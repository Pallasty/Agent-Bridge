# L=8 Fermi--Hubbard 有界参考策略

更新日期：2026-07-11。

## 结论

目前没有发现可以直接复用、同时匹配 `8 x 8` open-boundary square lattice、
`t=1, U/t=8, tT=1`、checkerboard Néel product state、固定半填充粒子数以及
`staggered_magnetization` / `double_occupancy` 的公开有界参考值。

全态 exact diagonalization 也不是可执行后备方案。在
`N_up=N_down=32` 子空间中，维数已经是

\[
{64\choose32}^2
=3{,}358{,}511{,}241{,}965{,}567{,}934{,}376{,}258{,}434{,}786{,}405{,}156
\approx 3.36\times10^{36}.
\]

因此下一条可行路线不是寻找一个现成的 “exact number”，而是生成一个可独立检查的
deterministic interval certificate。首选是 certified Majorana/Pauli Heisenberg
operator propagation；local-cluster + locality/Krylov bounds 是后备；普通 TDVP、PEPS、
QMC 和当前参数扫描结果继续只作 diagnostic cross-check。

## 方法分级

| 方法 | 当前可获得结果 | 本项目状态 |
|---|---|---|
| Full ED | 原理上 exact，但目标子空间不可存储 | 不可执行 |
| Majorana/Pauli operator propagation | 已能处理强耦合二维 Hubbard 的短时动力学；当前发表结果主要靠参数收敛 | 首选改造成 deterministic certificate |
| Local-cluster Krylov + locality bound | 每一误差项都有严格工具 | 先算 locality tail，再决定是否执行 |
| Certified TEBD/MPS | 可累积 SVD state-norm error，但二维映射资源和界松弛风险高 | 后备 |
| 普通 TDVP/tDMRG/MPS | bond dimension / timestep convergence | diagnostic only |
| fPEPS/PEPS | bond/environment convergence，通常还含近似 contraction | diagnostic only |
| Real-time QMC | 动态 sign/phase 问题与 ratio estimator | diagnostic only |
| DMFT/NQS/强耦合有效模型 | 变分或模型近似 | diagnostic only |

