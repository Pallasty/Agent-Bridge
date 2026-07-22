# BioCortex Track B T22-A1 three-domain admission

Date: 2026-07-22

Status: **OFFLINE_FINAL_EXECUTION_ADMISSION_COMPLETE_RUNNER_AND_HOST_READINESS_FAIL_CLOSED**

Live execution: **NOT AUTHORIZED AND NOT ATTEMPTED**

## Decision

T22-A1 is split into two independently admitted evidence tracks:

1. **T22-A1-H** may eventually prove three distinct physical-host placements
   and recovery after every owned cluster service on one host is stopped. It
   cannot prove host power loss, site independence, storage durability,
   provider durability, or production HA.
2. **T22-A1-R** may later publish a non-secret checkpoint into an external
   transparency log. That is a separate irreversible-output decision. Even a
   successful inclusion proof establishes public inclusion and fork visibility,
   not monotonic compare-and-swap, rollback prevention, or satisfaction of the
   S20 external-checkpoint contract.

The current owner instruction authorizes this offline planning and admission
implementation. It does not supply or authorize remote endpoints, credential
sources, a third host, a cloud provider, a numeric cloud budget, overlay
changes, or public transparency-log output. All such actions remain blocked.

## Asset audit

The current coordinator is `tb14`. Historical repository evidence also uses
the logical names `aio2` and `pallasting-ThinkBook-14-G5-IRH`. Naming alone is
not physical identity evidence, so the admission contract conservatively puts
all three labels in one equivalence class until fresh private attestations prove
otherwise. They cannot be counted as multiple domains.

The Mac host `maxiaodeMac-Pro.local` is a plausible second physical-host
candidate, but its cited evidence is dated 2026-06-22 and is not a current
T22-A1 attestation. No third host is named. The present mechanically admissible
count is therefore one; the known candidate upper bound is two.

Stable machine, hardware, boot, provider-instance, and endpoint digests are not
committed to the public repository. They belong only in short-lived,
challenge-bound, independently signed domain packets under the private
artifact root. The committed schema defines their shape without publishing
their values.

## T22-A1-H claim ceiling

The exact maximum success claim is:

`THREE_DISTINCT_PHYSICAL_HOST_PLACEMENT_AND_ONE_HOST_SCOPED_OWNED_SERVICE_SET_LOSS_RECOVERY_NONPRODUCTION`

The experiment places one etcd voter and one OpenBao voter in each domain. It
must first observe three voters and the T22-A0 authorize/consume, replay-denial,
and Transit-signature invariants. It then stops every owned cluster process in
one observed non-coordinator domain, verifies that the surviving two domains
retain quorum and the pre-fault state, restarts the stopped processes, and
observes rejoin.

Only owned process stop, timeout-bounded kill, and restart are allowed. Host
reboot, power-off, provider instance stop, block-device mutation, and
host-global firewall, route, `iptables`, or `tc` changes are forbidden. Thus
the placement is across physical hosts, while the injected fault remains a
host-scoped workload disappearance rather than a power or hardware fault.

## Domain attestation chain

Advancement requires exactly three current packets conforming to
`agent_bridge.biocortex.track_b.t22_a1.domain_attestation.v1`:

- three distinct machine-identity digests;
- three distinct hardware-identity digests;
- three distinct hostnames after alias collapse;
- three distinct Ed25519 domain-signing public keys whose private keys never
  leave their hosts;
- boot-bound freshness and a maximum age of four hours;
- a provider-signed instance identity binding if a cloud VM is used;
- the exact private-overlay endpoint-set digest and ACL receipt digest;
- per-domain pinned-tool, private-data-root, and port-set bindings; and
- an owner countersignature over the sorted exact three-packet digest set.

A candidate's self-reported distinctness is not authoritative. The coordinator
must recompute cross-packet uniqueness, freshness, source binding, signatures,
and endpoint/ACL equality before any future execution payload can be generated.

The offline verifier now implements that recomputation. It admits only a
private `0700` directory containing exactly `domain-{1,2,3}.{json,pub}` and
`domain-{1,2,3}.json.sig`. Packets must use canonical one-line JSON plus one LF,
their domain-separated self digests must match, and each complete packet must
verify under SSHSIG namespace `agent-bridge-t22-a1-domain-v1` and its own
domain identity. Public keys are normalized to their algorithm/key material
before hashing, so comments cannot change identity. The three packet times may
span at most 300 seconds.

