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

1. **No live cross-host runner or process backend.** The fixed-command executor
   and mTLS framing/context cores are now frozen, but their activation constants
   remain false. No socket adapter, owned-process backend, or end-to-end runner
   can yet consume the final execution admission receipt and produce T22-A1-H
   evidence.
2. **Three-host runtime-readiness contract and signed-set verifier — closed
   after this audit.** The private packet binds exact executable, local-root,
   port, credential-placement and operator/coordinator identities for each role.
   The verifier freshly revalidates the original attestation bundle, requires
   each readiness packet to use that domain's admitted operator key under a
   purpose-separated namespace, and emits only a non-executing private receipt.
   The three real packets and detached signatures remain uncollected.
3. **No credential-placement proof.** The material preparer creates all leaf
   private keys beneath the coordinator artifact root. Its manifest does not
   prove that each exact domain host possesses the matching key/certificate at
   a private local path with mode `0600`. Treating the central generation path
   as a remote host path would be false.
4. **Single-use execution consumer — closed after this audit.** The consumer
   independently verifies the clean source commit and exact final owner SSHSIG
   before reading the private admission receipt, reserves it atomically before
   runner dispatch, requires bound terminal evidence for PASS, and makes
   failure terminal with no retry. The network runner itself remains absent.
5. **No executable evidence builder.** Event and terminal schemas reject unsafe
   synthetic packets, but there is no implementation that creates, verifies,
   secret-scans, and terminalizes the real signed three-domain chain.

## TLS applicability correction

The initial runtime-material implementation issued each domain leaf with only
`serverAuth`. That is insufficient for an etcd peer identity: the same peer
certificate is used when accepting and initiating peer TLS, and peer-client
authentication requires both `serverAuth` and `clientAuth`. The frozen
pre-run implementation now issues and independently verifies both EKUs on each
domain leaf while keeping the coordinator leaf client-only. This also permits a
domain node to present its own client certificate during an mTLS OpenBao Raft
join without creating another unbound identity.

Primary specifications: [etcd v3.7 transport security](https://etcd.io/docs/v3.7/op-guide/security/)
and [OpenBao integrated storage TLS](https://openbao.org/docs/2.4.x/concepts/integrated-storage/).
This correction changes no schema bytes, grants no runtime authority, and reads
no real credential.

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

## Implemented closure evidence

`biocortex_ab_track_b_t22_a1_execution_consumer_v1.py` and its KAT now close
item 4. The KAT exercises one complete synthetic single-use dispatch and 42
negative cases, including wrong signature before private receipt reads,
caller-selected source commit, replay, runner failure, post-run expiry, missing
terminal evidence, terminal cross-binding forgery, cleanup and budget
escalation. It reads zero real instances and performs no network, listener,
workload, fault or credential action.

`biocortex_ab_track_b_t22_a1_domain_runtime_readiness_v1.py`, its closed schema
and KAT now close the contract and signed-set verification portion of item 2.
Three synthetic domain-role packets and one complete same-key signed set pass;
52 semantic, file-set, namespace, signature, key, ordering, freshness and
cross-binding mutations fail. Real packet/signature collection remains a later
owner-authorized step.

`biocortex_ab_track_b_t22_a1_domain_workload_plan_v1.py` now freezes the first
runner-side source component. It purely compiles each verified private endpoint
and readiness position into exact etcd argv, mTLS OpenBao HCL, owner-only paths,
cleared process environment, deterministic workload values and a role-specific
command allowlist. Three synthetic plans pass and 42 unsafe input/plan mutations
fail. It starts nothing and does not close the still-missing executor, transport
or evidence-builder findings.

`biocortex_ab_track_b_t22_a1_domain_executor_core_v1.py` closes the fixed-command
dispatch/state/evidence-core portion, but not the live backend. Three synthetic
domain lifecycles produce 23 independently replay-verified private command
receipts; 19 mutations fail, including dispatch-after-failure, timeout, spend,
observation, transition, chain and timing attacks. Any failure after backend
dispatch becomes an absorbing terminal state. Non-synthetic backends remain
hard-disabled, so no process, listener, credential or network action is enabled.

`biocortex_ab_track_b_t22_a1_mtls_transport_v1.py` closes the bounded wire-frame
and TLS-context portion, but not the live socket adapter. Its KAT performs one
real TLS 1.2/1.3-capable mutual-authentication handshake entirely through
`ssl.MemoryBIO`, round-trips one signed-message envelope and one bounded
ephemeral OpenBao unseal-secret frame, and rejects 27 framing, route, digest,
certificate, hostname, permission and activation mutations. The contexts bind
the exact plan-selected CA and leaf certificate files, require owner-only files,
verify the exact peer certificate digest after TLS authentication, and keep
transport activation false. The KAT opens no socket, starts no listener and
contacts no host.
