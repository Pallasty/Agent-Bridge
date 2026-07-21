# Batch 2 review: DPPs and negative-dependence ML

Review date: 2026-07-11

Cluster input: inherited ledger indices 0–24 and 55–59

Newly adjudicated: indices 5–24 and 55–59

Method: three independent reviewers, with survey claims traced to the primary
papers they summarize

The task packet initially misidentified indices 50–54 as DPP claims. Those
indices belong to the 2026 fermion-to-qubit encoding paper. The reviewers
corrected the batch to 5–24 and 55–59 before voting.

Full reviewer packets:

- `reviews/dpp-vote-a.md`
- `reviews/dpp-vote-b.md`
- `reviews/dpp-vote-c.md`

## Verdict

| Scope | Verified | Refuted as written | Unverified |
|---|---:|---:|---:|
| Newly adjudicated 25 claims | 23 | 2 | 0 |
| Full 30-claim DPP cluster, including inherited 3–0 claims 0–4 | 28 | 2 | 0 |

The refuted claims are 16 and 55. Claim 16 changes a gradient estimator into a
loss/coreset estimator. One reviewer additionally challenged the proof status
of the discrete-DPP variance-rate transfer. Claim 55 turns a qualified
tractability comparison into an unsupported uniqueness and
complete-tractability theorem.

Claims 18, 22, 57, and 58 passed 2–1. Their corrected wording below is
mandatory: each inherited sentence combines a supported mathematical core
with either a physical-causation interpretation or an over-broad complexity
or equivalence phrase.

## Vote matrix

`P` = pass, `R` = refute, `U` = unverified. A verified claim has three valid
votes and fewer than two refutations.

| Ledger | Source | A | B | C | Consensus | Required boundary |
|---:|---|:---:|:---:|:---:|---|---|
| 5 | NeurIPS 2024 | P | P | P | VERIFIED | Smaller coresets are proved for carefully chosen DPPs with the stated data, density, function-class, and variance assumptions; the gain vanishes with dimension as `1/d`. |
| 6 | NeurIPS 2024 | P | P | P | VERIFIED | Hermitian, non-symmetric, and vector-valued cases are covered by different theorems with different domains and deviation ranges. |
| 7 | NeurIPS 2024 | P | P | P | VERIFIED | “Limited toolbox” is the authors' literature assessment, not a theorem that no prior guarantees existed. |
| 8 | NeurIPS 2024 | P | P | P | VERIFIED | The paper makes and supports the novelty claim; this review did not prove exhaustive historical priority. |
| 9 | NeurIPS 2024 | P | P | P | VERIFIED | Official proceedings and Spotlight metadata are confirmed. |
| 10 | RandNLA overview and primary work | P | P | P | VERIFIED | Full-column-rank fixed design and a projection `d`-DPP; the i.i.d. contrast is not a claim that every independently designed estimator is biased. |
| 11 | RandNLA overview and primary work | P | P | P | VERIFIED | The exact `(d+1)` loss identity requires rows in general position. |
| 12 | RandNLA overview and primary work | P | P | P | VERIFIED | The `d` versus `d log d` comparison is for rank preservation/subspace guarantees, not every loss metric. |
| 13 | RandNLA overview and primary work | P | P | P | VERIFIED | Worst-case optimality concerns expected error, sample size, and the specified Frobenius or trace norm—not runtime or all objectives. |
| 14 | RandNLA overview and primary work | P | P | P | VERIFIED | Separate first-sample/preprocessing cost from amortized repeated sampling and retain the kernel-access and hidden-polynomial assumptions. |
| 15 | Annals of Applied Probability result | P | P | P | VERIFIED | Uniform hypercube, a specified OPE DPP, and `C^1` functions compactly supported in the open cube; not arbitrary DPP quadrature. |
| 16 | NeurIPS 2021 result / 2025 review | R | R | R | REFUTED | The object is an empirical-risk gradient estimator, not a scalar loss or general coreset estimator; the transfer of the stated rate to the practical discrete sampler also needs the original paper's spectral-approximation caveat. |
| 17 | ICML 2019 tree sampler | P | P | P | VERIFIED | `O(log N)` describes dependence on `N` after preprocessing and with rank/sample-size factors retained; it is not a pure end-to-end cost. |
| 18 | 2025 review | P | R | P | VERIFIED 2–1 | A review-level synthesis of several conditional results and a historical quantum origin, not a unified theorem or physical-fermion causal advantage for ML. |
| 19 | 2025 preprint, new result | P | P | P | VERIFIED | Idealized two-layer teacher–student assumptions and preprint maturity; not a general deep-network pruning theorem. |
| 20 | JMLR 2022 | P | P | P | VERIFIED | Finite second moments, invertible covariance, and the stated conditional response model; “almost always biased” is a generic statement with exceptions. |
| 21 | JMLR 2022 | P | P | P | VERIFIED | The construction mixes `d` volume-rescaled points with leverage-distribution samples and weighted least squares. |
| 22 | JMLR 2022 | P | R | P | VERIFIED 2–1 | The determinant/volume-rescaled construction directly causes unbiasedness; calling that a physical-fermion resource is interpretation. |
| 23 | JMLR 2022 | P | P | P | VERIFIED | Fixed tall design, one-time near-linear preprocessing, and a later `poly(d)` sampling phase; end-to-end work still depends on `n`. |
| 24 | JMLR 2022 | P | P | P | VERIFIED | A `d=5` synthetic experiment at the reported `k` values; `1/T` is model-averaged squared-estimation-error scaling, not every loss for every `k`. |
| 55 | Foundations and Trends 2012 | U | R | R | REFUTED | Finite DPPs support exact polynomial algorithms for specified probability-inference tasks. They were not proved the unique globally negatively dependent tractable family, and MAP remains hard. |
| 56 | Foundations and Trends 2012 | P | P | P | VERIFIED | The `O(N^3)` decomposition and `O(N k^3)` sampler are the monograph's costs; its `N≈10^4` timing is a 2012 hardware observation. |
| 57 | Foundations and Trends 2012 | P | P | R | VERIFIED 2–1 | MAP remains NP-hard under cardinality constraints; the cited greedy factor is about `O(1/k!)`, not a useful constant uniform in `k`. |
| 58 | Foundations and Trends 2012 | P | R | P | VERIFIED 2–1 | Exact determinantal structure applies to specified free/quasi-free fermion point processes, not all interacting thermal fermion systems or every ML DPP as a physical system. |
| 59 | Foundations and Trends 2012 | P | P | P | VERIFIED | Constant-in-`N` normalization or marginal queries assume the low-rank dual kernel is already formed; forming it and exact sampling retain linear `N` costs. |

