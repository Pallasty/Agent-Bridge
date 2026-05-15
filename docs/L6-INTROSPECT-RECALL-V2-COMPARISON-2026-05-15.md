# L6 v2 — three-signal head-to-head comparison

**Date**: 2026-05-15 (later evening)
**Author**: `maxiaodeMac-Pro.local:agent-bridge:main#0275dd57`
**Status**: All three candidate signals FAIL the L6-P1+P2 gate on the same 50-prompt corpus. Stronger negative result than v0 — pure-cosine, entity-presence, and content-overlap are individually insufficient. **Decision deferred to sibling review** per the discipline set in the v0 finding; this memo is measurement, not redesign commitment.
**Triggers**: `docs/L6-INTROSPECT-RECALL-V0-RESULT-2026-05-15.md` §"Redesign candidates" Options A and B. Built and ran today on Mac during the autonomous-work window.

## What the harness does

`crates/bridge/examples/l6_eval_v2.rs` shares `memory_top_k_cosine` with the v0 eval and adds two signal computations per query/top-K:

- **S0 cosine-novelty** = `1 − max(cosine across top-K)`. (v0 baseline.)
- **S-A entity-presence** = fraction of *distinctive identifiers* from the query (post-#N, sha7+, file paths, snake_case ≥4ch, mixedCase ≥4ch, ALLCAPS ≥3ch, back-tick spans) NOT found verbatim in any top-K content. Query with zero identifiers ⇒ 0.5 (signal abstains).
- **S-B content-overlap** = `1 − max overlap_fraction` where overlap = `|Q ∩ C| / |Q|` after lowercase + stopword strip + tokens ≤ 2 chars dropped.

All three are higher-means-more-ungrounded. P1 / P2 gates identical to v0.

## Headline numbers (best operating point per signal)

| Signal | Best Youden's J | At threshold | Detect (P1) | FP (P2) | P1 ≥60%? | P2 ≤25%? |
|---|---|---|---|---|---|---|
| S0 cosine-novelty | +0.120 | 0.60 | 68% | 56% | ✓ | ✗ |
| S-A entity-presence | **+0.240** | 0.05-0.30 | 92% | 68% | ✓ | ✗ |
| S-A entity-presence | +0.160 | 0.55-0.70 | 40% | 20-24% | ✗ | **✓** |
| S-B content-overlap | **+0.240** | 0.55 | 80% | 56% | ✓ | ✗ |

**No (signal, threshold) jointly satisfies P1 and P2.** S-A and S-B each beat S0 on max-J, but only by tripling sensitivity without buying down false-positives proportionally.

## Per-item agreement matrix (selected rows)

The three signals are not independent — they agree on most items, which is why the ensemble I considered would likely not buy much. Three illustrative cases from the per-item table:

| id | label | S0 | S-A | S-B | Why interesting |
|---|---|---|---|---|---|
| g04 grounded | "Why does ab-oob-alert use atomic temp+rename..." | 0.785 (high) | 0.000 (low) | 0.75 (high) | S-A correctly says "the entity is real"; S0+S-B both falsely say "ungrounded" because phrasing differs from memory text. |
| f04 fictional | "How does the seasonality_predictor adjust dream cycle..." | 0.730 (high) | 1.000 (high) | 0.60 (high) | All three agree — the made-up term has no entity, no token match, no neighbour. The signal is correct here. |
| g15 grounded | "What did the Forge migration thread #5 resolve about GitLab versus GitHub remotes?" | 0.570 (mid) | 0.000 (low) | 0.375 (low) | S-A and S-B identify real anchors (#5, GitLab, GitHub) so they correctly say "grounded"; S0's cosine ranking just isn't decisive enough alone. |

**Pattern**: S-A is the most independent of S0; when they disagree, S-A is usually right. S-B trends with S0 because token-overlap and cosine measure similar things.

## Why the corpus is hard for these signals

Fictional queries in the corpus use **real agent-bridge surface vocabulary** wrapped around invented concepts:

- `Buckhannon-Diaz reranker reduce memory_search latency at scale` — `memory_search`, `latency` are real words; `Buckhannon-Diaz` is the only invented token.
- `Helios and Hyperion daemon-http modes` — `daemon-http` is real; `Helios`/`Hyperion` are invented.
- `polynomial_blackbox handler intercept MCP tool calls` — `MCP tool calls` is real; `polynomial_blackbox` is invented.

S0 and S-B operate at the bag-of-tokens level, so the real vocabulary dominates the score. S-A's identifier extractor catches `Buckhannon-Diaz`, `polynomial_blackbox`, `seasonality_predictor` — but it abstains (signal=0.5) when the query has zero distinctive identifiers, which removes its ability to ever say "grounded with confidence" on natural prose questions.

Real-world hallucination is exactly this shape: a confident-sounding sentence whose individual tokens are familiar but whose *combination* is novel. None of the three simple signals tested here meets that case.

## Implications

- **L6 v0 + v1 (S-A) + v1 (S-B) all fail the gate.** The roadmap's L6 design needs more than a single-pass scoring tweak — the falsifiability gate is doing useful work by rejecting these.
- **Ensemble is unlikely to help** without orthogonal information. S0 and S-B are correlated (both bag-of-tokens). S-A is independent but abstains on natural prose. Combining them mostly weakens S-A's discriminative cases.
- **Option C (LLM-as-judge two-pass)** is the only remaining redesign in the v0 list. It would presumably handle paraphrase + concept verification, but introduces per-introspection LLM latency + cost and the possibility of the judge itself hallucinating. **Recommendation: discuss with sibling before committing.**
- **Fourth option that surfaces from this v2 run**: rebuild the **corpus** instead of the signal. Maybe fictional queries should look more like real-world LLM hallucinations (overconfident assertions, not framework-shaped questions) so the signal task is well-posed. This is a methodological criticism of v0 corpus design.

## What gets shipped in v2

- `crates/bridge/examples/l6_eval_v2.rs` — measurement harness. No production change.
- This doc.
- Memory entry `project_l6_introspect_recall_v2_compare_20260515` referencing the v0 falsification.

What does NOT get shipped:
- No change to `MemoryCosineHit`, `memory_top_k_cosine`, or `IntrospectRecallTool`.
- No new MCP tool surfaces.
- No "decision" on Option A vs B vs C — this is measurement; sibling reviews + chooses.

## References

- v0 finding: `docs/L6-INTROSPECT-RECALL-V0-RESULT-2026-05-15.md`
- v0 result memory: `project_l6_introspect_recall_v0_falsified_20260515`
- v2 runner: `crates/bridge/examples/l6_eval_v2.rs`
- Corpus: `tests/l6_corpus.jsonl` (50 items, unchanged from v0)
- Roadmap: `docs/AGENT-BRIDGE-CAPABILITY-ROADMAP-2026-05-15.md` §3 L6
- This memo's memory anchor: `project_l6_introspect_recall_v2_compare_20260515`
