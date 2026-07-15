# BioCortex / Agent-Bridge Track B External Operation Recovery S10

Date: 2026-07-14

Status:
`LOOKUP_ONLY_OPERATION_RECOVERY_PROTOCOL_PREREGISTERED_SYNTHETIC_JOURNAL_NO_PROVIDER_NO_OWNER_TRUST_ANCHOR_NOT_AUTHORIZED_NOT_TRANSPORT`

Decision: `BLOCKED_FAIL_CLOSED`

## Outcome

S10 preregisters a lookup-only protocol for resolving a lost S9 provider
response by exact operation identity. The interface can query only
`operation_id + exact S9 request digest`; it cannot submit, retry, activate,
consume, or mutate currentness state. `NOT_FOUND` is a terminal failed lookup,
not authorization to repeat the original request.

An authenticated `COMMITTED` response returns one private
`VerifiedExternalOperationRecoveryObservationV1`. The value is non-serializable
and is neither S9 currentness nor admission. S9 has no detached decision
verifier today, so S10 cannot reverify or resurrect the original result without
wrongly calling `request_currentness` again. That bridge remains an explicit
successor gap.

No provider account, network endpoint, credential, owner trust pin, external
journal, production constructor, Bridge feature, `StateStore` surface, or
transport was added.

## Protocol and implementation

The default-off Store feature
`temporal-evidence-s10-operation-recovery-synthetic` depends on S9. Its private
sibling module freezes:

- exact length-framed query and response domains;
- the S9 contract digest and exact original operation/request binding;
- provider profile, namespace, tenant, audience, cluster, incarnation, and
  trust-policy scope;
- lookup query ID and challenge;
- provider term, provider-asserted operation-commit revision, current observed
  journal revision, journal generation, record sequence, decision digest,
  result ID, signer ID, and permit-pinned signer version;
- Ed25519 verification with an independently supplied permit shape;
- `COMMITTED`, `NOT_FOUND`, `PENDING`, `CONFLICT`, and `INDETERMINATE` outcomes;
- one lookup, no submit/retry/cache/clock/local fallback behavior.

The verification order bounds untrusted response labels, authenticates the
complete signed observation before interpreting its state, then checks exact
query, provider, journal, and result bindings. The operation-commit revision is
separate from the query-time observed revision, so unrelated journal writes do
not change the result ID in the non-equivocating synthetic sequence model. A
signature authenticates the provider assertion but cannot detect signer
equivocation; external linearizability remains unattested. Every modeled
provider failure and every non-committed state returns no observation.

## Synthetic sequence evidence

Tests reconstruct an adapter object around one shared in-process journal and
recover the same provider-asserted result. Exact duplicate lookups do not
change journal records; an unrelated global revision advance changes only the
signed observed floor while the operation revision, result ID, record sequence,
and decision digest stay stable absent provider equivocation. Conflicting
request identity fails closed.

This is deliberately not called crash recovery. When the synthetic journal is
lost, the same operation returns `NOT_FOUND`; the protocol cannot distinguish
an operation that never ran from journal rollback. That negative result keeps
external durability, linearizability, rollback resistance, and provider
failure ambiguity unresolved.

## Provider research decision

The later production-validation reference is a dedicated authority service
using Cloud Spanner for the externally consistent operation journal and an
exact-version Cloud KMS/Cloud HSM Ed25519 key for signing. The self-hosted
fault-injection reference is etcd 3.6 with OpenBao Transit Ed25519.

Neither is deployed by S10. The managed reference still lacks a cross-service
atomic commit between database and KMS, an independently delivered owner pin,
instant revocation, and immediate physical destruction. The self-hosted
reference additionally shares operator rollback domains. Both therefore
remain research candidates, not authority receipts.

## Verification

The final gate requires:

- deterministic S10 checker output on two isolated passes;
- an independently recomputed RFC 8032 known-answer vector;
- 14 S10 Rust tests;
- unchanged S9, S8, S7, S6, and context-sampling evidence receipts;
- S9 through S2 Rust regressions;
- Store S10-feature and default-off builds;
- Bridge historical-feature and default-off builds;
- formatting, clean-tree, topology, exact-path, mode, archive, and report
  digest checks under the low-memory build profile.

