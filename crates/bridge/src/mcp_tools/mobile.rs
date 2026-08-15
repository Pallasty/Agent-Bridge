//! mobile / Android ADB bridge tools: device discovery, UI snapshot/interaction, screenshot, logcat, APK install, plus the iOS observation subset. Includes the self-contained mobile_tool_struct! helper macro (defined and used only here).
//! Extracted verbatim from `mcp_tools.rs` (2026-07 split, step 2); the
//! only mechanical delta is `pub(super)` on previously-private top-level
//! items (51 promoted).

use super::*;

// ===========================================================================
//                        mobile / Android ADB tools
// ===========================================================================

pub(super) const MOBILE_UI_DUMP_PATH: &str = "/sdcard/agent_bridge_window.xml";
pub(super) const MOBILE_DEFAULT_TIMEOUT_MS: u64 = 30_000;

/// Additive observation identity for UIAutomator snapshots.  The existing
/// compact node payload remains unchanged; this metadata lets an action bind
/// itself to the exact read without pretending that UIAutomator ordinals are
/// stable across captures.
pub(super) fn mobile_ui_observation_metadata(
    serial: &str,
    nodes: &[MobileUiNode],
    raw_xml: &str,
) -> Value {
    let observed_at_unix_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64;
    let compact_nodes: Vec<Value> = nodes.iter().map(MobileUiNode::compact_json).collect();
    let canonical =
        serde_json::to_vec(&json!({"serial": serial, "nodes": compact_nodes})).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(&canonical);
    hasher.update(raw_xml.as_bytes());
    let content_hash = format!("sha256:{:x}", hasher.finalize());
    json!({
        "observation_id": format!("mobile-ui:{serial}:{}", &content_hash[7..23]),
        "observed_at_unix_ms": observed_at_unix_ms,
        "revision": observed_at_unix_ms,
        "revision_semantics": "capture_unix_milliseconds; ordering hint only",
        "content_hash": content_hash,
        "max_age_ms": 2_000,
        "coordinate_provenance": {
            "source": "uiautomator",
            "serial": serial,
            "coordinate_space": "android.screen.px",
            "bounds_semantics": "node bounds reported by UIAutomator"
        }
    })
}

/// Convert the verified, read-only `app_control playlist_current` payload into
/// the bounded media context carried by a projection frame. Keeping this
/// conversion here makes the sync tool unable to smuggle control fields into
/// the projection protocol.
pub(super) fn media_context_from_app_control(
    payload: &Value,
    observed_at_unix_seconds: i64,
) -> std::result::Result<crate::mobile_projection::MediaContext, String> {
    if payload.get("schema").and_then(Value::as_str) != Some("agent_bridge.app_control.v0")
        || payload.get("verdict").and_then(Value::as_str) != Some("verified")
        || payload.get("action").and_then(Value::as_str) != Some("playlist_current")
    {
        return Err("app_control playlist_current result was not verified".into());
    }
    let playlist = payload
        .get("active_playlist")
        .and_then(Value::as_object)
        .ok_or_else(|| "app_control result missing active_playlist".to_string())?;
    let track = payload
        .get("track_summary")
        .and_then(Value::as_object)
        .ok_or_else(|| "app_control result missing track_summary".to_string())?;
    let mut context = crate::mobile_projection::MediaContext::new(observed_at_unix_seconds);
    context.player = track
        .get("player")
        .and_then(Value::as_str)
        .map(str::to_owned);
    context.active_playlist_id = playlist
        .get("id")
        .and_then(Value::as_str)
        .map(str::to_owned);
    context.active_playlist_name = playlist
        .get("name")
        .and_then(Value::as_str)
        .map(str::to_owned);
    context.playback_status = track
        .get("playback_status")
        .and_then(Value::as_str)
        .map(str::to_owned);
    context.track_id = track
        .get("track_id")
        .and_then(Value::as_str)
        .map(str::to_owned);
    context.artist = track
        .get("artist")
        .and_then(Value::as_str)
        .map(str::to_owned);
    context.title = track
        .get("title")
        .and_then(Value::as_str)
        .map(str::to_owned);
    context.position_seconds = track.get("position_seconds").and_then(Value::as_f64);
    context.duration_seconds = track
        .get("duration_seconds")
        .and_then(Value::as_f64)
        .filter(|value| value.is_finite() && *value > 0.0);
    context.metadata_available = track
        .get("metadata_available")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    Ok(context)
}

/// Preserve the read-only player-selection evidence in the projection response.
/// This is intentionally a pure projection of the verified app-control payload;
/// it cannot add control capabilities or fabricate a selection result.
pub(super) fn mobile_projection_app_control_evidence(payload: &Value) -> Value {
    json!({
        "action": payload.get("action").cloned().unwrap_or(Value::Null),
        "read_only": true,
        "verdict": payload.get("verdict").cloned().unwrap_or(Value::Null),
        "player": payload.get("player").cloned().unwrap_or(Value::Null),
        "players": payload.get("players").cloned().unwrap_or(Value::Null),
        "selection": payload.get("selection").cloned().unwrap_or(Value::Null),
        "error": payload.get("error").cloned().unwrap_or(Value::Null)
    })
}

/// Map only target-selection failures into an honest projection replacement.
/// Other app-control failures remain errors and must not mutate the projection.
pub(super) fn mobile_projection_media_unavailable(payload: &Value) -> Option<Value> {
    if payload.get("schema").and_then(Value::as_str) != Some("agent_bridge.app_control.v0")
        || payload.get("action").and_then(Value::as_str) != Some("playlist_current")
        || payload.get("verdict").and_then(Value::as_str) != Some("error")
    {
        return None;
    }
    let code = payload
        .get("error")
        .and_then(|value| value.get("code"))
        .and_then(Value::as_str)?;
    let (body, status) = match code {
        "no_mpris_player" => (
            "No active media player is available.",
            "Start a player to sync media",
        ),
        "ambiguous_player" => (
            "More than one media player is available.",
            "Choose a player and sync again",
        ),
        "player_selection_incomplete" => (
            "Media player state could not be observed completely.",
            "Retry or choose a player explicitly",
        ),
        _ => return None,
    };
    Some(json!({
        "code": code,
        "title": "Media unavailable",
        "body": body,
        "status": status,
        "media_context": Value::Null,
    }))
}

fn format_media_clock(seconds: Option<f64>) -> String {
    let Some(seconds) = seconds.filter(|value| value.is_finite() && *value >= 0.0) else {
        return "??:??".into();
    };
    let total = seconds.round() as u64;
    format!("{:02}:{:02}", total / 60, total % 60)
}

fn format_media_progress(position_seconds: Option<f64>, duration_seconds: Option<f64>) -> String {
    let position = position_seconds.filter(|value| value.is_finite() && *value >= 0.0);
    let duration = duration_seconds.filter(|value| value.is_finite() && *value > 0.0);
    match (position, duration) {
        (Some(position), Some(duration)) => format!(
            "{} / {}",
            format_media_clock(Some(position)),
            format_media_clock(Some(duration))
        ),
        (Some(position), None) => format_media_clock(Some(position)),
        (None, Some(duration)) => format!("时长 {}", format_media_clock(Some(duration))),
        (None, None) => "时间未知".into(),
    }
}

fn truncate_display(value: &str, max_chars: usize, fallback: &str) -> String {
    if value.is_empty() {
        return fallback.into();
    }
    let mut chars = value.chars();
    let prefix: String = chars.by_ref().take(max_chars).collect();
    if chars.next().is_some() {
        let keep = max_chars.saturating_sub(1);
        format!("{}…", prefix.chars().take(keep).collect::<String>())
    } else {
        prefix
    }
}

fn display_playback_status(value: Option<&str>) -> String {
    match value.unwrap_or("Unknown") {
        "Playing" => "播放中".into(),
        "Paused" => "已暂停".into(),
        "Stopped" => "已停止".into(),
        "Unknown" | "" => "未知状态".into(),
        other => truncate_display(other, 32, "未知状态"),
    }
}

pub(super) fn media_projection_presentation(
    context: &crate::mobile_projection::MediaContext,
) -> (String, String, String) {
    let title = truncate_display(context.title.as_deref().unwrap_or(""), 96, "未播放曲目");
    let artist = truncate_display(context.artist.as_deref().unwrap_or(""), 48, "未知艺术家");
    let playlist = truncate_display(
        context.active_playlist_name.as_deref().unwrap_or(""),
        64,
        "未选择播放列表",
    );
    let status = display_playback_status(context.playback_status.as_deref());
    let body = format!(
        "{} · {}\n{} · {}\n播放列表：{}",
        artist,
        title,
        status,
        format_media_progress(context.position_seconds, context.duration_seconds),
        playlist,
    );
    ("媒体状态 · 已同步".into(), body, status)
}

#[derive(Debug, Clone)]
pub(super) struct AdbCommandOutput {
    pub(super) exit_code: i32,
    pub(super) stdout: String,
    pub(super) stderr: String,
    pub(super) duration_ms: u64,
    pub(super) truncated: bool,
}

impl AdbCommandOutput {
    pub(super) fn ok(&self) -> bool {
        self.exit_code == 0
    }

    pub(super) fn as_json(&self) -> Value {
        json!({
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "truncated": self.truncated,
        })
    }
}

#[derive(Debug, Clone)]
pub(super) struct AdbBinaryOutput {
    pub(super) exit_code: i32,
    pub(super) stdout: Vec<u8>,
    pub(super) stderr: String,
    pub(super) duration_ms: u64,
    pub(super) stderr_truncated: bool,
}

impl AdbBinaryOutput {
    pub(super) fn ok(&self) -> bool {
        self.exit_code == 0
    }

