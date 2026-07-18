# BioCortex Track B S17: minimal owned-lab process-crash preregistration

Date: 2026-07-17

Decision: `CONDITIONAL_GO_PREREGISTRATION_ONLY`

Live execution: `BLOCKED_PENDING_AUTHENTICATED_OWNER_RESOURCE_BINDING`

## Outcome

S17 freezes a small, falsifiable L1 experiment for the recovered-envelope path. This packet contains documentation, closed JSON contracts, an offline checker, a negative-mutation suite, and a source-bound gate. It does not implement or launch the runner, kill a process, create a lab database, collect an observation, bind an owner, or unlock an Agent-Bridge effect.

The first batch contains exactly 60 assigned attempts:

| Family | Purpose | Attempts | pidfd SIGKILL | Fresh-exec recovery reads | S16 mapping records |
|---|---|---:|---:|---:|---:|
| OL00 / D00 | clean committed-head control | 1 | 0 | 0 | 1 |
| OL04 / D04 | publish crash/restart cuts | 6 | 6 | 6 | 6 |
| OL05 / D05 | S15 read crash/restart cuts | 53 | 53 | 53 | 106 |
| **Total** | | **60** | **59** | **59** | **113** |

D05 produces an ordered `FIRST_ATTEMPT` and `RESTART` mapping record inside each attempt envelope. Its 106 phase records are not 106 independent trials and do not increment the 60-attempt denominator twice. OL00 and OL04 each carry one `ATTEMPT_RESULT` mapping record, so the closed schema can represent exactly 113 phase records. The one repetition is a canary batch, not a reliability estimate, power calculation, availability result, or production-readiness score.

OL01–OL03 and OL06–OL15 are deliberately outside this first batch. Adding them or adding repetitions requires a new preregistration and independent review; a runner may not silently widen the schedule.

## Frozen predecessor boundary

The plan binds the exact S16 source, integration, contract, catalog, checker, gate, oracle, and known-answer commitments. S17 does not change an S16 row, evaluator, model, known answer, evidence origin, or observation counter.

S16 rows are synthetic historical fault-model rows and intentionally reject nonzero observed-evidence counters. A future S17 observation must live in the domain-separated S17 ledger and reference S16 only by frozen commitment. It must never be written back into the S16 catalog or relabeled as S16 evidence.

## Closed assignment and denominator

The schedule is ordered and closed-world:

- OL00 has only `CLEAN_CONTROL_NO_CRASH`;
- OL04 has the six frozen D04 publication cut identities; and
- OL05 has `BEFORE_OPEN`, `AFTER_OPEN`, 49 ordered `AFTER_DATA_0001` through `AFTER_DATA_0049` cuts, `AFTER_COMPLETE_BEFORE_S14`, and `AFTER_HISTORICAL`.

Only repetition ordinal 1 is permitted. Missing, extra, duplicate, reordered, repaired, retried, or substituted assignments invalidate the batch. All 60 preassigned attempts stay in the denominator, including STOP, timeout, OOM, evidence loss, indeterminate classification, or unexpected recovery state. A retry requires a new preregistration; it cannot replace a failed row.

The planned labels are assignment identities, not result labels. Classification is derived after retention from the raw recovered bytes and metadata. Unknown or unmodeled states map to `OBSERVED_OUT_OF_MODEL_INDETERMINATE`.

Each mapping phase retains its own raw-measurement object. It contains the exact raw-event-stream digest and byte-frame index/offset/length/hash plus publisher/object/receipt/witness/view facts, exact acknowledgement payload when observed, crash cut/index, whether the phase is post-crash restart, observed data-step/length progress, and adapter pre/post state. Actual ABSENT values carry `null` hashes. The raw object cannot contain a case result, disposition, reason, mapped failure, S16 absent sentinel, S16 evidence counter, or planned variant label. This is necessary because D05's killed first attempt and fresh restart have different adapter/read states even though they belong to one attempt.

