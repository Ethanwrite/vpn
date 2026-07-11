use crate::core;
use crate::models::{Entitlement, StatsPayload};
use crate::state::AppState;
use chrono::{DateTime, Utc};
use futures_util::StreamExt;
use parking_lot::Mutex;
use std::sync::Arc;
use std::time::Duration;
use tauri::{AppHandle, Emitter, Manager};

const AUTHORIZATION_INTERVAL_SECS: u64 = 10;

#[derive(Default)]
struct PendingUsage {
    up: u64,
    down: u64,
}

pub fn spawn_traffic_poller(
    app: AppHandle,
    clash_port: u16,
    generation: u64,
    clash_secret: String,
    tunnel_name: String,
    lease_id: String,
    lease_expires_at: DateTime<Utc>,
) {
    let pending = Arc::new(Mutex::new(PendingUsage::default()));
    spawn_local_traffic_reader(
        app.clone(),
        clash_port,
        generation,
        clash_secret,
        pending.clone(),
    );
    spawn_authorization_loop(
        app,
        generation,
        tunnel_name,
        lease_id,
        lease_expires_at,
        pending,
    );
}

fn spawn_local_traffic_reader(
    app: AppHandle,
    clash_port: u16,
    generation: u64,
    clash_secret: String,
    pending: Arc<Mutex<PendingUsage>>,
) {
    tauri::async_runtime::spawn(async move {
        let url = format!("http://127.0.0.1:{clash_port}/traffic");
        let client = match reqwest::Client::builder()
            .timeout(Duration::from_secs(3))
            .build()
        {
            Ok(client) => client,
            Err(_) => return,
        };
        let mut up_total = 0_u64;
        let mut down_total = 0_u64;

        loop {
            if generation_stale(&app, generation) {
                return;
            }
            let response = match client.get(&url).bearer_auth(&clash_secret).send().await {
                Ok(response) if response.status().is_success() => response,
                _ => {
                    tokio::time::sleep(Duration::from_millis(800)).await;
                    continue;
                }
            };
            let mut stream = response.bytes_stream();
            let mut buffer = Vec::new();
            while let Some(chunk) = stream.next().await {
                if generation_stale(&app, generation) {
                    return;
                }
                let Ok(bytes) = chunk else { break };
                buffer.extend_from_slice(&bytes);
                while let Some(position) = buffer.iter().position(|byte| *byte == b'\n') {
                    let line: Vec<u8> = buffer.drain(..=position).collect();
                    if let Some((up, down)) = parse_traffic(&line) {
                        up_total = up_total.saturating_add(up);
                        down_total = down_total.saturating_add(down);
                        {
                            let mut usage = pending.lock();
                            usage.up = usage.up.saturating_add(up);
                            usage.down = usage.down.saturating_add(down);
                        }
                        let _ = app.emit(
                            "stats",
                            StatsPayload {
                                up_bps: up,
                                down_bps: down,
                                up_total,
                                down_total,
                            },
                        );
                    }
                }
            }
            tokio::time::sleep(Duration::from_millis(300)).await;
        }
    });
}

fn spawn_authorization_loop(
    app: AppHandle,
    generation: u64,
    tunnel_name: String,
    lease_id: String,
    mut lease_expires_at: DateTime<Utc>,
    pending: Arc<Mutex<PendingUsage>>,
) {
    tauri::async_runtime::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_secs(AUTHORIZATION_INTERVAL_SECS));
        interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
        loop {
            interval.tick().await;
            if generation_stale(&app, generation) {
                return;
            }
            if Utc::now() >= lease_expires_at {
                core::fail_connection(&app, generation);
                return;
            }
            let token = {
                let state = app.state::<AppState>();
                let token = state.token.read().clone();
                token
            };
            let Some(token) = token else {
                core::fail_connection(&app, generation);
                return;
            };
            let (up_delta, down_delta) = {
                let mut usage = pending.lock();
                let snapshot = (usage.up, usage.down);
                usage.up = 0;
                usage.down = 0;
                snapshot
            };
            let result = {
                let state = app.state::<AppState>();
                state
                    .api
                    .report_usage(&token, &lease_id, Some(&tunnel_name), down_delta, up_delta)
                    .await
            };
            if generation_stale(&app, generation) {
                return;
            }
            let now = Utc::now();
            match result {
                Ok(entitlement) if now < lease_expires_at => {
                    let Some(renewed_expiry) = validated_renewal_expiry(&entitlement, now) else {
                        core::fail_connection(&app, generation);
                        return;
                    };
                    lease_expires_at = renewed_expiry;
                }
                _ => {
                    core::fail_connection(&app, generation);
                    return;
                }
            }
        }
    });
}

fn validated_renewal_expiry(
    entitlement: &Entitlement,
    now: DateTime<Utc>,
) -> Option<DateTime<Utc>> {
    if !entitlement.allowed || entitlement.vip_status != "active" {
        return None;
    }
    let vip_expiry = entitlement
        .vip_expired_at
        .as_deref()
        .and_then(|value| DateTime::parse_from_rfc3339(value).ok())
        .map(|expires_at| expires_at.with_timezone(&Utc))?;
    let lease_expiry = entitlement
        .lease_expires_at
        .as_deref()
        .and_then(|value| DateTime::parse_from_rfc3339(value).ok())
        .map(|expires_at| expires_at.with_timezone(&Utc))?;
    if vip_expiry <= now
        || lease_expiry <= now
        || lease_expiry > now + chrono::Duration::minutes(15)
        || lease_expiry > vip_expiry
    {
        return None;
    }
    Some(lease_expiry)
}

fn generation_stale(app: &AppHandle, generation: u64) -> bool {
    let state = app.state::<AppState>();
    let stale = state.conn.lock().generation != generation;
    stale
}

fn parse_traffic(line: &[u8]) -> Option<(u64, u64)> {
    let value: serde_json::Value = serde_json::from_slice(line).ok()?;
    let up = value.get("up")?.as_u64()?;
    let down = value.get("down")?.as_u64()?;
    Some((up, down))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn entitlement(now: DateTime<Utc>) -> Entitlement {
        Entitlement {
            allowed: true,
            reason: "vip_active".into(),
            vip_status: "active".into(),
            vip_expired_at: Some((now + chrono::Duration::minutes(5)).to_rfc3339()),
            free_traffic_quota_bytes: 0,
            free_traffic_used_bytes: 0,
            free_traffic_remaining_bytes: 0,
            lease_expires_at: Some((now + chrono::Duration::minutes(5)).to_rfc3339()),
        }
    }

    #[test]
    fn authorization_requires_allowed_live_vip() {
        let now = Utc::now();
        assert!(validated_renewal_expiry(&entitlement(now), now).is_some());

        let mut denied = entitlement(now);
        denied.allowed = false;
        assert!(validated_renewal_expiry(&denied, now).is_none());

        let mut expired = entitlement(now);
        expired.vip_expired_at = Some((now - chrono::Duration::seconds(1)).to_rfc3339());
        assert!(validated_renewal_expiry(&expired, now).is_none());

        let mut missing_lease = entitlement(now);
        missing_lease.lease_expires_at = None;
        assert!(validated_renewal_expiry(&missing_lease, now).is_none());
    }

    #[test]
    fn parses_clash_traffic_line() {
        assert_eq!(parse_traffic(b"{\"up\":12,\"down\":34}\n"), Some((12, 34)));
        assert_eq!(parse_traffic(b"not-json"), None);
    }
}
