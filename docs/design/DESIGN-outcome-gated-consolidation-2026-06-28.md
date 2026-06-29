# DESIGN — Outcome-Gated Memory Consolidation

Status: **Proposed** (design only — no code in this PR)
Date: 2026-06-28
Scope: `crates/store` (sqlite), `crates/bridge` (mcp_tools)
Methodology: dry-run-first + staged opt-in gates (same discipline as the
biocortex retrieval opt-in contract and `trigger_recall_opt_in`).

## 1. Problem

agent-bridge already *records* and *reports* retrieval feedback, but never
lets it **act**. The loop today is open:

- `memory_retrieval_feedback` (`crates/bridge/src/mcp_tools.rs:21506`) writes a
  `kind=feedback` row + an outcome-specific edge (`retrieval_used` /
  `_ignored` / `_stale` / `_duplicate` / `_harmful` / `_too_large`) to the
  target (`mcp_tools.rs:21569-21793`).
- `memory_consolidation_queue` (`mcp_tools.rs:36710`) buckets the four negative
  outcomes **read-only** (`stale_warnings`, `duplicate_lessons`,
  `harmful_memories`, `too_large_memories`).
- A human eyeballs the queue and manually runs `memory_consolidate` /
  `memory_compact` / `session_finalize`.

The missing arrow is **"queue bucket → mutation"**: nothing consolidates or
archives automatically from corroborated feedback, and the queue's scores are
display values, not actionable decisions. We want feedback to *drive*
consolidation/archival — safely, reversibly, and OFF by default.

## 2. Grounded current state (file:line)

**Schema** (`crates/store/src/sqlite.rs`):
- `memories` (V3 `:118-128`, V7 `:248-273`): `key` PK, `kind`, `content`,
  `tags` JSON, `related_keys` JSON, `created_at`, `updated_at`,
  `last_accessed_at`, `access_count`, `importance REAL DEFAULT 0.5`,
  `status TEXT DEFAULT 'active'` (`active|archived|superseded`). V22 `:496-508`
  adds `superseded_by`.
- `memory_edges` (V6 `:171-181`): `(from_key, to_key, edge_type)` PK, `weight`.
  Canonical weights in `weight_for_edge_type` `:22-59`.
- `MemoryRecord` struct: `crates/store/src/lib.rs:197-234`. **Note:**
  `last_decayed_at` and `fts_content` are *columns but deliberately NOT struct
  fields* — node-local hygiene, not synced (V33 comment `sqlite.rs:1365`).

**Lifecycle primitives** (all soft, none hard-delete):
- `memory_decay_importance` `sqlite.rs:4968-5056` — `importance *
  0.5^(age/half_life)`, advance-on-write anchor (kills compounding), archives
  when `< threshold` AND not durable.
- `memory_decay_unused_importance` `sqlite.rs:5058-5108` — fixed-step decay for
  unaccessed rows, floored.
- `memory_compact` `sqlite.rs:5246-5332` — `status='tombstoned'` (not DELETE)
  for low-use + old + `importance < 0.6` + no edges/related_keys; 1h grace;
  purged after 7d by `memory_purge_tombstones`.
- `memory_consolidate` `mcp_tools.rs:23245-23567` — content-Jaccard, grouped
  **by_kind**, winner = `importance*(1+access_count)` (`:23405`), archives
  loser + mints `supersedes` edge (executor `:23490`). `dry_run=true` default.
- `session_finalize` `mcp_tools.rs:47658-47903` — decay → compact → optional
  export; hints `memory_consolidate` when active ≥ 60; emits a Verified
  `finalize_readback` SemanticEvent (`:47846`).

**Feedback vocabulary** (`mcp_tools.rs:21424-21495`):
`Used|Ignored|Stale|Duplicate|Harmful|Missing|TooLarge`. `Missing` mints no
edge (corpus-gap signal, no target).

**House gating pattern to reuse** (do not invent a new one):
`BioCortexRetrievalOptInRequest::evaluate() -> blockers`
(`crates/store/src/lib.rs:300-406`) and the
`trigger_recall_opt_in` ladder (`crates/bridge/src/trigger_recall_opt_in.rs`):
`status -> runtime_transition_gate -> gated_baseline_trial -> approval ->
execution`, with a `side_effects` inventory that is **all-false until the
execution stage** (`trigger_recall_opt_in.rs:729-741`).

