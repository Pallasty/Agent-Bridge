> `docs/design/BOUNDED_COACTIVATION_LATCH_2026_06_28.md` — **IMPLEMENTED as v38 and currently verified; see `docs/reports/goal-c-u/2026-07-01-bounded-coactivation-latch-current-state.md`.**

## 0. Status

> **SUPERSEDED STATUS NOTE (2026-07-01): IMPLEMENTED AND VERIFIED.**
>
> This design has landed in the store as the v38 bounded coactivation latch. The live schema is now v39, which includes v38's additive `last_cofire_at` rung and the v38 behavior wiring in `record_coactivation`, `decay_coactivation_once`, and `memory_prune_coactivation_noise`. The original proposal text below is retained as design rationale; do not treat the historical "owner-gated" wording as an active blocker.

- **Author:** `claude-opus-4.8` (Data session, `borrowed-patterns` campaign).
- **Date:** 2026-06-28.
- **Builds on:** v37 (`memory_coactivation.consolidated INTEGER NOT NULL DEFAULT 0` already landed, master `1c078b9`, currently inert) and the reverted L2 wiring + its adversarial-verify findings (forum #102 post #2586, memory `decision_v37_l1_landed_l2_held_20260628`).
- **What this artifact IS:** the bounded-latch design that the held L2 wiring needs before it can land.
- **What this artifact is NOT:** a code change. No migration, no decay-behavior change, no schema mutation lands from this doc.

## 1. Problem recap — why the first latch was reverted

The held L2 wiring made a consolidated edge **permanently immune** to decay pruning. A 3-lens adversarial verify found two MAJORs:

1. **Unbounded growth.** The latch was a *monotonic ratchet with no un-latch path*. Any edge that **ever** transiently reached `count >= consolidate_at_count` latched **forever**, even if it immediately decayed back to 0 (exactly the `important_but_bursty` trajectory in `coactivation_latch.rs`). The true immune set is the cumulative *“ever reached threshold”* set, which a **snapshot** (`coactivation_latch_threshold_eval` reported ~6.3% of 652 live edges at `count>=5` *right now*) does **not** bound. Worse: `decay_coactivation_once` keeps advancing a cold latched edge’s `last_at` (the halving `UPDATE` matches `count==0` rows too), so `memory_prune_coactivation_noise` (`last_at <= cutoff`) could never reclaim them either — latched edges were effectively **immortal**.

2. **Inconsistent immunity.** `memory_prune_coactivation_noise` (`DELETE WHERE count <= ?1 AND last_at <= ?2`, `sqlite.rs:4119`) had **no** `consolidated` check, so it deleted latched edges while automatic decay never could. The “immune to pruning” invariant was non-uniform across the two live prune paths.

The root cause of both: **immunity was a function of a one-time event (ever-reached-threshold), not of current state.** A sound latch must make immunity a function of *current* state so the immune set is bounded and every prune path can apply the same rule.

## 2. Core mechanism — recency-conditioned immunity

Replace *permanent* immunity with immunity that is **conditional on recent activity**. Define one immunity predicate, used identically by **every** prune path:

```
is_immune(row, now) := row.consolidated = 1
                       AND row.last_cofire_at >= now - STALE_WINDOW_SECS
```

- `consolidated` (sticky, from v37): the edge has *proven* importance — it reached `count >= consolidate_at_count` at least once. Set on co-fire, never cleared.
- `last_cofire_at` (NEW, v38): the timestamp of the **real last co-fire**, written **only** by `record_coactivation`, **never** by decay. This is the “currently active” signal the old design lacked.

An edge is immune **iff it is both proven-important AND warm** (co-fired within the last `STALE_WINDOW_SECS`). A proven edge that goes genuinely cold (no co-fire for longer than the window) loses immunity and is reaped by the next sweep — the reaping of the row *is* the un-latch (no explicit flag-clearing needed).

This single change fixes both MAJORs:

- **Bounded (MAJOR 1):** the immune set `{rows : consolidated=1 AND last_cofire_at >= now - STALE}` is bounded **in time** by the sliding window — every edge exits ≤ `STALE` after its last co-fire (§5) — **and in size** by an enforced ceiling `max_latched_edges` with coldest-first eviction (§5.1). It is **directly snapshot-measurable**, eliminating the snapshot-vs-cumulative gap. (Recency alone bounds time, *not* size — see §5(B); the cap is what makes size structural.)
- **Consistent (MAJOR 2):** both `decay_coactivation_once` and `memory_prune_coactivation_noise` gate their `DELETE` on the *same* `NOT is_immune(...)` predicate, so a warm latched edge is immune in **both** paths and a cold latched edge is reapable in **both**.

## 3. Schema (v38) — one additive column

`consolidated` already exists (v37). The bounded latch needs one more additive column:

| Column | Type | Set by | Meaning |
|---|---|---|---|
| `last_cofire_at` | `INTEGER NOT NULL DEFAULT 0` | `record_coactivation` only | unix-seconds of the most recent real co-fire; **never** touched by decay |

Migration v38 must use the **full** v37 rung idiom — version-gate **and** version-bump, not just the column guard (the v37 block gates on `cur=="36"` and bumps to `"37"`, `sqlite.rs:1510-1533`). Shown in full so the backfill runs **exactly once** (gated by the version bump, not by a fragile column-value `WHERE`):

```rust
// ── v38: bounded coactivation latch — last_cofire_at (warmth signal).
let cur: String = c
    .query_row("SELECT value FROM schema_meta WHERE key='version'", [], |r| r.get(0))
    .unwrap_or_else(|_| "37".to_string());
if cur.as_str() == "37" {
    let exists: i64 = c
        .query_row(
            "SELECT COUNT(*) FROM pragma_table_info('memory_coactivation') WHERE name='last_cofire_at'",
            [], |r| r.get(0))
        .unwrap_or(0);
    if exists == 0 {
        c.execute(
            "ALTER TABLE memory_coactivation ADD COLUMN last_cofire_at INTEGER NOT NULL DEFAULT 0",
            [])?;
    }
    // One-time cosmetic backfill: seed from `first_at` (a REAL first-co-fire timestamp),
    // NOT the decay-bumped `last_at` (which on a count-0 row was advanced by decay, not by
    // a co-fire). Immaterial to immunity — `consolidated` is uniformly 0 at v38 start, so
    // is_immune is false for every legacy row regardless — so this is honesty, not correctness.
    c.execute("UPDATE memory_coactivation SET last_cofire_at = first_at", [])?;
    let _ = c.execute("UPDATE schema_meta SET value='38' WHERE key='version'", []);
}
```

**Implementation obligation (folded in from review):** the v37-pinning tests must move to `"38"` as part of the wiring — `schema_meta_version_returns_current_after_open` (`sqlite.rs:~20612`) and the v32-ladder reopen assertion (`sqlite.rs:~16375`), both currently asserting `"37"`. They are the intended tripwire for a schema bump.

Because `consolidated` is `0` for every row until the v38 wiring first sets it (the v37 column was never written — L2 was reverted), there is **no** pre-existing stale-latched-row hazard: the first edge to latch under v38 sets `consolidated` and `last_cofire_at` in the *same* co-fire, so the two are always mutually consistent.

`STALE_WINDOW_SECS` and `consolidate_at_count` live in `coactivation_latch::LatchConfig` as the single source of truth (add `stale_window_secs` to the struct), so the SQL binds them rather than hardcoding.

## 4. Wiring (the three touch points)

### 4.1 `record_coactivation` — set the two signals on co-fire

In the existing `ON CONFLICT DO UPDATE` (and the `INSERT` for a fresh edge), stamp both:

```sql
-- INSERT (fresh edge): count starts at 1; last_cofire_at = now; consolidated stays DEFAULT 0
VALUES (?a, ?b, 1, ?now, ?now, ?ctx, ?now)            -- trailing ?now = last_cofire_at

-- ON CONFLICT DO UPDATE:
count          = count + 1,
last_at        = ?now,
last_cofire_at = ?now,                                 -- always: this IS a co-fire
ctx_centroid   = ?ctx,
consolidated   = CASE WHEN count + 1 >= ?threshold THEN 1 ELSE consolidated END
```

`count` in the `ON CONFLICT` SET is the pre-increment value (SQLite evaluates all SET RHS against the old row), so `count + 1` is the new count — the edge latches exactly when the new count reaches the threshold. `consolidated` is sticky (the `ELSE` preserves it).

**Fresh-edge / threshold≤1 consistency (folded in):** the `INSERT` leaves `consolidated` at its `DEFAULT 0` and a fresh edge has `count = 1`, so at the default `consolidate_at_count = 5` it cannot latch on first co-fire (correct). But the pure kernel `coactivation_latch::decide(1, …)` would `Latch` if `consolidate_at_count` were retuned to `1`, so the INSERT path must agree: either set the inserted `consolidated = CASE WHEN 1 >= ?threshold THEN 1 ELSE 0 END`, **or** assert `consolidate_at_count >= 2` in `LatchConfig` with a comment that a fresh `count=1` edge is never eligible to latch. Pick one at wiring time so the INSERT path and the kernel never disagree.

### 4.2 `decay_coactivation_once` — reap only non-immune dead rows

The halving `UPDATE` gains one guard — `AND count >= 1` — so a warm latched edge that has already decayed to `count 0` (immune, never reaped) is not pointlessly re-touched every sweep (`0/2` is `0` anyway, so excluding `count<1` rows is behavior-neutral for live rows). This also stops `last_at` drift on dead-but-immune rows and keeps `DecayCoactivationStats.swept` honest. The halving WHERE becomes `WHERE last_at + tau <= now AND count >= 1`. The reap then becomes:

```sql
DELETE FROM memory_coactivation
 WHERE count < 1
   AND NOT (consolidated = 1 AND last_cofire_at >= ?now - ?stale_window_secs)
```

A warm latched edge at `count 0` survives (immune); a cold latched edge (`last_cofire_at` older than the window) is reaped; an un-latched edge is reaped exactly as before (`consolidated=0` ⇒ predicate false ⇒ `NOT false = true`).

### 4.3 `memory_prune_coactivation_noise` — same predicate (MAJOR 2 fix)

Both the `COUNT` and the `DELETE` gain the identical immunity guard:

```sql
... WHERE count <= ?max_count AND last_at <= ?cutoff
        AND NOT (consolidated = 1 AND last_cofire_at >= ?now - ?stale_window_secs)
```

Now the two prune paths agree: a warm latched edge is immune in both; a cold latched edge is reclaimable in both. The maintenance tool keeps its role (operators can still purge genuine noise) but can no longer silently delete a *currently-important* edge.

## 5. Boundedness — what is and is NOT guaranteed

Be precise about two *different* claims, because the reverted design conflated them.

**(A) Bounded in TIME — rigorous, and this is the actual fix for MAJOR 1.** At any instant `now`:

```
immune(now) = { e : e.consolidated = 1  AND  e.last_cofire_at >= now - STALE }
            ⊆ { e : e.last_cofire_at >= now - STALE }
            = { distinct edges co-fired in the window [now - STALE, now] }
```

The load-bearing property is **eviction**: `last_cofire_at` is written *only* by a real co-fire and *never* advanced by decay, so **every** edge leaves the immune set at most `STALE` seconds after its last co-fire. The immune set is a *sliding window over current activity*, not a monotone accumulation. Its hard ceiling is `P` — the finite number of memory pairs that ever co-fire — and unlike the reverted design it sheds members continuously. This is the genuine repair: the old immune set was the cumulative *ever-latched* set (monotone in time, unbounded); this one is the *currently proven-and-warm* set. It is also **directly snapshot-measurable**, closing the snapshot-vs-cumulative gap:

```sql
SELECT COUNT(*) FROM memory_coactivation
 WHERE consolidated = 1 AND last_cofire_at >= :now - :stale;     -- the live immune-set size
```

**(B) Bounded in SIZE by a constant — NOT guaranteed by recency alone (honest caveat).** Time-boundedness does *not* by itself bound the immune-set *size* to anything small. Informally `|immune(now)|` is on the order of `R · STALE` for a steady co-fire rate `R`, but `R · STALE` is a *workload* quantity, not a design constant, and `record_coactivation` explodes a single co-fire of `k` keys into `k(k-1)/2` pairs stamped warm in the **same** call (`sqlite.rs:6197-6253`). One batch co-fire of a large key set can make `O(k²)` edges warm at once; a workload that periodically does so keeps `O(k²)` edges warm continuously, and `P` itself grows with the store. So §5(A) bounds the set in time and by `P`, but the *size* is bounded only by the co-fire working set, which can be a large and growing fraction of all live edges. **Do not read `|immune| ≲ R·STALE` as a small constant bound.** Size must be bounded *structurally*, by §5.1 — not left to observation.

### 5.1 Enforced size ceiling (structural size bound)

Add a configured hard cap `max_latched_edges` (in `LatchConfig`) and **enforce** it in the periodic `decay_coactivation_once` sweep (cheap — once per sweep, not per co-fire): after the reap, if the live immune-set size (the §5(A) query) exceeds the cap, **evict** the excess by un-consolidating the **least-recently-co-fired** latched edges (lowest `last_cofire_at`) down to the cap — un-consolidated cold rows are then reaped by the same/next sweep:

```sql
-- evict oldest-warm latched edges beyond the cap (run inside the decay tx, after the reap)
UPDATE memory_coactivation SET consolidated = 0
 WHERE rowid IN (
   SELECT rowid FROM memory_coactivation WHERE consolidated = 1
    ORDER BY last_cofire_at ASC
    LIMIT MAX(0, (SELECT COUNT(*) FROM memory_coactivation WHERE consolidated = 1) - :max_latched_edges)
 );
```

This makes the size bound **structural**: `|immune(now)| ≤ max_latched_edges` always, independent of workload or the `k²` pair explosion. The eviction policy (drop the coldest-proven edges first) is the right one: under pressure we keep the most-recently-reinforced important edges. §10 gate #1 then becomes an *enforced* invariant (assert/alert if the immune count ever exceeds the cap), not merely an observed plateau.

## 6. Churn-value preservation

The latch exists to stop the *re-learn / re-prune oscillation* of an important-but-bursty edge (co-fire → quiet window decays count to 0 → pruned → co-fire re-mints from scratch). Under this design:

- An edge co-fired at `t1 < t2 < …` with inter-co-fire gaps `≤ STALE_WINDOW` stays warm (its `last_cofire_at` is always within `STALE` of `now`). Once it has proven importance (`consolidated=1`), it is immune through each quiet dip to `count 0`, so it is **not** reaped and **not** re-minted — the churn is eliminated for exactly the edges the latch targets.
- An edge whose gap exceeds `STALE_WINDOW` (genuinely abandoned) loses immunity and is reaped — correct: it is no longer important, and keeping it would be the unbounded-growth bug.

So `STALE_WINDOW_SECS` is precisely *“how long an idle but once-important edge is kept alive.”* It is the single knob trading churn-suppression (larger) against immune-set size (smaller).

### 6.1 The cooldown half is intentionally OUT OF SCOPE (folded in)

`coactivation_latch` is *“consolidation latch **+ regrowth cooldown**”* — it also has `regrowth_cooldown_steps`, `in_cooldown()`, and a cooldown branch in `simulate_prunes`. This v38 design wires **only the latch/immunity half**, not cooldown. That is a deliberate scope decision, stated here so it is not a silent gap:

- **Why acceptable:** the latch already covers the bursty-*important* edge (it stays immune across quiet dips while warm). Cooldown targets a *different* edge — a **non-latched, flapping** pair that repeatedly mints, decays, gets reaped, and is instantly re-minted. The latch does not address that flapping, but the flapping edge is by definition below threshold (never proven important), so its churn is lower-stakes; suppressing it is a separable, future enhancement (and would need a tombstone/“recently-pruned” record, more schema).
- **Acceptance-baseline correction:** because cooldown is NOT shipping, the §10.3 churn target must be re-derived from a **latch-only** simulation — `coactivation_latch::simulate_prunes(..., use_latch=true)` with cooldown disabled — *not* from `measure_churn`’s combined latch+cooldown number. Quoting the module’s cooldown-inclusive churn figure as the v38 acceptance bar would be an apples-to-oranges baseline. The shipped churn reduction is whatever the latch alone delivers on real co-fire trajectories.

## 7. Tuning — both knobs, measured (not snapshotted-as-cumulative)

- **`consolidate_at_count` (eligibility):** the live snapshot (`coactivation_latch_threshold_eval`: 652 edges, `count` max 10, p50 1 / p90 3 / p95 5 / p99 8) supports `5` (the module default) — it selects the top ~6% by count as *eligible* to latch. Note this is now only an **upper bound** on the immune set; the recency gate (§5) makes the *actual* immune set smaller and bounded.
- **`stale_window_secs` (immunity duration):** tune against the decay half-life `tau` and observed co-fire gaps. A once-co-fired edge with `count=C` decays to 0 in ≈ `log2(C)·tau` (≤ ~3.3·tau for `C≤10`), so `STALE` should be at least a small multiple of `tau` (survive a normal quiet window) but small enough that the measured immune-set size (§5 query) stays a bounded small fraction. **Concrete starting point:** with the deployed decay cadence (the sync/maintenance path calls `decay_coactivation_once` on a ~daily-ish `tau`), start `STALE ≈ 4·tau` (≈ a few days) and `max_latched_edges` at ≈ the snapshot’s `count>=5` cohort (≈ 6.3% of current edges ≈ 40 on today’s 652-edge store), then adjust both from the live §5(A) time series before promotion. These are starting values to be confirmed by measurement, not final constants.
- **Acceptance is a *time-series* measurement, not a single snapshot:** sample the §5 immune-set-size query periodically under live load and confirm it **plateaus** (bounded) rather than trends upward. This is the gate that the reverted design failed; it is now directly checkable because immunity is current-state.

## 8. Migration & rollback

- **Forward (v38):** the single guarded `ALTER ... ADD COLUMN last_cofire_at` + optional backfill (§3), then the three wiring edits (§4). Additive schema; the wiring is a behavior change gated by §10.
- **Rollback:** revert the three wiring edits (decay/noise-prune return to their pre-v38 `WHERE`, `record_coactivation` stops stamping `last_cofire_at`); optionally drop the column. **Zero data loss** — `last_cofire_at` is derived from co-fire events and `consolidated` is recomputed on future co-fires. Reverting leaves the store at v37 (consolidated column inert), the exact current production state.

## 9. Risks & adversarial analysis

- **(a) Pre-v38 rows / NULL-vs-0 `last_cofire_at` — Low.** `NOT NULL DEFAULT 0` + the fact that `consolidated` is uniformly `0` at v38 start means immunity is moot for legacy rows until they re-co-fire (which sets both columns together). No stale-latched-row window exists.
- **(b) Clock skew / non-monotonic `now` — Low.** `last_cofire_at` and the reap’s `now` come from the same clock; `STALE` is a *duration*, robust to a constant offset. A large backward clock jump could transiently mis-classify warmth (same exposure `decay_coactivation_once` already has via `last_at`); not worse than today.
- **(c) `STALE_WINDOW` mis-tuned — Medium, mitigated by measurement.** Too long → larger (still bounded) immune set; too short → important edges reaped during normal gaps (churn returns). The §5 immune-set query + §7 time-series acceptance make this observable and tunable, not a silent failure.
- **(d) Decay still halves latched rows — intended.** Count decays for everyone; immunity gates *reaping*, not decaying. A warm latched edge sits at `count 0` but immune; when it goes cold it is reaped. Per-edge cost is a few bytes while warm, bounded by §5.
- **(e) Sync — None.** `memory_coactivation` is node-local: it is absent from `memory_export`/`memory_import`/`sync.rs` (verified during the L2 review). `consolidated` and `last_cofire_at` stay node-local; each node latches from its own co-fire trajectory, which is correct. No cross-node leak, no `memory.jsonl` churn.
- **(f) Alternative considered — reuse `last_at` by freezing it on dead rows.** Instead of a new column, decay could stop advancing `last_at` for `count==0` rows so `last_at` becomes a “cold-since” marker. **Rejected:** it overloads `last_at` (decay-progress for live rows vs cold-since for dead rows) and changes decay semantics for *every* edge, not just latched ones — more blast radius and less self-documenting than one additive, write-once-per-co-fire column.

## 10. Gates / acceptance (before the wiring may land)

1. **Bounded immune set (the MAJOR-1 gate) — STRUCTURAL, not observational.** The §5.1 eviction makes `|immune(now)| ≤ max_latched_edges` an *enforced invariant*; gate on a test that drives the immune set past the cap and asserts the sweep evicts back to it, plus a runtime assertion/alert if the live §5(A) count ever exceeds the cap. The time-series *plateau* of the §5(A) query under live load is a secondary monitoring check, not the primary bound.
2. **Consistent immunity (the MAJOR-2 gate):** a test pins that a *cold* latched edge is reaped by **both** `decay_coactivation_once` and `memory_prune_coactivation_noise`, and a *warm* latched edge survives **both**. Pin the boundary explicitly to the inclusive predicate: an edge with `last_cofire_at == now - STALE` is still warm (survives); one at `now - STALE - 1` is cold (reaped).
3. **Churn reduction — latch-only baseline (per §6.1):** the prune-event count drops materially for important-but-bursty edges vs the un-latched baseline, measured by `simulate_prunes(use_latch=true)` with cooldown disabled on real co-fire trajectories — **not** `measure_churn`’s cooldown-inclusive figure.
4. **No regression:** un-latched edges prune exactly as pre-v38 (existing decay tests unchanged); the `count >= 1` halving guard is behavior-neutral for live rows.
5. **Re-run the full 3-lens adversarial verify** — the bounded-growth and immunity-consistency lenses must now return SAFE (they were the FIX-REQUIRED lenses on the reverted L2).
6. **Human review required even if 1–5 pass** — this changes shared-store decay behavior for every node.

## 11. Definition of done (for THIS proposal)

DONE when this doc is committed to `docs/design/` and posted to kanban #102 for owner review. It authorizes **no** schema or behavior change. The next action is owner review; on approval, the v38 wiring is implemented in an isolated worktree, validated, **re-run through the same 3-lens adversarial verify** (which must now return SAFE on the bounded-growth and immunity-consistency lenses), and only then committed.

## 12. Adversarial review record

This design was hardened against a 3-lens adversarial review (boundedness / behavior-correctness / honesty). The **behavior** lens returned SOUND (the two core fixes — time-boundedness via write-once `last_cofire_at`, and a unified immunity predicate across both prune paths — are correct, un-latched behavior is preserved, and the migration is additive/idempotent/fresh-DB-safe). Two MAJORs from the other lenses were folded in:

- **Boundedness overclaim → fixed (§5/§5.1):** recency bounds the immune set in *time* but not in *size* (the `k(k-1)/2` pair explosion can make `O(k²)` edges warm at once). §5 now states this honestly and §5.1 adds an **enforced** `max_latched_edges` ceiling with coldest-first eviction so size-boundedness is *structural*, not observational.
- **Cooldown silently dropped → fixed (§6.1):** the module’s cooldown half is now explicitly out of scope with rationale, and the §10.3 churn-acceptance baseline is corrected to a latch-only simulation (not `measure_churn`’s cooldown-inclusive figure).

Minor/nit fixes folded in: inclusive `>=` immunity boundary throughout (predicate vs prose), the full version-gated v38 migration idiom + the v37-test-update obligation (§3), the `count >= 1` halving guard (§4.2), the `INSERT`-vs-kernel agreement at `threshold ≤ 1` (§4.1), backfill from `first_at` not the decay-bumped `last_at` (§3), and a concrete `STALE`/`max_latched_edges` starting point (§7). The boundedness and honesty lenses’ FIX-REQUIRED verdicts apply to the *previous* draft; this revision resolves them and must still pass a fresh verify at wiring time (§10.5).
