# R2 Low-Ceremony Operating Mode

R2 reduces the coordination work paid by a single developer. It changes operating behavior, not the Agent-Bridge runtime.

## Reviewable collaboration contract

R2 applies the High-Autonomy Recoverable-Risk Contract from
`CLAUDE-SIBLING.md` without turning every implementation step into an approval
ceremony.

- `AUTO` means the action is inside the stated task, recoverable, and isolated
  from unrelated or shared WIP. Inspection, focused edits, tests,
  documentation, local commits, non-force pushes to isolated feature branches,
  read-only device observation, R2/R3-justified AB coordination, and evidenced
  cleanup of agent-created temporary files or worktrees normally belong here
  when host policy permits them.
- `NEEDS <exact boundary>` means the next action advances a shared, default, or
  protected remote line; force-pushes or rewrites shared history; deploys to
  production or enables a runtime/executor; performs real external execution
  or effectful device installation, uninstallation, or data mutation; changes
  secrets, accounts, payments, or permissions; destroys user data or a
  non-agent-created directory; creates an irreversible external effect; or
  materially expands the task scope.
- Praise such as `很好` is feedback, not authority for an unpresented action.
  `继续` or `按你的思路走` may advance only an already displayed `AUTO` next
  action. Every `NEEDS` packet requires an explicit owner or harness response
  to that exact packet. `授权下一道门` binds only the displayed packet; it does
  not authorize an unseen or later gate.
- Authorization binds only the displayed action, target, candidate, and
  evidence state. Source, artifact, runtime, device, remote, or target drift
  invalidates that binding. Passing one gate never implies that a later gate
  passed or was authorized.

The owner-ratified scope makes these classifications reviewable. It does not
let peer agents authorize each other, issue or copy capability credentials,
weaken host policy, or bypass the host permission classifier. Peers synchronize
coordination state, not authorization.

Permission to use AB memory or forum is not an obligation to create ceremony.
Forum use still requires one of the four triggers below. Durable memory remains
limited to decisions and lessons; short-lived work memory is cleared when the
task completes.

## Gate packet

Use this compact packet at a real boundary, evidence drift, verification
failure, shared-WIP conflict, milestone, or when the owner asks for status:

```text
[门] <name> — PASS | HOLD | BLOCKED
绑定：action=<action>; target=<target>; candidate=<hash/ref>; evidence=<revision>; source/artifact/runtime/device/remote=<ids or n/a>
已证明：<one to three decision-relevant facts>
未证明：<explicit exclusions, unknowns, or drift>
下一门：<one recommended action>
授权：AUTO | NEEDS <exact boundary and requested response>
```

Do not emit a packet for every internal step. The packet should remove
coordination work, not rename it.

## Content-free burden counts

The measurement unit is one real owner task, beginning after the initial
request. The root or coordinator may record at most one outcome for that task;
subagent reviews or implementation lanes are not separate owner tasks. These
counts describe coordination burden, not personal productivity:

- `owner_restatements`: the owner had to repeat intent or context already
  supplied because the agent lost or incorrectly recovered it. New
  constraints, corrections to a new mistake, new trade-off choices, and the
  first answer to a legitimate boundary question are excluded.
- `repeated_authorization_prompts`: the agent asked again for materially the
  same authorization after the same action, target, candidate, and bound state
  were already authorized and had not drifted. A first prompt at a new gate,
  a different push/deploy/device gate, expanded scope, or changed source,
  artifact, runtime, device, remote, or target is excluded.
- `manual_interventions`: owner actions needed to finish or recover the task,
  excluding the initial request and the first legitimate authorization at each
  new boundary.

Unknown counts remain omitted or `unavailable`; they are never converted to
zero. An explicit zero is a task-local, agent-reported claim, not authenticated
owner or harness evidence. If a normal task already records a public
`session_finalize.task_outcome`, the coordinator may include these three
counts once with `provenance=agent_reported`, `user_acceptance=unknown`, and
`acceptance_provenance=unavailable`. Do not add another finalize call or a
second ledger merely to collect them.

The agent may assess the active task context needed to do the work. Do not
retroactively mine or retain Computer History, raw prompts or transcripts,
keystrokes, shortcuts, browsing history, MCP call counts, or desktop activity
for R2. Never copy these counts or task content into `session_finalize`'s
`user_profile`, `USER.md`, or another benefit ledger.

## Default path

For an ordinary task handled in one session:

1. Keep the plan in the current task.
2. Use one short-lived `work_memory` slot only when continuation across compaction, sessions, or machines is useful.
3. Deliver the result in the task's final response.
4. Do not create a forum thread or duplicate the result into the forum.

A commit, push, isolated worktree, local test run, routine review, or reversible edit does not by itself justify forum coordination.

## Forum triggers

Use a forum thread only when at least one trigger is present:

- two or more agents are concurrently changing or reviewing shared state;
- a cross-device or cross-node handoff needs a durable shared cursor;
- a shared high-risk change needs an explicit decision or independent review trail;
- an active incident needs coordination among multiple participants.

Record the trigger in the first post. When the trigger ends, stop posting routine progress there. A thread remaining technically `open` does not make it active product work.

## Active shared-thread registry

Keep one project-scoped `work_memory` slot named `coordination`. It may contain at most five active thread IDs, each with a purpose, owner, and close condition. Empty is valid and preferred for ordinary single-developer work. This registry, not the count of historically open forum rows, is the current coordination surface.

If a sixth thread appears necessary, first close or remove a stale registry entry. Do not create a second registry or a new tracking protocol.

## Dogfood check

For each ordinary task, answer only:

- Was a forum trigger present?
- If not, did the task finish without a forum post?
- If work memory was used, was its slot cleared at completion?
- Was any handoff or decision lost because the forum was not used?
- Were any owner restatements, repeated authorization prompts, manual
  interventions observed or left unavailable?
- Did any final-only guardrail fire: lost handoff, boundary overrun, or
  unrelated-WIP damage? These are not `task_outcome.counts` fields and must not
  be added to that strict schema or a new ledger.

R2 is useful when ordinary tasks finish with zero forum ceremony and no lost handoff. Exceptions are evidence to refine the four triggers, not a reason to add more coordination layers.

A new read-only projection, dashboard, schema, hook, or protocol needs a real
dogfood failure plus a user-cost metric and a one- or two-increment closure.
Without that evidence, retain the operating contract and stop expansion.

## Boundaries

R2 does not delete, resolve, or archive historical threads. It does not change MCP exposure, forum storage, runtime behavior, deployment, or the R1 requirement for 20 organically occurring real tasks.

R2 also does not automatically edit `USER.md`, build a behavior or distraction
profile, expand agent authority, reopen a frozen benefit-collection lane, copy
samples into another ledger, or introduce a peer authorization system.
