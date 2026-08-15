# ADR: CLI composition-root governance S11 Dream HTML renderers

## Status

Accepted for implementation on 2026-08-02.

- Base: `ff934b7d06170c65de4a6ffbc5aeda4c82b2ec48`
- Coordination: Agent-Bridge forum thread #356
- Predecessor: S10 Walkthrough completed-content predicate, thread #354
- Scope: completed-result HTML rendering for `dream promote` and
  `dream codebase-report`
- Adoption posture: source-only; no deployment, restart, or reconnect

## Context

After S10, `main.rs` still owned two adjacent self-contained HTML renderers.
Both receive already completed Dream results and transform them into strings,
but their shared escaping, URL encoding, truncation, status styling, and bar
formatting surface occupied more than 700 lines in the composition root.

The surrounding executors are authority-bearing. `run_dream_promote` opens the
default Store, queries candidates and existing edges, chooses tier policy,
performs optional graph writes, orders terminal output and failures, and writes
the caller-selected report path. `run_dream_codebase_report` resolves the root,
opens and queries the Store, chooses text or JSON output, and writes the
optional report. Moving either executor would hide storage, mutation,
filesystem, stdout/stderr, error, and partial-effect ordering.

The original renderers also acquired wall-clock time internally. That made the
otherwise completed-result boundary dependent on ambient runtime state and
prevented fixed-input rendering. S11 therefore keeps UTC acquisition in the
composition root and passes the resulting string into the private renderer.

## Decision

Create binary-private `cli::dream` and move only:

- `PromoteDecision` and `PromoteStatus`, the immutable completed audit rows;
- `render_promote_html` and `render_codebase_report_html`;
- the pure Dream display helpers `short_key`, `truncate_chars`, `chip_class`,
  `html_escape`, `url_escape`, and `bar_pct`.

`main.rs` retains:

- the complete `DreamOp` Clap schema and dispatch;
- default database and caller-root selection;
- Store open, query, neighbor lookup, and promote mutation;
- tier policy, weight calculation, skip/error classification, and decision
  construction;
- UTC timestamp acquisition;
- report path selection and every filesystem write;
- text/JSON/stdout/stderr schemas and ordering;
- error context and `Result` custody.

The private module accepts completed values, a database path for display, and
an already captured timestamp. It returns `String` and has no environment,
filesystem, Store, process, async, stdout, error, or runtime dependency.

## Behavior contract

The S11 real-binary characterization suite freezes the empty-result paths for
both commands before movement. It checks exit status, exact stdout, empty
stderr, report creation, UTC timestamp shape and reuse, completed-report
identity, zero-result summaries, section labels, root/database display, and
empty-state guidance.

The characterization suite passed on unchanged base behavior. The ownership
test then failed at the expected missing `cli::dream` declaration and passed
after the minimal extraction. Timestamp acquisition remains immediately before
each renderer invocation, after all Store work and before the existing report
write.

## Authority contract

The ownership test requires schema, dispatch, both executors, Store access,
promote writes, root/default-path selection, UTC acquisition, report writes,
stdout/stderr, and return markers to remain in `main.rs`. It rejects Store,
environment, filesystem, path selection, system time, process, async, output,
and error authority inside `cli::dream`.

S11 does not change promotion thresholds, tiers, weights, edge types, query
limits, output schemas, report paths, HTML/CSS content, or error ordering. It
does not introduce a generic renderer framework, library API, MCP tool, runtime
enablement, or authorization for a later Dream executor move.

## Stop and revisit conditions

Stop if a follow-up requires moving Store initialization, queries, graph
mutation, root or report-path resolution, system time, filesystem writes,
stdout/stderr, error context, or effect ordering. A later Dream candidate must
be re-audited from current master and receive its own behavior and ownership
RED evidence.

## Verification

Required before landing:

- exact Dream promote/codebase-report CLI characterization;
- S11 ownership and authority-custody suite;
- adjacent private CLI extraction suites;
- scoped rustfmt and `git diff --check`;
- repository pre-commit all-target check;
- fresh `ab-bridge --all-targets` full test gate on reconciled master;
- non-force fast-forward and exact readback from both remotes.
