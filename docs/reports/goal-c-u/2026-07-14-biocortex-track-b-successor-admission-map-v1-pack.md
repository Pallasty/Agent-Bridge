# BioCortex Track B successor admission/map v1 source pack

Date: 2026-07-14

Frozen source baseline: `2e828d7b86444770c3ef3cd40ac17f26cac6fb0e`

Decision: `SUCCESSOR_V1_SOURCE_COMPATIBILITY_PASS_REAL_RUN_NOT_ADMITTED`

## Technical summary

The successor admission/map v1 source interface is implemented and passes its
synthetic compatibility gate. The repair is append-only: frozen admission v0,
blind-map schema v0, map checker v0, dependency graph, and live-binding ledger
remain byte-identical. New trials route only through an exact v1 tuple; v0
historical replay remains available only through an explicit frozen v0 route.
Neither validator performs automatic version inference, fallback, upcast, or
downcast.

The unit closes four interface defects left by the sampling-receipt writer
pack:

1. `contract_sha256` now has one meaning: SHA-256 of the exact canonical
   `sampling_contract_core.v0` bytes, not the monolithic admission packet.
2. The v1 map consumes the writer's exact
   `selected_case_manifest_source_profile.v0`, including `stratum`,
   `sampling_seed_sha256`, and `selection_commitment_sha256`; it does not
   down-project to the lossy selected-manifest v0 shape.
3. The map checker re-executes the hash-pinned sampling writer against the exact
   write request and requires byte-for-byte receipt equality before joining the
   receipt, selected manifest, frame, map, generation, and blind packet.
4. Sampling identity now has two levels: a trial-only attempt namespace and an
   input-bound event. Changing policy/core, frame, allocation, or entropy
   therefore cannot manufacture a fresh attempt; a later custodian must allow
   one exact policy/core/frame/allocation/event tuple per owner-issued globally
   unique trial namespace.

The positive synthetic vector contains three selected cases, two conditions,
and six answers. The map result closes 18 identity bindings. The directed
self-test rejects 46 map mutations and 32 admission mutations. These counts are
test-vector counts, not statistical coverage estimates. Frozen state remains
non-admitting: 0 of 91 live-ledger bindings are satisfied, all authority fields
are false, and no real frame, entropy, receipt, map, output, review, or score was
created.

The next unit is an independent custodian sampling-attempt claim and
write-outcome receipt. It must verify an owner-issued globally unique trial,
claim that stable attempt namespace once, bind one exact policy/core, frame,
allocation, and sampling event to the claim, and commit the causally later
sampling-write observation or terminal abort. A first-condition-output guard
remains a separate following unit.

## Exact version routing and joins now fail closed

The successor is deliberately a mixed, explicit version tuple. Version numbers
do not need to match textually; every component must match its exact approved
schema and hash.

| Component | Exact v1 route | Historical v0 route | Cross-route behavior |
|---|---|---|---|
| Admission policy | `real_run_admission_policy.v1` | Frozen `real_run_admission.v0` | No default version and no fallback |
| Contract identity | `sampling_contract_core.v0` canonical bytes | Monolithic v0 preregistration semantics | No hash aliasing |
| Sampling receipt | `sampling_receipt.v1` / schema `e418b582…` | `sampling_receipt.v0` / schema `9e73afee…` | Each checker rejects the other receipt shape |
| Selected manifest | `selected_case_manifest_source_profile.v0` | `selected_case_manifest.v0` | No lossy projection |
| Blind map | `blind_map.v1` / schema `475f5c51…` | `blind_map.v0` / schema `ad40df50…` | No shared `latest` alias |
| Map request/result | `map_bijection_request.v1` / `validation_result.v1` | v0 request/result | Exact request schema routes first |
| Opaque identity domain | `agent-bridge/track-b/blind-map/v2` | `agent-bridge/track-b/blind-map/v1` | Cross-version opaque-ID reuse forbidden |

The result is not a live migration. It is a source-level successor path whose
runtime state template remains empty and blocked.

### Contract identity is non-circular

The v1 admission policy, contract core, receipt, and runtime state are separate
layers:

| Layer | Contains | Must not contain |
|---|---|---|
| Admission policy v1 | Static protocol, source identities, routing, stage obligations | Per-trial frame, entropy, seed, receipt, output, review, or score state |
| Sampling contract core v0 | Exact pre-seed policy hashes and `trial_id`; `admission_policy_sha256` binds the exact policy bytes | Dynamic sampling or downstream artifacts |
| Sampling receipt v1 | Contract-core digest, frame/allocation/entropy commitments, seed, full selection commitment, probabilities and weights | Post-write custody claims or output authority |
| Admission state v1 | Later receipt/map/guard/custody identities | Any field that would be hashed back into the already frozen contract core |

