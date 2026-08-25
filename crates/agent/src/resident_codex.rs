//! A bounded, one-shot Codex cognition provider for a resident Agent-Bridge subject.
//!
//! This is deliberately separate from [`crate::CodexRuntime`].  The ordinary
//! runtime represents a user-launched coding-agent session and inherits the
//! user's execution configuration.  A resident cognitive episode instead has
//! a much narrower contract: one process, prompt over stdin, read-only sandbox,
//! ephemeral rollout, structured final output, a hard deadline, and no action
//! authority.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::ffi::OsString;
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::fd::AsRawFd;
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::{Duration, Instant};
use tempfile::Builder as TempDirBuilder;
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWriteExt};
use tokio::process::{Child, Command};

pub const RESIDENT_CODEX_RECEIPT_SCHEMA_V0: &str =
    "agent_bridge.resident_codex_execution_receipt.v0";
pub const RESIDENT_CODEX_RECEIPT_SCHEMA_V1: &str =
    "agent_bridge.resident_codex_execution_receipt.v1";
pub const RESIDENT_CODEX_NATIVE_SHA256_V0: &str =
    "73dc5888888f411c1f0fa7b81d866e721dcc86b527ce8e3b2cf4708661e823ba";
const RESIDENT_BWRAP_BINARY: &str = "/usr/bin/bwrap";
const SANDBOX_PROVIDER_PATH: &str = "/opt/agent-bridge/codex";
const SANDBOX_WORKSPACE_PATH: &str = "/workspace";
const SANDBOX_OUTPUT_PATH: &str = "/output";
const SANDBOX_HOME_PATH: &str = "/home/resident";
const SANDBOX_CODEX_HOME_PATH: &str = "/home/resident/.codex";
const AUTH_MAX_BYTES: u64 = 1_048_576;
pub const DEFAULT_PROMPT_MAX_BYTES: usize = 65_536;
pub const DEFAULT_SCHEMA_MAX_BYTES: usize = 65_536;
pub const DEFAULT_FINAL_MAX_BYTES: usize = 32_768;
pub const DEFAULT_STDOUT_MAX_BYTES: usize = 1_048_576;
pub const DEFAULT_STDERR_MAX_BYTES: usize = 65_536;
pub const MAX_DEADLINE: Duration = Duration::from_secs(120);
pub const RESIDENT_DISABLED_PROVIDER_FEATURES: &[&str] = &[
    "hooks",
    "shell_tool",
    "shell_snapshot",
    "unified_exec",
    "code_mode",
    "code_mode_only",
    "code_mode_host",
    "js_repl",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "in_app_browser",
    "computer_use",
    "image_generation",
    "view_image",
    "apps",
    "plugins",
    "remote_plugin",
    "plugin_sharing",
    "recommended_plugins",
    "enable_mcp_apps",
    "mcp_2026_07_28",
    "auth_elicitation",
    "tool_call_mcp_elicitation",
    "skill_env_var_dependency_prompt",
    "skill_mcp_dependency_install",
    "skill_search",
    "tool_suggest",
    "workspace_dependencies",
    "request_permissions_tool",
    "external_agent_memory_import",
    "memories",
    "goals",
    "guardian_approval",
    "in_app_chat",
    "in_app_dictation",
    "in_app_updates",
    "collaboration_modes",
    "steer",
    "multi_agent",
    "multi_agent_v2",
];

#[derive(Debug, thiserror::Error)]
pub enum ResidentCodexError {
    #[error("resident_codex_invalid_configuration:{0}")]
    InvalidConfiguration(&'static str),
    #[error("resident_codex_prompt_too_large")]
    PromptTooLarge,
    #[error("resident_codex_schema_too_large")]
    SchemaTooLarge,
    #[error("resident_codex_schema_invalid")]
    SchemaInvalid,
    #[error("resident_codex_lock_unavailable")]
    LockUnavailable,
    #[error("resident_codex_busy")]
    Busy,
    #[error("resident_codex_temporary_workspace_failed")]
    TemporaryWorkspaceFailed,
    #[error("resident_codex_provider_content_pin_failed")]
    ProviderContentPinFailed,
    #[error("resident_codex_provider_content_hash_mismatch")]
    ProviderContentHashMismatch,
    #[error("resident_codex_provider_not_native")]
    ProviderNotNative,
    #[error("resident_codex_authentication_snapshot_failed")]
    AuthenticationSnapshotFailed,
    #[error("resident_codex_spawn_failed")]
    SpawnFailed,
    #[error("resident_codex_stdin_failed")]
    StdinFailed,
    #[error("resident_codex_stdout_limit_exceeded")]
    StdoutLimitExceeded,
    #[error("resident_codex_stderr_limit_exceeded")]
    StderrLimitExceeded,
    #[error("resident_codex_wait_failed")]
    WaitFailed,
    #[error("resident_codex_deadline_exceeded")]
    DeadlineExceeded,
    #[error("resident_codex_process_failed:exit_code={exit_code:?}")]
    ProcessFailed { exit_code: Option<i32> },
    #[error("resident_codex_provider_event_stream_invalid")]
    ProviderEventStreamInvalid,
    #[error("resident_codex_provider_tool_event_observed")]
    ProviderToolEventObserved,
    #[error("resident_codex_final_missing")]
    FinalMissing,
    #[error("resident_codex_final_too_large")]
    FinalTooLarge,
    #[error("resident_codex_final_invalid_json")]
    FinalInvalidJson,
    #[error("resident_codex_cleanup_failed")]
    CleanupFailed,
}

#[derive(Debug, Clone)]
pub struct ResidentCodexBrokerConfig {
    pub codex_binary: PathBuf,
    pub expected_codex_sha256: String,
    pub lock_path: PathBuf,
    pub deadline: Duration,
    pub termination_grace: Duration,
    pub prompt_max_bytes: usize,
    pub schema_max_bytes: usize,
    pub final_max_bytes: usize,
    pub stdout_max_bytes: usize,
    pub stderr_max_bytes: usize,
}

impl ResidentCodexBrokerConfig {
    pub fn new(
        codex_binary: PathBuf,
        expected_codex_sha256: String,
        lock_path: PathBuf,
        deadline: Duration,
    ) -> Self {
        Self {
            codex_binary,
            expected_codex_sha256,
            lock_path,
            deadline,
            termination_grace: Duration::from_secs(2),
            prompt_max_bytes: DEFAULT_PROMPT_MAX_BYTES,
            schema_max_bytes: DEFAULT_SCHEMA_MAX_BYTES,
            final_max_bytes: DEFAULT_FINAL_MAX_BYTES,
            stdout_max_bytes: DEFAULT_STDOUT_MAX_BYTES,
            stderr_max_bytes: DEFAULT_STDERR_MAX_BYTES,
        }
    }

