# BioCortex Track B T22-A0 real-lab preflight and owner signing request

## Outcome

T22-A0 crossed the real-process boundary once and failed closed before fault
injection. Hash-pinned etcd 3.7.0, OpenBao 2.6.0, and Toxiproxy 2.12.0 were
acquired; three etcd processes formed one local cluster; then the runner's
strict `succeeded is False` check rejected the replay response. Official API
semantics and protobuf-JSON default-field behavior make an omitted false scalar
the leading diagnosis, but the original runner did not persist the raw
response. The authorization was irreversibly consumed, all three
owned processes stopped without SIGKILL, all 14 loopback ports were released,
and no OpenBao process, Toxiproxy process, fault, credential, host-global
network mutation, spend, or production claim occurred. A source-bound rerun
requires a fresh owner signature after the response verifier correction lands.

## Proposed first real execution

The first authorization is deliberately smaller than production: three local
etcd processes, three local OpenBao Raft processes, and one loopback Toxiproxy
process, with generated lab-only workload and a zero-dollar ceiling. It may
test one owned process crash, one loopback transport disconnect, CAS/replay
behavior, and service restart. It cannot prove independent host
failure, production HA, external anti-rollback, provider behavior, or production
admissibility.

After authorization, only hash-pinned public release artifacts may be acquired.
OpenBao initialization may generate ephemeral unseal material and a root token,
but they must remain memory-only, must never enter logs or receipts, and must be
discarded when the runner exits after cleanup and exact-value leak scanning. No
system package installation, sudo, host-global
`iptables`/`tc`, pre-existing or ambient credential discovery, cloud API,
production data, customer data, or external output is authorized by this
proposal.

The public-tool supply chain is now frozen in
`docs/design/fixtures/biocortex-ab-track-b-t22-a0-public-tool-pins-v1.json`
(SHA-256 `c5f1d79dc232b1de6be2a3f4f190bd4adf4fb10425529dff1ad94747402b7dc7`):

| Tool | Version | Exact bytes | Linux/amd64 artifact SHA-256 |
| --- | --- | ---: | --- |
| etcd / etcdctl | 3.7.0 | 23,857,260 | `b05cb07f5686dab8f9cdab89986b44f0dd24aaf5c627176aff325e21fa56f9f0` |
| OpenBao / bao | 2.6.0 | 75,952,530 | `42d83073f2d7a28ed408840138b0312111a8d4b2f5617086f009150336dad6d4` |
| Toxiproxy server | 2.12.0 | 8,642,712 | `556d891134a3c582dc1e1a3f7335fd55142e5965769855a00b944e13e48302fc` |

Each artifact hash must also appear exactly once in the separately hash-pinned
upstream checksum document. Redirects are limited to GitHub's release-asset
host, ambient proxies are explicitly disabled, and every artifact must match
both its frozen byte count and SHA-256 while remaining below its safety cap.
Archive extraction selects only the four named regular files, and a canonical
acquisition receipt records both archive and installed-binary hashes. The
acquisition destination is fixed to
`/Data/CascadeProjects/.artifacts/agent-bridge/biocortex-track-b-t22-a0-real-lab/tools`.

## Owner authorization state

The owner approved proposal SHA-256
`854862a6dd71935590ef0f01072b25dd289221b296c7979964afa7155faaa92b` and
provided a dedicated Ed25519 SSH public key. The repository trust anchor now
binds that proposal, host `tb14`, owner role, canonical public key SHA-256
`331e7a6eee7e57abf583a6dd88700c09bd9576f409d72ff24ef503485be26bd5`,
and fingerprint
`SHA256:cKXQiuD9OQ0KD5zykCE0+lcRSXnrURROhzSm7NqH8Jw`.

The remaining owner action is to sign the exact timestamped payload with
`ssh-keygen -Y sign` under namespace `agent-bridge-t22-a0-owner-v1`.

The signed payload will be valid for at most four hours. The signature grants
only T22-A0 implementation and execution on the named host. A later T22-A1
decision is required for three independent failure domains, cloud/provider
access, non-zero spend, external anti-rollback, or production claims.

The authorization utility reports `READY_TO_GENERATE_EXACT_PAYLOAD`: the exact
repository trust anchor is present and valid, while owner signature and real
execution authority remain false. `bind-anchor` accepted only an absolute,
repository-external `.pub` file and the exact confirmed proposal hash. The
anchor pins the key, host, fingerprint, and proposal hash; the private key
remains outside both repository and artifact root. Verification uses
OpenSSH `sshsig` with the exact owner identity and namespace; it never reads the
private key. A synthetic ephemeral-key test covers the cryptographic path but
cannot install or substitute for the repository owner trust anchor.
Payload generation additionally requires a clean tracked tree and writes only
an exclusive, non-overwriting canonical file beneath the exact lab artifact
root's `authorizations` directory.

## Fail-closed preflight

