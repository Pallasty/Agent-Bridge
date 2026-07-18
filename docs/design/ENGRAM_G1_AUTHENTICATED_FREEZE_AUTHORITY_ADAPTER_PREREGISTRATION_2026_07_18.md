# Engram G1 Authenticated Freeze-Authority Adapter Preregistration

Date: 2026-07-18

Status: **DESIGN PREREGISTERED / IMPLEMENTATION PREREQUISITES PENDING / NO AUTHORITY**

## Decision

This gate freezes the security contract for a future adapter that could turn a
G1.3 structural corpus-freeze review into authenticated, securely captured,
single-use freeze authority. It does not implement that adapter and is not
G1.4.

The current state vocabulary intentionally cannot express approval or
authority. A public validation can produce only the design verdict
`AUTHENTICATED_FREEZE_AUTHORITY_ADAPTER_PREREGISTERED_DESIGN_ONLY_FAIL_CLOSED`.
The future runtime state remains one of:

- `PENDING_IMPLEMENTATION_PREREQUISITES`; or
- `REJECTED_FAIL_CLOSED`.

The registered public contract is
`scripts/eval/fixtures/engram_g1_authenticated_freeze_authority_adapter_preregistration_contract_v0.json`,
SHA-256
`a9d267056fac1662b478d929b011ef971b309db60182f0f1c7563624571945c0`.
Its structural validator SHA-256 is
`632f93b9c9bfcedeca81916ed34be6b4ce8b7b03b916c060b2d1999d06597fde`;
the checker SHA-256 is
`ea8ac0126306de517175a3dffa2a3722439b93b10a3d9d112ca1732f553e6f29`.

The checker digest is an out-of-band review and Git-tree identity, not a
self-verifying field. The checker pins the contract and validator upstream;
the reviewed commit pins the checker downstream. Requiring the checker to
contain its own expected digest would create a circular hash dependency.

The contract pins hardened G1.3 commit
`7062869196d1a3ff8bb72572a39700e65130cde4` and its exact public artifacts:

- contract SHA-256
  `5657ac8f4b6fd4f154de7285fd4a62125bf4ea15cba787d25da40701a3ac1504`;
- validator SHA-256
  `0b7cb3295bc3690bbfeee033de2ddf27a39eb71d0cec68f96e9b27b1a67ef089`;
- checker SHA-256
  `e56a6f50a2c0372d0d59390e8792bc4269c4f63e282d49cf1a1bfe1fdd463e39`.

## Why G1.3 is insufficient

G1.3 binds packet bytes and role commitments, but its `consumer_owned_real`
label is caller-controlled. It does not authenticate signers, securely retain
private file identity, prove custody, consult an independently provisioned
trust root, or consume a replay-resistant capability. A structurally complete
G1.3 double endorsement is therefore a proposal requiring secure capture, not
freeze authority.

The future adapter must securely reopen the original private bytes and
revalidate the entire G1.3 chain while retaining object identity. It may not
upgrade an existing G1.3 receipt by trusting labels or copied digests.

## Independent trust and quorum

The future adapter requires five distinct Ed25519 signatures over one exact
RFC 8785 JSON Canonicalization Scheme envelope after duplicate-key rejection:

1. application owner;
2. outside independence auditor;
3. freeze reviewer 1;
4. freeze reviewer 2;
5. sealed evaluator custodian.

Each role has a separate domain string. Every signature binds the role, key
identifier, key epoch, repository, scope, predecessor, adapter version,
private-packet digests, manifest bytes, nonce, sequence, issue time, and expiry.
All five roles must appear exactly once; partial or duplicate quorum fails
closed.

Trust anchors come from an owner-provisioned private capability-control ledger
outside both the packet and repository. A packet cannot introduce, replace, or
select its own trust root. Key currentness, role scope, epoch, and revocation are
checked again at single-use claim time. The ledger revision is monotonic and
rollback-protected; a fork or stale ledger cannot silently restore a revoked
key.

No crypto dependency, trust ledger, key file, signature, or verifier is added
by this gate.

## Secure-custody profile

The future implementation must resolve every private path component with a
retained directory descriptor and no-follow `openat` semantics. It must retain
the repository-root, parent-directory, and file descriptors through reading,
hashing, parsing, and full-chain validation.

For each private file it must:

- accept only a regular file with `st_nlink == 1`;
- require owner-only directory and file modes (`0700` and `0600`);
- hash bytes read from the retained file descriptor;
- compare `fstat` identity before and after validation;
- re-resolve the final name from the retained parent and prove it still names
  the same inode;
- bind the retained repository root and canonical scope;
- reject symlinks, hardlinks, path or mount swaps, and identity drift; and
- require one local filesystem, rejecting network, FUSE, and remote mounts.

These requirements deliberately exceed G1.3's public-file reader. The present
validator reads only the public design contract and predecessor artifacts. It
does not claim secure custody for anything.

## Authenticated envelope and replay lifecycle

The exact signed envelope binds:

- the G1.3 commit and exact contract, validator, and checker identities;
- the exact G1.3 input packet digests and private manifest bytes;
- the canonical repository and scope identities;
- the adapter contract and implementation versions;
- all signer role, key, and epoch identities; and
- a minimum 32-byte nonce, per-scope monotonic sequence, issue time, and expiry.

Freshness is capped at 24 hours, with a 15-minute claim window. Local wall time
alone is insufficient. The trusted-time profile combines a monotonic clock,
durable boot epoch, signed time checkpoint, and durable high-water mark. Clock
regression fails closed, and a boot-epoch change requires a fresh signed
envelope.

A durable append-only ledger must consume the envelope through a single-use
compare-and-swap claim. The claim receipt binds the envelope digest, nonce,
sequence, repository, and scope. Cross-stage, cross-scope, cross-repository,
post-success, and post-denial replay all fail closed. Key currentness and
revocation are rechecked atomically with the claim.

## One-shot capability boundary

A future successful adapter may mint exactly one typed, single-use capability
for the authenticated manifest. Its only permitted successor is opening a
separate G1.4 candidate-protocol **design review**.

Even that future receipt grants none of the following:

- G1.4 implementation;
- candidate manifest or FIT access;
- candidate implementation;
- BioCortex experiment execution;
- retrieval-order mutation;
- live-store writes; or
- runtime promotion.

The receipt contains no raw identity, query, manifest, or sealed material. A
bearer receipt is forbidden: the receipt binds the authorized consumer key and
process identity. It cannot be replayed or widened to another repository,
scope, stage, or manifest.

## Human-audit policy

Agent-Bridge optimizes for autonomous, recoverable work. Routine validation,
unchanged authenticated verification, and fail-closed denial do not require
per-run human approval. Reversible failures roll back automatically. If a
rollback fails or leaves residual state, the operation must emit durable
failure evidence and record a lesson before retrying.

Independent manual safety audit is reserved for changes with persistent trust
or blast-radius consequences:

- initial trust-root provisioning;
- key rotation or revocation;
- signer-role or quorum changes;
- repository, scope, or predecessor widening;
- hardlink, mount, or filesystem-policy changes;
- first production adapter enablement; and
- suspected secret, privacy, or identity exposure.

This is a transition audit, not a standing approval queue. A denied request is
blocked by the adapter rather than escalated into a routine human prompt. The
public structural validator cannot infer or fabricate a manual-audit outcome.

## Threat model

| Threat | Mandatory future control | Current result |
| --- | --- | --- |
| label laundering | authenticated evidence-class, role, and scope binding | unimplemented; fail closed |
| symlink/path swap | retained no-follow directory and file descriptors | unimplemented; fail closed |
| hardlink escape | regular file, one link, final inode recheck | unimplemented; fail closed |
| key injection/substitution | out-of-band private trust ledger | unimplemented; fail closed |
| stale/revoked key | epoch, revocation, and claim-time currentness | unimplemented; fail closed |
| cross-stage/scope/repo replay | exact predecessor, repository, and scope binding | unimplemented; fail closed |
| local-time rollback | monotonic time, durable boot epoch/high-water mark, signed checkpoint, bounded freshness | unimplemented; fail closed |
| partial/duplicate quorum | five distinct role signatures exactly once | unimplemented; fail closed |
| digest alias/privacy echo | disjoint digest namespaces and redaction | unimplemented; fail closed |
| duplicate/noncanonical JSON | duplicate-key rejection and exact signed encoding | unimplemented; fail closed |
| repository/scope identity drift | retained root identity and canonical binding | unimplemented; fail closed |
| capability replay/theft | durable single-use CAS claim plus consumer key/process binding | unimplemented; fail closed |

## Current zero-authority state

This gate observes no real role or corpus evidence. It does not implement
cryptography, secure custody, replay protection, or capability minting. Every
current readiness, access, implementation, execution, mutation, write, and
promotion field remains false. G1.4 remains closed.

The only admissible next engineering action is a separate, threat-reviewed
implementation gate. That gate must first supply the missing trust-root,
custody, filesystem, replay-ledger, and audit-transition evidence; it cannot
reinterpret this preregistration receipt as implementation authority.

## Run

```bash
scripts/check-engram-g1-authenticated-freeze-authority-adapter-preregistration.sh

python3 \
  scripts/eval/engram_g1_authenticated_freeze_authority_adapter_preregistration.py \
  validate-contract \
  --contract \
  scripts/eval/fixtures/engram_g1_authenticated_freeze_authority_adapter_preregistration_contract_v0.json
```

The checker pins the exact contract and validator hashes, proves deterministic
zero-authority receipts and exact predecessor hashes, and drives at least 90
table-based mutations through a pure semantic seam below the public raw-byte
pin. Recursive comparison rejects every nested field, value, order, length,
and JSON type drift with its specific path. It also rejects duplicate JSON and
contract symlinks and scans both the new validator and imported public reader
for crypto, network, process, or database imports.

A hardlink of the **public design contract** is intentionally accepted and
must still emit secure-custody and authority false. This demonstrates rather
than obscures the boundary: the public validator is not the future private-file
custody adapter, whose registered `st_nlink == 1` rule remains unimplemented
and fail closed.
