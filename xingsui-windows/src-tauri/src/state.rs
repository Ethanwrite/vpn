//! 全局共享状态：API 客户端、登录态、连接运行时。

use crate::api::ApiClient;
use crate::models::{ConnState, NetMode};
use crate::sysproxy::ProxyBackup;
use parking_lot::{Mutex, RwLock};
use std::path::PathBuf;
use tauri_plugin_shell::process::CommandChild;

/// 当前连接运行时（受 Mutex 保护，跨命令共享）。
#[derive(Default)]
pub struct ConnRuntime {
    pub state: ConnState,
    pub mode: NetMode,
    pub node_id: Option<String>,
    pub node_name: Option<String>,
    /// sing-box 子进程句柄；断开时 kill。
    pub child: Option<CommandChild>,
    /// clash api 端口，用于轮询流量。
    pub clash_port: u16,
    /// 系统代理模式下备份的原注册表值，用于恢复。
    pub proxy_backup: Option<ProxyBackup>,
    /// 流量轮询任务的停止信号代际；每次连接自增使旧任务退出。
    pub generation: u64,
}

impl Default for ConnState {
    fn default() -> Self {
        ConnState::Disconnected
    }
}

pub struct AppState {
    pub api: ApiClient,
    pub token: RwLock<Option<String>>,
    pub app_dir: PathBuf,
    pub conn: Mutex<ConnRuntime>,
}

impl AppState {
    pub fn new(app_dir: PathBuf) -> Self {
        Self {
            api: ApiClient::new(),
            token: RwLock::new(None),
            app_dir,
            conn: Mutex::new(ConnRuntime::default()),
        }
    }

    /// 返回当前 token；无则 Unauthorized。
    pub fn require_token(&self) -> crate::error::AppResult<String> {
        self.token
            .read()
            .clone()
            .ok_or(crate::error::AppError::Unauthorized)
    }

    /// 运行时配置目录（AppData/config）。
    pub fn config_dir(&self) -> PathBuf {
        self.app_dir.join("config")
    }
}
