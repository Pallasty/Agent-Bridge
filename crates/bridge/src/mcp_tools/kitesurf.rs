use super::*;

const INLINE_IMAGE_MAX_BYTES: usize = 8 * 1024 * 1024;
const MARKDOWN_MAX_CHARS: usize = 32_000;
const A11Y_MAX_CHARS: usize = 48_000;

pub(super) struct CloudflareKitesurfSnapshotTool {
    hub: Hub,
}

impl CloudflareKitesurfSnapshotTool {
    pub(super) fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for CloudflareKitesurfSnapshotTool {
    fn name(&self) -> &'static str {
        "cloudflare_kitesurf_snapshot"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Capture a stateless, read-only Kitesurf evidence bundle for a public \
                 URL: screenshot digest, bounded Markdown, accessibility tree, metadata, and \
                 optional inline PNG. Requires runtime opt-in, Browser policy, Cloudflare \
                 credentials, and per_call_opt_in=true."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Public http/https URL. Credentials and local/private hosts are rejected."
                    },
                    "per_call_opt_in": {
                        "type": "boolean",
                        "default": false,
                        "description": "Consent to send this public URL to Cloudflare Browser Run."
                    },
                    "include_image": {
                        "type": "boolean",
                        "default": false,
                        "description": "Include the PNG as an MCP image block. Digest and byte count are always returned."
                    },
                    "viewport_width": {
                        "type": "integer",
                        "default": 1280,
                        "minimum": 320,
                        "maximum": 3840
                    },
                    "viewport_height": {
                        "type": "integer",
                        "default": 720,
                        "minimum": 240,
                        "maximum": 2160
                    },
                    "wait_until": {
                        "type": "string",
                        "enum": ["domcontentloaded", "load", "networkidle0", "networkidle2"],
                        "default": "domcontentloaded"
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "default": 15000,
                        "minimum": 1000,
                        "maximum": 45000
                    }
                },
                "required": ["url", "per_call_opt_in"],
                "additionalProperties": false
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(error) = self.hub.security.check(Cap::Browser) {
            return Ok(ToolResult::error(error));
        }
        if args.get("per_call_opt_in").and_then(Value::as_bool) != Some(true) {
            return Ok(ToolResult::error(
                "per_call_opt_in=true is required before sending a URL to Cloudflare Browser Run",
            ));
        }
        let url = match args
            .get("url")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
        {
            Some(url) => url,
            None => return Ok(ToolResult::error("missing or empty 'url'")),
        };
        let request = crate::cloudflare_api::KitesurfSnapshotRequest {
            url: url.to_string(),
            viewport_width: bounded_u32(&args, "viewport_width", 1280, 320, 3840),
            viewport_height: bounded_u32(&args, "viewport_height", 720, 240, 2160),
            wait_until: args
                .get("wait_until")
                .and_then(Value::as_str)
                .unwrap_or("domcontentloaded")
                .to_string(),
            timeout_ms: bounded_u32(&args, "timeout_ms", 15_000, 1_000, 45_000),
        };
        let include_image = args
            .get("include_image")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let client = match crate::cloudflare_api::CloudflareClient::from_env() {
            Ok(client) => client,
            Err(error) => return Ok(ToolResult::error(format!("{error}"))),
        };
        let snapshot = match client.kitesurf_snapshot(&request).await {
            Ok(snapshot) => snapshot,
            Err(error) => return Ok(ToolResult::error(format!("{error}"))),
        };
        result_from_snapshot(snapshot, request, include_image)
    }
}

fn bounded_u32(args: &Value, key: &str, default: u32, min: u32, max: u32) -> u32 {
    args.get(key)
        .and_then(Value::as_u64)
        .unwrap_or(u64::from(default))
        .clamp(u64::from(min), u64::from(max)) as u32
}

