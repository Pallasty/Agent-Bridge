# Qwen-AgentWorld trajectory compatibility P0

Status: **implemented and fail-closed**

This P0 asks one narrow question: can current Agent-Bridge telemetry be
converted into an honest Qwen-AgentWorld-style sequence of initial state plus
`(action, observation)` turns without exporting private payloads or confusing
simulation with execution evidence?

The answer on 2026-07-21 is **no**. The new audit surface records that result as
typed blockers instead of fabricating turns from telemetry previews.

## Scope and nonclaims

P0 adds:

- `agent_bridge.agent_world_trajectory.v0`, a digest-only manifest shape;
- `agent_bridge.agent_world_trajectory_audit.v0`, a compatibility report;
- a pure adapter from `AgentTaskContractPreview` plus `EventSpineSnapshot`;
- observed/simulated evidence-separation validation; and
- `agent_world_trajectory_audit`, a read-only MCP tool available only in the
  `all` profile (`Tier::Niche`).

P0 does **not**:

- download Qwen-AgentWorld weights;
- send traces to an external endpoint;
- persist a new trajectory table or memory row;
- copy prompts, tool arguments/results, session transcripts, errors, or state
  values into the report;
- enable a world-model runtime; or
- let a simulated observation carry an evidence or sandbox-attestation claim.

The upstream artifacts inspected for this design were pinned during research:

- repository: `QwenLM/Qwen-AgentWorld` at
  `cd0aa83dc7a9c733695eb9c4652e0a68b6e6ecde`;
- model: `Qwen/Qwen-AgentWorld-35B-A3B` at
  `60d2b0434a53d2e62a7c00a489586815d94ebffb`; and
- benchmark: `Qwen/AgentWorldBench` at
  `6b8d28437042434dcdd168434227ca0de408c5ba`.

## Manifest boundary

The task portion contains only:

- a keyed commitment to the contract id plus its revision;
- process-local keyed commitments to the objective and allowed actions; and
- keyed commitments to both state keys and state values.

The ephemeral process key is never returned. These are privacy commitments,
not portable content hashes, so low-entropy values cannot be checked by an
offline dictionary without access to the running process key.

The provenance portion contains only event ids, timestamps, source/kind,
success state, payload digests, event hashes, and the event-spine chain head.
Raw `facts` and event labels are deliberately excluded. The audit recomputes
the local hash chain rather than trusting the snapshot's `verified` boolean;
this proves local consistency, not external authenticity or runtime authority.

Future turns have an explicit `observation_origin`:

- `observed` requires at least one evidence reference; and
- `simulated` must have no evidence or attestation reference.

This keeps the real executor and sandbox attestation authoritative while still
allowing a later world model to produce shadow observations.

## Live aggregate-only audit

The read-only contract preview was `ready` at revision 2 with these continuity
locks:

- `real_executor_is_ground_truth=true`
- `sandbox_attestation_is_real_only=true`
- `payload_mode=digest_only`

A one-hour live `event_spine_snapshot` was then inspected in memory and reduced
to aggregates before reporting:

| Measure | Result |
| --- | ---: |
| Candidate / retained events | 122 / 122 |
| Truncated events | 0 |
| Hash chain verified | true |
| MCP tool-call events | 110 |
| Agent-session lifecycle events | 10 |
| MCP tool-error events | 2 |
| Action candidates | 110 |
| Exact observation candidates | 0 |
| Session preview-only candidates | 5 |
| Unambiguous action/observation pairs | 0 |
| Reconstructability | 0% |

The chain head for this bounded observation was
`eed58fc1aa29374a03da5dd90ff02366d19b61bd907b72199519a9f8070d97e5`.
No raw event body is retained in this receipt.

The 24-hour view contained 872 candidates but the existing tool is capped at
500, so it correctly reported 372 truncated events. P0 therefore uses the
complete one-hour window for its coverage verdict and treats the 24-hour view
as a separate truncation finding.

## Why reconstruction is blocked

Current sources are useful for integrity and operational telemetry, but not for
world-model replay:

1. `mcp_tool_calls` records tool name, duration, success, and argument/result
   sizes, not the action and exact result.
2. `agent_sessions` records lifecycle and truncated stdout/stderr previews;
   the initiating prompt/action is not paired with those previews.
3. A preview is diagnostic text, not a ground-truth observation.
4. Event ordering alone is insufficient to infer causality or pair an action
   with an observation.

The audit therefore emits `missing_exact_observations`,
`preview_is_not_observation`, and `missing_action_observation_pairs` as typed
blockers. Even a future event containing both fields is not auto-paired unless
an explicit capture producer establishes the pair.

## Verification

The dedicated test suite covers:

- fail-closed behavior for current tool/session telemetry;
- absence of raw objective, action, state, event, and preview secrets from the
  serialized report;
- deterministic manifests for the same contract and event chain;
- rejection of evidence/attestation claims on simulated turns;
- evidence requirements for observed turns;
- refusal to infer a turn from coincidental fields; and
- rejection of forged integrity booleans and malformed evidence references;
- per-source truncation sentinel handling; and
- explicit `all` / `all-dev` high-surface-profile-only tool exposure.

Commands:

```text
cargo test -p ab-bridge --test agent_world_trajectory
cargo test -p ab-bridge --lib agent_world_trajectory_audit_is_all_profile_only
```

Result: 8 integration tests and 1 registry test passed. Existing warnings were
unchanged.

## Next gate

Do not run the 69 GB model yet. A later P1 capture proposal should first prove:

1. at least 20 explicit observed action/observation pairs from local Terminal
   and MCP runs;
2. opt-in capture with bounded retention and a local-only payload resolver;
3. secret scanning before any payload leaves the execution boundary;
4. content hashes and evidence references that survive replay verification;
5. simulated and observed ledgers remain disjoint; and
6. external egress remains a separate authority gate.

Only after those conditions pass should a small remote-GPU shadow comparison be
considered.

## Implementation lesson

The first isolation command cloned the repository and then ran `git switch` in
the parent shell directory. `git clone` does not change the shell working
directory, so the switch failed harmlessly. No repository state required
rollback. The corrected and reusable form is an explicit
`git -C <clone-path> switch ...`; subsequent commands in this slice use an
explicit working directory.

Coordination: Agent-Bridge forum thread `#186`.
