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

The source-pinned Pauli propagation proof kernel does not close that gap. Its
positive state verifies only arithmetic and truncation for one fixed abstract
two-qubit declared circuit. The L=2 `R=2` witness is a conformance cross-check and
the original string-sparse implementation marked its full 112-gate Fraction
certificate `DEFERRED_RESOURCE_LIMIT`.

A separate mapping subcertificate now verifies the fixed L2/L3 OBC canonical JW
bonds, terms, raw events and selected CAR/onsite actions; it also binds the pinned L2
witness's 112 nonidentity gates. This does not retroactively make the abstract
truncation certificate a Hubbard certificate, does not compose the two artifacts into
an end-to-end proof, and does not assess product-formula error, L=8 reference values or
campaign-budget adequacy. The standalone bitset/checkpoint module remains a
non-authoritative prototype, but a new source-pinned checkpointed checker now uses
it to complete the fixed L2 112-gate mapped-circuit propagation for both observables.
That run has zero dropped `L1` and rigorous Taylor/quantization intervals, yet still
does not bound the R=2 product formula against exact Hubbard evolution or transfer
the result to L=8.

A separate source-pinned Strang checker now recomputes the fixed L2/L3/L8 five-group
nested commutators.  Its L8 coefficient-L1 result is `C=7076/3`, giving the generic
norm-one observable bound `1769/3750` at R=100.  This fails the `1/4000` allocation
and therefore records a rigorous nonqualifying bound, not a reference value.  The
checker does not compose mapping/truncation certificates or bind the physical L8
initial state and observables.  Neither new subcertificate is part of the source
snapshot or outer evidence orchestrator.

The subsequent grouping screen exhausts all 120 orders of the fixed five groups and
all 24 orders of an exact OBC plaquette-plus-boundary cover.  It finds only a
`1/1769` relative coefficient reduction from reordering and a worse plaquette
coefficient-L1 result.  This is a source-pinned nonqualifying feasibility screen,
not a new reference: the candidate plaquette cluster exponentials do not match the
benchmark circuit, the paper's PBC decimal norm bounds are not imported, and no
observable/locality-specific tightening is assessed.

The paper-time official cluster code is separately pinned at commit
`859bef092675957ae126e9d3b09dc3c63b213859`.  Its at-most-14-mode compact Fock
matrices are evaluated with NumPy binary64 spectral routines and no directed
rounding or residual enclosure, so neither those outputs nor the full-L8 diagnostic
prototype are certificate inputs.  The diagnostic value `C≈1343.9636` is retained
only as route-screening context.

A further source-pinned exact checker removes the need to certify that cluster upper
bound for the fixed-generic decision.  It recomputes
`A=[K1,[K1,H1]]` and its action on one normalized checkerboard Néel basis vector in
the `N_up=N_down=32` sector.  The exact result `||A|q>||^2=295200` implies that the
single positive `||A||/12` theorem contribution has squared lower bound 2,050,
already above the entire R=100 coefficient ceiling squared `25/16`.  Thus even a
globally exact sector-restricted spectral norm cannot make this fixed five-group
generic theorem expression qualify.  This is not an actual product-formula-error
lower bound and does not assess observable/locality-specific cancellation,
alternative groupings, or higher-order formulas.  It supplies no reference value and
is not part of the source snapshot.

The observable-specific follow-on is also standalone.  Its source-pinned checker
uses Fang--Qu's iterated integral-Taylor remainder to certify a single
`delta=1/100` Strang step acting on each initial target observable.  The exact L8
Pauli-L1 bounds are `159187/1600000000` and `133927/2400000000`.  Correct full-time
telescoping instead requires the evolved observables `O_k`; multiplying either
initial bound by 100 is not an error certificate.  The checker only uses those
multiplied values as a floor proving that the uniform-supremum Pauli-L1 architecture
cannot meet the allocation.  It supplies no R=100 reference value, and its exact
Néel-sector `D3` action is a leading-coefficient route witness rather than an actual
error lower bound.

The standalone double-occupancy cluster checker now proves a different, narrower
uniform-sup no-go.  Its compressed physical-fermion fixture is accepted only after exact JW
expansion reproduces the source-pinned 8,928-term Pauli `D3`.  The fixed upstream
greedy14 rule yields 43 clusters, and direct global half-filled Néel matrix elements
lower-bound the first 30 cluster norms by `1945/768>5/2`.  Therefore exact cluster
norms plus triangle for this k=0 partition cannot seed the R=100 uniform-supremum
certificate.  A per-step evolved cluster ledger is not ruled out; the k=0 partial
floor contributes only `389/153600000` in that sum.  These cluster lower bounds are
not a lower bound on the globally summed operator; cross-cluster cancellation and
other partitions remain unassessed.  The fixture's upstream decomposition/order
provenance is externally audited but not runtime-regenerated.  No numeric reference
value is added to this snapshot.

The Majorana implementation audit likewise changes no snapshot value.  It selects a
future fork from registered `main@b7849cb` because the inferred paper-date commit
precedes a documented splitting-sign fix; a complete Julia Manifest, deterministic
composite ordering, outward intervals, and a per-gate/stage dropped-L1 ledger are
still missing.  Current Majorana convergence data therefore remain diagnostic only.

None of the campaign preflight, reference-qualification ledger, proof kernel, L=2
conformance witness, mapping checker, checkpointed L2 checker, bitset prototype,
Strang commutator checker, grouping-screen checker, fixed-generic-bound no-go checker,
observable-Taylor-step checker or double-occupancy-cluster no-go checker is currently
a component of
`evidence_manifest_source_snapshot.json` or `fermi_hubbard_evidence.py`. Their
standalone results therefore cannot change the
outer snapshot status or promote it toward `READY_FOR_BENCHMARK`.

The convergence status boundary is intentional. Finite-sample route data that pass the
family-wise Bonferroni--Hoeffding grid checks but lack a fully bounded independent
reference can reach only `SCREENED_FOR_TARGET_R`. The unified evidence orchestrator
accepts only `READY_FOR_TARGET_R`, so neither the empty snapshot nor screening-only
evidence can be promoted to `READY_FOR_BENCHMARK`.
