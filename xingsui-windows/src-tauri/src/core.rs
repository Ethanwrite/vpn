use crate::error::{AppError, AppResult, CONNECTION_SYNC_ERROR};
use crate::models::{ConnState, NetMode, StatusPayload, VlessConfig};
use crate::state::AppState;
use crate::{singbox_config, stats, sysproxy};
use chrono::{DateTime, Utc};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::time::Duration;
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const PROXY_PORT: u16 = 7897;
const CLASH_PORT: u16 = 9191;
const RUNTIME_CONFIG_PREFIX: &str = "xingsui-runtime-";
const SING_BOX_SHA256: &str = "db0d779948214cf761011d154c3a5da36df20394fa01a9fc798f1dc39fe9d183";
const WINTUN_SHA256: &str = "e5da8447dc2c320edc0fc52fa01885c103de8c118481f683643cacc3220dafce";

pub fn start_vless(
    app: &AppHandle,
    cfg: VlessConfig,
    mode: NetMode,
    node_id: String,
    node_name: String,
    tunnel_name: String,
    lease_id: String,
    lease_expires_at: DateTime<Utc>,
    generation: u64,
) -> AppResult<bool> {
    let proxy_port = available_port(PROXY_PORT);
    let clash_port = available_port_excluding(CLASH_PORT, proxy_port);
    let clash_secret = format!("{:032x}", rand::random::<u128>());
    let value = singbox_config::build_vless(&cfg, mode, proxy_port, clash_port, &clash_secret)?;
    start_with_config(
        app,
        value,
        mode,
        node_id,
        node_name,
        tunnel_name,
        lease_id,
        lease_expires_at,
        proxy_port,
        clash_port,
        clash_secret,
        generation,
    )
}

#[allow(clippy::too_many_arguments)]
fn start_with_config(
    app: &AppHandle,
    value: Value,
    mode: NetMode,
    node_id: String,
    node_name: String,
    tunnel_name: String,
    lease_id: String,
    lease_expires_at: DateTime<Utc>,
    proxy_port: u16,
    clash_port: u16,
    clash_secret: String,
    generation: u64,
) -> AppResult<bool> {
    if !connection_is_current_or_connecting(app, generation) {
        return Ok(false);
    }

    let resource_dir = verify_runtime_resources(app)?;
    let runtime_dir = {
        let state = app.state::<AppState>();
        state.config_dir()
    };
    std::fs::create_dir_all(&runtime_dir)?;
    let mut config_file = EphemeralConfig::create(&runtime_dir, &value)?;
    let config_path = config_file.path().to_path_buf();

    if !connection_is_current_or_connecting(app, generation) {
        return Ok(false);
    }

    let mut proxy_backup = if mode == NetMode::SystemProxy {
        Some(sysproxy::enable(proxy_port)?)
    } else {
        None
    };
    if !connection_is_current_or_connecting(app, generation) {
        restore_proxy_backup(&mut proxy_backup);
        return Ok(false);
    }

    let sidecar = match app.shell().sidecar("sing-box") {
        Ok(command) => command
            .args(["run", "-c", &config_path.to_string_lossy()])
            .current_dir(resource_dir),
        Err(error) => {
            restore_proxy_backup(&mut proxy_backup);
            return Err(AppError::core(format!("定位 sing-box 失败: {error}")));
        }
    };
    let (mut rx, child) = match sidecar.spawn() {
        Ok(result) => result,
        Err(error) => {
            restore_proxy_backup(&mut proxy_backup);
            return Err(AppError::core(format!("启动 sing-box 失败: {error}")));
        }
    };

    let mut stale_child: Option<CommandChild> = None;
    {
        let state = app.state::<AppState>();
        let mut rt = state.conn.lock();
        if rt.generation != generation || rt.state != ConnState::Connecting {
            stale_child = Some(child);
        } else {
            rt.child = Some(child);
            rt.config_path = Some(config_file.disarm());
            rt.clash_port = clash_port;
            rt.mode = mode;
            rt.node_id = Some(node_id);
            rt.node_name = Some(node_name);
            rt.proxy_backup = proxy_backup.take();
        }
    }
    if let Some(child) = stale_child {
        let _ = child.kill();
        restore_proxy_backup(&mut proxy_backup);
        return Ok(false);
    }

    emit_status(app, None);
    spawn_ready_check(
        app.clone(),
        generation,
        mode,
        proxy_port,
        clash_port,
        clash_secret,
        tunnel_name,
        lease_id,
        lease_expires_at,
    );

    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            if matches!(event, CommandEvent::Terminated(_)) {
                break;
            }
        }
        cleanup_on_unexpected_exit(&app_handle, generation);
    });
    Ok(true)
}

