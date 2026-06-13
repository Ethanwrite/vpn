//! 与后端控制面对齐的数据模型（字段名严格匹配后端 JSON）。

use serde::{Deserialize, Serialize};

/// 后端用户对象（/me、登录响应中的 user）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    pub id: String,
    pub email: String,
    #[serde(default)]
    pub nickname: String,
    #[serde(default)]
    pub invite_code: String,
    #[serde(default = "default_inactive")]
    pub vip_status: String,
    #[serde(default)]
    pub vip_expired_at: Option<String>,
    #[serde(default)]
    pub cash_balance_cents: i64,
    #[serde(default)]
    pub free_traffic_quota_bytes: i64,
    #[serde(default)]
    pub free_traffic_used_bytes: i64,
    #[serde(default)]
    pub free_traffic_remaining_bytes: i64,
}

fn default_inactive() -> String {
    "inactive".to_string()
}

/// 登录 / 注册响应。
#[derive(Debug, Clone, Deserialize)]
pub struct AuthResponse {
    pub access_token: String,
    #[serde(default)]
    pub token_type: String,
    pub user: User,
}

/// 节点摘要（/vpn/nodes）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VpnNodeSummary {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub region: String,
    #[serde(default)]
    pub vip_only: bool,
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub load_percent: i32,
    #[serde(default)]
    pub locked: bool,
}

/// 节点配置（/vpn/nodes/{id}/config）。config_text 为 AmneziaWG INI。
#[derive(Debug, Clone, Deserialize)]
pub struct VpnNodeConfig {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub region: String,
    #[serde(default)]
    pub tunnel_name: String,
    pub config_text: String,
}

/// 网络接管模式。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum NetMode {
    /// TUN 全局接管（wintun）
    Tun,
    /// 系统代理（注册表）
    SystemProxy,
}

impl Default for NetMode {
    fn default() -> Self {
        NetMode::Tun
    }
}

/// 连接状态机。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ConnState {
    Disconnected,
    Connecting,
    Connected,
}

/// 推送给前端的实时状态。
#[derive(Debug, Clone, Serialize)]
pub struct StatusPayload {
    pub state: ConnState,
    pub node_id: Option<String>,
    pub node_name: Option<String>,
    pub mode: NetMode,
    pub message: Option<String>,
}

/// 推送给前端的实时速率（字节/秒）与累计流量。
#[derive(Debug, Clone, Copy, Serialize)]
pub struct StatsPayload {
    pub up_bps: u64,
    pub down_bps: u64,
    pub up_total: u64,
    pub down_total: u64,
}
