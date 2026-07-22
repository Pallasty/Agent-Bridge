//! Read-only, fail-closed validation for A2UI v0.9.1 server message streams.

use serde::Serialize;
use serde_json::{Map, Value};
use std::collections::{HashMap, HashSet};

pub const PROTOCOL_VERSION: &str = "v0.9.1";
pub const REPORT_SCHEMA: &str = "agent_bridge.a2ui.validation_report.v0";

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
}
