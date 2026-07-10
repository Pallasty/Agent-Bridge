# AB-Native Portfolio Continuity Surface Trial

Date: 2026-07-10

Stage: version-bound evidence-surface readiness, before answer generation

AB anchors:

- Scope memory: `portfolio_continuity_ab_native_trial_scope_20260710`
- Parent contract: `portfolio_continuity_eval_contract_completed_20260710`
- Digest surfacing evidence: `ab_writeside_digest_shadow_trial_pass_20260710`
- Forum thread: `design#119`, start post `3033`

## Verdict

Direct portfolio digest and hybrid retrieval both satisfy the strict reviewed
evidence contract for the two observed strategic prompt classes. Direct digest
uses substantially less context. Session bootstrap is sufficient for the
status/concerns case but incomplete for the broader retrospective/planning
case.

This is not a natural-language answer-quality result. It admits direct digest
to a separate blinded answer-stage comparison; it does not admit automatic
digest regeneration or any runtime behavior.

```yaml
trial_schema: agent_bridge.portfolio_continuity_ab_assembly.v0
runtime_version: 0.14.0
runtime_source_commit: a8c6302325e27c9b5cb20f8c958ab719666de372
adapter_base_commit: a8c6302325e27c9b5cb20f8c958ab719666de372
capture_sha256: ab08bee97a29caa2ef51d73266208fc7fdaa041f230a4572cffbab4da1a2545f
snapshot_sha256_before: 46ddbdba1cf08fcae0d696aa5bcd2d09e14af2a8e26e7d8f89746a97f2ec3a4d
raw_capture_in_git: false
calls_llm: false
writes_live_ab_store: false
answer_quality_claim: false
runtime_promotion_allowed: false
```

## Preregistered Contract

Two exact 14-day high-frequency prompt classes were fixed before capture. The
repository records only their SHA-256 values:

| Case | Prompt SHA-256 | Required claim surface |
| --- | --- | --- |
| `status_and_concerns` | `1037b009bfeee23aa952c619c1cc541aea8c161b6abb6b4058b2c5d88aa4c672` | design vision, current state, open concerns |
| `retrospective_and_plan` | `d08a2e67c9fd3882b815b5a1b419ecbe55b2f33a258bfc2fce01b50e8f14dac7` | vision, problems, unexpected results, disproven directions, recommendations, next priorities |

Every case required weighted supported-claim coverage `1.0`, selected-evidence
precision `1.0`, no stale/unknown selected evidence, no unsupported or forbidden
claims, and all cases passing. The thresholds were stored in the ignored
private capture spec before collection and were not changed after results.
Hybrid retrieval was explicitly locked to `compact: false`.

## Results

| Condition | Verdict | Cases | Supported coverage | Selected precision | Context tokens | p95 latency | Relevant / observed evidence | Stale/unknown observed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `hybrid_retrieval` | PASS | 2/2 | 1.000000 | 1.000000 | 17,870 | 14.980 ms | 10/18 (0.555556) | 4 |
| `session_bootstrap` | FAIL | 1/2 | 0.833333 | 1.000000 | 7,802 | 184.310 ms | 10/32 (0.312500) | 8 |
| `portfolio_digest` | PASS | 2/2 | 1.000000 | 1.000000 | 3,676 | 42.282 ms | 2/2 (1.000000) | 0 |

Selected precision applies only to evidence that the complete human review map
assigned to a claim. Relevant/observed ratio accounts for every context item,
including irrelevant and stale/unknown material. Therefore precision `1.0`
does not mean retrieval or bootstrap is noise-free.

Per case:

| Condition | Status/concerns | Retrospective/plan |
| --- | ---: | ---: |
| `hybrid_retrieval` | 1.000000 PASS | 1.000000 PASS |
| `session_bootstrap` | 1.000000 PASS | 0.666667 FAIL |
| `portfolio_digest` | 1.000000 PASS | 1.000000 PASS |

The bootstrap retrospective context supplied vision, encountered-problem,
unexpected-result, and disproven-direction evidence, but lacked portfolio-level
recommendations and next priorities. This is an evidence-availability finding,
not a claim that a model could never infer those fields.

## Efficiency

For these two cases, direct digest used:

- 79.429% fewer estimated context tokens than hybrid retrieval;
- 52.884% fewer estimated context tokens than session bootstrap.

