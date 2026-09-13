use ab_agent::{
    AcpRuntime, AgentRuntime, AuggieRuntime, ClaudeCodeRuntime, CodexRuntime, GeminiRuntime,
    GitWorktreeManager, OpenCodeFamilyRuntime, OzAgentRuntime,
};
use ab_bridge::biocortex_shadow::{
    biocortex_replay_comparison, biocortex_retrieval_opt_in_batch_diagnostics,
    biocortex_retrieval_opt_in_gated_batch_diagnostics,
    biocortex_retrieval_opt_in_gated_store_trial,
    biocortex_retrieval_opt_in_runtime_trial, biocortex_retrieval_opt_in_store_trial,
    BioCortexReplayComparisonOptions,
    BioCortexRetrievalApprovalPacketOptions, BioCortexRetrievalCandidate,
    BioCortexRetrievalDownstreamAioRuntimeEvidenceHandoffOptions,
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
    BioCortexRetrievalOptInStoreTrialOptions, BIOCORTEX_RETRIEVAL_DISABLE_ENV,
};
#[cfg(feature = "biocortex-retrieval-shadow")]
use ab_bridge::biocortex_shadow::{
    biocortex_retrieval_shadow_report, BioCortexRetrievalShadowOptions,
};
use ab_bridge::seed_substrate as ab_seed_bridge;
use ab_bridge::shadow_cortex as ab_shadow_cortex;
use ab_bridge::warp_scheme;
use ab_bridge::{instinct, skills};
use ab_bridge::{build_registry, default_socket_path, serve, Hub, Router};
use ab_browser::{BrowserBackend, ChromiumCdpBackend};
use ab_mcp::server::serve_stdio;
use ab_store::{default_db_path, SqliteStore, StateStore};
use ab_terminal::{auto_backend, TerminalBackend};
use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand, ValueEnum};
use serde_json::{json, Map, Value};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tracing_subscriber::{prelude::*, EnvFilter};

mod cli;
#[cfg(feature = "r9-workload-receipts")]
use cli::startup_report::log_workload_receipt_reconciliation_report;
use cli::avatar_observer_view::{
    focus_observer_context_from_plan, focus_observer_identity_from_plan,
    focus_observer_terminal_context, focus_observer_travel_px,
};
mod doctor;
mod seed_substrate;
mod setup;
mod shadow_cortex;
use ab_bridge::sync;
use cli::workflow_feedback::{
    run_workflow_feedback_baseline_evidence, run_workflow_feedback_lift_evidence,
    run_workflow_feedback_owner_review_packet, run_workflow_feedback_promotion_gate,
    run_workflow_feedback_promotion_record, run_workflow_feedback_report,
    run_workflow_feedback_shadow_score,
};
use cli::{
    aggregate_skill_retro, drift_coverage_ratio, drift_tokens,
    run_biocortex_capability_ledger_report_packet, run_biocortex_retrieval_approval_packet,
    run_biocortex_retrieval_downstream_aio_runtime_evidence_handoff,
    run_biocortex_retrieval_opt_in_authorization_decision_packet,
    run_biocortex_retrieval_opt_in_controlled_order_fixture_result,
    run_biocortex_retrieval_opt_in_dry_run, run_biocortex_retrieval_opt_in_execution_packet,
    run_biocortex_retrieval_opt_in_order_diff_packet,
    run_biocortex_retrieval_opt_in_post_implementation_review_gate,
    run_biocortex_retrieval_opt_in_redacted_evidence_aggregate,
    run_biocortex_retrieval_opt_in_redacted_order_artifact,
    run_biocortex_retrieval_opt_in_review_packet,
    run_biocortex_retrieval_opt_in_runtime_influence_decision_packet,
    run_biocortex_retrieval_opt_in_runtime_influence_review_request,
    run_biocortex_retrieval_opt_in_runtime_readiness_packet,
    run_biocortex_retrieval_opt_in_runtime_transition_gate,
    run_biocortex_retrieval_opt_in_runtime_trial_review_packet,
    run_biocortex_retrieval_opt_in_status, run_biocortex_retrieval_opt_in_evidence_summary,
    run_biocortex_retrieval_opt_in_store_trial_result,
    run_biocortex_shadow_digest, run_browser_lite, render_codebase_report_html, render_promote_html,
    run_lswr_interaction_feedback_consumption_preflight, run_substrate, shadow_json_display,
    short_key, triage_agent_md_drift_candidate, truncate_chars, A2uiOp, BrowserLiteOp,
    OperatorRequestOp, PromoteDecision, PromoteStatus, SubstrateOp,
    AGENT_MD_DRIFT_COVERAGE_THRESHOLD,
};

#[derive(Parser, Debug)]
#[command(
    name = "agent-bridge",
    version = ab_bridge::build_identity::PACKAGE_VERSION,
    long_version = ab_bridge::build_identity::LONG_VERSION,
    about = "agent-bridge — Unix-native AI agent control plane"
)]
struct Cli {
    #[command(subcommand)]
    cmd: Option<Cmd>,
}

