# BioCortex / Agent-Bridge Track B S17 preregistration report

Date: 2026-07-17

Decision: `CONDITIONAL_GO_PREREGISTRATION_ONLY`

Live execution: `BLOCKED_PENDING_AUTHENTICATED_OWNER_RESOURCE_BINDING`

## Result

S17 now defines the smallest useful owned-lab L1 process-crash experiment without executing it. The former full-taxonomy draft was reduced to one 60-attempt canary batch after harness review found that 3,060 attempts and rollback/equivocation/witness families exceeded the first-stage process-death claim.

| Measure | Preregistered | Observed now |
|---|---:|---:|
| Families | OL00, OL04, OL05 | 0 |
| Scenarios / assigned attempts | 60 | 0 |
| Clean controls | 1 | 0 |
| pidfd SIGKILL attempts | 59 | 0 |
| Distinct fresh-exec recovery reads | 59 | 0 |
| D05 linked first/restart records | 106 | 0 |
| Total S16 mapping records | 113 | 0 |
| Owned-lab observations | planned only | 0 |
| Provider or production observations | forbidden | 0 |
| Global runtime prerequisites | 0/16 | 0/16 |
| Side effects unlocked | `NONE` | `NONE` |

One repetition is a canary, not a reliability, availability, statistical-power, or readiness claim. OL01–OL03 and OL06–OL15, further repetitions, and L2/L3 failure modes require a new preregistration.

## What was closed

The machine plan fixes the ordered OL00/OL04/OL05 assignment and denominator. A failed, stopped, timed-out, OOM, indeterminate, or evidence-lost attempt remains in the denominator; there is no implicit retry or success-only replacement. D05 carries two ordered mapping-phase records inside one attempt packet, while OL00/OL04 carry one, making all 113 records representable without double-counting attempts.

The observation schema now requires an exact external crash proof for killed cases: child PID/start identity, pidfd open and identity match, `pidfd_send_signal(SIGKILL)`, sender identity, pidfd readability, signal-9 exit, reap, no descendants, and disappearance of the original `/proc` identity. OL00 is conditionally locked to no crash and zero restart accounting.

Recovery is a new executable process, not a reconstructed in-process object. It binds the frozen image, different PID/start identity and nonce, same boot, no inherited target descriptor or cache, exact no-create reopen, and clean reap.

The cut-ready signal uses an anonymous pipe and is never persisted beside the database. This avoids changing the very pre-fsync state the experiment is intended to test.

The storage evidence binds the actual per-run path to its mount ID, device, F2FS mountinfo digest, boot IDs, modes, inode/link identity, and absence of symlink, tmpfs, overlay, or FUSE substitution. The exact SQLite profile is `DELETE + EXTRA`, with database and parent-directory durability barriers, no-create reopen, sidecar checks, and `quick_check` evidence. The separate owner decision must bind the concrete schema/profile, `application_id`, `user_version`, classifier, and expected-oracle digests before a runner can execute.

Classification is independent of the planned label and derived from retained phase-specific raw measurements. Every phase binds an exact raw-event-stream byte frame and carries actual state plus acknowledgement payload, post-crash-restart state, and D05 cut/index, observed data-step/length progress, and adapter pre/post state. Actual ABSENT hashes are `null`; outcome/disposition/reason/planned-variant and S16 sentinel fields are forbidden from the raw object. A separately verified virtual projection supplies only the frozen S16 normalization and zero model counters, never S17 observed accounting. The classifier must search the full frozen 5,639-row catalog without family/case/variant prefiltering. Unknown or non-unique states are retained as `OBSERVED_OUT_OF_MODEL_INDETERMINATE`.

An offline full-catalog uniqueness KAT found all 5,639 augmented 20-field fingerprints globally unique and matched all 113 target phase shapes uniquely (113 unique, 0 missing, 0 multiple). The 17 observable S16 row fields alone left one ambiguity—D04's object-prefix crash/restart and D01's 2,747-byte prefix row. The independently observed lifecycle field `restarted_after_crash`, together with D05 `observed_data_steps` and `observed_len`, removes that ambiguity without consulting the planned label.

