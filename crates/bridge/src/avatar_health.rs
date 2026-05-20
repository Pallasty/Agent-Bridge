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

pub fn heartbeat_plist_path(label: &str) -> Result<PathBuf> {
    Ok(home_dir()?
        .join("Library")
        .join("LaunchAgents")
        .join(format!("{label}.plist")))
}

pub fn heartbeat_log_path(label: &str, suffix: &str) -> Result<PathBuf> {
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

fn probe_binary_help(binary: Option<&Path>) -> (Option<bool>, Option<bool>, Option<String>) {
    let Some(binary) = binary else {
        return (
            None,
            None,
            Some("missing ProgramArguments binary".to_string()),
        );
    };
    if !binary.exists() {
        return (
            Some(false),
            Some(false),
            Some(format!("binary does not exist: {}", binary.display())),
        );
    }
    let output = std::process::Command::new(binary)
        .args(["avatar", "--help"])
        .output();
    match output {
        Ok(output) => {
            let mut text = String::new();
            text.push_str(&String::from_utf8_lossy(&output.stdout));
            text.push_str(&String::from_utf8_lossy(&output.stderr));
            let sync = output.status.success() && text.contains("sync-presence");
            let health = output.status.success() && text.contains("heartbeat-health");
            let error = if output.status.success() {
                None
            } else {
                Some(format!("avatar --help exited with {}", output.status))
            };
            (Some(sync), Some(health), error)
        }
        Err(err) => (
            Some(false),
            Some(false),
            Some(format!("avatar --help failed: {err}")),
        ),
    }
}

fn heartbeat_binary_json(plist: &Path) -> Value {
    let args = std::fs::read_to_string(plist)
        .ok()
        .map(|contents| parse_plist_program_arguments(&contents))
        .unwrap_or_default();
    let binary_path = args.first().map(PathBuf::from);
    let exists = binary_path.as_ref().map(|p| p.exists()).unwrap_or(false);
    let (supports_sync_presence, supports_heartbeat_health, error) =
        probe_binary_help(binary_path.as_deref());
    let missing_command = matches!(supports_sync_presence, Some(false));
    json!({
        "path": binary_path.as_ref().map(|p| path_string(p)),
        "exists": exists,
        "program_arguments": args,
        "supports_sync_presence": supports_sync_presence,
        "supports_heartbeat_health": supports_heartbeat_health,
        "missing_command": missing_command,
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
    let project = project_arg
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("agent-bridge")
        .to_string();
    let label = heartbeat_label(label_arg, &project);
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
            "binary_missing_command: heartbeat binary does not support sync-presence".to_string()
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
