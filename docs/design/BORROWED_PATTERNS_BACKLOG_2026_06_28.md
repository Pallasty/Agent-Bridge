# Borrowed-Patterns Backlog — CascadeProjects cross-reference scan (2026-06-28)

> Successor to `BORROWED_PATTERNS_BACKLOG_2026_06_09.md`. Produced by a multi-agent
> survey→match→adversarial-verify→synthesize workflow over the 52-project
> `/Data/CascadeProjects` workspace, cross-referenced against the AB open-problem
> set (memory) and the borrowed-patterns kanban (forum thread #102).
>
> **Discipline (unchanged):** every borrow lands behind a **read-only / shadow surface
> + lswr gated-admission ladder**; never a direct runtime/substrate write. Python→Rust
> is **idea-level** unless noted; `biocortex-rs` (Rust, zero-dep) yields **code-level**
> borrows. Any borrow that duplicates a shipped AB capability is rejected.

## Scan outcome

11 source units surveyed (10 relevant), 6 targets, **29 candidates** → after adversarial
verification: **3 strong / 17 plausible / 5 weak / 20 reject** (45 verdicts incl. dup runs).
Two independently-produced syntheses (harvested-from-journal + the workflow's own synthesis
agent) **cross-validated with no contradictions**.

Every cited path/line below was confirmed on disk on 2026-06-28.

---

## Priority ladder

| P | Target | Item | Source | Kind | Lang fit | Effort |
|---|--------|------|--------|------|----------|--------|
| **P0** | T1 | Side-signal scorer sharpening (IDF-scaled key bonus + graded spike bonus) | `biocortex-rs/examples/ab_retrieval_side_signal_adapter.rs` | code | rust-direct | S |
| **P1** | T2 | INT8 row quantizer + recall-regression gate (ArrowQuant V2, kanban #106) | `vllm/.../tpu_int8.py`, `quant_utils.py`, lm-eval harness | code/idea | idea-cross-lang | S/M |
| **P2** | T8 | consolidate-latch + regrowth-cooldown (edge churn suppression) | `biocortex-rs/src/lib.rs` + `topology.rs` | code | rust-direct (port) | M |
| **P3** | T5 | Extend `seed-bridge/snapshot.rs` to memories table; AQFH schema ref + nexus schema-contract discipline | `AQFH/.../enhanced_memory_engine.py`, `nexus-civilization/.../arrow/schemas.py` | idea | idea-cross-lang | M |
| **P4** | T8 | connectivity-repair (stitch fragmented graph islands); graceful-forget; decay-regime A/B harness | `TCF/.../neural_plasticity.py`, `AIMemoryPalace_v2/.../adaptive_pruning.py`, `biocortex-rs/src/experiments/mod.rs` | idea | idea-cross-lang | M/S |
| **P5** | T7 | conservation/cascade/severity audit predicates (read-only, consume SEPL lineage — NOT a new gate chain) | `nexus-civilization/.../governance/compliance.py` | idea | idea-cross-lang | M |
| — | T4 | **Do not borrow.** AB already ships Syncthing version-vector merge | (operational fix only) | — | — | — |

---

## P0 — T1: retrieval side-signal scorer sharpening  (STRONG, rust-direct, S)

**Problem.** The BioCortex retrieval gate fails at the conservative blend: at `alpha=0.20`
the offline MRR lift is `+0.019` vs the required `+0.03` (`finding_biocortex_retrieval_side_signal_fails_gate_20260610`); it only passes at `alpha=0.80`. `runtime_adapter_approved` stays `false`.

**Root cause (verified on disk).** The side score is compressed into a narrow band, so under
the additive blend `blended = baseline_cosine + alpha*side` the side term adds nearly the same
constant to every candidate and barely changes rank. Two under-exploited levers in the scorer:

- `weighted_overlap_fraction` (L325-350): `weight = 1.0 + ln((N+1)/(df+0.5))` is a real BM25-style
  IDF, but the **key-field bonus is a flat `0.20`** (L341-346) regardless of term rarity.
- `score_candidate` (L102-156): the **spike bonuses are flat binary thresholds** —
  `0.20 if integration_spikes>0`, `0.08 if candidate_spikes>0` (L145-146).

**Edit (two levers, parameterized as named consts for tuning):**
1. **IDF-scale the key bonus** — `key_bonus = KEY_BONUS_BASE + KEY_BONUS_IDF_SCALE * (weight - 1.0)`
   so a *rare* query term matched in the candidate **key** (≈ doc identity) widens the right-doc gap.
2. **Grade the spike bonuses** — `integration_bonus = integration_spikes as f32 * INTEGRATION_STEP`,
   `candidate_bonus = candidate_spikes as f32 * CANDIDATE_STEP`, so the top candidate pulls clearly
   ahead instead of all firing candidates getting the same flat add.

**Why 0-regression holds.** The blend is additive-only and never subtracts; `overlap` only rises
for the right doc (denominator = Σweight is unchanged), and both the overlap fraction and the final
score are `.clamp/.min(1.0)`. Sharpening the expected doc's lead cannot by itself create a regression.
The +0.019→+0.03 gap is ~58% more separation, so **the offline gate decides deterministically** —
this is a tuning of a principled mechanism, not a per-query hack.

**Landing.** Pure-function edit inside the **read-only** example only (it is shelled out via
`--example`, NOT linked into AB runtime — `biocortex_shadow.rs:11781`). Honor biocortex-rs hard
constraints: zero-dep/std-only, `#![forbid(unsafe_code)]`, **determinism** (scorer already uses
BTreeMap/BTreeSet), validation triad before commit.

**Acceptance (pre-registered).** Run the gate over all **35** corpus queries at `alpha=0.20`:
require `coverage >= 0.80 && regressions == 0 && mrr_delta >= 0.03`. Keep `runtime_adapter_approved=false`.

**Reproduction:**
```bash
# 1) produce side signals from the (edited) read-only adapter
cd /Data/CascadeProjects/biocortex-rs
cargo run --release --example ab_retrieval_side_signal_adapter -- \
  /Data/CascadeProjects/agent-bridge/crates/bridge/tests/fixtures/biocortex_retrieval_gate_corpus.jsonl > /tmp/side.jsonl
# 2) run the deterministic offline gate (default hash backend, no onnx model needed)
cd /Data/CascadeProjects/agent-bridge
BIOCORTEX_RETRIEVAL_CORPUS=crates/bridge/tests/fixtures/biocortex_retrieval_gate_corpus.jsonl \
BIOCORTEX_RETRIEVAL_SIDE_SIGNAL=/tmp/side.jsonl \
  cargo run -q -p ab-bridge --example biocortex_retrieval_gate_eval
```

**Companion idea (plausible).** Per-query side-signal normalization (group rows by `query_id`,
min-max/z-score the scores before blending) — source `QNNs/src/core/memory/indexing.py:271`.
NOTE: stretching scores **changes rank**, so "0 regression" is NOT structural here — must be proven
by the same gate.

---

## P1 — T2: embedding quantization (ArrowQuant V2, kanban #106)  (3× PLAUSIBLE, idea-cross-lang)

AB stores each gte-768 embedding as a raw little-endian `f32[768]` BLOB
(`crates/store/src/vector.rs` `encode_embedding`/`decode_embedding`) = 3072 B/row, and has **no**
INT8/PQ/scalar quantizer anywhere in `crates/`. vLLM supplies a coherent triple:

1. **Per-row absmax INT8** — `vllm/vllm/model_executor/layers/quantization/tpu_int8.py:75`.
   ~10-line Rust `quantize_row_i8(&[f32;768]) -> (Vec<i8>, f32)`; 3072 B → **772 B** (768 i8 + 4 B
   scale) ≈ 3.96×. **Keep the `eps=1e-5` max-floor** (AB has all-zero hash-fallback rows → div-by-zero
   otherwise; `sqlite.rs:2303` `embedding_result_is_hash_fallback`).
2. **Group/zero-point upgrade math** — `.../quantization/utils/quant_utils.py:127` (symmetric vs
   zero-point branch + group reshape). Opt-in eval-only variant if row-wise absmax loses tail recall;
   AB is per-vector so reshape maps to e.g. 4 groups × 192. Drop torch `ScalarType`, hardcode n_bit=8.
3. **Recall-regression gate** — `vllm/.buildkite/lm-eval-harness/test_lm_eval_correctness.py:44`
   (`isclose(rtol=0.05)` vs frozen baseline, print-all-then-assert). Mostly overlaps AB's existing
   recall machinery (`recall_eval.rs` `AB_BASELINE_DB`, `biocortex_relevance_eval.rs`); the only new
   sliver is the per-metric rtol band — **extend** `biocortex_retrieval_gate_eval.rs`'s verdict struct.

**Landing.** New pure-fn `ab_store::quant` module beside `vector.rs`, **no write path**. First a
read-only **shadow drift-measurement surface** (mirror `embedding_dim_guard.rs` warn-only +
`biocortex_shadow.rs`): re-quantize a snapshot in memory, report projected byte savings + per-row
cosine drift, never mutate the f32 BLOB. A real INT8 column only after an lswr admission ladder
clears the recall gate.

---

## P2 — T8: consolidate-latch + regrowth-cooldown  (PLAUSIBLE, rust-direct port, M)

AB's `decay_coactivation_once` (`sqlite.rs:8107`) blindly halves `count` then `DELETE WHERE count<1`;
an important edge that dips during a quiet window is deleted, re-minted on next co-fire, and can be
re-pruned = **churn** (which also pollutes sync). No consolidation latch, no regrowth cooldown
(grep of `crates/store` = 0 hits).

Borrow biocortex's rule (`lib.rs:956-1038`): weight ≥ `consolidate_at_weight` latches
`consolidated=true` (immune to prune); below `prune_below_weight` prunes unless consolidated;
`add_structural_cooldown` blocks re-add churn; `MaturityProfile` (L396-431) = 3-tier escalating
thresholds/cooldowns.

**Caveats:** AB edges are **integer `count`, undirected**; biocortex weights are float — so the
thresholds (40.0/0.001) **cannot be copied**, only the rule shape; re-tune via the offline harness.
biocortex-rs is NOT an AB dep (the `biocortex-retrieval-shadow` Cargo entry is a *feature flag*) — so
**port** the latch+cooldown bool logic + 3 integer thresholds into `crates/store`, do not add a crate
dep. The score-decay arithmetic is idea-level only; the latch+cooldown bool is the code-level kernel.

**Landing.** First a pure churn-reduction eval over `Agent-Bridge-memory/memory_edges.jsonl`
(1017 edges) in `crates/bridge/examples/` (cf. `recall_eval.rs`), zero writes. Then add
`consolidated INTEGER NOT NULL DEFAULT 0` to `memory_coactivation` behind the lswr ladder;
`decay_coactivation_once` skips latched rows. Event-driven, never wall-clock.

---

## P3 — T5: columnar memory model  (STRONG schema-ref + PLAUSIBLE contract discipline)

**Key finding: AB already has a production arrow-rs v53 + parquet pipeline** —
`crates/seed-bridge/src/snapshot.rs` (currently stores substrate neuron logits, not memories). So the
external Rust template (`nexus city_schema`) is **rejected as duplicate**; the right move is to
**reuse/extend `snapshot.rs`** onto the memories table + embeddings.

- **Schema design reference (strong):** `AQFH/aqfh/core/enhanced_memory_engine.py:660-746` — a real
  PyArrow memory schema (memory_table + association_table) persisted as Parquet, with `pc.sort_indices`
  importance hot-preload. Two-table split maps onto AB's `memory.jsonl` + `memory_edges.jsonl`. Store
  embedding as `List<Float32>` (the T2 quantization seam); drop the `quantum_*` columns + JSON
  side-channels (use typed columns where dense).
- **Cross-language Arrow contract discipline (plausible):**
  `nexus-civilization/server/core/arrow/schemas.py` + `engine-rs/src/arrow_bridge.rs` — versioned
  schema metadata (`b"...version"`), written CONTRACT RULES (append-at-end / renamed-needs-bump /
  removed→reserved), consumer validates on open, field-asserting unit test. **Real gap:**
  `snapshot.rs::arrow_schema()` carries **zero** metadata/version today — this discipline closes a
  silent cross-language drift hole. Lands read-only, no admission gate of its own.

---

## P4 — T8: additional memory dynamics  (PLAUSIBLE)

- **connectivity-repair** — `TCF/src/core/neural_plasticity.py` `_optimize_topology`. AB detects graph
  components (`hebbian_clusters` Union-Find, `sqlite.rs:4304`) but has **no repair step**; orphan islands
  persist and `memory_neighbors_bfs` cannot cross a cut, degrading spreading-activation recall. Land
  `memory_connectivity_repair_candidates` (read-only JSON bridge-edge proposals, no write) via the
  `memory_related_keys_materialize` propose→review→materialize ladder. Pick bridges deterministically
  (highest-importance hub / shared tags), NOT randomly (the TCF `np.random` pairing is the anti-pattern).
- **graceful-forget** — `AIMemoryPalace_v2/.../adaptive_pruning.py:65` `_prune_node` redistributes a
  retiring node's mass to neighbors before archive. **Reconcile first:** AB's archive lives on the
  *wall-clock* `memory_decay_importance` path, and the durable-guard already spares edge-connected rows,
  so the benefit fires only on near-isolated nodes — quantify in shadow before promoting.
- **decay-regime A/B harness** — `biocortex-rs/src/experiments/mod.rs` event-vs-wall-clock decay
  comparison. AB has 3 decay regimes with no harness comparing them and a documented thread-97
  false-archive collateral. Offline `examples/decay_regime_eval.rs`, read-only.

---

## P5 — T7: provenance / controlled-RSI  (1 PLAUSIBLE; rest already-have)

**Key finding: AB already built the dry-run/admission/attestation machinery**
(`lswr_outcome_admission.rs`, `biocortex_shadow.rs` `boundary_payload()`), and the RSI design doc
explicitly warns "Goal C is a continuity honest ledger, **NOT another gate chain**". So the biocortex
`topology.rs` dry-run gate and attestation-flags borrows are **rejected as duplicates**.

Only net-new: the **three audit scenarios** from `nexus-civilization/server/core/governance/compliance.py`
— cascade-depth (runaway self-mod), severity-burst, and **conservation-leak** ("any runtime/config
delta with no lineage-traceable admitted entry ⇒ un-provenanced mutation"). Land as **read-only report
predicates that consume SEPL lineage**, in the Goal-C report-first loop / Falsifiers list — not as new
gates or MCP tools (the lane's own falsifier stops it if it "creates gates that do not feed a dashboard").

---

## T4 — sync/merge: do not borrow (operational fix only)

AB already ships and tests Syncthing-style causal merge: `crates/store/src/version_vector.rs`
(node→counter map + Concurrent detection), `sqlite.rs` `VersionVectorMerge` (concurrent →
non-destructive `<key>#conflict-<hash>`), and `sync.rs` already defaults to it. Every T4 candidate
(`Agent-Bridge-memory/sync.sh` branch fix, TTE/TCF conflict resolvers) was **rejected** — duplicate, or
weaker LWW than AB's preserve-both. The repeated-sync-failure alert (`alert-sync-failing-aio2`) is most
likely **operational churn** (every export rewrites the full ~29 MB `memory.jsonl` → a commit nearly
every run → concurrent-push contention), not a merge-algorithm gap.

**Action (not a borrow):** confirm the *deployed* `sync.sh` uses `version_vector_merge`, and cut the
full-snapshot-per-export churn.

---

## Provenance

- Full per-candidate adversarial verdicts (existence confirmation, line numbers, blockers):
  workflow run `wf_1e9f3911-c52`.
- Open-problem inputs: `finding_biocortex_retrieval_side_signal_fails_gate_20260610`,
  `finding_biocortex_hard_holdout_pass_20260610`, `mac_continuity_report_embedded_zero_diagnostic_20260627`,
  `alert-sync-failing-aio2-1780381829`.
- Kanban: forum thread #102 (AB borrowed-patterns landing kanban); #106 (ArrowQuant V2).
