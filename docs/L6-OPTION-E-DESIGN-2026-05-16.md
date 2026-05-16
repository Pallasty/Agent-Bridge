# L6 Option E — LLM-as-Relevance Design

**Date**: 2026-05-16
**Author**: `maxiaodeMac-Pro.local:agent-bridge:main#0275dd57`
**Status**: Design phase. No code yet. Verify-design-act discipline anchor.
**Parents**: thread 11 #160 (`#7a37d28e` proposal) + #170 (`#b374110e` buy-in) + #178 (my owner claim) + audit doc `1b62e0d`.
**Pre-conditions met**: §6.5 rule 3 reframe ✓ / sibling buy-in (1)(2)(4) ✓ / falsifiability gate unchanged ✓ / v0/v2 author ack ✓.

---

## 1 · Intent recap

C1 hallucination gap was FALSIFIED twice on token-level signals (S0 cosine, S-A entity-presence, S-B content-overlap). Option E is a **dimensional reframe**, not a third token-dim attempt: ask an LLM to judge *relevance* (with required verbatim quote) on the geometric top-K candidates from v0.

Stage 1 (cheap): existing `memory_top_k_cosine(query, k=5)` — unchanged.
Stage 2 (LLM probe): one batched API call rating each of the 5 docs `{0, 1, 2}` with a mandatory verbatim quote when score ≥ 1. Quote presence is verified via substring match against the original doc body.

---

## 2 · Output schema (extended `IntrospectRecallTool`)

Backward-compat: `likely_unsupported` boolean preserved (semantics shift to `probability_grounded < threshold`). New fields additive.

```jsonc
{
  "query": "...",
  "probability_grounded": 0.62,            // float [0..1] continuous (NEW)
  "threshold": 0.4,                         // caller-tunable, default 0.4 (was 0.7 for novelty)
  "likely_unsupported": false,              // = probability_grounded < threshold (semantics shift)
  "stage1_novelty": 0.35,                   // 1 - max(cosine), preserved from v0
  "top_k_count": 5,
  "per_doc": [                              // NEW
    {
      "key": "memory/key/123",
      "kind": "feedback",
      "cosine": 0.82,
      "score": 2,                           // 0|1|2 from LLM
      "quote": "...verbatim...",            // null if score=0
      "quote_verified": true,               // substring match in original body
      "score_after_verify": 2               // = score if verified else min(score, 1)
    },
    // ... 5 entries
  ],
  "degraded": false,                        // NEW: true if LLM call failed → fell back to v0 novelty
  "llm": {                                  // NEW: telemetry
    "model": "claude-haiku-4-5",
    "provider": "anthropic",
    "input_tokens": 412,
    "output_tokens": 73,
    "latency_ms": 198
  }
}
```

