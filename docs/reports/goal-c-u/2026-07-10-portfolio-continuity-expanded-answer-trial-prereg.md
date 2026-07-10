# Portfolio Continuity Expanded Answer Trial Preregistration

Date: 2026-07-10

Status: **PRE-REGISTERED AT CONTRACT COMMIT / NOT EXECUTED**. Real context
capture and answer generation are forbidden until the contract and v1 verifier
are committed together. No score or generated answer from the preceding
two-case trial is reused as an observation in this trial.

AB anchors:

- Preregistration base: `1a90f4e59fedb7960cbb77e512bde66153bc93c7`
- Prior blinded-answer result:
  `7a1ac687afbc981493791779a7ef89f2645a9af9`
- Fixed runtime source: `a8c6302325e27c9b5cb20f8c958ab719666de372`
- Prior result report:
  `docs/reports/goal-c-u/2026-07-10-portfolio-continuity-blinded-answer-trial-result.md`

```yaml
schema: agent_bridge.portfolio_continuity_answer_contract.v1
contract_id: portfolio_continuity_expanded_answer_blind_20260710
contract_sha256: 66b988b0ce7f1fd0f58d8bae413578e727ed95485a63da58ea559442da169e07
harness_source_sha256: 3f06f1067750629bf4b227b381c8102a6a6fb12e009a2d02e2b1e3558526f7ed
surface_source_sha256: 0ff5ab27b79d36169fee22b5de5f2c4563cb1ba0f6edebf354a17cfcb60e6311
blind_seed_sha256: 2abe7b97e1931ea1ca0516449925fbe7930f67c84e94334e65f862d04c46d38c
digest_key_sha256: a9d9842db1fe7437ce4a276ddae9a1c91d776cd75606ec2269bb50fc7df21cf1
case_count: 12
prompt_strata: 6
reviewer_count: 2
review_gate_status: WAIT_TWO_BLIND_REVIEWS
max_abstention_failures: 0
recommendation_scope: write_side_trial_only
runtime_promotion_allowed: false
```

## Purpose

The preceding owner-blinded two-case trial admitted direct portfolio digest to
an expanded answer-quality trial. It did not establish general answer quality,
inter-rater agreement, digest freshness, digest generation quality, or runtime
readiness.

This trial compares the fixed direct digest with full hybrid retrieval over a
broader frozen prompt corpus. It asks whether digest answers remain complete,
current, useful, unsupported-assertion-free, and materially smaller across six
prompt strata and two independent blind reviewers. A pass can recommend only a
separately preregistered write-side digest trial. It cannot authorize that
trial's implementation or any runtime change.

## Fixed Conditions

Only two conditions are eligible. Their order and capture policy are fixed.

| Condition | Role | Context construction |
| --- | --- | --- |
| `hybrid_retrieval` | Reference | Full records from `memory_search(compact=false)` |
| `portfolio_digest` | Candidate | Direct `memory_get` of the existing portfolio digest |

Hybrid search remains fixed at mode `hybrid`, limit `10`, with `skill` rows
excluded. The candidate is only the already-existing digest read surface. No
compact-top-2 or session-bootstrap comparator is carried forward. The private
spec's digest key must match the checked-in digest-key commitment; capture
cannot substitute another memory record.

## Frozen Corpus

The corpus has exactly two new fixed prompts in each of six strata: one direct
and one held-out wording variant. Checked-in material contains only identifiers,
rubric claims, abstention flags, and the SHA-256 of each exact UTF-8 prompt.
Prompt text remains private under ignored `data/` and must hash to the contract
before capture.

