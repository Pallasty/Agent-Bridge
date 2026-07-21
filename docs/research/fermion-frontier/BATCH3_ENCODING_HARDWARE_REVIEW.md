# Batch 3 review: fermion-to-qubit encoding and native hardware

Review date: 2026-07-11

Cluster input: inherited ledger indices 40–54

Method: three independent reviewers audited the same 15 claims against the
primary papers, with resource units, connectivity, preprocessing, publication
status, and experimental maturity normalized before synthesis.

Full reviewer packets:

- [review A](reviews/encoding-vote-a.md)
- [review B](reviews/encoding-vote-b.md)
- [review C](reviews/encoding-vote-c.md)

## Verdict

| Outcome | Count | Claims |
|---|---:|---|
| Fully verified, with mandatory boundaries | 12 | 40–42, 44–45, 47–53 |
| Verified core after partial rewrite | 2 | 43, 54 |
| Refuted as written | 1 | 46 |
| No verified component | 0 | — |

Claim 46 is refuted unanimously. It converts a circuit-depth statement into a
total-gate-count statement: the PNAS source supports exact, constant-depth
native-gate decompositions, but the number five denotes native-gate layers,
not five total elementary gates in both circuits.

Claim 43 passed 2–1 only after deleting its causal conclusion and replacing it
with a single-instance observation. The IonQ run does not establish that
Pauli-weight optimization generally causes noise resistance. Claim 54 passed with one
proof-status reservation: the construction and comparison upper bounds are
direct, but its gate-count-optimality component remains unverified without an
explicit lower-bound argument. These are accepted corrected cores, not full
endorsements of the inherited compound sentences.

## Vote matrix

`P` = pass, `R` = refute, `U` = unverified. A verified claim has three valid
independent reviews and fewer than two refutations.

| Ledger | Source | A | B | C | Consensus | Required boundary |
|---:|---|:---:|:---:|:---:|---|---|
| 40 | HATT / HPCA 2025 | P | P | P | VERIFIED | Benchmark averages under specified Hamiltonians, compiler chains, baselines, and coupling graphs; not a per-instance or hardware-independent guarantee. |
| 41 | HATT / HPCA 2025 | P | P | P | VERIFIED | `O(N^3)` is Hamiltonian-specific classical mapping construction, with the paper's Pauli-weight-cost convention; it is not quantum circuit depth. |
| 42 | HATT / HPCA 2025 | P | P | P | VERIFIED | “Close to optimal” and SAT scalability are empirical benchmark findings, not an approximation-ratio theorem or a universal solver threshold. |
| 43 | HATT / HPCA 2025 | P | R | P | OBSERVATION VERIFIED 2–1; CAUSAL CLAUSE REMOVED | Four-mode H2, one IonQ Forte 1 device, and 1,000 shots. The paper-reported shot-energy dispersion/variance does not establish a general or causal noise advantage. |
| 44 | HATT / HPCA 2025 | P | P | P | VERIFIED | HPCA 2025 publication status is confirmed; conference standing does not expand the scope of the resource evidence. |
| 45 | PNAS 2023 | P | P | P | VERIFIED | `L` is modes/traps; the native constant-depth comparison assumes the proposed gate set, rearrangement, and parallelism and excludes physical transport time and error correction. |
| 46 | PNAS 2023 | R | R | R | REFUTED | Density-dependent tunneling uses four sequential native-gate factors; pair-tunneling uses five layers, some with parallel gates. These are not five total elementary gates or a global optimum across gate sets. |
| 47 | PNAS 2023 | P | P | P | VERIFIED | Hardware statistics remove the specified Jordan–Wigner strings only if indistinguishability, motional ground states, and coherent merge/shuttle operations are maintained. |
| 48 | PNAS 2023 | P | P | P | VERIFIED | Prior experiments implement an essentially equivalent Rydberg entangler and related components, not the paper's integrated fermionic register and full gate stack. |
| 49 | PNAS 2023 | P | P | P | VERIFIED | LiH and lattice-gauge-theory results are numerical/circuit examples; the larger-molecule scaling advantage is a forecast. |
| 50 | arXiv:2605.12600v1 | P | P | P | VERIFIED | Fixed-range geometrically local pairwise interactions, with one logical qubit per fermionic mode; not arbitrary high-body/dense interactions or zero fault-tolerant physical space. |
| 51 | arXiv:2605.12600v1 | P | P | P | VERIFIED | `O(sqrt(N))`, `O(log N)`, and `O(1)` use different connectivity and logical-operation models; constant logical lattice-surgery/Clifford-round depth hides code distance and auxiliary patches. |
| 52 | arXiv:2605.12600v1 | P | P | P | VERIFIED | The interaction-count exponent is removed; only logical-depth scaling matches native hardware in the stated lattice-surgery cost model. Physical space-time and constants are not equated. |
| 53 | arXiv:2605.12600v1 | P | P | P | VERIFIED | Leading-order CNOT counts/depth for the stated spinful second-order Trotter accounting; crossover sizes are implementation- and baseline-specific. |
| 54 | arXiv:2605.12600v1 | P | U | P | UPPER BOUNDS VERIFIED 2–0–1; GATE-COUNT OPTIMALITY UNVERIFIED | The FFFT upper bounds and tabulated comparisons are direct. Retain local-connectivity assumptions and state depth optimality separately from the unverified gate-count lower bound. |