A separate `s16_virtual_projection` is deterministically derived from that raw object. Only this projection may introduce S16's domain-separated ABSENT sentinels and frozen `(external=0, provider=0, owned_lab=0, side_effects=NONE)` model fields. Those virtual zeros never overwrite or reduce S17's real accounting. For an observed acknowledgement, the retained receipt/witness payload must satisfy the exact S16 acknowledgement binding; otherwise both payload hashes are `null`.

The frozen offline uniqueness KAT compares those 17 observational S16 fields plus the three lifecycle-evaluator fields against all 5,639 frozen rows. All 5,639 augmented fingerprints are globally unique (zero duplicate keys, maximum multiplicity one), and all 113 target phase shapes have exactly one match. Without the lifecycle fields, D04's object-prefix crash/restart is observationally identical to D01's 2,747-byte prefix row; the raw `restarted_after_crash` fact resolves it without a planned-family or case filter.

## Exact L1 process boundary

OL04 and OL05 require an external controller to:

1. create the child and record its PID plus `/proc/<pid>/stat` start identity;
2. open a pidfd for that exact child and recheck the identity;
3. receive a run-bound `CUT_REACHED` frame over an anonymous pipe;
4. send signal 9 through `pidfd_send_signal`;
5. observe pidfd readability, reap the child, record signal 9, and verify the original `/proc` identity is gone; and
6. only then launch the recovery reader with a new `exec`.

Numeric-PID fallback, self-termination, panic, graceful shutdown, injected error, thread/task restart, and a new Rust object in the old process are ineligible. pidfd unavailability, identity drift, a descendant child, an unconfirmed death, timeout, OOM, or leaked process fails closed and invalidates the batch as specified by the future owner decision.

The recovery process must use the frozen runner image, a distinct PID/start identity and nonce, the same recorded boot identity, no inherited target descriptor or process cache, and an exact no-create reopen. It is reaped cleanly after the read. OL00 is a no-crash control and must record zero SIGKILL and zero post-crash restart observations.

No cut-ready marker may be persisted to the test filesystem. The anonymous control pipe is a separate control domain, so it cannot accidentally turn a pre-fsync cut into a post-fsync state.

## Exact storage profile

The candidate root is a unique create-new descendant of `/Data/CascadeProjects/.ab-owned-lab`, named from the frozen source commit, controller identity, monotonic run counter, and a random 256-bit nonce. Each future attempt must re-observe the actual mount containing that descendant and bind its mount ID, device major/minor, mountinfo digest, boot IDs, inode identity, and filesystem type.

The admissible first profile is the exact observed F2FS mount, not the string "f2fs" supplied by the runner. A root on tmpfs, overlay, FUSE, a symlink, an existing directory, or another mount is rejected. Root mode is `0700`; database mode is `0600`; the database is not a symlink and has link count 1.

The SQLite profile is frozen to:

- `journal_mode=DELETE`;
- `synchronous=EXTRA`;
- create-new initialization followed by read/write reopen without create;
- explicit database-file and parent-directory durability barriers;
- no unexpected sidecars at the classified boundary; and
- an owner decision that binds the exact `application_id`, `user_version`, schema digest, profile digest, classifier, expected oracle, and `quick_check` receipt before any run.

Every barrier invocation and return value is raw evidence. `close`, buffered flush, acknowledgement, log text, rename without the required directory barrier, or page-cache survival is not a durable commit.

## Evidence and classification boundary

The SUT and runner emit raw observations only. They cannot set eligibility, acceptance, S16 disposition, mapped failure, or a scientific conclusion. A separate offline classifier verifies process identities, pidfd actions, order, storage profile, durability receipts, recovered bytes, S16 bindings, counters, custody, and the L1 ceiling.