    pub(super) fn as_json(&self) -> Value {
        json!({
            "exit_code": self.exit_code,
            "stdout_bytes": self.stdout.len(),
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "stderr_truncated": self.stderr_truncated,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct MobileDevice {
    // pub(super): the capabilities/doctor readouts in the parent module read
    // these fields directly.
    pub(super) serial: String,
    pub(super) state: String,
    pub(super) attrs: HashMap<String, String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(super) struct MobileBounds {
    pub(super) left: i64,
    pub(super) top: i64,
    pub(super) right: i64,
    pub(super) bottom: i64,
}

impl MobileBounds {
    pub(super) fn center(self) -> (i64, i64) {
        ((self.left + self.right) / 2, (self.top + self.bottom) / 2)
    }

    pub(super) fn as_json(self) -> Value {
        let (x, y) = self.center();
        json!({
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "center": { "x": x, "y": y },
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct MobileUiNode {
    pub(super) ordinal: usize,
    pub(super) index: String,
    pub(super) text: String,
    pub(super) resource_id: String,
    pub(super) class_name: String,
    pub(super) package_name: String,
    pub(super) content_desc: String,
    pub(super) clickable: bool,
    pub(super) enabled: bool,
    pub(super) focusable: bool,
    pub(super) focused: bool,
    pub(super) scrollable: bool,
    pub(super) bounds: Option<MobileBounds>,
}

impl MobileUiNode {
    pub(super) fn has_semantic_label(&self) -> bool {
        !self.text.is_empty() || !self.resource_id.is_empty() || !self.content_desc.is_empty()
    }

    pub(super) fn is_actionable(&self) -> bool {
        self.clickable || self.focusable || self.scrollable || self.has_semantic_label()
    }

    pub(super) fn is_surface_view(&self) -> bool {
        self.class_name == "android.view.SurfaceView"
    }

    pub(super) fn compact_json(&self) -> Value {
        let mut obj = Map::new();
        obj.insert("ordinal".into(), json!(self.ordinal));
        if !self.index.is_empty() {
            obj.insert("index".into(), json!(self.index));
        }
        if !self.text.is_empty() {
            obj.insert("text".into(), json!(self.text));
        }
        if !self.resource_id.is_empty() {
            obj.insert("resource_id".into(), json!(self.resource_id));
        }
        if !self.class_name.is_empty() {
            obj.insert("class".into(), json!(self.class_name));
        }
        if !self.package_name.is_empty() {
            obj.insert("package".into(), json!(self.package_name));
        }
        if !self.content_desc.is_empty() {
            obj.insert("content_desc".into(), json!(self.content_desc));
        }
        if self.clickable {
            obj.insert("clickable".into(), json!(true));
        }
        if self.focusable {
            obj.insert("focusable".into(), json!(true));
        }
        if self.focused {
            obj.insert("focused".into(), json!(true));
        }
        if self.scrollable {
            obj.insert("scrollable".into(), json!(true));
        }
        obj.insert("enabled".into(), json!(self.enabled));
        if let Some(bounds) = self.bounds {
            obj.insert("bounds".into(), bounds.as_json());
        }
        Value::Object(obj)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(super) struct MobileUiAnalysis {
    pub(super) node_count: usize,
    pub(super) semantic_node_count: usize,
    pub(super) actionable_node_count: usize,
    pub(super) surface_view_count: usize,
    pub(super) focused_surface_view_count: usize,
    pub(super) semantic_nodes: bool,
    pub(super) canvas_only: bool,
    pub(super) surface_dominated: bool,
}

impl MobileUiAnalysis {
    pub(super) fn from_nodes(nodes: &[MobileUiNode]) -> Self {
        let semantic_node_count = nodes.iter().filter(|n| n.has_semantic_label()).count();
        let actionable_node_count = nodes.iter().filter(|n| n.is_actionable()).count();
        let surface_view_count = nodes.iter().filter(|n| n.is_surface_view()).count();
        let focused_surface_view_count = nodes
            .iter()
            .filter(|n| n.is_surface_view() && n.focused)
            .count();
        let semantic_nodes = semantic_node_count > 0;
        let canvas_only = surface_view_count > 0 && !semantic_nodes;
        let surface_dominated = surface_view_count > 0 && semantic_node_count <= 2;
        Self {
            node_count: nodes.len(),
            semantic_node_count,
            actionable_node_count,
            surface_view_count,
            focused_surface_view_count,
            semantic_nodes,
            canvas_only,
            surface_dominated,
        }
    }

    pub(super) fn as_json(self) -> Value {
        json!({
            "node_count": self.node_count,
            "semantic_node_count": self.semantic_node_count,
            "actionable_node_count": self.actionable_node_count,
            "surface_view_count": self.surface_view_count,
            "focused_surface_view_count": self.focused_surface_view_count,
            "semantic_nodes": self.semantic_nodes,
            "canvas_only": self.canvas_only,
            "surface_dominated": self.surface_dominated,
            "hint": if self.canvas_only {
                "UIAutomator sees a SurfaceView/canvas shell but no semantic child controls; use screenshot or engine-side hooks for in-canvas targets."
            } else if self.surface_dominated {
                "UIAutomator sees a SurfaceView/canvas app with limited semantic overlays; selector actions may only work for native overlays."
            } else {
                "UIAutomator exposes semantic nodes; prefer selectors over coordinates when possible."
            },
        })
    }
}

#[derive(Debug, Clone, Default)]
pub(super) struct MobileSelector {
    pub(super) text: Option<String>,
    pub(super) text_contains: Option<String>,
    pub(super) resource_id: Option<String>,
    pub(super) content_desc: Option<String>,
    pub(super) class_name: Option<String>,
    pub(super) package_name: Option<String>,
    pub(super) clickable: Option<bool>,
    pub(super) focused: Option<bool>,
    pub(super) enabled: Option<bool>,
}

impl MobileSelector {
    pub(super) fn from_value(value: &Value) -> std::result::Result<Self, String> {
        let Some(obj) = value.as_object() else {
            return Err("'selector' must be an object".to_string());
        };
        let selector = Self {
            text: obj
                .get("text")
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(str::to_string),
            text_contains: obj
                .get("text_contains")
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(str::to_string),
            resource_id: obj
                .get("resource_id")
                .or_else(|| obj.get("resource-id"))
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(str::to_string),
            content_desc: obj
                .get("content_desc")
                .or_else(|| obj.get("content-desc"))
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(str::to_string),
            class_name: obj
                .get("class")
                .or_else(|| obj.get("class_name"))
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(str::to_string),
            package_name: obj
                .get("package")
                .or_else(|| obj.get("package_name"))
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(str::to_string),
            clickable: obj.get("clickable").and_then(|v| v.as_bool()),
            focused: obj.get("focused").and_then(|v| v.as_bool()),
            enabled: obj.get("enabled").and_then(|v| v.as_bool()),
        };
        if selector.is_empty() {
            return Err("selector must include at least one matching field".to_string());
        }
        Ok(selector)
    }

    pub(super) fn is_empty(&self) -> bool {
        self.text.is_none()
            && self.text_contains.is_none()
            && self.resource_id.is_none()
            && self.content_desc.is_none()
            && self.class_name.is_none()
            && self.package_name.is_none()
            && self.clickable.is_none()
            && self.focused.is_none()
            && self.enabled.is_none()
    }

    pub(super) fn matches(&self, node: &MobileUiNode) -> bool {
        if let Some(expected) = &self.text {
            if &node.text != expected {
                return false;
            }
        }
        if let Some(expected) = &self.text_contains {
            if !node.text.contains(expected) {
                return false;
            }
        }
        if let Some(expected) = &self.resource_id {
            if &node.resource_id != expected {
                return false;
            }
        }
        if let Some(expected) = &self.content_desc {
            if &node.content_desc != expected {
                return false;
            }
        }
        if let Some(expected) = &self.class_name {
            if &node.class_name != expected {
                return false;
            }
        }
        if let Some(expected) = &self.package_name {
            if &node.package_name != expected {
                return false;
            }
        }
        if let Some(expected) = self.clickable {
            if node.clickable != expected {
                return false;
            }
        }
        if let Some(expected) = self.focused {
            if node.focused != expected {
                return false;
            }
        }
        if let Some(expected) = self.enabled {
            if node.enabled != expected {
                return false;
            }
        }
        true
    }
}

pub(super) fn mobile_schema_serial() -> Value {
    json!({
        "type": "string",
        "description": "ADB serial. Required when multiple online devices are connected."
    })
}

pub(super) fn mobile_schema_selector() -> Value {
    json!({
        "type": "object",
        "description": "UI Automator node selector. All supplied fields must match.",
        "properties": {
            "text": { "type": "string" },
            "text_contains": { "type": "string" },
            "resource_id": { "type": "string" },
            "resource-id": { "type": "string" },
            "content_desc": { "type": "string" },
            "content-desc": { "type": "string" },
            "class": { "type": "string" },
            "package": { "type": "string" },
            "clickable": { "type": "boolean" },
            "focused": { "type": "boolean" },
            "enabled": { "type": "boolean" }
        }
    })
}

pub(super) fn adb_args(parts: &[&str]) -> Vec<String> {
    parts.iter().map(|s| (*s).to_string()).collect()
}

pub(super) fn mobile_timeout_ms(args: &Value) -> u64 {
    args.get("timeout_ms")
        .and_then(|v| v.as_u64())
        .unwrap_or(MOBILE_DEFAULT_TIMEOUT_MS)
        .clamp(1_000, 120_000)
}

pub(super) fn resolve_adb_bin() -> String {
    if let Ok(v) = std::env::var("AGENT_BRIDGE_ADB") {
        if !v.trim().is_empty() {
            return v;
        }
    }
    if let Ok(v) = std::env::var("ADB") {
        if !v.trim().is_empty() {
            return v;
        }
    }
    if let Ok(home) = std::env::var("ANDROID_HOME") {
        let candidate = PathBuf::from(home).join("platform-tools").join("adb");
        if candidate.exists() {
            return candidate.to_string_lossy().into_owned();
        }
    }
    for candidate in [
        "/opt/homebrew/share/android-commandlinetools/platform-tools/adb",
        "/opt/homebrew/bin/adb",
        "/usr/local/bin/adb",
    ] {
        if PathBuf::from(candidate).exists() {
            return candidate.to_string();
        }
    }
    "adb".to_string()
}

pub(super) async fn run_adb_command(
    serial: Option<&str>,
    args: &[String],
    timeout_ms: u64,
) -> std::result::Result<AdbCommandOutput, String> {
    let mut cmd = killable_command(resolve_adb_bin());
    if let Some(serial) = serial.filter(|s| !s.trim().is_empty()) {
        cmd.arg("-s").arg(serial);
    }
    cmd.args(args);
    cmd.stdin(std::process::Stdio::null());
    cmd.stdout(std::process::Stdio::piped());
    cmd.stderr(std::process::Stdio::piped());

    let started = Instant::now();
    let out = tokio::time::timeout(Duration::from_millis(timeout_ms), cmd.output()).await;
    let duration_ms = started.elapsed().as_millis() as u64;
    let output = match out {
        Ok(Ok(output)) => output,
        Ok(Err(e)) => return Err(format!("spawn adb failed: {e}")),
        Err(_) => {
            return Ok(AdbCommandOutput {
                exit_code: -1,
                stdout: String::new(),
                stderr: format!("killed after {timeout_ms} ms timeout"),
                duration_ms,
                truncated: false,
            });
        }
    };
    let (stdout, stdout_truncated) = lossy_truncate(&output.stdout);
    let (stderr, stderr_truncated) = lossy_truncate(&output.stderr);
    Ok(AdbCommandOutput {
        exit_code: output.status.code().unwrap_or(-1),
        stdout,
        stderr,
        duration_ms,
        truncated: stdout_truncated || stderr_truncated,
    })
}

pub(super) async fn run_adb_binary_command(
    serial: Option<&str>,
    args: &[String],
    timeout_ms: u64,
) -> std::result::Result<AdbBinaryOutput, String> {
    let mut cmd = killable_command(resolve_adb_bin());
    if let Some(serial) = serial.filter(|s| !s.trim().is_empty()) {
        cmd.arg("-s").arg(serial);
    }
    cmd.args(args);
    cmd.stdin(std::process::Stdio::null());
    cmd.stdout(std::process::Stdio::piped());
    cmd.stderr(std::process::Stdio::piped());

    let started = Instant::now();
    let out = tokio::time::timeout(Duration::from_millis(timeout_ms), cmd.output()).await;
    let duration_ms = started.elapsed().as_millis() as u64;
    let output = match out {
        Ok(Ok(output)) => output,
        Ok(Err(e)) => return Err(format!("spawn adb failed: {e}")),
        Err(_) => {
            return Ok(AdbBinaryOutput {
                exit_code: -1,
                stdout: Vec::new(),
                stderr: format!("killed after {timeout_ms} ms timeout"),
                duration_ms,
                stderr_truncated: false,
            });
        }
    };
    let (stderr, stderr_truncated) = lossy_truncate(&output.stderr);
    Ok(AdbBinaryOutput {
        exit_code: output.status.code().unwrap_or(-1),
        stdout: output.stdout,
        stderr,
        duration_ms,
        stderr_truncated,
    })
}

pub(super) fn parse_adb_devices(stdout: &str) -> Vec<MobileDevice> {
    stdout
        .lines()
        .filter_map(|line| {
            let line = line.trim();
            if line.is_empty() || line.starts_with("List of devices") {
                return None;
            }
            let mut parts = line.split_whitespace();
            let serial = parts.next()?.to_string();
            let state = parts.next()?.to_string();
            let attrs = parts
                .filter_map(|part| {
                    let (k, v) = part.split_once(':')?;
                    Some((k.to_string(), v.to_string()))
                })
                .collect();
            Some(MobileDevice {
                serial,
                state,
                attrs,
            })
        })
        .collect()
}

pub(super) fn mobile_device_json(device: &MobileDevice, android_version: Option<String>) -> Value {
    let mut obj = Map::new();
    obj.insert("serial".into(), json!(device.serial));
    obj.insert("state".into(), json!(device.state));
    for (k, v) in &device.attrs {
        obj.insert(k.clone(), json!(v));
    }
    if let Some(version) = android_version.filter(|s| !s.is_empty()) {
        obj.insert("android_version".into(), json!(version));
    }
    Value::Object(obj)
}

pub(super) async fn mobile_online_devices(
    timeout_ms: u64,
) -> std::result::Result<Vec<MobileDevice>, String> {
    let out = run_adb_command(None, &adb_args(&["devices", "-l"]), timeout_ms).await?;
    if !out.ok() {
        return Err(format!("adb devices failed: {}", out.stderr.trim()));
    }
    Ok(parse_adb_devices(&out.stdout)
        .into_iter()
        .filter(|d| d.state == "device")
        .collect())
}

pub(super) async fn resolve_mobile_serial(
    args: &Value,
    timeout_ms: u64,
) -> std::result::Result<String, String> {
    if let Some(serial) = args
        .get("serial")
        .and_then(|v| v.as_str())
        .filter(|s| !s.trim().is_empty())
    {
        return Ok(serial.to_string());
    }
    let devices = mobile_online_devices(timeout_ms).await?;
    match devices.len() {
        0 => Err("no online ADB devices found".to_string()),
        1 => Ok(devices[0].serial.clone()),
        _ => Err(format!(
            "multiple online devices found; pass serial (available: {})",
            devices
                .iter()
                .map(|d| d.serial.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        )),
    }
}

pub(super) async fn mobile_getprop(serial: &str, prop: &str, timeout_ms: u64) -> Option<String> {
    let args = vec!["shell".to_string(), "getprop".to_string(), prop.to_string()];
    let out = run_adb_command(Some(serial), &args, timeout_ms)
        .await
        .ok()?;
    if out.ok() {
        Some(out.stdout.trim().to_string())
    } else {
        None
    }
}

pub(super) fn parse_focus_lines(stdout: &str) -> Vec<String> {
    stdout
        .lines()
        .map(str::trim)
        .filter(|line| {
            line.contains("mCurrentFocus")
                || line.contains("mFocusedApp")
                || line.contains("topResumedActivity")
        })
        .map(str::to_string)
        .collect()
}

pub(super) fn focus_token_package(token: &str) -> Option<String> {
    let clean = token.trim_matches(|c: char| {
        c == '{' || c == '}' || c == ')' || c == '(' || c == ',' || c == ';'
    });
    let (pkg, _) = clean.split_once('/')?;
    if pkg.contains('.')
        && pkg
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '.')
    {
        Some(pkg.to_string())
    } else {
        None
    }
}

pub(super) fn parse_foreground_package(focus_lines: &[String]) -> Option<String> {
    for line in focus_lines {
        for token in line.split_whitespace() {
            if let Some(pkg) = focus_token_package(token) {
                return Some(pkg);
            }
        }
    }
    None
}

pub(super) fn summarize_mobile_logcat(stdout: &str, package: Option<&str>) -> Value {
    let mut fatal_count = 0usize;
    let mut error_count = 0usize;
    let mut warning_count = 0usize;
    let mut surface_line_count = 0usize;
    let mut package_mentions = 0usize;
    let mut markers = Vec::new();
    let mut push_marker = |kind: &str, line: &str| {
        if markers.len() >= 30 {
            return;
        }
        let (text, truncated, total_chars) = truncate_chars(line, 500);
        markers.push(json!({
            "kind": kind,
            "line": text,
            "truncated": truncated,
            "total_chars": total_chars,
        }));
    };

    for line in stdout.lines() {
        let lower = line.to_ascii_lowercase();
        let package_hit = package.map(|pkg| line.contains(pkg)).unwrap_or(false);
        if package_hit {
            package_mentions += 1;
        }

        let is_fatal = line.contains("FATAL EXCEPTION")
            || lower.contains("fatal signal")
            || lower.contains("androidruntime")
            || lower.contains(" anr ")
            || lower.contains(" crash");
        let is_error = is_fatal
            || line.contains(" E ")
            || line.contains(" E/")
            || (lower.contains("exception") && (line.contains(" E ") || package_hit));
        let is_warning = line.contains(" W ") || line.contains(" W/");
        let is_surface = lower.contains("surfaceview")
            || lower.contains("surfaceflinger")
            || lower.contains("choreographer")
            || lower.contains("fps")
            || lower.contains("godot");

        if is_fatal {
            fatal_count += 1;
            push_marker("fatal", line);
        } else if is_error {
            error_count += 1;
            push_marker("error", line);
        } else if is_warning {
            warning_count += 1;
        }
        if is_surface {
            surface_line_count += 1;
        }
    }

    json!({
        "line_count": stdout.lines().count(),
        "fatal_count": fatal_count,
        "error_count": error_count,
        "warning_count": warning_count,
        "surface_line_count": surface_line_count,
        "package_mentions": package_mentions,
        "has_crash_markers": fatal_count > 0,
        "markers": markers,
    })
}

pub(super) fn parse_mobile_bounds(raw: &str) -> Option<MobileBounds> {
    let nums: Vec<i64> = raw
        .split(|c| matches!(c, '[' | ']' | ','))
        .filter(|s| !s.trim().is_empty())
        .filter_map(|s| s.trim().parse::<i64>().ok())
        .collect();
    if nums.len() == 4 {
        Some(MobileBounds {
            left: nums[0],
            top: nums[1],
            right: nums[2],
            bottom: nums[3],
        })
    } else {
        None
    }
}

pub(super) fn attr_bool(attrs: &HashMap<String, String>, key: &str) -> bool {
    attrs.get(key).map(|v| v == "true").unwrap_or(false)
}

pub(super) fn decode_xml_attr_value(raw: &str) -> String {
    raw.replace("&quot;", "\"")
        .replace("&apos;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
}

pub(super) fn parse_xml_attrs(tag_body: &str) -> HashMap<String, String> {
    let mut attrs = HashMap::new();
    let bytes = tag_body.as_bytes();
    let mut i = 0usize;
    while i < bytes.len() {
        while i < bytes.len() && (bytes[i].is_ascii_whitespace() || bytes[i] == b'/') {
            i += 1;
        }
        let key_start = i;
        while i < bytes.len()
            && !bytes[i].is_ascii_whitespace()
            && bytes[i] != b'='
            && bytes[i] != b'/'
        {
            i += 1;
        }
        if key_start == i {
            i += 1;
            continue;
        }
        let key = &tag_body[key_start..i];
        while i < bytes.len() && bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        if i >= bytes.len() || bytes[i] != b'=' {
            continue;
        }
        i += 1;
        while i < bytes.len() && bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        if i >= bytes.len() || (bytes[i] != b'"' && bytes[i] != b'\'') {
            continue;
        }
        let quote = bytes[i];
        i += 1;
        let value_start = i;
        while i < bytes.len() && bytes[i] != quote {
            i += 1;
        }
        if i > bytes.len() {
            break;
        }
        let value = decode_xml_attr_value(&tag_body[value_start..i]);
        attrs.insert(key.to_string(), value);
        i += 1;
    }
    attrs
}

pub(super) fn node_from_attrs(ordinal: usize, attrs: HashMap<String, String>) -> MobileUiNode {
    let bounds = attrs.get("bounds").and_then(|s| parse_mobile_bounds(s));
    MobileUiNode {
        ordinal,
        index: attrs.get("index").cloned().unwrap_or_default(),
        text: attrs.get("text").cloned().unwrap_or_default(),
        resource_id: attrs.get("resource-id").cloned().unwrap_or_default(),
        class_name: attrs.get("class").cloned().unwrap_or_default(),
        package_name: attrs.get("package").cloned().unwrap_or_default(),
        content_desc: attrs.get("content-desc").cloned().unwrap_or_default(),
        clickable: attr_bool(&attrs, "clickable"),
        enabled: attrs.get("enabled").map(|v| v == "true").unwrap_or(true),
        focusable: attr_bool(&attrs, "focusable"),
        focused: attr_bool(&attrs, "focused"),
        scrollable: attr_bool(&attrs, "scrollable"),
        bounds,
    }
}

pub(super) fn parse_uiautomator_nodes(xml: &str) -> std::result::Result<Vec<MobileUiNode>, String> {
    let mut nodes = Vec::new();
    let mut search_start = 0usize;
    while let Some(rel) = xml[search_start..].find("<node") {
        let tag_start = search_start + rel;
        let after_name = tag_start + "<node".len();
        let next = xml[after_name..].chars().next();
        if !matches!(next, Some(c) if c.is_ascii_whitespace() || c == '/' || c == '>') {
            search_start = after_name;
            continue;
        }
        let Some(tag_end_rel) = xml[tag_start..].find('>') else {
            return Err("unterminated <node> tag in UI XML".to_string());
        };
        let tag_end = tag_start + tag_end_rel;
        let tag_body = &xml[after_name..tag_end];
        let attrs = parse_xml_attrs(tag_body);
        let ordinal = nodes.len();
        nodes.push(node_from_attrs(ordinal, attrs));
        search_start = tag_end + 1;
    }
    Ok(nodes)
}

pub(super) async fn mobile_dump_ui_xml(
    serial: &str,
    timeout_ms: u64,
) -> std::result::Result<(AdbCommandOutput, AdbCommandOutput), String> {
    let dump_args = vec![
        "shell".to_string(),
        "uiautomator".to_string(),
        "dump".to_string(),
        MOBILE_UI_DUMP_PATH.to_string(),
    ];
    let dump = run_adb_command(Some(serial), &dump_args, timeout_ms).await?;
    if !dump.ok() {
        return Err(format!("uiautomator dump failed: {}", dump.stderr.trim()));
    }
    let cat_args = vec![
        "exec-out".to_string(),
        "cat".to_string(),
        MOBILE_UI_DUMP_PATH.to_string(),
    ];
    let cat = run_adb_command(Some(serial), &cat_args, timeout_ms).await?;
    if !cat.ok() {
        return Err(format!("read UI XML failed: {}", cat.stderr.trim()));
    }
    Ok((dump, cat))
}

pub(super) fn sanitize_mobile_path_component(s: &str) -> String {
    let sanitized: String = s
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                c
            } else {
                '-'
            }
        })
        .collect();
    if sanitized.is_empty() {
        "device".to_string()
    } else {
        sanitized
    }
}

pub(super) fn mobile_screenshot_path(args: &Value, serial: &str) -> PathBuf {
    if let Some(path) = args
        .get("path")
        .and_then(|v| v.as_str())
        .filter(|s| !s.trim().is_empty())
    {
        return PathBuf::from(path);
    }
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    std::env::temp_dir().join(format!(
        "agent-bridge-mobile-screenshot-{}-{ts}.png",
        sanitize_mobile_path_component(serial)
    ))
}

pub(super) fn mobile_debug_bundle_path(parent: &Path, serial: &str, now: u64) -> PathBuf {
    parent.join(format!(
        "agent-bridge-mobile-debug-{}-{now}",
        sanitize_mobile_path_component(serial)
    ))
}

pub(super) fn write_mobile_bundle_text(
    path: &Path,
    body: &str,
) -> std::result::Result<u64, String> {
    std::fs::write(path, body).map_err(|e| format!("write {} failed: {e}", path.display()))?;
    harden_mobile_bundle_path(path, false)?;
    Ok(body.len() as u64)
}

pub(super) fn harden_mobile_bundle_path(
    path: &Path,
    directory: bool,
) -> std::result::Result<(), String> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = if directory { 0o700 } else { 0o600 };
        std::fs::set_permissions(path, std::fs::Permissions::from_mode(mode))
            .map_err(|e| format!("set private permissions on {} failed: {e}", path.display()))?;
    }
    #[cfg(not(unix))]
    let _ = (path, directory);
    Ok(())
}

fn record_mobile_bundle_text(
    bundle: &Path,
    name: &str,
    filename: &str,
    out: std::result::Result<AdbCommandOutput, String>,
    artifacts: &mut Vec<Value>,
) -> bool {
    match out {
        Ok(out) if out.ok() => {
            let path = bundle.join(filename);
            match write_mobile_bundle_text(&path, &out.stdout) {
                Ok(bytes) => artifacts.push(json!({ "name": name, "path": path, "status": "ok", "bytes": bytes, "truncated": out.truncated })),
                Err(e) => {
                    artifacts.push(json!({ "name": name, "status": "error", "error": e }));
                    return true;
                }
            }
            false
        }
        Ok(out) => {
            artifacts.push(json!({ "name": name, "status": "error", "adb": out.as_json() }));
            true
        }
        Err(e) => {
            artifacts.push(json!({ "name": name, "status": "error", "error": e }));
            true
        }
    }
}

pub(super) fn adb_input_text_arg(text: &str) -> String {
    text.replace(' ', "%s")
}

macro_rules! mobile_tool_struct {
    ($name:ident) => {
        pub struct $name {
            hub: Hub,
        }
        impl $name {
            pub fn new(hub: Hub) -> Self {
                Self { hub }
            }
        }
    };
}

mobile_tool_struct!(MobileListDevicesTool);
#[async_trait]
impl McpTool for MobileListDevicesTool {
    fn name(&self) -> &'static str {
        "mobile_list_devices"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "List Android devices visible to ADB. Returns serials, connection \
                 state, `adb devices -l` attributes, and optional Android version/model \
                 properties. Use before any mobile_* action when multiple devices may be \
                 connected."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "include_props": { "type": "boolean", "default": true, "description": "Read model and Android version via getprop for online devices." },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let include_props = args
            .get("include_props")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);
        let out = match run_adb_command(None, &adb_args(&["devices", "-l"]), timeout_ms).await {
            Ok(out) => out,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        if !out.ok() {
            return Ok(ToolResult::json_text(&json!({
                "status": "error",
                "adb": out.as_json(),
            })));
        }
        let devices = parse_adb_devices(&out.stdout);
        let mut rows = Vec::new();
        for device in &devices {
            let android_version = if include_props && device.state == "device" {
                mobile_getprop(&device.serial, "ro.build.version.release", timeout_ms).await
            } else {
                None
            };
            rows.push(mobile_device_json(device, android_version));
        }
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "adb_bin": resolve_adb_bin(),
            "count": rows.len(),
            "devices": rows,
        })))
    }
}

mobile_tool_struct!(MobileCurrentFocusTool);
#[async_trait]
impl McpTool for MobileCurrentFocusTool {
    fn name(&self) -> &'static str {
        "mobile_current_focus"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read the current Android foreground window/activity via `dumpsys \
                 window`, without taking a screenshot."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "serial": mobile_schema_serial(),
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let serial = match resolve_mobile_serial(&args, timeout_ms).await {
            Ok(s) => s,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let out = match run_adb_command(
            Some(&serial),
            &adb_args(&["shell", "dumpsys", "window"]),
            timeout_ms,
        )
        .await
        {
            Ok(out) => out,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        if !out.ok() {
            return Ok(ToolResult::json_text(&json!({
                "status": "error",
                "serial": serial,
                "adb": out.as_json(),
            })));
        }
        let focus_lines = parse_focus_lines(&out.stdout);
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "serial": serial,
            "focus_lines": focus_lines,
            "duration_ms": out.duration_ms,
        })))
    }
}