## 3. ⚠️ Blocker found by code audit (must ship in the same PR as Stage 0)

**The durable-memory guard self-defeats the entire feature.** Both archival
primitives treat **any inbound edge** as "durable / do not touch":
- `memory_compact` `sqlite.rs:5290-5296`:
  `NOT EXISTS (SELECT 1 FROM memory_edges WHERE from_key=key OR to_key=key)`
- `memory_decay_importance` `sqlite.rs:5034`: `edge_keys` from `UNION SELECT to_key`

But **every feedback writes an edge `to_key=target`** (`mcp_tools.rs:21740`).
So a *single* `stale`/`harmful` flag makes a memory **permanently immune** to
exactly the primitives this design delegates to — the loop would silently
no-op on every flagged target.

**Fix A (BLOCKER):** narrow the durable guard to ignore `retrieval_*` edge
types when computing edge-connectedness, while still protecting real hubs
(`relates|supersedes|corrects|caused_by|…`). Ship it behind its own SQL change
with a dry-run readback (count rows that gain eligibility) so the blast radius
is sized before anything can archive.

## 4. Chosen design — `queue-driven-gated-apply` (+ 3 grafts)

Selected over `aggregate-counters` (schema-heavy, breaks the node-local-hygiene
convention, counters never decay) and `eligibility-trace` (best temporal
fidelity but adds a hot-path write per feedback + a derived/stored drift
burden). The queue-driven spine is the only design whose core claim survives
contact with the code: `memory_consolidation_queue_from_records`
(`mcp_tools.rs:36710`) is **already a pure fn receiving `edges_by_key`**, so
corroboration + per-candidate gated actions cost **zero DDL, no `MemoryRecord`
change, no hot-path write**.

**Spine:** keep the queue as the single candidate source of truth, but have it
emit, per candidate, a structured **gated action**
(`{verb, target_key, corroboration_count, distinct_sources, score,
evidence_feedback_keys, candidate_blockers[]}`) instead of a display row. A thin
staged opt-in gate consumes those actions; only when every gate passes does
`session_finalize` apply them — dry-run default, OFF default, with an approval
packet + readback. Verbs dispatch to **existing** primitives (no new mutator):
`stale|duplicate → memory_consolidate executor (mcp_tools.rs:23490) / decay`,
`harmful → archive (status='archived', never tombstone)`,
`too_large → rewrite-queue only (never auto-archive content)`.

**Graft B (from eligibility-trace):** replace a static corroboration count with
a **time-decayed neg-trace + a separate pos-trace veto**, computed *at read
time* from the already-loaded feedback edges using the existing
`0.5^(age/half_life)` anchor. This kills the "counters never decay /
stale-by-history" hole and the false-neutral case: a memory with a live
`retrieval_used` (positive) trace above a veto floor is excluded from merge
even if occasionally flagged. Promote the trace to **node-local hygiene
columns** (off `MemoryRecord`, off sync, mirroring `last_decayed_at`) *only* if
read-time replay profiles hot; keep edges as source of truth + a
`replay_drift==0` check.

**Graft C (from consolidate audit):** do **not** claim "duplicate → seed
`memory_consolidate`" as a merge guarantee. `memory_consolidate` is
content-Jaccard + by_kind only (`:23393`) and never reads feedback. The gate
must only propose a duplicate-merge when the pair **also** passes the existing
Jaccard/min_similarity + same-kind test; otherwise surface
`feedback-says-duplicate-but-content-not-similar` as a **held/blocker** status
rather than forcing a merge. Keep `Missing` as a corpus-gap counter.

## 5. Data model (deliberately schema-light)

- **No** new `MemoryRecord`/`MemoryEdge`/`memory_edges`/status-enum change.
- Queue schema string bumps `agent_bridge.memory_consolidation_queue.v0 → .v1`
  (additive `gated_action` field, forward-compatible).
- New gate schema consts (pinned like `BIOCORTEX_RETRIEVAL_OPT_IN_*` for replay
  cross-check): `…outcome_gated_consolidation.{status,transition_gate,
  apply_trial,approval_packet}.v1`.
- Corroboration computed at read time: group `feedback→target` edges by
  `retrieval_source` tag for distinct-source counting.
