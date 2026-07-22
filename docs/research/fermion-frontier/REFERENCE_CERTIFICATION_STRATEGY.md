# L=8 Fermi--Hubbard 有界参考策略

更新日期：2026-07-14。

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

double occupancy 的累计 dropped-L1 radius 已约为 `1.23770e-4`，占 `1/4000`
scalar truncation-error-radius allocation 的 49.5%；该 allocation 不含 coefficient-box
width 与 product-formula-to-exact-Hubbard error。step-2 local drop 又是 step 1 的
16.46 倍，因此不得直接执行 fixed-K step 3。

磁化量的相邻 `2 -> 3` transition 现已正证闭合。新 state v2 同时绑定 immediate-parent
checker/witness、previous transition 与 transition-policy SHA；boundary 3 仍为完整
65,536-term box。第三步 `d3=1479500890039114/2^64`，所以
`E3=1691496669588296/2^64 ~=9.16962e-5`，declared mapped interval 为
`[18329701971403435870,18333084964742654970]/2^64`。本步 peak/visits 为
92,964/83,365,144。固定 K 的 step-4 诊断得到 `E4=7166451866997599/2^64 ~=3.88494e-4`，
已超过 `1/4000` scalar truncation-error-radius allocation；它没有 sidecar、transition
或正证 authority。

double occupancy adaptive-K v1 在正式执行前单独提交，候选为
`65,536,73,728,...,131,072`，并用
`C(q)=E2+floor(q(B-E2)/(98*144))` 保留余下 checkpoint 的 truncation slack。前六个
checkpoint 选择 `[73728,81920,90112,98304,114688,122880]`；第七个 checkpoint 的
最大 K 仍需 drop 429,299,248,198 ticks，高于 177,868,057,779 ticks slack，故
fail closed 且不提交 child boundary。该 screen 的 ledger/failure SHA 分别为
`f1210e3bdd2d505195b93029fcd9ec3a05e29a5ee99ab854e910c7726d2ad9bb` 与
`8d8aff7ab17148df346857cb9d86b07c9a031cb3a1ffec5945b3183938f0e5cd`。
诊断 K=262,144 虽得到 `E3~=1.86259e-4`，但 peak/visits 为
446,188/337,691,387，违反 v1 的 262,144/200,000,000 caps；它只能指导 v2。
已提交算术内核上的 v2 design probe 进一步冻结 `K<=327,680` 的候选面：磁化量
step 4 先提交 28 个诊断 checkpoint，第 29 个需要 effective `K=333,983`；double
occupancy step 3 先提交 21 个，第 22 个需要 `K=350,604`。对应 peak/visits 为
397,526/48,646,721 与 501,254/37,271,764，故当前停止原因是候选 K ceiling，而非
拟议资源 envelope。两份 canonical transcript 明确为 `DIAGNOSTIC_ONLY`，没有 sidecar、
transition、child depth 或正证 authority，只能用于下一份独立 precommit。
现已分别预提交 magnetization step-4 与 double-occupancy step-3 的 v2 policy：候选数为
17/21、共同最大 `K=327,680`，live/digest/visits caps 为
786,432/786,432/536,870,912。policy 绑定 immediate parent、输入 boundary、v2 kernel 与
non-normative transcript，但刻意不含 formal failure checkpoint、selected-K history、
child hash/value、实测资源或 positive status；正式 screen 必须在该 precommit 之后独立重放。
该 policy-pinned formal dual screen 现已完成：magnetization 前 28 个 checkpoint 按
first-feasible 规则提交，第 29 个的 slack 为 284,729,064,009 ticks，而
`K=327,680` drop 为 415,018,229,551，最低有效 K 为 333,983；double occupancy
前 21 个提交，第 22 个 slack 为 229,230,395,634，最大 policy K drop 为
1,074,313,509,825，最低有效 K 为 350,604。两者均是 max-K infeasibility，不是
resource-cap failure；正式 checker 未解析 design records，并从预哈希字节执行
kernel/root/parent，外层再次复核全部 prefix、candidate、first-feasible 与 ledger SHA。
因此 M/D certified mapped depth 仍分别为 3/2，没有 boundary、transition 或 sidecar。
任何走势都不能线性外推到 R100；product-formula-to-exact-Hubbard 项仍须独立组合。

随后完成的 v3 extended-`K` design probe 仍不具有 certificate authority。它从一次
bounded 读取的自身字节 fresh-exec，并把已固定 v2 probe、kernel、root 与 immediate
parent 依赖从同一批已验哈希字节编译；旧 v2 文件不作任何修改。magnetization / double
occupancy 分别采用 21/25 个候选并延伸到 `K=393,216`，仅放宽 candidate/output ceiling，
其余 `786,432` live/digest 与 `536,870,912` visits caps 保持不变。结果分别在提交 32/23
个 checkpoint 后，于 checkpoint 33/24 需要最低有效 `K=405,291/397,750`；peak/visits
为 550,806/61,421,993 与 525,968/44,079,570。旧 v2 committed prefix 的 propagation、
first-feasible 选择、drop、retained digest 与 E recurrence 全部保持一致，故两次停止仍是
K ceiling，而非资源失败。该结果只排除完整 attempted step 使用 `K<=393,216`；下一轮
设计候选至少须包含 `409,600`，且仍必须在 formal replay 前另行预提交，不得原地放宽 v2
policy，也不增加当前 M/D depth 3/2。

再下一代 v4 higher-`K` design probe 将相同梯度扩为 25/29 个候选、最大
`K=458,752`，并保持 v3 的 `786,432` live/digest 与 `536,870,912` visits envelope。
其 provenance 明确绑定 v4 same-byte self、v3 parent probe、v2 implementation 及
kernel/root/immediate-parent 已验字节；输出另有 1 MiB cap 并原子落盘。magnetization
提交 35 个 checkpoint 后在 checkpoint 36 需要最低有效 `K=464,310`；double occupancy
提交 27 个后在 checkpoint 28 需要 `K=461,297`。两路 peak/visits 分别为
660,262/73,130,963 与 591,330/59,719,825，仍未触发资源帽。v3 committed prefix 与旧
failure 的 propagation/budget/candidate-prefix 全部保持一致，旧 failure 均由
`K=409,600` first-feasible 接管。因此 `K<=458,752` 仍不能完成 attempted step；下一标准
档 `475,136` 足以跨过这两个当前 failure，但尚未证明后续 checkpoint。v4 同样没有 policy、
formal witness、boundary、transition、sidecar 或 depth 增量，不能被提升为正式证书。

v5 kernel-edge design generation 再追加 `475,136/491,520/507,904`，使 M/D 候选数
达到 28/32，并保持所有非 K 的 v4 resource caps 不变。它把 direct
v5-over-canonical-v4 delta 与 configured-v4 effective override 分开绑定，同时固定有序
v5/v4/v3/v2 source layers。magnetization 在 checkpoint 36--38 选择
`475,136/475,136/491,520`，checkpoint 39 需要最低有效 `K=521,800`；double occupancy
在 checkpoint 28--31 选择 `475,136/475,136/507,904/507,904`，checkpoint 32 需要
`K=518,097`。两路 peak/visits 为 714,754/86,294,299 与
694,872/76,953,164，仍是 K ceiling 而非资源失败。下一标准档 `524,288` 同时覆盖当前
minimum K，但它正好等于 kernel retained-K 上界；D 已用满 32 个候选槽，下一设计代必须
删除或合并旧档，不能直接追加第 33 项。该结果没有 precommit policy、formal witness、
boundary、transition、sidecar 或 depth 增量，也没有证明 `K=524,288` 能完成后续 checkpoint。

