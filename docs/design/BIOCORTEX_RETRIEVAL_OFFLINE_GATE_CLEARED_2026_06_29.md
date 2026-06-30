# BioCortex Retrieval — offline benchmark gate CLEARED at the conservative blend (2026-06-29)

Date: 2026-06-29

## Decision

The BioCortex retrieval side-signal **passes the offline benchmark gate**
(`docs/design/BIOCORTEX_RETRIEVAL_BENCHMARK_GATE_2026_06_10.md`) at the **conservative** blend
`alpha=0.20`, deterministically and without a single rank regression. This supersedes the stale
open-problem finding `finding_biocortex_retrieval_side_signal_fails_gate_20260610` (and the P0 item
in `docs/design/BORROWED_PATTERNS_BACKLOG_2026_06_28.md`), both of which still describe the
**pre-fix** state (`+0.019 < +0.03`, "only passes at `alpha=0.80`").

This is the **AB-side attestation that was missing**: the scorer fix landed in the *biocortex-rs*
repo (commit `04f26e9` — "IDF-scale key-field bonus in side-signal overlap (clears +0.03 gate on
S70)", a 6-line edit to the read-only `examples/ab_retrieval_side_signal_adapter.rs`), but that
repo cannot touch this one, so the gate-owning repo (AB) never recorded the pass. The stale finding
then misled both the borrowed-patterns backlog and a 2026-06-29 integration survey into re-listing
an already-cleared lever as the blocker.

## What changed in the scorer (already landed in biocortex-rs)

The side score was compressed into a narrow band, so under the additive blend
`blended = baseline_cosine + alpha*side` the side term added nearly the same constant to every
candidate and barely moved rank. Two levers sharpen the expected document's lead:

- **IDF-scaled key-field bonus** (landed, `04f26e9`): `weighted_overlap_fraction` now adds
  `key_bonus = 0.20 + KEY_BONUS_IDF_SCALE * (weight - 1.0)` (`KEY_BONUS_IDF_SCALE = 0.75`), so a
  *rare* query term matched in a candidate's **key** (≈ its identity) widens the right-doc gap
  instead of every key-match getting a flat `+0.20`.
- The spike-bonus lever from the backlog is **already subsumed**: the current scorer's substrate
  term is the **S69/S70 competitive-field** activation `competition_spikes / field_peak_spikes`
  (graded by count in `[0,1]`), not the old flat binary `integration_spikes>0 ? 0.20`. The backlog
  text predates the S69/S70 rework.

## Verified result (this attestation, 2026-06-29)

Reproduction (deterministic; default hash/`gte-multilingual-base` backend, no model download needed
for the gate logic):

```bash
cd /Data/CascadeProjects/biocortex-rs
cargo run --release --example ab_retrieval_side_signal_adapter -- \
  /Data/CascadeProjects/agent-bridge/crates/bridge/tests/fixtures/biocortex_retrieval_gate_corpus.jsonl > /tmp/side.jsonl
cd /Data/CascadeProjects/agent-bridge
BIOCORTEX_RETRIEVAL_CORPUS=crates/bridge/tests/fixtures/biocortex_retrieval_gate_corpus.jsonl \
BIOCORTEX_RETRIEVAL_SIDE_SIGNAL=/tmp/side.jsonl \
  cargo run -q -p ab-bridge --example biocortex_retrieval_gate_eval
```

Gate criteria (`..._BENCHMARK_GATE`, "first gate is conservative") vs. measured:

| Criterion | Required | Measured @ `alpha=0.20` | |
|---|---|---|---|
| corpus size | ≥ 30 queries | 35 | ✅ |
| candidates/query | ≥ 5 | 5 (175 rows) | ✅ |
| side-signal coverage | ≥ 0.80 | 1.00 | ✅ |
| rank regressions | 0 | 0 | ✅ |
| MRR@10 lift | ≥ +0.03 | **+0.0381** (0.900 → 0.938) | ✅ |
| recall@1 | — | 0.829 → 0.886 | — |
| status | — | `side_signal_passes_offline_gate` | ✅ |

**Robustness (not a knife-edge).** An `alpha` sweep (override `BIOCORTEX_RETRIEVAL_BLEND_ALPHA`)
shows a monotone, regression-free curve that clears the bar from the conservative policy onward:

| `alpha` | 0.10 | 0.15 | **0.20** | 0.25 | 0.30 | 0.50 |
|---|---|---|---|---|---|---|
| `mrr_delta` | +0.0238 | +0.0238 | **+0.0381** | +0.0524 | +0.0667 | +0.0667 |
| regressions | 0 | 0 | **0** | 0 | 0 | 0 |
| gate | fail | fail | **pass** | pass | pass | pass |

`regressions == 0` at **every** `alpha` (the additive-only blend can only sharpen, never invert,
the expected-doc lead). The conservative contractual `alpha=0.20` clears the `+0.03` bar by ~28%;
the lift saturates at `+0.0667` by `alpha≈0.30`. The side-signal output is byte-identical across
re-runs (deterministic: the scorer uses `BTreeMap`/`BTreeSet`, plasticity blocked, homeostasis OFF).

## Boundary — what this does and does NOT authorize

Unchanged from the gate contract: **passing the offline gate does not approve runtime mutation.**
The eval still reports `runtime_adapter_approved: false` and `requires_human_review: true`, and the
gate doc's own clause — *"human review is required even if metrics pass … Passing this gate does not
approve runtime mutation. It only authorizes a follow-up runtime-boundary design."* — still governs.

So the blocker on "the body's retrieval side-signal influences AB retrieval order" has **moved**:
from *"offline gate fails (+0.019)"* (now false) to *"offline gate cleared; awaiting the human
runtime-boundary decision"* on the existing opt-in ladder
(`biocortex_retrieval_opt_in_*` → `..._authorization_decision_packet`, all behind
`AB_BIOCORTEX_RETRIEVAL_OPT_IN`, default OFF). That decision is the owner's, not this attestation's.

This attestation is **read-only**: no corpus, scorer, gate code, memory, embedding, or graph edge is
mutated; it only records a verified measurement and supersedes a stale finding. The deeper thesis
(AB outcomes shaping BioCortex *learning* — STDP/eligibility/morphology, not just retrieval order)
remains entirely unbuilt and is **not** advanced by this gate (`open_limitation=
outcomes_injected_no_autonomous_self_shaped_morphology` still holds).