    fn validate(&self) -> Result<(), ResidentCodexError> {
        if !self.codex_binary.is_absolute() {
            return Err(ResidentCodexError::InvalidConfiguration("codex_binary"));
        }
        if self.expected_codex_sha256.len() != 64
            || !self
                .expected_codex_sha256
                .bytes()
                .all(|byte| byte.is_ascii_digit() || matches!(byte, b'a'..=b'f'))
        {
            return Err(ResidentCodexError::InvalidConfiguration(
                "expected_codex_sha256",
            ));
        }
        if !self.lock_path.is_absolute() {
            return Err(ResidentCodexError::InvalidConfiguration("lock_path"));
        }
        if self.lock_path.parent().is_none_or(|path| !path.is_dir()) {
            return Err(ResidentCodexError::InvalidConfiguration(
                "lock_parent_missing",
            ));
        }
        if self.deadline.is_zero() || self.deadline > MAX_DEADLINE {
            return Err(ResidentCodexError::InvalidConfiguration("deadline"));
        }
        if self.termination_grace.is_zero()
            || self.prompt_max_bytes == 0
            || self.schema_max_bytes == 0
            || self.final_max_bytes == 0
            || self.stdout_max_bytes == 0
            || self.stderr_max_bytes == 0
        {
            return Err(ResidentCodexError::InvalidConfiguration("limits"));
        }
        Ok(())
    }
}

#[derive(Debug, Clone)]
pub struct ResidentCodexRequest {
    pub wake_id: String,
    pub cognitive_episode_id: String,
    pub resident_id: String,
    pub cwd: PathBuf,
    pub prompt: Vec<u8>,
    pub output_schema: Vec<u8>,
    pub model: Option<String>,
    pub reasoning_effort: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentCodexExecutionReceipt {
    pub schema_version: String,
    pub wake_id: String,
    pub cognitive_episode_id: String,
    pub resident_id: String,
    pub provider: String,
    pub requested_model: Option<String>,
    pub requested_reasoning_effort: Option<String>,
    pub sandbox_requested: String,
    pub approval_policy_requested: String,
    pub user_config_ignored: bool,
    pub ephemeral: bool,
    pub prompt_via_stdin: bool,
    pub output_schema_requested: bool,
    pub disabled_provider_features: Vec<String>,
    pub expected_provider_sha256: String,
    pub observed_provider_sha256: String,
    pub provider_content_pinned: bool,
    pub outer_host_filesystem: String,
    pub private_ephemeral_output_writable: bool,
    pub request_cwd_mounted: bool,
    pub privacy_boundary_required: bool,
    pub recoverable_failure_accepted: bool,
    pub external_mutation_authority: bool,
    pub provider_event_stream_audited: bool,
    pub provider_tool_events_observed: usize,
    pub provider_fail_closed_diagnostics_observed: usize,
    pub stdout_event_count: usize,
    pub executes_action: bool,
    pub grants_authority: bool,
    pub exit_code: Option<i32>,
    pub duration_ms: u64,
    pub prompt_sha256: String,
    pub output_schema_sha256: String,
    pub final_sha256: String,
    pub stdout_bytes: usize,
    pub stderr_bytes: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentCodexRun {
    pub final_json: Value,
    pub execution: ResidentCodexExecutionReceipt,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentCodexInvocationContract {
    pub provider: &'static str,
    pub subcommand: &'static str,
    pub ignores_user_config: bool,
    pub sandbox: &'static str,
    pub approval_policy: &'static str,
    pub ephemeral: bool,
    pub prompt_transport: &'static str,
    pub structured_output: bool,
    pub provider_tool_features_requested_disabled: bool,
    pub provider_content_pinned: bool,
    pub outer_host_filesystem: &'static str,
    pub private_ephemeral_output_writable: bool,
    pub request_cwd_mounted: bool,
    pub privacy_boundary_required: bool,
    pub recoverable_failure_accepted: bool,
    pub external_mutation_authority: bool,
    pub provider_event_stream_policy: &'static str,
    pub persists_session: bool,
    pub executes_action: bool,
    pub grants_authority: bool,
}

impl Default for ResidentCodexInvocationContract {
    fn default() -> Self {
        Self {
            provider: "codex_cli",
            subcommand: "exec",
            ignores_user_config: true,
            sandbox: "read_only",
            approval_policy: "never",
            ephemeral: true,
            prompt_transport: "stdin",
            structured_output: true,
            provider_tool_features_requested_disabled: true,
            provider_content_pinned: true,
            outer_host_filesystem: "read_only",
            private_ephemeral_output_writable: true,
            request_cwd_mounted: false,
            privacy_boundary_required: false,
            recoverable_failure_accepted: true,
            external_mutation_authority: false,
            provider_event_stream_policy: "fail_closed_on_tool_or_unknown_event",
            persists_session: false,
            executes_action: false,
            grants_authority: false,
        }
    }
}

#[derive(Debug, Clone)]
pub struct ResidentCodexBroker {
    config: ResidentCodexBrokerConfig,
}

impl ResidentCodexBroker {
    pub fn new(config: ResidentCodexBrokerConfig) -> Result<Self, ResidentCodexError> {
        config.validate()?;
        Ok(Self { config })
    }

    pub fn invocation_contract(&self) -> ResidentCodexInvocationContract {
        ResidentCodexInvocationContract::default()
    }

    pub async fn run(
        &self,
        request: ResidentCodexRequest,
    ) -> Result<ResidentCodexRun, ResidentCodexError> {
        self.validate_request(&request)?;
        // Pin before acquiring the subject lock or creating the episode
        // workspace. The configured path is only ever read; production never
        // executes it, a shebang, or anything resolved through PATH.
        let provider = pin_provider(
            &self.config.codex_binary,
            &self.config.expected_codex_sha256,
            true,
        )?;
        self.run_pinned(request, provider, ResidentLauncher::Bubblewrap)
            .await
    }

    /// Exercise the historical provider protocol with a deterministic fake.
    /// This exists only in this module's tests; production has no direct-launch
    /// branch and can execute only the native snapshot through `/usr/bin/bwrap`.
    #[cfg(test)]
    async fn run_unwrapped_fixture(
        &self,
        request: ResidentCodexRequest,
    ) -> Result<ResidentCodexRun, ResidentCodexError> {
        self.validate_request(&request)?;
        let provider = pin_provider(
            &self.config.codex_binary,
            &self.config.expected_codex_sha256,
            false,
        )?;
        self.run_pinned(request, provider, ResidentLauncher::DirectFixture)
            .await
    }

    async fn run_pinned(
        &self,
        request: ResidentCodexRequest,
        provider: PinnedProvider,
        launcher: ResidentLauncher,
    ) -> Result<ResidentCodexRun, ResidentCodexError> {
        let _lock = HostLock::acquire(&self.config.lock_path)?;
        #[cfg(test)]
        EPISODE_TEMP_ATTEMPTED.with(|attempted| attempted.set(true));
        let temporary = TempDirBuilder::new()
            .prefix("agent-bridge-resident-codex-")
            .tempdir()
            .map_err(|_| ResidentCodexError::TemporaryWorkspaceFailed)?;
        let output_directory = temporary.path().join("output");
        std::fs::create_dir(&output_directory)
            .map_err(|_| ResidentCodexError::TemporaryWorkspaceFailed)?;
        std::fs::set_permissions(&output_directory, std::fs::Permissions::from_mode(0o700))
            .map_err(|_| ResidentCodexError::TemporaryWorkspaceFailed)?;
        let schema_path = output_directory.join("intent.schema.json");
        let final_path = output_directory.join("final.json");
        write_private_new(&schema_path, &request.output_schema)?;
        write_private_new(&final_path, b"")?;

        let production_envelope = matches!(launcher, ResidentLauncher::Bubblewrap);
        let mut command = match launcher {
            ResidentLauncher::Bubblewrap => {
                let auth_snapshot = snapshot_auth_json(temporary.path())?;
                let mut command = Command::new(RESIDENT_BWRAP_BINARY);
                command
                    .args(self.bubblewrap_args(
                        &request,
                        provider.path(),
                        &auth_snapshot,
                        &output_directory,
                    ))
                    .current_dir("/");
                configure_outer_environment(&mut command);
                command
            }
            #[cfg(test)]
            ResidentLauncher::DirectFixture => {
                let mut command = Command::new(provider.path());
                command
                    .args(self.provider_args(&request, &schema_path, &final_path, &request.cwd))
                    .current_dir(&request.cwd);
                configure_fixture_environment(&mut command);
                command
            }
        };
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);
        configure_process_group(&mut command);

        let started = Instant::now();
        let mut child = command
            .spawn()
            .map_err(|_| ResidentCodexError::SpawnFailed)?;
        let child_pid = child.id().ok_or(ResidentCodexError::SpawnFailed)?;
        let mut group_guard = ProcessGroupGuard::new(child_pid);
        let mut stdin = child.stdin.take().ok_or(ResidentCodexError::SpawnFailed)?;
        let mut stdout = child.stdout.take().ok_or(ResidentCodexError::SpawnFailed)?;
        let mut stderr = child.stderr.take().ok_or(ResidentCodexError::SpawnFailed)?;

        let execution = async {
            let write_prompt = async {
                stdin
                    .write_all(&request.prompt)
                    .await
                    .map_err(|_| ResidentCodexError::StdinFailed)?;
                stdin
                    .shutdown()
                    .await
                    .map_err(|_| ResidentCodexError::StdinFailed)?;
                drop(stdin);
                Ok(())
            };
            let read_stdout = read_bounded(
                &mut stdout,
                self.config.stdout_max_bytes,
                ResidentCodexError::StdoutLimitExceeded,
            );
            let read_stderr = read_bounded(
                &mut stderr,
                self.config.stderr_max_bytes,
                ResidentCodexError::StderrLimitExceeded,
            );
            let wait = async {
                child
                    .wait()
                    .await
                    .map_err(|_| ResidentCodexError::WaitFailed)
            };
            tokio::try_join!(write_prompt, read_stdout, read_stderr, wait)
        };

        let ((), stdout, stderr, status) =
            match tokio::time::timeout(self.config.deadline, execution).await {
                Ok(Ok(output)) => output,
                Ok(Err(error)) => {
                    terminate_and_reap(&mut child, child_pid, self.config.termination_grace)
                        .await?;
                    return Err(error);
                }
                Err(_) => {
                    terminate_and_reap(&mut child, child_pid, self.config.termination_grace)
                        .await?;
                    return Err(ResidentCodexError::DeadlineExceeded);
                }
            };

        // A resident episode never owns a persistent helper.  Clean any
        // descendant that outlived a successful Codex leader before disarming
        // the cancellation guard.
        let _ = signal_group(child_pid, libc::SIGKILL);
        group_guard.disarm();
        if !status.success() {
            return Err(ResidentCodexError::ProcessFailed {
                exit_code: status.code(),
            });
        }
        let event_audit = audit_provider_event_stream(&stdout)?;

        let final_bytes = read_final_bounded(&final_path, self.config.final_max_bytes)?;
        let final_json: Value = serde_json::from_slice(&final_bytes)
            .map_err(|_| ResidentCodexError::FinalInvalidJson)?;
        if !final_json.is_object() {
            return Err(ResidentCodexError::FinalInvalidJson);
        }

        Ok(ResidentCodexRun {
            final_json,
            execution: ResidentCodexExecutionReceipt {
                schema_version: RESIDENT_CODEX_RECEIPT_SCHEMA_V1.to_string(),
                wake_id: request.wake_id,
                cognitive_episode_id: request.cognitive_episode_id,
                resident_id: request.resident_id,
                provider: "codex_cli".to_string(),
                requested_model: request.model,
                requested_reasoning_effort: request.reasoning_effort,
                sandbox_requested: "read_only".to_string(),
                approval_policy_requested: "never".to_string(),
                user_config_ignored: true,
                ephemeral: true,
                prompt_via_stdin: true,
                output_schema_requested: true,
                disabled_provider_features: RESIDENT_DISABLED_PROVIDER_FEATURES
                    .iter()
                    .map(|feature| (*feature).to_string())
                    .collect(),
                expected_provider_sha256: self.config.expected_codex_sha256.clone(),
                observed_provider_sha256: provider.observed_sha256.clone(),
                provider_content_pinned: true,
                outer_host_filesystem: if production_envelope {
                    "read_only".to_string()
                } else {
                    "test_fixture_unwrapped".to_string()
                },
                private_ephemeral_output_writable: true,
                request_cwd_mounted: !production_envelope,
                privacy_boundary_required: false,
                recoverable_failure_accepted: true,
                external_mutation_authority: false,
                provider_event_stream_audited: true,
                provider_tool_events_observed: 0,
                provider_fail_closed_diagnostics_observed: event_audit.fail_closed_diagnostics,
                stdout_event_count: event_audit.event_count,
                executes_action: false,
                grants_authority: false,
                exit_code: status.code(),
                duration_ms: started.elapsed().as_millis() as u64,
                prompt_sha256: sha256_hex(&request.prompt),
                output_schema_sha256: sha256_hex(&request.output_schema),
                final_sha256: sha256_hex(&final_bytes),
                stdout_bytes: stdout.len(),
                stderr_bytes: stderr.len(),
            },
        })
    }

    fn validate_request(&self, request: &ResidentCodexRequest) -> Result<(), ResidentCodexError> {
        if request.wake_id.trim().is_empty()
            || request.cognitive_episode_id.trim().is_empty()
            || request.resident_id.trim().is_empty()
        {
            return Err(ResidentCodexError::InvalidConfiguration("identity"));
        }
        if !request.cwd.is_absolute() || !request.cwd.is_dir() {
            return Err(ResidentCodexError::InvalidConfiguration("cwd"));
        }
        if request.prompt.is_empty() {
            return Err(ResidentCodexError::InvalidConfiguration("prompt"));
        }
        if request.prompt.len() > self.config.prompt_max_bytes {
            return Err(ResidentCodexError::PromptTooLarge);
        }
        if request.output_schema.len() > self.config.schema_max_bytes {
            return Err(ResidentCodexError::SchemaTooLarge);
        }
        let schema: Value = serde_json::from_slice(&request.output_schema)
            .map_err(|_| ResidentCodexError::SchemaInvalid)?;
        if !schema.is_object() {
            return Err(ResidentCodexError::SchemaInvalid);
        }
        if request.model.as_ref().is_some_and(|model| {
            model.trim().is_empty() || model.len() > 128 || model.chars().any(char::is_whitespace)
        }) {
            return Err(ResidentCodexError::InvalidConfiguration("model"));
        }
        if request
            .reasoning_effort
            .as_deref()
            .is_some_and(|effort| !matches!(effort, "low" | "medium"))
        {
            return Err(ResidentCodexError::InvalidConfiguration("reasoning_effort"));
        }
        Ok(())
    }

    fn provider_args(
        &self,
        request: &ResidentCodexRequest,
        schema_path: &Path,
        final_path: &Path,
        workspace_path: &Path,
    ) -> Vec<OsString> {
        let mut args = vec![
            OsString::from("exec"),
            OsString::from("--strict-config"),
            OsString::from("--ignore-user-config"),
            OsString::from("--ignore-rules"),
            OsString::from("--ephemeral"),
            OsString::from("--sandbox"),
            OsString::from("read-only"),
            OsString::from("-c"),
            OsString::from("approval_policy=\"never\""),
            OsString::from("-c"),
            OsString::from("web_search=\"disabled\""),
            OsString::from("--color"),
            OsString::from("never"),
            OsString::from("--skip-git-repo-check"),
            OsString::from("-C"),
            workspace_path.as_os_str().to_os_string(),
            OsString::from("--output-schema"),
            schema_path.as_os_str().to_os_string(),
            OsString::from("--output-last-message"),
            final_path.as_os_str().to_os_string(),
            OsString::from("--json"),
        ];
        for feature in RESIDENT_DISABLED_PROVIDER_FEATURES {
            args.push(OsString::from("--disable"));
            args.push(OsString::from(feature));
        }
        if let Some(model) = &request.model {
            args.push(OsString::from("--model"));
            args.push(OsString::from(model));
        }
        if let Some(effort) = &request.reasoning_effort {
            args.push(OsString::from("-c"));
            args.push(OsString::from(format!(
                "model_reasoning_effort=\"{effort}\""
            )));
        }
        args.push(OsString::from("-"));
        args
    }

    fn bubblewrap_args(
        &self,
        request: &ResidentCodexRequest,
        provider_snapshot: &Path,
        auth_snapshot: &Path,
        output_directory: &Path,
    ) -> Vec<OsString> {
        let mut args = vec![
            OsString::from("--die-with-parent"),
            OsString::from("--new-session"),
            OsString::from("--unshare-user"),
            OsString::from("--unshare-pid"),
            OsString::from("--unshare-ipc"),
            OsString::from("--unshare-uts"),
            OsString::from("--unshare-cgroup"),
            OsString::from("--hostname"),
            OsString::from("resident-cognition"),
            OsString::from("--cap-drop"),
            OsString::from("ALL"),
            OsString::from("--clearenv"),
            OsString::from("--setenv"),
            OsString::from("HOME"),
            OsString::from(SANDBOX_HOME_PATH),
            OsString::from("--setenv"),
            OsString::from("CODEX_HOME"),
            OsString::from(SANDBOX_CODEX_HOME_PATH),
            OsString::from("--setenv"),
            OsString::from("TMPDIR"),
            OsString::from("/tmp"),
            OsString::from("--setenv"),
            OsString::from("PATH"),
            OsString::from("/opt/agent-bridge"),
            OsString::from("--setenv"),
            OsString::from("LANG"),
            OsString::from("C.UTF-8"),
            OsString::from("--setenv"),
            OsString::from("NO_COLOR"),
            OsString::from("1"),
            OsString::from("--setenv"),
            OsString::from("SSL_CERT_DIR"),
            OsString::from("/etc/ssl/certs"),
        ];
        append_proxy_environment(&mut args);
        args.extend([
            OsString::from("--dev"),
            OsString::from("/dev"),
            OsString::from("--proc"),
            OsString::from("/proc"),
            OsString::from("--remount-ro"),
            OsString::from("/proc"),
            OsString::from("--tmpfs"),
            OsString::from("/tmp"),
            OsString::from("--tmpfs"),
            OsString::from("/run"),
            OsString::from("--tmpfs"),
            OsString::from("/home"),
            OsString::from("--dir"),
            OsString::from(SANDBOX_HOME_PATH),
            OsString::from("--dir"),
            OsString::from(SANDBOX_CODEX_HOME_PATH),
            OsString::from("--dir"),
            OsString::from(SANDBOX_WORKSPACE_PATH),
            OsString::from("--dir"),
            OsString::from("/opt"),
            OsString::from("--dir"),
            OsString::from("/opt/agent-bridge"),
            OsString::from("--dir"),
            OsString::from("/etc"),
            OsString::from("--dir"),
            OsString::from("/etc/ssl"),
            OsString::from("--ro-bind-try"),
            OsString::from("/etc/ssl/certs"),
            OsString::from("/etc/ssl/certs"),
            OsString::from("--ro-bind-try"),
            OsString::from("/etc/resolv.conf"),
            OsString::from("/etc/resolv.conf"),
            OsString::from("--ro-bind-try"),
            OsString::from("/etc/hosts"),
            OsString::from("/etc/hosts"),
            OsString::from("--ro-bind-try"),
            OsString::from("/etc/nsswitch.conf"),
            OsString::from("/etc/nsswitch.conf"),
            OsString::from("--ro-bind"),
            provider_snapshot.as_os_str().to_os_string(),
            OsString::from(SANDBOX_PROVIDER_PATH),
            OsString::from("--ro-bind"),
            auth_snapshot.as_os_str().to_os_string(),
            OsString::from(format!("{SANDBOX_CODEX_HOME_PATH}/auth.json")),
            OsString::from("--dir"),
            OsString::from(SANDBOX_OUTPUT_PATH),
            OsString::from("--bind"),
            output_directory.as_os_str().to_os_string(),
            OsString::from(SANDBOX_OUTPUT_PATH),
            OsString::from("--chdir"),
            OsString::from(SANDBOX_WORKSPACE_PATH),
            OsString::from("--"),
            OsString::from(SANDBOX_PROVIDER_PATH),
        ]);
        args.extend(self.provider_args(
            request,
            Path::new("/output/intent.schema.json"),
            Path::new("/output/final.json"),
            Path::new(SANDBOX_WORKSPACE_PATH),
        ));
        args
    }
}

#[cfg(test)]
std::thread_local! {
    static EPISODE_TEMP_ATTEMPTED: std::cell::Cell<bool> = const { std::cell::Cell::new(false) };
}

#[derive(Clone, Copy)]
enum ResidentLauncher {
    Bubblewrap,
    #[cfg(test)]
    DirectFixture,
}

struct PinnedProvider {
    _temporary: tempfile::TempDir,
    snapshot_path: PathBuf,
    observed_sha256: String,
}

impl PinnedProvider {
    fn path(&self) -> &Path {
        &self.snapshot_path
    }
}

fn pin_provider(
    source_path: &Path,
    expected_sha256: &str,
    require_native: bool,
) -> Result<PinnedProvider, ResidentCodexError> {
    const PROVIDER_MAX_BYTES: u64 = 536_870_912;

    let temporary = TempDirBuilder::new()
        .prefix("agent-bridge-resident-provider-pin-")
        .tempdir()
        .map_err(|_| ResidentCodexError::ProviderContentPinFailed)?;
    let snapshot_path = temporary.path().join("codex.native");
    let mut source = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(source_path)
        .map_err(|_| ResidentCodexError::ProviderContentPinFailed)?;
    let metadata = source
        .metadata()
        .map_err(|_| ResidentCodexError::ProviderContentPinFailed)?;
    if !metadata.is_file() || metadata.len() == 0 || metadata.len() > PROVIDER_MAX_BYTES {
        return Err(ResidentCodexError::ProviderContentPinFailed);
    }
    let mut snapshot = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o700)
        .open(&snapshot_path)
        .map_err(|_| ResidentCodexError::ProviderContentPinFailed)?;
    let mut digest = Sha256::new();
    let mut prefix = [0_u8; 4];
    let mut prefix_length = 0_usize;
    let mut copied = 0_u64;
    let mut chunk = [0_u8; 64 * 1024];
    loop {
        let count = source
            .read(&mut chunk)
            .map_err(|_| ResidentCodexError::ProviderContentPinFailed)?;
        if count == 0 {
            break;
        }
        copied = copied.saturating_add(count as u64);
        if copied > PROVIDER_MAX_BYTES {
            return Err(ResidentCodexError::ProviderContentPinFailed);
        }
        if prefix_length < prefix.len() {
            let prefix_count = (prefix.len() - prefix_length).min(count);
            prefix[prefix_length..prefix_length + prefix_count]
                .copy_from_slice(&chunk[..prefix_count]);
            prefix_length += prefix_count;
        }
        digest.update(&chunk[..count]);
        snapshot
            .write_all(&chunk[..count])
            .map_err(|_| ResidentCodexError::ProviderContentPinFailed)?;
    }
    snapshot
        .sync_all()
        .map_err(|_| ResidentCodexError::ProviderContentPinFailed)?;
    let observed_sha256 = digest_to_hex(digest.finalize());
    if observed_sha256 != expected_sha256 {
        return Err(ResidentCodexError::ProviderContentHashMismatch);
    }
    if require_native && (prefix_length != prefix.len() || prefix != *b"\x7fELF") {
        return Err(ResidentCodexError::ProviderNotNative);
    }
    std::fs::set_permissions(&snapshot_path, std::fs::Permissions::from_mode(0o500))
        .map_err(|_| ResidentCodexError::ProviderContentPinFailed)?;
    Ok(PinnedProvider {
        _temporary: temporary,
        snapshot_path,
        observed_sha256,
    })
}

fn snapshot_auth_json(episode_root: &Path) -> Result<PathBuf, ResidentCodexError> {
    let source_path = resident_auth_source()?;
    snapshot_auth_json_from(&source_path, episode_root)
}

fn snapshot_auth_json_from(
    source_path: &Path,
    episode_root: &Path,
) -> Result<PathBuf, ResidentCodexError> {
    let mut source = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(source_path)
        .map_err(|_| ResidentCodexError::AuthenticationSnapshotFailed)?;
    let metadata = source
        .metadata()
        .map_err(|_| ResidentCodexError::AuthenticationSnapshotFailed)?;
    if !metadata.is_file() || metadata.len() == 0 || metadata.len() > AUTH_MAX_BYTES {
        return Err(ResidentCodexError::AuthenticationSnapshotFailed);
    }
    let destination_path = episode_root.join("auth.json");
    let mut destination = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&destination_path)
        .map_err(|_| ResidentCodexError::AuthenticationSnapshotFailed)?;
    let mut copied = 0_u64;
    let mut chunk = [0_u8; 8 * 1024];
    loop {
        let count = source
            .read(&mut chunk)
            .map_err(|_| ResidentCodexError::AuthenticationSnapshotFailed)?;
        if count == 0 {
            break;
        }
        copied = copied.saturating_add(count as u64);
        if copied > AUTH_MAX_BYTES {
            return Err(ResidentCodexError::AuthenticationSnapshotFailed);
        }
        destination
            .write_all(&chunk[..count])
            .map_err(|_| ResidentCodexError::AuthenticationSnapshotFailed)?;
    }
    destination
        .sync_all()
        .map_err(|_| ResidentCodexError::AuthenticationSnapshotFailed)?;
    Ok(destination_path)
}

fn resident_auth_source() -> Result<PathBuf, ResidentCodexError> {
    if let Some(codex_home) = std::env::var_os("CODEX_HOME") {
        let codex_home = PathBuf::from(codex_home);
        if !codex_home.is_absolute() {
            return Err(ResidentCodexError::AuthenticationSnapshotFailed);
        }
        return Ok(codex_home.join("auth.json"));
    }
    let home = std::env::var_os("HOME")
        .map(PathBuf::from)
        .filter(|path| path.is_absolute())
        .ok_or(ResidentCodexError::AuthenticationSnapshotFailed)?;
    Ok(home.join(".codex/auth.json"))
}

fn append_proxy_environment(args: &mut Vec<OsString>) {
    const PROXY_ENVIRONMENT: &[&str] = &[
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    ];
    for name in PROXY_ENVIRONMENT {
        if let Some(value) = std::env::var_os(name) {
            args.push(OsString::from("--setenv"));
            args.push(OsString::from(name));
            args.push(value);
        }
    }
}

struct ProviderEventAudit {
    event_count: usize,
    fail_closed_diagnostics: usize,
}

fn audit_provider_event_stream(stdout: &[u8]) -> Result<ProviderEventAudit, ResidentCodexError> {
    if stdout.is_empty() {
        // A content-free progress stream is valid. Any emitted Codex JSONL is
        // parsed strictly below so a tool call or protocol drift fails closed.
        return Ok(ProviderEventAudit {
            event_count: 0,
            fail_closed_diagnostics: 0,
        });
    }
    let text =
        std::str::from_utf8(stdout).map_err(|_| ResidentCodexError::ProviderEventStreamInvalid)?;
    let mut count = 0_usize;
    let mut fail_closed_diagnostics = 0_usize;
    for line in text.lines().filter(|line| !line.trim().is_empty()) {
        let event: Value = serde_json::from_str(line)
            .map_err(|_| ResidentCodexError::ProviderEventStreamInvalid)?;
        let event_type = event
            .get("type")
            .and_then(Value::as_str)
            .ok_or(ResidentCodexError::ProviderEventStreamInvalid)?;
        match event_type {
            "thread.started" | "turn.started" | "turn.completed" => {}
            "item.started" | "item.updated" | "item.completed" => {
                let item_type = event
                    .get("item")
                    .and_then(|item| item.get("type"))
                    .and_then(Value::as_str)
                    .ok_or(ResidentCodexError::ProviderEventStreamInvalid)?;
                match item_type {
                    "reasoning" | "agent_message" => {}
                    "error" => {
                        let message = event
                            .get("item")
                            .and_then(|item| item.get("message"))
                            .and_then(Value::as_str)
                            .ok_or(ResidentCodexError::ProviderEventStreamInvalid)?;
                        if !message.starts_with(
                            "Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed;",
                        ) {
                            return Err(ResidentCodexError::ProviderEventStreamInvalid);
                        }
                        fail_closed_diagnostics = fail_closed_diagnostics.saturating_add(1);
                    }
                    _ => return Err(ResidentCodexError::ProviderToolEventObserved),
                }
            }
            _ => return Err(ResidentCodexError::ProviderEventStreamInvalid),
        }
        count = count.saturating_add(1);
    }
    Ok(ProviderEventAudit {
        event_count: count,
        fail_closed_diagnostics,
    })
}

/// Bubblewrap receives no caller environment. The small inner environment is
/// passed as explicit `--setenv` arguments assembled by `bubblewrap_args`.
fn configure_outer_environment(command: &mut Command) {
    command.env_clear();
}

/// The direct launcher is test-only and preserves enough host environment for
/// shell fixtures. It is absent from non-test builds.
#[cfg(test)]
fn configure_fixture_environment(command: &mut Command) {
    const ALLOWED: &[&str] = &[
        "PATH",
        "HOME",
        "CODEX_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "XDG_RUNTIME_DIR",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "TZ",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    ];
    let values: Vec<_> = ALLOWED
        .iter()
        .filter_map(|key| std::env::var_os(key).map(|value| (*key, value)))
        .collect();
    command.env_clear();
    for (key, value) in values {
        command.env(key, value);
    }
    command.env("NO_COLOR", "1");
}

fn write_private_new(path: &Path, bytes: &[u8]) -> Result<(), ResidentCodexError> {
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)
        .map_err(|_| ResidentCodexError::TemporaryWorkspaceFailed)?;
    file.write_all(bytes)
        .map_err(|_| ResidentCodexError::TemporaryWorkspaceFailed)?;
    file.sync_all()
        .map_err(|_| ResidentCodexError::TemporaryWorkspaceFailed)
}

fn read_final_bounded(path: &Path, maximum: usize) -> Result<Vec<u8>, ResidentCodexError> {
    let metadata = std::fs::symlink_metadata(path).map_err(|error| {
        if error.kind() == io::ErrorKind::NotFound {
            ResidentCodexError::FinalMissing
        } else {
            ResidentCodexError::FinalInvalidJson
        }
    })?;
    if !metadata.file_type().is_file() || metadata.len() > maximum as u64 {
        return Err(if metadata.len() > maximum as u64 {
            ResidentCodexError::FinalTooLarge
        } else {
            ResidentCodexError::FinalInvalidJson
        });
    }
    let bytes = std::fs::read(path).map_err(|_| ResidentCodexError::FinalInvalidJson)?;
    if bytes.is_empty() {
        return Err(ResidentCodexError::FinalMissing);
    }
    if bytes.len() > maximum {
        return Err(ResidentCodexError::FinalTooLarge);
    }
    Ok(bytes)
}

async fn read_bounded<R: AsyncRead + Unpin>(
    reader: &mut R,
    maximum: usize,
    overflow: ResidentCodexError,
) -> Result<Vec<u8>, ResidentCodexError> {
    let mut output = Vec::new();
    let mut chunk = [0_u8; 8_192];
    loop {
        let count = reader
            .read(&mut chunk)
            .await
            .map_err(|_| ResidentCodexError::WaitFailed)?;
        if count == 0 {
            return Ok(output);
        }
        if output.len().saturating_add(count) > maximum {
            return Err(overflow);
        }
        output.extend_from_slice(&chunk[..count]);
    }
}

struct HostLock(File);

impl HostLock {
    fn acquire(path: &Path) -> Result<Self, ResidentCodexError> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .mode(0o600)
            .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
            .open(path)
            .map_err(|_| ResidentCodexError::LockUnavailable)?;
        let metadata = file
            .metadata()
            .map_err(|_| ResidentCodexError::LockUnavailable)?;
        if !metadata.is_file() || metadata.mode() & 0o777 != 0o600 || metadata.nlink() != 1 {
            return Err(ResidentCodexError::LockUnavailable);
        }
        let result = unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) };
        if result == 0 {
            return Ok(Self(file));
        }
        let error = io::Error::last_os_error();
        if matches!(error.raw_os_error(), Some(code) if code == libc::EAGAIN || code == libc::EWOULDBLOCK)
        {
            Err(ResidentCodexError::Busy)
        } else {
            Err(ResidentCodexError::LockUnavailable)
        }
    }
}

