# Final synthesis: fermion continuity and computational leverage

Status date: 2026-07-11

Scope: physical fermions and fermionic mathematics. This report does not refer
to the historical Fermion Memory service.

## Executive verdict

There is no single established “fermion continuity” law spanning condensed
matter, quantum field theory, lattice regularization, and variational geometry.
The phrase covers several different continuity questions whose assumptions and
failure modes must remain separate.

Fermionic structure is also not a universal computational or AI advantage. It
becomes a lever when the target problem and representation preserve one of a
small set of structures: Gaussian closure, parity grading,
determinant/Pfaffian algebra, negative dependence, or genuinely native
fermionic operations. The advantage disappears, changes resource unit, or
becomes exponential when non-Gaussian resources, generic interactions,
preprocessing, physical control, or a mismatched inductive bias dominate.

| Question | Final answer | Confidence |
|---|---|---|
| Is there one cross-domain fermion-continuity principle? | No. There are related symmetry, anomaly, topology, and manifold statements, but no proved equivalence or common conservation law. | High |
| Does fermionic structure create rigorous computational/statistical gains? | Yes, for matched tasks and cost models. The strongest examples are Gaussian/matchgate compression, determinant identities, and conditional DPP estimators. | High |
| Do physical fermions cause a generic classical-ML advantage? | No evidence in the reviewed literature. Classical ML uses transferable determinant and negative-dependence mathematics. | High |
| Is native fermionic quantum hardware already an end-to-end advantage? | Component maturity is now substantial, but the reviewed sources do not demonstrate an integrated processor or an application-level advantage against a normalized qubit baseline. | Medium-high |
| Is the evidence base ready for synthesis? | Yes. All 70 focused claims have three reviews: 56 unanimous verified findings, 8 split/partial accepted findings, and 6 refuted as written. | High |

## 1. Evidence base and decision rule

The takeover preserved Claude's source artifacts, audited the incomplete
workflow, and then closed the three missing evidence clusters.

| Evidence layer | Reviewed claims | Outcome | Role in this synthesis |
|---|---:|---|---|
| Claude broad survey, round 1 | 25 selected from 120 candidates | 22 confirmed, 3 refuted | Condensed-matter continuity, anomalies, lattice no-go results, matchgate shadows |
| Claude targeted survey, round 2 | 25 selected from 119 candidates | 21 confirmed, 4 refuted | Fermionic tensor networks and determinant/Pfaffian neural states |
| Focused gap-3/4/5 ledger | 70 | 56 unanimous verified, 8 split/partial accepted, 6 refuted as written | DPPs, Gaussian/non-Gaussian boundary, Gaussian geometry, encodings, native hardware |

A Physical Review Research paper accepted on 2026-06-17 was found after the
focused ledger closed and received a separate three-review update. It does not
change the 70-claim counts above; its adjudication is preserved in
`POST_LEDGER_MATCHGATE_UPDATE.md`.

These rows must not be summed as independent replications. Some claims and
sources are linked, and several research programs reuse authors, benchmarks,
or survey-to-primary chains. Three reviewers establish an audit gate; they do
not create three independent experiments or proofs.

The durable status source is `claim-status.jsonl`. A split-vote finding may be
used only with its replacement wording. Publication status, resource unit, and
source dependence are part of the finding, not optional footnotes.

## 2. The continuity map

| Meaning of continuity | Object being followed | What remains constrained | Principal failure or modification |
|---|---|---|---|
| Landau adiabatic continuity | Interacting electron state relative to a free Fermi gas | Quasiparticle identity and Fermi-surface data | SYK-like non-quasiparticle metals; fractionalization; topological order |
| Luttinger/filling continuity | Charge filling and momentum-space count across low-energy descriptions | An anomaly/filling constraint, sometimes without quasiparticles | Broken U(1) or translation assumptions; FL* topological sectors; generalized rather than conventional count |
| Current continuity | Divergence of a specified Noether current | Classical axial-current conservation for a massless theory | The quantum axial anomaly adds a term; the vector current is a different symmetry |
| Lattice-to-continuum continuity | A local lattice regulator approaching a chiral continuum theory | Low-momentum dispersion, locality, symmetries, species count | Nielsen–Ninomiya doubling; a premise must be relaxed |
| Continuous state-manifold dynamics | A path through a Gaussian or variational state family | Group-orbit geometry, metric, symplectic form, projected dynamics | Leaving Gaussian closure; non-Kähler manifolds split some projection principles |

