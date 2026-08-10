# R2 Low-Ceremony Operating Mode

R2 reduces the coordination work paid by a single developer. It changes operating behavior, not the Agent-Bridge runtime.

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

R2 is useful when ordinary tasks finish with zero forum ceremony and no lost handoff. Exceptions are evidence to refine the four triggers, not a reason to add more coordination layers.

## Boundaries

R2 does not delete, resolve, or archive historical threads. It does not change MCP exposure, forum storage, runtime behavior, deployment, or the R1 requirement for 20 organically occurring real tasks.