## Normalized resource model

| Work | Size variable | Count/depth unit | Hidden or separate cost | Maturity |
|---|---|---|---|---|
| HATT | `N = fermionic modes = mapped qubits` | Pauli weight; compiled CNOT count and logical depth | `O(N^3)` classical, Hamiltonian-specific preprocessing; compiler and topology dependence | Peer-reviewed HPCA paper; one four-qubit H2 hardware example |
| PNAS native processor | `L = modes/traps`; `N = atoms`, generally `N <= L` | Layers of high-level native fermionic tunneling/interaction gates | Tweezer movement, motional control, cooling, leakage, calibration, and error correction | Peer-reviewed architecture proposal with prior component experiments |
| Dynamic JW | `N = fermionic modes = logical qubits`; spinful spatial sites contribute multiple modes | Two-qubit Clifford/CNOT count and logical circuit or measurement-round depth | Connectivity, surface-code physical qubits, auxiliary logical patches, code cycles, and feed-forward | May 2026 theoretical arXiv v1; no hardware experiment or peer review |

These units are not interchangeable. A native fermionic gate layer, a compiled
CNOT layer, and a surface-code measurement round can have the same asymptotic
depth while carrying very different physical time and space costs.

## Corrected findings

### 1. Hamiltonian-adaptive mappings give conditional constant-factor gains

HATT reports material Pauli-weight, CNOT-count, and depth reductions across its
electronic-structure, Hubbard, and neutrino benchmarks. Its caching and
candidate-selection changes reduce the classical construction from `O(N^4)`
to `O(N^3)` while retaining vacuum preservation. The percentages remain
benchmark, compiler, and topology dependent; HATT has no general
approximation-ratio guarantee against the SAT optimum.

