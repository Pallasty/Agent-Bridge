//! `agent-bridge setup` — one-shot installer.
//!
//! Installation profiles:
//!
//! - `Frontend::ClaudeCode` (legacy default): copies the binary,
//!   writes the three hook scripts, and merges `UserPromptSubmit /
//!   Stop / PreCompact` entries into `~/.claude/settings.json`.
//! - `Frontend::Codex`: copies the binary and merges an
//!   `[mcp_servers.agent-bridge]` entry into `~/.codex/config.toml`.
//!   It also enables Codex hooks and merges the Agent-Bridge lifecycle
//!   hooks plus the instinct observer into `~/.codex/hooks.json`. The
//!   default toolset is `codex-essential`; `--codex-toolset lean` writes
//!   the narrower experimental `codex-lean` surface.
//! - `Frontend::CodexCli` / `Frontend::CodexIde`: install the same Codex
//!   MCP entry with a host marker, but skip lifecycle hooks because those
//!   surfaces may not expose Codex desktop hook events.
//! - `Frontend::GeminiCli`: copies the binary and merges an
//!   `mcpServers.agent-bridge` entry into `~/.gemini/settings.json`.
//! - `Frontend::LocalCli`: copies the binary and installs MCP config
//!   for local stdio-capable CLI clients (Codex, Gemini CLI, Claude Code
//!   best-effort registration).
//! - `Frontend::Warp`: copies the binary only. Warp does not expose
//!   shell-out hooks for those events, so the hook scripts and the
//!   `~/.claude/settings.json` rewrite are deliberately skipped.
//!   Instead, prints UI guidance for registering the MCP server
//!   through `Settings → MCP servers` and recommends letting agents
//!   call `session_bootstrap` / `session_curate` / `session_finalize`
//!   manually at session boundaries.
//! - `Frontend::Auggie`: copies the binary and tries to register the
//!   MCP server with `auggie mcp add` so the user does not have to
//!   hand-edit `~/.augment/settings.json`. Like Warp, Auggie has no
//!   `UserPromptSubmit / Stop / PreCompact` hooks, so we skip the
//!   hook scripts and Claude settings rewrite.

use anyhow::{Context, Result};
use serde_json::{json, Value};
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

// Hook scripts embedded at compile time from the hooks/ directory.
const HOOK_MEMORY: &str = include_str!("hooks/ab-memory-hook.sh");
const HOOK_PRECOMPACT: &str = include_str!("hooks/ab-precompact-hook.sh");
const HOOK_SESSION_END: &str = include_str!("hooks/ab-session-end-hook.sh");
const HOOK_INSTINCT_OBSERVER: &str = include_str!("hooks/ab-instinct-observer-hook.py");
const MANAGED_TOOL_ENV_KEYS: &[&str] = &[
    "AGENT_BRIDGE_CLIENT",
    "AGENT_BRIDGE_TOOLSET",
    "AGENT_BRIDGE_TOOL_PROFILE",
    "AGENT_BRIDGE_CODEX_HOST",
];

/// Which frontend the setup is targeting. Drives whether hook scripts
/// and `~/.claude/settings.json` are written.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum Frontend {
    ClaudeCode,
    Warp,
    Auggie,
    Codex,
    CodexCli,
    CodexIde,
    GeminiCli,
    Cursor,
    LocalCli,
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum CodexToolset {
    Essential,
    Lean,
}

impl CodexToolset {
    fn label(self) -> &'static str {
        match self {
            Self::Essential => "codex-essential",
            Self::Lean => "codex-lean",
        }
    }

    fn profile_label(self) -> &'static str {
        "essential"
    }
}

pub fn run(frontend: Frontend, codex_toolset: CodexToolset) -> Result<()> {
    let home = home_dir().context("cannot determine $HOME")?;

    // ── 1. Install binary (always) ───────────────────────────────────────
    let bin_dir = home.join(".local/bin");
    fs::create_dir_all(&bin_dir).context("create ~/.local/bin")?;

    let mcp_command = bin_dir.join("agent-bridge");
    let install_dst = binary_install_destination(&mcp_command);
    let bin_src = std::env::current_exe().context("current_exe")?;

    if bin_src != install_dst {
        copy_executable_atomically(&bin_src, &install_dst)?;
        println!("  ✓  binary      → {}", install_dst.display());
        if install_dst != mcp_command {
            println!(
                "  ·  MCP command → {} (wrapper preserved)",
                mcp_command.display()
            );
        }
    } else {
        println!("  ·  binary      already at {}", install_dst.display());
    }

    match frontend {
        Frontend::ClaudeCode => install_claude_code(&home, &bin_dir, &mcp_command),
        Frontend::Warp => install_warp(&mcp_command),
        Frontend::Auggie => install_auggie(&mcp_command),
        Frontend::Codex => install_codex(
            &home,
            &bin_dir,
            &mcp_command,
            CodexHost::Desktop,
            codex_toolset,
        ),
        Frontend::CodexCli => {
            install_codex(&home, &bin_dir, &mcp_command, CodexHost::Cli, codex_toolset)
        }
        Frontend::CodexIde => {
            install_codex(&home, &bin_dir, &mcp_command, CodexHost::Ide, codex_toolset)
        }
        Frontend::GeminiCli => install_gemini_cli(&home, &mcp_command),
        Frontend::Cursor => install_cursor(&home, &mcp_command),
        Frontend::LocalCli => install_local_cli(&home, &mcp_command, codex_toolset),
    }
}

/// When `~/.local/bin/agent-bridge` is the env-injection wrapper, install the
/// real ELF to `agent-bridge.real` so `setup` does not clobber the wrapper.
fn binary_install_destination(mcp_command: &Path) -> PathBuf {
    if is_env_wrapper_script(mcp_command) {
        mcp_command.with_extension("real")
    } else {
        mcp_command.to_path_buf()
    }
}

fn is_env_wrapper_script(path: &Path) -> bool {
    let Ok(meta) = fs::metadata(path) else {
        return false;
    };
    if !meta.is_file() || meta.len() > 32 * 1024 {
        return false;
    }
    let Ok(text) = fs::read_to_string(path) else {
        return false;
    };
    text.starts_with("#!") && text.contains("bash") && text.contains("agent-bridge.real")
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
enum CodexHost {
    Desktop,
    Cli,
    Ide,
}

impl CodexHost {
    fn label(self) -> &'static str {
        match self {
            Self::Desktop => "desktop",
            Self::Cli => "cli",
            Self::Ide => "ide",
        }
    }

    fn profile_label(self) -> &'static str {
        match self {
            Self::Desktop => "codex desktop",
            Self::Cli => "codex-cli",
            Self::Ide => "codex-ide",
        }
    }

    fn installs_hooks(self) -> bool {
        matches!(self, Self::Desktop)
    }
}

fn copy_executable_atomically(src: &Path, dst: &Path) -> Result<()> {
    let tmp = dst.with_extension(format!("tmp-{}", std::process::id()));
    if tmp.exists() {
        fs::remove_file(&tmp).with_context(|| format!("remove stale {}", tmp.display()))?;
    }

    fs::copy(src, &tmp).with_context(|| format!("copy binary → {}", tmp.display()))?;
    let perms_result = (|| -> Result<()> {
        let mut perms = fs::metadata(&tmp)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&tmp, perms)?;
        fs::rename(&tmp, dst).with_context(|| format!("install binary → {}", dst.display()))?;
        Ok(())
    })();

    if perms_result.is_err() {
        let _ = fs::remove_file(&tmp);
    }
    perms_result
}

