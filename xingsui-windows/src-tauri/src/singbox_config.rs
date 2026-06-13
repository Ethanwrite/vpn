//! 将 AmneziaWG 配置转换为 sing-box config.json。
//!
//! 注意：混淆字段（jc/jmin/jmax/s1/s2/h1-h4）需要 AmneziaWG-capable 的
//! sing-box 构建（如 Leadaxe/sing-box-lx）。这些字段直接提升到 wireguard
//! endpoint 顶层。`awg_fields()` 集中映射，便于按内核分支微调。

use crate::awg::AwgConfig;
use crate::error::AppResult;
use crate::models::NetMode;
use serde_json::{json, Map, Value};

const WG_TAG: &str = "wg-out";
const TUN_IFACE: &str = "xingsui-tun";

/// 生成完整 sing-box 配置。
pub fn build(
    cfg: &AwgConfig,
    mode: NetMode,
    proxy_port: u16,
    clash_port: u16,
) -> AppResult<Value> {
    let (host, port) = cfg.endpoint_host_port()?;
    let mtu = cfg.mtu.unwrap_or(1420);

    let mut endpoint = Map::new();
    endpoint.insert("type".into(), json!("wireguard"));
    endpoint.insert("tag".into(), json!(WG_TAG));
    endpoint.insert("system".into(), json!(false));
    endpoint.insert("mtu".into(), json!(mtu));
    endpoint.insert("address".into(), json!(cfg.address));
    endpoint.insert("private_key".into(), json!(cfg.private_key));
    endpoint.insert(
        "peers".into(),
        json!([{
            "address": host,
            "port": port,
            "public_key": cfg.peer_public_key,
            "allowed_ips": cfg.allowed_ips,
            "persistent_keepalive_interval": cfg.persistent_keepalive.unwrap_or(25),
            "reserved": [0, 0, 0]
        }]),
    );
    // 混淆参数（仅在存在时写入）。
    for (k, v) in awg_fields(cfg) {
        endpoint.insert(k.into(), v);
    }

    let dns = if cfg.dns.is_empty() {
        vec!["1.1.1.1".to_string()]
    } else {
        cfg.dns.clone()
    };

    let inbounds = build_inbounds(mode, mtu, proxy_port);

    let config = json!({
        "log": { "level": "warn", "timestamp": true },
        "dns": {
            "servers": [
                { "tag": "remote", "address": dns_first(&dns) },
                { "tag": "local", "address": "223.5.5.5", "detour": "direct" }
            ],
            "strategy": "prefer_ipv4"
        },
        "inbounds": inbounds,
        "endpoints": [Value::Object(endpoint)],
        "outbounds": [
            { "type": "direct", "tag": "direct" }
        ],
        "route": {
            "auto_detect_interface": true,
            "final": WG_TAG,
            "rules": [
                { "action": "sniff" },
                { "protocol": "dns", "action": "hijack-dns" }
            ]
        },
        "experimental": {
            "clash_api": {
                "external_controller": format!("127.0.0.1:{clash_port}")
            }
        }
    });
    Ok(config)
}

/// 集中映射混淆字段（小写键，整数值）。便于按内核分支调整命名。
fn awg_fields(cfg: &AwgConfig) -> Vec<(&'static str, Value)> {
    let mut out = Vec::new();
    let mut push = |key: &'static str, raw: &Option<String>| {
        if let Some(v) = raw {
            if let Ok(n) = v.parse::<i64>() {
                out.push((key, json!(n)));
            }
        }
    };
    push("jc", &cfg.jc);
    push("jmin", &cfg.jmin);
    push("jmax", &cfg.jmax);
    push("s1", &cfg.s1);
    push("s2", &cfg.s2);
    push("h1", &cfg.h1);
    push("h2", &cfg.h2);
    push("h3", &cfg.h3);
    push("h4", &cfg.h4);
    out
}

fn dns_first(dns: &[String]) -> String {
    dns.first().cloned().unwrap_or_else(|| "1.1.1.1".into())
}

/// 按模式构造入站：TUN 全局接管 或 本地混合代理。
fn build_inbounds(mode: NetMode, mtu: u32, proxy_port: u16) -> Value {
    match mode {
        NetMode::Tun => json!([{
            "type": "tun",
            "tag": "tun-in",
            "interface_name": TUN_IFACE,
            "address": ["172.19.0.1/30"],
            "mtu": mtu,
            "auto_route": true,
            "strict_route": true,
            "stack": "system"
        }]),
        NetMode::SystemProxy => json!([{
            "type": "mixed",
            "tag": "mixed-in",
            "listen": "127.0.0.1",
            "listen_port": proxy_port
        }]),
    }
}
