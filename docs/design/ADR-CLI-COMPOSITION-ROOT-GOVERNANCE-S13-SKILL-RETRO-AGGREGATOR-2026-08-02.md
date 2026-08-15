# ADR: CLI composition-root governance S13 SkillRetro aggregator

## Status

Accepted for implementation on 2026-08-02.

- Base: `956be2f73df291d961797de57774a721c5828ef0`
- Coordination: Agent-Bridge forum thread #359
- Predecessor: S12 AGENT.md drift classifier, thread #357
- Scope: deterministic report construction for `dream skill-retro`
- Adoption posture: source-only; no deployment, restart, or reconnect

## Context

After S12, `main.rs` still owned the complete SkillRetro read-model
aggregation. The aggregation receives an already queried vector of immutable
lesson records plus caller-supplied `now` and `cutoff`, projects report rows,
sorts them by access count, and computes consulted and mean-access metrics. It
does not need storage, filesystem, clock, process, output, async runtime, or
error authority.

The surrounding executor is authority-bearing. It selects the default
database, opens the Store, acquires wall-clock time, queries lesson memories,
filters active records inside the requested window, selects JSON or text
output, serializes the report, and orders errors and output. Moving that
executor would obscure database, time, filtering, serialization, output,
error, and effect ordering.

The existing `cli::dream` module owns completed HTML rendering and the pure
AGENT.md drift classifier. S12 also deliberately excludes Store record and
serialization-schema coupling from that module. S13 therefore creates a
separate binary-private `cli::skill_retro` module instead of turning
`cli::dream` into a replacement composition-root hotspot.

## Decision

Create binary-private `cli::skill_retro` and move only:

- `SkillRetroLessonRow`, the immutable projected row;
- `SkillRetroReport`, the deterministic report schema;
- `aggregate_skill_retro`, including row projection, descending access-count
  ordering, consulted ratio, and mean access-count calculation.

`main.rs` retains:

- the complete `DreamOp::SkillRetro` Clap schema and dispatch;
- default database selection and `SqliteStore::open`;
- `list_memories` and its query limit/sort policy;
- active-status and created-at window filtering;
- system-time acquisition and cutoff calculation;
- JSON serialization and all text/JSON stdout;
- empty-state and falsifiability guidance;
- error context and `Result` custody.

The private module accepts `Vec<ab_store::MemoryRecord>` only as an immutable,
already-authorized read-model input. It cannot open, query, or write a Store
and cannot acquire ambient time. The root calls the aggregator through a
private `cli` re-export; no library or MCP API is added.

## Behavior contract

Before extraction, a real-binary characterization test passed on unchanged
base behavior. It freezes command success, empty stderr, the complete
empty-window JSON value schema, the exact seven-day cutoff relationship,
runtime timestamp capture, zero metrics, empty rows, and isolated Store
creation.

The three existing unit tests freeze empty-input division behavior, consulted
count and ratio, mean access count, descending access-count ordering, row
consulted flags, and the all-consulted case. The ownership test then failed at
the expected missing module declaration and passed after the minimal move.

## Authority contract

The ownership test requires schema, dispatch, executor, default-path and Store
open, query, active/window filter, system time, serializer, stdout, error, and
falsifiability guidance to remain in `main.rs`. It rejects Store operations,
ambient time, environment and filesystem access, JSON serialization, output,
`Result`, async runtime, process execution, and Hub authority inside
`cli::skill_retro`.

S13 does not change report fields, JSON shape, query sort or limit, active or
window filters, access-count ordering, consulted definition, metric formulas,
empty-input semantics, timestamps, text output, or error ordering. It does not
move the archive-alarm predicate, introduce a generic Dream framework, expose
a library/MCP surface, deploy a binary, restart a process, or authorize runtime
adoption.

## Stop and revisit conditions

Stop if a follow-up requires moving default-path selection, Store open/query
or write, active/window filtering, system time, JSON serialization,
stdout/stderr, errors, or effect ordering. Any report/schema, sort, query,
filter, or metric change is a behavior change and requires a separate
characterization and review unit.

## Verification

Required before landing:

- real-binary `dream skill-retro` characterization;
- existing SkillRetro aggregation unit suite;
- S13 ownership and authority-custody suite;
- S5-S12 adjacent private CLI extraction suites;
- scoped rustfmt and `git diff --check`;
- repository pre-commit all-target check;
- fresh `ab-bridge --all-targets` full test gate on reconciled master;
- non-force fast-forward and exact readback from both remotes.
