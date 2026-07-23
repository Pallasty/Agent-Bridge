# BioCortex Track B T22-A1 three-domain admission report

Date: 2026-07-22

Status: **BLOCKED_REMOTE_ATTESTATIONS_THIRD_DOMAIN_MODE_ENDPOINT_SET_AND_EXACT_OWNER_DECISION_REQUIRED**

## Outcome

The first T22-A1 unit is implemented as a fail-closed, offline admission layer.
It does not pretend that process multiplicity or host aliases create three
failure domains. `aio2`, `pallasting-ThinkBook-14-G5-IRH`, and `tb14` are
conservatively counted as one domain until fresh private evidence proves
otherwise. The historical Mac record is only a stale second-host candidate,
and no third host is currently named. Mechanically validated domain count is
one of three.

The A1-H contract freezes a realizable non-production target: one etcd voter
and one OpenBao voter on each of three freshly attested physical hosts, followed
by complete loss and recovery of all owned cluster services in one
non-coordinator domain. Its success ceiling excludes host power loss, site
independence, storage/provider durability, external rollback resistance, and
production HA.

A1-R is a separate optional decision. Sigstore Rekor is recorded only as a
candidate for public transparency-log inclusion and fork visibility. No public
entry is authorized or created, and Rekor is not relabelled as monotonic CAS or
rollback prevention.

## Implemented packet

- closed Draft 2020-12 domain-attestation schema with Linux/macOS and
  owner-physical/cloud-VM branches;
- domain-specific SSHSIG key, freshness, private-overlay, pinned-tool, and
  nonclaim bindings;
- frozen three-domain admission contract and conservative claim ceiling;
- blocked owner-decision proposal with all real endpoint, cloud, budget,
  attestation-set, ACL, fault-target, and public-output choices unset; and
- offline preflight plus 82 semantic negative mutations that recompute packet
  self-digests before rejection;
- private three-packet bundle verifier with canonical framing, SSHSIG, public-key
  normalization, four-hour freshness, 300-second clock spread, alias-collapse,
  identity/key uniqueness, endpoint/ACL equality, and exact directory closure;
  its 30 synthetic negatives create no real attestation; and
- closed distributed execution-contract, signed-event, and terminal-evidence
  schemas with 104 synthetic negative cases and no real contract instance or
  evidence item; and
- exact owner-signed per-domain collection-challenge schema, trust-anchor
  binding/generation/verification gate, and 42 synthetic negative cases. It
  performs zero real identity reads and creates zero real attestations; and
- a challenge-gated Linux/macOS physical-domain collector with atomic
  single-use reservation, exact domain-key matching, identity-domain-separated
  in-memory hashing, canonical packet signing/self-verification, private
  terminal receipts, one synthetic success, and 10 synthetic failure paths;
  and
- an exact-set owner countersignature schema and admission gate that verifies
  owner authority before reading the private bundle, reserves one use, reruns
  all three packet/signature/distinctness/freshness checks, and emits only a
  private non-executing admitted-set receipt. Its synthetic full chain and 51
  negative paths read no real bundle or stable identity source; and
- private endpoint, mTLS credential-source, and signed domain-agent protocol
  schemas plus semantic validators with 62 synthetic negative paths. No real
  manifest, credential file, listener, or network connection is used; and
- an offline domain-agent session core with finite coordinator/fault-target/
  survivor lifecycles, paired signature/nonce/sequence/chain verification, 25
  valid synthetic signed transitions, and 15 negative paths. It deliberately
  executes no command and starts no listener or service; and
- a separate zero-network runtime-material preparation challenge, owner
  namespace, generator/verifier gate, and 45 synthetic negative paths. This
  stage binds the owner-countersigned admitted-set receipt and endpoint
  manifest before any
  per-run CA or runtime identity may be generated, but grants no execution,
  network, listener, service, fault, cloud, retry, or spend authority; and
- a single-use runtime-material preparer with one complete synthetic
  cryptographic success and 10 negative paths. It binds and re-hashes the exact
  OpenSSL and `ssh-keygen` executables, generates a per-run P-256 CA, four
  purpose-separated mTLS leaves, and a coordinator Ed25519 key, verifies chain,
  key, EKU, expiry and endpoint SANs, drops the CA key, writes the private
  manifest, and terminally cleans partial material on failure.
- a final execution-contract builder and owner-signature admission gate that
  binds the exact artifact/run roots, set countersignature chain, runtime-
  preparation challenge/signature/terminal, private manifests, tool binaries,
  budget, fault target, three signed runtime-readiness packets and exact
  runner/executor/live-backend/transport/evidence/consumer source-artifact
  set. A complete
  synthetic chain verifies all eleven credential files only after the final
  owner signature; 50 negative paths cover forgery, readiness/source
  substitution, receipt integrity/currentness, replay, wrong signature and
  post-signature key substitution. The owner payload binds only stable packet,
  signature and source-set identities; the time-varying readiness-verification
  receipt is created and bound by the later private admission receipt.
