//! present_voice audio embodiment lane: TTS synthesis pipeline, playback, and the E3 embodied-mirror dashboard surface.
//! Extracted verbatim from `mcp_tools.rs` (2026-07 split, step 2); the
//! only mechanical delta is `pub(super)` on previously-private top-level
//! items (4 promoted) so the parent module and its other children
//! (tests.rs) keep seeing them through the parent's glob re-export.

use super::*;

/// Output-expression lane E3 (embodied mirror): renders a PERSISTENT dashboard
/// surface that mirrors the `present_replay` snapshot, and self-verifies the
/// embodiment by reading back the `chain_head` the rendered surface shows. See
/// `crate::present::build_dashboard_html` / `classify_embody`.
// ===========================================================================
//                            present_voice (audio embodiment)
// ===========================================================================
// Output-expression lane, AUDIO domain. Emits a KNOWN signal (a defined-frequency
// tone) to an output sink and reads it back off the SYSTEM BUS (the PipeWire sink
// `.monitor` loopback) to prove the requested signal actually reached the bus — a
// SPECTRAL-PEAK falsifier (Goertzel at the target freq vs the local spectral floor),
// robust to concurrent audio. HONEST BOUNDARY (the unverifiable last mile): this
// verifies the signal reached the OUTPUT BUS, NOT the physical transducer
// (headphone/speaker driver) — only a human, or (for speakers) the mic channel,
// can confirm that. Thin wrapper over scripts/audio_embody.py (the analysis +
// pure decision live there with Python truth-table tests), mirroring the
// desktop_verify / vision_grounding_ocr pattern. Writes a verified-outcome sidecar
// that flows into present_outcomes exactly like the display surfaces.
pub struct PresentVoiceTool {
    _hub: Hub,
}

impl PresentVoiceTool {
    pub fn new(hub: Hub) -> Self {
        Self { _hub: hub }
    }
}

#[async_trait]
impl McpTool for PresentVoiceTool {
    fn name(&self) -> &'static str {
        "present_voice"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Output-expression lane, AUDIO embodiment. backend=tone (default) emits a known \
                 tone; kokoro/piper use offline model TTS; say uses macOS native speech synthesis; qwen3 is an explicit, default-off external Qwen3-TTS CustomVoice adapter. \
                 Linux tone/model speech is played to an output sink and read back off the system bus (PipeWire \
                 sink .monitor loopback) to prove it reached the bus: tone uses a spectral-peak falsifier \
                 (Goertzel vs local floor); speech uses an energy-envelope cross-correlation falsifier (the \
                 captured bus signal's loudness-over-time must match the played WAV's shape) + voiced span — \
                 both robust to concurrent audio. macOS say+synth_file instead runs STT over the synthesized \
                 file, proving file intelligibility but NOT output-bus delivery or the physical transducer. \
                 Returns status (emitted|silent|mismatch|no_capture|error) plus an HONEST verified_to boundary. \
                 Writes a verified-outcome sidecar that flows into present_outcomes. capture_channel is \
                 sink_monitor, mic, or synth_file. Linux bus verification requires PipeWire + ffmpeg/paplay; \
                 kokoro/piper need ab-tts-synth and their model assets; qwen3 needs an explicit isolated Python runtime and official model assets; say needs macOS /usr/bin/say and Whisper \
                 for synth_file verification. Opt-in (Niche)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "backend": {"type": "string", "enum": ["tone", "kokoro", "piper", "say", "qwen3"], "default": "tone", "description": "tone = fixed-freq tone (default); kokoro/piper = offline model TTS; say = macOS native TTS; qwen3 = explicit external Qwen3-TTS CustomVoice. Speech on macOS verifies only the synthesized file via STT."},
                    "text": {"type": "string", "description": "Speech text; required for kokoro, piper, say, or qwen3."},
                    "voice": {"type": "string", "default": "af_sarah", "description": "TTS voice. Kokoro names use af_*/bf_*; macOS say accepts installed system voice names such as Samantha or Tingting."},
                    "speed": {"type": "number", "minimum": 0.5, "maximum": 2.0, "default": 1.0, "description": "Speech speed."},
                    "freq": {"type": "number", "minimum": 50, "maximum": 18000, "default": 440, "description": "backend=tone: tone frequency (Hz) whose presence on the bus is verified."},
                    "duration_ms": {"type": "integer", "minimum": 100, "maximum": 8000, "default": 1500},
                    "amplitude": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.25, "description": "backend=tone: output amplitude 0..1 (gentle by default)."},
                    "sink": {"type": "string", "description": "PipeWire output sink to emit to. Defaults to the system default sink; the SAME sink's .monitor is the bus-loopback readback."},
                    "capture_channel": {"type": "string", "enum": ["sink_monitor", "mic", "synth_file"], "default": "sink_monitor", "description": "Readback channel: sink_monitor = PipeWire bus loopback; mic = acoustic input; synth_file = STT over the synthesized file (macOS, does not verify playback)."},
                    "intent": {"type": "string", "description": "What this emission is the outcome of (recorded in the outcome sidecar; does not affect playback)."},
                    "synth_bin": {"type": "string", "description": "backend=kokoro/piper: explicit ab-tts-synth path (else env AB_TTS_SYNTH_BIN)."},
                    "qwen_instruct": {"type": "string", "description": "backend=qwen3: natural-language expression instruction, for example a calm, warm Mandarin delivery."},
                    "qwen_python": {"type": "string", "description": "backend=qwen3: explicit isolated Python 3.12 executable containing qwen-tts (else AB_QWEN3_TTS_PYTHON)."},
                    "qwen_model": {"type": "string", "description": "backend=qwen3: Qwen model id or local model directory; defaults to Qwen3-TTS 0.6B CustomVoice."},
                    "verify_intelligibility": {"type": "boolean", "default": false, "description": "backend=kokoro/piper: ALSO transcribe the bus capture (whisper.cpp). synth_file already uses STT as its primary falsifier."},
                    "stt_bin": {"type": "string", "description": "verify_intelligibility: whisper.cpp CLI path (else env AB_TTS_STT_BIN)."},
                    "stt_model": {"type": "string", "description": "verify_intelligibility: whisper ggml model path (else env AB_TTS_STT_MODEL)."},
                    "cwd": {"type": "string", "description": "Repo root to resolve scripts/audio_embody.py."},
                    "script_path": {"type": "string", "description": "Explicit audio_embody.py path (tests/alternate checkouts)."}
                }
            }),
        }
    }

    async fn execute(&self, args: Value, ctx: &ToolContext) -> Result<ToolResult> {
        let backend = args
            .get("backend")
            .and_then(|v| v.as_str())
            .unwrap_or("tone")
            .to_string();
        let is_speech = backend != "tone";
        let freq = args
            .get("freq")
            .and_then(|v| v.as_f64())
            .unwrap_or(440.0)
            .clamp(50.0, 18000.0);
        let duration_ms = args
            .get("duration_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(1500)
            .clamp(100, 8000);
        let amplitude = args
            .get("amplitude")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.25)
            .clamp(0.0, 1.0);
        let text = args
            .get("text")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let voice = args
            .get("voice")
            .and_then(|v| v.as_str())
            .unwrap_or("af_sarah")
            .to_string();
        let speed = args
            .get("speed")
            .and_then(|v| v.as_f64())
            .unwrap_or(1.0)
            .clamp(0.5, 2.0);
        let verify_intelligibility = args
            .get("verify_intelligibility")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let capture_channel = args
            .get("capture_channel")
            .and_then(|v| v.as_str())
            .unwrap_or("sink_monitor")
            .to_string();
        let intent = args
            .get("intent")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let cwd = args.get("cwd").and_then(|v| v.as_str()).map(PathBuf::from);

        if is_speech && text.trim().is_empty() {
            return Ok(ToolResult::error(format!(
                "present_voice backend={backend} requires a non-empty `text` to speak"
            )));
        }

        let script = present_voice_script_path(&args, cwd.as_ref());
        if !script.exists() {
            return Ok(ToolResult::error(format!(
                "audio_embody.py not found at {} (pass script_path or run from the Agent-Bridge repo root)",
                script.display()
            )));
        }

        let mut cmd = killable_command(
            std::env::var("PYTHON")
                .ok()
                .filter(|s| !s.trim().is_empty())
                .unwrap_or_else(|| "python3".to_string()),
        );
        cmd.arg(&script).arg("--json");
        if is_speech {
            // Speech backends are passed through exactly. The Python adapter owns the
            // platform route: say+synth_file on macOS; model+bus on Linux.
            cmd.arg("--mode")
                .arg("speech")
                .arg("--text")
                .arg(&text)
                .arg("--voice")
                .arg(&voice)
                .arg("--speed")
                .arg(format!("{speed}"))
                .arg("--synth-backend")
                .arg(&backend)
                .arg("--capture-channel")
                .arg(&capture_channel);
            push_optional_str_arg(&mut cmd, &args, "synth_bin", "--synth-bin");
            push_optional_str_arg(&mut cmd, &args, "qwen_instruct", "--qwen-instruct");
            push_optional_str_arg(&mut cmd, &args, "qwen_python", "--qwen-python");
            push_optional_str_arg(&mut cmd, &args, "qwen_model", "--qwen-model");
            if verify_intelligibility {
                cmd.arg("--check-intelligibility");
                push_optional_str_arg(&mut cmd, &args, "stt_bin", "--stt-bin");
                push_optional_str_arg(&mut cmd, &args, "stt_model", "--stt-model");
            }
        } else {
            cmd.arg("--freq")
                .arg(format!("{freq}"))
                .arg("--duration-ms")
                .arg(duration_ms.to_string())
                .arg("--amplitude")
                .arg(format!("{amplitude}"))
                .arg("--capture-channel")
                .arg(&capture_channel);
        }
        push_optional_str_arg(&mut cmd, &args, "sink", "--sink");
        cmd.stdout(std::process::Stdio::piped());
        cmd.stderr(std::process::Stdio::piped());
        if let Some(cwd) = cwd.as_ref() {
            cmd.current_dir(cwd);
        }

        // process kill ceiling. tone: emit duration + capture/ffmpeg margin. speech:
        // generous — first call loads the ~300 MB model (~3-4s) + synth + realtime play.
        let timeout_ms = if is_speech {
            120_000
        } else {
            duration_ms + 8_000
        };
        let output =
            match tokio::time::timeout(Duration::from_millis(timeout_ms), cmd.output()).await {
                Err(_) => {
                    return Ok(ToolResult::error(format!(
                        "present_voice: audio_embody exceeded {timeout_ms} ms"
                    )))
                }
                Ok(Err(e)) => {
                    return Ok(ToolResult::error(format!(
                        "present_voice: spawn failed: {e}"
                    )))
                }
                Ok(Ok(o)) => o,
            };
        let (stdout, _) = lossy_truncate(&output.stdout);
        let (stderr, _) = lossy_truncate(&output.stderr);
        let res: Value = match serde_json::from_str(&stdout) {
            Ok(v) => v,
            Err(e) => {
                return Ok(ToolResult::error(format!(
                    "present_voice: audio_embody returned invalid JSON: {e}; stderr={stderr}"
                )));
            }
        };

        let status = res
            .get("status")
            .and_then(|v| v.as_str())
            .unwrap_or("error");
        let verify_status = res
            .get("verify_status")
            .and_then(|v| v.as_str())
            .unwrap_or("error");
        // The platform adapter is authoritative for the method/backend/channel it
        // actually used. On macOS a requested offline speech backend intentionally
        // routes to native `say` + STT over the synthesized file; labelling that as
        // PipeWire bus readback would overstate the verified boundary.
        let verify_method = res
            .get("verify_method")
            .and_then(|v| v.as_str())
            .unwrap_or("audio_bus_readback")
            .to_string();
        let effective_backend = res
            .get("synth_backend")
            .and_then(|v| v.as_str())
            .unwrap_or(&backend)
            .to_string();
        let effective_capture_channel = res
            .get("capture_channel")
            .and_then(|v| v.as_str())
            .unwrap_or(&capture_channel)
            .to_string();

        // Provenance: the present_replay chain_head over the lane's artifacts NOW
        // (same idiom present()/present_dashboard use). build_outcome_memory now
        // forwards chain_head into the durable row (P-defer #2), so an ingested
        // voice outcome carries the same provenance the bus readback saw.
        let dir = crate::present::presentations_dir();
        let chain_head = {
            let artifacts = crate::present::list_artifacts(&dir, 500, None);
            crate::present::present_replay_snapshot(
                &artifacts,
                0usize,
                0u64,
                crate::present::now_unix(),
            )
            .get("chain_head")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_default()
        };
        let ts = crate::present::now_unix();
        let id = if is_speech {
            format!("voice_{backend}_{ts}")
        } else {
            format!("voice_{}hz_{}", freq as u64, ts)
        };
        // Faithful log regardless of outcome (the gate decides eligibility on the
        // read side). verify_status=rendered_ok ONLY when the played audio was
        // confirmed at the adapter-declared boundary. On Linux that is normally the
        // bus; on macOS synth_file_stt proves only the synthesized file.
        // Mode-specific metrics are present for the active backend, null otherwise.
        let outcome_record = json!({
            "artifact_id": id,
            "intent": intent,
            "action_tool": "present_voice",
            "kind": "voice",
            "backend": effective_backend,
            "verify_status": verify_status,
            "embody_status": crate::present::EmbodyStatus::NotApplicable.as_str(),
            "verify_method": verify_method,
            "audio_status": status,
            "capture_channel": effective_capture_channel,
            "verified_to": res.get("verified_to"),
            "not_verified": res.get("not_verified"),
            // speech-mode fields
            "text": if is_speech { json!(text) } else { Value::Null },
            "voice": res.get("voice"),
            "played_dur_s": res.get("played_dur_s"),
            "env_corr": res.get("env_corr"),
            "voiced_secs": res.get("voiced_secs"),
            "capture_rms": res.get("capture_rms"),
            // intelligibility (STT round-trip; present only when verify_intelligibility)
            "intelligibility": res.get("intelligibility"),
            "word_overlap": res.get("word_overlap"),
            "stt_transcript": res.get("stt_transcript"),
            // tone-mode fields
            "freq": if is_speech { Value::Null } else { json!(freq) },
            "rms": res.get("rms"),
            "goertzel": res.get("goertzel"),
            "goertzel_floor": res.get("goertzel_floor"),
            "peak_ratio": res.get("peak_ratio"),
            "chain_head": chain_head,
            "session_id": ctx.session_id.as_ref().map(|s| s.to_string()),
            "ts": ts,
        });
        let _ = crate::present::write_outcome_sidecar(&dir, &id, &outcome_record);

        let mut result = res;
        if let Some(obj) = result.as_object_mut() {
            obj.insert("id".to_string(), json!(id));
            obj.insert("action_tool".to_string(), json!("present_voice"));
            obj.insert("verify_method".to_string(), json!(verify_method));
            obj.insert("chain_head".to_string(), json!(chain_head));
            obj.insert(
                "outcome_sidecar".to_string(),
                json!(format!("{id}.outcome.json")),
            );
            obj.insert(
                "mcp_wrapper".to_string(),
                json!({
                    "tool": "present_voice",
                    "exit_code": output.status.code().unwrap_or(-1),
                    "stderr_present": !stderr.is_empty()
                }),
            );
        }
        Ok(ToolResult::json_text(&result))
    }
}

pub(super) fn present_voice_script_path(args: &Value, cwd: Option<&PathBuf>) -> PathBuf {
    if let Some(path) = args.get("script_path").and_then(|v| v.as_str()) {
        return PathBuf::from(path);
    }
    if let Ok(path) = std::env::var("AGENT_BRIDGE_AUDIO_EMBODY_SCRIPT") {
        if !path.trim().is_empty() {
            return PathBuf::from(path);
        }
    }
    if let Some(cwd) = cwd {
        let path = cwd.join("scripts/audio_embody.py");
        if path.exists() {
            return path;
        }
    }
    if let Ok(cwd) = std::env::current_dir() {
        let path = cwd.join("scripts/audio_embody.py");
        if path.exists() {
            return path;
        }
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../scripts/audio_embody.py")
}

/// Persist a human audibility decision for exactly one existing voice outcome.
///
/// This is a separate evidence row: it never rewrites the machine-produced
/// synth/bus receipt and never generalises one person's decision to future runs.
pub struct PresentVoiceConfirmAudibilityTool {
    _hub: Hub,
}

impl PresentVoiceConfirmAudibilityTool {
    pub fn new(hub: Hub) -> Self {
        Self { _hub: hub }
    }
}

pub(super) fn build_voice_audibility_confirmation(
    source: &Value,
    source_digest: &str,
    confirmation_id: &str,
    audibility: &str,
    confirmed_by: &str,
    playback_path: &str,
    note: &str,
    ts: u64,
    session_id: Option<&str>,
) -> std::result::Result<Value, String> {
    if source.get("kind").and_then(Value::as_str) != Some("voice") {
        return Err("source outcome kind must be voice".to_string());
    }
    let source_artifact_id = source
        .get("artifact_id")
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty())
        .ok_or_else(|| "source voice outcome has no artifact_id".to_string())?;
    let (decision, verified_to, not_verified) = match audibility {
        "confirmed_audible" => (
            "approved",
            Some("human_reported_audible_at_playback_endpoint"),
            "objective loudness, audio quality, comfort, and future voice runs",
        ),
        "confirmed_not_audible" => (
            "rejected",
            Some("human_reported_not_audible_at_playback_endpoint"),
            "failure cause, objective signal path, and future voice runs",
        ),
        "uncertain" => (
            "pending",
            None,
            "audibility, objective signal path, audio quality, and future voice runs",
        ),
        _ => {
            return Err(
                "audibility must be confirmed_audible|confirmed_not_audible|uncertain".to_string(),
            )
        }
    };
    Ok(json!({
        "artifact_id": confirmation_id,
        "intent": format!("human audibility confirmation for {source_artifact_id}"),
        "action_tool": "present_voice_confirm_audibility",
        "kind": "voice_audibility_confirmation",
        "verify_status": "rendered_ok",
        "embody_status": crate::present::EmbodyStatus::NotApplicable.as_str(),
        "decision": decision,
        "audibility": audibility,
        "verify_method": "human_decision",
        "verified_to": verified_to,
        "not_verified": not_verified,
        "scope": "single_voice_outcome",
        "source_artifact_id": source_artifact_id,
        "source_outcome_sha256": source_digest,
        "source_machine_verify_method": source.get("verify_method").cloned().unwrap_or(Value::Null),
        "source_machine_verified_to": source.get("verified_to").cloned().unwrap_or(Value::Null),
        "source_machine_verify_status": source.get("verify_status").cloned().unwrap_or(Value::Null),
        "confirmation_provenance": "caller_asserted_human_statement",
        "confirmed_by": confirmed_by,
        "playback_path": playback_path,
        "note": note,
        "session_id": session_id,
        "ts": ts,
    }))
}

