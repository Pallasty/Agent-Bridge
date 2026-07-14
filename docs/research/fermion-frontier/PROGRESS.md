# Research progress ledger

Status date: 2026-07-12

## State labels

- `VERIFIED`: three valid independent votes and no two-vote refutation.
- `PROVISIONAL`: two supporting votes but fewer than three total votes.
- `REFUTED`: at least two independent refutation votes.
- `UNVERIFIED`: fewer than two valid votes.
- `INFERRED`: synthesis or cross-domain mapping not directly asserted by a
  source.

Split suffixes retain the vote tally: `verified_2_1` means two passes and one
refutation; `verified_2_0_1` means two passes and one unverified verdict. Their
replacement wording and disagreement are mandatory, not optional caveats.

## Completed evidence clusters

The inherited completed rounds support these clusters, subject to the original
source-level caveats preserved in the round result files:

1. Luttinger constraints, ersatz Fermi liquids, and explicit continuity
   failures or modifications in SYK, FL*, and fractionalized phases.
2. Nielsen-Ninomiya as a lattice-continuum no-go boundary and
   Ginsparg-Wilson as a premise-relaxing construction.
3. Axial anomaly as a quantum violation of a classically conserved current.
4. Matchgate designs and shadows as a polynomial fermionic-Gaussian
   computational representation, with high practical polynomial costs.
5. Graded/Grassmann tensor-network sign handling as asymptotically low
   overhead rather than an automatic speedup.
6. Determinant/Pfaffian neural quantum states, their expressivity, cubic
   algebraic costs, and orthogonal acceleration routes.
7. Fast exact DPP sampling, conditional DPP coreset advantages, volume-sampling
   identities, and the sampling-versus-MAP tractability boundary.

## Focused verification clusters

| Cluster | Candidate claims | Current state |
|---|---:|---|
| DPP / negative-dependence ML | 30 | 28 verified, 2 refuted/rewrite-required |
| Non-Gaussian fermionic simulation | 10 | 9 verified, 1 refuted/rewrite-required |
| Fermion-to-qubit encoding / native hardware | 15 | 12 fully verified, 2 verified after partial rewrite, 1 refuted |
| Gaussian-state manifold geometry | 15 | 13 verified, 2 refuted/rewrite-required |

All 70 claims in the focused gap-3/4/5 ledger are now adjudicated: 56 unanimous
verified, 8 split/partial accepted, and 6 refuted as written. There are no
unreviewed focused claims.

## QA findings

- Round 1 metadata reports 11 post-synthesis findings, while the original
  narrative called them 10. The JSON result count is authoritative.
- `unverified: 0` in rounds 1 and 2 describes the selected 25-claim voting
  batch, not all 120/119 extracted candidates.
- Five round 3 DPP coreset claims were accepted with only 2-0 votes. They are
  now closed by three new independent reviews; all five passed with explicit
  construction and dimensionality limits.
- The DPP batch task initially pointed to indices 50–54. The persistent ledger
  shows that those are encoding claims; the correct fifth DPP source is at
  indices 55–59. All three reviewers used the corrected index set.
- The DPP source graph has substantial author overlap and survey-to-primary
  dependencies. Three independent reviews do not constitute three independent
  source replications.
- The encoding batch separates classical mapping preprocessing, compiled CNOT
  count, logical depth, physical execution time, and fault-tolerant space-time.
  Equal asymptotic depth across two papers does not make these resources
  interchangeable.
- Encoding claim 46 was unanimously refuted because it changed a five-layer
  native-gate depth statement into five total gates. Claim 43 passed 2–1 only
  as a four-mode H2 hardware observation without a general causal noise claim.
- The 2023 native-hardware maturity statement is now historically incomplete.
  Separate 2026 experiments demonstrate high-fidelity fermionic collisional
  gates and programmable fermionic array preparation/readout, but not yet the
  complete integrated processor proposed in PNAS.
- A June 2026 Physical Review Research accepted paper was found after the
  ledger closed and separately reviewed 3–0. Its 24-qubit hybrid QC-AFQMC
  workflow is an engineering milestone; `9x` is a tuned circuit-throughput
  result and `656x` is a normalized/extrapolated post-processing estimate, not
  an end-to-end quantum speedup.
- Claude produced no unified final report. The takeover's synthesis and final
  adversarial review are now complete in `FINAL_SYNTHESIS.md` and
  `FINAL_ADVERSARIAL_REVIEW.md`, with a Chinese brief in
  `EXECUTIVE_BRIEF_ZH.md`.

## Roadmap execution update

The first execution task now has a reproducible planning deliverable in
`RESOURCE_MODEL_FERMI_HUBBARD_ZH.md` and
`fermi_hubbard_resource_model.py`. It fixes an open-boundary spinful square
Fermi--Hubbard physics target, a shared Strang-step planning input, an additive
target-error ledger, and route-specific accepted-shot/acceptance/mitigation
accounting. The common term-group order is reconstructed from dynamic-JW Fig. 14
but remains a validation target rather than a completed cross-compiler fact. The
model separates:

- source-reported leading dynamic-JW resources;
- finite-size FSN/dynamic candidate fits restricted to the Fig. 5 domain;
- a new graph-coloring native schedule under the common group-order target;
- bare-qubit layer time from non-CNOT time;
- lattice-surgery ladder rounds from complete encoding switches, code cycles,
  auxiliary/routing/factory patches, and magic-state supply.

The model intentionally returns `UNRESOLVED` for complete totals and wall-clock
quantities that the primary sources do not determine. The next update must
supply individual-term cross-compiler validation, a joint dual-observable
convergence/covariance study, full first-step circuit exports, native consecutive-matching
movement benchmarks, and real compiler/measured data for the now-executable
distance-`d` surface-code place-and-route ledger before claiming an end-to-end winner.

The first of those interfaces is now executable: `term_order_contract.json` pins
the reconstructed group-level Strang order and fusion rules,
`term_order_validator.py` validates route exports, and the native fixture passes
group-level checks. Individual-term exports for dynamic-JW and FSN are still
absent, so the research status remains “target defined, cross-compiler equality
unverified.” A stricter `term_order_cross_route.py` comparator now requires all
five route exports to carry individual-term lists and compares their raw sequence
fingerprints; its empty manifest remains `UNRESOLVED`, and synthetic same-sequence
fixtures are test-only evidence. The comparator also rejects an export whose embedded
`route` differs from its manifest key, so one export cannot be relabeled as independent
evidence for another route.

The target-`R` interface is also executable in
`fermi_hubbard_convergence.py`. Schema v2 fixes the canonical
`staggered_magnetization` / `double_occupancy` pair, their definitions and
physical ranges, the full planned refinement grid, and target `R=100` before
route data are inspected. Every route must supply the exact planned grid as
joint-observable points with a finite symmetric positive-semidefinite covariance
matrix for the estimator mean, per-observable systematic bounds, and
measurement/circuit/term provenance. Shared-shot points additionally require
attempted/accepted counts, effective-independent-shot counts, per-shot contribution
ranges, and concentration/mitigation status. They enforce
`attempted >= accepted >= 2` and `0 < effective <= accepted`; the concentration
status certifies the model, contribution ranges, and effective-sample derivation.
Circuit fingerprints must be globally unique across every route/R point. Standard
errors are derived only from covariance diagonals.

