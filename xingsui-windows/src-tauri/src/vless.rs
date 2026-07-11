use crate::error::{AppError, AppResult};
use crate::models::{VlessConfig, VpnNodeConfig};
use base64::Engine;
use chrono::{DateTime, Duration, Utc};
use std::net::IpAddr;

const MAX_CLOCK_SKEW: Duration = Duration::seconds(60);
const MAX_ISSUE_AGE: Duration = Duration::minutes(5);
const MAX_LEASE_LIFETIME: Duration = Duration::minutes(15);
const MIN_LEASE_REMAINING: Duration = Duration::seconds(30);
const ALLOWED_FINGERPRINTS: &[&str] = &[
    "chrome", "firefox", "edge", "safari", "ios", "android", "360", "qq",
];

#[derive(Debug, Clone)]
pub struct ValidatedNodeConfig {
    pub vless: VlessConfig,
    pub lease_id: String,
    pub expires_at: DateTime<Utc>,
}

pub fn validate_node_config(
    config: &VpnNodeConfig,
    now: DateTime<Utc>,
) -> AppResult<ValidatedNodeConfig> {
    if config.protocol != "vless" {
        return Err(AppError::config("Windows 仅接受 VLESS 配置"));
    }
    validate_entitlement(config, now)?;
    let (issued_at, expires_at) = validate_lease(config, now)?;
    let lease_id = config.lease_id.trim();
    if lease_id != config.lease_id
        || lease_id.is_empty()
        || lease_id.len() > 128
        || !lease_id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
    {
        return Err(AppError::config("租约标识格式错误"));
    }
    let tunnel_name = config.tunnel_name.trim();
    if tunnel_name != config.tunnel_name
        || tunnel_name.is_empty()
        || tunnel_name.len() > 64
        || !tunnel_name
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
    {
        return Err(AppError::config("隧道标识格式错误"));
    }

    let link_config = if config.config_text.trim().is_empty() {
        None
    } else {
        Some(parse_vless_link(&config.config_text)?)
    };
    let vless = match (&config.vless_config, link_config) {
        (Some(structured), Some(link)) => {
            validate_vless_config(structured)?;
            if structured != &link {
                return Err(AppError::config("VLESS 结构化配置与链接不一致"));
            }
            structured.clone()
        }
        (Some(structured), None) => {
            validate_vless_config(structured)?;
            structured.clone()
        }
        (None, Some(link)) => link,
        (None, None) => return Err(AppError::config("VLESS 配置为空")),
    };

    debug_assert!(expires_at > issued_at);
    Ok(ValidatedNodeConfig {
        vless,
        lease_id: lease_id.to_string(),
        expires_at,
    })
}

fn validate_entitlement(config: &VpnNodeConfig, now: DateTime<Utc>) -> AppResult<()> {
    let entitlement = &config.entitlement;
    // 与 Android 端一致的业务规则：后端已判定授权（VIP 有效或免费流量剩余>0）时放行；
    // 免费流量用户 reason=free_trial / vip_status=inactive，不再被 VIP-only 拦截。
    if !entitlement.allowed {
        return Err(AppError::config("账户无有效授权"));
    }
    // 仅 VIP 用户校验 VIP 到期时间；免费流量用户无 VIP 到期时间，凭剩余流量放行。
    if entitlement.vip_status == "active" {
        let vip_expires_at = entitlement
            .vip_expired_at
            .as_deref()
            .ok_or_else(|| AppError::config("VIP 到期时间缺失"))?;
        if parse_timestamp(vip_expires_at, "VIP 到期时间")? <= now {
            return Err(AppError::config("VIP 已到期"));
        }
    }
    let entitlement_lease = entitlement
        .lease_expires_at
        .as_deref()
        .ok_or_else(|| AppError::config("授权租约到期时间缺失"))?;
    if parse_timestamp(entitlement_lease, "授权租约到期时间")?
        != parse_timestamp(&config.expires_at, "租约到期时间")?
    {
        return Err(AppError::config("授权租约与节点租约不一致"));
    }
    Ok(())
}

fn validate_lease(
    config: &VpnNodeConfig,
    now: DateTime<Utc>,
) -> AppResult<(DateTime<Utc>, DateTime<Utc>)> {
    let issued_at = parse_timestamp(&config.issued_at, "租约签发时间")?;
    let expires_at = parse_timestamp(&config.expires_at, "租约到期时间")?;
    if issued_at > now + MAX_CLOCK_SKEW || issued_at < now - MAX_ISSUE_AGE {
        return Err(AppError::config("租约签发时间无效"));
    }
    if expires_at <= now + MIN_LEASE_REMAINING || expires_at <= issued_at {
        return Err(AppError::config("租约已到期"));
    }
    if expires_at - issued_at > MAX_LEASE_LIFETIME {
        return Err(AppError::config("租约有效期过长"));
    }
    Ok((issued_at, expires_at))
}