#[allow(clippy::too_many_arguments)]
fn spawn_ready_check(
    app: AppHandle,
    generation: u64,
    mode: NetMode,
    proxy_port: u16,
    clash_port: u16,
    clash_secret: String,
    tunnel_name: String,
    lease_id: String,
    lease_expires_at: DateTime<Utc>,
) {
    tauri::async_runtime::spawn(async move {
        if !wait_for_clash_api(&app, generation, clash_port, &clash_secret).await {
            fail_connection(&app, generation);
            return;
        }
        if remove_runtime_config(&app, generation).is_err() {
            fail_connection(&app, generation);
            return;
        }
        {
            let state = app.state::<AppState>();
            let mut rt = state.conn.lock();
            if rt.generation != generation || rt.state != ConnState::Connecting {
                return;
            }
            rt.state = ConnState::Connected;
        }
        emit_status(&app, Some("已连接".into()));
        stats::spawn_traffic_poller(
            app.clone(),
            clash_port,
            generation,
            clash_secret,
            tunnel_name,
            lease_id,
            lease_expires_at,
        );
        if mode == NetMode::SystemProxy {
            spawn_connectivity_check(app, generation, proxy_port);
        }
    });
}

pub fn stop(app: &AppHandle) -> AppResult<()> {
    let outcome = stop_runtime(app, None);
    outcome.cleanup_result
}

fn stop_runtime(app: &AppHandle, expected_generation: Option<u64>) -> StopOutcome {
    let state = app.state::<AppState>();
    let (child, config_path, backup, mode, was_active) = {
        let mut rt = state.conn.lock();
        if expected_generation.is_some_and(|expected| rt.generation != expected) {
            return StopOutcome::stale();
        }
        rt.generation = rt.generation.wrapping_add(1);
        let active = rt.state != ConnState::Disconnected || rt.child.is_some();
        let child = rt.child.take();
        let config_path = rt.config_path.take();
        let backup = rt.proxy_backup.take();
        let mode = rt.mode;
        rt.state = ConnState::Disconnected;
        rt.node_id = None;
        rt.node_name = None;
        (child, config_path, backup, mode, active)
    };
    if let Some(child) = child {
        let _ = child.kill();
    }
    if let Some(backup) = backup {
        let _ = sysproxy::restore(&backup);
    } else if mode == NetMode::SystemProxy {
        let _ = sysproxy::force_disable();
    }
    if was_active {
        emit_status(app, None);
    }
    let cleanup_result = config_path.map_or(Ok(()), |path| remove_file_if_exists(&path));
    StopOutcome {
        stopped: true,
        cleanup_result,
    }
}

pub fn fail_connection(app: &AppHandle, generation: u64) {
    let outcome = stop_runtime(app, Some(generation));
    if outcome.stopped {
        emit_status(app, Some(CONNECTION_SYNC_ERROR.into()));
    }
}

pub fn stop_attempt(app: &AppHandle, generation: u64) -> bool {
    stop_runtime(app, Some(generation)).stopped
}

fn cleanup_on_unexpected_exit(app: &AppHandle, generation: u64) {
    fail_connection(app, generation);
}

fn spawn_connectivity_check(app: AppHandle, generation: u64, proxy_port: u16) {
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(Duration::from_secs(4)).await;
        if !connection_is_current(&app, generation) {
            return;
        }
        if proxy_health_check(proxy_port).await {
            return;
        }
        fail_connection(&app, generation);
    });
}

pub fn connection_is_current_or_connecting(app: &AppHandle, generation: u64) -> bool {
    let state = app.state::<AppState>();
    let rt = state.conn.lock();
    rt.generation == generation && matches!(rt.state, ConnState::Connecting | ConnState::Connected)
}

fn connection_is_current(app: &AppHandle, generation: u64) -> bool {
    let state = app.state::<AppState>();
    let rt = state.conn.lock();
    rt.generation == generation && rt.state == ConnState::Connected
}

