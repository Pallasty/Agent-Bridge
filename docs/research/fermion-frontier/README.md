# Fermion frontier research takeover

Status date: 2026-07-11

Scope: physical fermions, not the historical Fermion Memory service.

## Research question

The inherited Claude investigation has two linked but non-identical questions:

1. What does “fermion continuity” mean across condensed matter, field theory,
   lattice theory, and fermionic Gaussian-state dynamics?
2. Under which assumptions does antisymmetry, Gaussian closure, parity grading,
   or determinant/Pfaffian structure create a computational or statistical
   advantage in high-dimensional spaces?

The final report must not invent a single unified “fermion continuity” law.
It must separate established physical meanings before comparing their
mathematical structures.

## Inherited evidence

Claude completed two broad deep-research rounds and began a focused third
verification round:

| Round | Candidate claims | Claims adjudicated | Confirmed | Refuted | Durable result |
|---|---:|---:|---:|---:|---|
| Full survey | 120 | 25 | 22 | 3 | `claude-round1-result.json` |
| Targeted gap survey | 119 | 25 | 21 | 4 | `claude-round2-result.json` |
| Gap 3/4/5 verification | 70 | 10 | 10 | 0 | `claude-round3-partial-result.json` |

At takeover, the third round was incomplete: only five claims had a full 3-0
vote, five more had 2-0 votes, and sixty had no valid adjudication. The original
third-round synthesis failed after the Claude session hit its usage limit.

The compact 70-claim input is preserved as `gap345-claims.json`. Original
Claude paths and content hashes are recorded in `ARTIFACTS.md`.

## Evidence contract

A claim may enter the final report as a finding only when all of the following
are explicit:

- its physical meaning and domain;
- assumptions and theorem/experiment scope;
- asymptotic complexity and practical or constant-factor costs when relevant;
- failure boundary or counterexample;
- primary source and publication status;
- three independent verdicts, with disagreement retained;
- classification as direct support, mathematical transfer, or analogy.

Additional rules:

- A 2026 preprint is at most medium-confidence without independent support.
- A 2-0 vote is provisional, not fully verified.
- “Efficiently sampleable DPP” does not imply efficient DPP MAP optimization.
- Matchgate classical simulability is not a quantum-computing advantage.
- A hardware architecture proposal is not an end-to-end experimental machine.
- A natural-gradient analogy to machine learning is not a direct application
  until the two metrics and optimization domains are mapped explicitly.

## Current working thesis

Fermionic structure is not a universal computational advantage. It becomes a
lever when the task preserves Gaussian closure, parity grading,
determinant/Pfaffian algebra, negative dependence, or a target symmetry that is
intrinsically antisymmetric. Non-Gaussian resources, interactions, encoding
overheads, high polynomial degree, and mismatched inductive bias delimit the
advantage.

The three focused verification batches are closed, and this thesis passed the
final cross-cluster adversarial review with all required corrections applied.

## Planned verification batches

1. Gaussian/non-Gaussian boundary: **complete** — 22 verified and 3 refuted as
   written; corrected findings are in `BATCH1_GAUSSIAN_NONGAUSSIAN_REVIEW.md`.
2. DPP and negative-dependence ML: **complete** — the full 30-claim cluster has
   28 verified and 2 refuted as written; corrected findings are in
   `BATCH2_DPP_REVIEW.md`.
3. Fermion-to-qubit mappings and native hardware: **complete** — 12 fully
   verified, 2 verified only after partial rewrite, and 1 refuted as written;
   corrected findings and the July 2026 experimental maturity update are in
   `BATCH3_ENCODING_HARDWARE_REVIEW.md`.
4. Final synthesis and adversarial review: **complete**.
5. First roadmap execution task, evidence-bounded Fermi--Hubbard resource model:
   **planning scaffold complete; matched benchmark still open** — logical
   subtotals, topology, first-step unknowns, route-specific error/shots
   bookkeeping, and a parameterized native/bare-qubit/lattice-surgery physical
   translation are implemented. Cross-compiler term-order validation and current
   primary-source gaps remain explicit as `UNRESOLVED`.

The focused 70-claim ledger is fully adjudicated: 56 unanimous verified, 8
split/partial accepted, and 6 refuted as written, with every mandatory rewrite
retained in `claim-status.jsonl`.

## Final deliverables

- [Chinese executive brief](EXECUTIVE_BRIEF_ZH.md)
- [Full technical synthesis](FINAL_SYNTHESIS.md)
- [Final adversarial review](FINAL_ADVERSARIAL_REVIEW.md)
- [Post-ledger June 2026 matchgate/QC-AFQMC update](POST_LEDGER_MATCHGATE_UPDATE.md)
- [Evidence-bounded 2D Fermi--Hubbard resource model (Chinese)](RESOURCE_MODEL_FERMI_HUBBARD_ZH.md)
- Reproducible model: `fermi_hubbard_resource_model.py`, scenario
  `fermi_hubbard_resource_scenario.json`, Fig. 5 candidate points
  `fermi_hubbard_fig5_candidate_points.json`, term-order contract/validator and
  cross-route sequence comparator/template, convergence template/assessor,
  first-step ledger contract/template/validator, unified evidence manifest
  contract/template/orchestrator, native transition contract/template/validator,
  and the dynamic-JW primary-source evidence ledger,
  plus the FSN primary-source evidence ledger,
  and the native-fermion primary-source evidence ledger,
  an L=2 exact-reference pilot, and unit tests
  `test_fermi_hubbard_resource_model.py` /
  `test_term_order_validator.py` /
  `test_term_order_cross_route.py` /
  `test_fermi_hubbard_convergence.py` /
  `test_fermi_hubbard_l2_pilot.py` /
  `test_first_step_ledger_validator.py` /
  `test_fermi_hubbard_evidence.py` /
  `test_native_transition_validator.py`
- Batch reviews: `BATCH1_GAUSSIAN_NONGAUSSIAN_REVIEW.md`,
  `BATCH2_DPP_REVIEW.md`, and `BATCH3_ENCODING_HARDWARE_REVIEW.md`
