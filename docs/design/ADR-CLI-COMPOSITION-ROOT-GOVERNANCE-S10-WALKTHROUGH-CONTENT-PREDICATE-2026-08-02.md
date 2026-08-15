# ADR: CLI composition-root governance S10 Walkthrough content predicate

## Status

Accepted for implementation on 2026-08-02.

- Base: `4c7690fe29e30f1f4b81683b3e192da1e43f18cb`
- Coordination: Agent-Bridge forum thread #354
- Predecessor: S9 ShellInit static snippet mapping, thread #352
- Scope: completed Walkthrough HTML content predicate only
- Adoption posture: source-only; no deployment, restart, or reconnect

## Context

After S9, `main.rs` still owned `walkthrough_region_has_content`, a pure
predicate over an already rendered HTML string. The predicate extracts the
existing `#ab-render` region through `ab_bridge::present::render_region` and
accepts only content-bearing Walkthrough markers: `wt-summary`, `wt-heading`,
`wt-narrative`, or `wt-ev`.

The surrounding `run_walkthrough` executor is authority-bearing. It selects
stdin or a caller-selected file, parses JSON, resolves the gallery directory,
writes an artifact, reads it back, composes the payload/content self-check,
prints text or JSON, and returns an error only after the artifact and output
already exist. Moving that executor would hide filesystem, stdout, error, and
partial-effect ordering behind a private adapter.

The adjacent `ContinuityReport` candidate was also audited and rejected. Its
pure Markdown and JSON rendering already lives on
`ab_bridge::continuity::ContinuityReport`; the root executor only retains
`AB_BASELINE_DB`, default database selection, asynchronous report acquisition,
error context, output selection, and stdout. Moving it would transfer authority
for negligible cohesion benefit.

## Decision

Create private binary module `cli::walkthrough` and move only
`walkthrough_region_has_content(&str) -> bool` into it.

`main.rs` retains:

- the complete `Cmd::Walkthrough` Clap schema and early dispatch;
- stdin versus file selection and all read errors;
- JSON parsing and its error context;
- gallery-directory selection, artifact write, and readback;
- payload extraction and `payload_ok && region_has_content` composition;
- text/JSON output schemas and key order;
- the write -> readback -> output -> error ordering for failed self-checks;
- `Result` propagation and return custody.

The private module receives only the completed HTML string and returns one
boolean. It has no filesystem, environment, path, JSON, Store, Hub, process,
async, stdout, error, or runtime dependency.

## Behavior contract

The S10 characterization suite freezes exact real-binary behavior for:

- successful human-readable output and artifact path;
- successful compact JSON bytes, including key order;
- empty-content failure exit code, stdout, stderr, and the existing artifact
  proving write-before-self-check ordering.

The suite passed on unchanged base behavior. The ownership test then failed at
the expected missing-module assertion before production movement and passed
after the minimal extraction.

## Authority contract

The ownership test requires schema, early dispatch, executor, input selection,
parsing, gallery path, write, readback, payload check, self-check composition,
output, error, and return markers to remain in `main.rs`. It rejects filesystem,
environment, path, JSON, Store, Hub, process, async, stdout, and error authority
inside `cli::walkthrough`.

S10 does not change which rendered markers count as content. It does not move
`run_walkthrough`, introduce a generic renderer framework, change artifact
format or storage, add an MCP tool, or authorize a later Walkthrough move.

## Stop and revisit conditions

Stop if a follow-up requires moving input, filesystem, gallery, payload,
self-check composition, output, error, or return ordering. A later candidate
must be re-audited from current master and receive its own behavioral and
ownership RED evidence. `ContinuityReport` remains closed unless a new pure
root-owned seam appears.

## Verification

Required before landing:

- exact Walkthrough CLI parity suite;
- S10 ownership/custody suite;
- existing Walkthrough marker-channel unit test;
- adjacent private CLI extraction suites;
- scoped rustfmt and `git diff --check`;
- repository pre-commit all-target check;
- fresh `ab-bridge --all-targets` test gate on reconciled master;
- non-force fast-forward and readback from both remotes.