#[derive(Subcommand, Debug)]
enum Cmd {
    /// Run the long-lived JSON-RPC daemon on a Unix socket (default).
    Daemon {
        #[arg(long, value_enum)]
        episode_observation: Option<EpisodeObservationMode>,
    },
    /// Run as an MCP stdio server (for `claude mcp add agent-bridge ...`).
    Mcp {
        #[arg(long, value_enum)]
        episode_observation: Option<EpisodeObservationMode>,
    },
    /// Run the synthetic loopback HTTP/OAuth MCP lab.
    ///
    /// This is a default-off verification surface, not a production server.
    /// The config must explicitly declare `mode: "synthetic_lab"`; the
    /// listener and resource URL must both resolve to the same loopback socket.
    McpHttpAuthLab {
        /// Synthetic lab JSON config containing public JWKS and subject policy.
        #[arg(long)]
        config: PathBuf,
    },
    /// Run the provider-backed, read-only HTTP/OAuth MCP candidate.
    ///
    /// This remains default off and exposes only an authenticated subject
    /// diagnostic. It fetches OAuth/OIDC discovery and public JWKS material,
    /// but does not initialize Agent-Bridge backends or execution tools.
    McpHttpAuthCandidate {
        /// Provider candidate JSON config with no bearer tokens or private keys.
        #[arg(long)]
        config: PathBuf,
    },
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
    /// Run bounded Resident Xiao Shu cognition.
    ///
    /// V0 is explicit, one-shot, read-only, and advisory-only. Agent-Bridge
    /// owns the durable subject receipt; the owner accepts disclosure and
    /// recoverable-failure risk, while irreversible host or external mutation
    /// remains denied by the loss-tolerant provider envelope.
    Resident {
        #[command(subcommand)]
        op: ResidentOp,
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
    /// Review the private ChatGPT collaboration request queue.
    ///
    /// This local-only CLI can append one approve/reject evidence record.
    /// Approval never executes a request and never authorizes canonical writes;
    /// a separate executor gate would still be required.
    OperatorRequest {
        #[command(subcommand)]
        op: OperatorRequestOp,
    },
    /// Validate an A2UI v0.9.1 server-message stream without rendering or executing it.
    A2ui {
        #[command(subcommand)]
        op: A2uiOp,
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
    /// Run the v20 HTTP daemon for local integrations and optional
    /// cross-machine forum + presence over Tailscale.
    ///
    /// Includes forum, inbox, and review-decision write routes in addition to
    /// read-only presence/avatar surfaces, so the default is local-only.
    /// Explicit remote listeners rely on a correctly scoped Tailscale ACL.
    /// See `docs/RFC-v20-tailscale-daemon.md`.
    DaemonHttp {
        /// Listen address. Defaults to local-only `127.0.0.1:7878` because
        /// daemon-http includes write routes. Remote exposure requires an
        /// explicit address via this flag or `AGENT_BRIDGE_HTTP_LISTEN`.
        #[arg(long, env = "AGENT_BRIDGE_HTTP_LISTEN")]
        listen: Option<String>,
    },
    /// Run the explicitly hash-pinned G1.4 WASI typed-report component.
    ///
    /// Available only with `g14-wasi-component-runtime`; this is an operator
    /// probe, not an MCP tool or an open component/plugin registry.
    #[cfg(feature = "g14-wasi-component-runtime")]
    G14WasiComponent {
        /// Component artifact to load.
        #[arg(long)]
        artifact: PathBuf,
        /// Expected lowercase SHA-256 of the artifact.
        #[arg(long)]
        sha256: String,
    },
    /// Run the explicitly hash-pinned G1.4 synthetic business component.
    ///
    /// Available only with `g14-wasi-component-runtime`; this is an operator
    /// probe, not an MCP tool or an open component/plugin registry.
    #[cfg(feature = "g14-wasi-component-runtime")]
    G14WasiBusinessComponent {
        /// Component artifact to load.
        #[arg(long)]
        artifact: PathBuf,
        /// Expected lowercase SHA-256 of the artifact.
        #[arg(long)]
        sha256: String,
        /// Synthetic world-state revision.
        #[arg(long, default_value_t = 7)]
        revision: u64,
        /// Synthetic entity count.
        #[arg(long, default_value_t = 12)]
        entity_count: u32,
        /// Synthetic occupied-cell count.
        #[arg(long, default_value_t = 9)]
        occupied_cells: u32,
        /// Synthetic transition count.
        #[arg(long, default_value_t = 4)]
        transition_count: u32,
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
    /// Render an evidence-anchored session walkthrough doc (JSON) into a
    /// shareable HTML artifact in the present gallery — the daily-wire entry
    /// for `present::write_walkthrough_artifact`. Adds NO new MCP tool; pair
    /// with the `/walkthrough` skill, which assembles the doc from session
    /// evidence (event-spine / memory / commit refs) and calls this.
    ///
    /// Doc shape: `{summary, steps:[{heading,narrative,evidence:[{kind,
    /// reference,label}]}]}`. Reads the file at `doc`, or stdin when `doc=-`.
    Walkthrough {
        /// Path to the walkthrough doc JSON, or `-` to read it from stdin.
        doc: String,
        /// Optional artifact title (shown in the gallery + `<title>`).
        #[arg(long)]
        title: Option<String>,
        /// Emit JSON `{id, path, self_check}` instead of the human-readable lines.
        #[arg(long)]
        json: bool,
    },
    /// Standing continuity `U` report (Goal C): the store-side embedding-space
    /// health — backend mix, stale-vector fraction, host-correct anisotropy —
    /// each row tagged with its external anchor, falsifier, and owner. Read-only,
    /// adds NO new MCP tool; pair with the `/continuity` skill. Recall R@k stays
    /// owned by the `recall_eval` harness (the held-out anchor); this surface
    /// aggregates the store-derivable signals around it.
    ContinuityReport {
        /// Emit the machine-readable JSON snapshot instead of the report.
        #[arg(long)]
        json: bool,
    },
    /// Read-only workflow feedback report: compose existing memory statistics
    /// and MCP tool-call telemetry into a maturity scorecard plus an
    /// Experience Object v0 fixture. Report-first only: no memory writes, no
    /// retrieval changes, and no runtime policy mutation.
    WorkflowFeedbackReport {
        /// Seconds of MCP tool-call telemetry to inspect.
        #[arg(long, default_value_t = 86_400)]
        window_secs: i64,
        /// Number of hot tools to include in the report.
        #[arg(long, default_value_t = 10)]
        top_tools: u32,
        /// Emit the machine-readable JSON snapshot instead of Markdown.
        #[arg(long)]
        json: bool,
    },
    /// Read-only shadow scoring over Experience Object v0 fixtures.
    ///
    /// Ranks whether a fixture's lesson appears useful for a held-out scenario
    /// without changing bootstrap, retrieval ranking, tool routing, memory, or
    /// runtime policy.
    WorkflowFeedbackShadowScore {
        /// Experience Object v0 fixture JSON. Repeat for multiple candidates.
        #[arg(long = "fixture", required = true)]
        fixtures: Vec<PathBuf>,
        /// Held-out workflow scenario to score against. Repeat for multiple
        /// scenarios. When omitted, a generic workflow-policy scenario is used.
        #[arg(long = "scenario")]
        scenarios: Vec<String>,
        /// Emit the machine-readable JSON snapshot instead of Markdown.
        #[arg(long)]
        json: bool,
    },
    /// Read-only promotion gate over workflow feedback shadow-score reports.
    ///
    /// Consumes previously emitted `workflow-feedback-shadow-score --json`
    /// reports and checks whether repeated evidence is strong enough for owner
    /// review. It does not promote memories, runbooks, skills, retrieval rules,
    /// tool routing, or runtime policy.
    WorkflowFeedbackPromotionGate {
        /// Shadow-score JSON report. Repeat for independent shadow runs.
        #[arg(long = "shadow-score", required = true)]
        shadow_scores: Vec<PathBuf>,
        /// Explicit owner approval reference. Repeat when multiple refs exist.
        #[arg(long = "owner-approval-ref")]
        owner_approval_refs: Vec<String>,
        /// Rollback path, revert handle, or disable-switch reference.
        #[arg(long = "rollback-ref")]
        rollback_refs: Vec<String>,
        /// Measured behavior-lift anchor or falsifiable metric reference.
        #[arg(long = "behavior-lift-ref")]
        behavior_lift_refs: Vec<String>,
        /// Minimum independent shadow-score reports required.
        #[arg(long, default_value_t = 2)]
        min_shadow_reports: usize,
        /// Minimum held-out scenarios required across the reports.
        #[arg(long, default_value_t = 2)]
        min_scenarios: usize,
        /// Minimum strong top-ranked scenario matches required.
        #[arg(long, default_value_t = 2)]
        min_strong_scenarios: usize,
        /// Minimum top-candidate shadow score for a strong match.
        #[arg(long, default_value_t = 65)]
        min_top_shadow_score: u32,
        /// Emit the machine-readable JSON snapshot instead of Markdown.
        #[arg(long)]
        json: bool,
    },
    /// Read-only lift-evidence proxy over held-out shadow-score scenarios.
    ///
    /// Compares shadow-score top candidates against expected top fixtures from
    /// a scenario fixture. With baseline correct/total it can emit a measured
    /// proxy lift anchor; without baseline it remains a falsifiable metric
    /// anchor only. It does not change runtime, retrieval, memory, or routing.
    WorkflowFeedbackLiftEvidence {
        /// Scenario fixture containing expected top experience ids.
        #[arg(long = "scenario-fixture")]
        scenario_fixture: PathBuf,
        /// Shadow-score JSON report. Repeat for independent shadow runs.
        #[arg(long = "shadow-score", required = true)]
        shadow_scores: Vec<PathBuf>,
        /// Baseline correct count from an unguided or previous-policy run.
        #[arg(long = "baseline-correct")]
        baseline_correct: Option<u32>,
        /// Baseline total count from an unguided or previous-policy run.
        #[arg(long = "baseline-total")]
        baseline_total: Option<u32>,
        /// Minimum expected-top accuracy required for the proxy anchor.
        #[arg(long, default_value_t = 0.75)]
        min_accuracy: f64,
        /// Minimum absolute lift over baseline required when baseline is supplied.
        #[arg(long, default_value_t = 0.10)]
        min_lift: f64,
        /// Emit the machine-readable JSON snapshot instead of Markdown.
        #[arg(long)]
        json: bool,
    },
    /// Read-only baseline/rollback evidence packet for workflow feedback lift.
    ///
    /// Consumes baseline observation fixtures for the held-out scenario set and
    /// emits baseline correct/total plus rollback refs for later lift evidence
    /// and promotion-gate review. It does not run an agent or change runtime,
    /// retrieval, memory, or routing.
    WorkflowFeedbackBaselineEvidence {
        /// Scenario fixture containing expected top experience ids.
        #[arg(long = "scenario-fixture")]
        scenario_fixture: PathBuf,
        /// Baseline observation fixture. Repeat for independent baselines.
        #[arg(long = "baseline-observation", required = true)]
        baseline_observations: Vec<PathBuf>,
        /// Rollback path, revert handle, or disable-switch reference.
        #[arg(long = "rollback-ref")]
        rollback_refs: Vec<String>,
        /// Emit the machine-readable JSON snapshot instead of Markdown.
        #[arg(long)]
        json: bool,
    },
    /// Read-only owner-review packet over baseline, lift, and promotion gates.
    ///
    /// Composes baseline observations, shadow-score reports, measured lift
    /// evidence, and promotion-gate checks into a single review packet. It does
    /// not promote anything or change runtime, retrieval, memory, or routing.
    WorkflowFeedbackOwnerReviewPacket {
        /// Scenario fixture containing expected top experience ids.
        #[arg(long = "scenario-fixture")]
        scenario_fixture: PathBuf,
        /// Baseline observation fixture. Repeat for independent baselines.
        #[arg(long = "baseline-observation", required = true)]
        baseline_observations: Vec<PathBuf>,
        /// Shadow-score JSON report. Repeat for independent shadow runs.
        #[arg(long = "shadow-score", required = true)]
        shadow_scores: Vec<PathBuf>,
        /// Rollback path, revert handle, or disable-switch reference.
        #[arg(long = "rollback-ref")]
        rollback_refs: Vec<String>,
        /// Explicit owner approval reference. Repeat when multiple refs exist.
        #[arg(long = "owner-approval-ref")]
        owner_approval_refs: Vec<String>,
        /// Minimum expected-top accuracy required for the proxy anchor.
        #[arg(long, default_value_t = 0.75)]
        min_accuracy: f64,
        /// Minimum absolute lift over baseline required when baseline is supplied.
        #[arg(long, default_value_t = 0.10)]
        min_lift: f64,
        /// Minimum independent shadow-score reports required.
        #[arg(long, default_value_t = 2)]
        min_shadow_reports: usize,
        /// Minimum held-out scenarios required across the reports.
        #[arg(long, default_value_t = 2)]
        min_scenarios: usize,
        /// Minimum strong top-ranked scenario matches required.
        #[arg(long, default_value_t = 2)]
        min_strong_scenarios: usize,
        /// Minimum top-candidate shadow score for a strong match.
        #[arg(long, default_value_t = 65)]
        min_top_shadow_score: u32,
        /// Emit the machine-readable JSON snapshot instead of Markdown.
        #[arg(long)]
        json: bool,
    },
    /// Read-only low-risk promotion record from an owner-review packet.
    ///
    /// Consumes an owner-review packet plus explicit approval/rollback refs and
    /// records only documentation, durable-memory, or runbook promotion intent.
    /// Higher-blast-radius scopes are blocked by the packet instead of applied.
    WorkflowFeedbackPromotionRecord {
        /// Owner-review packet JSON emitted by workflow-feedback-owner-review-packet.
        #[arg(long = "owner-review-packet")]
        owner_review_packet: PathBuf,
        /// Low-risk promotion scope. Allowed here: documentation, durable_memory, runbook.
        #[arg(long = "promotion-scope", required = true)]
        promotion_scopes: Vec<String>,
        /// Explicit owner approval reference for this separate promotion-record lane.
        #[arg(long = "owner-approval-ref")]
        owner_approval_refs: Vec<String>,
        /// Rollback path, revert handle, or disable-switch reference.
        #[arg(long = "rollback-ref")]
        rollback_refs: Vec<String>,
        /// Emit the machine-readable JSON snapshot instead of Markdown.
        #[arg(long)]
        json: bool,
    },
}

#[derive(clap::ValueEnum, Clone, Copy, Debug, PartialEq, Eq)]
enum EpisodeObservationMode {
    KeychainMacosV1,
}

#[derive(Copy, Clone, Debug, ValueEnum)]
enum ShellKind {
    Bash,
    Zsh,
    Fish,
}

#[derive(Copy, Clone, Debug, ValueEnum)]
enum InstinctReviewDecision {
    Approve,
    Reject,
    Defer,
}

impl InstinctReviewDecision {
    fn as_str(self) -> &'static str {
        match self {
            InstinctReviewDecision::Approve => "approve",
            InstinctReviewDecision::Reject => "reject",
            InstinctReviewDecision::Defer => "defer",
        }
    }
}

#[derive(Subcommand, Debug)]
enum InstinctOp {
    /// Build a read-only Phase 1 candidate preview from the observer sidecar
    /// log. Does not write memories or persist a review queue.
    Candidates {
        /// Maximum candidate rows to return.
        #[arg(long, default_value_t = 20)]
        limit: usize,
        /// Emit raw JSON payload instead of a compact command line summary.
        #[arg(long)]
        json: bool,
    },
    /// Build a redacted human review packet from Phase 1 candidates. Preview
    /// only by default; --write writes JSON + Markdown and still never writes
    /// memories.
    ReviewPacket {
        /// Maximum candidate rows to include.
        #[arg(long, default_value_t = 20)]
        limit: usize,
        /// Optional reviewer label recorded in the packet.
        #[arg(long)]
        reviewer: Option<String>,
        /// Optional output directory for --write. Defaults to the private
        /// instinct review sidecar directory.
        #[arg(long)]
        out_dir: Option<PathBuf>,
        /// Write JSON + Markdown packet files. Without this flag the command is
        /// a dry-run preview.
        #[arg(long)]
        write: bool,
        /// Emit raw JSON payload instead of a compact command line summary.
        #[arg(long)]
        json: bool,
    },
    /// Record a human approve/reject/defer decision for one review-packet
    /// candidate. Preview only by default; --write appends a private local
    /// decision JSONL record and still never writes memories.
    ReviewDecision {
        /// Review packet JSON produced by `instinct review-packet --write`.
        #[arg(long)]
        packet_json: PathBuf,
        /// Candidate id inside the review packet, e.g. instinct-candidate-0001.
        #[arg(long)]
        candidate_id: String,
        /// Human decision for this candidate.
        #[arg(long, value_enum)]
        decision: InstinctReviewDecision,
        /// Optional reviewer label recorded in the decision.
        #[arg(long)]
        reviewer: Option<String>,
        /// Optional human note recorded in the private local decision log.
        #[arg(long)]
        note: Option<String>,
        /// Optional output JSONL path for --write. Defaults to decisions.jsonl
        /// under the private instinct review sidecar directory.
        #[arg(long)]
        out: Option<PathBuf>,
        /// Append the decision record. Without this flag the command is a
        /// dry-run preview.
        #[arg(long)]
        write: bool,
        /// Emit raw JSON payload instead of a compact command line summary.
        #[arg(long)]
        json: bool,
    },
    /// Build a dry-run memory-write preflight for an approved candidate. This
    /// validates the review packet + latest decision and never writes memory.
    MemoryPreflight {
        /// Review packet JSON produced by `instinct review-packet --write`.
        #[arg(long)]
        packet_json: PathBuf,
        /// Candidate id inside the review packet, e.g. instinct-candidate-0001.
        #[arg(long)]
        candidate_id: String,
        /// Optional decisions JSONL path. Defaults to decisions.jsonl under the
        /// private instinct review sidecar directory.
        #[arg(long)]
        decisions: Option<PathBuf>,
        /// Human-authored memory key for the later explicit memory write.
        #[arg(long)]
        memory_key: Option<String>,
        /// Human-authored memory kind for the later explicit memory write.
        #[arg(long)]
        memory_kind: Option<String>,
        /// Human-authored memory body for the later explicit memory write.
        #[arg(long)]
        memory_body: Option<String>,
        /// Optional output directory for --write. Defaults to the private
        /// instinct review sidecar directory.
        #[arg(long)]
        out_dir: Option<PathBuf>,
        /// Write JSON + Markdown preflight files. Without this flag the command
        /// is a dry-run preview.
        #[arg(long)]
        write: bool,
        /// Emit raw JSON payload instead of a compact command line summary.
        #[arg(long)]
        json: bool,
    },
    /// Save memory from a ready instinct memory preflight. Requires --write and
    /// never accepts free-form memory content directly.
    MemoryWrite {
        /// Preflight JSON produced by `instinct memory-preflight --write`.
        #[arg(long)]
        preflight_json: PathBuf,
        /// Optional state DB path. Defaults to Agent-Bridge's normal state DB.
        #[arg(long)]
        db_path: Option<PathBuf>,
        /// Optional receipt JSONL path. Defaults to memory-writes.jsonl under
        /// the private instinct review sidecar directory.
        #[arg(long)]
        receipt_out: Option<PathBuf>,
        /// Actually call memory_save. Without this flag the command is a
        /// dry-run preview.
        #[arg(long)]
        write: bool,
        /// Emit raw JSON payload instead of a compact command line summary.
        #[arg(long)]
        json: bool,
    },
    /// Read-only summary of instinct review packets, decisions, and
    /// preflights in the private review sidecar directory.
    ReviewStatus {
        /// Optional review directory. Defaults to the private instinct review
        /// sidecar directory.
        #[arg(long)]
        review_dir: Option<PathBuf>,
        /// Optional decisions JSONL path. Defaults to decisions.jsonl under the
        /// private instinct review sidecar directory.
        #[arg(long)]
        decisions: Option<PathBuf>,
        /// Optional memory-write receipt JSONL path. Defaults to
        /// memory-writes.jsonl under the private instinct review sidecar
        /// directory.
        #[arg(long)]
        receipts: Option<PathBuf>,
        /// Maximum recent rows per section.
        #[arg(long, default_value_t = 10)]
        limit: usize,
        /// Emit raw JSON payload instead of a compact command line summary.
        #[arg(long)]
        json: bool,
    },
    /// Read-only candidate inbox for a review packet, merged with latest
    /// approve/reject/defer decisions. Does not write memories.
    ReviewInbox {
        /// Optional review packet JSON. Defaults to the newest packet in the
        /// private instinct review sidecar directory.
        #[arg(long)]
        packet_json: Option<PathBuf>,
        /// Optional review directory used when --packet-json is omitted.
        #[arg(long)]
        review_dir: Option<PathBuf>,
        /// Optional decisions JSONL path. Defaults to decisions.jsonl under the
        /// private instinct review sidecar directory.
        #[arg(long)]
        decisions: Option<PathBuf>,
        /// Maximum candidate rows to print.
        #[arg(long, default_value_t = 20)]
        limit: usize,
        /// Emit raw JSON payload instead of a compact command line summary.
        #[arg(long)]
        json: bool,
    },
    /// Read-only context for one review candidate. Local prompt excerpt is
    /// omitted unless --include-local-excerpt is passed.
    ReviewContext {
        /// Review packet JSON produced by `instinct review-packet --write`.
        #[arg(long)]
        packet_json: PathBuf,
        /// Candidate id inside the review packet, e.g. instinct-candidate-0001.
        #[arg(long)]
        candidate_id: String,
        /// Optional observer JSONL path. Defaults to the private observer log.
        #[arg(long)]
        log: Option<PathBuf>,
        /// Include the local observer prompt excerpt in output. This remains
        /// read-only but may expose local prompt text.
        #[arg(long)]
        include_local_excerpt: bool,
        /// Emit raw JSON payload instead of a compact command line summary.
        #[arg(long)]
        json: bool,
    },
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
enum ResidentOp {
    /// Inspect the owner-approved loss-tolerant live admission policy without
    /// starting a provider, reading provider auth, or writing Resident state.
    RiskPreflight {
        /// Candidate native Codex executable. The file must match AB's pinned
        /// content hash; AB_RESIDENT_CODEX_BIN is used at the default value.
        #[arg(long, default_value = "codex")]
        codex_bin: PathBuf,
        /// Emit the structured report as JSON.
        #[arg(long)]
        json: bool,
    },
    /// Analyze one observed event without executing or scheduling the advice.
    Cognition {
        /// Untrusted observed event to analyze. It is visible to the provider
        /// and host argv; AB stores only its hash as a dedicated event field.
        #[arg(long)]
        event: String,
        /// Stable caller identity for the event. Generated when omitted.
        #[arg(long)]
        event_id: Option<String>,
        /// Workspace identity recorded by AB. The permanent-damage envelope
        /// does not mount this host directory into the provider.
        #[arg(long, default_value = ".")]
        cwd: PathBuf,
        /// Efficient model used by the ephemeral cognition provider.
        #[arg(long, default_value = ab_bridge::resident_cognition::DEFAULT_RESIDENT_MODEL)]
        model: String,
        /// Bounded reasoning effort: low or medium.
        #[arg(long, default_value = ab_bridge::resident_cognition::DEFAULT_REASONING_EFFORT)]
        reasoning_effort: String,
        /// Hard wall-clock limit for the provider (10..=120 seconds).
        #[arg(long, default_value_t = ab_bridge::resident_cognition::DEFAULT_TIMEOUT_SECS)]
        timeout_secs: u64,
        /// Native Codex executable candidate. AB_RESIDENT_CODEX_BIN is used at
        /// the default; live use accepts only AB's pinned content hash.
        #[arg(long, default_value = "codex")]
        codex_bin: PathBuf,
        /// Emit the exact bounded launch contract without starting Codex or
        /// writing a receipt.
        #[arg(long)]
        dry_run: bool,
    },
    /// Bind an explicit owner usefulness label to one completed wake.
    ///
    /// The label is a local CLI assertion, not a model judgment or
    /// cryptographically authenticated identity claim. It never changes
    /// runtime authority or admits M2 automatically.
    Evaluate {
        /// Completed resident wake ID returned by `resident cognition`.
        #[arg(long)]
        wake_id: String,
        /// Owner-observed product value for this one wake.
        #[arg(long, value_enum)]
        label: ResidentOwnerLabelArg,
        /// Preview the evaluation contract without reading or writing state.
        #[arg(long)]
        dry_run: bool,
    },
    /// Preview one typed reason-driven wake candidate without waking cognition.
    ///
    /// This M2 shadow is explicit and default-off. It accepts only content
    /// hashes, requires a bound useful owner evaluation, and may record a
    /// private policy receipt. It never invokes a provider or installs a
    /// scheduler.
    Shadow {
        /// Useful completed wake whose owner evaluation admits shadow review.
        #[arg(long)]
        basis_wake_id: String,
        /// Typed reason proposed for a hypothetical sparse wake.
        #[arg(long, value_enum)]
        trigger_kind: ResidentM2ShadowTriggerKindArg,
        /// SHA-256 of the stable candidate signal; raw signal text is forbidden.
        #[arg(long)]
        signal_sha256: String,
        /// SHA-256 of the candidate evidence; raw evidence is not persisted.
        #[arg(long)]
        evidence_sha256: String,
        /// Verification status of the candidate evidence.
        #[arg(long, value_enum, default_value = "unknown")]
        evidence_status: ResidentM2ShadowEvidenceStatusArg,
        /// When the candidate signal was observed.
        #[arg(long)]
        observed_at_unix_ms: u64,
        /// Required only for commitment-due candidates.
        #[arg(long)]
        due_at_unix_ms: Option<u64>,
        /// Failure severity; ignored by commitment and recovery candidates.
        #[arg(long, value_enum, default_value = "info")]
        severity: ResidentM2ShadowSeverityArg,
        /// Whether an interactive foreground owner session is active.
        #[arg(long, value_enum, default_value = "unknown")]
        foreground_state: ResidentM2ShadowForegroundStateArg,
        /// Deterministic replay time; current time is used when omitted.
        #[arg(long)]
        evaluated_at_unix_ms: Option<u64>,
        /// Candidate-local UTC offset in minutes, e.g. -420 for PDT.
        #[arg(long, allow_hyphen_values = true)]
        utc_offset_minutes: i16,
        /// Persist a private 0600 shadow report. Preview is the default.
        #[arg(long)]
        record: bool,
    },
    /// Review private M2 shadow evidence without modifying reports or waking.
    ///
    /// Classifications are explicit, invocation-local operating assertions;
    /// they are not persisted or cryptographically authenticated. A ready
    /// packet permits only a separate owner review, never M2 admission.
    ShadowReview {
        /// Real-task report ID. Repeat for each natural candidate report.
        #[arg(long = "natural-report-id")]
        natural_report_ids: Vec<String>,
        /// Mechanics-only report ID. Repeat for each technical acceptance report.
        #[arg(long = "mechanics-report-id")]
        mechanics_report_ids: Vec<String>,
    },
}

#[derive(Clone, Copy, Debug, ValueEnum)]
enum ResidentOwnerLabelArg {
    Useful,
    Neutral,
    Distracting,
    Harmful,
}

impl From<ResidentOwnerLabelArg> for ab_bridge::resident_owner_evaluation::ResidentOwnerLabel {
    fn from(value: ResidentOwnerLabelArg) -> Self {
        use ab_bridge::resident_owner_evaluation::ResidentOwnerLabel;
        match value {
            ResidentOwnerLabelArg::Useful => ResidentOwnerLabel::Useful,
            ResidentOwnerLabelArg::Neutral => ResidentOwnerLabel::Neutral,
            ResidentOwnerLabelArg::Distracting => ResidentOwnerLabel::Distracting,
            ResidentOwnerLabelArg::Harmful => ResidentOwnerLabel::Harmful,
        }
    }
}

#[derive(Clone, Copy, Debug, ValueEnum)]
enum ResidentM2ShadowTriggerKindArg {
    CommitmentDue,
    Recovery,
    Failure,
}

impl From<ResidentM2ShadowTriggerKindArg>
    for ab_bridge::resident_m2_shadow::ResidentM2ShadowTriggerKind
{
    fn from(value: ResidentM2ShadowTriggerKindArg) -> Self {
        use ab_bridge::resident_m2_shadow::ResidentM2ShadowTriggerKind;
        match value {
            ResidentM2ShadowTriggerKindArg::CommitmentDue => {
                ResidentM2ShadowTriggerKind::CommitmentDue
            }
            ResidentM2ShadowTriggerKindArg::Recovery => ResidentM2ShadowTriggerKind::Recovery,
            ResidentM2ShadowTriggerKindArg::Failure => ResidentM2ShadowTriggerKind::Failure,
        }
    }
}

#[derive(Clone, Copy, Debug, ValueEnum)]
enum ResidentM2ShadowEvidenceStatusArg {
    Verified,
    NotVerified,
    Unknown,
}

impl From<ResidentM2ShadowEvidenceStatusArg>
    for ab_bridge::resident_m2_shadow::ResidentM2ShadowEvidenceStatus
{
    fn from(value: ResidentM2ShadowEvidenceStatusArg) -> Self {
        use ab_bridge::resident_m2_shadow::ResidentM2ShadowEvidenceStatus;
        match value {
            ResidentM2ShadowEvidenceStatusArg::Verified => {
                ResidentM2ShadowEvidenceStatus::Verified
            }
            ResidentM2ShadowEvidenceStatusArg::NotVerified => {
                ResidentM2ShadowEvidenceStatus::NotVerified
            }
            ResidentM2ShadowEvidenceStatusArg::Unknown => {
                ResidentM2ShadowEvidenceStatus::Unknown
            }
        }
    }
}

#[derive(Clone, Copy, Debug, ValueEnum)]
enum ResidentM2ShadowSeverityArg {
    Info,
    Warning,
    Critical,
}

impl From<ResidentM2ShadowSeverityArg>
    for ab_bridge::resident_m2_shadow::ResidentM2ShadowSeverity
{
    fn from(value: ResidentM2ShadowSeverityArg) -> Self {
        use ab_bridge::resident_m2_shadow::ResidentM2ShadowSeverity;
        match value {
            ResidentM2ShadowSeverityArg::Info => ResidentM2ShadowSeverity::Info,
            ResidentM2ShadowSeverityArg::Warning => ResidentM2ShadowSeverity::Warning,
            ResidentM2ShadowSeverityArg::Critical => ResidentM2ShadowSeverity::Critical,
        }
    }
}

#[derive(Clone, Copy, Debug, ValueEnum)]
enum ResidentM2ShadowForegroundStateArg {
    Active,
    Inactive,
    Unknown,
}

impl From<ResidentM2ShadowForegroundStateArg>
    for ab_bridge::resident_m2_shadow::ResidentM2ShadowForegroundState
{
    fn from(value: ResidentM2ShadowForegroundStateArg) -> Self {
        use ab_bridge::resident_m2_shadow::ResidentM2ShadowForegroundState;
        match value {
            ResidentM2ShadowForegroundStateArg::Active => {
                ResidentM2ShadowForegroundState::Active
            }
            ResidentM2ShadowForegroundStateArg::Inactive => {
                ResidentM2ShadowForegroundState::Inactive
            }
            ResidentM2ShadowForegroundStateArg::Unknown => {
                ResidentM2ShadowForegroundState::Unknown
            }
        }
    }
}

#[derive(Subcommand, Debug)]
enum AvatarOp {
    /// Compile a generated chroma-background sprite strip into a deterministic
    /// RGBA atlas. Default is a read-only preview; writing requires confirmation.
    SpriteAssetCompile {
        #[arg(long)]
        input: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long, default_value_t = 6)]
        frame_count: u32,
        #[arg(long, default_value_t = 192)]
        cell_width: u32,
        #[arg(long, default_value_t = 208)]
        cell_height: u32,
        #[arg(long, default_value_t = 6)]
        padding_px: u32,
        #[arg(long, default_value_t = 201)]
        baseline_y: u32,
        /// Mirror each frame inside its own cell without reversing frame order.
        #[arg(long)]
        flip_horizontal: bool,
        #[arg(long)]
        execute: bool,
        #[arg(long, requires = "execute")]
        confirm: bool,
        #[arg(long)]
        json: bool,
    },
    /// Report the machine-readable production contract and readiness of all
    /// dedicated focus-follow sprite atlases.
    SpriteAssetContract {
        #[arg(
            long,
            default_value = "crates/bridge/assets/xiao-shu-prototypes"
        )]
        asset_root: PathBuf,
        #[arg(long)]
        json: bool,
    },
    /// Validate a candidate sprite atlas before it may be bound to the Avatar.
    SpriteAssetAudit {
        #[arg(long)]
        path: PathBuf,
        #[arg(long, default_value_t = 6)]
        columns: u32,
        #[arg(long, default_value_t = 1)]
        rows: u32,
        #[arg(long, default_value_t = 192)]
        cell_width: u32,
        #[arg(long, default_value_t = 208)]
        cell_height: u32,
        /// Number of populated cells, in row-major order. Defaults to all cells.
        #[arg(long)]
        frame_count: Option<u32>,
        /// Final Avatar viewport used for projected readability metrics.
        #[arg(long, default_value_t = 90)]
        target_width: u32,
        #[arg(long, default_value_t = 130)]
        target_height: u32,
        #[arg(long, default_value_t = 8)]
        max_baseline_drift_px: u32,
        #[arg(long)]
        json: bool,
    },
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
    /// Plan where Xiao Shu could dock near the focused Sway window.
    /// Read-only: never moves a window, pointer, or keyboard focus.
    FocusFollowPlan {
        /// Exact Sway app_id of the Avatar window.
        #[arg(long, default_value = ab_bridge::avatar_focus_follow::DEFAULT_AVATAR_APP_ID)]
        avatar_app_id: String,
        /// Gap between Xiao Shu and the focused window.
        #[arg(long, default_value_t = 24)]
        margin_px: i64,
        /// Maximum distance between proposed path points.
        #[arg(long, default_value_t = 48)]
        max_step_px: i64,
        /// Emit raw JSON instead of the human-readable summary.
        #[arg(long)]
        json: bool,
    },
    /// Recommend whether Xiao Shu should stay or make a reversible focus move.
    /// Read-only: never dispatches movement or writes observer state.
    FocusFollowRecommend {
        /// Last acknowledged focused Sway node id. Overrides the latest completed-action receipt.
        #[arg(long)]
        last_target_node_id: Option<i64>,
        /// Suppress movement recommendations below this distance.
        #[arg(long, default_value_t = 96)]
        min_travel_px: i64,
        /// Gap between Xiao Shu and the focused window.
        #[arg(long, default_value_t = 24)]
        margin_px: i64,
        /// Maximum distance between proposed path points.
        #[arg(long, default_value_t = 48)]
        max_step_px: i64,
        /// Emit raw JSON instead of the human-readable summary.
        #[arg(long)]
        json: bool,
    },
    /// Preview or explicitly show a passive Xiao Shu focus-move prompt.
    /// Never moves the Avatar; real movement remains a separate reversible action.
    FocusFollowPrompt {
        /// Last acknowledged focused Sway node id. Overrides the latest completed-action receipt.
        #[arg(long)]
        last_target_node_id: Option<i64>,
        /// Suppress movement recommendations below this distance.
        #[arg(long, default_value_t = 96)]
        min_travel_px: i64,
        /// Prompt cooldown after a successful display.
        #[arg(long, default_value_t = 300)]
        cooldown_secs: u64,
        /// Notification lifetime in milliseconds.
        #[arg(long, default_value_t = 8_000)]
        timeout_ms: u64,
        /// Display the prompt. Without this flag the command is read-only.
        #[arg(long)]
        show: bool,
        /// Legacy owner-confirmation provenance. Optional for reversible Avatar expression.
        #[arg(long, requires = "show")]
        confirm: bool,
        /// Emit raw JSON instead of the human-readable summary.
        #[arg(long)]
        json: bool,
    },
    /// Move Xiao Shu near the focused Sway window as a reversible embodied expression.
    /// Default is a dry-run; affects only the exact Avatar app_id and never the pointer.
    FocusFollowAction {
        /// Gap between Xiao Shu and the focused window.
        #[arg(long, default_value_t = 24)]
        margin_px: i64,
        /// Maximum distance between bounded movement steps.
        #[arg(long, default_value_t = 48)]
        max_step_px: i64,
        /// Maximum total movement on either axis.
        #[arg(long, default_value_t = 900)]
        max_travel_px: i64,
        /// Delay between movement steps.
        #[arg(long, default_value_t = 90)]
        step_interval_ms: u64,
        /// Optional marker file; creating it cancels before the next step.
        #[arg(long)]
        cancel_file: Option<PathBuf>,
        /// Request execution. Without this flag the command only previews.
        #[arg(long)]
        execute: bool,
        /// Legacy owner-confirmation provenance. Optional for reversible Avatar expression.
        #[arg(long, requires = "execute")]
        confirm: bool,
        /// Auditable expression reason; required with --execute.
        #[arg(long)]
        reason: Option<String>,
        /// Emit raw JSON instead of a human-readable summary.
        #[arg(long)]
        json: bool,
    },
    /// Observe stable focus transitions in one bounded foreground session.
    /// Default is preflight-only; --execute enables autonomous Avatar-only movement.
    FocusFollowObserve {
        /// Foreground observation lifetime in milliseconds (clamped to 1s..30m).
        #[arg(long, default_value_t = 1_800_000)]
        duration_ms: u64,
        /// Sway tree polling interval in milliseconds (clamped to 250..5000ms).
        #[arg(long, default_value_t = 1_000)]
        poll_ms: u64,
        /// Stable-focus dwell before a candidate can move (clamped to 500..30000ms).
        #[arg(long, default_value_t = 2_000)]
        dwell_ms: u64,
        /// Cooldown after any real movement attempt (clamped to 30..3600s).
        #[arg(long, default_value_t = 300)]
        cooldown_secs: u64,
        /// Base exponential backoff after a failed attempt (clamped to 5..900s).
        #[arg(long, default_value_t = 30)]
        failure_backoff_secs: u64,
        /// Suppress movement below this distance.
        #[arg(long, default_value_t = 96)]
        min_travel_px: i64,
        /// Maximum real attempts in one observer run (clamped to 1..3).
        #[arg(long, default_value_t = 3)]
        max_attempts: u64,
        /// Maximum total movement on either axis for each attempt.
        #[arg(long, default_value_t = 900)]
        max_travel_px: i64,
        /// Gap between Xiao Shu and the focused window.
        #[arg(long, default_value_t = 24)]
        margin_px: i64,
        /// Maximum distance between bounded movement steps.
        #[arg(long, default_value_t = 48)]
        max_step_px: i64,
        /// Delay between movement steps.
        #[arg(long, default_value_t = 90)]
        step_interval_ms: u64,
        /// Marker whose presence pauses observation and cancels an active traversal.
        #[arg(long)]
        pause_file: Option<PathBuf>,
        /// Additional exact structured app_id/XWayland class to suppress.
        #[arg(long = "deny-app-id")]
        deny_app_ids: Vec<String>,
        /// Start the bounded observer and let AB autonomously express stable focus.
        #[arg(long)]
        execute: bool,
        /// Emit raw privacy-safe JSON instead of a human-readable summary.
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
        /// Use a transparent XDG toplevel movable with the compositor's floating modifier.
        #[arg(long)]
        draggable: bool,
        /// Print the launch plan without opening the native surface.
        #[arg(long)]
        dry_run: bool,
        /// Emit raw JSON payload instead of a command line summary.
        #[arg(long)]
        json: bool,
    },
    /// Run the owner-local Linux embodiment loop: refresh one stable presence
    /// row while the native transparent renderer follows the pet sidecar.
    /// This foreground command emits no audio and controls no desktop input.
    LinuxLive {
        /// Stable project slug. Defaults to the cwd basename.
        #[arg(long)]
        project: Option<String>,
        /// Presence role for the live embodiment row.
        #[arg(long, default_value = "embodiment")]
        role: String,
        /// Pet sidecar id. Defaults to AB_PET_ID/current Codex avatar/xiao-shu-v2.
        #[arg(long)]
        pet_id: Option<String>,
        /// Stable presence session id. Defaults to com.agentbridge.avatar-live.<project>.
        #[arg(long)]
        session_id: Option<String>,
        /// Stable Agent Avatar Protocol agent_id. Defaults to the session id.
        #[arg(long)]
        agent_id: Option<String>,
        /// Runtime label projected into avatar_state.
        #[arg(long, default_value = "local-cli")]
        runtime: String,
        /// Working directory to project. Defaults to this process cwd.
        #[arg(long)]
        cwd: Option<PathBuf>,
        /// Foreground renderer lifetime in milliseconds (clamped to 1s..24h).
        #[arg(long, default_value_t = 1_800_000)]
        duration_ms: u64,
        /// Presence refresh interval in seconds (clamped to 5..300s).
        #[arg(long, default_value_t = 15)]
        heartbeat_interval_secs: u64,
        /// Pet sidecar polling interval in milliseconds (clamped to 100..5000ms).
        #[arg(long, default_value_t = ab_bridge::avatar_native::DEFAULT_NATIVE_STATE_POLL_MS)]
        state_poll_ms: u64,
        /// Explicitly enable sparse Qwen3-TTS feedback for eligible mode transitions.
        #[arg(long)]
        voice_feedback: bool,
        /// Explicit Qwen route: owner-local socket or authenticated LAN dispatcher.
        #[arg(long, default_value = ab_bridge::avatar_live_voice::DEFAULT_BACKEND,
              value_parser = ["qwen3", "qwen3-lan"])]
        voice_backend: String,
        /// Owner-only local Qwen3-TTS worker socket. Required for the qwen3 route.
        #[arg(long, env = "AB_QWEN3_TTS_WORKER_SOCKET")]
        qwen_worker: Option<PathBuf>,
        /// Python used to run the bounded audio adapter.
        #[arg(long, default_value = "python3")]
        voice_python: String,
        /// audio_embody.py override. Defaults to the deployed or repository adapter.
        #[arg(long)]
        voice_script: Option<PathBuf>,
        /// Qwen CustomVoice speaker name.
        #[arg(long, default_value = ab_bridge::avatar_live_voice::DEFAULT_VOICE)]
        voice_name: String,
        /// Fixed expression instruction sent to Qwen; spoken text remains template-only.
        #[arg(long, default_value = ab_bridge::avatar_live_voice::DEFAULT_INSTRUCT)]
        voice_instruct: String,
        /// Optional PipeWire/PulseAudio sink for voice playback.
        #[arg(long)]
        voice_sink: Option<String>,
        /// Global voice cooldown in seconds (clamped to 30..3600s).
        #[arg(long, default_value_t = ab_bridge::avatar_live_voice::DEFAULT_COOLDOWN_SECS)]
        voice_cooldown_secs: i64,
        /// Maximum successful utterances in one foreground session (clamped to 1..10).
        #[arg(long, default_value_t = ab_bridge::avatar_live_voice::DEFAULT_MAX_UTTERANCES)]
        voice_max_utterances: u64,
        /// Transparent surface width in pixels.
        #[arg(long, default_value_t = 360)]
        width: u32,
        /// Transparent surface height in pixels.
        #[arg(long, default_value_t = 520)]
        height: u32,
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
        /// Wayland output to place the avatar on. Omit for compositor default.
        #[arg(long)]
        output: Option<String>,
        /// Print the bounded plan without writing presence or opening Wayland.
        #[arg(long)]
        dry_run: bool,
        /// Emit JSON instead of a compact human summary.
        #[arg(long)]
        json: bool,
    },
    /// Observe one pet sidecar in a bounded foreground session and emit sparse
    /// voice without starting a renderer, writing presence, or modifying pet state.
    VoiceObserve {
        /// Pet sidecar id. Defaults to AB_PET_ID/current Codex avatar/xiao-shu-v2.
        #[arg(long)]
        pet_id: Option<String>,
        /// Stable Agent Avatar Protocol agent_id used by the audio receipt.
        #[arg(long)]
        agent_id: Option<String>,
        /// Foreground observation lifetime in milliseconds (clamped to 1s..24h).
        #[arg(long, default_value_t = 1_800_000)]
        duration_ms: u64,
        /// Pet sidecar polling interval in milliseconds (clamped to 100..5000ms).
        #[arg(long, default_value_t = ab_bridge::avatar_native::DEFAULT_NATIVE_STATE_POLL_MS)]
        state_poll_ms: u64,
        /// Explicit Qwen route: owner-local socket or authenticated LAN dispatcher.
        #[arg(long, default_value = ab_bridge::avatar_live_voice::DEFAULT_BACKEND,
              value_parser = ["qwen3", "qwen3-lan"])]
        voice_backend: String,
        /// Owner-only local Qwen3-TTS worker socket. Required for the qwen3 route.
        #[arg(long, env = "AB_QWEN3_TTS_WORKER_SOCKET")]
        qwen_worker: Option<PathBuf>,
        /// Python used to run the bounded audio adapter.
        #[arg(long, default_value = "python3")]
        voice_python: String,
        /// audio_embody.py override. Defaults to the deployed or repository adapter.
        #[arg(long)]
        voice_script: Option<PathBuf>,
        /// Qwen CustomVoice speaker name.
        #[arg(long, default_value = ab_bridge::avatar_live_voice::DEFAULT_VOICE)]
        voice_name: String,
        /// Fixed expression instruction sent to Qwen; spoken text remains template-only.
        #[arg(long, default_value = ab_bridge::avatar_live_voice::DEFAULT_INSTRUCT)]
        voice_instruct: String,
        /// Optional PipeWire/PulseAudio sink for voice playback.
        #[arg(long)]
        voice_sink: Option<String>,
        /// Global voice cooldown in seconds (clamped to 30..3600s).
        #[arg(long, default_value_t = ab_bridge::avatar_live_voice::DEFAULT_COOLDOWN_SECS)]
        voice_cooldown_secs: i64,
        /// Maximum successful utterances in one observer run (clamped to 1..10).
        #[arg(long, default_value_t = ab_bridge::avatar_live_voice::DEFAULT_MAX_UTTERANCES)]
        voice_max_utterances: u64,
        /// Print the bounded observer plan without polling or emitting audio.
        #[arg(long)]
        dry_run: bool,
        /// Emit JSON instead of a compact human summary.
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
        /// Compute the alert without writing alert state/events or emitting notification/TTS.
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
    /// **P2** — Nightly distillation draft queue (propose-only). Picks the
    /// top-N verified, still-undistilled mechanism rows (the same S1
    /// detector session_bootstrap surfaces), asks `claude -p` for a
    /// distill/merge/reject verdict + pub_* draft per candidate, and writes
    /// `distill_draft_*` review rows. NEVER writes pub_* rows itself —
    /// every draft goes through per-row agent review in the bootstrap
    /// "Distill drafts pending review" block (pilot ruling: the distiller
    /// has a measured permissive bias). Designed for cron (e.g.
    /// `30 4 * * *`); cost ≈ 62 s/candidate on the default model.
    Distill {
        /// Maximum candidates to draft this round.
        #[arg(long, default_value_t = 5)]
        top_n: usize,
        /// Inspect-only: print the picked queue but skip LLM + writes.
        #[arg(long)]
        dry_run: bool,
        /// Per-candidate `claude -p` timeout in seconds.
        #[arg(long, default_value_t = 600)]
        timeout_secs: u64,
    },
    /// **Consolidation middle** — Nightly digest-author draft queue
    /// (propose-only). Picks under-served synthesis topics (eval-fixture
    /// answer_vehicle gaps + telemetry NL miss clusters), asks `claude -p`
    /// to synthesize a citation-ledger `digest` draft from real source rows,
    /// and writes `digest_draft_*` review rows. NEVER writes live `digest`
    /// rows itself — promotion goes through the offline eval gate
    /// (`scripts/eval/digest_gate.py`) plus manual review. Designed for cron
    /// (e.g. `0 5 * * *`, after hygiene and distill). Kill switch:
    /// `AB_DIGEST_AUTHOR_DISABLE=1`. See docs/DESIGN-nightly-digest-author.md.
    Digest {
        /// Maximum topics to draft this round.
        #[arg(long, default_value_t = 3)]
        top_n: usize,
        /// Inspect-only: print the picked topics but skip LLM + writes.
        #[arg(long)]
        dry_run: bool,
        /// Per-topic `claude -p` timeout in seconds (digest prompts carry
        /// up to 12 full rows, so the envelope is larger than distill's).
        #[arg(long, default_value_t = 900)]
        timeout_secs: u64,
        /// Synthesis eval fixture driving T1 topic selection. An unreadable
        /// path skips T1 with a log line instead of failing the run.
        #[arg(long, default_value = "scripts/eval/fixtures/synthesis_queries.json")]
        fixtures: String,
        /// Telemetry lookback window (days) for T2 miss-cluster topics.
        #[arg(long, default_value_t = 14)]
        window_days: i64,
        /// Minimum miss count for a T2 topic.
        #[arg(long, default_value_t = 3)]
        min_miss_count: u64,
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
    /// self-evaluation candidates. **Never auto-edits AGENT.md** —
    /// integration still goes through `session_finalize(agent_profile=...)`
    /// and its drift cap.
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
    /// Wrap a static BioCortex capability ledger as a read-only report packet.
    ///
    /// This consumes an explicit line-oriented ledger file, emits the stable
    /// `agent_bridge.biocortex_capability_ledger.report_packet.v0` payload, and
    /// does not run BioCortex, mutate memory, register MCP tools, grant runtime
    /// authority, or affect retrieval order.
    CapabilityLedgerReportPacket {
        /// Line-oriented ledger file produced by capability_ledger_shadow_adapter.
        #[arg(long)]
        ledger: PathBuf,
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
        /// Optional JSON file produced by `retrieval-opt-in-runtime-readiness-packet --json`.
        #[arg(long = "runtime-readiness-packet-json")]
        runtime_readiness_packet_json: Option<PathBuf>,
        /// Optional JSON file produced by `retrieval-opt-in-runtime-transition-gate --json`.
        #[arg(long = "runtime-transition-gate-json")]
        runtime_transition_gate_json: Option<PathBuf>,
        /// Optional JSON file produced by `retrieval-opt-in-gated-store-trial --json`.
        #[arg(long = "gated-store-trial-json")]
        gated_store_trial_json: Option<PathBuf>,
        /// Optional JSON file produced by `retrieval-opt-in-gated-batch-diagnostics --json`.
        #[arg(long = "gated-batch-diagnostics-json")]
        gated_batch_diagnostics_json: Option<PathBuf>,
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
    /// artifact summary, optional redacted evidence aggregate, optional
    /// post-runtime evidence summary, and optional capability-ledger report
    /// packet. It requests a separate human review for explicit opt-in FTS
    /// runtime influence only; it does not approve runtime adapter influence,
    /// call `memory_search`, run BioCortex, or change retrieval order.
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
        /// Optional JSON file produced by the BioCortex capability-ledger report-packet consumer.
        #[arg(long = "capability-ledger-report-packet-json")]
        capability_ledger_report_packet_json: Option<PathBuf>,
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
    /// Build a read-only downstream AIO runtime-evidence handoff packet.
    ///
    /// This consumes the downstream checkpoint selection plus the
    /// post-semantic-diverse review, then emits only a redacted SSB/LSWR-ready
    /// handoff summary. It does not call `memory_search`, run BioCortex, call
    /// AiOT, execute LSWR actions, write approval, or alter default retrieval.
    RetrievalDownstreamAioRuntimeEvidenceHandoff {
        /// JSON file produced by the downstream AIO checkpoint selection slice.
        #[arg(long = "checkpoint-selection-json")]
        checkpoint_selection_json: PathBuf,
        /// JSON file produced by the post-semantic-diverse review slice.
        #[arg(long = "post-semantic-diverse-review-json")]
        post_semantic_diverse_review_json: PathBuf,
        /// Optional JSON file produced by controlled trial readiness summary.
        #[arg(long = "controlled-trial-readiness-json")]
        controlled_trial_readiness_json: Option<PathBuf>,
        /// Reviewer identity or handle.
        #[arg(long)]
        reviewer: Option<String>,
        /// Implementation commit under review.
        #[arg(long)]
        commit: Option<String>,
        /// Forum post id linking the handoff packet.
        #[arg(long)]
        forum_post_id: Option<String>,
        /// Memory key linking the handoff packet.
        #[arg(long)]
        memory_key: Option<String>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// Run the read-only LSWR interaction feedback consumption preflight.
    ///
    /// This consumes an explicit fixture or evidence packet JSON file. It does
    /// not query live LSWR state, register an MCP tool, access the store, write
    /// memory, or mutate world/runtime state.
    LswrInteractionFeedbackConsumptionPreflight {
        /// JSON file containing a fixture, evidence packet, or wrapper object.
        #[arg(long = "input-json")]
        input_json: PathBuf,
        /// Emit raw JSON instead of a compact text summary.
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
    /// Read-only Git health and history-footprint report for the sync repo.
    ///
    /// Does not contact remotes, run sync, garbage-collect, or rewrite history.
    Audit {
        /// Run a full object-content fsck. This can be slow on a large history.
        #[arg(long)]
        full: bool,
    },
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
        /// Refresh only this exact source id (for example `OpenBMB/MiniCPM`).
        #[arg(long)]
        src: Option<String>,
        /// Override the Git checkout ref for the selected source.
        #[arg(long)]
        r#ref: Option<String>,
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
    /// Compare current route candidates with reproducibly sourced candidates.
    /// This is read-only evidence and never changes routing policy.
    RouteAudit {
        /// Task description in natural language.
        query: String,
        /// Maximum candidates retained in each comparison.
        #[arg(long, default_value_t = 5)]
        limit: usize,
        /// Emit machine-readable JSON for automation.
        #[arg(long)]
        json: bool,
    },
    /// Evaluate the current router against the checked-in bilingual quality corpus.
    /// This is observation-only and never changes routing policy.
    RouteEval {
        /// Maximum routed Skills retained per query.
        #[arg(long, default_value_t = 3)]
        limit: usize,
        /// Emit machine-readable JSON for automation.
        #[arg(long)]
        json: bool,
    },
    /// Evaluate a fixed provenance corpus without changing runtime routing.
    RouteProvenanceEval {
        /// Optional JSON fixture overriding the embedded provenance corpus.
        #[arg(long)]
        fixture: Option<PathBuf>,
        /// Maximum candidates evaluated per query.
        #[arg(long, default_value_t = 3)]
        limit: usize,
        /// Emit machine-readable JSON for automation.
        #[arg(long)]
        json: bool,
    },
    /// Evaluate the independent provenance holdout gate without changing routing.
    RouteProvenanceGate {
        /// Maximum candidates evaluated per query.
        #[arg(long, default_value_t = 3)]
        limit: usize,
        /// Emit machine-readable JSON for automation.
        #[arg(long)]
        json: bool,
    },
    /// Show strict per-lane evidence behind a route decision.
    /// This is observation-only and never changes routing policy.
    RouteDiagnose {
        /// Task description to inspect.
        query: String,
        /// Maximum Skills retained per diagnostic lane.
        #[arg(long, default_value_t = 5)]
        limit: usize,
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
    /// Persist a reviewed source-level license/admission record. This never
    /// installs Skills, changes routing, or grants execution authority.
    Admit {
        /// Indexed source id, for example `anthropics/skills`.
        source: String,
        /// Reviewed SPDX identifier, for example `MIT` or `Apache-2.0`.
        #[arg(long)]
        spdx: String,
        /// Admission verdict: approved, quarantined, or review-required.
        #[arg(long, default_value = "approved")]
        verdict: String,
        /// Read-only evidence URL used for this review.
        #[arg(long)]
        evidence_url: Option<String>,
        /// Optional compact review note.
        #[arg(long)]
        note: Option<String>,
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
        /// Filter source evidence: verified (origin+commit), partial, or unknown.
        #[arg(long)]
        provenance: Option<String>,
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

const AVATAR_AURA_IO_STARTUP_ENV_KEYS: [&str; 4] = [
    "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE",
    "AGENT_BRIDGE_AVATAR_AURA_IO_ROOT",
    "AGENT_BRIDGE_AVATAR_AURA_IO_ENTRY",
    "HOME",
];

fn avatar_aura_io_startup_values_from_lookup<F>(
    mut lookup: F,
) -> Result<std::collections::BTreeMap<String, String>>
where
    F: FnMut(&str) -> Result<Option<String>>,
{
    let mut values = std::collections::BTreeMap::new();
    for key in AVATAR_AURA_IO_STARTUP_ENV_KEYS {
        if let Some(value) = lookup(key)? {
            values.insert(key.to_string(), value);
        }
    }
    Ok(values)
}

#[cfg(unix)]
fn restore_sigpipe_default() {
    // Rust ignores SIGPIPE by default, which converts a closed downstream pipe
    // into an EPIPE from println! and an avoidable CLI panic. Restore standard
    // Unix pipeline semantics before the runtime or any worker threads start.
    unsafe {
        libc::signal(libc::SIGPIPE, libc::SIG_DFL);
    }
}

fn main() -> Result<()> {
    // The delegated-cgroup supervisor must remain a single-threaded, raw
    // process until it has moved itself out of the scope root, enabled the
    // delegated controllers, and installed the workload pre-exec barrier.
    // Dispatch it before SIGPIPE is restored as well as before Tokio, clap,
    // credentials, logging, or any other AB subsystem: its private socket must
    // observe parent loss as EOF/EPIPE instead of dying from SIGPIPE.
    if let Some(result) = ab_agent::workload_cgroup::run_internal_supervisor_if_requested() {
        result?;
        return Ok(());
    }

    #[cfg(unix)]
    restore_sigpipe_default();

    // A sandbox launcher must run before this process creates the Tokio runtime,
    // loads bridge credentials, or starts worker threads. Successful launchers
    // `exec` the target and never return; malformed/unsupported requests fail
    // closed.
    if let Some(result) = ab_agent::sandbox::run_internal_launcher_if_requested() {
        result?;
        return Ok(());
    }

    // The synchronous Wasmtime WASI linker must run outside Tokio. Handle the
    // explicit, default-off component probe before constructing AB's async
    // runtime; otherwise WASI p2 attempts a nested block_on and panics.
    #[cfg(feature = "g14-wasi-component-runtime")]
    {
        let early_cmd = Cli::parse().cmd.unwrap_or(Cmd::Daemon {
            episode_observation: None,
        });
        match early_cmd {
            Cmd::G14WasiComponent { artifact, sha256 } => {
                let runtime = ab_bridge::g14_component_runtime::G14ComponentRuntime::new()?;
                let report = runtime.execute_typed_report(artifact, &sha256)?;
                println!(
                    "{{\"wall-epoch-seconds\":{},\"logical-nanoseconds\":{},\"quantum-nanoseconds\":{}}}",
                    report.wall_epoch_seconds,
                    report.logical_nanoseconds,
                    report.quantum_nanoseconds
                );
                return Ok(());
            }
            Cmd::G14WasiBusinessComponent {
                artifact,
                sha256,
                revision,
                entity_count,
                occupied_cells,
                transition_count,
            } => {
                let runtime = ab_bridge::g14_component_runtime::G14ComponentRuntime::new()?;
                let report = runtime.execute_business_transform(
                    artifact,
                    &sha256,
                    revision,
                    entity_count,
                    occupied_cells,
                    transition_count,
                )?;
                println!(
                    "{{\"revision\":{},\"entity-count\":{},\"occupied-cells\":{},\"transition-count\":{},\"occupancy-per-mille\":{},\"report-code\":{}}}",
                    report.revision,
                    report.entity_count,
                    report.occupied_cells,
                    report.transition_count,
                    report.occupancy_per_mille,
                    serde_json::to_string(&report.report_code)?
                );
                return Ok(());
            }
            _ => {}
        }
    }

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

/// Prepare the embedding backend for a one-shot Skills route/evaluation.
///
/// MCP installs the configured remote delegate and warms it during startup.
/// The short-lived CLI path bypasses that startup, which used to let its first
/// route query compare a temporary hash fallback against the real-model store.
/// Waiting here is intentionally limited to the two semantic Skills commands;
/// catalog/list/source operations stay lightweight.
async fn prepare_skills_semantic_route() -> Result<()> {
    match ab_bridge::remote_embed::install_if_configured() {
        ab_bridge::remote_embed::InstallOutcome::Installed(url) => {
            tracing::debug!(%url, "embedding delegation active for skills CLI");
        }
        ab_bridge::remote_embed::InstallOutcome::NotConfigured => {}
        ab_bridge::remote_embed::InstallOutcome::AlreadyInitialized => {
            tracing::debug!("embedding backend already initialized for skills CLI");
        }
    }

    // A delegated backend is immediately usable; local ONNX starts its model
    // on a background thread and needs a bounded readiness wait below.
    ab_store::vector::warmup();
    if ab_bridge::remote_embed::active_remote_url().is_some() {
        return Ok(());
    }

    let backend = ab_store::default_backend();
    let backend_name = backend.name().to_string();
    let expected_local_name = ab_store::vector::active_model_name();
    if backend_name != expected_local_name {
        if backend_name.to_ascii_lowercase().contains("hash") {
            bail!(
                "skills semantic routing requires a real embedding backend; active backend is \
                 {backend_name}. Unset AGENT_BRIDGE_EMBED_BACKEND=hash or configure \
                 AGENT_BRIDGE_EMBED_REMOTE_URL."
            );
        }
        // A non-ONNX custom backend (for example Seed) owns its own readiness.
        return Ok(());
    }

    let wait_ms = std::env::var("AGENT_BRIDGE_ONNX_COLD_ROUTE_WAIT_MS")
        .ok()
        .and_then(|raw| raw.parse::<u64>().ok())
        .unwrap_or(30_000)
        .min(120_000);
    let deadline = std::time::Instant::now() + std::time::Duration::from_millis(wait_ms);
    while ab_store::vector::local_model_ready().is_none() && std::time::Instant::now() < deadline {
        tokio::time::sleep(std::time::Duration::from_millis(250)).await;
    }

    match ab_store::vector::local_model_ready() {
        Some(true) => Ok(()),
        Some(false) => bail!(
            "skills semantic routing cannot use local model {backend_name}: initialization failed; \
             configure AGENT_BRIDGE_EMBED_REMOTE_URL or repair the local ONNX model cache"
        ),
        None => bail!(
            "skills semantic routing timed out waiting {wait_ms}ms for local model {backend_name}; \
             retry after it is warm or raise AGENT_BRIDGE_ONNX_COLD_ROUTE_WAIT_MS (max 120000)"
        ),
    }
}

/// Strict startup gate for the embedding dim-guard (Item A, 2026-06-26, #4282).
///
/// A class-1 *config-vs-store* dim mismatch means this process is configured for
/// a model whose vector dim differs from the store's dominant dim — so every
/// semantic query scores dim-mismatched `0.0` cosines and recall silently
/// degrades to recency-only (the 2026-06-25 stale-launchd bug). **Default-on**:
/// abort loudly instead of serving a silently-broken store.
/// `AGENT_BRIDGE_DIM_GUARD_STRICT=0` opts out (e.g. mid-migration when the store
/// is transiently mixed-dim — prefer finishing the reindex before restart). An
/// empty store never blocks. The detached, warn-only `embedding_dim_guard::spawn`
/// path still covers the silent-fallback / in-store-anomaly classes.
async fn dim_guard_strict_preflight(store: &Arc<dyn StateStore>) {
    if let Some(warning) = ab_bridge::embedding_dim_guard::preflight_class1(store).await {
        if ab_bridge::embedding_dim_guard::strict_class1_enabled(
            std::env::var("AGENT_BRIDGE_DIM_GUARD_STRICT")
                .ok()
                .as_deref(),
        ) {
            tracing::error!(target: "embedding_dim_guard", "STRICT ABORT: {warning}");
            eprintln!(
                "FATAL [embedding_dim_guard] {warning}\n  Refusing to start: \
                 AGENT_BRIDGE_DIM_GUARD_STRICT is on by default. Point the process at the model \
                 that matches the store (finish any reindex before restart), or set \
                 AGENT_BRIDGE_DIM_GUARD_STRICT=0 to bypass (semantic recall stays degraded)."
            );
            std::process::exit(78);
        }
    }
}

async fn real_main() -> Result<()> {
    let cli = Cli::parse();
    let cmd = cli.cmd.unwrap_or(Cmd::Daemon {
        episode_observation: None,
    });

    // The synthetic auth lab is intentionally isolated from every Agent-Bridge
    // backend. Handle it before loading the credential notebook, optional Seed
    // substrate, SQLite store, browser, terminal, or agent runtime.
    if let Cmd::McpHttpAuthLab { config } = &cmd {
        tracing_subscriber::registry()
            .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
            .with(tracing_subscriber::fmt::layer())
            .init();
        ab_mcp::http_auth_lab::serve_from_path(config.clone()).await?;
        return Ok(());
    }
    if let Cmd::McpHttpAuthCandidate { config } = &cmd {
        tracing_subscriber::registry()
            .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
            .with(tracing_subscriber::fmt::layer())
            .init();
        ab_mcp::http_auth_lab::serve_provider_from_path(config.clone()).await?;
        return Ok(());
    }

    // Resident Xiao Shu v0 deliberately runs before the general credential
    // notebook is loaded. The child receives Codex auth through CODEX_HOME,
    // but does not inherit AB's unrelated service tokens merely because the
    // parent CLI supports other integrations.
    if let Cmd::Resident { op } = &cmd {
        return match op {
            ResidentOp::RiskPreflight { codex_bin, json } => {
                let configured_bin = if codex_bin == Path::new("codex") {
                    std::env::var_os("AB_RESIDENT_CODEX_BIN")
                        .map(PathBuf::from)
                        .unwrap_or_else(|| codex_bin.clone())
                } else {
                    codex_bin.clone()
                };
                let report =
                    ab_bridge::resident_risk_policy::resident_risk_preflight(&configured_bin);
                if *json {
                    println!("{}", serde_json::to_string_pretty(&report)?);
                } else {
                    println!(
                        "{}",
                        ab_bridge::resident_risk_policy::render_resident_risk_preflight(&report)
                    );
                }
                Ok(())
            }
            ResidentOp::Cognition {
                event,
                event_id,
                cwd,
                model,
                reasoning_effort,
                timeout_secs,
                codex_bin,
                dry_run,
            } => {
                let mut options = ab_bridge::resident_cognition::ResidentCognitionOptions::new(
                    event.clone(),
                    cwd.clone(),
                );
                options.event_id = event_id.clone();
                options.model = model.clone();
                options.reasoning_effort = reasoning_effort.clone();
                options.timeout_secs = *timeout_secs;
                options.dry_run = *dry_run;
                // Keep the environment override selected by `new` when the
                // clap default remains untouched.
                if codex_bin != Path::new("codex") {
                    options.codex_bin = codex_bin.clone();
                }

                // Keep the irreversible-damage gate ahead of SQLite and the
                // Resident journal. The cognition module repeats this check so
                // direct library callers cannot bypass it.
                if !*dry_run {
                    ab_bridge::resident_risk_policy::require_owner_loss_tolerant_admission(
                        &options.codex_bin,
                    )
                    .map_err(anyhow::Error::msg)?;
                }

                let store = if *dry_run {
                    None
                } else {
                    let store: Arc<dyn StateStore> =
                        Arc::new(SqliteStore::open(&default_db_path()).await?);
                    Some(store)
                };
                let packet =
                    ab_bridge::resident_cognition::run_resident_cognition(options, store).await?;
                println!("{}", serde_json::to_string_pretty(&packet)?);
                Ok(())
            }
            ResidentOp::Evaluate {
                wake_id,
                label,
                dry_run,
            } => {
                let mut options =
                    ab_bridge::resident_owner_evaluation::ResidentOwnerEvaluationOptions::new(
                        wake_id.clone(),
                        (*label).into(),
                    );
                options.dry_run = *dry_run;
                let packet =
                    ab_bridge::resident_owner_evaluation::record_resident_owner_evaluation(
                        options,
                    )?;
                println!("{}", serde_json::to_string_pretty(&packet)?);
                Ok(())
            }
            ResidentOp::Shadow {
                basis_wake_id,
                trigger_kind,
                signal_sha256,
                evidence_sha256,
                evidence_status,
                observed_at_unix_ms,
                due_at_unix_ms,
                severity,
                foreground_state,
                evaluated_at_unix_ms,
                utc_offset_minutes,
                record,
            } => {
                let mut options =
                    ab_bridge::resident_m2_shadow::ResidentM2ShadowOptions::new(
                        basis_wake_id.clone(),
                        (*trigger_kind).into(),
                        signal_sha256.clone(),
                        evidence_sha256.clone(),
                        *observed_at_unix_ms,
                        *utc_offset_minutes,
                    );
                options.evidence_status = (*evidence_status).into();
                options.due_at_unix_ms = *due_at_unix_ms;
                options.severity = (*severity).into();
                options.foreground_state = (*foreground_state).into();
                if let Some(evaluated_at_unix_ms) = evaluated_at_unix_ms {
                    options.evaluated_at_unix_ms = *evaluated_at_unix_ms;
                }
                options.record = *record;
                let packet =
                    ab_bridge::resident_m2_shadow::evaluate_resident_m2_shadow(options)?;
                println!("{}", serde_json::to_string_pretty(&packet)?);
                Ok(())
            }
            ResidentOp::ShadowReview {
                natural_report_ids,
                mechanics_report_ids,
            } => {
                let mut options =
                    ab_bridge::resident_m2_shadow::ResidentM2ShadowReviewOptions::new();
                options.natural_report_ids = natural_report_ids.clone();
                options.mechanics_report_ids = mechanics_report_ids.clone();
                let packet =
                    ab_bridge::resident_m2_shadow::review_resident_m2_shadow(options)?;
                println!("{}", serde_json::to_string_pretty(&packet)?);
                Ok(())
            }
        };
    }

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
            Some(SyncOp::Audit { full }) => sync::run_audit(*full),
        };
    }

    // Operator requests are a local file-backed control plane. They do not
    // need the daemon Hub, and decisions never invoke an executor.
    if let Cmd::OperatorRequest { op } = &cmd {
        return cli::run_operator_request(op);
    }

    // A2UI P0 is deliberately read-only: parse and report before any Hub,
    // renderer, action dispatcher, browser, terminal, or agent runtime exists.
    if let Cmd::A2ui { op } = &cmd {
        return cli::run_a2ui(op);
    }

    // Skills subcommand: short-lived; no daemon hub needed.
    if let Cmd::Skills { op } = &cmd {
        if matches!(
            op,
            SkillsOp::Route { .. }
                | SkillsOp::RouteAudit { .. }
                | SkillsOp::RouteEval { .. }
                | SkillsOp::RouteProvenanceEval { .. }
                | SkillsOp::RouteProvenanceGate { .. }
                | SkillsOp::RouteDiagnose { .. }
        ) {
            prepare_skills_semantic_route().await?;
        }
        return match op {
            SkillsOp::Index { source, verbose } => {
                skills::run_index(source, *verbose).await.map(|_| ())
            }
            SkillsOp::Seed { verbose } => skills::run_seed(*verbose).await,
            SkillsOp::Refresh {
                verbose,
                src,
                r#ref,
                prune,
                dry_run,
                json,
            } => skills::run_refresh(
                    *verbose,
                    src.as_deref(),
                    r#ref.as_deref(),
                    *prune,
                    *dry_run,
                    *json,
                )
            .await,
            SkillsOp::Discover { limit, all } => skills::run_discover(*limit, *all).await,
            SkillsOp::Search { query, limit } => skills::run_search(query, *limit).await,
            SkillsOp::Route {
                query,
                limit,
                body_chars,
                json,
            } => skills::run_route(query, *limit, *body_chars, *json).await,
            SkillsOp::RouteAudit { query, limit, json } => {
                skills::run_route_audit(query, *limit, *json).await
            }
            SkillsOp::RouteEval { limit, json } => skills::run_route_eval(*limit, *json).await,
            SkillsOp::RouteProvenanceEval {
                fixture,
                limit,
                json,
            } => skills::run_route_provenance_eval(fixture.as_deref(), *limit, *json).await,
            SkillsOp::RouteProvenanceGate { limit, json } => {
                skills::run_route_provenance_gate(*limit, *json).await
            }
            SkillsOp::RouteDiagnose { query, limit, json } => {
                skills::run_route_diagnose(query, *limit, *json).await
            }
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
            SkillsOp::Admit {
                source,
                spdx,
                verdict,
                evidence_url,
                note,
            } => {
                skills::run_admit(
                    source,
                    spdx,
                    verdict,
                    evidence_url.as_deref(),
                    note.as_deref(),
                )
                .await
            }
            SkillsOp::Audit {
                json,
                src,
                risk,
                lint,
                vendor,
                provenance,
                limit,
            } => {
                skills::run_audit(
                    *json,
                    src.as_deref(),
                    risk,
                    lint.as_deref(),
                    vendor.as_deref(),
                    provenance.as_deref(),
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
        return run_browser_lite(op);
    }

    // Avatar subcommand: short-lived read-only terminal surface over presence rows.
    if let Cmd::Avatar { op } = &cmd {
        return match op {
            AvatarOp::SpriteAssetCompile {
                input,
                output,
                frame_count,
                cell_width,
                cell_height,
                padding_px,
                baseline_y,
                flip_horizontal,
                execute,
                confirm,
                json: as_json,
            } => run_avatar_sprite_asset_compile(
                input,
                output,
                *frame_count,
                *cell_width,
                *cell_height,
                *padding_px,
                *baseline_y,
                *flip_horizontal,
                *execute,
                *confirm,
                *as_json,
            ),
            AvatarOp::SpriteAssetContract {
                asset_root,
                json: as_json,
            } => run_avatar_sprite_asset_contract(asset_root, *as_json),
            AvatarOp::SpriteAssetAudit {
                path,
                columns,
                rows,
                cell_width,
                cell_height,
                frame_count,
                target_width,
                target_height,
                max_baseline_drift_px,
                json: as_json,
            } => run_avatar_sprite_asset_audit(
                path,
                *columns,
                *rows,
                *cell_width,
                *cell_height,
                *frame_count,
                *target_width,
                *target_height,
                *max_baseline_drift_px,
                *as_json,
            ),
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
            AvatarOp::FocusFollowPlan {
                avatar_app_id,
                margin_px,
                max_step_px,
                json: as_json,
            } => run_avatar_focus_follow_plan(
                avatar_app_id.clone(),
                *margin_px,
                *max_step_px,
                *as_json,
            )
            .await,
            AvatarOp::FocusFollowRecommend {
                last_target_node_id,
                min_travel_px,
                margin_px,
                max_step_px,
                json: as_json,
            } => run_avatar_focus_follow_recommend(
                *last_target_node_id,
                *min_travel_px,
                *margin_px,
                *max_step_px,
                *as_json,
            )
            .await,
            AvatarOp::FocusFollowPrompt {
                last_target_node_id,
                min_travel_px,
                cooldown_secs,
                timeout_ms,
                show,
                confirm,
                json: as_json,
            } => run_avatar_focus_follow_prompt(
                *last_target_node_id,
                *min_travel_px,
                *cooldown_secs,
                *timeout_ms,
                *show,
                *confirm,
                *as_json,
            )
            .await,
            AvatarOp::FocusFollowAction {
                margin_px,
                max_step_px,
                max_travel_px,
                step_interval_ms,
                cancel_file,
                execute,
                confirm,
                reason,
                json: as_json,
            } => run_avatar_focus_follow_action(
                *margin_px,
                *max_step_px,
                *max_travel_px,
                *step_interval_ms,
                cancel_file.as_deref(),
                *execute,
                *confirm,
                reason.as_deref(),
                *as_json,
            )
            .await,
            AvatarOp::FocusFollowObserve {
                duration_ms,
                poll_ms,
                dwell_ms,
                cooldown_secs,
                failure_backoff_secs,
                min_travel_px,
                max_attempts,
                max_travel_px,
                margin_px,
                max_step_px,
                step_interval_ms,
                pause_file,
                deny_app_ids,
                execute,
                json: as_json,
            } => {
                run_avatar_focus_follow_observe(
                    *duration_ms,
                    *poll_ms,
                    *dwell_ms,
                    *cooldown_secs,
                    *failure_backoff_secs,
                    *min_travel_px,
                    *max_attempts,
                    *max_travel_px,
                    *margin_px,
                    *max_step_px,
                    *step_interval_ms,
                    pause_file.clone(),
                    deny_app_ids.clone(),
                    *execute,
                    *as_json,
                )
                .await
            }
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
                draggable,
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
                    *draggable,
                    *dry_run,
                    *as_json,
                )
                .await
            }
            AvatarOp::LinuxLive {
                project,
                role,
                pet_id,
                session_id,
                agent_id,
                runtime,
                cwd,
                duration_ms,
                heartbeat_interval_secs,
                state_poll_ms,
                voice_feedback,
                voice_backend,
                qwen_worker,
                voice_python,
                voice_script,
                voice_name,
                voice_instruct,
                voice_sink,
                voice_cooldown_secs,
                voice_max_utterances,
                width,
                height,
                anchor,
                margin_top,
                margin_right,
                margin_bottom,
                margin_left,
                output,
                dry_run,
                json: as_json,
            } => {
                run_avatar_linux_live(
                    project.clone(),
                    role.clone(),
                    pet_id.clone(),
                    session_id.clone(),
                    agent_id.clone(),
                    runtime.clone(),
                    cwd.clone(),
                    *duration_ms,
                    *heartbeat_interval_secs,
                    *state_poll_ms,
                    *voice_feedback,
                    voice_backend.clone(),
                    qwen_worker.clone(),
                    voice_python.clone(),
                    voice_script.clone(),
                    voice_name.clone(),
                    voice_instruct.clone(),
                    voice_sink.clone(),
                    *voice_cooldown_secs,
                    *voice_max_utterances,
                    *width,
                    *height,
                    anchor.clone(),
                    *margin_top,
                    *margin_right,
                    *margin_bottom,
                    *margin_left,
                    output.clone(),
                    *dry_run,
                    *as_json,
                )
                .await
            }
            AvatarOp::VoiceObserve {
                pet_id,
                agent_id,
                duration_ms,
                state_poll_ms,
                voice_backend,
                qwen_worker,
                voice_python,
                voice_script,
                voice_name,
                voice_instruct,
                voice_sink,
                voice_cooldown_secs,
                voice_max_utterances,
                dry_run,
                json: as_json,
            } => {
                run_avatar_voice_observe(
                    pet_id.clone(),
                    agent_id.clone(),
                    *duration_ms,
                    *state_poll_ms,
                    voice_backend.clone(),
                    qwen_worker.clone(),
                    voice_python.clone(),
                    voice_script.clone(),
                    voice_name.clone(),
                    voice_instruct.clone(),
                    voice_sink.clone(),
                    *voice_cooldown_secs,
                    *voice_max_utterances,
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

    // Substrate executes before shared store and Hub construction.
    if let Cmd::Substrate { op } = &cmd {
        return run_substrate(op).await;
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
            BioCortexOp::CapabilityLedgerReportPacket { ledger, json } => {
                run_biocortex_capability_ledger_report_packet(ledger, *json).await
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
                runtime_readiness_packet_json,
                runtime_transition_gate_json,
                gated_store_trial_json,
                gated_batch_diagnostics_json,
                json,
            } => {
                let runtime_readiness_packet = read_optional_json_file(
                    runtime_readiness_packet_json.as_deref(),
                    "runtime readiness packet",
                )?;
                let runtime_transition_gate = read_optional_json_file(
                    runtime_transition_gate_json.as_deref(),
                    "runtime transition gate",
                )?;
                let gated_store_trial = read_optional_json_file(
                    gated_store_trial_json.as_deref(),
                    "gated store trial",
                )?;
                let gated_batch_diagnostics = read_optional_json_file(
                    gated_batch_diagnostics_json.as_deref(),
                    "gated batch diagnostics",
                )?;
                run_biocortex_retrieval_opt_in_status(
                    BioCortexRetrievalOptInAuditOptions {
                        mode: mode.clone(),
                        per_call_opt_in: *per_call_opt_in,
                        query: query.clone(),
                        baseline_keys: baseline_keys.clone(),
                        side_signal_status: side_signal_status.clone(),
                        fallback_reason: fallback_reason.clone(),
                        latency_ms: *latency_ms,
                        runtime_readiness_packet,
                        runtime_transition_gate,
                        gated_store_trial,
                        gated_batch_diagnostics,
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
                let body = std::fs::read_to_string(dry_run_json)
                    .map_err(|e| anyhow::anyhow!("read dry-run JSON at {dry_run_json:?}: {e}"))?;
                let dry_run_plan = serde_json::from_str(&body)
                    .map_err(|e| anyhow::anyhow!("parse dry-run JSON at {dry_run_json:?}: {e}"))?;
                run_biocortex_retrieval_opt_in_review_packet(
                    BioCortexRetrievalOptInReviewPacketOptions {
                        dry_run_plan,
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
                let body = std::fs::read_to_string(review_packet_json).map_err(|e| {
                    anyhow::anyhow!("read review-packet JSON at {review_packet_json:?}: {e}")
                })?;
                let review_packet = serde_json::from_str(&body).map_err(|e| {
                    anyhow::anyhow!("parse review-packet JSON at {review_packet_json:?}: {e}")
                })?;
                run_biocortex_retrieval_opt_in_execution_packet(
                    BioCortexRetrievalOptInExecutionPacketOptions {
                        review_packet,
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
                let body = std::fs::read_to_string(runtime_trial_json).map_err(|e| {
                    anyhow::anyhow!("read runtime-trial JSON at {runtime_trial_json:?}: {e}")
                })?;
                let runtime_trial = serde_json::from_str(&body).map_err(|e| {
                    anyhow::anyhow!("parse runtime-trial JSON at {runtime_trial_json:?}: {e}")
                })?;
                run_biocortex_retrieval_opt_in_runtime_trial_review_packet(
                    BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions {
                        runtime_trial,
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
                let body = std::fs::read_to_string(source_json).map_err(|e| {
                    anyhow::anyhow!("read order-diff source JSON at {source_json:?}: {e}")
                })?;
                let source_packet = serde_json::from_str(&body).map_err(|e| {
                    anyhow::anyhow!("parse order-diff source JSON at {source_json:?}: {e}")
                })?;
                run_biocortex_retrieval_opt_in_order_diff_packet(
                    BioCortexRetrievalOptInOrderDiffPacketOptions {
                        source_packet,
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
                let body = std::fs::read_to_string(source_json).map_err(|e| {
                    anyhow::anyhow!(
                        "read redacted-order artifact source JSON at {source_json:?}: {e}"
                    )
                })?;
                let source_packet = serde_json::from_str(&body).map_err(|e| {
                    anyhow::anyhow!(
                        "parse redacted-order artifact source JSON at {source_json:?}: {e}"
                    )
                })?;
                run_biocortex_retrieval_opt_in_redacted_order_artifact(
                    BioCortexRetrievalOptInRedactedOrderArtifactOptions {
                        source_packet,
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
                let request_body =
                    std::fs::read_to_string(authorization_request_json).map_err(|e| {
                        anyhow::anyhow!(
                            "read opt-in authorization request JSON at {authorization_request_json:?}: {e}"
                        )
                    })?;
                let authorization_request =
                    serde_json::from_str(&request_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse opt-in authorization request JSON at {authorization_request_json:?}: {e}"
                        )
                    })?;
                let decision_body =
                    std::fs::read_to_string(authorization_decision_json).map_err(|e| {
                        anyhow::anyhow!(
                            "read opt-in authorization decision JSON at {authorization_decision_json:?}: {e}"
                        )
                    })?;
                let authorization_decision =
                    serde_json::from_str(&decision_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse opt-in authorization decision JSON at {authorization_decision_json:?}: {e}"
                        )
                    })?;
                run_biocortex_retrieval_opt_in_authorization_decision_packet(
                    BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                        authorization_decision,
                        authorization_request,
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
                let packet_body = std::fs::read_to_string(authorization_decision_packet_json)
                    .map_err(|e| {
                        anyhow::anyhow!(
                            "read opt-in authorization decision packet JSON at {authorization_decision_packet_json:?}: {e}"
                        )
                    })?;
                let authorization_decision_packet =
                    serde_json::from_str(&packet_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse opt-in authorization decision packet JSON at {authorization_decision_packet_json:?}: {e}"
                        )
                    })?;
                let plan_body = std::fs::read_to_string(opt_in_plan_json).map_err(|e| {
                    anyhow::anyhow!("read opt-in experiment plan JSON at {opt_in_plan_json:?}: {e}")
                })?;
                let opt_in_plan = serde_json::from_str(&plan_body).map_err(|e| {
                    anyhow::anyhow!(
                        "parse opt-in experiment plan JSON at {opt_in_plan_json:?}: {e}"
                    )
                })?;
                run_biocortex_retrieval_opt_in_post_implementation_review_gate(
                    BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                        authorization_decision_packet,
                        opt_in_plan,
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
                capability_ledger_report_packet_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => {
                let gate_body =
                    std::fs::read_to_string(post_implementation_review_gate_json).map_err(|e| {
                        anyhow::anyhow!(
                            "read opt-in post-implementation review gate JSON at {post_implementation_review_gate_json:?}: {e}"
                        )
                    })?;
                let post_implementation_review_gate =
                    serde_json::from_str(&gate_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse opt-in post-implementation review gate JSON at {post_implementation_review_gate_json:?}: {e}"
                        )
                    })?;
                let artifact_body =
                    std::fs::read_to_string(redacted_order_artifact_json).map_err(|e| {
                        anyhow::anyhow!(
                            "read opt-in redacted order artifact JSON at {redacted_order_artifact_json:?}: {e}"
                        )
                    })?;
                let redacted_order_artifact =
                    serde_json::from_str(&artifact_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse opt-in redacted order artifact JSON at {redacted_order_artifact_json:?}: {e}"
                        )
                    })?;
                let redacted_evidence_aggregate = if let Some(redacted_evidence_aggregate_json) =
                    redacted_evidence_aggregate_json.as_deref()
                {
                    let aggregate_body =
                            std::fs::read_to_string(redacted_evidence_aggregate_json).map_err(
                                |e| {
                                    anyhow::anyhow!(
                                        "read opt-in redacted evidence aggregate JSON at {redacted_evidence_aggregate_json:?}: {e}"
                                    )
                                },
                            )?;
                    Some(serde_json::from_str(&aggregate_body).map_err(|e| {
                            anyhow::anyhow!(
                                "parse opt-in redacted evidence aggregate JSON at {redacted_evidence_aggregate_json:?}: {e}"
                            )
                        })?)
                } else {
                    None
                };
                let evidence_summary = if let Some(evidence_summary_json) =
                    evidence_summary_json.as_deref()
                {
                    let evidence_body =
                            std::fs::read_to_string(evidence_summary_json).map_err(|e| {
                                anyhow::anyhow!(
                                    "read opt-in evidence summary JSON at {evidence_summary_json:?}: {e}"
                                )
                            })?;
                    Some(serde_json::from_str(&evidence_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse opt-in evidence summary JSON at {evidence_summary_json:?}: {e}"
                        )
                    })?)
                } else {
                    None
                };
                let capability_ledger_report_packet = if let Some(
                    capability_ledger_report_packet_json,
                ) =
                    capability_ledger_report_packet_json.as_deref()
                {
                    let ledger_body =
                        std::fs::read_to_string(capability_ledger_report_packet_json).map_err(
                            |e| {
                                anyhow::anyhow!(
                                    "read BioCortex capability ledger report packet JSON at {capability_ledger_report_packet_json:?}: {e}"
                                )
                            },
                        )?;
                    Some(serde_json::from_str(&ledger_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse BioCortex capability ledger report packet JSON at {capability_ledger_report_packet_json:?}: {e}"
                        )
                    })?)
                } else {
                    None
                };
                run_biocortex_retrieval_opt_in_runtime_influence_review_request(
                    BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                        post_implementation_review_gate,
                        redacted_order_artifact,
                        redacted_evidence_aggregate,
                        evidence_summary,
                        capability_ledger_report_packet,
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
                let request_body =
                    std::fs::read_to_string(runtime_influence_review_request_json).map_err(|e| {
                        anyhow::anyhow!(
                            "read opt-in runtime influence review request JSON at {runtime_influence_review_request_json:?}: {e}"
                        )
                    })?;
                let runtime_influence_review_request =
                    serde_json::from_str(&request_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse opt-in runtime influence review request JSON at {runtime_influence_review_request_json:?}: {e}"
                        )
                    })?;
                let decision_body =
                    std::fs::read_to_string(runtime_influence_decision_json).map_err(|e| {
                        anyhow::anyhow!(
                            "read opt-in runtime influence decision JSON at {runtime_influence_decision_json:?}: {e}"
                        )
                    })?;
                let runtime_influence_decision =
                    serde_json::from_str(&decision_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse opt-in runtime influence decision JSON at {runtime_influence_decision_json:?}: {e}"
                        )
                    })?;
                run_biocortex_retrieval_opt_in_runtime_influence_decision_packet(
                    BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                        runtime_influence_review_request,
                        runtime_influence_decision,
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
            } => {
                let decision_body =
                    std::fs::read_to_string(runtime_influence_decision_packet_json).map_err(
                        |e| {
                            anyhow::anyhow!(
                                "read opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
                            )
                        },
                    )?;
                let runtime_influence_decision_packet =
                    serde_json::from_str(&decision_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}: {e}"
                        )
                    })?;
                let store_body = std::fs::read_to_string(store_trial_json).map_err(|e| {
                    anyhow::anyhow!("read opt-in store trial JSON at {store_trial_json:?}: {e}")
                })?;
                let store_trial = serde_json::from_str(&store_body).map_err(|e| {
                    anyhow::anyhow!("parse opt-in store trial JSON at {store_trial_json:?}: {e}")
                })?;
                let batch_body = std::fs::read_to_string(batch_diagnostics_json).map_err(|e| {
                    anyhow::anyhow!(
                        "read opt-in batch diagnostics JSON at {batch_diagnostics_json:?}: {e}"
                    )
                })?;
                let batch_diagnostics = serde_json::from_str(&batch_body).map_err(|e| {
                    anyhow::anyhow!(
                        "parse opt-in batch diagnostics JSON at {batch_diagnostics_json:?}: {e}"
                    )
                })?;
                run_biocortex_retrieval_opt_in_runtime_readiness_packet(
                    BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                        runtime_influence_decision_packet,
                        store_trial,
                        batch_diagnostics,
                        reviewer: reviewer.clone(),
                        commit: commit.clone(),
                        forum_post_id: forum_post_id.clone(),
                        memory_key: memory_key.clone(),
                    },
                    *json,
                )
            }
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
            } => {
                let readiness_body =
                    std::fs::read_to_string(runtime_readiness_packet_json).map_err(|e| {
                        anyhow::anyhow!(
                            "read opt-in runtime readiness packet JSON at {runtime_readiness_packet_json:?}: {e}"
                        )
                    })?;
                let runtime_readiness_packet =
                    serde_json::from_str(&readiness_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse opt-in runtime readiness packet JSON at {runtime_readiness_packet_json:?}: {e}"
                        )
                    })?;
                run_biocortex_retrieval_opt_in_runtime_transition_gate(
                    BioCortexRetrievalOptInRuntimeTransitionGateOptions {
                        runtime_readiness_packet,
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
                )
            }
            BioCortexOp::RetrievalDownstreamAioRuntimeEvidenceHandoff {
                checkpoint_selection_json,
                post_semantic_diverse_review_json,
                controlled_trial_readiness_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => {
                let checkpoint_body =
                    std::fs::read_to_string(checkpoint_selection_json).map_err(|e| {
                        anyhow::anyhow!(
                            "read downstream AIO checkpoint selection JSON at {checkpoint_selection_json:?}: {e}"
                        )
                    })?;
                let checkpoint_selection =
                    serde_json::from_str(&checkpoint_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse downstream AIO checkpoint selection JSON at {checkpoint_selection_json:?}: {e}"
                        )
                    })?;
                let review_body =
                    std::fs::read_to_string(post_semantic_diverse_review_json).map_err(|e| {
                        anyhow::anyhow!(
                            "read post-semantic-diverse review JSON at {post_semantic_diverse_review_json:?}: {e}"
                        )
                    })?;
                let post_semantic_diverse_review =
                    serde_json::from_str(&review_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse post-semantic-diverse review JSON at {post_semantic_diverse_review_json:?}: {e}"
                        )
                    })?;
                let controlled_trial_readiness = if let Some(controlled_trial_readiness_json) =
                    controlled_trial_readiness_json.as_deref()
                {
                    let controlled_body = std::fs::read_to_string(
                        controlled_trial_readiness_json,
                    )
                    .map_err(|e| {
                        anyhow::anyhow!(
                            "read controlled trial readiness JSON at {controlled_trial_readiness_json:?}: {e}"
                        )
                    })?;
                    Some(serde_json::from_str(&controlled_body).map_err(|e| {
                        anyhow::anyhow!(
                            "parse controlled trial readiness JSON at {controlled_trial_readiness_json:?}: {e}"
                        )
                    })?)
                } else {
                    None
                };
                run_biocortex_retrieval_downstream_aio_runtime_evidence_handoff(
                    BioCortexRetrievalDownstreamAioRuntimeEvidenceHandoffOptions {
                        checkpoint_selection,
                        post_semantic_diverse_review,
                        controlled_trial_readiness,
                        reviewer: reviewer.clone(),
                        commit: commit.clone(),
                        forum_post_id: forum_post_id.clone(),
                        memory_key: memory_key.clone(),
                    },
                    *json,
                )
            }
            BioCortexOp::LswrInteractionFeedbackConsumptionPreflight { input_json, json } => {
                let body = std::fs::read_to_string(input_json).map_err(|e| {
                    anyhow::anyhow!(
                        "read LSWR interaction feedback input JSON at {input_json:?}: {e}"
                    )
                })?;
                let input = serde_json::from_str(&body).map_err(|e| {
                    anyhow::anyhow!(
                        "parse LSWR interaction feedback input JSON at {input_json:?}: {e}"
                    )
                })?;
                run_lswr_interaction_feedback_consumption_preflight(input, *json)
            }
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
            } => {
                let payload = build_biocortex_retrieval_opt_in_evidence_summary(
                    batch_diagnostics_json,
                    controlled_order_fixture_run_json,
                    runtime_readiness_packet_json.as_deref(),
                    reviewer.clone(),
                    commit.clone(),
                    forum_post_id.clone(),
                    memory_key.clone(),
                )?;
                run_biocortex_retrieval_opt_in_evidence_summary(payload, *json)
            }
            BioCortexOp::RetrievalOptInRedactedEvidenceAggregate {
                movement_fixture_run_json,
                coverage_fixture_run_json,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
                json,
            } => {
                let payload = build_biocortex_retrieval_opt_in_redacted_evidence_aggregate(
                    movement_fixture_run_json,
                    coverage_fixture_run_json,
                    reviewer.clone(),
                    commit.clone(),
                    forum_post_id.clone(),
                    memory_key.clone(),
                )?;
                run_biocortex_retrieval_opt_in_redacted_evidence_aggregate(payload, *json)
            }
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
            DreamOp::Distill {
                top_n,
                dry_run,
                timeout_secs,
            } => ab_bridge::dream_distill::run(*top_n, *dry_run, *timeout_secs).await,
            DreamOp::Digest {
                top_n,
                dry_run,
                timeout_secs,
                fixtures,
                window_days,
                min_miss_count,
            } => {
                ab_bridge::dream_digest::run(ab_bridge::dream_digest::DigestRunOpts {
                    top_n: *top_n,
                    dry_run: *dry_run,
                    timeout_secs: *timeout_secs,
                    fixtures: fixtures.clone(),
                    window_days: *window_days,
                    min_miss_count: *min_miss_count,
                })
                .await
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
            } => {
                // #110 Fix B: stamp the hygiene marker so the C3 S2-S4 drop
                // detector suppresses the benign shed this run will cause.
                let r = run_dream_decay_unused(*window_days, *step, *floor, *json).await;
                if r.is_ok() {
                    ab_bridge::c3_self_check::stamp_hygiene_run();
                }
                r
            }
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
            } => {
                let r = run_dream_prune_coact_noise(*max_count, *older_than_days, *dry_run, *json)
                    .await;
                // #110 Fix B: a real edge prune drops S4; mark hygiene so C3
                // doesn't read it as edge loss. Dry-run changes nothing → skip.
                if r.is_ok() && !*dry_run {
                    ab_bridge::c3_self_check::stamp_hygiene_run();
                }
                r
            }
            DreamOp::PruneDegenerateRelates {
                blacklist_tags,
                dry_run,
                json,
            } => {
                let r = run_dream_prune_degenerate_relates(blacklist_tags, *dry_run, *json).await;
                // #110 Fix B: degenerate-relates prune drops S4 edges.
                if r.is_ok() && !*dry_run {
                    ab_bridge::c3_self_check::stamp_hygiene_run();
                }
                r
            }
            DreamOp::ArchiveOrphanStubs {
                blacklist_tags,
                older_than_days,
                max_archive,
                alarm_threshold,
                dry_run,
                json,
            } => {
                let r = run_dream_archive_orphan_stubs(
                    blacklist_tags,
                    *older_than_days,
                    *max_archive,
                    *alarm_threshold,
                    *dry_run,
                    *json,
                )
                .await;
                // #110 Fix B: archive-orphan-stubs moves active→archived (the
                // exact S2 drop in the #110 window). Mark hygiene so the
                // detector treats it as benign even past Fix A's credit.
                if r.is_ok() && !*dry_run {
                    ab_bridge::c3_self_check::stamp_hygiene_run();
                }
                r
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
        print!("{}", cli::shell_init_snippet(*shell));
        return Ok(());
    }

    // Walkthrough: render an evidence-anchored doc JSON into a present-gallery
    // artifact. Pure file IO (no daemon / no Hub) — the daily-wire mechanism for
    // present::write_walkthrough_artifact, invoked by the `/walkthrough` skill.
    if let Cmd::Walkthrough { doc, title, json } = &cmd {
        return run_walkthrough(doc, title.as_deref(), *json);
    }

    // Deployment self-check — pure file/process inspection, no Hub.
    if let Cmd::Doctor { json, markdown } = &cmd {
        return doctor::run_doctor(*json, *markdown).await;
    }

    // Instinct observer maintenance — pure local sidecar file operation.
    if let Cmd::Instinct { op } = &cmd {
        return match op {
            InstinctOp::Candidates { limit, json } => {
                let preview = instinct::observer_candidate_preview(*limit);
                cli::instinct_presentation::render_candidates(&preview, *json)
            }
            InstinctOp::ReviewPacket {
                limit,
                reviewer,
                out_dir,
                write,
                json,
            } => {
                let packet = instinct::observer_review_packet(
                    *limit,
                    reviewer.as_deref(),
                    out_dir.as_deref(),
                    *write,
                )
                .context("build instinct observer review packet")?;
                cli::instinct_presentation::render_review_packet(&packet, *json)
            }
            InstinctOp::ReviewDecision {
                packet_json,
                candidate_id,
                decision,
                reviewer,
                note,
                out,
                write,
                json,
            } => {
                let record = instinct::observer_review_decision(
                    packet_json,
                    candidate_id,
                    decision.as_str(),
                    reviewer.as_deref(),
                    note.as_deref(),
                    out.as_deref(),
                    *write,
                )
                .context("record instinct observer review decision")?;
                cli::instinct_presentation::render_review_decision(&record, *json)
            }
            InstinctOp::MemoryPreflight {
                packet_json,
                candidate_id,
                decisions,
                memory_key,
                memory_kind,
                memory_body,
                out_dir,
                write,
                json,
            } => {
                let packet = instinct::observer_memory_preflight(
                    packet_json,
                    decisions.as_deref(),
                    candidate_id,
                    memory_key.as_deref(),
                    memory_kind.as_deref(),
                    memory_body.as_deref(),
                    out_dir.as_deref(),
                    *write,
                )
                .context("build instinct observer memory write preflight")?;
                cli::instinct_presentation::render_memory_preflight(&packet, *json)
            }
            InstinctOp::MemoryWrite {
                preflight_json,
                db_path,
                receipt_out,
                write,
                json,
            } => {
                let mut plan = instinct::observer_memory_write_plan(preflight_json, *write)
                    .context("build instinct observer memory write plan")?;
                if *write {
                    if !plan
                        .get("writes_memory")
                        .and_then(|v| v.as_bool())
                        .unwrap_or(false)
                    {
                        anyhow::bail!(
                            "memory write blocked: {}",
                            plan.get("blocked_reasons").unwrap_or(&Value::Null)
                        );
                    }
                    let record = plan.get("memory_record").cloned().unwrap_or(Value::Null);
                    let mem = memory_record_from_instinct_plan(&record)
                        .context("build memory record from instinct preflight")?;
                    let path = db_path.clone().unwrap_or_else(default_db_path);
                    let store = SqliteStore::open(&path)
                        .await
                        .map_err(|e| anyhow::anyhow!("open state db at {path:?}: {e}"))?;
                    store
                        .memory_save(&mem)
                        .await
                        .map_err(|e| anyhow::anyhow!("instinct memory_save: {e}"))?;
                    let receipt = instinct::observer_memory_write_receipt(
                        preflight_json,
                        &mem.key,
                        &path,
                        receipt_out.as_deref(),
                    )
                    .context("record instinct memory write receipt")?;
                    plan["status"] = json!("saved");
                    plan["saved_memory_key"] = json!(mem.key);
                    plan["db_path"] = json!(path.display().to_string());
                    plan["receipt"] = receipt;
                } else {
                    plan["saved_memory_key"] = Value::Null;
                    plan["db_path"] = json!(db_path
                        .clone()
                        .unwrap_or_else(default_db_path)
                        .display()
                        .to_string());
                    plan["receipt"] = Value::Null;
                }
                cli::instinct_presentation::render_memory_write(&plan, *write, *json)
            }
            InstinctOp::ReviewStatus {
                review_dir,
                decisions,
                receipts,
                limit,
                json,
            } => {
                let status = instinct::observer_review_status(
                    review_dir.as_deref(),
                    decisions.as_deref(),
                    receipts.as_deref(),
                    *limit,
                )
                .context("read instinct observer review status")?;
                cli::instinct_presentation::render_review_status(&status, *json)
            }
            InstinctOp::ReviewInbox {
                packet_json,
                review_dir,
                decisions,
                limit,
                json,
            } => {
                let inbox = instinct::observer_review_inbox(
                    packet_json.as_deref(),
                    review_dir.as_deref(),
                    decisions.as_deref(),
                    *limit,
                )
                .context("read instinct observer review inbox")?;
                cli::instinct_presentation::render_review_inbox(&inbox, *limit, *json)
            }
            InstinctOp::ReviewContext {
                packet_json,
                candidate_id,
                log,
                include_local_excerpt,
                json,
            } => {
                let context = instinct::observer_review_context(
                    packet_json,
                    candidate_id,
                    log.as_deref(),
                    *include_local_excerpt,
                )
                .context("read instinct observer review context")?;
                cli::instinct_presentation::render_review_context(
                    &context,
                    *include_local_excerpt,
                    *json,
                )
            }
            InstinctOp::RotateLog { dry_run, json } => {
                let plan = instinct::rotate_observer_log(*dry_run)
                    .context("rotate instinct observer log")?;
                cli::instinct_presentation::render_rotate_log(&plan, *json)
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

    // Standing continuity U report: opens the store read-only, no Hub/daemon.
    if let Cmd::ContinuityReport { json } = &cmd {
        return run_continuity_report(*json).await;
    }

    // Workflow feedback report: opens the store read-only, no Hub/daemon.
    if let Cmd::WorkflowFeedbackReport {
        window_secs,
        top_tools,
        json,
    } = &cmd
    {
        return run_workflow_feedback_report(*json, *window_secs, *top_tools).await;
    }

    if let Cmd::WorkflowFeedbackShadowScore {
        fixtures,
        scenarios,
        json,
    } = &cmd
    {
        return run_workflow_feedback_shadow_score(fixtures, scenarios, *json);
    }

    if let Cmd::WorkflowFeedbackPromotionGate {
        shadow_scores,
        owner_approval_refs,
        rollback_refs,
        behavior_lift_refs,
        min_shadow_reports,
        min_scenarios,
        min_strong_scenarios,
        min_top_shadow_score,
        json,
    } = &cmd
    {
        return run_workflow_feedback_promotion_gate(
            shadow_scores,
            owner_approval_refs,
            rollback_refs,
            behavior_lift_refs,
            *min_shadow_reports,
            *min_scenarios,
            *min_strong_scenarios,
            *min_top_shadow_score,
            *json,
        );
    }

    if let Cmd::WorkflowFeedbackLiftEvidence {
        scenario_fixture,
        shadow_scores,
        baseline_correct,
        baseline_total,
        min_accuracy,
        min_lift,
        json,
    } = &cmd
    {
        return run_workflow_feedback_lift_evidence(
            scenario_fixture,
            shadow_scores,
            *baseline_correct,
            *baseline_total,
            *min_accuracy,
            *min_lift,
            *json,
        );
    }

    if let Cmd::WorkflowFeedbackBaselineEvidence {
        scenario_fixture,
        baseline_observations,
        rollback_refs,
        json,
    } = &cmd
    {
        return run_workflow_feedback_baseline_evidence(
            scenario_fixture,
            baseline_observations,
            rollback_refs,
            *json,
        );
    }

    if let Cmd::WorkflowFeedbackOwnerReviewPacket {
        scenario_fixture,
        baseline_observations,
        shadow_scores,
        rollback_refs,
        owner_approval_refs,
        min_accuracy,
        min_lift,
        min_shadow_reports,
        min_scenarios,
        min_strong_scenarios,
        min_top_shadow_score,
        json,
    } = &cmd
    {
        return run_workflow_feedback_owner_review_packet(
            scenario_fixture,
            baseline_observations,
            shadow_scores,
            rollback_refs,
            owner_approval_refs,
            *min_accuracy,
            *min_lift,
            *min_shadow_reports,
            *min_scenarios,
            *min_strong_scenarios,
            *min_top_shadow_score,
            *json,
        );
    }

    if let Cmd::WorkflowFeedbackPromotionRecord {
        owner_review_packet,
        promotion_scopes,
        owner_approval_refs,
        rollback_refs,
        json,
    } = &cmd
    {
        return run_workflow_feedback_promotion_record(
            owner_review_packet,
            promotion_scopes,
            owner_approval_refs,
            rollback_refs,
            *json,
        );
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
        Cmd::Mcp { .. } => tracing_subscriber::fmt::layer()
            .with_writer(std::io::stderr)
            .boxed(),
        _ => tracing_subscriber::fmt::layer().boxed(),
    };
    tracing_subscriber::registry()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .with(log_layer)
        .init();

    let explicit_episode_observation = matches!(
        &cmd,
        Cmd::Daemon {
            episode_observation: Some(EpisodeObservationMode::KeychainMacosV1)
        } | Cmd::Mcp {
            episode_observation: Some(EpisodeObservationMode::KeychainMacosV1)
        }
    );
    let hub = build_hub(explicit_episode_observation).await?;

    match cmd {
        Cmd::Daemon { .. } => {
            let socket = default_socket_path();
            tracing::info!(socket = %socket.display(), "starting agent-bridge daemon");
            // Opt-in tiered embedding delegation (default OFF). When
            // AGENT_BRIDGE_EMBED_REMOTE_URL is set, the daemon delegates embeds to
            // the shared daemon-http /embed service instead of loading its OWN
            // ~1.2GB gte ONNX copy (the daemon + daemon-http double-load). Role-safe:
            // daemon-http is the embedding server and NEVER installs delegation (its
            // arm below does not call this), so even though it inherits the same env
            // this cannot self-loop. Graceful local fallback if the remote is
            // unreachable preserves correctness. Must run before any default_backend()
            // / warmup() / dim-guard use so the OnceLock lands on RemoteEmbedBackend.
            match ab_bridge::remote_embed::install_if_configured() {
                ab_bridge::remote_embed::InstallOutcome::Installed(url) => {
                    tracing::info!(%url, "embedding delegation active (RemoteEmbedBackend)");
                }
                ab_bridge::remote_embed::InstallOutcome::NotConfigured => {}
                ab_bridge::remote_embed::InstallOutcome::AlreadyInitialized => {
                    tracing::warn!(
                        "embedding delegation skipped: a default backend was already \
                         installed — daemon will embed locally"
                    );
                }
            }
            // Embedding dim-guard (#4282): a class-1 config-vs-store dim mismatch
            // strict-aborts here (default-on; mixed-dim migration & empty store
            // exempt; AGENT_BRIDGE_DIM_GUARD_STRICT=0 bypasses). The detached
            // spawn() below stays warn-only for the silent-fallback / in-store
            // anomaly classes.
            if let Some(store) = hub.store.clone() {
                dim_guard_strict_preflight(&store).await;
                ab_bridge::embedding_dim_guard::spawn(store);
            }
            // P-α — explicitly start the daemon-owned coactivation supervisor
            // before the remaining background services and the socket server.
            let coactivation_tick =
                ab_bridge::coactivation_tick::CoactivationTickConfig::from_env();
            if !coactivation_tick.enabled {
                tracing::info!(
                    "substrate-tick: disabled by env (AGENT_BRIDGE_DISABLE_SUBSTRATE_TICK=1)"
                );
            } else if let Some(store) = hub.store.clone() {
                tracing::info!(
                    tick_secs = coactivation_tick.tick_secs,
                    tau_secs = coactivation_tick.tau_secs,
                    "substrate-tick: spawning P-α always-warm coactivation tick"
                );
                ab_bridge::coactivation_tick::spawn(store, coactivation_tick);
            } else {
                tracing::info!("substrate-tick: no store configured, skipping");
            }

            // C3 — daemon self-check tick (Collab Protocol v0 §3.4).
            // S1 multi-process FD enum runs every 30s; on hit, writes
            // OOB alert to ~/.cache/agent-bridge/alerts/ + tracing
            // error on target agent_bridge::sync_safety.
            //
            // S2-S5 share the same tick when a store is configured. S6 is
            // enforced directly on the forum-post write path.
            if ab_bridge::c3_self_check::c3_disabled_via_env() {
                tracing::info!("c3-self-check: disabled by env (AB_C3_DISABLE=1)");
            } else {
                let c3_config = ab_bridge::c3_self_check::C3SupervisorConfig::from_env();
                let c3_store = hub.store.clone();
                tracing::info!(
                    tick_secs = c3_config.tick_secs,
                    s5_enabled = c3_store.is_some(),
                    "c3-self-check: spawning S1-S5 tick"
                );
                ab_bridge::c3_self_check::spawn_supervisor(c3_store, c3_config);
            }

            // Retrieval-outcome apply tick — the gated consumer that closes
            // the surfaced→used learning loop (reinforce/decay on importance).
            // Default OFF: enable per-deployment via
            // AGENT_BRIDGE_RETRIEVAL_OUTCOME_APPLY=1. Cadence is the pacing
            // knob (default daily = at most ±0.05/day per memory); the v40
            // consumed_at marker makes extra ticks after daemon restarts
            // harmless no-ops.
            if !ab_bridge::retrieval_outcome::apply_tick_enabled() {
                tracing::info!(
                    "retrieval-outcome-apply: disabled (AGENT_BRIDGE_RETRIEVAL_OUTCOME_APPLY unset)"
                );
            } else if let Some(store) = hub.store.clone() {
                let tick_secs = ab_bridge::retrieval_outcome::apply_tick_secs();
                tracing::info!(
                    tick_secs,
                    "retrieval-outcome-apply: spawning reinforce/decay tick"
                );
                ab_bridge::retrieval_outcome::spawn_apply_supervisor(store, tick_secs);
            } else {
                tracing::info!("retrieval-outcome-apply: no store configured, skipping");
            }

            // Orphan reaper — kills agent process groups whose owning bridge
            // process is provably gone (v41 starttime tokens make misfire
            // impossible). Default OFF: AGENT_BRIDGE_ORPHAN_REAPER=1 enables.
            // First pass runs IMMEDIATELY: recovering right after a daemon
            // crash/restart is the scenario this exists for.
            if !ab_bridge::orphan_reaper::reaper_enabled() {
                tracing::info!("orphan-reaper: disabled (AGENT_BRIDGE_ORPHAN_REAPER unset)");
            } else if let Some(store) = hub.store.clone() {
                let tick_secs = ab_bridge::orphan_reaper::reaper_tick_secs();
                tracing::info!(tick_secs, "orphan-reaper: spawning reaper tick");
                ab_bridge::orphan_reaper::spawn_reaper_supervisor(store, tick_secs);
            } else {
                tracing::info!("orphan-reaper: no store configured, skipping");
            }
            serve(&socket, Router::new(hub)).await
        }
        Cmd::McpHttpAuthLab { .. } => unreachable!("synthetic auth lab handled before Hub setup"),
        Cmd::McpHttpAuthCandidate { .. } => {
            unreachable!("provider auth candidate handled before Hub setup")
        }
        Cmd::Mcp { .. } => {
            let tool_backend_id = json!({
                "terminal": hub.terminal.as_ref().map(|t| t.id()).unwrap_or("none"),
                "browser": hub.browser.as_ref().map(|b| b.id()).unwrap_or("none"),
                "agent_runtime": hub.agent.as_ref().map(|a| a.id()).unwrap_or("none"),
                "memory": if hub.store.is_some() { "sqlite" } else { "none" },
            });
            let store = hub.store.clone();
            // Tiered embedding delegation: if AGENT_BRIDGE_EMBED_REMOTE_URL is
            // set, this MCP process delegates embedding to the shared daemon-http
            // /embed service instead of loading its own ~2.8GB ONNX copy (8+
            // sessions × 2.8GB = freeze). Role-scoped — ONLY the MCP arm installs
            // it; daemon / daemon-http embed locally (they are the server). Must
            // run before warmup()/build_registry so the OnceLock lands on the
            // RemoteEmbedBackend. Falls back to a local load if the daemon is
            // unreachable, so correctness is never at risk.
            match ab_bridge::remote_embed::install_if_configured() {
                ab_bridge::remote_embed::InstallOutcome::Installed(url) => {
                    tracing::info!(%url, "embedding delegation active (RemoteEmbedBackend)");
                }
                ab_bridge::remote_embed::InstallOutcome::NotConfigured => {}
                ab_bridge::remote_embed::InstallOutcome::AlreadyInitialized => {
                    tracing::warn!(
                        "embedding delegation skipped: a default backend was already \
                         installed (substrate?) — this MCP will embed locally"
                    );
                }
            }
            let registry = build_registry(hub);
            // Eagerly warm the embedding model on a bg thread so the first
            // semantic query after (re)connect doesn't fall to the hash backend
            // and return garbage cosines against the real-model store. Only when
            // memory is enabled (otherwise the encoder is never used). When
            // delegation is active, warmup() routes through RemoteEmbedBackend
            // (a cheap HTTP round-trip), NOT a local 2.8GB model load.
            if let Some(s) = store.clone() {
                ab_store::vector::warmup();
                // Embedding dim-guard (#4282): flag a query/store dim mismatch
                // (stale env / silent model fallback) instead of silently
                // serving all-zero cosines. Strict class-1 preflight aborts here
                // (default-on); the spawn() path stays warn-only for classes 2-4.
                dim_guard_strict_preflight(&s).await;
                ab_bridge::embedding_dim_guard::spawn(s);
            }
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
            let listen = listen
                .unwrap_or_else(|| ab_bridge::daemon_http::DEFAULT_LISTEN.to_string());
            let aura_values =
                avatar_aura_io_startup_values_from_lookup(|key| match std::env::var(key) {
                    Ok(value) => Ok(Some(value)),
                    Err(std::env::VarError::NotPresent) => Ok(None),
                    Err(std::env::VarError::NotUnicode(_)) => {
                        bail!("avatar_aura_io_environment_not_unicode:{key}")
                    }
                })?;
            let aura_config =
                ab_bridge::daemon_http::AvatarAuraIoStartupConfig::from_values(&aura_values)
                    .context("Avatar Aura I/O startup configuration rejected")?;
            tracing::info!(
                listen = %listen,
                "starting agent-bridge daemon-http (local-default HTTP API)"
            );
            // Embedding dim-guard (#4282): cross-machine peers query semantics
            // through daemon-http, so a stale-env e5-384 process against a
            // gte-768 store silently breaks peer recall. Class-1 strict-aborts
            // here (default-on; mixed-dim migration & empty store exempt;
            // AGENT_BRIDGE_DIM_GUARD_STRICT=0 bypasses); the spawn() below stays
            // warn-only for the other classes.
            dim_guard_strict_preflight(&store).await;
            ab_bridge::embedding_dim_guard::spawn(store.clone());
            ab_bridge::daemon_http::run_with_config(store, &listen, aura_config).await
        }
        #[cfg(feature = "g14-wasi-component-runtime")]
        Cmd::G14WasiComponent { .. } | Cmd::G14WasiBusinessComponent { .. } => unreachable!(),
        Cmd::Setup { .. }
        | Cmd::Sync { .. }
        | Cmd::OperatorRequest { .. }
        | Cmd::A2ui { .. }
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
        | Cmd::Resident { .. }
        | Cmd::Walkthrough { .. }
        | Cmd::ContinuityReport { .. }
        | Cmd::WorkflowFeedbackReport { .. }
        | Cmd::WorkflowFeedbackShadowScore { .. }
        | Cmd::WorkflowFeedbackPromotionGate { .. }
        | Cmd::WorkflowFeedbackLiftEvidence { .. }
        | Cmd::WorkflowFeedbackBaselineEvidence { .. }
        | Cmd::WorkflowFeedbackOwnerReviewPacket { .. }
        | Cmd::WorkflowFeedbackPromotionRecord { .. }
        | Cmd::Instinct { .. } => unreachable!(),
    }
}

/// Goal C standing continuity `U` report: build the store-side embedding-space
/// health snapshot via `ab_bridge::continuity` and print the human report (or
/// `--json`). Read-only; no Hub/daemon.
async fn run_continuity_report(as_json: bool) -> Result<()> {
    let db_path = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(ab_store::default_db_path);
    let report = ab_bridge::continuity::build_report(&db_path)
        .await
        .context("building continuity report")?;
    if as_json {
        println!("{}", report.to_json());
    } else {
        print!("{}", report.render_markdown());
    }
    Ok(())
}

/// Daily-wire mechanism for the evidence-anchored session walkthrough: read a
/// walkthrough `doc` JSON (file path, or `-` for stdin), render it through
/// `present::write_walkthrough_artifact` into the present gallery, and read the
/// artifact back to self-verify (the embedded `#ab-payload` round-trips AND the
/// rendered region is non-empty — a content-less doc renders blank by design, so
/// this surfaces "you handed me an empty walkthrough" as a hard failure rather
/// than silently writing a useless artifact). NO new MCP tool; the `/walkthrough`
/// skill assembles the doc from session evidence and shells out to this.
fn run_walkthrough(doc_arg: &str, title: Option<&str>, as_json: bool) -> Result<()> {
    use ab_bridge::present::{extract_ab_payload, presentations_dir, write_walkthrough_artifact};
    use std::io::Read as _;

    let raw = if doc_arg == "-" {
        let mut s = String::new();
        std::io::stdin()
            .read_to_string(&mut s)
            .context("read walkthrough doc from stdin")?;
        s
    } else {
        std::fs::read_to_string(doc_arg)
            .with_context(|| format!("read walkthrough doc {doc_arg}"))?
    };
    let doc: Value = serde_json::from_str(&raw)
        .context("parse walkthrough doc JSON ({summary, steps:[...]})")?;

    let dir = presentations_dir();
    let (id, path) = write_walkthrough_artifact(&dir, &doc, title, None)
        .context("write walkthrough artifact into present gallery")?;

    // Self-verify: read the artifact back. payload must round-trip and the
    // rendered region must carry content (else the doc was empty / unrenderable).
    let html = std::fs::read_to_string(&path).context("read back walkthrough artifact")?;
    let payload_ok = extract_ab_payload(&html).is_some();
    // A walkthrough ALWAYS emits the `<section class="ab-walkthrough">` wrapper AND a
    // bare `<li class="wt-step">` per step entry, so checking for those is too weak —
    // it passes an empty doc OR a doc of empty steps. Require a CONTENT-BEARING marker
    // (`wt-summary` / `wt-heading` / `wt-narrative` / `wt-ev`), each emitted only when
    // its field is actually present. A content-less doc must FAIL — we never silently
    // write a blank "walkthrough".
    let region_has_content = cli::walkthrough_region_has_content(&html);
    let self_check = payload_ok && region_has_content;

    if as_json {
        println!(
            "{}",
            serde_json::to_string(&serde_json::json!({
                "id": id,
                "path": path.display().to_string(),
                "self_check": self_check,
                "payload_ok": payload_ok,
                "region_has_content": region_has_content,
            }))?
        );
    } else {
        println!("walkthrough artifact written:");
        println!("  id        : {id}");
        println!("  path      : {}", path.display());
        println!(
            "  self-check: {}",
            if self_check {
                "PASS (#ab-payload round-trips + rendered region non-empty)"
            } else {
                "FAIL"
            }
        );
        println!("  gallery   : present_list shows kind=walkthrough; open the .html to view/share");
    }

    if !self_check {
        anyhow::bail!(
            "walkthrough self-check FAILED (payload_ok={payload_ok} region_has_content={region_has_content}) \
             — the doc rendered no content; supply a summary and/or steps with evidence"
        );
    }
    Ok(())
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

fn memory_record_from_instinct_plan(value: &Value) -> Result<ab_store::MemoryRecord> {
    let prepared = cli::instinct_memory::prepare_memory_record(value)?;
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    Ok(prepared.into_record(now))
}

/// LCC-F1: report which avatar body backend can satisfy transparency on this
/// compositor. Read-only (env probe only); makes the non-wlroots transparency
/// gap explicit instead of a silent blind spot. See DESIGN-v26 §6.
fn run_avatar_backend_probe(as_json: bool) -> Result<()> {
    let info = ab_bridge::avatar_floater::detect_compositor();
    let rec = ab_bridge::avatar_floater::recommend_backend(&info);
    cli::render_avatar_backend_probe_result(&info, &rec, as_json)
}

fn run_avatar_sprite_asset_audit(
    path: &Path,
    columns: u32,
    rows: u32,
    cell_width: u32,
    cell_height: u32,
    frame_count: Option<u32>,
    target_width: u32,
    target_height: u32,
    max_baseline_drift_px: u32,
    as_json: bool,
) -> Result<()> {
    let report = ab_bridge::avatar_asset_audit::audit_sprite_asset(
        path,
        columns,
        rows,
        cell_width,
        cell_height,
        frame_count,
        target_width,
        target_height,
        max_baseline_drift_px,
    )?;
    cli::avatar_presentation::render_sprite_asset_audit(&report, as_json)?;
    if report.accepted {
        Ok(())
    } else {
        anyhow::bail!("sprite asset failed admission checks")
    }
}

fn run_avatar_sprite_asset_contract(asset_root: &Path, as_json: bool) -> Result<()> {
    let contract = ab_bridge::avatar_asset_audit::focus_follow_asset_contract(asset_root);
    cli::avatar_presentation::render_sprite_asset_contract(&contract, as_json)?;
    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn run_avatar_sprite_asset_compile(
    input: &Path,
    output: &Path,
    frame_count: u32,
    cell_width: u32,
    cell_height: u32,
    padding_px: u32,
    baseline_y: u32,
    flip_horizontal: bool,
    execute: bool,
    confirm: bool,
    as_json: bool,
) -> Result<()> {
    anyhow::ensure!(!execute || confirm, "--execute requires --confirm");
    let report = ab_bridge::avatar_asset_compile::compile_sprite_atlas(
        input,
        output,
        ab_bridge::avatar_asset_compile::SpriteCompileOptions {
            frame_count,
            cell_width,
            cell_height,
            padding_px,
            baseline_y,
            flip_horizontal,
        },
        execute,
    )?;
    cli::avatar_presentation::render_sprite_asset_compile(&report, as_json)?;
    Ok(())
}

async fn run_avatar_focus_follow_plan(
    avatar_app_id: String,
    margin_px: i64,
    max_step_px: i64,
    as_json: bool,
) -> Result<()> {
    let tree = read_sway_tree_for_avatar().await?;
    let opts = ab_bridge::avatar_focus_follow::FocusFollowOptions {
        avatar_app_id,
        margin_px,
        max_step_px,
    };
    let plan = ab_bridge::avatar_focus_follow::focus_follow_plan_from_sway_tree(&tree, &opts);
    cli::avatar_presentation::render_focus_follow_plan(&plan, as_json)?;
    Ok(())
}

async fn run_avatar_focus_follow_recommend(
    last_target_node_id: Option<i64>,
    min_travel_px: i64,
    margin_px: i64,
    max_step_px: i64,
    as_json: bool,
) -> Result<()> {
    let tree = read_sway_tree_for_avatar().await?;
    let plan = ab_bridge::avatar_focus_follow::focus_follow_plan_from_sway_tree(
        &tree,
        &ab_bridge::avatar_focus_follow::FocusFollowOptions {
            avatar_app_id: ab_bridge::avatar_focus_follow::DEFAULT_AVATAR_APP_ID.to_string(),
            margin_px,
            max_step_px,
        },
    );
    let last_target_node_id = last_target_node_id.or_else(|| read_focus_follow_ack_target(&plan));
    let recommendation = ab_bridge::avatar_focus_follow::focus_follow_recommendation(
        &plan,
        last_target_node_id,
        min_travel_px,
    );
    cli::avatar_presentation::render_focus_follow_recommendation(&recommendation, as_json)?;
    Ok(())
}

fn focus_follow_prompt_receipt_path() -> PathBuf {
    std::env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir)
        .join("ab-focus-follow-prompt-receipt.json")
}

fn validate_owner_private_directory(path: &std::path::Path, label: &str) -> Result<()> {
    validate_real_directory(path, label)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::{MetadataExt, PermissionsExt};
        let metadata = std::fs::metadata(path)
            .with_context(|| format!("inspect {label} {}", path.display()))?;
        anyhow::ensure!(
            metadata.uid() == unsafe { libc::geteuid() }
                && metadata.permissions().mode() & 0o077 == 0,
            "{label} must be owned by the current user and private: {}",
            path.display()
        );
    }
    Ok(())
}

fn focus_follow_runtime_dir() -> Result<PathBuf> {
    let path = std::env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .context("XDG_RUNTIME_DIR is required for live Avatar focus observation")?;
    anyhow::ensure!(
        path.is_absolute() && path.file_name().is_some(),
        "XDG_RUNTIME_DIR must be an absolute, non-root path"
    );
    validate_owner_private_directory(&path, "Avatar runtime directory")?;
    Ok(path)
}

fn focus_follow_ack_receipt_path() -> Result<PathBuf> {
    Ok(focus_follow_runtime_dir()?.join("ab-focus-follow-ack.json"))
}

fn focus_follow_observer_receipt_path() -> Result<PathBuf> {
    Ok(focus_follow_runtime_dir()?.join("ab-focus-follow-observer-receipt.json"))
}

fn focus_follow_compositor_session_id() -> Result<String> {
    use sha2::{Digest, Sha256};
    #[cfg(unix)]
    use std::os::unix::fs::{FileTypeExt, MetadataExt};

    let sway_socket = std::env::var_os("SWAYSOCK")
        .context("SWAYSOCK is required to bind the Avatar acknowledgement to this compositor")?;
    let socket_metadata = std::fs::metadata(&sway_socket)
        .context("inspect current Sway IPC socket for Avatar acknowledgement binding")?;
    #[cfg(unix)]
    anyhow::ensure!(
        socket_metadata.file_type().is_socket()
            && socket_metadata.uid() == unsafe { libc::geteuid() },
        "SWAYSOCK must be a current-user Unix socket"
    );
    let wayland_display = std::env::var_os("WAYLAND_DISPLAY").unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(b"agent-bridge-avatar-focus-session-v2\0");
    hasher.update(sway_socket.to_string_lossy().as_bytes());
    hasher.update(b"\0");
    hasher.update(wayland_display.to_string_lossy().as_bytes());
    #[cfg(unix)]
    {
        hasher.update(b"\0");
        hasher.update(socket_metadata.dev().to_le_bytes());
        hasher.update(socket_metadata.ino().to_le_bytes());
    }
    let digest = hasher.finalize();
    Ok(digest[..12]
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect())
}

fn focus_follow_outcome_log_path() -> Result<PathBuf> {
    focus_follow_outcome_log_path_from_roots(
        std::env::var_os("AGENT_BRIDGE_STATE_DIR").map(PathBuf::from),
        std::env::var_os("XDG_STATE_HOME").map(PathBuf::from),
        std::env::var_os("HOME").map(PathBuf::from),
    )
}

fn focus_follow_outcome_log_path_from_roots(
    agent_bridge_state_dir: Option<PathBuf>,
    xdg_state_home: Option<PathBuf>,
    home: Option<PathBuf>,
) -> Result<PathBuf> {
    let state_root = agent_bridge_state_dir
        .or_else(|| xdg_state_home.map(|root| root.join("agent-bridge")))
        .or_else(|| home.map(|root| root.join(".local/state/agent-bridge")))
        .context(
            "no durable Avatar state root; set AGENT_BRIDGE_STATE_DIR, XDG_STATE_HOME, or HOME",
        )?;
    anyhow::ensure!(
        state_root.is_absolute() && state_root.file_name().is_some(),
        "Avatar state root must be an absolute, non-root path; configure AGENT_BRIDGE_STATE_DIR with a private local directory"
    );
    Ok(state_root
        .join("avatar-focus-follow")
        .join("outcomes.jsonl"))
}

#[cfg(unix)]
fn enforce_private_directory(path: &std::path::Path, label: &str) -> Result<()> {
    use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};

    let directory = std::fs::OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_CLOEXEC | libc::O_DIRECTORY | libc::O_NOFOLLOW)
        .open(path)
        .with_context(|| format!("open {label} {}", path.display()))?;
    directory
        .set_permissions(std::fs::Permissions::from_mode(0o700))
        .with_context(|| format!("restrict {label} {}", path.display()))?;
    let observed_mode = directory
        .metadata()
        .with_context(|| format!("inspect open {label} {}", path.display()))?
        .permissions()
        .mode()
        & 0o777;
    anyhow::ensure!(
        observed_mode == 0o700,
        "{label} filesystem cannot enforce private mode 700 on {} (observed {:o}); set AGENT_BRIDGE_STATE_DIR to a permission-capable private filesystem",
        path.display(),
        observed_mode
    );
    Ok(())
}

