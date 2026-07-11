# Portfolio Continuity Successor Answer Trial Result

Date: 2026-07-10

Status: **TERMINAL / NO_ADVANCE_REVIEW_PROTOCOL_FAILURE**.

## Verdict

The generation checkpoint remains valid: the successor protocol completed its
fixed 24-cell matrix on the first and only claimed attempt, and its complete
postflight validation passed. The later review phase did not satisfy the
preregistered gate. Both returned review packets pass the frozen schema,
binding, completeness, and distinct-string checks, but both reviewer fields
explicitly identify Claude and share one stable base identifier. They
are therefore neither two human reviewers nor independent reviewers under the
frozen protocol.

A parallel custodian line nevertheless invoked the frozen scorer once. That
run opened the condition-labelled artifacts and returned mechanical status
`NO_ADVANCE`, but it is not an admissible answer-quality result. The formal
trial outcome is `NO_ADVANCE_REVIEW_PROTOCOL_FAILURE`; no scorer rerun or
replacement review can repair the preregistered ordering after unblinding.

```yaml
score_schema: agent_bridge.portfolio_continuity_answer_score.v2
trial_id: portfolio_continuity_successor_answer_20260710
status: NO_ADVANCE_REVIEW_PROTOCOL_FAILURE
contract_commit: e5c985d4916086bc3396ab28d2a4943b82f5df0a
contract_sha256: ef109025d1b7b7724295d075edbb7061a56f1e5a87faa643d8e6b55383f815dd
harness_source_sha256: af15d85758c4e5454a27a8f18a2e3101f60c5472c8fdc352a750ba5681e045ee
surface_source_sha256: 0ff5ab27b79d36169fee22b5de5f2c4563cb1ba0f6edebf354a17cfcb60e6311
spec_sha256: ab1fa16ae3c42021d725f804f14bae8ed13f154970b75f917fc66bb685a3fd9b
capture_sha256: 0041ed29ec778ffce824755cb0c73025252f668ca876d7d5dcc3598c416c82f9
generation_sha256: c83f62ce88f2509667f949c1dd2ebca1410537f73a4ed49d595b62b1c635d368
redacted_generation_sha256: eb7b94e1e14f6226507b101b4bda4b5aceedf2a1647bbf163a8fb4f254941c3c
blind_packet_sha256: 12a1364f59ee970956e289823608641dd83747e605fb7308ebfa4e221c416c0b
blind_map_sha256: e80693737e4afb0204cf3dd7b108c6011504f92d18364594945d5b70539b8b80
review_1_sha256: 8d6874cb3084e7b0f7b98b6f6264bd310eaa2dfa032d14ff769304a7761b4a0b
review_2_sha256: 86188b8ee4f5435d886a46a35c0fa954861990f4306d04e582b1ccd4738d2e3a
score_sha256: 32bd54632fa342e481f57d17526a11358fd35ccc38209611efc0718e6e4cf065
score_stdout_sha256: 1edaa4f51179fc69c902c437996bc129253e4ad606e05d3242213070dbcc8328
private_reviewer_declarations_sha256: bed06056b4206fcc6ffc25bad6124468412ff6db6f513cb66bf453cf5b8a516f
custodian_receipt_sha256: e09992c837ed355c6b4dd26157d72ebd945e0f600e8386c4be8e5a08ff13254d
generated_at_utc: 2026-07-10T20:25:31Z
custodian_score_completed_at_utc: 2026-07-11T00:02:45Z
generator_identity: codex-cli 0.144.1
model: gpt-5.4
reasoning_effort: medium
generation_attempt: 1
automatic_retry: false
case_count: 12
condition_count: 2
answer_count: 24
answer_chars_total: 29252
answer_chars_min: 218
answer_chars_max: 2142
generation_latency_ms_total: 653442.890
generation_latency_ms_p95: 42800.643
tool_events_observed: false
answer_postprocessing_applied: false
mechanically_valid_review_packets: 2
independent_human_reviews_completed: 0
unblinded_by_custodian: true
scorer_passes_executed: 1
mechanical_score_status: NO_ADVANCE
score_admissible: false
stratum_count: 6
mechanical_reviews_complete: true
all_abstention_pass_exploratory: true
all_reviewer_global_gates_pass_exploratory: false
all_reviewer_stratum_gates_pass_exploratory: false
advance: false
recommend_write_side_preregistration: false
runtime_promotion_allowed: false
ci_action_allowed: false
```

