# DESIGN — v22: Agent-Bridge Memory Substrate (Layer 2 Seed Grid)

**Status**: design draft 2026-05-13. **No code until this memo is solid.**
**Predecessor**: `DESIGN-v21-synaptic-trace-and-dream.md` (α/β/γ trace + dream layer).
**Companion docs (AiOT side, ground-truth for v22)**:
- `AiOT:docs/memos/MULTI_GRID_ARCHITECTURE_FOUNDATIONS_2026_05_13.md`
- `AiOT:docs/memos/SEED_STATE_AND_ADJUSTMENT_DIRECTION_2026_05_13.md`
- `AiOT:project_seed_uniaxial_structural_2026_05_13.md`
- `feedback_verify_design_act_workflow.md`
**Forum thread**: design board #6 — *v22 RFC — Agent-Bridge Memory Substrate (Layer 2 Seed grid)*

---

## 0 · Why this exists (verify-phase output)

Agent-Bridge memory has shipped P17–P24 across two layers:

| Layer (per Multi-Grid Foundations §3) | Current ship | Status |
|---|---|---|
| L3 — Inter-grid / UI / recall | Palace viewer, canvas rail, dream stats, dream replay, ζ-10 hygiene cron, embedding stats footer, kind-aware split, lineage rail, retire state machine | ✅ extensive |
| L2 — **Memory substrate** | (none — only `memory_coactivation` SQL **trace**) | ❌ **missing** |
| L1 — Substrate rules | (none — agent-bridge has no learning rule binary) | ❌ **missing** |

The AiOT Seed line solved L1 (Rust crate, 280 LOC, 28 unit tests, softmax-competition + spawn/death + bit-exact cross-machine determinism per ADR-022/023). The agent-bridge memory line has produced rich L3 but **no L2 substrate**.

`dream cluster-probe` (commit `e5c88fb` 2026-05-13) revealed that the SQL coactivation graph collapses to a **single hairball component** (28 nodes, 1 component). The framing this surfaces: SQL trace is not modular by construction. A real substrate (Seed grid with softmax-competition + multi-carrier v10 bimodal property) would produce **internal modular structure** naturally — that's the point of having an L2.

**v22's job**: introduce the missing L2 — wire an AiOT-style Seed grid as the substrate that consumes agent-bridge memory events as perception, and provides modular topology back to L3 retrieval.

This is also the agent-bridge realization of **one of Direction α (multi-grid parallel)'s first concrete instances**: a memory-domain grid that exchanges signals (centroids, surprise events) with future AiOT grids per `project_seed_v10_multiplicity` bimodal cross-similarity invariant.

---

## 1 · Goals (in scope)

| # | Goal | Acceptance test |
|---|---|---|
| G1 | Every memory event (save/get/search) flows through encoder → projection → Seed substrate step | After 1 day of normal use, `substrate_snapshot.parquet` contains ≥ 200 step rows with non-zero `connection_logits` diffs |
| G2 | Substrate is N=256 starting point, eager-allocated, always-warm at 1 Hz Warm tier | `agent-bridge substrate stats` reports `n_alive ≈ 256`, `cadence_hz ≈ 1.0`, `tier=Warm` continuously |
| G3 | Substrate exposes a query API: given a key (or query embedding), return co-active neuron IDs and the keys those neurons last fired on | `substrate.active_neighbors(key, k=8)` returns deterministic ordered list; reused across processes via snapshot reload |
| G4 | Snapshot determinism: same seed + same event log replays bit-exact | `agent-bridge substrate replay --log events.jsonl --seed 42` produces SHA256-identical `substrate_snapshot.parquet` across aio2 and Mac |
| G5 | L2 ablation is clean: turning substrate off does not break L3 retrieval | `AGENT_BRIDGE_DISABLE_SUBSTRATE=1` makes all `substrate_*` calls no-op; existing FTS/semantic/cofires paths unchanged |
| G6 | Compute envelope budget held: substrate adds < 1% of one CPU core sustained | After 7-day dogfood, `top` shows substrate worker thread ≤ 1% CPU time avg; encoder MiniLM dominates if anything |
| G7 | Memory budget held: substrate state ≤ 5 MB RAM, ≤ 5 GB/year on-disk | `du -sh state.db substrate_snapshot.parquet` after 1 month ≤ 500 MB |
| G8 | Three-axis decoupling preserved: state existence / cadence / perception subscription are independent | Toggle each axis via CLI flag; observe expected behavior (loaded but paused; loaded + computing but unsubscribed from new perception; etc.) |