impl Drop for HostLock {
    fn drop(&mut self) {
        let _ = unsafe { libc::flock(self.0.as_raw_fd(), libc::LOCK_UN) };
    }
}

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
            let _ = signal_group(self.pid, libc::SIGKILL);
        }
    }
}

fn configure_process_group(command: &mut Command) {
    let parent_pid = unsafe { libc::getpid() };
    unsafe {
        command.as_std_mut().pre_exec(move || {
            #[cfg(target_os = "linux")]
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL) == -1 {
                return Err(io::Error::last_os_error());
            }
            if libc::getppid() != parent_pid {
                return Err(io::Error::other("resident broker parent changed"));
            }
            if libc::setsid() == -1 {
                return Err(io::Error::last_os_error());
            }
            Ok(())
        });
    }
}

async fn terminate_and_reap(
    child: &mut Child,
    pid: u32,
    grace: Duration,
) -> Result<(), ResidentCodexError> {
    signal_group(pid, libc::SIGTERM)?;
    match tokio::time::timeout(grace, child.wait()).await {
        Ok(Ok(_)) => {
            let _ = signal_group(pid, libc::SIGKILL);
            Ok(())
        }
        Ok(Err(_)) => Err(ResidentCodexError::CleanupFailed),
        Err(_) => {
            signal_group(pid, libc::SIGKILL)?;
            child
                .wait()
                .await
                .map_err(|_| ResidentCodexError::CleanupFailed)?;
            Ok(())
        }
    }
}

