# 二维 Fermi–Hubbard 同任务资源模型

状态日期：2026-07-12

模型状态：**证据约束的可复算规划脚手架；尚不是完成项序校验的 A/B benchmark，
也不是硬件性能预测。**

## 结论先行

第一优先级任务已经从跨论文比较渐近符号推进到一个共享 Hamiltonian、误差账本、
首步/稳态分离、route-specific shots 和逻辑到物理接口的可运行模型。当前可以严格说：

1. 对固定度二维 spinful Hubbard，native fermion 与 dynamic Jordan–Wigner
   （dynamic-JW）的逻辑 interaction count 都可保持 `O(NR)`；standard/ladder
   fermionic swap network（FSN）仍为 `O(N^(3/2)R)`。
2. 普通局域 qubit 网格上的 dynamic-JW 仍有 `O(sqrt(N)R)` CNOT 深度。
   Lattice surgery 只把它变成相对于 `N` 的常逻辑测量轮数；联合逻辑测量仍约需
   `d` 个 syndrome cycles，并占用 data、auxiliary、routing 和 factory patches。
3. 现有证据不能判定端到端赢家。Native 主源虽定义任意角原生门，但没有完整二维
   matching 之间的运动、任意角 hopping/onsite 集成实现时长与保真度、冷却/echo、
   回位和空间占用；dynamic-JW 主源没有首步
   额外资源、distance-`d` 完整布局、局域旋转综合、magic-state dependency schedule
   或逐层 active volume。模型因此输出 `UNRESOLVED`，而不是用组件数据补造总时间。
4. 对抗复核发现，论文的 `21N/4L` 排程和最初拟定的 native Strang 排程并非已证
   同项序。v2 已改成从 dynamic-JW Fig. 14 重建的共同**分组顺序目标**，但仍需
   两边完整电路导出来确认 individual-term order。当前数字是 planning subtotals，
   不能声称已在同一 `epsilon_alg` 下完成 A/B。

原问题“native fermion 在 dynamic encoding 与纠错之后是否仍有端到端优势”仍然
开放；这份交付的价值是把关闭问题所需的编译、微基准与布局数据变成明确接口。

## 1. 共同物理任务与仍未关闭的匹配条件

目标 Hamiltonian 是开放边界 `L x L`、spinful、最近邻 Fermi–Hubbard：

\[
H=-t\sum_{\langle i,j\rangle,\sigma}
(c^\dagger_{i\sigma}c_{j\sigma}+\mathrm{h.c.})
+U\sum_i n_{i\uparrow}n_{i\downarrow}.
\]

共同规模量为

\[
V=L^2,\qquad N=2L^2,\qquad E=2L(L-1),
\qquad G_{hop}=2E=4L(L-1).
\]

默认规划任务进一步固定：

| 量 | 默认值 | 状态 |
|---|---:|---|
| `L, V, N` | `8, 64, 128` | 已固定 |
| `t, U/t, tT` | `1, 8, 1` | 已固定为无量纲 quench 目标 |
| 粒子数 / filling | `64 / 1 particle per site` | 半填充 |
| 初态 | checkerboard Néel product state | `L=8` 时 spin-balanced；具体制备时间未给 |
| observables | staggered magnetization；double occupancy | 同一 occupation-basis setting |
| 产品公式 | second-order Suzuki–Trotter / Strang | 已固定 |
| 分组顺序目标 | `H1,H2,HU,H3,H4,H4,H3,HU,H2,H1` | 从 Fig. 14 重建；待跨编译器验证 |
| `R` | `100` | 共同规划输入；尚无收敛证书 |
| 误差账本 | `0.005 alg + 0.01 stat + 0.005 hw <= 0.02` | additive observable-error 规划值 |
| accepted shots | 每 measurement setting `10,000` | 尚无 variance/置信区间证书 |

共同 `R` 不自动等于共同 Trotter error。必须导出各路线的 individual-term order，
确认重排不改变所引用的计数，再对给定 observables 做同序收敛测试。配置中的
`R=100` 和 shots 目前只测试资源模型接口，不证明达到两个误差子预算。

## 2. 统一资源向量

| 路线 | classical preprocessing / memory | online 逻辑资源 | topology / depth | physical space-time | shots / postprocessing |
|---|---|---|---|---|---|
| Native | 规则 edge-color schedule 可线性生成；校准与 movement plan 未量化 | mode-resolved native macros | 四个 matchings；两 spin 同层是假设 | storage traps、atoms、transport tweezers、workspace、loss/leakage 均分列 | route-specific acceptance/mitigation/readout |
| Standard FSN | 网络可流式生成；编译 wall-clock 未测 | source `O(N^(3/2)R)`；有限尺寸只给 candidate fit | 1D NN line，`O(sqrt(N)R)` | 尚无 FT 翻译 | route-specific |
| Ladder FSN | 同上 | 约 standard 一半，仍为 `O(N^(3/2)R)` | spin-separated ladder/rungs | 连接资源与 standard 不同 | route-specific |
| Dynamic-JW grid | encoding-switch schedule 输出 `O(N)`/step；runtime 未测 | source leading `21NR` CNOT | `L x 2L` NN grid，leading `4LR` | bare-qubit gate/rotation/routing 参数化 | route-specific |
| Dynamic-JW lattice surgery | 另需 place/route、decoder、factory scheduling | ladder measurements + rotations/magic | logical depth 对 `N` 常数；cycles 随 `d` | data + aux + routing + factory；逐层 volume 未知 | decoder/前馈进 critical path；observable reduction 另计 |

一次性 classical preprocessing、每次 state preparation/readout-reset、每次 observable
post-processing、acceptance probability 和 mitigation multiplier 都按路线配置。
随机 post-selection 下的

\[
\left\lceil\frac{S_{accepted}\,M_{settings}\,m_{mit}}{p_{accept}}\right\rceil
\]

只是固定接受率下的**期望执行量级**，不是以指定置信度拿到足够 accepted samples 的
停止界，也没有包含并行 replicas。

## 3. 逻辑资源模型

### 3.1 Native：采用共同分组顺序目标的推导

把四个 hopping matchings 记为 `H1...H4`，共同目标单步为

\[
H_1,H_2,H_U,H_3,H_4,H_4,H_3,H_U,H_2,H_1.
\]

中央两个 `H4` 半角合为整角；相邻 Trotter steps 的边界 `H1` 半角再合为整角。
令 `g_k` 为第 `k` 个 matching 中两 spin 合计的 mode-resolved gates。模型把两类
较大颜色放在 `H1,H4`：

\[
g_1=g_4=2L\lfloor L/2\rfloor,
\qquad
g_2=g_3=2L\lfloor (L-1)/2\rfloor.
\]

于是

\[
C_{native}
=R(2G_{hop}-g_4+2V)-(R-1)g_1,
\]

\[
D_{native}=8R+1,qquad
D_{hop}=6R+1,qquad D_U=2R.
\]

Hopping depth 可进一步分为 `4R+2` 个半角层、`R-1` 个 full-angle `H1`
边界层和 `R` 个 full-angle `H4` 中央层。这些公式是本调查从 PNAS 原生门集、
图着色与共同分组目标推导的，**不是 PNAS/Nature 直接报告的资源表**。`H1/H4`
能否同时选择为较大颜色且完全保持 dynamic-JW 的 individual-term order，仍需电路
导出确认。

在 `hbar=1` 的 PNAS native-gate 参数约定下，默认 `tT=1,R=100,U/t=8` 对应
`|theta_hop,half|=0.01`、融合 hopping `|theta_hop,full|=0.02`，以及
`|phi_U,half|=0.04`；后续填写层时长必须针对这些目标角，而不是借用另一个固定
角度组件的时长。

### 3.2 Dynamic-JW 与 FSN：source leading、candidate fit、complete total