pub(super) fn latest_voice_audibility_by_source(records: &[Value]) -> Value {
    let mut latest = std::collections::BTreeMap::<String, Value>::new();
    for record in records {
        if record.get("kind").and_then(Value::as_str) != Some("voice_audibility_confirmation") {
            continue;
        }
        let Some(source_id) = record
            .get("source_artifact_id")
            .and_then(Value::as_str)
            .filter(|v| !v.is_empty())
        else {
            continue;
        };
        let candidate_ts = record.get("ts").and_then(Value::as_u64).unwrap_or_default();
        let replace = latest
            .get(source_id)
            .and_then(|current| current.get("ts"))
            .and_then(Value::as_u64)
            .map(|current_ts| candidate_ts >= current_ts)
            .unwrap_or(true);
        if replace {
            latest.insert(source_id.to_string(), record.clone());
        }
    }
    Value::Object(latest.into_iter().collect())
}

/// Read-only health projection over machine voice receipts and their explicitly
/// linked, single-outcome human audibility confirmations. This never treats a
/// human confirmation as a property of a backend, device, or future run.
pub(super) fn voice_delivery_health_projection(
    records: &[Value],
    now: u64,
    confirmation_fresh_secs: u64,
) -> Value {
    let voices: Vec<&Value> = records
        .iter()
        .filter(|record| record.get("kind").and_then(Value::as_str) == Some("voice"))
        .collect();
    let voice_outcome_count = voices.len();
    let confirmations = latest_voice_audibility_by_source(records);
    let confirmation_rows = confirmations.as_object();

    let mut machine_rendered_ok_count = 0usize;
    let mut machine_failed_count = 0usize;
    let mut confirmed_audible_fresh_count = 0usize;
    let mut confirmed_not_audible_fresh_count = 0usize;
    let mut uncertain_fresh_count = 0usize;
    let mut expired_confirmation_count = 0usize;
    let mut unconfirmed_count = 0usize;

    for voice in &voices {
        if voice.get("verify_status").and_then(Value::as_str) == Some("rendered_ok") {
            machine_rendered_ok_count += 1;
        } else {
            machine_failed_count += 1;
        }
        let source_id = voice.get("artifact_id").and_then(Value::as_str);
        let confirmation = source_id.and_then(|id| confirmation_rows.and_then(|rows| rows.get(id)));
        let confirmation_ts = confirmation
            .and_then(|row| row.get("ts"))
            .and_then(Value::as_u64);
        let fresh = confirmation_ts
            .map(|ts| ts <= now && now.saturating_sub(ts) <= confirmation_fresh_secs)
            .unwrap_or(false);
        if !fresh {
            if confirmation.is_some() {
                expired_confirmation_count += 1;
            }
            unconfirmed_count += 1;
            continue;
        }
        match confirmation
            .and_then(|row| row.get("audibility"))
            .and_then(Value::as_str)
        {
            Some("confirmed_audible") => confirmed_audible_fresh_count += 1,
            Some("confirmed_not_audible") => confirmed_not_audible_fresh_count += 1,
            _ => {
                uncertain_fresh_count += 1;
                unconfirmed_count += 1;
            }
        }
    }

    let latest_voice = voices.into_iter().max_by(|a, b| {
        let a_ts = a.get("ts").and_then(Value::as_u64).unwrap_or_default();
        let b_ts = b.get("ts").and_then(Value::as_u64).unwrap_or_default();
        let a_id = a.get("artifact_id").and_then(Value::as_str).unwrap_or("");
        let b_id = b.get("artifact_id").and_then(Value::as_str).unwrap_or("");
        a_ts.cmp(&b_ts).then_with(|| a_id.cmp(b_id))
    });
    let latest_source_id = latest_voice
        .and_then(|row| row.get("artifact_id"))
        .and_then(Value::as_str);
    let latest_confirmation = latest_source_id
        .and_then(|id| confirmation_rows.and_then(|rows| rows.get(id)))
        .cloned();
    let latest_confirmation_ts = latest_confirmation
        .as_ref()
        .and_then(|row| row.get("ts"))
        .and_then(Value::as_u64);
    let latest_confirmation_fresh = latest_confirmation_ts
        .map(|ts| ts <= now && now.saturating_sub(ts) <= confirmation_fresh_secs)
        .unwrap_or(false);
    let latest_machine_ok = latest_voice
        .and_then(|row| row.get("verify_status"))
        .and_then(Value::as_str)
        == Some("rendered_ok");
    let latest_audibility = latest_confirmation
        .as_ref()
        .and_then(|row| row.get("audibility"))
        .and_then(Value::as_str);

    let (status, recommended_action) = if latest_voice.is_none() {
        (
            "insufficient_evidence",
            "emit_one_explicit_test_then_request_single_human_confirmation",
        )
    } else if !latest_machine_ok {
        (
            "failed",
            "inspect_machine_synthesis_or_verification_failure",
        )
    } else if latest_confirmation_fresh && latest_audibility == Some("confirmed_not_audible") {
        (
            "delivery_mismatch",
            "inspect_named_playback_endpoint_then_emit_a_new_explicit_test",
        )
    } else if latest_confirmation_fresh && latest_audibility == Some("confirmed_audible") {
        ("healthy_confirmed", "none")
    } else if latest_confirmation_fresh && latest_audibility == Some("uncertain") {
        (
            "insufficient_evidence",
            "request_a_clear_single_human_audibility_confirmation",
        )
    } else {
        (
            "machine_only",
            "request_single_human_audibility_confirmation",
        )
    };

    json!({
        "schema": "voice_delivery_health/v1",
        "read_only": true,
        "emits_audio": false,
        "changes_playback_device": false,
        "confirmation_scope": "each human confirmation applies only to its linked voice artifact",
        "now": now,
        "confirmation_fresh_secs": confirmation_fresh_secs,
        "status": status,
        "recommended_action": recommended_action,
        "voice_outcome_count": voice_outcome_count,
        "machine": {
            "rendered_ok_count": machine_rendered_ok_count,
            "failed_count": machine_failed_count,
            "latest": latest_voice.cloned().unwrap_or(Value::Null),
        },
        "human": {
            "latest_confirmation": latest_confirmation,
            "latest_confirmation_fresh": latest_confirmation_fresh,
            "confirmed_audible_fresh_count": confirmed_audible_fresh_count,
            "confirmed_not_audible_fresh_count": confirmed_not_audible_fresh_count,
            "uncertain_fresh_count": uncertain_fresh_count,
            "expired_confirmation_count": expired_confirmation_count,
            "unconfirmed_count": unconfirmed_count,
        },
        "not_verified": "objective loudness, audio quality, physical transducer behavior beyond each named human report, and delivery of future voice runs",
    })
}

/// Read-only operator projection for whether the latest explicit voice outcome
/// has matching, fresh human audibility evidence.
pub struct VoiceDeliveryHealthTool {
    _hub: Hub,
}

impl VoiceDeliveryHealthTool {
    pub fn new(hub: Hub) -> Self {
        Self { _hub: hub }
    }
}

#[async_trait]
impl McpTool for VoiceDeliveryHealthTool {
    fn name(&self) -> &'static str {
        "voice_delivery_health"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only voice delivery health projection. Correlates machine voice receipts with \
                 their explicitly linked, single-outcome human audibility confirmations. Reports \
                 healthy_confirmed|machine_only|delivery_mismatch|failed|insufficient_evidence \
                 plus an operator recommendation. Never emits audio, changes playback devices, \
                 or generalises a human report to a backend or future run. Niche."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "window_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 86400,
                        "description": "Look-back window over voice outcomes and confirmations."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "default": 200,
                        "description": "Maximum sidecar records scanned, newest-first."
                    },
                    "confirmation_fresh_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 604800,
                        "description": "A human confirmation older than this is historical only, not current delivery evidence."
                    }
                },
                "additionalProperties": false
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let window_secs = args
            .get("window_secs")
            .and_then(Value::as_u64)
            .unwrap_or(86_400)
            .clamp(60, 31_536_000);
        let limit = args
            .get("limit")
            .and_then(Value::as_u64)
            .unwrap_or(200)
            .clamp(1, 1000) as usize;
        let confirmation_fresh_secs = args
            .get("confirmation_fresh_secs")
            .and_then(Value::as_u64)
            .unwrap_or(604_800)
            .clamp(60, 31_536_000);
        let now = dispatch_now_secs().max(0) as u64;
        let cutoff = now.saturating_sub(window_secs);
        let records = crate::present::read_outcome_records(
            &crate::present::presentations_dir(),
            limit,
            cutoff,
        );
        Ok(ToolResult::json_text(&voice_delivery_health_projection(
            &records,
            now,
            confirmation_fresh_secs,
        )))
    }
}

/// Combines independent, read-only body-scheduling and voice-delivery
/// observations without deriving a cross-domain policy or actuator command.
pub(super) fn embodiment_operating_readiness_projection(
    body_scheduling_advice: Value,
    voice_delivery_health: Value,
) -> Value {
    let body_recommendation = body_scheduling_advice
        .get("recommendation")
        .cloned()
        .unwrap_or(Value::Null);
    let voice_recommendation = voice_delivery_health
        .get("recommended_action")
        .cloned()
        .unwrap_or(Value::Null);
    json!({
        "schema": "embodiment_operating_readiness/v1",
        "mode": "observation_only",
        "read_only": true,
        "emits_audio": false,
        "changes_playback_device": false,
        "changes_routing": false,
        "changes_parallelism": false,
        "changes_task_admission": false,
        "cross_domain_causal_inference": false,
        "cross_domain_policy_change": false,
        "automatic_action_allowed": false,
        "body_scheduling_advice": body_scheduling_advice,
        "voice_delivery_health": voice_delivery_health,
        "operator_checks": [
            {
                "domain": "body_scheduling",
                "recommendation": body_recommendation,
                "authority": "advisory_only"
            },
            {
                "domain": "voice_delivery",
                "recommendation": voice_recommendation,
                "authority": "single_outcome_human_evidence_only"
            }
        ],
        "not_verified": "whether body pressure caused any voice result, whether voice delivery affects task quality, and whether either observation should automatically change execution",
    })
}

/// One read-only operator surface for two independent embodiment observations.
pub struct EmbodimentOperatingReadinessTool {
    _hub: Hub,
}

impl EmbodimentOperatingReadinessTool {
    pub fn new(hub: Hub) -> Self {
        Self { _hub: hub }
    }
}

#[async_trait]
impl McpTool for EmbodimentOperatingReadinessTool {
    fn name(&self) -> &'static str {
        "embodiment_operating_readiness"
    }

    fn annotations(&self) -> Option<ToolAnnotations> {
        Some(ToolAnnotations::read_only())
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Read-only embodiment operating snapshot. Places body scheduling advice and \
                 voice delivery health beside one another without inferring a causal relationship \
                 or changing routing, parallelism, task admission, audio, or playback devices. \
                 Niche."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "workload_class": {
                        "type": "string",
                        "enum": ["light", "standard", "heavy", "sustained", "remote_heavy"],
                        "default": "standard",
                        "description": "Read-only body scheduling observation context."
                    },
                    "requested_parallelism": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1024,
                        "default": 1
                    },
                    "voice_window_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 86400
                    },
                    "voice_limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "default": 200
                    },
                    "confirmation_fresh_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 604800
                    }
                },
                "additionalProperties": false
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let workload_class = args
            .get("workload_class")
            .and_then(Value::as_str)
            .unwrap_or("standard");
        let requested_parallelism = args
            .get("requested_parallelism")
            .and_then(Value::as_u64)
            .unwrap_or(1)
            .clamp(1, 1024);
        let voice_window_secs = args
            .get("voice_window_secs")
            .and_then(Value::as_u64)
            .unwrap_or(86_400)
            .clamp(60, 31_536_000);
        let voice_limit = args
            .get("voice_limit")
            .and_then(Value::as_u64)
            .unwrap_or(200)
            .clamp(1, 1000) as usize;
        let confirmation_fresh_secs = args
            .get("confirmation_fresh_secs")
            .and_then(Value::as_u64)
            .unwrap_or(604_800)
            .clamp(60, 31_536_000);
        let now = dispatch_now_secs().max(0) as u64;
        let records = crate::present::read_outcome_records(
            &crate::present::presentations_dir(),
            voice_limit,
            now.saturating_sub(voice_window_secs),
        );
        Ok(ToolResult::json_text(
            &embodiment_operating_readiness_projection(
                crate::body_telemetry::body_scheduling_advice_snapshot(
                    workload_class,
                    requested_parallelism,
                ),
                voice_delivery_health_projection(&records, now, confirmation_fresh_secs),
            ),
        ))
    }
}

#[async_trait]
impl McpTool for PresentVoiceConfirmAudibilityTool {
    fn name(&self) -> &'static str {
        "present_voice_confirm_audibility"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Persist a HUMAN audibility decision for exactly one existing voice \
                 outcome. Writes a separate append-only outcome sidecar linked by \
                 source_artifact_id and SHA-256; never rewrites machine evidence and never \
                 generalises to future runs. This confirms only the named person's report at \
                 the named playback endpoint, not objective loudness or audio quality. Niche."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "source_artifact_id": {
                        "type": "string",
                        "description": "Exact artifact_id of an existing kind=voice outcome."
                    },
                    "audibility": {
                        "type": "string",
                        "enum": ["confirmed_audible", "confirmed_not_audible", "uncertain"]
                    },
                    "confirmed_by": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 80,
                        "description": "Human identity/role making this report, e.g. owner."
                    },
                    "playback_path": {
                        "type": "string",
                        "enum": ["headphones", "speakers", "other"],
                        "description": "Endpoint through which the human evaluated this run."
                    },
                    "note": {
                        "type": "string",
                        "maxLength": 500,
                        "description": "Optional bounded human observation."
                    },
                    "acknowledge_single_outcome_scope": {
                        "type": "boolean",
                        "description": "Must be true: this decision applies only to source_artifact_id."
                    }
                },
                "required": [
                    "source_artifact_id",
                    "audibility",
                    "confirmed_by",
                    "playback_path",
                    "acknowledge_single_outcome_scope"
                ],
                "additionalProperties": false
            }),
        }
    }

    async fn execute(&self, args: Value, ctx: &ToolContext) -> Result<ToolResult> {
        let source_artifact_id = args
            .get("source_artifact_id")
            .and_then(Value::as_str)
            .unwrap_or("");
        if source_artifact_id.is_empty()
            || source_artifact_id.len() > 160
            || !source_artifact_id
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.'))
        {
            return Ok(ToolResult::error(
                "source_artifact_id must be 1..160 safe ASCII id characters",
            ));
        }
        if args
            .get("acknowledge_single_outcome_scope")
            .and_then(Value::as_bool)
            != Some(true)
        {
            return Ok(ToolResult::error(
                "acknowledge_single_outcome_scope=true is required",
            ));
        }
        let audibility = args.get("audibility").and_then(Value::as_str).unwrap_or("");
        let confirmed_by = args
            .get("confirmed_by")
            .and_then(Value::as_str)
            .unwrap_or("")
            .trim();
        if confirmed_by.is_empty() || confirmed_by.len() > 80 {
            return Ok(ToolResult::error("confirmed_by must be 1..80 characters"));
        }
        let playback_path = args
            .get("playback_path")
            .and_then(Value::as_str)
            .unwrap_or("");
        if !matches!(playback_path, "headphones" | "speakers" | "other") {
            return Ok(ToolResult::error(
                "playback_path must be headphones|speakers|other",
            ));
        }
        let note = args.get("note").and_then(Value::as_str).unwrap_or("");
        if note.len() > 500 {
            return Ok(ToolResult::error("note must be at most 500 characters"));
        }

        let dir = crate::present::presentations_dir();
        let source_path = dir.join(format!(
            "{source_artifact_id}.{}",
            crate::present::OUTCOME_SIDECAR_SUFFIX
        ));
        let source_raw = match std::fs::read_to_string(&source_path) {
            Ok(v) => v,
            Err(e) => {
                return Ok(ToolResult::error(format!(
                    "source voice outcome not found/readable: {e}"
                )))
            }
        };
        let source: Value = match serde_json::from_str(&source_raw) {
            Ok(v) => v,
            Err(e) => {
                return Ok(ToolResult::error(format!(
                    "source voice outcome is malformed JSON: {e}"
                )))
            }
        };
        if source.get("artifact_id").and_then(Value::as_str) != Some(source_artifact_id) {
            return Ok(ToolResult::error(
                "source outcome artifact_id does not match requested id",
            ));
        }
        let digest = Sha256::digest(source_raw.as_bytes());
        let source_digest = digest
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect::<String>();
        let ts = crate::present::now_unix();
        let millis = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis();
        let confirmation_id = format!("{source_artifact_id}.audibility.{millis}");
        let session_id = ctx.session_id.as_ref().map(|s| s.to_string());
        let confirmation = match build_voice_audibility_confirmation(
            &source,
            &source_digest,
            &confirmation_id,
            audibility,
            confirmed_by,
            playback_path,
            note,
            ts,
            session_id.as_deref(),
        ) {
            Ok(v) => v,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        if let Err(e) = crate::present::write_outcome_sidecar(&dir, &confirmation_id, &confirmation)
        {
            return Ok(ToolResult::error(format!(
                "write audibility confirmation failed: {e}"
            )));
        }
        Ok(ToolResult::json_text(&json!({
            "schema": "present_voice_audibility_confirmation/v0",
            "status": "recorded",
            "source_artifact_id": source_artifact_id,
            "source_outcome_unchanged": true,
            "confirmation": confirmation,
            "confirmation_sidecar": format!("{confirmation_id}.{}", crate::present::OUTCOME_SIDECAR_SUFFIX),
        })))
    }
}

