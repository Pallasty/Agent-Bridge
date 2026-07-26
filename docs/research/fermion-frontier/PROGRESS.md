# Research progress ledger

Status date: 2026-07-25

## 2026-07-25 — FH-L8 D45--D49 fixed64 resource稳定性与归档闭环

- D45 固定64 受控复放保留 CPU-0、512 MiB AS、零 swap 条件下 67 动作、64 representative 的 replay
  约束证据，并保持 `packed_q3_reads=0`、`full_53_scientific_execution_authorized=false`。
- D46 重复复放形成同条件区间，结合 D42–D46 的结构摘要与动作计数一致性，进入 D47 资源区间汇总。
- D47 形成 D45/D46 区间汇总；D48 执行第三次同约束样本复放（样本 3：0.87s / 38,336 KiB）；
  D49 决议 `VERIFIED_D49_CONTROLLED_RESOURCE_STABILITY_DECISION` 且 `resource_stability_decision=stabilized`，
  停止扩规模复放。
- D47 固定证据包（manifest/result）静态核验通过（D47 status 和 next-gate 正确），随后由 D48
  consumer check 与 archive 两步推进为 `FH_L8_REPRO_PACKET_D47_ARCHIVE_CLOSED`，未进行任何科学动作，
  未解锁 full-53 外推。

## 2026-07-23 — FH-L8 D23 non-authoritative resource guardrail

- Concurrent D23 converts the D21 5/4-margin planning values into a
  2,750,812,950-byte / 13,622-file capacity guardrail for 53 × 256 spill files, manifests and one
  target.
- Returned `NO_GO_D23_FULL_53_RESOURCE_ENVELOPE_INCOMPLETE`: no auditable worst-case memory or
  runtime bound and no external resource reservation exists.
- D23's resource next gate is
  `FULL_53_EXPLICIT_MEMORY_RUNTIME_AND_EXTERNAL_RESOURCE_RESERVATION`. D22-R's production
  scientific-kernel binding remains a separate unmet prerequisite.

## 2026-07-23 — FH-L8 D22 synthetic executable/recovery validation

- The concurrent D22 lane at `4ad711c775b0079dc4554710805a2bbdee47e86f` exercised 53
  two-row synthetic shards, eight partitions, frontier-17 resume and basic gap/orphan/hash/
  no-replace failures. It performed no packed-q3 read or scientific action.
- D22-R independently implemented a three-shard/four-partition fixed-record data plane with
  exclusive lock, manifest-enumerated partition admission, per-shard receipt SHA-256 chain,
  exact-frontier resume, signed merge, target manifest and terminal-receipt-last publication.
- Clean execution and one-shard interruption/resume produced identical 208-byte targets
  (`f68d75d3...a2ca2876`) and identical terminal receipts (`dbe9f4bb...442efef3`).
- Live fault replay verified exact classifications for gap, overlap, orphan bytes, partition hash
  drift, busy lock, partial final publication and production attempt.
- Frozen D22-R chronology after a pre-contract refreeze:
  `bb85c6734a92aad27731c3d6d8561a95fed2aa25` ->
  `7362c8b434e3aedf056ca355db4dc9fb3b5f659e` ->
  `7a3f8bbfedc1e589fd14a9a77e1597752f5aeb12`.
- Production checkpoint reads, q3 rows, scientific-kernel calls, full-53 authorization and full q4
  remain zero/false. Next gate:
  `FULL_53_SHARD_SCIENTIFIC_KERNEL_BINDING_AND_WORST_CASE_RESOURCE_PROOF`.

## 2026-07-23 — FH-L8 D21 full-53 resource-authorization readiness

- Audited the merged D20 source rather than accepting its status label as executable evidence.
  AST inspection proves that `run()` validates the plan and then unconditionally raises; the file
  contains no loop, scientific-kernel reference, action-file write or manifest merge.
- Admitted D20 only as a declarative protocol plan. Exact 53-shard iteration, per-shard spill and
  receipt publication, resume-frontier validation, full merge, atomic target publication, terminal
  resources and tiny-fixture recovery tests are all absent.
- Scaled D18-C's bounded observation by exact integer ceiling for planning only: 1,446,386,155
  spill bytes, 707,025,856 target bytes and 3,014,449,254,665 ns. A 25% margin gives
  2,691,765,014 combined spill/target bytes and 3,768,061,568,332 ns, but none is an authoritative
  worst-case disk, runtime or memory bound.
- Froze an acyclic checker -> contract -> result chain after a pre-contract checker refreeze:
  `273dd1216be28772acb8a83cc9836aceb0a87086` ->
  `994c8d3f43aa0f1bc68b984610b65d00978f8dab` ->
  `0b3e8a1072c9f0e442a2e7353c61726e7a236f3c`.
- Returned `NO_GO_D21_FULL_53_RESOURCE_AUTHORIZATION_EXECUTABLE_IMPLEMENTATION_ABSENT` with zero
  scientific calls. Full q4, all 53 shards, q5 and every downstream authority remain false.
- Next gate:
  `FULL_53_SHARD_EXECUTABLE_CONSUMER_AND_TINY_FIXTURE_RECOVERY_VALIDATION`.

## 2026-07-23 — FH-L8 D19/D20 full-run decision and protocol plan

- D19 rechecked the bounded D18-C conclusion and correctly kept full-53 authorization false,
  returning `NO_GO_D19_FULL_53_SHARD_REQUIRES_NEW_IMPLEMENTATION_AND_AUTHORIZATION`.
- D20 pinned the 213,099-row source and a declarative 53-shard / 256-partition protocol while
  authorizing zero rows and zero kernel calls. Its action entrypoint deliberately rejects.
- D21 supersedes any interpretation of D20 as an executable consumer; D20 remains useful only as
  a protocol-plan input.

## 2026-07-22 — FH-L8 D18-C fresh-exclusive packed-q3 bounded preflight V2

- Deprecated the first D18-C attempt after a verified zero-action failure. Its implementation and
  contract commits were `732643eb856da31e68541df603ed88481a9063cd` ->
  `34006de5f3548432c7f6e24e1fd3527fab49cb53`; the pre-launch contract checker rejected legacy
  D18's `elapsed_seconds:66.543` under the generic integer-only JSON reader. No launcher, scratch,
  source row, kernel action or result commit followed, so V1 is an audit record rather than
  scientific evidence.
- Restarted from baseline `26c49b6e7bcddc22a1fc88f3743befa1b6de4446` and froze the V2
  implementation -> authorization -> result chain as
  `8cf944e42fd9a981cd78f584885a5c525dd2abd9` ->
  `9e4266600439143d7fdaaf76331dc9780cecd55c` ->
  `10d56da28318d622e791f5f5d39932d7a4a39e11`. The three commits add only the four
  implementation/test files, then the contract, then the result. The narrow V2 legacy reader first
  checks exact D18 SHA-256 and treats its finite decimal only as an opaque string; main D18-C
  contract/result JSON remains integer-only.
- Fully admitted all 213,099 packed-q3 records (6,819,168 bytes; SHA-256
  `db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231`) and the complete rank
  permutation before action, then rehashed the source afterward. Exactly the first 4,096 unique
  sorted rows were acted on; 4,096 spill evaluations plus 4,096 validation-replay evaluations
  produced 8,192 frozen `_reduced_column` calls. The remaining 209,003 source rows were not acted
  on.
- Compiled/parsed the scientific context from one pre-action byte snapshot of the D5 checker, D5
  contract, D4 checker and commutator backend. All four working bytes and custody metadata were
  rehashed after action while execution HEAD/status remained frozen, and no transitive worktree
  module or contract load occurred during action.
- Materialized 868,786 spill records / 27,801,152 bytes in 256 partitions, with 868,786 reduced
  columns, 22 projected-zero outputs and zero dropped zero coefficients. The bounded partial target
  contains 424,682 records / 13,589,824 bytes with SHA-256
  `8b43b76f1e7a45f12e220905bcba41dc7cfef9fce66f0257cb3c9dff9623fa5f`.
- A bounded 256-way external merge binds the target to globally sorted semantic SHA-256
  `da049d945738630c66b8118ec58627a09910887e7263f91e4b08417ef7bafb34`, exactly matching the
  second-pass naive aggregation. Legacy D18's matching counts/digest remain a non-authoritative
  diagnostic guard and do not restore its execution authority.
- The official scope enforced `MemoryMax=536,870,912`, `MemoryHigh=402,653,184` and zero swap.
  Runner cgroup/systemd peak was 224,747,520 bytes, process max RSS was 193,392,640 bytes, the
  pre-publication elapsed interval was 57,941,070,334 ns, and all pressure/OOM deltas were zero.
  The launcher recorded exit 0, zero stderr, then stopped the unit to `inactive/dead`.
- Static result checking returns
  `D18C_COMMITTED_RESULT_SCHEMA_AND_GIT_PROVENANCE_ONLY` and explicitly does not certify external
  scratch, executed authority or scientific outcome. Rechecking the retained exact 264-file scratch
  verifies terminal/launcher receipts, captured outputs, all spill/target bytes and semantic
  digests, returning `VERIFIED_D18C_RESULT_AND_EXTERNAL_TERMINAL_EVIDENCE`.
- The launcher command digest binds the official execution worktree's absolute runner, contract and
  capture paths. External checking from another worktree therefore fails closed with
  `launcher command digest drift`; a normal clone can recover only static provenance unless the
  original custody path and untracked scratch are retained or a future evidence-transfer contract
  is separately frozen.
- Authority is limited to `bounded_4096_preflight_executed=true` and
  `partial_q3_to_q4_action_executed=true`. The partial target is forbidden as q4, contraction, q5
  or downstream numerical input. Full q4, all 53 shards, D12/D13 and D16-W numeric authority,
  remainder/error/reference/hardware/advantage/READY claims remain false.
- Active next gate:
  `CLEAN_BOUNDED_PREFLIGHT_REVIEW_AND_FULL_53_SHARD_AUTHORIZATION_DECISION`. No full-shard action
  is authorized by this result.

## 2026-07-22 — FH-L8 D18 legacy bounded observation

- The legacy D18 lane used a fresh scratch root for one 4,096-source spill/sort/merge and reported
  868,786 spill/reduced records, 22 projected-zero outputs and 424,682 partial targets. Its target
  is 13,589,824 bytes with SHA-256
  `8b43b76f1e7a45f12e220905bcba41dc7cfef9fce66f0257cb3c9dff9623fa5f`, matching its same-kernel
  naive aggregation.
- It observed a 218,451,968-byte peak and 66.543-second elapsed time under a 1 GiB / 768 MiB
  high-water / zero-swap scope, but did not execute all 53 shards, q5 or any error/READY route.
- D18-C does not admit the legacy execution as authority. It pins the exact D18 result
  (`51643e67fbb33148b231a4bf1251923c621fd11b`, SHA-256
  `7fa505485fc718db39d9918ec459094f3766f014fd2ddee7d108f01fae4842c4`) only as a
  preregistered, fail-closed reproducibility comparator.

## 2026-07-22 — FH-L8 D17 vector custody gate

- Reconfirmed the 213,099-record packed C3 as the only admissible q3 vector and kept the legacy q4
  target quarantined. No admissible q0, q1 or q2 packed payload was available.
- Returned `NO_GO_D17_Q0_TO_Q4_DUAL_VECTOR_CUSTODY_INCOMPLETE`: complete q0--q4 vector custody and
  dual-vector contraction could not be materialized. This is a custody no-go, not a numerical
  q3 -> q4 feasibility result.
- Authorized no bounded or full action. The only successor was a separately frozen
  fresh-exclusive packed-q3 consumer with full source validation, manifest-only merge and an
  independently authorized 4,096-source preflight.

## 2026-07-22 — FH-L8 D16-F packed-consumer custody forensic

- Froze the globally unique
  `FH-L8-INDEPENDENT-REFERENCE-D16-PACKED-Q3-CUSTODY-FORENSIC-V1` unit as a strict
  checker -> contract -> result chain:
  `ad20d45f14016bbc34bd61a3685c581c9727ef20` ->
  `f7d9fdf2d24e22973d0409737c2182fc9266e6e9` ->
  `6e3230f55ddc68e7ea39e6513f28c2cfb5c0ce6e`. The result was absent at both freezes;
  D16-F executed no Hamiltonian action.
- Independently admitted packed C3 `784f01b8e3c589b7c6ab25773f93937d5a1344f8` as the only
  q3 source for a future clean consumer: all 213,099 fixed-width records, the
  `db2ce0a338a...f840231` checkpoint digest, the 53-shard manifest and the C3 result/terminal
  receipt were rebound exactly. This is source admission, not q3 -> q4 execution authority.
- The retained 256-partition spool contains the intended shards 0--52 plus one extra copy of
  shards 25--51: 6,912 receipt-unbound gaps, 23,126,970 duplicate records and 740,063,040
  duplicate bytes. Every gap exactly matches one receipt-bound chunk, and the complete forensic
  manifest SHA-256 is `869008057db5eb93129aca801dce2dab458ec2cfc6f7fa2894bf04538cb4d79b`.
- No provenance proves that the retained target was produced from exactly that contaminated spool.
  The legacy parallel-D11 full-action target's reported 10,785,545 records and digest are therefore
  quarantined as broken production custody and are not authoritative q3 -> q4 results. The D16-F
  result status is
  `NO_GO_D16_LEGACY_TARGET_CUSTODY_BROKEN_ASSOCIATED_SPOOL_DUPLICATED_TARGET_QUARANTINED`.
  This `NO_GO` is the narrow custody/admission decision; it is not a numerical feasibility no-go.
- D12's q4 -> q5 costs remain reproducible only as post-hoc arithmetic conditional on the
  quarantined q4 count, so D12 has no scientific no-go authority. D13 inherits that invalid input;
  neither its full-q5 no-go nor its route-exclusivity claim is authoritative. D14--D15 abstract
  algebra may remain design-only but must be reattached to a clean numeric lineage.
- The later remote D16-W word-family unit has the distinct full ID
  `FH-L8-INDEPENDENT-REFERENCE-D16`; it does not collide with D16-F's complete contract ID and
  does not rewrite the frozen D16-F chain. D16-W's atomic hopping-word G-equivariance rejection may
  be retained as design-only. Its full-H moment, pinned q0 -> q4 custody and q4-count/byte resource
  path depend on the quarantined D11/D12 lineage and are isolated; D16-W execution authority was
  already false.
- The official read-only audit scanned 2,523,861,175 external bytes with 1 MiB reads in 8.997 s.
  Its fresh cgroup peaked at 112,730,112 bytes, process RSS peaked at 38,510,592 bytes, and swap and
  all memory-event deltas were zero. This snapshot ends before result serialization/publication;
  D16-F does not claim a terminal execution/resource receipt or publication-resource attestation.
- The built-in composite `--mode external` transparently remains
  `INDETERMINATE_D16_EXTERNAL_CUSTODY_AUDIT`: its preceding static phase raised the same-scope
  initial peak to 77,021,184 bytes, above the frozen 67,108,864-byte initial cap. An independent
  static CLI replay passed, and a second fresh scope running only frozen external custody plus the
  embedded-manifest comparison also passed: identical manifest SHA-256, 5,472,872,990 ns elapsed,
  98,095,104-byte cgroup peak, 33,546,240-byte RSS, zero swap and zero event deltas. This split
  replay is reproducibility evidence, not a newly committed terminal receipt.
- Active next gate:
  `FRESH_EXCLUSIVE_PACKED_Q3_CONSUMER_IMPLEMENTATION_AND_BOUNDED_4096_PREFLIGHT_AUTHORIZATION`.
  Neither the bounded preflight nor the full 53-shard action is yet execution-authorized.

## 2026-07-22 — FH-L8 packed depth-3 quotient checkpoint D8--D11

- D8 froze the 213,099-record, 32-byte packed-checkpoint and 53-shard protocol without executing
  scientific computation or materializing a checkpoint.
- D9 rebuilt q3 and measured only the first 4,096-source quotient-H preflight, then failed closed
  because observed `memory.current` was approximately 9 GiB while memory and swap limits were
  unlimited.
- D10 reproduced that bounded preflight in an enforced 1 GiB / 805,306,368-byte (768 MiB)
  high-water / zero-swap transient scope. This removed the environmental blocker but retained
  `full_run_authorized=false`.
- D11 froze checker and contract before outcome, replayed q0→q1→q2→q3 under that envelope and
  materialized 213,099 sorted fixed-width records. The 6,819,168-byte checkpoint SHA-256 is
  `db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231`; its q3 coverage is
  1,704,285 full states.
- The D11 execution observed a 406,224,896-byte cgroup peak, 414,253,056-byte process max RSS,
  zero swap and no cgroup memory events. The fourth call was rejected before the backend and zero
  q4 records were emitted.
- A post-C3 heavy replay in a separate fresh scope reproduced the committed checkpoint byte for
  byte; it observed a 418,836,480-byte cgroup peak, 427,343,872-byte process max RSS, zero swap and
  no cgroup memory events.
- After integration, zeroing each packed record's seven-byte tail reproduces the parallel
  `FH-L8-INDEPENDENT-REFERENCE-D11` base receipt's payload SHA-256 `09758478e...77017` exactly.
  This establishes a base-view/rank-extension relationship, not external-payload availability or
  added execution authority.
- The parallel lane's 4,096-source spill/sort/merge preflight produced 424,682 targets and matched
  its naive signed quotient calculation. It did visit bounded q3 source rows, unlike the packed
  C3 generation/replay, but did not run all 53 shards or finish the fourth action. At D11 close a
  separately frozen consumer still had to bind C3, its terminal receipt and full packed validation;
  D16-F now satisfies that source/custody gate without authorizing execution.
- The D11 artifact status remains
  `VERIFIED_D11_PACKED_DEPTH3_QUOTIENT_CHECKPOINT_MATERIALIZED_NO_Q4_AUTHORITY`, while active
  downstream authority is now controlled by D16-F's fresh-exclusive-consumer gate. Target
  cardinality, target vector, q3-to-q4 feasibility, remainder, R100, hardware, quantum advantage
  and READY all remain uncertified. See `FH_L8_PACKED_Q3_CHECKPOINT_D11_ZH.md`, the committed D11
  bundle and `test_fh_l8_packed_q3_checkpoint_d11.py`.

## 2026-07-22 — FH-L8 depth-3→depth-4 quotient-H design gate

- Froze globally unique contract `FH-L8-QUOTIENT-H-D3-TO-D4-DESIGN-GATE-V1` after a checker-only
  commit and before any contract, result, runner or implementation existed.
- Bound D5B signed quotient semantics and D6 support-only byte-table evidence as distinct,
  non-additive inputs on shared D4 data.
- Separated `47,947,275` raw candidate actions, `383,578,200` candidate group images and
  `1,704,792` source-canonicality images; total planned group images are `385,282,992`.
- Designed 53 source shards, 32-byte fixed records, deterministic 256-way partitioning and bounded
  external merge under a future 1 GiB / zero-swap envelope. No runtime/RSS feasibility is certified.
- The next bounded unit is a separate packed depth-3 quotient checkpoint protocol. No fourth Krylov
  Hamiltonian action, target vector, remainder, R100, reference or READY authority was created.

## 2026-07-22 — FH-L8 D5/D6 descendant scope reconciliation R2

- Bound the historical byte-table D6 outcome to the signed-prefix D5A lane by exact source hashes;
  its checker/contract/result first appeared together, so preregistration remains unestablished.
- D6's parallel implementation on the shared D4 inputs matches the full D5B depth-3 count
  `1,704,285→213,099`, but certifies only support-orbit canonicalization; quotient amplitudes and
  the fourth H action were not executed.
- The result retains only completion within the 240-second cap. The previously reported `14.856s`
  is an unretained console observation and not a certified performance number.
