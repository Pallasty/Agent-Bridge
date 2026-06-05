//! Honest grounding for the Agent Avatar Protocol embodiment state.
//!
//! Division of labour:
//!   * `pet_state`    — JSON sidecar IO (atomic read/write).
//!   * `pet_presence` — projects the sidecar to `agent_avatar_protocol=1`.
//!   * `pet_ground`   — *this* module: derives embodiment fields from real
//!     loop telemetry, and audits whether a state is genuinely grounded
//!     versus decorative.
//!
//! Load-bearing invariant (mirrors the voice-grounding lesson): a field that
//! makes a "truth claim" — `focus` (what I attend to), `activity_state` (what
//! I'm doing), `mood` (how it's going) — must be derivable from a real signal
//! and must carry its provenance. A bare constant (e.g. `mood:"calm"` written
//! unconditionally by the prompt hook) is decoration, not embodiment.
//! `audit_grounding` is the falsifier that catches decoration and staleness.

use serde_json::{json, Map, Value};

/// Telemetry captured at a real harness event — the grounding source of truth.
#[derive(Debug, Clone, Default)]
pub struct ToolTelemetry {
    /// Harness event name, e.g. "UserPromptSubmit", "PostToolUse", "Stop".
    pub event: String,
    /// Tool that just ran (PostToolUse), if any.
    pub tool_name: Option<String>,
    /// Raw tool input payload (file_path, key, command, ...).
    pub tool_input: Value,
}

impl ToolTelemetry {
    pub fn new(event: impl Into<String>) -> Self {
        Self {
            event: event.into(),
            tool_name: None,
            tool_input: Value::Null,
        }
    }

    pub fn with_tool(mut self, name: impl Into<String>, input: Value) -> Self {
        self.tool_name = Some(name.into());
        self.tool_input = input;
        self
    }
}

/// What kind of grounding failure the audit found.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GroundingIssue {
    /// A truth-claim field holds a value with no provenance source.
    Decorative,
    /// A field contradicts another grounded field (or the live event).
    Inconsistent,
    /// A claim is made (e.g. "verified") with no backing signal.
    UnverifiedClaim,
    /// The state is older than the freshness window.
    Stale,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GroundingViolation {
    pub field: String,
    pub issue: GroundingIssue,
    pub detail: String,
}

impl GroundingViolation {
    fn new(field: &str, issue: GroundingIssue, detail: impl Into<String>) -> Self {
        Self {
            field: field.to_string(),
            issue,
            detail: detail.into(),
        }
    }
}

/// Activity vocabulary grounded purely in the harness event. We deliberately do
/// NOT synthesise "verified" here — that is a higher-bar claim requiring a real
/// verification signal (`last_verified_at`), not merely an event.
pub fn activity_for_event(event: &str) -> &'static str {
    match event {
        "UserPromptSubmit" => "orienting",
        "PostToolUse" | "PreToolUse" => "working",
        "Stop" | "SubagentStop" => "idle",
        "Notification" => "waiting_for_user",
        _ => "working",
    }
}

/// Derive `focus` (what I am attending to) from the tool that just ran.
/// Returns `None` when the tool has no meaningful target — never invents one.
pub fn derive_focus_from_tool(tool_name: &str, tool_input: &Value) -> Option<String> {
    let field = |k: &str| {
        tool_input
            .get(k)
            .and_then(|v| v.as_str())
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
    };
    // Match by suffix so MCP-namespaced tools (mcp__server__memory_get) work too.
    let base = tool_name.rsplit("__").next().unwrap_or(tool_name);
    match base {
        "Edit" | "Write" | "Read" | "NotebookEdit" => field("file_path"),
        "memory_get" | "memory_save" | "memory_delete" => field("key"),
        "Bash" | "shell_exec" => field("description"),
        _ => None,
    }
}

