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
        /// Promotion tier. Default 1 = strong-tier `cofires` edges (the
        /// classic dream-promote behavior). Set to 2 for **secondary
        /// promotion**: scans recurring-but-weak pairs (default
        /// `min_count=3`) that have NO existing edge of any type
        /// between them, and crystallises them as `co_referenced`
        /// edges with lower weight (0.3–0.5). This salvages the
        /// middle-tier signal that tier-1 cofires misses — the
        /// research_coactivation_data_audit_20260512 memory observed
        /// 43 such pairs in the live store. `cofires` is for "they
        /// fired together a lot"; `co_referenced` is for "they fired
        /// together more than once and we've never noticed in the
        /// graph."
        #[arg(long, default_value_t = 1, value_parser = clap::value_parser!(u8).range(1..=2))]
        tier: u8,
        /// Edge type to write in tier-2 mode. Default `co_referenced`
        /// keeps the provenance traceable to coactivation data rather
        /// than colliding with hand-authored `relates`.
        #[arg(long, default_value = "co_referenced")]
        tier2_edge: String,
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
    /// **Hebbian wire-strengthen** — Positive-reinforcement mirror of
    /// `decay-unused`. Bumps `importance` by `--step` (capped at
    /// `--ceiling`) for every active memory that was accessed ≥
    /// `--min-access` times AND last touched within `--window-days`.
    ///
    /// Without this op the system was entropy-monotonic — `decay-unused`,
    /// `decay-importance`, and `compact` only LOWERED importance. Repeat
    /// use produced no signal in retrieval rank. This op rewards
    /// "neurons that fire often" so frequently-touched memories aren't
    /// crushed to the floor by background decay.
    ///
    /// Pairs with the daily cron service (3rd ExecStart=- alongside
    /// `decay-unused` and `prune-coactivation-noise`).
    ReinforceActive {
        /// Only reinforce rows whose `last_accessed_at` is within this
        /// many days. Default 7. (Decay's mirror is 30; reinforce is
        /// narrower because we want a stronger signal of recency.)
        #[arg(long, default_value_t = 7.0)]
        window_days: f64,
        /// Minimum `access_count` to qualify. Default 5. Below this the
        /// memory is too rarely touched to call "repeatedly used."
        #[arg(long, default_value_t = 5)]
        min_access: u64,
        /// How much to add to `importance` per pass. Default 0.05.
        #[arg(long, default_value_t = 0.05)]
        step: f64,
        /// Importance never grows above this ceiling. Default 0.95
        /// (leaves manual headroom for an explicit `importance = 1.0`).
        #[arg(long, default_value_t = 0.95)]
        ceiling: f64,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **Hebbian closure observability** — Spearman rank correlation
    /// between `importance` and `access_count` over active memories.
    /// Answers "does importance actually predict access?" — i.e. is
    /// the post-Hebbian-loop ranking signal real or noise?
    ///
    /// Baseline question: pre-`reinforce-active` (commit `586cbb1`)
    /// expectation is `r ≈ 0` because decay had flattened importance
    /// to the floor. Post-cron-cycles, `r` should drift toward 0.4+.
    /// Re-run weekly; longitudinal trend is the actual measurement.
    ///
    /// Also surfaces the worst misranks for inspection: under-reinforced
    /// rows (high access, low importance) and over-promoted rows
    /// (high importance, low access).
    SignalFidelity {
        /// Top-N misranks to surface on each side. Capped at 50.
        /// Default 5.
        #[arg(long, default_value_t = 5)]
        top_n: u32,
        /// Emit raw JSON instead of pretty text.
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
    /// **ζ-12 (graph hygiene)** — Drop `relates` edges where BOTH endpoints
    /// carry any tag in `--blacklist-tags`. CLI mirror of the
    /// `memory_prune_degenerate_relates` MCP tool. Sibling daily-hygiene
    /// op to `dream decay-unused` / `prune-coactivation-noise`. Only the
    /// softest edge type (`relates`) is in scope — causal/structural
    /// edges are preserved.
    PruneDegenerateRelates {
        /// Edges where both endpoints carry any of these tags are
        /// pruned. Comma-separated. Default `auto_curated`.
        #[arg(long, default_value = "auto_curated", value_delimiter = ',')]
        blacklist_tags: Vec<String>,
        /// Preview only.
        #[arg(long)]
        dry_run: bool,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **ζ-14 (graph hygiene)** — Flip orphan stubs carrying a blacklist
    /// tag from `status='active'` to `status='archived'`. Criterion (all
    /// four required): status=active, tags overlap blacklist, zero edges,
    /// created_at ≤ now-`--older-than-days`*86400. CLI mirror of the
    /// `memory_archive_orphan_stubs` MCP tool. Closes the ζ-9→ζ-12
    /// hygiene loop: ζ-11 stops new degenerate links, ζ-12 deletes the
    /// legacy ones, ζ-14 retires the resulting orphan stubs instead of
    /// waiting for passive decay.
    ArchiveOrphanStubs {
        /// Stubs whose tags overlap this list are eligible. Default
        /// `auto_curated`.
        #[arg(long, default_value = "auto_curated", value_delimiter = ',')]
        blacklist_tags: Vec<String>,
        /// Only stubs whose `created_at` is at least this many days old.
        /// Default 3 — gives a session window to revisit recent stubs.
        #[arg(long, default_value_t = 3)]
        older_than_days: i64,
        /// Hard cap on archives per run. Default 200, clamp [1, 1000].
        #[arg(long, default_value_t = 200)]
        max_archive: i64,
        /// **ζ-15** — when archived count ≥ this threshold (and run is not
        /// dry), write a `kind=alert` memory and shout on stderr so the
        /// ζ-10 daily cron's journal captures the burst. Steady-state is
        /// 0-3/day; 10 is a sane "look at this" floor. Set 0 to disable.
        #[arg(long, default_value_t = 10)]
        alarm_threshold: i64,
        /// Preview only.
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
        /// Window (minutes) for the waypoint pass — classifies each
        /// summary as gateway/trailing/ambiguous/isolated based on
        /// whether its `get` events lead or trail its sources' within
        /// this window. Default 30. Pass 0 to skip the waypoint pass.
        #[arg(long, default_value_t = 30)]
        waypoint_min: u32,
        /// Jaccard threshold for the source-set overlap pass. Two
        /// active replay summaries whose `summarizes`-edge source sets
        /// overlap at this similarity or higher are surfaced as
        /// duplicate-candidate pairs (pre-Phase-2-#2 keys that escaped
        /// canonical-key dedupe). Range (0, 1]. Default 0.5. Pass 0 to
        /// skip the overlap pass entirely.
        #[arg(long, default_value_t = 0.5)]
        overlap_min: f64,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **ζ-1 (2026-05-11)** — Mid-grain self-portrait. Captures memory
    /// stats + coactivation temporal-spread + top access + identity window
    /// + δ-4 transitions into a structured JSON payload and (by default)
    /// saves it as a `kind=snapshot` memory. Designed as the time-series
    /// foundation for a future `dream diff` command — vision §5 身份元监控
    /// at a 1-day grain (vs dream identity's 3-day window, AiOT Soul's
    /// 256-dim trait vector, and AGENT.md's timeless self-portrait).
    ///
    /// Cheap (read-only over current store), idempotent, suitable for
    /// daily cron.
    Snapshot {
        /// Optional slug for the memory key. Default: `anon`. Final key
        /// is `snapshot_<slug>_<YYYYMMDD_HHMM>` so multiple runs/day
        /// don't collide.
        #[arg(long)]
        name: Option<String>,
        /// Identity-window span (matches `dream identity --days N`).
        #[arg(long, default_value_t = 3)]
        days: u32,
        /// Print the snapshot to stdout but DON'T save as memory. Use to
        /// preview shape before kicking off a recurring cron.
        #[arg(long)]
        print_only: bool,
        /// Emit raw JSON to stdout instead of human-readable summary.
        /// Memory body is always JSON regardless.
        #[arg(long)]
        json: bool,
    },
    /// **ζ-3 (2026-05-11)** — Diff two `dream snapshot` memories. Reads
    /// both `kind=snapshot` rows, parses content as JSON (schema_version=1),
    /// detects which one is older, prints structured deltas for every
    /// section: memory counts, coactivation distribution, top persistent,
    /// top-10 access, identity tools/saves, transitions. Designed to make
    /// "what did I change about myself between these two timestamps"
    /// answerable in one command.
    ///
    /// Order-independent: caller can pass the two keys in any order; the
    /// command swaps them so the diff is always "older → newer".
    ///
    /// **ζ-16 (2026-05-12)** — `--auto` skips the key arguments and pulls
    /// the two most-recent `snapshot_daily_*` rows from the store. Pairs
    /// with the ζ-10 daily cron so a one-word `dream diff --auto` shows
    /// the last 24h hygiene net effect.
    Diff {
        /// First snapshot memory key. Required unless `--auto` is set.
        key_a: Option<String>,
        /// Second snapshot memory key. Required unless `--auto` is set.
        key_b: Option<String>,
        /// ζ-16 — fetch the two most-recent active `snapshot_daily_*`
        /// memories and diff them. Errors out if fewer than 2 exist yet.
        #[arg(long, conflicts_with_all = ["key_a", "key_b"])]
        auto: bool,
        /// Emit raw JSON deltas instead of pretty text. Useful for
        /// piping into other tools.
        #[arg(long)]
        json: bool,
    },
    /// **Monday-morning composite** — Bundles three read-only audits into
    /// one command: replay-audit (P5 summary quality + waypoint pass +
    /// orphan-overlap), signal-fidelity (Spearman importance↔access +
    /// misranks), and an optional snapshot capture. Designed for a weekly
    /// review pulse where you want the full state-of-the-memory in one
    /// scroll instead of three.
    ///
    /// All three component ops are pure SQL/Rust passes — no LLM, no
    /// writes (except the optional snapshot save). Vision §5 身份元监控
    /// surface for the human reviewer.
    Weekly {
        /// Skip the snapshot capture step (just print the audits).
        /// Default: capture a `kind=snapshot` memory tagged `weekly`.
        #[arg(long)]
        no_snapshot: bool,
        /// Emit raw JSON containing all three structured results.
        /// Pretty text is the default — easier to skim.
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
                        1,
                        "co_referenced",
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
                tier,
                tier2_edge,
            } => {
                // Tier 2 gets a softer default: count >= 3 (vs 5) since
                // the whole point is to catch the mid-tier that tier 1
                // misses. User can still override via --min-count.
                let effective_min = if *tier == 2 && *min_count == 5 {
                    3
                } else {
                    *min_count
                };
                run_dream_promote(
                    effective_min,
                    *limit,
                    *dry_run,
                    html.as_deref(),
                    *tier,
                    tier2_edge.as_str(),
                )
                .await
            }
            DreamOp::DecayUnused {
                window_days,
                step,
                floor,
                json,
            } => run_dream_decay_unused(*window_days, *step, *floor, *json).await,
            DreamOp::ReinforceActive {
                window_days,
                min_access,
                step,
                ceiling,
                json,
            } => {
                run_dream_reinforce_active(
                    *window_days,
                    *min_access,
                    *step,
                    *ceiling,
                    *json,
                )
                .await
            }
            DreamOp::SignalFidelity { top_n, json } => {
                run_dream_signal_fidelity(*top_n, *json).await
            }
            DreamOp::PruneCoactivationNoise {
                max_count,
                older_than_days,
                dry_run,
                json,
            } => run_dream_prune_coact_noise(*max_count, *older_than_days, *dry_run, *json).await,
            DreamOp::PruneDegenerateRelates {
                blacklist_tags,
                dry_run,
                json,
            } => run_dream_prune_degenerate_relates(blacklist_tags, *dry_run, *json).await,
            DreamOp::ArchiveOrphanStubs {
                blacklist_tags,
                older_than_days,
                max_archive,
                alarm_threshold,
                dry_run,
                json,
            } => {
                run_dream_archive_orphan_stubs(
                    blacklist_tags,
                    *older_than_days,
                    *max_archive,
                    *alarm_threshold,
                    *dry_run,
                    *json,
                )
                .await
            }
            DreamOp::ReplayAudit {
                stale_days,
                waypoint_min,
                overlap_min,
                json,
            } => {
                run_dream_replay_audit(*stale_days, *waypoint_min, *overlap_min, *json).await
            }
            DreamOp::Snapshot {
                name,
                days,
                print_only,
                json,
            } => run_dream_snapshot(name.as_deref(), *days, *print_only, *json).await,
            DreamOp::Diff { key_a, key_b, auto, json } => {
                run_dream_diff(key_a.as_deref(), key_b.as_deref(), *auto, *json).await
            }
            DreamOp::Weekly { no_snapshot, json } => {
                run_dream_weekly(*no_snapshot, *json).await
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
    tier: u8,
    tier2_edge: &str,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};
    use std::collections::HashSet;

    // Tier semantics:
    //   1 = classic dream-promote, writes `cofires`, skips pairs that
    //       already have a `cofires` edge (other edge types stack on top).
    //   2 = secondary promotion, writes `<tier2_edge>` (default
    //       `co_referenced`), skips pairs that have ANY existing edge of
    //       any type. Targets the middle-tier signal (count≥3) that
    //       lives in coact but never gets captured in the graph.
    let primary_edge_type = if tier == 2 { tier2_edge } else { "cofires" };

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

    // Build the existing-edge set by querying memory_neighbors for every
    // key referenced in the candidate pairs. Single pass per key (cached).
    //
    // Tier 1 only tracks `cofires` edges (matches the ε-1 rule from
    // 2026-05-11: cofires stacks alongside other edge types).
    // Tier 2 tracks ALL edge types — the secondary promote is for pairs
    // that have nothing yet; we don't want to pollute pairs that the
    // human (or another auto-engine) already linked.
    let mut existing: HashSet<(String, String)> = HashSet::new();
    let mut probed: HashSet<String> = HashSet::new();
    for c in &pairs {
        for k in [&c.key_a, &c.key_b] {
            if !probed.insert(k.clone()) {
                continue;
            }
            let nbrs = store.memory_neighbors(k).await.unwrap_or_default();
            for e in nbrs {
                if tier == 1 && e.edge_type != "cofires" {
                    continue;
                }
                // Tier 2 falls through and counts every edge.
                let p = if e.from_key < e.to_key {
                    (e.from_key, e.to_key)
                } else {
                    (e.to_key, e.from_key)
                };
                existing.insert(p);
            }
        }
    }

    println!(
        "# Hebbian promote (tier {}) — coact ≥ {min_count} → `{}` edge",
        tier, primary_edge_type
    );
    println!("DB: {}", path.display());
    println!("candidates: {} pair(s)", pairs.len());
    if tier == 2 {
        println!("tier-2 mode: skip if any existing edge between pair");
    }
    println!();

    let mut decisions: Vec<PromoteDecision> = Vec::with_capacity(pairs.len());
    for c in &pairs {
        let pair = if c.key_a < c.key_b {
            (c.key_a.clone(), c.key_b.clone())
        } else {
            (c.key_b.clone(), c.key_a.clone())
        };
        // Map count → weight. Tier 1: [0.5, 0.95]. Tier 2: [0.3, 0.5]
        // — weaker because the signal is weaker (count=3-8 typically)
        // and we don't want secondary `co_referenced` edges crowding out
        // hand-authored / strong cofires in graph weight comparisons.
        let weight = if tier == 2 {
            ((c.count as f64) / 20.0).clamp(0.3, 0.5)
        } else {
            ((c.count as f64) / 10.0).clamp(0.5, 0.95)
        };

        if existing.contains(&pair) {
            if dry_run {
                let reason = if tier == 2 { "edge already exists" } else { "cofires already exists" };
                println!(
                    "  SKIP    ({:>2} fires)  {}  ↔  {}    [{reason}]",
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
                .memory_link(&pair.0, &pair.1, primary_edge_type, weight)
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
        let skip_reason = if tier == 2 { "edge already exists" } else { "cofires already exists" };
        println!(
            "✓ promoted {promoted} pairs as `{primary_edge_type}`, skipped {skipped} ({skip_reason})"
        );
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

/// Hebbian wire-strengthen — positive-reinforcement mirror of
/// `run_dream_decay_unused`. Bumps `importance` by `step` (capped at
/// `ceiling`) for every active row with `access_count >= min_access`
/// and `last_accessed_at` within `window_days`.
///
/// Composes with the daily cron service as a 3rd ExecStart=- alongside
/// `decay-unused` and `prune-coactivation-noise`. Without this op the
/// system was entropy-monotonic; this is the wire-strengthen that
/// closes the Hebbian loop at the single-node level.
async fn run_dream_reinforce_active(
    window_days: f64,
    min_access: u64,
    step: f64,
    ceiling: f64,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};

    let window_days = window_days.max(0.0);
    let step = step.clamp(0.0, 1.0);
    let ceiling = ceiling.clamp(0.0, 1.0);
    let window_secs = (window_days * 86_400.0) as i64;

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let stats = store
        .memory_reinforce_active(window_secs, min_access, step, ceiling)
        .await
        .map_err(|e| anyhow::anyhow!("memory_reinforce_active: {e}"))?;

    if as_json {
        let payload = json!({
            "window_days": window_days,
            "min_access": min_access,
            "step": step,
            "ceiling": ceiling,
            "candidates": stats.candidates,
            "reinforced": stats.reinforced,
            "skipped_at_ceiling": stats.skipped_at_ceiling,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# Hebbian wire-strengthen — read-recency reinforcement");
    println!("DB: {}", path.display());
    println!(
        "window: <{window_days:.1}d accessed · ≥{min_access} hits · step: {step:.3} · ceiling: {ceiling:.3}"
    );
    println!();
    println!("candidates         : {}", stats.candidates);
    println!("reinforced         : {}", stats.reinforced);
    println!("skipped at ceiling : {}", stats.skipped_at_ceiling);
    if stats.candidates == 0 {
        println!();
        println!(
            "(no memory met access≥{min_access} AND recency<{window_days:.0}d — try a smaller --min-access)"
        );
    } else if stats.reinforced == 0 {
        println!();
        println!("(every candidate already at/above ceiling — nothing to lift)");
    }
    Ok(())
}

/// Hebbian-closure observability — Spearman rank correlation of
/// `importance` vs `access_count` across active memories, plus the
/// top-N misranks on each side. Pure read, no writes.
///
/// Baseline reading taken pre-reinforce-active-cron is the anchor for a
/// longitudinal study: re-run weekly, compare. If the closure works,
/// `spearman_r` should drift from ≈ 0 (decay-flattened) toward 0.4+.
async fn run_dream_signal_fidelity(top_n: u32, as_json: bool) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let stats = store
        .signal_fidelity_stats(top_n)
        .await
        .map_err(|e| anyhow::anyhow!("signal_fidelity_stats: {e}"))?;

    if as_json {
        println!("{}", serde_json::to_string_pretty(&stats)?);
        return Ok(());
    }

    println!("# Hebbian-closure observability — importance vs access");
    println!("DB: {}", path.display());
    println!();
    println!("total active           : {}", stats.total_active);
    println!(
        "  zero-access          : {}    ({:.0}% — bootstrap / never-read)",
        stats.n_zero_access,
        if stats.total_active > 0 {
            100.0 * stats.n_zero_access as f64 / stats.total_active as f64
        } else {
            0.0
        }
    );
    println!(
        "  at importance floor  : {}    ({:.0}% — decay-flattened)",
        stats.n_floor_importance,
        if stats.total_active > 0 {
            100.0 * stats.n_floor_importance as f64 / stats.total_active as f64
        } else {
            0.0
        }
    );
    println!();
    println!(
        "mean importance        : {:.3}    mean access : {:.2}",
        stats.mean_importance, stats.mean_access
    );
    println!();
    let spearman_label = |r: f64| -> &'static str {
        if r.is_nan() {
            "(undefined)"
        } else if r.abs() < 0.1 {
            "noise"
        } else if r.abs() < 0.3 {
            "weak"
        } else if r.abs() < 0.5 {
            "moderate"
        } else if r.abs() < 0.7 {
            "strong"
        } else {
            "very strong"
        }
    };
    println!(
        "spearman r (all)       : {:>+.3}  [{}]",
        stats.spearman_r,
        spearman_label(stats.spearman_r),
    );
    println!(
        "spearman r (touched)   : {:>+.3}  [{}]  (n={})",
        stats.spearman_r_touched,
        spearman_label(stats.spearman_r_touched),
        stats.n_touched,
    );

    if !stats.under_reinforced.is_empty() {
        println!();
        println!("under-reinforced — high access, low importance (reinforce target):");
        for r in &stats.under_reinforced {
            println!(
                "  Δ{:>+6.1}  imp={:.2}  acc={:>3}  · {}",
                r.rank_diff,
                r.importance,
                r.access_count,
                short_key(&r.key, 52),
            );
        }
    }
    if !stats.over_promoted.is_empty() {
        println!();
        println!("over-promoted — high importance, low access (decay/review target):");
        for r in &stats.over_promoted {
            println!(
                "  Δ{:>+6.1}  imp={:.2}  acc={:>3}  · {}",
                r.rank_diff,
                r.importance,
                r.access_count,
                short_key(&r.key, 52),
            );
        }
    }

    if stats.total_active >= 10 {
        println!();
        if stats.spearman_r.is_nan() {
            println!(
                "verdict: signal undefined — too few rows or zero variance."
            );
        } else if stats.spearman_r.abs() < 0.1 {
            println!(
                "verdict: importance is noise — ranking does NOT predict access. \
                Hebbian closure (reinforce-active) has not yet produced informative ranks."
            );
        } else if stats.spearman_r < 0.3 {
            println!(
                "verdict: weak signal — closure is starting to bite, give it more cron cycles."
            );
        } else {
            println!(
                "verdict: importance is a real prior (r={:.2}) — Hebbian closure working.",
                stats.spearman_r
            );
        }
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

/// **ζ-12** — Drop `relates` edges where both endpoints carry a tag in
/// the blacklist. CLI mirror of the `memory_prune_degenerate_relates`
/// MCP tool. Idempotent — re-running after a successful prune is a no-op.
async fn run_dream_prune_degenerate_relates(
    blacklist_tags: &[String],
    dry_run: bool,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};
    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let pruned = store
        .memory_prune_degenerate_relates(blacklist_tags, dry_run)
        .await
        .map_err(|e| anyhow::anyhow!("memory_prune_degenerate_relates: {e}"))?;

    if as_json {
        let payload = json!({
            "dry_run": dry_run,
            "blacklist_tags": blacklist_tags,
            "pruned_count": pruned,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# ζ-12 — degenerate relates prune");
    println!("DB: {}", path.display());
    println!(
        "blacklist_tags: {:?} · dry_run: {dry_run}",
        blacklist_tags
    );
    println!();
    let label = if dry_run { "would prune" } else { "pruned" };
    println!("{label:16} : {pruned}");
    if pruned == 0 {
        println!();
        println!(
            "(no degenerate relates edges found — pre-ζ-11 noise hubs already cleaned)"
        );
    }
    Ok(())
}

/// **ζ-14** — Flip orphan stubs to `status='archived'`. CLI mirror of the
/// `memory_archive_orphan_stubs` MCP tool. Closes the ζ-9→ζ-12 hygiene
/// loop by actively retiring stubs that ζ-11's blacklist would block from
/// ever re-linking. Pairs with `dream prune-degenerate-relates`.
async fn run_dream_archive_orphan_stubs(
    blacklist_tags: &[String],
    older_than_days: i64,
    max_archive: i64,
    alarm_threshold: i64,
    dry_run: bool,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, MemoryRecord, SqliteStore, StateStore};
    use std::time::{SystemTime, UNIX_EPOCH};
    let older_than_days = older_than_days.max(0);
    let max_archive = max_archive.clamp(1, 1000);

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let archived = store
        .memory_archive_orphan_stubs(blacklist_tags, older_than_days, max_archive, dry_run)
        .await
        .map_err(|e| anyhow::anyhow!("memory_archive_orphan_stubs: {e}"))?;

    // ζ-15 — burst alarm. Runs *before* normal output so the alert key
    // can be echoed alongside the count. Pure-decision helper keeps the
    // condition unit-testable.
    let alarm_key = if archive_alarm_should_fire(archived, alarm_threshold, dry_run) {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);
        let key = format!("alert_archive_burst_{}", time_slug(now));
        let body = format!(
            "# ζ-15 archive burst alert\n\n\
             - archived: {archived}\n\
             - alarm_threshold: {alarm_threshold}\n\
             - blacklist_tags: {blacklist_tags:?}\n\
             - older_than_days: {older_than_days}\n\
             - max_archive: {max_archive}\n\
             - at: {ts}\n\n\
             Steady-state daily archive count is 0–3 after the initial \
             ζ-14 sweep. A burst this size suggests one of:\n\
             1. blacklist tag was widened (re-run with `--dry-run` to inspect)\n\
             2. an automated process injected many `auto_curated` stubs\n\
             3. one-off cleanup of a previously-deferred cohort\n\n\
             If neither (1) nor (2) applies, this alarm can be ignored — the \
             post-archive snapshot (via ζ-10 cron) will record the new \
             steady-state, and `dream diff --auto` tomorrow will show \
             `orphan -N` as the net effect.\n",
            ts = chrono_like_date(now),
        );
        let rec = MemoryRecord {
            key: key.clone(),
            kind: "alert".into(),
            content: body,
            tags: vec![
                "alert".into(),
                "zeta-15".into(),
                "archive-burst".into(),
            ],
            related_keys: vec![],
            scope: None,
            created_at: now,
            updated_at: now,
            last_accessed_at: 0,
            access_count: 0,
            // Mid-high importance — not as critical as a true incident
            // (this is "look at this", not "act now") but should sit
            // above ambient noise so default FTS surfaces it.
            importance: 0.6,
            status: String::new(),
            trigger_pattern: None,
            superseded_by: None,
        };
        store
            .memory_save(&rec)
            .await
            .map_err(|e| anyhow::anyhow!("memory_save alert: {e}"))?;
        eprintln!(
            "⚠ ζ-15 alarm: archived {archived} orphan stubs (threshold {alarm_threshold}) — saved as memory {key}"
        );
        Some(key)
    } else {
        None
    };

    if as_json {
        let payload = json!({
            "dry_run": dry_run,
            "blacklist_tags": blacklist_tags,
            "older_than_days": older_than_days,
            "max_archive": max_archive,
            "alarm_threshold": alarm_threshold,
            "archived_count": archived,
            "alert_key": alarm_key,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# ζ-14 — archive orphan stubs");
    println!("DB: {}", path.display());
    println!(
        "blacklist_tags: {:?} · older_than: {older_than_days}d · max_archive: {max_archive} · alarm_threshold: {alarm_threshold} · dry_run: {dry_run}",
        blacklist_tags
    );
    println!();
    let label = if dry_run { "would archive" } else { "archived" };
    println!("{label:16} : {archived}");
    if archived == 0 {
        println!();
        println!(
            "(no eligible orphan stubs — lower --older-than-days or check `memory_list status=active tag=auto_curated`)"
        );
    }
    if let Some(k) = &alarm_key {
        println!();
        println!("⚠ alarm fired (≥{alarm_threshold}) — alert memory: {k}");
    }
    Ok(())
}

/// ζ-15 — pure decision: should the archive-burst alarm fire?
///
/// - `dry_run=true` always returns false (no real archives happened).
/// - `threshold <= 0` disables the alarm (operator opt-out).
/// - Otherwise compare archived count against threshold.
fn archive_alarm_should_fire(archived: u64, threshold: i64, dry_run: bool) -> bool {
    if dry_run || threshold <= 0 {
        return false;
    }
    (archived as i64) >= threshold
}

/// **Replay quality audit** — pure read pass, no writes, no LLM.
/// Counts `p5_replay`-tagged active memories, bins access patterns
/// (never / once / multi), flags `access_count = 0` + aged rows as
/// stale dead weight, and surfaces the top wins + oldest unused for
/// manual inspection. Pairs with `dream replay` to answer "are the
/// LLM-consolidated summaries actually being used?"
async fn run_dream_replay_audit(
    stale_days: u32,
    waypoint_min: u32,
    overlap_min: f64,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let waypoint_window_secs = (waypoint_min as i64).saturating_mul(60);
    let stats = store
        .replay_audit_stats(stale_days, waypoint_window_secs, overlap_min)
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

    // Waypoint section — pairs `get(summary)` against `get(source)`
    // within a session window to classify summaries as gateway / trailing
    // / ambiguous / isolated. Different question than access count alone:
    // *what role* does the summary play in attention flow?
    if let Some(wp) = &stats.waypoint {
        println!();
        println!(
            "# waypoint pass (±{} min window)",
            wp.window_secs / 60
        );
        println!("  gateway (lead→source) : {}", wp.gateway_summaries);
        println!("  trailing (source→lead): {}", wp.trailing_summaries);
        println!("  ambiguous (==)        : {}", wp.ambiguous_summaries);
        println!(
            "  isolated (no source-get in window): {}",
            wp.isolated_summaries
        );
        if !wp.rows.is_empty() {
            println!();
            println!("per-summary detail (lead/trail/total):");
            for r in &wp.rows {
                println!(
                    "  [{}] {}/{} of {}  · {}",
                    r.classification.chars().next().unwrap_or('?'),
                    r.leading_pairs,
                    r.trailing_pairs,
                    r.pairs_total,
                    short_key(&r.key, 52)
                );
            }
        }
    }

    // Overlap pairs — pre-Phase-2-#2 orphan duplicates that escaped
    // canonical-key dedupe. Strong tell when two pairs share most
    // sources but land on opposite waypoint sides: role is access-order
    // driven, not cluster-shape driven.
    if !stats.overlap_pairs.is_empty() {
        println!();
        println!("# source-set overlap (orphan-duplicate candidates)");
        for op in &stats.overlap_pairs {
            let cls_a = op.classification_a.as_deref().unwrap_or("?");
            let cls_b = op.classification_b.as_deref().unwrap_or("?");
            println!(
                "  J={:.2}  {} shared / {} ∪ {}  · [{}] {}",
                op.jaccard,
                op.shared_sources,
                op.size_a,
                op.size_b,
                cls_a,
                short_key(&op.key_a, 52)
            );
            println!(
                "                          ↕         · [{}] {}",
                cls_b,
                short_key(&op.key_b, 52)
            );
        }
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
        } else if let Some(wp) = &stats.waypoint {
            if wp.gateway_summaries > 0 && wp.gateway_summaries >= wp.trailing_summaries {
                println!(
                    "verdict: summaries act as attention gateways for ≥{} clusters — replay is creating real entrypoints.",
                    wp.gateway_summaries
                );
            } else if wp.trailing_summaries > wp.gateway_summaries {
                println!(
                    "verdict: summaries trail their sources — they read more like decoration than entrypoints."
                );
            } else {
                println!(
                    "verdict: mixed signal — let it bake a few more days before judging."
                );
            }
        } else {
            println!(
                "verdict: mixed signal — let it bake a few more days before judging."
            );
        }
    }

    Ok(())
}

/// ζ-1 (2026-05-11) — Self-portrait snapshot. Captures a mid-grain
/// behavioural fingerprint by composing existing read-only store methods,
/// renders as JSON, optionally saves to a `kind=snapshot` memory.
///
/// Designed as the *artifact* future `dream diff` will read: each row in
/// the snapshot timeline is a frozen self-portrait readable cross-session.
/// This is the 1-day grain in the identity-monitor stack:
///   • AGENT.md           — timeless (markdown, drift-capped)
///   • AiOT Soul          — 256-dim trait vector, EMA over 18 sessions
///   • dream identity     — 3-day rolling window comparison
///   • dream snapshot ←   — 1-day frozen point (this)
///   • last_accessed_at   — per-row real-time
async fn run_dream_snapshot(
    name: Option<&str>,
    days: u32,
    print_only: bool,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, MemoryRecord, SqliteStore, StateStore};
    use std::time::{SystemTime, UNIX_EPOCH};

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;

    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);

    // ── memory stats ─────────────────────────────────────────────────────
    let mstats = store
        .memory_stats()
        .await
        .map_err(|e| anyhow::anyhow!("memory_stats: {e}"))?;

    // ── coactivation stats (ε-2 already exposes burst vs persistent) ─────
    let cstats = store
        .coactivation_stats()
        .await
        .map_err(|e| anyhow::anyhow!("coactivation_stats: {e}"))?;

    // ── graph topology (ζ-9) — orphan rate + degree + hubs + P4 coverage ─
    let topo = store
        .graph_topology()
        .await
        .map_err(|e| anyhow::anyhow!("graph_topology: {e}"))?;

    // ── top-10 most-accessed non-skill memories (current attention) ──────
    let top_access: Vec<(String, u64)> = {
        let rows = store
            .list_memories_in_scope(
                "",
                None,
                ab_store::MemoryListSort::Frequent,
                200,
            )
            .await
            .map_err(|e| anyhow::anyhow!("list_memories: {e}"))?;
        rows.into_iter()
            .filter(|r| r.kind != "skill")
            .take(10)
            .map(|r| (r.key, r.access_count))
            .collect()
    };

    // ── identity window cur vs prior ─────────────────────────────────────
    let window_secs = days as i64 * 86_400;
    let cur_start = now - window_secs;
    let prior_start = cur_start - window_secs;
    let id_cur = store
        .identity_window(cur_start, now)
        .await
        .map_err(|e| anyhow::anyhow!("identity_window cur: {e}"))?;
    let id_prior = store
        .identity_window(prior_start, cur_start)
        .await
        .map_err(|e| anyhow::anyhow!("identity_window prior: {e}"))?;

    // ── δ-4 transitions (top repeated A→B with span ≤ 10min) ─────────────
    let transitions: Vec<(String, String, u32)> = {
        let mut events = store
            .recent_memory_get_keys(200)
            .await
            .unwrap_or_default();
        events.reverse();
        let mut counts: std::collections::HashMap<(String, String), u32> =
            std::collections::HashMap::new();
        for win in events.windows(2) {
            let (a_key, a_at) = &win[0];
            let (b_key, b_at) = &win[1];
            if a_key == b_key {
                continue;
            }
            if b_at - a_at > 600 {
                continue;
            }
            *counts
                .entry((a_key.clone(), b_key.clone()))
                .or_insert(0) += 1;
        }
        let mut ranked: Vec<((String, String), u32)> =
            counts.into_iter().filter(|(_, c)| *c >= 2).collect();
        ranked.sort_by(|a, b| b.1.cmp(&a.1));
        ranked
            .into_iter()
            .take(5)
            .map(|((a, b), n)| (a, b, n))
            .collect()
    };

    // ── node label (matches daemon-http /identity convention) ────────────
    let node = std::env::var("AGENT_BRIDGE_NODE")
        .ok()
        .or_else(|| {
            std::fs::read_to_string("/etc/hostname")
                .ok()
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
        })
        .unwrap_or_else(|| "unknown".to_string());

    // ── compose payload ──────────────────────────────────────────────────
    // Use serde_json::json! for the body so the JSON is order-preserving
    // and human-diffable. Schema v1.
    let by_kind_non_skill: Vec<serde_json::Value> = mstats
        .counts_by_kind
        .iter()
        .filter(|(k, _)| k != "skill")
        .map(|(k, n)| json!({ "kind": k, "count": n }))
        .collect();
    let coact_top_persistent: Vec<serde_json::Value> = cstats
        .top_5_persistent_edges
        .iter()
        .map(|e| {
            json!({
                "key_a": e.key_a,
                "key_b": e.key_b,
                "count": e.count,
                "span_hours": (e.last_at - e.first_at) / 3600,
            })
        })
        .collect();
    let active_total = mstats
        .counts_by_status
        .get("active")
        .copied()
        .unwrap_or(0);
    let archived_total = mstats
        .counts_by_status
        .get("archived")
        .copied()
        .unwrap_or(0);
    let payload = json!({
        "schema_version": 2,
        "captured_at": now,
        "node": node,
        "name": name.unwrap_or("anon"),
        "memory": {
            "active_total": active_total,
            "archived_total": archived_total,
            "edge_count": mstats.edge_count,
            "avg_importance_active": mstats.avg_importance_active,
            "by_kind_non_skill": by_kind_non_skill,
        },
        "coactivation": {
            "total_pairs": cstats.total_pairs,
            "pairs_burst_lt_1h": cstats.pairs_burst_lt_1h,
            "pairs_persistent_ge_6h": cstats.pairs_persistent_ge_6h,
            "top10_to_median_ratio": cstats.top10_to_median_ratio,
            "top_5_persistent": coact_top_persistent,
        },
        "access": {
            "top_10_keys": top_access.iter().map(|(k, n)| json!({ "key": k, "access_count": n })).collect::<Vec<_>>(),
        },
        "identity": {
            "days": days,
            "current": id_cur,
            "prior": id_prior,
        },
        "transitions": {
            "top_5": transitions.iter().map(|(a, b, n)| json!({ "from": a, "to": b, "count": n })).collect::<Vec<_>>(),
        },
        "topology": {
            "non_skill_active_total": topo.non_skill_active_total,
            "orphan_count": topo.orphan_count,
            "p4_evolved_coverage": topo.p4_evolved_coverage,
            "degree_histogram": topo.degree_histogram.iter().map(|(b,n)| json!({"bucket":b,"count":n})).collect::<Vec<_>>(),
            "top_5_hubs": topo.top_5_hubs.iter().map(|(k,d)| json!({"key":k,"degree":d})).collect::<Vec<_>>(),
        },
    });

    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
    } else {
        // Human summary — same fields, narrative layout. Goes to stdout
        // so it composes with shell pipelines.
        println!("# ζ-1 self-portrait snapshot ({} {})",
            chrono_like_date(now), node);
        println!();
        println!("memory       : {} active / {} archived / {} edges · avg imp {:.3}",
            active_total, archived_total,
            mstats.edge_count, mstats.avg_importance_active);
        let non_skill: Vec<String> = by_kind_non_skill
            .iter()
            .take(6)
            .filter_map(|v| {
                let k = v.get("kind")?.as_str()?;
                let n = v.get("count")?.as_u64()?;
                Some(format!("{k}:{n}"))
            })
            .collect();
        if !non_skill.is_empty() {
            println!("  non-skill  : {}", non_skill.join(", "));
        }
        let burst_pct = if cstats.total_pairs > 0 {
            100.0 * cstats.pairs_burst_lt_1h as f64 / cstats.total_pairs as f64
        } else {
            0.0
        };
        let persist_pct = if cstats.total_pairs > 0 {
            100.0 * cstats.pairs_persistent_ge_6h as f64 / cstats.total_pairs as f64
        } else {
            0.0
        };
        println!(
            "coactivation : {} pairs ({:.0}% burst <1h, {:.0}% persistent ≥6h)",
            cstats.total_pairs, burst_pct, persist_pct
        );
        if let Some(e) = cstats.top_5_persistent_edges.first() {
            let span = (e.last_at - e.first_at) / 3600;
            println!(
                "  top persistent (count={}, span={}h):",
                e.count, span
            );
            println!("    {} ↔ {}",
                short_key(&e.key_a, 40),
                short_key(&e.key_b, 40));
        }
        println!("attention    : top-3 most-accessed (non-skill)");
        for (key, n) in top_access.iter().take(3) {
            println!("  a={n:>3}  {}", short_key(key, 60));
        }
        let tools_ratio = if id_prior.tool_calls_total > 0 {
            id_cur.tool_calls_total as f64 / id_prior.tool_calls_total as f64
        } else {
            0.0
        };
        let saves_ratio = if id_prior.memory_saves > 0 {
            id_cur.memory_saves as f64 / id_prior.memory_saves as f64
        } else {
            0.0
        };
        println!(
            "identity {days}d : tools={} (×{:.1}) · saves={} (×{:.1})",
            id_cur.tool_calls_total, tools_ratio,
            id_cur.memory_saves, saves_ratio
        );
        if transitions.is_empty() {
            println!("transitions  : (none surfaced yet — need ≥2 repeated A→B within 10min)");
        } else {
            println!("transitions  : {} surfaced", transitions.len());
            for (a, b, n) in transitions.iter().take(3) {
                println!(
                    "  [×{n}] {} → {}",
                    short_key(a, 30),
                    short_key(b, 30)
                );
            }
        }
        // ζ-9 — topology line (orphan rate + P4 coverage + top hubs)
        let orphan_pct = if topo.non_skill_active_total > 0 {
            100.0 * topo.orphan_count as f64 / topo.non_skill_active_total as f64
        } else {
            0.0
        };
        let p4_pct = if topo.non_skill_active_total > 0 {
            100.0 * topo.p4_evolved_coverage as f64 / topo.non_skill_active_total as f64
        } else {
            0.0
        };
        println!(
            "topology     : {} non-skill · {} orphan ({:.0}%) · P4 evolved cov {:.0}%",
            topo.non_skill_active_total, topo.orphan_count, orphan_pct, p4_pct
        );
        if let Some((k, deg)) = topo.top_5_hubs.first() {
            println!("  top hub    : deg={deg}  {}", short_key(k, 60));
        }
        println!();
    }

    if print_only {
        eprintln!("(--print-only: not saving)");
        return Ok(());
    }

    // ── save as kind=snapshot memory ─────────────────────────────────────
    // Key format: `snapshot_<slug>_<YYYYMMDD_HHMM>`. Slug defaults to
    // "anon" so daily cron without --name still produces unique keys.
    let slug = name.unwrap_or("anon");
    let key = format!("snapshot_{slug}_{}", time_slug(now));
    let body = serde_json::to_string_pretty(&payload)
        .map_err(|e| anyhow::anyhow!("serialize payload: {e}"))?;
    let rec = MemoryRecord {
        key: key.clone(),
        kind: "snapshot".into(),
        content: body,
        tags: vec!["snapshot".into(), "self-portrait".into()],
        related_keys: vec![],
        scope: None,
        created_at: now,
        updated_at: now,
        last_accessed_at: 0,
        access_count: 0,
        importance: 0.4,
        status: String::new(),
        trigger_pattern: None,
        superseded_by: None,
    };
    store
        .memory_save(&rec)
        .await
        .map_err(|e| anyhow::anyhow!("memory_save: {e}"))?;
    if !as_json {
        eprintln!("saved as memory: {key}");
    } else {
        // In JSON mode, echo the key on stderr so the JSON payload itself
        // stays clean on stdout (pipeline-friendly).
        eprintln!("saved as memory: {key}");
    }
    Ok(())
}

/// Format unix-epoch seconds as `YYYY-MM-DD HH:MM` in the local timezone.
/// Avoids the chrono dependency since we only need this one call site.
fn chrono_like_date(unix_secs: i64) -> String {
    // libc::localtime is the cheapest path; fall back to UTC if it fails.
    let secs = unix_secs as i64;
    // Compute UTC components manually (no external deps). Good enough for
    // logging — DST/local offset not critical here.
    let days_since_epoch = secs.div_euclid(86_400);
    let sod = secs.rem_euclid(86_400);
    let hour = sod / 3600;
    let minute = (sod % 3600) / 60;
    // Use civil_from_days (Howard Hinnant algorithm) for date.
    let (y, mo, d) = civil_from_days(days_since_epoch);
    format!("{:04}-{:02}-{:02} {:02}:{:02} UTC", y, mo, d, hour, minute)
}

/// `YYYYMMDD_HHMM` slug for memory key suffix.
fn time_slug(unix_secs: i64) -> String {
    let days_since_epoch = unix_secs.div_euclid(86_400);
    let sod = unix_secs.rem_euclid(86_400);
    let hour = sod / 3600;
    let minute = (sod % 3600) / 60;
    let (y, mo, d) = civil_from_days(days_since_epoch);
    format!("{:04}{:02}{:02}_{:02}{:02}", y, mo, d, hour, minute)
}

/// Convert days-since-1970-01-01 to (year, month, day) using Hinnant's
/// civil_from_days algorithm. No external date library needed.
fn civil_from_days(z: i64) -> (i32, u32, u32) {
    let z = z + 719_468;
    let era = if z >= 0 { z } else { z - 146096 } / 146_097;
    let doe = (z - era * 146_097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = (if mp < 10 { mp + 3 } else { mp - 9 }) as u32;
    let y = if m <= 2 { y + 1 } else { y };
    (y as i32, m, d)
}

/// ζ-3 (2026-05-11) — Diff two `dream snapshot` memories.
///
/// Reads both `kind=snapshot` rows, parses JSON content (schema v1),
/// auto-orders older → newer by `captured_at`, computes structured deltas
/// across all 6 sections (memory / coactivation / access / identity /
/// transitions). Pretty-prints or emits JSON. Read-only.
///
/// Closes the `dream snapshot` time-series loop: ζ-1 wrote the artifact
/// shape, ζ-3 makes it answer "what changed about me between t_a and t_b"
/// in one command. Vision §5 身份元监控 reaches usable shape.
async fn run_dream_diff(
    key_a: Option<&str>,
    key_b: Option<&str>,
    auto: bool,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;

    // ζ-16: --auto pulls the latest pair of snapshot_daily_* rows.
    // Without --auto, both keys are required (CLI validation lets one
    // through as None for clap reasons, so re-check at runtime).
    let (resolved_a, resolved_b) = if auto {
        let pair = store
            .latest_daily_snapshot_pair()
            .await
            .map_err(|e| anyhow::anyhow!("latest_daily_snapshot_pair: {e}"))?
            .ok_or_else(|| {
                anyhow::anyhow!(
                    "--auto needs at least 2 active `snapshot_daily_*` rows in the store; \
                     run `agent-bridge dream snapshot --name daily` twice (e.g. via the \
                     ζ-10 daily cron) before retrying"
                )
            })?;
        // pair = (older, newer); diff helper auto-orders by captured_at,
        // so order here is informational only.
        (pair.0, pair.1)
    } else {
        let a = key_a
            .ok_or_else(|| anyhow::anyhow!("KEY_A is required unless `--auto` is set"))?
            .to_string();
        let b = key_b
            .ok_or_else(|| anyhow::anyhow!("KEY_B is required unless `--auto` is set"))?
            .to_string();
        (a, b)
    };
    let key_a = resolved_a.as_str();
    let key_b = resolved_b.as_str();

    let rec_a = store
        .memory_get(key_a)
        .await
        .map_err(|e| anyhow::anyhow!("memory_get({key_a}): {e}"))?
        .ok_or_else(|| anyhow::anyhow!("no memory with key {key_a:?}"))?;
    let rec_b = store
        .memory_get(key_b)
        .await
        .map_err(|e| anyhow::anyhow!("memory_get({key_b}): {e}"))?
        .ok_or_else(|| anyhow::anyhow!("no memory with key {key_b:?}"))?;

    if rec_a.kind != "snapshot" || rec_b.kind != "snapshot" {
        anyhow::bail!(
            "both keys must be kind=snapshot (got {} and {})",
            rec_a.kind,
            rec_b.kind
        );
    }

    let pa: serde_json::Value = serde_json::from_str(&rec_a.content)
        .map_err(|e| anyhow::anyhow!("parse {key_a} content as JSON: {e}"))?;
    let pb: serde_json::Value = serde_json::from_str(&rec_b.content)
        .map_err(|e| anyhow::anyhow!("parse {key_b} content as JSON: {e}"))?;

    let schema_a = pa.get("schema_version").and_then(|v| v.as_u64()).unwrap_or(0);
    let schema_b = pb.get("schema_version").and_then(|v| v.as_u64()).unwrap_or(0);
    // ζ-9: allow v1↔v2 — newer schemas are strict supersets so missing
    // fields default to 0/empty via gi64/gf64 helpers below. Bail only on
    // wholly-unsupported versions (e.g. some future v3 that drops fields).
    let supported = (1..=2).contains(&schema_a) && (1..=2).contains(&schema_b);
    if !supported {
        anyhow::bail!(
            "unsupported schema_version pair ({schema_a} vs {schema_b}); diff requires both in 1..=2"
        );
    }

    // Auto-order: smaller captured_at = older.
    let ts_a = pa.get("captured_at").and_then(|v| v.as_i64()).unwrap_or(0);
    let ts_b = pb.get("captured_at").and_then(|v| v.as_i64()).unwrap_or(0);
    let ((older, k_old, ts_old), (newer, k_new, ts_new)) = if ts_a <= ts_b {
        ((&pa, key_a, ts_a), (&pb, key_b, ts_b))
    } else {
        ((&pb, key_b, ts_b), (&pa, key_a, ts_a))
    };
    let dt_secs = (ts_new - ts_old).max(0);

    // Helpers to extract numbers, with 0 fallback.
    let gi64 = |v: &serde_json::Value, path: &[&str]| -> i64 {
        let mut cur = v;
        for p in path {
            cur = match cur.get(*p) {
                Some(x) => x,
                None => return 0,
            };
        }
        cur.as_i64().or_else(|| cur.as_u64().map(|u| u as i64)).unwrap_or(0)
    };
    let gf64 = |v: &serde_json::Value, path: &[&str]| -> f64 {
        let mut cur = v;
        for p in path {
            cur = match cur.get(*p) {
                Some(x) => x,
                None => return 0.0,
            };
        }
        cur.as_f64().unwrap_or(0.0)
    };

    // memory.* deltas
    let active_d = gi64(newer, &["memory", "active_total"])
        - gi64(older, &["memory", "active_total"]);
    let archived_d = gi64(newer, &["memory", "archived_total"])
        - gi64(older, &["memory", "archived_total"]);
    let edges_d = gi64(newer, &["memory", "edge_count"])
        - gi64(older, &["memory", "edge_count"]);
    let avg_imp_d = gf64(newer, &["memory", "avg_importance_active"])
        - gf64(older, &["memory", "avg_importance_active"]);

    // by_kind deltas — diff per kind name. Use HashMap to align.
    let by_kind_old: std::collections::HashMap<String, i64> =
        kind_map(older.get("memory").and_then(|m| m.get("by_kind_non_skill")));
    let by_kind_new: std::collections::HashMap<String, i64> =
        kind_map(newer.get("memory").and_then(|m| m.get("by_kind_non_skill")));
    let kinds_union: std::collections::BTreeSet<String> = by_kind_old
        .keys()
        .chain(by_kind_new.keys())
        .cloned()
        .collect();
    let kind_deltas: Vec<(String, i64, i64)> = kinds_union
        .iter()
        .filter_map(|k| {
            let o = by_kind_old.get(k).copied().unwrap_or(0);
            let n = by_kind_new.get(k).copied().unwrap_or(0);
            if o != n {
                Some((k.clone(), o, n))
            } else {
                None
            }
        })
        .collect();

    // coactivation.* deltas
    let coact_total_d = gi64(newer, &["coactivation", "total_pairs"])
        - gi64(older, &["coactivation", "total_pairs"]);
    let coact_burst_d = gi64(newer, &["coactivation", "pairs_burst_lt_1h"])
        - gi64(older, &["coactivation", "pairs_burst_lt_1h"]);
    let coact_persist_d = gi64(newer, &["coactivation", "pairs_persistent_ge_6h"])
        - gi64(older, &["coactivation", "pairs_persistent_ge_6h"]);

    // access.top_10_keys deltas — which keys entered/left, and access_count changes
    let access_old: std::collections::HashMap<String, i64> =
        access_map(older.get("access").and_then(|a| a.get("top_10_keys")));
    let access_new: std::collections::HashMap<String, i64> =
        access_map(newer.get("access").and_then(|a| a.get("top_10_keys")));
    let entered_top: Vec<(String, i64)> = access_new
        .iter()
        .filter(|(k, _)| !access_old.contains_key(*k))
        .map(|(k, n)| (k.clone(), *n))
        .collect();
    let dropped_top: Vec<(String, i64)> = access_old
        .iter()
        .filter(|(k, _)| !access_new.contains_key(*k))
        .map(|(k, n)| (k.clone(), *n))
        .collect();
    let access_changed: Vec<(String, i64, i64)> = access_new
        .iter()
        .filter_map(|(k, n)| {
            access_old.get(k).and_then(|o| {
                if o != n { Some((k.clone(), *o, *n)) } else { None }
            })
        })
        .collect();

    // identity.{current,prior}.tool_calls_total + memory_saves deltas
    let tools_d = gi64(newer, &["identity", "current", "tool_calls_total"])
        - gi64(older, &["identity", "current", "tool_calls_total"]);
    let saves_d = gi64(newer, &["identity", "current", "memory_saves"])
        - gi64(older, &["identity", "current", "memory_saves"]);

    // ζ-9 — topology deltas (v1 snapshots default to 0/empty via gi64).
    let topo_total_d = gi64(newer, &["topology", "non_skill_active_total"])
        - gi64(older, &["topology", "non_skill_active_total"]);
    let topo_orphan_d = gi64(newer, &["topology", "orphan_count"])
        - gi64(older, &["topology", "orphan_count"]);
    let topo_p4_d = gi64(newer, &["topology", "p4_evolved_coverage"])
        - gi64(older, &["topology", "p4_evolved_coverage"]);
    // Hub set diff — which keys entered/left top-5 hubs.
    let hub_set = |v: Option<&serde_json::Value>| -> Vec<(String, i64)> {
        let mut out = Vec::new();
        if let Some(arr) = v.and_then(|x| x.as_array()) {
            for item in arr {
                if let (Some(k), Some(d)) = (
                    item.get("key").and_then(|x| x.as_str()),
                    item.get("degree").and_then(|x| x.as_i64()),
                ) {
                    out.push((k.to_string(), d));
                }
            }
        }
        out
    };
    let hubs_old = hub_set(older.get("topology").and_then(|t| t.get("top_5_hubs")));
    let hubs_new = hub_set(newer.get("topology").and_then(|t| t.get("top_5_hubs")));
    let hubs_entered: Vec<(String, i64)> = hubs_new
        .iter()
        .filter(|(k, _)| !hubs_old.iter().any(|(x, _)| x == k))
        .cloned()
        .collect();
    let hubs_dropped: Vec<(String, i64)> = hubs_old
        .iter()
        .filter(|(k, _)| !hubs_new.iter().any(|(x, _)| x == k))
        .cloned()
        .collect();

    // transitions.top_5 — entered/left
    let trans_old = trans_set(older.get("transitions").and_then(|t| t.get("top_5")));
    let trans_new = trans_set(newer.get("transitions").and_then(|t| t.get("top_5")));
    let trans_entered: Vec<(String, String, i64)> = trans_new
        .iter()
        .filter(|(a, b, _)| !trans_old.iter().any(|(x, y, _)| x == a && y == b))
        .cloned()
        .collect();
    let trans_dropped: Vec<(String, String, i64)> = trans_old
        .iter()
        .filter(|(a, b, _)| !trans_new.iter().any(|(x, y, _)| x == a && y == b))
        .cloned()
        .collect();

    if as_json {
        let payload = serde_json::json!({
            "older_key": k_old,
            "newer_key": k_new,
            "dt_secs": dt_secs,
            "memory": {
                "active_delta": active_d,
                "archived_delta": archived_d,
                "edges_delta": edges_d,
                "avg_imp_delta": avg_imp_d,
                "kind_deltas": kind_deltas.iter().map(|(k,o,n)| serde_json::json!({"kind":k,"old":o,"new":n,"delta":n-o})).collect::<Vec<_>>(),
            },
            "coactivation": {
                "total_delta": coact_total_d,
                "burst_lt_1h_delta": coact_burst_d,
                "persistent_ge_6h_delta": coact_persist_d,
            },
            "access": {
                "entered_top10": entered_top.iter().map(|(k,n)| serde_json::json!({"key":k,"access_count":n})).collect::<Vec<_>>(),
                "dropped_top10": dropped_top.iter().map(|(k,n)| serde_json::json!({"key":k,"access_count":n})).collect::<Vec<_>>(),
                "changed": access_changed.iter().map(|(k,o,n)| serde_json::json!({"key":k,"old":o,"new":n,"delta":n-o})).collect::<Vec<_>>(),
            },
            "identity": {
                "tools_delta": tools_d,
                "saves_delta": saves_d,
            },
            "transitions": {
                "entered_top5": trans_entered.iter().map(|(a,b,n)| serde_json::json!({"from":a,"to":b,"count":n})).collect::<Vec<_>>(),
                "dropped_top5": trans_dropped.iter().map(|(a,b,n)| serde_json::json!({"from":a,"to":b,"count":n})).collect::<Vec<_>>(),
            },
            "topology": {
                "non_skill_active_delta": topo_total_d,
                "orphan_delta": topo_orphan_d,
                "p4_coverage_delta": topo_p4_d,
                "hubs_entered": hubs_entered.iter().map(|(k,d)| serde_json::json!({"key":k,"degree":d})).collect::<Vec<_>>(),
                "hubs_dropped": hubs_dropped.iter().map(|(k,d)| serde_json::json!({"key":k,"degree":d})).collect::<Vec<_>>(),
            },
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    // Pretty text.
    let dt_human = if dt_secs >= 86_400 {
        format!("{:.1}d", dt_secs as f64 / 86_400.0)
    } else if dt_secs >= 3_600 {
        format!("{:.1}h", dt_secs as f64 / 3_600.0)
    } else {
        format!("{}min", dt_secs / 60)
    };
    println!("# dream diff: {} → {} (Δt={dt_human})", k_old, k_new);
    println!();
    println!(
        "memory       : active {:+} · archived {:+} · edges {:+} · avg_imp {:+.3}",
        active_d, archived_d, edges_d, avg_imp_d
    );
    if !kind_deltas.is_empty() {
        let s: Vec<String> = kind_deltas
            .iter()
            .map(|(k, o, n)| format!("{k} {:+}", n - o))
            .collect();
        println!("  kinds      : {}", s.join(", "));
    }
    println!(
        "coactivation : pairs {:+} · burst<1h {:+} · persistent≥6h {:+}",
        coact_total_d, coact_burst_d, coact_persist_d
    );
    if !entered_top.is_empty() {
        println!("attention    : entered top-10");
        for (k, n) in entered_top.iter().take(5) {
            println!("  + a={n:>3}  {}", short_key(k, 60));
        }
    }
    if !dropped_top.is_empty() {
        println!("               dropped from top-10");
        for (k, n) in dropped_top.iter().take(5) {
            println!("  - a={n:>3}  {}", short_key(k, 60));
        }
    }
    if !access_changed.is_empty() {
        println!("               access changed (in both top-10)");
        for (k, o, n) in access_changed.iter().take(5) {
            println!("    a {:+} ({o}→{n})  {}", n - o, short_key(k, 56));
        }
    }
    println!(
        "identity     : tools {:+} · saves {:+}",
        tools_d, saves_d
    );
    if !trans_entered.is_empty() {
        println!("transitions  : entered top-5");
        for (a, b, n) in trans_entered.iter().take(3) {
            println!(
                "  + [×{n}] {} → {}",
                short_key(a, 30),
                short_key(b, 30)
            );
        }
    }
    if !trans_dropped.is_empty() {
        println!("               dropped from top-5");
        for (a, b, n) in trans_dropped.iter().take(3) {
            println!(
                "  - [×{n}] {} → {}",
                short_key(a, 30),
                short_key(b, 30)
            );
        }
    }
    // ζ-9 — topology delta (suppressed when both snapshots are v1 since
    // all deltas would be zero anyway).
    let has_topology = schema_a >= 2 || schema_b >= 2;
    if has_topology {
        println!(
            "topology     : non-skill {:+} · orphan {:+} · P4 cov {:+}",
            topo_total_d, topo_orphan_d, topo_p4_d
        );
        if !hubs_entered.is_empty() {
            println!("  hubs entered top-5");
            for (k, d) in hubs_entered.iter().take(3) {
                println!("  + deg={d}  {}", short_key(k, 60));
            }
        }
        if !hubs_dropped.is_empty() {
            println!("  hubs dropped from top-5");
            for (k, d) in hubs_dropped.iter().take(3) {
                println!("  - deg={d}  {}", short_key(k, 60));
            }
        }
    }
    if entered_top.is_empty()
        && dropped_top.is_empty()
        && access_changed.is_empty()
        && trans_entered.is_empty()
        && trans_dropped.is_empty()
        && coact_total_d == 0
        && active_d == 0
        && archived_d == 0
        && edges_d == 0
        && topo_total_d == 0
        && topo_orphan_d == 0
        && topo_p4_d == 0
    {
        println!();
        println!("(no notable deltas — quiet window)");
    }
    Ok(())
}

/// Monday-morning composite: bundles replay-audit + signal-fidelity +
/// optional snapshot into one command. Vision §5 身份元监控 surface for
/// the human reviewer — answers "what does the memory state look like
/// this week, and is the Hebbian closure still working?" in one scroll.
///
/// Three sections, separated by blank-line dividers in pretty mode:
///   1. replay-audit (P5 summary use + waypoint + orphan-overlap)
///   2. signal-fidelity (Spearman importance↔access + misranks)
///   3. snapshot key (if not --no-snapshot; identifies the freshly-saved
///      `kind=snapshot` memory the next `dream weekly` can diff against)
async fn run_dream_weekly(no_snapshot: bool, as_json: bool) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};

    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;

    // Replay-audit with defaults: stale_days=7, waypoint_window=30min,
    // overlap=0.5.
    let replay = store
        .replay_audit_stats(7, 30 * 60, 0.5)
        .await
        .map_err(|e| anyhow::anyhow!("replay_audit_stats: {e}"))?;

    // Signal-fidelity with default top_n=5.
    let fidelity = store
        .signal_fidelity_stats(5)
        .await
        .map_err(|e| anyhow::anyhow!("signal_fidelity_stats: {e}"))?;

    // Optional snapshot: tag it `weekly` so future weekly diffs can find
    // the prior pulse without grepping all `kind=snapshot` rows.
    let now_epoch = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let snapshot_key: Option<String> = if no_snapshot {
        None
    } else {
        let auto_name = format!("weekly_{now_epoch}");
        match run_dream_snapshot(Some(&auto_name), 1, false, true).await {
            Ok(()) => Some(format!("snapshot_{auto_name}")),
            Err(e) => {
                eprintln!("(snapshot save skipped: {e})");
                None
            }
        }
    };

    if as_json {
        let payload = serde_json::json!({
            "generated_at_epoch": now_epoch,
            "snapshot_key": snapshot_key,
            "replay_audit": replay,
            "signal_fidelity": fidelity,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    // ── Section 1: replay-audit ────────────────────────────────────────
    println!("════════════════════════════════════════════════════════════");
    println!("  dream weekly — Monday-morning composite");
    println!("  DB: {}", path.display());
    println!("  generated_at_epoch: {now_epoch}");
    println!("════════════════════════════════════════════════════════════");
    println!();
    println!("[1/3] replay-audit (P5 summary quality)");
    println!("─────────────────────────────────────────");
    if replay.total_summaries == 0 {
        println!("  (no p5_replay summaries yet — run `dream replay` first)");
    } else {
        let useful_ratio = 100.0 * replay.accessed_multi as f64 / replay.total_summaries as f64;
        println!(
            "  {} summaries · {:.0}% accessed≥2 · avg access {:.1} (vs source {:.1})",
            replay.total_summaries, useful_ratio,
            replay.avg_access_count, replay.avg_source_access_count
        );
        if let Some(wp) = &replay.waypoint {
            println!(
                "  waypoint ±{}min: {} gateway, {} trailing, {} isolated",
                wp.window_secs / 60,
                wp.gateway_summaries,
                wp.trailing_summaries,
                wp.isolated_summaries,
            );
        }
        if !replay.overlap_pairs.is_empty() {
            println!(
                "  orphan-overlap (J≥0.5): {} duplicate-candidate pair(s)",
                replay.overlap_pairs.len()
            );
            for op in replay.overlap_pairs.iter().take(3) {
                println!(
                    "    J={:.2}  {} ↔ {}",
                    op.jaccard,
                    short_key(&op.key_a, 40),
                    short_key(&op.key_b, 40),
                );
            }
        }
    }

    // ── Section 2: signal-fidelity ────────────────────────────────────
    println!();
    println!("[2/3] signal-fidelity (Hebbian closure observability)");
    println!("─────────────────────────────────────────");
    if fidelity.total_active < 2 {
        println!("  (not enough rows to compute correlation)");
    } else {
        println!(
            "  {} active · {} zero-access ({:.0}%) · {} at floor ({:.0}%)",
            fidelity.total_active,
            fidelity.n_zero_access,
            100.0 * fidelity.n_zero_access as f64 / fidelity.total_active as f64,
            fidelity.n_floor_importance,
            100.0 * fidelity.n_floor_importance as f64 / fidelity.total_active as f64,
        );
        println!(
            "  spearman r (all)     : {:>+.3}  (touched={:>+.3}, n={})",
            fidelity.spearman_r, fidelity.spearman_r_touched, fidelity.n_touched,
        );
        if !fidelity.under_reinforced.is_empty() {
            println!(
                "  top under-reinforced: imp={:.2} acc={} · {}",
                fidelity.under_reinforced[0].importance,
                fidelity.under_reinforced[0].access_count,
                short_key(&fidelity.under_reinforced[0].key, 48),
            );
        }
        if !fidelity.over_promoted.is_empty() {
            println!(
                "  top over-promoted   : imp={:.2} acc={} · {}",
                fidelity.over_promoted[0].importance,
                fidelity.over_promoted[0].access_count,
                short_key(&fidelity.over_promoted[0].key, 48),
            );
        }
    }

    // ── Section 3: snapshot key ───────────────────────────────────────
    println!();
    println!("[3/3] snapshot");
    println!("─────────────────────────────────────────");
    match &snapshot_key {
        Some(key) => println!("  saved: {key}"),
        None => println!("  (skipped — pass without --no-snapshot to capture)"),
    }
    println!();
    println!(
        "next: re-run `dream weekly` in 7 days; \
         compare via `dream diff <prev_key> <this_key>` for drift."
    );
    Ok(())
}

/// Build a kind→count map from a JSON array of `{kind, count}` objects.
/// Returns empty map on None / non-array / malformed entries.
fn kind_map(v: Option<&serde_json::Value>) -> std::collections::HashMap<String, i64> {
    let mut m = std::collections::HashMap::new();
    if let Some(arr) = v.and_then(|x| x.as_array()) {
        for item in arr {
            if let (Some(k), Some(n)) = (
                item.get("kind").and_then(|x| x.as_str()),
                item.get("count").and_then(|x| x.as_i64()),
            ) {
                m.insert(k.to_string(), n);
            }
        }
    }
    m
}

/// Build a key→access_count map from a JSON array of `{key, access_count}`.
fn access_map(v: Option<&serde_json::Value>) -> std::collections::HashMap<String, i64> {
    let mut m = std::collections::HashMap::new();
    if let Some(arr) = v.and_then(|x| x.as_array()) {
        for item in arr {
            if let (Some(k), Some(n)) = (
                item.get("key").and_then(|x| x.as_str()),
                item.get("access_count").and_then(|x| x.as_i64()),
            ) {
                m.insert(k.to_string(), n);
            }
        }
    }
    m
}

/// Build a vec of (from, to, count) triples from a transitions array.
fn trans_set(v: Option<&serde_json::Value>) -> Vec<(String, String, i64)> {
    let mut out = Vec::new();
    if let Some(arr) = v.and_then(|x| x.as_array()) {
        for item in arr {
            if let (Some(a), Some(b), Some(n)) = (
                item.get("from").and_then(|x| x.as_str()),
                item.get("to").and_then(|x| x.as_str()),
                item.get("count").and_then(|x| x.as_i64()),
            ) {
                out.push((a.to_string(), b.to_string(), n));
            }
        }
    }
    out
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

    // ── ζ-15 archive_alarm_should_fire ──────────────────────────────

    #[test]
    fn archive_alarm_fires_when_above_threshold() {
        // The plain happy path: real archive run, count clears the
        // floor. Threshold-equal also fires (≥, not >).
        assert!(archive_alarm_should_fire(10, 10, false));
        assert!(archive_alarm_should_fire(99, 10, false));
    }

    #[test]
    fn archive_alarm_quiet_below_threshold() {
        // Steady-state cron output: a few archives, well under the
        // operator-set ceiling. Silence is the correct response.
        assert!(!archive_alarm_should_fire(0, 10, false));
        assert!(!archive_alarm_should_fire(9, 10, false));
    }

    #[test]
    fn archive_alarm_silent_on_dry_run() {
        // No archives actually happened — a dry-run count of 500 is a
        // capacity estimate, not a burst. Firing here would spam the
        // operator running `dream archive-orphan-stubs --dry-run` to
        // check what *would* be cleaned.
        assert!(!archive_alarm_should_fire(500, 10, true));
        assert!(!archive_alarm_should_fire(500, 1, true));
    }

    #[test]
    fn archive_alarm_disabled_by_zero_or_negative_threshold() {
        // Operator opt-out: cron clusters where the burst is the
        // expected steady state (e.g. initial sweep) can set
        // --alarm-threshold 0. Negative is treated identically out of
        // defensive programming — clap accepts i64 so a typo like
        // `--alarm-threshold -10` shouldn't silently re-enable.
        assert!(!archive_alarm_should_fire(9999, 0, false));
        assert!(!archive_alarm_should_fire(9999, -1, false));
    }
}