The binding finite-sample gate is not an asymptotic `z * SE` claim. It allocates
the declared family-wise error rate across all planned point, adjacent-pair, and
reference inequalities with Bonferroni, then uses bounded Hoeffding half-widths
from a validated effective independent sample count and per-shot contribution
range. With no mitigation, that range must equal the observable physical range;
bounded weighted mitigation must supply a finite validated range containing the
reported estimate. Adjacent-`R` checks add both point half-widths and both systematic
bounds, so they do not assume independent batches across `R`. Both observables must
have the required stable intervals and the target must lie inside their joint stable
window.

This yields two deliberately different positive states. Joint stability on the
declared grid without a fully bounded independent reference is
`SCREENED_FOR_TARGET_R`; only complete binding reference checks and binding route
systematic bounds plus validated independent bounded-sample concentration assumptions
can produce `READY_FOR_TARGET_R`. Unbounded/unvalidated mitigation or concentration
evidence is screening-only. The empty L=8 template remains `UNRESOLVED`, and the
unified evidence orchestrator accepts only `READY_FOR_TARGET_R` for
`READY_FOR_BENCHMARK`.

A new standalone measurement-campaign preflight now turns that finite-sample rule
into an explicit acquisition floor. It derives, rather than accepts, the four unique
convergence routes, six planned R values, two observables, 48 point inequalities,
40 adjacent-pair inequalities and 48 reference inequalities. The resulting family
size is `m=136`. The contract allocates family-wise half-width `h=0.002` to each
observable; because both observables share one occupation-basis batch, the width-two
staggered-magnetization requirement dominates at `4,300,768` effective independent
shots per route/R cell. Across 24 cells this is `103,218,432` effective shots. The
width-one double-occupancy requirement is lower and is not added to the shared-batch
count. By comparison, the old `10,000`-shot planning placeholder fails even the
`h=0.01` point budget under the same Bonferroni--Hoeffding family.

The `136` count is deliberately conservative: it indexes every declared inequality,
while the underlying stochastic concentration events are the 48 route/R point
intervals reused across point, adjacent and reference checks. Independence among 136
comparisons is neither asserted nor required by the union bound.

This remains an effective-shot preflight, not an execution ledger. The campaign
template deliberately leaves route/R acceptance probability `p`, effective-shot
fraction `eta`, and their provenance unresolved. Therefore planned accepted shots,
expected raw attempts and any high-confidence attempt cap remain null, and the status
is `EFFECTIVE_TARGETS_DERIVED_RAW_UNRESOLVED`. Even when future `p` and `eta` values
permit an expected-attempt calculation, that value is planning-only rather than a
high-confidence stopping guarantee. The validator also reports convergence
certification as `NOT_ASSESSED_BY_PREFLIGHT`: no estimate, covariance, systematic
bound or actual shot result is generated by this planner.
For the accepted-shot conversion to be meaningful, each future `eta` must be a
conservative effective-independent fraction jointly valid for both observables;
an empirical ESS estimate alone is diagnostic rather than a guaranteed denominator.

A second standalone interface now checks the structure of deterministic reference
certificate records. Its contract exactly fixes the evidence convergence workload
and both observable identities. Each record binds the value and target to the
reference formula and term sequence, solver/configuration, certificate checker,
implementation commit, environment lock, theorem/assumptions, local JSON certificate
artifact and SHA-256. The JSON artifact must bind every decision-relevant ledger
field exactly. The validator checks a non-negative four-part error decomposition
against `total_abs_bound` and compares reference inputs with a complete externally
supplied route batch/circuit fingerprint snapshot. Binding-looking classes must use
directed interval rounding and satisfy method-specific claims: full target-sector
coverage for exact diagonalization; deduplication, dropped-L1 ledger and product-formula
bound for certified operator propagation; state-norm and contraction bounds for
certified tensor networks; locality-tail and solver-defect bounds for certified
locality methods; or an external checker for `other_rigorous`.

The reference state boundary is fail closed. Missing or internally inconsistent
records are `UNRESOLVED`; arbitrary text artifacts, JSON content drift, uncertified
TN/Krylov/stochastic methods, a missing/partial external route snapshot, failed
independence, non-directed rounding or unsatisfied claims cannot produce a positive
binding state. Even two complete self-consistent records are only
`STRUCTURALLY_COMPLETE_UNVERIFIED`: SHA-256 and exact record binding establish byte
integrity and consistency, not numerical truth. This validator runs no fixed machine
checker, does not assess whether `total_abs_bound` fits the campaign allocation,
always reports `ready_gate_eligible=false`, and deliberately has no
`QUALIFIED_BOUNDED` state. External-snapshot completeness is shape-checked rather
than proven against convergence data, and `STRUCTURALLY_COMPLETE_UNVERIFIED` still
has a nonzero CLI exit code. The empty template is `UNRESOLVED`.

A first machine-recomputed subcertificate layer is now executable. The fixed
two-qubit contract pins the checker source SHA-256, raw observable, computational
basis state, two nonzero noncommuting rotations and explicit backpropagation order.
The checker uses Fraction-only Taylor--Lagrange sine/cosine enclosures, exact Pauli
phase algebra and four-corner interval arithmetic; it propagates every gate in a
slice, merges identical strings, then recomputes each dropped coefficient's maximum
absolute interval and the cumulative `L1` ledger. It also returns the retained
expectation interval expanded by cumulative dropped `L1`.

This positive state is narrowly named
`VERIFIED_CIRCUIT_TRUNCATION_SUBCERTIFICATE`. The kernel itself does not check whether
its declared Pauli sequence is a Hubbard mapping, whether its product formula
approximates ideal time evolution, whether the truncation bound meets any budget, or
whether the method scales to L=8. All such fields remain `NOT_ASSESSED`, READY remains
false and the CLI exits nonzero. The reference-qualification validator does not
invoke this kernel, so no existing reference or outer state is upgraded.

The companion L=2 conformance witness independently builds the site-major JW
`R=2,T=1` sequence with 112 raw rotations and obtains
`M_s=0.781713978559467` and `D=0.0309252063024724`, agreeing with the direct-fermion
statevector path to below `1e-12`. The ideal-evolution diagnostic remains separated:
the R=2 differences are about `0.12595` and `0.00586`. A one-gate Fraction probe is
fully enclosed, while the full 112-gate rational certificate is
`DEFERRED_RESOURCE_LIMIT`: the unoptimized term and rational-size growth is itself a
measured implementation boundary, not evidence of L=8 feasibility.

