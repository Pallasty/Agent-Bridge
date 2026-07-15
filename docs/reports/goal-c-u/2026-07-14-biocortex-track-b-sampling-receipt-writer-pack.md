# Title: BioCortex Track B sampling receipt writer pack

## Technical summary

This pack implements the final independent-public Track B source candidate,
`sampling.sampling_receipt_writer_sha256`, as a deterministic sampling-receipt
builder and exclusive-write protocol. It closes the public **source-authoring**
frontier only. It does not create a live binding, admit a real run, authorize a
condition output, or prove external custody.

The writer does not reinterpret the frozen sampling-receipt v0 schema as
sufficient. That schema is preserved byte-for-byte. A new v1 schema is added
because v0 cannot bind the derived sampling seed or the complete selection
commitment and has `additionalProperties=false`. The v1 receipt requires the
non-circular contract-digest profile, external-entropy commitment, derived seed
commitment, seed domain and message profile, complete selection commitment,
and three explicit false boundary fields:
`condition_output_authorized=false`, `anti_shopping_order_verified=false`, and
`pre_output_timing_verified=false`.

The writer consumes an exact pre-seed contract core, eligible-frame rows,
stratum allocations, externally committed entropy, and fixed source bindings.
It independently recomputes the contract digest, sampling seed, complete
selection, selected and reserve manifests, rational inclusion probabilities,
and reciprocal weights. It rejects caller-supplied derived values that could
otherwise create a confused-deputy or join-substitution path.

Persistence uses an exclusive, locally read-only snapshot discipline: a
caller-opened private `0700` directory descriptor, a fixed leaf name, `O_EXCL`,
initial mode `0600`, content `fsync`, `fchmod` to `0400`, seal `fsync`,
parent-directory `fsync`, and an exact reread. The writer returns the post-write
execution outcome to its caller but does not insert that outcome into the
receipt. Persisting a claim
that file and directory synchronization have already completed inside the file
being synchronized would reverse the causal order or require a post-write
mutation.

All validation in this pack uses source-only synthetic vectors. The frozen
checker executes 86 directed self-test cases and produces the same bytes under
both required `PYTHONHASHSEED` values. Dependency-graph accounting is 13 of 13
independent-public source candidates, zero live bindings, and an empty next
public authoring frontier.

## Key findings/evidence

### The v0 interface gap is repaired by versioning, not mutation

The frozen v0 sampling receipt binds the entropy receipt and the seed-derivation
algorithm, but it does not bind `sampling_seed_sha256` or the selection
algorithm's complete `selection_commitment_sha256`. Because the schema also
rejects additional properties, adding these fields to a purported v0 instance
would be invalid. Mutating the committed v0 schema would invalidate the prior
source evidence that already identifies it by SHA-256.

The repair is therefore append-only:

| Interface | Treatment | Audit consequence |
|---|---|---|
| Frozen sampling receipt v0 | Unchanged | Prior hashes and historical evidence remain reproducible |
| Sampling receipt v1 | New source candidate | Seed identity and the complete selection envelope become explicit receipt bindings |
| Frozen admission/map v0 | Unchanged | They remain incompatible with v1 and continue to fail closed |
| Live-binding ledger | Unchanged | No source hash is represented as a runtime or custodian binding |

The v1 schema requires, in addition to the v0-equivalent provenance and
manifest commitments:

- the exact contract-core digest profile and its resulting contract digest;
- the external-entropy commitment used by seed derivation;
- `sampling_seed_sha256`;
- the frozen seed domain and exact seed message profile;
- `selection_commitment_sha256`; and
- `condition_output_authorized=false`,
  `anti_shopping_order_verified=false`, and
  `pre_output_timing_verified=false`.

Those fields close the public receipt's seed-to-selection identity gap. They do
not prove when entropy became available, who controlled it, whether allocation
was frozen before entropy, whether the frame was honestly frozen, or whether
any downstream output guard honored the false authorization value. The required
`receipt_precedes_first_condition_output=true` is a protocol assertion, not
schema-level proof of causal timing.