## 2 · Non-goals (out of scope for v22)

- ✗ Multi-grid parallel (multiple Seed grids exchanging signals) — that's AiOT Direction α; v22 ships a single memory-domain grid only.
- ✗ Replacing α `memory_coactivation` table — v22 substrate sits **alongside** the SQL trace, not on top. Trace remains the audit log; substrate is the structural learner.
- ✗ Replacing or modifying `agent-bridge-seed` static `hub_clusters` / `near_keys` — those are v0.13.0 path-C semantic priors (different layer); v22 substrate is a parallel L2 mechanism, not a replacement.
- ✗ Cross-machine substrate consensus — first ship is single-node; cross-machine fork-and-rejoin deferred until single-node is solid.
- ✗ Modifying any existing CLI surface (`dream …`, `memory_*`, `palace serve`) — v22 introduces a new `substrate` subtree, never re-routes existing commands.
- ✗ LLM-driven anything inside v22 substrate. The substrate is pure mechanism (softmax-competition Hebbian learning). LLM consolidation stays at the L3 dream-replay layer.

---

## 3 · Architecture

### 3.1 The three layers, made explicit for v22

```
┌─────────────────────────────────────────────────────────────────┐
│ L3 — Recall / UI / hygiene                                       │
│      Palace viewer · canvas chat · dream {replay,stats,promote, │
│      identity,cluster-probe} · ζ-10 cron · embedding-stats       │
│      (P17–P24 shipped)                                           │
│                                                                  │
│      ↑ reads attention bias / topology                           │
└──────┼──────────────────────────────────────────────────────────┘
       │
┌──────┼──────────────────────────────────────────────────────────┐
│ L2 — **v22 substrate (NEW)**                                     │
│      One Seed grid, N=256, Warm tier @ 1 Hz + event-triggered   │
│      Receives memory events as perception                        │
│      Maintains connection_logits + in_strengths                  │
│      Periodic Parquet snapshot                                   │
│      Exposes neighbor / cofires-from-substrate queries           │
└──────┼──────────────────────────────────────────────────────────┘
       │  ← agent-bridge memory events as perception
       │
┌──────┼──────────────────────────────────────────────────────────┐
│ L1 — Substrate rules (REUSED from AiOT)                          │
│      Rust binary: softmax-competition learning + spawn/death     │
│      + Adam optimizer + RNG-seeded cross-machine determinism     │
│      (AiOT crate; shipped, 28 unit tests)                        │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Three-axis decoupling (Multi-Grid Foundations §5.5)

For v22's single grid, axes default as follows (overridable):

| Axis | Default | CLI override |
|---|---|---|
| State Existence | always loaded (eager, ~260 KB) | `--state-mode {loaded, persisted_only}` |
| Activation Cadence | Warm: 1 Hz baseline + event-triggered burst | `--cadence-hz N`, `--tier {hot, warm, cool, cold}` |
| Perception Subscription | full agent-bridge memory event stream | `--subscribe {memory_save, memory_get, memory_search}` subset |

These three are independent variables. Future multi-grid work needs them to vary per grid. v22 fixes them but the substrate API does NOT collapse them.

### 3.3 Perception pipeline (the bridge between L3 and L2)

```
agent-bridge memory event  (kind, key, content/query, ts)
    │
    ▼
encoder  (existing fastembed ONNX, 384-dim if MiniLM-L6-v2; deferred)
    │  cost: ~50 ms/event (dominant)
    ▼
projection  (linear layer 384 → D, where D ∈ [128, 192] per Q-back-1 PCA scree post 56;
              learned offline via SVD warm-start per Q6, see §11)
    │  ⚠ D ≠ N: D is the perception dim feeding each neuron; N=256 is the neuron count.
    │    Crate `z_states: [N][D]` confirms axes independent (post 51 Task A reviewer).
    │  D=128: 80.9% cum_var captured (min acceptable per scree on 659 active embeddings)
    │  D=192: 90.8% cum_var captured (recommended; sweet spot before diminishing returns)
    │  D=64 NOT recommended (62.9% cum_var, fails 80% threshold for memory-text domain;
    │  multigrid-foundations encoder memo §2 default D=64 was scoped to /proc telemetry,
    │  not text embedding — overridden by Q-back-1 measurement, post 56)
    │  cost: ~1 ms/event
    ▼
