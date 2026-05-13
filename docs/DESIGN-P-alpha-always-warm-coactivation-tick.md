# DESIGN — P-α: Always-Warm Coactivation Tick (Warm tier @ 30s)

**Status**: design draft 2026-05-13. **No code until this memo is solid.**
**Source**: `verify_memory_layers_vs_seed_l1l2l3_20260513` memo, proposal P-α
**Predecessor**: `DESIGN-P-epsilon-substrate-readiness-audit.md` — P-ε ships first as observability primitive; P-α uses P-ε metrics as before/after measurement.
**Workflow**: verify-design-act. This memo IS the 设计 phase artifact.

---

## 0 · Why this exists

P-ε wet-run on aio2 production state.db (2026-05-13) confirmed `memory_coactivation` is **purely reactive** — the trace ONLY grows when `memory_search` fires. Three concrete observations:

1. **M1 = 1 component / size 29** — single hairball, no internal structure (verify-memo G1 confirmed).
2. **M3 avg_count = 1.86, max_count = 9** — most pairs touched once or twice; no aging mechanism. Cron `prune-coactivation-noise` runs **once daily** with a hard `count ≤ 1 AND last_at older than 30d` filter — binary, not gradient.
3. **M5 = 0.036** — only 3.6% of active memories participate in cofires/co_referenced edges, far below P-ε P3 prediction threshold of 0.20 / 12 weeks.

The verify memo's diagnosis: there is no **Warm tier** between event-driven (Hot, instantaneous) and cron-driven (Cold, daily). P-α fills it.

P-α's specific job: **continuous gradient decay** of coactivation rows so the trace stops accumulating linearly with sessions and starts reflecting recency. Discrete half-life decay via SQL — no LLM, no float schema change, no new tables.

---

## 1 · Goals (in scope)

| # | Goal | Acceptance test |
|---|---|---|
| G1 | `Cmd::Daemon` spawns a background task that calls `decay_coactivation_once(tau_secs)` every `tick_secs` (default 30s) | Start daemon, wait 60s, observe stderr log: `substrate-tick: ran, swept N rows, pruned M` |
| G2 | Decay math: every τ seconds since `last_at`, `count` halves (integer divide); `last_at` advances by τ | Unit test: row with count=8, last_at=T-τ → after one tick: count=4, last_at=T |
| G3 | Rows with count < 1 after decay are DELETEd | Unit test: row with count=1, last_at=T-τ → after one tick: count=0, then row gone |
| G4 | Idempotent: re-running with `now` unchanged is a no-op | Unit test: same `now` × 2 calls → same row state, second returns swept=0 |
| G5 | No conflict with `record_coactivation` (concurrent INSERT/UPDATE during a sweep) | Wet-run: hammer memory_save while daemon ticks; SQLite WAL handles it; zero panics |
| G6 | Full ablation: `AGENT_BRIDGE_DISABLE_SUBSTRATE_TICK=1` env makes daemon skip the spawn | Set env, start daemon, observe stderr log: `substrate-tick: disabled by env`; no SQL touched |
| G7 | CLI mirror `dream decay-coactivation [--tau-days N] [--dry-run]` for manual / cron use (matches existing `dream …` pattern) | `dream decay-coactivation --dry-run` prints decay candidate count, no writes |
| G8 | All M1-M8 audit metrics (P-ε) remain valid before/after; the report is the canonical evaluator | After 14d of P-α running, P-ε shows M1 components 1 → ≥2 OR P-α null-rule fires (per §4) |

## 2 · Non-goals

- ✗ Adding L2 substrate (Seed grid) — that's v22.
- ✗ Float schema change for fractional counts — integer halving is sufficient and reversible.
- ✗ Modifying `record_coactivation` semantics — writers continue to INCREMENT on co-firing; only the sweep changes.
- ✗ Modifying existing hygiene cron — `prune-coactivation-noise` keeps running (lower priority once P-α decay is doing the heavy lift, but no removal in v1).
- ✗ Cross-machine consensus on decay state — single-node only; sync covers the post-decay rows naturally.
- ✗ Daemon-http hosting the tick — single host (`Cmd::Daemon`) avoids duplicate writers.

