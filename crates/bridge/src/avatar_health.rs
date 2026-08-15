//! Health projection for the independent avatar heartbeat.
//!
//! This keeps CLI and HTTP views aligned: launchd state, the stable
//! heartbeat presence row, and the fresh/stale decision are evaluated once
//! here and rendered by the caller.

use ab_store::StateStore;
use anyhow::{Context, Result};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Default, PartialEq)]
pub struct LaunchdProbe {
    pub loaded: bool,
    pub domain: String,
    pub target: String,
    pub state: Option<String>,
    pub runs: Option<i64>,
    pub last_exit_code: Option<i64>,
    pub run_interval_secs: Option<i64>,
    pub error: Option<String>,
}

fn home_dir() -> Result<PathBuf> {
    std::env::var_os("HOME")
        .map(PathBuf::from)
        .ok_or_else(|| anyhow::anyhow!("HOME is not set"))
}

fn unix_now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn label_component(value: &str) -> String {
    let mut out = String::new();
    for ch in value.chars() {
        if ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.') {
            out.push(ch.to_ascii_lowercase());
        } else if ch.is_whitespace() {
            out.push('-');
        }
    }
    let out = out.trim_matches(['-', '.', '_']).to_string();
    if out.is_empty() {
        "default".to_string()
    } else {
        out
    }
}

pub fn heartbeat_label(label: Option<&str>, project: &str) -> String {
    label
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(ToString::to_string)
        .unwrap_or_else(|| {
            format!(
                "com.agentbridge.avatar-heartbeat.{}",
                label_component(project)
            )
        })
}

/// Reject labels that cannot safely serve as a single launchd/file-name component.
///
/// Explicit heartbeat labels are identifiers, not paths. Keep the historical
/// trim/identity behavior in [`heartbeat_label`], then validate the resolved
/// value at every health-projection boundary before it reaches HOME, launchctl,
/// a plist, or a store key.
pub fn validate_heartbeat_label(label: &str) -> Result<()> {
    if label.is_empty() {
        anyhow::bail!("invalid heartbeat label: empty labels are not allowed");
    }
    if label.len() > 255 {
        anyhow::bail!("invalid heartbeat label: exceeds 255 bytes");
    }
    if matches!(label, "." | "..") {
        anyhow::bail!("invalid heartbeat label: dot path components are not allowed");
    }
    if !label
        .bytes()
        .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.'))
    {
        anyhow::bail!("invalid heartbeat label: use only ASCII letters, digits, '-', '_', or '.'");
    }
    Ok(())
}

/// Resolve the shared health identity without touching the filesystem, a
/// process, or the StateStore. Composition roots use this before acquiring
/// their own resources so malformed explicit labels cannot cause earlier
/// effects.
pub fn resolve_heartbeat_health_identity(
    label_arg: Option<&str>,
    project_arg: Option<&str>,
) -> Result<(String, String)> {
    let project = project_arg
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("agent-bridge")
        .to_string();
    let label = heartbeat_label(label_arg, &project);
    validate_heartbeat_label(&label)?;
    Ok((project, label))
}

pub fn heartbeat_plist_path(label: &str) -> Result<PathBuf> {
    validate_heartbeat_label(label)?;
    Ok(home_dir()?
        .join("Library")
        .join("LaunchAgents")
        .join(format!("{label}.plist")))
}

pub fn heartbeat_log_path(label: &str, suffix: &str) -> Result<PathBuf> {
    validate_heartbeat_label(label)?;
    Ok(home_dir()?
        .join("Library")
        .join("Logs")
        .join("agent-bridge")
        .join(format!("{label}.{suffix}.log")))
}

fn launchd_domain() -> Result<String> {
    let output = std::process::Command::new("id")
        .arg("-u")
        .output()
        .context("run id -u")?;
    if !output.status.success() {
        return Err(anyhow::anyhow!("id -u exited with {}", output.status));
    }
    let uid = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if uid.is_empty() {
        return Err(anyhow::anyhow!("id -u returned empty uid"));
    }
    Ok(format!("gui/{uid}"))
}

fn parse_i64_first(value: &str) -> Option<i64> {
    value
        .split(|ch: char| !ch.is_ascii_digit() && ch != '-')
        .find(|s| !s.is_empty())
        .and_then(|s| s.parse::<i64>().ok())
}