pub struct PresentDashboardTool {
    hub: Hub,
}
impl PresentDashboardTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for PresentDashboardTool {
    fn name(&self) -> &'static str {
        "present_dashboard"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Output-expression lane E3 (embodied mirror): render a PERSISTENT \
                 dashboard surface (~/.cache/agent-bridge/presentations/_ab_dashboard.html) that \
                 MIRRORS the present_replay snapshot — the lane's current chain_head, the \
                 count/drift/dual-encoding summary, and a recent-artifacts table — into one stable \
                 browser tab a human keeps open (every call refreshes the same file). Read-only \
                 over present() artifacts (NOT a new source of truth). When verify runs, a headless \
                 probe reads the chain_head the rendered surface shows and compares it to the \
                 lane's CURRENT chain_head, returning embody_status: \
                 embodied|stale|dead|no_browser|error|skipped (stale = the surface is behind the \
                 lane; dead = it rendered nothing / no head — the lane never claims an embodiment \
                 it didn't achieve). The whole snapshot is dual-encoded as #ab-payload for bypass \
                 agents. Degrades to no_browser when no browser is available."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "window_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 86400,
                        "description": "Look-back window for both present calls and artifacts (by provenance ts)."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 200,
                        "description": "Max artifacts scanned (most-recent-first) and present-call rows fetched."
                    },
                    "kind": {
                        "type": "string",
                        "description": "Optional kind filter (table|markdown_table|html|svg|mermaid)."
                    },
                    "title": { "type": "string", "description": "Dashboard document title." },
                    "verify": {
                        "type": "boolean",
                        "default": true,
                        "description": "Self-verify embodiment by loading the dashboard in the browser and comparing the chain_head it renders to the lane's current chain_head (embody_status). Degrades to no_browser when no browser is available."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let window_secs = args
            .get("window_secs")
            .and_then(|v| v.as_i64())
            .unwrap_or(86_400)
            .clamp(60, 31_536_000);
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(200)
            .clamp(1, 500) as usize;
        let kind_filter = args.get("kind").and_then(|v| v.as_str());
        let title = args.get("title").and_then(|v| v.as_str());
        let verify = args.get("verify").and_then(|v| v.as_bool()).unwrap_or(true);

        // Snapshot the lane state the dashboard will mirror, then render + write
        // the stable surface (refreshing the one tab the human keeps open).
        let snapshot =
            match dashboard_replay_snapshot(&store, window_secs, limit, kind_filter).await {
                Ok(s) => s,
                Err(e) => return Ok(ToolResult::error(e)),
            };
        let chain_head = snapshot
            .get("chain_head")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        let dir = crate::present::presentations_dir();
        let path = dir.join(format!("{}.html", crate::present::DASHBOARD_BASENAME));
        let html = crate::present::build_dashboard_html(&snapshot, title);
        if let Err(e) = crate::present::write_artifact_atomic(&path, &html) {
            return Ok(ToolResult::error(format!(
                "present_dashboard: write failed: {e}"
            )));
        }

        // Self-verify embodiment: load the surface, read the chain_head it shows,
        // and compare to the lane's head recomputed NOW (a genuine cross-check —
        // a concurrent present() that landed since the write makes the surface
        // honestly `stale`, not a fault).
        let mut embody_status = crate::present::EmbodyStatus::Skipped;
        let mut embody_detail: Option<String> = None;
        let mut screenshot_path: Option<String> = None;
        if verify {
            if let Err(e) = self.hub.security.check(Cap::Browser) {
                embody_status = crate::present::EmbodyStatus::NoBrowser;
                embody_detail = Some(format!("capability: {e}"));
            } else if let Some(b) = self.hub.browser.clone() {
                let file_url = format!("file://{}", path.display());
                match b.navigate(&file_url).await {
                    Ok(page) => {
                        match b.eval(&page, crate::present::DASHBOARD_READBACK_JS).await {
                            Ok(rv) => {
                                let readback = crate::present::parse_dashboard_readback(&rv);
                                // Compare the rendered head to the lane's CURRENT head,
                                // recomputed NOW — independent of the value we embedded.
                                // If the recompute fails we CANNOT confirm currency, so
                                // report `error` rather than fall back to the embedded
                                // head: comparing the DOM against the value we just
                                // embedded would be a self-fulfilling H==H check that
                                // could dishonestly report `embodied` (the lane never
                                // claims an embodiment it didn't verify).
                                match dashboard_replay_snapshot(
                                    &store,
                                    window_secs,
                                    limit,
                                    kind_filter,
                                )
                                .await
                                {
                                    Ok(s) => {
                                        let expected = s
                                            .get("chain_head")
                                            .and_then(|v| v.as_str())
                                            .unwrap_or("")
                                            .to_string();
                                        embody_status =
                                            crate::present::classify_embody(&readback, &expected);
                                        embody_detail = Some(format!(
                                            "dom_head={} expected_head={} rendered={} rows={}",
                                            short_head(&readback.chain_head),
                                            short_head(&expected),
                                            readback.rendered,
                                            readback.rows
                                        ));
                                    }
                                    Err(e) => {
                                        embody_status = crate::present::EmbodyStatus::Error;
                                        embody_detail = Some(format!(
                                            "verify-time chain_head recompute failed \
                                             (cannot confirm currency): {e}"
                                        ));
                                    }
                                }
                            }
                            Err(e) => {
                                embody_status = crate::present::EmbodyStatus::Error;
                                embody_detail = Some(format!("readback eval: {e}"));
                            }
                        }
                        if let Ok(bytes) = b.screenshot(&page).await {
                            let png =
                                dir.join(format!("{}.png", crate::present::DASHBOARD_BASENAME));
                            if std::fs::write(&png, bytes.as_ref()).is_ok() {
                                screenshot_path = Some(png.display().to_string());
                            }
                        }
                    }
                    Err(e) => {
                        embody_status = crate::present::EmbodyStatus::NoBrowser;
                        embody_detail = Some(format!("navigate: {e}"));
                    }
                }
            } else {
                embody_status = crate::present::EmbodyStatus::NoBrowser;
                embody_detail = Some("no browser backend configured".to_string());
            }
        }

        // Producer-side outcome sidecar: the dashboard is the FIRST producer to
        // populate the embody axis with a REAL value, so its embodiment outcome
        // enters the same queryable, gate-filtered stream as present()
        // (`present_outcomes`). The render axis is derived honestly from the embody
        // outcome (`EmbodyStatus::implied_verify_status`: a Stale surface rendered
        // real content so it's `rendered_ok`, and the `embody_status=stale` rung is
        // what — correctly — makes it ineligible; a Dead surface is `blank`). Only
        // an `embodied` dashboard passes `outcome_gate`; a stale/dead mirror is
        // never minted as a verified outcome. `chain_head` records the lane head the
        // surface mirrors (provenance). Best-effort — a sidecar write failure never
        // fails the call. Single basename → this reflects the LATEST embodiment.
        let dash_verify_method = if !verify {
            "none"
        } else if matches!(embody_status, crate::present::EmbodyStatus::NoBrowser) {
            "no_browser"
        } else {
            "browser_eval"
        };
        let outcome_record = json!({
            "artifact_id": crate::present::DASHBOARD_BASENAME,
            "intent": title.unwrap_or("E3 embodied mirror of the present_replay chain_head"),
            "action_tool": "present_dashboard",
            "kind": "dashboard",
            "verify_status": embody_status.implied_verify_status().as_str(),
            "embody_status": embody_status.as_str(),
            "verify_method": dash_verify_method,
            "chain_head": chain_head,
            "session_id": ctx.session_id.as_ref().map(|s| s.to_string()),
            "ts": crate::present::now_unix(),
        });
        let _ = crate::present::write_outcome_sidecar(
            &dir,
            crate::present::DASHBOARD_BASENAME,
            &outcome_record,
        );

        let result = json!({
            "schema": crate::present::PRESENT_DASHBOARD_SCHEMA,
            "dashboard_path": path.display().to_string(),
            "screenshot_path": screenshot_path,
            "chain_head": chain_head,
            "artifact_count": snapshot.get("artifact_count"),
            "present_calls_logged": snapshot.get("present_calls_logged"),
            "drift": snapshot.get("drift"),
            "dual_encoding_ok": snapshot.get("dual_encoding_ok"),
            "dual_encoding_missing": snapshot.get("dual_encoding_missing"),
            "embody_status": embody_status.as_str(),
            "embody_detail": embody_detail,
            "bytes": html.len(),
        });
        Ok(ToolResult::json_text(&result))
    }
}

/// Host-confirm path B (Linux Computer Use, thread 79): the present-lane decision
/// channel an Approve/Reject card needs. Renders a pending HOST desktop action's
/// summary + confirm token as an interactive card in the daemon's OWN browser, blocks
/// server-side until a human clicks (stamping `#ab-decision`), then reads the verdict
/// back via `eval` — turning a client-side click into a server-side decision with NO
/// new HTTP origin (the E3 readback-from-DOM pattern). It mints NO authority: Approve
/// only matters because the caller then presents the (human-minted, single-use, TTL'd)
/// token to `desktop_confirm`. Additive + isolated in `crate::present_approval` so it
/// does not perturb the present lane's existing one-way `file://` artifacts.
pub struct PresentApprovalTool {
    hub: Hub,
}
impl PresentApprovalTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for PresentApprovalTool {
    fn name(&self) -> &'static str {
        "present_await_decision"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Output-expression lane host-confirm card (path B): render a pending HOST \
                 desktop action (its `summary` + confirm `token`) as an Approve/Reject card in the \
                 daemon's browser and BLOCK until a human clicks, returning decision: \
                 approved|rejected|pending(timeout)|no_browser|error. The click stamps #ab-decision; \
                 the server reads it back via eval (no new HTTP origin). Mints no authority — on \
                 `approved`, call desktop_confirm(token) to execute the action (token is single-use + \
                 TTL'd). Mint the token first via desktop_invoke/desktop_action confirm_host:true. \
                 Degrades to no_browser when no browser is available."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "summary": { "type": "string", "description": "Human-readable description of the pending host action (from the confirm_host pending record's `summary`)." },
                    "token": { "type": "string", "description": "The single-use confirm token minted by desktop_invoke/desktop_action confirm_host:true." },
                    "title": { "type": "string", "description": "Optional card document title." },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 60000, "default": 60000, "description": "How long to block waiting for the human click before returning pending(timeout)." },
                    "simulate": { "type": "string", "enum": ["approve", "reject"], "description": "TEST/DEMO ONLY: stamp the decision via eval (no human). Production omits this. Does not weaken the model — eval-stamp is already possible to any browser-capable agent." }
                },
                "required": ["summary", "token"]
            }),
        }
    }

    async fn execute(&self, args: Value, ctx: &ToolContext) -> Result<ToolResult> {
        let summary = args.get("summary").and_then(|v| v.as_str()).unwrap_or("");
        let token = args.get("token").and_then(|v| v.as_str()).unwrap_or("");
        if summary.is_empty() || token.is_empty() {
            return Ok(present_approval_error(
                "missing_args",
                "both `summary` and `token` are required",
            ));
        }
        let title = args.get("title").and_then(|v| v.as_str());
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(60_000)
            .clamp(1_000, 60_000);
        let simulate = args
            .get("simulate")
            .and_then(|v| v.as_str())
            .filter(|s| *s == "approve" || *s == "reject");

        let html = crate::present_approval::build_approval_html(summary, token, title);
        let dir = crate::present::presentations_dir();
        let safe_token: String = token
            .chars()
            .filter(|c| c.is_ascii_alphanumeric())
            .take(32)
            .collect();
        let path = dir.join(format!("_ab_approval_{safe_token}.html"));
        if let Err(e) = crate::present::write_artifact_atomic(&path, &html) {
            return Ok(present_approval_error(
                "write_failed",
                &format!("could not write approval card: {e}"),
            ));
        }
        let card_path = path.display().to_string();

        // Render the card in the daemon's own browser and block until a human decides.
        if let Err(e) = self.hub.security.check(Cap::Browser) {
            return Ok(present_approval_pending(
                "no_browser",
                token,
                summary,
                &card_path,
                &format!("capability: {e}"),
            ));
        }
        let b = match self.hub.browser.clone() {
            Some(b) => b,
            None => {
                return Ok(present_approval_pending(
                    "no_browser",
                    token,
                    summary,
                    &card_path,
                    "no browser backend configured",
                ))
            }
        };
        let file_url = format!("file://{}", path.display());
        let page = match b.navigate(&file_url).await {
            Ok(p) => p,
            Err(e) => {
                return Ok(present_approval_pending(
                    "no_browser",
                    token,
                    summary,
                    &card_path,
                    &format!("navigate: {e}"),
                ))
            }
        };
        // TEST/DEMO: stamp the decision so the wait_for resolves without a human.
        if let Some(sim) = simulate {
            let _ = b
                .eval(&page, &crate::present_approval::approval_stamp_js(sim))
                .await;
        }
        // Block until #ab-decision is stamped (human click), or timeout.
        let _ = b
            .wait_for(
                &page,
                Some(crate::present_approval::APPROVAL_DECIDED_SELECTOR),
                None,
                timeout_ms,
            )
            .await;
        let readback = match b
            .eval(&page, crate::present_approval::APPROVAL_READBACK_JS)
            .await
        {
            Ok(rv) => crate::present_approval::parse_approval_readback(&rv),
            Err(e) => {
                return Ok(present_approval_error(
                    "readback_failed",
                    &format!("decision readback eval: {e}"),
                ))
            }
        };
        let decision = crate::present_approval::classify_approval(&readback);
        // Provenance (narrows the last-mile: the readback proves the DOM was stamped,
        // not that a HUMAN stamped it — record where/when so the verdict is auditable;
        // who is not provable, the assurance leans on the daemon-owned page + token).
        let page_id = page.to_string();
        let decided_at = crate::present::now_unix();
        // Integrity: the card must have rendered THE token (verdict refers to this action).
        let token_match = readback.token == token;
        let approved = decision.is_approved() && token_match;
        // Tool-level status: a `Pending` that survived the wait_for window is a
        // timeout (fail-closed — never an approval). Dead/Approved/Rejected pass through.
        let decision_status = match decision {
            crate::present_approval::ApprovalDecision::Approved => "approved",
            crate::present_approval::ApprovalDecision::Rejected => "rejected",
            crate::present_approval::ApprovalDecision::Dead => "dead",
            crate::present_approval::ApprovalDecision::Pending => "timed_out",
        };

        // Slice A composition: the verdict IS a verified (intent→action→outcome)
        // record. Emit an outcome sidecar so the approval joins the present_outcomes
        // training-signal stream, where outcome_gate's human-decision axis treats a
        // real decided card (approved|rejected) as eligible and timed_out/dead as
        // rejected. Best-effort; never fails the call.
        let card_id = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_string();
        let outcome = json!({
            "artifact_id": card_id,
            "intent": summary,
            "action_tool": "present_await_decision",
            "kind": "approval",
            "verify_status": "rendered_ok",
            "embody_status": crate::present::EmbodyStatus::NotApplicable.as_str(),
            "decision": decision_status,
            "verify_method": "human_decision",
            "token_match": token_match,
            "page_id": page_id,
            "decided_at": decided_at,
            "session_id": ctx.session_id.as_ref().map(|s| s.to_string()),
            "ts": decided_at,
        });
        let _ = crate::present::write_outcome_sidecar(&dir, &card_id, &outcome);

        let result = json!({
            "schema": crate::present_approval::PRESENT_APPROVAL_SCHEMA,
            "decision": decision_status,
            "approved": approved,
            "token": token,
            "token_match": token_match,
            "page_id": page_id,
            "decided_at": decided_at,
            "summary": summary,
            "card_path": card_path,
            "simulated": simulate.is_some(),
            "next": if approved {
                "approved — call desktop_confirm(token) to execute the action"
            } else {
                "not approved — do NOT execute; the token stays unconsumed"
            }
        });
        Ok(ToolResult::json_text(&result))
    }
}

