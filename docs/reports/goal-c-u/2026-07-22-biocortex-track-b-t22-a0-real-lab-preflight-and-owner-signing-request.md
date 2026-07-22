# BioCortex Track B T22-A0 real-lab execution result

## Outcome

T22-A0 completed its bounded single-host real-process objective on the fifth
real attempt. The seventh exact owner authorization entered run
`t22-a0-20260722T183604.320765z-00aee8892cc4`, which returned
`PASS_T22_A0_REAL_PROCESS_FAULT_EVIDENCE`. It proved the three-member etcd
cluster, linearizable exact-value consume, replay rejection, and loopback proxy
disconnect/recovery. It then waited for all three expected OpenBao peers to be
voters, killed active `bao-1`, observed `bao-2` become active, verified the
pre-fault Transit signature through the replacement, restarted `bao-1`, and
observed it rejoin unsealed with three Raft members.

The terminal receipt content SHA-256 is
`3d73929854090364a399755fcc417d83f32cd552b4207a449661277413ec31ca`.
Its 15-event chain ends at
`0cd1e2375e278639f8ea14c1dee5df87fc707c35d2ce5cf6abba1f6436b2798d`.
Independent post-run verification recomputed the canonical terminal,
preflight, and cleanup receipt digests and the complete event chain. All eight
owned process instances stopped, all 14 loopback ports were released, no
host-global network state changed, spend remained zero, and exact-value secret
scanning covered 34 files and 343,261,815 bytes with zero matches.

## Authorized isolated-lab execution boundary

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
After a fresh signature verifies, a later source-bound acquisition may instead
reuse one prior `tools.authorization-<authorization-digest>` directory under
the same artifact root. That path constructs no network opener: it verifies
the prior canonical receipt and current pins, recopies only exact checksum and
release files whose byte counts and hashes match, freshly installs the four
binaries, and emits a new receipt bound to the new authorization and source
commit. Cache inspection remains forbidden before signature verification.

## Owner authorization state

The owner approved proposal SHA-256
`854862a6dd71935590ef0f01072b25dd289221b296c7979964afa7155faaa92b` and
provided a dedicated Ed25519 SSH public key. The repository trust anchor now
binds that proposal, host `tb14`, owner role, canonical public key SHA-256
`331e7a6eee7e57abf583a6dd88700c09bd9576f409d72ff24ef503485be26bd5`,
and fingerprint
`SHA256:cKXQiuD9OQ0KD5zykCE0+lcRSXnrURROhzSm7NqH8Jw`.

The seventh payload, content SHA-256
`00aee8892cc46c2c8d5b38e6e119e746035813bad521879a746323a47182afff`,
was signed under namespace `agent-bridge-t22-a0-owner-v1`, verified against the
dedicated key, bound to source commit `b32a633621c790958991869e96b03f00ebd0403b`,
and consumed exactly once. No further T22-A0 owner action is required. A later
T22-A1 decision remains mandatory for three independent failure domains,
cloud/provider access, non-zero spend, external anti-rollback, or production
claims.

`bind-anchor` accepted only an absolute, repository-external `.pub` file and
the exact confirmed proposal hash. The anchor pins the key, host, fingerprint,
and proposal hash; the private key remains outside both repository and artifact
root. Verification uses OpenSSH `sshsig` with the exact owner identity and
namespace; it never reads the private key. A synthetic ephemeral-key test
covers the cryptographic path but cannot install or substitute for the
repository owner trust anchor. Payload generation additionally requires a
clean tracked tree and writes only an exclusive, non-overwriting canonical file
beneath the exact lab artifact root's `authorizations` directory.

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
adds 24 directed safety checks for pin drift, exact byte-size enforcement, URL
and size policy, output path
escape, duplicate checksums, archive extraction, and the authorization-before-
network boundary. Its present result is
`BLOCKED_EXACT_OWNER_SIGNATURE_REQUIRED`; it confirms that no network request
is constructed and no release artifact is downloaded before authorization.

`scripts/check-biocortex-ab-track-b-t22-a0-real-process-runner-v1-pack.sh`
adds 52 directed negative cases over the signed execution-contract binding,
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

The proposal confirmation and dedicated public-key binding are complete, and
the trust-anchor commit has landed on both remotes. Every subsequent exact
four-hour payload is generated only after its source commit lands on both
remotes. The owner's private key never enters this repository or the lab
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

