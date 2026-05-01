//! `agent-bridge setup` — one-shot installer.
//!
//! Two installation profiles:
//!
//! - `Frontend::ClaudeCode` (legacy default): copies the binary,
//!   writes the three hook scripts, and merges `UserPromptSubmit /
//!   Stop / PreCompact` entries into `~/.claude/settings.json`.
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
}

pub fn run(frontend: Frontend) -> Result<()> {
    let home = home_dir().context("cannot determine $HOME")?;

    // ── 1. Install binary (always) ───────────────────────────────────────
    let bin_dir = home.join(".local/bin");
    fs::create_dir_all(&bin_dir).context("create ~/.local/bin")?;

    let bin_dst = bin_dir.join("agent-bridge");
    let bin_src = std::env::current_exe().context("current_exe")?;

    if bin_src != bin_dst {
        fs::copy(&bin_src, &bin_dst)
            .with_context(|| format!("copy binary → {}", bin_dst.display()))?;
        let mut perms = fs::metadata(&bin_dst)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&bin_dst, perms)?;
        println!("  ✓  binary      → {}", bin_dst.display());
    } else {
        println!("  ·  binary      already at {}", bin_dst.display());
    }

    match frontend {
        Frontend::ClaudeCode => install_claude_code(&home, &bin_dir),
        Frontend::Warp => install_warp(&bin_dst),
        Frontend::Auggie => install_auggie(&bin_dst),
    }
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
    println!("  4. (Optional) Clone the memory-sync repo (private):");
    println!(
        "       git clone git@github.com:pallasting/agent-bridge-memory.git ~/agent-bridge-memory"
    );
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
