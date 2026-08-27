//! `opencode` / `kilo` CLI family runtime.
//!
//! `kilo` is a fork of `opencode`, so the two share an identical
//! non-interactive `run` shape:
//!
//! ```text
//! opencode run [--model PROVIDER/MODEL] --dangerously-skip-permissions "<prompt>"
//! kilo run [--model PROVIDER/MODEL] --auto "<prompt>"
//! ```
//!
//! We model both as a single struct parameterised by binary + runtime id +
//! optional default model. Two convenience constructors,
//! [`OpenCodeFamilyRuntime::opencode`] and [`OpenCodeFamilyRuntime::kilo`],
//! pick up sensible defaults from env (`AGENT_BRIDGE_OPENCODE_BIN`,
//! `AGENT_BRIDGE_OPENCODE_MODEL`, `AGENT_BRIDGE_KILO_BIN`,
//! `AGENT_BRIDGE_KILO_MODEL`).
//!
//! Per-call model selection comes from [`SpawnConfig::model`]. If neither
//! the call nor the default is set, the binary picks its own default
//! (which today is `anthropic/claude-sonnet` for kilo and a free-tier model
//! for opencode — both fine for smoke testing).
//!
//! Like [`crate::ClaudeCodeRuntime`] this is a one-shot wrapper: spawn,
//! capture stdout+stderr to the store, surface PID for kill.

use ab_core::{Error, Result, SessionId};
use ab_store::{StateStore, StoredSession};
use async_trait::async_trait;
use dashmap::DashMap;
use std::collections::HashMap;
use std::ffi::OsStr;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::process::Command;
use tokio::sync::Notify;
use tracing::{info, warn};

use crate::pty_interactive::{self, InteractiveMap};
use crate::{AgentCapabilities, AgentRuntime, AgentSession, SpawnConfig};

const KILO_INTERACTIVE_READY_MARKERS: &[&str] = &["Ask anything"];
const RETRY_BACKOFF: Duration = Duration::from_secs(4);
/// Positive 143 is a synthetic Agent-Bridge lifecycle result (128 + SIGTERM),
/// used only when cancellation happens with no child to supply a real status.
/// A child actually terminated by SIGTERM continues to be stored as `-15`.
const SYNTHETIC_CANCEL_EXIT_CODE: i32 = 143;
const SYNTHETIC_CANCEL_MESSAGE: &str =
    "[agent-bridge] cancelled during retry backoff; synthetic exit code 143 (no child was signalable)";

#[derive(Default)]
struct OneShotLifecycle {
    cancelled: AtomicBool,
    retry_waiting: AtomicBool,
    wake: Notify,
}

impl OneShotLifecycle {
    fn cancel(&self) {
        self.cancelled.store(true, Ordering::SeqCst);
        // There is one retry loop per lifecycle. `notify_one` retains a permit
        // if cancellation races just before the loop creates `notified()`.
        self.wake.notify_one();
    }

    fn is_cancelled(&self) -> bool {
        self.cancelled.load(Ordering::SeqCst)
    }

    async fn wait_retry_backoff(&self, duration: Duration) -> bool {
        self.retry_waiting.store(true, Ordering::SeqCst);
        if self.is_cancelled() {
            self.retry_waiting.store(false, Ordering::SeqCst);
            return true;
        }
        let cancelled = tokio::select! {
            _ = tokio::time::sleep(duration) => self.is_cancelled(),
            _ = self.wake.notified() => true,
        };
        self.retry_waiting.store(false, Ordering::SeqCst);
        cancelled
    }

    #[cfg(test)]
    fn is_retry_waiting(&self) -> bool {
        self.retry_waiting.load(Ordering::SeqCst)
    }
}

#[derive(Clone)]
pub struct OpenCodeFamilyRuntime {
    binary: String,
    runtime_id: &'static str,
    default_model: Option<String>,
    auto_approve_flag: &'static str,
    retry_attempts_override: Option<u32>,
    retry_backoff_override: Option<Duration>,
    store: Option<Arc<dyn StateStore>>,
    children: Arc<DashMap<String, u32>>,
    /// Explicit cancellable one-shot lifecycle. It remains addressable during
    /// retry backoff when no PID is safely signalable, so kill can cancel and
    /// wake the retry loop without inventing a process identity.
    active_one_shot: Arc<DashMap<String, Arc<OneShotLifecycle>>>,
    /// Launch flags for the interactive PTY entry point (the bare TUI). Host-
    /// supplied; default empty = bare `<binary>`, which starts the kilo/opencode
    /// TUI. The one-shot `run` path is unaffected.
    interactive_args: Vec<String>,
    /// SessionId → live interactive PTY session (live `send_input`).
    interactive: InteractiveMap,
    /// How this runtime's TUI accepts a submitted turn. Per-runtime, NOT shared:
    /// the family's two binaries do NOT agree. Both real-binary verified —
    /// kilo submits on a bare CR (no Kitty protocol); opencode enables the Kitty
    /// keyboard protocol and submits on KITTY_ENTER (a combined `text\r` write is
    /// dropped). A fork and its upstream needed opposite keys — always probe.
    submit: pty_interactive::SubmitProfile,
}

impl OpenCodeFamilyRuntime {
    /// Build the `opencode` runtime, picking up
    /// `AGENT_BRIDGE_OPENCODE_BIN` / `AGENT_BRIDGE_OPENCODE_MODEL` if set.
    pub fn opencode() -> Self {
        Self {
            binary: std::env::var("AGENT_BRIDGE_OPENCODE_BIN")
                .unwrap_or_else(|_| "opencode".into()),
            runtime_id: "opencode",
            default_model: env_nonempty("AGENT_BRIDGE_OPENCODE_MODEL"),
            auto_approve_flag: "--dangerously-skip-permissions",
            retry_attempts_override: None,
            retry_backoff_override: None,
            store: None,
            children: Arc::new(DashMap::new()),
            active_one_shot: Arc::new(DashMap::new()),
            interactive_args: Vec::new(),
            interactive: Arc::new(DashMap::new()),
            // VERIFIED against the real opencode TUI (2026-06-30, opencode-ai
            // v1.17.12): opencode ENABLES the Kitty keyboard protocol — unlike
            // its own downstream fork kilo, which does not — so the earlier
            // INFERRED `ENTER` was WRONG: a zero-settle combined `text\r` write is
            // typed but never submits (the exact silent hang the old note warned
            // about). Empirically combined-CR fails; both KITTY_ENTER and a
            // CR-after-settle round-trip. Use KITTY_ENTER, matching codex and the
            // TUI's own Kitty-native contract.
            submit: pty_interactive::SubmitProfile::KITTY_ENTER
                .with_initial_prompt_delay(Duration::from_secs(3)),
        }
    }

