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
- `hubbard_l8_magnetization_adaptive_k_four_gate_k606208_c33_q88_screen.py`
  and its `*_transcript.json`: same-cap M33 horizon extension through q88.  Screen
  source SHA-256 is
  `d158d00275e78b33d0246e86bf9bc7bcaf4eb4f7fa4cb9afce2298e97cb5308d`.
  The q86 same-byte private parent performs the fresh replay and its canonical is
  loaded afterward; q1--86 remain exact.  q87 selects index 32/K=606,208 at
  pre-count 645,618, dropping 39,410 terms and 28,631,843,222 ticks with
  89,696,616,395 ticks of margin.  q88 fails at pre-count 689,242 with minimum
  effective K=607,993, excess 1,785; the maximum row's 218,739,972,624-tick drop
  exceeds slack by 24,511,950,557 ticks.  The no-abort terminal branch is
  `Q87_SUCCESS_Q88_FAILURE`; attempted/completed are 88/87 and peak/visits are
  694,130/106,375,865.  The 804,599-byte canonical has 88 records, 87 history
  entries and 2,904 rows; its SHA-256 is
  `f7ca4a1defd38472366c1cfcd112736f34b73e612002cce98a52f79daa5cc1b0`.
- `test_hubbard_l8_magnetization_adaptive_k_four_gate_k606208_c33_q88_screen.py`:
  exact q86 parent/canonical/capability pins, replay-before-reference ordering,
  all five terminal branches, all three q87 and q88 structured resource-abort
  kinds, closed raw67/final96, success37/failure31, row7 and abort50 schemas,
  11 components/10 custody entries and the exact 88-record/2,904-row canonical
  ledger with q87 success and q88 failure anchors; full replay is opt-in.
- `hubbard_l8_adaptive_k_arithmetic_k655360_c37.py`: fail-closed direct-v2 D
  capability wrapper with source SHA-256
  `2acf8f8329376ab06ad4c079af633d23bcc6a32fa20af654e5c3dbbb32093d54`
  and manifest SHA-256
  `62c889baf0676150344f06ccf5d48132e121ade399c77dd1b85727f5002dd6e5`.
  Relative to arithmetic-v2 it changes retained K 524,288 -> 655,360 and candidate
  capacity 32 -> 37; relative to the D36 route it changes 622,592 -> 655,360 and
  36 -> 37.  Only K=655,360 is appended, while live/digest limits remain
  1,048,576; the D36 route is a non-executed reference.
- `test_hubbard_l8_adaptive_k_arithmetic_k655360_c37.py`: same-byte/fail-closed
  direct-v2 loading, exact direct/route deltas, provider bindings, 655,360/655,361
  and C37/C38 boundaries, manifest/layer hashes and strict predecessor pins.
- `hubbard_l8_double_occupancy_adaptive_k_four_gate_k655360_c37_l1048576_d1048576_q72_screen.py`
  and its `*_transcript.json`: append-only D37 replay through q72.  Screen source
  SHA-256 is
  `1d3366d7c3fdc2a1e4a5c58198cc9be7e561af1f2ff8582e324ed5902c760183`.
  The current D36 policy artifacts are loaded only after a fresh q1 replay.
  q72 reaches 799,279 terms and selects appended index 36/K=655,360, dropping
  143,919 terms and 78,846,106,758 ticks with 43,761,880,334 ticks of margin;
  E becomes 2,289,046,235,933,480 ticks.  The route commits 72/72 checkpoints and
  2,664 rows with peak/visits 799,279/92,869,433.  The 751,550-byte canonical
  SHA-256 is
  `0517461f8695b21b578190cdd9a5da884f301d43c2f80be8093fbfc20cc006ae`.
  K=638,976 is excluded only for the fixed q72 state/prefix (threshold 642,206,
  shortfall 3,230); it has no executed row or asserted exact drop.
- `test_hubbard_l8_double_occupancy_adaptive_k_four_gate_k655360_c37_l1048576_d1048576_q72_screen.py`:
  exact wrapper/policy/predecessor pins, post-replay-only comparison custody,
  q1--71 and q72-old-row identity, first-feasible index-36 selection, fail-closed
  unexpected-resource handling without an abort artifact, closed raw67/final96,
  success38/failure32 and row7 schemas, 11 components/10 custody entries and the
  exact 72-record/2,664-row canonical ledger.  No full replay runs in the default
  suite.
- `hubbard_l8_adaptive_k_arithmetic_k622592_c34.py`: 21,957-byte fail-closed
  direct-v2 M capability wrapper with source SHA-256
  `f4e676da40535903301181cf482119e051066b90921793e34152403b3b74b976`
  and manifest SHA-256
  `3c2b66149d524cc63a4d04838b3eec47fb69677466fe1f208e226df92bf0dac3`.
  Relative to M33 it appends only K=622,592, changes retained K 606,208 ->
  622,592 and candidate capacity 33 -> 34, and leaves all other capability limits
  fixed; M33 and same-K D36 are non-executed route/cross-route references.
- `test_hubbard_l8_adaptive_k_arithmetic_k622592_c34.py`: 22,229-byte exact
  wrapper/base/route/cross-route pin, limit-delta, C34/C35 boundary, layer and
  manifest regression suite.  Its source SHA-256 is
  `7fd4700bc3be8eec606e32fa72844a7c299283abd745d7160d0c36259e4a29e3`.
- `hubbard_l8_magnetization_adaptive_k_four_gate_k622592_c34_q88_screen.py`
  and its `*_transcript.json`: fixed-q88 M34 fresh replay.  The 78,218-byte screen
  source SHA-256 is
  `6867dda2d6bd34ab2eed6b31d02a587e16762263a493e9890d0caa40f23a58a4`.
  The M33 screen/canonical are post-replay evidence only.  The route commits
  88/88 checkpoints, 88 history entries and 2,992 rows.  At q88, pre-count
  689,242 selects index 33/K=622,592, dropping 66,650 terms and 33,833,242,742
  ticks; E becomes 1,700,535,038,508,063 and the ranking boundary is
  3,434,232 > 3,434,132.  Branch `Q88_INDEX33_FIRST_FEASIBLE_SUCCESS` has no
  failure or resource abort.  Records/history SHA-256 values are
  `8832c0fd7c61146f2aa3c5e9a3a827972c459a126c2d371b5a5c41bac700c804`
  and `58cd214e13f4c122f710aad62ac0e52ead1aed0fa7d8a7e2498ea6013c7f4726`.
  The 821,781-byte canonical SHA-256 is
  `0074b1eea5fa574378d5a9fae9e748e7145efaa0c96b622ddf50587a72a2551a`.
- `test_hubbard_l8_magnetization_adaptive_k_four_gate_k622592_c34_q88_screen.py`:
  35,686-byte static, synthetic and opt-in exact-replay suite with source SHA-256
  `3617e92e356354bc2c75137bddbfbabbc9ecd15a83c3935a96bae40561d26f22`.
  It closes direct-parent execution, route/cross-route custody, all q88 terminal
  paths, resource pass-through, raw67/final96 schemas, 11 components/10 custody
  entries, and the exact 88-record/2,992-row canonical; default tests do not replay.
