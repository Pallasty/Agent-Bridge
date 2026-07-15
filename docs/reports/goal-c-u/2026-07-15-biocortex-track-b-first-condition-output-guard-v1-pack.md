# BioCortex Track B first-condition-output guard v1 source pack

Date: 2026-07-15

Integration baseline: `8daa44ee`

Decision: `SOURCE_PROFILE_PASS_BLOCKED_FAIL_CLOSED_EXTERNAL_ATOMIC_AUTHORITY_AND_NON_BYPASSABLE_OUTPUT_PATH_UNBOUND`

Status: `LOCAL_PRE_OUTPUT_TUPLE_VALIDATION_ONLY_NO_LIVE_OUTPUT_PERMIT`

## Technical summary

This unit closes a local validation gap without claiming to close the live
authorization gap. It validates an exact pre-output tuple, replays the stored
sampling receipt from the hash-bound write request, verifies a complete
seed-derived six-unit generation plan, and binds the first planned output
slot. The same valid input deterministically returns the same replayable,
blocked local validation receipt. It does not consume local state, issue a
permit, invoke a generator, own an output sink, or unlock any side effect.

The result therefore remains fail-closed. A valid local receipt says that the
source-level tuple is internally consistent; it does not say that no output
already exists, that all generator paths are interlocked, or that an external
authority authorized and atomically consumed this attempt. The synthetic S11
authority evidence cannot promote any of those facts to production authority.
The frozen live-binding ledger consequently remains at 0 of 91 satisfied
bindings, and `condition_output_authorized` remains false.

The protocol has an unavoidable causal boundary:

`sampling receipt < first condition output <= final blind map`

The final generation artifact and blind map are downstream of first output.
Their hashes cannot honestly be required by a pre-output generation plan.
They belong in a later post-generation, pre-review map-consumption gate. This
unit instead binds only evidence that can exist before first output: the
terminal local sampling outcome, exact sampling receipt and selection, roster,
private ordering commitment, generation-session plan, generator profile, and
the first output slot.

## Key findings

### Protocol-fact bars

The following bars encode Boolean protocol facts at one common grain: whether
this source pack establishes the named fact. `1` means established by this
unit and `0` means not established. These values are not rates, coverage,
probabilities, confidence scores, or effect sizes.

| Same-grain protocol fact | Value | Boolean bar |
|---|---:|:---|
| Local terminal sampling success verified | 1 | `█` |
| Exact sampling receipt replay verified | 1 | `█` |
| Complete local generation plan verified | 1 | `█` |
| Exact first output slot bound | 1 | `█` |
| External atomic authority verified | 0 | ` ` |
| Non-bypassable generator/output path verified | 0 | ` ` |
| Live condition output authorized | 0 | ` ` |

Chart specification: horizontal Boolean bars; domain `[0, 1]`; no aggregation;
one row per protocol assertion; established facts use one filled cell and
unestablished facts use an empty cell. The chart deliberately has no
percentage axis or normalization.

### Three evidence levels remain distinct

| Evidence level | What this unit can say | What it cannot say |
|---|---|---|
| Protocol assertion | Required identities, hashes, joins, order, coverage, and false authority fields satisfy the closed source contract | The assertion was enforced on every live execution path |
| Local timestamp consistency | Sampling creation, local terminal outcome, plan creation, and local evaluation are strictly ordered in the supplied and replayed artifacts | The timestamps came from a trusted clock or prove real-world anti-shopping order |
| Trusted proof | None is admitted by this source unit | External owner trust, linearizable authorization and consumption, anti-rollback, global single use, or prior-output absence |

Local timestamp consistency is useful diagnostic evidence, but it is not a
trusted pre-output-order proof. Accordingly,
`trusted_pre_output_order_verified=false` even when the local timestamp checks
pass.

### Deterministic source-profile result

- The valid synthetic world contains six generation units: the exact selected
  cases crossed with the condition roster and ordered by the bound private
  seed.
- A second validation of the same world produces a byte-identical blocked
  receipt. This confirms deterministic replay and also demonstrates that no
  authorizing consume operation occurred.
- A preexisting output canary remains byte-identical after validation. The
  validator neither deletes nor rewrites it, but its existence proves why the
  receipt must retain `caller_prior_output_absence_verified=false`.
- The local source surface exposes no output permit, generator call, guard-
  owned sink, or output write. `live_output_capability_emitted=false`,
  `condition_output_authorized=false`, and `side_effects_unlocked=NONE`.
- The frozen admission ledger remains 0 of 91 live bindings. No synthetic
  source-profile success changes that live-state count.

### Directed negative oracle

The closed oracle rejects 47 directed negative vectors:

| Directed-vector category | Rejected vectors |
|---|---:|
| Exact-tuple substitutions (cross-world or alternate invariant digest) | 20 |
| Generation-plan and ordering mutations | 6 |
| Causal-boundary and false-authority mutations | 9 |
| Canonical-form and closed-schema mutations | 7 |
| Bound artifact-byte substitutions | 3 |
| Terminal-abort and missing-outcome states | 2 |
| **Total** | **47** |

These are constructed test-vector counts. They are not code coverage,
security coverage, statistical coverage, failure probability, or proof that
all invalid states have been enumerated.

## Scope and definitions

### In scope

- Canonical, closed pre-output generation-plan and local-validation-receipt
  contracts.
- Exact joins across trial, policy, contract core, eligible frame, allocation,
  sampling-attempt namespace, sampling event, owner registration, namespace
  claim, terminal success outcome, write request, sampling receipt, selected
  case manifest, selection commitment, condition roster, private ordering seed,
  generation session, and first output unit.
- Query of the pinned local custodian outcome and replay of the exact sampling
  writer from the bound write-request bytes.
- Complete selected-case-by-condition plan coverage, contiguous invocation
  indexes, seed-derived order, and an exact first-slot digest.
- Rejection of post-generation fields in the pre-output plan, including final
  generation, answer, capture, blind-packet, and blind-map hashes.
- Deterministic blocked-receipt replay, no-local-consume behavior, preexisting-
  canary preservation, and directed cross-world, order, schema, artifact, and
outcome negatives. Tuple fields that differ between the two complete worlds
are cross-substituted directly; fields that are intentionally invariant across
both worlds receive an alternate nonzero digest so their exact join is still
tested rather than counted as a no-op.
- Frozen live-ledger observation and explicit retention of every unresolved
  authority fact as false.

### Out of scope

- A production external authority provider, production owner-trust root, or
  trusted currentness proof.
- Linearizable `authorize_and_consume`, an external monotonic sequence, quorum,
  transparency log, hardware counter, or other anti-rollback anchor.
- Proof of global single use across processes, hosts, stores, snapshots, or
  restored virtual machines.
- Proof that the caller did not generate, stream, log, or persist output before
  invoking this validator.
- A non-bypassable generator entry point, guard-owned output sink, first-byte
  interlock, live permit, output writer, or output-side crash protocol.
- Final-generation or blind-map validation. Those artifacts do not yet exist
  at the honest pre-output boundary.
- Scientific, model-quality, memory-quality, retrieval, storage-efficiency, or
  biological-brain conclusions.

### Definitions

- **Local guard validation receipt**: a deterministic source-profile statement
  that the bound local pre-output tuple passed validation. It is replayable and
  is not an output permit.
- **First output unit**: invocation index 1 in the complete seed-derived
  generation order, binding one case, one opaque condition identifier, one
  generator profile, and one output-sink commitment.
- **Authorizing consumption**: one externally linearizable transition that
  both verifies current authority and irreversibly consumes the exact
  operation. Validation without that transition is not authorization.
- **Non-bypassable path**: a runtime architecture in which no generator entry
  point can emit a first byte except through a guard-controlled capability and
  guard-owned sink.
- **Final map**: the post-generation binding among generated artifacts,
  captures, blind packet, and condition mapping. Its honest validation point is
  after generation and before review, not before first output.

The intended future live authority grain is narrower than a trial-wide bearer
token. It must bind authority namespace, protocol, owner trial, sampling-
attempt namespace, generation session, output slot, sink identity, operation
identifier, challenge, epoch, and external provider revision. This source unit
does not instantiate that production grain.

## Methodology

### 1. Pin and reconstruct predecessor evidence

The checker loads hash-pinned predecessor validators and the local custodian
surface. It queries the stored terminal outcome by sampling-attempt namespace
instead of trusting a caller-supplied outcome object. The outcome must be an
exact durable local `SUCCESS`, with the expected registration, claim, sampling
event, write request, and receipt identities.

### 2. Replay the sampling receipt

The exact canonical sampling-write request is passed to the pinned writer. The
rebuilt sampling receipt must equal the receipt digest recorded by the stored
terminal outcome. This verifies local reproducibility of the sampling result;
it does not create external custody or anti-rollback evidence.

### 3. Validate the pre-output plan

The plan is canonical and closed. Its selected cases, condition roster, and
private seed are revalidated, then the expected Cartesian product is derived
and sorted by the protocol ranking function. All six units must be present
exactly once with contiguous indexes. Each unit binds its case, opaque
condition, prompt context, generator build, model snapshot, tokenizer,
decoding profile, and output-sink commitment.

