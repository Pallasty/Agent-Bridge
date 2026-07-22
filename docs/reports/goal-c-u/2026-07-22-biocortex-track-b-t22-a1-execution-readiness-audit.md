# BioCortex Track B T22-A1 execution-readiness audit

Date: 2026-07-22

Status: **FAIL_CLOSED_PRE_SIGN_RUNNER_AND_HOST_READINESS_GAPS_CONFIRMED**

No host, endpoint, private credential, external service, provider API, or
production system was accessed for this audit.

## Decision

Do not bind an A1 owner key to the prior proposal and do not collect real
source-bound attestations yet. The final three-host run cannot honestly be
activated from the currently committed artifacts because the runner and the
host-local execution inputs are not frozen.

The source ordering matters: every domain attestation and later authorization
binds the exact Git commit. Adding a runner after collecting those signatures
would change the commit and invalidate the entire chain. The source-bound
runner and executor therefore have to be committed and tested before the first
real collection challenge is generated.

## Confirmed gaps

1. **No cross-host runner or command executor.** The agent-session core checks
   signed transcript transitions but deliberately opens no socket and executes
   no command. The final execution admission receipt consequently has no
   consumer capable of producing T22-A1-H evidence.
2. **No three-host runtime-readiness contract.** Attestations carry digests for
   a pinned-tool receipt, private data root, and port set, but no private packet
   binds the exact `etcd`, `etcdctl`, `bao`, agent runtime, local data/log roots,
   or host-local credential paths that a runner would use.
3. **No credential-placement proof.** The material preparer creates all leaf
   private keys beneath the coordinator artifact root. Its manifest does not
   prove that each exact domain host possesses the matching key/certificate at
   a private local path with mode `0600`. Treating the central generation path
   as a remote host path would be false.
4. **No single-use execution consumer.** Admission reserves one owner-signed
   contract, but no later gate atomically consumes the admission receipt before
   the first listener, process, or fault action.
5. **No executable evidence builder.** Event and terminal schemas reject unsafe
   synthetic packets, but there is no implementation that creates, verifies,
   secret-scans, and terminalizes the real signed three-domain chain.

## Required closure order

1. Freeze a private domain-runtime-readiness packet and detached domain
   signature for each host. It must bind exact executable hashes, local roots,
   ports, credential placement and domain signing identity without exposing raw
   endpoints or paths publicly.
2. Freeze a bounded mTLS agent and coordinator runner. It must accept only the
   existing command enum, perform no shell evaluation, clear ambient proxy and
   credential variables, bind listeners to exact overlay IPs, and confine
   process/fault actions to owned PIDs and run roots.
3. Add an execution-consumption reservation that validates the final owner
   signature and admission receipt before any credential read, listener, remote
   connection, subprocess, or fault action. Failure remains terminal with no
   automatic retry.
4. Add real-event construction and terminalization with exact domain
   signatures, hash-chain verification, process-log hashing, cleanup receipts,
   secret-value scanning, time/spend bounds and the existing conservative claim
   ceiling.
5. Only after those source files and tests are committed may the owner bind the
   A1 key, choose the third host and begin fresh source-commit-bound collection.

## Decision-packet hardening

The admission contract now truthfully records all three missing execution
surfaces as `false`. The owner proposal also requires explicit values for:

- credential initial-placement mode;
- the exact three runtime-readiness packet hashes;
- their exact three detached-signature hashes; and
- the exact source-bound runner/executor source hash set.

This is a fail-closed correction, not an execution authorization. It creates no
permission to read credentials, connect hosts, start listeners or services,
inject faults, spend money, or make production claims.
