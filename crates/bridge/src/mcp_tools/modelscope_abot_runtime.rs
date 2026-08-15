use super::*;
use ab_browser::BrowserBackend;
use std::{
    fs,
    io::Write,
    os::unix::fs::{OpenOptionsExt, PermissionsExt},
    path::Path,
    sync::OnceLock,
};

const PROVIDER_ID: &str = "modelscope.studio.amap_cvlab.abot-world-0";
const BASE_URL: &str = "https://amap-cvlab-abot-world-0.ms.show";
const ENABLE_ENV: &str = "AB_MODELSCOPE_ABOT_RUNTIME_ENABLE";
const MIN_OBSERVE_MS: u64 = 5_000;
const MAX_OBSERVE_MS: u64 = 60_000;
const DEFAULT_OBSERVE_MS: u64 = 30_000;
const MAX_PROMPT_CHARS: usize = 4_000;
const MAX_REQUEST_ID_CHARS: usize = 128;
const TASK_SCHEMA: &str = "agent_bridge.modelscope_abot_task.v0";
const STUDIO_PROMPT_SELECTOR: &str = "textarea";
const STUDIO_READY_TIMEOUT_MS: u64 = 45_000;
const STUDIO_START_TIMEOUT_MS: u64 = 20_000;
const MAX_PROVIDER_TASK_SCAN: usize = 256;
const PROVIDER_COOLDOWN_STEPS_MS: &[u64] = &[5 * 60_000, 15 * 60_000, 30 * 60_000, 60 * 60_000];

static SESSION_LOCK: OnceLock<tokio::sync::Mutex<()>> = OnceLock::new();
static TASK_LOCK: OnceLock<tokio::sync::Mutex<()>> = OnceLock::new();
static PROCESS_INSTANCE_ID: OnceLock<String> = OnceLock::new();

#[derive(Debug, Clone)]
struct RunRequest {
    prompt: String,
    prompt_sha256: String,
    observe_ms: u64,
}

#[derive(Debug, Clone)]
struct TaskRequest {
    request_id: String,
    task_id: String,
    request_digest: String,
}

impl TaskRequest {
    fn parse(args: &Value, request: &RunRequest) -> std::result::Result<Option<Self>, String> {
        let Some(request_id) = args
            .get("request_id")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
        else {
            return Ok(None);
        };
        if request_id.chars().count() > MAX_REQUEST_ID_CHARS {
            return Err(format!(
                "request_id exceeds {MAX_REQUEST_ID_CHARS} characters"
            ));
        }
        let task_hash = format!(
            "{:x}",
            Sha256::digest(format!("{PROVIDER_ID}\0{request_id}").as_bytes())
        );
        let task_id = format!("abot-task-{}", &task_hash[..24]);
        let intent_id = args
            .get("embodiment_intent_id")
            .and_then(Value::as_str)
            .map(str::trim)
            .unwrap_or_default();
        let request_digest = format!(
            "{:x}",
            Sha256::digest(
                format!(
                    "{TASK_SCHEMA}\0{PROVIDER_ID}\0{request_id}\0{}\0{}\0{intent_id}",
                    request.prompt_sha256, request.observe_ms,
                )
                .as_bytes()
            )
        );
        Ok(Some(Self {
            request_id: request_id.to_string(),
            task_id,
            request_digest,
        }))
    }
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

fn task_dir() -> PathBuf {
    cache_dir().join("tasks")
}

fn task_path(task_id: &str) -> PathBuf {
    task_dir().join(format!("{task_id}.json"))
}

fn now_unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

fn process_instance_id() -> &'static str {
    PROCESS_INSTANCE_ID.get_or_init(|| format!("mcp-{}-{}", std::process::id(), now_unix_ms()))
}

