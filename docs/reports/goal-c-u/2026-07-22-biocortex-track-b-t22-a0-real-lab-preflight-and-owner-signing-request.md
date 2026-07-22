# BioCortex Track B T22-A0 real-lab preflight and owner signing request

## Outcome

T22-A0 is intentionally blocked before owner signature. The current host is a
single physical Linux machine with enough compute and disk for a small
multi-process pilot, but `etcd`, `etcdctl`, `bao`, and `toxiproxy-server` are
not installed. No credential, network endpoint, provider, cloud resource, or
secret was inspected; no service was started and no fault was injected.

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
(SHA-256 `87bad005334766ba4dbb80d11cc8d6418f5d35d3148472235222634471d82cc5`):

| Tool | Version | Linux/amd64 artifact SHA-256 |
| --- | --- | --- |
| etcd / etcdctl | 3.7.0 | `b05cb07f5686dab8f9cdab89986b44f0dd24aaf5c627176aff325e21fa56f9f0` |
| OpenBao / bao | 2.6.0 | `42d83073f2d7a28ed408840138b0312111a8d4b2f5617086f009150336dad6d4` |
| Toxiproxy server | 2.12.0 | `556d891134a3c582dc1e1a3f7335fd55142e5965769855a00b944e13e48302fc` |

Each artifact hash must also appear exactly once in the separately hash-pinned
upstream checksum document. Redirects are limited to GitHub's release-asset
host, downloads are size bounded, archive extraction selects only the four
named regular files, and a canonical acquisition receipt records both archive
and installed-binary hashes. The acquisition destination is fixed to
`/Data/CascadeProjects/.artifacts/agent-bridge/biocortex-track-b-t22-a0-real-lab/tools`.

## What the owner must provide

1. Approve or amend the exact proposal SHA-256 and its bounded scope.
2. Provide one dedicated Ed25519 SSH public key (never the private key) as the
   out-of-band owner trust anchor.
3. After the exact timestamped payload is generated, sign it with
   `ssh-keygen -Y sign` under namespace `agent-bridge-t22-a0-owner-v1`.

The signed payload will be valid for at most four hours. The signature grants
only T22-A0 implementation and execution on the named host. A later T22-A1
decision is required for three independent failure domains, cloud/provider
access, non-zero spend, external anti-rollback, or production claims.

The authorization utility remains blocked while the exact repository trust
anchor is absent. After the owner confirms the proposal and supplies the public
key, a separate commit will pin that key, host, fingerprint, and proposal hash.
Only then can the utility generate a timestamped payload. Verification uses
OpenSSH `sshsig` with the exact owner identity and namespace; it never reads the
private key. A synthetic ephemeral-key test covers the cryptographic path but
cannot install or substitute for the repository owner trust anchor.

## Fail-closed preflight

`scripts/check-biocortex-ab-track-b-t22-a0-real-lab-preflight-v1-pack.sh`
validates the proposal hash and rejects authority, spend, credentials, cloud,
production data, host-global networking, false topology claims, signature
forgery, external anti-rollback claims, and hash drift. It performs no network
or secret access. The current pack exercises 18 directed negative cases.

`scripts/check-biocortex-ab-track-b-t22-a0-owner-authorization-v1-pack.sh`
additionally verifies exact four-hour payload semantics, the memory-only lab
bootstrap-material boundary, OpenSSH Ed25519 signing
and verification, owner identity/namespace binding, and 12 authorization
mutations. Its repository-facing result remains
`BLOCKED_OWNER_TRUST_ANCHOR_REQUIRED` until the owner supplies the public key.

`scripts/check-biocortex-ab-track-b-t22-a0-acquire-pinned-tools-v1-pack.sh`
adds 16 directed safety checks for pin drift, URL and size policy, output path
escape, duplicate checksums, archive extraction, and the authorization-before-
network boundary. Its present result is
`BLOCKED_EXACT_OWNER_SIGNATURE_REQUIRED`; it confirms that no network request
is constructed and no release artifact is downloaded before authorization.

`scripts/check-biocortex-ab-track-b-t22-a0-real-process-runner-v1-pack.sh`
adds 27 directed negative cases over the signed execution-contract binding,
one-shot authorization use, exact loopback ports, clean environment, etcd CAS
shape, canonical/hash-chained evidence, process-start boundary, and exact
ephemeral-bootstrap-value leak rejection. Its current result is
`BLOCKED_OWNER_TRUST_ANCHOR_AND_EXACT_SIGNATURE_REQUIRED`; the test uses no
real service double and proves that the offline status and rejection paths
construct no network opener, start no process, inject no fault, and create no
real evidence.

## Current transition

The exact execution contract is now frozen at SHA-256
`f84fe9ea9d8948afa7eca516f486bb40d690acfd19437a7b3469af8c4dc37616`.
It binds the loopback ports, one-shot consumption, etcd proxy-disconnect
scenario, OpenBao active-process failover scenario, memory-only bootstrap
material, timeouts, evidence outputs, and non-production claims.

The remaining owner action is to confirm proposal SHA-256
`854862a6dd71935590ef0f01072b25dd289221b296c7979964afa7155faaa92b`
and provide the dedicated Ed25519 public key. The trust-anchor commit must land
before the exact four-hour payload is generated. The owner's private key never
enters this repository or the lab artifact root.

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
