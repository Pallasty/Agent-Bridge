# PROBE — A1 DRIFT_THRESHOLD calibration result

**Date**: 2026-05-17
**Author**: `maxiaodeMac-Pro.local:agent-bridge:main#0275dd57`
**Parent design**: `docs/DESIGN-A1-B1-B3-RECALL-TIMING-v0.md` §10 Q1
**Status**: probe finding — drift primitive de-risked; A1 design needs reframe before act

---

## TL;DR

ONNX MiniLM cosine drift **cannot cleanly separate same-topic from cross-topic memory pairs** on the agent-bridge corpus. Best Youden's J is at THRESH=0.20 with FP=67% / recall=100% — gap only 33pp. The originally-proposed `DRIFT_THRESHOLD=0.45` has no empirical basis on this corpus.

**Decision implication**: A1 intervention should ship in v0 with **cooldown-only re-fire** (no drift signal), and treat semantic drift as Phase 2 contingent on a real prompt-corpus probe (memory pairs are an imperfect proxy for prompt-prompt distance).

---

## 1 · Probe design

- **Corpus**: 670 active memories with ONNX MiniLM (D=384, normalized) embeddings stored in `state.db`.
- **Sampling**: 8 thematic groups via key-pattern LIKE filter (palace_viewer, codebase_imports, codebase_calls, l6, audit_gap, sync, tombstone, canvas_chat). Yields 21 same-topic pairs (within-group) + 21 cross-topic pairs (between-group, 1 random pair per group-pair).
- **Metric**: drift = `1 - cos(emb_a, emb_b)`. Embeddings already L2-normalised so cos = dot product.

## 2 · Results

### Distribution

| Percentile | Same-topic drift | Cross-topic drift |
|---|---|---|
| P10 | 0.000 | 0.492 |
| P25 | 0.000 | 0.889 |
| P50 | 0.647 | 0.985 |
| P75 | 0.978 | 1.000 |
| P90 | 1.000 | 1.043 |
| mean | 0.588 | 0.877 |

### Threshold sweep (Youden's J)

Best operating point: **THRESH=0.20**, FP=67%, recall=100%, J=+0.33.

At the originally-proposed 0.45: FP and recall both saturate badly because same-topic distribution is bimodal (cluster at 0 + cluster at 0.65+), and cross-topic stays above 0.49 in most cases.

## 3 · Why the proposed threshold fails

Two confounding signals in the corpus:

1. **Same-topic is bimodal**: some intra-cluster pairs are near-duplicate (drift ~0.00 — e.g. templated alert memories that share boilerplate), while other intra-cluster pairs are about the same project but from different angles (drift 0.6-1.0).
2. **Long-content truncation**: most memories tested were 700-3000 chars (multi-screen markdown), truncated to ONNX's 512-token input. The resulting embeddings reflect the truncated prefix, not the full content. **This is not a good proxy for prompt-prompt drift** — real user prompts are typically 50-500 chars and never truncated.

The probe cannot answer "is 0.45 the right threshold for prompt drift?" from this corpus. It can answer "does drift on memory pairs cleanly separate same/cross? **No.**"

## 4 · Decision

| Option | Choice |
|---|---|
| Lock DRIFT_THRESHOLD=0.45 anyway | ❌ no empirical support |
| Re-tune to optimal Youden (0.20) | ❌ FP=67% is unacceptable for context-budget impact |
| Drop drift, keep cooldown-only | ✅ **chosen for A1 v0** |
| Pivot to keyword-overlap drift (FTS5 jaccard) | 🟡 backup option for Phase 2 |
| Pivot to LLM-judged drift | ❌ L6 three FALSIFIED ships warns against this |

## 5 · Impact on parent design

`DESIGN-A1-B1-B3-RECALL-TIMING-v0.md` revisions needed before act phase:

| Section | Original | After probe |
|---|---|---|
| §2.1 prompt-embedding diff primitive | proposed shared cosine drift | **deferred** — Phase 2 only after prompt-corpus probe validates |
| §2.2 A1 re-fire gate | cooldown OR drift | **cooldown only** in v0 (`COOLDOWN_TURNS=8`) |
| §5 P-A1 predicate | recall lift via drift-triggered injection | recall lift via cooldown-triggered injection (threshold semantics unchanged) |
| §10 Q1 | "Is 0.45 defensible?" | **answered: NO** — drift dropped from v0 |

B1 (digest block) and B3 (preflight cosine on save-time content) are **unaffected** by this probe — they don't use prompt-prompt drift. B3 cosine is content-content on similar-shape saved memories, a much cleaner case. B3's REDO_THRESHOLD=0.75 still needs its own calibration but on a different corpus (same-kind-same-project pairs).

## 6 · Follow-up probes

1. **Real prompt-corpus probe** (needed before A1 Phase 2): collect 30-50 actual user prompts from session logs, embed inline, measure prompt-prompt cosine for same-task vs cross-task pairs. Defer to post-A1-v0-ship.
2. **B3 REDO_THRESHOLD calibration** (needed before B3 ship): same-kind-same-project pairs only, target >50pp Youden gap. ~30 min.

## 7 · Discipline frame

- §6.5 rule 2 working as designed: locked thresholds force calibration **before** ship, not after. This probe is exactly the rule-2 calibration step.
- §6.5 rule 3 nascent: drift primitive is one failed dimension (memory cosine) — falls back to a different dimension (cooldown turn count), not "tune the same dimension lower". Same logic L6 Option E used (reframe orthogonal dim).
- Verify-design-act discipline confirmed: probe ran BEFORE any code change. Cost: 30 min Python. Saved: shipping a primitive that would FALSIFY P-A1 in dogfood.

## 8 · Probe artifact

Probe script content lives in this session's bash log (not committed — pure Python). Reproducible: connect to `state.db`, sample by key-pattern LIKE filter, decode `embedding BLOB` as little-endian float32 × 384, compute dot products.

## 9 · Cross-link

- Parent design: `docs/DESIGN-A1-B1-B3-RECALL-TIMING-v0.md`
- Forum cross-check thread: design thread #10 post #216
- L6 dimension-reframe precedent: `docs/L6-OPTION-E-FALSIFIED-2026-05-16.md` (rule-3 first use)
- ONNX backend config: `crates/seed-bridge/src/embedding.rs` (`build_inner_backend()`)
