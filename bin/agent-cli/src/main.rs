use ab_bridge::default_socket_path;
use ab_core::{RpcRequest, RpcResponse};
use ab_store::{
    default_db_path, CompactPolicy, MemoryListSort, MemoryRecord, SqliteStore, StateStore,
};
use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use serde_json::{json, Value};
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};
use tokio::net::UnixStream;

#[derive(Parser, Debug)]
#[command(version, about = "agent-bridge command line client")]
struct Cli {
    /// Override the bridge socket path.
    #[arg(long, env = "AGENT_BRIDGE_SOCKET")]
    socket: Option<PathBuf>,

    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand, Debug)]
enum Cmd {
    /// Health check — round-trips system.ping.
    Ping,

    /// Print the bridge's advertised methods.
    Capabilities,

    /// Send a desktop notification.
    Notify {
        /// Notification title.
        #[arg(short, long, default_value = "agent-bridge")]
        title: String,

        /// Notification body (positional).
        body: String,

        /// info | success | warning | error | attention
        #[arg(short, long, default_value = "info")]
        severity: String,
    },

    /// Show recent notifications from the persistent store.
    History {
        /// How many entries to print (most recent first).
        #[arg(short = 'n', long, default_value_t = 20)]
        limit: u32,

        /// Print raw JSON instead of the human-readable table.
        #[arg(long)]
        json: bool,
    },

    /// OSC sequence helpers (parse arbitrary text or emit a demo sequence).
    Osc {
        #[command(subcommand)]
        cmd: OscCmd,
    },

    /// Terminal multiplexer commands (backend auto-selected: wezterm | kitty | zellij).
    Term {
        #[command(subcommand)]
        cmd: TermCmd,
    },

    /// Self-memory commands. Operate directly on the SQLite store (no daemon
    /// required), so they work offline and from cron jobs. Use `--db` to
    /// point at a non-default state.db (rare; tests).
    Memory {
        /// Override the state.db path.
        #[arg(long, env = "AGENT_BRIDGE_DB")]
        db: Option<PathBuf>,

        #[command(subcommand)]
        cmd: MemoryCmd,
    },

    /// Self-evolution: propose and track improvements to agent-bridge itself.
    /// Proposals become isolated git worktree branches ready for review/merge.
    Evolve {
        /// Override the agent-bridge repo root (default: inferred via `git rev-parse`).
        #[arg(long, env = "AGENT_BRIDGE_REPO")]
        repo: Option<PathBuf>,

        /// Override the state.db path.
        #[arg(long, env = "AGENT_BRIDGE_DB")]
        db: Option<PathBuf>,

        #[command(subcommand)]
        cmd: EvolveCmd,
    },
}

#[derive(Subcommand, Debug)]
enum MemoryCmd {
    /// List memories. Defaults to recent-first.
    List {
        #[arg(long)]
        kind: Option<String>,
        #[arg(long, default_value = "recent")]
        sort: String,
        #[arg(short = 'n', long, default_value_t = 20)]
        limit: u32,
        #[arg(long)]
        json: bool,
    },
    /// Fetch one memory by exact key (bumps access_count).
    Get {
        key: String,
        #[arg(long)]
        json: bool,
    },
    /// Substring/FTS search across key + content.
    Search {
        query: String,
        #[arg(long, value_delimiter = ',')]
        tags: Vec<String>,
        #[arg(short = 'n', long, default_value_t = 10)]
        limit: u32,
        #[arg(long)]
        json: bool,
    },
    /// Save (insert-or-replace) a memory.
    Save {
        key: String,
        #[arg(long, default_value = "note")]
        kind: String,
        /// Memory body. If omitted, read from stdin.
        #[arg(long)]
        content: Option<String>,
        #[arg(long, value_delimiter = ',')]
        tags: Vec<String>,
        #[arg(long, value_delimiter = ',')]
        related: Vec<String>,
        #[arg(long)]
        scope: Option<String>,
    },
    /// Delete a memory by key.
    Delete { key: String },
    /// Visualise the memory graph rooted at KEY.
    ///
    /// Performs BFS up to DEPTH hops, printing each reachable edge with its
    /// type, direction (outgoing → / incoming ←), weight, and decayed energy.
    /// Use this to audit edge quality after `memory_link` calls.
    ///
    /// Example:
    ///   agent-cli memory graph decision_foo --depth 2
    Graph {
        /// Root memory key to start traversal from.
        key: String,
        /// BFS depth – how many hops to traverse (default 2).
        #[arg(short, long, default_value_t = 2)]
        depth: u8,
        /// Energy decay factor applied at each hop (default 0.7).
        #[arg(long, default_value_t = 0.7)]
        decay: f64,
        /// Minimum energy threshold – prune edges below this (default 0.05).
        #[arg(long, default_value_t = 0.05)]
        min_energy: f64,
        /// Print raw JSON instead of the tree view.
        #[arg(long)]
        json: bool,
    },
    /// Prune low-value memories. With no thresholds, applies the v0.8
    /// healthy default (`min_uses=2 AND older_than_days=90`).
    Compact {
        #[arg(long)]
        min_uses: Option<u64>,
        #[arg(long)]
        older_than_days: Option<i64>,
        #[arg(long)]
        dry_run: bool,
    },

