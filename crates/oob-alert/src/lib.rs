//! **C3 — Out-of-Band alert channel** (Collab Protocol v0, design §3.4).
//!
//! Write alerts to filesystem + `tracing::error!` without going through
//! SQLite. Used by daemon self-checks (S1 FD enum / S5 schema version /
//! S6 post-write verify) where the alert subject IS state.db.
//!
//! Q-4 decision: DB-anomaly alerts MUST NOT call `forum_post`,
//! `memory_save`, or any SQLite write. They go here.
//!
//! ```ignore
//! use ab_oob_alert::{Alert, AlertKind, ProcessFd, write_alert};
//!
//! let a = Alert::new(AlertKind::FdDeleted)
//!     .with_process_inventory(vec![ProcessFd {
//!         pid: 1318355,
//!         fd: 10,
//!         target: "/Media/.../state.db (deleted)".into(),
//!     }])
//!     .with_suggested_action("agent-bridge rescue-snapshot --canonical");
//! write_alert(&a).expect("write OOB alert");
//! ```

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

/// Default directory for OOB alert files. `~/.cache/agent-bridge/alerts/`.
///
/// Mirrors AiOT-side `logs/seed_observer.jsonl` pattern (thread 10 #135)
/// — keep alert sink under `XDG_CACHE_HOME` so the user can `tail -F`
/// it without elevation.
pub fn default_alert_dir() -> PathBuf {
    if let Ok(p) = std::env::var("AB_OOB_ALERT_DIR") {
        return PathBuf::from(p);
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    PathBuf::from(home).join(".cache/agent-bridge/alerts")
}

/// Open inventory of `agent-bridge.real` processes' FD-10/11/12 (state.db
/// main / wal / shm) — populated by S1 multi-process FD enum.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProcessFd {
    pub pid: u32,
    pub fd: u32,
    /// readlink target as observed, e.g.
    /// `"/Media/.../state.db (deleted)"`. The literal `(deleted)`
    /// suffix is the kernel's signal — preserve it verbatim.
    pub target: String,
}

/// Closed set of alert kinds. Channel routing in `tracing` target field
/// uses the string form. Add to this enum as new self-checks ship.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum AlertKind {
    /// S1 — any agent-bridge.real process holds a state.db fd that
    /// readlink-resolves to `... (deleted)`. Indicates unlink+replace
    /// happened while the process was running.
    FdDeleted,
    /// S5 — schema_meta.version row changed between two ticks.
    /// Always an explicit migration; informational signal.
    SchemaChange,
    /// S6 — forum_post handler INSERTed a row but post-write `SELECT`
    /// didn't find it. Indicates split-brain MCP+daemon write race.
    PostWriteRaceMiss,
}

impl AlertKind {
    /// Kebab-case label for filename suffix.
    pub fn as_str(&self) -> &'static str {
        match self {
            AlertKind::FdDeleted => "fd-deleted",
            AlertKind::SchemaChange => "schema-change",
            AlertKind::PostWriteRaceMiss => "post-write-race-miss",
        }
    }
}

/// One OOB alert record. Stored as JSON file + emitted to tracing.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Alert {
    /// Seconds since UNIX epoch. Filename uses the same value.
    pub ts_unix: i64,
    pub kind: AlertKind,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub process_inventory: Vec<ProcessFd>,
    /// Free-form evidence (e.g. `{"before": {...}, "after": {...}}`).
    /// Kept as `serde_json::Value` so each alert kind decides its shape
    /// without churning this crate.
    #[serde(default, skip_serializing_if = "is_null_value")]
    pub evidence: serde_json::Value,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub suggested_action: String,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub next_steps: Vec<String>,
}

fn is_null_value(v: &serde_json::Value) -> bool {
    v.is_null()
}

impl Alert {
    /// Build an alert stamped with `SystemTime::now()`.
    pub fn new(kind: AlertKind) -> Self {
        let ts_unix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);
        Self {
            ts_unix,
            kind,
            process_inventory: Vec::new(),
            evidence: serde_json::Value::Null,
            suggested_action: String::new(),
            next_steps: Vec::new(),
        }
    }

    pub fn with_process_inventory(mut self, inv: Vec<ProcessFd>) -> Self {
        self.process_inventory = inv;
        self
    }

    pub fn with_evidence(mut self, ev: serde_json::Value) -> Self {
        self.evidence = ev;
        self
    }

    pub fn with_suggested_action(mut self, s: impl Into<String>) -> Self {
        self.suggested_action = s.into();
        self
    }

    pub fn with_next_steps(mut self, steps: Vec<String>) -> Self {
        self.next_steps = steps;
        self
    }
}

