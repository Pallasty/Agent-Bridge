# ADR: CLI Composition Root Governance S5-G — BioCortex Runtime-Trial-Review Custody Split

## Status

Accepted for implementation on 2026-07-29.

## Context

S5-F landed the protected execution-packet renderer at
`73784fda44c88f6559190e629064687111c7d5cf`. Local, GitLab, and GitHub
`master` resolved to that commit when S5-G was preregistered.

The immediately following runtime-trial command may invoke an external
BioCortex side-signal adapter. It is therefore outside this narrow
composition-root extraction unit.

The subsequent
`run_biocortex_retrieval_opt_in_runtime_trial_review_packet` currently combines:

1. composition-root custody of a required runtime-trial JSON file, including
   exact read and parse error messages; and
2. a synchronous, read-only review-packet renderer consuming fully populated
   `BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions`.

Moving the whole function would move filesystem input custody into
`cli::biocortex`. Keeping the whole function in `main.rs` would leave a pure
renderer embedded in the composition root.

The review constructor:

- consumes only safe summary fields from an already-produced runtime trial;
- sanitizes raw query, key, content, and side-signal fields;
- emits violations for unsafe or malformed contract values;
- does not grant runtime-influence approval;
- does not call `memory_search`;
- does not run BioCortex;
- does not open the store;
- does not change retrieval order.

AB memory intent:
`decision_ab_cli_composition_root_governance_s5g_runtime_trial_review_packet_intent_20260729`.

AB forum thread: `#266`.

## Options Considered

### Extract the runtime-trial command first

Rejected for this ladder. That command may invoke the external side-signal
adapter and requires a separate authority review.

### Move the complete review adapter

Mechanically simple, but it would move runtime-trial file-read and parse custody
out of the composition root.

### Retain input custody and move only the pure review renderer

This keeps all input and runtime authority visible in `main.rs`, while the
private module receives only a populated, read-only options value.

## Decision

Choose the custody split and explicitly skip the runtime-trial executor.

`main.rs` will:

- retain the complete Clap schema and
  `BioCortexOp::RetrievalOptInRuntimeTrialReviewPacket` dispatch;
- call `std::fs::read_to_string(runtime_trial_json)`;
- retain the exact `read runtime-trial JSON` and
  `parse runtime-trial JSON` errors;
- deserialize the required runtime-trial packet;
- assemble all fields of
  `BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions`;
- pass the complete options value and `as_json` to the private renderer.

`cli::biocortex` will own only:

```text
run_biocortex_retrieval_opt_in_runtime_trial_review_packet(
    opts: BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions,
    as_json: bool,
)
```

## Boundaries Retained in `main.rs`

- every public Clap enum and attribute;
- all required and optional JSON file custody;
- the full runtime-trial executor, input resolution, candidate parsing, and
  external side-signal authority;
- order-diff, redaction, store, readiness, transition, evidence, replay,
  controlled fixture, and shadow paths;
- environment and compile-feature semantics;
- `SqliteStore`, `memory_search`, and external adapter authority.

## Trade-Offs

The dispatch arm grows because file loading is deliberately visible. This is
accepted rather than introducing a generic loader that obscures exact
command-specific error contracts.

The private renderer remains `async` although its constructor is synchronous,
preserving dispatch shape and output behavior.

## Verification Contract

Before production changes:

1. capture an exact-base contract for root help, BioCortex help, command help,
   valid JSON/text, invalid-but-valid trial JSON/text, a missing input, and
   malformed JSON;
2. extend the cumulative ownership test to require the review renderer in
   `cli::biocortex`;
3. assert runtime-trial file read, exact parse errors, and full options assembly
   remain in `main.rs`;
4. assert the runtime-trial executor remains in `main.rs`;
5. observe the expected RED ownership failure.

After the minimal split:

1. run cumulative ownership, focused runtime-trial-review tests, and formatter
   tests;
2. run touched-file formatting and whitespace checks without accepting
   unrelated repository-wide drift;
3. run a fresh-target locked/offline all-target check and final binary build;
4. compare all base/final stdout, stderr, and exit-code artifacts, normalizing
   only JSON fields named `generated_at`;
5. re-check current `master`, rebase and repeat affected gates if it moved;
6. prove final branch and `master` refs on GitLab and GitHub.

## Hard Non-Goals

- no public CLI spelling, help, default, output, or exit-code change;
- no filesystem, store, or database access in the extracted renderer;
- no extraction or invocation of the runtime-trial executor;
- no BioCortex side-signal execution;
- no `memory_search` or retrieval-order mutation;
- no raw input echo;
- no approval or runtime authority;
- no deployment or reconnect.

## Revisit Trigger

The runtime-trial executor requires a separate authority-focused ADR before any
ownership move. Later pure packet renderers require independent input-custody
analysis.