pub(super) fn present_approval_error(code: &str, message: &str) -> ToolResult {
    let mut r = ToolResult::json_text(&json!({
        "schema": "present_approval_error.v0",
        "status": "error",
        "error": { "code": code, "message": message }
    }));
    r.is_error = true;
    r
}

pub(super) fn present_approval_pending(
    decision: &str,
    token: &str,
    summary: &str,
    card_path: &str,
    detail: &str,
) -> ToolResult {
    ToolResult::json_text(&json!({
        "schema": crate::present_approval::PRESENT_APPROVAL_SCHEMA,
        "decision": decision,
        "approved": false,
        "token": token,
        "summary": summary,
        "card_path": card_path,
        "detail": detail,
        "next": "not approved — do NOT execute; the token stays unconsumed"
    }))
}

/// Output-expression lane Slice A: READ-ONLY, falsifier-gated projection of the
/// `<id>.outcome.json` sidecars present() persists — the verified
/// (intent → action → outcome) training-signal stream. Applies the pure
/// `outcome_gate` (verify_status==rendered_ok and any present embody/interact
/// axis did not fail); `verified_only` (default) surfaces only eligible records
/// while the tallies always reflect the full set. Produces the stream; consuming
/// it (memory ingestion, a learner) is a separate lane's slice.
pub struct PresentOutcomesTool {
    _hub: Hub,
}
impl PresentOutcomesTool {
    pub fn new(hub: Hub) -> Self {
        Self { _hub: hub }
    }
}

#[async_trait]
impl McpTool for PresentOutcomesTool {
    fn name(&self) -> &'static str {
        "present_outcomes"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Output-expression lane Slice A: READ-ONLY, falsifier-gated stream of \
                 verified (intent → action → outcome) records. Reads the `<id>.outcome.json` \
                 sidecars present() writes after self-verify and applies the outcome gate \
                 (eligible iff verify_status=rendered_ok AND any present embodiment/interactivity \
                 axis did not fail). With verified_only=true (default) only eligible records are \
                 surfaced, but eligible_count/rejected_count ALWAYS reflect the full set (a \
                 consumer never mistakes a filtered list for 'all verified'). Each surfaced record \
                 carries eligible + gate_reason. This is the training-signal stream a downstream \
                 consumer (memory ingestion, a learner) would read; it never claims a verified \
                 label it didn't earn."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "window_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 86400,
                        "description": "Look-back window over outcome records (by ts)."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "default": 200,
                        "description": "Max records scanned (most-recent-first)."
                    },
                    "verified_only": {
                        "type": "boolean",
                        "default": true,
                        "description": "When true, surface only gate-eligible (verified) records; tallies still reflect the full set. False surfaces all records annotated with eligible + gate_reason."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let window_secs = args
            .get("window_secs")
            .and_then(|v| v.as_i64())
            .unwrap_or(86_400)
            .clamp(60, 31_536_000);
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(200)
            .clamp(1, 1000) as usize;
        let verified_only = args
            .get("verified_only")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        let now = dispatch_now_secs();
        let cutoff = now.saturating_sub(window_secs).max(0) as u64;
        let dir = crate::present::presentations_dir();
        let records = crate::present::read_outcome_records(&dir, limit, cutoff);
        let mut projection = crate::present::present_outcomes_projection(&records, verified_only);
        if let Some(obj) = projection.as_object_mut() {
            let confirmations = latest_voice_audibility_by_source(&records);
            let confirmation_count = confirmations
                .as_object()
                .map(|rows| rows.len())
                .unwrap_or_default();
            obj.insert("schema".into(), json!("present_outcomes/v0"));
            obj.insert("dir".into(), json!(dir.display().to_string()));
            obj.insert("window_secs".into(), json!(window_secs));
            obj.insert("generated_at".into(), json!(now.max(0)));
            obj.insert(
                "voice_audibility_confirmation_count".into(),
                json!(confirmation_count),
            );
            obj.insert("voice_audibility_by_source".into(), confirmations);
        }
        Ok(ToolResult::json_text(&projection))
    }
}

/// LSWR Step E2: READ-ONLY admission projection over Step D present artifacts.
///
/// Reads persisted `present` HTML artifacts, filters to dual-encoded LSWR Step D
/// packets, applies the pure Step E1 classifier, and reports class/reason
/// counts. Writes nothing and never calls the #94 ingestion path.
pub struct LswrOutcomeAdmissionsTool {
    _hub: Hub,
}
impl LswrOutcomeAdmissionsTool {
    pub fn new(hub: Hub) -> Self {
        Self { _hub: hub }
    }
}

#[async_trait]
impl McpTool for LswrOutcomeAdmissionsTool {
    fn name(&self) -> &'static str {
        "lswr_outcome_admissions"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "LSWR Step E2: READ-ONLY projection over persisted Step D present \
                 artifacts. Scans the present() artifact directory for HTML artifacts carrying \
                 `agent_bridge.lswr.present_packet.v0`, applies the pure Step E admission \
                 classifier, and reports training_eligible/audit_only/rejected counts + reasons. \
                 Writes nothing, calls no memory tools, and never invokes present_outcomes_ingest."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "window_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 86400,
                        "description": "Look-back window over present artifacts by provenance timestamp."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 200,
                        "description": "Max HTML artifacts scanned (most-recent-first before timestamp filtering)."
                    },
                    "eligible_only": {
                        "type": "boolean",
                        "default": false,
                        "description": "When true, return only training_eligible admissions while summary counts still cover all scanned LSWR artifacts."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let window_secs = args
            .get("window_secs")
            .and_then(|v| v.as_i64())
            .unwrap_or(86_400)
            .clamp(60, 31_536_000);
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(200)
            .clamp(1, 500) as usize;
        let eligible_only = args
            .get("eligible_only")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        let now = dispatch_now_secs();
        let cutoff = now.saturating_sub(window_secs).max(0) as u64;
        let dir = crate::present::presentations_dir();
        let artifacts: Vec<_> = crate::present::list_artifacts(&dir, limit, Some("html"))
            .into_iter()
            .filter(|a| a.ts.map_or(true, |t| t >= cutoff))
            .collect();
        let mut projection = crate::lswr_outcome_admission::outcome_admissions_projection(
            &artifacts,
            eligible_only,
            now.max(0) as u64,
            window_secs as u64,
        );
        if let Some(obj) = projection.as_object_mut() {
            obj.insert("dir".into(), json!(dir.display().to_string()));
            obj.insert("limit".into(), json!(limit));
        }
        Ok(ToolResult::json_text(&projection))
    }
}

/// LSWR Step E3: DRY-RUN adapter from E2 admissions to #94 present_outcome rows.
///
/// This tool deliberately exposes no write flag. It computes the same
/// training_eligible admission projection as E2, then returns the planned
/// memory rows that a future explicit ingest step could persist.
pub struct LswrOutcomeAdmissionsDryRunTool {
    _hub: Hub,
}
impl LswrOutcomeAdmissionsDryRunTool {
    pub fn new(hub: Hub) -> Self {
        Self { _hub: hub }
    }
}

#[async_trait]
impl McpTool for LswrOutcomeAdmissionsDryRunTool {
    fn name(&self) -> &'static str {
        "lswr_outcome_admissions_dry_run"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "LSWR Step E3: DRY-RUN-ONLY adapter from Step E2 \
                 training_eligible admissions to #94-compatible present_outcome memory \
                 candidates. Scans persisted LSWR Step D present artifacts, classifies \
                 admissions, filters to training_eligible only, and returns the would-write \
                 rows with deterministic key/kind/scope/tags/content. Writes nothing, exposes \
                 no dry_run=false switch, calls no memory_save, and never invokes \
                 present_outcomes_ingest."
                .into(),
            input_schema: json!({
                "type": "object",
                "additionalProperties": false,
                "properties": {
                    "window_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 86400,
                        "description": "Look-back window over present artifacts by provenance timestamp."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 200,
                        "description": "Max HTML artifacts scanned (most-recent-first before timestamp filtering)."
                    },
                    "max_candidates": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 25,
                        "description": "Hard cap on planned present_outcome candidate rows returned by this dry run."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let window_secs = args
            .get("window_secs")
            .and_then(|v| v.as_i64())
            .unwrap_or(86_400)
            .clamp(60, 31_536_000);
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(200)
            .clamp(1, 500) as usize;
        let max_candidates = args
            .get("max_candidates")
            .and_then(|v| v.as_u64())
            .unwrap_or(25)
            .clamp(1, 200) as usize;

        let now = dispatch_now_secs();
        let cutoff = now.saturating_sub(window_secs).max(0) as u64;
        let dir = crate::present::presentations_dir();
        let artifacts: Vec<_> = crate::present::list_artifacts(&dir, limit, Some("html"))
            .into_iter()
            .filter(|a| a.ts.map_or(true, |t| t >= cutoff))
            .collect();
        let projection = crate::lswr_outcome_admission::outcome_admissions_projection(
            &artifacts,
            false,
            now.max(0) as u64,
            window_secs as u64,
        );
        let admissions: Vec<Value> = projection
            .get("admissions")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let mut dry_run = crate::lswr_outcome_admission::outcome_admission_dry_run_candidates(
            &admissions,
            now.max(0) as u64,
            window_secs as u64,
            max_candidates,
        );
        if let Some(obj) = dry_run.as_object_mut() {
            obj.insert("dir".into(), json!(dir.display().to_string()));
            obj.insert("limit".into(), json!(limit));
            for key in [
                "scanned_artifacts",
                "skipped_non_lswr_count",
                "artifact_read_error_count",
                "lswr_artifact_count",
                "audit_only_count",
                "rejected_count",
                "reason_counts",
            ] {
                if let Some(value) = projection.get(key) {
                    obj.insert(key.into(), value.clone());
                }
            }
        }
        Ok(ToolResult::json_text(&dry_run))
    }
}

/// LSWR Step E4c: READ-ONLY approval packet over the E3 dry-run plan.
///
/// This tool deliberately exposes no write mode. It computes the E3 dry-run
/// candidates, canonicalizes them into an approval packet with a stable plan
/// hash, and optionally marks currently active outcome rows via non-mutating
/// `memory_search` probes.
pub struct LswrOutcomeAdmissionsApprovalPacketTool {
    hub: Hub,
}
impl LswrOutcomeAdmissionsApprovalPacketTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for LswrOutcomeAdmissionsApprovalPacketTool {
    fn name(&self) -> &'static str {
        "lswr_outcome_admissions_approval_packet"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "LSWR Step E4c: READ-ONLY approval packet over the E3 dry-run \
                 candidate plan. Scans persisted LSWR Step D present artifacts, reuses \
                 the E2/E3 gates, computes a stable sha256 plan_hash over canonical \
                 candidate rows, and reports active_row_exists using non-mutating \
                 memory_search probes when a store is configured. Writes nothing, exposes \
                 no dry_run=false or max_writes switch, calls no memory_save, and never \
                 invokes present_outcomes_ingest."
                .into(),
            input_schema: json!({
                "type": "object",
                "additionalProperties": false,
                "properties": {
                    "window_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 86400,
                        "description": "Look-back window over present artifacts by provenance timestamp."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 200,
                        "description": "Max HTML artifacts scanned (most-recent-first before timestamp filtering)."
                    },
                    "max_candidates": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 25,
                        "description": "Hard cap on planned present_outcome candidate rows included in the review packet."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let window_secs = args
            .get("window_secs")
            .and_then(|v| v.as_i64())
            .unwrap_or(86_400)
            .clamp(60, 31_536_000);
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(200)
            .clamp(1, 500) as usize;
        let max_candidates = args
            .get("max_candidates")
            .and_then(|v| v.as_u64())
            .unwrap_or(25)
            .clamp(1, 200) as usize;

        let now = dispatch_now_secs();
        let cutoff = now.saturating_sub(window_secs).max(0) as u64;
        let dir = crate::present::presentations_dir();
        let artifacts: Vec<_> = crate::present::list_artifacts(&dir, limit, Some("html"))
            .into_iter()
            .filter(|a| a.ts.map_or(true, |t| t >= cutoff))
            .collect();
        let projection = crate::lswr_outcome_admission::outcome_admissions_projection(
            &artifacts,
            false,
            now.max(0) as u64,
            window_secs as u64,
        );
        let admissions: Vec<Value> = projection
            .get("admissions")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let dry_run = crate::lswr_outcome_admission::outcome_admission_dry_run_candidates(
            &admissions,
            now.max(0) as u64,
            window_secs as u64,
            max_candidates,
        );

        let active_rows = if let Some(store) = &self.hub.store {
            let keys: Vec<String> = dry_run
                .get("candidates")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .filter_map(|candidate| {
                    candidate
                        .get("memory")
                        .and_then(|m| m.get("key"))
                        .and_then(Value::as_str)
                        .map(str::to_string)
                })
                .collect();
            let mut active = BTreeSet::new();
            for key in keys {
                let exists = store
                    .memory_search(&key, &[], 5)
                    .await
                    .unwrap_or_default()
                    .iter()
                    .any(|hit| hit.record.key == key);
                if exists {
                    active.insert(key);
                }
            }
            Some(active)
        } else {
            None
        };

        let mut plan = crate::lswr_outcome_admission::outcome_admission_ingest_plan_from_dry_run(
            &dry_run,
            now.max(0) as u64,
            active_rows.as_ref(),
        );
        if let Some(obj) = plan.as_object_mut() {
            obj.insert("dir".into(), json!(dir.display().to_string()));
            obj.insert("limit".into(), json!(limit));
            obj.insert("max_candidates".into(), json!(max_candidates));
            obj.insert(
                "store_probe".into(),
                json!(if active_rows.is_some() {
                    "memory_search_active_only"
                } else {
                    "store_unavailable"
                }),
            );
            for key in [
                "scanned_artifacts",
                "skipped_non_lswr_count",
                "artifact_read_error_count",
                "lswr_artifact_count",
                "training_eligible_count",
                "audit_only_count",
                "rejected_count",
                "reason_counts",
            ] {
                if let Some(value) = projection.get(key) {
                    obj.insert(key.into(), value.clone());
                }
            }
        }
        Ok(ToolResult::json_text(&plan))
    }
}

/// LSWR Step E4d preflight: READ-ONLY validation of a future write request.
///
/// This tool intentionally is not the writer. It recomputes the E4c plan,
/// validates an operator-supplied future write request against that plan, and
/// always returns `writes_state=false`.
pub struct LswrOutcomeAdmissionsWritePreflightTool {
    hub: Hub,
}
impl LswrOutcomeAdmissionsWritePreflightTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for LswrOutcomeAdmissionsWritePreflightTool {
    fn name(&self) -> &'static str {
        "lswr_outcome_admissions_write_preflight"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "LSWR Step E4d: READ-ONLY write-request preflight over a \
                 recomputed E4c approval packet. Accepts a proposed future \
                 lswr_outcome_admissions_ingest request object, validates confirmation, \
                 approval anchor, reviewed plan_hash, candidate keys, first-slice cap, \
                 and active-row status, but writes nothing, exposes no executable writer, \
                 calls no memory_save, and never invokes present_outcomes_ingest."
                .into(),
            input_schema: json!({
                "type": "object",
                "additionalProperties": false,
                "properties": {
                    "window_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 86400,
                        "description": "Look-back window over present artifacts by provenance timestamp; used to recompute the E4c plan."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 200,
                        "description": "Max HTML artifacts scanned (most-recent-first before timestamp filtering)."
                    },
                    "max_candidates": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 25,
                        "description": "Hard cap on planned present_outcome candidate rows included in the recomputed E4c plan."
                    },
                    "request": {
                        "type": "object",
                        "additionalProperties": false,
                        "description": "Proposed future writer request to validate; this preflight tool never executes it.",
                        "properties": {
                            "dry_run": {
                                "type": "boolean",
                                "const": false,
                                "description": "Must be false in the future writer request shape; the preflight result itself still writes nothing."
                            },
                            "apply_confirmation": {
                                "type": "string",
                                "const": crate::lswr_outcome_admission::LSWR_OUTCOME_ADMISSION_WRITE_CONFIRMATION,
                                "description": "Exact confirmation token required before any future writer can be implemented."
                            },
                            "approval_thread_id": {
                                "type": "integer",
                                "const": crate::lswr_outcome_admission::LSWR_OUTCOME_ADMISSION_APPROVAL_THREAD_ID,
                                "description": "Board thread that must contain the owner approval post."
                            },
                            "approval_post_id": {
                                "type": "integer",
                                "minimum": 1,
                                "description": "Positive owner approval post id; zero or missing is invalid."
                            },
                            "reviewed_plan_hash": {
                                "type": "string",
                                "pattern": "^sha256:[0-9a-f]{64}$",
                                "description": "Plan hash from the reviewed E4c approval packet."
                            },
                            "candidate_keys": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string"},
                                "description": "Subset of candidate keys selected from the reviewed E4c plan."
                            },
                            "max_writes": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 1,
                                "description": "First E4d slice cap; must be 1 or less."
                            }
                        }
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let window_secs = args
            .get("window_secs")
            .and_then(|v| v.as_i64())
            .unwrap_or(86_400)
            .clamp(60, 31_536_000);
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(200)
            .clamp(1, 500) as usize;
        let max_candidates = args
            .get("max_candidates")
            .and_then(|v| v.as_u64())
            .unwrap_or(25)
            .clamp(1, 200) as usize;
        let request = args.get("request").cloned().unwrap_or(Value::Null);