The next independent layer now verifies the canonical Hubbard-to-JW construction for
fixed L=2 and L=3 OBC profiles. `hubbard_jw_mapping_validator.py` source-pins its own
checker plus the L2 pilot, term-order contract, L2 witness and the witness's proof-kernel
dependency. It regenerates every spin-resolved matching bond and Pauli term, retains
the onsite identity component in raw events, and records global phases `exp(-i*8)` and
`exp(-i*18)` for L2/L3. Exact CAR/JW action witnesses number 64/192, onsite occupation
witnesses number 16/36, and L3 has six bonds in each of H1/H2/H3/H4. Its positive path
also executes the pinned L2 builder and requires exact equality with the canonical
112-gate nonidentity sequence. The maximum status is
`VERIFIED_CANONICAL_JW_MAPPING_SUBCERTIFICATE`; product-formula error, exact evolution,
L=8, the campaign budget and READY remain outside its scope.

`pauli_bitset_backend.py` provides exact Hermitian-Pauli multiplication, symplectic
commutation, checker-compatible interval propagation and order-independent checkpoint
SHA-256 over canonical Fraction intervals. It is explicitly a consistency/performance
prototype with certificate authority `NONE`. It matches exhaustive/random string-backend
tests and an eight-gate L2 prefix, but neither changes the pinned checker nor claims a
complete 112-gate rational expansion.

That full L2 expansion is now completed by the separate source-pinned
`operator_propagation_checkpointed_l2.py`.  It composes the positive canonical mapping
result with all 112 nonidentity gates of the fixed `L=2,R=2,T=1` circuit, reverses the
20 raw group-event checkpoints, uses fifth-order exact Taylor intervals, and rounds
outward to the `2^32` grid after every slice.  No term is dropped: staggered
magnetization finishes and peaks at 16,380 terms with interval
`[104895467/134217728,209888553/268435456]`; double occupancy finishes and peaks at
16,381 terms with interval `[8238201/268435456,33458587/1073741824]`.  Both final
checkpoint digests and every intermediate checkpoint are independently recomputed.
The float statevector values are contained diagnostics only.  The maximum status,
`VERIFIED_L2_MAPPED_CIRCUIT_TRUNCATION_SUBCERTIFICATE`, still excludes error from the
R=2 product formula to exact Hubbard evolution, any L=8 transfer, reference-budget
qualification and READY.

The new `hubbard_strang_commutator_checker.py` independently regenerates the
nonidentity Pauli expansions for the fixed L=2/L=3/L=8 OBC five-group split and
computes the two nested-commutator families in the source-pinned Schubert--Mendl
second-order bound.  Equal Pauli strings are merged inside each family before its
coefficient `L1` norm is taken; theorem families are never cancelled against one
another.  For L=8, the exact family sums are 22,752 and 11,104, giving `C=7076/3`.
At `T=1,R=100` this yields unitary error at most `1769/7500` and the generic
norm-one-observable comparison bound `1769/3750`, so the `1/4000` allocation fails by
a wide margin; the least R satisfying this generic bound is 4,344.  This is a
rigorous negative feasibility result for this grouping and generic norm reduction,
not an observable-specific no-go theorem.  It cross-checks but does not compose the
mapping certificate; L8 sparse-action validation, physical workload identity,
truncation composition, observable-specific tightening, reference qualification and
READY remain outside the positive status.

`hubbard_strang_grouping_screen.py` now closes the immediate regrouping question.
It source-pins the positive commutator checker and enumerates every order of two
exact L8 OBC decompositions.  Among all 120 orders of the declared five groups, the
minimum is `C=7072/3` with generic R=100 observable bound `884/1875`; the reduction
from the declared `7076/3` is only `1/1769`, below the predeclared 1% materiality
threshold.  The exact OBC plaquette adaptation covers all 112 spatial bonds using
64/36 bulk bonds and 12 boundary residual bonds, but its best of 24 orders has
`C=7232/3` and bound `904/1875`, which is worse.  Its bulk group exponentials require
noncommuting plaquette-cluster evolution and are not the benchmark circuit.  Since
the R=100 allocation requires `C<=5/4`, the screen proves that coefficient-L1
reordering/regrouping is not the next viable tightening; it does not prove a
no-go for cluster spectral norms or observable/locality-specific analysis.

The official cluster implementation is now pinned at paper commit
`859bef092675957ae126e9d3b09dc3c63b213859`.  It constructs compact Fock matrices on
at most 14 modes and calls NumPy binary64 spectral routines; no outward rounding
or residual certificate is emitted.  A separate full-L8 diagnostic prototype uses
105 clusters (94 at 14 modes) and obtains `C≈1343.9636`, a 43% reduction from Pauli
L1 but still about 1075 times the R=100 ceiling.  These numbers are not imported into
any positive scope.

`hubbard_strang_generic_bound_no_go_checker.py` removes the need to certify those
cluster upper bounds for the route decision.  For the fixed five-group theorem it
recomputes the 3,072-term `A=[K1,[K1,H1]]` and its exact action on the checkerboard
Néel vector in the physical `N_up=N_down=32` sector.  The 416 nonzero outputs give
`||A|q>||^2=295200`, so the selected `1/12` contribution has squared lower bound
2,050, while the entire coefficient would have to satisfy `C^2<=25/16`.  The implied
generic R=100 bound expression is at least `sqrt(82)/1000`, over the allocation by
`4*sqrt(82)`; R=602 is only the first step count not ruled out by this single witness.
Thus globally exact and sector-restricted cluster spectral norms cannot rescue the
fixed generic bound.  Actual product-formula error and observable-specific error are
not lower-bounded; the next route is observable/locality-specific or a genuinely
different grouping/formula.

`hubbard_strang_observable_taylor_step_checker.py` now implements the first
observable-specific proof kernel.  It source-pins the positive Strang backend,
specializes Fang--Qu Eq. (3.9) to the fixed nine-stage composition, verifies exact
formal cancellation through degree two, merges the degree-three defects and
enumerates all 495 fourth-order remainder paths for L2/L3/L8 and both targets.  At
L8 its strict `delta=1/100` initial-observable one-step operator bounds are
`159187/1600000000` and `133927/2400000000`; the initial Néel expectation bounds are
smaller because both exact `D3` expectations vanish.  Correct R-step telescoping
requires evolved `O_k`, so neither number is multiplied into an actual full-time
bound.  Conversely, a uniform-supremum Pauli-L1 architecture must include `k=0` and
therefore has floors 39.80 and 22.32 times the allocation.  The exact L8 Néel action
witness makes the magnetization leading-coefficient floor exceed `5/2`, while the
double-occupancy witness remains below it.  The narrow positive status certifies only
the one-step kernel and route decision; full R=100 error, reference and READY remain
unassessed.

