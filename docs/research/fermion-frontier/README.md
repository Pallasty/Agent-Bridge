# Fermion frontier research takeover

Status date: 2026-07-12

Scope: physical fermions, not the historical Fermion Memory service.

## Research question

The inherited Claude investigation has two linked but non-identical questions:

1. What does “fermion continuity” mean across condensed matter, field theory,
   lattice theory, and fermionic Gaussian-state dynamics?
2. Under which assumptions does antisymmetry, Gaussian closure, parity grading,
   or determinant/Pfaffian structure create a computational or statistical
   advantage in high-dimensional spaces?

The final report must not invent a single unified “fermion continuity” law.
It must separate established physical meanings before comparing their
mathematical structures.

## Inherited evidence

Claude completed two broad deep-research rounds and began a focused third
verification round:

| Round | Candidate claims | Claims adjudicated | Confirmed | Refuted | Durable result |
|---|---:|---:|---:|---:|---|
| Full survey | 120 | 25 | 22 | 3 | `claude-round1-result.json` |
| Targeted gap survey | 119 | 25 | 21 | 4 | `claude-round2-result.json` |
| Gap 3/4/5 verification | 70 | 10 | 10 | 0 | `claude-round3-partial-result.json` |

At takeover, the third round was incomplete: only five claims had a full 3-0
vote, five more had 2-0 votes, and sixty had no valid adjudication. The original
third-round synthesis failed after the Claude session hit its usage limit.

The compact 70-claim input is preserved as `gap345-claims.json`. Original
Claude paths and content hashes are recorded in `ARTIFACTS.md`.

## Evidence contract

A claim may enter the final report as a finding only when all of the following
are explicit:

- its physical meaning and domain;
- assumptions and theorem/experiment scope;
- asymptotic complexity and practical or constant-factor costs when relevant;
- failure boundary or counterexample;
- primary source and publication status;
- three independent verdicts, with disagreement retained;
- classification as direct support, mathematical transfer, or analogy.

Additional rules:

- A 2026 preprint is at most medium-confidence without independent support.
- A 2-0 vote is provisional, not fully verified.
- “Efficiently sampleable DPP” does not imply efficient DPP MAP optimization.
- Matchgate classical simulability is not a quantum-computing advantage.
- A hardware architecture proposal is not an end-to-end experimental machine.
- A natural-gradient analogy to machine learning is not a direct application
  until the two metrics and optimization domains are mapped explicitly.

## Current working thesis

Fermionic structure is not a universal computational advantage. It becomes a
lever when the task preserves Gaussian closure, parity grading,
determinant/Pfaffian algebra, negative dependence, or a target symmetry that is
intrinsically antisymmetric. Non-Gaussian resources, interactions, encoding
overheads, high polynomial degree, and mismatched inductive bias delimit the
advantage.

The three focused verification batches are closed, and this thesis passed the
final cross-cluster adversarial review with all required corrections applied.

## Planned verification batches

1. Gaussian/non-Gaussian boundary: **complete** — 22 verified and 3 refuted as
   written; corrected findings are in `BATCH1_GAUSSIAN_NONGAUSSIAN_REVIEW.md`.
2. DPP and negative-dependence ML: **complete** — the full 30-claim cluster has
   28 verified and 2 refuted as written; corrected findings are in
   `BATCH2_DPP_REVIEW.md`.
3. Fermion-to-qubit mappings and native hardware: **complete** — 12 fully
   verified, 2 verified only after partial rewrite, and 1 refuted as written;
   corrected findings and the July 2026 experimental maturity update are in
   `BATCH3_ENCODING_HARDWARE_REVIEW.md`.
4. Final synthesis and adversarial review: **complete**.
5. First roadmap execution task, evidence-bounded Fermi--Hubbard resource model:
   **planning scaffold complete; matched benchmark still open** — logical
   subtotals, topology, first-step unknowns, route-specific error/shots
   bookkeeping, and a parameterized native/bare-qubit/lattice-surgery physical
   translation are implemented. Cross-compiler term-order validation and current
   primary-source gaps remain explicit as `UNRESOLVED`.

The fail-closed evidence path now binds each export's embedded `route` to its
manifest key and uses convergence schema v2 for the fixed
`staggered_magnetization` / `double_occupancy` observable pair. The convergence
plan fixes the complete refinement grid and target `R=100`; every point is a
joint-observable record with estimator-mean covariance, systematic bounds, and
route/circuit provenance; circuit fingerprints are globally unique per route/R
point. A `shared_shots` point additionally supplies attempted/accepted shots,
effective-independent-shot counts, per-shot contribution ranges, and
concentration/mitigation status. Finite-sample statistical gates use family-wise
Bonferroni--Hoeffding half-widths from the validated contribution ranges and
effective independent samples. Covariance-derived normal intervals are diagnostic
rather than the binding finite-sample guarantee.

