//! Read-only A2UI v0.9.1 MCP transport.

use super::*;

const A2UI_MIME_TYPE: &str = "application/a2ui+json";
const A2UI_PREVIEW_MIME_TYPE: &str = "text/html";
const A2UI_MAX_INPUT_BYTES: usize = 256 * 1024;

pub struct A2uiValidateTool;

impl A2uiValidateTool {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for A2uiValidateTool {
    fn name(&self) -> &'static str {
        "a2ui_validate"
    }

    fn title(&self) -> String {
        "Validate an A2UI v0.9.1 stream".into()
    }

    fn annotations(&self) -> Option<ToolAnnotations> {
        Some(ToolAnnotations::read_only())
    }

    fn output_schema(&self) -> Option<Value> {
        Some(json!({
            "type": "object",
            "properties": {
                "schema": {"const": crate::a2ui::REPORT_SCHEMA},
                "protocol_version": {"const": crate::a2ui::PROTOCOL_VERSION},
                "valid": {"type": "boolean"},
                "execution_allowed": {"const": false},
                "rendering_allowed": {"const": false},
                "message_count": {"type": "integer", "minimum": 0},
                "surface_count": {"type": "integer", "minimum": 0},
                "component_count": {"type": "integer", "minimum": 0},
                "action_count": {"type": "integer", "minimum": 0},
                "errors": {"type": "array"},
                "warnings": {"type": "array"},
                "resource_uri": {"type": "string"},
                "mime_type": {"const": A2UI_MIME_TYPE}
            },
            "required": [
                "schema", "protocol_version", "valid", "execution_allowed",
                "rendering_allowed", "message_count", "surface_count",
                "component_count", "action_count", "errors", "warnings"
            ],
            "additionalProperties": false
        }))
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Validate an A2UI v0.9.1 server-message stream and, only when valid, return it as an MCP EmbeddedResource with MIME application/a2ui+json. Accepts a JSON/JSONL string, one message object, or an array of messages. This P1 surface is read-only: it never renders UI, executes described actions, dispatches browser/terminal operations, persists the payload, or grants authority. Niche/opt-in.".into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "messages": {
                        "description": "A2UI v0.9.1 stream as JSON/JSONL text, one message object, or an array of messages.",
                        "oneOf": [
                            {"type": "string", "maxLength": A2UI_MAX_INPUT_BYTES},
                            {"type": "object"},
                            {"type": "array", "minItems": 1}
                        ]
                    }
                },
                "required": ["messages"],
                "additionalProperties": false
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let raw = match normalize_a2ui_input(&args) {
            Ok(raw) => raw,
            Err(result) => return Ok(result),
        };

        let report = crate::a2ui::validate_stream(&raw);
        let mut structured = serde_json::to_value(&report)?;
        if !report.valid {
            return Ok(ToolResult {
                content: vec![ContentBlock::text(serde_json::to_string(&structured)?)],
                structured_content: Some(structured),
                is_error: true,
                backend_id: None,
            });
        }

        let digest = format!("{:x}", Sha256::digest(raw.as_bytes()));
        let resource_uri = format!("agent-bridge://a2ui/validated/{}", &digest[..16]);
        let object = structured
            .as_object_mut()
            .expect("serialized validation report is an object");
        object.insert("resource_uri".into(), Value::String(resource_uri.clone()));
        object.insert("mime_type".into(), Value::String(A2UI_MIME_TYPE.into()));

        Ok(ToolResult {
            content: vec![
                ContentBlock::text(format!(
                    "Validated A2UI v0.9.1: {} messages, {} surfaces, {} components, {} described actions; execution=false rendering=false",
                    report.message_count,
                    report.surface_count,
                    report.component_count,
                    report.action_count
                )),
                ContentBlock::embedded_text_resource(resource_uri, A2UI_MIME_TYPE, raw),
            ],
            structured_content: Some(structured),
            is_error: false,
            backend_id: None,
        })
    }
}

pub struct A2uiPreviewTool;

impl A2uiPreviewTool {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for A2uiPreviewTool {
    fn name(&self) -> &'static str {
        "a2ui_preview"
    }

    fn title(&self) -> String {
        "Create a read-only A2UI HTML preview".into()
    }

    fn annotations(&self) -> Option<ToolAnnotations> {
        Some(ToolAnnotations::read_only())
    }

