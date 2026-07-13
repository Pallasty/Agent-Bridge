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
- `hubbard_jw_mapping_contract.json`: source-pinned fixed L=2/L=3 OBC policy for
  site-major/spin-minor JW bonds, unshifted onsite terms, raw R=2 Strang events,
  selected CAR/onsite witnesses, explicit identity/global-phase accounting and the
  pinned L2 112-gate cross-source binding.
- `hubbard_jw_mapping_template.json`: positive canonical profile claims and digests;
  its maximum status remains `VERIFIED_CANONICAL_JW_MAPPING_SUBCERTIFICATE`.
- `hubbard_jw_mapping_validator.py`: stdlib-only exact mapping checker. It regenerates
  bonds/terms/events, compares exact CAR and Pauli actions, evaluates all four onsite
  occupations, runs the pinned L2 sequence builder, clears failed scopes and always
  exits nonzero because product-formula error, L=8 and READY are not assessed.
- `test_hubbard_jw_mapping_validator.py`: thirty-four mapping, parity, sign,
  global-phase, source/digest, strict-JSON, resource, API/CLI and overclaim regressions.
- `pauli_bitset_backend.py`: non-authoritative exact `(x_mask,z_mask)` Pauli arithmetic,
  checker-compatible Fraction interval propagation and deterministic canonical
  checkpoint digest prototype; certificate authority is explicitly `NONE`.
- `test_pauli_bitset_backend.py`: thirty-five exhaustive/random algebra, interval,
  checkpoint, cap, malformed-input and L2-prefix conformance regressions.
- `operator_propagation_checkpointed_l2_contract.json`: fixed source pins, mapped
  112-gate L2 circuit identity, two observable definitions, checkpoint schedule,
  fifth-order Taylor policy, outward `2^32` quantization and hard resource caps.
- `operator_propagation_checkpointed_l2_template.json`: positive full-circuit claims
  for 20 checkpoints per observable.  Its final/peak term counts are 16,380/16,381,
  cumulative dropped `L1` is zero, and the two declared-circuit expectation intervals
  and canonical checkpoint digests are independently reproducible.
- `operator_propagation_checkpointed_l2.py`: exact bitset/Fraction checker that loads
  hash-verified dependencies from the same bytes it executes and returns at most
  `VERIFIED_L2_MAPPED_CIRCUIT_TRUNCATION_SUBCERTIFICATE`.  Product-formula error,
  L8, reference qualification and READY remain unassessed; the CLI exits nonzero.
- `test_operator_propagation_checkpointed_l2.py`: fifty-one regressions covering full
  replay, mapping/source pins, checkpoints, intervals, quantization, no-drop,
  strict-schema, resource, API/CLI and fail-closed behavior.
- `hubbard_strang_commutator_contract.json`: source-pinned Schubert--Mendl
  Proposition-2/Eq.-13 policy for the fixed L2/L3/L8 OBC
  `H1,H2,HU,H3,H4` split, raw S2 binding, exact commutators, coefficient-L1 norm
  substitution, R-step telescoping and generic observable factor two.
- `hubbard_strang_commutator_template.json`: exact group, phase-ledger,
  nested-family, digest and resource claims.  The L8 result is `C=7076/3`, unitary
  bound `1769/7500`, generic observable bound `1769/3750` at R=100, and minimum
  generic-allocation R of 4,344.
- `hubbard_strang_commutator_checker.py`: independently regenerates and merges every
  fixed nested Pauli commutator, performs full L2 and selected L3 sparse-action
  oracles, cross-checks pinned mapping/bitset sources, and returns at most
  `VERIFIED_STRANG_COMMUTATOR_L1_SUBCERTIFICATE`; it does not compose a physical
  reference and always exits nonzero.
- `test_hubbard_strang_commutator_checker.py`: fifty regressions covering the formula,
  group order, commutation, raw palindrome, common phase, exact values, action oracles,
  source execution, strict schema, resources, failure scopes and the CLI boundary.