Joint stability on the declared grid without a fully bounded independent
reference is only `SCREENED_FOR_TARGET_R`. `READY_FOR_TARGET_R` additionally
requires binding route systematics, validated independent bounded-sample assumptions,
and a bounded independent reference for both observables; the unified evidence
orchestrator accepts only that stronger state.
It also requires a complete surface-code place-and-route ledger. Real compiler
exports, route measurements, bounded references, and physical schedules remain
`UNRESOLVED`.

Two independent preflight interfaces now make the remaining measurement and
reference gaps quantitative without claiming that they are closed. The
measurement-campaign planner derives four unique convergence routes, six fixed
`R` values, two observables, and all point/adjacent/reference comparisons directly
from the pinned evidence contract, giving a Bonferroni family size of `136`. With
the declared residual allocation `h=0.002`, the shared batch is controlled by the
width-two staggered-magnetization estimator: `4,300,768` effective independent
shots per route/R cell, or `103,218,432` over all 24 cells. The earlier `10,000`
shot placeholder fails even the looser pointwise statistical budget. Because the
template leaves acceptance probability `p` and effective-shot fraction `eta`
null, accepted and raw execution totals remain unresolved; the planner explicitly
returns `EFFECTIVE_TARGETS_DERIVED_RAW_UNRESOLVED`, reports
`NOT_ASSESSED_BY_PREFLIGHT` for convergence certification, and is not measurement
evidence.

Here `136` is a conservative declared-comparison multiplicity, not a claim that
136 independent random events exist: the same 48 route/R point intervals are reused
inside adjacent and reference inequalities. Likewise, a future `eta` is usable for
planning only if it is a conservative effective-independent-shot fraction valid for
both jointly measured observables; an empirical ESS ratio remains diagnostic.

The separate reference-qualification contract/template/validator fixes the same
workload and two observable identities, verifies local JSON certificate paths and
SHA-256 hashes, requires exact certificate-to-ledger record binding, checks the
deterministic error decomposition, and compares reference inputs against an
externally supplied batch/circuit snapshot. A binding-looking method must also
provide formula/term-order, checker, implementation-commit, environment-lock and
theorem/assumption fingerprints, directed-interval rounding, and its method-specific
mechanical claims. Uncertified tensor-network, Krylov and stochastic records remain
`DIAGNOSTIC_ONLY` even if they assert binding claims. Because the validator does not
run a fixed machine checker or load the campaign budget, its maximum output is
`STRUCTURALLY_COMPLETE_UNVERIFIED`; it explicitly returns
`ready_gate_eligible=false`, and no `QUALIFIED_BOUNDED` state is reachable. The empty
template is `UNRESOLVED`. External-snapshot completeness is only shape-checked here,
not proven against convergence data, and even the structurally complete CLI state
exits nonzero. The primary-source method assessment and proposed
certificate pipeline are recorded in
[REFERENCE_CERTIFICATION_STRATEGY.md](REFERENCE_CERTIFICATION_STRATEGY.md).

The first executable proof-kernel layer now exists, but remains deliberately
separate from that reference ledger. Its source-pinned checker uses only exact
`Fraction` arithmetic to enclose nonzero Pauli rotations, applies a contract-pinned
backpropagation sequence, merges duplicate strings before truncation, and recomputes
the cumulative dropped-`L1` interval. The maximum result is
`VERIFIED_CIRCUIT_TRUNCATION_SUBCERTIFICATE`; it does not assess the
fermion-to-Pauli mapping, product-formula error to exact evolution, a truncation
acceptance budget, or L=8, and its CLI exits nonzero. An executable L=2 `R=2`
conformance witness independently reproduces both product-formula observables from
112 Pauli rotations, while the full 112-gate Fraction certificate is explicitly
`DEFERRED_RESOURCE_LIMIT` because the unoptimized sparse rational expansion grows
too quickly.

A separate source-pinned mapping checker now closes the narrower gate-identity gap
for fixed L=2/L=3 OBC profiles. It independently regenerates the site-major,
spin-minor JW bonds, `XX/YY` parity strings, unshifted onsite `I/Z/Z/ZZ` terms and
the raw R=2 Strang events. Exact CAR-versus-Pauli basis-action witnesses include
external spectators; all four onsite occupations are re-evaluated; omitted identity
rotations retain an explicit global-phase ledger. The L=2 nonidentity sequence is
checked at runtime, gate by gate, against the source-pinned 112-gate witness. L=3
forces H2 and H3 to be nonempty. The maximum state is only
`VERIFIED_CANONICAL_JW_MAPPING_SUBCERTIFICATE`: it does not compose itself with the
truncation kernel, assess product-formula error, transfer to L=8, or enter READY.

