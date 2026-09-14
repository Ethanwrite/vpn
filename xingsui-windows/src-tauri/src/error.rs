//! 统一错误类型：所有 Tauri command 返回 Result<T, AppError>，
//! 序列化为字符串供前端 Toast 友好提示。

use serde::Serialize;

pub const CONNECTION_SYNC_ERROR: &str = "账户状态同步失败\n暂时无法连接，请检查网络后重试";

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("网络请求失败：{0}")]
    Network(String),

    #[error("接口返回错误({status})：{message}")]
    Api { status: u16, message: String },

    #[error("{0}")]
    Entitlement(String),

    #[error("登录已过期，请重新登录后连接")]
    Unauthorized,

    #[error("内核启动失败：{0}")]
    Core(String),

    #[error("系统配置失败：{0}")]
    System(String),

    #[error("配置解析失败：{0}")]
    Config(String),

    #[error("{0}")]
    Other(String),
}

impl AppError {
    pub fn other(msg: impl Into<String>) -> Self {
        AppError::Other(msg.into())
    }
    pub fn core(msg: impl Into<String>) -> Self {
        AppError::Core(msg.into())
    }
    pub fn system(msg: impl Into<String>) -> Self {
        AppError::System(msg.into())
    }
    pub fn config(msg: impl Into<String>) -> Self {
        AppError::Config(msg.into())
    }
    /// Only approved account reasons can escape the generic connection failure message.
    pub fn entitlement(reason: &str) -> Self {
        let message = match reason.trim() {
            "free_traffic_exhausted" => "免费体验流量已用完，请前往官网开通会员后继续使用",
            "vip_required" => "该线路为会员专属，请前往官网开通会员后使用",
            "vip_expired" => "会员已到期，请前往官网续费后继续使用",
            _ => return Self::connection_sync(),
        };
        Self::Entitlement(message.into())
    }

    pub fn for_connection(self) -> Self {
        match self {
            Self::Entitlement(_) | Self::Unauthorized => self,
            _ => Self::connection_sync(),
        }
    }

    /// No response bodies, tokens, URLs, lease IDs or node credentials in diagnostics.
    pub fn diagnostic_code(&self) -> &str {
        match self {
            Self::Entitlement(message) => message,
            Self::Unauthorized => "unauthorized",
            Self::Network(_) => "network_error",
            Self::Api { .. } => "api_error",
            Self::Core(_) => "core_error",
            Self::System(_) => "system_error",
            Self::Config(_) => "config_validation_error",
            Self::Other(_) => "connection_error",
        }
    }

    pub fn connection_sync() -> Self {
        AppError::Other(CONNECTION_SYNC_ERROR.to_string())
    }
}

impl From<reqwest::Error> for AppError {
    fn from(e: reqwest::Error) -> Self {
        AppError::Network(e.to_string())
    }
}

impl From<std::io::Error> for AppError {
    fn from(e: std::io::Error) -> Self {
        AppError::System(e.to_string())
    }
}

impl From<serde_json::Error> for AppError {
    fn from(e: serde_json::Error) -> Self {
        AppError::Config(e.to_string())
    }
}

impl From<anyhow::Error> for AppError {
    fn from(e: anyhow::Error) -> Self {
        AppError::Other(e.to_string())
    }
}

// Tauri command 错误需可序列化为 JSON 字符串。
impl Serialize for AppError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}

pub type AppResult<T> = Result<T, AppError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn account_reasons_survive_connection_error_sanitization() {
        for reason in ["free_traffic_exhausted", "vip_required", "vip_expired"] {
            let expected = AppError::entitlement(reason).to_string();
            assert_ne!(expected, CONNECTION_SYNC_ERROR);
            assert_eq!(AppError::entitlement(reason).for_connection().to_string(), expected);
        }
        assert!(AppError::Unauthorized.for_connection().to_string().contains("重新登录"));
        for error in [AppError::entitlement("secret-unknown-reason"),
            AppError::Network("private-url".into()), AppError::core("private-config"),
            AppError::config("private-uuid"), AppError::other("unexpected-body")] {
            assert_eq!(error.for_connection().to_string(), CONNECTION_SYNC_ERROR);
        }
    }

    #[test]
    fn connection_failures_expose_only_the_approved_message() {
        assert_eq!(
            AppError::connection_sync().to_string(),
            "账户状态同步失败\n暂时无法连接，请检查网络后重试"
        );
    }
}
