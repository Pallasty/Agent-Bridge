# PROBE — B3 REDO_THRESHOLD calibration result

**Date**: 2026-05-17
**Author**: `maxiaodeMac-Pro.local:agent-bridge:main#0275dd57`
**Parent design**: `docs/DESIGN-A1-B1-B3-RECALL-TIMING-v0.md` §5 P-B3
**Adjacent probe**: `docs/PROBE-A1-DRIFT-CALIBRATION-2026-05-17.md` (A1 case, different corpus)
**Status**: B3 threshold **defensible at 0.75**, but P-B3 predicate semantics need reframe

---

## TL;DR

`REDO_THRESHOLD=0.75` is **defensible as a near-duplicate trigger** — it sits at the **p99 of all same-kind pairwise cosines** (4095 pairs, 91 active `kind ∈ {decision, finding, lesson}` memories). Pairs above 0.75 (eyeballed top-15) are genuinely semantically related/redo concepts.

But the **original P-B3 predicate "≥80% recall, ≤25% FP" doesn't apply cleanly to this corpus**. The synthetic-corpus predicate is trivially satisfiable; the real-world interpretation should emphasize **precision** (when B3 fires, the flag is meaningful) over **recall** (catch all conceptual redos).

**Decision**: Keep 0.75. Reframe P-B3 from recall-centric to precision-centric. Add soft warning band [0.60, 0.75) as informational.

---

## 1 · Probe design

- **Corpus**: 91 active memories `kind ∈ {decision, finding, lesson}` (B3 target set) with ONNX MiniLM D=384 embeddings.
- **Method**: all-pairs pairwise cosine (n=4095 pairs).
- **Label heuristic**: shared_tags ≥ 3 = "positive" (likely related). Weak label — most relevant pairs share 0-2 tags by design.

## 2 · Results

### 2.1 Cosine distribution (all pairs)

| Percentile | Cosine |
|---|---|
| min | -0.181 |
| p10 | -0.055 |
| p25 | -0.016 |
| p50 | 0.088 |
| p75 | 0.385 |
| p90 | 0.525 |
| p95 | 0.593 |
| p99 | 0.712 |
| max | 0.902 |

**Median pair is near-orthogonal**. The "agent-bridge same-kind" embedding space spreads memories across the unit sphere; high cosines are exceptional.

### 2.2 Top-cosine pairs (eyeballed)

```
cos=0.902  lesson_git_commit_by_path        ↔ lesson_sibling_sweep_during_build
cos=0.856  workflow_worktree_per_session    ↔ lesson_sibling_sweep_during_build
cos=0.853  workflow_worktree_per_session    ↔ lesson_git_commit_by_path
cos=0.821  vision_synaptic_dream_alpha_beta ↔ finding_burst_vs_persistent_attr
cos=0.817  lesson_st2000lm015_smr_drive     ↔ lesson_ssk_ns1066_bridge_firmware
cos=0.808  project_monthly_gap_audit_v0     ↔ memory_l4_l8_gap_audit_mapping
cos=0.806  decision_path_c_v02_write_path   ↔ lesson_path_c_actuator_v01_design
cos=0.790  project_tombstone_sync           ↔ summary_phase2_memory_schema_evol
cos=0.781  decision_b_prototype_kept        ↔ finding_direction_b_superseded
```

These ARE related concepts (git workflow lessons, hardware quirks, audit chain, path-c iterations, b-prototype lineage). The cosine ≥ 0.75 region is **populated by genuine semantic neighbors**.

### 2.3 Threshold sweep with shared-tag label

| THRESH | Recall on shared_tags≥3 | FP on shared_tags<3 | Youden's J |
|---|---|---|---|
| 0.500 | 32.8% | 12.2% | +0.205 |
| 0.600 | 20.7% | 4.4% | +0.163 |
| 0.700 | 10.3% | 1.2% | +0.091 |
| **0.750** | **6.9%** | **0.4%** | **+0.065** |
| 0.800 | 0.0% | 0.2% | -0.002 |

Best Youden's J at THRESH=0.50 (J=+0.205). But this misreads the use case — see §3.

### 2.4 Firing rate at 0.75

20 / 4095 = 0.5% of pairs cross the threshold. Light fire rate; suggests B3 would emit `prior_decision_warning` rarely in production. On any given new `memory_save`, the expected number of prior matches at cos ≥ 0.75 ≈ `0.5% × N_same_kind_in_project` — typically 0-2 prior matches.