## Execution Record

Capture used one read-only online backup and 24 condition-isolated snapshots;
all twelve reference-coverage cases passed. Generation ran only in the
canonical detached execution worktree. A private `CODEX_HOME` containing only
authentication isolated the exact frozen CLI identity from unrelated shared-
home startup warnings before any attempt was claimed or model invoked.

The harness created the single contract-scoped attempt-1 claim and ran one
independent Codex process per fixed cell in an empty ephemeral read-only
workspace. It observed no tool events, performed no answer postprocessing or
automatic retry, emitted empty stderr, and created no failure receipt or
attempt-2 claim. Each of the five generation artifacts was written atomically
in sequence; they do not form one cross-file transaction.

Two mode-restricted handoff directories received byte-identical packet,
template, and reading-guide bytes. Both returned packets self-attested
independent review and condition blinding and contain 12 cases, 24 answer
judgments, 78 claim scores, four abstention judgments, and 12 preferences with
no missing field or tie. The frozen validator accepted them because their
free-form reviewer strings differ.

## Review-Phase Protocol Failure

The mechanical checks were insufficient for the preregistered process. Private
provenance inspection found that both reviewer strings explicitly name Claude
and reuse the same stable base identifier. Varying their suffixes made the
strings unequal but did not create either a human reviewer or an independent
second reviewer.

The current scorer checks packet structure, completeness, blind-packet
binding, two Boolean attestations, and exact reviewer-string inequality. It
does not establish that either reviewer is human, that the identities belong
to different people, or that one agent did not complete both packets. The
parallel custodian line accepted those inputs and opened the condition-labelled
generation and private map before this provenance failure was identified.

The score is retained privately as protocol-deviation evidence and was not
rerun during this audit. Its values below describe the deterministic output of
the frozen scorer for the two non-admissible packets; they are not formal
answer-quality evidence. The detailed disposition is in
`2026-07-10-portfolio-continuity-successor-review-protocol-failure.md`.

## Exploratory Score Result

The scorer assigns stable pseudonymous packet labels after sorting private
reviewer-identity hashes; it does not emit reviewer identities or notes.

| Scorer reviewer | Condition | Completeness | Current fail / uncertain | Unsupported | Usefulness mean / min | Context tokens | Preference wins | Absolute gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `reviewer_1` | `hybrid_retrieval` | 0.972973 | 1 / 2 | 2 | 4.416667 / 3 | 111,996 | 10 | fail |
| `reviewer_1` | `portfolio_digest` | 0.635135 | 8 / 3 | 3 | 3.083333 / 2 | 22,452 | 2 | fail |
| `reviewer_2` | `hybrid_retrieval` | 1.000000 | 0 / 4 | 2 | 4.583333 / 4 | 111,996 | 11 | fail |
| `reviewer_2` | `portfolio_digest` | 0.594595 | 5 / 6 | 1 | 2.916667 / 2 | 22,452 | 1 | fail |

| Scorer reviewer | Completeness drop | Usefulness drop | Token reduction | Non-inferiority | Efficiency |
| --- | ---: | ---: | ---: | --- | --- |
| `reviewer_1` | 0.337838 | 1.333334 | 0.799529 | fail | pass |
| `reviewer_2` | 0.405405 | 1.666666 | 0.799529 | fail | pass |

| Stratum | Cases | Reviewer 1 gate | Reviewer 2 gate | All reviewers |
| --- | ---: | --- | --- | --- |
| Portfolio status | 2 | fail | fail | fail |
| Portfolio retrospective | 2 | fail | fail | fail |
| Portfolio planning | 2 | fail | fail | fail |
| Dependency and risk | 2 | fail | fail | fail |
| Stale state | 2 | fail | fail | fail |
| Cross-project conflict | 2 | fail | fail | fail |