### The contract digest has an exact non-circular domain

The contract digest is computed over a machine-checked exact allowlist of
pre-seed commitments. Unknown, missing, duplicate, or noncanonical fields are
terminal. The allowlist excludes all values that arise only after entropy is
revealed or the sample is selected, including:

- external entropy or its later reveal material;
- the derived seed and seed commitment;
- selected and reserve manifests;
- case inclusion probabilities and sampling weights;
- the selection commitment and sampling-receipt digest; and
- condition outputs, reviews, scores, preference summaries, or unblinding
  artifacts.

This produces a directed computation rather than a hash cycle:

```text
pre-seed contract core
  -> contract_sha256
  -> external entropy commitment + eligible frame
  -> derived sampling seed
  -> deterministic selection
  -> selected/reserve manifests + probabilities/weights
  -> exclusive-created, locally read-only sampling receipt snapshot
```

The profile defines the digest shape and requires the allocation manifest to be
frozen before entropy; it does not verify independent custody of that order,
fill owner policy values, or turn placeholders into valid commitments. A real
run must supply all admitted pre-seed values before entropy and sampling.

### Derived sampling evidence is recomputed, not trusted

The writer loads the exact hash-verified dependency source bytes into private
module namespaces and invokes the committed seed-derivation and selection
algorithms there. Those executions receive a strict import allowlist backed by
primitives captured by the writer, including a writer-bound one-shot
HMAC-SHA-256 implementation. This isolates the two algorithms from later
ambient import-path or `sys.modules` substitution. It binds their exact source
identities, domains, and message profiles and rejects disagreement between
recomputation and any expected commitment supplied for checking.

The writer constructs the selected and reserve manifests from the recomputed
selection result. It also reconstructs each selected case's reduced inclusion
probability `n_h/N_h` and reciprocal weight `N_h/n_h`. Selected and reserve rows
must be disjoint and must partition the eligible frame exactly. Probability and
weight keys must equal the selected-case key set exactly, with one row per case
and no join multiplication.

The complete selection commitment remains the authority over the selection
envelope. Individual manifest hashes make joins explicit, but are not a
substitute for recomputing and checking that complete commitment.

### Exclusive persistence separates receipt bytes from execution evidence

The writer's persistence protocol requires all of the following before it
returns success:

| Control | Required behavior | Boundary |
|---|---|---|
| Output confinement | Accept only a caller-opened, current-euid-owned `0700` directory FD and use a fixed leaf | Does not establish who controls that directory |
| Creation | `O_EXCL` exclusive creation with no overwrite path | Prevents replacement through the writer API, not hostile privileged filesystem mutation |
| File mode | Create as `0600`, then `fchmod` to `0400` and seal with another file `fsync` | Establishes a locally read-only end state; the same euid can still chmod or mutate it later |
| Durability | Flush receipt bytes and perform content and seal file `fsync` calls | Establishes successful local system-call completion only |
| Directory durability | Perform parent-directory `fsync` after creation | Establishes successful local system-call completion only |
| Reread | Reopen and require exact byte/hash identity | Detects immediate divergence on the checked path |
| Execution outcome | Return success metadata after all checks | Deliberately not embedded in the already written receipt |

The returned outcome is useful to a future custodian, which can commit it in a
separate causally later receipt. This source pack does not implement that
custodian receipt.

### Source coverage closes without granting live authority

The frozen dependency graph previously had 12 of 13 independent-public source
candidates and exposed exactly one frontier node:
`sampling.sampling_receipt_writer_sha256`. After the writer source is frozen,
the expected source-only state is:

| State dimension | Expected value after validated freeze |
|---|---:|
| Independent-public graph nodes | 13 |
| Exact public source candidates | 13 |
| Live bindings created by this pack | 0 |
| Public authoring frontier | Empty |
| Condition outputs authorized | 0 |

This is source completeness, not experiment readiness. The frozen live-binding
ledger and real-run admission packet continue to contain unset blockers, and
the v0 admission/map surfaces do not accept the v1 receipt. Consequently, the
system remains fail closed.

