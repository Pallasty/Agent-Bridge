# Portfolio Continuity Blinded Answer Trial Result

Date: 2026-07-10

Status: **COMPLETE / READY_FOR_EXPANDED_TRIAL**

AB anchors:

- Scope memory: `portfolio_continuity_blinded_answer_trial_scope_20260710`
- Preregistration memory:
  `portfolio_continuity_blinded_answer_trial_preregistered_20260710`
- Owner-review wait memory:
  `portfolio_continuity_blinded_answer_trial_wait_owner_review_20260710`
- Forum thread: `design#119`, review-wait post `3040`

## Verdict

The owner-blinded two-case trial admits `portfolio_digest` to an expanded
answer trial. It does not admit `compact_then_get_top2`.

The direct digest retained weighted claim completeness `1.0`, had no
currentness uncertainty or unsupported assertions, scored mean usefulness
`4.5`, and used `78.9574%` fewer context tokens than full hybrid retrieval.
The compact-then-top-2 condition used `52.8750%` fewer tokens, but completeness
fell to `0.5`, both cases were marked currentness-uncertain, and three
unsupported assertions were recorded.

This verdict has `expanded_trial_only` scope. It does not authorize automatic
digest regeneration, a compact-search default change, runtime promotion,
version or tag changes, release action, or CI.

```yaml
score_schema: agent_bridge.portfolio_continuity_answer_score.v0
trial_id: portfolio_continuity_answer_blind_20260710
status: READY_FOR_EXPANDED_TRIAL
recommendation_scope: expanded_trial_only
contract_commit: bf0ec41abaf7749feb60ead77951657b9529925e
contract_sha256: f1dbaa335f082d329c2fe01d3681df14046df720351d22d300663bcb4a6acd1f
scorer_commit: ea7d09b1af9f97fa8ea0a9e977c3531368860eb2
scorer_source_sha256: 106740c0426c5fb2c5c8882dd59e5f03d800e5334fe1d53c97f714a58c097def
capture_sha256: ec2def7c7601626198f985071d166699fb57b540373d7df1a95f8e64ebf4990f
generation_sha256: 13e7423414de8d3bd7fb7d1f8b532c2bfa72726ba3d3bb5bac89fc64055b0ff9
blind_packet_sha256: fc5d783bcbdd0773fb589a5a727e247fbd34f140ba51c87b718ffc656bb82201
blind_map_sha256: d53c03942a7a7e2335bad465c2476413a617791bf345b858633e956a53cba51b
review_sha256: 0747f57b8cbb80597a98aca5f2c33aef5eb5e63b7b530eaca80b7b7105d14ea0
score_sha256: e8ebba1f070c7e436703d290fd254ca73860bbc057f3504d2c4d667bb0c52738
raw_private_material_in_git: false
runtime_promotion_allowed: false
```

## Aggregate Results

| Condition | Absolute gate | Weighted completeness | Currentness uncertain / fail | Unsupported assertions | Mean / minimum usefulness | Context tokens | Preference wins |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `hybrid_retrieval` | PASS | 1.000000 | 0 / 0 | 0 | 5.0 / 5 | 17,878 | 1 |
| `compact_then_get_top2` | FAIL | 0.500000 | 2 / 0 | 3 | 2.0 / 2 | 8,425 | 0 |
| `session_bootstrap` | FAIL | 0.708333 | 0 / 0 | 2 | 3.5 / 3 | 7,238 | 0 |
| `portfolio_digest` | PASS | 1.000000 | 0 / 0 | 0 | 4.5 / 4 | 3,762 | 1 |

There were no per-case preference ties. Full hybrid and direct digest each won
one of the two case preferences.

## Candidate Decisions

| Candidate | Token reduction vs full hybrid | Completeness drop | Usefulness drop | Efficiency | Non-inferiority | Advance |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `compact_then_get_top2` | 52.8750% | 0.500000 | 3.0 | PASS | FAIL | NO |
| `portfolio_digest` | 78.9574% | 0.000000 | 0.5 | PASS | PASS | YES |

The full-hybrid reference passed its absolute gate, so candidate comparison was
admissible under the preregistered contract. Session bootstrap was a diagnostic
comparator and was never eligible to advance.

## Review And Unblinding Discipline

The owner completed all rubric fields for eight opaque answers and both case
preferences before unblinding. The completed review was frozen at SHA-256
`0747f57b8cbb80597a98aca5f2c33aef5eb5e63b7b530eaca80b7b7105d14ea0`.

The executed scorer source was byte-identical to its last code change at
`ea7d09b1af9f97fa8ea0a9e977c3531368860eb2`, with source SHA-256
`106740c0426c5fb2c5c8882dd59e5f03d800e5334fe1d53c97f714a58c097def`.

The scorer validated the contract, capture, blind packet, and complete review
before opening the condition-labelled generation packet or blind map. Its
checked output contains no raw prompt, context, answer, opaque answer id,
review note, or reviewer identity. Raw trial material remains under the ignored
private directory:

```text
data/eval/portfolio-continuity-answer-blind-20260710/
```

## Interpretation

- Direct digest is the only candidate worth carrying into the next trial. Its
  result combines the lowest context cost with answer quality inside the fixed
  non-inferiority margin.
- Compact-then-top-2-get should not be widened in its current rank-only form.
  Token savings did not compensate for lost claim coverage and unsupported
  inference.
- Session bootstrap remains useful for session orientation, but this trial does
  not support treating it as a complete portfolio-status answer surface.
- Full hybrid remains the reference condition. This trial supplies no reason
  to change its current behavior.

## Limitations

- The trial contains two strategic prompt classes, one captured memory state,
  one fixed model/configuration, and one owner reviewer. It is a gate, not a
  benchmark or generalization result.
- The same owner supplied all blinded scores. Blinding limits condition bias but
  does not measure inter-rater reliability.
- Context token counts use the trial harness estimator rather than an exact
  model tokenizer. Generation latency was recorded but not preregistered as an
  advance criterion.
- The direct digest was already present and manually synthesized. This result
  does not test digest creation, refresh cadence, staleness detection, or
  failure recovery.
- Hybrid retrieval already surfaced digest evidence. The comparison measures
  answer behavior from the observed context surfaces, not a no-digest runtime
  baseline.

## Next Gate

Preregister an expanded, owner-blinded trial that compares only full hybrid and
direct digest across a broader frozen corpus. The corpus should cover at least
project status, retrospective, planning, dependency/risk, stale-state, and
cross-project conflict prompts, with held-out prompt wording and explicit
abstention cases. Preserve the same claim-level rubric and non-inferiority
thresholds, add prompt-stratum reporting and a second blinded reviewer, and
keep digest freshness/refresh behavior outside this answer-quality gate.

Only after that expanded trial passes should a separate write-side experiment
evaluate digest generation and freshness. Any runtime promotion would require
its own preregistration, rollback plan, and operational guardrails.

## Repository Files

```text
scripts/eval/portfolio_continuity_answer_trial.py
scripts/eval/fixtures/portfolio_continuity_answer_contract.json
scripts/verify-portfolio-continuity-answer-trial.sh
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-blinded-answer-trial-prereg.md
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-blinded-answer-trial-result.md
```

## Verification

```bash
python3 -m py_compile scripts/eval/portfolio_continuity_answer_trial.py
bash -n scripts/verify-portfolio-continuity-answer-trial.sh
bash scripts/verify-portfolio-continuity-answer-trial.sh
git diff --check
```