fn atomic_write_json(path: &Path, value: &Value) -> std::result::Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| format!("task path has no parent: {}", path.display()))?;
    fs::create_dir_all(parent)
        .map_err(|error| format!("create task directory {}: {error}", parent.display()))?;
    fs::set_permissions(parent, fs::Permissions::from_mode(0o700))
        .map_err(|error| format!("secure task directory {}: {error}", parent.display()))?;
    let staged = path.with_extension(format!("json.tmp-{}-{}", std::process::id(), now_unix_ms()));
    let bytes = serde_json::to_vec_pretty(value)
        .map_err(|error| format!("serialize task record: {error}"))?;
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&staged)
        .map_err(|error| format!("create staged task record {}: {error}", staged.display()))?;
    file.write_all(&bytes)
        .map_err(|error| format!("stage task record {}: {error}", staged.display()))?;
    file.sync_all()
        .map_err(|error| format!("sync task record {}: {error}", staged.display()))?;
    fs::rename(&staged, path)
        .map_err(|error| format!("commit task record {}: {error}", path.display()))?;
    fs::File::open(parent)
        .and_then(|directory| directory.sync_all())
        .map_err(|error| format!("sync task directory {}: {error}", parent.display()))
}

fn read_task(path: &Path) -> std::result::Result<Option<Value>, String> {
    let bytes = match fs::read(path) {
        Ok(bytes) => bytes,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(format!("read task record {}: {error}", path.display())),
    };
    serde_json::from_slice(&bytes)
        .map(Some)
        .map_err(|error| format!("parse task record {}: {error}", path.display()))
}

#[derive(Default)]
struct ProviderTaskScan {
    records: Vec<Value>,
    invalid_records: usize,
    omitted_records: usize,
}

fn valid_provider_health_record(record: &Value) -> bool {
    record.get("schema").and_then(Value::as_str) == Some(TASK_SCHEMA)
        && record.get("provider_id").and_then(Value::as_str) == Some(PROVIDER_ID)
        && record
            .get("task_id")
            .and_then(Value::as_str)
            .is_some_and(|task_id| task_id.starts_with("abot-task-"))
        && record
            .get("updated_at_unix_ms")
            .and_then(Value::as_u64)
            .is_some_and(|timestamp| timestamp > 0)
        && matches!(
            record.get("status").and_then(Value::as_str),
            Some("running" | "completed" | "failed")
        )
}

fn read_provider_tasks() -> std::result::Result<ProviderTaskScan, String> {
    let entries = match fs::read_dir(task_dir()) {
        Ok(entries) => entries,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(ProviderTaskScan::default())
        }
        Err(error) => return Err(format!("read provider task directory: {error}")),
    };
    let mut paths = Vec::new();
    for entry in entries {
        let entry = entry.map_err(|error| format!("read provider task entry: {error}"))?;
        let path = entry.path();
        if path.extension().and_then(|value| value.to_str()) != Some("json") {
            continue;
        }
        let metadata = match fs::symlink_metadata(&path) {
            Ok(metadata) if metadata.file_type().is_file() => metadata,
            _ => continue,
        };
        paths.push((metadata.modified().unwrap_or(UNIX_EPOCH), path));
    }
    paths.sort_by(|left, right| right.0.cmp(&left.0));
    let omitted_records = paths.len().saturating_sub(MAX_PROVIDER_TASK_SCAN);
    paths.truncate(MAX_PROVIDER_TASK_SCAN);

    let mut scan = ProviderTaskScan {
        omitted_records,
        ..ProviderTaskScan::default()
    };
    for (_, path) in paths {
        match read_task(&path) {
            Ok(Some(record)) if valid_provider_health_record(&record) => scan.records.push(record),
            _ => scan.invalid_records += 1,
        }
    }
    Ok(scan)
}

fn task_updated_at(record: &Value) -> u64 {
    record
        .get("updated_at_unix_ms")
        .and_then(Value::as_u64)
        .unwrap_or_default()
}

fn is_provider_failure(record: &Value) -> bool {
    let provider_failure = record.get("status").and_then(Value::as_str) == Some("failed")
        && matches!(
            record.get("failure_class").and_then(Value::as_str),
            Some("provider_timeout" | "provider_lifecycle")
        );
    provider_failure || is_interrupted_running(record)
}

fn is_interrupted_running(record: &Value) -> bool {
    record.get("status").and_then(Value::as_str) == Some("running")
        && record.get("process_instance_id").and_then(Value::as_str) != Some(process_instance_id())
}

fn cooldown_duration_ms(failure_count: usize) -> u64 {
    if failure_count == 0 {
        return 0;
    }
    PROVIDER_COOLDOWN_STEPS_MS[failure_count
        .saturating_sub(1)
        .min(PROVIDER_COOLDOWN_STEPS_MS.len() - 1)]
}