The double-occupancy sector follow-on now closes one additional uniform-supremum
architecture without
overclaiming a global norm.  The new source-pinned checker expands a compact
2,748-term physical-fermion fixture, independently obtains 18,544 field terms, and
proves its exact JW image equals the existing 8,928-term Pauli `D3` oracle
(`L1=423/16`).  It then replays the fixture-defined 43-cluster greedy14 partition.  Direct
matrix elements on the global `N_up=N_down=32` Néel basis state lower-bound the first
30 exact cluster norms by `1945/768>5/2`, margin `25/768`; hence even exact norms for
this k=0 partition followed by triangle cannot seed the R=100 uniform leading bound.
A per-step evolved cluster ledger remains open because this k=0 floor contributes
only `389/153600000` there.  The fixture decomposition/order's link to upstream
simplify is external audit provenance rather than a runtime-recomputed claim.  The
checker explicitly does not add those lower bounds into a lower bound for the
globally merged `D3`, so cancellation-aware/global-sector routes remain open.

The Majorana source audit also fixes the implementation direction.  The inferred
paper-date snapshot predates a documented splitting-sign repair; the selected base
is registered MajoranaPropagation `v0.3.0`, `main@b7849cb`, with a certificate fork
that must pin Julia/Manifest and PauliPropagation, sort composite terms, and add
outward intervals plus a post-dedup dropped-L1 ledger.  Exact term-growth probes show
that applying `D3` to `ad_H(O)` already yields 42,488/88,352 terms, so the next kernel
will directly propagate evolved observables instead of recomputing 495 fourth-order
paths at every step.

None of the campaign, reference-qualification, proof-kernel, mapping, checkpoint,
commutator, grouping-screen, generic-bound no-go, observable-Taylor-step or
double-occupancy-cluster no-go interfaces
is currently loaded by
`fermi_hubbard_evidence.py`. They do not
add components to `component_statuses`, and none can yet participate
in or strengthen the outer `READY_FOR_BENCHMARK` decision. Outer integration remains
a subsequent implementation step.

The dependency-free `L=2` group-order pilot now exercises both observables and
is screened at `R=32`. Its scaled-Taylor reference values have no rigorous
truncation-error bound and are therefore recorded as `approximate_unbounded`.
Consequently the result is `SCREENED_FOR_TARGET_R`, not an exact-reference or
bounded algorithmic certificate, and it remains neither hardware evidence nor
an `L=8` result.

The first-step interface is now executable as well. `first_step_contract.json`
requires per-route steady and first-step logical resources, an explicit
`compiled_exact` provenance flag, and route-specific timing fields.
`first_step_ledger_validator.py` distinguishes `UNRESOLVED`,
`BOOKKEEPING_CLOSED_ESTIMATE`, and `COMPLETE`; the empty five-route ledger remains
unresolved, and candidate/source-leading steady values cannot be promoted to exact
totals merely by supplying a first-step subtotal.

Five evidence components are now joined by `evidence_manifest_contract.json`,
`evidence_manifest_template.json`, and `fermi_hubbard_evidence.py`. The orchestrator
checks route-map/workload consistency, cross-checks term-export `trotter_steps` against
ledger `R`, requires the native occurrence-level transition component, and requires a
surface place-route ledger whose event count and logical-sequence fingerprint match the
term export. Its empty manifest is still `UNRESOLVED`; only real individual-term exports,
exact first-step resources, measured native transitions, a `COMPLETE` surface schedule,
and convergence evidence at `READY_FOR_TARGET_R` can produce
`READY_FOR_BENCHMARK`; `SCREENED_FOR_TARGET_R` is intentionally insufficient.

The new `surface_place_route_validator.py` checks all `2L^2` live data patches,
`2d^2-1` physical-qubit patch sizing, odd distance, tile conflicts, participant/corridor
connectivity, continuous intervals, operation windows and shared-patch conflicts,
dependencies, the distill/buffer/inject/rotation support chain, term-ordered one-to-one
logical-event bindings, the active physical-qubit-cycle sum, and fixed cycle/failure
budgets. It does not synthesize a routing solution:
`COMPLETE` also requires an external compiler export, `place_route_validated=true`, and
measured/compiler evidence; derived schedules remain `BOOKKEEPING_CLOSED_ESTIMATE`.

The dynamic-JW source was rechecked directly against arXiv v1. `DYNAMIC_JW_SOURCE_EVIDENCE.md`
records that Fig. 14 supports only a group-level sequence and that Appendix I explicitly
omits the extra cost of the first Trotter step. No individual-term list or exact first-step
compiled record is published there, so the unified manifest remains correctly unresolved.

The FSN side is now separated in `FSN_SOURCE_EVIDENCE.md`: Kivlichan's generic theorem
supports an exact N-depth / N²⁄2-entangling-gate network for the all-pair electronic-structure
setting, while dynamic-JW Fig. 15 supplies only the 2D NN standard/ladder strategy and
fusion convention. The finite-size formulas used in the model therefore remain
figure-domain candidate fits, not primary-source formulas.

Native evidence is now split into `NATIVE_SOURCE_EVIDENCE.md`: PNAS remains a proposal
with component-level movement/error estimates, Nature 2026 supplies a measured local
^6Li collisional-gate primitive, and arXiv:2604.13160 supplies a new global-control
proposal. None provides the matched L=8 four-matching compiled route needed for
`native_fermions` to leave `UNRESOLVED`.

`evidence_manifest_source_snapshot.json` now preserves the known L=8/R=100 source-leading
and derived bookkeeping values without inventing missing fields. Its native row exposes
the `44,864` count / `801` depth schedule, while qubit-route first-step corrections,
native occurrence timing, individual terms, and fixed-grid dual-observable convergence
data remain unresolved. The
surface row is likewise an empty placeholder with no patches, layouts, intervals, or
operations. The validator therefore continues to report `UNRESOLVED` for the snapshot.

The adaptive L8 interval route has advanced through a second, independently
precommitted resource generation.  A certificate-authority-free v2 arithmetic kernel
was first committed and old-domain parity tested; deterministic design probes then
fixed separate 17/21-candidate policies through `K=327,680` before formal execution.
The final source-pinned dual screen same-byte verifies the positive step-3/two-step
parent chain and independently replays both policies from prehashed modules.  It
certifies maximum-K infeasibility at magnetization checkpoint 29 (minimum effective
K 333,983 after 28 commits) and double-occupancy checkpoint 22 (minimum K 350,604
after 21 commits).  Exact ledgers, candidate feasibility, first-feasible choices and
five resource diagnostics are bound, while no child sidecar or transition is written.
Certified mapped depth remains 3 for magnetization and 2 for double occupancy; the
outer evidence orchestrator, exact-Hubbard error, remaining R100 evolution, physical
reference and READY status are unchanged.

