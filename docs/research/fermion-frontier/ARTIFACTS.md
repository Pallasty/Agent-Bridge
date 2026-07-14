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
- `hubbard_l8_adaptive_k_v2_dual_screen_checker.py`, contract and template:
  source-pinned, contract-self-executing formal authority for the two precommitted
  v2 infeasibility screens.  It same-byte executes the positive magnetization
  step-3 parent (and its transitive positive two-step parent), runs both new attempts
  from prehashed kernel/root/parent modules, independently recomputes every prefix,
  candidate, first-feasible choice and ledger digest, and certifies only the
  checkpoint-29/checkpoint-22 maximum-K failures.  No child boundary, transition,
  sidecar or depth increment is generated; the compact witness SHA-256 is
  `79f5cfeebfe87ea45af1c29eefe9b1468af0099d9cd3501dc732cbff0ca8fcf5`.
- `test_hubbard_l8_adaptive_k_v2_dual_screen_checker.py`: checker/contract/source,
  canonical-policy, verified-module loader/escape, live-monkeypatch self-exec,
  exact ledger/budget/first-feasible, tamper, resource, diagnostic-separation,
  compact-witness and structured CLI regressions, plus an opt-in full public replay.
- `hubbard_l8_adaptive_k_v3_design_probe.py` and the magnetization/double-occupancy
  `*_adaptive_k_v3_design_transcript.json` files: non-authoritative extended-`K`
  diagnostics that leave all v2 evidence immutable.  The wrapper fresh-executes its
  exact bounded self bytes and compiles the pinned v2 implementation and dependencies
  from the same verified payloads.  Its 21/25-candidate ladders end at `K=393,216`;
  magnetization commits 32 checkpoints before checkpoint 33 requires `K=405,291`,
  while double occupancy commits 23 before checkpoint 24 requires `K=397,750`.
  Canonical transcript SHA-256 values are
  `8ac6f010a136ace8f1d5be73e0d076c7090e4ee7d70adef86ae72c0782a2703e` and
  `263636de9e788bde4ad0b85f872fcfa22fae9ac73a5029af4c81383360584d90`.
  They commit no policy, boundary, transition, sidecar or positive witness.
- `test_hubbard_l8_adaptive_k_v3_design_probe.py`: exact base/source loader,
  same-byte self-exec bypass, isolated configuration, candidate/kernel containment,
  canonical transcript, every-prefix/candidate/first-feasible recurrence, frozen
  record/failure/history/resource hashes and exact v2-prefix handoff regressions.
- `hubbard_l8_adaptive_k_v4_design_probe.py` and the magnetization/double-occupancy
  `*_adaptive_k_v4_design_transcript.json` files: diagnostic-only higher-`K`
  continuations with 25/29 candidates through `K=458,752`.  Their wrapper binds the
  exact v4/v3/v2 implementation chain, restricts configuration overrides to the
  candidate/output names and two K ceilings, preserves all other resource caps, and
  atomically publishes at most 1 MiB.  Magnetization commits 35 checkpoints before
  checkpoint 36 requires `K=464,310`; double occupancy commits 27 before checkpoint
  28 requires `K=461,297`.  Canonical transcript SHA-256 values are
  `962a3b14c5836e12d50debc82b0f4681fe167e075d4b7579766354ff2c3e79db` and
  `e6f5e2299f3f892d2f24230df32a93a8acb10d49433079db500ee0102d085350`.
  Neither transcript commits a policy, child boundary, transition or witness.
- `test_hubbard_l8_adaptive_k_v4_design_probe.py`: same-byte parent/private-call,
  three-layer provenance, override-tamper, output-collision/atomic-cap, exact
  candidate/kernel containment, canonical transcript, every-checkpoint budget and
  first-feasible recurrence, frozen result/resource hashes, and full v3-prefix plus
  old-failure handoff regressions.
- `hubbard_l8_adaptive_k_v5_design_probe.py` and the magnetization/double-occupancy
  `*_adaptive_k_v5_design_transcript.json` files: diagnostic-only kernel-edge ladder
  probes with 28/32 candidates through `K=507,904`.  They distinguish the direct
  v5-over-canonical-v4 delta from the parent effective override, bind ordered
  v5/v4/v3/v2 source layers, preserve every non-K v4 cap and atomically publish at
  most 1 MiB.  Magnetization commits 38 checkpoints before checkpoint 39 requires
  `K=521,800`; double occupancy commits 31 before checkpoint 32 requires
  `K=518,097`.  Canonical transcript SHA-256 values are
  `384f9d0e0d3551f08765bec337286f2ab6745a63479fc07bc39bb99d685f645e` and
  `50d0f956f1e0e5fa379334be98d857882cca28e1a48644b3faf1b59711bfddd0`.
  Neither transcript commits a policy, child boundary, transition or witness.
