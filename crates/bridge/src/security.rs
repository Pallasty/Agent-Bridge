//! Runtime security policy — driven by environment variables.
//!
//! All env vars default to `true` (permissive), preserving backwards
//! compatibility. Operators who want to restrict high-risk capabilities set
//! the corresponding variable to `false` (or `0`/`no`).
//!
//! | Capability    | Env var                    | Controlled tools                        |
//! |---------------|----------------------------|-----------------------------------------|
//! | ShellExec     | `AB_ALLOW_SHELL_EXEC`      | shell_exec                              |
//! | AgentSpawn    | `AB_ALLOW_AGENT_SPAWN`     | agent_spawn                             |
//! | TerminalWrite | `AB_ALLOW_TERMINAL_WRITE`  | terminal_send_keys, terminal_split      |
//! | Browser       | `AB_ALLOW_BROWSER`         | browser_navigate, browser_eval, …       |
//!
//! Additionally, `AB_SHELL_EXEC_TIMEOUT_MAX` caps the `timeout_ms` parameter
//! accepted by `shell_exec` (default: 300 000 ms = 5 min).

/// High-risk capability gate.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Cap {
    ShellExec,
    AgentSpawn,
    TerminalWrite,
    Browser,
}

/// Policy loaded once at startup from environment variables.
#[derive(Debug, Clone)]
pub struct SecurityPolicy {
    pub allow_shell_exec: bool,
    pub allow_agent_spawn: bool,
    pub allow_terminal_write: bool,
    pub allow_browser: bool,
    /// Hard upper bound on shell_exec's timeout_ms parameter.
    pub shell_exec_timeout_max_ms: u64,
}

impl Default for SecurityPolicy {
    fn default() -> Self {
        Self {
            allow_shell_exec: true,
            allow_agent_spawn: true,
            allow_terminal_write: true,
            allow_browser: true,
            shell_exec_timeout_max_ms: 300_000,
        }
    }
}

impl SecurityPolicy {
    /// Read policy from the current process environment.
    pub fn from_env() -> Self {
        Self {
            allow_shell_exec: bool_env("AB_ALLOW_SHELL_EXEC", true),
            allow_agent_spawn: bool_env("AB_ALLOW_AGENT_SPAWN", true),
            allow_terminal_write: bool_env("AB_ALLOW_TERMINAL_WRITE", true),
            allow_browser: bool_env("AB_ALLOW_BROWSER", true),
            shell_exec_timeout_max_ms: std::env::var("AB_SHELL_EXEC_TIMEOUT_MAX")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(300_000),
        }
    }

    /// Returns `Ok(())` if the capability is allowed, or an error string
    /// suitable for `ToolResult::error(...)`.
    pub fn check(&self, cap: Cap) -> Result<(), String> {
        let (allowed, tool, var) = match cap {
            Cap::ShellExec => (self.allow_shell_exec, "shell_exec", "AB_ALLOW_SHELL_EXEC"),
            Cap::AgentSpawn => (
                self.allow_agent_spawn,
                "agent_spawn",
                "AB_ALLOW_AGENT_SPAWN",
            ),
            Cap::TerminalWrite => (
                self.allow_terminal_write,
                "terminal_write",
                "AB_ALLOW_TERMINAL_WRITE",
            ),
            Cap::Browser => (self.allow_browser, "browser", "AB_ALLOW_BROWSER"),
        };
        if allowed {
            Ok(())
        } else {
            Err(format!(
                "{tool} is disabled by policy ({var}=false). \
                 Set {var}=true to enable this capability."
            ))
        }
    }
}

fn bool_env(name: &str, default: bool) -> bool {
    match std::env::var(name).as_deref() {
        Ok("false" | "0" | "no") => false,
        Ok("true" | "1" | "yes") => true,
        _ => default,
    }
}
