# Portfolio Continuity Expanded Answer Trial Result

Date: 2026-07-10

Status: **COMPLETE / NO_ADVANCE_GENERATION_PROTOCOL_FAILURE**

AB anchors:

- Owner authorization: `agent_bridge_expanded_trial_owner_authorization_20260710`
- Preregistration memory:
  `portfolio_continuity_expanded_answer_trial_preregistered_20260710`
- Active work memory:
  `codex-portfolio-continuity-expanded-answer-trial-20260710_active`
- Forum thread: `design#119`, preregistration post `3046`

## Verdict

The expanded trial did not reach blind review and does not advance direct
portfolio digest to a write-side trial preregistration.

The amended collector completed 24 isolated context captures and validated the
raw payload before writing it. During fixed-model answer generation, one answer
contained a forbidden condition/evidence marker. The harness failed closed
before it wrote a generation packet, blind packet, condition map, or review
template. No reviewer saw an answer, no condition was unblinded, and no score
was computed.

The preregistration defines no retry for a semantic answer-policy failure.
Restarting generation until all answers avoid the marker would selectively
resample the fixed trial. This run is therefore terminal.

```yaml
result_schema: agent_bridge.portfolio_continuity_answer_trial_result.v1
trial_id: portfolio_continuity_expanded_20260710_run2
status: NO_ADVANCE_GENERATION_PROTOCOL_FAILURE
contract_commit: f472244f2bd07c9edee6b8b34118a17c795d72a7
contract_sha256: a02affde622ede83c52121e47dd5cb085127b1e4525427518909eb7ba43de57d
harness_source_sha256: 60dd2130f6e4af976e594dec284ae38c46c63b437a7f3080d5eb5f41369973a5
surface_source_sha256: 0ff5ab27b79d36169fee22b5de5f2c4563cb1ba0f6edebf354a17cfcb60e6311
base_snapshot_sha256: fb83ff42a5ad92f81c65de1e3228bc76e61065326b2f9dc163e742bfef318da8
capture_sha256: 58a3a38ec053b4c13d4bad65267abde78164276ec5f04488fa6408bb1aaeb766
operator_failure_receipt_sha256: f971862997ab6bb11cbbc6e9c0606025447bda780ef0123eae1cd5d1a85cd105
capture_condition_runs: 24
hybrid_zero_hit_cases: 6
generator_identity: codex-cli 0.144.1
model: gpt-5.4
reasoning_effort: medium
generation_completed: false
generation_packet_created: false
blind_packet_created: false
blind_map_created: false
review_template_created: false
blind_reviews_completed: 0
unblinded: false
scored: false
recommend_write_side_preregistration: false
runtime_promotion_allowed: false
ci_action_allowed: false
```

## Execution Record

The first capture under commit `1a93668f` exposed an inherited v0 validation
invariant: six v1 full-hybrid searches returned no rows, while the downstream
validator incorrectly required at least two. Capture hash `6a62665a...` was
invalidated before generation. Commit `f472244f` made the cardinality check
version-aware, added pre-write capture validation, and added synthetic
zero-hit and duplicate-ranking regressions. It did not change the corpus,
seed, conditions, generator, rubric, thresholds, review protocol, or boundaries.

The amended run then completed capture against one read-only online backup.
Every case-condition call used a separate snapshot copy and process. The
runtime identity was `agent-bridge 0.14.0` at source `a8c63023`, all snapshot
paths were confirmed, and the source store was not passed to any child.

The initial generator identity observation encountered a warning from the
shared Codex arg0 directory while other Codex sessions were active. It failed
before any model call. The execution was restarted with an ignored, private
`CODEX_HOME` containing only the authentication file; no user config, hook,
rule, or prior session state was copied. Identity then matched the frozen
`codex-cli 0.144.1` string exactly. This was an environment isolation measure,
not a generator or contract change.

The answer run stopped when the harness detected a forbidden marker in model
output. The failing answer and its condition were not persisted, so this report
does not attribute the failure to either condition. The private operator
receipt records only the bound hashes, error class, and absence of downstream
artifacts; it contains no prompt, context, answer, opaque id, or condition map.

## Capture Diagnostics

These values describe captured context only. They are not answer-quality scores
and cannot rescue the failed generation gate.

| Prompt stratum | Cases | Hybrid zero-hit cases | Hybrid token estimate | Digest token estimate |
| --- | ---: | ---: | ---: | ---: |
| Portfolio status | 2 | 2 | 4 | 3,768 |
| Portfolio retrospective | 2 | 1 | 8,549 | 3,768 |
| Portfolio planning | 2 | 1 | 11,352 | 3,768 |
| Dependency and risk | 2 | 2 | 4 | 3,768 |
| Stale state | 2 | 0 | 19,614 | 3,768 |
| Cross-project conflict | 2 | 0 | 17,936 | 3,768 |
| **Total** | **12** | **6** | **57,459** | **22,608** |

The six zero-hit cases span four strata. Under the fixed per-stratum efficiency
gate, several cells would likely have blocked digest advance even if generation
and both reviews had completed. That is a diagnostic inference only; no score
was run and no preregistered verdict is derived from it.

## Privacy And Blinding

- Raw prompts, contexts, invalidated capture, amended capture, seed, isolated
  Codex home, and failure receipt remain under ignored `data/`.
- No generation packet, blind packet, blind map, or review template exists.
- No reviewer identity or review record exists for this run.
- No condition mapping or raw private content appears in this report or git.
- The production Agent-Bridge store was not mutated by capture or generation.

## Interpretation

- The failure is a trial-level generation-protocol failure. Without a persisted
  answer and map, it cannot be assigned to hybrid retrieval or direct digest.
- The two-case result remains evidence only for entering this expanded trial.
  It does not override the expanded trial's terminal failure.
- Direct digest therefore remains unqualified for a write-side generation or
  freshness trial.
- Retrieval defaults, digest contents, runtime behavior, release state, and CI
  remain unchanged.

## Next Gate

Do not rerun this corpus ad hoc. Any successor must be separately
preregistered and should add:

1. an atomic private failure receipt that records case id, condition, answer
   hash, and matched-marker hash without exposing them in public output;
2. an explicit retry taxonomy that permits infrastructure-only retries and
   assigns zero retries to semantic policy failures;
3. a deliberate decision on whether evidence metadata keys remain part of the
   answer surface, rather than silently sanitizing an answer after generation;
4. a capture-validity or reference-coverage rule for zero-hit hybrid baselines.

No write-side trial should be planned until that successor design is reviewed
and preregistered.

## Repository Files

```text
scripts/eval/portfolio_continuity_answer_trial.py
scripts/eval/fixtures/portfolio_continuity_expanded_answer_contract.json
scripts/verify-portfolio-continuity-answer-trial.sh
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-expanded-answer-trial-prereg.md
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-expanded-answer-trial-result.md
```

## Verification

```bash
python3 -m py_compile scripts/eval/portfolio_continuity_answer_trial.py
bash -n scripts/verify-portfolio-continuity-answer-trial.sh
bash scripts/verify-portfolio-continuity-answer-trial.sh
git diff --check
```