A non-authoritative v3 design generation has now tested the next bounded ladder
without altering any v2 policy or formal artifact.  A same-byte fresh-executed
wrapper reuses the pinned v2 implementation, expands the magnetization/double-
occupancy candidate sets to 21/25 values through `K=393,216`, and leaves all other
resource envelopes fixed.  Magnetization advances from the old checkpoint-29 stop
through checkpoint 32 and then needs `K=405,291` at checkpoint 33; double occupancy
advances through checkpoint 23 and then needs `K=397,750` at checkpoint 24.  The
observed peaks/visits (550,806/61,421,993 and 525,968/44,079,570) remain within the
design caps, and the entire formerly committed v2 prefix is unchanged.  Thus this
generation diagnoses another maximum-K ceiling and establishes `K=409,600` as the
minimum next ladder endpoint worth testing.  No v3 policy, formal witness, child
sidecar, transition, exact-Hubbard statement or depth increment has been created.

The v4 higher-K design generation now extends the same diagnostic surface to
`K=458,752`, using 25 magnetization and 29 double-occupancy candidates while
retaining the v3 resource envelope.  Its bounded same-byte wrapper records the
v4/v3/v2 source chain and publishes only complete atomic transcripts.  Magnetization
selects `409,600/425,984/442,368` at checkpoints 33--35 and fails at checkpoint 36
with minimum effective K 464,310.  Double occupancy selects
`409,600/425,984/442,368/458,752` at checkpoints 24--27 and fails at checkpoint 28
with minimum K 461,297.  Peaks/visits are 660,262/73,130,963 and
591,330/59,719,825, so neither stop is a resource failure.  The next standard
candidate `K=475,136` covers both current minima but remains untested beyond the
handoff.  This generation is diagnostic only: certified depths remain 3/2 and no
policy, formal witness, child sidecar, transition, exact-Hubbard claim or READY
component is added.

The v5 kernel-edge generation now tests the last dense ladder that fits the current
double-occupancy candidate-count capability.  Adding `475,136/491,520/507,904`
produces 28/32 candidate sets without changing the v4 live/digest/visit or bit-width
caps.  Magnetization advances through checkpoint 38 and fails at checkpoint 39 with
minimum K 521,800; double occupancy advances through checkpoint 31 and fails at
checkpoint 32 with minimum K 518,097.  Their peaks/visits are
714,754/86,294,299 and 694,872/76,953,164, so both remain K-ceiling diagnostics.
The standard `K=524,288` endpoint covers the two current minima but is also the
kernel retained-K maximum.  Double occupancy has no remaining candidate slot;
testing that endpoint requires a new sparse/merged ladder rather than appending to
v5.  No policy, formal witness, child sidecar, transition, depth increase,
exact-Hubbard conclusion or READY component has been added.

The v6 kernel-limit generation now exercises `K=524,288`, the current arithmetic
kernel's maximum retained value.  Magnetization uses 29 candidates by appending that
endpoint.  Double occupancy remains at the 32-candidate capability by replacing the
unused v5-only `491,520` slot, preserving every ancestral v2--v4 candidate and every
K selected in the v5 committed prefix.  Five ordered same-byte source layers and
three distinct override levels are bound.  Magnetization commits checkpoint 39 with
`K=524,288` and fails at checkpoint 40 with minimum K 525,859; peak/visits are
714,754/91,034,065.  Double occupancy commits checkpoint 32 with `K=524,288`, then
the unchanged 786,432 live/digest cap stops checkpoint 33 before ranking.  A separate
noncanonical measurement at the kernel's 1,048,576-term capability records an
825,000-term peak, 82,050,350 visits and minimum K 553,717 for that checkpoint, with
the K requirement 29,429 above the retained maximum.  The resource exception is
propagated, so no partial D transcript is published; the complete M transcript is
canonical and atomic.  This exhausts candidate-only continuation under the current
kernel.  Certified depths remain 3/2, with no policy, formal witness, boundary,
transition, exact-Hubbard conclusion or READY component added.

A separate four-gate granularity screen now evaluates checkpoint cadence while
holding the v6 candidates and caps fixed as configuration-only inputs.  It owns
independent control flow, does not call the v2 or v6 run entrypoints, and does not
treat v6 as a same-byte parent or a v7 generation.  The physical 1,152-gate sequence
is unchanged; 288 four-gate checkpoints preserve every aligned prefix budget.
Magnetization commits 77 checkpoints and fails at q78/gates 308--311 with minimum
K 529,897, peak 643,624 and 82,493,877 visits.  This is the second half of old
eight-gate q39, so the reduced peak does not improve M reach.  Double occupancy
commits 64 and fails at q65/gates 256--259 with minimum K 532,869, peak 645,011 and
75,412,433 visits, converting the corresponding frontier from a full-eight-gate
live-cap stop into an earlier half-block K stop.  The deleted `491,520` rung is
counterfactually first feasible at q58--59, showing that ladder sparsification and
checkpoint cadence cannot be assessed independently.  A noncanonical 32-slot
sensitivity restores `491,520` and removes unused `65,536`; it changes both choices
but still fails at q65, now with minimum K 536,203, peak 645,044 and 75,255,249
visits.  The altered ladder is reproduced only by an opt-in test and is not saved as
a misleading v6-configured transcript.  Checkpoint halving and this one-rung repair
therefore both fail to cross the D frontier.  The screen remains diagnostic-only and
leaves certified depths 3/2 and all authority-bearing artifacts unchanged.
The planned `K=540,672` discriminator has now been executed as an explicit,
separately pinned capability extension.  Its arithmetic wrapper compiles exact v2
bytes and changes only `max_retained_K` from 524,288 to 540,672.  The diagnostic
configuration changes only the candidate/output K ceilings; live/digest stay at
786,432 and every other resource cap is unchanged.  M appends the new rung for 30
candidates.  D replaces `65,536`, which is infeasible in all 65 rows and never
selected in the pinned four-gate baseline, so its count remains 32.

M selects `540,672` at q78--80 and reaches the fixed q80 horizon with 80/80
commits; q78--80 pre-counts are 643,624/624,312/587,900 and total peak/visits are
643,624/87,032,691.  D selects `540,672` at q65, then fails at q66/gates 260--263:
pre-count/peak is 679,285, minimum effective K is 558,598, excess over the configured
maximum is 17,926 and total visits are 77,762,021.  The canonical M/D transcript
SHA-256 values are
`d4a0f952a3d4a93bd78d370fae50c5c043e33caa4d1452e841987976e43354a5` and
`5ced57f7f6fc8aef50a6536920243d00af083b0a113b09d19f239bc1266fd8a5`.
Full ledger tests cover 80x30 plus 66x32 candidate rows and bind the old committed
prefixes and failure handoffs.  The route remains diagnostic-only and leaves
certified depths 3/2 and all authority-bearing artifacts unchanged.

The observable-split discriminator is now complete.  M's same-cap q82 wrapper
replays from q1 and uses the q80 artifact only for post-replay validation.  All
q1--80 records and selected history are exact, while q81/gates 320--323 fails at
pre-count 597,254 with minimum effective K 545,129, excess 4,457.  Overall
peak/visits are 643,624/89,253,151, and the canonical SHA-256 is
`0486a8b19077de9e90f134c7b3c0d43fdf3504a4876d6e0b2c3d01b37b89cb52`.