- `test_hubbard_l8_adaptive_k_v5_design_probe.py`: exact 28/32-candidate and kernel
  edge containment, same-byte/private-call/resource propagation, four-layer source
  and effective/direct-override tamper, atomic output, canonical transcript,
  every-checkpoint recurrence, frozen result/resource hashes, and full v4-prefix
  plus old-failure handoff regressions.
- `hubbard_l8_adaptive_k_v6_design_probe.py` and
  `hubbard_l8_magnetization_adaptive_k_v6_design_transcript.json`: diagnostic-only
  kernel-limit continuation through `K=524,288`.  The probe uses 29 M candidates and
  a 32-slot D ladder that replaces unused v5-only `491,520`, binds ordered
  v6/v5/v4/v3/v2 source layers, separates the direct v6/configured-v5/configured-v4
  overrides, propagates resource failures and atomically publishes at most 1 MiB.
  M commits checkpoint 39 and fails at checkpoint 40 with minimum K `525,859`;
  its canonical transcript SHA-256 is
  `7b0f4509a067a41da849c86c0e3e8e0ec585217d6c44a7d48aeeedc2e9aa6102`.
  D commits checkpoint 32 in replay but checkpoint 33 exceeds the unchanged
  786,432 live/digest cap, so no partial D v6 transcript is published.  A separate
  noncanonical kernel-cap measurement gives peak 825,000, 82,050,350 visits and
  minimum K `553,717`, 29,429 above the retained maximum, at that checkpoint.
  Neither route commits policy or positive authority.
- `test_hubbard_l8_adaptive_k_v6_design_probe.py`: exact kernel-limit ladders/caps,
  same-byte/private-call and exception-identity checks, five-layer source and
  three-level override tamper checks, canonical M file/ledger/failure/history hashes,
  full v5-prefix handoff, atomic failure preservation, explicit absence of a partial
  D transcript, and opt-in exact D resource-failure/resource-measurement replays.
- `hubbard_l8_adaptive_k_four_gate_granularity_screen.py` and the mode-specific
  `*_adaptive_k_four_gate_granularity_transcript.json` files: independent diagnostic
  checkpoint-cadence screens.  They retain the pinned nine-stage/1,152-gate physical
  sequence and take exact v6 candidates/caps as configuration only, but own their
  four-gate/288-checkpoint control flow.  Exact v2 is a verified helper provider;
  neither v2 nor v6 is an execution parent.  M commits 77 checkpoints before q78
  needs `K=529,897`; D commits 64 before q65 needs `K=532,869`.  Their canonical
  transcript SHA-256 values are
  `18629c9a0841e1e3308eda0bc7f3cbc568c8ed2925a6b95d1c3e7b7665b142a0` and
  `2b83f7f349cb0b7fedab4ad8b8058606c239b01d45579722afc490c35f684060`.
  A noncanonical D ladder sensitivity restores `491,520`, removes unused `65,536`
  and still fails at q65 with minimum K `536,203`; it is intentionally not published
  as a transcript because that ladder is absent from the pinned v6 source.
  Outputs are canonical, atomic and bounded by 4 MiB.  They are not v7, policies,
  boundaries, transitions or certificate witnesses.
- `test_hubbard_l8_adaptive_k_four_gate_granularity_screen.py`: exact source and
  configuration pins, fresh-self isolation, rebuilt boundary/source custody,
  fixed geometry and aligned-budget identities, four-gate commit-to-next-input
  continuity, gate digests, full candidate/ledger/resource recurrence,
  v6-parent negation, D `491,520` counterfactuals, resource-exception identity,
  4 MiB atomic failure preservation, frozen transcript summaries and opt-in full
  canonical replays.  A separate opt-in noncanonical replay freezes the 32-slot D
  sensitivity at q65/minimum K `536,203`, peak 645,044 and 75,255,249 visits without
  writing a provenance-ambiguous output file.