v6 kernel-limit design generation 随后测试当前算术内核支持的最后一个 retained-K 档。
magnetization 直接追加 `524,288`，形成 29 项；double occupancy 删除 v5 新增且从未被选中的
`491,520`，再加入 `524,288`，故仍为 32 项，并完整保留 v2--v4 候选集及 v5 的全部实际选择。
same-byte wrapper 固定有序 v6/v5/v4/v3/v2 五层来源，同时把 direct v6 delta、configured-v5
effective override 及其内含的 configured-v4 effective override 分层绑定。M 在 checkpoint 39
选择 `524,288`，checkpoint 40 随即需要最低有效 `K=525,859`，超过内核上界 1,571；其
peak/visits 为 `714,754/91,034,065`。D 在未改变非 K caps 的精确回放中先以 `524,288`
跨过 checkpoint 32，但 checkpoint 33 在 ranking 前因 825,000 项展开超过 786,432
live/digest envelope 而终止。仅用于测量、不得提升为 policy 的 1,048,576-term 内核能力回放
进一步表明同一 checkpoint 还需 `K=553,717`，超过 retained-K 上界 29,429，visits 为
82,050,350。资源异常不被捕获或降级，因此只发布完整 M v6 transcript，不存在 D 半成品
transcript。当前内核的纯候选扩展路线至此耗尽；下一步必须显式选择 kernel retained-K/
live-digest 扩容、checkpoint 粒度重构或不同 propagation/proof 路线，再另行预提交。v6 仍
不产生 policy、formal witness、boundary、transition、sidecar、exact-Hubbard/READY 结论
或 M/D depth 3/2 增量。

在选择 kernel 扩容或不同 propagation 路线前，另行执行了一个独立
four-gate checkpoint-granularity screen。它不是 v7：screen 只 same-byte 执行
自身，v2 仅提供已验字节 helper，v6 仅提供 candidates/caps 配置，二者的
run entrypoint 均未调用，v6 也不是 same-byte parent。物理九 stage、1,152 gate
顺序不变，但每四门 ranking/commit 一次，故每 mapped step 为 288
checkpoints；预算分母同步加倍，所有对齐边界严格满足 `C4(2q)=C8(q)`。
额外 commit 会改变 retained-state 轨迹，因此不宣称与八门 v6 共享状态前缀。

M 在 q1--77 提交后，于 q78（物理 gates 308--311）需要 `K=529,897`，比
kernel retained-K 上界高 5,609；peak/visits 为 643,624/82,493,877。q78 正是旧
八门 q39 的后半，所以 peak 降低不等于 M 可达深度增加。D 在 q1--64
提交后，于 q65（gates 256--259）需要 `K=532,869`，超出上界 8,581；
peak/visits 为 645,011/75,412,433。相较八门路径在完整 gates 256--263
propagation 时触发 825,000-term live cap，四门路径先在半块处截断并转为
K-ceiling stop。这只是 checkpoint cadence 的敏感性对照，不是同一个 retained
state 前缀。D 中被 v6 删除的 `491,520` counterfactual 在 q58、q59 会先于
实际 `507,904` 被选择，说明八门前缀中的“未使用候选”不能直接视为
四门轨迹中的安全删除项。为隔离该变量，又做了一次不发布 transcript 的
32-slot 敏感性回放：恢复 `491,520`，删除在四门规范轨迹中仍未被选中的
`65,536`。新轨迹按预期在 q58--59 改选 `491,520`，但仍只提交 64 个
checkpoints，并在同一 q65/gates 256--259 失败；minimum K 反而升至
`536,203`（超出 11,915），peak/visits 为 645,044/75,255,249。由于该候选集不存在于
已固定的 v6 配置源中，数值结果只由 opt-in regression 重现，不伪装成来源正确的
canonical artifact。因此已能排除“单纯减半 checkpoint 间隔”和“仅补回该候选档”
这两个简单修复，但不把它外推为所有 cadence/ladder 协同设计的 no-go。
该显式 kernel capability 扩展现已完成。独立 wrapper 从已验 arithmetic-v2 字节隔离
编译，唯一资源变化是 `max_retained_K: 524,288 -> 540,672`；诊断配置只同步
candidate/output 两个 K ceiling，786,432 live/digest 及其余 caps 全部不变。M 在 v6
基线后追加 `540,672`，形成 30 档。D 为保持 32-slot 上界，删除旧四门 canonical
q1--65 中逐行均 infeasible 且从未 selected 的 `65,536`，再追加 `540,672`。screen
固定自身、four-gate private control-flow parent、v6 baseline、v2 arithmetic 和 capability
wrapper 五类来源角色；wrapper/screen SHA 分别为
`327837e4646cb79cb237611ab49e645b51a47a36a97006e94838d1f5fa05af60` 与
`81ac62fa093c48d57667cb56958ad58a8ed26e8ff81abd7c35365e01fb981d6f`。

M 在 q78 正确接过旧 `minK=529,897` failure，并在 q78--80 连续选择
`540,672`，最终 80/80 committed 到达预提交 horizon；三步 pre-count 为
643,624/624,312/587,900，总 peak/visits 为 643,624/87,032,691，canonical SHA 为
`d4a0f952a3d4a93bd78d370fae50c5c043e33caa4d1452e841987976e43354a5`。D 在 q65
以 `540,672` 接过旧 `minK=532,869` failure，但 q66（gates 260--263）再次无可行档：
pre-count/peak 为 679,285，minimum effective K 为 558,598，超出新 ceiling 17,926，
visits 为 77,762,021；canonical SHA 为
`5ced57f7f6fc8aef50a6536920243d00af083b0a113b09d19f239bc1266fd8a5`。因此 M 已到达
规划中的旧 q40 对齐比较面，而 D 暴露出新的 K-ceiling stop，并未触发 live/digest cap。
两条有限 horizon 都没有完成每步 288 checkpoints。

该 observable-split 单元现已完成。M 外层只把隔离的 K=540,672 parent horizon 从
q80 改为 q82，仍从 q1 完整 replay；旧 q80 canonical 只在结果产生后验证 prefix，绝不
提供 propagation state。q1--80 records/history 完整不变，q81（gates 320--323）
pre-count 597,254，minimum effective K 545,129，超过 ceiling 4,457，因此以
K-ceiling failure 结束。总 peak/visits 为 643,624/89,253,151，canonical SHA 为
`0486a8b19077de9e90f134c7b3c0d43fdf3504a4876d6e0b2c3d01b37b89cb52`。

