# L6 `introspect_recall` v0 — falsification result

**Date**: 2026-05-15
**Author**: `maxiaodeMac-Pro.local:agent-bridge:main#0275dd57`
**Status**: **L6-P1 and L6-P2 jointly FAIL.** v0 design as currently formulated does not separate grounded vs fictional queries on a 25+25 held-out corpus. The pure-cosine novelty signal is statistically indistinguishable between the two classes (Welch's t = -0.36). Redesign required before L5 / L7 can build on L6.
**Triggers**: Week-1 roadmap commitment from `docs/AGENT-BRIDGE-CAPABILITY-ROADMAP-2026-05-15.md` §3 + falsifiability test L6-P1 (detection ≥60%) and L6-P2 (false-positive ≤25%).

## Setup

- Backend: `all-MiniLM-L6-v2` ONNX (real embeddings, downloaded on first call to `~/.cache/fastembed/`, ~80 MB)
- Store: Mac canonical `~/.local/share/agent-bridge/state.db` (2137 memories, 674 active, post-merge with aio2 snapshot)
- k = 5 (top-K cosine, novelty = `1 - max(cosine)`)
- Corpus: `tests/l6_corpus.jsonl` (25 grounded, 25 fictional)
  - **Grounded** = questions about real recent work (commits, sibling posts, repo concepts, memory entries from today's session)
  - **Fictional** = plausible-shape questions about invented concepts using real agent-bridge vocabulary (e.g. `multimodal_sentinel`, `Buckhannon-Diaz reranker`, `karst_index`, `.agent_bridge_lockfile`)
- Runner: `crates/bridge/examples/l6_eval.rs` (build: `cargo build --release -p ab-bridge --example l6_eval`)

## Headline numbers

| Metric | Grounded (n=25) | Fictional (n=25) |
|---|---|---|
| Mean novelty | 0.635 | 0.626 |
| Median | 0.632 | 0.646 |
| Std dev | 0.094 | 0.077 |
| Min | 0.478 | 0.459 |
| Max | 0.785 | 0.766 |

- **Mean gap (fictional − grounded) = −0.009.** Directionally **backwards** — fictional queries had slightly *lower* novelty on average than grounded ones.
- **Welch's t = −0.36, p ≫ 0.05.** Distributions are statistically indistinguishable.

## Threshold sweep

| threshold | detect (fictional ≥ thr) | FP (grounded ≥ thr) | Youden's J |
|---|---|---|---|
| 0.40 | 100% | 100% | 0.000 |
| 0.50 | 96% | 96% | 0.000 |
| 0.55 | 84% | 84% | 0.000 |
| 0.60 | 68% | 56% | **+0.120** |
| 0.65 | 40% | 44% | −0.040 |
| 0.70 | 12% | 28% | −0.160 |
| 0.75 | 8% | 16% | −0.080 |
| 0.80 | 0% | 0% | 0.000 |

The maximum Youden's J across all thresholds is **+0.12** — essentially random (J=0). No operating point jointly satisfies L6-P1 (≥60% detect) and L6-P2 (≤25% FP).

## What broke

The v0 design assumed novelty = `1 - max(cosine)` would separate "I have grounding in memory" from "I do not". The data shows this isn't true on a domain-specific corpus.

The mechanism: both grounded and fictional queries share the **same surface vocabulary** (`agent-bridge`, `daemon`, `MCP`, `memory`, `sibling`, `embedding`, `forum_post`). MiniLM correctly identifies that they all belong to the same topical neighborhood — and assigns similar cosines to whichever of my 674 active memories is the closest neighbor. The fact that "Buckhannon-Diaz reranker" is invented and "v22 Phase 3 predict-weighted neighbors_of" is real is a finer distinction than the embedding sees.

Equivalently: cosine ranking finds **topical match**, not **claim grounding**. They are not the same.

## Implications for the roadmap

- **Discipline worked.** Roadmap §3 promised "highest-leverage falsifiability test that doesn't depend on Seed". The test executed, ran cleanly, and **falsified** the v0 design at week 1 — before L5 / L7 built on top. The cost of finding this out is one day, not weeks. This is the falsifiability discipline doing its job.
- **L5 and L7 are *not* dead.** L6 v0 is one specific mechanism; L5 (behavioral memory) and L7 (self-modification) don't strictly require this specific L6 signal. They could be unlocked by a different L6 design that does pass.
- **The 4-5 week sequencing slips by ~1 week** while L6 is redesigned and re-tested. That's expected when the first ship is the highest-leverage test.

## Redesign candidates

Three concrete redesigns ranked by cost. Pick after sleep / sibling review; don't ship the first idea.

### Option A — Entity-presence check (cheapest, ~0.5d)

Extract from the query any **distinctive identifiers** — post numbers (#147), commit shas (8666119), file paths (crates/store/src/sqlite.rs), specific names with capitalised letters or underscores (PROJ_EPSILON), API symbols (`memory_top_k_cosine`). For each, check whether they appear verbatim in any of the top-K memory contents (or in `forum_posts.body`, `memory.content`, `codebase_symbols.signature`). Grounding = ≥1 distinctive identifier confirmed.

- **Why it might work**: fictional queries use invented identifiers (`karst_index`, `Buckhannon-Diaz`) that by construction won't appear in real memory.
- **Why it might not**: real questions sometimes don't include distinctive identifiers ("How does the wrapper warn about missing files?"), and we'd default to "no grounding" too aggressively.
- **Failure mode**: high false-negative on natural-language-only queries.

### Option B — Content overlap on top-K (cheap, ~1d)

Tokenize query (strip stopwords), tokenize top-K memory contents same way, compute fraction of query tokens present in any top-K content. Threshold at e.g. 0.4. Grounding = enough query terms appear in retrieved memories that an answer could be quoted from them.

- **Why it might work**: fictional queries have invented terms that won't appear anywhere; grounded queries have terms that should appear in their related memories.
- **Why it might not**: paraphrase / synonym mismatch (e.g. memory says "carrier-pinning" but query says "perception slot tracking"); high specificity on prose questions.
- **Failure mode**: brittle to natural-language variation.

### Option C — LLM-as-judge two-pass (most expensive, ~1.5d)

Pass 1: cosine top-K narrows from 674 to 5. Pass 2: ask the LLM client (existing `LlmClient` in agent-bridge) "given query Q and these 5 contents, can you confidently answer Q from these contents alone? yes/no/partial + 1-line reason". Grounding = yes or partial.

- **Why it works**: matches human judgment of grounding; handles paraphrase robustly.
- **Why it might not**: LLM may hallucinate the judgment too; cost ≈ 1 LLM call per `introspect_recall` invocation (~$0.001 + ~200ms).
- **Risk**: introduces an LLM dependency at the introspection layer, which we wanted to avoid for a fast metacognition probe.

### Recommendation

Run A and B as cheap regression tests first (same 50-prompt corpus, redo the threshold sweep, see if either gives Youden's J > 0.4). If A or B passes, ship the cheap version. If both fail, escalate to C with explicit cost accounting.

## What the v0 implementation gives us regardless

Even though L6-P1 fails as a *hallucination-detection* signal, the `introspect_recall` MCP tool plus the `memory_top_k_cosine` trait method are not wasted:

- **Pure-cosine top-K is a real API** — useful for any caller that wants raw geometric ranking without the importance/recency blending that `memory_search` mode=semantic applies (e.g. corpus building, similarity studies, embedding-backend regression tests).
- **The corpus + runner stay** as the testbed for option A/B/C: redesigns plug into the same eval and we get directly comparable threshold sweeps.

So: ship the v0 code, ship the falsification finding, redesign the signal — don't redesign the harness.

## What I'm NOT doing right now

- Not deleting `IntrospectRecallTool` — the tool surface is correct, only the internal scoring is wrong. The redesigned version can keep the same MCP schema.
- Not blocking on this — L5 work can start in parallel with L6 redesign once option A/B is chosen.
- Not promoting v0 to default introspection. The tool ships but its `likely_unsupported` boolean is **unreliable** for that flag's named purpose until a redesigned signal passes the gate.

## References

- Code: `crates/bridge/src/mcp_tools.rs` (IntrospectRecallTool), `crates/store/src/sqlite.rs` (memory_top_k_cosine SQLite impl), `crates/store/src/lib.rs` (MemoryCosineHit + trait method)
- Eval: `crates/bridge/examples/l6_eval.rs`
- Corpus: `tests/l6_corpus.jsonl` (50 items)
- Raw report (this run): saved at `/tmp/l6_eval_report.md` on the Mac that ran the eval
- Roadmap: `docs/AGENT-BRIDGE-CAPABILITY-ROADMAP-2026-05-15.md` §3 L6 (the falsifiability gate this result evaluates)
- Memory anchors:
  - new: `project_l6_introspect_recall_v0_falsified_20260515`
  - companion: `project_agent_bridge_l5_l7_roadmap_20260515`