### Evidence inventory

The source and merge commit IDs are intentionally not embedded in packet bytes:
doing so would create a self-reference. The shell gate reports and validates
those Git identities after commit creation.

| Evidence artifact | Role | SHA-256/status |
|---|---|---|
| Frozen sampling receipt schema v0 | Historical interface retained unchanged | `9e73afee2f6366a241b155680b4f77341adeb7c4e341ab91b8d4b1499b5aacbd` |
| Sampling receipt schema v1 | Seed/selection-complete receipt shape | `e418b58246eaf183b5624c7eb12299caeea933c83a07584faa915651b3cd48d4` |
| Non-circular contract-core digest profile | Exact pre-seed allowlist and exclusions | `a8972ad5e75b30634931fee84f08226e2660413b45cf9dfea948089d61160243` |
| Seed-derivation source | Independently recomputed seed | `4f51781ff707e89b4c09adffeafbdaacd75c7e1571d1a86e45d336aace888a3f` |
| Sampling-selection source | Independently recomputed full selection envelope | `e327faf2ad73718dc33f68fdb66a89abf0ac84fbbf8d828ff79fa0e8b75772ec` |
| Sampling receipt writer | Deterministic construction, controlled dependency imports, and exclusive persistence | `a8642d2b524183e060eb2f2c16d3a4bba4bca43c8e18b8524bc14738d4f6d975` |
| Synthetic fixture | Positive known-answer and adversarial source-only inputs | `79bdb87f5fdaeb72423ff12002f4cf9a0deca2e9cd9b86e820321357a0641b8a` |
| Pack manifest | Source bindings, dependency evidence, boundaries, and fixture | `3fb4e59754c9c52b6c0ebb642dccdd6ccb7f9282fca6bfb83a4fd001e76437e9` |
| Expected public diagnostic | Byte-for-byte normal-mode oracle | `596d14471a20409bd29b74e9a917187dda10a22b8b0f1ad0070e374cf7cb3b62` |
| Purpose checker | Structural, semantic, and mutation validation | `91a30e8e77473dd2ff4ddcfc3a77ffd3b7a70869b1bf16782444e5eacfcec0e2` |
| Self-test output | 86-case directed mutation oracle | `1586d038f3759dc6e695c377be5983975ab59ce36a3c9edd7b7d8428be0d588d` |
| Source commit | Sole-parent all-add packet commit | Reported and bound by the gate; not self-embedded |
| Ordinary merge commit | Two-parent integration evidence | Reported and bound by the descendant gate; not self-embedded |

No quantitative chart is included. The audit decision depends on exact
field-to-artifact, key-to-grain, and causal-order relationships. Tables preserve
those discrete relationships; a chart would imply a magnitude or trend that
the source-only synthetic evidence does not measure.

## Scope and definitions

### In scope

This unit covers:

- an append-only v1 sampling-receipt schema;
- an exact, non-circular pre-seed contract-core digest profile;
- deterministic recomputation of seed and selection evidence;
- canonical selected/reserve manifest construction;
- exact rational probability and reciprocal-weight projection;
- canonical receipt serialization;
- confined exclusive local persistence with file and directory synchronization;
- source-manifest, diagnostic, dependency-frontier, and Git-provenance checks;
  and
- source-only synthetic positive, negative, and mutation vectors.

### Out of scope

This unit does not implement or assert:

- a real eligible-frame freeze or frame custodian;
- external entropy acquisition, unpredictability, timing, or multi-party
  anti-shopping custody;
- a live runtime binding to the new writer or v1 schema;
- migration of the frozen v0 admission/map contracts to v1;
- a durable custodian receipt for the returned write outcome;
- a first-condition-output guard or any downstream side-effect interlock;
- owner policy completion, reviewer assignment, generation, scoring,
  unblinding, or portfolio decisions; or
- statistical validity, power, effect size, or BioCortex product efficacy.

### Grain and join contract

The checker treats each data surface at its declared grain before interpreting
hashes or results.