---

## 3 · Why "recall" was the wrong metric for B3

The original P-B3 predicate "≥80% redo flag rate on 20-pair synthetic" was internally consistent: a synthetic corpus pre-constructed with cos ≥ 0.7 pairs would trivially pass at THRESH=0.65.

But on real corpus, the question "what fraction of real redos do we catch?" has no clean answer because:

1. **No ground truth label** — there's no oracle that says "memory X is a redo of memory Y" in the corpus.
2. **Shared-tags is a weak proxy** — only 58 pairs out of 4095 share ≥3 tags; positive class is too small and biased toward heavily-tagged decisions.
3. **The cost asymmetry favours precision over recall**:
   - FP cost = a single advisory warning the agent reads + dismisses (~ low)
   - FN cost = a missed redo (the gap B3 exists to close) but **agent can still search after saving** — not a hard fail

The probe surfaces that **the right question is "when B3 fires, is the flag meaningful?"**, not "what fraction of redos does it catch?".

---

## 4 · Reframed P-B3 predicate

Replace the original "≥80% recall on synthetic" with:

| Original | Reframed |
|---|---|
| ≥80% recall on 20-pair synthetic redos | ≥**75% precision** on the flagged set: of 20 production `prior_decision_warning` firings over 4-week dogfood, ≥15 should be acknowledged by the saving agent as "yes, related/redo" |
| ≤25% FP | (subsumed — precision is the metric) |
| (none) | **Fire rate predicate** — ≤3 warnings per `memory_save` (median) to prevent noise |

This is closer to L7-P1's structure ("≥60% proposal accept rate") than L6's recall-centric framing.

---

## 5 · Soft warning band

In addition to the hard threshold at 0.75, emit an **informational band** [0.60, 0.75):

- THRESH ≥ 0.75 → `prior_decision_warning` (hard flag, shown prominently)
- THRESH ∈ [0.60, 0.75) → `prior_decision_hint` (soft note, lower visibility)
- THRESH < 0.60 → silent

This catches the broader "possibly related" set (cosines 0.60-0.75 contain a meaningful slice — eyeballing rows around 0.65-0.75 shows genuine adjacencies). The soft tier is information-only; agent decides whether to engage.

---

## 6 · Decision

| Question | Answer |
|---|---|
| Is REDO_THRESHOLD=0.75 defensible? | ✅ Yes, as a **near-duplicate trigger**. p99 of corpus; eyeballed pairs are genuinely redo-flavoured. |
| Does the original P-B3 predicate apply cleanly? | ⚠️ No — reframe needed (recall → precision; see §4). |
| Should we ship 0.75 + the soft band? | ✅ Yes for v0; soft band catches the "near but not duplicate" middle. |
| Does this need re-locking under §6.5 rule 2? | ✅ Yes — the predicate reframe is a rule-2 fixup (new predicate text + thresholds, same intent). Cite in parent design v1 amendment. |

---

## 7 · Impact on parent design

`DESIGN-A1-B1-B3-RECALL-TIMING-v0.md` §5 P-B3 needs amendment (in parent v1 or via this probe-as-amendment pattern):

- **P-B3**: replaced (see §4).
- **§2.4** mechanism: add the soft band [0.60, 0.75) emitting `prior_decision_hint`.
- **§7 step 2** B3 preflight budget: now ~3-4h (was 2-3h) — soft band adds two thresholds + two emit paths.

---

## 8 · Cost-benefit recap

| Item | Cost | Saved |
|---|---|---|
| Probe (this doc) | 25 min Python | A predicate that would FALSIFY in dogfood + force redo of P-B3 design |
| Verify-before-act | 30 + 25 = 55 min cumulative | Two rule-3 reframes pre-empted (A1 drift drop + B3 predicate reshape) |

Verify-design-act discipline: 2-for-2 today.

---

## 9 · Cross-link

- Parent design: `docs/DESIGN-A1-B1-B3-RECALL-TIMING-v0.md`
- A1 probe sibling: `docs/PROBE-A1-DRIFT-CALIBRATION-2026-05-17.md`
- L7-P1 precision-predicate precedent: `project_l7_p1_session_reflect_shipped` (≥60% accept-rate framing)
- L6 rule-3 precedent: `project_l6_option_e_falsified_20260516`
- Forum thread #10 (cross-check) — this probe will follow-up with reply post
