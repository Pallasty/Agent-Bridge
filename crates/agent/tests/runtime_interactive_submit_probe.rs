//! Configurable real-binary probe for interactive submit profiles.
//!
//! Ignored by default: this can launch real agent CLIs and make live model/API
//! calls. Use it when installing a new runtime or deciding whether a TUI submits
//! on bare Enter or Kitty CSI-u Enter.
//!
//! Minimal examples:
//!
//! ```text
//! AB_REAL_PTY_PROBE_RUNTIME=opencode \
//! AB_REAL_PTY_PROBE_PROFILE=enter \
//! cargo test -p ab-agent --test runtime_interactive_submit_probe -- --ignored --nocapture
//!
//! AB_REAL_PTY_PROBE_RUNTIME=gemini \
//! AB_REAL_PTY_PROBE_PROFILE=kitty_enter \
//! cargo test -p ab-agent --test runtime_interactive_submit_probe -- --ignored --nocapture
//! ```
//!
//! Useful overrides:
//! - `AB_REAL_PTY_PROBE_BIN=/absolute/path/to/cli`
//! - `AB_REAL_PTY_PROBE_ARGS_JSON='["--flag","value"]'`
//! - `AB_REAL_PTY_PROBE_CWD=/path/to/workspace`
//! - `AB_REAL_PTY_PROBE_BOOT_SECS=20`
//! - `AB_REAL_PTY_PROBE_RESPONSE_SECS=120`
//! - `AB_REAL_PTY_PROBE_PROMPT='Reply with exactly: AB42-PROBE-OK'`
//! - `AB_REAL_PTY_PROBE_EXPECT=AB42-PROBE-OK`

use ab_agent::pty_interactive::SubmitProfile;
use ab_agent::pty_session::PtySession;
use ab_core::{Error, Result};
use serde_json::Value;
use std::collections::HashMap;
use std::path::Path;
use std::sync::Arc;
use std::time::Duration;

struct ProbeConfig {
    runtime: String,
    binary: String,
    args: Vec<String>,
    cwd: String,
    profile_name: String,
    profile: SubmitProfile,
    boot_secs: u64,
    response_secs: u64,
    prompt: String,
    expect: String,
}

#[tokio::test]
#[ignore]
async fn configured_runtime_interactive_submit_profile_probe() {
    let Some(cfg) = (match ProbeConfig::from_env() {
        Ok(cfg) => cfg,
        Err(e) => panic!("invalid probe config: {e}"),
    }) else {
        eprintln!(
            "SKIP: set AB_REAL_PTY_PROBE_RUNTIME or AB_REAL_PTY_PROBE_BIN to run the live probe"
        );
        return;
    };

    eprintln!(
        "probe runtime={} binary={} args={:?} profile={} cwd={} boot={}s response={}s expect={}",
        cfg.runtime,
        cfg.binary,
        cfg.args,
        cfg.profile_name,
        cfg.cwd,
        cfg.boot_secs,
        cfg.response_secs,
        cfg.expect
    );

    let (sess, _exit_rx) =
        match PtySession::spawn(&cfg.binary, &cfg.args, &cfg.cwd, &HashMap::new()) {
            Ok(pair) => pair,
            Err(e) => {
                eprintln!("SKIP: {} not spawnable ({e})", cfg.binary);
                return;
            }
        };
    let sess = Arc::new(sess);
    tokio::time::sleep(Duration::from_secs(cfg.boot_secs)).await;

    submit_turn(&sess, &cfg.prompt, cfg.profile)
        .await
        .expect("submit probe turn");

    let matched = wait_for_output(&sess, &cfg.expect, cfg.response_secs).await;
    let output = sess.output_snapshot();
    let _ = sess.kill();

    if !matched {
        eprintln!("--- PTY output tail ---\n{}", tail_chars(&output, 6000));
    }
    assert!(
        matched,
        "expected marker {:?} was not observed; if the TUI accepted the prompt but did not submit, rerun with the other AB_REAL_PTY_PROBE_PROFILE (enter vs kitty_enter)",
        cfg.expect
    );
}

impl ProbeConfig {
    fn from_env() -> std::result::Result<Option<Self>, String> {
        let runtime = env_nonempty("AB_REAL_PTY_PROBE_RUNTIME");
        let explicit_binary = env_nonempty("AB_REAL_PTY_PROBE_BIN");
        if runtime.is_none() && explicit_binary.is_none() {
            return Ok(None);
        }

        let runtime = runtime.unwrap_or_else(|| "custom".to_string());
        let binary = explicit_binary
            .or_else(|| default_binary(&runtime))
            .ok_or_else(|| format!("no default binary for runtime '{runtime}'"))?;
        let args = match env_nonempty("AB_REAL_PTY_PROBE_ARGS_JSON") {
            Some(raw) => parse_args_json(&raw)?,
            None => Vec::new(),
        };
        let profile_name = env_nonempty("AB_REAL_PTY_PROBE_PROFILE")
            .unwrap_or_else(|| default_profile_name(&runtime).to_string());
        let profile = parse_profile(&profile_name)?;
        let cwd = env_nonempty("AB_REAL_PTY_PROBE_CWD").unwrap_or_else(default_cwd);
        let boot_secs = env_u64("AB_REAL_PTY_PROBE_BOOT_SECS", 20)?;
        let response_secs = env_u64("AB_REAL_PTY_PROBE_RESPONSE_SECS", 120)?;
        let prompt = env_nonempty("AB_REAL_PTY_PROBE_PROMPT")
            .unwrap_or_else(|| "Reply with exactly: AB42-PROBE-OK".to_string());
        let expect =
            env_nonempty("AB_REAL_PTY_PROBE_EXPECT").unwrap_or_else(|| "AB42-PROBE-OK".into());

        Ok(Some(Self {
            runtime,
            binary,
            args,
            cwd,
            profile_name,
            profile,
            boot_secs,
            response_secs,
            prompt,
            expect,
        }))
    }
}