- `hubbard_l8_double_occupancy_adaptive_k_four_gate_k655360_c37_l1048576_d1048576_q74_screen.py`
  and its `*_transcript.json`: same-cap D37 horizon extension.  The 117,108-byte
  screen source SHA-256 is
  `5e2e077a9cab2a2b83f9830d755bafb7cc6dfa1d1c8a1ffade840d09e5016376`.
  It changes only horizon 72 -> 74, replays from q1, and loads the q72 canonical
  only afterward.  q73 pre-count 794,529 selects index 36/K=655,360, drops
  139,169 terms and 100,499,996,927 ticks, commits E=2,289,146,735,930,407 and
  closes 3,668,234 > 3,667,375.  q74 pre-count 726,450 selects the same index,
  drops 71,090 terms and 44,071,221,987 ticks, commits E=2,289,190,807,152,394
  and closes the exact tie 4,009,413 = 4,009,413.  Branch
  `Q73_AND_Q74_SUCCESS_HORIZON_REACHED` has no failure or resource abort.  The
  ledger has 74 records/history entries and 2,738 rows; records/history SHA-256
  values are
  `f765797dad4f6892524fc651a259786dff9c10187a6c634fc088fd3508c1e89f`
  and `d521cdf189b54254cf3ca3d0e9033b52c90ea6ec91dc571d95a605e520972ff8`.
  The 773,489-byte canonical SHA-256 is
  `4421f5973253968167b1c8bd77e024b18450325ea9581ed39dbe975ec8163ec9`.
- `test_hubbard_l8_double_occupancy_adaptive_k_four_gate_k655360_c37_l1048576_d1048576_q74_screen.py`:
  56,179-byte static, synthetic and opt-in exact-replay suite with source SHA-256
  `3a767b45c08e84f25a37e1f25a18226f409b7f59d6d369c76b22d09e188f0ea6`.
  It closes all five terminal branches and three abort kinds per checkpoint,
  post-replay-only predecessor custody, raw67/final96 schemas, 11 components/10
  custody entries, and the exact 74-record/2,738-row canonical; default tests do
  not replay.
- `hubbard_l8_magnetization_adaptive_k_four_gate_k622592_c34_q90_screen.py`
  and its `*_transcript.json`: same-cap M34 horizon extension through q90.  The
  89,527-byte screen source SHA-256 is
  `f880e851bb16df5e659d7c0e6aa237d1836b17b4ad010d5676557ade2ba9140a`.
  It exact-byte executes the q88 M34 private parent from q1 and admits the q88
  canonical only afterward as q1--88 prefix evidence.  q89 pre-count 718,896
  selects index 33/`K=622,592`, drops 96,304 terms and 174,253,874,408 ticks,
  commits E=1,700,709,292,382,471 and retained digest
  `b7d1e16a3f344eb1353593fd66c379d36272c49d1ebfe5c5c2b3e6958ed98c19`;
  its ranking boundary is the exact tie 13,718,154 = 13,718,154.  q90 pre-count
  741,376 has no feasible C34 row: minimum effective K is 635,284, exceeding
  622,592 by 12,692.  Its maximum row drops 369,541,613,084 ticks, exceeding
  prefix slack by 174,337,896,824 ticks.  The terminal branch is
  `Q89_SUCCESS_Q90_FAILURE`, not a resource abort.  The ledger has 90 records,
  89 history entries and 3,060 rows; records/history SHA-256 values are
  `8978329b712168dce39991af25f6903deaf69c45f236521bb0e08e74f3d8741f`
  and `c6755c7655d6b2ff37da7b1a8ac8c16cfc4295ef9ad0b687ddaa3dcd3c785d53`.
  The 842,060-byte canonical SHA-256 is
  `d30359d9dd38c8e3a1461a0c7048645e35f478fa66920711871b3dc1c44bbd49`.
- `test_hubbard_l8_magnetization_adaptive_k_four_gate_k622592_c34_q90_screen.py`:
  53,085-byte static, synthetic, adversarial and opt-in exact-replay suite with
  source SHA-256
  `9cd2dfadcd89bc5d35eed690aaa4cafc35f5e0f07eeb0325023981d931a1380e`.
  Its default gate closes all five branches, six structured-abort cases, unknown
  exception identity, exact q1--88 handoff, parent restoration, post-only order,
  11 components/10 custody entries and bounded atomic output without replay.
- `hubbard_l8_magnetization_q90_formal_s0_policy.json`,
  `hubbard_l8_magnetization_q90_formal_s0_precommit_contract.json`,
  `hubbard_l8_magnetization_q90_formal_s0_checker.py` and
  `test_hubbard_l8_magnetization_q90_formal_s0.py`: result-unpinned
  retrospective-replication precommit at
  `d3e58a62c1ca8c7c33512acfc3db141c329490fd`.  Policy/checker/precommit-contract
  SHA-256 values are
  `8084ab612c6d3cefb8f779d4dfe24450cb5c7d612d14b485feabb7044ae7cab5`,
  `7edfb6f4b811db6f97b8bd8dc9245793ee24c0613d908ded3dc7bb340c6f7bfe`
  and `557447ed7de793571a1f192023fa1a3e8c2c8e95e231ebd346d4127c09cf023c`.
  The checker stages an exact 13-file allowlist and excludes prior q90
  result/test bytes.
- `hubbard_l8_magnetization_q90_formal_s0_contract.json`,
  `hubbard_l8_magnetization_q90_formal_s0_certificate.json` and
  `test_hubbard_l8_magnetization_q90_formal_s0_result.py`: post-precommit
  result binding.  Fresh result SHA-256
  `d30359d9dd38c8e3a1461a0c7048645e35f478fa66920711871b3dc1c44bbd49`
  was compared with the old diagnostic canonical only after replay and is
  byte-identical; canonical witness SHA-256 is
  `26d4996bc8977f8e9cfa0a62817166cd5b122a1355bdb455e77b9cd87382deda`.
  It verifies `Q89_SUCCESS_Q90_FAILURE`, 90 records, 89 history entries,
  3,060 rows, all 34 q90 candidates infeasible and no resource abort.  The
  external receipt is 13:35.69 / 671,592 KiB; authority is fixed-policy
  M3-only, with no M4, child artifact or READY.
- `majorana_certificate_p0/Project.toml`, `Manifest.toml` and
  `majorana_p0_runner.jl`: exact Julia 1.11.9 execution environment and
  deterministic small-fixture runner.  The lock selects MajoranaPropagation
  0.3.0 / `b7849cb4` and PauliPropagation 0.7.3 / `2a96e9a9`; runner SHA-256 is
  `67a72a6ac2f02dd7572a48694c9e07ecaf84936411d212b48a996e6710946941`.
