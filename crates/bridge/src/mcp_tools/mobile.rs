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
        Ok(ToolResult::json_text(&json!({
            "status": if tap_ok { "ok" } else { "error" },
            "serial": serial,
            "tap": { "x": x, "y": y },
            "selected_node": selected_node,
            "adb": out.as_json(),
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
        Ok(ToolResult::json_text(&json!({
            "status": if out.ok() { "ok" } else { "error" },
            "serial": serial,
            "encoded_text": encoded,
            "adb": out.as_json(),
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