最新的 Majorana-string 算法已针对一维和二维 Fermi--Hubbard quench 展示
Heisenberg-picture observable propagation，并提供公开 Julia 实现；但论文所称的
systematically controlled truncation 和参数收敛还不是本项目要求的逐项绝对误差证书。
参见 [D'Anna--Nys--Carrasquilla](https://arxiv.org/abs/2511.02809) 和
[MajoranaPropagation.jl](https://github.com/SparqleSim/MajoranaPropagation.jl)。

## 首选证书：Majorana/Pauli operator propagation

目标 observable 写成范数为一的 Majorana strings 之和，在 Heisenberg picture 中逐
gate 或逐 slice 传播。每次 truncation 前必须先全局合并重复 strings；随后记录被删
系数的 `L1` 和。对 Pauli operator backpropagation，triangle inequality 已给出严格的
单次 truncation bound，并说明多 slice 的误差需要逐次相加，见
[Fuller et al., npj Quantum Information 12, 51 (2026)](https://www.nature.com/articles/s41534-026-01196-0)。

对每个 Majorana string 同样使用 operator norm `1`，可以得到下面的 proposed
certificate；这是从上述 Pauli 论证到 Majorana basis 的直接范数推论，而不是当前
Majorana 论文已经提供的 artifact：

\[
\epsilon_{drop}
\le \sum_s\sum_{v\in\mathrm{drop}(s)}|c_{s,v}|.
\]

若 `W` 是 reference product formula，`U=exp(-iHT)` 是目标演化，则总 observable
reference bound 至少还要包含

\[
|\Delta\langle O\rangle|
\le
\epsilon_{drop}
+2\|O\|\,\|W-U\|
+\epsilon_{solver}
+\epsilon_{fp}
+\epsilon_{initial}.
\]

两个归一化 observable 都满足 `||O|| <= 1`。这里的 `||W-U||` 必须来自目标 OBC、
实际 Hamiltonian convention、实际 term split 和完整 term order 的严格 commutator
certificate；不能拿小系统上的 empirical convergence 代替。
[Schubert--Mendl](https://arxiv.org/abs/2306.10603) 给出了 Fermi--Hubbard 专用的
higher-order commutator-scaling machinery，但仍需为本项目五分组 OBC 顺序重新生成
bound。所有 coefficient arithmetic 和最终 interval 必须使用 outward/directed rounding。

建议优先采用与四条 benchmark routes 都不同的 reference formula 与实现，避免共享
product-formula bias。当前二阶 `R=100` 只应作为被检对象；reference 可先尝试独立四阶
公式，再把其 product-formula bound 纳入上式。

## 后备证书

### Local cluster + locality + Krylov

对 64 个局域 observable terms 分别选择 cluster，在 cluster 内做有 defect bound 的
Krylov evolution，再用 locality bound 控制删去边界 interaction 的影响，最后对局域项
平均。产品初态 real-time finite-size/locality bound 可参考
[Wang--Foss-Feig--Hazzard](https://arxiv.org/abs/2009.12032)；Krylov matrix-exponential
defect 的可计算 rigorous upper bound 可参考
[Jawecki--Auzinger--Koch](https://arxiv.org/abs/1809.03369)。

应先计算 graph-specific locality tail。如果 tail 本身已超过 reference allocation，
就停止，不启动昂贵 cluster ED。

### Certified TEBD/MPS

只有 “exact local gates + 每次 SVD 的 state 2-norm bound + 严格 product-formula bound +
directed rounding” 才可进入资格审查。普通 TDVP 的 tangent-space projection error 不能
由 discarded weight 自动替代。当前 72-qubit 二维 Hubbard 工作把 tensor-network 与
operator-propagation 结果作为 approximate classical benchmarks，而不是 bounded
certificates，见 [Alam et al.](https://arxiv.org/abs/2510.26845)。

PEPS 还需要认证 contraction error；一般 PEPS contraction 为 `#P-complete`，因此仅做
bond/environment-dimension convergence 不能升级成证书，见
[Schuch et al.](https://arxiv.org/abs/quant-ph/0611050)。

### Real-time QMC

半填充 equilibrium DQMC 的 sign-free 结论不能转移到 unitary real-time quench。
square-lattice Hubbard 的 real-time FPQMC 已明确出现 strong dynamical sign problem；
ABQMC 改善部分时间依赖也没有给出本项目所需的 finite-sample/discretization/ratio
联合 deterministic bound，见
[Janković--Vučičević](https://arxiv.org/abs/2206.08844)。

## Reference qualification artifact

每个 observable 的 binding record 必须至少包含：

- workload、boundary condition、Hamiltonian convention、初态与 observable definition
  fingerprints；
- `value`、`total_abs_bound` 和 deterministic error decomposition；
- method、solver/configuration、implementation commit 与 environment-lock fingerprints；
- 本地 certificate artifact 路径及 SHA-256；
- theorem/assumptions fingerprint、directed-rounding mode；
- reference formula 和 term-sequence fingerprint；
- 明确未使用 route estimates、route samples、route batch IDs 或 route circuit exports 的
  independence ledger。

顶层误差 decomposition 精确分成 time evolution、representation truncation、
floating point 和 observable evaluation 四个聚合桶；product-formula、cluster boundary、
Krylov solver、tensor contraction 或 initial-state preparation 等 method-specific 明细
放入 certificate artifact，并由对应 method claims 指明已覆盖。validator 必须重算顶层
component sum、检查 artifact hash、directed-rounding mode 与 method claims，并要求严格
JSON artifact 的 `record_binding` 与 ledger 的 value/bound/identity/provenance 逐字段一致。

这仍只是结构核验。SHA-256 证明本地 bytes 没变，`record_binding` 证明 artifact 与 ledger
说法一致；二者都不证明误差账本的数学结论是真的。当前 validator 不执行 certificate
checker，也不加载 measurement campaign contract 判断 `total_abs_bound` 是否不超过
`0.00025`，所以最高状态刻意限制为 `STRUCTURALLY_COMPLETE_UNVERIFIED`，并始终输出
`ready_gate_eligible=false`。实现、pin 并实际运行可重算证书的 checker 后，才能设计新的
machine-verified qualification 状态。当前外部 route-input snapshot 也只检查 batch/circuit
两类列表非空且格式正确，并不证明它来自完整 convergence manifest；未来 outer
orchestrator 必须直接从已验证 manifest 注入该 snapshot。结构完整状态的 CLI 因此仍返回
非零退出码。

### 已实现的最小 proof kernel

本阶段新增 `operator_propagation_certificate_checker.py`，把上述方案中的一个真子命题
变成可执行证明：对合同固定的

\[
G_P(\theta)=\exp(-i\theta P/2),\qquad |\theta|\le1,
\]

checker 用纯 `Fraction` Taylor--Lagrange 区间重算 `sin(theta)` / `cos(theta)`，按合同
明确的 backprop order 做 Pauli phase algebra；每个 slice 完成全部 gates 后才合并相同
strings、执行显式 drop，并以区间最大绝对值重算累计 dropped-`L1`。这对应 Fuller et al.
的单次 `L1` triangle bound 和跨 slice 逐项相加规则，而不是典型态 `L2` 估计。checker
source、generator sequence、initial terms 和 computational-basis state 都被独立 SHA/pin
固定；失败输出不会保留任何正的 `*_verified` claim。

最高状态仅为 `VERIFIED_CIRCUIT_TRUNCATION_SUBCERTIFICATE`。输出同时给 retained
expectation interval 与其 `± cumulative_dropped_L1` 扩张，但不判断该界是否足够小。
fermion-to-Pauli mapping、`W_R` 到 ideal `exp(-iHT)` 的 product-formula bound、L=8 和
campaign `0.00025` allocation 全部仍为 `NOT_ASSESSED`；CLI 始终非零，reference validator
也尚未调用此 kernel。

L=2 conformance witness 对 `R=2,T=1` 的 112 个 raw rotations 独立复算得到
`M_s=0.781713978559467`、`D=0.0309252063024724`，与 direct-fermion statevector 一致；
但它与 ideal diagnostic 的差仍约为 `0.12595` 和 `0.00586`，直接说明“circuit arithmetic
正确”不等于“ideal-time reference 已认证”。完整 112-gate Fraction expansion 在当前纯
Python sparse representation 中出现快速 term/rational growth，因此标为
`DEFERRED_RESOURCE_LIMIT`。下一实现层必须引入 bitset Pauli keys、批量 directed
arithmetic 和受审计的 checkpoint/digest，而不能降低为 binary64 后继续声称 rigorous。

`standard_error=0` 只表示 deterministic certificate，不等于 bound 为零。未经证书的
Majorana/MPS/PEPS/QMC 数值，即使跨参数看似收敛，也只能标 `DIAGNOSTIC_ONLY`。

## 执行顺序

1. 冻结 OBC、未平移的 `U n_up n_down` convention、A/B Néel 相位和两个 observable 的
   canonical formulas。
2. 固定 MajoranaPropagation implementation commit；先补 deduplicate-before-truncation、
   per-slice dropped-L1 ledger、directed coefficient intervals 和小尺寸 ED 对照。
3. 为独立 reference formula 生成目标 OBC term split 的 commutator certificate。
4. 以 machine-checked `total_abs_bound` 达到 campaign reference allocation 为停止条件；
   两个 observables 可以采用不同 certified methods。
5. 若 Majorana L1 bound 爆炸，先计算 locality tail，再决定是否执行 cluster Krylov。
6. TDVP、PEPS、当前 Majorana 参数扫描、QMC 和 effective-model 结果保留为独立诊断，
   不参与任何 machine-verified reference 或 READY 判定。

更一般的 bounded-error quantum simulation 已能把 learned Hamiltonian/Lindbladian 的
实验不确定度传播到 observable interval，但目前示范对象是 long-range Ising，不是匹配
的 Hubbard workload，见 [Kraft et al.](https://arxiv.org/abs/2511.23392)。这条路线可作为
未来 `stochastic_certified` schema 的参考，当前不能冒充 `exact_bounded`。
