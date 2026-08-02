# ADR: CLI composition-root governance S12 AGENT.md drift classifier

## Status

Accepted for implementation on 2026-08-02.

- Base: `5719046753964b618575facc1c2f8210288f3aad`
- Coordination: Agent-Bridge forum thread #357
- Predecessor: S11 Dream HTML renderers, thread #356
- Scope: deterministic token, coverage, and triage classification for
  `dream agent-md-drift`
- Adoption posture: source-only; no deployment, restart, or reconnect

## Context

After S11, `main.rs` still owned an adjacent deterministic classifier used by
`dream agent-md-drift`. The classifier tokenises fixed text, computes a set
coverage ratio, and assigns a fixed triage decision from key, tags, content,
and literal marker lists. It does not need storage, filesystem, clock, process,
output, async runtime, or error authority.

The surrounding executor is authority-bearing. It resolves and reads the
caller-selected AGENT.md, opens the default Store, queries active lessons,
applies the time window, constructs proposal keys and content, optionally
writes `l7_proposed_update` memories, assembles the report, and selects JSON or
text output. Moving that executor would obscure file, database, mutation,
clock, serialization, output, error, and partial-effect ordering.

## Decision

Extend the binary-private `cli::dream` module and move only:

- `AGENT_MD_DRIFT_COVERAGE_THRESHOLD`;
- `drift_tokens` and `drift_coverage_ratio`;
- `AgentMdTriageDecision`;
- the private `contains_any` helper;
- `triage_agent_md_drift_candidate` and its fixed marker policy.

`main.rs` retains:

- the complete `DreamOp` Clap schema and dispatch;
- AGENT.md path selection and `std::fs::read_to_string`;
- default database selection, Store open, list, and active/window filtering;
- system-time acquisition and cutoff calculation;
- proposal key and content construction;
- every `memory_save` call and dry-run write decision;
- report assembly, JSON/text selection, stdout, and errors;
- the explicit human-review posture that AGENT.md is never auto-edited.

The root calls the classifier through private `cli` re-exports. The decision
type remains binary-private and is consumed by inference at the call site; it
is not promoted to a library API.

## Behavior contract

Before extraction, the real-binary characterization test passed on the
unchanged base and froze the empty-window JSON contract, empty stderr, dry-run
proposal count, and isolated Store creation. Existing unit tests froze token
selection, full/partial/zero/empty coverage, the 30% threshold, and stable,
transient, domain-specific, and implementation-specific triage outcomes.

The ownership test then failed at the expected missing `cli::dream` boundary.
It passes after the minimal move and also asserts that the executor, authority,
and human-adoption markers remain in `main.rs`.

## Authority contract

The ownership test rejects Store types and operations, AGENT.md path helpers,
environment and filesystem access, system time, serialization, output,
`Result`, async runtime, process execution, and Hub authority inside the
deterministic Dream module.

S12 does not change the 30% threshold, token rules, marker lists, decision
ordering, proposal schema, Store query, write behavior, output schema, or error
ordering. It does not auto-edit AGENT.md, introduce model inference, expose a
new library or MCP API, move the executor, deploy a binary, restart a process,
or authorize runtime adoption.

## Stop and revisit conditions

Stop if a follow-up requires moving AGENT.md path or file access, Store open,
queries or writes, cutoff-time calculation, proposal construction,
serialization, stdout/stderr, errors, human-review posture, or effect ordering.
Any threshold or marker-policy change is a behavior change and requires a new
characterization and review unit rather than being bundled into extraction.

## Verification

Required before landing:

- exact real-binary `dream agent-md-drift` characterization;
- existing helper and triage unit suites;
- S12 ownership and authority-custody suite;
- adjacent private CLI extraction suites;
- scoped rustfmt and `git diff --check`;
- repository pre-commit all-target check;
- fresh `ab-bridge --all-targets` full test gate on reconciled master;
- non-force fast-forward and exact readback from both remotes.
