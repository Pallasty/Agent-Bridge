# ADR: CLI Composition Root Governance S5-D — BioCortex Retrieval Opt-In Dry Run

## Status

Accepted for implementation on 2026-07-29.

## Context

Agent-Bridge `main.rs` remains the public CLI composition root. Earlier
governance units moved narrowly bounded execution adapters into private
`cli::*` modules while retaining the Clap schema, dispatch, option assembly,
and authority decisions in `main.rs`.

S5-C landed at
`cf4c130489ef1c248d74a7e2fa0c3d498730eeea`, after incorporating the
independently landed S6 BrowserLite extraction. Local, GitLab, and GitHub
`master` all resolved to that commit when this unit was preregistered.

The next narrow candidate is
`run_biocortex_retrieval_opt_in_dry_run`. It accepts an already assembled
`BioCortexRetrievalOptInDryRunOptions`, calls
`biocortex_retrieval_opt_in_dry_run_plan`, and renders JSON or text.

The planner observes the frozen compile and environment gates and emits
timestamps, but it remains a read-only planning surface:

- it does not call `memory_search`;
- it does not run BioCortex;
- it does not open the store or read input files;
- it does not register an embedding backend;
- it does not change retrieval order;
- it returns the baseline order by contract;
- it does not expose raw query text, keys, or content.

The downstream review, execution, runtime-trial, store-trial, readiness,
transition, and evidence commands have materially broader input and authority
boundaries and are not part of this unit.

AB memory intent:
`decision_ab_cli_composition_root_governance_s5d_retrieval_opt_in_dry_run_intent_20260729`.

AB forum thread: `#262`.

## Options Considered

### Keep the adapter in `main.rs`

This avoids a code move but leaves a proven presentation-only executor inside
the composition root and makes the BioCortex ownership boundary inconsistent
with S5-A through S5-C.

### Extract the whole retrieval opt-in family

This would remove more lines, but it would combine pure planning/rendering with
file parsing, database access, external process execution, runtime gates, and
store authority. The verification surface and rollback radius would be too
large for one governance unit.

### Extract only the dry-run executor

This is the smallest behavior-preserving boundary. It improves module
cohesion without moving argument assembly, input custody, runtime authority, or
side effects.

## Decision

Move only `run_biocortex_retrieval_opt_in_dry_run` from
`crates/bridge/src/main.rs` to the existing private
`crates/bridge/src/cli/biocortex.rs`.

Privately re-export it through `crates/bridge/src/cli/mod.rs`.

Retain in `main.rs`:

- the complete `BioCortexOp` Clap schema and attributes;
- the exact `RetrievalOptInDryRun` dispatch arm;
- cloning and assembly of `BioCortexRetrievalOptInDryRunOptions`;
- compile-feature and environment-gate semantics;
- `read_optional_json_file`;
- replay comparison;
- all review, execution, runtime, store, readiness, transition, controlled
  fixture, aggregation, and shadow paths;
- `SqliteStore`, `memory_search`, and external adapter authority.

## Trade-Offs

The extraction removes only one executor and therefore does not materially
reduce the total size of `main.rs`. That is intentional: the governance
sequence optimizes for independently provable ownership boundaries instead of
bulk line-count reduction.

The executor remains `async` even though the current planner is synchronous.
Preserving the signature keeps dispatch behavior and the public command
contract unchanged.

## Verification Contract

Before production code changes:

1. capture an exact-base binary contract covering root help, BioCortex help,
   command help, default JSON/text, populated JSON/text, and unauthorized-mode
   JSON/text;
2. extend the cumulative ownership test;
3. run it and observe the expected RED failure because
   `cli::biocortex` does not own the dry-run executor.

After the minimal move:

1. run the ownership test and focused dry-run planner tests;
2. run the existing `cli::biocortex` formatter tests;
3. check touched-file formatting and commit whitespace;
4. run a fresh-target locked/offline `ab-bridge --all-targets` check;
5. build a fresh final binary;
6. compare all 27 contract artifacts with the exact-base binary, normalizing
   only every JSON field named `generated_at`;
7. re-check current `master`, rebase if necessary, and repeat affected gates;
8. prove the final branch and `master` hashes on both remotes.

## Hard Non-Goals

- no public CLI spelling, help, default, output, or exit-code change;
- no file, database, or store access movement;
- no `memory_search` or BioCortex execution;
- no retrieval-order change;
- no raw query, key, or content disclosure;
- no runtime enablement or authority expansion;
- no deployment or reconnect.

## Revisit Trigger

Consider another executor only after S5-D has independent behavior parity and
dual-remote evidence. Any candidate that reads files, opens the store, invokes
an external process, or evaluates transition authority requires a separate ADR
and narrower custody analysis.