- **Optional** apply ledger: one `kind=audit` `MemoryRecord` per execution
  tagged `outcome_gated_apply:<verb>`, `related_keys=[target,winner]` — apply
  history is queryable/syncable via the existing substrate (NewerWins), **no
  DDL**.
- Migration idiom (when columns *are* eventually needed): string `schema_meta`
  gate `cur.as_str()=="36"` + idempotent `pragma_table_info('memories')`
  presence check + backfill, mirroring the V33 `last_decayed_at` block
  (`sqlite.rs:1356-1395`). Latest applied = **V36** (`:1448-1480`) → next is
  **V37**. (The runner uses `schema_meta` string compare, *not* the
  `user_version` PRAGMA.)

## 6. Control flow

1. **Feedback arrives** — `memory_retrieval_feedback` unchanged (append-only,
   write-once). No new write at feedback time.
2. **Gate evaluates** (on demand: `session_finalize`, or explicit `status`
   call) — v1 queue recomputes buckets, attaches `gated_action` +
   `candidate_blockers`; `status.evaluate()` collapses
   `{flags, quorum/trace, durable-guard, packet-freshness}` into
   `may_apply` + ordered blockers (earliest root-cause wins, `BTreeSet`).
3. **Consolidation applies** — only inside `session_finalize`, only when
   `apply_outcome_gated=true` + valid unexpired `approval_packet` +
   `dry_run=false` + `may_apply==true` + diff-hash still matches. Dispatches
   each action to an existing primitive, capped per pass, emits a Verified
   SemanticEvent. Any drift / stale packet / new blocker → **fail-closed
   abort** → read-only hint.

## 7. Staged rollout (mirrors the house ladder)

- **Stage 0 — Shadow (ships first, no flag):** extend
  `memory_consolidation_queue_from_records` to compute the `gated_action` per
  candidate. `read_only=true`, schema `v0→v1`. Pure fn, no writes. **Ship Fix A
  (durable-guard narrowing) in this same PR**, behind a SQL change + dry-run
  eligibility readback. *(~1 day + the guard fix.)*
- **Stage 1 — Status gate (read-only) — LANDED 2026-06-28:**
  `outcome_gated_consolidation_status`, a pure
  `outcome_gated_consolidation_status_eval()` (mirrors
  `BioCortexRetrievalOptInRequest::evaluate`, `lib.rs:353`, and
  `trigger_recall_opt_in_status`) over the Stage-0 `gated_actions` shadow →
  `boundary_check.may_apply` + ordered gate blockers `[feature_runtime_disabled,
  operator_disabled, per_call_opt_in_missing, no_shadow_eligible_candidates]`
  (most-fundamental first; the leading entry is the next thing to fix).
  **Refinement vs. the original sketch:** the *per-candidate* eligibility
  blockers (`QuorumNotMet`, `SingleSourceOnly`, `DurableGuardWouldArchiveHub`,
  `ContentMergeUnverified`) stay on each `gated_action` (Stage 0) and are
  surfaced here as a `candidates.candidate_blocker_counts` histogram; the gate
  collapses them into the single "≥1 `shadow_eligible` candidate?" check, so
  `FeatureDisabled`/`RuntimeDisabled` also merge into one
  `feature_runtime_disabled` (the env flag *is* the runtime feature).
  `QueuePacketStale` is deferred to the Stage 2 transition gate that consumes a
  status packet. `side_effects` mutation inventory is all-false; a separate
  `data_access` block honestly marks the read-only row/edge reads. Default-OFF
  behind `AB_OUTCOME_GATED_CONSOLIDATION` (+ operator kill
  `AB_OUTCOME_GATED_CONSOLIDATION_DISABLE`); registered at `Tier::Niche` with
  the other gate-ceremony tools. `may_apply=true` authorizes *only* a later
  Stage 2 transition-gate request — no verb is ever applied by this surface.
