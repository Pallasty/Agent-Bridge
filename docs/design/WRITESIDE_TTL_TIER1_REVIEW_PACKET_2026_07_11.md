# Review Package — Write-side Audit-Row TTL Governance (Tier 1)

**Prepared:** 2026-07-11 · biocortex-rs session, read-only inspection of the AB worktree
**For:** owner / AB-code landing session
**Decision requested:** review → adopt/reject the Tier 1 diff; if adopt, rebuild on merged master + re-verify + deploy (all touch the shared AB substrate → owner sign-off).

---

## 1. TL;DR

A 68-line, additive-only diff that stops **rollback-map audit rows** (bounded-life operator plumbing) from flooding top-k on `valence`/`retrieval` queries. It tags those rows `ttl:14d` at both emit sites and adds a **kind-agnostic read-time TTL suppression** on the general `memory_search` path so any `ttl:Nd` row past its window drops out of results. Untagged rows (>99% of the store) are byte-identical.

**State:** uncommitted working-tree edits on branch `claude/writeside-audit-ttl-20260711`, **never committed, not merged, not deployed.** Prior `cargo check` passed on the branch base — but that base is now **11 commits behind master**, so a re-verify on merged master is mandatory before landing.

**Verdict from this inspection:** the change is clean, well-scoped, and correctly diagnoses the root cause. Two honest caveats the reviewer must weigh (§5): the blast radius is slightly **wider** than the originating memory row stated, and the diff needs a rebase + re-verify (low textual-conflict risk, one semantic-interaction check).

---

## 2. Why this exists (provenance chain)

1. `dpp_memory_headroom_recon_verdict_20260711` — DPP recon found real top-k redundancy but ruled DPP the wrong tool; root cause is **write-side**, near-exact-duplicate template rows.
2. `writeside_consolidation_audit_rollback_map_gap_20260711` (档 A audit, `needs_review`) — measured that `outcome_valence_importance_apply_*` / `retrieval_outcome_apply` rollback-map rows are **TTL/log-class** (durable value low, regenerated every apply pass) yet were written into **durable semantic memory**, so they multiply and pollute top-k. `memory_consolidation_queue`'s dedup bucket only inspects `lessons`, so these sat invisible to shadow surfacing.
3. **Tier 1 (this diff)** = the "真修·写入侧" tier: give the rows a TTL tag + make retrieval honor it. (Tier 2 = a non-lesson duplicate-family bucket in `consolidation_queue`; Tier 3 = a one-shot `memory_consolidate(kind=observation)` band-aid. Both still open, no diff.)

---

## 3. What changed (5 blocks, file:line on the branch)

| # | File · anchor | Change |
|---|---|---|
| 1 | `mcp_tools.rs` · `MemorySearchTool` after the `exclude_kinds` retain (~L13171) | **New read-time filter**: `let now = unix_now_secs(); hits.retain(|h| record_ttl_is_live(&h.record, now));` |
| 2 | `mcp_tools.rs` · new fn after `work_memory_is_live` (~L13837) | **`record_ttl_is_live(record, now)`** — kind-agnostic; reuses `work_memory_expires_at`; returns `true` for rows with no `ttl:` tag |
| 3 | `mcp_tools.rs` · `OutcomeValenceImportanceApplyTool` tags (~L23775) | Adds `"ttl:14d"` to the rollback-map audit row |
| 4 | `retrieval_outcome.rs` · `run_apply_pass` tags (~L359) | Adds `"ttl:14d"` to the rollback-map audit row |
| 5 | `mcp_tools/tests.rs` (~L1275) | Unit test `record_ttl_is_live_suppresses_expired_rollback_map_audit_rows` — expired→suppressed / in-window→live / untagged→live |

**Design insight that determined the diff shape (verify-first):** `ttl:Nd` expiry was previously enforced **only in the work_memory read path** (`work_memory_is_live`, used at `mcp_tools.rs:14005/14196/14457/14478/14526`). Tagging a row alone was therefore inert on the general search path — block #1 is the piece that makes the tag actually do anything. The parser `work_memory_expires_at` (anchor = `updated_at.max(created_at) + N days`) is shared, so work_memory keeps identical semantics; block #2 only extends the same rule to other tagged rows.

---

## 4. Verification status

| Item | Status |
|---|---|
| **Re-verify on MERGED MASTER `c72bfa16` (branch HEAD `dc5ae095`)** | ✅ `cargo test -p ab-bridge --lib` compiles lib+tests clean, **2m46s** (`$HOME` warm target, `-j2`, debug) — 2026-07-11, this session |
| New unit test `record_ttl_is_live_suppresses_expired_rollback_map_audit_rows` | ✅ **ok** (`1 passed; 0 failed; 1539 filtered out`) |
| New warnings from this diff | **0** (`record_ttl_is_live` is live via the search retain) |
| Pre-existing warnings | 1 (`ToolPolicy` more-private-than-`build_registry_with_policy`, `mcp_tools.rs:38335/41444` — not this diff) |
| **Full `ab-bridge` lib suite** | ✅ **1536 passed / 0 failed / 4 ignored**, 18.23s (2026-07-11, merged master) — no regressions |
| Superseded | the stale base-`789866a5` `cargo check` recorded in `writeside_ttl_tier1_diff_verified_20260711` |

---

## 5. Reviewer scrutiny points (honest risk list)