substrate_step(z: [f32; N])
    │  - softmax-competition over connection_logits
    │  - update in_strengths via Adam
    │  - spawn-on-surprise / death-on-low-strength per ADR-022/023
    │  cost: ~1 ms/event
    ▼
substrate state mutated in place
    │
    ▼
periodic snapshot to parquet (every K events or T seconds, whichever first)
    │  cost: ~10 ms/snapshot, amortized
```

Total per-event cost: ~62 ms with encoder dominating 80%. **Real event rate measured: ~57/day working (post-Q5 audit, forum post 50)**, much lower than the 244/day in Multi-Grid Foundations §Q6 (that figure was inflated by 2026-05-06 484-row skill bulk-import).

Refined cost calculation:
- ~57 events/day × (assume 30% fresh embed, 70% cache hit via existing `memory_embed_cache`) × 50ms = **~0.86 sec/day** encoder cost
- Substrate-step itself: 57 × 1 ms = 57 ms/day
- Snapshot writes: ~7/day × ~10 ms = 70 ms/day
- **Total CPU sustained**: < 1 sec/day = ~0.001% of one core

This is an order of magnitude under the §Q6 envelope. Substrate ship has zero compute risk at current event rate; even 10× growth stays trivially within budget.

**Cache reuse note**: substrate perception SHOULD share `memory_embed_cache` (already in `crates/bridge/src/hub.rs:32`, record-keyed `Vec<(MemoryRecord, Vec<f32>)>`). Reuse avoids duplicate ONNX inference for save/get events that already invoked semantic search.

### 3.4 Snapshot format (multi-window per γ finding 2026-05-13)

Per **AiOT γ audit** (forum #6 post 49, commit `775c341`): SVD on 5-feature `(instantaneous, derivative, window_{100,1k,10k})` gave effective rank=5 (σ_2/σ_1 = 0.78, well above 0.05 threshold). Although the deep reading attributes most independence to non-stationary drift rather than substrate-mechanism multi-axis, **both readings recommend the same v22 action**: snapshot at multiple timescales.

Final snapshot schema:

- Parquet file `~/.local/share/agent-bridge/substrate.parquet` (next to `state.db`)
- Columns per row (one row per snapshot cycle):
  - `step` (i64)
  - `cycle_ts` (i64 unix secs)
  - `n_alive` (i32)
  - `connection_logits` (flat f32 array, **N×(N-1)** — crate skips diagonal since neurons have no self-logit per post 51 Task A reviewer; **only on long-tier snapshots**, see below)
  - `in_strengths` (f32 array, N)
  - `last_perceived_key` (string array, N)
  - `last_perceived_ts` (i64 array, N)
  - **`trailing_surprise_mean_short`** (f32, mean over last 100 events) — new
  - **`trailing_surprise_mean_long`** (f32, mean over last 1000 events) — new
- Append-only with rotation: keep last 100 snapshots, then prune oldest
- SHA256 of last snapshot is the "substrate fingerprint" usable for cross-machine equivalence checks

**Multi-cadence write strategy** (synthesis of memo §11 Q5 + γ finding):

| Cadence tier | Trigger | What's written |
|---|---|---|
| Hot | Every 20 events (or per substrate step config) | metadata + `in_strengths` + `last_perceived_*` + trailing means (cheap row, no N×N matrix) |
| Long | Every 100-event multiple OR every 6h, whichever first | full row incl. `connection_logits` (the expensive N×(N-1) flat) |

Cost: hot row ≈ N×4 bytes + 2 floats ≈ 1 KB; long row ≈ N×(N-1)×4 bytes ≈ 260 KB. At our event rate (~57/day working), hot snapshots fire ≈ 3/day; long snapshots fire ≈ 4/day max (6h floor dominates). Total disk ≈ 1 MB/day = 365 MB/year (still well under the 5 GB/year G7 budget).

The two-cadence design fulfills γ's "drift detection on long window" + Hot's "per-event responsiveness", giving the actuator/retrieval layer access to both timescales without paying N² storage per event.

### 3.5 Substrate query API

```rust
trait MemorySubstrate {
    // Step once with a perception event. Substrate manages encoding +
    // projection + secondary-window buffer internally (per post 51 Task
    // A reviewer: real `DynamicGrid::step(primary, secondary, lr)` takes
    // two slices; we hide the secondary axis behind the trait).
    fn step(&mut self, event: PerceptionEvent) -> StepReport;