Both packets mark all four required abstention judgments as passing. Their
preferences contain no ties and favor full hybrid retrieval by `10–2` and
`11–1`. Every one of the
six two-case strata fails the complete gate for both packets, although
digest efficiency passes in all twelve reviewer-stratum slices. The global
79.9529% reduction exceeds the frozen 40% efficiency threshold.

The absolute gate requires at least 0.90 weighted completeness, zero current
failures, zero current uncertainties, zero unsupported assertions, zero
abstention failures, mean usefulness at least 4.0, and no case below 3. Full
hybrid clears completeness and usefulness globally but fails the zero-
tolerance currentness/unsupported requirements. Direct digest fails multiple
absolute thresholds and is not non-inferior to the reference.

## Validation

Post-score validation did not invoke the scorer again. It confirmed mode
`0600`, empty stderr, semantic JSON equality between score stdout and the score
artifact, the complete contract/capture/generation/blind/map/review hash chain,
the fixed output privacy boundary, and the final gate aggregation.

An independent arithmetic check recomputed absolute, non-inferiority,
efficiency, abstention, and combined gates from the safe score output and
frozen thresholds for 14 packet slices: two global slices plus all twelve
packet-stratum slices. It reproduced every delta and Boolean. An exact-value
scan found no private prompt, query, context, answer, opaque answer id,
reviewer identity, or review note in the score artifact or stdout.

## Interpretation

The exploratory mapping labels `portfolio_digest` as the lower-scoring
condition. Across the two non-admissible packets it has five to eight
currentness failures, three to six currentness uncertainties, completeness
below 0.64, and mean usefulness below 3.09. The objective context accounting
shows a 79.9529% reduction. The judgment-derived values are useful hypotheses
for a future preregistration, but they are not formal comparative evidence and
do not endorse either condition for production.

## Methodological Caveats

- This is a fixed 12-case, six-stratum trial with two mechanically complete but
  nonhuman and non-independent review packets. It is not a benchmark or a
  generalization claim.
- Currentness and answer-quality judgments in the exploratory score cannot be
  promoted to formal evidence. A future trial must collect valid human reviews
  under a fresh frozen sequence rather than reinterpret this score.
- Public score metrics are rounded to six decimal places. Independent
  arithmetic validation reproduced the packet-level computations; that check
  does not cure the reviewer-provenance failure.
- Reviewer declarations and free-text observations remain private and are not
  used as public score evidence.

## Privacy And Boundaries

Raw capture, generation, seed, private map, reviews, reviewer identities,
notes, private Codex home, and claim remain in ignored mode-restricted paths.
The public result contains only committed identities, hashes, aggregate
metrics, scorer condition labels, and boundary facts. The live Agent-Bridge
store was not written by capture, generation, review, or scoring.

## Terminal Boundary

There is no remaining gate inside this trial. The single scoring pass has been
consumed and unblinding has occurred before two valid human reviews. Do not
rerun generation, substitute new reviews, rerun scoring, or use the exploratory
metrics to preregister a write-side trial.

Any future answer-quality trial requires a separate preregistration, fresh
blinding and execution identity, and a reviewer-provenance gate that does not
treat free-form string inequality or self-attestation as proof of human
independence. No runtime, digest, retrieval-default, benchmark, CI, release,
version, tag, or deployment action is authorized.

## Repository Files

```text
scripts/eval/portfolio_continuity_answer_trial.py
scripts/eval/fixtures/portfolio_continuity_successor_answer_contract.json
scripts/verify-portfolio-continuity-answer-trial.sh
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-successor-protocol-prereg.md
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-successor-capture-result.md
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-successor-answer-trial-result.md
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-successor-review-protocol-failure.md
```

## Verification

```bash
python3 -m py_compile scripts/eval/portfolio_continuity_answer_trial.py
bash -n scripts/verify-portfolio-continuity-answer-trial.sh
python3 scripts/eval/portfolio_continuity_answer_trial.py validate-contract \
  --contract scripts/eval/fixtures/portfolio_continuity_successor_answer_contract.json
bash scripts/verify-portfolio-continuity-answer-trial.sh
git diff --check
```
