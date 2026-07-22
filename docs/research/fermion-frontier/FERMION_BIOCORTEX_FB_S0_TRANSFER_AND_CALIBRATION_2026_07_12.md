# Fermion × BioCortex FB-S0 mathematical transfer and interpretation calibration

Status date: 2026-07-12

Status: **P0 calibration complete; direct runtime integration rejected; temporal
residual scout held until its nominal model is scientifically repaired.**

Owning branch: `codex/fermion-biocortex-fb-s0-20260712`, based on the physical-
fermion research branch after commit `725b0a32`. This lane is independent of the
L=8 benchmark evidence manifest and of every BGL asset.

## Decision

The useful bridge is narrower than a shared solver:

| Proposed bridge | Decision | Reason |
|---|---|---|
| BioCortex as a fermionic state or circuit solver | `NO_GO` | BioCortex has no CAR, Majorana, Fock, parity-string, Pfaffian, Pauli or complex-amplitude semantics. |
| Shared falsification, direct-reduction and resource-accounting discipline | `GO` | Both programs benefit from exact controls, state/operation budgets, source custody and fail-closed claims. |
| HOI `C3` as a fermionic non-Gaussianity witness | `REFUTED` | A gauge-invariant quasifree Gaussian mixed-state occupation distribution can have `C3 > 0` against the classical binary pairwise-maximum-entropy family. |
| Fixed-workload temporal mapping controller | `NO_GO_CURRENT_WORKLOAD` | The current Hubbard interaction schedule is known offline; a full-lookahead direct optimizer has strictly more information than a temporal predictor. |
| Free-reference temporal residual calibration | `DESIGN_HOLD` | `U=0` is a legitimate free reference, but it is not a same-`U` Gaussian/Wick closure of the interacting Hamiltonian. |
| Future online dynamic-JW sidecar | `CONDITIONAL` | Reopen only for genuinely unknown, adaptive or measurement-conditioned future interactions. |

The result preserves the physical-fermion program's thesis: fermionic structure is
a conditional representation and constraint lever, not a generic neural-dynamics
advantage. It also preserves BioCortex's application-first rule: a mechanism earns
no credit when a direct mathematical reduction explains the result.

## P0: exact-margin Gaussian occupation counterexample

### Construction

For a gauge-invariant number-conserving fermionic Gaussian state, a one-body
correlation kernel `K` with `0 <= K <= I` defines occupation inclusion moments

\[
\Pr(S \subseteq X)=\det K_S.
\]

FB-S0 freezes two three-mode kernels with `p=1/2` and `r=6/25`:

\[
K_+=\begin{pmatrix}p&r&r\\r&p&r\\r&r&p\end{pmatrix},\qquad
K_-=\begin{pmatrix}p&r&-r\\r&p&r\\-r&r&p\end{pmatrix}.
\]

Their exact eigenvalues are

\[
\operatorname{eig}(K_+)=\{49/50,13/50,13/50\},\qquad
\operatorname{eig}(K_-)=\{37/50,37/50,1/50\},
\]

so both are valid gauge-invariant quasifree Gaussian mixed-state correlation
kernels. They are not fixed-particle-number pure Slater states; equivalently,
such kernels may occur as subsystem marginals of a larger pure Gaussian state.
They have identical
single-mode inclusions `1/2` and identical pair inclusions

\[
p^2-r^2=481/2500.
\]

Their three-mode inclusions differ because

\[
\det K_{123}
=p^3-3pr^2+2\operatorname{Re}(K_{12}K_{23}K_{31}),
\]

and the loop product changes sign. The exact values are `8281/125000` and
`1369/125000`. Thus pairwise occupation margins do not determine the third-order
occupation table even though both states remain Gaussian and Wick-reducible.

### Q2 result

The deterministic one-dimensional fibre solver constructs the classical binary
maximum-entropy `Q2` matching every single and pair margin. Both kernels produce
the same `Q2`, while their population divergences are:

| Kernel | `C3 = D_KL(P || Q2) / ln 2` |
|---|---:|
| `positive_loop` | `0.0533499393291` bits |
| `negative_loop` | `0.0533499393291` bits |

Therefore the supported interpretation is only:

> `C3` measures order-3 irreducibility relative to the declared classical binary
> pairwise-maximum-entropy family.

The following interpretation is refuted:

> `C3 > 0` is sufficient evidence of fermionic non-Gaussianity, beyond-Wick
> structure, a three-body Hamiltonian or a BioCortex mechanism.

The converse is also unavailable: `C3 = 0` does not prove Gaussianity.

### Fixed L=2 negative control

The same executable imports the already committed, source-pinned L=2 pilot and
runs the `U=0`, `T=1`, `R=8` quadratic product circuit from the checkerboard Néel
state. Every finite product of these quadratic gates remains a pure Slater/
fermionic-Gaussian state.

The calibration independently checks:

- state norm;
- Hermiticity, trace four and idempotence of the `8 x 8` one-body kernel;
- all size-one through size-three occupation moments against `det(K_S)`; and
- all `C(8,3)=56` triplets, without selecting a favourable triplet.

This particular fixture has maximum population `C3 = 0` within the frozen
`1e-12` tolerance. It is an honest negative control, not a contradiction: one
Gaussian fixture with `C3=0` cannot turn `C3` into a general Gaussianity test,
while the valid analytic kernels above already provide the counterexample.

## Correction to the proposed temporal residual scout

The initially proposed quantity

