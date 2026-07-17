# BioCortex Track B S16: recovered-envelope durability fault model

Date: 2026-07-17
Decision: `BLOCKED_FAIL_CLOSED`

## Outcome

S16 preregisters a private, default-off, deterministic fault model against the
exact S15 `open_exact -> read_into -> complete` state surface. The model
enumerates 5,639 synthetic rows over object bytes, durability receipts,
publication order, restart cuts, replicas, generations, and witnesses. It
exists to make durability claims falsifiable before any provider is selected.

The model is not a durable store. It performs no filesystem, network,
database, provider-SDK, clock, credential, or production operation. Every row
is a local simulation and contributes **zero** external durability
observations, **zero** provider observations, and **zero** owned-lab
observations. The S14 result remains private and historical-only.

```text
       frozen S15 one-shot adapter state surface
                        |
                        v
       deterministic event + fault schedule (5,639 rows)
              / object / receipt / witness \
             v                              v
     modeled volatile state          modeled durable state
             \                              /
              +---- crash / restart cut ---+
                        |
                        v
          fail-closed synthetic observation
                        |
                        v
       NO provider evidence · NO currentness · NO admission
```

## Why a model, not a provider adapter

S15 made the read lifecycle executable while deliberately supplying no
production or provider concrete transport. Connecting a real provider first
would combine protocol, provider semantics, credentials, deployment, and
fault interpretation in one step. S16 instead freezes the questions a later
provider or owned lab must answer, while keeping model outcomes visibly
separate from observations.

The model may demonstrate that an event schedule is internally consistent or
that a forbidden state fails closed. It cannot demonstrate that a filesystem,
database, quorum, KMS, managed provider, host, or network behaves that way.

## Deterministic state surface

Each row starts from an explicit modeled object/receipt/witness state and
applies a finite, ordered schedule. The model distinguishes:

- volatile bytes from bytes declared durable by the synthetic schedule;
- object presence from receipt presence;
- object revision from source generation and witness generation;
- acknowledgement from commit and commit from response delivery;
- local replica state from the selected witness view;
- adapter completion from downstream currentness or consumption.

Restart reconstructs only the row's modeled durable state. Volatile state is
discarded. No hidden cache, retry, latest lookup, replica fallback, wall clock,
random seed, environmental input, or iteration-order dependence may repair a
row.

The 5,639-row catalog is the closed, exhaustive, stably ordered union of
families D00 through D15. Duplicate rows are forbidden rather than repaired by
deduplication. Its row count and catalog commitment are conformance known
answers, not statistical sample sizes and not external observations.

Catalog construction supplies only raw durable, volatile, evidence-boundary,
and lifecycle facts. One evaluator derives disposition, reason, S15 execution
result, and mapped failure from those facts. The row builder cannot accept,
carry, or override those outcomes; unsupported combinations take the single
fail-closed fallback. This keeps case labels and expected rows from acting as
an independent outcome oracle. The evaluator validates both the exact
lifecycle tuple and its allowed pairing with the durable image before any
pending, unavailable, rollback, or success result can be selected.

All 106 D05 rows remain modeled: 53 cut positions times first attempt and
restart. The Rust test uses a test-only synthetic `ModelTransport` to execute
50 injected failures (`AFTER_OPEN` plus `AFTER_DATA_0001..0049`) and 50 exact
rereads through newly constructed adapter/transport instances. The six rows
for `BEFORE_OPEN`, `AFTER_COMPLETE_BEFORE_S14`, and `AFTER_HISTORICAL` remain
model-only. S16 executes **zero** OS process crashes and **zero** external
durable restarts; none of these test-only calls is external durability
evidence.

## Fault families

The closed D00-through-D15 catalog covers these independently named families:

1. partial and torn object bytes, including post-persistence bit flips;
2. object/durability-receipt/witness publication reordering;
3. acknowledgement before durable commit;
4. durable commit followed by response loss;
5. synthetic crash/restart rows at every open, data, and completion cut;
6. object-present/receipt-absent and receipt-present/object-absent restart;
7. restoration of an older snapshot or source generation;
8. same-revision equivocation and cross-replica byte disagreement;
9. stale replica and split-brain selection;
10. missing, unavailable, corrupt, or forked witness evidence.

A modeled success requires one exact object identity and digest to remain
consistent through the scheduled restart and the unchanged S15/S14 verifier.
Ambiguity, missing evidence, rollback, mismatch, or unsupported ordering fails
closed. The model never substitutes latest, invents a receipt, repairs bytes,
or upgrades an indeterminate row to success.

## Frozen predecessor seam

The feature is
`temporal-evidence-s16-recovered-envelope-durability-fault-model-synthetic`.
It is absent from defaults and depends exactly on
`temporal-evidence-s15-recovered-envelope-bounded-runtime-adapter-synthetic`.

S16 is a private child of the S15 adapter module. The only permitted S15
source change is one exact feature-gated child-module declaration. No test
fixture seam is added, no production S15 item becomes public, and no
production constructor or caller is added.

Those successor seams deliberately change the current S15 packet. Therefore
the S16 gate does **not** claim that the current S16 HEAD passes the S15
historical-descendant gate. It independently replays the frozen S15 integrated
gate at `80fdb9b5d5f4be5f9663f30cd686cd5fb6bdfd35`, reruns the 13 S15 tests and
all retained S14-through-S9 matrices with the S16 feature, and makes the S16
gate authoritative for the current tree.

## Verification contract

The independent checker must validate duplicate-free, root-closed JSON; the
exact default-off feature edge; exact predecessor glue; the deterministic
catalog size and commitment; state, event, fault, and observation taxonomies;
known S14/S15 commitments; and absence of production or Bridge wiring. Two
isolated checker runs must byte-match one frozen TSV receipt.

The Rust matrix is S16 20, S15 13, S14 24, S13 15, S12 32, S11 30, S10 15,
and S9 15 non-ignored tests. Cargo remains serial, non-incremental, offline,
and built without debug information. Passing these checks proves local model
conformance only.

## Explicit negative claims

S16 contains no production or provider concrete transport, durable object
store, filesystem writer, database transaction, provider client, credential,
production permit, Bridge/`StateStore` caller, background worker, deployment
configuration, currentness token, admission receipt, or side effect. Its
test-only synthetic `ModelTransport` is neither production wiring nor durable
restart evidence. In particular, S16 does not prove or provide:

- fsync, atomic rename, WAL, manifest, quorum, or KMS semantics;
- provider linearizability, availability, memory, timeout, or liveness bounds;
- crash/restart behavior on any real host or service;
- rollback resistance, non-equivocation, split-brain fencing, or witness
  independence;
- owner-authorized exact-object selection;
- capture attestation, signer custody, revocation, or key-role separation;
- runtime S10 delivery, currentness at use, atomic consume-and-action,
  exactly-once behavior, production admission, or side-effect authority.

Modeled durable state is a label inside a synthetic row, not evidence that any
byte survived a real crash. A modeled witness is not an independently operated
witness. Replaying the same successful row remains repeatable historical
verification, not a global replay fence.

## Successor boundary

The next production-facing step remains blocked. A successor may be proposed
only as a separately authorized provider or owned-lab evidence plan that maps
each observed event to this frozen taxonomy, records real crash/restart and
anti-rollback evidence, and keeps simulated and observed ledgers disjoint.

Until that evidence exists, owner-pinned production permits, runtime
capture/custody and signer separation, runtime S10 delivery, and atomic
currentness-at-use remain unavailable. Production admission remains false and
side effects unlocked remain `NONE`.