`scripts/check-biocortex-ab-track-b-t22-a0-real-lab-preflight-v1-pack.sh`
validates the proposal hash and rejects authority, spend, credentials, cloud,
production data, host-global networking, false topology claims, signature
forgery, external anti-rollback claims, and hash drift. It performs no network
or secret access. The current pack exercises 18 directed negative cases.

`scripts/check-biocortex-ab-track-b-t22-a0-owner-authorization-v1-pack.sh`
additionally verifies exact four-hour payload semantics, the memory-only lab
bootstrap-material boundary, OpenSSH Ed25519 signing
and verification, owner identity/namespace binding, 14 payload/key-path
negatives, and four repository-anchor drift negatives. Its repository-facing
result is `READY_TO_GENERATE_EXACT_PAYLOAD`; signature and real-execution flags
remain false.

`scripts/check-biocortex-ab-track-b-t22-a0-acquire-pinned-tools-v1-pack.sh`
adds 20 directed safety checks for pin drift, exact byte-size enforcement, URL
and size policy, output path
escape, duplicate checksums, archive extraction, and the authorization-before-
network boundary. Its present result is
`BLOCKED_EXACT_OWNER_SIGNATURE_REQUIRED`; it confirms that no network request
is constructed and no release artifact is downloaded before authorization.

`scripts/check-biocortex-ab-track-b-t22-a0-real-process-runner-v1-pack.sh`
adds 32 directed negative cases over the signed execution-contract binding,
one-shot authorization use, exact loopback ports, clean environment, etcd CAS
shape, canonical/hash-chained evidence, process-start boundary, and exact
ephemeral-bootstrap-value leak rejection. Its current result is
`BLOCKED_EXACT_SIGNED_PAYLOAD_AND_SOURCE_BOUND_TOOL_RECEIPT_REQUIRED`; the test uses no
real service double and proves that the offline status and rejection paths
construct no network opener, start no process, inject no fault, and create no
real evidence.

## Current transition

The exact execution contract is now frozen at SHA-256
`f84fe9ea9d8948afa7eca516f486bb40d690acfd19437a7b3469af8c4dc37616`.
It binds the loopback ports, one-shot consumption, etcd proxy-disconnect
scenario, OpenBao active-process failover scenario, memory-only bootstrap
material, timeouts, evidence outputs, and non-production claims.

The proposal confirmation and dedicated public-key binding are complete. The
trust-anchor commit must land on both remotes before the exact four-hour payload
is generated. The owner's private key never enters this repository or the lab
artifact root.

The first exact signature, bound to source commit `ae393577`, verified
successfully. Its acquisition attempt then failed closed before final install:
OpenBao's immutable 75,952,530-byte artifact exceeded the original 64 MiB
safety cap. The staging directory was removed; no final tools, service process,
fault, or real evidence was created. The corrected source freezes all three
artifact byte counts, raises only OpenBao's cap to 96 MiB, and requires a fresh
source-bound payload and owner signature; the earlier authorization must not be
reused.

The second exact signature, bound to source commit `5b84873e`, acquired all
three pinned tools and entered the one-shot runner. Real run
`t22-a0-20260722T091828.865372z-250aee7115e7` formed a three-process etcd
cluster, then terminated with `E_ETCD_REPLAY_CONSUME_ADMITTED`. The terminal
receipt SHA-256 is
`c5478beffd84e81c335f027b87904d898d863dd11df252deb37e403b34acf613`;
its cleanup receipt proves all three owned processes stopped. Official etcd
semantics define `succeeded=false` as selection of the transaction Failure
block, whose responses correspond to that block. This makes omission of the
default-false scalar the evidence-backed diagnosis rather than a directly
captured fact. The corrected verifier
accepts an omitted default-false scalar only when the response also contains
exactly one failure RangeResponse that reads back the same consumed key/value
at a non-regressing revision. The consumed second authorization must not be
reused; another source-bound payload and owner signature are required.

After the exact owner signature verifies, the operator sequence is fixed: first
run the owner-gated pinned-tool acquirer into the exact `tools` directory, then
invoke the real-process runner with the same payload and signature. The runner
irrevocably reserves that authorization before starting services, permits no
automatic retry, and always attempts cleanup. A failed real attempt therefore
requires a newly generated and newly signed payload rather than silently
reusing authority.

## Runtime source basis

The executor is pinned to the upstream semantics documented for [etcd v3.7
configuration](https://etcd.io/docs/v3.7/op-guide/configuration/) and its
[default-linearizable Range API](https://etcd.io/docs/v3.7/learning/api/);
[OpenBao integrated Raft join](https://openbao.org/api-docs/system/storage/raft/),
[unseal](https://openbao.org/api-docs/system/unseal/),
[health](https://openbao.org/api-docs/system/health/), and
[Transit sign/verify](https://openbao.org/api-docs/secret/transit/); and the
[Toxiproxy v2 API and `/version` surface](https://github.com/Shopify/toxiproxy).
These references define runtime mechanics only and grant no authority.
