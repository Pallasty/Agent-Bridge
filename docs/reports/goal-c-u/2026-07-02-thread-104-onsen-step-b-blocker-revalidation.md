# Thread 104 Onsen Step B Blocker Revalidation

Date: 2026-07-02

Status: `READ_ONLY_BLOCKER_REVALIDATION / NO_RUNTIME_CHANGE / KEEP_THREAD_OPEN`

## Decision

Keep thread #104 open as the BioCortex opt-in / LSWR live-runtime evidence
continuation.

The current blocker is unchanged: Agent-Bridge still lacks the accepted Onsen
Step B checkout or an accessible repository URL for the accepted branch/head.
Without that source and a running newline-JSON TCP dev host on
`127.0.0.1:37691`, do not rerun live `world_visibility_query` evidence or claim
verified Onsen runtime action-result evidence.

## Current Repository State

Before this report:

```text
HEAD = 757bb7a feat(memory): durable valence labels + one-shot apply stamps (#51)
master == origin/master
```

Unrelated local file observed and left untouched:

```text
?? scripts/verify-outcome-valence-ingest-copied-db.sh
```

That file belongs to the adjacent outcome-valence lane and was not staged,
edited, or deleted by this pass.

## Runtime Health

`agent-bridge.real doctor --json`:

| Check | Result |
|---|---|
| overall | `ok=true`, `fails=0`, `warns=0` |
| MCP servers | 7 servers, all executing current `agent-bridge.real` |
| MCP tool surface | `claude-standard+cursor=142`, current process `142` |
| daemon runtime | running with `AB_SUBSTRATE_PROJECTION=svd` |

Runtime health is not the blocker.

## Thread #104 Latest State

Latest #104 post remains `#2418`, which records Slice 49:

- the host-launch-plan fixture landed;
- the source-resolution and launch-plan fixtures are wired into the opt-in
  experiment plan;
- the boundary remains read-only;
- current blocker is `provide_or_sync_onsen_step_b_checkout_or_repository_url`;
- after source is available, the operator should launch the newline-JSON TCP
  host at `127.0.0.1:37691`, then rerun live `world_visibility_query` evidence.

## Revalidation Commands

Default accepted checkout probe:

```text
scripts/probe-onsen-step-b-host-source.sh --no-remote
```

Result:

| Field | Value |
|---|---|
| status | `blocked_missing_onsen_step_b_source` |
| expected checkout | `/Data/CascadeProjects/onsen-hd-live-semantic-phase0` |
| checkout present | false |
| expected branch | `codex/live-semantic-phase0-t1` |
| expected head | `10d58ee` |
| listener `127.0.0.1:37691` | false |
| source_found | false |
| ready_for_live_probe | false |
| next_step | `provide_or_sync_onsen_step_b_checkout_or_repository_url` |

Local `/Data/CascadeProjects/Onsen-HD` probe:

```text
scripts/probe-onsen-step-b-host-source.sh --no-remote --checkout /Data/CascadeProjects/Onsen-HD
```

Result:

| Field | Value |
|---|---|
| checkout present | true |
| git branch | `main` |
| git head | `d070ad7` |
| branch matches expected | false |
| head matches expected | false |
| source_found | false |
| ready_for_live_probe | false |

Remote-source probe:

```text
scripts/probe-onsen-step-b-host-source.sh
```

Result:

| Candidate | Result |
|---|---|
| `git@github.com:pallasting/onsen-hd-live-semantic-phase0.git` | `not_found_or_inaccessible` |
| `git@github.com:pallasting/onsen.git` | `not_found_or_inaccessible` |
| `git@github.com:pallasting/Onsen-HD.git` | `reachable_but_not_accepted_step_b_source` at `d070ad7...` |

Host-launch plan:

```text
scripts/plan-onsen-step-b-host-launch.sh --no-remote
```

Result:

| Field | Value |
|---|---|
| status | `blocked_missing_onsen_step_b_source` |
| source_found | false |
| ready_for_live_probe | false |
| launch action | `none` |
| operator_action_required | false |
| Agent-Bridge starts host | false |
| next_step | `provide_or_sync_onsen_step_b_checkout_or_repository_url` |

## Interpretation

The available `/Data/CascadeProjects/Onsen-HD` checkout does not satisfy the
accepted Step B identity contract. It is useful as a nearby Onsen repository,
but it is not the accepted LSWR Step B source because it lacks the expected
branch/head.

Therefore the next valuable action is not Agent-Bridge implementation. It is
source/host provisioning:

1. provide or sync the accepted Step B checkout at
   `/Data/CascadeProjects/onsen-hd-live-semantic-phase0`, or provide an
   accessible repository URL containing branch `codex/live-semantic-phase0-t1`
   at head `10d58ee`;
2. launch the accepted Onsen newline-JSON TCP dev host on `127.0.0.1:37691`;
3. rerun the strict source probe and then collect live `world_visibility_query`
   evidence through Agent-Bridge.

## Boundary

This pass did not:

- clone repositories;
- start Onsen, Godot, LSWR, or any TCP host;
- call live `world_visibility_query`;
- execute LSWR actions;
- call `memory_search`;
- run BioCortex;
- write approvals, memory rows, graph edges, schemas, embeddings, or DB state;
- change default retrieval order, ranking, runtime flags, MCP profiles, or
  deployed binaries;
- change thread #104 status.
