# BioCortex / AB Track B real-run admission v0

Date: 2026-07-13

Status: **public fail-closed preregistration + synthetic arithmetic checker only; real run blocked**

Parent source baseline: `533ab2607825d877278edd6548e897f93c2acf19`

## Decision

Do not start a real Track B capture, generation, review, unblinding, or score.

Track B remains the priority measurement lane, but its next executable unit is
an admission/hardening slice rather than a benchmark. The public contract finds
two independent critical paths:

1. the proposed full-hybrid reference is not yet an exact, deterministic
   reference;
2. Temporal Truth Projection v0 is a deterministic pure resolver, but the
   current mutable SQLite store cannot provide admissible resolver evidence.

The contract therefore records `BLOCKED_FAIL_CLOSED`,
`NO_GO_EXACT_REFERENCE_BINDING`, and `BLOCKED_DATA_MODEL` simultaneously. A
public checker PASS means only that these boundaries, declared schemas and
synthetic schedule/latency/context/hardware/storage arithmetic are internally
consistent and tamper-sensitive. It is not a retrieval run, a BioCortex result,
or scientific/runtime authority.

## Evidence-quality decision

The governing distinction is **available evidence versus admissible evidence**.

| Surface | Available now | Admissible for a new confirmatory run | Decision |
|---|---:|---:|---|
| full-hybrid search implementation | yes | no | code identity can be bound, but clock, environment, tie order, budget, binary and snapshot cannot yet be bound exactly |
| successor-v3 capture/blind/review machinery | yes | mechanism only | reuse validation order and custody ideas; do not reuse its 12 cases, map, score claim, reviewer identities or result |
| Temporal Truth Projection v0 pure resolver | yes | resolver only | deterministic code does not create the missing store evidence |
| `MutableSqliteV41` truth-adapter producer profile | yes | no | the conservative profile label (not a current schema-version attestation) has eight minimum static completeness gaps and must report `adapter_allowed=false` |
| old v3 latency/context observations | yes | no | single request timings and heuristic tokens do not satisfy fixed-hardware repeated retrieval+assembly measurement |
| SQLite allocated-byte counters/export paths | yes | no | they omit a frozen canonical denominator and complete persistent-artifact manifest |

The intended analytical grain is frozen before data exists:

- retrieval: `case_id × condition`;
- review: `trial_id × reviewer_slot × case_id × opaque_answer_id`;
- latency: `case_id × condition × repetition`;
- storage: `canonical_package × condition`;
- primary statistical unit: one case, never an answer, claim, or reviewer row.

Required data-quality checks cover key uniqueness, field validity, relational
integrity, timeliness/frozen `as_of`, leakage and consumed-case exclusion,
intention-to-treat missingness, and source lineage/hash binding.

## Why the reference is not exact yet

The proposed invariant request profile (with each future case/query supplied by
the frozen selected-case manifest) is now explicit:

```json
{
  "tool": "memory_search",
  "mode": "hybrid",
  "compact": false,
  "limit": 10,
  "tags_any": [],
  "exclude_kinds": ["skill"],
  "scope": null,
  "scope_mode": "local_only",
  "include_global": false,
  "expand_top": 10,
  "rrf_k": 60.0
}
```

That request is necessary but insufficient:

1. FTS recency and TTL suppression consult wall clock time. There is no frozen
   `as_of` injection through the current search path.
2. The old trial client copies its parent environment. Ranking can therefore
   depend on machine exclusions, class quota, coactivation policy, correction
   co-surfacing, or an auto-discovered Path-C sidecar.
3. Equal-score ordering is not proven deterministic through every FTS, graph,
   RRF and rerank collection/sort boundary.
4. `top_k=10` is not a full budget. With the proposed exclusion it implies an
   MCP pool of 50, a store FTS pool of 200 and a raw FTS scan cap of 800; graph
   expansion uses up to 10 available FTS seeds and neighbor fan-out remains
   unbounded.
5. Graph-only expansion calls exact record reads that can update access time
   and count. The legacy context projection drops only `key`, so those volatile
   fields can enter generated context.