D 使用 direct-v2 capability wrapper；唯一 kernel 变化是
`max_retained_K: 524,288 -> 573,440` 与 `max_candidate_count: 32 -> 33`，其余 caps
保持不变。公开 pinned loader 还会严格拒绝 `None` 或非 canonical 64-hex pin。wrapper/
manifest SHA 分别为
`811a16b6a47bca60281fb4afe8280783146e6f4ee28955dde7907b47fc65bb49` 与
`c2787b105553b80ee9a1e5e1d925d6cac2ab819b0cdfab305484bf89bbba32c5`；K=540,672
wrapper 仅作未编译、未执行的 route-lineage reference。D ladder 在原 32 档后追加
`573,440`。完整 replay 中 q1--65 的 common state/history 与前 32 行全部 exact；q66
也保持旧 propagation 和前 32 行，新增 index 32 的 drop 为 75,084,546,988 ticks、
dropped count 105,845，并 first-feasible commit。q67/q68 继续选择 573,440，drop 分别为
128,389,336,170/62,098,539,389 ticks，pre-count 为 688,548/630,616。最终到达对齐的
q68 horizon，68/68 committed；总 peak/visits 为 688,548/82,618,707，last E 为
`2288712409577855/2^64`，canonical SHA 为
`b1f072c84cc676151fe3cddbb8a0db445df946f299dbb81f41e34f765d30dfc8`。

下一判别器也已完成。M 使用独立 direct-v2 capability wrapper；相对 arithmetic-v2
唯一变化是 `max_retained_K: 524,288 -> 557,056`，candidate-count capacity 仍为 32，
K=540,672 wrapper 只作未执行的 route reference。wrapper/manifest SHA 分别为
`4c54b9a2451ad9ae76e4b4036705558cdc527f22b015fd67c035118ad2c8506f` 与
`cc60b39010c55fa3a95f7160e5ccb0a4985ab6926aa8076841d75e660a954868`。M 在原 30
档后追加 `557,056`；q1--80 common state/history 与前 30 行保持 exact，q81 也保持
旧 propagation 与前 30 行，新增 index 30 首次可行。q81--82 均选择 557,056，
pre-count 为 597,254/641,180，dropped count 为 40,198/84,124，最终 82/82 committed；
总 peak/visits 为 643,624/91,592,879，canonical SHA 为
`1d6cbcddac8a8c596746f24b8c8498f24874e86db5235532d7d269220043cdd4`。

D 不改变 candidate、policy 或 kernel capability；外层 screen 只把隔离 q68 parent 的
horizon 从 68 改为 70，并从 q1 完整 replay。旧 q68 canonical 仅在结果产生后验证
prefix，不提供 propagation state。q1--68 records/history 完整不变；q69（gates
272--275）pre-count 为 644,504，minimum effective K 为 579,098，超过 ceiling 5,658，
因此以 K-ceiling failure 结束。总 peak/visits 为 688,548/84,984,299，canonical SHA 为
`38fa337482dbd323d68f36b6debfdc6fff94d4cf8c42e68d6477b45dc02368d6`。两条新增账本
覆盖 `82x31 + 69x33 = 4,819` 个 candidate rows，仍未触发 live/digest cap。

该阶段现已完成。M 外层只把隔离 q82 parent 的 horizon 从 82 改为 84，并从 q1 完整
replay；旧 q82 canonical 只在结果产生后验证 q1--82 prefix，不提供 propagation state。
q1--82 records/history 完整不变；q83（gates 328--331）pre-count 为 652,016，minimum
effective K 为 565,994，超过 ceiling 8,938，因此以 K-ceiling failure 结束，q84 未尝试。
总 peak/visits 为 652,016/93,965,211，canonical SHA 为
`2f866d658570c9cf667088662a98288c14b41144c3ffacdefd862aaf8f185138`。

D 使用新的 direct-v2 capability wrapper；相对 arithmetic-v2 唯一变化是
`max_retained_K: 524,288 -> 589,824` 与 `max_candidate_count: 32 -> 34`，其余 caps 与
provider bindings 保持不变。wrapper/manifest SHA 分别为
`7758cc1bf0cd71545a7135c92848059dc69e5d934c79f1d8c60ea61019459254` 与
`36694fa3e72ad78fde91826c6a1ae81ae5a7f07e51db2d008769d97eabce5b1a`；K=573,440/C33
wrapper 及其 q70 screen 只作未编译、未执行的 route reference。D 在原 33 档后追加
`589,824`。q1--68 common state/history 与前 33 行保持 exact；q69 也保持旧 propagation
和前 33 行，新增 index 33 以 61,286,012,190 ticks drop first-feasible commit。q70
（gates 276--279）pre-count 为 718,805，minimum effective K 为 597,272，超过 ceiling
7,448，因此再次 fail-stop。总 peak/visits 为 718,805/87,505,002，last E 为
`2288773695590045/2^64`，canonical SHA 为
`65d6f5ba3e45b5b57b12d1b9e1daadb17064f8aece7dc914697191f822b3a8d7`。两条账本覆盖
`83x31 + 70x34 = 4,953` 个 candidate rows，均未触发 live/digest cap。

该 capability 扩展阶段现已完成。M 使用 retained-K-only direct-v2 wrapper；相对
arithmetic-v2 唯一变化是 `max_retained_K: 524,288 -> 573,440`，candidate capacity
保持 32，其余 caps/provider bindings 不变。wrapper/manifest SHA 分别为
`c644dfeaf2a0b27be40403715aec8711818ae11ff575b230339af745f0a56ff1` 与
`fb6d6c241ab7ee2f535aa2f1cdff38a5e8f47bab1035ba29249332ca2d4f3f39`；screen SHA 为
`1246023edea93e89db2ec0071c51c1cb15f60b8a928b934aad08cebb593240b2`。M 在 31 档后
append `573,440`。q1--82 common state/history 与前 31 行 exact；q83 保留旧 propagation
与前 31 行，新增 index 31 首次可行。q83 的 pre-count/cap/slack/drop/dropped 分别为
652,016 / 1,700,172,776,259,030 / 133,727,664,071 / 49,417,284,097 / 78,576，E 从
`1700039048594959/2^64` 增至 `1700088465879056/2^64`。q84（gates 332--335）则在
pre-count 694,130 处 32/32 infeasible，minimum effective K 为 586,381，K excess
12,941；最大档的 counterfactual drop excess 为 177,725,804,621 ticks。总 peak/visits
为 694,130/96,423,989，canonical SHA 为
`f379f6a72caba82c0f1aca599ef9872666cfed8b4ea72003194438ed01806f48`。

D 使用 direct-v2 K=606,208/C35 wrapper；相对 arithmetic-v2 唯一变化是
`max_retained_K: 524,288 -> 606,208` 与 `max_candidate_count: 32 -> 35`。wrapper/
manifest SHA 分别为
`34757028d695e2542cade50f4be5c214006dee6945e01afc2483e7338d6cb7dd` 与
`c55df50288334226a4d8ba37a257ca645d601967f8778f426a313773c1c73629`；screen SHA 为
`dffd720464566ef443909b5e7b01518ac82bf5defd68e72ce9de079422985068`。D 在 D34 后
append `606,208`。q1--69 common state/history 与前 34 行 exact；q70 继续保持旧
propagation 与前 34 行，新增 index 34 first-feasible。q70 的 pre-count/cap/slack/drop/
dropped 分别为 718,805 / 2,288,924,993,833,947 / 151,298,243,902 /
97,846,623,202 / 112,597，feasibility margin 为 53,451,620,700 ticks，E 从
`2288773695590045/2^64` 增至 `2288871542213247/2^64`，并到达 70/70 committed。
总 peak/visits 为 718,805/87,505,002，canonical SHA 为
`55e9d305c90b62dea918071cd6ae383668c2ffb2f7dc108f7d4abcbcb772aa36`。两份完整账本
覆盖 `84x32 + 70x35 = 5,138` 行；独立逐行复算、closed-schema 与 canonical 定向测试
均通过，未触发 live/digest cap；D 的 35 个 candidate index 均至少被选择一次。