- `hubbard_strang_grouping_screen_contract.json`: fixed L8 OBC policy for exhaustive
  five-group and plaquette-boundary order screens, source pins, materiality threshold,
  R=100 allocation and exact expected-screen digest.
- `hubbard_strang_grouping_screen_template.json`: positive nonqualifying screen.  The
  best five-group value is `C=7072/3`; the best OBC plaquette-boundary value is
  `C=7232/3`; both remain far above the exact R=100 ceiling `C=5/4`.
- `hubbard_strang_grouping_screen.py`: verifies the pinned base subcertificate, exact
  OBC Hamiltonian cover and all 144 permutations.  It imports no PBC paper decimal as
  OBC evidence, does not match candidate cluster exponentials to the benchmark
  circuit, returns at most `VERIFIED_STRANG_GROUPING_COEFFICIENT_L1_SCREEN`, and
  always exits nonzero.
- `test_hubbard_strang_grouping_screen.py`: thirty-nine exact-value, permutation,
  Hamiltonian-cover, plaquette-structure, source-pin, strict-schema, tamper,
  failure-scope and CLI regressions.
- `hubbard_strang_generic_bound_no_go_contract.json`: fixed L8 five-group theorem,
  half-filled Néel witness, exact coefficient ceiling, paper/official-code provenance,
  source pins, resource caps and expected-witness digest.
- `hubbard_strang_generic_bound_no_go_template.json`: positive infeasibility witness
  with exact nested/action digests, `||A|q>||^2=295200`, squared contribution lower
  bound 2,050 versus ceiling `25/16`, and the necessary-step boundary 601/602.
- `hubbard_strang_generic_bound_no_go_checker.py`: recomputes one exact nested family
  and its sector-preserving basis action.  It proves that globally exact cluster
  spectral norms cannot make the fixed generic R=100 theorem expression qualify,
  while explicitly not lower-bounding actual error or importing upstream binary64.
- `test_hubbard_strang_generic_bound_no_go_checker.py`: thirty-eight operator/witness,
  amplitude, sector, exact-square, margin, R-boundary, source-pin, strict-schema,
  tamper, failure-scope and CLI regressions.
- `hubbard_strang_observable_taylor_step_checker.py`: source-pins the fixed Strang
  backend and specializes the Fang--Qu iterated Taylor remainder to both target
  observables.  It exactly verifies degree-zero through degree-two cancellation,
  degree-three defects, all 495 fourth-order paths, strict initial-observable
  `delta=1/100` operator/expectation bounds and L8 Néel-sector action witnesses.  It
  explicitly does not multiply the initial bound into a full R=100 claim.
- `test_hubbard_strang_observable_taylor_step_checker.py`: thirty-two source,
  composition, observable-identity, exact-Fraction, formal-residual, remainder-path,
  one-step, uniform-floor, action/sector, resource, cache, failure-scope and CLI
  regressions.
- `hubbard_d3_double_occupancy_symbolic_terms.b85`: bounded compressed fixture of
  2,748 simplified physical-fermion terms for `D3=-i[B3,D]`; it has no independent
  authority and is accepted only after the checker expands all 18,544 field terms
  and proves exact JW equality to the source-pinned 8,928-term Pauli oracle.
- `hubbard_d3_double_occupancy_cluster_no_go_contract.json`: same-byte checker pin,
  compressed/raw fixture pins, upstream audit metadata, fixed greedy14 partition,
  global half-filled Néel witness policy, uniform-supremum scope, resource caps and
  witness digest.
- `hubbard_d3_double_occupancy_cluster_no_go_template.json`: positive narrow
  no-go witness with all 43 cluster count/support summaries and the first 30 detailed
  exact global-sector matrix-element/JW-action records, whose sum is
  `1945/768>5/2`.
- `hubbard_d3_double_occupancy_cluster_no_go_checker.py`: independently expands the
  physical fixture, verifies exact fermion-to-Pauli D3 identity, replays the fixed
  fixture-defined greedy partition and proves that even exact cluster norms followed
  by the same k=0 triangle sum cannot seed the R=100 uniform-supremum certificate. It
  does not rule out a per-step cluster ledger or lower-bound the globally merged D3
  norm; upstream decomposition/order provenance remains external audit metadata.
