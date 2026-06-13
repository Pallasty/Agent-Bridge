use ab_agent::{
    AgentRuntime, AuggieRuntime, ClaudeCodeRuntime, CodexRuntime, GeminiRuntime,
    GitWorktreeManager, OpenCodeFamilyRuntime, OzAgentRuntime,
};
use ab_bridge::biocortex_shadow::{
    biocortex_replay_comparison, biocortex_retrieval_opt_in_audit_report,
    biocortex_retrieval_opt_in_authorization_decision_packet,
    biocortex_retrieval_opt_in_batch_diagnostics, biocortex_retrieval_opt_in_dry_run_plan,
    biocortex_retrieval_opt_in_execution_packet,
    biocortex_retrieval_opt_in_gated_batch_diagnostics,
    biocortex_retrieval_opt_in_gated_store_trial, biocortex_retrieval_opt_in_order_diff_packet,
    biocortex_retrieval_opt_in_post_implementation_review_gate,
    biocortex_retrieval_opt_in_redacted_order_artifact, biocortex_retrieval_opt_in_review_packet,
    biocortex_retrieval_opt_in_runtime_influence_decision_packet,
    biocortex_retrieval_opt_in_runtime_influence_review_request,
    biocortex_retrieval_opt_in_runtime_readiness_packet,
    biocortex_retrieval_opt_in_runtime_transition_gate, biocortex_retrieval_opt_in_runtime_trial,
    biocortex_retrieval_opt_in_runtime_trial_review_packet, biocortex_retrieval_opt_in_store_trial,
    biocortex_retrieval_runtime_approval_packet_preview, biocortex_shadow_digest,
    supported_benchmarks, BioCortexReplayComparisonOptions,
    BioCortexRetrievalApprovalPacketOptions, BioCortexRetrievalCandidate,
    BioCortexRetrievalOptInAuditOptions, BioCortexRetrievalOptInAuthorizationDecisionPacketOptions,
    BioCortexRetrievalOptInBatchDiagnosticsOptions, BioCortexRetrievalOptInBatchQueryCase,
    BioCortexRetrievalOptInDryRunOptions, BioCortexRetrievalOptInExecutionPacketOptions,
    BioCortexRetrievalOptInGatedBatchDiagnosticsOptions,
    BioCortexRetrievalOptInGatedStoreTrialOptions, BioCortexRetrievalOptInOrderDiffPacketOptions,
    BioCortexRetrievalOptInPostImplementationReviewGateOptions,
    BioCortexRetrievalOptInRedactedOrderArtifactOptions,
    BioCortexRetrievalOptInReviewPacketOptions,
    BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions,
    BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions,
    BioCortexRetrievalOptInRuntimeReadinessPacketOptions,
    BioCortexRetrievalOptInRuntimeTransitionGateOptions,
    BioCortexRetrievalOptInRuntimeTrialOptions,
    BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions,
    BioCortexRetrievalOptInStoreTrialOptions, BioCortexShadowOptions,
    BIOCORTEX_RETRIEVAL_DISABLE_ENV,
};
#[cfg(feature = "biocortex-retrieval-shadow")]
use ab_bridge::biocortex_shadow::{
    biocortex_retrieval_shadow_report, BioCortexRetrievalShadowOptions,
};
use ab_bridge::seed_substrate as ab_seed_bridge;
use ab_bridge::shadow_cortex as ab_shadow_cortex;
use ab_bridge::warp_scheme;
use ab_bridge::{browser_lite, instinct, skills};
use ab_bridge::{build_registry, default_socket_path, serve, Hub, Router};
use ab_browser::{BrowserBackend, ChromiumCdpBackend};
use ab_mcp::server::serve_stdio;
use ab_store::{default_db_path, SqliteStore, StateStore};
use ab_terminal::{auto_backend, TerminalBackend};
use anyhow::{Context, Result};
use clap::{Parser, Subcommand, ValueEnum};
use serde_json::{json, Map, Value};
use std::path::PathBuf;
use std::sync::Arc;
use tracing_subscriber::{prelude::*, EnvFilter};

mod doctor;
mod seed_substrate;
mod setup;
mod shadow_cortex;
use ab_bridge::sync;

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
    /// Deployment self-check: verify the wrapper is intact (not clobbered by a
    /// direct binary), agent-bridge.real exists, the SVD projection env is
    /// injected + its artifact resolvable, the running daemon carries the SVD
    /// env, and MCP servers exec the current binary. Catches silent
    /// "deployed but didn't take effect" failures. Exits non-zero on any fail.
    Doctor {
        /// Emit a JSON report instead of the human-readable table.
        #[arg(long)]
        json: bool,
        /// Emit a Markdown operator snapshot (paste into forum/commit/handoff).
        #[arg(long)]
        markdown: bool,
    },
    /// Inspect or rotate the local instinct observer sidecar log.
    Instinct {
        #[command(subcommand)]
        op: InstinctOp,
    },
    /// Install agent-bridge for the chosen frontend.
    ///
    /// `--frontend claude-code` (default): copies the binary to
    /// `~/.local/bin/agent-bridge`, writes the three Claude Code hook
    /// scripts, and merges hook entries into `~/.claude/settings.json`.
    ///
    /// `--frontend codex`: installs the Codex desktop profile with MCP config
    /// plus Codex lifecycle hooks and the instinct observer hook.
    ///
    /// Add `--codex-toolset lean` to write the narrower experimental Codex
    /// tool surface without changing the default stable profile.
    ///
    /// `--frontend codex-cli` / `--frontend codex-ide`: register Codex MCP
    /// config with a host marker but skip desktop lifecycle hooks.
    ///
    /// `--frontend gemini-cli`: copies the binary and registers the MCP server
    /// in `~/.gemini/settings.json`.
    ///
    /// `--frontend cursor`: copies the binary and registers the MCP server
    /// in `~/.cursor/mcp.json` with `AGENT_BRIDGE_TOOLSET=claude-standard`.
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
        #[arg(long, value_enum, default_value_t = SetupCodexToolset::Essential)]
        codex_toolset: SetupCodexToolset,
        /// Print the setup plan without writing files or invoking client CLIs.
        #[arg(long)]
        dry_run: bool,
        /// Emit the setup dry-run plan as JSON. Implies --dry-run.
        #[arg(long)]
        json: bool,
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
    /// Probe optional lightweight browser backends without changing routing.
    ///
    /// This is a read-only discovery surface for external browser-lite
    /// candidates such as Obscura. It never starts a persistent service and
    /// does not alter the default Chrome-backed browser tools.
    BrowserLite {
        #[command(subcommand)]
        op: BrowserLiteOp,
    },
    /// Read-only avatar/presence surfaces for terminal dashboards.
    Avatar {
        #[command(subcommand)]
        op: AvatarOp,
    },
    /// Run the v20 HTTP daemon for cross-machine forum + presence over
    /// Tailscale.
    ///
    /// Read-only in Stage 1: serves `/.well-known/agent.json/<sid>`,
    /// `/forum/threads`, `/forum/posts`, `/presence`, and the
    /// `/avatar-surface` JSON/text/HTML read-only surfaces. Bind to a
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
    /// **v22** — Memory substrate Layer 2 introspection.
    ///
    /// Substrate is opt-in via `AB_SUBSTRATE=1` and lives inside the running
    /// MCP server / palace serve process. CLI introspection reads the
    /// in-process global if this binary was the one that installed it;
    /// otherwise reports config + "not installed" state. Phase 2.2 ships
    /// Parquet snapshot persistence at `$HOME/.local/share/agent-bridge/
    /// substrate.parquet` for cross-process state inspection.
    Substrate {
        #[command(subcommand)]
        op: SubstrateOp,
    },
    /// BioCortex shadow integration probes.
    ///
    /// Runs sanctioned read-only adapter examples from a local `biocortex-rs`
    /// checkout and projects their `key=value` report into AB JSON. This does
    /// not link BioCortex into the AB runtime or mutate AB memory.
    BioCortex {
        #[command(subcommand)]
        op: BioCortexOp,
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
    /// **C2 — Canonical state.db rescue snapshot** (Collab Protocol v0 §3.3).
    ///
    /// Reads `state.db{,-wal,-shm}` directly from the running daemon's
    /// FD table (`/proc/<daemon-pid>/fd/`) so the snapshot captures the
    /// inode the daemon is actually using — immune to the unlink+replace
    /// race that produced phantoms during the 2026-05-14 incident.
    ///
    /// Coordinated by a first-writer-wins lockfile under
    /// `~/.cache/agent-bridge/locks/state.db.rescue.lock`. A sibling
    /// racing in on the same op sees the lock and exits 1 with the
    /// existing artifact's path rather than producing a divergent
    /// snapshot.
    ///
    /// Exit codes: 0 = own snapshot completed, 1 = attached to existing.
    RescueSnapshot {
        /// Required for v0 — explicit acknowledgement that the caller
        /// wants the canonical (FD-based) rescue. Reserved for future
        /// `--path` mode that would explicitly accept the path-based
        /// race; we don't want that path used implicitly.
        #[arg(long)]
        canonical: bool,
        /// TTL for the lockfile. Default 300s gives a slow rescue
        /// plenty of room. Past this age a sibling will force-break.
        #[arg(long, default_value_t = 300)]
        ttl_secs: u64,
        /// Override the daemon PID. Default: scan /proc for the
        /// canonical `agent-bridge.real daemon` process.
        #[arg(long)]
        pid: Option<u32>,
        /// Emit raw JSON of [`ab_bridge::rescue::RescueReport`].
        #[arg(long)]
        json: bool,
    },
}

#[derive(Copy, Clone, Debug, ValueEnum)]
enum ShellKind {
    Bash,
    Zsh,
    Fish,
}

#[derive(Subcommand, Debug)]
enum InstinctOp {
    /// Rotate the local instinct observer JSONL log by renaming it to a
    /// timestamped archive path. The hook recreates a fresh log on its next
    /// event.
    RotateLog {
        /// Print the rotation plan without moving the log.
        #[arg(long)]
        dry_run: bool,
        /// Emit raw JSON payload instead of a command line summary.
        #[arg(long)]
        json: bool,
    },
}

#[derive(Subcommand, Debug)]
enum BrowserLiteOp {
    /// Probe an optional browser-lite backend and print a capability report.
    Probe {
        /// Backend to probe. Defaults to obscura.
        #[arg(value_enum, default_value = "obscura")]
        backend: BrowserLiteBackend,
        /// Override backend binary path. Otherwise uses AGENT_BRIDGE_OBSCURA_BIN, then PATH.
        #[arg(long)]
        bin: Option<PathBuf>,
        /// Probe MCP tools/list in addition to `--help`.
        ///
        /// Enabled by default because tool count is part of the provenance
        /// evidence for external browser-lite routing decisions.
        #[arg(long = "no-mcp-tools", default_value_t = false)]
        no_mcp_tools: bool,
        /// Per-probe timeout for backend commands.
        #[arg(long, default_value_t = 5_000)]
        timeout_ms: u64,
        /// Emit raw JSON payload instead of a command line summary.
        #[arg(long)]
        json: bool,
    },
}

#[derive(Copy, Clone, Debug, ValueEnum)]
enum BrowserLiteBackend {
    Obscura,
}

#[derive(Subcommand, Debug)]
enum AvatarOp {
    /// Render the Agent Avatar Protocol surface from local presence rows.
    Surface {
        /// Filter by project slug.
        #[arg(long)]
        project: Option<String>,
        /// Filter by role.
        #[arg(long)]
        role: Option<String>,
        /// Skip rows whose heartbeat is older than this. 0 = no TTL.
        #[arg(long, default_value_t = 300)]
        max_idle_secs: i64,
        /// Equivalent to --max-idle-secs 0.
        #[arg(long)]
        include_stale: bool,
        /// Max rows to include.
        #[arg(long, default_value_t = 20)]
        limit: u32,
        /// Emit raw JSON payload instead of the human-readable report.
        #[arg(long)]
        json: bool,
        /// Include original presence row in each JSON avatar entry.
        #[arg(long)]
        include_raw_presence: bool,
        /// Include compatibility capabilities.pet_state in each JSON avatar entry.
        #[arg(long)]
        include_compat: bool,
    },
    /// Probe the compositor and report which avatar body backend can satisfy
    /// transparency here (native wlr-layer-shell vs degraded browser). Env-only,
    /// read-only — spawns nothing and controls nothing (LCC-F1).
    BackendProbe {
        /// Emit raw JSON instead of a human-readable summary.
        #[arg(long)]
        json: bool,
    },
    /// Open the Linux avatar renderer in a small browser app window.
    LinuxFloater {
        /// Base URL for a running daemon-http instance.
        #[arg(long, default_value = "http://127.0.0.1:7878")]
        base_url: String,
        /// Filter by project slug.
        #[arg(long)]
        project: Option<String>,
        /// Filter by role.
        #[arg(long)]
        role: Option<String>,
        /// Equivalent to renderer include_stale=true.
        #[arg(long)]
        include_stale: bool,
        /// Request the pet-only transparent renderer route and browser hints.
        #[arg(long)]
        transparent: bool,
        /// Browser binary. Defaults to the first supported browser on PATH.
        #[arg(long)]
        browser: Option<String>,
        /// Floater window width in pixels.
        #[arg(long, default_value_t = 360)]
        width: u32,
        /// Floater window height in pixels.
        #[arg(long, default_value_t = 520)]
        height: u32,
        /// After launch, ask Sway to make the renderer floating/sticky.
        #[arg(long)]
        sway_manage: bool,
        /// Sway X coordinate used with --sway-manage.
        #[arg(long, default_value_t = 40)]
        sway_x: i32,
        /// Sway Y coordinate used with --sway-manage.
        #[arg(long, default_value_t = 80)]
        sway_y: i32,
        /// Print the launch plan without spawning the browser.
        #[arg(long)]
        dry_run: bool,
        /// Emit raw JSON payload instead of a command line summary.
        #[arg(long)]
        json: bool,
    },
    /// Run a native Wayland/layer-shell transparent avatar probe.
    LinuxNativeTransparent {
        /// Probe surface width in pixels.
        #[arg(long, default_value_t = 360)]
        width: u32,
        /// Probe surface height in pixels.
        #[arg(long, default_value_t = 520)]
        height: u32,
        /// Layer-shell layer: top or overlay.
        #[arg(long, default_value = "overlay")]
        layer: String,
        /// Screen anchor: top-left, top-right, bottom-left, bottom-right.
        #[arg(long, default_value = "bottom-right")]
        anchor: String,
        /// Top margin in pixels.
        #[arg(long, default_value_t = 0)]
        margin_top: i32,
        /// Right margin in pixels.
        #[arg(long, default_value_t = 96)]
        margin_right: i32,
        /// Bottom margin in pixels.
        #[arg(long, default_value_t = 96)]
        margin_bottom: i32,
        /// Left margin in pixels.
        #[arg(long, default_value_t = 0)]
        margin_left: i32,
        /// How long to keep the probe visible.
        #[arg(long, default_value_t = 2_000)]
        duration_ms: u64,
        /// Avatar lifecycle mode used to choose a native PNG sprite asset.
        #[arg(long, default_value = "idle")]
        mode: String,
        /// Pet sidecar id to poll for live state updates. Omit for static --mode.
        #[arg(long)]
        pet_id: Option<String>,
        /// HTTP renderer-state endpoint to poll for live state updates.
        #[arg(long)]
        state_url: Option<String>,
        /// Milliseconds between live state polls when --pet-id or --state-url is set.
        #[arg(long, default_value_t = ab_bridge::avatar_native::DEFAULT_NATIVE_STATE_POLL_MS)]
        state_poll_ms: u64,
        /// HTTP timeout in milliseconds when --state-url is set.
        #[arg(long, default_value_t = ab_bridge::avatar_native::DEFAULT_NATIVE_STATE_HTTP_TIMEOUT_MS)]
        state_http_timeout_ms: u64,
        /// Override the sidecar sprite asset id. Use `none` for marker-only probe.
        #[arg(long)]
        asset: Option<String>,
        /// Atlas frame column.
        #[arg(long, default_value_t = 0)]
        frame_col: u32,
        /// Atlas frame row.
        #[arg(long, default_value_t = 0)]
        frame_row: u32,
        /// Atlas cell width.
        #[arg(long, default_value_t = ab_bridge::avatar_native::DEFAULT_NATIVE_SPRITE_CELL_WIDTH)]
        cell_width: u32,
        /// Atlas cell height.
        #[arg(long, default_value_t = ab_bridge::avatar_native::DEFAULT_NATIVE_SPRITE_CELL_HEIGHT)]
        cell_height: u32,
        /// Sprite scale as a percentage.
        #[arg(long, default_value_t = ab_bridge::avatar_native::DEFAULT_NATIVE_SPRITE_SCALE_PERCENT)]
        sprite_scale_percent: u32,
        /// Number of atlas frames to animate from the selected base frame.
        #[arg(long, default_value_t = ab_bridge::avatar_native::DEFAULT_NATIVE_FRAME_COUNT)]
        frame_count: u32,
        /// Milliseconds between native sprite frames.
        #[arg(long, default_value_t = ab_bridge::avatar_native::DEFAULT_NATIVE_FRAME_INTERVAL_MS)]
        frame_interval_ms: u64,
        /// Wayland output to place the face on, by name (e.g. DP-1). Omit for the
        /// compositor's default output.
        #[arg(long)]
        output: Option<String>,
        /// Print the launch plan without opening the native surface.
        #[arg(long)]
        dry_run: bool,
        /// Emit raw JSON payload instead of a command line summary.
        #[arg(long)]
        json: bool,
    },
    /// Sync the current pet sidecar into a presence row for CLI/launchd heartbeats.
    SyncPresence {
        /// Pet id to sync. Defaults to AB_PET_ID, current Codex avatar, then xiao-shu-v2.
        #[arg(long)]
        pet_id: Option<String>,
        /// Optional explicit presence session id.
        #[arg(long)]
        session_id: Option<String>,
        /// Presence display name.
        #[arg(long)]
        name: Option<String>,
        /// Presence description.
        #[arg(long)]
        description: Option<String>,
        /// Presence version label.
        #[arg(long)]
        version: Option<String>,
        /// Reserved daemon URL.
        #[arg(long)]
        url: Option<String>,
        /// Override hostname.
        #[arg(long)]
        node: Option<String>,
        /// Override project slug.
        #[arg(long)]
        project: Option<String>,
        /// Presence role.
        #[arg(long, default_value = "main")]
        role: String,
        /// Optional disambiguator.
        #[arg(long)]
        tag: Option<String>,
        /// Optional Agent Avatar Protocol agent_id override.
        #[arg(long)]
        agent_id: Option<String>,
        /// Runtime label for the adapter writing this row.
        #[arg(long, default_value = "local-cli")]
        runtime: String,
        /// Caller cwd. Defaults to this CLI process cwd.
        #[arg(long)]
        cwd: Option<String>,
        /// Caller pid. Defaults to this CLI process.
        #[arg(long)]
        pid: Option<i64>,
        /// Disable pid-tag collision avoidance.
        #[arg(long)]
        no_auto_tag: bool,
        /// Optional fine-grained work posture.
        #[arg(long)]
        activity_state: Option<String>,
        /// Optional compact focus label.
        #[arg(long)]
        focus: Option<String>,
        /// Optional low/medium/high risk hint.
        #[arg(long)]
        risk_level: Option<String>,
        /// Optional compact blocked reason.
        #[arg(long)]
        blocked_reason: Option<String>,
        /// Optional compact verification evidence.
        #[arg(long)]
        evidence: Option<String>,
        /// Optional compact next local action.
        #[arg(long)]
        next_action: Option<String>,
        /// Voice policy override for presence metadata only.
        #[arg(long)]
        tts_voice: Option<String>,
        /// Voice rate policy override for presence metadata only.
        #[arg(long)]
        tts_rate: Option<u64>,
        /// Emit the full JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Install a macOS launchd job that periodically runs avatar sync-presence.
    InstallHeartbeat {
        /// launchd label. Defaults to com.agentbridge.avatar-heartbeat.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Stable agent/presence project. Defaults to cwd basename.
        #[arg(long)]
        project: Option<String>,
        /// Presence role for the heartbeat row.
        #[arg(long, default_value = "heartbeat")]
        role: String,
        /// Stable presence session id. Defaults to the launchd label.
        #[arg(long)]
        session_id: Option<String>,
        /// Stable Agent Avatar Protocol agent_id. Defaults to session id.
        #[arg(long)]
        agent_id: Option<String>,
        /// Runtime label for the adapter writing this row.
        #[arg(long, default_value = "local-cli")]
        runtime: String,
        /// Pet id to sync.
        #[arg(long)]
        pet_id: Option<String>,
        /// Working directory to report.
        #[arg(long)]
        cwd: Option<PathBuf>,
        /// Installed agent-bridge binary for launchd to run.
        #[arg(long)]
        bin: Option<PathBuf>,
        /// StartInterval seconds.
        #[arg(long, default_value_t = 60)]
        interval_secs: u64,
        /// Optional fine-grained work posture.
        #[arg(long)]
        activity_state: Option<String>,
        /// Optional compact focus label.
        #[arg(long)]
        focus: Option<String>,
        /// Optional low/medium/high risk hint.
        #[arg(long)]
        risk_level: Option<String>,
        /// Optional compact verification evidence.
        #[arg(long)]
        evidence: Option<String>,
        /// Optional compact next local action.
        #[arg(long)]
        next_action: Option<String>,
        /// Voice policy override for presence metadata only.
        #[arg(long)]
        tts_voice: Option<String>,
        /// Voice rate policy override for presence metadata only.
        #[arg(long)]
        tts_rate: Option<u64>,
        /// Write the plist but do not bootstrap it.
        #[arg(long)]
        no_load: bool,
        /// Print the plist instead of writing or loading it.
        #[arg(long)]
        dry_run: bool,
    },
    /// Remove a macOS launchd avatar heartbeat job and plist.
    RemoveHeartbeat {
        /// launchd label. Defaults to com.agentbridge.avatar-heartbeat.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Project used to derive the default label.
        #[arg(long)]
        project: Option<String>,
    },
    /// Show launchd status for an avatar heartbeat job.
    HeartbeatStatus {
        /// launchd label. Defaults to com.agentbridge.avatar-heartbeat.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Project used to derive the default label.
        #[arg(long)]
        project: Option<String>,
    },
    /// Summarize launchd plus presence health for an avatar heartbeat job.
    HeartbeatHealth {
        /// launchd label. Defaults to com.agentbridge.avatar-heartbeat.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Project used to derive the default label.
        #[arg(long)]
        project: Option<String>,
        /// Heartbeat age threshold for stale detection.
        #[arg(long, default_value_t = 300)]
        stale_secs: i64,
        /// Emit raw JSON payload instead of the human-readable summary.
        #[arg(long)]
        json: bool,
    },
    /// Emit a sparse notification/TTS only when heartbeat health changes.
    HeartbeatAlert {
        /// launchd label. Defaults to com.agentbridge.avatar-heartbeat.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Project used to derive the default label.
        #[arg(long)]
        project: Option<String>,
        /// Heartbeat age threshold for stale detection.
        #[arg(long, default_value_t = 300)]
        stale_secs: i64,
        /// Force an alert even if the event key is unchanged.
        #[arg(long)]
        force: bool,
        /// Compute and record the event but do not emit notification or TTS.
        #[arg(long)]
        preview: bool,
        /// Suppress desktop notification emission.
        #[arg(long)]
        no_notification: bool,
        /// Also speak the status line with macOS say.
        #[arg(long)]
        tts: bool,
        /// Repeat an unchanged unhealthy alert after this many seconds. 0 disables repeats.
        #[arg(long, default_value_t = 3600)]
        repeat_secs: i64,
        /// Optional macOS say voice for --tts.
        #[arg(long)]
        tts_voice: Option<String>,
        /// Optional macOS say rate for --tts.
        #[arg(long)]
        tts_rate: Option<u64>,
        /// Emit raw JSON payload instead of the human-readable summary.
        #[arg(long)]
        json: bool,
    },
    /// Install a macOS launchd job that periodically runs avatar heartbeat-alert.
    InstallHeartbeatAlert {
        /// launchd label. Defaults to com.agentbridge.avatar-heartbeat-alert.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Project used to derive the default label.
        #[arg(long)]
        project: Option<String>,
        /// Installed agent-bridge binary for launchd to run.
        #[arg(long)]
        bin: Option<PathBuf>,
        /// StartInterval seconds.
        #[arg(long, default_value_t = 120)]
        interval_secs: u64,
        /// Heartbeat age threshold for stale detection.
        #[arg(long, default_value_t = 300)]
        stale_secs: i64,
        /// Repeat an unchanged unhealthy alert after this many seconds. 0 disables repeats.
        #[arg(long, default_value_t = 3600)]
        repeat_secs: i64,
        /// Suppress desktop notification emission.
        #[arg(long)]
        no_notification: bool,
        /// Also speak the status line with macOS say when an alert emits.
        #[arg(long)]
        tts: bool,
        /// Optional macOS say voice for --tts.
        #[arg(long)]
        tts_voice: Option<String>,
        /// Optional macOS say rate for --tts.
        #[arg(long)]
        tts_rate: Option<u64>,
        /// Write the plist but do not bootstrap it.
        #[arg(long)]
        no_load: bool,
        /// Print the plist instead of writing or loading it.
        #[arg(long)]
        dry_run: bool,
    },
    /// Remove a macOS launchd avatar heartbeat alert job and plist.
    RemoveHeartbeatAlert {
        /// launchd label. Defaults to com.agentbridge.avatar-heartbeat-alert.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Project used to derive the default label.
        #[arg(long)]
        project: Option<String>,
    },
    /// Show launchd status for an avatar heartbeat alert job.
    HeartbeatAlertStatus {
        /// launchd label. Defaults to com.agentbridge.avatar-heartbeat-alert.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Project used to derive the default label.
        #[arg(long)]
        project: Option<String>,
    },
    /// Project avatar heartbeat alert events into Seed substrate replay JSONL.
    SeedEvents {
        /// Heartbeat label. Defaults to com.agentbridge.avatar-heartbeat.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Project used to derive the default heartbeat label.
        #[arg(long)]
        project: Option<String>,
        /// Override alert events JSONL path.
        #[arg(long)]
        input: Option<PathBuf>,
        /// Keep the latest N projected records. 0 keeps all.
        #[arg(long, default_value_t = 20)]
        limit: usize,
        /// Include preview/dogfood events. Defaults to production events only.
        #[arg(long)]
        include_preview: bool,
        /// Write projected replay JSONL to this path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Print projected replay JSONL to stdout.
        #[arg(long)]
        jsonl: bool,
        /// Emit summary JSON payload instead of the human-readable summary.
        #[arg(long)]
        json: bool,
    },
    /// Replay avatar Seed events into an isolated shadow-only Xiao Shu cortex snapshot.
    CortexReplay {
        /// Heartbeat label. Defaults to com.agentbridge.avatar-heartbeat.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Project used to derive the default heartbeat label.
        #[arg(long)]
        project: Option<String>,
        /// Override alert events JSONL path.
        #[arg(long)]
        input: Option<PathBuf>,
        /// Output path for the isolated avatar cortex snapshot.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Keep the latest N projected records. 0 keeps all.
        #[arg(long, default_value_t = 200)]
        limit: usize,
        /// Include preview/dogfood events.
        #[arg(long)]
        include_preview: bool,
        /// Use OnnxBackend instead of the default HashBackend.
        #[arg(long)]
        onnx: bool,
        /// Grid size N for the isolated cortex.
        #[arg(long, default_value_t = 64)]
        n: usize,
        /// Substrate perception dimension D for the isolated cortex.
        #[arg(long, default_value_t = 64)]
        d: usize,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Install a macOS launchd job that periodically refreshes the Xiao Shu cortex snapshot.
    InstallCortexRunner {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label to consume. Defaults to com.agentbridge.avatar-heartbeat.<project>.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Installed agent-bridge binary for launchd to run.
        #[arg(long)]
        bin: Option<PathBuf>,
        /// StartInterval seconds.
        #[arg(long, default_value_t = 300)]
        interval_secs: u64,
        /// Output path for the isolated avatar cortex snapshot.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Keep the latest N projected records. 0 keeps all.
        #[arg(long, default_value_t = 500)]
        limit: usize,
        /// Include preview/dogfood events.
        #[arg(long)]
        include_preview: bool,
        /// Use OnnxBackend instead of the default HashBackend.
        #[arg(long)]
        onnx: bool,
        /// Grid size N for the isolated cortex.
        #[arg(long, default_value_t = 64)]
        n: usize,
        /// Substrate perception dimension D for the isolated cortex.
        #[arg(long, default_value_t = 64)]
        d: usize,
        /// Write the plist but do not bootstrap it.
        #[arg(long)]
        no_load: bool,
        /// Print the plist instead of writing or loading it.
        #[arg(long)]
        dry_run: bool,
    },
    /// Remove the macOS launchd Xiao Shu cortex runner job and plist.
    RemoveCortexRunner {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Project used to derive the default label.
        #[arg(long)]
        project: Option<String>,
    },
    /// Show Xiao Shu cortex runner and snapshot status.
    CortexStatus {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Preview Xiao Shu's cortex voice line without emitting audio or notifications.
    CortexPreview {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Preview Xiao Shu's dynamic language line without emitting audio.
    CortexLanguage {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Preview Xiao Shu's gesture/mood/attention semantics without touching renderer assets.
    CortexMotion {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Dry-run Xiao Shu's motion renderer slot mapping without mutating renderer assets.
    CortexRenderer {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Show the renderer binding candidate registry without mutating renderer assets.
    CortexRendererRegistry {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Plan the first safe Xiao Shu renderer bindings without mutating renderer assets.
    CortexBindingPlan {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Build sidecar renderer preview fixtures for the first safe Xiao Shu bindings.
    CortexBindingFixture {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Preview Xiao Shu sidecar visual frames without rendering pixels or mutating assets.
    CortexVisualAdapter {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Build a browser sidecar renderer view without writing assets or package bindings.
    CortexRendererView {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Score Xiao Shu renderer tracks for manual visual review without approving bindings.
    CortexReviewGate {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Build read-only human review packets for pending Xiao Shu renderer tracks.
    CortexReviewPacket {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Summarize whether pending Xiao Shu renderer packets are ready for human review.
    CortexReviewReport {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// List append-only Xiao Shu renderer review decision records without approving bindings.
    CortexReviewDecisions {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels and ledger path.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Filter to a renderer token.
        #[arg(long)]
        track: Option<String>,
        /// Filter to a decision value.
        #[arg(long)]
        decision: Option<String>,
        /// Include full nested decision records instead of compact rows.
        #[arg(long)]
        details: bool,
        /// Maximum records to return, newest first.
        #[arg(long, default_value_t = 20)]
        limit: usize,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Append one Xiao Shu renderer review decision record without approving or promoting.
    CortexReviewDecision {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels and ledger path.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Actor recording the decision.
        #[arg(long, default_value = "operator")]
        actor: String,
        /// Pending renderer review token to record.
        #[arg(long)]
        track: String,
        /// Decision to record. This is audit-only, not approval.
        #[arg(long, default_value = "keep_pending")]
        decision: String,
        /// Optional human note.
        #[arg(long)]
        note: Option<String>,
        /// Optional evidence pointer, such as a screenshot path or panel observation.
        #[arg(long)]
        evidence: Option<String>,
        /// Required to append the record. Without it, this is a dry-run preview.
        #[arg(long)]
        confirm: bool,
        /// Include full nested source review report in JSON output.
        #[arg(long)]
        details: bool,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Persist a local CLI-only human visual review record for one renderer candidate.
    CortexReviewRecord {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Renderer track token, for example xiao_shu::alert_peek::medium.
        #[arg(long, default_value = "xiao_shu::alert_peek::medium")]
        track: String,
        /// Semantic variant id. Defaults to the track's preferred/default variant.
        #[arg(long)]
        variant: Option<String>,
        /// Human review outcome to record.
        #[arg(long, value_enum, default_value = "approved")]
        outcome: AvatarReviewOutcome,
        /// Actor/reviewer writing the local review record.
        #[arg(long, default_value = "local-operator")]
        reviewer: String,
        /// Operator-facing reason. Required to write with --confirm.
        #[arg(long)]
        reason: Option<String>,
        /// Optional review note. May be repeated.
        #[arg(long = "note")]
        notes: Vec<String>,
        /// Persist the record. Without this flag the command is a dry-run preview.
        #[arg(long)]
        confirm: bool,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Show Xiao Shu's sparse voice policy without emitting audio.
    CortexVoicePolicy {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Preview a two-step Xiao Shu voice confirmation request without emitting audio.
    CortexVoiceRequest {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Renderer token to request. Defaults to the first policy-approved manual voice rule.
        #[arg(long)]
        track: Option<String>,
        /// Operator reason to preview in the future CLI emit command.
        #[arg(long)]
        reason: Option<String>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Dry-run a Xiao Shu voice confirmation action without emitting audio.
    CortexVoiceConfirm {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Renderer token to confirm. Defaults to the first policy-approved manual voice rule.
        #[arg(long)]
        track: Option<String>,
        /// Operator reason required before the future CLI emit command is previewed as executable.
        #[arg(long)]
        reason: Option<String>,
        /// Mark the dry-run confirmation as explicitly requested.
        #[arg(long)]
        confirm: bool,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Run the confirmed Xiao Shu voice action through the CLI-only emit gate.
    CortexVoiceAction {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Renderer token to confirm. Defaults to the first policy-approved manual voice rule.
        #[arg(long)]
        track: Option<String>,
        /// Operator reason required before real audio can be invoked.
        #[arg(long)]
        reason: Option<String>,
        /// Mark the confirmation as explicitly requested.
        #[arg(long)]
        confirm: bool,
        /// Actually invoke the existing CLI-only emit gate after confirmation passes.
        #[arg(long)]
        emit: bool,
        /// Ignore cooldown state for this invocation.
        #[arg(long)]
        force: bool,
        /// Cooldown seconds to evaluate and record after a successful emit.
        #[arg(long, default_value_t = 300)]
        cooldown_secs: i64,
        /// Optional macOS say voice. Defaults to the policy suggestion or AB_PET_TTS_VOICE.
        #[arg(long)]
        tts_voice: Option<String>,
        /// Optional macOS say rate. Defaults to the policy suggestion or AB_PET_TTS_RATE.
        #[arg(long)]
        tts_rate: Option<u64>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Preview whether the confirmed Xiao Shu voice action would emit now.
    CortexVoiceActionPreview {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path and voice cooldown state.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Renderer token to confirm. Defaults to the first policy-approved manual voice rule.
        #[arg(long)]
        track: Option<String>,
        /// Operator reason used in the previewed action command.
        #[arg(long)]
        reason: Option<String>,
        /// Mark the confirmation as explicitly requested.
        #[arg(long)]
        confirm: bool,
        /// Preview readiness as if cooldown state were ignored.
        #[arg(long)]
        force: bool,
        /// Cooldown seconds to evaluate without mutating state.
        #[arg(long, default_value_t = 300)]
        cooldown_secs: i64,
        /// Optional macOS say voice. Defaults to the policy suggestion or AB_PET_TTS_VOICE.
        #[arg(long)]
        tts_voice: Option<String>,
        /// Optional macOS say rate. Defaults to the policy suggestion or AB_PET_TTS_RATE.
        #[arg(long)]
        tts_rate: Option<u64>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Create an LLM-safe Xiao Shu action request without directly controlling the pet.
    XiaoShuActionRequest {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path and voice cooldown state.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Requesting actor label, such as llm, panel, slash, or operator.
        #[arg(long, default_value = "llm")]
        actor: String,
        /// High-level Xiao Shu action intent. Current supported intent: voice_alert.
        #[arg(long, default_value = "voice_alert")]
        intent: String,
        /// Optional natural-language request from the caller.
        #[arg(long)]
        message: Option<String>,
        /// Renderer token to target. Defaults to alert_peek.
        #[arg(long)]
        track: Option<String>,
        /// Operator-facing reason for the request and generated command.
        #[arg(long)]
        reason: Option<String>,
        /// Preview as if a human/operator confirmation is present.
        #[arg(long)]
        confirm: bool,
        /// Append this request to the local pending queue without emitting audio.
        #[arg(long)]
        enqueue: bool,
        /// Preview readiness as if cooldown state were ignored.
        #[arg(long)]
        force: bool,
        /// Cooldown seconds to evaluate without mutating state.
        #[arg(long, default_value_t = 300)]
        cooldown_secs: i64,
        /// Optional macOS say voice. Defaults to the policy suggestion or AB_PET_TTS_VOICE.
        #[arg(long)]
        tts_voice: Option<String>,
        /// Optional macOS say rate. Defaults to the policy suggestion or AB_PET_TTS_RATE.
        #[arg(long)]
        tts_rate: Option<u64>,
        /// Include full nested downstream provenance instead of compact preview output.
        #[arg(long)]
        details: bool,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// List queued Xiao Shu action requests without emitting audio.
    XiaoShuActionRequests {
        /// Project used to derive the queue path.
        #[arg(long)]
        project: Option<String>,
        /// Return one request id, if present.
        #[arg(long)]
        request_id: Option<String>,
        /// State to filter. Defaults to pending_human_confirmation.
        #[arg(long)]
        state: Option<String>,
        /// Include all queue states instead of only pending records.
        #[arg(long)]
        all_states: bool,
        /// Include full nested queue records. Defaults to compact list records.
        #[arg(long)]
        details: bool,
        /// Maximum records to return, newest first.
        #[arg(long, default_value_t = 20)]
        limit: usize,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Preview or run one queued Xiao Shu action request through local CLI confirmation.
    XiaoShuActionRequestAction {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path and voice cooldown state.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive the queue path and default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Queued request id to inspect or consume.
        #[arg(long)]
        request_id: String,
        /// Operator-facing reason. Defaults to the queued request reason.
        #[arg(long)]
        reason: Option<String>,
        /// Mark the local confirmation as explicitly present.
        #[arg(long)]
        confirm: bool,
        /// Invoke the existing CLI-only voice action after confirmation passes.
        #[arg(long)]
        emit: bool,
        /// Mark the queued request as reviewed without emitting audio.
        #[arg(long)]
        dismiss: bool,
        /// Ignore cooldown state for this invocation.
        #[arg(long)]
        force: bool,
        /// Cooldown seconds to evaluate and record after a successful emit.
        #[arg(long, default_value_t = 300)]
        cooldown_secs: i64,
        /// Optional macOS say voice. Defaults to the policy suggestion or AB_PET_TTS_VOICE.
        #[arg(long)]
        tts_voice: Option<String>,
        /// Optional macOS say rate. Defaults to the policy suggestion or AB_PET_TTS_RATE.
        #[arg(long)]
        tts_rate: Option<u64>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Dry-run Xiao Shu's explicit cortex voice gate without emitting audio.
    CortexVoiceGate {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Override the preview line for this dry-run only.
        #[arg(long)]
        preview_text: Option<String>,
        /// Explicitly enable the dry-run gate for this invocation.
        #[arg(long)]
        enabled: bool,
        /// Ignore cooldown state in the dry-run decision.
        #[arg(long)]
        force: bool,
        /// Cooldown seconds to evaluate. Dry-run does not persist cooldown state.
        #[arg(long, default_value_t = 300)]
        cooldown_secs: i64,
        /// Operator reason required before any future real emit path can pass.
        #[arg(long)]
        reason: Option<String>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
    /// Emit Xiao Shu's cortex voice line through a manual CLI-only gate.
    CortexVoiceEmit {
        /// launchd label. Defaults to com.agentbridge.avatar-cortex.<project>.
        #[arg(long)]
        label: Option<String>,
        /// Heartbeat label used to derive the default snapshot path.
        #[arg(long)]
        heartbeat_label: Option<String>,
        /// Project used to derive default labels.
        #[arg(long)]
        project: Option<String>,
        /// Override cortex snapshot path.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Override the spoken preview line for this CLI-only emit.
        #[arg(long)]
        preview_text: Option<String>,
        /// Explicitly enable the emit gate for this invocation.
        #[arg(long)]
        enabled: bool,
        /// Ignore cooldown state for this invocation.
        #[arg(long)]
        force: bool,
        /// Cooldown seconds to evaluate and record after a successful emit.
        #[arg(long, default_value_t = 300)]
        cooldown_secs: i64,
        /// Operator reason required for real audio emission.
        #[arg(long)]
        reason: Option<String>,
        /// Allow a manual operator to override the default silent cortex policy.
        #[arg(long)]
        allow_policy_override: bool,
        /// Optional macOS say voice. Defaults to AB_PET_TTS_VOICE when set.
        #[arg(long)]
        tts_voice: Option<String>,
        /// Optional macOS say rate. Defaults to AB_PET_TTS_RATE when set.
        #[arg(long)]
        tts_rate: Option<u64>,
        /// Emit raw JSON payload.
        #[arg(long)]
        json: bool,
    },
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
    /// v25 — Agent Shadow Cortex heuristic attention report. Read-only:
    /// scores existing MCP dispatch telemetry, memory query logs, and forum
    /// activity into compact attention signals. Does not write memories, run
    /// tools, or change MCP exposure.
    ShadowCortex {
        /// Look-back window in days.
        #[arg(long, default_value_t = 7)]
        window_days: u32,
        /// Maximum signals to print or emit.
        #[arg(long, default_value_t = 8)]
        max_signals: usize,
        /// Source selector: all | mcp_dispatch | memory | forum | codex.
        /// `codex` narrows MCP dispatch telemetry to source=codex.
        #[arg(long, default_value = "all")]
        source: String,
        /// Write the deterministic replay fixture to this JSON path.
        #[arg(long)]
        fixture_out: Option<PathBuf>,
        /// Build the report from a previously captured replay fixture.
        #[arg(long)]
        fixture_in: Option<PathBuf>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// v25 — Explicit accepted/ignored feedback for shadow-cortex signals.
    /// Appends JSONL under `~/.cache/agent-bridge/shadow-cortex/` by default;
    /// does not write state.db or change live ranking.
    ShadowCortexFeedback {
        #[command(subcommand)]
        op: ShadowCortexFeedbackOp,
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
    /// **ζ-18 (graph hygiene escape hatch)** — Restore a single archived
    /// memory back to `status='active'`. Operator-driven inverse of
    /// ζ-14 `archive-orphan-stubs`. Single-key by design: bulk restore
    /// would re-introduce the noise ζ-14 just retired. Only matches
    /// `status='archived'`; active/superseded/tombstoned rows are
    /// no-ops. CLI mirror of the `memory_restore_archived` MCP tool.
    RestoreArchived {
        /// The memory key to restore. UNIQUE column, so at most one row
        /// flips per invocation.
        key: String,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **β v0 (vision §5 seed-self-evolution scaffolding)** —
    /// Read-only probe of Hebbian clusters: connected components on
    /// the `cofires` + `co_referenced` subgraph. v0 surfaces raw
    /// groups so the operator can inspect thematic coherence; v1 will
    /// layer LLM abstraction to generate seed memories. `coactivation`
    /// edges (the soft trace) are excluded — only crystallised
    /// promotions count toward structure.
    ClusterProbe {
        /// Minimum component size to surface. Default 2 (skip
        /// singletons). Set to 3+ to filter out isolated pairs.
        #[arg(long, default_value_t = 2)]
        min_size: i64,
        /// Cap clusters in the output. Default 20 — enough to scan
        /// in one screen.
        #[arg(long, default_value_t = 20)]
        top_k: i64,
        /// Per-cluster member preview cap. Default 5.
        #[arg(long, default_value_t = 5)]
        preview: i64,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **ζ-19 (graph hygiene retire-end GC)** — Time-based downgrade of
    /// stale `archived` rows to `tombstoned`. Closes the hygiene state
    /// machine: active → ζ-14 → archived → ζ-19 → tombstoned →
    /// purge_tombstones (7d) → DELETE. Tombstoned (not direct DELETE)
    /// preserves the dedupe_key slot so resurrect-by-import/re-save
    /// can't bypass earlier retire decisions.
    TombstoneAgedArchived {
        /// Rows whose updated_at is at least this many days old.
        /// `updated_at` is what ζ-14 bumps at archive time, so this
        /// measures time-spent-in-archived. Default 14 — comfortably
        /// outside the ζ-18 restore window.
        #[arg(long, default_value_t = 14)]
        older_than_days: i64,
        /// Hard cap per run. Default 500, clamp [1, 5000].
        #[arg(long, default_value_t = 500)]
        max_count: i64,
        /// Preview only.
        #[arg(long)]
        dry_run: bool,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **Phase 2.x #6 (sync-window GC)** — Hard-DELETE rows that have been
    /// tombstoned (soft-deleted) for at least `--older-than-days` days.
    /// Tombstone semantics keep deleted rows alive so the deletion
    /// propagates via `agent-bridge sync`; this GC pass cleans them up
    /// once the cross-machine sync window is safely past. CLI mirror of
    /// the `memory_purge_tombstones` MCP tool — adds it to the ζ-10
    /// daily hygiene chain so tombstones don't accumulate indefinitely.
    PurgeTombstones {
        /// Minimum tombstone age in days before a row becomes eligible
        /// for hard-delete. Default 7 = matches the cross-machine sync
        /// cadence (Mac/aio2 weekly catch-up). Set to 0 to purge ALL
        /// tombstones (use only when no peer is offline).
        #[arg(long, default_value_t = 7)]
        older_than_days: i64,
        /// Preview only — print would-be-deleted keys but don't write.
        #[arg(long)]
        dry_run: bool,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **XM v0.5 (cross-machine messaging inbox GC)** — P-XM-7 enforcement.
    /// Hard-DELETE `agent_messages` rows whose effective last-touch
    /// timestamp (`COALESCE(read_at, created_at)`) is older than
    /// `--max-age-days`. CLI mirror / cron entry point for the
    /// `agent_messages_gc` store method (the wet-validation gap noted in
    /// `docs/DESIGN-cross-machine-agent-messaging-2026-05-17.md` §10).
    /// Locked predicate (§4 / §6.5 rule 2): stale-unread 100% cleared,
    /// touched-within-window 0% false-deleted.
    XmGc {
        /// Rows whose effective last-touch (`COALESCE(read_at, created_at)`)
        /// is older than this many days are cleared. Default 30 = the locked
        /// P-XM-7 threshold; do NOT lower (§6.5 rule 2 — fail goes to a
        /// rule-3 reframe, not a threshold drop).
        #[arg(long, default_value_t = 30)]
        max_age_days: i64,
        /// Preview only — report would-clear / would-retain counts without
        /// deleting. Shares the exact match predicate with the real pass.
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
    /// **Codebase call-graph audit** — Aggregate read of the
    /// `codebase_calls` table for a single index root and render a
    /// self-contained HTML report (sibling to `dream promote --html`).
    /// Sections: per-language pills, hot callees, fan-out callers,
    /// orphan-function candidates, fan-out by file. Caveats: callee
    /// matching is alias-blind (use `codebase_callers` MCP tool when
    /// alias resolution matters); orphan detection is best-effort
    /// last-segment matching so trait dispatch / FFI / string-key
    /// dispatch will surface false positives.
    ///
    /// Pure SQL pass — no writes. Run after `agent-bridge codebase
    /// index` (or rely on auto-indexing) to ensure the table is fresh.
    CodebaseReport {
        /// Index root to aggregate. Defaults to the current working
        /// directory — same convention as `codebase_index`.
        #[arg(long)]
        root: Option<PathBuf>,
        /// Cap on hot_callees / hot_callers / orphan_functions /
        /// fan_out_files (each individually). Default 20.
        #[arg(long, default_value_t = 20)]
        top_n: u32,
        /// Write a self-contained HTML report to PATH. Pretty text
        /// remains on stdout when this is set.
        #[arg(long)]
        html: Option<PathBuf>,
        /// Emit raw JSON of `CodebaseCallStats` instead of pretty text.
        /// The HTML still writes if --html is set.
        #[arg(long)]
        json: bool,
    },
    /// **P-ε — Substrate-Readiness Audit.** Read-only aggregate of 7
    /// metric families (M1-M8) covering L1+L2 substrate state: connected
    /// components, edges per type, coactivation growth, retire balance,
    /// edge coverage of active memories, embedding backend distribution,
    /// signal-fidelity Spearman, query-side health. CLI mirror of the
    /// `memory_substrate_audit` MCP tool.
    ///
    /// Pure composition; no schema, no writes. Use as ongoing baseline
    /// before v22 substrate ships; continues to be useful after as
    /// substrate observability surface. See
    /// `docs/DESIGN-P-epsilon-substrate-readiness-audit.md`.
    SubstrateAudit {
        /// Lookback window for M3 recent_active / M4 delta / M8 query
        /// stats. Default 7 days.
        #[arg(long, default_value_t = 7)]
        window_days: u32,
        /// Emit raw JSON of `SubstrateAuditReport` instead of pretty text.
        #[arg(long)]
        json: bool,
        /// **Method A (#204 / #203)** — exclude rows of these kinds from the
        /// M7 signal-fidelity computation. Other metrics (M1–M6, M8) are
        /// computed unchanged on the full active set.
        ///
        /// Use for Day-7 (5/20) P-α audit to filter `kind=feedback` rows
        /// pumped by L5 P3 session-bootstrap preamble (`a3af97a`), yielding
        /// a pure-P-α r_touched reading. Pair with the unfiltered default
        /// run for dual-report mode per thread 6 #204.
        ///
        /// Comma-separated, e.g. `--exclude-kinds feedback,observation`.
        #[arg(long, value_delimiter = ',')]
        exclude_kinds: Vec<String>,
    },
    /// **v22 Phase 3 (A) — substrate ↔ α cofires correlation audit.**
    /// For each memory key with `≥ min_cofires` α `cofires` edges, compute
    /// Spearman rank correlation between
    ///   A = `substrate.neighbors_of(key, k)` (from latest Long snapshot)
    ///   B = `memory_neighbors(key)` filtered to edge_type=cofires
    /// over the union of candidate keys. Reports median Spearman across
    /// qualifying keys — the falsifiability metric for v22 §4 P2
    /// (median ≥ 0.4 → P2 PASS → unlock P3 cold-start probe).
    ///
    /// Pure read; no schema, no writes. Writes JSON snapshot under
    /// `~/.cache/agent-bridge/baselines/substrate-corr-YYYY-MM-DD.json`
    /// when `--json` is set, for Day-7/14/28 trend diff.
    SubstrateCorrAudit {
        /// k for substrate.neighbors_of(key, k). Default 20 per memo §4 P2.
        #[arg(long, default_value_t = 20)]
        k: usize,
        /// Min cofires edge count for a key to qualify. Default 3 per memo.
        #[arg(long, default_value_t = 3)]
        min_cofires: u32,
        /// Override snapshot file path.
        #[arg(long)]
        snapshot_path: Option<PathBuf>,
        /// Emit raw JSON of `SubstrateCorrReport` instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **P-α — Always-Warm Coactivation Tick (manual mirror).** One
    /// sweep of `memory_coactivation` decay with integer half-life:
    /// every row where `last_at + tau ≤ now` gets `count /= 2` and
    /// `last_at += tau`; rows with `count < 1` are DELETEd. The
    /// in-daemon background task (spawned by `Cmd::Daemon`) runs the
    /// same primitive every `tick_secs`; this CLI is for ad-hoc
    /// inspection + cron safety net.
    ///
    /// See `docs/DESIGN-P-alpha-always-warm-coactivation-tick.md`.
    DecayCoactivation {
        /// Half-life in days. Default 7. Clamp [0.5, 30] days.
        #[arg(long, default_value_t = 7.0)]
        tau_days: f64,
        /// Cap iterations per sweep (catches up multi-half-life stale
        /// rows). Default 10. Clamp [1, 100].
        #[arg(long, default_value_t = 10)]
        max_iterations: u32,
        /// Preview only — print decay candidates without writing.
        #[arg(long)]
        dry_run: bool,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **L7 P2 — AGENT.md drift detector.** Scan recent `kind=lesson`
    /// memories (last N days) and compare each to the current
    /// `AGENT.md`. Lessons that aren't already substantially covered
    /// by the durable preamble become `kind=l7_proposed_update`
    /// memories so they surface in the next session's bootstrap as
    /// review candidates. **Never auto-edits AGENT.md** — that stays
    /// user-gated per the L7 design safety rule.
    ///
    /// Roadmap: `docs/AGENT-BRIDGE-CAPABILITY-ROADMAP-2026-05-15.md` §4.
    AgentMdDrift {
        /// Lookback window for the lesson scan. Default 14 days per
        /// roadmap §4 spec.
        #[arg(long, default_value_t = 14)]
        window_days: u32,
        /// Skip writing `l7_proposed_update` memories; print decisions
        /// only. Useful for cron preview / inspection.
        #[arg(long)]
        dry_run: bool,
        /// Override the AGENT.md path. Default
        /// `~/.local/share/agent-bridge/AGENT.md`.
        #[arg(long)]
        agent_md_path: Option<PathBuf>,
        /// Emit raw JSON of `AgentMdDriftReport` instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **L7 P3 — Weekly skill-rating retro.** Lists `kind=lesson`
    /// memories captured in the last N days and reports how many
    /// were consulted post-creation (`access_count > 0`). Designed
    /// to be diffed week-over-week as a JSON time series: feeding
    /// the cross-week Spearman trend that L7-P2 falsifiability needs
    /// ("improving trend over 8 weeks").
    ///
    /// Roadmap: `docs/AGENT-BRIDGE-CAPABILITY-ROADMAP-2026-05-15.md` §4.
    SkillRetro {
        /// Lookback window. Default 7 days (weekly).
        #[arg(long, default_value_t = 7)]
        days: u32,
        /// Emit raw JSON of `SkillRetroReport` (suitable for
        /// `tee ~/.cache/agent-bridge/baselines/skill-retro-YYYY-MM-DD.json`).
        #[arg(long)]
        json: bool,
    },
    /// **§6.5 rule 4 — Monthly gap-coverage audit (CLI surface).** Prints
    /// the 13-gap coverage matrix from the canonical monthly audit doc +
    /// a git-log delta since `--since`. The audit doc remains the source
    /// of truth for status; this CLI surfaces it cheaply. Designed to
    /// compose with `dream weekly` as a Monday-morning health pulse.
    ///
    /// Pure read; no SQL writes. `git log` subprocess only, controlled
    /// arg-list. See `docs/DESIGN-DREAM-GAP-AUDIT-2026-05-16.md`.
    GapAudit {
        /// Lookback for the sectional commit delta. Default 7 days.
        /// Accepts any value `git log --since` understands (e.g.
        /// "7 days ago", "2026-05-09", "2 weeks ago").
        #[arg(long, default_value = "7 days ago")]
        since: String,
        /// Emit raw JSON of `GapAuditReport` for piping into other tools.
        #[arg(long)]
        json: bool,
    },
}

#[derive(Subcommand, Debug)]
enum SubstrateOp {
    /// Print substrate config + (if installed) live stats. Output
    /// shows N / D / outer_dim / step_count / surprise / connection
    /// mean. JSON mode is machine-readable for forum / dream pipeline
    /// integration.
    ///
    /// **Phase 3 (C)**: also reads `substrate.parquet` when available
    /// (installed-substrate's configured path, or `--snapshot-path`
    /// override, or `default_snapshot_path()`) and reports total rows,
    /// hot vs long counts, latest Long/Hot step + ts + fingerprint, and
    /// file size — useful for cross-process determinism / freshness
    /// checks without needing `AB_SUBSTRATE=1` in the inspecting process.
    Stats {
        /// Override snapshot file path. Default: installed substrate's
        /// path, falling back to `default_snapshot_path()`.
        #[arg(long)]
        snapshot_path: Option<PathBuf>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **v22 Phase 3 (B)** — Replay a JSONL event log against a fresh
    /// in-process substrate, write the resulting `substrate.parquet`, and
    /// emit the SHA256 fingerprint of the latest Long row. Tool for v22
    /// §4 P5 (cross-machine determinism) — note that `NeuronGrid` currently
    /// uses `rand::thread_rng()` internally, so fingerprints differ across
    /// machines until the AiOT crate ships a seeded variant; `--seed` is
    /// reserved + logged but not yet effective.
    ///
    /// Event log: one JSON object per line, e.g.
    /// `{"text": "hello", "ts": 1700000000}`. Only `text` is required.
    /// `ts` and `kind` are informational; parse errors / empty lines are
    /// skipped with a warning.
    Replay {
        /// JSONL event log file. Each line `{text, ts?, kind?}`.
        #[arg(long)]
        log: PathBuf,
        /// RNG seed (reserved; logged but not yet effective — pending
        /// upstream AiOT seed_neuron::NeuronGrid::new_seeded support).
        #[arg(long, default_value_t = 0)]
        seed: u64,
        /// Grid size N. Default 256 (memo §3.3).
        #[arg(long, default_value_t = 256)]
        n: usize,
        /// Substrate dim D. Default 192 (memo §3.3 + post 56 PCA).
        #[arg(long, default_value_t = 192)]
        d: usize,
        /// Force HashBackend (deterministic encoder, no ONNX load).
        /// Default false → ONNX (encoder is deterministic on same hw).
        #[arg(long)]
        use_hash: bool,
        /// Output path for substrate.parquet. Default temp file.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit JSON summary instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **v22 Phase 3 (A)** — Query substrate topology: for `--key K`,
    /// return up to `--k` other keys that the substrate's neuron(s)
    /// which fired on K connect to most strongly. Reads the latest Long
    /// snapshot row from `substrate.parquet` (no live install_default
    /// required) so short-lived CLI invocations get useful answers.
    Neighbors {
        /// Memory key to look up (must have been perceived by the
        /// substrate process that wrote the snapshot file).
        #[arg(long)]
        key: String,
        /// Max number of distinct neighbor keys to return.
        #[arg(long, default_value_t = 20)]
        k: usize,
        /// Override file path (default: `$HOME/.local/share/agent-bridge/substrate.parquet`).
        #[arg(long)]
        path: Option<PathBuf>,
        /// Emit raw JSON `[{"key":..., "score":...}]` for scripts.
        #[arg(long)]
        json: bool,
    },
    /// **Phase 2.2 read side** — Read rows from `substrate.parquet`
    /// without touching the in-process substrate (no install_default
    /// required). Useful for cross-process inspection, forum/dream
    /// pipeline, and G4 fingerprint comparisons across machines.
    Snapshot {
        /// Override file path (default: `$HOME/.local/share/agent-bridge/substrate.parquet`).
        #[arg(long)]
        path: Option<PathBuf>,
        /// Number of trailing rows to show (0 = all). Default 5.
        #[arg(long, default_value_t = 5)]
        limit: usize,
        /// Filter by tier (`hot` or `long`).
        #[arg(long)]
        tier: Option<String>,
        /// Print only the SHA256 fingerprint per row (one per line) —
        /// for cross-machine determinism compare (G4).
        #[arg(long)]
        fingerprint_only: bool,
        /// Emit JSON summary (omits bulk per-neuron arrays).
        #[arg(long)]
        json: bool,
    },
}

#[derive(Subcommand, Debug)]
enum BioCortexOp {
    /// Run a read-only BioCortex shadow adapter and print an AB digest.
    ShadowDigest {
        /// Local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling
        /// checkout paths, then /tmp/biocortex-rs-ab-eval.
        #[arg(long)]
        checkout: Option<PathBuf>,
        /// Adapter benchmark: scaled_morphology, temporal_credit, minimal_morphology, or ab_fixture_projection.
        #[arg(long, default_value = "scaled_morphology")]
        benchmark: String,
        /// External adapter timeout in milliseconds.
        #[arg(long, default_value_t = 120_000)]
        timeout_ms: u64,
        /// Include raw stdout/stderr from the external adapter in JSON output.
        #[arg(long)]
        include_raw: bool,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Compare an AB shadow-cortex replay fixture with a BioCortex shadow digest.
    ///
    /// This is side-by-side evidence only: BioCortex does not yet consume AB
    /// events, and AB retrieval vectors remain unchanged.
    ReplayCompare {
        /// Look-back window in days when collecting a live AB fixture.
        #[arg(long, default_value_t = 7)]
        window_days: u32,
        /// Source selector: all | mcp_dispatch | memory | forum | codex.
        #[arg(long, default_value = "all")]
        source: String,
        /// Write the deterministic AB replay fixture to this JSON path.
        #[arg(long)]
        fixture_out: Option<PathBuf>,
        /// Build the comparison from a previously captured replay fixture.
        #[arg(long)]
        fixture_in: Option<PathBuf>,
        /// Local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling
        /// checkout paths, then /tmp/biocortex-rs-ab-eval.
        #[arg(long)]
        checkout: Option<PathBuf>,
        /// Adapter benchmark: ab_fixture_projection, scaled_morphology, temporal_credit, or minimal_morphology.
        #[arg(long, default_value = "ab_fixture_projection")]
        benchmark: String,
        /// External adapter timeout in milliseconds.
        #[arg(long, default_value_t = 120_000)]
        timeout_ms: u64,
        /// Include raw stdout/stderr from the external adapter in JSON output.
        #[arg(long)]
        include_raw: bool,
        /// Include every projected AB event in JSON output instead of only a preview.
        #[arg(long)]
        include_events: bool,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Run a review-only BioCortex retrieval side-signal report.
    ///
    /// This command is feature-gated and runtime-gated. It never changes
    /// `memory_search` order, registers an embedding backend, or writes memory.
    #[cfg(feature = "biocortex-retrieval-shadow")]
    RetrievalShadow {
        /// Query text to evaluate. May also be provided in --input-json.
        #[arg(long)]
        query: Option<String>,
        /// Candidate JSON file: either `{"query": "...", "candidates": [...]}` or a candidate array.
        #[arg(long)]
        input_json: Option<PathBuf>,
        /// Candidate key/content JSON array file, used when --input-json is an array.
        #[arg(long)]
        candidates_json: Option<PathBuf>,
        /// Optional expected key for labeled review/regression reporting.
        #[arg(long)]
        expected_key: Option<String>,
        /// Local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling
        /// checkout paths, then /tmp/biocortex-rs-ab-eval.
        #[arg(long)]
        checkout: Option<PathBuf>,
        /// External side-signal adapter timeout in milliseconds.
        #[arg(long, default_value_t = 120_000)]
        timeout_ms: u64,
        /// Include raw stdout/stderr from the external adapter in JSON output.
        #[arg(long)]
        include_raw: bool,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Report the feature/runtime/per-call opt-in gate and audit shape.
    ///
    /// This is read-only observability. It does not call `memory_search`, run
    /// BioCortex, include raw memory keys/content, or change retrieval order.
    RetrievalOptInStatus {
        /// Retrieval mode under review. Only fts is authorized for opt-in work.
        #[arg(long, default_value = "fts")]
        mode: String,
        /// Simulate the explicit per-call opt-in bit.
        #[arg(long)]
        per_call_opt_in: bool,
        /// Optional query text. The output includes only a hash.
        #[arg(long)]
        query: Option<String>,
        /// Optional baseline candidate key. May be repeated; output includes only count/hash.
        #[arg(long = "baseline-key")]
        baseline_keys: Vec<String>,
        /// Optional side-signal status label for audit-shape previews.
        #[arg(long)]
        side_signal_status: Option<String>,
        /// Optional fallback reason override for audit-shape previews.
        #[arg(long)]
        fallback_reason: Option<String>,
        /// Optional latency in milliseconds for audit-shape previews.
        #[arg(long)]
        latency_ms: Option<f64>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Plan the future FTS opt-in ordering path without executing it.
    ///
    /// This is read-only observability. It does not call `memory_search`, run
    /// BioCortex, include raw memory keys/content, or change retrieval order.
    RetrievalOptInDryRun {
        /// Retrieval mode under review. Only fts is authorized for opt-in work.
        #[arg(long, default_value = "fts")]
        mode: String,
        /// Simulate the explicit per-call opt-in bit.
        #[arg(long)]
        per_call_opt_in: bool,
        /// Optional query text. The output includes only a hash.
        #[arg(long)]
        query: Option<String>,
        /// Optional baseline candidate key. May be repeated; output includes only count/hash.
        #[arg(long = "baseline-key")]
        baseline_keys: Vec<String>,
        /// Whether the baseline memory_search result already exists for this dry run.
        #[arg(long, default_value_t = true)]
        baseline_completed: bool,
        /// Future side-signal adapter timeout in milliseconds.
        #[arg(long, default_value_t = 120_000)]
        timeout_ms: u64,
        /// Future minimum side-signal coverage threshold.
        #[arg(long, default_value_t = 0.8)]
        coverage_threshold: f64,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Convert a dry-run plan into a read-only human/agent review packet.
    ///
    /// This consumes only safe summary fields from a dry-run JSON file. It does
    /// not include the raw dry-run payload, approve anything, run BioCortex,
    /// call `memory_search`, or change retrieval order.
    RetrievalOptInReviewPacket {
        /// JSON file produced by `retrieval-opt-in-dry-run --json`.
        #[arg(long = "dry-run-json")]
        dry_run_json: PathBuf,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the review packet.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the review packet.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Build a protected execution preflight packet from a review packet.
    ///
    /// This is a contract surface only. It consumes safe review-packet summary
    /// fields, rebuilds the store contract, and still returns baseline. It
    /// does not run BioCortex, call `memory_search`, or change retrieval order.
    RetrievalOptInExecutionPacket {
        /// JSON file produced by `retrieval-opt-in-review-packet --json`.
        #[arg(long = "review-packet-json")]
        review_packet_json: PathBuf,
        /// Simulate the explicit per-call opt-in bit for the store contract.
        #[arg(long)]
        per_call_opt_in: bool,
        /// Optional execution attempt id for audit correlation.
        #[arg(long)]
        attempt_id: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Run a baseline-preserving opt-in side-signal trial from an execution packet.
    ///
    /// This consumes an execution packet and explicit candidates. It may run
    /// the external BioCortex side-signal adapter when opt-in gates pass, but
    /// it never calls `memory_search` or changes returned retrieval order.
    RetrievalOptInRuntimeTrial {
        /// JSON file produced by `retrieval-opt-in-execution-packet --json`.
        #[arg(long = "execution-packet-json")]
        execution_packet_json: PathBuf,
        /// Query text to evaluate. May also be provided in --input-json.
        #[arg(long)]
        query: Option<String>,
        /// Candidate JSON file: either `{"query": "...", "candidates": [...]}` or a candidate array.
        #[arg(long)]
        input_json: Option<PathBuf>,
        /// Candidate key/content JSON array file, used when --input-json is absent.
        #[arg(long)]
        candidates_json: Option<PathBuf>,
        /// Optional expected key for labeled review/regression reporting.
        #[arg(long)]
        expected_key: Option<String>,
        /// Local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling
        /// checkout paths, then /tmp/biocortex-rs-ab-eval.
        #[arg(long)]
        checkout: Option<PathBuf>,
        /// External side-signal adapter timeout in milliseconds.
        #[arg(long, default_value_t = 120_000)]
        timeout_ms: u64,
        /// Minimum side-signal coverage threshold for an advisory result.
        #[arg(long, default_value_t = 0.8)]
        coverage_threshold: f64,
        /// Optional runtime trial attempt id for audit correlation.
        #[arg(long)]
        attempt_id: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Convert a runtime trial into a read-only post-implementation review packet.
    ///
    /// This consumes only safe summary fields from a runtime-trial JSON file.
    /// It does not approve runtime influence, run BioCortex, call
    /// `memory_search`, or change retrieval order.
    RetrievalOptInRuntimeTrialReviewPacket {
        /// JSON file produced by `retrieval-opt-in-runtime-trial --json`.
        #[arg(long = "runtime-trial-json")]
        runtime_trial_json: PathBuf,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the review packet.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the review packet.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Compare baseline order against the BioCortex advisory order.
    ///
    /// This consumes a runtime-trial or runtime-trial-review JSON file and emits
    /// hash-only order-diff evidence. It does not approve runtime influence,
    /// run BioCortex, call `memory_search`, or change retrieval order.
    RetrievalOptInOrderDiffPacket {
        /// JSON file produced by runtime-trial or runtime-trial-review-packet.
        #[arg(long = "source-json")]
        source_json: PathBuf,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the review packet.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the review packet.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Compute redacted top-k overlap and rank movement evidence.
    ///
    /// This consumes a runtime-trial or runtime-trial-review JSON file and
    /// emits rank metrics from key_hash rows only. It does not approve runtime
    /// influence, run BioCortex, call `memory_search`, or change retrieval
    /// order.
    RetrievalOptInRedactedOrderArtifact {
        /// JSON file produced by runtime-trial or runtime-trial-review-packet.
        #[arg(long = "source-json")]
        source_json: PathBuf,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the artifact.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the artifact.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Consume the opt-in authorization decision as an implementation-only gate.
    ///
    /// This consumes safe summary fields from the authorization request and
    /// human decision records. It does not approve runtime adapter influence,
    /// call `memory_search`, run BioCortex, or change retrieval order.
    RetrievalOptInAuthorizationDecisionPacket {
        /// JSON file produced by `prepare-biocortex-retrieval-opt-in-authorization-request.sh`.
        #[arg(long = "authorization-request-json")]
        authorization_request_json: PathBuf,
        /// JSON decision fixture for the human opt-in implementation authorization.
        #[arg(long = "authorization-decision-json")]
        authorization_decision_json: PathBuf,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the decision packet.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the decision packet.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Check implementation-only evidence before a separate runtime-influence review.
    ///
    /// This consumes the authorization decision packet and opt-in plan fixture
    /// summaries. It prepares a post-implementation review gate only; it does
    /// not approve runtime adapter influence, call `memory_search`, run
    /// BioCortex, or change retrieval order.
    RetrievalOptInPostImplementationReviewGate {
        /// JSON file produced by retrieval-opt-in-authorization-decision-packet.
        #[arg(long = "authorization-decision-packet-json")]
        authorization_decision_packet_json: PathBuf,
        /// Machine-readable opt-in experiment plan fixture.
        #[arg(long = "opt-in-plan-json")]
        opt_in_plan_json: PathBuf,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the review gate.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the review gate.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Prepare a human runtime-influence review request without approval.
    ///
    /// This consumes the post-implementation review gate, redacted order
    /// artifact summary, optional redacted evidence aggregate, and optional
    /// post-runtime evidence summary. It requests a separate human review for
    /// explicit opt-in FTS runtime influence only; it does not approve runtime
    /// adapter influence, call `memory_search`, run BioCortex, or change
    /// retrieval order.
    RetrievalOptInRuntimeInfluenceReviewRequest {
        /// JSON file produced by retrieval-opt-in-post-implementation-review-gate.
        #[arg(long = "post-implementation-review-gate-json")]
        post_implementation_review_gate_json: PathBuf,
        /// JSON file produced by retrieval-opt-in-redacted-order-artifact.
        #[arg(long = "redacted-order-artifact-json")]
        redacted_order_artifact_json: PathBuf,
        /// Optional JSON file produced by retrieval-opt-in-redacted-evidence-aggregate.
        #[arg(long = "redacted-evidence-aggregate-json")]
        redacted_evidence_aggregate_json: Option<PathBuf>,
        /// Optional JSON file produced by retrieval-opt-in-evidence-summary.
        #[arg(long = "evidence-summary-json")]
        evidence_summary_json: Option<PathBuf>,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the review request.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the review request.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Consume a human runtime-influence review decision without mutating state.
    ///
    /// This consumes a runtime-influence review request plus a separate human
    /// decision record. It can authorize implementation of explicit opt-in FTS
    /// runtime influence only; it does not call `memory_search`, run BioCortex,
    /// connect ordering behavior, or change retrieval order.
    RetrievalOptInRuntimeInfluenceDecisionPacket {
        /// JSON file produced by retrieval-opt-in-runtime-influence-review-request.
        #[arg(long = "runtime-influence-review-request-json")]
        runtime_influence_review_request_json: PathBuf,
        /// JSON decision record for the human runtime-influence review.
        #[arg(long = "runtime-influence-decision-json")]
        runtime_influence_decision_json: PathBuf,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the decision packet.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the decision packet.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Run a protected live store trial from a runtime-influence decision packet.
    ///
    /// This opens the AB store, calls baseline `memory_search`, runs BioCortex
    /// only when explicit runtime-influence gates authorize it, and feeds
    /// sanitized side-signal rows into the protected opt-in store wrapper.
    /// Output is redacted to hashes, counts, rank rows, and contracts.
    RetrievalOptInStoreTrial {
        /// JSON file produced by retrieval-opt-in-runtime-influence-decision-packet.
        #[arg(long = "runtime-influence-decision-packet-json")]
        runtime_influence_decision_packet_json: PathBuf,
        /// FTS query to evaluate against the AB store. Output includes only a hash.
        #[arg(long)]
        query: String,
        /// Optional tag filter forwarded to baseline memory_search. May be repeated.
        #[arg(long = "tag")]
        tags_any: Vec<String>,
        /// Maximum baseline candidates to retrieve from store memory_search.
        #[arg(long, default_value_t = 10)]
        limit: u32,
        /// Retrieval mode under review. Only fts is authorized for runtime influence.
        #[arg(long, default_value = "fts")]
        mode: String,
        /// Required explicit per-call opt-in bit.
        #[arg(long)]
        per_call_opt_in: bool,
        /// Local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling
        /// checkout paths, then /tmp/biocortex-rs-ab-eval.
        #[arg(long)]
        checkout: Option<PathBuf>,
        /// External side-signal adapter timeout in milliseconds.
        #[arg(long, default_value_t = 120_000)]
        timeout_ms: u64,
        /// Minimum matched side-signal coverage before experimental order is allowed.
        #[arg(long, default_value_t = 0.8)]
        coverage_threshold: f64,
        /// Blend weight passed to the protected store wrapper.
        #[arg(long, default_value_t = 0.8)]
        blend_alpha: f32,
        /// Optional store-trial attempt id for audit correlation.
        #[arg(long)]
        attempt_id: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Run a transition-gated protected live store trial.
    ///
    /// This is the runtime entry variant: it consumes a
    /// retrieval-opt-in-runtime-transition-gate packet and refuses to call
    /// `memory_search` unless that gate allows the explicit opt-in FTS
    /// transition. Once the gate passes it delegates to the existing protected
    /// store trial and returns only redacted summaries.
    RetrievalOptInGatedStoreTrial {
        /// JSON file produced by retrieval-opt-in-runtime-transition-gate.
        #[arg(long = "runtime-transition-gate-json")]
        runtime_transition_gate_json: PathBuf,
        /// JSON file produced by retrieval-opt-in-runtime-influence-decision-packet.
        #[arg(long = "runtime-influence-decision-packet-json")]
        runtime_influence_decision_packet_json: PathBuf,
        /// FTS query to evaluate against the AB store. Output includes only a hash.
        #[arg(long)]
        query: String,
        /// Optional tag filter forwarded to baseline memory_search. May be repeated.
        #[arg(long = "tag")]
        tags_any: Vec<String>,
        /// Maximum baseline candidates to retrieve from store memory_search.
        #[arg(long, default_value_t = 10)]
        limit: u32,
        /// Retrieval mode under review. Only fts is authorized for runtime influence.
        #[arg(long, default_value = "fts")]
        mode: String,
        /// Required explicit per-call opt-in bit.
        #[arg(long)]
        per_call_opt_in: bool,
        /// Local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling
        /// checkout paths, then /tmp/biocortex-rs-ab-eval.
        #[arg(long)]
        checkout: Option<PathBuf>,
        /// External side-signal adapter timeout in milliseconds.
        #[arg(long, default_value_t = 120_000)]
        timeout_ms: u64,
        /// Minimum matched side-signal coverage before experimental order is allowed.
        #[arg(long, default_value_t = 0.8)]
        coverage_threshold: f64,
        /// Blend weight passed to the protected store wrapper.
        #[arg(long, default_value_t = 0.8)]
        blend_alpha: f32,
        /// Optional gated store-trial attempt id for audit correlation.
        #[arg(long)]
        attempt_id: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Run redacted batch diagnostics over protected live store trials.
    ///
    /// Each query reuses the same runtime-influence decision packet and
    /// protected store-trial gate. Output includes only query hashes, order
    /// hashes, counts, coverage, latency, and movement classes.
    RetrievalOptInBatchDiagnostics {
        /// JSON file produced by retrieval-opt-in-runtime-influence-decision-packet.
        #[arg(long = "runtime-influence-decision-packet-json")]
        runtime_influence_decision_packet_json: PathBuf,
        /// FTS query to evaluate against the AB store. May be repeated.
        #[arg(long = "query")]
        queries: Vec<String>,
        /// Optional bucket label for the corresponding --query. May be repeated.
        #[arg(long = "query-class")]
        query_classes: Vec<String>,
        /// JSON file containing query cases. Accepts a bare array or an object
        /// with `query_cases` / `queries`.
        #[arg(long = "query-cases-json")]
        query_cases_json: Option<PathBuf>,
        /// Optional tag filter forwarded to baseline memory_search. May be repeated.
        #[arg(long = "tag")]
        tags_any: Vec<String>,
        /// Maximum baseline candidates to retrieve from store memory_search.
        #[arg(long, default_value_t = 10)]
        limit: u32,
        /// Retrieval mode under review. Only fts is authorized for runtime influence.
        #[arg(long, default_value = "fts")]
        mode: String,
        /// Required explicit per-call opt-in bit.
        #[arg(long)]
        per_call_opt_in: bool,
        /// Local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling
        /// checkout paths, then /tmp/biocortex-rs-ab-eval.
        #[arg(long)]
        checkout: Option<PathBuf>,
        /// External side-signal adapter timeout in milliseconds, per query.
        #[arg(long, default_value_t = 120_000)]
        timeout_ms: u64,
        /// Minimum matched side-signal coverage before experimental order is allowed.
        #[arg(long, default_value_t = 0.8)]
        coverage_threshold: f64,
        /// Blend weight passed to the protected store wrapper.
        #[arg(long, default_value_t = 0.8)]
        blend_alpha: f32,
        /// Optional batch attempt id for audit correlation.
        #[arg(long)]
        attempt_id: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Run transition-gated redacted batch diagnostics over live store trials.
    ///
    /// Each query consumes the same runtime-transition gate before it may call
    /// the protected store-trial path. Blocked gates return only redacted
    /// transition blockers and do not call `memory_search` or BioCortex.
    RetrievalOptInGatedBatchDiagnostics {
        /// JSON file produced by retrieval-opt-in-runtime-transition-gate.
        #[arg(long = "runtime-transition-gate-json")]
        runtime_transition_gate_json: PathBuf,
        /// JSON file produced by retrieval-opt-in-runtime-influence-decision-packet.
        #[arg(long = "runtime-influence-decision-packet-json")]
        runtime_influence_decision_packet_json: PathBuf,
        /// FTS query to evaluate against the AB store. May be repeated.
        #[arg(long = "query")]
        queries: Vec<String>,
        /// Optional bucket label for the corresponding --query. May be repeated.
        #[arg(long = "query-class")]
        query_classes: Vec<String>,
        /// JSON file containing query cases. Accepts a bare array or an object
        /// with `query_cases` / `queries`.
        #[arg(long = "query-cases-json")]
        query_cases_json: Option<PathBuf>,
        /// Optional tag filter forwarded to baseline memory_search. May be repeated.
        #[arg(long = "tag")]
        tags_any: Vec<String>,
        /// Maximum baseline candidates to retrieve from store memory_search.
        #[arg(long, default_value_t = 10)]
        limit: u32,
        /// Retrieval mode under review. Only fts is authorized for runtime influence.
        #[arg(long, default_value = "fts")]
        mode: String,
        /// Required explicit per-call opt-in bit.
        #[arg(long)]
        per_call_opt_in: bool,
        /// Local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling
        /// checkout paths, then /tmp/biocortex-rs-ab-eval.
        #[arg(long)]
        checkout: Option<PathBuf>,
        /// External side-signal adapter timeout in milliseconds, per query.
        #[arg(long, default_value_t = 120_000)]
        timeout_ms: u64,
        /// Minimum matched side-signal coverage before experimental order is allowed.
        #[arg(long, default_value_t = 0.8)]
        coverage_threshold: f64,
        /// Blend weight passed to the protected store wrapper.
        #[arg(long, default_value_t = 0.8)]
        blend_alpha: f32,
        /// Optional gated batch attempt id for audit correlation.
        #[arg(long)]
        attempt_id: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Summarize controlled explicit opt-in runtime readiness.
    ///
    /// This consumes only safe summaries from an aggregate-backed
    /// runtime-influence decision packet, one store trial, and one legacy or
    /// transition-gated batch diagnostics run. It reports operator readiness without calling
    /// `memory_search`, running BioCortex, writing approval state, or changing
    /// default retrieval order.
    RetrievalOptInRuntimeReadinessPacket {
        /// JSON file produced by retrieval-opt-in-runtime-influence-decision-packet.
        #[arg(long = "runtime-influence-decision-packet-json")]
        runtime_influence_decision_packet_json: PathBuf,
        /// JSON file produced by retrieval-opt-in-store-trial.
        #[arg(long = "store-trial-json")]
        store_trial_json: PathBuf,
        /// JSON file produced by retrieval-opt-in-batch-diagnostics or
        /// retrieval-opt-in-gated-batch-diagnostics.
        #[arg(long = "batch-diagnostics-json")]
        batch_diagnostics_json: PathBuf,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the readiness packet.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the readiness packet.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Gate a requested live transition on a runtime-readiness packet.
    ///
    /// This is still a read-only packet. It consumes the runtime readiness
    /// packet and checks that the requested transition is explicit opt-in FTS,
    /// per-call opted in, and not operator-disabled. It does not call
    /// `memory_search`, run BioCortex, write approval, or alter default order.
    RetrievalOptInRuntimeTransitionGate {
        /// JSON file produced by retrieval-opt-in-runtime-readiness-packet.
        #[arg(long = "runtime-readiness-packet-json")]
        runtime_readiness_packet_json: PathBuf,
        /// Retrieval mode under review. Only fts is allowed.
        #[arg(long, default_value = "fts")]
        mode: String,
        /// Required explicit per-call opt-in bit.
        #[arg(long)]
        per_call_opt_in: bool,
        /// Treat the operator disable switch as active for this gate.
        #[arg(long)]
        operator_disabled: bool,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the transition gate.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the transition gate.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Seed a non-production store fixture and run redacted batch diagnostics.
    ///
    /// This is a controlled order-movement probe. It requires an explicit
    /// non-production store write flag and AGENT_BRIDGE_DB override, writes only
    /// fixture memories into that store, then runs the existing protected batch
    /// diagnostics surface. Output remains redacted.
    RetrievalOptInControlledOrderFixture {
        /// JSON file produced by retrieval-opt-in-runtime-influence-decision-packet.
        #[arg(long = "runtime-influence-decision-packet-json")]
        runtime_influence_decision_packet_json: PathBuf,
        /// Controlled fixture JSON containing memory_records and query_cases.
        #[arg(long = "fixture-json")]
        fixture_json: PathBuf,
        /// Required acknowledgement that the selected AGENT_BRIDGE_DB is non-production.
        #[arg(long)]
        allow_non_production_store_writes: bool,
        /// Optional tag filter forwarded to baseline memory_search. May be repeated.
        #[arg(long = "tag")]
        tags_any: Vec<String>,
        /// Maximum baseline candidates to retrieve from store memory_search.
        #[arg(long, default_value_t = 10)]
        limit: u32,
        /// Retrieval mode under review. Only fts is authorized for runtime influence.
        #[arg(long, default_value = "fts")]
        mode: String,
        /// Required explicit per-call opt-in bit.
        #[arg(long)]
        per_call_opt_in: bool,
        /// Local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling
        /// checkout paths, then /tmp/biocortex-rs-ab-eval.
        #[arg(long)]
        checkout: Option<PathBuf>,
        /// External side-signal adapter timeout in milliseconds, per query.
        #[arg(long, default_value_t = 120_000)]
        timeout_ms: u64,
        /// Minimum matched side-signal coverage before experimental order is allowed.
        #[arg(long, default_value_t = 0.8)]
        coverage_threshold: f64,
        /// Blend weight passed to the protected store wrapper.
        #[arg(long, default_value_t = 0.8)]
        blend_alpha: f32,
        /// Optional controlled fixture attempt id for audit correlation.
        #[arg(long)]
        attempt_id: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Summarize redacted post-runtime evidence without approving influence.
    ///
    /// This consumes batch diagnostics and a controlled order fixture run,
    /// reports only schema/count/safety conclusions, and never calls
    /// `memory_search`, runs BioCortex, writes approval state, or changes
    /// retrieval order.
    RetrievalOptInEvidenceSummary {
        /// JSON file produced by retrieval-opt-in-batch-diagnostics.
        #[arg(long = "batch-diagnostics-json")]
        batch_diagnostics_json: PathBuf,
        /// JSON file produced by retrieval-opt-in-controlled-order-fixture.
        #[arg(long = "controlled-order-fixture-run-json")]
        controlled_order_fixture_run_json: PathBuf,
        /// Optional JSON file produced by retrieval-opt-in-runtime-readiness-packet.
        #[arg(long = "runtime-readiness-packet-json")]
        runtime_readiness_packet_json: Option<PathBuf>,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the evidence summary.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the evidence summary.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Aggregate redacted movement and expanded coverage evidence.
    ///
    /// This consumes two redacted controlled fixture runs: one canonical
    /// movement run and one expanded coverage/alignment run. It reports only
    /// schema/count/safety conclusions, and never calls `memory_search`, runs
    /// BioCortex, writes approval state, or changes retrieval order.
    RetrievalOptInRedactedEvidenceAggregate {
        /// JSON file produced by retrieval-opt-in-controlled-order-fixture that demonstrates movement.
        #[arg(long = "movement-fixture-run-json")]
        movement_fixture_run_json: PathBuf,
        /// JSON file produced by retrieval-opt-in-controlled-order-fixture that demonstrates expanded coverage.
        #[arg(long = "coverage-fixture-run-json")]
        coverage_fixture_run_json: PathBuf,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the aggregate.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the aggregate.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Preview the future runtime approval packet without approving anything.
    ///
    /// This is a review-preparation packet only. It never runs BioCortex,
    /// changes retrieval order, writes approval state, or mutates memory.
    RetrievalApprovalPacket {
        /// Target host for the future review evidence.
        #[arg(long)]
        target_host: Option<String>,
        /// Source branch/ref under review.
        #[arg(long)]
        branch: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Human reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Agent identity providing the technical attestation.
        #[arg(long)]
        agent_attestor: Option<String>,
        /// Agent technical attestation decision, such as technical_review_pending.
        #[arg(long)]
        agent_attestation_decision: Option<String>,
        /// Agent technical attestation summary.
        #[arg(long)]
        agent_attestation_summary: Option<String>,
        /// Human authorization scope. Use none until a human explicitly grants scope.
        #[arg(long)]
        human_authorization_scope: Option<String>,
        /// Verification bundle status, normally "pass".
        #[arg(long)]
        verification_status: Option<String>,
        /// Verification capture timestamp.
        #[arg(long)]
        verification_captured_at: Option<String>,
        /// Current corpus gate status.
        #[arg(long)]
        current_gate_status: Option<String>,
        /// Hard holdout corpus gate status.
        #[arg(long)]
        hard_holdout_gate_status: Option<String>,
        /// Measured p95 side-signal latency for five candidates.
        #[arg(long)]
        side_signal_p95_ms_for_5_candidates: Option<String>,
        /// Measured added latency on the default memory_search path.
        #[arg(long)]
        default_memory_search_added_latency_ms: Option<String>,
        /// Exact code call site where a future ordering change would happen.
        #[arg(long)]
        exact_call_site: Option<String>,
        /// Fail-open behavior when BioCortex is absent, slow, or errors.
        #[arg(long)]
        fail_open_behavior: Option<String>,
        /// Rollback command for the proposed runtime adapter.
        #[arg(long)]
        rollback_command: Option<String>,
        /// Forum decision post id linking the evidence packet.
        #[arg(long)]
        forum_decision_post_id: Option<String>,
        /// Memory key linking the evidence packet.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
}

#[derive(Subcommand, Debug)]
enum ShadowCortexFeedbackOp {
    /// Append one accepted/ignored decision to feedback.jsonl.
    Record {
        /// Human/agent review decision for the signal.
        #[arg(long, value_enum)]
        decision: ShadowCortexFeedbackDecision,
        /// Stable signal id from report context; source_event_id is fine for v0.
        #[arg(long)]
        signal_id: String,
        /// Optional source event id; repeat for multi-event signals.
        #[arg(long = "source-event-id")]
        source_event_ids: Vec<String>,
        /// Actor writing the review.
        #[arg(long, default_value = "codex-desktop-gpt-5.5")]
        actor: String,
        /// Short review note.
        #[arg(long)]
        note: Option<String>,
        /// Override feedback log path.
        #[arg(long)]
        path: Option<PathBuf>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Print recent shadow-cortex feedback decisions.
    List {
        /// Maximum recent records to print.
        #[arg(long, default_value_t = 20)]
        limit: usize,
        /// Override feedback log path.
        #[arg(long)]
        path: Option<PathBuf>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
}

#[derive(Clone, Copy, Debug, ValueEnum)]
enum AvatarReviewOutcome {
    Approved,
    #[value(name = "keep_pending", alias = "keep-pending")]
    KeepPending,
    #[value(name = "request_revision", alias = "request-revision")]
    RequestRevision,
    Rejected,
}

impl AvatarReviewOutcome {
    fn as_str(self) -> &'static str {
        match self {
            Self::Approved => "approved",
            Self::KeepPending => "keep_pending",
            Self::RequestRevision => "request_revision",
            Self::Rejected => "rejected",
        }
    }
}

#[derive(Clone, Copy, Debug, ValueEnum)]
enum ShadowCortexFeedbackDecision {
    Accepted,
    Ignored,
}

impl ShadowCortexFeedbackDecision {
    fn as_str(self) -> &'static str {
        match self {
            Self::Accepted => "accepted",
            Self::Ignored => "ignored",
        }
    }
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
    /// Walks all `kind=skill` records, collects distinct remote `src:` values,
    /// and re-runs indexing for each. Existing `git_origin` / `git_branch`
    /// provenance is preserved, so branch-sourced records refresh the same
    /// branch instead of drifting back to a default branch. Local-path sources
    /// are skipped — re-run `index <path>` manually. Suitable for cron / Stop
    /// hook.
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
        /// Print the refresh plan without cloning repos, writing memories, or pruning.
        #[arg(long)]
        dry_run: bool,
        /// Emit machine-readable JSON for `--dry-run`.
        #[arg(long)]
        json: bool,
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
    /// Route a task to a few indexed skills without exposing the whole catalog.
    ///
    /// Semantic-first retrieval over `kind=skill`, then prints a compact
    /// context-loading plan with lint/risk/source metadata and `skills show`
    /// follow-up commands. This is the intended runtime pair for a curated
    /// Codex active-skill set: keep the prompt small, retrieve only the
    /// relevant procedures for the current task.
    Route {
        /// Task description in natural language.
        query: String,
        /// Maximum skills to recommend.
        #[arg(long, default_value_t = 5)]
        limit: usize,
        /// Include the first N chars of each skill body. 0 = metadata only.
        #[arg(long, default_value_t = 0)]
        body_chars: usize,
        /// Emit machine-readable JSON for automation.
        #[arg(long)]
        json: bool,
    },
    /// Record whether a routed skill was used/helpful, and link that feedback into memory.
    Feedback {
        /// Skill memory key, usually copied from `skills route` / `skills_route`.
        skill_key: String,
        /// Original task/query that caused this skill to be considered.
        #[arg(long)]
        query: String,
        /// Feedback outcome: used, helpful, not-helpful, or ignored.
        #[arg(long, default_value = "used")]
        outcome: String,
        /// Optional short note about why the skill helped or failed.
        #[arg(long)]
        note: Option<String>,
        /// Related memory keys to connect as task context. Repeatable.
        #[arg(long = "related-key")]
        related_keys: Vec<String>,
        /// Emit machine-readable JSON for automation.
        #[arg(long)]
        json: bool,
    },
    /// List indexed skills, most-recent first.
    List {
        #[arg(long, default_value_t = 50)]
        limit: usize,
    },
    /// Summarize indexed skill sources by repo, branch, lint, and risk.
    Sources {
        /// Emit machine-readable JSON for automation.
        #[arg(long)]
        json: bool,
        /// Maximum sources to print. 0 = all.
        #[arg(long, default_value_t = 100)]
        limit: usize,
    },
    /// Batch-audit indexed skills by provenance, lint, and operational risk.
    Audit {
        /// Emit machine-readable JSON for automation.
        #[arg(long)]
        json: bool,
        /// Filter to one source id, for example `OpenBMB/MiniCPM`.
        #[arg(long)]
        src: Option<String>,
        /// Require a risk tag, without or with `risk:` prefix. Repeatable.
        #[arg(long)]
        risk: Vec<String>,
        /// Filter by lint class: clean, warn, danger, or an exact tag value.
        #[arg(long)]
        lint: Option<String>,
        /// Filter by vendor class, for example community or vendor-curated.
        #[arg(long)]
        vendor: Option<String>,
        /// Maximum records to print in the `items`/record section. 0 = all.
        #[arg(long, default_value_t = 100)]
        limit: usize,
    },
    /// Print one skill's body and metadata (use a key from `list` / `search`).
    Show {
        key: String,
        /// Emit machine-readable JSON for automation.
        #[arg(long)]
        json: bool,
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
        /// Preview source, destination, lint, and risk gates without writing files.
        #[arg(long)]
        dry_run: bool,
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
    /// Install for Codex CLI — MCP config only, no desktop lifecycle hooks.
    CodexCli,
    /// Install for Codex IDE hosts — MCP config plus IDE bridge marker, no desktop hooks.
    CodexIde,
    /// Install for Gemini CLI — registers MCP in ~/.gemini/settings.json.
    GeminiCli,
    /// Install for Cursor — registers MCP in ~/.cursor/mcp.json.
    Cursor,
    /// Install MCP config for local CLI clients (Codex, Gemini CLI, Claude Code, Cursor).
    LocalCli,
    /// Auto-detect from the running shell's environment.
    Auto,
}

#[derive(Copy, Clone, Debug, ValueEnum)]
pub enum SetupCodexToolset {
    /// Stable Codex default: compact but keeps shell/codebase/worktree bridge tools.
    Essential,
    /// Experimental narrower Codex surface: memory/skills/session/IDE/plan only.
    Lean,
}

impl From<SetupCodexToolset> for setup::CodexToolset {
    fn from(value: SetupCodexToolset) -> Self {
        match value {
            SetupCodexToolset::Essential => setup::CodexToolset::Essential,
            SetupCodexToolset::Lean => setup::CodexToolset::Lean,
        }
    }
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
            Self::CodexCli => setup::Frontend::CodexCli,
            Self::CodexIde => setup::Frontend::CodexIde,
            Self::GeminiCli => setup::Frontend::GeminiCli,
            Self::Cursor => setup::Frontend::Cursor,
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
/// `ab-precompact-hook`, `ab-session-end-hook`, or
/// `ab-instinct-observer-hook`). This is the strongest
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
        || body.contains("ab-instinct-observer-hook")
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

fn main() -> Result<()> {
    // TD-02: bound the tokio blocking-thread pool. `#[tokio::main]` uses the
    // default cap of 512, which in practice let blocked `spawn_blocking` tasks
    // (sqlite / pty / a hung host call) accumulate threads (observed 83 -> 242,
    // all futex-waiting) and never shed them. A tight cap turns runaway thread
    // growth into back-pressure — excess blocking work queues instead of minting
    // an unbounded thread per stuck task. Default 256 sits above the observed
    // 242 peak (so legit concurrent blocking work isn't starved / self-deadlocked
    // when a CDP/git/shell call nests further blocking tasks) yet at half the
    // tokio default, still bounding runaway. Tunable via env for incident response.
    let max_blocking = std::env::var("AGENT_BRIDGE_MAX_BLOCKING_THREADS")
        .ok()
        .and_then(|s| s.parse::<usize>().ok())
        .filter(|n| *n > 0)
        .unwrap_or(256);
    tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .max_blocking_threads(max_blocking)
        .build()?
        .block_on(real_main())
}

async fn real_main() -> Result<()> {
    // Load API tokens from the user's plaintext creds notebook before any
    // worker thread can read env. Self-heals after a `cargo install` that
    // overwrites the shell wrapper. See `creds.rs` for resolution order.
    ab_bridge::creds::load_at_startup();

    // v22 — opt-in substrate install. Must precede any embedding touch so
    // the OnceLock in ab-store::embedding lands on SeedBackend. Env-gated:
    // `AB_SUBSTRATE=1`. Silent + ablation-safe when unset. Phase 2.2 wires
    // snapshot persistence inside install_default; tests/ablation that
    // don't want IO simply don't call install_default.
    if ab_seed_bridge::env_enabled() {
        if let Err(e) = ab_seed_bridge::install_default() {
            tracing::warn!("seed-bridge install_default failed: {e}");
        } else {
            tracing::info!("seed-bridge installed (v22 phase 2.2)");
        }
    }

    let cli = Cli::parse();
    let cmd = cli.cmd.unwrap_or(Cmd::Daemon);

    // Setup runs synchronously, no async runtime needed beyond tokio's shell.
    if let Cmd::Setup {
        frontend,
        codex_toolset,
        dry_run,
        json,
    } = &cmd
    {
        let frontend = frontend.resolve();
        let codex_toolset = (*codex_toolset).into();
        if *dry_run || *json {
            return setup::dry_run(frontend, codex_toolset, *json);
        }
        return setup::run(frontend, codex_toolset);
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
            SkillsOp::Refresh {
                verbose,
                prune,
                dry_run,
                json,
            } => skills::run_refresh(*verbose, *prune, *dry_run, *json).await,
            SkillsOp::Discover { limit, all } => skills::run_discover(*limit, *all).await,
            SkillsOp::Search { query, limit } => skills::run_search(query, *limit).await,
            SkillsOp::Route {
                query,
                limit,
                body_chars,
                json,
            } => skills::run_route(query, *limit, *body_chars, *json).await,
            SkillsOp::Feedback {
                skill_key,
                query,
                outcome,
                note,
                related_keys,
                json,
            } => {
                skills::run_feedback(
                    skill_key,
                    query,
                    outcome,
                    note.as_deref(),
                    related_keys,
                    *json,
                )
                .await
            }
            SkillsOp::List { limit } => skills::run_list(*limit).await,
            SkillsOp::Sources { json, limit } => skills::run_sources(*json, *limit).await,
            SkillsOp::Audit {
                json,
                src,
                risk,
                lint,
                vendor,
                limit,
            } => {
                skills::run_audit(
                    *json,
                    src.as_deref(),
                    risk,
                    lint.as_deref(),
                    vendor.as_deref(),
                    *limit,
                )
                .await
            }
            SkillsOp::Show { key, json } => skills::run_show(key, *json).await,
            SkillsOp::Install { key, yes, dry_run } => {
                skills::run_install(key, *yes, *dry_run).await
            }
        };
    }

    // Browser-lite probes: short-lived; no Hub and no persistent backend service.
    if let Cmd::BrowserLite { op } = &cmd {
        return match op {
            BrowserLiteOp::Probe {
                backend: BrowserLiteBackend::Obscura,
                bin,
                no_mcp_tools,
                timeout_ms,
                json,
            } => browser_lite::run_obscura_probe(browser_lite::ObscuraProbeOptions {
                bin: bin.clone(),
                timeout_ms: *timeout_ms,
                probe_mcp_tools: !*no_mcp_tools,
                json: *json,
            }),
        };
    }

    // Avatar subcommand: short-lived read-only terminal surface over presence rows.
    if let Cmd::Avatar { op } = &cmd {
        return match op {
            AvatarOp::Surface {
                project,
                role,
                max_idle_secs,
                include_stale,
                limit,
                json: as_json,
                include_raw_presence,
                include_compat,
            } => {
                run_avatar_surface(
                    project.clone(),
                    role.clone(),
                    *max_idle_secs,
                    *include_stale,
                    *limit,
                    *as_json,
                    *include_raw_presence,
                    *include_compat,
                )
                .await
            }
            AvatarOp::BackendProbe { json: as_json } => run_avatar_backend_probe(*as_json),
            AvatarOp::LinuxFloater {
                base_url,
                project,
                role,
                include_stale,
                transparent,
                browser,
                width,
                height,
                sway_manage,
                sway_x,
                sway_y,
                dry_run,
                json: as_json,
            } => {
                run_avatar_linux_floater(
                    base_url.clone(),
                    project.clone(),
                    role.clone(),
                    *include_stale,
                    *transparent,
                    browser.clone(),
                    *width,
                    *height,
                    *sway_manage,
                    *sway_x,
                    *sway_y,
                    *dry_run,
                    *as_json,
                )
                .await
            }
            AvatarOp::LinuxNativeTransparent {
                width,
                height,
                layer,
                anchor,
                margin_top,
                margin_right,
                margin_bottom,
                margin_left,
                duration_ms,
                mode,
                pet_id,
                state_url,
                state_poll_ms,
                state_http_timeout_ms,
                asset,
                frame_col,
                frame_row,
                cell_width,
                cell_height,
                sprite_scale_percent,
                frame_count,
                frame_interval_ms,
                output,
                dry_run,
                json: as_json,
            } => {
                run_avatar_linux_native_transparent(
                    *width,
                    *height,
                    layer.clone(),
                    anchor.clone(),
                    *margin_top,
                    *margin_right,
                    *margin_bottom,
                    *margin_left,
                    *duration_ms,
                    mode.clone(),
                    pet_id.clone(),
                    state_url.clone(),
                    *state_poll_ms,
                    *state_http_timeout_ms,
                    asset.clone(),
                    *frame_col,
                    *frame_row,
                    *cell_width,
                    *cell_height,
                    *sprite_scale_percent,
                    *frame_count,
                    *frame_interval_ms,
                    output.clone(),
                    *dry_run,
                    *as_json,
                )
                .await
            }
            AvatarOp::SyncPresence {
                pet_id,
                session_id,
                name,
                description,
                version,
                url,
                node,
                project,
                role,
                tag,
                agent_id,
                runtime,
                cwd,
                pid,
                no_auto_tag,
                activity_state,
                focus,
                risk_level,
                blocked_reason,
                evidence,
                next_action,
                tts_voice,
                tts_rate,
                json: as_json,
            } => {
                run_avatar_sync_presence(
                    pet_id.clone(),
                    session_id.clone(),
                    name.clone(),
                    description.clone(),
                    version.clone(),
                    url.clone(),
                    node.clone(),
                    project.clone(),
                    role.clone(),
                    tag.clone(),
                    agent_id.clone(),
                    runtime.clone(),
                    cwd.clone(),
                    *pid,
                    *no_auto_tag,
                    activity_state.clone(),
                    focus.clone(),
                    risk_level.clone(),
                    blocked_reason.clone(),
                    evidence.clone(),
                    next_action.clone(),
                    tts_voice.clone(),
                    *tts_rate,
                    *as_json,
                )
                .await
            }
            AvatarOp::InstallHeartbeat {
                label,
                project,
                role,
                session_id,
                agent_id,
                runtime,
                pet_id,
                cwd,
                bin,
                interval_secs,
                activity_state,
                focus,
                risk_level,
                evidence,
                next_action,
                tts_voice,
                tts_rate,
                no_load,
                dry_run,
            } => {
                run_avatar_install_heartbeat(
                    label.clone(),
                    project.clone(),
                    role.clone(),
                    session_id.clone(),
                    agent_id.clone(),
                    runtime.clone(),
                    pet_id.clone(),
                    cwd.clone(),
                    bin.clone(),
                    *interval_secs,
                    activity_state.clone(),
                    focus.clone(),
                    risk_level.clone(),
                    evidence.clone(),
                    next_action.clone(),
                    tts_voice.clone(),
                    *tts_rate,
                    *no_load,
                    *dry_run,
                )
                .await
            }
            AvatarOp::RemoveHeartbeat { label, project } => {
                run_avatar_remove_heartbeat(label.clone(), project.clone()).await
            }
            AvatarOp::HeartbeatStatus { label, project } => {
                run_avatar_heartbeat_status(label.clone(), project.clone()).await
            }
            AvatarOp::HeartbeatHealth {
                label,
                project,
                stale_secs,
                json: as_json,
            } => {
                run_avatar_heartbeat_health(label.clone(), project.clone(), *stale_secs, *as_json)
                    .await
            }
            AvatarOp::HeartbeatAlert {
                label,
                project,
                stale_secs,
                force,
                preview,
                no_notification,
                tts,
                repeat_secs,
                tts_voice,
                tts_rate,
                json: as_json,
            } => {
                run_avatar_heartbeat_alert(
                    label.clone(),
                    project.clone(),
                    *stale_secs,
                    *force,
                    *preview,
                    !*no_notification,
                    *tts,
                    *repeat_secs,
                    tts_voice.clone(),
                    *tts_rate,
                    *as_json,
                )
                .await
            }
            AvatarOp::InstallHeartbeatAlert {
                label,
                project,
                bin,
                interval_secs,
                stale_secs,
                repeat_secs,
                no_notification,
                tts,
                tts_voice,
                tts_rate,
                no_load,
                dry_run,
            } => {
                run_avatar_install_heartbeat_alert(
                    label.clone(),
                    project.clone(),
                    bin.clone(),
                    *interval_secs,
                    *stale_secs,
                    *repeat_secs,
                    !*no_notification,
                    *tts,
                    tts_voice.clone(),
                    *tts_rate,
                    *no_load,
                    *dry_run,
                )
                .await
            }
            AvatarOp::RemoveHeartbeatAlert { label, project } => {
                run_avatar_remove_heartbeat_alert(label.clone(), project.clone()).await
            }
            AvatarOp::HeartbeatAlertStatus { label, project } => {
                run_avatar_heartbeat_alert_status(label.clone(), project.clone()).await
            }
            AvatarOp::SeedEvents {
                label,
                project,
                input,
                limit,
                include_preview,
                output,
                jsonl,
                json: as_json,
            } => {
                run_avatar_seed_events(
                    label.clone(),
                    project.clone(),
                    input.clone(),
                    *limit,
                    *include_preview,
                    output.clone(),
                    *jsonl,
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexReplay {
                label,
                project,
                input,
                output,
                limit,
                include_preview,
                onnx,
                n,
                d,
                json: as_json,
            } => {
                run_avatar_cortex_replay(
                    label.clone(),
                    project.clone(),
                    input.clone(),
                    output.clone(),
                    *limit,
                    *include_preview,
                    !*onnx,
                    *n,
                    *d,
                    *as_json,
                )
                .await
            }
            AvatarOp::InstallCortexRunner {
                label,
                heartbeat_label,
                project,
                bin,
                interval_secs,
                output,
                limit,
                include_preview,
                onnx,
                n,
                d,
                no_load,
                dry_run,
            } => {
                run_avatar_install_cortex_runner(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    bin.clone(),
                    *interval_secs,
                    output.clone(),
                    *limit,
                    *include_preview,
                    !*onnx,
                    *n,
                    *d,
                    *no_load,
                    *dry_run,
                )
                .await
            }
            AvatarOp::RemoveCortexRunner { label, project } => {
                run_avatar_remove_cortex_runner(label.clone(), project.clone()).await
            }
            AvatarOp::CortexStatus {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_status(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexPreview {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_preview(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexLanguage {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_language(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexMotion {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_motion(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexRenderer {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_renderer(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexRendererRegistry {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_renderer_registry(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexBindingPlan {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_binding_plan(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexBindingFixture {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_binding_fixture(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexVisualAdapter {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_visual_adapter(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexRendererView {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_renderer_view(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexReviewGate {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_review_gate(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexReviewPacket {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_review_packet(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexReviewReport {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_review_report(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexReviewDecisions {
                label,
                heartbeat_label,
                project,
                output,
                track,
                decision,
                details,
                limit,
                json: as_json,
            } => {
                run_avatar_cortex_review_decisions(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    track.clone(),
                    decision.clone(),
                    *details,
                    *limit,
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexReviewDecision {
                label,
                heartbeat_label,
                project,
                output,
                actor,
                track,
                decision,
                note,
                evidence,
                confirm,
                details,
                json: as_json,
            } => {
                run_avatar_cortex_review_decision(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    actor.clone(),
                    track.clone(),
                    decision.clone(),
                    note.clone(),
                    evidence.clone(),
                    *confirm,
                    *details,
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexReviewRecord {
                label,
                heartbeat_label,
                project,
                output,
                track,
                variant,
                outcome,
                reviewer,
                reason,
                notes,
                confirm,
                json: as_json,
            } => {
                run_avatar_cortex_review_record(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    track.clone(),
                    variant.clone(),
                    *outcome,
                    reviewer.clone(),
                    reason.clone(),
                    notes.clone(),
                    *confirm,
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexVoicePolicy {
                label,
                heartbeat_label,
                project,
                output,
                json: as_json,
            } => {
                run_avatar_cortex_voice_policy(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexVoiceRequest {
                label,
                heartbeat_label,
                project,
                output,
                track,
                reason,
                json: as_json,
            } => {
                run_avatar_cortex_voice_request(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    track.clone(),
                    reason.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexVoiceConfirm {
                label,
                heartbeat_label,
                project,
                output,
                track,
                reason,
                confirm,
                json: as_json,
            } => {
                run_avatar_cortex_voice_confirm(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    track.clone(),
                    reason.clone(),
                    *confirm,
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexVoiceAction {
                label,
                heartbeat_label,
                project,
                output,
                track,
                reason,
                confirm,
                emit,
                force,
                cooldown_secs,
                tts_voice,
                tts_rate,
                json: as_json,
            } => {
                run_avatar_cortex_voice_action(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    track.clone(),
                    reason.clone(),
                    *confirm,
                    *emit,
                    *force,
                    *cooldown_secs,
                    tts_voice.clone(),
                    *tts_rate,
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexVoiceActionPreview {
                label,
                heartbeat_label,
                project,
                output,
                track,
                reason,
                confirm,
                force,
                cooldown_secs,
                tts_voice,
                tts_rate,
                json: as_json,
            } => {
                run_avatar_cortex_voice_action_preview(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    track.clone(),
                    reason.clone(),
                    *confirm,
                    *force,
                    *cooldown_secs,
                    tts_voice.clone(),
                    *tts_rate,
                    *as_json,
                )
                .await
            }
            AvatarOp::XiaoShuActionRequest {
                label,
                heartbeat_label,
                project,
                output,
                actor,
                intent,
                message,
                track,
                reason,
                confirm,
                enqueue,
                force,
                cooldown_secs,
                tts_voice,
                tts_rate,
                details,
                json: as_json,
            } => {
                run_xiao_shu_action_request(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    actor.clone(),
                    intent.clone(),
                    message.clone(),
                    track.clone(),
                    reason.clone(),
                    *confirm,
                    *enqueue,
                    *force,
                    *cooldown_secs,
                    tts_voice.clone(),
                    *tts_rate,
                    *details,
                    *as_json,
                )
                .await
            }
            AvatarOp::XiaoShuActionRequests {
                project,
                request_id,
                state,
                all_states,
                details,
                limit,
                json: as_json,
            } => {
                run_xiao_shu_action_requests(
                    project.clone(),
                    request_id.clone(),
                    state.clone(),
                    *all_states,
                    *details,
                    *limit,
                    *as_json,
                )
                .await
            }
            AvatarOp::XiaoShuActionRequestAction {
                label,
                heartbeat_label,
                project,
                output,
                request_id,
                reason,
                confirm,
                emit,
                dismiss,
                force,
                cooldown_secs,
                tts_voice,
                tts_rate,
                json: as_json,
            } => {
                run_xiao_shu_action_request_action(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    request_id.clone(),
                    reason.clone(),
                    *confirm,
                    *emit,
                    *dismiss,
                    *force,
                    *cooldown_secs,
                    tts_voice.clone(),
                    *tts_rate,
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexVoiceGate {
                label,
                heartbeat_label,
                project,
                output,
                preview_text,
                enabled,
                force,
                cooldown_secs,
                reason,
                json: as_json,
            } => {
                run_avatar_cortex_voice_gate(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    preview_text.clone(),
                    *enabled,
                    *force,
                    *cooldown_secs,
                    reason.clone(),
                    *as_json,
                )
                .await
            }
            AvatarOp::CortexVoiceEmit {
                label,
                heartbeat_label,
                project,
                output,
                preview_text,
                enabled,
                force,
                cooldown_secs,
                reason,
                allow_policy_override,
                tts_voice,
                tts_rate,
                json: as_json,
            } => {
                run_avatar_cortex_voice_emit(
                    label.clone(),
                    heartbeat_label.clone(),
                    project.clone(),
                    output.clone(),
                    preview_text.clone(),
                    *enabled,
                    *force,
                    *cooldown_secs,
                    reason.clone(),
                    *allow_policy_override,
                    tts_voice.clone(),
                    *tts_rate,
                    *as_json,
                )
                .await
            }
        };
    }

    // Substrate subcommand: short-lived read-only introspection over
    // in-process seed-bridge global. No state.db touched.
    if let Cmd::Substrate { op } = &cmd {
        return match op {
            SubstrateOp::Stats {
                snapshot_path,
                json,
            } => run_substrate_stats(snapshot_path.clone(), *json).await,
            SubstrateOp::Neighbors { key, k, path, json } => {
                run_substrate_neighbors(key.clone(), *k, path.clone(), *json).await
            }
            SubstrateOp::Replay {
                log,
                seed,
                n,
                d,
                use_hash,
                output,
                json,
            } => {
                run_substrate_replay(log.clone(), *seed, *n, *d, *use_hash, output.clone(), *json)
                    .await
            }
            SubstrateOp::Snapshot {
                path,
                limit,
                tier,
                fingerprint_only,
                json,
            } => {
                run_substrate_snapshot(path.clone(), *limit, tier.clone(), *fingerprint_only, *json)
                    .await
            }
        };
    }

    // BioCortex is intentionally a shadow-only external adapter. It runs a
    // local checkout example and never links BioCortex into AB's runtime graph.
    if let Cmd::BioCortex { op } = &cmd {
        return match op {
            BioCortexOp::ShadowDigest {
                checkout,
                benchmark,
                timeout_ms,
                include_raw,
                json,
            } => {
                run_biocortex_shadow_digest(
                    checkout.clone(),
                    benchmark.clone(),
                    *timeout_ms,
                    *include_raw,
                    *json,
                )
                .await
            }
            BioCortexOp::ReplayCompare {
                window_days,
                source,
                fixture_out,
                fixture_in,
                checkout,
                benchmark,
                timeout_ms,
                include_raw,
                include_events,
                json,
            } => {
                run_biocortex_replay_compare(
                    *window_days,
                    source,
                    fixture_out.as_deref(),
                    fixture_in.as_deref(),
                    checkout.clone(),
                    benchmark.clone(),
                    *timeout_ms,
                    *include_raw,
                    *include_events,
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalApprovalPacket {
                target_host,
                branch,
                commit,
                reviewer,
                agent_attestor,
                agent_attestation_decision,
                agent_attestation_summary,
                human_authorization_scope,
                verification_status,
                verification_captured_at,
                current_gate_status,
                hard_holdout_gate_status,
                side_signal_p95_ms_for_5_candidates,
                default_memory_search_added_latency_ms,
                exact_call_site,
                fail_open_behavior,
                rollback_command,
                forum_decision_post_id,
                memory_key,
                json,
            } => {
                run_biocortex_retrieval_approval_packet(
                    BioCortexRetrievalApprovalPacketOptions {
                        target_host: target_host.clone(),
                        branch: branch.clone(),
                        commit: commit.clone(),
                        reviewer: reviewer.clone(),
                        agent_attestor: agent_attestor.clone(),
                        agent_attestation_decision: agent_attestation_decision.clone(),
                        agent_attestation_summary: agent_attestation_summary.clone(),
                        human_authorization_scope: human_authorization_scope.clone(),
                        verification_status: verification_status.clone(),
                        verification_captured_at: verification_captured_at.clone(),
                        current_gate_status: current_gate_status.clone(),
                        hard_holdout_gate_status: hard_holdout_gate_status.clone(),
                        side_signal_p95_ms_for_5_candidates: side_signal_p95_ms_for_5_candidates
                            .clone(),
                        default_memory_search_added_latency_ms:
                            default_memory_search_added_latency_ms.clone(),
                        exact_call_site: exact_call_site.clone(),
                        fail_open_behavior: fail_open_behavior.clone(),
                        rollback_command: rollback_command.clone(),
                        forum_decision_post_id: forum_decision_post_id.clone(),
                        memory_key: memory_key.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInStatus {
                mode,
                per_call_opt_in,
                query,
                baseline_keys,
                side_signal_status,
                fallback_reason,
                latency_ms,
                json,
            } => {
                run_biocortex_retrieval_opt_in_status(
                    BioCortexRetrievalOptInAuditOptions {
                        mode: mode.clone(),
                        per_call_opt_in: *per_call_opt_in,
                        query: query.clone(),
                        baseline_keys: baseline_keys.clone(),
                        side_signal_status: side_signal_status.clone(),
                        fallback_reason: fallback_reason.clone(),
                        latency_ms: *latency_ms,
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInDryRun {
                mode,
                per_call_opt_in,
                query,
                baseline_keys,
                baseline_completed,
                timeout_ms,
                coverage_threshold,
                json,
            } => {
                run_biocortex_retrieval_opt_in_dry_run(
                    BioCortexRetrievalOptInDryRunOptions {
                        mode: mode.clone(),
                        per_call_opt_in: *per_call_opt_in,
                        query: query.clone(),
                        baseline_keys: baseline_keys.clone(),
                        baseline_completed: *baseline_completed,
                        timeout_ms: *timeout_ms,
                        coverage_threshold: *coverage_threshold,
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInReviewPacket {
                dry_run_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => {
                run_biocortex_retrieval_opt_in_review_packet(
                    dry_run_json,
                    BioCortexRetrievalOptInReviewPacketOptions {
                        dry_run_plan: Value::Null,
                        reviewer: reviewer.clone(),
                        commit: commit.clone(),
                        forum_post_id: forum_post_id.clone(),
                        memory_key: memory_key.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInExecutionPacket {
                review_packet_json,
                per_call_opt_in,
                attempt_id,
                commit,
                json,
            } => {
                run_biocortex_retrieval_opt_in_execution_packet(
                    review_packet_json,
                    BioCortexRetrievalOptInExecutionPacketOptions {
                        review_packet: Value::Null,
                        per_call_opt_in: *per_call_opt_in,
                        attempt_id: attempt_id.clone(),
                        commit: commit.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInRuntimeTrial {
                execution_packet_json,
                query,
                input_json,
                candidates_json,
                expected_key,
                checkout,
                timeout_ms,
                coverage_threshold,
                attempt_id,
                commit,
                json,
            } => {
                run_biocortex_retrieval_opt_in_runtime_trial(
                    execution_packet_json,
                    query.clone(),
                    input_json.as_deref(),
                    candidates_json.as_deref(),
                    expected_key.clone(),
                    BioCortexRetrievalOptInRuntimeTrialOptions {
                        execution_packet: Value::Null,
                        query: String::new(),
                        candidates: Vec::new(),
                        expected_key: None,
                        checkout: checkout.clone(),
                        timeout_ms: *timeout_ms,
                        coverage_threshold: *coverage_threshold,
                        attempt_id: attempt_id.clone(),
                        commit: commit.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInRuntimeTrialReviewPacket {
                runtime_trial_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => {
                run_biocortex_retrieval_opt_in_runtime_trial_review_packet(
                    runtime_trial_json,
                    BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions {
                        runtime_trial: Value::Null,
                        reviewer: reviewer.clone(),
                        commit: commit.clone(),
                        forum_post_id: forum_post_id.clone(),
                        memory_key: memory_key.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInOrderDiffPacket {
                source_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => {
                run_biocortex_retrieval_opt_in_order_diff_packet(
                    source_json,
                    BioCortexRetrievalOptInOrderDiffPacketOptions {
                        source_packet: Value::Null,
                        reviewer: reviewer.clone(),
                        commit: commit.clone(),
                        forum_post_id: forum_post_id.clone(),
                        memory_key: memory_key.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInRedactedOrderArtifact {
                source_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => {
                run_biocortex_retrieval_opt_in_redacted_order_artifact(
                    source_json,
                    BioCortexRetrievalOptInRedactedOrderArtifactOptions {
                        source_packet: Value::Null,
                        reviewer: reviewer.clone(),
                        commit: commit.clone(),
                        forum_post_id: forum_post_id.clone(),
                        memory_key: memory_key.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInAuthorizationDecisionPacket {
                authorization_request_json,
                authorization_decision_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => {
                run_biocortex_retrieval_opt_in_authorization_decision_packet(
                    authorization_request_json,
                    authorization_decision_json,
                    BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                        authorization_decision: Value::Null,
                        authorization_request: Value::Null,
                        reviewer: reviewer.clone(),
                        commit: commit.clone(),
                        forum_post_id: forum_post_id.clone(),
                        memory_key: memory_key.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInPostImplementationReviewGate {
                authorization_decision_packet_json,
                opt_in_plan_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => {
                run_biocortex_retrieval_opt_in_post_implementation_review_gate(
                    authorization_decision_packet_json,
                    opt_in_plan_json,
                    BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                        authorization_decision_packet: Value::Null,
                        opt_in_plan: Value::Null,
                        reviewer: reviewer.clone(),
                        commit: commit.clone(),
                        forum_post_id: forum_post_id.clone(),
                        memory_key: memory_key.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInRuntimeInfluenceReviewRequest {
                post_implementation_review_gate_json,
                redacted_order_artifact_json,
                redacted_evidence_aggregate_json,
                evidence_summary_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => {
                run_biocortex_retrieval_opt_in_runtime_influence_review_request(
                    post_implementation_review_gate_json,
                    redacted_order_artifact_json,
                    redacted_evidence_aggregate_json.as_deref(),
                    evidence_summary_json.as_deref(),
                    BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                        post_implementation_review_gate: Value::Null,
                        redacted_order_artifact: Value::Null,
                        redacted_evidence_aggregate: None,
                        evidence_summary: None,
                        reviewer: reviewer.clone(),
                        commit: commit.clone(),
                        forum_post_id: forum_post_id.clone(),
                        memory_key: memory_key.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInRuntimeInfluenceDecisionPacket {
                runtime_influence_review_request_json,
                runtime_influence_decision_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => {
                run_biocortex_retrieval_opt_in_runtime_influence_decision_packet(
                    runtime_influence_review_request_json,
                    runtime_influence_decision_json,
                    BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                        runtime_influence_review_request: Value::Null,
                        runtime_influence_decision: Value::Null,
                        reviewer: reviewer.clone(),
                        commit: commit.clone(),
                        forum_post_id: forum_post_id.clone(),
                        memory_key: memory_key.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInStoreTrial {
                runtime_influence_decision_packet_json,
                query,
                tags_any,
                limit,
                mode,
                per_call_opt_in,
                checkout,
                timeout_ms,
                coverage_threshold,
                blend_alpha,
                attempt_id,
                commit,
                json,
            } => {
                run_biocortex_retrieval_opt_in_store_trial(
                    runtime_influence_decision_packet_json,
                    BioCortexRetrievalOptInStoreTrialOptions {
                        runtime_influence_decision_packet: Value::Null,
                        query: query.clone(),
                        tags_any: tags_any.clone(),
                        limit: *limit,
                        mode: mode.clone(),
                        per_call_opt_in: *per_call_opt_in,
                        checkout: checkout.clone(),
                        timeout_ms: *timeout_ms,
                        coverage_threshold: *coverage_threshold,
                        blend_alpha: *blend_alpha,
                        attempt_id: attempt_id.clone(),
                        commit: commit.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInGatedStoreTrial {
                runtime_transition_gate_json,
                runtime_influence_decision_packet_json,
                query,
                tags_any,
                limit,
                mode,
                per_call_opt_in,
                checkout,
                timeout_ms,
                coverage_threshold,
                blend_alpha,
                attempt_id,
                commit,
                json,
            } => {
                run_biocortex_retrieval_opt_in_gated_store_trial(
                    runtime_transition_gate_json,
                    runtime_influence_decision_packet_json,
                    BioCortexRetrievalOptInGatedStoreTrialOptions {
                        runtime_transition_gate: Value::Null,
                        runtime_influence_decision_packet: Value::Null,
                        query: query.clone(),
                        tags_any: tags_any.clone(),
                        limit: *limit,
                        mode: mode.clone(),
                        per_call_opt_in: *per_call_opt_in,
                        checkout: checkout.clone(),
                        timeout_ms: *timeout_ms,
                        coverage_threshold: *coverage_threshold,
                        blend_alpha: *blend_alpha,
                        attempt_id: attempt_id.clone(),
                        commit: commit.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInBatchDiagnostics {
                runtime_influence_decision_packet_json,
                queries,
                query_classes,
                query_cases_json,
                tags_any,
                limit,
                mode,
                per_call_opt_in,
                checkout,
                timeout_ms,
                coverage_threshold,
                blend_alpha,
                attempt_id,
                commit,
                json,
            } => {
                let query_cases = load_biocortex_batch_query_cases(
                    query_cases_json.as_deref(),
                    queries,
                    query_classes,
                )?;
                run_biocortex_retrieval_opt_in_batch_diagnostics(
                    runtime_influence_decision_packet_json,
                    BioCortexRetrievalOptInBatchDiagnosticsOptions {
                        runtime_influence_decision_packet: Value::Null,
                        queries: query_cases,
                        tags_any: tags_any.clone(),
                        limit: *limit,
                        mode: mode.clone(),
                        per_call_opt_in: *per_call_opt_in,
                        checkout: checkout.clone(),
                        timeout_ms: *timeout_ms,
                        coverage_threshold: *coverage_threshold,
                        blend_alpha: *blend_alpha,
                        attempt_id: attempt_id.clone(),
                        commit: commit.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInGatedBatchDiagnostics {
                runtime_transition_gate_json,
                runtime_influence_decision_packet_json,
                queries,
                query_classes,
                query_cases_json,
                tags_any,
                limit,
                mode,
                per_call_opt_in,
                checkout,
                timeout_ms,
                coverage_threshold,
                blend_alpha,
                attempt_id,
                commit,
                json,
            } => {
                let query_cases = load_biocortex_batch_query_cases(
                    query_cases_json.as_deref(),
                    queries,
                    query_classes,
                )?;
                run_biocortex_retrieval_opt_in_gated_batch_diagnostics(
                    runtime_transition_gate_json,
                    runtime_influence_decision_packet_json,
                    BioCortexRetrievalOptInGatedBatchDiagnosticsOptions {
                        runtime_transition_gate: Value::Null,
                        runtime_influence_decision_packet: Value::Null,
                        queries: query_cases,
                        tags_any: tags_any.clone(),
                        limit: *limit,
                        mode: mode.clone(),
                        per_call_opt_in: *per_call_opt_in,
                        checkout: checkout.clone(),
                        timeout_ms: *timeout_ms,
                        coverage_threshold: *coverage_threshold,
                        blend_alpha: *blend_alpha,
                        attempt_id: attempt_id.clone(),
                        commit: commit.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInRuntimeReadinessPacket {
                runtime_influence_decision_packet_json,
                store_trial_json,
                batch_diagnostics_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => run_biocortex_retrieval_opt_in_runtime_readiness_packet(
                runtime_influence_decision_packet_json,
                store_trial_json,
                batch_diagnostics_json,
                BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                    runtime_influence_decision_packet: Value::Null,
                    store_trial: Value::Null,
                    batch_diagnostics: Value::Null,
                    reviewer: reviewer.clone(),
                    commit: commit.clone(),
                    forum_post_id: forum_post_id.clone(),
                    memory_key: memory_key.clone(),
                },
                *json,
            ),
            BioCortexOp::RetrievalOptInRuntimeTransitionGate {
                runtime_readiness_packet_json,
                mode,
                per_call_opt_in,
                operator_disabled,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => run_biocortex_retrieval_opt_in_runtime_transition_gate(
                runtime_readiness_packet_json,
                BioCortexRetrievalOptInRuntimeTransitionGateOptions {
                    runtime_readiness_packet: Value::Null,
                    mode: mode.clone(),
                    per_call_opt_in: *per_call_opt_in,
                    operator_disabled: *operator_disabled
                        || cli_env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV),
                    reviewer: reviewer.clone(),
                    commit: commit.clone(),
                    forum_post_id: forum_post_id.clone(),
                    memory_key: memory_key.clone(),
                },
                *json,
            ),
            BioCortexOp::RetrievalOptInControlledOrderFixture {
                runtime_influence_decision_packet_json,
                fixture_json,
                allow_non_production_store_writes,
                tags_any,
                limit,
                mode,
                per_call_opt_in,
                checkout,
                timeout_ms,
                coverage_threshold,
                blend_alpha,
                attempt_id,
                commit,
                json,
            } => {
                run_biocortex_retrieval_opt_in_controlled_order_fixture(
                    runtime_influence_decision_packet_json,
                    fixture_json,
                    *allow_non_production_store_writes,
                    BioCortexRetrievalOptInBatchDiagnosticsOptions {
                        runtime_influence_decision_packet: Value::Null,
                        queries: Vec::new(),
                        tags_any: tags_any.clone(),
                        limit: *limit,
                        mode: mode.clone(),
                        per_call_opt_in: *per_call_opt_in,
                        checkout: checkout.clone(),
                        timeout_ms: *timeout_ms,
                        coverage_threshold: *coverage_threshold,
                        blend_alpha: *blend_alpha,
                        attempt_id: attempt_id.clone(),
                        commit: commit.clone(),
                    },
                    *json,
                )
                .await
            }
            BioCortexOp::RetrievalOptInEvidenceSummary {
                batch_diagnostics_json,
                controlled_order_fixture_run_json,
                runtime_readiness_packet_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => run_biocortex_retrieval_opt_in_evidence_summary(
                batch_diagnostics_json,
                controlled_order_fixture_run_json,
                runtime_readiness_packet_json.as_deref(),
                reviewer.clone(),
                commit.clone(),
                forum_post_id.clone(),
                memory_key.clone(),
                *json,
            ),
            BioCortexOp::RetrievalOptInRedactedEvidenceAggregate {
                movement_fixture_run_json,
                coverage_fixture_run_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => run_biocortex_retrieval_opt_in_redacted_evidence_aggregate(
                movement_fixture_run_json,
                coverage_fixture_run_json,
                reviewer.clone(),
                commit.clone(),
                forum_post_id.clone(),
                memory_key.clone(),
                *json,
            ),
            #[cfg(feature = "biocortex-retrieval-shadow")]
            BioCortexOp::RetrievalShadow {
                query,
                input_json,
                candidates_json,
                expected_key,
                checkout,
                timeout_ms,
                include_raw,
                json,
            } => {
                run_biocortex_retrieval_shadow(
                    query.clone(),
                    input_json.as_deref(),
                    candidates_json.as_deref(),
                    expected_key.clone(),
                    checkout.clone(),
                    *timeout_ms,
                    *include_raw,
                    *json,
                )
                .await
            }
        };
    }

    // Dream subcommand: short-lived read-only introspection over state.db.
    if let Cmd::Dream { op } = &cmd {
        return match op {
            DreamOp::Stats { json } => run_dream_stats(*json).await,
            DreamOp::Identity { days, json } => run_dream_identity(*days, *json).await,
            DreamOp::ShadowCortex {
                window_days,
                max_signals,
                source,
                fixture_out,
                fixture_in,
                json,
            } => {
                run_dream_shadow_cortex(
                    *window_days,
                    *max_signals,
                    source.as_str(),
                    fixture_out.as_deref(),
                    fixture_in.as_deref(),
                    *json,
                )
                .await
            }
            DreamOp::ShadowCortexFeedback { op } => match op {
                ShadowCortexFeedbackOp::Record {
                    decision,
                    signal_id,
                    source_event_ids,
                    actor,
                    note,
                    path,
                    json,
                } => run_dream_shadow_cortex_feedback_record(
                    *decision,
                    signal_id,
                    source_event_ids.clone(),
                    actor,
                    note.as_deref(),
                    path.as_deref(),
                    *json,
                ),
                ShadowCortexFeedbackOp::List { limit, path, json } => {
                    run_dream_shadow_cortex_feedback_list(*limit, path.as_deref(), *json)
                }
            },
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
                run_dream_reinforce_active(*window_days, *min_access, *step, *ceiling, *json).await
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
            DreamOp::RestoreArchived { key, json } => run_dream_restore_archived(key, *json).await,
            DreamOp::ClusterProbe {
                min_size,
                top_k,
                preview,
                json,
            } => run_dream_cluster_probe(*min_size, *top_k, *preview, *json).await,
            DreamOp::TombstoneAgedArchived {
                older_than_days,
                max_count,
                dry_run,
                json,
            } => {
                run_dream_tombstone_aged_archived(*older_than_days, *max_count, *dry_run, *json)
                    .await
            }
            DreamOp::PurgeTombstones {
                older_than_days,
                dry_run,
                json,
            } => run_dream_purge_tombstones(*older_than_days, *dry_run, *json).await,
            DreamOp::XmGc {
                max_age_days,
                dry_run,
                json,
            } => run_dream_xm_gc(*max_age_days, *dry_run, *json).await,
            DreamOp::ReplayAudit {
                stale_days,
                waypoint_min,
                overlap_min,
                json,
            } => run_dream_replay_audit(*stale_days, *waypoint_min, *overlap_min, *json).await,
            DreamOp::Snapshot {
                name,
                days,
                print_only,
                json,
            } => run_dream_snapshot(name.as_deref(), *days, *print_only, *json).await,
            DreamOp::Diff {
                key_a,
                key_b,
                auto,
                json,
            } => run_dream_diff(key_a.as_deref(), key_b.as_deref(), *auto, *json).await,
            DreamOp::Weekly { no_snapshot, json } => run_dream_weekly(*no_snapshot, *json).await,
            DreamOp::CodebaseReport {
                root,
                top_n,
                html,
                json,
            } => run_dream_codebase_report(root.as_deref(), *top_n, html.as_deref(), *json).await,
            DreamOp::SubstrateAudit {
                window_days,
                json,
                exclude_kinds,
            } => run_dream_substrate_audit(*window_days, *json, exclude_kinds.clone()).await,
            DreamOp::DecayCoactivation {
                tau_days,
                max_iterations,
                dry_run,
                json,
            } => run_dream_decay_coactivation(*tau_days, *max_iterations, *dry_run, *json).await,
            DreamOp::SubstrateCorrAudit {
                k,
                min_cofires,
                snapshot_path,
                json,
            } => {
                run_dream_substrate_corr_audit(*k, *min_cofires, snapshot_path.clone(), *json).await
            }
            DreamOp::AgentMdDrift {
                window_days,
                dry_run,
                agent_md_path,
                json,
            } => {
                run_dream_agent_md_drift(*window_days, *dry_run, agent_md_path.clone(), *json).await
            }
            DreamOp::SkillRetro { days, json } => run_dream_skill_retro(*days, *json).await,
            DreamOp::GapAudit { since, json } => run_dream_gap_audit(since, *json).await,
        };
    }

    // ShellInit: print snippet to stdout. Pure function, no daemon, no state.
    if let Cmd::ShellInit { shell } = &cmd {
        print!("{}", shell_init_snippet(*shell));
        return Ok(());
    }

    // Deployment self-check — pure file/process inspection, no Hub.
    if let Cmd::Doctor { json, markdown } = &cmd {
        return doctor::run_doctor(*json, *markdown).await;
    }

    // Instinct observer maintenance — pure local sidecar file operation.
    if let Cmd::Instinct { op } = &cmd {
        return match op {
            InstinctOp::RotateLog { dry_run, json } => {
                let plan = instinct::rotate_observer_log(*dry_run)
                    .context("rotate instinct observer log")?;
                if *json {
                    println!("{}", serde_json::to_string_pretty(&plan)?);
                } else {
                    println!(
                        "instinct observer log: {} {} -> {}",
                        plan.get("status")
                            .and_then(|v| v.as_str())
                            .unwrap_or("unknown"),
                        plan.get("log_path").and_then(|v| v.as_str()).unwrap_or(""),
                        plan.get("archive_path")
                            .and_then(|v| v.as_str())
                            .unwrap_or("")
                    );
                }
                Ok(())
            }
        };
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

    // C2: state.db rescue-snapshot. No Hub — reads /proc + writes
    // recovery dir + lockfile. Pure (well, IO-bound) function.
    if let Cmd::RescueSnapshot {
        canonical,
        ttl_secs,
        pid,
        json,
    } = &cmd
    {
        return run_rescue_snapshot(*canonical, *ttl_secs, *pid, *json).await;
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
                let mut store_impl = SqliteStore::open(&path).await?;
                // Track MS — stamp this node's identity so live memory writes
                // carry a version vector (conflict-aware cross-machine sync).
                store_impl.set_node_id(ab_store::node_id_from_name(
                    &ab_bridge::sync::hostname_short(),
                ));
                let store: Arc<dyn StateStore> = Arc::new(store_impl);
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
            // P-α — spawn always-warm coactivation tick if a store is
            // available and the env disable flag is not set. The task
            // runs for the daemon's lifetime; detached on shutdown.
            // See docs/DESIGN-P-alpha-always-warm-coactivation-tick.md
            if std::env::var("AGENT_BRIDGE_DISABLE_SUBSTRATE_TICK")
                .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
                .unwrap_or(false)
            {
                tracing::info!(
                    "substrate-tick: disabled by env (AGENT_BRIDGE_DISABLE_SUBSTRATE_TICK=1)"
                );
            } else if let Some(store) = hub.store.clone() {
                let tick_secs: u64 = std::env::var("AGENT_BRIDGE_TICK_SECS")
                    .ok()
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(30)
                    .clamp(5, 300);
                let tau_secs: i64 = std::env::var("AGENT_BRIDGE_TAU_SECS")
                    .ok()
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(7 * 86_400)
                    .clamp(3600, 30 * 86_400);
                tracing::info!(
                    tick_secs,
                    tau_secs,
                    "substrate-tick: spawning P-α always-warm coactivation tick"
                );
                tokio::spawn(async move {
                    let mut interval =
                        tokio::time::interval(std::time::Duration::from_secs(tick_secs));
                    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
                    // Skip the first immediate fire (interval ticks once at t=0).
                    interval.tick().await;
                    loop {
                        interval.tick().await;
                        let now = std::time::SystemTime::now()
                            .duration_since(std::time::UNIX_EPOCH)
                            .map(|d| d.as_secs() as i64)
                            .unwrap_or(0);
                        match store.decay_coactivation_once(tau_secs, now, 10).await {
                            Ok(s) if s.iterations > 0 => {
                                tracing::debug!(
                                    swept = s.swept,
                                    pruned = s.pruned,
                                    iters = s.iterations,
                                    "substrate-tick: ran"
                                );
                            }
                            Ok(_) => {}
                            Err(e) => {
                                tracing::warn!(error = %e, "substrate-tick: decay error");
                            }
                        }
                    }
                });
            } else {
                tracing::info!("substrate-tick: no store configured, skipping");
            }

            // C3 — daemon self-check tick (Collab Protocol v0 §3.4).
            // S1 multi-process FD enum runs every 30s; on hit, writes
            // OOB alert to ~/.cache/agent-bridge/alerts/ + tracing
            // error on target agent_bridge::sync_safety.
            //
            // S5 schema_meta.version watch shares the same tick when a
            // store is configured. S2-S4/S6 still pending follow-ups.
            if ab_bridge::c3_self_check::c3_disabled_via_env() {
                tracing::info!("c3-self-check: disabled by env (AB_C3_DISABLE=1)");
            } else {
                let c3_tick_secs: u64 = std::env::var("AB_C3_TICK_SECS")
                    .ok()
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(30)
                    .clamp(5, 300);
                let c3_store = hub.store.clone();
                tracing::info!(
                    tick_secs = c3_tick_secs,
                    s5_enabled = c3_store.is_some(),
                    "c3-self-check: spawning S1+S5 tick"
                );
                tokio::spawn(async move {
                    let mut interval =
                        tokio::time::interval(std::time::Duration::from_secs(c3_tick_secs));
                    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
                    // Skip the t=0 immediate fire — startup may race
                    // with the daemon installing its own fds.
                    interval.tick().await;
                    loop {
                        interval.tick().await;
                        let inv = ab_bridge::c3_self_check::s1_check_and_alert();
                        if !inv.is_empty() {
                            tracing::warn!(
                                pids = inv.len(),
                                "c3-self-check: S1 detected state.db (deleted) fds"
                            );
                        }
                        if let Some(store) = c3_store.as_ref() {
                            match store.schema_meta_version().await {
                                Ok(Some(v)) => {
                                    if ab_bridge::c3_self_check::s5_check_and_alert(&v) {
                                        tracing::warn!(
                                            version = %v,
                                            "c3-self-check: S5 schema_meta.version change fired alert"
                                        );
                                    }
                                }
                                Ok(None) => {
                                    // Backend has no schema_meta row — nothing to
                                    // compare against. Quiet by design.
                                }
                                Err(e) => {
                                    tracing::warn!(
                                        error = %e,
                                        "c3-self-check: S5 schema_meta_version error"
                                    );
                                }
                            }

                            // S2-S4 — 5-min anchor metric drops. Cheap (3 SELECT
                            // COUNT) so we let the check sample every tick; the
                            // helper internally guards against returning anything
                            // before the 5-min window elapses.
                            match store.s234_counts().await {
                                Ok(counts) => {
                                    let now = std::time::SystemTime::now();
                                    let events =
                                        ab_bridge::c3_self_check::s234_check_against_snapshot(
                                            counts, now,
                                        );
                                    if !events.is_empty() {
                                        let ts_unix = now
                                            .duration_since(std::time::UNIX_EPOCH)
                                            .map(|d| d.as_secs() as i64)
                                            .unwrap_or(0);
                                        let node_label = ab_bridge::c3_self_check::c3_node_label();
                                        for ev in events {
                                            let title = format!(
                                                "[C3 alert][{}] {}: {} -> {}",
                                                node_label,
                                                ev.signal.as_str(),
                                                ev.before,
                                                ev.after,
                                            );
                                            let body =
                                                ab_bridge::c3_self_check::format_s234_alert_body_for_node(
                                                    &ev,
                                                    ts_unix,
                                                    &node_label,
                                                );
                                            if let Err(e) = store
                                                .forum_post(
                                                    None,
                                                    Some("incidents"),
                                                    Some(&title),
                                                    "agent-bridge:daemon:c3-s234",
                                                    "finding",
                                                    &body,
                                                    None,
                                                    None,
                                                )
                                                .await
                                            {
                                                tracing::warn!(
                                                    error = %e,
                                                    signal = ev.signal.as_str(),
                                                    "c3-self-check: S2-S4 forum_post failed"
                                                );
                                            } else {
                                                tracing::warn!(
                                                    signal = ev.signal.as_str(),
                                                    before = ev.before,
                                                    after = ev.after,
                                                    drop_pct = ev.drop_pct,
                                                    "c3-self-check: S2-S4 drop posted to incidents"
                                                );
                                            }
                                        }
                                    }
                                }
                                Err(e) => {
                                    tracing::warn!(
                                        error = %e,
                                        "c3-self-check: s234_counts error"
                                    );
                                }
                            }
                        }
                    }
                });
            }
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
        | Cmd::BrowserLite { .. }
        | Cmd::Avatar { .. }
        | Cmd::Dream { .. }
        | Cmd::Substrate { .. }
        | Cmd::BioCortex { .. }
        | Cmd::Palace { .. }
        | Cmd::ShellInit { .. }
        | Cmd::WorktreeSession { .. }
        | Cmd::RescueSnapshot { .. }
        | Cmd::Doctor { .. }
        | Cmd::Instinct { .. } => unreachable!(),
    }
}

async fn run_avatar_surface(
    project: Option<String>,
    role: Option<String>,
    max_idle_secs: i64,
    include_stale: bool,
    limit: u32,
    as_json: bool,
    include_raw_presence: bool,
    include_compat: bool,
) -> Result<()> {
    let max_idle_secs = if include_stale { 0 } else { max_idle_secs };
    let limit = limit.clamp(1, 500);
    let store = SqliteStore::open(&default_db_path())
        .await
        .context("open state.db")?;
    let rows = store
        .agent_presence_list(project.as_deref(), role.as_deref(), max_idle_secs, limit)
        .await
        .context("agent_presence_list")?;
    let avatars: Vec<serde_json::Value> = rows
        .iter()
        .map(|row| {
            ab_bridge::avatar_surface::entry_from_presence(
                row,
                include_raw_presence,
                include_compat,
            )
        })
        .collect();
    let report_ctx = ab_bridge::avatar_surface::ReportContext {
        project: project.as_deref(),
        role: role.as_deref(),
        max_idle_secs,
        source: "local",
    };
    let report = ab_bridge::avatar_surface::report_from_entries(&avatars, &report_ctx);

    if as_json {
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "agent_avatar_protocol": ab_bridge::avatar_surface::AGENT_AVATAR_PROTOCOL_VERSION,
                "read_only": true,
                "surface": "avatar_surface_cli",
                "count": avatars.len(),
                "project": project,
                "role": role,
                "max_idle_secs": max_idle_secs,
                "limit": limit,
                "report": report,
                "avatars": avatars,
            }))?
        );
    } else {
        println!("{report}");
    }
    Ok(())
}

/// LCC-F1: report which avatar body backend can satisfy transparency on this
/// compositor. Read-only (env probe only); makes the non-wlroots transparency
/// gap explicit instead of a silent blind spot. See DESIGN-v26 §6.
fn run_avatar_backend_probe(as_json: bool) -> Result<()> {
    let info = ab_bridge::avatar_floater::detect_compositor();
    let rec = ab_bridge::avatar_floater::recommend_backend(&info);
    if as_json {
        let payload = serde_json::json!({
            "surface": "linux_avatar_backend_probe",
            "compositor": {
                "session_type": info.session_type,
                "current_desktop": info.current_desktop,
                "has_wayland_display": info.has_wayland_display,
                "wlroots_signal": info.wlroots_signal,
            },
            "recommendation": {
                "backend": rec.backend.as_str(),
                "transparency_available": rec.transparency_available,
                "reason": rec.reason,
            },
            "read_only": true,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
    } else {
        println!("avatar backend probe (read-only)");
        println!(
            "  session_type    : {}",
            info.session_type.as_deref().unwrap_or("?")
        );
        println!(
            "  current_desktop : {}",
            info.current_desktop.as_deref().unwrap_or("?")
        );
        println!("  wayland_display : {}", info.has_wayland_display);
        println!(
            "  wlroots_signal  : {}",
            info.wlroots_signal.as_deref().unwrap_or("none")
        );
        println!("  => backend      : {}", rec.backend.as_str());
        println!(
            "     transparency : {}",
            if rec.transparency_available {
                "available"
            } else {
                "NOT available (degraded browser floater)"
            }
        );
        println!("     reason       : {}", rec.reason);
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_linux_floater(
    base_url: String,
    project: Option<String>,
    role: Option<String>,
    include_stale: bool,
    transparent: bool,
    browser: Option<String>,
    width: u32,
    height: u32,
    sway_manage: bool,
    sway_x: i32,
    sway_y: i32,
    dry_run: bool,
    as_json: bool,
) -> Result<()> {
    let opts = ab_bridge::avatar_floater::LinuxFloaterOptions {
        base_url,
        project,
        role,
        include_stale,
        width,
        height,
        browser,
        transparent,
    };
    let url = ab_bridge::avatar_floater::linux_renderer_url(&opts);
    let candidates = ab_bridge::avatar_floater::browser_candidates_from_path();
    let browser = ab_bridge::avatar_floater::choose_browser(opts.browser.as_deref(), &candidates)
        .ok_or_else(|| {
        anyhow::anyhow!(
            "no supported browser found on PATH; pass --browser google-chrome or similar"
        )
    })?;
    let args = ab_bridge::avatar_floater::browser_app_args(
        &url,
        opts.width,
        opts.height,
        opts.transparent,
    );
    let sway_command = sway_manage.then(|| {
        ab_bridge::avatar_floater::sway_manage_command(
            ab_bridge::avatar_floater::LINUX_RENDERER_TITLE,
            opts.width,
            opts.height,
            sway_x,
            sway_y,
        )
    });

    if dry_run {
        if as_json {
            println!(
                "{}",
                serde_json::to_string_pretty(&json!({
                    "surface": "linux_avatar_floater_launch_plan",
                    "read_only": true,
                    "browser": browser,
                    "args": args,
                    "url": url,
                    "width": opts.width,
                    "height": opts.height,
                    "transparent": opts.transparent,
                    "sway_manage": sway_manage,
                    "sway_command": sway_command,
                    "spawned": false,
                }))?
            );
        } else {
            println!("browser: {browser}");
            println!("url: {url}");
            println!("args: {}", args.join(" "));
            if let Some(command) = &sway_command {
                println!("swaymsg: {command}");
            }
        }
        return Ok(());
    }

    let mut command = if cfg!(unix) {
        let mut command = std::process::Command::new("setsid");
        command.arg(&browser);
        command
    } else {
        std::process::Command::new(&browser)
    };
    command
        .args(&args)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null());
    let child = command
        .spawn()
        .with_context(|| format!("spawn Linux avatar floater launcher for `{browser}`"))?;

    let mut sway_managed = false;
    if let Some(command) = &sway_command {
        run_sway_manage_command(command).await?;
        sway_managed = true;
    }

    if as_json {
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "surface": "linux_avatar_floater_launch_plan",
                "read_only": true,
                "browser": browser,
                "args": args,
                "url": url,
                "width": opts.width,
                "height": opts.height,
                "transparent": opts.transparent,
                "sway_manage": sway_manage,
                "sway_command": sway_command,
                "sway_managed": sway_managed,
                "spawned": true,
                "pid": child.id(),
            }))?
        );
    } else {
        println!("launched Linux avatar floater pid={} url={url}", child.id());
        if sway_managed {
            println!("managed Linux avatar floater with swaymsg");
        }
    }
    Ok(())
}

async fn run_sway_manage_command(command: &str) -> Result<()> {
    let mut last_exit = None;
    for _ in 0..20 {
        tokio::time::sleep(std::time::Duration::from_millis(250)).await;
        let status = std::process::Command::new("swaymsg")
            .arg(command)
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .with_context(|| format!("spawn swaymsg for Linux avatar floater: {command}"))?;
        if status.success() {
            return Ok(());
        }
        last_exit = status.code();
    }
    anyhow::bail!("swaymsg failed for Linux avatar floater after retries: exit={last_exit:?}")
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_linux_native_transparent(
    width: u32,
    height: u32,
    layer: String,
    anchor: String,
    margin_top: i32,
    margin_right: i32,
    margin_bottom: i32,
    margin_left: i32,
    duration_ms: u64,
    mode: String,
    pet_id: Option<String>,
    state_url: Option<String>,
    state_poll_ms: u64,
    state_http_timeout_ms: u64,
    asset: Option<String>,
    frame_col: u32,
    frame_row: u32,
    cell_width: u32,
    cell_height: u32,
    sprite_scale_percent: u32,
    frame_count: u32,
    frame_interval_ms: u64,
    output: Option<String>,
    dry_run: bool,
    as_json: bool,
) -> Result<()> {
    let layer = ab_bridge::avatar_native::parse_native_layer(&layer)
        .ok_or_else(|| anyhow::anyhow!("invalid --layer; expected top or overlay"))?;
    let anchor = ab_bridge::avatar_native::parse_native_anchor(&anchor).ok_or_else(|| {
        anyhow::anyhow!(
            "invalid --anchor; expected top-left, top-right, bottom-left, or bottom-right"
        )
    })?;
    let state_pet_id = pet_id
        .as_deref()
        .map(|value| ab_bridge::pet_state::normalize_pet_id(Some(value)));
    let state_url = state_url
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned);
    let sprite_asset = match asset.as_deref().map(str::trim) {
        Some("none") | Some("None") | Some("NONE") => None,
        Some(value) if !value.is_empty() => Some(value.to_string()),
        _ => ab_bridge::avatar_native::native_sprite_asset_for_mode(&mode),
    };
    let mut opts = ab_bridge::avatar_native::NativeTransparentOptions {
        width,
        height,
        layer,
        anchor,
        margin_top,
        margin_right,
        margin_bottom,
        margin_left,
        duration_ms,
        sprite_asset,
        frame_col,
        frame_row,
        cell_width,
        cell_height,
        sprite_scale_percent,
        frame_count,
        frame_interval_ms,
        state_pet_id: state_pet_id.clone(),
        state_url,
        state_poll_ms,
        state_http_timeout_ms,
        output,
        ..ab_bridge::avatar_native::NativeTransparentOptions::default()
    };
    if let Some(pet_id) = state_pet_id.as_deref() {
        if let Some(state) = ab_bridge::pet_state::read_pet_state(pet_id)
            .with_context(|| format!("read native avatar pet sidecar state for {pet_id}"))?
        {
            let plan = ab_bridge::avatar_native::native_sprite_plan_from_state_value(&state);
            ab_bridge::avatar_native::apply_native_sprite_plan(&mut opts, &plan);
        }
    }

    if dry_run {
        let plan = ab_bridge::avatar_native::native_transparent_plan_json(&opts, false);
        if as_json {
            println!("{}", serde_json::to_string_pretty(&plan)?);
        } else {
            println!(
                "native transparent probe: {}x{} layer={} anchor={} duration={}ms",
                opts.width,
                opts.height,
                ab_bridge::avatar_native::native_layer_name(opts.layer),
                ab_bridge::avatar_native::native_anchor_name(opts.anchor).replace('_', "-"),
                opts.duration_ms
            );
            println!("backend: wayland_wlr_layer_shell");
            println!("pixel_format: wl_shm::Argb8888");
        }
        return Ok(());
    }

    ab_bridge::avatar_native::run_native_transparent_probe(opts.clone())?;
    let plan = ab_bridge::avatar_native::native_transparent_plan_json(&opts, true);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&plan)?);
    } else {
        println!(
            "native transparent probe completed: {}x{} duration={}ms",
            opts.width, opts.height, opts.duration_ms
        );
    }
    Ok(())
}

fn avatar_arg_string(args: &mut Map<String, Value>, key: &str, value: Option<String>) {
    if let Some(value) = value {
        let trimmed = value.trim();
        if !trimmed.is_empty() {
            args.insert(key.to_string(), json!(trimmed));
        }
    }
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_sync_presence(
    pet_id: Option<String>,
    session_id: Option<String>,
    name: Option<String>,
    description: Option<String>,
    version: Option<String>,
    url: Option<String>,
    node: Option<String>,
    project: Option<String>,
    role: String,
    tag: Option<String>,
    agent_id: Option<String>,
    runtime: String,
    cwd: Option<String>,
    pid: Option<i64>,
    no_auto_tag: bool,
    activity_state: Option<String>,
    focus: Option<String>,
    risk_level: Option<String>,
    blocked_reason: Option<String>,
    evidence: Option<String>,
    next_action: Option<String>,
    tts_voice: Option<String>,
    tts_rate: Option<u64>,
    as_json: bool,
) -> Result<()> {
    let mut args = Map::new();
    avatar_arg_string(&mut args, "pet_id", pet_id);
    avatar_arg_string(&mut args, "session_id", session_id);
    avatar_arg_string(&mut args, "name", name);
    avatar_arg_string(&mut args, "description", description);
    avatar_arg_string(&mut args, "version", version);
    avatar_arg_string(&mut args, "url", url);
    avatar_arg_string(&mut args, "node", node);
    avatar_arg_string(&mut args, "project", project);
    avatar_arg_string(&mut args, "role", Some(role));
    avatar_arg_string(&mut args, "tag", tag);
    avatar_arg_string(&mut args, "agent_id", agent_id);
    avatar_arg_string(&mut args, "runtime", Some(runtime));
    let cwd = cwd.or_else(|| {
        std::env::current_dir()
            .ok()
            .map(|p| p.display().to_string())
    });
    avatar_arg_string(&mut args, "cwd", cwd);
    avatar_arg_string(&mut args, "activity_state", activity_state);
    avatar_arg_string(&mut args, "focus", focus);
    avatar_arg_string(&mut args, "risk_level", risk_level);
    avatar_arg_string(&mut args, "blocked_reason", blocked_reason);
    avatar_arg_string(&mut args, "evidence", evidence);
    avatar_arg_string(&mut args, "next_action", next_action);
    avatar_arg_string(&mut args, "tts_voice", tts_voice);
    if let Some(pid) = pid {
        args.insert("pid".to_string(), json!(pid));
    }
    if no_auto_tag {
        args.insert("auto_tag".to_string(), json!(false));
    }
    if let Some(rate) = tts_rate {
        args.insert("tts_rate".to_string(), json!(rate));
    }

    let store = SqliteStore::open(&default_db_path())
        .await
        .context("open state.db")?;
    let payload = ab_bridge::pet_presence::sync_pet_presence(&store, Value::Object(args))
        .await
        .context("avatar sync-presence")?;

    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
    } else {
        let session_id = payload
            .get("session_id")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown-session");
        let avatar = payload
            .get("avatar_state")
            .and_then(|v| v.as_object())
            .cloned()
            .unwrap_or_default();
        let presence = payload
            .get("presence")
            .and_then(|v| v.as_object())
            .cloned()
            .unwrap_or_default();
        let field = |key: &str, fallback: &str| {
            avatar
                .get(key)
                .and_then(|v| v.as_str())
                .unwrap_or(fallback)
                .to_string()
        };
        let heartbeat = presence
            .get("last_heartbeat_at")
            .map(|v| v.to_string())
            .unwrap_or_else(|| "-".to_string());
        println!("Pet presence synced");
        println!("session_id={session_id}");
        println!(
            "runtime={} avatar={} mode={} activity={} focus={}",
            field("runtime", "unknown-runtime"),
            field("avatar_id", "unknown-avatar"),
            field("mode", "unknown"),
            field("activity_state", "unknown"),
            field("focus", "-")
        );
        println!("heartbeat={heartbeat}");
        println!(
            "auto_tagged={}",
            payload
                .get("auto_tagged")
                .and_then(|v| v.as_bool())
                .unwrap_or(false)
        );
    }
    Ok(())
}

fn home_dir() -> Result<PathBuf> {
    std::env::var_os("HOME")
        .map(PathBuf::from)
        .ok_or_else(|| anyhow::anyhow!("HOME is not set"))
}

fn avatar_current_cwd() -> Result<PathBuf> {
    std::env::current_dir().context("resolve current dir")
}

fn avatar_project_slug(project: Option<String>, cwd: &std::path::Path) -> String {
    project
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .or_else(|| {
            cwd.file_name()
                .and_then(|s| s.to_str())
                .map(|s| s.to_string())
        })
        .unwrap_or_else(|| "agent-bridge".to_string())
}

fn launchd_label_component(value: &str) -> String {
    let mut out = String::new();
    for ch in value.chars() {
        if ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.') {
            out.push(ch.to_ascii_lowercase());
        } else if ch.is_whitespace() {
            out.push('-');
        }
    }
    let out = out.trim_matches(['-', '.', '_']).to_string();
    if out.is_empty() {
        "default".to_string()
    } else {
        out
    }
}

fn avatar_heartbeat_label(label: Option<String>, project: &str) -> String {
    label
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| {
            format!(
                "com.agentbridge.avatar-heartbeat.{}",
                launchd_label_component(project)
            )
        })
}

fn avatar_heartbeat_alert_label(label: Option<String>, project: &str) -> String {
    label
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| {
            format!(
                "com.agentbridge.avatar-heartbeat-alert.{}",
                launchd_label_component(project)
            )
        })
}

fn avatar_cortex_runner_label(label: Option<String>, project: &str) -> String {
    label
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| {
            format!(
                "com.agentbridge.avatar-cortex.{}",
                launchd_label_component(project)
            )
        })
}

fn launchd_xml_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

fn avatar_launchd_domain() -> Result<String> {
    let output = std::process::Command::new("id")
        .arg("-u")
        .output()
        .context("run id -u")?;
    if !output.status.success() {
        return Err(anyhow::anyhow!("id -u exited with {}", output.status));
    }
    let uid = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if uid.is_empty() {
        return Err(anyhow::anyhow!("id -u returned empty uid"));
    }
    Ok(format!("gui/{uid}"))
}

fn avatar_launchd_plist_path(label: &str) -> Result<PathBuf> {
    Ok(home_dir()?
        .join("Library")
        .join("LaunchAgents")
        .join(format!("{label}.plist")))
}

fn avatar_launchd_log_path(label: &str, suffix: &str) -> Result<PathBuf> {
    Ok(home_dir()?
        .join("Library")
        .join("Logs")
        .join("agent-bridge")
        .join(format!("{label}.{suffix}.log")))
}

fn avatar_default_heartbeat_bin() -> Result<PathBuf> {
    let home = home_dir()?;
    let real = home.join(".local/bin/agent-bridge.real");
    if real.exists() {
        Ok(real)
    } else {
        Ok(home.join(".local/bin/agent-bridge"))
    }
}

fn launchctl_status(args: &[&str]) -> Result<std::process::ExitStatus> {
    std::process::Command::new("launchctl")
        .args(args)
        .status()
        .with_context(|| format!("launchctl {}", args.join(" ")))
}

fn launchctl_status_quiet(args: &[&str]) -> Result<std::process::ExitStatus> {
    std::process::Command::new("launchctl")
        .args(args)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .with_context(|| format!("launchctl {}", args.join(" ")))
}

fn run_launchctl(args: &[&str]) -> Result<()> {
    let status = launchctl_status(args)?;
    if !status.success() {
        return Err(anyhow::anyhow!(
            "launchctl {} exited with {}",
            args.join(" "),
            status
        ));
    }
    Ok(())
}

fn avatar_heartbeat_plist(
    label: &str,
    program_args: &[String],
    interval_secs: u64,
    stdout_path: &std::path::Path,
    stderr_path: &std::path::Path,
) -> String {
    let mut args_xml = String::new();
    for arg in program_args {
        args_xml.push_str("    <string>");
        args_xml.push_str(&launchd_xml_escape(arg));
        args_xml.push_str("</string>\n");
    }
    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
{args_xml}  </array>
  <key>StartInterval</key>
  <integer>{interval_secs}</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{stdout_path}</string>
  <key>StandardErrorPath</key>
  <string>{stderr_path}</string>
</dict>
</plist>
"#,
        label = launchd_xml_escape(label),
        args_xml = args_xml,
        interval_secs = interval_secs,
        stdout_path = launchd_xml_escape(&stdout_path.display().to_string()),
        stderr_path = launchd_xml_escape(&stderr_path.display().to_string())
    )
}

fn avatar_program_arg(args: &mut Vec<String>, key: &str, value: String) {
    args.push(key.to_string());
    args.push(value);
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_install_heartbeat(
    label: Option<String>,
    project: Option<String>,
    role: String,
    session_id: Option<String>,
    agent_id: Option<String>,
    runtime: String,
    pet_id: Option<String>,
    cwd: Option<PathBuf>,
    bin: Option<PathBuf>,
    interval_secs: u64,
    activity_state: Option<String>,
    focus: Option<String>,
    risk_level: Option<String>,
    evidence: Option<String>,
    next_action: Option<String>,
    tts_voice: Option<String>,
    tts_rate: Option<u64>,
    no_load: bool,
    dry_run: bool,
) -> Result<()> {
    let cwd = cwd.unwrap_or(avatar_current_cwd()?);
    let project = avatar_project_slug(project, &cwd);
    let label = avatar_heartbeat_label(label, &project);
    let session_id = session_id.unwrap_or_else(|| label.clone());
    let agent_id = agent_id.unwrap_or_else(|| session_id.clone());
    let bin = match bin {
        Some(bin) => bin,
        None => avatar_default_heartbeat_bin()?,
    };
    let interval_secs = interval_secs.clamp(30, 3600);
    let activity_state = activity_state.unwrap_or_else(|| "launchd-heartbeat".to_string());
    let focus = focus.unwrap_or_else(|| "avatar-heartbeat".to_string());
    let risk_level = risk_level.unwrap_or_else(|| "low".to_string());
    let evidence = evidence.unwrap_or_else(|| "launchd avatar heartbeat".to_string());
    let next_action = next_action.unwrap_or_else(|| "refresh avatar surface panel".to_string());
    let plist_path = avatar_launchd_plist_path(&label)?;
    let stdout_path = avatar_launchd_log_path(&label, "out")?;
    let stderr_path = avatar_launchd_log_path(&label, "err")?;

    let mut program_args = vec![
        bin.display().to_string(),
        "avatar".to_string(),
        "sync-presence".to_string(),
    ];
    if let Some(pet_id) = pet_id {
        avatar_program_arg(&mut program_args, "--pet-id", pet_id);
    }
    avatar_program_arg(&mut program_args, "--project", project.clone());
    avatar_program_arg(&mut program_args, "--role", role);
    avatar_program_arg(&mut program_args, "--tag", "launchd".to_string());
    avatar_program_arg(&mut program_args, "--session-id", session_id);
    avatar_program_arg(&mut program_args, "--agent-id", agent_id);
    avatar_program_arg(&mut program_args, "--runtime", runtime);
    avatar_program_arg(&mut program_args, "--cwd", cwd.display().to_string());
    avatar_program_arg(&mut program_args, "--activity-state", activity_state);
    avatar_program_arg(&mut program_args, "--focus", focus);
    avatar_program_arg(&mut program_args, "--risk-level", risk_level);
    avatar_program_arg(&mut program_args, "--evidence", evidence);
    avatar_program_arg(&mut program_args, "--next-action", next_action);
    if let Some(tts_voice) = tts_voice {
        avatar_program_arg(&mut program_args, "--tts-voice", tts_voice);
    }
    if let Some(tts_rate) = tts_rate {
        avatar_program_arg(&mut program_args, "--tts-rate", tts_rate.to_string());
    }
    program_args.push("--json".to_string());

    let plist = avatar_heartbeat_plist(
        &label,
        &program_args,
        interval_secs,
        &stdout_path,
        &stderr_path,
    );
    if dry_run {
        print!("{plist}");
        return Ok(());
    }

    std::fs::create_dir_all(plist_path.parent().unwrap())
        .with_context(|| format!("create {}", plist_path.parent().unwrap().display()))?;
    std::fs::create_dir_all(stdout_path.parent().unwrap())
        .with_context(|| format!("create {}", stdout_path.parent().unwrap().display()))?;
    std::fs::write(&plist_path, plist)
        .with_context(|| format!("write {}", plist_path.display()))?;

    if no_load {
        println!("wrote {}", plist_path.display());
        println!("label={label}");
        println!("load=false");
        return Ok(());
    }

    let domain = avatar_launchd_domain()?;
    let _ = launchctl_status_quiet(&["bootout", &domain, plist_path.to_str().unwrap_or_default()]);
    run_launchctl(&[
        "bootstrap",
        &domain,
        plist_path.to_str().unwrap_or_default(),
    ])?;
    let target = format!("{domain}/{label}");
    run_launchctl(&["kickstart", "-k", &target])?;
    println!("installed avatar heartbeat");
    println!("label={label}");
    println!("plist={}", plist_path.display());
    println!("bin={}", bin.display());
    println!("interval_secs={interval_secs}");
    println!("stdout={}", stdout_path.display());
    println!("stderr={}", stderr_path.display());
    Ok(())
}

async fn run_avatar_remove_heartbeat(label: Option<String>, project: Option<String>) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let label = avatar_heartbeat_label(label, &project);
    let plist_path = avatar_launchd_plist_path(&label)?;
    let domain = avatar_launchd_domain()?;
    let _ = launchctl_status_quiet(&["bootout", &domain, plist_path.to_str().unwrap_or_default()]);
    if plist_path.exists() {
        std::fs::remove_file(&plist_path)
            .with_context(|| format!("remove {}", plist_path.display()))?;
    }
    println!("removed avatar heartbeat");
    println!("label={label}");
    println!("plist={}", plist_path.display());
    Ok(())
}

async fn run_avatar_heartbeat_status(label: Option<String>, project: Option<String>) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let label = avatar_heartbeat_label(label, &project);
    let domain = avatar_launchd_domain()?;
    let target = format!("{domain}/{label}");
    let output = std::process::Command::new("launchctl")
        .args(["print", &target])
        .output()
        .with_context(|| format!("launchctl print {target}"))?;
    if output.status.success() {
        println!("label={label}");
        print!("{}", String::from_utf8_lossy(&output.stdout));
    } else {
        println!("label={label}");
        println!("status=not_loaded");
        let stderr = String::from_utf8_lossy(&output.stderr);
        if !stderr.trim().is_empty() {
            println!("launchctl={}", stderr.trim());
        }
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_install_heartbeat_alert(
    label: Option<String>,
    project: Option<String>,
    bin: Option<PathBuf>,
    interval_secs: u64,
    stale_secs: i64,
    repeat_secs: i64,
    notification: bool,
    tts: bool,
    tts_voice: Option<String>,
    tts_rate: Option<u64>,
    no_load: bool,
    dry_run: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let label = avatar_heartbeat_alert_label(label, &project);
    let bin = match bin {
        Some(bin) => bin,
        None => avatar_default_heartbeat_bin()?,
    };
    let interval_secs = interval_secs.clamp(60, 3600);
    let stale_secs = stale_secs.clamp(30, 86_400);
    let repeat_secs = repeat_secs.clamp(0, 86_400);
    let plist_path = avatar_launchd_plist_path(&label)?;
    let stdout_path = avatar_launchd_log_path(&label, "out")?;
    let stderr_path = avatar_launchd_log_path(&label, "err")?;

    let mut program_args = vec![
        bin.display().to_string(),
        "avatar".to_string(),
        "heartbeat-alert".to_string(),
    ];
    avatar_program_arg(&mut program_args, "--project", project.clone());
    avatar_program_arg(&mut program_args, "--stale-secs", stale_secs.to_string());
    avatar_program_arg(&mut program_args, "--repeat-secs", repeat_secs.to_string());
    if !notification {
        program_args.push("--no-notification".to_string());
    }
    if tts {
        program_args.push("--tts".to_string());
    }
    if let Some(tts_voice) = tts_voice {
        avatar_program_arg(&mut program_args, "--tts-voice", tts_voice);
    }
    if let Some(tts_rate) = tts_rate {
        avatar_program_arg(&mut program_args, "--tts-rate", tts_rate.to_string());
    }
    program_args.push("--json".to_string());

    let plist = avatar_heartbeat_plist(
        &label,
        &program_args,
        interval_secs,
        &stdout_path,
        &stderr_path,
    );
    if dry_run {
        print!("{plist}");
        return Ok(());
    }

    std::fs::create_dir_all(plist_path.parent().unwrap())
        .with_context(|| format!("create {}", plist_path.parent().unwrap().display()))?;
    std::fs::create_dir_all(stdout_path.parent().unwrap())
        .with_context(|| format!("create {}", stdout_path.parent().unwrap().display()))?;
    std::fs::write(&plist_path, plist)
        .with_context(|| format!("write {}", plist_path.display()))?;

    if no_load {
        println!("wrote {}", plist_path.display());
        println!("label={label}");
        println!("load=false");
        return Ok(());
    }

    let domain = avatar_launchd_domain()?;
    let _ = launchctl_status_quiet(&["bootout", &domain, plist_path.to_str().unwrap_or_default()]);
    run_launchctl(&[
        "bootstrap",
        &domain,
        plist_path.to_str().unwrap_or_default(),
    ])?;
    let target = format!("{domain}/{label}");
    run_launchctl(&["kickstart", "-k", &target])?;
    println!("installed avatar heartbeat alert");
    println!("label={label}");
    println!("plist={}", plist_path.display());
    println!("bin={}", bin.display());
    println!("interval_secs={interval_secs}");
    println!("stale_secs={stale_secs}");
    println!("repeat_secs={repeat_secs}");
    println!("notification={notification}");
    println!("tts={tts}");
    println!("stdout={}", stdout_path.display());
    println!("stderr={}", stderr_path.display());
    Ok(())
}

async fn run_avatar_remove_heartbeat_alert(
    label: Option<String>,
    project: Option<String>,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let label = avatar_heartbeat_alert_label(label, &project);
    let plist_path = avatar_launchd_plist_path(&label)?;
    let domain = avatar_launchd_domain()?;
    let _ = launchctl_status_quiet(&["bootout", &domain, plist_path.to_str().unwrap_or_default()]);
    if plist_path.exists() {
        std::fs::remove_file(&plist_path)
            .with_context(|| format!("remove {}", plist_path.display()))?;
    }
    println!("removed avatar heartbeat alert");
    println!("label={label}");
    println!("plist={}", plist_path.display());
    Ok(())
}

async fn run_avatar_heartbeat_alert_status(
    label: Option<String>,
    project: Option<String>,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let label = avatar_heartbeat_alert_label(label, &project);
    let domain = avatar_launchd_domain()?;
    let target = format!("{domain}/{label}");
    let output = std::process::Command::new("launchctl")
        .args(["print", &target])
        .output()
        .with_context(|| format!("launchctl print {target}"))?;
    if output.status.success() {
        println!("label={label}");
        print!("{}", String::from_utf8_lossy(&output.stdout));
    } else {
        println!("label={label}");
        println!("status=not_loaded");
        let stderr = String::from_utf8_lossy(&output.stderr);
        if !stderr.trim().is_empty() {
            println!("launchctl={}", stderr.trim());
        }
    }
    Ok(())
}

fn avatar_records(value: &Value) -> &[Value] {
    value
        .get("records")
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or(&[])
}

fn write_avatar_seed_jsonl(path: &PathBuf, records: &[Value]) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
    }
    let mut out = String::new();
    for record in records {
        out.push_str(&serde_json::to_string(record)?);
        out.push('\n');
    }
    std::fs::write(path, out).with_context(|| format!("write {}", path.display()))
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_seed_events(
    label: Option<String>,
    project: Option<String>,
    input: Option<PathBuf>,
    limit: usize,
    include_preview: bool,
    output: Option<PathBuf>,
    print_jsonl: bool,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let opts = ab_bridge::avatar_seed::AvatarSeedEventsOptions {
        label: label.as_deref(),
        project: Some(&project),
        input: input.as_deref(),
        limit,
        include_preview,
    };
    let payload = ab_bridge::avatar_seed::avatar_seed_events(&opts)?;
    let records = avatar_records(&payload);
    if let Some(path) = output.as_ref() {
        write_avatar_seed_jsonl(path, records)?;
    }
    if print_jsonl {
        for record in records {
            println!("{}", serde_json::to_string(record)?);
        }
        return Ok(());
    }
    if as_json {
        let mut payload = payload;
        if let Some(path) = output.as_ref() {
            if let Some(obj) = payload.as_object_mut() {
                obj.insert("output_path".to_string(), json!(path.to_string_lossy()));
            }
        }
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("avatar seed events");
    println!(
        "project={} label={}",
        avatar_health_display(payload.get("project"), "agent-bridge"),
        avatar_health_display(payload.get("label"), "-")
    );
    println!(
        "events_path={} seen={} records={} preview_skips={} parse_skips={}",
        avatar_health_display(payload.get("events_path"), "-"),
        avatar_health_display(payload.get("events_seen"), "0"),
        avatar_health_display(payload.get("records_count"), "0"),
        avatar_health_display(payload.get("preview_skips"), "0"),
        avatar_health_display(payload.get("parse_skips"), "0")
    );
    println!(
        "substrate_input={} target={}",
        avatar_health_display(payload.get("substrate_input"), "-"),
        avatar_health_display(payload.get("target"), "-")
    );
    if let Some(path) = output.as_ref() {
        println!("output={}", path.display());
    }
    for (i, record) in records.iter().take(5).enumerate() {
        println!(
            "{:>2}. kind={} key={} ts={}",
            i + 1,
            avatar_health_display(record.get("kind"), "-"),
            avatar_health_display(record.get("key"), "-"),
            avatar_health_display(record.get("ts"), "-")
        );
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_cortex_replay(
    label: Option<String>,
    project: Option<String>,
    input: Option<PathBuf>,
    output: Option<PathBuf>,
    limit: usize,
    include_preview: bool,
    use_hash: bool,
    n: usize,
    d: usize,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let opts = ab_bridge::avatar_cortex::AvatarCortexReplayOptions {
        label: label.as_deref(),
        project: Some(&project),
        input: input.as_deref(),
        output: output.as_deref(),
        limit,
        include_preview,
        use_hash,
        n,
        d,
    };
    let payload = ab_bridge::avatar_cortex::avatar_cortex_replay(&opts)?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    println!("avatar cortex replay");
    println!(
        "cortex_id={} mode={} encoder={} n={} d={}",
        avatar_health_display(payload.get("cortex_id"), "xiao-shu"),
        avatar_health_display(payload.get("mode"), "shadow_only"),
        avatar_health_display(payload.get("encoder"), "hash"),
        avatar_health_display(payload.get("n"), "64"),
        avatar_health_display(payload.get("d"), "64")
    );
    println!(
        "records={} perceived={} skipped={} snapshot_rows={}",
        avatar_health_display(payload.get("records_count"), "0"),
        avatar_health_display(payload.get("perceived"), "0"),
        avatar_health_display(payload.get("skipped"), "0"),
        avatar_health_display(payload.get("snapshot_rows"), "0")
    );
    println!(
        "snapshot={} latest_long_fingerprint={}",
        avatar_health_display(payload.get("snapshot_path"), "-"),
        avatar_health_display(payload.get("latest_long_fingerprint"), "-")
    );
    println!(
        "global_substrate_mutated={} no_daemon_restart={} no_sibling_activation={}",
        avatar_health_display(payload.get("mutates_global_substrate"), "false"),
        avatar_health_display(
            payload
                .get("aiot_alignment")
                .and_then(|v| v.get("no_daemon_restart")),
            "true"
        ),
        avatar_health_display(
            payload
                .get("aiot_alignment")
                .and_then(|v| v.get("no_sibling_activation")),
            "true"
        )
    );
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_install_cortex_runner(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    bin: Option<PathBuf>,
    interval_secs: u64,
    output: Option<PathBuf>,
    limit: usize,
    include_preview: bool,
    use_hash: bool,
    n: usize,
    d: usize,
    no_load: bool,
    dry_run: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let label = avatar_cortex_runner_label(label, &project);
    let heartbeat_label = avatar_heartbeat_label(heartbeat_label, &project);
    let bin = match bin {
        Some(bin) => bin,
        None => avatar_default_heartbeat_bin()?,
    };
    let interval_secs = interval_secs.clamp(120, 86_400);
    let plist_path = avatar_launchd_plist_path(&label)?;
    let stdout_path = avatar_launchd_log_path(&label, "out")?;
    let stderr_path = avatar_launchd_log_path(&label, "err")?;

    let mut program_args = vec![
        bin.display().to_string(),
        "avatar".to_string(),
        "cortex-replay".to_string(),
    ];
    avatar_program_arg(&mut program_args, "--project", project.clone());
    avatar_program_arg(&mut program_args, "--label", heartbeat_label.clone());
    avatar_program_arg(&mut program_args, "--limit", limit.to_string());
    avatar_program_arg(&mut program_args, "--n", n.to_string());
    avatar_program_arg(&mut program_args, "--d", d.to_string());
    if include_preview {
        program_args.push("--include-preview".to_string());
    }
    if !use_hash {
        program_args.push("--onnx".to_string());
    }
    if let Some(output) = output.as_ref() {
        avatar_program_arg(&mut program_args, "--output", output.display().to_string());
    }
    program_args.push("--json".to_string());

    let plist = avatar_heartbeat_plist(
        &label,
        &program_args,
        interval_secs,
        &stdout_path,
        &stderr_path,
    );
    if dry_run {
        print!("{plist}");
        return Ok(());
    }

    std::fs::create_dir_all(plist_path.parent().unwrap())
        .with_context(|| format!("create {}", plist_path.parent().unwrap().display()))?;
    std::fs::create_dir_all(stdout_path.parent().unwrap())
        .with_context(|| format!("create {}", stdout_path.parent().unwrap().display()))?;
    std::fs::write(&plist_path, plist)
        .with_context(|| format!("write {}", plist_path.display()))?;

    if no_load {
        println!("wrote {}", plist_path.display());
        println!("label={label}");
        println!("load=false");
        return Ok(());
    }

    let domain = avatar_launchd_domain()?;
    let _ = launchctl_status_quiet(&["bootout", &domain, plist_path.to_str().unwrap_or_default()]);
    run_launchctl(&[
        "bootstrap",
        &domain,
        plist_path.to_str().unwrap_or_default(),
    ])?;
    let target = format!("{domain}/{label}");
    run_launchctl(&["kickstart", "-k", &target])?;
    println!("installed avatar cortex runner");
    println!("label={label}");
    println!("heartbeat_label={heartbeat_label}");
    println!("plist={}", plist_path.display());
    println!("bin={}", bin.display());
    println!("interval_secs={interval_secs}");
    println!("limit={limit}");
    println!("encoder={}", if use_hash { "hash" } else { "onnx" });
    println!("n={n}");
    println!("d={d}");
    if let Some(output) = output.as_ref() {
        println!("output={}", output.display());
    }
    println!("stdout={}", stdout_path.display());
    println!("stderr={}", stderr_path.display());
    Ok(())
}

async fn run_avatar_remove_cortex_runner(
    label: Option<String>,
    project: Option<String>,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let label = avatar_cortex_runner_label(label, &project);
    let plist_path = avatar_launchd_plist_path(&label)?;
    let domain = avatar_launchd_domain()?;
    let _ = launchctl_status_quiet(&["bootout", &domain, plist_path.to_str().unwrap_or_default()]);
    if plist_path.exists() {
        std::fs::remove_file(&plist_path)
            .with_context(|| format!("remove {}", plist_path.display()))?;
    }
    println!("removed avatar cortex runner");
    println!("label={label}");
    println!("plist={}", plist_path.display());
    Ok(())
}

async fn run_avatar_cortex_status(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_status(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let launchd = payload.get("launchd").unwrap_or(&Value::Null);
    let snapshot = payload.get("snapshot").unwrap_or(&Value::Null);
    let latest = snapshot.get("latest_long").unwrap_or(&Value::Null);
    println!("avatar cortex status");
    println!(
        "label={} loaded={} state={} runs={} last_exit_code={} interval_secs={}",
        avatar_health_display(payload.get("label"), "-"),
        avatar_health_display(launchd.get("loaded"), "false"),
        avatar_health_display(launchd.get("state"), "-"),
        avatar_health_display(launchd.get("runs"), "-"),
        avatar_health_display(launchd.get("last_exit_code"), "-"),
        avatar_health_display(launchd.get("run_interval_secs"), "-")
    );
    println!(
        "snapshot={} exists={} rows={} long_rows={} file_bytes={}",
        avatar_health_display(snapshot.get("path"), "-"),
        avatar_health_display(snapshot.get("exists"), "false"),
        avatar_health_display(snapshot.get("total_rows"), "0"),
        avatar_health_display(snapshot.get("long_rows"), "0"),
        avatar_health_display(snapshot.get("file_bytes"), "-")
    );
    println!(
        "latest_long_step={} fingerprint={}",
        avatar_health_display(latest.get("step"), "-"),
        avatar_health_display(latest.get("fingerprint"), "-")
    );
    Ok(())
}

async fn run_avatar_cortex_preview(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_voice_preview(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let learning = payload.get("learning_state").unwrap_or(&Value::Null);
    let policy = payload.get("behavior_policy").unwrap_or(&Value::Null);
    let preview = payload.get("preview").unwrap_or(&Value::Null);
    println!("avatar cortex voice preview");
    println!(
        "state={} reason={} badge={} action={}",
        avatar_health_display(learning.get("state"), "-"),
        avatar_health_display(learning.get("reason"), "-"),
        avatar_health_display(policy.get("badge"), "-"),
        avatar_health_display(policy.get("recommended_action"), "-")
    );
    println!(
        "would_say={} voice_allowed={} notification_allowed={} emits_audio={} emits_notification={}",
        avatar_health_display(preview.get("text"), "-"),
        avatar_health_display(preview.get("voice_allowed"), "false"),
        avatar_health_display(preview.get("notification_allowed"), "false"),
        avatar_health_display(payload.get("emits_audio"), "false"),
        avatar_health_display(payload.get("emits_notification"), "false")
    );
    println!(
        "gate={} voice_reason={} notification_reason={}",
        avatar_health_display(preview.get("requires_explicit_emit_gate"), "true"),
        avatar_health_display(preview.get("voice_reason"), "sparse_voice_policy"),
        avatar_health_display(preview.get("notification_reason"), "read_only_panel_policy")
    );
    Ok(())
}

async fn run_avatar_cortex_language(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_language_preview(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let language = payload.get("language").unwrap_or(&Value::Null);
    let slots = language.get("slots").unwrap_or(&Value::Null);
    let memory = language.get("memory").unwrap_or(&Value::Null);
    let safety = language.get("safety").unwrap_or(&Value::Null);
    let generator = language.get("generator").unwrap_or(&Value::Null);
    println!("avatar cortex language preview");
    println!(
        "line={}",
        avatar_health_display(language.get("utterance"), "-")
    );
    println!(
        "intent={} style={} state={} latest_status={}",
        avatar_health_display(language.get("intent"), "-"),
        avatar_health_display(language.get("style"), "-"),
        avatar_health_display(slots.get("state"), "-"),
        avatar_health_display(slots.get("latest_status"), "-")
    );
    println!(
        "memory={} window={} transitions={}",
        avatar_health_display(memory.get("summary"), "-"),
        avatar_health_display(memory.get("window_size"), "0"),
        avatar_health_display(memory.get("transition_count"), "0")
    );
    println!(
        "voice_allowed={} notification_allowed={} uses_llm={} uses_voice_model={}",
        avatar_health_display(safety.get("voice_allowed"), "false"),
        avatar_health_display(safety.get("notification_allowed"), "false"),
        avatar_health_display(generator.get("uses_llm"), "false"),
        avatar_health_display(generator.get("uses_voice_model"), "false")
    );
    Ok(())
}

async fn run_avatar_cortex_motion(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_motion_preview(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let motion = payload.get("motion").unwrap_or(&Value::Null);
    let hint = motion.get("animation_hint").unwrap_or(&Value::Null);
    let source = motion.get("source").unwrap_or(&Value::Null);
    let safety = motion.get("safety").unwrap_or(&Value::Null);
    println!("avatar cortex motion preview");
    println!(
        "gesture={} mood={} attention={}",
        avatar_health_display(motion.get("gesture"), "-"),
        avatar_health_display(motion.get("mood"), "-"),
        avatar_health_display(motion.get("attention"), "-")
    );
    println!(
        "animation={} intensity={} reason={}",
        avatar_health_display(hint.get("loop"), "-"),
        avatar_health_display(hint.get("intensity"), "-"),
        avatar_health_display(motion.get("reason"), "-")
    );
    println!(
        "state={} memory={} sidecar_only={} renderer_mapping={}",
        avatar_health_display(source.get("state"), "-"),
        avatar_health_display(source.get("memory_observation"), "-"),
        avatar_health_display(safety.get("sidecar_only"), "true"),
        avatar_health_display(safety.get("requires_renderer_mapping"), "true")
    );
    Ok(())
}

async fn run_avatar_cortex_renderer(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_renderer_preview(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let renderer = payload.get("renderer").unwrap_or(&Value::Null);
    let mapping = renderer.get("mapping").unwrap_or(&Value::Null);
    let evidence = mapping.get("evidence").unwrap_or(&Value::Null);
    let target = mapping.get("target").unwrap_or(&Value::Null);
    let safety = renderer.get("safety").unwrap_or(&Value::Null);
    println!("avatar cortex renderer preview");
    println!(
        "token={} resolved={}",
        avatar_health_display(mapping.get("input_token"), "-"),
        avatar_health_display(mapping.get("resolved"), "false")
    );
    println!(
        "pose={} expression={} motion={} accessory={}",
        avatar_health_display(target.get("pose_slot"), "-"),
        avatar_health_display(target.get("expression_slot"), "-"),
        avatar_health_display(target.get("motion_slot"), "-"),
        avatar_health_display(target.get("accessory_slot"), "-")
    );
    println!(
        "evidence_stage={} risk={} intent={}",
        avatar_health_display(evidence.get("binding_stage"), "-"),
        avatar_health_display(evidence.get("risk_level"), "-"),
        avatar_health_display(evidence.get("visual_intent"), "-")
    );
    println!(
        "dry_run={} writes_files={} mutates_renderer={} codex_pet_package_mutation={}",
        avatar_health_display(payload.get("dry_run"), "true"),
        avatar_health_display(safety.get("writes_files"), "false"),
        avatar_health_display(safety.get("mutates_renderer"), "false"),
        avatar_health_display(safety.get("codex_pet_package_mutation"), "false")
    );
    Ok(())
}

async fn run_avatar_cortex_renderer_registry(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_renderer_registry(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let registry = payload.get("registry").unwrap_or(&Value::Null);
    let current = registry.get("current").unwrap_or(&Value::Null);
    let stage_counts = registry.get("stage_counts").unwrap_or(&Value::Null);
    let risk_counts = registry.get("risk_counts").unwrap_or(&Value::Null);
    println!("avatar cortex renderer registry");
    println!(
        "known={} candidate={} needs_review={} fallback={}",
        avatar_health_display(registry.get("known_token_count"), "0"),
        avatar_health_display(stage_counts.get("candidate"), "0"),
        avatar_health_display(stage_counts.get("needs_review"), "0"),
        avatar_health_display(stage_counts.get("fallback_only"), "0")
    );
    println!(
        "risk_low={} risk_medium={} risk_high={}",
        avatar_health_display(risk_counts.get("low"), "0"),
        avatar_health_display(risk_counts.get("medium"), "0"),
        avatar_health_display(risk_counts.get("high"), "0")
    );
    println!(
        "current={} stage={} risk={}",
        avatar_health_display(current.get("token"), "-"),
        avatar_health_display(current.get("binding_stage"), "-"),
        avatar_health_display(current.get("risk_level"), "-")
    );
    Ok(())
}

async fn run_avatar_cortex_binding_plan(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_binding_plan(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let plan = payload.get("binding_plan").unwrap_or(&Value::Null);
    let first = plan.get("first_candidate").unwrap_or(&Value::Null);
    println!("avatar cortex binding plan");
    println!(
        "selected={} deferred={}",
        avatar_health_display(plan.get("selected_count"), "0"),
        avatar_health_display(plan.get("deferred_count"), "0")
    );
    println!(
        "first={} risk={}",
        avatar_health_display(first.get("token"), "-"),
        avatar_health_display(first.get("risk_level"), "-")
    );
    println!(
        "writes_files={} mutates_renderer={} pet_package={}",
        avatar_health_display(payload.get("writes_files"), "false"),
        avatar_health_display(payload.get("mutates_renderer"), "false"),
        avatar_health_display(payload.get("codex_pet_package_mutation"), "false")
    );
    Ok(())
}

async fn run_avatar_cortex_binding_fixture(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_binding_fixture(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let fixture = payload.get("fixture").unwrap_or(&Value::Null);
    let first = fixture.get("first_fixture").unwrap_or(&Value::Null);
    let first_assertions = first.get("golden_assertions").unwrap_or(&Value::Null);
    println!("avatar cortex binding fixture");
    println!(
        "fixtures={} source={}",
        avatar_health_display(fixture.get("fixture_count"), "0"),
        avatar_health_display(fixture.get("source"), "-")
    );
    println!(
        "first={} motion={} returns_idle={} duration_ms={}",
        avatar_health_display(first.get("token"), "-"),
        avatar_health_display(first_assertions.get("motion_slot"), "-"),
        avatar_health_display(first_assertions.get("returns_to_idle"), "false"),
        avatar_health_display(first_assertions.get("duration_ms"), "0")
    );
    println!(
        "writes_files={} mutates_renderer={} pet_package={}",
        avatar_health_display(payload.get("writes_files"), "false"),
        avatar_health_display(payload.get("mutates_renderer"), "false"),
        avatar_health_display(payload.get("codex_pet_package_mutation"), "false")
    );
    Ok(())
}

async fn run_avatar_cortex_visual_adapter(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_visual_adapter(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let adapter = payload.get("visual_adapter").unwrap_or(&Value::Null);
    let first = adapter.get("first_preview").unwrap_or(&Value::Null);
    let first_final = first.get("final_state").unwrap_or(&Value::Null);
    println!("avatar cortex visual adapter");
    println!(
        "previews={} input={}",
        avatar_health_display(adapter.get("preview_count"), "0"),
        avatar_health_display(adapter.get("input"), "-")
    );
    println!(
        "first={} frames={} final_motion={}",
        avatar_health_display(first.get("token"), "-"),
        avatar_health_display(first.get("frame_count"), "0"),
        avatar_health_display(first_final.get("motion_slot"), "-")
    );
    println!(
        "renders_pixels={} writes_files={} mutates_renderer={} pet_package={}",
        avatar_health_display(payload.get("renders_pixels"), "false"),
        avatar_health_display(payload.get("writes_files"), "false"),
        avatar_health_display(payload.get("mutates_renderer"), "false"),
        avatar_health_display(payload.get("codex_pet_package_mutation"), "false")
    );
    Ok(())
}

async fn run_avatar_cortex_renderer_view(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_renderer_view(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let view = payload.get("renderer_view").unwrap_or(&Value::Null);
    let first = view.get("first_track").unwrap_or(&Value::Null);
    println!("avatar cortex renderer view");
    println!(
        "tracks={} route={} input={}",
        avatar_health_display(view.get("track_count"), "0"),
        avatar_health_display(view.get("html_route"), "-"),
        avatar_health_display(view.get("input"), "-")
    );
    println!(
        "first={} frames={} browser_pixels={}",
        avatar_health_display(first.get("token"), "-"),
        avatar_health_display(first.get("frame_count"), "0"),
        avatar_health_display(payload.get("browser_renders_pixels"), "false")
    );
    println!(
        "writes_files={} mutates_renderer={} pet_package={}",
        avatar_health_display(payload.get("writes_files"), "false"),
        avatar_health_display(payload.get("mutates_renderer"), "false"),
        avatar_health_display(payload.get("codex_pet_package_mutation"), "false")
    );
    Ok(())
}

async fn run_avatar_cortex_review_gate(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_renderer_review_gate(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let gate = payload.get("review_gate").unwrap_or(&Value::Null);
    println!("avatar cortex review gate");
    println!(
        "tracks={} selected={} pending={} auto_pass={} blocked={}",
        avatar_health_display(gate.get("track_count"), "0"),
        avatar_health_display(gate.get("selected_baseline_count"), "0"),
        avatar_health_display(gate.get("manual_pending_count"), "0"),
        avatar_health_display(gate.get("automatic_pass_count"), "0"),
        avatar_health_display(gate.get("automatic_blocked_count"), "0")
    );
    println!(
        "manual_required={} can_promote_review={} mutates_bindings={}",
        avatar_health_display(
            gate.get("acceptance")
                .and_then(|acceptance| acceptance.get("manual_review_required")),
            "false"
        ),
        avatar_health_display(
            gate.get("acceptance")
                .and_then(|acceptance| acceptance.get("can_promote_review_tracks")),
            "false"
        ),
        avatar_health_display(
            gate.get("acceptance")
                .and_then(|acceptance| acceptance.get("review_tracks_mutate_bindings")),
            "false"
        )
    );
    if let Some(items) = gate.get("items").and_then(Value::as_array) {
        for item in items.iter().take(5) {
            println!(
                "- {} gate={} manual={} promote={}",
                avatar_health_display(item.get("token"), "-"),
                avatar_health_display(item.get("automatic_gate"), "-"),
                avatar_health_display(item.get("manual_decision"), "-"),
                avatar_health_display(item.get("can_promote_binding"), "false")
            );
        }
    }
    Ok(())
}

async fn run_avatar_cortex_review_packet(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_renderer_review_packet(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let packet = payload.get("review_packet").unwrap_or(&Value::Null);
    println!("avatar cortex review packet");
    println!(
        "packets={} baseline_refs={} pending={} approval_writes={} can_promote={}",
        avatar_health_display(packet.get("packet_count"), "0"),
        avatar_health_display(packet.get("baseline_reference_count"), "0"),
        avatar_health_display(packet.get("manual_pending_count"), "0"),
        avatar_health_display(
            packet
                .get("acceptance")
                .and_then(|acceptance| acceptance.get("approval_writes_allowed")),
            "false"
        ),
        avatar_health_display(
            packet
                .get("acceptance")
                .and_then(|acceptance| acceptance.get("can_promote_review_tracks")),
            "false"
        )
    );
    if let Some(items) = packet.get("packets").and_then(Value::as_array) {
        for item in items.iter().take(5) {
            println!(
                "- {} decision={} gate={} promote={} preview=track:{}",
                avatar_health_display(item.get("token"), "-"),
                avatar_health_display(item.get("default_decision"), "-"),
                avatar_health_display(item.get("automatic_gate"), "-"),
                avatar_health_display(item.get("can_promote_binding"), "false"),
                avatar_health_display(
                    item.get("renderer_view")
                        .and_then(|renderer| renderer.get("track")),
                    "-"
                )
            );
        }
    }
    Ok(())
}

async fn run_avatar_cortex_review_report(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_renderer_review_report(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let report = payload.get("review_report").unwrap_or(&Value::Null);
    println!("avatar cortex review report");
    println!(
        "state={} packets={} ready={} blocked={} feedback={} voice_requests={} human_decisions={} approved={} records={}",
        avatar_health_display(report.get("report_state"), "-"),
        avatar_health_display(report.get("packet_count"), "0"),
        avatar_health_display(report.get("ready_packet_count"), "0"),
        avatar_health_display(report.get("blocked_packet_count"), "0"),
        avatar_health_display(report.get("human_feedback_count"), "0"),
        avatar_health_display(report.get("voice_linkage_requested_count"), "0"),
        avatar_health_display(report.get("human_decision_count"), "0"),
        avatar_health_display(report.get("approved_count"), "0"),
        avatar_health_display(report.get("review_record_count"), "0")
    );
    println!(
        "ready_for_human_review={} ready_for_approval={} can_promote={} merge_without_review={}",
        avatar_health_display(
            report
                .get("acceptance")
                .and_then(|acceptance| acceptance.get("ready_for_human_visual_review")),
            "false"
        ),
        avatar_health_display(
            report
                .get("acceptance")
                .and_then(|acceptance| acceptance.get("ready_for_approval")),
            "false"
        ),
        avatar_health_display(
            report
                .get("acceptance")
                .and_then(|acceptance| acceptance.get("can_promote_review_tracks")),
            "false"
        ),
        avatar_health_display(
            report
                .get("acceptance")
                .and_then(|acceptance| acceptance.get("merge_without_human_review_allowed")),
            "false"
        )
    );
    if let Some(items) = report.get("items").and_then(Value::as_array) {
        for item in items.iter().take(5) {
            println!(
                "- {} readiness={} approval={} decision={} promote={}",
                avatar_health_display(item.get("token"), "-"),
                avatar_health_display(item.get("readiness"), "-"),
                avatar_health_display(item.get("ready_for_approval"), "false"),
                avatar_health_display(item.get("approval_state"), "-"),
                avatar_health_display(item.get("can_promote_binding"), "false")
            );
        }
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_cortex_review_decisions(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    track: Option<String>,
    decision: Option<String>,
    details: bool,
    limit: usize,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let opts = ab_bridge::avatar_cortex::AvatarCortexRendererReviewDecisionQueueOptions {
        label: label.as_deref(),
        heartbeat_label: heartbeat_label.as_deref(),
        project: Some(&project),
        output: output.as_deref(),
        track: track.as_deref(),
        decision: decision.as_deref(),
        include_details: details,
        limit,
    };
    let payload = ab_bridge::avatar_cortex::avatar_cortex_renderer_review_decisions(&opts)?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    let ledger = payload.get("ledger").unwrap_or(&Value::Null);
    println!("avatar cortex review decisions");
    println!(
        "project={} exists={} path={}",
        avatar_health_display(ledger.get("project"), &project),
        avatar_health_display(ledger.get("exists"), "false"),
        avatar_health_display(ledger.get("path"), "-")
    );
    println!(
        "filter track={} decision={} details={} limit={} parsed={} matching={} returned={} parse_errors={}",
        avatar_health_display(ledger.get("track_filter"), "-"),
        avatar_health_display(ledger.get("decision_filter"), "-"),
        avatar_health_display(ledger.get("include_details"), "false"),
        avatar_health_display(ledger.get("limit"), "20"),
        avatar_health_display(ledger.get("parsed_records"), "0"),
        avatar_health_display(ledger.get("matching_records"), "0"),
        avatar_health_display(ledger.get("returned_count"), "0"),
        avatar_health_display(ledger.get("parse_errors"), "0")
    );
    println!(
        "writes_approval={} can_promote={} mutates_renderer={} pet_package={}",
        avatar_health_display(payload.get("writes_approval"), "false"),
        avatar_health_display(
            payload
                .get("acceptance")
                .and_then(|acceptance| acceptance.get("can_promote_review_tracks")),
            "false"
        ),
        avatar_health_display(payload.get("mutates_renderer"), "false"),
        avatar_health_display(payload.get("codex_pet_package_mutation"), "false")
    );
    if let Some(records) = payload.get("records").and_then(Value::as_array) {
        for record in records {
            println!(
                "- {} track={} decision={} actor={} approval={}",
                avatar_health_display(record.get("decision_id"), "-"),
                avatar_health_display(record.get("track"), "-"),
                avatar_health_display(record.get("decision"), "-"),
                avatar_health_display(record.get("actor"), "-"),
                avatar_health_display(record.get("approval_state"), "not_approved")
            );
        }
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_cortex_review_decision(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    actor: String,
    track: String,
    decision: String,
    note: Option<String>,
    evidence: Option<String>,
    confirm: bool,
    details: bool,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let opts = ab_bridge::avatar_cortex::AvatarCortexRendererReviewDecisionOptions {
        label: label.as_deref(),
        heartbeat_label: heartbeat_label.as_deref(),
        project: Some(&project),
        output: output.as_deref(),
        actor: Some(actor.as_str()),
        track: Some(track.as_str()),
        decision: Some(decision.as_str()),
        note: note.as_deref(),
        evidence: evidence.as_deref(),
        confirm,
        include_details: details,
    };
    let payload = ab_bridge::avatar_cortex::avatar_cortex_renderer_review_decision(&opts)?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    let decision_payload = payload.get("decision").unwrap_or(&Value::Null);
    println!("avatar cortex review decision");
    println!(
        "track={} decision={} actor={} confirm={} blocked={} recorded={}",
        avatar_health_display(decision_payload.get("track"), "-"),
        avatar_health_display(decision_payload.get("decision"), "-"),
        avatar_health_display(decision_payload.get("actor"), "-"),
        avatar_health_display(decision_payload.get("confirm_requested"), "false"),
        avatar_health_display(decision_payload.get("blocked"), "true"),
        avatar_health_display(decision_payload.get("recorded"), "false")
    );
    println!(
        "reasons={} writes_record={} writes_approval={} can_promote={} mutates_renderer={}",
        avatar_health_display_list(decision_payload.get("blocked_reasons"), "none"),
        avatar_health_display(payload.get("writes_review_record"), "false"),
        avatar_health_display(payload.get("writes_approval"), "false"),
        avatar_health_display(
            payload
                .get("acceptance")
                .and_then(|acceptance| acceptance.get("can_promote_review_tracks")),
            "false"
        ),
        avatar_health_display(payload.get("mutates_renderer"), "false")
    );
    println!(
        "ledger={} next={}",
        avatar_health_display(decision_payload.get("ledger_path"), "-"),
        avatar_health_display(payload.get("next_step"), "-")
    );
    Ok(())
}

async fn run_avatar_cortex_review_record(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    track: String,
    variant: Option<String>,
    outcome: AvatarReviewOutcome,
    reviewer: String,
    reason: Option<String>,
    notes: Vec<String>,
    confirm: bool,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let opts = ab_bridge::avatar_cortex::AvatarCortexReviewRecordOptions {
        label: label.as_deref(),
        heartbeat_label: heartbeat_label.as_deref(),
        project: Some(&project),
        output: output.as_deref(),
        requested_track: Some(track.as_str()),
        requested_variant: variant.as_deref(),
        outcome: Some(outcome.as_str()),
        reviewer: Some(reviewer.as_str()),
        reason: reason.as_deref(),
        notes: notes.as_slice(),
        confirm,
    };
    let payload = ab_bridge::avatar_cortex::avatar_cortex_renderer_review_record(&opts)?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    println!("avatar cortex review record");
    println!(
        "track={} variant={} outcome={} confirmed={} blocked={} wrote_record={} approval_write={}",
        avatar_health_display(payload.get("track"), "-"),
        avatar_health_display(payload.get("variant"), "-"),
        avatar_health_display(payload.get("outcome"), "-"),
        avatar_health_display(payload.get("confirmed"), "false"),
        avatar_health_display(payload.get("blocked"), "true"),
        avatar_health_display(payload.get("persists_review_record"), "false"),
        avatar_health_display(payload.get("writes_approval"), "false")
    );
    if let Some(reasons) = payload.get("blocked_reasons").and_then(Value::as_array) {
        if !reasons.is_empty() {
            println!("blocked_reasons={}", serde_json::to_string(reasons)?);
        }
    }
    println!(
        "record_path={}",
        avatar_health_display(payload.get("record_path"), "-")
    );
    println!(
        "next={}",
        avatar_health_display(payload.get("next_step"), "-")
    );
    Ok(())
}

async fn run_avatar_cortex_voice_policy(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_voice_policy(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let policy = payload.get("voice_policy").unwrap_or(&Value::Null);
    println!("avatar cortex voice policy");
    println!(
        "tracks={} manual_cli_emit={} display_only={} auto_emit={} http_emit_route_added={}",
        avatar_health_display(policy.get("track_count"), "0"),
        avatar_health_display(policy.get("manual_cli_emit_count"), "0"),
        avatar_health_display(policy.get("display_only_count"), "0"),
        avatar_health_display(policy.get("auto_emit_count"), "0"),
        avatar_health_display(payload.get("http_emit_route_added"), "false")
    );
    println!(
        "default_voice={} rate={} cooldown={} real_emit={}",
        avatar_health_display(policy.get("default_voice"), "-"),
        avatar_health_display(policy.get("default_rate"), "-"),
        avatar_health_display(policy.get("default_cooldown_secs"), "300"),
        avatar_health_display(
            policy
                .get("gate")
                .and_then(|gate| gate.get("real_emit_surface")),
            "-"
        )
    );
    if let Some(rules) = policy.get("rules").and_then(Value::as_array) {
        for rule in rules.iter().take(8) {
            println!(
                "- {} mode={} manual_cli={} utterance={} variant={}",
                avatar_health_display(rule.get("token"), "-"),
                avatar_health_display(rule.get("mode"), "-"),
                avatar_health_display(rule.get("manual_cli_emit_allowed"), "false"),
                avatar_health_display(rule.get("utterance"), "-"),
                avatar_health_display(rule.get("visual_variant"), "-")
            );
        }
    }
    Ok(())
}

async fn run_avatar_cortex_voice_request(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    track: Option<String>,
    reason: Option<String>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_voice_request(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
        track.as_deref(),
        reason.as_deref(),
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let request = payload.get("voice_request").unwrap_or(&Value::Null);
    println!("avatar cortex voice request");
    println!(
        "state={} token={} manual_cli={} auto_emit={} emits_audio={} http_emit_route={}",
        avatar_health_display(request.get("request_state"), "-"),
        avatar_health_display(request.get("selected_token"), "-"),
        avatar_health_display(request.get("manual_cli_emit_allowed"), "false"),
        avatar_health_display(request.get("auto_emit_allowed"), "false"),
        avatar_health_display(payload.get("emits_audio"), "false"),
        avatar_health_display(request.get("http_emit_route"), "null")
    );
    println!(
        "line={} voice={} rate={} reason_present={} cooldown={}",
        avatar_health_display(request.get("line"), "-"),
        avatar_health_display(request.get("suggested_voice"), "-"),
        avatar_health_display(request.get("suggested_rate"), "-"),
        avatar_health_display(request.get("operator_reason_present"), "false"),
        avatar_health_display(request.get("cooldown_secs"), "300")
    );
    println!(
        "second_step={} cli_only={} command={}",
        avatar_health_display(request.get("requires_second_step"), "true"),
        avatar_health_display(
            request
                .get("safety")
                .and_then(|safety| safety.get("cli_only_real_emit")),
            "true"
        ),
        avatar_health_display(request.get("command_preview"), "-")
    );
    Ok(())
}

async fn run_avatar_cortex_voice_confirm(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    track: Option<String>,
    reason: Option<String>,
    confirm: bool,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let payload = ab_bridge::avatar_cortex::avatar_cortex_voice_confirm(
        label.as_deref(),
        heartbeat_label.as_deref(),
        Some(&project),
        output.as_deref(),
        track.as_deref(),
        reason.as_deref(),
        confirm,
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let confirm = payload.get("voice_confirm").unwrap_or(&Value::Null);
    println!("avatar cortex voice confirm dry-run");
    println!(
        "state={} confirm_requested={} would_execute_cli={} emits_audio={} http_emit_route={}",
        avatar_health_display(confirm.get("confirmation_state"), "-"),
        avatar_health_display(confirm.get("confirm_requested"), "false"),
        avatar_health_display(confirm.get("would_execute_cli"), "false"),
        avatar_health_display(payload.get("emits_audio"), "false"),
        avatar_health_display(confirm.get("http_emit_route"), "null")
    );
    println!(
        "token={} line={} reason_present={} voice={} rate={}",
        avatar_health_display(confirm.get("selected_token"), "-"),
        avatar_health_display(confirm.get("line"), "-"),
        avatar_health_display(confirm.get("operator_reason_present"), "false"),
        avatar_health_display(confirm.get("suggested_voice"), "-"),
        avatar_health_display(confirm.get("suggested_rate"), "-")
    );
    println!(
        "actual_execution_here={} command={}",
        avatar_health_display(confirm.get("actual_execution_available_here"), "false"),
        avatar_health_display(confirm.get("command_preview"), "-")
    );
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_cortex_voice_action(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    track: Option<String>,
    reason: Option<String>,
    confirm: bool,
    emit: bool,
    force: bool,
    cooldown_secs: i64,
    tts_voice: Option<String>,
    tts_rate: Option<u64>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let opts = ab_bridge::avatar_cortex::AvatarCortexVoiceActionOptions {
        label: label.as_deref(),
        heartbeat_label: heartbeat_label.as_deref(),
        project: Some(&project),
        output: output.as_deref(),
        requested_track: track.as_deref(),
        reason: reason.as_deref(),
        confirm,
        emit,
        force,
        cooldown_secs,
        tts_voice: tts_voice.as_deref(),
        tts_rate,
    };
    let payload = ab_bridge::avatar_cortex::avatar_cortex_voice_action(&opts)?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let action = payload.get("action").unwrap_or(&Value::Null);
    let emit_payload = payload.get("source_voice_emit").unwrap_or(&Value::Null);
    let tts = emit_payload.get("tts").unwrap_or(&Value::Null);
    println!("avatar cortex voice action");
    println!(
        "state={} confirm={} emit={} actual_emit_invoked={} emitted={} emits_audio={}",
        avatar_health_display(action.get("confirmation_state"), "-"),
        avatar_health_display(action.get("confirm_flag"), "false"),
        avatar_health_display(action.get("emit_flag"), "false"),
        avatar_health_display(payload.get("actual_emit_invoked"), "false"),
        avatar_health_display(payload.get("emitted"), "false"),
        avatar_health_display(payload.get("emits_audio"), "false")
    );
    println!(
        "blocked={} reasons={} token={} line={}",
        avatar_health_display(action.get("blocked"), "true"),
        avatar_health_display_list(action.get("blocked_reasons"), "none"),
        avatar_health_display(action.get("selected_token"), "-"),
        avatar_health_display(action.get("line"), "-")
    );
    println!(
        "tts_ok={} voice={} rate={} command={}",
        avatar_health_display(tts.get("ok"), "-"),
        avatar_health_display(action.get("tts_voice"), "-"),
        avatar_health_display(action.get("tts_rate"), "-"),
        avatar_health_display(action.get("command_preview"), "-")
    );
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_cortex_voice_action_preview(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    track: Option<String>,
    reason: Option<String>,
    confirm: bool,
    force: bool,
    cooldown_secs: i64,
    tts_voice: Option<String>,
    tts_rate: Option<u64>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let opts = ab_bridge::avatar_cortex::AvatarCortexVoiceActionPreviewOptions {
        label: label.as_deref(),
        heartbeat_label: heartbeat_label.as_deref(),
        project: Some(&project),
        output: output.as_deref(),
        requested_track: track.as_deref(),
        reason: reason.as_deref(),
        confirm,
        force,
        cooldown_secs,
        tts_voice: tts_voice.as_deref(),
        tts_rate,
    };
    let payload = ab_bridge::avatar_cortex::avatar_cortex_voice_action_preview(&opts)?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let action = payload.get("action_preview").unwrap_or(&Value::Null);
    let gate = payload.get("gate_dry_run").unwrap_or(&Value::Null);
    let cooldown = gate.get("cooldown").unwrap_or(&Value::Null);
    println!("avatar cortex voice action preview");
    println!(
        "state={} confirm={} ready={} would_emit_audio={} emits_audio={} http_emit_route=false",
        avatar_health_display(action.get("confirmation_state"), "-"),
        avatar_health_display(action.get("confirm_flag"), "false"),
        avatar_health_display(action.get("ready_to_emit_now"), "false"),
        avatar_health_display(action.get("would_emit_if_operator_runs_command"), "false"),
        avatar_health_display(payload.get("emits_audio"), "false")
    );
    println!(
        "blocked={} reasons={} token={} line={}",
        avatar_health_display(action.get("blocked"), "true"),
        avatar_health_display_list(action.get("blocked_reasons"), "none"),
        avatar_health_display(action.get("selected_token"), "-"),
        avatar_health_display(action.get("line"), "-")
    );
    println!(
        "cooldown_active={} last_emit_at={} next_allowed_at={} command={}",
        avatar_health_display(cooldown.get("active"), "false"),
        avatar_health_display(cooldown.get("last_emit_at"), "-"),
        avatar_health_display(cooldown.get("next_allowed_at"), "-"),
        avatar_health_display(action.get("command_preview"), "-")
    );
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_xiao_shu_action_request(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    actor: String,
    intent: String,
    message: Option<String>,
    track: Option<String>,
    reason: Option<String>,
    confirm: bool,
    enqueue: bool,
    force: bool,
    cooldown_secs: i64,
    tts_voice: Option<String>,
    tts_rate: Option<u64>,
    details: bool,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let opts = ab_bridge::avatar_cortex::XiaoShuActionRequestOptions {
        label: label.as_deref(),
        heartbeat_label: heartbeat_label.as_deref(),
        project: Some(&project),
        output: output.as_deref(),
        actor: Some(actor.as_str()),
        intent: Some(intent.as_str()),
        message: message.as_deref(),
        requested_track: track.as_deref(),
        reason: reason.as_deref(),
        confirm: if enqueue { false } else { confirm },
        force,
        cooldown_secs,
        tts_voice: tts_voice.as_deref(),
        tts_rate,
        include_details: details,
    };
    let payload = if enqueue {
        ab_bridge::avatar_cortex::xiao_shu_action_request_enqueue(&opts)?
    } else {
        ab_bridge::avatar_cortex::xiao_shu_action_request(&opts)?
    };
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    if enqueue {
        if payload
            .get("enqueue_blocked")
            .and_then(Value::as_bool)
            .unwrap_or(false)
        {
            println!("xiao shu action request enqueue blocked");
            println!(
                "reasons={} emits_audio={} direct_control={} writes_request_record={}",
                avatar_health_display(payload.get("blocked_reasons"), "-"),
                avatar_health_display(payload.get("emits_audio"), "false"),
                avatar_health_display(payload.get("direct_pet_control_allowed"), "false"),
                avatar_health_display(payload.get("writes_request_record"), "false")
            );
            return Ok(());
        }
        let record = payload.get("record").unwrap_or(&Value::Null);
        let queue = payload.get("queue").unwrap_or(&Value::Null);
        let request = record.get("action_request").unwrap_or(&Value::Null);
        println!("xiao shu action request enqueued");
        println!(
            "request_id={} state={} queue={} emits_audio={} direct_control={}",
            avatar_health_display(record.get("request_id"), "-"),
            avatar_health_display(record.get("state"), "-"),
            avatar_health_display(queue.get("path"), "-"),
            avatar_health_display(payload.get("emits_audio"), "false"),
            avatar_health_display(payload.get("direct_pet_control_allowed"), "false")
        );
        println!(
            "track={} cue={} line={}",
            avatar_health_display(record.get("mapped_track"), "-"),
            avatar_health_display(record.get("cue_id"), "-"),
            avatar_health_display(record.get("line").or_else(|| request.get("line")), "-")
        );
        println!(
            "confirm={} emit={}",
            avatar_health_display(record.get("local_confirm_command"), "-"),
            avatar_health_display(record.get("local_emit_command"), "-")
        );
        return Ok(());
    }
    let request = payload.get("action_request").unwrap_or(&Value::Null);
    println!("xiao shu action request");
    println!(
        "state={} actor={} intent={} supported={} direct_control={} emits_audio={}",
        avatar_health_display(request.get("request_state"), "-"),
        avatar_health_display(request.get("actor"), "-"),
        avatar_health_display(request.get("intent"), "-"),
        avatar_health_display(request.get("supported_intent"), "false"),
        avatar_health_display(payload.get("direct_pet_control_allowed"), "false"),
        avatar_health_display(payload.get("emits_audio"), "false")
    );
    println!(
        "confirmation_required={} confirmed={} ready={} blocked={} reasons={}",
        avatar_health_display(request.get("requires_human_confirmation"), "true"),
        avatar_health_display(request.get("human_confirmation_present"), "false"),
        avatar_health_display(request.get("ready_for_local_cli_emit"), "false"),
        avatar_health_display(request.get("blocked"), "true"),
        avatar_health_display_list(request.get("blocked_reasons"), "none")
    );
    println!(
        "track={} line={} command={}",
        avatar_health_display(request.get("mapped_track"), "-"),
        avatar_health_display(request.get("line"), "-"),
        avatar_health_display(request.get("emit_command"), "-")
    );
    Ok(())
}

async fn run_xiao_shu_action_requests(
    project: Option<String>,
    request_id: Option<String>,
    state: Option<String>,
    all_states: bool,
    details: bool,
    limit: usize,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let opts = ab_bridge::avatar_cortex::XiaoShuActionRequestQueueOptions {
        project: Some(&project),
        request_id: request_id.as_deref(),
        state: state.as_deref(),
        include_all_states: all_states,
        include_details: details,
        limit,
    };
    let payload = ab_bridge::avatar_cortex::xiao_shu_action_request_queue(&opts)?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    let queue = payload.get("queue").unwrap_or(&Value::Null);
    println!("xiao shu action requests");
    println!(
        "project={} exists={} path={}",
        avatar_health_display(queue.get("project"), &project),
        avatar_health_display(queue.get("exists"), "false"),
        avatar_health_display(queue.get("path"), "-")
    );
    println!(
        "filter request_id={} state={} all_states={} details={} limit={} parsed={} matching={} returned={} parse_errors={}",
        avatar_health_display(queue.get("request_id_filter"), "-"),
        avatar_health_display(queue.get("state_filter"), "-"),
        avatar_health_display(queue.get("include_all_states"), "false"),
        avatar_health_display(queue.get("include_details"), "false"),
        avatar_health_display(queue.get("limit"), "20"),
        avatar_health_display(queue.get("parsed_records"), "0"),
        avatar_health_display(queue.get("matching_records"), "0"),
        avatar_health_display(queue.get("returned_count"), "0"),
        avatar_health_display(queue.get("parse_errors"), "0")
    );
    if let Some(records) = payload.get("records").and_then(Value::as_array) {
        for record in records {
            println!(
                "- {} state={} actor={} intent={} track={} line={}",
                avatar_health_display(record.get("request_id"), "-"),
                avatar_health_display(record.get("state"), "-"),
                avatar_health_display(record.get("actor"), "-"),
                avatar_health_display(record.get("intent"), "-"),
                avatar_health_display(record.get("mapped_track"), "-"),
                avatar_health_display(
                    record
                        .get("action_request")
                        .and_then(|request| request.get("line")),
                    "-"
                )
            );
        }
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_xiao_shu_action_request_action(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    request_id: String,
    reason: Option<String>,
    confirm: bool,
    emit: bool,
    dismiss: bool,
    force: bool,
    cooldown_secs: i64,
    tts_voice: Option<String>,
    tts_rate: Option<u64>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let opts = ab_bridge::avatar_cortex::XiaoShuActionRequestActionOptions {
        label: label.as_deref(),
        heartbeat_label: heartbeat_label.as_deref(),
        project: Some(&project),
        output: output.as_deref(),
        request_id: Some(request_id.as_str()),
        reason: reason.as_deref(),
        confirm,
        emit,
        dismiss,
        force,
        cooldown_secs,
        tts_voice: tts_voice.as_deref(),
        tts_rate,
    };
    let payload = ab_bridge::avatar_cortex::xiao_shu_action_request_action(&opts)?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    let action_payload = payload.get("action").unwrap_or(&Value::Null);
    let action = action_payload.get("action").unwrap_or(&Value::Null);
    let queue = payload.get("queue").unwrap_or(&Value::Null);
    println!("xiao shu action request action");
    println!(
        "request_id={} state={} prior_state={} pending_before={} confirm={} emit={} dismiss={}",
        avatar_health_display(payload.get("request_id"), "-"),
        avatar_health_display(payload.get("state"), "-"),
        avatar_health_display(payload.get("prior_state"), "-"),
        avatar_health_display(payload.get("pending_before_action"), "false"),
        avatar_health_display(payload.get("confirm_requested"), "false"),
        avatar_health_display(payload.get("emit_requested"), "false"),
        avatar_health_display(payload.get("dismiss_requested"), "false")
    );
    println!(
        "actual_emit_invoked={} would_emit={} emitted={} dismissed={} emits_audio={} writes_request_record={}",
        avatar_health_display(payload.get("actual_emit_invoked"), "false"),
        avatar_health_display(payload.get("would_emit"), "false"),
        avatar_health_display(payload.get("emitted"), "false"),
        avatar_health_display(payload.get("dismissed"), "false"),
        avatar_health_display(payload.get("emits_audio"), "false"),
        avatar_health_display(payload.get("writes_request_record"), "false")
    );
    println!(
        "blocked={} reasons={} token={} line={}",
        avatar_health_display(action.get("blocked"), "true"),
        avatar_health_display_list(action.get("blocked_reasons"), "none"),
        avatar_health_display(action.get("selected_token"), "-"),
        avatar_health_display(action.get("line"), "-")
    );
    println!(
        "queue={} next={}",
        avatar_health_display(queue.get("path"), "-"),
        avatar_health_display(payload.get("next_step"), "-")
    );
    Ok(())
}

async fn run_avatar_cortex_voice_gate(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    preview_text: Option<String>,
    enabled: bool,
    force: bool,
    cooldown_secs: i64,
    reason: Option<String>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let opts = ab_bridge::avatar_cortex::AvatarCortexVoiceGateOptions {
        label: label.as_deref(),
        heartbeat_label: heartbeat_label.as_deref(),
        project: Some(&project),
        output: output.as_deref(),
        preview_text: preview_text.as_deref(),
        enabled,
        force,
        cooldown_secs,
        reason: reason.as_deref(),
    };
    let payload = ab_bridge::avatar_cortex::avatar_cortex_voice_gate_dry_run(&opts)?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let gate = payload.get("gate").unwrap_or(&Value::Null);
    let required = payload.get("required").unwrap_or(&Value::Null);
    let cooldown = payload.get("cooldown").unwrap_or(&Value::Null);
    let preview = payload.get("preview").unwrap_or(&Value::Null);
    println!("avatar cortex voice gate dry-run");
    println!(
        "enabled={} force={} dry_run={} would_emit={} emits_audio={} emits_notification={}",
        avatar_health_display(gate.get("enabled"), "false"),
        avatar_health_display(gate.get("force"), "false"),
        avatar_health_display(payload.get("dry_run"), "true"),
        avatar_health_display(payload.get("would_emit"), "false"),
        avatar_health_display(payload.get("emits_audio"), "false"),
        avatar_health_display(payload.get("emits_notification"), "false")
    );
    println!(
        "blocked={} reasons={} preview={}",
        avatar_health_display(gate.get("blocked"), "true"),
        avatar_health_display_list(gate.get("blocked_reasons"), "none"),
        avatar_health_display(preview.get("text"), "-")
    );
    println!(
        "required enabled={} reason_present={} voice_policy_allowed={} cooldown_clear={}",
        avatar_health_display(required.get("explicit_enabled"), "false"),
        avatar_health_display(required.get("operator_reason_present"), "false"),
        avatar_health_display(required.get("voice_policy_allowed"), "false"),
        avatar_health_display(required.get("cooldown_clear"), "false")
    );
    println!(
        "operator_reason={} cooldown_secs={} cooldown_active={}",
        avatar_health_display(gate.get("operator_reason"), "-"),
        avatar_health_display(cooldown.get("cooldown_secs"), "300"),
        avatar_health_display(cooldown.get("active"), "false")
    );
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_cortex_voice_emit(
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<PathBuf>,
    preview_text: Option<String>,
    enabled: bool,
    force: bool,
    cooldown_secs: i64,
    reason: Option<String>,
    allow_policy_override: bool,
    tts_voice: Option<String>,
    tts_rate: Option<u64>,
    as_json: bool,
) -> Result<()> {
    let cwd = avatar_current_cwd()?;
    let project = avatar_project_slug(project, &cwd);
    let opts = ab_bridge::avatar_cortex::AvatarCortexVoiceEmitOptions {
        label: label.as_deref(),
        heartbeat_label: heartbeat_label.as_deref(),
        project: Some(&project),
        output: output.as_deref(),
        preview_text: preview_text.as_deref(),
        enabled,
        force,
        cooldown_secs,
        reason: reason.as_deref(),
        allow_policy_override,
        tts_voice: tts_voice.as_deref(),
        tts_rate,
    };
    let payload = ab_bridge::avatar_cortex::avatar_cortex_voice_emit(&opts)?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let gate = payload.get("gate").unwrap_or(&Value::Null);
    let tts = payload.get("tts").unwrap_or(&Value::Null);
    println!("avatar cortex voice emit");
    println!(
        "enabled={} policy_override={} would_emit={} emitted={} emits_audio={}",
        avatar_health_display(gate.get("gate").and_then(|v| v.get("enabled")), "false"),
        avatar_health_display(
            gate.get("gate")
                .and_then(|v| v.get("allow_policy_override")),
            "false"
        ),
        avatar_health_display(payload.get("would_emit"), "false"),
        avatar_health_display(payload.get("emitted"), "false"),
        avatar_health_display(payload.get("emits_audio"), "false")
    );
    println!(
        "blocked={} reasons={} preview={}",
        avatar_health_display(gate.get("gate").and_then(|v| v.get("blocked")), "true"),
        avatar_health_display_list(
            gate.get("gate").and_then(|v| v.get("blocked_reasons")),
            "none"
        ),
        avatar_health_display(gate.get("preview").and_then(|v| v.get("text")), "-")
    );
    println!(
        "tts_ok={} voice={} rate={}",
        avatar_health_display(tts.get("ok"), "-"),
        avatar_health_display(tts.get("voice"), "-"),
        avatar_health_display(tts.get("rate"), "-")
    );
    println!(
        "state={} events={}",
        avatar_health_display(payload.get("state_path"), "-"),
        avatar_health_display(payload.get("events_path"), "-")
    );
    Ok(())
}

fn avatar_health_display(value: Option<&Value>, fallback: &str) -> String {
    match value {
        Some(Value::String(s)) if !s.is_empty() => s.clone(),
        Some(Value::Number(n)) => n.to_string(),
        Some(Value::Bool(b)) => b.to_string(),
        _ => fallback.to_string(),
    }
}

fn avatar_health_display_list(value: Option<&Value>, fallback: &str) -> String {
    match value.and_then(Value::as_array) {
        Some(items) if !items.is_empty() => items
            .iter()
            .filter_map(Value::as_str)
            .collect::<Vec<_>>()
            .join(","),
        _ => fallback.to_string(),
    }
}

async fn run_avatar_heartbeat_health(
    label: Option<String>,
    project: Option<String>,
    stale_secs: i64,
    as_json: bool,
) -> Result<()> {
    let store = SqliteStore::open(&default_db_path())
        .await
        .context("open state.db")?;
    let payload = ab_bridge::avatar_health::heartbeat_health(
        &store,
        label.as_deref(),
        project.as_deref(),
        stale_secs,
    )
    .await?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    let launchd = payload.get("launchd").unwrap_or(&Value::Null);
    let binary = payload.get("binary").unwrap_or(&Value::Null);
    let presence = payload.get("presence").unwrap_or(&Value::Null);
    println!("avatar heartbeat health");
    println!(
        "status={} healthy={} project={} label={}",
        avatar_health_display(payload.get("status"), "unknown"),
        avatar_health_display(payload.get("healthy"), "false"),
        avatar_health_display(payload.get("project"), "agent-bridge"),
        avatar_health_display(payload.get("label"), "-")
    );
    println!(
        "summary={}",
        avatar_health_display(payload.get("summary"), "-")
    );
    println!(
        "launchd.loaded={} state={} runs={} last_exit_code={} interval_secs={}",
        avatar_health_display(launchd.get("loaded"), "false"),
        avatar_health_display(launchd.get("state"), "-"),
        avatar_health_display(launchd.get("runs"), "-"),
        avatar_health_display(launchd.get("last_exit_code"), "-"),
        avatar_health_display(launchd.get("run_interval_secs"), "-")
    );
    println!(
        "binary.path={} exists={} supports_sync_presence={} supports_heartbeat_health={} missing_command={}",
        avatar_health_display(binary.get("path"), "-"),
        avatar_health_display(binary.get("exists"), "false"),
        avatar_health_display(binary.get("supports_sync_presence"), "false"),
        avatar_health_display(binary.get("supports_heartbeat_health"), "false"),
        avatar_health_display(binary.get("missing_command"), "false")
    );
    println!(
        "presence.exists={} fresh={} age_secs={} heartbeat={}",
        avatar_health_display(presence.get("exists"), "false"),
        avatar_health_display(presence.get("fresh"), "false"),
        avatar_health_display(presence.get("age_secs"), "-"),
        avatar_health_display(presence.get("last_heartbeat_at"), "-")
    );
    if let Some(avatar) = presence.get("avatar").filter(|v| !v.is_null()) {
        println!(
            "avatar.runtime={} avatar_id={} mode={} activity={} focus={}",
            avatar_health_display(avatar.get("runtime"), "unknown-runtime"),
            avatar_health_display(avatar.get("avatar_id"), "unknown-avatar"),
            avatar_health_display(avatar.get("mode"), "unknown"),
            avatar_health_display(avatar.get("activity_state"), "-"),
            avatar_health_display(avatar.get("focus"), "-")
        );
    }
    println!(
        "plist={} stdout={} stderr={}",
        avatar_health_display(launchd.get("plist_path"), "-"),
        avatar_health_display(launchd.get("stdout_path"), "-"),
        avatar_health_display(launchd.get("stderr_path"), "-")
    );
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_heartbeat_alert(
    label: Option<String>,
    project: Option<String>,
    stale_secs: i64,
    force: bool,
    preview: bool,
    notification: bool,
    tts: bool,
    repeat_secs: i64,
    tts_voice: Option<String>,
    tts_rate: Option<u64>,
    as_json: bool,
) -> Result<()> {
    let store = SqliteStore::open(&default_db_path())
        .await
        .context("open state.db")?;
    let opts = ab_bridge::avatar_alert::HeartbeatAlertOptions {
        label: label.as_deref(),
        project: project.as_deref(),
        stale_secs,
        force,
        preview,
        notification,
        tts,
        repeat_secs,
        tts_voice: tts_voice.as_deref(),
        tts_rate,
    };
    let payload = ab_bridge::avatar_alert::heartbeat_alert(&store, &opts).await?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }
    let event = payload.get("event").unwrap_or(&Value::Null);
    let health = event.get("health").unwrap_or(&Value::Null);
    println!("avatar heartbeat alert");
    println!(
        "status={} healthy={} emitted={} reason={}",
        avatar_health_display(health.get("status"), "unknown"),
        avatar_health_display(health.get("healthy"), "false"),
        avatar_health_display(event.get("emitted"), "false"),
        avatar_health_display(event.get("reason"), "-")
    );
    println!(
        "event_key={}",
        avatar_health_display(event.get("event_key"), "-")
    );
    println!(
        "state={} events={}",
        avatar_health_display(payload.get("state_path"), "-"),
        avatar_health_display(payload.get("events_path"), "-")
    );
    Ok(())
}

async fn run_biocortex_shadow_digest(
    checkout: Option<PathBuf>,
    benchmark: String,
    timeout_ms: u64,
    include_raw: bool,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_shadow_digest(BioCortexShadowOptions {
        checkout,
        benchmark,
        timeout_ms,
        include_raw,
        fixture_projection: None,
    })
    .await;

    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex shadow digest");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!("status={}", shadow_json_display(payload.get("status"), "-"));
    println!(
        "benchmark={} example={}",
        shadow_json_display(payload.get("benchmark"), "-"),
        shadow_json_display(payload.get("example"), "-")
    );
    if let Some(path) = payload.get("checkout_path") {
        println!("checkout={}", shadow_json_display(Some(path), "-"));
    }
    if let Some(reason) = payload.get("reason").or_else(|| payload.get("error")) {
        println!("reason={}", shadow_json_display(Some(reason), "-"));
    }

    let summary = payload.get("summary").unwrap_or(&Value::Null);
    println!(
        "verdict={} demonstrated={}",
        shadow_json_display(summary.get("verdict"), "-"),
        shadow_json_display(summary.get("demonstrated"), "false")
    );
    println!(
        "demonstrated_keys={}",
        shadow_json_display(summary.get("demonstrated_keys"), "[]")
    );
    println!(
        "failed_predicates={}",
        shadow_json_display(summary.get("failed_predicates"), "[]")
    );
    println!(
        "open_limitations={}",
        shadow_json_display(summary.get("open_limitations"), "[]")
    );
    println!("supported_benchmarks={}", supported_benchmarks().join(","));

    let boundary = payload.get("boundary").unwrap_or(&Value::Null);
    println!(
        "boundary=shadow_only links_runtime={} mutates_ab_memory={} mutates_retrieval={}",
        shadow_json_display(boundary.get("links_biocortex_into_ab_runtime"), "false"),
        shadow_json_display(boundary.get("mutates_ab_memory"), "false"),
        shadow_json_display(boundary.get("changes_retrieval_vector"), "false")
    );
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_biocortex_replay_compare(
    window_days: u32,
    source: &str,
    fixture_out: Option<&std::path::Path>,
    fixture_in: Option<&std::path::Path>,
    checkout: Option<PathBuf>,
    benchmark: String,
    timeout_ms: u64,
    include_raw: bool,
    include_events: bool,
    as_json: bool,
) -> Result<()> {
    let db_path = default_db_path();
    let fixture = if let Some(path) = fixture_in {
        let body = std::fs::read_to_string(path)
            .map_err(|e| anyhow::anyhow!("read BioCortex replay fixture at {path:?}: {e}"))?;
        serde_json::from_str::<ab_shadow_cortex::ShadowCortexReplayFixture>(&body)
            .map_err(|e| anyhow::anyhow!("parse BioCortex replay fixture at {path:?}: {e}"))?
    } else {
        let store = SqliteStore::open(&db_path)
            .await
            .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;
        ab_shadow_cortex::collect_shadow_cortex_fixture(
            &store,
            ab_shadow_cortex::ShadowCortexOptions {
                window_days,
                source: source.to_string(),
            },
        )
        .await?
    };

    if let Some(path) = fixture_out {
        let body = serde_json::to_string_pretty(&fixture)?;
        std::fs::write(path, body)
            .map_err(|e| anyhow::anyhow!("write BioCortex replay fixture at {path:?}: {e}"))?;
    }

    let payload = biocortex_replay_comparison(
        &fixture,
        BioCortexReplayComparisonOptions {
            checkout,
            benchmark,
            timeout_ms,
            include_raw,
            include_events,
        },
    )
    .await;

    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    let projection = payload.get("ab_fixture_projection").unwrap_or(&Value::Null);
    let comparison = payload.get("comparison").unwrap_or(&Value::Null);
    let digest = payload
        .get("biocortex_shadow_digest")
        .unwrap_or(&Value::Null);
    println!("# BioCortex replay comparison");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!("status={}", shadow_json_display(payload.get("status"), "-"));
    println!(
        "fixture_events={} fixture_hash={}",
        shadow_json_display(projection.get("event_count"), "0"),
        shadow_json_display(projection.get("fixture_hash"), "-")
    );
    println!(
        "fixture_sources={} recommended_benchmark={}",
        shadow_json_display(projection.get("sources"), "[]"),
        shadow_json_display(projection.get("recommended_benchmark"), "-")
    );
    println!(
        "biocortex_status={} benchmark={} demonstrated={}",
        shadow_json_display(digest.get("status"), "-"),
        shadow_json_display(digest.get("benchmark"), "-"),
        shadow_json_display(digest.pointer("/summary/demonstrated"), "false")
    );
    println!(
        "alignment={} consumes_ab_events={} retrieval_mutation={}",
        shadow_json_display(comparison.get("benchmark_alignment"), "-"),
        shadow_json_display(
            comparison.get("current_adapter_consumes_ab_events"),
            "false"
        ),
        shadow_json_display(comparison.get("retrieval_mutation"), "false")
    );
    println!(
        "next={}",
        shadow_json_display(comparison.get("next_step"), "-")
    );
    Ok(())
}

async fn run_biocortex_retrieval_approval_packet(
    opts: BioCortexRetrievalApprovalPacketOptions,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_retrieval_runtime_approval_packet_preview(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval runtime approval packet preview");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "approval_state={} default_decision={}",
        shadow_json_display(payload.get("approval_state"), "-"),
        shadow_json_display(payload.get("default_decision"), "-")
    );
    println!(
        "runtime_adapter_approved={} approval_writes_allowed={} default_search_order_change_allowed={}",
        shadow_json_display(payload.get("runtime_adapter_approved"), "false"),
        shadow_json_display(payload.get("approval_writes_allowed"), "false"),
        shadow_json_display(payload.get("default_search_order_change_allowed"), "false")
    );
    println!(
        "requires_separate_human_approval={} ready_for_human_approval_review={}",
        shadow_json_display(payload.get("requires_separate_human_approval"), "true"),
        shadow_json_display(payload.get("ready_for_human_approval_review"), "false")
    );
    let attestation = payload
        .get("agent_technical_attestation")
        .unwrap_or(&Value::Null);
    let authorization = payload.get("human_authorization").unwrap_or(&Value::Null);
    println!(
        "agent_attestation_decision={} agent_can_authorize_runtime_influence={}",
        shadow_json_display(attestation.get("decision"), "-"),
        shadow_json_display(attestation.get("can_authorize_runtime_influence"), "false")
    );
    println!(
        "human_authorization_status={} human_authorization_scope={}",
        shadow_json_display(authorization.get("status"), "not_authorized"),
        shadow_json_display(authorization.get("scope"), "-")
    );
    let gates = payload.get("gates").unwrap_or(&Value::Null);
    println!(
        "gates feature_enabled={} runtime_enabled={} operator_disabled={}",
        shadow_json_display(gates.get("compile_feature_enabled"), "false"),
        shadow_json_display(gates.get("runtime_enabled"), "false"),
        shadow_json_display(gates.get("operator_disabled"), "false")
    );
    let missing_count = payload
        .get("missing_evidence")
        .and_then(Value::as_array)
        .map(Vec::len)
        .unwrap_or(0);
    println!("missing_evidence_count={missing_count}");
    if let Some(paths) = payload.get("missing_evidence").and_then(Value::as_array) {
        for path in paths.iter().take(8).filter_map(Value::as_str) {
            println!("missing={path}");
        }
        if paths.len() > 8 {
            println!("missing=...{} more", paths.len() - 8);
        }
    }
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_status(
    opts: BioCortexRetrievalOptInAuditOptions,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_retrieval_opt_in_audit_report(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in status");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "mode={} mode_authorized={} implementation_stage={}",
        shadow_json_display(payload.get("mode"), "-"),
        shadow_json_display(payload.get("mode_authorized"), "false"),
        shadow_json_display(payload.get("implementation_stage"), "-")
    );
    let gate = payload.get("gate").unwrap_or(&Value::Null);
    println!(
        "gate_status={} gate_ready={} per_call_opt_in={}",
        shadow_json_display(gate.get("status"), "-"),
        shadow_json_display(gate.get("ready_for_explicit_opt_in_experiment"), "false"),
        shadow_json_display(
            payload
                .get("per_call_opt_in")
                .and_then(|value| value.get("present")),
            "false"
        )
    );
    println!(
        "runtime_enabled={} operator_disabled={}",
        shadow_json_display(gate.get("runtime_enabled"), "false"),
        shadow_json_display(gate.get("operator_disabled"), "false")
    );
    let baseline = payload.get("baseline_order").unwrap_or(&Value::Null);
    println!(
        "baseline_key_count={} baseline_hash={} raw_keys_included={} content_included={}",
        shadow_json_display(baseline.get("key_count"), "0"),
        shadow_json_display(baseline.get("hash"), "-"),
        shadow_json_display(baseline.get("raw_keys_included"), "false"),
        shadow_json_display(baseline.get("content_included"), "false")
    );
    let fallback = payload.get("fallback").unwrap_or(&Value::Null);
    println!(
        "returned_order={} fallback_reason={}",
        shadow_json_display(
            payload
                .get("returned_order")
                .and_then(|value| value.get("source")),
            "baseline"
        ),
        shadow_json_display(fallback.get("reason"), "-")
    );
    println!(
        "ordering_behavior_connected={} may_change_search_order_now={} changes_memory_search_order={}",
        shadow_json_display(payload.get("ordering_behavior_connected"), "false"),
        shadow_json_display(payload.get("may_change_search_order_now"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_dry_run(
    opts: BioCortexRetrievalOptInDryRunOptions,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_retrieval_opt_in_dry_run_plan(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in dry run");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "mode={} mode_authorized={} dry_run={} implementation_stage={}",
        shadow_json_display(payload.get("mode"), "-"),
        shadow_json_display(payload.get("mode_authorized"), "false"),
        shadow_json_display(payload.get("dry_run"), "true"),
        shadow_json_display(payload.get("implementation_stage"), "-")
    );
    let baseline = payload.get("baseline_order").unwrap_or(&Value::Null);
    println!(
        "baseline_completed={} baseline_key_count={} baseline_hash={} raw_keys_included={} content_included={}",
        shadow_json_display(baseline.get("completed"), "false"),
        shadow_json_display(baseline.get("key_count"), "0"),
        shadow_json_display(baseline.get("hash"), "-"),
        shadow_json_display(baseline.get("raw_keys_included"), "false"),
        shadow_json_display(baseline.get("content_included"), "false")
    );
    let planner = payload.get("planner_result").unwrap_or(&Value::Null);
    println!(
        "returned_order={} fallback_reason={} execution_ready={}",
        shadow_json_display(planner.get("returned_order_source"), "baseline"),
        shadow_json_display(planner.get("fallback_reason"), "-"),
        shadow_json_display(planner.get("execution_ready"), "false")
    );
    let side_signal = payload.get("planned_side_signal").unwrap_or(&Value::Null);
    println!(
        "side_signal_status={} timeout_ms={} coverage_threshold={} runs_biocortex={}",
        shadow_json_display(side_signal.get("status"), "-"),
        shadow_json_display(side_signal.get("timeout_ms"), "-"),
        shadow_json_display(side_signal.get("coverage_threshold"), "-"),
        shadow_json_display(payload.get("runs_biocortex"), "false")
    );
    println!(
        "calls_memory_search={} ordering_behavior_connected={} changes_memory_search_order={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("ordering_behavior_connected"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_review_packet(
    dry_run_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInReviewPacketOptions,
    as_json: bool,
) -> Result<()> {
    let body = std::fs::read_to_string(dry_run_json)
        .map_err(|e| anyhow::anyhow!("read dry-run JSON at {dry_run_json:?}: {e}"))?;
    opts.dry_run_plan = serde_json::from_str(&body)
        .map_err(|e| anyhow::anyhow!("parse dry-run JSON at {dry_run_json:?}: {e}"))?;
    let payload = biocortex_retrieval_opt_in_review_packet(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in review packet");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "review_ready={} approval_state={} may_implement_ordering_now={}",
        shadow_json_display(
            payload
                .get("boundary_check")
                .and_then(|value| value.get("review_ready")),
            "false"
        ),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("may_implement_ordering_now"), "false")
    );
    let target = payload.get("review_target").unwrap_or(&Value::Null);
    println!(
        "mode={} mode_authorized={} commit={}",
        shadow_json_display(target.get("mode"), "-"),
        shadow_json_display(target.get("mode_authorized"), "false"),
        shadow_json_display(target.get("commit"), "-")
    );
    let summary = payload.get("dry_run_summary").unwrap_or(&Value::Null);
    let baseline = summary.get("baseline_order").unwrap_or(&Value::Null);
    let planner = summary.get("planner_result").unwrap_or(&Value::Null);
    println!(
        "baseline_key_count={} baseline_hash={} returned_order={} fallback_reason={}",
        shadow_json_display(baseline.get("key_count"), "0"),
        shadow_json_display(baseline.get("hash"), "-"),
        shadow_json_display(planner.get("returned_order_source"), "baseline"),
        shadow_json_display(planner.get("fallback_reason"), "-")
    );
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "violations={}",
        boundary
            .get("violations")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_execution_packet(
    review_packet_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInExecutionPacketOptions,
    as_json: bool,
) -> Result<()> {
    let body = std::fs::read_to_string(review_packet_json)
        .map_err(|e| anyhow::anyhow!("read review-packet JSON at {review_packet_json:?}: {e}"))?;
    opts.review_packet = serde_json::from_str(&body)
        .map_err(|e| anyhow::anyhow!("parse review-packet JSON at {review_packet_json:?}: {e}"))?;
    let payload = biocortex_retrieval_opt_in_execution_packet(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in execution packet");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "execution_allowed={} approval_state={} may_change_search_order_now={}",
        shadow_json_display(
            payload
                .get("preflight")
                .and_then(|value| value.get("execution_allowed")),
            "false"
        ),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("may_change_search_order_now"), "false")
    );
    let attempt = payload.get("attempt").unwrap_or(&Value::Null);
    println!(
        "attempt_id={} mode={} per_call_opt_in={}",
        shadow_json_display(attempt.get("attempt_id"), "-"),
        shadow_json_display(attempt.get("mode"), "-"),
        shadow_json_display(attempt.get("per_call_opt_in"), "false")
    );
    let preflight = payload.get("preflight").unwrap_or(&Value::Null);
    println!(
        "baseline_preflight={} fallback_reason={} packet_blockers={} store_blockers={}",
        shadow_json_display(
            preflight.get("preflight_passed_for_baseline_only_contract"),
            "false"
        ),
        shadow_json_display(preflight.get("fallback_reason"), "-"),
        preflight
            .get("packet_blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string()),
        preflight
            .get("store_blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    let execution = payload.get("execution_decision").unwrap_or(&Value::Null);
    println!(
        "returned_order={} baseline_returned={} calls_memory_search={} runs_biocortex={}",
        shadow_json_display(execution.get("returned_order_source"), "baseline"),
        shadow_json_display(execution.get("baseline_returned"), "true"),
        shadow_json_display(execution.get("calls_memory_search_now"), "false"),
        shadow_json_display(execution.get("runs_biocortex_now"), "false")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_runtime_trial(
    execution_packet_json: &std::path::Path,
    query: Option<String>,
    input_json: Option<&std::path::Path>,
    candidates_json: Option<&std::path::Path>,
    expected_key: Option<String>,
    mut opts: BioCortexRetrievalOptInRuntimeTrialOptions,
    as_json: bool,
) -> Result<()> {
    let packet_body = std::fs::read_to_string(execution_packet_json).map_err(|e| {
        anyhow::anyhow!("read execution-packet JSON at {execution_packet_json:?}: {e}")
    })?;
    opts.execution_packet = serde_json::from_str(&packet_body).map_err(|e| {
        anyhow::anyhow!("parse execution-packet JSON at {execution_packet_json:?}: {e}")
    })?;

    let mut resolved_query = query;
    let mut resolved_expected = expected_key;
    let candidates = if let Some(path) = input_json {
        let body = std::fs::read_to_string(path)
            .map_err(|e| anyhow::anyhow!("read BioCortex trial input at {path:?}: {e}"))?;
        let value: Value = serde_json::from_str(&body)
            .map_err(|e| anyhow::anyhow!("parse BioCortex trial input at {path:?}: {e}"))?;
        if resolved_query.is_none() {
            resolved_query = value
                .get("query")
                .and_then(Value::as_str)
                .map(str::to_string);
        }
        if resolved_expected.is_none() {
            resolved_expected = value
                .get("expected_key")
                .and_then(Value::as_str)
                .map(str::to_string);
        }
        let candidate_value = value
            .get("candidates")
            .cloned()
            .unwrap_or_else(|| value.clone());
        serde_json::from_value::<Vec<BioCortexRetrievalCandidate>>(candidate_value)
            .map_err(|e| anyhow::anyhow!("parse candidates in {path:?}: {e}"))?
    } else if let Some(path) = candidates_json {
        let body = std::fs::read_to_string(path)
            .map_err(|e| anyhow::anyhow!("read BioCortex candidates at {path:?}: {e}"))?;
        serde_json::from_str::<Vec<BioCortexRetrievalCandidate>>(&body)
            .map_err(|e| anyhow::anyhow!("parse BioCortex candidates at {path:?}: {e}"))?
    } else {
        anyhow::bail!("provide --input-json or --candidates-json");
    };
    opts.query = resolved_query
        .map(|q| q.trim().to_string())
        .filter(|q| !q.is_empty())
        .ok_or_else(|| anyhow::anyhow!("provide --query or query in --input-json"))?;
    opts.candidates = candidates;
    opts.expected_key = resolved_expected;

    let payload = biocortex_retrieval_opt_in_runtime_trial(opts).await;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in runtime trial");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "runtime_trial={} approval_state={} returned_order={}",
        shadow_json_display(payload.get("runtime_trial"), "true"),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(
            payload
                .get("returned_order")
                .and_then(|value| value.get("source")),
            "baseline"
        )
    );
    let preflight = payload.get("runtime_preflight").unwrap_or(&Value::Null);
    println!(
        "trial_allowed={} blockers={} gate_ready={}",
        shadow_json_display(preflight.get("side_signal_trial_allowed"), "false"),
        preflight
            .get("blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string()),
        shadow_json_display(preflight.get("gate_ready"), "false")
    );
    let side_signal = payload.get("side_signal").unwrap_or(&Value::Null);
    println!(
        "side_signal_status={} attempted={} coverage={} latency_ms={}",
        shadow_json_display(side_signal.get("status"), "-"),
        shadow_json_display(side_signal.get("attempted"), "false"),
        shadow_json_display(side_signal.get("coverage"), "0"),
        shadow_json_display(side_signal.get("latency_ms"), "0")
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_runtime_trial_review_packet(
    runtime_trial_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions,
    as_json: bool,
) -> Result<()> {
    let body = std::fs::read_to_string(runtime_trial_json)
        .map_err(|e| anyhow::anyhow!("read runtime-trial JSON at {runtime_trial_json:?}: {e}"))?;
    opts.runtime_trial = serde_json::from_str(&body)
        .map_err(|e| anyhow::anyhow!("parse runtime-trial JSON at {runtime_trial_json:?}: {e}"))?;
    let payload = biocortex_retrieval_opt_in_runtime_trial_review_packet(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in runtime trial review packet");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "review_ready={} approval_state={} may_implement_ordering_now={}",
        shadow_json_display(
            boundary.get("review_ready_for_baseline_runtime_trial"),
            "false"
        ),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("may_implement_ordering_now"), "false")
    );
    let target = payload.get("review_target").unwrap_or(&Value::Null);
    println!(
        "mode={} per_call_opt_in={} commit={}",
        shadow_json_display(target.get("mode"), "-"),
        shadow_json_display(target.get("per_call_opt_in"), "false"),
        shadow_json_display(target.get("commit"), "-")
    );
    let summary = payload.get("runtime_trial_summary").unwrap_or(&Value::Null);
    let side_signal = summary.get("side_signal").unwrap_or(&Value::Null);
    println!(
        "side_signal_status={} attempted={} coverage={} latency_ms={}",
        shadow_json_display(side_signal.get("status"), "-"),
        shadow_json_display(side_signal.get("attempted"), "false"),
        shadow_json_display(side_signal.get("coverage"), "0"),
        shadow_json_display(side_signal.get("latency_ms"), "0")
    );
    let returned = summary.get("returned_order").unwrap_or(&Value::Null);
    println!(
        "returned_order={} baseline_returned={} violations={}",
        shadow_json_display(returned.get("source"), "baseline"),
        shadow_json_display(returned.get("baseline_returned"), "true"),
        boundary
            .get("violations")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_order_diff_packet(
    source_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInOrderDiffPacketOptions,
    as_json: bool,
) -> Result<()> {
    let body = std::fs::read_to_string(source_json)
        .map_err(|e| anyhow::anyhow!("read order-diff source JSON at {source_json:?}: {e}"))?;
    opts.source_packet = serde_json::from_str(&body)
        .map_err(|e| anyhow::anyhow!("parse order-diff source JSON at {source_json:?}: {e}"))?;
    let payload = biocortex_retrieval_opt_in_order_diff_packet(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in order diff packet");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "diff_ready={} approval_state={} may_implement_ordering_now={}",
        shadow_json_display(boundary.get("diff_ready"), "false"),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("may_implement_ordering_now"), "false")
    );
    let comparison = payload.get("order_comparison").unwrap_or(&Value::Null);
    let hash_diff = comparison.get("hash_diff").unwrap_or(&Value::Null);
    println!(
        "order_hash_changed={} top_key_changed={} order_hashes_comparable={}",
        shadow_json_display(hash_diff.get("order_hash_changed"), "-"),
        shadow_json_display(hash_diff.get("top_key_changed"), "-"),
        shadow_json_display(hash_diff.get("order_hashes_comparable"), "false")
    );
    let expected = comparison.get("expected_key_rank").unwrap_or(&Value::Null);
    println!(
        "expected_rank_delta={} direction={} regressed={}",
        shadow_json_display(expected.get("rank_delta_advisory_minus_baseline"), "-"),
        shadow_json_display(expected.get("direction"), "unknown"),
        shadow_json_display(expected.get("regressed"), "false")
    );
    let returned = comparison.get("returned_order").unwrap_or(&Value::Null);
    println!(
        "returned_order={} actual_return_order_changed={} violations={}",
        shadow_json_display(returned.get("source"), "baseline"),
        shadow_json_display(returned.get("actual_return_order_changed"), "false"),
        boundary
            .get("violations")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_redacted_order_artifact(
    source_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInRedactedOrderArtifactOptions,
    as_json: bool,
) -> Result<()> {
    let body = std::fs::read_to_string(source_json).map_err(|e| {
        anyhow::anyhow!("read redacted-order artifact source JSON at {source_json:?}: {e}")
    })?;
    opts.source_packet = serde_json::from_str(&body).map_err(|e| {
        anyhow::anyhow!("parse redacted-order artifact source JSON at {source_json:?}: {e}")
    })?;
    let payload = biocortex_retrieval_opt_in_redacted_order_artifact(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in redacted order artifact");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "artifact_ready={} approval_state={} may_implement_ordering_now={}",
        shadow_json_display(boundary.get("artifact_ready"), "false"),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("may_implement_ordering_now"), "false")
    );
    let comparison = payload
        .get("redacted_order_comparison")
        .unwrap_or(&Value::Null);
    let distribution = comparison
        .get("rank_delta_distribution")
        .unwrap_or(&Value::Null);
    println!(
        "improved={} regressed={} unchanged={} max_abs_delta={}",
        shadow_json_display(distribution.get("improved_count"), "0"),
        shadow_json_display(distribution.get("regressed_count"), "0"),
        shadow_json_display(distribution.get("unchanged_count"), "0"),
        shadow_json_display(distribution.get("max_abs_delta"), "0")
    );
    let overlap_k1 = comparison
        .get("top_k_overlap")
        .and_then(Value::as_array)
        .and_then(|rows| {
            rows.iter()
                .find(|row| row.get("k").and_then(Value::as_u64) == Some(1))
        })
        .unwrap_or(&Value::Null);
    println!(
        "top1_overlap={} top1_jaccard={} redacted_rows_comparable={} violations={}",
        shadow_json_display(overlap_k1.get("overlap_count"), "0"),
        shadow_json_display(overlap_k1.get("jaccard"), "-"),
        shadow_json_display(boundary.get("redacted_rows_comparable"), "false"),
        boundary
            .get("violations")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_authorization_decision_packet(
    authorization_request_json: &std::path::Path,
    authorization_decision_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInAuthorizationDecisionPacketOptions,
    as_json: bool,
) -> Result<()> {
    let request_body = std::fs::read_to_string(authorization_request_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in authorization request JSON at {authorization_request_json:?}: {e}"
        )
    })?;
    opts.authorization_request = serde_json::from_str(&request_body).map_err(|e| {
        anyhow::anyhow!(
            "parse opt-in authorization request JSON at {authorization_request_json:?}: {e}"
        )
    })?;
    let decision_body = std::fs::read_to_string(authorization_decision_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in authorization decision JSON at {authorization_decision_json:?}: {e}"
        )
    })?;
    opts.authorization_decision = serde_json::from_str(&decision_body).map_err(|e| {
        anyhow::anyhow!(
            "parse opt-in authorization decision JSON at {authorization_decision_json:?}: {e}"
        )
    })?;
    let payload = biocortex_retrieval_opt_in_authorization_decision_packet(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in authorization decision packet");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "implementation_authorized={} approval_state={} authorization_state={}",
        shadow_json_display(boundary.get("implementation_authorized"), "false"),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("authorization_state"), "not_authorized")
    );
    println!(
        "runtime_adapter_approved={} default_search_order_change_allowed={} may_implement_ordering_now={}",
        shadow_json_display(payload.get("runtime_adapter_approved"), "false"),
        shadow_json_display(payload.get("default_search_order_change_allowed"), "false"),
        shadow_json_display(payload.get("may_implement_ordering_now"), "false")
    );
    let authorized = payload
        .get("authorized_implementation")
        .unwrap_or(&Value::Null);
    println!(
        "fts_only={} per_call_surface={} post_review_required={}",
        shadow_json_display(
            authorized.get("may_affect_only_explicitly_opted_in_fts_calls"),
            "false"
        ),
        shadow_json_display(authorized.get("may_add_per_call_opt_in_surface"), "false"),
        shadow_json_display(
            authorized.get("requires_post_implementation_review_before_use"),
            "true"
        )
    );
    println!(
        "blockers={} calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        boundary
            .get("blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string()),
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_post_implementation_review_gate(
    authorization_decision_packet_json: &std::path::Path,
    opt_in_plan_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInPostImplementationReviewGateOptions,
    as_json: bool,
) -> Result<()> {
    let packet_body = std::fs::read_to_string(authorization_decision_packet_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in authorization decision packet JSON at {authorization_decision_packet_json:?}: {e}"
        )
    })?;
    opts.authorization_decision_packet = serde_json::from_str(&packet_body).map_err(|e| {
        anyhow::anyhow!(
            "parse opt-in authorization decision packet JSON at {authorization_decision_packet_json:?}: {e}"
        )
    })?;
    let plan_body = std::fs::read_to_string(opt_in_plan_json).map_err(|e| {
        anyhow::anyhow!("read opt-in experiment plan JSON at {opt_in_plan_json:?}: {e}")
    })?;
    opts.opt_in_plan = serde_json::from_str(&plan_body).map_err(|e| {
        anyhow::anyhow!("parse opt-in experiment plan JSON at {opt_in_plan_json:?}: {e}")
    })?;
    let payload = biocortex_retrieval_opt_in_post_implementation_review_gate(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in post-implementation review gate");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "ready_for_human_runtime_influence_review={} review_state={} approval_state={}",
        shadow_json_display(
            boundary.get("ready_for_human_runtime_influence_review"),
            "false"
        ),
        shadow_json_display(payload.get("review_state"), "blocked"),
        shadow_json_display(payload.get("approval_state"), "not_approved")
    );
    println!(
        "runtime_adapter_approved={} default_search_order_change_allowed={} ordering_behavior_connected={}",
        shadow_json_display(payload.get("runtime_adapter_approved"), "false"),
        shadow_json_display(payload.get("default_search_order_change_allowed"), "false"),
        shadow_json_display(payload.get("ordering_behavior_connected"), "false")
    );
    println!(
        "blockers={} calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        boundary
            .get("blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string()),
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_runtime_influence_review_request(
    post_implementation_review_gate_json: &std::path::Path,
    redacted_order_artifact_json: &std::path::Path,
    redacted_evidence_aggregate_json: Option<&std::path::Path>,
    evidence_summary_json: Option<&std::path::Path>,
    mut opts: BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions,
    as_json: bool,
) -> Result<()> {
    let gate_body = std::fs::read_to_string(post_implementation_review_gate_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in post-implementation review gate JSON at {post_implementation_review_gate_json:?}: {e}"
        )
    })?;
    opts.post_implementation_review_gate = serde_json::from_str(&gate_body).map_err(|e| {
        anyhow::anyhow!(
            "parse opt-in post-implementation review gate JSON at {post_implementation_review_gate_json:?}: {e}"
        )
    })?;
    let artifact_body = std::fs::read_to_string(redacted_order_artifact_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in redacted order artifact JSON at {redacted_order_artifact_json:?}: {e}"
        )
    })?;
    opts.redacted_order_artifact = serde_json::from_str(&artifact_body).map_err(|e| {
        anyhow::anyhow!(
            "parse opt-in redacted order artifact JSON at {redacted_order_artifact_json:?}: {e}"
        )
    })?;
    if let Some(redacted_evidence_aggregate_json) = redacted_evidence_aggregate_json {
        let aggregate_body = std::fs::read_to_string(redacted_evidence_aggregate_json).map_err(|e| {
            anyhow::anyhow!(
                "read opt-in redacted evidence aggregate JSON at {redacted_evidence_aggregate_json:?}: {e}"
            )
        })?;
        opts.redacted_evidence_aggregate =
            Some(serde_json::from_str(&aggregate_body).map_err(|e| {
                anyhow::anyhow!(
                    "parse opt-in redacted evidence aggregate JSON at {redacted_evidence_aggregate_json:?}: {e}"
                )
            })?);
    }
    if let Some(evidence_summary_json) = evidence_summary_json {
        let evidence_body = std::fs::read_to_string(evidence_summary_json).map_err(|e| {
            anyhow::anyhow!("read opt-in evidence summary JSON at {evidence_summary_json:?}: {e}")
        })?;
        opts.evidence_summary = Some(serde_json::from_str(&evidence_body).map_err(|e| {
            anyhow::anyhow!("parse opt-in evidence summary JSON at {evidence_summary_json:?}: {e}")
        })?);
    }
    let payload = biocortex_retrieval_opt_in_runtime_influence_review_request(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in runtime-influence review request");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "request_ready={} request_state={} approval_state={}",
        shadow_json_display(
            boundary.get("runtime_influence_review_request_ready"),
            "false"
        ),
        shadow_json_display(payload.get("review_request_state"), "blocked"),
        shadow_json_display(payload.get("approval_state"), "not_approved")
    );
    println!(
        "runtime_adapter_approved={} default_search_order_change_allowed={} ordering_behavior_connected={}",
        shadow_json_display(payload.get("runtime_adapter_approved"), "false"),
        shadow_json_display(payload.get("default_search_order_change_allowed"), "false"),
        shadow_json_display(payload.get("ordering_behavior_connected"), "false")
    );
    let evidence = payload.get("evidence_summary").unwrap_or(&Value::Null);
    println!(
        "redacted_evidence_aggregate_provided={} redacted_evidence_aggregate_ready={} post_runtime_evidence_summary_ready={}",
        shadow_json_display(
            evidence.get("redacted_evidence_aggregate_provided"),
            "false"
        ),
        shadow_json_display(evidence.get("redacted_evidence_aggregate_ready"), "false"),
        shadow_json_display(
            evidence.get("post_runtime_evidence_summary_ready"),
            "false"
        )
    );
    println!(
        "blockers={} calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        boundary
            .get("blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string()),
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_runtime_influence_decision_packet(
    runtime_influence_review_request_json: &std::path::Path,
    runtime_influence_decision_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions,
    as_json: bool,
) -> Result<()> {
    let request_body = std::fs::read_to_string(runtime_influence_review_request_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in runtime influence review request JSON at {runtime_influence_review_request_json:?}: {e}"
        )
    })?;
    opts.runtime_influence_review_request = serde_json::from_str(&request_body).map_err(|e| {
        anyhow::anyhow!(
            "parse opt-in runtime influence review request JSON at {runtime_influence_review_request_json:?}: {e}"
        )
    })?;
    let decision_body = std::fs::read_to_string(runtime_influence_decision_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in runtime influence decision JSON at {runtime_influence_decision_json:?}: {e}"
        )
    })?;
    opts.runtime_influence_decision = serde_json::from_str(&decision_body).map_err(|e| {
        anyhow::anyhow!(
            "parse opt-in runtime influence decision JSON at {runtime_influence_decision_json:?}: {e}"
        )
    })?;
    let payload = biocortex_retrieval_opt_in_runtime_influence_decision_packet(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in runtime-influence decision packet");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "runtime_influence_authorized={} approval_state={} authorization_state={}",
        shadow_json_display(boundary.get("runtime_influence_authorized"), "false"),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("authorization_state"), "not_authorized")
    );
    println!(
        "runtime_adapter_approved={} default_search_order_change_allowed={} ordering_behavior_connection_authorized={}",
        shadow_json_display(payload.get("runtime_adapter_approved"), "false"),
        shadow_json_display(payload.get("default_search_order_change_allowed"), "false"),
        shadow_json_display(
            payload.get("ordering_behavior_connection_authorized"),
            "false"
        )
    );
    println!(
        "blockers={} calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        boundary
            .get("blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string()),
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_store_trial(
    runtime_influence_decision_packet_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInStoreTrialOptions,
    as_json: bool,
) -> Result<()> {
    let packet_body = std::fs::read_to_string(runtime_influence_decision_packet_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
        )
    })?;
    opts.runtime_influence_decision_packet =
        serde_json::from_str(&packet_body).map_err(|e| {
            anyhow::anyhow!(
                "parse opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
            )
        })?;

    let db_path = std::env::var("AGENT_BRIDGE_DB")
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;
    let payload = biocortex_retrieval_opt_in_store_trial(&store, opts).await;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in store trial");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "status={} implementation_stage={} approval_state={}",
        shadow_json_display(payload.get("status"), "-"),
        shadow_json_display(payload.get("implementation_stage"), "-"),
        shadow_json_display(payload.get("approval_state"), "not_approved")
    );
    let preflight = payload.get("runtime_preflight").unwrap_or(&Value::Null);
    println!(
        "adapter_allowed={} blockers={} compile_feature_enabled={} runtime_enabled={} operator_disabled={}",
        shadow_json_display(preflight.get("adapter_allowed"), "false"),
        preflight
            .get("blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string()),
        shadow_json_display(preflight.get("compile_feature_enabled"), "false"),
        shadow_json_display(preflight.get("runtime_enabled"), "false"),
        shadow_json_display(preflight.get("operator_disabled"), "false")
    );
    let baseline = payload.get("baseline_order").unwrap_or(&Value::Null);
    println!(
        "baseline_completed={} baseline_key_count={} baseline_hash={} raw_keys_included={} content_included={}",
        shadow_json_display(baseline.get("completed"), "false"),
        shadow_json_display(baseline.get("key_count"), "0"),
        shadow_json_display(baseline.get("hash"), "-"),
        shadow_json_display(baseline.get("raw_keys_included"), "false"),
        shadow_json_display(baseline.get("content_included"), "false")
    );
    let side_signal = payload.get("side_signal").unwrap_or(&Value::Null);
    println!(
        "side_signal_attempted={} side_signal_status={} matched_candidate_count={} coverage={} raw_included={}",
        shadow_json_display(side_signal.get("attempted"), "false"),
        shadow_json_display(side_signal.get("status"), "-"),
        shadow_json_display(side_signal.get("matched_candidate_count"), "0"),
        shadow_json_display(side_signal.get("coverage"), "0"),
        shadow_json_display(side_signal.get("raw_included"), "false")
    );
    let returned = payload.get("returned_order").unwrap_or(&Value::Null);
    println!(
        "returned_source={} baseline_returned={} actual_return_order_changed={} fallback_reason={}",
        shadow_json_display(returned.get("source"), "baseline"),
        shadow_json_display(returned.get("baseline_returned"), "true"),
        shadow_json_display(returned.get("actual_return_order_changed"), "false"),
        shadow_json_display(returned.get("fallback_reason"), "-")
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={} default_calls_unchanged={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false"),
        shadow_json_display(payload.get("default_calls_unchanged"), "true")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_gated_store_trial(
    runtime_transition_gate_json: &std::path::Path,
    runtime_influence_decision_packet_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInGatedStoreTrialOptions,
    as_json: bool,
) -> Result<()> {
    let gate_body = std::fs::read_to_string(runtime_transition_gate_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in runtime transition gate JSON at {runtime_transition_gate_json:?}: {e}"
        )
    })?;
    opts.runtime_transition_gate = serde_json::from_str(&gate_body).map_err(|e| {
        anyhow::anyhow!(
            "parse opt-in runtime transition gate JSON at {runtime_transition_gate_json:?}: {e}"
        )
    })?;
    let packet_body = std::fs::read_to_string(runtime_influence_decision_packet_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
        )
    })?;
    opts.runtime_influence_decision_packet =
        serde_json::from_str(&packet_body).map_err(|e| {
            anyhow::anyhow!(
                "parse opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
            )
        })?;

    let db_path = std::env::var("AGENT_BRIDGE_DB")
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;
    let payload = biocortex_retrieval_opt_in_gated_store_trial(&store, opts).await;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in gated store trial");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "status={} gate_allowed={} store_trial_called={} approval_state={}",
        shadow_json_display(payload.get("status"), "-"),
        shadow_json_display(
            payload.pointer("/runtime_transition_preflight/transition_gate_allowed"),
            "false"
        ),
        shadow_json_display(payload.get("store_trial_called"), "false"),
        shadow_json_display(payload.get("approval_state"), "blocked")
    );
    let transition = payload
        .get("runtime_transition_preflight")
        .unwrap_or(&Value::Null);
    println!(
        "transition_blockers={} operator_disabled_now={} query_present={}",
        transition
            .get("blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string()),
        shadow_json_display(transition.get("operator_disabled_now"), "false"),
        shadow_json_display(transition.get("query_present"), "false")
    );
    let summary = payload.get("store_trial_summary").unwrap_or(&Value::Null);
    println!(
        "store_trial_status={} adapter_allowed={} baseline_key_count={} side_signal_status={}",
        shadow_json_display(summary.get("status"), "-"),
        shadow_json_display(summary.get("runtime_adapter_allowed"), "false"),
        shadow_json_display(summary.get("baseline_key_count"), "0"),
        shadow_json_display(summary.get("side_signal_status"), "-")
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={} default_calls_unchanged={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false"),
        shadow_json_display(payload.get("default_calls_unchanged"), "true")
    );
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_batch_diagnostics(
    runtime_influence_decision_packet_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInBatchDiagnosticsOptions,
    as_json: bool,
) -> Result<()> {
    let packet_body = std::fs::read_to_string(runtime_influence_decision_packet_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
        )
    })?;
    opts.runtime_influence_decision_packet =
        serde_json::from_str(&packet_body).map_err(|e| {
            anyhow::anyhow!(
                "parse opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
            )
        })?;

    let db_path = std::env::var("AGENT_BRIDGE_DB")
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;
    let payload = biocortex_retrieval_opt_in_batch_diagnostics(&store, opts).await;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in batch diagnostics");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "status={} implementation_stage={}",
        shadow_json_display(payload.get("status"), "-"),
        shadow_json_display(payload.get("implementation_stage"), "-")
    );
    let summary = payload.get("summary").unwrap_or(&Value::Null);
    println!(
        "queries={} baseline_completed={} adapter_allowed={} side_signal_ok={} experimental_source={} actual_order_changed={}",
        shadow_json_display(summary.get("query_count"), "0"),
        shadow_json_display(summary.get("baseline_completed_count"), "0"),
        shadow_json_display(summary.get("adapter_allowed_count"), "0"),
        shadow_json_display(summary.get("side_signal_ok_count"), "0"),
        shadow_json_display(summary.get("experimental_source_count"), "0"),
        shadow_json_display(summary.get("actual_order_changed_count"), "0")
    );
    println!(
        "avg_coverage={} avg_latency_ms={} raw_flagged_count={}",
        shadow_json_display(summary.get("avg_coverage"), "0"),
        shadow_json_display(summary.get("avg_latency_ms"), "0"),
        shadow_json_display(summary.get("raw_flagged_count"), "0")
    );
    let safety = payload.get("safety").unwrap_or(&Value::Null);
    println!(
        "calls_memory_search_all={} runs_biocortex_any={} default_calls_unchanged_all={} raw_flags_all_false={}",
        shadow_json_display(safety.get("calls_memory_search_all"), "false"),
        shadow_json_display(safety.get("runs_biocortex_any"), "false"),
        shadow_json_display(safety.get("default_calls_unchanged_all"), "true"),
        shadow_json_display(safety.get("raw_flags_all_false"), "true")
    );
    if let Some(buckets) = payload.get("bucket_summary").and_then(Value::as_array) {
        for bucket in buckets.iter().take(12) {
            println!(
                "bucket={} queries={} moved={} aligned_experimental={}",
                shadow_json_display(bucket.get("class_label"), "unlabeled"),
                shadow_json_display(bucket.get("query_count"), "0"),
                shadow_json_display(bucket.get("actual_order_changed_count"), "0"),
                shadow_json_display(bucket.get("experimental_source_count"), "0")
            );
        }
    }
    Ok(())
}

async fn run_biocortex_retrieval_opt_in_gated_batch_diagnostics(
    runtime_transition_gate_json: &std::path::Path,
    runtime_influence_decision_packet_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInGatedBatchDiagnosticsOptions,
    as_json: bool,
) -> Result<()> {
    let gate_body = std::fs::read_to_string(runtime_transition_gate_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in runtime transition gate JSON at {runtime_transition_gate_json:?}: {e}"
        )
    })?;
    opts.runtime_transition_gate = serde_json::from_str(&gate_body).map_err(|e| {
        anyhow::anyhow!(
            "parse opt-in runtime transition gate JSON at {runtime_transition_gate_json:?}: {e}"
        )
    })?;
    let packet_body = std::fs::read_to_string(runtime_influence_decision_packet_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
        )
    })?;
    opts.runtime_influence_decision_packet =
        serde_json::from_str(&packet_body).map_err(|e| {
            anyhow::anyhow!(
                "parse opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
            )
        })?;

    let db_path = std::env::var("AGENT_BRIDGE_DB")
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;
    let payload = biocortex_retrieval_opt_in_gated_batch_diagnostics(&store, opts).await;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in gated batch diagnostics");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "status={} implementation_stage={} approval_state={}",
        shadow_json_display(payload.get("status"), "-"),
        shadow_json_display(payload.get("implementation_stage"), "-"),
        shadow_json_display(payload.get("approval_state"), "blocked")
    );
    let summary = payload.get("summary").unwrap_or(&Value::Null);
    println!(
        "queries={} gate_allowed={} gate_blocked={} store_trial_called={} calls_memory_search={}",
        shadow_json_display(summary.get("query_count"), "0"),
        shadow_json_display(summary.get("transition_gate_allowed_count"), "0"),
        shadow_json_display(summary.get("transition_gate_blocked_count"), "0"),
        shadow_json_display(summary.get("store_trial_called_count"), "0"),
        shadow_json_display(summary.get("calls_memory_search_count"), "0")
    );
    println!(
        "baseline_completed={} side_signal_ok={} experimental_source={} actual_order_changed={}",
        shadow_json_display(summary.get("baseline_completed_count"), "0"),
        shadow_json_display(summary.get("side_signal_ok_count"), "0"),
        shadow_json_display(summary.get("experimental_source_count"), "0"),
        shadow_json_display(summary.get("actual_order_changed_count"), "0")
    );
    let safety = payload.get("safety").unwrap_or(&Value::Null);
    println!(
        "transition_gate_blocked_all={} store_trial_called_all={} calls_memory_search_all={} raw_flags_all_false={}",
        shadow_json_display(safety.get("transition_gate_blocked_all"), "false"),
        shadow_json_display(safety.get("store_trial_called_all"), "false"),
        shadow_json_display(safety.get("calls_memory_search_all"), "false"),
        shadow_json_display(safety.get("raw_flags_all_false"), "true")
    );
    if let Some(buckets) = payload.get("bucket_summary").and_then(Value::as_array) {
        for bucket in buckets.iter().take(12) {
            println!(
                "bucket={} queries={} gate_blocked={} moved={}",
                shadow_json_display(bucket.get("class_label"), "unlabeled"),
                shadow_json_display(bucket.get("query_count"), "0"),
                shadow_json_display(bucket.get("transition_gate_blocked_count"), "0"),
                shadow_json_display(bucket.get("actual_order_changed_count"), "0")
            );
        }
    }
    Ok(())
}

fn run_biocortex_retrieval_opt_in_runtime_readiness_packet(
    runtime_influence_decision_packet_json: &std::path::Path,
    store_trial_json: &std::path::Path,
    batch_diagnostics_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInRuntimeReadinessPacketOptions,
    as_json: bool,
) -> Result<()> {
    let decision_body = std::fs::read_to_string(runtime_influence_decision_packet_json)
        .map_err(|e| {
            anyhow::anyhow!(
                "read opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
            )
        })?;
    opts.runtime_influence_decision_packet =
        serde_json::from_str(&decision_body).map_err(|e| {
            anyhow::anyhow!(
                "parse opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
            )
        })?;
    let store_body = std::fs::read_to_string(store_trial_json).map_err(|e| {
        anyhow::anyhow!("read opt-in store trial JSON at {store_trial_json:?}: {e}")
    })?;
    opts.store_trial = serde_json::from_str(&store_body).map_err(|e| {
        anyhow::anyhow!("parse opt-in store trial JSON at {store_trial_json:?}: {e}")
    })?;
    let batch_body = std::fs::read_to_string(batch_diagnostics_json).map_err(|e| {
        anyhow::anyhow!("read opt-in batch diagnostics JSON at {batch_diagnostics_json:?}: {e}")
    })?;
    opts.batch_diagnostics = serde_json::from_str(&batch_body).map_err(|e| {
        anyhow::anyhow!("parse opt-in batch diagnostics JSON at {batch_diagnostics_json:?}: {e}")
    })?;

    let payload = biocortex_retrieval_opt_in_runtime_readiness_packet(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in runtime readiness packet");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "status={} control_plane_ready={} live_probe_state={}",
        shadow_json_display(payload.get("status"), "-"),
        shadow_json_display(payload.pointer("/readiness/control_plane_ready"), "false"),
        shadow_json_display(payload.pointer("/readiness/live_probe_state"), "-")
    );
    println!(
        "may_accept_controlled_opt_in={} live_order_influence_ready={} default_influence_ready={}",
        shadow_json_display(
            payload.pointer("/readiness/may_accept_controlled_explicit_opt_in_fts_calls"),
            "false"
        ),
        shadow_json_display(
            payload.pointer("/readiness/live_order_influence_ready"),
            "false"
        ),
        shadow_json_display(
            payload.pointer("/readiness/default_influence_ready"),
            "false"
        )
    );
    println!(
        "batch_evidence_source={} transition_gated={}",
        shadow_json_display(payload.pointer("/batch_summary/evidence_source"), "-"),
        shadow_json_display(payload.pointer("/batch_summary/transition_gated"), "false")
    );
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "runtime_readiness_ready={} blockers={}",
        shadow_json_display(boundary.get("runtime_readiness_ready"), "false"),
        boundary
            .get("blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={} default_calls_unchanged={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false"),
        shadow_json_display(payload.get("default_calls_unchanged"), "true")
    );
    Ok(())
}

fn cli_env_truthy(key: &str) -> bool {
    std::env::var(key)
        .ok()
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(false)
}

fn run_biocortex_retrieval_opt_in_runtime_transition_gate(
    runtime_readiness_packet_json: &std::path::Path,
    mut opts: BioCortexRetrievalOptInRuntimeTransitionGateOptions,
    as_json: bool,
) -> Result<()> {
    let readiness_body = std::fs::read_to_string(runtime_readiness_packet_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in runtime readiness packet JSON at {runtime_readiness_packet_json:?}: {e}"
        )
    })?;
    opts.runtime_readiness_packet = serde_json::from_str(&readiness_body).map_err(|e| {
        anyhow::anyhow!(
            "parse opt-in runtime readiness packet JSON at {runtime_readiness_packet_json:?}: {e}"
        )
    })?;

    let payload = biocortex_retrieval_opt_in_runtime_transition_gate(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in runtime transition gate");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "status={} transition_allowed={} mode={} per_call_opt_in={} operator_disabled={}",
        shadow_json_display(payload.get("status"), "-"),
        shadow_json_display(payload.pointer("/transition/transition_allowed"), "false"),
        shadow_json_display(payload.pointer("/requested_transition/mode"), "-"),
        shadow_json_display(
            payload.pointer("/requested_transition/per_call_opt_in"),
            "false"
        ),
        shadow_json_display(
            payload.pointer("/requested_transition/operator_disabled"),
            "false"
        )
    );
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "runtime_transition_allowed={} blockers={}",
        shadow_json_display(boundary.get("runtime_transition_allowed"), "false"),
        boundary
            .get("blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={} default_calls_unchanged={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false"),
        shadow_json_display(payload.get("default_calls_unchanged"), "true")
    );
    Ok(())
}

const BIOCORTEX_RETRIEVAL_OPT_IN_BATCH_DIAGNOSTICS_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0";
const BIOCORTEX_RETRIEVAL_OPT_IN_GATED_BATCH_DIAGNOSTICS_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_gated_batch_diagnostics.v0";
const BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_READINESS_PACKET_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0";
const BIOCORTEX_RETRIEVAL_OPT_IN_EVIDENCE_SUMMARY_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_evidence_summary.v0";
const BIOCORTEX_RETRIEVAL_OPT_IN_REDACTED_EVIDENCE_AGGREGATE_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_redacted_evidence_aggregate.v0";
const BIOCORTEX_RETRIEVAL_OPT_IN_CONTROLLED_ORDER_FIXTURE_RUN_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0";
const BIOCORTEX_RETRIEVAL_OPT_IN_CONTROLLED_ORDER_FIXTURE_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture.v0";

#[derive(Debug, Clone, serde::Deserialize)]
struct BioCortexControlledOrderFixture {
    #[serde(default)]
    schema: Option<String>,
    memory_records: Vec<BioCortexControlledOrderMemoryRecord>,
    query_cases: Vec<BioCortexControlledOrderQueryCase>,
    #[serde(default)]
    expected: BioCortexControlledOrderExpected,
}

#[derive(Debug, Clone, serde::Deserialize)]
struct BioCortexControlledOrderMemoryRecord {
    key: String,
    content: String,
    #[serde(default)]
    kind: Option<String>,
    #[serde(default)]
    tags: Vec<String>,
    #[serde(default)]
    related_keys: Vec<String>,
    #[serde(default)]
    scope: Option<String>,
    #[serde(default)]
    importance: Option<f64>,
}

#[derive(Debug, Clone, serde::Deserialize)]
struct BioCortexControlledOrderQueryCase {
    query: String,
    #[serde(default)]
    class_label: Option<String>,
}

#[derive(Debug, Clone, Default, serde::Deserialize)]
struct BioCortexControlledOrderExpected {
    #[serde(default)]
    min_actual_order_changed_count: Option<u64>,
    #[serde(default)]
    min_experimental_source_count: Option<u64>,
    #[serde(default)]
    min_side_signal_ok_count: Option<u64>,
}

async fn run_biocortex_retrieval_opt_in_controlled_order_fixture(
    runtime_influence_decision_packet_json: &std::path::Path,
    fixture_json: &std::path::Path,
    allow_non_production_store_writes: bool,
    mut opts: BioCortexRetrievalOptInBatchDiagnosticsOptions,
    as_json: bool,
) -> Result<()> {
    if !allow_non_production_store_writes {
        return Err(anyhow::anyhow!(
            "controlled order fixture requires --allow-non-production-store-writes"
        ));
    }

    let db_path = controlled_fixture_db_path()?;
    let packet_body = std::fs::read_to_string(runtime_influence_decision_packet_json).map_err(|e| {
        anyhow::anyhow!(
            "read opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
        )
    })?;
    opts.runtime_influence_decision_packet =
        serde_json::from_str(&packet_body).map_err(|e| {
            anyhow::anyhow!(
                "parse opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
            )
        })?;

    let fixture = load_biocortex_controlled_order_fixture(fixture_json)?;
    opts.queries = fixture
        .query_cases
        .iter()
        .map(|case| BioCortexRetrievalOptInBatchQueryCase {
            query: case.query.clone(),
            class_label: case.class_label.clone(),
        })
        .collect();

    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open non-production state.db at {db_path:?}: {e}"))?;
    for rec in &fixture.memory_records {
        let mem = ab_store::MemoryRecord {
            key: rec.key.trim().to_string(),
            kind: rec
                .kind
                .as_deref()
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .unwrap_or("fact")
                .to_string(),
            content: rec.content.clone(),
            tags: rec.tags.clone(),
            related_keys: rec.related_keys.clone(),
            scope: rec.scope.clone(),
            created_at: 0,
            updated_at: 0,
            last_accessed_at: 0,
            access_count: 0,
            importance: rec.importance.unwrap_or(0.5).clamp(0.0, 1.0),
            status: "active".to_string(),
            trigger_pattern: None,
            superseded_by: None,
        };
        if mem.key.is_empty() {
            return Err(anyhow::anyhow!(
                "controlled order fixture memory_records cannot contain an empty key"
            ));
        }
        store
            .memory_save(&mem)
            .await
            .map_err(|e| anyhow::anyhow!("seed controlled order fixture memory: {e}"))?;
    }

    let diagnostics = biocortex_retrieval_opt_in_batch_diagnostics(&store, opts).await;
    let summary = diagnostics.get("summary").unwrap_or(&Value::Null);
    let actual_moved = summary
        .get("actual_order_changed_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let experimental_source = summary
        .get("experimental_source_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let side_signal_ok = summary
        .get("side_signal_ok_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let expected_min_moved = fixture.expected.min_actual_order_changed_count.unwrap_or(0);
    let expected_min_experimental = fixture.expected.min_experimental_source_count.unwrap_or(0);
    let expected_min_side_signal_ok = fixture.expected.min_side_signal_ok_count.unwrap_or(0);
    let expected_met = actual_moved >= expected_min_moved
        && experimental_source >= expected_min_experimental
        && side_signal_ok >= expected_min_side_signal_ok;

    let payload = json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_CONTROLLED_ORDER_FIXTURE_RUN_SCHEMA,
        "generated_at": diagnostics.get("generated_at").cloned().unwrap_or(Value::Null),
        "controlled_order_fixture": true,
        "implementation_stage": "store_opt_in_controlled_order_fixture",
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "purpose": "Seed a caller-selected non-production store with fixture memories, then run redacted opt-in batch diagnostics to prove the protected path can surface actual order movement.",
        "status": if expected_met { "completed" } else { "completed_expected_movement_missing" },
        "attempt": {
            "attempt_id": diagnostics.pointer("/attempt/attempt_id").cloned().unwrap_or(Value::Null),
            "commit": diagnostics.pointer("/attempt/commit").cloned().unwrap_or(Value::Null),
            "query_count": fixture.query_cases.len(),
            "seeded_memory_count": fixture.memory_records.len(),
        },
        "fixture_contract": {
            "fixture_schema": fixture.schema.unwrap_or_else(|| BIOCORTEX_RETRIEVAL_OPT_IN_CONTROLLED_ORDER_FIXTURE_SCHEMA.to_string()),
            "requires_agent_bridge_db_override": true,
            "requires_non_production_store_write_ack": true,
            "writes_ab_store": true,
            "writes_approval": false,
            "registers_embedding_backend": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "expected": {
            "min_actual_order_changed_count": expected_min_moved,
            "min_experimental_source_count": expected_min_experimental,
            "min_side_signal_ok_count": expected_min_side_signal_ok,
            "met": expected_met,
        },
        "diagnostics": diagnostics,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
        "default_search_order_change_allowed": false,
        "default_calls_unchanged": true,
    });

    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in controlled order fixture");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "status={} expected_met={}",
        shadow_json_display(payload.get("status"), "-"),
        shadow_json_display(payload.pointer("/expected/met"), "false")
    );
    println!(
        "seeded_memories={} queries={} actual_order_changed={} experimental_source={} side_signal_ok={}",
        shadow_json_display(payload.pointer("/attempt/seeded_memory_count"), "0"),
        shadow_json_display(payload.pointer("/attempt/query_count"), "0"),
        actual_moved,
        experimental_source,
        side_signal_ok
    );
    println!(
        "raw_queries_included={} raw_keys_included={} content_included={}",
        shadow_json_display(payload.get("raw_queries_included"), "false"),
        shadow_json_display(payload.get("raw_keys_included"), "false"),
        shadow_json_display(payload.get("content_included"), "false")
    );
    Ok(())
}

fn run_biocortex_retrieval_opt_in_evidence_summary(
    batch_diagnostics_json: &std::path::Path,
    controlled_order_fixture_run_json: &std::path::Path,
    runtime_readiness_packet_json: Option<&std::path::Path>,
    reviewer: Option<String>,
    commit: Option<String>,
    forum_post_id: Option<String>,
    memory_key: Option<String>,
    as_json: bool,
) -> Result<()> {
    let batch =
        load_biocortex_redacted_json(batch_diagnostics_json, "opt-in batch diagnostics JSON")?;
    let controlled = load_biocortex_redacted_json(
        controlled_order_fixture_run_json,
        "opt-in controlled order fixture run JSON",
    )?;
    let runtime_readiness = if let Some(path) = runtime_readiness_packet_json {
        Some(load_biocortex_redacted_json(
            path,
            "opt-in runtime readiness packet JSON",
        )?)
    } else {
        None
    };

    let batch_legacy_schema_ok = evidence_json_str_eq(
        batch.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_BATCH_DIAGNOSTICS_SCHEMA,
    );
    let batch_gated_schema_ok = evidence_json_str_eq(
        batch.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_GATED_BATCH_DIAGNOSTICS_SCHEMA,
    );
    let batch_schema_ok = batch_legacy_schema_ok || batch_gated_schema_ok;
    let batch_transition_gated = batch_gated_schema_ok;
    let batch_evidence_source = if batch_transition_gated {
        "runtime_transition_gated_batch_diagnostics"
    } else {
        "store_opt_in_batch_diagnostics"
    };
    let controlled_schema_ok = evidence_json_str_eq(
        controlled.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_CONTROLLED_ORDER_FIXTURE_RUN_SCHEMA,
    );

    let batch_summary = batch.get("summary").unwrap_or(&Value::Null);
    let batch_query_count = evidence_json_u64(batch_summary.get("query_count"));
    let batch_baseline_completed = evidence_json_u64(batch_summary.get("baseline_completed_count"));
    let batch_baseline_empty = evidence_json_u64(batch_summary.get("baseline_empty_count"));
    let batch_transition_gate_allowed =
        evidence_json_u64(batch_summary.get("transition_gate_allowed_count"));
    let batch_transition_gate_blocked =
        evidence_json_u64(batch_summary.get("transition_gate_blocked_count"));
    let batch_store_trial_called = evidence_json_u64(batch_summary.get("store_trial_called_count"));
    let batch_calls_memory_search =
        evidence_json_u64(batch_summary.get("calls_memory_search_count"));
    let batch_adapter_allowed = if batch_transition_gated {
        evidence_json_u64(batch_summary.get("store_trial_adapter_allowed_count"))
    } else {
        evidence_json_u64(batch_summary.get("adapter_allowed_count"))
    };
    let batch_side_signal_ok = evidence_json_u64(batch_summary.get("side_signal_ok_count"));
    let batch_experimental_source =
        evidence_json_u64(batch_summary.get("experimental_source_count"));
    let batch_actual_moved = evidence_json_u64(batch_summary.get("actual_order_changed_count"));
    let batch_raw_flags_all_false =
        evidence_json_bool_is(batch.pointer("/safety/raw_flags_all_false"), true)
            && evidence_json_bool_is(batch.get("raw_queries_included"), false)
            && evidence_json_bool_is(batch.get("raw_keys_included"), false)
            && evidence_json_bool_is(batch.get("content_included"), false)
            && evidence_json_bool_is(batch.get("side_signal_raw_included"), false);
    let batch_movement_observed = batch_actual_moved > 0;
    let batch_transition_gate_ok = !batch_transition_gated
        || (batch_query_count > 0
            && batch_transition_gate_allowed == batch_query_count
            && batch_transition_gate_blocked == 0
            && evidence_json_bool_is(batch.pointer("/safety/transition_gate_allowed_all"), true));
    let batch_gated_downstream_called = !batch_transition_gated
        || (batch_store_trial_called == batch_transition_gate_allowed
            && evidence_json_bool_is(batch.pointer("/safety/store_trial_called_all"), true));
    let batch_gated_diagnostics_ready = batch_transition_gated
        && batch_schema_ok
        && batch_raw_flags_all_false
        && batch_transition_gate_ok
        && batch_gated_downstream_called;
    let batch_diagnostic_class = if batch_movement_observed {
        "movement_observed"
    } else if batch_experimental_source > 0 {
        "experimental_aligned_with_baseline"
    } else if batch_adapter_allowed == 0 {
        "preflight_or_baseline_empty"
    } else {
        "no_rank_movement_observed"
    };

    let controlled_summary = controlled
        .pointer("/diagnostics/summary")
        .unwrap_or(&Value::Null);
    let controlled_query_count = evidence_json_u64(controlled_summary.get("query_count"));
    let controlled_adapter_allowed =
        evidence_json_u64(controlled_summary.get("adapter_allowed_count"));
    let controlled_side_signal_ok =
        evidence_json_u64(controlled_summary.get("side_signal_ok_count"));
    let controlled_experimental_source =
        evidence_json_u64(controlled_summary.get("experimental_source_count"));
    let controlled_actual_moved =
        evidence_json_u64(controlled_summary.get("actual_order_changed_count"));
    let controlled_expected_met = evidence_json_bool_is(controlled.pointer("/expected/met"), true);
    let controlled_raw_flags_all_false =
        evidence_json_bool_is(
            controlled.pointer("/diagnostics/safety/raw_flags_all_false"),
            true,
        ) && evidence_json_bool_is(controlled.get("raw_queries_included"), false)
            && evidence_json_bool_is(controlled.get("raw_keys_included"), false)
            && evidence_json_bool_is(controlled.get("content_included"), false)
            && evidence_json_bool_is(controlled.get("side_signal_raw_included"), false)
            && evidence_json_bool_is(
                controlled.pointer("/fixture_contract/raw_queries_included"),
                false,
            )
            && evidence_json_bool_is(
                controlled.pointer("/fixture_contract/raw_keys_included"),
                false,
            )
            && evidence_json_bool_is(
                controlled.pointer("/fixture_contract/content_included"),
                false,
            )
            && evidence_json_bool_is(
                controlled.pointer("/fixture_contract/side_signal_raw_included"),
                false,
            );
    let controlled_movement_observed =
        controlled_schema_ok && controlled_expected_met && controlled_actual_moved > 0;
    let runtime_readiness_value = runtime_readiness.as_ref();
    let runtime_readiness_provided = runtime_readiness_value.is_some();
    let runtime_readiness_schema_ok = runtime_readiness_value
        .map(|value| {
            evidence_json_str_eq(
                value.get("schema"),
                BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_READINESS_PACKET_SCHEMA,
            )
        })
        .unwrap_or(false);
    let runtime_readiness_marker_ok = runtime_readiness_value
        .map(|value| evidence_json_bool_is(value.get("runtime_readiness_packet"), true))
        .unwrap_or(false);
    let runtime_readiness_ready = runtime_readiness_value
        .map(|value| {
            evidence_json_bool_is(
                value.pointer("/boundary_check/runtime_readiness_ready"),
                true,
            )
        })
        .unwrap_or(false);
    let runtime_readiness_control_plane_ready = runtime_readiness_value
        .map(|value| evidence_json_bool_is(value.pointer("/readiness/control_plane_ready"), true))
        .unwrap_or(false);
    let runtime_readiness_live_order_influence_ready = runtime_readiness_value
        .map(|value| {
            evidence_json_bool_is(value.pointer("/readiness/live_order_influence_ready"), true)
        })
        .unwrap_or(false);
    let runtime_readiness_may_accept_controlled = runtime_readiness_value
        .map(|value| {
            evidence_json_bool_is(
                value.pointer("/readiness/may_accept_controlled_explicit_opt_in_fts_calls"),
                true,
            )
        })
        .unwrap_or(false);
    let runtime_readiness_default_influence_blocked = runtime_readiness_value
        .map(|value| {
            evidence_json_bool_is(value.pointer("/readiness/default_influence_ready"), false)
        })
        .unwrap_or(false);
    let runtime_readiness_batch_evidence_source = runtime_readiness_value
        .and_then(|value| value.pointer("/batch_summary/evidence_source"))
        .and_then(Value::as_str)
        .unwrap_or("");
    let runtime_readiness_batch_transition_gated = runtime_readiness_value
        .map(|value| evidence_json_bool_is(value.pointer("/batch_summary/transition_gated"), true))
        .unwrap_or(false);
    let runtime_readiness_batch_schema_ok = runtime_readiness_value
        .map(|value| evidence_json_bool_is(value.pointer("/batch_summary/schema_ok"), true))
        .unwrap_or(false);
    let runtime_readiness_batch_transition_gate_ok = runtime_readiness_value
        .map(|value| {
            evidence_json_bool_is(value.pointer("/batch_summary/transition_gate_ok"), true)
        })
        .unwrap_or(false);
    let runtime_readiness_raw_flags_all_false = runtime_readiness_value
        .map(|value| {
            evidence_json_bool_is(value.get("raw_queries_included"), false)
                && evidence_json_bool_is(value.get("raw_keys_included"), false)
                && evidence_json_bool_is(value.get("content_included"), false)
                && evidence_json_bool_is(value.get("side_signal_raw_included"), false)
                && evidence_json_bool_is(value.get("human_decision_text_included"), false)
                && evidence_json_bool_is(
                    value.pointer("/input_contract/raw_queries_included"),
                    false,
                )
                && evidence_json_bool_is(value.pointer("/input_contract/raw_keys_included"), false)
                && evidence_json_bool_is(value.pointer("/input_contract/content_included"), false)
                && evidence_json_bool_is(
                    value.pointer("/input_contract/side_signal_raw_included"),
                    false,
                )
                && evidence_json_bool_is(
                    value.pointer("/input_contract/human_decision_text_included"),
                    false,
                )
        })
        .unwrap_or(false);
    let runtime_readiness_default_safe = runtime_readiness_value
        .map(|value| {
            evidence_json_bool_is(value.get("default_search_order_change_allowed"), false)
                && evidence_json_bool_is(value.get("default_calls_unchanged"), true)
                && evidence_json_bool_is(value.get("calls_memory_search"), false)
                && evidence_json_bool_is(value.get("runs_biocortex"), false)
                && evidence_json_bool_is(value.get("changes_memory_search_order"), false)
        })
        .unwrap_or(false);
    let runtime_readiness_matches_batch = runtime_readiness_value
        .map(|_| {
            runtime_readiness_batch_evidence_source == batch_evidence_source
                && runtime_readiness_batch_transition_gated == batch_transition_gated
        })
        .unwrap_or(false);
    let runtime_readiness_gated_batch_evidence_ready = runtime_readiness_provided
        && runtime_readiness_schema_ok
        && runtime_readiness_marker_ok
        && runtime_readiness_ready
        && runtime_readiness_batch_schema_ok
        && runtime_readiness_batch_transition_gated
        && runtime_readiness_batch_transition_gate_ok
        && runtime_readiness_matches_batch
        && runtime_readiness_raw_flags_all_false
        && runtime_readiness_default_safe;
    let runtime_readiness_requirement_met = !runtime_readiness_provided
        || (runtime_readiness_schema_ok
            && runtime_readiness_marker_ok
            && runtime_readiness_ready
            && runtime_readiness_control_plane_ready
            && runtime_readiness_may_accept_controlled
            && runtime_readiness_default_influence_blocked
            && runtime_readiness_matches_batch
            && runtime_readiness_raw_flags_all_false
            && runtime_readiness_default_safe);
    let runtime_adapter_connection_evidence = batch_adapter_allowed > 0
        || controlled_adapter_allowed > 0
        || controlled_side_signal_ok > 0;
    let evidence_ready = batch_schema_ok
        && controlled_schema_ok
        && batch_raw_flags_all_false
        && controlled_raw_flags_all_false
        && controlled_movement_observed
        && runtime_readiness_requirement_met;
    let recommended_next_step = if evidence_ready {
        "expand_non_production_corpus"
    } else {
        "collect_missing_redacted_evidence"
    };
    let review_state = if evidence_ready {
        "post_runtime_evidence_ready"
    } else {
        "post_runtime_evidence_incomplete"
    };

    let payload = json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_EVIDENCE_SUMMARY_SCHEMA,
        "read_only": true,
        "evidence_summary": true,
        "implementation_stage": "post_runtime_evidence_summary",
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "purpose": "Summarize redacted batch diagnostics plus controlled order-movement evidence without copying raw inputs or granting any runtime/default retrieval approval.",
        "status": "completed",
        "reviewer": optional_string_json(reviewer),
        "commit": optional_string_json(commit),
        "forum_post_id": optional_string_json(forum_post_id),
        "memory_key": optional_string_json(memory_key),
        "input_contract": {
            "batch_diagnostics_schema": batch.get("schema").cloned().unwrap_or(Value::Null),
            "batch_diagnostics_legacy_schema_ok": batch_legacy_schema_ok,
            "batch_diagnostics_gated_schema_ok": batch_gated_schema_ok,
            "batch_diagnostics_evidence_source": batch_evidence_source,
            "batch_diagnostics_transition_gated": batch_transition_gated,
            "controlled_order_fixture_run_schema": controlled.get("schema").cloned().unwrap_or(Value::Null),
            "runtime_readiness_packet_schema": runtime_readiness_value
                .and_then(|value| value.get("schema").cloned())
                .unwrap_or(Value::Null),
            "batch_diagnostics_included": false,
            "controlled_order_fixture_run_included": false,
            "runtime_readiness_packet_included": false,
            "runtime_readiness_packet_provided": runtime_readiness_provided,
            "unknown_fields_ignored": true,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "batch_diagnostics": {
            "schema_ok": batch_schema_ok,
            "legacy_schema_ok": batch_legacy_schema_ok,
            "gated_schema_ok": batch_gated_schema_ok,
            "evidence_source": batch_evidence_source,
            "transition_gated": batch_transition_gated,
            "transition_gate_ok": batch_transition_gate_ok,
            "transition_gate_allowed_count": batch_transition_gate_allowed,
            "transition_gate_blocked_count": batch_transition_gate_blocked,
            "store_trial_called_count": batch_store_trial_called,
            "calls_memory_search_count": batch_calls_memory_search,
            "query_count": batch_query_count,
            "baseline_completed_count": batch_baseline_completed,
            "baseline_empty_count": batch_baseline_empty,
            "adapter_allowed_count": batch_adapter_allowed,
            "side_signal_ok_count": batch_side_signal_ok,
            "experimental_source_count": batch_experimental_source,
            "actual_order_changed_count": batch_actual_moved,
            "raw_flags_all_false": batch_raw_flags_all_false,
            "movement_observed": batch_movement_observed,
            "diagnostic_class": batch_diagnostic_class,
        },
        "controlled_order": {
            "schema_ok": controlled_schema_ok,
            "expected_met": controlled_expected_met,
            "seeded_memory_count": evidence_json_u64(controlled.pointer("/attempt/seeded_memory_count")),
            "query_count": controlled_query_count,
            "adapter_allowed_count": controlled_adapter_allowed,
            "side_signal_ok_count": controlled_side_signal_ok,
            "experimental_source_count": controlled_experimental_source,
            "actual_order_changed_count": controlled_actual_moved,
            "raw_flags_all_false": controlled_raw_flags_all_false,
            "movement_observed": controlled_movement_observed,
        },
        "runtime_readiness": {
            "provided": runtime_readiness_provided,
            "schema_ok": runtime_readiness_schema_ok,
            "runtime_readiness_packet": runtime_readiness_marker_ok,
            "runtime_readiness_ready": runtime_readiness_ready,
            "control_plane_ready": runtime_readiness_control_plane_ready,
            "live_order_influence_ready": runtime_readiness_live_order_influence_ready,
            "may_accept_controlled_explicit_opt_in_fts_calls": runtime_readiness_may_accept_controlled,
            "default_influence_ready": !runtime_readiness_default_influence_blocked,
            "batch_evidence_source": if runtime_readiness_provided {
                Value::String(runtime_readiness_batch_evidence_source.to_string())
            } else {
                Value::Null
            },
            "batch_transition_gated": runtime_readiness_batch_transition_gated,
            "batch_schema_ok": runtime_readiness_batch_schema_ok,
            "batch_transition_gate_ok": runtime_readiness_batch_transition_gate_ok,
            "raw_flags_all_false": runtime_readiness_raw_flags_all_false,
            "default_order_safe": runtime_readiness_default_safe,
            "matches_batch_diagnostics": runtime_readiness_matches_batch,
            "gated_batch_evidence_ready": runtime_readiness_gated_batch_evidence_ready,
        },
        "interpretation": {
            "batch_diagnostics_raw_safe": batch_raw_flags_all_false,
            "batch_diagnostics_transition_gated": batch_transition_gated,
            "batch_diagnostics_evidence_source": batch_evidence_source,
            "gated_batch_diagnostics_ready": batch_gated_diagnostics_ready,
            "controlled_order_raw_safe": controlled_raw_flags_all_false,
            "runtime_readiness_packet_provided": runtime_readiness_provided,
            "runtime_readiness_packet_ready": runtime_readiness_ready,
            "runtime_readiness_requirement_met": runtime_readiness_requirement_met,
            "readiness_batch_evidence_source": if runtime_readiness_provided {
                Value::String(runtime_readiness_batch_evidence_source.to_string())
            } else {
                Value::Null
            },
            "readiness_batch_transition_gated": runtime_readiness_batch_transition_gated,
            "readiness_matches_batch_diagnostics": runtime_readiness_matches_batch,
            "readiness_gated_batch_evidence_ready": runtime_readiness_gated_batch_evidence_ready,
            "runtime_adapter_connection_evidence": runtime_adapter_connection_evidence,
            "batch_alignment_or_preflight_evidence": !batch_movement_observed,
            "controlled_rank_movement_observed": controlled_movement_observed,
            "evidence_ready": evidence_ready,
            "default_influence_ready": false,
            "why_not_default": "evidence is explicit-opt-in only; controlled fixture is non-production; default memory_search remains unchanged",
            "recommended_next_step": recommended_next_step,
            "review_state": review_state,
        },
        "approval_state": "evidence_summary_only",
        "authorization_state": "does_not_grant_runtime_influence",
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "default_calls_unchanged": true,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
    });

    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in evidence summary");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "review_state={} evidence_ready={} default_influence_ready={}",
        shadow_json_display(payload.pointer("/interpretation/review_state"), "-"),
        shadow_json_display(payload.pointer("/interpretation/evidence_ready"), "false"),
        shadow_json_display(
            payload.pointer("/interpretation/default_influence_ready"),
            "false"
        )
    );
    println!(
        "batch_queries={} batch_moved={} controlled_moved={} controlled_expected_met={}",
        batch_query_count, batch_actual_moved, controlled_actual_moved, controlled_expected_met
    );
    if runtime_readiness_provided {
        println!(
            "runtime_readiness_ready={} readiness_batch_source={} transition_gated={}",
            shadow_json_display(
                payload.pointer("/runtime_readiness/runtime_readiness_ready"),
                "false"
            ),
            shadow_json_display(
                payload.pointer("/runtime_readiness/batch_evidence_source"),
                "-"
            ),
            shadow_json_display(
                payload.pointer("/runtime_readiness/batch_transition_gated"),
                "false"
            )
        );
    }
    println!(
        "recommended_next_step={} raw_flags batch={} controlled={}",
        shadow_json_display(
            payload.pointer("/interpretation/recommended_next_step"),
            "-"
        ),
        batch_raw_flags_all_false,
        controlled_raw_flags_all_false
    );
    Ok(())
}

fn run_biocortex_retrieval_opt_in_redacted_evidence_aggregate(
    movement_fixture_run_json: &std::path::Path,
    coverage_fixture_run_json: &std::path::Path,
    reviewer: Option<String>,
    commit: Option<String>,
    forum_post_id: Option<String>,
    memory_key: Option<String>,
    as_json: bool,
) -> Result<()> {
    let movement = load_biocortex_redacted_json(
        movement_fixture_run_json,
        "opt-in movement fixture run JSON",
    )?;
    let coverage = load_biocortex_redacted_json(
        coverage_fixture_run_json,
        "opt-in coverage fixture run JSON",
    )?;
    let movement_summary = summarize_biocortex_redacted_fixture_run(&movement);
    let coverage_summary = summarize_biocortex_redacted_fixture_run(&coverage);

    let movement_ready = movement_summary.movement_observed && movement_summary.raw_flags_all_false;
    let coverage_ready =
        coverage_summary.expanded_coverage_observed && coverage_summary.raw_flags_all_false;
    let aggregate_ready = movement_ready && coverage_ready;
    let runtime_adapter_connection_evidence = movement_summary.adapter_allowed_count > 0
        || coverage_summary.adapter_allowed_count > 0
        || movement_summary.side_signal_ok_count > 0
        || coverage_summary.side_signal_ok_count > 0;
    let recommended_next_step = if aggregate_ready {
        "prepare_human_runtime_influence_review_request"
    } else {
        "collect_missing_redacted_evidence"
    };
    let review_state = if aggregate_ready {
        "redacted_aggregate_ready"
    } else {
        "redacted_aggregate_incomplete"
    };

    let payload = json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_REDACTED_EVIDENCE_AGGREGATE_SCHEMA,
        "read_only": true,
        "redacted_evidence_aggregate": true,
        "implementation_stage": "post_runtime_redacted_evidence_aggregate",
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "purpose": "Aggregate redacted controlled rank-movement evidence and expanded adapter-coverage evidence without copying raw inputs or granting runtime/default retrieval approval.",
        "status": "completed",
        "reviewer": optional_string_json(reviewer),
        "commit": optional_string_json(commit),
        "forum_post_id": optional_string_json(forum_post_id),
        "memory_key": optional_string_json(memory_key),
        "input_contract": {
            "movement_fixture_run_schema": movement.get("schema").cloned().unwrap_or(Value::Null),
            "coverage_fixture_run_schema": coverage.get("schema").cloned().unwrap_or(Value::Null),
            "movement_fixture_run_included": false,
            "coverage_fixture_run_included": false,
            "unknown_fields_ignored": true,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "movement_evidence": redacted_fixture_run_evidence_json(&movement_summary),
        "coverage_evidence": redacted_fixture_run_evidence_json(&coverage_summary),
        "interpretation": {
            "movement_redacted_evidence_ready": movement_ready,
            "expanded_coverage_redacted_evidence_ready": coverage_ready,
            "runtime_adapter_connection_evidence": runtime_adapter_connection_evidence,
            "controlled_rank_movement_observed": movement_summary.movement_observed,
            "expanded_coverage_without_additional_movement": coverage_summary.expanded_coverage_observed,
            "aggregate_evidence_ready": aggregate_ready,
            "default_influence_ready": false,
            "human_review_required": true,
            "why_not_default": "aggregate is explicit-opt-in review evidence only; fixture runs are non-production; default memory_search remains unchanged",
            "recommended_next_step": recommended_next_step,
            "review_state": review_state,
        },
        "approval_state": "evidence_aggregate_only",
        "authorization_state": "does_not_grant_runtime_influence",
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "default_calls_unchanged": true,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
    });

    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in redacted evidence aggregate");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "review_state={} aggregate_ready={} default_influence_ready={}",
        shadow_json_display(payload.pointer("/interpretation/review_state"), "-"),
        shadow_json_display(
            payload.pointer("/interpretation/aggregate_evidence_ready"),
            "false"
        ),
        shadow_json_display(
            payload.pointer("/interpretation/default_influence_ready"),
            "false"
        )
    );
    println!(
        "movement_moved={} coverage_queries={} coverage_experimental={} coverage_moved={}",
        movement_summary.actual_order_changed_count,
        coverage_summary.query_count,
        coverage_summary.experimental_source_count,
        coverage_summary.actual_order_changed_count
    );
    println!(
        "recommended_next_step={} raw_flags movement={} coverage={}",
        shadow_json_display(
            payload.pointer("/interpretation/recommended_next_step"),
            "-"
        ),
        movement_summary.raw_flags_all_false,
        coverage_summary.raw_flags_all_false
    );
    Ok(())
}

#[derive(Debug, Clone)]
struct BioCortexRedactedFixtureRunEvidence {
    schema_ok: bool,
    expected_met: bool,
    seeded_memory_count: u64,
    query_count: u64,
    adapter_allowed_count: u64,
    side_signal_ok_count: u64,
    experimental_source_count: u64,
    actual_order_changed_count: u64,
    hash_matches_baseline_count: u64,
    raw_flags_all_false: bool,
    movement_observed: bool,
    expanded_coverage_observed: bool,
}

fn summarize_biocortex_redacted_fixture_run(value: &Value) -> BioCortexRedactedFixtureRunEvidence {
    let summary = value
        .pointer("/diagnostics/summary")
        .unwrap_or(&Value::Null);
    let schema_ok = evidence_json_str_eq(
        value.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_CONTROLLED_ORDER_FIXTURE_RUN_SCHEMA,
    );
    let expected_met = evidence_json_bool_is(value.pointer("/expected/met"), true);
    let query_count = evidence_json_u64(summary.get("query_count"));
    let adapter_allowed_count = evidence_json_u64(summary.get("adapter_allowed_count"));
    let side_signal_ok_count = evidence_json_u64(summary.get("side_signal_ok_count"));
    let experimental_source_count = evidence_json_u64(summary.get("experimental_source_count"));
    let actual_order_changed_count = evidence_json_u64(summary.get("actual_order_changed_count"));
    let hash_matches_baseline_count = evidence_json_u64(summary.get("hash_matches_baseline_count"));
    let raw_flags_all_false = evidence_json_bool_is(
        value.pointer("/diagnostics/safety/raw_flags_all_false"),
        true,
    ) && evidence_json_bool_is(value.get("raw_queries_included"), false)
        && evidence_json_bool_is(value.get("raw_keys_included"), false)
        && evidence_json_bool_is(value.get("content_included"), false)
        && evidence_json_bool_is(value.get("side_signal_raw_included"), false)
        && evidence_json_bool_is(
            value.pointer("/fixture_contract/raw_queries_included"),
            false,
        )
        && evidence_json_bool_is(value.pointer("/fixture_contract/raw_keys_included"), false)
        && evidence_json_bool_is(value.pointer("/fixture_contract/content_included"), false)
        && evidence_json_bool_is(
            value.pointer("/fixture_contract/side_signal_raw_included"),
            false,
        );
    let movement_observed = schema_ok && expected_met && actual_order_changed_count > 0;
    let expanded_coverage_observed = schema_ok
        && expected_met
        && query_count >= 5
        && adapter_allowed_count == query_count
        && side_signal_ok_count == query_count
        && experimental_source_count == query_count
        && actual_order_changed_count == 0;
    BioCortexRedactedFixtureRunEvidence {
        schema_ok,
        expected_met,
        seeded_memory_count: evidence_json_u64(value.pointer("/attempt/seeded_memory_count")),
        query_count,
        adapter_allowed_count,
        side_signal_ok_count,
        experimental_source_count,
        actual_order_changed_count,
        hash_matches_baseline_count,
        raw_flags_all_false,
        movement_observed,
        expanded_coverage_observed,
    }
}

fn redacted_fixture_run_evidence_json(summary: &BioCortexRedactedFixtureRunEvidence) -> Value {
    json!({
        "schema_ok": summary.schema_ok,
        "expected_met": summary.expected_met,
        "seeded_memory_count": summary.seeded_memory_count,
        "query_count": summary.query_count,
        "adapter_allowed_count": summary.adapter_allowed_count,
        "side_signal_ok_count": summary.side_signal_ok_count,
        "experimental_source_count": summary.experimental_source_count,
        "actual_order_changed_count": summary.actual_order_changed_count,
        "hash_matches_baseline_count": summary.hash_matches_baseline_count,
        "raw_flags_all_false": summary.raw_flags_all_false,
        "movement_observed": summary.movement_observed,
        "expanded_coverage_observed": summary.expanded_coverage_observed,
    })
}

fn load_biocortex_redacted_json(path: &std::path::Path, label: &str) -> Result<Value> {
    let body = std::fs::read_to_string(path)
        .map_err(|e| anyhow::anyhow!("read {label} at {path:?}: {e}"))?;
    serde_json::from_str(&body).map_err(|e| anyhow::anyhow!("parse {label} at {path:?}: {e}"))
}

fn optional_string_json(value: Option<String>) -> Value {
    value
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(Value::String)
        .unwrap_or(Value::Null)
}

fn evidence_json_u64(value: Option<&Value>) -> u64 {
    value.and_then(Value::as_u64).unwrap_or(0)
}

fn evidence_json_bool_is(value: Option<&Value>, expected: bool) -> bool {
    value.and_then(Value::as_bool) == Some(expected)
}

fn evidence_json_str_eq(value: Option<&Value>, expected: &str) -> bool {
    value.and_then(Value::as_str) == Some(expected)
}

fn controlled_fixture_db_path() -> Result<PathBuf> {
    let raw = std::env::var("AGENT_BRIDGE_DB")
        .map_err(|_| anyhow::anyhow!("controlled order fixture requires AGENT_BRIDGE_DB"))?;
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Err(anyhow::anyhow!(
            "controlled order fixture requires non-empty AGENT_BRIDGE_DB"
        ));
    }
    let db_path = PathBuf::from(trimmed);
    let default_path = default_db_path();
    if paths_equivalent_or_equal(&db_path, &default_path) {
        return Err(anyhow::anyhow!(
            "controlled order fixture refuses to write the default Agent-Bridge DB; set AGENT_BRIDGE_DB to a non-production path"
        ));
    }
    Ok(db_path)
}

fn paths_equivalent_or_equal(a: &std::path::Path, b: &std::path::Path) -> bool {
    if a == b {
        return true;
    }
    match (a.canonicalize(), b.canonicalize()) {
        (Ok(a), Ok(b)) => a == b,
        _ => false,
    }
}

fn load_biocortex_controlled_order_fixture(
    path: &std::path::Path,
) -> Result<BioCortexControlledOrderFixture> {
    let body = std::fs::read_to_string(path)
        .map_err(|e| anyhow::anyhow!("read controlled order fixture JSON at {path:?}: {e}"))?;
    let fixture: BioCortexControlledOrderFixture = serde_json::from_str(&body)
        .map_err(|e| anyhow::anyhow!("parse controlled order fixture JSON at {path:?}: {e}"))?;
    if fixture.memory_records.is_empty() {
        return Err(anyhow::anyhow!(
            "controlled order fixture at {path:?} must contain memory_records"
        ));
    }
    if fixture.query_cases.is_empty() {
        return Err(anyhow::anyhow!(
            "controlled order fixture at {path:?} must contain query_cases"
        ));
    }
    Ok(fixture)
}

fn load_biocortex_batch_query_cases(
    query_cases_json: Option<&std::path::Path>,
    queries: &[String],
    query_classes: &[String],
) -> Result<Vec<BioCortexRetrievalOptInBatchQueryCase>> {
    let mut cases = Vec::new();
    if let Some(path) = query_cases_json {
        let body = std::fs::read_to_string(path).map_err(|e| {
            anyhow::anyhow!("read batch diagnostics query cases JSON at {path:?}: {e}")
        })?;
        let value: Value = serde_json::from_str(&body).map_err(|e| {
            anyhow::anyhow!("parse batch diagnostics query cases JSON at {path:?}: {e}")
        })?;
        let Some(values) = batch_query_case_array(&value) else {
            return Err(anyhow::anyhow!(
                "batch diagnostics query cases JSON at {path:?} must be an array or contain query_cases/queries array"
            ));
        };
        for value in values {
            if let Some(query) = value.as_str() {
                cases.push(BioCortexRetrievalOptInBatchQueryCase {
                    query: query.to_string(),
                    class_label: None,
                });
            } else if let Some(query) = value.get("query").and_then(Value::as_str) {
                cases.push(BioCortexRetrievalOptInBatchQueryCase {
                    query: query.to_string(),
                    class_label: value
                        .get("class_label")
                        .or_else(|| value.get("class"))
                        .and_then(Value::as_str)
                        .map(str::to_string),
                });
            }
        }
    }
    cases.extend(queries.iter().enumerate().map(|(idx, query)| {
        BioCortexRetrievalOptInBatchQueryCase {
            query: query.clone(),
            class_label: query_classes.get(idx).cloned(),
        }
    }));
    Ok(cases)
}

fn batch_query_case_array(value: &Value) -> Option<&Vec<Value>> {
    value.as_array().or_else(|| {
        value
            .get("query_cases")
            .and_then(Value::as_array)
            .or_else(|| value.get("queries").and_then(Value::as_array))
    })
}

#[cfg(feature = "biocortex-retrieval-shadow")]
#[allow(clippy::too_many_arguments)]
async fn run_biocortex_retrieval_shadow(
    query: Option<String>,
    input_json: Option<&std::path::Path>,
    candidates_json: Option<&std::path::Path>,
    expected_key: Option<String>,
    checkout: Option<PathBuf>,
    timeout_ms: u64,
    include_raw: bool,
    as_json: bool,
) -> Result<()> {
    let mut resolved_query = query;
    let mut resolved_expected = expected_key;
    let candidates = if let Some(path) = input_json {
        let body = std::fs::read_to_string(path)
            .map_err(|e| anyhow::anyhow!("read BioCortex retrieval input at {path:?}: {e}"))?;
        let value: Value = serde_json::from_str(&body)
            .map_err(|e| anyhow::anyhow!("parse BioCortex retrieval input at {path:?}: {e}"))?;
        if resolved_query.is_none() {
            resolved_query = value
                .get("query")
                .and_then(Value::as_str)
                .map(str::to_string);
        }
        if resolved_expected.is_none() {
            resolved_expected = value
                .get("expected_key")
                .and_then(Value::as_str)
                .map(str::to_string);
        }
        let candidate_value = value
            .get("candidates")
            .cloned()
            .unwrap_or_else(|| value.clone());
        serde_json::from_value::<Vec<BioCortexRetrievalCandidate>>(candidate_value)
            .map_err(|e| anyhow::anyhow!("parse candidates in {path:?}: {e}"))?
    } else if let Some(path) = candidates_json {
        let body = std::fs::read_to_string(path)
            .map_err(|e| anyhow::anyhow!("read BioCortex candidates at {path:?}: {e}"))?;
        serde_json::from_str::<Vec<BioCortexRetrievalCandidate>>(&body)
            .map_err(|e| anyhow::anyhow!("parse BioCortex candidates at {path:?}: {e}"))?
    } else {
        anyhow::bail!("provide --input-json or --candidates-json");
    };
    let query = resolved_query
        .map(|q| q.trim().to_string())
        .filter(|q| !q.is_empty())
        .ok_or_else(|| anyhow::anyhow!("provide --query or query in --input-json"))?;

    let payload = biocortex_retrieval_shadow_report(BioCortexRetrievalShadowOptions {
        query,
        candidates,
        expected_key: resolved_expected,
        checkout,
        timeout_ms,
        include_raw,
    })
    .await;

    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval shadow report");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!("status={}", shadow_json_display(payload.get("status"), "-"));
    if let Some(reason) = payload.get("reason") {
        println!("reason={}", shadow_json_display(Some(reason), "-"));
    }
    println!(
        "runtime_adapter_approved={} default_search_order_changed={}",
        shadow_json_display(payload.get("runtime_adapter_approved"), "false"),
        shadow_json_display(payload.get("default_search_order_changed"), "false")
    );
    println!(
        "alpha_policy={} alpha={} explicit_alpha={}",
        shadow_json_display(payload.get("alpha_policy"), "-"),
        shadow_json_display(payload.get("blend_alpha"), "-"),
        shadow_json_display(payload.get("explicit_alpha"), "false")
    );
    println!(
        "coverage={} latency_ms={}",
        shadow_json_display(payload.get("side_signal_coverage"), "0"),
        shadow_json_display(payload.get("latency_ms"), "-")
    );
    println!(
        "baseline_top={} advisory_top={} expected_regressions={}",
        shadow_json_display(payload.get("baseline_top_key"), "-"),
        shadow_json_display(payload.get("advisory_top_key"), "-"),
        shadow_json_display(payload.get("expected_regressions"), "0")
    );
    let gates = payload.get("gates").unwrap_or(&Value::Null);
    println!(
        "gates feature_enabled={} runtime_enabled={} operator_disabled={}",
        shadow_json_display(gates.get("compile_feature_enabled"), "false"),
        shadow_json_display(gates.get("runtime_enabled"), "false"),
        shadow_json_display(gates.get("operator_disabled"), "false")
    );
    Ok(())
}

fn shadow_json_display(value: Option<&Value>, default: &str) -> String {
    match value {
        Some(Value::String(s)) => s.clone(),
        Some(Value::Bool(b)) => b.to_string(),
        Some(Value::Number(n)) => n.to_string(),
        Some(Value::Array(items)) => {
            if items.is_empty() {
                "[]".to_string()
            } else {
                items
                    .iter()
                    .map(|v| shadow_json_display(Some(v), "null"))
                    .collect::<Vec<_>>()
                    .join(",")
            }
        }
        Some(Value::Null) | None => default.to_string(),
        Some(other) => other.to_string(),
    }
}

/// **v22** — Substrate stats CLI. Reads the in-process global installed by
/// `ab_seed_bridge::install_default()`. If substrate is not installed (env
/// not set, or process didn't install), reports config + the disabled state
/// — useful for confirming env var spelling.
///
/// **Phase 3 (C)**: in addition, attempts to read `substrate.parquet`
/// from `path_override` → installed-substrate's path →
/// `default_snapshot_path()`, and reports row counts / latest fingerprints
/// / file size. Snapshot section appears in both pretty and JSON output
/// when a readable file is found.
async fn run_substrate_stats(path_override: Option<PathBuf>, as_json: bool) -> Result<()> {
    use ab_seed_bridge::snapshot;
    let env_on = ab_seed_bridge::env_enabled();
    let installed = ab_seed_bridge::current();
    let stats = installed.as_ref().map(|s| s.stats());

    let resolved_path: Option<PathBuf> = path_override
        .or_else(|| installed.as_ref().and_then(|s| s.snapshot_path()))
        .or_else(snapshot::default_snapshot_path);

    let snapshot_summary = match resolved_path.as_ref() {
        Some(p) if p.exists() => match snapshot::read_all(p) {
            Ok(rows) => {
                let bytes = std::fs::metadata(p).ok().map(|m| m.len());
                Some(summarize_snapshot_rows(p, bytes, &rows))
            }
            Err(e) => {
                eprintln!("warn: read substrate snapshot {}: {}", p.display(), e);
                None
            }
        },
        _ => None,
    };

    if as_json {
        let payload = json!({
            "env_var": ab_seed_bridge::SUBSTRATE_ENV_VAR,
            "env_enabled": env_on,
            "installed": stats.is_some(),
            "stats": stats,
            "snapshot_path": resolved_path.as_ref().map(|p| p.to_string_lossy()),
            "snapshot": snapshot_summary,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# v22 substrate stats");
    println!(
        "env: {var}={state}",
        var = ab_seed_bridge::SUBSTRATE_ENV_VAR,
        state = if env_on {
            "enabled"
        } else {
            "unset (substrate disabled)"
        }
    );
    match stats {
        Some(s) => {
            println!("backend (inner) : {}", s.backend_name);
            println!("projection      : {}", s.projection);
            println!("N (neurons)     : {}", s.n);
            println!("D (substrate)   : {}", s.d);
            println!("outer_dim       : {}", s.outer_dim);
            println!("step_count      : {}", s.step_count);
            println!(
                "last surprise   : mean={:.4} max={:.4}",
                s.last_surprise_mean, s.last_surprise_max
            );
            println!("|conn| mean     : {:.6}", s.connection_mean_abs);
            match resolved_path.as_ref() {
                Some(p) => println!("snapshot path   : {}", p.display()),
                None => println!("snapshot path   : (no path configured)"),
            }
            if s.step_count == 0 {
                println!();
                println!("(no perception events yet — substrate is opt-in to this process only;");
                println!(" trigger via memory_save / memory_search inside an MCP session with");
                println!(" `AB_SUBSTRATE=1` in env — phase 2.2 will append snapshot rows once");
                println!(" the cadence triggers (every 20 events / every 100 events or 6h))");
            }
        }
        None => {
            println!("not installed");
            match resolved_path.as_ref() {
                Some(p) => println!("(snapshot probe path: {})", p.display()),
                None => println!(),
            }
            if snapshot_summary.is_none() {
                println!("(set `AB_SUBSTRATE=1` in env and re-launch the long-lived process;");
                println!(" phase 2.2 ships snapshot persistence to");
                println!(" `$HOME/.local/share/agent-bridge/substrate.parquet`)");
            }
        }
    }
    if let Some(sum) = &snapshot_summary {
        println!();
        println!("# snapshot file");
        println!("file size       : {}", human_bytes(sum.file_bytes));
        println!(
            "rows            : total={} hot={} long={}",
            sum.total_rows, sum.hot_rows, sum.long_rows
        );
        match &sum.latest_long {
            Some(li) => println!(
                "latest Long     : step={} ts={} fp={}",
                li.step, li.cycle_ts, li.fingerprint
            ),
            None => println!("latest Long     : (none)"),
        }
        match &sum.latest_hot {
            Some(hi) => println!(
                "latest Hot      : step={} ts={} fp={}",
                hi.step, hi.cycle_ts, hi.fingerprint
            ),
            None => println!("latest Hot      : (none)"),
        }
    }
    Ok(())
}

/// Phase 3 (C) snapshot summary returned from `summarize_snapshot_rows`.
/// Exposed as serde for the JSON payload of `substrate stats`.
#[derive(Debug, Clone, serde::Serialize)]
struct SnapshotSummary {
    path: String,
    file_bytes: Option<u64>,
    total_rows: usize,
    hot_rows: usize,
    long_rows: usize,
    latest_hot: Option<SnapshotEntry>,
    latest_long: Option<SnapshotEntry>,
}

#[derive(Debug, Clone, serde::Serialize)]
struct SnapshotEntry {
    step: i64,
    cycle_ts: i64,
    fingerprint: String,
}

/// Build a [`SnapshotSummary`] from `read_all` rows. Pure helper, tested.
fn summarize_snapshot_rows(
    path: &std::path::Path,
    file_bytes: Option<u64>,
    rows: &[ab_seed_bridge::SnapshotRow],
) -> SnapshotSummary {
    use ab_seed_bridge::{snapshot, SnapshotTier};
    let mut hot_rows = 0usize;
    let mut long_rows = 0usize;
    for r in rows {
        match r.tier {
            SnapshotTier::Hot => hot_rows += 1,
            SnapshotTier::Long => long_rows += 1,
        }
    }
    let latest_hot = rows
        .iter()
        .rev()
        .find(|r| matches!(r.tier, SnapshotTier::Hot))
        .map(|r| SnapshotEntry {
            step: r.step,
            cycle_ts: r.cycle_ts,
            fingerprint: snapshot::fingerprint(r),
        });
    let latest_long = rows
        .iter()
        .rev()
        .find(|r| matches!(r.tier, SnapshotTier::Long))
        .map(|r| SnapshotEntry {
            step: r.step,
            cycle_ts: r.cycle_ts,
            fingerprint: snapshot::fingerprint(r),
        });
    SnapshotSummary {
        path: path.to_string_lossy().to_string(),
        file_bytes,
        total_rows: rows.len(),
        hot_rows,
        long_rows,
        latest_hot,
        latest_long,
    }
}

/// Human-readable byte size for `Option<u64>`. Returns `"(unknown)"` for None.
fn human_bytes(b: Option<u64>) -> String {
    match b {
        None => "(unknown)".to_string(),
        Some(n) if n < 1024 => format!("{} B", n),
        Some(n) if n < 1024 * 1024 => format!("{:.1} KiB", n as f64 / 1024.0),
        Some(n) if n < 1024 * 1024 * 1024 => {
            format!("{:.1} MiB", n as f64 / (1024.0 * 1024.0))
        }
        Some(n) => format!("{:.2} GiB", n as f64 / (1024.0 * 1024.0 * 1024.0)),
    }
}

/// **v22 §4 P2 measurement** — Spearman rank correlation between the
/// substrate's `neighbors_of(key, k)` (from the latest Long snapshot row)
/// and the α-graph's `cofires` neighbors of the same key. Aggregates
/// across all keys with ≥ `min_cofires` cofires degree and reports the
/// median Spearman.
///
/// **Decision rule (memo §4 P2)**: median ≥ 0.4 → P2 PASS → unlock the
/// Phase 3 cold-start probe (P3). Below 0.4 → null-result per §4 P6,
/// substrate stays as observability only, retrieval-bias wiring deferred.
///
/// Pure read; no schema, no writes.
async fn run_dream_substrate_corr_audit(
    k: usize,
    min_cofires: u32,
    snapshot_path_override: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    use ab_seed_bridge::snapshot::{self, SnapshotTier};
    use ab_store::{default_db_path, SqliteStore, StateStore};
    use std::collections::HashMap;

    let snap_path = snapshot_path_override.or_else(snapshot::default_snapshot_path);
    let snap_row = match &snap_path {
        Some(p) if p.exists() => {
            let rows = snapshot::read_all(p)
                .with_context(|| format!("read substrate snapshot {}", p.display()))?;
            rows.into_iter()
                .rev()
                .find(|r| matches!(r.tier, SnapshotTier::Long))
        }
        _ => None,
    };

    let db_path = default_db_path();
    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;
    let qualifying = store
        .cofires_keys_with_min_degree(min_cofires)
        .await
        .map_err(|e| anyhow::anyhow!("cofires_keys_with_min_degree: {e}"))?;

    let mut per_key: Vec<serde_json::Value> = Vec::new();
    let mut spearmans: Vec<f64> = Vec::new();
    let mut substrate_misses = 0u64;
    let mut bilateral_pairs = 0u64;
    for (key, deg) in &qualifying {
        let edges = store
            .memory_neighbors(key)
            .await
            .map_err(|e| anyhow::anyhow!("memory_neighbors({key}): {e}"))?;
        let mut cofires_pairs: Vec<(String, f64)> = edges
            .iter()
            .filter(|e| e.edge_type == "cofires")
            .map(|e| {
                let other = if e.from_key == *key {
                    e.to_key.clone()
                } else {
                    e.from_key.clone()
                };
                (other, e.weight)
            })
            .collect();
        cofires_pairs.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        let mut seen_co = std::collections::HashSet::new();
        cofires_pairs.retain(|(k, _)| seen_co.insert(k.clone()));

        let substrate_pairs: Vec<(String, f64)> = match snap_row.as_ref() {
            Some(row) => ab_seed_bridge::neighbors_from_snapshot(row, key, k)
                .into_iter()
                .map(|(k_text, s)| (k_text, s as f64))
                .collect(),
            None => Vec::new(),
        };
        if substrate_pairs.is_empty() {
            substrate_misses += 1;
        }

        let mut rank_co: HashMap<&str, f64> = HashMap::new();
        for (i, (k_text, _)) in cofires_pairs.iter().enumerate() {
            rank_co.insert(k_text.as_str(), (i + 1) as f64);
        }
        let mut rank_sub: HashMap<&str, f64> = HashMap::new();
        for (i, (k_text, _)) in substrate_pairs.iter().enumerate() {
            rank_sub.insert(k_text.as_str(), (i + 1) as f64);
        }
        let mut union: std::collections::BTreeSet<&str> = std::collections::BTreeSet::new();
        for (k_text, _) in &cofires_pairs {
            union.insert(k_text.as_str());
        }
        for (k_text, _) in &substrate_pairs {
            union.insert(k_text.as_str());
        }
        let n_union = union.len();
        let last_co = (cofires_pairs.len() + 1) as f64;
        let last_sub = (substrate_pairs.len() + 1) as f64;
        let spearman_opt: Option<f64> = if n_union < 3 {
            None
        } else {
            let mut sum_d_sq = 0.0_f64;
            for k_text in &union {
                let ra = *rank_co.get(*k_text).unwrap_or(&last_co);
                let rb = *rank_sub.get(*k_text).unwrap_or(&last_sub);
                sum_d_sq += (ra - rb).powi(2);
            }
            let n_f = n_union as f64;
            let denom = n_f * (n_f * n_f - 1.0);
            if denom > 0.0 {
                Some(1.0 - 6.0 * sum_d_sq / denom)
            } else {
                None
            }
        };
        if let Some(rho) = spearman_opt {
            spearmans.push(rho);
            bilateral_pairs += 1;
        }
        per_key.push(serde_json::json!({
            "key": key,
            "cofires_degree": deg,
            "cofires_neighbors": cofires_pairs.iter()
                .map(|(k, w)| serde_json::json!({"key": k, "weight": w}))
                .collect::<Vec<_>>(),
            "substrate_neighbors": substrate_pairs.iter()
                .map(|(k, w)| serde_json::json!({"key": k, "score": w}))
                .collect::<Vec<_>>(),
            "union_size": n_union,
            "spearman": spearman_opt,
        }));
    }

    let median_spearman = if spearmans.is_empty() {
        None
    } else {
        let mut v = spearmans.clone();
        v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let mid = v.len() / 2;
        Some(if v.len() % 2 == 0 {
            (v[mid - 1] + v[mid]) / 2.0
        } else {
            v[mid]
        })
    };

    let snap_step = snap_row.as_ref().map(|r| r.step);
    let snap_ts = snap_row.as_ref().map(|r| r.cycle_ts);
    let verdict = match median_spearman {
        Some(m) if m >= 0.4 => "P2 PASS (>=0.4)",
        Some(_) => "P2 not yet PASS (<0.4)",
        None => "no bilateral pairs — insufficient overlap",
    };

    if as_json {
        let payload = serde_json::json!({
            "k": k,
            "min_cofires": min_cofires,
            "snapshot_path": snap_path.as_ref().map(|p| p.to_string_lossy()),
            "snapshot_step": snap_step,
            "snapshot_ts": snap_ts,
            "qualifying_keys": qualifying.len(),
            "bilateral_pairs": bilateral_pairs,
            "substrate_misses": substrate_misses,
            "median_spearman": median_spearman,
            "verdict": verdict,
            "per_key": per_key,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# v22 §4 P2 — substrate <-> α cofires correlation audit");
    println!("DB             : {}", db_path.display());
    match (&snap_path, snap_row.as_ref()) {
        (Some(p), Some(r)) => println!(
            "Snapshot       : {} (step={} ts={})",
            p.display(),
            r.step,
            r.cycle_ts
        ),
        (Some(p), None) => println!("Snapshot       : {} (no Long row yet)", p.display()),
        (None, _) => println!("Snapshot       : (no path configured)"),
    }
    println!("Params         : k={}  min_cofires={}", k, min_cofires);
    println!();
    println!(
        "qualifying keys (>= {} cofires) : {}",
        min_cofires,
        qualifying.len()
    );
    println!("bilateral pairs (>= 3 union)    : {}", bilateral_pairs);
    println!("substrate-empty keys            : {}", substrate_misses);
    match median_spearman {
        Some(m) => println!("median Spearman                 : {:.4}", m),
        None => println!("median Spearman                 : (n/a)"),
    }
    println!("verdict                         : {}", verdict);
    if bilateral_pairs > 0 {
        println!();
        println!("(per-key detail available via --json)");
    }
    Ok(())
}

/// **v22 Phase 3 (A)** — `substrate neighbors` CLI. Loads the most recent
/// Long-tier row from `substrate.parquet` and runs
/// [`ab_seed_bridge::neighbors_from_snapshot`] against it. Pure disk read,
/// no `install_default()` — CLI is short-lived so a fresh in-process grid
/// would always be empty; reading the snapshot is the only way to answer.
///
/// When the snapshot file is missing or has no Long row yet, output is
/// empty (still exit 0). MCP `substrate_neighbors_of` is the live-grid
/// counterpart for in-daemon queries.
async fn run_substrate_neighbors(
    key: String,
    k: usize,
    path_override: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    use ab_seed_bridge::snapshot::{self, SnapshotTier};
    let path = match path_override.or_else(snapshot::default_snapshot_path) {
        Some(p) => p,
        None => {
            if as_json {
                println!(
                    "{}",
                    serde_json::json!({"neighbors": [], "reason": "no snapshot path"})
                );
            } else {
                println!("# v22 substrate neighbors");
                println!("(no snapshot path configured; rerun with --path)");
            }
            return Ok(());
        }
    };
    if !path.exists() {
        if as_json {
            println!(
                "{}",
                serde_json::json!({
                    "neighbors": [],
                    "reason": "snapshot file missing",
                    "path": path.to_string_lossy(),
                })
            );
        } else {
            println!("# v22 substrate neighbors");
            println!("(snapshot file not found at {})", path.to_string_lossy());
        }
        return Ok(());
    }
    let rows = snapshot::read_all(&path)
        .with_context(|| format!("read substrate snapshot {}", path.display()))?;
    let latest_long = rows
        .iter()
        .rev()
        .find(|r| matches!(r.tier, SnapshotTier::Long));
    let neighbors = match latest_long {
        Some(row) => ab_seed_bridge::neighbors_from_snapshot(row, &key, k),
        None => Vec::new(),
    };
    if as_json {
        let payload: Vec<_> = neighbors
            .iter()
            .map(|(k_text, score)| serde_json::json!({"key": k_text, "score": score}))
            .collect();
        println!(
            "{}",
            serde_json::to_string_pretty(&serde_json::json!({
                "key": key,
                "k": k,
                "row_step": latest_long.map(|r| r.step),
                "row_ts": latest_long.map(|r| r.cycle_ts),
                "neighbors": payload,
            }))?
        );
        return Ok(());
    }
    println!("# v22 substrate neighbors of {}", key);
    match latest_long {
        Some(row) => println!("(source: snapshot step={} ts={})", row.step, row.cycle_ts),
        None => {
            println!("(no Long-tier snapshot row yet — substrate needs ≥100 perception events)")
        }
    }
    if neighbors.is_empty() {
        println!("(no neighbors)");
    } else {
        for (i, (k_text, score)) in neighbors.iter().enumerate() {
            println!("{:>3}. {:.6}  {}", i + 1, score, k_text);
        }
    }
    Ok(())
}

/// **v22 Phase 3 (B)** — `substrate replay` CLI. Reads a JSONL event log,
/// runs each event through a fresh in-process `SeedBackend`, force-writes
/// a final Long-tier snapshot, and emits the SHA256 fingerprint of that
/// row. Tool for v22 §4 P5 cross-machine determinism.
///
/// **Determinism caveat**: `seed_neuron::NeuronGrid::new` and `step` both
/// use `rand::thread_rng()`, so fingerprints will differ across runs (and
/// across machines) until the AiOT crate exposes a seeded variant.
/// `--seed` is reserved and emitted in the JSON output so once the
/// upstream supports it, this CLI becomes a true determinism gate.
async fn run_substrate_replay(
    log_path: PathBuf,
    seed: u64,
    n: usize,
    d: usize,
    use_hash: bool,
    output_override: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    use ab_seed_bridge::snapshot::{self, SnapshotTier};
    use ab_seed_bridge::{SeedBackend, SubstrateConfig};
    use ab_store::embedding::{EmbeddingBackend, HashBackend, OnnxBackend};
    use std::sync::Arc;

    // --- 1. Parse event log ---
    // P-γ: each event is (text_to_embed, key_to_perceive_opt). When key
    // is None we fall back to text (backward-compat with pre-P-γ replay
    // JSONL that only carried `text`). Production-style replays should
    // include `key` so substrate.neighbors_of(memory_key) is queryable.
    let raw = std::fs::read_to_string(&log_path)
        .with_context(|| format!("read event log {}", log_path.display()))?;
    let mut events: Vec<(String, String)> = Vec::new();
    let mut parse_skips = 0u64;
    for line in raw.lines() {
        match parse_event_line(line) {
            Some((text, key_opt)) => {
                let key = key_opt.unwrap_or_else(|| text.clone());
                events.push((text, key));
            }
            None => parse_skips += 1,
        }
    }

    // --- 2. Prepare output path ---
    let output: PathBuf = match output_override {
        Some(p) => p,
        None => {
            let mut p = std::env::temp_dir();
            p.push(format!(
                "agent-bridge-replay-{}.parquet",
                std::process::id()
            ));
            p
        }
    };
    if output.exists() {
        std::fs::remove_file(&output)
            .with_context(|| format!("clearing prior replay output at {}", output.display()))?;
    }

    // --- 3. Build SeedBackend on chosen inner backend ---
    let inner: Arc<dyn EmbeddingBackend> = if use_hash {
        Arc::new(HashBackend)
    } else {
        Arc::new(OnnxBackend)
    };
    let cfg = SubstrateConfig {
        n,
        d,
        state_noise: 0.01,
        lr: 0.01,
    };
    let backend = SeedBackend::wrap_with(inner, cfg);
    backend.set_snapshot_path(Some(output.clone()));

    // --- 4. Replay ---
    // P-γ: perceive(text, key) lets the substrate index by key while
    // embedding text — falls back to embed-equivalent behaviour when
    // event omitted `key` (key=text via the parse step above).
    for (text, key) in &events {
        let _ = backend.perceive(text, key);
    }
    let stats = backend.stats();

    // --- 5. Force a final Long snapshot (so cross-machine compare always has a target) ---
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let final_fp = match backend.build_row(SnapshotTier::Long, now) {
        Some(row) => match snapshot::append_row(&output, row) {
            Ok(fp) => Some(fp),
            Err(e) => {
                eprintln!("warn: forced Long snapshot append failed: {e}");
                None
            }
        },
        None => None,
    };

    // --- 6. Re-read snapshot to count rows + latest fingerprint ---
    let rows = snapshot::read_all(&output).unwrap_or_default();
    let latest_long = rows
        .iter()
        .rev()
        .find(|r| matches!(r.tier, SnapshotTier::Long));
    let latest_long_fp = latest_long.map(snapshot::fingerprint);

    let warnings = vec![
        "NeuronGrid::new / step use rand::thread_rng() — cross-machine sha256 will differ"
            .to_string(),
        format!("--seed {seed} logged but not yet effective (AiOT crate pending)"),
    ];

    if as_json {
        let payload = serde_json::json!({
            "log_path": log_path.to_string_lossy(),
            "events_parsed": events.len(),
            "events_skipped": parse_skips,
            "step_count_final": stats.step_count,
            "seed": seed,
            "n": n,
            "d": d,
            "encoder": if use_hash { "hash" } else { "onnx" },
            "snapshot_path": output.to_string_lossy(),
            "snapshot_rows": rows.len(),
            "latest_long_fingerprint": latest_long_fp,
            "forced_final_fingerprint": final_fp,
            "rng_determinism": false,
            "warnings": warnings,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# v22 Phase 3 (B) — substrate replay");
    println!("log              : {}", log_path.display());
    println!(
        "events           : parsed={} skipped={}",
        events.len(),
        parse_skips
    );
    println!(
        "config           : n={n}  d={d}  encoder={}",
        if use_hash { "hash" } else { "onnx" }
    );
    println!("seed (reserved)  : {seed}");
    println!("snapshot         : {}", output.display());
    println!("snapshot rows    : {}", rows.len());
    match (&latest_long_fp, &final_fp) {
        (Some(fp), _) => println!("latest Long fp   : {}", fp),
        (None, Some(fp)) => println!("forced final fp  : {}", fp),
        (None, None) => println!("(no Long row produced)"),
    }
    println!("step_count       : {}", stats.step_count);
    println!();
    println!("Warnings:");
    for w in &warnings {
        println!("  - {w}");
    }
    Ok(())
}

/// Parse one JSONL event line. Returns `Some((text, key_opt))` when the
/// line is a JSON object with a non-empty `text` string field; `None`
/// for blank lines, parse errors, or missing-field lines.
///
/// **P-γ** — optional `key` field carries the perception identifier
/// (memory key in production semantics). When absent, falls back to
/// `text` as both embedded content AND perceived identifier, matching
/// pre-P-γ replay behaviour for backward compat.
///
/// Pure helper, used by `run_substrate_replay`.
fn parse_event_line(line: &str) -> Option<(String, Option<String>)> {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return None;
    }
    let v: serde_json::Value = serde_json::from_str(trimmed).ok()?;
    let text = v.get("text")?.as_str()?;
    if text.is_empty() {
        return None;
    }
    let key = v
        .get("key")
        .and_then(|k| k.as_str())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string());
    Some((text.to_string(), key))
}

/// **v22 Phase 2.2 read side** — `substrate snapshot` CLI. Reads the
/// Parquet file written by long-lived substrate-enabled processes. Pure
/// disk read, no `install_default()` needed — this is the asymmetric
/// counterpart to `substrate stats` (which queries the in-process global).
///
/// Use cases:
/// 1. Inspect what a *different* process has been learning ("forum
///    pipeline can read what MCP saw").
/// 2. Cross-machine fingerprint compare for G4 determinism gate
///    (`--fingerprint-only` then `diff` two outputs).
/// 3. Forum/dream offline analysis of trailing surprise trends.
async fn run_substrate_snapshot(
    path_override: Option<PathBuf>,
    limit: usize,
    tier_filter: Option<String>,
    fingerprint_only: bool,
    as_json: bool,
) -> Result<()> {
    use anyhow::anyhow;

    let path = path_override
        .or_else(ab_seed_bridge::snapshot::default_snapshot_path)
        .ok_or_else(|| anyhow!("no $HOME — pass --path explicitly"))?;

    let mut rows = ab_seed_bridge::snapshot::read_all(&path)
        .map_err(|e| anyhow!("read {}: {}", path.display(), e))?;

    if let Some(t) = tier_filter.as_deref() {
        let want = ab_seed_bridge::snapshot::SnapshotTier::from_str(t)
            .ok_or_else(|| anyhow!("unknown tier '{t}' — expected hot|long"))?;
        rows.retain(|r| r.tier == want);
    }

    if limit > 0 && rows.len() > limit {
        let skip = rows.len() - limit;
        rows = rows.into_iter().skip(skip).collect();
    }

    if fingerprint_only {
        for row in &rows {
            println!("{}", ab_seed_bridge::snapshot::fingerprint(row));
        }
        return Ok(());
    }

    if as_json {
        let payload: Vec<_> = rows
            .iter()
            .map(|r| {
                json!({
                    "step": r.step,
                    "cycle_ts": r.cycle_ts,
                    "tier": r.tier.as_str(),
                    "n_alive": r.n_alive,
                    "trailing_surprise_mean_short": r.trailing_surprise_mean_short,
                    "trailing_surprise_mean_long": r.trailing_surprise_mean_long,
                    "connection_logits_len": r.connection_logits.len(),
                    "in_strengths_mean": mean_f32(&r.in_strengths),
                    "fingerprint": ab_seed_bridge::snapshot::fingerprint(r),
                })
            })
            .collect();
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "path": path.display().to_string(),
                "rows_shown": payload.len(),
                "rows": payload,
            }))?
        );
        return Ok(());
    }

    println!("# v22 substrate snapshot");
    println!("path : {}", path.display());
    if rows.is_empty() {
        println!("(no rows yet — file absent or empty)");
        return Ok(());
    }
    println!("rows : {} shown", rows.len());
    println!();
    for r in &rows {
        let fp = ab_seed_bridge::snapshot::fingerprint(r);
        let fp_short = if fp.len() >= 16 {
            &fp[..16]
        } else {
            fp.as_str()
        };
        println!(
            "step={:<6} ts={} tier={:<4} n_alive={:<4} surprise(s/l)={:.4}/{:.4} logits={:<6} fp={}",
            r.step,
            r.cycle_ts,
            r.tier.as_str(),
            r.n_alive,
            r.trailing_surprise_mean_short,
            r.trailing_surprise_mean_long,
            r.connection_logits.len(),
            fp_short,
        );
    }
    Ok(())
}

fn mean_f32(xs: &[f32]) -> f32 {
    if xs.is_empty() {
        0.0
    } else {
        xs.iter().sum::<f32>() / xs.len() as f32
    }
}

/// OSC 133 shell-integration snippets. Source-of-truth lives here; the
/// human-readable copy in `docs/SHELL-INTEGRATION-OSC133.md` is intended
/// to track this verbatim. If you edit one, mirror the change in the doc
/// (or vice-versa) so the install instructions stay consistent.
fn shell_init_snippet(shell: ShellKind) -> &'static str {
    match shell {
        ShellKind::Bash => {
            "\
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
"
        }
        ShellKind::Zsh => {
            "\
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
"
        }
        ShellKind::Fish => {
            "\
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
"
        }
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
async fn run_worktree_session_new(name: Option<&str>, base: Option<&str>) -> Result<()> {
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
        std::fs::create_dir_all(parent).map_err(|e| anyhow::anyhow!("mkdir {parent:?}: {e}"))?;
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
    eprintln!(
        "  next: cd to the printed path; work + commit there; `git worktree remove` when merged"
    );
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
        eprintln!(
            "(no session worktrees under {})",
            repo_root.join(".worktrees").display()
        );
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

    println!("# v21 — Identity continuity (last {days}d vs prior {days}d)");
    println!("DB: {}", path.display());
    println!();

    print_identity_section(&cur, &prior);
    Ok(())
}

/// v25 — `agent-bridge dream shadow-cortex`. Read-only heuristic attention
/// report over existing Agent-Bridge telemetry. This is the Gate A baseline
/// for later Seed shadow/runtime comparison.
async fn run_dream_shadow_cortex(
    window_days: u32,
    max_signals: usize,
    source: &str,
    fixture_out: Option<&std::path::Path>,
    fixture_in: Option<&std::path::Path>,
    as_json: bool,
) -> Result<()> {
    let db_path = default_db_path();
    let fixture = if let Some(path) = fixture_in {
        let body = std::fs::read_to_string(path)
            .map_err(|e| anyhow::anyhow!("read shadow-cortex fixture at {path:?}: {e}"))?;
        serde_json::from_str::<shadow_cortex::ShadowCortexReplayFixture>(&body)
            .map_err(|e| anyhow::anyhow!("parse shadow-cortex fixture at {path:?}: {e}"))?
    } else {
        let store = SqliteStore::open(&db_path)
            .await
            .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;
        shadow_cortex::collect_shadow_cortex_fixture(
            &store,
            shadow_cortex::ShadowCortexOptions {
                window_days,
                source: source.to_string(),
            },
        )
        .await?
    };

    if let Some(path) = fixture_out {
        let body = serde_json::to_string_pretty(&fixture)?;
        std::fs::write(path, body)
            .map_err(|e| anyhow::anyhow!("write shadow-cortex fixture at {path:?}: {e}"))?;
    }

    let report = shadow_cortex::build_shadow_cortex_report_from_fixture(&fixture, max_signals)?;
    let source_label = match fixture_in {
        Some(path) => path,
        None => db_path.as_path(),
    };

    if as_json {
        println!("{}", serde_json::to_string_pretty(&report)?);
    } else {
        shadow_cortex::print_shadow_cortex_report(&report, source_label);
    }
    Ok(())
}

fn run_dream_shadow_cortex_feedback_record(
    decision: ShadowCortexFeedbackDecision,
    signal_id: &str,
    source_event_ids: Vec<String>,
    actor: &str,
    note: Option<&str>,
    path: Option<&std::path::Path>,
    as_json: bool,
) -> Result<()> {
    let record = shadow_cortex::append_feedback_record(
        path,
        decision.as_str(),
        signal_id,
        source_event_ids,
        actor,
        note,
    )?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&record)?);
    } else {
        let path = path
            .map(std::path::Path::to_path_buf)
            .unwrap_or_else(shadow_cortex::default_feedback_path);
        println!(
            "recorded shadow-cortex feedback: {} {}",
            record.decision, record.signal_id
        );
        println!("path: {}", path.display());
    }
    Ok(())
}

fn run_dream_shadow_cortex_feedback_list(
    limit: usize,
    path: Option<&std::path::Path>,
    as_json: bool,
) -> Result<()> {
    let records = shadow_cortex::read_feedback_records(path, limit)?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&records)?);
    } else if records.is_empty() {
        println!("(no shadow-cortex feedback records)");
    } else {
        for record in records {
            println!(
                "{}  {}  {}  {}",
                record.recorded_at, record.decision, record.signal_id, record.actor
            );
            if let Some(note) = record.note {
                println!("  note: {note}");
            }
            if !record.source_event_ids.is_empty() {
                println!("  source_event_ids: {}", record.source_event_ids.join(", "));
            }
        }
    }
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
                let reason = if tier == 2 {
                    "edge already exists"
                } else {
                    "cofires already exists"
                };
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
                    eprintln!("  ✗ ({} fires)  {} ↔ {}    [{e}]", c.count, pair.0, pair.1);
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
        .filter(|d| {
            matches!(
                d.status,
                PromoteStatus::Promoted | PromoteStatus::WouldPromote
            )
        })
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
        println!("(dry run — no writes)  would promote {promoted}, skip {skipped}");
    } else if errors == 0 {
        let skip_reason = if tier == 2 {
            "edge already exists"
        } else {
            "cofires already exists"
        };
        println!(
            "✓ promoted {promoted} pairs as `{primary_edge_type}`, skipped {skipped} ({skip_reason})"
        );
    } else {
        println!("promoted {promoted}, skipped {skipped}, FAILED {errors} — see stderr");
    }

    if let Some(p) = html_path {
        let html = render_promote_html(min_count, limit, dry_run, &path, &decisions);
        std::fs::write(p, html).map_err(|e| anyhow::anyhow!("write html report to {p:?}: {e}"))?;
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
        .filter(|d| {
            matches!(
                d.status,
                PromoteStatus::Promoted | PromoteStatus::WouldPromote
            )
        })
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
        let label = format!("{} ↔ {}", short_key(&d.key_a, 24), short_key(&d.key_b, 24));
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
            PromoteStatus::Failed(msg) => {
                format!(r#"<div class="error-msg">{}</div>"#, html_escape(msg))
            }
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

/// Render a self-contained HTML report for `dream codebase-report`.
///
/// Layout (top → bottom):
///   1. Header — root path, timestamp, totals
///   2. Per-language pills
///   3. Hot callees table (callee · count · callers · langs)
///   4. Hot callers table (caller · file · fan-out · total)
///   5. Fan-out files table
///   6. Orphan function candidates list (with caveat banner)
///   7. Footer — DB path, generation timestamp
///
/// Color motif matches `render_promote_html` (cyan = activity intensity,
/// purple = orphan/structural, amber = caveat) so both audit reports
/// read as a coherent family in a browser.
fn render_codebase_report_html(
    stats: &ab_store::CodebaseCallStats,
    db_path: &std::path::Path,
) -> String {
    let now = chrono_now_utc_string();

    let lang_pills = if stats.per_language.is_empty() {
        r#"<span class="empty-inline">no calls</span>"#.to_string()
    } else {
        stats
            .per_language
            .iter()
            .map(|l| {
                format!(
                    r#"<span class="lang-pill"><b>{lang}</b> <span class="num">{calls}</span> calls · <span class="num">{files}</span> files</span>"#,
                    lang = html_escape(&l.language),
                    calls = l.call_count,
                    files = l.distinct_files,
                )
            })
            .collect::<Vec<_>>()
            .join("\n")
    };

    let callee_peak = stats.hot_callees.first().map(|x| x.call_count).unwrap_or(1);
    let hot_callee_rows = stats
        .hot_callees
        .iter()
        .enumerate()
        .map(|(i, h)| {
            format!(
                r##"<tr>
  <td class="rank">{rank}</td>
  <td class="callee"><code>{callee}</code></td>
  <td class="num"><span class="bar" style="width:{bar_pct}%"></span>{count}</td>
  <td class="num">{callers}</td>
  <td class="langs">{langs}</td>
</tr>"##,
                rank = i + 1,
                callee = html_escape(&h.callee),
                bar_pct = bar_pct(h.call_count, callee_peak),
                count = h.call_count,
                callers = h.distinct_callers,
                langs = h
                    .languages
                    .iter()
                    .map(|l| format!(r#"<span class="lang-chip">{}</span>"#, html_escape(l)))
                    .collect::<Vec<_>>()
                    .join(" "),
            )
        })
        .collect::<String>();

    let caller_peak = stats
        .hot_callers
        .first()
        .map(|x| x.distinct_callees)
        .unwrap_or(1);
    let hot_caller_rows = stats
        .hot_callers
        .iter()
        .enumerate()
        .map(|(i, c)| {
            format!(
                r##"<tr>
  <td class="rank">{rank}</td>
  <td class="caller"><code>{caller}</code></td>
  <td class="file"><code>{file}</code></td>
  <td class="num"><span class="bar bar-purple" style="width:{bar_pct}%"></span>{fanout}</td>
  <td class="num">{total}</td>
  <td class="langs"><span class="lang-chip">{lang}</span></td>
</tr>"##,
                rank = i + 1,
                caller = html_escape(&c.caller),
                file = html_escape(&c.file_path),
                bar_pct = bar_pct(c.distinct_callees, caller_peak),
                fanout = c.distinct_callees,
                total = c.total_calls,
                lang = html_escape(&c.language),
            )
        })
        .collect::<String>();

    let file_peak = stats
        .fan_out_files
        .first()
        .map(|x| x.distinct_callees)
        .unwrap_or(1);
    let fan_file_rows = stats
        .fan_out_files
        .iter()
        .enumerate()
        .map(|(i, f)| {
            format!(
                r##"<tr>
  <td class="rank">{rank}</td>
  <td class="file"><code>{file}</code></td>
  <td class="num"><span class="bar bar-purple" style="width:{bar_pct}%"></span>{fanout}</td>
  <td class="num">{total}</td>
  <td class="langs"><span class="lang-chip">{lang}</span></td>
</tr>"##,
                rank = i + 1,
                file = html_escape(&f.file_path),
                bar_pct = bar_pct(f.distinct_callees, file_peak),
                fanout = f.distinct_callees,
                total = f.total_calls,
                lang = html_escape(&f.language),
            )
        })
        .collect::<String>();

    // Split orphans into high-confidence + likely-FP for visual demotion.
    let (orphan_real, orphan_fp): (Vec<_>, Vec<_>) =
        stats.orphan_functions.iter().partition(|o| !o.likely_fp);
    let orphan_rows = orphan_real
        .iter()
        .enumerate()
        .map(|(i, o)| {
            format!(
                r##"<tr>
  <td class="rank">{rank}</td>
  <td class="kind"><span class="kind-chip">{kind}</span></td>
  <td class="name"><code>{name}</code></td>
  <td class="file"><code>{file}:{line}</code></td>
  <td class="langs"><span class="lang-chip">{lang}</span></td>
</tr>"##,
                rank = i + 1,
                kind = html_escape(&o.kind),
                name = html_escape(&o.name),
                file = html_escape(&o.file_path),
                line = o.line,
                lang = html_escape(&o.language),
            )
        })
        .collect::<String>();
    let orphan_fp_rows = orphan_fp
        .iter()
        .enumerate()
        .map(|(i, o)| {
            format!(
                r##"<tr class="fp-row">
  <td class="rank">{rank}</td>
  <td class="kind"><span class="kind-chip">{kind}</span></td>
  <td class="name"><code>{name}</code></td>
  <td class="fp-reason"><span class="fp-chip">{reason}</span></td>
  <td class="file"><code>{file}:{line}</code></td>
  <td class="langs"><span class="lang-chip">{lang}</span></td>
</tr>"##,
                rank = i + 1,
                kind = html_escape(&o.kind),
                name = html_escape(&o.name),
                reason = html_escape(&o.likely_fp_reason),
                file = html_escape(&o.file_path),
                line = o.line,
                lang = html_escape(&o.language),
            )
        })
        .collect::<String>();

    let empty_state = if stats.total_calls == 0 {
        r#"<p class="empty">No calls indexed for this root. Run <code>agent-bridge codebase index &lt;root&gt;</code> first, or check that the root path matches the indexed one (canonical form).</p>"#
    } else {
        ""
    };

    format!(
        r##"<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>codebase report — {timestamp}</title>
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
    max-width: 1280px;
    margin: 0 auto;
  }}
  h1 {{ margin: 0 0 8px; font-size: 22px; font-weight: 600; }}
  h2 {{ margin: 32px 0 12px; font-size: 14px; font-weight: 600; color: var(--dim);
        text-transform: uppercase; letter-spacing: 0.08em; }}
  code {{ font-family: "JetBrains Mono", "SF Mono", Menlo, monospace; color: var(--text); }}
  a {{ color: inherit; text-decoration: none; }}
  .header {{ display: flex; flex-direction: column; gap: 6px; padding-bottom: 18px;
            border-bottom: 1px solid var(--border); }}
  .meta-row {{ display: flex; gap: 14px; flex-wrap: wrap; color: var(--dim); font-size: 12px; }}
  .meta-row code {{ color: var(--text); }}
  .stats {{ display: flex; gap: 18px; margin-top: 6px; }}
  .stat .num {{ font-size: 18px; font-weight: 600; margin-right: 4px; }}
  .stat-calls .num {{ color: var(--cyan-strong); }}
  .stat-files .num {{ color: var(--cyan-mid); }}

  .lang-pills {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 8px; }}
  .lang-pill {{ padding: 6px 12px; border-radius: 4px;
               background: var(--panel); border: 1px solid var(--border);
               font-size: 13px; color: var(--cyan-mid); }}
  .lang-pill b {{ color: var(--text); }}
  .lang-pill .num {{ color: var(--cyan-strong); font-weight: 600; }}

  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 0;
          font-size: 13px; }}
  th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--dim); font-weight: 600; font-size: 11px;
       text-transform: uppercase; letter-spacing: 0.06em; }}
  tr:hover td {{ background: rgba(255,255,255,0.025); }}
  td.rank {{ color: var(--dim); width: 36px; }}
  td.num {{ font-family: "JetBrains Mono", "SF Mono", Menlo, monospace;
           font-variant-numeric: tabular-nums; white-space: nowrap;
           position: relative; }}
  td.callee code, td.caller code, td.name code {{ color: var(--cyan-strong); }}
  td.file code {{ color: var(--dim); font-size: 12px; }}

  .bar {{ display: inline-block; height: 100%;
         position: absolute; left: 0; top: 0;
         background: linear-gradient(90deg, var(--cyan-mid), var(--cyan-strong));
         opacity: 0.18; }}
  .bar-purple {{ background: linear-gradient(90deg, var(--purple), #b07ed0); }}

  .lang-chip {{ display: inline-block; padding: 1px 6px; border-radius: 2px;
               background: rgba(92,200,200,0.1); color: var(--cyan-mid);
               font-size: 11px; font-family: "JetBrains Mono", monospace;
               margin-right: 3px; }}
  .kind-chip {{ display: inline-block; padding: 1px 6px; border-radius: 2px;
               background: rgba(122,75,168,0.12); color: var(--purple);
               font-size: 11px; font-family: "JetBrains Mono", monospace; }}
  .fp-chip {{ display: inline-block; padding: 1px 6px; border-radius: 2px;
             background: rgba(212,166,74,0.10); color: var(--amber);
             font-size: 11px; font-family: "JetBrains Mono", monospace; }}
  .fp-table tr.fp-row td {{ color: var(--dim); }}
  .fp-table tr.fp-row td.name code,
  .fp-table tr.fp-row td.file code {{ color: var(--dim); }}

  .caveat {{ margin: 10px 0; padding: 8px 12px;
            background: #2a2316; border-left: 3px solid var(--amber);
            border-radius: 2px; color: var(--amber); font-size: 12px; }}
  .caveat b {{ color: #f0c468; }}

  .empty {{ color: var(--dim); padding: 16px; background: var(--panel);
           border-radius: 4px; border: 1px dashed var(--border); }}
  .empty-inline {{ color: var(--dim); font-style: italic; }}

  .footer {{ margin-top: 36px; padding-top: 18px; border-top: 1px solid var(--border);
            color: var(--dim); font-size: 12px; }}
</style>
</head>
<body>
<div class="header">
  <h1>codebase call-graph audit</h1>
  <div class="meta-row">
    <span>root <code>{root}</code></span>
    <span>generated <code>{timestamp}</code></span>
  </div>
  <div class="stats">
    <span class="stat stat-calls"><span class="num">{total_calls}</span>calls</span>
    <span class="stat stat-files"><span class="num">{files}</span>files with calls</span>
  </div>
</div>

{empty_state}

<h2>Per-language</h2>
<div class="lang-pills">{lang_pills}</div>

<h2>Hot callees — top {hc_n}</h2>
<table>
<thead><tr>
  <th></th><th>callee (raw)</th><th>calls</th><th>callers</th><th>langs</th>
</tr></thead>
<tbody>{hot_callee_rows}</tbody>
</table>

<h2>Fan-out callers — top {hcr_n}</h2>
<table>
<thead><tr>
  <th></th><th>caller</th><th>file</th><th>fan-out</th><th>total</th><th>lang</th>
</tr></thead>
<tbody>{hot_caller_rows}</tbody>
</table>

<h2>Fan-out files — top {ff_n}</h2>
<table>
<thead><tr>
  <th></th><th>file</th><th>fan-out</th><th>total</th><th>lang</th>
</tr></thead>
<tbody>{fan_file_rows}</tbody>
</table>

<h2>Orphan function candidates — {orphan_real_n} high-confidence</h2>
<div class="caveat">
  <b>Best-effort, alias-blind.</b> Last-segment matching only — false positives include trait dispatch, dyn dispatch, reflection / string-key dispatch, FFI exports, and macro-generated callers. Use as a starting list, not a verdict.
</div>
<table>
<thead><tr>
  <th></th><th>kind</th><th>name</th><th>file:line</th><th>lang</th>
</tr></thead>
<tbody>{orphan_rows}</tbody>
</table>

<h2>Likely false positives — {orphan_fp_n}</h2>
<div class="caveat" style="background: #1f1a2a; border-left-color: var(--purple); color: var(--dim);">
  Rows tagged with known false-positive heuristics: test-file paths (callers via <code>#[test]</code> / pytest macros are invisible to the extractor), <code>main</code> entries (runtime-called), pytest <code>test_*</code> naming convention. Shown for completeness — verify before acting.
</div>
<table class="fp-table">
<thead><tr>
  <th></th><th>kind</th><th>name</th><th>reason</th><th>file:line</th><th>lang</th>
</tr></thead>
<tbody>{orphan_fp_rows}</tbody>
</table>

<div class="footer">
  DB: <code>{db_display}</code><br>
  Generated by <code>dream codebase-report</code> at <code>{timestamp}</code>.
</div>

</body>
</html>
"##,
        timestamp = html_escape(&now),
        root = html_escape(&stats.root_path),
        total_calls = stats.total_calls,
        files = stats.distinct_caller_files,
        lang_pills = lang_pills,
        hc_n = stats.hot_callees.len(),
        hot_callee_rows = hot_callee_rows,
        hcr_n = stats.hot_callers.len(),
        hot_caller_rows = hot_caller_rows,
        ff_n = stats.fan_out_files.len(),
        fan_file_rows = fan_file_rows,
        orphan_real_n = orphan_real.len(),
        orphan_rows = orphan_rows,
        orphan_fp_n = orphan_fp.len(),
        orphan_fp_rows = orphan_fp_rows,
        empty_state = empty_state,
        db_display = html_escape(&db_path.display().to_string()),
    )
}

/// Map an absolute count to a 0–100 bar width relative to a peak value.
/// Used in HTML tables to give callees / callers a visual scale-bar.
fn bar_pct(count: u64, peak: u64) -> u32 {
    if peak == 0 {
        return 0;
    }
    let raw = (count as f64 / peak as f64) * 100.0;
    raw.round().clamp(0.0, 100.0) as u32
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
    println!("window: >{window_days:.1}d unused · step: {step:.3} · floor: {floor:.3}");
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
            println!("verdict: signal undefined — too few rows or zero variance.");
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
    println!("max_count: {max_count} · older_than: {older_than_days}d · dry_run: {dry_run}");
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
    println!("blacklist_tags: {:?} · dry_run: {dry_run}", blacklist_tags);
    println!();
    let label = if dry_run { "would prune" } else { "pruned" };
    println!("{label:16} : {pruned}");
    if pruned == 0 {
        println!();
        println!("(no degenerate relates edges found — pre-ζ-11 noise hubs already cleaned)");
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
            tags: vec!["alert".into(), "zeta-15".into(), "archive-burst".into()],
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

/// **ζ-18** — CLI mirror of `memory_restore_archived` MCP tool.
/// Operator escape hatch when ζ-14 retires a row that turns out to
/// still carry signal. Single-key, status-gated, returns bool.
async fn run_dream_restore_archived(key: &str, as_json: bool) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};
    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let restored = store
        .memory_restore_archived(key)
        .await
        .map_err(|e| anyhow::anyhow!("memory_restore_archived: {e}"))?;
    if as_json {
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "key": key,
                "restored": restored,
            }))?
        );
        return Ok(());
    }
    println!("# ζ-18 — restore archived");
    println!("DB:  {}", path.display());
    println!("key: {key}");
    if restored {
        println!();
        println!("✓ restored: {key} → status=active (updated_at bumped)");
    } else {
        println!();
        println!(
            "(no-op — row is missing, already active, superseded, or tombstoned; \
             check `memory_get key={key}` for current status)"
        );
    }
    Ok(())
}

/// **ζ-19** — CLI mirror of `memory_tombstone_aged_archived` MCP tool.
/// Time-based downgrade of stale `archived` rows to `tombstoned`. Pair
/// with the existing 7-day `dream purge-tombstones` to drive the full
/// retire chain in the ζ-10 daily service.
async fn run_dream_tombstone_aged_archived(
    older_than_days: i64,
    max_count: i64,
    dry_run: bool,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};
    let older_than_days = older_than_days.max(0);
    let max_count = max_count.clamp(1, 5000);
    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let tombstoned = store
        .memory_tombstone_aged_archived(older_than_days, max_count, dry_run)
        .await
        .map_err(|e| anyhow::anyhow!("memory_tombstone_aged_archived: {e}"))?;
    if as_json {
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "dry_run": dry_run,
                "older_than_days": older_than_days,
                "max_count": max_count,
                "tombstoned_count": tombstoned,
            }))?
        );
        return Ok(());
    }
    println!("# ζ-19 — tombstone aged archived");
    println!("DB: {}", path.display());
    println!("older_than_days: {older_than_days} · max_count: {max_count} · dry_run: {dry_run}");
    println!();
    let label = if dry_run {
        "would tombstone"
    } else {
        "tombstoned"
    };
    println!("{label:18} : {tombstoned}");
    if tombstoned == 0 {
        println!();
        println!(
            "(no archived rows aged past --older-than-days; lower the threshold or check `memory_list` after archive-orphan-stubs)"
        );
    }
    Ok(())
}

/// **β v0** — Read-only probe of Hebbian clusters. Surfaces connected
/// components on the `cofires` + `co_referenced` subgraph so the
/// operator can inspect thematic coherence before β v1 layers LLM
/// abstraction on top. No writes, no LLM, no network.
async fn run_dream_cluster_probe(
    min_size: i64,
    top_k: i64,
    preview: i64,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};
    let min_size = min_size.max(2);
    let top_k = top_k.max(1) as usize;
    let preview = preview.max(1) as usize;
    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let clusters = store
        .hebbian_clusters(min_size)
        .await
        .map_err(|e| anyhow::anyhow!("hebbian_clusters: {e}"))?;

    let total_nodes: usize = clusters.iter().map(|c| c.size as usize).sum();
    let shown = clusters.len().min(top_k);

    if as_json {
        let payload = clusters
            .iter()
            .take(top_k)
            .map(|c| {
                json!({
                    "hub": c.hub,
                    "size": c.size,
                    "members": c.members,
                })
            })
            .collect::<Vec<_>>();
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "min_size": min_size,
                "clusters_total": clusters.len(),
                "clusters_shown": shown,
                "nodes_in_clusters": total_nodes,
                "clusters": payload,
            }))?
        );
        return Ok(());
    }

    println!("# β v0 — Hebbian cluster probe");
    println!("DB: {}", path.display());
    println!(
        "min_size: {min_size} · top_k: {top_k} · preview: {preview} · clusters: {n} ({shown} shown) · nodes: {total_nodes}",
        n = clusters.len()
    );
    println!();
    if clusters.is_empty() {
        println!(
            "(no Hebbian clusters yet — wait for `dream promote` (T1/T2) cron to crystallise cofires/co_referenced edges, or lower --min-size to 1)"
        );
        return Ok(());
    }
    for (i, c) in clusters.iter().take(top_k).enumerate() {
        println!(
            "## cluster #{i} (size {size}, hub: {hub})",
            i = i + 1,
            size = c.size,
            hub = c.hub
        );
        for m in c.members.iter().take(preview) {
            let star = if *m == c.hub { " ★" } else { "" };
            println!("  - {m}{star}");
        }
        if c.members.len() > preview {
            println!("  - … ({} more)", c.members.len() - preview);
        }
        println!();
    }
    if clusters.len() > top_k {
        println!(
            "({} more clusters below --top-k cap)",
            clusters.len() - top_k
        );
    }
    Ok(())
}

/// **Phase 2.x #6 — sync-window GC for tombstones.** CLI mirror of the
/// `memory_purge_tombstones` MCP tool. Hard-DELETEs rows that have been
/// tombstoned for at least `older_than_days`. Designed to ride the ζ-10
/// daily hygiene service after `dream reinforce-active` (snapshot then
/// captures the post-GC state, so tomorrow's diff sees the cleanup).
async fn run_dream_purge_tombstones(
    older_than_days: i64,
    dry_run: bool,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};
    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let removed = store
        .memory_purge_tombstones(older_than_days, dry_run)
        .await
        .map_err(|e| anyhow::anyhow!("memory_purge_tombstones: {e}"))?;

    if as_json {
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "older_than_days": older_than_days,
                "dry_run": dry_run,
                "removed_count": removed.len(),
                "removed_keys": removed,
            }))?
        );
        return Ok(());
    }

    println!("# Phase 2.x #6 — purge tombstones (sync-window GC)");
    println!("DB: {}", path.display());
    println!("older_than: {older_than_days}d · dry_run: {dry_run}");
    println!();
    let verb = if dry_run { "would remove" } else { "removed" };
    println!("{verb:<16}: {}", removed.len());
    if removed.is_empty() {
        println!();
        println!(
            "(no tombstones older than {older_than_days}d — \
             nothing to GC)"
        );
    } else if removed.len() <= 20 {
        println!();
        for k in &removed {
            println!("  · {k}");
        }
    } else {
        println!();
        for k in removed.iter().take(20) {
            println!("  · {k}");
        }
        println!("  … (+{} more)", removed.len() - 20);
    }
    Ok(())
}

/// **XM v0.5 — cross-machine messaging inbox GC (P-XM-7).** CLI / cron entry
/// point for `agent_messages_gc`. Clears rows whose effective last-touch
/// (`COALESCE(read_at, created_at)`) is older than `--max-age-days`; the
/// dry-run path shares the same match predicate so the preview can't drift
/// from the executed pass. Closes the §10 wet-validation invocation gap.
async fn run_dream_xm_gc(max_age_days: i64, dry_run: bool, as_json: bool) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};
    let max_age_days = max_age_days.max(0);
    let now_secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let max_age_secs = max_age_days.saturating_mul(86_400);
    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;
    let (cleared, retained) = store
        .agent_messages_gc(now_secs, max_age_secs, dry_run)
        .await
        .map_err(|e| anyhow::anyhow!("agent_messages_gc: {e}"))?;

    if as_json {
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "max_age_days": max_age_days,
                "dry_run": dry_run,
                "cleared": cleared,
                "retained": retained,
            }))?
        );
        return Ok(());
    }

    println!("# XM v0.5 — agent_messages inbox GC (P-XM-7)");
    println!("DB: {}", path.display());
    println!("max_age: {max_age_days}d · dry_run: {dry_run}");
    println!();
    let verb = if dry_run { "would clear" } else { "cleared" };
    let kept = if dry_run { "would retain" } else { "retained" };
    println!("{verb:<14}: {cleared}");
    println!("{kept:<14}: {retained}");
    if cleared == 0 {
        println!();
        println!("(no agent_messages older than {max_age_days}d — nothing to GC)");
    }
    Ok(())
}

/// **P-α — Always-Warm Coactivation Tick CLI mirror.** Manual / cron
/// invocation of the same `decay_coactivation_once` that the daemon
/// background task calls every `tick_secs` seconds. Useful for ad-hoc
/// inspection (`--dry-run`) and as a cron safety net independent of
/// the daemon being up.
///
/// See `docs/DESIGN-P-alpha-always-warm-coactivation-tick.md` §3.5.
async fn run_dream_decay_coactivation(
    tau_days: f64,
    max_iterations: u32,
    dry_run: bool,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};

    let tau_days = tau_days.clamp(0.5, 30.0);
    let tau_secs = (tau_days * 86_400.0) as i64;
    let max_iter = max_iterations.clamp(1, 100);
    let path = default_db_path();
    let store = SqliteStore::open(&path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {path:?}: {e}"))?;

    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);

    if dry_run {
        if as_json {
            println!(
                "{}",
                serde_json::to_string_pretty(&json!({
                    "tau_days": tau_days,
                    "tau_secs": tau_secs,
                    "max_iterations": max_iter,
                    "dry_run": true,
                    "note": "dry-run reports config only; v1 does not enumerate candidate rows",
                }))?
            );
            return Ok(());
        }
        println!("# P-α — decay-coactivation (dry-run)");
        println!("DB: {}", path.display());
        println!("tau_days: {tau_days:.1} · max_iter: {max_iter} · dry_run: true");
        println!();
        println!("(no writes performed — re-run without --dry-run to apply decay)");
        return Ok(());
    }

    let stats = store
        .decay_coactivation_once(tau_secs, now, max_iter)
        .await
        .map_err(|e| anyhow::anyhow!("decay_coactivation_once: {e}"))?;

    if as_json {
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "tau_days": tau_days,
                "tau_secs": tau_secs,
                "max_iterations": max_iter,
                "dry_run": false,
                "stats": {
                    "swept": stats.swept,
                    "pruned": stats.pruned,
                    "iterations": stats.iterations,
                },
            }))?
        );
        return Ok(());
    }

    println!("# P-α — decay-coactivation (manual mirror)");
    println!("DB: {}", path.display());
    println!("tau_days: {tau_days:.1} · max_iter: {max_iter}");
    println!();
    println!("swept       : {} rows", stats.swept);
    println!("pruned      : {} rows", stats.pruned);
    println!("iterations  : {}", stats.iterations);
    if stats.iterations == 0 {
        println!();
        println!(
            "(no rows eligible — coactivation table is fresh or tau_days \
             too small for current row ages)"
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
        println!("# waypoint pass (±{} min window)", wp.window_secs / 60);
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
            println!("verdict: replay is paying for itself — summaries out-access their sources.");
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
                println!("verdict: mixed signal — let it bake a few more days before judging.");
            }
        } else {
            println!("verdict: mixed signal — let it bake a few more days before judging.");
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
            .list_memories_in_scope("", None, ab_store::MemoryListSort::Frequent, 200)
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
        let mut events = store.recent_memory_get_keys(200).await.unwrap_or_default();
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
            *counts.entry((a_key.clone(), b_key.clone())).or_insert(0) += 1;
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
    let active_total = mstats.counts_by_status.get("active").copied().unwrap_or(0);
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
        println!(
            "# ζ-1 self-portrait snapshot ({} {})",
            chrono_like_date(now),
            node
        );
        println!();
        println!(
            "memory       : {} active / {} archived / {} edges · avg imp {:.3}",
            active_total, archived_total, mstats.edge_count, mstats.avg_importance_active
        );
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
            println!("  top persistent (count={}, span={}h):", e.count, span);
            println!(
                "    {} ↔ {}",
                short_key(&e.key_a, 40),
                short_key(&e.key_b, 40)
            );
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
            id_cur.tool_calls_total, tools_ratio, id_cur.memory_saves, saves_ratio
        );
        if transitions.is_empty() {
            println!("transitions  : (none surfaced yet — need ≥2 repeated A→B within 10min)");
        } else {
            println!("transitions  : {} surfaced", transitions.len());
            for (a, b, n) in transitions.iter().take(3) {
                println!("  [×{n}] {} → {}", short_key(a, 30), short_key(b, 30));
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

    let schema_a = pa
        .get("schema_version")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    let schema_b = pb
        .get("schema_version")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
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
        cur.as_i64()
            .or_else(|| cur.as_u64().map(|u| u as i64))
            .unwrap_or(0)
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
    let active_d =
        gi64(newer, &["memory", "active_total"]) - gi64(older, &["memory", "active_total"]);
    let archived_d =
        gi64(newer, &["memory", "archived_total"]) - gi64(older, &["memory", "archived_total"]);
    let edges_d = gi64(newer, &["memory", "edge_count"]) - gi64(older, &["memory", "edge_count"]);
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
                if o != n {
                    Some((k.clone(), *o, *n))
                } else {
                    None
                }
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
    let topo_orphan_d =
        gi64(newer, &["topology", "orphan_count"]) - gi64(older, &["topology", "orphan_count"]);
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
    println!("identity     : tools {:+} · saves {:+}", tools_d, saves_d);
    if !trans_entered.is_empty() {
        println!("transitions  : entered top-5");
        for (a, b, n) in trans_entered.iter().take(3) {
            println!("  + [×{n}] {} → {}", short_key(a, 30), short_key(b, 30));
        }
    }
    if !trans_dropped.is_empty() {
        println!("               dropped from top-5");
        for (a, b, n) in trans_dropped.iter().take(3) {
            println!("  - [×{n}] {} → {}", short_key(a, 30), short_key(b, 30));
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

    let (shadow_cortex, shadow_cortex_error) = match shadow_cortex_weekly_summary(&store).await {
        Ok(summary) => (Some(summary), None),
        Err(e) => (None, Some(e.to_string())),
    };
    let (shadow_cortex_feedback, shadow_cortex_feedback_error) =
        match shadow_cortex::feedback_summary(None, 7 * 86_400, now_epoch as i64) {
            Ok(summary) => (Some(summary), None),
            Err(e) => (None, Some(e.to_string())),
        };

    if as_json {
        let payload = serde_json::json!({
            "generated_at_epoch": now_epoch,
            "snapshot_key": snapshot_key,
            "replay_audit": replay,
            "signal_fidelity": fidelity,
            "shadow_cortex": shadow_cortex,
            "shadow_cortex_error": shadow_cortex_error,
            "shadow_cortex_feedback": shadow_cortex_feedback,
            "shadow_cortex_feedback_error": shadow_cortex_feedback_error,
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
            replay.total_summaries,
            useful_ratio,
            replay.avg_access_count,
            replay.avg_source_access_count
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

    // ── P-ε substrate-readiness one-liner ─────────────────────────────
    // Pure read; cost is bounded by memory_substrate_audit (<200ms target
    // per memo §1 G4). Surfaces 3 most-actionable numbers from the audit.
    println!();
    println!("[bonus] substrate-readiness (P-ε)");
    println!("─────────────────────────────────────────");
    match {
        use ab_store::{default_db_path, SqliteStore, StateStore as _};
        let path = default_db_path();
        let store_res = SqliteStore::open(&path).await;
        match store_res {
            Ok(s) => s.memory_substrate_audit(7 * 86_400).await,
            Err(e) => Err(ab_core::Error::Backend(format!(
                "open state.db at {path:?}: {e}"
            ))),
        }
    } {
        Ok(r) => {
            let m1_verdict = if r.m1_components.components == 0 {
                "(empty)"
            } else if r.m1_components.components == 1 {
                "⚠ hairball"
            } else if r.m1_components.components < 3 {
                "partially modular"
            } else {
                "✓ modular"
            };
            println!(
                "  substrate: {} components ({}) · {:.3} edges/active · {:.1}% L2-covered · signal={}",
                r.m1_components.components,
                m1_verdict,
                r.m2_edges.density_per_active,
                r.m5_edge_coverage.fraction * 100.0,
                r.m7_signal_fidelity.verdict,
            );
            println!("  (run `dream substrate-audit` for full M1-M8 breakdown)");
        }
        Err(e) => {
            eprintln!("  substrate-audit skipped: {e}");
        }
    }

    // ── §6.5 rule 4 — gap-audit one-liner ─────────────────────────────
    // Cheap pure-Rust + git log; surfaces the 13-gap baseline + sectional
    // delta count at the end of the weekly pulse. Full table on explicit
    // `dream gap-audit` invocation.
    println!();
    println!("[bonus #2] gap-audit (§6.5 rule 4)");
    println!("─────────────────────────────────────────");
    match gap_audit_baseline_report("7 days ago") {
        Ok(rep) => {
            let total_delta: usize = rep.sectional_delta.iter().map(|s| s.commit_count).sum();
            let next_gate = rep
                .outstanding_gates
                .iter()
                .min_by_key(|g| g.days_until.max(0));
            println!(
                "  {} closed / {} shelved / {} partial / {} planned / {} untouched",
                rep.counts.closed,
                rep.counts.shelved,
                rep.counts.partial,
                rep.counts.planned,
                rep.counts.untouched,
            );
            println!(
                "  delta since 7d: {total_delta} in-scope ships ({} layers touched)",
                rep.sectional_delta
                    .iter()
                    .filter(|s| s.commit_count > 0)
                    .count(),
            );
            match next_gate {
                Some(g) if g.days_until >= 0 => println!(
                    "  next outstanding gate: {} opens in {} days",
                    g.gate_label, g.days_until,
                ),
                Some(g) => println!(
                    "  next outstanding gate: {} opens {} days AGO (overdue)",
                    g.gate_label, -g.days_until,
                ),
                None => println!("  no future-dated outstanding gates"),
            }
            println!("  (run `dream gap-audit` for full table)");
        }
        Err(e) => {
            eprintln!("  gap-audit skipped: {e}");
        }
    }

    // ── §4 P2 substrate↔α correlation one-liner ───────────────────────
    // Auto-runs the v22 §4 P2 falsifiable measurement on the Monday
    // cadence so no human has to remember `dream substrate-corr-audit`
    // ad-hoc. Falsifiability rule: median Spearman ρ ≥ 0.4 across keys
    // with ≥3 cofires degree → P2 PASS → unlock §4 P3 cold-start probe.
    println!();
    println!("[bonus #3] substrate↔α cofires correlation (§4 P2)");
    println!("─────────────────────────────────────────");
    match substrate_corr_weekly_one_liner(20, 3).await {
        Ok(s) => match s.median_spearman {
            Some(m) => {
                println!(
                    "  median ρ = {:>+.3} · {} bilateral / {} qualifying · {}",
                    m, s.bilateral_pairs, s.qualifying_keys, s.verdict,
                );
                println!("  (run `dream substrate-corr-audit --json` for per-key detail)");
            }
            None => {
                println!(
                    "  ρ n/a · {} qualifying / {} substrate-empty · {}",
                    s.qualifying_keys, s.substrate_misses, s.verdict,
                );
                println!(
                    "  (need more snapshot history or more cofires edges; check back next week)"
                );
            }
        },
        Err(e) => {
            eprintln!("  substrate-corr-audit skipped: {e}");
        }
    }

    // ── v25 Agent Shadow Cortex one-liner ─────────────────────────────
    // First read-only consumer for the shadow-cortex lane. Keep it compact:
    // the standalone `dream shadow-cortex` command owns the full replay report.
    println!();
    println!("[bonus #4] shadow-cortex attention (v25)");
    println!("─────────────────────────────────────────");
    match shadow_cortex {
        Some(summary) => {
            print_shadow_cortex_weekly_bonus(&summary, shadow_cortex_feedback.as_ref());
            if let Some(err) = shadow_cortex_feedback_error {
                eprintln!("  shadow-cortex feedback skipped: {err}");
            }
        }
        None => {
            let err = shadow_cortex_error.unwrap_or_else(|| "unknown error".to_string());
            eprintln!("  shadow-cortex skipped: {err}");
        }
    }

    println!();
    println!(
        "next: re-run `dream weekly` in 7 days; \
         compare via `dream diff <prev_key> <this_key>` for drift."
    );
    Ok(())
}

async fn shadow_cortex_weekly_summary(
    store: &dyn StateStore,
) -> Result<shadow_cortex::ShadowCortexWeeklySummary> {
    let fixture = shadow_cortex::collect_shadow_cortex_fixture(
        store,
        shadow_cortex::ShadowCortexOptions {
            window_days: 7,
            source: "codex".to_string(),
        },
    )
    .await?;
    let report = shadow_cortex::build_shadow_cortex_report_from_fixture(&fixture, 3)?;
    Ok(shadow_cortex::weekly_summary(&report))
}

fn print_shadow_cortex_weekly_bonus(
    summary: &shadow_cortex::ShadowCortexWeeklySummary,
    feedback: Option<&shadow_cortex::ShadowCortexFeedbackSummary>,
) {
    println!(
        "  verdict: {} | mode={:?} | source={} | events={}",
        summary.verdict, summary.mode, summary.requested_source, summary.total_events,
    );
    println!(
        "  totals: tool_calls={} errors={} memory_queries={} misses={} forum_posts={}",
        summary.totals.mcp_tool_calls,
        summary.totals.mcp_tool_errors,
        summary.totals.memory_queries,
        summary.totals.memory_misses,
        summary.totals.forum_posts,
    );
    for lane in &summary.lane_coverage {
        println!(
            "  {}: {} ({}/{}, {:.0}%) rank_tie={} saturation={} top_k_cap_hits={}/{}",
            lane.lane,
            lane.state,
            lane.covered_events,
            lane.total_events,
            lane.coverage * 100.0,
            lane.rank_tie_state,
            lane.salience_saturation_state,
            lane.top_k_cap_hits,
            lane.top_k_size,
        );
    }
    if let Some(signal) = &summary.top_signal {
        println!(
            "  heuristic top: {:?}/{:?} {} ({:.2})",
            signal.scope, signal.signal_type, signal.subject_id, signal.salience,
        );
        println!("    {}", signal.summary);
    }
    if let Some(signal) = &summary.seed_shadow_top_signal {
        println!(
            "  seed-shadow top: {:?}/{:?} {} ({:.2})",
            signal.scope, signal.signal_type, signal.subject_id, signal.salience,
        );
        println!("    {}", signal.summary);
    }
    if let Some(signal) = &summary.seed_runtime_top_signal {
        println!(
            "  seed-runtime top: {:?}/{:?} {} ({:.2})",
            signal.scope, signal.signal_type, signal.subject_id, signal.salience,
        );
        println!("    {}", signal.summary);
    }
    if let Some(feedback) = feedback {
        println!(
            "  feedback 7d: {} accepted / {} ignored ({} in-window, {} total)",
            feedback.accepted, feedback.ignored, feedback.window_records, feedback.total_records,
        );
        if let Some(latest) = &feedback.latest {
            println!(
                "  latest feedback: {} {} by {}",
                latest.decision, latest.signal_id, latest.actor
            );
        }
    }
    println!("  (run `dream shadow-cortex --source codex --json` for replay detail)");
}

/// Compact aggregate of `dream substrate-corr-audit`, sized for the
/// `dream weekly` Monday-morning one-liner. Mirrors the aggregation
/// done inline in `run_dream_substrate_corr_audit` but skips per-key
/// detail — full breakdown stays on the standalone CLI + `--json`.
#[derive(Debug, Clone)]
struct SubstrateCorrOneLiner {
    median_spearman: Option<f64>,
    bilateral_pairs: u64,
    qualifying_keys: u64,
    substrate_misses: u64,
    verdict: &'static str,
}

/// Compute the §4 P2 one-liner summary. Default snapshot path; `k=20`
/// and `min_cofires=3` per memo §4 P2. Returns `Ok(SubstrateCorrOneLiner)`
/// even on "no snapshot / no qualifying keys" — verdict text encodes the
/// no-signal state. Errors only on DB open / unexpected store failure.
async fn substrate_corr_weekly_one_liner(
    k: usize,
    min_cofires: u32,
) -> Result<SubstrateCorrOneLiner> {
    use ab_seed_bridge::snapshot::{self, SnapshotTier};
    use ab_store::{default_db_path, SqliteStore, StateStore};
    use std::collections::HashMap;

    let snap_path = snapshot::default_snapshot_path();
    let snap_row = match &snap_path {
        Some(p) if p.exists() => {
            let rows = snapshot::read_all(p)
                .with_context(|| format!("read substrate snapshot {}", p.display()))?;
            rows.into_iter()
                .rev()
                .find(|r| matches!(r.tier, SnapshotTier::Long))
        }
        _ => None,
    };

    let db_path = default_db_path();
    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;
    let qualifying = store
        .cofires_keys_with_min_degree(min_cofires)
        .await
        .map_err(|e| anyhow::anyhow!("cofires_keys_with_min_degree: {e}"))?;

    let mut spearmans: Vec<f64> = Vec::new();
    let mut substrate_misses = 0u64;
    let mut bilateral_pairs = 0u64;
    for (key, _deg) in &qualifying {
        let edges = store
            .memory_neighbors(key)
            .await
            .map_err(|e| anyhow::anyhow!("memory_neighbors({key}): {e}"))?;
        let mut cofires_pairs: Vec<(String, f64)> = edges
            .iter()
            .filter(|e| e.edge_type == "cofires")
            .map(|e| {
                let other = if e.from_key == *key {
                    e.to_key.clone()
                } else {
                    e.from_key.clone()
                };
                (other, e.weight)
            })
            .collect();
        cofires_pairs.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        let mut seen_co = std::collections::HashSet::new();
        cofires_pairs.retain(|(k, _)| seen_co.insert(k.clone()));

        let substrate_pairs: Vec<(String, f64)> = match snap_row.as_ref() {
            Some(row) => ab_seed_bridge::neighbors_from_snapshot(row, key, k)
                .into_iter()
                .map(|(k_text, s)| (k_text, s as f64))
                .collect(),
            None => Vec::new(),
        };
        if substrate_pairs.is_empty() {
            substrate_misses += 1;
        }

        let mut rank_co: HashMap<&str, f64> = HashMap::new();
        for (i, (k_text, _)) in cofires_pairs.iter().enumerate() {
            rank_co.insert(k_text.as_str(), (i + 1) as f64);
        }
        let mut rank_sub: HashMap<&str, f64> = HashMap::new();
        for (i, (k_text, _)) in substrate_pairs.iter().enumerate() {
            rank_sub.insert(k_text.as_str(), (i + 1) as f64);
        }
        let mut union: std::collections::BTreeSet<&str> = std::collections::BTreeSet::new();
        for (k_text, _) in &cofires_pairs {
            union.insert(k_text.as_str());
        }
        for (k_text, _) in &substrate_pairs {
            union.insert(k_text.as_str());
        }
        let n_union = union.len();
        let last_co = (cofires_pairs.len() + 1) as f64;
        let last_sub = (substrate_pairs.len() + 1) as f64;
        if n_union >= 3 {
            let mut sum_d_sq = 0.0_f64;
            for k_text in &union {
                let ra = *rank_co.get(*k_text).unwrap_or(&last_co);
                let rb = *rank_sub.get(*k_text).unwrap_or(&last_sub);
                sum_d_sq += (ra - rb).powi(2);
            }
            let n_f = n_union as f64;
            let denom = n_f * (n_f * n_f - 1.0);
            if denom > 0.0 {
                let rho = 1.0 - 6.0 * sum_d_sq / denom;
                spearmans.push(rho);
                bilateral_pairs += 1;
            }
        }
    }

    let median_spearman = if spearmans.is_empty() {
        None
    } else {
        let mut v = spearmans.clone();
        v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let mid = v.len() / 2;
        Some(if v.len() % 2 == 0 {
            (v[mid - 1] + v[mid]) / 2.0
        } else {
            v[mid]
        })
    };

    let verdict = match median_spearman {
        Some(m) if m >= 0.4 => "P2 PASS (≥0.4)",
        Some(_) => "P2 not yet PASS (<0.4)",
        None => "no bilateral pairs — insufficient overlap",
    };

    Ok(SubstrateCorrOneLiner {
        median_spearman,
        bilateral_pairs,
        qualifying_keys: qualifying.len() as u64,
        substrate_misses,
        verdict,
    })
}

// ─── §6.5 rule 4 — gap-audit ────────────────────────────────────────────
//
// CLI surface for the monthly gap-coverage audit. Source of truth =
// docs/MONTHLY-GAP-COVERAGE-AUDIT-YYYY-MM-DD.md + L4/L8 audit-layer memo
// memory_l4_l8_gap_audit_mapping_*. The 13-gap table is hardcoded against
// the latest published audit; future audits add a new constant
// `GAPS_AS_OF_YYYY_MM_DD` so git log preserves audit-state evolution.
// Design memo: docs/DESIGN-DREAM-GAP-AUDIT-2026-05-16.md.

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "lowercase")]
// Status vocabulary for the gap table — variants stay defined even when no
// current GapEntry uses them (e.g. Partial/Planned drained to Closed as gaps
// ship), so the lifecycle stays expressible without churning the enum.
#[allow(dead_code)]
enum GapStatus {
    Closed,
    Shelved,
    Partial,
    Planned,
    Untouched,
}

impl GapStatus {
    fn icon(self) -> &'static str {
        match self {
            Self::Closed => "✅",
            Self::Shelved => "🛑",
            Self::Partial => "⚠",
            Self::Planned => "⏳",
            Self::Untouched => "⚪",
        }
    }
}

#[derive(Debug, Clone, serde::Serialize)]
struct GapEntry {
    id: &'static str,
    layer: &'static str,
    status: GapStatus,
    text: &'static str,
    last_touch: &'static str,
    gate_opens: Option<&'static str>,
    notes: &'static str,
}

/// Snapshot from the 2026-05-16 monthly audit + L4/L8 audit-layer memo.
/// Update by adding a new constant + bumping `current_gap_baseline()`.
const GAPS_AS_OF_2026_05_16: &[GapEntry] = &[
    GapEntry {
        id: "A1",
        layer: "L5?",
        status: GapStatus::Untouched,
        text: "Forget what we worked on last week without explicit memory_save/search",
        last_touch: "—",
        gate_opens: None,
        notes: "no ship attempted; def working",
    },
    GapEntry {
        id: "A3",
        layer: "L5",
        status: GapStatus::Closed,
        text: "User corrected me ten times; new session makes same mistake",
        last_touch: "9383ca4 0f9ea7e a3af97a",
        gate_opens: Some("2026-06-14"),
        notes: "L5 v0 closed; L5-P1 30d window",
    },
    GapEntry {
        id: "B1",
        layer: "?",
        status: GapStatus::Untouched,
        text: "Lose track of multi-week project state (phase, open RFC, blocked-on-whom)",
        last_touch: "—",
        gate_opens: None,
        notes: "no ship attempted; def working",
    },
    GapEntry {
        id: "B2",
        layer: "L5",
        status: GapStatus::Closed,
        text: "Judgment standards drift over months without me noticing",
        last_touch: "9383ca4 0f9ea7e a3af97a",
        gate_opens: Some("2026-06-14"),
        notes: "L5 v0 closed (same ships as A3); long-window gate",
    },
    GapEntry {
        id: "B3",
        layer: "?",
        status: GapStatus::Untouched,
        text: "Redo design work that was already settled — can't locate prior decision",
        last_touch: "—",
        gate_opens: None,
        notes: "no ship attempted; def working",
    },
    GapEntry {
        id: "C1",
        layer: "L6",
        status: GapStatus::Shelved,
        text: "Hallucination self-awareness — am I making things up?",
        last_touch: "f9551b6 7fa9ff5 0ced487",
        gate_opens: None,
        notes: "3/3 FALSIFIED; §6.5 rule 3 shelve; raw observability mode",
    },
    GapEntry {
        id: "C2",
        layer: "L6",
        status: GapStatus::Closed,
        text: "Which tool results did I actually attend to vs ignore?",
        last_touch: "6ad5959",
        gate_opens: None,
        notes: "tool_call_attention_report MCP probe shipped (6ad5959 'L6 v0 fully closed'); observability-only per L6 charter (proposals never auto-applied)",
    },
    GapEntry {
        id: "C3",
        layer: "L6",
        status: GapStatus::Closed,
        text: "Fatigue / context-pressure tracking — am I saturated?",
        last_touch: "38517f1 2c6e76b",
        gate_opens: None,
        notes: "context_pressure_estimate MCP probe shipped (38517f1; honest 1M-window override 2c6e76b); observability-only per L6 charter",
    },
    GapEntry {
        id: "D1",
        layer: "L8",
        status: GapStatus::Closed,
        text: "Don't reliably know what sibling sessions are doing in parallel",
        last_touch: "0fac0f4 2b2e47b 8666119 3f71212 484e376",
        gate_opens: None,
        notes: "Closed via L8 C3 self-check set (audit-layer mapping)",
    },
    GapEntry {
        id: "D2",
        layer: "L8",
        status: GapStatus::Closed,
        text: "Decisions made by one session don't propagate without explicit forum post",
        last_touch: "484e376 316193e",
        gate_opens: None,
        notes: "D2-G1 closed — durable cross-machine forum+memory git-sync wired into `agent-bridge sync` (sync.rs forum_export/forum_import + memory export/import); verified live 2026-06-03: mac + aio2 sync.logs converge (forum ~2259 posts, conflict_copies=0). The old `17-post gap; peer-query workaround` note predated forum sync landing in durable sync (2026-05-16 f5400b2); peer-query now only serves real-time reads before the next 15-min sync.",
    },
    GapEntry {
        id: "D3",
        layer: "L8",
        status: GapStatus::Closed,
        text: "Concurrent edits collide — no coordination protocol",
        last_touch: "0fac0f4 8666119 3f71212 484e376",
        gate_opens: None,
        notes: "Closed via L8 C3 S2-S6 self-checks",
    },
    GapEntry {
        id: "E1",
        layer: "L7",
        status: GapStatus::Closed,
        text: "Lessons-learned don't update behavior",
        last_touch: "a7756bf e1911ad 35f34c5",
        gate_opens: Some("2026-06-15"),
        notes: "L7 v0 closed; L7-P1 30d window",
    },
    GapEntry {
        id: "E2",
        layer: "L7",
        status: GapStatus::Closed,
        text: "No \"getting better\" trajectory measurable across weeks",
        last_touch: "a7756bf e1911ad 35f34c5",
        gate_opens: Some("2026-07-11"),
        notes: "L7 v0 closed; L7-P2 8-week Spearman gate",
    },
];

fn current_gap_baseline() -> (&'static str, &'static [GapEntry]) {
    ("2026-05-16", GAPS_AS_OF_2026_05_16)
}

#[derive(Debug, Clone, Default, serde::Serialize)]
struct GapStatusCounts {
    closed: usize,
    shelved: usize,
    partial: usize,
    planned: usize,
    untouched: usize,
}

impl GapStatusCounts {
    fn from_entries(entries: &[GapEntry]) -> Self {
        let mut c = Self::default();
        for e in entries {
            match e.status {
                GapStatus::Closed => c.closed += 1,
                GapStatus::Shelved => c.shelved += 1,
                GapStatus::Partial => c.partial += 1,
                GapStatus::Planned => c.planned += 1,
                GapStatus::Untouched => c.untouched += 1,
            }
        }
        c
    }
}

#[derive(Debug, Clone, serde::Serialize)]
struct SectionalDelta {
    prefix: String,
    commit_count: usize,
    commits: Vec<String>,
}

#[derive(Debug, Clone, serde::Serialize)]
struct OutstandingGate {
    gap_id: &'static str,
    gate_label: String,
    opens_iso: &'static str,
    days_until: i64,
}

#[derive(Debug, Clone, serde::Serialize)]
struct GapAuditReport {
    generated_at_unix: u64,
    baseline_date: &'static str,
    since: String,
    counts: GapStatusCounts,
    gaps: Vec<GapEntry>,
    sectional_delta: Vec<SectionalDelta>,
    outstanding_gates: Vec<OutstandingGate>,
}

/// Days between an ISO `YYYY-MM-DD` date and `now`. Negative = past.
fn iso_days_until_now(iso: &str, now_unix: u64) -> Option<i64> {
    // Minimal ISO date parse — guards against bad input but doesn't
    // depend on chrono.
    let parts: Vec<&str> = iso.split('-').collect();
    if parts.len() != 3 {
        return None;
    }
    let y: i64 = parts[0].parse().ok()?;
    let m: i64 = parts[1].parse().ok()?;
    let d: i64 = parts[2].parse().ok()?;
    if !(1..=12).contains(&m) || !(1..=31).contains(&d) {
        return None;
    }
    // Days-from-civil-epoch (Howard Hinnant's algorithm).
    let (y, m) = if m <= 2 { (y - 1, m + 9) } else { (y, m - 3) };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = y - era * 400;
    let doy = (153 * m + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days_since_civil_epoch = era * 146097 + doe - 719468; // 1970-01-01
    let target_unix = days_since_civil_epoch * 86400;
    let now_days = (now_unix as i64) / 86400;
    Some(days_since_civil_epoch - now_days).map(|d| {
        // Recompute target days for cleaner reporting.
        let _ = target_unix;
        d
    })
}

/// Build the gap-audit report against the canonical baseline. Pure aside
/// from the `git log` subprocess (controlled args, no shell interp).
fn gap_audit_baseline_report(since: &str) -> std::result::Result<GapAuditReport, String> {
    let (baseline_date, entries) = current_gap_baseline();
    let now_unix = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let counts = GapStatusCounts::from_entries(entries);
    let gaps: Vec<GapEntry> = entries.to_vec();

    // Sectional commit delta — parse `git log --since=<x> --oneline`.
    let sectional_delta = git_log_sectional_delta(since)?;

    // Outstanding gates: any entry with gate_opens in the future.
    let mut outstanding: Vec<OutstandingGate> = Vec::new();
    for e in entries {
        if let Some(iso) = e.gate_opens {
            if let Some(days) = iso_days_until_now(iso, now_unix) {
                // Always include for visibility (negative => overdue).
                let label = match (e.id, iso) {
                    ("A3" | "B2", _) => format!("L5-P1 ({})", e.id),
                    ("E1", _) => "L7-P1".to_string(),
                    ("E2", _) => "L7-P2".to_string(),
                    (id, _) => format!("{id}-Gate"),
                };
                outstanding.push(OutstandingGate {
                    gap_id: e.id,
                    gate_label: label,
                    opens_iso: iso,
                    days_until: days,
                });
            }
        }
    }
    outstanding.sort_by_key(|g| g.days_until);

    Ok(GapAuditReport {
        generated_at_unix: now_unix,
        baseline_date,
        since: since.to_string(),
        counts,
        gaps,
        sectional_delta,
        outstanding_gates: outstanding,
    })
}

/// Run `git log --since=<x> --oneline --no-decorate` in the current
/// repo and group results by the conventional commit subject prefix
/// (`feat(...)`, `docs(...)`, `chore(...)`, etc.). Errors if `git`
/// isn't available or the cwd isn't a repo.
fn git_log_sectional_delta(since: &str) -> std::result::Result<Vec<SectionalDelta>, String> {
    use std::process::Command;
    let out = Command::new("git")
        .args(["log", "--no-decorate", "--oneline", "--since"])
        .arg(since)
        .output()
        .map_err(|e| format!("spawn git log: {e}"))?;
    if !out.status.success() {
        let err = String::from_utf8_lossy(&out.stderr);
        return Err(format!("git log non-zero: {}", err.trim()));
    }
    let stdout = String::from_utf8_lossy(&out.stdout);
    Ok(group_oneline_by_prefix(&stdout))
}

/// Group `git log --oneline` output by the `type(scope):` prefix.
/// Pure — testable in isolation.
fn group_oneline_by_prefix(oneline: &str) -> Vec<SectionalDelta> {
    use std::collections::BTreeMap;
    let mut buckets: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for line in oneline.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        // <sha> <subject>
        let Some((_sha, subject)) = line.split_once(' ') else {
            continue;
        };
        // Extract `type(scope):` or `type:` prefix; fallback "uncategorized".
        let prefix =
            extract_conventional_prefix(subject).unwrap_or_else(|| "uncategorized".to_string());
        buckets.entry(prefix).or_default().push(subject.to_string());
    }
    buckets
        .into_iter()
        .map(|(prefix, commits)| SectionalDelta {
            prefix,
            commit_count: commits.len(),
            commits,
        })
        .collect()
}

/// Extract the `type(scope):` (or `type:`) prefix of a conventional
/// commit subject. Returns `None` for free-form subjects.
fn extract_conventional_prefix(subject: &str) -> Option<String> {
    let colon = subject.find(':')?;
    let head = &subject[..colon];
    // Reject if `head` has spaces (no convention prefix).
    if head.contains(' ') {
        return None;
    }
    Some(format!("{head}:"))
}

async fn run_dream_gap_audit(since: &str, as_json: bool) -> Result<()> {
    let report = gap_audit_baseline_report(since)
        .map_err(|e| anyhow::anyhow!("gap_audit_baseline_report: {e}"))?;

    if as_json {
        let s = serde_json::to_string_pretty(&report)
            .map_err(|e| anyhow::anyhow!("serde gap-audit json: {e}"))?;
        println!("{s}");
        return Ok(());
    }

    println!("════════════════════════════════════════════════════════════");
    println!("  dream gap-audit — §6.5 rule 4 monthly cadence");
    println!(
        "  baseline: {} · since: {}",
        report.baseline_date, report.since
    );
    println!("════════════════════════════════════════════════════════════");
    println!();
    println!("13-gap status (from monthly audit baseline):");
    println!();
    println!("| Gap | Layer | Status | Notes |");
    println!("|---|---|---|---|");
    for g in &report.gaps {
        println!(
            "| {} | {} | {} {:<9} | {} |",
            g.id,
            g.layer,
            g.status.icon(),
            format!("{:?}", g.status).to_lowercase(),
            g.notes,
        );
    }
    println!();
    println!(
        "Status counts: {} closed / {} shelved / {} partial / {} planned / {} untouched (total {})",
        report.counts.closed,
        report.counts.shelved,
        report.counts.partial,
        report.counts.planned,
        report.counts.untouched,
        report.gaps.len(),
    );
    println!();
    println!("Sectional commit delta since {}:", report.since);
    if report.sectional_delta.is_empty() {
        println!("  (no commits in window)");
    } else {
        for s in &report.sectional_delta {
            if s.commit_count == 0 {
                continue;
            }
            println!("  {:<18} {:>3} commits", s.prefix, s.commit_count);
        }
        let total: usize = report.sectional_delta.iter().map(|s| s.commit_count).sum();
        println!("  total: {total} in-scope ships");
    }
    println!();
    println!("Outstanding falsifiability gates:");
    if report.outstanding_gates.is_empty() {
        println!("  (no future-dated gates registered)");
    } else {
        for g in &report.outstanding_gates {
            let when = if g.days_until >= 0 {
                format!("in {} days", g.days_until)
            } else {
                format!("{} days AGO (overdue)", -g.days_until)
            };
            println!("  {:<12} {:<12} {when}", g.gate_label, g.opens_iso);
        }
    }
    println!();
    println!("next monthly audit: 2026-06-15");

    Ok(())
}

/// Codebase call-graph audit — sibling to `dream promote --html`. Loads
/// `codebase_call_stats(root, top_n)` from the store and renders a
/// terminal summary plus (optionally) a self-contained HTML report.
async fn run_dream_codebase_report(
    root: Option<&std::path::Path>,
    top_n: u32,
    html_path: Option<&std::path::Path>,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};

    let cwd = std::env::current_dir().map_err(|e| anyhow::anyhow!("current_dir: {e}"))?;
    let root_path = root.map(|p| p.to_path_buf()).unwrap_or(cwd);
    let root_canonical = std::fs::canonicalize(&root_path)
        .unwrap_or(root_path.clone())
        .to_string_lossy()
        .to_string();

    let db_path = default_db_path();
    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;

    let stats = store
        .codebase_call_stats(&root_canonical, top_n)
        .await
        .map_err(|e| anyhow::anyhow!("codebase_call_stats: {e}"))?;

    if as_json {
        let s = serde_json::to_string_pretty(&stats)
            .map_err(|e| anyhow::anyhow!("serialize stats: {e}"))?;
        println!("{s}");
    } else {
        println!("# Codebase call-graph audit");
        println!("root: {}", stats.root_path);
        println!("DB:   {}", db_path.display());
        println!();
        println!(
            "{} total calls across {} files",
            stats.total_calls, stats.distinct_caller_files
        );
        if stats.total_calls == 0 {
            println!();
            println!(
                "(no calls in `codebase_calls` for this root — run \
                 `agent-bridge codebase index` first, or check that the \
                 root path matches the indexed one)"
            );
        } else {
            println!();
            println!("per-language:");
            for l in &stats.per_language {
                println!(
                    "  {:<8} {:>6} calls   {:>4} files",
                    l.language, l.call_count, l.distinct_files
                );
            }

            if !stats.hot_callees.is_empty() {
                println!();
                println!("top {} hottest callees:", stats.hot_callees.len());
                for h in &stats.hot_callees {
                    println!(
                        "  {:>5} fires  {:>3} callers  {:<24}  [{}]",
                        h.call_count,
                        h.distinct_callers,
                        truncate_chars(&h.callee, 60),
                        h.languages.join(",")
                    );
                }
            }

            if !stats.hot_callers.is_empty() {
                println!();
                println!("top {} fan-out callers:", stats.hot_callers.len());
                for c in &stats.hot_callers {
                    println!(
                        "  fan={:>3} ({:>4} calls)  {:<32}  [{}]",
                        c.distinct_callees,
                        c.total_calls,
                        truncate_chars(&c.caller, 50),
                        c.language
                    );
                }
            }

            if !stats.fan_out_files.is_empty() {
                println!();
                println!("top {} fan-out files:", stats.fan_out_files.len());
                for f in &stats.fan_out_files {
                    println!(
                        "  fan={:>3} ({:>4} calls)  {}",
                        f.distinct_callees, f.total_calls, f.file_path
                    );
                }
            }

            if !stats.orphan_functions.is_empty() {
                let (real, likely_fp): (Vec<_>, Vec<_>) =
                    stats.orphan_functions.iter().partition(|o| !o.likely_fp);
                println!();
                println!(
                    "orphan function candidates — {} high-confidence + {} likely false positives:",
                    real.len(),
                    likely_fp.len()
                );
                if real.is_empty() {
                    println!("  (none — every orphan candidate was tagged as a likely FP)");
                } else {
                    for o in &real {
                        println!(
                            "  {:<10} {:<32}  {}:{}",
                            o.kind,
                            truncate_chars(&o.name, 40),
                            o.file_path,
                            o.line
                        );
                    }
                }
                if !likely_fp.is_empty() {
                    println!();
                    println!(
                        "  likely false positives (test files / main entry / pytest convention):"
                    );
                    for o in &likely_fp {
                        println!(
                            "    {:<10} {:<28}  [{}]  {}:{}",
                            o.kind,
                            truncate_chars(&o.name, 36),
                            o.likely_fp_reason,
                            o.file_path,
                            o.line
                        );
                    }
                }
            }
        }
    }

    if let Some(p) = html_path {
        let html = render_codebase_report_html(&stats, &db_path);
        std::fs::write(p, html).map_err(|e| anyhow::anyhow!("write html report to {p:?}: {e}"))?;
        println!();
        println!("html report: {}", p.display());
    }
    Ok(())
}

fn truncate_chars(s: &str, n: usize) -> String {
    if s.chars().count() <= n {
        s.to_string()
    } else {
        let prefix: String = s.chars().take(n.saturating_sub(1)).collect();
        format!("{prefix}…")
    }
}

/// P-ε — Substrate-Readiness Audit CLI. Calls the same trait method as
/// the `memory_substrate_audit` MCP tool; pretty text in terminal mode,
/// JSON via `--json`. Pure read.
async fn run_dream_substrate_audit(
    window_days: u32,
    as_json: bool,
    exclude_kinds: Vec<String>,
) -> Result<()> {
    use ab_store::{default_db_path, SqliteStore, StateStore};
    let db_path = default_db_path();
    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;
    let window_secs = (window_days as u64) * 86_400;
    let mut r = store
        .memory_substrate_audit(window_secs)
        .await
        .map_err(|e| anyhow::anyhow!("memory_substrate_audit: {e}"))?;

    // Method A (#204) — when --exclude-kinds is set, recompute M7 on
    // the filtered subset and overlay it onto the report. Other metrics
    // stay on the full active set; only signal-fidelity (the L5 P3
    // confound target) gets the filter. Report.excluded_kinds populated
    // so downstream readers tell apart dual-report runs without parsing
    // file names.
    if !exclude_kinds.is_empty() {
        let filtered = store
            .signal_fidelity_stats_excluding(0, &exclude_kinds)
            .await
            .map_err(|e| anyhow::anyhow!("signal_fidelity_stats_excluding: {e}"))?;
        let verdict = if filtered.spearman_r_touched.is_nan() {
            "n/a".to_string()
        } else if filtered.spearman_r_touched.abs() < 0.2 {
            "noise".to_string()
        } else if filtered.spearman_r_touched.abs() < 0.4 {
            "weak".to_string()
        } else if filtered.spearman_r_touched.abs() < 0.6 {
            "moderate".to_string()
        } else {
            "strong".to_string()
        };
        r.m7_signal_fidelity = ab_store::SignalFidelityCompact {
            r_all: filtered.spearman_r,
            r_touched: filtered.spearman_r_touched,
            n_touched: filtered.n_touched,
            verdict,
        };
        r.excluded_kinds = exclude_kinds.clone();
    }

    if as_json {
        let s = serde_json::to_string_pretty(&r)
            .map_err(|e| anyhow::anyhow!("serialize report: {e}"))?;
        println!("{s}");
        return Ok(());
    }

    println!("# Substrate-Readiness Audit (P-ε)");
    println!("DB: {}", db_path.display());
    println!("window: {} days", window_days);
    println!();

    // M1
    println!("M1 components (cofires + co_referenced):");
    println!(
        "  components: {}  largest_size: {}  total_clustered: {}",
        r.m1_components.components,
        r.m1_components.largest_size,
        r.m1_components.total_clustered_nodes
    );
    let m1_verdict = if r.m1_components.components == 0 {
        "(empty)"
    } else if r.m1_components.components == 1 {
        "⚠ hairball regime"
    } else if r.m1_components.components < 3 {
        "partially modular"
    } else {
        "✓ modular"
    };
    println!("  verdict: {m1_verdict}");

    // M2
    println!();
    println!("M2 edges by type:");
    let mut pairs: Vec<(&String, &u64)> = r.m2_edges.per_type.iter().collect();
    pairs.sort_by(|a, b| b.1.cmp(a.1));
    for (t, n) in pairs {
        println!("  {:<14} {:>5}", t, n);
    }
    println!(
        "  total: {} · density/active: {:.3}",
        r.m2_edges.total, r.m2_edges.density_per_active
    );

    // M3
    println!();
    println!("M3 coactivation:");
    println!(
        "  total_pairs: {}  recent_active({}d): {}  avg_count: {:.2}  max_count: {}",
        r.m3_coactivation.total_pairs,
        window_days,
        r.m3_coactivation.recent_active,
        r.m3_coactivation.avg_count,
        r.m3_coactivation.max_count,
    );
    println!(
        "  est_daily_new_pairs: {:.2}",
        r.m3_coactivation.est_daily_new_pairs
    );

    // M4
    println!();
    println!("M4 retire-state balance:");
    println!(
        "  active: {}  archived: {}  superseded: {}  tombstoned: {}",
        r.m4_retire.active, r.m4_retire.archived, r.m4_retire.superseded, r.m4_retire.tombstoned,
    );
    println!(
        "  archived_fraction: {:.3}  delta_7d (approx={}): a={:+} archived={:+} t={:+} s={:+}",
        r.m4_retire.archived_fraction,
        r.m4_retire.delta.is_approximate,
        r.m4_retire.delta.active,
        r.m4_retire.delta.archived,
        r.m4_retire.delta.tombstoned,
        r.m4_retire.delta.superseded,
    );

    // M5
    println!();
    println!("M5 edge coverage of active:");
    println!(
        "  active_with_l2_edge: {} / {} · fraction: {:.3}",
        r.m5_edge_coverage.active_with_l2_edge,
        r.m5_edge_coverage.active_total,
        r.m5_edge_coverage.fraction,
    );

    // M6
    println!();
    println!("M6 embedding backend:");
    println!(
        "  onnx: {}  hash: {}  unknown: {}  total: {}  stale_fraction: {:.3}",
        r.m6_embedding.onnx,
        r.m6_embedding.hash,
        r.m6_embedding.unknown,
        r.m6_embedding.total,
        r.m6_embedding.stale_fraction,
    );

    // M7
    println!();
    if r.excluded_kinds.is_empty() {
        println!("M7 signal fidelity:");
    } else {
        println!(
            "M7 signal fidelity (Method A — excluded kinds: {}):",
            r.excluded_kinds.join(", ")
        );
    }
    println!(
        "  r_all: {:.3}  r_touched: {:.3} (n={})  verdict: {}",
        r.m7_signal_fidelity.r_all,
        r.m7_signal_fidelity.r_touched,
        r.m7_signal_fidelity.n_touched,
        r.m7_signal_fidelity.verdict,
    );

    // M8
    println!();
    println!("M8 query health ({}d window):", window_days);
    println!(
        "  total: {}  hit_rate: {:.3}  p50: {}µs  p95: {}µs",
        r.m8_query.total_queries,
        r.m8_query.hit_rate,
        r.m8_query.p50_duration_us,
        r.m8_query.p95_duration_us,
    );
    println!(
        "  avg_top_hit_age: {:.2}d",
        r.m8_query.avg_top_hit_age_secs / 86_400.0
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
            if weight >= 0.8 {
                "chip-strong"
            } else if weight >= 0.65 {
                "chip-mid"
            } else {
                "chip-weak"
            }
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
        let safe =
            b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b'.' | b'~' | b':' | b'/');
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

// ─── L7 P2 — AGENT.md drift detector ────────────────────────────────

/// One drift candidate emitted by [`run_dream_agent_md_drift`].
#[derive(Debug, serde::Serialize)]
struct AgentMdDriftProposal {
    lesson_key: String,
    coverage_ratio: f64,
    snippet: String,
    proposal_key: String,
    skipped: bool,
}

#[derive(Debug, serde::Serialize)]
struct AgentMdDriftReport {
    agent_md_path: String,
    agent_md_bytes: usize,
    window_days: u32,
    lessons_scanned: usize,
    covered: usize,
    proposed: usize,
    proposals: Vec<AgentMdDriftProposal>,
    dry_run: bool,
}

/// L7 P2 — coverage threshold below which a lesson is considered NOT
/// represented in AGENT.md. 0.30 means: if fewer than 30% of the
/// lesson's distinctive tokens appear in AGENT.md, propose an update.
const AGENT_MD_DRIFT_COVERAGE_THRESHOLD: f64 = 0.30;

/// Tokenise text into lowercase alphanumeric tokens of length >= 4.
/// Pure, no allocation beyond the returned set.
fn drift_tokens(text: &str) -> std::collections::HashSet<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|t| t.chars().count() >= 4)
        .map(|t| t.to_lowercase())
        .collect()
}

/// Fraction of `lesson_tokens` that also appear in `preamble_tokens`.
/// Returns 0.0 when `lesson_tokens` is empty (no signal to compare).
fn drift_coverage_ratio(
    lesson_tokens: &std::collections::HashSet<String>,
    preamble_tokens: &std::collections::HashSet<String>,
) -> f64 {
    if lesson_tokens.is_empty() {
        return 0.0;
    }
    let covered = lesson_tokens
        .iter()
        .filter(|t| preamble_tokens.contains(*t))
        .count();
    covered as f64 / lesson_tokens.len() as f64
}

async fn run_dream_agent_md_drift(
    window_days: u32,
    dry_run: bool,
    agent_md_path_override: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    use ab_store::{default_db_path, MemoryListSort, MemoryRecord, SqliteStore, StateStore};

    let agent_md_path =
        agent_md_path_override.unwrap_or_else(ab_bridge::mcp_tools::agent_profile_path);
    let agent_md_content = std::fs::read_to_string(&agent_md_path).unwrap_or_default();
    let agent_md_bytes = agent_md_content.len();
    let preamble_tokens = drift_tokens(&agent_md_content);

    let db_path = default_db_path();
    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;

    let now_secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let cutoff = now_secs - (window_days as i64) * 86_400;

    let all = store
        .list_memories(Some("lesson"), MemoryListSort::Newest, 500)
        .await
        .map_err(|e| anyhow::anyhow!("list_memories: {e}"))?;
    let recent: Vec<MemoryRecord> = all
        .into_iter()
        .filter(|r| r.status == "active" && r.created_at >= cutoff)
        .collect();

    let mut proposals: Vec<AgentMdDriftProposal> = Vec::new();
    let mut covered = 0usize;
    let mut proposed = 0usize;

    for lesson in &recent {
        let lesson_tokens = drift_tokens(&lesson.content);
        let ratio = drift_coverage_ratio(&lesson_tokens, &preamble_tokens);
        if ratio >= AGENT_MD_DRIFT_COVERAGE_THRESHOLD {
            covered += 1;
            continue;
        }
        // Stable derived key — same lesson → same proposal row (idempotent
        // re-run = memory_save replaces). Stamp the rounded coverage so a
        // newly-edited lesson body re-triggers without spamming the bucket.
        let coverage_bucket = (ratio * 100.0).round() as i64;
        let proposal_key = format!(
            "l7_proposal:{}:cov{}",
            ab_bridge::mcp_tools::sanitise_target_for_key(&lesson.key),
            coverage_bucket
        );
        let snippet: String = lesson.content.chars().take(140).collect();

        let written = if dry_run {
            true // pretend; nothing actually persisted
        } else {
            let stored_content = format!(
                "AGENT.md drift candidate (coverage {:.0}%): lesson `{}` is not yet \
                 substantially represented in AGENT.md. Review and integrate by hand if \
                 the behavior should become durable.\n\nLesson snippet:\n{}\n\n\
                 Source key: {}",
                ratio * 100.0,
                lesson.key,
                snippet,
                lesson.key,
            );
            let mem = ab_store::MemoryRecord {
                key: proposal_key.clone(),
                kind: "l7_proposed_update".into(),
                content: stored_content,
                tags: vec!["l7".into(), "drift_proposal".into(), "needs_review".into()],
                related_keys: vec![lesson.key.clone()],
                scope: None,
                created_at: 0,
                updated_at: 0,
                last_accessed_at: 0,
                access_count: 0,
                importance: 0.7,
                status: "active".into(),
                trigger_pattern: None,
                superseded_by: None,
            };
            store.memory_save(&mem).await.is_ok()
        };
        if !written {
            continue;
        }
        proposed += 1;
        proposals.push(AgentMdDriftProposal {
            lesson_key: lesson.key.clone(),
            coverage_ratio: ratio,
            snippet,
            proposal_key,
            skipped: false,
        });
    }

    let report = AgentMdDriftReport {
        agent_md_path: agent_md_path.display().to_string(),
        agent_md_bytes,
        window_days,
        lessons_scanned: recent.len(),
        covered,
        proposed,
        proposals,
        dry_run,
    };

    if as_json {
        let s = serde_json::to_string_pretty(&report)
            .map_err(|e| anyhow::anyhow!("serialize report: {e}"))?;
        println!("{s}");
        return Ok(());
    }

    println!("# AGENT.md Drift Report (L7 P2)");
    println!(
        "AGENT.md: {} ({} bytes)",
        report.agent_md_path, report.agent_md_bytes
    );
    println!("window: {} days", report.window_days);
    println!("lessons scanned: {}", report.lessons_scanned);
    println!(
        "  covered (≥{:.0}% token overlap): {}",
        AGENT_MD_DRIFT_COVERAGE_THRESHOLD * 100.0,
        report.covered
    );
    println!(
        "  proposed updates: {}{}",
        report.proposed,
        if report.dry_run { " (DRY RUN)" } else { "" }
    );
    if report.proposals.is_empty() {
        println!();
        println!("(no drift detected in window)");
    } else {
        println!();
        for p in &report.proposals {
            println!(
                "  - {}  coverage={:.0}%  →  {}",
                p.lesson_key,
                p.coverage_ratio * 100.0,
                p.proposal_key
            );
            println!("      {}", p.snippet);
        }
    }
    println!();
    println!(
        "NOTE: proposals are surfaced via kind=l7_proposed_update memories. \
         AGENT.md is NEVER auto-edited; review proposals and integrate by hand \
         via session_finalize(agent_profile=...)."
    );
    Ok(())
}

// ─── L7 P3 — Weekly skill-rating retro ──────────────────────────────

#[derive(Debug, serde::Serialize)]
struct SkillRetroLessonRow {
    key: String,
    created_at: i64,
    last_accessed_at: i64,
    access_count: u64,
    importance: f64,
    consulted: bool,
}

#[derive(Debug, serde::Serialize)]
struct SkillRetroReport {
    window_days: u32,
    cutoff_unix: i64,
    now_unix: i64,
    lessons_total: usize,
    lessons_consulted: usize,
    consulted_ratio: f64,
    mean_access_count: f64,
    rows: Vec<SkillRetroLessonRow>,
}

/// Pure aggregator for [`run_dream_skill_retro`]. `now` and `cutoff`
/// are caller-injected for deterministic testing.
fn aggregate_skill_retro(
    lessons: Vec<ab_store::MemoryRecord>,
    window_days: u32,
    now: i64,
    cutoff: i64,
) -> SkillRetroReport {
    let mut rows: Vec<SkillRetroLessonRow> = lessons
        .into_iter()
        .map(|m| SkillRetroLessonRow {
            consulted: m.access_count > 0,
            key: m.key,
            created_at: m.created_at,
            last_accessed_at: m.last_accessed_at,
            access_count: m.access_count,
            importance: m.importance,
        })
        .collect();
    // Order by access_count DESC (most-consulted first) for readable
    // text output; JSON consumers can re-sort.
    rows.sort_by(|a, b| b.access_count.cmp(&a.access_count));
    let total = rows.len();
    let consulted = rows.iter().filter(|r| r.consulted).count();
    let mean_access = if total == 0 {
        0.0
    } else {
        rows.iter().map(|r| r.access_count as f64).sum::<f64>() / total as f64
    };
    let consulted_ratio = if total == 0 {
        0.0
    } else {
        consulted as f64 / total as f64
    };
    SkillRetroReport {
        window_days,
        cutoff_unix: cutoff,
        now_unix: now,
        lessons_total: total,
        lessons_consulted: consulted,
        consulted_ratio,
        mean_access_count: mean_access,
        rows,
    }
}

async fn run_dream_skill_retro(days: u32, as_json: bool) -> Result<()> {
    use ab_store::{default_db_path, MemoryListSort, MemoryRecord, SqliteStore, StateStore};

    let db_path = default_db_path();
    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;

    let now_secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let cutoff = now_secs - (days as i64) * 86_400;

    let all = store
        .list_memories(Some("lesson"), MemoryListSort::Newest, 500)
        .await
        .map_err(|e| anyhow::anyhow!("list_memories: {e}"))?;
    let lessons: Vec<MemoryRecord> = all
        .into_iter()
        .filter(|r| r.status == "active" && r.created_at >= cutoff)
        .collect();

    let report = aggregate_skill_retro(lessons, days, now_secs, cutoff);

    if as_json {
        let s = serde_json::to_string_pretty(&report)
            .map_err(|e| anyhow::anyhow!("serialize report: {e}"))?;
        println!("{s}");
        return Ok(());
    }

    println!("# Skill-Rating Retro (L7 P3)");
    println!(
        "window: {} days  cutoff_unix={}  now_unix={}",
        report.window_days, report.cutoff_unix, report.now_unix
    );
    println!("lessons in window: {}", report.lessons_total);
    println!(
        "  consulted post-creation: {} ({:.0}%)",
        report.lessons_consulted,
        report.consulted_ratio * 100.0
    );
    println!("  mean access_count: {:.2}", report.mean_access_count);
    if report.rows.is_empty() {
        println!();
        println!("(no lessons captured in window)");
    } else {
        println!();
        println!("Per-lesson (sorted by access_count DESC):");
        for row in &report.rows {
            let badge = if row.consulted { "✓" } else { "·" };
            println!(
                "  {} {} access={} imp={:.2} created_at={}",
                badge, row.key, row.access_count, row.importance, row.created_at
            );
        }
    }
    println!();
    println!(
        "L7-P2 falsifiability: this snapshot is one weekly datapoint. \
         Cross-week Spearman trend is computed by diffing JSON outputs \
         over 8+ weeks; ship the JSON form via:"
    );
    println!(
        "  agent-bridge dream skill-retro --json | tee \\\n    \
         ~/.cache/agent-bridge/baselines/skill-retro-$(date -I).json"
    );
    Ok(())
}

/// C2 dispatch wrapper. Translates RescueError → exit code per §3.3
/// spec: 0 = own snapshot, 1 = attached, anything else = hard fail.
async fn run_rescue_snapshot(
    canonical: bool,
    ttl_secs: u64,
    pid_override: Option<u32>,
    as_json: bool,
) -> Result<()> {
    if !canonical {
        anyhow::bail!(
            "rescue-snapshot v0 requires --canonical (only FD-based mode is implemented)"
        );
    }

    let daemon_pid = match pid_override.or_else(ab_bridge::rescue::find_daemon_pid) {
        Some(p) => p,
        None => {
            anyhow::bail!(
                "no agent-bridge daemon found (scan /proc for `agent-bridge.real daemon`); \
                 pass --pid <PID> to override"
            );
        }
    };

    match ab_bridge::rescue::rescue_snapshot(daemon_pid, ttl_secs) {
        Ok(report) => {
            if as_json {
                let s = serde_json::to_string_pretty(&report)
                    .map_err(|e| anyhow::anyhow!("serialize report: {e}"))?;
                println!("{s}");
            } else {
                println!("# C2 Rescue Snapshot");
                println!("status         : {}", report.status);
                println!("daemon pid     : {}", report.daemon_pid);
                println!("recovery dir   : {}", report.recovery_dir.display());
                println!("lock file      : {}", report.lock_path.display());
                println!("combined sha256: {}", report.combined_sha256);
                println!();
                println!("Copied artifacts:");
                for c in &report.copied {
                    println!(
                        "  fd={:>3} {:>11} bytes  sha256={}  →  {}",
                        c.fd,
                        c.bytes,
                        c.sha256,
                        c.dest_path.display()
                    );
                    println!("      source: {}", c.source_readlink);
                }
            }
            Ok(())
        }
        Err(ab_bridge::rescue::RescueError::Attached(existing)) => {
            if as_json {
                println!(
                    "{{\"status\":\"attached\",\"existing_artifact\":\"{}\"}}",
                    existing.display()
                );
            } else {
                println!(
                    "Another rescue in progress; attaching to existing snapshot at {}",
                    existing.display()
                );
            }
            std::process::exit(1);
        }
        Err(e) => Err(anyhow::anyhow!("rescue-snapshot failed: {e}")),
    }
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

    // ── Phase 3 (C): summarize_snapshot_rows + human_bytes ──────────────

    use ab_seed_bridge::{SnapshotRow, SnapshotTier};
    use std::path::Path;

    fn make_row(step: i64, ts: i64, tier: SnapshotTier) -> SnapshotRow {
        SnapshotRow {
            step,
            cycle_ts: ts,
            tier,
            n_alive: 2,
            in_strengths: vec![0.1, 0.2],
            last_perceived_key: vec!["a".into(), "b".into()],
            last_perceived_ts: vec![ts, ts],
            trailing_surprise_mean_short: 0.5,
            trailing_surprise_mean_long: 0.5,
            connection_logits: if matches!(tier, SnapshotTier::Long) {
                vec![0.0, 0.0]
            } else {
                Vec::new()
            },
        }
    }

    #[test]
    fn summarize_snapshot_rows_empty_returns_zero_counts() {
        let p = Path::new("/tmp/none.parquet");
        let sum = summarize_snapshot_rows(p, Some(0), &[]);
        assert_eq!(sum.total_rows, 0);
        assert_eq!(sum.hot_rows, 0);
        assert_eq!(sum.long_rows, 0);
        assert!(sum.latest_hot.is_none());
        assert!(sum.latest_long.is_none());
        assert_eq!(sum.path, "/tmp/none.parquet");
    }

    #[test]
    fn summarize_snapshot_rows_mixed_counts_and_latest_per_tier() {
        // 5 rows interleaved hot/long. Latest hot at step=80; latest long at step=100.
        let p = Path::new("/tmp/x.parquet");
        let rows = vec![
            make_row(20, 1000, SnapshotTier::Hot),
            make_row(40, 2000, SnapshotTier::Hot),
            make_row(60, 3000, SnapshotTier::Hot),
            make_row(80, 4000, SnapshotTier::Hot),
            make_row(100, 5000, SnapshotTier::Long),
        ];
        let sum = summarize_snapshot_rows(p, Some(12345), &rows);
        assert_eq!(sum.total_rows, 5);
        assert_eq!(sum.hot_rows, 4);
        assert_eq!(sum.long_rows, 1);
        assert_eq!(sum.file_bytes, Some(12345));
        let latest_hot = sum.latest_hot.expect("latest hot");
        assert_eq!(latest_hot.step, 80);
        assert_eq!(latest_hot.cycle_ts, 4000);
        assert_eq!(latest_hot.fingerprint.len(), 64); // sha256 hex
        let latest_long = sum.latest_long.expect("latest long");
        assert_eq!(latest_long.step, 100);
        assert_eq!(latest_long.cycle_ts, 5000);
        assert_eq!(latest_long.fingerprint.len(), 64);
    }

    #[test]
    fn summarize_snapshot_rows_picks_last_per_tier_not_first() {
        // Two Long rows; latest_long must be the later one (rev iteration).
        let p = Path::new("/tmp/y.parquet");
        let rows = vec![
            make_row(100, 5000, SnapshotTier::Long),
            make_row(200, 6000, SnapshotTier::Long),
        ];
        let sum = summarize_snapshot_rows(p, None, &rows);
        assert_eq!(sum.long_rows, 2);
        let latest = sum.latest_long.expect("latest");
        assert_eq!(latest.step, 200);
    }

    #[test]
    fn human_bytes_renders_units_correctly() {
        assert_eq!(human_bytes(None), "(unknown)");
        assert_eq!(human_bytes(Some(0)), "0 B");
        assert_eq!(human_bytes(Some(512)), "512 B");
        assert_eq!(human_bytes(Some(1024)), "1.0 KiB");
        assert_eq!(human_bytes(Some(2048)), "2.0 KiB");
        assert_eq!(human_bytes(Some(1024 * 1024)), "1.0 MiB");
        assert_eq!(human_bytes(Some(3 * 1024 * 1024 * 1024)), "3.00 GiB");
    }

    // ── Phase 3 (B): parse_event_line unit tests ─────────────────────────

    #[test]
    fn parse_event_line_happy_path_returns_text() {
        let got = parse_event_line(r#"{"text":"hello world"}"#);
        assert_eq!(got, Some(("hello world".to_string(), None)));
    }

    #[test]
    fn parse_event_line_with_ts_and_kind_ignores_extras() {
        let got = parse_event_line(r#"{"text":"foo","ts":1700000000,"kind":"save"}"#);
        assert_eq!(got, Some(("foo".to_string(), None)));
    }

    #[test]
    fn parse_event_line_blank_returns_none() {
        assert!(parse_event_line("").is_none());
        assert!(parse_event_line("   \t  ").is_none());
    }

    #[test]
    fn parse_event_line_malformed_returns_none() {
        // Garbage JSON, missing text field, text=null, text="" all → None.
        assert!(parse_event_line("not json").is_none());
        assert!(parse_event_line(r#"{"ts":1}"#).is_none());
        assert!(parse_event_line(r#"{"text":null}"#).is_none());
        assert!(parse_event_line(r#"{"text":""}"#).is_none());
        // text not a string
        assert!(parse_event_line(r#"{"text":42}"#).is_none());
    }

    // P-γ: optional `key` field carries perception identifier.
    #[test]
    fn parse_event_line_with_key_returns_text_and_key() {
        let got = parse_event_line(r#"{"text":"content body","key":"memory_key_42"}"#);
        assert_eq!(
            got,
            Some((
                "content body".to_string(),
                Some("memory_key_42".to_string())
            ))
        );
    }

    #[test]
    fn parse_event_line_empty_key_falls_back_to_none() {
        // Empty key string is treated as absent so caller defaults to text.
        let got = parse_event_line(r#"{"text":"hello","key":""}"#);
        assert_eq!(got, Some(("hello".to_string(), None)));
    }

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

    // ── L7 P2 — AGENT.md drift helpers (pure) ──────────────────────────

    #[test]
    fn drift_tokens_keeps_alnum_words_of_length_4_or_more() {
        let s = "foo, bar! Buckhannon a be tail42 dot.path snake_case";
        let toks = drift_tokens(s);
        // Keeps: buckhannon, tail42, snake, case, path (≥4 chars,
        // alphanumeric, lowercased). Drops: foo, bar (3 chars), a/be
        // (<4), `dot.path` split on `.` then both halves checked
        // individually (`path` keeps, `dot` drops). `snake_case` splits
        // on `_` → snake + case.
        assert!(toks.contains("buckhannon"));
        assert!(toks.contains("tail42"));
        assert!(toks.contains("snake"));
        assert!(toks.contains("case"));
        assert!(toks.contains("path"));
        assert!(!toks.contains("foo"));
        assert!(!toks.contains("bar"));
        assert!(!toks.contains("dot"));
    }

    #[test]
    fn drift_coverage_ratio_full_partial_zero_empty() {
        use std::collections::HashSet;
        let make =
            |words: &[&str]| -> HashSet<String> { words.iter().map(|s| s.to_string()).collect() };
        // Full coverage: every lesson token appears in preamble.
        let full = drift_coverage_ratio(
            &make(&["alpha", "beta"]),
            &make(&["alpha", "beta", "gamma"]),
        );
        assert!((full - 1.0).abs() < 1e-9);
        // Half coverage.
        let half = drift_coverage_ratio(&make(&["alpha", "delta"]), &make(&["alpha", "beta"]));
        assert!((half - 0.5).abs() < 1e-9);
        // Zero coverage.
        let zero = drift_coverage_ratio(&make(&["epsilon"]), &make(&["alpha", "beta"]));
        assert!(zero.abs() < 1e-9);
        // Empty lesson → 0 by convention.
        let empty = drift_coverage_ratio(&HashSet::new(), &make(&["x"]));
        assert!(empty.abs() < 1e-9);
    }

    #[test]
    fn drift_coverage_threshold_constant_is_30_percent() {
        // Pin the v0 threshold — bumping it changes report semantics
        // and should be a coordinated commit, not a silent drift.
        assert!((AGENT_MD_DRIFT_COVERAGE_THRESHOLD - 0.30).abs() < 1e-9);
    }

    // ── L7 P3 — skill-retro aggregator (pure) ─────────────────────────

    fn mk_lesson(
        key: &str,
        importance: f64,
        access_count: u64,
        created_at: i64,
    ) -> ab_store::MemoryRecord {
        ab_store::MemoryRecord {
            key: key.into(),
            kind: "lesson".into(),
            content: format!("body of {key}"),
            tags: vec![],
            related_keys: vec![],
            scope: None,
            created_at,
            updated_at: created_at,
            last_accessed_at: if access_count > 0 {
                created_at + 3600
            } else {
                0
            },
            access_count,
            importance,
            status: "active".into(),
            trigger_pattern: None,
            superseded_by: None,
        }
    }

    #[test]
    fn aggregate_skill_retro_empty_input_zero_metrics_no_div_by_zero() {
        let r = aggregate_skill_retro(vec![], 7, 1_700_000_000, 1_700_000_000 - 7 * 86_400);
        assert_eq!(r.lessons_total, 0);
        assert_eq!(r.lessons_consulted, 0);
        assert!(r.consulted_ratio.abs() < 1e-9);
        assert!(r.mean_access_count.abs() < 1e-9);
        assert!(r.rows.is_empty());
    }

    #[test]
    fn aggregate_skill_retro_counts_consulted_and_mean_access() {
        let now: i64 = 1_700_000_000;
        let cutoff = now - 7 * 86_400;
        let lessons = vec![
            mk_lesson("l_hot", 0.9, 5, now - 86_400),
            mk_lesson("l_warm", 0.7, 2, now - 2 * 86_400),
            mk_lesson("l_cold", 0.5, 0, now - 3 * 86_400),
        ];
        let r = aggregate_skill_retro(lessons, 7, now, cutoff);
        assert_eq!(r.lessons_total, 3);
        assert_eq!(r.lessons_consulted, 2, "two had access_count>0");
        assert!((r.consulted_ratio - 2.0 / 3.0).abs() < 1e-9);
        assert!((r.mean_access_count - 7.0 / 3.0).abs() < 1e-9);
        // Order by access DESC: hot, warm, cold.
        assert_eq!(r.rows[0].key, "l_hot");
        assert_eq!(r.rows[1].key, "l_warm");
        assert_eq!(r.rows[2].key, "l_cold");
        assert!(!r.rows[2].consulted, "cold row marked not consulted");
    }

    #[test]
    fn aggregate_skill_retro_all_consulted() {
        let now: i64 = 1_700_000_000;
        let cutoff = now - 7 * 86_400;
        let lessons = vec![
            mk_lesson("a", 0.5, 1, now - 86_400),
            mk_lesson("b", 0.5, 1, now - 2 * 86_400),
        ];
        let r = aggregate_skill_retro(lessons, 7, now, cutoff);
        assert_eq!(r.lessons_total, 2);
        assert_eq!(r.lessons_consulted, 2);
        assert!((r.consulted_ratio - 1.0).abs() < 1e-9);
    }

    // ── §6.5 rule 4 — gap-audit ───────────────────────────────────────

    #[test]
    fn gap_audit_table_has_13_entries() {
        let (_, entries) = super::current_gap_baseline();
        assert_eq!(
            entries.len(),
            13,
            "13-gap inventory must have exactly 13 entries"
        );
        let mut ids: Vec<&str> = entries.iter().map(|e| e.id).collect();
        ids.sort();
        let expected = [
            "A1", "A3", "B1", "B2", "B3", "C1", "C2", "C3", "D1", "D2", "D3", "E1", "E2",
        ];
        assert_eq!(ids, expected, "gap IDs must match canonical 13-set");
    }

    #[test]
    fn gap_audit_status_counts_sum_to_13() {
        let (_, entries) = super::current_gap_baseline();
        let c = super::GapStatusCounts::from_entries(entries);
        let total = c.closed + c.shelved + c.partial + c.planned + c.untouched;
        assert_eq!(total, 13, "counts must sum to total entries");
    }

    #[test]
    fn gap_audit_2026_05_16_snapshot_matches_audit_doc() {
        // Pin the snapshot constants against the published monthly audit so a
        // future edit to the constants doesn't silently drift from the doc
        // without a corresponding audit refresh.
        //
        // Reconciled to live 2026-06-04 (see the "2026-06-04 reconciliation
        // refresh" section appended to MONTHLY-GAP-COVERAGE-AUDIT-2026-05-16.md).
        // The 2026-05-16 audit pinned 6 closed; since then C2/C3 closed via L6
        // observability probes (6ad5959 / 38517f1·2c6e76b) and D2 closed via
        // durable cross-machine sync (fc11815 / 03da6a6 / 7862049 reconcile-to-
        // live, verified converged 2026-06-03), moving Partial(D2)→Closed and
        // Planned(C2,C3)→Closed. New tally: 9 closed / 0 partial / 0 planned.
        let (_, entries) = super::current_gap_baseline();
        let c = super::GapStatusCounts::from_entries(entries);
        assert_eq!(
            c.closed, 9,
            "reconciled tally: 9 closed (A3 B2 C2 C3 D1 D2 D3 E1 E2)"
        );
        assert_eq!(c.shelved, 1, "1 shelved (C1 — 3/3 FALSIFIED)");
        assert_eq!(c.partial, 0, "0 partial (D2 promoted Partial→Closed)");
        assert_eq!(c.planned, 0, "0 planned (C2 C3 promoted Planned→Closed)");
        assert_eq!(
            c.untouched, 3,
            "3 untouched (A1 B1 B3 — def working, no ship attempted)"
        );
    }

    #[test]
    fn gap_audit_group_oneline_by_prefix_simple() {
        let log = "\
abc1234 feat(l5): P1 — boost
def5678 feat(l5): P2 — correction
ghi9012 feat(l7): P1 — reflect
jkl3456 docs(infra): audit
mno7890 chore(infra): cleanup
pqr1357 random free-form subject without prefix
";
        let groups = super::group_oneline_by_prefix(log);
        let by_prefix: std::collections::HashMap<String, usize> = groups
            .iter()
            .map(|g| (g.prefix.clone(), g.commit_count))
            .collect();
        assert_eq!(by_prefix.get("feat(l5):"), Some(&2));
        assert_eq!(by_prefix.get("feat(l7):"), Some(&1));
        assert_eq!(by_prefix.get("docs(infra):"), Some(&1));
        assert_eq!(by_prefix.get("chore(infra):"), Some(&1));
        // The free-form subject without `:` is grouped under "uncategorized".
        // Subject "random free-form subject without prefix" has no colon
        // before whitespace → falls through to uncategorized.
        assert!(
            by_prefix.contains_key("uncategorized"),
            "free-form subject must be grouped under uncategorized"
        );
    }

    #[test]
    fn gap_audit_extract_prefix_handles_variants() {
        assert_eq!(
            super::extract_conventional_prefix("feat(l5): P1 boost").as_deref(),
            Some("feat(l5):")
        );
        assert_eq!(
            super::extract_conventional_prefix("docs: simple no-scope").as_deref(),
            Some("docs:")
        );
        assert_eq!(
            super::extract_conventional_prefix("no prefix at all"),
            None,
            "free-form (no colon before whitespace) must be None"
        );
        assert_eq!(
            super::extract_conventional_prefix("Free form: not conventional"),
            None,
            "human prose containing colon must be rejected (head has space)"
        );
    }

    #[test]
    fn gap_audit_outstanding_gates_future_only_with_today_anchor() {
        // Use a fixed `now` from the canonical audit baseline date to make
        // this deterministic across CI clock drift. 2026-05-16 UTC midnight.
        let now_unix: u64 = 1_778_975_200; // approx 2026-05-16 03:46 UTC
                                           // L5-P1 opens 2026-06-14 → ~29 days from now (anchor day).
        let days = super::iso_days_until_now("2026-06-14", now_unix).expect("valid iso");
        assert!(
            (28..=30).contains(&days),
            "2026-06-14 should be ~29 days from 2026-05-16, got {days}"
        );
        // L7-P2 opens 2026-07-11 → ~56 days.
        let d2 = super::iso_days_until_now("2026-07-11", now_unix).expect("valid iso");
        assert!(
            (54..=58).contains(&d2),
            "2026-07-11 should be ~56 days from 2026-05-16, got {d2}"
        );
        // A past date → negative.
        let d3 = super::iso_days_until_now("2026-01-01", now_unix).expect("valid iso");
        assert!(d3 < 0, "past date must be negative, got {d3}");
    }

    #[test]
    fn gap_audit_iso_parse_rejects_bad_input() {
        let now: u64 = 1_700_000_000;
        assert!(super::iso_days_until_now("not-a-date", now).is_none());
        assert!(
            super::iso_days_until_now("2026-13-01", now).is_none(),
            "month 13 invalid"
        );
        assert!(
            super::iso_days_until_now("2026-05-32", now).is_none(),
            "day 32 invalid"
        );
        assert!(
            super::iso_days_until_now("2026-05", now).is_none(),
            "wrong arity"
        );
    }
}