- a completion audit that originally proved real collection had to wait for a
  source-bound execution/evidence chain. Those offline components now exist;
  real activation still waits for authenticated live domain lanes, three
  signed host-local runtime-readiness packets and credential-placement proof. The
  decision packet fails closed on every remaining input.
- a single-use execution consumer that independently rechecks the clean source
  commit, owner signature and admission receipt, reserves before runner
  dispatch, requires exact validated terminal evidence for PASS, and records
  failure without retry. It now also binds the runner manifest, re-hashes the
  closed 64-artifact evidence set, rejects extra paths/symlinks and independently
  replays the coordinator chain before accepting terminal evidence. Its KAT has
  one synthetic success and 47 negative
  paths with zero real network, listener, workload, fault or credential access.
- a private domain-runtime-readiness schema, semantic gate and signed-set
  verifier with three synthetic role/domain successes, one complete
  same-attested-key signed-set success and
  signed-set success and 54 negative paths. It closes the contract for exact
  host-local tools, roots, ports, placed credentials, operator keys,
  coordinator public trust on every domain, coordinator private material only
  on domain-1, and process boundaries, then freshly revalidates
  the attestation bundle and purpose-separated domain signatures. The KAT reads
  zero real host, tool, endpoint or credential input.
- corrected per-domain runtime leaves with both TLS server and client EKUs, as
  required for an etcd peer that both accepts and initiates authenticated peer
  connections. The coordinator leaf remains client-only; schema bytes and
  activation authority are unchanged.
- a pure private workload-plan compiler with three synthetic domain successes
  and 45 negative paths. It freezes exact etcd argv, mTLS OpenBao HCL, cleared
  environment, local paths, deterministic workload state and the per-role
  command allowlist, but deliberately does not start a process or claim that
  the later live local-process backend is active.
- a fixed-command executor core with three synthetic lifecycles, 23 chained
  command receipts and 20 negative paths. It revalidates the exact plan,
  enforces role/state/time/spend boundaries, independently replays each receipt
  chain, binds each domain terminal to its preceding receipt-chain head, and
  makes every post-dispatch failure terminal. Its activation constant remains
  false.
- a live local-process backend with a concrete bounded child-process runtime
  and literal-IP, source-bound mTLS etcd/OpenBao JSON control path. It accepts
  no arbitrary argv or shell, inherits no parent environment, caps service
  logs and HTTP responses, pins the local service leaf, tracks/stops only its
  own two child objects, and exposes bootstrap material only through an
  injected memory-only exchange whose bundle is bound to run/source/execution.
  Three fake-backed non-synthetic lifecycles cover the exact 23-command
  schedule and 28 negatives; committed activation
  remains false, so no real process, socket, credential or fault is used.
- a bounded mTLS framing, context and one-shot socket-adapter core with one real in-memory mutual-TLS
  handshake, one signed-message-frame round trip, one bounded ephemeral secret-
  frame round trip, and 36 negative paths. It binds exact plan-selected
  certificate files, owner-only file modes, hostname and peer-certificate
  identity, including exact rejection of a different same-CA client leaf,
  and adds literal-IP/no-DNS routing, exact source IP, bounded timeout/frame,
  single-accept and failure-close behavior. The adapter is tested through
  in-memory fake sockets while both activation gates remain false; no OS socket,
  listener or external host is used.
- a source-bound global scheduler that compiles all three exact plans,
  dispatches only the 23-command cross-domain schedule, replays all terminal
  receipt chains, and requires cleanup before evidence finalization. One full
  synthetic schedule and nine directed negative paths pass with activation,
  private inputs, sockets, processes and faults all absent/false. Authenticated
  live domain lanes remain the next implementation boundary.
- an in-memory evidence compiler that replays 23 command receipts, verifies 21
  source-domain Ed25519 SSHSIG payloads, independently reconstructs and replays
  the 21-event coordinator hash chain, binds and scans four bounded logs per
  domain plus the exact OpenBao secret frame, zeroizes the transferred secret,
  and returns one schema-valid T22-A1-H value. Fifteen negative paths fail.
- an atomic private evidence writer that re-verifies all 21 source signatures,
  reserves one no-retry publication attempt, writes and fsyncs 65 owner-only
  evidence files through staging, atomically publishes the closed directory and
  revalidates its exact manifest/file set. Four writer-specific negative paths
  reject replay, wrong signatures, unsafe permissions and injected partial
  writes. Real activation and live-runner integration remain absent/false.

Stable host identity and endpoint hashes are intentionally absent from the
public repository. They must be generated into the private artifact root only
after a source-bound challenge exists.

## Verification result