The third exact signature, bound to source commit `06787029`, acquired the
pinned tools and entered real run
`t22-a0-20260722T093420.701505z-c2dcbab608c5`. Its nine-event hash chain proves
the three-member etcd cluster, exact consumed-state readback, rejected replay,
and Toxiproxy disconnect/recovery before `bao-1` started. OpenBao began its
single-node election about 5.25 seconds after listener start, just beyond the
contract's five-second individual HTTP deadline, and the runner terminated
with `E_LOOPBACK_HTTP_TRANSPORT`; the terminal receipt SHA-256 is
`47d9c785e63743fa48b194388ae0aefac4158c768775300a9135267930a3017f`.
The receipt's conservative stage booleans are false because that source only
populated them after complete success; the canonical events are the direct
evidence of the completed etcd stages. The corrected source derives those
booleans and peak concurrency from observed events even on a later failure,
classifies HTTP failures without recording bodies, removes OpenBao 2.6.0's
unsupported `disable_mlock` field, and configures the documented highest-
performance Raft timing. It deliberately does not retry `/sys/init`: a timed-
out initialization may already have generated the memory-only root token and
unseal share, so retrying would be unsafe. The consumed third authorization
must not be reused.

The fourth payload expired before signature verification and never authorized
tool acquisition or execution. Its signature is retained as expired audit
material and must not be reused.

The fifth exact signature, bound to integrated source commit `85dcc018`,
survived two atomically cleaned GitHub DNS failures before acquiring and
verifying all pinned tools. Real run
`t22-a0-20260722T161610.405993z-cbaa511ecf45` produced ten hash-chained events:
the etcd cluster, linearizable consume, rejected replay, and Toxiproxy recovery
all passed; OpenBao initialization also completed and `bao-2` started. The run
then terminated with `E_BAO_UNSEAL`; terminal receipt SHA-256 is
`7269d1accb691491042996a9022eaddd9d0475b4e98aee5acd3f71610dafe611`.
OpenBao's manual Shamir Raft-join path returns from `unsealWithRaft` after
launching a background wait for keyring replication, so immediate
`sealed=true` is not sufficient evidence of unseal failure. The corrected
runner validates exact Shamir type, boolean states, and the frozen 1-of-1
threshold, permits the temporary sealed state only for joined/restarted nodes,
and waits for exact unsealed health with process-liveness monitoring. The
consumed fifth authorization must not be reused.

The sixth exact signature, bound to source commit `b620f02f`, entered real run
`t22-a0-20260722T180455.411425z-ff7e2b3acb8d`. It proved all three OpenBao
processes could join and unseal, but the runner treated member count as voting
readiness and killed the sole voter before Autopilot promoted either joiner.
The run terminated as `E_BAO_FAILOVER_NOT_OBSERVED`; terminal receipt content
SHA-256 is
`13e5d3bc73da088262fb9e27a2e9fbb8ee181a11c80240b7a8b2ec2238bfda77`.
All seven owned processes stopped and 343,254,086 scanned bytes contained no
exact bootstrap-secret match. The correction requires the exact three-node
set, expected Raft addresses, three `voter=true` states, and one matching
leader before allowing fault injection. The consumed sixth authorization must
not be reused.

The seventh exact signature reused only revalidated hash-pinned release
archives, with a fresh acquisition receipt bound to source commit `b32a6336`
and authorization content SHA-256
`00aee8892cc46c2c8d5b38e6e119e746035813bad521879a746323a47182afff`.
The resulting real run is
the PASS described in the Outcome section. Its claims remain deliberately
bounded to real processes on one physical host: it supplies neither three
failure domains nor external anti-rollback or production evidence.

For every attempt, the operator sequence remained fixed: first run the
owner-gated pinned-tool acquirer into the exact `tools` directory, then invoke
the real-process runner with the same payload and signature. The runner
irrevocably reserved that authorization before starting services, permitted no
automatic retry, and always attempted cleanup. Each failed real attempt
therefore required a newly generated and newly signed payload rather than
silently reusing authority.

## Runtime source basis

The executor is pinned to the upstream semantics documented for [etcd v3.7
configuration](https://etcd.io/docs/v3.7/op-guide/configuration/) and its
[default-linearizable Range API](https://etcd.io/docs/v3.7/learning/api/);
[OpenBao integrated Raft configuration](https://openbao.org/docs/configuration/storage/raft/),
[OpenBao integrated Raft join](https://openbao.org/api-docs/system/storage/raft/),
[unseal](https://openbao.org/api-docs/system/unseal/),
[health](https://openbao.org/api-docs/system/health/), and
[Transit sign/verify](https://openbao.org/api-docs/secret/transit/); and the
[Toxiproxy v2 API and `/version` surface](https://github.com/Shopify/toxiproxy).
These references define runtime mechanics only and grant no authority.
