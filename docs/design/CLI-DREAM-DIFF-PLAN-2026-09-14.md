# Dream diff calculation boundary — 2026-09-14

The owner accepted the proposed next bounded governance target after root date
consolidation. Extract the calculation in `run_dream_diff` and its three JSON
helpers into private binary module `cli::dream_diff_plan`. This is explicitly
authorized maintenance, not a reopened S22/G8 sequence or a line-count target.

## Boundary and preserved behavior

`calculate` consumes two parsed, schema-checked JSON values and borrows their
keys, returning a typed 23-field `DiffPlan`. Store opening, explicit/automatic
key selection, A-then-B reads, kind checks, A-then-B parsing, schema checks and
text/JSON rendering stay in main.rs. In particular, `memory_get` updates access
count and last-access time: these effects and their ordering remain at root.
The extracted module has no Store, clock, I/O or output capability.

Preserve timestamp ties, chronological key order, missing/wrong-type defaults,
unsigned casts, duplicate-key last-wins rules and integer overflow behavior.
Three access result lists originate in HashMap iteration and remain unordered;
no runtime sorting is added. Other existing ordering rules remain intact.
Avatar/BioCortex authority and unrelated retained regions are outside scope.

## Verification contract

The frozen Rust oracle is bound byte-for-byte to the original calculation and
three helpers at `e34700ca0adf5b21c892d872f6ab8fa09f146fa3`. Five pure/source
tests cover independent expected deltas, ties and duplicate rows, 256 ordered
value pairs and overflow parity. Comparisons normalize only the three originally
unordered access lists; the frozen oracle is deliberately not reformatted.

A sixth Rust test runs 22 isolated CLI cases against a frozen output/state oracle
recorded from the pre-extraction binary. Its SHA was verified against the archived
civil-date candidate build. Cases cover help, missing/not-found keys, kind/parse/
schema errors, forward/reverse/same-key/empty text and JSON results, timestamp
ties and automatic pair selection. SQLite triggers record read order; every
memory column is compared, with only bounded access timestamps and temporary
paths normalized. Each unordered result group has at most one element in these
exact-output cases; multi-element semantics are covered by the pure corpus.

Enroll the six tests and CLI fixture inputs in the existing local gate. Run the
normal full pre-commit profiles and ab-bridge all-targets check. Archive the
143-case portable CLI bundle separately from the new 22-case evidence: the G5
offline verifier does not validate these additional cases.

## Size and rollback

main.rs decreases from 21,828 to 21,647 lines (181 lines); this records the
boundary change, not an acceptance metric. Restore the original computation,
helpers and associated test enrollment together to roll back. No database
migration, installation, service restart or CI execution is part of delivery.
