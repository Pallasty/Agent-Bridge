# Scope Project ID Canonical Policy

Date: 2026-06-24

Status: design guardrail, updated after owner ratification

Related local authorization ledger:
`MEMORY_AUTHORIZATION_CONTRACTS_2026_06_25.md`.

## Context

Agent-Bridge is moving project-scoped memory from path-shaped scopes such as
`project:/Users/pallasting/Projects/agent-bridge` toward stable project IDs such
as `project-id:git:gitlab.com/pallasting/agent-bridge`.

The trace-only `memory_save(scope_identity_trace=true)` path can now report an
explicit project ID from either:

- a caller supplied `scope=project-id:...`; or
- `AGENT_BRIDGE_PROJECT_ID`, when no project-id scope is supplied.

It also reports a no-op `scope_write_shadow_comparison` decision when requested.
That trace does not rewrite stored memory scope today. It exists to prove the
identity and policy decision before any production write switch.

## Problem

`AGENT_BRIDGE_PROJECT_ID` is a process-level environment variable. A shared MCP
process can serve Codex turns for multiple workspaces. If that global variable is
set to the Agent-Bridge canonical ID, a save from another project could trace as
Agent-Bridge even when the requested scope is `project:/some/other/project`.

That is acceptable for a dedicated single-project smoke process. It is not
acceptable as a production policy for shared Codex, Claude Code, Cursor, Warp, or
daemon-http sessions.

There is also a host-choice problem. Different nodes have observed different
primary remotes. Choosing GitLab versus GitHub as the canonical host is a policy
decision, not a fact that should be silently inferred from whichever remote name
happens to be `origin` on the current machine.

## Decision

Do not configure a global `AGENT_BRIDGE_PROJECT_ID` in shared MCP sessions as a
production write policy.

The environment variable remains valid for:

- trace-only experiments;
- dedicated single-project MCP processes; and
- CI or smoke runs where the working directory and process lifetime are scoped
  to one project.

Production canonical writes must wait for a root-bound or registry-bound policy
that proves the requested project scope belongs to the selected stable project
ID.

## Precedence

Future production identity selection should use this order:

1. Explicit `scope=project-id:...` supplied by the caller.
2. A trusted scope registry that maps requested legacy project scopes and aliases
   to an approved canonical project ID.
3. A dedicated process-scoped `AGENT_BRIDGE_PROJECT_ID`, only when the process is
   declared single-project and the requested scope is inside that project root.
4. Git remote identity as high-confidence evidence, not as an automatic host
   selection when multiple public mirrors exist.
5. `GitRootName` and path fallback identities as trace evidence only.

`GitRootName` and path fallback identities are not production-eligible canonical
write targets.

## Agent-Bridge Project Policy

Owner ratified the Agent-Bridge canonical host in forum #120 post #4297:

```text
canonical_project_id=project-id:git:gitlab.com/pallasting/agent-bridge
production_project_id_writes_authorized=false
```

For `/Users/pallasting/Projects/agent-bridge`, the current live trace on this
Mac also resolves to:

`project-id:git:gitlab.com/pallasting/agent-bridge`

GitHub remains a synchronized mirror and may appear as evidence on another node,
but it is not the canonical write target unless a later owner decision supersedes
#4297. A future write switch must use the reviewed GitLab canonical policy, not
whichever remote name happens to be available in the running process.

## Acceptance Gates For Write Switch

A future implementation that stores canonical project IDs instead of path scopes
must prove all of these before deployment:

- `scope_canon_rescue_gate` remains PASS against the live store or a current
  snapshot.
- `memory_save(scope_identity_trace=true)` reports which source selected the
  identity: `scope`, `policy`, `env`, or `git_remote`.
- A non-Agent-Bridge project save in the same shared MCP process does not inherit
  the Agent-Bridge canonical ID.
- Ambiguous multi-remote checkouts require explicit policy instead of silently
  choosing a host.
- The production write switch and any database backfill/migration are separate
  slices.

## Non-Goals

This document does not:

- switch stored memory scopes to `project-id:*`;
- migrate existing rows;
- add a new MCP tool; or
- choose any replacement for the owner-ratified GitLab canonical host.
