# ChatGPT collaboration control plane

**Status:** P1 and P2A implemented; P2B synthetic lab implemented; production remains read-only
**Date:** 2026-07-18
**Production tunnel:** remains `chatgpt-read`

## Decision

ChatGPT should gain Agent-Bridge collaboration capabilities in layers, not by
receiving the Codex toolset wholesale.

Codex runs inside a local engineering host with filesystem, Git, process, and
approval semantics supplied by its client. An ordinary ChatGPT App reaches
Agent-Bridge through a Secure MCP Tunnel. The tunnel protects transport
reachability, but does not by itself prove a local human identity, constrain a
project path, provide per-action approval, or supply rollback for a mutation.

P1 therefore adds a **request control plane**, not an execution plane:

1. ChatGPT may read the existing scoped knowledge/forum surfaces.
2. ChatGPT may compile an `agent_task_contract_preview`.
3. ChatGPT may stage an API-single-write, TTL-bounded operator request.
4. ChatGPT may inspect that request and its eventual decision.
5. Only a local CLI may append one approve/reject decision.
6. Approval is evidence for a future executor review. It is never execution
   authority and always reports `execution_allowed=false`.

## P1 surface

The explicit `chatgpt-collab` toolset contains:

- `search`
- `fetch`
- `forum_search` and `forum_fetch`, only when forum tags are allowlisted
- `capabilities`
- `context_governor_snapshot`
- `agent_task_contract_preview`
- `operator_request_stage`, only when a collaboration channel is configured
- `operator_request_get`, only when a collaboration channel is configured

It does **not** expose `memory_save`, `work_memory`, `forum_post`,
`shell_exec`, terminal/browser/device/Git/deployment tools, IDE mutation, or
agent spawning/steering.

The generic aliases `chatgpt` and `openai-chat` still resolve to
`chatgpt-read`. Collaboration requires the exact `chatgpt-collab` or
`openai-collab` name.

## Request contract

A staged request records:

- requested capability and exact target
- bounded summary and full validated task-contract preview
- UUID, creation/expiry timestamps, configured channel, source, and toolset
- optional MCP session identifier
- an honest identity-strength label:
  - `channel_only`
  - `channel_and_client_session`
- SHA-256 digest over the complete staged record material
- `execution_performed=false`
- `canonical_write_performed=false`

Supported requested capabilities are:

| Capability | Required authority boundary |
|---|---|
| `work_memory_write` | `project_write` |
| `forum_post` | `project_write` |
| `project_write` | `project_write` |
| `external_write` | `external_write` |
| `runtime_enablement` | `runtime_enablement` |

Non-read-only task contracts must carry accepted parent evidence for the exact
authority boundary. A mismatch is rejected before any record is created.

Records live under the Agent-Bridge data directory in
`operator-requests/{requests,decisions}` by default. Unix directories are
`0700`; files are created once with `0600`. Requests expire after 60-3600
seconds (default 600), are capped at 30 staged records per hour and 5000 total
records, and are channel-scoped on MCP reads. Every read recomputes request and
decision digests and fails closed on inconsistency.

## Local review

The decision interface is intentionally CLI-only:

```bash
agent-bridge operator-request list
agent-bridge operator-request show REQUEST_ID
agent-bridge operator-request approve REQUEST_ID \
  --operator OWNER_ID \
  --reason "Reviewed this exact digest"
agent-bridge operator-request reject REQUEST_ID \
  --operator OWNER_ID \
  --reason "Boundary or target is not acceptable"
```

Approval writes:

- `approval_scope=request_evidence_only`
- `execution_allowed=false`
- `requires_separate_executor_gate=true`

The decision is single-write and must occur before request expiry. There is no
MCP approve/reject tool and no executor in P1.

## Explicit configuration

Local testing of the P1 profile requires all of:

```bash
export AGENT_BRIDGE_TOOLSET=chatgpt-collab
export AGENT_BRIDGE_CLIENT=chatgpt
export AGENT_BRIDGE_MCP_SOURCE=chatgpt
export AGENT_BRIDGE_CHATGPT_COLLAB_CHANNEL=chatgpt-desktop-owner
export AGENT_BRIDGE_CHATGPT_COLLAB_CAPABILITIES=work_memory_write,forum_post,project_write
export AGENT_BRIDGE_CHATGPT_FORUM_TAGS=agent-bridge
agent-bridge mcp
```

`AGENT_BRIDGE_CHATGPT_COLLAB_CAPABILITIES` is a stage allowlist, not an
execution grant. Missing/invalid channel configuration hides both request
tools. A missing or empty capability allowlist keeps the tools visible for
inspection but rejects every stage attempt.

Do not apply this profile to the production ChatGPT tunnel during P1. Keeping
`AGENT_BRIDGE_TOOLSET=chatgpt-read` is the rollback and current production
contract.

## Security limits

P1 deliberately does not claim:

- MCP session IDs are authenticated human identities.
- Caller-supplied parent evidence references are authenticated authorization;
  P1 validates their shape and boundary consistency only.
- A SHA-256 record digest prevents a same-user process from rewriting and
  recomputing local files.
- Local CLI invocation proves that a human, rather than automation with shell
  access, made the decision.
- An approved request may be executed.

The digest detects inconsistent or accidental modification and binds review to
an exact request. It is not a signature. The control plane is useful because it
keeps mutation structurally unreachable while producing bounded review
evidence.

## Conditions for an execution plane

The P2 authenticated-subject feasibility result and threat model are recorded in
[ChatGPT collaboration P2 authenticated subject binding](CHATGPT-COLLAB-P2-SUBJECT-BINDING.md).
The current stdio tunnel cannot satisfy authenticated subject binding;
production therefore remains on `chatgpt-read`. A separate default-off
loopback HTTP/OAuth synthetic lab now proves the transport-owned subject path
and negative token/policy cases, but a real authorization server, key rotation,
public HTTPS tunnel path, and live ChatGPT OAuth acceptance remain prerequisites.

P2 may add one narrowly scoped executor only after all of these exist:

1. **Authenticated subject binding:** tunnel/app identity mapped to a local
   policy subject; channel and session labels alone are insufficient.
2. **Capability-specific policy:** exact target/path/service constraints, not a
   generic write bit.
3. **Fresh human gate:** per-request confirmation or a separately issued,
   TTL/use-count/scope-limited local grant.
4. **Atomic digest consumption:** revalidate the complete request and decision,
   then consume once before mutation.
5. **Workspace/runtime sandbox:** filesystem and process boundaries appropriate
   to the capability.
6. **Outcome receipt:** append-only attempt/result audit with the consumed
   digest and observed postcondition.
7. **Rollback handle:** a tested revert/revoke/disable path recorded before
   execution.
8. **Rate and concurrency controls:** per subject, channel, capability, and
   target.
9. **Independent threat review and live acceptance:** source tests, deployed
   runtime proof, tunnel reconnect, and an actual bounded call.

Direct ChatGPT write tools are a later P3 decision. They must not be implemented
by reusing Codex/Claude profiles or by treating P1 approval evidence as
execution authorization.