- `majorana_certificate_p0_fixture.json`, `majorana_certificate_p0_policy.json`,
  `majorana_certificate_p0_runtime_lock.json`,
  `majorana_certificate_p0_precommit_contract.json`,
  `majorana_certificate_p0_checker.py` and `test_majorana_certificate_p0.py`:
  result-unpinned P0 source/custody/independent-oracle closure.  Final precommit
  `c6050be2fcc0beb1454465aa77240f6b1f88c71b` contains no result contract,
  certificate or exact-result test.  Its checker independently rebuilds the
  Majorana algebra, outward intervals, merge/drop policy, Fock expectation and
  five-event ledger, while formal replay uses a nine-file Git-object allowlist and
  two fresh bubblewrap network namespaces.
- `majorana_certificate_p0_contract.json`,
  `majorana_certificate_p0_certificate.json` and
  `test_majorana_certificate_p0_result.py`: post-replay-only result binding.
  Both transcript SHA-256 values are
  `ff7a6f420e9ddadcba32df575c6b9e653a1ef703b3299b5a95e3b51442f5344c`;
  canonical witness SHA-256 is
  `b06a7a16bc6697b92e6d3fa05a33089a2437195d5d12133346b68438177d13f8`.
  The certificate covers 4,096 algebra pairs, 17,856 fixed primitive rotations
  and one frozen two-site composite fixture only.  L8, exact-Hubbard/reference
  composition and READY are explicitly excluded.  Majorana-specific tests pass
  34/34; complete discovery passes 1,208 tests with 26 expected skips.
- `majorana_certificate_p1_fixture.json`, `majorana_certificate_p1_policy.json`,
  `majorana_certificate_p1_precommit_contract.json`,
  `majorana_certificate_p1_runner.jl`, `majorana_certificate_p1_checker.py`,
  `majorana_certificate_p1_contract.json`,
  `majorana_certificate_p1_certificate.json` and the two P1 test modules:
  result-unpinned L2/L3 exact-CAR versus pinned-upstream action/cadence bridge.
  Precommit `0b3e766814442c1f4186335b50d19f78c043e527` covers 62 fixed operator
  instances, 11,538,944 operator-ket action columns and a 180-composite / 412-
  constituent / 284-boundary two-step schedule.  Both fresh replay transcripts
  have SHA-256 `8b0b1cc063adf5914c78cfbb2a88721c9623ec90a47dab087ea21c124c3badb7`;
  witness SHA-256 is
  `12b01c0aa89d71107f9acc5e4866f0b2998a84783aa1e255c9f462ac2a13b7f5`.
- `majorana_certificate_p2_fixture.json`, `majorana_certificate_p2_policy.json`,
  `majorana_certificate_p2_precommit_contract.json`,
  `majorana_certificate_p2/majorana_p2_runner.jl`,
  `majorana_certificate_p2_checker.py`, `majorana_certificate_p2_contract.json`,
  `majorana_certificate_p2_certificate.json` and the two P2 test modules:
  result-unpinned and post-replay closures for the fixed L8 staggered-
  magnetization first fused mapped step.  Lifecycle-safe precommit
  `65d0fe7778322b2bb83aabf65e7c12e989d73671` freezes 512 composites, 1,152
  constituents, 768 cadence boundaries, strict binary64 `2^-34` truncation,
  deterministic term/visit caps and per-replay cgroup v2 4-GiB/300-s limits.
  Both fresh transcripts have SHA-256
  `cf18113b82fd0348d2ae271630e59a67a1e9d73b3e09010f612cf89dbe09d0f5`;
  witness SHA-256 is
  `ca382cd7cd8dd01dfcf7ea540809b32f89a5c512ce71484e76ed7e409cb7ae03`.
  The execution finishes with 42,704 terms after 40,259,148 charged visits.
  P2 precommit/result tests pass 43/43, the focused P0/P1/P2/JW closure passes
  156/156, and complete discovery passes 1,296 tests with 26 expected skips.
  Authority is resource feasibility for this one Float64 prefix only; no
  truncation-accuracy, remaining-R100, exact-Hubbard, reference or READY claim
  is made.
- `majorana_certificate_p3_fixture.json`, `majorana_certificate_p3_policy.json`,
  `majorana_certificate_p3_precommit_contract.json`,
  `majorana_certificate_p3/majorana_p3_runner.jl`,
  `majorana_certificate_p3_checker.py`, `majorana_certificate_p3_contract.json`,
  `majorana_certificate_p3_certificate.json` and the two P3 test modules:
  result-unpinned and post-replay local-defect/expectation closure for the same
  fixed P2 L8 first fused mapped step.  Precommit
  `5c1d009165716e6b8a935cad57c556a7ba966bbf` separates the 27-file outer source
  custody from the exact six-file runner stage.  Two cgroup-limited fresh
  replays unshared both network and PID namespaces and used only that stage,
  the pinned Julia/depot, private `/proc` and `/dev`, writable `/scratch`, and
  exactly 18 read-only ELF/glibc/C.UTF-8 custody files.  Their byte-identical
  transcript SHA-256 is
  `f102a1aab1bfc4f05b38d98df6371cf1aee2c3087a9960ba1b2c346b6c6dba43`;
  witness and environment-manifest SHA-256 values are
  `6b4354b7f26db198427a74cfc7eac08c1895fda8d397918a9733fe7e32e8d7f5`
  and `07860c1eac760479a92059c00dd573f5de571bc13928e6bcde6cd31d22470d3f`.
  The integer `2^-128` ledger has 979,480 product, 118,208 merge and 328,956
  drop events, with total `296986546391593866116533250955376` ticks
  (`8.72765018884e-7`), strictly below `1/400000`.  The 42,704-term final state
  has exact Neel center
  `604040239256614101433905/604462909807314587353088` and declared interval
  `[21252757972972667064323158507908464249/21267647932558653966460912964485513216,
  21252795096290966013556423074564833671/21267647932558653966460912964485513216]`.
  Result-contract/certificate SHA-256 values are
  `1b795f11e76fca543028ce6b82d26b76711598efee61da12de0177a9d577af33`
  and `cd861b06721ea945d312c60dac309dd5d350848f3daec42d8eab5892f92ea1bc`.
  P3 precommit/result tests pass 49/49, the focused JW plus Majorana
  P0/P1/P2/P3 closure passes 205/205, and complete frontier discovery passes
  1,345 tests with 26 conditional skips.
  Authority is limited to the exact-untruncated product-formula operator and
  checkerboard-Neel expectation enclosure for this one prefix.  Global
  coefficientwise intervals, the remaining 99 steps, double occupancy,
  product-formula-to-exact-Hubbard error, physical reference and READY are
  excluded.  The P4 artifact below executes the separately precommitted
  adjacent-step handoff rather than extrapolating this one-step bound.
