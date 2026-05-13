# DESIGN — P-ε: Substrate-Readiness Audit Tool

**Status**: design draft 2026-05-13. **No code until this memo is solid.**
**Source**: `verify_memory_layers_vs_seed_l1l2l3_20260513` memo, proposal P-ε
**Sibling**: `DESIGN-v22-agent-bridge-memory-substrate.md` (substrate body); P-ε is the pre-substrate baseline tool, complementary not overlapping.
**Workflow**: verify-design-act (per `feedback_verify_design_act_workflow`). This memo IS the 设计 phase; 行动 starts only after Gate (§10) passes.

---

## 0 · Why this exists (verify-phase output recap)

The verify memo found 5 architectural gaps (G1-G5) vs the Seed L1/L2/L3 model. P-ε is the **cheapest** of 5 falsifiable proposals — pure read-only MCP tool that **reports** the gap state continuously, without touching it.

**P-ε's specific job**: make substrate-relevant L1+L2 metrics first-class so:
1. Before v22 substrate ships: every "before" baseline number exists in writing.
2. After v22 substrate ships: same query gives "after" delta. Falsifiable.
3. If v22 substrate is delayed (Gate B blocked by Mac SSH availability): P-ε keeps the data accumulating — null-result rule on P-α/P-β/P-γ becomes testable.

P-ε is the **observability primitive** that the other 4 proposals (P-α/β/γ/δ) lean on for falsifiability. Ship-order is P-ε first.

---

## 1 · Goals (in scope)

| # | Goal | Acceptance test |
|---|---|---|
| G1 | A single MCP tool `memory_substrate_audit` returns 7 metric families in one JSON document | Tool returns valid JSON; all 7 sections populated on a non-empty DB |
| G2 | CLI mirror `dream substrate-audit [--json] [--window-days N]` | Same 7 sections; pretty-text default, JSON optional |
| G3 | Zero new SQL tables / zero new write paths | `git diff` on impl PR shows no `CREATE TABLE` / no `INSERT/UPDATE/DELETE` |
| G4 | All 7 metrics computed in < 200 ms on current store (DB 1.13 GB, 2090 rows) | Wall-clock measured during impl; if >200ms, page off slow metrics or add LIMIT clauses |
| G5 | `dream weekly` composite gains one substrate-readiness line | `dream weekly` text output shows `substrate: N components / X edges/active / +Y% growth` |
| G6 | Tool is idempotent + safe to call from any Hot tier event | Same DB state → same output; no side effects observable in `memory_query_log` |
| G7 | Falsifiable predictions matrix (P1-P3 in §7) is evaluable after 4 weekly runs | Each P has explicit threshold + null-rule; reviewer can verdict after 28 days |

## 2 · Non-goals (out of scope)

- ✗ Building substrate itself — that's v22.
- ✗ Auto-act on metrics (no automatic promote/decay triggered by audit thresholds).
- ✗ New schema / new tables / new event types.
- ✗ LLM calls.
- ✗ Re-implementing existing dream subcommand internals — P-ε **calls** `hebbian_clusters` / `signal_fidelity_stats` / `memory_stats` / `memory_query_stats` etc., never duplicates their SQL.
- ✗ Disk/RAM telemetry (those are `du` and `top`, not in audit scope).

---

## 3 · Architecture

### 3.1 Surface

```
MCP tool: memory_substrate_audit(window_secs?: u64)
         → JSON: 7 sections, all populated
CLI:     dream substrate-audit [--json] [--window-days N=7]
         → same 7 sections; text mode is the default for terminal use
```

`window_secs` / `--window-days` controls the lookback window for growth-rate / signal-fidelity / query-stats sub-metrics. Default 7d (matches `memory_query_stats` default). Counts that don't need a window (component count, status distribution, edge_count) are window-independent.

### 3.2 Internal call graph (no new code, only orchestration)

```
memory_substrate_audit
  ├── store::hebbian_clusters(min_size=2)            (P-ε:M1 component count)
  ├── store::memory_stats()                          (P-ε:M2,M4,M5 — edge_count, status dist)
  ├── store::memory_query_stats(window_secs)         (P-ε:M3 query rate, retrieval health)
  ├── raw SQL on memory_coactivation                 (P-ε:M2,M6 coact size + 7d delta)
  ├── store::signal_fidelity_stats(top_n=0)          (P-ε:M7 — Spearman; top_n=0 = no misrank rows)
  └── raw SQL on memories.embedding_backend          (P-ε:M8 — onnx/hash/unknown split)
```