- `hubbard_l8_adaptive_k_arithmetic_k540672.py`: source-pinned capability wrapper
  over the exact arithmetic-v2 bytes.  It changes only
  `RESOURCE_LIMITS.max_retained_K` from 524,288 to 540,672, keeps every exported
  arithmetic function and counter method bound to the isolated v2 provider, and
  publishes a diagnostic manifest with SHA-256
  `d51151fc1d6c73c33f1b50da0a09de4d3346212599716feaba578839dde37526`.
  The wrapper source SHA-256 is
  `327837e4646cb79cb237611ab49e645b51a47a36a97006e94838d1f5fa05af60`;
  it has no certificate authority.
- `hubbard_l8_adaptive_k_four_gate_k540672_screen.py` and the mode-specific
  `*_adaptive_k_four_gate_k540672_transcript.json` files: controlled capability
  screen using the pinned four-gate private control-flow parent, exact v6 baseline
  configuration, exact v2 arithmetic and the separate K=540,672 wrapper.  Policy
  configuration changes only the two K ceilings; all non-K caps remain fixed.  M
  uses 30 candidates and commits q1--80, selecting 540,672 at q78--80; peak/visits
  are 643,624/87,032,691.  D uses 32 candidates after replacing baseline 65,536,
  commits q1--65 and fails at q66 with pre-count 679,285, minimum K 558,598 and
  excess 17,926; visits are 77,762,021.  Canonical transcript SHA-256 values are
  `d4a0f952a3d4a93bd78d370fae50c5c043e33caa4d1452e841987976e43354a5` and
  `5ced57f7f6fc8aef50a6536920243d00af083b0a113b09d19f239bc1266fd8a5`.
  The screen source SHA-256 is
  `81ac62fa093c48d57667cb56958ad58a8ed26e8ff81abd7c35365e01fb981d6f`.
  Both outputs are canonical, atomic, bounded by 4 MiB and diagnostic-only.
- `test_hubbard_l8_adaptive_k_four_gate_k540672_screen.py`: exact source/capability
  pins, provider isolation, M30/D32 ladder construction, recomputed D-65,536 removal
  evidence, K-only cap deltas, fixed geometry/aligned budgets, fresh/private-path
  exception identity, provenance hashes, 4 MiB atomic failure preservation, and
  complete canonical ledger regressions over 146 records and 4,512 candidate rows.
  It verifies the old committed prefixes, q78/q65 handoffs, M q80 horizon and D q66
  failure; exact full propagation replays remain opt-in.
- `hubbard_l8_magnetization_adaptive_k_four_gate_k540672_q82_screen.py` and its
  `*_q82_transcript.json`: same-cap M horizon-only continuation.  The outer source
  SHA-256 is
  `c06d2be38215266f1d19dc64116041b456e2a597e6aa24aa63b9ffbaeda86b03`;
  it calls the exact K=540,672 private parent, changes only M horizon 80 -> 82 and
  replays from q1.  The old q80 artifact is post-replay prefix evidence, not a
  state-resume input.  q1--80 remains exact and q81 fails at minimum K 545,129
  with pre-count 597,254, peak/visits 643,624/89,253,151.  Canonical transcript
  SHA-256 is
  `0486a8b19077de9e90f134c7b3c0d43fdf3504a4876d6e0b2c3d01b37b89cb52`.
- `test_hubbard_l8_magnetization_adaptive_k_four_gate_k540672_q82_screen.py`:
  exact parent/artifact pins, horizon-adapter restoration, real private-path and
  exception-identity checks, provenance/atomic/scope regressions, and complete
  81-record/2,430-row canonical ledger validation; full replay is opt-in.
- `hubbard_l8_adaptive_k_arithmetic_k573440_c33.py`: fail-closed direct-v2
  capability wrapper with source SHA-256
  `811a16b6a47bca60281fb4afe8280783146e6f4ee28955dde7907b47fc65bb49`
  and manifest SHA-256
  `c2787b105553b80ee9a1e5e1d925d6cac2ab819b0cdfab305484bf89bbba32c5`.
  It changes only retained K 524,288 -> 573,440 and candidate count 32 -> 33;
  K=540,672 is a non-executed route-predecessor reference.
- `test_hubbard_l8_adaptive_k_arithmetic_k573440_c33.py`: same-byte/fail-closed
  loading, exact direct/route deltas, provider/global binding, 33/34-candidate and
  573,440/573,441 boundaries, manifest/layer and predecessor-reference hashes.