/// Errors writing OOB alerts. Callers should log + continue — alert
/// pipeline is best-effort, never block the daemon tick.
#[derive(thiserror::Error, Debug)]
pub enum WriteError {
    #[error("mkdir failed at {path}: {source}")]
    MkDir {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },
    #[error("write failed at {path}: {source}")]
    Write {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },
    #[error("serialize failed: {0}")]
    Serialize(#[from] serde_json::Error),
}

/// Persist `alert` to `<dir>/<ts>-<kind>.json` and emit a structured
/// `tracing::error!` line on target `agent_bridge::sync_safety` so the
/// systemd journal scrapes it.
///
/// File write uses **temp + atomic rename** so partial writes never
/// surface to readers. `dir` is created if missing.
///
/// Returns the path of the written file. On error, the alert is still
/// emitted to tracing — the caller's `Err` only signals that filesystem
/// persistence failed, not that the alert was lost from observability.
pub fn write_alert_to_dir(alert: &Alert, dir: &Path) -> Result<PathBuf, WriteError> {
    // Always emit to tracing first — this path is infallible.
    tracing::error!(
        target: "agent_bridge::sync_safety",
        kind = alert.kind.as_str(),
        ts_unix = alert.ts_unix,
        n_processes = alert.process_inventory.len(),
        suggested_action = %alert.suggested_action,
        "[C3 OOB ALERT] daemon self-check fired"
    );

    fs::create_dir_all(dir).map_err(|e| WriteError::MkDir {
        path: dir.to_path_buf(),
        source: e,
    })?;

    let final_path = dir.join(format!("{}-{}.json", alert.ts_unix, alert.kind.as_str()));
    let tmp_path = dir.join(format!(
        ".{}-{}.json.tmp",
        alert.ts_unix,
        alert.kind.as_str()
    ));

    let payload = serde_json::to_vec_pretty(alert)?;
    {
        let mut f = fs::File::create(&tmp_path).map_err(|e| WriteError::Write {
            path: tmp_path.clone(),
            source: e,
        })?;
        f.write_all(&payload).map_err(|e| WriteError::Write {
            path: tmp_path.clone(),
            source: e,
        })?;
        f.sync_all().map_err(|e| WriteError::Write {
            path: tmp_path.clone(),
            source: e,
        })?;
    }
    fs::rename(&tmp_path, &final_path).map_err(|e| WriteError::Write {
        path: final_path.clone(),
        source: e,
    })?;

    Ok(final_path)
}

/// Convenience: write to [`default_alert_dir()`].
pub fn write_alert(alert: &Alert) -> Result<PathBuf, WriteError> {
    write_alert_to_dir(alert, &default_alert_dir())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn write_alert_round_trip_via_atomic_rename() {
        let dir = TempDir::new().unwrap();
        let alert = Alert::new(AlertKind::FdDeleted)
            .with_process_inventory(vec![
                ProcessFd {
                    pid: 1318355,
                    fd: 10,
                    target: "/Media/.../state.db (deleted)".into(),
                },
                ProcessFd {
                    pid: 2232459,
                    fd: 9,
                    target: "/Media/.../state.db-wal (deleted)".into(),
                },
            ])
            .with_suggested_action("agent-bridge rescue-snapshot --canonical")
            .with_next_steps(vec!["see lesson_split_brain_forum_id_collision".into()]);

        let path = write_alert_to_dir(&alert, dir.path()).expect("write OK");

        assert!(path.exists(), "alert file must exist");
        assert!(
            path.file_name()
                .unwrap()
                .to_string_lossy()
                .ends_with(".json"),
            "alert filename ends with .json"
        );
        assert!(
            !path.file_name().unwrap().to_string_lossy().starts_with('.'),
            "atomic-rename target must NOT keep the dotfile prefix"
        );

        // Round-trip via serde
        let raw = fs::read_to_string(&path).expect("read alert");
        let parsed: Alert = serde_json::from_str(&raw).expect("parse alert");
        assert_eq!(parsed.kind, AlertKind::FdDeleted);
        assert_eq!(parsed.process_inventory.len(), 2);
        assert_eq!(parsed.process_inventory[0].pid, 1318355);
        assert_eq!(
            parsed.suggested_action,
            "agent-bridge rescue-snapshot --canonical"
        );
        assert_eq!(parsed.next_steps.len(), 1);
    }

    #[test]
    fn filename_includes_ts_and_kind() {
        let dir = TempDir::new().unwrap();
        let mut alert = Alert::new(AlertKind::SchemaChange);
        alert.ts_unix = 1700000000;
        let path = write_alert_to_dir(&alert, dir.path()).expect("write OK");
        assert_eq!(
            path.file_name().unwrap().to_string_lossy(),
            "1700000000-schema-change.json"
        );
    }

    #[test]
    fn alert_kind_str_labels_kebab_case() {
        assert_eq!(AlertKind::FdDeleted.as_str(), "fd-deleted");
        assert_eq!(AlertKind::SchemaChange.as_str(), "schema-change");
        assert_eq!(
            AlertKind::PostWriteRaceMiss.as_str(),
            "post-write-race-miss"
        );
    }

    #[test]
    fn empty_optional_fields_skipped_in_json() {
        let dir = TempDir::new().unwrap();
        let alert = Alert::new(AlertKind::SchemaChange);
        let path = write_alert_to_dir(&alert, dir.path()).expect("write OK");
        let raw = fs::read_to_string(&path).unwrap();
        // process_inventory empty Vec, suggested_action empty String,
        // next_steps empty Vec, evidence Null → should not appear.
        assert!(!raw.contains("process_inventory"));
        assert!(!raw.contains("suggested_action"));
        assert!(!raw.contains("next_steps"));
        assert!(!raw.contains("evidence"));
        // ts_unix and kind always present.
        assert!(raw.contains("ts_unix"));
        assert!(raw.contains("schema_change"));
    }

    #[test]
    fn default_alert_dir_respects_env_override() {
        std::env::set_var("AB_OOB_ALERT_DIR", "/tmp/ab-oob-alert-test-override");
        let d = default_alert_dir();
        assert_eq!(d, PathBuf::from("/tmp/ab-oob-alert-test-override"));
        std::env::remove_var("AB_OOB_ALERT_DIR");
    }
}