D's direct-v2 capability wrapper raises retained K to 573,440 and candidate count
to 33, with all other kernel limits unchanged and the K=540,672 wrapper retained
only as a non-executed route reference.  The new ladder appends 573,440 to the
old 32 values.  Full replay preserves q1--65 common records/history and the first
32 rows, then preserves q66 propagation and its first 32 rows before the appended
row becomes first feasible.  D selects 573,440 at q66--68 and reaches 68/68
commits; pre-counts are 679,285/688,548/630,616, peak/visits are
688,548/82,618,707, and the canonical SHA-256 is
`b1f072c84cc676151fe3cddbb8a0db445df946f299dbb81f41e34f765d30dfc8`.
The two full ledgers cover 81x30 plus 68x33 candidate rows.  No policy, witness,
boundary, transition, READY component or certified-depth increase is created.

That next split discriminator is complete.  M's direct-v2 capability wrapper
changes only retained K from 524,288 to 557,056 while leaving candidate-count
capacity at 32.  Its append-only 31-slot ladder preserves q1--80 common
records/history and all first 30 candidate rows, then preserves q81 propagation
before the new index 30 becomes first feasible.  M selects 557,056 at q81--82 and
reaches 82/82 commits; the two pre-counts are 597,254/641,180, dropped counts are
40,198/84,124, peak/visits are 643,624/91,592,879, and the canonical SHA-256 is
`1d6cbcddac8a8c596746f24b8c8498f24874e86db5235532d7d269220043cdd4`.

D's outer horizon-only screen changes only q68 -> q70 and replays from q1, using
the q68 artifact solely for post-replay prefix validation.  Its q1--68 prefix is
exact, but q69/gates 272--275 fails at pre-count 644,504 with minimum effective K
579,098, 5,658 above the retained maximum.  Peak/visits are 688,548/84,984,299,
and the canonical SHA-256 is
`38fa337482dbd323d68f36b6debfdc6fff94d4cf8c42e68d6477b45dc02368d6`.
The two new ledgers cover 82x31 plus 69x33 = 4,819 candidate rows.  Both outputs
remain diagnostic-only; policy, witness, boundary, transition, READY components,
certified depths 3/2 and all authority-bearing artifacts remain unchanged.

Those bounded decisions are complete.  M's horizon-only outer screen changes
only q82 -> q84 and replays from q1, with the q82 artifact used solely for
post-replay prefix validation.  q1--82 records/history are exact; q83/gates
328--331 fails at pre-count 652,016 with minimum effective K 565,994 and excess
8,938, so q84 is not attempted.  Peak/visits are 652,016/93,965,211, and the
canonical SHA-256 is
`2f866d658570c9cf667088662a98288c14b41144c3ffacdefd862aaf8f185138`.

D's direct-v2 wrapper changes only retained K 524,288 -> 589,824 and candidate
capacity 32 -> 34.  Its append-only D34 ladder preserves q1--68 common state,
history and first 33 rows, then preserves q69 propagation and first 33 rows
before index 33 becomes first feasible.  q69 selects 589,824 with drop
61,286,012,190 ticks.  q70/gates 276--279 then fails at pre-count 718,805,
minimum effective K 597,272 and excess 7,448.  Peak/visits are
718,805/87,505,002, and the canonical SHA-256 is
`65d6f5ba3e45b5b57b12d1b9e1daadb17064f8aece7dc914697191f822b3a8d7`.
The two ledgers cover 83x31 plus 70x34 = 4,953 candidate rows.  No policy,
witness, boundary, transition, READY component, certified-depth or other
authority-bearing artifact changes.

Those capability extensions are complete.  M's direct-v2 wrapper changes only
retained K 524,288 -> 573,440 while keeping candidate capacity 32.  Its append-only
M32 ladder preserves q1--82 common records/history and all first 31 rows, then
preserves q83 propagation and the first 31 rows before appended index 31 becomes
first feasible.  q83 selects 573,440 with pre-count 652,016, drop
49,417,284,097 ticks and dropped count 78,576.  q84/gates 332--335 fails at
pre-count 694,130, minimum effective K 586,381 and excess 12,941.  Peak/visits are
694,130/96,423,989, and the canonical SHA-256 is
`f379f6a72caba82c0f1aca599ef9872666cfed8b4ea72003194438ed01806f48`.

D's direct-v2 wrapper changes retained K 524,288 -> 606,208 and candidate capacity
32 -> 35, with all other kernel limits unchanged.  Its append-only D35 ladder
preserves q1--69 common state/history and all first 34 rows; q70 retains the old
propagation and first 34 rows before index 34 becomes first feasible.  q70 selects
606,208 with drop 97,846,623,202 ticks, dropped count 112,597 and feasibility
margin 53,451,620,700 ticks, reaching 70/70 committed.  Peak/visits remain
718,805/87,505,002, and the canonical SHA-256 is
`55e9d305c90b62dea918071cd6ae383668c2ffb2f7dc108f7d4abcbcb772aa36`.
The exact ledgers cover 84x32 plus 70x35 = 5,138 rows.  No policy, witness,
boundary, transition, READY component, certified-depth or other authority-bearing
artifact changes.  All 35 current D candidate indices have now been selected at
least once.

Those split routes are complete.  M's direct-v2 wrapper changes only retained K
524,288 -> 589,824 while keeping candidate capacity 32.  Its replacement ladder
deletes K=65,536 and appends K=589,824.  q1--83 preserve selected-K history,
propagation and committed state exactly; because old candidate indices 1--31 shift
to new 0--30, candidate rows are normalized-exact by configured K rather than raw
row-prefix exact.  q83 still selects K=573,440 at new index 30.  q84 selects new
index 31/K=589,824 with pre-count 694,130, drop 142,263,012,225 ticks, dropped
count 104,306 and feasibility margin 46,578,773,421 ticks, reaching 84/84
committed.  Peak/visits remain 694,130/96,423,989, and the canonical SHA-256 is
`cf93ebcccde4ff10adee2e600a13ef1c0f979e89fe151fca16d4eae79da2420f`.
All 32 M candidate indices now occur in selected history.

D's same-cap outer screen changes only horizon 70 -> 72 and replays from q1; the
q70 screen/transcript are post-replay references and never execution or state
inputs.  q1--70 records, selected history and all 35 rows remain exact.  q71/gates
280--283 fails at pre-count 761,190, minimum effective K 614,584 and excess
8,376, so q72 is not attempted.  Peak/visits are 761,190/90,141,781, and the
canonical SHA-256 is
`f21288cf0c37dc86fedc9ac195f4efe390dcc913640caa7ca79f02e6297d20f8`.
The two ledgers cover 84x32 plus 71x35 = 5,173 rows.  No policy, witness, boundary,
transition, READY component, certified-depth or other authority-bearing artifact
changes.