- `hubbard_l8_double_occupancy_adaptive_k_four_gate_k573440_c33_q68_screen.py`
  and its `*_q68_transcript.json`: D33 append-only route through the aligned q68
  boundary.  Screen source SHA-256 is
  `3c4dfb8aca29b6a5903d2aedd52f85409941d1c16050760f6b24453d9585d67b`.
  q1--65 common state/history and all first 32 rows are exact; q66 retains the old
  propagation/rows and selects appended index 32.  K=573,440 is selected at
  q66--68, whose pre-counts are 679,285/688,548/630,616.  The route reaches 68/68
  with peak/visits 688,548/82,618,707; canonical transcript SHA-256 is
  `b1f072c84cc676151fe3cddbb8a0db445df946f299dbb81f41e34f765d30dfc8`.
- `test_hubbard_l8_double_occupancy_adaptive_k_four_gate_k573440_c33_q68_screen.py`:
  source/configuration/capability pins, unique D-horizon override, real private
  sentinel and exception identity, reference-only predecessor, synthetic tamper
  rejection, 4 MiB atomic output and complete 68-record/2,244-row ledger with all
  canonical hashes; full replay is opt-in.
- `hubbard_l8_adaptive_k_arithmetic_k557056.py`: fail-closed direct-v2 capability
  wrapper with source SHA-256
  `4c54b9a2451ad9ae76e4b4036705558cdc527f22b015fd67c035118ad2c8506f`
  and manifest SHA-256
  `cc60b39010c55fa3a95f7160e5ccb0a4985ab6926aa8076841d75e660a954868`.
  It changes only retained K 524,288 -> 557,056, keeps candidate-count capacity
  at 32, and treats K=540,672 only as an unexecuted route-predecessor reference.
- `test_hubbard_l8_adaptive_k_arithmetic_k557056.py`: same-byte/fail-closed
  loading, exact direct and route deltas, provider/global binding, 557,056/557,057
  K boundaries, candidate-count invariance, manifest/layer hashes and strict
  rejection of missing or malformed public pins.
- `hubbard_l8_magnetization_adaptive_k_four_gate_k557056_c31_q82_screen.py`
  and its `*_transcript.json`: append-only M31 route through q82.  Screen source
  SHA-256 is
  `ba1c221b57fa59655612ad7209b38c83337f6f21b794132f7a9e1600b8d60fed`.
  q1--80 common state/history and all first 30 rows are exact; q81 retains the old
  propagation/rows before appended index 30 becomes first feasible.  K=557,056
  is selected at q81--82, whose pre-counts are 597,254/641,180 and dropped counts
  are 40,198/84,124.  The route reaches 82/82 with peak/visits
  643,624/91,592,879; canonical transcript SHA-256 is
  `1d6cbcddac8a8c596746f24b8c8498f24874e86db5235532d7d269220043cdd4`.
- `test_hubbard_l8_magnetization_adaptive_k_four_gate_k557056_c31_q82_screen.py`:
  exact source/configuration/capability pins, M31 append-only construction,
  private-path and exception identity, reference-only predecessor handoff,
  atomic output, provenance and complete 82-record/2,542-row canonical ledger;
  full propagation replay remains opt-in.
- `hubbard_l8_double_occupancy_adaptive_k_four_gate_k573440_c33_q70_screen.py`
  and its `*_transcript.json`: D33 same-cap horizon-only extension.  The outer
  source SHA-256 is
  `3e0ae3c21f4d8b2e56a95573ecb238dfe0542ed891ac6bbadceb72b2d03b3045`;
  it calls the exact q68 private parent, changes only D horizon 68 -> 70 and
  replays from q1.  The q68 artifact is post-replay prefix evidence rather than a
  state-resume input.  q1--68 is exact and q69 fails at pre-count 644,504,
  minimum K 579,098 and excess 5,658; peak/visits are 688,548/84,984,299.
  Canonical transcript SHA-256 is
  `38fa337482dbd323d68f36b6debfdc6fff94d4cf8c42e68d6477b45dc02368d6`.
- `test_hubbard_l8_double_occupancy_adaptive_k_four_gate_k573440_c33_q70_screen.py`:
  exact parent/artifact pins, isolated horizon override and restoration, real
  private-path/exception identity, reference-only q68 predecessor, atomic output,
  provenance and complete 69-record/2,277-row canonical ledger; full propagation
  replay remains opt-in.
