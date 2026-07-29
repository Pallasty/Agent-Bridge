# ADR: CLI Composition Root Governance S5-F — BioCortex Execution-Packet Custody Split

## Status

Accepted for implementation on 2026-07-29.

## Context

S5-E landed the read-only retrieval review-packet executor at
`af6594b0daf2d1e51484e2948823c8ed47781aa8`. Local, GitLab, and GitHub
`master` resolved to that commit when S5-F was preregistered.

The next command in the evidence chain,
`run_biocortex_retrieval_opt_in_execution_packet`, currently combines:

1. composition-root custody of a required review-packet JSON file, including
   exact read and parse error messages; and
2. a protected contract/preflight executor that consumes fully populated
   `BioCortexRetrievalOptInExecutionPacketOptions` and renders JSON or text.

Moving the whole function would move filesystem input custody into
`cli::biocortex`. Keeping the whole function in `main.rs` would leave a pure
packet executor embedded in the composition root. The responsibilities can be
split without adding a shared abstraction.

Despite its name, the planner is fail-closed and contract-only. It:

- rebuilds and validates the baseline-preserving store contract;
- emits blockers for unsafe or malformed review-packet values;
- does not grant approval;
- does not call `memory_search`;
- does not run BioCortex;
- does not open the store;
- does not change retrieval order;
- does not echo the raw review packet, query, keys, or content.

AB memory intent:
`decision_ab_cli_composition_root_governance_s5f_retrieval_opt_in_execution_packet_intent_20260729`.

AB forum thread: `#265`.

## Options Considered

### Keep both responsibilities in `main.rs`

This preserves current ownership but leaves a presentation-only packet executor
in the composition root and prevents the BioCortex module boundary from
advancing.

### Move the entire existing function

This is mechanically smaller, but it moves file-read and parse custody into the
execution module. That weakens the governance rule established by S5-E.

### Retain input custody and move only the pure executor

This requires relocating the existing read/parse statements into the dispatch
arm, but it keeps authority visible in `main.rs` and gives
`cli::biocortex` only a fully populated, read-only input value.

## Decision

Choose the custody split.

`main.rs` will:

- retain the complete Clap schema and
  `BioCortexOp::RetrievalOptInExecutionPacket` dispatch;
- call `std::fs::read_to_string(review_packet_json)`;
- retain the exact `read review-packet JSON` and
  `parse review-packet JSON` errors;
- deserialize the required packet;
- assemble all fields of
  `BioCortexRetrievalOptInExecutionPacketOptions`;
- pass the complete options value and `as_json` to the private executor.

`cli::biocortex` will own only:

```text
run_biocortex_retrieval_opt_in_execution_packet(
    opts: BioCortexRetrievalOptInExecutionPacketOptions,
    as_json: bool,
)
```

The private executor will call the existing library planner and render the
unchanged JSON/text contract.

## Boundaries Retained in `main.rs`

- every public Clap enum and attribute;
- all required and optional JSON file custody;
- replay comparison;
- runtime trial, runtime-trial review, order-diff, store trial, batch
  diagnostics, readiness, transition, evidence, controlled fixture, and shadow
  paths;
- environment and compile-feature semantics;
- `SqliteStore`, `memory_search`, and external adapter authority.

## Trade-Offs

The dispatch arm becomes several lines longer because it now visibly owns input
loading. This duplication remains preferable to introducing a generic required
JSON loader whose exact error wording would itself become a new shared
contract.

The private executor stays `async` even though its planner is synchronous, so
dispatch shape and behavior remain unchanged.

## Verification Contract

Before production changes:

1. capture an exact-base contract for root help, BioCortex help, command help,
   valid JSON/text, an invalid-but-valid review packet in JSON/text, a missing
   input, and malformed JSON;
2. extend the cumulative ownership test to require the execution-packet
   executor in `cli::biocortex`;
3. assert the review-packet file read, exact parse errors, and full options
   assembly remain in `main.rs`;
4. assert this executor does not bring filesystem custody into the private
   module;
5. observe the expected RED ownership failure.

After the minimal split:

1. run cumulative ownership, focused execution-packet planner tests, and
   formatter tests;
2. run touched-file rustfmt and whitespace checks;
3. run a fresh-target locked/offline all-target check and final binary build;
4. compare all base/final stdout, stderr, and exit-code artifacts, normalizing
   only JSON fields named `generated_at`;
5. re-check current `master`, rebase and repeat affected gates if it moved;
6. prove the final branch and `master` refs on GitLab and GitHub.

## Hard Non-Goals

- no public CLI spelling, help, default, output, or exit-code change;
- no filesystem, store, or database access in the extracted executor;
- no extraction of runtime trial or later evidence-chain commands;
- no `memory_search` or BioCortex execution;
- no retrieval-order mutation;
- no raw input echo;
- no approval or runtime authority;
- no deployment or reconnect.

## Revisit Trigger

Further packet executors require their own custody analysis. A generic required
JSON loader may be considered only if repeated exact error contracts can be
centralized without obscuring authority.
