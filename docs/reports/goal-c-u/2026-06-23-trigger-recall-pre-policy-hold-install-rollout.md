# Trigger Recall Pre-Policy Hold Install Rollout

Date: 2026-06-23

Scope: installed-binary rollout of the already-merged Trigger Recall
pre-policy hold simulation and approval-packet validator surfaces.

This report records a separate owner follow-up authorization after the earlier
merge/aio2-evidence documents, which explicitly did not authorize deployment.
It authorizes only the local `agent-bridge.real` installed-binary rollout from
current `origin/master`; it does not authorize production retrieval behavior
changes.

## Rollout Target

| Field | Value |
|---|---|
| deploy source | `origin/master @ 8f0be61` |
| code payload | `fbeebeb merge trigger pre-policy hold simulation candidate` |
| docs-only audit evidence | `8f0be61 docs(memory): add pre-policy hold aio2 audit evidence` |
| installed binary | `/home/pallasting/.local/bin/agent-bridge.real` |
| deployed size | `67113016` bytes |
| deployed sha256 | `fd7800aedef48732dd044a06b52916893cc246cf2b7f784d7d4f35f5e3a40b4a` |
| backup | `/home/pallasting/.local/bin/agent-bridge.real.bak-deploy-8f0be61-20260623T071437` |

## Pre-Rollout Verification

Run on current mainline before rollout:

```text
CARGO_BUILD_JOBS=2 cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
```

Result: passed, 36 tests.

```text
CARGO_BUILD_JOBS=2 cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
```

Result: passed, 27 tests.

```text
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
```

Result: passed with existing warnings only. Observed:

- true hits lost by shadow gate: `0`;
- positive cases held: `0`;
- baseline false hits after shadow gate: `0`;
- default `memory_search` unchanged;
- no MCP `memory_search`, memory writes, graph writes, or reindex.

```text
CARGO_BUILD_JOBS=2 cargo check -p ab-bridge --lib
CARGO_BUILD_JOBS=2 cargo check -p ab-bridge --all-targets
git diff --check
git diff --cached --check
```

Result: passed with existing warnings only.

## Rollout Command

```text
scripts/deploy_from_master.sh --yes
```

The deploy script:

- fetched current `origin/master`;
- built a release binary in `/home/pallasting/.cache/agent-bridge-deploy-target`;
- verified the new binary was a superset of the currently deployed feature
  markers;
- backed up the previous `.real`;
- copied the new binary over `/home/pallasting/.local/bin/agent-bridge.real`.

Required markers were present after deploy:

- `desktop_steer.py`;
- `desktop_action.py`;
- `desktop_invoke.py`;
- `desktop_confirm`;
- `avatar_renderer`;
- `present_voice`;
- `browser_navigate`;
- `memory_save`;
- `forum_post`.

The deployed binary also contains:

- `trigger_recall_enforce_hold_approval_packet_validator`;
- `trigger_recall_opt_in_pre_policy_hold_simulation`.

## Post-Rollout Verification

```text
/home/pallasting/.local/bin/agent-bridge.real doctor --json
```

Result:

- `ok=true`;
- `fails=0`;
- `warns=1`.

The one warning is expected after replacing `.real`: two existing Cursor/Codex
MCP server processes still map the old deleted inode. They need MCP reconnect or
client restart before those sessions see the newly deployed tool manifests.

The runtime lifecycle digest reported Agent-Bridge readiness and runtime health
as `ready`, with daemon-http and Palace health checks passing.

## Boundaries Preserved

This rollout still does not authorize:

- default `memory_search` behavior, schema, or ordering changes;
- production `enforce_hold`;
- exposing the simulation outside `Tier::Niche`;
- semantic or graph retrieval changes;
- memory writes;
- graph writes.

The installed rollout only makes the already-merged Niche/read-only or
explicit-opt-in surfaces available after MCP reconnect.
