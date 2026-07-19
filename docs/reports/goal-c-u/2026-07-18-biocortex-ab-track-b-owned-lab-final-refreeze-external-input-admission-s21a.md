# BioCortex Track B S21A final-refreeze and external-input admission report

Date: 2026-07-18

Status: **S21A_NON_LIVE_REFREEZE_AND_EXTERNAL_INPUT_ADMISSION_TOOLING_COMPLETE**

Decision: **S21B_BLOCKED_PENDING_POST_INTEGRATION_UNSIGNED_FINAL_SUBJECT_NEW_OWNER_SIGNATURE_INSTALLED_TRUST_ANCHOR_AND_INDEPENDENT_LIVE_INPUTS**

Implementation mode: **PRIVATE_DEFAULT_OFF_SYNTHETIC_NON_LIVE_REFREEZE_AND_ADMISSION_VALIDATION_ONLY**

Live execution: **NOT AUTHORIZED, NOT IMPLEMENTED, AND NOT ATTEMPTED**

Side effects unlocked: **NONE**

## Outcome

S21A makes the final-refreeze and external-input boundary mechanically
reviewable without creating authority. It provides four distinct closed packet
roles: final unsigned subject, independently installed owner trust anchor,
detached owner envelope under a new S21A domain, and external-input admission
result. Private typed builders, parsers, semantic validators, independent
canonical/digest checks, synthetic KATs, and negative mutations remain default
off and non-live.

The predecessor identities are frozen to S20B integration
`33c2c4df78ef302fd0538986b95fa40a3711ba86` / tree
`6f92c687b61e1433e693ca6cd1bc6390dda97f29` and source
`a1948daaf466563358fcbf054b2bebef8e966777` / tree
`eca0de065221621fcc70941adaefac1f4315bd3e`. The independently computed S20B
integrated archive SHA-256 is
`cde7d7e71591265cc26f57e378448fa066b0083ef4b32cbebd3ec8ca27a8b43e`.

## Synthetic KAT receipts

- final-refreeze subject self digest:
  `0a9194756d3c1117d2bce0094f8336b37b916da6d126c0946f3c603dced532f4`;
- owner trust-anchor document self digest:
  `936381903a35e1c889da276d06c129990d7fc72117716eed39437e35c9a8fd91`;
- owner envelope self digest:
  `5b6c286d41c1ab43d7af28f0226fcdb73920fdfbf4ec5e03b5a59499bda5411b`;
- external-input admission self digest:
  `47c0c36647e992ef6615fa5b0f3e9b728e0ee3a347ba18c3f5c1015d59b22cae`;
- signed-payload digest:
  `2073c06984a6e045374a2848f1bdff74d63276f058f83f0cb8e2fa5002eba003`.

All four fixtures are exact one-line compact sorted-key ASCII JSON followed by
one LF. They are `test_only=true`, `synthetic=true`, and fail closed. The anchor
is not installed, the signature is not verified, no owner authority is
established, every real external-input presence/validation boolean is false,
and no live action occurs. The public KAT retains its stable anchor self digest;
its key identifier `s21a-synthetic-public-kat-v1` and public key
`d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a`
are accepted only on the synthetic test path.

## Post-integration boundary

No real final subject is committed. After S21A is integrated, a real unsigned
subject must be generated outside the repository from the exact integrated
archive and independently rebuilt binaries/toolchains/features/schemas/rulesets.
The candidate cannot provide its own expected digest. Any later change requires
a new refreeze subject and owner decision.

The admission packet binds the checkpoint provider trust anchor, distinct
provider/database failure domains, current checkpoint head and observed
revocation epoch. Its external registration binds registrar/control-plane
identities, provenance, creator binary, the exact predecessor/current revision
relation, and the zero-claim/null-run unclaimed state. Policy bindings include a
nonzero independent-review receipt and current revocation epoch. All required
security digests, Git OIDs, public keys, and signatures reject all-zero values;
catalog/rules/phase and key-version bounds match the typed validator.

S21B remains blocked on that unsigned subject, a new owner signature, a genuinely
out-of-band installed and caller-pinned anchor, a real independent monotonic
checkpoint provider, an external authorized-unclaimed registration, a fresh
observer, real runner, exact environment and canary input pack, fresh STOP and
revocation snapshots, and retention/cleanup/custody/review inputs. S19 signature
reuse and same-failure-domain checkpoint evidence are rejected.

