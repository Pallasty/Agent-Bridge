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
- offline preflight plus 67 semantic negative mutations that recompute packet
  self-digests before rejection;
- private three-packet bundle verifier with canonical framing, SSHSIG, public-key
  normalization, four-hour freshness, 300-second clock spread, alias-collapse,
  identity/key uniqueness, endpoint/ACL equality, and exact directory closure;
  its 30 synthetic negatives create no real attestation; and
- closed distributed execution-contract, signed-event, and terminal-evidence
  schemas with 83 synthetic negative cases and no real contract instance or
  evidence item; and
- exact owner-signed per-domain collection-challenge schema, trust-anchor
  binding/generation/verification gate, and 42 synthetic negative cases. It
  performs zero real identity reads and creates zero real attestations; and
- a challenge-gated Linux/macOS physical-domain collector with atomic
  single-use reservation, exact domain-key matching, identity-domain-separated
  in-memory hashing, canonical packet signing/self-verification, private
  terminal receipts, one synthetic success, and 10 synthetic failure paths;
  and
- private endpoint, mTLS credential-source, and signed domain-agent protocol
  schemas plus semantic validators with 62 synthetic negative paths. No real
  manifest, credential file, listener, or network connection is used; and
- an offline domain-agent session core with finite coordinator/fault-target/
  survivor lifecycles, paired signature/nonce/sequence/chain verification, 25
  valid synthetic signed transitions, and 15 negative paths. It deliberately
  executes no command and starts no listener or service; and
- a separate zero-network runtime-material preparation challenge, owner
  namespace, generator/verifier gate, and 42 synthetic negative paths. This
  stage binds the admitted attestation set and endpoint manifest before any
  per-run CA or runtime identity may be generated, but grants no execution,
  network, listener, service, fault, cloud, retry, or spend authority.

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
successful future `verify-set` result will still be non-executing until the
owner countersigns the exact set.

Frozen packet identities:

| Packet | SHA-256 |
|---|---|
| domain-attestation schema raw bytes | `1b261a7ac328de62cbcb51eac9189787e3e5144688ec967311c7341f630b8a2b` |
| domain-collection challenge schema raw bytes | `26d078bb9716cdb443808755ef87c0962f5e4284f94be6f1d168c370a911676d` |
| distributed execution-contract schema raw bytes | `056f7e555c6e04ac5a9ba1ddc3817771635edf3a0321921b69fa8924d803428a` |
| private endpoint-manifest schema raw bytes | `8741f130384d246077c281a8200a174f92c63fda565c9384ab7d6edc0f723953` |
| runtime credential-manifest schema raw bytes | `b729e53c775af8350badd72660b8adb36e97ca717228e129411c2b5c4ebb3d8a` |
| runtime-preparation challenge schema raw bytes | `8d736b86cf7ead0c342f37a5b58fac9f0bb4fb410b0b3ea91c801aa636567a1a` |
| domain-agent message schema raw bytes | `92d8a9e59e62b56afec200caf0e25517c7bf3322bc24078024d4c52993e9e3ee` |
| distributed event schema raw bytes | `4aaad4ea4006cfbae80fc784837146f3de48bcf9655fd1fe30a237f0d34f6cf5` |
| terminal-evidence schema raw bytes | `f3e6b833b04150376d09f3926dc75601acced248ebd9f9e08d70a86cc51e2a1a` |
| admission-contract content | `5a2d2fcb9d6bda78ab16661d9abcf85b3953bccc5d7796ea9ba15d5b782cf05b` |
| blocked owner proposal content | `4da58d0e705b0b3e8e96d70922fa1e8f0f3ed20133f9d78a03a733cbf1e02460` |

## Advancement boundary

No signature is requested yet. The next concrete inputs are:

1. a third owner physical host, or an exact cloud provider/region/zone/instance
   type and numeric USD limit;
2. an explicit choice of a T22-A1 owner public key (dedicated is preferred; A0
   reuse is never inferred);
3. three owner-signed, source-bound collection challenges;
4. fresh private attestations from the coordinator, Mac, and third host under
   three distinct dedicated keys; and
5. the exact private-overlay endpoint-set and ACL receipt digests; and
6. the private endpoint-manifest content hash.

After those inputs are admitted, the new intermediate payload binds their exact
hashes and requests only zero-network runtime-material preparation under
`agent-bridge-t22-a1-owner-runtime-preparation-v1`. A later single-use material
generator may then create the exact per-run mTLS material, credential manifest,
and coordinator runtime signing key. The final execution payload binds those
new hashes and still requires a separate owner signature under
`agent-bridge-t22-a1-owner-v1`. None of these real instances exists or is
accessed yet.

After those exist, a separate unit may implement the cross-host runner against
the now-frozen schemas, generate one source-bound execution-contract instance,
and ask the owner to sign it. Public Rekor submission remains a separate
explicit choice.

The physical collector is implemented but remains unreachable in the current
state because no T22-A1 owner trust anchor or signed challenge exists. Its KAT
injects synthetic identity bytes and proves invalid authority, key, host,
output, and replay paths do not call the identity reader. Cloud collection
stays closed until a provider-specific identity verifier exists.

Full design and operational conditions are recorded in
`docs/design/BIOCORTEX_TRACK_B_T22_A1_THREE_DOMAIN_ADMISSION_2026_07_22.md`.