---

## 3 · Architecture

### 3.1 Where the tick runs

```
agent-bridge daemon                    ← Unix socket JSON-RPC, always-on
   │
   ├── existing services (Hub)
   │
   └── P-α background task             ← NEW
         loop {
             sleep(tick_secs);
             decay_coactivation_once(tau_secs, now);
         }
```

Spawned during `Cmd::Daemon` startup via `tokio::spawn`. Lives for the daemon's lifetime. No external supervisor.

`Cmd::DaemonHttp` and `Cmd::Mcp` do NOT spawn this task — those are read-mostly / short-lived processes. Single-writer discipline avoids race conditions even though SQLite WAL would tolerate it.

### 3.2 Decay math (integer-safe)

Half-life decay with integer counts:

```
for each row R where last_at + τ ≤ now:
   R.count := R.count / 2     -- integer divide (floor)
   R.last_at := R.last_at + τ -- advance by one half-life, NOT rebase to now
   if R.count < 1:
      DELETE R
```

Properties:
- A row with `count = 8` decays as `8 → 4 → 2 → 1 → 0 (deleted)` over 4τ.
- Continuous re-firing (record_coactivation increments) resets the clock naturally.
- Advancing `last_at` by exactly τ (not rebasing to `now`) preserves the "decay rate" semantic: if τ=7d and `last_at = T - 21d`, three ticks (each catching one half-life) bring the row to count/8.
- Each tick processes at most one half-life per row, so catching up an old row takes multiple ticks. Acceptable for steady-state; old rows decay gradually rather than all-at-once.

### 3.3 The single SQL pass

```sql
-- One tick: advance one half-life for every eligible row.
UPDATE memory_coactivation
   SET count   = count / 2,
       last_at = last_at + ?tau
 WHERE last_at + ?tau <= ?now;

-- Reap dead rows.
DELETE FROM memory_coactivation WHERE count < 1;
```

Two statements, single transaction (`unchecked_transaction()` for SQLite). Returns affected row counts for logging.

For very stale tables (months of un-decayed rows), call repeatedly within the same tick until UPDATE returns 0. Per-tick budget cap: at most 10 iterations to bound wall-time.

### 3.4 Trait method signature

```rust
async fn decay_coactivation_once(
    &self,
    tau_secs: i64,        // half-life in seconds; default 7*86400
    now: i64,             // wall clock at tick start; injected for determinism in tests
) -> Result<DecayCoactivationStats>;
```

```rust
pub struct DecayCoactivationStats {
    pub swept: u64,       // rows whose count was halved this call
    pub pruned: u64,      // rows whose count dropped to 0 and were DELETED
    pub iterations: u32,  // how many UPDATE/DELETE rounds ran (1..=10)
}
```

### 3.5 CLI surface (sibling to bg tick)

```
agent-bridge dream decay-coactivation
    [--tau-days N=7]
    [--dry-run]
    [--max-iterations N=10]
    [--json]
```

Same trait method as bg task. `--dry-run` reports counts but rolls back the transaction. Useful for ad-hoc inspection + safe to run from cron as a backup.

### 3.6 Env flags

| Flag | Effect |
|---|---|
| `AGENT_BRIDGE_DISABLE_SUBSTRATE_TICK=1` | Daemon skips the spawn entirely; CLI command still works |
| `AGENT_BRIDGE_TICK_SECS=N` | Override tick cadence (clamp 5..=300) |
| `AGENT_BRIDGE_TAU_SECS=N` | Override half-life (clamp 3600..=2592000, 1h..30d) |

Defaults: tick=30s, tau=604800s (7 days), env-overridable for experiments.

---

## 4 · Falsifiable predictions (14-day evaluation matrix)

Re-evaluate via P-ε MCP tool (`memory_substrate_audit` weekly).