| Surface | Exact grain/key | Required integrity rule | Join into receipt |
|---|---|---|---|
| Pre-seed contract core | One canonical core per `trial_id` | Exact allowlist; no dynamic sampling/output fields | Canonical core SHA-256 equals `contract_sha256` |
| Eligible frame | One row per opaque `case_id` | Unique case IDs; exactly one admitted stratum per case | Canonical frame-manifest SHA-256 equals the receipt binding |
| Stratum allocation | One row per stratum | Unique strata; exact coverage of frame strata; `1 <= n_h <= N_h` | Canonical allocation-manifest SHA-256 equals the receipt binding |
| External entropy | One committed digest per trial sampling event | Lowercase SHA-256 commitment in the seed request | Same digest is bound in the v1 receipt and seed recomputation |
| Seed derivation | One result per contract/trial/frame/entropy tuple | Domain, message profile, inputs, and source hash are exact | Recomputed `sampling_seed_sha256` equals receipt value |
| Selected manifest | One row per selected `case_id` | Unique opaque IDs; canonical case-ID order | Manifest SHA-256 equals receipt binding |
| Reserve manifest | One row per unselected `case_id` | Unique opaque IDs; canonical stratum/rank projection | Manifest SHA-256 equals receipt binding |
| Probability rows | One row per selected `case_id` | Exact selected-key equality; reduced `n_h/N_h` | Canonical rows are embedded and selection-committed |
| Weight rows | One row per selected `case_id` | Exact selected-key equality; reduced reciprocal `N_h/n_h` | Canonical rows are embedded and selection-committed |
| Complete selection | One envelope per seed/frame/allocation tuple | Selected/reserve partition frame; all derived rows agree | Recomputed commitment equals `selection_commitment_sha256` |
| Sampling receipt | One exclusive create per custody directory and trial/contract/frame/allocation/entropy sampling event | Exact v1 fields; canonical bytes; all three boundary-verification/authority fields false | Receipt digest identifies the written bytes |
| Write outcome | One return value per attempted exclusive creation | Success only after create, content fsync, `fchmod(0400)`, seal fsync, directory fsync, and reread | Returned to caller; not persisted inside the sampling receipt |

The selected manifest, probability rows, and weight rows are deliberately three
separate representations with an exact one-to-one selected-case join. The
checker must reject missing rows, extras, duplicates, order ambiguity, and any
many-to-many expansion. The selected and reserve sets must have empty
intersection and their union must equal the eligible-frame key set.

### Terminology

- **Source candidate** means an exact committed implementation file is
  available for later review and binding. It is not a live runtime identity.
- **Live binding** means a custodian-controlled runtime or configuration has
  been bound to an exact approved artifact hash. This pack creates none.
- **Contract core** means the exact pre-seed, policy-bearing allowlist whose
  canonical bytes produce `contract_sha256`.
- **Selection commitment** means the sampling-selection algorithm's digest of
  its complete canonical result envelope except the commitment field itself.
- **Receipt digest** means the SHA-256 of the canonical v1 receipt bytes. It
  identifies content, not immutable storage.
- **Write outcome** means causally later local execution metadata returned only
  after persistence and reread complete.
- **Fail closed** means missing, unset, incompatible, noncanonical, or
  unverified evidence cannot be treated as authorization.

## Methodology

### 1. Freeze and compare existing interfaces

The analysis begins from the exact dependency graph, live-binding ledger,
real-run admission packet, v0 sampling-receipt schema, seed derivation source,
and selection source. It compares their exact required fields and confirms that
v0 cannot carry the derived seed or complete selection commitment without
violating its own schema and historical hash.

### 2. Define the append-only protocol repair

The v1 schema is validated as a new artifact. The checker verifies that v0 is
still byte-identical to its frozen source evidence and that v1 makes every new
seed/selection/provenance field required. `condition_output_authorized`,
`anti_shopping_order_verified`, and `pre_output_timing_verified` must each be
present and exactly false; omission is not treated as equivalent.

