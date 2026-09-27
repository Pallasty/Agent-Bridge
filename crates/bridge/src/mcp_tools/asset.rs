//! Read-only inspection of explicitly selected local PNG and GLB assets.

use std::path::Path;

use ab_core::Result;
use ab_mcp::{McpTool, ToolAnnotations, ToolContext, ToolResult, ToolSchema};
use async_trait::async_trait;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::asset_inspect::{inspect_file, MAX_FILE_BYTES, REPORT_SCHEMA};

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct AssetInspectArgs {
    path: String,
    expected_sha256: Option<String>,
}

#[derive(Default)]
pub struct AssetInspectTool;

impl AssetInspectTool {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for AssetInspectTool {
    fn name(&self) -> &'static str {
        "asset_inspect"
    }

    fn annotations(&self) -> Option<ToolAnnotations> {
        Some(ToolAnnotations::read_only())
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: format!(
                "Inspect one explicitly selected local PNG or GLB file, bounded to {MAX_FILE_BYTES} bytes. \
                 Returns SHA-256, optional expected-hash verification, decoded PNG facts or limited \
                 GLB container/JSON facts. Does not verify mesh semantics or visual quality, follow \
                 external resources, render, execute commands, or write files or task outcomes. Niche/opt-in."
            ),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Path to one existing local PNG or GLB file."
                    },
                    "expected_sha256": {
                        "type": ["string", "null"],
                        "pattern": "^[A-Fa-f0-9]{64}$",
                        "description": "Optional SHA-256 to verify, accepting either letter case. Null omits the comparison."
                    }
                },
                "required": ["path"],
                "additionalProperties": false
            }),
        }
    }

    fn output_schema(&self) -> Option<Value> {
        Some(json!({
            "type": "object",
            "properties": {
                "schema": {"const": REPORT_SCHEMA},
                "path": {"type": "string", "minLength": 1},
                "bytes": {"type": "integer", "minimum": 1, "maximum": MAX_FILE_BYTES},
                "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "expected_sha256_matches": {"type": ["boolean", "null"]},
                "format": {"type": "string", "enum": ["png", "glb"]},
                "inspection_level": {"type": "string", "minLength": 1},
                "details": {"type": "object"},
                "mesh_semantics_verified": {"const": false},
                "visual_quality_reviewed": {"const": false}
            },
            "required": [
                "schema", "path", "bytes", "sha256", "expected_sha256_matches",
                "format", "inspection_level", "details", "mesh_semantics_verified",
                "visual_quality_reviewed"
            ],
            "additionalProperties": false
        }))
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let request: AssetInspectArgs = match serde_json::from_value(args) {
            Ok(request) => request,
            Err(error) => {
                return Ok(ToolResult::error(format!(
                    "invalid asset_inspect arguments: {error}"
                )));
            }
        };
        if request.path.is_empty() {
            return Ok(ToolResult::error("asset_inspect path must not be empty"));
        }

        let result = tokio::task::spawn_blocking(move || {
            inspect_file(Path::new(&request.path), request.expected_sha256.as_deref())
        })
        .await;
        Ok(match result {
            Ok(Ok(report)) => ToolResult::structured_json(&report),
            Ok(Err(error)) => ToolResult::error(format!("asset inspection rejected: {error:#}")),
            Err(error) => ToolResult::error(format!("asset inspection worker failed: {error}")),
        })
    }
}

#[cfg(test)]
mod tests {
    use std::{fs, path::Path};

    use ab_mcp::ToolAnnotations;
    use sha2::{Digest, Sha256};

    use super::*;

    fn write_png(path: &Path) -> Vec<u8> {
        let mut bytes = Vec::new();
        {
            let mut encoder = png::Encoder::new(&mut bytes, 2, 1);
            encoder.set_color(png::ColorType::Rgba);
            encoder.set_depth(png::BitDepth::Eight);
            let mut writer = encoder.write_header().expect("PNG fixture header");
            writer
                .write_image_data(&[12, 34, 56, 255, 78, 90, 12, 0])
                .expect("PNG fixture pixels");
        }
        fs::write(path, &bytes).expect("write PNG fixture");
        bytes
    }