    /// Build the `kilo` runtime, picking up
    /// `AGENT_BRIDGE_KILO_BIN` / `AGENT_BRIDGE_KILO_MODEL` if set.
    pub fn kilo() -> Self {
        let home = std::env::var_os("HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("."));
        let path_env = std::env::var_os("PATH")
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();
        Self {
            binary: resolve_kilo_binary_from(
                &home,
                &path_env,
                env_nonempty("AGENT_BRIDGE_KILO_BIN"),
            ),
            runtime_id: "kilo",
            default_model: env_nonempty("AGENT_BRIDGE_KILO_MODEL"),
            auto_approve_flag: "--auto",
            retry_attempts_override: None,
            retry_backoff_override: None,
            store: None,
            children: Arc::new(DashMap::new()),
            active_one_shot: Arc::new(DashMap::new()),
            interactive_args: Vec::new(),
            interactive: Arc::new(DashMap::new()),
            // VERIFIED against the real kilo TUI (tests/kilo_real_interactive.rs):
            // it emits no Kitty keyboard protocol and uses bracketed paste, so a
            // bare CR submits — proven by a multi-turn 42/99 round-trip.
            // Kilo 7.3.x can spend several seconds painting its alternate-screen
            // boot UI before the composer is ready. Input sent during that
            // window is silently dropped, while later send_input turns work.
            // Wait for the visible composer marker instead of racing it with a
            // fixed sleep.
            submit: pty_interactive::SubmitProfile::ENTER.with_initial_prompt_ready_markers(
                KILO_INTERACTIVE_READY_MARKERS,
                Duration::from_secs(30),
            ),
        }
    }

    pub fn with_store(mut self, store: Arc<dyn StateStore>) -> Self {
        self.store = Some(store);
        self
    }

    pub fn with_binary(mut self, binary: impl Into<String>) -> Self {
        self.binary = binary.into();
        self
    }

    pub fn with_default_model(mut self, model: impl Into<String>) -> Self {
        self.default_model = Some(model.into());
        self
    }

    #[cfg(test)]
    fn with_retry_attempts_for_test(mut self, attempts: u32) -> Self {
        self.retry_attempts_override = Some(attempts.max(1));
        self
    }

    #[cfg(test)]
    fn with_retry_backoff_for_test(mut self, duration: Duration) -> Self {
        self.retry_backoff_override = Some(duration);
        self
    }

    /// Launch flags for the interactive PTY entry point (the bare TUI). Host-
    /// supplied; default empty = bare `<binary>`. The one-shot `run` path is
    /// unaffected (it always appends `run <auto_flag> <prompt>`).
    pub fn with_interactive_args(
        mut self,
        args: impl IntoIterator<Item = impl Into<String>>,
    ) -> Self {
        self.interactive_args = args.into_iter().map(Into::into).collect();
        self
    }

    /// Number of currently signalable one-shot child generations. A retrying
    /// session has no safe PID during its backoff and is intentionally absent.
    pub fn live_count(&self) -> usize {
        self.children.len()
    }

    #[cfg(test)]
    fn retry_backoff_active(&self, session: &SessionId) -> bool {
        self.active_one_shot
            .get(session.as_str())
            .is_some_and(|lifecycle| lifecycle.is_retry_waiting())
    }

    /// Number of live interactive PTY sessions (testing / observability).
    pub fn interactive_count(&self) -> usize {
        self.interactive.len()
    }

    /// Snapshot the merged PTY output of a live interactive session, if one
    /// exists for `session`. Returns `None` once the session has exited (and
    /// been finalised to the [`StateStore`]).
    pub fn read_interactive_output(&self, session: &SessionId) -> Option<String> {
        pty_interactive::interactive_output(&self.interactive, session)
    }

    /// Launch the kilo/opencode TUI inside a PTY the daemon owns and keep it
    /// alive for successive [`AgentRuntime::send_input`] turns. Mirrors the
    /// one-shot path's StateStore bookkeeping (start row at spawn, finalise on
    /// exit). The interactive entry point is the bare binary (no `run`); the host
    /// may add launch flags via [`Self::with_interactive_args`].
    ///
    /// Uses this runtime's [`submit`](Self::submit) profile — both real-binary
    /// verified: bare CR for kilo, KITTY_ENTER for opencode (Kitty-native); see
    /// the constructors.
    async fn spawn_interactive(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        pty_interactive::spawn_interactive(
            self.id(),
            &self.binary,
            &self.interactive_args,
            &self.store,
            &self.interactive,
            cfg,
            self.submit,
        )
        .await
    }
}

fn env_nonempty(key: &str) -> Option<String> {
    std::env::var(key)
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
}

/// POSIX single-quote escape so an arbitrary value (prompt, model, env value,
/// cwd) is transported intact inside the single remote-command string we hand
/// to `ssh`. The remote login shell parses that string exactly once, so each
/// untrusted piece is wrapped in `'…'` with embedded quotes escaped as `'\''`.
fn sh_single_quote(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('\'');
    for ch in s.chars() {
        if ch == '\'' {
            out.push_str("'\\''");
        } else {
            out.push(ch);
        }
    }
    out.push('\'');
    out
}

/// Whether a `node` value designates a real remote host (not this machine).
fn is_remote_node(node: Option<&str>) -> bool {
    node.map(|n| {
        let n = n.trim();
        !n.is_empty() && !n.eq_ignore_ascii_case("local") && !n.eq_ignore_ascii_case("localhost")
    })
    .unwrap_or(false)
}

/// Build the single remote-shell command string for an ssh-dispatched one-shot
/// run: `[cd <cwd> &&] <ENV…> "<bin>" run <auto> [--model <m>] <prompt>`.
/// `cwd`/`model`/`prompt`/env values are single-quoted; `bin` is wrapped in
/// double quotes so a leading `$HOME` (the kilo default) expands on the remote
/// while the path stays space-safe. Mirrors the proven `ab-kilo-run.sh` path.
fn build_remote_run_cmd(
    bin: &str,
    auto_flag: &str,
    cwd: &str,
    model: Option<&str>,
    prompt: &str,
    env: &HashMap<String, String>,
) -> String {
    let mut cmd = String::new();
    if !cwd.is_empty() {
        cmd.push_str(&format!("cd {} && ", sh_single_quote(cwd)));
    }
    // env assignments prefix the command (apply only to it). Skip keys that
    // are not safe shell identifiers rather than risk an injection.
    for (k, v) in env {
        if !k.is_empty()
            && k.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
            && !k.chars().next().unwrap().is_ascii_digit()
        {
            cmd.push_str(&format!("{}={} ", k, sh_single_quote(v)));
        }
    }
    cmd.push_str(&format!("\"{bin}\" run {auto_flag}"));
    if let Some(m) = model {
        cmd.push_str(&format!(" --model {}", sh_single_quote(m)));
    }
    cmd.push_str(&format!(" {}", sh_single_quote(prompt)));
    cmd
}

/// The kilo/opencode `*/free` gateway intermittently returns this when its pool
/// is momentarily empty; the same call almost always succeeds on the next try.
/// Detected in either stream because kilo prints it to stderr while exiting 0.
fn is_provider_miss(output: &str) -> bool {
    output.contains("ProviderModelNotFoundError") || output.contains("Model not found")
}

/// OpenCode can print this expired-login error and still exit 0. Treat the
/// proven provider message as a failed execution; broad user/model text such
/// as `unauthorized` is intentionally not classified here.
fn is_auth_failure(output: &str) -> bool {
    let normalized = output.to_ascii_lowercase();
    normalized.contains("token refresh failed: 401")
}

fn is_payment_failure(output: &str) -> bool {
    strip_csi_sequences(output)
        .to_ascii_lowercase()
        .contains("error: no payment method.")
}

fn strip_csi_sequences(output: &str) -> String {
    let mut clean = String::with_capacity(output.len());
    let mut chars = output.chars();
    while let Some(ch) = chars.next() {
        if ch == '\u{1b}' && chars.next() == Some('[') {
            for code in chars.by_ref() {
                if code.is_ascii_alphabetic() {
                    break;
                }
            }
        } else {
            clean.push(ch);
        }
    }
    clean
}

fn corrected_exit_code(exit_code: Option<i32>, stdout: &str, stderr: &str) -> Option<i32> {
    if exit_code == Some(0)
        && (is_auth_failure(stdout) || is_auth_failure(stderr) || is_payment_failure(stderr))
    {
        Some(1)
    } else {
        exit_code
    }
}

/// Everything needed to (re)build the one-shot run Command, so the background
/// wait loop can retry the SAME invocation on a free-pool miss without
/// re-deriving it. `build()` only constructs the local/remote launch command;
/// `spawn()` performs process creation.
struct SpawnPlan {
    runtime_id: &'static str,
    remote: bool,
    // remote (ssh) fields
    ssh_dest: String,
    ssh_key: Option<String>,
    remote_cmd: String,
    // local fields
    binary: String,
    auto_flag: &'static str,
    model: Option<String>,
    prompt: String,
    cwd: String,
    env: HashMap<String, String>,
}

impl SpawnPlan {
    fn build(&self) -> Result<Command> {
        if self.remote {
            let mut c = Command::new("ssh");
            c.arg("-o")
                .arg("BatchMode=yes")
                .arg("-o")
                .arg("ConnectTimeout=10");
            if let Some(key) = &self.ssh_key {
                c.arg("-i").arg(key);
            }
            c.arg(&self.ssh_dest).arg(&self.remote_cmd);
            // env is injected into remote_cmd; cwd is a remote path → no current_dir.
            c.stdin(Stdio::null())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped());
            Ok(c)
        } else {
            let mut args = vec!["run".to_string(), self.auto_flag.to_string()];
            if let Some(m) = &self.model {
                args.push("--model".to_string());
                args.push(m.clone());
            }
            // The prompt comes last as a positional argument so any preceding
            // flag values (model strings, etc.) can't shadow it.
            args.push(self.prompt.clone());
            let launch = crate::sandbox::wrap_local_command(
                self.runtime_id,
                &self.cwd,
                &self.env,
                &self.binary,
                &args,
            )?;
            let mut c = Command::new(&launch.program);
            c.args(&launch.args);
            c.current_dir(&self.cwd)
                .stdin(Stdio::null())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped());
            crate::sandbox::configure_command_env(&mut c, &self.env, launch.sandboxed)?;
            Ok(c)
        }
    }

    fn spawn(&self) -> Result<tokio::process::Child> {
        self.build()?
            .spawn()
            .map_err(|e| Error::Backend(format!("spawn {}: {e}", self.runtime_id)))
    }
}

