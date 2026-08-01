# ADR: CLI composition-root governance S5-V BioCortex effectful-executor audit

## Status

Accepted on 2026-07-31.

- Decision scope: `crates/bridge/src/main.rs`
- Audited base: `b0fe0e13164111b86c84f8dd31ca5c3a9fa679af`
- Coordination: Agent-Bridge forum thread #295, intent post #5784
- Predecessor: S5-U store-trial renderer extraction
- Implementation posture: audit and freeze only; no Rust production movement

## Context

S5-A through S5-U established a private `cli::biocortex` presentation boundary
without moving Store, file-input, subprocess, retrieval-order, or runtime
authority out of the CLI composition root. At the audited base, `main.rs` has
fallen from 21,700 lines at S0 to 19,274 lines and contains 86 top-level
`run_*` functions. Eight BioCortex executors remain:

1. `run_biocortex_replay_compare`;
2. `run_biocortex_retrieval_opt_in_runtime_trial`;
3. `run_biocortex_retrieval_opt_in_store_trial`;
4. `run_biocortex_retrieval_opt_in_gated_store_trial`;
5. `run_biocortex_retrieval_opt_in_batch_diagnostics`;
6. `run_biocortex_retrieval_opt_in_gated_batch_diagnostics`;
7. `run_biocortex_retrieval_opt_in_controlled_order_fixture`;
8. feature-gated `run_biocortex_retrieval_shadow`.

These wrappers span 711 lines at the audited base. They are not one cohesive
presentation family: they select live versus fixture input, open SQLite,
consume authorization packets and current environment gates, call baseline
`memory_search`, execute an external checkout, write caller-selected files,
or seed a caller-selected non-production store. Moving them together would
hide rather than clarify the effect boundary.

Six wrappers still have JSON/text presentation tails in `main.rs`. Those tails
total 277 lines, about 1.4% of the current composition root. `git blame` at the
audited base attributes each tail to only one or two commits. There is no
current evidence that these presentation blocks are a recurring merge or
behavioral hotspot.

## Effect and authority matrix

`Store open` is classified as an effect even when the later business query is
read-only: `SqliteStore::open` may create a parent directory/database, enable
WAL, create schema, and run migrations. `External` includes temporary corpus
or projection files and `cargo run --offline` against a local BioCortex
checkout.

| Executor and base lines | Input and direct effects | Store/external behavior | Retrieval and authority posture | Decision |
| --- | --- | --- | --- | --- |
| Replay compare, `11488-11581` | Reads `fixture_in`, or selects the default DB; optionally writes `fixture_out` | Opens Store and collects a live fixture when no input fixture is supplied; always permits an external comparison run | No AB memory mutation or retrieval-order change, but it owns Store/file/process custody and has no opt-in retrieval kill switch | Retain the complete executor in `main.rs` |
| Runtime trial, `11594-11695` | Reads execution packet plus `input_json` or `candidates_json`; preserves input precedence and exact errors | No Store; after feature/runtime/per-call/kill-switch preflight it writes a temporary corpus and may run the external side signal | Always returns baseline order; no `memory_search`, approval write, or ordering connection | Retain executor; renderer is conditional-only |
| Store trial, `11697-11725` | Reads decision packet; resolves `AGENT_BRIDGE_DB` or default path; opens SQLite | Runs baseline `memory_search`, may run external side signal, then calls the protected Store wrapper | May change only the current explicitly opted-in FTS result when all decision, runtime, coverage, and operator gates pass; defaults remain unchanged | Freeze executor in `main.rs`; renderer already belongs to `cli::biocortex` |
| Gated store trial, `11727-11811` | Reads transition gate and decision packet; opens SQLite before lower gate evaluation | A blocked transition prevents `memory_search` and BioCortex but not packet reads or DB initialization; an allowed transition delegates to Store trial | Consumes readiness/capability-ledger authority for an actual explicit runtime entry | Retain executor; renderer is the first conditional candidate |
| Batch diagnostics, `11813-11888` | Reads decision packet; receives query cases assembled by root dispatch; opens SQLite | Runs up to 50 protected Store trials, each of which may query Store and run the external adapter | Aggregates explicit opt-in order movement; does not change default calls | Retain executor; renderer is conditional-only |
| Gated batch diagnostics, `11890-11977` | Reads transition gate and decision packet; receives query cases; opens SQLite | Runs up to 50 gated Store trials; blocked gates stop each query before `memory_search` | Repeatedly consumes the transition gate and can exercise explicit runtime ordering | Retain executor; renderer is conditional-only |
| Controlled-order fixture, `12061-12197` | Requires explicit write acknowledgement, mandatory non-default `AGENT_BRIDGE_DB`, and fixture JSON | Writes fixture memories to the non-production Store, then runs batch diagnostics and possible external side signals | Deliberately demonstrates real order movement in an isolated Store while denying default/production authority | Permanently retain executor, guards, schemas, loaders, Store writes, and payload construction in `main.rs`; renderer is already extracted |
| Retrieval shadow, `12915-13014` | Feature-gated; reads `input_json` or `candidates_json` before runtime gate evaluation | No Store; enabled path may initialize the configured baseline backend, write a temporary corpus, and run the external adapter | Computes advisory ordering only; does not call `memory_search`, register a backend, or return the advisory order as live recall | Retain under the current contract; whole-wrapper movement requires a separate effect-aware ADR |