| ID | Prediction | Threshold | Window | Null-rule |
|---|---|---|---|---|
| P-α-1 | After 14d P-α deployed, P-ε M3 `avg_count` distribution shifts from current 1.86 toward larger spread (variance/mean > 1.0 = smooth tail emerges) | variance/mean ≥ 1.0 | 14 days | If still flat (variance/mean < 0.5): co-firing signal too sparse — escalate to P-γ (perception subscription) |
| P-α-2 | P-ε M1 components climbs from 1 to ≥ 2 (modular structure emerges as decay clears spurious links) | components ≥ 2 | 14 days | If still M1=1: hairball is structural not temporal — escalate to P-β (recall-bias might break it) |
| P-α-3 | P-ε M3 `total_pairs` becomes bounded — slope shifts from current linear ~44/day toward sub-linear | new pairs/day at 14d ≤ pairs deleted/day at 14d (steady state) | 14 days | If still growing linearly: τ=7d too long for current rate — propose τ=3d in P-α v2 |
| P-α-4 | P-ε M2 `cofires` edge count grows monotonically — decay strengthens promote selectivity (current dream promote uses count≥5, which decay enforces) | cofires count after 14d > cofires count at deploy | 14 days | If cofires plateaus or shrinks: promote threshold too conservative for post-decay distribution → propose lowering `dream promote --min-count` |

Re-run P-ε via `dream substrate-audit --json` daily; track P-α-1..4 against the 14-day window.

---

## 5 · Multi-Grid 7 invariants cross-check

| Invariant | P-α posture |
|---|---|
| #1 Parallel uniaxial grids | N/A (P-α is a substrate hygiene op, not a grid) |
| #2 Exchange signals not weights | ✅ output is signal-shape (decay stats); no weight transfer |
| #3 L1/L2/L3 separation | ✅ P-α operates purely on L2-proxy (coactivation trace); doesn't reach into L1 retrieval or L3 UI |
| #4 Eager loading | ✅ runs against eager-loaded SQLite; no lazy state |
| #5 Dormancy = reduced cadence not unload | ✅ this is literally the operational form of "dormancy = reduced cadence" for coactivation rows |
| #6 Bimodal cross-similarity | N/A (single-grid op) |
| #7 Three-axis decoupling (state / cadence / perception) | ✅ tick is a cadence-axis change; doesn't touch state existence or perception subscription |

All 7 pass or N/A.

## 6 · 6 anti-patterns cross-check

1. **Optimizing against unverified targets**: ✅ P-ε wet-run is the verified target — M1/M3/M5 numbers are real.
2. **Conflating topology with capacity**: ✅ decay reshapes topology; doesn't affect capacity (active memory count unchanged).
3. **Mining internal observables for multi-axis**: ✅ decay is a single-axis (count) op.
4. **Replacing FEP dynamics**: ✅ doesn't touch substrate physics (there is no substrate yet).
5. **Merging carrier weights**: ✅ no merging.
6. **Adding Rust complexity without tests**: ✅ ≥4 unit tests (see §11).

## 7 · 5 preserved properties (must NOT regress)

1. `memory_save / memory_get / memory_search` contracts unchanged — `record_coactivation` still increments on co-fire.
2. ζ-10 cron `prune-coactivation-noise` continues to work (now redundant for steady-state, but safety net for stale tables).
3. P-ε `memory_substrate_audit` continues to report correct numbers — decay just shifts what those numbers describe.
4. Cross-machine sync semantics unchanged — decayed rows look identical to "never grew much" rows from sync's perspective.
5. No LLM in any Hot-tier op — P-α is a Warm-tier SQL pass, zero LLM.

---

## 8 · Gate-α (this memo's pass criteria)

**Gate-α passes when**:
1. This memo has trait method signature (§3.4), SQL (§3.3), decay math (§3.2) ✅
2. Acceptance tests (§1 G1-G8) are concrete ✅
3. 4-row falsifiable prediction matrix (§4) with null-rules ✅
4. 7-invariant + 6-anti-pattern + 5-preserved cross-checks pass ✅
5. No reviewer blocking objection (or user-explicit Gate override)

