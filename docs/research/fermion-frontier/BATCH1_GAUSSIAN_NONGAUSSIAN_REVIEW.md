# Batch 1 review: Gaussian geometry and non-Gaussian resources

Review date: 2026-07-11

Input: inherited ledger indices 25–39 and 60–69

Method: three independent reviewers, primary sources only

Full reviewer packets:

- `reviews/vote-a.md`
- `reviews/vote-b.md`
- `reviews/vote-c.md`

## Verdict

| Outcome | Count |
|---|---:|
| Verified | 22 |
| Refuted as written | 3 |
| Unverified | 0 |

The refuted claims are 27, 63, and 65. Each contains a supportable core, but
the inherited wording crosses a material boundary. Corrected replacements are
recorded below rather than silently editing the preserved input ledger.

## Vote matrix

`P` = pass, `R` = refute, `U` = unverified. A verified claim has three valid
votes and fewer than two refutations.

| Ledger | Source | A | B | C | Consensus | Required boundary |
|---:|---|:---:|:---:|:---:|---|---|
| 25 | Quantum 8, 1350 | P | P | P | VERIFIED | Efficient only when a suitable Gaussian decomposition or bound is available; extent may be exponential. |
| 26 | Quantum 8, 1350 | P | P | P | VERIFIED | Applies to operations with a resource-state gadget, not arbitrary black-box non-Gaussian gates. |
| 27 | Quantum 8, 1350 | P* | R | R | REFUTED | Algorithm templates transfer; the two resource theories were not proved isomorphic. |
| 28 | Quantum 8, 1350 | P | P | P | VERIFIED | Tracks relative phases in Gaussian superpositions; not arbitrary non-Gaussian states. |
| 29 | Quantum 8, 1350 | P | P | P | VERIFIED | “Four modes,” not four particles; the general multiplicativity problem remains open. |
| 30 | Quantum 8, 1549 | P | P | P | VERIFIED | Additive-error Born-probability estimation with model and parity assumptions; not a universal exact sampler. |
| 31 | Quantum 8, 1549 | P | P | P | VERIFIED | Each maximal resource gate doubles the extent factor; total time is `poly(...) * 2^k`. |
| 32 | Quantum 8, 1549 | P | P | P | VERIFIED | `4.5^k` is the improvement ratio over the prior method, not the new runtime. |
| 33 | Quantum 8, 1549 | P | P | P | VERIFIED | The phase-sensitive statevector decomposition is the mechanism. |
| 34 | Quantum 8, 1549 | P | P | P | VERIFIED | Peer-reviewed publication metadata confirmed. |
| 35 | SciPost Phys. 10, 066 | P | P | P | VERIFIED | Local differentiable optimization; no global optimum or polynomial-convergence guarantee. |
| 36 | SciPost Phys. 10, 066 | P | P | P | VERIFIED | Distinguish full `O(2N)` structure from the connected fixed-parity `SO(2N)` branch. |
| 37 | SciPost Phys. 10, 066 | P | P | P | VERIFIED | Explicit conversion between Gaussian-state parameterizations. |
| 38 | SciPost Phys. 10, 066 | P | P | P | VERIFIED | Demonstrated Gaussian applications, not general exact quantum algorithms. |
| 39 | SciPost Phys. 10, 066 | P | P | P | VERIFIED | Gaussian purification optimality remains a conjecture. |
| 60 | SciPost Phys. 9, 048 | P | P | P | VERIFIED | A geometric framework for closed-system variational families, not one universal numerical method. |
| 61 | SciPost Phys. 9, 048 | P | P | R | VERIFIED 2–1 | Kähler structure controls equivalence of real-time variational projections; it is not a gate on all continuous optimization. |
| 62 | SciPost Phys. 9, 048 | P | P | P | VERIFIED | The projected variational prescriptions diverge; the exact Schrödinger equation is not ambiguous. |
| 63 | SciPost Phys. 9, 048 | U | R | R | REFUTED | Riemannian gradient flow is direct; equivalence to ML natural gradient is our mathematical transfer. |
| 64 | SciPost Phys. 9, 048 | P | P | P | VERIFIED | Local linearization near a stable approximate ground state; not an exact full-spectrum theorem. |
| 65 | SciPost Phys. Core 4, 025 | R | R | P | REFUTED | `J` alone characterizes centered states; a general bosonic Gaussian state also needs displacement `z`. |
| 66 | SciPost Phys. Core 4, 025 | R | P | P | VERIFIED 2–1 | Full structure group is `O(2N)`; continuous quadratic FLO is in `SO(2N)` and acts through Spin/Pin representations. |
| 67 | SciPost Phys. Core 4, 025 | P | P | P | VERIFIED | This is a bridge to companion optimization papers, not an independent re-proof. |
| 68 | SciPost Phys. Core 4, 025 | P | P | P | VERIFIED | Canonical metric/symplectic roles are reversed between fermions and bosons within the Gaussian framework. |
| 69 | SciPost Phys. Core 4, 025 | P | P | P | VERIFIED | Common `J`-form of information quantities is direct; labeling it “fermion continuity” is our interpretation. |