## Source-backed boundary findings

### Replay and shadow

- Replay source selection, default-Store opening, optional fixture write, and
  comparison invocation are adjacent in `main.rs:11488-11537`. The library
  comparison at `biocortex_shadow.rs:831` sends a full fixture projection to
  the external adapter; `include_events` controls response projection rather
  than adapter-input completeness.
- Retrieval shadow input parsing is in `main.rs:12925-12970`. The library gate
  at `biocortex_shadow.rs:871` checks compile feature, operator disable, and
  runtime enable before invoking the external side signal. Its advisory result
  is not a live Store result.
- Retrieval shadow is the only remaining wrapper that could plausibly move as
  a whole without Store/Hub custody. Such a move would still transfer raw
  candidate-file custody and feature-dependent behavior, so S5-V does not
  authorize it.

### Runtime and Store

- Runtime trial permits the external side signal only after its blockers are
  empty (`biocortex_shadow.rs:2932-3005`) and explicitly reports baseline
  return/no ordering connection (`biocortex_shadow.rs:3104-3126`).
- Runtime, Store, gated Store, and shadow paths retain the operator kill switch
  named `AB_BIOCORTEX_RETRIEVAL_DISABLE`; physical movement must not change
  when that current-process environment value is evaluated.
- Store trial performs baseline `memory_search` before its complete runtime
  blocker decision (`biocortex_shadow.rs:7890-7910`), may invoke the external
  side signal, and then calls `StateStore::memory_search_biocortex_opt_in`.
  Therefore an unauthorized packet blocks experimental influence but does not
  imply that no baseline Store query occurred.
- Gated Store trial validates the transition/capability contract before
  delegating to Store trial. A blocked gate reports no Store trial,
  `memory_search`, or side signal; an allowed gate inherits the complete Store
  trial effect surface.

### Batch and controlled fixture

- Non-gated batch delegates each normalized query to Store trial; gated batch
  delegates each query to gated Store trial. Both cap the set at 50 queries.
- Controlled fixture is the only remaining CLI executor with an explicit AB
  memory write. It refuses the default DB, requires
  `--allow-non-production-store-writes`, seeds `MemoryRecord` values, and only
  then runs the batch path through `store.memory_save(&mem)`. Records are
  written sequentially, so a later invalid record can fail after earlier
  records have already been persisted;
  the acknowledgement and non-default-DB guard must remain visibly adjacent
  to that partial-write behavior. These guards are composition-root authority,
  not presentation mechanics.
- The nearby root-owned helper cluster contains environment evaluation,
  controlled fixture schemas/types, default-DB equivalence checks, loaders,
  evidence construction, and query-case normalization. Whole-executor moves
  would either drag this broad cluster into `cli::biocortex` or create reverse
  dependencies back into the root.

## Test evidence and gaps

Existing evidence supports the effect classification:

- `cli_biocortex_extraction::biocortex_evidence_entry_has_the_preregistered_module_boundary`
  requires runtime trial, Store trial, controlled fixture, ReplayCompare,
  Store opening, actual lower calls, schemas, and memory writes to remain in
  `main.rs`, while forbidding those capabilities in `cli::biocortex`.
- `opt_in_runtime_trial_blocks_without_feature_and_sanitizes_inputs` and
  `opt_in_runtime_trial_rejects_bad_execution_packet_without_echoing_raw_fields`
  cover runtime-trial fail-closed/baseline behavior.
- Store-trial library and MCP tests cover rejected and authorized packets,
  redaction, external-adapter gating, and explicit result-order influence.
- `opt_in_gated_store_trial_blocks_before_memory_search_without_allowed_gate`
  and `opt_in_gated_store_trial_consumes_gate_before_store_trial` cover gate
  precedence.
- MCP tests cover non-gated batch redaction plus gated Store/batch
  blocked-before-search and gate-consumption paths.