/// Claude Code profile: full hook installation.
fn install_claude_code(home: &Path, bin_dir: &Path, bin_dst: &Path) -> Result<()> {
    // ── 2. Write hook scripts ────────────────────────────────────────────
    write_script(&bin_dir.join("ab-memory-hook"), HOOK_MEMORY)?;
    write_script(&bin_dir.join("ab-precompact-hook"), HOOK_PRECOMPACT)?;
    write_script(&bin_dir.join("ab-session-end-hook"), HOOK_SESSION_END)?;

    // ── 3. Merge Claude Code settings ────────────────────────────────────
    merge_claude_settings(home, bin_dir)?;
    let claude_registered = try_register_claude_mcp(bin_dst);

    println!();
    println!("Setup complete (claude-code profile).");
    println!();
    println!("Next steps:");
    println!("  1. Add ~/.local/bin to your PATH if it isn't already.");
    println!("  2. Start the daemon:  agent-bridge daemon &");
    if claude_registered {
        println!("  3. MCP server registered with AGENT_BRIDGE_TOOLSET=claude-standard.");
    } else {
        println!("  3. Register as MCP:");
        print_claude_mcp_add_command(bin_dst);
    }
    println!("  4. (Optional) Bootstrap cross-device memory sync:");
    println!("       gh auth login          # one-time, if not already authenticated");
    println!("       agent-bridge sync init # creates/clones the private memory repo");
    println!("  5. Restart Claude Code — the hooks take effect on the next session.");

    Ok(())
}

/// Warp profile: binary only, plus printed registration guidance.
///
/// Warp does not have analogues for the Claude Code hook events
/// (`UserPromptSubmit` / `Stop` / `PreCompact`), so we deliberately
/// skip:
///   - writing the three `ab-*-hook` shell scripts,
///   - rewriting `~/.claude/settings.json` (which Warp users may not
///     even have),
///   - emitting hook scripts (no hook events in Warp).
fn install_warp(bin_dst: &Path) -> Result<()> {
    println!("  ·  hook scripts skipped (Warp has no equivalent hook events)");
    println!("  ·  ~/.claude/settings.json skipped (claude-code only)");
    println!();
    println!("Setup complete (warp profile).");
    println!();
    println!("Next steps in Warp:");
    println!("  1. Open  Settings  →  MCP servers  →  Add server.");
    println!("  2. Configure:");
    println!("       Name:    agent-bridge");
    println!("       Command: {}", bin_dst.display());
    println!("       Args:    [\"mcp\"]");
    println!("  3. Save and reload Warp.");
    println!();
    println!("For session lifecycle (Warp has no PreCompact/Stop hooks),");
    println!("have the agent call these MCP tools manually:");
    println!("  • At session start  →  read agent-bridge://session/bootstrap");
    println!("                        (or call the session_bootstrap tool)");
    println!("  • Before summarising →  call session_curate(conversation_text=...)");
    println!("  • At session end    →  call session_finalize()");
    println!();
    println!("Optional: start the long-lived daemon for Unix-socket access:");
    println!("  agent-bridge daemon &");

    Ok(())
}

/// Codex profiles: binary plus MCP registration; desktop also installs lifecycle hooks.
///
/// Codex reads MCP server definitions from the `[mcp_servers]` table in
/// `config.toml`. Recent Codex builds expose a hooks.json lifecycle file,
/// so this profile installs the Agent-Bridge hook scripts and wires them
/// into Codex without touching `~/.claude/settings.json`.
fn install_codex(
    home: &Path,
    bin_dir: &Path,
    bin_dst: &Path,
    host: CodexHost,
    toolset: CodexToolset,
) -> Result<()> {
    if host.installs_hooks() {
        write_script(&bin_dir.join("ab-memory-hook"), HOOK_MEMORY)?;
        write_script(&bin_dir.join("ab-precompact-hook"), HOOK_PRECOMPACT)?;
        write_script(&bin_dir.join("ab-session-end-hook"), HOOK_SESSION_END)?;
        write_script(
            &bin_dir.join("ab-instinct-observer-hook"),
            HOOK_INSTINCT_OBSERVER,
        )?;
    } else {
        println!("  ·  hook scripts skipped ({} host)", host.profile_label());
    }
    println!("  ·  ~/.claude/settings.json skipped (claude-code only)");

    merge_codex_config(home, bin_dst, host.installs_hooks(), host, toolset)?;
    if host.installs_hooks() {
        merge_codex_hooks(home, bin_dir)?;
    }

    println!();
    println!("Setup complete ({} profile).", host.profile_label());
    println!();
    println!("Next steps in Codex:");
    println!("  1. Restart Codex or open a new Codex session so MCP servers reload.");
    println!("  2. Check the MCP/tools panel for the `agent-bridge` server.");
    if host.installs_hooks() {
        println!("  3. If Codex asks to trust new hooks, approve the Agent-Bridge entries.");
    } else if matches!(host, CodexHost::Ide) {
        println!("  3. Start an IDE snapshot writer so `ide_snapshot` returns editor state.");
    } else {
        println!("  3. Call `session_bootstrap` / `session_finalize` manually if this host has no hooks.");
    }
    println!();
    println!("Optional: start the long-lived daemon for Unix-socket access:");
    println!("  agent-bridge daemon &");

    Ok(())
}

/// Cursor profile: binary plus `~/.cursor/mcp.json` MCP registration.
fn install_cursor(home: &Path, bin_dst: &Path) -> Result<()> {
    println!("  ·  hook scripts skipped (Cursor has no equivalent hook events)");
    println!("  ·  ~/.claude/settings.json skipped (claude-code only)");

    merge_cursor_settings(home, bin_dst)?;

    println!();
    println!("Setup complete (cursor profile).");
    println!();
    println!("Next steps in Cursor:");
    println!("  1. Open Settings → MCP and confirm `agent-bridge` is enabled.");
    println!("  2. Run **Developer: Reload Window** so tools/list refreshes.");
    println!("  3. Expect ~98 tools with `AGENT_BRIDGE_TOOLSET=claude-standard`.");
    print_manual_lifecycle_guidance("Cursor");

    Ok(())
}

/// Read `~/.cursor/mcp.json`, replace or append `mcpServers.agent-bridge`.
fn merge_cursor_settings(home: &Path, bin_dst: &Path) -> Result<()> {
    let settings_path = home.join(".cursor/mcp.json");

    let mut settings: Value = if settings_path.exists() {
        let raw = fs::read_to_string(&settings_path)
            .with_context(|| format!("read {}", settings_path.display()))?;
        serde_json::from_str(&raw).unwrap_or(json!({}))
    } else {
        json!({})
    };

    let root = settings
        .as_object_mut()
        .context("Cursor mcp.json is not an object")?;
    let mcp_servers = root
        .entry("mcpServers")
        .or_insert(json!({}))
        .as_object_mut()
        .context("Cursor mcpServers is not an object")?;

    let agent_bridge_env = merged_tool_env(
        mcp_servers.get("agent-bridge").and_then(|v| v.get("env")),
        "cursor",
        "claude-standard",
        "standard",
    );
    mcp_servers.insert(
        "agent-bridge".to_string(),
        json!({
            "command": bin_dst.display().to_string(),
            "args": ["mcp"],
            "env": agent_bridge_env
        }),
    );

    if let Some(parent) = settings_path.parent() {
        fs::create_dir_all(parent).context("create ~/.cursor")?;
    }
    let out = serde_json::to_string_pretty(&settings).context("re-serialize Cursor mcp.json")?;
    fs::write(&settings_path, out).with_context(|| format!("write {}", settings_path.display()))?;
    println!(
        "  ✓  settings     → {} (MCP server merged)",
        settings_path.display()
    );

    Ok(())
}