`P*` means the reviewer accepted the mathematical core but independently
required the same rewrite that the two refuting reviewers used to reject the
original compound wording.

## Corrected findings

### 1. Non-Gaussianity is a resource-parameter boundary

Fermionic linear-optical circuits remain classically simulable beyond exactly
Gaussian inputs when the input or resource state has a supplied low-rank
Gaussian decomposition or bounded Gaussian/FLO extent. The algorithms are
polynomial in ordinary circuit and accuracy parameters and parameterized by
the non-Gaussian resource measure. This is not unconditional efficiency:
finding an optimal decomposition is outside the first paper's guarantee, and
the extent can itself grow exponentially.

Primary sources: [Quantum 8, 1350](https://quantum-journal.org/papers/q-2024-05-21-1350/)
and [Quantum 8, 1549](https://quantum-journal.org/papers/q-2024-12-04-1549/).

### 2. The resource exponent, not circuit size alone, marks the break

For maximal controlled-phase resources, the newer simulation has a resource
factor `2^k`, multiplied by polynomial terms. The reported `4.5^k` is the
asymptotic improvement ratio against the prior approximately `9^k` resource
factor. It is neither the new algorithm's runtime nor an end-to-end measured
speedup.

### 3. The Clifford analogy is operational, not an isomorphism theorem

Several decomposition and sparsification algorithms from Clifford circuits
with non-stabilizer resources transfer to the fermionic-linear-optics setting.
The source calls the problems analogous and does not prove that the complete
resource theories are isomorphic.

### 4. Gaussian-state geometry supports local constrained optimization

Pure bosonic and fermionic Gaussian states form structured manifolds on which
geometric gradients can be evaluated efficiently using symplectic or
orthogonal group actions. The result is a local optimization method for
differentiable objectives, not a guarantee of global optimality.

Primary sources: [SciPost Phys. 10, 066](https://scipost.org/SciPostPhys.10.3.066),
[SciPost Phys. 9, 048](https://scipost.org/SciPostPhys.9.4.048), and
[SciPost Phys. Core 4, 025](https://scipost.org/SciPostPhysCore.4.3.025).

### 5. Kähler structure separates real-time projection rules

On Kähler variational manifolds, real-time Lagrangian and McLachlan-style
projected evolutions coincide under the relevant conditions. On non-Kähler
manifolds they need not. Imaginary-time evolution can still define a
Riemannian gradient flow on a real differentiable manifold, so non-Kähler does
not mean “continuous optimization fails.”

### 6. The ML natural-gradient connection is inferred

The quantum source directly proves the Riemannian gradient-flow equation and
monotonic energy decrease. It does not discuss Fisher information, Amari
natural gradient, or machine learning. Any ML connection must therefore be
classified as mathematical transfer until a direct mapping of metrics and
optimization domains is supplied.

### 7. Parameterization needs two group-level qualifications

- A centered Gaussian state can be described by a linear complex structure
  `J`; a general bosonic Gaussian state also needs displacement `z`.
- `O(2N)` describes the full fermionic Gaussian structure group, while
  continuous quadratic Hamiltonian evolution lies in the connected
  `SO(2N)` branch and is represented on Fock space through its double cover.

## Source-independence audit

All five sources are primary and peer reviewed. However, the three Gaussian
geometry papers share Lucas Hackl and explicitly describe themselves as
complementary parts of one research program. They are a coherent theory chain,
not three independent replications. The two Quantum papers have distinct
author groups and provide stronger independent convergence on the
non-Gaussian-resource boundary.

## Program consequence

The working thesis is strengthened but narrowed: Gaussian closure is a
classically tractable manifold, and non-Gaussianity is a quantitative resource
parameter controlling departure from it. This supports a precise boundary
claim. It does not support a generic “fermionic natural gradient for AI” claim.