- **Stage 2 — Transition gate (supervisor cross-check) — LANDED 2026-06-28:**
  `outcome_gated_consolidation_transition_gate` consumes a Stage 1 `status`
  packet + a *re-asserted* transition request and reports
  `boundary_check.runtime_transition_allowed` → whether a later Stage 3 dry-run
  apply trial may be requested. Pure
  `outcome_gated_consolidation_transition_gate_eval()` validates: `schema ==
  v1`, `read_only`, **no raw payload** (`outcome_gated_packet_contains_raw`
  rejects `content`/`target_key`/`gated_actions`/`buckets`/… both *inside* the
  packet **and** in the *outer* `args` beside it — `execute()` strips the known
  wrapper fields then scans the remainder, so a raw field cannot bypass the
  contract by sitting next to `status_packet`; the gate must never become a
  content side-channel), packet `side_effects`
  all-false **AND** `data_access.mutates_state==false` (a packet missing those
  **fails closed**), `boundary_check.may_apply==true`, then **re-checks**
  runtime/operator/per-call independently of the packet (a stale "ready" packet
  cannot smuggle a transition through) and `regression_anchor ==
  OUTCOME_GATED_CONSOLIDATION_ANCHOR`
  (`outcome_gated_consolidation_stage2_transition_readonly_20260628`). Any
  residual packet blockers are folded in as `status_<blocker>`. Records
  presence-only `{reviewer, commit, forum_post_id, memory_key}`; **never echoes
  the packet**. `transition_allowed=true` sets `may_call_apply_trial=true` but
  `may_apply_now=false` + `apply_trial_dry_run_forced=true` — it only unlocks
  the next read-only surface. Registered `Tier::Niche`; default-OFF behind
  `AB_OUTCOME_GATED_CONSOLIDATION`. Zero writes. Models
  `trigger_recall_opt_in_runtime_transition_gate` (`:545`).
- **Stage 3 — Gated dry-run apply trial — LANDED 2026-06-28:**
  `outcome_gated_consolidation_apply_trial` **re-asserts the runtime/operator/
  per-call gate at the trial layer** (default-OFF `AB_OUTCOME_GATED_CONSOLIDATION`
  — a previously-allowed/crafted transition packet cannot leak a key-level plan
  while the feature is disabled; `blocked_by_runtime_gate`) **and** validates a
  Stage 2 transition-gate packet — schema/read_only/side_effects/raw plus its
  **own internal consistency** (`transition.may_call_apply_trial==true`,
  `apply_trial_dry_run_forced==true`, `may_apply_now==false`; a self-
  contradictory packet fails closed). Only if **both** gates pass does it plan
  the exact mutation each shadow-eligible candidate would receive. `dry_run` is
  **hard-forced true** — it reads memory and recomputes the shadow but writes
  nothing. Per
  verb: `archive_direct` → `accepted` `{op: archive_status, → archived}`;
  `archive_via_consolidate` → reuses the **same** consolidate winner logic
  (`outcome_gated_consolidate_rank = importance*(1+access_count)`, jaccard ≥
  `min_similarity` (default 0.45), same-kind — kept in sync with
  `MemoryConsolidateTool`) to emit `accepted` `{op: memory_consolidate, winner,
  loser, supersedes_edge winner→loser}` when the target is the loser, else
  `held(target_is_consolidate_winner)` (never archive a winner) or
  `held(no_consolidate_partner_above_threshold)` when content can't confirm the
  feedback-named duplicate; `queue_rewrite` →
  `held(rewrite_is_content_decision_not_auto_applied)` (too_large never
  auto-archives). Each plan entry is `accepted|held(reason)`; summary rolls up
  accepted/held + `hold_reasons` histogram. A blocked/invalid transition packet
  ⇒ `status=blocked_by_transition_gate` + empty plan. Outer-args raw-payload
  defense as in Stage 2. `side_effects` all-false; registered `Tier::Niche`;
  default-OFF behind `AB_OUTCOME_GATED_CONSOLIDATION`. Models
  `trigger_recall_opt_in_gated_baseline_trial`.
- **Stage 4 — Approval packet (owner sign-off) — LANDED 2026-06-28:**
  `outcome_gated_consolidation_approval_packet` validates a Stage 3 apply-trial
  packet (schema/read_only/`dry_run_forced`/`status==trial_complete`/side_effects/
  raw + the trial's own `runtime_gate.accepted` & `transition_gate_check.accepted`
  + `accepted_actions>0`), **re-asserts the runtime gate + anchor**, and
  **REQUIRES all four owner refs** (`reviewer`/`commit`/`forum_post_id`/
  `memory_key` — vs. presence-only optional at Stages 2-3). Only if all pass does
  it freeze a **volatile-field-free canonical diff** (plan target/verb/decision/
  hold_reason/planned_mutation + `min_similarity`, excluding `generated_at`)
  under `diff_hash = memory_biocortex_sha256_json(canonical)` and issue
  `apply_token = sha256({diff_hash, reviewer, commit, forum_post_id, memory_key,
  anchor})` (raw refs hashed in, never echoed). `accepted_targets` surfaces the
  approved {target,verb}. Blocked ⇒ `diff_hash`/`apply_token` null. Pure fn (no
  store); `may_apply_now=false`, `next_allowed_surface=session_finalize(...)`.
  `execution_contract` declares the Stage 5 obligation:
  `valid_only_if_diff_hash_matches_live_recompute` + `apply_token_single_use`.
  Registered `Tier::Niche`; default-OFF. Models the house `*_approval_packet` /
  `enforce_hold_approval_packet` tools.
