# RSI and harness evolution: bounded offline audit

Date: 2026-09-27. Source candidate: `6c4b1a9f332d8b9e9329f8d2914deed7db713453`.

## Research and decision

- [RSIAgent](https://arxiv.org/abs/2609.15364) separates broad exploration,
  targeted refinement, and frozen-memory evaluation. It keeps model weights and
  the harness fixed. Its reported OSWorld and ALE aggregate gains combine some
  RSI runs with retained baseline entries; budgets and repetitions are not fully
  matched. The paper identifies missed weaknesses, incomplete verification, and
  incorrect memory consolidation as failure modes.
- [Lilian Weng's review](https://lilianweng.github.io/posts/2026-07-04-harness/)
  distinguishes prompt, context, workflow, harness-code, and optimizer changes.
  It calls for observable, bounded edits and evaluation beyond the examples
  used to propose a change.
- [ModularRSI](https://arxiv.org/abs/2609.14857) uses success/failure contrasts
  and restricts harness edits to agent loop, observation, tools, context
  management, or task completion detection. Its held-out benchmark design is
  the useful transfer test. The authors do not isolate contrastive analysis in
  a dedicated ablation, and their main runs use only a subset of the 2,000
  curated evolution tasks. Its research contribution is CC BY-NC 4.0; no code
  from that repository is copied here.

The feasible AB increment is a **read-only packet auditor** for a future
single-module, frozen-memory comparison. It is neither an autonomous exploration
loop nor a memory writer, verifier, runner, or promotion mechanism. This keeps
the research inside the existing [controlled RSI boundary](../design/CONTROLLED_RECURSIVE_SELF_IMPROVEMENT_FOR_AGENT_BRIDGE_2026_06_21.md)
and the [product decision board](../ACTIVE-PRODUCT-ROADMAP.md). R1 memory
usefulness is already decision-complete, and R10's independent completion
producer remains NO-GO. This audit does not reopen either lane.

## Input and acceptance

Run `python3 scripts/eval/harness_candidate_audit.py <packet.json>`.
The packet names one changed behavioral module, pinned source revisions,
disjoint exploration and evaluation task IDs, and one baseline and candidate
record for every declared evaluation task. Each pair must use the same model
and budget; each arm must keep one memory hash throughout evaluation. A record
states its outcome, evidence digest, independent-verifier claim, and whether
the official score was visible to learning. The command only reads JSON and
prints JSON. No result authorizes runtime or durable-memory promotion.

`review_candidate` means the **declared records** are structurally complete,
have at least one fail-to-pass change, and no pass-to-fail change. It is only a
review queue label. `invalid_protocol` blocks incomplete, unmatched, leaked,
unresolved, or self-reported records. `regression` and `no_gain` describe a
complete declared comparison. The script cannot authenticate source revisions,
run evidence, verifier identity, the completeness of a caller-supplied cohort,
or causal benefit. It cannot verify that the candidate changed only the stated
module. A real trial must bind those externally and preserve its
raw task outcomes, including failures and infrastructure errors.

## Local validation

`tests/test_harness_candidate_audit.py` exercises complete pairs and negative
controls for task overlap, missing or duplicate arms, unmatched model or budget,
self-reported verification, scoring feedback leakage, missing evidence, memory
drift, unresolved results, regression, unchanged revisions, and malformed
fields. The JSON fixture is deliberately synthetic; its hashes and outcomes are
placeholders. A successful run of that fixture demonstrates parser and audit
mechanics only, with **zero measured AB task benefit**.

The next empirical step is one naturally occurring new-tool task with a real,
independent acceptance check and a frozen evaluation cohort established before
candidate construction. Run both arms with matched model, budget, and
environment reset. A memory-only comparison must hold the harness fixed; a
harness comparison must hold all modules except the named one fixed. Keep the
candidate scoped to one module or memory snapshot.
Record task-level results and owner cost. If this prerequisite is absent, close
the mechanics audit without manufacturing a sample.