An exact `(x_mask,z_mask)` Pauli backend and deterministic Fraction-interval
checkpoint digest first established the required arithmetic as a non-authoritative
prototype.  The follow-on source-pinned L=2 checker now uses that backend to replay
all 112 mapped nonidentity rotations, with one checkpoint at each of 20 raw group events,
fifth-order Taylor enclosures and outward quantization to denominator `2^32` after
each slice.  Both observables retain the complete Pauli space reached by the run:
the final/peak term counts are 16,380 for staggered magnetization and 16,381 for
double occupancy, and cumulative dropped `L1` is exactly zero.  The certified
declared-circuit intervals are `[0.7815321311,0.7818957902]` and
`[0.0306896903,0.0311607374]`.  This closes the earlier L=2 implementation defer,
but not product-formula error to ideal evolution or any L=8 claim.

A second source-pinned checker now evaluates the exact nested commutators in the
fixed `H1,H2,HU,H3,H4` Strang split at L=2,3,8.  It fully merges each theorem family
before taking a Pauli-coefficient `L1` norm and applies the constants in Schubert--
Mendl Proposition 2, Eq. (13).  For L=8 it obtains `C=7076/3`, hence at `R=100` a
unitary bound `1769/7500` and the generic norm-one observable bound `1769/3750`.
The latter is far above the per-observable allocation `1/4000`; this generic route
would require at least `R=4344`.  Mapping/truncation certificates are not composed,
the physical L=8 workload identity and observable-specific tightening remain
unassessed, and this result cannot qualify a reference or READY gate.

The follow-on grouping screen exhausts all 120 permutations of those five groups and
all 24 permutations of an exact OBC candidate made from two disjoint bulk-plaquette
families, a disjoint boundary residual, and onsite interactions.  The best five-group
order has `C=7072/3`, only a `1/1769` relative reduction; the best plaquette-boundary
candidate is worse at `C=7232/3`.  Since R=100 requires `C<=5/4`, neither reordering
nor regrouping can supply the missing three orders of magnitude under the same
coefficient-L1 reduction.  The candidate bulk exponentials also contain
noncommuting edges inside each plaquette and do not match the declared benchmark
circuit.  This screen therefore selects certified cluster spectral norms or
observable/locality-specific bounds as the next mathematical layer.

The cluster route has now been audited against the paper-time official implementation
and stopped at a stronger exact decision boundary.  The upstream 14-mode method uses
binary64 NumPy spectral calculations without directed rounding, so its values
are diagnostic rather than certificate inputs.  A full L8 diagnostic prototype lowers
the coefficient to about `1343.96`, still more than one thousand times the required
`5/4`.  More decisively, the new exact checker applies just
`A=[K1,[K1,H1]]` to the normalized half-filled Néel basis vector and obtains
`||A|q>||^2=295200`.  Hence the single positive theorem contribution already obeys
`(||A||/12)^2>=2050>25/16=(5/4)^2`.  Even a globally exact, sector-restricted cluster
spectral norm therefore cannot make the fixed generic R=100 bound qualify.  This is
not a lower bound on actual Trotter error and does not exclude observable/locality-
specific cancellation, alternative groupings, or higher-order formulas.

The first observable-specific layer is now machine checked as well.  The new
Fang--Qu specialization expands the fixed nine-stage Strang Heisenberg map through
degree three and enumerates all 495 degree-four remainder paths.  For one
`delta=1/100` step acting on the initial observables, the rigorous Pauli-L1 operator
bounds are `159187/1600000000` for staggered magnetization and
`133927/2400000000` for double occupancy.  These numbers cannot simply be multiplied
by 100: correct telescoping acts on evolved observables `O_k`.  Any uniform-supremum
Pauli-L1 shortcut nevertheless has a `k=0` floor already 39.80 and 22.32 times the
full-time allocation, so that architecture is stopped.  An exact half-filled-sector
`D3` action witness also stops the corresponding uniform-leading route for
magnetization, while double occupancy remains open to tighter sector norms or a
per-step/cancellation-aware ledger.  No full R=100 error or reference is claimed.