fn signal_group(pid: u32, signal: libc::c_int) -> Result<(), ResidentCodexError> {
    if pid <= 1 || pid > i32::MAX as u32 {
        return Err(ResidentCodexError::CleanupFailed);
    }
    let result = unsafe { libc::kill(-(pid as libc::pid_t), signal) };
    if result == 0 {
        return Ok(());
    }
    let error = io::Error::last_os_error();
    if error.raw_os_error() == Some(libc::ESRCH) {
        Ok(())
    } else {
        Err(ResidentCodexError::CleanupFailed)
    }
}

fn sha256_hex(bytes: &[u8]) -> String {
    digest_to_hex(Sha256::digest(bytes))
}

fn digest_to_hex(digest: impl AsRef<[u8]>) -> String {
    let digest = digest.as_ref();
    let mut output = String::with_capacity(digest.len() * 2);
    for byte in digest {
        use std::fmt::Write;
        let _ = write!(output, "{byte:02x}");
    }
    output
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn fake_request(cwd: PathBuf) -> ResidentCodexRequest {
        ResidentCodexRequest {
            wake_id: "wake-test".into(),
            cognitive_episode_id: "episode-test".into(),
            resident_id: "agent-bridge:resident:xiaoshu".into(),
            cwd,
            prompt: b"private resident packet".to_vec(),
            output_schema: br#"{"type":"object"}"#.to_vec(),
            model: Some("test-model".into()),
            reasoning_effort: Some("low".into()),
        }
    }

    fn broker_config(root: &Path, binary: PathBuf) -> ResidentCodexBrokerConfig {
        let expected_sha256 = sha256_hex(&fs::read(&binary).unwrap());
        let mut config = ResidentCodexBrokerConfig::new(
            binary,
            expected_sha256,
            root.join("resident.lock"),
            Duration::from_secs(2),
        );
        config.termination_grace = Duration::from_millis(25);
        config
    }

    fn write_script(path: &Path, body: &str) {
        use std::io::Write;
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o700)
            .open(path)
            .unwrap();
        file.write_all(body.as_bytes()).unwrap();
    }

    #[tokio::test]
    async fn invocation_is_ephemeral_read_only_structured_and_prompt_stays_on_stdin() {
        let root = tempfile::tempdir().unwrap();
        let script = root.path().join("fake-codex");
        let argv_log = root.path().join("argv.log");
        let stdin_log = root.path().join("stdin.log");
        let body = format!(
            r#"#!/bin/sh
set -eu
printf '%s\n' "$@" > '{}'
final=''
while [ "$#" -gt 0 ]; do
  if [ "$1" = '--output-last-message' ]; then
    final="$2"
    shift 2
  else
    shift
  fi
done
cat > '{}'
printf '%s' '{{"schema_version":"intent-v0","wake_id":"wake-test"}}' > "$final"
printf '%s\n' '{{"type":"turn.completed"}}'
"#,
            argv_log.display(),
            stdin_log.display()
        );
        write_script(&script, &body);
        let broker = ResidentCodexBroker::new(broker_config(root.path(), script)).unwrap();
        let run = broker
            .run_unwrapped_fixture(fake_request(root.path().canonicalize().unwrap()))
            .await
            .unwrap();

        let argv = fs::read_to_string(argv_log).unwrap();
        assert!(argv.contains("--strict-config"));
        assert!(argv.contains("--ignore-user-config"));
        assert!(argv.contains("--ignore-rules"));
        assert!(argv.contains("--ephemeral"));
        assert!(argv.contains("--sandbox\nread-only"));
        assert!(argv.contains("approval_policy=\"never\""));
        assert!(argv.contains("web_search=\"disabled\""));
        assert!(argv.contains("--output-schema"));
        assert!(argv.contains("--output-last-message"));
        assert!(argv.contains("--json"));
        assert!(argv.contains("model_reasoning_effort=\"low\""));
        for feature in RESIDENT_DISABLED_PROVIDER_FEATURES {
            assert!(argv.contains(&format!("--disable\n{feature}")));
        }
        assert!(argv.ends_with("-\n"));
        assert!(!argv.contains("private resident packet"));
        assert!(!argv.contains("danger-full-access"));
        assert!(argv.contains("--skip-git-repo-check"));
        assert_eq!(fs::read(stdin_log).unwrap(), b"private resident packet");
        assert_eq!(run.final_json["wake_id"], "wake-test");
        assert!(run.execution.user_config_ignored);
        assert!(run.execution.ephemeral);
        assert_eq!(
            run.execution.schema_version,
            RESIDENT_CODEX_RECEIPT_SCHEMA_V1
        );
        assert!(run.execution.provider_content_pinned);
        assert_eq!(
            run.execution.expected_provider_sha256,
            run.execution.observed_provider_sha256
        );
        assert!(!run.execution.executes_action);
        assert!(!run.execution.grants_authority);
        assert!(run.execution.provider_event_stream_audited);
        assert_eq!(run.execution.provider_tool_events_observed, 0);
        assert_eq!(run.execution.provider_fail_closed_diagnostics_observed, 0);
        assert_eq!(run.execution.stdout_event_count, 1);
        assert_eq!(
            run.execution.requested_reasoning_effort.as_deref(),
            Some("low")
        );
        assert_eq!(run.execution.stdout_bytes, 26);
        assert_eq!(run.execution.stderr_bytes, 0);
    }

    #[tokio::test]
    async fn malformed_final_output_is_rejected() {
        let root = tempfile::tempdir().unwrap();
        let script = root.path().join("fake-codex");
        write_script(
            &script,
            r#"#!/bin/sh
set -eu
final=''
while [ "$#" -gt 0 ]; do
  if [ "$1" = '--output-last-message' ]; then final="$2"; shift 2; else shift; fi
done
cat >/dev/null
printf 'not-json' > "$final"
"#,
        );
        let broker = ResidentCodexBroker::new(broker_config(root.path(), script)).unwrap();
        let error = broker
            .run_unwrapped_fixture(fake_request(root.path().canonicalize().unwrap()))
            .await
            .unwrap_err();
        assert!(matches!(error, ResidentCodexError::FinalInvalidJson));
    }

    #[tokio::test]
    async fn deadline_terminates_the_episode() {
        let root = tempfile::tempdir().unwrap();
        let script = root.path().join("fake-codex");
        write_script(
            &script,
            r#"#!/bin/sh
cat >/dev/null
sleep 5
"#,
        );
        let mut config = broker_config(root.path(), script);
        config.deadline = Duration::from_millis(40);
        let broker = ResidentCodexBroker::new(config).unwrap();
        let error = broker
            .run_unwrapped_fixture(fake_request(root.path().canonicalize().unwrap()))
            .await
            .unwrap_err();
        assert!(matches!(error, ResidentCodexError::DeadlineExceeded));
    }

    #[tokio::test]
    async fn held_subject_lock_refuses_a_second_episode_without_spawning() {
        let root = tempfile::tempdir().unwrap();
        let marker = root.path().join("spawned");
        let script = root.path().join("fake-codex");
        write_script(
            &script,
            &format!(
                "#!/bin/sh\nprintf spawned > '{}'\nexit 1\n",
                marker.display()
            ),
        );
        let config = broker_config(root.path(), script);
        let _held = HostLock::acquire(&config.lock_path).unwrap();
        let broker = ResidentCodexBroker::new(config).unwrap();
        let error = broker
            .run_unwrapped_fixture(fake_request(root.path().canonicalize().unwrap()))
            .await
            .unwrap_err();
        assert!(matches!(error, ResidentCodexError::Busy));
        assert!(!marker.exists());
    }

    #[tokio::test]
    async fn stdout_overflow_is_bounded_and_rejected() {
        let root = tempfile::tempdir().unwrap();
        let script = root.path().join("fake-codex");
        write_script(
            &script,
            r#"#!/bin/sh
cat >/dev/null
while :; do printf '0123456789abcdef'; done
"#,
        );
        let mut config = broker_config(root.path(), script);
        config.stdout_max_bytes = 128;
        let broker = ResidentCodexBroker::new(config).unwrap();
        let error = broker
            .run_unwrapped_fixture(fake_request(root.path().canonicalize().unwrap()))
            .await
            .unwrap_err();
        assert!(matches!(error, ResidentCodexError::StdoutLimitExceeded));
    }

    #[tokio::test]
    async fn provider_tool_event_fails_closed_even_when_process_exits_zero() {
        let root = tempfile::tempdir().unwrap();
        let script = root.path().join("fake-codex");
        write_script(
            &script,
            r#"#!/bin/sh
set -eu
final=''
while [ "$#" -gt 0 ]; do
  if [ "$1" = '--output-last-message' ]; then final="$2"; shift 2; else shift; fi
done
cat >/dev/null
printf '%s' '{"schema_version":"intent-v0","wake_id":"wake-test"}' > "$final"
printf '%s\n' '{"type":"item.completed","item":{"type":"command_execution"}}'
"#,
        );
        let broker = ResidentCodexBroker::new(broker_config(root.path(), script)).unwrap();
        let error = broker
            .run_unwrapped_fixture(fake_request(root.path().canonicalize().unwrap()))
            .await
            .unwrap_err();
        assert!(matches!(
            error,
            ResidentCodexError::ProviderToolEventObserved
        ));
    }

    #[tokio::test]
    async fn hash_mismatch_refuses_before_lock_episode_temp_or_spawn() {
        let root = tempfile::tempdir().unwrap();
        let marker = root.path().join("spawned");
        let script = root.path().join("fake-codex");
        write_script(
            &script,
            &format!(
                "#!/bin/sh\nprintf spawned > '{}'\nexit 1\n",
                marker.display()
            ),
        );
        let mut config = broker_config(root.path(), script);
        config.expected_codex_sha256 = "0".repeat(64);
        let lock_path = config.lock_path.clone();
        let broker = ResidentCodexBroker::new(config).unwrap();
        EPISODE_TEMP_ATTEMPTED.with(|attempted| attempted.set(false));

        let error = broker
            .run(fake_request(root.path().canonicalize().unwrap()))
            .await
            .unwrap_err();

        assert!(matches!(
            error,
            ResidentCodexError::ProviderContentHashMismatch
        ));
        assert_eq!(
            error.to_string(),
            "resident_codex_provider_content_hash_mismatch"
        );
        assert!(!lock_path.exists());
        assert!(!marker.exists());
        EPISODE_TEMP_ATTEMPTED.with(|attempted| assert!(!attempted.get()));
    }

    #[tokio::test]
    async fn matching_script_is_never_executed_by_production() {
        let root = tempfile::tempdir().unwrap();
        let marker = root.path().join("spawned");
        let script = root.path().join("fake-codex");
        write_script(
            &script,
            &format!(
                "#!/bin/sh\nprintf spawned > '{}'\nexit 1\n",
                marker.display()
            ),
        );
        let config = broker_config(root.path(), script);
        let lock_path = config.lock_path.clone();
        let broker = ResidentCodexBroker::new(config).unwrap();

        let error = broker
            .run(fake_request(root.path().canonicalize().unwrap()))
            .await
            .unwrap_err();

        assert!(matches!(error, ResidentCodexError::ProviderNotNative));
        assert!(!lock_path.exists());
        assert!(!marker.exists());
    }

    #[test]
    fn bubblewrap_topology_has_no_host_workspace_or_general_writable_mount() {
        let root = tempfile::tempdir().unwrap();
        let script = root.path().join("fake-codex");
        write_script(&script, "#!/bin/sh\nexit 0\n");
        let broker = ResidentCodexBroker::new(broker_config(root.path(), script)).unwrap();
        let request = fake_request(root.path().canonicalize().unwrap());
        let provider_snapshot = root.path().join("private/provider.native");
        let auth_snapshot = root.path().join("private/auth.json");
        let output_directory = root.path().join("private/output");
        let args: Vec<String> = broker
            .bubblewrap_args(
                &request,
                &provider_snapshot,
                &auth_snapshot,
                &output_directory,
            )
            .into_iter()
            .map(|argument| argument.to_string_lossy().into_owned())
            .collect();

        assert_eq!(RESIDENT_BWRAP_BINARY, "/usr/bin/bwrap");
        for required in [
            "--die-with-parent",
            "--unshare-user",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--unshare-cgroup",
            "--cap-drop",
            "--clearenv",
            "--dev",
            "--proc",
            "--remount-ro",
            "--tmpfs",
        ] {
            assert!(args.iter().any(|argument| argument == required));
        }
        assert!(!args.iter().any(|argument| argument == "--unshare-net"));
        assert!(!args.iter().any(|argument| argument == "--dev-bind"));
        assert!(!args
            .iter()
            .any(|argument| argument == &request.cwd.display().to_string()));
        assert!(args.windows(3).any(|window| {
            window[0] == "--ro-bind"
                && window[1] == provider_snapshot.display().to_string()
                && window[2] == SANDBOX_PROVIDER_PATH
        }));
        assert!(args.windows(3).any(|window| {
            window[0] == "--ro-bind"
                && window[1] == auth_snapshot.display().to_string()
                && window[2] == format!("{SANDBOX_CODEX_HOME_PATH}/auth.json")
        }));
        let writable_binds: Vec<&[String]> = args
            .windows(3)
            .filter(|window| window[0] == "--bind")
            .collect();
        assert_eq!(writable_binds.len(), 1);
        assert_eq!(writable_binds[0][1], output_directory.display().to_string());
        assert_eq!(writable_binds[0][2], SANDBOX_OUTPUT_PATH);
        assert!(args
            .windows(2)
            .any(|window| { window[0] == "-C" && window[1] == SANDBOX_WORKSPACE_PATH }));
        assert!(args
            .iter()
            .any(|argument| argument == "--skip-git-repo-check"));
        assert!(args
            .iter()
            .any(|argument| argument == "web_search=\"disabled\""));
        for feature in [
            "goals",
            "guardian_approval",
            "in_app_chat",
            "in_app_dictation",
            "in_app_updates",
            "collaboration_modes",
            "steer",
        ] {
            assert!(args
                .windows(2)
                .any(|window| window[0] == "--disable" && window[1] == feature));
        }
    }

    #[test]
    fn authentication_snapshot_copies_only_auth_json_into_episode_temp() {
        let root = tempfile::tempdir().unwrap();
        let source_home = root.path().join("source-home");
        let episode = root.path().join("episode");
        fs::create_dir(&source_home).unwrap();
        fs::create_dir(&episode).unwrap();
        fs::write(source_home.join("auth.json"), b"private-auth").unwrap();
        fs::write(source_home.join("config.toml"), b"must-not-copy").unwrap();

        let snapshot = snapshot_auth_json_from(&source_home.join("auth.json"), &episode).unwrap();

        assert_eq!(snapshot, episode.join("auth.json"));
        assert_eq!(fs::read(&snapshot).unwrap(), b"private-auth");
        assert_eq!(
            fs::metadata(&snapshot).unwrap().permissions().mode() & 0o777,
            0o600
        );
        let entries: Vec<_> = fs::read_dir(&episode)
            .unwrap()
            .map(|entry| entry.unwrap().file_name())
            .collect();
        assert_eq!(entries, vec![OsString::from("auth.json")]);
    }

    #[test]
    fn invocation_contract_grants_no_action_authority() {
        let contract = ResidentCodexInvocationContract::default();
        assert_eq!(contract.sandbox, "read_only");
        assert_eq!(contract.prompt_transport, "stdin");
        assert!(contract.provider_tool_features_requested_disabled);
        assert!(contract.provider_content_pinned);
        assert_eq!(contract.outer_host_filesystem, "read_only");
        assert!(contract.private_ephemeral_output_writable);
        assert!(!contract.request_cwd_mounted);
        assert!(!contract.privacy_boundary_required);
        assert!(contract.recoverable_failure_accepted);
        assert!(!contract.external_mutation_authority);
        assert_eq!(
            contract.provider_event_stream_policy,
            "fail_closed_on_tool_or_unknown_event"
        );
        assert!(!contract.persists_session);
        assert!(!contract.executes_action);
        assert!(!contract.grants_authority);
    }
}