mobile_tool_struct!(MobileScreenshotTool);
#[async_trait]
impl McpTool for MobileScreenshotTool {
    fn name(&self) -> &'static str {
        "mobile_screenshot"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Capture an Android device screenshot through `adb exec-out screencap \
                 -p`. Returns a saved PNG path by default, or an inline image block when \
                 `inline=true`."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "serial": mobile_schema_serial(),
                    "path": { "type": "string", "description": "Optional local output path. Defaults to a PNG under the system temp directory when inline=false." },
                    "inline": { "type": "boolean", "default": false, "description": "Return the PNG as an MCP image block instead of only saving it to disk." },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let serial = match resolve_mobile_serial(&args, timeout_ms).await {
            Ok(s) => s,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let out = match run_adb_binary_command(
            Some(&serial),
            &adb_args(&["exec-out", "screencap", "-p"]),
            timeout_ms,
        )
        .await
        {
            Ok(out) => out,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        if !out.ok() {
            return Ok(ToolResult::json_text(&json!({
                "status": "error",
                "serial": serial,
                "adb": out.as_json(),
            })));
        }
        const PNG_SIGNATURE: &[u8] = &[137, 80, 78, 71, 13, 10, 26, 10];
        if !out.stdout.starts_with(PNG_SIGNATURE) {
            return Ok(ToolResult::json_text(&json!({
                "status": "error",
                "serial": serial,
                "error": "screencap output did not start with a PNG signature",
                "adb": out.as_json(),
            })));
        }

        let inline = args
            .get("inline")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let explicit_path = args
            .get("path")
            .and_then(|v| v.as_str())
            .filter(|s| !s.trim().is_empty())
            .is_some();
        let should_write = explicit_path || !inline;
        let mut path_value = Value::Null;
        if should_write {
            let path = mobile_screenshot_path(&args, &serial);
            if let Some(parent) = path.parent() {
                if !parent.as_os_str().is_empty() && !parent.exists() {
                    return Ok(ToolResult::error(format!(
                        "screenshot parent directory does not exist: {}",
                        parent.to_string_lossy()
                    )));
                }
            }
            if let Err(e) = std::fs::write(&path, &out.stdout) {
                return Ok(ToolResult::error(format!("write screenshot failed: {e}")));
            }
            path_value = json!(path.to_string_lossy());
        }

        let meta = json!({
            "status": "ok",
            "serial": serial,
            "mime_type": "image/png",
            "bytes": out.stdout.len(),
            "path": path_value,
            "duration_ms": out.duration_ms,
        });
        if inline {
            let b64 = general_purpose::STANDARD.encode(&out.stdout);
            return Ok(ToolResult {
                content: vec![
                    ContentBlock::image(b64, "image/png"),
                    ContentBlock::text(
                        serde_json::to_string_pretty(&meta).unwrap_or_else(|_| meta.to_string()),
                    ),
                ],
                structured_content: None,
                is_error: false,
                backend_id: None,
            });
        }
        Ok(ToolResult::json_text(&meta))
    }
}

mobile_tool_struct!(MobileHealthTool);
#[async_trait]
impl McpTool for MobileHealthTool {
    fn name(&self) -> &'static str {
        "mobile_health"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Collect a compact Android device/app health snapshot: foreground \
                 package, focus lines, recent crash/error logcat markers, and optional \
                 UIAutomator canvas/semantic-node analysis."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "serial": mobile_schema_serial(),
                    "package": { "type": "string", "description": "Optional expected foreground Android package." },
                    "log_lines": { "type": "integer", "minimum": 1, "maximum": 5000, "default": 200 },
                    "include_ui": { "type": "boolean", "default": true },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let serial = match resolve_mobile_serial(&args, timeout_ms).await {
            Ok(s) => s,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let expected_package = args
            .get("package")
            .and_then(|v| v.as_str())
            .filter(|s| !s.trim().is_empty());
        let log_lines = args
            .get("log_lines")
            .and_then(|v| v.as_u64())
            .unwrap_or(200)
            .clamp(1, 5000)
            .to_string();
        let include_ui = args
            .get("include_ui")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        let mut partial = false;
        let focus_out = run_adb_command(
            Some(&serial),
            &adb_args(&["shell", "dumpsys", "window"]),
            timeout_ms,
        )
        .await;
        let (focus_lines, focus_status) = match focus_out {
            Ok(out) if out.ok() => {
                let lines = parse_focus_lines(&out.stdout);
                (
                    lines,
                    json!({ "status": "ok", "duration_ms": out.duration_ms }),
                )
            }
            Ok(out) => {
                partial = true;
                (
                    Vec::new(),
                    json!({ "status": "error", "adb": out.as_json() }),
                )
            }
            Err(e) => {
                partial = true;
                (Vec::new(), json!({ "status": "error", "error": e }))
            }
        };
        let foreground_package = parse_foreground_package(&focus_lines);
        let log_package = expected_package.or(foreground_package.as_deref());

        let log_out = run_adb_command(
            Some(&serial),
            &vec!["logcat".into(), "-d".into(), "-t".into(), log_lines.clone()],
            timeout_ms,
        )
        .await;
        let logcat = match log_out {
            Ok(out) if out.ok() => {
                let mut summary = summarize_mobile_logcat(&out.stdout, log_package);
                summary["status"] = json!("ok");
                summary["package"] = json!(log_package);
                summary["requested_lines"] = json!(log_lines);
                summary["duration_ms"] = json!(out.duration_ms);
                summary["truncated"] = json!(out.truncated);
                summary
            }
            Ok(out) => {
                partial = true;
                json!({ "status": "error", "adb": out.as_json() })
            }
            Err(e) => {
                partial = true;
                json!({ "status": "error", "error": e })
            }
        };

        let ui = if include_ui {
            match mobile_dump_ui_xml(&serial, timeout_ms).await {
                Ok((dump, cat)) => match parse_uiautomator_nodes(&cat.stdout) {
                    Ok(nodes) => json!({
                        "status": "ok",
                        "analysis": MobileUiAnalysis::from_nodes(&nodes).as_json(),
                        "dump": dump.as_json(),
                    }),
                    Err(e) => {
                        partial = true;
                        json!({ "status": "error", "error": e })
                    }
                },
                Err(e) => {
                    partial = true;
                    json!({ "status": "error", "error": e })
                }
            }
        } else {
            json!({ "status": "skipped" })
        };

        let package_match = match (expected_package, foreground_package.as_deref()) {
            (Some(expected), Some(actual)) => Some(expected == actual),
            (Some(_), None) => Some(false),
            (None, _) => None,
        };
        Ok(ToolResult::json_text(&json!({
            "status": if partial { "partial" } else { "ok" },
            "serial": serial,
            "expected_package": expected_package,
            "foreground_package": foreground_package,
            "package_match": package_match,
            "focus_lines": focus_lines,
            "focus": focus_status,
            "logcat": logcat,
            "ui": ui,
        })))
    }
}

mobile_tool_struct!(MobileDebugBundleTool);
#[async_trait]
impl McpTool for MobileDebugBundleTool {
    fn name(&self) -> &'static str {
        "mobile_debug_bundle"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Collect a bounded, read-only Android app debug bundle into a new local directory. Includes a manifest, focus state, package details, recent logcat, crash-dropbox excerpts, UI XML, and an optional screenshot. Individual collection failures are recorded as partial results instead of discarding the useful artifacts.".into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "serial": mobile_schema_serial(),
                    "package": { "type": "string", "description": "Android package to inspect. Defaults to the parsed foreground package when available." },
                    "output_parent": { "type": "string", "description": "Existing local parent directory. Defaults to the system temp directory; a unique child directory is always created." },
                    "log_lines": { "type": "integer", "minimum": 1, "maximum": 5000, "default": 500 },
                    "include_ui": { "type": "boolean", "default": true },
                    "include_screenshot": { "type": "boolean", "default": false },
                    "include_crash_dropbox": { "type": "boolean", "default": true },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let serial = match resolve_mobile_serial(&args, timeout_ms).await {
            Ok(serial) => serial,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_secs())
            .unwrap_or(0);
        let parent = args
            .get("output_parent")
            .and_then(Value::as_str)
            .filter(|value| !value.trim().is_empty())
            .map(PathBuf::from)
            .unwrap_or_else(std::env::temp_dir);
        if !parent.is_dir() {
            return Ok(ToolResult::error(format!(
                "debug bundle output parent is not an existing directory: {}",
                parent.display()
            )));
        }
        let bundle = mobile_debug_bundle_path(&parent, &serial, now);
        if bundle.exists() {
            return Ok(ToolResult::error(format!(
                "debug bundle path already exists; retry after the timestamp changes: {}",
                bundle.display()
            )));
        }
        if let Err(e) = std::fs::create_dir(&bundle) {
            return Ok(ToolResult::error(format!(
                "create debug bundle directory {} failed: {e}",
                bundle.display()
            )));
        }
        if let Err(e) = harden_mobile_bundle_path(&bundle, true) {
            return Ok(ToolResult::error(e));
        }

        let mut artifacts = Vec::new();
        let mut partial = false;
        let focus = run_adb_command(
            Some(&serial),
            &adb_args(&["shell", "dumpsys", "window"]),
            timeout_ms,
        )
        .await;
        let (focus_lines, foreground_package) = match focus {
            Ok(out) if out.ok() => {
                let path = bundle.join("focus.txt");
                match write_mobile_bundle_text(&path, &out.stdout) {
                    Ok(bytes) => artifacts.push(json!({ "name": "focus", "path": path, "status": "ok", "bytes": bytes, "truncated": out.truncated })),
                    Err(e) => { partial = true; artifacts.push(json!({ "name": "focus", "status": "error", "error": e })); }
                }
                let lines = parse_focus_lines(&out.stdout);
                let package = parse_foreground_package(&lines);
                (lines, package)
            }
            Ok(out) => {
                partial = true;
                artifacts.push(json!({ "name": "focus", "status": "error", "adb": out.as_json() }));
                (Vec::new(), None)
            }
            Err(e) => {
                partial = true;
                artifacts.push(json!({ "name": "focus", "status": "error", "error": e }));
                (Vec::new(), None)
            }
        };
        let package = args
            .get("package")
            .and_then(Value::as_str)
            .filter(|value| !value.trim().is_empty())
            .map(str::to_string)
            .or_else(|| foreground_package.clone());

        if let Some(package) = package.as_deref() {
            partial |= record_mobile_bundle_text(
                &bundle,
                "package",
                "package.txt",
                run_adb_command(
                    Some(&serial),
                    &vec![
                        "shell".into(),
                        "dumpsys".into(),
                        "package".into(),
                        package.into(),
                    ],
                    timeout_ms,
                )
                .await,
                &mut artifacts,
            );
        } else {
            partial = true;
            artifacts.push(json!({ "name": "package", "status": "skipped", "reason": "no package supplied and foreground package unavailable" }));
        }

        let log_lines = args
            .get("log_lines")
            .and_then(Value::as_u64)
            .unwrap_or(500)
            .clamp(1, 5000)
            .to_string();
        partial |= record_mobile_bundle_text(
            &bundle,
            "logcat",
            "logcat.txt",
            run_adb_command(
                Some(&serial),
                &vec!["logcat".into(), "-d".into(), "-t".into(), log_lines.clone()],
                timeout_ms,
            )
            .await,
            &mut artifacts,
        );

        if args
            .get("include_crash_dropbox")
            .and_then(Value::as_bool)
            .unwrap_or(true)
        {
            partial |= record_mobile_bundle_text(
                &bundle,
                "crash_dropbox",
                "crash-dropbox.txt",
                run_adb_command(
                    Some(&serial),
                    &adb_args(&["shell", "dumpsys", "dropbox", "--print", "data_app_crash"]),
                    timeout_ms,
                )
                .await,
                &mut artifacts,
            );
        } else {
            artifacts.push(json!({ "name": "crash_dropbox", "status": "skipped" }));
        }