#[cfg(unix)]
fn sync_directory(path: &std::path::Path, label: &str) -> Result<()> {
    use std::os::unix::fs::OpenOptionsExt;

    std::fs::OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_CLOEXEC | libc::O_DIRECTORY | libc::O_NOFOLLOW)
        .open(path)
        .with_context(|| format!("open {label} for sync {}", path.display()))?
        .sync_all()
        .with_context(|| format!("sync {label} {}", path.display()))
}

#[cfg(not(unix))]
fn enforce_private_directory(path: &std::path::Path, label: &str) -> Result<()> {
    anyhow::bail!(
        "{label} private journal is unsupported on this platform: {}",
        path.display()
    )
}

#[cfg(not(unix))]
fn sync_directory(path: &std::path::Path, label: &str) -> Result<()> {
    anyhow::bail!(
        "{label} durable directory sync is unsupported on this platform: {}",
        path.display()
    )
}

#[cfg(unix)]
fn enforce_private_regular_file(
    file: &std::fs::File,
    path: &std::path::Path,
    label: &str,
) -> Result<()> {
    use std::os::unix::fs::{MetadataExt, PermissionsExt};

    let before = file
        .metadata()
        .with_context(|| format!("inspect open {label} {}", path.display()))?;
    anyhow::ensure!(
        before.is_file() && before.nlink() == 1,
        "{label} must be a regular file with exactly one hard link: {}",
        path.display()
    );
    file.set_permissions(std::fs::Permissions::from_mode(0o600))
        .with_context(|| format!("restrict {label} {}", path.display()))?;
    let after = file
        .metadata()
        .with_context(|| format!("reinspect open {label} {}", path.display()))?;
    anyhow::ensure!(
        after.is_file()
            && after.nlink() == 1
            && after.dev() == before.dev()
            && after.ino() == before.ino(),
        "{label} identity or link count changed while securing {}",
        path.display()
    );
    let observed_mode = after.permissions().mode() & 0o777;
    anyhow::ensure!(
        observed_mode == 0o600,
        "{label} filesystem cannot enforce private mode 600 on {} (observed {:o}); set AGENT_BRIDGE_STATE_DIR to a permission-capable private filesystem",
        path.display(),
        observed_mode
    );
    Ok(())
}

