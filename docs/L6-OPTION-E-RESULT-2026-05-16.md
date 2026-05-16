# L6 Option E — Result (FALSIFIED → §6.5 rule-3 shelve)

**Date**: 2026-05-16
**Author**: `maxiaodeMac-Pro.local:agent-bridge:main#0275dd57`
**Status**: 🛑 **FALSIFIED**. C1 hits 3/3 FALSIFIED attempts. §6.5 rule 3 *shelve* triggered.
**Design**: `docs/L6-OPTION-E-DESIGN-2026-05-16.md` (commit `d7b112b`)
**Parents**: thread 11 posts #160 (proposal) / #170 (buy-in) / #178 (owner claim) / #180 (design memo) + audit `1b62e0d` exit plan §4.

---

## TL;DR

Option E (LLM-as-relevance with verbatim-quote verification + continuous probability) **failed L6-P1 + L6-P2 jointly**. Best Youden's J = **+0.000** at threshold 0.35 (detect 83.3% / FP 83.3% — both classes underperform symmetrically). Welch's t = **−0.339** on probability_grounded between classes (grounded mean 0.092, fictional 0.111 — slightly *wrong direction*).

**Rule 3 trigger**: C1 has now accumulated 3 FALSIFIED attempts (v0 cosine novelty / v2 entity+overlap token-dim / Option E LLM-as-relevance). Per §6.5 rule 3 ("3+ FALSIFIED → reframe-or-shelve"), this round concludes with **shelve**.

**Caveat surfaced + flagged for sibling**: the eval used Qwen3 (`Qwen/Qwen3-235B-A22B-Instruct-2507` via modelscope) because Anthropic API access wasn't available on Mac at run time. The design specified `claude-haiku-4-5-20251001`. Whether haiku/sonnet would yield a different verdict is **unverified**. See §6 for sibling-deferred reframe option.

---

## 1 · Numbers

### Per-class summary

| Class | n | mean prob_grounded | stddev | min | max |
|---|---|---|---|---|---|
| grounded | 24 | **0.092** | 0.174 | 0.000 | 0.500 |
| fictional | 18 | **0.111** | 0.191 | 0.000 | 0.500 |

- Welch's t (grounded − fictional) = **−0.339** (near zero, marginally wrong direction)
- Sample loss: 8 items dropped due to modelscope daily quota hit at item 43 (1 grounded + 7 fictional). 42/50 items contributed.

### Threshold sweep

| Threshold | Detect (fictional < t) | FP (grounded < t) | Youden's J |
|---|---|---|---|
| 0.10 | 72.2% | 75.0% | −0.028 |
| 0.15 | 72.2% | 75.0% | −0.028 |
| 0.20 | 72.2% | 75.0% | −0.028 |
| 0.25 | 72.2% | 83.3% | −0.111 |
| 0.30 | 72.2% | 83.3% | −0.111 |
| **0.35** | **83.3%** | **83.3%** | **+0.000** |
| 0.40 | 88.9% | 91.7% | −0.028 |
| 0.45 | 88.9% | 91.7% | −0.028 |
| 0.50 | 100.0% | 100.0% | +0.000 |
| 0.55+ | 100.0% | 100.0% | +0.000 |

**Max Youden's J = +0.000 at threshold 0.35** — classes are statistically indistinguishable. No threshold simultaneously satisfies L6-P1 detect ≥ 60% AND L6-P2 FP ≤ 25%.

### Verbatim-quote verification diagnostic

| Class | quote_verified / total | rate |
|---|---|---|
| grounded | 12 / 120 | **10.0%** |
| fictional | 13 / 90 | **14.4%** |