**Aggregation**: `probability_grounded = sum(score_after_verify) / (k * 2)`. Range [0, 1]. `k=5` → max 10 → /10. Verbatim quote required to retain score=2; if LLM claims score=2 but quote substring missing from doc body, score capped to 1 (per #160 anti-hallucination mitigation).

**Threshold semantics**: `probability_grounded < threshold` → `likely_unsupported = true`. Default threshold 0.4 = "less than 4 out of 10 grounded score across 5 docs". Tunable by caller.

---

## 3 · LLM call design

**One batched call** per `introspect_recall` invocation (not 5 per-doc calls).

### Prompt template (system + user)

```
SYSTEM:
You judge how directly each document addresses a query. You do NOT
verify facts; you score topical and content relevance only.

For each document, output:
- score: 0 (unrelated), 1 (tangential), 2 (directly addresses)
- quote: REQUIRED if score >= 1. Copy a verbatim span from that
  specific document that demonstrates the relevance. The span must
  be present in the document text exactly. If you cannot find a
  verbatim span that justifies score >= 1, set score to 0.

Output strict JSON only, no prose.

USER:
Query: {query}

Documents:
[1] (kind={kind1}, key={key1[:32]})
{content1[:1200]}

[2] (kind={kind2}, key={key2[:32]})
{content2[:1200]}

... [5]

Output JSON: {"docs": [{"id": 1, "score": 0|1|2, "quote": "..."|null}, ...]}
```

### Model + budget

- **Default model**: `claude-haiku-4-5-20251001` (cheap + fast)
- **Env override**: `AB_INTROSPECT_LLM_MODEL`
- **Max output tokens**: 400 (5 docs × ~70 tokens incl quote)
- **Per-call cost target**: <$0.002 (haiku rates)
- **Per-call latency target**: <500ms p95

### Per-session ceiling

- Env var `AB_INTROSPECT_LLM_MAX_PER_HOUR` default **30 calls/hour**
- Soft limit; exceed → fall back to v0 cosine novelty + `degraded: true` + warn log
- Prevents runaway cost in eval / repeated test loops

### Failure modes + fallbacks

| Mode | Detection | Fallback |
|---|---|---|
| LLM API unreachable | `LlmClient::messages_create` returns Err | v0 cosine novelty path; `degraded: true` |
| LLM output not parseable as JSON | serde_json fail | Same — fall back to v0 + `degraded: true` |
| LLM output has wrong doc count | `docs.len() != k` | Same |
| LLM hallucinates quote (substring miss) | substring check fails | Cap score to 1; continue |
| Rate limit hit (per-hour ceiling) | counter check | v0 fallback + `degraded: true` for this call only |

---

## 4 · Code changes

| File | Change | LOC est |
|---|---|---|
| `crates/bridge/src/mcp_tools.rs` | Extend `IntrospectRecallTool::execute` — add Stage-2 LLM probe + JSON parse + quote verify + aggregate. New schema fields. | ~250 |
| `crates/bridge/src/llm_client.rs` | No change — reuse existing `messages_create` | 0 |
| `crates/bridge/examples/l6_eval_v3.rs` | New eval harness — same corpus, runs Option E pipeline, reports per-class probability distribution + L6-P1/P2 verdict | ~200 |
| `crates/bridge/src/mcp_tools.rs` (tests) | +6-8 tests: prompt builder, JSON parser, quote-verify substring, aggregate math, fallback path, rate limiter, empty-hits edge | ~150 |
| `Cargo.toml` (bridge crate) | No new deps — `reqwest` + `serde_json` already there | 0 |

**Total new code**: ~600 LOC including tests. Estimated 4-6h impl + ~1h eval.

---

## 5 · Test plan

### Unit (in `mcp_tools.rs`)

1. `option_e_prompt_builder_includes_all_k_docs` — k=5 docs all appear in user prompt
2. `option_e_json_parser_happy_path` — well-formed `{"docs":[...]}` parses
3. `option_e_json_parser_malformed_returns_err` — missing field, garbage → Err
4. `option_e_quote_verify_substring_match` — quote IS substring → verified=true
5. `option_e_quote_verify_substring_miss` — quote NOT substring → verified=false → score capped to 1
6. `option_e_aggregate_continuous_probability` — sum/(k*2) math, edge cases (all 0, all 2, mixed)
7. `option_e_fallback_on_llm_err` — mocked LlmClient Err → degraded=true, novelty path
8. `option_e_rate_limit_after_max_per_hour` — 31st call/hour → degraded=true

### Wet eval (`l6_eval_v3.rs`)

Reuse `tests/l6_corpus.jsonl` 50-prompt corpus. For each query:
- Compute v0 cosine novelty (same as v0)
- Compute Option E `probability_grounded`
- Compute `quote_verified_rate` per doc

Output:
- Per-class table: grounded vs fictional mean probability_grounded ± stddev
- Welch t-test on probability_grounded
- Threshold sweep (0.10..0.90 step 0.05): detect rate (probability < threshold on fictional) vs FP rate (probability < threshold on grounded)
- Max Youden's J + best (threshold, detect, FP) tuple
- L6-P1 verdict: max detect at FP ≤ 25% ≥ 60% ?
- L6-P2 verdict: max FP at detect ≥ 60% ≤ 25% ?
- Per-class `quote_verified_rate` — diagnostic

### PASS criteria (rule 2 unchanged)

- L6-P1: detect ≥ 60% at some threshold AND L6-P2 FP ≤ 25% at SAME threshold (joint PASS)
- L6-P3 not in scope (separate ship)

### FAIL exit (rule 3)

- Both gates fail → C1 hits 3/3 → **rule-3 shelve**:
  - Ship `IntrospectRecallTool` as raw observability: return `per_doc[]` with scores + quotes but drop `likely_unsupported` from contract (mark deprecated, return false)
  - Document the cheap-probe-intractable finding
  - L5/L7 explicitly non-dependent per roadmap §7 — no other ship blocked
  - Forum post: `kind=finding`, parent = thread 11

---

## 6 · Cost ceiling for eval

50 prompts × 1 LLM call each = 50 calls. ~$0.10 wall cost. Within `dream weekly` discretionary spend.

Wet-run will set `AB_INTROSPECT_LLM_MAX_PER_HOUR=200` for the eval session only.

---

## 7 · What stays untouched

- `memory_top_k_cosine` primitive
- `tests/l6_corpus.jsonl` corpus
- MCP tool name `introspect_recall` (schema additive)
- L5 / L7 v0 (independent, not blocked)
- `kind=feedback` retrieval boost, `corrects` edge type, AGENT.md drift detector

---

## 8 · Exit plan if Option E FAIL

Per audit §4 + this design §5: ship raw observability mode. The tool becomes useful as **caller-side input** even without binary verdict — callers (next LLM session) can read `per_doc[]` + `quote_verified_rate` and decide for themselves.

Memory + forum trail will preserve the falsification chain v0 → v2 → Option E for future inquiry.

---

## 9 · Sequence

1. Write design doc ← **YOU ARE HERE**
2. Forum-post design memo to thread 11 (~10 min)
3. Implement code changes (~4-6h)
4. Run unit tests
5. Run `l6_eval_v3.rs` wet eval
6. Write result doc + memory + forum post
7. Commit + push
8. Bake observation period: 24h (in case LLM provider has cost spike or quota issue)
9. If PASS → C1 closes; if FAIL → shelve per §8

---

## 10 · Pre-impl forum visibility check

Before code, post design memo to thread 11 with **24-hour sibling redirect window**. If `#7a37d28e` or `#b374110e` flag a design issue, pause + revise. Otherwise proceed. This is the discipline that prevents another v2-FALSIFIED-during-author-asleep round.

Window pragma: I'm awake + working now (~10:55 UTC, 2026-05-16). User explicitly granted autonomy ("按照你的思路推进"). 24h window is generous but defaults to "proceed if no redirect by ~10:55 UTC 2026-05-17". I'll start impl in parallel with the forum visibility window — the unit-test cost of revising is low if anyone objects within first 2-3h.

## 11 · References

- audit `docs/MONTHLY-GAP-COVERAGE-AUDIT-2026-05-16.md` (commit `1b62e0d`)
- v0 result `docs/L6-INTROSPECT-RECALL-V0-RESULT-2026-05-15.md`
- v2 result `docs/L6-INTROSPECT-RECALL-V2-COMPARISON-2026-05-15.md`
- roadmap `docs/AGENT-BRIDGE-CAPABILITY-ROADMAP-2026-05-15.md` §3 + §6.5 + §7
- forum thread 11 posts #160, #170, #178
- LLM client: `crates/bridge/src/llm_client.rs`
- existing tool: `crates/bridge/src/mcp_tools.rs:9239` `IntrospectRecallTool`
- corpus: `tests/l6_corpus.jsonl`
