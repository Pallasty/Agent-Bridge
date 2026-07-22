# BioCortex Track B T22-A1 three-domain admission

Date: 2026-07-22

Status: **OFFLINE_ADMISSION_TOOLING_COMPLETE_REAL_INPUTS_BLOCKED**

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

1. Choose a third owner physical host, or choose a cloud provider plus exact
   region/zone/instance type and numeric spend limit.
2. Produce fresh private domain attestations from `tb14`, the Mac, and the
   selected third host, each under a distinct dedicated public key.
3. Provide the sorted three-packet digest set, private-overlay endpoint-set
   digest, ACL receipt digest, and fault-target domain.
4. Review the completed execution payload and sign only that source-bound
   payload under `agent-bridge-t22-a1-owner-v1`.
5. Separately decide whether A1-R may create a public Rekor entry. A1-H can run
   and remain honest with A1-R disabled.

No current file is a signing request. The proposal remains deliberately
blocked until these inputs are concrete.

## Frozen identities and offline gate

- domain-attestation schema raw SHA-256:
  `1b261a7ac328de62cbcb51eac9189787e3e5144688ec967311c7341f630b8a2b`;
- admission-contract content SHA-256:
  `88fe5e0198e096fd2a7e93951b10db843166b94b99b0de8471cc411e22a2631e`;
- blocked owner-proposal content SHA-256:
  `62c26d44d929830c04cdacfbdffa8e71183e4e1a951f5cbc4dc95aef1decc05c`.

The offline gate exercises 46 directed negative cases after recomputing
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
