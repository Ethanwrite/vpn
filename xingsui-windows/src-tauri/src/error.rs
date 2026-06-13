//! 统一错误类型：所有 Tauri command 返回 Result<T, AppError>，
//! 序列化为字符串供前端 Toast 友好提示。

use serde::Serialize;

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("网络请求失败：{0}")]
    Network(String),

    #[error("接口返回错误({status})：{message}")]
    Api { status: u16, message: String },

    #[error("尚未登录或登录已过期")]
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
