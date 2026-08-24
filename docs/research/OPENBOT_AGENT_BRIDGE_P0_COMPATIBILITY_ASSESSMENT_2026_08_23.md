# OpenBot -> Agent-Bridge P0 Compatibility Assessment

- Date: 2026-08-23
- Status: P0 source review complete; design-only candidate
- Agent-Bridge base: `github/master@77600c9170703fbf9f93a5d9c91a5312c51df372`
- Release base at review time: `origin/master@eb5718b61fd9097ece725c6d1d494c367669cc00`
- OpenBot source pin: `CopilotKit/OpenBot@2251ad266406ec8212235adba365d2c478437a0c`
- AG-UI source pin: `ag-ui-protocol/ag-ui@54f13419055b4d0f442c71e1efab18b310982ce1`
- AG-UI package contract: `@ag-ui/core@0.0.57`, `@ag-ui/client@0.0.57`
- Decision: borrow bounded governance primitives; do not adopt or install the OpenBot product stack

## Executive decision

OpenBot is a high-value architecture reference for Agent-Bridge, but it is not a replacement runtime.
The useful seam is a governed Agent Computer boundary:

1. resolve a server-owned target;
2. decide against an explicit action policy;
3. record the decision before forwarding;
4. execute only when admitted;
5. append a distinct outcome record;
6. refuse agent actions while a human owns the surface.

Agent-Bridge already has strong pieces of this loop: typed Semantic System Bus events, honest
`verified | not_verified | unknown` verdicts, action-receipt lineage, body write leases, AX action
admission, workspace-runtime descriptors, agent spawning, skills routing, and A2A AgentCards. The
highest-value next increment is therefore a read-only AG-UI event projector, followed by a durable
human-control lease design. A per-agent container backend is a later, separate runtime gate.

This P0 authorizes no tool execution, no OpenBot installation, no CopilotKit dependency, no new MCP
surface, no policy change, no shared-remote write, and no deployment.

## Pinned evidence

The review used detached source checkouts. These hashes identify the exact OpenBot files read:

| Source file | SHA-256 |
| --- | --- |
| `docs/architecture.md` | `d55efad722a870c94da97688e67a7937cc7f90d6c8380b12464f30edc57c88b5` |
| `server/src/computer/policy.ts` | `144432cbb1e8a72e2452435aba68e63fb502405626c0641131331cd8ac452d27` |
| `server/src/computer/gateway.ts` | `88a89d7e6c5f44a29d5c7ecb042ed6de8a9e523f76d17a816642ef9081eae078` |
| `server/src/audit.ts` | `09e28c7b9cbf2fed3b0d9517be55d19a35db612da9a605552912f62d47d802df` |
| `server/src/plugins/selection.ts` | `62fd5746ed5a7aa7790dbd51a302da6c42a55b965eee4476bb41c4152288ffa2` |
| `server/src/copilot.ts` | `fc6debfd8b27a18a896d9e141ad10debb8660fd6cffabf1f72c1c3c0ba7a8bf7` |
| `supervisor/src/index.ts` | `6f6f9c10e479bb2f416b7c6e03d7b8efb18769c20c388737948b8eff99771071` |
| `supervisor/src/names.ts` | `b3d0962dabe6595c72dcaadc3dc6d7e30c07656eb5eb708b66b5eabcd63fb956` |
| `supervisor/src/docker.ts` | `f8a190237f55c6fcff93c4ee6ee34212db97651057e6af267353a9936206c8c3` |
| `LICENSE` | `6d35a6bb107ae508da34636387f6208e75a6938e797bc0d5bfa9489d2ca95bad` |
| AG-UI `packages/core/src/events.ts` | `268de0990a52d3a3a485559b53a74ac0465525916106cfa0d0a3e013e880eb24` |
| AG-UI `packages/core/src/types.ts` | `f7f18fea44fe16da4e190b32ceffb36830f5f5e0bc55f57f9a5a5f3102ccf2ce` |

Primary source links:

- [OpenBot architecture](https://github.com/CopilotKit/OpenBot/blob/2251ad266406ec8212235adba365d2c478437a0c/docs/architecture.md)
- [Action policy](https://github.com/CopilotKit/OpenBot/blob/2251ad266406ec8212235adba365d2c478437a0c/server/src/computer/policy.ts)
- [Governed computer gateway](https://github.com/CopilotKit/OpenBot/blob/2251ad266406ec8212235adba365d2c478437a0c/server/src/computer/gateway.ts)
- [Per-run tool selection](https://github.com/CopilotKit/OpenBot/blob/2251ad266406ec8212235adba365d2c478437a0c/server/src/plugins/selection.ts)
- [Per-Bot computer supervisor](https://github.com/CopilotKit/OpenBot/blob/2251ad266406ec8212235adba365d2c478437a0c/supervisor/src/docker.ts)
- [AG-UI 0.0.57 event types](https://github.com/ag-ui-protocol/ag-ui/blob/54f13419055b4d0f442c71e1efab18b310982ce1/sdks/typescript/packages/core/src/events.ts)

OpenBot is MIT-licensed, but its documented deployment also requires CopilotKit Intelligence
credentials and a CopilotKit license token. The repository license does not remove those runtime
dependencies. No OpenBot code is copied by this P0.

## Five governance objects

### 1. Action envelope and policy decision

OpenBot constructs policy context from server-held state rather than trusting caller-provided labels.
It separates mechanism (`tool.name`) from intent/effect, exposes browser, file, shell, and MCP fields,
evaluates deny before allow, and fails closed on broken rules. Its decision includes `allowed`, mode,
matched expression, rule source, `forward`, and a human-readable reason.

Agent-Bridge has two adjacent but different controls:

- `ToolPolicy` chooses a named tool surface/profile at process construction time.
- action-specific gates such as AX admission and body leases guard selected actuators.

Gap: there is no single normalized, per-action decision envelope that every browser, desktop, mobile,
shell, and MCP write passes through. `ToolPolicy` must not be renamed or reinterpreted as that policy;
it is exposure/routing policy, not execution admission.

### 2. Audit decision and outcome receipts

OpenBot writes the policy decision before forwarding. A forwarded action that fails receives a later
failure row. This preserves attempted actions, not only successes.

Agent-Bridge's `SemanticEvent` is stronger on outcome honesty: a dispatched action without readback
is `unknown`, never automatically `verified`. Its embodiment projection links prior intents to action
receipts and explicitly avoids claiming global completeness.

Gap: not every AB actuation path persists a durable pre-action decision record with one shared schema.
The future design should preserve AB's tri-state verdict instead of importing a boolean success model.

### 3. Human takeover

OpenBot records `computer.help_requested`, `computer.control_taken`, and
`computer.control_released`. While a human controls the browser, agent actions are refused rather than
queued.

Agent-Bridge's `embodiment_lease` provides exclusive process-local body write ownership and clears on
restart. It deliberately states that concurrency ownership is not per-action user permission.

Gap: AB has no explicit `human_controlled` lease mode, help-request lineage, or durable takeover
interval. Adding this must not make a human takeover depend on agent policy, and release must never
automatically resume a previously pending action.

### 4. Per-agent computer lifecycle

OpenBot derives container and volume names from a validated Bot ID, labels owned resources, provides
only `ensure | stop | reset | list`, binds laptop ports to loopback, separates browser profile from
workspace, and can request gVisor. `ensure` waits for actual health; `reset` removes the browser
profile while retaining workspace work.

Agent-Bridge's `WorkspaceRuntimeContract` is intentionally descriptive metadata. It reports locality,
interactive/cancellable/live-output support, and sandbox capabilities, but it is not an enforcement
attestation and does not provision a separate browser computer.

Gap: AB cannot currently request `computer_per_agent`, independently attest network isolation, or
distinguish profile reset from workspace deletion as a runtime contract. This belongs in a later
backend experiment, not the AG-UI adapter.

### 5. Per-run tool projection

OpenBot intersects skill-declared tools with tools already granted to the Bot. A skill can narrow but
never grant. Selector failure or no selection preserves the full granted set, because narrowing is an
accuracy optimization rather than an authorization boundary. Each selection is audited.

Agent-Bridge has static toolsets/profiles plus `skills_route` and `skills_recommend`, but it does not
currently build a distinct MCP registry for each turn from `matched skills intersect grants`.

Gap: AB should first produce a read-only projection explaining `granted`, `declared`, `matched`,
`offered`, and fallback reason. Runtime narrowing needs telemetry and accuracy evidence before it may
change the tools offered to a model.

## Compatibility matrix

| Concern | OpenBot | Agent-Bridge today | Disposition |
| --- | --- | --- | --- |
| Agent protocol | AG-UI HTTP event stream | MCP plus A2A AgentCard/presence | Add a read-only AG-UI projection seam; do not replace MCP/A2A |
| Tool exposure | Per-run skill-based narrowing | Construction-time profiles/toolsets | Design advisory projection first |
| Action admission | One CEL gateway across browser/file/shell/MCP | Selected actuator-specific gates | Later normalized decision envelope |
| Target integrity | Server-held snapshot and generation | Stable refs/AX identifiers where supported | Reuse AB object/affordance descriptors; require adapter-owned identity |
| Decision trail | Pre-forward decision row | Uneven across actuators | Add intent/decision event without execution authority |
| Outcome truth | Forward/failure rows | Tri-state verify-first verdict | Keep AB semantics; `TOOL_CALL_RESULT` is not automatically verified |
| Human takeover | Explicit audited control interval | Process-local exclusive body lease | Add a separate human-control state machine later |
| Computer isolation | Container and volumes per Bot | Runtime-described local/remote workspace | Later opt-in backend, never implied by metadata |
| Secrets | Separate entry, redacted audit | Tool-specific redaction boundaries | AG-UI P1 stores no raw messages, args, results, or secrets |
| Product UI/store | React, Hono, PostgreSQL, CopilotKit | Palace, daemon-http, SQLite store | Do not import the product stack |

## Prioritized route

### P1: read-only AG-UI -> Semantic Bus projector

Build a pure projector over caller-supplied AG-UI 0.0.57 event batches. It may report lifecycle,
tool-intent, and outcome-shape facts, but must not connect to an endpoint, execute a tool, write the
store, acquire a lease, or expose raw content. The companion protocol is
`AG_UI_SEMANTIC_BUS_READ_ONLY_ADAPTER_V0_2026_08_23.md`.

### P2: durable human-control lease design

Model `agent_owned | help_requested | human_controlled | released_needs_new_intent`. Keep it separate
from policy admission. Require every post-release action to carry a new intent and current lease.

### P3: advisory per-run tool projection

Project the tool set a message would receive without changing the live registry. Measure selection
coverage, fallback frequency, missing-tool regressions, and token savings.

### P4: isolated Agent Computer backend experiment

Only after P1-P3 review, extend workspace runtime capability vocabulary and evaluate a local container
backend. No Docker socket is exposed through MCP; a narrow supervisor owns lifecycle operations.

## Rejected routes

- Do not vendor or fork OpenBot as AB's UI/runtime.
- Do not add React, Bun, PostgreSQL, or CopilotKit Intelligence to the AB dependency graph for P1.
- Do not call AG-UI `TOOL_CALL_END` or `RUN_FINISHED` proof that an external effect occurred.
- Do not persist message text, reasoning, raw tool arguments, raw tool results, credentials, or page
  content in the semantic event spine.
- Do not let a skill declaration widen grants.
- Do not treat workspace runtime metadata as isolation attestation.
- Do not resume a queued agent action after human control releases.

## P0 exit result

`PASS_FOR_P1_DESIGN_REVIEW`.

This result admits only a pure, read-only projector candidate in an isolated worktree. It grants no
source merge, remote push, runtime exposure, OpenBot installation, action policy change, or deployment.
