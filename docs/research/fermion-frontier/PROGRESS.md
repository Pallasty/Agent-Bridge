# Research progress ledger

Status date: 2026-07-11

## State labels

- `VERIFIED`: three valid independent votes and no two-vote refutation.
- `PROVISIONAL`: two supporting votes but fewer than three total votes.
- `REFUTED`: at least two independent refutation votes.
- `UNVERIFIED`: fewer than two valid votes.
- `INFERRED`: synthesis or cross-domain mapping not directly asserted by a
  source.

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
7. Fast exact DPP sampling and DPP coreset advantages, partially verified.

## Open clusters

| Cluster | Candidate claims | Current state |
|---|---:|---|
| DPP / negative-dependence ML | 30 | 5 verified, 5 provisional, 20 unverified |
| Non-Gaussian fermionic simulation | 10 | 9 verified, 1 refuted/rewrite-required |
| Fermion-to-qubit encoding / native hardware | 15 | Unverified |
| Gaussian-state manifold geometry | 15 | 13 verified, 2 refuted/rewrite-required |

## QA findings

- Round 1 metadata reports 11 post-synthesis findings, while the original
  narrative called them 10. The JSON result count is authoritative.
- `unverified: 0` in rounds 1 and 2 describes the selected 25-claim voting
  batch, not all 120/119 extracted candidates.
- Five round 3 DPP coreset claims were accepted with only 2-0 votes. They are
  provisional here until a third independent vote is recorded.
- No unified final report was produced by Claude.

## Next update

Proceed to the DPP/negative-dependence batch. Reuse existing votes, add the
missing third coreset vote, and verify the four untouched sources before any
cross-project application proposal.
