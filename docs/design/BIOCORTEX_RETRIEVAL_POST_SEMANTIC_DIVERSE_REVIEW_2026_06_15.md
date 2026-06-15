# BioCortex Retrieval Post-Semantic-Diverse Review

Date: 2026-06-15

## Summary

The aio2 handoff review for the post-runtime semantic-diverse live-candidate
corpus is recorded. The review accepts the evidence as sufficient for selecting
a downstream AIO integration checkpoint that consumes runtime-backed BioCortex
evidence under controlled, explicit opt-in FTS gates.

Reviewed source evidence:

- `docs/design/BIOCORTEX_RETRIEVAL_POST_RUNTIME_SEMANTIC_DIVERSE_LIVE_CANDIDATE_2026_06_14.md`
- `docs/design/fixtures/biocortex-retrieval-post-runtime-semantic-diverse-live-candidate-2026-06-14.json`
- `docs/design/fixtures/biocortex-retrieval-post-runtime-semantic-diverse-live-candidate-corpus-2026-06-14.json`
- `scripts/run-biocortex-post-runtime-semantic-diverse-live-candidate-corpus.sh`
- `scripts/verify-biocortex-retrieval-shadow.sh`

Machine-readable review:

- `docs/design/fixtures/biocortex-retrieval-post-semantic-diverse-review-2026-06-15.json`

## Review Result

The evidence is accepted for the next planning step:

- select the downstream AIO integration checkpoint that should consume the
  runtime-backed evidence;
- keep the first downstream checkpoint read-only or explicitly opt-in;
- keep Agent-Bridge fixture expansion stopped unless the downstream checkpoint
  reveals a new gap.

The semantic-diverse corpus is sufficient because it demonstrates protected
movement across four independent non-production fixture families:

| case | queries | BioCortex runs | side-signal ok | actual order changed |
|---|---:|---:|---:|---:|
| semantic-route | 2 | 2 | 2 | 2 |
| semantic-repair | 2 | 2 | 2 | 2 |
| semantic-temporal | 2 | 2 | 2 | 2 |
| semantic-graph | 2 | 2 | 2 | 2 |

Aggregate review checks:

- fixture count: `4`;
- total query count: `8`;
- total BioCortex run count: `8`;
- total side-signal ok count: `8`;
- total actual order changed count: `8`;
- expected met: `true`;
- status surfaces remained `blocked` and side-effect free;
- committed summaries omit raw query text, raw memory keys, memory content, and
  raw side-signal rows.

## Boundary

This review does not grant any new runtime or default-use permission. It does
not authorize:

- default retrieval influence;
- hybrid retrieval influence;
- semantic retrieval influence;
- approval writes;
- default `memory_search` order changes;
- production use without a downstream gate;
- additional raw query, key, content, or side-signal disclosure.

The accepted scope remains:

- explicit opt-in FTS runtime influence only;
- compile feature `biocortex-retrieval-opt-in` required;
- runtime env `AB_BIOCORTEX_RETRIEVAL_OPT_IN=1` required;
- explicit per-call opt-in required;
- post-runtime transition gate required;
- operator kill switch `AB_BIOCORTEX_RETRIEVAL_DISABLE` preserved.

## Next Step

The next project action is
`select_downstream_aio_integration_checkpoint_for_runtime_backed_evidence`.
That checkpoint should decide where AIO consumes the evidence first, while
preserving the same read-only or explicit opt-in boundary until a separate
authorization expands it.