- **Stage 5 — Gated WRITE executor — LANDED 2026-06-28:** the first and only
  stage that mutates memory. Shipped first as a **dedicated tool**
  `outcome_gated_consolidation_apply` (also reachable via `session_finalize`,
  Stage 5b below) to keep the first write path on-demand, isolated, and fully
  testable rather than embedded in the Stop-hook pipeline. It writes ONLY when
  **four independent gates** all hold: (1) runtime env on + operator not
  disabled + `per_call_opt_in` + anchor matches; (2) the Stage 4 approval packet
  is schema-valid + `status==approved` and its `apply_token` is **reproduced**
  from the re-supplied owner refs (`sha256({frozen_diff_hash, reviewer, commit,
  forum_post_id, memory_key, anchor})`); (3) a **LIVE recompute** of the plan
  (`outcome_gated_recompute_plan` → same Stage 3 planner + Stage 4 canonical
  projection) still hashes to the frozen `diff_hash` — the staleness defense;
  and (4) `confirm_apply==true`. Any failure ⇒ a no-write **verified preview**
  (`verified_preview_awaiting_confirm` / `blocked_by_runtime_gate` /
  `blocked_invalid_approval` / `blocked_diff_hash_stale`). Applies accepted
  actions via existing primitives — `archive_status` (status→archived) and
  `memory_consolidate` (archive loser + `memory_link` supersedes winner→loser) —
  capped at `max_apply_per_pass`; gates 1+2 are checked **before any store
  read/write**. Returns a `finalize_readback` with `archived_memories` /
  `supersedes_edges_written` / `verified`. Registered `Tier::Niche`; default-OFF.
  Scoping args must match the trial (enforced by the diff_hash check).
  - **Stage 5b — `session_finalize` delegation — LANDED 2026-06-28:**
    `apply_outcome_gated: bool = false` + `approval_packet` (and forwarded owner
    refs / scoping args) wired into `session_finalize`. Default false ⇒ **zero
    behavior change**: the gated path is not invoked and the response is
    byte-identical except for one added read-only `follow_up.outcome_gated_apply`
    pointer (non-null only when the existing `suggest_memory_consolidate` nudge
    fires). When `true`, `session_finalize` adds **nothing of its own** — it
    forwards args to the same `outcome_gated_consolidation_apply` executor, which
    independently enforces all four gates; the full executor result is returned
    under `outcome_gated_consolidation`. A `dry_run` finalize **forces the
    sub-call to preview** (`confirm_apply→false`), so `session_finalize(dry_run)`
    can never mutate memory. The delegation runs **before** this call's own
    decay/compact maintenance, so finalize's own importance-decay (which feeds the
    consolidate rank) and compaction can never self-invalidate a just-approved
    plan within the same call — external drift since approval is still caught by
    the executor's live `diff_hash` gate. The two `session_lifecycle_step`
    forward-allowlists (the Stop-hook path) deliberately **exclude**
    `apply_outcome_gated`, so the gated WRITE is reachable only via an explicit
    human `session_finalize` call. Covered by 6 store-backed tests (schema/opt-in,
    default-off omits the block + no writes, delegates+applies when fully gated,
    in-band apply succeeds without `skip_decay`, dry-run forces preview, env-off
    blocks). Two adversarial workflows (4-lens refutation + 6-hypothesis
    prove-or-disprove panel) found **0 unsafe behaviors**; the ordering refinement
    above came out of the hypothesis panel.

## 8. Noise / poison-feedback safety (defense in depth)

1. **Corroboration quorum** — `≥2 distinct feedback rows from ≥2 distinct
   `retrieval_source` values` with the same negative outcome, OR 1 row from a
   trusted-source allowlist; single-source and self-feedback (author==target
   author within grace) never reach `may_apply`.
