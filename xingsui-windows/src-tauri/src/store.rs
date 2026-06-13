//! 本地登录态加密存储。
//! Windows 使用 DPAPI（CryptProtectData，绑定当前用户），密文落盘 AppData。

use crate::error::{AppError, AppResult};
use std::path::PathBuf;

const TOKEN_FILE: &str = "auth.bin";

fn token_path(app_dir: &PathBuf) -> PathBuf {
    app_dir.join(TOKEN_FILE)
}

/// 加密并保存 access token。
pub fn save_token(app_dir: &PathBuf, token: &str) -> AppResult<()> {
    std::fs::create_dir_all(app_dir)?;
    let cipher = encrypt(token.as_bytes())?;
    std::fs::write(token_path(app_dir), cipher)?;
    Ok(())
}

/// 读取并解密 access token；不存在返回 None。
pub fn load_token(app_dir: &PathBuf) -> AppResult<Option<String>> {
    let path = token_path(app_dir);
    if !path.exists() {
        return Ok(None);
    }
    let cipher = std::fs::read(path)?;
    let plain = decrypt(&cipher)?;
    Ok(Some(String::from_utf8_lossy(&plain).to_string()))
}

/// 清除登录态。
pub fn clear_token(app_dir: &PathBuf) -> AppResult<()> {
    let path = token_path(app_dir);
    if path.exists() {
        std::fs::remove_file(path)?;
    }
    Ok(())
}

#[cfg(windows)]
fn encrypt(data: &[u8]) -> AppResult<Vec<u8>> {
    use windows::Win32::Security::Cryptography::{CryptProtectData, CRYPT_INTEGER_BLOB};
    use windows::Win32::System::Memory::LocalFree;
    use windows::Win32::Foundation::HLOCAL;

    let mut input = CRYPT_INTEGER_BLOB {
        cbData: data.len() as u32,
        pbData: data.as_ptr() as *mut u8,
    };
    let mut output = CRYPT_INTEGER_BLOB::default();
    unsafe {
        CryptProtectData(&mut input, None, None, None, None, 0, &mut output)
            .map_err(|e| AppError::system(format!("DPAPI 加密失败: {e}")))?;
        let slice = std::slice::from_raw_parts(output.pbData, output.cbData as usize);
        let out = slice.to_vec();
        let _ = LocalFree(HLOCAL(output.pbData as *mut _));
        Ok(out)
    }
}

#[cfg(windows)]
fn decrypt(data: &[u8]) -> AppResult<Vec<u8>> {
    use windows::Win32::Security::Cryptography::{CryptUnprotectData, CRYPT_INTEGER_BLOB};
    use windows::Win32::System::Memory::LocalFree;
    use windows::Win32::Foundation::HLOCAL;

    let mut input = CRYPT_INTEGER_BLOB {
        cbData: data.len() as u32,
        pbData: data.as_ptr() as *mut u8,
    };
    let mut output = CRYPT_INTEGER_BLOB::default();
    unsafe {
        CryptUnprotectData(&mut input, None, None, None, None, 0, &mut output)
            .map_err(|e| AppError::system(format!("DPAPI 解密失败: {e}")))?;
        let slice = std::slice::from_raw_parts(output.pbData, output.cbData as usize);
        let out = slice.to_vec();
        let _ = LocalFree(HLOCAL(output.pbData as *mut _));
        Ok(out)
    }
}

// 非 Windows 仅用于跨平台 cargo check；不提供真实安全性。
#[cfg(not(windows))]
fn encrypt(data: &[u8]) -> AppResult<Vec<u8>> {
    use base64::Engine;
    Ok(base64::engine::general_purpose::STANDARD
        .encode(data)
        .into_bytes())
}

#[cfg(not(windows))]
fn decrypt(data: &[u8]) -> AppResult<Vec<u8>> {
    use base64::Engine;
    base64::engine::general_purpose::STANDARD
        .decode(data)
        .map_err(|e| AppError::system(e.to_string()))
}