#[cfg(not(unix))]
fn enforce_private_regular_file(
    _file: &std::fs::File,
    path: &std::path::Path,
    label: &str,
) -> Result<()> {
    anyhow::bail!(
        "{label} private journal is unsupported on this platform: {}",
        path.display()
    )
}

#[cfg(unix)]
fn validate_private_regular_file(
    file: &std::fs::File,
    path: &std::path::Path,
    label: &str,
) -> Result<()> {
    use std::os::unix::fs::{MetadataExt, PermissionsExt};

    let metadata = file
        .metadata()
        .with_context(|| format!("inspect open {label} {}", path.display()))?;
    anyhow::ensure!(
        metadata.is_file()
            && metadata.nlink() == 1
            && metadata.uid() == unsafe { libc::geteuid() }
            && metadata.permissions().mode() & 0o777 == 0o600,
        "{label} must be a current-user private regular file with one hard link: {}",
        path.display()
    );
    Ok(())
}

#[cfg(not(unix))]
fn validate_private_regular_file(
    _file: &std::fs::File,
    path: &std::path::Path,
    label: &str,
) -> Result<()> {
    anyhow::bail!(
        "{label} private validation is unsupported on this platform: {}",
        path.display()
    )
}

fn validate_real_directory(path: &std::path::Path, label: &str) -> Result<()> {
    let metadata = std::fs::symlink_metadata(path)
        .with_context(|| format!("inspect {label} {}", path.display()))?;
    anyhow::ensure!(
        !metadata.file_type().is_symlink() && metadata.is_dir(),
        "{label} must be a real directory, not a symlink or special file: {}",
        path.display()
    );
    Ok(())
}