        if args
            .get("include_ui")
            .and_then(Value::as_bool)
            .unwrap_or(true)
        {
            match mobile_dump_ui_xml(&serial, timeout_ms).await {
                Ok((_dump, cat)) => {
                    let path = bundle.join("ui.xml");
                    match write_mobile_bundle_text(&path, &cat.stdout) {
                        Ok(bytes) => artifacts.push(json!({ "name": "ui", "path": path, "status": "ok", "bytes": bytes, "truncated": cat.truncated })),
                        Err(e) => { partial = true; artifacts.push(json!({ "name": "ui", "status": "error", "error": e })); }
                    }
                }
                Err(e) => {
                    partial = true;
                    artifacts.push(json!({ "name": "ui", "status": "error", "error": e }));
                }
            }
        } else {
            artifacts.push(json!({ "name": "ui", "status": "skipped" }));
        }

        if args
            .get("include_screenshot")
            .and_then(Value::as_bool)
            .unwrap_or(false)
        {
            match run_adb_binary_command(
                Some(&serial),
                &adb_args(&["exec-out", "screencap", "-p"]),
                timeout_ms,
            )
            .await
            {
                Ok(out)
                    if out.ok() && out.stdout.starts_with(&[137, 80, 78, 71, 13, 10, 26, 10]) =>
                {
                    let path = bundle.join("screenshot.png");
                    match std::fs::write(&path, &out.stdout) {
                        Ok(()) => match harden_mobile_bundle_path(&path, false) {
                            Ok(()) => artifacts.push(json!({ "name": "screenshot", "path": path, "status": "ok", "bytes": out.stdout.len() })),
                            Err(e) => { partial = true; artifacts.push(json!({ "name": "screenshot", "status": "error", "error": e })); }
                        },
                        Err(e) => { partial = true; artifacts.push(json!({ "name": "screenshot", "status": "error", "error": e.to_string() })); }
                    }
                }
                Ok(out) => {
                    partial = true;
                    artifacts.push(json!({ "name": "screenshot", "status": "error", "adb": out.as_json(), "error": "screencap did not return a valid PNG" }));
                }
                Err(e) => {
                    partial = true;
                    artifacts.push(json!({ "name": "screenshot", "status": "error", "error": e }));
                }
            }
        } else {
            artifacts.push(json!({ "name": "screenshot", "status": "skipped" }));
        }

        let manifest_path = bundle.join("manifest.json");
        let manifest = json!({
            "schema": "agent_bridge.mobile_debug_bundle.v1",
            "status": if partial { "partial" } else { "ok" },
            "created_at_unix_seconds": now,
            "serial": serial,
            "package": package,
            "foreground_package": foreground_package,
            "focus_lines": focus_lines,
            "requested_log_lines": log_lines,
            "artifacts": artifacts,
        });
        let manifest_body =
            serde_json::to_string_pretty(&manifest).unwrap_or_else(|_| manifest.to_string());
        if let Err(e) = write_mobile_bundle_text(&manifest_path, &manifest_body) {
            return Ok(ToolResult::error(e));
        }
        Ok(ToolResult::json_text(&json!({
            "status": manifest["status"],
            "serial": serial,
            "package": manifest["package"],
            "bundle_path": bundle,
            "manifest_path": manifest_path,
            "artifact_count": manifest["artifacts"].as_array().map(Vec::len).unwrap_or(0),
            "artifacts": manifest["artifacts"],
        })))
    }
}

mobile_tool_struct!(MobileProjectionStartTool);

struct MobileProjectionRuntimeState {
    session_id: String,
    serial: String,
    endpoint: String,
    started_at: i64,
    expires_at: i64,
    frame: std::sync::RwLock<crate::mobile_projection::ProjectionFrame>,
    pulls: std::sync::atomic::AtomicU64,
    last_served_revision: std::sync::atomic::AtomicU64,
    last_pull_unix_seconds: std::sync::atomic::AtomicU64,
    text_submissions: std::sync::atomic::AtomicU64,
    latest_text_observation:
        std::sync::RwLock<Option<crate::mobile_projection::MobileTextObservation>>,
    stop_requested: std::sync::atomic::AtomicBool,
    ended: std::sync::atomic::AtomicBool,
}

fn mobile_projection_registry(
) -> &'static std::sync::Mutex<HashMap<String, Arc<MobileProjectionRuntimeState>>> {
    static REGISTRY: std::sync::OnceLock<
        std::sync::Mutex<HashMap<String, Arc<MobileProjectionRuntimeState>>>,
    > = std::sync::OnceLock::new();
    REGISTRY.get_or_init(|| std::sync::Mutex::new(HashMap::new()))
}

#[cfg(test)]
pub(super) fn mobile_projection_test_seed_state(
    session_id: &str,
    now: i64,
    frame: crate::mobile_projection::ProjectionFrame,
) {
    let state = Arc::new(MobileProjectionRuntimeState {
        session_id: session_id.into(),
        serial: "test-device".into(),
        endpoint: "http://127.0.0.1:1".into(),
        started_at: now,
        expires_at: now + 60,
        frame: std::sync::RwLock::new(frame),
        pulls: std::sync::atomic::AtomicU64::new(1),
        last_served_revision: std::sync::atomic::AtomicU64::new(4),
        last_pull_unix_seconds: std::sync::atomic::AtomicU64::new(now as u64),
        text_submissions: std::sync::atomic::AtomicU64::new(0),
        latest_text_observation: std::sync::RwLock::new(None),
        stop_requested: std::sync::atomic::AtomicBool::new(false),
        ended: std::sync::atomic::AtomicBool::new(false),
    });
    mobile_projection_registry()
        .lock()
        .unwrap()
        .insert(session_id.into(), state);
}

#[cfg(test)]
pub(super) fn mobile_projection_test_frame(
    session_id: &str,
) -> Option<crate::mobile_projection::ProjectionFrame> {
    let registry = mobile_projection_registry().lock().unwrap();
    let state = registry.get(session_id)?;
    let frame = state.frame.read().unwrap().clone();
    Some(frame)
}

#[cfg(test)]
pub(super) fn mobile_projection_test_remove_state(session_id: &str) {
    mobile_projection_registry()
        .lock()
        .unwrap()
        .remove(session_id);
}

pub(super) fn mobile_projection_phase(
    pulls: u64,
    last_pull_unix_seconds: u64,
    stop_requested: bool,
    ended: bool,
    expires_at: i64,
    now: i64,
) -> &'static str {
    if stop_requested {
        "stopped"
    } else if ended || now >= expires_at {
        "expired"
    } else if pulls == 0 {
        "awaiting_consent"
    } else if last_pull_unix_seconds.saturating_add(5) >= now.max(0) as u64 {
        "connected_recently"
    } else {
        "connected_then_idle"
    }
}

fn mobile_projection_snapshot(
    state: &MobileProjectionRuntimeState,
    now: i64,
    include_text: bool,
) -> Value {
    use std::sync::atomic::Ordering;
    let pulls = state.pulls.load(Ordering::Relaxed);
    let last_pull = state.last_pull_unix_seconds.load(Ordering::Relaxed);
    let text_submissions = state.text_submissions.load(Ordering::Relaxed);
    let stopped = state.stop_requested.load(Ordering::Relaxed);
    let ended = state.ended.load(Ordering::Relaxed);
    let frame = state.frame.read().unwrap();
    let current_revision = frame.revision;
    let last_served_revision = state.last_served_revision.load(Ordering::Relaxed);
    let mut snapshot = json!({
        "session_id": state.session_id,
        "serial": state.serial,
        "endpoint": state.endpoint,
        "started_at_unix_seconds": state.started_at,
        "expires_at_unix_seconds": state.expires_at,
        "current_revision": current_revision,
        "last_served_revision": last_served_revision,
        "current_revision_observed_by_device": last_served_revision >= current_revision,
        "title_chars": frame.title.chars().count(),
        "body_chars": frame.body.chars().count(),
        "status_present": frame.status.is_some(),
        "action_count": frame.actions.len(),
        "phase": mobile_projection_phase(pulls, last_pull, stopped, ended, state.expires_at, now),
        "pull_count": pulls,
        "last_pull_unix_seconds": if last_pull == 0 { Value::Null } else { json!(last_pull) },
        "consent_observed": pulls > 0,
        "text_submission_count": text_submissions,
        "latest_text_observation_available": text_submissions > 0,
        "text_retention": "in_memory_until_mcp_process_or_session_record_ends",
        "text_does_not_grant_attention_memory_or_actuation": true,
        "listener_active": !stopped && !ended && now < state.expires_at,
        "stop_requested": stopped,
        "ended": ended,
        "disconnect_inference": "connected_then_idle means pulls stopped or paused; without a signed device disconnect event it is not proof of explicit disconnect"
    });
    if include_text {
        snapshot["latest_text_observation"] =
            json!(state.latest_text_observation.read().unwrap().clone());
    }
    snapshot
}

fn mobile_projection_presentation(
    args: &Value,
) -> std::result::Result<(Option<&str>, Vec<String>), String> {
    let status = args.get("status").and_then(Value::as_str);
    if args.get("status").is_some() && status.is_none() {
        return Err("status must be a string".into());
    }
    let actions = match args.get("actions") {
        None => Vec::new(),
        Some(Value::Array(values)) => values
            .iter()
            .map(|value| {
                value
                    .as_str()
                    .map(str::to_owned)
                    .ok_or_else(|| "actions must contain only strings".to_string())
            })
            .collect::<std::result::Result<Vec<_>, _>>()?,
        Some(_) => return Err("actions must be an array of strings".into()),
    };
    Ok((status, actions))
}

pub(super) fn mobile_projection_patch_frame(
    current: &crate::mobile_projection::ProjectionFrame,
    args: &Value,
) -> std::result::Result<(crate::mobile_projection::ProjectionFrame, Vec<&'static str>), String> {
    let mut changed_fields = Vec::new();
    let title = match args.get("title") {
        None => current.title.clone(),
        Some(Value::String(value)) => {
            changed_fields.push("title");
            value.clone()
        }
        Some(_) => return Err("title must be a string when provided".into()),
    };
    let body = match args.get("body") {
        None => current.body.clone(),
        Some(Value::String(value)) => {
            changed_fields.push("body");
            value.clone()
        }
        Some(_) => return Err("body must be a string when provided".into()),
    };
    let status = match args.get("status") {
        None => current.status.clone(),
        Some(Value::Null) => {
            changed_fields.push("status");
            None
        }
        Some(Value::String(value)) => {
            changed_fields.push("status");
            Some(value.clone())
        }
        Some(_) => return Err("status must be a string or null when provided".into()),
    };
    let actions = match args.get("actions") {
        None => current.actions.clone(),
        Some(Value::Null) => {
            changed_fields.push("actions");
            Vec::new()
        }
        Some(Value::Array(values)) => {
            changed_fields.push("actions");
            values
                .iter()
                .map(|value| {
                    value
                        .as_str()
                        .map(str::to_owned)
                        .ok_or_else(|| "actions must contain only strings".to_string())
                })
                .collect::<std::result::Result<Vec<_>, _>>()?
        }
        Some(_) => return Err("actions must be an array of strings or null when provided".into()),
    };
    let media_context = match args.get("media_context") {
        None => current.media_context.clone(),
        Some(Value::Null) => {
            changed_fields.push("media_context");
            None
        }
        Some(value) => {
            changed_fields.push("media_context");
            serde_json::from_value(value.clone())
                .map_err(|error| {
                    format!("media_context must match agent_bridge.media_context.v0: {error}")
                })
                .map(Some)?
        }
    };
    if changed_fields.is_empty() {
        return Err(
            "provide at least one of title, body, status, actions, or media_context".into(),
        );
    }
    let revision = current.revision.saturating_add(1);
    let frame = crate::mobile_projection::ProjectionFrame::new(
        &current.session_id,
        revision,
        current.expires_at_unix_seconds,
        &title,
        &body,
    )
    .and_then(|frame| frame.with_presentation(status.as_deref(), &actions))
    .and_then(|frame| frame.with_media_context(media_context))
    .map_err(|error| format!("invalid projection frame: {error}"))?;
    Ok((frame, changed_fields))
}

pub(super) fn mobile_projection_write_rejection(
    stop_requested: bool,
    ended: bool,
    now: i64,
    expires_at: i64,
) -> Option<&'static str> {
    if stop_requested || ended || now >= expires_at {
        Some("projection session is stopped or expired; start a new consent session")
    } else {
        None
    }
}

pub(super) fn mobile_projection_wait_outcome(
    pulls: u64,
    last_served_revision: u64,
    stop_requested: bool,
    ended: bool,
    expires_at: i64,
    target_revision: Option<u64>,
    now: i64,
) -> Option<&'static str> {
    if stop_requested {
        return Some("stopped_before_observation");
    }
    if ended || now >= expires_at {
        return Some("expired_before_observation");
    }
    match target_revision {
        Some(revision) if last_served_revision >= revision => Some("revision_observed_by_device"),
        None if pulls > 0 => Some("consent_observed"),
        _ => None,
    }
}