All trait methods exist today. P-ε is **pure composition** of existing reads.

---

## 4 · The 7 metric families (each with SQL/source + null-rule + interpretation)

### M1 — Substrate-component count

**Source**: `store::hebbian_clusters(min_size=2)` (same call backing `dream cluster-probe`)
**Output**: `{ components: N, total_clustered_nodes: M, largest_component_size: K, distribution: [size_a, size_b, ...] }`
**Read**: how many independent clusters does the crystallized graph have?
- N=1, K≈M, total_nodes ≈ active count: **hairball regime** (current state per `e5c88fb` cluster-probe wet-run)
- N ≥ 3 with bimodal cross-cluster cos: **substrate emerged**, Multi-Grid Foundations invariant #6
- N ≥ 3 with degenerate sizes (one giant + many singletons): **partially modular** — middle state

**Null-rule**: if 4 weekly runs all show N=1, conclude P-α (always-warm tick) and/or P-γ (perception subscription) is required before further L3 development would help.

### M2 — Edge density per edge_type

**Source**: `store::memory_stats()` (gives total `edge_count`) + raw SQL `SELECT edge_type, COUNT(*) FROM memory_edges GROUP BY edge_type`
**Output**: `{ total_edges: N, per_type: {cofires: X, co_referenced: Y, evolved: Z, ...}, density: edges/active_memories }`
**Read**: which edge classes are accumulating? cofires/co_referenced are L2-crystallized; relates/derived_from are L1-authored.

**Null-rule**: if `cofires + co_referenced < 0.05 * active_memories` after 14 days of ζ-10 cron, conclude promote thresholds are too tight OR substrate signal is too sparse → P-α candidate.

### M3 — Coactivation table growth rate

**Source**: raw SQL on `memory_coactivation`:
```sql
SELECT COUNT(*) FROM memory_coactivation;                              -- total
SELECT COUNT(*) FROM memory_coactivation WHERE last_at >= ?cutoff;     -- recent
SELECT AVG(count) FROM memory_coactivation;                            -- avg intensity
SELECT MAX(count) FROM memory_coactivation;                            -- peak
```
**Output**: `{ total_pairs: N, recent_active: M, avg_count: A, max_count: K, est_daily_new_pairs: D }`
**Read**: is the trace expanding (new co-firings appearing) or saturating (same pairs reinforcing)?

**Null-rule**: if `recent_active / total_pairs < 0.1` for 4 weeks, conclude trace is stale → P-α tick would re-activate.

### M4 — Retire state machine balance

**Source**: `store::memory_stats().counts_by_status` (already returns active/archived/superseded/tombstoned)
**Output**: `{ active: N, archived: M, superseded: S, tombstoned: T, archived_fraction: M/(N+M+S+T), 7d_delta: {...} }`
**Read**: is ζ-10 (decay/archive/tombstone/purge) chain healthy? Steady state: active stable, archived growing slowly, tombstoned cycling (created ↔ purged).

**Null-rule**: if `archived_fraction > 0.7` for 4 weeks AND `tombstoned` not cycling, conclude purge-tombstones isn't running (cron broken) OR ζ-19 archived→tombstoned threshold too tight.

### M5 — Edge coverage of active memories

**Source**: raw SQL:
```sql
SELECT COUNT(DISTINCT key) FROM (
  SELECT from_key AS key FROM memory_edges WHERE edge_type IN ('cofires','co_referenced')
  UNION
  SELECT to_key AS key FROM memory_edges WHERE edge_type IN ('cofires','co_referenced')
) AS touched
WHERE key IN (SELECT key FROM memories WHERE status='active');
```
**Output**: `{ active_with_l2_edge: N, fraction: N/active_total }`
**Read**: what proportion of active memories participate in the substrate-relevant graph?

**Null-rule**: if `fraction < 0.1` after 30 days, conclude L2 crystallization is reaching only a niche of memories → either threshold too tight or substrate signal too sparse.

### M6 — Embedding backend distribution