/// Build the grounded patch to merge into the sidecar state for a given event.
/// Every truth-claim field is written together with its `*_source` provenance.
pub fn ground_patch(tel: &ToolTelemetry, now_rfc3339: &str) -> Map<String, Value> {
    let mut patch = Map::new();
    let activity = activity_for_event(&tel.event);
    patch.insert("activity_state".into(), json!(activity));
    patch.insert("mode".into(), json!(activity));
    patch.insert("last_event".into(), json!(tel.event));

    if let Some(tool) = &tel.tool_name {
        if let Some(focus) = derive_focus_from_tool(tool, &tel.tool_input) {
            patch.insert("focus".into(), json!(focus));
            patch.insert("focus_source".into(), json!(format!("tool:{tool}")));
        }
    }
    patch.insert("source".into(), json!("ab-pet-ground"));
    patch.insert("updated_at".into(), json!(now_rfc3339));
    patch
}

/// Merge a grounded patch into an existing sidecar state value.
pub fn apply_patch(state: &mut Value, patch: Map<String, Value>) {
    if !state.is_object() {
        *state = Value::Object(Map::new());
    }
    if let Some(obj) = state.as_object_mut() {
        for (k, v) in patch {
            obj.insert(k, v);
        }
    }
}

fn nonnull_str<'a>(state: &'a Value, key: &str) -> Option<&'a str> {
    state
        .get(key)
        .and_then(|v| v.as_str())
        .filter(|s| !s.is_empty())
}

const WORK_ACTIVITIES: &[&str] = &["working", "acting", "reviewing"];

