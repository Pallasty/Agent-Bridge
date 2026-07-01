# Thread 105 Controlled RSI Status Audit

Date: 2026-07-01

Status: `READ_ONLY_STATUS_AUDIT / NO_RUNTIME_CHANGE / NO_BOARD_STATUS_CHANGE`

## Decision

Thread #105 should remain open as the Controlled RSI / Goal C continuity
ledger, not as a single active implementation queue.

The latest concrete implementation and verification lanes cited by #105 are
closed or gated:

- trigger-recall production `enforce_hold` remains parked and owner-gated;
- project-id scope production writes remain blocked;
- local GTE runtime state is already on `gte-multilingual-base` 768d;
- recall-eval active-corpus scoring and snapshot corpus-health gate are landed;
- stale projection probe output is diagnostic-only;
- correction co-surface S2 remains separately owner-gated by the current #102
  readiness review.

Do not infer authorization for default `memory_search`, retrieval ranking,
memory writes, graph writes, project-id production writes, or live runtime gates
from #105 without a fresh scoped owner packet.

## Evidence

Current repo state:

```text
## master...origin/master
HEAD f3bedb9 docs(memory): review correction cosurface s2 readiness
```

Current runtime checks:

| Check | Result |
|---|---|
| `agent-bridge.real doctor --json` | `ok=true`, `fails=0`, `warns=0`; 11 MCP servers all current `.real` |
| `mcp_lifecycle_digest` | lifecycle `ready`, readiness `ready`, runtime health `ready`, failing tools `0` |
| `continuity-report --json` | active_total `689`, embedded `689`, dominant_backend `gte-multilingual-base`, stale_vectors `0` |
| `recall_eval --check-corpus` | cases_total `18`, cases_with_present `9`, cases_with_active `9` |

`recall_eval --check-corpus` emitted only existing warnings:

- mixed-script confusable warning for the existing Greek-beta test name;
- private-interface/dead-code warnings already present in `mcp_tools.rs`.

## Thread #105 Current Readout

| Area | Current state |
|---|---|
| Trigger recall opt-in | Read-only/status/trial surfaces and batch diagnostics landed. Production `enforce_hold` was rejected/parked unless a future owner packet reopens it. |
| Trigger pre-policy hold | Review/smoke packets exist, but production implementation remains blocked. Default `memory_search` remains unchanged. |
| Scope canonicalization | Project identity and explicit alias read path landed; scope write shadow comparison landed. Production project-id writes, DB migration/backfill, search broadening, and global env policy remain blocked. |
| Authorization ledger | `agent_bridge_memory_authorization_contracts_20260625` plus reversible-autonomy clarification define the current boundary: reversible operator maintenance is allowed, but subsystem runtime authority still needs explicit gates. |
| GTE 768 migration | aio2/local node migration is complete; local runtime switch plan is closed as a no-op for this node. Fleet/Mac follow-ups are not automatic local work. |
| Post-scope plan | `agent_bridge_post_scope_shadow_followups_20260625` is complete 3/3. |
| Recall eval denominator | `c8547c1` active-corpus filter landed; current live check shows 18 defined / 9 present / 9 active cases. |
| Canonical snapshot gate | `7f98b85` records/enforces corpus health expectations for frozen snapshots. |
| Stale projection probe labels | `5b1e388` labels stale/skipped probes as diagnostic-only. |

## Open But Gated

These should not be auto-implemented from #105 alone:

- production trigger-recall `enforce_hold`;
- default `memory_search` changes or hidden search parameters;
- project-id production writes or scope DB backfill;
- retrieval ranking/candidate-set/PageRank influence;
- graph or memory writes beyond separately authorized lanes;
- long-lived correction co-surface S2 windows;
- BioCortex/T6 runtime influence;
- fleet-wide GTE or cross-node migration changes.

## Safe Next Shapes

1. Keep #105 open as a standing continuity ledger.
2. Use #105 as an evidence index when a future owner packet names a specific
   lane and acceptance gate.
3. Prefer read-only verification or docs-only status updates unless a fresh
   owner decision explicitly opens a gated implementation window.
4. If board hygiene continues, mark older digest open-questions inside #105 as
   historical/stale in a separate proposal rather than resolving #105 outright.

## Boundary

This audit did not:

- change #105 status;
- edit runtime configuration or restart services;
- deploy binaries;
- write memory rows, graph edges, schemas, or embeddings;
- change retrieval, ranking, candidate selection, model selection, or tool
  routing;
- open production trigger-recall, scope-write, co-surface, BioCortex, or GTE
  runtime gates.