    fn output_schema(&self) -> Option<Value> {
        Some(json!({
            "type": "object",
            "properties": {
                "schema": {"const": crate::a2ui::PREVIEW_REPORT_SCHEMA},
                "protocol_version": {"const": crate::a2ui::PROTOCOL_VERSION},
                "valid": {"type": "boolean"},
                "preview_generated": {"type": "boolean"},
                "execution_allowed": {"const": false},
                "interactive": {"const": false},
                "message_count": {"type": "integer", "minimum": 0},
                "surface_count": {"type": "integer", "minimum": 0},
                "rendered_component_count": {"type": "integer", "minimum": 0},
                "placeholder_count": {"type": "integer", "minimum": 0},
                "disabled_action_count": {"type": "integer", "minimum": 0},
                "errors": {"type": "array"},
                "warnings": {"type": "array"},
                "preview_uri": {"type": "string"},
                "mime_type": {"const": A2UI_PREVIEW_MIME_TYPE}
            },
            "required": [
                "schema", "protocol_version", "valid", "preview_generated",
                "execution_allowed", "interactive", "message_count", "surface_count",
                "rendered_component_count", "placeholder_count", "disabled_action_count",
                "errors", "warnings"
            ],
            "additionalProperties": false
        }))
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Validate an A2UI v0.9.1 stream then return a limited, static HTML preview as an MCP EmbeddedResource. Buttons are disabled; actions and data-model bindings are never executed or evaluated; remote assets are not fetched; unsupported components are explicit placeholders. Nothing is persisted or opened in a browser. Niche/opt-in.".into(),
            input_schema: a2ui_input_schema(),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let raw = match normalize_a2ui_input(&args) {
            Ok(raw) => raw,
            Err(result) => return Ok(result),
        };
        let preview = crate::a2ui::render_html_preview(&raw);
        let mut structured = serde_json::to_value(&preview.report)?;
        if !preview.report.valid {
            return Ok(ToolResult {
                content: vec![ContentBlock::text(serde_json::to_string(&structured)?)],
                structured_content: Some(structured),
                is_error: true,
                backend_id: None,
            });
        }

        let html = preview.html.expect("valid A2UI preview has HTML");
        let digest = format!("{:x}", Sha256::digest(raw.as_bytes()));
        let preview_uri = format!("agent-bridge://a2ui/preview/{}", &digest[..16]);
        let object = structured
            .as_object_mut()
            .expect("serialized preview report is an object");
        object.insert("preview_uri".into(), Value::String(preview_uri.clone()));
        object.insert(
            "mime_type".into(),
            Value::String(A2UI_PREVIEW_MIME_TYPE.into()),
        );

        Ok(ToolResult {
            content: vec![
                ContentBlock::text(format!(
                    "Read-only A2UI preview: {} surfaces, {} rendered components, {} placeholders, {} disabled actions; execution=false interactive=false",
                    preview.report.surface_count,
                    preview.report.rendered_component_count,
                    preview.report.placeholder_count,
                    preview.report.disabled_action_count,
                )),
                ContentBlock::embedded_text_resource(preview_uri, A2UI_PREVIEW_MIME_TYPE, html),
            ],
            structured_content: Some(structured),
            is_error: false,
            backend_id: None,
        })
    }
}

fn a2ui_input_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "messages": {
                "description": "A2UI v0.9.1 stream as JSON/JSONL text, one message object, or an array of messages.",
                "oneOf": [
                    {"type": "string", "maxLength": A2UI_MAX_INPUT_BYTES},
                    {"type": "object"},
                    {"type": "array", "minItems": 1}
                ]
            }
        },
        "required": ["messages"],
        "additionalProperties": false
    })
}