该 split 阶段现已完成。M 使用 retained-K-only direct-v2 wrapper；相对 arithmetic-v2
唯一变化是 `max_retained_K: 524,288 -> 589,824`，candidate capacity 仍为 32。wrapper/
manifest SHA 分别为
`9eded142673fcb548d585d0071f5c550970c48c24d50c5ef1fc43b6257b1775d` 与
`6906e56af531063800742e95304682f9bcd123d0086806d59691e0b099772b1a`；screen SHA 为
`594f03e397c5887df335d05971297a1d00e06b1ea19140003e7842a5ca897fb0`。C32 ladder 删除
在旧 q1--84 全部 infeasible、never-selected 的 `65,536`，追加 `589,824`，candidate SHA
为 `94c062a2f562b7ce9e095ce9585ac4087b7bfef2af492b45762ca5d732ae9b80`。q1--83 的
selected K、propagation 与 committed state exact；旧 index 1--31 变为新 0--30，因此
candidate rows 只在按 configured-K 对齐并把 index 减一后 normalized-exact，明确不宣称
raw row-prefix identity。q83 仍以新 index 30 选择 K=573,440。

q84（gates 332--335）pre-count/cap/slack 为 694,130 /
1,700,277,307,664,702 / 188,841,785,646；新 index 31/K=589,824 丢弃 104,306 项、
drop 142,263,012,225 ticks，feasibility margin 46,578,773,421 ticks，E 从
`1700088465879056/2^64` 增至 `1700230728891281/2^64`，最终 84/84 committed。
总 peak/visits 为 694,130/96,423,989，canonical SHA 为
`cf93ebcccde4ff10adee2e600a13ef1c0f979e89fe151fca16d4eae79da2420f`；32 个 candidate
index 均至少 selected 一次。

D 不扩 capability；screen 只把 horizon 70 -> 72，并从 q1 通过 exact b483 private
control flow 重放。q70 screen/transcript 不编译、不执行、不提供 propagation/state，只在
结果产生后验证 q1--70 exact records/history/35 rows。screen SHA 为
`54601418ab5aa2b6c887d928ad6c87fa0cff558c0558d106961201d291cc33fe`。q71（gates
280--283）input/pre-count/cap/slack 为 606,208 / 761,190 /
2,289,007,495,823,880 / 135,953,610,633；最大 K=606,208 的 drop 为
187,038,988,049 ticks、dropped count 154,982，仍超 slack 51,085,377,416 ticks。
minimum effective K 为 614,584，K excess 8,376，因此 q71 fail-stop、q72 未尝试，E 保持
`2288871542213247/2^64`。总 peak/visits 为 761,190/90,141,781，canonical SHA 为
`f21288cf0c37dc86fedc9ac195f4efe390dcc913640caa7ca79f02e6297d20f8`。两份账本覆盖
`84x32 + 71x35 = 5,173` 行，均未触发 live/digest cap。

该下一 split 也已完成。M 保持 `K=589,824/C32`，只把 horizon 84 -> 86；q84
same-byte private parent 从 q1 replay，q84 canonical 仅在重放后载入。q1--84 records、
history 与每步 32 行均 exact。q85（gates 336--339）pre-count 为 673,356，prefix slack
为 151,110,179,092 ticks；最大 K 的 drop 为 184,958,529,526 ticks，因此 minimum
effective K 为 592,290，超出现有上限 2,466。q85 fail-stop、q86 未尝试，总 peak/visits
为 694,130/98,908,531。screen/canonical SHA 分别为
`002cc87d5d1a8f1908a837e8612e3a9d4a4c5ebbf68e41f841ba4a5a639ff878` 与
`c24a665d543323a0e7f28ac4023fe5ae3d54b39c4e2991cba3e70e9371d0053d`。

D 的 direct-v2 capability 把 retained K 606,208 -> 622,592、capacity 35 -> 36，并只在
index 35 append 标准 `K=622,592`。q1--70 common state/history 与旧 35 行 exact；q71
也保留旧 propagation/rows，追加档丢弃 138,598 项、drop 95,847,613,475 ticks，以
40,105,997,158 ticks margin 成功 commit 到 `2288967389826722/2^64`。q72 propagation
精确产生 799,279 项，比未变的 786,432 live-term policy cap 多 12,847；中止发生在
digest、ranking、candidate construction 与 commit 之前。screen 以独立 closed 40-key
resource-abort ledger 记录实际 traceback state，不伪造 q72 checkpoint record。总
peak/visits（含 q72 attempt）为 799,279/92,869,433；wrapper/screen/canonical SHA 分别为
`7ac6c87f3d789ad62540cbc96e81f0a092594b0524eec3f9b05e7ffec2124838`、
`2e22e1918fbc10cd696d700dbf05e8d99d0c333a1428e9473de6ebbc563488e1` 与
`e7ae9abb11a4cc116778c8c373ff1c93131db9c9d36ba886ff6ef2d7b53bd09f`。两份账本覆盖
`85x32 + 71x36 = 5,276` 行。

这两条 bounded route 也已完成。M wrapper 实现 direct-v2 `K=606,208/C33`：相对
arithmetic-v2 把 retained K 524,288 -> 606,208、capacity 32 -> 33；相对不执行的
M K589824/C32 route predecessor，阶段增量是 K 589,824 -> 606,208，并把
`K=606,208` append 为 index 32。q1--84 的 propagation、committed state、selected
history 和旧 32 行 exact；q85 保持旧
propagation/ranking/rows，新行丢弃 67,148 项、drop 28,686,183,592 ticks，以
122,423,995,500 ticks margin commit。q86（gates 340--343）产生 654,324 项，选择旧
index 31/`K=589,824`，丢弃 64,500 项、drop 213,158,347,226 ticks，margin 为
13,797,053,946 ticks。86/86 全部 commit，总 peak/visits 为 694,130/101,424,121；
wrapper/screen/canonical SHA 分别为
`447cb116c2ca977cb2711b08e64e5795728907b8c4033bd1eb38211bf63cf558`、
`86e5148a51cb70d2aab21d770ad2b21928caf6e2818786542b287be7c8d02d27` 与
`fc649a90aa42429d7d746f40bdc7dfe109f1dc6921b46beb8c3396cc3012e875`。

D 保持 `K=622,592/C36` 与 horizon 72，只把 live/digest policy caps 从 786,432
提高到 1,048,576；旧 resource-abort canonical 只作 post-replay evidence。q1--71
records/history exact；q72（gates 284--287）再次产生 799,279 项，这次完成 digest、
ranking 与全部 36 行求值。minimum effective K 为 642,206，超 ceiling 19,614；最大
候选的 drop 仍比 prefix slack 多 111,121,545,012 ticks。结果是 policy failure，
q72 resource abort/selection/commit 均为空，attempted/completed 为 72/71。总 peak/visits
为 799,279/92,869,433；screen/canonical SHA 分别为
`57a68b3086cd2ed2d484d0f835a190dc768b12bbb2b8d6a3c99c86f6ea6bda8d` 与
`4bdc16622a52a57ab6d43da04d77c6c67defdb36c2630a9d51178b65ac1e6ddd`。当前两份
账本覆盖 `86x33 + 72x36 = 5,430` 行。