The common vocabulary—symmetry, topology, anomaly, and continuous
deformation—does not make these rows interchangeable. In particular:

- the Luttinger/filling `'t Hooft` anomaly is not the ABJ axial anomaly;
- changing interaction strength adiabatically is not taking lattice spacing
  to zero;
- a momentum-space filling count is not a local current-divergence equation;
- Gaussian group evolution is a fifth geometric usage, not an extension of
  the other four physical statements.

### 2.1 Adiabatic continuity is not the modern invariant core

Landau's picture organizes an ordinary Fermi liquid by adiabatically connecting
it to free fermions and retaining long-lived quasiparticles. The modern
“ersatz Fermi liquid” result instead derives filling constraints from emergent
symmetry and a `'t Hooft` anomaly. Under unbroken charge conservation and
lattice translation, compressible low-energy theories require a very large
emergent symmetry; this can preserve a generalized Luttinger relation and
quantum oscillations even when quasiparticles are absent.

This is a different, more assumption-explicit organizing principle than
adiabatic continuity, but not an unconditional theorem about every strange
metal or a replacement for Landau theory in its valid regime. The framework's
“many, if not all” coverage remains a research claim, and superfluids evade the
premises by breaking U(1).

Primary source: [Else, Thorngren, and Senthil, PRX 2021](https://arxiv.org/abs/2007.07896).

### 2.2 Explicit non-adiabatic examples retain or modify different constraints

- The solvable SYK example has no quasiparticles and exhibits Planckian
  relaxation, yet a generalized density relation still fixes the particle-hole
  asymmetry of its Green function. It separates “no adiabatic quasiparticle
  continuity” from “no Luttinger-type constraint.”
- In an FL* phase, topological order and fractionalized spinons permit a small
  Fermi surface without ordinary symmetry breaking. This is a modification of
  the conventional Luttinger count, not a counterexample with unchanged
  premises. The FL*-style reading of CeCoIn5 is a theory-led interpretation of
  experiment, not a direct experimental measurement of topological order.
- A March 2026 exact-diagonalization preprint reports a Luttinger-count
  violation and a Luttinger-integral contribution in a fractional Chern
  insulator. It concerns a gapped fractionalized phase, not the conventional
  metallic Fermi-volume theorem, and remains single-preprint evidence.
- A disorder-driven universal Yukawa-SYK description of several metallic
  quantum transitions is a falsifiable mechanism proposal, not a settled
  unification of strange metals.

Key sources: [Sachdev's 2023 review](https://arxiv.org/abs/2305.01001),
[2024 metallic-transition lectures](https://arxiv.org/abs/2407.15919), and the
[2026 fractional-Chern-insulator preprint](https://arxiv.org/abs/2603.17006).

### 2.3 The axial anomaly is a quantum failure of a specific continuity equation

In 3+1 dimensions, the axial-current divergence contains both a mass term and
a gauge-field topological term. At zero mass, parallel electric and magnetic
fields can therefore produce nonzero axial divergence. Landau-level spectral
flow and a regulated triangle diagram give complementary derivations.

For the one-Dirac-fermion convention audited here,

`partial_mu J_A^mu = 2 i m bar(Psi) gamma_5 Psi +
(e^2 / 16 pi^2) epsilon^(mu nu rho sigma) F_(mu nu) F_(rho sigma)`.

The coefficient and sign must be rechecked when charges, generators, or tensor
conventions change.

This does not mean every fermion-number current is anomalous. The reviewed
quantitative statement is the axial anomaly with its specified current,
dimension, regulator, and convention. Stronger inherited claims about the
Wilson mass term and finite-lattice Ward identities were rejected.

Primary source: [Kaplan's chiral-fermion lectures](https://arxiv.org/abs/0912.2560).

### 2.4 Nielsen–Ninomiya is a premise boundary, not a ban on lattice fermions

Under the standard locality, translation, Hermiticity/reality, exact chiral
symmetry, and single-species continuum requirements, a lattice Dirac operator
cannot avoid doublers. Naive four-dimensional discretization produces sixteen
species. Successful formulations do not disprove the theorem; they alter a
premise.

Ginsparg–Wilson/overlap fermions replace the continuum anticommutation relation
with the lattice relation `{D, gamma_5} = a D gamma_5 D`. Proper local
overlap/Ginsparg–Wilson constructions can retain locality in the relevant
sense, reproduce the anomaly and lattice index theorem, and remove unwanted
doublers. Wilson, domain-wall, non-Hermitian, and interaction-enabled routes
likewise need to be classified by the premise they relax.

Primary sources: [Chandrasekharan and Wiese](https://arxiv.org/abs/hep-lat/0405024)
and [Kaplan](https://arxiv.org/abs/0912.2560).

### 2.5 Gaussian-manifold continuity is geometric, not another Luttinger theorem

Pure fermionic Gaussian states form orthogonal-group orbits that admit
covariance/complex-structure descriptions and local geometric optimization.
On Kähler variational manifolds, specified real-time projection principles
coincide; on non-Kähler manifolds they may diverge. Imaginary-time projection
can still define a Riemannian gradient flow with monotonic energy decrease.

The source proves a quantum variational geometry result. Calling it a machine-
learning natural gradient is a mathematical transfer until the probability
model, metric, and optimization domain are mapped directly. A centered state
can be represented by its complex structure `J`; a general bosonic Gaussian
state also requires displacement.

Key sources: [SciPost Physics 9, 048](https://scipost.org/SciPostPhys.9.4.048),
[SciPost Physics 10, 066](https://scipost.org/SciPostPhys.10.3.066), and
[SciPost Physics Core 4, 025](https://scipost.org/SciPostPhysCore.4.3.025).

## 3. Where fermionic structure is a computational lever

The evidence supports five recurring mechanisms. They are conditional tools,
not one complexity theorem.

1. **Algebraic closure:** quadratic fermionic dynamics preserve Gaussian
   states, allowing exponentially large state spaces to be represented through
   covariance matrices, determinants, and Pfaffians.
2. **Symmetry-local representation:** parity grading and antisymmetric ansätze
   encode signs once rather than repeatedly repairing them with nonlocal
   bookkeeping.
3. **Structured dependence:** determinant identities create repulsion,
   unbiasedness, or variance reduction for particular estimators.
4. **Resource parameterization:** departures from Gaussian closure can be
   isolated in a non-Gaussian extent or resource count.
5. **Hardware/algorithm co-design:** native fermionic operations can remove a
   software encoding primitive, while improved qubit mappings can sometimes
   remove the same asymptotic exponent.

Every efficiency comparison should report the same resource vector:

`(classical preprocessing and memory, online arithmetic or gate count,
parallel depth and topology, logical space, physical space-time, shots or
samples, classical post-processing, target error, amortized reuse)`.

Without this vector, “polynomial,” “constant depth,” and “no overhead” are not
comparable statements.

### 3.1 Comparative evidence matrix

| Cluster | Verified lever | Resource statement | Failure boundary | Evidence class |
|---|---|---|---|---|
| Matchgates and Gaussian shadows | Discrete Clifford matchgates reproduce the first three Haar moments of the continuous matchgate group; overlaps and local fermionic observables reduce to polynomial classical processing | Exponential post-processing can become polynomial; high-degree costs remain, although a June 2026 accepted workflow moves the engineering boundary | Not a 4-design; arbitrary non-Gaussian dynamics leave FLO simulation closure, although the shadow protocol still covers specified overlaps of arbitrary measured states with Gaussian references | Direct theorem plus peer-reviewed/accepted hardware workflows |
| Non-Gaussian simulation | Supplied Gaussian decompositions and FLO extent parameterize simulation beyond exactly Gaussian inputs | Polynomial factors times a resource term; maximal resource gates give a `2^k` factor | Extent can be exponential; finding an optimal decomposition is not generally free | Direct theorem, peer reviewed |
| Graded fermionic tensor networks | Z2 grading turns signs into block-level factors and keeps asymptotic contraction order equal to the bosonic/symmetric network | Minimal or subleading sign overhead; one fPEPS study reports a material expressivity gain over a JW-bosonized ansatz | Contraction remains hard; no universal speedup; direct graded-vs-JW end-to-end benchmarks remain sparse | Direct formalism, multiple papers; performance evidence narrower |
| Determinant/Pfaffian neural states | Exact antisymmetry is built into the ansatz; Pfaffians strictly contain Slater determinants in the stated construction | Determinant and Pfaffian evaluation remain `O(N^3)`; gains come from expressivity, forward Laplacians, and pretraining | Subcubic representability theorems do not yet supply a practical general replacement; benchmark gains are task and training dependent | Direct electronic-structure ML evidence; some single-team benchmarks |
| DPPs and negative dependence | Volume/determinant sampling yields exact unbiasedness or loss identities; selected OPE DPPs improve coreset or variance rates | Dense exact sampling has `O(N^3)` preprocessing; low-rank/amortized methods move rather than erase cost | Kernel construction, dimension, regularity, preprocessing, and estimator choice matter; sampling tractability does not make MAP easy | Direct classical statistics/ML theorem; physical-causation claim rejected |
| Gaussian manifold optimization | Group geometry gives efficient local gradients and structured projected dynamics | Local differentiable optimization on a constrained state family | No global optimum or polynomial convergence guarantee; ML-natural-gradient identification is transferred, not direct | Direct quantum geometry; ML mapping inferred |
| Encodings and native hardware | HATT reduces benchmark constants; native atoms remove selected JW strings; dynamic JW removes an interaction-count exponent for fixed-range pairwise terms | Classical HATT preprocessing `O(N^3)`; native layers, CNOT layers, and lattice-surgery rounds use different units | Connectivity, movement, control, error correction, constants, and high-body/dense interactions remain | Mixed: peer-reviewed compiler/proposal, 2026 preprint, component experiments |

Key sources for the first two rows: [matchgate shadows](https://link.springer.com/article/10.1007/s00220-023-04844-0),
[Gaussian extent simulation](https://quantum-journal.org/papers/q-2024-05-21-1350/),
and [phase-sensitive FLO simulation](https://quantum-journal.org/papers/q-2024-12-04-1549/).

### 3.2 Gaussian closure is tractability, not quantum advantage

Matchgate/FLO circuits are valuable precisely because their fermionic Gaussian
structure is classically compressible. The matchgate 3-design and shadow
results let a discrete, efficiently sampled circuit family replace continuous
randomization for the specified low moments. In QC-AFQMC this removes an
exponential classical post-processing step, but the remaining high-degree
polynomial can still be prohibitive.

Adding non-Gaussian resources changes the picture quantitatively. The reviewed
algorithms scale with a supplied Gaussian decomposition or FLO extent. For
maximal controlled-phase resources, the resource factor is `2^k`; the reported
`4.5^k` is an improvement ratio over a previous exponent, not the new runtime.
This is a controlled boundary between tractable and universal behavior, not a
claim that all interacting fermions are easy.

A post-ledger paper accepted by Physical Review Research demonstrates a larger
hybrid QC-AFQMC workflow using 16 data qubits plus 8 leakage-detection ancillas.
It reports a `9x` tuned Forte circuit-throughput improvement and a `656x`
normalized classical post-processing estimate. Three reviewers verified the
numbers only with strict boundaries: `9x` is a `9.9 s` to `1.1 s` per-circuit
control-stack result, while `656x` extrapolates a four-qubit prior kernel to
sixteen qubits and converts GPU to CPU-equivalent time. Neither is a measured
same-task end-to-end quantum speedup. QPU reaction barriers remain about
10 kcal/mol from the frozen-core CCSD(T) reference and reverse the reported
relative ordering. The result is a real systems-engineering milestone, not
chemical accuracy or quantum advantage.

Update sources: [APS accepted paper](https://journals.aps.org/prresearch/accepted/10.1103/n1tf-8kr7)
and [arXiv:2506.22408](https://arxiv.org/abs/2506.22408).

### 3.3 Tensor signs can be localized without solving tensor contraction

Grassmann/Z2-graded formulations encode parity in block structure, arrows, or
local ordering. Sign changes then act on whole blocks and do not change the
leading contraction complexity relative to a corresponding bosonic tensor
network. This is an important engineering result: antisymmetry need not be an
extra asymptotic burden.

It does not make PEPS contraction polynomial. Nor does it prove that every
graded implementation beats a Jordan–Wigner-first implementation. A reported
fPEPS advantage on a fermionic lattice problem supports an expressivity claim,
but comes from a limited benchmark and one research line.

Key sources: [graded tensor networks](https://arxiv.org/abs/2404.14611),
[arbitrary-geometry contractions](https://arxiv.org/abs/2410.02215), and the
[fPEPS VMC study](https://arxiv.org/abs/2506.20106).

### 3.4 Antisymmetric neural states trade cubic algebra for correct bias

Slater determinants and Pfaffians enforce exchange antisymmetry exactly.
Neural Pfaffian enlarges the determinant family and removes a discrete orbital-
selection restriction, while retaining `O(N^3)` asymptotic algebra. Forward
Laplacian attacks a separate automatic-differentiation bottleneck, and
pretrained transferable wavefunctions reduce optimization work at specified
accuracy points. These are orthogonal improvements, not evidence that the
cubic antisymmetrization cost has vanished.

The May 2026 WF-Bench scaling laws are useful diagnostics but remain single-
preprint, optimizer-dependent observations. A formal `O(N^2)` pairwise
representability construction is an existence/expressivity result, not a
validated practical replacement for determinant-based neural wavefunctions.

Key sources: [Forward Laplacian](https://www.nature.com/articles/s42256-024-00794-x),
[Neural Pfaffian](https://arxiv.org/abs/2405.14762),
[transferable wavefunctions](https://www.nature.com/articles/s41467-023-44216-9),
and [WF-Bench](https://arxiv.org/abs/2605.29683).

### 3.5 DPP gains are estimator- and kernel-specific

Determinantal sampling supplies some of the cleanest classical statistical
gains in the review: exact unbiased least-squares estimators, exact expected-
loss identities under stated conditions, near-optimal random-design sample
sizes, and conditional coreset/variance improvements. These gains arise from
the determinant sampling design and negative dependence.

They are not universal dominance results. The coreset exponent gain shrinks as
`1/d`; the Monte Carlo and SGD results require specified OPE kernels,
regularity, and estimator objects; exact dense sampling begins with an
`O(N^3)` eigendecomposition; and MAP remains NP-hard. The SGD object is a
gradient estimator, not a scalar loss estimator. Free/quasi-free fermion point
processes give the physical historical connection, but physical fermions do
not cause the classical ML theorem.

The practical discrete-DPP gradient estimator is unbiased. Its strongest
reported `O_P(m^(-(1+1/d)))` variance rate is proved first for a smoothed
theoretical estimator; transferring that rate to the practical discrete
sampler uses a spectral approximation whose rigor is qualified in the original
appendix. This proof-status reservation remains open in the final evidence.

Key sources: [NeurIPS 2024 DPP coresets](https://proceedings.neurips.cc/paper_files/paper/2024/hash/997089469acbeb410405e43f0011be1f-Abstract-Conference.html),
[JMLR 2018 volume sampling](https://jmlr.org/papers/v19/17-781.html),
[JMLR 2022 random-design regression](https://www.jmlr.org/papers/v23/19-571.html),
and [Kulesza and Taskar's DPP monograph](https://www.nowpublishers.com/article/Details/MAL-044).

## 4. Direct application, mathematical transfer, and analogy

| Classification | Supported examples | What may be said | What may not be said |
|---|---|---|---|
| `DIRECT` | Electronic wavefunctions using determinant/Pfaffian ansätze; fermionic tensor networks; matchgate simulation; native fermionic gates; DPP estimators as classical statistics/ML results | The stated target is treated directly, with its fermionic or determinant structure explicit | Direct structure alone guarantees speedup or accuracy on every instance |
| `MATHEMATICAL TRANSFER` | The free-fermion/DPP connection used to interpret classical ML; Clifford-resource algorithms adapted to FLO; Riemannian gradient language | The same determinant, negative-dependence, decomposition, or geometric template is reused in another domain | The complete physical/resource theories are isomorphic, or a physical fermion is necessary |
| `ANALOGY / UNSUPPORTED CAUSATION` | “Pauli exclusion causes AI diversity,” “fermion continuity is a universal optimizer,” “physical fermionic hardware improves classical ML” | It may motivate a hypothesis if labeled as analogy | It may not enter the findings as established evidence |

The correct cross-domain synthesis is therefore structural: a matched
representation can compress bookkeeping or impose a useful inductive bias.
It is not a causal claim that fermionic matter supplies a generic AI resource.
The DPP theorems themselves are direct classical statistics/ML results; only
their attribution to physical fermions is a mathematical transfer.

## 5. Encoding and native-hardware frontier as of July 2026

| Stage | What is established | What is not established |
|---|---|---|
| HATT / HPCA 2025 | Peer-reviewed benchmark reductions in Pauli weight, compiled CNOTs, and depth; `O(N^3)` classical mapping construction; one four-mode H2 IonQ run | General approximation ratio, hardware-independent percentages, or a causal scalable noise advantage |
| PNAS 2023 native-atom blueprint | Hardware fermionic statistics can remove specified JW strings; exact system-size-independent-depth native subroutines | Integrated processor, physical wall-clock comparison, or error-corrected application advantage |
| Dynamic JW, May 2026 v1 | For fixed-range pairwise 2D interactions, one logical qubit per mode and `O(N)` two-qubit gates; architecture-dependent logical depth | Peer review, hardware execution, dense/high-body generality, or equal physical space-time to native hardware |
| Nature 2026 component experiment | Fermionic lithium-6 collisional spin-entangling gates up to `99.75(6)%` from a repeated-pulse fit; long-lived Bell states; pair-tunneling and a small separate composite pair-exchange demonstration | Integrated local addressing, full proposed gate stack, end-to-end algorithm, or pair-exchange fidelity equal to the spin-gate number |
| PRL 2026 tweezer experiment | Programmable `8 x 8` product-state preparation above `98.5%` motional-ground-state fidelity and resolved readout | Entangling gate or end-to-end processor in the same experiment |
| PRL 2025 error-correction blueprint | A phase-error-focused logical-fermion construction and minimal numerical example | Experimental error-corrected processor or a full fault model |

The native advantage has not vanished, but its location has moved. The May
2026 qubit construction removes the interaction-count exponent and can match
the native depth exponent in a lattice-surgery logical model. Remaining
questions concern constants, physical qubits, code cycles, movement, local
addressing, control error, and application-level performance.

Key sources: [HATT](https://arxiv.org/abs/2409.02010),
[PNAS native processor](https://doi.org/10.1073/pnas.2304294120),
[dynamic JW](https://arxiv.org/abs/2605.12600),
[Nature 2026 gates](https://www.nature.com/articles/s41586-026-10356-3),
[PRL 2026 arrays](https://journals.aps.org/prl/abstract/10.1103/fsmh-dz71), and
[PRL 2025 error correction](https://journals.aps.org/prl/abstract/10.1103/zkpl-hh28).

## 6. Evidence maturity and source dependence

| Tier | Suitable use | Main clusters |
|---|---|---|
| A — established theorem/formalism | State as a finding with its assumptions | Nielsen–Ninomiya, axial anomaly, Ginsparg–Wilson, matchgate 3-design, Gaussian resource algorithms, core DPP identities, graded sign formalism |
| B — peer-reviewed but benchmark, proposal, or component dependent | State as a reported result, not a universal law or integrated system | HATT percentages, native PNAS architecture, Neural Pfaffian benchmarks, transferable wavefunctions, fPEPS example, Nature/PRL component experiments |
| C — frontier preprint or system-level extrapolation | Use as an update or testable direction | 2026 FCI count violation, dynamic JW v1, WF-Bench, integrated-native-processor outlook |

Peer review and independence are distinct. Important dependency clusters are:

- the ersatz-Fermi-liquid core comes from one PRX theory line, and several SYK,
  FL*, and strange-metal interpretations run through overlapping Sachdev-led
  work;
- the three Gaussian-geometry papers share Lucas Hackl and form one program;
- HATT and its Fermihedral comparator share three authors;
- several DPP survey and primary papers share authors and proof lineages;
- the 2025 error-correction paper is a continuation of the 2023 PNAS author
  line, with five of six authors in common;
- the two 2026 fermionic-atom experiments use different apparatus and
  demonstrate different components, but share Philipp Preiss and an
  institutional research line;
- the dynamic-JW and WF-Bench results are each single, unreviewed preprints.
- the accepted QC-AFQMC scale-up is a 41-author IonQ/AstraZeneca/NVIDIA/AWS
  collaboration, shares two authors with its 2024 baseline, and is not an
  independent replication or a neutral cost comparison.

Evidence updates should therefore record three axes independently: direct
support versus transfer/analogy; theorem versus numerical, component, or
end-to-end experiment; and same-line evidence versus independent corroboration
or replication.

## 7. Conclusions that the evidence forbids

The following statements should not appear in downstream summaries without
being explicitly marked false, refuted as written, or speculative:

1. All uses of “fermion continuity” are one physical conservation law.
2. Every non-Fermi liquid violates every Luttinger-type relation.
3. Every fermion current has an axial anomaly.
4. Nielsen–Ninomiya forbids useful lattice chiral fermions rather than forcing
   a premise tradeoff.
5. Matchgate classical simulability is itself a quantum computational
   advantage.
6. Fermionic magic and stabilizer magic resource theories are proved
   isomorphic.
7. Graded tensor signs or determinant ansätze automatically accelerate an
   arbitrary non-fermionic problem.
8. DPPs are the unique tractable negatively dependent family, or exact DPP
   sampling implies tractable DPP MAP.
9. A DPP gradient estimator is a scalar loss/coreset estimator.
10. Physical fermions cause DPP or neural-network gains on classical hardware.
11. Riemannian imaginary-time flow is already a direct ML natural-gradient
    application.
12. The HATT H2 run proves a general noise-resistance benefit.
13. The PNAS native subroutines use five total elementary gates.
14. “Zero space overhead” in the dynamic-JW paper includes surface-code
    physical qubits and lattice-surgery ancillas.
15. The 2026 experiments already constitute a fully programmable,
    error-corrected native fermionic processor.
16. The QC-AFQMC `9x` or `656x` numbers prove a same-task, end-to-end quantum
    speedup.

## 8. Highest-value next research program

The next phase should compare complete resource models and seek falsifiable
cross-paper tests rather than collect more isolated percentage claims.

| Priority | Research question | Minimal decisive deliverable | Success criterion |
|---:|---|---|---|
| 1 | Does native fermionic hardware retain an end-to-end advantage after dynamic encodings and error correction? | Matched Hubbard or lattice-gauge workload on native and qubit architectures, with logical-to-physical resource estimates | Report wall-clock, space-time volume, movement, connectivity, fidelity, and error-correction cost under the same target error |
| 2 | Can the demonstrated 2026 components form a programmable native processor? | Integrate array preparation, local addressing, fermionic entangling/pair gates, and resolved readout in one device | Execute a small digital fermionic algorithm and compare against a classically verified result without postselecting away the central failure mode |
| 3 | Does the QC-AFQMC quantum trial state improve the same task at matched error and total cost? | Compare the QPU trial against classical pCCD, multi-Slater, and MPS trials on one molecule and active space | Include QPU sampling, GPU post-processing, phaseless bias, error mitigation, wall-clock, and statistical error in one A/B resource table |
| 4 | Where is the practical non-Gaussian simulability transition? | Compute or tightly bound Gaussian/FLO extent for physically motivated interacting-state families | Identify size/resource regimes where the `2^k` method beats generic simulation and where decomposition cost becomes dominant |
| 5 | When do DPP statistical gains survive end-to-end cost? | Benchmark matched DPP and independent estimators on real high-dimensional tasks, including kernel construction and amortization | Demonstrate lower total compute at matched error, not only a better asymptotic estimator exponent |
| 6 | Is graded-local fermionic tensor software better than JW-first software in practice? | Same contraction path, symmetry content, hardware, and accuracy across both pipelines | Measure memory, time, sign-handling overhead, and numerical stability across planar and non-planar networks |
| 7 | Can Gaussian quantum geometry become a direct ML method? | Explicitly map a probabilistic model's Fisher metric and objective to the Gaussian-manifold metric and flow | Prove equivalence under stated conditions or exhibit a counterexample; then compare convergence on a matched task |
| 8 | How broad is the ersatz-Fermi-liquid framework? | Catalogue candidate non-Fermi liquids by U(1), translation, emergent symmetry, anomaly, and topological sector | Produce clear falsifiers and identify systems that cannot be absorbed by merely modifying the Luttinger count |

## 9. Final answer

The physical side of the investigation supports a family of sharply bounded
continuity statements. Adiabatic quasiparticle continuity can fail while an
anomaly-protected filling constraint persists; topological order can modify
the conventional count; a quantum anomaly can break a classical current
continuity equation; and a chiral, doubler-free lattice regulator can reach the
desired continuum only by relaxing a no-go premise. Gaussian-state continuity
is a separate geometric statement about paths inside a variational family.

The computational side supports an equally bounded conclusion. Fermionic
structure is useful when it closes the algebra, localizes signs, matches an
antisymmetric target, creates a determinant identity, or removes a specific
encoding primitive. It is costly when interactions and non-Gaussianity break
closure, when the determinant kernel or decomposition must be built, when a
high polynomial dominates, or when logical asymptotics hide physical
space-time.

The durable cross-domain thesis is therefore:

> Fermionic structure is a representation and constraint lever, not a
> universal advantage. Its benefit is real only when the target symmetry, the
> algorithmic representation, and the resource accounting are matched.

This thesis is supported by the reviewed evidence. A universal “fermionic AI
advantage” or single “fermion continuity law” is not.
