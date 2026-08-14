use super::*;
use ab_browser::BrowserBackend;
use std::sync::OnceLock;

const PROVIDER_ID: &str = "modelscope.studio.amap_cvlab.abot-world-0";
const BASE_URL: &str = "https://amap-cvlab-abot-world-0.ms.show";
const ENABLE_ENV: &str = "AB_MODELSCOPE_ABOT_RUNTIME_ENABLE";
const MIN_OBSERVE_MS: u64 = 5_000;
const MAX_OBSERVE_MS: u64 = 60_000;
const DEFAULT_OBSERVE_MS: u64 = 30_000;
const MAX_PROMPT_CHARS: usize = 4_000;

static SESSION_LOCK: OnceLock<tokio::sync::Mutex<()>> = OnceLock::new();

#[derive(Debug, Clone)]
struct RunRequest {
    prompt: String,
    prompt_sha256: String,
    observe_ms: u64,
}

impl RunRequest {
    fn parse(args: &Value) -> std::result::Result<Self, String> {
        if args.get("owner_confirmed").and_then(Value::as_bool) != Some(true) {
            return Err("owner_confirmed=true is required for live ModelScope execution".into());
        }
        let prompt = args
            .get("prompt")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .ok_or_else(|| "missing non-empty 'prompt'".to_string())?
            .to_string();
        if prompt.chars().count() > MAX_PROMPT_CHARS {
            return Err(format!("prompt exceeds {MAX_PROMPT_CHARS} characters"));
        }
        let observe_ms = args
            .get("observe_ms")
            .and_then(Value::as_u64)
            .unwrap_or(DEFAULT_OBSERVE_MS);
        if !(MIN_OBSERVE_MS..=MAX_OBSERVE_MS).contains(&observe_ms) {
            return Err(format!(
                "observe_ms must be between {MIN_OBSERVE_MS} and {MAX_OBSERVE_MS}"
            ));
        }
        let prompt_sha256 = format!("{:x}", Sha256::digest(prompt.as_bytes()));
        Ok(Self {
            prompt,
            prompt_sha256,
            observe_ms,
        })
    }
}

fn runtime_enabled() -> bool {
    matches!(
        std::env::var(ENABLE_ENV).as_deref(),
        Ok("1" | "true" | "yes")
    )
}

fn first_selector(value: &Value) -> Option<String> {
    match value {
        Value::Object(map) => map
            .get("selector")
            .and_then(Value::as_str)
            .map(str::to_string)
            .or_else(|| map.values().find_map(first_selector)),
        Value::Array(values) => values.iter().find_map(first_selector),
        _ => None,
    }
}

fn strings_in(value: &Value, out: &mut Vec<String>) {
    match value {
        Value::String(text) => out.push(text.clone()),
        Value::Array(values) => values.iter().for_each(|value| strings_in(value, out)),
        Value::Object(map) => map.values().for_each(|value| strings_in(value, out)),
        _ => {}
    }
}

fn frame_values(value: &Value) -> Vec<Value> {
    value
        .get("frames")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default()
}

fn observed_fps(value: &Value) -> Option<f64> {
    let mut strings = Vec::new();
    strings_in(value, &mut strings);
    strings.into_iter().find_map(|text| {
        let marker = text.find("FPS")?;
        let prefix = &text[..marker];
        let token = prefix
            .split_whitespace()
            .last()?
            .trim_matches(|character: char| !character.is_ascii_digit() && character != '.');
        token.parse::<f64>().ok().filter(|value| *value > 0.0)
    })
}

fn cache_dir() -> PathBuf {
    std::env::var_os("XDG_CACHE_HOME")
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".cache")))
        .unwrap_or_else(|| PathBuf::from("."))
        .join("agent-bridge/modelscope-abot")
}

async fn selector_for_text(
    browser: &dyn BrowserBackend,
    page: &PageId,
    text: &str,
) -> std::result::Result<String, String> {
    let candidates = browser
        .find_by_text(page, text, Some("button"))
        .await
        .map_err(|error| format!("find button '{text}': {error}"))?;
    first_selector(&candidates).ok_or_else(|| format!("button '{text}' not found"))
}

async fn stop_session(browser: &dyn BrowserBackend, page: &PageId) -> bool {
    let Ok(selector) = selector_for_text(browser, page, "封存你的世界").await else {
        return false;
    };
    if browser.click(page, &selector).await.is_err() {
        return false;
    }
    let _ = browser.wait_for(page, None, None, 8_000).await;
    true
}

