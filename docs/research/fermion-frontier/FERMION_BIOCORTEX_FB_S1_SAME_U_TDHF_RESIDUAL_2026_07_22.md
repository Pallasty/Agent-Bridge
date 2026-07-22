# Fermion × BioCortex FB-S1 same-U TDHF residual benchmark

Date: 2026-07-22

Decision: **NO_GO_DIRECT_REDUCTION**

Authority: research-only, post-reveal amended exploratory evidence; not a BioCortex runtime result

## Outcome first

The budget-valid five-state recurrent proxy did not beat the direct temporal
baselines. Its median held-out NRMSE was `0.9252574169819254`; the best direct
baseline, `PRONY_AR8`, reached `0.8932096493643846` with half as many realized
parameters (`18` versus `36`). The registered NRMSE improvement was therefore
`-0.035879334308967954`, rather than the required `+0.10`. Every candidate and
direct baseline had zero effective forecast-horizon steps under the frozen
normalized-error threshold, so the required `+0.20` horizon improvement also
failed.

This activates the registered direct-reduction stop rule. Nothing from FB-S1 is
eligible for Agent-Bridge runtime or memory-policy adoption.

## Research-integrity chronology

The first same-session protocol used an eight-state proxy. Its initial output
was inspected before the protocol had an independent Git timestamp. Audit then
found that the realized fixed-plus-fitted scalar count had been understated as
`37`; the correct count is `54`, above the frozen cap of `40`. That run is
permanently classified `INVALID_BUDGET_ACCOUNTING`, not relabelled as a valid
NO-GO. Its diagnostic values and limitations are retained in
`fb_s1_initial_reveal_audit.json`.

The repair did not raise the cap. It applied the mechanical formula

```text
realized parameters = 4d + 4 + 2(d+1) = 6d + 6
```

and selected the largest admissible integer, `d=5` (`36 <= 40`, while `d=6`
would require `42`). U values, causal split, purge, seeds, ridge coefficient,
KPI thresholds and direct baselines were unchanged. Fixed recurrent weights
were precomputed, and the operation inventory was corrected to `14d+2=72`.

The repaired protocol and exact executor were committed before the d=5 outcome
was run:

- preregistration-repair commit:
  `ce6d9d1a79c7e57ccf411b5772b5a32c8688472a`;
- amended contract SHA-256:
  `363c18d668ce8ea7eb3896ccd7c72ab39fdbf3cbce6509604eb625d2ea139d0b`;
- benchmark SHA-256:
  `ede1ca6b68a6efeec12a1e80714091567ebd7f768cc48f7f1a8a78bd628c5952`.

Because this repair followed the d=8 reveal, the d=5 run is explicitly
`POST_REVEAL_AMENDED_EXPLORATORY`, has no confirmation authority and could not
have produced a confirmatory GO even if it had crossed the thresholds.

## Frozen benchmark

- Physics: L=2, four particles, same interaction strength in the exact and
  collinear number-conserving TDHF trajectories.
- Observables: staggered magnetization and double occupancy.
- Residual: exact observable minus the same-time TDHF/Wick nominal observable.
- Time grid: `dt=0.05`, steps `0..80`.
- Fit U: `2, 4, 6`; development-only physics check U: `5`; held-out U: `3, 7`.
- Causal prefix: steps `0..48`; recursive forecast: `49..80`; the first eight
  forecast offsets are purged before scoring.
- Scaling: per-observable population mean and standard deviation from only the
  147 train-U prefix values.
- Fitting: 120 causal rows per fitted model. Neither held-out U nor future
  suffix values enter scaling, fitting or seed selection.
- Candidate: three fixed seeds (`11`, `29`, `47`), reported by componentwise
  median as a robustness diagnostic, not seed-generalization evidence.

## Held-out results

| Model | NRMSE | horizon | parameters | state | logical ops/step |
|---|---:|---:|---:|---:|---:|
| Persistence | 0.9493823610 | 0 | 0 | 2 | 2 |
| Affine DMD | 0.9333877031 | 0 | 6 | 2 | 10 |
| Ridge VAR(4) | 1.0201752672 | 0 | 18 | 8 | 34 |
| Prony / AR(8) | **0.8932096494** | 0 | 18 | 16 | 34 |
| HBR-R1-motivated tanh proxy, median | 0.9252574170 | 0 | 36 | 5 | 72 |

Candidate seed NRMSE values were `0.8548022901`, `0.9252574170`, and
`1.0837624846`. A single favorable seed does not replace the frozen median and
was not selected using held-out performance.

## Physics and numerical guards

All registered guards passed:

| Guard | observed maximum | cap |
|---|---:|---:|
| exact pre-normalization norm error | 4.441e-16 | 1e-10 |
| exact particle-number drift | 0 | 1e-9 |
| exact out-of-sector probability | 0 | 1e-9 |
| exact energy drift | 5.826e-15 | 5e-5 |
| dt versus dt/2 observable refinement | 2.540e-15 | 1e-10 |
| TDHF Hermiticity residual | 0 | 1e-10 |
| TDHF trace drift | 6.217e-15 | 1e-9 |
| TDHF idempotency residual | 3.997e-15 | 1e-8 |
| TDHF cross-spin coherence | 0 | 1e-10 |
| TDHF energy drift | 5.161e-10 | 5e-5 |

The Taylor reference remains the L=2 diagnostic pilot, not a rigorously bounded
L=8 reference. The dt/2 agreement is a numerical refinement check, not a proof
that the pilot has general reference authority.

## Resource record

Runs were single-process under a systemd `MemoryMax=1 GiB` scope. The timed
summary run took `32.02 s` and reported `27,444 KiB` maximum RSS externally.
A separate JSON-receipt run recorded `32.02 s`, `1,096,612` peak tracemalloc
bytes and `434,216,960` process peak-RSS bytes internally. Because the two RSS
instruments/runs disagree materially, the conservative larger value is retained
and portable byte identity is false; neither measurement grants runtime
authority.

## BioCortex boundary

The candidate is a local tanh reservoir proxy motivated only by the fixed
recurrent-context idea in BioCortex's HBR-R1 public generated design. The
binding is design commit `3d66a257b3e1038b1715bbdb3b05529b7a686354`, document
SHA-256 `4e059a84a7a8dea52f45784598f530f5acff64d6d5609f81fb36020a5465f96a`.
That design itself says implementation is false. FB-S1 does not call the
BioCortex repository, implement its topology/dynamics, assess HBR-R1
conformance, or grant BioCortex runtime authority.

It also supplies no evidence about fermionic non-Gaussianity, quantum
advantage, physical L=8 instances, BGL, hardware, or mainline parameter
influence.

## Disposition and next admissible target

Close this proxy lane as `NO_GO_DIRECT_REDUCTION` and retain Prony/AR8 as the
compact comparator for this L=2 residual surface. Do not tune the current
threshold, seeds, U split or proxy dimension.

Any future FB-S2 must be a fresh protocol with new held-out U/time/seed support.
The only scientifically useful reopening is an exact, source-bound execution of
an independently reviewed BioCortex mechanism (or a proved faithful adapter),
compared again with direct pole/modal reduction. A new generic reservoir sweep
would not answer that question and is not recommended.