The contract-core profile is checked as an exact allowlist. Targeted mutations
show that missing, unknown, malformed, or source-hash-substituted fields are
rejected rather than silently ignored. The profile separately records that
transitive cycle checks over future policy artifacts are not yet verified.

### 3. Recompute the complete derivation chain

For each synthetic trial, the checker:

1. canonicalizes and hashes the exact contract core;
2. validates the eligible-frame and allocation grains;
3. derives the seed from contract, trial, frame, and entropy commitments;
4. runs the deterministic full-width HMAC selection;
5. reconstructs selected and reserve manifests;
6. validates exact selected-case probability/weight joins and reciprocal
   rational arithmetic;
7. recomputes the complete selection commitment; and
8. builds and schema-validates the v1 receipt.

At no point is a caller-supplied seed, selected set, reserve set, probability,
weight, or selection commitment accepted as authority without recomputation.
The writer rejects more than 16 MiB of aggregate input, more than 8 MiB for a
single artifact or receipt, more than 1 MiB for the contract core, more than
4,096 cases or 256 strata, and JSON nesting deeper than 32 levels.

### 4. Exercise exclusive persistence in an isolated synthetic root

Positive tests create a fresh private directory, write one receipt with
exclusive flags and initial mode `0600`, content-sync it, change it to `0400`,
seal-sync it, synchronize the directory, reread the bytes, and compare the exact
digest and final mode. Negative tests cover pre-existing targets,
unsafe directory descriptors, mode drift, malformed receipt requests,
canonicalization failures, concurrent creation, short writes, and injected
file- or directory-`fsync` failure.

The test result may confirm that the implementation made and checked those
local calls. It must not be reworded as proof of independent custody or of
durability against every storage, kernel, hypervisor, or hardware fault model.

### 5. Validate source identity and dependency accounting

The pack manifest binds source candidates, supporting artifacts, predecessor
evidence, and the fixture by SHA-256; the shell gate binds the exact nine-path
packet, expected diagnostic, and every in-repository checker input. Normal mode
is run from an immutable Git-blob snapshot under multiple `PYTHONHASHSEED`
values and must be byte-identical to
the checked-in expected diagnostic. Self-test mode applies directed mutations
and requires every negative case to fail for the intended reason while positive
sensitivity controls remain accepted.

The dependency graph is then re-evaluated without changing it. The result must
show that all 13 independent-public nodes have exact source candidates and that
no next public authoring frontier remains. The checker separately verifies that
the live ledger still has zero bindings introduced by this packet.

### 6. Bind Git provenance without rewriting history

The shell gate requires a clean, all-add source commit whose sole raw parent is
the frozen baseline, followed by an ordinary two-parent merge of that exact
source commit. It rejects replace refs, grafts, shallow history, path aliases,
mode drift, nondefault index flags, and worktree/index/HEAD/source-blob
divergence. Source and merge commit IDs are validated and emitted by the gate,
not embedded into the self-referential packet.

## Limitations/robustness

### Claims this pack can support

Subject to the final gate, this pack can support narrow claims that:

- the public source set contains a deterministic v1 sampling-receipt writer;
- v0 remains unchanged while v1 explicitly binds seed and selection identity;
- the source algorithm rejects circular contract inputs and recomputes derived
  sampling evidence;
- the local write path uses exclusive creation, restrictive mode, file and
  directory synchronization, and exact reread; and
- the graph-derived public source frontier is empty after 13 of 13 source
  candidates are present.

### Claims this pack cannot support

It cannot support claims that:

- any real eligible frame, entropy source, seed, sample, or receipt exists;
- entropy was unpredictable, unbiased, singular, or unavailable before frame
  freeze;
- a custodian independently observed the write or preserved the returned
  outcome;
- a production output path checks `condition_output_authorized=false`;
- the host Python interpreter or standard-library binaries have approved live
  runtime provenance;
- the frozen v0 admission/map surfaces accept v1;
- any unset live binding or owner-policy field has been filled; or
- BioCortex has demonstrated a product, memory, statistical, or biological
  effect.

### Robustness boundaries

