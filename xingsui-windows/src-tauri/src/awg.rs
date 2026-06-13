//! 解析后端下发的 AmneziaWG `.conf`（INI）文本。
//! 字段顺序见 node_service.AMNEZIA_PARAM_KEYS：Jc/Jmin/Jmax/S1/S2/H1-H4。

use crate::error::{AppError, AppResult};

/// 解析后的 AmneziaWG 配置（client 侧）。
#[derive(Debug, Clone, Default)]
pub struct AwgConfig {
    // [Interface]
    pub private_key: String,
    pub address: Vec<String>,
    pub dns: Vec<String>,
    pub mtu: Option<u32>,
    // 混淆参数（字符串形式，按需转数字）
    pub jc: Option<String>,
    pub jmin: Option<String>,
    pub jmax: Option<String>,
    pub s1: Option<String>,
    pub s2: Option<String>,
    pub h1: Option<String>,
    pub h2: Option<String>,
    pub h3: Option<String>,
    pub h4: Option<String>,
    // [Peer]
    pub peer_public_key: String,
    pub allowed_ips: Vec<String>,
    pub endpoint: String,
    pub persistent_keepalive: Option<u32>,
}

impl AwgConfig {
    /// endpoint 拆分为 (host, port)。
    pub fn endpoint_host_port(&self) -> AppResult<(String, u16)> {
        let (host, port) = self
            .endpoint
            .rsplit_once(':')
            .ok_or_else(|| AppError::config(format!("Endpoint 格式错误: {}", self.endpoint)))?;
        let port: u16 = port
            .trim()
            .parse()
            .map_err(|_| AppError::config(format!("Endpoint 端口非法: {}", self.endpoint)))?;
        Ok((host.trim().to_string(), port))
    }
}

fn split_csv(value: &str) -> Vec<String> {
    value
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

/// 解析 INI 文本为 AwgConfig。
pub fn parse(config_text: &str) -> AppResult<AwgConfig> {
    let mut cfg = AwgConfig::default();
    let mut section = "";

    for raw in config_text.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') || line.starts_with(';') {
            continue;
        }
        if line.starts_with('[') && line.ends_with(']') {
            section = match line.to_ascii_lowercase().as_str() {
                "[interface]" => "interface",
                "[peer]" => "peer",
                _ => "",
            };
            continue;
        }
        let Some((key, value)) = line.split_once('=') else {
            continue;
        };
        let key = key.trim();
        let value = value.trim().to_string();
        match (section, key.to_ascii_lowercase().as_str()) {
            ("interface", "privatekey") => cfg.private_key = value,
            ("interface", "address") => cfg.address = split_csv(&value),
            ("interface", "dns") => cfg.dns = split_csv(&value),
            ("interface", "mtu") => cfg.mtu = value.parse().ok(),
            ("interface", "jc") => cfg.jc = Some(value),
            ("interface", "jmin") => cfg.jmin = Some(value),
            ("interface", "jmax") => cfg.jmax = Some(value),
            ("interface", "s1") => cfg.s1 = Some(value),
            ("interface", "s2") => cfg.s2 = Some(value),
            ("interface", "h1") => cfg.h1 = Some(value),
            ("interface", "h2") => cfg.h2 = Some(value),
            ("interface", "h3") => cfg.h3 = Some(value),
            ("interface", "h4") => cfg.h4 = Some(value),
            ("peer", "publickey") => cfg.peer_public_key = value,
            ("peer", "allowedips") => cfg.allowed_ips = split_csv(&value),
            ("peer", "endpoint") => cfg.endpoint = value,
            ("peer", "persistentkeepalive") => cfg.persistent_keepalive = value.parse().ok(),
            _ => {}
        }
    }

    if cfg.private_key.is_empty() {
        return Err(AppError::config("缺少 PrivateKey"));
    }
    if cfg.peer_public_key.is_empty() {
        return Err(AppError::config("缺少 Peer PublicKey"));
    }
    if cfg.endpoint.is_empty() {
        return Err(AppError::config("缺少 Endpoint"));
    }
    if cfg.address.is_empty() {
        cfg.address = vec!["10.66.66.2/32".to_string()];
    }
    if cfg.allowed_ips.is_empty() {
        cfg.allowed_ips = vec!["0.0.0.0/0".to_string()];
    }
    Ok(cfg)
}
