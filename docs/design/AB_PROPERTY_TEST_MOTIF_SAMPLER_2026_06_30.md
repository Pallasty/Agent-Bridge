# Agent-Bridge Property-Test Motif Sampler

Date: 2026-06-30
Status: design memo, no code or runtime change

## Decision

Agent-Bridge should borrow only test motifs from the TCT/TCF/TTE idea archives:
conservation, stability, round-trip consistency, operator consistency,
regression gates, and negative controls. These motifs must be translated into
Agent-Bridge's existing engineering language: fixtures, invariants, redaction
contracts, deterministic replay, bounded gates, no-authority checks, and
fail-closed review surfaces.

This memo does not import archive code, add tests, register tools, write memory
or graph edges, change retrieval order, or inspect raw archive outputs. It
captures reusable test shapes for future AB lanes.

## Source Anchors

This sampler uses the sanitized portfolio boundary and existing AB tests/docs:

- `CASCADE_PORTFOLIO_IDEA_ARCHIVE_READONLY_2026_06_29.md`
- `AB_SANITIZED_MEMORY_VOCABULARY_AUDIT_2026_06_29.md`
- `AB_PROJECTION_BUILDER_PATTERN_AUDIT_2026_06_30.md`
- `BIOCORTEX_COMPOSED_LIMIT_CYCLE_CONSUMER_DRY_RUN_2026_06_29.md`
- `MEMORY_CONTINUITY_T5_T6_EVIDENCE_SURFACES_2026_06_19.md`
- `INT8_EMBEDDING_COLUMN_SHADOW_PROPOSAL_2026_06_28.md`
- `crates/memory-columnar/src/lib.rs`
- `crates/store/src/quant.rs`
- `crates/store/src/connectivity_repair.rs`
- `crates/store/src/lineage_audit.rs`
- `crates/bridge/tests/biocortex_capability_ledger_display_packet.rs`
- `crates/bridge/tests/lswr_readonly_bridge_display_model.rs`

No raw TCT/TCF/TTE files are re-read here. The archive contribution is only the
sanitized portfolio prompt: look for conservation, stability, fusion/operator
consistency, and backend-selection motifs.

## Motif Catalog

| Motif | AB translation | Existing examples | Good future use |
|---|---|---|---|
| Round-trip consistency | encode/decode, write/read, serialize/deserialize, or packet/display round-trip preserves fields | memory-columnar Parquet round-trip; INT8 code blob round-trip; stable pretty JSON fixtures | Any new storage, packet, export, or display payload |
| Byte-exact identity | canonical bytes survive transport, including edge numeric cases | memory-columnar fingerprint with NaN and signed zero; INT8 sign endpoints | Cross-machine sync, snapshot hashes, replay fixtures |
| Schema contract rejection | future/mismatched contract fails closed | memory-columnar footer contract mismatch; LSWR display matrix/packet mismatch | Versioned packet and archive readers |
| Determinism | same input yields same output across runs and input order | quant recall gate determinism; connectivity repair input-order independence; lineage duplicate-id canonicalization | Any dry-run planner, repair proposal, or sampler |
| Empty/degenerate safety | small, empty, missing, or no-mainland input returns safe no-op output | empty Parquet round-trip; quant degenerate corpus vacuous pass; empty graph safe | Tools that may run on fresh, partial, or filtered state |
| Negative control flip | changing one forbidden field forces rejection | BioCortex ledger `executor_enabled=true`; display model mutating safety flag; LSWR action affordance | Any report/display/gate claiming read-only safety |
| Redaction no-leak | output proves raw query/key/content/case rows are absent | T5/T6 redacted evidence surfaces and review packet chain | Memory, retrieval, BioCortex, and forum-facing summaries |
| Regression gate | a measured threshold blocks promotion without authorizing runtime | INT8 recall-regression gate; BioCortex lift/headroom fixtures | Any optimization that could alter ranking, storage, or candidate sets |
| Conservation/leak check | every effect has provenance; dangling references are surfaced as leaks | lineage audit conservation-leak checks | Event spine, outcome ingestion, sync, graph materialization |
| Boundedness/cap | output remains capped, ordered, and reviewable | connectivity repair max candidates; lineage max findings; T6 bounded candidate delta | Any planner that emits actions, edges, candidates, or alerts |
| Accepted/rejected fixture pair | happy path and explicit failed path are both stable | BioCortex capability ledger, C1 composed-limit-cycle, LSWR display model | Any new consumer or display model |
| No-authority invariant | readiness to show or review never becomes authority to execute | projection/display docs; memory authorization contracts; T6 gates | Every review packet, report, or shadow eval |