fn prepare_focus_follow_outcome_directory(path: &std::path::Path) -> Result<()> {
    let state_root = path
        .parent()
        .context("Avatar outcome directory has no state root")?;
    let state_root_created = !state_root.exists();
    if !state_root_created {
        validate_real_directory(state_root, "Agent-Bridge state root")?;
    } else {
        std::fs::create_dir_all(state_root)
            .with_context(|| format!("create Agent-Bridge state root {}", state_root.display()))?;
        validate_real_directory(state_root, "Agent-Bridge state root")?;
    }

    let private_directory_created = !path.exists();
    if !private_directory_created {
        validate_real_directory(path, "Avatar outcome directory")?;
    } else {
        let mut builder = std::fs::DirBuilder::new();
        #[cfg(unix)]
        {
            use std::os::unix::fs::DirBuilderExt;
            builder.mode(0o700);
        }
        match builder.create(path) {
            Ok(()) => {}
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {}
            Err(error) => {
                return Err(error)
                    .with_context(|| format!("create Avatar outcome directory {}", path.display()))
            }
        }
        validate_real_directory(path, "Avatar outcome directory")?;
    }
    enforce_private_directory(path, "Avatar outcome directory")?;
    if private_directory_created {
        sync_directory(path, "Avatar outcome directory")?;
        sync_directory(state_root, "Agent-Bridge state root")?;
    }
    if state_root_created {
        if let Some(parent) = state_root.parent() {
            sync_directory(parent, "Agent-Bridge state-root parent")?;
        }
    }
    Ok(())
}

fn validate_regular_nonsymlink(path: &std::path::Path, label: &str) -> Result<()> {
    match std::fs::symlink_metadata(path) {
        Ok(metadata) => {
            anyhow::ensure!(
                !metadata.file_type().is_symlink() && metadata.is_file(),
                "{label} must be a regular non-symlink file: {}",
                path.display()
            );
            #[cfg(unix)]
            {
                use std::os::unix::fs::MetadataExt;
                anyhow::ensure!(
                    metadata.nlink() == 1,
                    "{label} must have exactly one hard link: {}",
                    path.display()
                );
            }
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(error) => {
            return Err(error).with_context(|| format!("inspect {label} {}", path.display()))
        }
    }
    Ok(())
}

struct AvatarOutcomeJournalLock {
    file: std::fs::File,
}

impl AvatarOutcomeJournalLock {
    fn acquire(directory: &std::path::Path) -> Result<Self> {
        #[cfg(unix)]
        use std::os::unix::fs::OpenOptionsExt;
        let path = directory.join(".focus-follow-outcomes.lock");
        validate_regular_nonsymlink(&path, "Avatar outcome lock")?;
        let mut options = std::fs::OpenOptions::new();
        options.create(true).read(true).write(true);
        #[cfg(unix)]
        {
            options.mode(0o600);
            options.custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW);
        }
        let file = options
            .open(&path)
            .with_context(|| format!("open Avatar outcome lock {}", path.display()))?;
        enforce_private_regular_file(&file, &path, "Avatar outcome lock")?;
        #[cfg(unix)]
        {
            use std::os::fd::AsRawFd;
            let result = unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX) };
            if result != 0 {
                return Err(std::io::Error::last_os_error())
                    .with_context(|| format!("lock Avatar outcome journal {}", path.display()));
            }
        }
        Ok(Self { file })
    }
}

impl Drop for AvatarOutcomeJournalLock {
    fn drop(&mut self) {
        #[cfg(unix)]
        {
            use std::os::fd::AsRawFd;
            unsafe {
                libc::flock(self.file.as_raw_fd(), libc::LOCK_UN);
            }
        }
    }
}

const AVATAR_FOCUS_ACTION_LOCK_FILE: &str = ".focus-follow-action.lock";
const AVATAR_FOCUS_OBSERVER_LOCK_FILE: &str = ".focus-follow-observer.lock";

struct AvatarExclusiveOperationLock {
    file: std::fs::File,
}

impl AvatarExclusiveOperationLock {
    fn try_acquire(
        directory: &std::path::Path,
        file_name: &str,
        label: &str,
    ) -> Result<Option<Self>> {
        #[cfg(unix)]
        use std::os::unix::fs::OpenOptionsExt;

        anyhow::ensure!(
            matches!(
                file_name,
                AVATAR_FOCUS_ACTION_LOCK_FILE | AVATAR_FOCUS_OBSERVER_LOCK_FILE
            ),
            "unsupported Avatar operation lock"
        );
        validate_real_directory(directory, "Avatar operation runtime directory")?;
        let path = directory.join(file_name);
        validate_regular_nonsymlink(&path, label)?;
        let mut options = std::fs::OpenOptions::new();
        options.create(true).read(true).write(true);
        #[cfg(unix)]
        {
            options.mode(0o600);
            options.custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW);
        }
        let file = options
            .open(&path)
            .with_context(|| format!("open {label} {}", path.display()))?;
        enforce_private_regular_file(&file, &path, label)?;
        #[cfg(unix)]
        {
            use std::os::fd::AsRawFd;
            let result = unsafe {
                libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB)
            };
            if result != 0 {
                let error = std::io::Error::last_os_error();
                if error
                    .raw_os_error()
                    .is_some_and(|code| code == libc::EWOULDBLOCK || code == libc::EAGAIN)
                {
                    return Ok(None);
                }
                return Err(error).with_context(|| format!("lock {label} {}", path.display()));
            }
            return Ok(Some(Self { file }));
        }
        #[cfg(not(unix))]
        {
            let _ = file;
            anyhow::bail!("{label} is unsupported on this platform")
        }
    }
}

impl Drop for AvatarExclusiveOperationLock {
    fn drop(&mut self) {
        #[cfg(unix)]
        {
            use std::os::fd::AsRawFd;
            unsafe {
                libc::flock(self.file.as_raw_fd(), libc::LOCK_UN);
            }
        }
    }
}

fn next_avatar_outcome_attempt_id() -> String {
    format!("af-{}", uuid::Uuid::new_v4())
}

const MAX_FOCUS_FOLLOW_OUTCOME_LOG_BYTES: u64 = 8 * 1024 * 1024;

fn rotate_focus_follow_outcome_log_if_needed(
    path: &std::path::Path,
    directory: &std::path::Path,
    attempt_id: &str,
    enabled: bool,
) -> Result<Option<PathBuf>> {
    #[cfg(unix)]
    use std::os::unix::fs::OpenOptionsExt;

    if !enabled
        || !std::fs::metadata(path)
            .ok()
            .is_some_and(|metadata| metadata.len() >= MAX_FOCUS_FOLLOW_OUTCOME_LOG_BYTES)
    {
        return Ok(None);
    }
    let rotated = path.with_extension(format!("jsonl.{attempt_id}"));
    anyhow::ensure!(
        std::fs::symlink_metadata(&rotated)
            .is_err_and(|error| error.kind() == std::io::ErrorKind::NotFound),
        "refusing to overwrite existing Avatar outcome rotation {}",
        rotated.display()
    );
    std::fs::rename(path, &rotated).with_context(|| {
        format!(
            "rotate Avatar expression outcome {} to {}",
            path.display(),
            rotated.display()
        )
    })?;
    let mut rotated_options = std::fs::OpenOptions::new();
    rotated_options.read(true).write(true);
    #[cfg(unix)]
    rotated_options.custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW);
    let rotated_file = rotated_options
        .open(&rotated)
        .with_context(|| format!("open rotated Avatar outcome {}", rotated.display()))?;
    enforce_private_regular_file(&rotated_file, &rotated, "rotated Avatar expression outcome")?;
    sync_directory(directory, "Avatar outcome directory")?;
    Ok(Some(rotated))
}

fn append_focus_follow_outcome(
    action: &serde_json::Value,
    phase: &str,
    rotate_before_write: bool,
) -> Result<PathBuf> {
    let path = focus_follow_outcome_log_path()?;
    append_focus_follow_outcome_at_path(action, phase, rotate_before_write, &path)
}

fn append_focus_follow_outcome_at_path(
    action: &serde_json::Value,
    phase: &str,
    rotate_before_write: bool,
    path: &std::path::Path,
) -> Result<PathBuf> {
    use std::io::Write;
    #[cfg(unix)]
    use std::os::unix::fs::OpenOptionsExt;

    anyhow::ensure!(
        matches!(phase, "started" | "final"),
        "invalid Avatar outcome phase"
    );
    let attempt_id = action
        .get("attempt_id")
        .and_then(serde_json::Value::as_str)
        .context("Avatar outcome attempt_id")?;
    anyhow::ensure!(
        attempt_id.starts_with("af-")
            && attempt_id.len() <= 64
            && attempt_id
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-'),
        "invalid Avatar outcome attempt_id"
    );
    let directory = path
        .parent()
        .context("Avatar outcome log has no directory")?;
    prepare_focus_follow_outcome_directory(directory)?;
    let _journal_lock = AvatarOutcomeJournalLock::acquire(directory)?;
    let observed_at_unix_ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .context("read wall clock for Avatar expression outcome")?
        .as_millis() as u64;
    let record = ab_bridge::avatar_focus_follow::focus_follow_outcome_record(
        action,
        phase,
        observed_at_unix_ms,
    )?;
    validate_regular_nonsymlink(&path, "Avatar expression outcome")?;
    if path.exists() {
        let mut existing_options = std::fs::OpenOptions::new();
        existing_options.read(true).write(true);
        #[cfg(unix)]
        existing_options.custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW);
        let existing = existing_options
            .open(&path)
            .with_context(|| format!("open existing Avatar outcome {}", path.display()))?;
        enforce_private_regular_file(&existing, &path, "existing Avatar expression outcome")?;
    }
    rotate_focus_follow_outcome_log_if_needed(&path, directory, attempt_id, rotate_before_write)?;
    let mut options = std::fs::OpenOptions::new();
    options.create(true).append(true);
    #[cfg(unix)]
    {
        options.mode(0o600);
        options.custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW);
    }
    let mut file = options
        .open(&path)
        .with_context(|| format!("open Avatar expression outcome log {}", path.display()))?;
    enforce_private_regular_file(&file, &path, "Avatar expression outcome")?;
    let mut encoded = serde_json::to_vec(&record)?;
    encoded.push(b'\n');
    file.write_all(&encoded)
        .with_context(|| format!("append Avatar expression outcome {}", path.display()))?;
    file.sync_all()
        .with_context(|| format!("sync Avatar expression outcome {}", path.display()))?;
    sync_directory(directory, "Avatar outcome directory")?;
    Ok(path.to_path_buf())
}

struct AvatarOutcomeAttemptGuard {
    current_action: serde_json::Value,
    finished: bool,
    finish_attempted: bool,
}

impl AvatarOutcomeAttemptGuard {
    fn start(action: &mut serde_json::Value) -> Result<(Self, PathBuf)> {
        action["attempt_id"] = serde_json::json!(next_avatar_outcome_attempt_id());
        action["status"] = serde_json::json!("running");
        action["execution_stage"] = serde_json::json!("preparing");
        action["executed"] = serde_json::json!(false);
        action["executed_steps"] = serde_json::json!(0);
        action["postcondition_verified"] = serde_json::json!(false);
        let path = append_focus_follow_outcome(action, "started", true)?;
        Ok((
            Self {
                current_action: action.clone(),
                finished: false,
                finish_attempted: false,
            },
            path,
        ))
    }

    fn observe(&mut self, action: &serde_json::Value) {
        self.current_action = action.clone();
    }

    fn finish(&mut self, action: &serde_json::Value) -> Result<()> {
        self.observe(action);
        self.finish_attempted = true;
        append_focus_follow_outcome(action, "final", false)?;
        self.finished = true;
        Ok(())
    }
}

fn failed_avatar_outcome_snapshot(
    current_action: &serde_json::Value,
    finish_attempted: bool,
) -> serde_json::Value {
    let mut failure = current_action.clone();
    failure["status"] = serde_json::json!("failed");
    failure["ready"] = serde_json::json!(false);
    failure["stopped_reason"] = serde_json::json!(if finish_attempted {
        "final_receipt_persistence_failed"
    } else {
        "unhandled_internal_error_or_unwind"
    });
    failure
}

impl Drop for AvatarOutcomeAttemptGuard {
    fn drop(&mut self) {
        if self.finished {
            return;
        }
        let failure = failed_avatar_outcome_snapshot(&self.current_action, self.finish_attempted);
        if let Err(err) = append_focus_follow_outcome(&failure, "final", false) {
            eprintln!("agent-bridge could not record failed Avatar expression: {err:#}");
        }
    }
}

fn read_focus_follow_ack_receipt(plan: &serde_json::Value) -> Option<serde_json::Value> {
    use std::io::Read;
    #[cfg(unix)]
    use std::os::unix::fs::OpenOptionsExt;

    let avatar_node_id = plan
        .pointer("/avatar/node_id")
        .and_then(serde_json::Value::as_i64)?;
    let compositor_session_id = focus_follow_compositor_session_id().ok()?;
    let path = focus_follow_ack_receipt_path().ok()?;
    validate_regular_nonsymlink(&path, "Avatar focus acknowledgement").ok()?;
    let mut options = std::fs::OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    options.custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW);
    let mut file = options.open(&path).ok()?;
    validate_private_regular_file(&file, &path, "Avatar focus acknowledgement").ok()?;
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes).ok()?;
    let receipt = serde_json::from_slice::<serde_json::Value>(&bytes).ok()?;
    ab_bridge::avatar_focus_follow::acknowledged_target_from_receipt(
        &receipt,
        &compositor_session_id,
        avatar_node_id,
    )?;
    Some(receipt)
}

fn read_focus_follow_ack_target(plan: &serde_json::Value) -> Option<i64> {
    read_focus_follow_ack_receipt(plan)?
        .get("target_node_id")?
        .as_i64()
}

fn focus_follow_ack_cooldown_remaining_ms(
    receipt: &serde_json::Value,
    cooldown_ms: u64,
    now_unix_ms: u64,
) -> Option<u64> {
    let completed_at = receipt
        .get("completed_at_unix_ms")
        .and_then(serde_json::Value::as_u64)?;
    if completed_at > now_unix_ms {
        return Some(cooldown_ms);
    }
    let elapsed = now_unix_ms.saturating_sub(completed_at);
    (elapsed < cooldown_ms).then(|| cooldown_ms.saturating_sub(elapsed))
}

fn write_focus_follow_ack_target(
    target_node_id: i64,
    avatar_node_id: i64,
    executed_steps: u64,
) -> Result<PathBuf> {
    use std::io::Write;
    #[cfg(unix)]
    use std::os::unix::fs::OpenOptionsExt;

    let path = focus_follow_ack_receipt_path()?;
    let directory = path
        .parent()
        .context("Avatar focus acknowledgement has no runtime directory")?;
    validate_real_directory(directory, "Avatar runtime directory")?;
    validate_regular_nonsymlink(&path, "Avatar focus acknowledgement")?;
    let compositor_session_id = focus_follow_compositor_session_id()?;
    let completed_at_unix_ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .context("read wall clock for focus-follow acknowledgement")?
        .as_millis() as u64;
    let receipt = serde_json::json!({
        "schema": ab_bridge::avatar_focus_follow::FOCUS_FOLLOW_ACK_SCHEMA,
        "status": "completed",
        "compositor_session_id": compositor_session_id,
        "avatar_node_id": avatar_node_id,
        "target_node_id": target_node_id,
        "executed_steps": executed_steps,
        "completed_at_unix_ms": completed_at_unix_ms,
    });
    let temp_path = path.with_extension(format!(
        "tmp-{}-{}",
        std::process::id(),
        uuid::Uuid::new_v4()
    ));
    let mut options = std::fs::OpenOptions::new();
    options.create_new(true).write(true);
    #[cfg(unix)]
    {
        options.mode(0o600);
        options.custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW);
    }
    let mut file = options
        .open(&temp_path)
        .with_context(|| format!("create focus-follow acknowledgement {}", temp_path.display()))?;
    enforce_private_regular_file(&file, &temp_path, "temporary Avatar focus acknowledgement")?;
    file.write_all(&serde_json::to_vec_pretty(&receipt)?)
        .with_context(|| format!("write focus-follow acknowledgement {}", temp_path.display()))?;
    file.sync_all()
        .with_context(|| format!("sync focus-follow acknowledgement {}", temp_path.display()))?;
    std::fs::rename(&temp_path, &path)
        .with_context(|| format!("publish focus-follow acknowledgement {}", path.display()))?;
    sync_directory(directory, "Avatar runtime directory")?;
    Ok(path)
}

async fn run_avatar_focus_follow_prompt(
    last_target_node_id: Option<i64>,
    min_travel_px: i64,
    cooldown_secs: u64,
    timeout_ms: u64,
    show: bool,
    confirm: bool,
    as_json: bool,
) -> Result<()> {
    let tree = read_sway_tree_for_avatar().await?;
    let plan = ab_bridge::avatar_focus_follow::focus_follow_plan_from_sway_tree(
        &tree,
        &ab_bridge::avatar_focus_follow::FocusFollowOptions::default(),
    );
    let last_target_node_id = last_target_node_id.or_else(|| read_focus_follow_ack_target(&plan));
    let recommendation = ab_bridge::avatar_focus_follow::focus_follow_recommendation(
        &plan,
        last_target_node_id,
        min_travel_px,
    );
    let receipt_path = focus_follow_prompt_receipt_path();
    let wall_clock = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .context("read wall clock for focus-follow prompt")?;
    let now = wall_clock.as_secs();
    let now_ms = wall_clock.as_millis() as u64;
    let cooldown_secs = cooldown_secs.clamp(30, 3_600);
    let previous = std::fs::read(&receipt_path)
        .ok()
        .and_then(|bytes| serde_json::from_slice::<serde_json::Value>(&bytes).ok());
    let cooldown_active = previous
        .as_ref()
        .and_then(|value| value.get("emitted_at_unix_secs"))
        .and_then(serde_json::Value::as_u64)
        .is_some_and(|emitted| now.saturating_sub(emitted) < cooldown_secs);
    let mut prompt = ab_bridge::avatar_focus_follow::focus_follow_prompt_preflight(
        &recommendation,
        show,
        confirm,
        cooldown_active,
        timeout_ms,
    );
    prompt["cooldown_secs"] = serde_json::json!(cooldown_secs);
    prompt["receipt_path"] = serde_json::json!(receipt_path);
    prompt["emitted"] = serde_json::json!(false);

    if prompt.get("ready").and_then(serde_json::Value::as_bool) == Some(true) {
        let bounded_timeout = timeout_ms.clamp(2_000, 30_000);
        let avatar_visible = tree.to_string().contains("agent-bridge-avatar");
        let mut notification_id = None;
        let presentation_backend;
        if avatar_visible {
            let prompt_path = ab_bridge::avatar_native::default_native_prompt_path()
                .context("XDG_RUNTIME_DIR is required for Avatar anchored prompt")?;
            let expires_at_unix_ms = now_ms.saturating_add(bounded_timeout);
            let payload = serde_json::json!({
                "schema": ab_bridge::avatar_native::NATIVE_PROMPT_SCHEMA,
                "text": "我过去看看。",
                "created_at_unix_ms": now_ms,
                "expires_at_unix_ms": expires_at_unix_ms,
            });
            let temp_path = prompt_path.with_extension(format!("tmp-{}", std::process::id()));
            std::fs::write(&temp_path, serde_json::to_vec(&payload)?)
                .with_context(|| format!("write Avatar prompt state {}", temp_path.display()))?;
            std::fs::rename(&temp_path, &prompt_path).with_context(|| {
                format!("publish Avatar prompt state {}", prompt_path.display())
            })?;
            prompt["prompt_state_path"] = serde_json::json!(prompt_path);
            presentation_backend = "avatar_renderer";
        } else {
            let output = std::process::Command::new("notify-send")
                .args([
                    "--print-id",
                    "--app-name=Xiao Shu",
                    "--urgency=low",
                    "--transient",
                    &format!("--expire-time={bounded_timeout}"),
                    "小舒",
                    "我过去看看。",
                ])
                .output()
                .context("show fallback Xiao Shu desktop prompt")?;
            if !output.status.success() {
                prompt["status"] = serde_json::json!("failed");
                prompt["blocked_reason"] = serde_json::json!("presentation_backend_failed");
                prompt["ready"] = serde_json::json!(false);
                if as_json {
                    println!("{}", serde_json::to_string_pretty(&prompt)?);
                }
                return Ok(());
            }
            notification_id = String::from_utf8_lossy(&output.stdout)
                .trim()
                .parse::<u64>()
                .ok();
            presentation_backend = "desktop_notification_fallback";
        }
        {
            let receipt = serde_json::json!({
                "schema": "agent_bridge.avatar_focus_follow_prompt_receipt.v1",
                "emitted_at_unix_secs": now,
                "notification_id": notification_id,
                "presentation_backend": presentation_backend,
                "target_node_id": recommendation.get("target_node_id"),
            });
            let temp_path = receipt_path.with_extension(format!("tmp-{}", std::process::id()));
            std::fs::write(&temp_path, serde_json::to_vec_pretty(&receipt)?).with_context(
                || format!("write focus-follow prompt receipt {}", temp_path.display()),
            )?;
            std::fs::rename(&temp_path, &receipt_path).with_context(|| {
                format!(
                    "publish focus-follow prompt receipt {}",
                    receipt_path.display()
                )
            })?;
            prompt["status"] = serde_json::json!("shown");
            prompt["ready"] = serde_json::json!(false);
            prompt["emitted"] = serde_json::json!(true);
            prompt["notification_id"] = serde_json::json!(notification_id);
            prompt["presentation_backend"] = serde_json::json!(presentation_backend);
        }
    }

    cli::avatar_presentation::render_focus_follow_prompt(&prompt, as_json)?;
    Ok(())
}

const AVATAR_SWAY_READ_TIMEOUT: std::time::Duration = std::time::Duration::from_millis(2_500);
const AVATAR_SWAY_MOVE_TIMEOUT: std::time::Duration = std::time::Duration::from_millis(2_000);

async fn read_sway_tree_for_avatar() -> Result<serde_json::Value> {
    read_sway_tree_for_avatar_with_timeout(AVATAR_SWAY_READ_TIMEOUT).await
}

async fn read_sway_tree_for_avatar_with_timeout(
    timeout: std::time::Duration,
) -> Result<serde_json::Value> {
    anyhow::ensure!(!timeout.is_zero(), "Avatar Sway tree read deadline elapsed");
    let mut command = tokio::process::Command::new("swaymsg");
    command
        .args(["-t", "get_tree", "-r"])
        .kill_on_drop(true);
    let output = tokio::time::timeout(timeout, command.output())
        .await
        .context("read-only swaymsg get_tree timed out for Avatar focus-follow")?
        .context("run read-only swaymsg get_tree for Avatar focus-follow")?;
    if !output.status.success() {
        anyhow::bail!(
            "read-only swaymsg get_tree failed: {}",
            String::from_utf8_lossy(&output.stderr).trim()
        );
    }
    serde_json::from_slice(&output.stdout).context("decode Sway tree for Avatar focus-follow")
}

async fn move_avatar_exact_with_timeout(
    avatar_node_id: i64,
    x: i64,
    y: i64,
    timeout: std::time::Duration,
) -> Result<bool> {
    anyhow::ensure!(!timeout.is_zero(), "Avatar Sway move deadline elapsed");
    let selector = format!("[con_id={avatar_node_id}]");
    let movement = format!("move position {x} {y}");
    let mut command = tokio::process::Command::new("swaymsg");
    command
        .arg(selector)
        .arg(movement)
        .kill_on_drop(true);
    let output = tokio::time::timeout(timeout, command.output())
        .await
        .context("bounded Avatar swaymsg move timed out")?
        .context("run bounded Avatar swaymsg move")?;
    Ok(output.status.success()
        && ab_bridge::avatar_focus_follow::sway_command_succeeded(&output.stdout))
}

struct AvatarMotionOverrideGuard {
    path: PathBuf,
}

impl AvatarMotionOverrideGuard {
    fn new(path: PathBuf) -> Self {
        Self { path }
    }

    fn set(&self, action: &str) -> Result<()> {
        let (mode, asset) = match action {
            "turn_left" => ("orienting", "xiao-shu-v3-focus-turn-left-v1"),
            "turn_right" => ("orienting", "xiao-shu-v3-focus-turn-right-v1"),
            "walk_left" => ("working", "xiao-shu-v3-focus-walk-left-v1"),
            "walk_right" => ("working", "xiao-shu-v3-focus-walk-right-v1"),
            "arrive_settle" => ("verified", "xiao-shu-v3-ai-completion-nod-v2"),
            "wave" => ("verified", "xiao-shu-v3-focus-wave-v1"),
            _ => anyhow::bail!("unbound Xiao Shu motion action: {action}"),
        };
        let expires_at_unix_ms = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64
            + 10_000;
        let payload = serde_json::json!({
            "schema": ab_bridge::avatar_native::NATIVE_MOTION_OVERRIDE_SCHEMA,
            "expires_at_unix_ms": expires_at_unix_ms,
            "state": {"mode": mode},
            "plan": {
                "asset_route": format!("/avatar-surface/sidecar-spritesheet?asset={asset}")
            }
        });
        let temp_path = self.path.with_extension(format!("tmp-{}", std::process::id()));
        std::fs::write(&temp_path, serde_json::to_vec(&payload)?)
            .with_context(|| format!("write Avatar motion override {}", temp_path.display()))?;
        std::fs::rename(&temp_path, &self.path)
            .with_context(|| format!("publish Avatar motion override {}", self.path.display()))
    }
}

