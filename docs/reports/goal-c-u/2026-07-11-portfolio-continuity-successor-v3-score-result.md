# Portfolio Continuity Successor V3 Score Result

Date: 2026-07-11 PDT

Status: **COMPLETE / NO_ADVANCE / ANSWER TRIAL CLOSED**. The two fixed blind
reviews passed their provenance gate, the scorer atomically consumed the one
authorized score claim, and the frozen all-reviewer/all-stratum rule rejected
`portfolio_digest`. This result does not open a write-side trial.

## Verdict

The observed direct portfolio digest reduced estimated context tokens by
`80.9257%`, but both fixed reviewers found material answer-quality loss. The
candidate failed its absolute and non-inferiority gates for both reviewers,
failed every one of the six prompt strata, and received zero of 12 case
preferences from either reviewer.

The admissible v3 result is therefore `NO_ADVANCE`. Full hybrid retrieval
remains the answer-stage reference. This trial does not establish that a
portfolio digest can never be useful; it establishes that the frozen digest
snapshot and answer surface evaluated here are not safe to advance.

## Frozen Chain

```yaml
implementation_commit: 1d2da68181a276a71da36688f53c8f26f3770b50
contract_sha256: da9e190492d74824159bbff18eaeff02a4848921989f4077072f126e1d4e4bcc
capture_sha256: 35131cec096d5bb2bee481aee34c9fcc0f599431f5543cf791dec4f84f6da973
generation_sha256: 6b7de6a7ac1d32f35cc76117158d2e59765938bb3301e0eabaf83e22e1e0adc0
blind_packet_sha256: 50badd6c677963e0ba91cf7ad9e873c9ca8b2ff14c56d2d2ea08102b8b449f33
blind_map_sha256: 7fcfb4a793cf4677be35b9258a18ab489065daba948417a07a68f7be2cc9a04e
reviewer_anthropic_opus_review_sha256: 028530c76aae07f88a3dff0b0be46d86c7b79bee642c09e59e271e4f8b4130d0
reviewer_anthropic_opus_receipt_sha256: 7859b60edb62821b7bca0d417d43295202153a997c04a5307031dd8d1575aba6
reviewer_openai_sol_review_sha256: 765019cad54c21ae2fda5b5c85adcf36f54745d4dd3cb08a5f88f22f36543e23
reviewer_openai_sol_receipt_sha256: 92533965cc1550639da4ad469b8e129297f814a4e36622facd17181480fe2c8d
score_claim_identity_sha256: 91e0365f2a6a29c291b52ab5850bc85219231f53d402eec07b201768cfd67237
score_claim_sha256: 65cfb01663d3f28a7f4162a8de14388db822bd2baa5fb730984f7ade0ebaecf1
score_sha256: df3047dc654255489baf540f4339fb8714b45c51f1e8e49f8d990435b57ad1c1
score_schema: agent_bridge.portfolio_continuity_answer_score.v3
score_status: NO_ADVANCE
```

## Single-Use Scoring

The final preflight revalidated the contract, capture, blind packet, both
reviews, receipts, commands, and byte-identical raw responses in the frozen
Claude-then-Codex slot order. It also confirmed distinct review, session, and
empty-workspace identities; private mode `0600`; ignored and non-aliasing
paths; unchanged generation/map hashes; and absent claim/output paths.

The deterministic claim identity was derived from the score-claim schema and
contract hash. At `2026-07-11T13:40:57Z`, the scorer created that claim with
`O_EXCL`, then and only then opened the condition-labelled generation and map.
The sole score invocation exited zero in under one second, emitted no stderr,
and was not retried. The private claim directory is mode `0700`; the claim,
score, stdout, and stderr artifacts are mode `0600` under ignored `data/`.

## Global Results

| Metric | Claude Opus 4.8 | Codex GPT-5.6-sol |
| --- | ---: | ---: |
| Reference weighted completeness | 1.000000 | 0.986486 |
| Digest weighted completeness | 0.432432 | 0.560811 |
| Completeness drop | 0.567568 | 0.425675 |
| Reference mean usefulness | 4.750000 | 4.833333 |
| Digest mean usefulness | 2.666667 | 3.083333 |
| Usefulness drop | 2.083333 | 1.750000 |
| Digest currentness failures | 11 / 12 | 11 / 12 |
| Digest unsupported assertions | 48 | 31 |
| Digest context token reduction | 80.9257% | 80.9257% |
| Digest preference wins | 0 / 12 | 0 / 12 |
| Candidate absolute gate | FAIL | FAIL |
| Candidate non-inferiority gate | FAIL | FAIL |
| Candidate efficiency gate | PASS | PASS |
| Reviewer global gate | FAIL | FAIL |

