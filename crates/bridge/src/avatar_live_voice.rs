//! Default-off sparse voice policy for the foreground Linux avatar loop.
//!
//! This module decides whether one observed pet-sidecar transition may be sent
//! to the existing `audio_embody.py --mode voice` adapter. It never reads the
//! sidecar, starts a process, or emits audio itself.

use serde_json::{json, Value};
use std::path::{Path, PathBuf};

pub const DEFAULT_COOLDOWN_SECS: i64 = 300;
pub const DEFAULT_MAX_UTTERANCES: u64 = 3;
pub const DEFAULT_VOICE: &str = "Serena";
pub const DEFAULT_BACKEND: &str = "qwen3";
pub const DEFAULT_INSTRUCT: &str = "用温暖、清晰、简短的普通话播报，语速自然，不要添加额外内容。";
pub const ADAPTER_CONTRACT_MARKER: &str = "agent_bridge.linux_live_qwen_voice.v1";

#[derive(Clone, Debug)]
pub struct LinuxLiveVoiceConfig {
    pub enabled: bool,
    pub backend: String,
    pub python: String,
    pub script_path: PathBuf,
    pub qwen_worker: PathBuf,
    pub voice: String,
    pub instruct: String,
    pub sink: Option<String>,
    pub cooldown_secs: i64,
    pub max_utterances: u64,
    pub agent_id: String,
}

pub fn lifecycle_mode(state: &Value) -> String {
    state
        .get("mode")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or("idle")
        .to_string()
}

pub fn allowed_mode(mode: &str) -> bool {
    matches!(mode, "failed" | "verified" | "waiting_for_user" | "handoff")
}

pub fn fixed_line(mode: &str) -> Option<&'static str> {
    match mode {
        "failed" => Some("任务遇到问题，需要检查。"),
        "verified" => Some("验证已经通过。"),
        "waiting_for_user" => Some("需要你的确认。"),
        "handoff" => Some("任务已经准备交接。"),
        _ => None,
    }
}

pub fn evidence_ids(state: &Value) -> Vec<String> {
    let mut ids = Vec::new();
    for key in [
        "evidence_ids",
        "evidence_event_ids",
        "verification_outcome_ids",
    ] {
        if let Some(values) = state.get(key).and_then(Value::as_array) {
            for value in values.iter().filter_map(Value::as_str) {
                push_unique_visible(&mut ids, value);
            }
        }
    }
    for key in ["verified_outcome_id", "verification_outcome_id"] {
        if let Some(value) = state.get(key).and_then(Value::as_str) {
            push_unique_visible(&mut ids, value);
        }
    }
    ids
}

fn push_unique_visible(ids: &mut Vec<String>, value: &str) {
    let value = value.trim();
    if !value.is_empty()
        && value
            .chars()
            .any(|ch| !ch.is_whitespace() && !ch.is_control())
        && !ids.iter().any(|current| current == value)
    {
        ids.push(value.to_string());
    }
}

pub fn transition_decision(
    config: &LinuxLiveVoiceConfig,
    previous_mode: &str,
    state: &Value,
    last_spoken_at: Option<i64>,
    now: i64,
    utterance_count: u64,
    invocation_active: bool,
) -> Value {
    let mode = lifecycle_mode(state);
    let evidence = evidence_ids(state);
    let changed = mode != previous_mode;
    let cooldown_active = last_spoken_at
        .map(|then| now >= then && now - then < config.cooldown_secs)
        .unwrap_or(false);
    let mut blocked_reasons = Vec::new();
    if !config.enabled {
        blocked_reasons.push("voice_feedback_disabled");
    }
    if !changed {
        blocked_reasons.push("no_mode_transition");
    }
    if !allowed_mode(&mode) {
        blocked_reasons.push("mode_not_allowed");
    }
    if mode == "verified" && evidence.is_empty() {
        blocked_reasons.push("verified_requires_evidence");
    }
    if cooldown_active {
        blocked_reasons.push("cooldown_active");
    }
    if utterance_count >= config.max_utterances {
        blocked_reasons.push("session_utterance_limit_reached");
    }
    if invocation_active {
        blocked_reasons.push("voice_invocation_active");
    }
    let should_invoke = blocked_reasons.is_empty();
    json!({
        "surface": "linux_avatar_live_voice_transition",
        "schema": 1,
        "should_invoke": should_invoke,
        "previous_mode": previous_mode,
        "mode": mode,
        "line": fixed_line(&mode),
        "evidence_ids": evidence,
        "blocked_reasons": blocked_reasons,
        "cooldown": {
            "seconds": config.cooldown_secs,
            "active": cooldown_active,
            "last_spoken_at": last_spoken_at,
        },
        "session_budget": {
            "utterance_count": utterance_count,
            "max_utterances": config.max_utterances,
        },
        "authority": {
            "explicit_voice_feedback": config.enabled,
            "fixed_lines_only": true,
            "qwen3_only": true,
            "writes_pet_sidecar": false,
            "controls_desktop": false,
            "continuous_listening": false,
        },
    })
}