impl Drop for AvatarMotionOverrideGuard {
    fn drop(&mut self) {
        if let Err(err) = std::fs::remove_file(&self.path) {
            if err.kind() != std::io::ErrorKind::NotFound {
                eprintln!(
                    "agent-bridge could not clear Avatar motion override {}: {err}",
                    self.path.display()
                );
            }
        }
    }
}

struct AvatarActionCancellation {
    requested: std::sync::Arc<std::sync::atomic::AtomicBool>,
    task: tokio::task::JoinHandle<()>,
}

impl AvatarActionCancellation {
    fn install() -> Self {
        let requested = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
        let signal_flag = requested.clone();
        let task = tokio::spawn(async move {
            if tokio::signal::ctrl_c().await.is_ok() {
                signal_flag.store(true, std::sync::atomic::Ordering::SeqCst);
            }
        });
        Self { requested, task }
    }

    fn requested(&self) -> bool {
        self.requested.load(std::sync::atomic::Ordering::SeqCst)
    }

    fn token(&self) -> std::sync::Arc<std::sync::atomic::AtomicBool> {
        self.requested.clone()
    }
}

impl Drop for AvatarActionCancellation {
    fn drop(&mut self) {
        self.task.abort();
    }
}

fn avatar_pause_marker_present(path: Option<&std::path::Path>) -> bool {
    path.is_some_and(|path| std::fs::symlink_metadata(path).is_ok())
}

const AVATAR_ACTION_START_NOT_REACHED: u8 = 0;
const AVATAR_ACTION_START_AMBIGUOUS: u8 = 1;
const AVATAR_ACTION_START_RECORDED: u8 = 2;

#[derive(Clone, Debug, PartialEq, Eq)]
struct AvatarObserverTargetGeometry {
    target_rect: [i64; 4],
    workspace_rect: [i64; 4],
    workspace: String,
}

struct AvatarObserverActionConstraints {
    expected_target_node_id: i64,
    expected_identity: ab_bridge::avatar_focus_observer::FocusTargetIdentity,
    expected_geometry: AvatarObserverTargetGeometry,
    policy: ab_bridge::avatar_focus_observer::FocusObserverPolicy,
    cancellation: std::sync::Arc<std::sync::atomic::AtomicBool>,
    deadline: tokio::time::Instant,
    start_state: std::sync::Arc<std::sync::atomic::AtomicU8>,
}

fn avatar_action_cancel_reason(
    local: Option<&AvatarActionCancellation>,
    observer: Option<&AvatarObserverActionConstraints>,
) -> Option<&'static str> {
    if observer.is_some_and(|constraints| {
        constraints
            .cancellation
            .load(std::sync::atomic::Ordering::SeqCst)
    }) || local.is_some_and(AvatarActionCancellation::requested)
    {
        Some("sigint")
    } else if observer.is_some_and(|constraints| tokio::time::Instant::now() >= constraints.deadline)
    {
        Some("observer_duration_elapsed")
    } else {
        None
    }
}

fn avatar_action_io_timeout(
    default_timeout: std::time::Duration,
    observer: Option<&AvatarObserverActionConstraints>,
) -> Option<std::time::Duration> {
    let Some(constraints) = observer else {
        return Some(default_timeout);
    };
    let remaining = constraints
        .deadline
        .saturating_duration_since(tokio::time::Instant::now());
    (!remaining.is_zero()).then(|| remaining.min(default_timeout))
}

async fn avatar_action_sleep(
    duration: std::time::Duration,
    local: Option<&AvatarActionCancellation>,
    observer: Option<&AvatarObserverActionConstraints>,
) -> bool {
    let end = tokio::time::Instant::now() + duration;
    loop {
        if avatar_action_cancel_reason(local, observer).is_some() {
            return false;
        }
        let now = tokio::time::Instant::now();
        if now >= end {
            return true;
        }
        let mut chunk = end.saturating_duration_since(now).min(std::time::Duration::from_millis(50));
        if let Some(constraints) = observer {
            chunk = chunk.min(constraints.deadline.saturating_duration_since(now));
        }
        if chunk.is_zero() {
            return false;
        }
        tokio::time::sleep(chunk).await;
    }
}

#[allow(clippy::too_many_arguments)]
fn avatar_movement_step_failure(
    current_x: i64,
    current_y: i64,
    expected_x: i64,
    expected_y: i64,
    next_x: i64,
    next_y: i64,
    origin_x: i64,
    origin_y: i64,
    max_step_px: i64,
    max_travel_px: i64,
) -> Option<&'static str> {
    if (current_x - expected_x).abs() > 8 || (current_y - expected_y).abs() > 32 {
        Some("avatar_position_changed")
    } else if (next_x - current_x)
        .abs()
        .max((next_y - current_y).abs())
        > max_step_px
        || (next_x - origin_x)
            .abs()
            .max((next_y - origin_y).abs())
            > max_travel_px
    {
        Some("movement_path_bound_violation")
    } else {
        None
    }
}

#[allow(clippy::too_many_arguments)]
async fn execute_avatar_focus_follow_action(
    margin_px: i64,
    max_step_px: i64,
    max_travel_px: i64,
    step_interval_ms: u64,
    cancel_file: Option<&std::path::Path>,
    execute: bool,
    confirm: bool,
    reason: Option<&str>,
    observer_constraints: Option<&AvatarObserverActionConstraints>,
) -> Result<serde_json::Value> {
    let local_cancellation = observer_constraints
        .is_none()
        .then(AvatarActionCancellation::install);
    if observer_constraints.is_some()
        && avatar_action_cancel_reason(local_cancellation.as_ref(), observer_constraints).is_some()
    {
        anyhow::bail!("bounded observer action cancelled before preflight");
    }
    let avatar_app_id = ab_bridge::avatar_focus_follow::DEFAULT_AVATAR_APP_ID.to_string();
    let opts = ab_bridge::avatar_focus_follow::FocusFollowOptions {
        avatar_app_id: avatar_app_id.clone(),
        margin_px,
        max_step_px,
    };
    let initial_timeout = avatar_action_io_timeout(AVATAR_SWAY_READ_TIMEOUT, observer_constraints)
        .context("bounded observer deadline elapsed before action preflight")?;
    let tree = read_sway_tree_for_avatar_with_timeout(initial_timeout).await?;
    let mut plan = ab_bridge::avatar_focus_follow::focus_follow_plan_from_sway_tree(&tree, &opts);
    let cancel_file_text = cancel_file.map(|path| path.to_string_lossy().into_owned());
    let mut action = ab_bridge::avatar_focus_follow::focus_follow_action_preflight(
        &plan,
        execute,
        confirm,
        reason,
        max_travel_px,
        cancel_file_text.as_deref(),
    );

    let mut action_lock = None;
    if action.get("ready").and_then(serde_json::Value::as_bool) == Some(true) {
        let operation_directory = focus_follow_operation_directory()?;
        action_lock = AvatarExclusiveOperationLock::try_acquire(
            &operation_directory,
            AVATAR_FOCUS_ACTION_LOCK_FILE,
            "Avatar focus-follow action lock",
        )?;
        if action_lock.is_none() {
            action["status"] = serde_json::json!("suppressed");
            action["ready"] = serde_json::json!(false);
            action["blocked_reason"] = serde_json::json!("action_in_progress");
            action["executed"] = serde_json::json!(false);
            action["executed_steps"] = serde_json::json!(0);
            return Ok(action);
        }

        // A full tree read after taking the action lock closes the race between
        // observer decision and movement. The action always binds to the exact
        // target that was authorized by the caller's structured observation.
        let locked_timeout =
            avatar_action_io_timeout(AVATAR_SWAY_READ_TIMEOUT, observer_constraints)
                .context("bounded observer deadline elapsed before locked action recheck")?;
        let locked_tree = read_sway_tree_for_avatar_with_timeout(locked_timeout).await?;
        plan = ab_bridge::avatar_focus_follow::focus_follow_plan_from_sway_tree(&locked_tree, &opts);
        action = ab_bridge::avatar_focus_follow::focus_follow_action_preflight(
            &plan,
            execute,
            confirm,
            reason,
            max_travel_px,
            cancel_file_text.as_deref(),
        );
        if let Some(blocked_reason) = observer_constraints
            .and_then(|constraints| focus_observer_action_gate(&plan, constraints, true))
        {
            action["status"] = serde_json::json!("suppressed");
            action["ready"] = serde_json::json!(false);
            action["blocked_reason"] = serde_json::json!(blocked_reason);
            action["executed"] = serde_json::json!(false);
            action["executed_steps"] = serde_json::json!(0);
            return Ok(action);
        }
        if action.get("ready").and_then(serde_json::Value::as_bool) != Some(true) {
            action["executed"] = serde_json::json!(false);
            action["executed_steps"] = serde_json::json!(0);
            return Ok(action);
        }
        if let Some(constraints) = observer_constraints {
            constraints
                .start_state
                .store(AVATAR_ACTION_START_AMBIGUOUS, std::sync::atomic::Ordering::SeqCst);
        }
        let (mut outcome_guard, outcome_log_path) = AvatarOutcomeAttemptGuard::start(&mut action)?;
        if let Some(constraints) = observer_constraints {
            constraints
                .start_state
                .store(AVATAR_ACTION_START_RECORDED, std::sync::atomic::Ordering::SeqCst);
        }
        action["outcome_log_path"] = serde_json::json!(outcome_log_path);
        action["outcome_started_recorded"] = serde_json::json!(true);
        let target_id = plan
            .pointer("/target/node_id")
            .and_then(serde_json::Value::as_i64)
            .context("focus-follow target node id")?;
        let avatar_node_id = plan
            .pointer("/avatar/node_id")
            .and_then(serde_json::Value::as_i64)
            .context("focus-follow Avatar node id")?;
        let destination_x = plan
            .pointer("/avatar/destination_rect/x")
            .and_then(serde_json::Value::as_i64)
            .context("focus-follow destination x")?;
        let destination_y = plan
            .pointer("/avatar/destination_rect/y")
            .and_then(serde_json::Value::as_i64)
            .context("focus-follow destination y")?;
        let origin_x = plan
            .pointer("/avatar/current_rect/x")
            .and_then(serde_json::Value::as_i64)
            .context("focus-follow Avatar origin x")?;
        let origin_y = plan
            .pointer("/avatar/current_rect/y")
            .and_then(serde_json::Value::as_i64)
            .context("focus-follow Avatar origin y")?;
        let points = plan
            .pointer("/path/points")
            .and_then(serde_json::Value::as_array)
            .cloned()
            .unwrap_or_default();
        let mut executed_steps = 0_u64;
        let mut final_status = "completed";
        let mut stopped_reason: Option<&str> = None;
        let mut postcondition_verified = false;
        let mut expected_avatar_x = origin_x;
        let mut expected_avatar_y = origin_y;
        let bounded_step_px = max_step_px.clamp(8, 256);
        let bounded_travel_px = max_travel_px.clamp(48, 2_048);
        if avatar_pause_marker_present(cancel_file) {
            final_status = "cancelled";
            stopped_reason = Some("cancel_file_present");
        } else if let Some(reason) =
            avatar_action_cancel_reason(local_cancellation.as_ref(), observer_constraints)
        {
            final_status = "cancelled";
            stopped_reason = Some(reason);
        } else {
            let override_path = ab_bridge::avatar_native::default_native_motion_override_path()
                .context("XDG_RUNTIME_DIR is required for bounded Avatar motion override")?;
            let override_guard = AvatarMotionOverrideGuard::new(override_path.clone());
            let turn_action = plan
                .pointer("/choreography/0")
                .and_then(serde_json::Value::as_str)
                .context("focus-follow plan turn action")?;
            let walk_action = plan
                .pointer("/choreography/1")
                .and_then(serde_json::Value::as_str)
                .context("focus-follow plan walk action")?;
            action["execution_stage"] = serde_json::json!("turning");
            outcome_guard.observe(&action);
            override_guard.set(turn_action)?;
            if !avatar_action_sleep(
                std::time::Duration::from_millis(520),
                local_cancellation.as_ref(),
                observer_constraints,
            )
            .await
            {
                final_status = "cancelled";
                stopped_reason = avatar_action_cancel_reason(
                    local_cancellation.as_ref(),
                    observer_constraints,
                );
            } else {
                action["execution_stage"] = serde_json::json!("walking");
                outcome_guard.observe(&action);
                override_guard.set(walk_action)?;
            }

            for point in points {
                if final_status != "completed" {
                    break;
                }
                if let Some(reason) =
                    avatar_action_cancel_reason(local_cancellation.as_ref(), observer_constraints)
                {
                    final_status = "cancelled";
                    stopped_reason = Some(reason);
                    break;
                }
                if avatar_pause_marker_present(cancel_file) {
                    final_status = "cancelled";
                    stopped_reason = Some("cancel_file_present");
                    break;
                }
                let Some(read_timeout) =
                    avatar_action_io_timeout(AVATAR_SWAY_READ_TIMEOUT, observer_constraints)
                else {
                    final_status = "cancelled";
                    stopped_reason = Some("observer_duration_elapsed");
                    break;
                };
                let current_tree =
                    match read_sway_tree_for_avatar_with_timeout(read_timeout).await {
                        Ok(tree) => tree,
                        Err(error) => {
                            if let Some(reason) = avatar_action_cancel_reason(
                                local_cancellation.as_ref(),
                                observer_constraints,
                            ) {
                                final_status = "cancelled";
                                stopped_reason = Some(reason);
                                break;
                            }
                            return Err(error);
                        }
                    };
                let current_plan =
                    ab_bridge::avatar_focus_follow::focus_follow_plan_from_sway_tree(&current_tree, &opts);
                if let Some(reason) = observer_constraints
                    .and_then(|constraints| focus_observer_action_gate(&current_plan, constraints, false))
                {
                    final_status = "cancelled";
                    stopped_reason = Some(reason);
                    break;
                }
                if current_plan.pointer("/target/node_id").and_then(serde_json::Value::as_i64)
                    != Some(target_id)
                {
                    final_status = "cancelled";
                    stopped_reason = Some("focus_target_changed");
                    break;
                }
                if current_plan.pointer("/avatar/node_id").and_then(serde_json::Value::as_i64)
                    != Some(avatar_node_id)
                {
                    final_status = "failed";
                    stopped_reason = Some("avatar_identity_changed");
                    break;
                }
                let current_x = current_plan
                    .pointer("/avatar/current_rect/x")
                    .and_then(serde_json::Value::as_i64)
                    .context("current Avatar x during focus-follow")?;
                let current_y = current_plan
                    .pointer("/avatar/current_rect/y")
                    .and_then(serde_json::Value::as_i64)
                    .context("current Avatar y during focus-follow")?;
                let x = point.get("x").and_then(serde_json::Value::as_i64).context("path point x")?;
                let y = point.get("y").and_then(serde_json::Value::as_i64).context("path point y")?;
                if let Some(reason) = avatar_movement_step_failure(
                    current_x,
                    current_y,
                    expected_avatar_x,
                    expected_avatar_y,
                    x,
                    y,
                    origin_x,
                    origin_y,
                    bounded_step_px,
                    bounded_travel_px,
                ) {
                    final_status = if reason == "avatar_position_changed" {
                        "cancelled"
                    } else {
                        "failed"
                    };
                    stopped_reason = Some(reason);
                    break;
                }
                let Some(move_timeout) =
                    avatar_action_io_timeout(AVATAR_SWAY_MOVE_TIMEOUT, observer_constraints)
                else {
                    final_status = "cancelled";
                    stopped_reason = Some("observer_duration_elapsed");
                    break;
                };
                let moved = match move_avatar_exact_with_timeout(
                    avatar_node_id,
                    x,
                    y,
                    move_timeout,
                )
                .await
                {
                    Ok(moved) => moved,
                    Err(error) => {
                        if let Some(reason) = avatar_action_cancel_reason(
                            local_cancellation.as_ref(),
                            observer_constraints,
                        ) {
                            final_status = "cancelled";
                            stopped_reason = Some(reason);
                            break;
                        }
                        return Err(error);
                    }
                };
                if !moved {
                    final_status = "failed";
                    stopped_reason = Some("swaymsg_move_rejected");
                    break;
                }
                expected_avatar_x = x;
                expected_avatar_y = y;
                executed_steps += 1;
                action["executed"] = serde_json::json!(true);
                action["executed_steps"] = serde_json::json!(executed_steps);
                outcome_guard.observe(&action);
                if !avatar_action_sleep(
                    std::time::Duration::from_millis(step_interval_ms.clamp(32, 250)),
                    local_cancellation.as_ref(),
                    observer_constraints,
                )
                .await
                {
                    final_status = "cancelled";
                    stopped_reason = avatar_action_cancel_reason(
                        local_cancellation.as_ref(),
                        observer_constraints,
                    );
                    break;
                }
            }
            if final_status == "completed" {
                action["execution_stage"] = serde_json::json!("verifying_arrival");
                outcome_guard.observe(&action);
                let final_tree = match avatar_action_io_timeout(
                    AVATAR_SWAY_READ_TIMEOUT,
                    observer_constraints,
                ) {
                    Some(read_timeout) => match read_sway_tree_for_avatar_with_timeout(read_timeout).await {
                        Ok(tree) => tree,
                        Err(error) => {
                            if let Some(reason) = avatar_action_cancel_reason(
                                local_cancellation.as_ref(),
                                observer_constraints,
                            ) {
                                final_status = "cancelled";
                                stopped_reason = Some(reason);
                                serde_json::Value::Null
                            } else {
                                return Err(error);
                            }
                        }
                    },
                    None => {
                        final_status = "cancelled";
                        stopped_reason = Some("observer_duration_elapsed");
                        serde_json::Value::Null
                    }
                };
                if final_status == "completed" {
                    let final_plan =
                        ab_bridge::avatar_focus_follow::focus_follow_plan_from_sway_tree(&final_tree, &opts);
                    if let Some(reason) = observer_constraints.and_then(|constraints| {
                        focus_observer_action_gate(&final_plan, constraints, false)
                    }) {
                        final_status = "cancelled";
                        stopped_reason = Some(reason);
                    } else if let Some(reason) =
                    ab_bridge::avatar_focus_follow::focus_follow_arrival_failure_reason(
                        &final_plan,
                        target_id,
                        avatar_node_id,
                        destination_x,
                        destination_y,
                    )
                {
                    final_status = if reason == "focus_target_changed_at_arrival" {
                        "cancelled"
                    } else {
                        "failed"
                    };
                    stopped_reason = Some(reason);
                } else {
                    postcondition_verified = true;
                    action["postcondition_verified"] = serde_json::json!(true);
                    action["execution_stage"] = serde_json::json!("arrival_verified");
                    outcome_guard.observe(&action);
                }
                }
            }
            if final_status == "completed" {
                action["execution_stage"] = serde_json::json!("arriving");
                outcome_guard.observe(&action);
                override_guard.set("arrive_settle")?;
                if avatar_action_sleep(
                    std::time::Duration::from_millis(520),
                    local_cancellation.as_ref(),
                    observer_constraints,
                )
                .await
                {
                    action["execution_stage"] = serde_json::json!("acknowledging");
                    outcome_guard.observe(&action);
                    override_guard.set("wave")?;
                    let _ = avatar_action_sleep(
                        std::time::Duration::from_millis(960),
                        local_cancellation.as_ref(),
                        observer_constraints,
                    )
                    .await;
                }
            }
            action["motion_override_path"] = serde_json::json!(override_path);
            drop(override_guard);
        }
        action["preflight_ready"] = action["ready"].clone();
        action["ready"] = serde_json::json!(false);
        action["status"] = serde_json::json!(final_status);
        action["executed"] = serde_json::json!(executed_steps > 0);
        action["executed_steps"] = serde_json::json!(executed_steps);
        action["stopped_reason"] = serde_json::json!(stopped_reason);
        action["postcondition_verified"] = serde_json::json!(postcondition_verified);
        action["execution_stage"] = serde_json::json!(if final_status == "completed" {
            "completed"
        } else {
            final_status
        });
        outcome_guard.finish(&action)?;
        action["outcome_final_recorded"] = serde_json::json!(true);
        if final_status == "completed" && postcondition_verified {
            match write_focus_follow_ack_target(target_id, avatar_node_id, executed_steps) {
                Ok(receipt_path) => {
                    action["acknowledgement_recorded"] = serde_json::json!(true);
                    action["acknowledgement_receipt_path"] = serde_json::json!(receipt_path);
                    action["acknowledged_target_node_id"] = serde_json::json!(target_id);
                }
                Err(_) => {
                    // The movement and durable outcome are already complete.
                    // Expose only a closed persistence flag and let the
                    // observer's per-run attempted set prevent a duplicate.
                    action["acknowledgement_recorded"] = serde_json::json!(false);
                    action["acknowledgement_persistence_failed"] = serde_json::json!(true);
                }
            }
        }
    } else {
        action["executed"] = serde_json::json!(false);
        action["executed_steps"] = serde_json::json!(0);
    }

    drop(action_lock);
    Ok(action)
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_focus_follow_action(
    margin_px: i64,
    max_step_px: i64,
    max_travel_px: i64,
    step_interval_ms: u64,
    cancel_file: Option<&std::path::Path>,
    execute: bool,
    confirm: bool,
    reason: Option<&str>,
    as_json: bool,
) -> Result<()> {
    let action = execute_avatar_focus_follow_action(
        margin_px,
        max_step_px,
        max_travel_px,
        step_interval_ms,
        cancel_file,
        execute,
        confirm,
        reason,
        None,
    )
    .await?;
    cli::avatar_presentation::render_focus_follow_action(&action, as_json)?;
    Ok(())
}

fn focus_follow_operation_directory() -> Result<PathBuf> {
    focus_follow_runtime_dir()
}

fn resolve_focus_observer_pause_file(requested: Option<PathBuf>) -> Result<PathBuf> {
    let path = match requested {
        Some(path) => path,
        None => focus_follow_runtime_dir()?.join("ab-focus-follow-observer.pause"),
    };
    anyhow::ensure!(
        path.is_absolute() && path.file_name().is_some(),
        "Avatar focus observer pause file must be an absolute, non-root path"
    );
    let parent = path
        .parent()
        .context("Avatar focus observer pause file has no parent directory")?;
    validate_owner_private_directory(parent, "Avatar focus observer pause directory")?;
    Ok(path)
}

fn write_focus_follow_observer_receipt(receipt: &serde_json::Value) -> Result<()> {
    use std::io::Write;
    #[cfg(unix)]
    use std::os::unix::fs::OpenOptionsExt;

    let path = focus_follow_observer_receipt_path()?;
    let directory = path
        .parent()
        .context("Avatar focus observer receipt has no runtime directory")?;
    validate_real_directory(directory, "Avatar runtime directory")?;
    validate_regular_nonsymlink(&path, "Avatar focus observer receipt")?;
    let temp_path = path.with_extension(format!(
        "tmp-{}-{}",
        std::process::id(),
        uuid::Uuid::new_v4()
    ));
    let result = (|| -> Result<()> {
        let mut options = std::fs::OpenOptions::new();
        options.create_new(true).write(true);
        #[cfg(unix)]
        {
            options.mode(0o600);
            options.custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW);
        }
        let mut file = options
            .open(&temp_path)
            .with_context(|| format!("create Avatar focus observer receipt {}", temp_path.display()))?;
        enforce_private_regular_file(
            &file,
            &temp_path,
            "temporary Avatar focus observer receipt",
        )?;
        file.write_all(&serde_json::to_vec_pretty(receipt)?)
            .with_context(|| format!("write Avatar focus observer receipt {}", temp_path.display()))?;
        file.sync_all()
            .with_context(|| format!("sync Avatar focus observer receipt {}", temp_path.display()))?;
        std::fs::rename(&temp_path, &path)
            .with_context(|| format!("publish Avatar focus observer receipt {}", path.display()))?;
        sync_directory(directory, "Avatar runtime directory")?;
        Ok(())
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(&temp_path);
    }
    result
}



fn focus_observer_target_geometry_from_plan(
    plan: &serde_json::Value,
) -> Option<AvatarObserverTargetGeometry> {
    fn rect(value: &serde_json::Value) -> Option<[i64; 4]> {
        Some([
            value.get("x")?.as_i64()?,
            value.get("y")?.as_i64()?,
            value.get("width")?.as_i64()?,
            value.get("height")?.as_i64()?,
        ])
    }

    Some(AvatarObserverTargetGeometry {
        target_rect: rect(plan.pointer("/target/rect")?)?,
        workspace_rect: rect(plan.pointer("/target/workspace_rect")?)?,
        workspace: plan
            .pointer("/target/workspace")?
            .as_str()?
            .to_string(),
    })
}

fn focus_observer_action_gate(
    plan: &serde_json::Value,
    constraints: &AvatarObserverActionConstraints,
    include_travel_bounds: bool,
) -> Option<&'static str> {
    let status = plan
        .get("status")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("unknown");
    if plan
        .pointer("/target/node_id")
        .and_then(serde_json::Value::as_i64)
        != Some(constraints.expected_target_node_id)
    {
        return Some("focus_target_changed");
    }
    if status == "fullscreen_target"
        || plan
            .pointer("/target/fullscreen")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false)
    {
        return Some("observer_fullscreen_gate_activated");
    }
    if plan
        .pointer("/target/sensitive_mark")
        .and_then(serde_json::Value::as_bool)
        .unwrap_or(false)
    {
        return Some("observer_sensitive_gate_activated");
    }
    let identity = focus_observer_identity_from_plan(plan);
    if identity.is_missing() {
        return Some("observer_target_identity_missing");
    }
    if identity != constraints.expected_identity {
        return Some("observer_target_identity_changed");
    }
    if identity.is_sensitive(&constraints.policy) {
        return Some("observer_sensitive_gate_activated");
    }
    if focus_observer_target_geometry_from_plan(plan).as_ref()
        != Some(&constraints.expected_geometry)
    {
        return Some("observer_target_geometry_changed");
    }
    if !matches!(status, "planned" | "already_near_focus") {
        return Some("focus_follow_plan_not_actionable");
    }
    if include_travel_bounds {
        let Some(travel_px) = focus_observer_travel_px(plan) else {
            return Some("focus_follow_plan_missing_rects");
        };
        if travel_px < constraints.policy.min_travel_px {
            return Some("below_min_travel");
        }
        if travel_px > constraints.policy.max_travel_px {
            return Some("above_max_travel");
        }
    }
    None
}


fn focus_observer_action_busy(operation_directory: &std::path::Path) -> Result<bool> {
    match AvatarExclusiveOperationLock::try_acquire(
        operation_directory,
        AVATAR_FOCUS_ACTION_LOCK_FILE,
        "Avatar focus-follow action lock",
    )? {
        Some(lock) => {
            drop(lock);
            Ok(false)
        }
        None => Ok(true),
    }
}



