# StructMemEval Next-Lane Value Assessment

Date: 2026-07-09

Source base commit: `7e932279`

Run type: docs-only value assessment, no benchmark runner

Memory evolution stage:

```yaml
memory_evolution_stage: reflection
runtime_authority: none
promotion_allowed: false
private_memory_export_allowed: false
third_party_runtime_dependencies: false
no_write_invariant: true
may_write_memory_now: false
may_change_retrieval_order_now: false
```

AB planning anchors:

- Durable memory key: `structmemeval_next_lane_value_assessment_20260709`
- Work-memory key: `codex-structmemeval-next-lane-assessment-20260709_active`
- Forum thread: `design#119`, post `2977`
- Parent report:
  `docs/reports/goal-c-u/2026-07-09-structmemeval-accounting-corpus-gate.md`
- Parent durable memory key: `structmemeval_accounting_corpus_gate_20260709`

## Decision

```yaml
recommended_next_lane: pause_structmemeval_and_return_to_survey_triage
real_runner_gate: owner_gated_boundary_packet_only
benchmark_performance_claim_allowed: false
official_runner_import_allowed_now: false
dependency_install_allowed_now: false
writes_ab_store: false
private_memory_export_allowed: false
```

Pause the StructMemEval implementation lane after the local accounting corpus
gate. Do not proceed directly to the official runner.

The local StructMemEval accounting lane now has enough scaffolding to guard
normalizer behavior:

- no-write adapter contract helper;
- pinned upstream shape smoke;
- deterministic accounting answer normalizer;
- pinned upstream accounting smoke;
- checked-in accounting candidate corpus;
- redacted review-summary mode;
- local accounting corpus gate.

Additional local accounting fixtures are now lower value than returning to the
survey-level benchmark map. A real StructMemEval runner may still be useful, but
only after a separate owner-gated boundary packet defines source, license,
dependency, privacy, score, and rollback constraints.

## Value Assessment

| Option | Value | Risk / cost | Verdict |
| --- | --- | --- | --- |
| Pause StructMemEval and return to survey triage | High. Restores portfolio view after one external benchmark has a local guardrail chain. | Low. Docs-only and no runtime effect. | Recommended. |
| Draft a real-runner boundary packet | Medium. Useful if the owner wants benchmark scores next. | Medium. Must inspect official runner, dependencies, API-key path, score semantics, and isolation rules before any run. | Owner-gated only. |
| Extend the accounting fixture corpus | Low to medium. Can catch parser edge cases. | Low, but diminishing returns because this still remains synthetic local behavior, not benchmark performance. | Defer unless normalizer grammar changes. |
| Import or execute the official runner now | Potentially high evidence value later. | High. Crosses license/dependency/network/API-key/score-semantics boundaries and can be mistaken for a benchmark claim. | Do not do now. |

## Why Pause Here

StructMemEval has already served the intended first-lane purpose: it converted a
survey recommendation into concrete, privacy-safe AB adapter contracts and local
evidence. The current chain proves that AB can shape StructMemEval-like
accounting inputs, compare settlement answers deterministically, and gate local
normalizer behavior without writing the AB store.

That is different from proving benchmark performance. A benchmark score would
require:

- official runner source and license review;
- isolated dependency plan;
- input/output schema review;
- explicit score semantics;
- no private AB memory export;
- no AB store writes;
- network/API-key policy;
- reproducible run log and raw-result retention policy.

Those are worthwhile only if benchmark scores are now the highest-value product
question. Otherwise, the next better move is to revisit the memory-survey matrix
and decide whether RealMem, Memory Probe, MemoryArena, AMA-Bench, MemoryBench,
or LifelongAgentBench now offers a better marginal signal.

## Recommended Next Work Packet

Name: `memory_survey_next_benchmark_lane_retriage`

Type: docs-first selection packet.

Scope:

1. Re-open the benchmark matrix from
   `docs/reports/goal-c-u/2026-07-09-memory-survey-benchmark-triage.md`.
2. Treat StructMemEval as `locally_scaffolded`, not as an open implementation
   lane.
3. Re-rank the remaining candidates by:
   - license clarity;
   - data shape accessibility;
   - adapter cost;
   - relevance to AB storage, reflection, and experience surfaces;
   - ability to run without private memory export;
   - evidence value not already covered by StructMemEval accounting.
4. Select one next no-write packet, preferably a different benchmark family or
   a diagnostic pattern that complements StructMemEval.

Admission bar:

- no dependency installation;
- no external runner import;
- no private AB memory export;
- no benchmark-performance claim;
- no MCP tool or runtime path;
- no retrieval, consolidation, trigger-recall, bootstrap, or workflow-feedback
  behavior change.

## Owner-Gated Alternative

If the owner explicitly wants StructMemEval scores next, do not start by running
the benchmark. Start with `structmemeval_real_runner_boundary_packet`.

That packet should answer:

- which exact upstream commit, files, and license terms are in scope;
- whether official dependencies can be isolated outside AB runtime;
- whether API keys or network calls are required;
- which task family will run first;
- which output fields count as benchmark results;
- how raw outputs are stored or redacted;
- how to prove `writes_ab_store=false`;
- how to avoid exporting existing private AB memories;
- which command is allowed to run and which commands remain forbidden.

Only after that packet is reviewed should a real runner be considered.

## Boundary

This assessment did not:

- clone, vendor, import, or execute StructMemEval official code;
- install Python, Rust, npm, or system dependencies;
- run a benchmark or create a score;
- call an LLM or API-key-backed evaluator;
- export private AB memory data;
- write to the AB memory store;
- add a DB schema, MCP tool, feature flag, or runtime process;
- change retrieval, bootstrap, consolidation, trigger-recall, workflow-feedback,
  forum status, or daemon configuration.

## Verification

Commands:

```bash
bash -n scripts/verify-structmemeval-next-lane-value-assessment.sh
scripts/verify-structmemeval-next-lane-value-assessment.sh
git diff --check
```

The verifier asserts that this packet names the recommended next lane, keeps the
real runner owner-gated, preserves the no-score/no-runner/no-dependency/no-write
boundaries, and links back to the corpus-gate memory anchor.

## Next Step

Proceed with `memory_survey_next_benchmark_lane_retriage` unless the owner
explicitly chooses the owner-gated StructMemEval real-runner boundary packet.
