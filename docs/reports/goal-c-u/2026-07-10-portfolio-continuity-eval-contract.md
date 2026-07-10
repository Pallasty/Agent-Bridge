# Portfolio Continuity Evaluation Contract

Date: 2026-07-10

Source base commit: `dda3f26e`

Run type: no-write compositional continuity measurement contract

AB anchors:

- Durable scope memory: `portfolio_continuity_eval_contract_scope_20260710`
- Parent direction memory: `ab_memory_evolution_direction_20260710`
- Gate A decision: `ab_gate_a_ppr_typed_edge_door_closed_20260710`
- Forum thread: `design#119`, post `3026`

## Verdict

The first portfolio-continuity scoring contract is implemented and locally
verifiable. It does not generate a digest and does not claim live digest
quality. It establishes the deterministic measurement boundary required before
comparing retrieval, `session_handoff`, or a future prebuilt portfolio digest.

```yaml
schema: agent_bridge.portfolio_continuity_eval.v0
stage: measurement_contract
fixture_scope: synthetic fixtures only
claim_ids_are_review_labels: true
natural_language_semantics_scored: false
raw_content_in_output: false
raw_evidence_keys_in_output: false
calls_llm: false
calls_retrieval: false
reads_ab_store: false
writes_ab_store: false
benchmark_performance_claim: false
runtime_promotion_allowed: false
```

## Why This Lane

The AB-native typed-edge Gate A has already closed the PPR/GNN retrieval lane:
existing retrieval places relational gold in the top ten, while the active
typed graph is too sparse to justify heavier traversal. The dominant unresolved
workload is different: about 61% of recent misses are two broad owner prompts
asking for project status, vision, disproven paths, concerns, and next steps.

Those prompts have no single gold memory key. Mapping either prompt to one
`expected_key` and scoring MRR, as the old retrieval fixture does, confuses
evidence assembly with single-item lookup.

Existing local surfaces do not close that measurement gap:

- `scripts/eval/ab_eval.py` continuity checks whether fixed bootstrap anchors
  are visible, not whether a compositional answer is complete and current.
- `snapshot_daily_*` records system telemetry/topology, not project claims.
- `session_handoff` aggregates todos, recent handoffs, and git state, but has no
  required-claim, stale-evidence, or unsupported-claim scorer.

## Contract Shape

The fixture defines versioned cases with:

```text
case_id
prompt_class
as_of
requires_abstention
evidence_catalog[]
required_claims[]
optional_claims[]
forbidden_claim_ids[]
thresholds
```

Each required or optional claim declares one or more accepted evidence keys.
Evidence carries explicit lifecycle state and validity bounds. A candidate
contains only redacted claim ids, confidence labels, evidence keys, token cost,
and latency. It does not carry answer prose.

Every fixture and candidate object has an explicit field whitelist. Claim,
case, condition, and evidence identifiers must be bounded machine labels;
duplicate JSON fields are rejected; numeric diagnostics must be finite; and
abstained claims cannot carry evidence references. These checks keep the
evaluation packet structured and prevent free-form content from leaking through
extension fields or error diagnostics.

Claim ids are review labels. An upstream deterministic normalizer or human
review must map a candidate answer to those labels. This scorer does not use
string overlap to pretend that it understands natural-language semantics.

## Metrics

Primary outcome metrics:

| Metric | Meaning |
| --- | --- |
| `supported_claim_coverage` | Weighted required claims backed by accepted, currently valid evidence |
| `evidence_precision` | Evidence references that are accepted and current for their labeled claim |
| `case_pass_count` | Cases satisfying every configured quality and abstention gate |

Safety diagnostics:

| Metric | Failure represented |
| --- | --- |
| `stale_evidence_ref_count` | Superseded, archived, unknown-status, or time-invalid evidence presented as current |
| `unknown_evidence_ref_count` | Candidate references outside the case evidence catalog |
| `unsupported_claim_count` | Non-abstained claim id absent from required/optional/forbidden sets |
| `forbidden_claim_count` | Explicitly invalid claim such as declaring an unresolved release complete |
| `unsupported_evidence_claim_count` | Supported claim without accepted current evidence |
| `abstention_pass_count` | Insufficient-evidence cases that abstain without smuggling claims/evidence |

`context_tokens_total` and `latency_ms_p95` are recorded over candidate-present
cases only. `candidate_case_count` and `cost_diagnostics_complete` disclose
whether that diagnostic population covers the whole fixture. The contract does
not set product targets before a real baseline exists.

## Fail-Closed Verification

The checked-in candidate passes all three synthetic contract cases:

1. current project status;
2. project retrospective;
3. insufficient evidence requiring abstention.

The verifier derives and rejects nine quality-failing candidates:

- a superseded evidence reference;
- a missing required claim;
- an unsupported claim;
- an explicitly forbidden claim;
- a false answer where abstention is required;
- an unknown evidence key;
- a current but claim-incompatible evidence reference, isolating precision;
- a missing fixture case;
- an uncertain required claim, exercising weighted support separately from
  claim presence.

It separately rejects candidate packets containing raw `text`, `content`,
`answer`, `question`, or `prompt` fields; unknown extension fields; free-form
claim/evidence identifiers; duplicate JSON fields; non-finite or unrepresentable
numeric diagnostics; or evidence attached to an abstained claim. Output packets
expose bounded case/claim labels and aggregate counts but never echo evidence
keys.

Fixture validation also rejects any required/optional claim whose accepted set
contains no evidence that is current at the case's `as_of` boundary. Abstention
has an independent aggregate gate, and non-abstention cases cannot be vacuous:
they must define at least one required claim. These constraints remain
fail-closed even if a future experiment relaxes the all-cases threshold.

## Files

```text
scripts/eval/portfolio_continuity_eval.py
scripts/eval/fixtures/portfolio_continuity_contract.json
scripts/eval/fixtures/portfolio_continuity_candidate_pass.json
scripts/verify-portfolio-continuity-eval.sh
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-eval-contract.md
```

## Boundaries

This packet:

- uses synthetic fixtures only;
- does not read or export private AB memory content;
- does not call `memory_search`, `session_bootstrap`, or `session_handoff`;
- does not call an LLM, API, or external benchmark runner;
- does not write the AB store, graph, telemetry, forum, or approval state;
- does not generate or persist a portfolio/session digest;
- does not change retrieval order, ranking, consolidation, bootstrap, runtime,
  MCP surface, schema, version, release, or benchmark policy;
- does not claim live digest quality or benchmark performance.

## Verification

```bash
python3 -m py_compile scripts/eval/portfolio_continuity_eval.py
bash -n scripts/verify-portfolio-continuity-eval.sh
scripts/verify-portfolio-continuity-eval.sh
git diff --check
```

## Next Step

Create a separate, version-bound AB-native corpus packet for the two observed
strategic prompt classes. It should define reviewed required/optional/forbidden
claim labels and evidence sets without checking private prose into the repo.

Then add no-write adapters that convert three candidate conditions into this
contract:

1. single-query retrieval evidence;
2. current `session_handoff` evidence;
3. a temporary prebuilt portfolio digest evidence bundle.

Only after those conditions produce comparable packets should an answer-stage
normalizer or blinded human review score natural-language quality. Durable
digest generation and runtime admission remain separate later decisions.
