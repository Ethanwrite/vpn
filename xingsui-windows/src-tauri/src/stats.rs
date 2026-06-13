//! 通过 sing-box clash API 的 /traffic 流式接口轮询实时速率。
//! 每秒一条 {"up":bytes,"down":bytes}；累加得到累计流量并推送前端。

use crate::models::StatsPayload;
use crate::state::AppState;
use futures_util::StreamExt;
use tauri::{AppHandle, Emitter, Manager};

/// 启动流量轮询任务，generation 用于在新连接到来时自动退出旧任务。
pub fn spawn_traffic_poller(app: AppHandle, clash_port: u16, generation: u64) {
    tauri::async_runtime::spawn(async move {
        let url = format!("http://127.0.0.1:{clash_port}/traffic");
        let client = reqwest::Client::new();
        let mut up_total: u64 = 0;
        let mut down_total: u64 = 0;

        // clash API 启动需短暂等待。
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
            }
            tokio::time::sleep(std::time::Duration::from_millis(800)).await;
        }
    });
}

/// 当前 generation 与运行时不一致 => 旧任务应退出。
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
