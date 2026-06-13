//! 后端控制面 HTTP 客户端（reqwest）。
//! 多域名按序回退；严禁硬编码节点信息，节点全部通过 API 动态获取。

use crate::error::{AppError, AppResult};
use crate::models::{AuthResponse, User, VpnNodeConfig, VpnNodeSummary};
use reqwest::{Client, Method};
use serde_json::json;
use std::time::Duration;

const VERSION_CODE: &str = "1";
const VERSION_NAME: &str = "1.0.0";

/// 生产 API 基址（含 /api 前缀，后端中间件会剥离）。按序回退。
pub const BASE_URLS: &[&str] = &[
    "https://api.xingsuico.com/api",
    "https://xingsui.org/api",
    "https://api.xingsui.org/api",
];

pub struct ApiClient {
    http: Client,
}

impl ApiClient {
    pub fn new() -> Self {
        let http = Client::builder()
            .connect_timeout(Duration::from_secs(6))
            .timeout(Duration::from_secs(12))
            .user_agent("XingsuiWindows/1.0")
            .build()
            .expect("构建 HTTP 客户端失败");
        Self { http }
    }

    async fn request(
        &self,
        method: Method,
        path: &str,
        token: Option<&str>,
        body: Option<serde_json::Value>,
    ) -> AppResult<String> {
        let mut last_err: Option<AppError> = None;
        for base in BASE_URLS {
            let url = format!("{base}{path}");
            let mut req = self
                .http
                .request(method.clone(), &url)
                .header("Accept", "application/json")
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
                        return Err(AppError::Api {
                            status: status.as_u16(),
                            message: extract_detail(&text),
                        });
                    }
                    last_err = Some(AppError::Api {
                        status: status.as_u16(),
                        message: extract_detail(&text),
                    });
                }
                Err(e) => last_err = Some(AppError::Network(e.to_string())),
            }
        }
        Err(last_err.unwrap_or_else(|| AppError::Network("所有线路均不可达".into())))
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
        Ok(serde_json::from_str(&text)?)
    }

    pub async fn get_node_config(&self, token: &str, node_id: &str) -> AppResult<VpnNodeConfig> {
        let path = format!("/vpn/nodes/{node_id}/config");
        let text = self.request(Method::GET, &path, Some(token), None).await?;
        Ok(serde_json::from_str(&text)?)
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