async fn run_once(
    browser: Arc<dyn BrowserBackend>,
    request: RunRequest,
) -> std::result::Result<Value, String> {
    let page = browser
        .navigate(BASE_URL)
        .await
        .map_err(|error| format!("navigate Studio: {error}"))?;
    let mut started = false;
    let run_result = async {
        browser
            .wait_for(&page, None, None, 12_000)
            .await
            .map_err(|error| format!("wait Studio load: {error}"))?;
        browser
            .fill_form(&page, "textarea", &request.prompt)
            .await
            .map_err(|error| format!("fill prompt: {error}"))?;
        let start_selector = selector_for_text(browser.as_ref(), &page, "唤醒你的世界").await?;
        browser
            .click(&page, &start_selector)
            .await
            .map_err(|error| format!("start Studio: {error}"))?;
        started = true;
        browser
            .wait_for(&page, None, None, 3_000)
            .await
            .map_err(|error| format!("wait GPU allocation: {error}"))?;

        let deadline = Instant::now() + Duration::from_millis(request.observe_ms);
        let mut max_fps = 0.0_f64;
        let mut observed_frame_count = 0_usize;
        while Instant::now() < deadline {
            let frames = browser
                .list_frames(&page)
                .await
                .map_err(|error| format!("list Studio frames: {error}"))?;
            let frame_values = frame_values(&frames);
            observed_frame_count = observed_frame_count.max(frame_values.len().saturating_sub(1));
            for frame in frame_values {
                let frame_id = frame.get("frame_id").and_then(Value::as_str);
                let parent_id = frame.get("parent_id").and_then(Value::as_str);
                if parent_id.is_none() {
                    continue;
                }
                let value = browser
                    .eval_in_frame(
                        &page,
                        frame_id,
                        None,
                        "document.body ? document.body.innerText : ''",
                    )
                    .await;
                if let Ok(value) = value {
                    if let Some(fps) = observed_fps(&value) {
                        max_fps = max_fps.max(fps);
                    }
                }
            }
            if max_fps > 0.0 {
                break;
            }
            let _ = browser.wait_for(&page, None, None, 1_000).await;
        }
        if max_fps <= 0.0 {
            return Err("Studio stream did not report positive FPS before deadline".into());
        }

        let screenshot = browser
            .screenshot(&page)
            .await
            .map_err(|error| format!("capture Studio screenshot: {error}"))?;
        let screenshot_sha256 = format!("{:x}", Sha256::digest(screenshot.as_ref()));
        let observed_at_unix_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64;
        let artifact_dir = cache_dir();
        std::fs::create_dir_all(&artifact_dir)
            .map_err(|error| format!("create receipt directory: {error}"))?;
        let run_id = format!("abot-live-{observed_at_unix_ms}");
        let screenshot_path = artifact_dir.join(format!("{run_id}.png"));
        std::fs::write(&screenshot_path, screenshot.as_ref())
            .map_err(|error| format!("write Studio screenshot: {error}"))?;

        if !stop_session(browser.as_ref(), &page).await {
            return Err("Studio stop action failed".into());
        }
        let frames_after_stop = browser
            .list_frames(&page)
            .await
            .map_err(|error| format!("verify Studio stop: {error}"))?;
        let iframe_count_after_stop = frame_values(&frames_after_stop)
            .iter()
            .filter(|frame| frame.get("parent_id").and_then(Value::as_str).is_some())
            .count();
        if iframe_count_after_stop != 0 {
            return Err(format!(
                "Studio lifecycle did not close: {iframe_count_after_stop} iframe(s) remain"
            ));
        }
        started = false;

        let receipt = json!({
            "schema": "agent_bridge.modelscope_abot_run_once_receipt.v0",
            "provider_id": PROVIDER_ID,
            "run_id": run_id,
            "observed_at_unix_ms": observed_at_unix_ms,
            "prompt_sha256": request.prompt_sha256,
            "authorization": {
                "owner_confirmed": true,
                "scope": "one_shot_browser_runtime",
                "persistent_runtime_authorized": false,
            },
            "observations": {
                "gpu_session_observed": observed_frame_count > 0,
                "stream_observed": true,
                "max_observed_fps": max_fps,
                "stop_observed": true,
                "post_stop_iframe_count": iframe_count_after_stop,
            },
            "artifact": {
                "path": screenshot_path,
                "sha256": screenshot_sha256,
                "bytes": screenshot.len(),
                "content_type": "image/png",
                "evidence_type": "presentation_screenshot",
            },
            "execution": {
                "network_request_sent": true,
                "studio_start_called": true,
                "execution_attempted": true,
                "execution_authorized": true,
                "one_shot_runtime_admitted": true,
                "persistent_runtime_admitted": false,
                "mcp_tool_registered": true,
            },
            "lifecycle_closed": true,
            "status": "completed",
        });
        let receipt_path = artifact_dir.join(format!("{run_id}.json"));
        let receipt_bytes = serde_json::to_vec_pretty(&receipt)
            .map_err(|error| format!("serialize Studio receipt: {error}"))?;
        std::fs::write(&receipt_path, receipt_bytes)
            .map_err(|error| format!("write Studio receipt: {error}"))?;
        let mut receipt = receipt;
        receipt["receipt_path"] = json!(receipt_path);
        Ok(receipt)
    }
    .await;

    let cleanup_stop_observed = if started {
        stop_session(browser.as_ref(), &page).await
    } else {
        true
    };
    let close_observed = browser.close(&page).await.is_ok();
    run_result.map_err(|error| {
        format!(
            "{error}; cleanup_stop_observed={cleanup_stop_observed}; close_observed={close_observed}"
        )
    })
}

pub struct ModelScopeAbotRunOnceTool {
    hub: Hub,
}

impl ModelScopeAbotRunOnceTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for ModelScopeAbotRunOnceTool {
    fn name(&self) -> &'static str {
        "modelscope_abot_run_once"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Run one bounded ABot-World Studio browser session, capture evidence, stop it, and return a receipt. Requires Browser capability, a body-write lease, owner confirmation, and AB_MODELSCOPE_ABOT_RUNTIME_ENABLE=1; never creates a persistent runtime.".into(),
            input_schema: json!({
                "type": "object",
                "required": ["prompt", "owner_confirmed", "embodiment_lease_id"],
                "properties": {
                    "prompt": {"type": "string", "minLength": 1, "maxLength": MAX_PROMPT_CHARS},
                    "observe_ms": {"type": "integer", "minimum": MIN_OBSERVE_MS, "maximum": MAX_OBSERVE_MS, "default": DEFAULT_OBSERVE_MS},
                    "owner_confirmed": {"type": "boolean", "const": true},
                    "embodiment_lease_id": {"type": "string", "minLength": 1, "maxLength": 128},
                    "embodiment_intent_id": {"type": "string", "minLength": 1, "maxLength": 128}
                }
            }),
        }
    }

    async fn execute(&self, args: Value, ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(error) = self.hub.security.check(Cap::Browser) {
            return Ok(ToolResult::error(error));
        }
        let lease_id = match require_body_write_lease(&self.hub, &args, ctx).await {
            Ok(lease_id) => lease_id,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        if !runtime_enabled() {
            return Ok(ToolResult::error(format!(
                "ModelScope ABot runtime is disabled; set {ENABLE_ENV}=1 before starting agent-bridge"
            )));
        }
        let request = match RunRequest::parse(&args) {
            Ok(request) => request,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let browser = match self.hub.browser.clone() {
            Some(browser) => browser,
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let lock = SESSION_LOCK.get_or_init(|| tokio::sync::Mutex::new(()));
        let _guard = match lock.try_lock() {
            Ok(guard) => guard,
            Err(_) => {
                return Ok(ToolResult::error(
                    "a ModelScope ABot session is already active",
                ))
            }
        };
        let intent_id = args
            .get("embodiment_intent_id")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty());
        match run_once(browser, request).await {
            Ok(mut receipt) => {
                receipt["embodiment_lease_id"] = json!(lease_id.to_string());
                record_embodiment_receipt(
                    &self.hub,
                    "modelscope_abot",
                    "run_once",
                    intent_id,
                    receipt
                        .get("run_id")
                        .and_then(Value::as_str)
                        .map(str::to_string),
                    true,
                    receipt.clone(),
                )
                .await;
                Ok(ToolResult::structured_json(&receipt))
            }
            Err(error) => {
                record_embodiment_receipt(
                    &self.hub,
                    "modelscope_abot",
                    "run_once",
                    intent_id,
                    None,
                    false,
                    json!({"error": error, "embodiment_lease_id": lease_id}),
                )
                .await;
                Ok(ToolResult::error(error))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_args() -> Value {
        json!({
            "prompt": "A sunlit sandstone temple",
            "observe_ms": 10_000,
            "owner_confirmed": true,
        })
    }

    #[test]
    fn request_is_prompt_hash_bound_and_bounded() {
        let request = RunRequest::parse(&valid_args()).expect("valid request");
        assert_eq!(request.observe_ms, 10_000);
        assert_eq!(request.prompt_sha256.len(), 64);
        assert!(!request.prompt_sha256.contains("sandstone"));
    }

    #[test]
    fn request_rejects_missing_authority_and_bad_timeout() {
        let mut args = valid_args();
        args["owner_confirmed"] = json!(false);
        assert!(RunRequest::parse(&args)
            .unwrap_err()
            .contains("owner_confirmed"));
        args["owner_confirmed"] = json!(true);
        args["observe_ms"] = json!(MAX_OBSERVE_MS + 1);
        assert!(RunRequest::parse(&args).unwrap_err().contains("observe_ms"));
    }

    #[test]
    fn selector_and_fps_parsers_accept_browser_payloads() {
        let candidates = json!([{"text": "start", "selector": "button:nth-of-type(1)"}]);
        assert_eq!(
            first_selector(&candidates).as_deref(),
            Some("button:nth-of-type(1)")
        );
        assert_eq!(
            observed_fps(&json!({"text": "GPU ready · 2.0 FPS"})),
            Some(2.0)
        );
        assert_eq!(
            frame_values(&json!({
                "count": 2,
                "frames": [{"kind": "main"}, {"kind": "oopif"}]
            }))
            .len(),
            2
        );
        assert!(frame_values(&json!([{"kind": "main"}])).is_empty());
    }

    #[test]
    fn tool_stays_niche_and_declares_persistence_boundary() {
        let tool = ModelScopeAbotRunOnceTool::new(Hub::builder().build());
        assert_eq!(tool.name(), "modelscope_abot_run_once");
        let schema = tool.schema();
        assert_eq!(
            schema.input_schema["properties"]["owner_confirmed"]["const"],
            true
        );
        assert!(schema
            .description
            .contains("never creates a persistent runtime"));
    }
}