/// Audit whether a projected/sidecar state is genuinely grounded.
///
/// * `telemetry` — when supplied, cross-check derived fields against the live event.
/// * `stale_before` — RFC3339 cutoff; states updated before it are flagged stale.
///
/// An empty result means the state passes the grounding contract.
pub fn audit_grounding(
    state: &Value,
    telemetry: Option<&ToolTelemetry>,
    stale_before: Option<&str>,
) -> Vec<GroundingViolation> {
    let mut violations = Vec::new();

    // 1. `mood` is a truth-claim: a non-null value requires a `mood_source`.
    if let Some(mood) = nonnull_str(state, "mood") {
        if nonnull_str(state, "mood_source").is_none() {
            violations.push(GroundingViolation::new(
                "mood",
                GroundingIssue::Decorative,
                format!("mood=\"{mood}\" has no mood_source — decorative constant"),
            ));
        }
    }

    // 2. `focus` is a truth-claim: a non-null value requires a `focus_source`.
    if let Some(focus) = nonnull_str(state, "focus") {
        if nonnull_str(state, "focus_source").is_none() {
            violations.push(GroundingViolation::new(
                "focus",
                GroundingIssue::Decorative,
                format!("focus=\"{focus}\" has no focus_source"),
            ));
        }
    }

    let activity = nonnull_str(state, "activity_state")
        .or_else(|| nonnull_str(state, "mode"))
        .unwrap_or("");

    // 3. Activity claims work but no focus is grounded => inconsistent.
    if WORK_ACTIVITIES.contains(&activity) && nonnull_str(state, "focus").is_none() {
        violations.push(GroundingViolation::new(
            "focus",
            GroundingIssue::Inconsistent,
            format!("activity_state=\"{activity}\" claims work but focus is null"),
        ));
    }

    // 4. A "verified" claim requires a real verification timestamp.
    if activity == "verified"
        && state
            .get("last_verified_at")
            .map(|v| v.is_null())
            .unwrap_or(true)
    {
        violations.push(GroundingViolation::new(
            "last_verified_at",
            GroundingIssue::UnverifiedClaim,
            "activity=\"verified\" with last_verified_at null",
        ));
    }

    // 5. Cross-check `focus` against the live event, when telemetry is supplied.
    if let Some(tel) = telemetry {
        if let Some(tool) = &tel.tool_name {
            if let Some(expected) = derive_focus_from_tool(tool, &tel.tool_input) {
                let actual = nonnull_str(state, "focus");
                if actual != Some(expected.as_str()) {
                    violations.push(GroundingViolation::new(
                        "focus",
                        GroundingIssue::Inconsistent,
                        format!("focus={actual:?} does not match last tool target {expected:?}"),
                    ));
                }
            }
        }
    }

    // 6. Staleness (RFC3339 UTC strings are lexically ordered).
    if let (Some(cutoff), Some(updated)) = (stale_before, nonnull_str(state, "updated_at")) {
        if updated < cutoff {
            violations.push(GroundingViolation::new(
                "updated_at",
                GroundingIssue::Stale,
                format!("updated_at={updated} is before cutoff {cutoff}"),
            ));
        }
    }

    violations
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn derive_focus_from_file_and_memory_tools() {
        assert_eq!(
            derive_focus_from_tool("Edit", &json!({"file_path": "/a/b.rs"})),
            Some("/a/b.rs".to_string())
        );
        assert_eq!(
            derive_focus_from_tool("mcp__agent-bridge__memory_get", &json!({"key": "k1"})),
            Some("k1".to_string())
        );
        // Tools without a meaningful target return None — never invent focus.
        assert_eq!(
            derive_focus_from_tool("WebFetch", &json!({"url": "x"})),
            None
        );
        assert_eq!(
            derive_focus_from_tool("Read", &json!({"file_path": ""})),
            None
        );
    }

    #[test]
    fn activity_grounded_in_event() {
        assert_eq!(activity_for_event("UserPromptSubmit"), "orienting");
        assert_eq!(activity_for_event("PostToolUse"), "working");
        assert_eq!(activity_for_event("Stop"), "idle");
    }

    #[test]
    fn ground_patch_carries_provenance() {
        let tel = ToolTelemetry::new("PostToolUse")
            .with_tool("Edit", json!({"file_path": "src/pet_ground.rs"}));
        let patch = ground_patch(&tel, "2026-06-05T12:00:00Z");
        assert_eq!(patch["activity_state"], json!("working"));
        assert_eq!(patch["focus"], json!("src/pet_ground.rs"));
        assert_eq!(patch["focus_source"], json!("tool:Edit"));
        assert_eq!(patch["source"], json!("ab-pet-ground"));
    }

    #[test]
    fn audit_flags_live_decorative_mood() {
        // The actual current live state: orienting + hardcoded calm + null focus.
        let live = json!({
            "mode": "orienting",
            "activity_state": "orienting",
            "mood": "calm",
            "focus": null,
            "last_verified_at": null,
            "source": "ab-memory-hook",
            "updated_at": "2026-06-05T12:09:10Z"
        });
        let violations = audit_grounding(&live, None, None);
        // orienting is pre-work, so focus-null is fine; but mood is a bare constant.
        assert!(violations
            .iter()
            .any(|x| x.field == "mood" && x.issue == GroundingIssue::Decorative));
        assert!(!violations.iter().any(|x| x.field == "focus"));
    }

    #[test]
    fn audit_passes_grounded_state() {
        let state = json!({
            "mode": "working",
            "activity_state": "working",
            "focus": "src/pet_ground.rs",
            "focus_source": "tool:Edit",
            "source": "ab-pet-ground",
            "updated_at": "2026-06-05T12:10:00Z"
        });
        let violations = audit_grounding(&state, None, None);
        assert!(
            violations.is_empty(),
            "unexpected violations: {violations:?}"
        );
    }

    #[test]
    fn audit_flags_work_without_focus() {
        let state = json!({"activity_state": "working", "focus": null});
        let violations = audit_grounding(&state, None, None);
        assert!(violations
            .iter()
            .any(|x| x.field == "focus" && x.issue == GroundingIssue::Inconsistent));
    }

    #[test]
    fn audit_flags_unverified_verified_claim() {
        let state = json!({
            "activity_state": "verified",
            "focus": "tests",
            "focus_source": "tool:Bash",
            "last_verified_at": null
        });
        let violations = audit_grounding(&state, None, None);
        assert!(violations
            .iter()
            .any(|x| x.field == "last_verified_at" && x.issue == GroundingIssue::UnverifiedClaim));
    }

    #[test]
    fn audit_cross_checks_focus_against_event() {
        let state = json!({
            "activity_state": "working",
            "focus": "old.rs",
            "focus_source": "tool:Edit"
        });
        let tel =
            ToolTelemetry::new("PostToolUse").with_tool("Edit", json!({"file_path": "new.rs"}));
        let violations = audit_grounding(&state, Some(&tel), None);
        assert!(violations
            .iter()
            .any(|x| x.field == "focus" && x.issue == GroundingIssue::Inconsistent));
    }

    #[test]
    fn audit_flags_stale() {
        let state = json!({"updated_at": "2026-06-05T10:00:00Z"});
        let violations = audit_grounding(&state, None, Some("2026-06-05T12:00:00Z"));
        assert!(violations.iter().any(|x| x.issue == GroundingIssue::Stale));
    }

    #[test]
    fn apply_patch_merges_into_state() {
        let mut state = json!({"mode": "orienting", "mood": "calm"});
        let tel =
            ToolTelemetry::new("PostToolUse").with_tool("Read", json!({"file_path": "lib.rs"}));
        apply_patch(&mut state, ground_patch(&tel, "2026-06-05T12:11:00Z"));
        assert_eq!(state["mode"], json!("working"));
        assert_eq!(state["focus"], json!("lib.rs"));
        // pre-existing unrelated fields are preserved.
        assert_eq!(state["mood"], json!("calm"));
    }

    /// End-to-end: the PostToolUse shell hook must write a sidecar that
    /// satisfies the same grounding contract as the Rust core, and must be a
    /// strict no-op when the gate flag is unset. This pins the shell producer
    /// to `audit_grounding` so the two paths cannot drift apart.
    #[cfg(unix)]
    #[test]
    fn ground_hook_output_passes_audit_and_respects_gate() {
        use std::io::Write as _;
        use std::process::{Command, Stdio};

        let script = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/src/hooks/ab-pet-ground-hook.sh"
        );
        if Command::new("bash").arg("--version").output().is_err() {
            eprintln!("skip ground_hook test: bash unavailable");
            return;
        }

        let run = |dir: &std::path::Path, gated_on: bool| -> std::process::ExitStatus {
            let payload = json!({
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": "src/pet_ground.rs"},
                "session_id": "test-session",
                "cwd": dir.to_string_lossy(),
            })
            .to_string();
            let mut cmd = Command::new("bash");
            cmd.arg(script)
                .env("XDG_DATA_HOME", dir)
                .env("AB_PET_ID", "xiao-shu-test")
                .env_remove("AB_MEMORY_CURATOR")
                .env_remove("AB_PET_STATE_DISABLE")
                .stdin(Stdio::piped())
                .stdout(Stdio::null())
                .stderr(Stdio::null());
            if gated_on {
                cmd.env("AB_PET_GROUND_TOOLS", "1");
            } else {
                cmd.env_remove("AB_PET_GROUND_TOOLS");
            }
            let mut child = cmd.spawn().expect("spawn hook");
            child
                .stdin
                .take()
                .expect("stdin")
                .write_all(payload.as_bytes())
                .expect("write payload");
            child.wait().expect("wait hook")
        };

        let sidecar = |dir: &std::path::Path| {
            dir.join("agent-bridge")
                .join("pet_state")
                .join("xiao-shu-test.json")
        };

        // Gate ON: grounded sidecar that passes the audit.
        let on = tempfile::tempdir().expect("tempdir");
        assert!(run(on.path(), true).success());
        let raw = std::fs::read_to_string(sidecar(on.path())).expect("sidecar written");
        let state: Value = serde_json::from_str(&raw).expect("valid json");
        assert_eq!(state["focus"], json!("src/pet_ground.rs"));
        assert_eq!(state["activity_state"], json!("working"));
        assert_eq!(state["focus_source"], json!("tool:Edit"));
        let violations = audit_grounding(&state, None, None);
        assert!(
            violations.is_empty(),
            "hook output failed audit: {violations:?}"
        );

        // Gate OFF: strict no-op, nothing written.
        let off = tempfile::tempdir().expect("tempdir");
        assert!(run(off.path(), false).success());
        assert!(
            !sidecar(off.path()).exists(),
            "gated-off hook must not write the sidecar"
        );
    }
}
