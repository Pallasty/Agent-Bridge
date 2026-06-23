# GTE Embedder Flag-Day Acceptance Runbook

Date: 2026-06-23

Host: macOS (`maxiaodeMac-Pro.local`)

Worktree: `/Users/pallasting/Projects/agent-bridge-gte-flagday-acceptance-plan`

Branch: `codex/gte-flagday-acceptance-plan`

Base commit: `1968c1d test(mcp): cover stdio eof teardown`

Scope: docs-only acceptance and runbook plan for a future GTE embedder cut-over.
This report does not approve, execute, or automate the live migration.

Verdict: `flagday_plan_ready_for_owner_review`

## Board Window

Thread #120 was read through post #4024 before this slice started.

Controlling posts:

- #4016: GTE production path validated on a scratch snapshot copy. The author
  reported a full active-row re-embed to 768-dim `gte` vectors and an improved
  canonical `recall_eval` hard-tier semantic R@10, but explicitly held live
  cut-over for owner coordination.
- #4024: a separate Codex session claimed the held-out policy-benefit eval plan
  for trigger pre-policy hold. This slice intentionally does not touch that
  lane.
- #4025: this docs-only GTE flag-day acceptance/runbook slice was claimed with
  no live DB mutation, no reindex, no deploy, no default `memory_search` change,
  and no production `enforce_hold`.

## Current Master Facts

These facts were verified from the worktree at `1968c1d`:

- `crates/store/src/vector.rs` still defines `VECTOR_DIM = 384`.
- `select_model()` on master supports `all-MiniLM-L6-v2`,
  `multilingual-e5-small`, and `paraphrase-multilingual-MiniLM-L12-v2`; it does
  not yet include a GTE arm.
- `crates/store/examples/reindex_to_active_model.rs` defaults to the real
  production store unless an explicit DB path is passed. Any rehearsal must pass
  a scratch-copy path.
- `memory_reindex_embeddings(only_stale=true)` rewrites active rows whose
  embedding is missing, whose `embedding_backend` is null, or whose backend tag
  differs from the current backend.
- the reindex path refuses to write hash fallback vectors under a non-hash
  backend name.
- `recall_eval` currently auto-detects `multilingual-e5-small` and
  `paraphrase-multilingual-MiniLM-L12-v2` from `embedding_backend`; a GTE
  cut-over candidate must extend this detection before its semantic score can be
  accepted as live evidence.

Implication: #4016 is evidence for a candidate production path, not evidence
that master has already cut over. The flag-day needs an implementation commit,
dual-node deployment, live-store reindex, and reconnect gate before it can be
called production.

## Non-Goals

This plan does not authorize:

- running `reindex_to_active_model` against Mac or aio2 live stores;
- changing `VECTOR_DIM`, embedder selection, or `recall_eval` in this slice;
- enabling production `enforce_hold`;
- changing default `memory_search` behavior or ranking order;
- widening Codex MCP tool surfaces;
- fabricating or restoring phantom gold rows;
- treating a single-host scratch result as live production acceptance.

## Acceptance Gates

The future cut-over can be accepted only if every gate below is green.

### Gate 1: Candidate Commit Is Explicit

The candidate implementation commit must be named before any live action. It
must include at least:

- `VECTOR_DIM = 768` or an equivalent dimension source of truth;
- a GTE model selection arm with a stable `embedding_backend` name, expected to
  be `gte-multilingual-base` unless the owner chooses another exact label;
- local-model loading instructions, including model directory, file list, and
  any pooling/prefix behavior;
- `recall_eval` alias detection for the GTE backend;
- tests or direct evidence that old 384 rows are handled as stale or that the
  process is safe only with clients stopped.

If this gate is not met, the run stops before deployment.

### Gate 2: Rehearsal Uses a Copy

Before live migration, both Mac and aio2 must run the candidate on a copied DB.

Required evidence:

- source DB path and copied DB path;
- source DB sha256 or timestamped backup path;
- command line showing the copy path was passed explicitly to
  `reindex_to_active_model`;
- active-row count before and after;
- `embedding_backend` distribution before and after;
- vector byte-length distribution before and after;
- no hash fallback writes;
- no active rows left with null, mismatched, or old backend tags unless they are
  individually explained.

The rehearsal must never mutate the original snapshot or live store.

### Gate 3: Reader Compatibility Is Decided

Before live migration, the owner must decide which compatibility mode the
candidate provides:

- `mixed_readers_supported`: the 768-capable binary can safely open a 384 store
  before reindex and treat old rows as stale, so deployment can precede reindex;
- `atomic_node_cutover_only`: the 768-capable binary cannot safely serve a 384
  store before reindex, so all MCP clients for that node must be stopped while
  binary replacement and reindex happen as one maintenance action.

If the candidate cannot prove `mixed_readers_supported`, assume
`atomic_node_cutover_only`.

### Gate 4: Dual-Node Deployment Is Serialized

Mac and aio2 must both be on a GTE-capable binary before any live 768 vectors
are exposed to readers that may still use the old 384 code path.

Minimum sequence:

1. Announce maintenance window and freeze non-essential memory writes.
2. Capture process inventory: active MCP PIDs, stale MCP PIDs, `.real` sha256,
   branch/commit, and doctor output on both nodes.
3. Back up live DB files and installed binaries on both nodes.
4. Stop or reconnect clients according to Gate 3.
5. Install the candidate binary on Mac and aio2.
6. Verify both installed binaries report the candidate commit and GTE-capable
   behavior.
7. Run live reindex one node at a time, only after its reader state is safe.
8. Reconnect MCP clients.
9. Re-run post-cutover acceptance on both nodes.

If aio2 is unavailable or unverified, do not partially cut over Mac unless the
owner explicitly accepts a single-node maintenance window and rollback boundary.

### Gate 5: Store Invariants Hold

After live reindex, each live store must satisfy:

- all active rows that participate in semantic search have
  `embedding_backend = 'gte-multilingual-base'` or the owner-approved exact GTE
  label;
- all active semantic embeddings have byte length `3072` for 768 f32 values;
- old 384 active rows are zero or explicitly quarantined outside semantic
  search;
- inactive/stale rows are either intentionally untouched or separately reported;
- no row is stamped as GTE when its vector matches the hash fallback detector;
- `memory_embedding_backend_counts` and direct SQL agree on distribution.

### Gate 6: Recall Evidence Reproduces the Benefit

The production cut-over must reproduce the #4016 direction on the active live
store or explain corpus drift before acceptance.

Minimum acceptance:

- `recall_eval` semantic mode is enabled with a real GTE model confirmed;
- the harness reports the GTE backend name, not hash and not an old 384 backend;
- hard-tier semantic R@10 is at least the #4016 scratch threshold of `0.625`, or
  a lower result is explicitly justified by corpus drift and accepted by owner;
- hard-tier semantic R@10 remains higher than the same-run FTS hard-tier R@10;
- easy and moderate tiers do not regress enough to erase the hard-tier gain;
- misses #1 and #14 from #4016 are reviewed as either genuine hard misses or
  weak/phantom gold, not silently ignored.

This gate is about the main `recall_eval` anchor, not a trigger-only cohort.

### Gate 7: Post-Reconnect Surface Is Current

After reindex, run MCP/live checks on both nodes:

- `capabilities` confirms the expected toolset/profile and memory backend state;
- `doctor --json` has no current MCP servers mapped to the old `.real`;
- stale old-reader rows are either gone or clearly attributed to inactive
  historical sessions;
- direct `tools/list` remains within the intended profile boundary;
- no new Niche or GTE-only tools become visible to Codex by default.

## Rollback Plan

Rollback must be prepared before live reindex starts.

Required rollback packet:

- backup paths for DB, WAL, SHM, and installed binary on each node;
- exact old binary sha256 and source commit;
- exact candidate binary sha256 and source commit;
- stop-client procedure;
- restore commands for DB and binary;
- reconnect procedure;
- verification commands proving old 384 readers are again paired with a 384
  store.

Rollback rule: never start an old 384 reader against a 768 live store. If
rollback is needed after 768 vectors are written, stop clients first, restore the
384 DB backup, restore the old binary, then reconnect.

## Stop Conditions

Stop before live mutation if any condition appears:

- no explicit owner greenlight for the implementation commit and maintenance
  window;
- aio2 cannot verify the candidate binary or model files;
- a client using the old 384 binary is still active and can attach to a store
  that will receive 768 vectors;
- candidate `recall_eval` cannot identify GTE as the active semantic backend;
- scratch rehearsal writes hash fallback vectors or leaves unexplained mixed
  active backend/dimension rows;
- live backup paths are missing or unverified;
- the held-out policy-benefit eval lane (#4024) reports a contradictory
  constraint that changes production memory-search approval.

## Owner Decisions Needed

Before execution, the owner must decide:

1. Exact candidate commit and whether to merge it before or during the
   maintenance window.
2. Exact GTE backend label and model artifact path/hash for Mac and aio2.
3. Whether the candidate supports mixed 384/768 read mode or requires atomic
   per-node cut-over.
4. Maintenance window and write-freeze policy.
5. Minimum acceptable `recall_eval` thresholds if live corpus drift changes the
   #4016 numbers.
6. Whether inactive/stale rows remain 384 or are migrated in a later slice.
7. Who posts final acceptance and who owns rollback if post-cutover checks fail.

## Suggested Final Acceptance Post

The final Agent-Bridge forum closeout should include:

- implementation commit;
- Mac and aio2 installed binary sha256;
- DB backup paths;
- pre/post backend and byte-length distributions;
- reindex command evidence for each live store;
- `recall_eval` output with hard-tier anchor;
- doctor/current `.real` evidence after reconnect;
- rollback packet location;
- explicit statement that production `enforce_hold`, trigger held-out policy
  eval, and default tool-surface boundaries were not changed by the GTE cut-over.

## Verification For This Slice

This docs-only slice should be verified with:

```bash
git diff --check
```

No Rust tests are required because no code or runtime behavior changes in this
slice.
