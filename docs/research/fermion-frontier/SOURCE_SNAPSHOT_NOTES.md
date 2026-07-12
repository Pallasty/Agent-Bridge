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

The standalone measurement-campaign preflight does not fill these snapshot gaps.
It mechanically derives the final-reference family size `m=136` and, for the
declared `h=0.002` residual allocation, a shared-batch floor of `4,300,768`
effective independent shots per route/R cell and `103,218,432` across the 24-cell
grid. It also confirms that the old `10,000`-shot resource placeholder is
insufficient. These are acquisition targets, not observed shot counts. Because
the campaign template retains null acceptance probability `p` and effective-shot
fraction `eta`, it cannot derive accepted-shot totals, expected raw executions or
a high-confidence stopping cap; its status remains
`EFFECTIVE_TARGETS_DERIVED_RAW_UNRESOLVED` and it explicitly does not assess
convergence certification.

Likewise, the separate reference-qualification template contains no observable
records and returns `UNRESOLVED`. Its validator can verify workload/value identity,
safe local JSON certificate paths and SHA-256, exact record binding, deterministic
error decomposition, externally supplied route-input independence, directed interval
rounding, implementation/environment fingerprints and method-specific claims.
Uncertified TN/Krylov/stochastic records remain `DIAGNOSTIC_ONLY`; even two complete
records are only `STRUCTURALLY_COMPLETE_UNVERIFIED`. No fixed checker is executed,
campaign-bound adequacy is `NOT_ASSESSED_NO_CAMPAIGN_CONTRACT`, and
`ready_gate_eligible` is always false. No real L=8 certificate has been entered into
the snapshot.

The new source-pinned Pauli propagation proof kernel does not close that gap. Its
positive state verifies only arithmetic and truncation for one fixed abstract
two-qubit declared circuit. The L=2 `R=2` witness is a conformance cross-check and
marks its full 112-gate Fraction certificate `DEFERRED_RESOURCE_LIMIT`; neither
artifact certifies the Hubbard mapping, product-formula error, L=8 reference value or
campaign-budget adequacy. Neither is part of the source snapshot or outer evidence
orchestrator.

None of the campaign preflight, reference-qualification ledger, proof kernel or L=2
conformance witness is currently a component of
`evidence_manifest_source_snapshot.json` or `fermi_hubbard_evidence.py`. Their
standalone results therefore cannot change the
outer snapshot status or promote it toward `READY_FOR_BENCHMARK`.

The convergence status boundary is intentional. Finite-sample route data that pass the
family-wise Bonferroni--Hoeffding grid checks but lack a fully bounded independent
reference can reach only `SCREENED_FOR_TARGET_R`. The unified evidence orchestrator
accepts only `READY_FOR_TARGET_R`, so neither the empty snapshot nor screening-only
evidence can be promoted to `READY_FOR_BENCHMARK`.