async fn wait_for_clash_api(
    app: &AppHandle,
    generation: u64,
    clash_port: u16,
    clash_secret: &str,
) -> bool {
    let url = format!("http://127.0.0.1:{clash_port}/traffic");
    let client = match reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
    {
        Ok(client) => client,
        Err(_) => return false,
    };

    for _ in 0..24 {
        if !connection_is_current_or_connecting(app, generation) {
            return false;
        }
        if client
            .get(&url)
            .bearer_auth(clash_secret)
            .send()
            .await
            .is_ok()
        {
            return true;
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
    false
}

async fn proxy_health_check(proxy_port: u16) -> bool {
    let proxy = match reqwest::Proxy::all(format!("http://127.0.0.1:{proxy_port}")) {
        Ok(proxy) => proxy,
        Err(_) => return false,
    };
    let client = match reqwest::Client::builder()
        .proxy(proxy)
        .timeout(Duration::from_secs(8))
        .build()
    {
        Ok(client) => client,
        Err(_) => return false,
    };
    for url in [
        "http://cp.cloudflare.com/generate_204",
        "http://connectivitycheck.gstatic.com/generate_204",
    ] {
        if let Ok(response) = client.get(url).send().await {
            if response.status() == reqwest::StatusCode::NO_CONTENT {
                return true;
            }
        }
    }
    false
}

fn available_port(preferred: u16) -> u16 {
    available_port_excluding(preferred, 0)
}

fn available_port_excluding(preferred: u16, excluded: u16) -> u16 {
    if preferred != excluded && port_is_available(preferred) {
        return preferred;
    }
    for port in preferred.saturating_add(1)..=preferred.saturating_add(200) {
        if port != excluded && port_is_available(port) {
            return port;
        }
    }
    std::net::TcpListener::bind(("127.0.0.1", 0))
        .ok()
        .and_then(|listener| listener.local_addr().ok())
        .map(|addr| addr.port())
        .filter(|port| *port != excluded)
        .unwrap_or(preferred)
}

fn port_is_available(port: u16) -> bool {
    std::net::TcpListener::bind(("127.0.0.1", port)).is_ok()
}

fn verify_runtime_resources(app: &AppHandle) -> AppResult<PathBuf> {
    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|error| AppError::system(format!("定位受保护资源目录失败: {error}")))?;
    let sidecar_name = if cfg!(windows) {
        "sing-box.exe"
    } else {
        "sing-box"
    };
    verify_sha256(
        &resource_dir.join(sidecar_name),
        SING_BOX_SHA256,
        "sing-box",
    )?;
    verify_sha256(
        &resource_dir.join("wintun.dll"),
        WINTUN_SHA256,
        "wintun.dll",
    )?;
    Ok(resource_dir)
}

fn verify_sha256(path: &Path, expected: &str, label: &str) -> AppResult<()> {
    let mut file =
        File::open(path).map_err(|_| AppError::system(format!("{label} 缺失或无法读取")))?;
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    let actual = format!("{:x}", hasher.finalize());
    if actual != expected {
        return Err(AppError::system(format!("{label} 完整性校验失败")));
    }
    Ok(())
}

pub fn cleanup_stale_runtime_files(app_dir: &Path) -> AppResult<()> {
    cleanup_stale_runtime_files_in(&app_dir.join("config"))
}

fn cleanup_stale_runtime_files_in(runtime_dir: &Path) -> AppResult<()> {
    if !runtime_dir.exists() {
        return Ok(());
    }
    for entry in std::fs::read_dir(runtime_dir)? {
        let entry = entry?;
        let file_name = entry.file_name();
        let file_name = file_name.to_string_lossy();
        let stale = file_name == "config.json"
            || file_name == "wintun.dll"
            || file_name == "sing-box.log"
            || (file_name.starts_with(RUNTIME_CONFIG_PREFIX) && file_name.ends_with(".json"));
        if stale {
            remove_file_if_exists(&entry.path())?;
        }
    }
    Ok(())
}

fn remove_runtime_config(app: &AppHandle, generation: u64) -> AppResult<()> {
    let path = {
        let state = app.state::<AppState>();
        let mut rt = state.conn.lock();
        if rt.generation != generation {
            return Ok(());
        }
        rt.config_path.take()
    };
    if let Some(path) = path {
        remove_file_if_exists(&path)?;
    }
    Ok(())
}

fn remove_file_if_exists(path: &Path) -> AppResult<()> {
    match std::fs::remove_file(path) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(AppError::system(format!("清理临时文件失败: {error}"))),
    }
}

