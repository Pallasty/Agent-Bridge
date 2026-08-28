# R9 installed acceptance gate

Date: 2026-08-28
Status: source-side gate implemented; clean identity and execution evidence pending; authoritative publication and deployment blocked

## Decision boundary

The current shared worktree implements the source candidate needed to evaluate
an installed R9 deployment. It does not establish that this candidate has been
published, installed, adopted by the three long-running services, or admitted
through live acceptance.

The authoritative GitLab/publisher identity is still unavailable on this node.
No deployment or production service restart was performed for this report, and
there is no installed PASS claim. The existing installation is expected to
fail the new read-only verifier closed until an authorized publication and
exact installed build adoption occur. This is a preregistered expectation, not
an observed verifier result.

## Implemented source candidate gate

The candidate contains three bounded parts:

1. Doctor now includes `workload_receipt_root`. It resolves the production
   workload-receipt root without creating it and reports its physical
   owner/mode boundary in the normal strict Doctor result.
2. `scripts/verify-r9-installed-deployment.py` is an independent, read-only,
   fail-closed verifier. It requires an explicit absolute physical binary,
   expected SHA-256, expected commit, and absolute physical production receipt
   root. It binds the binary and replacement-authority boundary; requires
   `agent-bridge-daemon.service`, `agent-bridge-daemon-http.service`, and
   `agent-bridge-palace.service` to remain active on that exact executable path
   and content; verifies each service resolves the same receipt root; binds the
   systemd user bus to the current UID's validated runtime directory; requires
   exact `ok` bodies from ports 7878 and 7979; and requires Doctor to return
   `ok=true`, zero failures, zero warnings, and an `ok`
   `workload_receipt_root` check. Its JSON omits process IDs, filesystem paths,
   subprocess output, and environment contents.
3. `scripts/verify-r9-installed-receipt-restart.py` defaults to read-only
   preflight. Its live mode requires the exact confirmation token and uses an
   exact-byte private binary copy plus a disposable isolated state root to test
   commit-before-ACK interruption, restart replay, Duplicate classification,
   unchanged committed row counts, exact transient-scope cleanup, and removal
   of the owned receipt residue.

Dedicated fake-fixture unit tests cover the verifier and harness. Their
presence is source evidence only; the final clean-candidate test ledger and all
live results remain release evidence to be filled below.

## Frozen release and acceptance order

The release owner must preserve this order. A later step cannot repair or
substitute for a missing earlier authority boundary.

1. Freeze a clean source candidate and record its exact 40-hex commit.
2. Build the candidate through the authoritative release path and bind its
   exact SHA-256 to that commit.
3. Publish with an authenticated, authorized GitLab/publisher identity. A local
   file remote, local-only commit, copied binary, or manual override is not a
   substitute.
4. Install through the authoritative deployment workflow and deliberately
   restart daemon, daemon-http, and Palace onto the exact admitted binary.
5. Run the isolated restart harness against the pinned candidate binary and
   retain its privacy-bounded result.
6. Run the independent installed verifier against the exact physical installed
   binary and production receipt root. PASS requires every aggregate and
   per-service check to pass in the same bounded observation.
7. Retain the publisher's fresh-MCP admission and the no-residual-spool/scope
   evidence required by the original R9 live-acceptance plan.

Any mismatch, unstable service identity, unsafe or inconsistent receipt-root
binding, non-exact executable path/content, non-`ok` health response, Doctor
failure or warning, harness residue, missing publisher authority, or
mixed-candidate evidence stops admission. It must not be relabeled as a partial
PASS.

## Evidence ledger

| Evidence | State on 2026-08-28 | Admission meaning |
|---|---|---|
| Source candidate gate implementation | `IMPLEMENTED_SOURCE_ONLY` | The checks and harness exist in the shared worktree. |
| Clean candidate identity | `PENDING` | No final clean commit is recorded here. |
| Authoritative GitLab publication | `BLOCKED` | Authenticated publisher identity/path is unavailable. |
| Authoritative installed build adoption | `NOT_DONE` | No deployment or restart is claimed. |
| Isolated live restart harness | `PENDING` | No final bounded live result is recorded. |
| Independent installed verifier | `PENDING` | Expected current-node outcome is fail-closed; no final result is recorded. |
| R9 deployed/live-admitted | `NO` | A PASS claim is prohibited. |

## Release-owner fill-in fields

- **PENDING — clean source commit:** `<40 lowercase hex>`
- **PENDING — candidate/installed binary SHA-256:** `<64 lowercase hex>`
- **PENDING — isolated live harness result:** `<bounded result and evidence reference>`
- **PENDING — final installed verifier result:** `<bounded result and evidence reference>`

Until all required evidence is authoritative, exact-candidate-bound, and green,
the only truthful product status is: source candidate gate implemented, R9 not
deployed, installed acceptance not admitted.