**Source**: raw SQL `SELECT embedding_backend, COUNT(*) FROM memories WHERE status='active' GROUP BY embedding_backend` (P9/P12 column)
**Output**: `{ onnx: N, hash: M, unknown: K, stale_fraction: (hash+unknown)/total }`
**Read**: is the MiniLM-L6-v2 backend fully covering? Hash fallback rows mean substrate inputs may have degraded representation.

**Null-rule**: if `stale_fraction > 0.1` after `memory_reindex` ran 4× → `memory_reindex` is broken OR ONNX backend hangs → escalate to `feedback_onnx_backend_hangs_without_model`.

### M7 — Signal fidelity (Spearman importance↔access)

**Source**: `store::signal_fidelity_stats(top_n=0)` (existing per `dream signal-fidelity`)
**Output**: `{ r_all: f64, r_touched: f64, n_touched: N, verdict: "noise" | "weak" | "moderate" | "strong" }`
**Read**: does importance score predict access? Hebbian wire-strengthen working as intended?

**Null-rule**: if `r_touched < 0.2` for 4 consecutive weekly runs after reinforce-active step=0.10 deployed → reinforce step too small OR access-bumping pathway leaky → escalate to `project_signal_fidelity_shipped` follow-up.

### M8 — Query-side health (existing memory_query_stats wrapped)

**Source**: `store::memory_query_stats(window_secs)`
**Output**: `{ hit_rate: f64, p50_us: u64, p95_us: u64, total_queries: N, avg_top_hit_age_days: f64, by_kind: [...] }`
**Read**: is retrieval doing its job? P-ε surfaces this alongside L2 metrics so reviewer can spot retrieval/substrate decoupling.

**Null-rule**: if `hit_rate < 0.5` for 4 weeks AND M5 fraction > 0.5, conclude L2 edges are being formed but not consulted by search → reinforces need for P-β (recall-bias path).

---

## 5 · Output JSON shape (concrete schema)

```json
{
  "version": 1,
  "generated_at": "2026-05-13T12:34:56Z",
  "window_secs": 604800,
  "m1_components": {
    "min_size": 2,
    "components": 1,
    "total_clustered_nodes": 28,
    "largest_size": 28,
    "distribution": [28]
  },
  "m2_edges": {
    "total": 482,
    "per_type": {"cofires": 17, "co_referenced": 26, "relates": 280, "derived_from": 80, "evolved": 79},
    "density_per_active": 0.731
  },
  "m3_coactivation": {
    "total_pairs": 305,
    "recent_active": 60,
    "avg_count": 2.4,
    "max_count": 18,
    "est_daily_new_pairs": 8.5
  },
  "m4_retire": {
    "active": 659,
    "archived": 1211,
    "superseded": 29,
    "tombstoned": 191,
    "archived_fraction": 0.579,
    "delta_7d": {"active": -8, "archived": +12, "tombstoned": -3, "superseded": +1}
  },
  "m5_edge_coverage": {
    "active_with_l2_edge": 43,
    "active_total": 659,
    "fraction": 0.065
  },
  "m6_embedding": {
    "onnx": 657,
    "hash": 0,
    "unknown": 2,
    "stale_fraction": 0.003
  },
  "m7_signal_fidelity": {
    "r_all": 0.357,
    "r_touched": 0.394,
    "n_touched": 92,
    "verdict": "moderate"
  },
  "m8_query": {
    "hit_rate": 0.733,
    "p50_us": 18996,
    "p95_us": 110689,
    "total_queries": 86,
    "avg_top_hit_age_days": 1.59,
    "by_kind": [{"kind": "get", "count": 45}, {"kind": "search_fts", "count": 26}]
  }
}
```

Text mode reuses `dream stats` shape: one line per family with a one-word verdict and the most-important metric inline.

---

## 6 · `delta_7d` semantics (the only non-trivial computation)

The `_7d` fields require **either**:
- (a) Read a `dream snapshot` from 7 days ago (kind=snapshot, tag=daily) and diff against now, OR
- (b) Compute deltas from creation/update timestamps in current rows.

Choice: **(a) when daily snapshot exists, otherwise (b) as fallback**. This makes P-ε work on fresh DBs (no snapshot history) while leveraging ζ-1 snapshots on mature DBs.

If neither path is feasible (e.g. snapshot exists but schema unrecognized), the field omits with `null` — never invented data.