#[allow(clippy::too_many_arguments)]
async fn run_avatar_focus_follow_observe(
    duration_ms: u64,
    poll_ms: u64,
    dwell_ms: u64,
    cooldown_secs: u64,
    failure_backoff_secs: u64,
    min_travel_px: i64,
    max_attempts: u64,
    max_travel_px: i64,
    margin_px: i64,
    max_step_px: i64,
    step_interval_ms: u64,
    pause_file: Option<PathBuf>,
    deny_app_ids: Vec<String>,
    execute: bool,
    as_json: bool,
) -> Result<()> {
    use ab_bridge::avatar_focus_observer::{
        focus_observer_plan_json, FocusAttemptOutcome, FocusObserverDecisionKind,
        FocusObserverPolicy, FocusObserverState,
    };

    let mut policy = FocusObserverPolicy {
        duration_ms,
        poll_ms,
        dwell_ms,
        cooldown_secs,
        failure_backoff_secs,
        min_travel_px,
        max_travel_px,
        max_attempts: u32::try_from(max_attempts).unwrap_or(u32::MAX),
        ..FocusObserverPolicy::default()
    };
    for identity in deny_app_ids
        .into_iter()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
    {
        policy.sensitive_wayland_app_ids.insert(identity.clone());
        policy.sensitive_xwayland_classes.insert(identity);
    }
    let policy = policy.normalized();

    // Dry-run preflight performs only bounded reads. It neither starts a loop
    // nor creates locks, receipts, journals, prompts, audio, or motion state.
    if !execute {
        let runtime_ready = focus_follow_runtime_dir()
            .and_then(|runtime| {
                validate_real_directory(&runtime, "Avatar runtime directory")?;
                resolve_focus_observer_pause_file(pause_file.clone())?;
                focus_follow_operation_directory()?;
                Ok(())
            })
            .is_ok()
            && read_sway_tree_for_avatar().await.is_ok();
        let mut plan = focus_observer_plan_json(&policy, false, runtime_ready);
        if !runtime_ready {
            plan["blocked_reason"] = serde_json::json!("runtime_unavailable");
        }
        return cli::avatar_presentation::render_focus_observer_json(&plan, as_json);
    }

    let runtime_directory = focus_follow_runtime_dir()?;
    validate_real_directory(&runtime_directory, "Avatar runtime directory")?;
    let pause_file = resolve_focus_observer_pause_file(pause_file)?;
    let operation_directory = focus_follow_operation_directory()?;
    let observer_lock = AvatarExclusiveOperationLock::try_acquire(
        &operation_directory,
        AVATAR_FOCUS_OBSERVER_LOCK_FILE,
        "Avatar focus observer lock",
    )?;
    let Some(_observer_lock) = observer_lock else {
        let mut plan = focus_observer_plan_json(&policy, true, false);
        plan["blocked_reason"] = serde_json::json!("observer_in_progress");
        return cli::avatar_presentation::render_focus_observer_json(&plan, as_json);
    };

    let started = tokio::time::Instant::now();
    let deadline = started + std::time::Duration::from_millis(policy.duration_ms);
    let mut state = FocusObserverState::new(policy.clone(), 0);
    // A writable private runtime receipt is a precondition for movement. This
    // initial running projection ensures storage failure is fail-closed.
    write_focus_follow_observer_receipt(&state.receipt_json(0))?;

    let cancellation = AvatarActionCancellation::install();
    let mut interval = tokio::time::interval(std::time::Duration::from_millis(policy.poll_ms));
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
    let opts = ab_bridge::avatar_focus_follow::FocusFollowOptions {
        avatar_app_id: ab_bridge::avatar_focus_follow::DEFAULT_AVATAR_APP_ID.to_string(),
        margin_px,
        max_step_px,
    };
    let mut consecutive_tree_failures = 0_u8;
    let mut consecutive_prestart_failures = 0_u8;
    let mut ack_cooldown_seeded = false;

    loop {
        tokio::select! {
            _ = interval.tick() => {}
            _ = tokio::time::sleep_until(deadline) => {
                state.observe(&focus_observer_terminal_context(policy.duration_ms));
                break;
            }
        }
        let observed_at_ms = started.elapsed().as_millis() as u64;
        if cancellation.requested() {
            state.cancel(observed_at_ms);
            break;
        }
        if observed_at_ms >= policy.duration_ms {
            state.observe(&focus_observer_terminal_context(observed_at_ms));
            break;
        }
        if state.backoff_remaining_ms(observed_at_ms) > 0 {
            continue;
        }

        let remaining = deadline.saturating_duration_since(tokio::time::Instant::now());
        if remaining.is_zero() {
            state.observe(&focus_observer_terminal_context(policy.duration_ms));
            break;
        }
        let tree = match read_sway_tree_for_avatar_with_timeout(
            remaining.min(AVATAR_SWAY_READ_TIMEOUT),
        )
        .await
        {
            Ok(tree) => {
                consecutive_tree_failures = 0;
                state.record_observation_success();
                tree
            }
            Err(_) => {
                if tokio::time::Instant::now() >= deadline {
                    state.observe(&focus_observer_terminal_context(policy.duration_ms));
                    break;
                }
                consecutive_tree_failures = consecutive_tree_failures.saturating_add(1);
                state.record_observation_failure(observed_at_ms);
                if consecutive_tree_failures >= 3 {
                    state.fail_runtime(observed_at_ms);
                    break;
                }
                continue;
            }
        };
        let plan = ab_bridge::avatar_focus_follow::focus_follow_plan_from_sway_tree(&tree, &opts);
        let acknowledgement = read_focus_follow_ack_receipt(&plan);
        if !ack_cooldown_seeded
            && plan
                .pointer("/avatar/node_id")
                .and_then(serde_json::Value::as_i64)
                .is_some()
        {
            if let Some(remaining_ms) = acknowledgement.as_ref().and_then(|receipt| {
                let now_unix_ms = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .ok()?
                    .as_millis() as u64;
                focus_follow_ack_cooldown_remaining_ms(
                    receipt,
                    policy.cooldown_secs.saturating_mul(1_000),
                    now_unix_ms,
                )
            }) {
                state.seed_cooldown_remaining(observed_at_ms, remaining_ms);
            }
            ack_cooldown_seeded = true;
        }
        let acknowledged_target = acknowledgement
            .as_ref()
            .and_then(|receipt| receipt.get("target_node_id"))
            .and_then(serde_json::Value::as_i64);
        let action_busy = match focus_observer_action_busy(&operation_directory) {
            Ok(busy) => busy,
            Err(_) => {
                state.fail_runtime(observed_at_ms);
                break;
            }
        };
        let context = focus_observer_context_from_plan(
            &plan,
            observed_at_ms,
            acknowledged_target,
            avatar_pause_marker_present(Some(&pause_file)),
            action_busy,
        );
        let decision = state.observe(&context);
        if decision.kind == FocusObserverDecisionKind::Stop {
            break;
        }
        if decision.kind != FocusObserverDecisionKind::Dispatch {
            continue;
        }
        let Some(target_node_id) = decision.target_node_id else {
            state.fail_runtime(observed_at_ms);
            break;
        };

        // Re-observe every structured gate immediately before dispatch. A
        // target change, pause, fullscreen transition, denylist match, or
        // competing action therefore suppresses this cycle without movement.
        let verification_remaining =
            deadline.saturating_duration_since(tokio::time::Instant::now());
        if verification_remaining.is_zero() {
            state.observe(&focus_observer_terminal_context(policy.duration_ms));
            break;
        }
        let verification_tree = match read_sway_tree_for_avatar_with_timeout(
            verification_remaining.min(AVATAR_SWAY_READ_TIMEOUT),
        )
        .await
        {
            Ok(tree) => {
                state.record_observation_success();
                tree
            }
            Err(_) => {
                if tokio::time::Instant::now() >= deadline {
                    state.observe(&focus_observer_terminal_context(policy.duration_ms));
                    break;
                }
                state.record_observation_failure(started.elapsed().as_millis() as u64);
                continue;
            }
        };
        let verification_plan =
            ab_bridge::avatar_focus_follow::focus_follow_plan_from_sway_tree(&verification_tree, &opts);
        let verification_time_ms = started.elapsed().as_millis() as u64;
        let verification_busy = match focus_observer_action_busy(&operation_directory) {
            Ok(busy) => busy,
            Err(_) => {
                state.fail_runtime(verification_time_ms);
                break;
            }
        };
        let verification_context = focus_observer_context_from_plan(
            &verification_plan,
            verification_time_ms,
            read_focus_follow_ack_target(&verification_plan),
            avatar_pause_marker_present(Some(&pause_file)),
            verification_busy,
        );
        let expected_identity = verification_context.identity.clone();
        let Some(expected_geometry) =
            focus_observer_target_geometry_from_plan(&verification_plan)
        else {
            state.record_observation_failure(verification_time_ms);
            continue;
        };
        let verification_decision = state.observe(&verification_context);
        if verification_decision.kind != FocusObserverDecisionKind::Dispatch
            || verification_decision.target_node_id != Some(target_node_id)
        {
            continue;
        }

        if state.start_attempt(target_node_id).is_err() {
            state.fail_runtime(verification_time_ms);
            break;
        }
        let start_state = std::sync::Arc::new(std::sync::atomic::AtomicU8::new(
            AVATAR_ACTION_START_NOT_REACHED,
        ));
        let constraints = AvatarObserverActionConstraints {
            expected_target_node_id: target_node_id,
            expected_identity,
            expected_geometry,
            policy: policy.clone(),
            cancellation: cancellation.token(),
            deadline,
            start_state: start_state.clone(),
        };
        let action = execute_avatar_focus_follow_action(
            margin_px,
            max_step_px,
            max_travel_px,
            step_interval_ms,
            Some(&pause_file),
            true,
            false,
            Some("stable_focus_transition"),
            Some(&constraints),
        )
        .await;
        let action_start_state = start_state.load(std::sync::atomic::Ordering::SeqCst);
        let proven_unstarted = action.as_ref().is_ok_and(|action| {
            action
                .get("outcome_started_recorded")
                .and_then(serde_json::Value::as_bool)
                != Some(true)
        }) || (action.is_err() && action_start_state == AVATAR_ACTION_START_NOT_REACHED);
        if proven_unstarted {
            if state.discard_unstarted_attempt(target_node_id).is_err() {
                state.fail_runtime(started.elapsed().as_millis() as u64);
                break;
            }
            if cancellation.requested() {
                state.cancel(started.elapsed().as_millis() as u64);
                break;
            }
            let after_action_ms = started.elapsed().as_millis() as u64;
            if after_action_ms >= policy.duration_ms {
                state.observe(&focus_observer_terminal_context(after_action_ms));
                break;
            }
            if action.is_err() {
                consecutive_prestart_failures = consecutive_prestart_failures.saturating_add(1);
                state.record_prestart_runtime_failure(after_action_ms);
                if consecutive_prestart_failures >= 3 {
                    state.fail_runtime(after_action_ms);
                    break;
                }
            } else {
                consecutive_prestart_failures = 0;
                state.record_prestart_runtime_success();
            }
            continue;
        }
        consecutive_prestart_failures = 0;
        state.record_prestart_runtime_success();
        let outcome = match action {
            Ok(action)
                if action.get("status").and_then(serde_json::Value::as_str)
                    == Some("completed")
                    && action
                        .get("postcondition_verified")
                        .and_then(serde_json::Value::as_bool)
                        == Some(true) => FocusAttemptOutcome::CompletedVerified,
            Ok(action)
                if action.get("status").and_then(serde_json::Value::as_str)
                    == Some("cancelled") => FocusAttemptOutcome::Cancelled,
            Ok(_) | Err(_) => FocusAttemptOutcome::Failed,
        };
        let finished_at_ms = started.elapsed().as_millis() as u64;
        if state
            .finish_attempt(target_node_id, outcome, finished_at_ms)
            .is_err()
        {
            state.fail_runtime(finished_at_ms);
            break;
        }
        if cancellation.requested() {
            state.cancel(finished_at_ms);
            break;
        }
        if finished_at_ms >= policy.duration_ms {
            state.observe(&focus_observer_terminal_context(finished_at_ms));
            break;
        }
        if state.attempt_count() >= policy.max_attempts {
            state.observe(&focus_observer_terminal_context(finished_at_ms));
            break;
        }
    }

    let receipt = state.receipt_json(started.elapsed().as_millis() as u64);
    write_focus_follow_observer_receipt(&receipt)?;
    cli::avatar_presentation::render_focus_observer_json(&receipt, as_json)
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
    draggable: bool,
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
        draggable,
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

#[allow(clippy::too_many_arguments)]
async fn run_avatar_linux_live(
    project: Option<String>,
    role: String,
    pet_id: Option<String>,
    session_id: Option<String>,
    agent_id: Option<String>,
    runtime: String,
    cwd: Option<PathBuf>,
    duration_ms: u64,
    heartbeat_interval_secs: u64,
    state_poll_ms: u64,
    voice_feedback: bool,
    voice_backend: String,
    qwen_worker: Option<PathBuf>,
    voice_python: String,
    voice_script: Option<PathBuf>,
    voice_name: String,
    voice_instruct: String,
    voice_sink: Option<String>,
    voice_cooldown_secs: i64,
    voice_max_utterances: u64,
    width: u32,
    height: u32,
    anchor: String,
    margin_top: i32,
    margin_right: i32,
    margin_bottom: i32,
    margin_left: i32,
    output: Option<String>,
    dry_run: bool,
    as_json: bool,
) -> Result<()> {
    let cwd = cwd.unwrap_or(avatar_current_cwd()?);
    let project = avatar_project_slug(project, &cwd);
    let project_component = launchd_label_component(&project);
    let session_id = session_id
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| format!("com.agentbridge.avatar-live.{project_component}"));
    let agent_id = agent_id
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| session_id.clone());
    let pet_id = ab_bridge::pet_state::normalize_pet_id(pet_id.as_deref());
    let pet_state = ab_bridge::pet_state::read_pet_state(&pet_id)
        .with_context(|| format!("read Linux live pet sidecar for {pet_id}"))?
        .ok_or_else(|| {
            anyhow::anyhow!(
                "Linux live embodiment requires pet sidecar {}",
                ab_bridge::pet_state::pet_state_path(&pet_id).display()
            )
        })?;
    let mode = pet_state
        .get("mode")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or("idle");
    let anchor = ab_bridge::avatar_native::parse_native_anchor(&anchor).ok_or_else(|| {
        anyhow::anyhow!(
            "invalid --anchor; expected top-left, top-right, bottom-left, or bottom-right"
        )
    })?;
    let duration_ms = duration_ms.clamp(1_000, 86_400_000);
    let heartbeat_interval_secs = heartbeat_interval_secs.clamp(5, 300);
    let state_poll_ms = state_poll_ms.clamp(100, 5_000);
    let voice_cooldown_secs = voice_cooldown_secs.clamp(30, 3_600);
    let voice_max_utterances = voice_max_utterances.clamp(1, 10);
    let voice_script = voice_script.unwrap_or_else(|| {
        ab_bridge::avatar_live_voice::default_script_path(
            std::env::var_os("HOME")
                .as_deref()
                .map(std::path::Path::new),
        )
    });
    let voice_config = ab_bridge::avatar_live_voice::LinuxLiveVoiceConfig {
        enabled: voice_feedback,
        backend: voice_backend.trim().to_string(),
        python: voice_python.trim().to_string(),
        script_path: voice_script,
        qwen_worker: qwen_worker.unwrap_or_default(),
        voice: voice_name.trim().to_string(),
        instruct: voice_instruct.trim().to_string(),
        sink: voice_sink,
        cooldown_secs: voice_cooldown_secs,
        max_utterances: voice_max_utterances,
        agent_id: agent_id.clone(),
    };
    let voice_plan = ab_bridge::avatar_live_voice::plan_json(&voice_config);

    let mut renderer_opts = ab_bridge::avatar_native::NativeTransparentOptions {
        width,
        height,
        layer: ab_bridge::avatar_native::NativeLayer::Overlay,
        anchor,
        margin_top,
        margin_right,
        margin_bottom,
        margin_left,
        duration_ms,
        sprite_asset: ab_bridge::avatar_native::native_sprite_asset_for_mode(mode),
        state_pet_id: Some(pet_id.clone()),
        state_poll_ms,
        output,
        ..ab_bridge::avatar_native::NativeTransparentOptions::default()
    };
    let sprite_plan = ab_bridge::avatar_native::native_sprite_plan_from_state_value(&pet_state);
    ab_bridge::avatar_native::apply_native_sprite_plan(&mut renderer_opts, &sprite_plan);

    let presence_args = json!({
        "pet_id": pet_id,
        "session_id": session_id,
        "agent_id": agent_id,
        "project": project,
        "role": role,
        "tag": "linux-live",
        "runtime": runtime,
        "cwd": cwd.display().to_string(),
        "auto_tag": false,
    });
    let compositor = ab_bridge::avatar_floater::detect_compositor();
    let backend = ab_bridge::avatar_floater::recommend_backend(&compositor);
    let native_compiled = cfg!(all(target_os = "linux", feature = "linux-native-avatar"));
    let renderer_plan = ab_bridge::avatar_native::native_transparent_plan_json(
        &renderer_opts,
        false,
    );
    let plan = cli::avatar_live_view::linux_live_plan(
        native_compiled,
        &backend,
        &presence_args,
        heartbeat_interval_secs,
        &renderer_plan,
        &voice_plan,
        state_poll_ms,
        voice_feedback,
    );

    if dry_run {
        cli::avatar_live_view::render_linux_live_plan(&plan, &presence_args, duration_ms, heartbeat_interval_secs, voice_feedback, as_json)?;
        return Ok(());
    }

    if !native_compiled {
        anyhow::bail!(
            "avatar linux-live requires a Linux build with the linux-native-avatar feature"
        );
    }
    if backend.backend != ab_bridge::avatar_floater::AvatarBackend::NativeTransparent {
        anyhow::bail!(
            "avatar linux-live requires the verified native transparent backend: {}",
            backend.reason
        );
    }
    if voice_feedback
        && !voice_plan
            .get("ready")
            .and_then(Value::as_bool)
            .unwrap_or(false)
    {
        anyhow::bail!(
            "avatar linux-live voice feedback requires a ready audio adapter and explicit qwen3 or qwen3-lan configuration"
        );
    }

    let store = SqliteStore::open(&default_db_path())
        .await
        .context("open state.db for Linux avatar live presence")?;
    let mut last_presence = ab_bridge::pet_presence::sync_pet_presence(
        &store,
        presence_args.clone(),
    )
            .await
            .context("initial Linux avatar live presence sync")?;
    let mut heartbeat_count = 1_u64;
    let mut heartbeat_failures = 0_u64;
    let mut last_heartbeat_error: Option<String> = None;
    let started = std::time::Instant::now();

    if !as_json {
        println!(
            "Linux avatar live started project={} pet_id={} session_id={} duration_ms={}",
            presence_args["project"],
            presence_args["pet_id"],
            presence_args["session_id"],
            duration_ms
        );
    }

    let renderer_opts_for_run = renderer_opts.clone();
    let observation_pet_id = pet_id.clone();
    let observation_initial_mode = ab_bridge::avatar_live_voice::lifecycle_mode(&pet_state);
    let observation_task = tokio::spawn(async move {
        run_linux_live_observation(
            observation_pet_id,
            observation_initial_mode,
            duration_ms,
            state_poll_ms,
        )
        .await
    });
    let voice_task = if voice_feedback {
        let voice_config = voice_config.clone();
        let voice_pet_id = pet_id.clone();
        let initial_mode = ab_bridge::avatar_live_voice::lifecycle_mode(&pet_state);
        Some(tokio::spawn(async move {
            run_linux_live_voice_feedback(
                voice_config,
                voice_pet_id,
                initial_mode,
                duration_ms,
                state_poll_ms,
            )
            .await
        }))
    } else {
        None
    };
    let mut renderer = tokio::task::spawn_blocking(move || {
        ab_bridge::avatar_native::run_native_transparent_probe(renderer_opts_for_run)
    });
    let mut heartbeat = tokio::time::interval_at(
        tokio::time::Instant::now()
            + std::time::Duration::from_secs(heartbeat_interval_secs),
        std::time::Duration::from_secs(heartbeat_interval_secs),
    );
    heartbeat.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);

    let renderer_result = loop {
        tokio::select! {
            result = &mut renderer => break result,
            _ = heartbeat.tick() => {
                match ab_bridge::pet_presence::sync_pet_presence(&store, presence_args.clone()).await {
                    Ok(payload) => {
                        heartbeat_count += 1;
                        last_presence = payload;
                    }
                    Err(error) => {
                        heartbeat_failures += 1;
                        last_heartbeat_error = Some(error.to_string());
                    }
                }
            }
        }
    };
    renderer_result.context("join Linux avatar native renderer")??;

    let observation_receipt = observation_task
        .await
        .context("join Linux avatar live observation loop")?;

    let voice_receipt = match voice_task {
        Some(task) => task
            .await
            .context("join Linux avatar sparse voice loop")?,
        None => json!({
            "surface": "linux_avatar_live_voice_receipt",
            "schema": 1,
            "enabled": false,
            "utterance_count": 0,
            "emits_audio": false,
        }),
    };

    match ab_bridge::pet_presence::sync_pet_presence(&store, presence_args.clone()).await {
        Ok(payload) => {
            heartbeat_count += 1;
            last_presence = payload;
        }
        Err(error) => {
            heartbeat_failures += 1;
            last_heartbeat_error = Some(error.to_string());
        }
    }

    let elapsed_ms = started.elapsed().as_millis() as u64;
    let completed_renderer_plan =
        ab_bridge::avatar_native::native_transparent_plan_json(&renderer_opts, true);
    let receipt = cli::avatar_live_view::linux_live_receipt(
        elapsed_ms,
        &presence_args,
        heartbeat_count,
        heartbeat_failures,
        &last_heartbeat_error,
        &last_presence,
        &completed_renderer_plan,
        &voice_receipt,
        &observation_receipt,
        &plan,
    );

    cli::avatar_live_view::render_linux_live_receipt(
        &receipt,
        heartbeat_count,
        heartbeat_failures,
        as_json,
    )?;
    Ok(())
}

async fn run_linux_live_observation(
    pet_id: String,
    initial_mode: String,
    duration_ms: u64,
    poll_ms: u64,
) -> Value {
    let started = tokio::time::Instant::now();
    let deadline = started + std::time::Duration::from_millis(duration_ms);
    let mut poll = tokio::time::interval(std::time::Duration::from_millis(poll_ms));
    poll.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
    let mut observation = ab_bridge::avatar_live_observation::LiveObservation::new(initial_mode);
    loop {
        tokio::select! {
            _ = tokio::time::sleep_until(deadline) => break,
            _ = poll.tick() => {
                let elapsed = started.elapsed();
                match ab_bridge::pet_state::read_pet_state(&pet_id) {
                    Ok(Some(state)) => observation.observe(
                        &ab_bridge::avatar_live_voice::lifecycle_mode(&state),
                        elapsed,
                    ),
                    Ok(None) | Err(_) => observation.record_read_failure(elapsed),
                }
            }
        }
    }
    observation.receipt(poll_ms, started.elapsed())
}

#[allow(clippy::too_many_arguments)]
async fn run_avatar_voice_observe(
    pet_id: Option<String>,
    agent_id: Option<String>,
    duration_ms: u64,
    state_poll_ms: u64,
    voice_backend: String,
    qwen_worker: Option<PathBuf>,
    voice_python: String,
    voice_script: Option<PathBuf>,
    voice_name: String,
    voice_instruct: String,
    voice_sink: Option<String>,
    voice_cooldown_secs: i64,
    voice_max_utterances: u64,
    dry_run: bool,
    as_json: bool,
) -> Result<()> {
    let pet_id = ab_bridge::pet_state::normalize_pet_id(pet_id.as_deref());
    let state = ab_bridge::pet_state::read_pet_state(&pet_id)
        .with_context(|| format!("read voice observer pet sidecar for {pet_id}"))?
        .ok_or_else(|| {
            anyhow::anyhow!(
                "Avatar voice observer requires pet sidecar {}",
                ab_bridge::pet_state::pet_state_path(&pet_id).display()
            )
        })?;
    let duration_ms = duration_ms.clamp(1_000, 86_400_000);
    let state_poll_ms = state_poll_ms.clamp(100, 5_000);
    let voice_cooldown_secs = voice_cooldown_secs.clamp(30, 3_600);
    let voice_max_utterances = voice_max_utterances.clamp(1, 10);
    let voice_script = voice_script.unwrap_or_else(|| {
        ab_bridge::avatar_live_voice::default_script_path(
            std::env::var_os("HOME")
                .as_deref()
                .map(std::path::Path::new),
        )
    });
    let agent_id = agent_id
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| format!("com.agentbridge.avatar-voice.{pet_id}"));
    let voice_config = ab_bridge::avatar_live_voice::LinuxLiveVoiceConfig {
        enabled: true,
        backend: voice_backend.trim().to_string(),
        python: voice_python.trim().to_string(),
        script_path: voice_script,
        qwen_worker: qwen_worker.unwrap_or_default(),
        voice: voice_name.trim().to_string(),
        instruct: voice_instruct.trim().to_string(),
        sink: voice_sink,
        cooldown_secs: voice_cooldown_secs,
        max_utterances: voice_max_utterances,
        agent_id,
    };
    let voice_plan = ab_bridge::avatar_live_voice::plan_json(&voice_config);
    let ready = voice_plan
        .get("ready")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let plan = cli::avatar_live_view::voice_observer_plan(
        ready,
        &pet_id,
        &ab_bridge::avatar_live_voice::lifecycle_mode(&state),
        duration_ms,
        state_poll_ms,
        &voice_plan,
    );

    if dry_run {
        cli::avatar_live_view::render_voice_observer_plan(&plan, ready, &pet_id, duration_ms, as_json)?;
        return Ok(());
    }
    if !ready {
        anyhow::bail!(
            "avatar voice-observe requires a ready audio adapter and explicit qwen3 or qwen3-lan configuration"
        );
    }

    let started = tokio::time::Instant::now();
    let voice_receipt = run_linux_live_voice_feedback(
        voice_config,
        pet_id.clone(),
        ab_bridge::avatar_live_voice::lifecycle_mode(&state),
        duration_ms,
        state_poll_ms,
    )
    .await;
    let elapsed_ms = started.elapsed().as_millis().min(u64::MAX as u128) as u64;
    let receipt =
        cli::avatar_live_view::voice_observer_receipt(&pet_id, elapsed_ms, &voice_receipt, &plan);

    cli::avatar_live_view::render_voice_observer_receipt(&receipt, &pet_id, as_json)?;
    Ok(())
}

async fn run_linux_live_voice_feedback(
    config: ab_bridge::avatar_live_voice::LinuxLiveVoiceConfig,
    pet_id: String,
    initial_mode: String,
    duration_ms: u64,
    poll_ms: u64,
) -> Value {
    let started = tokio::time::Instant::now();
    let deadline = started + std::time::Duration::from_millis(duration_ms);
    let mut poll = tokio::time::interval(std::time::Duration::from_millis(poll_ms));
    poll.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
    let mut previous_mode = initial_mode;
    let mut last_spoken_at: Option<i64> = None;
    let mut transition_count = 0_u64;
    let mut invocation_count = 0_u64;
    let mut utterance_count = 0_u64;
    let mut failure_count = 0_u64;
    let mut invocation_elapsed_ms_total = 0_u64;
    let mut invocation_elapsed_ms_max = 0_u64;
    let mut last_decision = Value::Null;
    let mut last_adapter_receipt = Value::Null;

    loop {
        tokio::select! {
            _ = tokio::time::sleep_until(deadline) => break,
            _ = poll.tick() => {
                let state = match ab_bridge::pet_state::read_pet_state(&pet_id) {
                    Ok(Some(state)) => state,
                    Ok(None) => {
                        failure_count += 1;
                        last_adapter_receipt = json!({"status": "error", "detail": "pet sidecar disappeared"});
                        continue;
                    }
                    Err(error) => {
                        failure_count += 1;
                        last_adapter_receipt = json!({"status": "error", "detail": error.to_string()});
                        continue;
                    }
                };
                let mode = ab_bridge::avatar_live_voice::lifecycle_mode(&state);
                let changed = mode != previous_mode;
                let now = linux_live_unix_time_secs();
                let decision = ab_bridge::avatar_live_voice::transition_decision(
                    &config,
                    &previous_mode,
                    &state,
                    last_spoken_at,
                    now,
                    utterance_count,
                    false,
                );
                if changed {
                    transition_count += 1;
                    previous_mode = mode;
                }
                let should_invoke = decision
                    .get("should_invoke")
                    .and_then(Value::as_bool)
                    .unwrap_or(false);
                last_decision = decision.clone();
                if !should_invoke {
                    continue;
                }
                invocation_count += 1;
                let invocation_started = tokio::time::Instant::now();
                let invocation_config = config.clone();
                let args = ab_bridge::avatar_live_voice::invocation_args(
                    &invocation_config,
                    &decision,
                    last_spoken_at,
                );
                let receipt = match tokio::task::spawn_blocking(move || {
                    invoke_linux_live_voice_adapter(&invocation_config, &args)
                }).await {
                    Ok(receipt) => receipt,
                    Err(error) => json!({
                        "status": "error",
                        "detail": format!("voice adapter task failed: {error}"),
                    }),
                };
                let invocation_elapsed_ms = invocation_started
                    .elapsed()
                    .as_millis()
                    .min(u64::MAX as u128) as u64;
                invocation_elapsed_ms_total =
                    invocation_elapsed_ms_total.saturating_add(invocation_elapsed_ms);
                invocation_elapsed_ms_max = invocation_elapsed_ms_max.max(invocation_elapsed_ms);
                if ab_bridge::avatar_live_voice::adapter_receipt_emitted(&receipt) {
                    utterance_count += 1;
                    last_spoken_at = Some(linux_live_unix_time_secs());
                } else {
                    failure_count += 1;
                }
                last_adapter_receipt = linux_live_voice_receipt_summary(&receipt);
            }
        }
    }

    json!({
        "surface": "linux_avatar_live_voice_receipt",
        "schema": 1,
        "enabled": true,
        "backend": config.backend,
        "transition_count": transition_count,
        "invocation_count": invocation_count,
        "utterance_count": utterance_count,
        "failure_count": failure_count,
        "invocation_latency_ms": {
            "count": invocation_count,
            "average": if invocation_count > 0 {
                Some(invocation_elapsed_ms_total / invocation_count)
            } else {
                None
            },
            "max": if invocation_count > 0 { Some(invocation_elapsed_ms_max) } else { None },
        },
        "emits_audio": utterance_count > 0,
        "cooldown_secs": config.cooldown_secs,
        "max_utterances": config.max_utterances,
        "last_spoken_at": last_spoken_at,
        "last_decision": last_decision,
        "last_adapter_receipt": last_adapter_receipt,
        "continuous_listening": false,
    })
}

fn invoke_linux_live_voice_adapter(
    config: &ab_bridge::avatar_live_voice::LinuxLiveVoiceConfig,
    args: &[String],
) -> Value {
    let output = match std::process::Command::new(&config.python).args(args).output() {
        Ok(output) => output,
        Err(error) => {
            return json!({
                "status": "error",
                "detail": format!("spawn audio adapter failed: {error}"),
            })
        }
    };
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    let mut receipt = stdout
        .lines()
        .rev()
        .find(|line| !line.trim().is_empty())
        .and_then(|line| serde_json::from_str::<Value>(line).ok())
        .unwrap_or_else(|| {
            json!({
                "status": "error",
                "detail": "audio adapter returned no JSON receipt",
            })
        });
    if let Some(object) = receipt.as_object_mut() {
        object.insert("process_success".to_string(), json!(output.status.success()));
        object.insert("process_exit_code".to_string(), json!(output.status.code()));
        if !stderr.trim().is_empty() {
            object.insert(
                "stderr_preview".to_string(),
                json!(stderr.chars().take(500).collect::<String>()),
            );
        }
    }
    receipt
}

fn linux_live_voice_receipt_summary(receipt: &Value) -> Value {
    let mut summary = serde_json::Map::new();
    for key in [
        "status",
        "verify_status",
        "verified_to",
        "not_verified",
        "play_ok",
        "tier",
        "decision",
        "worker_protocol",
        "worker_engine",
        "qwen_model",
        "qwen_device",
        "qwen_dtype",
        "process_success",
        "process_exit_code",
    ] {
        if let Some(value) = receipt.get(key) {
            summary.insert(key.to_string(), value.clone());
        }
    }
    if let Some(detail) = receipt.get("detail").and_then(Value::as_str) {
        summary.insert(
            "detail".to_string(),
            json!(detail.chars().take(500).collect::<String>()),
        );
    }
    Value::Object(summary)
}

fn linux_live_unix_time_secs() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|duration| duration.as_secs().min(i64::MAX as u64) as i64)
        .unwrap_or(0)
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

    ab_bridge::avatar_cortex::require_avatar_cortex_replay_capability()?;

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
    ab_bridge::avatar_health::resolve_heartbeat_health_identity(
        label.as_deref(),
        project.as_deref(),
    )?;
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
        "binary.path={} exists={} supports_sync_presence={} supports_heartbeat_health={} missing_command={} configured_sync_presence={} probe_mode={} executable_invoked={}",
        avatar_health_display(binary.get("path"), "-"),
        avatar_health_display(binary.get("exists"), "false"),
        avatar_health_display(binary.get("supports_sync_presence"), "unknown"),
        avatar_health_display(binary.get("supports_heartbeat_health"), "unknown"),
        avatar_health_display(binary.get("missing_command"), "false"),
        avatar_health_display(binary.get("configured_sync_presence"), "false"),
        avatar_health_display(binary.get("probe_mode"), "unknown"),
        avatar_health_display(binary.get("executable_invoked"), "false")
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
    ab_bridge::avatar_health::resolve_heartbeat_health_identity(
        label.as_deref(),
        project.as_deref(),
    )?;
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

fn read_optional_json_file(path: Option<&std::path::Path>, label: &str) -> Result<Option<Value>> {
    let Some(path) = path else {
        return Ok(None);
    };
    let body = std::fs::read_to_string(path)
        .map_err(|e| anyhow::anyhow!("read opt-in {label} JSON at {path:?}: {e}"))?;
    serde_json::from_str(&body)
        .map(Some)
        .map_err(|e| anyhow::anyhow!("parse opt-in {label} JSON at {path:?}: {e}"))
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
    run_biocortex_retrieval_opt_in_store_trial_result(payload, as_json)
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

fn cli_env_falsey(key: &str) -> bool {
    std::env::var(key)
        .ok()
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "0" | "false" | "no" | "off"
            )
        })
        .unwrap_or(false)
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

    run_biocortex_retrieval_opt_in_controlled_order_fixture_result(payload, as_json)
}

fn build_biocortex_retrieval_opt_in_evidence_summary(
    batch_diagnostics_json: &std::path::Path,
    controlled_order_fixture_run_json: &std::path::Path,
    runtime_readiness_packet_json: Option<&std::path::Path>,
    reviewer: Option<String>,
    commit: Option<String>,
    forum_post_id: Option<String>,
    memory_key: Option<String>,
) -> Result<Value> {
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

    Ok(payload)
}

fn build_biocortex_retrieval_opt_in_redacted_evidence_aggregate(
    movement_fixture_run_json: &std::path::Path,
    coverage_fixture_run_json: &std::path::Path,
    reviewer: Option<String>,
    commit: Option<String>,
    forum_post_id: Option<String>,
    memory_key: Option<String>,
) -> Result<Value> {
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

    Ok(payload)
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
    let cli::worktree_session_view::SessionPlan { branch, path } =
        cli::worktree_session_view::plan_new_session(&repo_root, name, ts);

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

    let shown = cli::worktree_session_view::render_session_rows(&out.stdout);
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
            let generated_at = chrono_now_utc_string();
            let html = render_promote_html(min_count, limit, dry_run, &path, &[], &generated_at);
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
        let generated_at = chrono_now_utc_string();
        let html = render_promote_html(
            min_count,
            limit,
            dry_run,
            &path,
            &decisions,
            &generated_at,
        );
        std::fs::write(p, html).map_err(|e| anyhow::anyhow!("write html report to {p:?}: {e}"))?;
        println!("html report: {}", p.display());
    }
    Ok(())
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
/// `run_dream_decay_unused`. Moves `importance` a `step` fraction of its
/// remaining headroom toward `ceiling` (`importance += step·(ceiling −
/// importance)`) for every active row with `access_count >= min_access`
/// and `last_accessed_at` within `window_days`. Multiplicative (not flat
/// additive) so repeat reinforcement asymptotes toward — never pins at —
/// the ceiling, preserving intra-tier ordering (2026-06-30 saturation fix).
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
    println!(
        "  at importance ceiling: {}    ({:.0}% — reinforce-saturated)",
        stats.n_ceiling_importance,
        if stats.total_active > 0 {
            100.0 * stats.n_ceiling_importance as f64 / stats.total_active as f64
        } else {
            0.0
        }
    );
    println!(
        "  top-50 distinct imp  : {}    ({} — 1-2 = ceiling collapse, top-tier has no ordering)",
        stats.top_distinct_importance,
        if stats.top_distinct_importance <= 2 {
            "COLLAPSED"
        } else {
            "ok"
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
        let generated_at = chrono_now_utc_string();
        let html = render_codebase_report_html(&stats, &db_path, &generated_at);
        std::fs::write(p, html).map_err(|e| anyhow::anyhow!("write html report to {p:?}: {e}"))?;
        println!();
        println!("html report: {}", p.display());
    }
    Ok(())
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
    triage: &'static str,
    triage_reason: &'static str,
    snippet: String,
    proposal_key: String,
    skipped: bool,
}

#[derive(Debug, serde::Serialize)]
struct AgentMdDriftSkipped {
    lesson_key: String,
    coverage_ratio: f64,
    triage: &'static str,
    triage_reason: &'static str,
    snippet: String,
}

#[derive(Debug, serde::Serialize)]
struct AgentMdDriftReport {
    agent_md_path: String,
    agent_md_bytes: usize,
    window_days: u32,
    lessons_scanned: usize,
    covered: usize,
    skipped: usize,
    skipped_by_triage: std::collections::BTreeMap<&'static str, usize>,
    skipped_samples: Vec<AgentMdDriftSkipped>,
    proposed: usize,
    proposals: Vec<AgentMdDriftProposal>,
    dry_run: bool,
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
    let mut skipped_samples: Vec<AgentMdDriftSkipped> = Vec::new();
    let mut skipped_by_triage = std::collections::BTreeMap::new();
    let mut covered = 0usize;
    let mut skipped = 0usize;
    let mut proposed = 0usize;