/// Gemini CLI profile: binary plus `~/.gemini/settings.json` MCP registration.
fn install_gemini_cli(home: &Path, bin_dst: &Path) -> Result<()> {
    println!("  ·  hook scripts skipped (Gemini CLI has no equivalent hook events)");
    println!("  ·  ~/.claude/settings.json skipped (claude-code only)");

    merge_gemini_settings(home, bin_dst)?;

    println!();
    println!("Setup complete (gemini-cli profile).");
    println!();
    println!("Next steps in Gemini CLI:");
    println!("  1. Restart Gemini CLI so MCP servers reload.");
    println!("  2. Run `/mcp` inside Gemini CLI to verify `agent-bridge` is connected.");
    print_manual_lifecycle_guidance("Gemini CLI");

    Ok(())
}

/// Local CLI profile: register stdio MCP config for multiple CLI clients.
fn install_local_cli(home: &Path, bin_dst: &Path, codex_toolset: CodexToolset) -> Result<()> {
    println!("  ·  hook scripts skipped (local CLI profile uses MCP config only)");
    println!("  ·  ~/.claude/settings.json skipped (claude-code hooks only)");

    merge_codex_config(home, bin_dst, false, CodexHost::Cli, codex_toolset)?;
    merge_gemini_settings(home, bin_dst)?;
    merge_cursor_settings(home, bin_dst)?;
    let claude_registered = try_register_claude_mcp(bin_dst);

    println!();
    println!("Setup complete (local-cli profile).");
    println!();
    println!("Configured:");
    println!("  ✓ Codex      → ~/.codex/config.toml");
    println!("  ✓ Gemini CLI → ~/.gemini/settings.json");
    println!("  ✓ Cursor     → ~/.cursor/mcp.json");
    if claude_registered {
        println!("  ✓ Claude Code → MCP server registered");
    } else {
        println!("  · Claude Code → register manually if desired:");
        print_claude_mcp_add_command(bin_dst);
    }
    println!();
    println!("Restart each CLI session so MCP servers reload.");
    print_manual_lifecycle_guidance("local CLI clients");

    Ok(())
}

/// Auggie profile: binary only, plus best-effort `auggie mcp add`
/// registration.
///
/// Auggie has no `UserPromptSubmit / Stop / PreCompact` hook events,
/// so we deliberately skip:
///   - writing the three `ab-*-hook` shell scripts,
///   - rewriting `~/.claude/settings.json` (Auggie users may not have it).
///
/// MCP registration uses the Auggie CLI's own `mcp add` subcommand
/// (which writes `~/.augment/settings.json`). If `auggie` is not on
/// `$PATH`, we fall back to printing the equivalent command for the
/// user to run manually.
fn install_auggie(bin_dst: &Path) -> Result<()> {
    println!("  ·  hook scripts skipped (Auggie has no equivalent hook events)");
    println!("  ·  ~/.claude/settings.json skipped (claude-code only)");

    let registered = try_register_auggie_mcp(bin_dst);

    println!();
    println!("Setup complete (auggie profile).");
    println!();
    if registered {
        println!("MCP server 'agent-bridge' registered with Auggie via `auggie mcp add`.");
        println!("Restart any open Auggie sessions to pick it up.");
    } else {
        println!("Could not run `auggie mcp add` automatically. Register manually:");
        println!(
            "  auggie mcp add agent-bridge --command {} --args mcp",
            bin_dst.display()
        );
        println!("(or edit ~/.augment/settings.json by hand).");
    }
    println!();
    println!("For session lifecycle (Auggie has no PreCompact/Stop hooks),");
    println!("have the agent call these MCP tools manually:");
    println!("  • At session start  →  read agent-bridge://session/bootstrap");
    println!("                        (or call the session_bootstrap tool)");
    println!("  • Before summarising →  call session_curate(conversation_text=...)");
    println!("  • At session end    →  call session_finalize()");
    println!();
    println!("Optional: start the long-lived daemon for Unix-socket access:");
    println!("  agent-bridge daemon &");

    Ok(())
}

/// Best-effort: invoke `auggie mcp add agent-bridge --command <bin>
/// --args mcp`. Returns true on success, false on any failure
/// (auggie not installed, non-zero exit, etc.) so the caller can
/// print a manual fallback.
fn try_register_auggie_mcp(bin_dst: &Path) -> bool {
    let status = std::process::Command::new("auggie")
        .arg("mcp")
        .arg("add")
        .arg("agent-bridge")
        .arg("--command")
        .arg(bin_dst)
        .arg("--args")
        .arg("mcp")
        .status();
    match status {
        Ok(s) if s.success() => true,
        Ok(s) => {
            println!("  ·  `auggie mcp add` exited with {s}; falling back to manual instructions");
            false
        }
        Err(e) => {
            println!("  ·  could not invoke `auggie` ({e}); falling back to manual instructions");
            false
        }
    }
}

/// Best-effort: invoke `claude mcp add -s user` with the Claude-specific
/// Agent-Bridge toolset environment.
///
/// Claude Code's CLI owns the exact config format/scope semantics, so
/// using the CLI is safer than editing Claude's files directly. The
/// local-CLI profile uses user scope so the server is available outside
/// the current project directory. Failure is non-fatal; setup prints the
/// manual command.
fn try_register_claude_mcp(bin_dst: &Path) -> bool {
    let output = claude_mcp_add_agent_bridge(bin_dst);
    match output {
        Ok(o) if o.status.success() => true,
        Ok(o) => {
            let detail = command_detail(&o);
            if detail.contains("already exists") {
                let _ = std::process::Command::new("claude")
                    .arg("mcp")
                    .arg("remove")
                    .arg("-s")
                    .arg("user")
                    .arg("agent-bridge")
                    .output();
                match claude_mcp_add_agent_bridge(bin_dst) {
                    Ok(retry) if retry.status.success() => true,
                    Ok(retry) => {
                        println!(
                            "  ·  `claude mcp add` retry exited with {}; falling back to manual instructions{}",
                            retry.status,
                            detail_suffix(&command_detail(&retry))
                        );
                        claude_mcp_get_agent_bridge()
                    }
                    Err(e) => {
                        println!("  ·  could not invoke `claude` ({e}); falling back to manual instructions");
                        claude_mcp_get_agent_bridge()
                    }
                }
            } else {
                println!(
                    "  ·  `claude mcp add` exited with {}; falling back to manual instructions{}",
                    o.status,
                    detail_suffix(&detail)
                );
                false
            }
        }
        Err(e) => {
            println!("  ·  could not invoke `claude` ({e}); falling back to manual instructions");
            false
        }
    }
}