fn normalize_a2ui_input(args: &Value) -> std::result::Result<String, ToolResult> {
    let Some(messages) = args.get("messages") else {
        return Err(ToolResult::error("missing 'messages'"));
    };
    let raw = match messages {
        Value::String(raw) => raw.clone(),
        Value::Object(_) | Value::Array(_) => match serde_json::to_string(messages) {
            Ok(raw) => raw,
            Err(error) => return Err(ToolResult::error(error.to_string())),
        },
        _ => {
            return Err(ToolResult::error(
                "'messages' must be JSON/JSONL text, an object, or an array",
            ))
        }
    };
    if raw.len() > A2UI_MAX_INPUT_BYTES {
        return Err(ToolResult::error(format!(
            "A2UI input exceeds the {A2UI_MAX_INPUT_BYTES}-byte limit"
        )));
    }
    Ok(raw)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_messages() -> Value {
        json!([
            {
                "version": "v0.9.1",
                "createSurface": {
                    "surfaceId": "main",
                    "catalogId": "https://a2ui.org/specification/v0_9_1/catalogs/basic/catalog.json"
                }
            },
            {
                "version": "v0.9.1",
                "updateComponents": {
                    "surfaceId": "main",
                    "components": [{"id": "root", "component": "Text", "text": "Hello"}]
                }
            }
        ])
    }

    #[tokio::test]
    async fn valid_stream_returns_typed_resource_without_authority() {
        let result = A2uiValidateTool::new()
            .execute(
                json!({"messages": valid_messages()}),
                &ToolContext::default(),
            )
            .await
            .unwrap();
        assert!(!result.is_error);
        assert_eq!(result.content.len(), 2);
        let ContentBlock::Resource { resource } = &result.content[1] else {
            panic!("expected embedded resource")
        };
        assert_eq!(resource.mime_type, A2UI_MIME_TYPE);
        assert!(resource.uri.starts_with("agent-bridge://a2ui/validated/"));
        let structured = result.structured_content.unwrap();
        assert_eq!(structured["valid"], true);
        assert_eq!(structured["execution_allowed"], false);
        assert_eq!(structured["rendering_allowed"], false);
    }

    #[tokio::test]
    async fn invalid_stream_never_returns_resource() {
        let result = A2uiValidateTool::new()
            .execute(
                json!({"messages": {"version":"v0.8","beginRendering":{"surfaceId":"main","root":"root"}}}),
                &ToolContext::default(),
            )
            .await
            .unwrap();
        assert!(result.is_error);
        assert!(result
            .content
            .iter()
            .all(|block| !matches!(block, ContentBlock::Resource { .. })));
        assert_eq!(result.structured_content.unwrap()["valid"], false);
    }

    #[tokio::test]
    async fn oversized_input_fails_before_validation() {
        let result = A2uiValidateTool::new()
            .execute(
                json!({"messages": "x".repeat(A2UI_MAX_INPUT_BYTES + 1)}),
                &ToolContext::default(),
            )
            .await
            .unwrap();
        assert!(result.is_error);
        assert!(result.structured_content.is_none());
    }

    #[tokio::test]
    async fn preview_returns_static_html_without_execution() {
        let result = A2uiPreviewTool::new()
            .execute(
                json!({
                    "messages": [
                        {
                            "version": "v0.9.1",
                            "createSurface": {
                                "surfaceId": "main",
                                "catalogId": "https://a2ui.org/specification/v0_9_1/catalogs/basic/catalog.json"
                            }
                        },
                        {
                            "version": "v0.9.1",
                            "updateComponents": {
                                "surfaceId": "main",
                                "components": [
                                    {"id": "root", "component": "Button", "child": "label", "action": {"event": {"name": "submit"}}},
                                    {"id": "label", "component": "Text", "text": "Submit"}
                                ]
                            }
                        }
                    ]
                }),
                &ToolContext::default(),
            )
            .await
            .unwrap();
        assert!(!result.is_error);
        let ContentBlock::Resource { resource } = &result.content[1] else {
            panic!("expected HTML embedded resource")
        };
        assert_eq!(resource.mime_type, A2UI_PREVIEW_MIME_TYPE);
        assert!(resource.uri.starts_with("agent-bridge://a2ui/preview/"));
        assert!(resource.text.contains("disabled aria-disabled=\"true\""));
        assert!(!resource.text.contains("onclick"));
        let structured = result.structured_content.unwrap();
        assert_eq!(structured["preview_generated"], true);
        assert_eq!(structured["execution_allowed"], false);
        assert_eq!(structured["interactive"], false);
    }

    #[tokio::test]
    async fn invalid_preview_never_returns_html_resource() {
        let result = A2uiPreviewTool::new()
            .execute(
                json!({"messages": {"version":"v0.8","beginRendering":{"surfaceId":"main"}}}),
                &ToolContext::default(),
            )
            .await
            .unwrap();
        assert!(result.is_error);
        assert!(result
            .content
            .iter()
            .all(|block| !matches!(block, ContentBlock::Resource { .. })));
        assert_eq!(
            result.structured_content.unwrap()["preview_generated"],
            false
        );
    }

    #[test]
    fn tool_is_opt_in_and_does_not_expand_codex_lean() {
        let all = super::super::exposed_tool_names_for(Some("all-dev"), None, None);
        assert!(all.iter().any(|name| name == "a2ui_validate"));
        assert!(all.iter().any(|name| name == "a2ui_preview"));
        let lean = super::super::exposed_tool_names_for(Some("codex-lean"), None, None);
        assert!(!lean.iter().any(|name| name == "a2ui_validate"));
        assert!(!lean.iter().any(|name| name == "a2ui_preview"));
    }
}
