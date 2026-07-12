# Source snapshot notes

`evidence_manifest_source_snapshot.json` is the current L=8/R=100 evidence snapshot.
It records known source-leading or derived steady-state subtotals while leaving all
unmeasured fields null. It is intentionally different from the empty template:

- native derived schedule: `448` steady count/step, `8` steady depth/step, first-step
  bookkeeping correction `64` count and `1` depth, giving the known logical subtotal
  `44,864` and depth `801` under the common group-order target;
- dynamic-JW source leading: `2,688` count/step and `32` depth/step;
- dynamic-JW candidate fit: `2,496` count/step and `62` depth/step;
- standard FSN candidate fit: `8,080` count/step and `128` depth/step;
- ladder FSN candidate fit: `3,984` count/step and `64` depth/step.
- surface place-route: a contract-shaped placeholder only; it has no patches,
  layouts, intervals, operation windows, or compiler/measured provenance.

The snapshot does **not** close any complete route. Native timing is missing its
occurrence table; qubit routes lack first-step corrections and route timing; all routes
lack individual-term exports and the schema-v2 dual-observable measurements on the fixed
`R=[25,50,100,200,400,800]` grid; and the surface schedule is empty. In particular,
there are no joint `staggered_magnetization` / `double_occupancy` estimates, accepted-shot
or effective-independent-shot counts, per-shot contribution ranges, validated
concentration/mitigation assumptions, estimator-mean covariance matrices, systematic
bounds, globally unique per-route/R circuit fingerprints, or bounded independent
references. Running the unified validator therefore remains `UNRESOLVED`. Candidate-fit
rows are confined to the Fig. 5 domain and retain their non-source provenance.

The convergence status boundary is intentional. Finite-sample route data that pass the
family-wise Bonferroni--Hoeffding grid checks but lack a fully bounded independent
reference can reach only `SCREENED_FOR_TARGET_R`. The unified evidence orchestrator
accepts only `READY_FOR_TARGET_R`, so neither the empty snapshot nor screening-only
evidence can be promoted to `READY_FOR_BENCHMARK`.