fn claude_mcp_add_agent_bridge(bin_dst: &Path) -> std::io::Result<std::process::Output> {
    std::process::Command::new("claude")
        .arg("mcp")
        .arg("add")
        .arg("-s")
        .arg("user")
        .arg("-e")
        .arg("AGENT_BRIDGE_CLIENT=claude")
        .arg("-e")
        .arg("AGENT_BRIDGE_TOOLSET=claude-standard")
        .arg("-e")
        .arg("AGENT_BRIDGE_TOOL_PROFILE=standard")
        .arg("--")
        .arg("agent-bridge")
        .arg(bin_dst)
        .arg("mcp")
        .output()
}

fn command_detail(output: &std::process::Output) -> String {
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if !stderr.is_empty() {
        stderr
    } else {
        stdout
    }
}

fn detail_suffix(detail: &str) -> String {
    if detail.is_empty() {
        String::new()
    } else {
        format!(" ({detail})")
    }
}

fn print_claude_mcp_add_command(bin_dst: &Path) {
    println!(
        "      claude mcp add -s user -e AGENT_BRIDGE_CLIENT=claude -e AGENT_BRIDGE_TOOLSET=claude-standard -e AGENT_BRIDGE_TOOL_PROFILE=standard -- agent-bridge {} mcp",
        bin_dst.display()
    );
}

fn claude_mcp_get_agent_bridge() -> bool {
    std::process::Command::new("claude")
        .arg("mcp")
        .arg("get")
        .arg("agent-bridge")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

// ─── helpers ─────────────────────────────────────────────────────────────────

fn home_dir() -> Option<PathBuf> {
    std::env::var("HOME").ok().map(PathBuf::from)
}

fn write_script(path: &Path, content: &str) -> Result<()> {
    fs::write(path, content).with_context(|| format!("write {}", path.display()))?;
    let mut perms = fs::metadata(path)?.permissions();
    perms.set_mode(0o755);
    fs::set_permissions(path, perms)?;
    println!("  ✓  hook script  → {}", path.display());
    Ok(())
}

/// Read `~/.codex/config.toml`, replace or append the
/// `[mcp_servers.agent-bridge]` table, then write back while preserving
/// unrelated Codex settings.
fn toml_line_assigns_key(line: &str, key: &str) -> bool {
    line.trim_start()
        .strip_prefix(key)
        .and_then(|rest| rest.trim_start().strip_prefix('='))
        .is_some()
}

fn toml_top_level_string(raw: &str, key: &str) -> Option<String> {
    for line in raw.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') {
            break;
        }
        let Some(rest) = trimmed.strip_prefix(key) else {
            continue;
        };
        let Some(value) = rest.trim_start().strip_prefix('=') else {
            continue;
        };
        let value = value.trim();
        if value.starts_with('"') && value.ends_with('"') && value.len() >= 2 {
            return Some(value[1..value.len() - 1].replace("\\\"", "\""));
        }
    }
    None
}

fn merge_codex_config(
    home: &Path,
    bin_dst: &Path,
    enable_hooks: bool,
    host: CodexHost,
    toolset: CodexToolset,
) -> Result<()> {
    let codex_home = codex_home(home);
    let config_path = codex_home.join("config.toml");

    let raw = if config_path.exists() {
        fs::read_to_string(&config_path)
            .with_context(|| format!("read {}", config_path.display()))?
    } else {
        String::new()
    };

    let mut env_lines = vec![
        "AGENT_BRIDGE_CLIENT = \"codex\"".to_string(),
        format!("AGENT_BRIDGE_TOOLSET = \"{}\"", toolset.label()),
        format!(
            "AGENT_BRIDGE_TOOL_PROFILE = \"{}\"",
            toolset.profile_label()
        ),
        format!("AGENT_BRIDGE_CODEX_HOST = \"{}\"", host.label()),
    ];
    let model = toml_top_level_string(&raw, "model");
    let model_reasoning_effort = toml_top_level_string(&raw, "model_reasoning_effort");
    if let Some(model) = &model {
        env_lines.push(format!(
            "AGENT_BRIDGE_MODEL = \"{}\"",
            escape_toml_basic_string(model)
        ));
    }
    if let Some(reasoning_effort) = &model_reasoning_effort {
        env_lines.push(format!(
            "AGENT_BRIDGE_MODEL_REASONING_EFFORT = \"{}\"",
            escape_toml_basic_string(reasoning_effort)
        ));
    }
    for line in toml_table_body_lines(&raw, "mcp_servers.agent-bridge.env") {
        let trimmed = line.trim_start();
        if MANAGED_TOOL_ENV_KEYS
            .iter()
            .any(|key| toml_line_assigns_key(trimmed, key))
        {
            continue;
        }
        if model.is_some() && toml_line_assigns_key(trimmed, "AGENT_BRIDGE_MODEL") {
            continue;
        }
        if model_reasoning_effort.is_some()
            && toml_line_assigns_key(trimmed, "AGENT_BRIDGE_MODEL_REASONING_EFFORT")
        {
            continue;
        }
        if !trimmed.is_empty() {
            env_lines.push(line.to_string());
        }
    }

    let block = format!(
        r#"[mcp_servers.agent-bridge]
command = "{}"
args = ["mcp"]
enabled = true
startup_timeout_sec = 20
tool_timeout_sec = 300
supports_parallel_tool_calls = false

[mcp_servers.agent-bridge.env]
{}
"#,
        escape_toml_basic_string(&bin_dst.display().to_string()),
        env_lines.join("\n")
    );

    let updated = replace_toml_table(&raw, "mcp_servers.agent-bridge", &block);
    let updated = if enable_hooks {
        let updated = remove_toml_key(&updated, "features", "codex_hooks");
        ensure_toml_bool(&updated, "features", "hooks", true)
    } else {
        updated
    };

    if let Some(parent) = config_path.parent() {
        fs::create_dir_all(parent).context("create Codex config directory")?;
    }
    fs::write(&config_path, updated).with_context(|| format!("write {}", config_path.display()))?;
    println!(
        "  ✓  settings     → {} (MCP server merged)",
        config_path.display()
    );

    Ok(())
}

