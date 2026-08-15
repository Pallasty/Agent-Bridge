# ADR: CLI Composition Root Governance S5-E — BioCortex Review-Packet Custody Split

## Status

Accepted for implementation on 2026-07-29.

## Context

S5-D landed the read-only retrieval dry-run executor at
`d4921e55afc290ca5ddd9ba4d350c2e7c396a530`. Local, GitLab, and GitHub
`master` resolved to that commit when S5-E was preregistered.

The next command in the evidence chain,
`run_biocortex_retrieval_opt_in_review_packet`, currently combines:

1. composition-root custody of a required dry-run JSON file, including exact
   read and parse error messages; and
2. a read-only planner/report executor that consumes fully populated
   `BioCortexRetrievalOptInReviewPacketOptions` and renders JSON or text.

Moving the whole function would move filesystem input custody into
`cli::biocortex`. Keeping the whole function in `main.rs` would leave a pure
executor embedded in the composition root. The responsibilities can be split
without adding a shared abstraction.

The planner is fail-closed and report-only. It:

- validates the dry-run packet boundary;
- emits violations for unsafe or malformed contract values;
- does not grant approval;
- does not call `memory_search`;
- does not run BioCortex;
- does not open the store;
- does not change retrieval order;
- does not echo the raw dry-run packet, query, keys, or content.

AB memory intent:
`decision_ab_cli_composition_root_governance_s5e_retrieval_opt_in_review_packet_intent_20260729`.

AB forum thread: `#264`.

## Options Considered

### Keep both responsibilities in `main.rs`

This preserves current ownership but leaves a presentation-only executor in the
composition root and prevents the BioCortex module boundary from advancing.

### Move the entire existing function

This is mechanically smaller, but it moves file-read and parse custody into the
execution module. That weakens the governance rule established by S5-C and
S5-D.

### Retain input custody and move only the pure executor

This requires relocating the existing read/parse statements into the dispatch
arm, but it keeps authority visible in `main.rs` and gives
`cli::biocortex` only a fully populated, read-only input value.

## Decision

Choose the custody split.

`main.rs` will:

- retain the complete Clap schema and
  `BioCortexOp::RetrievalOptInReviewPacket` dispatch;
- call `std::fs::read_to_string(dry_run_json)`;
- retain the exact `read dry-run JSON` and `parse dry-run JSON` errors;
- deserialize the required packet;
- assemble all fields of
  `BioCortexRetrievalOptInReviewPacketOptions`;
- pass the complete options value and `as_json` to the private executor.

`cli::biocortex` will own only:

```text
run_biocortex_retrieval_opt_in_review_packet(
    opts: BioCortexRetrievalOptInReviewPacketOptions,
    as_json: bool,
)
```

The private executor will call the existing library planner and render the
unchanged JSON/text contract.

## Boundaries Retained in `main.rs`

- every public Clap enum and attribute;
- all required and optional JSON file custody;
- replay comparison;
- execution packet, runtime trial, store trial, batch diagnostics, readiness,
  transition, evidence, controlled fixture, and shadow paths;
- environment and compile-feature semantics;
- `SqliteStore`, `memory_search`, and external adapter authority.

## Trade-Offs

The dispatch arm becomes several lines longer because it now visibly owns input
loading. This duplication is accepted for one command rather than introducing
a generic required-JSON loader before repeated need is proven.

The private executor stays `async` even though its planner is synchronous, so
dispatch shape and behavior remain unchanged.

## Verification Contract

Before production changes:

1. capture an exact-base contract for root help, BioCortex help, command help,
   valid JSON/text, an unsafe-but-valid dry-run plan in JSON/text, a missing
   input, and malformed JSON;
2. extend the cumulative ownership test to require the review executor in
   `cli::biocortex`;
3. assert the dry-run file read, parse errors, and full options assembly remain
   in `main.rs`;
4. assert this executor does not bring filesystem custody into the private
   module;
5. observe the expected RED ownership failure.

After the minimal split:

1. run cumulative ownership, focused review-packet planner tests, and formatter
   tests;
2. run touched-file rustfmt and whitespace checks;
3. run a fresh-target locked/offline all-target check and final binary build;
4. compare all 27 base/final artifacts, normalizing only JSON fields named
   `generated_at`;
5. re-check current `master`, rebase and repeat affected gates if it moved;
6. prove the final branch and `master` refs on GitLab and GitHub.

## Hard Non-Goals

- no public CLI spelling, help, default, output, or exit-code change;
- no filesystem, store, or database access in the extracted executor;
- no extraction of the execution packet or later evidence chain;
- no `memory_search` or BioCortex execution;
- no retrieval-order mutation;
- no raw input echo;
- no approval or runtime authority;
- no deployment or reconnect.

## Revisit Trigger

Further packet executors require their own custody analysis. A generic required
JSON loader may be considered only after another independently verified unit
demonstrates the same stable error and ownership contract.