fn process_scope_for_plan(plan: &SpawnPlan) -> crate::SpawnedProcessScope {
    if plan.remote {
        crate::SpawnedProcessScope::LocalTransport
    } else {
        crate::SpawnedProcessScope::LocalWorkloadRoot
    }
}

fn resolve_kilo_binary_from(home: &Path, path_env: &str, env_override: Option<String>) -> String {
    if let Some(binary) = env_override {
        return binary;
    }
    if let Some(binary) = find_executable_in_path("kilo", path_env) {
        return binary.display().to_string();
    }
    if let Some(binary) = find_latest_kilo_extension_binary(home) {
        return binary.display().to_string();
    }
    "kilo".to_string()
}

fn find_executable_in_path(name: &str, path_env: &str) -> Option<PathBuf> {
    std::env::split_paths(OsStr::new(path_env))
        .map(|dir| dir.join(name))
        .find(|path| is_executable_file(path))
}

fn find_latest_kilo_extension_binary(home: &Path) -> Option<PathBuf> {
    let roots = [
        home.join(".cursor").join("extensions"),
        home.join(".vscode").join("extensions"),
        home.join(".vscode-insiders").join("extensions"),
        home.join(".antigravity").join("extensions"),
        PathBuf::from("/Media/Ubuntu/Documents/.antigravity/extensions"),
    ];
    let mut candidates = Vec::new();
    for root in roots {
        let Ok(entries) = std::fs::read_dir(root) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            let Some(name) = path.file_name().and_then(|s| s.to_str()) else {
                continue;
            };
            if !name.starts_with("kilocode.kilo-code-") {
                continue;
            }
            let binary = path.join("bin").join("kilo");
            if is_executable_file(&binary) {
                candidates.push((kilo_extension_version_key(name), binary));
            }
        }
    }
    candidates.sort_by(|a, b| a.0.cmp(&b.0));
    candidates.pop().map(|(_, path)| path)
}

fn kilo_extension_version_key(name: &str) -> Vec<u32> {
    name.trim_start_matches("kilocode.kilo-code-")
        .split('-')
        .next()
        .unwrap_or_default()
        .split('.')
        .map(|part| part.parse::<u32>().unwrap_or(0))
        .collect()
}

