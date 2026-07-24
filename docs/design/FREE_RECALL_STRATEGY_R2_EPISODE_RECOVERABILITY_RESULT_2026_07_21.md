# Free Recall Strategy R2 — Episode Recoverability Result

Date: 2026-07-21

Status: **COMPLETE / RECOVERABILITY GATE FAILED / PROSPECTIVE INSTRUMENTATION NEXT**

Preregistration:
`docs/design/FREE_RECALL_STRATEGY_R2_EPISODE_RECOVERABILITY_PREREGISTRATION_2026_07_21.md`

## 1. Research correction from the paper

The published article and official implementation sharpen the project analogy:

- the model studies 8 items sampled from a 64-item vocabulary;
- a 128-unit GRU updates its hidden state and stores that state in one of 8
  episodic slots;
- during recall, the current hidden state queries stored states by cosine
  similarity, with a low-temperature softmax favoring one slot;
- the retrieved state, previous action, and previous reward update the next
  hidden state;
- A2C training rewards a new correct recall (`+1`) and penalizes wrong or
  repeated recall (`-0.75`), with no prescribed recall order;
- working memory is normally flushed between study and recall, forcing use of
  episodic slots.

The memory-palace strategy is an emergent recurrent representation: serial
position becomes decodable across changing item identities and across study
and recall phases. It is not an explicit database sequence number. In the
paper's key-value variant, keys become relatively index-heavy while values
remain relatively identity-heavy, which is the closest architectural analogy
to a stable scaffold plus content payload.

Official precomputed artifacts reinforce this distinction. In the authors'
filtered 611-model corpus, the memory-palace cluster (cluster 0) had mean index
cross-decoding `0.8865`, versus `0.4901` for TCM-like forward (cluster 2) and
`0.1751` for TCM-like backward (cluster 1). In the controlled performance
artifact, mean recall accuracy was `0.7522`, `0.5896`, and `0.4419`
respectively. These are artifact-derived descriptive statistics, not an
independent replication.

Primary sources:

- Nature Machine Intelligence article:
  `https://doi.org/10.1038/s42256-026-01274-0`;
- official repository:
  `https://github.com/Veritaria/rnn-free-recall` at
  `87371c046be5b3d4a9521b23d26f23a5b4385d7a`;
- archived code release: `https://doi.org/10.5281/zenodo.20422489`.

## 2. AB recoverability result

R2 tested whether current AB provenance can identify episode-like membership
without content, embeddings, query text, key parsing, or fitted parameters.
The frozen synthesis universe contained:

- 13 set-recall cases;
- 30 unique active keys;
- 435 possible pairs;
- 52 positive co-membership pairs;
- positive prevalence `0.119540`.

No preregistered channel passed the recoverability gate.

| Channel | Predicted | Precision | Recall | F1 | Verdict |
|---|---:|---:|---:|---:|---|
| exact shared tag | 342 | 0.134503 | 0.884615 | 0.233503 | FAIL |
| provenance tag | 4 | 0.250000 | 0.019231 | 0.035714 | FAIL, under coverage |
| `related_keys` | 33 | 0.606061 | 0.384615 | 0.470588 | FAIL |
| non-coactivation edge | 34 | 0.588235 | 0.384615 | 0.465116 | FAIL |
| same-scope within 5 min | 0 | 0.000000 | 0.000000 | 0.000000 | FAIL |
| same-scope within 30 min | 2 | 1.000000 | 0.038462 | 0.074074 | FAIL, under coverage |
| same-scope within 2 h | 9 | 0.777778 | 0.134615 | 0.229508 | FAIL |
| provenance or structure | 50 | 0.560000 | 0.538462 | **0.549020** | FAIL |
| metadata union | 348 | 0.143678 | 0.961538 | 0.250000 | FAIL |

The best balanced channel missed the required precision (`0.70`) and F1
(`0.58`). The highest-precision eligible channel, the 2-hour window, recovered
only 7 of 52 positive pairs.

## 3. Integrity evidence

- source SQLite connection: read-only, total changes `0 -> 0`;
- snapshot SHA-256 before/after:
  `8d04d52359529fdeebd0288af97c8f1e9642d778b71bc7ae240538cf030460fa`;
- aggregate result SHA-256:
  `35b3a08fe6ef2a90175c076c9cca14ac3401e770c55737a3d129bc64463c848a`;
- original/reversed case order: byte-identical aggregate result;
- stripping query text and notes: byte-identical aggregate result;
- no raw keys, tags, pair list, memory content, embeddings, or database is
  committed.

## 4. Interpretation

Current metadata has the wrong shape for an episode scaffold:

- broad continuity and topical tags connect many unrelated records, giving
  high recall but very low precision;
- direct edges and `related_keys` are more selective but cover less than 40%
  of true episode pairs;
- creation-time proximity is precise only at narrow windows and cannot recover
  records assembled across a longer reasoning arc.

Therefore an `episode_id` inferred retrospectively from the current corpus
would either hallucinate large episodes or omit most members. It should not be
used to rerank retrieval.

## 5. Next research target

The next eligible lane is a **prospective episode-observation sidecar**, not a
retrieval feature:

1. At write time, record an explicit opaque `episode_id`, zero-based
   `episode_position`, episode source (`session`, `curation_batch`, or explicit
   owner bundle), and completion state.
2. Keep it additive, default-off, and excluded from search scoring.
3. Collect public-synthetic episodes first, then a bounded owner-approved
   sample of real sessions.
4. Test three prerequisites before retrieval use:
   - membership precision/recall against declared bundles;
   - cross-content position decodability;
   - full-set recall lift under fixed candidate budget.
5. Only if the scaffold itself creates at least `+0.05` oracle lift should we
   consider learning a policy. BioCortex remains downstream of that gate.

This prospective sidecar still does not reproduce the paper's recurrent index
code; it creates the minimum observability needed to learn or falsify one.

## 6. Authority boundary

R2 authorizes no schema migration, writes, retrieval changes, MCP tools,
deployment, training, or BioCortex run. The current branch remains a research
branch pending separate review.