    /// Automatically curate memories from session_handoff records (or any
    /// source kind). Aggregates the N most important source memories, runs
    /// the two-pass curate pipeline (marker + implicit lexical scoring), and
    /// persists extracted lessons / decisions / facts. Duplicate keys are
    /// always skipped, so this is safe to call repeatedly from cron or an
    /// Oz cloud schedule.
    ///
    /// Multi-device pipeline:
    ///   1. Import merged JSONL into a temp DB:
    ///        agent-bridge memory --db /tmp/curate.db \
    ///          import /path/to/memories.jsonl
    ///   2. Run auto-curation on the temp DB:
    ///        agent-bridge memory --db /tmp/curate.db auto-curate
    ///   3. Export curated results back to JSONL:
    ///        agent-bridge memory --db /tmp/curate.db \
    ///          export --path /path/to/curated.jsonl
    AutoCurate {
        /// Memory kind used as source material (default: session_handoff).
        #[arg(long, default_value = "session_handoff")]
        source_kind: String,

        /// Number of source memories to aggregate, sorted by importance (1–20).
        #[arg(long, default_value_t = 5)]
        max_sources: u32,

        /// Max structured memories to extract from the aggregated text (1–50).
        #[arg(long, default_value_t = 12)]
        max_items: usize,

        /// Comma-separated kinds to suppress from extracted output.
        /// Default: session_handoff (avoids re-generating handoff records).
        #[arg(long, value_delimiter = ',', default_value = "session_handoff")]
        exclude_kinds: Vec<String>,

        /// Preview extracted candidates without writing to the store.
        #[arg(long)]
        dry_run: bool,

        /// Override Pass-2 minimum signal score (0.15–0.95).
        #[arg(long)]
        score_threshold: Option<f64>,

        /// Override Pass-2 Jaccard dedup threshold (0.1–0.95).
        #[arg(long)]
        dedup_jaccard: Option<f64>,

        /// Print machine-readable JSON summary.
        #[arg(long)]
        json: bool,
    },
}

#[derive(Subcommand, Debug)]
enum EvolveCmd {
    /// Propose a fix for friction hit during a session.
    /// Creates an isolated git worktree branch + records the proposal in memory.
    Propose {
        /// One-sentence description of the friction / bug / limitation encountered.
        #[arg(long)]
        issue: String,

        /// Proposed fix or approach (optional; can be added later).
        #[arg(long)]
        fix: Option<String>,

        /// Path to a .diff / .patch file to apply in the worktree (optional).
        #[arg(long)]
        patch: Option<PathBuf>,

        /// Dry-run: print what would happen, create nothing.
        #[arg(long)]
        dry_run: bool,
    },
    /// List open evolution proposals.
    List {
        /// Print raw JSON.
        #[arg(long)]
        json: bool,
    },
    /// Apply a targeted file edit inside an evolution worktree and commit it.
    ///
    /// Two modes:
    ///   Patch mode  (default): reads unified diff from stdin or --patch.
    ///   Edit mode   (--file + --old + --new): exact string replacement — no
    ///               diff required; I read the file, replace, write, and commit.
    ///
    /// Creates the worktree branch if --key names an existing proposal;
    /// otherwise --issue is required to create a new proposal on the fly.
    Fix {
        /// Memory key of an existing evolve proposal (from `evolve list`).
        /// If omitted, --issue is required to create a new proposal on the fly.
        #[arg(long)]
        key: Option<String>,

        /// Issue description (required when --key is not given).
        #[arg(long)]
        issue: Option<String>,

        /// Commit message suffix (default: derived from issue/key).
        #[arg(long)]
        message: Option<String>,

        // --- Edit mode (all three required together) ---
        /// [Edit mode] Repo-relative path of the file to edit in the worktree.
        #[arg(long)]
        file: Option<PathBuf>,

        /// [Edit mode] Exact string to find (must appear exactly once).
        #[arg(long)]
        old: Option<String>,

        /// [Edit mode] Replacement string.
        #[arg(long)]
        new: Option<String>,

        // --- Patch mode ---
        /// [Patch mode] Path to .diff file. If omitted (and not edit mode), reads from stdin.
        #[arg(long)]
        patch: Option<PathBuf>,

        /// Dry-run: show what would be applied, create nothing.
        #[arg(long)]
        dry_run: bool,
    },
    /// Mark a proposal as closed (merged/resolved) in the memory store.
    Close {
        /// Memory key of the proposal to close (from `evolve list`).
        key: String,
        /// Optional note about how it was resolved.
        #[arg(long)]
        note: Option<String>,
    },
}

#[derive(Subcommand, Debug)]
enum OscCmd {
    /// Parse a string for OSC notification sequences and dispatch them.
    /// Use `\\x1b` / `\\a` / `\\\\` etc. — backslash escapes are decoded.
    Parse {
        /// Raw text containing one or more OSC sequences.
        raw: String,
    },
    /// Emit a sample OSC 9 / 777 / 99 sequence and dispatch it.
    Demo {
        /// 9 | 777 | 99
        #[arg(default_value = "9")]
        code: String,
    },
}

