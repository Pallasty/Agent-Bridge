//! Sidecar state for Codex custom pets.
//!
//! The official Codex pet package stays a static spritesheet. This module owns
//! the small JSON presence state that hooks and MCP tools can read/write around
//! that renderer contract.

use serde_json::Value;
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

pub const DEFAULT_PET_ID: &str = "xiao-shu-v2";

/// Resolve the same state dir used by Agent-Bridge hook helpers.
pub fn agent_bridge_state_dir() -> PathBuf {
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
        return PathBuf::from(xdg).join("agent-bridge");
    }
    let home = std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/tmp"));
    if cfg!(target_os = "macos") {
        return home
            .join("Library")
            .join("Application Support")
            .join("agent-bridge");
    }
    home.join(".local").join("share").join("agent-bridge")
}

pub fn pet_state_dir() -> PathBuf {
    agent_bridge_state_dir().join("pet_state")
}

pub fn codex_global_state_path() -> PathBuf {
    let home = std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/tmp"));
    home.join(".codex").join(".codex-global-state.json")
}

pub fn sanitize_pet_id(raw: &str) -> Option<String> {
    let cleaned: String = raw
        .trim()
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_'))
        .collect();
    if cleaned.is_empty() {
        None
    } else {
        Some(cleaned)
    }
}

pub fn selected_codex_custom_avatar_id_from_path(path: &Path) -> Option<String> {
    let raw = fs::read_to_string(path).ok()?;
    let value: Value = serde_json::from_str(&raw).ok()?;
    let selected = value
        .get("electron-persisted-atom-state")
        .and_then(|v| v.get("selected-avatar-id"))
        .and_then(|v| v.as_str())?;
    let pet_id = selected.strip_prefix("custom:")?;
    sanitize_pet_id(pet_id)
}

pub fn selected_codex_custom_avatar_id() -> Option<String> {
    selected_codex_custom_avatar_id_from_path(&codex_global_state_path())
}

pub fn default_pet_id() -> String {
    std::env::var("AB_PET_ID")
        .ok()
        .and_then(|v| sanitize_pet_id(&v))
        .or_else(selected_codex_custom_avatar_id)
        .unwrap_or_else(|| DEFAULT_PET_ID.to_string())
}

pub fn normalize_pet_id(raw: Option<&str>) -> String {
    raw.and_then(sanitize_pet_id).unwrap_or_else(default_pet_id)
}

pub fn pet_state_path(pet_id: &str) -> PathBuf {
    pet_state_dir().join(format!("{}.json", normalize_pet_id(Some(pet_id))))
}

pub fn pet_state_path_in(state_dir: &Path, pet_id: &str) -> PathBuf {
    state_dir
        .join("pet_state")
        .join(format!("{}.json", normalize_pet_id(Some(pet_id))))
}

pub fn pet_ritual_state_path(pet_id: &str) -> PathBuf {
    pet_state_dir().join(format!("{}.ritual.json", normalize_pet_id(Some(pet_id))))
}

pub fn read_pet_state(pet_id: &str) -> io::Result<Option<Value>> {
    let path = pet_state_path(pet_id);
    read_pet_state_path(&path)
}

pub fn read_pet_state_path(path: &Path) -> io::Result<Option<Value>> {
    if !path.exists() {
        return Ok(None);
    }
    let raw = fs::read_to_string(path)?;
    let value =
        serde_json::from_str(&raw).map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
    Ok(Some(value))
}

pub fn write_pet_state_value(pet_id: &str, value: &Value) -> io::Result<PathBuf> {
    let path = pet_state_path(pet_id);
    write_pet_state_path(&path, value)?;
    Ok(path)
}

pub fn write_pet_state_path(path: &Path, value: &Value) -> io::Result<()> {
    let parent = path
        .parent()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "missing parent dir"))?;
    fs::create_dir_all(parent)?;

    let pid = std::process::id();
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let tmp_name = format!(
        ".tmp-{}-{}-{}",
        path.file_name()
            .and_then(|s| s.to_str())
            .unwrap_or("pet-state.json"),
        pid,
        nanos
    );
    let tmp_path = parent.join(tmp_name);

    let mut file = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&tmp_path)?;
    serde_json::to_writer_pretty(&mut file, value).map_err(io::Error::other)?;
    file.write_all(b"\n")?;
    file.sync_all()?;
    drop(file);

    fs::rename(&tmp_path, path)?;
    Ok(())
}

pub fn now_utc_rfc3339() -> String {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    unix_secs_to_utc_rfc3339(secs)
}

pub fn unix_secs_to_utc_rfc3339(secs: i64) -> String {
    let days = secs.div_euclid(86_400);
    let rem = secs.rem_euclid(86_400);
    let hour = rem / 3_600;
    let minute = (rem % 3_600) / 60;
    let second = rem % 60;
    let (year, month, day) = civil_from_days(days);
    format!("{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}Z")
}

fn civil_from_days(days_since_epoch: i64) -> (i32, u32, u32) {
    let z = days_since_epoch + 719_468;
    let era = (if z >= 0 { z } else { z - 146_096 }) / 146_097;
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let mut y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    if m <= 2 {
        y += 1;
    }
    (y as i32, m as u32, d as u32)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn normalize_pet_id_blocks_path_segments() {
        assert_eq!(normalize_pet_id(Some("../xiao shu!")), "xiaoshu");
        assert_eq!(normalize_pet_id(Some("xiao-shu_v2-1")), "xiao-shu_v2-1");
        assert_eq!(sanitize_pet_id("   "), None);
    }

    #[test]
    fn selected_codex_custom_avatar_id_reads_global_state() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join(".codex-global-state.json");
        fs::write(
            &path,
            json!({
                "electron-persisted-atom-state": {
                    "selected-avatar-id": "custom:xiao-shu-dev"
                }
            })
            .to_string(),
        )
        .expect("write codex state");

        assert_eq!(
            selected_codex_custom_avatar_id_from_path(&path).as_deref(),
            Some("xiao-shu-dev")
        );
    }

    #[test]
    fn selected_codex_custom_avatar_id_ignores_builtin_avatars() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join(".codex-global-state.json");
        fs::write(
            &path,
            json!({
                "electron-persisted-atom-state": {
                    "selected-avatar-id": "builtin:orb"
                }
            })
            .to_string(),
        )
        .expect("write codex state");

        assert_eq!(selected_codex_custom_avatar_id_from_path(&path), None);
    }

    #[test]
    fn write_then_read_state_atomically() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = pet_state_path_in(dir.path(), "xiao-shu-v2");
        let value = json!({
            "pet_id": "xiao-shu-v2",
            "mode": "handoff",
            "updated_at": "2026-05-17T10:00:00Z"
        });

        write_pet_state_path(&path, &value).expect("write pet state");
        let read = read_pet_state_path(&path)
            .expect("read pet state")
            .expect("state exists");
        assert_eq!(read["pet_id"], "xiao-shu-v2");
        assert_eq!(read["mode"], "handoff");
    }

    #[test]
    fn unix_secs_to_utc_rfc3339_formats_epoch_boundaries() {
        assert_eq!(unix_secs_to_utc_rfc3339(0), "1970-01-01T00:00:00Z");
        assert_eq!(
            unix_secs_to_utc_rfc3339(1_778_976_000),
            "2026-05-17T00:00:00Z"
        );
    }
}