pub fn parse_launchctl_print(output: &str, domain: &str, target: &str) -> LaunchdProbe {
    let mut probe = LaunchdProbe {
        loaded: true,
        domain: domain.to_string(),
        target: target.to_string(),
        ..LaunchdProbe::default()
    };
    for line in output.lines().map(str::trim) {
        if let Some(rest) = line.strip_prefix("state = ") {
            probe.state = Some(rest.trim().to_string());
        } else if let Some(rest) = line.strip_prefix("runs = ") {
            probe.runs = parse_i64_first(rest);
        } else if let Some(rest) = line.strip_prefix("last exit code = ") {
            probe.last_exit_code = parse_i64_first(rest);
        } else if let Some(rest) = line.strip_prefix("run interval = ") {
            probe.run_interval_secs = parse_i64_first(rest);
        }
    }
    probe
}

pub fn probe_launchd(label: &str) -> Result<LaunchdProbe> {
    validate_heartbeat_label(label)?;
    let domain = launchd_domain()?;
    let target = format!("{domain}/{label}");
    let output = std::process::Command::new("launchctl")
        .args(["print", &target])
        .output()
        .with_context(|| format!("launchctl print {target}"))?;
    if output.status.success() {
        Ok(parse_launchctl_print(
            &String::from_utf8_lossy(&output.stdout),
            &domain,
            &target,
        ))
    } else {
        Ok(LaunchdProbe {
            loaded: false,
            domain,
            target,
            error: Some(String::from_utf8_lossy(&output.stderr).trim().to_string()),
            ..LaunchdProbe::default()
        })
    }
}

fn path_string(path: &Path) -> String {
    path.display().to_string()
}