\[
r_U(t)=y_U(t)-y_{U=0}(t)
\]

is a **free-reference residual**. It removes the interaction term entirely and
therefore cannot be called a same-Hamiltonian Gaussian or non-Gaussian residual.
Executing it under the old name would confound interaction removal with departure
from a Gaussian closure.

Any later small calibration must either:

1. use the honest name `FB-S0_FREE_REFERENCE_RESIDUAL_CALIBRATION_V0` and claim
   only time-series extrapolation relative to that free reference; or
2. first freeze a same-`U` Gaussian approximation such as an independently
   reviewed TDHF/Wick-closure evolution, then test the residual against that
   nominal model.

Even the free-reference version remains blocked until it freezes an exact sector
solver, a time interval covering enough slow periods, prefix/purge boundaries,
held-out-`U` hyperparameter transfer, and equal budgets for Gaussian-only,
persistence, Ridge-VAR, DMD, Prony and direct modal controls. A dense or critical
candidate that reduces to the same or cheaper pole/trace bank is
`NO_GO_DIRECT_REDUCTION`.

No temporal residual result may enter the L=8 evidence manifest, change target
`R`, tune a BGL candidate or support a fermionic non-Gaussianity claim.

## Dynamic-mapping preflight

The current shared Fermi-Hubbard workload fixes its Hamiltonian and group-order
target before execution. Its route comparison needs real compiler exports,
first-step closure, native movement measurements and surface-code place-and-route;
it does not need a predictor of a future interaction schedule that is already
known.

Consequently `TEMPORAL_INTERACTION_MAPPING_SHADOW` is closed for the current
workload. It may be reconsidered only when future interactions are not available
to an offline optimizer, for example in a measurement-conditioned adaptive
algorithm or a hardware controller reacting to genuinely online calibration
drift. Even then it remains a classical advisory sidecar whose proposals must
pass exact CAR, parity, observable and resource validators.

## Reproduction and resource boundary

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  docs/research/fermion-frontier/test_fb_s0_gaussian_occupation_calibration.py

PYTHONDONTWRITEBYTECODE=1 python3 \
  docs/research/fermion-frontier/fb_s0_gaussian_occupation_calibration.py \
  --format markdown
```

The frozen logical caps are a state dimension of 256, one `8 x 8` kernel, 56
triplets processed and 448 triplet-table cells processed. These are logical
problem counts, not a measured Python working set: peak RSS, allocator overhead
and temporary object storage are unmeasured. There is no RNG, network, external
corpus read, BGL read, Agent-Bridge memory access or runtime mutation.

Artifact SHA-256 values at this checkpoint:

- implementation: `d471cf5235b1485c8cfe260315bed06076c4b3a1fd9c9f63b6b79d9cc9a21780`;
- contract: `bc78a97589d49643c3c2b167601ea0682a4813716e9294c07ac297af1fe71496`;
- generated receipt: `7c04eaa267ff16d7735f4f8b910b6a7a2b1935cf6c3fd6b03c364c709c80f1a7`.

The contract pins the checker SHA. The receipt independently records checker,
contract and pilot SHA values, and the pilot is compiled and executed from the
same verified byte buffer. The float-valued receipt uses the recorded
Python/platform/libc environment; local double-run byte identity passed, but
cross-platform byte identity is explicitly not claimed.

The receipt fixes:

```text
calibration_only=true
fermionic_non_gaussianity_assessed=false
hoi_application_claim=false
physical_l8_instance_assessed=false
ready_gate_eligible=false
bgl_accessed=false
runtime_authority=false
mainline_parameter_influence=false
portable_receipt_byte_identity=false
```

## TODO / trigger ladder

1. **P0 — DONE:** Gaussian occupation/Q2 interpretation counterexample plus the
   exhaustive fixed-L2 negative control.
2. **P1 — DESIGN HOLD:** mirror the claim boundary in BioCortex without adding a
   runtime, critical-dynamics module or HOI admission path.
3. **P2 — CONDITIONAL:** define and independently review a same-`U` Gaussian
   nominal before any experiment is called a Gaussian/non-Gaussian residual
   study. A free-reference study may run only under its narrower name.
4. **P3 — CONDITIONAL:** reopen adaptive mapping only for an interaction stream
   whose future is genuinely unavailable to a full-lookahead direct optimizer.
5. **P4 — FORBIDDEN:** never use the P0 receipt to alter BGL, L=8, hardware,
   convergence, measurement or deployment evidence.

## Primary anchors

- Physical-fermion synthesis and Gaussian/Wick boundary:
  [`FINAL_SYNTHESIS.md`](FINAL_SYNTHESIS.md).
- Matched Hubbard resource model:
  [`RESOURCE_MODEL_FERMI_HUBBARD_ZH.md`](RESOURCE_MODEL_FERMI_HUBBARD_ZH.md).
- BioCortex critical-dynamics direct-reduction rule:
  `/Data/CascadeProjects/biocortex-rs/docs/CRITICAL_DYNAMICS_HOI_EXPERIMENT_FAMILY_DESIGN_HOLD_2026_07_11.md`.
- Determinantal point-process background: Kulesza and Taskar,
  [*Determinantal Point Processes for Machine Learning*](https://www.nowpublishers.com/article/Details/MAL-044).
- Fermionic Gaussian formalism: Hackl and Bianchi,
  [*Bosonic and fermionic Gaussian states from Kähler structures*](https://scipost.org/SciPostPhysLectNotes.54/).