- Future quotient-H work requires a new globally unique contract ID plus separate D5B semantic and
  D6 canonicalization pins. Current authority is design-only.

## 2026-07-22 — FH-L8 D5 dual-track identity reconciliation

- Preserved two immutable D5 children of the same D4-containing base while recording that both use
  the ambiguous legacy internal ID `FH-L8-INDEPENDENT-REFERENCE-D5`.
- Assigned unique aliases to the signed-D4 prefix/custody lane and the fully preregistered
  symmetry-quotient lane; bare-ID evidence lookup or authorization is now forbidden.
- The full lane closes the other lane's unmeasured full-depth-3 and quotient-transition gaps without
  replacing its provenance or validating its prefix digest. Evidence is not additive.
- The reconciled ceiling is D6 design only; D6 execution and every error/reference/READY claim remain
  unauthorized.

## 2026-07-22 — FH-L8 symmetry-orbit quotient D5

- Official replay verified the eight-element Néel-stabilizing D4/conditional-spin-swap action,
  exact CAR phases, Hamiltonian equivariance and both trivial observable characters.
- Full and quotient Krylov transitions agree exactly through source depths 0--2; depth-3 full states
  `1,704,285` compress to `213,099` representatives.
- The projected next-action upper bound `47,947,275` is below 300M; audit group actions `13,831,456`
  remain below 16M under the frozen 1 GiB, zero-swap, 600-second envelope.
- This lane is now named `FH-L8-D5-EVIDENCE-SYMMETRY-ORBIT-QUOTIENT-V1`; D6 design is eligible only.
  No fourth action, D6 remainder, cumulative, R100, reference or READY authority was produced.

## 2026-07-22 — FH-L8 scalar supremum D4

- Derived exact two-step remainder slacks and M6 ceilings: 3.048B / 3.324B.
- Closed the fixed generic derivative bound (`2*2432^6`) and current global-norm Cauchy majorant as
  numerically inadequate by exact rational comparisons.
- Recomputed exact-CAR Krylov reachable-state counts `1,225,24421,1704285`; the next action floor
  383,464,125 exceeds the 300M cap and was not executed.
- Selected symmetry-orbit-compressed scalar Krylov. No D6, cumulative, R100, reference or READY bound.

## 2026-07-22 — FH-L8 degree-six streaming D3

- Replaced the 100,947-prefix resident cache with a deterministic DFS trie; peak live-path terms are
  only 13,824 / 21,888 for magnetization / double occupancy.
- Proved the fixed streaming Pauli-L1 architecture exceeds 2B prospective D6 pairs after only
  3,958 / 1,108 of 20,349 depth-five leaves; no D6 child was materialized.
- Fixed Pauli-L1 MITM remains blocked by the absence of an exact half-record composition identity;
  this is not a general MITM no-go.
- Next route is scalar derivative supremum enclosure. No D6, two-step, R100, reference or READY bound.

## 2026-07-22 — FH-L8 two-step scalar defect D2

- Corrected the scalar telescoping architecture: D1 cannot be multiplied or added as an operator-norm
  telescoping term, so D2 directly evaluates the 17-stage two-step cumulative scalar difference.
- Exactly merged D3--D5. Both odd Néel coefficients vanish; D4 is `230/3` for magnetization and
  `-115/3` for double occupancy.
- Localized the first uncontrolled object to the degree-six remainder, requiring 74,613 weak
  compositions and 100,947 prefixes versus fixed 4,096 caps.
- Status is failure-local only; no two-step cumulative bound, full R100, reference or READY authority.

## 2026-07-22 — FH-L8 state-specific defect D1

- Exactly merged the degree-four product-minus-ideal observable defect and evaluated it on the
  checkerboard Néel state: `115/6` for staggered magnetization and `-115/12` for double occupancy.
- Enumerated all 1,287 degree-five product remainder paths and the ideal fifth commutator.
- Certified total k0-to-k1 expectation-defect bounds `8784399/6400000000000` and
  `11682481/7680000000000`, respectively 54.90% and 60.85% of the `1/400000` allocation.
- The authority remains one-step-only; evolved steps, full R100, physical reference and READY remain
  unassessed.

## 2026-07-21 — FH-L8 independent reference route S0

- Verified both exact R100 uniform-supremum floors exceed the `1/4000` observable allocation.
- Closed the ordinary 803-layer support cone because it saturates the L8 OBC diameter 14.
- Selected `PER_STEP_STATE_SPECIFIC_EXACT_DEFECT_LEDGER`; both observables have exact zero
  checkerboard-Néel `k0` D3 expectation, while rotated-integrand cancellation remains unassessed.
- Froze `FH-L8-INDEPENDENT-REFERENCE-D1` as the next unit. No physical reference, full-R100 bound,
  or READY authority was produced.

## State labels

- `VERIFIED`: three valid independent votes and no two-vote refutation.
- `PROVISIONAL`: two supporting votes but fewer than three total votes.
- `REFUTED`: at least two independent refutation votes.
- `UNVERIFIED`: fewer than two valid votes.
- `INFERRED`: synthesis or cross-domain mapping not directly asserted by a
  source.

Split suffixes retain the vote tally: `verified_2_1` means two passes and one
refutation; `verified_2_0_1` means two passes and one unverified verdict. Their
replacement wording and disagreement are mandatory, not optional caveats.

## Completed evidence clusters

The inherited completed rounds support these clusters, subject to the original
source-level caveats preserved in the round result files:

1. Luttinger constraints, ersatz Fermi liquids, and explicit continuity
   failures or modifications in SYK, FL*, and fractionalized phases.
2. Nielsen-Ninomiya as a lattice-continuum no-go boundary and
   Ginsparg-Wilson as a premise-relaxing construction.
3. Axial anomaly as a quantum violation of a classically conserved current.
4. Matchgate designs and shadows as a polynomial fermionic-Gaussian
   computational representation, with high practical polynomial costs.
5. Graded/Grassmann tensor-network sign handling as asymptotically low
   overhead rather than an automatic speedup.
6. Determinant/Pfaffian neural quantum states, their expressivity, cubic
   algebraic costs, and orthogonal acceleration routes.
7. Fast exact DPP sampling, conditional DPP coreset advantages, volume-sampling
   identities, and the sampling-versus-MAP tractability boundary.

## Focused verification clusters

| Cluster | Candidate claims | Current state |
|---|---:|---|
| DPP / negative-dependence ML | 30 | 28 verified, 2 refuted/rewrite-required |
| Non-Gaussian fermionic simulation | 10 | 9 verified, 1 refuted/rewrite-required |
| Fermion-to-qubit encoding / native hardware | 15 | 12 fully verified, 2 verified after partial rewrite, 1 refuted |
| Gaussian-state manifold geometry | 15 | 13 verified, 2 refuted/rewrite-required |

All 70 claims in the focused gap-3/4/5 ledger are now adjudicated: 56 unanimous
verified, 8 split/partial accepted, and 6 refuted as written. There are no
unreviewed focused claims.

## QA findings

- Round 1 metadata reports 11 post-synthesis findings, while the original
  narrative called them 10. The JSON result count is authoritative.
- `unverified: 0` in rounds 1 and 2 describes the selected 25-claim voting
  batch, not all 120/119 extracted candidates.
- Five round 3 DPP coreset claims were accepted with only 2-0 votes. They are
  now closed by three new independent reviews; all five passed with explicit
  construction and dimensionality limits.
- The DPP batch task initially pointed to indices 50–54. The persistent ledger
  shows that those are encoding claims; the correct fifth DPP source is at
  indices 55–59. All three reviewers used the corrected index set.
- The DPP source graph has substantial author overlap and survey-to-primary
  dependencies. Three independent reviews do not constitute three independent
  source replications.
- The encoding batch separates classical mapping preprocessing, compiled CNOT
  count, logical depth, physical execution time, and fault-tolerant space-time.
  Equal asymptotic depth across two papers does not make these resources
  interchangeable.
- Encoding claim 46 was unanimously refuted because it changed a five-layer
  native-gate depth statement into five total gates. Claim 43 passed 2–1 only
  as a four-mode H2 hardware observation without a general causal noise claim.
- The 2023 native-hardware maturity statement is now historically incomplete.
  Separate 2026 experiments demonstrate high-fidelity fermionic collisional
  gates and programmable fermionic array preparation/readout, but not yet the
  complete integrated processor proposed in PNAS.
- A June 2026 Physical Review Research accepted paper was found after the
  ledger closed and separately reviewed 3–0. Its 24-qubit hybrid QC-AFQMC
  workflow is an engineering milestone; `9x` is a tuned circuit-throughput
  result and `656x` is a normalized/extrapolated post-processing estimate, not
  an end-to-end quantum speedup.
- Claude produced no unified final report. The takeover's synthesis and final
  adversarial review are now complete in `FINAL_SYNTHESIS.md` and
  `FINAL_ADVERSARIAL_REVIEW.md`, with a Chinese brief in
  `EXECUTIVE_BRIEF_ZH.md`.

## Roadmap execution update

The first execution task now has a reproducible planning deliverable in
`RESOURCE_MODEL_FERMI_HUBBARD_ZH.md` and
`fermi_hubbard_resource_model.py`. It fixes an open-boundary spinful square
Fermi--Hubbard physics target, a shared Strang-step planning input, an additive
target-error ledger, and route-specific accepted-shot/acceptance/mitigation
accounting. The common term-group order is reconstructed from dynamic-JW Fig. 14
but remains a validation target rather than a completed cross-compiler fact. The
model separates:

- source-reported leading dynamic-JW resources;
- finite-size FSN/dynamic candidate fits restricted to the Fig. 5 domain;
- a new graph-coloring native schedule under the common group-order target;
- bare-qubit layer time from non-CNOT time;
- lattice-surgery ladder rounds from complete encoding switches, code cycles,
  auxiliary/routing/factory patches, and magic-state supply.

The model intentionally returns `UNRESOLVED` for complete totals and wall-clock
quantities that the primary sources do not determine. The next update must
supply individual-term cross-compiler validation, a joint dual-observable
convergence/covariance study, full first-step circuit exports, native consecutive-matching
movement benchmarks, and real compiler/measured data for the now-executable
distance-`d` surface-code place-and-route ledger before claiming an end-to-end winner.

The first of those interfaces is now executable: `term_order_contract.json` pins
the reconstructed group-level Strang order and fusion rules,
`term_order_validator.py` validates route exports, and the native fixture passes
group-level checks. Individual-term exports for dynamic-JW and FSN are still
absent, so the research status remains “target defined, cross-compiler equality
unverified.” A stricter `term_order_cross_route.py` comparator now requires all
five route exports to carry individual-term lists and compares their raw sequence
fingerprints; its empty manifest remains `UNRESOLVED`, and synthetic same-sequence
fixtures are test-only evidence. The comparator also rejects an export whose embedded
`route` differs from its manifest key, so one export cannot be relabeled as independent
evidence for another route.

The target-`R` interface is also executable in
`fermi_hubbard_convergence.py`. Schema v2 fixes the canonical
`staggered_magnetization` / `double_occupancy` pair, their definitions and
physical ranges, the full planned refinement grid, and target `R=100` before
route data are inspected. Every route must supply the exact planned grid as
joint-observable points with a finite symmetric positive-semidefinite covariance
matrix for the estimator mean, per-observable systematic bounds, and
measurement/circuit/term provenance. Shared-shot points additionally require
attempted/accepted counts, effective-independent-shot counts, per-shot contribution
ranges, and concentration/mitigation status. They enforce
`attempted >= accepted >= 2` and `0 < effective <= accepted`; the concentration
status certifies the model, contribution ranges, and effective-sample derivation.
Circuit fingerprints must be globally unique across every route/R point. Standard
errors are derived only from covariance diagonals.

The binding finite-sample gate is not an asymptotic `z * SE` claim. It allocates
the declared family-wise error rate across all planned point, adjacent-pair, and
reference inequalities with Bonferroni, then uses bounded Hoeffding half-widths
from a validated effective independent sample count and per-shot contribution
range. With no mitigation, that range must equal the observable physical range;
bounded weighted mitigation must supply a finite validated range containing the
reported estimate. Adjacent-`R` checks add both point half-widths and both systematic
bounds, so they do not assume independent batches across `R`. Both observables must
have the required stable intervals and the target must lie inside their joint stable
window.

This yields two deliberately different positive states. Joint stability on the
declared grid without a fully bounded independent reference is
`SCREENED_FOR_TARGET_R`; only complete binding reference checks and binding route
systematic bounds plus validated independent bounded-sample concentration assumptions
can produce `READY_FOR_TARGET_R`. Unbounded/unvalidated mitigation or concentration
evidence is screening-only. The empty L=8 template remains `UNRESOLVED`, and the
unified evidence orchestrator accepts only `READY_FOR_TARGET_R` for
`READY_FOR_BENCHMARK`.

A new standalone measurement-campaign preflight now turns that finite-sample rule
into an explicit acquisition floor. It derives, rather than accepts, the four unique
convergence routes, six planned R values, two observables, 48 point inequalities,
40 adjacent-pair inequalities and 48 reference inequalities. The resulting family
size is `m=136`. The contract allocates family-wise half-width `h=0.002` to each
observable; because both observables share one occupation-basis batch, the width-two
staggered-magnetization requirement dominates at `4,300,768` effective independent
shots per route/R cell. Across 24 cells this is `103,218,432` effective shots. The
width-one double-occupancy requirement is lower and is not added to the shared-batch
count. By comparison, the old `10,000`-shot planning placeholder fails even the
`h=0.01` point budget under the same Bonferroni--Hoeffding family.

The `136` count is deliberately conservative: it indexes every declared inequality,
while the underlying stochastic concentration events are the 48 route/R point
intervals reused across point, adjacent and reference checks. Independence among 136
comparisons is neither asserted nor required by the union bound.

This remains an effective-shot preflight, not an execution ledger. The campaign
template deliberately leaves route/R acceptance probability `p`, effective-shot
fraction `eta`, and their provenance unresolved. Therefore planned accepted shots,
expected raw attempts and any high-confidence attempt cap remain null, and the status
is `EFFECTIVE_TARGETS_DERIVED_RAW_UNRESOLVED`. Even when future `p` and `eta` values
permit an expected-attempt calculation, that value is planning-only rather than a
high-confidence stopping guarantee. The validator also reports convergence
certification as `NOT_ASSESSED_BY_PREFLIGHT`: no estimate, covariance, systematic
bound or actual shot result is generated by this planner.
For the accepted-shot conversion to be meaningful, each future `eta` must be a
conservative effective-independent fraction jointly valid for both observables;
an empirical ESS estimate alone is diagnostic rather than a guaranteed denominator.

A second standalone interface now checks the structure of deterministic reference
certificate records. Its contract exactly fixes the evidence convergence workload
and both observable identities. Each record binds the value and target to the
reference formula and term sequence, solver/configuration, certificate checker,
implementation commit, environment lock, theorem/assumptions, local JSON certificate
artifact and SHA-256. The JSON artifact must bind every decision-relevant ledger
field exactly. The validator checks a non-negative four-part error decomposition
against `total_abs_bound` and compares reference inputs with a complete externally
supplied route batch/circuit fingerprint snapshot. Binding-looking classes must use
directed interval rounding and satisfy method-specific claims: full target-sector
coverage for exact diagonalization; deduplication, dropped-L1 ledger and product-formula
bound for certified operator propagation; state-norm and contraction bounds for
certified tensor networks; locality-tail and solver-defect bounds for certified
locality methods; or an external checker for `other_rigorous`.

The reference state boundary is fail closed. Missing or internally inconsistent
records are `UNRESOLVED`; arbitrary text artifacts, JSON content drift, uncertified
TN/Krylov/stochastic methods, a missing/partial external route snapshot, failed
independence, non-directed rounding or unsatisfied claims cannot produce a positive
binding state. Even two complete self-consistent records are only
`STRUCTURALLY_COMPLETE_UNVERIFIED`: SHA-256 and exact record binding establish byte
integrity and consistency, not numerical truth. This validator runs no fixed machine
checker, does not assess whether `total_abs_bound` fits the campaign allocation,
always reports `ready_gate_eligible=false`, and deliberately has no
`QUALIFIED_BOUNDED` state. External-snapshot completeness is shape-checked rather
than proven against convergence data, and `STRUCTURALLY_COMPLETE_UNVERIFIED` still
has a nonzero CLI exit code. The empty template is `UNRESOLVED`.

A first machine-recomputed subcertificate layer is now executable. The fixed
two-qubit contract pins the checker source SHA-256, raw observable, computational
basis state, two nonzero noncommuting rotations and explicit backpropagation order.
The checker uses Fraction-only Taylor--Lagrange sine/cosine enclosures, exact Pauli
phase algebra and four-corner interval arithmetic; it propagates every gate in a
slice, merges identical strings, then recomputes each dropped coefficient's maximum
absolute interval and the cumulative `L1` ledger. It also returns the retained
expectation interval expanded by cumulative dropped `L1`.

This positive state is narrowly named
`VERIFIED_CIRCUIT_TRUNCATION_SUBCERTIFICATE`. The kernel itself does not check whether
its declared Pauli sequence is a Hubbard mapping, whether its product formula
approximates ideal time evolution, whether the truncation bound meets any budget, or
whether the method scales to L=8. All such fields remain `NOT_ASSESSED`, READY remains
false and the CLI exits nonzero. The reference-qualification validator does not
invoke this kernel, so no existing reference or outer state is upgraded.

The companion L=2 conformance witness independently builds the site-major JW
`R=2,T=1` sequence with 112 raw rotations and obtains
`M_s=0.781713978559467` and `D=0.0309252063024724`, agreeing with the direct-fermion
statevector path to below `1e-12`. The ideal-evolution diagnostic remains separated:
the R=2 differences are about `0.12595` and `0.00586`. A one-gate Fraction probe is
fully enclosed, while the full 112-gate rational certificate is
`DEFERRED_RESOURCE_LIMIT`: the unoptimized term and rational-size growth is itself a
measured implementation boundary, not evidence of L=8 feasibility.

The next independent layer now verifies the canonical Hubbard-to-JW construction for
fixed L=2 and L=3 OBC profiles. `hubbard_jw_mapping_validator.py` source-pins its own
checker plus the L2 pilot, term-order contract, L2 witness and the witness's proof-kernel
dependency. It regenerates every spin-resolved matching bond and Pauli term, retains
the onsite identity component in raw events, and records global phases `exp(-i*8)` and
`exp(-i*18)` for L2/L3. Exact CAR/JW action witnesses number 64/192, onsite occupation
witnesses number 16/36, and L3 has six bonds in each of H1/H2/H3/H4. Its positive path
also executes the pinned L2 builder and requires exact equality with the canonical
112-gate nonidentity sequence. The maximum status is
`VERIFIED_CANONICAL_JW_MAPPING_SUBCERTIFICATE`; product-formula error, exact evolution,
L=8, the campaign budget and READY remain outside its scope.

`pauli_bitset_backend.py` provides exact Hermitian-Pauli multiplication, symplectic
commutation, checker-compatible interval propagation and order-independent checkpoint
SHA-256 over canonical Fraction intervals. It is explicitly a consistency/performance
prototype with certificate authority `NONE`. It matches exhaustive/random string-backend
tests and an eight-gate L2 prefix, but neither changes the pinned checker nor claims a
complete 112-gate rational expansion.