This direction avoids the cycle
`admission SHA → contract SHA → receipt SHA → admission SHA`. The receipt and
map both call the contract digest `contract_sha256`, but the admission policy
defines that name as the exact contract-core digest only.

### Selected-case joins preserve the writer's v1 evidence

The map checker validates these exact one-to-one relations:

| Surface | Grain/key | Required join |
|---|---|---|
| Eligible frame | `(trial_id, case_id)` | Unique case ID and exact admitted `stratum` |
| Selected manifest | `(trial_id, case_id)` | Ordered unique subset of frame; same stratum |
| Inclusion probability | `(trial_id, case_id)` | Exact selected key order; reduced `n_h/N_h` |
| Sampling weight | `(trial_id, case_id)` | Exact selected key order; reciprocal reduced `N_h/n_h` |
| Sampling attempt | `(protocol_version, trial_id)` | One exact policy/core, frame, allocation, and event may later be claimed by the custodian |
| Sampling receipt | One per sampling event candidate | Exact selected-manifest bytes, seed commitment, selection commitment, writer, schema, and contract core |
| Blind-map assignment | `(protocol_version, trial_id, case_id, opaque_answer_id)` | One condition per answer and one answer per case-condition cell |

Missing, extra, duplicate, reordered, cross-stratum, cross-seed, or
cross-selection rows fail closed. The checker also verifies
`answer_count = case_count × condition_count` locally rather than depending on
an outer identity checker.

### The receipt is recomputed, not trusted by declaration

For every accepted map request, the v1 checker:

1. verifies exact bytes for the receipt schema, writer, seed derivation,
   selection algorithm, contract digest profile, and blind-map schema;
2. executes the exact sampling writer source against the canonical write
   request;
3. requires the rebuilt receipt bytes and digest to equal the supplied receipt;
4. requires the separately supplied contract core, frame, and selected manifest
   to equal their write-request objects;
5. joins the contract, frame, seed, selection commitment, selected keys,
   roster, generation, blind packet, and map; and
6. emits hashes, counts, and false authority fields only.

Raw-file mode reads each artifact through the remaining global byte budget. It
cannot first retain ten per-artifact maxima and only then apply the 64 MiB
aggregate cap; a cumulative overflow is rejected before the next artifact is
loaded. Paths must resolve directly to single-link regular files; symlinks,
FIFOs, other special files, hard links, and identity/size races fail closed.

This proves deterministic source compatibility for the tested inputs. It does
not prove that `O_EXCL`, `fsync`, custody, or trusted timing occurred in a real
run.

## Scope, evidence, and metric definitions

### In scope

- Append-only real-run admission policy v1 and its closed-world validator.
- Append-only blind-map schema v1 and map-bijection checker v1.
- Exact receipt-writer request replay and byte equality.
- Exact contract-core, selected/frame, probability/weight, seed, selection,
  map, roster, output, and blind-packet joins.
- Explicit v0 historical replay and v0/v1 mutual rejection.
- Stable trial-only sampling-attempt identity plus core/frame/allocation-bound,
  pre-entropy sampling-event identity.
- Synthetic positive, version-confusion, data-quality, authority, timing,
  leakage, cardinality, and source-substitution negatives.
- Source/Git provenance and immutable predecessor checks.

### Out of scope

- A real contract core, frame, allocation, external entropy value, sampling
  receipt, generation, map, review, score, or unblinding artifact.
- Independent custody, trusted-clock evidence, entropy unpredictability, or
  anti-shopping order.
- Owner trial registration, global attempt-namespace claiming, one exact
  policy/core/frame/allocation/event enforcement, terminal abort persistence,
  or map-consumption replay protection.
- A first-condition-output interlock.
- Runtime Python/stdlib/binary provenance or a live source binding.
- Any scientific, product, memory, storage-efficiency, retrieval-quality, or
  biological-brain result.

### Quantitative definitions before values

- **Case count** is the number of unique selected opaque case IDs in the
  synthetic selected manifest.
- **Condition count** is the number of unique seed-derived opaque condition IDs
  in the synthetic roster.
- **Answer count** is the number of global opaque answer IDs and must equal the
  Cartesian case-condition cell count.
- **Identity-binding count** is the 17 required SHA-256 fields in blind-map v1
  plus the exact blind-map schema source identity.
- **Mutation count** is the number of deliberately constructed negative vectors
  rejected by the intended closed-world validators. It is not a probability,
  fuzzing coverage measure, or proof that every invalid input is rejected.
