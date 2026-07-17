//! Model Context Protocol — server-side tool registry, protocol types,
//! stdio transport.
//!
//! - [`McpTool`] / [`ToolRegistry`]: the extension point exposed to Claude.
//! - [`protocol`]: JSON-RPC 2.0 messages shaped per MCP 2024-11-05 spec.
//! - [`server`]: line-delimited stdio main loop.

use ab_core::Result;
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;

pub mod protocol;
pub mod server;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolSchema {
    pub name: String,
    pub description: String,
    /// JSON-Schema for `arguments`.
    pub input_schema: Value,
}

/// Optional safety hints for MCP tool descriptors.
///
/// Existing tools omit annotations until their behavior is explicitly
/// classified, which preserves legacy client approval behavior. New surfaces
/// can opt in to a conservative or read-only contract.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct ToolAnnotations {
    #[serde(rename = "readOnlyHint")]
    pub read_only_hint: bool,
    #[serde(rename = "destructiveHint")]
    pub destructive_hint: bool,
    #[serde(rename = "openWorldHint")]
    pub open_world_hint: bool,
    #[serde(
        default,
        rename = "idempotentHint",
        skip_serializing_if = "Option::is_none"
    )]
    pub idempotent_hint: Option<bool>,
}

impl ToolAnnotations {
    pub const fn conservative() -> Self {
        Self {
            read_only_hint: false,
            destructive_hint: true,
            open_world_hint: true,
            idempotent_hint: None,
        }
    }

    pub const fn read_only() -> Self {
        Self {
            read_only_hint: true,
            destructive_hint: false,
            open_world_hint: false,
            idempotent_hint: Some(true),
        }
    }
}

impl Default for ToolAnnotations {
    fn default() -> Self {
        Self::conservative()
    }
}

/// Fully described registry entry used by `tools/list`.
#[derive(Debug, Clone)]
pub struct ToolDescriptor {
    pub schema: ToolSchema,
    pub title: String,
    pub annotations: Option<ToolAnnotations>,
    pub output_schema: Option<Value>,
}

pub fn default_tool_title(name: &str) -> String {
    let mut title = name.replace('_', " ");
    if let Some(first) = title.get_mut(0..1) {
        first.make_ascii_uppercase();
    }
    title
}

/// Per-invocation context passed to every tool. Lets tools reach into shared
/// state without each tool importing every backend trait directly.
#[derive(Default)]
pub struct ToolContext {
    pub session_id: Option<ab_core::SessionId>,
    pub extras: HashMap<String, Value>,
}

/// One block in an MCP tool result. Per the MCP spec the wire-format `type`
/// discriminator uses lowercase strings (`"text"`, `"image"`, `"resource"`),
/// hence the explicit `rename` attributes. The MCP image block also expects
/// a camelCase `mimeType` field — annotated below.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum ContentBlock {
    #[serde(rename = "text")]
    Text { text: String },

    /// Inline image. `data` is the **base64-encoded** raw bytes (no
    /// `data:` URL prefix). MCP-aware clients (Claude Code) will render
    /// this directly into the model's context.
    #[serde(rename = "image")]
    Image {
        data: String,
        #[serde(rename = "mimeType")]
        mime_type: String,
    },
}

impl ContentBlock {
    pub fn text(s: impl Into<String>) -> Self {
        Self::Text { text: s.into() }
    }
    pub fn image(base64: impl Into<String>, mime: impl Into<String>) -> Self {
        Self::Image {
            data: base64.into(),
            mime_type: mime.into(),
        }
    }
}

/// Result of a `tools/call` invocation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult {
    pub content: Vec<ContentBlock>,
    #[serde(
        default,
        rename = "structuredContent",
        skip_serializing_if = "Option::is_none"
    )]
    pub structured_content: Option<Value>,
    #[serde(default, rename = "isError")]
    pub is_error: bool,
    /// Injected by the MCP stdio server on every `tools/call` response for support logs.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub backend_id: Option<Value>,
}

