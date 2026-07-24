//! 星隧 VPN Windows 客户端 Rust 壳入口。

mod api;
mod commands;
mod core;
mod error;
mod models;
mod singbox_config;
mod state;
mod stats;
mod store;
mod sysproxy;
mod vless;

use state::AppState;
use std::path::PathBuf;
use tauri::Manager;

/// 崩溃日志目录：%LOCALAPPDATA%\com.xingsui.vpn.desktop（回退到临时目录）。
fn crash_log_dir() -> PathBuf {
    let base = std::env::var_os("LOCALAPPDATA")
        .or_else(|| std::env::var_os("APPDATA"))
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir);
    base.join("com.xingsui.vpn.desktop")
}

/// 安装 panic 钩子：把 panic 现场追加写入 crash.log，避免静默闪退无从排查。
fn install_panic_logger() {
    let default_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let dir = crash_log_dir();
        let _ = std::fs::create_dir_all(&dir);
        let location = info
            .location()
            .map(|l| format!("{}:{}", l.file(), l.line()))
            .unwrap_or_else(|| "unknown".into());
        let payload = info
            .payload()
            .downcast_ref::<&str>()
            .map(|s| s.to_string())
            .or_else(|| info.payload().downcast_ref::<String>().cloned())
            .unwrap_or_else(|| "unknown panic".into());
        let line = format!(
            "[{}] v{} panic at {location}: {payload}\n",
            chrono::Utc::now().to_rfc3339(),
            api::version_name(),
        );
        use std::io::Write;
        if let Ok(mut f) = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(dir.join("crash.log"))
        {
            let _ = f.write_all(line.as_bytes());
        }
        default_hook(info);
    }));
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    install_panic_logger();
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // AppData 目录用于存放加密登录态与运行时配置。解析失败时回退到崩溃日志目录，
            // 绝不因目录/清理问题在启动阶段 panic 导致闪退。
            let app_dir = app
                .path()
                .app_data_dir()
                .unwrap_or_else(|_| crash_log_dir());
            std::fs::create_dir_all(&app_dir).ok();
            // 清理遗留敏感运行配置是尽力而为；失败（如文件被杀软/残留进程锁定）只记录，
            // 不阻断启动。
            if let Err(err) = core::cleanup_stale_runtime_files(&app_dir) {
                eprintln!("清理遗留运行配置失败（已忽略）: {err}");
            }
            app.manage(AppState::new(app_dir));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::login,
            commands::register,
            commands::restore_session,
            commands::get_me,
            commands::logout,
            commands::list_nodes,
            commands::connect,
            commands::disconnect,
            commands::switch_mode,
            commands::get_status,
        ])
        .on_window_event(|window, event| {
            // 关闭窗口时先清理内核与系统代理，防止断网。
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let _ = core::stop(&window.app_handle());
            }
        })
        .build(tauri::generate_context!())
        .expect("启动 Tauri 失败")
        .run(|app_handle, event| {
            // 进程退出（含异常）兜底清理。
            if let tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit = event {
                let _ = core::stop(app_handle);
            }
        });
}
