# L=8 Fermi--Hubbard 有界参考策略

更新日期：2026-07-12。

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
正确”不等于“ideal-time reference 已认证”。早期字符串稀疏实现的完整 112-gate
Fraction expansion 因 term/rational growth 标为 `DEFERRED_RESOURCE_LIMIT`；下述 bitset
checkpoint 层现已消除这个特定实现障碍，但没有消除 R=2 product-formula error。

### 已实现的 canonical JW mapping 子证书

`hubbard_jw_mapping_validator.py` 现已把“L2 witness 的 declared gates 是否真来自固定
Hubbard convention”从人工复核变成独立 machine check。合同固定 L=2/L=3 OBC、
site-major/spin-minor、未平移的 `U n_up n_down`、`U/t=8,T=1,R=2` 和 raw Strang 顺序；
checker 重新生成四个 hopping matchings、`-1/2(XX+YY)` 的中间 Z 串以及 onsite
`2(I-Zup-Zdown+ZZ)`。L3 的 H2/H3 各有六条 spin-resolved bonds，因而覆盖 L2 无法触发
的 odd-parity 分支。

每条 hopping bond 用八类 occupation witnesses 比较 CAR 与 Pauli action，其中包括
prefix/suffix spectator；每个 site 的 `00/10/01/11` 能量重新得到 `0/0/0/8`。Raw events
保留 identity rotations，并把非恒等 gate view 省略的全局相位显式记为 L2 `exp(-i*8)`、
L3 `exp(-i*18)`。正路径还运行 SHA-pinned L2 builder，逐项要求其 112 门与 canonical
sequence 完全相等。最高状态仅 `VERIFIED_CANONICAL_JW_MAPPING_SUBCERTIFICATE`；它没有
与 truncation kernel 组合，也没有验证 product-formula error、L=8 或 READY。

### 已实现的 bitset/checkpoint 原型

`pauli_bitset_backend.py` 采用 q0-first `(x_mask,z_mask)` Hermitian Pauli 编码，提供精确
相位乘法、辛对易、与现有 checker 同语义的 Fraction 区间传播，以及对排序稀疏项的
canonical JSON/SHA-256 checkpoint。固定样例 digest 为
`c69ecf852f053106f0feb89cd0c2e220903ef862974fd5821786605cec9929dd`。本机固定种子、
16-qubit/100,000 对诊断微基准中，预编码 bitset 的 multiply/commute 分别约为字符串实现
的 `3.5x/9.6x`；这些数值仅是 CPython 本机诊断，不是规模保证。该模块的 certificate
authority 固定为 `NONE`；它本身没有被升级为证书。新的 checker 将其 source-pin 后作为
算术依赖使用。其 `max_bytes` 只限制 canonical serialization 输出；payload 构造峰值另由
term-count/rational-digit caps 有界，不能把该字段解释为严格峰值内存证书。

### 已实现的完整 L2 checkpoint 子证书

`operator_propagation_checkpointed_l2.py` 从已哈希的精确源码字节加载 mapping、bitset、
Fraction kernel 与 L2 witness 依赖，并要求 mapping 正状态和 112 门 canonical sequence
逐项一致。对两个 observable 都反向执行 20 个 raw group-event checkpoints；每一 slice
使用五阶 Taylor--Lagrange 区间，然后向外量化到分母 `2^32`，再按 deterministic top-L1
规则执行容量上限 65,536 的保留。正 fixture 实际没有触发 drop：`M_s` 的 final/peak term
count 是 16,380，`D` 是 16,381，二者累计 dropped-`L1` 均为 `0/1`，最大有理数位数为
151。

最终 declared mapped-circuit intervals 为

\[
M_s\in[104895467/134217728,\;209888553/268435456]
      \simeq[0.7815321311,0.7818957902],
\]

\[
D\in[8238201/268435456,\;33458587/1073741824]
    \simeq[0.0306896903,0.0311607374].
\]

对应 float statevector 值被区间包含，但明确标为 diagnostic、`used_as_proof=false`。
最高状态是 `VERIFIED_L2_MAPPED_CIRCUIT_TRUNCATION_SUBCERTIFICATE`。这里“zero drop”只
说明该次容量截断没有误差，不说明 Taylor/量化区间宽度为零，更不说明 `W_{R=2}` 已靠近
`exp(-iHT)`；product-formula、L8 workload、campaign allocation、reference qualification
与 READY 仍为 `NOT_ASSESSED/false`。

### 已实现的 Strang 嵌套对易子 L1 子证书

