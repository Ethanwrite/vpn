use crate::awg::AwgConfig;
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

pub fn build(cfg: &AwgConfig, mode: NetMode, proxy_port: u16, clash_port: u16) -> AppResult<Value> {
    let (host, port) = cfg.endpoint_host_port()?;
    let mtu = effective_mtu(cfg);

    let mut endpoint = Map::new();
    endpoint.insert("type".into(), json!("wireguard"));
    endpoint.insert("tag".into(), json!(OUT_TAG));
    endpoint.insert("system".into(), json!(false));
    endpoint.insert("inet4_bind_address".into(), json!("0.0.0.0"));
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
    for (k, v) in awg_fields(cfg) {
        endpoint.insert(k.into(), v);
    }

    let dns = if cfg.dns.is_empty() {
        vec!["1.1.1.1".to_string()]
    } else {
        cfg.dns.clone()
    };

    Ok(base_config(
        build_inbounds(mode, mtu, proxy_port, Some(&host)),
        json!([]),
        json!([{"type": "direct", "tag": "direct"}]),
        Some(json!([Value::Object(endpoint)])),
        dns_first(&dns),
        mode,
        clash_port,
        mode.is_tun(),
        Some(host),
    ))
}

pub fn build_vless(
    cfg: &VlessConfig,
    mode: NetMode,
    proxy_port: u16,
    clash_port: u16,
) -> AppResult<Value> {
    let server_port = cfg.server_port.trim().parse::<u16>().unwrap_or(8443);
    let mut outbound = json!({
        "type": "vless",
        "tag": OUT_TAG,
        "server": cfg.server,
        "server_port": server_port,
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
                "external_controller": format!("127.0.0.1:{clash_port}")
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

fn awg_fields(cfg: &AwgConfig) -> Vec<(&'static str, Value)> {
    let mut out = Vec::new();
    push_int("jc", &cfg.jc, &mut out);
    push_int("jmin", &cfg.jmin, &mut out);
    push_int("jmax", &cfg.jmax, &mut out);
    push_int("s1", &cfg.s1, &mut out);
    push_int("s2", &cfg.s2, &mut out);
    push_int("s3", &cfg.s3, &mut out);
    push_int("s4", &cfg.s4, &mut out);
    push_header("h1", &cfg.h1, &mut out);
    push_header("h2", &cfg.h2, &mut out);
    push_header("h3", &cfg.h3, &mut out);
    push_header("h4", &cfg.h4, &mut out);
    push_string("i1", &cfg.i1, &mut out);
    push_string("i2", &cfg.i2, &mut out);
    push_string("i3", &cfg.i3, &mut out);
    push_string("i4", &cfg.i4, &mut out);
    push_string("i5", &cfg.i5, &mut out);
    out
}

fn push_int(key: &'static str, raw: &Option<String>, out: &mut Vec<(&'static str, Value)>) {
    if let Some(v) = raw {
        if let Ok(n) = v.trim().parse::<i64>() {
            out.push((key, json!(n)));
        }
    }
}

fn push_header(key: &'static str, raw: &Option<String>, out: &mut Vec<(&'static str, Value)>) {
    let Some(raw) = raw else { return };
    let v = raw.trim();
    if v.is_empty() {
        return;
    }
    if let Ok(n) = v.parse::<i64>() {
        out.push((key, json!(n)));
    } else if is_header_range(v) {
        out.push((key, json!(v)));
    }
}

fn is_header_range(v: &str) -> bool {
    match v.split_once('-') {
        Some((lo, hi)) => lo.trim().parse::<i64>().is_ok() && hi.trim().parse::<i64>().is_ok(),
        None => false,
    }
}

fn push_string(key: &'static str, raw: &Option<String>, out: &mut Vec<(&'static str, Value)>) {
    if let Some(v) = raw {
        let v = v.trim();
        if !v.is_empty() {
            out.push((key, json!(v)));
        }
    }
}

fn has_awg_obfuscation(cfg: &AwgConfig) -> bool {
    cfg.jc.is_some()
        || cfg.jmin.is_some()
        || cfg.jmax.is_some()
        || cfg.s1.is_some()
        || cfg.s2.is_some()
        || cfg.s3.is_some()
        || cfg.s4.is_some()
        || cfg.h1.is_some()
        || cfg.h2.is_some()
        || cfg.h3.is_some()
        || cfg.h4.is_some()
        || cfg.i1.is_some()
        || cfg.i2.is_some()
        || cfg.i3.is_some()
        || cfg.i4.is_some()
        || cfg.i5.is_some()
}

fn effective_mtu(cfg: &AwgConfig) -> u32 {
    let requested = cfg.mtu.unwrap_or(1280);
    if has_awg_obfuscation(cfg) {
        requested.min(1280)
    } else {
        requested
    }
}

fn dns_first(dns: &[String]) -> String {
    dns.first().cloned().unwrap_or_else(|| "1.1.1.1".into())
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