fn provider_recovery_state(records: &[Value], now_ms: u64) -> Value {
    let mut ordered = records.iter().collect::<Vec<_>>();
    ordered.sort_by_key(|record| std::cmp::Reverse(task_updated_at(record)));
    let last_success_at = ordered
        .iter()
        .find(|record| record.get("status").and_then(Value::as_str) == Some("completed"))
        .map(|record| task_updated_at(record));
    let provider_failures = ordered
        .iter()
        .copied()
        .filter(|record| {
            is_provider_failure(record)
                && last_success_at
                    .map(|success_at| task_updated_at(record) > success_at)
                    .unwrap_or(true)
        })
        .collect::<Vec<_>>();
    let failure_count = provider_failures.len();
    let latest_failure = provider_failures.first().copied();
    let cooldown_ms = cooldown_duration_ms(failure_count);
    let retry_not_before_unix_ms = latest_failure
        .map(task_updated_at)
        .unwrap_or_default()
        .saturating_add(cooldown_ms);
    let cooldown_active = failure_count > 0 && now_ms < retry_not_before_unix_ms;
    let remaining_ms = if cooldown_active {
        retry_not_before_unix_ms.saturating_sub(now_ms)
    } else {
        0
    };
    let latest_terminal_task = ordered
        .iter()
        .find(|record| {
            matches!(
                record.get("status").and_then(Value::as_str),
                Some("completed" | "failed")
            ) || is_interrupted_running(record)
        })
        .map(|record| {
            let interrupted = is_interrupted_running(record);
            json!({
                "task_id": record.get("task_id").and_then(Value::as_str),
                "status": if interrupted { Some("interrupted") } else { record.get("status").and_then(Value::as_str) },
                "failure_class": if interrupted { Some("interrupted_after_restart") } else { record.get("failure_class").and_then(Value::as_str) },
                "updated_at_unix_ms": task_updated_at(record),
            })
        });

    json!({
        "consecutive_provider_failures": failure_count,
        "last_success_at_unix_ms": last_success_at,
        "latest_terminal_task": latest_terminal_task,
        "cooldown": {
            "active": cooldown_active,
            "duration_ms": cooldown_ms,
            "remaining_ms": remaining_ms,
            "retry_not_before_unix_ms": if failure_count > 0 { Some(retry_not_before_unix_ms) } else { None },
            "policy_ms": PROVIDER_COOLDOWN_STEPS_MS,
            "reason": if cooldown_active { Some("recent_provider_failure") } else { None },
        },
    })
}

fn provider_cooldown_error(recovery: &Value) -> Option<String> {
    if recovery["cooldown"]["active"].as_bool() != Some(true) {
        return None;
    }
    let retry_at = recovery["cooldown"]["retry_not_before_unix_ms"]
        .as_u64()
        .unwrap_or_default();
    let remaining = recovery["cooldown"]["remaining_ms"]
        .as_u64()
        .unwrap_or_default();
    Some(format!(
        "provider_cooldown: ModelScope ABot recently failed; retry after unix_ms={retry_at} (remaining_ms={remaining}); no external execution was started"
    ))
}

fn running_task_record(task: &TaskRequest, request: &RunRequest, lease_id: &LeaseId) -> Value {
    let now = now_unix_ms();
    json!({
        "schema": TASK_SCHEMA,
        "task_id": task.task_id,
        "request_id": task.request_id,
        "request_digest": task.request_digest,
        "provider_id": PROVIDER_ID,
        "status": "running",
        "failure_class": Value::Null,
        "error": Value::Null,
        "created_at_unix_ms": now,
        "updated_at_unix_ms": now,
        "process_instance_id": process_instance_id(),
        "process_id": std::process::id(),
        "prompt_sha256": request.prompt_sha256,
        "observe_ms": request.observe_ms,
        "embodiment_lease_id": lease_id,
        "receipt": Value::Null,
        "retry_policy": "new_request_id_required_after_failure_or_interruption",
        "persistent_runtime_admitted": false,
    })
}

