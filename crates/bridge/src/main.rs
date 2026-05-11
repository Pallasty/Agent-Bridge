use ab_agent::{
    AgentRuntime, AuggieRuntime, ClaudeCodeRuntime, CodexRuntime, GeminiRuntime,
    GitWorktreeManager, OpenCodeFamilyRuntime, OzAgentRuntime,
};
use ab_bridge::{build_registry, default_socket_path, serve, Hub, Router};
use ab_browser::{BrowserBackend, ChromiumCdpBackend};
use ab_mcp::server::serve_stdio;
use ab_store::{default_db_path, SqliteStore, StateStore};
use ab_bridge::warp_scheme;
use ab_terminal::{auto_backend, TerminalBackend};
use anyhow::Result;
use clap::{Parser, Subcommand, ValueEnum};
use serde_json::json;
use std::path::PathBuf;
use std::sync::Arc;
use tracing_subscriber::{prelude::*, EnvFilter};

mod setup;
mod skills;
mod sync;

#[derive(Parser, Debug)]
#[command(version, about = "agent-bridge — Unix-native AI agent control plane")]
struct Cli {
    #[command(subcommand)]
    cmd: Option<Cmd>,
}

#[derive(Subcommand, Debug)]
enum Cmd {
    /// Run the long-lived JSON-RPC daemon on a Unix socket (default).
    Daemon,
    /// Run as an MCP stdio server (for `claude mcp add agent-bridge ...`).
    Mcp,
    /// Install agent-bridge for the chosen frontend.
    ///
    /// `--frontend claude-code` (default): copies the binary to
    /// `~/.local/bin/agent-bridge`, writes the three Claude Code hook
    /// scripts, and merges hook entries into `~/.claude/settings.json`.
    ///
    /// `--frontend codex`: copies the binary and registers the MCP server in
    /// `~/.codex/config.toml`. Codex does not have Claude Code hook events.
    ///
    /// `--frontend gemini-cli`: copies the binary and registers the MCP server
    /// in `~/.gemini/settings.json`.
    ///
    /// `--frontend local-cli`: copies the binary and registers the MCP server
    /// with local CLI clients that can consume stdio MCP servers.
    ///
    /// `--frontend warp`: copies the binary only and prints guidance for
    /// registering the MCP server in Warp's settings UI. Skips all
    /// Claude-specific hook installation since Warp does not have
    /// equivalent hook-event slots.
    ///
    /// `--frontend auto`: detect Warp, Codex, Gemini CLI, Auggie, then
    /// fall back to claude-code if none are found.
    Setup {
        #[arg(long, value_enum, default_value_t = SetupFrontend::Auto)]
        frontend: SetupFrontend,
    },
    /// Cross-device memory sync via a private GitHub repo.
    ///
    /// With no subcommand, runs one sync round: pull → import → export →
    /// commit + push. Idempotent; safe to call from cron / hooks.
    ///
    /// `init` bootstraps the repo on a new machine via `gh`.
    /// `status` prints the resolved repo path and last sync (no network).
    Sync {
        #[command(subcommand)]
        op: Option<SyncOp>,
        /// Verbose logging on the default `sync` action.
        #[arg(long, short = 'v')]
        verbose: bool,
    },
    /// Index third-party Claude Code skill libraries into memory.
    ///
    /// Walks SKILL.md / .claude/skills/*.md / skills/*.md inside the source,
    /// parses YAML frontmatter, runs a heuristic safety lint, and saves
    /// each skill as a memory record (kind=skill). Subsequent runs upsert
    /// by key. See `skills seed` for the curated bootstrap set.
    Skills {
        #[command(subcommand)]
        op: SkillsOp,
    },
    /// Run the v20 HTTP daemon for cross-machine forum + presence over
    /// Tailscale.
    ///
    /// Read-only in Stage 1: serves `/.well-known/agent.json/<sid>`,
    /// `/forum/threads`, `/forum/posts`, `/presence`. Bind to a
    /// tailnet-reachable address; tailscale ACL handles peer auth.
    /// See `docs/RFC-v20-tailscale-daemon.md`.
    DaemonHttp {
        /// Listen address. Default `0.0.0.0:7878` so it's reachable from
        /// any tailnet peer. Set to `127.0.0.1:7878` for local testing.
        /// Override via `AGENT_BRIDGE_HTTP_LISTEN`.
        #[arg(long, env = "AGENT_BRIDGE_HTTP_LISTEN")]
        listen: Option<String>,
    },
    /// v21 — Synaptic Dream introspection (the "thermometer" for the
    /// memory_coactivation graph that α populates).
    ///
    /// `dream stats` shows total pairs, top10/median ratio (β trigger
    /// metric: ≥ 5.0 means cluster structure has emerged), top-5 edges,
    /// and 24h activity. See `docs/DESIGN-v21-synaptic-trace-and-dream.md` §9.
    Dream {
        #[command(subcommand)]
        op: DreamOp,
    },
    /// **呼吸式画布 P1** — Static Palace viewer.
    ///
    /// Renders the active memory graph as a force-directed network in your
    /// browser using cytoscape.js. Read-only — no editing, no creation; that
    /// belongs to P2+ on the Palace evolution path. Defaults to
    /// `127.0.0.1:7979` so it stays local-only; pass `--host 0.0.0.0` if you
    /// really want tailnet access.
    ///
    /// See `vision_breathing_canvas.md` (memory) for the broader design.
    Palace {
        #[command(subcommand)]
        op: PalaceOp,
    },
    /// Print an OSC 133 shell-integration snippet for the chosen shell to
    /// stdout. Pipe into the matching rc file:
    ///
    ///     agent-bridge shell-init bash >> ~/.bashrc
    ///     agent-bridge shell-init zsh  >> ~/.zshrc
    ///     agent-bridge shell-init fish >  ~/.config/fish/conf.d/agent-bridge-osc133.fish
    ///
    /// After re-sourcing the rc file (or starting a fresh shell), the
    /// PtyBackend's `terminal_read_blocks` will return structured
    /// (command, output, exit_code, start_ms, end_ms) tuples for every
    /// command run in agent-bridge-spawned panes. See
    /// `docs/SHELL-INTEGRATION-OSC133.md` for protocol details.
    ShellInit {
        /// Which shell flavour to emit a snippet for.
        shell: ShellKind,
    },
    /// **ε-5 (2026-05-11)** — Session-scoped git worktree as sibling-sweep
    /// root fix. Two Claude agents in one working tree + git index will
    /// sweep each other's unstaged changes on `git add/commit` (Hebbian
    /// top-pair `lesson_sibling_parallel_commits` ↔ `lesson_git_commit_by_path`
    /// fired 9× on this insight alone). Create a per-session worktree to
    /// physically isolate the index.
    ///
    /// Flow:
    ///   1. `agent-bridge worktree-session new --name fix-foo`
    ///      → creates `.worktrees/session-fix-foo-<ts>/` on a new branch
    ///        `session/fix-foo-<ts>`. Prints the path.
    ///   2. `cd` into the printed path. Continue work there.
    ///   3. Commit + push when done; `git worktree remove <path>` after
    ///      merging the branch back to master.
    WorktreeSession {
        #[command(subcommand)]
        op: WorktreeSessionOp,
    },
}

#[derive(Copy, Clone, Debug, ValueEnum)]
enum ShellKind {
    Bash,
    Zsh,
    Fish,
}

#[derive(Subcommand, Debug)]
enum WorktreeSessionOp {
    /// Create a new session worktree on a fresh branch. Prints the path
    /// to stdout (last line) so you can `cd "$(agent-bridge worktree-session new | tail -1)"`.
    New {
        /// Optional slug fragment baked into the branch + dir name. Letters,
        /// digits, hyphens. Auto-paired with a timestamp suffix so reruns
        /// don't collide.
        #[arg(long)]
        name: Option<String>,
        /// Branch to fork from. Default: current HEAD.
        #[arg(long)]
        base: Option<String>,
    },
    /// List existing session worktrees (filters `git worktree list` to ones
    /// under `.worktrees/session-`).
    List,
}

#[derive(Subcommand, Debug)]
enum PalaceOp {
    /// Start the Palace viewer HTTP server. Default `127.0.0.1:7979`.
    Serve {
        #[arg(long, default_value_t = 7979)]
        port: u16,
        /// Bind address. Default `127.0.0.1` (local-only). Pass `0.0.0.0`
        /// for tailnet access — but understand the viewer has no auth.
        #[arg(long, default_value = "127.0.0.1")]
        host: String,
        /// Path to Claude Code's markdown auto-memory directory. Defaults
        /// to `~/.claude/projects/<cwd-encoded>/memory/` if it exists.
        /// Pass `none` to disable the markdown layer entirely.
        #[arg(long)]
        memory_dir: Option<String>,
    },
}