The classification-input and phase-record digests have distinct domains, exact RFC 8785 frames, raw-packet/opaque-assignment/process bindings, and explicit self-hash exclusion. The checker now computes both digests for frozen representative rows and rejects raw, ordinal, classification, packet-hash, or digest tampering. Conditional schema rules prevent contradictory control/crash accounting and prevent ABSENT packet-level evidence from carrying fabricated hashes. Cross-field equalities that JSON Schema cannot prove are enumerated in an exact 32-rule semantic contract, including raw-frame slice verification, acknowledgement and virtual-projection derivation, both digest recomputations, classifier-binary/owner binding, no-label-prefilter enforcement, D05 phase consistency, and exact frozen S16 case/variant/row/reason/failure reconstruction. They require a separately bound validator; schema conformance alone is never eligibility.

## Resource envelope

The proposed future run is serial and isolated under a unique create-new descendant of `/Data/CascadeProjects/.ab-owned-lab`:

- one controller, one child, one active attempt;
- 768 MiB memory and 256 MiB swap;
- 256 MiB lab disk, 16 tasks, 256 open files, and one build job;
- explicit cut, signal/reap, recovery, attempt, and suite deadlines; and
- whole-batch invalidation for OOM, timeout, leaked child, mount drift, scope escape, STOP, or custody failure.

Network, provider, production, credentials, paid resources, root, mount/unmount, reboot, drop-cache, block-device writes, Agent-Bridge Bridge/`StateStore`, runtime output, and physical actions remain forbidden. Cleanup is limited to the unique run descendant after durable evidence retention.

## Claim boundary

The highest possible claim is same-boot, local external-process-death recovery for the exact tested build and storage profile. It does not prove host/guest reboot, power loss, storage-device persistence, general filesystem durability, provider durability/linearizability, witness independence, rollback resistance, equivocation/split-brain resistance, currentness, production readiness, admission, or output authority.

A same-host or same-disk witness remains non-independent. Hashes and signatures prove only their stated integrity/custody properties; they do not prove a crash or physical-media persistence.

## Current authorization state

No owner decision, execution capability, runner, live lab root, or observation exists. This packet is offline and default-off. It cannot authorize itself, and passing the checker contributes zero observed evidence. The current v0 owner schema accepts only pending or rejected states; a positive decision is intentionally impossible until a successor implements cross-field/signature validation and a new positive schema.

The owner/resource decision is an internal project control for who may spend the bounded local resources and run the destructive child-process test. It is not legal approval, institutional certification, or recognition by an external organization.

The next permitted stage is a separately reviewed semantic/signature validator plus positive owner/resource schema. Runner implementation comes after that as another isolated commit; live execution remains blocked until both contracts and their fail-closed checks are satisfied.

## Frozen artifact binding

The source-bound gate requires this report to bind each executable or machine-readable S17 artifact. Digests are populated only after the final closed-world review:

- `docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-process-crash-restart-plan-s17-v0.json`: `ca9769ff2b79e474999df6bb5096a3e062b5acf78fa23788f76ae44295531650`
- `docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-process-crash-restart-observation-schema-s17-v0.json`: `26a8cca9f9ca74ceb4b949a2e75d9282a6227623f5bd66cc3333fbff7441588d`
- `docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-owner-resource-decision-schema-s17-v0.json`: `41426b240443672d7e83fc0a8781ddb79acd9beaab1c7f6e9eaf9270c1bdf608`
- `docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s17-v0.json`: `6c35fc3684f7262a7eca2b8405e2c3a21b5ce2f7d282731824ceb67b0ea7163e`
- `scripts/eval/check_memory_temporal_recovered_envelope_owned_lab_process_crash_restart_s17.py`: `d9903fc84701e7f6ceff3ae89a5f9f186efda36e8e8e9166fea7cab59510aed6`
- `scripts/eval/fixtures/memory_temporal_recovered_envelope_owned_lab_process_crash_restart_s17.synthetic.v0.json`: `edc3ef98be452e0a0a5c2e93d2962a1efd87241a4c10cb896f1c6f87504e0c7b`
- `scripts/eval/fixtures/memory_temporal_recovered_envelope_owned_lab_process_crash_restart_s17.expected.v0.tsv`: `4871cf350dbac6f2cc65fc8d178330260e9c6b601a20b6cf9cd33511de9c7c51`
- `scripts/check-memory-temporal-recovered-envelope-owned-lab-process-crash-restart-s17.sh`: `00b93ec57bbb60695061caf31152d97454936aa1ee7100cff0e6aa6a2f469687`
