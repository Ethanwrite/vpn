//! 星隧 VPN Windows 客户端 Rust 壳入口。

mod api;
mod awg;
mod commands;
mod core;
mod error;
mod models;
mod singbox_config;
mod state;
mod stats;
mod store;
mod sysproxy;

use state::AppState;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // AppData 目录用于存放加密登录态与运行时配置。
            let app_dir = app.path().app_data_dir().expect("无法解析 AppData 目录");
            std::fs::create_dir_all(&app_dir).ok();
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