fn restore_proxy_backup(backup: &mut Option<sysproxy::ProxyBackup>) {
    if let Some(backup) = backup.take() {
        let _ = sysproxy::restore(&backup);
    }
}

struct EphemeralConfig {
    path: Option<PathBuf>,
}

impl EphemeralConfig {
    fn create(runtime_dir: &Path, value: &Value) -> AppResult<Self> {
        for _ in 0..16 {
            let path = runtime_dir.join(format!(
                "{RUNTIME_CONFIG_PREFIX}{:032x}.json",
                rand::random::<u128>()
            ));
            let file = OpenOptions::new().write(true).create_new(true).open(&path);
            let mut file = match file {
                Ok(file) => file,
                Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(error) => return Err(error.into()),
            };
            let guard = Self { path: Some(path) };
            file.write_all(&serde_json::to_vec(value)?)?;
            file.sync_all()?;
            return Ok(guard);
        }
        Err(AppError::system("无法创建随机临时配置文件"))
    }

    fn path(&self) -> &Path {
        self.path.as_deref().expect("临时配置路径已转移")
    }

    fn disarm(&mut self) -> PathBuf {
        self.path.take().expect("临时配置路径已转移")
    }
}

impl Drop for EphemeralConfig {
    fn drop(&mut self) {
        if let Some(path) = self.path.take() {
            let _ = std::fs::remove_file(path);
        }
    }
}

struct StopOutcome {
    stopped: bool,
    cleanup_result: AppResult<()>,
}

impl StopOutcome {
    fn stale() -> Self {
        Self {
            stopped: false,
            cleanup_result: Ok(()),
        }
    }
}

pub fn emit_status(app: &AppHandle, message: Option<String>) {
    let state = app.state::<AppState>();
    let rt = state.conn.lock();
    let payload = StatusPayload {
        state: rt.state,
        node_id: rt.node_id.clone(),
        node_name: rt.node_name.clone(),
        mode: rt.mode,
        message,
    };
    drop(rt);
    let _ = app.emit("status", payload);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pinned_hashes_are_lowercase_sha256() {
        for hash in [SING_BOX_SHA256, WINTUN_SHA256] {
            assert_eq!(hash.len(), 64);
            assert!(hash.bytes().all(|byte| byte.is_ascii_hexdigit()));
            assert_eq!(hash, hash.to_ascii_lowercase());
        }
    }

    #[test]
    fn ephemeral_config_is_random_and_removed_on_drop() {
        let dir =
            std::env::temp_dir().join(format!("xingsui-core-test-{:032x}", rand::random::<u128>()));
        std::fs::create_dir_all(&dir).unwrap();
        let first_path;
        {
            let first = EphemeralConfig::create(&dir, &serde_json::json!({"test": 1})).unwrap();
            let second = EphemeralConfig::create(&dir, &serde_json::json!({"test": 2})).unwrap();
            first_path = first.path().to_path_buf();
            assert_ne!(first.path(), second.path());
            assert!(first.path().exists());
            assert!(second.path().exists());
        }
        assert!(!first_path.exists());
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn stale_cleanup_removes_only_sensitive_runtime_files() {
        let dir = std::env::temp_dir().join(format!(
            "xingsui-cleanup-test-{:032x}",
            rand::random::<u128>()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("config.json"), b"secret").unwrap();
        std::fs::write(dir.join("wintun.dll"), b"untrusted").unwrap();
        std::fs::write(dir.join("xingsui-runtime-deadbeef.json"), b"secret").unwrap();
        std::fs::write(dir.join("sing-box.log"), b"legacy endpoint log").unwrap();
        cleanup_stale_runtime_files_in(&dir).unwrap();
        assert!(!dir.join("config.json").exists());
        assert!(!dir.join("wintun.dll").exists());
        assert!(!dir.join("xingsui-runtime-deadbeef.json").exists());
        assert!(!dir.join("sing-box.log").exists());
        std::fs::remove_dir_all(dir).unwrap();
    }
}
