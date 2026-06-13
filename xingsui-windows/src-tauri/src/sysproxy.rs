//! Windows 系统代理开关（注册表 Internet Settings）。
//! 连接前备份原值，断开/退出/崩溃时恢复，避免断网。

use crate::error::AppResult;

/// 备份的系统代理原始状态，用于断开后还原。
#[derive(Debug, Clone)]
pub struct ProxyBackup {
    pub enable: u32,
    pub server: String,
    pub override_list: String,
}

#[cfg(windows)]
const SETTINGS_PATH: &str = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings";

/// 启用系统代理（指向本地 127.0.0.1:port），返回原始状态备份。
#[cfg(windows)]
pub fn enable(port: u16) -> AppResult<ProxyBackup> {
    use winreg::enums::*;
    use winreg::RegKey;

    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let (key, _) = hkcu.create_subkey(SETTINGS_PATH)?;

    let backup = ProxyBackup {
        enable: key.get_value("ProxyEnable").unwrap_or(0u32),
        server: key.get_value("ProxyServer").unwrap_or_default(),
        override_list: key.get_value("ProxyOverride").unwrap_or_default(),
    };

    key.set_value("ProxyEnable", &1u32)?;
    key.set_value("ProxyServer", &format!("127.0.0.1:{port}"))?;
    key.set_value("ProxyOverride", &"localhost;127.*;10.*;192.168.*;<local>")?;
    notify_change();
    Ok(backup)
}

/// 还原系统代理到备份状态。
#[cfg(windows)]
pub fn restore(backup: &ProxyBackup) -> AppResult<()> {
    use winreg::enums::*;
    use winreg::RegKey;

    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let (key, _) = hkcu.create_subkey(SETTINGS_PATH)?;
    key.set_value("ProxyEnable", &backup.enable)?;
    key.set_value("ProxyServer", &backup.server)?;
    key.set_value("ProxyOverride", &backup.override_list)?;
    notify_change();
    Ok(())
}

/// 强制关闭系统代理（兜底清理，无备份时使用）。
#[cfg(windows)]
pub fn force_disable() -> AppResult<()> {
    use winreg::enums::*;
    use winreg::RegKey;

    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let (key, _) = hkcu.create_subkey(SETTINGS_PATH)?;
    key.set_value("ProxyEnable", &0u32)?;
    notify_change();
    Ok(())
}

/// 通知 WinINet 配置已变更，使新设置立即生效。
#[cfg(windows)]
fn notify_change() {
    use windows::Win32::Networking::WinInet::{
        InternetSetOptionW, INTERNET_OPTION_REFRESH, INTERNET_OPTION_SETTINGS_CHANGED,
    };
    unsafe {
        let _ = InternetSetOptionW(None, INTERNET_OPTION_SETTINGS_CHANGED, None, 0);
        let _ = InternetSetOptionW(None, INTERNET_OPTION_REFRESH, None, 0);
    }
}

// ---------- 非 Windows 占位（仅供跨平台 cargo check）----------
#[cfg(not(windows))]
pub fn enable(port: u16) -> AppResult<ProxyBackup> {
    let _ = port;
    Ok(ProxyBackup {
        enable: 0,
        server: String::new(),
        override_list: String::new(),
    })
}

#[cfg(not(windows))]
pub fn restore(_backup: &ProxyBackup) -> AppResult<()> {
    Ok(())
}

#[cfg(not(windows))]
pub fn force_disable() -> AppResult<()> {
    Ok(())
}
