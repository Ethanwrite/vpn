//! 后端控制面 HTTP 客户端（reqwest）。
//! 多域名按序回退；严禁硬编码节点信息，节点全部通过 API 动态获取。

use crate::error::{AppError, AppResult};
use crate::models::{AuthResponse, Entitlement, User, VpnNodeConfig, VpnNodeSummary};
use reqwest::{Client, Method};
use serde_json::json;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Duration;

const VERSION_CODE: &str = "7";
const VERSION_NAME: &str = "1.0.23";

/// 供崩溃日志等处引用当前版本名。
pub fn version_name() -> &'static str {
    VERSION_NAME
}

/// 生产 API 基址（含 /api 前缀，后端中间件会剥离）。按序回退：
/// 主域名优先，xingsuico.com 为等价备用镜像（同一后端）。大陆部分 Wi-Fi 对主域名
/// 存在 DNS 污染/SNI 阻断，此时自动切换到镜像，保证登录/授权/连接仍可用。
pub const BASE_URLS: &[&str] = &[
    "https://xingsui.org/api",
    "https://xingsuico.com/api",
];

pub struct ApiClient {
    http: Client,
    /// 上次网络可达的基址下标。请求从它开始，命中后记住，避免每次都先在被封的
    /// 主域名上耗满连接超时（对标 Android 客户端的 activeBaseUrl 粘滞行为）。
    preferred_base: AtomicUsize,
}

impl ApiClient {
    pub fn new() -> Self {
        // 构建失败（TLS 后端初始化异常，极罕见）回退默认客户端，绝不因此在启动阶段 panic。
        let http = Client::builder()
            .connect_timeout(Duration::from_secs(6))
            .timeout(Duration::from_secs(12))
            .user_agent("XingsuiWindows/1.0")
            .build()
            .unwrap_or_else(|_| Client::new());
        Self {
            http,
            preferred_base: AtomicUsize::new(0),
        }
    }

    async fn request(
        &self,
        method: Method,
        path: &str,
        token: Option<&str>,
        body: Option<serde_json::Value>,
    ) -> AppResult<String> {
        let mut last_err: Option<AppError> = None;
        // 从上次可达的基址开始，环形遍历所有基址（粘滞回退）。
        let start = self.preferred_base.load(Ordering::Relaxed) % BASE_URLS.len();
        for offset in 0..BASE_URLS.len() {
            let idx = (start + offset) % BASE_URLS.len();
            let base = BASE_URLS[idx];
            let url = format!("{base}{path}");
            let mut req = self
                .http
                .request(method.clone(), &url)
                .header("Accept", "application/json")
                .header("X-Xingsui-Platform", "windows")
                .header("X-Xingsui-Version-Code", VERSION_CODE)
                .header("X-Xingsui-Version-Name", VERSION_NAME);
            if let Some(t) = token {
                req = req.header("Authorization", format!("Bearer {t}"));
            }
            if let Some(ref b) = body {
                req = req.json(b);
            }
            match req.send().await {
                Ok(resp) => {
                    // 收到 HTTP 响应即说明该基址网络可达，记为优先，下次从它开始。
                    self.preferred_base.store(idx, Ordering::Relaxed);
                    let status = resp.status();
                    let text = resp.text().await.unwrap_or_default();
                    if status.is_success() {
                        return Ok(text);
                    }
                    if status.as_u16() == 401 {
                        return Err(AppError::Unauthorized);
                    }
                    // 4xx 客户端错误无需切换域名，直接返回。
                    if status.is_client_error() {
                        let detail = extract_detail(&text);
                        return if token.is_some() {
                            // 已登录时，把授权失败原因码转成友好文案（免费流量用完 / VIP 相关），
                            // 其余仍回退到通用的“账户状态同步失败”提示。
                            Err(AppError::other(friendly_reason_message(&detail)))
                        } else {
                            Err(AppError::other(detail))
                        };
                    }
                    last_err = Some(AppError::Api {
                        status: status.as_u16(),
                        message: extract_detail(&text),
                    });
                }
                Err(e) => last_err = Some(AppError::Network(e.to_string())),
            }
        }
        if token.is_some() {
            Err(AppError::connection_sync())
        } else {
            Err(last_err.unwrap_or_else(|| AppError::Network("所有线路均不可达".into())))
        }
    }