- `majorana_certificate_p4_fixture.json`, `majorana_certificate_p4_policy.json`,
  `majorana_certificate_p4_precommit_contract.json`,
  `majorana_certificate_p4/majorana_p4_runner.jl`,
  `majorana_certificate_p4_checker.py`, `majorana_certificate_p4_contract.json`,
  `majorana_certificate_p4_certificate.json` and the P4 precommit/result test
  modules:
  result-unpinned adjacent-step replay and post-replay cumulative-allocation
  closure under precommit `c6c2614186a8315775fa477e025195741c36d582`.  The
  earlier signed-zero v1 replay failed closed and has no authority.  S0v2
  materialized result SHA-256
  `7d71cf5f71f8efc15f5cb4b9f1cac27f23d3a6ef05ab6925cc2e54772fa3be60`
  and certificate SHA-256
  `70aa96ff57cf2021099f79786d8f3f14a5d23f0459023603d65f475a463563a0`;
  its raw and composed witness SHA-256 values are respectively
  `869504938d4081d15fbd62e1353026141ebe41bef019c8a49ff79aebc515c493`
  and `b42b1ec0555f8dad15d35fd0f8ef0d35755175b91b3fec9a6e2970bfc406442a`.
  S0v2
  inherits the P3 upper once, then records step-2 product, merge and drop totals
  of `148110706480666299015145`, `145718728421478199062528` and
  `4432692192952477384756578989637632` ticks.  The resulting local total is
  `4432692193246306819658723487715305` ticks (`1.3026511580e-5`, `5.2106`
  times `1/400000`); `99.9999999934%` comes from the drop upper.  The cumulative
  two-step total is `4729678739637900685775256738670681` ticks
  (`1.3899276599e-5`, `2.7799` times `1/200000`).  The 72,808-term state has
  exact Neel center
  `301388136752758141215773/302231454903657293676544`.  Terminal branch and
  status are `TWO_STEP_CUMULATIVE_BOUND_EXCEEDS_ALLOCATION` and
  `VERIFIED_MAJORANA_P4_L8_TWO_STEP_CUMULATIVE_ERROR_BOUND_EXCEEDS_ALLOCATION_SUBCERTIFICATE`.
  This is only a bounded no-go for fixed `2^-34` thresholding with additive L1
  drop accounting: actual simulation error, the remaining 98 steps,
  product-formula-to-exact-Hubbard error, double occupancy, physical reference
  and READY remain uncertified.  The next artifact should be a new
  result-unpinned threshold-hardening child for a `2^-36`/`2^-37` design probe
  or budget-constrained drop rule, not a direct third-step child.
- `majorana_certificate_p5_design_probe.py`,
  `majorana_certificate_p5_design_probe/majorana_p5_threshold_resource_probe.jl`,
  `majorana_certificate_p5_design_probe_policy.json`,
  `majorana_certificate_p5_design_probe_report.json` and their preprobe/result
  tests:
  non-authoritative resource-envelope closure for conditional step-2 threshold
  hardening.  The result-blind preprobe commit is
  `f65ceb94494d71a2de1cd6057405a583fa388f82`; report SHA-256 is
  `602c4eddea30c20ddb793e2641b1e8b55e4767a62366b946892a19c3802dffc5`,
  policy SHA-256 is
  `e47ad24291f217b0b5d54ba6aa120c479d522bd23c74faf41b5bde6da2413aa2`,
  and staging-manifest SHA-256 is
  `8146322aab025311be873daaf58a61fa0e6ad5123d68182894a1706c40d2eeab`.
  The strict `2^-34` resource control exactly reproduces P4.  Conditional
  step-2 `2^-36` and `2^-37` both complete under 3 GiB/600 s without a
  deterministic cap.  Their step-2 final term counts are 174,280 and 241,120,
  total P2 visits are 279,133,312 and 372,980,288, and diagnostic maximum RSS
  values are 731,012 and 734,516 KiB.  The precommitted two-times/next-power-of-
  two rule yields one common formal cap set, including 524,288 term caps,
  536,870,912 scan/propagation visits and 1,073,741,824 total P2 visits.
  This report deliberately contains no defect ticks, allocation result,
  term/drop digest or Neel result and has `scientific_authority=NONE`; it cannot
  select candidates or enter the formal runner.  The formal P5 child must run
  both frozen candidates independently and inherit only P3 `E1` once after
  full step-1 conformance.
- `majorana_certificate_p5_fixture.json`, `majorana_certificate_p5_policy.json`,
  `majorana_certificate_p5_precommit_contract.json`,
  `majorana_certificate_p5/majorana_p5_runner.jl`,
  `majorana_certificate_p5_checker.py`, `majorana_certificate_p5_contract.json`,
  `majorana_certificate_p5_certificate.json`, `test_majorana_certificate_p5.py`
  and the post-replay `test_majorana_certificate_p5_result.py` companion:
  result-unpinned and post-replay formal S0 closure for fixed P3 `2^-34` step 1
  followed by conditional step-2 candidates `2^-36` and `2^-37`.  Precommit
  `85173e5982f526258563fc00e326d7f3f39b0a7a` has precommit-contract SHA-256
  `ad5980e74370a732456a1729665702fcaab4751d322145c0ea9775b329f06b01`.
  Checker, runner, fixture and policy SHA-256 values are respectively
  `b60cc0ab58316630f5fb15532c0d70c5dabaea1828fef19a2f570dae8f9f26d7`,
  `3f91ae3a6886c930cd482a13809cad5e772b8c5db0188bfa6dcbf3a7067721ea`,
  `fd8b46c8761f548d615042b24f8ec85b32891e4f42dbafdd9bd70d58379a8afb`
  and `5fb96c16dcae4cdef807491a65ccddb051e9451d0dc7d652f2971b1d0323185e`.
  Four fresh isolated processes, two per candidate, produced byte-identical
  stdout within each pair.  Raw K36/K37 witness SHA-256 values are
  `d7e176ec1ca6963ad85605bc8d7142ec5ec21f5db568b9bd3a24fa5e4a8f6ee7`
  and `484de796a2b47572db9b8f4dbc6130c3172d55a976973fb8e5c9131124edc901`;
  canonical composed-witness SHA-256 is
  `de70c1ac987906f6e800e7207bbc6fb9a07d8219002ba1c25ac51d2669139d7f`.
  Both candidates fail the strict local `1/400000` allocation; K37 alone is
  within the conditional cumulative `1/200000` allocation, so neither passes
  both required comparisons.  Terminal branch and status are
  `NO_CANDIDATE_WITHIN_BOTH_ALLOCATIONS_AFTER_ALL_CANDIDATES_COMPLETE` and
  `VERIFIED_MAJORANA_P5_L8_CONDITIONAL_STEP2_K36_K37_ERROR_BOUNDS_NO_SELECTION_SUBCERTIFICATE`.
  Result-contract and certificate SHA-256 values are
  `8177c2ebe24ef9da5d796ea61fac1ea035b9d1460d9708df0271edd988bd6c32`
  and `e99e6d5b9f4f037132d337c203ac5baf4527065f3a2ba2ee2f27565ab935c516`.
  The 9,335,545-byte formal replay package remains non-committable evidence at
  `/tmp/majorana-p5-formal-replay-85173e59.json`, with SHA-256
  `d58edc020c6611ac90c060007dea8fe96f28c9038381182ace4f632fc29331b3`;
  the committed result contract retains the witness and reconstructible replay
  summary, so the `/tmp` package must not enter the repository.  The exact-result
  test SHA-256 is
  `7c349309dfb50679fe80300d02c41b5834ecf5372dbdc72d2e1f841ddf17b779`.
  Authority is limited to these two fixed
  conditional candidates after the conformed P3 prefix; uniform rethresholding,
  budget-constrained drop, the remaining 98 steps, exact-Hubbard error, double
  occupancy, physical reference and READY remain excluded.
