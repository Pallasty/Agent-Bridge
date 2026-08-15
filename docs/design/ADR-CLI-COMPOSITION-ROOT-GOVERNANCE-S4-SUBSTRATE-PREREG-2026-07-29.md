# ADR: Preregister complete Substrate CLI family extraction

- Status: Accepted for preregistration; implementation remains a separate gate
- Date: 2026-07-29
- Decision scope: `crates/bridge/src/main.rs` Substrate command family
- Coordination: Agent-Bridge forum thread #251
- Accepted base: `51c0658444310917fb710cb44aaf89e51309cf78`
- Prerequisite: GitLab and GitHub `master` must both contain the accepted base

## Context

S0 established `main.rs` as the CLI composition root and selected
local-control as the pilot. S1 extracted that nested family. S3 then moved the
seven workflow-feedback execution adapters while deliberately retaining their
flat root schema and dispatch in `main.rs`.

At the accepted S4 base, `main.rs` contains 21,318 lines, 200 top-level
functions, and 110 top-level `run_*` functions. The next candidate listed by
the S0 rubric is the nested Substrate family:

- `substrate stats`
- `substrate replay`
- `substrate neighbors`
- `substrate snapshot`

Its current ownership is split across four regions:

| Region | Approximate lines | Responsibility |
| --- | ---: | --- |
| `SubstrateOp` schema | 2870-2969 | clap help, flags, defaults, and nested command spelling |
| pre-Hub dispatch | 5832-5864 | route all four operations before shared store/Hub construction |
| executors and helpers | 14329-14517, 14729-15112 | snapshot inspection, topology reads, replay, rendering, and parsing |
| existing unit tests | 20744-20893 | snapshot summaries, byte rendering, and JSONL parsing |

`run_dream_substrate_corr_audit` occupies the source interval between the
Substrate stats helpers and the remaining Substrate executors. Despite using
the same snapshot substrate, it belongs to `DreamOp::SubstrateCorrAudit`,
opens `state.db`, and has a separate command contract. Physical adjacency is
not module ownership.

The family has a wider dependency boundary than S1:

- the binary-local `seed_substrate` compatibility shim, imported as
  `ab_seed_bridge`, for snapshot, topology, configuration, and replay-shaped
  APIs;
- `ab_store::embedding::{EmbeddingBackend, HashBackend, OnnxBackend}`;
- `anyhow`, clap, serde/JSON, `PathBuf`, `Arc`, filesystem, process, time, and
  environment APIs.

At the accepted base, `crates/bridge/src/seed_substrate.rs` is an
unconditional disabled compatibility shim. The reserved `seed-substrate`
Cargo feature does not relink the standalone legacy `ab-seed-bridge` crate.
`stats` reports the disabled state; existing-file snapshot reads fail closed
through the shim. `replay` still reads and classifies caller-supplied JSONL,
constructs the shim backend, and attempts a final snapshot append, but the
append returns the disabled error. The command emits that warning and exits
successfully even when every input line is skipped, reports zero rows and null
fingerprints, and creates no output file. This observed
attempt-and-fail-closed behavior is load-bearing.
Restoring the legacy writer would be a separate Cargo/runtime design change,
not part of composition-root extraction.

## Decision

Preregister one later implementation slice that moves the complete nested
Substrate CLI family into a binary-private `cli::substrate` module:

1. `SubstrateOp` and all clap attributes/help;
2. the four pre-Hub dispatch branches;
3. `run_substrate_stats`, `run_substrate_neighbors`,
   `run_substrate_replay`, and `run_substrate_snapshot`;
4. Substrate-private helper types and functions:
   `SnapshotSummary`, `SnapshotEntry`, `summarize_snapshot_rows`,
   `human_bytes`, `parse_event_line`, and `mean_f32`;
5. the existing unit tests that directly exercise those helpers.

`main.rs` keeps the top-level `Cmd::Substrate { op: SubstrateOp }` variant as
the composition-root routing declaration, importing the binary-private
`SubstrateOp` from `cli`. The exact dispatch call shape may be reduced to one
module entry point only if clap and behavior evidence remain byte-identical.

The implementation must leave the following in `main.rs`:

- top-level process startup and shared dependency construction;
- the post-Hub `Cmd::Substrate { .. }` unreachable exhaustiveness entry;
- `DreamOp::SubstrateCorrAudit`, its dispatch, executor, helpers, and tests;
- all BioCortex, avatar, dream, memory, runtime, profile, and authority code.

No library API promotion is authorized.

## Preserved invariants

The implementation gate must preserve:

- the top-level `substrate` command and all four nested command names;
- every flag, default, required/optional rule, help paragraph, parse failure,
  and output basename;
