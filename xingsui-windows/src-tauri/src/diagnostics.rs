//! Bounded, credential-free connection diagnostics beside crash.log.
use std::io::Write;
use std::sync::Mutex;

static LOG_LOCK: Mutex<()> = Mutex::new(());

pub fn record(stage: &str, code: &str) {
    let Ok(_guard) = LOG_LOCK.lock() else { return };
    let dir = crate::crash_log_dir();
    if std::fs::create_dir_all(&dir).is_err() { return; }
    let path = dir.join("connection.log");
    if std::fs::metadata(&path).is_ok_and(|m| m.len() >= 256 * 1024) {
        let previous = dir.join("connection.log.1");
        let _ = std::fs::remove_file(&previous);
        if std::fs::rename(&path, previous).is_err() { return; }
    }
    if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(file, "[{}] v{} stage={} reason={}",
            chrono::Utc::now().to_rfc3339(), crate::api::version_name(), stage, code);
    }
}