pub fn invocation_args(
    config: &LinuxLiveVoiceConfig,
    decision: &Value,
    last_spoken_at: Option<i64>,
) -> Vec<String> {
    let mode = decision
        .get("mode")
        .and_then(Value::as_str)
        .unwrap_or("idle");
    let line = decision.get("line").and_then(Value::as_str).unwrap_or("");
    let mut args = vec![
        config.script_path.to_string_lossy().to_string(),
        "--mode".to_string(),
        "voice".to_string(),
        "--lifecycle-mode".to_string(),
        mode.to_string(),
        "--agent-id".to_string(),
        config.agent_id.clone(),
        "--voice".to_string(),
        config.voice.clone(),
        "--voice-line".to_string(),
        line.to_string(),
        "--cooldown-secs".to_string(),
        config.cooldown_secs.to_string(),
        "--synth-backend".to_string(),
        config.backend.clone(),
        "--qwen-instruct".to_string(),
        config.instruct.clone(),
        "--json".to_string(),
    ];
    if config.backend == "qwen3" {
        args.push("--qwen-worker".to_string());
        args.push(config.qwen_worker.to_string_lossy().to_string());
    }
    if let Some(sink) = config
        .sink
        .as_deref()
        .map(str::trim)
        .filter(|v| !v.is_empty())
    {
        args.push("--sink".to_string());
        args.push(sink.to_string());
    }
    if let Some(last_spoken_at) = last_spoken_at.filter(|value| *value > 0) {
        args.push("--last-spoken-ts".to_string());
        args.push(last_spoken_at.to_string());
    }
    if let Some(evidence) = decision.get("evidence_ids").and_then(Value::as_array) {
        for evidence_id in evidence.iter().filter_map(Value::as_str) {
            args.push("--evidence-id".to_string());
            args.push(evidence_id.to_string());
        }
    }
    args
}

pub fn adapter_receipt_emitted(receipt: &Value) -> bool {
    match receipt.get("status").and_then(Value::as_str) {
        Some("emitted") => true,
        Some("played_unverified") => receipt
            .get("play_ok")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        _ => false,
    }
}