`hubbard_strang_commutator_checker.py` 采用
[Schubert--Mendl Proposition 2, Eq. (13)](https://arxiv.org/html/2306.10603#S2.E13)
（论文 DOI [10.1103/PhysRevB.108.195105](https://doi.org/10.1103/PhysRevB.108.195105)）
固定的二阶对称公式。对顺序 `H1,H2,HU,H3,H4`，令

\[
K_\gamma=\sum_{j>\gamma}H_j,\qquad
C=\sum_\gamma\left(
\frac{\|[K_\gamma,[K_\gamma,H_\gamma]]\|}{12}+
\frac{\|[H_\gamma,[K_\gamma,H_\gamma]]\|}{24}\right).
\]

checker 对每个外层 `gamma` 和每个 theorem family 分别精确合并相同 Pauli strings，再以
coefficient `L1` 上界 operator norm；不同 family 之间不允许抵消。R 个 unitary steps 由
telescoping 给出 `C T^3/R^2`，而任意 `||O||<=1` 的 expectation comparison 需要额外因子
2。Raw palindrome 的十个 group events、每个 commuting term product 和被省略的 onsite
identity common phase 都有独立账本。

L8 五组非恒等 Pauli term counts 是 `(128,96,192,96,128)`；两个 nested-family L1 总和
分别为 22,752 与 11,104，因此

\[
C=7076/3,\qquad
\epsilon_U(R=100)\le1769/7500,\qquad
\epsilon_O(R=100)\le1769/3750\simeq0.4717333.
\]

这远大于单 observable allocation `1/4000=0.00025`；在同一 generic observable bound
下最小整数是 `R=4344`，`R=4343` 仍失败。这个结果只否定“当前五组划分 + coefficient-L1
+ generic factor-two + R=100”作为紧参考界的可行性，并不排除 observable/locality-specific
cancellation、Schubert--Mendl 使用的 plaquette grouping、另一独立高阶 reference formula
或更紧的 norm evaluation。该论文也明确指出四个 even/odd kinetic partitions 比其
plaquette grouping 给出更弱的界，所以不能把论文的 PBC plaquette 数值直接移植到这里的
OBC 五组 split。当前状态仍不组合 mapping/truncation，也没有认证 physical L8 initial
state、两个 observables 或 READY。

### 已实现的 grouping coefficient-L1 穷举筛选

`hubbard_strang_grouping_screen.py` 把“是否只需换 group order 或 plaquette split”变成
独立 machine check。它 source-pin 上述 commutator checker/contract/template，先要求基础
子证书为正，再对固定 L8 OBC Hamiltonian 执行两组穷举：

- 原 `H1,H2,HU,H3,H4` 的全部 120 个 permutations；
- 两个 bulk plaquette families `P0/P1`、一个 boundary residual `B` 与 `HU` 的全部
  24 个 permutations。

OBC candidate 将 112 条 spatial bonds 精确分为 `64+36+12`，对应 Pauli term counts
`(256,144,48,192)`，与原 640-term nonidentity Hamiltonian 完全相等。`P0/P1` 分别包含
16/9 个互不重叠 plaquettes；不同 plaquettes 互不作用，但一个 plaquette 内的边不全对易，
所以 `exp(-itP0)` / `exp(-itP1)` 需要真正的 cluster evolution，不能冒充当前逐 hopping
term benchmark circuit。

穷举结果是：

| screen | best `C` | generic R=100 observable bound | allocation 所需最小 R |
|---|---:|---:|---:|
| declared five groups | `7076/3` | `1769/3750` | 4344 |
| best of 120 orders | `7072/3` | `884/1875` | 4343 |
| best OBC plaquette+boundary order | `7232/3` | `904/1875` | 4392 |

重排相对改进只有 `1/1769≈0.0565%`，低于合同预先固定的 1% material threshold；OBC
plaquette regrouping 在同一 coefficient-L1 reduction 下反而更差。R=100 的 `1/4000`
observable allocation 等价于 `C<=5/4`，所以仍缺约三个数量级。

主源的 Section III.B / Eq. (19) 是 even-L PBC 三组方案，并假设 plaquette 四条 hopping
可同时实现；其 Section V.C 使用最多 14 fermionic modes 的 exact/cluster spectral norms，
这正是论文优于简单 Pauli-L1 的来源。将论文打印的四位小数系数在 `|v|=1,|u|=8` 下仅作
nonbinding diagnostic，会得到每 site `C≈25.4537`；即使形式上乘 64 sites，generic R=100
仍约 `0.326`，远超预算。由于 boundary、rounding direction 和 implementation identity
均不匹配，这个数没有进入 certificate。机器结论只排除 coefficient-L1 regrouping，下一
层必须是 certified cluster spectral norm 或直接面向两个 observables/locality cones 的界。

### Cluster spectral 主源审计与 exact generic-bound no-go

论文配套的[官方实现](https://github.com/qc-tum/fermi_hubbard_commutators)已固定到与最终
square plaquette 版本对应的 commit
[`859bef092675957ae126e9d3b09dc3c63b213859`](https://github.com/qc-tum/fermi_hubbard_commutators/commit/859bef092675957ae126e9d3b09dc3c63b213859)。
其 `SumOp.norm_bound()` 对不超过 14 active fermionic modes 的 compact Fock matrix 按粒子
数分块做 dense spectral norm；更大非二次 operator 先拆 support graph components，再用
“新增 modes 最少”的 greedy clusters。14 是实现阈值，不是定理。源码把系数转为 float，
调用 NumPy binary64 norm/eigensolver，没有 outward rounding、interval residual 或证书；满占据
block 还需由新 checker 单独验证。因此论文的 “numerically exactly” 不能解释成我们的
`exact_bounded`。

作为诊断，固定 OBC 五组的完整 14-mode prototype 得到：

| quantity | Pauli-L1 certificate | binary64 cluster diagnostic |
|---|---:|---:|
| tail-family sum | 22,752 | 11,810.1186 |
| self-family sum | 11,104 | 8,634.8900 |
| `C` | `7076/3≈2358.6667` | 1,343.9636 |
| generic R=100 bound | `1769/3750≈0.47173` | 0.26879 |

原型含 105 clusters，其中 94 个达到 14 modes；运行约 65.8 s、峰值约 69.5 MiB。它将
`C` 降低约 43%，但仍是所需 `C<=5/4` 的约 1075 倍，且数值本身不是 certificate。

更强且完全 exact 的路线判据已由
`hubbard_strang_generic_bound_no_go_checker.py` 实现。令

\[
A=[K_1,[K_1,H_1]],\qquad
|q\rangle=|\text{checkerboard Néel}\rangle,\quad N_\uparrow=N_\downarrow=32.
\]

checker 重算 A 的 3,072 个 merged Pauli terms，并得到 416 个非零输出与

\[
\|A|q\rangle\|_2^2=295200=3600\cdot82.
\]

由于 `|q>` 已归一化，`||A||²>=295200`；而 Proposition 2 中这一项的 weight 是 `1/12`，
所以

\[
\left(\frac{\|A\|}{12}\right)^2\ge2050
>\frac{25}{16}=\left(\frac54\right)^2.
\]

整个 `C` 是非负 norm terms 之和，因此仅此一项就超过 R=100 allocation 允许的总 ceiling。
等价地，generic theorem expression 至少为 `sqrt(82)/1000`，是 `1/4000` 的
`4*sqrt(82)≈36.22` 倍；由精确四次幂比较，R=601 仍被排除，R=602 只是“不再被这个单
witness 排除”的必要门槛，并非充分条件。所有 416 个输出都机械验证仍在
`N_up=N_down=32` sector，所以把 operator norm 限制到物理守恒 sector 也不能改变结论。

这个 no-go 只针对固定五组、固定二阶公式的 **generic operator-norm bound expression**。
它没有证明 actual Trotter error 很大，也没有排除两个 observable 的 cancellation/locality
cone、不同 grouping 或高阶 formula。由此停止继续认证该固定 generic cluster 上界，下一
主线正式转为 observable/locality-specific bound。

`standard_error=0` 只表示 deterministic certificate，不等于 bound 为零。未经证书的
Majorana/MPS/PEPS/QMC 数值，即使跨参数看似收敛，也只能标 `DIAGNOSTIC_ONLY`。

## 执行顺序

1. L2/L3 的 OBC、未平移 `U n_up n_down` 和 canonical JW term split 已冻结，完整 L2
   checkpoint propagation 已闭合；下一步为 L8 固定 A/B Néel 相位、两个 observable 和
   与真实 campaign 相同的 occurrence-level term-sequence identity。
2. 固定五组 generic bound 已被 half-filled-sector exact witness 严格排除；不再投入其
   14-mode cluster spectral upper bound。转而实现两个 target observables 的 locality cone /
   Heisenberg commutator bound，并平行筛选真正不同的 grouping 或高阶 formula。每个候选
   仍须保留 source-pinned constants、common-phase ledger 与可机检 records。
3. 固定 MajoranaPropagation implementation commit；补 deduplicate-before-truncation、
   per-slice dropped-L1 ledger、directed coefficient intervals 和小尺寸 ED 对照，并把
   L8 initial observable/state identity 与完整 mapped sequence 组合进 checker。
4. 以 machine-checked `total_abs_bound` 达到 campaign reference allocation 为停止条件；
   两个 observables 可以采用不同 certified methods，不能只因增大 R 就跳过资源与独立性
   复核。
5. 若 Majorana L1 或 locality tail 已超过 allocation，再决定是否执行 cluster Krylov。
6. TDVP、PEPS、当前 Majorana 参数扫描、QMC 和 effective-model 结果保留为独立诊断，
   不参与任何 machine-verified reference 或 READY 判定。

更一般的 bounded-error quantum simulation 已能把 learned Hamiltonian/Lindbladian 的
实验不确定度传播到 observable interval，但目前示范对象是 long-range Ising，不是匹配
的 Hubbard workload，见 [Kraft et al.](https://arxiv.org/abs/2511.23392)。这条路线可作为
未来 `stochastic_certified` schema 的参考，当前不能冒充 `exact_bounded`。
