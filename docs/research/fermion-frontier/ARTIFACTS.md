# Artifact manifest

All copied JSON files are research-only outputs. They contain no credentials.

## Claude source session

- Session:
  `/home/pallasting/.claude/projects/-Data-CascadeProjects/7f73a250-8155-4f85-8d7e-f01582f0c0a2.jsonl`
- Round 1 workflow:
  `/home/pallasting/.claude/projects/-Data-CascadeProjects/7f73a250-8155-4f85-8d7e-f01582f0c0a2/workflows/wf_bc524afa-64c.json`
- Round 2 workflow:
  `/home/pallasting/.claude/projects/-Data-CascadeProjects/7f73a250-8155-4f85-8d7e-f01582f0c0a2/workflows/wf_d952301b-468.json`
- Round 3 partial workflow:
  `/home/pallasting/.claude/projects/-Data-CascadeProjects/7f73a250-8155-4f85-8d7e-f01582f0c0a2/workflows/wf_68398a04-e09.json`
- Temporary 70-claim ledger:
  `/tmp/claude-1000/-Data-CascadeProjects/7f73a250-8155-4f85-8d7e-f01582f0c0a2/scratchpad/gap345_claims.min.json`

## Preserved files

| File | Source transformation |
|---|---|
| `claude-round1-result.json` | Exact `.result` projection from round 1 workflow |
| `claude-round2-result.json` | Exact `.result` projection from round 2 workflow |
| `claude-round3-partial-result.json` | Exact `.result` projection from round 3 workflow |
| `gap345-claims.json` | Byte-for-byte copy of the temporary 70-claim ledger |

## Source hashes before preservation

- Gap 3/4/5 claim ledger:
  `ab11ba7a7648c6e2f5d37254d4500a8c405633280c443e4d83e9b2afd673fa81`
- Fixed Claude verification script (not copied; retained for provenance):
  `1f8d9fe0342c0ad111d7524a34d6207886cc13c5e3d06c37664e216eca28d108`

The copied workflow projections are independently hashed in
`SHA256SUMS` after creation.

## Post-takeover reproducible model

The following are authored research artifacts rather than copied Claude data,
so they are versioned normally and are not added to the preservation-only
`SHA256SUMS` list:

- `RESOURCE_MODEL_FERMI_HUBBARD_ZH.md`: assumptions, derivations, evidence
  boundaries, planning scenario, and decisive next measurements;
- `fermi_hubbard_resource_model.py`: standard-library-only executable model;
- `fermi_hubbard_resource_scenario.json`: deliberately incomplete physical
  planning configuration; `null` denotes an evidence gap;
- `fermi_hubbard_fig5_candidate_points.json`: finite-domain reconstructed points
  and candidate formulas, explicitly not author-supplied machine-readable data;
- `term_order_contract.json`: reconstructed group-order and fusion contract;
- `term_order_validator.py`: fail-closed group/term-set export validator;
- `term_order_native_fixture.json`: abstract native group-level fixture, not a
  hardware circuit export;
- `term_order_cross_route.py`: strict five-route individual-term sequence comparator
  with per-route SHA-256 fingerprints and embedded-route/manifest-key identity checks;
- `term_order_cross_route_template.json`: empty cross-route manifest, intentionally
  unresolved until all compiler exports are supplied;
- `test_term_order_cross_route.py`: six regression tests for exact sequence comparison
  and route-key relabeling rejection.
- `test_fermi_hubbard_resource_model.py`: all plotted candidate points, domain
  guards, common-order scheduling, first-step blocking, lattice-surgery
  translation, route-specific shots, and validation tests.
- `test_term_order_validator.py`: contract, fusion, term-set, and invalid-export
  regression tests.
- `fermi_hubbard_convergence.py`: schema-v2 dual-observable target-R assessor. It
  fixes the complete refinement grid, validates joint estimator covariance and
  provenance, requires a globally unique circuit fingerprint per route/R point,
  derives standard errors only from covariance diagonals, and uses validated
  effective-independent-sample counts and contribution ranges for finite-sample
  Bonferroni--Hoeffding checks. Unvalidated concentration/mitigation assumptions
  cannot produce binding readiness;
