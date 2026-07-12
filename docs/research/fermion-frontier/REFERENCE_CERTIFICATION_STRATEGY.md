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

### MajoranaPropagation 主源与执行基线审计

论文当前只有 [arXiv:2511.02809v1](https://arxiv.org/abs/2511.02809v1)；审计 PDF
SHA-256 为 `be16b251adfef08eff14a7876addae0084ec78143173db5a296cae128bdf06cb`，
source tar SHA-256 为
`7d12e0b80ad7b61a910c9cebd5aa192f4832b638bcb3fb64db7be048ebee37a5`。
论文和 Code Availability 都没有给 tag/commit。提交日最近 merged-to-main 的 PR squash commit
`1a39fbf9af9be486ceca86c0e952fbd0a227ff42` 只能标为 **inferred paper snapshot**，
不能称为作者确认的 paper commit；而且它早于
[`46b696b`](https://github.com/SparqleSim/MajoranaPropagation.jl/commit/46b696bc62bc60e2580ab8d6e1037722d5caf61d)
所记录的 Majorana splitting “extra minus sign” 修复，因此不能作为证书执行基线。

当前最稳妥的 fork 基线是已注册 `v0.3.0` 的
[`main@b7849cb`](https://github.com/SparqleSim/MajoranaPropagation.jl/commit/b7849cb4bac5b604f0d2fe6ff807ed889305e668)，
tree `d62823f20677593ff5e256e5f8bc316dd7aecd7a`。其 `Project.toml` 中
`PauliPropagation = "0.7.2"` 是 compat 下界而非 lock；仓库没有 Manifest。在
2026-07-12 General registry 与兼容 Julia 环境下，fresh resolve 会选择
`PauliPropagation v0.7.3`、commit
`2a96e9a94dafc2df3466d2611fafa141319469f8`、tree
`757b43af3c247d9fad953dd056d3df76fe6e6a08`。证书 fork 必须提交完整 Manifest，不能只写
compat 字符串。

关键执行面 source pins 如下；完整 fork 还需把所有加载源码与 Manifest 一并 pin：

| source | SHA-256 |
|---|---|
| MP `Project.toml` | `692cceeecda9e613e31bb8a827d956ee922623b1b493be5f2b8a80a56e193fec` |
| MP `src/gates.jl` | `b268a49da3b13ba9d6f98ec3e43861b18ffd7faf83497909efff009b365c6689` |
| MP `src/truncations.jl` | `efd0dd8d64726de8b92782c7d93cf5ed7b1da08049a057d7877a5a47e92dc4c3` |
| MP `src/propagation.jl` | `3064b54daa1d0e3f2b1e2dfcb8c2f920898561e6b5db55fe2943d35505f7e115` |
| MP `src/MajoranaDataTypes.jl` | `73c3c1b889857b2c44e1e45c5ddaba1758c320f1350efe0bb21c961506b33803` |
| PP v0.7.3 `src/Base/merge.jl` | `3cb7a51fd80d4ca34f666b1c4950244557eca3f2a7fa09dfc4018e159098f4c6` |
| PP v0.7.3 `src/Base/truncate.jl` | `ce959eadff90c8b59a34a4a6acb8d056c4b044404be44469832c233f930c776e` |
| PP v0.7.3 `src/Base/propagate.jl` | `9cd0fb092dd1e76137b5c21735fc306d0fb2ccdaab322a4ebd6e45b7dcd21129` |

源码审计确认当前顺序是 branch 后先 merge/deduplicate、再 truncate；阈值比较是严格
`abs(c)<epsilon`。`:hop/:hopup/:hopdn` 在每个 constituent Majorana rotation 后 merge，
但延迟到完整 `FermionicRotation` 后 truncate；其他 composite 默认每个 constituent 后
truncate。现有 `truncate!` 只删除项，不返回 dropped terms/reason/`L1`，Float64
`sin/cos` 与 merge 也没有 directed enclosure。未合并的
[`327ef11`](https://github.com/SparqleSim/MajoranaPropagation.jl/commit/327ef11f4bb9e175532dd9d9600667a972bfae27)
才把 composite Majorana terms 按 bitmask 排序；certificate fork 应移植这项确定性修复，
但不直接跟随整个实验分支。

因此 P0 基线已冻结为：从 `b7849cb` 建最小 fork，固定 Julia/Manifest 与
PauliPropagation v0.7.3，序列化 Schrödinger/Heisenberg occurrence digests，并在每次
dedup 后记录 canonical dropped-term digest、reason 与
`sum sup(abs(coefficient_interval))`。区间跨过 cutoff 时必须保留；最终把
`B_trunc+B_round+B_Trotter` 分项报告。当前论文的 `S,epsilon` convergence 和
PauliPropagation `estimatemse` 都不是这种 deterministic absolute bound。

论文的二维展示也不与本项目 workload 同一：它使用 3x3、7x7、19x19 的 checkerboard
背景单-hole/多区域 hole observables（3x3 取 `U/t=8`，7x7 取 `U/t=8.72`），而不是
8x8 无 hole 初态的两个全局 observables；论文未报告这些二维图的 Trotter `dt`，审计的
`main@b7849cb` tree 中也没有对应 figure scripts、Manifest 或 raw data。因此即使参数扫描
收敛，也不能转写成当前 campaign 的 bounded reference。

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

### Fang--Qu observable Taylor 单步核与 R-step 路线判决

observable-specific Taylor 路线的主源固定为 Fang--Qu，*Uniform Semiclassical
Observable Error Bound of Trotter--Suzuki Splitting: A Simple Algebraic Proof*，
[SIAM J. Numer. Anal. 64 (2026)，DOI 10.1137/25M1777098](https://doi.org/10.1137/25M1777098)，
[arXiv:2507.02783v2](https://arxiv.org/abs/2507.02783)。本次审计下载的 v2 PDF SHA-256
为 `c1afaae4a944ba5c32bb5c86e421986bbcd89c14dae959d73560db979e668806`。
采用其 Eq. (3.9) 的逐 stage、由内向外积分 Taylor 展开，而不是对整条径向 product 的
四阶导数作朴素估计；后者会产生 interleaved exponentials，不能直接化为 `t=0` nested
commutators。

将相邻两个半步 `H4` 合并后，固定一步是 9-stage palindrome

\[
(H_1,H_2,H_U,H_3,H_4,H_3,H_U,H_2,H_1),\qquad
(c_1,\ldots,c_9)=(1/2,1/2,1/2,1/2,1,1/2,1/2,1/2,1/2).
\]

令 `ad_A(B)=[A,B]`。product 与 ideal Heisenberg maps 的 formal degrees 0--2 精确相同，
degree-3 差记为 `D3(O)`；四阶 ideal remainder 与逐 stage product remainder 分别由

\[
E_4(O)=\frac{\|\operatorname{ad}_H^4(O)\|}{24},
\]

\[
P_4(O)=
\sum_{q_1+\cdots+q_9=4}
\left(\prod_{j=1}^9\frac{c_j^{q_j}}{q_j!}\right)
\left\|
\operatorname{ad}_{H_9}^{q_9}\cdots
\operatorname{ad}_{H_1}^{q_1}(O)
\right\|
\]

控制。共有 `binom(12,8)=495` 个 weak compositions。由于所有 Hamiltonians Hermitian、
所有 `c_j` 为正，外层 exact conjugations 是 operator-norm isometries，故不需要
`delta<=1` 假设，也没有遗漏 exponential prefactor。以完全 merge 后的 Pauli coefficient
`L1` 上界代替各 operator norms，可严格得到初始 observable 的单步界

\[
\|\mathcal P_\delta(O)-\mathcal E_\delta(O)\|
\le \delta^3\|D_3(O)\|+\delta^4(E_4(O)+P_4(O)),\qquad \delta\ge0.
\]

L8 exact Fraction 重算结果为：

| observable | `D3` | `E4` | `P4` | `E4+P4` | `delta=1/100` 单步上界 |
|---|---:|---:|---:|---:|---:|
| staggered magnetization | `1703/24` | `15275/12` | `25287/16` | `136961/48` | `159187/1600000000` |
| double occupancy | `423/16` | `16633/12` | `37211/24` | `70477/24` | `133927/2400000000` |

这些量已由 `hubbard_strang_observable_taylor_step_checker.py` 对 L2/L3/L8 与两个
observables 机器重算。最高状态仅
`VERIFIED_ONE_STEP_OBSERVABLE_TAYLOR_L1_SUBCERTIFICATE`，CLI 固定非零。L8 的 exact
Néel-sector `D3` action 进一步得到 magnetization 的 norm-square 下界
`135913/18432>(5/2)^2`，所以即使把该 leading coefficient 的 Pauli-L1 换成精确 sector
norm，uniform-leading architecture 也不能达标；double occupancy 的同一 witness 为
`79145/73728<(5/2)^2`，没有排除更紧 sector norm。两者 `<q|D3|q>=0`，只收紧初始单步
expectation remainder，不能推断后续 steps 消失。
Checker 运行时重新绑定既有 Strang backend/contract/template，包括 warm-cache path；但该
最小 artifact 还没有自身 same-byte contract，论文 PDF SHA 也只作为外部审计 metadata。
这不影响本轮 exact arithmetic，但在接入 outer custody chain 前仍需补齐。

即两个严格单步界约为 `9.9491875e-5` 与 `5.5802916667e-5`。它们只绑定初始 `O`，
不能乘 100 冒充完整演化。若 `E_delta`、`P_delta` 分别表示 exact/PF 单步 Heisenberg
map，正确 telescoping 是

\[
\|\mathcal P_\delta^R(O)-\mathcal E_\delta^R(O)\|
\le\sum_{k=0}^{R-1}
\| (\mathcal P_\delta-\mathcal E_\delta)(O_k)\|,
\qquad O_k=\mathcal E_\delta^k(O),
\]

或使用 PF-evolved observable 的反向版本。外层等距性不能把 `O_k` 换回初始 `O`。
因此严格 uniform-sup 架构必须使用

\[
\frac{\sup_k\|D_3(O_k)\|}{R^2}+
\frac{\sup_k(E_4(O_k)+P_4(O_k))}{R^3}.
\]

这个架构已经可以提前停止：supremum 包含 `k=0`，所以 R=100 的右端 floor 至少为
`159187/16000000` 和 `133927/24000000`，分别是 `1/4000` allocation 的
`159187/4000=39.79675` 倍与 `133927/6000≈22.32117` 倍。这个判决只排除“逐步
triangle + uniform supremum + 当前 Pauli-L1 substitution”；逐 `k` 求和、直接保持不同
step defects 的 cancellation、state/sector-specific action 或其他更紧 norm 仍然开放，
也没有给出 actual Trotter error 下界。

### Double-occupancy D3 固定 cluster-triangle uniform-sup 路线 no-go

double occupancy 的单个 Néel action 小于 `5/2` 并不等于 cluster tightening 可行。新的
`hubbard_d3_double_occupancy_cluster_no_go_checker.py` 把该问题闭合到一个更窄但严格的
决策边界。它先把 `D3=-i[B3,D]` 的 2,748 个 fixture-defined simplified
physical-fermion terms 独立展开
为 18,544 个 field terms，再做 exact Jordan--Wigner mapping；所得 8,928 项 Pauli
expansion 与上述 Taylor checker 逐项一致，二者 digest 均为
`069f0d7d28804d2981081b84393e88696a55628814da625ff82df0beaa262aba`，`L1=423/16`。
因此 cluster fixture 的物理算符身份不依赖外部 binary64 spectral calculation。

随后按 fixture order 重放 externally audited
reversed-order/minimum-support-addition、14-mode greedy rule，得到 43 个 clusters。checker
明确标记：fixture decomposition/order 来自 upstream simplify 的 provenance 是外部审计，
没有在运行时从 upstream 源码重生成；已机检的是 fixture 总和的 exact D3 身份、单连通
128-mode support graph 和后续 partition/action。对每个 cluster `C_j`，checker 直接在全局 128-mode
checkerboard Néel basis state 上计算一个最大绝对矩阵元，因此在全局
`N_up=N_down=32` sector 中严格有

\[
\|C_j\|\ge \max_x |\langle x|C_j|q\rangle|.
\]

前 30 个非负下界已经满足

\[
\sum_{j=0}^{29}\|C_j\|\ge\frac{1945}{768}
=2.532552\ldots>\frac52,
\]

严格 margin 为 `25/768`。所以即使把这 43 个 cluster 的 Gershgorin/row bounds 全部换成
exact spectral norms，这个 **k=0 fixed-partition triangle bound** 仍不可能小于 uniform-sup
证书所需 `5/2`，因而不能作为 100 步共同 supremum coefficient。它不排除逐 `k` triangle
ledger：k=0 的上述 partial floor 在该求和中只贡献
`(1945/768)/100^3=389/153600000≈2.53e-6`。这里也绝不能把 cluster norm 下界相加成
globally merged `D3` norm 的下界；跨-cluster cancellation、不同 partition 和直接 global
half-sector norm 都仍开放。
checker 的最高状态仅
`VERIFIED_D3_DOUBLE_OCCUPANCY_CLUSTER_UNIFORM_SUP_NO_GO`，有 same-byte source contract、
40 个回归测试，CLI 固定退出 1；不认证 actual R=100 error、reference 或 READY。

### Evolved-observable 资源测量与已实现的 L8 mapped 单步内核

对每个 `O_k` 重跑完整 495-path `D3/E4/P4` 不是最小可行实现。L8 exact Pauli growth 为：

| observable | `O` | `ad_H O` | `ad_H^2 O` | `ad_H^3 O` | `ad_H^4 O` |
|---|---:|---:|---:|---:|---:|
| staggered magnetization | 128 | 448 | 1,800 | 9,008 | 50,144 |
| double occupancy | 192 | 896 | 6,688 | 30,912 | 157,892 |

`D3` map 本身含 6,996 项；作用在初始 observable 后输出 6,784/8,928 项，作用在
一阶 evolved component `ad_H(O)` 后已增至 42,488/88,352 项。double occupancy 若继续
构造 `ad_H^5(O)`，仅最后一层 pair-product floor 就是
`640*157892=101050880`。这已经足以停止“每个 k 重算完整 fourth remainder”的实现方向。

独立 binary64 PF resource probe（明确 `DIAGNOSTIC_ONLY`）在首个反向 step 内看到
magnetization 项数 `128→256→608→2048→16064→229776`，double occupancy
`192→640→5136→20112→255204`；第一次压回 65,536 项时 top-`L1` drop 约为
`2.74e-10` 与 `4.38e-10`。这些小数不是证书，但说明直接 observable propagation 值得
继续。下一内核因此固定为 **逐 gate/stage outward interval propagation + deterministic
top-L1 + cumulative dropped-L1 ledger**，先认证相对于未截断 product formula 的传播误差；
不再逐 `k` 枚举 495 条 Taylor paths。top-K 合同还必须明确按 interval absolute upper
bound 降序、bitmask 升序 tie-break、精确保留 K 项；这与官方 `abs(c)<epsilon` cutoff 是
两个不同策略，不能混写。

上述 direct-propagation 内核现已落地为严格子证书。checker 独立重建 L8 OBC 五组，
固定中央 H4 在截断前融合后的九 stage、1,152 门序列，并对两个 observable 使用
`2^64` tick、`N=5` Taylor outward intervals、每八门 merge-then-top-65,536。九个
stage 的门数均被八整除，所以 144 个 checkpoint 不跨 stage；这是固定资源政策，
不是 batch size 或 interval box 的最优性结论。

| observable | peak/final terms | cumulative dropped `L1` | retained Néel interval, ticks/`2^64` | declared mapped-step interval, ticks/`2^64` |
|---|---:|---:|---|---|
| staggered magnetization | 115,492 / 65,536 | `4619985807746/2^64` | `[18433845192157367192,18433845192157371232]` | `[18433840572171559446,18433849812143178978]` |
| double occupancy | 199,528 / 65,536 | `130757007004862/2^64` | `[6447487876967911,6447487876983172]` | `[6316730869963049,6578244883988034]` |

retained coefficient box 已包含 Taylor enclosure、trigonometric grid quantization
与逐乘法 outward rounding widening；这些不能作为独立 scalar error 重复相加。
累计 dropped-`L1` 则利用后续精确 unitary conjugation 的等距性，扩张最终
expectation interval。最高状态仅为
`VERIFIED_L8_ONE_STEP_MAPPED_INTERVAL_TRUNCATION_SUBCERTIFICATE`：这里的
“untruncated”只指同一个 fused mapped product-formula step 未执行 top-K，绝不指
`exp(-iH/100)`。

parent--child chain 的第一个真实 child 也已闭合。boundary 1/2 的完整 65,536-term
coefficient boxes 分别存为 canonical compact JSON，经单流 zlib 与 100-column Base85
封装；checker 同时验证 encoded/compressed/raw/state/semantic hashes、严格数值排序、
整数与解压资源上限。boundary 1 必须逐字段等于 same-byte positive parent 的 retained
expansion、累计 drop 与 Néel expectation，随后 step 2 独立执行固定九 stage、1,152 门、
144 checkpoints。child 边界处不融合相邻 H1 half stages，boundary 2 与重算 expansion
做完整 dictionary equality，而非只比较 digest。

链不变量冻结为：存在 `A_k` 位于 retained interval box，且未截断 mapped-PF observable
与 `A_k` 的 operator-norm 距离不超过 `E_k`。精确 unitary 共轭保持 `E_k`，所以
`E_{k+1}=E_k+d_{k+1}`，其中只有实际删除项的 Pauli-`L1` 进入 `d`；Taylor、trig grid
与乘法 rounding 只扩大 coefficient box，不再作为 scalar error 相加。

| observable | step-2 peak/final | child drop, ticks/`2^64` | two-step cumulative drop, ticks/`2^64` | declared two-step interval, ticks/`2^64` |
|---|---:|---:|---:|---|
| staggered magnetization | 103,720 / 65,536 | `207375793741436/2^64` | `211995779549182/2^64` | `[18395060021948335379,18395484013507455340]/2^64` |
| double occupancy | 105,350 / 65,536 | `2152392847533726/2^64` | `2283149854538588/2^64` | `[23418151510906025,27984451220025405]/2^64` |

double occupancy 的累计 half-width 已约为 `1.23770e-4`，占 `1/4000` allocation 的
49.5%；step-2 local drop 又是 step 1 的 16.46 倍。因此不得直接执行 fixed-K step 3，
必须先冻结更大 retained/single-expansion caps 或 deterministic adaptive-K rule。
磁化量累计约 `1.14923e-5`，可继续做 fixed-K step-3/4 稳态资源测量。任何走势都不能
线性外推到 R100；product-formula-to-exact-Hubbard 项仍须独立组合。

普通 light-cone 不能替代这一步。对二阶 chromatic formula，`chi=5`、`Upsilon=2`、
`R=100` 给出 `(chi-1) R Upsilon+3=803` 层，而 L8 OBC 物理格点直径仅 14，已经完全
饱和；此外已发表 theorem 按 qubit Pauli support 陈述，JW 竖向 hopping 是长字符串，若
在物理 site support 上使用还必须补 even-CAR 适配证明。下一可检验单元因此是直接
evolved-observable ledger：优先复用 Majorana/Pauli propagation，记录每个 gate/stage
的 retained interval、rounding widening 与 dropped-`L1`，再把 product-formula/Trotter
项作为独立预算组合；不再把初始 `D3/E4/P4` 核机械提升为逐 `k` 实现。

`standard_error=0` 只表示 deterministic certificate，不等于 bound 为零。未经证书的
Majorana/MPS/PEPS/QMC 数值，即使跨参数看似收敛，也只能标 `DIAGNOSTIC_ONLY`。

## 执行顺序

1. L2/L3 的 OBC、未平移 `U n_up n_down` 和 canonical JW term split 已冻结，完整 L2
   checkpoint propagation 已闭合；L8 初态、双 observable、mapped fused sequence 与
   首个和第二个 interval boundary 以及 step-2 child 已闭合。下一步为磁化量 fixed-K
   step 3，并先为 double occupancy 冻结 cap/adaptive-K policy。
2. 固定五组 generic bound、uniform-supremum Pauli-L1 shortcut，以及 double occupancy
   用 fixed greedy14 cluster-exact-norm triangle 作为 uniform supremum 的架构都已被 exact
   witness 严格排除；逐 `k` cluster triangle ledger 仍开放。直接 evolved-observable
   propagation 已完成两步，不再逐 `k` 重算 495 paths；cross-cluster/global
   cancellation-aware 方法仍作为平行数学路线。
3. Majorana 执行基线已固定为从 `main@b7849cb` 建 certificate fork，pin Julia Manifest 与
   PauliPropagation v0.7.3，并移植 deterministic composite bitmask sort。补
   deduplicate-before-truncation、per-gate/stage dropped-L1 ledger、directed coefficient
   intervals 和 L2/L3 ED 对照。该 fork 是平行 custody/实现路线，不能覆盖现有 Python
   one-step checker 的 authority。
4. 以 machine-checked `total_abs_bound` 达到 campaign reference allocation 为停止条件；
   double occupancy 必须先通过 cap 升级或合同固定的 adaptive-K child policy；
   两个 observables 可以采用不同 certified methods，不能只因增大 R 就跳过资源与独立性
   复核。
5. 若 Majorana L1 或 locality tail 已超过 allocation，再决定是否执行 cluster Krylov。
6. TDVP、PEPS、当前 Majorana 参数扫描、QMC 和 effective-model 结果保留为独立诊断，
   不参与任何 machine-verified reference 或 READY 判定。

更一般的 bounded-error quantum simulation 已能把 learned Hamiltonian/Lindbladian 的
实验不确定度传播到 observable interval，但目前示范对象是 long-range Ising，不是匹配
的 Hubbard workload，见 [Kraft et al.](https://arxiv.org/abs/2511.23392)。这条路线可作为
未来 `stochastic_certified` schema 的参考，当前不能冒充 `exact_bounded`。