**If Gate-α passes**: implement (~half day per verify memo cost estimate).

---

## 9 · File map (predictive, no new files)

```
crates/store/src/lib.rs                # +DecayCoactivationStats + trait method
crates/store/src/sqlite.rs             # +impl + ≥4 unit tests
crates/bridge/src/main.rs              # +Cmd::Daemon spawns bg task
                                       # +DreamOp::DecayCoactivation + handler
                                       # +substrate-tick bonus line in run_dream_weekly (optional)
```

No schema change. No new files.

---

## 10 · Vision rule self-check

- ✓ **rule 1 cold-start**: decayed trace gives next-session-you a cleaner attention surface (no spurious old co-firings)
- ✓ **rule 2 data-triggered**: 4 falsifiable predictions with numeric thresholds + null-rules
- ✓ **rule 3 seed unchanged**: zero touch on v0.13.0 path-C / hub_clusters / near_keys
- ✓ **rule 4 reversibility**: env flag disables bg spawn; ablation is one env var
- ✓ **rule 5 identity continuity**: decay is monotonic and deterministic — replaying same events produces same final state across machines

---

## 11 · Open questions (defer to impl-time)

1. **Q-α-1** — Should bg task also call `dream promote --tier 1` opportunistically when M3 distribution shifts? (probably no; keep concerns separated; promote stays on its 03:42 schedule.)
2. **Q-α-2** — Once daemon-http becomes the primary long-lived process (per v20 trajectory), should P-α migrate there? Defer until daemon-http is canonical.
3. **Q-α-3** — Should `last_at` rebase be tracked as a snapshot-able event so cross-machine sync can reconcile? Probably no in v1 — decay is reproducible from `(count, first_at, last_at, now)`; sync diff still works.
4. **Q-α-4** — Daily cron should report the daily aggregate of P-α stats (sum of swept/pruned over 24h). Add to `dream weekly`? Defer to next pass.

---

## 12 · Cost summary

| Phase | Effort | Risk |
|---|---|---|
| Design (this memo) | ~45 min ✅ done | ZERO |
| Reviewer window | 48h OR user-explicit override | ZERO |
| Impl + tests | ~3-4h | LOW (single new SQL pass, deterministic decay math) |
| Wet-run validation | ~1h (daemon up, observe stats) | LOW |
| **Total to ship** | **~5h elapsed + 48h review** | **LOW** |

---

## Appendix A — How P-α composes with P-ε

P-ε is **read-only observability**; P-α is **continuous-write hygiene**. They are orthogonal:

| | P-ε | P-α |
|---|---|---|
| Reads memory_coactivation | yes | yes (for sweep) |
| Writes memory_coactivation | no | yes (UPDATE + DELETE) |
| Process | Hot tier (on-demand) | Warm tier (1/30s continuous) |
| Affects M1-M8 | reports | reshapes |

**P-ε is the evaluator of P-α**. After P-α deploys, every `dream substrate-audit` call shows whether P-α-1..4 predictions held or fired their null-rules. This is the verify-design-act loop closing on its own infrastructure.

---

## Appendix B — Why the user's verify-memo P-α scope is sufficient

Verify memo §P-α: "background task in `agent-bridge daemon` runs every N seconds (1 ≤ N ≤ 60), reads recent coactivation rows, applies temporal decay to `count` (exponential, half-life ~7d), promotes/prunes deterministically without LLM."

This memo concretizes:
- **N seconds** → 30s default (mid-range; configurable)
- **temporal decay to count** → integer half-life: count /= 2 every τ since last_at
- **promotes/prunes deterministically** → no promote in P-α (separate cron); prune is "count < 1 → DELETE" naturally falling out of decay
- **without LLM** → ✅ pure SQL

No scope creep beyond verify memo's intent.

---

**Memo complete. Awaiting Gate-α (reviewer window or user override).**