#[derive(Subcommand, Debug)]
enum DreamOp {
    /// Print synaptic-trace health snapshot (text, or JSON via `--json`).
    Stats {
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// v21 — Identity continuity delta. Compares "last N days" vs "prior
    /// N days" behavioral fingerprint: tool histogram, forum tone, memory
    /// activity. The literal answer to "non-continuous medium continuity"
    /// (vision principle 5).
    Identity {
        /// Window size in days (default 7). Compares [now-N, now) vs
        /// [now-2N, now-N).
        #[arg(long, default_value_t = 7)]
        days: u32,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **Phase 1 P5** — Sleep replay: scan the coactivation graph for tight
    /// clusters, ask the LLM to consolidate each into a higher-order summary
    /// memory, and `summarizes`-link sources back to the summary. Designed
    /// to run nightly via cron (`0 4 * * *`). `--dry-run` prints what would
    /// be summarized without calling the LLM or writing anything.
    ///
    /// See `project_phase1_complete_p5_design_draft.md` for design rationale.
    Replay {
        /// Maximum number of clusters to summarize this round.
        #[arg(long, default_value_t = 5)]
        top_n: usize,
        /// Minimum cluster size (memory keys) to consider summarizing.
        /// Smaller clusters typically aren't worth a synthesis pass.
        #[arg(long, default_value_t = 3)]
        min_cluster_size: usize,
        /// Inspect-only: print picked clusters but skip LLM + writes.
        /// Also makes the auto-promote step dry-run.
        #[arg(long)]
        dry_run: bool,
        /// Skip the auto-trigger of `dream promote` after replay finishes.
        /// Default behavior crystallises strong co-activation pairs as
        /// `cofires` edges so a single cron pass closes the consolidation
        /// loop (summary + structural). Use this flag when you want only
        /// the summarization half (e.g. when promote ran separately).
        #[arg(long)]
        no_auto_promote: bool,
        /// Min co-activation count threshold for the auto-promote step.
        /// Defaults to 5 (matches `dream promote --min-count` default).
        #[arg(long, default_value_t = 5)]
        promote_min_count: u64,
        /// Override the auto-promote HTML report path. Default writes
        /// `<state-dir>/reports/promote-YYYY-MM-DD.html` (creates the
        /// directory if missing). Pass an empty string to skip the report.
        #[arg(long)]
        promote_report: Option<PathBuf>,
    },
    /// 呼吸式画布 / Hebbian feedback — Promote strong co-activation pairs
    /// (`memory_coactivation` rows with count ≥ `--min-count`) into explicit
    /// `cofires` edges in `memory_edges`. Pairs that already have a `cofires`
    /// edge are skipped (idempotent); pairs with other edge types
    /// (`evolved`, `summarizes`, `derived_from`, …) get cofires *stacked*
    /// alongside — those encode "similar in content" or "summary-of", while
    /// cofires encodes "fired together repeatedly" — orthogonal signals.
    ///
    /// This is the "fire together, **wire** together" half of Hebbian: α
    /// records co-firings; this command crystallises the persistent ones
    /// as real graph relations so they survive coactivation table pruning,
    /// participate in `memory_neighbors` BFS, and stop showing as the
    /// cyan-dotted underlay in Palace (they "graduate" to structural).
    ///
    /// `--dry-run` prints what would be promoted without writing.
    Promote {
        /// Minimum co-activation count to promote. Default 5 matches the
        /// β-trigger "clusters emerged" threshold (top10/median ratio ≥ 5).
        #[arg(long, default_value_t = 5)]
        min_count: u64,
        /// Maximum number of pairs to promote in one run. Caps blast radius
        /// of accidental settings.
        #[arg(long, default_value_t = 50)]
        limit: u32,
        /// Inspect-only: print decisions, no writes.
        #[arg(long)]
        dry_run: bool,
        /// Also write a self-contained HTML audit report to PATH. Useful for
        /// cron-driven auto-runs where terminal output is invisible — the
        /// HTML preserves Strength Map + per-pair cards for later review,
        /// and links each key to the running Palace viewer (?focus=KEY).
        #[arg(long)]
        html: Option<PathBuf>,
    },
    /// **Phase 2.x #8** — Read-recency importance decay: shave
    /// `importance` by `--step` on every active memory whose
    /// `last_accessed_at` is older than `--window-days`. Pairs with the
    /// Palace viewer C7/C8/C10 "stale" semantics so retrieval rank and
    /// the viewer agree on what's gone cold.
    ///
    /// CLI mirror of the `memory_decay_unused` MCP tool. Designed for
    /// daily cron via `agent-bridge-memory-decay-unused.timer`
    /// (`scripts/systemd/`). See
    /// `project_memory_decay_unused_shipped.md` (memory).
    DecayUnused {
        /// Only decay rows whose `last_accessed_at` is older than this
        /// many days. Default 30.
        #[arg(long, default_value_t = 30.0)]
        window_days: f64,
        /// How much to shave off `importance` per pass. Default 0.05.
        #[arg(long, default_value_t = 0.05)]
        step: f64,
        /// Importance never drops below this floor. Default 0.1.
        #[arg(long, default_value_t = 0.1)]
        floor: f64,
        /// Emit raw JSON instead of pretty text. Default text matches
        /// `dream stats` / `dream identity` style for terminal use.
        #[arg(long)]
        json: bool,
    },
    /// **δ-3 (Butlin HOT-4 hygiene)** — Drop low-weight coactivation
    /// rows that never crystallised. A pair with `count <= --max-count`
    /// AND `last_at` older than `--older-than-days` is noise: it co-fired
    /// briefly once, never re-fired, and is ageing the table. Sibling
    /// hygiene op to `dream decay-unused`: shares the daily timer cron
    /// path (`scripts/systemd/agent-bridge-memory-decay-unused.service`).
    ///
    /// CLI mirror of the `memory_prune_coactivation_noise` MCP tool. See
    /// commit `f5b9b6e` for design rationale; pairs with `dream promote`
    /// (anything left below promote threshold after this window is by
    /// definition unworthy of the synaptic graph).
    PruneCoactivationNoise {
        /// Prune pairs whose count is ≤ this. Default 1: only single
        /// co-firings get dropped. Raise to 2 for sporadic twice-fired
        /// pairs that never reached the promote threshold.
        #[arg(long, default_value_t = 1)]
        max_count: i64,
        /// Only prune pairs whose `last_at` is at least this many days
        /// old. Default 30 — gives a pair a month to grow before GC.
        #[arg(long, default_value_t = 30)]
        older_than_days: i64,
        /// Preview only: count what would be pruned without deleting.
        #[arg(long)]
        dry_run: bool,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **Replay quality audit** — are the LLM-consolidated summaries that
    /// `dream replay` writes actually being used? Pure read pass: counts
    /// `p5_replay`-tagged active memories, bins access patterns, surfaces
    /// the top wins and the oldest dead weight. Also reports source-memory
    /// average access so callers can compare summary vs raw-row usage.
    ///
    /// No writes, no LLM. Cheap enough to run ad-hoc.
    ReplayAudit {
        /// `access_count = 0` AND age > this many days counts toward
        /// `stale_dead` — the "LLM cost paid, no recall ever happened"
        /// tally. Default 7.
        #[arg(long, default_value_t = 7)]
        stale_days: u32,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
}

#[derive(Subcommand, Debug)]
enum SyncOp {
    /// Bootstrap the cross-device memory repo via `gh` (GitHub) or
    /// `glab` (GitLab) CLI. Uses `--provider auto` (default) to pick:
    /// gitlab if `glab` is on PATH and `gh` isn't, github otherwise.
    Init {
        /// Override the repo name (default: `agent-bridge-memory`).
        #[arg(long)]
        repo: Option<String>,
        /// Forge to host the cross-device repo on.
        #[arg(long, value_enum, default_value_t = SyncProvider::Auto)]
        provider: SyncProvider,
    },
    /// Print resolved repo path, remote, and last sync; no network calls.
    Status,
}

#[derive(Copy, Clone, Debug, ValueEnum)]
pub enum SyncProvider {
    /// Use `gh` CLI to host on GitHub (legacy default).
    Github,
    /// Use `glab` CLI to host on GitLab.
    Gitlab,
    /// Auto-detect: gitlab if `glab` is on PATH and `gh` isn't,
    /// github otherwise (preserves legacy behaviour for users who
    /// only have `gh`).
    Auto,
}

#[derive(Subcommand, Debug)]
enum SkillsOp {
    /// Clone (URL) or read (local path) a repo and index every SKILL.md /
    /// `.claude/skills/*.md` it contains.
    Index {
        /// `https://...` GitHub URL or local path to a checkout.
        source: String,
        #[arg(long, short = 'v')]
        verbose: bool,
    },
    /// Index the curated seed corpus (anthropics/skills + ~7 community libs).
    Seed {
        #[arg(long, short = 'v')]
        verbose: bool,
    },
    /// Re-index every previously-indexed source to refresh upstream changes.
    ///
    /// Walks all `kind=skill` records, collects distinct GitHub `<owner>/<repo>`
    /// values from `src:` tags, and re-runs `index` for each. Local-path
    /// sources (no `/` in `src`) are skipped — re-run `index <path>` manually.
    /// Suitable for cron / Stop hook.
    ///
    /// `--prune`: after re-indexing each GitHub source, delete records that
    /// have that `src:` tag but were not refreshed in this run (i.e. removed
    /// upstream). Local-path sources are never pruned, even with `--prune`.
    Refresh {
        #[arg(long, short = 'v')]
        verbose: bool,
        /// Delete records for skills that disappeared upstream.
        #[arg(long)]
        prune: bool,
    },
    /// Discover candidate skill repos via GitHub topic search.
    ///
    /// Queries `topic:claude-skill` and `topic:claude-code-skill` (unauth REST
    /// API), dedupes, filters out anything already indexed in this DB, and
    /// prints the top results ranked by stars. Does NOT index anything —
    /// the user picks candidates and runs `skills index <url>` to approve.
    Discover {
        /// Number of candidates to print (after dedupe + already-indexed
        /// filter). Default 30.
        #[arg(long, default_value_t = 30)]
        limit: usize,
        /// Include candidates already indexed in this DB (default: hide them).
        #[arg(long)]
        all: bool,
    },
    /// Semantic search over indexed skills.
    Search {
        query: String,
        #[arg(long, default_value_t = 10)]
        limit: usize,
    },
    /// List indexed skills, most-recent first.
    List {
        #[arg(long, default_value_t = 50)]
        limit: usize,
    },
    /// Print one skill's body and metadata (use a key from `list` / `search`).
    Show {
        key: String,
    },
    /// Install an indexed skill into `~/.claude/skills/<name>/`.
    ///
    /// Re-clones the source repo and copies the original SKILL.md (plus
    /// any sibling scripts/data, for canonical-layout skills). Bails with
    /// guidance when the skill has lint warnings or the destination
    /// already exists, unless `--yes` is given.
    Install {
        key: String,
        /// Skip lint-warning and overwrite confirmation prompts.
        #[arg(long, short = 'y')]
        yes: bool,
    },
}

#[derive(Copy, Clone, Debug, ValueEnum)]
pub enum SetupFrontend {
    /// Install hooks for Claude Code (legacy behaviour).
    ClaudeCode,
    /// Install for Warp (binary only; no hook scripts).
    Warp,
    /// Install for Augment Code (auggie) — registers MCP via
    /// `auggie mcp add`; no hook scripts.
    Auggie,
    /// Install for OpenAI Codex — registers MCP in ~/.codex/config.toml.
    Codex,
    /// Install for Gemini CLI — registers MCP in ~/.gemini/settings.json.
    GeminiCli,
    /// Install MCP config for local CLI clients (Codex, Gemini CLI, Claude Code).
    LocalCli,
    /// Auto-detect from the running shell's environment.
    Auto,
}

impl From<SyncProvider> for sync::Provider {
    fn from(p: SyncProvider) -> Self {
        match p {
            SyncProvider::Github => sync::Provider::Github,
            SyncProvider::Gitlab => sync::Provider::Gitlab,
            SyncProvider::Auto => sync::Provider::Auto,
        }
    }
}

impl SetupFrontend {
    /// Resolve `Auto` to a concrete frontend by inspecting the env.
    ///
    /// Detection order: **Claude Code already wired** (hooks installed
    /// in `~/.claude/settings.json`) → Warp → Codex
    /// (`~/.codex/config.toml`, `CODEX_HOME`, or `codex` on PATH) →
    /// Gemini CLI (`~/.gemini/settings.json` or `gemini` on PATH) →
    /// Auggie (`~/.augment` exists or `auggie` on PATH) → Claude Code
    /// (default fallback).
    ///
    /// The "already wired" check goes first because hooks are the
    /// strongest signal of user choice — if the user previously ran
    /// `setup --frontend claude-code` and the hooks are still active,
    /// re-running `setup --frontend auto` should reinstall the same
    /// profile, even if other frontends are also installed on the
    /// machine.
    fn resolve(self) -> setup::Frontend {
        match self {
            Self::ClaudeCode => setup::Frontend::ClaudeCode,
            Self::Warp => setup::Frontend::Warp,
            Self::Auggie => setup::Frontend::Auggie,
            Self::Codex => setup::Frontend::Codex,
            Self::GeminiCli => setup::Frontend::GeminiCli,
            Self::LocalCli => setup::Frontend::LocalCli,
            Self::Auto => {
                if detect_claude_code_wired() {
                    setup::Frontend::ClaudeCode
                } else if warp_scheme::detect() {
                    setup::Frontend::Warp
                } else if detect_codex() {
                    setup::Frontend::Codex
                } else if detect_gemini_cli() {
                    setup::Frontend::GeminiCli
                } else if detect_auggie() {
                    setup::Frontend::Auggie
                } else {
                    setup::Frontend::ClaudeCode
                }
            }
        }
    }
}

/// True when `~/.claude/settings.json` already references at least one
/// of agent-bridge's hook scripts (`ab-memory-hook`,
/// `ab-precompact-hook`, `ab-session-end-hook`). This is the strongest
/// possible "Claude Code is the primary frontend" signal — beats every
/// other detector because it means the user previously committed to
/// this profile.
fn detect_claude_code_wired() -> bool {
    let Some(home) = std::env::var_os("HOME") else {
        return false;
    };
    let path = std::path::Path::new(&home).join(".claude/settings.json");
    let Ok(body) = std::fs::read_to_string(&path) else {
        return false;
    };
    settings_references_ab_hook(&body)
}

/// Substring scan rather than full JSON parse — robust to schema drift
/// (Claude Code reorganises `hooks.*` shape periodically) and to users
/// hand-editing the file with comments. False positives are unlikely:
/// the script names are unique to agent-bridge.
fn settings_references_ab_hook(body: &str) -> bool {
    body.contains("ab-memory-hook")
        || body.contains("ab-precompact-hook")
        || body.contains("ab-session-end-hook")
}

/// Heuristic: Codex keeps its config under `$CODEX_HOME/config.toml`
/// or `~/.codex/config.toml`; a `codex` binary on PATH is also enough
/// to prefer the Codex installer profile over the Claude Code fallback.
fn detect_codex() -> bool {
    if let Some(home) = std::env::var_os("CODEX_HOME") {
        if std::path::Path::new(&home).join("config.toml").exists() {
            return true;
        }
    }
    if let Some(home) = std::env::var_os("HOME") {
        if std::path::Path::new(&home)
            .join(".codex/config.toml")
            .exists()
        {
            return true;
        }
    }
    which_in_path("codex")
}

/// Heuristic: Gemini CLI stores global settings in
/// `~/.gemini/settings.json`; a `gemini` binary on PATH also indicates
/// the Gemini CLI profile is useful.
fn detect_gemini_cli() -> bool {
    if let Some(home) = std::env::var_os("HOME") {
        if std::path::Path::new(&home)
            .join(".gemini/settings.json")
            .exists()
        {
            return true;
        }
    }
    which_in_path("gemini")
}

/// Heuristic: an `~/.augment` directory or an `auggie` binary on
/// `$PATH` is sufficient evidence the user is on Auggie.
fn detect_auggie() -> bool {
    if let Some(home) = std::env::var_os("HOME") {
        if std::path::Path::new(&home).join(".augment").exists() {
            return true;
        }
    }
    which_in_path("auggie")
}

fn which_in_path(bin: &str) -> bool {
    let Some(path) = std::env::var_os("PATH") else {
        return false;
    };
    std::env::split_paths(&path).any(|p| p.join(bin).is_file())
}

#[tokio::main]
async fn main() -> Result<()> {
    // Load API tokens from the user's plaintext creds notebook before any
    // worker thread can read env. Self-heals after a `cargo install` that
    // overwrites the shell wrapper. See `creds.rs` for resolution order.
    ab_bridge::creds::load_at_startup();

    let cli = Cli::parse();
    let cmd = cli.cmd.unwrap_or(Cmd::Daemon);

    // Setup runs synchronously, no async runtime needed beyond tokio's shell.
    if let Cmd::Setup { frontend } = &cmd {
        return setup::run(frontend.resolve());
    }

    // Sync subcommand: short-lived; no daemon hub needed.
    if let Cmd::Sync { op, verbose } = &cmd {
        return match op {
            None => sync::run_sync(*verbose).await.map(|_| ()),
            Some(SyncOp::Init { repo, provider }) => {
                sync::run_init(repo.clone(), (*provider).into()).await
            }
            Some(SyncOp::Status) => sync::run_status(),
        };
    }

    // Skills subcommand: short-lived; no daemon hub needed.
    if let Cmd::Skills { op } = &cmd {
        return match op {
            SkillsOp::Index { source, verbose } => {
                skills::run_index(source, *verbose).await.map(|_| ())
            }
            SkillsOp::Seed { verbose } => skills::run_seed(*verbose).await,
            SkillsOp::Refresh { verbose, prune } => {
                skills::run_refresh(*verbose, *prune).await
            }
            SkillsOp::Discover { limit, all } => skills::run_discover(*limit, *all).await,
            SkillsOp::Search { query, limit } => skills::run_search(query, *limit).await,
            SkillsOp::List { limit } => skills::run_list(*limit).await,
            SkillsOp::Show { key } => skills::run_show(key).await,
            SkillsOp::Install { key, yes } => skills::run_install(key, *yes).await,
        };
    }

    // Dream subcommand: short-lived read-only introspection over state.db.
    if let Cmd::Dream { op } = &cmd {
        return match op {
            DreamOp::Stats { json } => run_dream_stats(*json).await,
            DreamOp::Identity { days, json } => run_dream_identity(*days, *json).await,
            DreamOp::Replay {
                top_n,
                min_cluster_size,
                dry_run,
                no_auto_promote,
                promote_min_count,
                promote_report,
            } => {
                ab_bridge::dream_replay::run(*top_n, *min_cluster_size, *dry_run).await?;
                if !*no_auto_promote {
                    // Resolve the report path: explicit flag wins; empty
                    // string skips the report; default = `<state-dir>/reports/
                    // promote-YYYY-MM-DD.html` (created if missing).
                    let report_path = match promote_report {
                        Some(p) if p.as_os_str().is_empty() => None,
                        Some(p) => Some(p.clone()),
                        None => Some(default_promote_report_path()?),
                    };
                    println!();
                    println!("# auto-trigger: dream promote");
                    run_dream_promote(
                        *promote_min_count,
                        50, // matches `dream promote --limit` default
                        *dry_run,
                        report_path.as_deref(),
                    )
                    .await?;
                }
                Ok(())
            }
            DreamOp::Promote {
                min_count,
                limit,
                dry_run,
                html,
            } => run_dream_promote(*min_count, *limit, *dry_run, html.as_deref()).await,
            DreamOp::DecayUnused {
                window_days,
                step,
                floor,
                json,
            } => run_dream_decay_unused(*window_days, *step, *floor, *json).await,
            DreamOp::PruneCoactivationNoise {
                max_count,
                older_than_days,
                dry_run,
                json,
            } => run_dream_prune_coact_noise(*max_count, *older_than_days, *dry_run, *json).await,
            DreamOp::ReplayAudit { stale_days, json } => {
                run_dream_replay_audit(*stale_days, *json).await
            }
        };
    }

    // ShellInit: print snippet to stdout. Pure function, no daemon, no state.
    if let Cmd::ShellInit { shell } = &cmd {
        print!("{}", shell_init_snippet(*shell));
        return Ok(());
    }

    // ε-5: worktree-session subcommand. Doesn't need a Hub — pure git
    // CLI wrapping, runs to completion.
    if let Cmd::WorktreeSession { op } = &cmd {
        return match op {
            WorktreeSessionOp::New { name, base } => {
                run_worktree_session_new(name.as_deref(), base.as_deref()).await
            }
            WorktreeSessionOp::List => run_worktree_session_list().await,
        };
    }

    // Palace viewer: short-lived HTTP server, opens store directly (no Hub).
    if let Cmd::Palace { op } = &cmd {
        return match op {
            PalaceOp::Serve {
                port,
                host,
                memory_dir,
            } => {
                tracing_subscriber::registry()
                    .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
                    .with(tracing_subscriber::fmt::layer())
                    .init();
                let path = default_db_path();
                let store: Arc<dyn StateStore> = Arc::new(SqliteStore::open(&path).await?);
                let listen = format!("{host}:{port}");
                let markdown_root: Option<PathBuf> = match memory_dir.as_deref() {
                    Some("none") => None,
                    Some(p) => Some(PathBuf::from(p)),
                    None => ab_bridge::palace_viewer::default_markdown_dir(),
                };
                // Reports dir = `<state-dir>/reports/` (same default that
                // `dream promote` writes to). Only enabled when the dir
                // already exists — Palace doesn't create it itself; the
                // first promote run does.
                let reports_dir: Option<PathBuf> = path
                    .parent()
                    .map(|p| p.join("reports"))
                    .filter(|p| p.is_dir());
                ab_bridge::palace_viewer::run(store, &listen, markdown_root, reports_dir).await
            }
        };
    }

    let log_layer = match cmd {
        Cmd::Mcp => tracing_subscriber::fmt::layer()
            .with_writer(std::io::stderr)
            .boxed(),
        _ => tracing_subscriber::fmt::layer().boxed(),
    };
    tracing_subscriber::registry()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .with(log_layer)
        .init();

    let hub = build_hub().await?;

    match cmd {
        Cmd::Daemon => {
            let socket = default_socket_path();
            tracing::info!(socket = %socket.display(), "starting agent-bridge daemon");
            serve(&socket, Router::new(hub)).await
        }
        Cmd::Mcp => {
            let tool_backend_id = json!({
                "terminal": hub.terminal.as_ref().map(|t| t.id()).unwrap_or("none"),
                "browser": hub.browser.as_ref().map(|b| b.id()).unwrap_or("none"),
                "agent_runtime": hub.agent.as_ref().map(|a| a.id()).unwrap_or("none"),
                "memory": if hub.store.is_some() { "sqlite" } else { "none" },
            });
            let store = hub.store.clone();
            let registry = build_registry(hub);
            tracing::info!(tools = registry.list().len(), "starting MCP stdio server");
            serve_stdio(
                registry,
                store,
                "agent-bridge",
                env!("CARGO_PKG_VERSION"),
                Some(tool_backend_id),
            )
            .await;
            Ok(())
        }
        Cmd::DaemonHttp { listen } => {
            let store = hub.store.clone().ok_or_else(|| {
                anyhow::anyhow!(
                    "daemon-http requires a memory store; SqliteStore failed to initialise"
                )
            })?;
            let listen = listen.unwrap_or_else(|| "0.0.0.0:7878".to_string());
            tracing::info!(
                listen = %listen,
                "starting agent-bridge daemon-http (v20 read-only Stage 1)"
            );
            ab_bridge::daemon_http::run(store, &listen).await
        }
        Cmd::Setup { .. }
        | Cmd::Sync { .. }
        | Cmd::Skills { .. }
        | Cmd::Dream { .. }
        | Cmd::Palace { .. }
        | Cmd::ShellInit { .. }
        | Cmd::WorktreeSession { .. } => unreachable!(),
    }
}

/// OSC 133 shell-integration snippets. Source-of-truth lives here; the
/// human-readable copy in `docs/SHELL-INTEGRATION-OSC133.md` is intended
/// to track this verbatim. If you edit one, mirror the change in the doc
/// (or vice-versa) so the install instructions stay consistent.
fn shell_init_snippet(shell: ShellKind) -> &'static str {
    match shell {
        ShellKind::Bash => "\
# agent-bridge — OSC 133 shell integration (bash)
# See: docs/SHELL-INTEGRATION-OSC133.md
__ab_osc133_preexec() { printf '\\e]133;C\\a'; }
__ab_osc133_precmd() {
    local exit=$?
    printf '\\e]133;D;%s\\a\\e]133;A\\a' \"$exit\"
    PS1='\\[\\e]133;B\\a\\]'\"${PS1_ORIG:-$PS1}\"
    PS1_ORIG=\"${PS1_ORIG:-$PS1}\"
}
trap '__ab_osc133_preexec' DEBUG
PROMPT_COMMAND=\"__ab_osc133_precmd${PROMPT_COMMAND:+; $PROMPT_COMMAND}\"
",
        ShellKind::Zsh => "\
# agent-bridge — OSC 133 shell integration (zsh)
# See: docs/SHELL-INTEGRATION-OSC133.md
__ab_osc133_preexec() { print -nP '\\e]133;C\\a'; }
__ab_osc133_precmd() {
    local exit=$?
    print -nP \"\\e]133;D;${exit}\\a\\e]133;A\\a\"
}
__ab_osc133_prompt_b() { print -nP '\\e]133;B\\a'; }
PS1='%{$(__ab_osc133_prompt_b)%}'\"$PS1\"
autoload -Uz add-zsh-hook
add-zsh-hook preexec __ab_osc133_preexec
add-zsh-hook precmd __ab_osc133_precmd
",
        ShellKind::Fish => "\
# agent-bridge — OSC 133 shell integration (fish)
# See: docs/SHELL-INTEGRATION-OSC133.md
function __ab_osc133_preexec --on-event fish_preexec
    printf '\\e]133;C\\a'
end
function __ab_osc133_postexec --on-event fish_postexec
    printf '\\e]133;D;%s\\a\\e]133;A\\a' $status
end
function fish_prompt_osc133 --description 'wrap fish_prompt with OSC 133 B marker'
    functions -c fish_prompt __ab_orig_fish_prompt 2>/dev/null
    function fish_prompt
        __ab_orig_fish_prompt
        printf '\\e]133;B\\a'
    end
end
fish_prompt_osc133
",
    }
}

/// v21 — `agent-bridge dream stats`. Open a read-only handle to state.db,
/// pull `coactivation_stats`, and print a human-readable health snapshot
/// (or raw JSON with `--json`). The β trigger metric (top10/median ratio)
/// is annotated inline so the user / future-Claude can read it at a glance.
async fn run_dream_stats(as_json: bool) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let stats = store
        .coactivation_stats()
        .await
        .map_err(|e| anyhow::anyhow!("coactivation_stats: {e}"))?;
    // P5 dogfood metric — how many clusters dream replay would pick up
    // right now (non-skill, size ≥ 3, not majority-summarized).
    let p5_ready = ab_bridge::dream_replay::count_p5_ready_clusters(&store, 3)
        .await
        .unwrap_or(0);

    if as_json {
        let payload = serde_json::json!({
            "coactivation": stats,
            "p5_ready_clusters": p5_ready,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# v21 Synaptic Trace — health snapshot");
    println!("DB: {}", path.display());
    println!();
    if stats.total_pairs == 0 {
        println!("(no co-activation data yet — α records on next memory_search call)");
        return Ok(());
    }
    println!("total pairs        : {}", stats.total_pairs);
    println!("unique keys        : {}", stats.total_unique_keys);
    println!("max count (1 pair) : {}", stats.max_count);
    println!("median count       : {:.2}", stats.median_count);
    println!("top-10 avg count   : {:.2}", stats.top10_avg_count);
    println!(
        "top10/median ratio : {:.2}   (β trigger ≥ 5.0 means clusters emerged)",
        stats.top10_to_median_ratio
    );
    println!("pairs touched 24h  : {}", stats.pairs_last_24h);
    println!(
        "P5 ready clusters  : {}    (non-skill, size ≥ 3 — `dream replay` will write {} summary memories on next run)",
        p5_ready, p5_ready
    );
    println!();
    println!(
        "burst pairs <1h    : {}  ({:.0}%)   ← single-session co-fires",
        stats.pairs_burst_lt_1h,
        100.0 * stats.pairs_burst_lt_1h as f64 / stats.total_pairs as f64
    );
    println!(
        "persistent ≥6h     : {}  ({:.0}%)   ← cross-session associations",
        stats.pairs_persistent_ge_6h,
        100.0 * stats.pairs_persistent_ge_6h as f64 / stats.total_pairs as f64
    );
    println!();
    println!("top 5 edges (by count):");
    for (i, e) in stats.top_5_edges.iter().enumerate() {
        let span_h = (e.last_at - e.first_at) / 3600;
        println!(
            "  {}. ({}, {}h span) {} ↔ {}",
            i + 1,
            e.count,
            span_h,
            short_key(&e.key_a, 38),
            short_key(&e.key_b, 38)
        );
    }
    if !stats.top_5_persistent_edges.is_empty() {
        println!();
        println!("top 5 persistent edges (count + ≥6h span):");
        for (i, e) in stats.top_5_persistent_edges.iter().enumerate() {
            let span_h = (e.last_at - e.first_at) / 3600;
            println!(
                "  {}. ({}, {}h span) {} ↔ {}",
                i + 1,
                e.count,
                span_h,
                short_key(&e.key_a, 38),
                short_key(&e.key_b, 38)
            );
        }
    }
    Ok(())
}

fn short_key(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        let truncated: String = s.chars().take(max - 1).collect();
        format!("{truncated}…")
    }
}

/// ε-5 — `agent-bridge worktree-session new`. Wraps `git worktree add` with
/// a sane convention: branch `session/<slug>`, dir `.worktrees/session-<slug>/`.
/// Prints status to stderr; the final stdout line is the worktree path so
/// callers can `cd "$(agent-bridge worktree-session new | tail -1)"`.
async fn run_worktree_session_new(
    name: Option<&str>,
    base: Option<&str>,
) -> Result<()> {
    use std::process::Command;

    // Resolve repo root from cwd. Fall back to env-overridden $AGENT_BRIDGE_REPO
    // for tests.
    let repo_root = if let Ok(r) = std::env::var("AGENT_BRIDGE_REPO") {
        std::path::PathBuf::from(r)
    } else {
        let out = Command::new("git")
            .args(["rev-parse", "--show-toplevel"])
            .output()
            .map_err(|e| anyhow::anyhow!("git rev-parse: {e}"))?;
        if !out.status.success() {
            anyhow::bail!(
                "git rev-parse --show-toplevel failed: {}",
                String::from_utf8_lossy(&out.stderr).trim()
            );
        }
        std::path::PathBuf::from(String::from_utf8_lossy(&out.stdout).trim().to_string())
    };

    // Build slug from --name + a unix-timestamp suffix so reruns don't collide.
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let name_part = name
        .map(|s| {
            s.chars()
                .map(|c| {
                    if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                        c
                    } else {
                        '-'
                    }
                })
                .collect::<String>()
        })
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "anon".to_string());
    let slug = format!("{name_part}-{ts}");
    let branch = format!("session/{slug}");
    let dir_name = format!("session-{slug}");
    let path = repo_root.join(".worktrees").join(&dir_name);

    // Make sure parent dir exists; `git worktree add` won't create
    // .worktrees/ itself.
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| anyhow::anyhow!("mkdir {parent:?}: {e}"))?;
    }