---

## 7 · Falsifiable predictions (post-ship measurement matrix)

| ID | Prediction | Threshold | Window | Null-result decision |
|---|---|---|---|---|
| P1 | Per-week call rate of `memory_substrate_audit` (via MCP) trends ≥ 5/week within 4 weeks | ≥5 calls / 7d | weeks 1-4 | If <2 calls/week after 4 weeks: tool not surfacing useful info; add to `dream weekly` output if not already; if still low, sunset |
| P2 | M1 component count climbs from 1 to ≥3 within 8 weeks (no substrate yet — purely from natural usage + ζ-10 cron) | components ≥ 3 | weeks 1-8 | If still N=1 at week 8: confirms verify-memo G1 (no always-warm tick) is the binding constraint → P-α should ship next |
| P3 | M5 edge coverage fraction climbs ≥ 0.20 within 12 weeks | fraction ≥ 0.20 | weeks 1-12 | If still <0.10 at week 12: promote thresholds need lowering OR substrate signal too sparse → trigger P-α design |

Each P has an **explicit null-rule decision**. Re-evaluate at week 4 / 8 / 12 mark.

---

## 8 · Multi-Grid 7 invariants cross-check

| Invariant | P-ε posture |
|---|---|
| #1 Parallel uniaxial grids | N/A (P-ε is observability, not a grid) |
| #2 Exchange signals not weights | ✅ output is signal-shape (counts, ratios, fractions) |
| #3 L1/L2/L3 separation | ✅ tool reports cleanly per-layer; doesn't blur boundaries |
| #4 Eager loading | ✅ no lazy load; query-on-demand against eager-loaded SQLite |
| #5 Dormancy = reduced cadence not unload | N/A |
| #6 Bimodal cross-similarity | ✅ M1 distribution exposes if bimodal regime achieved |
| #7 Three-axis decoupling | ✅ M3/M4/M5 split across cadence/state/perception observables |

**All 7 pass or N/A.** No P-ε action violates Multi-Grid Foundations.

---

## 9 · 6 anti-patterns cross-check

1. **Optimizing against unverified targets**: ✅ P-ε IS the verification primitive — every other P uses P-ε numbers as ground truth.
2. **Conflating topology with capacity**: ✅ M1 (topology) and M4 (capacity/status) reported separately.
3. **Mining internal observables for multi-axis**: ✅ P-ε reports observables; doesn't try to invent new axes from them.
4. **Replacing FEP dynamics**: ✅ doesn't touch L2 substrate at all.
5. **Merging carrier weights**: ✅ no merging anywhere; pure read.
6. **Adding Rust complexity without tests**: ✅ implementation will ship with ≥5 unit tests (1 per metric family + 1 for delta_7d fallback + 1 for empty DB) per `feedback_cargo_incremental_stale` lesson.

---

## 10 · 5 preserved properties (must NOT regress)

1. **memory_save / memory_get / memory_search contracts unchanged** — P-ε doesn't touch them.
2. **ζ-10 cron chain stable** — P-ε is invocable from cron but doesn't depend on cron firing.
3. **Palace viewer endpoints unchanged** — P-ε is new MCP tool + new CLI subcommand, no UI touches.
4. **Cross-machine sync semantics** — P-ε is local-only read; per-node values, not synced. (Cross-machine comparison is a separate tool.)
5. **No LLM in any Hot-tier op** — P-ε zero LLM, latency-bounded SQL only.

---

## 11 · Gate (P-ε)

P-ε's Gate is simpler than v22's:

**Gate-ε passes when**:
1. This memo has 7 metric families each with explicit SQL + null-rule (§4) ✅
2. JSON schema is concrete (§5) ✅
3. Falsifiable predictions matrix (§7) has explicit thresholds + null-rule decisions ✅
4. 7-invariant + 6-anti-pattern + 5-preserved-property cross-check (§8-§10) ✅
5. No reviewer blocking objection within 48h

**If Gate-ε passes**: implement (`crates/store/src/lib.rs` trait + `crates/store/src/sqlite.rs` impl + `crates/bridge/src/mcp_tools.rs` MCP tool + `crates/bridge/src/main.rs` CLI + ≥5 tests). Estimate ~3-4h pure impl.

---

## 12 · File map (predictive, not yet existing)