- `fermi_hubbard_convergence_template.json`: empty L=8 template for the canonical
  `staggered_magnetization` / `double_occupancy` pair and fixed
  `R=[25,50,100,200,400,800]` analysis plan; it remains `UNRESOLVED` until every
  required route supplies the complete vector-valued grid;
- `test_fermi_hubbard_convergence.py`: regression coverage for dual-observable
  target stability, bounded-reference readiness, screening-only evidence,
  family-wise finite-sample gates, covariance/provenance validation, and
  fail-closed grid/identity behavior.
- `measurement_campaign_contract.json`: standalone preflight policy pinned to the
  canonical evidence contract. It fixes exact-bounded reference comparisons,
  `alpha=0.05`, the residual half-width allocation `h=0.002`, and allowed bounded
  mitigation modes; it is a planning contract, not a measurement record.
- `measurement_campaign_template.json`: complete 24-cell route/R planning grid with
  physical contribution ranges. Its acceptance probability `p` and effective-shot
  fraction `eta` remain null, so no accepted-shot or raw-execution total is invented.
- `measurement_campaign_validator.py`: derives the four routes, six R values and
  point/adjacent/reference family rather than accepting user-supplied counts. The
  current template has family size `136`, requires `4,300,768` effective shots per
  shared route/R cell at `h=0.002`, and totals `103,218,432` effective shots; it also
  demonstrates that `10,000` shots fail the required statistical gate. Its output is
  preflight only and never certifies convergence.
- `test_measurement_campaign_validator.py`: twenty-five campaign arithmetic,
  identity, allocation, null-raw-total, numeric-boundary, CLI and fail-closed schema
  regressions.
- `reference_qualification_contract.json`: standalone qualification policy that
  exactly matches the evidence convergence workload and fixes the two observable
  identities, binding/diagnostic method classes, directed interval rounding, and
  method-specific certification claims.
- `reference_qualification_template.json`: empty two-observable qualification ledger;
  with no reference records it intentionally returns `UNRESOLVED`.
- `reference_qualification_validator.py`: verifies physical ranges and workload
  identity, safe local JSON-certificate paths and SHA-256, exact ledger-to-certificate
  record binding, four-part deterministic error decomposition,
  solver/configuration/checker/commit/environment/theorem provenance, externally
  supplied route-input independence, and method claims. Uncertified
  TN/Krylov/stochastic methods are capped at `DIAGNOSTIC_ONLY`; because no fixed
  machine checker is executed, the maximum state is
  `STRUCTURALLY_COMPLETE_UNVERIFIED`, with bound-budget adequacy unassessed and
  `ready_gate_eligible=false`.
- `test_reference_qualification_validator.py`: twenty-nine focused regressions covering empty,
  diagnostic and structurally complete states, arbitrary/non-JSON artifacts,
  certificate/hash/content/identity drift, error sums, missing or reused external
  route inputs, directed rounding, method claims, and the absence of any reachable
  `QUALIFIED_BOUNDED` state.
- `REFERENCE_CERTIFICATION_STRATEGY.md`: current primary-source assessment of full-ED,
  Majorana/Pauli operator propagation, locality/Krylov, tensor-network and real-time
  QMC reference routes, plus the proposed deterministic-certificate execution order.
- `operator_propagation_certificate_contract.json`: fixed two-qubit conformance
  profile that pins the exact checker source, two noncommuting Pauli rotations, raw
  observable terms, computational-basis state, ordering semantics and hard resource
  caps.
- `operator_propagation_certificate_template.json`: nontrivial synthetic certificate
  whose duplicate input strings, rigorous Taylor intervals, merge-before-drop state,
  dropped-`L1` ledger and final expectation interval are all independently recomputed.
- `operator_propagation_certificate_checker.py`: stdlib-only Fraction proof kernel for
  `G_P(theta)=exp(-i theta P/2)`. It verifies only the declared circuit and returns at
  most `VERIFIED_CIRCUIT_TRUNCATION_SUBCERTIFICATE`; mapping, product-formula error,
  budget adequacy, L=8 and READY remain unassessed, and the CLI always exits nonzero.
- `test_operator_propagation_certificate_checker.py`: twenty-four arithmetic,
  interval, Pauli-phase, ordering, hash, byte-cap, state-boundary and fail-closed tests.