Successful set verification emits only packet, signature, public-key, endpoint,
and ACL digests. It deliberately returns
`THREE_DOMAIN_INPUT_SET_COMPLETE_PENDING_OWNER_COUNTERSIGNATURE_NON_EXECUTING`;
it is not an execution permit. Real packet collection remains absent until an
exact owner-signed collection challenge can bind the selected third domain and
private artifact root. Thus the current verifier can be fully tested without
reading a real stable host identifier.

### Exact-set owner countersignature

The pending state now has a concrete, non-executing successor. A closed owner
countersignature packet binds the source commit, current proposal and admission
contract, attestation schema, exact set digest, all three packet/signature/key
bindings, endpoint/ACL digests, distinctness results, earliest attestation
expiry, and private admitted-receipt output path. Its distinct SSHSIG namespace
is `agent-bridge-t22-a1-owner-attestation-set-v1` and its lifetime is at most
one hour and never later than the earliest domain-attestation expiry.

Admission verifies the owner signature before reading the private bundle,
atomically reserves the signed challenge for one use, then independently
re-runs canonical framing, source/freshness, three domain signatures,
identity/key/hostname/alias uniqueness, endpoint/ACL equality and clock-spread
checks. The signed stable set fields must equal the freshly recomputed result.
Only then is a private, content-addressed
`THREE_DOMAIN_INPUT_SET_OWNER_COUNTERSIGNED_ADMITTED_NON_EXECUTING` receipt
written. A failure is terminal with no automatic retry. The receipt contains
no raw identity, endpoint or credential value and grants no execution,
network, service, fault, budget, availability or production authority.

The runtime-preparation generator no longer accepts a manually supplied bare
attestation-set digest. Its CLI parses a current admitted-set receipt and binds
both the set digest and receipt digest into the separately signed preparation
challenge.

### Owner-signed collection challenge

The repository now defines a separate, exact, one-domain collection challenge
and verifier. It prevents the future collector from becoming an ambient host
inventory utility:

- a T22-A1 owner public key must first be bound to the current proposal as a
  committed trust anchor; T22-A0 key reuse is not inferred;
- every challenge binds one domain ID, expected hostname and complete logical
  alias class, OS/architecture, domain signing key, source commit, proposal,
  admission contract, attestation schema, endpoint/ACL digests, tool/data/port
  digests, and exact private artifact directory;
- challenge lifetime is at most one hour and each challenge digest permits at
  most one future collection;
- the distinct SSHSIG namespace is
  `agent-bridge-t22-a1-owner-collection-v1`;
- only hostname, OS/kernel/architecture, machine identity, hardware identity,
  and boot identity may be read after signature verification; raw values may
  only be hashed in memory and never persisted; and
- network access, ambient credential discovery, overlay changes, services,
  faults, cloud APIs without a frozen provider verifier, spend, production
  data, execution authority, and availability claims remain forbidden.

The current gate can bind an explicitly confirmed public key, generate a
canonical private challenge, and verify its detached owner signature. Its
`status` and `verify` paths perform zero stable-identity reads. Verification
returns `OWNER_SIGNED_DOMAIN_COLLECTION_CHALLENGE_VERIFIED_NO_COLLECTION_PERFORMED`;
the actual identity collector remains a separate next unit and must reuse this
exact verification path before its first read.

Cloud challenges are deliberately rejected with
`E_CLOUD_PROVIDER_IDENTITY_VERIFIER_NOT_FROZEN` until the owner selects a
provider and that provider's signed instance-identity verifier is implemented.
This prevents a generic self-report from being relabelled as provider proof.

### Physical-domain collector

The challenge-gated physical collector is now implemented for Linux and macOS.
Its irreversible ordering is:

1. verify the clean exact source commit, committed owner trust anchor, canonical
   challenge, challenge self-digest, lifetime, and detached owner signature;
2. validate private artifact scope and bound domain public key;
3. atomically reserve the challenge digest for one use, with automatic retry
   disabled even if collection later fails;
4. access the exact private domain-signing key and prove it matches the bound
   public key;