6. There is no hard per-case result-byte/token cap or exact frozen tokenizer.
7. The current source commit is not a runtime identity. The run still needs a
   matching binary SHA/features, SQLite runtime version, verified closed
   snapshot and effective-config hash.

The current deployed source observation is older than this source baseline and
is not adopted as the formal reference. The consumed v3 binary and snapshot
remain mechanism precedent only.

## Why the truth candidate is blocked

`crates/bridge/src/memory_truth.rs` is a deterministic, read-only pure resolver.
Its existence does not make current memory rows truth evidence.

`crates/bridge/src/memory_truth_adapter.rs` binds the current producer profile
to a fail-closed preflight. Before any dynamic truncation, dangling endpoint or
tombstone-redaction gap is observed, mutable SQLite v41 already lacks:

1. complete immutable lineage revision history;
2. unique lineage revision order;
3. complete tombstone/governance index;
4. all relationship channels and history;
5. provable relationship endpoint closure;
6. durable content-free governance attestations;
7. explicit claim/time/source-provenance bindings;
8. predicate-scoped truth authority policy.

A live snapshot may add more gaps. It cannot remove these eight static producer
gaps. Caller-supplied booleans, backfilled current rows, or a synthetic
all-true profile are not an admission path.

`MutableSqliteV41` is the adapter's conservative implementation-profile label;
it must not be read as proof that the live database currently has schema
version 41. Runtime SQLite and `schema_meta` identities remain separate unset
bindings.

The real candidate consequently remains:

```text
Temporal Truth Projection v0
  + future reviewed store adapter
  + append-only evidence/governance substrate
  + frozen current-authority policy
```

There is no candidate context-builder hash yet, and no current store record is
sent to the resolver by this packet.

## Confirmatory prevalence contract

The old 12 successor-v3 cases were curated, consumed and already scored. They
are not a population sample or power pilot for this run.

The sole confirmatory population is a fresh untouched prevalence holdout. Its
observation unit is one real query episode before condition assignment. Before
any condition output, a future contract must bind:

- target-population definition and UTC frame window;
- immutable raw and eligible frame manifests plus frame-builder hash;
- inclusion, exclusion, replay-deduplication and dependence-cluster rules;
- per-stratum `N_h`, selected `n_h`, inclusion probability and
  `w_i = N_h / n_h` where allocation is not self-weighting;
- an O_EXCL frame receipt followed by an external unpredictable beacon or
  multi-party commit/reveal, domain-separated seed derivation and deterministic
  HMAC selection; no single party may choose among candidate seeds;
- primary and reserve manifests plus an atomic single-use sampling receipt that
  binds trial/contract, algorithm/domain/message, schema/writer/time, frame,
  inclusion probabilities, exact rational weights and ordering;
- a disjoint pilot or conservative power assumption, paired method, target
  power and final primary case count;
- a frozen truth `as_of` and authority/claim manifest.

The challenge stratum contains 4–6 known hard cases and is diagnostic only. It
may not enter the confirmatory estimate. Replayed/imported copies of the same
upstream event are deduplicated; similar questions from distinct real episodes
remain prevalence observations and receive a dependence-cluster id rather than
post-outcome deletion.

Once any selected case produces a condition output, intention-to-treat starts.
A timeout, missing answer or missing review cannot be silently dropped or
replaced from reserve.

The admission sequence is explicitly staged; artifacts that do not exist yet
are not falsely required before the first output:

1. `PRE_OUTPUT_ADMISSION` binds reference/candidate truth, frame/sampling/power,
   the atomic sampling receipt, generator/condition/reviewer rosters, seed
   commitments, hardware/tokenizer/storage protocols, binary and snapshot.
2. `POST_GENERATION_PRE_REVIEW` binds capture, generation, blind packet, private
   map and map-bijection receipt before a fixed blind reviewer is invoked.
3. `PRE_UNBLIND` validates both complete command/request/raw-response/review/
   receipt chains and atomically creates the contract-scoped single-use score
   claim before the first condition-map read.

## Primary outcome and review

For each condition, each answerable case passes only when:

- authoritative evidence exists;
- every gold evidence item is recalled;
- current version and referent are correct;
- every required claim receives full support;
- currentness is `pass`;
- response mode is correct and usefulness is at least 4/5;
- forbidden/stale and unsupported factual-assertion counts are both zero.

