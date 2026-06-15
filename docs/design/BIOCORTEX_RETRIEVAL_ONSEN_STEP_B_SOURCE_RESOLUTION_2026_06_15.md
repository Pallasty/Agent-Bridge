# BioCortex Retrieval Onsen Step B Source Resolution

Date: 2026-06-15

## Summary

The host-attach preflight showed that the Agent-Bridge client path is ready to
rerun `world_visibility_query` against the intended onsen Step B LSWR host, but
the real host runtime is not available on this Linux checkout. This slice
records the source-resolution result for that missing runtime.

Machine-readable fixture:

- `docs/design/fixtures/biocortex-retrieval-onsen-step-b-source-resolution-2026-06-15.json`

Source preflight:

- `docs/design/fixtures/biocortex-retrieval-loopback-lswr-host-attach-preflight-2026-06-15.json`

## Result

The resolution step is blocked by a missing accepted onsen Step B checkout or an
accessible repository URL:

```text
status=blocked_missing_onsen_step_b_source
documented_worktree=/Users/pallasting/Projects/onsen-hd-live-semantic-phase0
documented_branch=codex/live-semantic-phase0-t1
documented_head=10d58ee
expected_endpoint=127.0.0.1:37691
expected_protocol=newline_json_tcp
```

The documented macOS worktree is not present on this Linux host. The candidate
Linux path `/Data/CascadeProjects/onsen-hd-live-semantic-phase0` is also absent,
and there is no listener on `127.0.0.1:37691`.

Three GitHub SSH candidates have now been checked:

- `git@github.com:pallasting/onsen-hd-live-semantic-phase0.git`
- `git@github.com:pallasting/onsen.git`
- `git@github.com:pallasting/Onsen-HD.git`

The first two did not resolve to a usable repository from this environment.
`Onsen-HD` is accessible, but it is not the accepted Step B host source: it only
exposes `main` at `79993b494cf6e41fbacb33f2ab2c6ea9ea544771`, does not contain
the documented `codex/live-semantic-phase0-t1` branch or `10d58ee` head, and did
not expose the expected `world_query`, `world_patch`, `world_visibility_query`,
or `127.0.0.1:37691` host contract during inspection.

The local `prototypes/lswr-web-prototype` remains useful as a prototype, but it
is not the accepted newline-JSON TCP onsen Step B world-tool host.

## Recovery Probe

The source-resolution path now has a reusable read-only probe:

```text
scripts/probe-onsen-step-b-host-source.sh
```

The probe checks:

- candidate checkout presence and git branch/head;
- candidate git remotes with `git ls-remote`, unless `--no-remote` is passed;
- whether a checkout or remote actually matches the documented branch/head,
  rather than merely being a reachable git repository;
- loopback listener state for the expected newline-JSON TCP endpoint;
- whether the next step is still source sync, host launch, or live probe rerun.

It does not clone repositories, start a host, execute LSWR actions, call
`memory_search`, run BioCortex, write approval state, mutate the default
Agent-Bridge DB, or change default retrieval order.

## Host Launch Plan

The next hop now has a reusable read-only plan generator:

```text
scripts/plan-onsen-step-b-host-launch.sh
```

The current blocked launch-plan result is recorded in:

```text
docs/design/fixtures/biocortex-retrieval-onsen-step-b-host-launch-plan-2026-06-15.json
```

The plan consumes the source probe output, or runs the source probe itself, and
emits a machine-readable `onsen_step_b_host_launch_plan.v0` envelope. It never
starts Godot, starts a host process, clones source, executes LSWR actions, or
collects runtime evidence. If an accepted checkout is found but no listener is
available yet, the plan marks the state as `ready_for_operator_host_launch` and
keeps host launch owned by the operator or onsen runtime.

## Boundary

This source-resolution slice does not:

- attach a real onsen runtime;
- verify the human-visible onsen root viewport;
- execute LSWR actions;
- emit or persist a durable runtime `agent_bridge.semantic_bus.action_result.v0`;
- call AiOT runtime;
- call `memory_search`;
- run BioCortex;
- write approval state;
- mutate the default Agent-Bridge DB;
- change default `memory_search` return order;
- include host response payloads, raw memory keys, memory content, raw
  side-signal rows, or human decision text.

## Next Step

Provide or sync the accepted onsen Step B checkout or repository URL, then
launch the newline-JSON TCP dev host and rerun the live
`world_visibility_query` probe:

```text
provide_or_sync_onsen_step_b_checkout_or_repository_url_then_launch_dev_host
```

After the checkout or repository URL is available, run:

```text
scripts/probe-onsen-step-b-host-source.sh --checkout /path/to/onsen-step-b
scripts/plan-onsen-step-b-host-launch.sh --checkout /path/to/onsen-step-b
```