That full L2 expansion is now completed by the separate source-pinned
`operator_propagation_checkpointed_l2.py`.  It composes the positive canonical mapping
result with all 112 nonidentity gates of the fixed `L=2,R=2,T=1` circuit, reverses the
20 raw group-event checkpoints, uses fifth-order exact Taylor intervals, and rounds
outward to the `2^32` grid after every slice.  No term is dropped: staggered
magnetization finishes and peaks at 16,380 terms with interval
`[104895467/134217728,209888553/268435456]`; double occupancy finishes and peaks at
16,381 terms with interval `[8238201/268435456,33458587/1073741824]`.  Both final
checkpoint digests and every intermediate checkpoint are independently recomputed.
The float statevector values are contained diagnostics only.  The maximum status,
`VERIFIED_L2_MAPPED_CIRCUIT_TRUNCATION_SUBCERTIFICATE`, still excludes error from the
R=2 product formula to exact Hubbard evolution, any L=8 transfer, reference-budget
qualification and READY.

The new `hubbard_strang_commutator_checker.py` independently regenerates the
nonidentity Pauli expansions for the fixed L=2/L=3/L=8 OBC five-group split and
computes the two nested-commutator families in the source-pinned Schubert--Mendl
second-order bound.  Equal Pauli strings are merged inside each family before its
coefficient `L1` norm is taken; theorem families are never cancelled against one
another.  For L=8, the exact family sums are 22,752 and 11,104, giving `C=7076/3`.
At `T=1,R=100` this yields unitary error at most `1769/7500` and the generic
norm-one-observable comparison bound `1769/3750`, so the `1/4000` allocation fails by
a wide margin; the least R satisfying this generic bound is 4,344.  This is a
rigorous negative feasibility result for this grouping and generic norm reduction,
not an observable-specific no-go theorem.  It cross-checks but does not compose the
mapping certificate; L8 sparse-action validation, physical workload identity,
truncation composition, observable-specific tightening, reference qualification and
READY remain outside the positive status.

`hubbard_strang_grouping_screen.py` now closes the immediate regrouping question.
It source-pins the positive commutator checker and enumerates every order of two
exact L8 OBC decompositions.  Among all 120 orders of the declared five groups, the
minimum is `C=7072/3` with generic R=100 observable bound `884/1875`; the reduction
from the declared `7076/3` is only `1/1769`, below the predeclared 1% materiality
threshold.  The exact OBC plaquette adaptation covers all 112 spatial bonds using
64/36 bulk bonds and 12 boundary residual bonds, but its best of 24 orders has
`C=7232/3` and bound `904/1875`, which is worse.  Its bulk group exponentials require
noncommuting plaquette-cluster evolution and are not the benchmark circuit.  Since
the R=100 allocation requires `C<=5/4`, the screen proves that coefficient-L1
reordering/regrouping is not the next viable tightening; it does not prove a
no-go for cluster spectral norms or observable/locality-specific analysis.

The official cluster implementation is now pinned at paper commit
`859bef092675957ae126e9d3b09dc3c63b213859`.  It constructs compact Fock matrices on
at most 14 modes and calls NumPy binary64 spectral routines; no outward rounding
or residual certificate is emitted.  A separate full-L8 diagnostic prototype uses
105 clusters (94 at 14 modes) and obtains `C≈1343.9636`, a 43% reduction from Pauli
L1 but still about 1075 times the R=100 ceiling.  These numbers are not imported into
any positive scope.

`hubbard_strang_generic_bound_no_go_checker.py` removes the need to certify those
cluster upper bounds for the route decision.  For the fixed five-group theorem it
recomputes the 3,072-term `A=[K1,[K1,H1]]` and its exact action on the checkerboard
Néel vector in the physical `N_up=N_down=32` sector.  The 416 nonzero outputs give
`||A|q>||^2=295200`, so the selected `1/12` contribution has squared lower bound
2,050, while the entire coefficient would have to satisfy `C^2<=25/16`.  The implied
generic R=100 bound expression is at least `sqrt(82)/1000`, over the allocation by
`4*sqrt(82)`; R=602 is only the first step count not ruled out by this single witness.
Thus globally exact and sector-restricted cluster spectral norms cannot rescue the
fixed generic bound.  Actual product-formula error and observable-specific error are
not lower-bounded; the next route is observable/locality-specific or a genuinely
different grouping/formula.

`hubbard_strang_observable_taylor_step_checker.py` now implements the first
observable-specific proof kernel.  It source-pins the positive Strang backend,
specializes Fang--Qu Eq. (3.9) to the fixed nine-stage composition, verifies exact
formal cancellation through degree two, merges the degree-three defects and
enumerates all 495 fourth-order remainder paths for L2/L3/L8 and both targets.  At
L8 its strict `delta=1/100` initial-observable one-step operator bounds are
`159187/1600000000` and `133927/2400000000`; the initial Néel expectation bounds are
smaller because both exact `D3` expectations vanish.  Correct R-step telescoping
requires evolved `O_k`, so neither number is multiplied into an actual full-time
bound.  Conversely, a uniform-supremum Pauli-L1 architecture must include `k=0` and
therefore has floors 39.80 and 22.32 times the allocation.  The exact L8 Néel action
witness makes the magnetization leading-coefficient floor exceed `5/2`, while the
double-occupancy witness remains below it.  The narrow positive status certifies only
the one-step kernel and route decision; full R=100 error, reference and READY remain
unassessed.

The double-occupancy sector follow-on now closes one additional uniform-supremum
architecture without
overclaiming a global norm.  The new source-pinned checker expands a compact
2,748-term physical-fermion fixture, independently obtains 18,544 field terms, and
proves its exact JW image equals the existing 8,928-term Pauli `D3` oracle
(`L1=423/16`).  It then replays the fixture-defined 43-cluster greedy14 partition.  Direct
matrix elements on the global `N_up=N_down=32` Néel basis state lower-bound the first
30 exact cluster norms by `1945/768>5/2`, margin `25/768`; hence even exact norms for
this k=0 partition followed by triangle cannot seed the R=100 uniform leading bound.
A per-step evolved cluster ledger remains open because this k=0 floor contributes
only `389/153600000` there.  The fixture decomposition/order's link to upstream
simplify is external audit provenance rather than a runtime-recomputed claim.  The
checker explicitly does not add those lower bounds into a lower bound for the
globally merged `D3`, so cancellation-aware/global-sector routes remain open.

The Majorana source audit also fixes the implementation direction.  The inferred
paper-date snapshot predates a documented splitting-sign repair; the selected base
is registered MajoranaPropagation `v0.3.0`, `main@b7849cb`, with a certificate fork
that must pin Julia/Manifest and PauliPropagation, sort composite terms, and add
outward intervals plus a post-dedup dropped-L1 ledger.  Exact term-growth probes show
that applying `D3` to `ad_H(O)` already yields 42,488/88,352 terms, so the next kernel
will directly propagate evolved observables instead of recomputing 495 fourth-order
paths at every step.

None of the campaign, reference-qualification, proof-kernel, mapping, checkpoint,
commutator, grouping-screen, generic-bound no-go, observable-Taylor-step or
double-occupancy-cluster no-go interfaces
is currently loaded by
`fermi_hubbard_evidence.py`. They do not
add components to `component_statuses`, and none can yet participate
in or strengthen the outer `READY_FOR_BENCHMARK` decision. Outer integration remains
a subsequent implementation step.

The dependency-free `L=2` group-order pilot now exercises both observables and
is screened at `R=32`. Its scaled-Taylor reference values have no rigorous
truncation-error bound and are therefore recorded as `approximate_unbounded`.
Consequently the result is `SCREENED_FOR_TARGET_R`, not an exact-reference or
bounded algorithmic certificate, and it remains neither hardware evidence nor
an `L=8` result.

The first-step interface is now executable as well. `first_step_contract.json`
requires per-route steady and first-step logical resources, an explicit
`compiled_exact` provenance flag, and route-specific timing fields.
`first_step_ledger_validator.py` distinguishes `UNRESOLVED`,
`BOOKKEEPING_CLOSED_ESTIMATE`, and `COMPLETE`; the empty five-route ledger remains
unresolved, and candidate/source-leading steady values cannot be promoted to exact
totals merely by supplying a first-step subtotal.

Five evidence components are now joined by `evidence_manifest_contract.json`,
`evidence_manifest_template.json`, and `fermi_hubbard_evidence.py`. The orchestrator
checks route-map/workload consistency, cross-checks term-export `trotter_steps` against
ledger `R`, requires the native occurrence-level transition component, and requires a
surface place-route ledger whose event count and logical-sequence fingerprint match the
term export. Its empty manifest is still `UNRESOLVED`; only real individual-term exports,
exact first-step resources, measured native transitions, a `COMPLETE` surface schedule,
and convergence evidence at `READY_FOR_TARGET_R` can produce
`READY_FOR_BENCHMARK`; `SCREENED_FOR_TARGET_R` is intentionally insufficient.

The new `surface_place_route_validator.py` checks all `2L^2` live data patches,
`2d^2-1` physical-qubit patch sizing, odd distance, tile conflicts, participant/corridor
connectivity, continuous intervals, operation windows and shared-patch conflicts,
dependencies, the distill/buffer/inject/rotation support chain, term-ordered one-to-one
logical-event bindings, the active physical-qubit-cycle sum, and fixed cycle/failure
budgets. It does not synthesize a routing solution:
`COMPLETE` also requires an external compiler export, `place_route_validated=true`, and
measured/compiler evidence; derived schedules remain `BOOKKEEPING_CLOSED_ESTIMATE`.

The dynamic-JW source was rechecked directly against arXiv v1. `DYNAMIC_JW_SOURCE_EVIDENCE.md`
records that Fig. 14 supports only a group-level sequence and that Appendix I explicitly
omits the extra cost of the first Trotter step. No individual-term list or exact first-step
compiled record is published there, so the unified manifest remains correctly unresolved.

The FSN side is now separated in `FSN_SOURCE_EVIDENCE.md`: Kivlichan's generic theorem
supports an exact N-depth / N²⁄2-entangling-gate network for the all-pair electronic-structure
setting, while dynamic-JW Fig. 15 supplies only the 2D NN standard/ladder strategy and
fusion convention. The finite-size formulas used in the model therefore remain
figure-domain candidate fits, not primary-source formulas.

Native evidence is now split into `NATIVE_SOURCE_EVIDENCE.md`: PNAS remains a proposal
with component-level movement/error estimates, Nature 2026 supplies a measured local
^6Li collisional-gate primitive, and arXiv:2604.13160 supplies a new global-control
proposal. None provides the matched L=8 four-matching compiled route needed for
`native_fermions` to leave `UNRESOLVED`.

`evidence_manifest_source_snapshot.json` now preserves the known L=8/R=100 source-leading
and derived bookkeeping values without inventing missing fields. Its native row exposes
the `44,864` count / `801` depth schedule, while qubit-route first-step corrections,
native occurrence timing, individual terms, and fixed-grid dual-observable convergence
data remain unresolved. The
surface row is likewise an empty placeholder with no patches, layouts, intervals, or
operations. The validator therefore continues to report `UNRESOLVED` for the snapshot.

The adaptive L8 interval route has advanced through a second, independently
precommitted resource generation.  A certificate-authority-free v2 arithmetic kernel
was first committed and old-domain parity tested; deterministic design probes then
fixed separate 17/21-candidate policies through `K=327,680` before formal execution.
The final source-pinned dual screen same-byte verifies the positive step-3/two-step
parent chain and independently replays both policies from prehashed modules.  It
certifies maximum-K infeasibility at magnetization checkpoint 29 (minimum effective
K 333,983 after 28 commits) and double-occupancy checkpoint 22 (minimum K 350,604
after 21 commits).  Exact ledgers, candidate feasibility, first-feasible choices and
five resource diagnostics are bound, while no child sidecar or transition is written.
Certified mapped depth remains 3 for magnetization and 2 for double occupancy; the
outer evidence orchestrator, exact-Hubbard error, remaining R100 evolution, physical
reference and READY status are unchanged.

A non-authoritative v3 design generation has now tested the next bounded ladder
without altering any v2 policy or formal artifact.  A same-byte fresh-executed
wrapper reuses the pinned v2 implementation, expands the magnetization/double-
occupancy candidate sets to 21/25 values through `K=393,216`, and leaves all other
resource envelopes fixed.  Magnetization advances from the old checkpoint-29 stop
through checkpoint 32 and then needs `K=405,291` at checkpoint 33; double occupancy
advances through checkpoint 23 and then needs `K=397,750` at checkpoint 24.  The
observed peaks/visits (550,806/61,421,993 and 525,968/44,079,570) remain within the
design caps, and the entire formerly committed v2 prefix is unchanged.  Thus this
generation diagnoses another maximum-K ceiling and establishes `K=409,600` as the
minimum next ladder endpoint worth testing.  No v3 policy, formal witness, child
sidecar, transition, exact-Hubbard statement or depth increment has been created.

The v4 higher-K design generation now extends the same diagnostic surface to
`K=458,752`, using 25 magnetization and 29 double-occupancy candidates while
retaining the v3 resource envelope.  Its bounded same-byte wrapper records the
v4/v3/v2 source chain and publishes only complete atomic transcripts.  Magnetization
selects `409,600/425,984/442,368` at checkpoints 33--35 and fails at checkpoint 36
with minimum effective K 464,310.  Double occupancy selects
`409,600/425,984/442,368/458,752` at checkpoints 24--27 and fails at checkpoint 28
with minimum K 461,297.  Peaks/visits are 660,262/73,130,963 and
591,330/59,719,825, so neither stop is a resource failure.  The next standard
candidate `K=475,136` covers both current minima but remains untested beyond the
handoff.  This generation is diagnostic only: certified depths remain 3/2 and no
policy, formal witness, child sidecar, transition, exact-Hubbard claim or READY
component is added.

The v5 kernel-edge generation now tests the last dense ladder that fits the current
double-occupancy candidate-count capability.  Adding `475,136/491,520/507,904`
produces 28/32 candidate sets without changing the v4 live/digest/visit or bit-width
caps.  Magnetization advances through checkpoint 38 and fails at checkpoint 39 with
minimum K 521,800; double occupancy advances through checkpoint 31 and fails at
checkpoint 32 with minimum K 518,097.  Their peaks/visits are
714,754/86,294,299 and 694,872/76,953,164, so both remain K-ceiling diagnostics.
The standard `K=524,288` endpoint covers the two current minima but is also the
kernel retained-K maximum.  Double occupancy has no remaining candidate slot;
testing that endpoint requires a new sparse/merged ladder rather than appending to
v5.  No policy, formal witness, child sidecar, transition, depth increase,
exact-Hubbard conclusion or READY component has been added.

The v6 kernel-limit generation now exercises `K=524,288`, the current arithmetic
kernel's maximum retained value.  Magnetization uses 29 candidates by appending that
endpoint.  Double occupancy remains at the 32-candidate capability by replacing the
unused v5-only `491,520` slot, preserving every ancestral v2--v4 candidate and every
K selected in the v5 committed prefix.  Five ordered same-byte source layers and
three distinct override levels are bound.  Magnetization commits checkpoint 39 with
`K=524,288` and fails at checkpoint 40 with minimum K 525,859; peak/visits are
714,754/91,034,065.  Double occupancy commits checkpoint 32 with `K=524,288`, then
the unchanged 786,432 live/digest cap stops checkpoint 33 before ranking.  A separate
noncanonical measurement at the kernel's 1,048,576-term capability records an
825,000-term peak, 82,050,350 visits and minimum K 553,717 for that checkpoint, with
the K requirement 29,429 above the retained maximum.  The resource exception is
propagated, so no partial D transcript is published; the complete M transcript is
canonical and atomic.  This exhausts candidate-only continuation under the current
kernel.  Certified depths remain 3/2, with no policy, formal witness, boundary,
transition, exact-Hubbard conclusion or READY component added.

A separate four-gate granularity screen now evaluates checkpoint cadence while
holding the v6 candidates and caps fixed as configuration-only inputs.  It owns
independent control flow, does not call the v2 or v6 run entrypoints, and does not
treat v6 as a same-byte parent or a v7 generation.  The physical 1,152-gate sequence
is unchanged; 288 four-gate checkpoints preserve every aligned prefix budget.
Magnetization commits 77 checkpoints and fails at q78/gates 308--311 with minimum
K 529,897, peak 643,624 and 82,493,877 visits.  This is the second half of old
eight-gate q39, so the reduced peak does not improve M reach.  Double occupancy
commits 64 and fails at q65/gates 256--259 with minimum K 532,869, peak 645,011 and
75,412,433 visits, converting the corresponding frontier from a full-eight-gate
live-cap stop into an earlier half-block K stop.  The deleted `491,520` rung is
counterfactually first feasible at q58--59, showing that ladder sparsification and
checkpoint cadence cannot be assessed independently.  A noncanonical 32-slot
sensitivity restores `491,520` and removes unused `65,536`; it changes both choices
but still fails at q65, now with minimum K 536,203, peak 645,044 and 75,255,249
visits.  The altered ladder is reproduced only by an opt-in test and is not saved as
a misleading v6-configured transcript.  Checkpoint halving and this one-rung repair
therefore both fail to cross the D frontier.  The screen remains diagnostic-only and
leaves certified depths 3/2 and all authority-bearing artifacts unchanged.
The planned `K=540,672` discriminator has now been executed as an explicit,
separately pinned capability extension.  Its arithmetic wrapper compiles exact v2
bytes and changes only `max_retained_K` from 524,288 to 540,672.  The diagnostic
configuration changes only the candidate/output K ceilings; live/digest stay at
786,432 and every other resource cap is unchanged.  M appends the new rung for 30
candidates.  D replaces `65,536`, which is infeasible in all 65 rows and never
selected in the pinned four-gate baseline, so its count remains 32.

M selects `540,672` at q78--80 and reaches the fixed q80 horizon with 80/80
commits; q78--80 pre-counts are 643,624/624,312/587,900 and total peak/visits are
643,624/87,032,691.  D selects `540,672` at q65, then fails at q66/gates 260--263:
pre-count/peak is 679,285, minimum effective K is 558,598, excess over the configured
maximum is 17,926 and total visits are 77,762,021.  The canonical M/D transcript
SHA-256 values are
`d4a0f952a3d4a93bd78d370fae50c5c043e33caa4d1452e841987976e43354a5` and
`5ced57f7f6fc8aef50a6536920243d00af083b0a113b09d19f239bc1266fd8a5`.
Full ledger tests cover 80x30 plus 66x32 candidate rows and bind the old committed
prefixes and failure handoffs.  The route remains diagnostic-only and leaves
certified depths 3/2 and all authority-bearing artifacts unchanged.

The observable-split discriminator is now complete.  M's same-cap q82 wrapper
replays from q1 and uses the q80 artifact only for post-replay validation.  All
q1--80 records and selected history are exact, while q81/gates 320--323 fails at
pre-count 597,254 with minimum effective K 545,129, excess 4,457.  Overall
peak/visits are 643,624/89,253,151, and the canonical SHA-256 is
`0486a8b19077de9e90f134c7b3c0d43fdf3504a4876d6e0b2c3d01b37b89cb52`.

D's direct-v2 capability wrapper raises retained K to 573,440 and candidate count
to 33, with all other kernel limits unchanged and the K=540,672 wrapper retained
only as a non-executed route reference.  The new ladder appends 573,440 to the
old 32 values.  Full replay preserves q1--65 common records/history and the first
32 rows, then preserves q66 propagation and its first 32 rows before the appended
row becomes first feasible.  D selects 573,440 at q66--68 and reaches 68/68
commits; pre-counts are 679,285/688,548/630,616, peak/visits are
688,548/82,618,707, and the canonical SHA-256 is
`b1f072c84cc676151fe3cddbb8a0db445df946f299dbb81f41e34f765d30dfc8`.
The two full ledgers cover 81x30 plus 68x33 candidate rows.  No policy, witness,
boundary, transition, READY component or certified-depth increase is created.

