use crate::error::AppResult;
use crate::models::{NetMode, VlessConfig};
use serde_json::{json, Map, Value};

const OUT_TAG: &str = "proxy-out";
const TUN_IFACE: &str = "xingsui-tun";
const PRIVATE_CIDRS: &[&str] = &[
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "224.0.0.0/4",
];
const DIRECT_DOMAIN_SUFFIXES: &[&str] = &["cn", "local", "localhost", "lan"];

pub fn build_vless(
    cfg: &VlessConfig,
    mode: NetMode,
    proxy_port: u16,
    clash_port: u16,
    clash_secret: &str,
) -> AppResult<Value> {
    let mut outbound = json!({
        "type": "vless",
        "tag": OUT_TAG,
        "server": cfg.server,
        "server_port": cfg.server_port,
        "uuid": cfg.uuid,
        "packet_encoding": "xudp",
        "tls": {
            "enabled": true,
            "server_name": cfg.server_name,
            "utls": {
                "enabled": true,
                "fingerprint": cfg.utls_fingerprint
            },
            "reality": {
                "enabled": true,
                "public_key": cfg.public_key,
                "short_id": cfg.short_id
            }
        }
    });
    if !cfg.flow.trim().is_empty() {
        outbound["flow"] = json!(cfg.flow.trim());
    }

    Ok(base_config(
        build_inbounds(mode, 1280, proxy_port, Some(&cfg.server)),
        json!([outbound]),
        json!([{ "type": "direct", "tag": "direct" }]),
        None,
        "1.1.1.1",
        mode,
        clash_port,
        clash_secret,
        mode.is_tun(),
        Some(cfg.server.clone()),
    ))
}

fn base_config(
    inbounds: Value,
    primary_outbounds: Value,
    fallback_outbounds: Value,
    endpoints: Option<Value>,
    dns_server: impl Into<String>,
    mode: NetMode,
    clash_port: u16,
    clash_secret: &str,
    block_udp_443: bool,
    bypass_host: Option<String>,
) -> Value {
    let mut outbounds = Vec::new();
    if let Value::Array(items) = primary_outbounds {
        outbounds.extend(items);
    }
    if let Value::Array(items) = fallback_outbounds {
        outbounds.extend(items);
    }

    let mut root = Map::new();
    root.insert("log".into(), json!({ "level": "warn", "timestamp": true }));
    root.insert("dns".into(), build_dns(dns_server.into()));
    root.insert("inbounds".into(), inbounds);
    if let Some(endpoints) = endpoints {
        root.insert("endpoints".into(), endpoints);
    }
    root.insert("outbounds".into(), Value::Array(outbounds));

    let mut rules = vec![json!({ "action": "sniff" })];
    rules.push(json!({ "protocol": "dns", "action": "hijack-dns" }));
    if let Some(host) = bypass_host.filter(|host| is_ipv4(host)) {
        rules.push(json!({
            "ip_cidr": [format!("{host}/32")],
            "action": "route",
            "outbound": "direct"
        }));
    }
    rules.push(json!({
        "ip_cidr": PRIVATE_CIDRS,
        "action": "route",
        "outbound": "direct"
    }));
    if mode == NetMode::Rule {
        rules.push(json!({
            "domain_suffix": DIRECT_DOMAIN_SUFFIXES,
            "action": "route",
            "outbound": "direct"
        }));
    }
    if block_udp_443 {
        rules.push(json!({ "network": "udp", "port": 443, "action": "reject" }));
    }

    root.insert(
        "route".into(),
        json!({
            "auto_detect_interface": true,
            "default_domain_resolver": {
                "server": if mode == NetMode::Global { "remote" } else { "local" },
                "strategy": "prefer_ipv4"
            },
            "final": OUT_TAG,
            "rules": rules
        }),
    );
    root.insert(
        "experimental".into(),
        json!({
            "clash_api": {
                "external_controller": format!("127.0.0.1:{clash_port}"),
                "secret": clash_secret
            }
        }),
    );
    Value::Object(root)
}