The reference received all 12 preferences from each reviewer. Both reviewers
passed all four answer-level abstention checks. Abstention success does not
rescue the candidate because the frozen gate also requires absolute quality,
non-inferiority, efficiency, every reviewer, and every stratum to pass.

## Stratum Gate

| Prompt stratum | Claude gate | Codex gate | All-reviewer gate |
| --- | --- | --- | --- |
| `portfolio_status` | FAIL | FAIL | FAIL |
| `portfolio_retrospective` | FAIL | FAIL | FAIL |
| `portfolio_planning` | FAIL | FAIL | FAIL |
| `dependency_risk` | FAIL | FAIL | FAIL |
| `stale_state` | FAIL | FAIL | FAIL |
| `cross_project_conflict` | FAIL | FAIL | FAIL |

There is no narrow passing stratum to carry forward. Every candidate stratum
passed the token-efficiency threshold and failed absolute quality and
non-inferiority for both reviewers.

## Reviewer Agreement

The two providers agreed on all 12 pairwise preferences and all four
abstention judgments. Agreement was `91.6667%` for currentness and `85.8974%`
for claim scores. Usefulness agreement was `66.6667%`; exact unsupported-count
agreement was `37.5%`. The frozen contract uses neither pooled reviewer means
nor agreement metrics to rescue a gate, so these values are descriptive only.

## Independent Audits

A separate implementation that did not import the frozen scorer recomputed
both reviewers, all six strata, the global decision, and cross-reviewer
agreement. It also verified the claim/hash chain, semantic stdout/output
identity, empty stderr, private permissions, and absence of raw prompts,
contexts, answers, answer IDs, or review notes in the score packet.

```yaml
deterministic_audit_sha256: d5e7ffa404f11678a56e392385331a2d423705f7915fdcc3117ea9982b556601
deterministic_audit_status: PASS
privacy_scan: PASS
reviewers_recomputed: 2
strata_recomputed: 6
```

An isolated Codex GPT-5.4/medium post-score auditor then received only the
frozen public contract, public score, and deterministic audit summary. It ran
in an empty read-only workspace with no project rules, user config, MCP, web,
or tool event. Its four-event stream contained one agent message and no other
item.

```yaml
audit_request_sha256: 92391337660160babe57cda5d17adcbaeafd5507242596668d7ae49273cff488
audit_raw_response_sha256: 9f81a9210f7b9601a423f11aa77f071f1b155eb7dc1ae106bfa3c2e6072f9fd6
audit_decision_sha256: d2c70dc8b74aae098163ab8bc1d10c8c12a5d70b719b27860c8378e3bfe3170b
audit_receipt_sha256: 0296eb3eeb95e21464baade6fe55cd77d92ba9a172957fd2d4c4c282b1c56d46
audit_decision: PASS
audit_scored_status: NO_ADVANCE
audit_next_gate: CLOSE_ANSWER_TRIAL_NO_ADVANCE
audit_blocker_count: 0
```

## Interpretation

- The candidate's cost advantage is real within the frozen estimator, but it
  is dominated by currentness, claim-coverage, unsupported-assertion, and
  usefulness failures.
- The result is robust to reviewer provider: both fixed reviewers reject the
  candidate globally and in every stratum, and both prefer the reference in
  every case.
- The experiment evaluates one frozen memory state, digest snapshot, corpus,
  model configuration, and strict rubric. It rejects advancement from this
  trial; it is not a universal impossibility result for digest designs.
- Any future investigation should first explain digest freshness and coverage
  failure from read-only evidence. A new digest mechanism or corpus would need
  a new preregistration and must not be treated as a retry of this consumed
  attempt.

## Closure Boundary

The answer-stage lane is closed at `NO_ADVANCE`. No successor-v4 experiment,
write-side preregistration, runtime promotion, automatic digest regeneration,
retrieval-default change, score edit, pooled-reviewer rescue, version change,
tag, release, deployment, or CI action is implicitly open.

The deployed schema-v42 provenance collector remains unchanged: production
defaults remain organic, outcome apply remains off, historical retrieval rows
remain unknown, causality remains `BLOCKED_PARTIAL_TRAFFIC_CLASS`, and ambient
evaluation remains `WAIT_LABELLED_DATA`. This score did not rebuild or deploy
Agent-Bridge.

## Private Material

Raw prompts, contexts, generated answers, blind map, reviewer notes, command
records, receipts, score claim, score packet, and audit records remain only in
the ignored private execution directory:

```text
data/eval/portfolio-continuity-successor-v3-answer-blind-20260710/
data/portfolio-continuity-score-claims/
```

No private trial artifact is added to git.

## Verification

```bash
git diff --check
git status --short
```