That next split discriminator is complete.  M's direct-v2 capability wrapper
changes only retained K from 524,288 to 557,056 while leaving candidate-count
capacity at 32.  Its append-only 31-slot ladder preserves q1--80 common
records/history and all first 30 candidate rows, then preserves q81 propagation
before the new index 30 becomes first feasible.  M selects 557,056 at q81--82 and
reaches 82/82 commits; the two pre-counts are 597,254/641,180, dropped counts are
40,198/84,124, peak/visits are 643,624/91,592,879, and the canonical SHA-256 is
`1d6cbcddac8a8c596746f24b8c8498f24874e86db5235532d7d269220043cdd4`.

D's outer horizon-only screen changes only q68 -> q70 and replays from q1, using
the q68 artifact solely for post-replay prefix validation.  Its q1--68 prefix is
exact, but q69/gates 272--275 fails at pre-count 644,504 with minimum effective K
579,098, 5,658 above the retained maximum.  Peak/visits are 688,548/84,984,299,
and the canonical SHA-256 is
`38fa337482dbd323d68f36b6debfdc6fff94d4cf8c42e68d6477b45dc02368d6`.
The two new ledgers cover 82x31 plus 69x33 = 4,819 candidate rows.  Both outputs
remain diagnostic-only; policy, witness, boundary, transition, READY components,
certified depths 3/2 and all authority-bearing artifacts remain unchanged.

Those bounded decisions are complete.  M's horizon-only outer screen changes
only q82 -> q84 and replays from q1, with the q82 artifact used solely for
post-replay prefix validation.  q1--82 records/history are exact; q83/gates
328--331 fails at pre-count 652,016 with minimum effective K 565,994 and excess
8,938, so q84 is not attempted.  Peak/visits are 652,016/93,965,211, and the
canonical SHA-256 is
`2f866d658570c9cf667088662a98288c14b41144c3ffacdefd862aaf8f185138`.

D's direct-v2 wrapper changes only retained K 524,288 -> 589,824 and candidate
capacity 32 -> 34.  Its append-only D34 ladder preserves q1--68 common state,
history and first 33 rows, then preserves q69 propagation and first 33 rows
before index 33 becomes first feasible.  q69 selects 589,824 with drop
61,286,012,190 ticks.  q70/gates 276--279 then fails at pre-count 718,805,
minimum effective K 597,272 and excess 7,448.  Peak/visits are
718,805/87,505,002, and the canonical SHA-256 is
`65d6f5ba3e45b5b57b12d1b9e1daadb17064f8aece7dc914697191f822b3a8d7`.
The two ledgers cover 83x31 plus 70x34 = 4,953 candidate rows.  No policy,
witness, boundary, transition, READY component, certified-depth or other
authority-bearing artifact changes.

Those capability extensions are complete.  M's direct-v2 wrapper changes only
retained K 524,288 -> 573,440 while keeping candidate capacity 32.  Its append-only
M32 ladder preserves q1--82 common records/history and all first 31 rows, then
preserves q83 propagation and the first 31 rows before appended index 31 becomes
first feasible.  q83 selects 573,440 with pre-count 652,016, drop
49,417,284,097 ticks and dropped count 78,576.  q84/gates 332--335 fails at
pre-count 694,130, minimum effective K 586,381 and excess 12,941.  Peak/visits are
694,130/96,423,989, and the canonical SHA-256 is
`f379f6a72caba82c0f1aca599ef9872666cfed8b4ea72003194438ed01806f48`.

D's direct-v2 wrapper changes retained K 524,288 -> 606,208 and candidate capacity
32 -> 35, with all other kernel limits unchanged.  Its append-only D35 ladder
preserves q1--69 common state/history and all first 34 rows; q70 retains the old
propagation and first 34 rows before index 34 becomes first feasible.  q70 selects
606,208 with drop 97,846,623,202 ticks, dropped count 112,597 and feasibility
margin 53,451,620,700 ticks, reaching 70/70 committed.  Peak/visits remain
718,805/87,505,002, and the canonical SHA-256 is
`55e9d305c90b62dea918071cd6ae383668c2ffb2f7dc108f7d4abcbcb772aa36`.
The exact ledgers cover 84x32 plus 70x35 = 5,138 rows.  No policy, witness,
boundary, transition, READY component, certified-depth or other authority-bearing
artifact changes.  All 35 current D candidate indices have now been selected at
least once.

Those split routes are complete.  M's direct-v2 wrapper changes only retained K
524,288 -> 589,824 while keeping candidate capacity 32.  Its replacement ladder
deletes K=65,536 and appends K=589,824.  q1--83 preserve selected-K history,
propagation and committed state exactly; because old candidate indices 1--31 shift
to new 0--30, candidate rows are normalized-exact by configured K rather than raw
row-prefix exact.  q83 still selects K=573,440 at new index 30.  q84 selects new
index 31/K=589,824 with pre-count 694,130, drop 142,263,012,225 ticks, dropped
count 104,306 and feasibility margin 46,578,773,421 ticks, reaching 84/84
committed.  Peak/visits remain 694,130/96,423,989, and the canonical SHA-256 is
`cf93ebcccde4ff10adee2e600a13ef1c0f979e89fe151fca16d4eae79da2420f`.
All 32 M candidate indices now occur in selected history.

D's same-cap outer screen changes only horizon 70 -> 72 and replays from q1; the
q70 screen/transcript are post-replay references and never execution or state
inputs.  q1--70 records, selected history and all 35 rows remain exact.  q71/gates
280--283 fails at pre-count 761,190, minimum effective K 614,584 and excess
8,376, so q72 is not attempted.  Peak/visits are 761,190/90,141,781, and the
canonical SHA-256 is
`f21288cf0c37dc86fedc9ac195f4efe390dcc913640caa7ca79f02e6297d20f8`.
The two ledgers cover 84x32 plus 71x35 = 5,173 rows.  No policy, witness, boundary,
transition, READY component, certified-depth or other authority-bearing artifact
changes.

That next split is complete.  M keeps K=589,824/C32 and changes only the horizon
84 -> 86.  Its exact q84 screen is the same-byte private execution parent, while
the q84 canonical is loaded only after replay.  q1--84 records, all 32 candidate
rows per record and selected history remain exact.  q85/gates 336--339 reaches
pre-count 673,356 with 151,110,179,092 ticks of slack.  K=589,824 would drop
184,958,529,526 ticks, so the minimum effective K is 592,290, excess 2,466;
q85 fails and q86 is not attempted.  Peak/visits are 694,130/98,908,531.  The
screen and canonical SHA-256 values are
`002cc87d5d1a8f1908a837e8612e3a9d4a4c5ebbf68e41f841ba4a5a639ff878`
and `c24a665d543323a0e7f28ac4023fe5ae3d54b39c4e2991cba3e70e9371d0053d`.

D adds direct-v2 capability K=622,592/C36 and appends that K as index 35 without
deleting any selected predecessor rung.  q1--70 common records/history and old 35
rows remain exact; q71 preserves the old propagation and first 35 rows, then
selects the appended row.  Its drop is 95,847,613,475 ticks for 138,598 terms,
leaving 40,105,997,158 ticks of margin and committing
E=2,288,967,389,826,722 ticks.  q72 propagation produces exactly 799,279 terms,
12,847 above the unchanged 786,432 live-term policy cap, before digest, ranking,
candidate construction or commit.  A closed 40-key resource-abort ledger records
that stop without inventing a q72 checkpoint record.  Peak/visits including the
attempt are 799,279/92,869,433.  The wrapper, screen and canonical SHA-256 values
are `7ac6c87f3d789ad62540cbc96e81f0a092594b0524eec3f9b05e7ffec2124838`,
`2e22e1918fbc10cd696d700dbf05e8d99d0c333a1428e9473de6ebbc563488e1`
and `e7ae9abb11a4cc116778c8c373ff1c93131db9c9d36ba886ff6ef2d7b53bd09f`.
The two exact ledgers cover 85x32 + 71x36 = 5,276 candidate rows.

Those bounded routes are complete.  M's wrapper realizes direct-v2 K=606,208/C33,
raising retained K 524,288 -> 606,208 and candidate capacity 32 -> 33 relative to
arithmetic-v2.  Relative to the non-executed M K589824/C32 route predecessor, the
incremental K change is 589,824 -> 606,208 and the wrapper appends K=606,208 as
index 32.  q1--84 preserve propagation, committed state, selected history and the
old 32 rows exactly.  q85 preserves the measured propagation/ranking and old rows,
then the appended row drops 67,148 terms and 28,686,183,592 ticks, leaving
122,423,995,500 ticks of margin.  q86/gates 340--343 reaches 654,324 terms and
selects existing index 31/K=589,824, dropping 64,500 terms and 213,158,347,226
ticks with 13,797,053,946 ticks of margin.  All 86 checkpoints commit; peak/visits
are 694,130/101,424,121.  The wrapper, screen and canonical SHA-256 values are
`447cb116c2ca977cb2711b08e64e5795728907b8c4033bd1eb38211bf63cf558`,
`86e5148a51cb70d2aab21d770ad2b21928caf6e2818786542b287be7c8d02d27`
and `fc649a90aa42429d7d746f40bdc7dfe109f1dc6921b46beb8c3396cc3012e875`.

D keeps K=622,592/C36 and horizon 72, changing only the live/digest policy caps
786,432 -> 1,048,576.  The frozen resource-abort canonical is post-replay evidence
only.  q1--71 records/history remain exact; q72/gates 284--287 again produces
799,279 terms, now completes digest/ranking and evaluates all 36 rows.  Every row
is infeasible: minimum effective K is 642,206, 19,614 above the ceiling, and the
maximum candidate's drop still exceeds prefix slack by 111,121,545,012 ticks.
There is no q72 resource abort, selection or commit; the ledger ends with 72
attempted and 71 completed checkpoints.  Peak/visits are 799,279/92,869,433.  The
screen and canonical SHA-256 values are
`57a68b3086cd2ed2d484d0f835a190dc768b12bbb2b8d6a3c99c86f6ea6bda8d`
and `4bdc16622a52a57ab6d43da04d77c6c67defdb36c2630a9d51178b65ac1e6ddd`.
The two current ledgers cover 86x33 + 72x36 = 5,430 candidate rows.

Those minimum discriminators are complete.  M keeps K=606,208/C33 and extends
only horizon 86 -> 88 through its q86 same-byte private parent and a fresh q1
replay.  q1--86 remain exact; the q86 canonical is loaded only after replay.  The
result has 88 records, 87 selected-history entries and 2,904 candidate rows.  q87
(gates 344--347, SHA-256
`4b60608343a13e9927dd20cd4bb7314e67b1432465e27d186c117935402801e7`)
reaches 645,618 terms and selects index 32/K=606,208.  It drops 39,410 terms and
28,631,843,222 ticks, leaves 89,696,616,395 ticks of margin and commits
E=1,700,501,205,265,321 ticks.  q88 (gates 348--351, SHA-256
`7f8c6a2dd155412a27369e1fa8402c37127c6eadf12e4fa59ba442d345e8eaf7`)
reaches 689,242 terms and fails policy: minimum effective K is 607,993, excess
1,785, while the maximum row drops 218,739,972,624 ticks and exceeds slack by
24,511,950,557 ticks.  The terminal branch is
`Q87_SUCCESS_Q88_FAILURE`; no resource abort is emitted.  Attempted/completed are
88/87 and peak/visits are 694,130/106,375,865.  Screen/canonical SHA-256 values
are `d158d00275e78b33d0246e86bf9bc7bcaf4eb4f7fa4cb9afce2298e97cb5308d`
and `f7ca4a1defd38472366c1cfcd112736f34b73e612002cce98a52f79daa5cc1b0`;
the canonical is 804,599 bytes.

D's separate direct-v2 K=655,360/C37 wrapper and manifest SHA-256 values are
`2acf8f8329376ab06ad4c079af633d23bcc6a32fa20af654e5c3dbbb32093d54`
and `62c889baf0676150344f06ccf5d48132e121ade399c77dd1b85727f5002dd6e5`.
Its fresh q1--72 replay commits 72/72 checkpoints and 2,664 candidate rows.  q72
reaches 799,279 terms and selects appended index 36/K=655,360, dropping 143,919
terms and 78,846,106,758 ticks with 43,761,880,334 ticks of margin.  It commits
E=2,289,046,235,933,480 ticks; peak/visits remain 799,279/92,869,433.
Screen/canonical SHA-256 values are
`1d3366d7c3fdc2a1e4a5c58198cc9be7e561af1f2ff8582e324ed5902c760183`
and `0517461f8695b21b578190cdd9a5da884f301d43c2f80be8093fbfc20cc006ae`;
the canonical is 751,550 bytes.  K=638,976 is excluded only for the fixed
four-gate q72 predecessor state/prefix: threshold 642,206, shortfall 3,230, with
no executed candidate row and no asserted exact drop.
Together the current ledgers cover 2,904 + 2,664 = 5,568 candidate rows.

Those follow-on discriminators are complete.  M's direct-v2 K622592/C34 wrapper
and capability manifest SHA-256 values are
`f4e676da40535903301181cf482119e051066b90921793e34152403b3b74b976`
and `3c2b66149d524cc63a4d04838b3eec47fb69677466fe1f208e226df92bf0dac3`.
Relative to M33 it appends only K=622,592 as index 33 and raises only the
candidate/output and retained-K/candidate-count ceilings; all other caps remain
fixed.  A fresh q1--88 replay precedes loading the old q88 canonical.  The result
commits 88/88 checkpoints with 88 records/history entries and 2,992 rows.  q88
pre-count is 689,242; index 33/K=622,592 drops 66,650 terms and 33,833,242,742
ticks, commits E=1,700,535,038,508,063 ticks, and closes the ranking boundary at
3,434,232 > 3,434,132.  No failure or resource abort is present.  Records/history
SHA-256 values are
`8832c0fd7c61146f2aa3c5e9a3a827972c459a126c2d371b5a5c41bac700c804`
and `58cd214e13f4c122f710aad62ac0e52ead1aed0fa7d8a7e2498ea6013c7f4726`.
The 78,218-byte screen and 821,781-byte canonical SHA-256 values are
`6867dda2d6bd34ab2eed6b31d02a587e16762263a493e9890d0caa40f23a58a4`
and `0074b1eea5fa574378d5a9fae9e748e7145efaa0c96b622ddf50587a72a2551a`.

D keeps K=655,360/C37 and every candidate, policy and kernel cap fixed, changing
only horizon 72 -> 74.  Its fresh q1 replay loads the q72 canonical only after
execution and commits 74/74 checkpoints, 74 records/history entries and 2,738
rows.  q73 pre-count is 794,529; index 36/K=655,360 drops 139,169 terms and
100,499,996,927 ticks, commits E=2,289,146,735,930,407 ticks and has ranking
boundary 3,668,234 > 3,667,375.  q74 pre-count is 726,450; the same index drops
71,090 terms and 44,071,221,987 ticks, commits E=2,289,190,807,152,394 ticks and
has exact ranking tie 4,009,413 = 4,009,413.  The terminal branch is
`Q73_AND_Q74_SUCCESS_HORIZON_REACHED`; there is no failure or resource abort.
Records/history SHA-256 values are
`f765797dad4f6892524fc651a259786dff9c10187a6c634fc088fd3508c1e89f`
and `d521cdf189b54254cf3ca3d0e9033b52c90ea6ec91dc571d95a605e520972ff8`.
The 117,108-byte screen and 773,489-byte canonical SHA-256 values are
`5e2e077a9cab2a2b83f9830d755bafb7cc6dfa1d1c8a1ffade840d09e5016376`
and `4421f5973253968167b1c8bd77e024b18450325ea9581ed39dbe975ec8163ec9`.
The current ledgers cover 2,992 + 2,738 = 5,730 rows.

Those same-cap horizon routes are now complete.  Their frozen pre-replay audits
both closed at P0=0, P1=0 and P2=0, after which the fresh replays were run
serially rather than concurrently.  M keeps K=622,592/C34 and changes only
horizon 88 -> 90.  Its q88 private parent starts from q1; the old q88 canonical is
loaded only after replay as exact q1--88 evidence.  q89 pre-count 718,896 selects
index 33/K=622,592, drops 96,304 terms and 174,253,874,408 ticks, and commits
E=1,700,709,292,382,471 with retained digest
`b7d1e16a3f344eb1353593fd66c379d36272c49d1ebfe5c5c2b3e6958ed98c19`.
q90 pre-count 741,376 has no feasible row: minimum effective K is 635,284,
12,692 above the ceiling.  The branch is `Q89_SUCCESS_Q90_FAILURE`, with 90
records, 89 history entries, 3,060 rows and no resource abort.  Records/history
SHA-256 values are
`8978329b712168dce39991af25f6903deaf69c45f236521bb0e08e74f3d8741f`
and `c6755c7655d6b2ff37da7b1a8ac8c16cfc4295ef9ad0b687ddaa3dcd3c785d53`.
The 89,527-byte screen and 842,060-byte canonical SHA-256 values are
`f880e851bb16df5e659d7c0e6aa237d1836b17b4ad010d5676557ade2ba9140a`
and `d30359d9dd38c8e3a1461a0c7048645e35f478fa66920711871b3dc1c44bbd49`.
The replay took 13:05 with maximum RSS 689,500 KiB.

D keeps K=655,360/C37 and changes only horizon 74 -> 76.  The q74 private parent
retains q72 as its raw parent, replays from q1, and exposes the q74 canonical only
afterward as exact q1--74 evidence.  The screen keeps ordinary source pins under
262,144 bytes and gives the unique 841,495-byte encoded `.b85` boundary a
separate 1,048,576-byte exact-pin cap.  q75 pre-count 733,965 selects index
36/K=655,360, drops 78,605 terms and 127,874,290,338 ticks, and commits
E=2,289,318,681,442,732 with retained digest
`1a0c6aae47e81c4473b43ca5c27f8580a8754c72f9332e761bbddc1b31722def`.
q76 pre-count 789,691 has no feasible row: minimum effective K is 665,836,
10,476 above the ceiling.  The branch is `Q75_SUCCESS_Q76_FAILURE`, with 76
records, 75 history entries, 2,812 rows and no resource abort.  Records/history
SHA-256 values are
`5ba16ae933ae9a17633a1c3c4d7edba28b2c115bef475480272fa2cf9df39274`
and `b72e24b2dbe1d8eff88ff9ad1e1bc47cebeb59807168603cd86ff91c218c604a`.
The 58,178-byte screen and 798,861-byte canonical SHA-256 values are
`621f9c97b72c3582314d360b9b29b46a9cb40bf60298776adfc52849300bd14e`
and `856ede1f5774795c25ca2c36eafa8ac0696402194c6bf4e17ea5e8874efc22e0`.
The replay took 11:29 with maximum RSS 715,972 KiB.

These are complete no-feasible-candidate diagnostics, not resource aborts or
positive results: both canonicals keep `resource_policy_abort=null`, do not commit
a child boundary and add no certificate authority.  The local failure thresholds
identify `K=638,976/C35` as M's next discrete ladder point and `K=671,744/C38`
as D's; neither candidate has been executed and neither may be precommitted as a
success.  K=607,993 and the older K=638,976 evidence remain scoped to their
original predecessor state/prefix.  Certified depths remain M3/D2, with no new
boundary, witness, READY or certificate authority.  The two current ledgers
cover 3,060 + 2,812 = 5,872 rows.