5. observe and match hostname, OS, architecture, and kernel; only then
6. read machine, hardware, and boot identity sources, domain-separate and hash
   them in memory, erase the raw identity object, build the canonical domain
   packet, sign it, verify the new signature, and write a terminal receipt.

Linux sources are the local machine-id, DMI/device-tree hardware identity, and
kernel boot ID files. macOS sources are local `ioreg` platform UUID/serial and
`kern.bootsessionuuid`. The collector executes no network command, reads no
ambient credential, and supports only `OWNER_PHYSICAL`; `CLOUD_VM` remains
closed at the challenge verifier.

Private output is exactly three `0600` files under the challenge-bound `0700`
domain directory: canonical attestation, canonical Ed25519 public key, and
detached SSHSIG. Challenge reservation and terminal receipts live below the
same private artifact root. Failed reserved challenges are terminal and cannot
be silently retried.

## Future execution and evidence contracts

Three additional closed Draft 2020-12 schemas now freeze the shape of the
future authorized run without creating a runnable instance:

1. The distributed execution-contract schema requires an exact source commit,
   a verified and unexpired detached owner signature, one-use authorization,
   a maximum four-hour runtime, all three signed attestation bindings, and one
   of two explicit budget branches: three owner hosts at zero spend, or a named
   provider/region/zone/instance type with a positive bounded USD ceiling.
2. The event schema requires every coordinator-chain event to carry the digest
   and verified detached-signature binding of its source-domain evidence. It
   prohibits raw endpoints and secret material and distinguishes genesis from
   non-genesis chain links.
3. The terminal-evidence schema requires exactly three ordered domain rows,
   hashed per-domain process evidence and cleanup receipts, all required fault
   observations, a verified coordinator chain, all source-domain signatures,
   bounded clock/runtime/spend observations, complete process/port cleanup,
   and an exact-value secret scan.

`PASS_T22_A1_THREE_HOST_OWNED_SERVICE_SET_LOSS_RECOVERY` is structurally
unavailable if any required domain, signature, recovery, event-chain, cleanup,
or secret-scan flag is false. A failure receipt must carry an `E_*` failure
code and cannot earn the admissible claim. Both PASS and FAIL receipts keep
power, site, storage, provider, anti-rollback, and production claims false.

These are schemas only. No distributed execution-contract instance, owner
authorization, real distributed event, or terminal evidence item exists yet.

## Private network boundary

The contract selects an owner-managed private overlay and forbids public
listeners. The runner may consume an owner-bound peer-endpoint set but cannot
provision, join, or reconfigure the overlay and cannot inspect ambient overlay
credentials.

