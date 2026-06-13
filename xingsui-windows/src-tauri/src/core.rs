//! sing-box 内核进程管理：启动/停止、崩溃自动清理、模式切换。
//! 退出/崩溃/断开时务必恢复系统代理并关闭 TUN，防止断网。

use crate::awg::AwgConfig;
use crate::error::{AppError, AppResult};
use crate::models::{ConnState, NetMode, StatusPayload};
use crate::state::AppState;
use crate::{singbox_config, stats, sysproxy};
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

const PROXY_PORT: u16 = 7897;
const CLASH_PORT: u16 = 9191;

/// 启动内核连接到指定节点。
pub fn start(
    app: &AppHandle,
    cfg: AwgConfig,
    mode: NetMode,
    node_id: String,
    node_name: String,
) -> AppResult<()> {
    let state = app.state::<AppState>();
    // 先彻底清理上一次连接（幂等）。
    stop(app)?;

    let config_dir = state.config_dir();
    std::fs::create_dir_all(&config_dir)?;

    let value = singbox_config::build(&cfg, mode, PROXY_PORT, CLASH_PORT)?;
    let config_path = config_dir.join("config.json");
    std::fs::write(&config_path, serde_json::to_vec_pretty(&value)?)?;

    if mode == NetMode::Tun {
        copy_wintun(app, &config_dir)?;
    }

    // 系统代理模式：先备份并启用。
    let proxy_backup = if mode == NetMode::SystemProxy {
        Some(sysproxy::enable(PROXY_PORT)?)
    } else {
        None
    };

    let sidecar = app
        .shell()
        .sidecar("binaries/sing-box")
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
        rt.clash_port = CLASH_PORT;
        rt.mode = mode;
        rt.node_id = Some(node_id.clone());
        rt.node_name = Some(node_name.clone());
        rt.proxy_backup = proxy_backup;
        rt.state = ConnState::Connected;
    }
    emit_status(app, Some("已连接".into()));
    stats::spawn_traffic_poller(app.clone(), CLASH_PORT, generation);

    // 监控进程退出（崩溃自愈）。
    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            if let CommandEvent::Terminated(_) = event {
                break;
            }
        }
        cleanup_on_unexpected_exit(&app_handle, generation);
    });
    Ok(())
}

/// 主动停止：kill 内核 + 恢复系统配置（幂等）。
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

/// 进程意外退出时，若该连接代际仍有效则执行清理与状态回报。
fn cleanup_on_unexpected_exit(app: &AppHandle, generation: u64) {
    {
        let state = app.state::<AppState>();
        let rt = state.conn.lock();
        if rt.generation != generation {
            return; // 已被新的 start/stop 取代，无需处理。
        }
    }
    let _ = stop(app);
    emit_status(app, Some("连接已断开".into()));
}

/// 将 bundled wintun.dll 复制到内核工作目录，供 TUN 模式加载。
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

/// 读取运行时状态并推送给前端。
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