fn is_executable_file(path: &Path) -> bool {
    let Ok(meta) = std::fs::metadata(path) else {
        return false;
    };
    if !meta.is_file() {
        return false;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        meta.permissions().mode() & 0o111 != 0
    }
    #[cfg(not(unix))]
    {
        true
    }
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

async fn finalise_synthetic_retry_cancel(
    store: &Option<Arc<dyn StateStore>>,
    session: &SessionId,
    stdout: Option<String>,
    stderr: Option<String>,
) {
    let stderr = match stderr.filter(|text| !text.is_empty()) {
        Some(text) => format!("{text}\n{SYNTHETIC_CANCEL_MESSAGE}"),
        None => SYNTHETIC_CANCEL_MESSAGE.to_string(),
    };
    if let Some(store) = store {
        let _ = store
            .finalise_session(
                session,
                now_secs(),
                Some(SYNTHETIC_CANCEL_EXIT_CODE),
                stdout,
                Some(stderr),
            )
            .await;
    }
}

#[async_trait]
impl AgentRuntime for OpenCodeFamilyRuntime {
    fn id(&self) -> &str {
        self.runtime_id
    }

    fn workspace_contract(&self) -> crate::WorkspaceRuntimeContract {
        crate::WorkspaceRuntimeContract::local_or_remote_agent(true)
    }

    async fn spawn(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        let remote = is_remote_node(cfg.node.as_deref());
        if cfg.interactive {
            if remote {
                return Err(Error::InvalidArgument(format!(
                    "{}: remote interactive sessions are not implemented; refusing to run the requested remote session locally",
                    self.runtime_id
                )));
            }
            return self.spawn_interactive(cfg).await;
        }

        let prompt = cfg.initial_prompt.clone().unwrap_or_default();
        if prompt.is_empty() {
            return Err(Error::InvalidArgument(format!(
                "{}: 'initial_prompt' is required for one-shot spawn",
                self.runtime_id
            )));
        }
        let model = cfg.model.clone().or_else(|| self.default_model.clone());
        let sandbox_profile_requested = (crate::sandbox::effective_mode(&cfg.env)?
            == crate::sandbox::AgentSandboxMode::Workspace)
            .then(|| "workspace".to_string());
        if remote && sandbox_profile_requested.is_some() {
            return Err(Error::InvalidArgument(format!(
                "{}: workspace sandboxing is local-only in P1; refusing to launch a remote SSH executor without equivalent remote enforcement",
                self.runtime_id
            )));
        }

        let session_id = SessionId::new();
        let cwd = cfg.cwd.clone();

        if let Some(store) = &self.store {
            let initial = StoredSession {
                id: session_id.clone(),
                runtime_id: self.runtime_id.into(),
                cwd: cwd.clone(),
                started_at: now_secs(),
                ended_at: None,
                exit_code: None,
                stdout: None,
                stderr: None,
                cloud_run_id: None,
                cloud_run_state: None,
                cloud_session_link: None,
                proc_pid: None,
                proc_pgid: None,
                proc_start_ticks: None,
                owner_pid: None,
                owner_start_ticks: None,
            };
            if let Err(e) = store.save_session(&initial).await {
                warn!(session = %session_id, error = %e, "store: save_session failed");
            }
        }

        let plan = if remote {
            // Dispatch the one-shot run to a tailnet node via ssh. The local ssh
            // child's stdout/stderr capture the remote output and ssh's exit
            // status mirrors the remote command's, so the background wait +
            // finalise_session path below works unchanged — the run becomes
            // visible in agent_sessions / event_spine while staying free.
            let node = cfg.node.as_deref().unwrap_or_default();
            let dest = match cfg.user.as_deref().filter(|u| !u.is_empty()) {
                Some(u) => format!("{u}@{node}"),
                None => node.to_string(),
            };
            // Remote binary: kilo is not on PATH on the canonical node, so default
            // to the workspace convention `$HOME/.kilo/bin/kilo` (expanded by the
            // remote shell), overridable via AGENT_BRIDGE_KILO_REMOTE_BIN. Other
            // runtimes fall back to their bare id (resolved on the remote PATH).
            let remote_bin = if self.runtime_id == "kilo" {
                env_nonempty("AGENT_BRIDGE_KILO_REMOTE_BIN")
                    .unwrap_or_else(|| "$HOME/.kilo/bin/kilo".to_string())
            } else {
                self.runtime_id.to_string()
            };
            let remote_cmd = build_remote_run_cmd(
                &remote_bin,
                self.auto_approve_flag,
                &cwd,
                model.as_deref(),
                &prompt,
                &cfg.env,
            );
            info!(
                session = %session_id,
                runtime = %self.runtime_id,
                dest = %dest,
                "dispatching one-shot run to remote node via ssh"
            );
            SpawnPlan {
                runtime_id: self.runtime_id,
                remote: true,
                ssh_dest: dest,
                ssh_key: env_nonempty("AGENT_BRIDGE_SSH_KEY"),
                remote_cmd,
                binary: String::new(),
                auto_flag: self.auto_approve_flag,
                model: model.clone(),
                prompt: prompt.clone(),
                cwd: cwd.clone(),
                env: cfg.env.clone(),
            }
        } else {
            SpawnPlan {
                runtime_id: self.runtime_id,
                remote: false,
                ssh_dest: String::new(),
                ssh_key: None,
                remote_cmd: String::new(),
                binary: self.binary.clone(),
                auto_flag: self.auto_approve_flag,
                model: model.clone(),
                prompt: prompt.clone(),
                cwd: cwd.clone(),
                env: cfg.env.clone(),
            }
        };

        // Free-pool retry-on-miss: the kilo/opencode `*/free` gateway intermittently
        // returns ProviderModelNotFoundError with an empty pool; the same call
        // usually succeeds on retry. Mirrors scripts/ab-kilo-run.sh. Default 3
        // total attempts; override with AGENT_BRIDGE_KILO_RETRIES.
        let max_attempts = self
            .retry_attempts_override
            .or_else(|| {
                env_nonempty("AGENT_BRIDGE_KILO_RETRIES")
                    .and_then(|s| s.parse::<u32>().ok())
                    .filter(|n| *n >= 1)
            })
            .unwrap_or(3);
        let retry_backoff = self.retry_backoff_override.unwrap_or(RETRY_BACKOFF);

        let child = match plan.spawn() {
            Ok(child) => child,
            Err(e) => {
                let message = format!("spawn {}: {e}", self.runtime_id);
                if let Some(store) = &self.store {
                    if let Err(store_err) = store
                        .finalise_session(
                            &session_id,
                            now_secs(),
                            Some(127),
                            None,
                            Some(message.clone()),
                        )
                        .await
                    {
                        warn!(
                            session = %session_id,
                            runtime = %self.runtime_id,
                            error = %store_err,
                            "store: finalise failed spawn session failed"
                        );
                    }
                }
                return Err(Error::Backend(message));
            }
        };
        let pid = child.id().unwrap_or(0);
        let process_scope = process_scope_for_plan(&plan);
        let process_custody = crate::SpawnedProcessCustody::from_spawn(pid, None, process_scope);
        if pid != 0 {
            self.children.insert(session_id.as_str().to_string(), pid);
        }
        let lifecycle = Arc::new(OneShotLifecycle::default());
        self.active_one_shot
            .insert(session_id.as_str().to_string(), lifecycle.clone());
        info!(
            session = %session_id,
            pid,
            runtime = %self.runtime_id,
            model = ?model,
            cwd = %cwd,
            "session started"
        );

        let runtime_id = self.runtime_id;
        let sid_bg = session_id.clone();
        let store_bg = self.store.clone();
        let children_bg = self.children.clone();
        let active_bg = self.active_one_shot.clone();
        let terminal_custody = process_custody.clone();
        tokio::spawn(async move {
            let mut child = child;
            let mut wait_observation = terminal_custody
                .as_ref()
                .map(|custody| custody.initial_wait_observation());
            let mut attempt: u32 = 1;
            loop {
                let out = match wait_observation.take() {
                    Some(observation) => {
                        let children_reaped = children_bg.clone();
                        let sid_reaped = sid_bg.clone();
                        crate::terminal_rusage::wait_with_output_notify_reaped(
                            child,
                            observation,
                            move || {
                                children_reaped.remove(sid_reaped.as_str());
                            },
                        )
                        .await
                    }
                    None => child.wait_with_output().await,
                };
                // Idempotent fallback for a wait error or a PID-less child. A
                // successful observed reap already removed the PID through the
                // callback, before inherited descendant pipes necessarily EOF.
                children_bg.remove(sid_bg.as_str());
                let ended_at = now_secs();
                match out {
                    Ok(o) => {
                        let stdout = String::from_utf8_lossy(&o.stdout).into_owned();
                        let stderr = String::from_utf8_lossy(&o.stderr).into_owned();
                        // Retry the SAME invocation on a free-pool miss while
                        // attempts remain (kilo exits 0 yet prints the error).
                        if attempt < max_attempts
                            && (is_provider_miss(&stdout) || is_provider_miss(&stderr))
                        {
                            if lifecycle.is_cancelled() {
                                if let Some(custody) = &terminal_custody {
                                    custody.seal_terminal_resources();
                                }
                                active_bg.remove(sid_bg.as_str());
                                finalise_synthetic_retry_cancel(
                                    &store_bg,
                                    &sid_bg,
                                    Some(stdout),
                                    Some(stderr),
                                )
                                .await;
                                break;
                            }
                            warn!(
                                session = %sid_bg,
                                runtime = %runtime_id,
                                attempt,
                                max_attempts,
                                "free-pool miss (ProviderModelNotFoundError) — retrying"
                            );
                            if lifecycle.wait_retry_backoff(retry_backoff).await
                                || lifecycle.is_cancelled()
                            {
                                if let Some(custody) = &terminal_custody {
                                    custody.seal_terminal_resources();
                                }
                                active_bg.remove(sid_bg.as_str());
                                finalise_synthetic_retry_cancel(
                                    &store_bg,
                                    &sid_bg,
                                    Some(stdout),
                                    Some(stderr),
                                )
                                .await;
                                info!(
                                    session = %sid_bg,
                                    runtime = %runtime_id,
                                    exit = SYNTHETIC_CANCEL_EXIT_CODE,
                                    "retry lifecycle cancelled with no signalable child"
                                );
                                break;
                            }

                            // The synchronous spawn below can race a cancel.
                            // Check immediately before it, then again after a
                            // successful spawn while the owned Child handle can
                            // still terminate/reap the new generation safely.
                            if lifecycle.is_cancelled() {
                                if let Some(custody) = &terminal_custody {
                                    custody.seal_terminal_resources();
                                }
                                active_bg.remove(sid_bg.as_str());
                                finalise_synthetic_retry_cancel(
                                    &store_bg,
                                    &sid_bg,
                                    Some(stdout),
                                    Some(stderr),
                                )
                                .await;
                                break;
                            }
                            match plan.spawn() {
                                Ok(mut next) => {
                                    let npid = next.id().unwrap_or(0);
                                    wait_observation = terminal_custody
                                        .as_ref()
                                        .and_then(|custody| custody.begin_process_generation(npid));
                                    if npid != 0 {
                                        children_bg.insert(sid_bg.as_str().to_string(), npid);
                                    }
                                    if lifecycle.is_cancelled() {
                                        // `start_kill` signals but never reaps.
                                        // The next loop iteration observes the
                                        // generation's rusage and performs the
                                        // sole Child::wait reap as usual.
                                        let _ = next.start_kill();
                                    }
                                    child = next;
                                    attempt += 1;
                                    continue;
                                }
                                Err(e) => {
                                    if let Some(custody) = &terminal_custody {
                                        custody.seal_terminal_resources();
                                    }
                                    active_bg.remove(sid_bg.as_str());
                                    if lifecycle.is_cancelled() {
                                        finalise_synthetic_retry_cancel(
                                            &store_bg,
                                            &sid_bg,
                                            Some(stdout),
                                            Some(stderr),
                                        )
                                        .await;
                                    } else if let Some(store) = store_bg.clone() {
                                        let _ = store
                                            .finalise_session(
                                                &sid_bg,
                                                now_secs(),
                                                Some(127),
                                                None,
                                                Some(format!("retry spawn failed: {e}")),
                                            )
                                            .await;
                                    }
                                    break;
                                }
                            }
                        }
                        if let Some(custody) = &terminal_custody {
                            custody.seal_terminal_resources();
                        }
                        active_bg.remove(sid_bg.as_str());
                        info!(
                            session = %sid_bg,
                            runtime = %runtime_id,
                            attempt,
                            exit = ?o.status.code(),
                            stdout_preview = %truncate(&stdout, 200),
                            stderr_preview = %truncate(&stderr, 200),
                            "session finished"
                        );
                        let exit_code = o.status.code().or_else(|| {
                            #[cfg(unix)]
                            {
                                use std::os::unix::process::ExitStatusExt;
                                o.status.signal().map(|s| -(s as i32))
                            }
                            #[cfg(not(unix))]
                            {
                                None
                            }
                        });
                        let provider_failure = exit_code == Some(0)
                            && (is_auth_failure(&stdout)
                                || is_auth_failure(&stderr)
                                || is_payment_failure(&stderr));
                        let exit_code = corrected_exit_code(exit_code, &stdout, &stderr);
                        if provider_failure {
                            warn!(
                                session = %sid_bg,
                                runtime = %runtime_id,
                                "provider failure reported by child; overriding successful exit status"
                            );
                        }
                        if let Some(store) = store_bg.clone() {
                            let _ = store
                                .finalise_session(
                                    &sid_bg,
                                    ended_at,
                                    exit_code,
                                    Some(stdout),
                                    Some(stderr),
                                )
                                .await;
                        }
                        break;
                    }
                    Err(e) => {
                        if let Some(custody) = &terminal_custody {
                            custody.seal_terminal_resources();
                        }
                        active_bg.remove(sid_bg.as_str());
                        warn!(
                            session = %sid_bg,
                            runtime = %runtime_id,
                            error = %e,
                            "wait failed"
                        );
                        if let Some(store) = store_bg.clone() {
                            let _ = store
                                .finalise_session(
                                    &sid_bg,
                                    ended_at,
                                    None,
                                    None,
                                    Some(format!("wait failed: {e}")),
                                )
                                .await;
                        }
                        break;
                    }
                }
            }
        });

        Ok(AgentSession {
            id: session_id,
            runtime_id: self.runtime_id.into(),
            cwd,
            sandbox_profile_requested,
            process_custody,
        })
    }

    async fn send_input(&self, session: &SessionId, text: &str) -> Result<()> {
        pty_interactive::send_input(self.id(), &self.interactive, session, text, self.submit).await
    }

    async fn kill(&self, session: &SessionId) -> Result<()> {
        // Interactive PTY session: signal the child via its kill handle. The
        // background reader sees EOF, reaps, and finalises the session row.
        if let Some(result) =
            pty_interactive::kill_interactive(self.id(), &self.interactive, session)
        {
            return result;
        }

        let lifecycle = self
            .active_one_shot
            .get(session.as_str())
            .map(|entry| entry.clone())
            .ok_or_else(|| {
                Error::NotFound(format!(
                    "no active one-shot lifecycle for session {session} (already finished or unknown)"
                ))
            })?;
        // Cancellation is durable for the in-memory lifecycle before any
        // signal attempt. It also wakes a PID-less retry backoff immediately.
        lifecycle.cancel();
        let Some(pid) = self.children.get(session.as_str()).map(|entry| *entry) else {
            info!(
                session = %session,
                runtime = %self.runtime_id,
                "retry lifecycle cancellation recorded with no signalable child"
            );
            return Ok(());
        };
        let status = tokio::process::Command::new("/bin/kill")
            .arg("-TERM")
            .arg(pid.to_string())
            .status()
            .await
            .map_err(|e| Error::Backend(format!("kill -TERM {pid}: {e}")))?;
        if !status.success() {
            return Err(Error::Backend(format!("/bin/kill exited with {status:?}")));
        }
        info!(
            session = %session,
            pid,
            runtime = %self.runtime_id,
            "SIGTERM sent"
        );
        Ok(())
    }

    fn pid_for(&self, session: &SessionId) -> Option<u32> {
        if let Some(pid) = pty_interactive::interactive_pid(&self.interactive, session) {
            return Some(pid);
        }
        self.children.get(session.as_str()).map(|kv| *kv)
    }

    fn session_is_active(&self, session: &SessionId) -> bool {
        pty_interactive::interactive_pid(&self.interactive, session).is_some()
            || self.children.contains_key(session.as_str())
            || self.active_one_shot.contains_key(session.as_str())
    }

    /// Trait-level exposure of the live interactive PTY buffer (bare-CR TUI)
    /// so `agent_session_output` can read a reply through `dyn AgentRuntime`;
    /// mirrors inherent [`OpenCodeFamilyRuntime::read_interactive_output`].
    fn read_interactive_output(&self, session: &SessionId) -> Option<String> {
        pty_interactive::interactive_output(&self.interactive, session)
    }

    async fn capabilities(&self) -> AgentCapabilities {
        AgentCapabilities {
            supports_mcp: true,
            supports_teams: false,
            supports_thinking: false,
        }
    }
}

fn truncate(s: &str, max: usize) -> String {
    let chars: Vec<char> = s.chars().collect();
    if chars.len() <= max {
        s.replace('\n', " ⏎ ")
    } else {
        let head: String = chars
            .iter()
            .take(max - 1)
            .collect::<String>()
            .replace('\n', " ⏎ ");
        format!("{head}…")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    #[cfg(unix)]
    use std::os::unix::fs::PermissionsExt;
    use std::path::Path;

    #[test]
    fn kilo_discovers_latest_extension_binary_when_kilo_is_not_on_path() {
        let root = unique_temp_dir("ab-kilo-resolver");
        let home = root.join("home");
        let older = home
            .join(".vscode-insiders")
            .join("extensions")
            .join("kilocode.kilo-code-7.2.31-linux-x64")
            .join("bin")
            .join("kilo");
        let newer = home
            .join(".vscode-insiders")
            .join("extensions")
            .join("kilocode.kilo-code-7.3.1-linux-x64")
            .join("bin")
            .join("kilo");
        write_executable(&older);
        write_executable(&newer);

        let resolved = resolve_kilo_binary_from(&home, "", None);

        assert_eq!(resolved, newer.display().to_string());
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn kilo_runtime_uses_kilo_auto_flag() {
        let runtime = OpenCodeFamilyRuntime::kilo();

        assert_eq!(runtime.auto_approve_flag, "--auto");
    }

    #[test]
    fn sh_single_quote_wraps_and_escapes() {
        assert_eq!(sh_single_quote("plain"), "'plain'");
        assert_eq!(sh_single_quote(""), "''");
        // an embedded single quote becomes close-quote, escaped quote, reopen
        assert_eq!(sh_single_quote("a'b"), "'a'\\''b'");
        // shell metacharacters are inert inside single quotes
        assert_eq!(sh_single_quote("$(rm -rf /)"), "'$(rm -rf /)'");
    }

    #[test]
    fn is_remote_node_only_true_for_real_hosts() {
        assert!(!is_remote_node(None));
        assert!(!is_remote_node(Some("")));
        assert!(!is_remote_node(Some("  ")));
        assert!(!is_remote_node(Some("local")));
        assert!(!is_remote_node(Some("LOCALHOST")));
        assert!(is_remote_node(Some("100.93.4.56")));
        assert!(is_remote_node(Some("aio2")));
    }

    #[test]
    fn custody_scope_distinguishes_local_workload_from_remote_transport() {
        let mut plan = SpawnPlan {
            runtime_id: "kilo",
            remote: false,
            ssh_dest: String::new(),
            ssh_key: None,
            remote_cmd: String::new(),
            binary: "/bin/true".into(),
            auto_flag: "--auto",
            model: None,
            prompt: "test".into(),
            cwd: "/tmp".into(),
            env: HashMap::new(),
        };
        assert_eq!(
            process_scope_for_plan(&plan),
            crate::SpawnedProcessScope::LocalWorkloadRoot
        );

        plan.remote = true;
        assert_eq!(
            process_scope_for_plan(&plan),
            crate::SpawnedProcessScope::LocalTransport
        );
    }

    #[tokio::test]
    async fn remote_interactive_request_fails_before_local_spawn() {
        let runtime = OpenCodeFamilyRuntime::kilo().with_binary("/definitely/missing/kilo");
        let error = runtime
            .spawn(SpawnConfig {
                cwd: "/remote/work".into(),
                node: Some("remote-node".into()),
                interactive: true,
                ..Default::default()
            })
            .await
            .expect_err("remote interactive must fail closed");
        let message = error.to_string();
        assert!(message.contains("remote interactive sessions are not implemented"));
        assert!(!message.contains("No such file"));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn local_spawn_returns_workload_root_custody() {
        let runtime = OpenCodeFamilyRuntime::kilo().with_binary("/bin/true");
        let session = runtime
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                initial_prompt: Some("custody probe".into()),
                ..Default::default()
            })
            .await
            .expect("spawn local stand-in");
        let custody = session.process_custody().expect("spawn custody");
        assert_eq!(
            custody.scope(),
            crate::SpawnedProcessScope::LocalWorkloadRoot
        );
        assert!(custody.is_local_workload_root());
        #[cfg(target_os = "linux")]
        assert!(
            custody.start_ticks().is_some(),
            "custody must be minted while the fast-exit child is still owned and unreaped"
        );
    }

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn retry_generations_accumulate_rusage_and_clear_reaped_pid_before_backoff() {
        use ab_store::{SessionFilter, SqliteStore, StateStore as _};

        let root = unique_temp_dir("ab-opencode-rusage-retry");
        fs::create_dir_all(&root).expect("mkdir root");
        let binary = root.join("fake-opencode");
        fs::write(
            &binary,
            r#"#!/bin/sh
state="$(dirname "$0")/attempts"
attempt=0
if [ -f "$state" ]; then attempt="$(cat "$state")"; fi
attempt=$((attempt + 1))
printf '%s' "$attempt" > "$state"
if [ "$attempt" -eq 1 ]; then
  # The waited shell exits immediately while this descendant keeps both
  # inherited capture pipes open. PID custody must clear at reap, not EOF.
  sleep 3 &
  printf '%s\n' 'ProviderModelNotFoundError'
else
  printf '%s\n' 'completed'
fi
"#,
        )
        .expect("write fake opencode");
        let mut permissions = fs::metadata(&binary).expect("metadata").permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(&binary, permissions).expect("chmod");
        let store = Arc::new(
            SqliteStore::open(&root.join("state.db"))
                .await
                .expect("open store"),
        );
        let runtime = OpenCodeFamilyRuntime::opencode()
            .with_binary(binary.display().to_string())
            .with_retry_attempts_for_test(2)
            .with_store(store.clone());
        let session = runtime
            .spawn(SpawnConfig {
                cwd: root.display().to_string(),
                initial_prompt: Some("retry probe".into()),
                ..Default::default()
            })
            .await
            .expect("spawn retry probe");
        let custody = session.process_custody().expect("custody");
        assert_eq!(runtime.live_count(), 1);

        // The retry delay is four seconds. The reaped generation must stop
        // being kill-addressable well before the next generation is spawned.
        let old_pid_cleared = wait_for(2_000, 20, || runtime.live_count() == 0).await;
        assert!(
            old_pid_cleared,
            "reaped generation PID must be removed before retry backoff"
        );
        assert!(runtime.pid_for(&session.id).is_none());
        assert!(
            runtime.session_is_active(&session.id),
            "retry backoff remains active without inventing a PID"
        );

        let filter = SessionFilter {
            runtime_id: Some("opencode".into()),
            cwd_prefix: Some(root.display().to_string()),
            ..SessionFilter::default()
        };
        let mut ended = false;
        for _ in 0..400 {
            let rows = store.list_sessions(&filter, 10).await.expect("list");
            if rows.first().is_some_and(|row| row.ended_at.is_some()) {
                ended = true;
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        assert!(ended, "retry session should finalise");
        let snapshot = custody.terminal_resources();
        assert_eq!(snapshot.status(), crate::TerminalResourceStatus::Complete);
        assert_eq!(snapshot.spawned_attempts(), 2);
        assert_eq!(snapshot.observed_attempts(), 2);
        assert!(snapshot.known_user_cpu_micros().is_some());
        assert!(snapshot.known_system_cpu_micros().is_some());
        assert!(snapshot.known_max_rss_bytes().is_some());
        assert_eq!(runtime.live_count(), 0);
        assert!(!runtime.session_is_active(&session.id));
        let _ = fs::remove_dir_all(root);
    }

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn kill_during_pidless_retry_backoff_cancels_without_respawn() {
        use ab_store::{SessionFilter, SqliteStore, StateStore as _};

        let root = unique_temp_dir("ab-opencode-cancel-backoff");
        fs::create_dir_all(&root).expect("mkdir root");
        let binary = root.join("fake-opencode");
        fs::write(
            &binary,
            r#"#!/bin/sh
state="$(dirname "$0")/attempts"
attempt=0
if [ -f "$state" ]; then attempt="$(cat "$state")"; fi
attempt=$((attempt + 1))
printf '%s' "$attempt" > "$state"
printf '%s\n' 'ProviderModelNotFoundError'
"#,
        )
        .expect("write fake opencode");
        let mut permissions = fs::metadata(&binary).expect("metadata").permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(&binary, permissions).expect("chmod");
        let store = Arc::new(
            SqliteStore::open(&root.join("state.db"))
                .await
                .expect("open store"),
        );
        let runtime = OpenCodeFamilyRuntime::opencode()
            .with_binary(binary.display().to_string())
            .with_retry_attempts_for_test(2)
            .with_retry_backoff_for_test(Duration::from_millis(500))
            .with_store(store.clone());
        let session = runtime
            .spawn(SpawnConfig {
                cwd: root.display().to_string(),
                initial_prompt: Some("cancel probe".into()),
                ..Default::default()
            })
            .await
            .expect("spawn cancel probe");
        let custody = session.process_custody().expect("custody");
        let in_backoff = wait_for(2_000, 10, || runtime.retry_backoff_active(&session.id)).await;
        assert!(in_backoff, "session should enter PID-less retry backoff");
        assert!(runtime.pid_for(&session.id).is_none());

        runtime
            .kill(&session.id)
            .await
            .expect("PID-less backoff cancellation is successful");

        let filter = SessionFilter {
            runtime_id: Some("opencode".into()),
            cwd_prefix: Some(root.display().to_string()),
            ..SessionFilter::default()
        };
        let mut finalised = None;
        for _ in 0..100 {
            let rows = store.list_sessions(&filter, 10).await.expect("list");
            if rows.first().is_some_and(|row| row.ended_at.is_some()) {
                finalised = rows.into_iter().next();
                break;
            }
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
        let finalised = finalised.expect("cancelled retry should finalise promptly");
        assert_eq!(finalised.exit_code, Some(SYNTHETIC_CANCEL_EXIT_CODE));
        assert!(finalised
            .stderr
            .as_deref()
            .is_some_and(|text| text.contains("synthetic exit code 143")));
        assert!(!runtime.session_is_active(&session.id));
        let resources = custody.terminal_resources();
        assert_eq!(resources.status(), crate::TerminalResourceStatus::Complete);
        assert_eq!(resources.spawned_attempts(), 1);
        assert_eq!(resources.observed_attempts(), 1);

        // Wait beyond the configured backoff: cancellation must have broken
        // the loop, not merely made the session look terminal early.
        tokio::time::sleep(Duration::from_millis(700)).await;
        assert_eq!(
            fs::read_to_string(root.join("attempts")).expect("attempt count"),
            "1"
        );
        assert_eq!(runtime.live_count(), 0);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn build_remote_run_cmd_minimal() {
        let cmd = build_remote_run_cmd(
            "$HOME/.kilo/bin/kilo",
            "--auto",
            "/home/pallasting/ab-kilo",
            None,
            "do the thing",
            &HashMap::new(),
        );
        assert_eq!(
            cmd,
            "cd '/home/pallasting/ab-kilo' && \"$HOME/.kilo/bin/kilo\" run --auto 'do the thing'"
        );
    }

    #[test]
    fn build_remote_run_cmd_with_model_and_env_is_injection_safe() {
        let mut env = HashMap::new();
        env.insert("AB_FLAG".to_string(), "v1".to_string());
        let cmd = build_remote_run_cmd(
            "$HOME/.kilo/bin/kilo",
            "--auto",
            "/w",
            Some("kilo/kilo-auto/free"),
            "; rm -rf / #",
            &env,
        );
        // The malicious prompt is inert: it is single-quoted into one positional
        // arg, and the env assignment binds only to this command.
        assert_eq!(
            cmd,
            "cd '/w' && AB_FLAG='v1' \"$HOME/.kilo/bin/kilo\" run --auto \
             --model 'kilo/kilo-auto/free' '; rm -rf / #'"
        );
    }

    #[test]
    fn build_remote_run_cmd_skips_unsafe_env_keys() {
        let mut env = HashMap::new();
        env.insert("BAD KEY".to_string(), "x".to_string()); // space → skipped
        env.insert("1leading".to_string(), "x".to_string()); // digit-led → skipped
        let cmd = build_remote_run_cmd("kilo", "--auto", "", None, "p", &env);
        assert_eq!(cmd, "\"kilo\" run --auto 'p'");
    }

    #[test]
    fn is_provider_miss_detects_free_pool_errors() {
        assert!(is_provider_miss(
            "ProviderModelNotFoundError: ProviderModelNotFoundError"
        ));
        assert!(is_provider_miss(
            "\u{1b}[91mError: Model not found: kilo/kilo-auto/free.\n"
        ));
        // a normal successful result must not look like a miss
        assert!(!is_provider_miss("4784d188c9f3\n"));
        assert!(!is_provider_miss(""));
    }

    #[test]
    fn is_auth_failure_detects_success_exit_token_refresh_error() {
        assert!(is_auth_failure("Error: Token refresh failed: 401"));
        assert!(!is_auth_failure("authentication failed for provider"));
        assert!(!is_auth_failure("request returned Unauthorized"));
        assert!(!is_auth_failure("completed successfully"));
        assert!(!is_auth_failure("ProviderModelNotFoundError"));
    }

    #[test]
    fn is_payment_failure_detects_missing_billing_method_only() {
        assert!(is_payment_failure("Error: No payment method."));
        assert!(is_payment_failure("\u{1b}[91mError: No payment method.\n"));
        assert!(!is_payment_failure("payment completed successfully"));
        assert!(!is_payment_failure("No payment method."));
        assert!(!is_payment_failure("Token refresh failed: 401"));
    }

    #[test]
    fn corrected_exit_code_marks_auth_failure_even_when_child_exits_zero() {
        assert_eq!(
            corrected_exit_code(Some(0), "", "Error: Token refresh failed: 401"),
            Some(1)
        );
        assert_eq!(corrected_exit_code(Some(7), "completed", ""), Some(7));
        assert_eq!(
            corrected_exit_code(Some(7), "", "Error: Token refresh failed: 401"),
            Some(7)
        );
        assert_eq!(
            corrected_exit_code(Some(0), "", "Error: No payment method."),
            Some(1)
        );
        assert_eq!(
            corrected_exit_code(Some(0), "No payment method.", ""),
            Some(0)
        );
        assert_eq!(corrected_exit_code(None, "completed", ""), None);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn auth_refresh_failure_overrides_zero_in_persisted_session() {
        use ab_store::{SessionFilter, SqliteStore, StateStore as _};
        use std::sync::Arc;

        let root = unique_temp_dir("ab-opencode-auth-failure");
        fs::create_dir_all(&root).expect("mkdir root");
        let binary = root.join("fake-opencode");
        fs::write(
            &binary,
            "#!/bin/sh\nprintf '%s\\n' 'Error: Token refresh failed: 401' >&2\nexit 0\n",
        )
        .expect("write fake opencode");
        let mut perms = fs::metadata(&binary).expect("metadata").permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&binary, perms).expect("chmod fake opencode");
        let store = Arc::new(
            SqliteStore::open(&root.join("state.db"))
                .await
                .expect("open store"),
        );
        let runtime = OpenCodeFamilyRuntime::opencode()
            .with_binary(binary.display().to_string())
            .with_store(store.clone());

        runtime
            .spawn(SpawnConfig {
                cwd: root.display().to_string(),
                initial_prompt: Some("hello".to_string()),
                ..Default::default()
            })
            .await
            .expect("spawn fake opencode");

        let mut finalised = false;
        let mut last_rows = Vec::new();
        for _ in 0..80 {
            let rows = store
                .list_sessions(
                    &SessionFilter {
                        runtime_id: Some("opencode".to_string()),
                        cwd_prefix: Some(root.display().to_string()),
                        ..SessionFilter::default()
                    },
                    10,
                )
                .await
                .expect("list sessions while waiting");
            last_rows = rows.clone();
            if rows
                .first()
                .is_some_and(|row| row.ended_at.is_some() && row.exit_code == Some(1))
            {
                finalised = true;
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        assert!(
            finalised,
            "auth refresh failure must persist as exit_code=1: {last_rows:?}"
        );

        let rows = store
            .list_sessions(
                &SessionFilter {
                    runtime_id: Some("opencode".to_string()),
                    cwd_prefix: Some(root.display().to_string()),
                    ..SessionFilter::default()
                },
                10,
            )
            .await
            .expect("list sessions");
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].exit_code, Some(1));
        assert!(rows[0]
            .stderr
            .as_deref()
            .unwrap_or_default()
            .contains("Token refresh failed: 401"));
        let _ = fs::remove_dir_all(root);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn payment_failure_overrides_zero_in_persisted_session() {
        use ab_store::{SessionFilter, SqliteStore, StateStore as _};
        use std::sync::Arc;

        let root = unique_temp_dir("ab-opencode-payment-failure");
        fs::create_dir_all(&root).expect("mkdir root");
        let binary = root.join("fake-opencode");
        fs::write(
            &binary,
            "#!/bin/sh\nprintf '%s\\n' 'Error: No payment method.' >&2\nexit 0\n",
        )
        .expect("write fake opencode");
        let mut perms = fs::metadata(&binary).expect("metadata").permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&binary, perms).expect("chmod fake opencode");
        let store = Arc::new(
            SqliteStore::open(&root.join("state.db"))
                .await
                .expect("open store"),
        );
        let runtime = OpenCodeFamilyRuntime::opencode()
            .with_binary(binary.display().to_string())
            .with_store(store.clone());

        runtime
            .spawn(SpawnConfig {
                cwd: root.display().to_string(),
                initial_prompt: Some("hello".to_string()),
                ..Default::default()
            })
            .await
            .expect("spawn fake opencode");

        let mut finalised = false;
        for _ in 0..80 {
            let rows = store
                .list_sessions(
                    &SessionFilter {
                        runtime_id: Some("opencode".to_string()),
                        cwd_prefix: Some(root.display().to_string()),
                        ..SessionFilter::default()
                    },
                    10,
                )
                .await
                .expect("list sessions while waiting");
            if rows
                .first()
                .is_some_and(|row| row.ended_at.is_some() && row.exit_code == Some(1))
            {
                finalised = true;
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        assert!(finalised, "payment failure must persist as exit_code=1");
        let _ = fs::remove_dir_all(root);
    }

    #[tokio::test]
    async fn spawn_failure_finalises_persisted_session() {
        use ab_store::{SessionFilter, SqliteStore, StateStore as _};
        use std::sync::Arc;

        let root = unique_temp_dir("ab-kilo-spawn-failure");
        fs::create_dir_all(&root).expect("mkdir root");
        let store = Arc::new(
            SqliteStore::open(&root.join("state.db"))
                .await
                .expect("open store"),
        );
        let runtime = OpenCodeFamilyRuntime::kilo()
            .with_binary(root.join("missing-kilo").display().to_string())
            .with_store(store.clone());

        let err = runtime
            .spawn(SpawnConfig {
                cwd: root.display().to_string(),
                env: HashMap::new(),
                initial_prompt: Some("hello".to_string()),
                model: None,
                node: None,
                user: None,
                interactive: false,
            })
            .await
            .expect_err("missing binary should fail");

        assert!(format!("{err}").contains("spawn kilo"));
        let rows = store
            .list_sessions(
                &SessionFilter {
                    runtime_id: Some("kilo".to_string()),
                    cwd_prefix: Some(root.display().to_string()),
                    ..SessionFilter::default()
                },
                10,
            )
            .await
            .expect("list sessions");
        assert_eq!(rows.len(), 1);
        assert!(
            rows[0].ended_at.is_some(),
            "failed spawn must not leave a fake running session"
        );
        assert_eq!(rows[0].exit_code, Some(127));
        assert!(rows[0]
            .stderr
            .as_deref()
            .unwrap_or_default()
            .contains("spawn kilo"));
        let _ = fs::remove_dir_all(root);
    }

    async fn wait_for<F: FnMut() -> bool>(total_ms: u64, step_ms: u64, mut predicate: F) -> bool {
        let mut waited = 0u64;
        while waited <= total_ms {
            if predicate() {
                return true;
            }
            tokio::time::sleep(std::time::Duration::from_millis(step_ms)).await;
            waited += step_ms;
        }
        predicate()
    }

    #[tokio::test]
    async fn interactive_session_multi_turn_round_trips() {
        // `/bin/cat` is a deterministic stand-in for the kilo/opencode TUI: it
        // stays alive and echoes each submitted line back through the PTY. This
        // proves the PTY plumbing; the real-binary submit key is covered by the
        // ignored `kilo_real_interactive` integration test.
        let rt = OpenCodeFamilyRuntime::kilo().with_binary("/bin/cat");
        let sess = rt
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                interactive: true,
                ..Default::default()
            })
            .await
            .expect("spawn interactive");
        assert_eq!(rt.interactive_count(), 1);
        assert!(
            rt.pid_for(&sess.id).is_some(),
            "interactive session should expose a pid"
        );

        rt.send_input(&sess.id, "alpha-one").await.expect("turn 1");
        let ok1 = wait_for(2000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("alpha-one"))
                .unwrap_or(false)
        })
        .await;
        assert!(ok1, "turn 1 should echo through the PTY");

        // A second turn proves the session stayed alive (not fire-and-forget).
        rt.send_input(&sess.id, "beta-two").await.expect("turn 2");
        let ok2 = wait_for(2000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("beta-two"))
                .unwrap_or(false)
        })
        .await;
        assert!(ok2, "turn 2 should echo — proves multi-turn interactive");

        rt.kill(&sess.id).await.expect("kill");
    }

    #[tokio::test]
    async fn trait_read_interactive_output_surfaces_live_buffer() {
        // The MCP `agent_session_output` tool reads through `dyn AgentRuntime`,
        // so the trait method (not just the inherent one) must surface the live
        // PTY buffer. Guards the read side of the interactive contract.
        let rt = OpenCodeFamilyRuntime::kilo().with_binary("/bin/cat");
        let dynrt: &dyn AgentRuntime = &rt;
        let sess = dynrt
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                interactive: true,
                ..Default::default()
            })
            .await
            .expect("spawn interactive");
        dynrt
            .send_input(&sess.id, "gamma-three")
            .await
            .expect("turn");
        let ok = wait_for(2000, 25, || {
            dynrt
                .read_interactive_output(&sess.id)
                .map(|o| o.contains("gamma-three"))
                .unwrap_or(false)
        })
        .await;
        assert!(
            ok,
            "trait-dispatched read_interactive_output should surface the live PTY buffer"
        );
        // An unknown session id reads as None through the trait, never panics.
        assert!(
            dynrt
                .read_interactive_output(&SessionId::from_raw("ses-does-not-exist"))
                .is_none(),
            "unknown session should read as None"
        );
        dynrt.kill(&sess.id).await.expect("kill");
    }

    #[tokio::test]
    async fn interactive_initial_prompt_is_submitted_as_first_turn() {
        let rt = OpenCodeFamilyRuntime::kilo().with_binary("/bin/cat");
        let sess = rt
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                interactive: true,
                initial_prompt: Some("seed-prompt".into()),
                ..Default::default()
            })
            .await
            .expect("spawn interactive");
        let ok = wait_for(2000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("seed-prompt"))
                .unwrap_or(false)
        })
        .await;
        assert!(
            ok,
            "initial_prompt should be typed + submitted as the first turn"
        );
        rt.kill(&sess.id).await.expect("kill");
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn interactive_initial_prompt_waits_for_tui_boot_settle() {
        let rt = OpenCodeFamilyRuntime::kilo()
            .with_binary("/bin/bash")
            .with_interactive_args([
                "-lc",
                "while IFS= read -r -t 0.2 _line; do :; done; printf 'READY\\n'; exec cat",
            ]);
        let sess = rt
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                interactive: true,
                initial_prompt: Some("boot-settle-marker".into()),
                ..Default::default()
            })
            .await
            .expect("spawn delayed-ready stand-in");

        let ready = wait_for(3000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("READY"))
                .unwrap_or(false)
        })
        .await;
        assert!(ready, "stand-in should reach its post-drain READY state");

        let submitted_after_ready = wait_for(5000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("boot-settle-marker"))
                .unwrap_or(false)
        })
        .await;
        assert!(
            submitted_after_ready,
            "initial_prompt should be submitted after the TUI boot settle; \
             an immediate write would be drained before READY and never echoed"
        );
        rt.kill(&sess.id).await.expect("kill");
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn interactive_args_are_passed_to_pty_child() {
        let rt = OpenCodeFamilyRuntime::kilo()
            .with_binary("/bin/sh")
            .with_interactive_args(["-c", "printf 'ARGV:%s\\n' \"$1\"; cat", "sh", "flag-one"]);
        let sess = rt
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                interactive: true,
                ..Default::default()
            })
            .await
            .expect("spawn interactive shell");

        let saw_arg = wait_for(2000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("ARGV:flag-one"))
                .unwrap_or(false)
        })
        .await;
        assert!(saw_arg, "interactive args should reach the PTY child");

        rt.send_input(&sess.id, "still-live")
            .await
            .expect("turn after argv print");
        let still_live = wait_for(2000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("still-live"))
                .unwrap_or(false)
        })
        .await;
        assert!(
            still_live,
            "child should remain interactive after startup args"
        );

        rt.kill(&sess.id).await.expect("kill");
    }

    #[tokio::test]
    async fn send_input_rejected_without_interactive_session() {
        // One-shot sessions (and unknown ids) must reject input — only live
        // PTY sessions accept it.
        let rt = OpenCodeFamilyRuntime::kilo().with_binary("/bin/cat");
        let err = rt
            .send_input(&SessionId::new(), "nope")
            .await
            .expect_err("send_input must fail without a live interactive session");
        assert!(matches!(err, Error::InvalidArgument(_)));
    }

    #[tokio::test]
    async fn kill_unknown_session_errors() {
        let rt = OpenCodeFamilyRuntime::kilo().with_binary("/bin/cat");
        let err = rt
            .kill(&SessionId::new())
            .await
            .expect_err("killing an unknown session must error");
        assert!(matches!(err, Error::NotFound(_)));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn enter_profile_submits_a_real_line_not_just_terminal_echo() {
        // GUARD for the submit-key choice (SubmitProfile::ENTER). A plain
        // `/bin/cat` stand-in cannot tell ENTER from KITTY_ENTER: the PTY echoes
        // typed text either way, so `output.contains(text)` passes even when the
        // turn never submits. Here `stty -echo` turns terminal echo OFF, so the
        // marker can only reach the output if the submit key actually completed a
        // line that `cat` read back. A bare CR (ENTER) is mapped to NL by the tty
        // (ICRNL) and submits; a Kitty CSI-u Enter (\x1b[13u) carries no newline,
        // so the line never completes and the marker never appears. This test
        // therefore FAILS if the family is ever mis-wired to KITTY_ENTER — the one
        // guard the echoing /bin/cat tests cannot provide.
        let rt = OpenCodeFamilyRuntime::kilo()
            .with_binary("/bin/sh")
            .with_interactive_args(["-c", "stty -echo; printf 'READY\\n'; exec cat", "sh"]);
        let sess = rt
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                interactive: true,
                ..Default::default()
            })
            .await
            .expect("spawn no-echo stand-in");
        // READY proves `stty -echo` has been applied before we submit.
        let ready = wait_for(3000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("READY"))
                .unwrap_or(false)
        })
        .await;
        assert!(
            ready,
            "stand-in should signal READY (echo disabled, cat live)"
        );

        rt.send_input(&sess.id, "submit-marker-xyz")
            .await
            .expect("turn");
        let submitted = wait_for(3000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("submit-marker-xyz"))
                .unwrap_or(false)
        })
        .await;
        assert!(
            submitted,
            "ENTER must submit a full line the no-echo cat reads back; a wrong \
             profile (e.g. KITTY_ENTER) would never complete the line"
        );
        rt.kill(&sess.id).await.expect("kill");
    }

    #[tokio::test]
    async fn interactive_session_persists_and_finalises_in_store() {
        use ab_store::{SessionFilter, SqliteStore, StateStore as _};

        let root = unique_temp_dir("ab-kilo-interactive-store");
        fs::create_dir_all(&root).expect("mkdir root");
        let store = Arc::new(
            SqliteStore::open(&root.join("state.db"))
                .await
                .expect("open store"),
        );
        let filter = || SessionFilter {
            runtime_id: Some("kilo".to_string()),
            cwd_prefix: Some(root.display().to_string()),
            ..SessionFilter::default()
        };
        let rt = OpenCodeFamilyRuntime::kilo()
            .with_binary("/bin/cat")
            .with_store(store.clone());
        let sess = rt
            .spawn(SpawnConfig {
                cwd: root.display().to_string(),
                interactive: true,
                ..Default::default()
            })
            .await
            .expect("spawn interactive");

        // save_session(initial) ran at spawn: exactly one row, not yet ended.
        let running = store.list_sessions(&filter(), 10).await.expect("list");
        assert_eq!(
            running.len(),
            1,
            "interactive spawn must persist a session row"
        );
        assert!(
            running[0].ended_at.is_none(),
            "live interactive session must not be pre-finalised"
        );

        // kill → PTY EOF → finalise_session on exit (asserts the close-the-loop
        // bookkeeping the echo-only tests never touch).
        rt.kill(&sess.id).await.expect("kill");
        let mut finalised = false;
        for _ in 0..80 {
            let rows = store.list_sessions(&filter(), 10).await.expect("list");
            if rows.len() == 1 && rows[0].ended_at.is_some() {
                finalised = true;
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(50)).await;
        }
        assert!(
            finalised,
            "interactive session must be finalised (ended_at set) on PTY exit"
        );
        let _ = fs::remove_dir_all(root);
    }

    fn unique_temp_dir(prefix: &str) -> std::path::PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("time")
            .as_nanos();
        std::env::temp_dir().join(format!("{prefix}-{}-{nanos}", std::process::id()))
    }

    fn write_executable(path: &Path) {
        fs::create_dir_all(path.parent().expect("parent")).expect("mkdir");
        fs::write(path, "#!/usr/bin/env sh\nexit 0\n").expect("write");
        #[cfg(unix)]
        {
            let mut perms = fs::metadata(path).expect("metadata").permissions();
            perms.set_mode(0o755);
            fs::set_permissions(path, perms).expect("chmod");
        }
    }
}