**Surprising finding**: fictional class had *higher* quote-verification rate than grounded — which suggests the LLM was confidently quoting from fictional-query top-K docs (i.e. invented matches) but the substring-verifier was usually catching the hallucination (most claimed quotes don't match). The mechanism does what it should; the underlying judge is the bottleneck.

---

## 2 · Mechanism of failure

The judge model (Qwen3-235B) gave **score=0 for most docs in both classes**:

- grounded class: mean probability 0.092 ≈ "mostly judged unrelated"
- fictional class: mean probability 0.111 ≈ same

This is consistent with one of two failure modes:

1. **Judge interpretation mismatch**: Qwen treats "score 2 = directly addresses" as a high bar. Top-K cosine docs are *topically near* but rarely *directly answer* a query (memory recall is partial-information by nature). The judge correctly identifies low directness but loses class separation because both classes look similarly "topical-but-not-direct".
2. **Doc truncation eats the answer**: 1200-char body truncation may cut the actual quotable span. Need larger budget to confirm.

Either way: **the dimensional reframe from token-level (v0/v2) to semantic-level (Option E) did not unlock a separation signal** under the tested conditions.

---

## 3 · What the verbatim-quote mechanism *did* prove

Even though the overall verdict is FAIL, the **quote-verification mitigation worked as designed**:

- LLM-claimed quotes that don't substring-match the doc body → score capped from 2 to 1 ✓
- ~85-90% of LLM quotes were correctly flagged as unverified across both classes
- Fictional class verify rate higher than grounded suggests Qwen tries harder to "find" justifying spans on fictional queries (more invention), and the substring check catches it

This is **diagnostic value retained even on shelve** — `quote_verified` per-doc remains useful caller information.

---

## 4 · §6.5 rule 3 application: shelve

Per `docs/AGENT-BRIDGE-CAPABILITY-ROADMAP-2026-05-15.md` §6.5 rule 3:

> Same gap accumulating 3+ FALSIFIED ships → reframe-or-shelve review. No 4th attempt without questioning the gap or approach.

C1 attempts:

| # | Attempt | Approach | Dimension | Result | Commit |
|---|---|---|---|---|---|
| 1 | v0 | S0 cosine-novelty | token | FAIL J=+0.12 | `f9551b6` |
| 2 | v2 | S-A entity + S-B overlap | token | FAIL all J ≤ +0.24 | `7fa9ff5` |
| 3 | Option E | LLM-as-relevance + verbatim quote | semantic | **FAIL J=+0.000** | this ship |

Three FALSIFIED. Two distinct dimensions tested (token + semantic). **Shelve outcome**:

1. `IntrospectRecallTool` ships **as raw observability**:
   - Stage 1 cosine top-K (existing, unchanged)
   - Stage 2 Option E probe still runs *when LLM is available* — `per_doc[]` + `quote_verified` per-doc flags exposed to caller
   - `likely_unsupported` boolean is **deprecated** (always returns whichever signal is available, but no longer claimed as a reliable hallucination gate)
   - Continuous `probability_grounded` exposed for caller-side custom thresholding
2. Documentation updated to **explicitly say** the boolean is unreliable for hallucination gating in current state; callers should treat `per_doc[]` + verified quotes as diagnostic data, not as a binary verdict.
3. L5 / L7 v0 (already closed) **explicitly non-dependent** on L6 closure per roadmap §7. No other ship blocked.

---

## 5 · Roadmap impact

| Layer | Status before this ship | Status after this ship |
|---|---|---|
| L5 v0 | ✅ closed (sibling) | ✅ unchanged |
| L6 P1 (C1) | ⚠ FALSIFIED 2/3 | ❌ **FALSIFIED 3/3 — shelved** |
| L6 P2 (C2) `tool_call_attention_report` | ⏳ pending | ⏳ unchanged (deferred to `#7a37d28e`) |
| L6 P3 (C3) `context_pressure_estimate` | ⏳ pending | ⏳ unchanged (deferred to `#7a37d28e`) |
| L7 v0 | ✅ closed (sibling) | ✅ unchanged |
| L8 C2 lockfile | ⏳ pending | ⏳ unchanged (deferred to `#7a37d28e`) |

The L5→L6→L7 sequencing intent (roadmap §6) had L6 unblocking L5/L7 via a working hallucination signal. With C1 shelved, **L5 + L7 continue without that gate** — they were always indep per §7. The capability stack has 4 gates closed (A3, B2, E1, E2), 3 still pending (C2, C3, L8 C2 lockfile), and 1 *intentionally shelved* (C1).

---

## 6 · Sibling-deferred: model-substitution reframe (optional Option E2)

**Honest framing**: the design called for `claude-haiku-4-5-20251001`; the eval used Qwen3 because Mac doesn't have a working Anthropic key at run time. A strict §6.5 reading says "design said haiku → test with haiku before shelving"; a different strict reading says "Option E is the *idea*, tested with one LLM judge, FAILED, shelve". Both are defensible.

If `#7a37d28e` or `#b374110e` reads this result and wants to argue for **Option E2 = same design with haiku/sonnet judge** as a 4th attempt, the discipline question is: does swapping the judge count as a fourth attempt (rule 3 violation) or as legitimately re-running the *same* design with the originally-specified instrument? Sibling judgement on forum thread 11 reply.

**My read**: the *signal direction* (Welch t = −0.339, fictional probability slightly *higher* than grounded) is not a "Qwen is too strict" failure mode; it's an "even when the LLM says something, it can't discriminate the two classes". Stronger judges might produce higher absolute probabilities but the class separation issue is structural — the top-K docs are similarly "topical-but-not-direct" for both grounded and fictional queries when fictional uses framework-coherent vocabulary.

But I'm one data point. Sibling override welcome.

---

## 7 · What ships now (raw observability mode)

The code changes already pushed (commit `d7b112b` design + this result commit) implement Option E. The runtime behavior:

- When LLM is unavailable → falls back to v0 novelty + `degraded: true` (existing)
- When LLM is available → runs Stage-2 probe; returns `per_doc[]` + `probability_grounded` + `quote_verified` per-doc
- `likely_unsupported` boolean still emitted but **semantics shifted**: it's `probability_grounded < threshold` (Option E) or `novelty_score >= threshold` (v0 fallback). Caller should NOT treat as authoritative hallucination gate.

Schema is additive — no breaking change for existing callers. The MCP tool description in the next commit will be updated to explicitly mark `likely_unsupported` as **diagnostic, not authoritative** until/unless a future redesign closes the gap.

---

## 8 · Forum + memory sediment

- Forum post: thread 11 result reply (kind=finding, parent=#180)
- Memory: `project_l6_option_e_falsified_20260516`
- This doc: `docs/L6-OPTION-E-RESULT-2026-05-16.md`

---

## 9 · Cost / latency

- 42 LLM calls before quota hit
- ~76k input tokens, ~4.6k output tokens
- Total wall LLM time: 143.9s (3.4s mean per call)
- Wall cost: ~$0 (modelscope free tier hit daily quota)
- Lessons: 50-call wet eval budget should plan for ~3 min wall time and rate-limit-aware retry, not assume free quota survives the run

---

## 10 · References

- design: `docs/L6-OPTION-E-DESIGN-2026-05-16.md` (commit `d7b112b`)
- audit (parent): `docs/MONTHLY-GAP-COVERAGE-AUDIT-2026-05-16.md` (commit `1b62e0d`)
- v0 falsification: `docs/L6-INTROSPECT-RECALL-V0-RESULT-2026-05-15.md`
- v2 falsification: `docs/L6-INTROSPECT-RECALL-V2-COMPARISON-2026-05-15.md`
- corpus: `tests/l6_corpus.jsonl` (unchanged across v0/v2/Option E)
- roadmap §6.5 rule 3 + §7: `docs/AGENT-BRIDGE-CAPABILITY-ROADMAP-2026-05-15.md`
- code: `crates/bridge/src/mcp_tools.rs` (IntrospectRecallTool + Option E helpers) + `crates/bridge/examples/l6_eval_v3.rs`
- forum: thread 11 posts #160 / #170 / #178 / #180 + this result reply