An unanswerable case requires a correct abstention with no smuggled claim.
Authority existence, all-gold recall and current-referent correctness come from
deterministic retrieval/truth manifests. Required-claim support, currentness,
response mode, abstention, forbidden/stale count, unsupported count and
usefulness are emitted independently by each frozen reviewer schema. The two
reviewer slots are combined by logical AND at case grain. Reviewer rows are not
extra statistical samples, and reviewer means cannot rescue a failed case.
Sampling weight is applied once after this reviewer AND.

The truth/authority/gold manifest, referent schema, review schema, strict-case
algorithm and provenance checker are pre-output hash bindings. A capture
timeout/error or generation failure is a terminal protocol failure with no
replacement. A missing/invalid review is terminal with no replacement and no
unblinding; it is never converted into a conveniently complete scored sample.

The prevalence gate remains a minimum point lift of `0.05` plus a one-sided 95%
paired case-level lower confidence bound above zero. Challenge results are
descriptive. The required primary prevalence count is the larger of 24 and the
power-derived count, explicitly excluding diagnostic challenge cases. No final
primary sample count is set without a disjoint power and cluster-variance
contract.

A future reviewer roster must rebind provider, model, reasoning effort, CLI and
version, normalized command profile, instruction hash, workspace/session
provenance and overlap/conflict disclosures. The old roster is not assumed
current. The future order is:

```text
validate both complete blind-review receipts
  -> atomically create a contract-scoped single-use score claim
  -> first read of condition-labelled generation and private map
```

The map and both sampling/blinding secrets are trial-specific and private.

## Latency, context and storage protocols

The protocol shape and its public synthetic arithmetic are frozen while all real
identities remain unset.

Latency unit: `(case, condition, repetition)`. Warm pre-touch/query work runs on
a sacrificial process and clone that is then discarded. Each timed unit starts a
fresh process and a pristine clone whose SHA must equal the shared base; this
accepts process-internal cold state rather than letting a writeful warmup mutate
the timed starting database. Snapshot clone and process startup are excluded.
The `perf_counter_ns` monotonic timer starts immediately before the first timed
MCP call and ends only after the final context has been assembled, validated
and measured as exact UTF-8 bytes. Thus wire parsing, all search/get calls and
context projection are inside primary latency; artifact hashing and output
writes are outside.

There are exactly six measured repetitions per case/condition. Two independent
HMAC domains use the same committed latency seed: one globally orders all
case×repetition pairs, while the other ranks repetitions within each case and
assigns exactly three reference-first and three candidate-first. Execution order
is therefore interleaved independently of condition assignment, with exact
per-case and survey-weighted AB/BA balance. Any non-OK or timeout unit blocks the
run with no drop or imputation. The receipt array itself must be in ordinal
execution order; editable ordinal labels alone are insufficient.

For prevalence p95, each case's exact rational survey weight is divided equally
across its six
repetitions. Integer-nanosecond observations are sorted and the p95 is the first
observed value whose cumulative weight reaches 95% of total weight, with no
interpolation:

```text
first latency where cumulative(w_i / 6) >= 0.95 * sum(w_i)
```

Candidate/reference p95 must be at most `1.25`. Per-case latency remains a
diagnostic. The hardware manifest schema binds host slot, OS/kernel/
architecture, CPU vendor/model/core/SMT shape, memory, governor, filesystem,
runtime, affinity and thread environment without hostname or serial numbers.
A separately hashed guard policy fixes acceptable pre/post load, swap, governor
and thermal-throttle observations before results exist. Pre/post guards bind the
same boot-session hash; a thermal counter decrease is a reset and fails closed.
Physical cores may not exceed logical cores, and a non-SMT profile must report
equal physical/logical counts.

`result_bytes` is the exact final context delivered to the generator, not the
JSON-RPC envelope or raw hits. Tokens must be recomputed with a frozen offline
tokenizer whose implementation and model hashes are bound. Candidate bytes and
tokens may not exceed the reference on any paired case; token ratio is at most
`1.00`.