- execution before shared store and Hub construction;
- `AB_SUBSTRATE` detection and disabled-state reporting;
- snapshot path precedence and `$HOME` fallback behavior;
- no-path and missing-file success behavior for `neighbors`, plus the
  disabled-shim failure when an explicit path exists and reaches `read_all`;
- `snapshot`'s current disabled-shim failure before tier filtering, limit, or
  fingerprint rendering can observe rows;
- `replay` JSONL skip rules, optional `key` fallback, reserved-but-ineffective
  seed disclosure, hash/ONNX selection, output-path reporting, failed append
  warning, zero-row/null-fingerprint JSON, no-output-file postcondition, and
  success/failure exit rules;
- stdout/stderr text, JSON field names and values, fingerprints, error
  contexts, and filesystem effects;
- default tool profiles, MCP manifests, store schemas, memory/retrieval
  routing, runtime admission, policy, and authority.

The implementation must preserve the existing RNG caveat text even though the
disabled shim currently reports null fingerprints. It must not imply that the
reserved feature marker restores the legacy writer.

## Implementation preregistration

Before moving Rust code, the implementation slice must capture from the exact
accepted implementation base:

1. repository status and local/GitLab/GitHub base identities;
2. root `--help`, `substrate --help`, and `--help` for all four operations;
3. `stats --json` with no snapshot path, a missing explicit path, and an
   existing isolated file that triggers the disabled read warning;
4. `neighbors --json` with no resolved path, a missing explicit path, and an
   existing explicit file that reaches the disabled-shim failure;
5. `snapshot --json` with missing and existing explicit paths, capturing the
   disabled-shim failure before row-level flags take effect;
6. `replay --use-hash --json` against fixed valid, partially malformed, and
   empty JSONL fixtures, using an isolated output path;
7. the no-output-file postcondition after successful valid/partial replay.

The disabled shim emits null Replay fingerprints and zero rows, so no
fingerprint or timestamp normalization is currently needed. Normalize only an
explicit default temporary path if that path is exercised. The baseline packet
must list every normalization and must not drop warnings, event counts,
configuration, exit status, or the no-file postcondition.

The first implementation change must add a focused ownership test that fails
while `SubstrateOp` and the four executors remain owned by `main.rs`. Only
after observing that RED may production code move.

Acceptance requires:

- byte-for-byte equality for all six help surfaces;
- equivalent success/failure exit codes and stdout/stderr;
- explicit no-output-file postcondition checks for valid and partially
  malformed replay;
- all moved helper tests and existing Seed/substrate tests;
- a source-boundary test proving Dream correlation audit remains in
  `main.rs`;
- touched-file rustfmt and `git diff --check`;
- `cargo check --locked --offline -p ab-bridge --all-targets --quiet`;
- a clean isolated worktree and independently reviewable implementation
  commit.

## Stop conditions

Stop and return to design if:

- `DreamOp::SubstrateCorrAudit` must move to make the module compile;
- the module needs shared `Hub`, mutable policy, authorization, MCP registry,
  or daemon state;
- a public library or Cargo feature change becomes necessary;
- replay output behavior, seed disclosure, or filesystem effects drift;
- the extraction requires relinking the standalone legacy seed bridge or
  making the reserved feature marker functional;
- any help, parse, JSON, Markdown/text, warning, error, or exit contract
  changes;
- another owner starts overlapping `main.rs` work without an explicit forum
  handoff;
- either remote no longer contains the implementation base.

## Non-goals

This preregistration does not authorize:

- Rust implementation in this documentation unit;
- substrate algorithm, snapshot schema, embedding backend, RNG, or
  determinism changes;
- changes to `run_dream_substrate_corr_audit`;
- new claims that replay currently persists a snapshot or that the reserved
  feature marker restores persistence;
- `mcp_tools.rs`, library exports, Cargo manifests, store migrations, memory
  writes, retrieval influence, runtime enablement, deployment, or reconnect.

## Trade-offs

Moving the complete nested family restores the S0-preferred ownership model
after S3's justified flat-command exception. It removes more schema and tests
from the composition root than S3, but carries a broader dependency set and a
legacy replay-shaped command whose write attempt currently fails closed. The
stronger replay fixture, warning check, and no-file postcondition are therefore
part of the decision, not optional test polish.

Keeping Dream correlation audit in `main.rs` leaves a nearby substrate-themed
function outside the new module. That is intentional: command ownership and
authority boundaries outrank name or file-position similarity.

## Rollback

This documentation-only unit can remain as an audit artifact if implementation
is abandoned. A later implementation must be one isolated commit that can be
reverted without reverting this ADR or the S3 environment-name correction.
Any behavior drift requires restoring the family to `main.rs`, not adding
aliases, output compatibility shims, or broader module dependencies.
