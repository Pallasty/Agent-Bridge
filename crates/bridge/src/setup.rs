//! `agent-bridge setup` — one-shot installer.
//!
//! Copies the binary to `~/.local/bin/agent-bridge`, writes three Claude Code
//! hook scripts, and merges the hook configuration into `~/.claude/settings.json`.

use anyhow::{Context, Result};
use serde_json::{json, Value};
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

// Hook scripts embedded at compile time from the hooks/ directory.
const HOOK_MEMORY: &str = include_str!("hooks/ab-memory-hook.sh");
const HOOK_PRECOMPACT: &str = include_str!("hooks/ab-precompact-hook.sh");
const HOOK_SESSION_END: &str = include_str!("hooks/ab-session-end-hook.sh");
const CURATOR_SETTINGS: &str = include_str!("hooks/memory-curator-settings.json");

pub fn run() -> Result<()> {
    let home = home_dir().context("cannot determine $HOME")?;

    // ── 1. Install binary ─────────────────────────────────────────────────────
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

    // ── 2. Write hook scripts ─────────────────────────────────────────────────
    write_script(&bin_dir.join("ab-memory-hook"), HOOK_MEMORY)?;
    write_script(&bin_dir.join("ab-precompact-hook"), HOOK_PRECOMPACT)?;
    write_script(&bin_dir.join("ab-session-end-hook"), HOOK_SESSION_END)?;

    // ── 3. Write curator settings ─────────────────────────────────────────────
    let cfg_dir = home.join(".config/agent-bridge");
    fs::create_dir_all(&cfg_dir).context("create ~/.config/agent-bridge")?;
    let cfg_path = cfg_dir.join("memory-curator-settings.json");
    fs::write(&cfg_path, CURATOR_SETTINGS)
        .with_context(|| format!("write {}", cfg_path.display()))?;
    println!("  ✓  curator cfg  → {}", cfg_path.display());

    // ── 4. Merge Claude Code settings ─────────────────────────────────────────
    merge_claude_settings(&home, &bin_dir)?;

    println!();
    println!("Setup complete.");
    println!();
    println!("Next steps:");
    println!("  1. Add ~/.local/bin to your PATH if it isn't already.");
    println!("  2. Start the daemon:  agent-bridge daemon &");
    println!("  3. Register as MCP:   claude mcp add agent-bridge agent-bridge mcp");
    println!("  4. (Optional) Clone the memory-sync repo:");
    println!("       git clone <your-memory-repo> ~/agent-bridge-memory");
    println!("  5. Restart Claude Code — the hooks take effect on the next session.");

    Ok(())
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