- `majorana_certificate_p6_design_probe.py`,
  `majorana_certificate_p6_design_probe/majorana_p6_adaptive_drop_resource_probe.jl`,
  `majorana_certificate_p6_design_probe_fixture.json`,
  `majorana_certificate_p6_design_probe_policy.json`,
  `majorana_certificate_p6_design_probe_report.json` and their preprobe/result
  tests: non-authoritative D0 resource-envelope closure for the full-domain
  adaptive-drop candidate `E768-MAX-LAZY37-V1`.  The result-blind preprobe
  commit is `2483450e9ae93402a5315dae21b142d08742e783`; report SHA-256 is
  `7c591111ee99b18bf2ccaca2d8157e93a19a3db49b6a680c01b0be13f570fc56`,
  policy SHA-256 is
  `6a8b9c1c2584cbe8998643e0644f35896d54fe57444eff795a93a83987fa87ab`,
  fixture file/canonical SHA-256 values are
  `2e5254b7a98cf4b0ba08c5674215d78a59a78ddf0b0e27460b7cf82ac7be3b6e`
  and `9b02421b53ef407531b95e1f9d4f48f29642f88962be297789ecbc88792755ba`,
  and staging-manifest SHA-256 is
  `f15196a28aaeeb2535d719f533dd4cb5f6c17f51e184450fa7a02f547358788f`.
  The nonselectable control exactly reproduces the frozen P5 K37 aggregate
  resource projection; the adaptive path completes 768 selection boundaries
  with 284,847 final terms, 426,811,185 total P2 visits and 160,531,288 total
  selection-work units.  The derived future S0 envelope uses 1,048,576 term
  caps, 536,870,912 cap-scan/propagation caps, 1,073,741,824 total-P2/combined
  caps, 536,870,912 total-selection-work, 2 GiB memory, zero swap, 1,800
  seconds and 4,096 stderr bytes.  The exact-result test SHA-256 is
  `60991ae7decb46de8028f0527b48e3a52acd1d312c88f74f381b1a1a1bb94c8d`.
  Report and witnesses have `scientific_authority=NONE`; they contain no
  scientific defect ledger, allocation result, term/drop stream, observable
  result or candidate certificate and cannot enter the formal S0 runner.  S0
  must be separately result-unpinned, schema-cap its scientific output, run two
  fresh byte-identical replays and reconstruct them independently.
- `majorana_certificate_p6_fixture.json`, `majorana_certificate_p6_policy.json`,
  `majorana_certificate_p6_precommit_contract.json`,
  `majorana_certificate_p6/majorana_p6_runner.jl`,
  `majorana_certificate_p6_checker.py`, `majorana_certificate_p6_contract.json`,
  `majorana_certificate_p6_certificate.json`, `test_majorana_certificate_p6.py`
  and the post-replay `test_majorana_certificate_p6_result.py` companion:
  result-unpinned and post-replay formal S0 closure for the sole
  `E768-MAX-LAZY37-V1` adaptive step-2 candidate after the certified P3 prefix.
  Precommit `e9c3b2ee9c095d0be6f834fa5f49ede9ec035e75` has precommit-contract
  SHA-256
  `4837c0411ea2392f07340b689e5faf4f04516cf1acb5a0336db1a2b1366c244f`.
  Checker, runner, fixture and policy file SHA-256 values are respectively
  `5db54434427079c6201c9006f4597ba6e557335577a38ed7230800e101c00b57`,
  `b63143c066d3d258594e27ee4062632632030e9962a0fcd127fcd5000ff9cc1c`,
  `fb381c613d675551d33680484a88870020a494e4a356dafd9fd869714c9d475d`
  and `942dc400a0df39541b083eb4de0e7d16bbc3b975b025a6ac3b6b3911efc8dd47`.
  Two fresh isolated processes produced the same transcript SHA-256
  `bcd72c0291cb98a674cfc2185d711c0a33ea4948c42d630e55d5dd3407d68341`.
  Raw and independently reconstructed canonical witness SHA-256 values are
  `33d4c30f00fae1797cbf266dcdf9eb6e5af4f60868c6bf6a2a081a44ce3c65e9`
  and `73c988137eba4e180ebe98101dd93a06d62f8a9a055ad9db1cf5d94bc77e9d25`.
  The step-2 local error is
  `850704723164717957289921415065051` `2^-128` ticks, strictly below the
  `1/400000` maximum by `1194137628201368515103514369` ticks; the inherited-
  once two-step error is `1147691269556311823406454666020427` ticks, below the
  `1/200000` maximum by `553720565048380493910418371138414` ticks.  The
  candidate therefore reaches terminal branch `CANDIDATE_QUALIFIED` and status
  `VERIFIED_MAJORANA_P6_L8_E768_MAX_LAZY37_LOCAL_AND_CUMULATIVE_ERROR_BOUNDS_WITHIN_ALLOCATIONS_SUBCERTIFICATE`.
  The final state has 284,847 retained terms and term-stream SHA-256
  `9bd44992823cc6f8cf731f84954840d4927a972fb6a78c1583c3d8c0983a7c51`;
  the adaptive selection charges 160,531,288 work units.
  Result-contract and certificate SHA-256 values are
  `dfe4f6194a0ec6c2f4597c164e30959289e85adc3f31c21cbf899c47494f90ce`
  and `4d5eac4084b97021d85995be44d4b829a6281e4a6cf1f0566fd4a9e3319df357`.
  The 4,686,380-byte formal replay package remains non-committable evidence at
  `/tmp/majorana-p6-s0-replay-package.json`, with SHA-256
  `256fba0bcbfbc967717b602773d29e8135e36032dcb2737bab15c467fdc9c8c8`;
  the committed contract retains its witness and reconstructible package
  summary.  The exact-result test SHA-256 is
  `b2e386a676fbcb56872f048e7ff3ef9beb43379f2b66994169c6db190d68776a`.
  Authority is limited to this fixed two-step operator and
  checkerboard-Neel enclosure.  Step 3 and the remaining 98 steps, exact-
  Hubbard error, double occupancy, physical reference, selector global
  optimality and READY remain excluded.