Direct digest p95 latency was 182.256% higher than retrieval in this two-call
sample and 77.059% lower than bootstrap. The sample is too small for a latency
claim; latency remains a diagnostic only.

## Isolation Proof

The collector:

1. opened the production SQLite database using URI `mode=ro`;
2. created a consistent online backup in a temporary directory;
3. passed only the snapshot path to the child MCP process;
4. required child stderr to confirm that exact path;
5. rejected output paths that alias the source DB;
6. allowed in-repo raw output only under a `git check-ignore`-confirmed
   `data/` path;
7. removed the snapshot after capture.

The snapshot hash changed from
`46ddbdba1cf08fcae0d696aa5bcd2d09e14af2a8e26e7d8f89746a97f2ec3a4d`
to `589d830637350bec7ba43b0566023cb859316cf5a49352bfef8f654a15b3815b`
because retrieval telemetry/coactivation side effects landed on the copy. A
read-only query against the production `retrieval_surfacing` table found zero
`mode=hybrid` rows for either trial prompt at or after capture time
`1783686790`. One concurrent `mode=fts` row from a separate `claude-code`
client existed at that timestamp; it is not attributed to this locked hybrid
capture.

## Review Discipline

The review adapter requires every observed evidence item to resolve through one
private source-key or source-title decision. Missing, extra, or unknown
selectors fail closed. The final review packet contains evidence hashes, status,
and claim labels, not memory keys or content.

Time-bound June work-memory snapshots were marked `superseded` even though their
database status remained active. Mixed index/prediction bootstrap blocks were
marked `unknown` and were not selected as claim evidence. These rows remain in
the observed-context denominator.

## Private Artifacts

The reproducible private packet is under ignored local path:

```text
data/eval/portfolio-continuity-ab-native-20260710/
```

It contains the raw capture, redacted capture, review template, selector
decisions, final review, generated scorer fixture/candidates, and three score
packets. None is checked into git.

## Limitations

- Current hybrid retrieval already surfaces the digest in its top two for both
  cases. It is not a pre-digest baseline; its PASS shows that the current
  retrieval surface can carry digest evidence, while the comparison primarily
  measures context expansion and noise.
- Runtime source `a8c63023` includes the newly deployed opt-in S4 compact search
  projection. This trial explicitly uses `compact: false`; it does not measure
  compact-only or compact-then-get behavior.
- The digest was hand-synthesized for these observed prompt classes. Full
  reviewed coverage is an admission signal for answer testing, not evidence of
  generalization to unseen strategic questions.
- Evidence review was performed by the implementing agent with condition labels
  visible. It is complete and hash-bound but not blinded or independently
  adjudicated.
- There are two prompts and one SQLite snapshot. Latency is diagnostic, and the
  token counts use Agent-Bridge's mixed CJK/Latin heuristic rather than a model's
  exact tokenizer.
- The scorer measures explicit evidence availability. It does not measure
  whether a model selects the right evidence, writes a useful answer, or avoids
  unsupported inference from noisy context.

## Repository Files

```text
scripts/eval/portfolio_continuity_ab_trial.py
scripts/eval/fixtures/portfolio_continuity_ab_capture_spec.json
scripts/verify-portfolio-continuity-ab-trial.sh
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-ab-native-surface-trial.md
```

## Verification

```bash
python3 -m py_compile scripts/eval/portfolio_continuity_ab_trial.py
bash -n scripts/verify-portfolio-continuity-ab-trial.sh
bash scripts/verify-portfolio-continuity-ab-trial.sh
git diff --check
```

The synthetic verifier makes its fake MCP mutate the snapshot and asserts the
source database remains unchanged. It also rejects a mismatched binary identity,
an unconfirmed child DB path, in-repo raw output outside ignored `data/`,
incomplete selector decisions, incomplete evidence review, malformed capture,
capture-hash drift, and unknown claim labels.

## Next Gate

Generate answers from the exact captured contexts with one fixed model and
decoding configuration. Randomize condition labels and have the owner score
claim completeness, currency, unsupported assertions, and usefulness without
seeing which condition produced each answer.

Only a blinded answer-stage win can justify discussing automatic digest
refresh. Current evidence supports carrying direct digest forward as a trial
condition, not enabling a runtime feature.