        let now = dispatch_now_secs();
        let cutoff = now.saturating_sub(window_secs).max(0) as u64;
        let dir = crate::present::presentations_dir();
        let artifacts: Vec<_> = crate::present::list_artifacts(&dir, limit, Some("html"))
            .into_iter()
            .filter(|a| a.ts.map_or(true, |t| t >= cutoff))
            .collect();
        let projection = crate::lswr_outcome_admission::outcome_admissions_projection(
            &artifacts,
            false,
            now.max(0) as u64,
            window_secs as u64,
        );
        let admissions: Vec<Value> = projection
            .get("admissions")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let dry_run = crate::lswr_outcome_admission::outcome_admission_dry_run_candidates(
            &admissions,
            now.max(0) as u64,
            window_secs as u64,
            max_candidates,
        );

        let active_rows = if let Some(store) = &self.hub.store {
            let keys: Vec<String> = dry_run
                .get("candidates")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .filter_map(|candidate| {
                    candidate
                        .get("memory")
                        .and_then(|m| m.get("key"))
                        .and_then(Value::as_str)
                        .map(str::to_string)
                })
                .collect();
            let mut active = BTreeSet::new();
            for key in keys {
                let exists = store
                    .memory_search(&key, &[], 5)
                    .await
                    .unwrap_or_default()
                    .iter()
                    .any(|hit| hit.record.key == key);
                if exists {
                    active.insert(key);
                }
            }
            Some(active)
        } else {
            None
        };

        let plan = crate::lswr_outcome_admission::outcome_admission_ingest_plan_from_dry_run(
            &dry_run,
            now.max(0) as u64,
            active_rows.as_ref(),
        );
        let mut validation =
            crate::lswr_outcome_admission::validate_lswr_e4d_write_request(&plan, &request);
        if let Some(obj) = validation.as_object_mut() {
            obj.insert("dir".into(), json!(dir.display().to_string()));
            obj.insert("limit".into(), json!(limit));
            obj.insert("max_candidates".into(), json!(max_candidates));
            obj.insert(
                "store_probe".into(),
                json!(if active_rows.is_some() {
                    "memory_search_active_only"
                } else {
                    "store_unavailable"
                }),
            );
            obj.insert(
                "approval_packet".into(),
                json!({
                    "schema": plan.get("schema").cloned().unwrap_or(Value::Null),
                    "candidate_count": plan.get("candidate_count").cloned().unwrap_or(Value::Null),
                    "candidate_keys": plan.get("candidate_keys").cloned().unwrap_or(Value::Null),
                    "active_row_check": plan.get("active_row_check").cloned().unwrap_or(Value::Null),
                    "active_row_exists_count": plan.get("active_row_exists_count").cloned().unwrap_or(Value::Null),
                    "plan_hash": plan.get("plan_hash").cloned().unwrap_or(Value::Null),
                    "writes_state": plan.get("writes_state").cloned().unwrap_or(Value::Null),
                    "write_tool_open": plan.get("write_tool_open").cloned().unwrap_or(Value::Null),
                }),
            );
            for key in [
                "scanned_artifacts",
                "skipped_non_lswr_count",
                "artifact_read_error_count",
                "lswr_artifact_count",
                "training_eligible_count",
                "audit_only_count",
                "rejected_count",
                "reason_counts",
            ] {
                if let Some(value) = projection.get(key) {
                    obj.insert(key.into(), value.clone());
                }
            }
        }
        Ok(ToolResult::json_text(&validation))
    }
}

/// LSWR Step E4d/E4e explicit write tool: `lswr_outcome_admissions_ingest`.
///
/// This is the FIRST and ONLY LSWR outcome-admission writer. It is a thin,
/// owner-gated consumer of the E3 candidate builder + the E4d validator. It does
/// NOT reimplement any LSWR admission gate and it NEVER calls
/// `present_outcomes_ingest`. Default mode is `dry_run=true` (returns the E4c
/// approval plan + `plan_hash`, writes nothing). A durable write additionally
/// requires `dry_run=false` PLUS the full owner approval contract validated by
/// [`validate_lswr_e4d_write_request`]: `apply_confirmation`,
/// `approval_thread_id=102`, a positive `approval_post_id`, a `reviewed_plan_hash`
/// equal to the recomputed plan hash, `candidate_keys` ⊆ plan, `max_writes<=1`,
/// and every selected row `active_row_exists=false` / `write_allowed=false` /
/// `requires_review=true`.
///
/// Write semantics (design §5/§6): persists exactly the [`MemoryRecord`] produced
/// by [`crate::present_ingest::build_outcome_memory`] for the SAME `outcome_record`
/// the reviewed plan hash covered; re-probes and REFUSES active-row refreshes (the
/// first slice creates a new deterministic row or does nothing); returns a
/// rollback packet. all-profile only; hidden from standard and codex-essential.
/// See `docs/design/LIVE_SEMANTIC_WORLD_RUNTIME_STEP_E4_MANUAL_OPT_IN_WRITE_DESIGN_2026_06_15.md`.
pub struct LswrOutcomeAdmissionsIngestTool {
    hub: Hub,
}
impl LswrOutcomeAdmissionsIngestTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for LswrOutcomeAdmissionsIngestTool {
    fn name(&self) -> &'static str {
        "lswr_outcome_admissions_ingest"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "LSWR Step E4d/E4e: owner-gated explicit writer that persists a \
                 training_eligible LSWR outcome admission as a single ordinary present_outcome \
                 memory row (key=outcome_<artifact_id>, kind=present_outcome, \
                 scope=outcome:<artifact_id>, related_keys=[]). Thin consumer of the E3 \
                 candidate builder + E4d validator: never reimplements admission gates, never \
                 calls present_outcomes_ingest, never creates graph edges. dry_run=TRUE by \
                 DEFAULT — returns the E4c plan (plan_hash + candidate_keys) and writes NOTHING. \
                 A durable write requires dry_run=false AND the full owner approval contract: \
                 apply_confirmation, approval_thread_id=102, a positive approval_post_id, \
                 reviewed_plan_hash == the recomputed plan_hash, candidate_keys subset of plan, \
                 and max_writes<=1. Fails closed (no memory_save; the only store access is a \
                 non-mutating active-row probe) on any contract violation. \
                 Refuses active-row refreshes; returns a rollback packet. all-profile only; \
                 hidden from standard and codex-essential. Not automatic — a human triggers it."
                .into(),
            input_schema: json!({
                "type": "object",
                "additionalProperties": false,
                "properties": {
                    "window_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 86400,
                        "description": "Look-back window over present artifacts by provenance timestamp; used to recompute the E4c plan."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 200,
                        "description": "Max HTML artifacts scanned (most-recent-first before timestamp filtering)."
                    },
                    "max_candidates": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 25,
                        "description": "Hard cap on planned present_outcome candidate rows in the recomputed E4c plan."
                    },
                    "dry_run": {
                        "type": "boolean",
                        "default": true,
                        "description": "TRUE (default) returns the E4c plan + plan_hash and writes NOTHING. Set false to attempt a durable write (requires the full approval contract below)."
                    },
                    "apply_confirmation": {
                        "type": "string",
                        "const": crate::lswr_outcome_admission::LSWR_OUTCOME_ADMISSION_WRITE_CONFIRMATION,
                        "description": "Exact confirmation token; required for any write."
                    },
                    "approval_thread_id": {
                        "type": "integer",
                        "const": crate::lswr_outcome_admission::LSWR_OUTCOME_ADMISSION_APPROVAL_THREAD_ID,
                        "description": "Board thread that contains the owner approval post."
                    },
                    "approval_post_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Positive owner approval post id; zero or missing is invalid."
                    },
                    "reviewed_plan_hash": {
                        "type": "string",
                        "pattern": "^sha256:[0-9a-f]{64}$",
                        "description": "Plan hash from the reviewed E4c approval packet; must equal the recomputed plan_hash."
                    },
                    "candidate_keys": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                        "description": "Subset of candidate keys selected from the reviewed E4c plan."
                    },
                    "max_writes": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1,
                        "description": "First E4 slice cap; must be 1 or less."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let window_secs = args
            .get("window_secs")
            .and_then(|v| v.as_i64())
            .unwrap_or(86_400)
            .clamp(60, 31_536_000);
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(200)
            .clamp(1, 500) as usize;
        let max_candidates = args
            .get("max_candidates")
            .and_then(|v| v.as_u64())
            .unwrap_or(25)
            .clamp(1, 200) as usize;
        let dry_run = args
            .get("dry_run")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        let now = dispatch_now_secs();
        let cutoff = now.saturating_sub(window_secs).max(0) as u64;
        let dir = crate::present::presentations_dir();
        let artifacts: Vec<_> = crate::present::list_artifacts(&dir, limit, Some("html"))
            .into_iter()
            .filter(|a| a.ts.map_or(true, |t| t >= cutoff))
            .collect();
        let projection = crate::lswr_outcome_admission::outcome_admissions_projection(
            &artifacts,
            false,
            now.max(0) as u64,
            window_secs as u64,
        );
        let admissions: Vec<Value> = projection
            .get("admissions")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let dry_run_candidates =
            crate::lswr_outcome_admission::outcome_admission_dry_run_candidates(
                &admissions,
                now.max(0) as u64,
                window_secs as u64,
                max_candidates,
            );

        // Non-mutating active-row probe (identical to the E4c/E4d read-only path).
        let store_opt = self.hub.store.clone();
        let active_rows = if let Some(store) = &store_opt {
            let keys: Vec<String> = dry_run_candidates
                .get("candidates")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .filter_map(|candidate| {
                    candidate
                        .get("memory")
                        .and_then(|m| m.get("key"))
                        .and_then(Value::as_str)
                        .map(str::to_string)
                })
                .collect();
            let mut active = BTreeSet::new();
            for key in keys {
                let exists = store
                    .memory_search(&key, &[], 5)
                    .await
                    .unwrap_or_default()
                    .iter()
                    .any(|hit| hit.record.key == key);
                if exists {
                    active.insert(key);
                }
            }
            Some(active)
        } else {
            None
        };

        let plan = crate::lswr_outcome_admission::outcome_admission_ingest_plan_from_dry_run(
            &dry_run_candidates,
            now.max(0) as u64,
            active_rows.as_ref(),
        );

        // DEFAULT dry-run: return the E4c approval plan; write nothing.
        if dry_run {
            let mut out = plan.clone();
            if let Some(obj) = out.as_object_mut() {
                obj.insert("dir".into(), json!(dir.display().to_string()));
                obj.insert(
                    "store_probe".into(),
                    json!(if active_rows.is_some() {
                        "memory_search_active_only"
                    } else {
                        "store_unavailable"
                    }),
                );
                obj.insert(
                    "note".into(),
                    json!(
                        "dry-run (default): read plan_hash + candidate_keys, then call again \
                         with dry_run:false + apply_confirmation + approval_thread_id:102 + \
                         approval_post_id + reviewed_plan_hash + candidate_keys + max_writes:1 \
                         to persist exactly one present_outcome row. Nothing written."
                    ),
                );
            }
            return Ok(ToolResult::json_text(&out));
        }

        // WRITE MODE. Re-pack the flat args into the validator's request object and
        // fail closed before any store access unless the full contract holds.
        let request = json!({
            "dry_run": false,
            "apply_confirmation": args.get("apply_confirmation").cloned().unwrap_or(Value::Null),
            "approval_thread_id": args.get("approval_thread_id").cloned().unwrap_or(Value::Null),
            "approval_post_id": args.get("approval_post_id").cloned().unwrap_or(Value::Null),
            "reviewed_plan_hash": args.get("reviewed_plan_hash").cloned().unwrap_or(Value::Null),
            "candidate_keys": args.get("candidate_keys").cloned().unwrap_or(Value::Null),
            "max_writes": args.get("max_writes").cloned().unwrap_or(Value::Null),
        });
        let validation =
            crate::lswr_outcome_admission::validate_lswr_e4d_write_request(&plan, &request);
        let valid = validation.get("valid").and_then(Value::as_bool) == Some(true);
        if !valid {
            let mut out = validation.clone();
            if let Some(obj) = out.as_object_mut() {
                obj.insert("writes_state".into(), json!(false));
                obj.insert("written_count".into(), json!(0));
                obj.insert(
                    "note".into(),
                    json!("write refused: request failed E4d validation; no memory_save performed (the only prior store access is a non-mutating active-row probe)."),
                );
            }
            return Ok(ToolResult::json_text(&out));
        }

        let store = match &store_opt {
            Some(s) => s.clone(),
            None => {
                return Ok(ToolResult::json_text(&json!({
                    "schema": crate::lswr_outcome_admission::LSWR_OUTCOME_ADMISSION_WRITE_RESULT_SCHEMA,
                    "valid": true,
                    "dry_run": false,
                    "writes_state": false,
                    "written_count": 0,
                    "failure_reasons": ["no_store_configured"],
                    "note": "valid request but no store configured; nothing written.",
                })))
            }
        };

        // Map each selected key back to the SAME outcome_record the plan hash covered,
        // then rebuild the durable MemoryRecord via the #94 helper (design §5).
        let candidates: Vec<Value> = dry_run_candidates
            .get("candidates")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let max_writes = request
            .get("max_writes")
            .and_then(Value::as_u64)
            .unwrap_or(1) as usize;
        let selected_keys: Vec<String> = request
            .get("candidate_keys")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(|k| k.as_str().map(str::to_string))
            .collect();

        let mut written: Vec<Value> = Vec::new();
        let mut written_keys: Vec<String> = Vec::new();
        let mut refused: Vec<Value> = Vec::new();
        let mut write_count = 0usize;

        for key in &selected_keys {
            if write_count >= max_writes {
                refused.push(json!({"key": key, "reason": "over_max_writes"}));
                continue;
            }
            let Some(candidate) = candidates.iter().find(|c| {
                c.get("memory")
                    .and_then(|m| m.get("key"))
                    .and_then(Value::as_str)
                    == Some(key.as_str())
            }) else {
                refused.push(json!({"key": key, "reason": "candidate_not_found_at_write"}));
                continue;
            };
            let outcome_record = candidate
                .get("outcome_record")
                .cloned()
                .unwrap_or(Value::Null);
            let Some(mem) =
                crate::present_ingest::build_outcome_memory(&outcome_record, now.max(0))
            else {
                refused.push(json!({"key": key, "reason": "unbuildable_at_write"}));
                continue;
            };
            if mem.key != *key {
                refused.push(
                    json!({"key": key, "reason": "rebuilt_key_mismatch", "rebuilt_key": mem.key}),
                );
                continue;
            }
            // Re-probe right before write; first slice refuses an active-row refresh.
            let active_now = store
                .memory_search(&mem.key, &[], 5)
                .await
                .unwrap_or_default()
                .iter()
                .any(|h| h.record.key == mem.key);
            if active_now {
                refused.push(json!({"key": key, "reason": "active_row_exists_at_write"}));
                continue;
            }
            match store.memory_save(&mem).await {
                Ok(()) => {
                    write_count += 1;
                    written_keys.push(mem.key.clone());
                    written.push(json!({
                        "key": mem.key,
                        "kind": mem.kind,
                        "scope": mem.scope,
                        "tags": mem.tags,
                        "written": true,
                    }));
                }
                Err(e) => {
                    refused
                        .push(json!({"key": key, "reason": "store_error", "error": e.to_string()}));
                }
            }
        }

        let plan_hash = plan.get("plan_hash").cloned().unwrap_or(Value::Null);
        let approval_post_id = request
            .get("approval_post_id")
            .cloned()
            .unwrap_or(Value::Null);
        let writes_state = !written_keys.is_empty();
        let rollback = if writes_state {
            json!({
                "schema": crate::lswr_outcome_admission::LSWR_OUTCOME_ADMISSION_INGEST_ROLLBACK_SCHEMA,
                "approval_post_id": approval_post_id,
                "plan_hash": plan_hash,
                "written_keys": written_keys,
                "rollback_instruction": "tombstone these exact keys through the existing memory admin path",
            })
        } else {
            Value::Null
        };

