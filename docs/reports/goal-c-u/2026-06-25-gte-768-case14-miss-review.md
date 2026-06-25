# GTE 768 Case #14 Miss Review

Date: 2026-06-25

Status: `CASE14_ADJUDICATED_AS_ALSO_CORRECT / LIVE_CUTOVER_NO_GO`.

Scope: content-read review for the remaining GTE 768 canonical rehearsal hard
miss `#14`. This packet adjusts the held-out eval accept-set after confirming an
also-correct memory. It does not authorize live reindex, live DB mutation,
deployment, runtime env changes, or production `memory_search` changes.

## Case

Query:

```text
biocortex 影子试验是只读的吗,会不会改默认检索顺序
```

Original expected key:

```text
ab_memory_continuity_t5_biocortex_shadow_trial_20260619
```

Original canonical GTE replay result before this review:

```text
#14 fts=- rows=10 fts+graph=- hybrid=- semantic=-
semantic misses: #5, #10, #14
hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.375 semantic=0.750
```

## Content Read

The original expected key directly answers the query:

```text
ab_memory_continuity_t5_biocortex_shadow_trial_20260619
```

Relevant facts from the row:

- T5 is implemented as a read-only, redacted AB-side shadow packet.
- It calls baseline `memory_search` and records hash-only baseline order.
- It computes a deterministic advisory-control order but sets
  `used_for_return_order=false`.
- It sets `changes_memory_search_order=false`.

The canonical semantic top-10 also returned this row at rank 3:

```text
ab_memory_continuity_t5_t6_shadow_evidence_batch_20260619
```

Content-read evidence from that row:

- all 5 real `memory_biocortex_shadow_trial` packets returned the expected T5
  schema;
- all packets were `read_only=true`;
- all packets had `runs_biocortex=false`, `writes_memory=false`, and
  `changes_memory_search_order=false`;
- advisory/control order did not change actual return order;
- `discovered_selection_claimed=false` remained conservative.

Decision: this is also-correct for the user's safety question. It is not merely
a same-topic BioCortex diagnostic row.

Rows deliberately not added to the accept-set:

- `biocortex_rs_owner_working_style_20260529`: owner preference/context, not the
  T5 shadow contract;
- BioCortex side-score / graph diagnostics from 2026-06-20: relevant to later
  T6 quality work, but not a direct answer to the read-only/order-safety
  question;
- `ab_memory_biocortex_t5_t6_live_chain_smoke_20260620`: helpful supporting
  evidence, but the 2026-06-19 T5/T6 batch is the narrower answer for this held
  out case.

## Eval Change

Updated `crates/bridge/examples/recall_eval.rs` case `#14` accept-set:

```text
ab_memory_continuity_t5_biocortex_shadow_trial_20260619
ab_memory_continuity_t5_t6_shadow_evidence_batch_20260619
```

The code comment records the content-read reason. This follows the existing
corpus rule: accept-set entries beyond the primary key are allowed only after
content-reading confirms they are also-correct.

## Canonical Re-Run

Command:

```bash
AB_BASELINE_DB=/home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T130030Z-canonical-snapshot-gate/state.db \
AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base \
cargo run -p ab-bridge --example recall_eval
```

Log:

```text
/home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T130030Z-canonical-snapshot-gate/recall_eval.case14-adjudicated.log
```

Updated overall 18-case recall:

```text
mode       R@1    R@5    R@10   MRR
fts        0.278  0.556  0.667  0.366
hybrid     0.278  0.500  0.667  0.364
semantic   0.111  0.833  0.889  0.436
```

Updated hard-tier anchor:

```text
hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.375 semantic=0.875
```

Updated case `#14` rank:

```text
#14 fts=- rows=10 fts+graph=- hybrid=- semantic=3
```

Updated semantic misses:

```text
#5, #10
```

FTS and hybrid still miss `#14`, so the specificity problem remains for lexical
and graph-expanded lexical retrieval. The change affects only the eval
accept-set for semantic scoring.

## Decision

`#14` is no longer a production-readiness blocker for GTE semantic evidence.
The canonical GTE replay now shows semantic finding an also-correct safety
answer for `#14` at rank 3.

This does not create runtime authority. It only clarifies the evaluation
contract and owner-review risk:

- live GTE cut-over remains `NO_GO`;
- reader compatibility remains undecided;
- rollback remains required before any live mutation;
- remaining semantic misses are `#5` and `#10`, both outside the hard-tier
  review-target set that originally named `#14`.

## Verification

Commands:

```bash
git diff --check
cargo test -p ab-bridge --example recall_eval -- --nocapture
AB_BASELINE_DB=/home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T130030Z-canonical-snapshot-gate/state.db \
AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base \
cargo run -p ab-bridge --example recall_eval -- 14
AB_BASELINE_DB=/home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T130030Z-canonical-snapshot-gate/state.db \
AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base \
cargo run -p ab-bridge --example recall_eval
```

Results:

- `git diff --check`: passed;
- `recall_eval` example tests: 36 passed;
- case `#14` debug: semantic rank 3 is
  `ab_memory_continuity_t5_t6_shadow_evidence_batch_20260619`;
- full canonical rerun: hard-tier semantic R@10 is `0.875`.

Note: `rustfmt --edition 2024 --check crates/bridge/examples/recall_eval.rs`
still reports pre-existing full-file formatting drift outside this change. The
file was not auto-formatted to avoid unrelated churn.