#[derive(Subcommand, Debug)]
enum TermCmd {
    /// List panes from the active terminal backend.
    List,
    /// Send keystrokes to a pane.
    SendKeys {
        /// Pane id.
        pane: String,
        /// Text to send.
        keys: String,
    },
    /// Split a pane horizontally or vertically.
    Split {
        /// Pane id.
        pane: String,
        /// horizontal | vertical
        #[arg(default_value = "vertical")]
        dir: String,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    let socket = cli.socket.unwrap_or_else(default_socket_path);

    // Memory commands talk directly to SQLite — no daemon required.
    if let Cmd::Memory { db, cmd } = cli.cmd {
        let path = db.unwrap_or_else(default_db_path);
        return run_memory(&path, cmd).await;
    }

    // Evolve commands: SQLite + git worktree, no daemon required.
    if let Cmd::Evolve { repo, db, cmd } = cli.cmd {
        let db_path = db.unwrap_or_else(default_db_path);
        return run_evolve(repo, &db_path, cmd).await;
    }

    // History has its own renderer; everything else just dumps JSON-RPC response.
    if let Cmd::History {
        limit,
        json: as_json,
    } = cli.cmd
    {
        let req = RpcRequest::new(1, "notifications.recent", Some(json!({ "limit": limit })));
        let resp = call(&socket, req).await?;
        if !resp.ok {
            println!("{}", serde_json::to_string_pretty(&resp)?);
            std::process::exit(1);
        }
        if as_json {
            println!("{}", serde_json::to_string_pretty(&resp)?);
        } else {
            render_history(&resp.result.unwrap_or(Value::Null));
        }
        return Ok(());
    }

    let (method, params) = match cli.cmd {
        Cmd::Ping => ("system.ping", None),
        Cmd::Capabilities => ("system.capabilities", None),
        Cmd::Notify {
            title,
            body,
            severity,
        } => (
            "notify.send",
            Some(json!({ "title": title, "body": body, "severity": severity })),
        ),
        Cmd::Osc {
            cmd: OscCmd::Parse { raw },
        } => ("osc.parse", Some(json!({ "raw": decode_escapes(&raw) }))),
        Cmd::Osc {
            cmd: OscCmd::Demo { code },
        } => ("osc.parse", Some(json!({ "raw": demo_payload(&code) }))),
        Cmd::Term { cmd: TermCmd::List } => ("terminal.list", None),
        Cmd::Term {
            cmd: TermCmd::SendKeys { pane, keys },
        } => (
            "terminal.send_keys",
            Some(json!({ "pane": pane, "keys": keys })),
        ),
        Cmd::Term {
            cmd: TermCmd::Split { pane, dir },
        } => ("terminal.split", Some(json!({ "pane": pane, "dir": dir }))),
        Cmd::History { .. } | Cmd::Memory { .. } | Cmd::Evolve { .. } => unreachable!(),
    };

    let req = RpcRequest::new(1, method, params);
    let resp = call(&socket, req).await?;

    println!("{}", serde_json::to_string_pretty(&resp)?);
    if !resp.ok {
        std::process::exit(1);
    }
    Ok(())
}

fn render_history(result: &Value) {
    let empty = Vec::new();
    let rows = result
        .get("notifications")
        .and_then(|v| v.as_array())
        .unwrap_or(&empty);

    if rows.is_empty() {
        println!("(no notifications yet)");
        return;
    }

    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);

    println!(
        "{:>6}  {:<10}  {:<10}  {}",
        "AGE", "SEVERITY", "SOURCE", "TITLE — BODY"
    );
    println!("{}", "-".repeat(78));
    for row in rows {
        let ts = row.get("ts").and_then(|v| v.as_i64()).unwrap_or(0);
        let age = format_age(now - ts);
        let event = row.get("event").cloned().unwrap_or(Value::Null);
        let severity = event
            .get("severity")
            .and_then(|v| v.as_str())
            .unwrap_or("?");
        let source = event.get("source").and_then(|v| v.as_str()).unwrap_or("?");
        let title = event.get("title").and_then(|v| v.as_str()).unwrap_or("");
        let body = event.get("body").and_then(|v| v.as_str()).unwrap_or("");
        let line = if body.is_empty() {
            title.to_string()
        } else {
            format!("{title} — {body}")
        };
        println!(
            "{:>6}  {:<10}  {:<10}  {}",
            age,
            severity,
            source,
            truncate(&line, 50)
        );
    }
}

fn format_age(secs: i64) -> String {
    if secs < 0 {
        return "now".into();
    }
    if secs < 60 {
        return format!("{secs}s");
    }
    if secs < 3600 {
        return format!("{}m", secs / 60);
    }
    if secs < 86400 {
        return format!("{}h", secs / 3600);
    }
    format!("{}d", secs / 86400)
}

/// Decode common backslash escape sequences (`\x1b`, `\a`, `\n`, `\\`) so users
/// can paste OSC payloads directly on the command line without shell heroics.
fn decode_escapes(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        if c != '\\' {
            out.push(c);
            continue;
        }
        match chars.next() {
            Some('x') => {
                let h1 = chars.next();
                let h2 = chars.next();
                if let (Some(a), Some(b)) = (h1, h2) {
                    if let Ok(byte) = u8::from_str_radix(&format!("{a}{b}"), 16) {
                        out.push(byte as char);
                        continue;
                    }
                }
                out.push('\\');
                out.push('x');
                if let Some(a) = h1 {
                    out.push(a);
                }
                if let Some(b) = h2 {
                    out.push(b);
                }
            }
            Some('a') => out.push('\x07'),
            Some('n') => out.push('\n'),
            Some('t') => out.push('\t'),
            Some('r') => out.push('\r'),
            Some('e') | Some('E') => out.push('\x1b'),
            Some('\\') => out.push('\\'),
            Some(other) => {
                out.push('\\');
                out.push(other);
            }
            None => out.push('\\'),
        }
    }
    out
}

fn demo_payload(code: &str) -> String {
    match code {
        "9" => "\x1b]9;Hello from OSC 9 demo\x07".into(),
        "777" => "\x1b]777;notify;agent-bridge demo;OSC 777 round-trip\x07".into(),
        "99" => {
            "\x1b]99;{\"title\":\"OSC 99 demo\",\"body\":\"json payload + severity\",\"severity\":\"warning\"}\x07".into()
        }
        _ => format!("\x1b]9;unknown demo code: {code}\x07"),
    }
}