#[async_trait]
impl McpTool for MobileProjectionStartTool {
    fn name(&self) -> &'static str {
        "mobile_projection_start"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Replace any prior projection Activity, then open an explicit-consent \
                 Android Activity for one short-lived, \
                 read-only Agent-Bridge title/text projection. Generates an in-memory token, \
                 binds a random private-LAN port, and never starts the companion service. \
                 By default the device holder must still press Allow and connect. The explicit \
                 test-only auto_connect option skips that display confirmation for an already \
                 ADB-paired device; this tool grants no \
                 attention, memory, sensor, or control authority. Payloads are authenticated \
                 but not encrypted, so do not project secrets."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["bind", "title", "body"],
                "properties": {
                    "serial": mobile_schema_serial(),
                    "bind": { "type": "string", "description": "Private or link-local host IP reachable by the phone." },
                    "title": { "type": "string", "maxLength": 160 },
                    "body": { "type": "string", "maxLength": 8000 },
                    "status": { "type": "string", "maxLength": 80, "description": "Optional short state label rendered as a status card." },
                    "actions": { "type": "array", "maxItems": 6, "items": { "type": "string", "maxLength": 240 }, "description": "Optional ordered, display-only next actions. They grant no actuation authority." },
                    "media_context": { "type": ["object", "null"], "description": "Optional read-only agent_bridge.media_context.v0 payload; it grants no control authority." },
                    "auto_connect": { "type": "boolean", "default": false, "description": "Test-only. Explicitly skip the companion Activity's display confirmation for this already ADB-paired device. Keeps the short expiry, per-session token, authenticated pull, and zero authority boundary." },
                    "ttl_seconds": { "type": "integer", "minimum": 1, "maximum": 600, "default": 300 },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let serial = match resolve_mobile_serial(&args, timeout_ms).await {
            Ok(s) => s,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let bind = match args.get("bind").and_then(Value::as_str) {
            Some(value) => match value.parse::<std::net::IpAddr>() {
                Ok(address) => address,
                Err(_) => return Ok(ToolResult::error("bind must be an IP address")),
            },
            None => return Ok(ToolResult::error("missing 'bind'")),
        };
        let title = match args.get("title").and_then(Value::as_str) {
            Some(value) => value,
            None => return Ok(ToolResult::error("missing 'title'")),
        };
        let body = match args.get("body").and_then(Value::as_str) {
            Some(value) => value,
            None => return Ok(ToolResult::error("missing 'body'")),
        };
        let ttl_seconds = args
            .get("ttl_seconds")
            .and_then(Value::as_i64)
            .unwrap_or(300);
        if !(1..=crate::mobile_projection::MAX_SESSION_SECONDS).contains(&ttl_seconds) {
            return Ok(ToolResult::error("ttl_seconds must be in 1..=600"));
        }
        let auto_connect = args
            .get("auto_connect")
            .and_then(Value::as_bool)
            .unwrap_or(false);

        let mut token = [0u8; 32];
        let random_result = std::fs::File::open("/dev/urandom")
            .and_then(|mut file| std::io::Read::read_exact(&mut file, &mut token));
        if let Err(error) = random_result {
            return Ok(ToolResult::error(format!(
                "generate projection token failed: {error}"
            )));
        }
        let token_hex: String = token.iter().map(|byte| format!("{byte:02x}")).collect();
        let now = match SystemTime::now().duration_since(UNIX_EPOCH) {
            Ok(duration) => duration.as_secs() as i64,
            Err(_) => return Ok(ToolResult::error("system clock before Unix epoch")),
        };
        let expires_at = now + ttl_seconds;
        let session_id = format!("mcp-{now}-{}", &token_hex[..12]);
        let replaced_listener_count = {
            use std::sync::atomic::Ordering;
            let mut registry = mobile_projection_registry().lock().unwrap();
            registry.retain(|_, state| now <= state.expires_at + 600);
            let mut stopped = 0u64;
            for state in registry.values() {
                if state.serial == serial && !state.ended.load(Ordering::Relaxed) {
                    state.stop_requested.store(true, Ordering::Relaxed);
                    stopped += 1;
                }
            }
            if registry.len() >= 32 {
                return Ok(ToolResult::error(
                    "projection runtime registry is full; wait for old session records to age out",
                ));
            }
            stopped
        };
        let session = match crate::mobile_projection::ProjectionSession::bind(
            bind,
            0,
            &token_hex,
            &session_id,
            expires_at,
        ) {
            Ok(session) => session,
            Err(error) => {
                return Ok(ToolResult::error(format!(
                    "start projection host: {error:#}"
                )))
            }
        };
        let endpoint = match session.local_addr() {
            Ok(endpoint) => endpoint,
            Err(error) => {
                return Ok(ToolResult::error(format!(
                    "read projection endpoint: {error}"
                )))
            }
        };
        let (status, actions) = match mobile_projection_presentation(&args) {
            Ok(value) => value,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let media_context = match args.get("media_context") {
            None | Some(Value::Null) => None,
            Some(value) => match serde_json::from_value(value.clone()) {
                Ok(context) => Some(context),
                Err(error) => {
                    return Ok(ToolResult::error(format!("invalid media_context: {error}")))
                }
            },
        };
        let frame = match crate::mobile_projection::ProjectionFrame::new(
            &session_id,
            1,
            expires_at,
            title,
            body,
        )
        .and_then(|frame| frame.with_presentation(status, &actions))
        .and_then(|frame| frame.with_media_context(media_context))
        {
            Ok(frame) => frame,
            Err(error) => {
                return Ok(ToolResult::error(format!(
                    "invalid projection frame: {error}"
                )))
            }
        };

        let bind_text = bind.to_string();
        let endpoint_port = endpoint.port().to_string();
        let expires_at_text = expires_at.to_string();
        let mut adb_start_args = vec![
            "shell",
            "am",
            "start",
            "-S",
            "-n",
            "dev.agentbridge.companion/.ProjectionActivity",
            "--es",
            "projection_host",
            &bind_text,
            "--ei",
            "projection_port",
            &endpoint_port,
            "--es",
            "projection_token",
            &token_hex,
            "--es",
            "projection_session_id",
            &session_id,
            "--el",
            "projection_expires_at_unix_seconds",
            &expires_at_text,
        ];
        if auto_connect {
            adb_start_args.extend_from_slice(&["--ez", "projection_auto_connect", "true"]);
        }
        let adb_start = adb_args(&adb_start_args);
        let launched = match run_adb_command(Some(&serial), &adb_start, timeout_ms).await {
            Ok(output)
                if output.ok()
                    && !output.stdout.contains("Error:")
                    && !output.stderr.contains("Error:") =>
            {
                output
            }
            Ok(output) => {
                return Ok(ToolResult::error(format!(
                    "open projection consent Activity failed: {} {}",
                    output.stdout.trim(),
                    output.stderr.trim()
                )))
            }
            Err(error) => return Ok(ToolResult::error(error)),
        };

        let runtime = Arc::new(MobileProjectionRuntimeState {
            session_id: session_id.clone(),
            serial: serial.clone(),
            endpoint: endpoint.to_string(),
            started_at: now,
            expires_at,
            frame: std::sync::RwLock::new(frame),
            pulls: std::sync::atomic::AtomicU64::new(0),
            last_served_revision: std::sync::atomic::AtomicU64::new(0),
            last_pull_unix_seconds: std::sync::atomic::AtomicU64::new(0),
            text_submissions: std::sync::atomic::AtomicU64::new(0),
            latest_text_observation: std::sync::RwLock::new(None),
            stop_requested: std::sync::atomic::AtomicBool::new(false),
            ended: std::sync::atomic::AtomicBool::new(false),
        });
        mobile_projection_registry()
            .lock()
            .unwrap()
            .insert(session_id.clone(), runtime.clone());
        let runtime_thread = runtime.clone();
        if let Err(error) = std::thread::Builder::new()
            .name(format!("mobile-projection-{session_id}"))
            .spawn(move || {
                use std::sync::atomic::Ordering;
                while !runtime_thread.stop_requested.load(Ordering::Relaxed)
                    && SystemTime::now()
                        .duration_since(UNIX_EPOCH)
                        .map(|duration| (duration.as_secs() as i64) < expires_at)
                        .unwrap_or(false)
                {
                    let frame = runtime_thread.frame.read().unwrap().clone();
                    if let Ok(Some(event)) = session.serve_next(&frame, Duration::from_secs(1)) {
                        match event {
                            crate::mobile_projection::ProjectionEvent::FramePulled { .. } => {
                                runtime_thread.pulls.fetch_add(1, Ordering::Relaxed);
                                runtime_thread
                                    .last_served_revision
                                    .store(frame.revision, Ordering::Relaxed);
                                if let Ok(duration) = SystemTime::now().duration_since(UNIX_EPOCH) {
                                    runtime_thread
                                        .last_pull_unix_seconds
                                        .store(duration.as_secs(), Ordering::Relaxed);
                                }
                            }
                            crate::mobile_projection::ProjectionEvent::TextSubmitted {
                                observation,
                                ..
                            } => {
                                *runtime_thread.latest_text_observation.write().unwrap() =
                                    Some(observation);
                                runtime_thread
                                    .text_submissions
                                    .fetch_add(1, Ordering::Relaxed);
                            }
                        }
                    }
                }
                runtime_thread.ended.store(true, Ordering::Relaxed);
            })
        {
            mobile_projection_registry()
                .lock()
                .unwrap()
                .remove(&session_id);
            return Ok(ToolResult::error(format!(
                "start projection listener thread failed: {error}"
            )));
        }

        Ok(ToolResult::json_text(&json!({
            "status": "awaiting_device_consent",
            "serial": serial,
            "session_id": session_id,
            "endpoint": endpoint.to_string(),
            "expires_at_unix_seconds": expires_at,
            "ttl_seconds": ttl_seconds,
            "activity_launch_duration_ms": launched.duration_ms,
            "token_exposed": false,
            "companion_service_started": false,
            "auto_connect": auto_connect,
            "replaced_prior_projection_activity": true,
            "replaced_prior_listener_count": replaced_listener_count,
            "authority": {
                "attention": false,
                "memory": false,
                "sensor": false,
                "actuation": false
            },
            "next": "The device holder must review the source/session/expiry and press Allow and connect."
        })))
    }
}

mobile_tool_struct!(MobileProjectionSyncMediaTool);
#[async_trait]
impl McpTool for MobileProjectionSyncMediaTool {
    fn name(&self) -> &'static str {
        "mobile_projection_sync_media"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read the current media playlist/track through the verified, read-only app_control playlist_current path and patch an existing consent-gated mobile projection. This never dispatches playback controls, extends TTL, reopens the Activity, or grants authority.".into(),
            input_schema: json!({
                "type": "object",
                "required": ["session_id"],
                "properties": {
                    "session_id": { "type": "string", "description": "Active mobile projection session to update." },
                    "player": { "type": "string", "description": "Optional exact or unique-substring MPRIS player selector." },
                    "cwd": { "type": "string", "description": "Optional repo root used to resolve app_control.py." },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 30000, "default": 15000 }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(error) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(error));
        }
        let Some(session_id) = args
            .get("session_id")
            .and_then(Value::as_str)
            .filter(|value| !value.trim().is_empty())
        else {
            return Ok(ToolResult::error("missing 'session_id'"));
        };
        let now = match SystemTime::now().duration_since(UNIX_EPOCH) {
            Ok(duration) => duration.as_secs() as i64,
            Err(_) => return Ok(ToolResult::error("system clock before Unix epoch")),
        };
        let state = {
            let registry = mobile_projection_registry().lock().unwrap();
            match registry.get(session_id) {
                Some(state) => state.clone(),
                None => return Ok(ToolResult::error("projection session not found or expired")),
            }
        };
        if let Some(error) = mobile_projection_write_rejection(
            state
                .stop_requested
                .load(std::sync::atomic::Ordering::Relaxed),
            state.ended.load(std::sync::atomic::Ordering::Relaxed),
            now,
            state.expires_at,
        ) {
            return Ok(ToolResult::error(error));
        }
        let mut read_args = json!({
            "domain": "media",
            "action": "playlist_current",
            "dry_run": true,
            "timeout_ms": args.get("timeout_ms").cloned().unwrap_or(json!(15_000)),
        });
        if let Some(player) = args.get("player") {
            read_args["player"] = player.clone();
        }
        if let Some(cwd) = args.get("cwd") {
            read_args["cwd"] = cwd.clone();
        }
        let read_result = AppControlTool::new(self.hub.clone())
            .execute(read_args, ctx)
            .await?;
        let Some(payload) = read_result.content.iter().find_map(|block| match block {
            ContentBlock::Text { text } => serde_json::from_str::<Value>(text).ok(),
            _ => None,
        }) else {
            return Ok(ToolResult::error("app_control returned no JSON payload"));
        };
        if read_result.is_error {
            let Some(unavailable) = mobile_projection_media_unavailable(&payload) else {
                return Ok(read_result);
            };
            let update_args = json!({
                "session_id": session_id,
                "title": unavailable["title"],
                "body": unavailable["body"],
                "status": unavailable["status"],
                "media_context": Value::Null,
            });
            let update_result = MobileProjectionUpdateTool::new(self.hub.clone())
                .execute(update_args, ctx)
                .await?;
            if update_result.is_error {
                return Ok(update_result);
            }
            let update_payload = update_result
                .content
                .iter()
                .find_map(|block| match block {
                    ContentBlock::Text { text } => serde_json::from_str::<Value>(text).ok(),
                    _ => None,
                })
                .unwrap_or_else(|| json!({"status": "updated"}));
            return Ok(ToolResult::json_text(&json!({
                "schema": "agent_bridge.mobile_projection_sync_media.v0",
                "status": "media_unavailable",
                "verdict": "verified",
                "recover": "replan",
                "session_id": session_id,
                "media_context": Value::Null,
                "unavailable": unavailable,
                "app_control": mobile_projection_app_control_evidence(&payload),
                "projection_update": update_payload,
                "authority": {
                    "attention": false,
                    "memory": false,
                    "sensor": false,
                    "actuation": false
                }
            })));
        }
        let observed_at = now;
        let context = match media_context_from_app_control(&payload, observed_at) {
            Ok(value) => value,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let (title, body, status) = media_projection_presentation(&context);
        let update_args = json!({
            "session_id": session_id,
            "title": title,
            "body": body,
            "status": status,
            "media_context": context,
        });
        let update_result = MobileProjectionUpdateTool::new(self.hub.clone())
            .execute(update_args, ctx)
            .await?;
        if update_result.is_error {
            return Ok(update_result);
        }
        let update_payload = update_result
            .content
            .iter()
            .find_map(|block| match block {
                ContentBlock::Text { text } => serde_json::from_str::<Value>(text).ok(),
                _ => None,
            })
            .unwrap_or_else(|| json!({"status": "updated"}));
        Ok(ToolResult::json_text(&json!({
            "schema": "agent_bridge.mobile_projection_sync_media.v0",
            "status": "updated",
            "session_id": session_id,
            "media_context": context,
            "app_control": mobile_projection_app_control_evidence(&payload),
            "projection_update": update_payload,
            "authority": {
                "attention": false,
                "memory": false,
                "sensor": false,
                "actuation": false
            }
        })))
    }
}

mobile_tool_struct!(MobileProjectionUpdateTool);
#[async_trait]
impl McpTool for MobileProjectionUpdateTool {
    fn name(&self) -> &'static str {
        "mobile_projection_update"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Patch one active, already consent-gated projection session. Omitted presentation fields keep their current values; status:null and actions:null (or an empty array) explicitly clear those fields. At least one field must be supplied. The patch keeps the original endpoint, token, expiry, and zero-authority boundary; it does not reopen the Activity, extend TTL, start a service, or grant new authority. Delivery is confirmed separately when status reports the revision as served by an authenticated device pull.".into(),
            input_schema: json!({
                "type": "object",
                "required": ["session_id"],
                "properties": {
                    "session_id": { "type": "string" },
                    "title": { "type": "string", "maxLength": 160 },
                    "body": { "type": "string", "maxLength": 8000 }
                    ,"media_context": { "type": ["object", "null"], "description": "Read-only agent_bridge.media_context.v0 payload. Omit to preserve; null to clear." }
                    ,"status": { "type": ["string", "null"], "maxLength": 80, "description": "Short state label. Omit to preserve; pass null to clear." }
                    ,"actions": { "type": ["array", "null"], "maxItems": 6, "items": { "type": "string", "maxLength": 240 }, "description": "Ordered, display-only next actions. Omit to preserve; pass null or [] to clear." }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(error) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(error));
        }
        let Some(session_id) = args
            .get("session_id")
            .and_then(Value::as_str)
            .filter(|value| !value.trim().is_empty())
        else {
            return Ok(ToolResult::error("missing 'session_id'"));
        };
        let now = match SystemTime::now().duration_since(UNIX_EPOCH) {
            Ok(duration) => duration.as_secs() as i64,
            Err(_) => return Ok(ToolResult::error("system clock before Unix epoch")),
        };
        let state = {
            let registry = mobile_projection_registry().lock().unwrap();
            match registry.get(session_id) {
                Some(state) => state.clone(),
                None => {
                    return Ok(ToolResult::error(
                        "projection session not found in this MCP process",
                    ))
                }
            }
        };
        use std::sync::atomic::Ordering;
        if let Some(error) = mobile_projection_write_rejection(
            state.stop_requested.load(Ordering::Relaxed),
            state.ended.load(Ordering::Relaxed),
            now,
            state.expires_at,
        ) {
            return Ok(ToolResult::error(error));
        }
        let mut frame = state.frame.write().unwrap();
        let (updated, changed_fields) = match mobile_projection_patch_frame(&frame, &args) {
            Ok(value) => value,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let revision = updated.revision;
        *frame = updated;
        let last_served_revision = state.last_served_revision.load(Ordering::Relaxed);
        Ok(ToolResult::json_text(&json!({
            "status": "updated_awaiting_authenticated_pull",
            "session_id": state.session_id,
            "revision": revision,
            "changed_fields": changed_fields,
            "last_served_revision": last_served_revision,
            "expires_at_unix_seconds": state.expires_at,
            "ttl_extended": false,
            "activity_reopened": false,
            "companion_service_started": false,
            "authority": {
                "attention": false,
                "memory": false,
                "sensor": false,
                "actuation": false
            }
        })))
    }
}

pub struct MobileProjectionStatusTool;
impl MobileProjectionStatusTool {
    pub fn new(_hub: Hub) -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MobileProjectionStatusTool {
    fn name(&self) -> &'static str {
        "mobile_projection_status"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read in-process mobile projection lifecycle state. Reports whether \
                 consent was observed through authenticated pulls and whether the listener is \
                 active. Passing an exact session_id also returns its latest foreground, \
                 user-submitted text observation; the session list exposes only availability \
                 metadata. An idle connection is reported honestly as ambiguous, not as proof \
                 that the device explicitly disconnected."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "session_id": { "type": "string", "description": "Optional exact session; omit to list recent sessions." }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let now = match SystemTime::now().duration_since(UNIX_EPOCH) {
            Ok(duration) => duration.as_secs() as i64,
            Err(_) => return Ok(ToolResult::error("system clock before Unix epoch")),
        };
        let session_id = args
            .get("session_id")
            .and_then(Value::as_str)
            .filter(|value| !value.trim().is_empty());
        let registry = mobile_projection_registry().lock().unwrap();
        if let Some(session_id) = session_id {
            return match registry.get(session_id) {
                Some(state) => Ok(ToolResult::json_text(&json!({
                    "status": "ok",
                    "session": mobile_projection_snapshot(state, now, true)
                }))),
                None => Ok(ToolResult::error(
                    "projection session not found in this MCP process",
                )),
            };
        }
        let mut sessions: Vec<Value> = registry
            .values()
            .map(|state| mobile_projection_snapshot(state, now, false))
            .collect();
        sessions.sort_by_key(|value| {
            std::cmp::Reverse(
                value
                    .get("started_at_unix_seconds")
                    .and_then(Value::as_i64)
                    .unwrap_or(0),
            )
        });
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "session_count": sessions.len(),
            "sessions": sessions
        })))
    }
}

