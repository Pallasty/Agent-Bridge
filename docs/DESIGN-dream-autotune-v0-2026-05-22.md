# DESIGN — `dream autotune` v0 (autonomous hygiene-param tuning)

**Status**: Backlog (design phase only — NOT scheduled for impl)
**Author**: aio2:agent-bridge:main#3b568a5f
**Date**: 2026-05-22
**Source inspiration**:
- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — autonomous overnight experiment loop (edit → time-box → measure → keep/discard → repeat). Minimal 630-line ML PoC.
- [uditgoenka/autoresearch](https://github.com/uditgoenka/autoresearch) ("Claude Autoresearch") — **stronger template**: generalizes karpathy to any measurable-metric domain as a Claude Code skill (41-line router + 12 commands). Already has the ledger + rollback + guard + bounded-iteration + anti-self-deception that this memo otherwise designs from scratch. **But its git-per-iteration memory model is incompatible with our multi-sibling shared-master workflow** (see §0.1).

**See also**: `memory/research_context_mode_rtk_comparison_2026_05_17.md` (sibling research-borrow pattern)

---

## §0 Framing

karpathy/autoresearch's value is the **autonomy pattern**: define a fast objective metric, let an agent iterate unattended overnight (modify → train 5min → check `val_bpb` → keep/discard). Its weaknesses — no overfitting protection, no cross-iteration ledger, single-metric — are exactly what agent-bridge's existing discipline already covers (pre-registered falsifiable thresholds + forum/memory ledger).

**The mismatch**: substrate metrics (M7 r_touched) evolve over DAYS, so you cannot run 100 substrate experiments overnight. But **hygiene parameters** have fast objective functions (run a replay → measure an audit metric). Those are autotune-able.

`dream autotune` v0 = the keep/discard loop, **grafted onto agent-bridge's falsifiability + ledger**, scoped to fast-objective hygiene params only.

## §0.1 uditgoenka/autoresearch — stronger template, incompatible memory model

Comparison (2026-05-22):

| Capability | karpathy | uditgoenka | this memo's plan | agent-bridge has |
|---|---|---|---|---|
| Ledger | none | git commits + TSV log | forum + memory (§4) | sqlite+embed+forum |
| Auto-rollback | none | `git revert` on fail | (not designed) | manual |
| Guard mechanism | none | metric-opt while guard cmd never breaks | (implicit in holdout) | pre-commit hook |
| Bounded iteration | unbounded | default 25 | candidate-list bounded | calendar-anchored |
| Anti-self-deception | none | multi-persona (predict/reason/probe) | holdout + pre-register (§3) | verify-design-act + frame-audit |
| Form factor | ML script | **Claude Code skill** | `dream` subcommand | we run on CC |

**Why NOT install uditgoenka directly**:
1. **git-per-iteration pollutes shared master** — agent-bridge has multiple sibling sessions on one master branch; dozens of `experiment:` commits would pollute coordination history + trigger `agent-bridge-sync.timer` churn. Our memory/forum ledger is the right substrate, not git commits.
2. **generic-metric needs glue** — "any number you can measure" still requires custom measurement adapters for our objectives (lesson access rate, M-metrics).
3. **single-machine iterate-on-code** vs our multi-agent forum-coordinated, days-scale substrate.

**What to borrow from uditgoenka** (patterns, not the tool):
- **TSV results log** (iteration, candidate, metric, delta, status) → but write to memory/forum, not git
- **Guard mechanism** (optimize objective while a guard invariant — e.g. `cargo check` — never breaks)
- **Bounded iterations by default** (already have: candidate list is finite)
- **Multi-persona adversarial refinement** (predict/reason/probe) → maps to our frame-audit; could strengthen §3 anti-overfitting with an adversarial "is this objective proxy actually valid?" persona pass

---

## §1 What gets tuned (fast-objective params only)

| Param | Env / config | Objective metric | Why it needs tuning |
|---|---|---|---|
| `AGENT_BRIDGE_CURATE_SCORE_THRESHOLD` | precompact hook env | 14-day lesson access rate | Day-7 A-audit found 16.9% vs 30% target (forum #325) |
| `AGENT_BRIDGE_CURATE_DEDUP_JACCARD` | precompact hook env | dedup precision (fewer near-dup lessons) | unmeasured; likely too loose |
| decay τ (`memory_decay_unused`) | daemon bg / cron | M3 coactivation retention vs M6 active count | M6 dropped 664→207; τ may be over-pruning |
| archive threshold (`ζ-15`) | dream config | catalog-vs-working balance | C3 alert s2-drop was archive-driven |
| bootstrap per-block budgets | `mcp_tools.rs` consts | bootstrap p95 token size vs "missed context" reports | shipped 16ae3ea; budgets hand-picked |

**v0 scope = ONE param**: `CURATE_SCORE_THRESHOLD` (the one with a measured gap). Prove the loop, then generalize.

**Explicit non-target**: substrate internals (projection, grid size, perception) — those evolve over days, not autotune-able.

---

## §2 The loop

```
dream autotune --param CURATE_SCORE_THRESHOLD \
               --candidates 0.3,0.4,0.5,0.6 \
               --objective lesson_access_rate \
               --holdout-frac 0.3
```

1. **Pre-register** (write to forum + memory BEFORE running): objective = "14-day lesson access rate ≥ 30%", candidates, holdout split. This is the anti-p-hacking gate karpathy lacks.
2. **Split** historical transcript corpus → train (70%) / holdout (30%) by session_id hash (deterministic).
3. **For each candidate**: replay train-set transcripts through `session_curate` at that threshold → measure proxy objective (how many extracted lessons would be accessed, using the existing access-history join).
4. **Keep best** on train-set.
5. **Validate on holdout**: re-measure best candidate's objective on the held-out 30%. If holdout objective < train objective by > tolerance (e.g. 5pp) → **overfitting detected, REJECT** (don't ship the param).
6. **Ledger**: write result (all candidates + train/holdout scores + decision) to forum thread 6 + a `project_autotune_<param>_<date>` memory.
7. **Apply** only if holdout-validated: update the env default in wrapper / config.

---

## §3 Anti-overfitting (the karpathy gap, closed)

- **Held-out validation** (§2.5) — best-on-train must survive holdout, else rejected
- **Pre-registration** (§2.1) — objective + threshold declared before running, can't be moved post-hoc
- **Deterministic split** (session_id hash) — reproducible, no cherry-picking the split
- **Minimum sample floor** — per sibling lesson `spec-must-bound-minimum-dataset-2026-05-20`: if train or holdout has < N qualifying sessions, ABORT (don't tune on noise)

---

## §4 Ledger (the karpathy gap, closed)

Every autotune run writes:
- **forum thread 6** finding post: param, candidates, train/holdout scores, keep/reject decision
- **memory** `project_autotune_<param>_<date>`: same + cross-link to the audit metric it optimized
- This makes autotune runs **auditable + reversible** — unlike karpathy's ephemeral overnight log

---

## §5 Verify phase (before any impl)

1. **V1** — confirm the objective is measurable offline: can we replay historical transcripts through `session_curate` with a given threshold and get a deterministic lesson set? (May need a `session_curate --dry-run --threshold X` mode.)
2. **V2** — confirm "lesson access rate" is joinable: extracted lesson key → memory_query_log access count within N days. Is the join clean?
3. **V3** — corpus size: how many historical transcripts qualify? If < ~30 sessions, the holdout split is too small → autotune not yet viable, defer until corpus grows.
4. **V4** — does changing `CURATE_SCORE_THRESHOLD` actually change the extracted lesson set materially? If the threshold is in a flat region, tuning is pointless.

§5 outputs gate whether §1-§4 are worth implementing.

---

## §6 Falsifiable acceptance (v0)

| Metric | Target |
|---|---|
| autotune picks a threshold that survives holdout | holdout objective ≥ train − 5pp |
| applied threshold improves 14-day lesson access rate | ≥ 30% (vs current 16.9%) measured at next Day-N audit |
| zero p-hacking incidents | holdout-reject path fires at least once in testing (proves the guard works) |

If after applying the autotuned threshold the real 14-day access rate does NOT reach 30%, the **objective proxy was wrong** (replay-access ≠ real-access) → v0 FALSIFIED, learn + redesign.

---

## §7 Risk + non-goals

**Risks**:
- R1: replay-access proxy ≠ real-session-access → optimizing the wrong thing. Mitigation: §6 falsifiable check at real Day-N audit.
- R2: corpus too small for holdout (§5.V3) → defer.
- R3: autotune becomes a maintenance burden if params interact. Mitigation: v0 = single param, no joint optimization.

**Non-goals**:
- Substrate internal tuning (days-scale objective)
- Joint multi-param optimization (v0 = one param)
- Continuous online tuning (v0 = manual `dream autotune` invocation, not a cron)
- Replacing human judgment on architecture decisions — autotune only touches scalar hygiene knobs

---

## §8 Backlog priority

**LOW-MEDIUM**. Rationale:
- The gap is real (lesson access 16.9% vs 30%) but not blocking
- Manual one-shot threshold tuning (try 0.5, measure at Day-14) is cheaper than building the loop for ONE param
- `dream autotune` only pays off when there are **multiple** fast-objective params to sweep repeatedly
- Recommend: do the MANUAL tune of CURATE_SCORE_THRESHOLD first (cheap), and only build `dream autotune` if 2+ more params surface needing repeated tuning

### Revised path (post uditgoenka comparison, 2026-05-22)

| Step | Action | Cost |
|---|---|---|
| **near-term** | Manual tune `CURATE_SCORE_THRESHOLD` (try 0.5, measure at Day-14 audit) | ~0 (env change) |
| **if automating** | Build `dream autotune` borrowing uditgoenka's 4 patterns (§0.1) — TSV ledger / guard-cmd / bounded / multi-persona — but with **memory/forum ledger, not git-per-iteration** | ~1-2d |
| **NOT recommended** | `npx` install uditgoenka skill directly — git-commit-as-memory conflicts with multi-sibling master workflow (§0.1.1) | — |

→ **Park until**: (a) §5 verify passes AND (b) ≥ 3 hygiene params accumulate measured tuning needs. The uditgoenka patterns lower the build cost when the time comes, but do not change the LOW-MED priority — the single-param manual path remains cheaper near-term.

---

## §9 Decision log

- **2026-05-22** — design memo created from karpathy/autoresearch borrow; parked LOW-MED pending verify §5 + multi-param justification. Single-param manual tune (CURATE_SCORE_THRESHOLD) is the cheaper near-term path.