- `test_hubbard_d3_double_occupancy_cluster_no_go_checker.py`: forty source/fixture,
  exact-JW identity, partition, global-sector action, rational-margin, strict-schema,
  tamper, failure-scope and CLI regressions.
- `hubbard_l8_observable_interval_step_contract.json`: same-byte checker pin,
  positive Strang-backend source pins, fixed L8 OBC/JW workload, fused
  nine-stage/1,152-gate sequence, `2^64` outward fixed-point policy, Taylor
  truncation index `N=5`, eight-gate checkpoint cadence, deterministic top-65,536
  ranking, hard resource caps and expected-witness digest.
- `hubbard_l8_observable_interval_step_template.json`: positive one-step
  mapped-circuit fixture for both observables.  It binds the independently rebuilt
  per-checkpoint ledgers by count/digest/nonzero/max summaries, retains nine stage
  summaries per observable, and records the exact final retained and dropped-`L1`-
  expanded mapped-step expectation intervals.
- `hubbard_l8_observable_interval_step_checker.py`: independently regenerates the
  112 geometric/224 spin-resolved OBC bonds, five mapped groups, 3,584 representative
  CAR and 256 onsite witnesses, raw-to-fused central-H4 equivalence, phase ledger and
  both one-step interval propagations.  It returns at most
  `VERIFIED_L8_ONE_STEP_MAPPED_INTERVAL_TRUNCATION_SUBCERTIFICATE`; exact-Hubbard
  error, the full R=100 chain, reference qualification and READY remain unassessed.
- `test_hubbard_l8_observable_interval_step_checker.py`: source-pin, L8 mapping,
  raw/fused sequence, phase, fixed-tick interval, checkpoint, deterministic ranking,
  nonzero-drop, exact tick-value, resource-cap, tamper, fail-closed and CLI-boundary
  regressions.
- `hubbard_l8_interval_checkpoints/*.b85`: five canonical 100-column Base85-wrapped
  single-zlib-stream sidecars containing both observables' complete 65,536-term
  retained interval expansions at boundaries one and two plus magnetization
  boundary three.  Each state binds the
  root one-step checker/witness, fixed backprop sequence, cumulative drop and retained
  Néel expectation; the child contract separately pins encoded, compressed and raw
  SHA-256 identities.
- `hubbard_l8_observable_interval_two_step_contract.json` and
  `hubbard_l8_observable_interval_two_step_template.json`: same-byte parent pins,
  four-layer sidecar custody, fixed child policy/resources, exact step-2 expansion,
  state, transition and expected-witness identities, with no remaining-step or
  exact-Hubbard claim.
- `hubbard_l8_observable_interval_two_step_checker.py`: verifies the positive parent
  transition, decodes and validates all four boundaries, executes a second fixed
  1,152-gate/144-checkpoint step without cross-boundary fusion, proves
  `E2=E1+d2`, compares boundary two term for term and reports the dropped-L1-expanded
  two-step mapped-circuit intervals.
- `test_hubbard_l8_observable_interval_two_step_checker.py`: parent/source pin,
  transport/raw/state/semantic custody, exact transition, recurrence, resource,
  compression/JSON/order/integer adversarial, tamper, cache, failure-scope and CLI
  regressions.
- `hubbard_l8_double_occupancy_adaptive_k_policy_v1.json`: output-independent
  precommit for the bounded double-occupancy step-3 attempt.  It freezes the
  nine-candidate `K=65,536..131,072` ladder, the exact future-checkpoint truncation
  prefix envelope, parent boundary/transition anchors, one-propagation suffix-sum
  selection rule and hard resource failures.  It contains no step-3 output pin;
  any relaxed candidate or resource limit requires a new policy version.
- `hubbard_l8_adaptive_k_arithmetic_v2.py`: certificate-authority-free, source-pinned
  high-cap arithmetic kernel for the next adaptive-K policy generation.  It keeps
  the v1 fixed-tick digest domain while locally implementing propagation, interval
  multiplication, expectation, deterministic ranking, suffix drops and
  first-feasible selection; it neither patches nor calls the v1 propagation,
  digest or truncation routines.  Its broad kernel caps do not themselves authorize
  a child transition: each observable still requires a tighter precommitted policy
  and a separately pinned formal checker.
