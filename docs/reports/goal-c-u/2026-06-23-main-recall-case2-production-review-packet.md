# Main Recall Case #2 Production Review Packet

Date: 2026-06-23
Host: `maxiaodeMac-Pro.local`
Worktree: `/Users/pallasting/Projects/agent-bridge`
Base: `d8f1547` (`test(memory): add case2 role-aware eval assembler`)
Scope: production review only; no runtime implementation

## Question

The case #2 role-aware eval assembler now succeeds in `recall_eval`:

- case #2 target moves from strict durable rank 2 to role-aware rank 1;
- diagnostic/meta candidates are excluded for generic tool-surface queries;
- negative controls remain clean;
- positive controls are 11/11 hits with 11/11 rank-1 primary-answer hits.

Should this become production retrieval behavior?

## Evidence Package

### Baseline Identity

The accepted comparison target is the pinned snapshot, not live-store-only
output:

```text
AB_BASELINE_DB=/Users/pallasting/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db
store fingerprint: pinned=true active=3022 edges=5527 newest=1782205313
```

The current hard-tier production anchor remains:

```text
hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.000 semantic=0.125
hard fts misses: #1, #2, #8, #9, #14
hard zero-row fts misses: #1, #2
```

### Eval Assembler Result

The role-aware assembler is eval-only and not wired into production retrieval:

```text
toolproj hit: 2
toolproj_acc hit: 2
toolproj_acc_durable hit: 2
role_aware hit: 1
```

Role-aware case #2 top set:

```text
1. primary     reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618
2. same-policy goal_b_surface_growth_gate_engine_finding_20260621
3. adjacent    mcp_codex_native_overlap_surface_narrowed_deployed_20260617
```

Excluded by default for generic tool-surface query:

```text
tool_diagnostics_plan_load_lookup_miss_20260619
goal_c_recall_eval_falsifier_anchor_contribution_20260621
```

Controls:

```text
negative controls: controls=6 nonempty_accepted=0 false_target_hits=0 work_memory_hits=0
positive controls: controls=11 ... role_aware_hits=11 role_aware_rank1_hits=11
tests: 20 passed
```

## Review Decision

Options reviewed:

| option | decision | reason |
|---|---|---|
| Reject as too narrow | Not chosen | The eval evidence is real: the role-aware assembler fixes the case #2 rank failure and keeps controls clean. Discarding it would lose a useful hard-miss recovery pattern. |
| Keep eval-only until more hard cases | Chosen | The evidence is strong but still one projection family. A default runtime path needs at least one more hard-miss family or an explicit owner decision to ship a case #2-only opt-in. |
| Implement behind a narrow opt-in flag | Conditional later | Plausible only after the next gate. It must remain disabled by default and report trigger/candidate/rank evidence when it fires. |

Verdict:

```text
NO-GO for default production memory_search.
CONDITIONAL-GO for a narrow opt-in experiment after one more gate.
KEEP the role-aware assembler in recall_eval as the current evidence harness.
```

This is not a rejection of the idea. It is a rejection of wiring a
case-specific projection directly into default recall from a single hard case.

## Rationale

### Why Default Production Is Not Ready

1. **Single-family proof**: the assembler is strong for tool-surface policy
   queries, but the hard-tier miss set also includes #1, #8, #9, and #14. A
   default runtime path needs evidence that it does not become another
   case-specific patch.
2. **Projection is hand-curated**: current role labels rely on known
   tool-surface tokens and known distractor classes. That is acceptable in eval,
   but risky as an implicit global ranking layer.
3. **Snapshot-open caveat remains**: the frozen-baseline report showed current
   `SqliteStore::open` can create WAL state on the snapshot. Fingerprint and
   hard-tier lines were stable, but production gate claims still need a cleaner
   read-only or managed-working-copy story.
4. **Hard-tier aggregate is unchanged**: the eval assembler proves case-level
   movement for #2, but the standing production modes still report the same
   hard-tier anchor. The production lift claim has not yet been measured as a
   runtime mode.
5. **Safety surface**: default `memory_search` is broad; injecting a projection
   path into it can alter unrelated queries unless the trigger, role policy, and
   observability are stricter than the current proof requires.

## Production Blast Radius

There are two possible implementation boundaries, and they do not carry the
same risk.

