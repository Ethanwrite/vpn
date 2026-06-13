//! 前端通过 invoke 调用的命令层（UI 与 Rust 核心解耦）。

use crate::core;
use crate::error::{AppError, AppResult};
use crate::models::{ConnState, NetMode, StatusPayload, User, VpnNodeSummary};
use crate::state::AppState;
use crate::{awg, store};
use tauri::{AppHandle, Manager};

#[tauri::command]
pub async fn login(app: AppHandle, email: String, password: String) -> AppResult<User> {
    let state = app.state::<AppState>();
    let resp = state.api.login(&email, &password).await?;
    *state.token.write() = Some(resp.access_token.clone());
    store::save_token(&state.app_dir, &resp.access_token)?;
    Ok(resp.user)
}

#[tauri::command]
pub async fn register(
    app: AppHandle,
    email: String,
    password: String,
    invite_code: Option<String>,
) -> AppResult<User> {
    let state = app.state::<AppState>();
    let resp = state
        .api
        .register(&email, &password, invite_code.as_deref())
        .await?;
    *state.token.write() = Some(resp.access_token.clone());
    store::save_token(&state.app_dir, &resp.access_token)?;
    Ok(resp.user)
}

/// 启动时静默恢复登录态：解密本地 token 并拉取用户信息。
#[tauri::command]
pub async fn restore_session(app: AppHandle) -> AppResult<Option<User>> {
    let state = app.state::<AppState>();
    let token = match store::load_token(&state.app_dir)? {
        Some(t) => t,
        None => return Ok(None),
    };
    *state.token.write() = Some(token.clone());
    match state.api.get_me(&token).await {
        Ok(user) => Ok(Some(user)),
        Err(_) => {
            *state.token.write() = None;
            let _ = store::clear_token(&state.app_dir);
            Ok(None)
        }
    }
}

#[tauri::command]
pub async fn get_me(app: AppHandle) -> AppResult<User> {
    let state = app.state::<AppState>();
    let token = state.require_token()?;
    state.api.get_me(&token).await
}

#[tauri::command]
pub async fn logout(app: AppHandle) -> AppResult<()> {
    let _ = core::stop(&app);
    let state = app.state::<AppState>();
    *state.token.write() = None;
    store::clear_token(&state.app_dir)?;
    Ok(())
}

#[tauri::command]
pub async fn list_nodes(app: AppHandle) -> AppResult<Vec<VpnNodeSummary>> {
    let state = app.state::<AppState>();
    let token = state.require_token()?;
    state.api.list_nodes(&token).await
}

/// 一键连接指定节点（按 mode 选择 TUN / 系统代理）。
#[tauri::command]
pub async fn connect(app: AppHandle, node_id: String, mode: NetMode) -> AppResult<()> {
    let token = {
        let state = app.state::<AppState>();
        let mut rt = state.conn.lock();
        rt.state = ConnState::Connecting;
        rt.node_id = Some(node_id.clone());
        rt.mode = mode;
        state.require_token()?
    };
    core::emit_status(&app, Some("正在连接…".into()));

    let config = {
        let state = app.state::<AppState>();
        match state.api.get_node_config(&token, &node_id).await {
            Ok(c) => c,
            Err(e) => {
                let _ = core::stop(&app);
                return Err(e);
            }
        }
    };

    let awg_cfg = match awg::parse(&config.config_text) {
        Ok(c) => c,
        Err(e) => {
            let _ = core::stop(&app);
            return Err(e);
        }
    };
    core::start(&app, awg_cfg, mode, config.id, config.name)
}

#[tauri::command]
pub async fn disconnect(app: AppHandle) -> AppResult<()> {
    core::stop(&app)
}

/// 在保持当前节点的前提下切换网络模式（重连生效）。
#[tauri::command]
pub async fn switch_mode(app: AppHandle, mode: NetMode) -> AppResult<()> {
    let node_id = {
        let state = app.state::<AppState>();
        let rt = state.conn.lock();
        rt.node_id.clone()
    };
    match node_id {
        Some(id) => connect(app, id, mode).await,
        None => Err(AppError::other("当前未连接，无法切换模式")),
    }
}

#[tauri::command]
pub fn get_status(app: AppHandle) -> StatusPayload {
    let state = app.state::<AppState>();
    let rt = state.conn.lock();
    StatusPayload {
        state: rt.state,
        node_id: rt.node_id.clone(),
        node_name: rt.node_name.clone(),
        mode: rt.mode,
        message: None,
    }
}