该判别器也已完成。M 保持 `K=606,208/C33`，只把 horizon 86 -> 88；q86 same-byte
private parent 从 q1 fresh replay，q86 canonical 仅在结果产生后载入，q1--86 exact。
canonical 有 88 个 records、87 个 selected-history entries 与 2,904 行。q87（gates
344--347，batch SHA
`4b60608343a13e9927dd20cd4bb7314e67b1432465e27d186c117935402801e7`）
pre-count 645,618，选择 index 32/`K=606,208`，丢弃 39,410 项、drop
28,631,843,222 ticks，以 89,696,616,395 ticks margin commit 到
`1700501205265321/2^64`。q88（gates 348--351，batch SHA
`7f8c6a2dd155412a27369e1fa8402c37127c6eadf12e4fa59ba442d345e8eaf7`）
pre-count 689,242，minimum effective K=607,993，比 ceiling 多 1,785；最大候选行的
drop 是 218,739,972,624 ticks，比 slack 多 24,511,950,557 ticks。结果分支为
`Q87_SUCCESS_Q88_FAILURE`，无 resource abort，attempted/completed 为 88/87，总
peak/visits 为 694,130/106,375,865。screen/canonical SHA 分别为
`d158d00275e78b33d0246e86bf9bc7bcaf4eb4f7fa4cb9afce2298e97cb5308d` 与
`f7ca4a1defd38472366c1cfcd112736f34b73e612002cce98a52f79daa5cc1b0`，canonical
大小为 804,599 bytes。

D 的独立 direct-v2 `K=655,360/C37` wrapper/manifest SHA 分别为
`2acf8f8329376ab06ad4c079af633d23bcc6a32fa20af654e5c3dbbb32093d54` 与
`62c889baf0676150344f06ccf5d48132e121ade399c77dd1b85727f5002dd6e5`。它相对
K622592/C36 只 append `K=655,360` 并把 retained-K/candidate-count capability 提到
655,360/37；live/digest caps 保持 1,048,576。fresh q1--72 replay 得到 72/72 commits
与 2,664 行。q72 pre-count 为 799,279，选择 index 36/`K=655,360`，丢弃 143,919
项、drop 78,846,106,758 ticks，以 43,761,880,334 ticks margin commit 到
`2289046235933480/2^64`；总 peak/visits 为 799,279/92,869,433。screen/canonical
SHA 分别为
`1d3366d7c3fdc2a1e4a5c58198cc9be7e561af1f2ff8582e324ed5902c760183` 与
`0517461f8695b21b578190cdd9a5da884f301d43c2f80be8093fbfc20cc006ae`，canonical
大小为 751,550 bytes。`K=638,976` 的结论严格限于 fixed four-gate q72 predecessor
state/prefix：实测 threshold 642,206、shortfall 3,230；没有执行 candidate row，也不
声明 exact drop。两份当前账本合计覆盖 5,568 行。

上述后续判别路线现已完成。M 的独立 direct-v2 `K622592/C34` wrapper/manifest SHA
分别为
`f4e676da40535903301181cf482119e051066b90921793e34152403b3b74b976` 与
`3c2b66149d524cc63a4d04838b3eec47fb69677466fe1f208e226df92bf0dac3`。它相对
M33 只 append `K=622,592` 为 index 33，并只提高 candidate/output 与
retained-K/candidate-count ceilings；其余 caps 固定。q1--88 fresh replay 先于旧 q88
canonical 的 post-replay 载入。结果为 88/88 commits、88 个 records/history entries
和 2,992 行。q88 pre-count 689,242，选择 index 33/`K=622,592`，丢弃 66,650 项、
drop 33,833,242,742 ticks，commit 到 `1700535038508063/2^64`；ranking boundary 为
`3434232 > 3434132`，没有 failure 或 resource abort。records/history SHA 分别为
`8832c0fd7c61146f2aa3c5e9a3a827972c459a126c2d371b5a5c41bac700c804` 与
`58cd214e13f4c122f710aad62ac0e52ead1aed0fa7d8a7e2498ea6013c7f4726`；screen/canonical
SHA 分别为
`6867dda2d6bd34ab2eed6b31d02a587e16762263a493e9890d0caa40f23a58a4` 与
`0074b1eea5fa574378d5a9fae9e748e7145efaa0c96b622ddf50587a72a2551a`，canonical
大小为 821,781 bytes。

D 保持 `K=655,360/C37` 与所有 candidate/policy/kernel caps 不变，只把 horizon
72 -> 74。fresh q1 replay 后才载入 q72 canonical，得到 74/74 commits、74 个
records/history entries 和 2,738 行。q73 pre-count 794,529，index 36/`K=655,360`
丢弃 139,169 项、drop 100,499,996,927 ticks，commit 到
`2289146735930407/2^64`，ranking boundary 为 `3668234 > 3667375`。q74 pre-count
726,450，同一 index 丢弃 71,090 项、drop 44,071,221,987 ticks，commit 到
`2289190807152394/2^64`，ranking boundary 为 exact tie
`4009413 = 4009413`。terminal branch 为
`Q73_AND_Q74_SUCCESS_HORIZON_REACHED`，没有 failure 或 resource abort。
records/history SHA 分别为
`f765797dad4f6892524fc651a259786dff9c10187a6c634fc088fd3508c1e89f` 与
`d521cdf189b54254cf3ca3d0e9033b52c90ea6ec91dc571d95a605e520972ff8`；screen/canonical
SHA 分别为
`5e2e077a9cab2a2b83f9830d755bafb7cc6dfa1d1c8a1ffade840d09e5016376` 与
`4421f5973253968167b1c8bd77e024b18450325ea9581ed39dbe975ec8163ec9`，canonical
大小为 773,489 bytes。当前两份账本合计覆盖 5,730 行。

这两条 same-cap horizon 路线现已完成。冻结的 replay 前审计均为 P0=0、P1=0、
P2=0，随后两条 fresh replay 串行执行而非并发执行。M 保持 `K=622,592/C34`，只把
horizon 88 -> 90；exact q88 private parent 从 q1 replay，q88 canonical 仅在 replay
完成后作为 q1--88 exact evidence 载入。q89 pre-count 718,896，选择 index 33/
`K=622,592`，丢弃 96,304 项、drop 174,253,874,408 ticks，commit 到
`1700709292382471/2^64`；retained digest 为
`b7d1e16a3f344eb1353593fd66c379d36272c49d1ebfe5c5c2b3e6958ed98c19`。
q90 pre-count 741,376，minimum effective K=635,284，比 ceiling 多 12,692，因而
terminal branch 为 `Q89_SUCCESS_Q90_FAILURE`，不是 resource abort。账本含 90 个
records、89 个 history entries 与 3,060 行；records/history SHA 分别为
`8978329b712168dce39991af25f6903deaf69c45f236521bb0e08e74f3d8741f` 与
`c6755c7655d6b2ff37da7b1a8ac8c16cfc4295ef9ad0b687ddaa3dcd3c785d53`。89,527-byte
screen 与 842,060-byte canonical SHA 分别为
`f880e851bb16df5e659d7c0e6aa237d1836b17b4ad010d5676557ade2ba9140a` 与
`d30359d9dd38c8e3a1461a0c7048645e35f478fa66920711871b3dc1c44bbd49`；执行时间
13:05，maximum RSS 689,500 KiB。