The fixed double-occupancy greedy-cluster uniform-sup shortcut is now decided too.  A new
same-byte checker expands 2,748 simplified physical-fermion terms into 18,544 field
terms, maps them exactly to the same 8,928-term Pauli `D3`, and replays the upstream
14-mode greedy partition into 43 clusters.  Exact global half-filled Néel matrix
elements lower-bound the first 30 cluster norms by a total `1945/768`, already above
the required uniform coefficient `5/2`.  Thus even exact norms for this fixed k=0
partition followed by triangle cannot seed the R=100 uniform-supremum certificate.
This does not rule out a per-step evolved cluster ledger: the k=0 partial floor then
contributes only `389/153600000`.  The sum is also deliberately not used as a lower
bound on the globally merged `D3`; cross-cluster cancellation, another partition and
direct global-sector methods remain open.  The fixture-defined decomposition/order
matches the external upstream audit but its provenance is not regenerated by the
checker; exact total-operator identity and all 30 used actions are machine checked.

The direct evolved-observable kernel has now closed its first bounded L8 unit.  A
same-byte source-pinned checker independently rebuilds the 8x8 OBC/JW groups,
verifies 3,584 representative CAR hopping actions and 256 onsite occupations, and
backpropagates both fixed observables through one fused nine-stage, 1,152-gate
Strang step.  The corresponding raw ten-event circuit has 1,280 gates; its central
commuting H4 halves are fused before truncation, so the exact unitary is unchanged
but the truncation path is deliberately different.  Coefficients use outward
`2^64` fixed-point intervals with Taylor truncation index `N=5`.  Equal keys are
merged before a deterministic top-65,536 rule after every eight gates, yielding
144 checkpoint records bound by digest.

For staggered magnetization, the peak/final term counts are 115,492/65,536,
cumulative dropped `L1` is `4619985807746/2^64`, and the declared untruncated
mapped-step Néel interval is
`[18433840572171559446,18433849812143178978]/2^64`, approximately
`[0.9993004997799919,0.9993010006798572]`.  For double occupancy the corresponding
counts are 199,528/65,536, cumulative dropped `L1` is
`130757007004862/2^64`, and the interval is
`[6316730869963049,6578244883988034]/2^64`, approximately
`[0.0003424306666110094,0.0003566073697180741]`.  These intervals certify
fixed-point containment and truncation only relative to the untruncated fused
mapped one-step circuit.  They do not certify exact-Hubbard evolution, the full
R=100 chain, a reference value, or READY.

The parent--child route now has one real linked transition.  Four canonical
compact-JSON/zlib/Base85 sidecars materialize the complete 65,536-term retained
boxes at boundaries one and two.  A new checker first executes the same-byte
one-step parent certificate, proves each boundary-one sidecar has the parent's
exact expansion, cumulative drop and retained expectation, and then replays the
second 1,152-gate/144-checkpoint child without fusing H1 halves across the step
boundary.  Boundary two is compared with the recomputed expansion term for term.

For staggered magnetization the second child drops `207375793741436/2^64`, giving
two-step cumulative drop `211995779549182/2^64` and mapped-circuit interval
`[18395060021948335379,18395484013507455340]/2^64`, approximately
`[0.9971982019398818,0.9972211865683575]`.  Double occupancy drops
`2152392847533726/2^64`, giving cumulative `2283149854538588/2^64` and interval
`[23418151510906025,27984451220025405]/2^64`, approximately
`[0.0012695005371859505,0.0015170401404283085]`.  The latter already consumes
about 49.5% of the `1/4000` scalar truncation-error-radius allocation after only
two mapped steps.  That allocation does not include coefficient-box width or
product-formula-to-exact-Hubbard error.
This is a two-step custody/transition certificate, not an R=100 or exact-Hubbard
result.

The magnetization chain now closes one further adjacent transition.  The step-3
checker same-byte executes the positive two-step parent, selects only its
magnetization output, binds the previous transition, and replays a fresh
1,152-gate/144-checkpoint fixed-`K=65,536` child.  The third child drops
`1479500890039114/2^64`; cumulative drop is `1691496669588296/2^64`, and the
declared three-step mapped-circuit interval is
`[18329701971403435870,18333084964742654970]/2^64`, approximately
`[0.9936551349203719,0.9938385273567662]`.  Term-gate visits are 83,365,144 and
the peak expansion is 92,964 terms.  A separate fixed-K step-4 diagnostic gives
cumulative drop `7166451866997599/2^64`, about `3.88494e-4`, already above the
`1/4000` truncation-radius allocation; no boundary-4 sidecar or four-step
certificate is issued.

