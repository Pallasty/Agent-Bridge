//! `agent-bridge setup` — one-shot installer.
//!
//! Two installation profiles:
//!
//! - `Frontend::ClaudeCode` (legacy default): copies the binary,
//!   writes the three hook scripts, and merges `UserPromptSubmit /
//!   Stop / PreCompact` entries into `~/.claude/settings.json`.
//! - `Frontend::Codex`: copies the binary and merges an
//!   `[mcp_servers.agent-bridge]` entry into `~/.codex/config.toml`.
//!   Codex does not expose Claude Code hook events, so hook scripts are
//!   skipped and session lifecycle tools are called manually.
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

/// Which frontend the setup is targeting. Drives whether hook scripts
/// and `~/.claude/settings.json` are written.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum Frontend {
    ClaudeCode,
    Warp,
    Auggie,
    Codex,
    GeminiCli,
    LocalCli,
}

pub fn run(frontend: Frontend) -> Result<()> {
    let home = home_dir().context("cannot determine $HOME")?;

    // ── 1. Install binary (always) ───────────────────────────────────────
    let bin_dir = home.join(".local/bin");
    fs::create_dir_all(&bin_dir).context("create ~/.local/bin")?;

    let bin_dst = bin_dir.join("agent-bridge");
    let bin_src = std::env::current_exe().context("current_exe")?;

    if bin_src != bin_dst {
        copy_executable_atomically(&bin_src, &bin_dst)?;
        println!("  ✓  binary      → {}", bin_dst.display());
    } else {
        println!("  ·  binary      already at {}", bin_dst.display());
    }

    match frontend {
        Frontend::ClaudeCode => install_claude_code(&home, &bin_dir),
        Frontend::Warp => install_warp(&bin_dst),
        Frontend::Auggie => install_auggie(&bin_dst),
        Frontend::Codex => install_codex(&home, &bin_dst),
        Frontend::GeminiCli => install_gemini_cli(&home, &bin_dst),
        Frontend::LocalCli => install_local_cli(&home, &bin_dst),
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
fn install_claude_code(home: &Path, bin_dir: &Path) -> Result<()> {
    // ── 2. Write hook scripts ────────────────────────────────────────────
    write_script(&bin_dir.join("ab-memory-hook"), HOOK_MEMORY)?;
    write_script(&bin_dir.join("ab-precompact-hook"), HOOK_PRECOMPACT)?;
    write_script(&bin_dir.join("ab-session-end-hook"), HOOK_SESSION_END)?;

    // ── 3. Merge Claude Code settings ────────────────────────────────────
    merge_claude_settings(home, bin_dir)?;

    println!();
    println!("Setup complete (claude-code profile).");
    println!();
    println!("Next steps:");
    println!("  1. Add ~/.local/bin to your PATH if it isn't already.");
    println!("  2. Start the daemon:  agent-bridge daemon &");
    println!("  3. Register as MCP:   claude mcp add agent-bridge agent-bridge mcp");
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

/// Codex profile: binary plus `~/.codex/config.toml` MCP registration.
///
/// Codex reads MCP server definitions from the `[mcp_servers]` table in
/// `config.toml`. It does not have Claude Code hook events, so this
/// profile deliberately skips:
///   - writing the three `ab-*-hook` shell scripts,
///   - rewriting `~/.claude/settings.json`.
fn install_codex(home: &Path, bin_dst: &Path) -> Result<()> {
    println!("  ·  hook scripts skipped (Codex has no equivalent hook events)");
    println!("  ·  ~/.claude/settings.json skipped (claude-code only)");

    merge_codex_config(home, bin_dst)?;

    println!();
    println!("Setup complete (codex profile).");
    println!();
    println!("Next steps in Codex:");
    println!("  1. Restart Codex or open a new Codex session so MCP servers reload.");
    println!("  2. Check the MCP/tools panel for the `agent-bridge` server.");
    println!();
    println!("For session lifecycle (Codex has no PreCompact/Stop hooks),");
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
fn install_local_cli(home: &Path, bin_dst: &Path) -> Result<()> {
    println!("  ·  hook scripts skipped (local CLI profile uses MCP config only)");
    println!("  ·  ~/.claude/settings.json skipped (claude-code hooks only)");

    merge_codex_config(home, bin_dst)?;
    merge_gemini_settings(home, bin_dst)?;
    let claude_registered = try_register_claude_mcp(bin_dst);

    println!();
    println!("Setup complete (local-cli profile).");
    println!();
    println!("Configured:");
    println!("  ✓ Codex      → ~/.codex/config.toml");
    println!("  ✓ Gemini CLI → ~/.gemini/settings.json");
    if claude_registered {
        println!("  ✓ Claude Code → MCP server registered");
    } else {
        println!("  · Claude Code → register manually if desired:");
        println!(
            "      claude mcp add -s user agent-bridge {} mcp",
            bin_dst.display()
        );
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

/// Best-effort: invoke `claude mcp add -s user agent-bridge <bin> mcp`.
///
/// Claude Code's CLI owns the exact config format/scope semantics, so
/// using the CLI is safer than editing Claude's files directly. The
/// local-CLI profile uses user scope so the server is available outside
/// the current project directory. Failure is non-fatal; setup prints the
/// manual command.
fn try_register_claude_mcp(bin_dst: &Path) -> bool {
    let output = std::process::Command::new("claude")
        .arg("mcp")
        .arg("add")
        .arg("-s")
        .arg("user")
        .arg("agent-bridge")
        .arg(bin_dst)
        .arg("mcp")
        .output();
    match output {
        Ok(o) if o.status.success() => true,
        Ok(o) => {
            let stderr = String::from_utf8_lossy(&o.stderr).trim().to_string();
            let stdout = String::from_utf8_lossy(&o.stdout).trim().to_string();
            let detail = if !stderr.is_empty() { stderr } else { stdout };
            if detail.contains("already exists in user config") || claude_mcp_get_agent_bridge() {
                println!("  ·  Claude Code MCP server already registered");
                true
            } else {
                println!(
                    "  ·  `claude mcp add` exited with {}; falling back to manual instructions{}",
                    o.status,
                    if detail.is_empty() {
                        String::new()
                    } else {
                        format!(" ({detail})")
                    }
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
fn merge_codex_config(home: &Path, bin_dst: &Path) -> Result<()> {
    let codex_home = std::env::var_os("CODEX_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| home.join(".codex"));
    let config_path = codex_home.join("config.toml");

    let raw = if config_path.exists() {
        fs::read_to_string(&config_path)
            .with_context(|| format!("read {}", config_path.display()))?
    } else {
        String::new()
    };

    let block = format!(
        r#"[mcp_servers.agent-bridge]
command = "{}"
args = ["mcp"]
enabled = true
startup_timeout_sec = 20
tool_timeout_sec = 300
supports_parallel_tool_calls = false
"#,
        escape_toml_basic_string(&bin_dst.display().to_string())
    );

    let updated = replace_toml_table(&raw, "mcp_servers.agent-bridge", &block);

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

    mcp_servers.insert(
        "agent-bridge".to_string(),
        json!({
            "command": bin_dst.display().to_string(),
            "args": ["mcp"]
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
                let trimmed = next.trim_start();
                if trimmed.starts_with('[') {
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
        "PreCompact" => "ab-precompact-hook",
        _ => "",
    }
}

#[cfg(test)]
mod tests {
    use super::{merge_gemini_settings, replace_toml_table};
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

[plugins.example]
enabled = true
";
        let block = "[mcp_servers.agent-bridge]\ncommand = \"new\"\n";

        let out = replace_toml_table(raw, "mcp_servers.agent-bridge", block);

        assert!(out.contains("[mcp_servers.agent-bridge]\ncommand = \"new\""));
        assert!(!out.contains("command = \"old\""));
        assert!(out.contains("[plugins.example]\nenabled = true"));
    }

    #[test]
    fn merges_gemini_mcp_server_while_preserving_settings() {
        let tmp =
            std::env::temp_dir().join(format!("agent-bridge-gemini-test-{}", std::process::id()));
        let settings_dir = tmp.join(".gemini");
        fs::create_dir_all(&settings_dir).unwrap();
        fs::write(
            settings_dir.join("settings.json"),
            r#"{"ui":{"theme":"Default"},"mcpServers":{"other":{"command":"old"}}}"#,
        )
        .unwrap();

        merge_gemini_settings(&tmp, std::path::Path::new("/tmp/agent-bridge")).unwrap();
        let raw = fs::read_to_string(settings_dir.join("settings.json")).unwrap();

        assert!(raw.contains("\"theme\": \"Default\""));
        assert!(raw.contains("\"other\""));
        assert!(raw.contains("\"agent-bridge\""));
        assert!(raw.contains("\"/tmp/agent-bridge\""));

        let _ = fs::remove_dir_all(tmp);
    }
}