`M-Q90-FORMAL-S0` subsequently converted only the M q90 ceiling result into a
retrospective fixed-policy replication.  Result-unpinned policy, checker and
precommit contract were committed first at
`d3e58a62c1ca8c7c33512acfc3db141c329490fd` (policy/checker SHA-256
`8084ab612c6d3cefb8f779d4dfe24450cb5c7d612d14b485feabb7044ae7cab5` /
`7edfb6f4b811db6f97b8bd8dc9245793ee24c0613d908ded3dc7bb340c6f7bfe`).
A later q1--q90 replay used a 13-file allowlist with the prior q90 transcript
and exact-result test absent.  Post-replay-only comparison established byte
equality with canonical SHA-256
`d30359d9dd38c8e3a1461a0c7048645e35f478fa66920711871b3dc1c44bbd49`;
branch/counts are `Q89_SUCCESS_Q90_FAILURE`, 90/89 records/history, 3,060
rows, 34 infeasible q90 candidates and `resource_policy_abort=null`.  Witness
SHA-256 is
`26d4996bc8977f8e9cfa0a62817166cd5b122a1355bdb455e77b9cd87382deda`;
the external timing receipt is 13:35.69 / 671,592 KiB maximum RSS.

This is narrow fixed-policy negative authority, not prospective discovery or
a general no-go.  It creates no M4 boundary, transition or sidecar; certified
magnetization depth remains M3 and exact-Hubbard error, physical reference
qualification and READY remain unassessed.

## Majorana P0 deterministic conformance subcertificate

The parallel Majorana custody route has completed its first formal result.  The
execution closure pins Julia 1.11.9, a complete Manifest,
MajoranaPropagation 0.3.0 (`b7849cb4`, tree `d62823f2`) and
PauliPropagation 0.7.3 (`2a96e9a9`, tree `757b43af`), including recursively
hashed loaded-source closures.  Composite constituents are sorted by unsigned
Majorana mask in the runner; coefficient arithmetic uses exact rational Taylor
enclosures followed by outward `2^64` quantization, global deduplication and a
strict `< 1/100` threshold.

The final result-unpinned precommit is
`c6050be2fcc0beb1454465aa77240f6b1f88c71b`.  Formal replay staged its exact
nine-file Git allowlist, mounted all non-scratch inputs read-only, unshared the
network namespace and ran two fresh Julia processes with compiled modules disabled.
Both transcript SHA-256 values are
`ff7a6f420e9ddadcba32df575c6b9e653a1ef703b3299b5a95e3b51442f5344c`;
the independently reproduced witness SHA-256 is
`b06a7a16bc6697b92e6d3fa05a33089a2437195d5d12133346b68438177d13f8`.

The witness closes 4,096 ordered multiplication/phase/commutation cases and
17,856 fixed primitive rotation cases.  Its two-site composite fixture has five
ledger events, 26 final retained terms, cumulative dropped L1
`45769830242595739/2^60`, retained expectation
`[276704759118530155/2^62, 1106819036474125325/2^64]` and the declared
dropped-L1-widened interval
`[93625438148147199/2^62, 1839136320355657149/2^64]`.  The complete repository
regression then passed 1,208 tests with 26 expected skips.

Authority is intentionally limited to the frozen small fixture and status
`VERIFIED_MAJORANA_P0_DETERMINISTIC_INTERVAL_LEDGER_CONFORMANCE_SUBCERTIFICATE`.
L8 propagation, 1,152-gate/R=100 execution, product-formula-to-exact-Hubbard
error, physical-reference qualification, complex/vector/GPU/multithread paths,
M4/D-route authority and READY remain unassessed.  The separately precommitted
P1 cross-language L2/L3 oracle and cadence matrix described below now closes the
next implementation-conformance prerequisite; it does not retroactively expand
P0 authority.

## Majorana P1 L2/L3 action and cadence conformance subcertificate

`MAJORANA-P1-S0` has completed the cross-language bridge between the P0 kernel
fixture and any future bounded propagation pilot.  Its result-unpinned input
commit is `0b3e766814442c1f4186335b50d19f78c043e527`, directly parented by the
P0 result commit.  The frozen workload is the spinful square-OBC Hubbard model
on L2 (2x2) and L3 (3x3), with all spin-resolved hopping and onsite generators,
every local `Sz`, and normalized staggered-magnetization and double-occupancy
observables: 62 fixed operator instances and 11,538,944 operator-ket action
columns in total.

The independent Python route derives exact occupation-basis CAR actions without
importing the Julia implementation.  The pinned Julia route uses upstream
MajoranaPropagation constructors and `overlapwithfock`.  For L2, upstream was
called for every one of the 1,179,648 bra-ket entries, including structural
zeros.  For L3, all 11,534,336 operator-ket candidate actions at term-derived
Majorana flip support were executed; entries outside that support are algebraic
zeros and were deliberately not represented as individually executed dense
checks.  This distinction is part of the certificate scope.

The fixed two-step Strang matrix contains 180 composite occurrences, 412
constituent occurrences and 284 truncation boundaries.  A deterministic
certificate wrapper actually applies constituents in unsigned-mask order and
calls the upstream apply/merge/truncate cache operations on a zero-angle identity
sentinel; a custom callback binds every real truncation call.  Native unsorted
upstream `Dict` iteration order remains unassessed.  The omitted onsite identity
phase is derived per occurrence and totals `exp(-i*8)` on L2 and `exp(-i*18)` on
L3 as a fixture convention, not as an exact-dynamics result.

Formal replay reconstructed the ten-file staging closure from committed Git
blobs, mounted inputs read-only, disabled the network and ran two fresh Julia
processes.  Both transcript SHA-256 values are
`8b0b1cc063adf5914c78cfbb2a88721c9623ec90a47dab087ea21c124c3badb7`;
the independently regenerated canonical witness SHA-256 is
`12b01c0aa89d71107f9acc5e4866f0b2998a84783aa1e255c9f462ac2a13b7f5`.
The staging manifest/tree SHA-256 values are
`510a8bfe09c140ac94418c21186326d43967632a9ec07b91bfb7c1386f01b393` /
`8dbf0db16f0566bb90c6511b2e6a23741db1899e919d2fea05e638cc4580d61b`,
and the fully reconstructible replay-package SHA-256 is
`e1161b9cb6c49144f56ea5fe4c1963beeb1a7974d18ea01c02a1f264ff37cff2`.
The focused P0/P1/JW closure passed 113 tests; the complete frontier directory
regression passed 1,253 tests with 26 expected skips in 1,810.316 seconds.

The maximum authority is
`VERIFIED_MAJORANA_P1_L2_L3_HUBBARD_SPARSE_ACTION_AND_CADENCE_CONFORMANCE_SUBCERTIFICATE`.
It excludes native unsorted execution order, individually executed L3
outside-support entries, arbitrary constructors/circuits/formulas, L8 full
propagation, product-formula-to-exact-Hubbard error, exact time evolution,
physical-reference qualification and READY.  The next Majorana unit should be a
new result-unpinned P2 resource-feasibility policy for a sharply bounded
propagation prefix, with one frozen observable, hard term/time/RSS caps and
explicit success/failure/indeterminate branches; no L8 scientific result should
be inferred from P1 alone.

## Majorana P2 L8 one-step bounded-prefix resource-feasibility subcertificate

`MAJORANA-P2-S0` has now executed the first complete L8 prefix that P1 only
prepared.  Its lifecycle-safe result-unpinned precommit is
`65d0fe7778322b2bb83aabf65e7c12e989d73671`, directly parented by the P1 result
commit.  The frozen workload is the normalized staggered magnetization on the
8x8 square-OBC checkerboard Neel state, evolved through one fused mapped Strang
step at `U/t=8`, `T=1`, `R=100`.  The nine Heisenberg stages are
`H1,H2,HU,H3,H4,H3,HU,H2,H1`; their deterministic schedule contains 512
composites, 1,152 unsigned-`UInt256`-sorted constituents and 768 real
truncation boundaries.  Hopping truncates after the complete two-constituent
composite, onsite after every constituent, and the strict threshold is the
exactly representable binary64 value `2^-34`.

The earlier candidate precommit `0965cf6b...` was superseded before any result
commit after final-state discovery exposed two tests that checked result-file
absence only in the live worktree.  The lifecycle-safe sibling instead checks
live absence before replay and the bound precommit Git tree after result
materialization.  Repeating the complete formal replay preserved the exact
witness and transcript hashes below; only custody hashes that include the
corrected test bytes changed.

Each formal replay was reconstructed from the frozen Git-object allowlist, ran
in a fresh read-only/network-unshared environment, and was enclosed by a cgroup
v2 user-systemd scope with `MemoryMax=4 GiB` and `RuntimeMaxSec=300s`.  Both
fresh Julia processes reached `PREFIX_COMPLETED_UNDER_CAPS` and produced the
same transcript SHA-256,
`cf18113b82fd0348d2ae271630e59a67a1e9d73b3e09010f612cf89dbe09d0f5`.
The independently reconstructed canonical witness SHA-256 is
`ca382cd7cd8dd01dfcf7ea540809b32f89a5c512ce71484e76ed7e409cb7ae03`;
the replay-package, staging-manifest and staging-tree SHA-256 values are
`ada3465adcc9983e1f323778e3a826746986d6d272cdd19552b69e3bc6aa5325`,
`81bc3689d038ed3bf7d5828fa52230106f81bef8d62dc9542036213d58bafaf0`
and `4e25ac066969b1623e82b149098e216127154207d6c1ac7a3dbc55534b960453`.

The observed execution had peak premerge/postmerge counts 44,222/43,848 and
finished with 42,704 retained terms.  It charged 15,113,342 cap-scan visits,
15,113,342 upstream propagation visits, 9,989,760 truncation-scan visits and
42,704 final-evaluation visits, for 40,259,148 total; all are below the frozen
`2^25`, `2^25`, `2^24` and `2^26` caps.  It recorded 489,740
anticommuting splits and 328,956 threshold-dropped records.  The final term
digest is `067f02a72d50f8061c746896d9eb02e3b60f7e5d6b42f21f0191b8e5887a9c9e`.
The lifecycle-aware P2 precommit/result suite passed all 43 tests, the focused
P0/P1/P2/JW closure passed all 156 tests, and complete frontier discovery passed
1,296 tests with 26 expected skips in 1,842.621 seconds.

The maximum status is
`VERIFIED_MAJORANA_P2_L8_STAGGERED_MAGNETIZATION_ONE_STEP_BOUNDED_PREFIX_RESOURCE_FEASIBILITY_SUBCERTIFICATE`.
It proves execution resource feasibility for this one fused Float64 threshold
path only.  The accumulated dropped-absolute-sum and final Neel expectation are
diagnostics, not certified coefficient or truncation-error bounds.  The raw
1,280-constituent threshold path, double occupancy, the remaining 99 steps,
equality to the Python top-L1 route, product-formula-to-exact-Hubbard error,
physical-reference qualification and READY all remain unassessed.  The next
scientific unit must therefore add outward coefficient enclosures and a
truncation-only error ledger for this same frozen prefix before any longer
horizon is considered.

## Majorana P3 one-prefix local-defect and Neel-enclosure subcertificate

`MAJORANA-P3-S0` has completed the accuracy layer that P2 deliberately left
open, for exactly the same L8 staggered-magnetization first fused mapped step.
Its result-unpinned precommit is
`5c1d009165716e6b8a935cad57c556a7ba966bbf`, directly parented by the finalized
P2 result commit.  The Julia runner saw only six staged files and never saw P2
or P3 result artifacts.  The outer lifecycle independently closed 27 source
files plus the precommit contract, the pinned Julia/depot custody and an exact
18-file host replay-environment manifest: one ELF loader, five glibc ABI files
and twelve C.UTF-8 locale files.  All environment inputs were captured and
mounted read-only; `/scratch` was the sole writable host-backed bind, `/proc`
and `/dev` were private kernel mounts, and both network and PID namespaces were
unshared.

Two fresh cgroup-v2/systemd executions under the inherited 4-GiB/300-s caps
produced byte-identical 2,530,705-byte transcripts with SHA-256
`f102a1aab1bfc4f05b38d98df6371cf1aee2c3087a9960ba1b2c346b6c6dba43`.
The canonical witness SHA-256 is
`6b4354b7f26db198427a74cfc7eac08c1895fda8d397918a9733fe7e32e8d7f5`,
and the accuracy-ledger SHA-256 is
`19774d946e85f04fbe1d3f97d85d62644adb9ff3e253546ead1e1ddd31abddd3`.
The independent Python checker uses exact rational order-7 trigonometric
enclosures and integer IEEE-754 binary64 round-to-nearest-ties-to-even; it
replayed all 1,152 constituents, 768 boundaries, every product/merge/drop row
and every final Fock element.  It also reproduced P2's transition, boundary,
stage and final-state digests as post-replay conformance evidence.

The accuracy ledger records 489,740 anticommuting actions and 1,426,644 charged
accuracy events:

- 979,480 product-defect events and `115422645562996270045296` ticks;
- 118,208 merge-defect events and `90064161277934613561344` ticks;
- 328,956 executed drop-defect events and
  `296986546186107059275602367348736` ticks.

The total is `296986546391593866116533250955376` ticks on the `2^128` grid,
or exactly
`18561659149474616632283328184711/21267647932558653966460912964485513216`
(`8.72765018884e-7` diagnostically).  Exact cross multiplication places it
strictly below `1/400000 = 2.5e-6`; it uses about 34.91% of that one-prefix
allocation.  Of 328,956 threshold drops, 3,714 were exact binary64 zeros.  The
retained state has 42,704 terms and exact checkerboard-Neel center
`604040239256614101433905/604462909807314587353088`.  Widening the center by
the authoritative total produces
`[21252757972972667064323158507908464249/21267647932558653966460912964485513216,
21252795096290966013556423074564833671/21267647932558653966460912964485513216]`,
approximately `[0.999299877465, 0.999301622995]`.

The lifecycle-aware P3 precommit/result suites pass all 49 tests, the focused
JW plus Majorana P0/P1/P2/P3 closure passes all 205 tests, and complete
`fermion-frontier` discovery passes 1,345 tests with 26 conditional skips.
The frozen checker also accepts the materialized result through its full
package reconstruction and independent oracle path.

The terminal branch is `BOUND_WITHIN_PREFIX_ALLOCATION`, with maximum status
`VERIFIED_MAJORANA_P3_L8_STAGGERED_MAGNETIZATION_ONE_FUSED_STEP_LOCAL_DEFECT_AND_TRUNCATION_OPERATOR_AND_NEEL_EXPECTATION_BOUND_SUBCERTIFICATE`.
This is one exact product-formula prefix and one observable/state only.  It does
not claim a global coefficientwise interval state, equality of the executed and
exact-arithmetic drop sets, the raw 1,280-constituent path, double occupancy,
the remaining 99 mapped steps, product-formula-to-exact-Hubbard error, a
physical reference or READY.

## Majorana P4 adjacent-step cumulative-allocation subcertificate

P4 S0v2 executed the planned adjacent step-1-to-step-2 child under
result-unpinned precommit `c6c2614186a8315775fa477e025195741c36d582`.  The
earlier signed-zero v1 replay failed closed and materialized no authority.  In
each fresh S0v2 process, step 1 was rerun as conformance evidence before step 2;
the telescoping ledger inherits the P3 operator-error upper exactly once and
does not charge or outward-round the freshly reproduced parent a second time.

On the `2^-128` integer grid, the step-2 product, merge and executed-drop
components are `148110706480666299015145`, `145718728421478199062528` and
`4432692192952477384756578989637632` ticks.  Their local total is
`4432692193246306819658723487715305` ticks, approximately
`1.3026511580e-5`: `5.2106` times the frozen `1/400000` step allocation.  The
drop upper accounts for `99.9999999934%` of this increment.  Adding the P3
parent once produces cumulative two-step error
`4729678739637900685775256738670681` ticks, approximately
`1.3899276599e-5`, which is `2.7799` times the frozen `1/200000` cumulative
allocation.  The final retained state contains 72,808 terms and has exact
checkerboard-Neel center
`301388136752758141215773/302231454903657293676544`.

The terminal branch is `TWO_STEP_CUMULATIVE_BOUND_EXCEEDS_ALLOCATION`, with
maximum status
`VERIFIED_MAJORANA_P4_L8_TWO_STEP_CUMULATIVE_ERROR_BOUND_EXCEEDS_ALLOCATION_SUBCERTIFICATE`.
This is a bounded no-go for the fixed binary64 `2^-34` threshold plus additive
L1 drop accounting.  It is not an actual-simulation-error no-go and does not
certify the remaining 98 mapped steps, product-formula-to-exact-Hubbard error,
double occupancy, physical-reference qualification or READY.

The next unit should be a separately precommitted, result-unpinned
threshold-hardening child that evaluates a `2^-36`/`2^-37` design probe or a
budget-constrained drop rule under fresh term/event/time/memory caps.  A direct
third-step extension is not the next priority.  Product-formula-to-exact-
Hubbard error remains an independent proof budget.

## Majorana P5 D0 conditional step-2 threshold resource envelope

P5 D0 narrowed the next question before opening any new scientific result:
step 1 remains the certified strict `2^-34` P3 path, while the formal candidate
set is frozen to strict step-2 thresholds `2^-36` and `2^-37`.  The `2^-34`
step-2 path is a resource-control candidate only.  A budget-constrained drop
algorithm is intentionally deferred to a separate child so that this unit
changes one execution rule at a time.

The non-authoritative probe was committed first at
`f65ceb94494d71a2de1cd6057405a583fa388f82`.  Its report SHA-256 is
`602c4eddea30c20ddb793e2641b1e8b55e4767a62366b946892a19c3802dffc5`.
The control exactly reproduced the published P4 resource projection.  Both
formal candidates then completed without a deterministic cap, timeout or OOM.
For `2^-36`, the step-2 peak premerge/postmerge/final counts were
186,102/183,704/174,280, total P2 visits were 279,133,312, and observed maximum
RSS was 731,012 KiB.  For `2^-37`, the corresponding values were
257,558/253,710/241,120, 372,980,288 and 734,516 KiB.  Wall-clock diagnostics
were 5:06.94 and 6:43.56 respectively.

Applying the precommitted common-cap rule gives term/premerge/final caps of
524,288; cap-scan and propagation visit caps of 536,870,912; truncation visits
268,435,456; total P2 visits 1,073,741,824; anticommuting/product/merge/drop
event caps 16,777,216/33,554,432/4,194,304/8,388,608; and accuracy/combined
caps 33,554,432/1,073,741,824.  The same caps must cover both candidates.

D0 has status `scientific_authority=NONE`: it contains no defect ticks,
allocation decision, term/drop digest, Neel center or expectation interval and
cannot rank candidates or enter a formal runner.  The next unit is a distinct
result-unpinned P5 formal precommit that runs each frozen candidate in its own
fresh process, reproduces the common P3 step-1 prefix, and only then evaluates
`E12(candidate) = E1_P3 + E2_local(candidate)` under an independent checker.

## Majorana P5 conditional step-2 threshold comparison subcertificate

P5 S0 has now completed that result-blind formal comparison under precommit
`85173e5982f526258563fc00e326d7f3f39b0a7a`.  An earlier formal attempt exposed
an inherited 8-MiB stdout-parser cap as too small for the expanded persisted P5
comparison container.  That attempt produced no scientific authority.  A
separate persisted-container cap was then derived result-blind as four frozen
processes times the already frozen 16-MiB per-process stdout cap (64 MiB),
without relaxing the P3 8-MiB stdout limit.  Under the new result-unpinned
precommit all four fresh processes (two each for K36 and K37) were replayed
from scratch.
The reconstructible replay-package SHA-256 is
`d58edc020c6611ac90c060007dea8fe96f28c9038381182ace4f632fc29331b3`,
and the independently reconstructed canonical witness SHA-256 is
`de70c1ac987906f6e800e7207bbc6fb9a07d8219002ba1c25ac51d2669139d7f`.

On the `2^-128` integer grid, K36's step-2 local increment is
`2070126857976823014693699325755484` ticks, above the strict `1/400000`
budget maximum `850705917302346158658436518579420`.  Adding the P3 parent
exactly once gives `2367113404368416880810232576710860` ticks, also above the
strict `1/200000` cumulative maximum
`1701411834604692317316873037158841`.  K36 therefore fails both required
comparisons.