Canonical serialization, exact schemas, full-set joins, deterministic seed and
selection recomputation, and exclusive-create/read-only-snapshot controls reduce
ambiguity and accidental substitution. They do not defend against a privileged
attacker who
can subvert the process, kernel, filesystem, source checkout, or custodian.

`O_EXCL` prevents a normal overwrite race at the target name; it does not by
itself prove safe parent-directory custody on every filesystem. Initial mode
`0600` does not provide cryptographic confidentiality, and final mode `0400`
does not prevent the same euid from changing permissions or later mutating the
file. `fsync` return success is a local durability signal, not proof against all
device/controller failure. The exact reread detects immediate path divergence
but is not long-term retention evidence.

The returned write outcome is intentionally not persisted by this writer.
Without a separate later custodian artifact, a caller could discard or
misreport it. Likewise, `condition_output_authorized=false` is a receipt field,
not an enforcement mechanism; a distinct output guard must consume and enforce
it.

The controlled dependency resolver rejects imports outside the exact allowlist
and the test matrix includes both an RFC 4231 HMAC-SHA-256 vector and an ambient
fake-`hmac` substitution. This is source-level isolation after the writer module
has initialized; it is not provenance for the host Python interpreter,
standard-library binaries, or a process already compromised before import.

The v1 schema and writer are intentionally incompatible with frozen v0
admission/map contracts. This incompatibility is a safety boundary, not a
successful migration. Until a separately reviewed successor admission/map
contract binds v1 and all owner/custody values, the real run remains blocked.

Synthetic vectors establish deterministic source behavior only within the
tested domain. They cover 86 directed cases; the fixed expected-output and
self-test hashes above bind those results. Git identities remain a separate
post-commit gate result and do not expand the scientific claim.

The checker binds the configured size/count/depth constants and directly tests
aggregate-size and nesting-depth rejection. It does not exercise every cap at
its maximum or include a peak-memory or worst-case CPU benchmark at the 16 MiB
aggregate limit. The caps therefore bound accepted input shapes; they do not
establish a production memory budget or denial-of-service resistance.

## Next steps

1. Run normal, self-test, resource, schema, source-identity, dependency, and Git
   gates from immutable Git blobs under the required environment variants.
2. Obtain independent security, data-quality, and Git-provenance review of the
   final packet before creating the source commit.
3. Create the sole-parent all-add source commit, integrate it through an
   ordinary two-parent merge, rerun descendant validation, and push only after
   all gates pass.
4. Design a successor admission/map version that explicitly binds the v1
   schema and writer without modifying frozen v0 evidence.
5. Implement an independent custodian receipt that commits the causally later
   write outcome, frame/entropy timing, and relevant filesystem identity.
6. Implement and test a first-condition-output guard that requires a valid,
   custodian-bound v1 sampling receipt and refuses every false, missing, stale,
   or incompatible authorization state.
7. Only after those controls and all owner policy/live bindings are complete,
   consider a synthetic end-to-end rehearsal; do not infer real-run admission
   from source completeness.

## Further questions

- What exact successor version and migration rule should replace the frozen v0
  admission/map interface while preserving historical replay?
- Which independent party or mechanism will acquire and attest external
  entropy, and how will candidate-value shopping be made observable?
- What causally later artifact should bind the returned write outcome without
  creating a digest cycle with the already written receipt?
- Which filesystem identity, mount, host, clock, process, and binary evidence
  must the custodian receipt include for the intended threat model?
- Where should the first-condition-output guard run, and what prevents an
  alternate generation path from bypassing it?
- Should a successor contract require one sampling receipt per trial, per
  sampling attempt, or per frozen frame revision, and how are aborted
  attempts represented without allowing retries to become seed shopping?
- How will the owner freeze the remaining policy fields before entropy is
  available, and which exact fields belong in the contract-core allowlist?
- What independent replay environment will verify the receipt, seed,
  selection, and manifest commitments before reviewer packet construction?
- Which later estimator will consume case-grain weights exactly once, and what
  join gate will prevent accidental double weighting or post-selection case
  loss?
