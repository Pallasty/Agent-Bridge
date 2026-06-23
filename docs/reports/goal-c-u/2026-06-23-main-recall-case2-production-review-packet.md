# Main Recall Case #2 Production Review Packet

Date: 2026-06-23
Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)
Worktree: `/Data/CascadeProjects/agent-bridge`
Base: `0def902` (`docs(memory): design trigger query intent runtime gate`)
Scope: production review packet; no implementation

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
next_gate: read-only snapshot-open hardening and/or broader hard-case family review
```

This is a conservative acceptance of the evidence, not a rejection of the idea.
The eval result is strong for case #2, but too narrow to justify live retrieval
behavior.

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

## Production Options

| Option | Decision | Rationale |
|---|---|---|
| Reject the idea entirely | no | eval evidence is too useful to discard; case #2 target rank improves inside the role-aware projected family |
| Keep eval-only | yes | safest current state; preserves evidence without changing live behavior |
| Implement narrow runtime flag now | no | premature before snapshot-open hardening and broader hard-case review |
| Wire into default `memory_search` | no | too narrow, not yet aggregate-lifted, and would change live retrieval order from a single-family probe |

## Why Not Default Runtime

Default runtime wiring fails the current review for four reasons.

First, the proof is case-family-specific. The role-aware assembler is built for
tool-surface taxonomy/contraction/delete/re-tier queries. The main hard miss set
still includes #1, #8, #9, and #14, which have different failure classes.

Second, the measured hard-tier anchor has not moved. The current result proves a
candidate-level policy for case #2, not a production recall lift.

Third, the role policy relies on curated projection terms and adjudicated
candidate roles. That is acceptable for an eval harness, but it should not
become invisible production ranking logic without another review.

Fourth, the frozen-baseline report found that the current store open path can
create WAL state even when used as a snapshot for eval. The logical fingerprint
was stable, but production-lift review should harden or explicitly manage that
workflow before live retrieval behavior changes.

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

1. **Read-only snapshot hardening**
   - Add or document a truly read-only store-open / snapshot working-copy path.
   - Prove `AB_BASELINE_DB` comparisons do not mutate the source snapshot.

2. **Broader hard-case family review**
   - Decide whether #1, #8, #9, and #14 need separate projection families or a
     different rescue mechanism.
   - Avoid building a runtime path that helps only one hand-curated case.

3. **Eval aggregate mode**
   - Add a named eval-only aggregate row that includes role-aware case #2
     behavior while preserving hard-tier reporting.
   - Claim lift only if the hard-tier anchor moves under the same pinned
     fingerprint and no controls regress.

## Next Gate

Recommended next slice:

```text
main-recall-readonly-snapshot-open-hardening-v1
```

Alternative if another lane owns snapshot hardening:

```text
main-recall-hard-family-production-scope-review-v1
```

Either path should stay report/eval-first. No production retrieval code should
be changed until one of these gates closes.

## Aio2 Verification

Current Aio2 repository sanity after syncing to `0def902`:

```text
git status: clean before this report
cargo check -p ab-bridge --examples: pass
```

This host uses a smaller Linux/Aio2 live memory store than the Mac pinned
baseline. Therefore Aio2 live output is useful for compile sanity, not for the
case #2 production-lift claim.

## Boundary

This packet is a decision document only. It does not change production
`memory_search`, tokenizer/schema/reindex, ranking, graph expansion, semantic
retrieval, MCP tools, memory rows, deploy behavior, or the pinned snapshot.