If a new ephemeral node is needed, the preferred operational pattern is an
owner-created one-off, ephemeral, tagged Tailscale auth key with a restrictive
ACL. Tailscale documents that auth keys authenticate a device as their creator
or tag identity, warns against reusable keys, and recommends ephemeral/tagged
keys for short-lived workloads. The key must be supplied outside shell history,
must never enter a packet or log, and must be revoked or logged out after
cleanup. See the official [auth-key](https://tailscale.com/docs/features/access-control/auth-keys)
and [secure handling](https://tailscale.com/docs/features/access-control/auth-keys/how-to/secure-auth-keys)
documentation. Existing owner-authenticated hosts need no new key merely for
this experiment; their exact endpoint and ACL receipts still require owner
binding.

### Private runtime endpoint, credential, and agent protocol

The cross-host control plane is now frozen as three additional private
contracts. No instance exists yet:

1. The endpoint manifest contains exactly three ordered domain rows with one
   literal private-overlay IP and the agent/etcd/OpenBao ports for each domain.
   Public, loopback, link-local, multicast, unspecified, duplicate, DNS-based,
   and per-host port-colliding forms are rejected. Raw instances are private
   and forbidden from the repository and public receipts.
2. The runtime credential manifest binds a private per-run CA, one coordinator
   client certificate, three distinct domain server certificates and
   private-key paths, plus the coordinator runtime Ed25519 public/private key
   paths and exact public-key digest. Every path must be absolute and outside the repository;
   certificate, SPKI, and path reuse are rejected. Keys must be `0600`, CA
   private-key paths are absent, client/server EKUs are exact, and every
   certificate must remain valid through execution expiry. Credential files
   are read only after the final owner execution signature verifies.
3. The domain-agent protocol carries only canonical, maximum-60-second,
   nonce/sequence/previous-hash-bound messages over mTLS. Requests are signed
   by the exact coordinator runtime key and responses by the domain operator
   key under distinct SSHSIG namespaces. Commands come from a fixed lifecycle
   enum; raw endpoints, credentials, secrets, arbitrary commands/shell text,
   and execution/production claims are structurally forbidden. A stop-service
   command cannot target coordinator `domain-1`.

The distributed execution contract binds the raw SHA-256 of all
three schemas, the exact private endpoint- and credential-manifest content
hashes, and the coordinator runtime public key. The runner may not discover
ambient credentials, resolve DNS, provision the overlay, or listen on any
address other than its exact manifest-bound overlay IP.

The credential binding creates a deliberate two-stage authorization sequence.
The final execution contract cannot be generated until the credential-manifest
hash and coordinator runtime public key exist, while those sensitive materials
must not be generated merely from ambient intent. A separate closed runtime-
preparation challenge now resolves that dependency without granting execution:

1. after the exact three-domain attestation set and private endpoint manifest
   are admitted, generate a canonical challenge that binds their hashes, the
   source commit, current proposal and admission contract, run ID, private
   paths, planned execution expiry, every runtime schema, and the exact raw
   SHA-256 and absolute path of the local OpenSSL and `ssh-keygen` executables;
2. the owner signs that complete packet under the distinct SSHSIG namespace
   `agent-bridge-t22-a1-owner-runtime-preparation-v1` for at most one hour;
3. only a later material generator may consume the verified one-use challenge
   to use local CSPRNG, create a per-run CA, one coordinator client identity,
   three domain server identities, and a coordinator runtime Ed25519 identity,
   validate them, and write the private credential manifest; and
4. that preparation still authorizes no network connection, listener, service,
   workload, fault, cloud API, spend, production data, or retry. The resulting
   hashes are inputs to a separately reviewed final execution contract and its
   separate owner signature.

The challenge generator/verifier and the single-use material preparer are now
implemented. Authorization `status`, `generate`, and `verify` paths do not read
the private endpoint-manifest instance or any credential file and do not
generate material. The preparer first verifies the exact owner signature,
atomically reserves the challenge, re-hashes both signed tool executables, and
only then reads the exact canonical private endpoint manifest.

The preparer creates a P-256 per-run CA, a client-only coordinator certificate,
three server-only domain certificates whose SANs bind the exact overlay IPs,
and a coordinator Ed25519 runtime key. It verifies the CA/leaf chains, every
certificate/private-key match, EKU, expiry margin, endpoint SAN, permissions,
and all private-runtime manifest invariants before atomically publishing the
credentials directory and manifest. The CA signing key, CSRs, extension files,
and serial file are not retained. A failure after reservation is terminal,
destroys the exact partial staging/output tree when possible, and never enables
automatic retry. A successful preparation still cannot connect, listen, start
a service, execute a workload, inject a fault, spend, or claim availability.

The offline agent-session core now implements the protocol's second semantic
layer without opening a listener. It verifies canonical request/response files,
coordinator and domain detached Ed25519 signatures, declared signing-key
digests, exact run/source/execution/endpoint/credential bindings, 60-second
freshness, paired nonce/command/payload, monotonically increasing sequences,
and the complete prior-message chain. It rejects coordinator/domain key reuse.

Each domain has a finite lifecycle:

- `domain-1`: preflight → start/query → authorize-consume → pre-fault Transit
  signature → survivor/state verification → post-fault signature verification
  → cleanup → terminal;
- fault target (`domain-2` or `domain-3`): preflight → start/query → stop all
  owned service members → restart → rejoin verification → cleanup → terminal;
- other survivor: preflight → start/query → survivor/state verification →
  cleanup → terminal.

A signed failure response moves the session directly to a no-retry terminal
state. The core emits transition receipts but explicitly executes zero
commands, starts zero listeners/services, and injects zero faults. Completion
audit showed that deferring the network adapter and command executors until
after real source-bound attestations would invalidate those attestations when
their implementation changes the commit. They must instead be frozen before
the first real collection challenge.

### Final execution authorization admission

The final execution layer is now more than a schema. Its offline builder
revalidates the admitted owner-countersigned three-domain set, the original set
signature, all three fresh domain signatures, the owner-signed runtime-
preparation challenge and terminal receipt, the endpoint manifest, credential
manifest, budget branch, fault target and evidence schemas. It emits one exact
content-addressed execution contract under the private artifact root without
reading any credential file.

That contract also binds the artifact root and run-evidence root, preventing a
single signature from being replayed under a caller-selected directory. It
binds the preparation challenge/signature/terminal hashes and the exact
OpenSSL/`ssh-keygen` paths and binary hashes used for post-signature credential
verification.

Admission verifies the final owner SSHSIG under
`agent-bridge-t22-a1-owner-v1` before reading any private evidence or credential
file, then atomically reserves the contract for one admission. Only afterward
does it rebuild the contract from the private evidence and verify the CA,
certificate chains, certificate/private-key matches, EKUs, expiry, overlay-IP
SANs, coordinator runtime Ed25519 pair, file set and permissions. Success emits
a private one-execution admission receipt; failure is terminal and cannot
retry. The admission step itself opens no socket, starts no listener or
service, injects no fault and spends nothing. The source-bound cross-host
runner remains a required pre-sign successor. Its single-use consumer core is
now implemented: it independently checks the clean source commit, exact final
owner signature and private admission receipt, atomically reserves one
execution, then dispatches an injected runner. A PASS is accepted only with an
exact schema-valid, digest-valid terminal-evidence file bound back to the
execution contract. Both final admission and the consumer are additionally
blocked by a source constant that remains false until the runner, three host
readiness packets and credential-placement proof are implemented. Failure is
terminal and cannot retry. The consumer itself
opens no socket and starts no listener, workload, or service process.

### Pre-sign execution-readiness correction

The execution-readiness audit found that the repository still lacks a
source-bound cross-host runner, three host-local runtime-readiness packets,
credential-placement proof and a real evidence builder. The single-use
admission consumer identified by the audit has since been implemented. The
central material manifest cannot truthfully prove that the matching
private key and certificate have been placed on each remote domain at an exact
private path. These are execution blockers, not documentation niceties.

The admission contract now records the runner, readiness contract and placement
proof as absent. The blocked proposal requires the exact readiness packet and
signature sets, credential-placement mode, and runner/executor source hash set.
See the [execution-readiness audit](../reports/goal-c-u/2026-07-22-biocortex-track-b-t22-a1-execution-readiness-audit.md).

## Third-domain decision

The preferred zero-spend path is a third owner-controlled physical host. If no
such host exists, the owner must explicitly select a cloud VM and bind:

- provider, account/project identity, region, zone, and instance type;
- provider-verifiable instance identity evidence;
- maximum authorized spend in USD;
- creation and deletion authority boundaries;
- private-overlay enrollment method and ACL;
- exact runtime deadline; and
- cleanup/deletion receipt requirements.

The implementation does not choose a provider or infer ambient cloud
credentials. A cloud VM cannot be created from the current proposal because
the provider and budget fields are null.

## T22-A1-R transparency boundary

The current candidate is Sigstore Rekor `hashedrekord`. Rekor's official CLI
documentation states that upload sends the public key, signature, and artifact
or SHA hash to the public transparency log and returns an entry URL suitable
for inclusion-proof verification. This is an irreversible external output and
needs its own exact owner decision before any upload. See the official
[Rekor CLI documentation](https://docs.sigstore.dev/logging/cli/).

An A1-R receipt would bind the A1-H terminal event-chain head, prior checkpoint
head, signing key, Rekor entry UUID, inclusion proof, signed tree head, and
consistency evidence. It may claim public inclusion and make a later fork
visible. It may not claim a linearizable conditional update, prevent a fork,
or satisfy the stronger S20 monotonic-CAS requirement.

## Exact owner inputs still required

1. Freeze and test the source-bound cross-host runner, domain executor,
   single-use admission consumer and real evidence builder.
2. Choose a third owner physical host, or choose a cloud provider plus exact
   region/zone/instance type and numeric spend limit.
3. Choose a dedicated T22-A1 owner public key or explicitly approve reuse of
   the existing T22-A0 key, then bind it to the current proposal.
4. Generate and sign one exact collection challenge for each selected domain.
5. Produce fresh private domain attestations from `tb14`, the Mac, and the
   selected third host, each under a distinct dedicated public key.
6. Generate and sign the exact set countersignature under
   `agent-bridge-t22-a1-owner-attestation-set-v1`, then admit the freshly
   reverified bundle once.
7. Provide the admitted-set receipt, private-overlay endpoint-set
   digest, ACL receipt digest, and fault-target domain.
8. Produce and privately validate the exact endpoint manifest.
9. Generate and sign the exact zero-network runtime-preparation challenge under
   `agent-bridge-t22-a1-owner-runtime-preparation-v1`, including the reviewed
   OpenSSL and `ssh-keygen` paths and raw binary hashes.
10. Consume it once to generate the per-run mTLS CA/certificates, credential
   manifest, and coordinator runtime signing key; review only their content
   hashes without publishing raw paths, endpoints, or private material.
11. Complete the explicitly approved initial credential placement and collect
    three signed host-local runtime-readiness packets binding the exact tools,
    roots, ports and placed credential hashes.
12. Review the completed execution payload and sign only that source-bound
   payload under `agent-bridge-t22-a1-owner-v1`.
13. Separately decide whether A1-R may create a public Rekor entry. A1-H can run
   and remain honest with A1-R disabled.

No current file is a signing request. The proposal remains deliberately
blocked until these inputs are concrete.

## Frozen identities and offline gate

- domain-attestation schema raw SHA-256:
  `1b261a7ac328de62cbcb51eac9189787e3e5144688ec967311c7341f630b8a2b`;
- domain-collection challenge schema raw SHA-256:
  `26d078bb9716cdb443808755ef87c0962f5e4284f94be6f1d168c370a911676d`;
- attestation-set countersignature schema raw SHA-256:
  `615959dbd1fbfe65da7830cd5b2bf4efc2ef9a917c94ae9438f820837d121a1c`;
- distributed execution-contract schema raw SHA-256:
  `2ef4bcae59c8eb3ee65611e592e816eaee80d9b977d6c9c4c37c14c3eb4f73fc`;
- private endpoint-manifest schema raw SHA-256:
  `8741f130384d246077c281a8200a174f92c63fda565c9384ab7d6edc0f723953`;
- runtime credential-manifest schema raw SHA-256:
  `fe9b257edae7f93d20e81280e54b20da771c432b65ae5ac906231799ad4c10e2`;
- runtime-preparation challenge schema raw SHA-256:
  `1baaddc21592427adad308f2325e4cd6a5f9ba7f1a45db2a5d1d03de734967b3`;
- domain-agent message schema raw SHA-256:
  `92d8a9e59e62b56afec200caf0e25517c7bf3322bc24078024d4c52993e9e3ee`;
- distributed event schema raw SHA-256:
  `4aaad4ea4006cfbae80fc784837146f3de48bcf9655fd1fe30a237f0d34f6cf5`;
- terminal-evidence schema raw SHA-256:
  `f3e6b833b04150376d09f3926dc75601acced248ebd9f9e08d70a86cc51e2a1a`;
- admission-contract content SHA-256:
  `a826a537bd4c7cb50bd11bfee16898279b0f69d47e8b127db437fe40a0f2c50e`;
- blocked owner-proposal content SHA-256:
  `86c2dfb19a196290af835f84a00abd2c4e12a11de1bf4007fc190629beb9ca57`.

The offline admission gate exercises 81 directed negative cases after recomputing
candidate self-digests, so semantic escalation cannot pass merely by updating
the hash. It constructs no network socket, reads no stable host identifier or
credential, contacts no external host or provider, starts no service, spends
nothing, injects no fault, and creates no transparency-log entry.

The private-bundle verifier adds 30 synthetic directed negatives over packet
shape, self digest, source/freshness, provider branch, private-key and network
claims, cross-domain identity/key/alias uniqueness, endpoint/ACL equality,
clock spread, signature mismatch, and exact bundle contents. Its KAT generates
only ephemeral synthetic keys and removes them; it reads zero real host
identifiers and produces zero real attestations.

The execution/event/terminal schema KAT adds 96 directed negatives. It rejects
multi-use or overlong authority, incomplete/domain-colliding topology, public
or credential-bearing network forms, coordinator-targeted faults, broken
source signatures and event links, incomplete recovery/cleanup, leaked-secret
states, overspend, and inflated claims. All instances are synthetic; it starts
zero services, contacts zero hosts, reads zero real identifiers or credentials,
and injects zero faults.

The private runtime KAT adds 69 directed negatives over endpoint privacy and
uniqueness, port separation, credential path scope and permissions,
certificate/SPKI uniqueness, issuer/EKU/expiry bindings, mTLS requirements,
message direction/signers/namespaces, freshness, replay links, fault targeting,
and shell/secret/claim escalation. It reads zero real manifest instances or
credential files, opens zero sockets/listeners, and contacts zero hosts.

The agent-session KAT validates 25 signed request/response transitions spanning
all three role paths and adds 15 directed negatives over lifecycle order,
coordinator/domain signature mismatch, key reuse, replay, terminal retry,
request/response nonce-command-payload pairing, sequence and chain links,
declared signer binding, domain binding, and message expiry. All keys and
messages are synthetic; no real keys, credentials, network, commands, services,
or faults are used.

The exact-set countersignature KAT adds one complete synthetic three-key,
three-packet owner-countersigned admission and 51 directed negatives over
envelope closure, owner/signature/namespace, source and contract identities,
lifetime, private output, bundle-before-owner ordering, one-use replay,
reverified-set equality, admitted-receipt integrity/currentness, distinctness,
side effects and claim ceilings. It reads zero real private bundles or stable
identity sources and performs no credential, network, service or fault action.

The runtime-preparation authorization KAT adds 45 directed negatives over the
source/proposal/contract, owner-admitted attestation set, endpoint-manifest and schema
bindings; private path closure; lifetime and planned-execution windows;
one-use/zero-spend authority; allowed/forbidden actions; claim ceilings;
canonical framing; owner signature and namespace; and private output
permissions. Its positive verification reads zero real endpoint-manifest or
credential instances, creates no runtime material, and performs no network,
listener, service, fault, or spend action.

The runtime-material preparer KAT adds one full synthetic cryptographic success
and 10 directed negative paths. It generates and validates five synthetic
certificates and five retained private keys in a temporary private root, proves
the CA signing key is absent from the published set, and covers atomic replay
denial, wrong/expired owner authority, signature namespace and source mismatch,
signed tool-binary mismatch, endpoint-content mismatch, unsafe permissions,
generation completion after authority expiry, and cleanup after injected
generation failure. It reads zero real endpoint or
credential instances and performs no network, listener, service, fault, or
spend action.

The final execution-authorization KAT drives one complete synthetic chain from
three independently signed domain packets through set countersignature,
runtime-material preparation, final owner execution signature and
post-signature verification of eleven credential files. Its 38 directed negatives
cover semantic contract escalation, evidence/tool cross-binding forgery, wrong
owner signature, execution-admission receipt tampering/currentness, both
output-present and reservation-backed replay, and a post-signature private-key
substitution. It reads zero real private evidence or
credential files and performs no network, listener, service, fault or spend
action.

The execution-consumer KAT adds one synthetic single-use dispatch success and
42 directed negatives over the closed activation gate, caller-selected source commits, owner-signature/read
ordering, admission replay, runner failure and expiry, runner-result closure,
terminal-evidence schema/digest/cross-bindings, cleanup, budget and claim
boundaries. It reads no real execution/admission/credential instance, opens no
network or listener, starts no workload process and injects no fault.

The collection-challenge KAT adds 42 directed negatives over schema and
domain-separated digest binding, source/proposal/contract identities, alias
closure, owner key parsing and trust binding, lifetime, signature and namespace,
cloud-verifier admission, private output paths and permissions, allowed reads,
forbidden actions, and claim ceilings. Its positive path still reads zero real
host identifiers and creates zero real attestations.

The physical collector KAT adds one complete synthetic collection and 10
negative paths covering wrong/expired owner authority, source mismatch,
public/private domain-key mismatch, unsafe key permissions, host mismatch,
pre-existing output, one-use replay, and an injected read failure. All identity
values and signing keys are synthetic and ephemeral. It invokes the injected
identity reader twice (one success and one deliberate failure), reads zero real
host identifiers, contacts no host, starts no service, and creates no real
attestation.