K37 reduces the local increment to
`1113735321208794997599598935941569` ticks, but this still exceeds the same
local maximum.  Its cumulative two-step bound is
`1410721867600388863716132186896945` ticks, which does pass the cumulative
allocation with `290689967004303453600740850261896` ticks of strict integer
slack.  The frozen selector requires both the local and cumulative comparisons,
so K37 is not eligible despite its cumulative pass.  The terminal branch is
`NO_CANDIDATE_WITHIN_BOTH_ALLOCATIONS_AFTER_ALL_CANDIDATES_COMPLETE`, with
status
`VERIFIED_MAJORANA_P5_L8_CONDITIONAL_STEP2_K36_K37_ERROR_BOUNDS_NO_SELECTION_SUBCERTIFICATE`.

The decisive obstruction is now the step-2 local increment, not the two-step
cumulative budget by itself.  Continuing to tighten one uniform threshold has
diminishing returns while sharply increasing the retained-state and replay
resource envelope.  The next route should therefore prioritize a separately
precommitted budget-constrained/adaptive drop rule, or a new proof that revises
the telescoping allocation obligation before reconsidering K37; the present
certificate cannot waive its failed local comparison.  Authority remains
limited to the fixed L8 P3 `2^-34` first step followed by one conditional K36
or K37 second step.  This is not a full-simulation no-go, does not assess the
remaining 98 mapped steps or product-formula-to-exact-Hubbard error, and does
not establish physical-reference qualification or READY.

## Majorana P6 D0 full-domain adaptive-drop resource envelope

P6 D0 now closes the resource question for the next budget-constrained route
without opening its scientific result.  The single formal candidate
`E768-MAX-LAZY37-V1` freezes a causal 768-boundary prefix schedule and ranks the
complete postmerge domain by exact point cost, absolute binary64 bits and
unsigned mask.  Strict K37 membership is only a lazy initial segment: a fully
consumed tier 1 with positive remainder must rescan and rank every affordable
nonpool row.  The `P5-K37-RESOURCE-CONTROL` path is nonselectable and preserves
the original threshold callback.

The result-blind preprobe was committed at
`2483450e9ae93402a5315dae21b142d08742e783`.  The canonical D0 report has
SHA-256
`7c591111ee99b18bf2ccaca2d8157e93a19a3db49b6a680c01b0be13f570fc56`.
The control exactly reproduced the frozen P5 K37 resource projection with zero
adaptive-selection work.  The adaptive candidate then completed all 768
selection boundaries from a fresh O0 process, with no deterministic cap,
timeout or OOM, and reproduced the same P3 step-1 resource projection.

For the adaptive step 2, peak premerge/postmerge/final term counts were
307,507/303,027/284,847.  Total P2 visits were 426,811,185 and combined P2 plus
accuracy events were 445,136,171.  Aggregate selection work comprised
114,104,682 ranking-scan visits, 20,263,438 sort inputs, 21,954,876 exact
row-cost evaluations and 4,208,292 selected-membership insertions, for
160,531,288 total work units and a 303,027-term peak ranking buffer.  Diagnostic
maximum RSS was 892,140 KiB; wall-clock time was 14:33.41.

The precommitted two-times/next-power-of-two rule establishes one future S0 cap
set: 1,048,576 for current/boundary/final/premerge terms; 536,870,912 for each
cap-scan and propagation counter; 268,435,456 truncation visits; 1,073,741,824
for total P2 and combined events; and
67,108,864/16,777,216/33,554,432/4,194,304/16,777,216 for
accuracy/anticommuting/product/merge/drop events.  Selection scan/sort/cost-
evaluation/insertion caps are
268,435,456/67,108,864/67,108,864/16,777,216, with a 1,048,576 ranking-buffer
cap and 536,870,912 total-selection-work cap.  Formal host caps are 2 GiB,
zero swap, 1,800 seconds and 4,096 stderr bytes.  The runtime cap reaches the
policy's fixed ceiling and cannot be relaxed in place.

This report remains `scientific_authority=NONE` and `certificate_eligible=false`.
It exposes no defect ticks, prefix budget or slack, allocation comparison,
term/drop stream, coefficient or mask, Neel observable, winner or certificate;
the resource observations cannot select or certify the candidate.  The next
unit must therefore be a direct-child, result-unpinned S0 precommit that freezes
these common caps, separately derives scientific-stdout and persisted-container
caps from schema rather than D0 output, restores the formal namespace custody,
and requires two fresh byte-identical replays plus independent reconstruction.
The D0 report and policy bytes must not enter the S0 runner.  Any S0 timeout is
`INDETERMINATE`, not permission to expand the 1,800-second cap.  The remaining
98 mapped steps, product-formula-to-exact-Hubbard error, double occupancy,
physical-reference qualification and READY all remain outside P6 D0 authority.

## Majorana P6 adaptive-drop two-step allocation subcertificate

P6 S0 has now completed the separately frozen formal replay under result-unpinned
precommit `e9c3b2ee9c095d0be6f834fa5f49ede9ec035e75`.  The sole candidate was
`E768-MAX-LAZY37-V1`: the certified P3 `2^-34` first step followed by a causal
768-boundary full-domain adaptive drop for step 2.  Two fresh isolated Julia
processes both completed before any outer reconstruction, and their stdout
transcripts were byte-identical with SHA-256
`bcd72c0291cb98a674cfc2185d711c0a33ea4948c42d630e55d5dd3407d68341`.
The reconstructible replay-package SHA-256 is
`256fba0bcbfbc967717b602773d29e8135e36032dcb2737bab15c467fdc9c8c8`;
raw and independently reconstructed canonical witness SHA-256 values are
`33d4c30f00fae1797cbf266dcdf9eb6e5af4f60868c6bf6a2a081a44ce3c65e9`
and `73c988137eba4e180ebe98101dd93a06d62f8a9a055ad9db1cf5d94bc77e9d25`.

On the `2^-128` integer grid, the step-2 product, merge and adaptive-drop
components are `148897211350102647194854`, `144697018805603317475573` and
`850704722871123727134215450394624` ticks.  Their local total is
`850704723164717957289921415065051` ticks, strictly below the frozen
`1/400000` maximum `850705917302346158658436518579420` by
`1194137628201368515103514369` ticks.  This uses approximately
`99.9998596298%` of the local allocation, so the positive result has very thin
local headroom.  Adding the P3 parent exactly once gives cumulative two-step
error `1147691269556311823406454666020427` ticks, below the strict `1/200000`
maximum `1701411834604692317316873037158841` by
`553720565048380493910418371138414` ticks.

The adaptive step records 18,324,986 accuracy events and 160,531,288 selection
work units, including 114,104,682 ranking-scan visits and 4,208,292 selected
insertions.  Its final state retains 284,847 terms with term-stream SHA-256
`9bd44992823cc6f8cf731f84954840d4927a972fb6a78c1583c3d8c0983a7c51`.
The exact checkerboard-Neel center is
`1205552546560279108145133/1208925819614629174706176`; the declared interval
is
`[339331727275257038734971019115129616821/340282366920938463463374607431768211456,
339334022657796151358617832024461657675/340282366920938463463374607431768211456]`.

The terminal branch is `CANDIDATE_QUALIFIED`, with maximum status
`VERIFIED_MAJORANA_P6_L8_E768_MAX_LAZY37_LOCAL_AND_CUMULATIVE_ERROR_BOUNDS_WITHIN_ALLOCATIONS_SUBCERTIFICATE`.
This is the first positive second-step child on this route after P4 and P5, but
its authority remains limited to the fixed L8 P3 first step, this one adaptive
second step, their additive operator-error enclosure and the checkerboard-Neel
observable.  It does not certify step 3 or the remaining 98 mapped steps,
product-formula-to-exact-Hubbard error, double occupancy, a physical reference,
global optimality of the causal selector or READY.

Because the local scientific budget is almost saturated and the D0-derived
formal runtime cap is already at the policy's 1,800-second ceiling, the next
unit should not
directly claim an adjacent third-step certificate.  It should first be a
separately precommitted, scientific-result-blind P7 D0 design/resource probe
that reproduces the P6 two-step prefix, freezes the step-3 allocation rule and
measures whether an adjacent third mapped step with its adaptive boundaries can
complete under unchanged host caps.  A cap or timeout must remain
`INDETERMINATE`; any algorithmic or proof-
allocation change belongs to a separate candidate rather than an in-place P6
relaxation.

## Majorana P7 D0 adjacent-step-3 resource admission remains indeterminate

P7 D0 froze the adjacent-step-3 design and its result-blind resource probe at
preprobe commit `8cfbd7869b38e7e0d20f72e7550b59c845bfb43a`.  The sole fresh
process was admitted under the same fixed future-S0 host envelope: 2 GiB
memory, zero swap and 1,800 seconds.  At the systemd runtime boundary it
received `SIGTERM`, returning `-15` after an outer monotonic elapsed time of
`1800.604540675` seconds.  It emitted zero stdout bytes, so the resource
witness is `null`.  The canonical report SHA-256 is
`4bf4be7f77fd499ffc9bd975f07353fd14ee7403cd6fc7759974dda37f8588cf`.

Runtime monitoring observed a cgroup memory peak of approximately 735 MiB,
well below the fixed memory ceiling, but that value is operational diagnostic
context only.  It is not part of the canonical resource witness, and the
report's `time_diagnostics` object is empty.  With no stdout witness,
the run establishes neither P6-prefix resource conformance nor any step-3
resource observation.

The terminal status is `INDETERMINATE_HOST_OR_RUNTIME_FAILURE`; fixed S0
admission is `NOT_ESTABLISHED` (stored as
`NOT_ESTABLISHED_INDETERMINATE_HOST_OR_RUNTIME_FAILURE`), and
`scientific_authority=NONE`.  This is not a deterministic-cap result and not a
mathematical or algorithmic no-go.  It cannot admit the candidate to P7 S0,
select or reject it, or authorize an in-place relaxation of any frozen host,
engine or selection cap.

The next route must therefore be a separately precommitted new version, not a
revision of this frozen P7 D0 contract.  It should either introduce a
result-blind time/algorithmic-complexity design probe or decompose the proof and
execution into independently bounded stages before reconsidering formal S0
admission.  Such work must not inspect, recover or use any suppressed
scientific value, including term streams or digests, checkerboard-Neel values,
exact centers, declared intervals or operator-error ticks.

## Majorana P7 D1 localizes the runtime interruption to the step-3 engine

P7 D1 froze the separately versioned, D0-result-informed but scientific-blind
phase diagnostic at preprobe commit
`48a1be6932331e2925261965c783e6b40b555747`, a direct child of D0 result
commit `4ebed6b651e3c9605f84939d6a9efff8281bc38b`.  Its sole execution used the
unchanged 2 GiB memory, zero-swap and 1,800-second memory/swap/runtime
admission.  The supervised command returned `-15` after `1800.381352338`
outer-monotonic seconds; the 1,830-second outer safety timeout did not fire.
Stdout remained empty, the resource witness is `null`, and the canonical
report SHA-256 is
`9d37609c51f9149baf347fbf801338cc0abe7c7323c187fe71a4932099f8f713`.

The dedicated phase channel produced a 15-event `LEGAL_PREFIX_INTERRUPTED`
trace.  The outer receiver observed
`P6_PREFIX_RESOURCE_CONFORMANCE_PASSED` at `660.422891266` seconds,
`STEP2_TO_STEP3_HANDOFF_COMPLETED` at `660.560118161` seconds and
`STEP3_ENGINE_STARTED` at `660.589519616` seconds.  No
`STEP3_ENGINE_RETURNED` or step-3 finalizer event followed before termination;
the last event is `STEP3_ENGINE_STARTED` and the diagnostic terminal branch is
`null`.  These timestamps are outer-receive host diagnostics only, not
scientific timings or bounds.  D1 therefore localizes this observed runtime-
envelope interruption to the step-3 adaptive engine without reproving or
expanding P6 scientific authority.

The terminal observation remains `INDETERMINATE_HOST_OR_RUNTIME_FAILURE`, with
`scientific_authority=NONE`, `certificate_eligible=false` and
`result_contract_eligible=false`.  S0 status is exactly
`NOT_ESTABLISHED_BY_D1_PHASE_DIAGNOSTIC`, while the D0 status remains
unchanged.  This is neither a deterministic cap nor a mathematical or
algorithmic no-go.  Any continuation must be a separately precommitted D2
focused on the step-3 engine: either coarse source-pinned stage instrumentation
or a separately versioned algorithm/proof decomposition.  It must not reuse or
relax D1, change the scientific candidate or admission caps in place, or
inspect/export suppressed scientific state.

## Majorana P7 D2 narrows the runtime interruption to segment E after checkpoint 1

P7 D2 froze its separately versioned, D1-result-informed but scientific-blind
static-schedule diagnostic at preprobe commit
`2692f10a266b635ef1942bc510801a7db952c0d9`, a direct child of D1 result
commit `29911a8ac46c068c550504f8b4a57d27a9441c0c`.  The sole execution used
the unchanged 2 GiB memory, zero-swap and 1,800-second admission.  The
supervised command returned `-15` after `1800.611541745` outer-monotonic
seconds; the 1,830-second outer safety timeout did not fire.  Stdout remained
empty, the resource witness is `null`, and the canonical report SHA-256 is
`94c8cc4bd9487f14d598d92dd96153ae9e631c8c232d484952b91eab3e5fd0dc`.

The dedicated channel produced a 33-event `LEGAL_PREFIX_INTERRUPTED` trace.
The P6-prefix conformance marker arrived at `660.801840022` seconds and the
step-3 engine started at `660.944943001` seconds.  Segments A through D
returned.  Segment E/H4 started at `1585.779306765` seconds and reached
checkpoint 1 at `1737.307683340` seconds.  No segment-E checkpoint-2 or return
marker, later segment marker, step-3 engine return or step-3 finalizer marker
followed.  These values are outer-receive host diagnostics only, not scientific
timings or bounds.

The frozen map emits checkpoint 1 after E composite ordinal 22 and checkpoint
2 after ordinal 43.  The marker protocol therefore confirms that control flow
passed the completion points for 224 earlier A--D composites plus the first 22
E composites: at least 246 frozen step-3 completion points.  The unmarked
static window is E local ordinals 23--43, corresponding to global zero-based
composite indices 246--266.  Abrupt interruption can occur between completion
and marker emission.  The absence proves only that no checkpoint-2 event was
successfully emitted; it does not prove E local ordinal 43 was unfinished or
identify the exact active composite.  The possible runtime completion-point-
count envelope is 246--267.  No scientific state was inspected or exported.

The observation remains `INDETERMINATE_HOST_OR_RUNTIME_FAILURE`, with no
diagnostic terminal branch and `scientific_authority=NONE`.  S0 status is
`NOT_ESTABLISHED_BY_D2_SCHEDULE_DIAGNOSTIC`; this is neither a deterministic
cap nor a mathematical or algorithmic no-go.  Further resolution requires a
separately precommitted, D2-result-informed but scientific-blind D3 that
subdivides only the frozen segment-E static window, or a separately versioned
algorithm/proof decomposition.  D2, the candidate and the host admission must
not be relaxed in place.

## Majorana P7 D3 narrows the unresolved segment-E window to local ordinals 23--26

P7 D3 froze its separately versioned, D2-result-informed but scientific-blind
segment-E subgrid diagnostic at preprobe commit
`55453f7fb0251f676a71220eb7b090d78ba6d8c5`, a direct child of D2 result
commit `937065e0a576ba7615d48e389fb8e75e3e3aa677`.  Its sole fresh process used
the unchanged 2 GiB memory, zero-swap and 1,800-second admission.  The
controlled command returned `-15` after `1800.488401583` outer-monotonic
seconds; the 1,830-second outer safety timeout did not fire and stdout was
empty.  Those process-level facts are retained only as host/runtime
diagnostics and do not establish why the process stopped, which signal source
was responsible or which composite was active.  The verified canonical report
is 11,888 bytes with SHA-256
`8374dff73a0753f95eba1fb1bcf3612e269095b33a223717293b33ef5f65f0db`.

The dedicated channel produced a 33-event `LEGAL_PREFIX_INTERRUPTED` trace.
Segments A through D returned.  Segment E/H4 started and reached checkpoint 1
after local composite ordinal 22.  No E subgrid-26 marker was emitted, nor was
any later E subgrid-30, subgrid-34, subgrid-38, checkpoint-2, E-return,
later-segment, step-3 engine-return or step-3 finalizer marker emitted.  These
marker facts localize only frozen control-flow progress; they do not expose a
scientific value or identify a failure mechanism.

The fixed D3 subgrid emits its next marker immediately after E local ordinal
26.  Combined with the confirmed checkpoint-1 marker, the unresolved static
window is therefore E local ordinals 23--26, corresponding to global
zero-based composite indices 246--249.  The returned A--D markers and E
checkpoint 1 confirm passage through at least 224 + 22 = 246 frozen step-3
completion points.  An interruption may occur after local ordinal 26
completes but before its marker is successfully emitted, so the possible
runtime completion-point-count envelope is 246--250.  The absent subgrid-26
marker does not prove that ordinal 26 was unfinished, and neither endpoint is
an observed scientific state.

The observation remains `INDETERMINATE_HOST_OR_RUNTIME_FAILURE`, with no
diagnostic terminal branch, `scientific_authority=NONE`,
`certificate_eligible=false` and `result_contract_eligible=false`.  The
resource witness is `null`, and S0 status is exactly
`NOT_ESTABLISHED_BY_D3_E_SUBGRID_DIAGNOSTIC`.  This is neither a deterministic
cap nor a mathematical or algorithmic no-go and cannot authorize an in-place
change to the candidate, algorithm, caps or host admission.  Any further
resolution requires another separately precommitted scientific-blind version
targeting the remaining local 23--26 window, or a separately versioned
algorithm/proof decomposition.

## Majorana P7 D4 V2 does not add a per-composite localization

P7 D4 V2 froze its separately versioned, D3-result-informed but scientific-
blind segment-E per-composite diagnostic at preprobe commit
`75371cf32b31e09ae255a1aafc2a98b2bf9d0a5a`, a direct child of D3 result
commit `70b5095fde9fdb743d1e5910b80bbcac88de4fca`.  The superseded D4 V1
preprobe commit `c8a4d9e137d4976e1b8841041a72b53993068e46` was never executed,
produced no report or execution claim and is not a result input to V2.  V2's
sole fresh process used the unchanged 2 GiB memory, zero-swap and
1,800-second admission.  The controlled command returned `-15` after
`1800.351788777` outer-monotonic seconds; the 1,830-second outer safety
timeout did not fire and stdout was empty.  These process-level facts are
host/runtime diagnostics only and do not identify a cause, signal source or
active composite.  The verified canonical report is 11,822 bytes with
SHA-256
`269e74dd23c33b0e2d1943d7f25e44ebcd897bdde1a96645a80eba4cf4e5da19`.

The dedicated channel produced a 32-event `LEGAL_PREFIX_INTERRUPTED` trace.
Segments A through D returned and segment E/H4 started, but no E checkpoint-1
marker was emitted.  Consequently none of the fixed per-composite markers
after E local ordinals 23, 24, 25 and 26 was emitted, nor was any later E or
step-3 terminal marker emitted.  D4 V2 therefore confirms only entry into
segment E for this execution.  It does not reproduce D3's checkpoint-1
progress and adds no localization inside D3's remaining local-ordinal 23--26
window.
Cross-run progress need not be monotonic, so this observation also does not
refute or weaken the separately frozen D3 result.