- `hubbard_l8_magnetization_adaptive_k_four_gate_k557056_c31_q84_screen.py`
  and its `*_transcript.json`: M31 same-cap horizon-only extension.  The outer
  source SHA-256 is
  `d778440f6a86adf7d4498d2c3496c0f650c7782379c9f5b25c1e979ad01a136f`;
  it calls the exact q82 private parent, changes only M horizon 82 -> 84 and
  replays from q1.  The q82 artifact is post-replay prefix evidence rather than a
  state-resume input.  q1--82 is exact and q83 fails at pre-count 652,016,
  minimum K 565,994 and excess 8,938; q84 is not attempted.  Peak/visits are
  652,016/93,965,211.  Canonical transcript SHA-256 is
  `2f866d658570c9cf667088662a98288c14b41144c3ffacdefd862aaf8f185138`.
- `test_hubbard_l8_magnetization_adaptive_k_four_gate_k557056_c31_q84_screen.py`:
  exact parent/artifact pins, validation-only horizon adapter restoration,
  private-path/exception identity, non-state q82 reference, atomic output,
  provenance and complete 83-record/2,573-row canonical ledger with an exact q83
  failure anchor; full propagation replay remains opt-in.
- `hubbard_l8_adaptive_k_arithmetic_k589824_c34.py`: fail-closed direct-v2
  capability wrapper with source SHA-256
  `7758cc1bf0cd71545a7135c92848059dc69e5d934c79f1d8c60ea61019459254`
  and manifest SHA-256
  `36694fa3e72ad78fde91826c6a1ae81ae5a7f07e51db2d008769d97eabce5b1a`.
  It changes only retained K 524,288 -> 589,824 and candidate capacity 32 -> 34;
  the K=573,440/C33 wrapper is a non-executed route-predecessor reference.
- `test_hubbard_l8_adaptive_k_arithmetic_k589824_c34.py`: same-byte/fail-closed
  direct-v2 loading, exact direct/route deltas, provider/global binding,
  C33/C34/C35 and 589,824/589,825 boundaries, manifest/layer hashes and strict
  public pins.
- `hubbard_l8_double_occupancy_adaptive_k_four_gate_k589824_c34_q70_screen.py`
  and its `*_transcript.json`: append-only D34 route through q70.  Screen source
  SHA-256 is
  `af4257d505bcebcafa80fa184bd83065fae1b5151fd9bdc28a5f5b9ccf9ecb32`.
  q1--68 common state/history and first 33 rows are exact; q69 retains the old
  propagation/rows before appended index 33 becomes first feasible and selects
  K=589,824.  q70 fails at pre-count 718,805, minimum K 597,272 and excess 7,448;
  peak/visits are 718,805/87,505,002.  Canonical transcript SHA-256 is
  `65d6f5ba3e45b5b57b12d1b9e1daadb17064f8aece7dc914697191f822b3a8d7`.
- `test_hubbard_l8_double_occupancy_adaptive_k_four_gate_k589824_c34_q70_screen.py`:
  exact direct-parent/route/capability pins, D34 append construction, q69
  counterfactual handoff, fail-closed success/failure terminal ledgers and
  execution-component schema, atomic/provenance/authority checks, and complete
  70-record/2,380-row canonical ledger with exact q69/q70 anchors; full replay is
  opt-in.
- `hubbard_l8_adaptive_k_arithmetic_k573440.py`: fail-closed direct-v2 M
  capability wrapper with source SHA-256
  `c644dfeaf2a0b27be40403715aec8711818ae11ff575b230339af745f0a56ff1`
  and manifest SHA-256
  `fb6d6c241ab7ee2f535aa2f1cdff38a5e8f47bab1035ba29249332ca2d4f3f39`.
  It changes only retained K 524,288 -> 573,440 and keeps candidate capacity 32;
  K=557,056 and D K=573,440/C33 artifacts are non-executed route references.
- `test_hubbard_l8_adaptive_k_arithmetic_k573440.py`: same-byte/fail-closed
  direct-v2 loading, exact direct/route deltas, provider/global binding,
  573,440/573,441 and C32/C33 boundaries, manifest/layer hashes and strict pins.