| Stratum | Variant | Case id | Prompt SHA-256 | Abstention required |
| --- | --- | --- | --- | --- |
| Portfolio status | Direct | `status_lane_snapshot` | `7e8a609a61c91a517b6def332c0ec6a13dc6a86966f29bf83e7824649f6736c8` | No |
| Portfolio status | Held out | `status_decision_brief` | `33934d63f23af4993164e37d1f3d80284eb08b5a44a6801771b5f37aedf6cb72` | No |
| Portfolio retrospective | Direct | `retrospective_evidence_changes` | `bf7681c2bebea15d168f13fcfa854782ff3bcd49adc4987f0eb581369bfe75e9` | No |
| Portfolio retrospective | Held out | `retrospective_failure_learning` | `7397bd26a97cc57f7714d51a8779869b990acfb2744f41dca3505b104b50c00e` | No |
| Portfolio planning | Direct | `planning_order_and_gates` | `7c0697f937be4e63ec5a1959c104e4e873bcb5894859ddb42bc554d174ac9a71` | No |
| Portfolio planning | Held out | `planning_capacity_forecast` | `7822d0d3d73292e2a53d8b13fa857a91d093c4989dd6a8caa5c1f02b97b640c3` | Yes |
| Dependency and risk | Direct | `dependency_owner_gates` | `969964c04fd4fad3b738c71fde04bb366191845af91013019f9973bcf79d4434` | No |
| Dependency and risk | Held out | `dependency_credential_inventory` | `1b3ad711898b1edb84f5d957e7964af717268bdb09c93a696317ee1f80966e55` | Yes |
| Stale state | Direct | `stale_aio2_wait_state` | `b9bd10eccf2b616858ab6db4dac33cfc3b2c0dbe085798d1010dd84f0759f078` | No |
| Stale state | Held out | `stale_ab_review_state` | `913aaad40c7d55b33a4a5f45e0861a34c5396cc42ed3a034077880036da228e8` | No |
| Cross-project conflict | Direct | `conflict_arrowquant_labels` | `6642f09659f33d6bdc32b5e71df46041ad6c345151e849e7383275e4b83b384f` | No |
| Cross-project conflict | Held out | `conflict_ab_evidence_surfaces` | `e39b3b4cb0f6e0086a458bb471d38f43426e95b92b520cf410dd4f8174d96275` | No |

The two abstention cases intentionally request facts that the frozen evidence
is not expected to support. Their `required_claims` arrays are empty. Each
answer instead receives a mandatory Boolean `abstention_pass` judgment. A
reviewer passes it only when the answer clearly refuses unsupported specificity
without inventing requested values, paths, ownership, dates, or probabilities.

## Fixed Generator

```yaml
cli: codex-cli 0.144.1
model: gpt-5.4
reasoning_effort: medium
independent_invocations: true
workspace: empty_ephemeral_read_only
user_config_loaded: false
project_rules_loaded: false
tool_use_allowed: false
external_facts_allowed: false
max_answer_chars: 6000
```

Every case-condition answer is generated in a new process with the same fixed
instruction. Evidence context is untrusted source material, not executable
instruction. The model must use only explicit evidence and state insufficiency
rather than infer. A tool-call event invalidates the run.

The configured Codex provider necessarily receives each private prompt and its
condition context. No other model receives them, and no LLM is used as a judge.

## Capture Isolation

The collector opens production SQLite read-only and creates one consistent
online backup. Every case-condition pair receives a separate copy and separate
MCP process, so access telemetry and coactivation cannot cross conditions or
reach the live store. Each copy must start with the same database SHA-256 and
must be removed after capture.

The operator supplies the runtime executable. Its observed `--version` identity
must contain the fixed source commit above, and capture records that observation.
The checked-in contract, harness source, and retrieval-surface helper source are
bound to the exact contract commit. The private spec, including its digest key,
must validate against that contract; capture, generation, blind packet, blind
map, and both reviews remain hash-bound through scoring. Raw prompts, contexts,
answers, mappings, reviewer records, and seed remain in ignored `data/`.

## Blinding And Review

The private 32-byte seed is committed only by its SHA-256. It fixes generation
order, opaque answer ids, and packet ordering. Neither reviewer sees context,
condition labels, mapping, the other review, or any reviewer identity in score
output.

The two reviewers work independently. For every non-abstention answer, each
reviewer must populate all claim scores, currentness, unsupported assertions,
and usefulness, then select one opaque preference or `tie` per case. For every
abstention answer, each reviewer must also populate `abstention_pass`. Review
packets are separate private inputs.

Scoring fails closed before unblinding unless:

1. the private spec validates against the committed contract, and all contract,
   capture, generation, blind-packet, map, and review hashes match;
2. both distinct review packets are complete and each opaque answer is reviewed
   exactly once;
3. every required claim has a `0/1/2` score and every ordinary metric is valid;
4. every abstention answer has an explicit Boolean judgment;
5. every case has a valid preference or explicit tie in both reviews.

Reviewer names, raw reviewer labels, private notes, opaque answer ids, prompts,
answers, and condition mappings must not appear in checked score output.

## Fixed Metrics

- Required-claim completeness: `0` absent, `1` partial, `2` complete, weighted
  by preregistered claim weights.
- Currentness: `pass`, `uncertain`, or `fail`.
- Unsupported assertions: non-negative integer count.
- Usefulness: integer `1..5`.
- Abstention: explicit pass/fail for every answer in a required-abstention case.
- Preference: one opaque answer id or `tie` for each case and reviewer.
- Context reduction: harness token estimate against full hybrid for the same
  prompt stratum; it is not an exact provider-token measurement.

