# Research progress ledger

Status date: 2026-07-11

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