- **Live-binding satisfied count** is the number of ledger rows whose exact
  `binding_satisfied` value is `true`.

| Synthetic diagnostic | Result |
|---|---:|
| Selected cases | 3 |
| Conditions | 2 |
| Answers | 6 |
| Identity bindings | 18 |
| Directed map mutations rejected | 46 |
| Directed admission mutations rejected | 32 |
| Total directed mutations rejected | 78 |
| Frozen graph nodes | 23 |
| Frozen live-ledger binding rows | 91 |
| Satisfied live-ledger bindings | 0 |

The table is categorical test evidence. No chart is used because there is no
measured trend, distribution, or effect magnitude; bars would turn protocol
cardinalities into a misleading performance comparison.

## Methodology

### 1. Freeze predecessor evidence

The checker pins the receipt v0/v1 schemas, blind-map v0 schema, map v0 checker,
sampling writer, seed derivation, selection algorithm, contract digest profile,
dependency graph, live ledger, admission v0 packet, and synthetic predecessor
fixtures by exact SHA-256. The successor pack does not edit them.

Admission v0 is a historical closed-world packet whose checker also pins old
repository source bytes. Running that checker against current `master` is not a
valid replay because those historical sources have legitimately changed. The
Git gate therefore materializes frozen commit
`59869af57f2a0b24647f3b47d7bea93839bfbefe`, runs the v0 checker there, and
requires its checked-in result byte-for-byte. This preserves replay without
pretending the old admission is current.

### 2. Build a policy-bound synthetic sampling attempt and event

The deterministic fixture derives a new synthetic trial from the predecessor
writer fixture. It replaces `admission_policy_sha256` with the exact successor
policy digest, recalculates the contract core, frame binding, seed, complete
selection, selected/reserve manifests, and receipt through the frozen writer.
The resulting contract-to-policy join is exact.

The stable sampling-attempt namespace uses:

`attempt_domain || NUL || trial_id`

It excludes policy/core, frame, strata allocation, and external entropy. The
exact sampling-event digest uses:

`event_domain || NUL || contract_core_sha256 || NUL || trial_id || NUL || eligible_frame_sha256 || NUL || strata_allocation_sha256`

External entropy is intentionally excluded. Otherwise a caller could change
entropy and claim a new logical event. Core, frame, or allocation changes may
create a different event, but all remain inside the same trial-only attempt
namespace. The current stateless checker validates both digests; only a later
external custodian can verify owner issuance and enforce one exact
policy/core/frame/allocation/event claim and one terminal outcome per namespace.

### 3. Compose and validate the map

The checker uses a distinct answer-blinding seed, the v2 identity domain, and a
sorted private condition roster. It reconstructs deterministic generation and
blind ordering, requires global answer-ID uniqueness, verifies exact answer
bytes, and rejects direct condition-key, condition-ID, and raw-seed disclosures
from the reviewer-visible blind packet.

The time comparison establishes only internal timestamp-string consistency:
receipt time precedes first-output time, which does not follow map creation.
Because the receipt explicitly retains
`pre_output_timing_verified=false`, the result reports
`protocol_time_order_consistent=true` and
`pre_output_timing_verified=false` as different facts.

### 4. Exercise version and mutation gates

The normal diagnostic is deterministic across `PYTHONHASHSEED` values and must
match the checked-in TSV byte-for-byte. Self-test covers exact-field removal,
extra fields, v0/v1 substitutions, source-hash changes, contract aliasing,
receipt/request divergence, selected/frame join damage, seed and selection
damage, false-to-true authority escalation, timestamp order, roster and answer
duplicates, private-token disclosure, seed separation, allocation-shopping
namespace identity, cumulative raw-input budget exhaustion, and rejection of
symlinks, FIFOs, and hard links.

The v0 map validates its frozen synthetic fixture. The v1 map rejects that v0
request, and the v0 map rejects the v1 request. No failed v1 validation invokes
v0 as a fallback.

### 5. Bind Git provenance

The shell gate requires an exact ten-path, all-add source commit with the frozen
baseline as its sole raw parent. It rejects shallow history, replace refs,
grafts, symlinks, hard links, nondefault index flags, mode drift, and
worktree/index/HEAD/source-blob divergence. After integration it requires an
ordinary two-parent merge containing that exact source commit. Commit IDs are
reported by the gate after creation rather than embedded in self-referential
packet bytes.

## Evidence inventory

