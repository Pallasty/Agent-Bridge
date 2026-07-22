//! Read-only, fail-closed validation for A2UI v0.9.1 server message streams.

use serde::Serialize;
use serde_json::{Map, Value};
use std::collections::{HashMap, HashSet};

pub const PROTOCOL_VERSION: &str = "v0.9.1";
pub const REPORT_SCHEMA: &str = "agent_bridge.a2ui.validation_report.v0";
pub const PREVIEW_REPORT_SCHEMA: &str = "agent_bridge.a2ui.preview_report.v0";

const BASIC_CATALOG_ID: &str = "https://a2ui.org/specification/v0_9_1/catalogs/basic/catalog.json";
const MESSAGE_KEYS: [&str; 4] = [
    "createSurface",
    "updateComponents",
    "updateDataModel",
    "deleteSurface",
];
const LEGACY_MESSAGE_KEYS: [&str; 3] = ["beginRendering", "surfaceUpdate", "dataModelUpdate"];
const BASIC_COMPONENTS: [&str; 18] = [
    "Text",
    "Image",
    "Icon",
    "Video",
    "AudioPlayer",
    "Row",
    "Column",
    "List",
    "Card",
    "Tabs",
    "Modal",
    "Divider",
    "Button",
    "TextField",
    "CheckBox",
    "ChoicePicker",
    "Slider",
    "DateTimeInput",
];

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct ValidationIssue {
    pub code: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message_index: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ValidationReport {
    pub schema: &'static str,
    pub protocol_version: &'static str,
    pub valid: bool,
    pub execution_allowed: bool,
    pub rendering_allowed: bool,
    pub message_count: usize,
    pub surface_count: usize,
    pub component_count: usize,
    pub action_count: usize,
    pub errors: Vec<ValidationIssue>,
    pub warnings: Vec<ValidationIssue>,
}

/// The authority-free result of rendering a validated A2UI stream as static HTML.
#[derive(Debug, Clone, Serialize)]
pub struct PreviewReport {
    pub schema: &'static str,
    pub protocol_version: &'static str,
    pub valid: bool,
    pub preview_generated: bool,
    pub execution_allowed: bool,
    pub interactive: bool,
    pub message_count: usize,
    pub surface_count: usize,
    pub rendered_component_count: usize,
    pub placeholder_count: usize,
    pub disabled_action_count: usize,
    pub errors: Vec<ValidationIssue>,
    pub warnings: Vec<ValidationIssue>,
}

#[derive(Debug, Clone)]
pub struct HtmlPreview {
    pub report: PreviewReport,
    pub html: Option<String>,
}

#[derive(Default)]
struct SurfaceState {
    components: HashSet<String>,
    references: Vec<(usize, String, String)>,
    has_root: bool,
    saw_component_update: bool,
}

impl ValidationReport {
    fn new() -> Self {
        Self {
            schema: REPORT_SCHEMA,
            protocol_version: PROTOCOL_VERSION,
            valid: false,
            execution_allowed: false,
            rendering_allowed: false,
            message_count: 0,
            surface_count: 0,
            component_count: 0,
            action_count: 0,
            errors: Vec::new(),
            warnings: Vec::new(),
        }
    }

    fn error(
        &mut self,
        code: impl Into<String>,
        message: impl Into<String>,
        message_index: Option<usize>,
        path: Option<String>,
    ) {
        self.errors.push(ValidationIssue {
            code: code.into(),
            message: message.into(),
            message_index,
            path,
        });
    }
}

pub fn validate_stream(input: &str) -> ValidationReport {
    let mut report = ValidationReport::new();
    let messages = match parse_messages(input) {
        Ok(messages) => messages,
        Err(message) => {
            report.error("invalid_json", message, None, None);
            return report;
        }
    };
    report.message_count = messages.len();

    let mut surfaces: HashMap<String, SurfaceState> = HashMap::new();
    for (index, message) in messages.iter().enumerate() {
        validate_message(message, index, &mut surfaces, &mut report);
    }

    for (surface_id, state) in &surfaces {
        validate_complete_surface(surface_id, state, &mut report);
    }

    report.valid = report.errors.is_empty();
    report
}

/// Render a deliberately limited, non-interactive HTML preview of a valid stream.
///
/// This does not interpret data-model updates, resolve remote assets, or dispatch
/// A2UI actions. Unsupported components and bindings are rendered as placeholders.
pub fn render_html_preview(input: &str) -> HtmlPreview {
    let validation = validate_stream(input);
    let mut report = PreviewReport {
        schema: PREVIEW_REPORT_SCHEMA,
        protocol_version: PROTOCOL_VERSION,
        valid: validation.valid,
        preview_generated: false,
        execution_allowed: false,
        interactive: false,
        message_count: validation.message_count,
        surface_count: validation.surface_count,
        rendered_component_count: 0,
        placeholder_count: 0,
        disabled_action_count: 0,
        errors: validation.errors.clone(),
        warnings: validation.warnings.clone(),
    };
    if !validation.valid {
        return HtmlPreview { report, html: None };
    }

    let messages = match parse_messages(input) {
        Ok(messages) => messages,
        Err(error) => {
            report.valid = false;
            report.errors.push(ValidationIssue {
                code: "preview_parse_failed".into(),
                message: error,
                message_index: None,
                path: None,
            });
            return HtmlPreview { report, html: None };
        }
    };

    let mut surfaces: HashMap<String, PreviewSurface> = HashMap::new();
    let mut surface_order = Vec::new();
    for (index, message) in messages.iter().enumerate() {
        let Some(object) = message.as_object() else {
            continue;
        };
        if let Some(payload) = object.get("createSurface").and_then(Value::as_object) {
            if let Some(surface_id) = payload.get("surfaceId").and_then(Value::as_str) {
                surfaces.insert(surface_id.to_string(), PreviewSurface::default());
                surface_order.push(surface_id.to_string());
            }
        } else if let Some(payload) = object.get("updateComponents").and_then(Value::as_object) {
            let Some(surface_id) = payload.get("surfaceId").and_then(Value::as_str) else {
                continue;
            };
            let Some(surface) = surfaces.get_mut(surface_id) else {
                continue;
            };
            let Some(components) = payload.get("components").and_then(Value::as_array) else {
                continue;
            };
            for component in components {
                if let Some(id) = component.get("id").and_then(Value::as_str) {
                    surface.components.insert(id.to_string(), component.clone());
                }
            }
        } else if object.contains_key("updateDataModel") {
            report.warnings.push(ValidationIssue {
                code: "data_model_not_evaluated".into(),
                message: "data-model updates are not evaluated by the read-only HTML preview"
                    .into(),
                message_index: Some(index),
                path: Some("/updateDataModel".into()),
            });
        } else if let Some(payload) = object.get("deleteSurface").and_then(Value::as_object) {
            if let Some(surface_id) = payload.get("surfaceId").and_then(Value::as_str) {
                surfaces.remove(surface_id);
                surface_order.retain(|id| id != surface_id);
            }
        }
    }

    let mut body = String::new();
    for surface_id in surface_order {
        let Some(surface) = surfaces.get(&surface_id) else {
            continue;
        };
        body.push_str("<section class=\"ab-a2ui-surface\"><h2>");
        body.push_str(&escape_html(&surface_id));
        body.push_str("</h2>");
        let mut stack = HashSet::new();
        render_component("root", surface, &mut stack, 0, &mut report, &mut body);
        body.push_str("</section>");
    }

    report.preview_generated = true;
    HtmlPreview {
        report,
        html: Some(format!(
            "<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>A2UI read-only preview</title><style>{}</style></head><body><main>{body}</main></body></html>",
            preview_css()
        )),
    }
}

#[derive(Default)]
struct PreviewSurface {
    components: HashMap<String, Value>,
}

fn render_component(
    id: &str,
    surface: &PreviewSurface,
    stack: &mut HashSet<String>,
    depth: usize,
    report: &mut PreviewReport,
    output: &mut String,
) {
    if depth > 64 {
        placeholder("component depth limit reached", report, output);
        return;
    }
    if !stack.insert(id.to_string()) {
        placeholder(&format!("component cycle at '{id}'"), report, output);
        return;
    }
    let Some(component) = surface.components.get(id).and_then(Value::as_object) else {
        placeholder(&format!("missing component '{id}'"), report, output);
        stack.remove(id);
        return;
    };
    let kind = component
        .get("component")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    match kind {
        "Text" => {
            report.rendered_component_count += 1;
            output.push_str("<p class=\"ab-a2ui-text\">");
            output.push_str(&render_property(component.get("text"), "text", report));
            output.push_str("</p>");
        }
        "Row" | "Column" | "List" => {
            report.rendered_component_count += 1;
            output.push_str("<div class=\"ab-a2ui-");
            output.push_str(&kind.to_ascii_lowercase());
            output.push_str("\">");
            render_children(component, surface, stack, depth + 1, report, output);
            output.push_str("</div>");
        }
        "Card" | "Modal" | "Tabs" => {
            report.rendered_component_count += 1;
            output.push_str("<section class=\"ab-a2ui-card\">");
            render_children(component, surface, stack, depth + 1, report, output);
            output.push_str("</section>");
        }
        "Divider" => {
            report.rendered_component_count += 1;
            output.push_str("<hr class=\"ab-a2ui-divider\">");
        }
        "Button" => {
            report.rendered_component_count += 1;
            if component.contains_key("action") {
                report.disabled_action_count += 1;
            }
            output.push_str("<button class=\"ab-a2ui-button\" disabled aria-disabled=\"true\">");
            if component.contains_key("child") || component.contains_key("children") {
                render_children(component, surface, stack, depth + 1, report, output);
            } else {
                output.push_str(&render_property(component.get("text"), "button", report));
            }
            output.push_str("</button>");
        }
        "Image" | "Icon" => {
            report.rendered_component_count += 1;
            output.push_str("<span class=\"ab-a2ui-media\">");
            output.push_str(kind);
            output.push_str(": ");
            output.push_str(&render_property(
                component.get("src").or_else(|| component.get("name")),
                kind,
                report,
            ));
            output.push_str("</span>");
        }
        _ => placeholder(
            &format!("unsupported A2UI component '{kind}'"),
            report,
            output,
        ),
    }
    stack.remove(id);
}

fn render_children(
    component: &Map<String, Value>,
    surface: &PreviewSurface,
    stack: &mut HashSet<String>,
    depth: usize,
    report: &mut PreviewReport,
    output: &mut String,
) {
    if let Some(child) = component.get("child").and_then(Value::as_str) {
        render_component(child, surface, stack, depth, report, output);
    }
    if let Some(children) = component.get("children").and_then(Value::as_array) {
        for child in children.iter().filter_map(Value::as_str) {
            render_component(child, surface, stack, depth, report, output);
        }
    }
}

fn render_property(value: Option<&Value>, label: &str, report: &mut PreviewReport) -> String {
    match value {
        Some(Value::String(value)) => escape_html(value),
        Some(Value::Object(value)) if value.contains_key("path") => {
            report.placeholder_count += 1;
            format!(
                "<span class=\"ab-a2ui-binding\">[data binding: {}]</span>",
                escape_html(&value["path"].to_string())
            )
        }
        Some(_) => {
            report.placeholder_count += 1;
            format!("<span class=\"ab-a2ui-binding\">[{label}: dynamic value]</span>")
        }
        None => {
            report.placeholder_count += 1;
            format!("<span class=\"ab-a2ui-binding\">[{label}: unavailable]</span>")
        }
    }
}

fn placeholder(message: &str, report: &mut PreviewReport, output: &mut String) {
    report.placeholder_count += 1;
    output.push_str("<div class=\"ab-a2ui-placeholder\">");
    output.push_str(&escape_html(message));
    output.push_str("</div>");
}

fn escape_html(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}

fn preview_css() -> &'static str {
    "body{font:14px system-ui,sans-serif;margin:0;background:#f7f7f8;color:#1b1b1d}main{max-width:760px;margin:0 auto;padding:24px}.ab-a2ui-surface{background:#fff;border:1px solid #d8d8dc;padding:20px;margin-bottom:16px}.ab-a2ui-surface h2{font-size:14px;margin:0 0 16px}.ab-a2ui-row{display:flex;gap:12px;align-items:flex-start}.ab-a2ui-column,.ab-a2ui-list{display:flex;flex-direction:column;gap:10px}.ab-a2ui-card{border:1px solid #d8d8dc;padding:14px}.ab-a2ui-button{padding:8px 12px}.ab-a2ui-media,.ab-a2ui-binding,.ab-a2ui-placeholder{display:inline-block;color:#5b5b62}.ab-a2ui-placeholder{border:1px dashed #a36b00;background:#fff7e5;padding:8px}.ab-a2ui-divider{border:0;border-top:1px solid #ddd;width:100%}"
}