Double occupancy remains certified only through step 2.  Adaptive-K policy v1 was
committed before its formal run and fixes nine candidates from 65,536 through
131,072 plus a future-checkpoint prefix envelope.  It selects
`[73728,81920,90112,98304,114688,122880]` for the first six checkpoints, then
fails closed at checkpoint 7: even `K=131,072` requires a drop of
`429299248198/2^64` while only `177868057779/2^64` remains below that prefix cap.
The infeasibility screen therefore commits no step-3 child boundary.  A diagnostic
fixed-`K=262,144` run ends below the scalar `1/4000` ceiling, but needs 337,691,387
term-gate visits and a 446,188-term peak, violating every corresponding v1 cap;
it is evidence for designing a separately precommitted v2, not a certificate.

A committed-arithmetic v2 design probe now tests the bounded `K<=327,680` policy
surface without certificate authority.  Magnetization step 4 commits 28 diagnostic
checkpoints and then needs effective `K=333,983` at checkpoint 29; double occupancy
step 3 commits 21 and then needs `K=350,604` at checkpoint 22.  Their peaks/visits
are respectively 397,526/48,646,721 and 501,254/37,271,764, so the observed stop is
the frozen candidate ceiling rather than the proposed resource envelope.  These
canonical transcripts omit runtime/RSS/host/path fields and may guide a separately
committed v2 policy, but they are not child boundaries, transitions or positive
certificate witnesses.

Two separate v2 policies now freeze those attempts before formal replay.  The
magnetization route has 17 candidates and the double-occupancy route 21, both ending
at `K=327,680`; each caps live/digest terms at 786,432 and visits at 536,870,912.
They source-pin the correct immediate parent, v2 arithmetic kernel and diagnostic
provenance while deliberately omitting formal failure checkpoints, selected-K
histories, child hashes/values, resource observations and positive statuses.  A
formal result is authorized only through a policy-pinned checker, and any looser
ladder, budget, resource or output schema requires a new policy version.

The policy-pinned dual formal screen has now completed.  Magnetization formally
commits the first-feasible ladder for 28 checkpoints, then fails at checkpoint 29:
the current slack is 284,729,064,009 ticks, `K=327,680` drops 415,018,229,551,
and the minimum effective K is 333,983.  Double occupancy commits 21 checkpoints,
then fails at checkpoint 22 with 229,230,395,634 ticks of slack, a maximum-policy-K
drop of 1,074,313,509,825 and minimum effective K 350,604.  The formal ledger/failure
hashes are `30c538ed...ca6fa`/`1a8ec752...02894` and
`504964a8...9b051`/`f3e78409...50820`.  Both stops are maximum-K infeasibility
screens under the precommitted policies, not resource failures.  Magnetization depth
therefore remains 3 and double-occupancy depth 2; no boundary, transition or sidecar
is emitted, and exact-Hubbard error, remaining R100 steps, physical reference and
READY remain unassessed.

An extended-`K` v3 design probe now reuses the exact committed v2 implementation
through a same-byte, source-bounded wrapper while remaining explicitly outside
certificate authority.  Its magnetization/double-occupancy ladders contain 21/25
candidates through `K=393,216`; only the candidate/output ceiling is relaxed, while
the `786,432` live/digest and `536,870,912` visit envelopes remain unchanged.
Magnetization commits 32 diagnostic checkpoints and fails at checkpoint 33 with
minimum effective `K=405,291`; double occupancy commits 23 and fails at checkpoint
24 with minimum `K=397,750`.  Their peaks/visits are 550,806/61,421,993 and
525,968/44,079,570, so both are again candidate-ceiling stops rather than resource
stops.  Every previously committed v2 diagnostic prefix selection, drop and retained
state is unchanged.  This rules out `K<=393,216` as a complete attempted-step ladder
and requires any next design ladder to include at least `K=409,600`; it does not
precommit a v3 policy or increase either certified depth.

The next v4 design generation extends those same ladders to `K=458,752` with
25/29 candidates and preserves the v3 `786,432` live/digest and `536,870,912`
visit envelopes.  Its same-byte provenance is explicit across v4, the pinned v3
parent probe, the pinned v2 implementation and the original kernel/root/parent
sources; bounded output is atomically published.  Magnetization commits 35
checkpoints and then needs effective `K=464,310` at checkpoint 36, while double
occupancy commits 27 and needs `K=461,297` at checkpoint 28.  Their peaks/visits
are 660,262/73,130,963 and 591,330/59,719,825, so both stops remain maximum-K
diagnostics rather than resource failures.  The complete v3 committed prefixes
and old failure computations are unchanged; each old failure is first continued
by `K=409,600`.  The next standard ladder value `K=475,136` covers both current
minimum-K requirements, but has not yet been tested beyond those handoff points.
No v4 policy, formal witness, child boundary, transition or depth increment exists.

