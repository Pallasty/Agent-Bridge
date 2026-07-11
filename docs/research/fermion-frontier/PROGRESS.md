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

## Next update

Begin the first execution task from the final roadmap: construct a matched
logical-to-physical resource model for one Hubbard or lattice-gauge workload
across native fermions, fermionic swap networks, dynamic Jordan–Wigner, and
surface-code lattice surgery. The comparison must fix a target error and report
preprocessing, gate count, topology/depth, physical space-time, movement,
readout, classical post-processing, and amortization in one table.