fn validate_complete_surface(
    surface_id: &str,
    state: &SurfaceState,
    report: &mut ValidationReport,
) {
    if state.saw_component_update && !state.has_root {
        report.error(
            "missing_root_component",
            format!("surface '{surface_id}' has components but no component with id 'root'"),
            None,
            None,
        );
    }
    for (index, source, target) in &state.references {
        if !state.components.contains(target) {
            report.error(
                "unknown_component_reference",
                format!("component '{source}' references missing component '{target}'"),
                Some(*index),
                Some(format!("/updateComponents/components/{source}")),
            );
        }
    }
}

fn parse_messages(input: &str) -> Result<Vec<Value>, String> {
    if input.trim().is_empty() {
        return Err("input is empty".to_string());
    }

    let mut values = Vec::new();
    let stream = serde_json::Deserializer::from_str(input).into_iter::<Value>();
    for value in stream {
        values.push(value.map_err(|error| error.to_string())?);
    }

    if values.len() == 1 {
        if let Some(items) = values.pop().and_then(|value| match value {
            Value::Array(items) => Some(items),
            other => {
                values.push(other);
                None
            }
        }) {
            values = items;
        }
    }
    if values.is_empty() {
        return Err("input contains no messages".to_string());
    }
    Ok(values)
}

fn validate_message(
    message: &Value,
    index: usize,
    surfaces: &mut HashMap<String, SurfaceState>,
    report: &mut ValidationReport,
) {
    let Some(object) = message.as_object() else {
        report.error(
            "message_not_object",
            "each A2UI message must be a JSON object",
            Some(index),
            None,
        );
        return;
    };

    let Some(version) = object.get("version").and_then(Value::as_str) else {
        report.error(
            "missing_version",
            "message version must be the string 'v0.9.1'",
            Some(index),
            Some("/version".to_string()),
        );
        return;
    };
    if version != PROTOCOL_VERSION {
        report.error(
            "unsupported_version",
            format!("expected '{PROTOCOL_VERSION}', found '{version}'"),
            Some(index),
            Some("/version".to_string()),
        );
    }

    if let Some(key) = LEGACY_MESSAGE_KEYS
        .iter()
        .find(|key| object.contains_key(**key))
    {
        report.error(
            "legacy_v0_8_message",
            format!("'{key}' is a legacy v0.8 message and is not accepted"),
            Some(index),
            Some(format!("/{key}")),
        );
        return;
    }

    let present: Vec<&str> = MESSAGE_KEYS
        .iter()
        .copied()
        .filter(|key| object.contains_key(*key))
        .collect();
    if present.len() != 1 {
        report.error(
            "invalid_message_envelope",
            "message must contain exactly one supported server message key",
            Some(index),
            None,
        );
        return;
    }
    if object.len() != 2 {
        report.error(
            "unknown_envelope_property",
            "message envelope may contain only 'version' and its message key",
            Some(index),
            None,
        );
    }

    let key = present[0];
    let Some(payload) = object.get(key).and_then(Value::as_object) else {
        report.error(
            "invalid_message_payload",
            format!("'{key}' must be an object"),
            Some(index),
            Some(format!("/{key}")),
        );
        return;
    };
    let Some(surface_id) = required_nonempty_string(payload, "surfaceId", key, index, report)
    else {
        return;
    };

    match key {
        "createSurface" => validate_create(payload, surface_id, index, surfaces, report),
        "updateComponents" => validate_components(payload, surface_id, index, surfaces, report),
        "updateDataModel" => {
            validate_existing_surface(surface_id, key, index, surfaces, report);
        }
        "deleteSurface" => {
            if validate_existing_surface(surface_id, key, index, surfaces, report) {
                if let Some(state) = surfaces.remove(surface_id) {
                    validate_complete_surface(surface_id, &state, report);
                }
            }
        }
        _ => unreachable!(),
    }
}