The v5 kernel-edge design generation adds `475,136`, `491,520` and `507,904`,
bringing the magnetization/double-occupancy ladders to 28/32 candidates while
keeping every non-K v4 resource cap fixed.  Its provenance separates the direct
v5-over-canonical-v4 delta from the effective configured-v4 override and binds the
ordered v5/v4/v3/v2 source layers.  Magnetization selects
`475,136/475,136/491,520` at checkpoints 36--38, then checkpoint 39 needs effective
`K=521,800`; double occupancy selects
`475,136/475,136/507,904/507,904` at checkpoints 28--31, then checkpoint 32 needs
`K=518,097`.  Peaks/visits are 714,754/86,294,299 and 694,872/76,953,164, so both
are still K-ceiling rather than resource failures.  The next standard value
`K=524,288` covers both current minima but equals the kernel retained-K maximum.
Double occupancy already uses all 32 candidate slots, so it cannot append that value
without deleting or merging an older candidate in a separately designed generation.
No v5 policy or positive certificate artifact is created, and certified depths stay
at 3/2.

The v6 kernel-limit generation tests the final retained-K value supported by the
current arithmetic kernel.  Magnetization appends `K=524,288` for 29 candidates;
double occupancy replaces the unused v5-only `491,520` slot with `524,288`, keeping
32 candidates while preserving every v2--v4 candidate and every K actually selected
by v5.  The wrapper binds ordered v6/v5/v4/v3/v2 same-byte source layers and records
the direct v6 delta, the configured-v5 effective override and its embedded
configured-v4 override separately.  Magnetization selects `524,288` at checkpoint
39 and then stops at checkpoint 40, whose minimum effective K is `525,859`, only
1,571 above the kernel maximum; peak/visits are `714,754/91,034,065`.  Under the
unchanged non-K caps, double occupancy selects `524,288` at checkpoint 32 but the
next propagation aborts before ranking because its 825,000-term expansion exceeds
the 786,432 live/digest envelope.  A noncanonical resource measurement at the
kernel's 1,048,576-term capability confirms that checkpoint 33 would additionally
need `K=553,717`, 29,429 above the retained-K maximum, with 82,050,350 visits.
Resource exceptions propagate without fallback, so only the complete magnetization
v6 transcript is published and no partial double-occupancy transcript exists.
Candidate-only extension of this kernel is now exhausted; continuation requires an
explicit kernel/resource or checkpointing redesign.  No v6 policy, formal witness,
boundary, transition, exact-Hubbard claim, READY component or certified-depth
increase is created.

An independent four-gate checkpoint-granularity screen now evaluates one explicit
redesign without creating a v7 generation.  The screen fresh-executes only its own
same-byte control flow.  Exact v2 bytes provide helper routines and exact v6 bytes
provide the candidate ladders and resource caps as configuration only; neither run
entrypoint is invoked, and v6 is not a same-byte execution parent.  The physical
nine-stage, 1,152-gate sequence is unchanged, while ranking and commit occur every
four gates, giving 288 checkpoints per mapped step.  Doubling the denominator
preserves every aligned budget boundary, `cap4(2q)=cap8(q)`, but the additional
commits deliberately produce a different retained-state trajectory.

With the exact v6 ladders, magnetization commits 77 four-gate checkpoints and fails
at checkpoint 78, gates 308--311, with minimum effective `K=529,897`, 5,609 above
the kernel limit; peak/visits are 643,624/82,493,877.  Because checkpoint 78 is the
second half of old eight-gate checkpoint 39, this lower observed peak does not
increase M reach.  Double occupancy commits 64 checkpoints and fails at checkpoint
65, gates 256--259, with minimum `K=532,869`, excess 8,581 and peak/visits
645,011/75,412,433.  The finer cadence therefore avoids the old 825,000-term live
stop long enough to expose a retained-K stop in the first half of old checkpoint
33.  The v6-removed `K=491,520` rung would be first feasible at four-gate
checkpoints 58 and 59, so its old eight-gate nonselection is not trajectory-neutral
under the new cadence.  A controlled noncanonical 32-slot sensitivity restores that
rung while removing the still-unused `65,536` rung.  It changes q58--59 as expected
but still commits only 64 checkpoints and fails at the same q65/gates 256--259;
minimum K worsens to 536,203 (excess 11,915), with peak/visits
645,044/75,255,249.  No sensitivity transcript is published because its altered
ladder is not contained in the pinned v6 configuration source; the opt-in regression
recreates the numerical comparison directly.  Thus neither checkpoint halving alone
nor this one-rung repair crosses the D frontier.  This remains an independent
diagnostic sensitivity screen, not v7, a policy or a parent/child certificate
continuation.  It writes no boundary, transition, sidecar, exact-Hubbard claim or
READY component, and certified depths remain 3/2.
That controlled capability-extension route is now complete.  A separately pinned
wrapper compiles the exact arithmetic-v2 bytes and changes only
`max_retained_K: 524,288 -> 540,672`; the diagnostic configuration changes only
the candidate/output K ceilings, while the 786,432 live/digest and all other caps
remain fixed.  Magnetization appends `540,672` for 30 candidates.  Double occupancy
keeps 32 slots by deleting `65,536`, which is infeasible in every one of the 65
pinned four-gate baseline rows and is never selected, then appending `540,672`.
The screen runs the exact pinned four-gate parent's private entrypoint and records
the v6 configuration, v2 arithmetic and capability wrapper as distinct source
roles; it is not a v7 execution parent or a policy.

