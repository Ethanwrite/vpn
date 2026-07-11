//! 前端通过 invoke 调用的命令层（UI 与 Rust 核心解耦）。

use crate::core;
use crate::error::{AppError, AppResult};
use crate::models::{ConnState, NetMode, StatusPayload, User, VpnNodeSummary};
use crate::state::AppState;
use crate::{store, vless};
use chrono::Utc;
use tauri::{AppHandle, Manager};

#[tauri::command]
pub async fn login(app: AppHandle, email: String, password: String) -> AppResult<User> {
    let state = app.state::<AppState>();
    let resp = state.api.login(&email, &password).await?;
    core::stop(&app).map_err(|_| AppError::connection_sync())?;
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
    core::stop(&app).map_err(|_| AppError::connection_sync())?;
    *state.token.write() = Some(resp.access_token.clone());
    store::save_token(&state.app_dir, &resp.access_token)?;
    Ok(resp.user)
}

/// 启动时静默恢复登录态：解密本地 token 并拉取用户信息。
#[tauri::command]
pub async fn restore_session(app: AppHandle) -> AppResult<Option<User>> {
    core::stop(&app).map_err(|_| AppError::connection_sync())?;
    let state = app.state::<AppState>();
    *state.token.write() = None;
    let token = match store::load_token(&state.app_dir)? {
        Some(t) => t,
        None => return Ok(None),
    };
    match state.api.get_me(&token).await {
        Ok(user) => {
            *state.token.write() = Some(token);
            Ok(Some(user))
        }
        Err(AppError::Unauthorized) => {
            *state.token.write() = None;
            let _ = store::clear_token(&state.app_dir);
            Ok(None)
        }
        Err(error) => Err(error),
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
    let stop_result = core::stop(&app);
    let state = app.state::<AppState>();
    *state.token.write() = None;
    store::clear_token(&state.app_dir)?;
    stop_result.map_err(|_| AppError::connection_sync())?;
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
    if !valid_node_id(&node_id) {
        let _ = core::stop(&app);
        return Err(AppError::connection_sync());
    }
    let token = match app.state::<AppState>().require_token() {
        Ok(token) => token,
        Err(_) => {
            let _ = core::stop(&app);
            return Err(AppError::connection_sync());
        }
    };
    if core::stop(&app).is_err() {
        return Err(AppError::connection_sync());
    }
    let generation = {
        let state = app.state::<AppState>();
        let mut rt = state.conn.lock();
        rt.generation = rt.generation.wrapping_add(1);
        rt.state = ConnState::Connecting;
        rt.node_id = Some(node_id.clone());
        rt.mode = mode;
        rt.generation
    };
    core::emit_status(&app, None);

    let config_result = {
        let state = app.state::<AppState>();
        state.api.get_node_config(&token, &node_id).await
    };
    if !attempt_is_current(&app, generation, &token) {
        return Ok(());
    }
    let config = match config_result {
        Ok(config) => config,
        Err(_) => return fail_attempt(&app, generation),
    };
    let validated = match vless::validate_node_config(&config, Utc::now()) {
        Ok(validated) => validated,
        Err(_) => return fail_attempt(&app, generation),
    };
    if !attempt_is_current(&app, generation, &token) {
        return Ok(());
    }
    match core::start_vless(
        &app,
        validated.vless,
        mode,
        config.id,
        config.name,
        config.tunnel_name,
        validated.lease_id,
        validated.expires_at,
        generation,
    ) {
        Ok(true) | Ok(false) => Ok(()),
        Err(_) => {
            if attempt_is_current(&app, generation, &token) {
                fail_attempt(&app, generation)
            } else {
                Ok(())
            }
        }
    }
}

fn attempt_is_current(app: &AppHandle, generation: u64, token: &str) -> bool {
    let state = app.state::<AppState>();
    let token_matches = state.token.read().as_deref() == Some(token);
    if !token_matches {
        return false;
    }
    let rt = state.conn.lock();
    attempt_snapshot_is_current(rt.generation, generation, rt.state, token_matches)
}

fn attempt_snapshot_is_current(
    current_generation: u64,
    expected_generation: u64,
    state: ConnState,
    token_matches: bool,
) -> bool {
    token_matches && current_generation == expected_generation && state == ConnState::Connecting
}

fn valid_node_id(node_id: &str) -> bool {
    !node_id.is_empty()
        && node_id.len() <= 64
        && node_id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
}

fn fail_attempt(app: &AppHandle, generation: u64) -> AppResult<()> {
    if core::stop_attempt(app, generation) {
        Err(AppError::connection_sync())
    } else {
        Ok(())
    }
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stale_cancelled_or_logged_out_attempt_never_starts() {
        assert!(attempt_snapshot_is_current(
            7,
            7,
            ConnState::Connecting,
            true
        ));
        assert!(!attempt_snapshot_is_current(
            8,
            7,
            ConnState::Connecting,
            true
        ));
        assert!(!attempt_snapshot_is_current(
            7,
            7,
            ConnState::Disconnected,
            true
        ));
        assert!(!attempt_snapshot_is_current(
            7,
            7,
            ConnState::Connecting,
            false
        ));
    }

    #[test]
    fn node_id_is_an_opaque_path_safe_identifier() {
        assert!(valid_node_id("node-singapore_1"));
        assert!(!valid_node_id("../me"));
        assert!(!valid_node_id("node/config"));
        assert!(!valid_node_id(""));
    }
}