Primary source: [HATT / HPCA 2025](https://arxiv.org/abs/2409.02010), the
[formal proceedings DOI](https://doi.org/10.1109/HPCA61900.2025.00022), and the
[official HPCA program](https://hpca-conf.org/2025/main-program/).

### 2. The available HATT hardware evidence is a small observation

On a four-mode H2 task with 1,000 shots on IonQ Forte 1, HATT produced the
smallest paper-reported shot-energy dispersion/variance and the second-closest
mean. One reviewer
correctly noted that HATT and Jordan–Wigner have identical Pauli weight, CNOT
count, and depth in that instance. The run therefore cannot identify
Pauli-weight reduction as the cause of the variance or establish a scalable
noise advantage.

### 3. Native fermionic statistics remove specified parity strings, not all cost

The PNAS architecture stores modes in indistinguishable fermionic atoms and
directly implements tunneling and interaction primitives. Under its native
gate and rearrangement model, this removes the `O(L)` Jordan–Wigner string for
a general long-range tunneling gate. It does not remove motion, cooling,
control, leakage, calibration, algorithmic, or error-correction costs.

Its pair-tunneling and density-dependent-tunneling subroutines have exact,
system-size-independent-depth decompositions. Density-dependent tunneling has
four sequential native-gate factors; pair-tunneling has five layers, some of
which contain parallel gates. The inherited “five total gates” wording is
therefore wrong. The paper's optimality language is tied to its native gate set
and construction, not a global lower bound across gate sets.

Primary source: [PNAS 2023](https://doi.org/10.1073/pnas.2304294120).

### 4. Dynamic Jordan–Wigner narrows the asymptotic native-hardware claim

For fixed-range pairwise interactions on a two-dimensional lattice, the May
2026 construction uses one qubit per fermionic mode and `O(N)` two-qubit gates,
matching the native processor's interaction-count exponent. The remaining
logical-depth cost is architecture dependent: `O(sqrt(N))` on a local 2D qubit
grid, `O(log N)` with the assumed row/column nonlocal connectivity, and `O(1)`
logical lattice-surgery/Clifford-round depth.

The last line does not prove end-to-end equivalence to native fermionic
hardware. Surface-code physical space-time, auxiliary patches, constants, and
native-gate implementation remain outside that asymptotic comparison. The
paper is an unreviewed v1 theoretical result.

Primary source: [arXiv:2605.12600v1](https://arxiv.org/abs/2605.12600).

### 5. The 2026 experimental frontier has advanced beyond the 2023 component baseline

The inherited PNAS claim described the experimental state in 2023. By the
review date, two separate 2026 experiments materially strengthen component
maturity:

- a Nature experiment with fermionic lithium-6 atoms demonstrated a
  collisional spin-entangling `sqrt(SWAP)` gate with fidelity up to
  `99.75(6)%` from a repeated-pulse fit and Bell-state lifetimes above 10
  seconds. It separately characterized pair-tunneling and a composite
  pair-exchange primitive; the latter's small post-selected analysis is not a
  `99.75(6)%` gate-fidelity result;
- a Physical Review Letters experiment demonstrated programmable preparation
  of an `8 x 8` lithium-6 tweezer array with motional-ground-state fidelity
  above `98.5%`, plus spin-, site-, and density-resolved readout. It is a
  product-state preparation/readout result, not an entangling-gate or
  end-to-end algorithm experiment.

Together these show gates on fermionic atoms, fermion-specific
pair-tunneling/pair-exchange primitives, and fermionic state preparation and
readout. They still do not constitute an integrated, end-to-end programmable
native fermionic processor demonstrating the PNAS resource advantage. Local
addressing was not integrated in the Nature experiment; the authors identify
combining it with these gates as a route toward full digital integration. A
2025 PRL error-correction paper likewise remains a blueprint focused on phase
errors and a minimal numerical circuit.

Primary sources: [Nature 2026 gates](https://www.nature.com/articles/s41586-026-10356-3),
[PRL 2026 array preparation/readout](https://journals.aps.org/prl/abstract/10.1103/fsmh-dz71),
and [PRL 2025 error-correction blueprint](https://journals.aps.org/prl/abstract/10.1103/zkpl-hh28).

## Source-independence audit

The three votes are independent audits, but the evidence is not threefold
replication:

- all HATT performance numbers come from one team, and HATT shares three
  authors with the Fermihedral baseline paper;
- the PNAS architecture, resource analysis, LiH example, and LGT example are
  one paper; earlier Rydberg work validates related components rather than the
  integrated processor;
- the 2025 PRL error-correction blueprint is a direct continuation of the PNAS
  author line: five of its six authors also appear on the 2023 paper. It is not
  an independent validation of that architecture;
- every dynamic-JW result comes from one Innsbruck/Parity Quantum preprint,
  including its comparisons against prior methods;
- the two 2026 experiments use different apparatus and demonstrate different
  components, but share Philipp Preiss and an institutional research line;
  they are not independent replications of each other or of the full PNAS
  stack.

## Program consequence

“Native fermions eliminate encoding overhead” is too broad. The defensible
statement is cost-model dependent: native statistics can remove parity-string
and mode-encoding work for matched primitives, while improved qubit encodings
can eliminate the interaction-count exponent and, under a fault-tolerant
logical model, the depth exponent as well. What remains to compare is physical
space-time volume, constants, connectivity, motion and control error,
fault-tolerance overhead, and end-to-end application performance. Those are the
highest-value targets for the final synthesis and future experiments.