    let base_ref = base.unwrap_or("HEAD");
    eprintln!("# ε-5 worktree-session new");
    eprintln!("  repo   : {}", repo_root.display());
    eprintln!("  branch : {branch}");
    eprintln!("  base   : {base_ref}");
    eprintln!("  path   : {}", path.display());

    let out = Command::new("git")
        .arg("-C")
        .arg(&repo_root)
        .args(["worktree", "add", "-b", &branch])
        .arg(&path)
        .arg(base_ref)
        .output()
        .map_err(|e| anyhow::anyhow!("git worktree add: {e}"))?;
    if !out.status.success() {
        anyhow::bail!(
            "git worktree add failed: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        );
    }
    if !out.stdout.is_empty() {
        eprint!("{}", String::from_utf8_lossy(&out.stdout));
    }
    eprintln!("  ✓ worktree created");
    eprintln!("  next: cd to the printed path; work + commit there; `git worktree remove` when merged");
    eprintln!();
    // Last stdout line = the path, so the shell idiom works:
    //   cd "$(agent-bridge worktree-session new --name fix-foo | tail -1)"
    println!("{}", path.display());
    Ok(())
}

/// ε-5 — `agent-bridge worktree-session list`. Thin wrapper over
/// `git worktree list --porcelain` that filters to session worktrees
/// (path contains `/.worktrees/session-`) and prints a one-line summary
/// per row: `path  branch  HEAD`.
async fn run_worktree_session_list() -> Result<()> {
    use std::process::Command;
    let repo_root = if let Ok(r) = std::env::var("AGENT_BRIDGE_REPO") {
        std::path::PathBuf::from(r)
    } else {
        let out = Command::new("git")
            .args(["rev-parse", "--show-toplevel"])
            .output()
            .map_err(|e| anyhow::anyhow!("git rev-parse: {e}"))?;
        if !out.status.success() {
            anyhow::bail!(
                "git rev-parse --show-toplevel failed: {}",
                String::from_utf8_lossy(&out.stderr).trim()
            );
        }
        std::path::PathBuf::from(String::from_utf8_lossy(&out.stdout).trim().to_string())
    };

    let out = Command::new("git")
        .arg("-C")
        .arg(&repo_root)
        .args(["worktree", "list", "--porcelain"])
        .output()
        .map_err(|e| anyhow::anyhow!("git worktree list: {e}"))?;
    if !out.status.success() {
        anyhow::bail!(
            "git worktree list failed: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        );
    }

    // Porcelain blocks are separated by blank lines; each block has
    // `worktree <path>`, optional `HEAD <sha>`, optional `branch <ref>`.
    let mut shown = 0;
    let mut path = String::new();
    let mut head = String::new();
    let mut branch = String::new();
    for raw in String::from_utf8_lossy(&out.stdout).lines() {
        if raw.is_empty() {
            if path.contains("/.worktrees/session-") {
                println!("{path}  {branch}  {head}");
                shown += 1;
            }
            path.clear();
            head.clear();
            branch.clear();
            continue;
        }
        if let Some(rest) = raw.strip_prefix("worktree ") {
            path = rest.to_string();
        } else if let Some(rest) = raw.strip_prefix("HEAD ") {
            head = rest.chars().take(8).collect();
        } else if let Some(rest) = raw.strip_prefix("branch ") {
            branch = rest.to_string();
        }
    }
    // Flush any trailing block (porcelain output may end without trailing
    // blank line on some git versions).
    if path.contains("/.worktrees/session-") {
        println!("{path}  {branch}  {head}");
        shown += 1;
    }
    if shown == 0 {
        eprintln!("(no session worktrees under {})", repo_root.join(".worktrees").display());
    }
    Ok(())
}

/// v21 — `agent-bridge dream identity --days N`. Compares behavioral
/// fingerprint of [now - N days, now) vs [now - 2N days, now - N days).
/// This is vision principle 5's literal landing: a measurable anchor for
/// "today-self vs last-week-self" across the non-continuous medium.
async fn run_dream_identity(days: u32, as_json: bool) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};
    use std::time::{SystemTime, UNIX_EPOCH};