- `hubbard_l8_magnetization_adaptive_k_four_gate_k573440_c32_q84_screen.py`
  and its `*_transcript.json`: append-only M32 route through q84.  Screen source
  SHA-256 is
  `1246023edea93e89db2ec0071c51c1cb15f60b8a928b934aad08cebb593240b2`.
  q1--82 common state/history and first 31 rows are exact; q83 retains the old
  propagation/rows before appended index 31 becomes first feasible and selects
  K=573,440.  q84 fails at pre-count 694,130, minimum K 586,381 and excess
  12,941; peak/visits are 694,130/96,423,989.  Canonical transcript SHA-256 is
  `f379f6a72caba82c0f1aca599ef9872666cfed8b4ea72003194438ed01806f48`.
- `test_hubbard_l8_magnetization_adaptive_k_four_gate_k573440_c32_q84_screen.py`:
  exact direct-parent/route/capability pins, M32 append construction, q83
  failure-to-success handoff, closed success/failure schemas, atomic provenance,
  authority and complete 84-record/2,688-row canonical ledger with exact q83/q84
  anchors; full replay is opt-in.
- `hubbard_l8_adaptive_k_arithmetic_k606208_c35.py`: fail-closed direct-v2 D
  capability wrapper with source SHA-256
  `34757028d695e2542cade50f4be5c214006dee6945e01afc2483e7338d6cb7dd`
  and manifest SHA-256
  `c55df50288334226a4d8ba37a257ca645d601967f8778f426a313773c1c73629`.
  It changes only retained K 524,288 -> 606,208 and candidate capacity 32 -> 35;
  K=589,824/C34 is a non-executed route reference.
- `test_hubbard_l8_adaptive_k_arithmetic_k606208_c35.py`: same-byte/fail-closed
  direct-v2 loading, exact direct/route deltas, provider/global binding,
  606,208/606,209 and C34/C35/C36 boundaries, manifest/layer hashes and pins.
- `hubbard_l8_double_occupancy_adaptive_k_four_gate_k606208_c35_q70_screen.py`
  and its `*_transcript.json`: append-only D35 route through q70.  Screen source
  SHA-256 is
  `dffd720464566ef443909b5e7b01518ac82bf5defd68e72ce9de079422985068`.
  q1--69 common state/history and first 34 rows are exact; q70 retains the old
  propagation/rows before appended index 34 becomes first feasible and selects
  K=606,208 with 53,451,620,700 ticks of margin, reaching 70/70 committed.
  Peak/visits are 718,805/87,505,002.  Canonical transcript SHA-256 is
  `55e9d305c90b62dea918071cd6ae383668c2ffb2f7dc108f7d4abcbcb772aa36`.
- `test_hubbard_l8_double_occupancy_adaptive_k_four_gate_k606208_c35_q70_screen.py`:
  exact direct-parent/route/capability pins, D35 append construction, q70
  failure-to-success handoff, closed raw/relabeled/terminal/candidate schemas,
  atomic provenance, authority and complete 70-record/2,450-row canonical ledger
  with an exact q70 anchor; full replay is opt-in.
- `hubbard_l8_adaptive_k_arithmetic_k589824.py`: fail-closed direct-v2 M
  capability wrapper with source SHA-256
  `9eded142673fcb548d585d0071f5c550970c48c24d50c5ef1fc43b6257b1775d`
  and manifest SHA-256
  `6906e56af531063800742e95304682f9bcd123d0086806d59691e0b099772b1a`.
  It changes only retained K 524,288 -> 589,824 and keeps candidate capacity 32;
  M K=573,440 and D K=589,824/C34 are non-executed route references.
- `test_hubbard_l8_adaptive_k_arithmetic_k589824.py`: same-byte/fail-closed
  direct-v2 loading, exact direct/route/cross-route deltas, provider bindings,
  589,824/589,825 and C32/C33 boundaries, manifest/layer hashes and strict pins.
- `hubbard_l8_magnetization_adaptive_k_four_gate_k589824_c32_q84_screen.py`
  and its `*_transcript.json`: trajectory-preserving C32 replacement through q84.
  Screen source SHA-256 is
  `594f03e397c5887df335d05971297a1d00e06b1ea19140003e7842a5ca897fb0`.
  It removes never-feasible K=65,536 and appends K=589,824.  q1--83 preserve
  selected/state trajectory while old rows 1--31 map normalized-exact to new
  rows 0--30; raw candidate-row prefix identity is explicitly false.  q84 selects
  new index 31 with 46,578,773,421 ticks of margin and reaches 84/84.  Peak/visits
  are 694,130/96,423,989.  Canonical transcript SHA-256 is
  `cf93ebcccde4ff10adee2e600a13ef1c0f979e89fe151fca16d4eae79da2420f`.
