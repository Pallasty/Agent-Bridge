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
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::process::Command;
use tracing::{info, warn};

use crate::{AgentCapabilities, AgentRuntime, AgentSession, SpawnConfig};

#[derive(Clone)]
pub struct OpenCodeFamilyRuntime {
    binary: String,
    runtime_id: &'static str,
    default_model: Option<String>,
    auto_approve_flag: &'static str,
    store: Option<Arc<dyn StateStore>>,
    children: Arc<DashMap<String, u32>>,
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
            store: None,
            children: Arc::new(DashMap::new()),
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
            store: None,
            children: Arc::new(DashMap::new()),
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

    /// Number of in-flight sessions (testing / observability).
    pub fn live_count(&self) -> usize {
        self.children.len()
    }
}

fn env_nonempty(key: &str) -> Option<String> {
    std::env::var(key)
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
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

#[async_trait]
impl AgentRuntime for OpenCodeFamilyRuntime {
    fn id(&self) -> &str {
        self.runtime_id
    }

    async fn spawn(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        let prompt = cfg.initial_prompt.clone().unwrap_or_default();
        if prompt.is_empty() {
            return Err(Error::InvalidArgument(format!(
                "{}: 'initial_prompt' is required for one-shot spawn",
                self.runtime_id
            )));
        }
        let model = cfg.model.clone().or_else(|| self.default_model.clone());

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
            };
            if let Err(e) = store.save_session(&initial).await {
                warn!(session = %session_id, error = %e, "store: save_session failed");
            }
        }

        let mut cmd = Command::new(&self.binary);
        cmd.arg("run").arg(self.auto_approve_flag);
        if let Some(m) = &model {
            cmd.arg("--model").arg(m);
        }
        // The prompt comes last as a positional argument so any preceding
        // flag values (model strings, etc.) can't shadow it.
        cmd.arg(&prompt);
        cmd.current_dir(&cwd)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        apply_env(&mut cmd, &cfg.env);

        let child = match cmd.spawn() {
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
        if pid != 0 {
            self.children.insert(session_id.as_str().to_string(), pid);
        }
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
        tokio::spawn(async move {
            let out = child.wait_with_output().await;
            children_bg.remove(sid_bg.as_str());
            let ended_at = now_secs();
            match out {
                Ok(o) => {
                    let stdout = String::from_utf8_lossy(&o.stdout).into_owned();
                    let stderr = String::from_utf8_lossy(&o.stderr).into_owned();
                    info!(
                        session = %sid_bg,
                        runtime = %runtime_id,
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
                    if let Some(store) = store_bg {
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
                }
                Err(e) => {
                    warn!(
                        session = %sid_bg,
                        runtime = %runtime_id,
                        error = %e,
                        "wait failed"
                    );
                    if let Some(store) = store_bg {
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
                }
            }
        });

        Ok(AgentSession {
            id: session_id,
            runtime_id: self.runtime_id.into(),
            cwd,
        })
    }

    async fn send_input(&self, _session: &SessionId, _text: &str) -> Result<()> {
        Err(Error::InvalidArgument(format!(
            "{}: send_input requires interactive (PTY) mode, not yet supported. \
             Use spawn() with initial_prompt for one-shot invocations.",
            self.runtime_id
        )))
    }

    async fn kill(&self, session: &SessionId) -> Result<()> {
        let pid = match self.children.get(session.as_str()) {
            Some(p) => *p,
            None => {
                return Err(Error::NotFound(format!(
                    "no live child for session {session} (already finished or unknown)"
                )));
            }
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
        self.children.get(session.as_str()).map(|kv| *kv)
    }

    async fn capabilities(&self) -> AgentCapabilities {
        AgentCapabilities {
            supports_mcp: true,
            supports_teams: false,
            supports_thinking: false,
        }
    }
}

fn apply_env(cmd: &mut Command, env: &HashMap<String, String>) {
    for (k, v) in env {
        cmd.env(k, v);
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