That next split is complete.  M keeps K=589,824/C32 and changes only the horizon
84 -> 86.  Its exact q84 screen is the same-byte private execution parent, while
the q84 canonical is loaded only after replay.  q1--84 records, all 32 candidate
rows per record and selected history remain exact.  q85/gates 336--339 reaches
pre-count 673,356 with 151,110,179,092 ticks of slack.  K=589,824 would drop
184,958,529,526 ticks, so the minimum effective K is 592,290, excess 2,466;
q85 fails and q86 is not attempted.  Peak/visits are 694,130/98,908,531.  The
screen and canonical SHA-256 values are
`002cc87d5d1a8f1908a837e8612e3a9d4a4c5ebbf68e41f841ba4a5a639ff878`
and `c24a665d543323a0e7f28ac4023fe5ae3d54b39c4e2991cba3e70e9371d0053d`.

D adds direct-v2 capability K=622,592/C36 and appends that K as index 35 without
deleting any selected predecessor rung.  q1--70 common records/history and old 35
rows remain exact; q71 preserves the old propagation and first 35 rows, then
selects the appended row.  Its drop is 95,847,613,475 ticks for 138,598 terms,
leaving 40,105,997,158 ticks of margin and committing
E=2,288,967,389,826,722 ticks.  q72 propagation produces exactly 799,279 terms,
12,847 above the unchanged 786,432 live-term policy cap, before digest, ranking,
candidate construction or commit.  A closed 40-key resource-abort ledger records
that stop without inventing a q72 checkpoint record.  Peak/visits including the
attempt are 799,279/92,869,433.  The wrapper, screen and canonical SHA-256 values
are `7ac6c87f3d789ad62540cbc96e81f0a092594b0524eec3f9b05e7ffec2124838`,
`2e22e1918fbc10cd696d700dbf05e8d99d0c333a1428e9473de6ebbc563488e1`
and `e7ae9abb11a4cc116778c8c373ff1c93131db9c9d36ba886ff6ef2d7b53bd09f`.
The two exact ledgers cover 85x32 + 71x36 = 5,276 candidate rows.

Those bounded routes are complete.  M's wrapper realizes direct-v2 K=606,208/C33,
raising retained K 524,288 -> 606,208 and candidate capacity 32 -> 33 relative to
arithmetic-v2.  Relative to the non-executed M K589824/C32 route predecessor, the
incremental K change is 589,824 -> 606,208 and the wrapper appends K=606,208 as
index 32.  q1--84 preserve propagation, committed state, selected history and the
old 32 rows exactly.  q85 preserves the measured propagation/ranking and old rows,
then the appended row drops 67,148 terms and 28,686,183,592 ticks, leaving
122,423,995,500 ticks of margin.  q86/gates 340--343 reaches 654,324 terms and
selects existing index 31/K=589,824, dropping 64,500 terms and 213,158,347,226
ticks with 13,797,053,946 ticks of margin.  All 86 checkpoints commit; peak/visits
are 694,130/101,424,121.  The wrapper, screen and canonical SHA-256 values are
`447cb116c2ca977cb2711b08e64e5795728907b8c4033bd1eb38211bf63cf558`,
`86e5148a51cb70d2aab21d770ad2b21928caf6e2818786542b287be7c8d02d27`
and `fc649a90aa42429d7d746f40bdc7dfe109f1dc6921b46beb8c3396cc3012e875`.

D keeps K=622,592/C36 and horizon 72, changing only the live/digest policy caps
786,432 -> 1,048,576.  The frozen resource-abort canonical is post-replay evidence
only.  q1--71 records/history remain exact; q72/gates 284--287 again produces
799,279 terms, now completes digest/ranking and evaluates all 36 rows.  Every row
is infeasible: minimum effective K is 642,206, 19,614 above the ceiling, and the
maximum candidate's drop still exceeds prefix slack by 111,121,545,012 ticks.
There is no q72 resource abort, selection or commit; the ledger ends with 72
attempted and 71 completed checkpoints.  Peak/visits are 799,279/92,869,433.  The
screen and canonical SHA-256 values are
`57a68b3086cd2ed2d484d0f835a190dc768b12bbb2b8d6a3c99c86f6ea6bda8d`
and `4bdc16622a52a57ab6d43da04d77c6c67defdb36c2630a9d51178b65ac1e6ddd`.
The two current ledgers cover 86x33 + 72x36 = 5,430 candidate rows.

Those minimum discriminators are complete.  M keeps K=606,208/C33 and extends
only horizon 86 -> 88 through its q86 same-byte private parent and a fresh q1
replay.  q1--86 remain exact; the q86 canonical is loaded only after replay.  The
result has 88 records, 87 selected-history entries and 2,904 candidate rows.  q87
(gates 344--347, SHA-256
`4b60608343a13e9927dd20cd4bb7314e67b1432465e27d186c117935402801e7`)
reaches 645,618 terms and selects index 32/K=606,208.  It drops 39,410 terms and
28,631,843,222 ticks, leaves 89,696,616,395 ticks of margin and commits
E=1,700,501,205,265,321 ticks.  q88 (gates 348--351, SHA-256
`7f8c6a2dd155412a27369e1fa8402c37127c6eadf12e4fa59ba442d345e8eaf7`)
reaches 689,242 terms and fails policy: minimum effective K is 607,993, excess
1,785, while the maximum row drops 218,739,972,624 ticks and exceeds slack by
24,511,950,557 ticks.  The terminal branch is
`Q87_SUCCESS_Q88_FAILURE`; no resource abort is emitted.  Attempted/completed are
88/87 and peak/visits are 694,130/106,375,865.  Screen/canonical SHA-256 values
are `d158d00275e78b33d0246e86bf9bc7bcaf4eb4f7fa4cb9afce2298e97cb5308d`
and `f7ca4a1defd38472366c1cfcd112736f34b73e612002cce98a52f79daa5cc1b0`;
the canonical is 804,599 bytes.

D's separate direct-v2 K=655,360/C37 wrapper and manifest SHA-256 values are
`2acf8f8329376ab06ad4c079af633d23bcc6a32fa20af654e5c3dbbb32093d54`
and `62c889baf0676150344f06ccf5d48132e121ade399c77dd1b85727f5002dd6e5`.
Its fresh q1--72 replay commits 72/72 checkpoints and 2,664 candidate rows.  q72
reaches 799,279 terms and selects appended index 36/K=655,360, dropping 143,919
terms and 78,846,106,758 ticks with 43,761,880,334 ticks of margin.  It commits
E=2,289,046,235,933,480 ticks; peak/visits remain 799,279/92,869,433.
Screen/canonical SHA-256 values are
`1d3366d7c3fdc2a1e4a5c58198cc9be7e561af1f2ff8582e324ed5902c760183`
and `0517461f8695b21b578190cdd9a5da884f301d43c2f80be8093fbfc20cc006ae`;
the canonical is 751,550 bytes.  K=638,976 is excluded only for the fixed
four-gate q72 predecessor state/prefix: threshold 642,206, shortfall 3,230, with
no executed candidate row and no asserted exact drop.
Together the current ledgers cover 2,904 + 2,664 = 5,568 candidate rows.