fn parse_timestamp(value: &str, field: &str) -> AppResult<DateTime<Utc>> {
    if value != value.trim() {
        return Err(AppError::config(format!("{field}格式错误")));
    }
    DateTime::parse_from_rfc3339(value)
        .map(|timestamp| timestamp.with_timezone(&Utc))
        .map_err(|_| AppError::config(format!("{field}格式错误")))
}

pub fn parse_vless_link(config_text: &str) -> AppResult<VlessConfig> {
    let text = config_text.trim();
    if !text.starts_with("vless://") {
        return Err(AppError::config("Windows 拒绝非 VLESS 配置"));
    }
    let url = reqwest::Url::parse(text).map_err(|_| AppError::config("VLESS 链接格式错误"))?;
    if url.scheme() != "vless" || url.password().is_some() {
        return Err(AppError::config("VLESS 链接格式错误"));
    }
    const ALLOWED_QUERY_KEYS: &[&str] = &[
        "encryption",
        "security",
        "type",
        "sni",
        "fp",
        "pbk",
        "sid",
        "flow",
    ];
    if url
        .query_pairs()
        .any(|(name, _)| !ALLOWED_QUERY_KEYS.contains(&name.as_ref()))
    {
        return Err(AppError::config("VLESS 链接包含未支持参数"));
    }
    let server = url
        .host_str()
        .map(str::trim)
        .filter(|host| !host.is_empty())
        .ok_or_else(|| AppError::config("VLESS 链接缺少服务器地址"))?
        .to_string();
    let server_port = url
        .port()
        .filter(|port| *port != 0)
        .ok_or_else(|| AppError::config("VLESS 链接缺少有效端口"))?;
    let uuid = url.username().trim().to_string();
    let flow = optional_query_value(&url, "flow")?.unwrap_or_default();
    let security = required_query_value(&url, "security")?;
    if security != "reality" {
        return Err(AppError::config("VLESS 链接未启用 Reality"));
    }
    if required_query_value(&url, "type")? != "tcp" {
        return Err(AppError::config("Windows VLESS 仅接受 TCP 传输"));
    }
    let encryption = required_query_value(&url, "encryption")?;
    if encryption != "none" {
        return Err(AppError::config("VLESS encryption 参数无效"));
    }
    let config = VlessConfig {
        server,
        server_port,
        uuid,
        flow,
        public_key: required_query_value(&url, "pbk")?,
        short_id: required_query_value(&url, "sid")?,
        server_name: required_query_value(&url, "sni")?,
        utls_fingerprint: required_query_value(&url, "fp")?,
    };
    validate_vless_config(&config)?;
    Ok(config)
}

fn required_query_value(url: &reqwest::Url, key: &str) -> AppResult<String> {
    optional_query_value(url, key)?.ok_or_else(|| AppError::config(format!("VLESS 缺少 {key}")))
}

fn optional_query_value(url: &reqwest::Url, key: &str) -> AppResult<Option<String>> {
    let values = url
        .query_pairs()
        .filter(|(name, _)| name == key)
        .map(|(_, value)| value.trim().to_string())
        .collect::<Vec<_>>();
    if values.len() > 1 {
        return Err(AppError::config(format!("VLESS {key} 参数重复")));
    }
    Ok(values.into_iter().next().filter(|value| !value.is_empty()))
}

pub fn validate_vless_config(config: &VlessConfig) -> AppResult<()> {
    if !valid_server(&config.server) || config.server_port == 0 {
        return Err(AppError::config("VLESS 服务器地址或端口无效"));
    }
    if !valid_uuid(&config.uuid) {
        return Err(AppError::config("VLESS UUID 格式错误"));
    }
    if !config.flow.is_empty() && config.flow != "xtls-rprx-vision" {
        return Err(AppError::config("VLESS flow 参数无效"));
    }
    let decoded_public_key = base64::engine::general_purpose::URL_SAFE_NO_PAD
        .decode(config.public_key.as_bytes())
        .ok();
    if config.public_key.len() != 43
        || !config
            .public_key
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
        || decoded_public_key.as_deref().map(|value| value.len()) != Some(32)
    {
        return Err(AppError::config("Reality public key 格式错误"));
    }
    if config.short_id.is_empty()
        || config.short_id.len() > 16
        || config.short_id.len() % 2 != 0
        || !config.short_id.bytes().all(|byte| byte.is_ascii_hexdigit())
    {
        return Err(AppError::config("Reality short id 格式错误"));
    }
    if !valid_dns_name(&config.server_name) || config.server_name.parse::<IpAddr>().is_ok() {
        return Err(AppError::config("Reality SNI 格式错误"));
    }
    if !ALLOWED_FINGERPRINTS.contains(&config.utls_fingerprint.as_str()) {
        return Err(AppError::config("Reality fingerprint 不受支持"));
    }
    Ok(())
}

fn valid_server(value: &str) -> bool {
    if value != value.trim() {
        return false;
    }
    !value.is_empty() && (value.parse::<IpAddr>().is_ok() || valid_dns_name(value))
}