```
crates/store/src/lib.rs                # +SubstrateAuditReport struct + trait method
crates/store/src/sqlite.rs             # +impl method + ≥5 unit tests
crates/bridge/src/mcp_tools.rs         # +memory_substrate_audit tool
crates/bridge/src/main.rs              # +DreamOp::SubstrateAudit + run_dream_substrate_audit
                                       # +"substrate_readiness" line in run_dream_weekly
```

No new file. No new schema. Only existing files extended.

---

## 13 · Vision rule self-check

- ✓ **rule 1 cold-start**: P-ε explicitly designed to give cold-start handoffs a substrate-readiness snapshot to read
- ✓ **rule 2 data-triggered**: prediction matrix (§7) gives null-rule decisions tied to numeric thresholds, not calendars
- ✓ **rule 3 seed unchanged**: zero touch on v0.13.0 path-C / hub_clusters / near_keys
- ✓ **rule 4 reversibility**: P-ε is fully ablate-able by removing the new tool; zero state created
- ✓ **rule 5 identity continuity**: M4 retire-balance + M7 signal-fidelity provide cross-session continuity baselines

---

## 14 · Open questions (defer to impl-time)

1. **Q-ε-1** — `delta_7d` precision: snapshot diff (§6 path a) gives exact deltas but depends on yesterday's snapshot existing. For first 7 days post-ship, path-b fallback is needed. Is path-b's "infer from row timestamps" close enough to ship, or wait for 7d of snapshots to accumulate first?
   - Recommended: ship with path-b fallback marked `(approximate)` in output; switch to path-a (exact) after 7 days.

2. **Q-ε-2** — Should P-ε include a "version drift" indicator (current store schema version vs latest)? Useful in cross-machine sync incidents but tangentially related to substrate.
   - Recommended: defer; add iff a real incident motivates.

3. **Q-ε-3** — Output text-mode color: should we reuse `dream stats` ANSI palette? `dream weekly` doesn't currently use color.
   - Recommended: monochrome text default; JSON for tooling.

4. **Q-ε-4** — Tool cadence: should `memory_substrate_audit` MCP tool be callable from Stop hook for automatic per-session capture?
   - Recommended: out of P-ε scope; if useful, add as a new `sediment` hook in a follow-up.

These resolve at impl time, not now.

---

## 15 · Cost summary

| Phase | Effort | Risk |
|---|---|---|
| Design (this memo) | ~1h ✅ done | ZERO |
| Review (forum reply cycle) | ≤ 48h ⏳ | ZERO |
| Impl + tests | ~3-4h | LOW (only existing reads, no writes) |
| Wet-run validation | ~10 min | ZERO |
| `dream weekly` integration | ~30 min | LOW |
| **Total to ship** | **~5h elapsed + 48h review** | **LOW** |

---

## Appendix A — How P-ε relates to v22 substrate

|  | v22 | P-ε |
|---|---|---|
| Builds substrate | yes | no |
| Observes substrate | yes (G3 active_neighbors) | yes (M1-M8) |
| Requires Seed crate dep | yes (Gate B blocker) | no |
| Ship today possible | no (Mac SSH gate) | yes |
| Useful before substrate | n/a | yes (baseline) |
| Useful after substrate | yes (substrate API) | yes (now reports L2 substrate health alongside L1) |

P-ε is **strict observability complement** to v22. P-ε ships first → baseline data accumulates → v22's "before vs after" delta becomes falsifiable.

## Appendix B — Why ship P-ε before v22 implementation

1. v22 acceptance tests (G1 ≥200 step rows, G7 ≤500MB disk, G8 three-axis decoupling) all need *baseline* numbers to compare against. P-ε produces them.
2. v22 Gate B is blocked on Mac SSH availability per thread #6 post 57. P-ε has no such block.
3. v22 phase 1 is `SeedBackend impl EmbeddingBackend` (one trait method). P-ε produces continuous coverage of what that backend would replace.
4. If v22 phase 1 is delayed indefinitely, P-ε still provides standalone hygiene value (substrate-relevant metrics surfaced in `dream weekly`).
5. P-ε implementation reuses 4 existing trait methods + 2 raw SQL queries — implementation cost is the lowest in the entire 5-proposal stack.

---

**Memo complete. Awaiting Gate-ε review (forum design board thread #6).**