pub struct MobileProjectionWaitTool;
impl MobileProjectionWaitTool {
    pub fn new(_hub: Hub) -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MobileProjectionWaitTool {
    fn name(&self) -> &'static str {
        "mobile_projection_wait"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Wait for bounded, authenticated evidence that a projection received \
                consent or that a requested revision was served to the device. A timeout only \
                reports that no matching evidence arrived; it never infers rejection or an \
                explicit disconnect. This read-only wait does not extend session TTL."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["session_id"],
                "properties": {
                    "session_id": { "type": "string" },
                    "target_revision": { "type": "integer", "minimum": 1, "description": "Omit to wait for the first authenticated device pull (consent observation)." },
                    "timeout_ms": { "type": "integer", "minimum": 100, "maximum": 120000, "default": 30000 }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let Some(session_id) = args
            .get("session_id")
            .and_then(Value::as_str)
            .filter(|value| !value.trim().is_empty())
        else {
            return Ok(ToolResult::error("missing 'session_id'"));
        };
        let target_revision = args.get("target_revision").and_then(Value::as_u64);
        if args.get("target_revision").is_some() && target_revision.is_none() {
            return Ok(ToolResult::error("target_revision must be an integer >= 1"));
        }
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(30_000);
        if !(100..=120_000).contains(&timeout_ms) {
            return Ok(ToolResult::error("timeout_ms must be in 100..=120000"));
        }
        let state = {
            let registry = mobile_projection_registry().lock().unwrap();
            match registry.get(session_id) {
                Some(state) => state.clone(),
                None => {
                    return Ok(ToolResult::error(
                        "projection session not found in this MCP process",
                    ))
                }
            }
        };
        if let Some(revision) = target_revision {
            let current_revision = state.frame.read().unwrap().revision;
            if revision > current_revision {
                return Ok(ToolResult::error(format!(
                    "target_revision {revision} is newer than current revision {current_revision}"
                )));
            }
        }

        let deadline = tokio::time::Instant::now() + Duration::from_millis(timeout_ms);
        let outcome = loop {
            use std::sync::atomic::Ordering;
            let now = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|duration| duration.as_secs() as i64)
                .unwrap_or(i64::MAX);
            if let Some(outcome) = mobile_projection_wait_outcome(
                state.pulls.load(Ordering::Relaxed),
                state.last_served_revision.load(Ordering::Relaxed),
                state.stop_requested.load(Ordering::Relaxed),
                state.ended.load(Ordering::Relaxed),
                state.expires_at,
                target_revision,
                now,
            ) {
                break outcome;
            }
            if tokio::time::Instant::now() >= deadline {
                break "timeout_without_matching_evidence";
            }
            tokio::time::sleep(Duration::from_millis(100)).await;
        };
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_secs() as i64)
            .unwrap_or(i64::MAX);
        Ok(ToolResult::json_text(&json!({
            "status": outcome,
            "target_revision": target_revision,
            "waited_without_ttl_extension": true,
            "timeout_is_not_rejection_or_disconnect": outcome == "timeout_without_matching_evidence",
            "session": mobile_projection_snapshot(&state, now, true)
        })))
    }
}

mobile_tool_struct!(MobileProjectionStopTool);
#[async_trait]
impl McpTool for MobileProjectionStopTool {
    fn name(&self) -> &'static str {
        "mobile_projection_stop"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Stop one mobile projection listener before TTL and force-stop the \
                 companion Activity on its selected Android device. The disabled companion \
                 service is not enabled or started."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["session_id"],
                "properties": {
                    "session_id": { "type": "string" },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(error) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(error));
        }
        let Some(session_id) = args
            .get("session_id")
            .and_then(Value::as_str)
            .filter(|value| !value.trim().is_empty())
        else {
            return Ok(ToolResult::error("missing 'session_id'"));
        };
        let state = {
            let registry = mobile_projection_registry().lock().unwrap();
            match registry.get(session_id) {
                Some(state) => state.clone(),
                None => {
                    return Ok(ToolResult::error(
                        "projection session not found in this MCP process",
                    ))
                }
            }
        };
        use std::sync::atomic::Ordering;
        state.stop_requested.store(true, Ordering::Relaxed);
        let adb_stop = run_adb_command(
            Some(&state.serial),
            &adb_args(&["shell", "am", "force-stop", "dev.agentbridge.companion"]),
            mobile_timeout_ms(&args),
        )
        .await;
        let adb = match adb_stop {
            Ok(output) => output.as_json(),
            Err(error) => json!({ "status": "error", "error": error }),
        };
        Ok(ToolResult::json_text(&json!({
            "status": "stop_requested",
            "session_id": state.session_id,
            "serial": state.serial,
            "listener_stop_requested": true,
            "companion_service_started": false,
            "adb_force_stop": adb
        })))
    }
}