## Archive Motif Translation

Use these translations when future work mentions TCT/TCF/TTE-style language:

| Archive-style idea | Agent-Bridge test shape |
|---|---|
| conservation | No unprovenanced effects, no dangling parents, no hidden writes, stable counts before/after dry-run |
| stability | Deterministic output across repeated runs, input order, host-independent fixtures, and fixed seeds |
| fusion | Combined evidence preserves each input schema, safety flag, caveat, and rejection reason |
| operator consistency | Applying an inverse or paired operation restores the same canonical payload or detects loss |
| interference | A targeted negative control must disrupt the claimed signal or force a blocked verdict |
| backend selection | Multiple backends preserve the same public contract, or fallback is explicit and detectable |
| entropy/energy budget | Candidate/action output is capped, monotonic where promised, and cannot grow without bounds |
| persistent homology/topology | Graph claims are tested through component/orphan/bridge invariants, not mystical topology words |

## Adoption Rules

1. Start with a named invariant before writing a test.
2. Prefer table-driven fixtures for safety and contract checks.
3. Prefer small deterministic generated corpora for numeric regression gates.
4. Use property-style randomized tests only when a broad input space is the
   actual risk and the test can use a fixed seed or deterministic shrink path.
5. Every accepted fixture should have at least one rejected sibling fixture or
   targeted tamper case.
6. Every read-only or redacted surface should test the forbidden words or fields
   that would accidentally grant authority or leak raw data.
7. Every optimization that changes storage, ranking, candidate sets, or graph
   proposals needs a no-regression gate plus a no-harm counterexample.
8. Every planner that emits more than one action needs caps, ordering rules, and
   deterministic tie-break tests.
9. Empty, missing, tiny, and malformed inputs are first-class cases.
10. Passing a property test can approve a review packet or next experiment; it
    does not approve runtime mutation.

## When To Add Code

Do not add new Rust tests from this memo alone. Add code only when a concrete
consumer appears and one of these is true:

- a new packet/storage format needs a stable fixture or round-trip lock;
- a read-only surface claims redaction, no writes, or no runtime authority;
- a planner proposes candidates, graph edges, actions, or merges;
- a ranking/storage optimization needs a regression gate;
- an imported idea is about to influence AB design and needs a falsifier.

The first implementation should usually be a focused unit test or fixture smoke,
not a broad fuzz harness. Add a reusable helper only after at least three lanes
repeat the same mechanics.

## Anti-Patterns

Do not:

- import TCT/TCF/TTE test code or generated outputs;
- fuzz live Agent-Bridge state or live memory databases by default;
- use random tests without a deterministic replay handle;
- treat metric improvement as runtime authorization;
- accept only a golden happy path without a negative control;
- hide rejected cases from display/report surfaces;
- let a projection, review packet, or fixture write memory, graph edges, or
  approval records;
- describe topology, energy, entropy, resonance, or evolution as capability
  evidence without a concrete AB invariant.

## Suggested Future Small Lanes

1. Add a negative-control checklist section to future display-model docs.
2. If a concrete candidate appears, add a tiny fixture-backed test that flips
   one forbidden authority field and proves the display/review surface rejects.
3. For any future graph materialization or sync change, start with
   conservation/leak and deterministic-order tests before adding a writer.
4. For any future ranking or embedding-storage change, require a deterministic
   no-regression fixture and a targeted counterexample.

## Non-Claims

This memo does not:

- add a test, fixture, fuzz target, or helper library;
- run BioCortex, LSWR, TCT, TCF, or TTE code;
- read raw archive trees;
- create an MCP tool or profile change;
- write memories, graph edges, audit rows, or approval records;
- change retrieval, bootstrap, candidate expansion, or ranking;
- approve runtime influence or executor enablement.

It only turns the portfolio's property-test idea into an Agent-Bridge review
and test-design vocabulary.