impl ToolResult {
    pub fn text(s: impl Into<String>) -> Self {
        Self {
            content: vec![ContentBlock::text(s)],
            structured_content: None,
            is_error: false,
            backend_id: None,
        }
    }
    pub fn error(s: impl Into<String>) -> Self {
        Self {
            content: vec![ContentBlock::text(s)],
            structured_content: None,
            is_error: true,
            backend_id: None,
        }
    }
    pub fn json_text(v: &Value) -> Self {
        Self::text(serde_json::to_string_pretty(v).unwrap_or_else(|_| v.to_string()))
    }
    /// Return the same JSON object through the modern structured channel and
    /// the legacy text channel. ChatGPT knowledge tools require both.
    pub fn structured_json(v: &Value) -> Self {
        Self {
            content: vec![ContentBlock::text(
                serde_json::to_string(v).unwrap_or_else(|_| v.to_string()),
            )],
            structured_content: Some(v.clone()),
            is_error: false,
            backend_id: None,
        }
    }
    /// Build a result whose single block is an inline image.
    pub fn image(base64: impl Into<String>, mime: impl Into<String>) -> Self {
        Self {
            content: vec![ContentBlock::image(base64, mime)],
            structured_content: None,
            is_error: false,
            backend_id: None,
        }
    }
    /// Image + a one-line text caption (some clients prefer the caption for
    /// alt-text; both blocks are returned in `content`).
    pub fn image_with_caption(
        base64: impl Into<String>,
        mime: impl Into<String>,
        caption: impl Into<String>,
    ) -> Self {
        Self {
            content: vec![
                ContentBlock::image(base64, mime),
                ContentBlock::text(caption),
            ],
            structured_content: None,
            is_error: false,
            backend_id: None,
        }
    }
}

#[async_trait]
pub trait McpTool: Send + Sync {
    fn name(&self) -> &'static str;
    fn schema(&self) -> ToolSchema;
    fn title(&self) -> String {
        default_tool_title(self.name())
    }
    fn annotations(&self) -> Option<ToolAnnotations> {
        None
    }
    fn output_schema(&self) -> Option<Value> {
        None
    }
    async fn execute(&self, args: Value, ctx: &ToolContext) -> Result<ToolResult>;
}

#[derive(Default, Clone)]
pub struct ToolRegistry {
    tools: HashMap<String, Arc<dyn McpTool>>,
}

impl ToolRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register(&mut self, tool: Arc<dyn McpTool>) {
        self.tools.insert(tool.name().to_string(), tool);
    }

    pub fn get(&self, name: &str) -> Option<Arc<dyn McpTool>> {
        self.tools.get(name).cloned()
    }

    pub fn list(&self) -> Vec<ToolSchema> {
        let mut v: Vec<_> = self.tools.values().map(|t| t.schema()).collect();
        v.sort_by(|a, b| a.name.cmp(&b.name));
        v
    }

    pub fn descriptors(&self) -> Vec<ToolDescriptor> {
        let mut v: Vec<_> = self
            .tools
            .values()
            .map(|tool| ToolDescriptor {
                schema: tool.schema(),
                title: tool.title(),
                annotations: tool.annotations(),
                output_schema: tool.output_schema(),
            })
            .collect();
        v.sort_by(|a, b| a.schema.name.cmp(&b.schema.name));
        v
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn structured_json_keeps_text_and_structured_channels_identical() {
        let value = json!({ "results": [{ "id": "memory-1" }] });
        let result = ToolResult::structured_json(&value);

        assert_eq!(result.structured_content, Some(value.clone()));
        assert!(!result.is_error);
        let ContentBlock::Text { text } = &result.content[0] else {
            panic!("expected text compatibility block")
        };
        assert_eq!(serde_json::from_str::<Value>(text).unwrap(), value);

        let serialized = serde_json::to_value(result).unwrap();
        assert_eq!(serialized["structuredContent"], value);
    }
}
