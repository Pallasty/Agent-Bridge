# New-node acceptance runbook

Bringing a fresh host into the agent-bridge mesh is four install steps that
already have tooling, plus an acceptance pass that did not exist as a written
flow until now. The two failure modes this runbook exists to catch:

1. **Sync success ≠ memory usable.** CJK long-ledger rows (nightly digests,
   surveys) are reachable **only through the semantic channel** — fts and
   hybrid are blind to them (measured 2026-07-14, consistent across two digest
   batches). A node that silently falls back to the `hash` embedding backend
   imports every row correctly and still cannot retrieve the consolidation
   layer. The store looks intact; recall is hollowed out.
2. **The nightly consolidation loop assumes a single writer.** If two nodes
   both run the digest/distill timers, both author draft rows for the same
   topics and the copies collide through sync; write-time dedup is
   near-blind on CJK content, so the collision lands as duplicate live rows.

Stages 1–2 verify the install. Stage 3 gates the model config with a
positive-control probe. Stage 4 declares the node's role. Stage 5 says what
does **not** need to be injected, and why.

## Stage 0 — install (existing tooling, listed for completeness)

| Step | Tool | Notes |
|---|---|---|
| Binary | `scripts/deploy_from_master.sh` or scp a release build | must come from merged master, never a feature branch |
| Wrapper | `scripts/wrapper/install.sh` | idempotent; real binary moves to `agent-bridge.real`, wrapper sources machine.env |
| Per-host env | copy `scripts/wrapper/machine.env.example` → `~/.config/agent-bridge/machine.env` | per-host, never committed; credentials are owner-installed only |
| Memory seed | `agent-bridge sync` (canonical, git-backed) or `scripts/sync-handoff.sh` (one-shot push) | see docs/CROSS-MACHINE-SYNC.md |
| Hooks + client config | `agent-bridge setup` per frontend | verified in stage 2, not trusted blindly |

## Stage 1 — install verification

- `~/.local/bin/agent-bridge` is the **wrapper** (small shell script), the
  real binary is `agent-bridge.real` (ELF/Mach-O). If the wrapper was
  clobbered by a binary copy, reinstall it — never the other way around.
- `machine.env` exists and sets what this host needs (context window only on
  a true 1M host; embedding knobs per stage 3). Do not print its values.
- Setup state applied: `readiness_audit` reports
  `setup_state.status = "applied"` and `ready = true`.

## Stage 2 — capability probe (read-only tools)

Run from any connected agent session:

- `readiness_audit {include_local_install: true, repo_root: <checkout path>}` —
  pass `repo_root` explicitly; auto-detection can return null on a deployed
  binary and then every source-asset check reads as spuriously missing.
- `hook_status` — every hook: installed, executable, recent run with exit 0.
  A hook that exists but has never fired is not accepted; open a session, do
  a trivial turn, re-check.
- `capabilities` — confirms the tool profile the frontend actually got.

## Stage 3 — model / embedding gate

**Decision table** (knobs and the recommended installer are documented in
`scripts/wrapper/machine.env.example`):

| Host situation | Backend | How |
|---|---|---|
| ≥ ~3 GB RAM headroom | gte-768 int8, local | `scripts/deploy-gte-int8-embedding.sh` (once per host) |
| RAM-constrained, a peer daemon-http is reachable | delegation | `AGENT_BRIDGE_EMBED_REMOTE_URL` → peer `/embed` (aio2 precedent, 2026-06-27) |
| Neither | **do not accept the node** | `hash` is a seeding-time fallback, not an operating mode |

**Reindex after backend choice.** `sync-handoff.sh` imports under
`embed=hash` by design. Once the real backend is configured, run
`memory_reindex` so every seeded row gets real embeddings. Skipping this is
exactly failure mode 1.

**Positive-control retrieval probe.** Per the verdict-validity rule
(scripts/eval/README.md): an acceptance check is only valid if it can detect
a known positive. The known positives are the promoted digest vehicles, which
rank 1–3 semantic on the primary node (2026-07-14):

| Query (mode=semantic) | Expected vehicle, rank ≤ 5 |
|---|---|
| owner 的安全-自由权衡原则 + 记忆价值决策权授予是什么？ | `digest_owner_security_freedom_and_memory_value_grants_20260714` |
| AB 内部回归基尺 (eval benchmark) 是怎么建的、修过哪些 bug？ | `digest_ab_internal_eval_benchmark_build_and_fixes_20260714` |
| 记忆生命周期里 supersede 怎么工作（声明边 vs 自动去重）？ | `digest_supersede_lifecycle_declared_vs_autodedup_20260714` |

Run via `memory_search {mode: "semantic"}` from a session on the new node,
with `AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=eval` at the process boundary so
the probe does not pollute organic telemetry. All three vehicles at rank ≤ 5
⇒ PASS. Any miss ⇒ the node is not accepted; suspect the embedding backend
first, then sync completeness. If these vehicles are ever archived, replace
them with the current `answer_vehicle` entries in
`scripts/eval/fixtures/synthesis_queries.json` — the probe must always use
rows that demonstrably rank on the primary node.

## Stage 4 — role declaration

Exactly **one consolidator per mesh**. Every store-mutating nightly pass —
decay (03:42), distill (04:30), digest (05:00) — runs only there. Every
other node is a replica: sync timer only.

| Timer | Consolidator | Replica |
|---|---|---|
| agent-bridge-sync.timer | on | on |
| agent-bridge-memory-decay-unused.timer | on | off |
| agent-bridge-distill.timer | on | off |
| agent-bridge-digest.timer | on | off |

Install accordingly:

```bash
./scripts/systemd/install.sh            # consolidator (all timers)
./scripts/systemd/install.sh --replica  # replica (sync only; disables the
                                        # three consolidator timers if a
                                        # previous full install enabled them)
```

Moving the consolidator role = enable the three timers on the new node,
`--replica` the old one, in that order on a quiet day (no overlap across a
05:00 boundary).

## Stage 5 — what is NOT injected, and why

- **CLAUDE.md**: repo-level static contract, rides git — a clone already has
  it. Never hand-copy AB memory rows into it; that creates a second source of
  truth that drifts from the store.
- **AGENT.md / USER.md**: generated from the store (session_finalize writes,
  bootstrap injects, 50% drift cap). A new node gets them through sync +
  regeneration. No manual step.
- **Runtime context**: session_bootstrap kernel block + floor index lines are
  the official store→context channel. Per-session, on demand, follows the
  store as it evolves — strictly better than freezing rows into a static
  file.
- **Harness-level memory dirs** (e.g. Claude Code auto-memory `MEMORY.md`):
  node-local caches. The AB store is canonical; do not file-sync these across
  nodes. They rebuild naturally as sessions run on the new node.

The only static per-node truth lives in `machine.env` (this host's window
size, embedding knobs, traffic class) — which is exactly why it is per-host
and uncommitted.
