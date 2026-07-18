//! ACP stdio agent runtime (P1).
//!
//! Speaks Agent Client Protocol v1 JSON-RPC to a long-lived child process.
//! Structured `session/update` notifications are flattened into the existing
//! `AgentRuntime::read_interactive_output` text surface; P1 deliberately adds
//! no store schema. Permission requests are auto-approved (prefer allow-once),
//! matching Agent-Bridge's recoverable-work autonomy contract.

use ab_core::{Error, Result, SessionId};
use ab_store::{StateStore, StoredSession};
use async_trait::async_trait;
use dashmap::DashMap;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::process::Stdio;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};
use tokio::process::{ChildStdin, Command};
use tokio::sync::{oneshot, Mutex as AsyncMutex};
use tokio::time::{timeout, Duration};
use tracing::{info, warn};

use crate::{AgentCapabilities, AgentRuntime, AgentSession, SpawnConfig};

const REQUEST_TIMEOUT: Duration = Duration::from_secs(30);
const OUTPUT_CAP: usize = 2 * 1024 * 1024;

type Pending = Arc<DashMap<u64, oneshot::Sender<std::result::Result<Value, String>>>>;

/// Kills the isolated ACP process group if spawn initialization returns early
/// or the owning Tokio task is dropped before it reaps the leader.
struct ProcessGroupGuard {
    pid: u32,
    armed: bool,
}

impl ProcessGroupGuard {
    fn new(pid: u32) -> Self {
        Self { pid, armed: true }
    }

    fn disarm(&mut self) {
        self.armed = false;
    }
}

impl Drop for ProcessGroupGuard {
    fn drop(&mut self) {
        if self.armed {
            let _ = signal_process_group(self.pid, libc::SIGKILL);
        }
    }
}

fn signal_process_group(pid: u32, signal: libc::c_int) -> Result<()> {
    #[cfg(unix)]
    {
        if pid <= 1 || pid > i32::MAX as u32 {
            return Err(Error::Backend(format!(
                "refuse to signal invalid ACP process group {pid}"
            )));
        }
        let rc = unsafe { libc::kill(-(pid as libc::pid_t), signal) };
        if rc == 0 {
            return Ok(());
        }
        let error = std::io::Error::last_os_error();
        if error.raw_os_error() == Some(libc::ESRCH) {
            Ok(())
        } else {
            Err(Error::Backend(format!(
                "signal ACP process group {pid}: {error}"
            )))
        }
    }
    #[cfg(not(unix))]
    {
        let _ = (pid, signal);
        Err(Error::Backend(
            "ACP process-group signalling requires Unix".into(),
        ))
    }
}

struct LiveAcpSession {
    writer: Arc<AsyncMutex<ChildStdin>>,
    pending: Pending,
    next_id: AtomicU64,
    protocol_session_id: String,
    output: Arc<Mutex<String>>,
    pid: u32,
}

impl LiveAcpSession {
    async fn prompt(&self, text: String) -> Result<()> {
        request_with_timeout(
            &self.writer,
            &self.pending,
            &self.next_id,
            "session/prompt",
            json!({"sessionId":self.protocol_session_id,"prompt":[{"type":"text","text":text}]}),
            None,
        )
        .await
        .map(|_| ())
    }
}

#[derive(Clone)]
pub struct AcpRuntime {
    binary: String,
    args: Vec<String>,
    store: Option<Arc<dyn StateStore>>,
    sessions: Arc<DashMap<String, Arc<LiveAcpSession>>>,
}

impl Default for AcpRuntime {
    fn default() -> Self {
        Self {
            binary: "grok".into(),
            args: vec!["agent".into(), "stdio".into()],
            store: None,
            sessions: Arc::new(DashMap::new()),
        }
    }
}