fn classify_failure(error: &str) -> &'static str {
    if error.contains("positive FPS") {
        "provider_timeout"
    } else if error.contains("stop action") || error.contains("lifecycle did not close") {
        "provider_lifecycle"
    } else if error.contains("receipt")
        || error.contains("screenshot")
        || error.contains("artifact")
    {
        "artifact_io"
    } else if error.contains("already active") {
        "concurrency_busy"
    } else {
        "browser_backend"
    }
}

fn completed_task_record(mut record: Value, receipt: Value) -> Value {
    record["status"] = json!("completed");
    record["updated_at_unix_ms"] = json!(now_unix_ms());
    record["receipt"] = receipt;
    record
}

fn failed_task_record(mut record: Value, error: &str) -> Value {
    record["status"] = json!("failed");
    record["failure_class"] = json!(classify_failure(error));
    record["error"] = json!(error);
    record["updated_at_unix_ms"] = json!(now_unix_ms());
    record
}

fn inspect_existing_task(
    task: &TaskRequest,
    record: &Value,
) -> std::result::Result<Option<Value>, String> {
    if record.get("request_digest").and_then(Value::as_str) != Some(task.request_digest.as_str()) {
        return Err(format!(
            "idempotency_conflict: request_id '{}' is already bound to a different request digest",
            task.request_id
        ));
    }
    match record.get("status").and_then(Value::as_str) {
        Some("completed") => {
            let mut receipt = record
                .get("receipt")
                .cloned()
                .filter(Value::is_object)
                .ok_or_else(|| "completed task has no receipt".to_string())?;
            receipt["task_protocol"] = json!({
                "schema": TASK_SCHEMA,
                "task_id": task.task_id,
                "request_id": task.request_id,
                "request_digest": task.request_digest,
                "idempotent_replay": true,
                "external_execution_repeated": false,
            });
            Ok(Some(receipt))
        }
        Some("running") => {
            let same_process = record.get("process_instance_id").and_then(Value::as_str)
                == Some(process_instance_id());
            Err(if same_process {
                format!("task_in_progress: {}", task.task_id)
            } else {
                format!(
                    "task_interrupted_after_restart: {}; use a new request_id to retry",
                    task.task_id
                )
            })
        }
        Some("failed") => Err(format!(
            "task_previously_failed: {}; use a new request_id to retry",
            task.task_id
        )),
        Some(status) => Err(format!("unknown task status '{status}'")),
        None => Err("task record has no status".into()),
    }
}