- `majorana_certificate_p7_design_probe.py`,
  `majorana_certificate_p7_design_probe/majorana_p7_step3_resource_probe.jl`,
  `majorana_certificate_p7_design_probe_fixture.json`,
  `majorana_certificate_p7_design_probe_policy.json`,
  `majorana_certificate_p7_design_probe_report.json` and their preprobe/result
  tests: non-authoritative D0 admission attempt for the adjacent step-3
  `E768-MAX-LAZY37-STEP3-V1` resource path.  The result-blind preprobe commit is
  `8cfbd7869b38e7e0d20f72e7550b59c845bfb43a`; report SHA-256 is
  `4bf4be7f77fd499ffc9bd975f07353fd14ee7403cd6fc7759974dda37f8588cf`.
  One fresh process ran under the fixed 2 GiB memory, zero-swap and 1,800-second
  admission.  Systemd delivered `SIGTERM` at the runtime boundary; the process
  returned `-15` after `1800.604540675` outer-monotonic seconds, with zero
  stdout bytes and a `null` resource witness.  Cgroup monitoring observed an
  approximately 735 MiB memory peak, but this is run-monitoring context only:
  the canonical report's `time_diagnostics` object is empty and it does not
  claim that value as D0 evidence.  Terminal status is
  `INDETERMINATE_HOST_OR_RUNTIME_FAILURE`; fixed S0 admission is
  `NOT_ESTABLISHED` (the stored status is
  `NOT_ESTABLISHED_INDETERMINATE_HOST_OR_RUNTIME_FAILURE`), with
  `scientific_authority=NONE` and `certificate_eligible=false`.  This is
  neither a deterministic-cap result nor a no-go, cannot enter P7 S0, and does
  not permit any frozen cap to be relaxed in place.  A continuation requires a
  separately precommitted new version for time/algorithmic-complexity probing
  or proof/execution decomposition, without inspecting or using suppressed
  scientific values such as term streams or digests, checkerboard-Neel values,
  exact centers, declared intervals or operator-error ticks.
- `majorana_certificate_p7_d1_phase_probe.py`,
  `majorana_certificate_p7_d1_phase_probe/majorana_p7_step3_phase_probe.jl`,
  `majorana_certificate_p7_d1_phase_probe_fixture.json`,
  `majorana_certificate_p7_d1_phase_probe_policy.json`,
  `majorana_certificate_p7_d1_phase_probe_report.json` and their preprobe/result
  tests: separately versioned, non-authoritative D1 phase diagnostic for the
  frozen P7 adjacent-step-3 path.  The D0-result-informed but scientific-blind
  preprobe commit is `48a1be6932331e2925261965c783e6b40b555747`, a direct child
  of D0 result commit `4ebed6b651e3c9605f84939d6a9efff8281bc38b`; canonical
  report SHA-256 is
  `9d37609c51f9149baf347fbf801338cc0abe7c7323c187fe71a4932099f8f713`.
  One fresh process ran under the unchanged 2 GiB memory, zero-swap and
  1,800-second memory/swap/runtime admission.  The supervised command returned
  `-15` after `1800.381352338` outer-monotonic seconds; stdout was empty and
  the resource witness is `null`.  Its 15-event
  `LEGAL_PREFIX_INTERRUPTED` trace observed the P6-prefix conformance milestone
  at `660.422891266` seconds and `STEP3_ENGINE_STARTED` at `660.589519616`
  seconds, but no step-3 engine-return or finalizer event.  These outer-receive
  timestamps only localize the observed runtime-envelope interruption to the
  step-3 adaptive engine; they are not scientific timings, do not reprove P6,
  and establish neither a deterministic cap nor a no-go.  The report remains
  `scientific_authority=NONE`; exact S0 status is
  `NOT_ESTABLISHED_BY_D1_PHASE_DIAGNOSTIC`.  A continuation requires a
  separately precommitted D2 focused on source-pinned step-3 stage diagnostics
  or a separately versioned algorithm/proof decomposition, without changing
  the candidate or admission caps in place or exporting suppressed scientific
  state.
- `majorana_certificate_p7_d2_schedule_probe.py`,
  `majorana_certificate_p7_d2_schedule_probe/majorana_p7_step3_schedule_probe.jl`,
  `majorana_certificate_p7_d2_schedule_probe_fixture.json`,
  `majorana_certificate_p7_d2_schedule_probe_policy.json`,
  `majorana_certificate_p7_d2_schedule_probe_report.json` and their
  preprobe/result tests: separately versioned, non-authoritative D2 static-
  schedule diagnostic for the frozen P7 adjacent-step-3 path.  Its D1-result-
  informed but scientific-blind preprobe commit is
  `2692f10a266b635ef1942bc510801a7db952c0d9`, a direct child of D1 result
  commit `29911a8ac46c068c550504f8b4a57d27a9441c0c`; canonical report SHA-256
  is `94c8cc4bd9487f14d598d92dd96153ae9e631c8c232d484952b91eab3e5fd0dc`.
  One fresh process ran under the unchanged 2 GiB memory, zero-swap and
  1,800-second admission.  The supervised command returned `-15` after
  `1800.611541745` outer-monotonic seconds; stdout was empty and the resource
  witness is `null`.  Its 33-event `LEGAL_PREFIX_INTERRUPTED` trace returned
  through segments A--D, then reached segment E/H4 checkpoint 1 after frozen
  local composite ordinal 22.  It emitted no E checkpoint-2 or return,
  later-segment, step-3 engine-return or finalizer marker.  The unresolved
  static window is E local ordinals 23--43 (global zero-based composite
  indices 246--266), not an observed scientific state or identified failure
  cause.  The report remains `scientific_authority=NONE`; exact S0 status is
  `NOT_ESTABLISHED_BY_D2_SCHEDULE_DIAGNOSTIC`.  A continuation requires a
  separately precommitted, scientific-blind D3 subgrid or a separately
  versioned algorithm/proof decomposition; no frozen candidate or admission
  cap may be changed in place.
- `majorana_certificate_p7_d3_e_subgrid_probe.py`,
  `majorana_certificate_p7_d3_e_subgrid_probe/majorana_p7_step3_e_subgrid_probe.jl`,
  `majorana_certificate_p7_d3_e_subgrid_probe_fixture.json`,
  `majorana_certificate_p7_d3_e_subgrid_probe_policy.json`,
  `majorana_certificate_p7_d3_e_subgrid_probe_report.json` and their
  preprobe/result tests: separately versioned, non-authoritative D3 static
  segment-E subgrid diagnostic for the frozen P7 adjacent-step-3 path.  Its
  D2-result-informed but scientific-blind preprobe commit is
  `55453f7fb0251f676a71220eb7b090d78ba6d8c5`, a direct child of D2 result
  commit `937065e0a576ba7615d48e389fb8e75e3e3aa677`.  The verified canonical
  report is 11,888 bytes with SHA-256
  `8374dff73a0753f95eba1fb1bcf3612e269095b33a223717293b33ef5f65f0db`.
  Its sole controlled execution produced a 33-event
  `LEGAL_PREFIX_INTERRUPTED` trace: segments A--D returned, segment E/H4
  started and reached checkpoint 1, and no E subgrid-26 or later marker,
  checkpoint-2, E-return, later-segment, step-3 engine-return or finalizer
  marker was emitted.  The static marker contract narrows the unresolved
  window to E local ordinals 23--26, corresponding to global zero-based
  composite indices 246--249.  Markers confirm passage through at least 246
  frozen step-3 completion points; because local ordinal 26 may complete
  before its marker is emitted, the possible runtime completion-point-count
  envelope is 246--250.  The controlled command returned `-15` after
  `1800.488401583` outer-monotonic seconds; the 1,830-second outer safety
  timeout did not fire and stdout was empty.  Those process-level facts are
  only host/runtime diagnostics and do not identify a cause, signal source or
  active composite.  The report remains `scientific_authority=NONE`, its
  resource witness is `null`, and exact S0 status is
  `NOT_ESTABLISHED_BY_D3_E_SUBGRID_DIAGNOSTIC`; this is neither a
  deterministic-cap result nor a mathematical or algorithmic no-go.