impl AcpRuntime {
    pub fn new() -> Self {
        Self::default()
    }
    pub fn with_binary(binary: impl Into<String>) -> Self {
        Self {
            binary: binary.into(),
            ..Self::default()
        }
    }
    pub fn with_args(mut self, args: impl IntoIterator<Item = impl Into<String>>) -> Self {
        self.args = args.into_iter().map(Into::into).collect();
        self
    }
    pub fn with_store(mut self, store: Arc<dyn StateStore>) -> Self {
        self.store = Some(store);
        self
    }
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn append_output(output: &Mutex<String>, text: &str) {
    let mut out = output.lock().unwrap_or_else(|e| e.into_inner());
    out.push_str(text);
    if out.len() > OUTPUT_CAP {
        let mut cut = out.len() - OUTPUT_CAP;
        while cut < out.len() && !out.is_char_boundary(cut) {
            cut += 1;
        }
        out.drain(..cut);
    }
}

fn update_text(update: &Value) -> Option<String> {
    let kind = update
        .get("sessionUpdate")
        .and_then(Value::as_str)
        .unwrap_or("");
    match kind {
        "agent_message_chunk" => update
            .pointer("/content/text")
            .and_then(Value::as_str)
            .map(str::to_owned),
        "agent_thought_chunk" => update
            .pointer("/content/text")
            .and_then(Value::as_str)
            .map(|s| format!("[thought] {s}")),
        "tool_call" => {
            let title = update
                .get("title")
                .and_then(Value::as_str)
                .unwrap_or("tool");
            Some(format!("\n[tool] {title}\n"))
        }
        "tool_call_update" => {
            let status = update
                .get("status")
                .and_then(Value::as_str)
                .unwrap_or("updated");
            Some(format!("[tool:{status}]\n"))
        }
        _ => None,
    }
}

async fn write_json(
    writer: &Arc<AsyncMutex<ChildStdin>>,
    value: &Value,
) -> std::result::Result<(), String> {
    let mut line = serde_json::to_vec(value).map_err(|e| e.to_string())?;
    line.push(b'\n');
    let mut w = writer.lock().await;
    w.write_all(&line).await.map_err(|e| e.to_string())?;
    w.flush().await.map_err(|e| e.to_string())
}

async fn request(
    writer: &Arc<AsyncMutex<ChildStdin>>,
    pending: &Pending,
    next_id: &AtomicU64,
    method: &str,
    params: Value,
) -> Result<Value> {
    request_with_timeout(
        writer,
        pending,
        next_id,
        method,
        params,
        Some(REQUEST_TIMEOUT),
    )
    .await
}

async fn request_with_timeout(
    writer: &Arc<AsyncMutex<ChildStdin>>,
    pending: &Pending,
    next_id: &AtomicU64,
    method: &str,
    params: Value,
    request_timeout: Option<Duration>,
) -> Result<Value> {
    let id = next_id.fetch_add(1, Ordering::Relaxed);
    let (tx, rx) = oneshot::channel();
    pending.insert(id, tx);
    if let Err(e) = write_json(
        writer,
        &json!({"jsonrpc":"2.0","id":id,"method":method,"params":params}),
    )
    .await
    {
        pending.remove(&id);
        return Err(Error::Backend(format!("ACP {method} write: {e}")));
    }
    let received = if let Some(wait) = request_timeout {
        match timeout(wait, rx).await {
            Ok(received) => received,
            Err(_) => {
                pending.remove(&id);
                return Err(Error::Backend(format!("ACP {method}: timed out")));
            }
        }
    } else {
        rx.await
    };
    match received {
        Ok(Ok(v)) => Ok(v),
        Ok(Err(e)) => Err(Error::Backend(format!("ACP {method}: {e}"))),
        Err(_) => Err(Error::Backend(format!(
            "ACP {method}: response channel closed"
        ))),
    }
}

fn permission_response(params: &Value) -> Value {
    let selected = params
        .get("options")
        .and_then(Value::as_array)
        .and_then(|options| {
            options
                .iter()
                .find(|o| o.get("kind").and_then(Value::as_str) == Some("allow_once"))
                .or_else(|| {
                    options
                        .iter()
                        .find(|o| o.get("kind").and_then(Value::as_str) == Some("allow_always"))
                })
                .and_then(|o| o.get("optionId"))
                .cloned()
        });
    match selected {
        Some(option_id) => json!({"outcome":{"outcome":"selected","optionId":option_id}}),
        None => json!({"outcome":{"outcome":"cancelled"}}),
    }
}

async fn reader_loop(
    stdout: tokio::process::ChildStdout,
    writer: Arc<AsyncMutex<ChildStdin>>,
    pending: Pending,
    output: Arc<Mutex<String>>,
) {
    let mut lines = BufReader::new(stdout).lines();
    while let Ok(Some(line)) = lines.next_line().await {
        let Ok(msg) = serde_json::from_str::<Value>(&line) else {
            continue;
        };
        if let Some(id) = msg.get("id").and_then(Value::as_u64) {
            if msg.get("method").is_none() {
                if let Some((_, tx)) = pending.remove(&id) {
                    let result = if let Some(error) = msg.get("error") {
                        Err(error.to_string())
                    } else {
                        Ok(msg.get("result").cloned().unwrap_or(Value::Null))
                    };
                    let _ = tx.send(result);
                }
                continue;
            }
        }
        match msg.get("method").and_then(Value::as_str) {
            Some("session/update") => {
                if let Some(text) = msg.pointer("/params/update").and_then(update_text) {
                    append_output(&output, &text);
                }
            }
            Some("session/request_permission") => {
                if let Some(id) = msg.get("id").cloned() {
                    let result = permission_response(msg.get("params").unwrap_or(&Value::Null));
                    let approved = result.pointer("/outcome/outcome").and_then(Value::as_str)
                        == Some("selected");
                    if let Err(e) =
                        write_json(&writer, &json!({"jsonrpc":"2.0","id":id,"result":result})).await
                    {
                        warn!(error=%e, "ACP permission auto-approve response failed");
                    }
                    append_output(
                        &output,
                        if approved {
                            "[permission:auto-approved]\n"
                        } else {
                            "[permission:auto-cancelled:no-allow-option]\n"
                        },
                    );
                }
            }
            _ => {}
        }
    }
    let pending_ids: Vec<u64> = pending.iter().map(|entry| *entry.key()).collect();
    for id in pending_ids {
        if let Some((_, tx)) = pending.remove(&id) {
            let _ = tx.send(Err("ACP stdout closed".into()));
        }
    }
}

fn apply_env(cmd: &mut Command, env: &HashMap<String, String>) {
    for (k, v) in env {
        cmd.env(k, v);
    }
}

#[async_trait]
impl AgentRuntime for AcpRuntime {
    fn id(&self) -> &str {
        "acp"
    }

