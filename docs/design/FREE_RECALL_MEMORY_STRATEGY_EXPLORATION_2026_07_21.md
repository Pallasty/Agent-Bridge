# Free Recall Memory Strategy Exploration

Date: 2026-07-21

Status: **PUBLIC-SYNTHETIC EXPLORATION COMPLETE / NO RUNTIME AUTHORITY**

## 1. Source and question

This exploration is motivated by Li et al., *A neural network model of free
recall learns multiple memory strategies*, published in *Nature Machine
Intelligence* in 2026:

- paper: <https://doi.org/10.1038/s42256-026-01274-0>
- code: <https://github.com/Veritaria/rnn-free-recall>
- archive: <https://doi.org/10.5281/zenodo.20422489>

The transferable claim is not that Agent-Bridge should embed that model. It is
that retrieval policy should depend on the recall objective. Exhaustive recall,
content-conditioned recall, recent-context continuation, and causal
reconstruction are different tasks and need not share one global ranking.

The falsifiable AB question is:

> On one controlled corpus, does choosing among relevance, recency, stable
> episode traversal, and causal-graph traversal outperform using any one policy
> for every query?

## 2. Existing AB evidence (not rerun here)

This lane does not replace existing evaluation work:

- `ab_eval.py` already measures single-gold retrieval and set-valued synthesis.
- `traversal_eval.py` already measures whether one-hop expansion recovers
  synthesis misses.
- the committed 2026-07-15 synthesis result reports any-mode set recall@20 of
  `0.778` over 13 real curated queries;
- the committed 2026-07-14 traversal diagnostic reports `0.917` under a fixed
  top-20 budget and `1.000` with unbounded one-hop expansion, at a mean
  neighborhood size of `168.8`.

Those results say graph traversal can recover missing evidence but may be
expensive. They do not answer whether traversal should run for every query.

## 3. Public-synthetic experiment

The fixture contains 24 synthetic records across three eight-record episodes:
release integration, memory research, and Live Semantic World. No production
memory, private query, store snapshot, or model output is present.

Sixteen queries cover four task intents:

| Intent | Correct policy shape | Primary metric |
|---|---|---|
| exhaustive / ordered audit | stable episode scaffold | set F1 plus pairwise order |
| conditional evidence lookup | lexical relevance | set F1 |
| causal reconstruction | dependency-graph traversal | set F1 |
| current-session continuation | scoped recency | set F1 |

The six measured arms are:

1. `content`: deterministic IDF-weighted lexical relevance;
2. `scoped_content`: the same ranker with the explicit episode prefilter, a
   control separating scope-filtering value from scaffold value;
3. `recency`: reverse traversal inside an explicit episode;
4. `scaffold`: forward traversal inside an explicit episode;
5. `graph`: bounded breadth-first traversal from an explicit target;
6. `router`: a text-only rule router choosing among the task-specific arms.

The fixture's gold `intent` field is used only for scoring. A self-test mutates
all intent labels and proves that router output does not change. Another
self-test reverses fixture item order and proves deterministic results.

Twelve calibration queries use direct intent language. Four
`paraphrase_challenge` queries deliberately avoid the router's obvious cue
words. This prevents a perfect calibration score from being mistaken for
generalization.

Run:

```bash
python3 scripts/eval/free_recall_strategy_benchmark.py \
  --selftest \
  --out scripts/eval/baselines/components/free_recall_strategy_2026-07-21.json
```

## 4. Result

| Arm | Macro task score |
|---|---:|
| content | 0.399870 |
| scoped content | 0.696540 |
| recency | 0.537500 |
| scaffold | 0.425000 |
| graph | 0.250000 |
| rule router | **0.830078** |
| oracle strategy selector (upper bound) | **1.000000** |

For ordered tasks, task score is fixed as `0.75 * set-F1 + 0.25 * pairwise
order`; other tasks use set-F1 directly. The weighting is an explicit synthetic
measurement choice, not a learned or production threshold.

The strongest single arm is scoped content at `0.696540`. The router improves
over that stronger matched control by `+0.133538`. The original unscoped
comparison would have overstated the lift, so episode filtering must remain a
required control in later experiments.

However, the router is not ready:

| Split | Route accuracy | Router task score |
|---|---:|---:|
| calibration | 1.000000 | 1.000000 |
| paraphrase challenge | **0.250000** | **0.320312** |
| combined | 0.812500 | 0.830078 |

The `0.169922` gap between the rule router and the oracle upper bound is almost
entirely intent-recognition failure. The experiment therefore supports a
multi-strategy architecture, but falsifies the stronger claim that a keyword
router is sufficient.

## 5. Interpretation for Agent-Bridge

### Supported by this experiment

- A single global retrieval policy is structurally mismatched to heterogeneous
  recall objectives.
- Episode scaffolds add a capability that relevance ranking does not provide:
  bounded, duplicate-free, order-aware coverage.
- Recency is a useful continuity strategy but a poor ordered-audit strategy.
- Graph traversal should be invoked for causal questions, not paid for on every
  query.
- Strategy selection is a separate quality problem from candidate ranking.

### Not supported by this experiment

- No claim about live AB retrieval quality or latency.
- No claim that the synthetic lexical ranker represents GTE, FTS, or hybrid
  search.
- No claim that AB currently has reliable episode boundaries.
- No neural-model reproduction and no evidence that BioCortex is needed.
- No authority to alter `memory_search`, `session_bootstrap`, graph edges,
  coactivation, memory writes, or runtime defaults.

The paper's “memory palace” should map to an abstract stable scaffold, not
automatically to a literal 3D scene. A session/event spine, goal tree, or semantic
world entity hierarchy can each provide the necessary index. Live Semantic
World may expose such a scaffold visually, but the canonical contract should
remain semantic.

## 6. Recommended next gate: R1 frozen-snapshot strategy replay

The next useful experiment is a read-only adapter over a disposable frozen AB
snapshot. It should reuse existing real curated fixtures rather than author a
new favorable corpus.

Preregister four matched arms:

1. current `memory_search` baseline;
2. explicit session/event scaffold traversal;
3. bounded causal/related-key graph traversal;
4. router-selected policy, with an oracle selector reported only as an upper
   bound.

Minimum acceptance conditions:

- router task score exceeds the best single arm by at least `0.10`;
- conditional retrieval does not regress by more than `0.02`;
- paraphrase route accuracy is at least `0.80` on a separately authored split;
- p95 work and surfaced context are no more than `2x` the baseline;
- abstention is explicit when scope, target, or episode metadata is missing;
- live memory is never written and default retrieval order remains unchanged.

BioCortex remains out of scope for R1. Only if explicit policies show value and
intent selection remains the limiting factor should a later lane compare a
small learned classifier or contextual bandit in shadow mode.