mobile_tool_struct!(MobileUiSnapshotTool);
#[async_trait]
impl McpTool for MobileUiSnapshotTool {
    fn name(&self) -> &'static str {
        "mobile_ui_snapshot"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Run `uiautomator dump` and return a compact structured Android UI \
                 node summary. Optionally include truncated raw XML. Prefer this over \
                 screenshot reading when native Android controls are visible."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "serial": mobile_schema_serial(),
                    "max_nodes": { "type": "integer", "minimum": 1, "maximum": 500, "default": 100 },
                    "include_xml": { "type": "boolean", "default": false },
                    "xml_max_chars": { "type": "integer", "minimum": 0, "maximum": 200000, "default": 20000 },
                    "selector": mobile_schema_selector(),
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let serial = match resolve_mobile_serial(&args, timeout_ms).await {
            Ok(s) => s,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let (dump, cat) = match mobile_dump_ui_xml(&serial, timeout_ms).await {
            Ok(v) => v,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let nodes = match parse_uiautomator_nodes(&cat.stdout) {
            Ok(nodes) => nodes,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let selector = match args.get("selector") {
            Some(v) => match MobileSelector::from_value(v) {
                Ok(s) => Some(s),
                Err(e) => return Ok(ToolResult::error(e)),
            },
            None => None,
        };
        let max_nodes = args
            .get("max_nodes")
            .and_then(|v| v.as_u64())
            .unwrap_or(100)
            .clamp(1, 500) as usize;
        let visible_nodes: Vec<Value> = nodes
            .iter()
            .filter(|n| selector.as_ref().map(|s| s.matches(n)).unwrap_or(true))
            .take(max_nodes)
            .map(MobileUiNode::compact_json)
            .collect();
        let analysis = MobileUiAnalysis::from_nodes(&nodes);
        let include_xml = args
            .get("include_xml")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let mut resp = json!({
            "status": "ok",
            "serial": serial,
            "node_count": nodes.len(),
            "returned_nodes": visible_nodes.len(),
            "analysis": analysis.as_json(),
            "nodes": visible_nodes,
            "dump": dump.as_json(),
        });
        resp["observation"] = mobile_ui_observation_metadata(&serial, &nodes, &cat.stdout);
        if include_xml {
            let xml_max = args
                .get("xml_max_chars")
                .and_then(|v| v.as_u64())
                .unwrap_or(20_000)
                .min(200_000) as usize;
            let (xml, xml_truncated, xml_total_chars) = truncate_chars(&cat.stdout, xml_max);
            resp["xml"] = json!(xml);
            resp["xml_truncated"] = json!(xml_truncated);
            resp["xml_total_chars"] = json!(xml_total_chars);
        }
        Ok(ToolResult::json_text(&resp))
    }
}

pub(super) fn mobile_wait_condition_met(match_count: usize, condition: &str) -> bool {
    match condition {
        "absent" => match_count == 0,
        _ => match_count > 0,
    }
}

mobile_tool_struct!(MobileWaitForUiTool);
#[async_trait]
impl McpTool for MobileWaitForUiTool {
    fn name(&self) -> &'static str {
        "mobile_wait_for_ui"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Poll bounded UIAutomator snapshots until a selector is present or absent. This is read-only and replaces fixed sleeps or repeated manual snapshots after an explicit mobile action. It returns matched compact nodes on success and honest timeout/error metadata otherwise.".into(),
            input_schema: json!({
                "type": "object",
                "required": ["selector"],
                "properties": {
                    "serial": mobile_schema_serial(),
                    "selector": mobile_schema_selector(),
                    "condition": { "type": "string", "enum": ["present", "absent"], "default": "present" },
                    "wait_timeout_ms": { "type": "integer", "minimum": 250, "maximum": 60000, "default": 10000 },
                    "poll_interval_ms": { "type": "integer", "minimum": 250, "maximum": 5000, "default": 500 },
                    "stable_polls": { "type": "integer", "minimum": 1, "maximum": 5, "default": 1, "description": "Require the condition on this many consecutive successful snapshots." },
                    "max_matches": { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS, "description": "Per-ADB-command timeout, independent from the total wait timeout." }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let adb_timeout_ms = mobile_timeout_ms(&args);
        let serial = match resolve_mobile_serial(&args, adb_timeout_ms).await {
            Ok(serial) => serial,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let selector = match args.get("selector") {
            Some(value) => match MobileSelector::from_value(value) {
                Ok(selector) => selector,
                Err(e) => return Ok(ToolResult::error(e)),
            },
            None => return Ok(ToolResult::error("missing 'selector'")),
        };
        let condition = args
            .get("condition")
            .and_then(Value::as_str)
            .unwrap_or("present");
        if !matches!(condition, "present" | "absent") {
            return Ok(ToolResult::error("condition must be present or absent"));
        }
        let wait_timeout_ms = args
            .get("wait_timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(10_000)
            .clamp(250, 60_000);
        let poll_interval_ms = args
            .get("poll_interval_ms")
            .and_then(Value::as_u64)
            .unwrap_or(500)
            .clamp(250, 5_000);
        let stable_polls = args
            .get("stable_polls")
            .and_then(Value::as_u64)
            .unwrap_or(1)
            .clamp(1, 5) as usize;
        let max_matches = args
            .get("max_matches")
            .and_then(Value::as_u64)
            .unwrap_or(10)
            .clamp(1, 50) as usize;

        let started = Instant::now();
        let mut attempts = 0usize;
        let mut consecutive = 0usize;
        let mut last_error: Option<String>;
        let mut last_match_count: Option<usize> = None;
        loop {
            attempts += 1;
            let before_snapshot_ms = started.elapsed().as_millis() as u64;
            let snapshot_budget_ms = wait_timeout_ms.saturating_sub(before_snapshot_ms).max(1);
            match tokio::time::timeout(
                Duration::from_millis(snapshot_budget_ms),
                mobile_dump_ui_xml(&serial, adb_timeout_ms),
            )
            .await
            {
                Ok(Ok((_dump, cat))) => match parse_uiautomator_nodes(&cat.stdout) {
                    Ok(nodes) => {
                        let matches: Vec<&MobileUiNode> =
                            nodes.iter().filter(|node| selector.matches(node)).collect();
                        last_match_count = Some(matches.len());
                        last_error = None;
                        if mobile_wait_condition_met(matches.len(), condition) {
                            consecutive += 1;
                            if consecutive >= stable_polls {
                                let elapsed_ms = started.elapsed().as_millis() as u64;
                                let matched_nodes: Vec<Value> = matches
                                    .into_iter()
                                    .take(max_matches)
                                    .map(MobileUiNode::compact_json)
                                    .collect();
                                return Ok(ToolResult::json_text(&json!({
                                    "status": "matched",
                                    "serial": serial,
                                    "condition": condition,
                                    "attempts": attempts,
                                    "elapsed_ms": elapsed_ms,
                                    "stable_polls_required": stable_polls,
                                    "match_count": last_match_count,
                                    "returned_matches": matched_nodes.len(),
                                    "matches": matched_nodes,
                                    "analysis": MobileUiAnalysis::from_nodes(&nodes).as_json(),
                                })));
                            }
                        } else {
                            consecutive = 0;
                        }
                    }
                    Err(e) => {
                        consecutive = 0;
                        last_error = Some(e);
                    }
                },
                Ok(Err(e)) => {
                    consecutive = 0;
                    last_error = Some(e);
                }
                Err(_) => {
                    consecutive = 0;
                    last_error = Some("UI snapshot exceeded the remaining wait timeout".into());
                }
            }

            let elapsed_ms = started.elapsed().as_millis() as u64;
            if elapsed_ms >= wait_timeout_ms {
                return Ok(ToolResult::json_text(&json!({
                    "status": "timeout",
                    "serial": serial,
                    "condition": condition,
                    "attempts": attempts,
                    "elapsed_ms": elapsed_ms,
                    "wait_timeout_ms": wait_timeout_ms,
                    "stable_polls_required": stable_polls,
                    "stable_polls_observed": consecutive,
                    "last_match_count": last_match_count,
                    "last_error": last_error,
                })));
            }
            let remaining_ms = wait_timeout_ms.saturating_sub(elapsed_ms);
            tokio::time::sleep(Duration::from_millis(poll_interval_ms.min(remaining_ms))).await;
        }
    }
}

mobile_tool_struct!(MobileLogcatTailTool);
#[async_trait]
impl McpTool for MobileLogcatTailTool {
    fn name(&self) -> &'static str {
        "mobile_logcat_tail"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Return recent Android logcat lines from a selected device. Optional \
                 substring filtering happens after capture so callers can quickly inspect app \
                 crashes or runtime warnings."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "serial": mobile_schema_serial(),
                    "lines": { "type": "integer", "minimum": 1, "maximum": 5000, "default": 200 },
                    "filter": { "type": "string", "description": "Optional substring filter applied to captured lines." },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let serial = match resolve_mobile_serial(&args, timeout_ms).await {
            Ok(s) => s,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let lines = args
            .get("lines")
            .and_then(|v| v.as_u64())
            .unwrap_or(200)
            .clamp(1, 5000)
            .to_string();
        let out = match run_adb_command(
            Some(&serial),
            &vec!["logcat".into(), "-d".into(), "-t".into(), lines],
            timeout_ms,
        )
        .await
        {
            Ok(out) => out,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        if !out.ok() {
            return Ok(ToolResult::json_text(&json!({
                "status": "error",
                "serial": serial,
                "adb": out.as_json(),
            })));
        }
        let filter = args.get("filter").and_then(|v| v.as_str()).unwrap_or("");
        let rows: Vec<&str> = out
            .stdout
            .lines()
            .filter(|line| filter.is_empty() || line.contains(filter))
            .collect();
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "serial": serial,
            "line_count": rows.len(),
            "filter": if filter.is_empty() { Value::Null } else { json!(filter) },
            "lines": rows,
            "duration_ms": out.duration_ms,
            "truncated": out.truncated,
        })))
    }
}

mobile_tool_struct!(MobileInstallApkTool);
#[async_trait]
impl McpTool for MobileInstallApkTool {
    fn name(&self) -> &'static str {
        "mobile_install_apk"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Install an APK on an Android device via ADB. This mutates the \
                 selected device and returns the raw install result."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "serial": mobile_schema_serial(),
                    "apk": { "type": "string", "description": "Absolute or daemon-cwd-relative path to the APK." },
                    "reinstall": { "type": "boolean", "default": true, "description": "Pass -r to adb install." },
                    "downgrade": { "type": "boolean", "default": false, "description": "Pass -d to adb install." },
                    "grant_permissions": { "type": "boolean", "default": false, "description": "Pass -g to adb install." },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": 120000 }
                },
                "required": ["apk"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(120_000)
            .clamp(1_000, 120_000);
        let serial = match resolve_mobile_serial(&args, timeout_ms).await {
            Ok(s) => s,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let apk = match args.get("apk").and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => s,
            _ => return Ok(ToolResult::error("missing 'apk'")),
        };
        let apk_path = PathBuf::from(apk);
        if !apk_path.exists() {
            return Ok(ToolResult::error(format!("apk not found: {apk}")));
        }
        let mut cmd = vec!["install".to_string()];
        if args
            .get("reinstall")
            .and_then(|v| v.as_bool())
            .unwrap_or(true)
        {
            cmd.push("-r".to_string());
        }
        if args
            .get("downgrade")
            .and_then(|v| v.as_bool())
            .unwrap_or(false)
        {
            cmd.push("-d".to_string());
        }
        if args
            .get("grant_permissions")
            .and_then(|v| v.as_bool())
            .unwrap_or(false)
        {
            cmd.push("-g".to_string());
        }
        cmd.push(apk_path.to_string_lossy().into_owned());
        let out = match run_adb_command(Some(&serial), &cmd, timeout_ms).await {
            Ok(out) => out,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        Ok(ToolResult::json_text(&json!({
            "status": if out.ok() { "ok" } else { "error" },
            "serial": serial,
            "apk": apk,
            "adb": out.as_json(),
        })))
    }
}

mobile_tool_struct!(MobileLaunchAppTool);
#[async_trait]
impl McpTool for MobileLaunchAppTool {
    fn name(&self) -> &'static str {
        "mobile_launch_app"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Launch an Android app. Pass `component` for an exact activity, \
                 or pass `package` only to use the launcher category through `monkey`."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "serial": mobile_schema_serial(),
                    "package": { "type": "string", "description": "Android package name, e.g. com.example.app." },
                    "activity": { "type": "string", "description": "Optional activity class. Relative values starting with '.' are joined with package." },
                    "component": { "type": "string", "description": "Exact component, e.g. com.example/.MainActivity." },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let serial = match resolve_mobile_serial(&args, timeout_ms).await {
            Ok(s) => s,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let package = args.get("package").and_then(|v| v.as_str()).unwrap_or("");
        let component_arg = args
            .get("component")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let activity = args
            .get("activity")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let cmd = if let Some(component) = component_arg {
            vec![
                "shell".to_string(),
                "am".to_string(),
                "start".to_string(),
                "-n".to_string(),
                component.to_string(),
            ]
        } else if let Some(activity) = activity {
            if package.is_empty() {
                return Ok(ToolResult::error(
                    "package is required when activity is provided without component",
                ));
            }
            let component = if activity.starts_with('.') {
                format!("{package}/{activity}")
            } else if activity.contains('/') {
                activity.to_string()
            } else {
                format!("{package}/{activity}")
            };
            vec![
                "shell".to_string(),
                "am".to_string(),
                "start".to_string(),
                "-n".to_string(),
                component,
            ]
        } else {
            if package.is_empty() {
                return Ok(ToolResult::error(
                    "missing 'package' or exact 'component' to launch",
                ));
            }
            vec![
                "shell".to_string(),
                "monkey".to_string(),
                "-p".to_string(),
                package.to_string(),
                "-c".to_string(),
                "android.intent.category.LAUNCHER".to_string(),
                "1".to_string(),
            ]
        };
        let out = match run_adb_command(Some(&serial), &cmd, timeout_ms).await {
            Ok(out) => out,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        Ok(ToolResult::json_text(&json!({
            "status": if out.ok() { "ok" } else { "error" },
            "serial": serial,
            "adb": out.as_json(),
        })))
    }
}

/// SSB Phase-1 typed event spine: emit a verify-first semantic event for a
/// `mobile_click` (adb `input tap`) outcome AT ACTION TIME. Best-effort — a
/// telemetry write must never fail the tap. adb tap has no readback, so a
/// successful tap is Unknown; a failed / no-device tap is NotVerified (the
/// anti-laundering signal). Same unified Object/Affordance descriptor vocabulary
/// as the browser_click and desktop_action producers.
pub(super) async fn record_mobile_click_event(hub: &Hub, ok: bool, err_msg: &str, facts: Value) {
    if let Some(store) = &hub.store {
        let verdict = crate::semantic_event::classify_mobile(ok, err_msg);
        let object = crate::semantic_event::SemanticObject {
            object_type: "mobile_ui_node".to_string(),
            source_adapter: "mobile".to_string(),
            label: None,
            object_id: None,
        };
        let affordance = crate::semantic_event::Affordance {
            action_type: "tap".to_string(),
            risk_level: "medium".to_string(),
            requires_gate: false,
            expected_effect: Some("tap the targeted node/coordinate on the device".to_string()),
        };
        let ev = crate::semantic_event::SemanticEvent {
            ts: dispatch_now_secs(),
            actor: "mcp".to_string(),
            source: "mobile".to_string(),
            action: "tap".to_string(),
            target: None,
            object,
            affordance,
            verdict,
            facts,
        };
        if let Err(e) = store.record_semantic_event(ev.to_record()).await {
            tracing::debug!(error = %e, "record_semantic_event (mobile_click) failed");
        }
    }
}

pub(super) fn mobile_click_effect_verification(tap_ok: bool) -> Value {
    if tap_ok {
        crate::semantic_event::effect_verification(
            crate::semantic_event::VerdictStatus::Unknown,
            "adb input tap dispatched; no post-action UI readback was performed",
        )
    } else {
        crate::semantic_event::effect_verification(
            crate::semantic_event::VerdictStatus::NotVerified,
            "adb input tap returned nonzero",
        )
    }
}

pub(super) fn mobile_input_text_effect_verification(input_ok: bool) -> Value {
    if input_ok {
        crate::semantic_event::effect_verification(
            crate::semantic_event::VerdictStatus::Unknown,
            "adb input text dispatched; focused-control state was not read back",
        )
    } else {
        crate::semantic_event::effect_verification(
            crate::semantic_event::VerdictStatus::NotVerified,
            "adb input text returned nonzero",
        )
    }
}

mobile_tool_struct!(MobileClickTool);
#[async_trait]
impl McpTool for MobileClickTool {
    fn name(&self) -> &'static str {
        "mobile_click"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Tap an Android device by coordinates, or resolve a UI Automator \
                 selector and tap the center of the selected node's bounds. This performs a \
                 real GUI tap through `adb shell input tap`."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "serial": mobile_schema_serial(),
                    "x": { "type": "integer", "description": "Tap X coordinate. Use with y." },
                    "y": { "type": "integer", "description": "Tap Y coordinate. Use with x." },
                    "selector": mobile_schema_selector(),
                    "match_index": { "type": "integer", "minimum": 0, "default": 0, "description": "When selector matches multiple nodes, choose this zero-based match." },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let serial = match resolve_mobile_serial(&args, timeout_ms).await {
            Ok(s) => s,
            Err(e) => {
                // Anti-laundering headline: a tap with no resolvable device never
                // landed — record not_verified, never a green success.
                record_mobile_click_event(
                    &self.hub,
                    false,
                    &e,
                    json!({ "stage": "resolve_serial" }),
                )
                .await;
                return Ok(ToolResult::error(e));
            }
        };
        let explicit_x = args.get("x").and_then(|v| v.as_i64());
        let explicit_y = args.get("y").and_then(|v| v.as_i64());
        let (x, y, selected_node) = match (explicit_x, explicit_y) {
            (Some(x), Some(y)) => (x, y, Value::Null),
            (Some(_), None) | (None, Some(_)) => {
                return Ok(ToolResult::error(
                    "both x and y are required for coordinate tap",
                ));
            }
            (None, None) => {
                let selector_value = match args.get("selector") {
                    Some(v) => v,
                    None => return Ok(ToolResult::error("pass coordinates or selector")),
                };
                let selector = match MobileSelector::from_value(selector_value) {
                    Ok(s) => s,
                    Err(e) => return Ok(ToolResult::error(e)),
                };
                let (_, cat) = match mobile_dump_ui_xml(&serial, timeout_ms).await {
                    Ok(v) => v,
                    Err(e) => return Ok(ToolResult::error(e)),
                };
                let nodes = match parse_uiautomator_nodes(&cat.stdout) {
                    Ok(nodes) => nodes,
                    Err(e) => return Ok(ToolResult::error(e)),
                };
                let matches: Vec<&MobileUiNode> =
                    nodes.iter().filter(|n| selector.matches(n)).collect();
                let match_index = args
                    .get("match_index")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0) as usize;
                let Some(node) = matches.get(match_index).copied() else {
                    return Ok(ToolResult::error(format!(
                        "selector matched {} node(s), no match_index {match_index}",
                        matches.len()
                    )));
                };
                let Some(bounds) = node.bounds else {
                    return Ok(ToolResult::error("selected node has no bounds"));
                };
                let (x, y) = bounds.center();
                (x, y, node.compact_json())
            }
        };
        let cmd = vec![
            "shell".to_string(),
            "input".to_string(),
            "tap".to_string(),
            x.to_string(),
            y.to_string(),
        ];
        let out = match run_adb_command(Some(&serial), &cmd, timeout_ms).await {
            Ok(out) => out,
            Err(e) => {
                record_mobile_click_event(
                    &self.hub,
                    false,
                    &e,
                    json!({ "stage": "adb_run", "tap": { "x": x, "y": y } }),
                )
                .await;
                return Ok(ToolResult::error(e));
            }
        };
        // SSB Phase-1 typed event spine: stamp the verify-first verdict for the
        // tap AT ACTION TIME — Unknown on a dispatched tap (no readback),
        // NotVerified when adb reports the tap failed.
        let tap_ok = out.ok();
        record_mobile_click_event(
            &self.hub,
            tap_ok,
            if tap_ok {
                ""
            } else {
                "adb input tap returned nonzero"
            },
            json!({ "stage": "tap", "tap": { "x": x, "y": y } }),
        )
        .await;
        Ok(ToolResult::structured_json(&json!({
            "status": if tap_ok { "ok" } else { "error" },
            "serial": serial,
            "tap": { "x": x, "y": y },
            "selected_node": selected_node,
            "adb": out.as_json(),
            "effect_verification": mobile_click_effect_verification(tap_ok),
        })))
    }
}

mobile_tool_struct!(MobileInputTextTool);
#[async_trait]
impl McpTool for MobileInputTextTool {
    fn name(&self) -> &'static str {
        "mobile_input_text"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Send text to the focused Android control via `adb shell input text`. \
                 Spaces are encoded as `%s`, matching Android input command conventions."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "serial": mobile_schema_serial(),
                    "text": { "type": "string", "description": "Text to send to the focused control." },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                },
                "required": ["text"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let serial = match resolve_mobile_serial(&args, timeout_ms).await {
            Ok(s) => s,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let text = match args.get("text").and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => s,
            _ => return Ok(ToolResult::error("missing or empty 'text'")),
        };
        let encoded = adb_input_text_arg(text);
        let cmd = vec![
            "shell".to_string(),
            "input".to_string(),
            "text".to_string(),
            encoded.clone(),
        ];
        let out = match run_adb_command(Some(&serial), &cmd, timeout_ms).await {
            Ok(out) => out,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        Ok(ToolResult::structured_json(&json!({
            "status": if out.ok() { "ok" } else { "error" },
            "serial": serial,
            "encoded_text": encoded,
            "adb": out.as_json(),
            "effect_verification": mobile_input_text_effect_verification(out.ok()),
        })))
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct AppleUsbDevice {
    pub(super) product_name: String,
    pub(super) vendor_name: String,
    pub(super) serial: String,
    pub(super) udid: String,
    pub(super) vendor_id: Option<u64>,
    pub(super) product_id: Option<u64>,
    pub(super) location_id: Option<u64>,
    pub(super) supports_iphone_os: bool,
}

pub(super) fn parse_ioreg_value(line: &str, key: &str) -> Option<String> {
    let prefix = format!("\"{key}\" = ");
    let value = line.split_once(&prefix)?.1.trim();
    if let Some(s) = value.strip_prefix('"') {
        return Some(s.split('"').next().unwrap_or_default().to_string());
    }
    Some(
        value
            .split_whitespace()
            .next()
            .unwrap_or_default()
            .trim_end_matches(',')
            .to_string(),
    )
}

pub(super) fn parse_ioreg_bool(line: &str, key: &str) -> Option<bool> {
    parse_ioreg_value(line, key).and_then(|v| match v.as_str() {
        "Yes" | "true" | "1" => Some(true),
        "No" | "false" | "0" => Some(false),
        _ => None,
    })
}

pub(super) fn parse_ioreg_u64(line: &str, key: &str) -> Option<u64> {
    parse_ioreg_value(line, key).and_then(|v| v.parse::<u64>().ok())
}

pub(super) fn apple_usb_device_json(device: &AppleUsbDevice) -> Value {
    json!({
        "product_name": device.product_name,
        "vendor_name": device.vendor_name,
        "serial": device.serial,
        "udid": device.udid,
        "vendor_id": device.vendor_id,
        "product_id": device.product_id,
        "location_id": device.location_id,
        "supports_iphone_os": device.supports_iphone_os,
    })
}

pub(super) fn parse_apple_usb_devices_from_ioreg(stdout: &str) -> Vec<AppleUsbDevice> {
    #[derive(Default)]
    struct Builder {
        in_device: bool,
        product_name: Option<String>,
        vendor_name: Option<String>,
        serial: Option<String>,
        udid: Option<String>,
        vendor_id: Option<u64>,
        product_id: Option<u64>,
        location_id: Option<u64>,
        supports_iphone_os: Option<bool>,
    }

    impl Builder {
        fn finish(&mut self, out: &mut Vec<AppleUsbDevice>) {
            if !self.in_device {
                return;
            }
            let product_name = self.product_name.take().unwrap_or_default();
            let vendor_name = self.vendor_name.take().unwrap_or_default();
            let serial = self.serial.take().unwrap_or_default();
            let udid = self.udid.take().unwrap_or_else(|| serial.clone());
            let supports_iphone_os = self.supports_iphone_os.unwrap_or(false);
            let is_apple_mobile =
                vendor_name == "Apple Inc." && (supports_iphone_os || product_name.contains("iP"));
            if is_apple_mobile {
                out.push(AppleUsbDevice {
                    product_name,
                    vendor_name,
                    serial,
                    udid,
                    vendor_id: self.vendor_id.take(),
                    product_id: self.product_id.take(),
                    location_id: self.location_id.take(),
                    supports_iphone_os,
                });
            }
            *self = Builder::default();
        }
    }

    let mut out = Vec::new();
    let mut current = Builder::default();
    for line in stdout.lines() {
        let starts_device = line.contains("+-o ")
            && line.contains("<class IOUSBHostDevice")
            && (line.contains("iPhone@") || line.contains("iPad@") || line.contains("iPod@"));
        let starts_other_device = line.contains("+-o ") && line.contains("<class IOUSBHostDevice");
        if starts_other_device && current.in_device {
            current.finish(&mut out);
        }
        if starts_device {
            current.in_device = true;
            if line.contains("iPhone@") {
                current.product_name = Some("iPhone".to_string());
            } else if line.contains("iPad@") {
                current.product_name = Some("iPad".to_string());
            } else if line.contains("iPod@") {
                current.product_name = Some("iPod".to_string());
            }
            continue;
        }
        if !current.in_device {
            continue;
        }
        if let Some(v) = parse_ioreg_value(line, "USB Product Name")
            .or_else(|| parse_ioreg_value(line, "kUSBProductString"))
        {
            current.product_name = Some(v);
        }
        if let Some(v) = parse_ioreg_value(line, "USB Vendor Name")
            .or_else(|| parse_ioreg_value(line, "kUSBVendorString"))
        {
            current.vendor_name = Some(v);
        }
        if let Some(v) = parse_ioreg_value(line, "USB Serial Number")
            .or_else(|| parse_ioreg_value(line, "kUSBSerialNumberString"))
        {
            current.serial = Some(v);
        }
        if let Some(v) = parse_ioreg_value(line, "UsbAppleDeviceUDID") {
            current.udid = Some(v);
        }
        if let Some(v) = parse_ioreg_u64(line, "idVendor") {
            current.vendor_id = Some(v);
        }
        if let Some(v) = parse_ioreg_u64(line, "idProduct") {
            current.product_id = Some(v);
        }
        if let Some(v) = parse_ioreg_u64(line, "locationID") {
            current.location_id = Some(v);
        }
        if let Some(v) = parse_ioreg_bool(line, "SupportsIPhoneOS") {
            current.supports_iphone_os = Some(v);
        }
    }
    current.finish(&mut out);
    out
}

pub(super) async fn run_local_mobile_command(
    program: &str,
    args: &[&str],
    timeout_ms: u64,
) -> std::result::Result<AdbCommandOutput, String> {
    let started = Instant::now();
    let output = tokio::time::timeout(Duration::from_millis(timeout_ms), async {
        killable_command(program)
            .args(args)
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .output()
            .await
    })
    .await;
    let duration_ms = started.elapsed().as_millis() as u64;
    let output = match output {
        Ok(Ok(output)) => output,
        Ok(Err(e)) => return Err(format!("spawn {program} failed: {e}")),
        Err(_) => {
            return Ok(AdbCommandOutput {
                exit_code: -1,
                stdout: String::new(),
                stderr: format!("killed after {timeout_ms} ms timeout"),
                duration_ms,
                truncated: false,
            });
        }
    };
    let (stdout, stdout_truncated) = lossy_truncate(&output.stdout);
    let (stderr, stderr_truncated) = lossy_truncate(&output.stderr);
    Ok(AdbCommandOutput {
        exit_code: output.status.code().unwrap_or(-1),
        stdout,
        stderr,
        duration_ms,
        truncated: stdout_truncated || stderr_truncated,
    })
}

pub(super) async fn command_path(program: &str, args: &[&str], timeout_ms: u64) -> Value {
    match run_local_mobile_command(program, args, timeout_ms).await {
        Ok(out) if out.ok() => {
            let path = out.stdout.lines().next().unwrap_or_default().trim();
            if path.is_empty() {
                json!({ "available": false, "path": Value::Null })
            } else {
                json!({ "available": true, "path": path })
            }
        }
        Ok(out) => json!({
            "available": false,
            "path": Value::Null,
            "error": out.stderr.trim(),
        }),
        Err(e) => json!({ "available": false, "path": Value::Null, "error": e }),
    }
}

pub(super) async fn shell_command_path(tool: &str, timeout_ms: u64) -> Value {
    command_path("sh", &["-lc", &format!("command -v {tool}")], timeout_ms).await
}

mobile_tool_struct!(MobileAppleStatusTool);
#[async_trait]
impl McpTool for MobileAppleStatusTool {
    fn name(&self) -> &'static str {
        "mobile_apple_status"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only Apple mobile readiness probe. Reports Xcode/devicectl/simctl, \
                 optional third-party iOS tooling, and iPhone/iPad/iPod devices visible over USB. \
                 Use this before deciding whether to add or use iOS install/debug/UI automation."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "include_usb": { "type": "boolean", "default": true },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let include_usb = args
            .get("include_usb")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        let xcode_select = run_local_mobile_command("xcode-select", &["-p"], timeout_ms).await;
        let developer_dir = xcode_select
            .as_ref()
            .ok()
            .filter(|out| out.ok())
            .and_then(|out| out.stdout.lines().next())
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(str::to_string);
        let has_full_xcode = developer_dir
            .as_deref()
            .map(|p| {
                p.ends_with("/Xcode.app/Contents/Developer")
                    || p.contains(".app/Contents/Developer")
            })
            .unwrap_or(false);

        let devicectl = command_path("xcrun", &["--find", "devicectl"], timeout_ms).await;
        let simctl = command_path("xcrun", &["--find", "simctl"], timeout_ms).await;
        let xctrace = command_path("xcrun", &["--find", "xctrace"], timeout_ms).await;
        let xcdevice = command_path("xcrun", &["--find", "xcdevice"], timeout_ms).await;
        let third_party = json!({
            "cfgutil": shell_command_path("cfgutil", timeout_ms).await,
            "ios-deploy": shell_command_path("ios-deploy", timeout_ms).await,
            "idevice_id": shell_command_path("idevice_id", timeout_ms).await,
            "ideviceinfo": shell_command_path("ideviceinfo", timeout_ms).await,
            "idevicesyslog": shell_command_path("idevicesyslog", timeout_ms).await,
            "pymobiledevice3": shell_command_path("pymobiledevice3", timeout_ms).await,
            "tidevice": shell_command_path("tidevice", timeout_ms).await,
            "idb": shell_command_path("idb", timeout_ms).await,
            "idb_companion": shell_command_path("idb_companion", timeout_ms).await,
        });

        let usb_devices = if include_usb {
            match run_local_mobile_command("ioreg", &["-p", "IOUSB", "-l", "-w0"], timeout_ms).await
            {
                Ok(out) if out.ok() => parse_apple_usb_devices_from_ioreg(&out.stdout)
                    .iter()
                    .map(apple_usb_device_json)
                    .collect::<Vec<_>>(),
                _ => Vec::new(),
            }
        } else {
            Vec::new()
        };
        let has_usb_device = !usb_devices.is_empty();
        let devicectl_ready = devicectl
            .get("available")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let simctl_ready = simctl
            .get("available")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let libimobiledevice_ready = third_party
            .get("idevice_id")
            .and_then(|v| v.get("available"))
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        let mut recommendations = Vec::new();
        if !has_full_xcode {
            recommendations.push(
                "Install/select full Xcode before expecting devicectl/simctl workflows."
                    .to_string(),
            );
        }
        if has_usb_device && !devicectl_ready && !libimobiledevice_ready {
            recommendations.push(
                "USB sees Apple mobile hardware, but no devicectl/libimobiledevice bridge is available."
                    .to_string(),
            );
        }
        if !has_usb_device {
            recommendations.push("No iPhone/iPad/iPod is visible over USB.".to_string());
        }

        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "xcode": {
                "developer_dir": developer_dir,
                "full_xcode_selected": has_full_xcode,
                "raw": xcode_select.map(|out| out.as_json()).unwrap_or_else(|e| json!({ "error": e })),
            },
            "apple_tools": {
                "devicectl": devicectl,
                "simctl": simctl,
                "xctrace": xctrace,
                "xcdevice": xcdevice,
            },
            "third_party_tools": third_party,
            "usb": {
                "checked": include_usb,
                "apple_mobile_count": usb_devices.len(),
                "devices": usb_devices,
            },
            "readiness": {
                "physical_usb_visible": has_usb_device,
                "physical_devicectl_ready": has_usb_device && devicectl_ready,
                "physical_libimobiledevice_ready": has_usb_device && libimobiledevice_ready,
                "simulator_ready": simctl_ready,
                "ui_automation_ready": false,
            },
            "recommendations": recommendations,
        })))
    }
}

