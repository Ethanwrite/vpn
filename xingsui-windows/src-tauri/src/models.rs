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
    pub protocol: String,
    #[serde(default)]
    pub vip_only: bool,
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub load_percent: i32,
    #[serde(default)]
    pub locked: bool,
}

/// 后端签发的短期 Windows VLESS 租约（/vpn/nodes/{id}/config）。
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct VpnNodeConfig {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub region: String,
    #[serde(default)]
    pub tunnel_name: String,
    pub protocol: String,
    pub issued_at: String,
    pub expires_at: String,
    pub lease_id: String,
    pub config_text: String,
    #[serde(default)]
    pub vless_config: Option<VlessConfig>,
    pub entitlement: Entitlement,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Entitlement {
    pub allowed: bool,
    pub reason: String,
    pub vip_status: String,
    #[serde(default)]
    pub vip_expired_at: Option<String>,
    #[serde(default)]
    pub free_traffic_quota_bytes: i64,
    #[serde(default)]
    pub free_traffic_used_bytes: i64,
    #[serde(default)]
    pub free_traffic_remaining_bytes: i64,
    #[serde(default)]
    pub lease_expires_at: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct VlessConfig {
    pub server: String,
    #[serde(deserialize_with = "deserialize_port")]
    pub server_port: u16,
    pub uuid: String,
    #[serde(default)]
    pub flow: String,
    pub public_key: String,
    pub short_id: String,
    pub server_name: String,
    pub utls_fingerprint: String,
}

fn deserialize_port<'de, D>(deserializer: D) -> Result<u16, D::Error>
where
    D: serde::Deserializer<'de>,
{
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum PortValue {
        Number(u16),
        Text(String),
    }

    let port = match PortValue::deserialize(deserializer)? {
        PortValue::Number(port) => port,
        PortValue::Text(value) => value.parse::<u16>().map_err(serde::de::Error::custom)?,
    };
    if port == 0 {
        return Err(serde::de::Error::custom("端口不能为 0"));
    }
    Ok(port)
}

/// 网络接管模式。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum NetMode {
    /// TUN 全局接管。
    #[serde(alias = "tun")]
    Global,
    /// TUN 规则接管。
    Rule,
    /// 系统代理。
    SystemProxy,
}

impl Default for NetMode {
    fn default() -> Self {
        NetMode::Global
    }
}

impl NetMode {
    pub fn is_tun(self) -> bool {
        matches!(self, NetMode::Global | NetMode::Rule)
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn structured_vless_requires_explicit_valid_port_and_fields() {
        let valid = serde_json::json!({
            "server": "edge.example.com",
            "server_port": "443",
            "uuid": "123e4567-e89b-12d3-a456-426614174000",
            "flow": "xtls-rprx-vision",
            "public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "short_id": "0123456789abcdef",
            "server_name": "www.example.com",
            "utls_fingerprint": "chrome"
        });
        assert!(serde_json::from_value::<VlessConfig>(valid.clone()).is_ok());

        let mut missing_sni = valid.clone();
        missing_sni.as_object_mut().unwrap().remove("server_name");
        assert!(serde_json::from_value::<VlessConfig>(missing_sni).is_err());

        let mut zero_port = valid.clone();
        zero_port["server_port"] = serde_json::json!(0);
        assert!(serde_json::from_value::<VlessConfig>(zero_port).is_err());

        let mut unexpected = valid;
        unexpected["unexpected_field"] = serde_json::json!("forbidden");
        assert!(serde_json::from_value::<VlessConfig>(unexpected).is_err());
    }
}