- Replay projection tests cover full adapter input versus bounded response
  previews. Retrieval-shadow unit/schema/acceptance evidence covers advisory
  ordering and runtime mutation denial.

The ownership test does not yet name the gated Store executor, either batch
executor, or retrieval-shadow executor as explicit root-owned functions. This
is a governance gap, but changing the Rust test in an audit-only unit would
convert documentation into production-boundary implementation. A later
authorized renderer or executor move must first add the relevant RED ownership
assertion. Its current forbidden token
`biocortex_retrieval_opt_in_batch_diagnostics` also matches a prospective
`..._batch_diagnostics_result` renderer name; a batch-renderer unit must narrow
that assertion to the actual lower call while separately forbidding Store,
file-input, and executor custody.

## Decision

1. Keep all eight effectful executors, the complete `BioCortexOp` schema,
   dispatch, option assembly, loaders, environment decisions, Store custody,
   external execution calls, controlled-write guards, schemas, and payload
   construction in `main.rs`.
2. Keep `cli::biocortex` binary-private and presentation-oriented. Existing
   Store-trial and controlled-fixture renderer boundaries are their terminal
   state under the current JSON contracts.
3. Do not extract the six remaining renderers merely to reduce line count.
   Their 277 lines are low-churn, and moving them now would add imports,
   ownership assertions, parity fixtures, ADRs, and review surface without
   evidence of a recurring conflict.
4. Close the BioCortex S5 composition-root phase at S5-V. The next default
   governance phase is a separately preregistered Avatar inventory, not S5-W.
5. Preserve conditional candidates rather than authorizing them. If S5 is
   reopened, the smallest candidate is the completed gated-Store renderer;
   runtime-trial and ReplayCompare renderers follow. Retrieval-shadow whole
   wrapper movement is a separate effect-aware decision, never a renderer
   follow-up.

The conditional order is intentional. Gated Store is directly symmetrical
with the already-proven S5-U Store renderer and has lower-level blocked/allowed
tests. Runtime trial and ReplayCompare have similarly small pure tails. Batch
and gated-batch renderers should wait for direct legacy-batch behavior coverage
and corrected ownership assertions. Retrieval shadow comes last because it
requires feature-on/feature-off parity and volatile latency normalization.

## Options considered

### Move all eight wrappers into `cli::biocortex`

Rejected. It combines Store initialization, Store reads/writes, caller file
writes, feature/runtime gates, external programs, and actual explicit-order
influence in one module move. The physical boundary would no longer reveal
where authority is consumed.

### Continue one renderer per S5 letter

Deferred. It is behavior-preserving in principle, but current blame/churn and
line-count evidence do not justify six more extraction units. The simpler
architecture is to record the safe seams and stop.

### Move retrieval shadow as the first effect-aware wrapper

Deferred, not rejected. It has no Store/Hub dependency and its core gate lives
in the library, but moving it transfers raw candidate-file custody and requires
feature-on/feature-off CLI parity. That scope needs explicit authorization and
a separate ADR.

## Reopen and stop conditions

S5 remains closed unless at least one of these evidence-backed triggers occurs:

- the same remaining renderer participates in two independent merge conflicts
  or at least three non-format behavior changes within a 90-day window;
- a typed payload/view model replaces the current JSON-pointer presentation
  contract;
- another binary-private consumer needs the same completed-payload renderer;
- retrieval-shadow input custody is explicitly authorized to move and both
  feature-on and feature-off contracts have deterministic parity fixtures;
- Store/external execution is first encapsulated behind a narrower capability
  interface whose authority remains visible at the root call site.

Even after reopening, stop immediately if a proposed change moves or obscures:

- `SqliteStore::open`, `StateStore`, `memory_search`, Store writes, DB-path
  selection, or the controlled non-production guard;
- input precedence or exact file read/parse/write errors;
- feature/runtime/per-call gates, the operator kill switch, transition or
  capability-ledger consumption;
- subprocess/temporary-corpus ownership or timeout behavior;
- default retrieval behavior, MCP/tool policy, approval state, deployment, or
  runtime enablement.

## Consequences

BioCortex ends with mixed physical ownership by design: presentation-only
adapters live in `cli::biocortex`, while effectful and authority-bearing
composition stays visible in `main.rs`. This accepts 711 root lines in
exchange for a legible security and runtime boundary. Future `main.rs`
governance should target demonstrated conflict domains rather than continue a
mechanical BioCortex countdown.

No CLI spelling, help, input order, error, output, Store behavior, external
process, retrieval order, feature, environment, MCP, deployment, or runtime
authority changes as a consequence of this audit.