### Store-Level Default Path

Changing `SqliteStore::memory_search` would affect more than one user-visible
surface:

- MCP `memory_search` with default/FTS mode calls the store path directly;
- MCP hybrid search uses the store FTS path as one of its baseline inputs;
- scope filtering, Seed boost, coactivation rerank, trace writing, and
  caller-side kind filtering run after the initial result set is chosen;
- exact-key fallback and OR fallback are shared behavior, not case #2-specific
  behavior.

That is too wide for the current evidence. A store-level default change should
wait until the mechanism has at least two hard-miss families, a stable
before/after gate, and a rollback switch.

### MCP or Eval-Approved Opt-In Path

A narrower path can contain the blast radius:

- expose it only through an explicit mode/flag or eval-approved cohort;
- run it only after baseline FTS misses or after a known hard-miss gate selects
  the cohort;
- report the projection terms, accepted candidates, role labels, and final
  ranks;
- leave default store ordering untouched.

This is the only implementation boundary that is plausible from current
evidence.

### Why Narrow Opt-In Remains Plausible

The evidence is too good to discard:

- the trigger can be made narrow: zero-row FTS or verified hard miss;
- case #2 query emits a strong five-term projection;
- negative controls remain empty;
- role-aware sorting fixes the specific rank failure;
- diagnostic/meta rows can be excluded by explicit rule;
- all proof can be reproduced against a pinned `AB_BASELINE_DB`.

So the next productive step is not default production. It is a constrained
experiment that preserves the eval harness as the authority.

## Conditional Implementation Path

The earliest acceptable production candidate would be:

```text
opt-in only, disabled by default
```

Required shape:

- guarded by explicit env/config flag, for example
  `AB_MEMORY_ROLE_AWARE_PROJECTION_EXPERIMENT=1`;
- only active for FTS-like recall paths;
- only active when baseline FTS returns zero rows or when an explicit
  eval-approved hard-miss cohort is selected;
- only active when projection terms include `projtoolsurface` plus at least
  three additional policy terms;
- durable hygiene is mandatory: exclude volatile scratch rows, `skill:` rows,
  archived/superseded rows, and non-active rows;
- role-aware filtering is mandatory: primary and same-policy allowed;
  adjacent demoted; diagnostic/meta excluded unless the query explicitly asks
  for those domains;
- every activation logs or reports enough evidence to audit trigger terms,
  projected candidates, role labels, and final rank positions.

This should still be treated as experimental. It should not silently replace
the existing `memory_search` ordering.

## Required Next Gate

Before any opt-in runtime implementation, complete one of these:

1. **Preferred**: `main-recall-second-hard-family-eval-v1`
   - Pick one more pinned hard miss, preferably #1 or #8.
   - Build an eval-only projection/role assembler for that family.
   - Require clean negative controls and a role-aware rank improvement.
   - Purpose: prove the mechanism is not only a tool-surface patch.

2. **Alternative**: `main-recall-readonly-snapshot-open-v1`
   - Add a read-only or managed-working-copy path for eval snapshots.
   - Purpose: strengthen production review evidence before runtime claims.

3. **Fallback**: `main-recall-case2-optin-design-v1`
   - Write a concrete opt-in implementation plan without coding it.
   - Include env flag name, code boundary, tests, rollback, and MCP reconnect
     proof.

Recommended next step:

```text
main-recall-second-hard-family-eval-v1
```

Reason: the highest remaining production risk is narrowness, not case #2
quality. A second hard family will tell us whether role-aware projection is a
general pattern or just a successful bespoke patch.

## Production Go/No-Go Checklist

Default production remains **NO-GO** until all are true:

- at least two hard-miss families have eval-only role-aware assemblers;
- pinned before/after evidence shows hard-tier movement without masking
  regressions;
- negative controls remain clean across both families;
- diagnostic/meta rows are demonstrably excluded unless requested;
- snapshot identity is stable enough for gate claims;
- production path is either opt-in or has an explicit rollback flag;
- MCP/live verification plan is written before deploy.

## Boundary

This packet does not change production `memory_search`, tokenizer/schema/reindex,
ranking, graph expansion, semantic retrieval, MCP tools, memory rows, deploy
behavior, or the pinned snapshot. It only records the production review decision
for the case #2 role-aware eval assembler.
