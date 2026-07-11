# Final adversarial review

Review date: 2026-07-11

Reviewed artifacts:

- [full synthesis](FINAL_SYNTHESIS.md)
- [Chinese executive brief](EXECUTIVE_BRIEF_ZH.md)
- [post-ledger QC-AFQMC update](POST_LEDGER_MATCHGATE_UPDATE.md)

Three reviewers independently audited different failure surfaces after the
draft synthesis was complete.

## Final verdict

| Reviewer | Primary lens | Initial verdict | Required changes | Final verdict |
|---|---|---|---|---|
| A | Condensed matter, field theory, lattice no-go results, Gaussian geometry | PASS with two optional precision edits | Qualify locality/doubler freedom as properties of proper local overlap/GW constructions; narrow the final lattice statement to chiral, doubler-free regulators | PASS |
| B | Complexity, DPP proof status, neural states, encodings, hardware resources | NEEDS REVISION | Separate arbitrary measured states in matchgate shadows from arbitrary non-Gaussian dynamics; restore the discrete-DPP spectral-approximation proof reservation | PASS after revision |
| C | Cross-domain classification, counts, publication maturity, independence, English/Chinese consistency | NEEDS MINOR FIXES | Put DPP ML theorems under direct support and only their free-fermion attribution under transfer; spell out `64 = 56 + 8`; fix Chinese spacing | PASS after revision |

All three reviewers marked the final artifacts ready to share after the listed
changes were applied.

## Correction log

The adversarial pass produced the following material safeguards:

1. The five meanings of continuity remain separate. Luttinger/filling
   `'t Hooft` anomalies, ABJ axial anomalies, regulator continuum limits, and
   Gaussian group flows are not presented as one law.
2. The axial-anomaly formula is limited to the audited one-Dirac-fermion
   convention, with coefficient/sign dependence and vector-current separation
   explicit.
3. Ginsparg–Wilson is not treated as an algebraic relation that automatically
   guarantees every desirable regulator property; proper local constructions
   are the claim.
4. Matchgate shadows retain specified overlap tasks for arbitrary measured
   states, even though arbitrary non-Gaussian dynamics leave FLO simulation
   closure. The earlier compound wording was too narrow.
5. The DPP-SGD practical estimator's unbiasedness is separated from the
   stronger variance-rate transfer, whose spectral-approximation rigor remains
   qualified in the original appendix.
6. Classical DPP theorems are direct statistics/ML results. Their explanation
   through free-fermion history is a mathematical transfer, not physical
   causation.
7. The post-ledger QC-AFQMC update records absolute cost and forbids reading
   `9x` or `656x` as a same-task end-to-end quantum speedup.
8. The English and Chinese reports now use the same focused-ledger accounting:
   56 unanimous verified findings, 8 split/partial accepted findings, and 6
   refuted as written.

## Post-ledger update audit

The June 2026 Physical Review Research accepted paper was separately reviewed
3–0. The reviewers agreed on the following boundary:

- a 24-qubit (`16 data + 8 leakage ancilla`) hybrid QPU–GPU QC-AFQMC workflow
  was executed;
- `9x` is a workload-tuned per-circuit Forte throughput comparison;
- `656x` is a normalized and extrapolated classical post-processing estimate;
- neither number is a measured end-to-end quantum speedup;
- QPU reaction barriers remain about 10 kcal/mol from the frozen-core CCSD(T)
  reference and reverse the relative ordering;
- the work is an industry-led engineering milestone, not chemical accuracy or
  independent replication.

## Release gate

The release gate is satisfied:

- all focused ledger indices `0–69` are present exactly once;
- the JSONL ledger parses and contains 64 accepted / 6 refuted statuses;
- split decisions retain mandatory replacement wording;
- preprints, accepted papers, peer-reviewed proposals, component experiments,
  and end-to-end workflows are labeled separately;
- source-lineage dependencies are disclosed;
- no final conclusion depends on a refuted compound claim;
- the full and Chinese summaries agree on the thesis, counts, hardware
  maturity, and next priorities.
