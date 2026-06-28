# Memory dynamics (T8 / P4) — connectivity-repair, graceful-forget, decay-regime A/B

CascadeProjects borrow scan 2026-06-28, plan `borrowed_patterns_landing_20260628`
step `p4-t8-repair`. Three memory-dynamics borrows from the structural-plasticity
family. Only the first ships code this round; the other two are deliberately
**plan/harness-first** (the backlog flags they need shadow quantification before
any promotion).

---

## 1. connectivity-repair candidates — LANDED (code)

**Module** `ab_store::connectivity_repair` + read-only
`examples/connectivity_repair_eval.rs`.

**Problem.** AB detects graph components (`hebbian_clusters` Union-Find over
`memory_edges`) but has no repair step. Orphan islands persist; `memory_neighbors_bfs`
cannot cross a cut, so spreading-activation recall degrades across fragments
(the 60% orphan rate from `finding_graph_orphan_topology_20260511`).

**Borrow + correction.** `TCF/src/core/neural_plasticity.py::_optimize_topology`
stitches fragmented topology but pairs islands with `np.random` — the
anti-pattern (non-reproducible, sync-hostile). The port keeps the idea and makes
it **deterministic**: bridge target chosen by (shared-tag overlap, importance,
key), never randomly. One bridge proposed per non-mainland component, connecting
the island's highest-importance representative to the best mainland hub.

**Discipline.** Read-only — `analyze()` returns proposals, writes nothing. Any
real edge goes through the `memory_related_keys_materialize`
propose→review→materialize ladder. A bridge is proposed only when a real mainland
(`largest_component_size >= 2`) exists.

**Status:** read-only shadow surface. No runtime consumer yet; the eval example
is the sole driver. A future MCP tool `memory_connectivity_repair_candidates`
would surface these proposals to the materialize ladder.

---

## 2. graceful-forget — SHADOW PLAN (no code yet)

**Borrow.** `AIMemoryPalace_v2/.../adaptive_pruning.py:65 _prune_node` redistributes
a retiring node's "mass" to its neighbors before archiving it, so its associative
contribution isn't lost outright.

**Reconcile first (why no code yet).** AB already archives on the wall-clock
`memory_decay_importance` path, and the durable-guard already spares
edge-connected rows. So mass-redistribution only adds value for **near-isolated**
nodes (degree ≤ 1) that are about to archive — exactly the rows with little mass
to redistribute. The benefit must be quantified before promoting.

**Shadow plan (the gate before any code):**
1. Read-only measurement over a frozen snapshot: of all rows the decay path would
   archive in a window, how many are degree ≤ 1 (durable-guard would NOT spare)?
2. Of those, how many have ≥ 1 neighbor that would receive redistributed
   importance, and what is the projected recall delta?
3. Only if material (non-trivial fraction × non-trivial recall delta) → implement
   redistribution as a **read-only proposal** first (importance transfer to top-K
   neighbors by edge weight), never an inline mutation. Mirror the
   connectivity-repair propose→review→materialize discipline.

**Predicted outcome:** likely immaterial (durable-guard already covers the
high-value case). Documenting the shadow plan so the negative result is cheap to
confirm and we don't ship speculative pruning logic.

---

## 3. decay-regime A/B harness — SPEC (read-only harness, follow-up)

**Borrow.** `biocortex-rs/src/experiments/mod.rs` compares event-vs-wall-clock
decay regimes. AB ships **three** decay regimes with no harness comparing them:
- `memory_decay_importance` — decays by `updated_at` (wall-clock age).
- `memory_decay_unused_importance` — decays by read-recency (`last_accessed_at`).
- `decay_coactivation_once` — integer half-life on edge `count`.

There is documented **thread-97 false-archive collateral** (a regime archiving
rows another regime would keep).

**Harness spec** (`examples/decay_regime_eval.rs`, read-only, follow-up):
- Snapshot `(key, importance, updated_at, last_accessed_at, access_count,
  degree)` for active non-skill memories (read-only).
- Replay each regime's archive predicate over the snapshot (pure functions; no
  writes) and emit, per regime: archive-set size, and the pairwise **divergence**
  (rows archived by regime A but kept by B).
- Flag **false-archive risk**: rows a regime would archive that are
  edge-connected (degree ≥ 1) — the thread-97 collateral class.
- Output JSON, read-only, deterministic. No new gate chain; this is a
  measurement surface to choose/parameterize regimes, not a runtime mutation.

**Why spec not code this round:** keeps `p4-t8-repair` focused on the one
concrete, clearly-valuable deliverable (connectivity-repair). The harness is a
clean separable follow-up that reuses the same read-only-eval pattern.