**R1 — Blast radius is wider than "rollback-map rows only" (must decide, not a blocker).**
The originating memory row framed scope as "work_memory + these audit rows." In fact block #1 suppresses **every** `ttl:Nd`-tagged row past its window from the general `memory_search` path. Today that population is:
- **work_memory rows** — carry `ttl:14d`/`ttl:{N}d` (emit site `mcp_tools.rs:14402`). Confirmed live examples exist (2× `ttl:14d` portfolio rows). Before this diff, an *expired* work_memory row could still surface via general search (liveness was only checked in the dedicated work_memory list paths); after, it can't. This is a **consistency change** (arguably a latent-leak fix), not the stated target.
- **`auto_curated` / `alert` rows tagged `ttl:7d`** — `ttl:7d` is a pervasive curation/orphan skip-tag family (defaults at `mcp_tools.rs:28243/28303/…`, `palace_viewer.rs:323`). Any such rows past 7d now also drop from general search.
- The intended **rollback-map audit rows** (once deployed).

→ **Decision for the reviewer:** confirm that suppressing expired work_memory + alert rows from general search is intended (plausibly a consistency win) rather than an accidental side effect. If it should be scoped to rollback-map only, block #1 needs a kind/tag guard.

**R2 — Wall-clock enters the general retrieval path.** Block #1 calls `unix_now_secs()` once per search + an O(N) retain over hits. Not new nondeterminism (AB ranking already uses recency), perf negligible. Confirm acceptable.

**R3 — Double-filtering with `work_memory_is_live`. → VERIFIED consistent.** Both helpers share the `work_memory_expires_at` parser and use identical `expires_at > now` logic. The only difference: `work_memory_is_live` also gates on `status == "active"`, which `record_ttl_is_live` omits — correctly, because the `memory_search` pipeline already excludes archived/superseded rows upstream, so the retain only needs the TTL discriminator. Idempotent and non-divergent as written. (Residual: if a future change makes the two TTL bodies drift, extract a shared helper — noted, not a blocker.)

**R4 — 14d window vs rollback correctness.** Rows inside the window are retained (rollback stays correct); past it they're suppressed from *retrieval* but not deleted until `memory_compact`. Confirm 14d ≥ the real rollback-map useful life.

**R5 — Per-pass scope.** Both emit sites use a DISTINCT per-pass scope for successive audit maps (comment preserved), so tagging doesn't collide/overwrite across passes. Verified in-diff.

---

## 6. Rebase / re-verify — DONE (2026-07-11, this session)

The rebase predicted below was **executed and landed clean.** The branch `claude/writeside-audit-ttl-20260711` was committed (`da615441`) and rebased onto master `c72bfa16` → new HEAD `dc5ae095`, base now = master. `git rebase` exit 0, **zero conflicts**. Post-rebase diff is byte-intact: 3 files / 68 insertions / all 5 blocks present. Re-verify (`cargo test -p ab-bridge --lib`, warm `$HOME` target, `-j2`): **see §4** (this replaces the stale base-`789866a5` check).

Original prediction (now confirmed) — branch base `789866a5` was **11 commits behind** master; master touched `mcp_tools.rs` (+386) and `tests.rs` (+445), `retrieval_outcome.rs` untouched.

**Textual conflict risk was LOW and materialized as zero.** All three re-anchor points exist **exactly once** in master's `mcp_tools.rs`, no symbol collision:

| Anchor | branch line | master line | occurrences in master |
|---|---|---|---|
| `hits.retain(|h| !exclude_kinds…` | 13171 | 13344 | 1 |
| `fn work_memory_is_live` → `fn stable_fnv1a_hex` (insert between) | 13828→13847 | 13996→14003 | 1 each, adjacent |
| `OutcomeValenceImportanceApplyTool` `"rollback_map".to_string()` | 23775 | 23946 | 1 |
| `record_ttl_is_live` (collision check) | — | — | **absent** (no collision) |

master's churn is elsewhere in the file → a 3-way/fuzzy rebase should be near-mechanical (line-number shift only). `retrieval_outcome.rs` hunk applies clean.

**One semantic-interaction check (not textual):** master commit `9efe4317 fix(memory): isolate scoped recall and retain curation lineage` altered recall/curation in the same file. Confirm the new `hits.retain` composes correctly with any scoped-recall isolation added there (retain ordering, whether `hits` shape changed).

---

## 7. Landing path (if adopted)

1. Rebuild the 3 hunks on **merged master** (per `pub_deploy_binary_from_merged_master`) — resolve the line-shift drift; re-check R6 semantic composition.
2. `cargo check -p ab-bridge --tests` + run the new unit test + the full memory test suite (`$HOME` target, `-j2`; never tmpfs, never release).
3. Deploy binary from merged master — **push allowed, CI forbidden** (`agent_bridge_push_allowed_ci_forbidden_20260710`); wrapper untouched, `.real` atomic-replace (`lesson_macos_atomic_deploy_running_binary_20260530`).
4. Post-deploy: already-expired rollback-map rows begin dropping from retrieval immediately; `memory_compact` retires them from storage. (None are tagged yet — the tag only starts applying to rows written after deploy, plus any backfill the reviewer chooses to run.)

## 8. Rollback

Additive, tags-only + a read-time filter — no schema/data migration. Revert = drop the 3 hunks. Rows already written with `ttl:14d` stay harmless (an untagged store simply never suppresses them). Reversible at every step.

---

## Appendix — full diff

Patch saved at `scratchpad/tier1_writeside_ttl.patch` (regenerated from the worktree working tree; the original prior-session patch file was lost to scratchpad cleanup, but the edits survive on the branch).

```
crates/bridge/src/mcp_tools.rs         | 28 ++++++++++++++++++++++++++++
crates/bridge/src/mcp_tools/tests.rs   | 33 +++++++++++++++++++++++++++++++++
crates/bridge/src/retrieval_outcome.rs |  7 +++++++
3 files changed, 68 insertions(+)
```
