# Signal Fidelity Baseline - 2026-06-30

This is the first post-deploy baseline after the reinforce saturation fixes:

- `fd3650c` changed `memory_reinforce_active` from additive ceiling jumps to
  multiplicative movement toward the ceiling.
- `86ae4ee` exposed ceiling saturation in `signal_fidelity_stats`.
- `3a17677` clarified that `top_distinct_importance` uses a fixed top-50
  window.

The observation was taken after `origin/master@4147637` was deployed.

## Command

```bash
/home/pallasting/.local/bin/agent-bridge.real dream signal-fidelity --top-n 5 --json
/home/pallasting/.local/bin/agent-bridge.real dream signal-fidelity --top-n 0
```

## Baseline

```text
total_active              643
n_touched                 512
n_zero_access             131
n_floor_importance        70
n_ceiling_importance      238
top_distinct_importance   2
mean_importance           0.6861511660062171
mean_access               24.757387247278384
spearman_r                +0.5464183100705774
spearman_r_touched        +0.47143437611008965
```

Human view:

```text
at importance ceiling: 238 (37% - reinforce-saturated)
top-50 distinct imp  : 2 (COLLAPSED - top-tier has no ordering)
spearman r (all)     : +0.546 [strong]
spearman r (touched) : +0.471 [moderate] (n=512)
```

## Interpretation

The current ranking signal is useful: importance is already a real prior
against access (`r_all ~= 0.55`, `r_touched ~= 0.47`).

The stored ceiling pile has not been rewritten, which is expected. The
backfill decision remains deferred: do not bulk-rewrite the 238 saturated rows
until certified-use density is much higher or a separate low-risk reset is
explicitly gated.

For the next observations, the expected healthy direction is:

- `n_ceiling_importance` falls below 238 as future reinforce passes stop adding
  new exact-ceiling rows.
- `top_distinct_importance` rises above 2 as the top tier regains ordering.

The useful next check is after one or more scheduled reinforce/decay cycles, not
immediately after this baseline.
