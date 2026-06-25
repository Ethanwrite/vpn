use crate::awg::AwgConfig;
use crate::error::{AppError, AppResult};
use crate::models::{ConnState, NetMode, StatusPayload, VlessConfig};
use crate::state::AppState;
use crate::{singbox_config, stats, sysproxy};
use serde_json::Value;
use std::io::Write;
use std::time::Duration;
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

const PROXY_PORT: u16 = 7897;
const CLASH_PORT: u16 = 9191;

pub fn start(
    app: &AppHandle,
    cfg: AwgConfig,
    mode: NetMode,
    node_id: String,
    node_name: String,
) -> AppResult<()> {
    let proxy_port = available_port(PROXY_PORT);
    let clash_port = available_port_excluding(CLASH_PORT, proxy_port);
    let value = singbox_config::build(&cfg, mode, proxy_port, clash_port)?;
    start_with_config(app, value, mode, node_id, node_name, proxy_port, clash_port)
}

pub fn start_vless(
    app: &AppHandle,
    cfg: VlessConfig,
    mode: NetMode,
    node_id: String,
    node_name: String,
) -> AppResult<()> {
    let proxy_port = available_port(PROXY_PORT);
    let clash_port = available_port_excluding(CLASH_PORT, proxy_port);
    let value = singbox_config::build_vless(&cfg, mode, proxy_port, clash_port)?;
    start_with_config(app, value, mode, node_id, node_name, proxy_port, clash_port)
}

fn start_with_config(
    app: &AppHandle,
    value: Value,
    mode: NetMode,
    node_id: String,
    node_name: String,
    proxy_port: u16,
    clash_port: u16,
) -> AppResult<()> {
    let state = app.state::<AppState>();
    stop(app)?;

    let config_dir = state.config_dir();
    std::fs::create_dir_all(&config_dir)?;

    let config_path = config_dir.join("config.json");
    std::fs::write(&config_path, serde_json::to_vec_pretty(&value)?)?;
    let log_path = config_dir.join("sing-box.log");
    let mut log_file = std::fs::File::create(&log_path)?;
    writeln!(
        log_file,
        "starting sing-box with config {}",
        config_path.display()
    )?;

    if mode.is_tun() {
        copy_wintun(app, &config_dir)?;
    }

    let proxy_backup = if mode == NetMode::SystemProxy {
        Some(sysproxy::enable(proxy_port)?)
    } else {
        None
    };

    let sidecar = app
        .shell()
        .sidecar("sing-box")
        .map_err(|e| AppError::core(format!("定位 sing-box 失败: {e}")))?
        .args(["run", "-c", &config_path.to_string_lossy()])
        .current_dir(config_dir);

    let (mut rx, child) = sidecar
        .spawn()
        .map_err(|e| AppError::core(format!("启动 sing-box 失败: {e}")))?;

    let generation;
    {
        let mut rt = state.conn.lock();
        rt.generation = rt.generation.wrapping_add(1);
        generation = rt.generation;
        rt.child = Some(child);
        rt.clash_port = clash_port;
        rt.mode = mode;
        rt.node_id = Some(node_id.clone());
        rt.node_name = Some(node_name.clone());
        rt.proxy_backup = proxy_backup;
        rt.state = ConnState::Connecting;
    }
    emit_status(app, Some("正在启动内核...".into()));

    spawn_ready_check(
        app.clone(),
        generation,
        mode,
        proxy_port,
        clash_port,
        log_path.clone(),
    );

    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        let mut last_output = String::new();
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stderr(line) | CommandEvent::Stdout(line) => {
                    let text = String::from_utf8_lossy(&line);
                    let _ = write!(log_file, "{text}");
                    last_output.push_str(&text);
                    last_output.push('\n');
                    if last_output.len() > 4000 {
                        let keep_from = last_output.len().saturating_sub(3000);
                        last_output = last_output[keep_from..].to_string();
                    }
                }
                CommandEvent::Error(e) => {
                    let _ = writeln!(log_file, "{e}");
                    last_output.push_str(&e);
                    last_output.push('\n');
                }
                CommandEvent::Terminated(status) => {
                    let _ = writeln!(log_file, "sing-box terminated: {status:?}");
                    break;
                }
                _ => {}
            }
        }
        cleanup_on_unexpected_exit(&app_handle, generation, last_output);
    });
    Ok(())
}