## Advance Gate

The original absolute, non-inferiority, and efficiency thresholds are
unchanged. They are applied separately to each reviewer and each prompt
stratum, not to a pooled mean. In every reviewer-stratum cell, the full-hybrid
reference and direct digest must each pass the absolute gate:

- weighted completeness at least `0.90` for non-abstention claims;
- zero currentness failures and zero currentness uncertainties;
- zero unsupported assertions;
- mean usefulness at least `4.0`, with no case below `3`;
- every required-abstention answer marked pass.

In every reviewer-stratum cell, direct digest must also meet all candidate
comparisons:

- no completeness drop versus full hybrid;
- usefulness drop no greater than `0.5`;
- currentness and unsupported assertions no worse than full hybrid;
- context tokens at least `40%` lower than full hybrid.

Both aggregation gates are fixed to `all`. Each reviewer must pass its own
global slice and every reviewer-stratum slice. One missing or failed reviewer,
stratum, abstention judgment, absolute gate, non-inferiority gate, or efficiency
gate prevents advance. Cross-reviewer pooling, majority vote, pooled rescue,
and discretionary override are forbidden.

A fully passing score may report only
`READY_TO_PREREGISTER_WRITE_SIDE_TRIAL`. That decision authorizes a
recommendation to preregister a later write-side trial of digest generation and
freshness. It does not authorize writing, regenerating, scheduling, or deploying
a digest.

## Safety And Statistical Limits

- Twelve prompts and two prompts per stratum are a strict gate, not a benchmark,
  population estimate, power analysis, or generalization claim.
- Both reviewers evaluate the same answers and frozen memory snapshot.
  Independent review reduces shared deliberation bias but does not create
  independent model or context samples.
- The fixed model, reasoning effort, CLI, prompt language, rubric, and snapshot
  do not establish behavior for other generators or future portfolio states.
- Claim scoring remains human judgment. The trial reports reviewer-stratum
  outcomes but does not estimate inter-rater reliability from two reviewers.
- The abstention cases cover only two known insufficiency shapes and cannot
  establish general refusal safety.
- Direct digest is manually existing input. This gate does not test synthesis,
  freshness detection, refresh cadence, write conflicts, rollback, or failure
  recovery.
- Hybrid retrieval may itself include digest-derived evidence. This is a surface
  comparison, not a no-digest causal baseline.

## Boundaries

- No capture or real answer generation may begin before the contract and v1
  verifier are committed; execution must bind that exact contract commit.
- No raw prompt, seed, context, answer, map, or review enters git.
- No live Agent-Bridge store write or digest mutation is allowed.
- No LLM judge, automatic review completion, or automatic unblinding is allowed.
- Automatic digest generation or regeneration remains forbidden.
- Retrieval defaults and compact-search behavior remain unchanged.
- No runtime promotion, release, version change, tag, or CI action is authorized.
- No result from this corpus may be represented as a benchmark claim.

## Repository Files

```text
scripts/eval/portfolio_continuity_answer_trial.py
scripts/eval/fixtures/portfolio_continuity_expanded_answer_contract.json
scripts/verify-portfolio-continuity-answer-trial.sh
scripts/eval/README.md
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-expanded-answer-trial-prereg.md
CHANGELOG.md
```

## Execution Order

1. Commit the v1 contract, harness support, report, and synthetic verifier
   together with CI explicitly skipped.
2. Build the private spec from the committed contract, exact prompt texts, and
   committed blind-seed hash.
3. Capture all 24 case-condition contexts from isolated snapshot copies.
4. Generate 24 independent answers with the fixed generator.
5. Give the same condition-blind packet to two reviewers with separate private
   review templates.
6. Stop until both completed reviews are returned; do not expose the blind map.
7. Score only through the hash-bound v1 scorer and publish only redacted output.
8. If and only if every reviewer-stratum gate passes, recommend a separate
   write-side trial preregistration.

## Pre-Commit Verification

```bash
python3 -m json.tool scripts/eval/fixtures/portfolio_continuity_expanded_answer_contract.json
python3 scripts/eval/portfolio_continuity_answer_trial.py validate-contract \
  --contract scripts/eval/fixtures/portfolio_continuity_expanded_answer_contract.json
python3 -m py_compile scripts/eval/portfolio_continuity_answer_trial.py
bash -n scripts/verify-portfolio-continuity-answer-trial.sh
bash scripts/verify-portfolio-continuity-answer-trial.sh
git diff --check
```