    // Read current state — no mutation, no access bump.
    fn neighbors_of(&self, key: &str, k: usize) -> Vec<(String, f32)>;
    fn snapshot(&self) -> SubstrateSnapshot;
    fn stats(&self) -> SubstrateStats;

    // Capability gate for ablation (G5).
    fn enabled(&self) -> bool;
}

// Single-event input to substrate. Mirrors the existing
// `QueryRecord` (used by `store.record_memory_query`) so the
// agent-bridge hook in mcp_tools.rs:4677-4679 can pass it through
// unchanged (post 52 Task B).
struct PerceptionEvent {
    pub kind: String,         // "save" | "get" | "search_fts" | …
    pub source: String,       // "mcp:memory_save" | "palace_viewer:click" | …
    pub key: Option<String>,  // resolved memory key when known
    pub query: String,        // the text to encode
    pub at: i64,              // unix secs
    // hit_count / duration_us elided — substrate doesn't need them yet
}
```

`neighbors_of(key, k)`: find the neuron(s) that fired highest on `key`'s most recent perception, return the **other keys** those neurons fired on recently with attention weights. This is the substrate's contribution to L3 retrieval — **topology, not content**.

---

## 4 · Falsifiable predictions

Each prediction has a clear decision rule including null result.

### P1 — Substrate produces internal modular structure within 30 days

After 30 days of normal use (244 records/day × 30 = 7 320 events), substrate `connection_logits` matrix exhibits **bimodal cross-correlation** between neuron pairs:
- Private cluster pairs at cos ≤ 0.1
- Shared/cofired pairs at cos ≥ 0.3

**Falsifiable**: if at day 30 the distribution is unimodal Gaussian around cos ≈ 0.1 (or any other flat shape), the substrate failed to develop modular structure → invariant #6 (bimodal cross-similarity, v10) does not generalize to memory-event perception. **Decision rule**: pause and re-design — maybe perception encoding is too noisy, or N=256 too small for this kind of input distribution, or projection layer needs different init.

### P2 — Substrate `neighbors_of(key)` correlates with α `cofires` edges

After 30 days, for each `key` that has at least 3 `cofires` edges in `memory_edges`:
- Spearman rank correlation between `substrate.neighbors_of(key, 20)` and α-graph `memory_neighbors_of_type(key, "cofires")` ≥ 0.4

**Falsifiable**: if correlation is near zero or negative, substrate is learning a different topology than the SQL trace — that's interesting but means substrate is NOT directly useful as attention bias for the existing retrieval queries. **Decision rule**: investigate which topology is "correct" by user feel (vision rule 1) before scaling further.

### P3 — Substrate attention bias improves cold-start frontier recall

The cold-start probe `research_drosophila_cold_start_misses_frontier_20260512` showed `Phase 2 #3 third slice` query returned the older 2nd-slice instead of today's 3rd-slice. After substrate is live for 14 days, re-run the same probe with `--use-substrate-bias`:
- Expected: substrate's `neighbors_of(query_centroid)` surfaces the recently-ingested 3rd-slice key in top-K

**Falsifiable**: if even with substrate bias the cold-start probe still misses, substrate is not solving the actual user pain. **Decision rule**: STOP and reconsider — maybe pattern completion (the energy-BFS over substrate output) is the missing piece, not substrate alone.

### P4 — Compute and memory envelopes hold

After 7 days continuous use:
- substrate worker thread CPU ≤ 1% sustained
- substrate.parquet on-disk ≤ 100 MB
- substrate RAM resident ≤ 5 MB

**Falsifiable**: if any of these blow past 2× the budget, v22's sizing is wrong for actual workload. **Decision rule**: re-derive sizing from observed event rate; consider downsizing N to 128, or rotating snapshot more aggressively.

### P5 — Snapshot determinism cross-machine

Same perception event log + same seed → SHA256-identical snapshot on aio2 and Mac.

**Falsifiable**: if SHA256 differs, the L1 binary's RNG seeding has a non-determinism leak. **Decision rule**: file as P1-bug against AiOT Seed crate's RNG layer; pause v22 ship.

### P6 — Null result: substrate provides no measurable retrieval improvement