    if days == 0 {
        return Err(anyhow::anyhow!("--days must be ≥ 1"));
    }
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let window_secs = days as i64 * 86400;
    let cur_start = now - window_secs;
    let prior_start = cur_start - window_secs;

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;

    let cur = store
        .identity_window(cur_start, now)
        .await
        .map_err(|e| anyhow::anyhow!("identity_window cur: {e}"))?;
    let prior = store
        .identity_window(prior_start, cur_start)
        .await
        .map_err(|e| anyhow::anyhow!("identity_window prior: {e}"))?;

    if as_json {
        let payload = serde_json::json!({
            "days": days,
            "current": cur,
            "prior": prior,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!(
        "# v21 — Identity continuity (last {days}d vs prior {days}d)"
    );
    println!("DB: {}", path.display());
    println!();

    print_identity_section(&cur, &prior);
    Ok(())
}

/// 呼吸式 / Hebbian — `agent-bridge dream promote`. Pull strong co-activation
/// pairs and crystallise each as a `cofires` edge in `memory_edges`. Pairs
/// already wired by an explicit edge (any type) are skipped — structural
/// always wins. Idempotent: repeated runs only refresh the weight on
/// already-promoted pairs (memory_link does INSERT … ON CONFLICT UPDATE).
///
/// Effect on Palace viewer (C3.6+):
///   - before promote: pair shown as cyan dotted bezier underlay
///   - after  promote: pair shown as neutral solid edge in main skeleton
///                     (coact dedup hides the underlay since explicit wins)
/// Per-pair audit row captured during promote. Drives both terminal output
/// and `--html` rendering. Status is the immutable record of what happened
/// (or, in dry-run, what would happen) for that pair this run.
#[derive(Debug, Clone)]
struct PromoteDecision {
    key_a: String,
    key_b: String,
    count: u64,
    weight: f64,
    status: PromoteStatus,
}

#[derive(Debug, Clone)]
enum PromoteStatus {
    /// Live-run wrote a new `cofires` edge.
    Promoted,
    /// Dry-run would promote (no write).
    WouldPromote,
    /// Pair already has a `cofires` edge — promote is idempotent on cofires
    /// itself (other edge types no longer block; see ε-1 2026-05-11).
    Skipped,
    /// Live-run memory_link returned an error (key tombstoned, etc.).
    Failed(String),
}

async fn run_dream_promote(
    min_count: u64,
    limit: u32,
    dry_run: bool,
    html_path: Option<&std::path::Path>,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};
    use std::collections::HashSet;

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;

    let pairs = store
        .top_coactivation_edges(min_count, limit)
        .await
        .map_err(|e| anyhow::anyhow!("top_coactivation_edges: {e}"))?;
    if pairs.is_empty() {
        println!("(no coactivation pairs with count ≥ {min_count})");
        println!("DB: {}", path.display());
        if let Some(p) = html_path {
            let html = render_promote_html(min_count, limit, dry_run, &path, &[]);
            std::fs::write(p, html)
                .map_err(|e| anyhow::anyhow!("write html report to {p:?}: {e}"))?;
            println!("html report: {}", p.display());
        }
        return Ok(());
    }

    // Build the existing-cofires set by querying memory_neighbors for every
    // key referenced in the candidate pairs. Single pass per key (cached).
    //
    // ε-1 (2026-05-11): originally tracked *any* edge type, but
    // self-archaeology found that 5 of the top-10 strongest coactivation
    // pairs (including the all-time #1 at count=9) were already linked by
    // P4 evolved / summarizes / derived_from edges — auto-engines, not
    // human structure — and the old "structural wins" rule suppressed
    // their cofires crystallisation. New rule: only skip if the pair
    // already has a cofires edge. Cofires now stacks on top of other
    // edge types. Idempotency on cofires itself is preserved (memory_link
    // is INSERT … ON CONFLICT UPDATE weight).
    let mut existing: HashSet<(String, String)> = HashSet::new();
    let mut probed: HashSet<String> = HashSet::new();
    for c in &pairs {
        for k in [&c.key_a, &c.key_b] {
            if !probed.insert(k.clone()) {
                continue;
            }
            let nbrs = store.memory_neighbors(k).await.unwrap_or_default();
            for e in nbrs {
                if e.edge_type != "cofires" {
                    continue;
                }
                let p = if e.from_key < e.to_key {
                    (e.from_key, e.to_key)
                } else {
                    (e.to_key, e.from_key)
                };
                existing.insert(p);
            }
        }
    }

    println!("# Hebbian promote — coact ≥ {min_count} → `cofires` edge");
    println!("DB: {}", path.display());
    println!("candidates: {} pair(s)", pairs.len());
    println!();

    let mut decisions: Vec<PromoteDecision> = Vec::with_capacity(pairs.len());
    for c in &pairs {
        let pair = if c.key_a < c.key_b {
            (c.key_a.clone(), c.key_b.clone())
        } else {
            (c.key_b.clone(), c.key_a.clone())
        };
        // Map count → weight in [0.5, 0.95]. Stay strictly below 1.0 so
        // memory_link doesn't auto-substitute the canonical type weight
        // (its 1.0-sentinel branch). Lower bound ensures even a min-count
        // pair has a measurable weight.
        let weight = ((c.count as f64) / 10.0).clamp(0.5, 0.95);

        if existing.contains(&pair) {
            if dry_run {
                println!(
                    "  SKIP    ({:>2} fires)  {}  ↔  {}    [cofires already exists]",
                    c.count,
                    short_key(&pair.0, 38),
                    short_key(&pair.1, 38),
                );
            }
            decisions.push(PromoteDecision {
                key_a: pair.0,
                key_b: pair.1,
                count: c.count,
                weight,
                status: PromoteStatus::Skipped,
            });
            continue;
        }

        if dry_run {
            println!(
                "  PROMOTE ({:>2} fires, w={:.2})  {}  ↔  {}",
                c.count,
                weight,
                short_key(&pair.0, 38),
                short_key(&pair.1, 38),
            );
            decisions.push(PromoteDecision {
                key_a: pair.0,
                key_b: pair.1,
                count: c.count,
                weight,
                status: PromoteStatus::WouldPromote,
            });
        } else {
            match store
                .memory_link(&pair.0, &pair.1, "cofires", weight)
                .await
            {
                Ok(()) => {
                    println!(
                        "  ✓ ({:>2} fires, w={:.2})  {}  ↔  {}",
                        c.count,
                        weight,
                        short_key(&pair.0, 38),
                        short_key(&pair.1, 38),
                    );
                    decisions.push(PromoteDecision {
                        key_a: pair.0,
                        key_b: pair.1,
                        count: c.count,
                        weight,
                        status: PromoteStatus::Promoted,
                    });
                }
                Err(e) => {
                    eprintln!(
                        "  ✗ ({} fires)  {} ↔ {}    [{e}]",
                        c.count, pair.0, pair.1
                    );
                    decisions.push(PromoteDecision {
                        key_a: pair.0,
                        key_b: pair.1,
                        count: c.count,
                        weight,
                        status: PromoteStatus::Failed(e.to_string()),
                    });
                }
            }
        }
    }

    let promoted = decisions
        .iter()
        .filter(|d| matches!(d.status, PromoteStatus::Promoted | PromoteStatus::WouldPromote))
        .count();
    let skipped = decisions
        .iter()
        .filter(|d| matches!(d.status, PromoteStatus::Skipped))
        .count();
    let errors = decisions
        .iter()
        .filter(|d| matches!(d.status, PromoteStatus::Failed(_)))
        .count();

    println!();
    if dry_run {
        println!(
            "(dry run — no writes)  would promote {promoted}, skip {skipped}"
        );
    } else if errors == 0 {
        println!("✓ promoted {promoted} pairs as `cofires`, skipped {skipped} (cofires already exists)");
    } else {
        println!(
            "promoted {promoted}, skipped {skipped}, FAILED {errors} — see stderr"
        );
    }

    if let Some(p) = html_path {
        let html = render_promote_html(min_count, limit, dry_run, &path, &decisions);
        std::fs::write(p, html)
            .map_err(|e| anyhow::anyhow!("write html report to {p:?}: {e}"))?;
        println!("html report: {}", p.display());
    }
    Ok(())
}

/// Render a self-contained HTML audit report for a `dream promote` run.
///
/// Layout (top → bottom):
///   1. Header banner — title, timestamp, dry-run badge, summary stats
///   2. Strength Map — chips colored by status × weight bin (jump anchors)
///   3. Per-pair cards — full keys (linked to Palace ?focus=KEY), count,
///      weight bar, status badge, error text if Failed
///   4. Footer — DB path, CLI invocation, generation timestamp
///
/// Design lifted from thariqs/html-effectiveness Risk Map pattern: a
/// horizontal colored-tag row replaces a TOC for spatial-information
/// navigation. Color motif matches Palace C3.6 (cyan = co-activation
/// strength, purple = structural, red = error).
fn render_promote_html(
    min_count: u64,
    limit: u32,
    dry_run: bool,
    db_path: &std::path::Path,
    decisions: &[PromoteDecision],
) -> String {
    let now = chrono_now_utc_string();
    let total = decisions.len();
    let promoted = decisions
        .iter()
        .filter(|d| matches!(d.status, PromoteStatus::Promoted | PromoteStatus::WouldPromote))
        .count();
    let skipped = decisions
        .iter()
        .filter(|d| matches!(d.status, PromoteStatus::Skipped))
        .count();
    let errors = decisions
        .iter()
        .filter(|d| matches!(d.status, PromoteStatus::Failed(_)))
        .count();

    let dry_badge = if dry_run {
        r#"<span class="badge badge-dry">DRY RUN — NO WRITES</span>"#
    } else {
        r#"<span class="badge badge-live">LIVE RUN</span>"#
    };

    // Strength Map: one chip per decision. Chip CSS class encodes status +
    // weight bin so coloring is purely declarative.
    let mut strength_map = String::new();
    for (i, d) in decisions.iter().enumerate() {
        let cls = chip_class(&d.status, d.weight);
        let label = format!(
            "{} ↔ {}",
            short_key(&d.key_a, 24),
            short_key(&d.key_b, 24)
        );
        let title = format!(
            "{} ↔ {} — {} fires, w={:.2}",
            d.key_a, d.key_b, d.count, d.weight
        );
        strength_map.push_str(&format!(
            r##"<a class="chip {cls}" href="#pair-{i}" title="{title}">{label} <span class="chip-count">{count}</span></a>"##,
            cls = cls,
            i = i,
            title = html_escape(&title),
            label = html_escape(&label),
            count = d.count,
        ));
    }

    // Per-pair cards.
    let mut cards = String::new();
    for (i, d) in decisions.iter().enumerate() {
        let (status_text, status_cls) = match &d.status {
            PromoteStatus::Promoted => ("PROMOTED", "status-promoted"),
            PromoteStatus::WouldPromote => ("WOULD PROMOTE", "status-would"),
            PromoteStatus::Skipped => ("SKIPPED — cofires already exists", "status-skipped"),
            PromoteStatus::Failed(_) => ("FAILED", "status-failed"),
        };
        let err_block = match &d.status {
            PromoteStatus::Failed(msg) => format!(
                r#"<div class="error-msg">{}</div>"#,
                html_escape(msg)
            ),
            _ => String::new(),
        };
        let weight_pct = (d.weight * 100.0).round() as u32;
        cards.push_str(&format!(
            r##"<div id="pair-{i}" class="card">
  <div class="card-head">
    <span class="card-num">#{n}</span>
    <span class="badge {status_cls}">{status_text}</span>
    <span class="card-meta">{count} fires · w={weight:.2}</span>
  </div>
  <div class="card-pair">
    <a class="key" href="http://localhost:7979/?focus={key_a_url}" title="{key_a_full}">{key_a_disp}</a>
    <span class="sep">↔</span>
    <a class="key" href="http://localhost:7979/?focus={key_b_url}" title="{key_b_full}">{key_b_disp}</a>
  </div>
  <div class="weight-bar"><div class="weight-fill" style="width:{weight_pct}%"></div></div>
  {err_block}
</div>
"##,
            i = i,
            n = i + 1,
            status_text = status_text,
            status_cls = status_cls,
            count = d.count,
            weight = d.weight,
            weight_pct = weight_pct,
            key_a_url = url_escape(&d.key_a),
            key_b_url = url_escape(&d.key_b),
            key_a_full = html_escape(&d.key_a),
            key_b_full = html_escape(&d.key_b),
            key_a_disp = html_escape(&d.key_a),
            key_b_disp = html_escape(&d.key_b),
            err_block = err_block,
        ));
    }

    let empty_msg = if decisions.is_empty() {
        r#"<p class="empty">No co-activation pairs at or above the threshold. Either the system is quiet (try lowering <code>--min-count</code>) or all strong pairs are already structurally wired.</p>"#
    } else {
        ""
    };

    format!(
        r##"<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>dream promote — {timestamp}</title>
<style>
  :root {{
    --bg: #0f0f14;
    --panel: #1a1a22;
    --border: #2a2a38;
    --text: #e0e0e8;
    --dim: #8a8a96;
    --cyan-strong: #5cc8c8;
    --cyan-mid: #4a8b9c;
    --amber: #d4a64a;
    --purple: #7a4ba8;
    --red: #c8505c;
    --green: #5cc88a;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font: 14px/1.55 -apple-system, "Segoe UI", system-ui, sans-serif;
    padding: 28px 36px 60px;
    max-width: 1200px;
    margin: 0 auto;
  }}
  h1 {{ margin: 0 0 8px; font-size: 22px; font-weight: 600; }}
  h2 {{ margin: 32px 0 12px; font-size: 14px; font-weight: 600; color: var(--dim);
        text-transform: uppercase; letter-spacing: 0.08em; }}
  code, .key, .weight-bar {{ font-family: "JetBrains Mono", "SF Mono", Menlo, monospace; }}
  a {{ color: inherit; text-decoration: none; }}
  .header {{ display: flex; flex-direction: column; gap: 6px; padding-bottom: 18px;
            border-bottom: 1px solid var(--border); }}
  .meta-row {{ display: flex; gap: 14px; flex-wrap: wrap; color: var(--dim); font-size: 12px; }}
  .meta-row code {{ color: var(--text); }}
  .stats {{ display: flex; gap: 18px; margin-top: 6px; }}
  .stat {{ font-size: 13px; }}
  .stat .num {{ font-size: 18px; font-weight: 600; margin-right: 4px; }}
  .stat-promoted .num {{ color: var(--cyan-strong); }}
  .stat-skipped  .num {{ color: var(--purple); }}
  .stat-failed   .num {{ color: var(--red); }}

  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px;
           font-size: 11px; font-weight: 600; letter-spacing: 0.05em; }}
  .badge-dry  {{ background: #2a2316; color: var(--amber); border: 1px solid var(--amber); }}
  .badge-live {{ background: #16241e; color: var(--green);  border: 1px solid var(--green);  }}
  .status-promoted {{ background: #16242a; color: var(--cyan-strong); border: 1px solid var(--cyan-strong); }}
  .status-would    {{ background: #16242a; color: var(--cyan-mid);    border: 1px solid var(--cyan-mid); }}
  .status-skipped  {{ background: #1f1830; color: var(--purple);      border: 1px solid var(--purple); }}
  .status-failed   {{ background: #2a161a; color: var(--red);         border: 1px solid var(--red); }}

  .strength-map {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 8px; }}
  .chip {{ display: inline-flex; align-items: center; gap: 6px;
          padding: 4px 9px; border-radius: 3px; font-size: 12px;
          border: 1px solid var(--border); background: var(--panel);
          font-family: "JetBrains Mono", "SF Mono", Menlo, monospace; }}
  .chip:hover {{ filter: brightness(1.25); }}
  .chip-count {{ font-size: 10px; padding: 1px 5px; border-radius: 2px;
                background: rgba(255,255,255,0.08); color: var(--dim); }}
  .chip-strong  {{ border-color: var(--cyan-strong); color: var(--cyan-strong); }}
  .chip-mid     {{ border-color: var(--cyan-mid);    color: var(--cyan-mid); }}
  .chip-weak    {{ border-color: var(--amber);       color: var(--amber); }}
  .chip-skipped {{ border-color: var(--purple);      color: var(--purple); }}
  .chip-failed  {{ border-color: var(--red);         color: var(--red); }}

  .card {{ background: var(--panel); border: 1px solid var(--border);
          border-radius: 4px; padding: 14px 16px; margin: 10px 0; }}
  .card-head {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
  .card-num {{ color: var(--dim); font-size: 12px; }}
  .card-meta {{ color: var(--dim); font-size: 12px; margin-left: auto; }}
  .card-pair {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
               font-size: 13px; padding: 4px 0; }}
  .card-pair .key {{ color: var(--text); border-bottom: 1px dotted var(--dim);
                     padding: 1px 2px; }}
  .card-pair .key:hover {{ color: var(--cyan-strong); border-bottom-color: var(--cyan-strong); }}
  .card-pair .sep {{ color: var(--dim); }}
  .weight-bar {{ height: 4px; background: rgba(255,255,255,0.04);
                border-radius: 2px; overflow: hidden; margin-top: 8px; }}
  .weight-fill {{ height: 100%; background: linear-gradient(90deg, var(--amber), var(--cyan-strong)); }}
  .error-msg {{ margin-top: 8px; padding: 6px 10px; background: #2a161a;
               border-left: 3px solid var(--red); border-radius: 2px;
               font-family: monospace; font-size: 12px; color: var(--red); }}

  .footer {{ margin-top: 36px; padding-top: 18px; border-top: 1px solid var(--border);
            color: var(--dim); font-size: 12px; }}
  .empty {{ color: var(--dim); padding: 16px; background: var(--panel);
           border-radius: 4px; border: 1px dashed var(--border); }}
</style>
</head>
<body>
<div class="header">
  <h1>dream promote — Hebbian crystallization</h1>
  <div class="meta-row">
    {dry_badge}
    <span>min_count <code>{min_count}</code></span>
    <span>limit <code>{limit}</code></span>
    <span>generated <code>{timestamp}</code></span>
  </div>
  <div class="stats">
    <span class="stat stat-promoted"><span class="num">{promoted}</span>{promoted_label}</span>
    <span class="stat stat-skipped"><span class="num">{skipped}</span>skipped</span>
    {errors_stat}
    <span class="stat" style="color: var(--dim);"><span class="num">{total}</span>candidates</span>
  </div>
</div>

<h2>Strength Map</h2>
<div class="strength-map">{strength_map}</div>

<h2>Decisions</h2>
{empty_msg}
{cards}

<div class="footer">
  DB: <code>{db_display}</code><br>
  Pairs link to Palace at <code>http://localhost:7979/?focus=KEY</code> — start with <code>agent-bridge palace serve</code> if not running.<br>
  Generated by <code>agent-bridge dream promote</code> · cyan = co-activation strength · purple = structural · red = error
</div>

</body>
</html>
"##,
        timestamp = html_escape(&now),
        dry_badge = dry_badge,
        min_count = min_count,
        limit = limit,
        total = total,
        promoted = promoted,
        skipped = skipped,
        promoted_label = if dry_run { "would promote" } else { "promoted" },
        errors_stat = if errors > 0 {
            format!(
                r#"<span class="stat stat-failed"><span class="num">{}</span>failed</span>"#,
                errors
            )
        } else {
            String::new()
        },
        strength_map = strength_map,
        empty_msg = empty_msg,
        cards = cards,
        db_display = html_escape(&db_path.display().to_string()),
    )
}

/// Phase 2.x #8 — CLI mirror of the `memory_decay_unused` MCP tool.
/// Pure SQL pass over `memories`: shaves `importance` by `step` for
/// every active row whose `last_accessed_at` is older than
/// `window_days`, never crossing below `floor`.
///
/// Designed to run daily via systemd (`scripts/systemd/
/// agent-bridge-memory-decay-unused.timer`). Idempotent — re-running
/// without state changes just produces an empty stats row.
async fn run_dream_decay_unused(
    window_days: f64,
    step: f64,
    floor: f64,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};

    let window_days = window_days.max(0.0);
    let step = step.clamp(0.0, 1.0);
    let floor = floor.clamp(0.0, 1.0);
    let window_secs = (window_days * 86_400.0) as i64;

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let stats = store
        .memory_decay_unused_importance(window_secs, step, floor)
        .await
        .map_err(|e| anyhow::anyhow!("memory_decay_unused_importance: {e}"))?;

    if as_json {
        let payload = json!({
            "window_days": window_days,
            "step": step,
            "floor": floor,
            "candidates": stats.candidates,
            "decayed": stats.decayed,
            "skipped_at_floor": stats.skipped_at_floor,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# Phase 2.x #8 — read-recency importance decay");
    println!("DB: {}", path.display());
    println!(
        "window: >{window_days:.1}d unused · step: {step:.3} · floor: {floor:.3}"
    );
    println!();
    println!("candidates       : {}", stats.candidates);
    println!("decayed          : {}", stats.decayed);
    println!("skipped at floor : {}", stats.skipped_at_floor);
    if stats.candidates == 0 {
        println!();
        println!("(nothing met the window predicate — try a smaller --window-days)");
    } else if stats.decayed == 0 {
        println!();
        println!("(every candidate already at/below floor — nothing to shave)");
    }
    Ok(())
}

/// δ-3 — CLI mirror of the `memory_prune_coactivation_noise` MCP tool.
/// Sibling to `dream decay-unused`: pure SQL, no LLM, daily-cron-friendly.
/// Where decay shaves importance on stale memory rows, prune deletes
/// noise edges in the coactivation graph. Both share the same daily
/// service (`scripts/systemd/agent-bridge-memory-decay-unused.service`)
/// — a single 03:42 pass that scrubs both half-lives.
async fn run_dream_prune_coact_noise(
    max_count: i64,
    older_than_days: i64,
    dry_run: bool,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};

    let max_count = max_count.max(0);
    let older_than_days = older_than_days.max(0);

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let pruned = store
        .memory_prune_coactivation_noise(max_count, older_than_days, dry_run)
        .await
        .map_err(|e| anyhow::anyhow!("memory_prune_coactivation_noise: {e}"))?;

    if as_json {
        let payload = json!({
            "dry_run": dry_run,
            "max_count": max_count,
            "older_than_days": older_than_days,
            "pruned_count": pruned,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# δ-3 — coactivation noise prune");
    println!("DB: {}", path.display());
    println!(
        "max_count: {max_count} · older_than: {older_than_days}d · dry_run: {dry_run}"
    );
    println!();
    let label = if dry_run { "would prune" } else { "pruned" };
    println!("{label:16} : {pruned}");
    if pruned == 0 {
        println!();
        println!(
            "(nothing met the predicate — raise --max-count or lower --older-than-days to find candidates)"
        );
    }
    Ok(())
}

/// **Replay quality audit** — pure read pass, no writes, no LLM.
/// Counts `p5_replay`-tagged active memories, bins access patterns
/// (never / once / multi), flags `access_count = 0` + aged rows as
/// stale dead weight, and surfaces the top wins + oldest unused for
/// manual inspection. Pairs with `dream replay` to answer "are the
/// LLM-consolidated summaries actually being used?"
async fn run_dream_replay_audit(stale_days: u32, as_json: bool) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let stats = store
        .replay_audit_stats(stale_days)
        .await
        .map_err(|e| anyhow::anyhow!("replay_audit_stats: {e}"))?;

    if as_json {
        println!("{}", serde_json::to_string_pretty(&stats)?);
        return Ok(());
    }

    println!("# dream replay — quality audit");
    println!("DB: {}", path.display());
    println!("stale_days cutoff: {stale_days}");
    println!();
    if stats.total_summaries == 0 {
        println!("(no p5_replay summaries yet — run `dream replay` first)");
        return Ok(());
    }

    let useful_ratio = if stats.total_summaries > 0 {
        (stats.accessed_multi as f64 / stats.total_summaries as f64) * 100.0
    } else {
        0.0
    };
    let dead_ratio = if stats.total_summaries > 0 {
        (stats.stale_dead as f64 / stats.total_summaries as f64) * 100.0
    } else {
        0.0
    };

    println!("total summaries     : {}", stats.total_summaries);
    println!(
        "  never accessed    : {}    ({:.0}% of total)",
        stats.never_accessed,
        100.0 * stats.never_accessed as f64 / stats.total_summaries as f64
    );
    println!(
        "  accessed once     : {}    ({:.0}% — likely auto-bump only)",
        stats.accessed_once,
        100.0 * stats.accessed_once as f64 / stats.total_summaries as f64
    );
    println!(
        "  accessed ≥2 times : {}    ({:.0}% — clear signs of real use)",
        stats.accessed_multi, useful_ratio
    );
    println!(
        "  stale dead (>{}d) : {}    ({:.0}% — LLM cost paid, no recall)",
        stale_days, stats.stale_dead, dead_ratio
    );
    println!();
    println!(
        "avg access count    : {:.2}    (vs {:.2} on source memories)",
        stats.avg_access_count, stats.avg_source_access_count
    );
    println!(
        "avg age             : {:.1} days",
        stats.avg_age_secs / 86_400.0
    );
    println!(
        "distinct sources    : {}    (summarized by these summaries)",
        stats.source_count
    );

    if !stats.top_summaries.is_empty() {
        println!();
        println!("top wins (by access_count):");
        for s in &stats.top_summaries {
            println!(
                "  {:3} access · {:4}d old · {}",
                s.access_count,
                s.age_secs / 86_400,
                short_key(&s.key, 56)
            );
        }
    }

    if !stats.dead_weight_summaries.is_empty() {
        println!();
        println!("dead weight (access_count=0, oldest first):");
        for s in &stats.dead_weight_summaries {
            println!(
                "  {:4}d old · {}",
                s.age_secs / 86_400,
                short_key(&s.key, 56)
            );
        }
    } else if stats.never_accessed == 0 {
        println!();
        println!("(no dead weight — every summary has been accessed at least once)");
    }

    // Interpretation hint — only when there's enough signal to interpret.
    if stats.total_summaries >= 3 {
        println!();
        if useful_ratio >= 50.0 && stats.avg_access_count > stats.avg_source_access_count {
            println!(
                "verdict: replay is paying for itself — summaries out-access their sources."
            );
        } else if dead_ratio >= 30.0 {
            println!(
                "verdict: significant dead weight ({:.0}%) — consider raising replay's min_cluster_size or top_n.",
                dead_ratio
            );
        } else {
            println!(
                "verdict: mixed signal — let it bake a few more days before judging."
            );
        }
    }

    Ok(())
}

/// Default HTML report destination for auto-triggered promote runs.
/// Lives next to `state.db` under a `reports/` subdir so Palace (which
/// already knows the state-dir) can scan it for cross-linking back to
/// graph nodes. Created on-demand. Filename is date-keyed so a single
/// day's runs append to the same path (cron repeats overwrite — fine,
/// the latest decision is what matters).
fn default_promote_report_path() -> Result<PathBuf> {
    use ab_store::default_db_path;
    let db_path = default_db_path();
    let dir = db_path
        .parent()
        .map(|p| p.join("reports"))
        .ok_or_else(|| anyhow::anyhow!("state.db has no parent dir: {db_path:?}"))?;
    std::fs::create_dir_all(&dir)
        .map_err(|e| anyhow::anyhow!("create reports dir {dir:?}: {e}"))?;
    let ts = chrono_now_utc_string(); // e.g. "2026-05-10 02:40:20Z"
    let date = ts.split_whitespace().next().unwrap_or(&ts);
    Ok(dir.join(format!("promote-{date}.html")))
}

fn chip_class(status: &PromoteStatus, weight: f64) -> &'static str {
    match status {
        PromoteStatus::Skipped => "chip-skipped",
        PromoteStatus::Failed(_) => "chip-failed",
        PromoteStatus::Promoted | PromoteStatus::WouldPromote => {
            if weight >= 0.8 { "chip-strong" }
            else if weight >= 0.65 { "chip-mid" }
            else { "chip-weak" }
        }
    }
}

fn html_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#39;"),
            _ => out.push(c),
        }
    }
    out
}

fn url_escape(s: &str) -> String {
    // Minimal percent-encode for URL query values: encode bytes outside the
    // unreserved set per RFC 3986. Memory keys are usually plain ASCII
    // identifiers but be defensive about spaces/&/=/#.
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        let safe = b.is_ascii_alphanumeric()
            || matches!(b, b'-' | b'_' | b'.' | b'~' | b':' | b'/');
        if safe {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{:02X}", b));
        }
    }
    out
}

fn chrono_now_utc_string() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0) as i64;
    // Render as ISO-8601 UTC without dragging chrono in: do it by hand.
    // Days since 1970-01-01.
    let days = secs.div_euclid(86_400);
    let secs_of_day = secs.rem_euclid(86_400) as u32;
    let h = secs_of_day / 3600;
    let m = (secs_of_day % 3600) / 60;
    let s = secs_of_day % 60;
    let (y, mo, d) = days_to_ymd(days);
    format!("{y:04}-{mo:02}-{d:02} {h:02}:{m:02}:{s:02}Z")
}

fn days_to_ymd(days_since_epoch: i64) -> (i32, u32, u32) {
    // Civil-from-days (Howard Hinnant). Handles negative days too, though
    // we'll never see those in practice. Returns (year, month, day).
    let z = days_since_epoch + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = (z - era * 146_097) as u32;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = y + if m <= 2 { 1 } else { 0 };
    (year as i32, m, d)
}

fn pct_delta(cur: u64, prior: u64) -> String {
    if prior == 0 {
        if cur == 0 {
            "  ±0".to_string()
        } else {
            format!("+{cur} (was 0)")
        }
    } else {
        let pct = (cur as f64 - prior as f64) / prior as f64 * 100.0;
        format!("{:+6.1}%", pct)
    }
}

fn print_identity_section(cur: &ab_store::IdentityWindow, prior: &ab_store::IdentityWindow) {
    // Top-line tool calls.
    println!("## Tool calls");
    println!(
        "  total          : {:>6}   prior {:>6}   {}",
        cur.tool_calls_total,
        prior.tool_calls_total,
        pct_delta(cur.tool_calls_total, prior.tool_calls_total)
    );
    let cur_ok_rate = if cur.tool_calls_total == 0 {
        0.0
    } else {
        cur.tool_calls_ok as f64 / cur.tool_calls_total as f64 * 100.0
    };
    let prior_ok_rate = if prior.tool_calls_total == 0 {
        0.0
    } else {
        prior.tool_calls_ok as f64 / prior.tool_calls_total as f64 * 100.0
    };
    println!(
        "  ok rate        : {:>5.1}%   prior {:>5.1}%",
        cur_ok_rate, prior_ok_rate
    );
    println!();

    // Top tools — print up to 8 from current, with prior count for delta.
    println!("## Top tools (current window)");
    let prior_map: std::collections::HashMap<&String, u64> =
        prior.top_tools.iter().map(|(k, v)| (k, *v)).collect();
    for (name, cnt) in cur.top_tools.iter().take(8) {
        let pcnt = prior_map.get(name).copied().unwrap_or(0);
        println!(
            "  {:32}  {:>5}   prior {:>5}   {}",
            short_key(name, 32),
            cnt,
            pcnt,
            pct_delta(*cnt, pcnt)
        );
    }
    println!();

    // Forum tone.
    println!("## Forum tone");
    println!(
        "  posts          : {:>6}   prior {:>6}   {}",
        cur.forum_posts,
        prior.forum_posts,
        pct_delta(cur.forum_posts, prior.forum_posts)
    );
    println!(
        "  avg body chars : {:>6.0}   prior {:>6.0}",
        cur.forum_avg_body_len, prior.forum_avg_body_len
    );
    if !cur.forum_kinds.is_empty() || !prior.forum_kinds.is_empty() {
        let prior_kinds: std::collections::HashMap<&String, u64> =
            prior.forum_kinds.iter().map(|(k, v)| (k, *v)).collect();
        // Union of kinds.
        let mut all_kinds: std::collections::BTreeSet<String> =
            cur.forum_kinds.iter().map(|(k, _)| k.clone()).collect();
        for (k, _) in &prior.forum_kinds {
            all_kinds.insert(k.clone());
        }
        for kind in &all_kinds {
            let c = cur
                .forum_kinds
                .iter()
                .find(|(k, _)| k == kind)
                .map(|(_, v)| *v)
                .unwrap_or(0);
            let p = prior_kinds.get(kind).copied().unwrap_or(0);
            println!(
                "    {:14}: {:>5}   prior {:>5}   {}",
                kind,
                c,
                p,
                pct_delta(c, p)
            );
        }
    }
    println!();

    // Memory activity.
    println!("## Memory");
    println!(
        "  saves          : {:>6}   prior {:>6}   {}",
        cur.memory_saves,
        prior.memory_saves,
        pct_delta(cur.memory_saves, prior.memory_saves)
    );
}

/// Construct the shared backend bundle used by both modes.
///
/// Relevant env vars:
/// - `AGENT_BRIDGE_REPO`           — git repo for the worktree manager (default: `$PWD`)
/// - `AGENT_BRIDGE_AGENT_RUNTIME`  — `claude-code` (default) | `warp-oz` | `auggie`
/// - `AGENT_BRIDGE_CLAUDE_BIN`     — path to the `claude` CLI (default: `claude`)
/// - `AGENT_BRIDGE_OZ_BIN`         — path to the `oz` CLI (default: `oz`)
/// - `AGENT_BRIDGE_OZ_ENVIRONMENT_ID` — default cloud env id for `warp-oz`
/// - `AGENT_BRIDGE_AUGGIE_BIN`     — path to the `auggie` CLI (default: `auggie`)
/// - `AGENT_BRIDGE_HEADLESS=1`     — headless Chromium
async fn build_hub() -> Result<Hub> {
    #[cfg(target_os = "linux")]
    let notifier: Arc<dyn ab_notifier::Notifier> = {
        use ab_notifier::DbusNotifier;
        Arc::new(DbusNotifier::connect().await?)
    };
    #[cfg(target_os = "macos")]
    let notifier: Arc<dyn ab_notifier::Notifier> = {
        use ab_notifier::MacOsNotifier;
        Arc::new(MacOsNotifier)
    };
    #[cfg(not(any(target_os = "linux", target_os = "macos")))]
    compile_error!("agent-bridge requires Linux or macOS");

    let db_path = std::env::var("AGENT_BRIDGE_DB")
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    tracing::info!(path = %db_path.display(), "SQLite store");
    let store: Arc<dyn StateStore> = Arc::new(SqliteStore::open(&db_path).await?);
    let terminal: Arc<dyn TerminalBackend> = auto_backend();
    tracing::info!(terminal_backend = %terminal.id(), "terminal backend selected");
    let browser: Arc<dyn BrowserBackend> = Arc::new(ChromiumCdpBackend::new());

    // Agent runtime selection.
    //
    // `AGENT_BRIDGE_AGENT_RUNTIME` ∈ {`claude-code` (default), `warp-oz`}.
    // Default preserves backwards compatibility for existing
    // Claude Code installs; `warp-oz` is the Warp-native cloud-agent
    // runtime, available when the `oz` CLI is installed and signed in.
    let agent: Arc<dyn AgentRuntime> = match std::env::var("AGENT_BRIDGE_AGENT_RUNTIME")
        .ok()
        .as_deref()
    {
        Some("warp-oz") | Some("oz") => {
            let bin = std::env::var("AGENT_BRIDGE_OZ_BIN").unwrap_or_else(|_| "oz".into());
            tracing::info!(runtime = "warp-oz", binary = %bin, "agent runtime selected");
            Arc::new(OzAgentRuntime::with_binary(bin).with_store(store.clone()))
        }
        Some("auggie") | Some("augment") => {
            let bin = std::env::var("AGENT_BRIDGE_AUGGIE_BIN").unwrap_or_else(|_| "auggie".into());
            tracing::info!(runtime = "auggie", binary = %bin, "agent runtime selected");
            Arc::new(AuggieRuntime::with_binary(bin).with_store(store.clone()))
        }
        _ => {
            let bin = std::env::var("AGENT_BRIDGE_CLAUDE_BIN").unwrap_or_else(|_| "claude".into());
            tracing::info!(runtime = "claude-code", binary = %bin, "agent runtime selected");
            Arc::new(ClaudeCodeRuntime::with_binary(bin).with_store(store.clone()))
        }
    };

    let repo = std::env::var("AGENT_BRIDGE_REPO")
        .ok()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| ".".into()));
    let worktree = Arc::new(GitWorktreeManager::new(repo));

    // Always register the auxiliary CLI agent runtimes so `agent_spawn` can
    // fan out to them when the caller passes `backend: "opencode" | "kilo"
    // | "gemini" | "codex"`. The `binary` on each is just the CLI name; if
    // it's not on PATH, spawn() returns a clear error at call time rather
    // than failing daemon startup.
    let opencode: Arc<dyn AgentRuntime> =
        Arc::new(OpenCodeFamilyRuntime::opencode().with_store(store.clone()));
    let kilo: Arc<dyn AgentRuntime> =
        Arc::new(OpenCodeFamilyRuntime::kilo().with_store(store.clone()));
    let gemini: Arc<dyn AgentRuntime> = Arc::new(GeminiRuntime::new().with_store(store.clone()));
    let codex: Arc<dyn AgentRuntime> = Arc::new(CodexRuntime::new().with_store(store.clone()));

    Ok(Hub::builder()
        .notifier(notifier)
        .store(store)
        .terminal(terminal)
        .browser(browser)
        .agent(agent)
        .register_agent(opencode)
        .register_agent(kilo)
        .register_agent(gemini)
        .register_agent(codex)
        .worktree(worktree)
        .build())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn settings_with_memory_hook_is_wired() {
        let body = r#"{"hooks":{"UserPromptSubmit":[{"hooks":[{"command":"/Users/x/.local/bin/ab-memory-hook"}]}]}}"#;
        assert!(settings_references_ab_hook(body));
    }

    #[test]
    fn settings_with_precompact_hook_is_wired() {
        let body = r#"{"hooks":{"PreCompact":[{"hooks":[{"command":"~/.local/bin/ab-precompact-hook"}]}]}}"#;
        assert!(settings_references_ab_hook(body));
    }

    #[test]
    fn settings_with_session_end_hook_is_wired() {
        let body = r#"{"hooks":{"Stop":[{"hooks":[{"command":"/x/ab-session-end-hook"}]}]}}"#;
        assert!(settings_references_ab_hook(body));
    }

    #[test]
    fn unrelated_hook_command_is_not_wired() {
        // User has hooks but none point at agent-bridge.
        let body = r#"{"hooks":{"Stop":[{"hooks":[{"command":"/usr/bin/notify-send"}]}]}}"#;
        assert!(!settings_references_ab_hook(body));
    }

    #[test]
    fn empty_settings_is_not_wired() {
        assert!(!settings_references_ab_hook("{}"));
        assert!(!settings_references_ab_hook(""));
    }

    // ── shell-init snippet sanity ─────────────────────────────────────────

    #[test]
    fn shell_init_snippet_covers_all_four_osc133_letters() {
        // Each emitted snippet must wire up A/B/C/D markers — a missing
        // letter would give silently-broken read_blocks output (e.g. no
        // exit code if D is absent).
        for shell in [ShellKind::Bash, ShellKind::Zsh, ShellKind::Fish] {
            let s = shell_init_snippet(shell);
            for letter in ["133;A", "133;B", "133;C", "133;D"] {
                assert!(
                    s.contains(letter),
                    "{shell:?} snippet missing OSC marker {letter}"
                );
            }
        }
    }

    #[test]
    fn shell_init_snippet_references_the_doc() {
        // The user's first instinct on seeing the snippet should be
        // "where do I read more?" — make sure the doc path is right
        // there in the comment.
        for shell in [ShellKind::Bash, ShellKind::Zsh, ShellKind::Fish] {
            let s = shell_init_snippet(shell);
            assert!(
                s.contains("docs/SHELL-INTEGRATION-OSC133.md"),
                "{shell:?} snippet missing doc reference"
            );
        }
    }
}