Magnetization hands the old q78 failure to `K=540,672`, selects the same value at
q79 and q80, and reaches the precommitted 80-checkpoint horizon with all 80 commits.
The q78--80 pretruncation counts are `643,624/624,312/587,900`; overall peak/visits
are `643,624/87,032,691`.  Its canonical transcript SHA-256 is
`d4a0f952a3d4a93bd78d370fae50c5c043e33caa4d1452e841987976e43354a5`.
Double occupancy hands q65 to `K=540,672` but fails at q66, gates 260--263, where
the 679,285-term expansion requires minimum effective `K=558,598`, 17,926 above
the new retained maximum; overall visits are `77,762,021`.  Its canonical
transcript SHA-256 is
`5ced57f7f6fc8aef50a6536920243d00af083b0a113b09d19f239bc1266fd8a5`.
Thus M reaches the planned old-q40 comparison horizon, while D exposes a new
K-ceiling rather than a live/digest stop.  Neither finite horizon completes the
288-checkpoint mapped step, and no policy, witness, boundary, transition, READY
component or certified-depth increase is created.

That split discriminator has now been executed.  The M branch changes only its
runtime horizon from q80 to q82 and replays from q1; the q80 transcript is used
only for post-replay prefix validation, never as a state-resume input.  Its exact
q1--80 prefix is unchanged, but q81/gates 320--323 fails at minimum effective
`K=545,129`, 4,457 above the retained maximum.  The q81 pre-count is 597,254 and
overall peak/visits are `643,624/89,253,151`.  The canonical transcript SHA-256 is
`0486a8b19077de9e90f134c7b3c0d43fdf3504a4876d6e0b2c3d01b37b89cb52`.

The D branch uses a separately pinned direct-v2 wrapper that changes only
`max_retained_K: 524,288 -> 573,440` and `max_candidate_count: 32 -> 33`; the
K=540,672 wrapper is route-lineage evidence only and is not executed.  Appending
`573,440` preserves the old 32-rung order.  Exact q1--65 state/history and every
old candidate row remain unchanged, and q66 preserves the old propagation and
first 32 rows before index 32 becomes first feasible.  D then selects `573,440`
at q66--68, with pre-counts `679,285/688,548/630,616`, and reaches the aligned q68
horizon with 68/68 commits; peak/visits are `688,548/82,618,707`.  Its canonical
transcript SHA-256 is
`b1f072c84cc676151fe3cddbb8a0db445df946f299dbb81f41e34f765d30dfc8`.
Both branches remain diagnostic-only and leave certified depths at 3/2.

The next discriminator again splits cleanly.  M needs a separately pinned
`K=557,056` capability and a 31st candidate through q82; that rung covers the q81
minimum by 11,927.  D has not exposed a new failure, so its least-assumptive next
move is a same-cap `K=573,440`/33-slot horizon-only extension through the next
aligned q70 boundary.  Neither route may predeclare the unmeasured q69--70 result.

The Majorana implementation audit selects a certificate fork of registered
`MajoranaPropagation v0.3.0` at `main@b7849cb`, not the inferred paper snapshot,
which predates a documented splitting-sign fix.  The fork must pin a complete Julia
Manifest/PauliPropagation version, sort composite bitmasks deterministically, and add
outward coefficient intervals plus a post-dedup per-gate/stage dropped-L1 ledger.
That work is a parallel implementation-custody route rather than authority for the
Python interval certificates.  The current v2 policies have now been exhausted by
formal maximum-K screens; any continuation to a larger ladder or different method
requires a new precommit.  Per-observable adjacent-transition depth remains separate,
and neither the old `K=262,144` diagnostics nor the v2 design transcripts can be
promoted in place.