The observation is `INDETERMINATE_HOST_OR_RUNTIME_FAILURE`, with no
diagnostic terminal branch, `scientific_authority=NONE`,
`certificate_eligible=false` and `result_contract_eligible=false`.  The
resource witness is `null`, D3's status remains unchanged, and S0 status is
exactly `NOT_ESTABLISHED_BY_D4_E_PER_COMPOSITE_DIAGNOSTIC`.  This is neither
a deterministic cap nor a mathematical or algorithmic no-go.  D4 V2 must not
be rerun or relaxed in place.  A continuation should instead use a separately
versioned algorithm/proof decomposition, or a separately precommitted
scientific-blind design that tests cross-run repeatability without treating
host timing or marker reach as scientific evidence.

## Majorana P9 G0 closes the post-D4 diagnostic route without a review target

P9 tested the separately frozen `E768-BITORDER-STEP3-V1` resource path after
the positive P6 two-step prefix.  Its D0 result commit
`92629e3049ac0dfac12c390fc5ed499597076b7f` produced an indeterminate
host/runtime report, not a resource witness or S0 result.  D1 through D4 then
added progressively finer, scientific-blind control-flow markers under the
same 2 GiB, zero-swap and 1,800-second admission.  Their result commits are
`47a34a4a0b39c616419c542a4c1b151f4aa9f8cc`,
`770076085452822a0128a5898042d986b5c2ec36`,
`e1f3d12bfaa51076ffea4ed43752c664970a4c92` and
`1bfdf15c553c6d4934ce4395114458dcda1be4f9` respectively.

The D4 canonical report is 8,283 bytes with SHA-256
`46aa8ea40a96f84e091de039cbb7212e4d165ef1c3a36cee43038a59736c9142`.
It contains a 22-event `LEGAL_PREFIX_INTERRUPTED` trace: segments A through C
returned and segment D started, but D checkpoint 1, ALPHA and the fixed
KAPPA/LAMBDA/MU/NU per-composite markers were not reached.  It has no
diagnostic terminal branch or resource witness, and S0 remains
`NOT_ESTABLISHED_BY_P9_D4_SEGMENT_D_PER_COMPOSITE_DIAGNOSTIC`.

The frozen post-D4 contract permits a review target only when one single D4
trace enters the selected ordinals 21--24 partition.  The actual D4 trace
stops before that partition.  D3's separately observed ALPHA marker cannot be
combined with D4's missing KAPPA marker: progress across fresh processes is
not assumed monotonic.  The G0 decision therefore evaluates all four review
predicates to false and closes with
`CLOSED_NO_POST_D4_REVIEW_TARGET`.  It authorizes no D5, repeat, finer marker,
candidate change, cap relaxation, resource no-go, S0 result or execution.

The accompanying source-only decomposition also records why more markers are
not the next proof step.  The frozen Step3 schedule has 9 stages, 512
composites, 1,152 constituents and 768 truncation boundaries; its logical
term cap is `M=2^20` and BigInt bit cap is 2,048.  These facts bound element
and abstract-operation counts, but not process bytes or wall-clock time.  At a
boundary, the live cache may overlap snapshot rows, a coefficient-bits
dictionary, selected and callback-seen sets, ranked rows, dropped rows and
persistent transition/boundary/stage records.  Julia object headers, capacity,
boxing, GMP limbs, GC/JIT state and allocator retention are not covered by the
logical term counters.  Likewise the current counters do not by themselves
bound every sort comparison or pinned-package primitive cost.

The only open gate is now a separately versioned, proof-only static resource
envelope design proposal.  It must source-pin allocation sites and types,
close alias/ownership/lifetime overlap, derive capacity-aware byte formulae,
bound runtime overhead, close uncounted operation costs and mechanically
compare a peak integer bound to the unchanged `2^31` byte cap.  A design
proposal is not an execution; any later run still requires a new independent
governance decision.  `ASSESSED_NOT_ESTABLISHED` may close the assessment but
never passes admission: all seven obligations must be positively verified and
the static peak must be established strictly below `2^31` before a later
governance review may even consider execution.

## Majorana P10-G1 opens only a nonexecuting contract-feasibility audit

P10-A's B0/B1 chain (`63ae7e485724ff7a208e3e369c43a8b1933c5e2e` then
`7ee0aca97233d2fd83d5e150f13c87e6e7379032`) completed a valid static
assessment with outcome `ASSESSED_NOT_ESTABLISHED`. This is not a resource
no-go: the exact process peak remains unknown, no strict comparison to the
unchanged `2^31`-byte cap is available, and all seven proof obligations remain
not established. Execution, Julia invocation, candidate/cap change and S0
authority remain closed.

P10-G1 therefore authorizes only
`P10-B-SOURCE-RUNTIME-CONTRACT-FEASIBILITY-AUDIT-V1`: a source-only inventory
of whether independent allocation/type/layout/capacity, lifetime, runtime and
machine-cost contracts can be obtained. P10-B may return either an evidence
route identifier or a closure that no independent static-byte contract route
is available. Neither outcome is a byte proof, resource no-go or execution
authorization; any later proof or execution still requires independent
governance.

## Majorana P10-B closes the frozen source/runtime contract inventory

P10-B read only the four source-pinned inputs authorized by P10-G1. They
identify Julia executable/sysimage and package source-tree custody, but P10-A
still records selected rather than transitive allocation closure and seven
missing byte-proof contracts. No independent static contract for object
layout/capacity, ownership lifetime, BigInt/GMP and resize costs,
GC/JIT/allocator/library/stack overhead, an envelope checker, or machine cost
is present in that frozen inventory.

The scoped outcome is `CLOSED_NO_INDEPENDENT_STATIC_BYTE_CONTRACT_ROUTE`.
It is not a global impossibility claim, resource no-go, OOM attribution, byte
bound, or execution authorization. The exact peak and strict comparison to
the unchanged `2^31` cap remain unknown; all seven obligations and execution
remain closed. Any new evidence acquisition, byte proof, or execution review
requires independent governance.

## Majorana P10-G2 closes the current Julia byte-proof route

P10-G2 validates P10-B directly and closes the attempt to derive a static
process-byte proof from the current frozen Julia/runtime inventory. This is a
scoped route closure, not a global impossibility or resource no-go. Peak bytes
and the strict comparison to the unchanged `2^31` cap remain unknown.

The only successor is the nonexecuting
`P11-A-EXPLICIT-MEMORY-KERNEL-FEASIBILITY-DESIGN-V1`. It may assess fixed
capacity/arena ownership, fixed-width 2048-bit arithmetic, deterministic
workspace bounds, runtime terms, lifetime overlap, and an independent checker.
It may not implement, compile, benchmark, execute, acquire external sources,
or change the frozen scientific schedule. Any implementation requires another
independent governance decision.

## Majorana P11-A identifies an explicit-memory design route

P11-A source-pins the frozen P3/P6/P9 semantics, P10-A gap ledger, and P10-G2
authority. It identifies a single-threaded ahead-of-time route with no GC/JIT,
one fixed arena, fixed-capacity term tables and workspaces, 256-bit masks,
stored 2048-bit ticks, streamed records, and a separately implemented layout
checker. No language or toolchain is selected in this phase.

The conservative all-regions-reserved design ledger totals 872,415,232 bytes
(832 MiB): two overprovisioned term tables plus snapshot, ranking, action,
collision, drop, and index/membership workspaces. The remaining 1,275,068,416
bytes below the unchanged 2 GiB cap is unassigned difference, not proven
runtime headroom. Exact arithmetic scratch width, slot layout, phase overlap,
toolchain/link map, static libraries, stack/TLS/transport, semantic equivalence,
and an independent peak checker are still unresolved.

The result is
`FEASIBLE_EXPLICIT_MEMORY_ROUTE_IDENTIFIED_NOT_IMPLEMENTATION_AUTHORITY`.
Implementation, compilation and execution gates remain closed; exact process
peak and strict cap admission remain unknown. New independent implementation
governance is required before any prototype or executable source is written.

## Majorana P11-G1 opens only a preimplementation contract pack

P11-G1 validates the P11-A design result and retains its design-only meaning.
It authorizes only `P11-B-PREIMPLEMENTATION-CONTRACT-PACK-V1`: byte layout,
wide arithmetic, arena lifetime, AOT toolchain/runtime, independent checker,
and frozen-semantics vector contracts. Read-only local toolchain identity and
official primary metadata may be inspected, but archives may not be downloaded.

P11-B may not write implementation source, prototype, compile, link, install,
benchmark, run Julia/candidates, change semantics or relax the 2 GiB cap. Both
allowed P11-B outcomes keep implementation and execution closed; a new
independent decision is required before source implementation.

## Majorana P11-B defines the preimplementation contract pack

P11-B selects a freestanding C17/GNU x86-64 static-ELF contract target without
writing or compiling source. Local GCC 15.2.0 and Binutils 2.46 executable
identities are recorded as a read-only observation; their source archive is
not yet pinned, so they are not implementation custody. GNU primary metadata
supports the freestanding, floating-point and linker-script mechanisms but is
identified rather than byte-pinned.

The pack fixes byte offsets for seven slot layouts, two half-full 2^21-slot
term tables, a contiguous nonaliasing 872,415,232-byte arena, and 2048-bit
magnitude storage with a reusable 2112-bit overflow scratch. It also fixes the
compile/link flag contract, static ELF and syscall restrictions, stack/map
proof inputs, independent-checker mutations, and frozen semantic checkpoints.

P6 contains only the two-step state count and stream hash, not serialized term
rows. A future implementation must therefore reconstruct frozen Step1 and
Step2 in the same explicit-memory process before Step3 and match the 42,704 and
284,847-term checkpoint hashes.

The full preimplementation target ledger is 1,028,653,056 bytes (981 MiB),
including a 64 MiB unproved kernel/cgroup-accounting reserve. Its
1,118,830,592-byte difference to the fixed 2 GiB cap is not proven headroom.
The result is `PREIMPLEMENTATION_CONTRACT_PACK_DEFINED_NOT_IMPLEMENTATION_AUTHORITY`;
implementation and execution remain closed pending new governance and the
listed toolchain, kernel-accounting, checker, equivalence and exact-peak proofs.

## Majorana P11-G2 opens only contract-level static proof artifacts

P11-G2 validates P11-B as a preimplementation contract result rather than an
implementation, exact peak, headroom, or semantic-equivalence proof. It opens
only `P11-C-STATIC-PROOF-ARTIFACT-PACK-V1`: an independent, nonimplementing
rederivation of slot padding, arena intervals, arithmetic widths, target-sum
arithmetic, and frozen prelude checkpoints, together with adversarial contract
mutation vectors.

P11-C may not write C, assembly, object, or runnable linker-script source;
compile, link, execute, benchmark, install, download, use the network, run
Julia/candidates, change semantics, or relax the 2 GiB cap. A positive result
can close only contract-level static-artifact readiness. Toolchain source
custody, postlink/stack evidence, kernel accounting, implementation semantics,
and an exact process peak remain outside this gate and require later evidence
and fresh governance.

## Majorana P11-C establishes contract-level static proof artifacts

P11-C independently parses the raw P11-B contract without importing its
validator or report. The canonical manifest rederives seven slot layouts,
including the three unassigned bytes at TERM offsets 49--51 and one at RANK
offset 305; all four are now explicit zero-padding obligations. It also
rederives the half-full term-table equation, eight contiguous 64-byte-aligned
arena intervals totaling 872,415,232 bytes, 2048-bit storage and a 2112-bit
scratch with 62 bits above the largest 2050-bit contract row.

The independent checker confirms that the eight target components sum to
1,028,653,056 bytes and leave a numerical difference of 1,118,830,592 bytes
to the fixed 2 GiB cap, while rejecting any headroom or exact-peak inference.
It also pins the Step1, Step2 and trigonometric checkpoint custody and rejects
nine adversarial layout, capacity, arithmetic, arena, runtime and checkpoint
mutations.

The scoped outcome is
`STATIC_PROOF_ARTIFACTS_ESTABLISHED_PARTIAL_OBLIGATION_CLOSURE`. This closes
contract-level artifact readiness only. There is still no candidate source,
toolchain source archive, postlink/stack proof, kernel accounting bound,
implementation-path arithmetic proof, semantic equivalence, or exact process
peak; implementation and execution remain closed.

## Majorana P11-G3 opens only an evidence-feasibility audit

P11-G3 validates the P11-C partial static-artifact closure without treating it
as toolchain-source custody, kernel-accounting, exact-peak, headroom, or
semantic-equivalence evidence. It opens only
`P11-D-SOURCE-CUSTODY-AND-STATIC-RUNTIME-EVIDENCE-FEASIBILITY-AUDIT-V1`.

P11-D may read existing package-manager, documentation, kernel, procfs and
cgroup metadata and retrieve official primary documentation. It may classify
whether auditable source-archive pinning and static kernel/cgroup accounting
routes exist. It may not update package indexes, install or download archives,
write candidate or linker-script source, compile, execute, benchmark, run
Julia/candidates, change semantics, or relax the 2 GiB cap. All possible audit
outcomes keep implementation and execution closed.

## Majorana P11-D finds a source-custody route but no static kernel bound

P11-D reads only the P11-G3/P11-C chain, installed package metadata, existing
APT indexes and configuration, the host kernel configuration, cgroup interface
presence, and official Debian, Ubuntu, and Linux documentation. GCC 15.2.0
maps to source package `gcc-15=15.2.0-16ubuntu1`; Binutils 2.46 maps to
`binutils=2.46-3ubuntu2`. Debian policy and APT's signed Release/index chain
provide an auditable exact-version `.dsc` plus source-part SHA-256 route.

That route is not current custody. The host has only `deb` entries, no
`deb-src` indexes, `apt-cache showsrc` fails, and no matching source archive is
visible in the allowed top-level APT cache. Acquiring and pinning the exact
GCC, Binutils, Linux, and linux-signed source bytes requires new governance.

The host is Linux 7.0.0-28 with MEMCG/cgroup-v2 configuration and the expected
non-root `memory.current`, `memory.peak`, `memory.max`, `memory.stat`, event,
and swap interfaces. No dynamic values are used. Kernel documentation says
memory accounting is stateful and not completely watertight, tracked charge
types may expand, `memory.peak` is a runtime record, and `memory.max` may be
temporarily exceeded. Page-table, kernel-stack, slab/per-CPU/vmalloc, transport,
file-cache, hierarchy, and transient-overage bounds therefore remain absent.

The outcome is
`SOURCE_CUSTODY_ROUTE_IDENTIFIED_STATIC_KERNEL_ACCOUNTING_NOT_ESTABLISHED`.
It is not source custody, a global impossibility result, a peak/headroom proof,
resource no-go, or execution authority. All implementation, execution,
equivalence, S0, and scientific gates remain closed.

## Majorana P11-G4 orders source custody before kernel-bound design

P11-G4 validates the exact P11-D result and splits the two unresolved evidence
routes instead of treating them as one permission. The source-custody route is
the dependency: a version-bound kernel-accounting design must bind the actual
Linux and linux-signed source archive bytes, while generic documentation and
dynamic cgroup interfaces cannot supply that binding.

The only opened successor is
`P11-E0-SOURCE-ARCHIVE-ACQUISITION-CONTRACT-PACK-V1`. It must pin four exact
source identities (`gcc-15=15.2.0-16ubuntu1`, `binutils=2.46-3ubuntu2`,
`linux=7.0.0-28.28`, and `linux-signed=7.0.0-28.28`) and define, without
executing, the isolated custody root, signed InRelease/Sources receipts,
exact-version download-only commands, `.dsc` authentication and SHA-256 rules,
complete referenced-part manifest, partial-failure cleanup, and the boundary
against unpacking or building.

Actual source configuration mutation, index refresh, download, unpacking, and
source-tree materialization remain closed until a later independent P11-E1
authorization. `P11-E2-KERNEL-ACCOUNTING-BOUND-FEASIBILITY-DESIGN-V1` is
deferred until verified P11-E1 source custody and another governance decision.
This dependency sequence grants no permission to skip a gate. Candidate source,
compilation, execution, dynamic measurement, exact peak/headroom, resource
no-go, semantic-equivalence, S0, and scientific authority all remain closed.

## Majorana P11-E0 defines acquisition without performing it

P11-E0 turns P11-G4's Route A into a deterministic future acquisition
contract. It fixes the Ubuntu snapshot to `20260719T064131Z`, the UTC instant
of the P11-D result commit, and pins the four source requests exactly:
`gcc-15=15.2.0-16ubuntu1`, `binutils=2.46-3ubuntu2`,
`linux=7.0.0-28.28`, and `linux-signed=7.0.0-28.28`. A missing snapshot or
version must fail closed; substitution by a newer package or another snapshot
is forbidden.

The future P11-E1 recipe uses a new non-symlink custody root outside Git,
isolated source-list, lists, cache and empty dpkg-status paths, two `deb-src`
stanzas, the Ubuntu archive keyring, and five exact `apt-get --snapshot`
commands. The four source commands require `--download-only --only-source` and
may not compile or unpack. P11-E0 records these argv but does not run them.

Acceptance requires the full authenticated chain: pinned keyring bytes,
successful InRelease verification, InRelease-bound Sources indexes,
Sources-bound `.dsc` and source-part size/SHA-256 rows, `.dsc`
`Checksums-Sha256`, and recomputed local hashes. The Sources, `.dsc`, and local
file sets must agree exactly; missing, extra, duplicate, malformed, conflicting,
or hash-mismatched inputs fail closed. Each package is atomically accepted only
as a complete set with a canonical receipt, and retries may delete only their
current unaccepted directory.

The outcome is
`SOURCE_ARCHIVE_ACQUISITION_CONTRACT_PACK_ESTABLISHED_AWAITING_INDEPENDENT_AUTHORIZATION`.
The next gate is `P11-G5-SOURCE-ARCHIVE-ACQUISITION-AUTHORIZATION-V1`.
P11-E0 itself establishes neither snapshot availability nor source custody and
does not authorize APT mutation, network acquisition, unpacking, kernel-bound
design, candidate implementation, execution, peak/headroom, equivalence,
resource no-go, S0, or scientific claims.

## Majorana P11-G5 authorizes only exact isolated source acquisition

P11-G5 independently reconstructs the P11-E0 result and records ten passing
readiness checks: topology and blob custody, exact identities and snapshot,
fail-closed substitution policy, external non-symlink root, isolated APT state,
five download-only commands, the signed authentication chain, strict three-way
part-set equality, transactional receipts and cleanup, and closed candidate and
scientific gates.

The disposition is
`AUTHORIZE_P11_E1_EXACT_ISOLATED_SOURCE_ARCHIVE_ACQUISITION_AND_BYTE_CUSTODY_ONLY`.
P11-E1 may create and write only
`/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e1-source-custody`,
contact the three declared Ubuntu origins and their snapshot redirects, run
the exact P11-E0 update plus four source argv, and implement the operational
runner, hashing, parsing, authentication, receipt and atomic-acceptance logic.
APT update is limited to one attempt; each exact source package gets at most
two attempts with internal APT retries disabled.

The authorization is unconsumed in P11-G5. P11-E1 must run unprivileged with a
direct argv and cleared allowlisted environment. It may not write host APT or
dpkg state, use credentials/proxies/private mirrors/third-party keys, change
the snapshot or versions, reuse unaccepted partial bytes, commit archive bytes,
unpack or read sources, derive kernel bounds, build or execute candidates, or
measure memory. Complete, partial, unavailable, and verification-failure
outcomes all proceed to `P11-G6-POST-SOURCE-CUSTODY-GOVERNANCE-V1`; none opens
candidate implementation, execution, static peak/headroom, equivalence,
resource no-go, S0, or scientific authority.

## Majorana P11-E1 records a partial, verified archive result