2. **Decayed neg-trace + pos-trace veto** (Graft B) — a live positive trace
   vetoes archival of a still-used memory.
3. **Narrowed durable guard** (Fix A) — still protects `relates|supersedes|
   corrects|caused_by` hubs and author-linked (`related_keys`) rows; surfaces
   `DurableGuardWouldArchiveHub` as a blocker rather than silently dropping.
4. **Per-pass cap** (`max_apply_per_pass`, default ~5) — bounds blast radius,
   forces multiple reviews for a large sweep.
5. **Verb asymmetry** — `stale|duplicate → archived+supersedes (reversible via
   `memory_restore_archived`)`; `harmful → archive (never tombstone/delete)`;
   `too_large → rewrite-queue only` (shrinking content is a content decision,
   not a lifecycle one).
6. **Diff-hash freeze** — any feedback/memory write between approval and
   execution mismatches the hash → fail closed.
7. **Grace period (3600s)** — protects freshly-saved targets from same-session
   feedback storms.
8. **Reversibility** — every applied action is soft/recoverable (archived/
   superseded, NewerWins-syncable); a bad apply is undoable and logged as a
   lesson (satisfies the reversible-autonomy discipline).

## 9. MCP surface

- **CHANGED** `memory_consolidation_queue` — `v0→v1`, candidates gain
  `gated_action`. Still `read_only=true`.
- **NEW** `outcome_gated_consolidation_status` — read-only `evaluate()`.
- **NEW** `outcome_gated_consolidation_transition_gate` — supervisor cross-check.
- **NEW** `outcome_gated_consolidation_apply_trial` — dry-run-forced diff.
- **NEW** `outcome_gated_consolidation_approval_packet` — sha256 diff freeze.
- **CHANGED** `session_finalize` — `apply_outcome_gated:bool=false` +
  `approval_packet`. Default ⇒ read-only hint only.
- **No new store-trait method required** — apply dispatches to existing
  `memory_decay_importance` / `memory_compact` / the `memory_consolidate`
  executor (`mcp_tools.rs:23490`, factor into a shared helper).

## 10. Open questions

1. **Source trust** — the `retrieval_source` allowlist is only 4 values
   (`memory_search|memory_get|session_bootstrap|manual`, `:21515`) and defaults
   to `manual`, so a single agent can satisfy a naive 2-source quorum. Need a
   distinct-EVENT-over-time-window brake and/or a real per-source trust signal
   before auto-apply is enabled.
2. **Trace: read-time replay vs persisted columns** — start read-time
   (`O(edges)` per queue call, zero DDL); promote to node-local columns only if
   profiling shows it hot, then add the `replay_drift==0` check.
3. **Blast-radius inventory** — after Fix A narrows the guard, run a one-time
   dry-run: count active rows whose ONLY edges are `retrieval_*` (these flip
   from durable→eligible) to confirm no genuine hubs are caught.
4. **Cross-kind duplicates** — `memory_consolidate` groups strictly by_kind;
   the gate must make explicit that a feedback-named duplicate spanning kinds
   is *not* merge-eligible (current code never pairs them).
5. **`Ignored` (weight 0.6)** — weak negative; advisory-only, or a small
   decay-pressure increment to the neg-trace?
6. **Eval metric** — the ladder requires an anchored regression eval
   (`false_archive_rate` / over-merge) and a labeled corpus before flipping the
   runtime flag; how is the ground-truth label set produced?

## 11. Effort & sequencing

~one focused week incl. tests + shadow burn-in:
- Stage 0 + **Fix A**: ~1–1.5 days (pure-fn enrichment + guard SQL narrowing +
  dry-run readback). **Highest-value, ship first.**
- Stages 1–4: ~2–3 days (near-mechanical copies of the
  `trigger_recall_opt_in_*` + `BioCortexRetrievalOptInRequest` patterns).
- Stage 5: ~1–2 days (bounded `session_finalize` edit, reuse Verified
  SemanticEvent).

No new migration, no new mutator; the riskiest logic (archival safety) stays in
already-hardened, now-corrected durable-guard code.

---
*Authored from the `w3-consolidation-design` workflow (4 grounding readers + a
3-approach judge panel). Tracking: plan `ab-parent-dir-leads-landing` (w3).*