- `test_hubbard_l8_magnetization_adaptive_k_four_gate_k589824_c32_q84_screen.py`:
  exact source/capability/route pins, C32 index-normalized replacement handoff,
  closed custody/components and 94/37/31/7 schemas, atomic authority and complete
  84-record/2,688-row canonical ledger with exact q83/q84 anchors; full replay is
  opt-in.
- `hubbard_l8_double_occupancy_adaptive_k_four_gate_k606208_c35_q72_screen.py`
  and its `*_transcript.json`: same-cap D35 horizon extension.  Screen source
  SHA-256 is
  `54601418ab5aa2b6c887d928ad6c87fa0cff558c0558d106961201d291cc33fe`.
  The q70 route is non-executed post-replay evidence; q1--70 records/history and
  all 35 rows are exact.  q71 fails at pre-count 761,190, minimum K 614,584 and
  excess 8,376, so q72 is absent.  Peak/visits are 761,190/90,141,781.
  Canonical transcript SHA-256 is
  `f21288cf0c37dc86fedc9ac195f4efe390dcc913640caa7ca79f02e6297d20f8`.
- `test_hubbard_l8_double_occupancy_adaptive_k_four_gate_k606208_c35_q72_screen.py`:
  exact q70 route and direct-parent pins, three-branch terminal state machine,
  closed 65/94/38/32/7/9 schemas, custody/components, digest and cumulative
  resource adversarial checks, atomic authority and complete 71-record/2,485-row
  canonical ledger with an exact q71 failure anchor; full replay is opt-in.
- `hubbard_l8_adaptive_k_arithmetic_k622592_c36.py`: fail-closed direct-v2 D
  capability wrapper with source SHA-256
  `7ac6c87f3d789ad62540cbc96e81f0a092594b0524eec3f9b05e7ffec2124838`
  and manifest SHA-256
  `fc82c41b1a1dd82fbb34e205ea347b0ba41b08c5fd2ebed6a599593fe95c1b34`.
  It changes only retained K 606,208 -> 622,592 and candidate capacity 35 -> 36;
  the D35 route and M K=589,824/C32 are non-executed references.
- `test_hubbard_l8_adaptive_k_arithmetic_k622592_c36.py`: same-byte/fail-closed
  direct-v2 loading, exact direct/route/cross-route deltas, provider bindings,
  622,592/622,593 and C36/C37 boundaries, manifest/layer hashes and strict pins.
- `hubbard_l8_magnetization_adaptive_k_four_gate_k589824_c32_q86_screen.py`
  and its `*_transcript.json`: same-cap M32 horizon extension.  Screen source
  SHA-256 is
  `002cc87d5d1a8f1908a837e8612e3a9d4a4c5ebbf68e41f841ba4a5a639ff878`.
  The q84 artifact is post-replay evidence only; q1--84 records/history and all
  32 rows remain exact.  q85 fails at pre-count 673,356, minimum effective
  K=592,290 and excess 2,466, so q86 is absent.  Peak/visits are
  694,130/98,908,531.  Canonical transcript SHA-256 is
  `c24a665d543323a0e7f28ac4023fe5ae3d54b39c4e2991cba3e70e9371d0053d`.
- `test_hubbard_l8_magnetization_adaptive_k_four_gate_k589824_c32_q86_screen.py`:
  exact q84 parent/route/capability pins, three-branch terminal state machine,
  closed custody/components and canonical schemas, adversarial type and digest
  checks, atomic authority and complete 85-record/2,720-row ledger with an exact
  q85 failure anchor; full replay is opt-in.
- `hubbard_l8_double_occupancy_adaptive_k_four_gate_k622592_c36_q72_screen.py`
  and its `*_transcript.json`: D36 append-and-horizon replay.  Screen source
  SHA-256 is
  `2e22e1918fbc10cd696d700dbf05e8d99d0c333a1428e9473de6ebbc563488e1`.
  q1--70 common state/history and old 35 rows remain exact.  q71 selects appended
  index 35/K=622,592 with 40,105,997,158 ticks of margin.  q72 propagation reaches
  799,279 terms, 12,847 above the unchanged live-term policy cap, before digest,
  ranking or candidate evaluation; a separate closed 40-key resource-abort ledger
  records the stop and q72 has no checkpoint record.  Peak/visits including the
  attempt are 799,279/92,869,433.  Canonical transcript SHA-256 is
  `e7ae9abb11a4cc116778c8c373ff1c93131db9c9d36ba886ff6ef2d7b53bd09f`.