- `majorana_certificate_p7_d4_e_per_composite_probe.py`,
  `majorana_certificate_p7_d4_e_per_composite_probe/majorana_p7_step3_e_per_composite_probe.jl`,
  `majorana_certificate_p7_d4_e_per_composite_probe_fixture.json`,
  `majorana_certificate_p7_d4_e_per_composite_probe_policy.json`,
  `majorana_certificate_p7_d4_e_per_composite_probe_report.json` and their
  preprobe/result tests: separately versioned, non-authoritative D4 V2 static
  segment-E per-composite diagnostic for the frozen P7 adjacent-step-3 path.
  Its D3-result-informed but scientific-blind preprobe commit is
  `75371cf32b31e09ae255a1aafc2a98b2bf9d0a5a`, a direct child of D3 result
  commit `70b5095fde9fdb743d1e5910b80bbcac88de4fca`.  Superseded D4 V1
  preprobe commit `c8a4d9e137d4976e1b8841041a72b53993068e46` was never executed,
  produced no report or execution claim and is not a V2 result input.  The
  verified V2 canonical report is 11,822 bytes with SHA-256
  `269e74dd23c33b0e2d1943d7f25e44ebcd897bdde1a96645a80eba4cf4e5da19`.
  Its sole controlled execution produced a 32-event
  `LEGAL_PREFIX_INTERRUPTED` trace: segments A--D returned and segment E/H4
  started, but no E checkpoint-1 or fixed local-ordinal 23, 24, 25 or 26
  per-composite marker was emitted.  D4 V2 therefore adds no
  localization inside D3's 23--26 window and does not refute the separately
  frozen D3 result.  The command returned `-15` after `1800.351788777`
  outer-monotonic seconds; the 1,830-second outer safety timeout did not fire
  and stdout was empty.  These facts are host/runtime diagnostics only and do
  not identify a cause or active composite.  The report remains
  `scientific_authority=NONE`, its resource witness is `null`, and exact S0
  status is `NOT_ESTABLISHED_BY_D4_E_PER_COMPOSITE_DIAGNOSTIC`; this is
  neither a deterministic-cap result nor a mathematical or algorithmic no-go.
  D4 V2 must not be rerun in place; a continuation requires a separately
  versioned algorithm/proof decomposition or a separately precommitted,
  scientific-blind cross-run repeatability design.
- `hubbard_l8_double_occupancy_adaptive_k_four_gate_k655360_c37_l1048576_d1048576_q76_screen.py`
  and its `*_transcript.json`: same-cap D37 horizon extension through q76.  The
  58,178-byte screen source SHA-256 is
  `621f9c97b72c3582314d360b9b29b46a9cb40bf60298776adfc52849300bd14e`.
  It exact-byte executes q74, which retains q72 as its private raw parent, and
  loads the q74 canonical only after the fresh q1 replay.  Ordinary pinned source
  inputs are bounded by 262,144 bytes.  The sole larger, non-source execution
  component,
  `hubbard_l8_interval_checkpoints/double_occupancy_boundary_002.b85`, is an
  independently bounded 841,495-byte encoded boundary under its own 1,048,576-byte
  cap and exact SHA-256
  `f92d5eadc01e1d9ebef86328b9eed92d867a2dd79b8bb2ba0baa821fe3b037ab`.
  q75 pre-count 733,965 selects index 36/`K=655,360`, drops 78,605 terms and
  127,874,290,338 ticks, commits E=2,289,318,681,442,732 and retained digest
  `1a0c6aae47e81c4473b43ca5c27f8580a8754c72f9332e761bbddc1b31722def`;
  its ranking boundary is the exact tie 5,447,500 = 5,447,500.  q76 pre-count
  789,691 has no feasible C37 row: minimum effective K is 665,836, exceeding
  655,360 by 10,476.  Its maximum row drops 160,308,954,820 ticks, exceeding
  prefix slack by 58,984,624,003 ticks.  The terminal branch is
  `Q75_SUCCESS_Q76_FAILURE`, not a resource abort.  The ledger has 76 records,
  75 history entries and 2,812 rows; records/history SHA-256 values are
  `5ba16ae933ae9a17633a1c3c4d7edba28b2c115bef475480272fa2cf9df39274`
  and `b72e24b2dbe1d8eff88ff9ad1e1bc47cebeb59807168603cd86ff91c218c604a`.
  The 798,861-byte canonical SHA-256 is
  `856ede1f5774795c25ca2c36eafa8ac0696402194c6bf4e17ea5e8874efc22e0`.
- `test_hubbard_l8_double_occupancy_adaptive_k_four_gate_k655360_c37_l1048576_d1048576_q76_screen.py`:
  57,919-byte static, synthetic, adversarial and opt-in exact-replay suite with
  source SHA-256
  `5a750e9eddff605cb880fa494307806c40c8fe0f224ce7960e846619072792fd`.
  Its default gate closes the nested q74/q72 restoration, post-only order, five
  branches, six structured-abort cases, exact q1--74 handoff, 11 components/10
  custody entries, unique boundary pin and bounded atomic output without replay.
- The M q90 and D q76 frozen pre-replay audits both closed at P0=0, P1=0 and
  P2=0.  Their fresh replays were then run serially, never concurrently: M took
  13:05 with maximum RSS 689,500 KiB, followed by D at 11:29 with maximum RSS
  715,972 KiB.  Both canonicals record an exact no-feasible-candidate failure row,
  `resource_policy_abort=null`, no child-boundary commit and no positive artifact.
  The failure-local next discrete ladder points are `K=638,976/C35` for M and
  `K=671,744/C38` for D; neither has been executed or precommitted as successful.
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

## Majorana P9 post-D4 governance closure

- `majorana_certificate_p9_g0_post_d4_governance_closure_contract.json`:
  result-informed, nonexecuting G0 contract pinned to D4 B1
  `1bfdf15c553c6d4934ce4395114458dcda1be4f9`.  It binds the five D4 B0
  source blobs, the 8,283-byte D4 report and its SHA-256
  `46aa8ea40a96f84e091de039cbb7212e4d165ef1c3a36cee43038a59736c9142`,
  permits only a minimal D4 governance projection, and requires each review
  predicate to use one and the same D4 trace.  It forbids D3/D4 marker
  splicing, a D4 repeat, D5, finer instrumentation, in-place cap or candidate
  changes, and any scientific/resource/S0 authority.
- `majorana_certificate_p9_g0_post_d4_governance_closure_record.json`:
  canonical governance decision.  All KAPPA/LAMBDA/MU/NU target predicates
  are false because the verified D4 legal prefix ends at
  `STEP3_SEGMENT_D_STARTED`, before checkpoint 1 and ALPHA.  Its disposition
  is `CLOSED_NO_POST_D4_REVIEW_TARGET`; matched targets are empty and all
  execution, candidate-selection, resource/no-go and scientific authority
  flags are false.
