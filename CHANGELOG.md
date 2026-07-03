# Changelog

All notable changes to **agent-bridge** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **`retrieval_outcome_apply`** (Tier::Standard): the behavior-changing
  counterpart of `retrieval_outcome_shadow` — one reinforce/decay pass over
  the `retrieval_surfacing` surfaced→used telemetry against live importances
  (used ⇒ +step ceiling-capped; surfaced-never-used ⇒ −step floor-capped).
  Schema **v40** adds a `consumed_at` marker (+ pending partial index): each
  telemetry row is counted toward at most ONE action, in one consume-first
  transaction per key (concurrent passes race-safe), only after a 7h
  maturation (used_at attribution windows must close first);
  below-threshold evidence stays pending and accumulates; clamped/zero-step
  keys and orphaned rows (memory no longer active) are consumed and
  reported. Dry-run by default; a confirmed pass persists a rollback-map
  audit memory before any write and amends it with per-row outcomes after.
- **Daemon reinforce/decay tick** (default OFF): gate
  `AGENT_BRIDGE_RETRIEVAL_OUTCOME_APPLY=1`, cadence
  `AB_RETRIEVAL_OUTCOME_APPLY_TICK_SECS` (default daily), rule knobs
  `AB_RETRIEVAL_OUTCOME_APPLY_{REINFORCE_STEP,DECAY_STEP,MIN_SURFACED,FLOOR,CEILING}`
  — shadow-tool recalibration re-points the actuator without a redeploy.
- **`memory_retrieval_feedback(outcome=used)` now stamps `used_at`** on the
  judged key's recent surfacings (6h window, collector-gated) — the missing
  positive channel: search hits consumed in place never trigger the
  `memory_get` attribution hook. The surfacing ring prune now evicts
  consumed history before pending evidence.

### Changed
- **MCP tool-surface prune** (30-day all-source telemetry driven; 294 exposed
  / 94 with traffic → standard profile 145→96, profile-all 294→~215 on a
  typical host). Three mechanisms, each with an escape hatch:
  - *Ceremony gate*: 50 concluded governance-ceremony tools (BioCortex T6
    candidate-expansion family, LSWR outcome admissions, outcome-gated
    consolidation, retrieval opt-in ceremony ladder, cold trigger-recall
    gates) are hidden from every toolset **including `all`**. Re-expose via
    `AGENT_BRIDGE_EXPOSE_CEREMONY=1` or the `all-dev` toolset. Exactly these
    family members stay registered: the four live biocortex runtime tools
    (`runtime_transition_gate`, `runtime_readiness_packet`, `gated_store_trial`,
    `gated_batch_diagnostics`), both read-only status tools
    (`biocortex_retrieval_opt_in_status`, `trigger_recall_opt_in_status`), and
    `trigger_recall_opt_in_pre_policy_hold_simulation`.
  - *Host-surface gating*: device/credential-backed families (`mobile_*`
    without `adb`, `mobile_ios_*`/`macos_ax_*` off macOS, brave/notion/
    cloudflare/github/gitlab/tailscale without their tokens) are not
    registered at all. `AGENT_BRIDGE_EXPOSE_UNAVAILABLE=1` restores them.
  - *Tier demotions*: 43 cold Standard tools → Niche (codebase_*,
    agent_steer_*, avatar_*, mutating desktop trio, session reflections,
    research shadow surfaces, system_control, …); 5 cold Essential →
    Standard (skills_*, session_finalize, pet_state_ritual). The
    name-allowlist toolsets keep every tool they listed, and the five
    Essential demotions were added to the codex-essential extras so that
    surface is byte-identical to before.
  `mcp_config_audit` gains a `tool_surface` section (what is hidden on this
  host and why); the registry-build log now prints the surface flags.
- **Distribution policy: source only.** agent-bridge no longer publishes
  prebuilt release binaries. Code is published to both GitHub and GitLab;
  install via `cargo install --git` or a source checkout (see README
  "Install"). The GitHub `release.yml` workflow and the GitLab tag-driven
  `build:release:linux` / `publish:release` jobs are removed; version tags
  (`v*`) remain as source markers. Existing v0.x GitHub releases stay
  downloadable but frozen.

## [0.14.0] - 2026-07-02

**Theme: interactive multi-agent PTY fan-out + the memory learning loop goes live.**

This entry is a thematic rollup of the ~1,700 commits landed since 0.13.0
(2026-05-07 → 2026-07-02); per-change detail lives in `git log` and the PR
history. CHANGELOG cadence resumes from here.

### Added
- **Interactive agent sessions across five CLI backends.**
  `agent_spawn(interactive=true)` drives live PTY sessions for `claude-code`,
  `codex`, `gemini`, and the opencode family (`kilo`, `opencode`), with
  per-backend submit-key handling verified against real binaries (golden gates
  in `crates/agent/tests/*_real_interactive.rs`). Follow-up turns via
  `agent_send_input`, screen reads via `agent_session_output` — the
  spawn→send→read→kill loop is closed. `agent_spawn` gains an automatic
  backend-failover chain (env-configurable).
- **Memory learning loop (L5), live end-to-end**: outcome rows → valence rule
  v0.1 → importance apply (`outcome_valence_shadow`,
  `outcome_valence_importance_apply`), durable `valence:*` tag channel with
  one-shot apply stamps, `retrieval_surfacing` telemetry (FIFO ring-capped)
  with read-only consumers `retrieval_outcome_report` and the what-if
  calibrator `retrieval_outcome_shadow`.
- Tool-surface observability: `mcp_dispatch_audit` (traffic/profile audit),
  `tool_atlas_snapshot`, `mcp_lifecycle_digest`, `context_governor_snapshot`.
- Read-only LSWR bridge surfaces (`lswr_*`) and gated biocortex retrieval
  opt-in experiment tooling (`biocortex_retrieval_opt_in_*`).
- Remote embedding backend option (`AGENT_BRIDGE_EMBED_REMOTE_URL`) alongside
  the local ONNX / hash backends.