- `test_hubbard_l8_double_occupancy_adaptive_k_four_gate_k622592_c36_q72_screen.py`:
  exact D35 parent/direct-v2/route pins, four-branch terminal state machine,
  traceback custody and resource-abort structure checks, closed schemas, atomic
  authority and complete 71-record/2,556-row canonical ledger with exact q71 and
  q72-abort anchors; full replay is opt-in.
- `hubbard_l8_adaptive_k_arithmetic_k606208_c33.py`: fail-closed direct-v2 M
  capability wrapper with source SHA-256
  `447cb116c2ca977cb2711b08e64e5795728907b8c4033bd1eb38211bf63cf558`
  and manifest SHA-256
  `116c8d37e11e2762a3a47d2d5844d059de0277dbd41724b5c65018b0b234b395`.
  Relative to arithmetic-v2 it changes retained K 524,288 -> 606,208 and candidate
  capacity 32 -> 33.  Relative to the non-executed M32 route predecessor, the
  incremental retained-K change is 589,824 -> 606,208; the D same-K/C35 route is
  also a non-executed reference.
- `test_hubbard_l8_adaptive_k_arithmetic_k606208_c33.py`: same-byte/fail-closed
  direct-v2 loading, exact direct/route/cross-route deltas, provider bindings,
  606,208/606,209 and C33/C34 boundaries, manifest/layer hashes and strict pins.
- `hubbard_l8_magnetization_adaptive_k_four_gate_k606208_c33_q86_screen.py`
  and its `*_transcript.json`: append-only M33 replay through q86.  Screen source
  SHA-256 is
  `86e5148a51cb70d2aab21d770ad2b21928caf6e2818786542b287be7c8d02d27`.
  The M32 transcript is post-replay evidence only.  q1--84 common record fields,
  state/history and the first 32 rows remain exact; each full M33 record also gains
  the appended index-32 row.  q85 selects index 32/K=606,208 with
  122,423,995,500 ticks of margin.  q86 selects existing index 31/K=589,824 with
  13,797,053,946 ticks of margin, reaching 86/86 committed.  Peak/visits are
  694,130/101,424,121.  Canonical transcript SHA-256 is
  `fc649a90aa42429d7d746f40bdc7dfe109f1dc6921b46beb8c3396cc3012e875`.
- `test_hubbard_l8_magnetization_adaptive_k_four_gate_k606208_c33_q86_screen.py`:
  exact raw-parent/wrapper/route pins, four synthetic terminal branches and three
  structured q86 resource-abort kinds, closed 67/96-key schemas, components/custody
  and reverse-relabel checks, atomic authority and complete 86-record/2,838-row
  canonical ledger with exact q85/q86 anchors; full replay is opt-in.
- `hubbard_l8_double_occupancy_adaptive_k_four_gate_k622592_c36_l1048576_d1048576_q72_screen.py`
  and its `*_transcript.json`: same-K/C36 policy-envelope discriminator.  Screen
  source SHA-256 is
  `57a68b3086cd2ed2d484d0f835a190dc768b12bbb2b8d6a3c99c86f6ea6bda8d`.
  Relative to the frozen D route it changes only live/digest caps 786,432 ->
  1,048,576; the old resource-abort transcript is post-replay evidence only.
  q1--71 records/history remain exact.  q72 completes digest/ranking but all 36
  rows fail: minimum effective K=642,206, excess 19,614.  There is no q72 resource
  abort or commit; attempted/completed are 72/71 and peak/visits are
  799,279/92,869,433.  Canonical transcript SHA-256 is
  `4bdc16622a52a57ab6d43da04d77c6c67defdb36c2630a9d51178b65ac1e6ddd`.
- `test_hubbard_l8_double_occupancy_adaptive_k_four_gate_k622592_c36_l1048576_d1048576_q72_screen.py`:
  exact provider/policy/predecessor pins, closed success/failure schemas, complete
  72-record/2,592-row canonical ledger, q72 arithmetic/resource/nested-digest
  anchors, 12 execution components, 11 custody entries and exact raw67-to-final96
  reverse/relabel reconstruction; full replay is opt-in.
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