fn xml_unescape(value: &str) -> String {
    value
        .replace("&quot;", "\"")
        .replace("&apos;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
}

pub fn parse_plist_program_arguments(contents: &str) -> Vec<String> {
    let mut saw_program_arguments = false;
    let mut in_array = false;
    let mut args = Vec::new();
    for line in contents.lines().map(str::trim) {
        if line == "<key>ProgramArguments</key>" {
            saw_program_arguments = true;
            continue;
        }
        if saw_program_arguments && line == "<array>" {
            in_array = true;
            continue;
        }
        if in_array && line == "</array>" {
            break;
        }
        if !in_array {
            continue;
        }
        if let Some(rest) = line.strip_prefix("<string>") {
            if let Some(value) = rest.strip_suffix("</string>") {
                args.push(xml_unescape(value));
            }
        }
    }
    args
}

fn heartbeat_binary_json(plist: &Path) -> Value {
    let args = std::fs::read_to_string(plist)
        .ok()
        .map(|contents| parse_plist_program_arguments(&contents))
        .unwrap_or_default();
    let binary_path = args.first().map(PathBuf::from);
    let exists = binary_path.as_ref().map(|p| p.exists()).unwrap_or(false);
    let configured_sync_presence = matches!(
        (
            args.get(1).map(String::as_str),
            args.get(2).map(String::as_str)
        ),
        (Some("avatar"), Some("sync-presence"))
    );
    let error = match binary_path.as_ref() {
        None => Some("missing ProgramArguments binary".to_string()),
        Some(binary) if !exists => Some(format!("binary does not exist: {}", binary.display())),
        Some(_) => None,
    };
    json!({
        "path": binary_path.as_ref().map(|p| path_string(p)),
        "exists": exists,
        "program_arguments": args,
        "probe_mode": "passive_program_arguments",
        "executable_invoked": false,
        "configured_sync_presence": configured_sync_presence,
        "supports_sync_presence": Value::Null,
        "supports_heartbeat_health": Value::Null,
        "missing_command": !configured_sync_presence,
        "error": error,
    })
}

fn launchd_probe_json(probe: &LaunchdProbe, plist: &Path, stdout: &Path, stderr: &Path) -> Value {
    json!({
        "loaded": probe.loaded,
        "domain": probe.domain,
        "target": probe.target,
        "state": probe.state,
        "runs": probe.runs,
        "last_exit_code": probe.last_exit_code,
        "run_interval_secs": probe.run_interval_secs,
        "error": probe.error,
        "plist_path": path_string(plist),
        "plist_exists": plist.exists(),
        "stdout_path": path_string(stdout),
        "stderr_path": path_string(stderr),
    })
}

pub async fn heartbeat_health(
    store: &dyn StateStore,
    label_arg: Option<&str>,
    project_arg: Option<&str>,
    stale_secs: i64,
) -> Result<Value> {
    let (project, label) = resolve_heartbeat_health_identity(label_arg, project_arg)?;
    let stale_secs = stale_secs.clamp(30, 86_400);
    let generated_at = unix_now();
    let plist_path = heartbeat_plist_path(&label)?;
    let stdout_path = heartbeat_log_path(&label, "out")?;
    let stderr_path = heartbeat_log_path(&label, "err")?;
    let launchd = probe_launchd(&label)?;
    let binary_json = heartbeat_binary_json(&plist_path);
    let presence_row = store
        .agent_presence_get(&label)
        .await
        .with_context(|| format!("agent_presence_get {label}"))?;

    let (presence_json, presence_fresh, presence_age) = match presence_row.as_ref() {
        Some(row) => {
            let avatar = crate::avatar_surface::entry_from_presence(row, false, false);
            let age = generated_at.saturating_sub(row.last_heartbeat_at);
            (
                json!({
                    "exists": true,
                    "session_id": row.session_id,
                    "last_heartbeat_at": row.last_heartbeat_at,
                    "age_secs": age,
                    "fresh": age <= stale_secs,
                    "avatar": avatar,
                }),
                age <= stale_secs,
                Some(age),
            )
        }
        None => (
            json!({
                "exists": false,
                "session_id": label,
                "last_heartbeat_at": Value::Null,
                "age_secs": Value::Null,
                "fresh": false,
                "avatar": Value::Null,
            }),
            false,
            None,
        ),
    };

    let last_exit_ok = launchd.last_exit_code.unwrap_or(0) == 0;
    let binary_exists = binary_json
        .get("exists")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let binary_missing_command = binary_json
        .get("missing_command")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let status = if !launchd.loaded {
        "not_loaded"
    } else if !binary_exists {
        "binary_missing"
    } else if binary_missing_command {
        "binary_missing_command"
    } else if !last_exit_ok {
        "failing"
    } else if presence_row.is_none() {
        "failing"
    } else if !presence_fresh {
        "stale"
    } else {
        "healthy"
    };
    let summary = match status {
        "healthy" => format!(
            "healthy: launchd loaded, last exit code 0, heartbeat age {}s",
            presence_age.unwrap_or(0)
        ),
        "stale" => format!(
            "stale: launchd is loaded but heartbeat age {}s exceeds {}s",
            presence_age.unwrap_or(0),
            stale_secs
        ),
        "failing" => {
            "failing: launchd is loaded but exit status or presence row is bad".to_string()
        }
        "binary_missing" => "binary_missing: heartbeat binary path is missing".to_string(),
        "binary_missing_command" => {
            "binary_missing_command: plist ProgramArguments does not configure avatar sync-presence"
                .to_string()
        }
        "not_loaded" => "not_loaded: launchd heartbeat job is not loaded".to_string(),
        _ => status.to_string(),
    };

    Ok(json!({
        "surface": "avatar_heartbeat_health",
        "read_only": true,
        "project": project,
        "label": label,
        "generated_at": generated_at,
        "stale_secs": stale_secs,
        "status": status,
        "healthy": status == "healthy",
        "summary": summary,
        "launchd": launchd_probe_json(&launchd, &plist_path, &stdout_path, &stderr_path),
        "binary": binary_json,
        "presence": presence_json,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn heartbeat_paths_reject_non_component_labels() {
        for label in [
            "/tmp/escape",
            "../escape",
            "nested/escape",
            "nested\\escape",
            "bad label",
            "bad\nlabel",
        ] {
            assert!(
                heartbeat_plist_path(label).is_err(),
                "unsafe heartbeat label should be rejected: {label:?}"
            );
            assert!(
                heartbeat_log_path(label, "out").is_err(),
                "unsafe heartbeat label should be rejected: {label:?}"
            );
        }
    }

    #[test]
    fn heartbeat_health_identity_accepts_legacy_safe_labels_and_rejects_unsafe_ones() {
        assert_eq!(
            resolve_heartbeat_health_identity(Some(" custom.label "), Some("ignored"))
                .expect("safe custom label"),
            ("ignored".to_string(), "custom.label".to_string())
        );
        assert_eq!(
            resolve_heartbeat_health_identity(None, Some("Agent Bridge")).expect("default label"),
            (
                "Agent Bridge".to_string(),
                "com.agentbridge.avatar-heartbeat.agent-bridge".to_string()
            )
        );
        for label in ["/tmp/escape", "../escape", "bad label", "bad\nlabel", "雪"] {
            assert!(
                resolve_heartbeat_health_identity(Some(label), Some("agent-bridge")).is_err(),
                "unsafe heartbeat label should be rejected: {label:?}"
            );
        }
    }

    #[cfg(unix)]
    #[test]
    fn heartbeat_binary_projection_never_executes_plist_program() {
        use std::os::unix::fs::PermissionsExt;

        let temp = tempfile::tempdir().expect("create tempdir");
        let sentinel = temp.path().join("sentinel");
        let marker = temp.path().join("invoked");
        std::fs::write(
            &sentinel,
            format!(
                "#!/bin/sh\nprintf invoked > '{}'\nprintf 'sync-presence heartbeat-health\\n'\n",
                marker.display()
            ),
        )
        .expect("write sentinel");
        let mut permissions = std::fs::metadata(&sentinel)
            .expect("stat sentinel")
            .permissions();
        permissions.set_mode(0o700);
        std::fs::set_permissions(&sentinel, permissions).expect("make sentinel executable");

        let plist = temp.path().join("heartbeat.plist");
        std::fs::write(
            &plist,
            format!(
                r#"<dict>
  <key>ProgramArguments</key>
  <array>
    <string>{}</string>
    <string>avatar</string>
    <string>sync-presence</string>
  </array>
</dict>
"#,
                sentinel.display()
            ),
        )
        .expect("write plist");

        let binary = heartbeat_binary_json(&plist);

        assert!(
            !marker.exists(),
            "heartbeat health must not execute ProgramArguments[0]"
        );
        assert_eq!(
            binary.get("probe_mode").and_then(Value::as_str),
            Some("passive_program_arguments")
        );
        assert_eq!(
            binary.get("executable_invoked").and_then(Value::as_bool),
            Some(false)
        );
        assert_eq!(
            binary
                .get("configured_sync_presence")
                .and_then(Value::as_bool),
            Some(true)
        );
        assert!(
            binary
                .get("supports_sync_presence")
                .is_some_and(Value::is_null),
            "passive projection must not claim executable support"
        );
        assert!(
            binary
                .get("supports_heartbeat_health")
                .is_some_and(Value::is_null),
            "passive projection must not claim executable support"
        );
    }

    #[test]
    fn heartbeat_binary_projection_marks_non_heartbeat_contract_missing() {
        let temp = tempfile::tempdir().expect("create tempdir");
        let binary_path = temp.path().join("configured-binary");
        std::fs::write(&binary_path, b"not executed").expect("write binary fixture");
        let plist = temp.path().join("heartbeat.plist");
        std::fs::write(
            &plist,
            format!(
                r#"<dict>
  <key>ProgramArguments</key>
  <array>
    <string>{}</string>
    <string>avatar</string>
    <string>heartbeat-health</string>
  </array>
</dict>
"#,
                binary_path.display()
            ),
        )
        .expect("write plist");

        let binary = heartbeat_binary_json(&plist);

        assert_eq!(
            binary
                .get("configured_sync_presence")
                .and_then(Value::as_bool),
            Some(false)
        );
        assert_eq!(binary.get("missing_command").and_then(Value::as_bool), Some(true));
        assert!(
            binary
                .get("supports_sync_presence")
                .is_some_and(Value::is_null)
        );
    }

    #[test]
    fn heartbeat_label_sanitizes_project() {
        assert_eq!(
            heartbeat_label(None, "Agent Bridge"),
            "com.agentbridge.avatar-heartbeat.agent-bridge"
        );
        assert_eq!(heartbeat_label(Some("custom.label"), "x"), "custom.label");
    }

    #[test]
    fn parse_launchctl_print_extracts_health_fields() {
        let output = r#"
gui/501/com.agentbridge.avatar-heartbeat.agent-bridge = {
    state = not running
    runs = 11
    last exit code = 0
    run interval = 60 seconds
}
"#;
        let probe = parse_launchctl_print(output, "gui/501", "gui/501/test");
        assert!(probe.loaded);
        assert_eq!(probe.state.as_deref(), Some("not running"));
        assert_eq!(probe.runs, Some(11));
        assert_eq!(probe.last_exit_code, Some(0));
        assert_eq!(probe.run_interval_secs, Some(60));
    }

    #[test]
    fn parse_plist_program_arguments_extracts_and_unescapes_strings() {
        let plist = r#"
<dict>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/me/.local/bin/agent-bridge.real</string>
    <string>avatar</string>
    <string>sync-presence</string>
    <string>risk &amp; focus</string>
  </array>
</dict>
"#;
        assert_eq!(
            parse_plist_program_arguments(plist),
            vec![
                "/Users/me/.local/bin/agent-bridge.real",
                "avatar",
                "sync-presence",
                "risk & focus"
            ]
        );
    }
}