D 保持 `K=655,360/C37` 与全部 caps 不变，只把 horizon 74 -> 76。exact q74 private
parent 保留 q72 raw parent，从 q1 replay 后才载入 q74 canonical。普通 source pin 上限
为 262,144 bytes；唯一较大的 `double_occupancy_boundary_002.b85` encoded boundary
单独使用 1,048,576-byte cap，其大小为 841,495 bytes、SHA 为
`f92d5eadc01e1d9ebef86328b9eed92d867a2dd79b8bb2ba0baa821fe3b037ab`。q75
pre-count 733,965，选择 index 36/`K=655,360`，丢弃 78,605 项、drop
127,874,290,338 ticks，commit 到 `2289318681442732/2^64`；retained digest 为
`1a0c6aae47e81c4473b43ca5c27f8580a8754c72f9332e761bbddc1b31722def`。
q76 pre-count 789,691，minimum effective K=665,836，比 ceiling 多 10,476，因而
terminal branch 为 `Q75_SUCCESS_Q76_FAILURE`，不是 resource abort。账本含 76 个
records、75 个 history entries 与 2,812 行；records/history SHA 分别为
`5ba16ae933ae9a17633a1c3c4d7edba28b2c115bef475480272fa2cf9df39274` 与
`b72e24b2dbe1d8eff88ff9ad1e1bc47cebeb59807168603cd86ff91c218c604a`。58,178-byte
screen 与 798,861-byte canonical SHA 分别为
`621f9c97b72c3582314d360b9b29b46a9cb40bf60298776adfc52849300bd14e` 与
`856ede1f5774795c25ca2c36eafa8ac0696402194c6bf4e17ea5e8874efc22e0`；执行时间
11:29，maximum RSS 715,972 KiB。

两份 canonical 都是完整 candidate-row failure：`resource_policy_abort=null`，没有
child-boundary commit 或 positive artifact。failure-local threshold 把下一离散 ladder
点限定为 M 的 `K=638,976/C35` 与 D 的 `K=671,744/C38`；两者均尚未执行，也不能
预承诺成功。旧 `K=607,993` 与 `K=638,976` 证据继续严格限于各自原始 fixed
predecessor state/prefix。认证深度保持 M3/D2，不产生 boundary、witness、READY 或
certificate authority；两份当前账本合计覆盖 5,872 行。

上述 diagnostic screens 自身不发布 authority-bearing policy artifact；任何下一
ladder、horizon 与 caps 仍必须在 replay 前独立 precommit。它们不发布 child
boundary/transition/sidecar，不组合 product-formula-to-exact-Hubbard error，也不增加
M/D certified depth 3/2 或 READY authority。

`M-Q90-FORMAL-S0` 已把其中仅 M q90 的 fixed-policy ceiling 结论收为回溯性正式复现。
result-unpinned policy/checker 先在 commit
`d3e58a62c1ca8c7c33512acfc3db141c329490fd` 冻结，SHA-256 分别为
`8084ab612c6d3cefb8f779d4dfe24450cb5c7d612d14b485feabb7044ae7cab5` 与
`7edfb6f4b811db6f97b8bd8dc9245793ee24c0613d908ded3dc7bb340c6f7bfe`。
随后 q1--q90 fresh replay 只 stage 13-file allowlist，旧 q90 transcript/test 均未读取或
进入执行闭包；仅在 replay 完成后才确认结果与旧 diagnostic canonical byte-for-byte
相同，SHA 为
`d30359d9dd38c8e3a1461a0c7048645e35f478fa66920711871b3dc1c44bbd49`。
正式分支为 `Q89_SUCCESS_Q90_FAILURE`，含 90/89 个 records/history、3,060 行、q90
的 34 个候选全不可行且无 resource abort；witness SHA 为
`26d4996bc8977f8e9cfa0a62817166cd5b122a1355bdb455e77b9cd87382deda`。
外部非规范资源回执为 13:35.69、maximum RSS 671,592 KiB。该 authority 只排除固定
M3 输入、four-gate q1--q90、`K<=622,592/C34` 策略；它不是 prospective discovery
或一般 no-go，认证深度仍为 M3，不产生 M4、child boundary/transition/sidecar、
exact-Hubbard reference 或 READY。

D q76、任何更大 K、不同 cadence/horizon/caps 或不同算法仍需新的独立
precommit/checker/same-byte replay。

`MAJORANA-P0-S0` 随后完成了平行实现托管路线的首个正式子证书。最终 result-unpinned
precommit 为 `c6050be2fcc0beb1454465aa77240f6b1f88c71b`；它固定 Julia 1.11.9、完整
Manifest、MajoranaPropagation 0.3.0 / `b7849cb4`、PauliPropagation 0.7.3 / `2a96e9a9`、
递归源码闭包、unsigned-mask composite 排序、`2^64` outward rational intervals、
merge-before-strict-threshold 与逐项 dropped-L1 账本。两个 fresh Git-object-staged、
read-only、network-isolated Julia 进程给出相同 transcript SHA
`ff7a6f420e9ddadcba32df575c6b9e653a1ef703b3299b5a95e3b51442f5344c`；独立 Python
oracle 逐字段复算后的 witness SHA 为
`b06a7a16bc6697b92e6d3fa05a33089a2437195d5d12133346b68438177d13f8`。

该 authority 只覆盖 4,096 个小 mask 代数对、17,856 个固定 primitive rotation cases
与单一 two-site composite fixture。它明确不覆盖 L8、1,152 gates/R=100、PF-to-exact
Hubbard error、physical reference、complex/vector/GPU/multithread path 或 READY；因此它
关闭的是 P0 custody/kernel conformance，而不是本节所需的最终 bounded reference。

`MAJORANA-P1-S0` 现已进一步关闭 L2/L3 的跨语言 action/cadence 前置条件。其
result-unpinned precommit 为
`0b3e766814442c1f4186335b50d19f78c043e527`，固定 2x2/3x3 square-OBC、全部
spin-resolved hopping/onsite generators、逐 site `Sz` 以及 staggered magnetization / double
occupancy，共 62 个 operator instances、11,538,944 个 operator-ket action columns。独立
Python exact-CAR 路线不导入 Julia 实现；Julia 路线调用 pinned upstream constructors 与
`overlapwithfock`。L2 的 1,179,648 个 bra-ket entries（含结构零）均由 upstream 实际调用；
L3 实际执行的是 11,534,336 个 term-derived support candidate actions，support 外零只由
Majorana flip algebra 推出，并未冒充逐项 dense 执行。