fn task_status_projection(mut record: Value, include_receipt: bool) -> Value {
    let persisted_status = record
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("unknown")
        .to_string();
    if persisted_status == "running"
        && record.get("process_instance_id").and_then(Value::as_str) != Some(process_instance_id())
    {
        record["persisted_status"] = json!("running");
        record["status"] = json!("interrupted");
        record["failure_class"] = json!("interrupted_after_restart");
        record["requires_new_request_id"] = json!(true);
    }
    if !include_receipt {
        record
            .as_object_mut()
            .map(|object| object.remove("receipt"));
    }
    record["read_only"] = json!(true);
    record["status_projection_mutated_record"] = json!(false);
    record
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

async fn wait_for_text_selector(
    browser: &dyn BrowserBackend,
    page: &PageId,
    text: &str,
    timeout_ms: u64,
) -> std::result::Result<String, String> {
    let deadline = Instant::now() + Duration::from_millis(timeout_ms);
    loop {
        match selector_for_text(browser, page, text).await {
            Ok(selector) => return Ok(selector),
            Err(_) if Instant::now() < deadline => {
                browser
                    .wait_for(page, None, None, 500)
                    .await
                    .map_err(|error| format!("wait for button '{text}': {error}"))?;
            }
            Err(_) => {
                return Err(format!(
                    "button '{text}' did not become ready within {timeout_ms}ms"
                ))
            }
        }
    }
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
        let ready = browser
            .wait_for(
                &page,
                Some(STUDIO_PROMPT_SELECTOR),
                None,
                STUDIO_READY_TIMEOUT_MS,
            )
            .await
            .map_err(|error| format!("wait Studio load: {error}"))?;
        if ready.matched != "selector" {
            return Err(format!(
                "Studio prompt did not become ready within {STUDIO_READY_TIMEOUT_MS}ms"
            ));
        }
        browser
            .fill_form(&page, STUDIO_PROMPT_SELECTOR, &request.prompt)
            .await
            .map_err(|error| format!("fill prompt: {error}"))?;
        let start_selector = wait_for_text_selector(
            browser.as_ref(),
            &page,
            "唤醒你的世界",
            STUDIO_START_TIMEOUT_MS,
        )
        .await?;
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
                    "embodiment_intent_id": {"type": "string", "minLength": 1, "maxLength": 128},
                    "request_id": {"type": "string", "minLength": 1, "maxLength": MAX_REQUEST_ID_CHARS, "description": "Optional stable idempotency key. Same id plus same request replays the completed receipt without external execution; failed or interrupted tasks require a new id."}
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
        let task = match TaskRequest::parse(&args, &request) {
            Ok(task) => task,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let browser = match self.hub.browser.clone() {
            Some(browser) => browser,
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        if let Some(task) = task.as_ref() {
            let _task_guard = TASK_LOCK
                .get_or_init(|| tokio::sync::Mutex::new(()))
                .lock()
                .await;
            match read_task(&task_path(&task.task_id)) {
                Ok(Some(record)) => match inspect_existing_task(task, &record) {
                    Ok(Some(receipt)) => return Ok(ToolResult::structured_json(&receipt)),
                    Ok(None) => {}
                    Err(error) => return Ok(ToolResult::error(error)),
                },
                Ok(None) => {}
                Err(error) => return Ok(ToolResult::error(error)),
            }
        }
        let provider_tasks = match read_provider_tasks() {
            Ok(scan) => scan,
            Err(error) => {
                return Ok(ToolResult::error(format!(
                    "provider recovery preflight unavailable: {error}"
                )))
            }
        };
        if provider_tasks.invalid_records > 0 {
            return Ok(ToolResult::error(format!(
                "provider recovery preflight unavailable: {} invalid task record(s); no external execution was started",
                provider_tasks.invalid_records
            )));
        }
        let recovery = provider_recovery_state(&provider_tasks.records, now_unix_ms());
        if let Some(error) = provider_cooldown_error(&recovery) {
            return Ok(ToolResult::error(error));
        }
        let lock = SESSION_LOCK.get_or_init(|| tokio::sync::Mutex::new(()));
        let _guard = match lock.try_lock() {
            Ok(guard) => guard,
            Err(_) => {
                return Ok(ToolResult::error(
                    "a ModelScope ABot session is already active",
                ))
            }
        };
        let mut task_record = None;
        if let Some(task) = task.as_ref() {
            let _task_guard = TASK_LOCK
                .get_or_init(|| tokio::sync::Mutex::new(()))
                .lock()
                .await;
            let path = task_path(&task.task_id);
            match read_task(&path) {
                Ok(Some(record)) => match inspect_existing_task(task, &record) {
                    Ok(Some(receipt)) => return Ok(ToolResult::structured_json(&receipt)),
                    Ok(None) => {}
                    Err(error) => return Ok(ToolResult::error(error)),
                },
                Ok(None) => {}
                Err(error) => return Ok(ToolResult::error(error)),
            }
            let record = running_task_record(task, &request, &lease_id);
            if let Err(error) = atomic_write_json(&path, &record) {
                return Ok(ToolResult::error(error));
            }
            task_record = Some(record);
        }
        let intent_id = args
            .get("embodiment_intent_id")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty());
        match run_once(browser, request).await {
            Ok(mut receipt) => {
                receipt["embodiment_lease_id"] = json!(lease_id.to_string());
                if let (Some(task), Some(record)) = (task.as_ref(), task_record.take()) {
                    receipt["task_protocol"] = json!({
                        "schema": TASK_SCHEMA,
                        "task_id": task.task_id,
                        "request_id": task.request_id,
                        "request_digest": task.request_digest,
                        "idempotent_replay": false,
                        "external_execution_repeated": false,
                    });
                    let completed = completed_task_record(record, receipt.clone());
                    if let Err(error) = atomic_write_json(&task_path(&task.task_id), &completed) {
                        return Ok(ToolResult::error(format!(
                            "execution completed but durable task receipt failed: {error}; do not retry with the same request_id"
                        )));
                    }
                }
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
                if let (Some(task), Some(record)) = (task.as_ref(), task_record.take()) {
                    let failed = failed_task_record(record, &error);
                    if let Err(persist_error) =
                        atomic_write_json(&task_path(&task.task_id), &failed)
                    {
                        return Ok(ToolResult::error(format!(
                            "{error}; durable task failure write also failed: {persist_error}; do not retry with the same request_id"
                        )));
                    }
                }
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

pub struct ModelScopeAbotProviderStatusTool {
    hub: Hub,
}

impl ModelScopeAbotProviderStatusTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for ModelScopeAbotProviderStatusTool {
    fn name(&self) -> &'static str {
        "modelscope_abot_provider_status"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Project local ModelScope ABot recovery readiness from durable task records. Read-only: performs no network probe, browser action, retry, lease acquisition, or runtime enablement.".into(),
            input_schema: json!({"type": "object", "properties": {}}),
        }
    }

    async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let scan = match read_provider_tasks() {
            Ok(scan) => scan,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let recovery = provider_recovery_state(&scan.records, now_unix_ms());
        let runtime_opted_in = runtime_enabled();
        let browser_configured = self.hub.browser.is_some();
        let browser_capability_allowed = self.hub.security.check(Cap::Browser).is_ok();
        let cooldown_active = recovery["cooldown"]["active"].as_bool() == Some(true);
        let mut blockers = Vec::new();
        if !runtime_opted_in {
            blockers.push("runtime_opt_in_missing");
        }
        if !browser_configured {
            blockers.push("browser_backend_missing");
        }
        if !browser_capability_allowed {
            blockers.push("browser_capability_denied");
        }
        if cooldown_active {
            blockers.push("provider_cooldown_active");
        }
        if scan.invalid_records > 0 {
            blockers.push("task_history_invalid");
        }
        Ok(ToolResult::structured_json(&json!({
            "schema": "agent_bridge.modelscope_abot_provider_status.v0",
            "provider_id": PROVIDER_ID,
            "read_only": true,
            "network_probe_performed": false,
            "external_execution_started": false,
            "persistent_runtime_admitted": false,
            "task_scan": {
                "records_considered": scan.records.len(),
                "invalid_records": scan.invalid_records,
                "omitted_records": scan.omitted_records,
                "limit": MAX_PROVIDER_TASK_SCAN,
            },
            "recovery": recovery,
            "runtime": {
                "opted_in": runtime_opted_in,
                "browser_configured": browser_configured,
                "browser_capability_allowed": browser_capability_allowed,
            },
            "execution_preflight": {
                "eligible": blockers.is_empty(),
                "blockers": blockers,
                "owner_confirmation_and_body_lease_still_required_per_call": true,
            },
        })))
    }
}

pub struct ModelScopeAbotTaskStatusTool;

#[async_trait]
impl McpTool for ModelScopeAbotTaskStatusTool {
    fn name(&self) -> &'static str {
        "modelscope_abot_task_status"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read one durable ModelScope ABot task record. A running record from an earlier MCP process is projected as interrupted and is never resumed automatically.".into(),
            input_schema: json!({
                "type": "object",
                "required": ["task_id"],
                "properties": {
                    "task_id": {"type": "string", "pattern": "^abot-task-[0-9a-f]{24}$"},
                    "include_receipt": {"type": "boolean", "default": true}
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let Some(task_id) = args.get("task_id").and_then(Value::as_str) else {
            return Ok(ToolResult::error("missing 'task_id'"));
        };
        let valid = task_id.len() == "abot-task-".len() + 24
            && task_id.starts_with("abot-task-")
            && task_id["abot-task-".len()..]
                .chars()
                .all(|character| character.is_ascii_hexdigit() && !character.is_ascii_uppercase());
        if !valid {
            return Ok(ToolResult::error(
                "task_id must match ^abot-task-[0-9a-f]{24}$",
            ));
        }
        let record = match read_task(&task_path(task_id)) {
            Ok(Some(record)) => record,
            Ok(None) => return Ok(ToolResult::error(format!("task not found: {task_id}"))),
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let include_receipt = args
            .get("include_receipt")
            .and_then(Value::as_bool)
            .unwrap_or(true);
        Ok(ToolResult::structured_json(&task_status_projection(
            record,
            include_receipt,
        )))
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
    fn task_request_is_stable_and_digest_bound() {
        let mut args = valid_args();
        args["request_id"] = json!("gate8a-request-001");
        let request = RunRequest::parse(&args).expect("run request");
        let first = TaskRequest::parse(&args, &request)
            .expect("task request")
            .expect("present task");
        let second = TaskRequest::parse(&args, &request)
            .expect("task request")
            .expect("present task");
        assert_eq!(first.task_id, second.task_id);
        assert_eq!(first.request_digest, second.request_digest);
        assert!(first.task_id.starts_with("abot-task-"));

        args["observe_ms"] = json!(20_000);
        let changed = RunRequest::parse(&args).expect("changed run request");
        let changed = TaskRequest::parse(&args, &changed)
            .expect("changed task request")
            .expect("present task");
        assert_eq!(first.task_id, changed.task_id);
        assert_ne!(first.request_digest, changed.request_digest);

        args["observe_ms"] = json!(10_000);
        args["embodiment_intent_id"] = json!("different-intent");
        let changed_intent = RunRequest::parse(&args).expect("changed intent run request");
        let changed_intent = TaskRequest::parse(&args, &changed_intent)
            .expect("changed intent task request")
            .expect("present task");
        assert_eq!(first.task_id, changed_intent.task_id);
        assert_ne!(first.request_digest, changed_intent.request_digest);
    }

    #[test]
    fn task_record_replays_completed_and_projects_restart_interruption() {
        let mut args = valid_args();
        args["request_id"] = json!("gate8a-request-002");
        let request = RunRequest::parse(&args).expect("run request");
        let task = TaskRequest::parse(&args, &request)
            .expect("task request")
            .expect("present task");
        let lease = LeaseId::from_raw("lease-test");
        let running = running_task_record(&task, &request, &lease);
        let completed = completed_task_record(
            running.clone(),
            json!({"schema": "agent_bridge.modelscope_abot_run_once_receipt.v0"}),
        );
        let replay = inspect_existing_task(&task, &completed)
            .expect("completed inspection")
            .expect("replay receipt");
        assert_eq!(replay["task_protocol"]["idempotent_replay"], true);
        assert_eq!(
            replay["task_protocol"]["external_execution_repeated"],
            false
        );

        let mut prior_process = running;
        prior_process["process_instance_id"] = json!("mcp-prior-process");
        let projection = task_status_projection(prior_process, false);
        assert_eq!(projection["status"], "interrupted");
        assert_eq!(projection["failure_class"], "interrupted_after_restart");
        assert!(projection.get("receipt").is_none());
        assert_eq!(projection["status_projection_mutated_record"], false);
    }

    #[test]
    fn task_conflict_and_failure_classes_are_stable() {
        let mut args = valid_args();
        args["request_id"] = json!("gate8a-request-003");
        let request = RunRequest::parse(&args).expect("run request");
        let task = TaskRequest::parse(&args, &request)
            .expect("task request")
            .expect("present task");
        let mut record = running_task_record(&task, &request, &LeaseId::from_raw("lease-test"));
        record["request_digest"] = json!("different");
        assert!(inspect_existing_task(&task, &record)
            .unwrap_err()
            .contains("idempotency_conflict"));
        assert_eq!(
            classify_failure("Studio stream did not report positive FPS before deadline"),
            "provider_timeout"
        );
        assert_eq!(
            classify_failure("Studio lifecycle did not close"),
            "provider_lifecycle"
        );
    }

    fn terminal_record(
        task_id: &str,
        status: &str,
        failure_class: Option<&str>,
        updated_at_unix_ms: u64,
    ) -> Value {
        json!({
            "schema": TASK_SCHEMA,
            "provider_id": PROVIDER_ID,
            "task_id": task_id,
            "status": status,
            "failure_class": failure_class,
            "updated_at_unix_ms": updated_at_unix_ms,
        })
    }

    #[test]
    fn provider_recovery_applies_bounded_cooldown_without_network_work() {
        let records = vec![
            terminal_record("newer", "failed", Some("provider_timeout"), 2_000),
            terminal_record("older", "failed", Some("provider_lifecycle"), 1_000),
            terminal_record("local", "failed", Some("browser_backend"), 3_000),
        ];
        let recovery = provider_recovery_state(&records, 2_500);
        assert_eq!(recovery["consecutive_provider_failures"], 2);
        assert_eq!(recovery["cooldown"]["active"], true);
        assert_eq!(recovery["cooldown"]["duration_ms"], 15 * 60_000);
        assert_eq!(
            recovery["cooldown"]["retry_not_before_unix_ms"],
            2_000 + 15 * 60_000
        );
        let error = provider_cooldown_error(&recovery).expect("active cooldown");
        assert!(error.contains("no external execution was started"));

        let elapsed = provider_recovery_state(&records, 2_000 + 15 * 60_000);
        assert_eq!(elapsed["cooldown"]["active"], false);
        assert!(provider_cooldown_error(&elapsed).is_none());
    }

    #[test]
    fn provider_success_resets_failure_streak() {
        let records = vec![
            terminal_record("failed", "failed", Some("provider_timeout"), 1_000),
            terminal_record("success", "completed", None, 2_000),
        ];
        let recovery = provider_recovery_state(&records, 2_500);
        assert_eq!(recovery["consecutive_provider_failures"], 0);
        assert_eq!(recovery["last_success_at_unix_ms"], 2_000);
        assert_eq!(recovery["cooldown"]["active"], false);
        assert_eq!(
            recovery["cooldown"]["retry_not_before_unix_ms"],
            Value::Null
        );
    }

    #[test]
    fn provider_health_record_validation_rejects_incomplete_history() {
        let valid = terminal_record(
            "abot-task-0123456789abcdef01234567",
            "failed",
            Some("provider_timeout"),
            1_000,
        );
        assert!(valid_provider_health_record(&valid));

        let mut missing_time = valid.clone();
        missing_time
            .as_object_mut()
            .expect("record object")
            .remove("updated_at_unix_ms");
        assert!(!valid_provider_health_record(&missing_time));

        let mut unknown_status = valid;
        unknown_status["status"] = json!("queued");
        assert!(!valid_provider_health_record(&unknown_status));
    }

    #[test]
    fn interrupted_prior_process_enters_recovery_cooldown() {
        let mut running = terminal_record(
            "abot-task-0123456789abcdef01234567",
            "running",
            None,
            10_000,
        );
        running["process_instance_id"] = json!("mcp-prior-process");
        let recovery = provider_recovery_state(&[running], 10_500);
        assert_eq!(recovery["consecutive_provider_failures"], 1);
        assert_eq!(recovery["cooldown"]["active"], true);
        assert_eq!(recovery["latest_terminal_task"]["status"], "interrupted");
        assert_eq!(
            recovery["latest_terminal_task"]["failure_class"],
            "interrupted_after_restart"
        );
    }

    #[test]
    fn task_record_atomic_roundtrip_preserves_digest() {
        let directory = tempfile::tempdir().expect("tempdir");
        let path = directory.path().join("abot-task-test.json");
        let record = json!({
            "schema": TASK_SCHEMA,
            "task_id": "abot-task-0123456789abcdef01234567",
            "request_digest": "digest-test",
            "status": "running",
        });
        atomic_write_json(&path, &record).expect("atomic write");
        let readback = read_task(&path).expect("read task").expect("task present");
        assert_eq!(readback, record);
        assert_eq!(
            fs::metadata(&path)
                .expect("task metadata")
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
        assert_eq!(
            fs::metadata(directory.path())
                .expect("directory metadata")
                .permissions()
                .mode()
                & 0o777,
            0o700
        );
        assert!(directory
            .path()
            .read_dir()
            .expect("read directory")
            .all(|entry| !entry
                .expect("directory entry")
                .file_name()
                .to_string_lossy()
                .contains(".tmp-")));
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
        assert!(schema.input_schema["properties"]
            .get("request_id")
            .is_some());

        let status = ModelScopeAbotTaskStatusTool;
        assert_eq!(status.name(), "modelscope_abot_task_status");
        assert!(status.schema().description.contains("never resumed"));

        let provider = ModelScopeAbotProviderStatusTool::new(Hub::builder().build());
        assert_eq!(provider.name(), "modelscope_abot_provider_status");
        assert!(provider.schema().description.contains("Read-only"));
        assert!(provider.schema().description.contains("no network probe"));
    }
}