### Fixed
- **`agent_kill` routes to the session's runtime** instead of the primary
  runtime (#48); SIGTERM→SIGKILL process-group escalation for signal-immune
  TUIs, with a Drop-guard against orphaned children (#49).
- **Semantic ranking parity**: the warm embed-cache path now shares
  `semantic_blend_score` with the cold SQL path (#53); the warm cache
  refreshes importance and drops non-active rows via a metadata-only overlay
  (#55); P4-evolve auto-linking selects neighbors by pure cosine on both cold
  and warm paths (#54, #56).
- **Sync**: stable export strips one-shot `valence_applied:*` stamps so
  receiving nodes re-apply valence honestly (#60); version-vector merge
  round-trips memories + edges + forum (the legacy `sync.sh` newer-wins flow
  is retired).

### Changed
- The MCP registry has grown to **~296 registered tools** behind tier/toolset
  gating (`claude-standard`, `codex-essential`, `codex-lean`, `gemini-lean`,
  `hook-lifecycle`, `all-dev`). README / EVOLUTION-CORE counts corrected to
  match reality.

## [0.13.0] - 2026-05-07

**Theme: skills Phase B (refresh / discover / prune) + GitLab as a first-class forge.**

### Changed
- **`agent-bridge skills` now accepts GitLab URLs.** `parse_src_id`
  handles both `https://gitlab.com/<owner>/<repo>` and the SSH form,
  storing as `gitlab.com/<owner>/<repo>` in the `src:` tag (host
  prefix). Existing GitHub records keep the bare `<owner>/<repo>` form
  for back-compat. New `src_to_clone_url` helper reverses the mapping
  for `skills install` and `skills refresh`. Live: indexing
  `https://gitlab.com/pallasting/agent-bridge-skills` produced 4 records
  with `src:gitlab.com/pallasting/agent-bridge-skills`. Renames
  `is_github_src` → `is_remote_src`.
- **`agent-bridge sync init --provider gitlab|github|auto`.** Adds
  GitLab support via `glab` CLI. `--provider auto` (default) picks
  gitlab when `glab` is on PATH and `gh` isn't, otherwise github
  (preserves legacy behaviour). Refactors the four `gh_*` helpers into
  provider-aware `forge_*` versions. The `glab api user --jq .username`
  / `gh api user --jq .login` field name difference is captured per
  provider.
- **`.gitlab-ci.yml` added** — GitLab CI/CD replicating the GitHub Actions
  CI + release pipeline on Shared Runners. Coverage is **Linux x86_64
  only** on the free tier; macOS prebuilts continue from the GitHub
  workflow until either GitLab SaaS macOS runners (paid) or self-hosted
  Apple Silicon are wired up. Tag-driven release publishes the Linux
  tarball + SHA256SUMS to the project Generic Package Registry, then
  attaches them as Release assets via release-cli.
- **GitHub Actions bumped to current major versions** to silence Node 20
  deprecation warnings ahead of the June 2026 enforcement: `actions/checkout`
  v4 → v6, `actions/upload-artifact` v4 → v7, `actions/download-artifact`
  v4 → v8. v5 of checkout/upload-artifact was the transitional Node 20
  release — already obsolete; pinning straight to current. Usage is
  basic checkout + name/path/if-no-files-found upload, so no breaking
  options were touched.

### Fixed
- **`setup --frontend auto` no longer misroutes** when multiple frontends
  are installed. Detection now checks "Claude Code already wired"
  (substring scan of `~/.claude/settings.json` for any of `ab-memory-hook`,
  `ab-precompact-hook`, `ab-session-end-hook`) FIRST. Previously a
  machine with both Claude Code hooks active AND `~/.codex/config.toml`
  present would re-install the Codex profile on every `setup --frontend
  auto`, silently de-prioritising the user's primary frontend. Hooks
  are the strongest signal of user choice; they win over any other
  detector. Verified live on a machine with `~/.claude/settings.json` +
  Codex + Warp all installed: now picks `claude-code`.

### Added
- **v20a: `agent-bridge daemon-http [--listen ADDR]` — HTTP daemon for
  cross-machine forum + presence over Tailscale.** Read+write endpoints
  on `0.0.0.0:7878` by default (override via flag or
  `AGENT_BRIDGE_HTTP_LISTEN`):
  - `GET /healthz`
  - `GET /.well-known/agent.json/<session_id>` — A2A AgentCard projection
    of the `agent_presence` row (public fields only —
    name/description/version/url/capabilities/skills; strips the local
    identity block per `docs/DESIGN-v19-presence-identity.md` §3)
  - `GET /forum/threads?board=…&status=…&limit=…`
  - `GET /forum/posts?thread_id=…&board=…&since_post_id=…&limit=…`
  - `GET /presence?project=…&role=…&max_idle_secs=…`
  - `POST /forum/post` (Stage 2; SQLITE_BUSY → 503 for caller-side retry)
  Plain HTTP on the trust of the tailnet's WireGuard layer (RFC §2 — no
  HMAC needed; tailscale ACL is the auth boundary). Daemon and stdio
  MCP server share the same SqliteStore — verified safe under 20-way
  concurrent multi-writer load (10 stdio + 10 HTTP, zero data loss,
  zero `SQLITE_BUSY`, `PRAGMA integrity_check: ok`).
- **v20a: optional `peer: "host:port"` arg on four MCP tools** —
  `forum_list_threads`, `forum_read`, `forum_post`, `agent_presence_list`.
  When set, the tool delegates to that peer's `daemon-http`; omitted →
  unchanged local-store path. Schema notes the local-only caveats
  (e.g. `forum_read.unread_for` cursor advance is silently dropped on
  remote read since the remote daemon doesn't carry our subscription
  state). 10 s peer timeout — wedged remote can't block the MCP loop.
- **`agent-bridge skills discover [--limit N] [--all]`** — query GitHub
  topic search (`topic:claude-skill` + `topic:claude-code-skill`,
  unauthenticated REST via `curl`) for candidate skill repos. Dedupes
  across topics, filters out anything already indexed in the local DB
  (use `--all` to include them), prints the top results ranked by stars
  with description and last-pushed date. Does NOT index anything — the
  user picks candidates and runs `skills index <url>` to approve.
- **`agent-bridge skills refresh`** — re-index every previously-indexed
  GitHub source to pick up upstream changes. Walks all `kind=skill`
  records, collects distinct `<owner>/<repo>` values from `src:` tags,
  and re-runs `index` per source. Local-path sources (basenames with
  no `/`) are reported and skipped — they need a manual `skills index`.
  Cron / Stop-hook friendly.
- **`agent-bridge skills refresh --prune`** — opt-in deletion of records
  for skills that disappeared upstream. After a successful re-index of
  a source, deletes records with that `src:` tag whose `updated_at` is
  older than the refresh's start time (i.e. weren't re-saved during
  this run). Failed re-indexes skip pruning of that source — never
  destroy data without a fresh authoritative state. Off by default.
- **Cross-device forum sync.** `agent-bridge sync` now also writes
  `forum.jsonl` alongside `memory.jsonl` in the cross-device git repo.
  New `StateStore::forum_export` / `forum_import` (SqliteStore impl)
  serialize the v18 forum tables (`forum_threads` + `forum_posts`)
  using natural-key dedup — threads matched on
  `(board, created_by, created_at, title)`, posts on
  `(thread, author, created_at, body)` — so re-import is idempotent
  and machine-local row ids never collide across devices. Subscriptions
  remain local (each device tracks its own read cursors). Presence is
  intentionally NOT synced — it's a real-time signal that doesn't fit
  git's pull/push cadence; the daemon-mode path in commit 7c4e39e is
  the right fix when needed.

## [0.12.0] - 2026-05-06

**Theme: skill-library indexer — find, search, recommend, install third-party Claude Code skills.**

### Added
- **`agent-bridge skills` subcommand** — index third-party open-source
  Claude Code skill repos into the memory store and search across them.
  Walks `**/SKILL.md`, `.claude/skills/*.md`, `skills/*.md`; parses YAML
  frontmatter (name/description/allowed-tools); runs a heuristic safety
  lint (pipe-to-shell, dangerous-rm, creds-path, eval-substitution); saves
  each as `kind=skill` memory record keyed by `skill:<owner>/<repo>/<path>`.
  Subcommands: `index <url|path>`, `seed` (curated 8-repo corpus →
  ~470 skills), `search <query>`, `list`, `show <key>`, `install <key>`.
  Lint flags surface to stderr but never refuse to save — judgment stays
  with the user.
- **`agent-bridge skills install <key>`** — re-clones the source repo and
  copies the original SKILL.md plus any sibling scripts/data into
  `~/.claude/skills/<name>/`. Bails when lint flags are present or the
  destination exists, unless `--yes` is given.
- **`mcp__agent-bridge__skills_recommend(query, limit)` MCP tool** — wraps
  the skill index so agents can query for pre-written skills in-loop.
  Returns key, source, summary, lint status, and a ready-to-run install
  command. Registered in the Standard tier (default-on). Use case: when
  an agent starts a task ("audit a Helm chart", "edit a PDF form"), it
  queries `skills_recommend` first and surfaces matching pre-written
  skills instead of writing instructions from scratch.

### Changed
- Indexer records now carry a `path:<rel-path>` tag recording the
  original SKILL.md location. Pre-existing records (from manual
  v0.11-era usage of `agent-bridge skills`) need a re-index to backfill;
  `skills install` will surface a clear error pointing at this.

## [0.11.0] - 2026-05-06

**Theme: ONNX-free prebuilts — Intel Mac and any-glibc Linux unblocked.**

### Changed
- **Prebuilt binaries are now ONNX-free.** `ab-bridge` exposes an
  `onnx-embed` feature (default on for source builds); the release
  workflow builds with `--no-default-features` to drop the ONNX
  sentence-transformer backend. Effect: tarballs ~3× smaller (compressed
  4.9–6.0 MB instead of 12.9–15.3 MB), Linux binary works on any glibc
  2.35+ instead of requiring 2.38+, and `x86_64-apple-darwin` (Intel
  Mac) is back in the prebuilt matrix. Hash-based 384-dim fallback
  keeps memory/embedding APIs functional; users wanting the full
  sentence-transformer backend should `cargo install --git` instead.
- **Release matrix expanded** to three targets:
  `x86_64-unknown-linux-gnu` (ubuntu-22.04), `aarch64-apple-darwin`
  (macos-14), `x86_64-apple-darwin` (macos-14 + cross-compile via
  Rosetta 2 for smoke).
- Workspace dep `ab-store` switched to `default-features = false`; only
  `ab-bridge`'s `onnx-embed` feature pulls fastembed into the dep graph.

### Other
- `feat(agent_spawn): policy → backend routing layer` — `policy` field
  on `agent_spawn` maps high-level intents to backends (default →
  claude-code, cheap → kilo, second_opinion/openai → codex). `backend`
  wins if both given; unknown values fall through gracefully.

## [0.10.0] - 2026-05-06

**Theme: cross-device sync, multi-frontend agent matrix, first prebuilt binaries.**

The biggest release since v0.9.1 (75 commits). Notable shifts:
1. **Memory sync becomes a first-class subcommand** — `agent-bridge sync`
   replaces the bash + python `sync.sh`; `agent-bridge sync init` bootstraps
   the cross-device repo via `gh` CLI on a new machine.
2. **Multi-frontend agent_spawn** — opencode / kilo / gemini / codex are all
   first-class spawn backends, joining the existing claude-code / warp-oz /
   auggie runtimes.
3. **PTY + vt100 in the daemon** — `terminal_resize`, vim/top/clear/progress
   rendering, multi-frontend setup support.
4. **Continuity layer matures** — AiOT Soul read-only injection, letter-to-
   future-self protocol, AGENT.md self-profile + 50% drift cap, agent-bridge-
   seed grid state injection.
5. **Release infrastructure ships** — first agent-bridge release with prebuilt
   binaries (Linux x86_64, macOS Intel & Apple Silicon). Tag-driven CI matrix.

### Release infrastructure

- **`.github/workflows/release.yml`** — tag-driven release workflow.
  Pushes of any `v*` tag trigger native builds on `ubuntu-22.04`,
  `macos-13`, and `macos-14`, producing tarballs for
  `x86_64-unknown-linux-gnu`, `x86_64-apple-darwin`, and
  `aarch64-apple-darwin`. SHA256SUMS aggregated; auto-generated release
  notes; `softprops/action-gh-release@v2` publishes to GitHub Releases.
- **`.github/workflows/ci.yml`** — PR-time matrix build + test on
  `ubuntu-22.04` and `macos-14`. Complements the existing
  master-push-only `verify-warp-integration.yml`.
- **Fix flaky `oz::tests::resolve_environment_id_*`** — four tests
  mutate the same process-wide env var and raced on multi-thread test
  runners. Serialised with a static `Mutex`. Verified stable across
  five consecutive `cargo test` runs.

### Added (cross-device memory sync)

- **`agent-bridge sync` first-class subcommand** — replaces the bash +
  python `~/agent-bridge-memory/sync.sh` with a Rust implementation that
  shells out to `git` only. One round = `git pull --rebase --autostash`
  → `memory_import(NewerWins)` → `memory_export` → `git add` + commit +
  push if anything changed. Idempotent and safe to call from cron / hooks.
  The Stop hook (`ab-session-end-hook.sh`) now invokes `agent-bridge sync`
  directly, removing the dependency on the external `sync.sh` script and
  the hardcoded `~/agent-bridge/target/release/agent-bridge` path.
- **`agent-bridge sync init`** — one-shot bootstrap on a new machine via
  `gh` CLI. Verifies `gh auth status`, derives the user's login, detects
  or creates the private repo (`<user>/agent-bridge-memory` by default,
  `--repo <name>` to override), clones it to the configured path, and
  runs the first sync. Removes the previous "you must `git clone` the
  private repo by hand" step from quick-start.
- **`agent-bridge sync status`** — prints resolved repo path, origin
  remote, last commit, and dirty state. No network.
- **`AGENT_BRIDGE_MEMORY_REPO` is the single source of truth** for the
  memory-sync repo location. Resolution order: env var → legacy
  `~/agent-bridge-memory` (if `.git` present) → legacy
  `~/Projects/agent-bridge-memory` → `<state-dir>/memory-sync` next to
  `state.db` (new canonical default). Existing setups keep working
  without configuration; new installs land beside the database.

### Added (continuity layer)

- **Phase α′: AiOT Soul read-only injection** —
  `session_bootstrap` now reads `/Data/CascadeProjects/AiOT/consciousness_state/soul_final.json`
  (override via `AGENT_BRIDGE_AIOT_SOUL_PATH`) and injects a compact summary
  block — fingerprint, session_count, total_experiences, 5-dim trait_vector
  (curiosity/caution/creativity/persistence/adaptability), 256-dim
  identity_embedding stats (norm + top-5 |dims|) — between Agent Self-Profile
  and Letters. First time agent-bridge holds AiOT carrier identity in its
  working state. Read-only; bidirectional sync (Phase β) requires the
  EMA + drift-cap logic from `identity_anchor.py` to run somewhere.
  See memory `decision_phase_alpha_prime_aiot_soul_injection_20260504`
  for full rationale including the deliberate override of the conservative
  trigger from `letter_1777853190`.
- **AGENT.md drift cap (50%)** — `session_finalize(agent_profile=...)` now
  computes line-set Jaccard distance between old and new AGENT.md content;
  writes that change > 50% of unique lines are rejected with
  `agent_profile_capped: true` + a `reason` string. Pass
  `agent_profile_force: true` to bypass (intended for deliberate major
  rewrites). First write (empty old) is always allowed. Response always
  reports `agent_profile_diff_ratio` so the caller can audit afterwards.
  Borrowed from AiOT `identity_anchor.py::MAX_STEP_DRIFT` —
  the stable identity layer should not be rewritable in one shot.
  Backed by 7 unit tests covering identity, partial change, additions,
  total rewrite, and the cap boundary.
- **Letter-to-future-self protocol** — append-only Markdown notes the agent
  writes at `session_finalize(letter="...")`. Each call creates
  `~/.local/share/agent-bridge/letters/letter_<unix_ts>.md`. `session_bootstrap`
  auto-injects the 3 most recent letters as `=== Letter from past-self (...) ===`
  blocks, placed between `Agent Self-Profile` and memory rows. Distinct from
  `AGENT.md` (stable identity) and `session_handoff` (factual progress log) —
  letters carry **momentary thinking**: state-at-time-of-writing, anticipations,
  hopes, warnings to future-self. Models the dual-mechanism identity pattern
  from AiOT's `identity_anchor.py` (attractor + signal). Inspired by AiOT's
  `README_FOR_FUTURE_RESIDENTS.md` (2026-04-25). See memory
  `decision_aiot_seed_actual_state_20260503` for the broader continuity context.

### Performance

- **`memory_import` batch embedding** — `OnnxBackend::embed_batch()` now
  overrides the trait default (per-row loop) and calls `fastembed`'s native
  batch interface, running a single ONNX forward pass across all texts.
  `memory_import` path pre-computes embeddings outside the SQL transaction
  via `default_backend().embed_batch(&content_refs)` then indexes into the
  per-row INSERT/UPDATE loop. Real measurement (312 rows export → import):
  pre-fix ~17 s avg → post-fix ~8-14 s avg (~2× total; embedding stage
  dropped from ~50 ms/row to ~5 ms/row, residual cost is per-row SQL).
  See memory `friction_workflow_20260503_memory_import_batch_embed`.

### Added

- **MCP `tools/call` full telemetry (schema v17)** — `mcp_tool_calls` table
  records every successful and failed tool call with timestamp, duration_ms,
  ok flag, args_size, result_size. Hook lives in the MCP stdio dispatcher
  (`crates/mcp/src/server.rs`); fire-and-forget, never fails the call.
  New MCP tool `mcp_call_stats(window_days, top_n)` returns per-tool aggregate
  call_count / error_count / avg+p95+max duration / avg result size, sorted
  by call_count desc. Powers the observation period that drives the
  ab-shell decision (see memory `plan_warp_observation_metrics_20260503`).
- **`AGENT.md` — agent self-profile companion to `USER.md`** —
  `~/.local/share/agent-bridge/AGENT.md` is now read at `session_bootstrap`
  and injected as `=== Agent Self-Profile ===` block (after User Profile,
  before memory rows). The agent maintains its own values, working style,
  observations, and growth markers across sessions. Editable via
  `session_finalize(agent_profile="<markdown>")`. v0 implementation is plain
  Markdown; long-term destination is AiOT Seed `SelfModel` initialization
  (see memory `decision_aiot_seed_as_agent_continuity_substrate_20260503`).
- **`EmbeddingBackend` trait — pluggable inference kernel** —
  `crates/store/src/embedding.rs` introduces a `Send + Sync` trait
  (`name() / dim() / embed() / embed_batch()`) with two built-in impls:
  `OnnxBackend` (all-MiniLM-L6-v2 via fastembed) and `HashBackend` (FNV-1a
  fallback). Selection precedence: `set_default_backend()` override →
  `AGENT_BRIDGE_EMBED_BACKEND` env var (`onnx` | `hash`) → compile-time
  default. The free function `embed_text()` now delegates to the active
  backend, so existing call sites are unchanged. External crates (e.g. AIoT
  Rust Seed) plug in by implementing the trait and calling
  `set_default_backend(Arc::new(MyBackend::new()))` at startup.
- **`capabilities` exposes active embedding backend** — response now
  includes `memory.embedding.{backend,dim,env_override}` so agents can
  introspect which inference kernel is active without grepping logs.

### Changed

- **`ab-memory-hook` v3.0 — pure-SQL static ranking** — reverts the v2.0
  Python FNV-1a re-ranking that became mathematically broken after the
  512→384-dim embedding migration (the hook still computed 512-dim hash
  vectors, which `cosine()` then silently truncated against 384-dim ONNX
  vectors, producing meaningless scores). v3.0 ranks by SQL only:
  `kind tier + access*recency + importance × 10⁷`. Hook stays cheap
  (~50 ms incl. process startup) and deterministic. Agents that want
  semantic ranking should call `session_bootstrap(query="...")` or
  `memory_search(mode=semantic)` — both routes use the real ONNX model.

### Added

- **ONNX semantic embeddings — `all-MiniLM-L6-v2` via `fastembed`** — replaces
  the FNV-1a hash-trick embedding for `memory_search(mode=semantic)`,
  `session_bootstrap(query=…)`, and `codebase_search(mode=semantic)`. Static
  link to ONNX Runtime via `ort` (no system deps); 384-dim sentence vectors;
  model auto-downloads to `~/.cache/fastembed/` (~22 MB) on first call.
  Steady-state cost: `memory_save` +50 ms (single embed),
  `memory_search(semantic)` +20 ms (cosine over in-memory cache).
  Hash backend remains as fallback when `onnx-embed` feature disabled.
- **`memory_reindex` MCP tool** — re-computes embeddings for active memories
  with `embedding IS NULL`. Needed once after the 512→384-dim migration to
  populate vectors for existing rows. Batch size 1–1000 per call; refreshes
  the in-process embedding cache on each batch so semantic search sees new
  vectors without restart.
- **`session_bootstrap` optional `query` parameter** — when provided, memories
  are ranked by cosine similarity (FNV-1a embeddings, threshold 0.15) instead of
  static importance. `session_handoff` rows are always prepended for continuity.
  Output header reflects active mode: `scope: ... | semantic`.
- **`ab-memory-hook` v2.0 — semantic UserPromptSubmit injection** — upgrades
  the `UserPromptSubmit` hook from static kind-tier+recency sort to FNV-1a
  semantic re-ranking. The user's first message is embedded with the same
  512-dim hash-trick as `ab_store::embed_text` (pure Python, no deps). Memories
  are ranked by `cosine_similarity + 0.15×importance`; concept nodes and
  session_handoff rows are always-injected first (not subject to ranking).
  Falls back to static sort for short/vague prompts (< 3 non-stop tokens).
  Execution time: ~265 ms on 280 memories (well within 5-second hook timeout).
- **`codebase_index` / `codebase_search` MCP tools (D3.2)** — pure-Rust symbol
  extractor (Rust, Python, TypeScript/JavaScript, Go) stores indexed symbols in
  SQLite `codebase_symbols` table (schema v14 + v15 embedding column). Exact
  (`LIKE`) and semantic (cosine similarity over FNV-hash embeddings) search modes.
  Search deduplicates across overlapping root-path indexes via `GROUP BY
  (file_path, line, kind, name)`. Returns `file_path`, `line`, `kind`, `name`,
  `signature`, `language`, and optional `score`.
- **D2.3 per-turn embedding cache** — `session_bootstrap` spawns a background
  `tokio::spawn` that pre-loads all active memories with embeddings into
  `Hub::memory_embed_cache` (`Arc<Mutex<Option<Vec<(MemoryRecord, Vec<f32>)>>>>`).
  `memory_search(mode=semantic)` checks the cache first; on hit, scores are
  computed in-process (cosine + 0.2 × importance) without a DB round-trip.
  Cache stays warm for the session; cold path falls back to `memory_search_semantic`.
- **`StateStore::memory_load_embeddings`** — new trait method (default returns
  empty vec); `SqliteStore` SELECTs all active rows with non-NULL embeddings in
  one query and decodes `Vec<f32>` pairs.

### Fixed

- **`memory_import` now writes `embedding`** — bulk JSONL import applies the same
  feature-hash vector as `memory_save`, so `memory_search` with `mode=semantic`
  immediately ranks imported rows (no `NULL embedding` gap).

### Added

- **`mcp_recent_errors` MCP tool (Phase C)** — reads newest-first rows from SQLite
  `mcp_tool_errors` (ring buffer, default cap 100). The stdio MCP server records
  failures on `tools/call`: missing tool name, unknown tool, `execute` `Err`,
  `ToolResult` with `isError`, and result serialization errors (when a store is
  configured).
- **`memory_export` / `memory_import` graph round-trip (Phase B)** — optional
  `edges_out_path` on export writes companion `MemoryEdgeExport` JSONL (edges
  whose **both** endpoints are in the exported memory set). `memory_import`
  accepts optional `edges_path` to upsert `memory_edges`. `memory_export` returns
  `{ memories_written, edges_written }`; import report includes
  `edges_upserted` / `edges_malformed`. MCP tools expose `edges_out_path` /
  `edges_path`; `session_finalize` export summary lists both counts.
- **`memory_snapshots/inject/ab_ai_kernel_v1.jsonl`** — compact AI-oriented
  memory bundle (SIGNAL / WHEN / MUST / KEYWORDS + 中文摘要, tags `ab-inject`)
  intended for `memory_import` + semantic or hybrid recall.
- **`memory_snapshots/inject/ab_ai_bridge_feedback_v1.jsonl`** — agent-UX /
  ops feedback cards (observability, graph export, embedding docs audience,
  multi-frontend matrix, security defaults); tags `ab-feedback`.
- **`docs/AGENT-BRIDGE-AGENT-UX-ROADMAP.md`** — phased implementation plan
  (Phases A–E) complementing `docs/PHASE-D-roadmap.md`; Phase A landed with
  README embedding guidance + inject bundle + `AGENT-BRIDGE-EVOLUTION-CORE` §8.2.
- **Browser MCP tools (W6)** — `browser_extract_text` (`innerText` as JSON) and
  `browser_fill_form` (CSS selector + value, dispatches input/change).
  `BrowserBackend` trait extended; `ChromiumCdpBackend` implements both.
- **Multi-session inbox (W6)** — SQLite schema **v10** `agent_messages` table plus MCP
  **`agent_message`** (send JSON) and **`agent_inbox`** (poll by `to_session`, optional
  `since_id` / `unread_only` / `limit`).
- **Warp URI MCP tools (W4)** — `warp_open_tab`, `warp_open_window`,
  `warp_open_settings` (best-effort internal action), `warp_launch_workflow`
  (`warp://launch/<name>`), and `warp_status` (environment + `oz` probe).
  Uses `ab-terminal` helpers + OS URL opener (`xdg-open` / `open`).
- **`plan_save` / `plan_load` / `plan_update` MCP tools** — SQLite-backed structured
  task plans (`plans` table, JSON steps). Survives sessions; `plan_load` adds
  `progress` and `next_step_id`. DESIGN Phase B / W5.
- **`context_budget` MCP tool** — Offline EN/CJK token heuristic plus optional
  `conversation_turns` coarse multiplier vs approximate `model` context limits;
  returns `pct_used` and `recommendation` (`nominal` / `suggest_session_curate` /
  `urgent_handoff_or_compact`). No model API calls.
- **`session_handoff` MCP tool** — JSON brief aggregating todo memories, recent
  `session_handoff` memory rows, and a git snapshot (`branch`, `log -1 --oneline`,
  `status --porcelain`, derived file list). Optional `last_task`, `status`,
  `open_questions`, and `conversation_snippet`. Implements DESIGN-warp-first
  W3 / D9 (no new tables).
- **`session_lifecycle_step` MCP tool** — dispatches `bootstrap` / `precompact`
  (runs `session_curate` then `session_finalize`) / `finalize` with argument
  pass-through.
- **`ab-precompact-hook`** now issues a single `session_lifecycle_step` call for
  the precompact phase instead of two separate tool calls.
- **`TerminalCapabilities`** on `TerminalBackend` — sync `capabilities()` method;
  MCP **`capabilities`** exposes nested `terminal.capabilities` plus top-level
  `can_send_keys` / `can_split`; **`terminal_read_output`** returns structured
  JSON error when `can_read_output` is false. Warp derives read/send from an IPC
  socket probe.
- **`project_detect`** / **`changes_digest`** MCP tools — filesystem manifest scan
  (`Cargo.toml` via `cargo metadata`, `package.json`, Python/Go/Make markers) plus
  structured git diff summaries (`git diff --numstat` / `--name-status`). DESIGN W2.
- **Global MCP `backend_id` diagnostics** — all `tools/call` responses now include a
  top-level `backend_id` object (`terminal`, `browser`, `agent_runtime`, `memory`),
  injected centrally by the stdio MCP server for both success and tool-error results.
- **`AGENT_BRIDGE_DB` override in bridge runtime** — `agent-bridge mcp` / daemon can
  use an explicit SQLite path instead of platform default `state.db`, enabling
  isolated end-to-end verification runs without mutating the main memory store.
- **`scripts/verify_warp_integration.sh`** — W8-style integration smoke script that
  validates lifecycle bootstrap, perception tools, structured handoff, plan
  save/load/update, Warp status, agent messaging, and per-response `backend_id`.
- **Warp IPC `terminal_read_output` E2E coverage** — added:
  - `scripts/verify_warp_terminal_read_output_e2e.sh` (MCP-level end-to-end check
    using a local Unix-socket Warp IPC stub for `list_sessions`/`read_scrollback`)
  - `WarpBackend` socket-RPC test (`warp_ipc_e2e_list_send_read`) covering
    list/send/read through the backend protocol path.

### Changed

- **`verify-warp-integration` CI** — `push` to `master` uses `paths-ignore` so
  markdown-only / docs / snapshot commits skip the job; **`workflow_dispatch`**
  remains unfiltered for full manual runs.
- **`context_budget` heuristic calibration** — non-CJK divisor adjusted from
  `3.5` to `3.3` chars/token to reduce under-estimation on repository-scale
  technical text; CJK divisor remains `1.5`.
- **Git-tracked memory snapshots** — `memory_snapshots/inject/ab_ai_bridge_feedback_v1.jsonl`
  and `ab_ai_kernel_v1.jsonl` cards now describe optional `edges_out_path` /
  `edges_path`, `mcp_recent_errors`, and roadmap status A–E; archived JSONL rows
  `lesson_memory_export_excludes_edges` and `agent_bridge_memory_sync_procedure`
  updated so import/sync docs match shipped behavior. Feedback bundle adds index
  entry **`ab_feedback_k08_phase_bc_shipped`** (Phase B+C anchor card).

### Added

- **`scripts/calibrate_context_budget.py`** — tokenizer-backed calibration tool
  (default: `tiktoken` `cl100k_base`) that reports MAPE/worst error and fails
  when MAPE exceeds target (`15%` by default).

## [0.9.2] — 2026-04-28

**Memory graph L0 layer + concept-node hook budget.**

### Added

- **L0 concept navigation nodes** (`kind=concept`, tags `["concept","L0"]`).
  10 top-level concept nodes covering the core knowledge domains: Arrow ecosystem,
  AMD GPU stack, MCP design, graduated autonomy, user philosophy, inference/knowledge
  split, project topology, AI identity continuity, self-evolution, and infrastructure
  stack. Each carries a `related_keys` list pointing to its L1 cluster.
- **Bidirectional graph edges**: synthesis and key domain memories updated to
  include back-references to their parent concept nodes (L1→L0 edges).
- **Hook v0.9.2 — dedicated concept budget** (`≤15 slots`, always injected first).
  `kind='concept'` rows are excluded from domain/other queries via `AND kind !=
  'concept'` filters. This prevents concept nodes from competing with lessons/
  decisions for budget, and from being sorted last by KIND_TIER's ELSE→5 rule.
  `KIND_TIER` updated to `WHEN 'concept' THEN 0` as defense-in-depth.
  Merge logic uses pre-declared `NL=$'\n'` to avoid `$'\n'` misexpansion inside
  double-quoted strings.

## [0.9.1] — 2026-04-28

**Memory scope expansion + hook budget split.**

### Added

- **Domain-scoped memories** (`domain:rust`, `domain:amd-gpu`, `domain:mcp`,
  `domain:ai-architecture`) — cross-project transferable knowledge that injects
  in every session regardless of CWD.
- **User cognitive-style memories** (`user_cognitive_style_*`, `user_design_values_core`,
  `user_collaboration_style`) — captures HOW the user thinks and collaborates,
  not just what they've built. Enables calibrated explanations and proposals.
- **Cross-domain synthesis memories** (`synthesis_*`) — explicit connections
  between recurring patterns across projects (Arrow as unified infra, inference/
  knowledge decoupling, graduated-autonomy meta-pattern).

### Fixed

- **Hook injection budget split (v0.9.1).** Flat `LIMIT 80` replaced with two
  budgeted queries: `domain:*` memories get a **reserved 20-slot budget** and are
  injected first; project/global memories fill the remaining **60 slots**. Prevents
  a large global store from crowding out domain-scoped cross-project knowledge.
  SQL fragments extracted into bash vars (`KIND_TIER`, `FREQ_SORT`, `PROJ_MATCH`)
  to eliminate repetition across SELECT + UPDATE pairs.

## [0.9.0] — 2026-04-28

**Self-evolution release.** Closes the loop between "I hit a wall" and "I
fixed it" — without manual diff generation or daemon intervention. Driven by
two core pain points: (1) the evolve workflow required hand-crafted unified
diffs; (2) the memory hook injected low-relevance records as the store grew.

### Added

- **`agent-cli evolve` subcommand family** — self-improvement proposal workflow:
  - `evolve propose --issue --fix [--patch]` — creates an isolated git worktree
    branch (`evolution/YYYYMMDD-<slug>`), records a `kind=evolution` memory entry.
  - `evolve fix` — two modes:
    - *Edit mode* (`--file --old --new`): exact string replacement in the
      worktree file; no diff required. I read the file, replace, `git add`, commit.
    - *Patch mode* (`--patch` or stdin): applies a unified diff via `git apply`.
    Both modes create the worktree branch if absent (one-shot propose+fix).
  - `evolve list` — shows open proposals only (`kind=evolution`; closed ones
    are filtered).
  - `evolve close <key> [--note]` — marks proposal as `kind=evolution_closed`;
    removes `open` tag; appends resolution note.
  - `--dry-run` on `propose` and `fix` previews without creating anything.

### Fixed

- **`ab-memory-hook` injection inside curator sub-agents.** The hook now exits
  immediately when `AB_MEMORY_CURATOR=1` is set, preventing recursive context
  bloat when `ab-precompact-hook` spawns a `claude -p` memory curator.
- **Memory hook sort order degraded at scale.** With 100+ records the previous
  `ORDER BY kind_tier, updated_at DESC` injected recently-written but never-
  accessed records ahead of frequently-used ones. Changed to
  `(access_count * 86400 + updated_at) DESC` within each kind tier — each
  access lifts a record by the equivalent of one extra day of recency.

## [0.8.0] — 2026-04-28

**AI ergonomics release.** No new user-facing features; instead, four small
changes that emerged from auditing my own pain points across 75 self-memories.
Every item in this release answers a specific friction signal logged in the
memory store — see `decision_v08_self_improvement_focus` for the full reasoning.

### Added

- **`agent-cli memory` subcommand family.** Direct SQLite access (no daemon
  needed) so memory work is reachable from cron, Stop hooks, and `pipx`-style
  one-shots. Subcommands: `list`, `get`, `search`, `save`, `delete`, `compact`.
  All accept `--json` where applicable. `agent-cli memory save` reads body
  from stdin if `--content` is omitted.
- **`agent_session_list` liveness probe.** Each running row now carries
  a `liveness` field — `alive` (PID still in `/proc`), `dead` (PID gone but
  `finalise_session` never ran → zombie row), or `unknown` (bridge restarted
  since spawn). Closes the long-standing "is this session actually still
  running, or is it a leaked DB row?" question.
- **`AgentRuntime::pid_for(session)`** trait method, default `None`.
  `ClaudeCodeRuntime` overrides to return the in-flight child PID. This is
  what backs the liveness probe above.

### Changed

- **`memory_compact` no longer silently no-ops with empty thresholds.**
  When called with neither `min_uses` nor `older_than_days`, the tool now
  applies a balanced default (`min_uses=2 AND older_than_days=90`) and
  reports `applied_defaults=true` in the response. Previously a bare
  `memory_compact()` call returned an error and forced callers to
  re-derive a policy. The 1-hour `created_at` grace period from v0.7.1
  still protects freshly-saved rows. `CompactPolicy::healthy_default()` is
  exposed publicly so library callers (including the new `agent-cli`) can
  share the same defaults.
- **`ab-memory-hook` bumps `access_count` and `last_accessed_at`** on the
  rows it injects, so the "Frequent" / "Recent" sorts and the new compact
  default reflect what is actually in front of Claude on each session
  start. Previously the hook only read; rows were "used" without ever
  being marked as such.

### Internal

- Added `ab-store` as a direct dependency of `agent-cli` for the new
  in-process memory subcommands. No new system deps (rusqlite stays
  bundled).

### Verification

- Workspace `cargo build --release` clean; `cargo test` 10/10 pass.
- `agent-cli memory list -n 3` round-trips against the live DB.
- Hook invoked with synthetic stdin → 40+ rows had `access_count` bumped
  by 1 (verified by SELECT before / after).
- `memory_compact({})` returns `applied_defaults=true`, removes 0 rows
  on the current healthy DB (1-hour grace shields the just-planted v0.8
  decision rows).

---

## [0.7.2] — 2026-04-28

**Hotfix.** Two small bugs surfaced 30 minutes after v0.7.1 went live, both
discovered while dogfooding the hooks + memory_search in a fresh Claude Code
session.

### Fixed

- **`memory_search` no longer drops queries containing `.` or `-`.**
  v0.5.1's `sanitise_fts_query` *stripped* every non-alphanumeric character
  except `_` / `-`, then prefix-suffixed the remainder with `*`. So a user
  query of `v0.7.1` collapsed to `v071*` and matched nothing — because FTS5's
  default `unicode61` tokeniser had indexed it as the three tokens
  `[v0, 7, 1]`. The sanitiser and the indexer disagreed on what counts as
  a token boundary.
  Fix: split the input on the *exact* same separator predicate the
  `unicode61` tokeniser uses (`!is_alphanumeric() && != '_'`), then
  `*`-suffix each non-empty fragment. `v0.7.1` now becomes `v0* 7* 1*`,
  `agent-bridge` becomes `agent* bridge*`, `session_handoff` stays a
  single `session_handoff*`.
- **`ab-memory-hook` once-per-session lock now actually works.**
  Claude Code does **not** export `CLAUDE_SESSION_ID` into the hook env
  (verified empirically — see `lesson_hook_session_id_from_stdin`). The
  v0.7.0 hook fell back to `$$` (bash PID), which is unique per
  invocation, so the `/tmp/ab-mem-injected-${SESSION_ID}` lock never
  collided with itself: the memory index was re-injected on **every**
  UserPromptSubmit instead of just the first one in a session.
  Fix: read the JSON payload Claude Code pipes into the hook on stdin
  and extract `session_id` from there. `CLAUDE_SESSION_ID` env and PID
  remain as fallbacks for manual / scripted invocations.

### Verification

- `memory_search "v0.7.1"` (release binary, fresh stdio session) → ≥ 3 hits
  including the v0.7.1 fix lessons we planted earlier today.
- `memory_search "agent-bridge"` → 3 hits (would have been 0 before).
- Hook invoked twice with same `session_id="abc-test-1"` → second call
  exits early with 0-byte output (lock honoured).
- Hook invoked with a different `session_id="abc-test-2"` → re-injects the
  index (lock keyed on session, not invocation).

---

## [0.7.1] — 2026-04-28

**Hotfix.** Two SQL bugs that v0.7.0 (commits `b71e2e2` + later) shipped to
the memory layer were documented in
`session_handoff_20260427` / `lesson_compact_or_logic_kills_new_memories` /
`lesson_memory_list_scope_query_bug` but not yet fixed. This release closes
both. Bugs #3 and #4 from the handoff (Stop-hook recursion + curator
settings) were already correctly implemented in `ab-precompact-hook.sh` /
`ab-session-end-hook.sh` / `memory-curator-settings.json`; we verified them
during this pass and document them here.

### Fixed

- **`memory_compact` no longer eats fresh memories**
  (`lesson_compact_or_logic_kills_new_memories`).
  v0.7.0 used OR between `access_count < min_uses` and
  `last_accessed_at < cutoff`, which deleted records the curator had just
  saved (`access_count = 0` always satisfies `< 2`). Two-part fix:
  - `OR → AND` between thresholds — both signals must agree before a row
    is considered stale.
  - **Hard-coded grace period of 1 h** on `created_at` — defence-in-depth
    so any policy is incapable of removing brand-new memories regardless
    of caller mistakes.
- **`memory_list` no longer raises "Got 3, needed 2"**
  (`lesson_memory_list_scope_query_bug`).
  The scope clause was a string-template that didn't reference `?3` when
  `ctx` was empty, but `query_map` always bound 3 params. Fix: the SQL
  now always references `?3`, with a `?3 IS NULL OR …` guard so a missing
  scope is a no-op filter rather than a compile-time mismatch.

### Verified, no fix needed

- **Stop hook recursion** (`lesson_stop_hook_fires_on_subagent_exit`):
  `ab-session-end-hook.sh` line 6 already short-circuits via
  `[[ -n "$AB_MEMORY_CURATOR" ]] && exit 0`; `ab-precompact-hook.sh`
  line 106 sets that env var before launching the curator sub-agent.
- **Curator-settings file path**: `setup.rs` writes
  `~/.config/agent-bridge/memory-curator-settings.json`; the precompact
  hook reads from the same path — the path mismatch hinted at in
  `session_handoff_20260427` (`~/.claude/precompact-settings.json`) was
  stale notes from an earlier draft and is no longer present in code.
  The settings file's `hooks: { UserPromptSubmit: [], Stop: [] }` cleanly
  suppresses recursion in the curator sub-agent.

### Verification (`/tmp/v071_smoke.py`)

1. `memory_list { limit: 5 }` → returns rows, no error  ✅ (was: SQL bind error)
2. `memory_list { kind: "lesson", limit: 3 }` → also clean  ✅
3. `memory_save { key: fresh-…, … }` then
   `memory_compact { min_uses: 2, dry_run: true }` → fresh key NOT in
   removal list (grace period protects records < 1 h old)  ✅
4. `memory_compact { min_uses: 2, older_than_days: 30, dry_run: true }`
   → 0 rows would be removed (AND with `last_accessed > 30 d ago` fails
   for all our recent imports)  ✅

---

## [0.6.1] — 2026-04-27

**Hotfix.** v0.6.0 (and every prior version since v0.1) shipped a
`ChromiumCdpBackend` that would *permanently hang* on any `browser_*` call
once the underlying chrome process died (external `kill -9`, OOM, parent
session ending, etc.). The cause: `OnceCell<Browser>` cached the handle
forever with no health check; CDP itself has no inherent RPC timeout, so a
dead websocket would block tasks indefinitely.

### Fix

- Replaced `Arc<OnceCell<Browser>>` with `Arc<RwLock<Option<Arc<Browser>>>>`.
  `Browser` itself is not `Clone`, hence the inner `Arc`.
- New `is_alive()` probe: 500 ms timeout-wrapped `browser.version()` over
  CDP. Both timeout and protocol error count as "dead".
- `ensure_browser()` now does a fast-path read-lock health check; if the
  cached handle is missing or dead, it acquires the write lock,
  double-checks (so two concurrent callers don't both relaunch), then spawns
  a fresh chrome process.
- Stale `pages` map is cleared on relaunch — old `PageId`s pointed at the
  dead browser's targets and would all error anyway. Callers now get a
  clean `NotFound` instead of a confusing CDP error.

### Verification (`/tmp/v061_self_heal_test.py`)

1. `browser_navigate https://example.com` → 11 chrome PIDs spawned, page id A
2. `kill -9` all 11 chrome PIDs (simulates v0.6.0's failure mode)
3. `browser_navigate https://example.com` again → **2.1 s** to relaunch +
   navigate, page id B (B ≠ A)
4. `browser_eval` on B → `document.title = "Example Domain"` ✅
5. `browser_eval` on A → `isError=true: page id … not tracked` (expected,
   stale cache cleared)

---

## [0.6.0] — 2026-04-27

**Memory portability.** Cross-machine sync for agent self-memory, decoupled
from any specific transport. Export to a newline-delimited JSON file; move
that file via `scp` / email attachment / cloud drive / git repo / however;
import on the other side with a conflict-resolution policy of your choosing.

This is the prerequisite that makes v0.4 actually useful across more than
one machine — without export/import, every Claude installation is a memory
silo.

### Added

- **`memory_export(path, kind?, tags_any?, since_ts?)`** — write matching
  memories to a JSONL file (one [`MemoryRecord`] per line). Parent
  directories auto-created. Filters compose with AND.
- **`memory_import(path, conflict_policy?)`** — read a JSONL file and
  upsert each row. Policy is one of:
  - `skip` (default) — keep local row on key conflict
  - `overwrite` — always replace local with imported
  - `newer_wins` — replace only if `imported.updated_at > local.updated_at`

  Returns `{inserted, updated, skipped, malformed}`. Whole import runs in
  one SQLite transaction — a single bad line is counted in `malformed` but
  doesn't roll back the rest.

### Why JSONL

- **grep-friendly**: `grep '"kind":"lesson"' export.jsonl` works.
- **Append-able**: future `memory_export --append` is trivial to add.
- **Diff-able**: line-oriented JSON plays nicely with git, code review,
  and `diff -u`.
- **Stable across schema versions**: each line is a self-describing record;
  if v0.7 adds a field, v0.6 importers ignore it; v0.7 importers fill in
  defaults for missing fields.

### Tools surface

| Group        | Count | Change |
|--------------|------:|-------|
| Notify       | 3 |  |
| Terminal     | 3 |  |
| Browser      | 5 |  |
| Agent        | 5 |  |
| Worktree     | 3 |  |
| Memory       | **8** | **`memory_export`, `memory_import`** |
| **Total**    | **27** | (was 25 in v0.5.1) |

### Cookbook: cross-machine sync recipes

```bash
# Export everything to a portable file
mcp memory_export path=~/agent-bridge-backup.jsonl

# Filter: only lessons, only since last week (1 689 786 000 ≈ epoch secs)
mcp memory_export \
    path=~/lessons-since-monday.jsonl \
    kind=lesson \
    since_ts=1689786000
```

Transport options (all work — pick what fits your habits):

| Transport     | Setup cost | Sync feel       | Best for                     |
|---------------|------------|-----------------|------------------------------|
| `scp`         | 0          | manual, push    | one-off catch-up             |
| `~/Dropbox/`  | already on | auto on save    | always-on personal           |
| Git repo      | 5 min      | versioned merge | team / versioned audit trail |
| Email         | 0          | message-style   | air-gapped backups           |
| WebDAV / S3   | 30 min     | scriptable      | server fleets                |

### End-to-end verification

`/tmp/v06_smoke.py`:

1. Plant 3 memories with shared tag
2. `memory_export tags_any=[…]` → 3 rows, 670 bytes JSONL
3. Inspect file → 3 lines, full schema present
4. Delete originals; confirm gone
5. `memory_import policy=skip` → `inserted=3, updated=0, skipped=0`
6. Verify content + `access_count=1` round-tripped
7. Modify local; `import policy=skip` → 3 skipped (local kept) ✅
8. `import policy=overwrite` → 3 updated (export wins) ✅
9. Bump local newer; `import policy=newer_wins` → 3 skipped (local kept) ✅

---

## [0.5.1] — 2026-04-27

**Hotfix.** v0.5.0 shipped with a broken FTS5 sync trigger that made
`memory_delete` (and any DELETE-then-INSERT path on `memories`) raise
`SQL logic error`.

### Root cause

We created a content-stored FTS5 virtual table (`memories_fts` with no
`content=` clause) but used the contentless table's special `INSERT INTO
fts(fts, ...) VALUES('delete', ...)` command in the AFTER DELETE / AFTER
UPDATE triggers. That command is only valid on contentless FTS5 tables.
For content-stored tables the standard pattern is
`DELETE FROM fts WHERE rowid = old.rowid`.

### Fix

- `SCHEMA_V4` rewritten with the correct trigger pattern (for new installs).
- New **schema v5** migration drops + recreates the broken triggers on
  databases already at v4. Bumps `schema_meta.version` to `5`. Idempotent.

### Verification

`/tmp/hotfix_check.py` proves: previously-stuck `memory_delete` now succeeds;
fresh save→delete round-trip works; FTS index correctly drops the row
(post-delete search returns 0); pre-existing memories remain searchable
(no regression).

---

## [0.5.0] — 2026-04-27

Two ergonomic upgrades from using v0.4 in anger.

### Added

- **FTS5 full-text search for memories.** `memory_search` now uses SQLite's
  built-in FTS5 virtual table with bm25 ranking, replacing the previous
  `LIKE %query%` scan. Plain queries are tokenised + prefix-matched
  (`PageRank graph` → `PageRank* graph*`); inputs containing FTS5 operators
  (`"`, `*`, `:`, `(`, `)`, `AND`/`OR`/`NOT`/`NEAR`) pass through unchanged
  for power users (`"exit code" OR sigterm`). Rankings blend bm25 with the
  recency × frequency composite from v0.4.
- **Filterable `agent_session_list`.** Optional arguments:
  - `runtime_id` — exact match (`"claude-code"`).
  - `cwd_prefix` — prefix-match the working directory.
  - `state` — `"running"` (ended_at IS NULL) or `"finished"`.
  - `exit_code` — exact match (negative for signal kills, e.g. `-15` =
    SIGTERM, per the v0.3 convention).

  All filters combine with AND.

### Storage

- **schema v3 → v4 migration**: creates `memories_fts` (FTS5 virtual table)
  with `unicode61 remove_diacritics 2` tokeniser; INSERT/UPDATE/DELETE
  triggers keep it in sync with the base table; backfills the index from
  every existing memory row at upgrade time. Idempotent.

### Tools surface

| Group        | Count | Change |
|--------------|------:|-------|
| Notify       | 3 |  |
| Terminal     | 3 |  |
| Browser      | 5 |  |
| Agent        | 5 | (`agent_session_list` gains 4 filter args) |
| Worktree     | 3 |  |
| Memory       | 6 | (`memory_search` now FTS5-backed) |
| **Total**    | **25** | (no new tools — both upgrades are in-place) |

### End-to-end verification

`/tmp/v05_smoke.py`:

1. `memory_search "AiOT"` → 1 hit, `lesson_aiot_not_to_reuse`, score 3.32
2. `memory_search "PageRank graph"` → 2 hits, top is the lesson, score 3.11
3. `memory_search '"exit code"'` (quoted phrase, operator path) → 2 hits
4. `memory_search "Claude"` → 3 hits, top is `lesson_mcp_session_param_routing`
   because bm25 ranks the most-frequent "Claude Code" mentions higher
5. `memory_search "zzznonexistent"` → 0 hits ✅
6. `agent_session_list state=running` → returns running fakes
7. `agent_session_list cwd_prefix=/tmp/v05a` → only those rows
8. `agent_session_list runtime_id=codex` → 0 (correct empty)
9. `agent_session_list runtime_id=claude-code state=running` → AND combo
10. `agent_session_list exit_code=-15 cwd_prefix=/tmp/v05` after kills →
    matches the SIGTERMed bucket ✅

### Known FTS5 corner

The default `unicode61` tokeniser treats `_` as a token char, so
`v0.4.0_birth` tokenises to `["v0", "4", "0_birth"]`. Searching for `birth`
alone won't match — search for `0_birth` or just words from the body
(the content text is fully indexed). A future v0.6 may switch to the
`trigram` tokeniser if substring search becomes important.

---

## [0.4.0] — 2026-04-27

**Agent self-memory.** Cross-session persistence for the lessons / decisions /
todos / context that Claude (or any MCP-aware agent) accumulates while using
agent-bridge. Inspired by — but deliberately *not* a port of — the cognitive
graph memory in `/Data/CascadeProjects/AiOT`: that system optimises for 256-d
latent embeddings + PageRank-on-graphs at large scale; we want plain notes
indexed by key with optional hyperlink-style relationships, on the order of
a few thousand entries per user-year.

### Added

- **`memory_save(key, kind, content, tags?, related_keys?)`** — upsert one
  note. `key` is stable; same key overwrites content while preserving
  `created_at`. `related_keys` is a JSON array of OTHER memory keys the author
  thinks are causally linked (Web 1.0 hyperlinks, no graph algorithms).
- **`memory_get(key)`** — fetch one row. **Side effect**: atomically bumps
  `access_count` and `last_accessed_at`. This is what gives `memory_search`
  ranking and `memory_compact` something to score against.
- **`memory_search(query, tags_any?, limit?)`** — substring match over `key`
  and `content`, optional tag intersection. Hits are scored
  `recency_weight(30d half-life) + 0.3·ln(1 + access_count)` and ranked.
- **`memory_list(kind?, sort?, limit?)`** — `sort` ∈ `recent | frequent |
  newest`. Use this at session start with `kind="lesson"` to surface what
  previous-you learned.
- **`memory_delete(key)`** — drop one row by key.
- **`memory_compact({min_uses?, older_than_days?, dry_run?})`** — prune
  low-value rows; `dry_run=true` returns the keys that *would* be removed.

### Storage

- **schema v3 migration**: new `memories` table:
  ```
  key TEXT PK, kind TEXT, content TEXT, tags JSON, related_keys JSON,
  created_at, updated_at, last_accessed_at, access_count
  ```
  Indexes on `kind`, `last_accessed_at DESC`, `updated_at DESC`,
  `access_count DESC`. Idempotent migration — bumps `schema_meta.version`
  to `3`; v2 databases upgrade in place at next open.
- `MEMORY_CONTENT_CAP = 256 KiB` per row, clamped at write time.

### Why not graph + PageRank?

We considered AiOT's GraphMemoryBridge wholesale. Three things ruled it out:

1. **Quantitative**: PageRank is a power-law algorithm; on a few-thousand-node
   "graph" every node is "cold", the algorithm collapses to noise.
2. **Intent mismatch**: Claude reaches for memory via keyword recall ≫ graph
   walks ≫ vector similarity. SQL `LIKE` covers 90% of real lookups.
3. **Cross-language cost**: AiOT is Python + Rust FFI. agent-bridge's
   "zero system dependency" promise would die.

Verdict: keep the *idea* of recency decay + access-count weighting +
explicit relationships, ditch the algorithms.

### Tools surface

| Group        | Count | New |
|--------------|------:|-----|
| Notify       | 3 |  |
| Terminal     | 3 |  |
| Browser      | 5 |  |
| Agent        | 5 |  |
| Worktree     | 3 |  |
| **Memory**   | **6** | **all of `memory_*`** |
| **Total**    | **25** | (was 19 in v0.3.0) |

### End-to-end verification

`/tmp/v04_smoke.py` drives a fresh `agent-bridge mcp` subprocess through the
full lifecycle:

1. `tools/list` → 25 tools, the 6 `memory_*` present.
2. `memory_save` × 3 (lesson + decision + todo with cross-references).
3. `memory_get` twice on the lesson → `access_count` went `0 → 1 → 2`.
4. `memory_search "exit_code"` → ranked the lesson first (score 1.330).
5. `memory_search "v0" tags_any=["v0.3"]` → tag intersection works.
6. `memory_list sort=frequent` → lesson (ac=2) tops decision/todo (ac=0).
7. `memory_compact min_uses=10 dry_run=true` → reports 3 would-delete keys.
8. `memory_get` confirms dry-run preserved the data.
9. `memory_delete` × 3 → `{deleted: true}` for all.
10. Final `memory_get` → `null`. Clean. ✅

---

## [0.3.0] — 2026-04-26

Two ergonomic upgrades that came straight out of using v0.2 in anger.

### Added

- **`agent_kill`** — send SIGTERM to a running session. The background wait
  task still finalises the session row with the resulting exit code, so a
  killed session remains queryable via `agent_session_get` (with whatever
  partial stdout/stderr was captured up to the kill point).
- **MCP image content block** — `ContentBlock::Image { data, mimeType }` per
  MCP 2024-11-05 spec; `ToolResult::image` / `image_with_caption` helpers.
- **`browser_screenshot inline=true`** now returns the PNG as a real MCP
  image block (Claude renders it directly into context) plus a one-line
  text caption — instead of a `data:image/png;base64,…` string.

### Changed

- `ClaudeCodeRuntime` keeps a `DashMap<SessionId, pid>` of live children;
  the wait task removes entries on exit. This is the substrate `kill` uses.
- Exit codes recorded by the store now encode signal-killed sessions as
  **negative** numbers (e.g. `-15` for SIGTERM, `-9` for SIGKILL). On Unix
  `std::process::ExitStatus::code()` returns `None` for signal kills, so
  this is the agreed convention to keep the `exit_code` column non-null
  when something *did* happen.

### Tools surface

| Group        | Count | New |
|--------------|------:|-----|
| Notify       | 3 |  |
| Terminal     | 3 |  |
| Browser      | 5 | (`browser_screenshot inline=true` now returns image block) |
| **Agent**    | **5** | **`agent_kill`** |
| Worktree     | 3 |  |
| **Total**    | **19** | (was 18 in v0.2.0) |

### End-to-end verification

`/tmp/v03_smoke.py` drives a fresh `agent-bridge mcp` subprocess:

1. `browser_navigate` + `browser_screenshot inline=true` →
   2 content blocks: `image/png` (17 634 raw bytes, ~23 KB base64) +
   text caption ✅
2. `agent_spawn` → fake-claude blocker (`bash -c "echo …; sleep 30"`) →
   `agent_session_get` confirms `ended_at == null` (running) →
   `agent_kill` returns `SIGTERM sent` →
   `agent_session_wait` returns within milliseconds with `exit_code = -15`,
   captured stdout intact ✅
3. Second `agent_kill` on the same id → `NotFound` error (idempotent) ✅

---

## [0.2.0] — 2026-04-26

Closes the `agent_spawn` loop. Sub-agent stdout / stderr / exit_code are now
persisted to SQLite; three new MCP tools let the parent agent (and the human)
introspect every session that ever ran.

### Added

- **`agent_session_list(limit?)`** — newest-first summary of all sessions
  (id / runtime / cwd / started_at / ended_at / exit_code, plus stdout/stderr
  byte counts). stdout/stderr bodies omitted from this listing for token
  economy.
- **`agent_session_get(id)`** — full row including the captured stdout and
  stderr (each clamped to 64 KiB).
- **`agent_session_wait(id, timeout_secs?)`** — blocks (polls every 500 ms,
  default 60 s, max 600 s) until the session finishes; returns the final row
  on success, or `timed_out=true` plus the in-flight row on timeout.

### Changed

- `ClaudeCodeRuntime` accepts an optional [`StateStore`] (`with_store`). When
  attached it writes an in-flight row at spawn and an UPDATE with
  exit_code / stdout / stderr after the child exits.
- `StateStore::list_sessions` now takes a `limit` (was unbounded).

### Storage migration

- **schema v1 → v2**: `sessions` gains `exit_code INTEGER`, `stdout TEXT`,
  `stderr TEXT` columns. Migration is idempotent — existing rows keep their
  data and get NULL values for the new columns. Bumps `schema_meta.version`
  to `2`.

### Tools surface

| Group        | Count | Names |
|--------------|------:|-------|
| Notify       | 3 | `notify`, `notifications_recent`, `osc_parse` |
| Terminal     | 3 | `terminal_list`, `terminal_send_keys`, `terminal_split` |
| Browser      | 5 | `browser_navigate`, `browser_eval`, `browser_snapshot`, `browser_click`, `browser_screenshot` |
| **Agent**    | **4** | `agent_spawn`, **`agent_session_list`**, **`agent_session_get`**, **`agent_session_wait`** |
| Worktree     | 3 | `worktree_list`, `worktree_create`, `worktree_remove` |
| **Total**    | **18** | (was 15 in v0.1.0) |

### End-to-end verification

End-to-end Python harness (`/tmp/v02_smoke.py`) drives a fresh `agent-bridge
mcp` subprocess with `AGENT_BRIDGE_CLAUDE_BIN=/usr/bin/echo` (no API tokens
spent), proves:

1. `initialize` → server reports `agent-bridge / 0.1.0`
2. `tools/list` → 18 tools registered, the 3 new `agent_session_*` present
3. `agent_spawn` → returns session id, child runs to completion
4. `agent_session_wait` → returns `timed_out=false` + final row including
   `exit_code=0` and `stdout="-p this prompt becomes echo's argument\n"`
5. `agent_session_list` / `agent_session_get` → roundtrip same row

---

## [0.1.0] — 2026-04-26

First public release. **Linux-native AI-agent control plane** reaching feature
parity with the cmux core surface, plus Claude-Code-native superpowers via the
Model Context Protocol.

### Run modes (single binary)

- `agent-bridge daemon` — long-lived JSON-RPC server on
  `$XDG_RUNTIME_DIR/agent-bridge/bridge.sock`.
- `agent-bridge mcp` — stdio MCP server, drop-in for
  `claude mcp add agent-bridge ...`.

Both modes share the same backend bundle (`Hub`) so business logic is written
once and exposed through two ergonomically distinct interfaces (CLI for humans,
MCP for AI agents).

### 15 MCP tools

| Group | Tools |
|-------|-------|
| **Notify**    | `notify`, `notifications_recent`, `osc_parse` |
| **Terminal**  | `terminal_list`, `terminal_send_keys`, `terminal_split` |
| **Browser**   | `browser_navigate`, `browser_eval`, `browser_snapshot`, `browser_click`, `browser_screenshot` |
| **Agent**     | `agent_spawn` |
| **Worktree**  | `worktree_list`, `worktree_create`, `worktree_remove` (each accepts optional per-call `repo` param — switch repos without restarting the MCP server) |

### 6 pluggable trait boundaries

`Notifier` · `BrowserBackend` · `AgentRuntime` · `TerminalBackend` ·
`StateStore` · `McpTool`. Default impls land first; future backends only
need to satisfy the trait.

### Default backends shipped

- **DbusNotifier**       — pure-Rust D-Bus (`zbus`).
- **SqliteStore**        — bundled SQLite (`rusqlite/bundled`), WAL journal,
  zero system dependency.
- **WezTermBackend**     — wraps `wezterm cli list / send-text / split-pane`.
- **ChromiumCdpBackend** — Chrome DevTools Protocol via `chromiumoxide`,
  lazy-launch, headed by default (`AGENT_BRIDGE_HEADLESS=1` to flip).
- **ClaudeCodeRuntime**  — `claude -p` one-shot spawning.
- **GitWorktreeManager** — concrete (single impl by design) wrapper around
  `git worktree {add,list,remove}`.

### Engineering deltas vs P0 baseline

| Phase  | Surface added                                                            |
|--------|--------------------------------------------------------------------------|
| P0     | Unix-socket JSON-RPC daemon, D-Bus desktop notifications, agent-cli      |
| P1-A   | SQLite history store + `notifications.recent` + agent-cli `history`     |
| P1-B   | Streaming OSC 9/99/777 parser (10 unit tests) + WezTerm CLI backend     |
|        | + WezTerm Lua hook example                                               |
| P1-E   | MCP stdio server (initialize / tools/list / tools/call) + 6 tools first |
| P1-D   | ChromiumCdpBackend (CDP) + 5 browser tools                               |
| P1-C   | GitWorktreeManager + ClaudeCodeRuntime + agent_spawn + 3 worktree tools |

### End-to-end verifications (every claim has a paper trail)

- ✅ MCP `initialize` → `tools/list` → `tools/call` round-trip
- ✅ All 15 tools registered, JSON Schema valid
- ✅ Real Chromium navigation to https://news.ycombinator.com → 5 stories
  scraped via JS eval; full-page PNG ≈ 254 KB
- ✅ `browser_click` triggers real DOM event; URL transitions
  `/` → `/item?id=47909226`; subsequent eval scrapes 3 top comments
- ✅ `worktree_list(repo=...)` parallel calls across 4 different repos
  in a single Claude session (zero MCP-server restarts)
- ✅ `agent_spawn` launches a sibling Claude that reads a source file,
  writes the answer to `/tmp`, and exits — verified via filesystem
- ✅ Notifications persist across daemon restarts (SQLite WAL)
- ✅ stderr / stdout strict separation in MCP mode (no protocol pollution)
- ✅ 11 unit tests pass (10 OSC parser + 1 git porcelain parser)

### Stats

- 9 crates (8 lib + 1 daemon binary, plus `agent-cli`)
- ~3 700 lines of Rust
- 42 source files
- Zero system dependencies (zbus / rusqlite-bundled / chromiumoxide all
  pure-Rust paths)
- Release binary: 12 MB (`agent-bridge`) + 1.2 MB (`agent-cli`), strip+LTO
- Cold compile: ~2.5 min (chromiumoxide-heavy); incremental: < 15 s

### Known limits / non-goals (yet)

- `ClaudeCodeRuntime::send_input` returns an error — interactive PTY mode
  needs `portable-pty`; the one-shot `-p` path is sufficient for parallel
  agent orchestration today.
- `terminal.subscribe` returns an empty stream — wezterm has no native event
  firehose; OSC events are expected to arrive via the `osc.parse` RPC fed by
  the Lua hook in `examples/wezterm/`.
- No GUI. Two interfaces only: `agent-cli` (humans) and the MCP server (AI).
- Single-host: no Postgres / multi-machine `Hub` yet.

### Configuration (env vars)

| Variable                  | Default                                             | Effect                              |
|---------------------------|-----------------------------------------------------|-------------------------------------|
| `AGENT_BRIDGE_SOCKET`     | `$XDG_RUNTIME_DIR/agent-bridge/bridge.sock`         | Override daemon socket path         |
| `AGENT_BRIDGE_REPO`       | `$PWD`                                              | Default repo for `worktree_*` tools |
| `AGENT_BRIDGE_HEADLESS`   | unset (= headed)                                    | `1` for headless Chromium           |
| `AGENT_BRIDGE_CHROME`     | auto-detect                                         | Path to chrome/chromium binary      |
| `AGENT_BRIDGE_CLAUDE_BIN` | `claude`                                            | Override claude CLI path            |
| `RUST_LOG`                | `info`                                              | Standard tracing-subscriber filter  |

### Refinements after the P0..P1 baseline commit

- **fix(browser)**: per-PID user-data-dir avoids `SingletonLock` collisions
  when multiple agent-bridge processes share the same machine
  (`crates/browser/src/chromium_cdp.rs`).
- **feat(worktree)**: `worktree_list / _create / _remove` accept an optional
  per-call `repo` parameter, so Claude can hop between repos within one
  MCP session instead of restarting (`crates/bridge/src/mcp_tools.rs`).
- **docs**: README rewritten to match the final 15-tool surface.
