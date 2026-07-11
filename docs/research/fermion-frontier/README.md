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

The third round is incomplete: only five claims received a full 3-0 vote;
five more received 2-0 and remain provisional under this takeover's stricter
three-vote gate. Sixty claims have no valid adjudication. The original third
round synthesis failed after the Claude session hit its usage limit.

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

This thesis remains a synthesis target rather than a final verdict until the
open verification batches are closed.

## Planned verification batches

1. Gaussian/non-Gaussian boundary: **complete** — 22 verified and 3 refuted as
   written; corrected findings are in `BATCH1_GAUSSIAN_NONGAUSSIAN_REVIEW.md`.
2. DPP and negative-dependence ML: finish four unverified sources and add the
   missing third vote to the current 2-0 coreset claims.
3. Fermion-to-qubit mappings and native hardware: HATT, programmable neutral
   atom fermionic processing, and the 2026 dynamic Jordan-Wigner construction.
4. Final synthesis and adversarial review.