fn validate_create(
    payload: &Map<String, Value>,
    surface_id: &str,
    index: usize,
    surfaces: &mut HashMap<String, SurfaceState>,
    report: &mut ValidationReport,
) {
    let Some(catalog_id) =
        required_nonempty_string(payload, "catalogId", "createSurface", index, report)
    else {
        return;
    };
    if catalog_id != BASIC_CATALOG_ID {
        report.error(
            "unsupported_catalog",
            format!("P0 accepts only the A2UI v0.9.1 Basic Catalog: {BASIC_CATALOG_ID}"),
            Some(index),
            Some("/createSurface/catalogId".to_string()),
        );
    }
    if surfaces.contains_key(surface_id) {
        report.error(
            "duplicate_surface",
            format!("surface '{surface_id}' already exists"),
            Some(index),
            Some("/createSurface/surfaceId".to_string()),
        );
        return;
    }
    surfaces.insert(surface_id.to_string(), SurfaceState::default());
    report.surface_count += 1;
}

fn validate_components(
    payload: &Map<String, Value>,
    surface_id: &str,
    index: usize,
    surfaces: &mut HashMap<String, SurfaceState>,
    report: &mut ValidationReport,
) {
    let Some(surface) = surfaces.get_mut(surface_id) else {
        report.error(
            "unknown_surface",
            format!("updateComponents references unknown surface '{surface_id}'"),
            Some(index),
            Some("/updateComponents/surfaceId".to_string()),
        );
        return;
    };
    let Some(components) = payload.get("components").and_then(Value::as_array) else {
        report.error(
            "invalid_components",
            "updateComponents.components must be a non-empty array",
            Some(index),
            Some("/updateComponents/components".to_string()),
        );
        return;
    };
    if components.is_empty() {
        report.error(
            "invalid_components",
            "updateComponents.components must be a non-empty array",
            Some(index),
            Some("/updateComponents/components".to_string()),
        );
        return;
    }
    surface.saw_component_update = true;

    let mut batch_ids = HashSet::new();
    for (component_index, component) in components.iter().enumerate() {
        let path = format!("/updateComponents/components/{component_index}");
        let Some(component) = component.as_object() else {
            report.error(
                "component_not_object",
                "component must be an object",
                Some(index),
                Some(path),
            );
            continue;
        };
        let Some(id) = component
            .get("id")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
        else {
            report.error(
                "invalid_component_id",
                "component.id must be a non-empty string",
                Some(index),
                Some(format!("{path}/id")),
            );
            continue;
        };
        if !batch_ids.insert(id.to_string()) {
            report.error(
                "duplicate_component_id",
                format!("component id '{id}' occurs more than once in this update"),
                Some(index),
                Some(format!("{path}/id")),
            );
        }
        let Some(kind) = component.get("component").and_then(Value::as_str) else {
            report.error(
                "invalid_component_type",
                "component.component must be a Basic Catalog component name",
                Some(index),
                Some(format!("{path}/component")),
            );
            continue;
        };
        if !BASIC_COMPONENTS.contains(&kind) {
            report.error(
                "unsupported_component",
                format!("component type '{kind}' is not in the v0.9.1 Basic Catalog"),
                Some(index),
                Some(format!("{path}/component")),
            );
        }
        if id == "root" {
            surface.has_root = true;
        }
        surface.components.insert(id.to_string());
        report.component_count += 1;

        if component.contains_key("action") {
            report.action_count += 1;
        }
        if let Some(child) = component.get("child").and_then(Value::as_str) {
            surface
                .references
                .push((index, id.to_string(), child.to_string()));
        }
        if let Some(children) = component.get("children").and_then(Value::as_array) {
            for (child_index, child) in children.iter().enumerate() {
                if let Some(child) = child.as_str() {
                    surface
                        .references
                        .push((index, id.to_string(), child.to_string()));
                } else {
                    report.error(
                        "invalid_component_reference",
                        "children entries must be component ID strings",
                        Some(index),
                        Some(format!("{path}/children/{child_index}")),
                    );
                }
            }
        }
    }
}