    async fn spawn(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        if cfg.node.is_some() || cfg.user.is_some() {
            return Err(Error::InvalidArgument(
                "acp: remote node dispatch is not supported in P1".into(),
            ));
        }
        let session_id = SessionId::new();
        let cwd = cfg.cwd.clone();
        let mut cmd = Command::new(&self.binary);
        cmd.args(&self.args)
            .current_dir(&cwd)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        #[cfg(unix)]
        cmd.process_group(0);
        // `kill_on_drop` covers the leader; `ProcessGroupGuard` also covers
        // descendants that inherited the dedicated pgid.
        cmd.kill_on_drop(true);
        apply_env(&mut cmd, &cfg.env);
        let mut child = cmd
            .spawn()
            .map_err(|e| Error::Backend(format!("spawn ACP agent '{}': {e}", self.binary)))?;
        let pid = child
            .id()
            .ok_or_else(|| Error::Backend("ACP child pid unavailable".into()))?;
        let mut process_group = ProcessGroupGuard::new(pid);
        let writer = Arc::new(AsyncMutex::new(
            child
                .stdin
                .take()
                .ok_or_else(|| Error::Backend("ACP stdin unavailable".into()))?,
        ));
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| Error::Backend("ACP stdout unavailable".into()))?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| Error::Backend("ACP stderr unavailable".into()))?;
        let pending = Arc::new(DashMap::new());
        let output = Arc::new(Mutex::new(String::new()));
        let reader_task = tokio::spawn(reader_loop(
            stdout,
            writer.clone(),
            pending.clone(),
            output.clone(),
        ));
        let output_err = output.clone();
        let stderr_task = tokio::spawn(async move {
            let mut reader = BufReader::new(stderr);
            let mut text = String::new();
            if reader.read_to_string(&mut text).await.is_ok() && !text.is_empty() {
                append_output(&output_err, &format!("\n[stderr]\n{text}"));
            }
        });
        let next_id = AtomicU64::new(1);