These campaign, reference, proof-kernel, mapping, checkpoint, commutator,
grouping-screen, fixed-generic-bound no-go, observable-Taylor-step and
double-occupancy-cluster no-go, shared two-step L8 intervals, the
magnetization-only step-3 interval and the depth-2 double-occupancy screen remain
standalone preflight, qualification and conformance tools. They have **not** yet
been added as components of `fermi_hubbard_evidence.py`, so they do not alter the
current outer `READY_FOR_BENCHMARK` gate.

The focused 70-claim ledger is fully adjudicated: 56 unanimous verified, 8
split/partial accepted, and 6 refuted as written, with every mandatory rewrite
retained in `claim-status.jsonl`.

## Final deliverables

- [Chinese executive brief](EXECUTIVE_BRIEF_ZH.md)
- [Full technical synthesis](FINAL_SYNTHESIS.md)
- [Final adversarial review](FINAL_ADVERSARIAL_REVIEW.md)
- [Post-ledger June 2026 matchgate/QC-AFQMC update](POST_LEDGER_MATCHGATE_UPDATE.md)
- [Evidence-bounded 2D Fermi--Hubbard resource model (Chinese)](RESOURCE_MODEL_FERMI_HUBBARD_ZH.md)
- Reproducible model: `fermi_hubbard_resource_model.py`, scenario
  `fermi_hubbard_resource_scenario.json`, Fig. 5 candidate points
  `fermi_hubbard_fig5_candidate_points.json`, term-order contract/validator and
  cross-route sequence comparator/template, convergence template/assessor,
  first-step ledger contract/template/validator, unified evidence manifest
  contract/template/orchestrator, native transition contract/template/validator,
  surface-code place-and-route contract/template/validator,
  standalone measurement-campaign preflight contract/template/validator and
  standalone reference-qualification contract/template/validator,
  source-pinned Pauli propagation subcertificate contract/template/checker,
  L=2 proof-kernel conformance witness,
  source-pinned L=2/L=3 Hubbard-to-JW mapping contract/template/validator,
  exact bitset Pauli/checkpoint prototype,
  source-pinned full L=2 checkpointed propagation contract/template/checker,
  source-pinned L=2/L=3/L=8 Strang commutator contract/template/checker,
  source-pinned L=8 Strang grouping-screen contract/template/checker,
  source-pinned fixed-generic-bound infeasibility contract/template/checker,
  base-source-pinned observable Taylor one-step checker,
  source-pinned double-occupancy D3 symbolic fixture and fixed-cluster no-go
  contract/template/checker,
  source-pinned L8 mapped one-step interval contract/template/checker,
  source-pinned L8 two-step parent--child interval contract/template/checker and
  four canonical boundary sidecars,
  source snapshot and snapshot notes,
  and the dynamic-JW primary-source evidence ledger,
  plus the FSN primary-source evidence ledger,
  and the native-fermion primary-source evidence ledger,
  an L=2 dual-observable deterministic screening pilot, and unit tests
  `test_fermi_hubbard_resource_model.py` /
  `test_term_order_validator.py` /
  `test_term_order_cross_route.py` /
  `test_fermi_hubbard_convergence.py` /
  `test_fermi_hubbard_l2_pilot.py` /
  `test_first_step_ledger_validator.py` /
  `test_fermi_hubbard_evidence.py` /
  `test_native_transition_validator.py` /
  `test_surface_place_route_validator.py` /
  `test_measurement_campaign_validator.py` /
  `test_reference_qualification_validator.py` /
  `test_operator_propagation_certificate_checker.py` /
  `test_operator_propagation_l2_witness.py` /
  `test_hubbard_jw_mapping_validator.py` /
  `test_pauli_bitset_backend.py` /
  `test_operator_propagation_checkpointed_l2.py` /
  `test_hubbard_strang_commutator_checker.py` /
  `test_hubbard_strang_grouping_screen.py` /
  `test_hubbard_strang_generic_bound_no_go_checker.py` /
  `test_hubbard_strang_observable_taylor_step_checker.py` /
  `test_hubbard_d3_double_occupancy_cluster_no_go_checker.py` /
  `test_hubbard_l8_observable_interval_step_checker.py` /
  `test_hubbard_l8_observable_interval_two_step_checker.py`
- Batch reviews: `BATCH1_GAUSSIAN_NONGAUSSIAN_REVIEW.md`,
  `BATCH2_DPP_REVIEW.md`, and `BATCH3_ENCODING_HARDWARE_REVIEW.md`