        Ok(ToolResult::json_text(&json!({
            "schema": crate::lswr_outcome_admission::LSWR_OUTCOME_ADMISSION_WRITE_RESULT_SCHEMA,
            "valid": true,
            "dry_run": false,
            "writes_state": writes_state,
            "generated_at": now.max(0),
            "plan_hash": plan_hash,
            "approval_thread_id": crate::lswr_outcome_admission::LSWR_OUTCOME_ADMISSION_APPROVAL_THREAD_ID,
            "approval_post_id": approval_post_id,
            "max_writes": max_writes,
            "selected_count": selected_keys.len(),
            "written_count": write_count,
            "written": written,
            "written_keys": written_keys,
            "refused": refused,
            "rollback": rollback,
            "memory_kind": crate::present_ingest::OUTCOME_MEMORY_KIND,
            "store_probe": "memory_search_active_only",
            "note": "E4 first-slice write: persists exactly the build_outcome_memory row(s) the \
                     reviewed plan_hash covered; active-row refreshes refused; no \
                     present_outcomes_ingest call; the rollback packet is operator guidance, \
                     not an automatic undo.",
        })))
    }
}

// ── Output-expression lane Slice B (v0) ───────────────────────────────────
// Two tools: a read-only outcome→memory drift projection (always-on, zero
// risk, zero owner coordination), and an opt-in, dry-run-default, capped
// ingestion that closes the loop on explicit operator action. See
// present_ingest.rs for the write-path-hazard analysis.

/// **Slice B read-only projection** — `outcomes_memory_drift`. Reports which
/// gate-verified outcomes are vs are NOT already represented in memory, as a
/// tamper-evident SHA-256-chained snapshot. Writes nothing; the representation
/// probe uses the store's non-mutating `memory_search` (NEVER `memory_get`,
/// which bumps access_count/last_accessed_at). Mirrors PresentReplayTool wiring.
pub struct OutcomesMemoryDriftTool {
    hub: Hub,
}
impl OutcomesMemoryDriftTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for OutcomesMemoryDriftTool {
    fn name(&self) -> &'static str {
        "outcomes_memory_drift"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Output-expression lane Slice B (v0): READ-ONLY outcome→memory drift \
                 projection. Reads the verified (intent→action→outcome) stream (the same \
                 gate-eligible records as present_outcomes(verified_only=true)) and, for each, \
                 probes existing memory READ-ONLY (via non-mutating memory_search) to report \
                 which verified outcomes are already represented vs missing. `drift` == \
                 `missing_count` is the literal size of the open output→memory loop. Output is \
                 a tamper-evident SHA-256 hash chain (reorder/loss changes chain_head). Each \
                 missing record also carries the `proposed_*` candidate a future opt-in ingest \
                 would persist — as REPORT DATA ONLY; this tool writes nothing. It cannot \
                 self-fulfill (representation is decided by querying memory it never authored)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "window_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 86400,
                        "description": "Look-back window over outcome records (by ts)."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "default": 200,
                        "description": "Max outcome records scanned (most-recent-first)."
                    },
                    "probe_limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 5,
                        "description": "Max memory hits fetched per representation probe."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let window_secs = args
            .get("window_secs")
            .and_then(|v| v.as_i64())
            .unwrap_or(86_400)
            .clamp(60, 31_536_000);
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(200)
            .clamp(1, 1000) as usize;
        let probe_limit = args
            .get("probe_limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(5)
            .clamp(1, 50) as u32;

        let now = dispatch_now_secs();
        let cutoff = now.saturating_sub(window_secs).max(0) as u64;
        let dir = crate::present::presentations_dir();
        let records = crate::present::read_outcome_records(&dir, limit, cutoff);
        // Gate is inherited transitively — only eligible (verified) records flow on.
        let projection = crate::present::present_outcomes_projection(&records, true);
        let verified: Vec<Value> = projection
            .get("outcomes")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();

        // Read-only representation probe: for each verified artifact_id, search
        // memory (memory_search is NON-MUTATING, unlike memory_get). STRICT
        // semantics (review fix): "represented" means the DETERMINISTIC outcome
        // row exists — a hit whose key == outcome_<artifact_id> — so drift ==
        // missing_count equals exactly the writes the ingest tool would make
        // (same exact-key predicate). A mere substring mention in some unrelated
        // memory body no longer counts as represented (it would understate
        // drift); such loose mentions are reported separately as `mentions` for
        // the operator without inflating represented.
        let mut represented: std::collections::HashMap<String, Vec<String>> =
            std::collections::HashMap::new();
        let mut mentions: std::collections::HashMap<String, Vec<String>> =
            std::collections::HashMap::new();
        for rec in &verified {
            let artifact_id = match rec.get("artifact_id").and_then(Value::as_str) {
                Some(a) if !a.is_empty() => a,
                _ => continue,
            };
            if represented.contains_key(artifact_id) {
                continue;
            }
            let outcome_key = format!("outcome_{artifact_id}");
            let hits = store
                .memory_search(artifact_id, &[], probe_limit)
                .await
                .unwrap_or_default();
            let mut strict: Vec<String> = Vec::new();
            let mut loose: Vec<String> = Vec::new();
            for h in hits {
                if h.record.key == outcome_key {
                    strict.push(h.record.key);
                } else if h.record.key.contains(artifact_id)
                    || h.record.content.contains(artifact_id)
                {
                    loose.push(h.record.key);
                }
            }
            represented.insert(artifact_id.to_string(), strict);
            mentions.insert(artifact_id.to_string(), loose);
        }

        let snapshot = crate::present::outcomes_memory_drift_snapshot(
            &verified,
            &represented,
            &mentions,
            now.max(0) as u64,
            window_secs as u64,
        );
        Ok(ToolResult::json_text(&snapshot))
    }
}

/// **Slice B opt-in ingestion** — `present_outcomes_ingest`. Persists
/// gate-verified outcomes as ordinary memory rows (kind=present_outcome,
/// key=outcome_<artifact_id>) via the existing memory_save. `dry_run=true` by
/// DEFAULT — never automatic, capped by `max_writes`. The always-on Slice B
/// surface is the read-only drift projection; this tool closes the loop only on
/// explicit operator action with dry_run:false. Additive: no schema/column/table
/// change, no event_spine write.
/// Refresh-preserving lifecycle state for `present_outcomes_ingest`: when an
/// ACTIVE row already exists for the deterministic outcome key, a content
/// refresh must carry forward the state owned by OTHER writers, because the
/// upsert replaces both `importance` and `tags` wholesale:
///
/// - **importance** is owned by decay passes, reinforce, and
///   `outcome_valence_importance_apply` — the builder's initial value must
///   not stomp it.
/// - **the `valence_applied:` stamp** is APPLY HISTORY, only truthfully
///   minted by the code that actually wrote the derived importance. On a
///   refresh the builder's importance is discarded (above), so any stamp the
///   builder minted for this rebuild would attest an application that never
///   happened — drop it, and preserve the EXISTING row's stamp verbatim
///   instead. A facet change then leaves the old stamp mismatching the newly
///   derived valence, which is exactly what re-qualifies the row in the
///   audited apply pass.
///
/// A brand-new row keeps the builder's output unchanged (initial importance —
/// 0.5 or the gated derivation — plus, gate-ON, a truthful birth stamp).
pub(super) fn carry_forward_ingest_lifecycle(
    mut mem: MemoryRecord,
    existing: Option<&MemoryRecord>,
) -> MemoryRecord {
    if let Some(ex) = existing {
        mem.importance = ex.importance;
        mem.tags
            .retain(|t| !t.starts_with(crate::outcome_valence::VALENCE_APPLIED_TAG_PREFIX));
        if let Some(stamp) = ex
            .tags
            .iter()
            .find(|t| t.starts_with(crate::outcome_valence::VALENCE_APPLIED_TAG_PREFIX))
        {
            mem.tags.push(stamp.clone());
        }
    }
    mem
}

pub struct PresentOutcomesIngestTool {
    hub: Hub,
}
impl PresentOutcomesIngestTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for PresentOutcomesIngestTool {
    fn name(&self) -> &'static str {
        "present_outcomes_ingest"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Output-expression lane Slice B (v0): opt-in ingestion of gate-verified \
                 outcomes into memory as ordinary rows (kind=present_outcome, \
                 key=outcome_<artifact_id>, scope=outcome:<artifact_id> [distinct per artifact — \
                 the auto-supersede guard], additive tags, related_keys=[], importance 0.5). \
                 Reuses the verified_only stream (gate inherited, never re-run). dry_run=TRUE by \
                 DEFAULT: returns the would-write set + per-row active_row_exists (true = an ACTIVE \
                 row with that key already exists → a benign content refresh on save; the \
                 active-only probe cannot see a superseded/tombstoned row, so it is NOT a \
                 resurrection oracle) and writes NOTHING. Set dry_run=false to persist (capped by \
                 max_writes). No schema/column/table change, no event_spine write. Not automatic — \
                 there is no lifecycle hook; a human triggers it."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "window_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 31536000,
                        "default": 86400,
                        "description": "Look-back window over outcome records (by ts)."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "default": 200,
                        "description": "Max outcome records scanned (most-recent-first)."
                    },
                    "max_writes": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 25,
                        "description": "Hard cap on rows written (or proposed in dry_run)."
                    },
                    "dry_run": {
                        "type": "boolean",
                        "default": true,
                        "description": "When true (default) compute and report the would-write set + already_present, writing NOTHING. Set false to actually persist."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let window_secs = args
            .get("window_secs")
            .and_then(|v| v.as_i64())
            .unwrap_or(86_400)
            .clamp(60, 31_536_000);
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(200)
            .clamp(1, 1000) as usize;
        let max_writes = args
            .get("max_writes")
            .and_then(|v| v.as_u64())
            .unwrap_or(25)
            .clamp(1, 200) as usize;
        let dry_run = args
            .get("dry_run")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        let now = dispatch_now_secs();
        let cutoff = now.saturating_sub(window_secs).max(0) as u64;
        let dir = crate::present::presentations_dir();
        let records = crate::present::read_outcome_records(&dir, limit, cutoff);
        let projection = crate::present::present_outcomes_projection(&records, true);
        let verified: Vec<Value> = projection
            .get("outcomes")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();

        let mut planned: Vec<Value> = Vec::new();
        let mut written = 0usize;
        let mut skipped_cap = 0usize;
        let mut seen_keys: std::collections::HashSet<String> = std::collections::HashSet::new();

        for rec in &verified {
            let mem = match crate::present_ingest::build_outcome_memory(rec, now.max(0)) {
                Some(m) => m,
                None => continue, // keyless / unsafe → never minted
            };
            // Deterministic key → de-dupe within this batch (lossy stream can
            // surface the same artifact more than once).
            if !seen_keys.insert(mem.key.clone()) {
                continue;
            }
            // Cap BEFORE the existence probe so a huge sidecar dir doesn't issue
            // `limit` DB round-trips for records we'll never report/write.
            if planned.len() >= max_writes {
                skipped_cap += 1;
                continue;
            }
            // Non-mutating existence probe (NEVER memory_get, which bumps
            // access_count/last_accessed_at). HONEST SCOPE: memory_search only
            // returns ACTIVE rows, so this detects an existing *active* row (a
            // benign ON CONFLICT content refresh) — it does NOT and cannot see a
            // superseded/tombstoned row (no non-mutating status-aware keyed read
            // exists in the store trait). Named `active_row_exists` accordingly;
            // it is not a resurrection oracle.
            let existing_record = store
                .memory_search(&mem.key, &[], 5)
                .await
                .unwrap_or_default()
                .iter()
                .find(|h| h.record.key == mem.key)
                .map(|h| h.record.clone());
            let active_row_exists = existing_record.is_some();
            // Refresh must not reset lifecycle state (importance NOR the
            // valence_applied stamp): both are owned by other writers and the
            // upsert replaces the columns wholesale (adversarial review
            // findings, 2026-07-02 — gate-OFF refresh wiped the stamp; gate-ON
            // refresh minted a false one).
            let mem = carry_forward_ingest_lifecycle(mem, existing_record.as_ref());

            let mut row = json!({
                "key": mem.key,
                "kind": mem.kind,
                "scope": mem.scope,
                "active_row_exists": active_row_exists,
                "tags": mem.tags,
            });
            if !dry_run {
                match store.memory_save(&mem).await {
                    Ok(()) => {
                        written += 1;
                        if let Some(o) = row.as_object_mut() {
                            o.insert("written".into(), Value::Bool(true));
                        }
                    }
                    Err(e) => {
                        if let Some(o) = row.as_object_mut() {
                            o.insert("written".into(), Value::Bool(false));
                            o.insert("error".into(), Value::String(e.to_string()));
                        }
                    }
                }
            }
            planned.push(row);
        }

        Ok(ToolResult::json_text(&json!({
            "schema": "present_outcomes_ingest/v0",
            "dry_run": dry_run,
            "generated_at": now.max(0),
            "window_secs": window_secs,
            "verified_count": verified.len(),
            "planned_count": planned.len(),
            "written_count": written,
            "skipped_over_cap": skipped_cap,
            "max_writes": max_writes,
            "memory_kind": crate::present_ingest::OUTCOME_MEMORY_KIND,
            "note": if dry_run {
                "dry_run: nothing written. active_row_exists=true → an active row with that key exists (ON CONFLICT would refresh content, NOT resurrect). NOTE: a superseded/tombstoned same-key row is invisible to the active-only probe, so this flag does not detect resurrection. With per-artifact distinct scope, auto-supersede no longer creates retired rows; the only resurrection source is manual delete/tombstone. Set dry_run=false to persist."
            } else {
                "persisted gate-verified outcomes as memory rows (distinct scope per artifact prevents cross-supersede)."
            },
            "rows": planned,
        })))
    }
}