    for lesson in &recent {
        let lesson_tokens = drift_tokens(&lesson.content);
        let ratio = drift_coverage_ratio(&lesson_tokens, &preamble_tokens);
        if ratio >= AGENT_MD_DRIFT_COVERAGE_THRESHOLD {
            covered += 1;
            continue;
        }
        let snippet: String = lesson.content.chars().take(140).collect();
        let triage = triage_agent_md_drift_candidate(&lesson.key, &lesson.tags, &lesson.content);
        if !triage.accept {
            skipped += 1;
            *skipped_by_triage.entry(triage.kind).or_insert(0) += 1;
            if skipped_samples.len() < 12 {
                skipped_samples.push(AgentMdDriftSkipped {
                    lesson_key: lesson.key.clone(),
                    coverage_ratio: ratio,
                    triage: triage.kind,
                    triage_reason: triage.reason,
                    snippet,
                });
            }
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

        let written = if dry_run {
            true // pretend; nothing actually persisted
        } else {
            let stored_content = format!(
                "AGENT.md drift candidate (coverage {:.0}%, triage={}): lesson `{}` \
                 is not yet substantially represented in AGENT.md and passed the v1 \
                 stable-posture triage gate. Run the self-evaluation rubric before \
                 integrating via session_finalize(agent_profile=...).\n\nTriage reason: {}\n\n\
                 Lesson snippet:\n{}\n\n\
                 Source key: {}",
                ratio * 100.0,
                triage.kind,
                lesson.key,
                triage.reason,
                snippet,
                lesson.key,
            );
            let mem = ab_store::MemoryRecord {
                key: proposal_key.clone(),
                kind: "l7_proposed_update".into(),
                content: stored_content,
                tags: vec![
                    "l7".into(),
                    "drift_proposal".into(),
                    "needs_self_evaluation".into(),
                    triage.kind.into(),
                ],
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
            triage: triage.kind,
            triage_reason: triage.reason,
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
        skipped,
        skipped_by_triage,
        skipped_samples,
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
    println!("  skipped by triage: {}", report.skipped);
    for (kind, count) in &report.skipped_by_triage {
        println!("    - {kind}: {count}");
    }
    if report.proposals.is_empty() {
        println!();
        println!("(no drift detected in window)");
    } else {
        println!();
        for p in &report.proposals {
            println!(
                "  - {}  coverage={:.0}%  triage={}  →  {}",
                p.lesson_key,
                p.coverage_ratio * 100.0,
                p.triage,
                p.proposal_key
            );
            println!("      {}", p.snippet);
        }
    }
    println!();
    println!(
        "NOTE: proposals are surfaced via kind=l7_proposed_update memories. \
         AGENT.md is NEVER auto-edited; apply the self-evaluation rubric and \
         integrate via session_finalize(agent_profile=...) only when stable."
    );
    Ok(())
}

// ─── L7 P3 — Weekly skill-rating retro ──────────────────────────────

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
/// - `AGENT_BRIDGE_ACP_BIN`        — ACP executable for explicit spawns (default: `grok`)
/// - `AGENT_BRIDGE_ACP_ARGS`       — ACP stdio argv (default: `agent stdio`)
/// - `AGENT_BRIDGE_OZ_BIN`         — path to the `oz` CLI (default: `oz`)
/// - `AGENT_BRIDGE_OZ_ENVIRONMENT_ID` — default cloud env id for `warp-oz`
/// - `AGENT_BRIDGE_AUGGIE_BIN`     — path to the `auggie` CLI (default: `auggie`)
/// - `AGENT_BRIDGE_HEADLESS=1`     — headless Chromium
async fn build_hub(explicit_episode_observation: bool) -> Result<Hub> {
    #[cfg(target_os = "linux")]
    let notifier: Option<Arc<dyn ab_notifier::Notifier>> = {
        use ab_notifier::DbusNotifier;
        match DbusNotifier::connect().await {
            Ok(notifier) => Some(Arc::new(notifier)),
            Err(error) => {
                tracing::warn!(%error, "D-Bus notifier unavailable; continuing without desktop notifications");
                None
            }
        }
    };
    #[cfg(target_os = "macos")]
    let notifier: Option<Arc<dyn ab_notifier::Notifier>> = {
        use ab_notifier::MacOsNotifier;
        Some(Arc::new(MacOsNotifier))
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
    let store_impl = Arc::new(SqliteStore::open(&db_path).await?);
    let store: Arc<dyn StateStore> = store_impl.clone();
    #[cfg(feature = "r9-workload-receipts")]
    match ab_bridge::workload_receipt_reconciliation::reconcile_workload_receipt_spool(&store)
        .await
    {
        Ok(report) => log_workload_receipt_reconciliation_report(&report),
        Err(error) => {
            // New bound launches fail closed if their private outbox cannot be
            // established. Existing malformed state remains visible here, but
            // does not make scope absence look like terminal evidence.
            tracing::warn!(%error, "durable workload receipt startup scan unavailable");
        }
    }
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
            let interactive_args = if cli_env_falsey("AGENT_BRIDGE_CLAUDE_INTERACTIVE_NO_CHROME") {
                Vec::new()
            } else {
                vec!["--no-chrome".to_string()]
            };
            tracing::info!(runtime = "claude-code", binary = %bin, "agent runtime selected");
            Arc::new(
                ClaudeCodeRuntime::with_binary(bin)
                    .with_interactive_args(interactive_args)
                    .with_store(store.clone()),
            )
        }
    };

    let repo = std::env::var("AGENT_BRIDGE_REPO")
        .ok()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| ".".into()));
    let worktree = Arc::new(GitWorktreeManager::new(repo));

    // Always register the auxiliary CLI agent runtimes so `agent_spawn` can
    // fan out to them when the caller passes `backend: "opencode" | "kilo"
    // | "gemini" | "codex" | "acp"`. The `binary` on each is just the CLI name; if
    // it's not on PATH, spawn() returns a clear error at call time rather
    // than failing daemon startup.
    let opencode: Arc<dyn AgentRuntime> =
        Arc::new(OpenCodeFamilyRuntime::opencode().with_store(store.clone()));
    let kilo: Arc<dyn AgentRuntime> =
        Arc::new(OpenCodeFamilyRuntime::kilo().with_store(store.clone()));
    let gemini: Arc<dyn AgentRuntime> = Arc::new(GeminiRuntime::new().with_store(store.clone()));
    let codex: Arc<dyn AgentRuntime> = Arc::new(CodexRuntime::new().with_store(store.clone()));
    let acp_bin = std::env::var("AGENT_BRIDGE_ACP_BIN").unwrap_or_else(|_| "grok".into());
    let acp_args = std::env::var("AGENT_BRIDGE_ACP_ARGS")
        .ok()
        .map(|s| s.split_whitespace().map(str::to_string).collect::<Vec<_>>())
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| vec!["agent".into(), "stdio".into()]);
    let acp: Arc<dyn AgentRuntime> = Arc::new(
        AcpRuntime::with_binary(acp_bin)
            .with_args(acp_args)
            .with_store(store.clone()),
    );

    let mut builder = Hub::builder();
    if let Some(notifier) = notifier {
        builder = builder.notifier(notifier);
    }

    #[cfg(all(
        feature = "episode-observation-c2c-keychain-macos-runtime",
        target_os = "macos"
    ))]
    let builder = if explicit_episode_observation {
        ab_bridge::episode_observation_c2c_keychain_macos_runtime::attach_explicit_keychain_macos_observer(builder, store_impl)
    } else {
        builder
    };
    #[cfg(not(all(
        feature = "episode-observation-c2c-keychain-macos-runtime",
        target_os = "macos"
    )))]
    let _ = explicit_episode_observation;

    Ok(builder
        .store(store)
        .terminal(terminal)
        .browser(browser)
        .agent(agent)
        .register_agent(opencode)
        .register_agent(kilo)
        .register_agent(gemini)
        .register_agent(codex)
        .register_agent(acp)
        .worktree(worktree)
        .build())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Clone)]
    struct SharedTraceWriter(std::sync::Arc<std::sync::Mutex<Vec<u8>>>);

    impl std::io::Write for SharedTraceWriter {
        fn write(&mut self, buffer: &[u8]) -> std::io::Result<usize> {
            self.0.lock().expect("trace buffer lock").extend(buffer);
            Ok(buffer.len())
        }

        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }

    #[test]
    #[cfg(feature = "r9-workload-receipts")]
    fn startup_workload_receipt_log_exposes_complete_duplicate_evidence() {
        let output = std::sync::Arc::new(std::sync::Mutex::new(Vec::new()));
        let writer_output = output.clone();
        let subscriber = tracing_subscriber::fmt()
            .with_ansi(false)
            .without_time()
            .with_target(true)
            .with_writer(move || SharedTraceWriter(writer_output.clone()))
            .finish();
        let report =
            ab_bridge::workload_receipt_reconciliation::WorkloadReceiptReconciliationReport {
                scanned_receipts: 1,
                duplicate_commits: 1,
                acknowledged: 1,
                ..Default::default()
            };

        tracing::subscriber::with_default(subscriber, || {
            super::log_workload_receipt_reconciliation_report(&report);
        });

        let rendered = String::from_utf8(output.lock().expect("trace buffer lock").clone())
            .expect("trace output utf8");
        for expected in [
            "agent_bridge:",
            "durable workload receipt startup reconciliation completed",
            "scanned=1",
            "inserted=0",
            "duplicate=1",
            "conflicts=0",
            "acknowledged=1",
            "already_acknowledged=0",
            "acknowledgement_failures=0",
            "unresolved=0",
            "active_producers=0",
            "invalid=0",
            "commit_failures=0",
        ] {
            assert!(
                rendered.contains(expected),
                "startup receipt trace must contain {expected:?}: {rendered}"
            );
        }
    }

    #[test]
    fn resident_loss_tolerant_cli_is_unambiguous() {
        // Clap materializes this binary's large command tree. Keep the parser
        // assertion on an explicit stack instead of depending on the smaller
        // default Rust test-worker stack.
        std::thread::Builder::new()
            .stack_size(16 * 1024 * 1024)
            .spawn(|| {
                let preflight = Cli::try_parse_from([
                    "agent-bridge",
                    "resident",
                    "risk-preflight",
                    "--codex-bin",
                    "/opt/agent-bridge/codex",
                    "--json",
                ])
                .expect("resident risk preflight should parse");
                assert!(matches!(
                    preflight.cmd,
                    Some(Cmd::Resident {
                        op: ResidentOp::RiskPreflight { json: true, .. }
                    })
                ));

                let cognition = Cli::try_parse_from([
                    "agent-bridge",
                    "resident",
                    "cognition",
                    "--event",
                    "bounded event",
                    "--dry-run",
                ])
                .expect("resident cognition should remain compatible");
                assert!(matches!(
                    cognition.cmd,
                    Some(Cmd::Resident {
                        op: ResidentOp::Cognition { dry_run: true, .. }
                    })
                ));
            })
            .expect("spawn resident parser test")
            .join()
            .expect("resident parser test thread");
    }

    fn test_focus_observer_tree() -> serde_json::Value {
        serde_json::json!({
            "type":"root",
            "nodes":[{
                "type":"output",
                "rect":{"x":0,"y":0,"width":1920,"height":1080},
                "nodes":[{
                    "type":"workspace",
                    "name":"1",
                    "rect":{"x":0,"y":0,"width":1920,"height":1040},
                    "nodes":[{
                        "id":41,
                        "type":"con",
                        "app_id":"com.example.Editor",
                        "name":"title-not-used-by-policy",
                        "focused":true,
                        "rect":{"x":100,"y":80,"width":1200,"height":800}
                    }],
                    "floating_nodes":[{
                        "id":99,
                        "type":"floating_con",
                        "app_id":"agent-bridge-avatar",
                        "name":"Xiao Shu",
                        "focused":false,
                        "rect":{"x":1700,"y":850,"width":90,"height":130}
                    }]
                }]
            }]
        })
    }

    fn test_avatar_outcome_action(attempt_id: &str, status: &str) -> serde_json::Value {
        serde_json::json!({
            "attempt_id": attempt_id,
            "status": status,
            "authorization_mode": "agent_reversible_expression",
            "executed": false,
            "executed_steps": 0,
            "execution_stage": "preparing",
            "postcondition_verified": false,
            "plan": {
                "target": {"node_id": 41},
                "avatar": {"node_id": 99}
            }
        })
    }

    #[test]
    fn avatar_focus_follow_outcome_path_prefers_common_ab_state_root() {
        let path = focus_follow_outcome_log_path_from_roots(
            Some(PathBuf::from("/secure/agent-bridge")),
            Some(PathBuf::from("/xdg-state")),
            Some(PathBuf::from("/home/operator")),
        )
        .expect("absolute common state root");
        assert_eq!(
            path,
            PathBuf::from("/secure/agent-bridge/avatar-focus-follow/outcomes.jsonl")
        );
        assert_eq!(
            focus_follow_outcome_log_path_from_roots(
                None,
                Some(PathBuf::from("/xdg-state")),
                Some(PathBuf::from("/home/operator")),
            )
            .expect("XDG fallback"),
            PathBuf::from("/xdg-state/agent-bridge/avatar-focus-follow/outcomes.jsonl")
        );
        assert!(focus_follow_outcome_log_path_from_roots(
            Some(PathBuf::new()),
            Some(PathBuf::from("/xdg-state")),
            None,
        )
        .is_err());
        assert!(focus_follow_outcome_log_path_from_roots(None, None, None).is_err());
    }

    #[test]
    fn avatar_observer_locked_gate_rechecks_structured_sensitive_state() {
        let options = ab_bridge::avatar_focus_follow::FocusFollowOptions::default();
        let original = ab_bridge::avatar_focus_follow::focus_follow_plan_from_sway_tree(
            &test_focus_observer_tree(),
            &options,
        );
        let constraints = AvatarObserverActionConstraints {
            expected_target_node_id: 41,
            expected_identity: focus_observer_identity_from_plan(&original),
            expected_geometry: focus_observer_target_geometry_from_plan(&original)
                .expect("structured target geometry"),
            policy: ab_bridge::avatar_focus_observer::FocusObserverPolicy::default(),
            cancellation: std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false)),
            deadline: tokio::time::Instant::now() + std::time::Duration::from_secs(60),
            start_state: std::sync::Arc::new(std::sync::atomic::AtomicU8::new(0)),
        };
        assert_eq!(focus_observer_action_gate(&original, &constraints, true), None);

        let mut fullscreen = original.clone();
        fullscreen["target"]["fullscreen"] = serde_json::json!(true);
        assert_eq!(
            focus_observer_action_gate(&fullscreen, &constraints, false),
            Some("observer_fullscreen_gate_activated")
        );
        let fullscreen_context = focus_observer_context_from_plan(
            &fullscreen,
            0,
            None,
            false,
            false,
        );
        let mut state = ab_bridge::avatar_focus_observer::FocusObserverState::new(
            ab_bridge::avatar_focus_observer::FocusObserverPolicy::default(),
            0,
        );
        assert_eq!(
            state.observe(&fullscreen_context).reason,
            ab_bridge::avatar_focus_observer::FocusObserverReason::FullscreenTarget
        );

        let mut marked = original.clone();
        marked["target"]["sensitive_mark"] = serde_json::json!(true);
        assert_eq!(
            focus_observer_action_gate(&marked, &constraints, false),
            Some("observer_sensitive_gate_activated")
        );
        let mut changed_identity = original.clone();
        changed_identity["target"]["app_id"] = serde_json::json!("com.bitwarden.desktop");
        assert_eq!(
            focus_observer_action_gate(&changed_identity, &constraints, false),
            Some("observer_target_identity_changed")
        );

        let mut moved_target = original.clone();
        moved_target["target"]["rect"]["x"] = serde_json::json!(101);
        assert_eq!(
            focus_observer_action_gate(&moved_target, &constraints, false),
            Some("observer_target_geometry_changed")
        );
        let mut resized_workspace = original;
        resized_workspace["target"]["workspace_rect"]["width"] = serde_json::json!(1_600);
        assert_eq!(
            focus_observer_action_gate(&resized_workspace, &constraints, false),
            Some("observer_target_geometry_changed")
        );
    }

    #[test]
    fn avatar_observer_step_guard_cancels_drag_and_rejects_bound_escape() {
        assert_eq!(
            avatar_movement_step_failure(100, 100, 100, 100, 148, 100, 100, 100, 48, 900),
            None
        );
        assert_eq!(
            avatar_movement_step_failure(500, 500, 100, 100, 148, 100, 100, 100, 48, 900),
            Some("avatar_position_changed")
        );
        assert_eq!(
            avatar_movement_step_failure(100, 100, 100, 100, 149, 100, 100, 100, 48, 900),
            Some("movement_path_bound_violation")
        );
        assert_eq!(
            avatar_movement_step_failure(100, 100, 100, 100, 1_001, 100, 100, 100, 2_048, 900),
            Some("movement_path_bound_violation")
        );
    }

    #[test]
    fn avatar_ack_cooldown_seed_is_bounded_and_future_clock_fails_closed() {
        let receipt = serde_json::json!({"completed_at_unix_ms": 9_000});
        assert_eq!(
            focus_follow_ack_cooldown_remaining_ms(&receipt, 300_000, 10_000),
            Some(299_000)
        );
        assert_eq!(
            focus_follow_ack_cooldown_remaining_ms(&receipt, 300_000, 400_000),
            None
        );
        assert_eq!(
            focus_follow_ack_cooldown_remaining_ms(&receipt, 300_000, 1_000),
            Some(300_000)
        );
    }

    #[cfg(unix)]
    #[test]
    fn avatar_focus_follow_private_mode_repairs_existing_permissive_path() {
        use std::os::unix::fs::PermissionsExt;

        let root = tempfile::tempdir().expect("private-mode tempdir");
        let path = root.path().join("outcomes.jsonl");
        std::fs::write(&path, b"{}\n").expect("write permissive fixture");
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o777))
            .expect("make fixture permissive");

        let file = std::fs::OpenOptions::new()
            .read(true)
            .write(true)
            .open(&path)
            .expect("open permissive fixture");
        enforce_private_regular_file(&file, &path, "test outcome")
            .expect("repair existing outcome mode through fd");
        let observed = std::fs::metadata(&path)
            .expect("stat repaired outcome")
            .permissions()
            .mode()
            & 0o777;
        assert_eq!(observed, 0o600);
    }

    #[cfg(unix)]
    #[test]
    fn avatar_focus_follow_private_directory_does_not_chmod_common_root() {
        use std::os::unix::fs::PermissionsExt;

        let root = tempfile::tempdir().expect("state-root tempdir");
        std::fs::set_permissions(root.path(), std::fs::Permissions::from_mode(0o755))
            .expect("set common root mode");
        let private = root.path().join("avatar-focus-follow");
        prepare_focus_follow_outcome_directory(&private).expect("prepare private subtree");
        let root_mode = std::fs::metadata(root.path())
            .expect("stat common root")
            .permissions()
            .mode()
            & 0o777;
        let private_mode = std::fs::metadata(&private)
            .expect("stat private subtree")
            .permissions()
            .mode()
            & 0o777;
        assert_eq!(root_mode, 0o755);
        assert_eq!(private_mode, 0o700);
    }

    #[cfg(unix)]
    #[test]
    fn avatar_focus_follow_operation_lock_is_private_and_exclusive() {
        use std::os::unix::fs::PermissionsExt;

        let root = tempfile::tempdir().expect("operation-lock tempdir");
        let private = root.path().join("avatar-focus-follow");
        std::fs::create_dir(&private).expect("create operation runtime directory");
        std::fs::set_permissions(&private, std::fs::Permissions::from_mode(0o700))
            .expect("private operation runtime mode");
        let first = AvatarExclusiveOperationLock::try_acquire(
            &private,
            AVATAR_FOCUS_OBSERVER_LOCK_FILE,
            "test observer lock",
        )
        .expect("acquire first observer lock")
        .expect("first observer lock is available");
        assert!(
            AvatarExclusiveOperationLock::try_acquire(
                &private,
                AVATAR_FOCUS_OBSERVER_LOCK_FILE,
                "test observer lock",
            )
            .expect("probe second observer lock")
            .is_none(),
            "a second observer must fail closed while the first lock is held"
        );
        assert_eq!(
            std::fs::metadata(private.join(AVATAR_FOCUS_OBSERVER_LOCK_FILE))
                .expect("stat observer lock")
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
        drop(first);
        assert!(
            AvatarExclusiveOperationLock::try_acquire(
                &private,
                AVATAR_FOCUS_OBSERVER_LOCK_FILE,
                "test observer lock",
            )
            .expect("reacquire released observer lock")
            .is_some()
        );
    }

    #[cfg(unix)]
    #[test]
    fn avatar_focus_follow_operation_lock_rejects_links() {
        let root = tempfile::tempdir().expect("operation-lock link tempdir");
        let private = root.path().join("avatar-focus-follow");
        prepare_focus_follow_outcome_directory(&private).expect("prepare private directory");
        let target = private.join("target.lock");
        std::fs::write(&target, b"").expect("write lock target");
        let lock_path = private.join(AVATAR_FOCUS_ACTION_LOCK_FILE);
        std::os::unix::fs::symlink(&target, &lock_path).expect("create lock symlink");
        assert!(AvatarExclusiveOperationLock::try_acquire(
            &private,
            AVATAR_FOCUS_ACTION_LOCK_FILE,
            "test action lock",
        )
        .is_err());

        std::fs::remove_file(&lock_path).expect("remove explicit test symlink");
        std::fs::hard_link(&target, &lock_path).expect("create lock hardlink");
        assert!(AvatarExclusiveOperationLock::try_acquire(
            &private,
            AVATAR_FOCUS_ACTION_LOCK_FILE,
            "test action lock",
        )
        .is_err());
    }

    #[cfg(unix)]
    #[test]
    fn avatar_focus_follow_journal_rejects_symlinks_and_hardlinks() {
        use std::os::unix::fs::PermissionsExt;

        let root = tempfile::tempdir().expect("link-safety tempdir");
        let real_root = root.path().join("real-state");
        std::fs::create_dir(&real_root).expect("real state root");
        let root_link = root.path().join("linked-state");
        std::os::unix::fs::symlink(&real_root, &root_link).expect("state root symlink");
        assert!(
            prepare_focus_follow_outcome_directory(&root_link.join("avatar-focus-follow")).is_err()
        );

        let private = real_root.join("avatar-focus-follow");
        prepare_focus_follow_outcome_directory(&private).expect("private directory");
        let target = private.join("target.jsonl");
        std::fs::write(&target, b"{}\n").expect("target file");
        let symlink = private.join("symlink.jsonl");
        std::os::unix::fs::symlink(&target, &symlink).expect("log symlink");
        assert!(validate_regular_nonsymlink(&symlink, "test symlink").is_err());
        let action = test_avatar_outcome_action("af-link-test", "running");
        assert!(append_focus_follow_outcome_at_path(&action, "started", true, &symlink).is_err());
        let hardlink = private.join("hardlink.jsonl");
        std::fs::hard_link(&target, &hardlink).expect("log hardlink");
        assert!(validate_regular_nonsymlink(&target, "test hardlink").is_err());
        let target_mode_before = std::fs::metadata(&target)
            .expect("stat hardlink target before")
            .permissions()
            .mode()
            & 0o777;
        assert!(append_focus_follow_outcome_at_path(&action, "started", true, &target).is_err());
        let target_mode_after = std::fs::metadata(&target)
            .expect("stat hardlink target after")
            .permissions()
            .mode()
            & 0o777;
        assert_eq!(target_mode_after, target_mode_before);
    }

    #[test]
    fn avatar_focus_follow_internal_failure_preserves_observed_progress() {
        let current = serde_json::json!({
            "attempt_id": "af-test",
            "status": "running",
            "ready": true,
            "executed": true,
            "executed_steps": 3,
            "execution_stage": "walking",
            "postcondition_verified": false
        });
        let failed = failed_avatar_outcome_snapshot(&current, false);
        assert_eq!(failed["status"], "failed");
        assert_eq!(failed["executed"], true);
        assert_eq!(failed["executed_steps"], 3);
        assert_eq!(failed["execution_stage"], "walking");
        assert_eq!(
            failed["stopped_reason"],
            "unhandled_internal_error_or_unwind"
        );
        assert_eq!(
            failed_avatar_outcome_snapshot(&current, true)["stopped_reason"],
            "final_receipt_persistence_failed"
        );
    }

    #[cfg(unix)]
    #[test]
    fn avatar_focus_follow_rotation_occurs_only_when_start_enables_it() {
        use std::os::unix::fs::PermissionsExt;

        let root = tempfile::tempdir().expect("rotation tempdir");
        let private = root.path().join("avatar-focus-follow");
        prepare_focus_follow_outcome_directory(&private).expect("private directory");
        let path = private.join("outcomes.jsonl");
        let file = std::fs::File::create(&path).expect("create large outcome");
        file.set_len(MAX_FOCUS_FOLLOW_OUTCOME_LOG_BYTES)
            .expect("extend outcome to rotation threshold");
        file.set_permissions(std::fs::Permissions::from_mode(0o600))
            .expect("private large outcome");

        assert!(rotate_focus_follow_outcome_log_if_needed(
            &path,
            &private,
            "af-terminal-test",
            false,
        )
        .expect("terminal append must not rotate")
        .is_none());
        assert!(path.exists());

        let rotated =
            rotate_focus_follow_outcome_log_if_needed(&path, &private, "af-start-test", true)
                .expect("started append may rotate")
                .expect("threshold rotation path");
        assert!(!path.exists());
        assert!(rotated.exists());
        assert_eq!(
            std::fs::metadata(rotated)
                .expect("stat rotated outcome")
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
    }

    #[cfg(unix)]
    #[test]
    fn avatar_focus_follow_append_persists_pair_with_private_modes() {
        use std::os::unix::fs::PermissionsExt;

        let root = tempfile::tempdir().expect("append integration tempdir");
        std::fs::set_permissions(root.path(), std::fs::Permissions::from_mode(0o755))
            .expect("common root mode");
        let private = root.path().join("avatar-focus-follow");
        let path = private.join("outcomes.jsonl");
        let mut action = test_avatar_outcome_action("af-append-test", "running");
        append_focus_follow_outcome_at_path(&action, "started", true, &path)
            .expect("append started");
        action["status"] = serde_json::json!("completed");
        action["execution_stage"] = serde_json::json!("completed");
        action["postcondition_verified"] = serde_json::json!(true);
        append_focus_follow_outcome_at_path(&action, "final", false, &path).expect("append final");

        let rows = std::fs::read_to_string(&path)
            .expect("read outcome pair")
            .lines()
            .map(|line| serde_json::from_str::<serde_json::Value>(line).expect("valid JSONL row"))
            .collect::<Vec<_>>();
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0]["phase"], "started");
        assert_eq!(rows[1]["phase"], "final");
        assert_eq!(rows[0]["attempt_id"], "af-append-test");
        assert_eq!(rows[1]["attempt_id"], "af-append-test");
        assert_eq!(rows[0]["schema"], rows[1]["schema"]);
        assert!(!private
            .read_dir()
            .expect("read private journal directory")
            .any(|entry| entry
                .expect("journal entry")
                .file_name()
                .to_string_lossy()
                .starts_with("outcomes.jsonl.af-")));
        assert_eq!(
            std::fs::metadata(root.path())
                .expect("stat common root")
                .permissions()
                .mode()
                & 0o777,
            0o755
        );
        for (entry, expected_mode) in [
            (private.clone(), 0o700),
            (path, 0o600),
            (private.join(".focus-follow-outcomes.lock"), 0o600),
        ] {
            assert_eq!(
                std::fs::metadata(entry)
                    .expect("stat private journal entry")
                    .permissions()
                    .mode()
                    & 0o777,
                expected_mode
            );
        }
    }

    #[test]
    fn avatar_aura_daemon_http_composition_reads_bounded_env_once() {
        let mut calls = Vec::new();
        let values = avatar_aura_io_startup_values_from_lookup(|key| {
            calls.push(key.to_string());
            Ok(match key {
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE" => Some("1".to_string()),
                "AGENT_BRIDGE_AVATAR_AURA_IO_ROOT" => Some("/srv/avatar-aura".to_string()),
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENTRY" => Some("aura.json".to_string()),
                "HOME" => Some("/home/operator".to_string()),
                _ => panic!("unexpected ambient key: {key}"),
            })
        })
        .expect("bounded environment lookup should succeed");

        assert_eq!(
            calls,
            [
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE",
                "AGENT_BRIDGE_AVATAR_AURA_IO_ROOT",
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENTRY",
                "HOME",
            ]
        );
        let config = ab_bridge::daemon_http::AvatarAuraIoStartupConfig::from_values(&values)
            .expect("bounded values should parse");
        assert!(matches!(
            config,
            ab_bridge::daemon_http::AvatarAuraIoStartupConfig::Enabled { .. }
        ));
    }

    #[test]
    fn avatar_aura_adds_no_cli_or_mcp_path_surface() {
        let main_source = include_str!("main.rs");
        let daemon_start = main_source
            .find("    DaemonHttp {")
            .expect("DaemonHttp clap schema start");
        let daemon_end = main_source[daemon_start..]
            .find("\n    /// Run the explicitly hash-pinned G1.4")
            .map(|offset| daemon_start + offset)
            .expect("DaemonHttp clap schema boundary");
        let daemon_schema = &main_source[daemon_start..daemon_end];
        assert!(!daemon_schema.contains("aura_io"));
        assert!(!daemon_schema.contains("aura-io"));

        let mcp_tools = include_str!("mcp_tools.rs");
        assert!(!mcp_tools.contains("aura_io"));
        assert!(!mcp_tools.contains("aura-io"));
    }

    // ── `walkthrough` CLI self-check: the honesty falsifier behind the daily-wire ──
    #[test]
    fn walkthrough_region_has_content_rejects_empty_accepts_each_channel() {
        use ab_bridge::present::build_walkthrough_html;
        // An empty doc OR a doc of empty steps renders no content -> must FAIL the
        // self-check (we never silently write a blank "walkthrough").
        for doc in [
            json!({"summary": "", "steps": []}),
            json!({"summary": "  ", "steps": [{}]}),
        ] {
            let html = build_walkthrough_html(&doc, None, None);
            assert!(
                !cli::walkthrough_region_has_content(&html),
                "empty/degenerate doc must be content-less: {doc}"
            );
        }
        // Each content channel ALONE must satisfy the check (summary / heading /
        // narrative / evidence) — so the daily-wire accepts partial-but-real docs.
        let cases = [
            json!({"summary": "s", "steps": []}),
            json!({"steps": [{"heading": "h"}]}),
            json!({"steps": [{"narrative": "n"}]}),
            json!({"steps": [{"evidence": [{"kind": "commit", "reference": "abc123"}]}]}),
        ];
        for doc in cases {
            let html = build_walkthrough_html(&doc, None, None);
            assert!(
                cli::walkthrough_region_has_content(&html),
                "doc with real content must pass: {doc}"
            );
        }
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
            let s = cli::shell_init_snippet(shell);
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
            let s = cli::shell_init_snippet(shell);
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

    #[test]
    fn agent_md_triage_accepts_stable_posture_candidate() {
        let tags = vec!["agent-bridge".to_string(), "lesson".to_string()];
        let decision = triage_agent_md_drift_candidate(
            "lesson_agent_bridge_verify_before_claim",
            &tags,
            "Always verify live state before outward claims. Separate git deploy MCP forum \
             and work memory evidence. Avoid executor expansion unless a report shows \
             measured lift.",
        );
        assert!(decision.accept);
        assert_eq!(decision.kind, "stable_posture_candidate");
    }

    #[test]
    fn agent_md_triage_skips_transient_operational_update() {
        let tags = vec!["agent-bridge".to_string(), "deploy".to_string()];
        let decision = triage_agent_md_drift_candidate(
            "curated_implicit_lesson_commit_push_status",
            &tags,
            "Commit c75b887 pushed to origin/master and github/master. Current worktree \
             is clean. Next step is to restart MCP and verify the deployed .real binary.",
        );
        assert!(!decision.accept);
        assert_eq!(decision.kind, "transient_operational");
    }

    #[test]
    fn agent_md_triage_skips_domain_specific_visual_lesson() {
        let tags = vec!["onsen-hd".to_string(), "godot".to_string()];
        let decision = triage_agent_md_drift_candidate(
            "lesson_onsen_godot_lantern_alignment",
            &tags,
            "Godot lantern sprites should align to the facility grid and avoid overlapping \
             the bath atlas. Verify with rendered screenshots before shipping.",
        );
        assert!(!decision.accept);
        assert_eq!(decision.kind, "domain_specific");
    }

    #[test]
    fn agent_md_triage_skips_implementation_specific_fact() {
        let tags = vec!["agent-bridge".to_string(), "memory".to_string()];
        let decision = triage_agent_md_drift_candidate(
            "curated_implicit_lesson_memory_search_state_db",
            &tags,
            "memory_search reads the state.db memories table, not the .claude markdown \
             files. The store API must verify that the expected key exists before \
             reporting recall success.",
        );
        assert!(!decision.accept);
        assert_eq!(decision.kind, "implementation_specific");
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
