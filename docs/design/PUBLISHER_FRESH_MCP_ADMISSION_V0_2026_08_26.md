# Publisher Fresh-MCP Admission v0

Status: local candidate

## Purpose

`scripts/deploy_from_master.sh` already records a deployment as
`fresh_mcp=unverified` after the installed binary, runtime assets, and resident
services have passed their publisher gates. Fresh-MCP admission v0 adds the
missing consumer for that state.

The consumer proves that the exact pending installed binary can start a new
independent MCP stdio process, complete initialization, select the
`codex-essential` profile, expose a self-consistent tool list, and return build
identity through the `capabilities` tool. It then retires the matching pending
state into an immutable receipt and quarantine pair.

Invocation:

```bash
scripts/deploy_from_master.sh --admit-fresh-mcp
```

This mode performs no build, install, service restart, remote access, or source
mutation.

## Evidence Boundary

The probe launches the exact `real_path` recorded by
`pending-admission.meta`. It uses isolated `XDG_DATA_HOME` and
`AGENT_BRIDGE_STATE_DIR` roots and forces `AGENT_BRIDGE_TOOLSET=codex-essential`.
It requires all of the following:

- MCP protocol `2024-11-05` initializes successfully.
- Server identity is `agent-bridge`.
- `tools/list` exposes `capabilities` exactly once.
- `capabilities(compact=true)` succeeds as a single structured text result.
- `build.git_sha` equals the first 12 characters of the pending 40-hex commit.
- The reported toolset is `codex-essential`.
- The reported exposed tool count equals the actual `tools/list` count.
- The installed binary and runtime-asset fingerprint still match the pending
  record before and after the probe.

The durable receipt stores only identity and manifest-count metadata plus a
canonical evidence hash that the consumer recomputes before admission. It does
not retain capability response content, stderr, memory records, tool arguments,
or tool results. v0 does not pin or claim the complete essential tool-name or
input-schema set; source and deployment anti-regression gates remain responsible
for that broader contract.

## Transaction

The host-wide publisher kernel mutex serializes the entire operation. Admission
uses a fixed completion intent at
`fresh-mcp-admission-intent.meta` to bind:

- the exact pending lease, challenge, candidate, paths, and pending-file hash;
- deterministic receipt and quarantine paths; and
- the validated probe identity and evidence hash.

Settlement publishes the exact admission receipt first and then atomically
moves `pending-admission.meta` to its prebound quarantine path. The publisher
lease is released through the existing release intent transaction. Only after
that release completes is the fresh-MCP completion intent archived.

Every transition is replayable:

| Interrupted state | Next publisher behavior |
| --- | --- |
| Probe failed before intent publication | Preserve canonical pending state |
| Intent exists, receipt absent, pending canonical | Publish receipt and quarantine pending |
| Receipt exists, pending still canonical | Verify exact receipt and quarantine pending |
| Receipt exists, pending already quarantined | Verify both artifacts and complete release |
| Prebound receipt differs | Fail closed and preserve the completion intent |
| Installed binary/assets drift | Fail closed without admitting the pending state |

Unknown schemas, symlinks, path escapes, duplicate canonical/quarantined state,
and identity or fingerprint mismatches fail closed.

## Non-Claims

Fresh-MCP admission v0 does not prove that an already-running Codex or Claude
connection adopted the new process. It does not prove every tool's business
workflow, external side effects, user authorization, daemon HTTP adoption, or
device/runtime behavior. Those remain separate evidence gates.

In particular, an AG-UI end/result event remains stream-local observation and
does not become Agent-Bridge `verified` status through this admission.

## Regression Coverage

`scripts/test-deploy-publisher-lease-v0.sh` covers:

- successful exact admission and artifact binding;
- replay after receipt publication but before pending quarantine;
- replay after pending quarantine but before publisher release;
- direct recovery after `SIGKILL` with a prepared active lease;
- an actual controlled MCP executable covering initialize/list/call framing;
- duplicate JSON-RPC response and invalid evidence-digest rejection;
- wrong-build probe rejection;
- post-pending installed-binary drift rejection; and
- conflicting prebound receipt rejection with durable intent preservation;
- publisher state-directory symlink rejection.

The suite runs entirely in a mode-700 OS temporary root and cannot address the
production publisher state tree.