pub struct BrowserEvalTool {
    hub: Hub,
}
impl BrowserEvalTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserEvalTool {
    fn name(&self) -> &'static str {
        "browser_eval"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Evaluate JavaScript in the given page's main frame and return the \
                 resulting JSON value. The expression's last value is returned (wrap in \
                 `(() => { ... })()` for multi-statement code)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page": { "type": "string", "description": "Page id from browser_navigate." },
                    "js":   { "type": "string", "description": "JavaScript expression." }
                },
                "required": ["page", "js"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let js = args.get("js").and_then(|v| v.as_str()).unwrap_or("");
        match b.eval(&page, js).await {
            Ok(v) => Ok(ToolResult::json_text(&v)),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserSnapshotTool {
    hub: Hub,
}
impl BrowserSnapshotTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserSnapshotTool {
    fn name(&self) -> &'static str {
        "browser_snapshot"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Return the page's accessibility tree (role/name/value + children). \
                 Far cheaper than a screenshot for letting the agent reason about page \
                 structure: the same content takes 10–50× fewer tokens than a PNG. \
                 Interactive nodes (button/link/textbox/…) carry a stable \"ref\" like \
                 \"@e1\" — pass it as browser_click's selector to click by ref instead of \
                 a brittle CSS selector. Refs are re-numbered on each snapshot."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": { "page": { "type": "string" } },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        match b.snapshot_a11y(&page).await {
            Ok(tree) => Ok(ToolResult::json_text(
                &serde_json::to_value(tree).unwrap_or(Value::Null),
            )),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserClickTool {
    hub: Hub,
}
impl BrowserClickTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserClickTool {
    fn name(&self) -> &'static str {
        "browser_click"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Click an element by CSS selector, OR by a stable \"@eN\" ref from \
                a prior browser_snapshot (e.g. \"@e3\"). Refs resolve to the element's backend \
                DOM node, so they survive dynamic class names that break CSS selectors."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":     { "type": "string" },
                    "selector": { "type": "string", "description": "CSS selector, or an \"@eN\" ref from browser_snapshot." }
                },
                "required": ["page", "selector"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let sel = args.get("selector").and_then(|v| v.as_str()).unwrap_or("");
        if sel.is_empty() {
            return Ok(ToolResult::error("missing 'selector'"));
        }
        // An `@eN` value (literally @e followed by digits) is a stable ref from a
        // prior browser_snapshot; route it to the ref-based click. Match the exact
        // ref grammar — not a loose "@e" prefix — so a selector like "@email" or an
        // attribute selector still goes down the CSS path. (Real CSS selectors never
        // begin with a literal '@', so backward compat is intact.) No schema change.
        let is_ref = sel.len() > 2
            && sel.as_bytes()[0] == b'@'
            && sel.as_bytes()[1] == b'e'
            && sel[2..].bytes().all(|c| c.is_ascii_digit());
        let outcome = if is_ref {
            b.click_by_ref(&page, sel).await
        } else {
            b.click(&page, sel).await
        };
        // SSB Phase-1 typed event spine: emit a verify-first semantic event AT
        // ACTION TIME. The verdict records whether the click was confirmed
        // actionable (Verified), determined inert/failed (NotVerified — the
        // anti-laundering signal), or merely dispatched without readback
        // (Unknown). Best-effort: a telemetry write must never fail the click.
        let (ok, err_msg) = match &outcome {
            Ok(()) => (true, String::new()),
            Err(e) => (false, e.to_string()),
        };
        if let Some(store) = &self.hub.store {
            let verdict = crate::semantic_event::classify_click(is_ref, ok, &err_msg);
            // SSB unified contract: same Object/Affordance vocabulary as desktop_action.
            let object = crate::semantic_event::SemanticObject {
                object_type: "dom_element".to_string(),
                source_adapter: "browser".to_string(),
                label: None,
                object_id: Some(sel.to_string()),
            };
            let affordance = crate::semantic_event::Affordance {
                action_type: "click".to_string(),
                risk_level: "low".to_string(),
                requires_gate: false,
                expected_effect: Some("the targeted DOM element receives a click".to_string()),
            };
            let ev = crate::semantic_event::SemanticEvent {
                ts: dispatch_now_secs(),
                actor: "mcp".to_string(),
                source: "browser".to_string(),
                action: "click".to_string(),
                target: Some(sel.to_string()),
                object,
                affordance,
                verdict,
                facts: json!({ "selector": sel, "is_ref": is_ref, "page": page.as_str() }),
            };
            if let Err(e) = store.record_semantic_event(ev.to_record()).await {
                tracing::debug!(error = %e, "record_semantic_event (browser_click) failed");
            }
        }
        match outcome {
            Ok(()) => Ok(ToolResult::text(format!("clicked {sel}"))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserScreenshotTool {
    hub: Hub,
}
impl BrowserScreenshotTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserScreenshotTool {
    fn name(&self) -> &'static str {
        "browser_screenshot"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Capture a full-page PNG screenshot. Default mode writes the PNG \
                 to /tmp and returns the file path (cheap, suitable for storage / \
                 passing to other tools). Set `inline=true` to return the image as \
                 a real MCP image content block — Claude renders it directly into \
                 context (token-heavy, ~1k tokens per 100 KB; only use when you \
                 actually need to *see* the page)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":   { "type": "string" },
                    "path":   { "type": "string", "description": "Optional output path (file mode only)." },
                    "inline": {
                        "type": "boolean",
                        "default": false,
                        "description": "If true, return the PNG as an MCP image block instead of writing a file."
                    }
                },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let png = match b.screenshot(&page).await {
            Ok(p) => p,
            Err(e) => return Ok(ToolResult::error(format!("browser: {e}"))),
        };
        let inline = args
            .get("inline")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        if inline {
            let b64 = general_purpose::STANDARD.encode(&png);
            let caption = format!("inline screenshot — {} bytes, image/png", png.len());
            return Ok(ToolResult::image_with_caption(b64, "image/png", caption));
        }
        let path = args
            .get("path")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| {
                std::env::temp_dir()
                    .join(format!("agent-bridge-{page}.png"))
                    .to_string_lossy()
                    .into_owned()
            });
        if let Err(e) = tokio::fs::write(&path, &png).await {
            return Ok(ToolResult::error(format!("write {path}: {e}")));
        }
        Ok(ToolResult::text(format!(
            "wrote {} bytes → {path}",
            png.len()
        )))
    }
}

pub struct BrowserScreenshotElementTool {
    hub: Hub,
}
impl BrowserScreenshotElementTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserScreenshotElementTool {
    fn name(&self) -> &'static str {
        "browser_screenshot_element"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Capture a tight PNG screenshot of just the first element matching \
                 `selector` (auto-scrolls into view; clip = element bounding box). Same \
                 file/inline options as `browser_screenshot`. Use this instead of a full-\
                 page shot when you only need to verify one widget rendered correctly \
                 (e.g. the API key value displayed in a code block)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":     { "type": "string" },
                    "selector": { "type": "string", "description": "CSS selector for the element to capture." },
                    "path":     { "type": "string", "description": "Optional output path (file mode only)." },
                    "inline":   { "type": "boolean", "default": false, "description": "If true, return the PNG as an MCP image block instead of writing a file." }
                },
                "required": ["page", "selector"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let selector = args.get("selector").and_then(|v| v.as_str()).unwrap_or("");
        if selector.is_empty() {
            return Ok(ToolResult::error("missing 'selector'"));
        }
        let png = match b.screenshot_element(&page, selector).await {
            Ok(p) => p,
            Err(e) => return Ok(ToolResult::error(format!("browser: {e}"))),
        };
        let inline = args
            .get("inline")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        if inline {
            let b64 = general_purpose::STANDARD.encode(&png);
            let caption = format!("inline element screenshot — {} bytes, image/png", png.len());
            return Ok(ToolResult::image_with_caption(b64, "image/png", caption));
        }
        let path = args
            .get("path")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| {
                std::env::temp_dir()
                    .join(format!("agent-bridge-{page}-element.png"))
                    .to_string_lossy()
                    .into_owned()
            });
        if let Err(e) = tokio::fs::write(&path, &png).await {
            return Ok(ToolResult::error(format!("write {path}: {e}")));
        }
        Ok(ToolResult::text(format!(
            "wrote {} bytes → {path}",
            png.len()
        )))
    }
}

pub struct BrowserExtractTextTool {
    hub: Hub,
}
impl BrowserExtractTextTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserExtractTextTool {
    fn name(&self) -> &'static str {
        "browser_extract_text"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Return visible page text (`innerText` of the document root). \
                 Cheaper than screenshots for reading main content when layout does not matter."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": { "page": { "type": "string", "description": "Page id from browser_navigate." } },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        match b.extract_text(&page).await {
            Ok(text) => Ok(ToolResult::json_text(&json!({
                "page": page.as_str(),
                "chars": text.len(),
                "text": text
            }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserFillFormTool {
    hub: Hub,
}
impl BrowserFillFormTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserFillFormTool {
    fn name(&self) -> &'static str {
        "browser_fill_form"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Fill the first element matching a CSS selector (sets `.value` or \
                 `textContent`) and dispatch `input`/`change` events."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":     { "type": "string" },
                    "selector": { "type": "string", "description": "CSS selector." },
                    "value":    { "type": "string", "description": "Text to apply." }
                },
                "required": ["page", "selector", "value"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let sel = args.get("selector").and_then(|v| v.as_str()).unwrap_or("");
        if sel.is_empty() {
            return Ok(ToolResult::error("missing 'selector'"));
        }
        let val = args.get("value").and_then(|v| v.as_str()).unwrap_or("");
        match b.fill_form(&page, sel, val).await {
            Ok(()) => Ok(ToolResult::json_text(&json!({
                "page": page.as_str(),
                "selector": sel,
                "status": "ok"
            }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserWaitForTool {
    hub: Hub,
}
impl BrowserWaitForTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserWaitForTool {
    fn name(&self) -> &'static str {
        "browser_wait_for"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Block until a CSS selector becomes present in the DOM, OR the page \
                 URL contains a substring, OR a timeout expires. Polls every 100 ms. Returns \
                 `{matched: \"selector\"|\"url\"|\"timeout\", elapsed_ms, current_url}`. Either \
                 or both predicates may be passed; `matched=\"timeout\"` is NOT an error — \
                 inspect the field to decide what to do next."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":          { "type": "string", "description": "Page id from browser_navigate." },
                    "selector":      { "type": "string", "description": "CSS selector to wait for (optional)." },
                    "url_substring": { "type": "string", "description": "Wait until location.href contains this (optional)." },
                    "timeout_ms":    { "type": "integer", "default": 10000, "minimum": 50, "maximum": 60000 }
                },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let sel = args
            .get("selector")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let url_sub = args
            .get("url_substring")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(10_000)
            .clamp(50, 60_000);
        match b.wait_for(&page, sel, url_sub, timeout_ms).await {
            Ok(out) => Ok(ToolResult::json_text(
                &serde_json::to_value(out).unwrap_or(Value::Null),
            )),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserListPagesTool {
    hub: Hub,
}
impl BrowserListPagesTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserListPagesTool {
    fn name(&self) -> &'static str {
        "browser_list_pages"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "List every page (tab/window) the underlying browser has open. \
                 Auto-discovers tabs that were opened by clicks, window.open, or \
                 target=_blank links and assigns fresh page_ids for them. The \
                 `newly_tracked` flag is true for tabs the daemon hadn't seen before \
                 this call — those are typically OAuth pop-ups or 'Open in new tab' \
                 results. Use this after any click that might have opened a new tab."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": false
            }),
        }
    }
    async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        match b.list_pages().await {
            Ok(rows) => Ok(ToolResult::json_text(&json!({
                "count": rows.len(),
                "pages": rows
            }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserPressKeyTool {
    hub: Hub,
}
impl BrowserPressKeyTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserPressKeyTool {
    fn name(&self) -> &'static str {
        "browser_press_key"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Dispatch a key-down + key-up sequence to whatever element is \
                 currently focused on `page`. `key` is a single character (\"a\", \"0\") \
                 or a named key (\"Enter\", \"Tab\", \"Escape\", \"ArrowDown\", \"Backspace\", \
                 etc.; full set: chromiumoxide::keys::USKEYBOARD_LAYOUT). \
                 `modifiers` is a CDP modifier bitmask: 1=Alt, 2=Ctrl, 4=Meta/Cmd, \
                 8=Shift; combine by OR-ing (e.g. 8|2 = 10 for Shift+Ctrl). \
                 Default 0 = no modifiers."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":      { "type": "string", "description": "Page id from browser_navigate." },
                    "key":       { "type": "string", "description": "Key name or single character." },
                    "modifiers": { "type": "integer", "default": 0, "minimum": 0, "maximum": 15 }
                },
                "required": ["page", "key"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let key = match args
            .get("key")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing 'key'")),
        };
        let modifiers = args
            .get("modifiers")
            .and_then(|v| v.as_u64())
            .unwrap_or(0)
            .clamp(0, 15) as u32;
        match b.press_key(&page, &key, modifiers).await {
            Ok(()) => Ok(ToolResult::json_text(&json!({
                "page": page.as_str(),
                "key": key,
                "modifiers": modifiers,
                "status": "ok"
            }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserSelectOptionTool {
    hub: Hub,
}
impl BrowserSelectOptionTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserSelectOptionTool {
    fn name(&self) -> &'static str {
        "browser_select_option"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Set the selected option of a `<select>` element. `value` matches \
                 against `option.value` first, then `option.text` (the visible label) — \
                 handles both `<option value=\"us\">United States</option>` and country \
                 pickers indexed by visible name. Dispatches `input` + `change` events. \
                 Returns `{selectedIndex, selectedValue, selectedText}`. Errors out with \
                 the available value/label list if no option matches."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":     { "type": "string", "description": "Page id from browser_navigate." },
                    "selector": { "type": "string", "description": "CSS selector for the <select> element." },
                    "value":    { "type": "string", "description": "option.value or option.text to select." }
                },
                "required": ["page", "selector", "value"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let sel = args.get("selector").and_then(|v| v.as_str()).unwrap_or("");
        if sel.is_empty() {
            return Ok(ToolResult::error("missing 'selector'"));
        }
        let val = args.get("value").and_then(|v| v.as_str()).unwrap_or("");
        if val.is_empty() {
            return Ok(ToolResult::error("missing 'value'"));
        }
        match b.select_option(&page, sel, val).await {
            Ok(v) => Ok(ToolResult::json_text(&v)),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserFindByTextTool {
    hub: Hub,
}
impl BrowserFindByTextTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserFindByTextTool {
    fn name(&self) -> &'static str {
        "browser_find_by_text"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Find DOM elements whose visible text contains `text`, returning a \
                 generated CSS selector for each that you can hand to browser_click or \
                 browser_fill_form. Optional `tag_filter` (\"button\", \"a\", \"input\", etc.) \
                 narrows the search; default \"*\" scans all elements. Returns up to 5 \
                 deepest-match candidates (parent containers are excluded if a child also \
                 matches). Empty `matches` array = no element found — try fewer characters \
                 or drop the tag filter."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":       { "type": "string", "description": "Page id from browser_navigate." },
                    "text":       { "type": "string", "description": "Substring to find in visible text." },
                    "tag_filter": { "type": "string", "description": "Optional tag name (default '*' scans all)." }
                },
                "required": ["page", "text"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let text = args.get("text").and_then(|v| v.as_str()).unwrap_or("");
        if text.is_empty() {
            return Ok(ToolResult::error("missing 'text'"));
        }
        let tag = args
            .get("tag_filter")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        match b.find_by_text(&page, text, tag).await {
            Ok(v) => Ok(ToolResult::json_text(&v)),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserListFramesTool {
    hub: Hub,
}
impl BrowserListFramesTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserListFramesTool {
    fn name(&self) -> &'static str {
        "browser_list_frames"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Enumerate the frame tree of `page`. Returns `[{frame_id, url, name, \
                 parent_id}]` covering the main document and every iframe regardless of \
                 cross-origin status. Use the `frame_id` (or a URL substring) with \
                 `browser_eval_in_frame` to drive code inside Stripe Elements / reCAPTCHA \
                 / Auth0 / any other embedded widget the parent JS cannot reach."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page": { "type": "string", "description": "Page id from browser_navigate." }
                },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        match b.list_frames(&page).await {
            Ok(v) => Ok(ToolResult::json_text(&v)),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserEvalInFrameTool {
    hub: Hub,
}
impl BrowserEvalInFrameTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserEvalInFrameTool {
    fn name(&self) -> &'static str {
        "browser_eval_in_frame"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Evaluate JavaScript inside a specific frame's isolated world. Pass \
                 either `frame_id` (from browser_list_frames) or `frame_url_substring` \
                 (matched against each frame's URL — first hit wins). Crosses cross-origin \
                 iframe boundaries that the parent's own JS cannot touch (Stripe Elements, \
                 reCAPTCHA, Auth0). The expression's last value is returned (wrap multi-\
                 statement code in `(() => { ... })()`). Exception details are surfaced \
                 with `text @ url:line:col`."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":                { "type": "string", "description": "Page id from browser_navigate." },
                    "frame_id":            { "type": "string", "description": "Frame id from browser_list_frames (preferred — exact)." },
                    "frame_url_substring": { "type": "string", "description": "Substring matched against each frame's URL — first hit wins." },
                    "js":                  { "type": "string", "description": "JavaScript expression." }
                },
                "required": ["page", "js"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let js = args.get("js").and_then(|v| v.as_str()).unwrap_or("");
        if js.is_empty() {
            return Ok(ToolResult::error("missing 'js'"));
        }
        let fid = args
            .get("frame_id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let furl = args
            .get("frame_url_substring")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        match b.eval_in_frame(&page, fid, furl, js).await {
            Ok(v) => Ok(ToolResult::json_text(&v)),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserPauseForHumanTool {
    hub: Hub,
}
impl BrowserPauseForHumanTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserPauseForHumanTool {
    fn name(&self) -> &'static str {
        "browser_pause_for_human"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Block this MCP request until a human releases the page via \
                 `browser_resume`, or until `timeout_ms` elapses. Fires a desktop \
                 notification (severity=attention) before pausing so the human is \
                 actually pinged. Use this for CAPTCHA solves, OTP/2FA prompts, \
                 \"are you sure?\" gates the agent shouldn't auto-click. Returns \
                 `{outcome, elapsed_ms}` where outcome ∈ {resumed, timeout, \
                 superseded}. `timeout_ms` clamped to [1_000, 1_800_000] (1 s … \
                 30 min); default 600_000 (10 min)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":       { "type": "string", "description": "Page id from browser_navigate." },
                    "reason":     { "type": "string", "description": "Short human-readable reason — appears in the notification body." },
                    "hint":       { "type": "string", "description": "Optional follow-up instruction for the human (e.g. 'solve CAPTCHA then call browser_resume')." },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 1800000, "default": 600000 }
                },
                "required": ["page", "reason"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let reason = args
            .get("reason")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        if reason.is_empty() {
            return Ok(ToolResult::error("missing 'reason'"));
        }
        let hint = args
            .get("hint")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(600_000);

        // Fire the notification BEFORE blocking, so the human gets pinged
        // even if all delivery channels are slow.
        let body = if hint.is_empty() {
            format!("page {}: {}", page.as_str(), reason)
        } else {
            format!("page {}: {} — {}", page.as_str(), reason, hint)
        };
        let evt = NotifyEvent {
            source: NotifySource::Mcp,
            severity: NotifySeverity::Attention,
            title: "browser: human action required".into(),
            body,
            session_id: None,
            context: json!({
                "tool": "browser_pause_for_human",
                "page": page.as_str(),
                "reason": reason,
                "hint": hint,
                "timeout_ms": timeout_ms,
            }),
        };
        let (delivered, _persisted) = self.hub.deliver(&evt).await;

        match b.pause_for_human(&page, timeout_ms).await {
            Ok(out) => Ok(ToolResult::json_text(&json!({
                "outcome": out.outcome,
                "elapsed_ms": out.elapsed_ms,
                "notified": delivered,
            }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserResumeTool {
    hub: Hub,
}
impl BrowserResumeTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserResumeTool {
    fn name(&self) -> &'static str {
        "browser_resume"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Release a `browser_pause_for_human` waiter on `page`. \
                 Returns `{released}` — true if a waiter existed and was woken \
                 up, false if no pause was pending (the original call already \
                 timed out, or page id is wrong)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page": { "type": "string", "description": "Page id passed to the original browser_pause_for_human." }
                },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        match b.resume(&page).await {
            Ok(released) => Ok(ToolResult::json_text(&json!({ "released": released }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserCaptureResponseStartTool {
    hub: Hub,
}
impl BrowserCaptureResponseStartTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserCaptureResponseStartTool {
    fn name(&self) -> &'static str {
        "browser_capture_response_start"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Begin recording XHR / Fetch / document responses on `page` whose URL \
                 contains `url_substring`. The recorder fetches the response body via \
                 `Network.getResponseBody` *after* `Network.loadingFinished` fires, so \
                 bodies are guaranteed-loaded (no flaky 'No data found' races). Idempotent \
                 per page: a second start replaces the first (existing buffer dropped). \
                 Pair with `browser_capture_response_drain` to read matches. Typical use: \
                 start capture before clicking 'Generate API Key', drain after to grab the \
                 freshly-issued key from the JSON response. `max_buffer` clamped to [1, 200] \
                 (default 50); ring-buffer drops oldest when full."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":          { "type": "string", "description": "Page id from browser_navigate." },
                    "url_substring": { "type": "string", "description": "Substring matched against full response URL — first hit per request_id wins. Pass a path fragment like '/api/v1/keys' or a host like 'api.openai.com'." },
                    "max_buffer":    { "type": "integer", "minimum": 1, "maximum": 200, "default": 50 }
                },
                "required": ["page", "url_substring"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let url_substring = args
            .get("url_substring")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if url_substring.is_empty() {
            return Ok(ToolResult::error("missing 'url_substring'"));
        }
        let max_buffer = args
            .get("max_buffer")
            .and_then(|v| v.as_u64())
            .unwrap_or(50) as usize;
        match b
            .capture_response_start(&page, url_substring, max_buffer)
            .await
        {
            Ok(()) => Ok(ToolResult::json_text(&json!({
                "status": "ok",
                "page": page.as_str(),
                "url_substring": url_substring,
                "max_buffer": max_buffer.clamp(1, 200),
            }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserCaptureResponseDrainTool {
    hub: Hub,
}
impl BrowserCaptureResponseDrainTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserCaptureResponseDrainTool {
    fn name(&self) -> &'static str {
        "browser_capture_response_drain"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Drain (and clear) responses captured since the last drain or since \
                 `browser_capture_response_start` began recording. If the buffer is empty, \
                 blocks up to `until_ms` for at least one match to arrive — useful for \
                 'wait for the API key XHR after I click submit'. Returns oldest-first; at \
                 most `max_results` entries. Each row: `{request_id, url, status, \
                 resource_type, mime_type, body, base64_encoded, headers, ts_ms}`. Errors \
                 if no capture is currently active for `page`. `until_ms` clamped to \
                 [0, 60_000]; `max_results` clamped to [1, 200] (default 20)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":        { "type": "string", "description": "Page id passed to capture_response_start." },
                    "until_ms":    { "type": "integer", "minimum": 0, "maximum": 60000, "default": 5000 },
                    "max_results": { "type": "integer", "minimum": 1, "maximum": 200, "default": 20 }
                },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let until_ms = args
            .get("until_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(5000);
        let max_results = args
            .get("max_results")
            .and_then(|v| v.as_u64())
            .unwrap_or(20) as usize;
        match b.capture_response_drain(&page, until_ms, max_results).await {
            Ok(rows) => Ok(ToolResult::json_text(&json!({
                "count": rows.len(),
                "rows": rows,
            }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserReloadTool {
    hub: Hub,
}
impl BrowserReloadTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserReloadTool {
    fn name(&self) -> &'static str {
        "browser_reload"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Reload `page` (CDP `Page.reload`) and wait for the load event. \
                 Equivalent to clicking the browser's reload button. Use after a network \
                 hiccup or when an SPA gets stuck in an inconsistent state."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page": { "type": "string", "description": "Page id from browser_navigate." }
                },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        match b.reload(&page).await {
            Ok(()) => Ok(ToolResult::json_text(&json!({ "status": "ok" }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserBackTool {
    hub: Hub,
}
impl BrowserBackTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserBackTool {
    fn name(&self) -> &'static str {
        "browser_back"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Step `page` one entry back in its session history (equivalent to \
                 clicking the browser's back button / `history.back()`). Returns immediately \
                 after dispatching; use `browser_wait_for` afterwards if you need to block \
                 until the URL settles."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page": { "type": "string", "description": "Page id from browser_navigate." }
                },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        match b.go_back(&page).await {
            Ok(()) => Ok(ToolResult::json_text(&json!({ "status": "ok" }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserForwardTool {
    hub: Hub,
}
impl BrowserForwardTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserForwardTool {
    fn name(&self) -> &'static str {
        "browser_forward"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Step `page` one entry forward in its session history (equivalent \
                 to clicking the browser's forward button / `history.forward()`). Returns \
                 immediately after dispatching; chase with `browser_wait_for` if needed."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page": { "type": "string", "description": "Page id from browser_navigate." }
                },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        match b.go_forward(&page).await {
            Ok(()) => Ok(ToolResult::json_text(&json!({ "status": "ok" }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserClosePageTool {
    hub: Hub,
}
impl BrowserClosePageTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserClosePageTool {
    fn name(&self) -> &'static str {
        "browser_close_page"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Close `page` and drop its tracker entry. Also releases any \
                 in-flight `browser_pause_for_human` waiter and aborts any active \
                 `browser_capture_response_*` pump on this page so they don't strand. \
                 Use after a flow finishes (e.g. signup confirmation grabbed) to free \
                 the tab and the daemon-side state."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page": { "type": "string", "description": "Page id from browser_navigate." }
                },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        match b.close(&page).await {
            Ok(()) => Ok(ToolResult::json_text(&json!({ "status": "ok" }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserScrollTool {
    hub: Hub,
}
impl BrowserScrollTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserScrollTool {
    fn name(&self) -> &'static str {
        "browser_scroll"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Scroll `page`. If `selector` is given, scroll the matching \
                 element into view (centered) — useful for revealing buttons below the \
                 fold before clicking. Otherwise dispatch `window.scrollBy(dx, dy)` with \
                 the supplied pixel deltas. Returns post-scroll \
                 `{scrollX, scrollY, scrollHeight}` so the agent can verify."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":     { "type": "string", "description": "Page id from browser_navigate." },
                    "selector": { "type": "string", "description": "CSS selector to scrollIntoView. Mutually exclusive with dx/dy." },
                    "dx":       { "type": "number", "default": 0, "description": "Horizontal pixels (used when selector is absent)." },
                    "dy":       { "type": "number", "default": 0, "description": "Vertical pixels (used when selector is absent)." }
                },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let selector = args
            .get("selector")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let dx = args.get("dx").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let dy = args.get("dy").and_then(|v| v.as_f64()).unwrap_or(0.0);
        match b.scroll(&page, selector, dx, dy).await {
            Ok(v) => Ok(ToolResult::json_text(&v)),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserUploadFileTool {
    hub: Hub,
}
impl BrowserUploadFileTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserUploadFileTool {
    fn name(&self) -> &'static str {
        "browser_upload_file"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Set files for an `<input type=\"file\">` element via CDP \
                 `DOM.setFileInputFiles`. Bypasses the OS file-picker dialog (which is \
                 unscriptable). `files` is a list of absolute paths on the daemon host. \
                 The input's `change` event fires automatically — no need to manually \
                 dispatch. Useful for ID-document upload steps in KYC sign-ups, avatar \
                 uploads, etc."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":     { "type": "string", "description": "Page id from browser_navigate." },
                    "selector": { "type": "string", "description": "CSS selector for the file <input> element." },
                    "files":    {
                        "type": "array",
                        "items": { "type": "string" },
                        "minItems": 1,
                        "description": "Absolute paths on the daemon host. Multi-file inputs accept multiple; single inputs use the first."
                    }
                },
                "required": ["page", "selector", "files"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let selector = args.get("selector").and_then(|v| v.as_str()).unwrap_or("");
        if selector.is_empty() {
            return Ok(ToolResult::error("missing 'selector'"));
        }
        let files: Vec<String> = match args.get("files").and_then(|v| v.as_array()) {
            Some(arr) => arr
                .iter()
                .filter_map(|v| v.as_str().map(|s| s.to_string()))
                .collect(),
            None => return Ok(ToolResult::error("missing 'files' array")),
        };
        if files.is_empty() {
            return Ok(ToolResult::error("'files' is empty"));
        }
        match b.upload_file(&page, selector, files.clone()).await {
            Ok(()) => Ok(ToolResult::json_text(&json!({
                "status": "ok",
                "uploaded": files.len(),
            }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserSetEmulationTool {
    hub: Hub,
}
impl BrowserSetEmulationTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserSetEmulationTool {
    fn name(&self) -> &'static str {
        "browser_set_emulation"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Override device characteristics for `page`: User-Agent string, \
                 Accept-Language header, viewport size, mobile flag, device pixel ratio. \
                 Useful for sign-up flows gated behind 'mobile only' checks (most banking \
                 / fintech) or for testing geo / locale-specific UI. All fields optional; \
                 omitted ones are left untouched. Pass `width` or `height` = 0 to disable \
                 the corresponding viewport override; pass empty `user_agent` to skip the \
                 UA override entirely. Persists for the lifetime of the page."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":                { "type": "string", "description": "Page id from browser_navigate." },
                    "user_agent":          { "type": "string", "description": "Full UA string. Empty / omitted = no UA override." },
                    "accept_language":     { "type": "string", "description": "e.g. 'en-US,en;q=0.9' or 'fr-FR'." },
                    "platform":            { "type": "string", "description": "Value navigator.platform should return (e.g. 'Linux x86_64')." },
                    "viewport_width":      { "type": "integer", "minimum": 0, "description": "CSS pixels; 0 = no override." },
                    "viewport_height":     { "type": "integer", "minimum": 0, "description": "CSS pixels; 0 = no override." },
                    "device_scale_factor": { "type": "number", "default": 1.0, "description": "DPR (1.0 = standard, 2.0 = retina). 0 = host default." },
                    "mobile":              { "type": "boolean", "default": false, "description": "Emulate mobile (overlay scrollbars, viewport meta, text autosizing)." }
                },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let user_agent = args
            .get("user_agent")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let accept_language = args
            .get("accept_language")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let platform = args
            .get("platform")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let vw = args
            .get("viewport_width")
            .and_then(|v| v.as_i64())
            .unwrap_or(0);
        let vh = args
            .get("viewport_height")
            .and_then(|v| v.as_i64())
            .unwrap_or(0);
        let dpr = args
            .get("device_scale_factor")
            .and_then(|v| v.as_f64())
            .unwrap_or(1.0);
        let mobile = args
            .get("mobile")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        let mut applied: Vec<&str> = Vec::new();
        if !user_agent.is_empty() {
            if let Err(e) = b
                .set_user_agent(&page, user_agent, accept_language, platform)
                .await
            {
                return Ok(ToolResult::error(format!("browser: {e}")));
            }
            applied.push("user_agent");
        }
        if vw > 0 || vh > 0 {
            if let Err(e) = b.set_viewport(&page, vw, vh, dpr, mobile).await {
                return Ok(ToolResult::error(format!("browser: {e}")));
            }
            applied.push("viewport");
        }
        if applied.is_empty() {
            return Ok(ToolResult::error(
                "no override applied — pass user_agent or viewport_width/height",
            ));
        }
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "applied": applied,
        })))
    }
}

pub struct BrowserHoverTool {
    hub: Hub,
}
impl BrowserHoverTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserHoverTool {
    fn name(&self) -> &'static str {
        "browser_hover"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Move the mouse cursor over the first element matching `selector` \
                 (auto-scrolls into view first). Triggers `mouseenter` / `mouseover` \
                 handlers and CSS `:hover` styles — useful for revealing drop-down menus, \
                 tooltips, and 'show on hover' UI affordances before clicking the \
                 newly-visible target."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":     { "type": "string", "description": "Page id from browser_navigate." },
                    "selector": { "type": "string", "description": "CSS selector for the element to hover over." }
                },
                "required": ["page", "selector"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let selector = args.get("selector").and_then(|v| v.as_str()).unwrap_or("");
        if selector.is_empty() {
            return Ok(ToolResult::error("missing 'selector'"));
        }
        match b.hover(&page, selector).await {
            Ok(()) => Ok(ToolResult::json_text(&json!({ "status": "ok" }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct AgentMessageTool {
    hub: Hub,
}
impl AgentMessageTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for AgentMessageTool {
    fn name(&self) -> &'static str {
        "agent_message"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Append a JSON payload to another session's inbox (SQLite \
                 `agent_messages`). Use opaque session ids (e.g. client-supplied handles). \
                 Set `peer: \"host:port\"` to route via that tailnet daemon-http instead of \
                 local (XM v0.2); when peer is set, ALSO posts a wake signal to the peer's \
                 `messaging` board (`direct:<to_session>` title) so the recipient session's \
                 next forum_read cycle surfaces the new inbox entry."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "from_session": { "type": "string", "description": "Sender session id." },
                    "to_session":   { "type": "string", "description": "Recipient session id." },
                    "payload":      { "type": "object", "description": "Arbitrary JSON object." },
                    "peer":         { "type": "string", "description": "Optional tailnet peer host:port; routes inbox write + wake signal via that daemon-http. (XM v0.2)" }
                },
                "required": ["from_session", "to_session", "payload"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let from_session = match args
            .get("from_session")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing or empty 'from_session'")),
        };
        let to_session = match args
            .get("to_session")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing or empty 'to_session'")),
        };
        let payload = match args.get("payload").filter(|v| v.is_object()) {
            Some(v) => v.clone(),
            None => return Ok(ToolResult::error("missing 'payload' object")),
        };
        let peer = args
            .get("peer")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());

        if let Some(p) = peer {
            // XM v0.2 — cross-machine path: write to peer's inbox + post
            // wake signal to its `messaging` board. The inbox write is
            // the durable payload; the wake forum_post is best-effort
            // (recipient can still poll via agent_inbox if the wake fails).
            let id = crate::peer_client::agent_message(p, &from_session, &to_session, &payload)
                .await
                .map_err(|e| ab_core::Error::Backend(format!("agent_message peer: {e}")))?;

            // Wake signal — separate forum_post call so a forum-side
            // SQLite hiccup on the peer doesn't roll back the inbox write.
            let wake_title = format!("direct:{to_session}");
            let wake_body = format!("📬 msg id {id} from {from_session}");
            let wake_refs = json!({
                "agent_msg_id": id,
                "to_session": to_session,
                "from_session": from_session,
            });
            let wake_req = crate::peer_client::ForumPostRequest {
                author: &from_session,
                body: &wake_body,
                thread_id: None,
                board: Some("messaging"),
                title: Some(&wake_title),
                kind: Some("msg"),
                tags: None,
                refs: Some(&wake_refs),
            };
            let (wake_status, wake_error) = match crate::peer_client::forum_post(p, wake_req).await
            {
                Ok(v) => (
                    json!({
                        "ok": true,
                        "post_id": v.get("post_id").cloned().unwrap_or(json!(null)),
                        "thread_id": v.get("thread_id").cloned().unwrap_or(json!(null)),
                        "board": "messaging",
                        "title": wake_title.clone(),
                    }),
                    None,
                ),
                Err(e) => (json!({"ok": false}), Some(format!("{e}"))),
            };

            let mut resp = json!({
                "status": "ok",
                "id": id,
                "peer": p,
                "from_session": from_session,
                "to_session": to_session,
                "wake_signal": wake_status,
            });
            if let Some(err) = wake_error {
                resp.as_object_mut()
                    .expect("wake resp must be object")
                    .insert("wake_signal_error".into(), Value::String(err));
            }
            return Ok(ToolResult::json_text(&resp));
        }

        // Local path — today's behavior unchanged.
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let id = store
            .agent_message_send(&from_session, &to_session, &payload)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("agent_message_send: {e}")))?;
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "id": id,
            "from_session": from_session,
            "to_session": to_session
        })))
    }
}

pub struct AgentInboxTool {
    hub: Hub,
}
impl AgentInboxTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for AgentInboxTool {
    fn name(&self) -> &'static str {
        "agent_inbox"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Fetch inbox rows for `to_session`, optionally after `since_id` \
                 (message id cursor), optionally unread-only. Ordered by id ascending; limit 1–500. \
                 Set `peer: \"host:port\"` to read from that tailnet daemon-http's inbox instead \
                 of local (XM v0.2). Returned payloads still live on the remote node; this tool \
                 does NOT replicate them locally."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "to_session": {
                        "type": "string",
                        "description": "Recipient session id (same namespace as agent_message)."
                    },
                    "since_id": {
                        "type": "integer",
                        "description": "Only rows with id greater than this (exclusive cursor)."
                    },
                    "unread_only": {
                        "type": "boolean",
                        "default": false,
                        "description": "If true, only rows with read=0."
                    },
                    "limit": {
                        "type": "integer",
                        "default": 50,
                        "description": "Max rows (clamped 1–500)."
                    },
                    "peer": {
                        "type": "string",
                        "description": "Optional tailnet peer host:port; routes the read via that daemon-http. (XM v0.2)"
                    }
                },
                "required": ["to_session"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let to_session = match args
            .get("to_session")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing or empty 'to_session'")),
        };
        let since_id = args.get("since_id").and_then(|v| v.as_i64());
        let unread_only = args
            .get("unread_only")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(50)
            .clamp(1, 500) as u32;
        let peer = args
            .get("peer")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());

        if let Some(p) = peer {
            let rows =
                crate::peer_client::agent_inbox(p, &to_session, since_id, unread_only, limit)
                    .await
                    .map_err(|e| ab_core::Error::Backend(format!("agent_inbox peer: {e}")))?;
            return Ok(ToolResult::json_text(&json!({
                "to_session": to_session,
                "since_id": since_id,
                "count": rows.len(),
                "messages": rows,
                "peer": p,
            })));
        }

        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let rows = store
            .agent_inbox_fetch(&to_session, since_id, unread_only, limit)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("agent_inbox_fetch: {e}")))?;
        Ok(ToolResult::json_text(&json!({
            "to_session": to_session,
            "since_id": since_id,
            "count": rows.len(),
            "messages": rows
        })))
    }
}