fn validate_existing_surface(
    surface_id: &str,
    key: &str,
    index: usize,
    surfaces: &HashMap<String, SurfaceState>,
    report: &mut ValidationReport,
) -> bool {
    if surfaces.contains_key(surface_id) {
        true
    } else {
        report.error(
            "unknown_surface",
            format!("{key} references unknown surface '{surface_id}'"),
            Some(index),
            Some(format!("/{key}/surfaceId")),
        );
        false
    }
}

fn required_nonempty_string<'a>(
    payload: &'a Map<String, Value>,
    field: &str,
    key: &str,
    index: usize,
    report: &mut ValidationReport,
) -> Option<&'a str> {
    match payload
        .get(field)
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty())
    {
        Some(value) => Some(value),
        None => {
            report.error(
                "missing_required_field",
                format!("{key}.{field} must be a non-empty string"),
                Some(index),
                Some(format!("/{key}/{field}")),
            );
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const CREATE: &str = r#"{"version":"v0.9.1","createSurface":{"surfaceId":"main","catalogId":"https://a2ui.org/specification/v0_9_1/catalogs/basic/catalog.json"}}"#;

    #[test]
    fn accepts_jsonl_and_keeps_actions_non_executable() {
        let input = format!(
            "{CREATE}\n{}",
            r#"{"version":"v0.9.1","updateComponents":{"surfaceId":"main","components":[{"id":"root","component":"Button","child":"label","action":{"event":{"name":"submit"}}},{"id":"label","component":"Text","text":"Submit"}]}}"#
        );
        let report = validate_stream(&input);
        assert!(report.valid, "{:?}", report.errors);
        assert_eq!(report.message_count, 2);
        assert_eq!(report.component_count, 2);
        assert_eq!(report.action_count, 1);
        assert!(!report.execution_allowed);
        assert!(!report.rendering_allowed);
    }

    #[test]
    fn accepts_json_array() {
        let input = format!("[{CREATE}]");
        assert!(validate_stream(&input).valid);
    }

    #[test]
    fn rejects_legacy_v0_8_message() {
        let report = validate_stream(
            r#"{"version":"v0.8","beginRendering":{"surfaceId":"main","root":"root"}}"#,
        );
        assert!(!report.valid);
        assert!(report
            .errors
            .iter()
            .any(|e| e.code == "legacy_v0_8_message"));
    }

    #[test]
    fn rejects_v0_9_in_strict_mode() {
        let report = validate_stream(
            r#"{"version":"v0.9","createSurface":{"surfaceId":"main","catalogId":"https://a2ui.org/specification/v0_9_1/catalogs/basic/catalog.json"}}"#,
        );
        assert!(!report.valid);
        assert!(report
            .errors
            .iter()
            .any(|e| e.code == "unsupported_version"));
    }

    #[test]
    fn rejects_update_before_create() {
        let report = validate_stream(
            r#"{"version":"v0.9.1","updateDataModel":{"surfaceId":"main","path":"/","value":{}}}"#,
        );
        assert!(!report.valid);
        assert!(report.errors.iter().any(|e| e.code == "unknown_surface"));
    }

    #[test]
    fn rejects_missing_root_and_dangling_reference() {
        let input = format!(
            "{CREATE}\n{}",
            r#"{"version":"v0.9.1","updateComponents":{"surfaceId":"main","components":[{"id":"card","component":"Card","child":"missing"}]}}"#
        );
        let report = validate_stream(&input);
        assert!(!report.valid);
        assert!(report
            .errors
            .iter()
            .any(|e| e.code == "missing_root_component"));
        assert!(report
            .errors
            .iter()
            .any(|e| e.code == "unknown_component_reference"));
    }

    #[test]
    fn rejects_unknown_catalog_and_component() {
        let input = concat!(
            r#"{"version":"v0.9.1","createSurface":{"surfaceId":"main","catalogId":"example.invalid/catalog.json"}}"#,
            "\n",
            r#"{"version":"v0.9.1","updateComponents":{"surfaceId":"main","components":[{"id":"root","component":"ShellCommand"}]}}"#
        );
        let report = validate_stream(input);
        assert!(!report.valid);
        assert!(report
            .errors
            .iter()
            .any(|e| e.code == "unsupported_catalog"));
        assert!(report
            .errors
            .iter()
            .any(|e| e.code == "unsupported_component"));
    }

    #[test]
    fn rejects_updates_after_delete() {
        let input = format!(
            "{CREATE}\n{}\n{}",
            r#"{"version":"v0.9.1","deleteSurface":{"surfaceId":"main"}}"#,
            r#"{"version":"v0.9.1","updateDataModel":{"surfaceId":"main","value":{}}}"#
        );
        let report = validate_stream(&input);
        assert!(!report.valid);
        assert!(report.errors.iter().any(|e| e.code == "unknown_surface"));
    }

    #[test]
    fn rejects_malformed_json() {
        let report = validate_stream(r#"{"version":"v0.9.1"#);
        assert!(!report.valid);
        assert_eq!(report.errors[0].code, "invalid_json");
    }

    #[test]
    fn preview_is_static_and_disables_actions() {
        let input = format!(
            "{CREATE}\n{}",
            r#"{"version":"v0.9.1","updateComponents":{"surfaceId":"main","components":[{"id":"root","component":"Button","child":"label","action":{"event":{"name":"submit"}}},{"id":"label","component":"Text","text":"<Submit & continue>"}]}}"#
        );
        let preview = render_html_preview(&input);
        let html = preview.html.expect("valid stream should render");
        assert!(preview.report.preview_generated);
        assert!(!preview.report.execution_allowed);
        assert!(!preview.report.interactive);
        assert_eq!(preview.report.disabled_action_count, 1);
        assert!(html.contains("disabled aria-disabled=\"true\""));
        assert!(html.contains("&lt;Submit &amp; continue&gt;"));
        assert!(!html.contains("onclick"));
    }

    #[test]
    fn preview_uses_placeholders_without_evaluating_bindings() {
        let input = format!(
            "{CREATE}\n{}",
            r#"{"version":"v0.9.1","updateComponents":{"surfaceId":"main","components":[{"id":"root","component":"Text","text":{"path":"/user/name"}}]}}"#
        );
        let preview = render_html_preview(&input);
        let html = preview.html.expect("valid stream should render");
        assert!(html.contains("data binding"));
        assert!(preview.report.placeholder_count > 0);
    }

    #[test]
    fn invalid_stream_never_generates_preview() {
        let preview = render_html_preview(r#"{"version":"v0.8","beginRendering":{}}"#);
        assert!(!preview.report.valid);
        assert!(!preview.report.preview_generated);
        assert!(preview.html.is_none());
    }
}