fn build_dns(remote_server: String) -> Value {
    json!({
        "servers": [
            {
                "type": "tcp",
                "tag": "remote",
                "server": remote_server,
                "detour": OUT_TAG
            },
            {
                "type": "udp",
                "tag": "local",
                "server": "223.5.5.5"
            }
        ],
        "strategy": "prefer_ipv4"
    })
}

fn build_inbounds(mode: NetMode, mtu: u32, proxy_port: u16, bypass_host: Option<&str>) -> Value {
    match mode {
        NetMode::Global | NetMode::Rule => {
            let mut route_exclude_address = PRIVATE_CIDRS
                .iter()
                .map(|cidr| json!(cidr))
                .collect::<Vec<_>>();
            if let Some(host) = bypass_host.filter(|host| is_ipv4(host)) {
                route_exclude_address.push(json!(format!("{host}/32")));
            }
            json!([{
                "type": "tun",
                "tag": "tun-in",
                "interface_name": TUN_IFACE,
                "address": ["172.19.0.1/30"],
                "mtu": mtu,
                "auto_route": true,
                "strict_route": false,
                "route_address": ["0.0.0.0/1", "128.0.0.0/1"],
                "route_exclude_address": route_exclude_address,
                "stack": "gvisor"
            }])
        }
        NetMode::SystemProxy => json!([{
            "type": "mixed",
            "tag": "mixed-in",
            "listen": "127.0.0.1",
            "listen_port": proxy_port
        }]),
    }
}

fn is_ipv4(host: &str) -> bool {
    host.parse::<std::net::Ipv4Addr>().is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn windows_config_is_vless_reality_only_and_secures_clash_api() {
        let config = VlessConfig {
            server: "edge.example.com".into(),
            server_port: 443,
            uuid: "123e4567-e89b-12d3-a456-426614174000".into(),
            flow: "xtls-rprx-vision".into(),
            public_key: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA".into(),
            short_id: "0123456789abcdef".into(),
            server_name: "www.example.com".into(),
            utls_fingerprint: "chrome".into(),
        };
        let value = build_vless(&config, NetMode::SystemProxy, 7897, 9191, "local-secret")
            .expect("build VLESS config");
        assert_eq!(value["outbounds"][0]["type"], "vless");
        assert_eq!(value["outbounds"][0]["tls"]["reality"]["enabled"], true);
        assert_eq!(value["experimental"]["clash_api"]["secret"], "local-secret");
        let encoded = serde_json::to_string(&value).unwrap();
        assert!(!encoded.contains("wireguard"));
    }

    #[test]
    fn official_sing_box_accepts_generated_configs_when_checker_is_available() {
        let Ok(checker) = std::env::var("SING_BOX_CHECK_BIN") else {
            return;
        };
        let config = VlessConfig {
            server: "192.0.2.1".into(),
            server_port: 443,
            uuid: "123e4567-e89b-12d3-a456-426614174000".into(),
            flow: "xtls-rprx-vision".into(),
            public_key: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA".into(),
            short_id: "0123456789abcdef".into(),
            server_name: "www.example.com".into(),
            utls_fingerprint: "chrome".into(),
        };
        for mode in [NetMode::SystemProxy, NetMode::Global, NetMode::Rule] {
            let value = build_vless(&config, mode, 7897, 9191, "local-secret").unwrap();
            let path = std::env::temp_dir().join(format!(
                "xingsui-sing-box-check-{:032x}.json",
                rand::random::<u128>()
            ));
            std::fs::write(&path, serde_json::to_vec(&value).unwrap()).unwrap();
            let output = std::process::Command::new(&checker)
                .args(["check", "-c"])
                .arg(&path)
                .output()
                .expect("run official sing-box checker");
            let _ = std::fs::remove_file(&path);
            assert!(
                output.status.success(),
                "sing-box rejected {mode:?}: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }
    }
}
