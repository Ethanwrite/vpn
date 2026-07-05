use crate::core;
use crate::models::{Entitlement, StatsPayload};
use crate::state::AppState;
use futures_util::StreamExt;
use tauri::{AppHandle, Emitter, Manager};

const USAGE_REPORT_INTERVAL_SECS: u64 = 3;
const USAGE_REPORT_MIN_BYTES: u64 = 128 * 1024;

pub fn spawn_traffic_poller(app: AppHandle, clash_port: u16, generation: u64) {
    tauri::async_runtime::spawn(async move {
        let url = format!("http://127.0.0.1:{clash_port}/traffic");
        let client = reqwest::Client::new();
        let mut up_total: u64 = 0;
        let mut down_total: u64 = 0;
        let mut pending_up: u64 = 0;
        let mut pending_down: u64 = 0;
        let mut last_report = std::time::Instant::now();

        for _ in 0..20 {
            if generation_stale(&app, generation) {
                return;
            }
            if let Ok(resp) = client.get(&url).send().await {
                let mut stream = resp.bytes_stream();
                let mut buf: Vec<u8> = Vec::new();
                while let Some(chunk) = stream.next().await {
                    if generation_stale(&app, generation) {
                        return;
                    }
                    let Ok(bytes) = chunk else { break };
                    buf.extend_from_slice(&bytes);
                    while let Some(pos) = buf.iter().position(|b| *b == b'\n') {
                        let line: Vec<u8> = buf.drain(..=pos).collect();
                        if let Some((up, down)) = parse_traffic(&line) {
                            up_total = up_total.saturating_add(up);
                            down_total = down_total.saturating_add(down);
                            pending_up = pending_up.saturating_add(up);
                            pending_down = pending_down.saturating_add(down);
                            let _ = app.emit(
                                "stats",
                                StatsPayload {
                                    up_bps: up,
                                    down_bps: down,
                                    up_total,
                                    down_total,
                                },
                            );
                            if should_report_usage(pending_up, pending_down, last_report)
                                && report_usage_delta(&app, generation, pending_up, pending_down)
                                    .await
                            {
                                pending_up = 0;
                                pending_down = 0;
                                last_report = std::time::Instant::now();
                            }
                        }
                    }
                }
            }
            tokio::time::sleep(std::time::Duration::from_millis(800)).await;
        }
    });
}

fn should_report_usage(pending_up: u64, pending_down: u64, last_report: std::time::Instant) -> bool {
    let pending_total = pending_up.saturating_add(pending_down);
    pending_total >= USAGE_REPORT_MIN_BYTES
        || (pending_total > 0 && last_report.elapsed().as_secs() >= USAGE_REPORT_INTERVAL_SECS)
}

async fn report_usage_delta(
    app: &AppHandle,
    generation: u64,
    up_delta: u64,
    down_delta: u64,
) -> bool {
    if generation_stale(app, generation) || up_delta.saturating_add(down_delta) == 0 {
        return false;
    }
    let token = {
        let state = app.state::<AppState>();
        let token = state.token.read().clone();
        token
    };
    let Some(token) = token else {
        return false;
    };
    let result = {
        let state = app.state::<AppState>();
        state
            .api
            .report_usage(&token, Some("xingsui"), down_delta, up_delta)
            .await
    };
    match result {
        Ok(entitlement) => {
            if !entitlement.allowed && !generation_stale(app, generation) {
                stop_for_entitlement(app, generation, &entitlement);
            }
            true
        }
        Err(_) => false,
    }
}

fn stop_for_entitlement(app: &AppHandle, generation: u64, entitlement: &Entitlement) {
    if generation_stale(app, generation) {
        return;
    }
    let message = match entitlement.reason.as_str() {
        "free_traffic_exhausted" => "30MB 免费体验流量已用完，请开通 VIP 后继续使用。",
        "vip_expired" => "VIP 已过期，请续费后继续使用。",
        _ => "当前账号暂无可用流量，请开通 VIP 后继续使用。",
    };
    let _ = core::stop(app);
    core::emit_status(app, Some(message.into()));
}

fn generation_stale(app: &AppHandle, generation: u64) -> bool {
    let state = app.state::<AppState>();
    let guard = state.conn.lock();
    guard.generation != generation
}

fn parse_traffic(line: &[u8]) -> Option<(u64, u64)> {
    let value: serde_json::Value = serde_json::from_slice(line).ok()?;
    let up = value.get("up")?.as_u64()?;
    let down = value.get("down")?.as_u64()?;
    Some((up, down))
}
