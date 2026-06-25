# Scope Phase 3 Project-ID Dry Run on aio2

Date: 2026-06-25
Status: report-only, no runtime mutation

## Context

This run follows `docs/design/SCOPE_PHASE3_WRITE_TIME_PROJECT_ID_PLAN_2026_06_24.md`
and the local authorization ledger:
`docs/design/MEMORY_AUTHORIZATION_CONTRACTS_2026_06_25.md`.

The goal was to verify the current aio2 state after MCP reconnect and deployment
before considering any write-time `project-id:*` shadow comparison.

This report does not change `MemorySaveTool`, does not write memory, does not
write graph edges, does not migrate state, does not add or expose an MCP tool,
and does not authorize production canonical project-scope writes.

## Environment

- repo: `/Data/CascadeProjects/agent-bridge`
- code state: `origin/master == 1fff9f7`
- MCP/doctor: `9 ok / 0 warn / 0 fail`
- git remote: `git@github.com:pallasting/Agent-Bridge.git`
- memory-sync: clean at the time of the run

## Commands

```bash
cargo run -p ab-bridge --example scope_canon_rescue_gate
cargo run -p ab-bridge --example scope_policy_admission_gate
cargo run -p ab-bridge --example scope_write_identity_dry_run

AB_SCOPE_CANON_GATE_CANONICAL=project-id:git:github.com/pallasting/agent-bridge \
  cargo run -p ab-bridge --example scope_canon_rescue_gate

AB_SCOPE_WRITE_DRY_RUN_PROJECT_ID=git:gitlab.com/pallasting/agent-bridge \
  cargo run -p ab-bridge --example scope_write_identity_dry_run

AB_SCOPE_WRITE_DRY_RUN_PROJECT_ID=git:github.com/pallasting/agent-bridge \
  cargo run -p ab-bridge --example scope_write_identity_dry_run
```

## Results

| Surface | Result | Important evidence |
|---|---:|---|
| `scope_canon_rescue_gate` default | PASS | registry recovered 258 local rows vs 254 basename rows; 4 worktree-suffix rows rescued; same-basename and parent-dir negatives stayed non-local |
| `scope_canon_rescue_gate` with explicit GitHub canonical | PASS | same 258 registry-local rows and 4 rescued rows, proving the gate can use an owner-chosen GitHub canonical |
| `scope_policy_admission_gate` | PASS | registered root/child admitted; unregistered sibling and parent dir `needs_review`; non-project and different project-id blocked |
| `scope_write_identity_dry_run` default | eligible | current aio2 remote proposes `project-id:git:github.com/pallasting/agent-bridge` with `evidence=git_remote`, `high_confidence=true`, `production_eligible=true` |
| `scope_write_identity_dry_run` explicit GitLab | eligible | explicit policy proposes `project-id:git:gitlab.com/pallasting/agent-bridge`, `evidence=explicit`, `production_eligible=true` |
| `scope_write_identity_dry_run` explicit GitHub | eligible | explicit policy proposes `project-id:git:github.com/pallasting/agent-bridge`, `evidence=explicit`, `production_eligible=true` |

Existing warnings were unchanged compile warnings only:

- `mixed_script_confusables` for the existing `β` test name;
- private-interface/dead-code warnings in `mcp_tools.rs`.

## Interpretation

The mechanism is ready for report-only and shadow-read evidence:

- the registry gate rescues real Agent-Bridge legacy scope fragments that
  basename matching misses;
- unregistered same-basename and parent-directory scopes remain blocked or
  `needs_review`;
- explicit project identity correctly outranks git remote evidence;
- aio2's current git remote can produce a high-confidence GitHub project ID.

However, this is not enough to start production write-time canonical scopes.
There is a canonical host decision still open:

- `scope_canon_rescue_gate` defaults to
  `project-id:git:gitlab.com/pallasting/agent-bridge`, matching older Mac-side
  trace/policy evidence;
- aio2's current remote and the policy admission gate default resolve to
  `project-id:git:github.com/pallasting/agent-bridge`;
- both explicit GitLab and explicit GitHub dry-runs are production-eligible, so
  the remaining question is an owner/policy choice, not resolver capability.

## Decision

Do not enable production `project-id:*` writes from this evidence alone.

Before any write-time shadow comparison or production write switch, create an
owner/policy record that chooses the canonical Agent-Bridge project ID host and
the reviewed alias registry that maps legacy scopes to that ID.

## Next Safe Slice

Prepare a canonical host decision packet with:

- candidate canonical ID: GitHub, GitLab, or an explicit non-host project ID;
- current evidence from Mac and aio2 checkouts;
- reviewed alias registry entries for `/Users`, `/Data`, `/Programs`, and known
  worktree suffix scopes;
- negative controls for same-basename different remote and parent-directory
  scopes;
- rollback rule: keep writing legacy `project:/...` scopes until the owner
  record is accepted.

Only after that record is accepted should the next slice run shadow write
comparison. Shadow comparison must still be no-op for store writes unless a
separate production write gate is approved.
