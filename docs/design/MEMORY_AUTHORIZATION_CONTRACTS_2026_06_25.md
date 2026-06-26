# Memory Authorization Contracts

Date: 2026-06-25
Status: local continuity ledger

## Source State

This ledger records the current local authorization boundary for Agent-Bridge
memory-related work after reconnect, remote sync, and board sync. It was updated
after forum #120 post #4297 ratified GitLab as the Agent-Bridge canonical host.

Verified local sources:

- code checkout reconciled across GitLab/GitHub for this design slice:
  `master` at `33d55e0`; merge audit later observed both forges at `9e0d8cf`
  without changing this authorization boundary;
- visible board landing: design thread #120 post #4297;
- scope policy docs:
  `SCOPE_PROJECT_ID_CANONICAL_POLICY_2026_06_24.md` and
  `SCOPE_PHASE3_WRITE_TIME_PROJECT_ID_PLAN_2026_06_24.md`;
- GitLab-ratified follow-up plan:
  `docs/reports/goal-c-u/2026-06-25-scope-policy-write-switch-gitlab-ratified-plan.md`;
- T5/T6 evidence doc:
  `MEMORY_CONTINUITY_T5_T6_EVIDENCE_SURFACES_2026_06_19.md`.
- fleet-wide permission contract:
  forum #128 post #4241 and the #135/#4398 owner reframe. Ordinary
  recoverable project work is high-autonomy by default; peer authorization
  grants are not the intended model.

The pre-ratification GitHub recommendation packet
`docs/reports/goal-c-u/2026-06-25-scope-canonical-host-owner-decision-packet.md`
is superseded. Keep it as historical evidence only.

## Current Authorization Boundary

### Contract Overlay

Forum #128/#4241 and #135/#4398 supersede older stepwise-permission framing for
recoverable project work. Read this ledger as a boundary for production
memory/scope/ranking/runtime mutations, not as a requirement to request approval
for ordinary recoverable docs, tests, local commits, isolated branch pushes, AB
memory/forum coordination, or cleanup of agent-created temporary files.

The #135 reframe also rejects a peer-to-peer authorization-grant layer for the
trusted fleet. Cross-machine collaboration should synchronize coordination state
such as presence, forum posts, work claims, and handoff status; it should not
replicate authorization credentials. The six high-side-effect boundaries remain
owner/harness confirmation points because the actions are irreversible, external,
or governance-changing.

### Project Scope Identity

For production project-scope identity writes, current `master` authorizes trace
and report work only:

- `memory_save(scope_identity_trace=true)` may report identity evidence such as
  `scope`, `policy`, `env`, or `git_remote`;
- the trace path does not rewrite stored memory scopes;
- `AGENT_BRIDGE_PROJECT_ID` may be used for trace-only experiments, CI/smoke, or
  dedicated single-project MCP processes;
- shared MCP sessions must not rely on global `AGENT_BRIDGE_PROJECT_ID` as a
  production write policy.

Future production `project-id:*` writes require high-confidence evidence. Allowed
production candidates are explicit project IDs and reviewed git-remote/registry
policy. `GitRootName` and `PathFallback` remain diagnostic evidence only.

The owner-ratified Agent-Bridge canonical project ID is:

```text
project-id:git:gitlab.com/pallasting/agent-bridge
```

GitHub is a synchronized mirror and must not be treated as equivalent unless a
future owner decision explicitly supersedes #4297.

Not authorized as production mutations in this slice:

- switching stored `project:/...` rows to `project-id:*`;
- database migration or backfill;
- broadening `session_bootstrap` SQL;
- a new default MCP tool;
- automatic alias admission from basename-only matching.

### GHP-1b Related-Key Graph Hygiene

Visible board #105 records a reviewed 20-edge tiny batch, but not graph write
authority.

Authorized now:

- read-only review packets;
- `dry_run=true` materializer checks;
- semantic review of the hash-locked tiny batch;
- pre-write gate checks.

Required before any future `dry_run=false` materialize attempt:

- clean repo and current deployed binary;
- `agent-bridge.real doctor --json` with `fails=0` and `warns=0`;
- read-only SQLite `PRAGMA quick_check`;
- rescue snapshot;
- fresh dry-run whose selected edge-list hash matches the reviewed packet;
- exact project scope;
- 20-edge cap and 3/3 inbound/outbound caps;
- one-shot all-profile subprocess only, with no eager profile expansion.

Blocked conditions include stale MCP server warnings, changed edge-list hash,
failed quick check, changed scope, wider caps, or any missing pre-write gate.

Not authorized:

- graph edge writes;
- memory row writes;
- ranking, search-order, candidate-set, PageRank, or centrality influence;
- automatic orphan linking;
- expanding the compact/eager MCP tool surface for the writer.

### Trigger Recall / Pre-Policy Hold

The latest visible board post keeps the trigger recall line read-only on aio2.
The local corpus preflight is not runnable against the aio2 live DB because the
expected gold keys are absent.

Authorized now:

- read-only corpus/source-host preflight;
- report-only trigger recall policy evidence.

Not authorized:

- production retrieval changes;
- ranking, tokenizer, or schema changes;
- memory sync/import as an implicit eval repair;
- graph/PageRank influence;
- memory writes.

### BioCortex T5/T6 Candidate Expansion

Current `master` keeps BioCortex retrieval influence behind read-only evidence
and review gates. Runtime candidate expansion remains off.

Observed remote candidate branches from 2026-06-24/25 add a further T6 runtime
enablement review chain:

- shadow telemetry review;
- runtime-enablement review;
- owner decision record;
- implementation-plan artifact.

Those branches are not merged into `master` in this local audit. Treat them as
candidate/unmerged contracts, not deployed authority.

Even in those candidate contracts, every surface remains review-only. They do
not authorize runtime enablement, runtime influence, candidate expansion,
search-order changes, memory writes, graph-edge writes, or production behavior.

## Operator Rule

For memory-related work, a design document, review packet, owner-decision record,
or implementation-plan artifact is not enough by itself to mutate runtime or
store state. A future mutating step must name the exact authority it consumes,
show the current preflight evidence, preserve rollback, and state which
non-authorizations remain false.

This rule governs production/runtime/store mutation. It does not demote #128
default-autonomous recoverable work, including bounded docs/tests/branch/commit
work and AB memory/forum coordination, back into step-by-step approval.

When local board state and merged docs disagree, prefer the stricter boundary and
record the discrepancy before proceeding.