    #[tokio::test]
    async fn asset_inspect_handler_decodes_png_without_changing_source() {
        let directory = tempfile::tempdir().expect("fixture directory");
        let path = directory.path().join("prop.png");
        let bytes = write_png(&path);

        let result = AssetInspectTool::new()
            .execute(json!({"path": path}), &ToolContext::default())
            .await
            .expect("MCP response");

        assert!(!result.is_error, "{result:?}");
        let report = result.structured_content.expect("structured report");
        assert_eq!(report["schema"], "agent_bridge.asset_inspection.v1");
        assert_eq!(report["format"], "png");
        assert_eq!(report["bytes"], bytes.len());
        assert_eq!(report["sha256"], format!("{:x}", Sha256::digest(&bytes)));
        assert!(report["expected_sha256_matches"].is_null());
        assert_eq!(report["details"]["width"], 2);
        assert_eq!(report["details"]["height"], 1);
        assert_eq!(report["mesh_semantics_verified"], false);
        assert_eq!(report["visual_quality_reviewed"], false);
        assert_eq!(fs::read(path).expect("retained source"), bytes);
    }

    #[tokio::test]
    async fn asset_inspect_handler_accepts_matching_uppercase_sha256() {
        let directory = tempfile::tempdir().expect("fixture directory");
        let path = directory.path().join("prop.png");
        let bytes = write_png(&path);
        let digest = format!("{:X}", Sha256::digest(&bytes));

        let result = AssetInspectTool::new()
            .execute(
                json!({"path": path, "expected_sha256": digest}),
                &ToolContext::default(),
            )
            .await
            .expect("MCP response");

        assert!(!result.is_error, "{result:?}");
        assert_eq!(
            result.structured_content.expect("structured report")["expected_sha256_matches"],
            true
        );
    }

    #[tokio::test]
    async fn asset_inspect_handler_rejects_mismatched_sha256() {
        let directory = tempfile::tempdir().expect("fixture directory");
        let path = directory.path().join("prop.png");
        write_png(&path);

        let result = AssetInspectTool::new()
            .execute(
                json!({"path": path, "expected_sha256": "0".repeat(64)}),
                &ToolContext::default(),
            )
            .await
            .expect("MCP response");

        assert!(result.is_error);
        assert!(result.structured_content.is_none());
    }

    #[tokio::test]
    async fn asset_inspect_handler_rejects_invalid_arguments() {
        let directory = tempfile::tempdir().expect("fixture directory");
        let path = directory.path().join("prop.png");
        write_png(&path);

        for arguments in [
            json!({}),
            json!({"path": 42}),
            json!({"path": path, "expected_sha256": false}),
            json!({"path": path, "extra": true}),
            json!({"path": ""}),
            json!([]),
        ] {
            let result = AssetInspectTool::new()
                .execute(arguments, &ToolContext::default())
                .await
                .expect("MCP response");
            assert!(result.is_error);
            assert!(result.structured_content.is_none());
        }
    }

    #[test]
    fn asset_inspect_descriptor_declares_bounded_read_only_contract() {
        let tool = AssetInspectTool::new();
        assert_eq!(tool.annotations(), Some(ToolAnnotations::read_only()));
        let input = tool.schema().input_schema;
        assert_eq!(input["additionalProperties"], false);
        assert_eq!(input["required"], json!(["path"]));
        let output = tool.output_schema().expect("declared output schema");
        assert_eq!(
            output["properties"]["schema"]["const"],
            "agent_bridge.asset_inspection.v1"
        );
        let required = output["required"].as_array().expect("required fields");
        for field in [
            "schema",
            "path",
            "bytes",
            "sha256",
            "expected_sha256_matches",
            "format",
            "inspection_level",
            "details",
            "mesh_semantics_verified",
            "visual_quality_reviewed",
        ] {
            assert!(required.contains(&json!(field)), "missing field {field}");
        }
    }

    #[test]
    fn asset_inspect_registry_exposes_only_opt_in_profiles() {
        for (toolset, profile) in [(None, Some("all")), (Some("all-dev"), None)] {
            let registry = super::super::build_registry_with_policy(
                crate::Hub::builder().build(),
                super::super::ToolPolicy::from_values(toolset, None, None, profile),
            );
            let descriptor = registry
                .descriptors()
                .into_iter()
                .find(|descriptor| descriptor.schema.name == "asset_inspect")
                .expect("registered asset inspector");
            assert_eq!(descriptor.annotations, Some(ToolAnnotations::read_only()));
            assert_eq!(
                descriptor.output_schema,
                AssetInspectTool::new().output_schema()
            );
            assert_eq!(
                descriptor.schema.input_schema["additionalProperties"],
                false
            );
        }
        for (toolset, profile) in [
            (None, Some("standard")),
            (None, Some("essential")),
            (None, Some("compact")),
            (Some("codex-essential"), None),
            (Some("codex-lean"), None),
        ] {
            let names = super::super::exposed_tool_names_for(toolset, None, profile);
            assert!(!names.iter().any(|name| name == "asset_inspect"));
        }
    }
}
