//! Per-agent workspace sandbox launcher.
//!
//! The bridge daemon must remain unsandboxed: applying Landlock or Seatbelt is
//! irreversible for the current process. Local runtimes therefore re-exec each
//! child through a hidden launcher in the `agent-bridge` binary. The launcher
//! applies a read-mostly workspace policy and then `exec`s the real agent.
//!
//! P1 is deliberately opt-in. `AGENT_BRIDGE_AGENT_SANDBOX=workspace` grants
//! read access to the host, write access to the workspace, temporary paths, and
//! selected runtime/build caches, while hiding common credential paths. Network
//! remains open so model providers and package managers continue to work.

use ab_core::{Error, Result};
use portable_pty::CommandBuilder;
use std::collections::{HashMap, HashSet};
#[cfg(test)]
use std::ffi::OsStr;
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use tokio::process::Command as TokioCommand;

pub const POLICY_ENV: &str = "AGENT_BRIDGE_AGENT_SANDBOX";
pub const BWRAP_BIN_ENV: &str = "AGENT_BRIDGE_BWRAP_BIN";
const CREDS_FILE_ENV: &str = "AGENT_BRIDGE_CREDS_FILE";
const INTERNAL_MARKER: &str = "__ab_agent_sandbox_exec";
const INTERNAL_PREFIX: &str = "__AGENT_BRIDGE_SANDBOX_";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AgentSandboxMode {
    Off,
    Workspace,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LaunchSpec {
    pub program: String,
    pub args: Vec<String>,
    pub sandboxed: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum DeniedKind {
    File,
    Directory,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct DeniedPath {
    path: PathBuf,
    kind: DeniedKind,
}

#[derive(Debug, Clone)]
struct ResolvedPolicy {
    workspace: PathBuf,
    writable: Vec<PathBuf>,
    denied: Vec<DeniedPath>,
}

#[derive(Debug, Clone)]
struct InternalRequest {
    #[cfg_attr(not(target_os = "linux"), allow(dead_code))]
    inner: bool,
    runtime: String,
    workspace: PathBuf,
    program: OsString,
    args: Vec<OsString>,
}

fn parse_mode(value: Option<&str>, source: &str) -> Result<AgentSandboxMode> {
    let Some(value) = value.map(str::trim).filter(|value| !value.is_empty()) else {
        return Ok(AgentSandboxMode::Off);
    };
    match value.to_ascii_lowercase().as_str() {
        "off" | "none" | "false" | "0" | "disabled" => Ok(AgentSandboxMode::Off),
        "workspace" | "true" | "1" | "on" => Ok(AgentSandboxMode::Workspace),
        other => Err(Error::InvalidArgument(format!(
            "invalid {source} sandbox policy '{other}'; expected 'off' or 'workspace'"
        ))),
    }
}

/// Resolve the daemon policy and per-spawn request. The daemon value is a
/// floor: an individual spawn may opt in, but cannot turn an ambient policy off.
pub fn effective_mode_from(ambient: Option<&str>, spawn: Option<&str>) -> Result<AgentSandboxMode> {
    let ambient = parse_mode(ambient, POLICY_ENV)?;
    let spawn = parse_mode(spawn, "agent_spawn env")?;
    if ambient == AgentSandboxMode::Workspace || spawn == AgentSandboxMode::Workspace {
        Ok(AgentSandboxMode::Workspace)
    } else {
        Ok(AgentSandboxMode::Off)
    }
}

pub fn effective_mode(env: &HashMap<String, String>) -> Result<AgentSandboxMode> {
    effective_mode_from(
        std::env::var(POLICY_ENV).ok().as_deref(),
        env.get(POLICY_ENV).map(String::as_str),
    )
}

/// Reject a cloud/remote runtime when workspace sandboxing was requested. P1
/// never claims to sandbox a remote executor by wrapping only its local client.
pub fn reject_nonlocal_if_requested(
    runtime: &str,
    env: &HashMap<String, String>,
    target: &str,
) -> Result<()> {
    if effective_mode(env)? == AgentSandboxMode::Workspace {
        return Err(Error::InvalidArgument(format!(
            "{runtime}: workspace sandboxing is local-only in P1; refusing to launch {target} without equivalent remote enforcement"
        )));
    }
    Ok(())
}

/// Wrap one local executable in the hidden per-child launcher when enabled.
pub fn wrap_local_command(
    runtime: &str,
    workspace: &str,
    env: &HashMap<String, String>,
    program: &str,
    args: &[String],
) -> Result<LaunchSpec> {
    let mode = effective_mode(env)?;
    wrap_local_command_from(
        mode,
        std::env::current_exe().map_err(|e| {
            Error::Backend(format!("{runtime}: resolve agent-bridge executable: {e}"))
        })?,
        runtime,
        workspace,
        env,
        program,
        args,
    )
}

fn wrap_local_command_from(
    mode: AgentSandboxMode,
    current_exe: PathBuf,
    runtime: &str,
    workspace: &str,
    env: &HashMap<String, String>,
    program: &str,
    args: &[String],
) -> Result<LaunchSpec> {
    if env.keys().any(|key| key.starts_with(INTERNAL_PREFIX)) {
        return Err(Error::InvalidArgument(format!(
            "{runtime}: agent_spawn env contains reserved sandbox launcher key"
        )));
    }
    if mode == AgentSandboxMode::Off {
        return Ok(LaunchSpec {
            program: program.to_string(),
            args: args.to_vec(),
            sandboxed: false,
        });
    }
    let launcher = current_exe.into_os_string().into_string().map_err(|_| {
        Error::Backend(format!(
            "{runtime}: agent-bridge executable path is not valid UTF-8"
        ))
    })?;
    let mut wrapped = vec![
        INTERNAL_MARKER.to_string(),
        "--runtime".to_string(),
        runtime.to_string(),
        "--workspace".to_string(),
        workspace.to_string(),
        "--".to_string(),
        program.to_string(),
    ];
    wrapped.extend(args.iter().cloned());
    Ok(LaunchSpec {
        program: launcher,
        args: wrapped,
        sandboxed: true,
    })
}

/// Apply caller env overrides to a pipe-backed child. When sandboxed, scrub
/// inherited non-model credentials before the launcher is started.
pub fn configure_command_env(
    cmd: &mut TokioCommand,
    env: &HashMap<String, String>,
    sandboxed: bool,
) -> Result<()> {
    if sandboxed {
        for (key, _) in std::env::vars_os() {
            if key.to_str().is_some_and(|key| {
                (should_scrub_secret_env(key) && !is_credential_path_env(key))
                    || key.starts_with(INTERNAL_PREFIX)
                    || is_dynamic_loader_env(key)
            }) {
                cmd.env_remove(key);
            }
        }
    }
    for (key, value) in env {
        if key.starts_with(INTERNAL_PREFIX) {
            return Err(Error::InvalidArgument(
                "agent_spawn env contains reserved sandbox launcher key".into(),
            ));
        }
        if !should_forward_spawn_env(key, sandboxed) {
            continue;
        }
        cmd.env(key, value);
    }
    Ok(())
}

/// Portable-PTY equivalent of [`configure_command_env`].
pub fn configure_pty_env(
    cmd: &mut CommandBuilder,
    env: &HashMap<String, String>,
    sandboxed: bool,
) -> Result<()> {
    if sandboxed {
        for (key, _) in std::env::vars_os() {
            if key.to_str().is_some_and(|key| {
                (should_scrub_secret_env(key) && !is_credential_path_env(key))
                    || key.starts_with(INTERNAL_PREFIX)
                    || is_dynamic_loader_env(key)
            }) {
                cmd.env_remove(key);
            }
        }
    }
    for (key, value) in env {
        if key.starts_with(INTERNAL_PREFIX) {
            return Err(Error::InvalidArgument(
                "agent_spawn env contains reserved sandbox launcher key".into(),
            ));
        }
        if !should_forward_spawn_env(key, sandboxed) {
            continue;
        }
        cmd.env(key, value);
    }
    Ok(())
}

fn is_spawn_control_env(key: &str) -> bool {
    matches!(key, POLICY_ENV | BWRAP_BIN_ENV | CREDS_FILE_ENV)
}

/// These values are consumed before the OS sandbox exists. A per-spawn value
/// must not redirect policy resolution or binary lookup, although the daemon's
/// inherited, trusted values remain available to the launcher and target.
fn is_policy_shaping_env(key: &str) -> bool {
    matches!(key, "HOME" | "TMPDIR" | "PATH")
}

/// Dynamic loader variables can execute caller-selected code as soon as the
/// hidden launcher starts, before it has a chance to apply Landlock/Seatbelt.
fn is_dynamic_loader_env(key: &str) -> bool {
    key.starts_with("LD_") || key.starts_with("DYLD_")
}

fn should_forward_spawn_env(key: &str, sandboxed: bool) -> bool {
    !is_spawn_control_env(key)
        && !(sandboxed
            && (should_scrub_secret_env(key)
                || is_policy_shaping_env(key)
                || is_dynamic_loader_env(key)))
}

fn is_credential_path_env(key: &str) -> bool {
    matches!(
        key,
        CREDS_FILE_ENV
            | "GOOGLE_APPLICATION_CREDENTIALS"
            | "AWS_WEB_IDENTITY_TOKEN_FILE"
            | "AWS_SHARED_CREDENTIALS_FILE"
            | "AWS_CONFIG_FILE"
            | "KUBECONFIG"
            | "DOCKER_CONFIG"
            | "NETRC"
    )
}

/// Non-model credentials inherited by the daemon must not leak into agents.
/// Provider credentials remain available so the executor can still authenticate.
pub fn should_scrub_secret_env(key: &str) -> bool {
    matches!(
        key,
        "TAILSCALE_OAUTH_CLIENT_ID"
            | "TAILSCALE_OAUTH_CLIENT_SECRET"
            | "GITHUB_TOKEN"
            | "GH_TOKEN"
            | "GITLAB_TOKEN"
            | "GLAB_TOKEN"
            | "NOTION_TOKEN"
            | "BRAVE_SEARCH_TOKEN"
            | "CLOUDFLARE_API_TOKEN"
            | "CLOUDFLARE_ACCOUNT_ID"
            | "SSH_AUTH_SOCK"
            | "SSH_ASKPASS"
            | "GIT_ASKPASS"
            | "GIT_ASKPASS_REQUIRE"
            | "AWS_ACCESS_KEY_ID"
            | "AWS_SECRET_ACCESS_KEY"
            | "AWS_SESSION_TOKEN"
            | "AWS_SECURITY_TOKEN"
            | "AWS_WEB_IDENTITY_TOKEN_FILE"
            | "AWS_SHARED_CREDENTIALS_FILE"
            | "AWS_CONFIG_FILE"
            | "AZURE_CLIENT_SECRET"
            | "GOOGLE_APPLICATION_CREDENTIALS"
            | "KUBECONFIG"
            | "DOCKER_CONFIG"
            | "NETRC"
            | "NPM_TOKEN"
            | "NODE_AUTH_TOKEN"
            | "PYPI_TOKEN"
            | "CARGO_REGISTRY_TOKEN"
    )
}

/// Called by `agent-bridge` before credential loading and CLI parsing. `None`
/// means this is an ordinary daemon/MCP invocation; `Some` owns the process.
pub fn run_internal_launcher_if_requested() -> Option<Result<()>> {
    let args: Vec<OsString> = std::env::args_os().skip(1).collect();
    let request = match parse_internal_request(&args) {
        Ok(Some(request)) => request,
        Ok(None) => return None,
        Err(error) => return Some(Err(error)),
    };
    Some(run_internal_launcher(request))
}

fn parse_internal_request(args: &[OsString]) -> Result<Option<InternalRequest>> {
    if args.first().and_then(|arg| arg.to_str()) != Some(INTERNAL_MARKER) {
        return Ok(None);
    }
    let mut inner = false;
    let mut runtime = None;
    let mut workspace = None;
    let mut index = 1;
    while index < args.len() {
        match args[index].to_str() {
            Some("--inner") => {
                inner = true;
                index += 1;
            }
            Some("--runtime") => {
                let value = args.get(index + 1).ok_or_else(|| {
                    Error::InvalidArgument("sandbox launcher: --runtime requires a value".into())
                })?;
                runtime = Some(
                    value
                        .to_str()
                        .ok_or_else(|| {
                            Error::InvalidArgument(
                                "sandbox launcher: runtime id is not valid UTF-8".into(),
                            )
                        })?
                        .to_string(),
                );
                index += 2;
            }
            Some("--workspace") => {
                let value = args.get(index + 1).ok_or_else(|| {
                    Error::InvalidArgument("sandbox launcher: --workspace requires a value".into())
                })?;
                workspace = Some(PathBuf::from(value));
                index += 2;
            }
            Some("--") => {
                index += 1;
                break;
            }
            Some(other) => {
                return Err(Error::InvalidArgument(format!(
                    "sandbox launcher: unknown option '{other}'"
                )));
            }
            None => {
                return Err(Error::InvalidArgument(
                    "sandbox launcher option is not valid UTF-8".into(),
                ));
            }
        }
    }
    let runtime = runtime
        .filter(|value| !value.is_empty())
        .ok_or_else(|| Error::InvalidArgument("sandbox launcher: missing --runtime".into()))?;
    let workspace = workspace
        .ok_or_else(|| Error::InvalidArgument("sandbox launcher: missing --workspace".into()))?;
    let program = args.get(index).cloned().ok_or_else(|| {
        Error::InvalidArgument("sandbox launcher: missing target after --".into())
    })?;
    if program.is_empty() {
        return Err(Error::InvalidArgument(
            "sandbox launcher: target program is empty".into(),
        ));
    }
    Ok(Some(InternalRequest {
        inner,
        runtime,
        workspace,
        program,
        args: args[index + 1..].to_vec(),
    }))
}

fn run_internal_launcher(request: InternalRequest) -> Result<()> {
    #[cfg(not(unix))]
    {
        let _ = request;
        return Err(Error::Backend(
            "workspace sandboxing is unsupported on this platform".into(),
        ));
    }

    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;

        let policy = resolve_policy(&request.runtime, &request.workspace)?;
        std::env::set_current_dir(&policy.workspace).map_err(|e| {
            Error::Backend(format!(
                "{}: enter sandbox workspace '{}': {e}",
                request.runtime,
                policy.workspace.display()
            ))
        })?;

        let support = nono::Sandbox::support_info();
        if !support.is_supported {
            return Err(Error::Backend(format!(
                "{}: workspace sandbox unavailable on {}: {}",
                request.runtime, support.platform, support.details
            )));
        }

        #[cfg(target_os = "linux")]
        if !request.inner {
            scrub_current_env(false);
            let bwrap = std::env::var(BWRAP_BIN_ENV).unwrap_or_else(|_| "bwrap".into());
            let self_exe = std::env::current_exe().map_err(|e| {
                Error::Backend(format!("sandbox launcher: resolve current executable: {e}"))
            })?;
            let blocked_file = bwrap_empty_data_fd(&request.runtime)?;
            use std::os::fd::AsRawFd;
            let args = build_bwrap_args(&request, &policy, &self_exe, blocked_file.as_raw_fd());
            let error = std::process::Command::new(&bwrap).args(&args).exec();
            return Err(Error::Backend(format!(
                "{}: exec bubblewrap '{}': {error}; install bubblewrap or set {BWRAP_BIN_ENV}",
                request.runtime, bwrap
            )));
        }

        apply_workspace_policy(&policy)?;
        scrub_current_env(true);
        let error = std::process::Command::new(&request.program)
            .args(&request.args)
            .exec();
        Err(Error::Backend(format!(
            "{}: exec sandbox target '{}': {error}",
            request.runtime,
            Path::new(&request.program).display()
        )))
    }
}

fn resolve_policy(runtime: &str, workspace: &Path) -> Result<ResolvedPolicy> {
    let workspace = workspace.canonicalize().map_err(|e| {
        Error::Backend(format!(
            "{runtime}: canonicalize sandbox workspace '{}': {e}",
            workspace.display()
        ))
    })?;
    if !workspace.is_dir() {
        return Err(Error::InvalidArgument(format!(
            "{runtime}: sandbox workspace '{}' is not a directory",
            workspace.display()
        )));
    }
    if workspace.parent().is_none() {
        return Err(Error::InvalidArgument(
            "workspace sandbox refuses '/' as a writable workspace".into(),
        ));
    }

    let home = std::env::var_os("HOME").map(PathBuf::from);
    if home
        .as_deref()
        .and_then(|path| path.canonicalize().ok())
        .as_ref()
        == Some(&workspace)
    {
        return Err(Error::InvalidArgument(
            "workspace sandbox refuses the home directory as a writable workspace".into(),
        ));
    }

    let mut writable = vec![workspace.clone()];
    for path in temp_writable_paths() {
        push_existing_dir(&mut writable, path);
    }
    if let Some(home) = &home {
        for path in common_cache_paths(home) {
            push_existing_dir(&mut writable, path);
        }
        for path in runtime_state_paths(runtime, home) {
            if !path.exists() {
                std::fs::create_dir_all(&path).map_err(|e| {
                    Error::Backend(format!(
                        "{runtime}: create sandbox runtime state '{}': {e}",
                        path.display()
                    ))
                })?;
            }
            push_existing_dir(&mut writable, path);
        }
    }
    dedup_paths(&mut writable);
    validate_writable_scope(runtime, &workspace, &writable, home.as_deref())?;

    let mut denied = sensitive_paths(home.as_deref());
    collapse_denied_paths(&mut denied);
    Ok(ResolvedPolicy {
        workspace,
        writable,
        denied,
    })
}

fn validate_writable_scope(
    runtime: &str,
    workspace: &Path,
    writable: &[PathBuf],
    home: Option<&Path>,
) -> Result<()> {
    let canonical_home =
        home.map(|path| path.canonicalize().unwrap_or_else(|_| path.to_path_buf()));
    for path in writable {
        if path.parent().is_none() {
            return Err(Error::InvalidArgument(format!(
                "{runtime}: workspace sandbox refuses filesystem root as writable"
            )));
        }
        if path != workspace && canonical_home.as_ref() == Some(path) {
            return Err(Error::InvalidArgument(format!(
                "{runtime}: workspace sandbox refuses the home directory as writable"
            )));
        }
    }
    Ok(())
}

fn temp_writable_paths() -> Vec<PathBuf> {
    let mut paths = vec![PathBuf::from("/tmp"), PathBuf::from("/var/tmp")];
    if cfg!(target_os = "macos") {
        paths.extend(
            ["/private/tmp", "/private/var/tmp"]
                .into_iter()
                .map(PathBuf::from),
        );
    }
    if let Some(path) = std::env::var_os("TMPDIR").map(PathBuf::from) {
        paths.push(path);
    }
    paths
}

fn common_cache_paths(home: &Path) -> Vec<PathBuf> {
    [
        ".cache",
        ".cargo",
        ".rustup",
        ".npm",
        ".pnpm-store",
        ".local/share/pnpm",
        "Library/Caches",
    ]
    .into_iter()
    .map(|suffix| home.join(suffix))
    .collect()
}

fn runtime_state_paths(runtime: &str, home: &Path) -> Vec<PathBuf> {
    let suffixes: &[&str] = match runtime {
        "claude-code" => &[".claude"],
        "codex" => &[".codex"],
        "gemini" => &[".gemini"],
        "acp" | "grok-build" => &[".grok"],
        "kilo" => &[".kilo", ".config/kilo", ".local/share/kilo"],
        "opencode" => &[
            ".config/opencode",
            ".local/share/opencode",
            ".local/state/opencode",
        ],
        "auggie" => &[".augment", ".config/augment", ".local/share/augment"],
        _ => &[],
    };
    suffixes.iter().map(|suffix| home.join(suffix)).collect()
}

fn sensitive_paths(home: Option<&Path>) -> Vec<DeniedPath> {
    let mut paths = Vec::new();
    if let Some(home) = home {
        for suffix in [
            ".ssh",
            ".aws",
            ".azure",
            ".config/gcloud",
            ".config/gh",
            ".config/glab",
            ".kube",
            ".docker",
            ".gnupg",
            "Library/Keychains",
        ] {
            paths.push(DeniedPath {
                path: home.join(suffix),
                kind: DeniedKind::Directory,
            });
        }
        for suffix in [
            ".netrc",
            ".pypirc",
            ".npmrc",
            ".git-credentials",
            ".config/git/credentials",
            ".cargo/credentials",
            ".cargo/credentials.toml",
        ] {
            paths.push(DeniedPath {
                path: home.join(suffix),
                kind: DeniedKind::File,
            });
        }
        paths.push(DeniedPath {
            path: home.join("Documents/ClaudeCode.txt"),
            kind: DeniedKind::File,
        });
    }
    paths.push(DeniedPath {
        path: PathBuf::from("/Media/Ubuntu/Documents/ClaudeCode.txt"),
        kind: DeniedKind::File,
    });

    for key in [
        CREDS_FILE_ENV,
        "GOOGLE_APPLICATION_CREDENTIALS",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_SHARED_CREDENTIALS_FILE",
        "AWS_CONFIG_FILE",
        "NETRC",
    ] {
        if let Some(path) = std::env::var_os(key).filter(|value| !value.is_empty()) {
            paths.push(DeniedPath {
                path: PathBuf::from(path),
                kind: DeniedKind::File,
            });
        }
    }
    if let Some(value) = std::env::var_os("KUBECONFIG") {
        paths.extend(std::env::split_paths(&value).map(|path| DeniedPath {
            path,
            kind: DeniedKind::File,
        }));
    }
    if let Some(path) = std::env::var_os("DOCKER_CONFIG").filter(|value| !value.is_empty()) {
        paths.push(DeniedPath {
            path: PathBuf::from(path),
            kind: DeniedKind::Directory,
        });
    }
    paths
}

fn push_existing_dir(paths: &mut Vec<PathBuf>, path: PathBuf) {
    if path.is_dir() {
        paths.push(path.canonicalize().unwrap_or(path));
    }
}

fn dedup_paths(paths: &mut Vec<PathBuf>) {
    let mut seen = HashSet::new();
    paths.retain(|path| seen.insert(path.clone()));
}

fn collapse_denied_paths(paths: &mut Vec<DeniedPath>) {
    let mut expanded = Vec::new();
    for denied in paths.drain(..) {
        expanded.push(denied.clone());
        if let Ok(canonical) = denied.path.canonicalize() {
            if canonical != denied.path {
                expanded.push(DeniedPath {
                    path: canonical,
                    kind: denied.kind,
                });
            }
        }
    }
    expanded.sort_by(|a, b| {
        a.path
            .components()
            .count()
            .cmp(&b.path.components().count())
            .then_with(|| a.path.cmp(&b.path))
    });
    let mut collapsed: Vec<DeniedPath> = Vec::new();
    for denied in expanded {
        if collapsed.iter().any(|parent| {
            parent.kind == DeniedKind::Directory && denied.path.starts_with(&parent.path)
        }) {
            continue;
        }
        if !collapsed.iter().any(|item| item.path == denied.path) {
            collapsed.push(denied);
        }
    }
    *paths = collapsed;
}

#[cfg(unix)]
fn apply_workspace_policy(policy: &ResolvedPolicy) -> Result<()> {
    use nono::{AccessMode, CapabilitySet, Sandbox};

    let mut caps = CapabilitySet::new()
        .allow_path("/", AccessMode::Read)
        .map_err(|e| Error::Backend(format!("sandbox allow host reads: {e}")))?;
    for path in &policy.writable {
        caps = caps.allow_path(path, AccessMode::ReadWrite).map_err(|e| {
            Error::Backend(format!("sandbox allow write '{}': {e}", path.display()))
        })?;
    }
    for path in [
        "/dev/null",
        "/dev/zero",
        "/dev/random",
        "/dev/urandom",
        "/dev/tty",
        "/dev/ptmx",
        "/dev/fd",
    ] {
        let path = Path::new(path);
        if !path.exists() {
            continue;
        }
        if path.is_dir() {
            caps = caps.allow_path(path, AccessMode::ReadWrite).map_err(|e| {
                Error::Backend(format!("sandbox allow device '{}': {e}", path.display()))
            })?;
        } else {
            caps.allow_file_mut(path, AccessMode::ReadWrite)
                .map_err(|e| {
                    Error::Backend(format!("sandbox allow device '{}': {e}", path.display()))
                })?;
        }
    }
    let dev_pts = Path::new("/dev/pts");
    if dev_pts.is_dir() {
        caps = caps
            .allow_path(dev_pts, AccessMode::ReadWrite)
            .map_err(|e| Error::Backend(format!("sandbox allow /dev/pts: {e}")))?;
    }

    #[cfg(target_os = "macos")]
    add_macos_deny_rules(&mut caps, &policy.denied)?;

    Sandbox::apply(&caps).map_err(|e| Error::Backend(format!("apply workspace sandbox: {e}")))?;
    Ok(())
}

#[cfg(target_os = "macos")]
const SEATBELT_WRITE_DENY_ACTIONS: &[&str] = &[
    "file-write-data",
    "file-write-create",
    "file-write-unlink",
    "file-write-mode",
    "file-write-owner",
    "file-write-flags",
    "file-write-times",
    "file-write-setugid",
];

#[cfg(target_os = "macos")]
fn add_macos_deny_rules(caps: &mut nono::CapabilitySet, denied: &[DeniedPath]) -> Result<()> {
    let mut exact_files = Vec::new();
    for denied in denied {
        for path in macos_path_aliases(&denied.path) {
            let escaped = escape_seatbelt_path(&path)?;
            let filter = match denied.kind {
                DeniedKind::File => {
                    exact_files.push(path);
                    format!("(literal \"{escaped}\")")
                }
                DeniedKind::Directory => format!("(subpath \"{escaped}\")"),
            };
            caps.add_platform_rule(format!("(deny file-read* {filter})"))
                .map_err(|e| Error::Backend(format!("add Seatbelt read deny: {e}")))?;
            caps.add_platform_rule(format!("(deny file-write* {filter})"))
                .map_err(|e| Error::Backend(format!("add Seatbelt write deny: {e}")))?;
            for action in SEATBELT_WRITE_DENY_ACTIONS {
                caps.add_platform_rule(format!("(deny {action} {filter})"))
                    .map_err(|e| Error::Backend(format!("add Seatbelt write deny: {e}")))?;
            }
        }
    }
    caps.remove_exact_file_caps_for_paths(&exact_files);
    Ok(())
}

#[cfg(target_os = "macos")]
fn macos_path_aliases(path: &Path) -> Vec<PathBuf> {
    let mut aliases = vec![path.to_path_buf()];
    if let Ok(canonical) = path.canonicalize() {
        if canonical != path {
            aliases.push(canonical);
        }
    }
    for path in aliases.clone() {
        if let Some(alias) = toggle_private_prefix(&path) {
            aliases.push(alias);
        }
    }
    dedup_paths(&mut aliases);
    aliases
}

#[cfg(target_os = "macos")]
fn toggle_private_prefix(path: &Path) -> Option<PathBuf> {
    let value = path.to_str()?;
    for dir in ["tmp", "var", "etc"] {
        if let Some(rest) = value.strip_prefix(&format!("/private/{dir}")) {
            if rest.is_empty() || rest.starts_with('/') {
                return Some(PathBuf::from(format!("/{dir}{rest}")));
            }
        }
        if let Some(rest) = value.strip_prefix(&format!("/{dir}")) {
            if rest.is_empty() || rest.starts_with('/') {
                return Some(PathBuf::from(format!("/private/{dir}{rest}")));
            }
        }
    }
    None
}

#[cfg(target_os = "macos")]
fn escape_seatbelt_path(path: &Path) -> Result<String> {
    let value = path.to_str().ok_or_else(|| {
        Error::Backend(format!(
            "cannot express non-UTF-8 credential path '{}' in Seatbelt",
            path.display()
        ))
    })?;
    if value.chars().any(char::is_control) {
        return Err(Error::Backend(format!(
            "cannot express control character in Seatbelt path '{}'",
            path.display()
        )));
    }
    Ok(value.replace('\\', "\\\\").replace('"', "\\\""))
}

#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
fn build_bwrap_args(
    request: &InternalRequest,
    policy: &ResolvedPolicy,
    self_exe: &Path,
    blocked_file_fd: i32,
) -> Vec<OsString> {
    let mut args = vec![
        OsString::from("--bind"),
        OsString::from("/"),
        OsString::from("/"),
        OsString::from("--die-with-parent"),
    ];
    for denied in &policy.denied {
        let parent_exists = denied.path.parent().is_some_and(Path::is_dir);
        if !denied.path.exists() && !parent_exists {
            continue;
        }
        match denied.kind {
            DeniedKind::Directory => {
                args.push(OsString::from("--tmpfs"));
                args.push(denied.path.as_os_str().to_owned());
                args.push(OsString::from("--chmod"));
                args.push(OsString::from("000"));
                args.push(denied.path.as_os_str().to_owned());
            }
            DeniedKind::File => {
                // bubblewrap copies EOF from this inherited fd into an
                // anonymous, mode-000 file. Unlike a host-path placeholder,
                // the target cannot find and chmod the backing inode through
                // another writable path.
                args.push(OsString::from("--perms"));
                args.push(OsString::from("000"));
                args.push(OsString::from("--ro-bind-data"));
                args.push(OsString::from(blocked_file_fd.to_string()));
                args.push(denied.path.as_os_str().to_owned());
            }
        }
    }
    args.extend([
        OsString::from("--dev-bind"),
        OsString::from("/dev"),
        OsString::from("/dev"),
        OsString::from("--proc"),
        OsString::from("/proc"),
        OsString::from("--chdir"),
        policy.workspace.as_os_str().to_owned(),
        OsString::from("--"),
        self_exe.as_os_str().to_owned(),
        OsString::from(INTERNAL_MARKER),
        OsString::from("--inner"),
        OsString::from("--runtime"),
        OsString::from(&request.runtime),
        OsString::from("--workspace"),
        policy.workspace.as_os_str().to_owned(),
        OsString::from("--"),
        request.program.clone(),
    ]);
    args.extend(request.args.iter().cloned());
    args
}

/// Open an EOF source for bubblewrap's anonymous `--ro-bind-data` files and
/// clear `FD_CLOEXEC` so the bwrap process can consume it. Bubblewrap closes the
/// descriptor before starting the inner launcher.
#[cfg(target_os = "linux")]
fn bwrap_empty_data_fd(runtime: &str) -> Result<std::fs::File> {
    use std::os::fd::AsRawFd;

    let file = std::fs::File::open("/dev/null")
        .map_err(|e| Error::Backend(format!("{runtime}: open bwrap deny source: {e}")))?;
    let fd = file.as_raw_fd();
    // SAFETY: `fd` belongs to the live `File` above. `fcntl` only reads and
    // updates its descriptor flags; the File retains ownership and closes it if
    // the later `exec` fails.
    let flags = unsafe { libc::fcntl(fd, libc::F_GETFD) };
    if flags < 0 {
        return Err(Error::Backend(format!(
            "{runtime}: read bwrap deny-source fd flags: {}",
            std::io::Error::last_os_error()
        )));
    }
    if unsafe { libc::fcntl(fd, libc::F_SETFD, flags & !libc::FD_CLOEXEC) } < 0 {
        return Err(Error::Backend(format!(
            "{runtime}: make bwrap deny-source fd inheritable: {}",
            std::io::Error::last_os_error()
        )));
    }
    Ok(file)
}

/// Remove secrets in the single-threaded launcher process. The outer Linux
/// launcher preserves path-only control vars until the inner re-exec can build
/// the same deny plan; the final target receives neither controls nor secrets.
fn scrub_current_env(final_target: bool) {
    let keys: Vec<OsString> = std::env::vars_os()
        .filter_map(|(key, _)| {
            let value = key.to_str()?;
            ((should_scrub_secret_env(value) && (final_target || !is_credential_path_env(value)))
                || value.starts_with(INTERNAL_PREFIX)
                || (final_target && is_spawn_control_env(value)))
            .then_some(key)
        })
        .collect();
    for key in keys {
        std::env::remove_var(key);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mode_parser_is_fail_closed_and_ambient_is_a_floor() {
        assert_eq!(
            effective_mode_from(None, None).unwrap(),
            AgentSandboxMode::Off
        );
        assert_eq!(
            effective_mode_from(None, Some("workspace")).unwrap(),
            AgentSandboxMode::Workspace
        );
        assert_eq!(
            effective_mode_from(Some("workspace"), Some("off")).unwrap(),
            AgentSandboxMode::Workspace
        );
        assert!(effective_mode_from(None, Some("typo")).is_err());
    }

    #[test]
    fn wrapper_is_identity_when_off_and_explicit_when_on() {
        let env = HashMap::new();
        let args = vec!["exec".to_string(), "hello".to_string()];
        let off = wrap_local_command_from(
            AgentSandboxMode::Off,
            PathBuf::from("/bin/agent-bridge"),
            "codex",
            "/work",
            &env,
            "codex",
            &args,
        )
        .unwrap();
        assert_eq!(off.program, "codex");
        assert_eq!(off.args, args);
        assert!(!off.sandboxed);

        let on = wrap_local_command_from(
            AgentSandboxMode::Workspace,
            PathBuf::from("/bin/agent-bridge"),
            "codex",
            "/work",
            &env,
            "codex",
            &args,
        )
        .unwrap();
        assert_eq!(on.program, "/bin/agent-bridge");
        assert!(on.sandboxed);
        let parsed =
            parse_internal_request(&on.args.iter().map(OsString::from).collect::<Vec<_>>())
                .unwrap()
                .unwrap();
        assert_eq!(parsed.runtime, "codex");
        assert_eq!(parsed.workspace, Path::new("/work"));
        assert_eq!(parsed.program, OsStr::new("codex"));
        assert_eq!(
            parsed.args,
            [OsString::from("exec"), OsString::from("hello")]
        );
    }

    #[test]
    fn reserved_launcher_env_is_rejected() {
        let mut env = HashMap::new();
        env.insert(format!("{INTERNAL_PREFIX}INNER"), "1".into());
        assert!(wrap_local_command_from(
            AgentSandboxMode::Workspace,
            PathBuf::from("/bin/agent-bridge"),
            "codex",
            "/work",
            &env,
            "codex",
            &[],
        )
        .is_err());
    }

    #[test]
    fn secret_env_scrub_preserves_model_provider_keys() {
        for key in [
            "GITHUB_TOKEN",
            "TAILSCALE_OAUTH_CLIENT_SECRET",
            "SSH_AUTH_SOCK",
            "AWS_SECRET_ACCESS_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
        ] {
            assert!(should_scrub_secret_env(key), "{key}");
        }
        for key in [
            "XAI_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "AZURE_OPENAI_API_KEY",
        ] {
            assert!(!should_scrub_secret_env(key), "{key}");
        }
    }

    #[test]
    fn sandboxed_spawn_env_cannot_shape_or_preload_the_launcher() {
        for key in [
            "HOME",
            "TMPDIR",
            "PATH",
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "DYLD_INSERT_LIBRARIES",
            "DYLD_LIBRARY_PATH",
        ] {
            assert!(!should_forward_spawn_env(key, true), "{key}");
            assert!(should_forward_spawn_env(key, false), "{key}");
        }
        for key in ["OPENAI_API_KEY", "XAI_API_KEY", "RUST_LOG"] {
            assert!(should_forward_spawn_env(key, true), "{key}");
        }
        assert!(!should_forward_spawn_env(POLICY_ENV, false));
        assert!(!should_forward_spawn_env("GITHUB_TOKEN", true));
    }

    #[test]
    fn writable_scope_rejects_root_and_home() {
        let workspace = Path::new("/home/u/project");
        assert!(validate_writable_scope(
            "codex",
            workspace,
            &[workspace.to_path_buf(), PathBuf::from("/")],
            Some(Path::new("/home/u")),
        )
        .is_err());
        assert!(validate_writable_scope(
            "codex",
            workspace,
            &[workspace.to_path_buf(), PathBuf::from("/home/u")],
            Some(Path::new("/home/u")),
        )
        .is_err());
        assert!(validate_writable_scope(
            "codex",
            workspace,
            &[workspace.to_path_buf(), PathBuf::from("/tmp")],
            Some(Path::new("/home/u")),
        )
        .is_ok());
    }

    #[test]
    fn linux_bwrap_plan_overlays_files_and_directories_then_reexecs_inner() {
        let request = InternalRequest {
            inner: false,
            runtime: "codex".into(),
            workspace: PathBuf::from("/work"),
            program: OsString::from("codex"),
            args: vec![OsString::from("exec")],
        };
        let policy = ResolvedPolicy {
            workspace: PathBuf::from("/work"),
            writable: vec![],
            denied: vec![
                DeniedPath {
                    path: PathBuf::from("/tmp/secret-file"),
                    kind: DeniedKind::File,
                },
                DeniedPath {
                    path: PathBuf::from("/tmp/secret-dir"),
                    kind: DeniedKind::Directory,
                },
            ],
        };
        let args = build_bwrap_args(&request, &policy, Path::new("/bin/agent-bridge"), 17);
        let values: Vec<&OsStr> = args.iter().map(OsString::as_os_str).collect();
        assert!(values.windows(5).any(|window| {
            window
                == [
                    OsStr::new("--perms"),
                    OsStr::new("000"),
                    OsStr::new("--ro-bind-data"),
                    OsStr::new("17"),
                    OsStr::new("/tmp/secret-file"),
                ]
        }));
        assert!(values.windows(5).any(|window| {
            window
                == [
                    OsStr::new("--tmpfs"),
                    OsStr::new("/tmp/secret-dir"),
                    OsStr::new("--chmod"),
                    OsStr::new("000"),
                    OsStr::new("/tmp/secret-dir"),
                ]
        }));
        assert!(values
            .windows(2)
            .any(|window| { window == [OsStr::new(INTERNAL_MARKER), OsStr::new("--inner")] }));
    }

    #[test]
    fn denied_directory_collapses_descendants() {
        let mut denied = vec![
            DeniedPath {
                path: PathBuf::from("/home/u/.ssh/id_ed25519"),
                kind: DeniedKind::File,
            },
            DeniedPath {
                path: PathBuf::from("/home/u/.ssh"),
                kind: DeniedKind::Directory,
            },
        ];
        collapse_denied_paths(&mut denied);
        assert_eq!(denied.len(), 1);
        assert_eq!(denied[0].path, Path::new("/home/u/.ssh"));
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn seatbelt_workspace_contract_e2e() {
        const CHILD: &str = "__AGENT_BRIDGE_SANDBOX_E2E_CHILD";
        if std::env::var(CHILD).as_deref() == Ok("1") {
            let workspace = PathBuf::from(std::env::var("AB_SANDBOX_E2E_WORKSPACE").unwrap());
            let outside = PathBuf::from(std::env::var("AB_SANDBOX_E2E_OUTSIDE").unwrap());
            let secret = PathBuf::from(std::env::var(CREDS_FILE_ENV).unwrap());
            let cache = PathBuf::from(std::env::var("AB_SANDBOX_E2E_CACHE").unwrap());
            let nested_secret = cache.join("credentials.toml");
            let mut policy = resolve_policy("sandbox-e2e", &workspace).unwrap();
            policy.writable.push(cache.clone());
            policy.denied.push(DeniedPath {
                path: nested_secret.clone(),
                kind: DeniedKind::File,
            });
            apply_workspace_policy(&policy).unwrap();

            std::fs::write(workspace.join("allowed.txt"), "allowed").unwrap();
            assert!(std::fs::write(outside.join("denied.txt"), "denied").is_err());
            assert!(std::fs::read_to_string(&secret).is_err());
            assert!(std::fs::write(&secret, "overwrite").is_err());
            std::fs::write(cache.join("ordinary-cache-entry"), "allowed").unwrap();
            assert!(std::fs::read_to_string(&nested_secret).is_err());
            assert!(std::fs::write(&nested_secret, "overwrite").is_err());
            let status = std::process::Command::new("/bin/sh")
                .arg("-c")
                .arg("printf child > child.txt")
                .current_dir(&workspace)
                .status()
                .unwrap();
            assert!(status.success());
            assert_eq!(
                std::fs::read_to_string(workspace.join("child.txt")).unwrap(),
                "child"
            );
            return;
        }

        let home = PathBuf::from(std::env::var_os("HOME").expect("HOME"));
        let base = home.join(format!(".agent-bridge-sandbox-e2e-{}", std::process::id()));
        let workspace = base.join("workspace");
        let outside = base.join("outside");
        let cache = base.join("cache");
        let secret = base.join("fake-credential.txt");
        std::fs::create_dir_all(&workspace).unwrap();
        std::fs::create_dir_all(&outside).unwrap();
        std::fs::create_dir_all(&cache).unwrap();
        std::fs::write(&secret, "do-not-read").unwrap();
        std::fs::write(cache.join("credentials.toml"), "nested-do-not-read").unwrap();

        let output = std::process::Command::new(std::env::current_exe().unwrap())
            .arg("--exact")
            .arg("sandbox::tests::seatbelt_workspace_contract_e2e")
            .arg("--nocapture")
            .env(CHILD, "1")
            .env("AB_SANDBOX_E2E_WORKSPACE", &workspace)
            .env("AB_SANDBOX_E2E_OUTSIDE", &outside)
            .env("AB_SANDBOX_E2E_CACHE", &cache)
            .env(CREDS_FILE_ENV, &secret)
            .output()
            .unwrap();
        let cleanup = std::fs::remove_dir_all(&base);
        assert!(cleanup.is_ok(), "cleanup {}: {cleanup:?}", base.display());
        assert!(
            output.status.success(),
            "child failed\nstdout:\n{}\nstderr:\n{}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
    }
}