fn result_from_snapshot(
    snapshot: crate::cloudflare_api::KitesurfSnapshot,
    request: crate::cloudflare_api::KitesurfSnapshotRequest,
    include_image: bool,
) -> Result<ToolResult> {
    let screenshot = match general_purpose::STANDARD.decode(&snapshot.screenshot_base64) {
        Ok(bytes) => bytes,
        Err(error) => {
            return Ok(ToolResult::error(format!(
                "cloudflare kitesurf snapshot returned invalid screenshot base64: {error}"
            )))
        }
    };
    if screenshot.len() > INLINE_IMAGE_MAX_BYTES {
        return Ok(ToolResult::error(format!(
            "cloudflare kitesurf screenshot exceeds {INLINE_IMAGE_MAX_BYTES} bytes"
        )));
    }

    let (markdown, markdown_truncated, markdown_chars) =
        truncate_chars(&snapshot.markdown, MARKDOWN_MAX_CHARS);
    let accessibility_raw =
        serde_json::to_string(&snapshot.accessibility_tree).unwrap_or_else(|_| "null".to_string());
    let (accessibility_preview, accessibility_truncated, accessibility_chars) =
        truncate_chars(&accessibility_raw, A11Y_MAX_CHARS);
    let accessibility_tree = if accessibility_truncated {
        json!({
            "truncated": true,
            "original_chars": accessibility_chars,
            "json_preview": accessibility_preview
        })
    } else {
        snapshot.accessibility_tree
    };
    let metadata = json!({
        "schema_version": "agent_bridge.cloudflare_kitesurf_snapshot.v0",
        "provider": "cloudflare-browser-run",
        "engine": "kitesurf",
        "read_only": true,
        "stateless": true,
        "source_url": snapshot.source_url,
        "title": snapshot.title,
        "http_status": snapshot.http_status,
        "browser_ms_used": snapshot.browser_ms_used,
        "viewport": {
            "width": request.viewport_width,
            "height": request.viewport_height
        },
        "wait_until": request.wait_until,
        "screenshot": {
            "mime_type": "image/png",
            "bytes": screenshot.len(),
            "sha256": format!("{:x}", Sha256::digest(&screenshot)),
            "included_inline": include_image
        },
        "markdown": markdown,
        "markdown_chars": markdown_chars,
        "markdown_truncated": markdown_truncated,
        "accessibility_tree": accessibility_tree,
        "accessibility_tree_chars": accessibility_chars,
        "accessibility_tree_truncated": accessibility_truncated,
        "limitations": [
            "no cookies, credentials, custom headers, or injected scripts",
            "Kitesurf beta is not pixel-identical to Chromium",
            "no durable browser session is created"
        ]
    });
    if include_image {
        let metadata_text =
            serde_json::to_string_pretty(&metadata).unwrap_or_else(|_| metadata.to_string());
        Ok(ToolResult {
            content: vec![
                ContentBlock::image(snapshot.screenshot_base64, "image/png"),
                ContentBlock::text(metadata_text),
            ],
            structured_content: Some(metadata),
            is_error: false,
            backend_id: None,
        })
    } else {
        Ok(ToolResult::structured_json(&metadata))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn requires_per_call_opt_in_before_network() {
        let tool = CloudflareKitesurfSnapshotTool::new(Hub::builder().build());
        let result = tool
            .execute(
                json!({"url": "https://example.com", "per_call_opt_in": false}),
                &ToolContext::default(),
            )
            .await
            .expect("tool result");
        assert!(result.is_error);
        let ContentBlock::Text { text } = &result.content[0] else {
            panic!("expected text error")
        };
        assert!(text.contains("per_call_opt_in=true"));
    }

    #[test]
    fn description_stays_within_client_listing_budget() {
        let tool = CloudflareKitesurfSnapshotTool::new(Hub::builder().build());
        assert!(tool.schema().description.chars().count() <= 256);
    }

    #[test]
    fn fixture_result_is_bounded_and_digest_backed() {
        let snapshot = crate::cloudflare_api::KitesurfSnapshot {
            source_url: "https://example.com/".into(),
            screenshot_base64: general_purpose::STANDARD.encode(b"png"),
            markdown: "hello".into(),
            accessibility_tree: json!({"role": "RootWebArea"}),
            title: Some("Example".into()),
            http_status: Some(200),
            browser_ms_used: Some(42),
        };
        let request = crate::cloudflare_api::KitesurfSnapshotRequest {
            url: "https://example.com/".into(),
            viewport_width: 1280,
            viewport_height: 720,
            wait_until: "domcontentloaded".into(),
            timeout_ms: 15_000,
        };
        let result = result_from_snapshot(snapshot, request, false).expect("result");
        assert!(!result.is_error);
        let structured = result.structured_content.expect("structured metadata");
        assert_eq!(structured["screenshot"]["bytes"], 3);
        assert_eq!(structured["screenshot"]["included_inline"], false);
        assert_eq!(structured["markdown"], "hello");
    }
}
