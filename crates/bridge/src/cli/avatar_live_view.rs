//! Pure plans and completed receipts for bounded live Avatar commands.
//! Callers retain sidecar, environment, clock, store, task and audio custody.
use ab_bridge::avatar_floater::BackendRecommendation;
use anyhow::Result;
use serde_json::{json, Value};

#[allow(clippy::too_many_arguments)]
pub(crate) fn linux_live_plan(
    native_compiled: bool,
    backend: &BackendRecommendation,
    presence_args: &Value,
    heartbeat_interval_secs: u64,
    renderer_plan: &Value,
    voice_plan: &Value,
    state_poll_ms: u64,
    voice_feedback: bool,
) -> Value {
    json!({
        "surface": "linux_avatar_live_plan",
        "schema": 1,
        "dry_run": true,
        "ready": native_compiled
            && backend.backend == ab_bridge::avatar_floater::AvatarBackend::NativeTransparent
            && voice_plan.get("ready").and_then(Value::as_bool).unwrap_or(false),
        "platform": std::env::consts::OS,
        "native_feature_compiled": native_compiled,
        "native_feature_contract": ab_bridge::avatar_native::NATIVE_FEATURE_CONTRACT,
        "backend": {
            "recommended": backend.backend.as_str(),
            "transparency_available": backend.transparency_available,
            "reason": backend.reason,
        },
        "presence": {
            "session_id": presence_args.get("session_id").cloned().unwrap_or(Value::Null),
            "agent_id": presence_args.get("agent_id").cloned().unwrap_or(Value::Null),
            "project": presence_args.get("project").cloned().unwrap_or(Value::Null),
            "role": presence_args.get("role").cloned().unwrap_or(Value::Null),
            "runtime": presence_args.get("runtime").cloned().unwrap_or(Value::Null),
            "pet_id": presence_args.get("pet_id").cloned().unwrap_or(Value::Null),
            "heartbeat_interval_secs": heartbeat_interval_secs,
            "stable_identity": true,
            "projects_current_sidecar_facets": true,
        },
        "renderer": renderer_plan,
        "voice_feedback": voice_plan,
        "observation": {
            "enabled": true,
            "read_only": true,
            "configured_poll_ms": state_poll_ms,
            "transition_sample_limit": 32,
            "measures": [
                "sidecar_poll_count",
                "sidecar_read_failures",
                "mode_transitions",
                "max_observed_poll_gap_ms",
                "process_peak_rss_bytes",
                "voice_invocation_latency_ms"
            ],
            "does_not_measure": [
                "compositor_pixels",
                "physical_display",
                "physical_audio",
                "worker_vram"
            ],
        },
        "safety": {
            "foreground_only": true,
            "installs_service": false,
            "writes_presence_only": !voice_feedback,
            "persistent_writes_presence_only": true,
            "creates_ephemeral_audio_files": voice_feedback,
            "writes_pet_sidecar": false,
            "audio_default_off": true,
            "emits_audio": voice_feedback,
            "emits_notification": false,
            "controls_desktop": false,
            "executes_actions": false,
            "enables_embodiment_runtime_p4": false,
        },
    })
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn linux_live_receipt(
    elapsed_ms: u64,
    presence_args: &Value,
    heartbeat_count: u64,
    heartbeat_failures: u64,
    last_heartbeat_error: &Option<String>,
    last_presence: &Value,
    renderer_plan: &Value,
    voice_receipt: &Value,
    observation_receipt: &Value,
    plan: &Value,
) -> Value {
    json!({
        "surface": "linux_avatar_live_receipt",
        "schema": 1,
        "dry_run": false,
        "completed": true,
        "elapsed_ms": elapsed_ms,
        "presence": {
            "session_id": presence_args.get("session_id").cloned().unwrap_or(Value::Null),
            "heartbeat_count": heartbeat_count,
            "heartbeat_failures": heartbeat_failures,
            "last_error": last_heartbeat_error,
            "last_projection": last_presence,
        },
        "renderer": {
            "completed": true,
            "launch_plan": renderer_plan,
            "dynamic_state_source": "pet_state_sidecar",
            "dynamic_state_polling_ran": true,
            "final_visual_state_observed": false,
            "reason": "the native surface completed and polled the sidecar, but this foreground receipt does not capture compositor pixels or infer the final visible sprite",
        },
        "voice_feedback": voice_receipt,
        "observation": observation_receipt,
        "safety": plan.get("safety").cloned().unwrap_or(Value::Null),
    })
}

pub(crate) fn voice_observer_plan(
    ready: bool,
    pet_id: &str,
    initial_mode: &str,
    duration_ms: u64,
    state_poll_ms: u64,
    voice_plan: &Value,
) -> Value {
    json!({
        "surface": "linux_avatar_voice_observer_plan",
        "schema": 1,
        "dry_run": true,
        "ready": ready,
        "pet_id": pet_id,
        "initial_mode": initial_mode,
        "duration_ms": duration_ms,
        "state_poll_ms": state_poll_ms,
        "voice_feedback": voice_plan,
        "ownership": {
            "renderer": false,
            "presence": false,
            "pet_state": false,
            "desktop_control": false,
            "voice_observer": true,
        },
        "safety": {
            "foreground_only": true,
            "bounded_duration": true,
            "initial_state_silent": true,
            "fixed_lines_only": true,
            "continuous_listening": false,
            "installs_service": false,
            "starts_renderer": false,
            "writes_presence": false,
            "writes_pet_sidecar": false,
            "controls_desktop": false,
            "emits_audio_when_live": true,
        },
    })
}

pub(crate) fn voice_observer_receipt(
    pet_id: &str,
    elapsed_ms: u64,
    voice_receipt: &Value,
    plan: &Value,
) -> Value {
    json!({
        "surface": "linux_avatar_voice_observer_receipt",
        "schema": 1,
        "dry_run": false,
        "completed": true,
        "pet_id": pet_id,
        "elapsed_ms": elapsed_ms,
        "voice_feedback": voice_receipt,
        "ownership": plan.get("ownership").cloned().unwrap_or(Value::Null),
        "safety": plan.get("safety").cloned().unwrap_or(Value::Null),
    })
}

pub(crate) fn render_linux_live_plan(
    plan: &Value,
    presence_args: &Value,
    duration_ms: u64,
    heartbeat_interval_secs: u64,
    voice_feedback: bool,
    as_json: bool,
) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&plan)?);
    } else {
        println!("Linux avatar live plan (dry run)");
        println!(
            "ready={} backend={} project={} pet_id={} session_id={}",
            plan["ready"],
            plan["backend"]["recommended"],
            presence_args["project"],
            presence_args["pet_id"],
            presence_args["session_id"]
        );
        println!(
            "duration_ms={} heartbeat_interval_secs={} audio={} actions=false",
            duration_ms, heartbeat_interval_secs, voice_feedback
        );
    }
    Ok(())
}

pub(crate) fn render_linux_live_receipt(
    receipt: &Value,
    heartbeat_count: u64,
    heartbeat_failures: u64,
    as_json: bool,
) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&receipt)?);
    } else {
        println!(
            "Linux avatar live completed heartbeats={} failures={} elapsed_ms={}",
            heartbeat_count, heartbeat_failures, receipt["elapsed_ms"]
        );
    }
    Ok(())
}

pub(crate) fn render_voice_observer_plan(
    plan: &Value,
    ready: bool,
    pet_id: &str,
    duration_ms: u64,
    as_json: bool,
) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&plan)?);
    } else {
        println!(
            "Avatar voice observer plan ready={} pet_id={} duration_ms={} renderer=false presence=false",
            ready, pet_id, duration_ms
        );
    }
    Ok(())
}

pub(crate) fn render_voice_observer_receipt(
    receipt: &Value,
    pet_id: &str,
    as_json: bool,
) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&receipt)?);
    } else {
        println!(
            "Avatar voice observer completed pet_id={} utterances={} elapsed_ms={}",
            pet_id, receipt["voice_feedback"]["utterance_count"], receipt["elapsed_ms"]
        );
    }
    Ok(())
}