Every real (`test_only=false`) anchor also passes a mandatory repository KAT
denylist. Either the public KAT key identifier or its exact public key material
hard-fails admission, including when installation and caller-pinning fields are
asserted. Repository test vectors therefore cannot be promoted into an S21
authority by relabeling, schema conformance, or matching pinned bytes.

## Claim ceiling

S21A contains no live adapter, checkpoint port, registration writer, claim,
permit, runner handle, executor, private key, credential, or provider access.
Even a later valid canary can claim only owned-lab L1 same-boot process-death and
fresh-process recovery for the exact frozen environment; it cannot establish
power-loss, device, provider, rollback, production, or application durability.

Hash table state: **FINAL_CLOSED_WORLD_BOUND**

## Final artifact digest table

| Path | SHA-256 |
|---|---|
| crates/store/Cargo.toml | 5689e3d5226224d6b971e8921dc731aaf0a17d16a221cbe111a140794f7f1e34 |
| crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner/trusted_controller_orchestration.rs | 57158d82e2cb95ea181a52d9989f39f1ca16070a4a535e2756134d1eb50e239c |
| crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner/trusted_controller_orchestration/final_refreeze_admission.rs | 01ef9e9a27aefa3ff7272e003d4ae6b3f9fbc61ff793a43823a7dffbd2a4af6a |
| docs/design/MEMORY_TEMPORAL_OWNED_LAB_FINAL_REFREEZE_EXTERNAL_INPUT_ADMISSION_S21A_2026_07_18.md | 8dd4df70efbc45be2aaca2f2fce37da9c32de1ca63032409f9266e5be67c8a96 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-final-refreeze-external-input-admission-contract-s21a-v0.json | 906762af12e1058943060bff311f72c257c86710e53d4e245701ebe3561c341a |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-final-refreeze-external-input-admission-status-s21a-v0.json | 6065dfde056b6ab9ec51f2df8020020575fc2988424ad535c439fd143c838369 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-final-refreeze-subject-schema-s21a-v0.json | 69fc0d385723746e453f1dc9faf0e280811de3c453f649c5472223b9eb11ec08 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-final-refreeze-subject-synthetic-s21a-v0.json | b4aff5033c2ff9d904e2987121dcb6c6cb786c783b7925670df320c2094cd4ca |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-trust-anchor-schema-s21a-v0.json | b16039674e4c4d0391078317424e1551338db2fd86b57145b2f661f919023009 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-trust-anchor-synthetic-s21a-v0.json | a3fbb7fb12db23b50149dcca8d2378ba1eafa4691a39be638b7b5c389d26aac2 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-authorization-envelope-schema-s21a-v0.json | dd20d5809509bf84606bb307436819e0bf3d3d0213337cb8ec5b78a38defffc4 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-authorization-envelope-synthetic-s21a-v0.json | 3692b4e7ce5c68b251276de135205fc698e20754e00c0236cc979957a33748f8 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-external-input-admission-schema-s21a-v0.json | 1080a1cc5527297ba26ca10aefba568bab31cd99c12a3d165de4a42db67a4b3b |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-external-input-admission-synthetic-s21a-v0.json | 814ac8273fd85f346aa5b2b4143dfe1bf8166c9812eed82a90344539fa3ac613 |
| docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s21a-v0.json | d7798215729d36447f13c3e44d50b519cfff380fa3046757f30cf4ef833b38f1 |
| scripts/eval/check_memory_temporal_owned_lab_final_refreeze_external_input_admission_s21a.py | 13aa6ec74828632660b982a7a50b2c80ff573ea166d39063deec8cc2bf77ebcc |
| scripts/eval/fixtures/memory_temporal_owned_lab_final_refreeze_external_input_admission_s21a.expected.v0.tsv | bbcd8d2df9ada4d9c299032c6f87aa056ec8b77e83e8398d11dca7d9629d27e6 |
| scripts/check-memory-temporal-owned-lab-final-refreeze-external-input-admission-s21a.sh | 60af34410c06678d385dc61fd015752a5cdbbc3f35ccd3e78fbf4364da7a2400 |