P11-E1 consumed the bounded G5 acquisition authority at the frozen snapshot.
It atomically retained the complete authenticated source-file sets for
`gcc-15=15.2.0-16ubuntu1` and `binutils=2.46-3ubuntu2`. The exact Linux source
request returned code 100 twice while fetching its orig tarball, exhausting the
two-attempt limit; therefore `linux-signed=7.0.0-28.28` was not attempted.
The only valid result is
`PARTIAL_VERIFIED_SOURCE_ARCHIVES_RETAINED_COMPLETE_SET_CUSTODY_NOT_ESTABLISHED`.

The independent offline verifier rehashes the retained bytes, the transaction
logs, and the signed-index receipts. It also preserves two audit findings for
the next governance gate: individual receipt paths name pre-rename `incoming/`
locations despite hashes being independently verified in `accepted/`, and APT
emitted an `/etc/apt/-/` readability warning. P11-G6 must decide any repair or
future acquisition policy. No retry, unpacking, source reading, build,
execution, resource measurement, equivalence, S0, or scientific conclusion is
authorized by this partial result.

## Majorana P11-G6 closes the partial custody route

P11-G6 independently treats P11-E1 as a partial retained-evidence result, not
as complete source custody. The P11-G5 network authority is consumed: the two
Linux attempts cannot be extended under that authorization. The retained GCC
and binutils bytes stay external evidence only and must not be unpacked or read.

The next admissible route is solely
`P11-E1R-REMEDIAL-ACQUISITION-GOVERNANCE-DESIGN-V1`. It must first design fresh
authority, final-path receipt integrity, fail-closed handling of the APT
configuration warning, fresh identity/authentication review, and disposition of
the retained evidence. It authorizes none of those future operations, and keeps
source use, kernel accounting, candidates, execution, measurement, S0, and
scientific authority closed.

## Majorana P11-E1R designs, but does not authorize, remediation

P11-E1R converts the G6 closure findings into five auditable preconditions for
any later operational proposal. It introduces no new network authority and does
not modify external evidence. An independent P11-G7 review is required before
any operational authorization can even be considered.

## Majorana P11-G7 opens only the next contract-design gate

P11-G7 passes six read-only readiness checks and authorizes only
`P11-E2R-REMEDIAL-ACQUISITION-OPERATIONAL-CONTRACT-PACK-V1`. P11-E2R may write
repository contract, validation, test, and progress artifacts, but it may not
create the future external root, access the network, run APT, mutate retained
evidence, unpack or read sources, or perform candidate and scientific work.

## Majorana P11-E2R defines repaired operations without executing them

P11-E2R selects a distinct future custody root and requires all four exact
packages to be acquired afresh. It replaces dash sentinel APT paths with real
isolated paths, mandates `apt-config dump` inspection and fail-closed rejection
of host `/etc/apt` warnings, and binds receipts to final accepted paths with an
independent post-rename rehash. Existing P11-E1 evidence is immutable and cannot
satisfy completeness. P11-G8 must independently authorize any future operation;
until then all network, APT, archive, source, candidate and scientific actions
remain closed.

## Majorana P11-E2R establishes fresh complete archive custody

The single G8-authorized run completed with all four exact source identities
freshly accepted in the new E2R root. The repaired runner passed its APT config
preflight, emitted no host `/etc/apt` warning, and rewrote receipts to final
accepted paths followed by independent rehash. Eleven accepted archive bytes
are recorded; P11-E1 evidence was not reused. This is source-byte custody only,
not source reading, build, execution, memory measurement, equivalence, S0, or
scientific evidence. P11-G9 is now the required post-custody governance gate.

## Majorana P11-G9 closes E2R custody and opens pre-read design only

G9 validates the complete fresh E2R four-package result and records five passing
findings. The only successor is
`P11-E3-SOURCE-UNPACK-READ-PRECONDITION-CONTRACT-DESIGN-V1`; bytes remain
immutable evidence until a later independent authorization. Source reading,
builds, candidates, execution, measurement, S0 and science remain closed.

## Majorana P11-E3 designs safe source inspection without performing it

E3 fixes a distinct derived root and specifies immutable archive hashes,
per-package empty extraction roots, filesystem-escape and special-file
rejection, canonical final-tree manifests, and bounded questions for compiler,
linker and kernel accounting sources. P11-G10 must independently authorize any
materialization or read; no archive, source, build, execution, measurement or
scientific action occurs in E3.

## Majorana P11-G10 authorizes one bounded source-inspection run

G10 passes six readiness checks and authorizes one operation in the E3 derived
root: authenticated materialization, final-tree manifests, and bounded searches
and excerpt hashes for the E3 topics. It permits read-only access to E2R custody
bytes but no custody mutation, network, package action, patch, build, execution,
measurement, kernel-bound derivation, candidate decision or scientific claim.

## Majorana P11-E3 stops before extraction on a link entry

The authorized E3 run reverified custody bytes, then rejected the symbolic-link
member `linux-7.0/Documentation/Changes` in `linux_7.0.0.orig.tar.gz` under the
contract's all-links-forbidden rule. No tree was materialized and no source text
was read. P11-G11 must govern whether a separately designed confined-link rule
is admissible; the failed run cannot be retried or relaxed in place.

## Majorana P11-G11 routes the link failure into a new design gate

G11 confirms the E3 fail-closed boundary and records five passing findings. It
does not authorize retry or source access. The sole successor,
`P11-E3R-CONFINED-LINK-MATERIALIZATION-CONTRACT-DESIGN-V1`, must define relative
target normalization, package-root containment, acyclic resolution, dangling
link rejection and pre/post graph equality before another authorization review.

## Majorana P11-E3R specifies confined links without retrying

E3R replaces the all-links-forbidden rule with a graph-checked policy: link
targets must be relative, normalize inside the same package root, terminate at
an existing file or directory, and remain acyclic. Absolute, escaping,
cross-package, dangling and hard links remain closed. The failed E3 root is not
reused. P11-G12 is required before any new materialization or read.

## Majorana P11-G12 authorizes one confined-link inspection run

G12 passes six readiness checks and authorizes one new-root E3R run under the
confined-link graph policy and the prior bounded-read limits. The E2R custody
root stays immutable; network, package mutation, patching, builds, execution,
measurement, candidate decisions and science remain closed.

## Majorana P11-E3R completes confined source inspection

E3R successfully materializes all four exact source packages in a new root.
The Linux archive's 85 symlinks pass pre-extraction graph resolution and
post-extraction realpath containment. Per-package tree manifests cover 130,694
entries, and bounded searches yield 20 GCC, 20 binutils, 20 Linux and 3
linux-signed receipts. These are source-location observations only; P11-G13
must govern any semantic, kernel-bound or candidate inference.

## Majorana P11-G13 admits locations, not conclusions

G13 records five passing findings and closes E3R as source-location evidence.
Tree manifests and line hashes can anchor a future analysis, but they do not by
themselves establish compiler, linker, kernel-accounting or memory-bound
semantics. Only P11-E4 analysis-contract design opens; no additional read or
downstream technical/scientific authority is granted.

## Majorana P11-E4 designs version-bound evidence admission

E4 pins four analysis tracks and exact paths/queries. A future authorized run
may admit at most 30 merged excerpts, each bounded to ±20 lines and 8 KiB, with
file and excerpt hashes. Observed text, interpretation and unresolved gaps must
remain separate. No new read, bound derivation, candidate or scientific claim
occurs before P11-G14.

## Majorana P11-G14 authorizes one bounded evidence-analysis run

G14 passes six readiness checks and authorizes read-only E3R tree access plus
at most 30 hash-bound excerpts under the E4 windows. Results must retain the
observed/interpretation/gap split and proceed to P11-G15. No mutation, build,
execution, measurement, kernel-bound, candidate or scientific authority opens.

## Majorana P11-G8 authorizes one bounded remedial custody run

G8 passes six readiness checks and authorizes one fresh E2R operation in the new
external root, with exact four-package identities, one update, two attempts per
package, zero internal APT retries, and stop-after-first-exhaustion. The run
must end before G9 post-custody governance; all source use, candidate, kernel,
measurement and scientific gates remain closed.

## Majorana P11-E4 stops before source-text read on a manifest mismatch

The single G14-authorized run fails closed at its first GCC path precondition:
`gcc/gcc.cc` is absent from the E3R final-tree manifest. That retained package
tree contains the nested `gcc-15.2.0.tar.xz` archive, not the materialized
upstream GCC subtree assumed by the E4 contract. No source text was read and
zero excerpts were admitted. The run cannot be relaxed or retried in place;
P11-G15 must govern any nested-archive remediation design. Build, execution,
measurement, candidate and scientific authority remain closed.

## Majorana P11-G15 closes the failed run and opens remediation design only

G15 confirms the exact E4 zero-read failure, treats the missing GCC path as a
source-layer mismatch rather than evidence corruption, and records that the G14
single-run authority is consumed. It authorizes only design of P11-E4R: a
manifest-bound, one-layer nested-archive materialization contract using a new
derived root. No extraction, retry, source read, build, execution, measurement,
candidate decision or scientific claim is authorized in this gate.

## Majorana P11-E4R designs one-layer GCC source materialization

E4R pins the manifest-bound `gcc-15.2.0.tar.xz` input and defines a distinct,
initially absent derived root. A future operation must preflight the complete
member and symlink graph, enforce a single top-level directory and strict
member/byte/path limits, reject duplicate or special entries, materialize via
private staging, rescan and hash the complete tree, then publish atomically.
Nested archives found inside are never recursively unpacked. This design does
not open the archive, create the root, read source text or retry E4; P11-G16 is
required for one future byte-level materialization operation.

## Majorana P11-G16 authorizes one nested-source materialization run

G16 independently rechecks the E4R evidence chain, exact nested archive row,
absent target root, descriptor/graph safeguards and resource caps. It authorizes
one byte-level, nonrecursive GCC inner-archive materialization run in the new
E4R root, with receipts and full manifest generation. Semantic source reading,
excerpts, E4 retry, evidence-root mutation, network, builds, execution,
measurement, candidate work and science remain closed. P11-G17 must govern the
operation result.

## Majorana P11-E4R stops at forbidden archive metadata

The single G16-authorized E4R run opens the pinned archive only for metadata
preflight and rejects a PAX-header or sparse-member indication. This is a
contract-forbidden member class. The stop occurs before creation of either the
derived root or staging directory, before source-byte extraction, and before
any semantic source reading. The authorization is consumed; P11-G17 must decide
whether a separately designed metadata policy is admissible. No retry occurs.

## Majorana P11-G17 closes the failed nested materialization

G17 confirms the exact zero-materialization boundary and closes G16's consumed
authorization. The PAX/sparse indication is archive metadata, not source
semantics, and the missing external failure receipt is recorded as an operation
contract gap rather than silently repaired. Only a new metadata-classification
and failure-receipt contract design is opened; archive access, root creation,
source reading and all downstream work remain closed.

## Majorana P11-E4S designs metadata inspection and receipt-first failure handling

E4S defines a future header-only inspection that distinguishes PAX global,
extended, xattr/capability and GNU sparse representations without reading member
payloads or recording paths verbatim. A separate receipt root must be created
safely and its append-only attempt receipt fsynced before the archive is opened;
exactly one terminal success or failure receipt follows. This design performs no
archive access or filesystem creation and requires independent G18 authorization.

## Majorana P11-G18 authorizes one header-only metadata inspection

G18 passes six independent checks and authorizes one E4S run: create its separate
receipt root, persist the attempt record, and inspect only archive headers via
read-only E3R access. Member payload bytes, path/link text, extraction,
materialization and semantic reading remain prohibited. P11-G19 must review the
result.

## Majorana P11-E4S completes header-only metadata inspection

E4S persists both receipt phases and classifies 149,865 headers with zero member
payload bytes. Every header carries per-member PAX metadata, but the observed
key set is limited to `path`, `atime`, `ctime` and `mtime`; no global/extended
PAX headers, xattr/ACL/capability keys or sparse representation is observed.
This is metadata evidence only, not a materialization-safety conclusion. P11-G19
must govern its interpretation.

## Majorana P11-G19 closes metadata inspection and opens PAX-policy design only

G19 accepts the receipt-first, header-only observations and closes the consumed
G18 run. The observed key set is compatible with a narrow future policy design,
but is not itself a materialization authorization. Only E4T may specify checks
for exact `path`/time metadata; all unknown, global, extended, xattr and sparse
classes remain fail-closed.

## Majorana P11-E4T designs restricted PAX acceptance

E4T permits a future policy to consider only exact per-member `path`, `atime`,
`ctime` and `mtime` keys. Values require strict encoding, path and decimal-time
checks; times are receipt-only and never restored. Every other PAX or metadata
class remains fail-closed. This is a design only and needs G20 authorization.

## Majorana P11-G20/G20R consumes one strict PAX validation authority

G20 first authorizes a strict four-key validation, and G20R subsequently binds
one execution to the exact archive and a receipt-first root. The G20R run checks
all 149,865 headers without reading member payloads or source text. It finds
149,244 headers nonqualifying under the exact-four-key policy. The result is a
policy failure, not a source-corruption or scientific conclusion; the single-run
authority is consumed.

## Majorana P11-G21 routes the strict-policy failure to value-shape design

G21 closes retry, extraction, materialization and policy relaxation under G20R.
It opens only E4U: a new, independently authorized header-only classification of
PAX value shapes. This separates the reason for strict-policy failure from any
claim that a relaxed policy would be safe.

## Majorana P11-E4U/G22 classify PAX value shapes without member reads

G22 authorizes one E4U run. The run classifies all 149,865 PAX-bearing headers
with zero member-payload bytes and no source-text read. `atime`, `ctime`, and
`mtime` are decimal-shaped throughout. For `path`, 149,190 values are missing,
621 equal the `TarInfo` name, and 54 have another relation. Values and member
names are not emitted. This remains metadata evidence only.

## Majorana P11-G23 rejects materialization under the classified policy

G23 concludes that missing `path` values and the 54 unproved relations prevent a
safe PAX-metadata-to-materialized-path mapping. It authorizes neither
materialization nor policy relaxation. E4V may only design a further aggregate,
zero-payload relation proof for the 54 exceptional headers.

## Majorana P11-E4V/G24/G25 closes the PAX path-mapping route

E4V defines four aggregate-only relation classes and G24 authorizes one run.
The run visits 149,865 headers, classifies exactly the 54 exceptional PAX paths,
and reads zero member payload bytes and zero source-text bytes. All 54 are
`unsafe_or_unproven_relation`; exact equality, single-leading-`./` equality and
POSIX lexical normalization each have count zero.

G25 independently binds the result and its external success receipt, closes the
consumed authority, and records
`CLOSE_P11_PAX_PATH_MAPPING_AS_UNPROVEN`. It authorizes no retry, policy
relaxation, materialization, semantic read or new follow-on contract. The route
is `TERMINATE_P11_PAX_PATH_MAPPING_ROUTE`. This is a scoped closure of the
current PAX path-mapping route, not a claim that all source-materialization
strategies or the Majorana program are impossible.

## FB-S0 / FB-S1 same-U temporal-residual lane closes as direct-reduction NO-GO

FB-S0 imported and revalidated the Gaussian-occupation/Q2 interpretation
calibration. FB-S1 then compared exact-minus-TDHF residual forecasts on held-out
L=2 Hubbard U values. The initial d=8 candidate was invalidated after a fixed
parameter undercount was found. A mechanically budget-corrected d=5 amendment
was committed before its outcome and kept every data split, seed and KPI fixed.

All same-U, Gaussian nominal, conservation, dt-refinement, causal-fit and
resource-cap checks pass. The corrected HBR-R1-motivated tanh proxy nevertheless
has median NRMSE `0.9252574169819254`, versus `0.8932096493643846` for the
18-parameter Prony/AR8 direct baseline; effective horizon is zero for both.
The lane therefore closes `NO_GO_DIRECT_REDUCTION`. This is exploratory proxy
evidence only: no BioCortex runtime, HBR-R1 implementation, L=8, BGL, hardware,
non-Gaussianity or quantum-advantage authority is created.

## Matched benchmark external-evidence activation remains fail-closed

The existing FH-L8 validators now have a single activation contract that binds
their current templates and checks the baseline jointly. Cross-route term order,
campaign parameters, bounded reference, native transition, surface place-route
and the matched evidence manifest all remain unresolved for lack of real external
evidence. The baseline is explicitly
`BASELINE_UNRESOLVED_EXTERNAL_EVIDENCE_REQUIRED`; it cannot be upgraded by a
synthetic fixture, assumed hardware value, empty template or uncertified reference.

## FB-S2 closes the current HBR-R1 adapter chain without a performance run

FB-S2 binds BioCortex commit `1539a6f` / tree `1b4eeda`. Static replay verified
the fixed snapshot, all identified record path/hash pairs and cross-record
authority consistency. Of 57 eligibility gates, 5 passed; 5 integrity/resource
fields were unobserved, 28 authority/implementation fields were explicitly
negative, and 19 Fermion mapping/receipt fields were missing. The nine bound
`.rs` source-media files remain outside Cargo/module targets; no materialized
adapter, call edge, registry instance or Fermion mapping is present.

The mandatory upstream integrity gate could not complete inside the frozen
1 GiB, zero-swap cgroup: its pre-check attempted to copy a 1,042,649,166-byte
toolchain library tree into tmpfs, `cp` invoked the OOM killer, and the recorded
victims were the checker/parent `python3` and `bash` processes. Therefore the
machine status is
`INDETERMINATE_SOURCE_AUTHORITY`, not machine `NO_GO`. Independently, the bound
negative authority and implementation records activate
`OPERATIONAL_NO_GO_CURRENT_CHAIN`, so adapter construction, candidate execution
and FB-S2B stop now. This is not a source-integrity, candidate-OOM or performance
result. Reopen requires new owner authority, a hash-bound 1-GiB-safe gate,
materialized adapter/mapping evidence and a new positive-qualification v2.

The historical lane `FH-L8-D5-EVIDENCE-SIGNED-D4-PREFIX-V1` verifies the eight
signed D4 spatial symmetries, all `+1` Néel characters, observable-map
invariance, and exact orbit compression through depth 2 (`225→29`,
`24421→3116`). Depth 3 has `1704285` states; only a
100000-state prefix (`71064` orbits) is certified. The next branch is the
byte-table signed bit-permutation canonicalizer; no D6 or error authority is
granted.

FH-L8 D6 closes the D5 depth-3 orbit-prefix boundary with a byte-table signed
D4 support canonicalizer: all `1704285` states yield `213099` orbits in
the frozen 240-second cap. The `14.856` console timing is not retained in the
result and is non-certifying. Complete depth-3 orbit enumeration is feasible,
but no quotient Hamiltonian or fourth-layer cost is certified.

## FH-L8 external-evidence bootstrap selection is fail-closed

The intake bootstrap now validates every explicit route/file selection against
the frozen route, workload, lattice-size, Trotter-step and nonempty-step
candidate shape before writing a draft registry. It also rejects duplicate
route selections, malformed JSON and paths outside the intake root. This is
candidate-shape validation only: it does not establish provenance, compiler
custody or scientific admissibility, all of which remain owned by the existing
intake validator. With no external raw exports present, all five routes remain
`MISSING` and cross-route comparison remains blocked.

## FH-L8 public export source re-audit remains unresolved

A 2026-07-26 network re-audit downloaded and hash-bound the official source
archives for dynamic-JW arXiv v1 and the adjacent MMD/FSN Hubbard scenario
arXiv v3. Their static inventories contain manuscripts and PDF figures, but no
code/data archive or complete individual-term event sequence. Exact arXiv-ID
repository search returned no candidate, and the native-fermion
machine-readable article still states that study data are included in the main
text. These observations are source-scoped rather than global absence proofs.
All five routes remain `UNRESOLVED_EXTERNAL_EXPORT_REQUIRED`.
