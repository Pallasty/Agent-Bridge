# ADR: Incremental governance of the Agent-Bridge CLI composition root

- Status: Accepted
- Date: 2026-07-28
- Decision scope: `crates/bridge/src/main.rs`
- Coordination: Agent-Bridge forum thread #244
- Base revision: `25dd312ac842641c72069205641fc160eb114891`

## Context

`crates/bridge/src/main.rs` has accumulated command schema, startup policy,
dispatch, and command execution code in one binary crate root. At the accepted
base it contains 21,700 lines, 266 top-level symbols, 119 `run_*` functions,
and 32 top-level `Cmd` variants. Its broad regions are:

| Region | Approximate lines | Responsibility |
| --- | ---: | --- |
| CLI schema | 79-4376 | clap types, flags, and help contracts |
| startup and dispatch | 4534-8242 | early gates, dependency construction, command routing |
| command executors and helpers | 8243-21700 | short-lived CLI behavior and reports |

The file is also an active integration surface. Reproducible churn commands at
the accepted base report:

```text
git log --since='14 days ago' --numstat --format= -- crates/bridge/src/main.rs
  23 commits, +691/-48
git log --since='30 days ago' --numstat --format= -- crates/bridge/src/main.rs
  45 commits, +1628/-97
git log --since='90 days ago' --numstat --format= -- crates/bridge/src/main.rs
  238 commits, +22448/-989
```

Raw size alone is not the governing problem. The risk is that CLI schema,
startup authority boundaries, and unrelated command implementations share one
high-churn merge and review surface. A large mechanical split would amplify
that risk and make behavioral review harder.

`crates/bridge/src/mcp_tools.rs` is larger, but it is a separate governance
problem and is not part of this decision.

## Decision

Treat `main.rs` as a CLI composition root and reduce it through small,
behavior-preserving vertical extractions:

1. Keep top-level process startup, shared dependency construction, and
   cross-domain dispatch visible in `main.rs`.
2. Move a command family's clap subcommand types and its private execution
   helpers together when the family has a narrow dependency boundary.
3. Keep extracted modules binary-private unless a demonstrated library
   consumer exists.
4. Require each extraction to preserve public CLI spelling, clap schema and
   help, defaults and environment behavior, authority boundaries, exit status,
   stdout/stderr, and runtime effects.
5. Establish behavior evidence before moving code and compare it after the
   move.
6. Land audit/decision artifacts separately from implementation where
   practical, so either commit can be reviewed or reverted independently.

The active coordination boundary is localized:

- Red: `crates/bridge/src/main.rs`; structural edits require coordination.
- Yellow: `crates/bridge/src/lib.rs`, `crates/bridge/Cargo.toml`, and CLI
  help/snapshot fixtures; touch only when demonstrated necessary.
- Green: independent domain modules, documentation, and tests outside the
  composition-root seam.

This does not require stopping unrelated Agent-Bridge work.

## Pilot selection

Candidate families were scored qualitatively on cohesion, dependency width,
behavioral observability, authority risk, and expected merge surface.

| Candidate | Cohesion | Dependency width | Authority/runtime risk | Pilot fit |
| --- | --- | --- | --- | --- |
| A2UI validation + operator-request local control plane | high | narrow | low and explicitly bounded | selected |
| workflow-feedback reports | high | medium | low | later |
| substrate commands | medium | medium | storage/embedding initialization | later |
| BioCortex commands | high | broad | policy and feature-gate sensitive | not first |
| avatar commands | high | broad | process/UI/platform effects | not first |
| dream commands | medium | broad | large shared helper surface | not first |

The S1 pilot moves the adjacent `A2uiOp` and `OperatorRequestOp` schemas and
their execution helpers into one binary-private `cli::local_control` module.
Both commands execute before Hub construction, and the module's dependencies
are limited to A2UI validation, the local operator-request store, clap, JSON
serialization, and standard input/filesystem I/O.

## Baseline and acceptance gates

Before S1, the following help surfaces are captured from the accepted base:

```text
agent-bridge --help
  sha256 537d0a6e8e3ff00c56d95f0481e57f6d6c7f9437b2572986325f0598da69f09f
agent-bridge operator-request --help
  sha256 019f982babfde8069e80bbedb9e3e4d314976b69ab5c636dc2dee82c1baf18e3
agent-bridge a2ui --help
  sha256 81055b23475c3142691ac5fa74a6654e59af2fef8a7eacf95ce8e97604c72b09
```

S1 is accepted only when:

- the three captured help outputs compare byte-for-byte;
- focused schema and command tests pass;
- touched Rust files are formatted;
- `git diff --check` passes;
- `cargo check -p ab-bridge --all-targets --quiet` passes;
- no public schema, runtime enablement, or authority behavior is added.

## Consequences

The pilot removes one cohesive family from the composition root and establishes
a repeatable seam without making line count a success metric. Future slices
can reuse the rubric and gates, but each remains a separate decision and
reviewable change.

The trade-off is temporary mixed organization: some command families remain in
`main.rs` while extracted families live under `cli/`. That is intentional and
safer than a one-shot reorganization.

## Rejected alternatives

- Big-bang split of `main.rs`: rejected because churn and review scope make
  semantic drift and merge conflicts likely.
- Split `main.rs` and `mcp_tools.rs` together: rejected because it combines two
  distinct risk surfaces.
- Move only executor functions while leaving their schema behind: rejected for
  the pilot because it does not establish a complete command-family seam.
- Promote the pilot into the library crate: rejected because there is no
  demonstrated non-binary consumer.

## Rollback

Revert only the S1 implementation commit. The S0 ADR remains valid as an audit
record and does not change runtime behavior. If help or command behavior
diverges, do not compensate with compatibility aliases or schema changes;
restore the original in-file family and reassess the seam.