fn valid_dns_name(value: &str) -> bool {
    if value.is_empty() || value.len() > 253 || !value.contains('.') {
        return false;
    }
    value.split('.').all(|label| {
        !label.is_empty()
            && label.len() <= 63
            && !label.starts_with('-')
            && !label.ends_with('-')
            && label
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-')
    })
}

fn valid_uuid(value: &str) -> bool {
    if value.len() != 36 {
        return false;
    }
    value.bytes().enumerate().all(|(index, byte)| {
        if matches!(index, 8 | 13 | 18 | 23) {
            byte == b'-'
        } else {
            byte.is_ascii_hexdigit()
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::Entitlement;

    fn valid_vless() -> VlessConfig {
        VlessConfig {
            server: "edge.example.com".into(),
            server_port: 443,
            uuid: "123e4567-e89b-12d3-a456-426614174000".into(),
            flow: "xtls-rprx-vision".into(),
            public_key: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA".into(),
            short_id: "0123456789abcdef".into(),
            server_name: "www.example.com".into(),
            utls_fingerprint: "chrome".into(),
        }
    }

    fn node_config(now: DateTime<Utc>) -> VpnNodeConfig {
        VpnNodeConfig {
            id: "node-1".into(),
            name: "Test".into(),
            region: "Test".into(),
            tunnel_name: "xingsui".into(),
            protocol: "vless".into(),
            issued_at: now.to_rfc3339(),
            expires_at: (now + Duration::minutes(5)).to_rfc3339(),
            lease_id: "lease-123".into(),
            config_text: String::new(),
            vless_config: Some(valid_vless()),
            entitlement: Entitlement {
                allowed: true,
                reason: "vip_active".into(),
                vip_status: "active".into(),
                vip_expired_at: Some((now + Duration::days(1)).to_rfc3339()),
                free_traffic_quota_bytes: 0,
                free_traffic_used_bytes: 0,
                free_traffic_remaining_bytes: 0,
                lease_expires_at: Some((now + Duration::minutes(5)).to_rfc3339()),
            },
        }
    }

    #[test]
    fn accepts_strict_vless_and_live_lease() {
        let now = Utc::now();
        assert!(validate_node_config(&node_config(now), now).is_ok());
    }

    #[test]
    fn rejects_expired_or_overlong_lease() {
        let now = Utc::now();
        let mut expired = node_config(now);
        expired.expires_at = (now - Duration::seconds(1)).to_rfc3339();
        assert!(validate_node_config(&expired, now).is_err());

        let mut overlong = node_config(now);
        overlong.expires_at = (now + Duration::minutes(16)).to_rfc3339();
        assert!(validate_node_config(&overlong, now).is_err());
    }

    #[test]
    fn accepts_free_trial_entitlement() {
        let now = Utc::now();
        let mut free = node_config(now);
        free.entitlement.reason = "free_trial".into();
        free.entitlement.vip_status = "inactive".into();
        free.entitlement.vip_expired_at = None;
        free.entitlement.free_traffic_remaining_bytes = 10_000_000;
        // 免费流量用户应放行，与 Android 端一致。
        assert!(validate_node_config(&free, now).is_ok());
    }

    #[test]
    fn rejects_denied_entitlement_and_non_vless_protocol() {
        let now = Utc::now();
        let mut denied = node_config(now);
        denied.entitlement.allowed = false;
        assert!(validate_node_config(&denied, now).is_err());

        let mut non_vless = node_config(now);
        non_vless.protocol = "amneziawg".into();
        assert!(validate_node_config(&non_vless, now).is_err());
    }

    #[test]
    fn rejects_invalid_reality_fields() {
        let cases = [
            ("uuid", "bad"),
            ("public_key", "short"),
            ("short_id", "xyz"),
            ("server_name", "127.0.0.1"),
            ("fingerprint", "random"),
        ];
        for (field, value) in cases {
            let mut config = valid_vless();
            match field {
                "uuid" => config.uuid = value.into(),
                "public_key" => config.public_key = value.into(),
                "short_id" => config.short_id = value.into(),
                "server_name" => config.server_name = value.into(),
                "fingerprint" => config.utls_fingerprint = value.into(),
                _ => unreachable!(),
            }
            assert!(validate_vless_config(&config).is_err(), "field={field}");
        }
    }

    #[test]
    fn link_requires_explicit_reality_values_and_port() {
        let valid = concat!(
            "vless://123e4567-e89b-12d3-a456-426614174000@edge.example.com:443",
            "?encryption=none&security=reality&type=tcp&sni=www.example.com&fp=chrome",
            "&pbk=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA&sid=0123456789abcdef",
            "&flow=xtls-rprx-vision"
        );
        assert!(parse_vless_link(valid).is_ok());
        assert!(parse_vless_link("vless://user@edge.example.com").is_err());
        assert!(parse_vless_link("[Interface]\nAddress = 192.0.2.2/32").is_err());
    }
}
