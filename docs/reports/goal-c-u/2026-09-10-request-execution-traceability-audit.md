# Request-to-execution traceability audit

Decision: close this bounded source audit with an operational documentation
correction. AB has partial traceability, not an automatically bound
contract-to-launch-to-result pipeline. No observed natural-task requirement
loss was established here; an automatic binding system is not justified by
this audit alone.

The owner accepted the proposed audit after the RunningHub H3 research:
inspect the existing task-contract, launch-parameter, and result path; repair
concrete gaps, otherwise record coverage and stop. The audit examined AB source
at `2f98e1beec2032e672e648e5b33762da5d2be096`; the configured origin master
was independently read at that same revision before editing. This is a source
inspection, not a new runtime experiment or natural continuity sample.

## Findings

| Seam | Existing coverage | Limit |
| --- | --- | --- |
| Contract input to preview | `AgentTaskContractPreview` returns the original contract alongside effective state and compiled instruction. Planned and observed maps remain separate in the contract. | The caller supplies all of these values; observed state does not authenticate a user request or independent observation. |
| Goal changes | The preview optionally compares a previous contract and returns supplied reasons/references. | History is caller supplied and not automatically persisted or authenticated. |
| Preview to launch | `agent_spawn` accepts a prompt and explicit runtime options. | It has no contract field and does not consume the compiled preview. This handoff is the working agent's responsibility. |
| Backend resolution | Explicit supported backend/policy selects one runtime; the unspecified route can use a configured fallback chain. A backup response exposes `failover.attempted` and `failover.used`. | Runtime identity does not prove provider model identity or preserve the source of each semantic requirement. |
| Model resolution example | The Codex one-shot adapter chooses `cfg.model` before its configured default. | This source path is an example, not a claim that all adapters preserve or report every effective provider setting. |
| Outcome | `AgentTaskOutcome` carries contract ID/revision, verification, acceptance provenance, outcome provenance, and optional agent/body/environment handles. | These fields alone do not bind a launched prompt to the contract or independently prove semantic success. |

Source locations (paths relative to the audited revision):

- `crates/bridge/src/agent_task_contract.rs`: `AgentTaskContract`,
  `AgentTaskContractPreview`, `preview_agent_task_contract`, `compile_instruction`.
- `crates/bridge/src/mcp_tools.rs`: `AgentTaskContractPreviewTool`,
  `AgentSpawnTool::execute`, `policy_to_backend`, `resolve_spawn_chain`.
- `crates/agent/src/lib.rs`: `SpawnConfig`.
- `crates/agent/src/codex.rs`: one-shot `spawn` model/prompt resolution.
- `crates/bridge/src/agent_task_outcome.rs`: `AgentTaskOutcome` and provenance types.

## Correction and acceptance

Updated [the existing goal-review procedure](../../operations/GOAL_REVIEW.md)
to explain the unbound handoff and preserve the distinction between user
requirements, assistant choices, requested settings, and observed settings.
It includes a concrete keyboard-navigation example and explicitly separates
process termination from semantic acceptance. It reuses existing task context
and outcome fields, requires no new approval, and creates no new contract or
collection service.

Acceptance is documentation accuracy against the named source paths and a
clean whitespace/link check. No Rust code, tool schema, runtime selection,
database schema, or completion policy changes. No GPU dependencies, model
downloads, child agents, or production deployment are needed. R7/R9/R10 frozen
lanes remain governed by the existing decision board.

The reusable principle comes from the bundled SGLang `request_validation.py`
and `resolved_plan.py`: distinguish original request semantics from explicit
execution choices. It is not an anti-drift effectiveness result. RunningHub
repository inspected at `5d1401228680ca635dac463825f71c3fbd681ef7`:
<https://github.com/RH-RunningHub/MiniMax-H3-MultiGPU-Lightning/tree/5d1401228680ca635dac463825f71c3fbd681ef7>.

Stop condition: this audit is complete when the documented boundary and
procedure are retained. Revisit automatic binding only if an actual task
demonstrates a lost or changed requirement at this seam and a bounded repair
can be evaluated against its original acceptance criteria. This condition is
not a queued task or a claim that the present gap has been technically closed.
