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
process, with non-secret generated workload and a zero-dollar ceiling. It may
test process crashes, loopback transport faults, CAS/replay behavior, service
restart, and owned-lab snapshot rollback. It cannot prove independent host
failure, production HA, external anti-rollback, provider behavior, or production
admissibility.

After authorization, only hash-pinned public release artifacts may be acquired.
No system package installation, sudo, host-global `iptables`/`tc`, ambient
credential discovery, cloud API, production data, customer data, or external
output is authorized by this proposal.

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

## Fail-closed preflight

`scripts/check-biocortex-ab-track-b-t22-a0-real-lab-preflight-v1-pack.sh`
validates the proposal hash and rejects authority, spend, credentials, cloud,
production data, host-global networking, false topology claims, signature
forgery, external anti-rollback claims, and hash drift. It performs no network
or secret access.