The full Cargo and parent-module digests intentionally scope this checker to
the frozen S10 tree. A future successor must run it against the archived S10
integration tree and separately validate the retained S10 projection in its
own changed tree.

Final validation result: `PASS`. The S10 checker produced the exact same
49-line receipt on two passes; the S9, S8, S7, S6, and context receipts remained
byte-exact. Rust regressions passed at S10=14, S9=14, S8=14, S7=13, S6=7,
S5=7, S4=7, and S2=14. Store S10/default-off and Bridge historical/default-off
builds passed under the one-job low-memory profile. Formatting, JSON, shell
syntax, exact receipt, and diff checks passed.

## Review

Independent code, security, and artifact review result: `PASS`; final remaining
P0/P1/P2 counts are `0/0/0`. Reviews found and closed the mutable-result-ID
conflation, glue-file/default-feature guard gap, vacuous key-set checks,
non-type-strict JSON comparisons, and over-strong immutability wording before
freeze.

## Admission status

The successor remains `NOT_ADMITTED`. All S9 admission/provider/custody
receipts remain null. S10 also leaves the external recovery provider and
journal durability receipts null. It adds four explicit gaps:

```text
RECOVERY_JOURNAL_EXTERNAL_DURABILITY_UNATTESTED
RECOVERY_LOOKUP_LINEARIZABILITY_UNATTESTED
RECOVERY_OPERATION_SUBMISSION_ATOMICITY_UNIMPLEMENTED
RECOVERY_OBSERVATION_TO_S9_REVERIFICATION_UNIMPLEMENTED
```

The decision remains `BLOCKED_FAIL_CLOSED`; no side effect is unlocked.

## Artifact manifest

- `crates/store/Cargo.toml`: `028c36cdd328c5256067f19a1ada948bb1150705a2f7d1b7c4b2da3e16f40a88`
- `crates/store/src/temporal_replay_transport.rs`: `31bd2379dc47454d78a7f1f9fa0a2df6d663d7eebfaeca6be4b9b410afbcaddf`
- `crates/store/src/temporal_replay_transport/external_operation_recovery.rs`: `850ddf4c47c76e9008671d44c47ba944b384744a4c50640e134e6c24008d90e4`
- `docs/design/MEMORY_TEMPORAL_EXTERNAL_OPERATION_RECOVERY_S10_2026_07_14.md`: `fd903954ca79c722dd9242f734fa7503105c48b102a19038efcdbc83889b21e8`
- `docs/design/fixtures/biocortex-ab-track-b-external-operation-recovery-s10-v0.json`: `da3566f13df522958f05c871ad4679d89cda9b888ba8aa4eb4caaee4c457fb88`
- `docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s10-v0.json`: `9bedb7ef289f31a6b9409875d3b8e6fb3b4784aa972a329de229565caa5b1eb7`
- `scripts/check-memory-temporal-external-operation-recovery-s10.sh`: `283ebeab3582d71bfedd5bedc6a8b2bd50905c461edfd495f9c1b49e84e72431`
- `scripts/eval/check_memory_temporal_external_operation_recovery_s10.py`: `43ef19fce89e6cc6febcd7d774d5fac7d147ebcbcb21034e41dadf6978e0a096`
- `scripts/eval/fixtures/memory_temporal_external_operation_recovery_s10.expected.v0.tsv`: `7a70ab44d9c27ac99c3bb06261bde0e09f55c7fa8afde990f9411d8ffc9eb8c9`

## Next admissible step

Do not connect S10 to Bridge. A later tranche may model and then implement the
atomic operation state machine around transaction commit, exact-version
signing, signature persistence, response loss, and non-equivocating stable
lookup. A real
adapter remains gated on owner-selected infrastructure, an out-of-band trust
pin, real provider/custodian receipts, and fault/recovery evidence.
