# BioCortex Track-B S18 owned-lab authorization envelope/verifier report

## Result

S18 adds a structurally positive but non-executable owner authorization envelope, an independent out-of-band trust-anchor schema, and a default-off private Rust semantic/Ed25519 verification kernel.

The stage remains blocked for real execution. There is no real trust anchor, owner signature, runner, CAS claim, capability, lab root, process termination, restart observation, provider access, or production evidence.

## Security correction from S17

The unreachable S17 target receipt carried only a signature digest and mixed pre-run authorization with future CAS, STOP, cleanup, and custody receipts. S18 replaces that target with a separated lifecycle:

- immutable owner-signed `AUTHORIZED_UNCLAIMED` envelope;
- independently pinned public-key trust anchor;
- future fresh preflight;
- future atomic one-use claim with fresh external STOP/revocation reads;
- future post-run retention, semantic, batch, cleanup, and custody receipts.

The signed audit timestamps and signed-at-issuance STOP state are not use-time freshness because no trusted-time receipt/current STOP receipt exists. Current external revocation state, one-use CAS, and the external absorbing STOP ledger are the authorization controls.

## Frozen scope

- Families: OL00/OL04/OL05 only.
- Scenarios/attempts: 60 in one canary batch.
- Planned pidfd SIGKILL/fresh process reads: 59/59.
- Planned S16 mapping phases: 113.
- Retry or implicit rerun: forbidden.
- Claim ceiling: L1 process crash and fresh-process restart only.
- Provider, production, network, credentials, paid resources, privilege, mount, reboot, power fault, block-device writes, and Agent-Bridge application effects: forbidden.

## Verification

The release gate requires:

- official Draft 2020-12 validation of both new schemas;
- restricted-canonical JSON and schema mutation KATs;
- active `ring` Ed25519 verification using public RFC 8032 test material only, plus independent fixed framing, authorization-ID, signature, and alternate-anchor KATs;
- anchor substitution, key/domain/message/signature/revocation, semantic-binding, lifecycle, canonicalization, size, and depth negatives;
- deterministic checker receipts under two Python hash seeds;
- the complete S17 full gate, preserving 5,639/5,639 uniqueness and 113/113 target matching;
- offline Cargo, one build job, and one test thread.

## Frozen artifact hashes

The final source-bound hashes are frozen after validation:

```text
- `crates/store/Cargo.toml`: `6b993a079c541d95485c908863da5aa427e4cebffd1cd3fd274105a477d5a2c6`
- `crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model.rs`: `aa94d1e8223fbc55e0cbbfb423a979f351704203a847bb252d513a3bef345a91`
- `docs/design/MEMORY_TEMPORAL_OWNED_LAB_AUTHORIZATION_ENVELOPE_VERIFIER_S18_2026_07_17.md`: `df4787947a6d284153cf98842bbc01b963e9876739edc3da386d6a924cdbe8af`
- `docs/design/fixtures/biocortex-ab-track-b-owned-lab-authorization-validator-contract-s18-v0.json`: `034918f67efea4487dfc28bff7830251dff71e6218317157efae106d07aa8f56`
- `docs/design/fixtures/biocortex-ab-track-b-owned-lab-authorization-validator-status-s18-v0.json`: `f9ca95332e061fc619f2a9f50c2ef9d7eee6607617da7c1051c5fdd5416e57a0`
- `docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-trust-anchor-schema-s18-v0.json`: `648d7f09dc430675707583e5be85adeb95209f8e26bbae7aad4fad08fbf7350b`
- `docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-authorization-envelope-schema-s18-v0.json`: `cb31843865d12c183b37c65d9d5ffae39a7f42bb8a7f4be2fd4f90c099548e6b`
- `docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s18-v0.json`: `3a2c446f3dfa4bad343c9ed582712a7c72135860d0a9eda2d4e64a1886e2f675`
- `crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization.rs`: `17af73a6c7793f53372ec15713afa7e329ce8cb001e4b9570bdbb1f0e982c2f6`
- `scripts/eval/check_memory_temporal_owned_lab_authorization_envelope_verifier_s18.py`: `05aff9ae7c22d653486de9d47e99f5ab6d7837919d17fb1735bd436f20514aea`
- `scripts/eval/fixtures/memory_temporal_owned_lab_authorization_envelope_verifier_s18.expected.v0.tsv`: `ce5919f5ad7b60bd0836e94158d30d4c59bcb28628931049f5046a0f38b2300e`
- `scripts/check-memory-temporal-owned-lab-authorization-envelope-verifier-s18.sh`: `af37e50736e0869b081a11ffeb204cc2aa42defdf0a826e067ae480a573fe61b`
```

## Current authority and execution

- Positive schema available: yes.
- Owner semantic and signature verification kernel: yes, private/default-off.
- Real owner trust anchor/signature: no.
- Single-use claim ledger/capability: no.
- Runner/live observation validator: no.
- Attempts/SIGKILLs/restarts/observations: 0/0/0/0.
- Side effects: `NONE`.

## Next stage

S19 implements and freezes the source-bound runner, fresh preflight, atomic claim ledger, absorbing STOP checks, separate owner/live-observation validators, independent expected-binding builder, and post-run receipt types in one closed typed subject manifest. S19 remains non-live; only its final exact manifest can be presented to the owner.

S20 is the first possible real-authority/live stage: out-of-band anchor installation, owner signature over that exact S19 manifest, fresh preflight, a one-use CAS claim, and only then the exact 60-attempt canary.