For storage, both arms are rebuilt from the same deterministic LF UTF-8 private
package, `memories.jsonl + edges.jsonl`, with serializer hash, individual file
hash/bytes and row/edge counts. The denominator is the sum of exact uncompressed
source bytes. The numerator is named `total_persistent_condition_bytes`: closed
main SQLite bytes plus every condition-specific persistent artifact in the
complete manifest. Per arm, the checker requires builder/package identity,
main size, page size/count, freelist, SQLite runtime, `user_version`,
`schema_meta` version, schema digest, quick-check, artifact role/hash/size and
exact total. SQLite page size is restricted to its valid 512–65536 power-of-two
domain, and runtime/page size must match across arms. Canonical source
serialization, memory order and edge order are also explicit. Artifact roles
are allowlisted; WAL/SHM/rollback journal and unlisted artifacts are forbidden.
A real runner must hash the actual JSONL/SQLite files and reconcile a closed
directory scan against the exact manifest.
Integer cross multiplication enforces the
candidate/reference normalized ratio at `1.10` without float rounding.

The checked-in public synthetic fixture contains 24 independently interleaved,
per-case-balanced case/repetition pairs (48 condition units), exact `4/3`
rational weights, invariant multibyte UTF-8 public contexts, a passing
boot-continuous hardware guard and two complete synthetic storage manifests. Its
latencies and bytes are invented solely to execute the validator. It does not
open Agent-Bridge, SQLite, a model, a private frame or a benchmark.

## Ordered implementation path

The smallest safe sequence is:

1. **Reference determinism S0:** add an injected frozen clock/as-of, stable
   score tie-breaks, a bounded graph fan-out and hard result/context budgets;
   implement a clean-environment runner and stable context projection that
   excludes access telemetry.
2. **Reference admission fixture:** exercise ordinary FTS, graph-only access
   mutation, excluded skill, equal-score ties, TTL boundary and sidecar/
   coactivation order changes across repeated fresh clones.
3. **Evidence substrate design:** preregister an append-only revision ledger,
   permanent content-free governance ledger, explicit claim/time/provenance and
   predicate-authority bindings. This is a separate schema/migration review.
4. **Store adapter:** admit only producer-bound complete snapshots; keep legacy
   rows unqualified unless a separate admission process succeeds.
5. **Fresh prevalence admission:** bind frame, power, reviewer, blind-map,
   hardware, tokenizer, snapshot, binary and storage manifests. Only then may
   the first real condition output be produced, and not before 2026-07-17.

This order hardens AB memory measurement independently of BioCortex and creates
the only honest path by which BioCortex-derived truth projection can later be
evaluated. It grants BioCortex no current retrieval, write, ranking or runtime
influence.

## Public verification

Run from a clean committed worktree:

```bash
./scripts/check-biocortex-ab-track-b-admission.sh
```

The direct executable path is the attested path. The shell gate clears inherited
shell/Python/Git state, checks the exact six-file source packet, runs the checker
twice, compares the fixed receipt and requires all 128 contract/arithmetic
adversarial mutations to be rejected. Mutations cover stage order, seed/map/
review rules, anti-shopping and self-contained sampling receipt bindings,
fractional frame weights, nested type confusion, missing/duplicate units,
fully rebound blocked HMAC schedules, execution-array order, timeouts, context
bytes/hash/tokens/invariance, weighted p95, pristine timed snapshot, multibyte
UTF-8, boot/thermal/core guards, canonical denominator, SQLite page/runtime
accounting, disguised sidecars/artifacts and the 1.10 storage boundary. The gate does not launch
Cargo, Rust, Agent-Bridge, a database, a model, or a benchmark.

The public contract is
`scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json`.
The public arithmetic fixture is
`scripts/eval/fixtures/biocortex_ab_track_b_admission_synthetic_v0.json`.
The fixed expected receipt is
`scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission.expected.v0.tsv`.

## Non-authority boundary

Nothing in this packet authorizes a real corpus/frame read, condition capture,
LLM generation, model review, unblinding, score, database write, Agent-Bridge
retrieval execution, BioCortex influence, production integration, deployment,
promotion or scientific/application claim.