Fields that causally require generated output are rejected. In particular, a
caller cannot make the preflight look stronger by injecting a final generation
hash, answer hash, capture hash, blind-packet hash, or blind-map hash.

### 4. Bind the requested first slot and retain false authority

The request must name the exact first-unit digest and request only
`FIRST_CONDITION_OUTPUT`. Placeholder fields for external authority, trusted
clock, currentness-at-use, and the non-bypassable adapter must remain null in
this source profile. Supplying synthetic or caller-authored values fails
closed rather than promoting the request.

### 5. Separate local order from trusted order

The checker requires strict local timestamp order across sampling creation,
terminal outcome, plan creation, and evaluation. It records only
`local_time_order_consistent=true`. Because no trusted clock or external
currentness service is bound, it simultaneously records
`trusted_pre_output_order_verified=false`.

### 6. Exercise replay, non-mutation, and negatives

The success path is invoked twice and must yield an identical blocked receipt.
A preexisting output canary is compared before and after validation and must be
preserved. The 47 directed vectors then substitute exact tuple fields across
two complete synthetic worlds, corrupt plan order and coverage, inject
post-generation or unbound authority fields, violate canonical/schema rules,
replace bound artifact bytes, and present terminal-abort or missing outcomes.
Every vector must fail at the intended boundary.

## Limitations and robustness

The strongest positive result is local tuple validation. It must not be read as
a live security claim. There is no local consuming transition, and the
byte-identical replay result is intentional evidence of that absence. A copied
or restored local store remains outside any externally monotonic authority.

The preserved canary demonstrates a second boundary: this validator cannot
prove that an untrusted caller has not already emitted output. It also cannot
enumerate or interlock alternate CLIs, workers, subprocesses, dynamic imports,
streaming callbacks, logs, traces, or other generator/output routes. Runtime
source hashes are not loaded-code attestation, and same-user filesystem checks
do not supply process isolation.

S11 remains synthetic database/KMS contract evidence. It has no production
provider, production owner trust, externally linearizable authority decision,
or verified anti-rollback anchor. Reusing its artifacts here would test joins,
not establish authority, so this pack does not use S11 to unlock output.

The local timestamp ordering can detect inconsistent fixture order but cannot
establish trusted chronology. The 47 negatives provide reproducible directed
regression evidence only. They do not measure attack-surface coverage, and
they do not exercise the crash states of a live permit, first-byte write, or
external authority consume because none of those mechanisms exists in this
unit.

Finally, 0 of 91 live bindings is a frozen ledger state, not a completion
percentage. The denominator lists required live artifacts; it does not imply
linear progress or that all bindings have equal security weight.

## Next steps

The next unit must establish production authority before any live permit work:

1. Bind a production external provider and production owner-trust verifier to
   the exact trial and operation grain.
2. Implement one externally linearizable `authorize_and_consume` transition
   with currentness, challenge, epoch/revision binding, terminal ambiguity
   rules, and a verified anti-rollback anchor.
3. Remove every bypass path by placing the generator behind a private,
   unforgeable, single-use capability and routing the first byte only through a
   guard-owned sink.
4. Red-team concurrency, split-brain, old-snapshot replay, wrong trust pins,
   capability reuse, sink replacement, and crash boundaries before emitting a
   live output permit.
5. Only after those controls pass, define a private `LiveOutputPermit` bound to
   one operation, generation session, slot, and sink. It must never be
   representable by this replayable local receipt.
6. After generation completes, introduce a separate post-generation,
   pre-review map-consumption gate that validates final generation, capture,
   blind-packet, and blind-map identities before reviewer access.

Until steps 1 through 4 are complete, the correct operational result remains
blocked with no side effects unlocked.

## Further questions

- Which production authority supplies the owner-trust root, and how are
  tenant, trial, audience, operation, challenge, epoch, provider term, and
  revision pinned?
- What is the exact irreversible state machine for
  `authorize_and_consume`, including timeout, retry, split-brain, and
  authority-consumed-but-no-durable-output cases?
- How will the generator eliminate alternate entry points and prevent first
  bytes from escaping through stdout, logs, traces, callbacks, or child
  processes?
- Which sink primitive can be exclusively guard-owned and bind both the
  capability and the durable output identity without pathname or descriptor
  substitution?
- What terminal state is recorded when a crash occurs after authority consume
  but before the first byte, after the first byte but before sink durability,
  or after durability but before the terminal receipt?
- How will external anti-rollback evidence survive database, filesystem, host,
  and virtual-machine snapshot restoration?
- At the later map-consumption boundary, which party owns the atomic transition
  from sealed generation artifacts to reviewer-readable blind packet?
