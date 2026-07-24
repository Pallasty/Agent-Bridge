# Free Recall Strategy R1 — Frozen-Snapshot Replay Result

Date: 2026-07-21

Status: **BLOCKED BEFORE SCORING / NO STRATEGY VERDICT / NO RUNTIME AUTHORITY**

Preregistration:
`docs/design/FREE_RECALL_STRATEGY_R1_FROZEN_SNAPSHOT_PREREGISTRATION_2026_07_21.md`

## 1. Result

R1 did not compare the six preregistered strategy arms. It stopped at the
query-order falsifier because the existing public `memory_search` Hybrid path
does not bind one logical `as_of` value across replay observations.

This is an instrumentation result, not evidence for or against multiple memory
strategies. No arm scores, gate decisions, or runtime recommendations may be
derived from this run.

## 2. Preconditions that passed

- The three committed fixtures retained their preregistered SHA-256 values.
- The tb14 source store contained all 65/65 referenced keys, all active.
- The source SQLite connection was read-only (`mode=ro`, `query_only=ON`) and
  recorded zero changes.
- Every observation used a fresh disposable clone of one online-backup base.
- Before each query, `/proc/<pid>/fd` inode identity proved that the MCP child
  had opened the disposable clone; stderr independently confirmed its path.
- The binary stayed fixed at Agent-Bridge 0.14.0; binary SHA-256 was
  `d9daa34b02d85722ae473a6583fd18a2cb1927a31505b958005d4c7cacfc9869`.
- BioCortex, seed boost, outcome collection, and the tb14 deployment's disabled
  coactivation rerank policy were explicitly bound in every child process.
- FTS top-20 pages passed the forward-versus-reverse order falsifier.

No private database, memory content, raw query, embedding, or memory key was
written to the repository.

## 3. Blocking evidence

With a fresh clone for every query and mode, Hybrid top-20 pages still differed
between forward and reverse replay order:

- changed cases: 16 of 44;
- task classes affected: conditional retrieval, relational, and synthesis;
- two cases changed at rank 1;
- other first differences occurred from ranks 2 through 20;
- no result JSON was emitted.

The diagnostic exposed only case IDs, first-difference ranks, and page hashes.
It never exposed page keys or query text.

## 4. Root-cause boundary

The store already has deterministic tie-breakers and internal frozen-clock
methods for FTS and Hybrid. The production MCP path does not expose that clock:

- ordinary FTS calls `memory_search_as_of(..., now_secs())`;
- ordinary Hybrid calls `memory_search_hybrid_as_of(..., now_secs(), ...)`;
- semantic ranking also resolves `now_secs()` while blending its small memory
  recency/access term;
- the MCP `memory_search` request has no evaluation-only `as_of` parameter.

The direct FTS top-20 happened to remain stable, but that does not make the
clock controlled. Hybrid's wider FTS pool and graph fusion can amplify small
time-sensitive rank changes into page changes. The evidence supports
"unbound wall clock is a remaining variable"; it does not yet isolate one
specific changed row or prove that no other ambient input contributes.

Two earlier harness defects were found and corrected before this final run:

1. `capabilities.memory.db_path` reports the platform default rather than the
   Hub's resolved `AGENT_BRIDGE_DB`; clone binding is now proved by inode and
   stderr evidence instead.
2. Directly launching `agent-bridge.real` bypassed the wrapper's `machine.env`;
   the runner now explicitly binds tb14's disabled coactivation-rerank policy.

Neither correction produced or inspected strategy scores.

## 5. Decision

R1 is honestly **blocked before scoring**. Exact page equality remains the
preregistered stopping rule; it is not weakened to gold-only equality after
seeing the failure.

The next eligible lane is R1.1: add an evaluation-only frozen-clock adapter for
all three existing modes, then rerun the unchanged fixtures, arms, budgets,
router, and decision gates. The adapter must:

- require an explicit non-negative `as_of_secs`;
- operate only on a caller-selected disposable SQLite clone;
- suppress read-side telemetry and adaptive writes;
- preserve the production algorithms and configured weights apart from binding
  the clock;
- fail closed on unsupported backends or missing clock binding;
- remain outside the default MCP/runtime surface;
- pass forward/reverse exact-page equality before any strategy score is emitted.

R1 does not authorize changing production retrieval order, deploying code,
running BioCortex, training a router, or merging this branch.