fn spawn_ready_check(
    app: AppHandle,
    generation: u64,
    mode: NetMode,
    proxy_port: u16,
    clash_port: u16,
    log_path: std::path::PathBuf,
) {
    tauri::async_runtime::spawn(async move {
        if wait_for_clash_api(&app, generation, clash_port).await {
            {
                let state = app.state::<AppState>();
                let mut rt = state.conn.lock();
                if rt.generation != generation {
                    return;
                }
                rt.state = ConnState::Connected;
            }
            emit_status(&app, Some("已连接".into()));
            stats::spawn_traffic_poller(app.clone(), clash_port, generation);
            if mode == NetMode::SystemProxy {
                spawn_connectivity_check(app.clone(), generation, proxy_port);
            }
            return;
        }

        if connection_is_current_or_connecting(&app, generation) {
            let _ = stop(&app);
            emit_status(
                &app,
                Some(format!(
                    "连接失败：内核已启动，但本地控制端口未就绪，请查看日志 {}",
                    log_path.display()
                )),
            );
        }
    });
}

pub fn stop(app: &AppHandle) -> AppResult<()> {
    let state = app.state::<AppState>();
    let (child, backup, mode, was_active) = {
        let mut rt = state.conn.lock();
        rt.generation = rt.generation.wrapping_add(1);
        let active = rt.state != ConnState::Disconnected || rt.child.is_some();
        let child = rt.child.take();
        let backup = rt.proxy_backup.take();
        let mode = rt.mode;
        rt.state = ConnState::Disconnected;
        rt.node_id = None;
        rt.node_name = None;
        (child, backup, mode, active)
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
    Ok(())
}

fn cleanup_on_unexpected_exit(app: &AppHandle, generation: u64, output: String) {
    {
        let state = app.state::<AppState>();
        let rt = state.conn.lock();
        if rt.generation != generation {
            return;
        }
    }
    let _ = stop(app);
    emit_status(app, Some(singbox_exit_message(&output)));
}

fn singbox_exit_message(output: &str) -> String {
    let cleaned = strip_ansi(output).replace('\r', "");
    let important = cleaned
        .lines()
        .rev()
        .find(|line| line.contains("FATAL") || line.contains("ERROR"))
        .or_else(|| cleaned.lines().rev().find(|line| !line.trim().is_empty()))
        .unwrap_or("sing-box exited unexpectedly")
        .trim();

    if important.contains("Access is denied") {
        "全局/TUN 模式创建虚拟网卡被 Windows 拒绝。请安装新版后从开始菜单正常启动，若仍失败请卸载残留虚拟网卡或暂用代理模式。".into()
    } else {
        format!("连接已断开：{important}")
    }
}

fn strip_ansi(input: &str) -> String {
    let mut out = String::with_capacity(input.len());
    let mut chars = input.chars().peekable();
    while let Some(ch) = chars.next() {
        if ch == '\u{1b}' && chars.peek() == Some(&'[') {
            chars.next();
            for c in chars.by_ref() {
                if c.is_ascii_alphabetic() {
                    break;
                }
            }
        } else {
            out.push(ch);
        }
    }
    out
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
        if !connection_is_current(&app, generation) {
            return;
        }

        let _ = stop(&app);
        emit_status(
            &app,
            Some("连接失败：内核已启动，但网络连通性检查未通过，请切换线路或稍后重试。".into()),
        );
    });
}

fn connection_is_current(app: &AppHandle, generation: u64) -> bool {
    let state = app.state::<AppState>();
    let rt = state.conn.lock();
    rt.generation == generation && rt.state == ConnState::Connected
}

fn connection_is_current_or_connecting(app: &AppHandle, generation: u64) -> bool {
    let state = app.state::<AppState>();
    let rt = state.conn.lock();
    rt.generation == generation && matches!(rt.state, ConnState::Connecting | ConnState::Connected)
}

async fn wait_for_clash_api(app: &AppHandle, generation: u64, clash_port: u16) -> bool {
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
        if client.get(&url).send().await.is_ok() {
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
        if client.get(url).send().await.is_ok() {
            return true;
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

fn copy_wintun(app: &AppHandle, config_dir: &std::path::Path) -> AppResult<()> {
    let src = app
        .path()
        .resolve("wintun.dll", tauri::path::BaseDirectory::Resource)
        .map_err(|e| AppError::system(format!("定位 wintun.dll 失败: {e}")))?;
    let dst = config_dir.join("wintun.dll");
    if src.exists() && !dst.exists() {
        std::fs::copy(&src, &dst)?;
    }
    Ok(())
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