If after 30 days P1+P2 pass but P3 fails (substrate has internal structure AND correlates with α, but doesn't help cold-start recall), the **null result decision** is:
- Keep substrate as observability layer (snapshot is a valuable "what is my agent learning?" artifact)
- DO NOT wire substrate into `memory_search` ranking (this would be optimizing against an unverified target)
- Re-direct downstream work to pattern completion v0 (energy BFS on L3, my earlier-recommended path) since substrate alone insufficient

---

## 5 · Vision-rule cross-check

| Rule | Check | Decision |
|---|---|---|
| 1 — "cold-start 更连续？" | P3 directly tests this | If P3 fails → null result per §4 P6 |
| 2 — "trigger 是数据" | α ratio currently 1.0 (insufficient by old criterion), BUT hairball finding is structural not density → trigger met by **different signal** (architectural gap) | OK to proceed; rule respected through different evidence |
| 3 — "种子改动走人审" | v22 is **new substrate**, does not modify existing `hub_clusters` / `near_keys` | OK |
| 4 — "可逆性是底线" | G5 ablation flag + substrate is alongside, not replacing | OK |
| 5 — "身份连续性是字面落地" | Substrate snapshot persists across cold-starts; identical seed → identical replay. Substrate IS a continuity mechanism. | OK; reinforced |

## 6 · Multi-Grid Foundations 7 invariants cross-check

| # | Invariant | v22 conformance |
|---|---|---|
| 1 | Parallel uniaxial grids + sparse cross-talk | v22 is **single grid** memory-domain; future grids cross-talk via signals; v22 does not preclude this |
| 2 | Inter-grid: exchange signals, NEVER weights | v22 exposes `neighbors_of`/`snapshot` — these are signals, not connection_logits raw export |
| 3 | L1/L2/L3 cleanly separated | §3.1 diagram makes this explicit |
| 4 | Eager loading by default | G2 says eager, ~260 KB; trivially holds |
| 5 | Grid dormancy = reduced cadence, NOT unload | G8 + §3.2 axis: dormancy = cadence drop, state stays loaded |
| 6 | Target bimodal cross-similarity (cos≈0.03 private / 0.3-0.5 shared) | P1 directly tests this |
| 7 | Three-axis decoupling | §3.2 + G8 |

All 7 hold for v22 design.

## 7 · Six anti-patterns (Seed state synthesis §"6 anti-patterns")

| # | Anti-pattern | v22 compliance |
|---|---|---|
| 1 | Optimizing against unverified targets | P1–P6 each include null-result decision rule |
| 2 | Conflating topology metric with capacity metric | v22 separates `n_alive` (capacity) from `connection_logits` (topology) explicitly |
| 3 | Mining internal observables for multi-axis | v22 is uniaxial substrate; multi-axis requires multi-grid (deferred) |
| 4 | Replacing FEP dynamics | v22 reuses AiOT Seed crate's L1 unchanged |
| 5 | Merging carrier weights | API exchanges signals only (`neighbors_of` returns keys + weights, not raw connection_logits) |
| 6 | Adding Rust complexity without tests | v22 implementation phase will require ≥ 5 unit tests per new module |

All 6 satisfied.

## 8 · Five preserved properties (Seed state synthesis)

| Property | v22 compliance |
|---|---|
| Thermodynamic/FEP dynamics | Reuse AiOT Seed crate verbatim — preserved |
| Softmax-competition connection learning | Reuse — preserved |
| Single-neuron prediction loss | Reuse — preserved |
| Spawn-on-surprise + death-on-low-strength | Reuse with ADR-022/023 Phase 5/6 — preserved |
| Cross-machine RNG-seeded determinism | Reuse with G4 + P5 cross-check — preserved |
| Read-only sidecar observer | Substrate is **alongside** retrieval, not a router — preserved |

---

## 9 · Cost estimate

| Phase | Work | Estimate |
|---|---|---|
| **设计 (this memo)** | Memo finalization + forum review cycle | ~1 day elapsed (today) |
| 协同认领 (forum thread #6) | Subtasks A-D from forum post (encoder API / event-source enum / N sizing rationale / fastembed-MiniLM confirmation) | 1-2 days, parallel |
| **实现 phase 1**: Rust crate integration | Pull AiOT Seed crate as dep / git submodule; wire perception pipeline; add CLI `substrate` subcommand; trait + impl | ~2-3 days |
| **实现 phase 2**: snapshot + replay determinism | Parquet schema; replay tool; cross-machine SHA256 check | ~1-2 days |
| **实现 phase 3**: `neighbors_of` query API + observability | Query API; `substrate stats` CLI; Palace footer line | ~1 day |
| **实现 phase 4**: 7-day dogfood + P1-P6 measurement | Live wet-test; collect data; either P3 pass → wire into retrieval, or P3 fail → null-result per §4 P6 | ~7 days elapsed |
| Total to first decision point | | ~2 weeks elapsed (much less actual work-time) |

## 10 · Decision rules for each gate

### Gate A — End of design phase
- Memo solid (peer review on forum thread #6 received)
- 7 invariants + 6 anti-patterns + 5 preserved properties all checked off
- → green-light implementation phase

### Gate B — End of implementation phases 1-3
- All G1-G7 tests pass (smoke + minimal dogfood)
- Cross-machine snapshot SHA256 match
- Substrate stats CLI shows healthy `n_alive ≈ 256` and reasonable connection_logits distribution
- → green-light 7-day dogfood

### Gate C — End of dogfood / P1-P6 measurement
- P1 + P2 + P3 all pass → **wire into retrieval bias** (becomes new minor version, like v22.1)
- P1 + P2 pass, P3 fails → **null result per §4 P6**, keep substrate as observability, redirect to pattern completion v0 on L3
- P1 or P2 fails → **substrate is wrong shape for this perception domain**; pause, re-design encoder/projection
- Any compute/memory budget blows up beyond P4 → **resize**; smaller N, slower cadence, more snapshot rotation
- Snapshot non-determinism (P5 fails) → file as AiOT crate bug, pause v22 ship

---

## 11 · Open questions for forum / collaboration

(Mirrored from forum thread #6, items A-D)

### Q1 — Perception interface shape (forum item A)
What `Vec<f32>` shape / batch semantics / async guarantees does the AiOT Seed `step()` expect? Currently AiOT crate has `step(z: &[f32])`; need confirmation about:
- expected dim (do they hard-code N? configurable?)
- batch vs single-event
- thread-safety guarantees

**Owner**: Mac node (closest to Seed crate).

### Q2 — Existing memory event hook points (forum item B)
Enumerate where in agent-bridge to tap into memory event stream. Candidates:
- `mcp_tools::MemorySave::execute` (write events)
- `mcp_tools::MemoryGet::execute` (read events)
- `mcp_tools::MemorySearch::execute` (search events — should we treat each query as one perception?)
- `mcp_tools::MemoryLink::execute` (relationship events)

**Owner**: any aio2 agent reading `crates/bridge/src/mcp_tools.rs`.

### Q3 — N=256 vs 128 vs 512 (forum item C)
Multi-Grid Foundations §Q6 specifies N=256 for the substrate target. Rationale was "~20 theme + ~100 concept specialists + headroom" given memory taxonomy distribution. Is N=128 sufficient given current 67% skill / 10% lesson distribution? Is N=512 wasted? Quantitative argument needed before locking.

**Owner**: ML-background agent or whoever has bandwidth to look at category histogram.

### Q4 — fastembed-MiniLM confirmation (forum item D)
Multi-Grid §5.6 §Q6 cost model assumes MiniLM at 50 ms/record. agent-bridge currently uses fastembed (ONNX). Is that the same model? Are the timing numbers reusable? If we're already running an embedding pipeline for `memory_search semantic`, can v22 piggyback on the same embedding cache?

**Owner**: agent familiar with current embedding stack (look at `crates/store/src/embedding.rs` or similar).

### Q5 — Snapshot cadence (RESOLVED 2026-05-13)

**Final answer** (per forum #6 post 49 γ-finding + post 50 event-rate measurement):

```
Hot tier   : every 20 events OR every 1800 seconds (30 min), whichever first
             — writes lightweight row (metadata + in_strengths + trailing means)
Long tier  : every 100-event multiple OR every 21600 seconds (6 h), whichever first
             — writes full row with N×N connection_logits
```

Two-cadence design is **directly informed by γ multi-window SVD result**: per-event snapshot alone misses ~80% of independent surprise variance discoverable at long windows. See §3.4 final schema.

Settled inputs:
- Real working event rate: **~57/day** (45 saves + 12 queries; bulk-skill-import excluded per Q5 audit post 50)
- Burst peak: 15 events/min over 7d window; 20-event hot trigger captures bursts naturally
- Long-tier 6h floor + 100-event multiple ensures drift detection regardless of burst timing

### Q6 — Initialization of projection layer
Zero-init then learn online (Hebbian-like)? Or zero-shot SVD over historical events to get a reasonable starting projection? Trade-off:
- Zero-init: pure substrate dynamics, but slow startup (takes many events to develop structure)
- SVD-warm-start: faster useful state, but introduces a "training step" violating the substrate-is-mechanism principle

Tentatively recommend zero-init to preserve mechanistic purity. Document and let dogfood data decide.

### Q7 — Perception source subscription scope (RESOLVED post 52)

Which `source` values in `record_memory_query` should feed substrate?

**Subscribed (Layer 2 perception)**:
- `mcp:memory_save` — write events (highest signal)
- `mcp:memory_get` — read events (attention signal)
- `mcp:memory_search` — query events (intent signal)

**Opt-out** (these are L3 phenomena, not raw perception):
- `palace_viewer:click` — UI navigation; already redundantly invokes `memory_get` inside `api_memory`, so substrate sees the underlying get not the click
- `mcp:memory_link` / `mcp:memory_consolidate` / `mcp:memory_compact` — meta-operations on graph structure, not first-class events
- Background tasks: `dream replay`, `dream promote`, `dream snapshot` — these READ memory but are internal hygiene, not user-driven perception

**Subscription is an axis (§3.2)**: per-source filter is configurable, default subscribes the 3-source set above. Future multi-grid setups may have different grids subscribe different source subsets (one grid for user perception, another for hygiene events) without architectural change.

### Q8 — Quantitative threshold for P3 (cold-start improvement) (RESOLVED — sharpened from earlier draft)

P3's original phrasing was qualitative: "expected: substrate's `neighbors_of(query_centroid)` surfaces the recently-ingested 3rd-slice key in top-K". Need a concrete success bar.

**Refined P3**:

Re-run the cold-start probe `research_drosophila_cold_start_misses_frontier_20260512` after 14 days substrate uptime. Define a fixed query set Q = {5 manual cold-start probes pulled from research memos}, where for each q ∈ Q, we know the "frontier hit" ground-truth key.

Substrate baseline: vanilla semantic search, no substrate bias.

Substrate-biased: re-rank top-50 semantic hits by `score' = score × (1 + α · substrate.neighbors_of(q, 50).contains_weight)` with α ∈ {0.2, 0.5}.

**Success criteria** (any one suffices):

| Metric | Baseline (today) | Substrate-biased threshold | Outcome |
|---|---|---|---|
| MRR@10 (mean reciprocal rank of frontier hit) | < 0.30 | ≥ 0.50 | P3 PASS |
| Recall@5 (frontier hit lands in top-5) | < 40% (2/5) | ≥ 60% (3/5) | P3 PASS |
| Time-to-frontier (cycles until any frontier hit fires) | unmeasured | < 3 cycles avg | secondary signal |

**Failure rule**: if both MRR@10 stays < 0.40 AND Recall@5 stays < 60% on substrate-biased after 14d uptime, **P3 FAILS** → §4 P6 null-result path activates, redirect to L3 pattern completion v0.

**Why 14d not 30d**: Q5 audit shows working event rate is ~57/day not 244/day. At lower rate, substrate needs ~14d to accumulate `n_alive ≈ 200` meaningful neurons. P1/P2 (structural) still measure at 30d; P3 (behavioral) measures earlier.

---

## 12 · File map (implementation reference — not yet code)

**Major revision per post 55** (Q-back-3 closure):
`crates/store/src/embedding.rs:36-61` already defines a pluggable
`EmbeddingBackend` trait + `set_default_backend()` global setter. The
substrate doesn't need a new crate scaffolded from scratch — it just
implements `EmbeddingBackend` and registers itself at startup. The
projection (384→D internal) is hidden inside the impl; the trait's
public `dim()` stays at 384 so the existing `embeddings` column and all
semantic-search code paths are untouched. This is **one-line wiring**.

```
agent-bridge/
├── crates/
│   ├── seed-bridge/                          # NEW crate (slimmer than original draft)
│   │   ├── Cargo.toml                        # dep: AiOT seed_neuron (git submodule or path-dep)
│   │   ├── src/
│   │   │   ├── lib.rs                        # SeedBackend impls ab_store::embedding::EmbeddingBackend
│   │   │   ├── grid.rs                       # Wrapper around AiOT seed_neuron::DynamicGrid
│   │   │   ├── projection.rs                 # 384 → D linear (SVD warm-start per Q6)
│   │   │   ├── perception_buffer.rs          # secondary rolling window (managed internally per post 51)
│   │   │   ├── snapshot.rs                   # Parquet read/write (two-cadence per §3.4)
│   │   │   └── replay.rs                     # Deterministic replay from event log
│   │   └── tests/
│   │       ├── smoke.rs                      # G1-G3 smoke tests
│   │       ├── determinism.rs                # G4 + P5
│   │       └── budget.rs                     # G6 + G7
│   ├── bridge/src/
│   │   ├── main.rs                           # +Cmd::Substrate { ... } CLI subtree
│   │   │                                     #   subcommands: stats / snapshot / replay
│   │   └── startup.rs                        # one-line: ab_store::embedding::set_default_backend(Arc::new(SeedBackend::new()))?
│   └── store/src/embedding.rs                # ALREADY has the trait + set_default_backend (post 55) — unchanged
└── docs/
    └── DESIGN-v22-agent-bridge-memory-substrate.md   # this file
```

**Note**: §3.5's `MemorySubstrate` trait is **agent-bridge-internal API**
(seed-bridge exposes neighbors_of/snapshot/stats for the v22 retrieval-
bias surface). The store-layer `EmbeddingBackend` is a separate, narrower
trait — same `SeedBackend` impl implements both, but the two concerns
stay typed-separate. `EmbeddingBackend` answers "give me 384-dim vector
for this text"; `MemorySubstrate` answers "show me the substrate's
topology".

## 13 · Vision review checkpoint

At every implementation gate, re-read vision soul file's "提醒" section:

1. "这让 cold-start 更连续了吗？" — answered by P3
2. β trigger is data, not calendar — substrate trigger is the **architectural gap** finding, satisfies the spirit (data informed)
3. seed changes go through人审 merge — v22 is alongside, not modifying static seed
4. all dream operations reversible — G5 ablation flag is the line
5. identity continuity is the literal goal — v22 substrate's snapshot replay IS a continuity mechanism

If at any gate the answer to (1) is "no, but the code is nice" — STOP, re-think.

---

## Appendix A — How v22 relates to the AiOT 5 directions (α-ε)

| AiOT direction | Status | Relation to v22 |
|---|---|---|
| α Multi-grid parallel | deferred (most expensive) | v22 is **one specific grid** of an eventual multi-grid; lays groundwork |
| β Sparse-K initialization | not started | Required prereq for N ≥ 1K; v22 starts at N=256 dense so not blocking |
| γ Long-snapshot aggregation | **SUPPORTED (drift-dominated)** — shipped commit `775c341` 2026-05-13 (forum #6 post 49); SVD effective rank=5 (σ_2/σ_1=0.78 ≫ 0.05); long-window means carry independent variance (drift-attributed but actionable) | v22 §3.4 snapshot schema **updated** to record `trailing_surprise_mean_{short,long}`; §11 Q5 **resolved** as multi-cadence (Hot 20-event/30min + Long 100-event/6h); cross-fed |
| δ External signal injection | not started (pairs with ADR-024) | Not directly related; v22 uses memory events as perception, AiOT δ uses raw /proc |
| ε Critical-period schedule | not started | Could compose with v22 — early grid life schedules higher spawn rate |

v22 unblocks no AiOT direction directly but **provides a parallel datapoint** about substrate behavior on a different perception domain (memory events vs `/proc` metrics).

## Appendix B — Why not just stay at SQL trace?

Three reasons SQL `memory_coactivation` is insufficient:

1. **No internal modular structure** — confirmed by `dream cluster-probe` hairball finding (all 28 nodes in 1 component). SQL trace has no spawn/death, no softmax-competition, no carrier dynamics; structure emerges only via dream-promote crystallization which is one-shot, not continuous.
2. **No bit-exact cross-machine replay** — SQL has timing-sensitive `last_at` columns; v22 substrate via L1 RNG-seed gives bit-exact reproducibility across aio2 and Mac.
3. **No persistent state separable from trace** — SQL trace mixes mutation events and current state. Substrate cleanly separates: events are append-only; substrate state is a derived first-class object that can be snapshot/restored/forked.

These are the same three reasons biology evolved hippocampus + neocortex as separate systems rather than relying on a single audit log.

---

**End of v22 design draft.**

Next action: forum thread #6 collects A-D subtask owners; reviewers post replies; if no blocking objections after 48h or all 7 invariants + 6 anti-patterns + 5 preserved-properties cross-check approved, advance to implementation phase 1.