| Artifact | SHA-256/status |
|---|---|
| Admission policy v1 | `2847ebd368c4a0b557f95b2c91f72b69e31126cf3623ed29320b4154537e3dbe` |
| Admission checker v1 | `8d493f3452589fe1cfd9ece27388c3222a28bac47ca6298cab66c6c3ed52db24` |
| Blind-map schema v1 | `475f5c518df83049808e0a118f50ef83026b8c8202bebfd4439dfb9c416fd724` |
| Map-bijection checker v1 | `92926f3e01910501e20a7d5f8f9b0cab79e28ca38ae2717966b8b6977fa89e58` |
| Synthetic config | `a95a0052a6abfa93ea58f7f913429b8aad4c368cb91a5a54ad98d36fc58470a8` |
| Pack manifest | `7cf7b5ea2a4f93d85616c57604ae7d06fe707f77d37546681e13fcc5744e3fb6` |
| Expected normal diagnostic | `e5dc9aad75adf5deeb114fdb568547d2cb3d4bcd4e975174799b4be47a4422e0` |
| Purpose checker | Final gate binds source blob and reports hash |
| Self-test output | `84ddcc09147c6a04e343d491d7adfb2d6c0bc0706dc70d831e70f15d20d2bb67` |
| Predecessor executable lineage | Seed derivation, selection algorithm, receipt writer, and predecessor gate are all exact-hash listed in the manifest |
| Frozen live bindings | `0 / 91` satisfied |
| Source commit and ordinary merge | Reported by final Git gate |

## Limitations, uncertainty, and robustness

The source pack establishes deterministic compatibility only within its exact
schemas, source hashes, limits, and synthetic vectors. The 78 mutation cases
are directed regression controls, not exhaustive formal verification.

Receipt recomputation proves that the supplied bytes are what the approved
source would build from the supplied request. It does not prove that the writer
executed before output, wrote to a custodian-controlled filesystem, or that its
same-process return observation was retained honestly. `O_EXCL` at one leaf in
one directory is not a global attempt ledger.

The attempt namespace deliberately contains only the v1 domain and trial ID;
the event includes contract core, frame, and allocation but excludes entropy.
This keeps policy/core, frame, allocation, and entropy changes under one stable
attempt identity while retaining the exact selected inputs in the event and
claim. The checker does not prove that a trial ID was owner-issued or globally
unique, and it does not persist consumption state. A privileged caller can
still replay a fully valid request unless a later custodian verifies the owner
registration and owns an external single-use namespace claim.

The map is necessarily post-generation evidence. Its success cannot authorize
the generation that already happened. A separate pre-output guard must consume
custodian evidence before any first condition output. Map validation also does
not authorize review, scoring, or unblinding.

The opaque ID derivation uses a new domain to prevent cross-version aliasing.
Cryptographic source checks do not establish host interpreter, standard-library,
kernel, filesystem, hardware, or custodian provenance.

## Recommended next steps

1. Complete independent data-quality, security, and Git-provenance review of
   this exact ten-path packet.
2. Create the sole-parent source commit, integrate it with an ordinary
   two-parent merge, rerun descendant validation, and push only after every
   gate passes.
3. Implement an independent custodian attempt-claim and write-outcome receipt.
   It must key global single use by an owner-issued globally unique trial
   namespace, bind exactly one policy/core/frame/allocation/event tuple, and
   record exactly one success or terminal abort. A new directory, policy/core,
   frame, allocation, or entropy value must not turn that namespace into a
   retry.
4. Implement the first-condition-output guard. It must require the exact v1
   policy, contract core, receipt, custodian outcome, trusted timing/order
   evidence, runtime source provenance, and unconsumed admission attempt before
   output.
5. Add a later map-consumption receipt before review, preserving the same
   single-use discipline for private mapping evidence.
6. Only after owner policy and all live bindings are complete should the system
   consider a synthetic end-to-end rehearsal. Source compatibility must never
   be treated as real-run admission.

## Further questions

- Which external custodian verifies globally unique owner-issued trial IDs,
  owns the sampling-attempt namespace, atomically binds its one exact
  policy/core/frame/allocation/event tuple, and makes success/abort durable and
  globally singular across protocol versions?
- What exact host, mount, file identity, process, clock, interpreter, and source
  provenance must the write-outcome receipt bind?
- How are partial writes, process death, ambiguous `fsync` completion, and
  custodian timeout represented as terminal outcomes without enabling retries?
- What owner-authorized process creates a new trial after terminal abort, and
  which policy/frame fields must be refrozen?
- Where can the first-output guard sit so every generator path must traverse it?
- What later receipt proves a private map was consumed exactly once for the
  intended blind packet and reviewer roster?