- `majorana_certificate_p9_g0_post_d4_governance_closure_validator.py`:
  read-only fail-closed validator for strict JSON, D4 B0/B1 Git topology,
  source pins, canonical D4 report bytes, minimal projection, same-trace
  predicate evaluation, exact record reconstruction and the six-path G0
  staged/committed lifecycle.  It contains no candidate launcher.
- `test_majorana_certificate_p9_g0_post_d4_governance_closure.py`:
  positive and adversarial static coverage for duplicate keys, source/report
  drift, forbidden host-field projection, cross-run marker splicing, false
  review targets, authority flags and exact Git path gates.
- G0 leaves seven proof-only static resource-envelope obligations open:
  source/type/allocation closure; alias/ownership/lifetime overlap; exact
  payload/capacity bytes; runtime/GC/JIT/allocator overhead; peak composition
  against the unchanged 2 GiB cap; an independent checker with adversarial
  mutations; and complete accounting for sorting, package primitives, BigInt,
  hashing, stringification and container-resize work.  This ledger is a design
  queue only and does not authorize an execution.  An
  `ASSESSED_NOT_ESTABLISHED` outcome keeps admission closed; only a positive
  seven-obligation result with a peak strictly below `2^31` can become input
  to a separate future execution-governance decision.

## Majorana P10-G1 post-assessment governance closure

- `majorana_certificate_p10_g1_post_assessment_governance_contract.json`:
  direct-child, result-informed and nonexecuting closure for P10-A B1. It
  projects only P10-A identity, authority-false fields and the closed negative
  assessment; it excludes D3/D4 diagnostics and does not claim an exact byte
  envelope.
- `majorana_certificate_p10_g1_post_assessment_governance_record.json`:
  canonical decision record with disposition
  `OPEN_NONEXECUTING_P10_B_CONTRACT_FEASIBILITY_AUDIT_ONLY`.
- `majorana_certificate_p10_g1_post_assessment_governance_validator.py` and
  `test_majorana_certificate_p10_g1_post_assessment_governance.py`:
  read-only validators for P10-A B0/B1 custody, the minimal projection,
  canonical record reconstruction and exact G1 direct-child lifecycle.
- The only allowed followup is
  `P10-B-SOURCE-RUNTIME-CONTRACT-FEASIBILITY-AUDIT-V1`. It may inventory
  independent source/layout/capacity/lifetime/runtime/machine-cost evidence;
  it must not run Julia or the candidate, change caps, infer resource no-go or
  authorize execution.

## Majorana P10-B source/runtime contract-feasibility audit

- `majorana_certificate_p10_b_source_runtime_contract_feasibility_contract.json`:
  P10-G1-authorized read-only audit contract; pins four frozen source inputs,
  seven evidence classes, the unchanged 2 GiB cap, and authority exclusions.
- `majorana_certificate_p10_b_source_runtime_contract_feasibility_record.json`:
  canonical result. Every class is
  `NO_INDEPENDENT_STATIC_CONTRACT_IN_FROZEN_INVENTORY`, producing the scoped
  outcome `CLOSED_NO_INDEPENDENT_STATIC_BYTE_CONTRACT_ROUTE`.
- `majorana_certificate_p10_b_source_runtime_contract_feasibility_validator.py`
  and `test_majorana_certificate_p10_b_source_runtime_contract_feasibility.py`:
  read-only source-digest, P10-A obligation-ledger, P10-G1 authority,
  canonical-reconstruction and staged-lifecycle checks.
- This is not a global impossibility claim, byte proof, resource no-go, OOM
  attribution, or permission to execute Julia/the candidate. It leaves peak
  bytes and strict cap comparison unknown; any future evidence or execution
  needs fresh independent governance.

## Majorana P10-G2 post-audit governance closure

- `majorana_certificate_p10_g2_post_audit_governance_contract.json` and
  `majorana_certificate_p10_g2_post_audit_governance_record.json`: validate
  P10-B custody, close the current frozen Julia static-byte route, and open
  only nonexecuting P11-A explicit-memory design work.
- `majorana_certificate_p10_g2_post_audit_governance_validator.py` and
  `test_majorana_certificate_p10_g2_post_audit_governance.py`: read-only Git
  topology, blob custody, canonical decision, authority, and exact-lifecycle
  checks.
- P11-A has no implementation, compilation, external acquisition, benchmark,
  Julia/candidate execution, cap-change, or scientific-result authority.

## Majorana P11-A explicit-memory kernel feasibility design

- `majorana_certificate_p11a_explicit_memory_kernel_design_contract.json`:
  source-pinned nonexecuting design for an AOT, no-GC/JIT, fixed-arena Step3
  route that preserves frozen mask, Float64, ranking, drop, and hash semantics.
- `majorana_certificate_p11a_explicit_memory_kernel_design_report.json`:
  canonical design result. It rederives an 872,415,232-byte provisional
  explicit-region subtotal and classifies all seven questions as
  `ROUTE_IDENTIFIED_CONTRACT_REQUIRED`.
- `majorana_certificate_p11a_explicit_memory_kernel_design_validator.py` and
  `test_majorana_certificate_p11a_explicit_memory_kernel_design.py`:
  frozen-source anchors, exact integer region arithmetic, P10-G2 custody,
  canonical reconstruction, authority mutations, and exact-lifecycle checks.
- The subtotal is a design budget, not an implemented layout, process peak or
  cap-admission result. Implementation, compilation, semantic equivalence,
  resource/no-go, execution and scientific authority remain absent.

## Majorana P11-G1 preimplementation governance

- `majorana_certificate_p11_g1_preimplementation_governance_contract.json`
  and `majorana_certificate_p11_g1_preimplementation_governance_record.json`:
  validate P11-A custody and authorize only a nonexecuting P11-B contract pack.
- `majorana_certificate_p11_g1_preimplementation_governance_validator.py` and
  `test_majorana_certificate_p11_g1_preimplementation_governance.py`:
  read-only topology, blob, canonical-record, authority and lifecycle checks.
- Local toolchain identity and official metadata may be read; implementation,
  compilation, downloads, installation, benchmark and candidate execution are
  forbidden.

## Majorana P11-B preimplementation contract pack

- `majorana_certificate_p11b_preimplementation_contract_pack_contract.json`:
  selected freestanding C17 static-ELF target, local GCC/Binutils identity
  receipt, official metadata pointers, byte layouts, contiguous arena,
  2112-bit scratch derivation, full-prefix semantics and runtime targets.
- `majorana_certificate_p11b_preimplementation_contract_pack_report.json`:
  canonical result with a 1,028,653,056-byte preimplementation target, closed
  implementation/execution gates, and explicit non-headroom/non-peak status.
- `majorana_certificate_p11b_preimplementation_contract_pack_validator.py`
  and `test_majorana_certificate_p11b_preimplementation_contract_pack.py`:
  source/Git custody, slot overlap, arena contiguity, exact arithmetic, local
  toolchain identity, report reconstruction and adversarial gate checks.
- P6 has no serialized two-step term state; future source must reconstruct the
  frozen Step1/Step2 prelude before Step3. No source, compile, link or candidate
  execution is authorized by P11-B.
