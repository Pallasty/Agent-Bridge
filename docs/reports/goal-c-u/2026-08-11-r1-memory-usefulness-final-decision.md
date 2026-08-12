# R1 memory usefulness final decision

Date: 2026-08-11

## Observed result

The local-only R1 ledger reached its code-locked target of 20 organically occurring real development tasks.

- observed tasks: `20/20`;
- outcomes: `used=20`, `no_recall=0`, `missing=0`, `stale=0`, `harmful=0`;
- repeated explanations: average `0.0`;
- optional retrieval-payload metric: 3 tasks, average `7,130` bytes;
- verdict: `READY_FOR_PRODUCT_DECISION`.

The recorder is operator-attested and aggregate-only. This result does not prove that memory caused each outcome, does not estimate a counterfactual, and does not change retrieval, ranking, memory, or runtime behavior.

## Product decision

Keep the current memory and continuity architecture for the next product phase:

1. retain targeted semantic bootstrap and the R3 compact-query auxiliary-section policy;
2. retain R2 low-ceremony operation: ordinary single-developer tasks use the task plan and optional short-lived work memory, without routine forum ceremony;
3. do not widen retrieval, add a new ranking layer, or reopen research-heavy embodiment/trajectory/custody lanes based on this aggregate alone;
4. continue ordinary regression observation and record only meaningful negative or missing-recall events if they occur.

The result is a positive dogfood signal, not a claim of causal product efficacy. A future change should require a concrete failure mode or a separately preregistered bounded comparison.

## Runtime boundary found during the final truth audit

The final source/install/runtime check found a separate deployment issue:

- GitLab and GitHub `master` aligned at `da177ef2cd5b5731deb4c73c9776ab266f94f5c7`;
- installed `agent-bridge.real` remained `bf5beb40861b`, SHA-256 `bda4dee5c978697bfe1dff13b60e167624aaafc2bd3249a4a2b175952ab6afd4`;
- healthz returned `ok` and Palace returned HTTP 200;
- `agent-bridge doctor` reported 7 stale MCP consumers and 0 current consumers for the install path.

Therefore R1 is complete, but the next operational goal is a separately gated build/deploy/reconnect from the latest `master`. This report does not claim that deployment or client refresh.
