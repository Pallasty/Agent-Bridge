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

The controller runs the physical, root-owned `/usr/bin/python3` with `-I`; it
does not resolve the controller interpreter through `PATH`. The interpreter is
given only explicit arguments, while the MCP child receives a minimal allowlist
environment with fixed system `PATH`, private `HOME`/XDG/state/temp roots, and
the required Agent-Bridge profile selectors. Caller `PYTHONPATH`, `PYTHONHOME`,
`sitecustomize`, `DYLD_*`, `LD_*`, and unrelated Agent-Bridge/deploy variables
are not inherited.

While holding the publisher mutex, the controller copies the physical
`real_path` recorded by `pending-admission.meta` into its private mode-700 probe
root, hashes the copied bytes, requires that digest to equal the pending
installed-binary digest, makes only that private copy executable, and launches
it. The original installed path and complete pending fingerprint are checked
again after the probe. This closes a path-resolution/same-path replacement gap
without changing the installed baseline.

The stdio exchange uses nonce-derived string request IDs, nonblocking bounded
stdout/stderr collection, and a fixed wall-clock deadline. The MCP process owns
a new process group. The controller kills that entire group on timeout, output
overflow, parse/identity failure, and after a normal direct-parent exit before
draining final output. A final cleanup path repeats group termination and waits
for the direct child, so a helper inherited from the MCP parent cannot outlive
the admission attempt or keep output descriptors open indefinitely.

It requires all of the following:

- MCP protocol `2024-11-05` initializes successfully.
- Server identity is `agent-bridge`.
- Every response is an exact JSON-RPC 2.0 object for one expected string ID;
  boolean, wrong, unknown, and duplicate IDs, protocol errors, malformed
  result types, or trailing unclassified responses are rejected.
- JSON decoding rejects duplicate object keys recursively, including duplicate
  `id`/`result` envelope fields and duplicate keys inside the nested
  capabilities text payload. Identical duplicate values are still ambiguous
  and therefore rejected.
- `tools/list` exposes `capabilities` exactly once.
- `tools/list` has no `nextCursor`. Admission v0 deliberately fails closed on
  pagination rather than claiming a partial manifest.
- `capabilities(compact=true)` has no `isError=true` and succeeds as exactly one
  text content block with no additional content blocks.
- `build.git_sha` equals the first 12 characters of the pending 40-hex commit.
- The reported toolset is `codex-essential`.
- The reported exposed tool count equals the actual `tools/list` count.
- The installed binary and runtime-asset fingerprint still match the pending
  record before and after the probe.

The durable receipt stores identity and manifest-count metadata, the random
probe nonce and timing, the private-copy digest, both pending/admission lease
contexts, and domain-separated evidence/admission/receipt binding hashes. The
binding covers the exact pending-file hash, full candidate, challenge, paths,
installed binary inode/mode/digest, runtime-assets digest, pending install time,
and observed probe identity. Thus a valid-looking observation cannot be moved
between pending candidates or replayed under another admission lease.

The receipt does not retain capability response content, stderr, memory
records, tool arguments, or tool results. v0 does not pin or claim the complete
essential tool-name or input-schema set; source and deployment anti-regression
gates remain responsible for that broader contract.

## Transaction

The host-wide publisher kernel mutex serializes the entire operation. Admission
uses a fixed completion intent at
`fresh-mcp-admission-intent.meta` to bind:

- the exact pending lease, challenge, candidate, paths, and pending-file hash;
- the pending install fingerprint and the new admission lease/challenge;
- deterministic receipt and quarantine paths; and
- the nonce-bound probe identity, byte-exact private-copy digest, and
  domain-separated evidence/admission binding hashes.

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
| Exact deterministic settled intent already archived | Reuse it and remove the canonical replay |
| Settled-intent archive is a symlink, unsafe file, or differs | Fail closed and preserve canonical intent |
| Prebound receipt differs | Fail closed and preserve the completion intent |
| Installed binary/assets drift | Fail closed without admitting the pending state |

Unknown schemas, symlinks, path escapes, duplicate canonical/quarantined state,
and identity or fingerprint mismatches fail closed.

## Non-Claims

Fresh-MCP admission v0 proves a new independent process launched from the exact
private binary copy. It does **not** identify or prove that an already-running
Codex or Claude connection adopted that process; reconnect plus a capability
check remains a separate consumer gate. It does not prove every tool's business
workflow, external side effects, daemon HTTP adoption, or device/runtime
behavior. Those remain separate evidence gates.

The physical trust-root, strict-schema, binding, and replay checks protect the
publisher contract against accidental drift, ambient-environment injection,
path substitution, transcript splicing, and partial transactions. They do not
provide cryptographic authenticity against an arbitrary malicious process
already running as the same OS user, which can read and rewrite user-owned
publisher state. A keyed or privileged trust service would be a separate design
if that threat enters scope.

In particular, an AG-UI end/result event remains stream-local observation and
does not become Agent-Bridge `verified` status through this admission.

## Regression Coverage

`scripts/test-deploy-publisher-lease-v0.sh` covers:

- successful exact admission and artifact binding;
- replay after receipt publication but before pending quarantine;
- replay after pending quarantine but before publisher release;
- direct recovery after `SIGKILL` with a prepared active lease;
- an actual controlled MCP executable covering initialize/list/call framing
  from a byte-exact private copy;
- fixed isolated interpreter/minimal-child-environment resistance to hostile
  `PATH`, `PYTHONPATH`, and `sitecustomize`;
- strict JSON-RPC version plus boolean/wrong/unknown/duplicate ID rejection;
- recursive duplicate JSON object-key rejection in envelopes and capabilities;
- `isError`, extra content block, and `nextCursor` rejection;
- bounded stdout/stderr and timeout rejection, with no surviving descendants
  after overflow, timeout, or normal direct-parent exit;
- invalid evidence-digest and nonce/context binding rejection;
- wrong-build probe rejection;
- post-pending installed-binary drift rejection; and
- conflicting prebound receipt rejection with durable intent preservation;
- exact settled-intent replay plus conflicting/symlink target rejection; and
- publisher state-directory symlink rejection.

The suite runs entirely in a mode-700 OS temporary root and cannot address the
production publisher state tree.