R=2、T=1 的固定 Strang occurrence matrix 含 180 composite、412 constituent、284
truncate boundaries。证书 wrapper 以 unsigned mask 排序真实调用 upstream
apply/merge/truncate，并用 zero-angle identity sentinel 与 callback 绑定每次 truncate；native
unsorted `Dict` order 明确为 `NOT_ASSESSED`。onsite identity phase 由 constructor identity
coefficient、physical multiplier 与 event duration 逐 occurrence 推导，L2/L3 分别为
`exp(-i*8)` / `exp(-i*18)`，但这只是 fixture convention check，不是 exact dynamics。

两个 fresh、Git-object-staged、read-only、network-isolated Julia replay 给出相同 transcript
SHA `8b0b1cc063adf5914c78cfbb2a88721c9623ec90a47dab087ea21c124c3badb7`；独立
oracle witness SHA 为
`12b01c0aa89d71107f9acc5e4866f0b2998a84783aa1e255c9f462ac2a13b7f5`，完整可重构
replay-package SHA 为
`e1161b9cb6c49144f56ea5fe4c1963beeb1a7974d18ea01c02a1f264ff37cff2`。最高状态仅为
`VERIFIED_MAJORANA_P1_L2_L3_HUBBARD_SPARSE_ACTION_AND_CADENCE_CONFORMANCE_SUBCERTIFICATE`；
它不覆盖 native unsorted execution、L3 support 外逐项执行、任意 lattice/circuit/formula、
L8 full propagation、PF-to-exact error、exact evolution、physical reference 或 READY。P0/P1/JW
专项联合回归为 113/113；frontier 全目录为 1,253 tests 全通过、26 expected skips。

`MAJORANA-P2-S0` 已把这一前置条件推进到固定 L8 首步的实际资源执行。lifecycle-safe
result-unpinned precommit `65d0fe7778322b2bb83aabf65e7c12e989d73671` 冻结 normalized
staggered magnetization、8x8 square OBC checkerboard Neel state、`U/t=8,T=1,R=100` 的
第一个 fused mapped Strang step，以及 `H1,H2,HU,H3,H4,H3,HU,H2,H1` 九阶段顺序。证书
runner 实际执行 512 composites、1,152 个 unsigned-`UInt256` 排序 constituents 和 768 个
真实 threshold boundaries；strict cutoff 为 binary64 中精确可表示的 `2^-34`。

两条 fresh Git-object-staged、read-only、network-unshared replay 均受 cgroup v2
`MemoryMax=4 GiB` / `RuntimeMaxSec=300s` 约束，并达到
`PREFIX_COMPLETED_UNDER_CAPS`。相同 transcript SHA 为
`cf18113b82fd0348d2ae271630e59a67a1e9d73b3e09010f612cf89dbe09d0f5`，独立
canonical witness SHA 为
`ca382cd7cd8dd01dfcf7ea540809b32f89a5c512ce71484e76ed7e409cb7ae03`。执行峰值
premerge/postmerge 为 44,222/43,848，最终保留 42,704 terms；cap scan、upstream
propagation、threshold scan 与 final evaluation 合计 40,259,148 charged visits，低于预先
冻结的 `2^26` 总 cap。

最高 authority 仅为
`VERIFIED_MAJORANA_P2_L8_STAGGERED_MAGNETIZATION_ONE_STEP_BOUNDED_PREFIX_RESOURCE_FEASIBILITY_SUBCERTIFICATE`。
Float64 dropped-absolute-sum 和 Neel expectation 只是诊断，不是 outward error bound；raw
1,280-constituent threshold path、double occupancy、其余 99 步、Python top-L1 路线等同性、
PF-to-exact、physical reference 与 READY 均未评估。下一子阶段应固定同一个 P2 prefix，
加入 outward coefficient enclosure 与可独立复算的 truncation-only error ledger；在它闭合前
不扩展到完整 R100。

`MAJORANA-P3-S0` 现已严格关闭上述同一 prefix 的 accuracy 子问题。result-unpinned
precommit `5c1d009165716e6b8a935cad57c556a7ba966bbf` 以最终 P2 result commit 为直接父节点；
外层 checker 托管 27 个 source files 加 precommit contract，而 Julia runner 只挂载 6 个
允许输入，不可见 P2/P3 result artifacts。两次 fresh replay 均在 cgroup v2 的 4 GiB/300 s
上限内运行，network/PID namespace 同时 unshare，`/proc`、`/dev` 为 private kernel mounts，
唯一 writable host-backed bind 是 `/scratch`。启动环境只额外挂载 policy 冻结的 18 个
read-only regular files（ELF loader、5 个 glibc ABI、12 个 C.UTF-8 locale files），其
pre/post manifest 完全一致。两个 2,530,705-byte stdout 的 SHA 均为
`f102a1aab1bfc4f05b38d98df6371cf1aee2c3087a9960ba1b2c346b6c6dba43`；独立 Python
integer-RNE/Fraction oracle 复算后的 witness SHA 为
`6b4354b7f26db198427a74cfc7eac08c1895fda8d397918a9733fe7e32e8d7f5`。

P3 对 schedule 中精确有理角使用 order-7 Taylor point 加 next-term remainder，再在
`2^-128` grid 上 outward quantize；每个 actual binary64 product、merge collision 和 strict
threshold drop 都以 exact dyadic 解释并逐行向上取整。账本含 489,740 个 anticommuting
actions、979,480 个 product events、118,208 个 merge events、328,956 个 drop events；三类
ticks 分别为

`115422645562996270045296`,
`90064161277934613561344`,
`296986546186107059275602367348736`。

因此 authoritative total 为
`296986546391593866116533250955376/2^128`
`=18561659149474616632283328184711/21267647932558653966460912964485513216`
（小数诊断约 `8.72765018884e-7`）。exact cross multiplication 给出
`total_ticks * 400000 < 2^128`，即只使用 one-prefix `1/400000` allocation 的约 34.91%。
这不是把 Taylor widening 再重复相加；每个 local upper 已吸收自身 outward widening，后续
exact unitary conjugation 通过 operator-norm invariance 不放大已有误差。

最终 42,704-term actual state 在独立 checkerboard-Neel Fock oracle 上的 authoritative exact
dyadic center 为
`604040239256614101433905/604462909807314587353088`。center grid enclosure 加减上述 total
得到

`[21252757972972667064323158507908464249/21267647932558653966460912964485513216,`
` 21252795096290966013556423074564833671/21267647932558653966460912964485513216]`,

约为 `[0.999299877465, 0.999301622995]`。Float64 reduction `3feffa45912362b7` 仅为诊断；
exact dyadic center 与声明区间才有 authority。P3 还逐项重现 P2 transition/boundary/stage、
final term 与 Neel diagnostic digests，因此 P2 只作为 post-replay conformance evidence，
没有成为 Julia 的 accuracy 输入。

P3 precommit/result 测试 49/49 通过，JW 与 Majorana P0/P1/P2/P3 focused closure
205/205 通过，全部 `fermion-frontier` discovery 共 1,345 项通过，26 项按环境
条件跳过。物化后 result 也由冻结 checker 经完整 package reconstruction 与
independent oracle 重新验证。

