# Free Recall Strategy R2 — Episode Recoverability Preregistration

Date: 2026-07-21

Status: **PREREGISTERED / READ-ONLY REPRESENTATION AUDIT / NO RETRIEVAL AUTHORITY**

Parent result:
`docs/design/FREE_RECALL_STRATEGY_R1_1_FROZEN_CLOCK_RESULT_2026_07_21.md`

Paper and code anchors:

- Li et al., *A neural network model of free recall learns multiple memory
  strategies*, Nature Machine Intelligence (2026), DOI
  `10.1038/s42256-026-01274-0`;
- official code: `https://github.com/Veritaria/rnn-free-recall`, audited at
  commit `87371c046be5b3d4a9521b23d26f23a5b4385d7a`.

## 1. Correction to the implementation hypothesis

The paper's winning memory-palace mechanism is not merely a stored
`episode_id` or timestamp. Training creates a stimulus-invariant serial-index
code in the recurrent hidden state; the same state is stored in episodic slots
and later used as both retrieval cue and retrieved value. The key-value variant
more explicitly separates index-heavy keys from identity-heavy values.

Therefore R2 does not claim that static provenance reproduces the paper. It
asks a prerequisite question:

> Does the current AB corpus already contain enough oracle-free provenance to
> identify which records belong to one exhaustive recall episode?

If not, adding a selector or learned policy has no reliable scaffold to act on.

## 2. Frozen truth and scope

Use only the 13 frozen `synthesis_queries.json` cases from R1. These are the
only existing fixtures with set-recall labels. A positive pair consists of two
active keys that co-occur in at least one frozen gold set; a negative pair is
two active keys in the synthesis universe that never co-occur.

Gold labels are used only for scoring. They must not choose tag values,
thresholds, graph edges, time windows, or channel combinations.

The eligible source remains a read-only online backup of tb14. All fixture
hashes and active-key preflight rules remain unchanged.

## 3. Preregistered oracle-free channels

Each channel predicts that a pair belongs to the same episode when:

1. `all_exact_tags`: the records share any exact tag value;
2. `provenance_tags`: they share an exact tag whose prefix is one of
   `batch`, `source`, `arc`, `zone`, `distill_prompt`, `method`, `verify`,
   `verdict`, `proposes`, `derived`, or `deploy`;
3. `related_keys`: either record names the other in `related_keys`;
4. `non_coactivation_edge`: an existing non-coactivation edge directly joins
   them in either direction;
5. `time_5m`, `time_30m`, `time_2h`: same exact scope and absolute
   `created_at` distance within 5 minutes, 30 minutes, or 2 hours;
6. `provenance_or_structure`: union of channels 2–4;
7. `all_metadata_union`: union of channels 1–5 using the fixed 30-minute time
   window.

No content, embeddings, query text, key-name parsing, gold-set overlap, or
trained parameters may construct a channel.

## 4. Metrics and gates

For every channel report predicted-pair count, precision, recall, F1, and
false-positive/false-negative counts. Also report positive prevalence and an
`all_pairs_positive` sanity baseline.

### Recoverability gate

At least one oracle-free channel must satisfy all three:

- precision >= `0.70`;
- recall >= `0.50`;
- F1 >= `0.58`.

### Coverage guard

A channel predicting fewer than 5 positive pairs is informational only and
cannot pass, regardless of precision.

### Leakage falsifier

Run once with original case ordering and once with reversed case ordering.
Aggregate channel results must be byte-identical. Removing query text and notes
from the in-memory fixture representation must also leave results identical.

## 5. Decisions

- If the recoverability gate passes: design a prospective, default-off episode
  projection using only the passing channel, then test set recall before any
  training.
- If it fails: current metadata cannot support a reliable episode scaffold.
  The next eligible experiment is prospective write-side instrumentation with
  explicit episode membership and position, collected before retrieval use.
- Even a pass does not reproduce the paper's learned index code. A later model
  must demonstrate item-invariant position decoding and recall lift.

## 6. Negative authority

R2 does not authorize schema migration, memory writes, retrieval changes,
MCP exposure, deployment, router training, BioCortex, or importing the paper's
model weights. No private content, tags, keys, database paths, or raw pair list
may enter the committed result.