The gate returned `t22_a1_three_domain_preflight_gate pass` with:

- network accessed: false;
- credentials accessed: false;
- external hosts contacted: 0;
- provider APIs accessed: 0;
- services started: 0;
- faults injected: 0;
- spend: USD 0; and
- public transparency entries created: 0.

The domain verifier independently reports
`BLOCKED_EXACT_THREE_PRIVATE_ATTESTATION_BUNDLE_AND_OWNER_COUNTERSIGNATURE_REQUIRED`.
Its `status` path reads neither stable host identity nor a private bundle. A
successful future `verify-set` result remains non-executing. The implemented
exact-set gate must additionally verify the owner countersignature and freshly
reverify the same bundle before producing an admitted-set receipt.

Frozen packet identities:

| Packet | SHA-256 |
|---|---|
| domain-attestation schema raw bytes | `1b261a7ac328de62cbcb51eac9189787e3e5144688ec967311c7341f630b8a2b` |
| domain-collection challenge schema raw bytes | `26d078bb9716cdb443808755ef87c0962f5e4284f94be6f1d168c370a911676d` |
| attestation-set countersignature schema raw bytes | `615959dbd1fbfe65da7830cd5b2bf4efc2ef9a917c94ae9438f820837d121a1c` |
| distributed execution-contract schema raw bytes | `f1738c7b4d4eb7749739a0f73ca599bab2577a40c62681527f78b24a28655426` |
| private endpoint-manifest schema raw bytes | `8741f130384d246077c281a8200a174f92c63fda565c9384ab7d6edc0f723953` |
| runtime credential-manifest schema raw bytes | `fe9b257edae7f93d20e81280e54b20da771c432b65ae5ac906231799ad4c10e2` |
| runtime-preparation challenge schema raw bytes | `1baaddc21592427adad308f2325e4cd6a5f9ba7f1a45db2a5d1d03de734967b3` |
| domain-agent message schema raw bytes | `92d8a9e59e62b56afec200caf0e25517c7bf3322bc24078024d4c52993e9e3ee` |
| distributed event schema raw bytes | `4aaad4ea4006cfbae80fc784837146f3de48bcf9655fd1fe30a237f0d34f6cf5` |
| terminal-evidence schema raw bytes | `f3e6b833b04150376d09f3926dc75601acced248ebd9f9e08d70a86cc51e2a1a` |
| domain runtime-readiness schema raw bytes | `22f34b20906e03f309e688f585d0deac03bcdf16c3eed9ba2ce76f650145b451` |
| admission-contract content | `dc4846831a0e0e11c992c6ea9e68ebb2cd5413d93d253cc9f08748a8fa73763a` |
| blocked owner proposal content | `42f28d09b3e354655ffd582b852d4e4bc3d9d7bf3ced17b6148011023e6ccfca` |

## Advancement boundary

No signature is requested yet. The next concrete inputs are:

1. a third owner physical host, or an exact cloud provider/region/zone/instance
   type and numeric USD limit;
2. an explicit choice of a T22-A1 owner public key (dedicated is preferred; A0
   reuse is never inferred);
3. three owner-signed, source-bound collection challenges;
4. fresh private attestations from the coordinator, Mac, and third host under
   three distinct dedicated keys; and
5. one owner-signed exact-set countersignature and its admitted-set receipt;
6. the exact private-overlay endpoint-set and ACL receipt digests; and
7. the private endpoint-manifest content hash.

After those inputs are admitted, the intermediate payload binds the exact
owner-countersigned set receipt plus the reviewed local cryptographic tool binaries and requests only
zero-network runtime-material preparation under
`agent-bridge-t22-a1-owner-runtime-preparation-v1`. The implemented single-use
preparer may then create the exact per-run mTLS material, credential manifest,
and coordinator runtime signing key. The final execution payload binds those
new hashes and still requires a separate owner signature under
`agent-bridge-t22-a1-owner-v1`. None of these real instances exists or is
accessed yet.

Before any real collection challenge is generated, the new runner scheduler
must be completed with live domain lanes/backend and bound, together with the
executor/transport/evidence sources, into the final execution contract.
Otherwise a later source change would invalidate the source-bound host
attestations. After that source set is frozen and the remaining
real inputs exist, the implemented builder can generate one source-bound final
execution-contract instance and admit it only after the exact owner signature.
Public Rekor submission remains a separate explicit choice.

The physical collector is implemented but remains unreachable in the current
state because no T22-A1 owner trust anchor or signed challenge exists. Its KAT
injects synthetic identity bytes and proves invalid authority, key, host,
output, and replay paths do not call the identity reader. Cloud collection
stays closed until a provider-specific identity verifier exists.

Full design and operational conditions are recorded in
`docs/design/BIOCORTEX_TRACK_B_T22_A1_THREE_DOMAIN_ADMISSION_2026_07_22.md`.
