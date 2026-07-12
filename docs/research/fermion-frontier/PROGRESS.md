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

None of the campaign, reference-qualification, proof-kernel, mapping, checkpoint,
commutator or grouping-screen interfaces is currently loaded by
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
