# BioCortex Retrieval Post-Runtime Semantic-Diverse Live-Candidate Corpus

Date: 2026-06-14

## Summary

The post-runtime live-candidate proof now has a semantic-diverse corpus runner.
It replays the existing single-fixture live-candidate runner across four
independent non-production candidate-pair fixtures:

- route;
- repair;
- temporal;
- graph.

Each fixture runs in its own isolated non-production SQLite store. That keeps
the proof focused on independent candidate-pair movement and avoids
cross-fixture FTS IDF coupling.

Runner:

- `scripts/run-biocortex-post-runtime-semantic-diverse-live-candidate-corpus.sh`

Corpus manifest:

- `docs/design/fixtures/biocortex-retrieval-post-runtime-semantic-diverse-live-candidate-corpus-2026-06-14.json`

Machine-readable summary:

- `docs/design/fixtures/biocortex-retrieval-post-runtime-semantic-diverse-live-candidate-2026-06-14.json`

Fixture cases:

- `docs/design/fixtures/biocortex-retrieval-post-runtime-semantic-route-live-candidate-fixture-2026-06-14.json`
- `docs/design/fixtures/biocortex-retrieval-post-runtime-semantic-repair-live-candidate-fixture-2026-06-14.json`
- `docs/design/fixtures/biocortex-retrieval-post-runtime-semantic-temporal-live-candidate-fixture-2026-06-14.json`
- `docs/design/fixtures/biocortex-retrieval-post-runtime-semantic-graph-live-candidate-fixture-2026-06-14.json`

Local evidence artifacts:

- `target/biocortex-post-runtime-semantic-diverse-live-candidate-20260614/semantic-diverse-live-candidate-corpus-summary.json`
- `target/biocortex-post-runtime-semantic-diverse-live-candidate-20260614/SEMANTIC_DIVERSE_LIVE_CANDIDATE_REPORT.md`
- `target/biocortex-post-runtime-semantic-diverse-live-candidate-20260614/cases/semantic-route/live-candidate-runner-summary.json`
- `target/biocortex-post-runtime-semantic-diverse-live-candidate-20260614/cases/semantic-repair/live-candidate-runner-summary.json`
- `target/biocortex-post-runtime-semantic-diverse-live-candidate-20260614/cases/semantic-temporal/live-candidate-runner-summary.json`
- `target/biocortex-post-runtime-semantic-diverse-live-candidate-20260614/cases/semantic-graph/live-candidate-runner-summary.json`

## Evidence

Aggregate summary:

- schema:
  `agent_bridge.biocortex_retrieval.post_runtime_semantic_diverse_live_candidate_corpus_summary.v0`;
- status:
  `post_runtime_semantic_diverse_live_candidate_evidence_ready`;
- fixture count: `4`;
- total query count: `8`;
- total baseline empty count: `0`;
- total BioCortex run count: `8`;
- total side-signal ok count: `8`;
- total experimental source count: `8`;
- total actual order changed count: `8`;
- expected met: `true`.

Per-case movement:

| case | queries | BioCortex runs | side-signal ok | actual order changed |
|---|---:|---:|---:|---:|
| semantic-route | 2 | 2 | 2 | 2 |
| semantic-repair | 2 | 2 | 2 | 2 |
| semantic-temporal | 2 | 2 | 2 | 2 |
| semantic-graph | 2 | 2 | 2 | 2 |

The status surface remains conservative for every case:

- controlled status: `blocked`;
- status surface calls memory search: `false`;
- status surface runs BioCortex: `false`;
- status surface changes memory search order: `false`.

That result is expected. The artifacts prove protected explicit opt-in FTS
movement under the post-runtime gate, while the status readiness surface remains
side-effect free and continues to reject movement evidence as controlled-trial
readiness input.

## Boundary

This run preserves the existing boundaries:

- one non-production SQLite DB per fixture;
- no default Agent-Bridge DB mutation;
- no approval writes;
- no default `memory_search` order change;
- no hybrid or semantic retrieval influence;
- compile feature `biocortex-retrieval-opt-in` required;
- runtime env `AB_BIOCORTEX_RETRIEVAL_OPT_IN=1` required;
- explicit per-call opt-in required;
- post-runtime transition gate required;
- raw query text, raw memory keys, memory content, and raw side-signal rows are
  absent from committed summaries.

## Interpretation

This closes the prior Slice 38 next step. The reusable live-candidate runner no
longer has only one controlled candidate pair or one canonical term family. The
new corpus proves repeated protected movement across four independent semantic
axes while keeping each axis isolated enough for stable replay.

The next project action is not more fixture expansion inside Agent-Bridge. The
next action is to hand this evidence to aio2 for post-semantic-diverse review
and decide which downstream AIO integration checkpoint should consume the
runtime-backed BioCortex evidence.