fn truncate(s: &str, max: usize) -> String {
    let chars: Vec<char> = s.chars().collect();
    if chars.len() <= max {
        s.to_string()
    } else {
        let head: String = chars.iter().take(max - 1).collect();
        format!("{head}…")
    }
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn parse_sort(s: &str) -> Result<MemoryListSort> {
    match s {
        "recent" => Ok(MemoryListSort::Recent),
        "frequent" => Ok(MemoryListSort::Frequent),
        "newest" => Ok(MemoryListSort::Newest),
        other => bail!("unknown sort '{other}' (expected: recent | frequent | newest)"),
    }
}

fn find_repo_root(hint: Option<PathBuf>) -> Result<PathBuf> {
    if let Some(p) = hint {
        return Ok(p);
    }
    let out = std::process::Command::new("git")
        .args(["rev-parse", "--show-toplevel"])
        .output()
        .context("git rev-parse --show-toplevel failed (is git installed?)")?;
    if !out.status.success() {
        bail!("not inside a git repo; use --repo to specify the agent-bridge root");
    }
    let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
    Ok(PathBuf::from(s))
}

fn slugify(s: &str) -> String {
    s.chars()
        .map(|c| {
            if c.is_alphanumeric() {
                c.to_ascii_lowercase()
            } else {
                '-'
            }
        })
        .collect::<String>()
        .split('-')
        .filter(|p| !p.is_empty())
        .collect::<Vec<_>>()
        .join("-")
        .chars()
        .take(40)
        .collect()
}

async fn run_evolve(
    repo_hint: Option<PathBuf>,
    db_path: &std::path::Path,
    cmd: EvolveCmd,
) -> Result<()> {
    match cmd {
        EvolveCmd::Propose {
            issue,
            fix,
            patch,
            dry_run,
        } => {
            let repo = find_repo_root(repo_hint)?;

            // Generate branch / worktree names.
            let now = chrono_date();
            let slug = slugify(&issue);
            let branch = format!("evolution/{now}-{slug}");
            let wt_name = format!("agent-bridge-evolve-{now}-{slug}");
            let wt_path = repo.parent().unwrap_or(&repo).join(&wt_name);

            println!("Evolution proposal");
            println!("  issue   : {issue}");
            if let Some(f) = &fix {
                println!("  fix     : {f}");
            }
            println!("  branch  : {branch}");
            println!("  worktree: {}", wt_path.display());
            if let Some(p) = &patch {
                println!("  patch   : {}", p.display());
            }

            if dry_run {
                println!("\n(dry-run — nothing created)");
                return Ok(());
            }

            // Create the worktree branch.
            let status = std::process::Command::new("git")
                .args([
                    "-C",
                    repo.to_str().unwrap_or("."),
                    "worktree",
                    "add",
                    wt_path.to_str().unwrap_or("."),
                    "-b",
                    &branch,
                ])
                .status()
                .context("git worktree add")?;
            if !status.success() {
                bail!("git worktree add failed (see above)");
            }

            // Apply patch if supplied.
            if let Some(patch_path) = &patch {
                let patch_abs = std::fs::canonicalize(patch_path)
                    .with_context(|| format!("patch file not found: {}", patch_path.display()))?;
                let apply = std::process::Command::new("git")
                    .args([
                        "-C",
                        wt_path.to_str().unwrap_or("."),
                        "apply",
                        "--index",
                        patch_abs.to_str().unwrap_or("."),
                    ])
                    .status()
                    .context("git apply")?;
                if !apply.success() {
                    eprintln!("warning: git apply failed; worktree created but patch not applied");
                } else {
                    println!("patch applied");
                }
            }

            // Record proposal in memory store.
            let store: Arc<dyn StateStore> = Arc::new(
                SqliteStore::open(db_path)
                    .await
                    .with_context(|| format!("open SQLite store at {db_path:?}"))?,
            );
            let key = format!("evolve_{now}_{slug}");
            let content = format!(
                "**Issue**: {issue}\n\n**Fix**: {}\n\n**Branch**: {branch}\n**Worktree**: {}",
                fix.as_deref().unwrap_or("(not yet specified)"),
                wt_path.display(),
            );
            let now_s = now_secs();
            let rec = MemoryRecord {
                key: key.clone(),
                kind: "evolution".to_string(),
                content,
                tags: vec!["evolution".to_string(), "open".to_string()],
                related_keys: vec![],
                scope: None,
                created_at: now_s,
                updated_at: now_s,
                last_accessed_at: now_s,
                access_count: 0,
                importance: 0.5,
                status: "active".to_string(),
                trigger_pattern: None,
            };
            store.memory_save(&rec).await?;

            println!("\n✓ proposal recorded as memory key: {key}");
            println!("\nNext steps:");
            println!("  cd {}", wt_path.display());
            println!("  # make changes, then:");
            println!("  git add -p && git commit -m \"evolve: {slug}\"");
            println!("  # when ready for review, notify user to merge or push");
        }

        EvolveCmd::Fix {
            key,
            issue,
            message,
            file,
            old,
            new,
            patch,
            dry_run,
        } => {
            let repo = find_repo_root(repo_hint)?;
            let store: Arc<dyn StateStore> = Arc::new(
                SqliteStore::open(db_path)
                    .await
                    .with_context(|| format!("open SQLite store at {db_path:?}"))?,
            );

            // Resolve or create the proposal record.
            let (branch, wt_path, mem_key, issue_text) = if let Some(k) = &key {
                let rec = store
                    .memory_get(k)
                    .await?
                    .with_context(|| format!("no evolution proposal found for key '{k}'"))?;
                // Extract branch from content.
                let branch = rec
                    .content
                    .lines()
                    .find(|l| l.starts_with("**Branch**:"))
                    .and_then(|l| l.strip_prefix("**Branch**: "))
                    .map(str::to_string)
                    .with_context(|| "proposal record missing **Branch** field")?;
                let wt_name = branch.strip_prefix("evolution/").unwrap_or(&branch);
                let wt = repo
                    .parent()
                    .unwrap_or(&repo)
                    .join(format!("agent-bridge-evolve-{wt_name}"));
                let issue_text = rec
                    .content
                    .lines()
                    .find(|l| l.starts_with("**Issue**:"))
                    .and_then(|l| l.strip_prefix("**Issue**: "))
                    .unwrap_or(&rec.key)
                    .to_string();
                (branch, wt, k.clone(), issue_text)
            } else {
                let iss = issue
                    .as_deref()
                    .context("--issue required when --key not given")?;
                let now = chrono_date();
                let slug = slugify(iss);
                let branch = format!("evolution/{now}-{slug}");
                let wt_name = format!("agent-bridge-evolve-{now}-{slug}");
                let wt = repo.parent().unwrap_or(&repo).join(&wt_name);
                let k = format!("evolve_{now}_{slug}");
                (branch, wt, k, iss.to_string())
            };

            let commit_msg = message.unwrap_or_else(|| {
                let slug = slugify(&issue_text);
                format!("evolve: {}", &slug[..slug.len().min(60)])
            });

            // Determine mode: edit (--file+--old+--new) or patch (stdin/--patch).
            let edit_mode = file.is_some() || old.is_some() || new.is_some();
            if edit_mode && (file.is_none() || old.is_none() || new.is_none()) {
                bail!("edit mode requires all three of --file, --old, and --new");
            }

            println!("Evolution fix");
            println!("  key     : {mem_key}");
            println!("  branch  : {branch}");
            println!("  worktree: {}", wt_path.display());
            println!("  commit  : {commit_msg}");
            if edit_mode {
                println!("  mode    : edit (--file/--old/--new)");
            }

            if dry_run {
                if edit_mode {
                    println!("\n  file : {}", file.as_ref().unwrap().display());
                    println!("  old  : {:?}", old.as_deref().unwrap());
                    println!("  new  : {:?}", new.as_deref().unwrap());
                } else {
                    let patch_bytes = match &patch {
                        Some(p) => std::fs::read(p)
                            .with_context(|| format!("read patch file {}", p.display()))?,
                        None => {
                            use std::io::Read;
                            let mut buf = Vec::new();
                            std::io::stdin().read_to_end(&mut buf)?;
                            buf
                        }
                    };
                    println!("\npatch preview ({} bytes):", patch_bytes.len());
                    println!(
                        "{}",
                        String::from_utf8_lossy(&patch_bytes)
                            .chars()
                            .take(800)
                            .collect::<String>()
                    );
                }
                println!("\n(dry-run — nothing created)");
                return Ok(());
            }

            // Create worktree if it doesn't exist yet.
            if !wt_path.exists() {
                let status = std::process::Command::new("git")
                    .args([
                        "-C",
                        repo.to_str().unwrap_or("."),
                        "worktree",
                        "add",
                        wt_path.to_str().unwrap_or("."),
                        "-b",
                        &branch,
                    ])
                    .status()
                    .context("git worktree add")?;
                if !status.success() {
                    bail!("git worktree add failed");
                }
            }

            if edit_mode {
                // Edit mode: read file, replace, write, git add.
                let rel_path = file.unwrap();
                let abs_path = wt_path.join(&rel_path);
                let src = std::fs::read_to_string(&abs_path)
                    .with_context(|| format!("read {}", abs_path.display()))?;
                let old_str = old.unwrap();
                let new_str = new.unwrap();
                let count = src.matches(old_str.as_str()).count();
                if count == 0 {
                    bail!("--old string not found in {}", rel_path.display());
                }
                if count > 1 {
                    bail!(
                        "--old string appears {count} times in {} — must be unique",
                        rel_path.display()
                    );
                }
                let result = src.replacen(old_str.as_str(), &new_str, 1);
                std::fs::write(&abs_path, result)?;
                let add = std::process::Command::new("git")
                    .args([
                        "-C",
                        wt_path.to_str().unwrap_or("."),
                        "add",
                        rel_path.to_str().unwrap_or("."),
                    ])
                    .status()
                    .context("git add")?;
                if !add.success() {
                    bail!("git add failed");
                }
                println!("edit applied: {}", rel_path.display());
            } else {
                // Patch mode: read diff from file or stdin, apply via git apply.
                let patch_bytes = match &patch {
                    Some(p) => std::fs::read(p)
                        .with_context(|| format!("read patch file {}", p.display()))?,
                    None => {
                        use std::io::Read;
                        let mut buf = Vec::new();
                        std::io::stdin().read_to_end(&mut buf)?;
                        buf
                    }
                };
                if patch_bytes.trim_ascii().is_empty() {
                    bail!("patch is empty — pipe a unified diff or use --patch <file>");
                }
                let tmp = wt_path.join(".evolve_patch.diff");
                std::fs::write(&tmp, &patch_bytes)?;
                let apply = std::process::Command::new("git")
                    .args([
                        "-C",
                        wt_path.to_str().unwrap_or("."),
                        "apply",
                        "--index",
                        tmp.to_str().unwrap_or("."),
                    ])
                    .status()
                    .context("git apply")?;
                std::fs::remove_file(&tmp).ok();
                if !apply.success() {
                    bail!("git apply failed — check that the diff is a clean unified diff against current HEAD");
                }
            }

            // Commit.
            let commit = std::process::Command::new("git")
                .args([
                    "-C",
                    wt_path.to_str().unwrap_or("."),
                    "commit",
                    "-m",
                    &commit_msg,
                ])
                .status()
                .context("git commit")?;
            if !commit.success() {
                bail!("git commit failed");
            }

            // Update memory record to reflect fix applied.
            let now_s = now_secs();
            if let Some(mut rec) = store.memory_get(&mem_key).await? {
                rec.content.push_str(&format!(
                    "\n\n**Fixed**: patch applied and committed ({})",
                    chrono_date()
                ));
                rec.updated_at = now_s;
                store.memory_save(&rec).await?;
            } else {
                // New proposal created on-the-fly — write full record.
                let content = format!(
                    "**Issue**: {issue_text}\n\n**Branch**: {branch}\n**Worktree**: {}\n\n**Fixed**: patch applied and committed ({})",
                    wt_path.display(), chrono_date()
                );
                let rec = MemoryRecord {
                    key: mem_key.clone(),
                    kind: "evolution".to_string(),
                    content,
                    tags: vec!["evolution".to_string(), "open".to_string()],
                    related_keys: vec![],
                    scope: None,
                    created_at: now_s,
                    updated_at: now_s,
                    last_accessed_at: now_s,
                    access_count: 0,
                    importance: 0.5,
                    status: "active".to_string(),
                    trigger_pattern: None,
                };
                store.memory_save(&rec).await?;
            }

            println!("\n✓ patch applied and committed in worktree");
            println!("  branch: {branch}");
            println!("\nTo merge:");
            println!("  cd {}", repo.display());
            println!("  git merge {branch} --no-ff");
            println!("  agent-cli evolve close {mem_key}");
        }

        EvolveCmd::Close { key, note } => {
            let store: Arc<dyn StateStore> = Arc::new(
                SqliteStore::open(db_path)
                    .await
                    .with_context(|| format!("open SQLite store at {db_path:?}"))?,
            );
            let mut rec = store
                .memory_get(&key)
                .await?
                .with_context(|| format!("no evolution proposal found for key '{key}'"))?;

            // Replace tag "open" → "closed", append resolution note.
            rec.tags.retain(|t| t != "open");
            if !rec.tags.contains(&"closed".to_string()) {
                rec.tags.push("closed".to_string());
            }
            rec.kind = "evolution_closed".to_string();
            if let Some(n) = &note {
                rec.content.push_str(&format!("\n\n**Closed**: {n}"));
            } else {
                rec.content.push_str("\n\n**Closed**: merged");
            }
            rec.updated_at = now_secs();
            store.memory_save(&rec).await?;
            println!("✓ closed {key}");
        }

        EvolveCmd::List { json: as_json } => {
            let store: Arc<dyn StateStore> = Arc::new(
                SqliteStore::open(db_path)
                    .await
                    .with_context(|| format!("open SQLite store at {db_path:?}"))?,
            );
            // Show open proposals only (kind=evolution); closed ones are kind=evolution_closed.
            let rows = store
                .list_memories(Some("evolution"), MemoryListSort::Newest, 50)
                .await?;
            if as_json {
                println!("{}", serde_json::to_string_pretty(&rows)?);
            } else if rows.is_empty() {
                println!("(no open evolution proposals)");
            } else {
                let now = now_secs();
                println!("{:>4}  {:<44}  {}", "AGE", "KEY", "ISSUE");
                println!("{}", "-".repeat(92));
                for r in &rows {
                    let age = format_age(now - r.created_at);
                    let issue = r
                        .content
                        .lines()
                        .find(|l| l.starts_with("**Issue**"))
                        .and_then(|l| l.strip_prefix("**Issue**: "))
                        .unwrap_or(&r.content);
                    println!(
                        "{:>4}  {:<44}  {}",
                        age,
                        truncate(&r.key, 44),
                        truncate(issue, 40)
                    );
                }
            }
        }
    }
    Ok(())
}

fn chrono_date() -> String {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let secs_per_day = 86400u64;
    // Days since Unix epoch → Gregorian (Zeller-like, no external dep).
    let days = now / secs_per_day;
    let (y, m, d) = days_to_ymd(days);
    format!("{y:04}{m:02}{d:02}")
}

fn days_to_ymd(days: u64) -> (u32, u32, u32) {
    // Algorithm: civil calendar from Julian day number.
    let jdn = days + 2_440_588; // Unix epoch = JDN 2440588
    let a = jdn + 32044;
    let b = (4 * a + 3) / 146097;
    let c = a - (146097 * b) / 4;
    let d = (4 * c + 3) / 1461;
    let e = c - (1461 * d) / 4;
    let m = (5 * e + 2) / 153;
    let day = (e - (153 * m + 2) / 5 + 1) as u32;
    let month = (m + 3 - 12 * (m / 10)) as u32;
    let year = (100 * b + d - 4800 + m / 10) as u32;
    (year, month, day)
}

async fn run_memory(db_path: &std::path::Path, cmd: MemoryCmd) -> Result<()> {
    let store: Arc<dyn StateStore> = Arc::new(
        SqliteStore::open(db_path)
            .await
            .with_context(|| format!("open SQLite store at {db_path:?}"))?,
    );

    match cmd {
        MemoryCmd::List {
            kind,
            sort,
            limit,
            json: as_json,
        } => {
            let sort = parse_sort(&sort)?;
            let rows = store.list_memories(kind.as_deref(), sort, limit).await?;
            if as_json {
                println!("{}", serde_json::to_string_pretty(&rows)?);
            } else {
                render_memory_list(&rows);
            }
        }
        MemoryCmd::Get { key, json: as_json } => match store.memory_get(&key).await? {
            None => {
                eprintln!("(no such key: {key})");
                std::process::exit(1);
            }
            Some(rec) => {
                if as_json {
                    println!("{}", serde_json::to_string_pretty(&rec)?);
                } else {
                    render_memory_detail(&rec);
                }
            }
        },
        MemoryCmd::Search {
            query,
            tags,
            limit,
            json: as_json,
        } => {
            let hits = store.memory_search(&query, &tags, limit).await?;
            if as_json {
                println!("{}", serde_json::to_string_pretty(&hits)?);
            } else if hits.is_empty() {
                println!("(no hits)");
            } else {
                println!(
                    "{:>5}  {:<14}  {:<40}  {}",
                    "SCORE", "KIND", "KEY", "PREVIEW"
                );
                println!("{}", "-".repeat(90));
                for h in hits {
                    println!(
                        "{:>5.2}  {:<14}  {:<40}  {}",
                        h.score,
                        truncate(&h.record.kind, 14),
                        truncate(&h.record.key, 40),
                        truncate(&h.record.content.replace('\n', " "), 30),
                    );
                }
            }
        }
        MemoryCmd::Save {
            key,
            kind,
            content,
            tags,
            related,
            scope,
        } => {
            let body = match content {
                Some(c) => c,
                None => {
                    let mut buf = String::new();
                    tokio::io::stdin().read_to_string(&mut buf).await?;
                    buf
                }
            };
            if body.trim().is_empty() {
                bail!("memory content is empty (use --content or pipe via stdin)");
            }
            let now = now_secs();
            let rec = MemoryRecord {
                key: key.clone(),
                kind,
                content: body,
                tags,
                related_keys: related,
                scope,
                created_at: now,
                updated_at: now,
                last_accessed_at: now,
                access_count: 0,
                importance: 0.5,
                status: "active".to_string(),
                trigger_pattern: None,
            };
            store.memory_save(&rec).await?;
            println!("✓ saved {key}");
        }
        MemoryCmd::Delete { key } => {
            let removed = store.memory_delete(&key).await?;
            if removed {
                println!("✓ deleted {key}");
            } else {
                eprintln!("(no such key: {key})");
                std::process::exit(1);
            }
        }
        MemoryCmd::Graph {
            key,
            depth,
            decay,
            min_energy,
            json: as_json,
        } => {
            let root = match store.memory_get(&key).await? {
                None => {
                    eprintln!("(no such key: {key})");
                    std::process::exit(1);
                }
                Some(r) => r,
            };

            if as_json {
                // JSON mode: emit root + edges array
                let edges = store
                    .memory_neighbors_bfs(&key, depth, decay, min_energy)
                    .await?;
                let out = serde_json::json!({
                    "root": root,
                    "edges": edges.iter().map(|(e, energy)| serde_json::json!({
                        "from_key": e.from_key,
                        "to_key": e.to_key,
                        "edge_type": e.edge_type,
                        "weight": e.weight,
                        "energy": energy,
                    })).collect::<Vec<_>>(),
                });
                println!("{}", serde_json::to_string_pretty(&out)?);
            } else {
                // Human-readable tree view
                let imp = root.importance;
                let stars = importance_bar(imp);
                println!(
                    "● {:<44} [{:<12}] {stars} {:.2}  {}",
                    root.key, root.kind, imp, root.status
                );

                if depth == 0 {
                    return Ok(());
                }

                let edges = store
                    .memory_neighbors_bfs(&key, depth, decay, min_energy)
                    .await?;

                // depth=1 → use memory_neighbors (all direct edges, no energy filter)
                // depth>1 → use BFS with energy decay
                struct EdgeRow {
                    from_key: String,
                    to_key: String,
                    edge_type: String,
                    weight: f64,
                    energy: f64,
                }
                let display_edges: Vec<EdgeRow> = if depth == 1 {
                    store
                        .memory_neighbors(&key)
                        .await?
                        .into_iter()
                        .map(|e| {
                            let w = e.weight;
                            EdgeRow {
                                from_key: e.from_key,
                                to_key: e.to_key,
                                edge_type: e.edge_type,
                                weight: w,
                                energy: w, // direct hop: energy == weight
                            }
                        })
                        .collect()
                } else {
                    edges
                        .into_iter()
                        .map(|(e, energy)| EdgeRow {
                            from_key: e.from_key,
                            to_key: e.to_key,
                            edge_type: e.edge_type,
                            weight: e.weight,
                            energy,
                        })
                        .collect()
                };

                if display_edges.is_empty() {
                    println!("  (no edges)");
                } else {
                    println!(
                        "  {:<8}  {:<5}  {:<30}  {:<16}  {}",
                        "ENERGY", "W", "FROM", "EDGE_TYPE", "TO"
                    );
                    println!("  {}", "─".repeat(84));
                    for e in &display_edges {
                        let from_disp = if e.from_key == key {
                            format!("●{}", truncate(&e.from_key, 29))
                        } else {
                            truncate(&e.from_key, 30)
                        };
                        println!(
                            "  {:<8.3}  {:<5.2}  {:<30}  {:<16}  {}",
                            e.energy,
                            e.weight,
                            from_disp,
                            truncate(&e.edge_type, 16),
                            &e.to_key,
                        );
                    }
                    println!(
                        "\n  {} edge(s), depth={depth}, decay={decay}",
                        display_edges.len()
                    );
                }
            }
        }
        MemoryCmd::Compact {
            min_uses,
            older_than_days,
            dry_run,
        } => {
            let policy_in = CompactPolicy {
                min_uses,
                older_than_secs: older_than_days.map(|d| d * 86_400),
                dry_run,
            };
            let policy = if policy_in.is_unset() {
                let mut def = CompactPolicy::healthy_default();
                def.dry_run = dry_run;
                def
            } else {
                policy_in
            };
            let applied_defaults = policy_in.is_unset();
            let keys = store.memory_compact(policy).await?;
            let label = if dry_run { "would remove" } else { "removed" };
            let suffix = if applied_defaults {
                " (healthy default policy)"
            } else {
                ""
            };
            println!("{label} {} memories{suffix}", keys.len());
            for k in keys {
                println!("  - {k}");
            }
        }

        MemoryCmd::AutoCurate {
            source_kind,
            max_sources,
            max_items,
            exclude_kinds,
            dry_run,
            score_threshold,
            dedup_jaccard,
            json: as_json,
        } => {
            // ── 1. Gather source memories ────────────────────────────────
            let sources = store
                .list_memories(
                    Some(&source_kind),
                    MemoryListSort::ByImportance,
                    max_sources,
                )
                .await?;

            if sources.is_empty() {
                if as_json {
                    println!(
                        "{}",
                        serde_json::to_string_pretty(&json!({
                            "status": "no_sources",
                            "source_kind": source_kind,
                            "sources_found": 0,
                            "saved_count": 0,
                        }))?
                    );
                } else {
                    println!(
                        "(no memories of kind '{}' — nothing to curate)",
                        source_kind
                    );
                }
                return Ok(());
            }

            // ── 2. Aggregate into sections ────────────────────────────────
            let mut aggregated = String::new();
            let source_keys: Vec<String> = sources.iter().map(|m| m.key.clone()).collect();
            for (i, m) in sources.iter().enumerate() {
                aggregated.push_str(&format!(
                    "\n=== Source {} ({}) ===\n{}",
                    i + 1,
                    m.key,
                    m.content
                ));
            }

            // ── 3. Run two-pass curate pipeline ──────────────────────────
            let opts = ab_bridge::curate::CurateOptions::from_env_or_defaults()
                .with_overrides(score_threshold.map(|x| x as f32), dedup_jaccard);
            let mut candidates = ab_bridge::curate::curate_conversation_with_options(
                &aggregated,
                None, // global distillation — no session_id namespace
                max_items.min(50),
                opts.clone(),
            );
            // Filter excluded kinds (default: session_handoff)
            candidates.retain(|c| !exclude_kinds.iter().any(|k| k == &c.kind));

            // ── 4. Dry-run: print preview and exit ────────────────────────
            if dry_run {
                if as_json {
                    println!(
                        "{}",
                        serde_json::to_string_pretty(&json!({
                            "dry_run": true,
                            "source_kind": source_kind,
                            "sources_used": source_keys,
                            "aggregated_chars": aggregated.len(),
                            "options": {
                                "implicit_score_threshold": opts.implicit_score_threshold,
                                "implicit_dedup_jaccard":   opts.implicit_dedup_jaccard,
                            },
                            "candidates": candidates.iter().map(|m| json!({
                                "key":     m.key,
                                "kind":    m.kind,
                                "content": m.content,
                                "tags":    m.tags,
                            })).collect::<Vec<_>>()
                        }))?
                    );
                } else {
                    println!(
                        "dry-run — {} candidate(s) from {} source(s) ({} chars aggregated):",
                        candidates.len(),
                        source_keys.len(),
                        aggregated.len()
                    );
                    for c in &candidates {
                        println!("  [{}] {}  —  {}", c.kind, c.key, truncate(&c.content, 60));
                    }
                    if candidates.is_empty() {
                        println!("  (no signal found in aggregated content)");
                    }
                }
                return Ok(());
            }

            // ── 5. Persist (skip duplicates) ──────────────────────────────
            let mut saved: Vec<String> = Vec::new();
            let mut skipped = 0usize;
            let mut errors: Vec<String> = Vec::new();

            for mem in &candidates {
                match store.memory_get(&mem.key).await {
                    Ok(Some(_)) => skipped += 1,
                    Ok(None) => match store.memory_save(mem).await {
                        Ok(()) => saved.push(mem.key.clone()),
                        Err(e) => errors.push(format!("{}: {e}", mem.key)),
                    },
                    Err(e) => errors.push(format!("{}: {e}", mem.key)),
                }
            }

            if as_json {
                println!(
                    "{}",
                    serde_json::to_string_pretty(&json!({
                        "status": "ok",
                        "source_kind": source_kind,
                        "sources_used": source_keys,
                        "aggregated_chars": aggregated.len(),
                        "candidates_found": candidates.len(),
                        "saved_count": saved.len(),
                        "new_keys": saved,
                        "skipped_duplicates": skipped,
                        "errors": errors,
                    }))?
                );
            } else {
                println!(
                    "✓ auto-curate: {} saved, {} skipped (duplicates), {} error(s) — from {} source(s)",
                    saved.len(), skipped, errors.len(), source_keys.len()
                );
                for k in &saved {
                    println!("  + {k}");
                }
                for e in &errors {
                    eprintln!("  ! {e}");
                }
            }
        }
    }
    Ok(())
}

fn render_memory_list(rows: &[MemoryRecord]) {
    if rows.is_empty() {
        println!("(no memories)");
        return;
    }
    let now = now_secs();
    println!(
        "{:>4}  {:>4}  {:<5}  {:<14}  {:<40}  {}",
        "AGE", "USES", "IMP", "KIND", "KEY", "PREVIEW"
    );
    println!("{}", "-".repeat(96));
    for r in rows {
        let age = format_age(now - r.last_accessed_at);
        let imp = format!("{:.2}", r.importance);
        println!(
            "{:>4}  {:>4}  {:<5}  {:<14}  {:<40}  {}",
            age,
            r.access_count,
            imp,
            truncate(&r.kind, 14),
            truncate(&r.key, 40),
            truncate(&r.content.replace('\n', " "), 30),
        );
    }
}

/// Returns a 5-char visual bar for importance score, e.g. "████░" for 0.8.
fn importance_bar(imp: f64) -> String {
    let filled = (imp * 5.0).round() as usize;
    let filled = filled.min(5);
    let empty = 5 - filled;
    format!("{}{}", "█".repeat(filled), "░".repeat(empty))
}

fn render_memory_detail(r: &MemoryRecord) {
    println!("key:        {}", r.key);
    println!("kind:       {}", r.kind);
    println!(
        "importance: {} {:.2}",
        importance_bar(r.importance),
        r.importance
    );
    println!("status:     {}", r.status);
    if let Some(s) = &r.scope {
        println!("scope:      {s}");
    }
    if !r.tags.is_empty() {
        println!("tags:       {}", r.tags.join(", "));
    }
    if !r.related_keys.is_empty() {
        println!("related:    {}", r.related_keys.join(", "));
    }
    println!("uses:       {}", r.access_count);
    println!("created:    {}", r.created_at);
    println!("updated:    {}", r.updated_at);
    println!("accessed:   {}", r.last_accessed_at);
    println!("---");
    println!("{}", r.content);
}

async fn call(socket: &std::path::Path, req: RpcRequest) -> Result<RpcResponse> {
    let stream = UnixStream::connect(socket)
        .await
        .with_context(|| format!("connect {socket:?} (is the daemon running?)"))?;
    let (read_half, mut write_half) = stream.into_split();

    let mut bytes = serde_json::to_vec(&req)?;
    bytes.push(b'\n');
    write_half.write_all(&bytes).await?;
    write_half.flush().await?;
    write_half.shutdown().await.ok();

    let mut reader = BufReader::new(read_half).lines();
    let line = match reader.next_line().await? {
        Some(l) => l,
        None => bail!("daemon closed connection without responding"),
    };
    let resp: RpcResponse = serde_json::from_str(&line)?;
    let _: Option<Value> = None;
    Ok(resp)
}
