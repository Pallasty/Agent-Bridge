# Free Recall Strategy R10 — `session_curate` Producer Preregistration

Date: 2026-07-22

Status: **PREREGISTERED / DESIGN AND PUBLIC-SYNTHETIC VALIDATION ONLY / NO SOURCE AUTHORITY**

Parent result:
`docs/design/FREE_RECALL_STRATEGY_R9_SLICE_B_BUILD_RESULT_2026_07_22.md`

## 1. Question

R10 asks whether the first and only Slice C producer seam can be placed in
`session_curate` without widening `StateStore`, coupling the bridge directly to
`SqliteStore`, changing curation results when observation fails, or finalizing
an episode whose event history is incomplete.

R10 preregisters call order, dependency injection, candidate accounting, and
failure semantics. It changes no Rust, Cargo feature, database, runtime
configuration, producer, key custody, or deployment.

## 2. Current-source findings

The current real-save path has two boundaries that must be repaired before a
producer can be inserted safely:

1. The single `errors` vector contains both prior-handoff scan errors and
   per-candidate lookup/save errors. Therefore
   `candidates.len() - saved.len() - errors.len()` is not a valid duplicate
   count and may underflow when auxiliary errors outnumber candidates.
2. `session_curate` owns `Arc<dyn StateStore>`, while the Slice B adapter is a
   private `SqliteStore` detail. Widening `StateStore`, downcasting it, or
   opening a second SQLite connection would violate the frozen isolation
   boundary.

The existing `record_session_curate_event` semantic lifecycle event remains a
separate, best-effort aggregate signal. It is not an episode sidecar event and
must not be repurposed as one.

## 3. Candidate outcome ledger

A future C1 source slice must first replace subtraction over the mixed error
vector with explicit outcomes:

- `saved`: `memory_save` returned success;
- `duplicate`: `memory_get` returned an existing record;
- `lookup_error`: `memory_get` failed;
- `save_error`: `memory_save` failed;
- `auxiliary_error`: the prior-handoff scan or another non-candidate helper
  failed.

`skipped_duplicates` is exactly the duplicate count. Candidate error count is
exactly lookup plus save errors. The outward `errors` array may preserve the
current presentation order, including auxiliary errors, but neither duplicate
count nor lifecycle save-failure classification may be derived from its
length. This prerequisite correction must have dedicated zero-candidate and
auxiliary-error tests.

## 4. Dependency boundary

The selected seam is an optional, narrowly scoped **curation-batch observation
capability** injected into `Hub` and defaulting to `None`.

It is not a `StateStore` method. It must not expose SQLite, projection reads,
MCP/API methods, sync/export, retrieval, or arbitrary event append. Its
producer-facing vocabulary is only:

1. begin one `curation_batch` attempt;
2. observe one memory key *after* that memory was saved, at a supplied saved
   ordinal;
3. finish the attempt with the number of successfully observed items.

The capability owns event/run/episode identity allocation, `item_ref`
derivation, payload hashing, key-provider access, and the actual sink. The
caller never receives key bytes and never constructs raw sidecar events.
Passing a just-saved memory key to this trusted in-process capability is the
only permitted raw-key boundary; the capability must not retain or log it.

Slice C is split into two separately authorized source gates:

- **C1 producer orchestration:** a bridge-private capability trait, optional
  `Hub` field/builder method, explicit outcome ledger, and deterministic fake
  capability tests. No `ab-store` adapter, real key provider, main wiring, or
  sidecar I/O is reachable.
- **C2 storage integration:** a narrow cross-crate capability implementation
  backed by the already private Slice B adapter, plus separately approved key
  custody and runtime configuration. C2 is not opened by R10 or C1 acceptance.

This split is necessary because a bridge test can inject a fake capability
without making the private Slice B adapter public merely to satisfy a test.

## 5. Activation gate

The producer is active only when all of these are present:

- explicit default-off Slice C compile support;
- explicit runtime enablement;
- a trusted `EpisodeRefKeyProvider`;
- an injected observation sink/capability.

If any element is absent, observation abstains and emits no episode event.
There is no environment/CLI secret, generated fallback key, unkeyed fallback,
production ID implementation, or automatic main-process wiring in C1.

`dry_run`, no-store calls, and empty candidate batches emit no episode event.
The existing curation response and memory behavior remain unchanged when the
capability is absent or disabled.

## 6. Canonical call order

For a non-dry-run call with a store and at least one candidate:

1. Complete candidate extraction, governance, and the auxiliary prior-handoff
   scan.
2. Immediately before entering the candidate lookup/save loop, call `begin`.
3. For each candidate, perform duplicate lookup and then memory save exactly as
   today.
4. Only after `memory_save` succeeds, call `observe_saved` with the memory key
   and the zero-based ordinal among successful memory saves. Duplicates,
   lookup errors, and save errors consume no ordinal and emit no item.
5. After the loop, call `finish` only if at least one memory save succeeded,
   every corresponding observation succeeded, and the number of observed
   items equals the number of successful saves.

An all-duplicate or all-error batch may leave one open event but never a close;
the Slice B projection therefore ignores it. This follows the already frozen
"open before loop" rule while avoiding an event for an empty candidate list.

## 7. Failure semantics

Observation is **fail-open for core curation and fail-closed for the sidecar**:

- begin failure: continue all memory operations, emit no further sidecar event;
- item-ref derivation or item append failure: latch the attempt as compromised,
  suppress all later sidecar calls including close, and continue all memory
  operations;
- close failure: memory results remain valid, while the incomplete episode is
  ignored by projection;
- duplicate or memory lookup/save failure: do not emit an item; other
  successful saves may still form a finalized episode;
- process crash: any open/partial event stream remains incomplete and ignored.

Observation failure must never abort, roll back, retry, reorder, or relabel a
memory save. It must not enter the candidate error ledger or alter the MCP
response. A future implementation may emit an internal bounded warning, but
must not add a public response field in C1.

## 8. Public-synthetic cases

The R10 validator models these traces without importing repository code or
touching a database:

- dry-run, no-store, disabled/missing gate, and empty candidates: no events;
- all duplicates: open only, no finalized episode;
- mixed saved/duplicate/lookup-error/save-error: contiguous saved ordinals and
  one matching close;
- begin failure: no sidecar events while all core outcomes remain available;
- first or later item failure: failure latch and no close;
- close failure: an incomplete trace;
- auxiliary error plus zero/one candidate: exact non-underflowing counters.

Directed mutations must reject default-on activation, additional producers,
raw/unkeyed item references, item-before-save, candidate-index positions,
duplicate/error items, zero-save close, close after a sidecar gap, core abort or
rollback, mixed-vector subtraction, `StateStore` widening/downcast, direct
SQLite access, public/retrieval/sync surfaces, production IDs/secrets, or any
source/build/run/capture/merge/deploy claim.

## 9. Decision rule

If all R10 deterministic and directed-mutation gates pass, the next possible
request is narrowly for **C1 producer-orchestration source only**. C1 may add
the optional `Hub` dependency, explicit outcome ledger, fake capability, and
unit tests, but it cannot create or append a real episode event.

C2 storage integration, Cargo build/test, real database execution, key custody,
real capture, retrieval experiment, merge, release, and deployment remain
separate owner gates.

## 10. Negative authority

R10 does not authorize Rust/SQL/Cargo changes, features, database access,
producer wiring, runtime enablement, key generation or custody, builds,
execution, private-state tests, real capture, retrieval, sync/export, MCP/API
changes, merge, release, deployment, training, or BioCortex.