[Aigner et al. 2026 v1](https://arxiv.org/abs/2605.12600) 直接给 square-NN、
spinful 稳态二阶步的 leading 值：

\[
C_{dyn}^{source}=21N,
\qquad D_{dyn}^{source}=4\sqrt{N/2}=4L.
\]

Appendix I 把相邻 hopping、FSWAP、融合 FSWAP+hopping 各按两个 CNOT，且明确
忽略第一步无法向前融合的额外 circuit cost，但未给该首步的 count 或 depth。
因此 v2 同时设 `first_step_extra_cnot=null` 和
`first_step_extra_cnot_depth=null`：`R x steady` 只叫 subtotal，complete total 和
complete physical time 保持 `UNRESOLVED`。即使补齐首步字段，也只得到
`first_step_closed_*_estimate`；source-leading 或 figure-fit steady depth 仍不是精确
compiled depth，所以代码不会把它升级为 `complete`。

论文没有打印 standard/ladder FSN 的有限尺寸公式。与 Fig. 5 七个绘图点及
Fig. 15 排程一致的一组候选曲线为

\[
\begin{aligned}
C_{dyn}^{fit}&=42L^2-24L,\\
C_{FSN,std}^{fit}&=16L^3-2L(L-1),\\
C_{FSN,ladder}^{fit}&=8L^3-2L(L-1).
\end{aligned}
\]

这些不是唯一可由图像决定的论文公式，模型标为
`candidate_fit_to_figure_not_source_formula`，只在原图 `L=4...10` 范围输出数值；
域外自动 `UNRESOLVED`。对应重建点保存在
`fermi_hubbard_fig5_candidate_points.json`，单测覆盖全部七个 `L`，但这仍不是作者
的原始机器可读数据。

候选曲线解释 count crossover：`L=4` 时 dynamic/standard/ladder 为
`576/1000/488`；`L=5,N=50` 时为 `930/1960/960`，dynamic 首次同时低于两个
FSN 基线。Dynamic 的有限尺寸 depth 候选为 `4L+30`；standard/ladder 只保留
约 `16L/8L` 的 leading 图示斜率。论文直接支持的是所有三者 depth `O(L)` 及
`L>7` 后 dynamic 更低，不能把读图斜率称为精确深度定理。

拓扑也不同：standard FSN 只要求 1D NN line；ladder 使用 spin-separated rungs；
dynamic-JW 使用 `L x 2L` 二维 NN grid。

## 4. Lattice surgery 的物理翻译

Dynamic-JW Appendix C 证明的是**一条** Hadamard-transformed CNOT ladder：

\[
3\text{ logical-measurement rounds}
+4\text{ single-qubit-Clifford rounds}.
\]

基本 `C2D` 是

\[
C_{2D}=C_\uparrow^\dagger C_\leftarrow^\dagger
CZ C_\leftarrow C_\uparrow,
\]

即四个 ladder macros、一个 CZ layer 与 frame correction。未经优化的一般
boustrophedon switch 可含两个 `C2D`，所以必须同时计八个 ladders 和两个 CZ
layers；spinful switch 还含 column-SWAP。完整稳态二阶步有 forward/reverse 两次
switch。

单 ladder 的配置公式是

\[
C_{lad}=2c_{PP}(d)+c_Z(d)+4c_C(d)
+D_{ff}\left\lceil\tau_{react}/\tau_{cyc}\right\rceil.
\]

`c_PP(d)~d` 是常用 lattice-surgery 保护尺度，不是一个物理 cycle。将单-qubit
Cliffords 设为 frame-tracked 的零 cycle 也不代表空间免费：edge/Clifford frame
会改变后续可接触边界与 routing。

对论文的两个并行 `L x L` spin JW 子网，显式 `C_up` column-ladder 层若按
one-aux-per-CNOT 构造，需要

\[
A_{explicit}=2L(L-1)=N-2L
\]

个 auxiliary patches。它是**这一个构造层的占用估计**，不是所有实现的下界。
唯一不依赖该辅助构造的 data-patch floor 是 `N` 个逻辑 patches。完整 active
时空体积必须有逐层占用表：

\[
V_{active}=(2d^2-1)\sum_k S_kC_k.
\]

代码另报 `configured_peak_core_times_switch_cycles_product`，它只是“把配置的峰值
核心 footprint 静态保留整个 switch subtotal”的乘积，不是上式，也不称理论下界。

Magic supply 的

\[
\max(C_{algorithm},C_{factory\ throughput})
\]

只输出为 optimistic latency lower bound；它假设完全 overlap，未包含 factory
startup、buffer、injection、routing、消费依赖与 distillation failure，所以永远不
生成 `complete_circuit_us`。

## 5. 默认场景输出

### 5.1 逻辑 subtotal 与 complete 的区别

| 路线 | provenance | count subtotal | complete count | depth subtotal | complete depth |
|---|---|---:|---:|---:|---:|
| Native | 共同分组目标下的新推导 | 44,864 | 44,864 | 801 | 801 |
| Dynamic-JW | source leading steady state | 268,800 | `UNRESOLVED` | 3,200 | `UNRESOLVED` |
| Dynamic-JW | Fig. 5 candidate fit | 249,600 | `UNRESOLVED` | 6,200 | `UNRESOLVED` |
| Standard FSN | Fig. 5 candidate fit | 808,000 | `UNRESOLVED` | about 12,800 | `UNRESOLVED` |
| Ladder FSN | Fig. 5 candidate fit | 398,400 | `UNRESOLVED` | about 6,400 | `UNRESOLVED` |

Native macro gates 与 CNOT 不是同质 location，不能直接用数字相除。Dynamic 的
source leading 与 finite-size candidate fit 也不是两种实现，而是同一排程的两个
证据层级。

### 5.2 Native 物理时间和空间仍是接口

共同分组顺序下，`R=100` 的 inclusive-layer 时间写成

\[
\begin{aligned}
T_{native}={}&2\tau_{H1,half}+200\tau_{H2,half}
+200\tau_{H3,half}\\
&+99\tau_{H1,full}+100\tau_{H4,full}
+200\tau_{U,half}.
\end{aligned}
\]

同一颜色/角度标量会在多个 incoming-layout context 中复用，所以每个输入必须是
覆盖 matching reconfiguration、move/ramp、gate、cooling/echo 与回位策略的 padded
worst-case。该和式只输出为 configured upper-bound scenario，不叫 complete time；
精确值还需逐 occurrence transition table。模型同时给出 `N=128` storage-mode
capacity floor，并把实际 storage traps、64 atoms、transport tweezers 和 movement
workspace 分列。后面三类完整量主源未给，所以默认为 `null`。

PNAS 的约 `500 us` 是“数微米 move 达约 99.9–99.99% fidelity”的保守组件估计，
不是 integrated layer time；其 Li-6 无 echo 例的 `T2*~2 ms` 也只相当于约四个
500-us moves。默认配置不把这两个数代入完整 circuit。

### 5.3 Bare-qubit 时间被首步与 route-specific 参数阻断

CNOT-depth subtotal 的斜率是 `3200/6200/~12800/~6400` CNOT layers，分别对应
dynamic leading、dynamic fit、standard FSN、ladder FSN。但每条路线有独立的
`cnot_layer_us`、steady non-CNOT time 和 first-step extra non-CNOT time；首步 CNOT
depth 也必须另填。补齐它们只会输出 first-step-closed planning estimate；在导入
精确 compiled steady count/depth 与 route timing 之前，complete circuit/campaign
始终不输出。

### 5.4 Surface-code 场景量不是完整结果

默认 `d=21, tau_cycle=1 us, c_PP=21, c_Z=1, c_C=0, tau_react=10 us,
D_ff=1`，所以

\[
C_{lad}=2(21)+1+10=53\text{ cycles}.
\]

配置一个基本 `C2D` block 时，每 switch 的 optimistic partial subtotal 是

\[
4(53)+1(21)=233\text{ cycles},
\]

`R=100`、每步两次 switch 为 `46.6 ms`。若配置一般两-block 变换，模型同时增加
ladders 和 CZ layers：

\[
8(53)+2(21)=466\text{ cycles/switch},
\]

所以 switch-only subtotal 是 `93.2 ms`，不是 `89.0 ms`。这些值仍不含 spinful
SWAP、local rotations、magic dependency、prep/readout 或 active layout。

显式 column-ladder 层在 `L=8` 有 `A=112` auxiliaries；配置的 construction layer
为 `128+112=240` patches。`q_patch=2d^2-1=881` 时，占用估计是

\[
Q_{construction\ layer}=240\times881=211,440
\]

physical qubits，明确排除 routing/factories，也不使用 `>=`。把它静态乘默认
`46,600` cycles 得 `9.853104e9` physical-qubit-cycles；这只是配置乘积，不是
逐层 active volume。

### 5.5 Error 与 shots 的安全解释

若乐观地把 `epsilon_hw=0.005` 全部分给 counted subtotal，并作简单 union-bound
除法，默认分母给出 native `1.11e-7`、dynamic-leading `1.86e-8`、dynamic-fit
`2.00e-8`、standard `6.19e-9`、ladder `1.26e-8`。后三类分母还缺首步；所有分母
又混合不同角度/门型，并遗漏 move、loss、heating/leakage、相关 layer error、
SPAM 和 routing。它们只是“还需要多严”的乐观告警，不能与 average gate fidelity
直接等同，更不是预测成功率。

Route-specific acceptance/mitigation 默认全为 `null`，所以 `10,000 accepted shots`
不会被误写成 `10,000 raw runs`，也不能自动当作 `10,000` 个有效独立样本。真正
campaign 还要给每个 measurement group 的 effective-independent-shot 依据、per-shot
contribution range、mitigation concentration model、variance/置信界和必要时的高置信
post-selection stopping rule。

## 6. 主源锚点与禁止外推

| 主源 | 可直接使用 | 不能外推 |
|---|---|---|
| [PNAS 2023 native proposal](https://pmc.ncbi.nlm.nih.gov/articles/PMC10468619/) | 原生 tunneling/interaction 门、Merge/Shuttle 并行性；movement/Rydberg 组件规划锚点 | 完整二维 Hubbard time/fidelity/space；冷却/echo/回位 |
| [Nature 2026 fermionic gates](https://www.nature.com/articles/s41586-026-10356-3) | global x-dimer 装置；1.125-ms truth-table pulse、1.29-ms repeated-pulse fidelity 数据；最高 `99.75(6)%` fit | PNAS gate stack、二维四 matching、任意角 hopping、onsite density-phase |
| [Dynamic-JW v1](https://arxiv.org/abs/2605.12600) | `21N,4L` leading；Fig. 5 crossover；单 ladder 的 3 measurement +4 Clifford | 首步额外 cost、FSN 正文精确式、完整 distance-`d` layout/time |
| [Litinski 2019](https://quantum-journal.org/papers/q-2019-03-05-128/) / [Horsman et al. 2012](https://doi.org/10.1088/1367-2630/14/12/123011) | joint measurement / merge-split 的 `d`-cycle 保护与 tile/space-time 口径 | 任意硬件通用的 `1 us` cycle、零 routing 或免费 frame |
| [Google surface-code experiment](https://www.nature.com/articles/s41586-024-08449-y) | rotated patch `2d^2-1` 口径、设备特定 logical error/cycle 数据 | 直接移植成任意架构 `d=21` 的性能预测 |

Nature 的 `99.75(6)%` 是最多 20 pulses 的 repeated-pulse fit、双粒子 post-selection，
不是 randomized benchmarking；pair-exchange truth table 仅三个 dimers，未给 process
fidelity。Nature 的 `U_int` 也不是 PNAS 的纯 density-phase primitive。因此这些值
均未进入默认完整误差模型。

## 7. 项序契约与验证器

本阶段新增 [term_order_contract.json](term_order_contract.json) 和
[term_order_validator.py](term_order_validator.py)。路线导出采用最小 schema：
`route`、`L`、`R`、每步的 raw `events[].group`；如果提供 `events[].terms`，验证器
还会检查每个 matching / onsite term set。

验证器固定检查：

- raw Strang group order：`H1,H2,HU,H3,H4,H4,H3,HU,H2,H1`；
- 每步一个 `H4-H4` fusion；
- 相邻步之间一个 `H1-H1` fusion；
- raw/fused group-event 数和 raw/fused term-call 数；
- `L>=3`、步数、group order 和 individual term set 的 fail-closed 行为。

当前 native fixture 已通过 group-level 验证，但没有 individual term lists；dynamic-JW
和两种 FSN 仍没有机器可读导出，因此不会被验证器假定为已匹配。验证结果
`VALIDATED` 只表示“给定导出符合契约”，不表示硬件实现或跨编译器等价已经成立。

### 7.1 跨路线 individual-term 序列比较

新增 [term_order_cross_route.py](term_order_cross_route.py) 与
[term_order_cross_route_template.json](term_order_cross_route_template.json)。它调用
旧 validator 检查每条导出，再要求每个事件都带 `terms` 列表，生成原始
`group + term sequence` 的 SHA-256 指纹，并逐事件比较五条 required routes。状态为：

- `UNRESOLVED`：路线缺失、导出非法，或只有 group-level 而没有 individual terms；
- `MISMATCH`：所有路线都有 individual terms，但至少一处序列不同；
- `MATCHED`：所有路线的原始 group/term 序列完全相同。

比较器还要求每份导出内部的 `route` 与 manifest route key 完全一致；把同一导出
改挂到另一 route key 会返回 `UNRESOLVED`，不能充当另一条路线的独立证据。

当前 cross-route 模板仍返回 `UNRESOLVED`。测试中的同序导出只是合成 fixture，不能
替代 dynamic-JW/FSN 的真实编译器导出；因此研究结论仍是“共同顺序目标已定义，跨
编译器 individual-term equality 未验证”。

本轮直接复核 [dynamic-JW arXiv v1](https://arxiv.org/abs/2605.12600) 并将页码/图表
锚点记录在 [DYNAMIC_JW_SOURCE_EVIDENCE.md](DYNAMIC_JW_SOURCE_EVIDENCE.md)。Fig. 14
只给分组级叙述，Appendix I 还明确忽略首个 Trotter step 无法融合的额外 circuit cost；
主源没有 individual-term event list 或首步 exact count/depth/time。因此这些字段继续
由 validator 保持 `UNRESOLVED`，而不是从图形反推。

FSN 的主源边界另见 [FSN_SOURCE_EVIDENCE.md](FSN_SOURCE_EVIDENCE.md)：Kivlichan 的
通用 `N`-depth / `N²/2` 结果不能直接替换二维 NN Hubbard 的 standard/ladder 有限尺寸
计数；后者目前仍是 Fig. 5 域内 candidate fit。这样既保留了通用 FSN theorem 的
primary-source anchor，也不把不同 interaction graph 的资源口径混为一谈。

Native 主源也已分层记录在 [NATIVE_SOURCE_EVIDENCE.md](NATIVE_SOURCE_EVIDENCE.md)：
PNAS 是含 MERGE/SHUTTLE 与组件级工程估计的 proposal；2026 Nature 的 `99.75(6)%`
和 `1.125 ms` 是双阱局部 collisional primitive 的实验数据；arXiv:2604.13160 是
全局控制 universal processor proposal。它们共同提高了 native 路线的证据成熟度，
但都没有关闭本任务的 L=8 连续 matching movement、任意角集成时长、空间占用和
individual-term compiled export，因此 native 完整 route 仍保持 `UNRESOLVED`。

## 8. 双观测量 target-R / 误差收敛接口

本阶段还新增 [fermi_hubbard_convergence.py](fermi_hubbard_convergence.py) 和
[fermi_hubbard_convergence_template.json](fermi_hubbard_convergence_template.json)。
schema v2 把 `staggered_magnetization` 与 `double_occupancy` 的定义、物理取值范围、
误差预算，以及完整的 `R=[25,50,100,200,400,800]` 网格固定在 workload 中；目标
`R=100` 不能在看到数据后另选。每条路线必须提供完整网格，每个点都是同批次的
双观测量向量，并带 estimator-mean covariance、逐观测量系统误差界、测量/线路/
term-sequence provenance 以及与 workload 一致的身份指纹；每个 route/R 点的 circuit
fingerprint 必须全局唯一。`shared_shots` 点还必须给出 attempted/accepted shots、
effective-independent-shot 数、逐观测量 per-shot contribution range 以及 concentration/
mitigation status，并满足 `attempted >= accepted >= 2`、`0 < effective <= accepted`。
concentration evidence status 同时认证 concentration model、贡献范围和有效样本数的推导。

shared-shot 点的绑定置信半宽不是用户填写的 `z * SE`，而是从已验证的单次贡献范围
`[l_{r,o,k},u_{r,o,k}]`、该联合批次的有效独立样本数 `n^eff_{r,k}` 和声明的
family-wise error rate `alpha` 推导：

\[
h_{r,o,k}=(u_{r,o,k}-l_{r,o,k})
\sqrt{\frac{\log(2m/\alpha)}{2n^{eff}_{r,k}}}.
\]

这里 `m` 由预先声明的路线、两个观测量、所有网格点、相邻 refinement 和 reference
比较的总数机械计算。无 mitigation 时 contribution range 必须等于物理范围；bounded
weighted mitigation 必须给出包含所报告 estimate 的经验证有限范围，unbounded/
unvalidated mitigation 不能进入 binding READY。deterministic simulation 的 sampling
half-width 为零。covariance
必须有限、对称且半正定，其对角线导出的 standard error 与 normal half-width 只作诊断，
不能替代上述有限样本 Bonferroni--Hoeffding 门。相邻 refinement 的绑定检查为

\[
|\hat O_{R_2}-\hat O_{R_1}|
+h_{R_1}+h_{R_2}+s_{R_1}+s_{R_2}
\le \epsilon_{alg}
\]

其中 `s_R` 是声明的系统误差绝对界；这个三角不等式不要求不同 `R` 批次相互独立。
稳定窗内每个点还必须满足 `h_R <= epsilon_stat`，且两个观测量都至少通过两个连续
refinement interval。若存在 reference，验证器还会绑定 Hamiltonian、初态、目标演化、
observable definition 和独立性，并逐点检查 estimate-to-reference 界。

通过完整网格联合稳定检查但没有完整的有界独立 reference，或路线系统误差界仍是
`assumed` / `derived_unvalidated` 时，结果最多为 `SCREENED_FOR_TARGET_R`。只有两个
reference 都是 identity-matched `exact_bounded`、其不确定性证据和每个路线点的系统界
均为 binding maturity、shared-shot concentration 声明为经验证的 independent bounded
samples，且目标点位于所有 route × observable 稳定窗中，才输出 `READY_FOR_TARGET_R`。
缺数据、metadata/identity 不一致、协方差非法或统计预算超限均 fail closed 为
`INVALID_SCHEMA` 或 `UNRESOLVED`。

统一 manifest 会把整份 convergence workload 与独立 evidence contract 精确比较，
并再次核验目标 `R=100` 的完整双观测量向量及 route × observable 稳定矩阵；不能通过
在数据内同步改网格、预算或 analysis-plan 字符串来绕过外层策略。

当前模板没有填入任何路线测量值，因此运行结果应为 `UNRESOLVED`。这不是失败，
而是避免把 `R=100` 规划输入误写成已验证的算法误差。

### 8.1 Measurement campaign preflight

新增 [measurement_campaign_contract.json](measurement_campaign_contract.json)、
[measurement_campaign_template.json](measurement_campaign_template.json) 和
[measurement_campaign_validator.py](measurement_campaign_validator.py)，把“需要多少 shots”
从资源模型里的 `10,000` 占位改成由统一 evidence contract 机械推导的 preflight。
planner 从 route map 去重得到四条 convergence routes，并固定全网格
`4 routes x 6 R = 24` 个 joint-observable batches；surface physical route 不会被重复算成
第五条独立 convergence route。

最终计划包含 reference comparisons，因此 family size 是

\[
m=4\times2\times(6+5+6)=136.
\]

这里的 `136` 是保守的 declared-comparison multiplicity，不表示存在 136 个相互独立的
随机事件。基本随机对象仍是 24 个 route/R joint batches 上的 48 个 point intervals；
同一 interval 会被 point、adjacent 和 reference inequalities 复用。Union bound 不需要
这些事件独立，使用 136 只会更保守。

在 `alpha=0.05` 下，当前 `10,000` 个**有效独立** samples 的最佳情形 Hoeffding 半宽
已经是 `0.0414766`（staggered magnetization）和 `0.0207383`（double occupancy），
二者都超过 `0.01` point budget。更重要的是，point budget 本身不足以关闭 adjacent-
`R` gate：即使 estimate delta 和两侧 systematic bounds 全为零，也必须有
`2h <= 0.005`，即 `h <= 0.0025`。

| 规划口径 | M 每点最小 effective | D 每点最小 effective | shared batch 每点 | 24 点总 effective |
|---|---:|---:|---:|---:|
| 只满足 `h <= 0.01` | 172,031 | 43,008 | 172,031 | 4,128,744 |
| 零 residual pair floor，`h <= 0.0025` | 2,752,491 | 688,123 | 2,752,491 | 66,059,784 |
| 当前 residual-budgeted plan，`h <= 0.002` | 4,300,768 | 1,075,192 | 4,300,768 | 103,218,432 |

最后一行把每个 observable 的 adjacent budget 分成两侧 sampling half-width 各
`0.002`、两侧 systematic 各 `0.00025` 和 estimate-delta reserve `0.0005`；reference
budget 则分成 route half-width `0.002`、route/reference systematic 各 `0.00025` 和
estimate-reference reserve `0.0025`。这只是可行的 error allocation，不是实测
convergence 证据。

模板中每个 route/R 的 acceptance probability 与 effective-per-accepted fraction 仍为
`null`，因此 planner 正确输出
`EFFECTIVE_TARGETS_DERIVED_RAW_UNRESOLVED`：accepted/raw totals 均为 `null`。即使未来
填入 `p` 与 `eta`，`ceil(N_eff/eta/p)` 也只会标
`EXPECTED_EXECUTION_PLAN_ONLY`，不能冒充 high-confidence stopping cap。planner 永不
输出 `READY_FOR_TARGET_R`。其中 `eta` 必须是对两个联合观测量都成立的 conservative
effective-independent-shot fraction；若只是经验 ESS ratio，则仍只能作 diagnostic
assumption。`p` 同样需要固定 iid Bernoulli acceptance 模型，不能从同一批结果事后挑选。

### 8.2 Independent bounded-reference qualification

前沿复核没有找到直接匹配本任务 `8 x 8` OBC、`U/t=8,tT=1`、checkerboard Néel 和
双 observable 的公开有界参考值。固定 `N_up=N_down=32` 后，full-ED 子空间维数为
`C(64,32)^2 ≈ 3.36e36`，所以“再做一个 exact statevector”不是可执行方案。

详细方法边界与执行顺序见
[REFERENCE_CERTIFICATION_STRATEGY.md](REFERENCE_CERTIFICATION_STRATEGY.md)。当前首选是
把 Majorana/Pauli Heisenberg operator propagation 改造成 deterministic certificate：
每次 truncation 前先合并重复 strings，累加 dropped-coefficient `L1` bound，再加入目标
OBC term split 的严格 product-formula bound、solver error 和 directed-rounding error。
local-cluster locality + Krylov bound 是后备；普通 TDVP/MPS、PEPS、QMC 和当前 Majorana
参数扫描都只保留为 diagnostic。

新增 [reference_qualification_contract.json](reference_qualification_contract.json)、
[reference_qualification_template.json](reference_qualification_template.json) 和
[reference_qualification_validator.py](reference_qualification_validator.py)。双 observable
identity 必须全匹配；本地 artifact 必须是严格 JSON，SHA-256 通过并逐字段绑定 ledger 中的
value/bound、boundary/Hamiltonian convention、reference formula/term sequence、
implementation/environment/checker 和 theorem fingerprints。四项 deterministic error
decomposition 必须自洽，binding-looking record 还需 directed interval rounding、完整外部
route batch/circuit snapshot、method-specific claims 成立且不复用 route inputs。

这些条件只足以输出 `STRUCTURALLY_COMPLETE_UNVERIFIED`，不等于证书数值已核验：当前
validator 不执行固定 machine checker，也不加载 campaign contract 判断
`total_abs_bound <= 0.00025`，并始终给出 `ready_gate_eligible=false`。代码中刻意没有
`QUALIFIED_BOUNDED` 状态。Uncertified tensor network/Krylov/stochastic records 即使填写
binding-looking fields 也只能是 `DIAGNOSTIC_ONLY`；空模板为 `UNRESOLVED`。

这些 artifact 当前保持独立生命周期：campaign preflight 规划数据获取，reference ledger
检查外部证书结构，proof kernel 只重算固定 declared circuit 的 truncation 子证明；它们均
未接入 `fermi_hubbard_evidence.py` 的最终 outer READY gate。
在真实 certificate 与 route data 出现前先保持这一边界，避免用空计划或合成证书制造
新的自我认证回路。

#### 8.2.1 Source-pinned Pauli truncation proof kernel

现在已有第一个真正重算数值子证明的 kernel：
[operator_propagation_certificate_checker.py](operator_propagation_certificate_checker.py)。
固定合同同时 pin checker source SHA-256、两个非零非交换 Pauli rotations、raw initial
observable、computational-basis state、backprop 顺序和硬资源上限。对
`G_P(theta)=exp(-i theta P/2)`，checker 用纯 `Fraction` Taylor--Lagrange 区间包住
`sin(theta)`/`cos(theta)`，重算 Pauli phase、四角 interval multiplication、slice 内
merge-before-drop 和累计 dropped-`L1`。最终输出 retained expectation interval 及其
`± cumulative dropped-L1` 扩张。

这一正状态刻意命名为 `VERIFIED_CIRCUIT_TRUNCATION_SUBCERTIFICATE`，而不是 bounded
reference。它没有验证 declared gates 来自 Hubbard mapping，没有给出 product formula 到
ideal evolution 的 bound，也不判断 truncation error 是否小于 `0.00025`；L=8 与 READY
仍为 `NOT_ASSESSED/false`，CLI 固定返回非零。现有 reference validator 也不调用它。

[operator_propagation_l2_witness.py](operator_propagation_l2_witness.py) 进一步把完整
`L=2,R=2,T=1` raw Strang sequence 展开为 112 个 8-qubit JW Pauli rotations。独立 Pauli
statevector 与 direct-fermion path 分别给出
`M_s=0.781713978559467`、`D=0.0309252063024724`，差小于 `1e-12`。但是它们与 ideal
diagnostic 的差仍约 `0.12595/0.00586`，所以 mapping cross-check 不能冒充 ideal-time
certificate。当前纯 Python `Fraction` 稀疏传播在完整 112 gates 上出现快速 term 和大整数
增长，因此该旧字符串实现的正式状态为 `DEFERRED_RESOURCE_LIMIT`；只有一门 local
probe 已做完整有理区间 enclosure。后续 8.2.3 的 bitset/checkpoint checker 已关闭这个
特定实现 defer，但没有改变这里的 ideal-evolution 边界。

#### 8.2.2 Canonical JW mapping 与 bitset checkpoint 层

新增 [hubbard_jw_mapping_validator.py](hubbard_jw_mapping_validator.py) 后，L2 witness
的 112 个 declared nonidentity gates 不再只靠 statevector 一致性间接支持。固定合同
source-pin checker、L2 pilot、term-order contract、L2 witness 及其 proof-kernel dependency；
checker 独立生成 L=2/L=3 OBC、site-major/spin-minor 的四组 bonds、
`-1/2(XX+YY)` parity strings、未平移 onsite `2(I-Zup-Zdown+ZZ)` 和完整 R=2 raw events。
L3 中 H1/H2/H3/H4 各有六条 spin-resolved bonds，补上 L2 的 H2/H3 空分支。

每条 hopping bond 的八类 exact occupation witness 包含 prefix/suffix spectator；L2/L3
分别重算 64/192 个 CAR-versus-Pauli actions。每个 site 的四种局域占据另得到
`(0,0,0,8)`，共 16/36 个 onsite witnesses。Raw events 保留 identity rotations；供
circuit 使用的 nonidentity view 省略它们时，全局相位账本明确给出 L2 `exp(-i*8)`、
L3 `exp(-i*18)`。正路径运行 pinned L2 builder 并逐项比较全部 112 门。最高状态仍只是
`VERIFIED_CANONICAL_JW_MAPPING_SUBCERTIFICATE`；product-formula、exact evolution、L=8、
campaign budget 与 READY 均未评估，CLI 固定非零。

[pauli_bitset_backend.py](pauli_bitset_backend.py) 同时提供 q0-first `(x_mask,z_mask)`
Pauli keys、精确相位/辛对易、checker-compatible Fraction interval propagation 和
canonical checkpoint SHA-256。固定 checkpoint 样例 digest 为
`c69ecf852f053106f0feb89cd0c2e220903ef862974fd5821786605cec9929dd`。本机固定种子
16-qubit/100,000 对诊断微基准中，预编码 bitset 的 multiply/commute 约有 `3.5x/9.6x`
加速；这不是可移植性能保证。该模块自身的 certificate authority 是 `NONE`；后续
8.2.3 将其作为 source-pinned 算术依赖并完成 112 门证书，而不是提升 prototype 自身。
其中 `max_bytes` 是 serialization 输出上限，不是峰值内存上限；payload 构造仍由独立
term-count 与 rational-digit caps 有界。

#### 8.2.3 完整 L2 checkpointed bitset/Fraction 子证书

[operator_propagation_checkpointed_l2.py](operator_propagation_checkpointed_l2.py)
把上节的 prototype 纳入新的 source-pinned checker，而不是提升 prototype 自身的
authority。它从已经哈希的同一份源码字节执行 mapping、bitset、Fraction kernel 与 L2
witness 依赖，要求 mapping positive status，并把全部 112 个 nonidentity rotations 与
canonical L2 sequence 逐项绑定。两个 observables 都按 reverse-forward 顺序通过 20 个
raw group-event checkpoints；每个 slice 用五阶 Taylor 区间传播，再向外量化到分母
`2^32`，最后执行容量 65,536 的 deterministic top-L1 保留。

本次完整运行没有发生 truncation drop。Staggered magnetization 的 final/peak term count
均为 16,380，最终区间为
`[104895467/134217728,209888553/268435456]`；double occupancy 的 final/peak term
count 均为 16,381，最终区间为
`[8238201/268435456,33458587/1073741824]`。两者 cumulative dropped-`L1` 都是
`0/1`，20 个中间 checkpoint 与 final digest 均由 checker 重算，float statevector 只作
被区间包含的非证明诊断。最高状态
`VERIFIED_L2_MAPPED_CIRCUIT_TRUNCATION_SUBCERTIFICATE` 只闭合 declared R=2 mapped
circuit；product-formula-to-exact error、L8、reference budget 与 READY 仍未评估，CLI
固定非零。

#### 8.2.4 L2/L3/L8 Strang commutator-L1 子证书

[hubbard_strang_commutator_checker.py](hubbard_strang_commutator_checker.py) 按
[Schubert--Mendl Proposition 2, Eq. (13)](https://arxiv.org/html/2306.10603#S2.E13)
固定 `H1,H2,HU,H3,H4` 顺序和

\[
C=\sum_\gamma\left(
\|[K_\gamma,[K_\gamma,H_\gamma]]\|/12+
\|[H_\gamma,[K_\gamma,H_\gamma]]\|/24\right),\quad
K_\gamma=\sum_{j>\gamma}H_j.
\]

checker 独立生成 L2/L3/L8 OBC nonidentity Pauli groups，逐 group 验证内部 commuting，
绑定 raw S2 palindrome/term products 与 onsite common-phase ledger，并在每个 outer
`gamma`、每个 nested family 内精确 merge 后才取 coefficient `L1`；不同 theorem norms
之间不作抵消。L2 action oracle 覆盖全部 256 个 basis states，L3 使用固定 16 个 basis
states；L8 action oracle 因显式资源边界未运行。

L8 的两类 L1 总和为 22,752 和 11,104，故 `C=7076/3`。由 unitary telescoping，
`T=1,R=100` 的 unitary bound 为 `1769/7500`；对 `||O||<=1` 的通用 expectation
comparison 加 factor two 后为 `1769/3750≈0.4717333`，远大于 `1/4000` allocation。
同一通用界至少需要 `R=4344`。因此当前五组 generic-L1 路线在 R=100 明确不可用作
bounded reference，但这不是 observable-specific no-go；下一步应优先检查 locality/
observable tightening、plaquette grouping 或独立高阶 formula。最高状态
`VERIFIED_STRANG_COMMUTATOR_L1_SUBCERTIFICATE` 不组合 mapping/truncation，不认证
physical L8 workload、reference 或 READY，CLI 固定非零。

#### 8.2.5 L8 group-order 与 OBC plaquette coefficient-L1 screen

[hubbard_strang_grouping_screen.py](hubbard_strang_grouping_screen.py) 继续回答一个更窄的
问题：保持 Proposition 2 / Eq. (13) 与 fully merged Pauli coefficient-L1 norm 时，换
group order 或改成 plaquette grouping 能否在 R=100 接近预算？Checker source-pin 上节
三件套并要求其正状态，然后穷举原五组全部 120 个 permutations。最佳顺序之一为
`H1,H2,HU,H4,H3`，`C=7072/3`、generic observable bound `884/1875`、minimum R=4343；
相对 declared `C=7076/3` 只减少 `1/1769≈0.0565%`，低于预先固定的 1% materiality
threshold。

主源 plaquette decomposition 是 PBC 三组并假定同一 plaquette 的四条 hopping 同时实现。
为避免直接移植，checker 构造了精确 OBC cover：`P0/P1/B` 分别含 64/36/12 条 spatial
bonds，加 `HU` 后 Pauli term counts 为 `(256,144,48,192)`，与原 640-term Hamiltonian
完全相等。全部 24 个 orders 的最佳 `C=7232/3`，generic bound `904/1875`、minimum
R=4392，反而比 declared split 更差。`P0/P1` 内一个 plaquette 的边不全对易，因此这些
cluster exponentials 也不等于 benchmark individual-term circuit。

R=100 与 `1/4000` allocation 要求 `C<=5/4`；当前最优仍为 `7072/3`。最高状态仅
`VERIFIED_STRANG_GROUPING_COEFFICIENT_L1_SCREEN`，明确不导入论文 PBC decimal norm、
不认证 candidate circuit identity、observable/locality tightening、truncation、reference
或 READY。结果把后续实现方向收敛到 certified cluster spectral norm 或 observable-specific
locality cone，而不是继续枚举同类 coefficient-L1 grouping。

#### 8.2.6 Cluster 主源审计与 fixed generic-bound exact no-go

Cluster 路线已对照
[Schubert--Mendl 的局域 cluster 方法](https://arxiv.org/html/2306.10603#S4.SS3)与
[论文时期官方代码提交](https://github.com/qc-tum/fermi_hubbard_commutators/commit/859bef092675957ae126e9d3b09dc3c63b213859)
完成审计。官方实现对不超过 14 个 fermionic modes 的 compact Fock matrix 做 NumPy
binary64 SVD/eigensolve；它没有 directed rounding、residual enclosure 或 interval
certificate，且 14 只是实现阈值。因此其输出可作算法诊断，不能直接进入严格证书。

未版本化的完整 L8 诊断原型把 tail/self 两类和从 22,752/11,104 降到约
11,810.1186/8,634.8900，得到 `C≈1343.9636` 和 R=100 generic observable bound
`≈0.268793`。它使用 105 个 clusters，其中 94 个达到 14 modes，运行约 65.8 s、峰值约
69.5 MiB。虽然相对 Pauli-L1 改善约 43%，`C` 仍是 `5/4` 门槛的约 1,075 倍；这些
binary64 数字只记录为诊断，不写入 positive scope。

[hubbard_strang_generic_bound_no_go_checker.py](hubbard_strang_generic_bound_no_go_checker.py)
给出了无需认证 cluster 上界的更强路线判据。对固定五组顺序，取 Proposition 2 中的单个
正项

\[
A=[K_1,[K_1,H_1]],\qquad C\ge \|A\|/12,
\]

并把精确 3,072 项 operator 作用于归一化 checkerboard Néel basis vector
`q=0x66669999666699996666999966669999`。该向量及全部 416 个非零输出都位于
`N_up=N_down=32` sector，checker 精确得到

\[
\|A|q\rangle\|^2=295200=3600\cdot82,
\qquad C\ge5\sqrt{82}.
\]

因此仅这一项已有

\[
(\|A\|/12)^2\ge2050>25/16=(5/4)^2.
\]

即使把所有 cluster approximation 换成全局精确、并限制到物理 half-filled sector 的谱
范数，也不可能使这个 **固定五组、固定二阶、generic operator-norm theorem expression**
在 R=100 达标。对应 generic bound 的精确平方下界为 `41/500000`，相对 allocation
平方 `1/16000000` 的比值为 1,312；单凭该 witness，`R=602` 只是第一个未被排除的步数，
并非充分条件。

最高状态为 `VERIFIED_GENERIC_STRANG_BOUND_INFEASIBILITY_WITNESS`，CLI 按设计仍非零。
它没有给 actual product-formula error 下界，也没有排除 observable/locality-specific
cancellation、不同 grouping 或高阶 formula；不组合 truncation、physical reference 或
READY。由此停止继续建设这条 fixed-generic cluster upper-bound 证书，下一数学层转向两个
target observables 的 locality cone / Heisenberg propagation，或真正不同的公式。

#### 8.2.7 Fang--Qu observable Taylor 单步核与 R-step 路线判决

observable-specific Taylor 核采用 Fang--Qu，*Uniform Semiclassical Observable Error
Bound of Trotter--Suzuki Splitting: A Simple Algebraic Proof*，
[SIAM J. Numer. Anal. 64 (2026)，DOI 10.1137/25M1777098](https://doi.org/10.1137/25M1777098)，
[arXiv:2507.02783v2](https://arxiv.org/abs/2507.02783)。审计所用 v2 PDF SHA-256 为
`c1afaae4a944ba5c32bb5c86e421986bbcd89c14dae959d73560db979e668806`。这里专门使用
其 Eq. (3.9) 的逐 stage 积分 Taylor remainder；对整条径向 product 直接求四阶导会出现
interleaved exponentials，不能作为同一公式的证明。

合并相邻两个 `H4` 半步后，一步固定为

\[
(H_1,H_2,H_U,H_3,H_4,H_3,H_U,H_2,H_1),\qquad
(c_1,\ldots,c_9)=(1/2,1/2,1/2,1/2,1,1/2,1/2,1/2,1/2).
\]

formal degree 0--2 product-minus-ideal residual 均为零；degree-3 差记为 `D3(O)`。四阶
remainder 使用

\[
E_4(O)=\|\operatorname{ad}_H^4(O)\|/24,
\]

\[
P_4(O)=\sum_{q_1+\cdots+q_9=4}
\left(\prod_j\frac{c_j^{q_j}}{q_j!}\right)
\left\|\operatorname{ad}_{H_9}^{q_9}\cdots
\operatorname{ad}_{H_1}^{q_1}(O)\right\|.
\]

总计 `binom(12,8)=495` 个 weak compositions。每个 remainder 首次在总 degree 4 的
stage 产生，余下 stages 只作为 exact unitary isometries 包在外层；因此对 `delta>=0`
没有小步长前提，也没有 exponential prefactor。当前数值是 fully merged Pauli coefficient
`L1` 对 operator norm 的严格替代，不是 exact spectral norms。L8 结果为：

| observable | `D3` | `E4` | `P4` | `E4+P4` | `delta=1/100` 严格单步界 |
|---|---:|---:|---:|---:|---:|
| staggered magnetization | `1703/24` | `15275/12` | `25287/16` | `136961/48` | `159187/1600000000≈9.9491875e-5` |
| double occupancy | `423/16` | `16633/12` | `37211/24` | `70477/24` | `133927/2400000000≈5.5802917e-5` |

这些界只认证单步 defect 作用于初始 observable。R 步 Heisenberg telescoping 的正确输入
是 evolved observable：

\[
\|\mathcal P_\delta^R(O)-\mathcal E_\delta^R(O)\|
\le\sum_{k=0}^{R-1}
\|(\mathcal P_\delta-\mathcal E_\delta)(O_k)\|,
\qquad O_k=\mathcal E_\delta^k(O),
\]

或反向 telescoping 中的 PF-evolved `O_k`。外层 conjugation 的等距性不足以把 `O_k`
替换成初始 `O`，所以把表中单步界直接乘 100 不是 actual/global error bound。严格
uniform-sup 版本必须写成

\[
\sup_k\|D_3(O_k)\|/R^2+
\sup_k(E_4(O_k)+P_4(O_k))/R^3.
\]

由于两个 suprema 都包含 `k=0`，R=100 的 RHS floor 分别至少为
`159187/16000000` 与 `133927/24000000`，相对 `1/4000` allocation 是
`159187/4000=39.79675` 倍与 `133927/6000≈22.32117` 倍。因此当前
“逐步 triangle + uniform supremum + Pauli-L1”架构不能达标；这不是 actual-error
no-go，也不排除逐 `k` ledger、跨 step cancellation、sector/state-specific action 或更紧
norm。

[hubbard_strang_observable_taylor_step_checker.py](hubbard_strang_observable_taylor_step_checker.py)
已把上述 ledger 对 L2/L3/L8 和两个 observables 机器重算。最高状态仅
`VERIFIED_ONE_STEP_OBSERVABLE_TAYLOR_L1_SUBCERTIFICATE`，CLI 固定非零。它 source-pin
既有 Strang backend/contract/template，并在 warm cache 上重验；当前最小 artifact 尚无
自身 same-byte contract，论文 PDF SHA 也只是外部审计 metadata，不是运行时载入的本地
source。L8 exact Néel `D3` action 对 magnetization 给出
`135913/18432>(5/2)^2`，排除 uniform-leading norm shortcut；double occupancy 为
`79145/73728<(5/2)^2`，仍保留更紧 sector norm 的可能性。两者 `<q|D3|q>=0` 只收紧
初始单步 expectation，不能外推后续 steps。

短时 global-observable light-cone theorem 也不能直接救回该实例：二阶公式取
`chi=5,Upsilon=2,R=100` 时覆盖 `(chi-1)R Upsilon+3=803` 层，远超过 L8 OBC
格点直径 14，已经饱和。并且 theorem 以 qubit Pauli support 陈述；当前 JW 竖向 hopping
含长字符串，若把物理 fermion-site locality 代入，必须另证 even-CAR adaptation。下一步
改为构造逐 `k` evolved-observable/Majorana propagation ledger，直接包住每步 defect 或
global cancellation-aware 表达式，再决定是否还有 observable-specific 认证空间。

### 8.3 L=2 双观测量 screening pilot

新增 [fermi_hubbard_l2_pilot.py](fermi_hubbard_l2_pilot.py) 后，已经可以在无
NumPy/SciPy 的环境中运行一个纯 Python 算法 pilot：`L=2, U/t=8, tT=1`、checkerboard
Néel 初态，并同时测量 staggered magnetization 与 double occupancy。它用稀疏
Hamiltonian 作用和 scaled Taylor evolution 得到诊断参考值
`0.655760337805` 与 `0.0367897165024`，再对共同 raw group order 运行
`R=1,2,4,8,16,32,64,128`。

将结果写入 [fermi_hubbard_l2_pilot_manifest.json](fermi_hubbard_l2_pilot_manifest.json)
后，两个观测量分别从 `R=32` 与 `R=4` 进入声明网格上的稳定窗，因此共同筛选点为
`R=32`。但 scaled-Taylor reference 没有随 artifact 提供严格 truncation-error bound，
point 的数值系统界也标为 `derived_unvalidated`；评估结果因此是
`SCREENED_FOR_TARGET_R`，不是 exact-reference 或 bounded certificate。这仍是一个可复核
的算法链路检查，不是 `L=8` 证据、不是 dynamic-JW/FSN/native 的硬件结果，也不能证明
不同编译器已经产生相同 individual-term order；真实路线数据仍需替换
`group_order_pilot`。

### 8.4 首步与计时账本

为避免把稳态 subtotal 误写成完整电路，新增
[first_step_contract.json](first_step_contract.json)、
[first_step_ledger_template.json](first_step_ledger_template.json) 和
[first_step_ledger_validator.py](first_step_ledger_validator.py)。契约要求每条路线
分别提供 `R`、稳态每步 count/depth、首步额外 count/depth、`compiled_exact` 标记、
逻辑资源 provenance，以及 CNOT layer、稳态 non-CNOT、首步额外 non-CNOT 和 timing
provenance。验证器的状态含义是：

- `UNRESOLVED`：首步或计时字段缺失/非法；
- `BOOKKEEPING_CLOSED_ESTIMATE`：首步 count/depth/time 已闭账，但稳态值仍是
  source-leading 或 figure-fit 估计（因此不能生成 complete total）；
- `COMPLETE`：稳态与首步均来自精确 compiled export，且所有 route timing 字段齐全。

当前账本仍为空模板，五条 L=8 路线均为 `UNRESOLVED`；加入首步数据不会自动把
leading 或 candidate-fit 证据升级为精确 compiled 资源。

### 8.5 统一 evidence manifest

新增 [evidence_manifest_contract.json](evidence_manifest_contract.json)、
[evidence_manifest_template.json](evidence_manifest_template.json) 和
[fermi_hubbard_evidence.py](fermi_hubbard_evidence.py)。这个编排层把 term-order、
首步账本、native transition、surface place-route 和 target-R 收敛结果放入同一
manifest，并检查：

- 五条路线的 route map 是否一致；
- workload fingerprint、目标 `L=8` 与目标 `R=100` 是否一致；
- term export 的 `trotter_steps` 是否等于首步账本的 `R`；
- surface physical-route map 是否绑定现有的 term/convergence route pair；
- surface event 数和 sequence fingerprint 是否分别匹配 term sequence 长度和共同指纹；
- convergence workload 是否逐字段匹配独立 contract，两个观测量是否都覆盖目标点；
- 共享的 qubit-route 收敛结果是否达到 `READY_FOR_TARGET_R`，且目标 `R` 位于每个
  route × observable 稳定窗。

它只在五类组件分别满足 term-order `MATCHED`、首步 `COMPLETE`、native transition
`COMPLETE`、surface place-route `COMPLETE`、收敛 `READY_FOR_TARGET_R` 且没有身份或
一致性错误时输出 `READY_FOR_BENCHMARK`；`SCREENED_FOR_TARGET_R` 明确不足。当前统一
模板的五个组件均为 `UNRESOLVED`；测试中的闭合 manifest 是合成集成 fixture，不是
论文或硬件证据。

现在统一 manifest 还纳入 [native_transition_contract.json](native_transition_contract.json)、
[native_transition_template.json](native_transition_template.json) 和
[native_transition_validator.py](native_transition_validator.py)。它要求 `R=100` 的
`801=8R+1` 个 native layer occurrence 按 `H1/H2/H3/H4/HU` class 计数，记录每次
incoming/outgoing layout、move legs/distance、move/gate/cooling/return/other 时间、
loss/leakage 和 provenance。只有所有 occurrence 都是 measured 且
`compiled_exact=true` 才能给出 `complete_circuit_us`；否则最多是
`BOOKKEEPING_CLOSED_ESTIMATE`，空模板为 `UNRESOLVED`。

Surface 侧新增 [surface_place_route_contract.json](surface_place_route_contract.json)、
[surface_place_route_template.json](surface_place_route_template.json) 和
[surface_place_route_validator.py](surface_place_route_validator.py)。台账必须列出
`2L^2` 个全程 live 的 data patches；当前 rotated-patch 口径要求 odd `d` 且每 patch
为 `2d^2-1` physical qubits，并要求 factory/buffer patches 与 cycle/error budget 留在
固定 scenario contract 内。验证器还检查 layout tile conflict、participant/corridor
的 Manhattan 连通、live patch 不可跨 layout 无成本瞬移、连续 interval、operation
cycle window、共享 patch 的时间冲突、
相向 boundary、distill→buffer→inject→rotation 的前置链、每个 `10R` logical event 的
按 term order 唯一 ladder-operation binding、active physical-qubit-cycles，以及不超过
contract budget 的 logical-failure union bound。

只有 `compiled_exact=true`、`place_route_validated=true`，且 timing/error/operation
evidence 全部属于 `compiler_export` 或 `measured` 时，surface 状态才是 `COMPLETE`；
结构和算术虽闭合但仍含 derived/assumed 证据时只是
`BOOKKEEPING_CLOSED_ESTIMATE`。这个 validator 验证给定台账并要求外部
`place_route_validated=true`，不自行综合或证明一个 routing solution。

为了保留已知但未闭合的数字，新增
[evidence_manifest_source_snapshot.json](evidence_manifest_source_snapshot.json) 和
[SOURCE_SNAPSHOT_NOTES.md](SOURCE_SNAPSHOT_NOTES.md)。snapshot 写入 native 的
`44,864/801` 逻辑 bookkeeping，以及 dynamic leading、dynamic fit、standard FSN、
ladder FSN 的 steady count/depth；首步 timing、native occurrence table、individual
terms 和固定网格双观测量数据仍为缺失，surface row 也没有 patches/layouts/intervals。
因此运行统一 validator 仍为 `UNRESOLVED`，不会把 source subtotal 误升级为完整
benchmark。

## 9. 复算与测试

```bash
python3 docs/research/fermion-frontier/fermi_hubbard_resource_model.py \
  --config docs/research/fermion-frontier/fermi_hubbard_resource_scenario.json \
  --format markdown

python3 docs/research/fermion-frontier/test_fermi_hubbard_resource_model.py

python3 docs/research/fermion-frontier/term_order_validator.py \
  --contract docs/research/fermion-frontier/term_order_contract.json \
  --export docs/research/fermion-frontier/term_order_native_fixture.json \
  --format markdown

python3 docs/research/fermion-frontier/test_term_order_validator.py

python3 docs/research/fermion-frontier/term_order_cross_route.py \
  --contract docs/research/fermion-frontier/term_order_contract.json \
  --manifest docs/research/fermion-frontier/term_order_cross_route_template.json \
  --format markdown

python3 docs/research/fermion-frontier/test_term_order_cross_route.py

python3 docs/research/fermion-frontier/fermi_hubbard_convergence.py \
  --manifest docs/research/fermion-frontier/fermi_hubbard_convergence_template.json \
  --format markdown

python3 docs/research/fermion-frontier/test_fermi_hubbard_convergence.py

python3 docs/research/fermion-frontier/measurement_campaign_validator.py \
  --contract docs/research/fermion-frontier/measurement_campaign_contract.json \
  --plan docs/research/fermion-frontier/measurement_campaign_template.json \
  --evidence-contract docs/research/fermion-frontier/evidence_manifest_contract.json \
  --format markdown

python3 docs/research/fermion-frontier/test_measurement_campaign_validator.py

python3 docs/research/fermion-frontier/reference_qualification_validator.py \
  --contract docs/research/fermion-frontier/reference_qualification_contract.json \
  --ledger docs/research/fermion-frontier/reference_qualification_template.json \
  --artifact-root docs/research/fermion-frontier \
  --format markdown

python3 docs/research/fermion-frontier/test_reference_qualification_validator.py

# 成功的 subcertificate 仍按设计 exit 1
python3 docs/research/fermion-frontier/operator_propagation_certificate_checker.py \
  docs/research/fermion-frontier/operator_propagation_certificate_contract.json \
  docs/research/fermion-frontier/operator_propagation_certificate_template.json

python3 docs/research/fermion-frontier/test_operator_propagation_certificate_checker.py

python3 docs/research/fermion-frontier/operator_propagation_l2_witness.py \
  --format markdown

python3 docs/research/fermion-frontier/test_operator_propagation_l2_witness.py

# 成功的 mapping subcertificate 仍按设计 exit 1
python3 docs/research/fermion-frontier/hubbard_jw_mapping_validator.py \
  docs/research/fermion-frontier/hubbard_jw_mapping_contract.json \
  docs/research/fermion-frontier/hubbard_jw_mapping_template.json

python3 docs/research/fermion-frontier/test_hubbard_jw_mapping_validator.py

python3 docs/research/fermion-frontier/test_pauli_bitset_backend.py

# 成功的完整 L2 mapped-circuit subcertificate 仍按设计 exit 1
python3 docs/research/fermion-frontier/operator_propagation_checkpointed_l2.py \
  docs/research/fermion-frontier/operator_propagation_checkpointed_l2_contract.json \
  docs/research/fermion-frontier/operator_propagation_checkpointed_l2_template.json

python3 docs/research/fermion-frontier/test_operator_propagation_checkpointed_l2.py

# 成功的 Strang commutator-L1 subcertificate 仍按设计 exit 1
python3 docs/research/fermion-frontier/hubbard_strang_commutator_checker.py \
  docs/research/fermion-frontier/hubbard_strang_commutator_contract.json \
  docs/research/fermion-frontier/hubbard_strang_commutator_template.json

python3 docs/research/fermion-frontier/test_hubbard_strang_commutator_checker.py

# 成功的 grouping screen 仍按设计 exit 1
python3 docs/research/fermion-frontier/hubbard_strang_grouping_screen.py \
  docs/research/fermion-frontier/hubbard_strang_grouping_screen_contract.json \
  docs/research/fermion-frontier/hubbard_strang_grouping_screen_template.json

python3 docs/research/fermion-frontier/test_hubbard_strang_grouping_screen.py

# 成功的 fixed-generic-bound no-go witness 仍按设计 exit 1
python3 docs/research/fermion-frontier/hubbard_strang_generic_bound_no_go_checker.py \
  docs/research/fermion-frontier/hubbard_strang_generic_bound_no_go_contract.json \
  docs/research/fermion-frontier/hubbard_strang_generic_bound_no_go_template.json

python3 docs/research/fermion-frontier/test_hubbard_strang_generic_bound_no_go_checker.py

# 成功的 observable Taylor one-step subcertificate 仍按设计 exit 1
python3 docs/research/fermion-frontier/hubbard_strang_observable_taylor_step_checker.py

python3 docs/research/fermion-frontier/test_hubbard_strang_observable_taylor_step_checker.py

python3 docs/research/fermion-frontier/fermi_hubbard_l2_pilot.py \
  --format markdown

python3 docs/research/fermion-frontier/test_fermi_hubbard_l2_pilot.py

python3 docs/research/fermion-frontier/first_step_ledger_validator.py \
  --contract docs/research/fermion-frontier/first_step_contract.json \
  --ledger docs/research/fermion-frontier/first_step_ledger_template.json \
  --format markdown

python3 docs/research/fermion-frontier/test_first_step_ledger_validator.py

python3 docs/research/fermion-frontier/surface_place_route_validator.py \
  --contract docs/research/fermion-frontier/surface_place_route_contract.json \
  --ledger docs/research/fermion-frontier/surface_place_route_template.json \
  --format markdown

python3 docs/research/fermion-frontier/test_surface_place_route_validator.py

python3 docs/research/fermion-frontier/fermi_hubbard_evidence.py \
  --contract docs/research/fermion-frontier/evidence_manifest_contract.json \
  --manifest docs/research/fermion-frontier/evidence_manifest_template.json \
  --term-contract docs/research/fermion-frontier/term_order_contract.json \
  --first-step-contract docs/research/fermion-frontier/first_step_contract.json \
  --native-transition-contract docs/research/fermion-frontier/native_transition_contract.json \
  --surface-place-route-contract docs/research/fermion-frontier/surface_place_route_contract.json \
  --format markdown

python3 docs/research/fermion-frontier/test_fermi_hubbard_evidence.py

python3 docs/research/fermion-frontier/native_transition_validator.py \
  --contract docs/research/fermion-frontier/native_transition_contract.json \
  --ledger docs/research/fermion-frontier/native_transition_template.json \
  --format markdown

python3 docs/research/fermion-frontier/test_native_transition_validator.py
```

资源模型的十个回归测试覆盖 Fig. 5 的全部 `L=4...10` candidate points、域外阻断、
退化网格、共同分组 native schedule、两个 `C2D` 的第二 CZ layer、辅助 footprint、
零/无限 cycle、factory 配置、route-specific expected executions、首步对 complete time
的阻断和误差预算校验；项序验证器另有四个测试覆盖 group order、融合、term set 和
fail-closed 行为；收敛接口另有二十一个测试覆盖双观测量稳定、bounded/diagnostic
reference、有限样本 family-wise 半宽、协方差 PSD、路线证据复制、reference identity、
系统界/采样集中界 maturity、逐点 circuit 唯一性、完整网格和 provenance 的 fail-closed
行为。
Measurement campaign preflight 另有二十五个测试覆盖 canonical evidence hash、四路线/
六点轴、family-size 与 shot ceilings、10k 阻断、shared-batch max、residual allocation、
未知或非法 `p/eta`、range 放大、派生/实测字段注入、route/R 重标、bool/超大整数和 CLI
fail-closed 行为。Reference qualification 另有二十九个测试覆盖双 observable identity、
严格 JSON certificate path/SHA-256/record binding、arbitrary blob 与 content drift、error
decomposition、缺失/部分/复用的外部 route-input snapshot、directed rounding、
implementation/environment/checker fingerprints、五类 method claims，以及不存在可达
`QUALIFIED_BOUNDED` 状态。
Pauli propagation proof kernel 另有二十四个测试覆盖 Fraction rational encoding、严格
Taylor remainder、Pauli phase/commutation、非零多门顺序、四角 interval、merge/drop、
累计 `L1`、source/sequence/observable/state pins、byte/resource caps、失败 claim 清零和
CLI 非零边界。L=2 conformance witness 另有八个测试覆盖 112-gate raw sequence、Néel
identity、双 observable statevector 交叉检查、local Fraction enclosure、ideal-reference
分离和 full-certificate resource defer。
Canonical JW mapping validator 另有三十四个测试覆盖 L2/L3 OBC bonds、H2/H3 parity、
CAR/JW signs 与 external spectators、onsite 四占据、identity/global phase、112-gate
source binding、term/event hashes、strict JSON/type/resource caps、API/CLI failure scopes
和 overclaim 阻断。Bitset/checkpoint 原型另有三十五个测试覆盖 2-qubit Pauli product
穷举、3-qubit commutation 穷举、随机多比特/区间传播、canonical digest、重复/越界/
非 Fraction/反向区间/资源上限拒绝，以及 L2 八门前缀与字符串 checker 一致性。
完整 L2 checkpointed checker 另有五十一个测试覆盖 112 门/20 checkpoints 双 observable
重放、精确 interval 与 digest、zero-drop、mapping/source same-byte execution、量化与资源
上限、strict schema/types、pre-exec self pin、API/CLI 和失败 scope 清零。Strang
commutator checker 另有五十个测试覆盖公式常数、L2/L3/L8 groups、内部 commuting、raw
palindrome/term binding、common identity phase、exact nested-family L1、L2/L3 action
oracles、R scaling/generic factor two、allocation boundary、source same-byte execution、
strict schema/types、资源上限、pre-exec pin、失败清零和 CLI 非零边界。
Grouping screen 另有三十九个测试覆盖基础 checker source pins、120/24 permutations、
declared/best exact values、OBC 112-bond cover、plaquette/boundary term counts 与 commuting
structure、materiality/allocation decision、paper-scope boundary、strict JSON/types、
well-shaped tamper、pre-exec pin、失败 scope 清零和 CLI 非零边界。
Fixed generic-bound no-go checker 另有三十八个测试覆盖 exact selected operator、归一化
Néel witness、half-filled sector、416 项 action 与 amplitude histogram、平方 margin、
601/602 边界、source pins、strict schema/types、tamper、失败 scope 清零和 CLI 非零边界。
Observable Taylor step checker 另有三十二个测试覆盖 source pins、warm-cache drift、
hard pair preflight、9-stage composition、
双 observable identity、formal degree 0--2 cancellation、495 个 remainder paths、L2/L3/L8
exact Fractions、严格单步 operator/expectation bounds、uniform-sup floor、Néel action/
sector、资源上限、缓存、失败 scope 清零和 CLI 非零边界。
跨路线比较器另有六个测试覆盖空模板、group-only 阻断、同序指纹、序列错排、非法
导出和 route-key 重标记的 fail-closed 行为。
L=2 pilot 另有四个测试覆盖双观测量诊断 reference、R 网格、`R=32` screening 和规模限制。
首步账本另有六个测试覆盖空模板、bookkeeping-closed 状态、精确闭账、全路线闭账
门槛和非法 timing 的 fail-closed 行为。
统一 evidence manifest 另有十七个测试覆盖空 manifest、source snapshot、合成闭合、
双观测量目标-R 稳定矩阵、screening 阻断、convergence policy drift、term mismatch
优先级、surface closure/fingerprint/event cardinality、组件身份、R 不一致和 route-map
漂移的 fail-closed 行为。
native transition validator 另有六个测试覆盖空模板、measured 完成、derived 估计、
class count、timing decomposition 和 fingerprint fail-closed 行为。
surface place-route validator 另有二十七个测试覆盖 exact/derived 状态、active volume、
全 data-live、patch sizing、odd distance、failure budget、几何 corridor、interval gap/
overlap、operation window/资源冲突、event binding、dependency、非法 ID 和 evidence policy。
全套共 `466` 个测试。

## 10. 下一阶段的决定性工作

1. **跨编译器同序验证：**导出 native、dynamic-JW、standard/ladder FSN 的
   individual-term circuits；若共同顺序改变 `21N/4L` 或 candidate fits，重新计数。
2. **Campaign 参数闭合：**逐 route/R 测出或严格下界化 acceptance probability 与
   effective-per-accepted fraction；在 `measurement_campaign_template.json` 中固定
   mitigation contribution ranges。当前 `p/eta` 为 `null`，所以 `103,218,432`
   effective target 还不能换算为 raw executions；若需要固定 attempt cap，另加入
   family-wise high-confidence binomial stopping rule，不能把 expected count 代替它。
3. **独立有界 reference：**完整 L2 `R=2` checkpointed checker 已闭合 112 门 mapped
   circuit，且本次容量截断的 dropped-`L1` 为零；这消除了旧的纯字符串资源 defer。
   L8 五组 Strang generic commutator-L1 也已机检，但 R=100 的通用 observable bound
   `1769/3750` 远超 `0.00025`；全部 group orders 与精确 OBC plaquette+boundary
   coefficient-L1 screen 也没有实质改进。更强的 exact half-filled-sector witness 已证明，
   即使使用全局精确 cluster spectral norms，固定五组 generic theorem 在 R=100 仍至少超
   allocation 约 36.2 倍；因此不再建设该 fixed-generic cluster upper-bound 路线。
   Observable Taylor 单步核现已严格闭合，但正确 R-step telescoping 需要 evolved `O_k`；
   uniform-supremum Pauli-L1 shortcut 也已被 `k=0` floor 排除。下一步构造逐 `k`
   Majorana/Pauli evolved-observable ledger 或 cancellation-aware global defect，并检查真正
   不同的 grouping 与高阶 formula；同时把 L8 初态、两个 observables、
   occurrence-level sequence、truncation 和 product-formula bound 组合成同一 source-pinned
   chain。只有全链通过且 `total_abs_bound<=0.00025` 才能新增 reference 资格状态；当前
   subcertificates 与 `STRUCTURALLY_COMPLETE_UNVERIFIED` 都不能作为交付边界。
4. **真实双观测量网格：**按固定 `R=[25,50,100,200,400,800]` 对四条 unique
   convergence routes 生成联合 measurements、covariance、有效样本与可绑定 systematic
   evidence；严格区分 screening 与 `READY_FOR_TARGET_R`。
5. **Outer gate 接入：**真实 campaign/certificate artifact 与固定 checker 出现后，把
   execution-plan match、checker result 和 campaign-bound adequacy 接入
   `fermi_hubbard_evidence.py`。当前保持独立 validator，不把
   `STRUCTURALLY_COMPLETE_UNVERIFIED`、空模板或合成证书接入最终 READY。
6. **首步闭账：**使用 `first_step_contract.json` 分别报告三条 qubit 路线
   first-step 的 CNOT count、depth、non-CNOT time；在 `compiled_exact=true` 前，
   只输出 `BOOKKEEPING_CLOSED_ESTIMATE`，不把稳态平均代替完整总量。
7. **Native 微基准与空间：**连续执行四 matchings，测 inclusive transition time、
   move legs/distance、loss/leakage、cooling/echo、traps/tweezers/workspace 和回位。
8. **Surface place-and-route：**用真实 compiler export 与 measured timing/error 数据
   填充 `surface_place_route_template.json`：给出完整 spinful switch 的 C2D blocks、
   CZ/SWAP、boundary corridors、逐周期 active patches、decoder/前馈、rotation
   synthesis、factory startup/buffer/injection/failure 与 code-distance error allocation。
9. **同误差 A/B：**在 route-specific acceptance、mitigation、prep/readout 和共同
   observable error 下报告 latency、expected/high-confidence campaign、peak physical
   space 与 active physical-qubit-cycles。

完成这些接口后，模型才能从“证据边界与缺口清单”升级为可判定 native 与 qubit
架构端到端优势的 matched benchmark。