Packet hashing uses an explicit canonical-payload domain that excludes the packet's own hash and signature fields; no self-referential digest is allowed. Each retained raw frame is bound to an exact byte range of the external raw event stream. `classification_input_sha256` is the SHA-256 of a NUL-separated UTF-8 domain and RFC 8785 frame over the raw-packet hash, opaque assignment identity, phase ordinal/kind/process, and the complete phase raw measurement. Family, case, and planned variant are deliberately excluded so they cannot prefilter or disambiguate classification. `phase_record_sha256` uses a separate domain over the complete phase record with only its own digest omitted. ABSENT states use `null` in the packet-level recovery view, not fabricated zero hashes. Classification fields are mutually constrained: an exact unique mapping has cardinality one and non-null mapping fields; an indeterminate result has cardinality zero and null mapping fields.

JSON Schema cannot compare arbitrary values across fields. It therefore does not prove that pidfd target equals child, signal sender equals controller, fresh PID/start/nonce differs from the killed child, image/profile hashes equal frozen bindings, paths share the same run root, or custody hashes equal identity hashes. It also cannot prove that a frame is the retained raw-stream slice, derive the virtual S16 projection, validate the acknowledgement binding, recompute either phase digest, bind the classifier build to the owner-frozen binary, or reproduce the unique S16 row from the phase facts. The observation packet therefore carries a closed 32-rule semantic-validation contract. A separately owner-bound lifecycle validator/classifier must enforce every equality, evaluate against the full frozen 5,639-row catalog without assignment-label prefiltering, verify D05 cut/data-step/length/adapter relations, and recompute the catalog lookup before eligibility. Schema conformance alone proves none of them.

Trusted external time is unavailable in the network-isolated lab and must be recorded as not obtained, not forged. Ordering instead uses bound process identities, monotonic clocks, run counters, a single-use CAS assignment, and the append-only custody chain. Custody sequence 1 requires no predecessor; every later sequence requires a predecessor digest. A same-host or same-disk custodian is not an independent failure domain.

## Resource and failure controls

The proposed future batch remains serial: one controller, one child, one active attempt. Its upper bounds are 768 MiB memory, 256 MiB swap, 256 MiB lab disk, 16 tasks, 256 open files, one build job, and zero paid resources. Nested Cargo builds are forbidden in the run phase.

Cut, signal/reap, recovery, per-attempt, and whole-suite deadlines are frozen by the owner/resource schema. OOM, timeout, leaked child, scope escape, mount drift, pidfd failure, STOP, or custody failure prevents a successful batch claim. Cleanup is limited to the unique run descendant and occurs only after evidence retention; no mount, reboot, drop-cache, block-device, root, provider, credential, production, or non-loopback network operation is allowed.

## Claim ceiling

The maximum possible result is:

`OWNED_LAB_LOCAL_PROCESS_DEATH_RECOVERY_L1_ONLY_NOT_HOST_POWER_LOSS_NOT_STORAGE_DEVICE_DURABILITY_NOT_PROVIDER_DURABILITY_NOT_ROLLBACK_RESISTANCE`

Even a completely eligible batch could speak only about same-boot external process death and fresh-exec recovery for the exact tested source, runner image, SQLite profile, kernel, mount, and device. It cannot prove host or guest reboot recovery, power-loss recovery, storage-device persistence, filesystem durability in general, provider durability or linearizability, witness independence, rollback resistance, equivocation or split-brain resistance, currentness, production readiness, admission, or output authority.

## Authorization boundary

No authenticated owner/resource decision is present. The v0 owner schema deliberately admits only `PENDING` or `REJECTED`; it cannot encode a positive decision. Its positive receipt definition is a successor target, not an executable state. A new positive schema plus cross-field/signature validator is required before authorization can exist. All current runtime and evidence counters are zero; global production prerequisites remain 0/16; `side_effects_unlocked=NONE`.

This owner check is a local project execution control. It is not institutional recognition, legal approval, certification, or a provider permit. The next admissible unit is a separately reviewed semantic/signature validator and positive owner/resource schema. Runner implementation and any live 60-attempt execution remain separate, default-off successor stages.
