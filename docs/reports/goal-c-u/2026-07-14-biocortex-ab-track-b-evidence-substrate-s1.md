# BioCortex / Agent-Bridge Track B Evidence Substrate S1

Date: 2026-07-14

Status: **design and synthetic checker PASS; separate migration review is next;
adapter and real capture remain blocked**

## Outcome

Track B ordered-path item 3 now has an executable, Agent-Bridge-owned evidence
substrate design packet. It freezes five logical append-only ledgers, dual-clock
and resolver-v0 compatibility, relationship carry-forward, permanent
content-free tombstone/governance attestations, latest-visible
predicate/source authority, and six fixed complete-snapshot maxima.

This is not an implementation of those ledgers. No SQLite schema, writer,
reader, adapter, projector, MCP surface, BioCortex runtime path, or legacy-row
qualification was added.

## Bound artifacts

- Design:
  `docs/design/MEMORY_TEMPORAL_EVIDENCE_SUBSTRATE_S1_2026_07_14.md`
- Design SHA-256:
  `e4425eabc6eb801525cfc98fb70ce70f45d1a814d93e00e74006650052284a63`
- Contract:
  `scripts/eval/fixtures/memory_temporal_evidence_substrate_s1_contract_v0.json`
- Contract SHA-256:
  `67f05ef574960a0d46db9313b7c8a498c41531c22d6d546f7741617a0c250fe5`
- Synthetic fixture:
  `scripts/eval/fixtures/memory_temporal_evidence_substrate_s1_synthetic_v0.json`
- Fixture SHA-256:
  `fea71602105364ca41df936d04981c6238fb9955ed69d8de9e0256a08c679a6a`
- Checker: `scripts/eval/check_memory_temporal_evidence_substrate_s1.py`
- Checker SHA-256:
  `6137281fd2920cb09467d2c93d462a0bd515ad35d81625e86875c45dd15be13c`
- Expected receipt:
  `scripts/eval/fixtures/memory_temporal_evidence_substrate_s1.expected.v0.tsv`
- Expected receipt SHA-256:
  `56fa48154222c55547af34734749a91a9c927c47280867a8b059bbc41f0fa233`
- Clean-HEAD gate: `scripts/check-memory-temporal-evidence-substrate-s1.sh`
- Gate SHA-256:
  `6094054796c6181d3048f4fef21b50072e512f1ebcf78e2ccca9bdc78ba06cae`

The gate emits the current committed `HEAD`; this tracked report does not embed
a self-referential fixed commit id.

## Synthetic evidence

The fixture contains 9 claim lineages, 5 authority-policy revisions, 10
evidence revisions, 4 relationships, and 2 content-free tombstones. The
canonical snapshot payload is 9,566 bytes with SHA-256
`a69fe303e42cf43a644195fa3e7a845e36303034d6014219455485335fbe812d`.

It exercises:

- two revisions and a carried-forward supersession relationship;
- explicit `observed_at` and `recorded_at`, including a late backfill excluded
  by the frozen knowledge cutoff;
- three predicates for one referent;
- inclusive supersession at its exact effective-time boundary;
- same-tier conflict and a lower policy-derived tier;
- latest-visible policy selection with revocation, strict policy-time, and
  predicate/source anti-shopping controls;
- relationship-tier comparison at the declaring source's knowledge time,
  including later-target-downgrade and same-second-ambiguity negative controls;
- inbound relationship pruning for a tombstoned target;
- fail-closed handling of a tombstoned source that had outgoing governance;
- exact counts, fixed hard caps, closure, canonical order, and payload digest.

The checker then rebuilds and rejects 36 adversarial mutations. These include
revision gaps/duplicates/same-time ambiguity; primary-key, foreign-key, and
store-derived-field drift; claim and relationship malformation; policy
revocation bypass, time regression, tier shopping, later-target downgrade, and
same-second target ambiguity; authority laundering; missing provenance;
governance/tombstone leakage;
unbounded caps, truncation, endpoint non-closure, digest/order drift, duplicate
evidence ids, unknown fields, and duplicate JSON keys.

This PASS concerns only internal design consistency and tamper-sensitive
synthetic controls. It is not evidence that any ledger, cap enforcement,
authority resolver, migration, snapshot reader, or adapter exists at runtime.

The direct deterministic receipt is:

```text
schema	agent_bridge.memory_temporal_evidence_substrate_design_receipt.v0
design_status	READY_FOR_SEPARATE_MIGRATION_REVIEW
fixture_only	true
contract_valid	true
synthetic_fixture_valid	true
negative_cases_rejected	36
lineages	9
policy_revisions	5
evidence_revisions	10
relationships	4
tombstones	2
append_only_revision_model	true
revision_sequence_and_v0_time_unique	true
dual_clock_bound	true
relationship_history_complete	true
governance_attestation_permanent	true
predicate_authority_default_deny	true
snapshot_complete_and_bounded	true
schema_migration_present	false
runtime_writer_present	false
store_adapter_present	false
projector_invoked	false
legacy_rows_qualified	false
adapter_allowed	false
real_capture_authorized	false
biocortex_runtime_influence	false
sentinels_cleared	true
decision	BLOCKED_FAIL_CLOSED
```

## Verification boundary

After commit, run:

```bash
./scripts/check-memory-temporal-evidence-substrate-s1.sh
```

The gate materializes all seven packet members, including the design and this
report, from immutable `HEAD` blobs; verifies the report's artifact hashes;
starts absolute Bash under an empty environment before shell startup, sanitizes
each checker invocation with shell builtins, runs the checker twice, compares
both byte streams to the fixed TSV, and fences `HEAD`, index, and worktree
drift. It runs only standard-library Python and does not start Cargo, SQLite,
Agent-Bridge, BioCortex, a model, or a benchmark.

## Admission decision

`READY_FOR_SEPARATE_MIGRATION_REVIEW` means the schema questions and negative
controls are preregistered. It does not mean the schema exists or that an
adapter is allowed. The current mutable profile continues to have its eight
static preflight gaps, and the old Track B v0 packet remains unchanged and
source-drift blocked.

The next ordered item is S2: review and, only after that review, implement an
additive synthetic-only migration with internal append/tombstone transactions
and a complete snapshot reader. Physical privacy deletion, exact producer
identity, same-second resolver semantics, and authority-policy custody must be
resolved or explicitly fail closed in that review. S3 can then consider a
producer-bound store adapter; a new Track B admission packet comes later.