fn default_binary(runtime: &str) -> Option<String> {
    match runtime {
        "codex" => Some(env_nonempty("AGENT_BRIDGE_CODEX_BIN").unwrap_or_else(|| "codex".into())),
        "opencode" => {
            Some(env_nonempty("AGENT_BRIDGE_OPENCODE_BIN").unwrap_or_else(|| "opencode".into()))
        }
        "kilo" => Some(env_nonempty("AGENT_BRIDGE_KILO_BIN").unwrap_or_else(|| "kilo".into())),
        "gemini" => {
            Some(env_nonempty("AGENT_BRIDGE_GEMINI_BIN").unwrap_or_else(|| "gemini".into()))
        }
        "auggie" => {
            Some(env_nonempty("AGENT_BRIDGE_AUGGIE_BIN").unwrap_or_else(|| "auggie".into()))
        }
        _ => None,
    }
}

fn default_profile_name(runtime: &str) -> &'static str {
    match runtime {
        "codex" => "kitty_enter",
        _ => "enter",
    }
}

fn parse_profile(raw: &str) -> std::result::Result<SubmitProfile, String> {
    match raw.trim().to_ascii_lowercase().as_str() {
        "enter" | "cr" => Ok(SubmitProfile::ENTER),
        "kitty" | "kitty_enter" | "kitty-enter" | "csi_u_enter" | "csi-u-enter" => {
            Ok(SubmitProfile::KITTY_ENTER)
        }
        other => Err(format!(
            "unknown AB_REAL_PTY_PROBE_PROFILE '{other}' (expected enter or kitty_enter)"
        )),
    }
}

fn parse_args_json(raw: &str) -> std::result::Result<Vec<String>, String> {
    let value: Value = serde_json::from_str(raw)
        .map_err(|e| format!("AB_REAL_PTY_PROBE_ARGS_JSON must be a JSON string array: {e}"))?;
    let Value::Array(items) = value else {
        return Err("AB_REAL_PTY_PROBE_ARGS_JSON must be a JSON string array".into());
    };
    let mut args = Vec::with_capacity(items.len());
    for item in items {
        match item {
            Value::String(s) => args.push(s),
            other => {
                return Err(format!(
                    "AB_REAL_PTY_PROBE_ARGS_JSON items must be strings, got {other}"
                ));
            }
        }
    }
    Ok(args)
}

fn env_u64(key: &str, default: u64) -> std::result::Result<u64, String> {
    match env_nonempty(key) {
        Some(raw) => raw
            .parse::<u64>()
            .map_err(|e| format!("{key} must be an integer number of seconds: {e}")),
        None => Ok(default),
    }
}

fn env_nonempty(key: &str) -> Option<String> {
    std::env::var(key)
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
}

fn default_cwd() -> String {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .map(|p| p.display().to_string())
        .unwrap_or_else(|| ".".to_string())
}

async fn submit_turn(sess: &Arc<PtySession>, text: &str, submit: SubmitProfile) -> Result<()> {
    if submit.settle.is_zero() {
        let payload = format!("{text}{}", submit.key);
        let s = sess.clone();
        tokio::task::spawn_blocking(move || s.write_input(&payload))
            .await
            .map_err(|e| Error::Backend(format!("submit_turn join: {e}")))?
    } else {
        let s1 = sess.clone();
        let t = text.to_string();
        tokio::task::spawn_blocking(move || s1.write_input(&t))
            .await
            .map_err(|e| Error::Backend(format!("submit_turn join: {e}")))??;
        tokio::time::sleep(submit.settle).await;
        let s2 = sess.clone();
        let key = submit.key;
        tokio::task::spawn_blocking(move || s2.write_input(key))
            .await
            .map_err(|e| Error::Backend(format!("submit_turn join: {e}")))?
    }
}

async fn wait_for_output(sess: &PtySession, needle: &str, secs: u64) -> bool {
    let mut waited_ms = 0u64;
    let total_ms = secs.saturating_mul(1000);
    while waited_ms <= total_ms {
        if sess.output_snapshot().contains(needle) {
            return true;
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
        waited_ms += 500;
    }
    false
}

fn tail_chars(s: &str, max_chars: usize) -> String {
    let count = s.chars().count();
    if count <= max_chars {
        return s.to_string();
    }
    s.chars().skip(count - max_chars).collect()
}

#[test]
fn parse_args_json_accepts_string_arrays() {
    assert_eq!(
        parse_args_json(r#"["--model","provider/model","--flag"]"#).unwrap(),
        vec!["--model", "provider/model", "--flag"]
    );
    assert!(parse_args_json(r#"{"bad":true}"#).is_err());
    assert!(parse_args_json(r#"["ok", 7]"#).is_err());
}

#[test]
fn parse_profile_accepts_known_submit_profiles() {
    let enter = parse_profile("enter").unwrap();
    assert_eq!(enter.key, "\r");
    assert!(enter.settle.is_zero());

    let kitty = parse_profile("kitty_enter").unwrap();
    assert_eq!(kitty.key, "\x1b[13u");
    assert!(!kitty.settle.is_zero());
    assert!(parse_profile("spacebar").is_err());
}