最高状态为
`VERIFIED_MAJORANA_P3_L8_STAGGERED_MAGNETIZATION_ONE_FUSED_STEP_LOCAL_DEFECT_AND_TRUNCATION_OPERATOR_AND_NEEL_EXPECTATION_BOUND_SUBCERTIFICATE`。
它认证的是同一 fused product-formula 的**第一步 exact-untruncated prefix operator**及该 Neel
expectation enclosure；不认证 global coefficientwise interval state、exact-arithmetic 与
executed drop-set 等同性、raw 1,280 path、double occupancy、其余 99 步、PF-to-exact Hubbard
error、physical reference 或 READY。特别地，`8.72765e-7 * 100` 只能是设计启发，不能作为
R100 证书。

P4 S0v2 已执行上述 adjacent-step child。新的 result-unpinned precommit 为
`c6c2614186a8315775fa477e025195741c36d582`；较早的 signed-zero v1 replay 严格
fail closed，没有生成 authority。S0v2 在同一 fresh process 中从初态重跑 step 1 再执行
step 2；fresh step 1 只作 fieldwise conformance，telescoping 账本只继承一次 P3 upper，
不重复 charge、requantize 或 outward widen parent error。

在 `2^-128` grid 上，step-2 product、merge、drop 三项 local upper 分别为

`148110706480666299015145`,
`145718728421478199062528`,
`4432692192952477384756578989637632` ticks。

因此 step-2 local total 为 `4432692193246306819658723487715305` ticks，诊断小数约
`1.3026511580e-5`，是冻结 `1/400000` allocation 的 `5.2106` 倍；其中 drop upper 占
`99.9999999934%`。继承 P3 parent 一次后的 two-step cumulative total 为
`4729678739637900685775256738670681` ticks，诊断小数约 `1.3899276599e-5`，是冻结
`1/200000` cumulative allocation 的 `2.7799` 倍。最终 actual thresholded state 保留
72,808 terms，其 exact checkerboard-Neel center 为
`301388136752758141215773/302231454903657293676544`。

terminal branch 为 `TWO_STEP_CUMULATIVE_BOUND_EXCEEDS_ALLOCATION`，最高状态为
`VERIFIED_MAJORANA_P4_L8_TWO_STEP_CUMULATIVE_ERROR_BOUND_EXCEEDS_ALLOCATION_SUBCERTIFICATE`。
这是对固定 binary64 `2^-34` threshold 加 additive L1 drop accounting 的 bounded no-go，
不是 actual simulation error 的 no-go；它也不认证其余 98 mapped steps、PF-to-exact Hubbard
error、double occupancy、physical reference 或 READY。

下一阶段不直接推进第三步，而应另发 result-unpinned threshold-hardening child：优先在正式
replay 前预提交 `2^-36`/`2^-37` design probe，或把 fixed-amplitude threshold 改为
budget-constrained drop rule，并重新冻结 term/event/time/memory caps 与失败分支。只有该路线
恢复 allocation slack 后，才重新评估 checkpoint ladder；PF-to-exact Hubbard error 和双占据
observable 仍各自需要独立 proof budget/传播路线。

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
   首个和第二个 interval boundary、step-2 child，以及磁化量 boundary 3/step-3 child
   已闭合；double occupancy adaptive-K v1 已以 checkpoint-7 不可行为正 screen 结果，
   其 certified depth 仍为 2。
2. 固定五组 generic bound、uniform-supremum Pauli-L1 shortcut，以及 double occupancy
   用 fixed greedy14 cluster-exact-norm triangle 作为 uniform supremum 的架构都已被 exact
   witness 严格排除；逐 `k` cluster triangle ledger 仍开放。直接 evolved-observable
   propagation 对两个 observable 共同完成两步，magnetization 另完成第三步；不再逐
   `k` 重算 495 paths；cross-cluster/global
   cancellation-aware 方法仍作为平行数学路线。
3. Majorana P0 已在 `main@b7849cb`、Julia 1.11.9 与 PauliPropagation v0.7.3 上闭合
   runtime/source custody、deterministic composite sort、deduplicate-before-threshold、
   per-boundary dropped-L1 ledger 与 directed rational intervals；P1 又闭合了固定 L2/L3
   全 occupation candidate-action、L2 dense entries、local/global observables 与 sorted-wrapper
   cadence matrix；P2 已在 cgroup v2 hard caps 下完成固定 L8 staggered-magnetization 首个
   fused mapped step；P3 又以 exact-rational trig enclosure、integer binary64 RNE 和完整
   product/merge/drop ledger 关闭同一 prefix 的 operator/Neel outward bound，并严格通过
   `1/400000` 单步 allocation；P4 S0v2 已从初态 fresh 重跑并组合第二步 telescoping error，
   其固定 `2^-34` threshold + additive L1 drop upper 以
   `TWO_STEP_CUMULATIVE_BOUND_EXCEEDS_ALLOCATION` 闭合。下一步必须另行预提交
   threshold-hardening child，比较 `2^-36`/`2^-37` 或 budget-constrained drop，而不是直接
   推进第三步；不得从 P4 推导其余 R98、PF-to-exact Hubbard reference 或 READY。现有 Python
   one-step checker 与 double occupancy 路线的 authority 均不被覆盖。
4. 以 machine-checked `total_abs_bound` 达到 campaign reference allocation 为停止条件；
   当前 fixed-K 磁化量 step 4 与 double occupancy step 3 都必须另发资源/sidecar v2；
   v2 至少需审计 K=262,144、single-expansion 446,188 与 visits 337,691,387 这一诊断点，
   且必须在正式运行前重新提交候选、prefix budget 与 hard caps；
   两个 observables 可以采用不同 certified methods，不能只因增大 R 就跳过资源与独立性
   复核。
5. 若 Majorana L1 或 locality tail 已超过 allocation，再决定是否执行 cluster Krylov。
6. TDVP、PEPS、当前 Majorana 参数扫描、QMC 和 effective-model 结果保留为独立诊断，
   不参与任何 machine-verified reference 或 READY 判定。

## 独立参考路线 S0 选择门（2026-07-21）

`FH-L8-INDEPENDENT-REFERENCE-S0` 已把 PF-to-exact 方向从泛化调研收敛为机器可检的
路线选择。它重算既有 exact-Fraction 账本的 R100 uniform-sup floor，确认磁化量与双占据
分别超过 `1/4000` allocation 的 `159187/4000` 与 `133927/6000` 倍；同时确认普通
803-layer support cone 已超过 L8 OBC 直径 14。两条固定架构因此关闭，但都不是 actual
Trotter error no-go。

两个 observable 的 checkerboard-Néel `k0` degree-three expectation 均严格为零，因此唯一
保留的下一路线是 `PER_STEP_STATE_SPECIFIC_EXACT_DEFECT_LEDGER`。下一单元
`FH-L8-INDEPENDENT-REFERENCE-D1` 只认证 `k0 -> k1` rotated-integrand defect enclosure，
保留 sector 与 cancellation；在它给出正 enclosure 或 failure-local threshold 前，不授权
D2、full R100、physical reference 或 READY。

更一般的 bounded-error quantum simulation 已能把 learned Hamiltonian/Lindbladian 的
实验不确定度传播到 observable interval，但目前示范对象是 long-range Ising，不是匹配
的 Hubbard workload，见 [Kraft et al.](https://arxiv.org/abs/2511.23392)。这条路线可作为
未来 `stochastic_certified` schema 的参考，当前不能冒充 `exact_bounded`。
