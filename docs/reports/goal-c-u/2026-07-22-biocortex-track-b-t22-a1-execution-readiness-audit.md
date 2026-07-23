# BioCortex Track B T22-A1 execution-readiness audit

Date: 2026-07-22

Status: **FAIL_CLOSED_REAL_HOST_READINESS_PLACEMENT_AND_FINAL_ACTIVATION_REQUIRED**

No host, endpoint, private credential, external service, provider API, or
production system was accessed for this audit.

## Decision

Do not bind an A1 owner key to the prior proposal and do not collect real
source-bound attestations yet. The runner, authenticated domain lane, bounded
local backend and exact evidence finalizer are now frozen, but the final
three-host run still cannot honestly be activated without three real
host-local readiness packets, placement proof and a final activation audit.

The source ordering matters: every domain attestation and later authorization
binds the exact Git commit. Adding a runner after collecting those signatures
would change the commit and invalidate the entire chain. The source-bound
runner and executor therefore have to be committed and tested before the first
real collection challenge is generated.

## Confirmed gaps

1. **Exact launch binding — closed after this audit.** The
   fixed-command executor, mTLS socket adapter, authenticated domain lane,
   bounded owned-process backend, source-bound scheduler and evidence
   finalizer and unique coordinator/domain-agent CLI are frozen. Each role
   independently revalidates the final owner signature and admission; each
   domain reserves before listening, while coordinator runtime inputs remain
   lazy until the consumer reservation. Every live activation constant remains
   false until real inputs and the final audit exist.
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
   failure terminal with no retry. The exact runner/launch path is now present
   but activation-closed.
5. **Runner-integrated evidence collection — closed after this audit.** The
   authenticated lanes now return source-signed events and bounded raw log
   bundles. A one-shot finalizer verifies the exact 23-row runner transcript,
   transfers the sole in-memory bootstrap secret, invokes the compiler and
   atomic writer, requires cleanup and secret-scan PASS, and rejects retry.
   It derives the conservative observed clock-offset bound from each
   coordinator-send/domain-observe/coordinator-receive interval instead of
   copying the 300-second policy ceiling into evidence.
   The KAT publishes and reads back 65 temporary owner-only files; no real
   evidence set exists.

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
2. Review the frozen bounded mTLS agent and exact non-production coordinator/
   domain launch entry point against the real placement set. It accepts only the
   existing command enum, perform no shell evaluation, clear ambient proxy and
   credential variables, bind listeners to exact overlay IPs, and confine
   process/fault actions to owned PIDs and run roots.
3. Add an execution-consumption reservation that validates the final owner
   signature and admission receipt before any credential read, listener, remote
   connection, subprocess, or fault action. Failure remains terminal with no
   automatic retry.
4. Collect the three real domain signatures, bounded logs and cleanup receipts
   through the now-frozen event/finalization path; retain time/spend bounds and
   the existing conservative claim ceiling.
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
item 4. The KAT exercises one complete synthetic single-use dispatch and 47
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
fail. It starts nothing and does not close the still-missing live process
backend, socket adapter or persistent evidence-writer findings.

`biocortex_ab_track_b_t22_a1_domain_executor_core_v1.py` closes the fixed-command
dispatch/state/evidence-core portion, but not the live backend. Three synthetic
domain lifecycles produce 23 independently replay-verified private command
receipts; 20 mutations fail, including dispatch-after-failure, timeout, spend,
observation, transition, chain and timing attacks. Any failure after backend
dispatch becomes an absorbing terminal state. Non-synthetic backends remain
hard-disabled, so no process, listener, credential or network action is enabled.

`biocortex_ab_track_b_t22_a1_mtls_transport_v1.py` closes the bounded wire-frame,
TLS-context and one-shot socket-adapter portion. Its KAT performs one
real TLS 1.2/1.3-capable mutual-authentication handshake entirely through
`ssl.MemoryBIO`, round-trips one signed-message envelope and one bounded
ephemeral OpenBao unseal-secret frame, one four-file bounded raw-log bundle,
and rejects 38 framing, route, digest,
certificate, hostname, permission and activation mutations. The contexts bind
the exact plan-selected CA and leaf certificate files, require owner-only files,
verify the exact peer certificate digest after TLS authentication, and keep
transport activation false. The KAT opens no socket, starts no listener and
contacts no host.

`biocortex_ab_track_b_t22_a1_evidence_compiler_v1.py` now closes the in-memory
signed-event and terminal-compilation portion of item 5. It replays all 23
fixed-command receipts, requires each domain terminal to bind its preceding
receipt-chain head, verifies 21 source-domain Ed25519 SSHSIG payloads with the
execution-bound `ssh-keygen`, constructs and independently replays the 21-event
coordinator chain, hashes four bounded logs per domain, binds the exact in-memory
OpenBao secret frame, scans for exact secret leakage, zeroizes the transferred
secret buffer, and emits one schema-valid T22-A1-H value in memory. Fifteen
directed mutations fail. Persistent writing, real input reads and activation
are delegated to a separately gated writer, and the compiler KAT performs no
network, listener, workload or fault action.

`biocortex_ab_track_b_t22_a1_evidence_writer_v1.py` reserves one irreversible
publication attempt, re-verifies all source signatures and both event/terminal
chains, writes 65 owner-only artifacts into a private staging directory,
fsyncs them, atomically renames the closed `evidence-set`, and reads back the
exact manifest/file set. Replay, wrong signature, unsafe directory permission
and injected mid-write failure all fail; a failed reserved attempt retains its
no-retry reservation and removes staging. The execution consumer now binds the
runner result to the manifest, re-hashes all 64 listed artifacts, rejects extra
files/directories/symlinks, cross-binds every source payload and signature hash,
independently replays the 21 coordinator events and then verifies the terminal
evidence. Its total directed negatives increase to
47. Real writer activation remains false.

`biocortex_ab_track_b_t22_a1_exact_evidence_finalizer_v1.py` now closes the
runner-integration gap. It rechecks the exact 23-command order, every receipt
binding and each transcript digest, permits one finalization attempt, retains
the coordinator bootstrap value only through the terminal cleanup scan, then
requires zeroization before atomic publication. Its directed KAT proves early
compiler failure still clears the transferred secret and a second attempt is
rejected. The authenticated-lane integration KAT additionally compiles 21
source-signed events and three log bundles into a 65-file temporary evidence
set. No real private input, OS socket, listener, process, fault or persistent
real evidence output is used.

`biocortex_ab_track_b_t22_a1_exact_launch_binding_v1.py` closes the launch
entry-point gap. The `domain-agent` and `coordinator` subcommands are the only
live role surfaces. Both independently call the owner-signature/admission
verifier; runtime files are unread before that succeeds. A domain re-verifies
its exact readiness SSHSIG using the packet-bound executable/key, creates an
owner-only single-use reservation, and only then constructs its one-accept
listener. The coordinator delegates reservation to the consumer and keeps all
endpoint, readiness, attestation and credential reads inside the injected
runner callback. Six directed failures and ordering doubles pass with zero real
private read, socket, listener, process or fault; committed activation remains
closed.