        let init = request(&writer, &pending, &next_id, "initialize", json!({
            "protocolVersion":1,
            "clientCapabilities":{"fs":{"readTextFile":false,"writeTextFile":false},"terminal":false},
            "_meta":{"startupHints":{"nonInteractive":true,"skipGitStatus":true,"skipProjectLayout":true},"clientType":"agent-bridge","clientVersion":env!("CARGO_PKG_VERSION")}
        })).await?;
        if let Some(method) = init
            .get("authMethods")
            .and_then(Value::as_array)
            .and_then(|a| a.first())
            .and_then(|m| m.get("id"))
            .cloned()
        {
            request(
                &writer,
                &pending,
                &next_id,
                "authenticate",
                json!({"methodId":method,"_meta":{"headless":true}}),
            )
            .await?;
        }
        let mut meta = serde_json::Map::new();
        meta.insert("yoloMode".into(), Value::Bool(true));
        if let Some(model) = cfg.model.clone() {
            meta.insert("modelId".into(), Value::String(model));
        }
        let created = request(
            &writer,
            &pending,
            &next_id,
            "session/new",
            json!({"cwd":cwd,"mcpServers":[],"_meta":meta}),
        )
        .await?;
        let protocol_session_id = created
            .get("sessionId")
            .and_then(Value::as_str)
            .ok_or_else(|| Error::Backend(format!("ACP session/new missing sessionId: {created}")))?
            .to_string();

        if let Some(store) = &self.store {
            // Stamp the same pid==pgid invariant used by the existing orphan
            // reaper, so a daemon crash cannot strand a proven ACP group.
            let row = StoredSession {
                id: session_id.clone(),
                runtime_id: self.id().into(),
                cwd: cfg.cwd.clone(),
                started_at: now_secs(),
                ended_at: None,
                exit_code: None,
                stdout: None,
                stderr: None,
                cloud_run_id: None,
                cloud_run_state: None,
                cloud_session_link: None,
                proc_pid: Some(pid as i64),
                proc_pgid: Some(pid as i64),
                proc_start_ticks: crate::pty_session::proc_start_ticks(pid),
                owner_pid: Some(std::process::id() as i64),
                owner_start_ticks: crate::pty_session::proc_start_ticks(std::process::id()),
            };
            if let Err(e) = store.save_session(&row).await {
                warn!(session=%session_id,error=%e,"store: save ACP session failed");
            }
        }
        let live = Arc::new(LiveAcpSession {
            writer,
            pending,
            next_id,
            protocol_session_id,
            output: output.clone(),
            pid,
        });
        self.sessions
            .insert(session_id.as_str().to_string(), live.clone());