- `operator_propagation_l2_witness.py`: executable 8-qubit JW conformance cross-check
  for the full L=2, `R=2`, `T=1` raw Strang sequence (112 rotations). It matches the
  independent direct-fermion pilot but defers the full Fraction certificate at the
  explicit resource boundary.
- `test_operator_propagation_l2_witness.py`: eight gate-count, identity, dual-observable,
  local Fraction enclosure, ideal-reference separation, resource-boundary and CLI
  regressions.
- The measurement-campaign, reference-qualification and proof-kernel artifacts are
  currently independent of `fermi_hubbard_evidence.py`; none is yet an outer
  `READY_FOR_BENCHMARK` component.
- `fermi_hubbard_l2_pilot.py`: dependency-free L=2 dual-observable deterministic
  product-formula screening generator;
- `fermi_hubbard_l2_pilot_manifest.json`: generated deterministic pilot data whose
  scaled-Taylor references are `approximate_unbounded`; it is
  `SCREENED_FOR_TARGET_R` at `R=32`, not an error-bounded certificate;
- `test_fermi_hubbard_l2_pilot.py`: dual-observable values, fixed R-grid,
  screening status, reference boundary, and size-bound regression coverage.
- `first_step_contract.json`: required per-route first-step, steady-state, and timing
  fields with fail-closed status rules;
- `first_step_ledger_template.json`: empty five-route ledger, intentionally unresolved;
- `first_step_ledger_validator.py`: validator that separates unresolved, bookkeeping-closed
  estimates, and exact compiled totals;
- `test_first_step_ledger_validator.py`: six regression tests for the first-step contract.
- `evidence_manifest_contract.json`: logical/physical route maps, workload fingerprint,
  L/R coherence, target-R stability, and required native/surface component contract;
- `evidence_manifest_template.json`: empty unified manifest with unresolved term-order,
  first-step, native-transition, surface-place-route, and convergence components;
- `fermi_hubbard_evidence.py`: orchestration validator producing `UNRESOLVED`,
  `INCONSISTENT`, `MISMATCH`, or `READY_FOR_BENCHMARK`; convergence contributes
  to the last state only when it is `READY_FOR_TARGET_R`, never when it is merely
  `SCREENED_FOR_TARGET_R`;
- `test_fermi_hubbard_evidence.py`: seventeen integration regression tests,
  including convergence-policy drift, missing-observable, screening-only, and
  route-by-observable stability rechecks.
- `native_transition_contract.json`: occurrence-level native matching class/count and
  measured timing contract;
- `native_transition_template.json`: empty 801-occurrence L=8/R=100 ledger;
- `native_transition_validator.py`: fail-closed transition/timing validator;
- `test_native_transition_validator.py`: six native transition regression tests.
- `surface_place_route_contract.json`: surface patch, operation, timing, evidence,
  active-volume, event-binding, and failure-union-bound contract;
- `surface_place_route_template.json`: empty L=8/R=100 surface schedule ledger;
- `surface_place_route_validator.py`: fail-closed patch-count/distance, placement,
  contiguous corridor, timeline, operation-window, shared-patch conflict, live-data,
  dependency, logical-event, active-volume, and failure-budget validator;
- `test_surface_place_route_validator.py`: twenty-seven closure and adversarial regression tests.
- `evidence_manifest_source_snapshot.json`: known L=8/R=100 source-leading and derived
  subtotals with unresolved timing/term/surface/convergence fields;
- `SOURCE_SNAPSHOT_NOTES.md`: provenance and non-closure explanation for the snapshot.
- `DYNAMIC_JW_SOURCE_EVIDENCE.md`: primary-source ledger for Fig. 5/Fig. 14,
  Appendix I leading counts, explicit first-step omission, and unresolved individual
  term/compiled-event fields.
- `FSN_SOURCE_EVIDENCE.md`: primary-source ledger separating the generic Kivlichan
  FSN theorem from dynamic-JW Fig. 15 standard/ladder candidate fits.
- `NATIVE_SOURCE_EVIDENCE.md`: primary-source ledger separating the PNAS proposal,
  2026 local collisional-gate experiment, and 2026 global-control proposal.
