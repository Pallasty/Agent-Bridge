# Main Recall Case #2 Production Review Packet

Date: 2026-06-23
Primary worktree: `/Users/pallasting/Projects/agent-bridge`
Scope: production review packet only; no runtime implementation

## Decision

Do not wire the case #2 role-aware projection assembler into default
`memory_search`.

Also do not implement a runtime flag in this slice. Keep the case #2
tool-surface path eval-only until the remaining measurement and scope risks are
closed.

Accepted status:

```text
case2_role_aware_eval: accepted as evidence
default_memory_search: rejected
runtime_flag_or_opt_in_mode: deferred
next_gate: broader hard-case family review, with snapshot hardening as the supporting gate
```

This is a conservative acceptance of the evidence, not a rejection of the idea.
The eval result is strong for case #2, but too narrow to justify live retrieval
behavior.

## Question

The case #2 role-aware eval assembler now succeeds in `recall_eval`:

- case #2 target moves from strict durable rank 2 to role-aware rank 1;
- diagnostic/meta candidates are excluded for generic tool-surface queries;
- negative controls remain clean;
- positive controls are 11/11 hits with 11/11 rank-1 primary-answer hits.

Should this become production retrieval behavior?

Answer: no for default production; not yet for opt-in production.

## Evidence Reviewed

| Report | Evidence |
|---|---|
| `2026-06-22-main-recall-hard-miss-autopsy.md` | case #2 is a candidate-visibility miss |
| `2026-06-22-main-recall-case2-tool-surface-projection-probe.md` | projection makes the target visible |
| `2026-06-22-main-recall-case2-tool-surface-negative-controls.md` | first hard negatives stay clean |
| `2026-06-23-main-recall-case2-tool-surface-positive-controls.md` | 11/11 intended family controls pass |
| `2026-06-23-main-recall-frozen-baseline-anchor.md` | lift claims must use a pinned store fingerprint |
| `2026-06-23-main-recall-case2-tool-surface-rank-adjudication.md` | strict candidates need role interpretation |
| `2026-06-23-main-recall-case2-runtime-design-sketch.md` | design shape forbids broad default expansion |
| `2026-06-23-main-recall-case2-eval-assembler.md` | role-aware eval assembler makes case #2 target rank 1 |

The strongest result is from the pinned Mac baseline:

```text
AB_BASELINE_DB=/Users/pallasting/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db
store fingerprint: pinned=true active=3022 edges=5527 newest=1782205313
toolproj hit: 2  toolproj_acc hit: 2  toolproj_acc_durable hit: 2  role_aware hit: 1
controls=6 nonempty_accepted=0 false_target_hits=0 work_memory_hits=0
controls=11 durable_hits=11 strict_hits=11 strict_cluster_hits=11 strict_empty=0 role_aware_hits=11 role_aware_rank1_hits=11
```

The standing hard-tier runtime anchor remains unchanged because the assembler is
eval-only:

```text
hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.000 semantic=0.125
hard fts misses: #1, #2, #8, #9, #14
hard zero-row fts misses: #1, #2
```

The Aio2/GitHub-side review input is useful as repository sanity and an
independent conservative read, but it is not the canonical case #2 production
lift evidence because it does not use the Mac pinned baseline.

## Eval Assembler Result

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

## Production Options

| Option | Decision | Reason |
|---|---|---|
| Reject the idea entirely | No | The eval evidence is too useful to discard; case #2 target rank improves inside the role-aware projected family. |
| Keep eval-only | Yes | Safest current state; preserves evidence without changing live behavior. |
| Implement a narrow runtime flag now | No | Premature before broader hard-case review and snapshot-open hardening. |
| Wire into default `memory_search` | No | Too narrow, not yet aggregate-lifted, and would change live retrieval order from a single-family probe. |

## Why Not Default Runtime

Default runtime wiring fails the current review for five reasons.

First, the proof is case-family-specific. The role-aware assembler is built for
tool-surface taxonomy/contraction/delete/re-tier queries. The main hard miss set
still includes #1, #8, #9, and #14, which have different failure classes.

Second, the measured hard-tier anchor has not moved. The current result proves a
candidate-level policy for case #2, not a production recall lift.

Third, the role policy relies on curated projection terms and adjudicated
candidate roles. That is acceptable for an eval harness, but it should not
become invisible production ranking logic without another review.

Fourth, the frozen-baseline report found that the current store-open path can
create WAL state even when used as a snapshot for eval. The logical fingerprint
was stable, but production-lift review should harden or explicitly manage that
workflow before live retrieval behavior changes.

Fifth, default `memory_search` is broad. Injecting a projection path into it can
alter unrelated queries unless the trigger, role policy, and observability are
stricter than the current proof requires.

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
evidence, and it still needs one more gate before implementation.

## What Is Approved

This packet approves the following evidence as reusable:

- `projtoolsurface` plus strict policy-term gating is a viable case #2
  diagnostic family;
- volatile candidate filtering is mandatory;
- role labels are mandatory before projected candidates can be interpreted;
- diagnostic/meta candidates are excluded by default;
- same-policy rows may be context, but must not outrank the primary taxonomy
  answer for the original case #2 query;
- any future implementation must compare against the same pinned
  `AB_BASELINE_DB` fingerprint.

## What Is Not Approved

This packet does not approve:

- default `memory_search` candidate expansion;
- default ranking changes;
- an MCP-visible opt-in retrieval mode;
- tokenizer/schema migrations;
- reindexing;
- graph/PageRank influence;
- semantic blending;
- memory writes;
- deploy behavior changes.

## Required Before Runtime Flag

Before even a disabled-by-default runtime flag is worth implementing, require at
least one of these gates:

1. **Broader hard-case family review**
   - Pick one more pinned hard miss, preferably #1 or #8.
   - Build an eval-only projection/role assembler for that family.
   - Require clean negative controls and a role-aware rank improvement.
   - Purpose: prove the mechanism is not only a tool-surface patch.

2. **Read-only snapshot hardening**
   - Add or document a truly read-only store-open / snapshot working-copy path.
   - Prove `AB_BASELINE_DB` comparisons do not mutate the source snapshot.
   - Purpose: strengthen production review evidence before runtime claims.

3. **Eval aggregate mode**
   - Add a named eval-only aggregate row that includes role-aware case #2
     behavior while preserving hard-tier reporting.
   - Claim lift only if the hard-tier anchor moves under the same pinned
     fingerprint and no controls regress.

## Next Gate

Recommended next slice:

```text
main-recall-second-hard-family-eval-v1
```

Reason: the highest remaining production risk is narrowness. Snapshot hardening
is also important, but a second hard family will tell us whether role-aware
projection is a general pattern or just a successful bespoke patch.

Alternative if another lane takes the second hard family first:

```text
main-recall-readonly-snapshot-open-hardening-v1
```

Either path should stay report/eval-first. No production retrieval code should
be changed until one of these gates closes.

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

This packet is a decision document only. It does not change production
`memory_search`, tokenizer/schema/reindex, ranking, graph expansion, semantic
retrieval, MCP tools, memory rows, deploy behavior, or the pinned snapshot.