/// Read `~/.codex/hooks.json`, add Agent-Bridge lifecycle hooks if absent,
/// and preserve unrelated hooks such as cmux or plugin-installed entries.
fn merge_codex_hooks(home: &Path, bin_dir: &Path) -> Result<()> {
    let hooks_path = codex_home(home).join("hooks.json");
    let mut settings: Value = if hooks_path.exists() {
        let raw = fs::read_to_string(&hooks_path)
            .with_context(|| format!("read {}", hooks_path.display()))?;
        serde_json::from_str(&raw).unwrap_or(json!({}))
    } else {
        json!({})
    };

    let root = settings
        .as_object_mut()
        .context("Codex hooks.json is not an object")?;
    let hooks_obj = root
        .entry("hooks")
        .or_insert(json!({}))
        .as_object_mut()
        .context("Codex hooks is not an object")?;

    let bin = bin_dir.to_string_lossy();
    let session_end_command = format!("AB_SESSION_END_CURATE=1 \"{}/ab-session-end-hook\"", bin);
    let new_hooks: &[(&str, Option<&str>, &'static str, Value)] = &[
        (
            "UserPromptSubmit",
            None,
            "ab-memory-hook",
            json!({
                "hooks": [{
                    "type": "command",
                    "command": format!("{}/ab-memory-hook", bin),
                    "timeout": 5
                }]
            }),
        ),
        (
            "UserPromptSubmit",
            None,
            "ab-instinct-observer-hook",
            json!({
                "hooks": [{
                    "type": "command",
                    "command": format!("{}/ab-instinct-observer-hook", bin),
                    "timeout": 5
                }]
            }),
        ),
        (
            "PostToolUse",
            None,
            "ab-instinct-observer-hook",
            json!({
                "hooks": [{
                    "type": "command",
                    "command": format!("{}/ab-instinct-observer-hook", bin),
                    "timeout": 5
                }]
            }),
        ),
        (
            "PreCompact",
            Some("manual"),
            "ab-precompact-hook",
            json!({
                "matcher": "manual",
                "hooks": [{
                    "type": "command",
                    "command": format!("{}/ab-precompact-hook", bin),
                    "timeout": 120,
                    "statusMessage": "Memory curator: saving insights before compact..."
                }]
            }),
        ),
        (
            "PreCompact",
            Some("auto"),
            "ab-precompact-hook",
            json!({
                "matcher": "auto",
                "hooks": [{
                    "type": "command",
                    "command": format!("{}/ab-precompact-hook", bin),
                    "timeout": 120,
                    "statusMessage": "Memory curator: saving insights before compact..."
                }]
            }),
        ),
        (
            "Stop",
            None,
            "ab-session-end-hook",
            json!({
                "hooks": [{
                    "type": "command",
                    "command": format!("{}/ab-session-end-hook", bin),
                    "timeout": 30
                }]
            }),
        ),
        (
            "SessionEnd",
            None,
            "ab-session-end-hook",
            json!({
                "hooks": [{
                    "type": "command",
                    "command": session_end_command,
                    "timeout": 150,
                    "statusMessage": "Agent-Bridge: saving session memories..."
                }]
            }),
        ),
    ];

    for (event, matcher, script_name, entry) in new_hooks {
        let arr = hooks_obj
            .entry(*event)
            .or_insert(json!([]))
            .as_array_mut()
            .context("Codex hook event entry is not an array")?;
        let already = arr.iter().any(|item| {
            let item_matcher = item.get("matcher").and_then(|m| m.as_str());
            if item_matcher != *matcher {
                return false;
            }
            item.get("hooks")
                .and_then(|h| h.as_array())
                .map(|hooks| {
                    hooks.iter().any(|h| {
                        h.get("command")
                            .and_then(|c| c.as_str())
                            .map(|c| c.contains(script_name))
                            .unwrap_or(false)
                    })
                })
                .unwrap_or(false)
        });

        if !already {
            arr.push(entry.clone());
        }
    }

    let out = serde_json::to_string_pretty(&settings).context("re-serialize Codex hooks")?;
    if let Some(parent) = hooks_path.parent() {
        fs::create_dir_all(parent).context("create Codex hooks directory")?;
    }
    fs::write(&hooks_path, out).with_context(|| format!("write {}", hooks_path.display()))?;
    println!(
        "  ✓  hooks        → {} (Agent-Bridge hooks merged)",
        hooks_path.display()
    );

    Ok(())
}

fn codex_home(home: &Path) -> PathBuf {
    std::env::var_os("CODEX_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| home.join(".codex"))
}

fn merged_tool_env(existing: Option<&Value>, client: &str, toolset: &str, profile: &str) -> Value {
    let mut env = existing
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_else(serde_json::Map::new);
    for key in MANAGED_TOOL_ENV_KEYS {
        env.remove(*key);
    }
    env.insert("AGENT_BRIDGE_CLIENT".to_string(), json!(client));
    env.insert("AGENT_BRIDGE_TOOLSET".to_string(), json!(toolset));
    env.insert("AGENT_BRIDGE_TOOL_PROFILE".to_string(), json!(profile));
    Value::Object(env)
}

/// Read `~/.gemini/settings.json`, replace or append the
/// `mcpServers.agent-bridge` entry, then write back while preserving
/// unrelated Gemini CLI settings.
fn merge_gemini_settings(home: &Path, bin_dst: &Path) -> Result<()> {
    let settings_path = home.join(".gemini/settings.json");

    let mut settings: Value = if settings_path.exists() {
        let raw = fs::read_to_string(&settings_path)
            .with_context(|| format!("read {}", settings_path.display()))?;
        serde_json::from_str(&raw).unwrap_or(json!({}))
    } else {
        json!({})
    };

    let root = settings
        .as_object_mut()
        .context("Gemini settings.json is not an object")?;
    let mcp_servers = root
        .entry("mcpServers")
        .or_insert(json!({}))
        .as_object_mut()
        .context("Gemini mcpServers is not an object")?;

    let agent_bridge_env = merged_tool_env(
        mcp_servers.get("agent-bridge").and_then(|v| v.get("env")),
        "gemini",
        "gemini-lean",
        "essential",
    );
    mcp_servers.insert(
        "agent-bridge".to_string(),
        json!({
            "command": bin_dst.display().to_string(),
            "args": ["mcp"],
            "env": agent_bridge_env
        }),
    );

    if let Some(parent) = settings_path.parent() {
        fs::create_dir_all(parent).context("create ~/.gemini")?;
    }
    let out = serde_json::to_string_pretty(&settings).context("re-serialize Gemini settings")?;
    fs::write(&settings_path, out).with_context(|| format!("write {}", settings_path.display()))?;
    println!(
        "  ✓  settings     → {} (MCP server merged)",
        settings_path.display()
    );

    Ok(())
}

fn print_manual_lifecycle_guidance(frontend: &str) {
    println!();
    println!("For session lifecycle ({frontend} do not provide PreCompact/Stop hooks),");
    println!("have the agent call these MCP tools manually:");
    println!("  • At session start  →  read agent-bridge://session/bootstrap");
    println!("                        (or call the session_bootstrap tool)");
    println!("  • Before summarising →  call session_curate(conversation_text=...)");
    println!("  • At session end    →  call session_finalize()");
}

fn escape_toml_basic_string(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

fn replace_toml_table(raw: &str, table: &str, block: &str) -> String {
    let header = format!("[{table}]");
    let mut out = String::new();
    let mut lines = raw.lines();
    let mut replaced = false;

    while let Some(line) = lines.next() {
        if line.trim() == header {
            if !out.ends_with('\n') && !out.is_empty() {
                out.push('\n');
            }
            out.push_str(block.trim_end());
            out.push('\n');
            replaced = true;

            for next in lines.by_ref() {
                if let Some(next_table) = toml_table_name(next) {
                    if next_table == table || next_table.starts_with(&format!("{table}.")) {
                        continue;
                    }
                    out.push('\n');
                    out.push_str(next);
                    out.push('\n');
                    break;
                }
            }
            continue;
        }

        out.push_str(line);
        out.push('\n');
    }

    if replaced {
        return out;
    }

    if !out.trim().is_empty() && !out.ends_with("\n\n") {
        if !out.ends_with('\n') {
            out.push('\n');
        }
        out.push('\n');
    }
    out.push_str(block.trim_end());
    out.push('\n');
    out
}

fn toml_table_body_lines<'a>(raw: &'a str, table: &str) -> Vec<&'a str> {
    let mut lines = Vec::new();
    let mut in_table = false;
    for line in raw.lines() {
        if let Some(next_table) = toml_table_name(line) {
            if in_table {
                break;
            }
            in_table = next_table == table;
            continue;
        }
        if in_table {
            lines.push(line);
        }
    }
    lines
}

fn ensure_toml_bool(raw: &str, table: &str, key: &str, value: bool) -> String {
    let header = format!("[{table}]");
    let assignment = format!("{key} = {value}");
    let mut out = String::new();
    let mut in_table = false;
    let mut table_seen = false;
    let mut key_written = false;

    for line in raw.lines() {
        if let Some(next_table) = toml_table_name(line) {
            if in_table && !key_written {
                out.push_str(&assignment);
                out.push('\n');
                key_written = true;
            }
            in_table = next_table == table;
            table_seen |= in_table;
        }

        if in_table {
            let trimmed = line.trim_start();
            if trimmed
                .strip_prefix(key)
                .and_then(|rest| rest.trim_start().strip_prefix('='))
                .is_some()
            {
                out.push_str(&assignment);
                out.push('\n');
                key_written = true;
                continue;
            }
        }

        out.push_str(line);
        out.push('\n');
    }

    if in_table && !key_written {
        out.push_str(&assignment);
        out.push('\n');
    } else if !table_seen {
        if !out.trim().is_empty() && !out.ends_with("\n\n") {
            if !out.ends_with('\n') {
                out.push('\n');
            }
            out.push('\n');
        }
        out.push_str(&header);
        out.push('\n');
        out.push_str(&assignment);
        out.push('\n');
    }

    out
}

fn remove_toml_key(raw: &str, table: &str, key: &str) -> String {
    let mut out = String::new();
    let mut in_table = false;

    for line in raw.lines() {
        if let Some(next_table) = toml_table_name(line) {
            in_table = next_table == table;
        }

        if in_table && toml_line_assigns_key(line, key) {
            continue;
        }

        out.push_str(line);
        out.push('\n');
    }

    out
}

fn toml_table_name(line: &str) -> Option<&str> {
    let trimmed = line.trim();
    let inner = trimmed.strip_prefix('[')?.strip_suffix(']')?.trim();
    if inner.is_empty() || inner.starts_with('[') || inner.ends_with(']') {
        return None;
    }
    Some(inner)
}

/// Read `~/.claude/settings.json`, add our three hooks if absent, write back.
///
/// We never overwrite an existing hook entry whose `command` already contains
/// "ab-memory-hook", "ab-precompact-hook", or "ab-session-end-hook".
fn merge_claude_settings(home: &Path, bin_dir: &Path) -> Result<()> {
    let settings_path = home.join(".claude/settings.json");

    let mut settings: Value = if settings_path.exists() {
        let raw = fs::read_to_string(&settings_path)
            .with_context(|| format!("read {}", settings_path.display()))?;
        serde_json::from_str(&raw).unwrap_or(json!({}))
    } else {
        json!({})
    };

    let hooks_obj = settings
        .as_object_mut()
        .context("settings.json is not an object")?
        .entry("hooks")
        .or_insert(json!({}))
        .as_object_mut()
        .context("hooks is not an object")?;

    let bin = bin_dir.to_string_lossy();

    let new_hooks: &[(&str, Option<&str>, Value)] = &[
        (
            "UserPromptSubmit",
            None,
            json!({
                "hooks": [{
                    "type": "command",
                    "command": format!("{}/ab-memory-hook", bin),
                    "timeout": 5,
                    "statusMessage": "Loading memory…"
                }]
            }),
        ),
        (
            "Stop",
            None,
            json!({
                "hooks": [{
                    "type": "command",
                    "command": format!("{}/ab-session-end-hook", bin),
                    "timeout": 30
                }]
            }),
        ),
        (
            "PreCompact",
            Some("manual"),
            json!({
                "matcher": "manual",
                "hooks": [{
                    "type": "command",
                    "command": format!("{}/ab-precompact-hook", bin),
                    "timeout": 120,
                    "statusMessage": "Memory curator: saving insights before compact…"
                }]
            }),
        ),
        (
            "PreCompact",
            Some("auto"),
            json!({
                "matcher": "auto",
                "hooks": [{
                    "type": "command",
                    "command": format!("{}/ab-precompact-hook", bin),
                    "timeout": 120,
                    "statusMessage": "Memory curator: saving insights before compact…"
                }]
            }),
        ),
    ];

    for (event, matcher, entry) in new_hooks {
        let arr = hooks_obj
            .entry(*event)
            .or_insert(json!([]))
            .as_array_mut()
            .context("hook event entry is not an array")?;

        // Dedupe by (script_name, matcher): PreCompact has separate manual/auto
        // entries that share the same script, so script-name alone is not enough.
        let script_name = script_name_for_event(event);
        let already = arr.iter().any(|item| {
            let item_matcher = item.get("matcher").and_then(|m| m.as_str());
            if item_matcher != *matcher {
                return false;
            }
            item.get("hooks")
                .and_then(|h| h.as_array())
                .map(|hooks| {
                    hooks.iter().any(|h| {
                        h.get("command")
                            .and_then(|c| c.as_str())
                            .map(|c| c.contains(script_name))
                            .unwrap_or(false)
                    })
                })
                .unwrap_or(false)
        });

        if !already {
            arr.push(entry.clone());
        }
    }

    // Write back with pretty-printing.
    let out = serde_json::to_string_pretty(&settings).context("re-serialize settings")?;
    if let Some(parent) = settings_path.parent() {
        fs::create_dir_all(parent).context("create ~/.claude")?;
    }
    fs::write(&settings_path, out).with_context(|| format!("write {}", settings_path.display()))?;
    println!(
        "  ✓  settings     → {} (hooks merged)",
        settings_path.display()
    );

    Ok(())
}

fn script_name_for_event(event: &str) -> &'static str {
    match event {
        "UserPromptSubmit" => "ab-memory-hook",
        "Stop" => "ab-session-end-hook",
        "SessionEnd" => "ab-session-end-hook",
        "PreCompact" => "ab-precompact-hook",
        _ => "",
    }
}