- `test_hubbard_l8_adaptive_k_arithmetic_v2.py`: old-domain arithmetic/digest parity,
  root-source drift, local-kernel isolation, transient/resource cap, exact schema,
  deterministic tie, first-feasible/no-commit and retained-`K=65,536` truncation
  regressions.
- `hubbard_l8_adaptive_k_v2_design_probe.py` and the magnetization/double-occupancy
  `*_adaptive_k_v2_design_transcript.json` files: explicitly non-authoritative,
  deterministic policy-design probes using the committed v2 kernel.  They exclude
  runtime, RSS, host, path and floating-point fields from the semantic bytes.  With
  policy maximum `K=327,680`, magnetization commits 28 checkpoints before
  checkpoint 29 needs effective `K=333,983`; double occupancy commits 21 before
  checkpoint 22 needs `K=350,604`.  No transcript is a child witness, transition or
  sidecar, and both leave certified depth unchanged.
- `test_hubbard_l8_adaptive_k_v2_design_probe.py`: source/kernel isolation,
  canonical transcript, exact prefix/recurrence, every-candidate feasibility,
  first-feasible, deterministic replay hash, failure summary, resource and
  diagnostic-only scope regressions.
- `hubbard_l8_magnetization_adaptive_k_policy_v2.json` and
  `hubbard_l8_double_occupancy_adaptive_k_policy_v2.json`: design-informed but
  formal-output-unpinned precommits for the next two adaptive attempts.  They bind
  the immediate positive parent and input boundary, committed v2 kernel,
  non-normative design transcript, exact future-prefix budget, respectively 17/21
  candidates through `K=327,680`, policy-specific `786,432` live/digest and
  `536,870,912` visit caps, fail-closed output rules and v3 child-state schema.
  Neither policy contains a formal failure checkpoint, selected-K history, child
  hash/value, resource observation, witness or positive status.
- `test_hubbard_l8_adaptive_k_policy_v2.py`: exact top-level schema, same-byte
  kernel/transcript/parent/boundary custody, candidate SHA, integer budget,
  kernel-capability containment, output-pin absence and precommit-scope tests.
- `hubbard_l8_magnetization_interval_step3_checker.py`, contract and template:
  same-byte execute the positive immediate two-step parent and certify only the
  adjacent magnetization `2 -> 3` fixed-K transition.  They bind state-v2 parent,
  previous-transition and policy identities, 144 fresh checkpoints, `E3=E2+d3`,
  the complete boundary-3 sidecar and the three-step mapped interval; double
  occupancy, step 4, exact-Hubbard error, reference and READY remain unassessed.
- `test_hubbard_l8_magnetization_interval_step3_checker.py`: 46 parent-DAG, adjacent
  sidecar, state-v2, anchor, sequence, recurrence, resource, cache, tamper and CLI
  regressions with one full public replay.
- `hubbard_l8_double_occupancy_adaptive_k_v1_screen_checker.py`, contract and
  template: same-byte replay the positive two-step parent and precommitted policy,
  verify six first-feasible K selections, and certify the seventh-checkpoint
  infeasibility result without committing a child boundary or increasing depth.
- `test_hubbard_l8_double_occupancy_adaptive_k_v1_screen_checker.py`: 43 policy,
  source, parent, suffix-selection, exact-ledger, failure, resources, cache, scope and
  CLI regressions with one full public replay.
- The measurement-campaign, reference-qualification, proof-kernel, mapping,
  checkpoint, commutator, grouping-screen, generic-bound no-go, observable-Taylor
  step, double-occupancy-cluster no-go, shared L8 two-step intervals,
  magnetization-only step 3 and depth-2 double-occupancy screen artifacts are
  currently independent of
  `fermi_hubbard_evidence.py`;
  none is yet an outer `READY_FOR_BENCHMARK` component.
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