        let sid_bg = session_id.clone();
        let sessions_bg = self.sessions.clone();
        let store_bg = self.store.clone();
        tokio::spawn(async move {
            let status = child.wait().await;
            process_group.disarm();
            let _ = reader_task.await;
            let _ = stderr_task.await;
            let stdout = output.lock().unwrap_or_else(|e| e.into_inner()).clone();
            match status {
                Ok(status) => {
                    let exit_code = status.code().or_else(|| {
                        #[cfg(unix)]
                        {
                            use std::os::unix::process::ExitStatusExt;
                            status.signal().map(|signal| -signal)
                        }
                        #[cfg(not(unix))]
                        {
                            None
                        }
                    });
                    if let Some(store) = store_bg {
                        let _ = store
                            .finalise_session(&sid_bg, now_secs(), exit_code, Some(stdout), None)
                            .await;
                    }
                }
                Err(e) => {
                    warn!(session=%sid_bg,error=%e,"ACP child wait failed");
                    if let Some(store) = store_bg {
                        let _ = store
                            .finalise_session(
                                &sid_bg,
                                now_secs(),
                                None,
                                Some(stdout),
                                Some(format!("wait failed: {e}")),
                            )
                            .await;
                    }
                }
            }
            sessions_bg.remove(sid_bg.as_str());
        });
        if let Some(prompt) = cfg.initial_prompt.filter(|p| !p.is_empty()) {
            let live_bg = live.clone();
            tokio::spawn(async move {
                if let Err(e) = live_bg.prompt(prompt).await {
                    append_output(&live_bg.output, &format!("\n[ACP prompt error] {e}\n"));
                }
            });
        }
        info!(session=%session_id,pid,cwd=%cfg.cwd,"ACP session started");
        Ok(AgentSession {
            id: session_id,
            runtime_id: self.id().into(),
            cwd: cfg.cwd,
        })
    }

    async fn send_input(&self, session: &SessionId, text: &str) -> Result<()> {
        let live = self
            .sessions
            .get(session.as_str())
            .map(|v| v.clone())
            .ok_or_else(|| Error::NotFound(format!("no live ACP session {session}")))?;
        let text = text.to_string();
        tokio::spawn(async move {
            if let Err(e) = live.prompt(text).await {
                append_output(&live.output, &format!("\n[ACP prompt error] {e}\n"));
            }
        });
        Ok(())
    }

    async fn kill(&self, session: &SessionId) -> Result<()> {
        let live = self
            .sessions
            .get(session.as_str())
            .map(|v| v.clone())
            .ok_or_else(|| Error::NotFound(format!("no live ACP session {session}")))?;
        // ACP cancel is a notification. Never wait for a response before the
        // OS-level termination fallback: a wedged agent is least likely to
        // answer exactly when kill is needed.
        let _ = write_json(
            &live.writer,
            &json!({"jsonrpc":"2.0","method":"session/cancel","params":{"sessionId":live.protocol_session_id}}),
        )
        .await;
        signal_process_group(live.pid, libc::SIGTERM)
    }

    fn pid_for(&self, session: &SessionId) -> Option<u32> {
        self.sessions.get(session.as_str()).map(|v| v.pid)
    }
    fn read_interactive_output(&self, session: &SessionId) -> Option<String> {
        self.sessions
            .get(session.as_str())
            .map(|v| v.output.lock().unwrap_or_else(|e| e.into_inner()).clone())
    }
    async fn capabilities(&self) -> AgentCapabilities {
        AgentCapabilities {
            supports_mcp: true,
            supports_teams: false,
            supports_thinking: true,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[cfg(unix)]
    use std::os::unix::fs::PermissionsExt;
    #[test]
    fn flattens_message_thought_and_tool_updates() {
        assert_eq!(update_text(&json!({"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"hi"}})).as_deref(), Some("hi"));
        assert_eq!(update_text(&json!({"sessionUpdate":"agent_thought_chunk","content":{"type":"text","text":"hmm"}})).as_deref(), Some("[thought] hmm"));
        assert!(
            update_text(&json!({"sessionUpdate":"tool_call","title":"bash"}))
                .unwrap()
                .contains("bash")
        );
    }
    #[test]
    fn permission_prefers_allow_once() {
        let v = permission_response(
            &json!({"options":[{"optionId":"deny","kind":"reject_once"},{"optionId":"yes","kind":"allow_once"}]}),
        );
        assert_eq!(v.pointer("/outcome/optionId"), Some(&json!("yes")));
    }
    #[test]
    fn permission_uses_allow_always_but_never_selects_reject() {
        let always = permission_response(
            &json!({"options":[{"optionId":"deny","kind":"reject_once"},{"optionId":"yes","kind":"allow_always"}]}),
        );
        assert_eq!(always.pointer("/outcome/optionId"), Some(&json!("yes")));

        let reject_only =
            permission_response(&json!({"options":[{"optionId":"deny","kind":"reject_once"}]}));
        assert_eq!(
            reject_only.pointer("/outcome/outcome"),
            Some(&json!("cancelled"))
        );
    }
    #[test]
    fn capped_output_stays_utf8() {
        let out = Mutex::new("x".repeat(OUTPUT_CAP));
        append_output(&out, "温泉");
        assert!(out.lock().unwrap().len() <= OUTPUT_CAP);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn fake_stdio_agent_completes_lifecycle_and_auto_approves() {
        use ab_store::{SessionFilter, SqliteStore, StateStore as _};

        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time")
            .as_nanos();
        let root = std::env::temp_dir().join(format!("ab-acp-fake-{}-{nanos}", std::process::id()));
        std::fs::create_dir_all(&root).unwrap();
        let path = root.join("fake-agent");
        let store = Arc::new(SqliteStore::open(&root.join("state.db")).await.unwrap());
        std::fs::write(
            &path,
            r#"#!/bin/sh
read init
printf '%s\n' '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1,"authMethods":[]}}'
read new_session
printf '%s\n' '{"jsonrpc":"2.0","id":2,"result":{"sessionId":"fake-session"}}'
read prompt
printf '%s\n' '{"jsonrpc":"2.0","id":99,"method":"session/request_permission","params":{"sessionId":"fake-session","options":[{"optionId":"yes","kind":"allow_once"}]}}'
read permission
printf '%s\n' '{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"fake-session","update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"hello from ACP"}}}}'
printf '%s\n' '{"jsonrpc":"2.0","id":3,"result":{"stopReason":"end_turn"}}'
read followup
sleep 1
printf '%s\n' '{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"fake-session","update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"follow-up from ACP"}}}}'
printf '%s\n' '{"jsonrpc":"2.0","id":4,"result":{"stopReason":"end_turn"}}'
printf '%s\n' 'tail-stderr' >&2
sleep 5
"#,
        )
        .unwrap();
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o700)).unwrap();
        let runtime = AcpRuntime::with_binary(path.to_string_lossy())
            .with_args(Vec::<String>::new())
            .with_store(store.clone());
        let spawned = runtime
            .spawn(SpawnConfig {
                cwd: root.to_string_lossy().into_owned(),
                initial_prompt: Some("test".into()),
                ..SpawnConfig::default()
            })
            .await
            .unwrap();
        let deadline = tokio::time::Instant::now() + Duration::from_secs(2);
        loop {
            let output = runtime
                .read_interactive_output(&spawned.id)
                .unwrap_or_default();
            if output.contains("hello from ACP") && output.contains("permission:auto-approved") {
                break;
            }
            assert!(tokio::time::Instant::now() < deadline, "output={output:?}");
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
        let sent_at = tokio::time::Instant::now();
        runtime.send_input(&spawned.id, "follow-up").await.unwrap();
        assert!(
            sent_at.elapsed() < Duration::from_millis(200),
            "send_input must enqueue the long ACP prompt instead of waiting for turn completion"
        );
        let deadline = tokio::time::Instant::now() + Duration::from_secs(2);
        loop {
            let output = runtime
                .read_interactive_output(&spawned.id)
                .unwrap_or_default();
            if output.contains("follow-up from ACP") {
                break;
            }
            assert!(tokio::time::Instant::now() < deadline, "output={output:?}");
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
        runtime.kill(&spawned.id).await.unwrap();
        let filter = SessionFilter {
            runtime_id: Some("acp".into()),
            cwd_prefix: Some(root.to_string_lossy().into_owned()),
            ..SessionFilter::default()
        };
        let mut finalised = None;
        for _ in 0..80 {
            let rows = store.list_sessions(&filter, 10).await.unwrap();
            if rows.first().is_some_and(|row| row.ended_at.is_some()) {
                finalised = rows.into_iter().next();
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        let finalised = finalised.expect("ACP session must finalise after SIGTERM");
        assert_eq!(finalised.exit_code, Some(-15));
        assert!(finalised.proc_pid.is_some_and(|pid| pid > 1));
        assert_eq!(finalised.proc_pgid, finalised.proc_pid);
        let transcript = finalised.stdout.unwrap_or_default();
        assert!(transcript.contains("follow-up from ACP"), "{transcript:?}");
        assert!(transcript.contains("tail-stderr"), "{transcript:?}");
        let _ = std::fs::remove_dir_all(root);
    }
}