#[cfg(test)]
mod tests {
    use super::{
        ensure_toml_bool, merge_codex_config, merge_codex_hooks, merge_cursor_settings,
        merge_gemini_settings, remove_toml_key, replace_toml_table, CodexHost, CodexToolset,
        HOOK_PRECOMPACT, HOOK_SESSION_END,
    };
    use serde_json::{json, Value};
    use std::fs;

    #[test]
    fn appends_codex_mcp_table_when_missing() {
        let raw = "model = \"gpt-5.5\"\n\n[features]\nmulti_agent = true\n";
        let block = "[mcp_servers.agent-bridge]\ncommand = \"/tmp/agent-bridge\"\n";

        let out = replace_toml_table(raw, "mcp_servers.agent-bridge", block);

        assert!(out.contains("[features]\nmulti_agent = true"));
        assert!(out.contains("[mcp_servers.agent-bridge]\ncommand = \"/tmp/agent-bridge\""));
    }

    #[test]
    fn replaces_existing_codex_mcp_table_only() {
        let raw = "\
model = \"gpt-5.5\"

[mcp_servers.agent-bridge]
command = \"old\"
args = [\"mcp\"]

[mcp_servers.agent-bridge.env]
AGENT_BRIDGE_TOOL_PROFILE = \"all\"

[plugins.example]
enabled = true
";
        let block = "\
[mcp_servers.agent-bridge]
command = \"new\"

[mcp_servers.agent-bridge.env]
AGENT_BRIDGE_CLIENT = \"codex\"
AGENT_BRIDGE_TOOLSET = \"codex-essential\"
AGENT_BRIDGE_TOOL_PROFILE = \"essential\"
";

        let out = replace_toml_table(raw, "mcp_servers.agent-bridge", block);

        assert!(out.contains("[mcp_servers.agent-bridge]\ncommand = \"new\""));
        assert!(!out.contains("command = \"old\""));
        assert!(!out.contains("AGENT_BRIDGE_TOOL_PROFILE = \"all\""));
        assert!(out.contains("AGENT_BRIDGE_CLIENT = \"codex\""));
        assert!(out.contains("AGENT_BRIDGE_TOOLSET = \"codex-essential\""));
        assert!(out.contains("AGENT_BRIDGE_TOOL_PROFILE = \"essential\""));
        assert!(out.contains("[plugins.example]\nenabled = true"));
    }

    #[test]
    fn merge_codex_config_preserves_existing_agent_bridge_env() {
        let tmp = std::env::temp_dir().join(format!(
            "agent-bridge-codex-config-test-{}",
            std::process::id()
        ));
        let codex_dir = tmp.join(".codex");
        fs::create_dir_all(&codex_dir).unwrap();
        fs::write(
            codex_dir.join("config.toml"),
            r#"model = "gpt-5.5"
model_reasoning_effort = "xhigh"

[mcp_servers.agent-bridge]
command = "old"

[mcp_servers.agent-bridge.env]
AGENT_BRIDGE_CLIENT = "claude-code"
AGENT_BRIDGE_TOOLSET = "all-dev"
AGENT_BRIDGE_TOOL_PROFILE = "all"
AGENT_BRIDGE_CODEX_HOST = "stale-host"
AGENT_BRIDGE_MODEL = "stale-model"
AGENT_BRIDGE_MODEL_REASONING_EFFORT = "low"
AB_PET_TTS_VOICE = "Meijia"
AB_PET_TTS_RATE = "180"

[plugins.example]
enabled = true
"#,
        )
        .unwrap();

        merge_codex_config(
            &tmp,
            &tmp.join(".local/bin/agent-bridge"),
            true,
            CodexHost::Desktop,
            CodexToolset::Essential,
        )
        .unwrap();

        let out = fs::read_to_string(codex_dir.join("config.toml")).unwrap();
        assert!(out.contains("AGENT_BRIDGE_CLIENT = \"codex\""));
        assert!(out.contains("AGENT_BRIDGE_TOOLSET = \"codex-essential\""));
        assert!(out.contains("AGENT_BRIDGE_TOOL_PROFILE = \"essential\""));
        assert!(out.contains("AGENT_BRIDGE_CODEX_HOST = \"desktop\""));
        assert!(out.contains("AGENT_BRIDGE_MODEL = \"gpt-5.5\""));
        assert!(out.contains("AGENT_BRIDGE_MODEL_REASONING_EFFORT = \"xhigh\""));
        assert!(!out.contains("AGENT_BRIDGE_CLIENT = \"claude-code\""));
        assert!(!out.contains("AGENT_BRIDGE_TOOLSET = \"all-dev\""));
        assert!(!out.contains("AGENT_BRIDGE_TOOL_PROFILE = \"all\""));
        assert!(!out.contains("AGENT_BRIDGE_CODEX_HOST = \"stale-host\""));
        assert!(!out.contains("AGENT_BRIDGE_MODEL = \"stale-model\""));
        assert!(!out.contains("AGENT_BRIDGE_MODEL_REASONING_EFFORT = \"low\""));
        assert!(out.contains("AB_PET_TTS_VOICE = \"Meijia\""));
        assert!(out.contains("AB_PET_TTS_RATE = \"180\""));
        assert!(out.contains("[plugins.example]\nenabled = true"));

        fs::remove_dir_all(tmp).unwrap();
    }

    #[test]
    fn merge_codex_config_marks_cli_and_ide_hosts_without_forcing_hooks() {
        for (host, expected) in [(CodexHost::Cli, "cli"), (CodexHost::Ide, "ide")] {
            let tmp = std::env::temp_dir().join(format!(
                "agent-bridge-codex-host-test-{}-{}",
                expected,
                std::process::id()
            ));
            let codex_dir = tmp.join(".codex");
            fs::create_dir_all(&codex_dir).unwrap();

            merge_codex_config(
                &tmp,
                &tmp.join(".local/bin/agent-bridge"),
                false,
                host,
                CodexToolset::Essential,
            )
            .unwrap();

            let out = fs::read_to_string(codex_dir.join("config.toml")).unwrap();
            assert!(out.contains("AGENT_BRIDGE_CLIENT = \"codex\""));
            assert!(out.contains("AGENT_BRIDGE_TOOLSET = \"codex-essential\""));
            assert!(out.contains(&format!("AGENT_BRIDGE_CODEX_HOST = \"{expected}\"")));
            assert!(!out.contains("hooks = true"));
            assert!(!out.contains("codex_hooks = true"));

            fs::remove_dir_all(tmp).unwrap();
        }
    }

    #[test]
    fn merge_codex_config_can_write_lean_toolset() {
        let tmp = std::env::temp_dir().join(format!(
            "agent-bridge-codex-lean-test-{}",
            std::process::id()
        ));
        let codex_dir = tmp.join(".codex");
        fs::create_dir_all(&codex_dir).unwrap();

        merge_codex_config(
            &tmp,
            &tmp.join(".local/bin/agent-bridge"),
            true,
            CodexHost::Desktop,
            CodexToolset::Lean,
        )
        .unwrap();

        let out = fs::read_to_string(codex_dir.join("config.toml")).unwrap();
        assert!(out.contains("AGENT_BRIDGE_TOOLSET = \"codex-lean\""));
        assert!(out.contains("AGENT_BRIDGE_TOOL_PROFILE = \"essential\""));
        assert!(out.contains("AGENT_BRIDGE_CODEX_HOST = \"desktop\""));

        fs::remove_dir_all(tmp).unwrap();
    }

    #[test]
    fn enables_hooks_feature_when_missing() {
        let raw = "model = \"gpt-5.5\"\n\n[features]\nmulti_agent = true\n";

        let out = ensure_toml_bool(raw, "features", "hooks", true);

        assert!(out.contains("[features]\nmulti_agent = true\nhooks = true"));
    }

    #[test]
    fn replaces_existing_hooks_feature() {
        let raw = "[features]\nhooks = false\nmulti_agent = true\n";

        let out = ensure_toml_bool(raw, "features", "hooks", true);

        assert!(out.contains("hooks = true"));
        assert!(!out.contains("hooks = false"));
        assert!(out.contains("multi_agent = true"));
    }

    #[test]
    fn removes_deprecated_codex_hooks_feature() {
        let raw = "\
[features]
codex_hooks = true
multi_agent = true

[projects.\"/tmp/example\"]
trust_level = \"trusted\"
";

        let out = remove_toml_key(raw, "features", "codex_hooks");

        assert!(!out.contains("codex_hooks"));
        assert!(out.contains("[features]\nmulti_agent = true"));
        assert!(out.contains("[projects.\"/tmp/example\"]\ntrust_level = \"trusted\""));
    }

    #[test]
    fn merges_codex_hooks_while_preserving_existing_entries() {
        let tmp = std::env::temp_dir().join(format!(
            "agent-bridge-codex-hooks-test-{}",
            std::process::id()
        ));
        let codex_dir = tmp.join(".codex");
        let bin_dir = tmp.join(".local/bin");
        fs::create_dir_all(&codex_dir).unwrap();
        fs::create_dir_all(&bin_dir).unwrap();
        fs::write(
            codex_dir.join("hooks.json"),
            r#"{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"cmux codex-hook stop","timeout":10}]}]}}"#,
        )
        .unwrap();

        merge_codex_hooks(&tmp, &bin_dir).unwrap();
        merge_codex_hooks(&tmp, &bin_dir).unwrap();

        let raw = fs::read_to_string(codex_dir.join("hooks.json")).unwrap();
        assert!(raw.contains("cmux codex-hook stop"));
        assert!(raw.contains("ab-memory-hook"));
        assert!(raw.contains("ab-precompact-hook"));
        assert!(raw.contains("ab-instinct-observer-hook"));
        assert!(raw.contains("\"PostToolUse\""));
        assert!(raw.contains("AB_SESSION_END_CURATE=1"));
        assert!(raw.contains("\"SessionEnd\""));

        let parsed: Value = serde_json::from_str(&raw).unwrap();
        let hooks = parsed["hooks"].as_object().unwrap();
        let user_prompt = hooks["UserPromptSubmit"].as_array().unwrap();
        let post_tool = hooks["PostToolUse"].as_array().unwrap();
        assert_eq!(
            count_hook_commands(user_prompt, "ab-memory-hook"),
            1,
            "memory hook should not be duplicated"
        );
        assert_eq!(
            count_hook_commands(user_prompt, "ab-instinct-observer-hook"),
            1,
            "observer prompt hook should not be duplicated"
        );
        assert_eq!(
            count_hook_commands(post_tool, "ab-instinct-observer-hook"),
            1,
            "observer post-tool hook should not be duplicated"
        );

        fs::remove_dir_all(tmp).unwrap();
    }

    #[test]
    fn wrapper_detection_scans_past_long_header_comments() {
        let tmp = std::env::temp_dir().join(format!(
            "agent-bridge-wrapper-detect-test-{}",
            std::process::id()
        ));
        let bin_dir = tmp.join(".local/bin");
        fs::create_dir_all(&bin_dir).unwrap();
        let wrapper = bin_dir.join("agent-bridge");
        let long_header = "#".repeat(700);
        fs::write(
            &wrapper,
            format!(
                "#!/usr/bin/env bash\n{long_header}\nexec \"$HOME/.local/bin/agent-bridge.real\" \"$@\"\n"
            ),
        )
        .unwrap();

        assert!(super::is_env_wrapper_script(&wrapper));
        assert_eq!(
            super::binary_install_destination(&wrapper),
            bin_dir.join("agent-bridge.real")
        );

        fs::remove_dir_all(tmp).unwrap();
    }

    fn count_hook_commands(entries: &[Value], script_name: &str) -> usize {
        entries
            .iter()
            .flat_map(|entry| {
                entry
                    .get("hooks")
                    .and_then(|hooks| hooks.as_array())
                    .into_iter()
                    .flatten()
            })
            .filter(|hook| {
                hook.get("command")
                    .and_then(|command| command.as_str())
                    .map(|command| command.contains(script_name))
                    .unwrap_or(false)
            })
            .count()
    }

    #[test]
    fn hook_mcp_children_use_lifecycle_toolset() {
        assert!(HOOK_PRECOMPACT.contains("AGENT_BRIDGE_TOOLSET=hook-lifecycle"));
        assert!(HOOK_PRECOMPACT.contains("AGENT_BRIDGE_CLIENT=hook"));
        assert!(HOOK_PRECOMPACT.contains("AGENT_BRIDGE_MCP_SOURCE=hook"));
        assert!(HOOK_SESSION_END.contains("AGENT_BRIDGE_TOOLSET=hook-lifecycle"));
        assert!(HOOK_SESSION_END.contains("AGENT_BRIDGE_CLIENT=hook"));
        assert!(HOOK_SESSION_END.contains("AGENT_BRIDGE_MCP_SOURCE=hook"));
        assert!(!HOOK_SESSION_END.contains("AGENT_BRIDGE_TOOL_PROFILE=all"));
    }

    #[test]
    fn merges_gemini_mcp_server_while_preserving_settings() {
        let tmp =
            std::env::temp_dir().join(format!("agent-bridge-gemini-test-{}", std::process::id()));
        let settings_dir = tmp.join(".gemini");
        fs::create_dir_all(&settings_dir).unwrap();
        fs::write(
            settings_dir.join("settings.json"),
            r#"{"ui":{"theme":"Default"},"mcpServers":{"other":{"command":"old"},"agent-bridge":{"command":"old","env":{"AGENT_BRIDGE_TOOLSET":"all-dev","CUSTOM_ENV":"keep"}}}}"#,
        )
        .unwrap();

        merge_gemini_settings(&tmp, std::path::Path::new("/tmp/agent-bridge")).unwrap();
        let raw = fs::read_to_string(settings_dir.join("settings.json")).unwrap();
        let v: Value = serde_json::from_str(&raw).unwrap();
        let agent_bridge = &v["mcpServers"]["agent-bridge"];

        assert!(raw.contains("\"theme\": \"Default\""));
        assert!(raw.contains("\"other\""));
        assert_eq!(agent_bridge["command"], "/tmp/agent-bridge");
        assert_eq!(agent_bridge["args"], json!(["mcp"]));
        assert_eq!(agent_bridge["env"]["AGENT_BRIDGE_CLIENT"], "gemini");
        assert_eq!(agent_bridge["env"]["AGENT_BRIDGE_TOOLSET"], "gemini-lean");
        assert_eq!(
            agent_bridge["env"]["AGENT_BRIDGE_TOOL_PROFILE"],
            "essential"
        );
        assert_eq!(agent_bridge["env"]["CUSTOM_ENV"], "keep");

        let _ = fs::remove_dir_all(tmp);
    }

    #[test]
    fn merges_cursor_mcp_server_while_preserving_settings() {
        let tmp =
            std::env::temp_dir().join(format!("agent-bridge-cursor-test-{}", std::process::id()));
        let cursor_dir = tmp.join(".cursor");
        fs::create_dir_all(&cursor_dir).unwrap();
        fs::write(
            cursor_dir.join("mcp.json"),
            r#"{"mcpServers":{"other":{"command":"old"},"agent-bridge":{"command":"old","env":{"AGENT_BRIDGE_TOOLSET":"all-dev","CUSTOM_ENV":"keep"}}}}"#,
        )
        .unwrap();

        merge_cursor_settings(&tmp, std::path::Path::new("/tmp/agent-bridge")).unwrap();
        let raw = fs::read_to_string(cursor_dir.join("mcp.json")).unwrap();
        let v: Value = serde_json::from_str(&raw).unwrap();
        let agent_bridge = &v["mcpServers"]["agent-bridge"];

        assert!(raw.contains("\"other\""));
        assert_eq!(agent_bridge["command"], "/tmp/agent-bridge");
        assert_eq!(agent_bridge["args"], json!(["mcp"]));
        assert_eq!(agent_bridge["env"]["AGENT_BRIDGE_CLIENT"], "cursor");
        assert_eq!(
            agent_bridge["env"]["AGENT_BRIDGE_TOOLSET"],
            "claude-standard"
        );
        assert_eq!(agent_bridge["env"]["AGENT_BRIDGE_TOOL_PROFILE"], "standard");
        assert_eq!(agent_bridge["env"]["CUSTOM_ENV"], "keep");

        let _ = fs::remove_dir_all(tmp);
    }
}
