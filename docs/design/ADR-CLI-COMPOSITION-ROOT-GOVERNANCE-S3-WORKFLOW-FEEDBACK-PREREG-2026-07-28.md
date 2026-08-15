# ADR: Preregister workflow-feedback CLI adapter extraction

- Status: Accepted for preregistration; implementation remains a separate gate
- Date: 2026-07-28
- Decision scope: `crates/bridge/src/main.rs` workflow-feedback command family
- Coordination: Agent-Bridge forum threads #246 and #247
- Candidate revision: `00918dad8c478a959f82bea6c3ad9705a245d2d1`
- Prerequisite: GitLab and GitHub `master` must both contain the candidate

## Context

S0 established `main.rs` as the CLI composition root. S1 extracted the nested
A2UI/operator-request local-control family without changing its clap schema.
The next candidate named by the accepted S0 ADR is the workflow-feedback
family.

At the candidate revision, the family consists of seven flat root commands:

- `workflow-feedback-report`
- `workflow-feedback-shadow-score`
- `workflow-feedback-promotion-gate`
- `workflow-feedback-lift-evidence`
- `workflow-feedback-baseline-evidence`
- `workflow-feedback-owner-review-packet`
- `workflow-feedback-promotion-record`

Its code is split across three contiguous regions in `main.rs`:

| Region | Approximate lines | Responsibility |
| --- | ---: | --- |
| root `Cmd` variants | 423-605 | clap names, flags, defaults, and help |
| early dispatch | 7526-7651 | route before Hub construction |
| execution adapters | 8210-8425 | open the store when needed, call library report builders, render output |

The commands are cohesive and explicitly report-first. Six consume files and
delegate to `ab_bridge::workflow_feedback`; one opens the local store to build
a read-only report. None is permitted to change retrieval, memory, routing,
runtime policy, or authority.

The structural complication is that these are seven flat root variants rather
than a nested subcommand enum. Moving the schema behind a new parent command
would change public CLI spelling. Replacing the variants with tuple argument
types could also change clap help or parsing details unless separately proven.

## Options considered

| Option | Benefit | Cost and risk | Decision |
| --- | --- | --- | --- |
| Move schema, dispatch, and adapters together | maximum line reduction and family ownership | risks public clap drift for seven flat root variants; broad review surface | reject for the next slice |
| Move only execution adapters to `cli::workflow_feedback` | narrows implementation ownership while preserving root schema and routing | leaves a deliberate split boundary and removes fewer lines | select |
| Redesign under a `workflow-feedback` parent command | clean nested schema | breaking CLI change and migration burden | reject |
| Defer the family and choose a smaller command | lower immediate effort | leaves an already cohesive, low-authority family in the high-churn root | reject for now |

## Decision

Preregister a separate implementation slice that moves only the seven
`run_workflow_feedback_*` execution adapters into the binary-private
`cli::workflow_feedback` module.

Keep the following visible in `main.rs`:

1. all seven root `Cmd` variants and their clap attributes;
2. all early-dispatch matches and argument forwarding;
3. the unreachable exhaustiveness entries in the post-Hub dispatch.

This is a deliberate exception to the S0 preference for moving schema and
helpers together. The exception is justified by the flat-root public CLI
contract. It must not be generalized to nested command families.

The extracted module may depend on:

- `ab_bridge::workflow_feedback`;
- `ab_store::{default_db_path, SqliteStore}`;
- `anyhow`, `serde_json`, `PathBuf`, and standard environment/current-directory
  reads.

It must not receive `Hub`, daemon handles, mutable policy state, MCP registry
state, authorization state, or a general-purpose dependency container.

## Preserved invariants

The implementation gate must preserve:

- all seven command names, flags, defaults, required/repeated argument rules,
  help text, and parse failures;
- the current pre-Hub execution order;
- `AB_BASELINE_DB` behavior for `workflow-feedback-report`;
- stdout/stderr shape, JSON schemas, Markdown rendering, exit codes, and error
  context;
- read-only behavior and every existing non-authority claim;
- default tool profiles, MCP manifests, runtime admission, and memory state.

No command may be grouped under a new parent, aliased, renamed, or promoted to
a public library API.

## Implementation preregistration

Before moving implementation code, the implementation slice must capture from
the exact accepted base:

1. root `--help`;
2. `--help` for each of the seven workflow-feedback commands;
3. one valid machine-readable fixture path for each file-consuming adapter;
4. missing-file and malformed-fixture failures;
5. an isolated-store `workflow-feedback-report --json` result;
6. repository status and the exact base commit.

The first code change must add focused module-level tests that fail while the
adapters remain unavailable from the proposed module boundary. Only then may
the adapters move. Tests must exercise argument forwarding and output/error
selection without changing the library report builders.

Acceptance requires:

- byte-for-byte equality for all captured help output;
- fixture JSON equivalence after removing no fields;
- identical success and failure exit codes;
- focused adapter tests;
- existing workflow-feedback library tests;
- touched-file rustfmt and `git diff --check`;
- `cargo check --locked --offline -p ab-bridge --all-targets --quiet`;
- a clean worktree and an independently reviewable diff.

## Trade-offs

The selected boundary leaves schema and dispatch in `main.rs`, so the family
is not fully encapsulated. That is accepted because `main.rs` is explicitly
the composition root and the flat command names are part of its public
contract.

The slice removes less code than a schema migration. Line count is not the
success metric; reduced ownership of report construction and rendering is.

## Stop conditions

Stop and return to design if:

- a moved adapter needs Hub or mutable runtime state;
- clap output changes for any root or workflow-feedback command;
- an existing fixture cannot prove output equivalence;
- a library API change becomes necessary;
- S2 has not converged on both remotes;
- overlapping `main.rs` work appears without an explicit coordination handoff.

## Non-goals

This decision does not authorize:

- implementation in this S3 preregistration unit;
- CLI redesign or compatibility aliases;
- changes to workflow-feedback scoring or promotion semantics;
- memory writes, retrieval/routing changes, runtime enablement, deployment, or
  MCP reconnect;
- changes to `mcp_tools.rs`, Cargo manifests, or public library exports.

## Rollback

The S3 artifact is documentation-only and can remain as the decision record if
the implementation is abandoned. A later implementation must be one isolated
commit that can be reverted without reverting this ADR. Any behavior drift
requires restoring the adapters to `main.rs`, not compensating with new flags
or aliases.

## Revisit trigger

Reconsider complete-family schema extraction only after a separate clap proof
shows that module-owned argument types preserve all seven flat command
surfaces byte-for-byte and without introducing a parent command.
