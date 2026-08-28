# R9 installed acceptance gate

Date: 2026-08-28
Status: clean source candidate and isolated restart exercise PASS; current installation FAIL_CLOSED; authoritative publication and deployment blocked

## Decision boundary

The clean source candidate is
`9bc924a2c1641983ac954ee9416e18ddb5fcdf77`. Its locally built exercise binary
has SHA-256
`f0b5fbdfe295d91f7c21f529aff0e9414bd4ebbe8948b1c4a258bdcb111dce4c`
and reports build identity `9bc924a2c164`. This establishes a reproducible
source-candidate exercise identity only. It does not establish that the
candidate was published, installed, adopted by the three long-running
services, or admitted through installed live acceptance.

The authoritative GitLab/publisher identity is still unavailable on this node.
No deployment or production service restart was performed for this report, and
there is no installed PASS claim. The new read-only verifier was executed
against the existing installation and returned `FAIL_CLOSED`. That observation
confirms the preregistered stop rule; it is not positive admission evidence.

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
   of the owned receipt residue. The private root is short enough for the real
   `receipt-<id>/supervisor.sock` Unix-socket path, and the harness primes one
   read-only Linux body sample before crossing two fixed sampling windows; an
   `Unknown` body event is never accepted as success.

The dedicated Python suite passed 62/62 tests: 24 installed-verifier cases and
38 restart-harness cases, with warnings as errors. The final source regression
also passed `ab-agent` 156/156, the six receipt-root Doctor cases, the startup
Duplicate log case, the live-commit Duplicate case, both crates' all-target
checks, the three deploy-marker shell suites, Python compilation, shell syntax,
format checks on the touched Rust modules, and `git diff --check`. Existing
unrelated compiler warnings remain unchanged.

## Isolated source-candidate exercise

The explicitly authorized exercise against the exact candidate binary returned
`PASS` without touching a production service or production spool. At the
observable crash point, SQLite had committed before any filesystem ACK could
succeed and one receipt remained pending. MCP1 was then proven SIGKILLed; MCP2
reported exactly one Duplicate and acknowledged the same receipt. The result
retained one ledger row and two semantic events before and after restart,
changed no row, emitted no `workload_receipt_reconciled` event, executed the
stand-in exactly once, and left no receipt entry, private trial root, or exact
transient scope. The body event remained hard-gated as `Verified` with complete
delegated CPU/memory workload-tree evidence.

This is deliberately a source-candidate exercise before publication. The
frozen release sequence below still requires the authoritative installed build
to repeat the gate; this result cannot substitute for it.

## Current installed read-only observation

The current installed binary still matches its pre-existing expected SHA-256
`624d379f4a71eced931d68a42e3ee4009744c16639b88f64f21dde945c1bb9c0`.
All three required services were active, both loopback health bodies were
exactly `ok`, and all three service environments resolved the expected receipt
root. The overall result nevertheless correctly returned `FAIL_CLOSED`:

- the installed binary owner boundary failed;
- the production receipt root was absent; and
- daemon, daemon-http, and Palace each executed a deleted old inode in both the
  initial observation and final two-round sweep.

Version execution, receipt-root mode acceptance, and strict Doctor were
therefore `NOT_RUN`. No service, installed file, or production state was
changed by this observation.

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
| Source candidate gate implementation | `SOURCE_VERIFIED` | The checks, Doctor organ, and deploy marker are frozen in the clean candidate. |
| Clean candidate identity | `9bc924a2c1641983ac954ee9416e18ddb5fcdf77` | Local source identity; not publication authority. |
| Local exercise binary identity | `f0b5fbdfe295d91f7c21f529aff0e9414bd4ebbe8948b1c4a258bdcb111dce4c` | Exact-byte source-candidate exercise only; not installed adoption. |
| Authoritative GitLab publication | `BLOCKED` | Authenticated publisher identity/path is unavailable. |
| Authoritative installed build adoption | `NOT_DONE` | No deployment or restart is claimed. |
| Isolated source-candidate restart harness | `PASS` | One execution, exact Duplicate replay, unchanged 1 ledger/2 event rows, zero recovery event and residue. Must repeat after authoritative install. |
| Independent current-installed verifier | `FAIL_CLOSED` | Unsafe owner boundary, absent receipt root, and three deleted service executables block later checks. |
| R9 deployed/live-admitted | `NO` | A PASS claim is prohibited. |

## Remaining release-owner fields

- **PENDING — authoritative publication receipt:** authenticated GitLab commit
  and publisher evidence.
- **PENDING — authoritative release binary SHA-256:** the exact installed
  artifact produced by the authorized workflow.
- **PENDING — post-install isolated harness result:** repeat against that exact
  artifact.
- **PENDING — post-restart installed verifier and fresh-MCP admission:** all
  aggregate and per-service gates green in one installed observation.

Until all required evidence is authoritative, exact-candidate-bound, and green,
the only truthful product status is: source candidate and isolated exercise
verified, current installation failed closed, R9 not deployed, installed
acceptance not admitted.