Those follow-on discriminators are complete.  M's direct-v2 K622592/C34 wrapper
and capability manifest SHA-256 values are
`f4e676da40535903301181cf482119e051066b90921793e34152403b3b74b976`
and `3c2b66149d524cc63a4d04838b3eec47fb69677466fe1f208e226df92bf0dac3`.
Relative to M33 it appends only K=622,592 as index 33 and raises only the
candidate/output and retained-K/candidate-count ceilings; all other caps remain
fixed.  A fresh q1--88 replay precedes loading the old q88 canonical.  The result
commits 88/88 checkpoints with 88 records/history entries and 2,992 rows.  q88
pre-count is 689,242; index 33/K=622,592 drops 66,650 terms and 33,833,242,742
ticks, commits E=1,700,535,038,508,063 ticks, and closes the ranking boundary at
3,434,232 > 3,434,132.  No failure or resource abort is present.  Records/history
SHA-256 values are
`8832c0fd7c61146f2aa3c5e9a3a827972c459a126c2d371b5a5c41bac700c804`
and `58cd214e13f4c122f710aad62ac0e52ead1aed0fa7d8a7e2498ea6013c7f4726`.
The 78,218-byte screen and 821,781-byte canonical SHA-256 values are
`6867dda2d6bd34ab2eed6b31d02a587e16762263a493e9890d0caa40f23a58a4`
and `0074b1eea5fa574378d5a9fae9e748e7145efaa0c96b622ddf50587a72a2551a`.

D keeps K=655,360/C37 and every candidate, policy and kernel cap fixed, changing
only horizon 72 -> 74.  Its fresh q1 replay loads the q72 canonical only after
execution and commits 74/74 checkpoints, 74 records/history entries and 2,738
rows.  q73 pre-count is 794,529; index 36/K=655,360 drops 139,169 terms and
100,499,996,927 ticks, commits E=2,289,146,735,930,407 ticks and has ranking
boundary 3,668,234 > 3,667,375.  q74 pre-count is 726,450; the same index drops
71,090 terms and 44,071,221,987 ticks, commits E=2,289,190,807,152,394 ticks and
has exact ranking tie 4,009,413 = 4,009,413.  The terminal branch is
`Q73_AND_Q74_SUCCESS_HORIZON_REACHED`; there is no failure or resource abort.
Records/history SHA-256 values are
`f765797dad4f6892524fc651a259786dff9c10187a6c634fc088fd3508c1e89f`
and `d521cdf189b54254cf3ca3d0e9033b52c90ea6ec91dc571d95a605e520972ff8`.
The 117,108-byte screen and 773,489-byte canonical SHA-256 values are
`5e2e077a9cab2a2b83f9830d755bafb7cc6dfa1d1c8a1ffade840d09e5016376`
and `4421f5973253968167b1c8bd77e024b18450325ea9581ed39dbe975ec8163ec9`.
The current ledgers cover 2,992 + 2,738 = 5,730 rows.

Those same-cap horizon routes are now complete.  Their frozen pre-replay audits
both closed at P0=0, P1=0 and P2=0, after which the fresh replays were run
serially rather than concurrently.  M keeps K=622,592/C34 and changes only
horizon 88 -> 90.  Its q88 private parent starts from q1; the old q88 canonical is
loaded only after replay as exact q1--88 evidence.  q89 pre-count 718,896 selects
index 33/K=622,592, drops 96,304 terms and 174,253,874,408 ticks, and commits
E=1,700,709,292,382,471 with retained digest
`b7d1e16a3f344eb1353593fd66c379d36272c49d1ebfe5c5c2b3e6958ed98c19`.
q90 pre-count 741,376 has no feasible row: minimum effective K is 635,284,
12,692 above the ceiling.  The branch is `Q89_SUCCESS_Q90_FAILURE`, with 90
records, 89 history entries, 3,060 rows and no resource abort.  Records/history
SHA-256 values are
`8978329b712168dce39991af25f6903deaf69c45f236521bb0e08e74f3d8741f`
and `c6755c7655d6b2ff37da7b1a8ac8c16cfc4295ef9ad0b687ddaa3dcd3c785d53`.
The 89,527-byte screen and 842,060-byte canonical SHA-256 values are
`f880e851bb16df5e659d7c0e6aa237d1836b17b4ad010d5676557ade2ba9140a`
and `d30359d9dd38c8e3a1461a0c7048645e35f478fa66920711871b3dc1c44bbd49`.
The replay took 13:05 with maximum RSS 689,500 KiB.

D keeps K=655,360/C37 and changes only horizon 74 -> 76.  The q74 private parent
retains q72 as its raw parent, replays from q1, and exposes the q74 canonical only
afterward as exact q1--74 evidence.  The screen keeps ordinary source pins under
262,144 bytes and gives the unique 841,495-byte encoded `.b85` boundary a
separate 1,048,576-byte exact-pin cap.  q75 pre-count 733,965 selects index
36/K=655,360, drops 78,605 terms and 127,874,290,338 ticks, and commits
E=2,289,318,681,442,732 with retained digest
`1a0c6aae47e81c4473b43ca5c27f8580a8754c72f9332e761bbddc1b31722def`.
q76 pre-count 789,691 has no feasible row: minimum effective K is 665,836,
10,476 above the ceiling.  The branch is `Q75_SUCCESS_Q76_FAILURE`, with 76
records, 75 history entries, 2,812 rows and no resource abort.  Records/history
SHA-256 values are
`5ba16ae933ae9a17633a1c3c4d7edba28b2c115bef475480272fa2cf9df39274`
and `b72e24b2dbe1d8eff88ff9ad1e1bc47cebeb59807168603cd86ff91c218c604a`.
The 58,178-byte screen and 798,861-byte canonical SHA-256 values are
`621f9c97b72c3582314d360b9b29b46a9cb40bf60298776adfc52849300bd14e`
and `856ede1f5774795c25ca2c36eafa8ac0696402194c6bf4e17ea5e8874efc22e0`.
The replay took 11:29 with maximum RSS 715,972 KiB.

These are complete no-feasible-candidate diagnostics, not resource aborts or
positive results: both canonicals keep `resource_policy_abort=null`, do not commit
a child boundary and add no certificate authority.  The local failure thresholds
identify `K=638,976/C35` as M's next discrete ladder point and `K=671,744/C38`
as D's; neither candidate has been executed and neither may be precommitted as a
success.  K=607,993 and the older K=638,976 evidence remain scoped to their
original predecessor state/prefix.  Certified depths remain M3/D2, with no new
boundary, witness, READY or certificate authority.  The two current ledgers
cover 3,060 + 2,812 = 5,872 rows.