## Corrected findings

### 1. A DPP can beat independent coresets, conditionally

The NeurIPS result supplies a theorem-backed example rather than a universal
dominance theorem. For a discretized multivariate OPE DPP whose linear
statistics have the required variance scaling, the coreset error exponent
improves over independent sampling. The construction assumes an ambient data
density and regularity conditions, requires a usable approximation to that
density, and gains only `1/d` in the exponent. The paper also reports material
kernel-density and DPP-sampling costs.

Primary source: [NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/997089469acbeb410405e43f0011be1f-Abstract-Conference.html).

### 2. Determinantal sampling gives exact statistical identities

Projection/volume DPPs directly yield unbiased least-squares estimators and,
under general-position assumptions, an exact expected-loss identity. In
random-design regression, a volume-rescaled sample combined with leverage
sampling achieves unbiasedness and a near-optimal expected loss with
`O(d log d + d/epsilon)` points. These are determinant and sampling-design
results; they do not require a physical fermionic device.

Primary sources: [JMLR 2018 volume sampling](https://jmlr.org/papers/v19/17-781.html)
and [JMLR 2022 random-design regression](https://www.jmlr.org/papers/v23/19-571.html).

### 3. Variance-rate improvements require a specified estimator

The Monte Carlo result uses a particular OPE DPP on a hypercube and a restricted
function class. The SGD result concerns an unbiased gradient estimator. The
inherited ledger incorrectly relabeled it as a loss/coreset estimator. One
reviewer also found that the original NeurIPS paper treats part of the
transfer from a smoothed theoretical estimator to the practical discrete DPP
through a spectral approximation whose rigor is qualified in the appendix; the
other two accepted the later review's theorem statement after correcting the
estimator object. The final report should retain this proof-status disagreement.

Primary sources: [Annals of Applied Probability 2020](https://doi.org/10.1214/19-AAP1504)
and [NeurIPS 2021](https://proceedings.neurips.cc/paper/2021/hash/8744cf92c88433f8cb04a02e6db69a0d-Abstract.html).

### 4. Exact probability inference does not make DPP optimization easy

For finite DPPs, determinants and eigendecompositions make normalization,
marginalization, conditioning, and exact sampling polynomial-time. Mode/MAP
optimization is nevertheless NP-hard and hard to approximate within the
stated factor; imposing a cardinality constraint does not remove the hardness.
The source does not prove that DPPs are the unique negatively dependent family
with tractable inference.

Primary source: [Kulesza and Taskar 2012](https://www.nowpublishers.com/article/Details/MAL-044).

### 5. Practicality is representation- and amortization-dependent

A dense generic kernel carries an `O(N^3)` eigendecomposition bottleneck.
Low-rank dual kernels, distortion-free intermediate sampling, and tree data
structures can reduce later sampling or query costs, but each moves work into
preprocessing and retains rank, subset-size, kernel-access, or hidden polynomial
factors. “Logarithmic sampling” and “constant-in-`N` inference” are valid only
with those factors and preconditions stated.

Primary sources: [COLT 2019 intermediate sampling](https://proceedings.mlr.press/v99/derezinski19a.html)
and [ICML 2019 tree sampling](https://proceedings.mlr.press/v97/gillenwater19a.html).

### 6. The fermion connection is structural, not a generic AI resource

Determinantal point processes have a direct historical and mathematical link
to anti-bunching in specified free or quasi-free fermion point processes. The
ML results exploit the same determinant and negative-dependence mathematics on
classical computers. The reviewed sources do not show that physical fermions,
fermionic hardware, or quantum effects cause the ML improvements.

## Source-independence audit

The source set is not a collection of independent replications:

- the 2024 coreset paper and 2025 negative-dependence review share Bardenet,
  Ghosh, and Tran;
- the Monte Carlo and SGD primary papers share members of that research line;
- the RandNLA overview and the 2022 random-design paper share Dereziński, and
  the overview summarizes several papers from the same program;
- the 2012 monograph is an authoritative tutorial but mixes authors' results
  with older work and should not be labeled uniformly as primary research.

The three votes are independent reviews of the claims. They do not turn linked
papers into independent empirical or theoretical replications.

## Program consequence

The DPP evidence supports a narrower and more useful thesis: negative
dependence and determinant identities can create exact unbiasedness, improved
sample complexity, or variance rates when the task and kernel are matched.
The advantage is bounded by model construction, dimension, preprocessing,
hidden polynomial factors, and a sharp sampling-versus-MAP distinction. No
source supports a universal “fermionic AI advantage.”