    pub async fn login(&self, email: &str, password: &str) -> AppResult<AuthResponse> {
        let body = json!({ "email": email, "password": password });
        let text = self
            .request(Method::POST, "/auth/email/login", None, Some(body))
            .await?;
        Ok(serde_json::from_str(&text)?)
    }

    pub async fn register(
        &self,
        email: &str,
        password: &str,
        invite_code: Option<&str>,
    ) -> AppResult<AuthResponse> {
        let mut body = json!({ "email": email, "password": password });
        if let Some(code) = invite_code.filter(|c| !c.is_empty()) {
            body["invite_code"] = json!(code);
        }
        let text = self
            .request(Method::POST, "/auth/email/register", None, Some(body))
            .await?;
        Ok(serde_json::from_str(&text)?)
    }

    pub async fn get_me(&self, token: &str) -> AppResult<User> {
        let text = self.request(Method::GET, "/me", Some(token), None).await?;
        Ok(serde_json::from_str(&text)?)
    }

    pub async fn list_nodes(&self, token: &str) -> AppResult<Vec<VpnNodeSummary>> {
        let text = self
            .request(Method::GET, "/vpn/nodes", Some(token), None)
            .await?;
        let mut nodes: Vec<VpnNodeSummary> = serde_json::from_str(&text)?;
        nodes.retain(|node| node.protocol == "vless");
        Ok(nodes)
    }

    pub async fn get_node_config(&self, token: &str, node_id: &str) -> AppResult<VpnNodeConfig> {
        let path = format!("/vpn/nodes/{node_id}/config");
        let text = self.request(Method::GET, &path, Some(token), None).await?;
        Ok(serde_json::from_str(&text)?)
    }

    pub async fn report_usage(
        &self,
        token: &str,
        lease_id: &str,
        tunnel_name: Option<&str>,
        rx_bytes_delta: u64,
        tx_bytes_delta: u64,
    ) -> AppResult<Entitlement> {
        let body = json!({
            "lease_id": lease_id,
            "tunnel_name": tunnel_name,
            "rx_bytes_delta": rx_bytes_delta,
            "tx_bytes_delta": tx_bytes_delta,
        });
        let text = self
            .request(Method::POST, "/usage/report", Some(token), Some(body))
            .await?;
        Ok(serde_json::from_str(&text)?)
    }
}

/// 把后端授权失败原因码映射成用户可读文案；未知原因回退到通用同步失败提示。
fn friendly_reason_message(detail: &str) -> String {
    match detail.trim() {
        "free_traffic_exhausted" => "免费体验流量已用完，请前往官网开通会员后继续使用".to_string(),
        "vip_required" => "该线路为会员专属，请前往官网开通会员后使用".to_string(),
        "vip_expired" => "会员已到期，请前往官网续费后继续使用".to_string(),
        _ => crate::error::CONNECTION_SYNC_ERROR.to_string(),
    }
}

/// 从后端 {"detail": "..."} 错误体抽取人类可读信息。
fn extract_detail(text: &str) -> String {
    serde_json::from_str::<serde_json::Value>(text)
        .ok()
        .and_then(|v| v.get("detail").and_then(|d| d.as_str()).map(String::from))
        .unwrap_or_else(|| {
            if text.is_empty() {
                "请求失败".to_string()
            } else {
                text.chars().take(200).collect()
            }
        })
}

#[cfg(test)]
mod tests {
    use super::friendly_reason_message;
    use crate::error::CONNECTION_SYNC_ERROR;

    #[test]
    fn maps_entitlement_reasons_to_friendly_text() {
        assert!(friendly_reason_message("free_traffic_exhausted").contains("官网"));
        assert!(friendly_reason_message("vip_expired").contains("续费"));
        assert!(friendly_reason_message("vip_required").contains("会员"));
        // 未知原因回退到通用同步失败提示
        assert_eq!(
            friendly_reason_message("something_else"),
            CONNECTION_SYNC_ERROR
        );
    }
}