pub fn default_script_path(home: Option<&Path>) -> PathBuf {
    if let Some(home) = home {
        let deployed = home
            .join(".local")
            .join("share")
            .join("ab-tts")
            .join("audio_embody.py");
        if deployed.exists() {
            return deployed;
        }
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../scripts/audio_embody.py")
}

pub fn plan_json(config: &LinuxLiveVoiceConfig) -> Value {
    let (worker_is_socket, worker_owner_only, worker_owned_by_current_user) =
        worker_socket_status(&config.qwen_worker);
    let worker_ready = worker_is_socket && worker_owner_only && worker_owned_by_current_user;
    let script_exists = config.script_path.exists();
    let script_contract_ready = std::fs::read_to_string(&config.script_path)
        .map(|source| source.contains(ADAPTER_CONTRACT_MARKER))
        .unwrap_or(false);
    let python_ready = command_ready(&config.python);
    let voice_ready = !config.voice.trim().is_empty();
    let backend_supported = matches!(config.backend.as_str(), "qwen3" | "qwen3-lan");
    let lan_dispatcher = config
        .script_path
        .parent()
        .map(|parent| parent.join("qwen3_lan_remote_synth.py"))
        .unwrap_or_default();
    let lan_dispatcher_ready = lan_dispatcher.is_file();
    let lan_config_ready = [
        "AB_QWEN3_LAN_REMOTE_HOST",
        "AB_QWEN3_LAN_REMOTE_PYTHON",
        "AB_QWEN3_LAN_WORKER_SOCKET",
        "AB_QWEN3_LAN_HOST_KEY_ALIAS",
    ]
    .iter()
    .all(|key| {
        std::env::var(key)
            .map(|value| !value.trim().is_empty())
            .unwrap_or(false)
    });
    let backend_ready = match config.backend.as_str() {
        "qwen3" => worker_ready,
        "qwen3-lan" => lan_dispatcher_ready && lan_config_ready,
        _ => false,
    };
    json!({
        "enabled": config.enabled,
        "ready": !config.enabled || (backend_supported && backend_ready && script_contract_ready && python_ready && voice_ready),
        "backend": config.backend,
        "backend_supported": backend_supported,
        "backend_ready": backend_ready,
        "voice": config.voice,
        "voice_ready": voice_ready,
        "worker_socket": config.qwen_worker,
        "worker_socket_ready": worker_ready,
        "worker_is_socket": worker_is_socket,
        "worker_owner_only": worker_owner_only,
        "worker_owned_by_current_user": worker_owned_by_current_user,
        "lan_dispatcher": lan_dispatcher,
        "lan_dispatcher_ready": lan_dispatcher_ready,
        "lan_config_ready": lan_config_ready,
        "python": config.python,
        "python_ready": python_ready,
        "script_path": config.script_path,
        "script_exists": script_exists,
        "script_contract": ADAPTER_CONTRACT_MARKER,
        "script_contract_ready": script_contract_ready,
        "cooldown_secs": config.cooldown_secs,
        "max_utterances": config.max_utterances,
        "allowed_modes": ["failed", "verified", "waiting_for_user", "handoff"],
        "initial_state_silent": true,
        "fixed_lines_only": true,
        "continuous_listening": false,
    })
}

fn command_ready(command: &str) -> bool {
    let command = command.trim();
    if command.is_empty() {
        return false;
    }
    if command.contains(std::path::MAIN_SEPARATOR) {
        return Path::new(command).is_file();
    }
    std::env::var_os("PATH")
        .map(|paths| std::env::split_paths(&paths).any(|path| path.join(command).is_file()))
        .unwrap_or(false)
}

#[cfg(unix)]
fn worker_socket_status(path: &Path) -> (bool, bool, bool) {
    use std::os::unix::fs::{FileTypeExt, MetadataExt, PermissionsExt};
    std::fs::metadata(path)
        .map(|metadata| {
            let is_socket = metadata.file_type().is_socket();
            let owner_only = metadata.permissions().mode() & 0o077 == 0;
            let owned_by_current_user = metadata.uid() == rustix::process::geteuid().as_raw();
            (is_socket, owner_only, owned_by_current_user)
        })
        .unwrap_or((false, false, false))
}

#[cfg(not(unix))]
fn worker_socket_status(_path: &Path) -> (bool, bool, bool) {
    (false, false, false)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn config(enabled: bool) -> LinuxLiveVoiceConfig {
        LinuxLiveVoiceConfig {
            enabled,
            backend: DEFAULT_BACKEND.to_string(),
            python: "python3".to_string(),
            script_path: PathBuf::from("/tmp/audio_embody.py"),
            qwen_worker: PathBuf::from("/tmp/qwen.sock"),
            voice: DEFAULT_VOICE.to_string(),
            instruct: DEFAULT_INSTRUCT.to_string(),
            sink: None,
            cooldown_secs: DEFAULT_COOLDOWN_SECS,
            max_utterances: DEFAULT_MAX_UTTERANCES,
            agent_id: "agent-live".to_string(),
        }
    }

    #[test]
    fn default_off_and_initial_state_are_silent() {
        let state = json!({"mode": "handoff"});
        let disabled = transition_decision(&config(false), "working", &state, None, 1000, 0, false);
        assert_eq!(disabled["should_invoke"], false);
        assert!(disabled["blocked_reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("voice_feedback_disabled")));
        let initial = transition_decision(&config(true), "handoff", &state, None, 1000, 0, false);
        assert_eq!(initial["should_invoke"], false);
        assert!(initial["blocked_reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("no_mode_transition")));
    }

    #[test]
    fn verified_transition_requires_real_evidence() {
        let missing = transition_decision(
            &config(true),
            "working",
            &json!({"mode": "verified"}),
            None,
            1000,
            0,
            false,
        );
        assert_eq!(missing["should_invoke"], false);
        let grounded = transition_decision(
            &config(true),
            "working",
            &json!({"mode": "verified", "verification_outcome_id": "outcome-7"}),
            None,
            1000,
            0,
            false,
        );
        assert_eq!(grounded["should_invoke"], true);
        assert_eq!(grounded["evidence_ids"], json!(["outcome-7"]));
    }

    #[test]
    fn cooldown_budget_and_busy_state_fail_closed() {
        let state = json!({"mode": "handoff"});
        let cooling =
            transition_decision(&config(true), "working", &state, Some(900), 1000, 0, false);
        assert_eq!(cooling["should_invoke"], false);
        let exhausted = transition_decision(&config(true), "working", &state, None, 1000, 3, false);
        assert_eq!(exhausted["should_invoke"], false);
        let busy = transition_decision(&config(true), "working", &state, None, 1000, 0, true);
        assert_eq!(busy["should_invoke"], false);
    }

    #[test]
    fn invocation_is_fixed_qwen_worker_shape() {
        let decision = transition_decision(
            &config(true),
            "working",
            &json!({"mode": "handoff"}),
            None,
            1000,
            0,
            false,
        );
        let args = invocation_args(&config(true), &decision, Some(700));
        assert!(args
            .windows(2)
            .any(|pair| pair == ["--synth-backend", "qwen3"]));
        assert!(args
            .windows(2)
            .any(|pair| pair == ["--qwen-worker", "/tmp/qwen.sock"]));
        assert!(args
            .windows(2)
            .any(|pair| pair == ["--voice-line", "任务已经准备交接。"]));
        assert!(args
            .windows(2)
            .any(|pair| pair == ["--last-spoken-ts", "700"]));
    }

    #[test]
    fn lan_invocation_is_explicit_and_never_forwards_a_local_socket() {
        let mut cfg = config(true);
        cfg.backend = "qwen3-lan".to_string();
        let decision = transition_decision(
            &cfg,
            "working",
            &json!({"mode": "handoff"}),
            None,
            1000,
            0,
            false,
        );
        let args = invocation_args(&cfg, &decision, None);
        assert!(args
            .windows(2)
            .any(|pair| pair == ["--synth-backend", "qwen3-lan"]));
        assert!(!args.iter().any(|arg| arg == "--qwen-worker"));
    }

    #[test]
    fn only_observed_delivery_counts_as_an_utterance() {
        assert!(adapter_receipt_emitted(&json!({"status": "emitted"})));
        assert!(adapter_receipt_emitted(&json!({
            "status": "played_unverified", "play_ok": true
        })));
        assert!(!adapter_receipt_emitted(&json!({
            "status": "played_unverified", "play_ok": false
        })));
        assert!(!adapter_receipt_emitted(&json!({"status": "error"})));
    }

    #[cfg(unix)]
    #[test]
    fn plan_requires_an_owner_only_unix_worker_socket() {
        use std::os::unix::fs::PermissionsExt;

        let temp = tempfile::tempdir().unwrap();
        let socket = temp.path().join("qwen.sock");
        let _listener = std::os::unix::net::UnixListener::bind(&socket).unwrap();
        std::fs::set_permissions(&socket, std::fs::Permissions::from_mode(0o600)).unwrap();
        let script = temp.path().join("audio_embody.py");
        std::fs::write(&script, format!("# {ADAPTER_CONTRACT_MARKER}\n")).unwrap();
        let mut cfg = config(true);
        cfg.qwen_worker = socket.clone();
        cfg.script_path = script;
        let ready = plan_json(&cfg);
        assert_eq!(ready["ready"], true);
        assert_eq!(ready["worker_is_socket"], true);
        assert_eq!(ready["worker_owner_only"], true);
        assert_eq!(ready["worker_owned_by_current_user"], true);

        std::fs::set_permissions(&socket, std::fs::Permissions::from_mode(0o666)).unwrap();
        let exposed = plan_json(&cfg);
        assert_eq!(exposed["ready"], false);
        assert_eq!(exposed["worker_owner_only"], false);
    }
}
