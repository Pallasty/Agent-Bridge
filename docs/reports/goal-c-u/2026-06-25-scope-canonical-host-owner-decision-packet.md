# Scope Canonical Host Owner Decision Packet

Date: 2026-06-25
Status: recommendation packet, not production write authorization

## Purpose

This packet resolves the next open question from
`2026-06-25-scope-phase3-project-id-dry-run-aio2.md`: Agent-Bridge needs one
canonical project ID before any write-time `project-id:*` shadow comparison can
be meaningful.

This document is a recommended owner-decision packet. It is safe to review,
cite, and adopt in a later approval post. It does not change runtime behavior,
does not write memory with `project-id:*`, does not migrate existing rows, does
not change search order, does not write graph edges, does not add an MCP tool,
and does not authorize production canonical writes.

## Recommendation

Adopt the GitHub project ID as the canonical Agent-Bridge memory scope target:

```text
project-id:git:github.com/pallasting/agent-bridge
```

Reason: the current aio2 working checkout, `origin/master` integration path,
deployment source, and memory-sync remote are all GitHub-backed. GitLab remains
valid historical/alternate forge evidence, but should not become the implicit
production write target unless a later owner record explicitly chooses it.

## Evidence

Current local evidence:

- repo: `/Data/CascadeProjects/agent-bridge`;
- code state before this packet: `origin/master == 39ebc56`;
- git remote: `git@github.com:pallasting/Agent-Bridge.git`;
- MCP doctor after reconnect: `9 ok / 0 warn / 0 fail`;
- memory-sync remote: `git@github.com:pallasting/agent-bridge-memory.git`;
- previous dry-run report: `2d2d58c`.

Read-only gate evidence from the prior run:

| Check | Result |
|---|---|
| default `scope_canon_rescue_gate` | PASS; registry recovered 258 local rows vs 254 basename rows |
| GitHub override `scope_canon_rescue_gate` | PASS; same 258 registry-local rows |
| `scope_policy_admission_gate` | PASS; root/child admitted, sibling/parent need review, non-project/different project-id blocked |
| default aio2 `scope_write_identity_dry_run` | proposes `project-id:git:github.com/pallasting/agent-bridge` from `git_remote` |
| explicit GitLab dry-run | eligible when explicitly requested |
| explicit GitHub dry-run | eligible when explicitly requested |

Interpretation: resolver and gate mechanics are not the blocker. The remaining
blocker is policy: choose one canonical host and a reviewed alias registry.

## Candidate Alias Registry

If the GitHub canonical ID is adopted, the first reviewed alias registry should
be:

```text
project-id:git:github.com/pallasting/agent-bridge=
project:/Data/CascadeProjects/agent-bridge,
project:/Programs/Users/Pallasting/Documents/CascadeProjects/agent-bridge,
project:/Users/pallasting/Projects/agent-bridge,
project:/Data/CascadeProjects/agent-bridge-lcc-voice-gate,
project:/Data/CascadeProjects/agent-bridge.wt-tts,
project:/Data/CascadeProjects/agent-bridge-lcc0
```

The registry is intentionally explicit. It must not be replaced by basename-only
matching.

Current known row counts from the dry-run:

| Scope | Rows | Registry action |
|---|---:|---|
| `project:/Data/CascadeProjects/agent-bridge` | 195 | include |
| `project:/Programs/Users/Pallasting/Documents/CascadeProjects/agent-bridge` | 32 | include |
| `project:/Users/pallasting/Projects/agent-bridge` | 27 | include |
| `project:/Data/CascadeProjects/agent-bridge-lcc-voice-gate` | 2 | include as reviewed worktree suffix |
| `project:/Data/CascadeProjects/agent-bridge.wt-tts` | 1 | include as reviewed worktree suffix |
| `project:/Data/CascadeProjects/agent-bridge-lcc0` | 1 | include as reviewed worktree suffix |

## Negative Controls

The following must remain non-local unless explicitly reviewed later:

| Scope | Required outcome |
|---|---|
| `project:/elsewhere/agent-bridge` | not local; same basename alone is insufficient |
| `project:/Data/CascadeProjects/agent-bridge-NOT-IN-REGISTRY` | not local; unreviewed worktree suffix needs review |
| `project:/Data/CascadeProjects` | not local; parent directory is too broad |
| `project-id:git:gitlab.com/pallasting/agent-bridge` | not equivalent to GitHub unless an explicit dual-forge alias policy is accepted |
| `project-id:git:example.com/other/agent-bridge` | blocked |

## Adoption Contract

An owner/adoption post may adopt this packet only if it keeps these flags false:

```text
production_project_id_writes_authorized=false
memory_db_migration_authorized=false
memory_backfill_authorized=false
default_memory_search_change_authorized=false
session_bootstrap_sql_broadening_authorized=false
mcp_surface_growth_authorized=false
graph_writes_authorized=false
ranking_or_candidate_set_change_authorized=false
```

Adoption may authorize only the next read-only or no-op slice:

```text
canonical_project_id=project-id:git:github.com/pallasting/agent-bridge
reviewed_alias_registry=<the explicit registry above>
may_run_shadow_write_comparison=true
shadow_comparison_must_not_mutate_store=true
```

## Next Slice If Adopted

Implement or run a shadow write comparison that reports, for project-scoped
memory saves:

- current legacy scope;
- proposed canonical scope;
- resolver evidence;
- whether the proposed scope is production-eligible;
- preserved legacy scope metadata;
- whether the request would be blocked by the alias registry or negative
  controls.

The shadow comparison must remain no-op for `MemorySaveTool` storage until a
separate production write gate is approved.

## Rollback

If later evidence shows GitLab or a non-host project ID should be canonical,
rollback is straightforward while this remains docs/report-only:

- keep writing legacy `project:/...` scopes;
- replace this packet with a new owner decision packet;
- rerun the same dry-run gates against the replacement canonical ID;
- do not rewrite any memory rows.