pub(super) fn mobile_schema_ios_udid() -> Value {
    json!({
        "type": "string",
        "description": "iOS device UDID. When omitted, the first `idevice_id -l` device is used."
    })
}

pub(super) async fn ios_visible_udids(timeout_ms: u64) -> std::result::Result<Vec<String>, String> {
    let out = run_local_mobile_command("idevice_id", &["-l"], timeout_ms).await?;
    if !out.ok() {
        return Err(out.stderr.trim().to_string());
    }
    Ok(out
        .stdout
        .lines()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .collect())
}

pub(super) async fn ios_selected_udid(
    args: &Value,
    timeout_ms: u64,
) -> std::result::Result<String, String> {
    if let Some(udid) = args
        .get("udid")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        return Ok(udid.to_string());
    }
    ios_visible_udids(timeout_ms)
        .await?
        .into_iter()
        .next()
        .ok_or_else(|| "no iOS device visible via idevice_id".to_string())
}

pub(super) async fn ios_info_key(udid: &str, key: &str, timeout_ms: u64) -> Option<String> {
    run_local_mobile_command("ideviceinfo", &["-u", udid, "-k", key], timeout_ms)
        .await
        .ok()
        .filter(|out| out.ok())
        .map(|out| out.stdout.trim().to_string())
        .filter(|s| !s.is_empty())
}

pub(super) async fn ios_device_info_json(udid: &str, timeout_ms: u64) -> Value {
    let keys = [
        ("device_name", "DeviceName"),
        ("product_type", "ProductType"),
        ("product_version", "ProductVersion"),
        ("build_version", "BuildVersion"),
        ("serial_number", "SerialNumber"),
        ("cpu_architecture", "CPUArchitecture"),
        ("trusted_host_attached", "TrustedHostAttached"),
    ];
    let mut obj = Map::new();
    obj.insert("udid".into(), json!(udid));
    for (field, key) in keys {
        if let Some(value) = ios_info_key(udid, key, timeout_ms).await {
            obj.insert(field.into(), json!(value));
        }
    }
    Value::Object(obj)
}

pub(super) fn parse_ios_installer_csv(stdout: &str, limit: usize) -> Vec<Value> {
    let mut records = Vec::new();
    let mut record = Vec::new();
    let mut field = String::new();
    let mut in_quotes = false;
    let mut chars = stdout.chars().peekable();
    while let Some(ch) = chars.next() {
        match ch {
            '"' if in_quotes && chars.peek() == Some(&'"') => {
                field.push('"');
                chars.next();
            }
            '"' => in_quotes = !in_quotes,
            ',' if !in_quotes => {
                record.push(field.trim().to_string());
                field.clear();
            }
            '\n' | '\r' if !in_quotes => {
                if ch == '\r' && chars.peek() == Some(&'\n') {
                    chars.next();
                }
                record.push(field.trim().to_string());
                field.clear();
                if !record.iter().all(|s| s.is_empty()) {
                    records.push(std::mem::take(&mut record));
                } else {
                    record.clear();
                }
            }
            _ => field.push(ch),
        }
    }
    if !field.is_empty() || !record.is_empty() {
        record.push(field.trim().to_string());
        if !record.iter().all(|s| s.is_empty()) {
            records.push(record);
        }
    }

    records
        .into_iter()
        .skip(1)
        .filter(|row| row.len() >= 3 && !row[0].is_empty())
        .take(limit)
        .map(|row| {
            json!({
                "bundle_identifier": row[0],
                "version": if row[1].is_empty() { Value::Null } else { json!(row[1]) },
                "display_name": row[2],
            })
        })
        .collect()
}

mobile_tool_struct!(MobileIosListDevicesTool);
#[async_trait]
impl McpTool for MobileIosListDevicesTool {
    fn name(&self) -> &'static str {
        "mobile_ios_list_devices"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "List iPhone/iPad/iPod devices visible through libimobiledevice. \
                 Returns UDIDs and optional lockdownd device info such as model, iOS version, \
                 serial, and trust state."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "include_info": { "type": "boolean", "default": true },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let include_info = args
            .get("include_info")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);
        let udids = match ios_visible_udids(timeout_ms).await {
            Ok(udids) => udids,
            Err(e) => {
                return Ok(ToolResult::json_text(&json!({
                    "status": "error",
                    "error": e,
                    "hint": "Install libimobiledevice and trust this computer on the device.",
                })));
            }
        };
        let mut devices = Vec::new();
        for udid in &udids {
            if include_info {
                devices.push(ios_device_info_json(udid, timeout_ms).await);
            } else {
                devices.push(json!({ "udid": udid }));
            }
        }
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "count": devices.len(),
            "devices": devices,
        })))
    }
}

mobile_tool_struct!(MobileIosAppsTool);
#[async_trait]
impl McpTool for MobileIosAppsTool {
    fn name(&self) -> &'static str {
        "mobile_ios_apps"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "List installed iOS apps through ideviceinstaller. Returns a compact \
                 parsed app list with bundle identifiers, display names, and versions."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "udid": mobile_schema_ios_udid(),
                    "scope": { "type": "string", "enum": ["user", "system", "all"], "default": "user" },
                    "limit": { "type": "integer", "minimum": 1, "maximum": 500, "default": 100 },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let udid = match ios_selected_udid(&args, timeout_ms).await {
            Ok(udid) => udid,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let scope = args
            .get("scope")
            .and_then(|v| v.as_str())
            .filter(|s| matches!(*s, "user" | "system" | "all"))
            .unwrap_or("user");
        let scope_arg = format!("--{scope}");
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(100)
            .clamp(1, 500) as usize;
        let out = match run_local_mobile_command(
            "ideviceinstaller",
            &["-u", &udid, "list", &scope_arg],
            timeout_ms,
        )
        .await
        {
            Ok(out) => out,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        if !out.ok() {
            return Ok(ToolResult::json_text(&json!({
                "status": "error",
                "udid": udid,
                "scope": scope,
                "ideviceinstaller": out.as_json(),
            })));
        }
        let apps = parse_ios_installer_csv(&out.stdout, limit);
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "udid": udid,
            "scope": scope,
            "count": apps.len(),
            "limit": limit,
            "apps": apps,
            "truncated": out.truncated,
        })))
    }
}

mobile_tool_struct!(MobileIosSyslogTailTool);
#[async_trait]
impl McpTool for MobileIosSyslogTailTool {
    fn name(&self) -> &'static str {
        "mobile_ios_syslog_tail"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Capture a short iOS syslog sample through idevicesyslog. Use this for \
                 crash/runtime diagnostics before falling back to screenshots."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "udid": mobile_schema_ios_udid(),
                    "duration_ms": { "type": "integer", "minimum": 1000, "maximum": 15000, "default": 3000 },
                    "lines": { "type": "integer", "minimum": 1, "maximum": 500, "default": 100 },
                    "filter": { "type": "string", "description": "Optional substring filter applied after capture." },
                    "timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": MOBILE_DEFAULT_TIMEOUT_MS }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let timeout_ms = mobile_timeout_ms(&args);
        let udid = match ios_selected_udid(&args, timeout_ms).await {
            Ok(udid) => udid,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let duration_ms = args
            .get("duration_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(3_000)
            .clamp(1_000, 15_000);
        let duration_secs = ((duration_ms + 999) / 1000).to_string();
        let line_limit = args
            .get("lines")
            .and_then(|v| v.as_u64())
            .unwrap_or(100)
            .clamp(1, 500) as usize;
        let filter = args
            .get("filter")
            .and_then(|v| v.as_str())
            .map(str::to_string)
            .filter(|s| !s.is_empty());
        let command_timeout = timeout_ms.max(duration_ms + 2_000);
        let out = match run_local_mobile_command(
            "perl",
            &[
                "-e",
                "alarm shift; exec @ARGV",
                &duration_secs,
                "idevicesyslog",
                "-u",
                &udid,
            ],
            command_timeout,
        )
        .await
        {
            Ok(out) => out,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let mut matched = 0usize;
        let mut kept = Vec::new();
        for line in out.stdout.lines() {
            if filter.as_ref().is_some_and(|needle| !line.contains(needle)) {
                continue;
            }
            matched += 1;
            if kept.len() < line_limit {
                kept.push(line.to_string());
            }
        }
        Ok(ToolResult::json_text(&json!({
            "status": if matched > 0 || out.ok() { "ok" } else { "error" },
            "udid": udid,
            "duration_ms": duration_ms,
            "line_count": matched,
            "returned_lines": kept.len(),
            "filter": filter,
            "lines": kept,
            "idevicesyslog": {
                "exit_code": out.exit_code,
                "stderr": out.stderr,
                "duration_ms": out.duration_ms,
                "truncated": out.truncated,
            },
        })))
    }
}

// ===========================================================================
//                        terminal_read_blocks tool
// ===========================================================================

pub struct TerminalReadBlocksTool {
    pub(super) hub: Hub,
}
impl TerminalReadBlocksTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for TerminalReadBlocksTool {
    fn name(&self) -> &'static str {
        "terminal_read_blocks"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Return structured blocks from a Warp terminal session. Each \
                block: command text, output, exit code, execution state. More reliable \
                than terminal_read_output for command→output mapping. Available only \
                with Warp IPC bridge connected."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "pane": {
                        "type": "string",
                        "description": "Pane/session id from terminal_list."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 20,
                        "description": "Maximum number of most-recent blocks to return."
                    },
                    "since_block": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "If set, only return blocks with 0-based index >= since_block (skip older blocks)."
                    },
                    "output_max_chars": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 65536,
                        "default": 4000,
                        "description": "Truncate each block's output to this many characters (default 4000). Set to 0 to omit output entirely."
                    }
                },
                "required": ["pane"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let term = match &self.hub.terminal {
            Some(t) => t.clone(),
            None => return Ok(ToolResult::error("no terminal backend configured")),
        };
        let pane = match args.get("pane").and_then(|v| v.as_str()) {
            Some(s) => PaneId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'pane'")),
        };
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(20)
            .clamp(1, 200) as usize;
        let since_block = args
            .get("since_block")
            .and_then(|v| v.as_u64())
            .map(|v| v as usize);
        let output_max = args
            .get("output_max_chars")
            .and_then(|v| v.as_u64())
            .unwrap_or(4000)
            .min(65536) as usize;

        match term.read_blocks(&pane, limit, since_block).await {
            Ok(blocks) => {
                let backend_id = term.id().to_string();
                let count = blocks.len();
                let blocks_json: Vec<serde_json::Value> = blocks
                    .into_iter()
                    .map(|b: TerminalBlock| {
                        let (out, truncated) = if output_max == 0 {
                            (String::new(), false)
                        } else {
                            let byte_end = b
                                .output
                                .char_indices()
                                .nth(output_max)
                                .map(|(i, _)| i)
                                .unwrap_or(b.output.len());
                            if byte_end < b.output.len() {
                                (b.output[..byte_end].to_string(), true)
                            } else {
                                (b.output, false)
                            }
                        };
                        let mut v = json!({
                            "block_id": b.block_id,
                            "command": b.command,
                            "output": out,
                            "exit_code": b.exit_code,
                            "state": b.state,
                            "is_running": b.is_running,
                        });
                        if let Some(ms) = b.start_ms {
                            v["start_ms"] = json!(ms);
                        }
                        if let Some(ms) = b.end_ms {
                            v["end_ms"] = json!(ms);
                            if let Some(start) = b.start_ms {
                                v["duration_ms"] = json!(ms - start);
                            }
                        }
                        if truncated {
                            v["output_truncated"] = json!(true);
                        }
                        v
                    })
                    .collect();
                Ok(ToolResult::json_text(&json!({
                    "pane": pane.as_str(),
                    "backend": backend_id,
                    "count": count,
                    "blocks": blocks_json,
                })))
            }
            Err(e) => Ok(ToolResult::error(format!("terminal_read_blocks: {e}"))),
        }
    }
}

// ===========================================================================
//                           browser-lite probes
// ===========================================================================

pub struct BrowserLiteProbeTool;
impl BrowserLiteProbeTool {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for BrowserLiteProbeTool {
    fn name(&self) -> &'static str {
        "browser_lite_probe"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only probe for optional external browser-lite backends. \
                 Currently supports Obscura: detects the binary, checks --help, optionally \
                 runs a short-lived MCP tools/list probe, and returns capability/safety \
                 evidence. It never starts a persistent service, changes browser routing, \
                 enables stealth, or mutates Agent-Bridge state."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "backend": {
                        "type": "string",
                        "enum": ["obscura"],
                        "default": "obscura",
                        "description": "External browser-lite backend to probe."
                    },
                    "bin": {
                        "type": "string",
                        "description": "Optional backend binary path. Otherwise uses AGENT_BRIDGE_OBSCURA_BIN, then PATH."
                    },
                    "probe_mcp_tools": {
                        "type": "boolean",
                        "default": true,
                        "description": "When true, run a short-lived MCP tools/list probe in addition to --help."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "minimum": 250,
                        "maximum": 60000,
                        "default": 5000,
                        "description": "Per-probe timeout for backend commands."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let backend = args
            .get("backend")
            .and_then(Value::as_str)
            .unwrap_or("obscura");
        if backend != "obscura" {
            return Ok(ToolResult::error(format!(
                "unsupported browser-lite backend: {backend}"
            )));
        }

        let bin = args
            .get("bin")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(PathBuf::from);
        let probe_mcp_tools = args
            .get("probe_mcp_tools")
            .and_then(Value::as_bool)
            .unwrap_or_else(|| {
                !args
                    .get("no_mcp_tools")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
            });
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(5_000);
        let options = crate::browser_lite::ObscuraProbeOptions {
            bin,
            timeout_ms,
            probe_mcp_tools,
            json: true,
        };

        let report =
            tokio::task::spawn_blocking(move || crate::browser_lite::probe_obscura(&options))
                .await
                .map_err(|e| ab_core::Error::Backend(format!("browser_lite_probe task: {e}")))?;
        let payload = serde_json::to_value(report).unwrap_or_else(|_| json!({}));
        Ok(ToolResult::json_text(&payload))
    }
}
