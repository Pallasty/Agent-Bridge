## 独立验证者 A 报告

结论：25 条中，**22 PASS、2 REFUTE、1 UNVERIFIED**。但 22 条 PASS 中有 6 条需要收紧措辞后才能进入最终报告。

关键修正：

- ledger 29 的“四费米子”应改为“4 个费米模式”，并非固定粒子数为 4。
- ledger 31 的“每门成本恰好翻倍”仅指 FLO extent／指数因子，不是含多项式项的总运行时。
- ledger 32 的 \(O(4.5^k)\) 是相对旧算法的改进比，不是新算法本身的运行时。
- ledger 63 的 ML natural-gradient 连接未被该论文直接论证。
- ledger 65 忽略了玻色 Gaussian 态的位移 \(z\)，原句不成立。
- ledger 66 把完整 \(O(2N)\) Gaussian 变换群与通常由二次哈密顿量生成的 FLO 混为一谈；后者的恒等连通分支是 \(SO(2N)\)。

所有来源均已正式同行评审发表。`par.nsf.gov/10303113` 对应 Hackl–Bianchi 论文；其 2021 SciPost 期刊版和 2024 arXiv v4 都做了核对，判定以期刊正文为主。

---

### Quantum 8, 1350

来源：[Dias & König, Quantum 8, 1350 (2024)](https://quantum-journal.org/papers/q-2024-05-21-1350/)，DOI `10.22331/q-2024-05-21-1350`。**同行评审：是。**

| 来源内 index / ledger | 判定 | 证据与边界 |
|---|---|---|
| 0 / 25 | **PASS** | Sec. 1.5、Table 4 给出近似模拟 building blocks，运行时对 Gaussian extent \(\xi\) 线性、对模式数和误差参数多项式；弱模拟为 \(\widetilde O(\epsilon^{-2}\xi)\)，隐藏 \(n,T,L,\log\epsilon^{-1}\) 的多项式因子。边界：\(n\) 是费米模式数；必须已给出合适的 Gaussian 分解。Sec. 1.3 明说计算最优 extent／分解超出论文范围，因此不能把它解释成任意输入的无条件高效算法。 |
| 1 / 26 | **PASS** | Sec. 1.4 明确说明非 Gaussian 幺正可通过 Gaussian 操作加非 Gaussian resource state 的 gadget 实现，Sec. 4 将初态模拟算法用于该构造。边界：只覆盖存在相应 gadget、且资源态能有效分解的操作；代价仍由资源态 rank/extent 控制。 |
| 2 / 27 | **PASS，需改词** | 摘要及 Sec. 1.5 明说 Clifford + non-stabilizer 的算法可“immediately translate”到费米子设定。应把“形式上同构”改为“算法框架可直接迁移、资源量呈平行结构”；论文使用的是 analogous，不证明两种资源理论的全范畴同构。 |
| 3 / 28 | **PASS** | Sec. 3 构造带相位信息的 Gaussian 态经典描述，并给出 overlap、evolve、measurement 等子程序；Sec. 4.4 明确指出旧方法潜在缺少统一 phase reference，而新描述解决该问题。边界：高效追踪的是 Gaussian 态叠加中的相对相位，并不意味着能高效处理任意非 Gaussian 态。 |
| 4 / 29 | **PASS，需改术语** | Theorem 5.10 证明两个任意正宇称 4-mode 纯态的 Gaussian fidelity 乘性；Theorem 6.6 证明 fidelity 乘性推出 extent 乘性；Theorem 7.1 得到最终结论。应写成“4 个费米模式上的正宇称纯态”，不是“含四个粒子的态”。一般模式数和多因子情形不由该定理覆盖。 |

---

### Quantum 8, 1549

来源：[Reardon-Smith, Oszmaniec & Korzekwa, Quantum 8, 1549 (2024)](https://quantum-journal.org/papers/q-2024-12-04-1549/)，DOI `10.22331/q-2024-12-04-1549`。**同行评审：是。**

| 来源内 index / ledger | 判定 | 证据与边界 |
|---|---|---|
| 0 / 30 | **PASS** | Theorems 2–3 对任意 FLO 幺正与 \(k\) 个相邻 controlled-phase 门组成的电路给出加性误差 Born 概率估计。资源因子为 \(\xi^\*=\prod_j (|\cos(\theta_j/4)|+|\sin(\theta_j/4)|)^2\)，运行时对它线性，对 \(n,k,\epsilon^{-1},\log\delta^{-1}\) 等多项式。边界：这是加性误差概率估计；定理对计算基输入/测量和宇称有明确要求，不是通用精确采样定理。 |
| 1 / 31 | **PASS，必须收紧** | 对 CZ／最大资源相位 \(\theta=\pi\)，单个资源态 extent 为 2，所以每增加一门，**资源相关指数因子**乘 2，即 \(2^k\)。总运行时还含 \((n+k)^3\)、误差和目标概率相关项，不能说“完整总成本恰好翻倍”。 |
| 2 / 32 | **PASS，必须收紧** | 论文比较旧方法约 \(9^k\) 与新方法 \(2^k\)，因此相对改进比为 \((9/2)^k=4.5^k\)。应写“相对旧算法获得 \(O(4.5^k)\) 的改进因子”；新算法自身的资源指数项是 \(O(2^k)\)。 |
| 3 / 33 | **PASS** | Theorem 1 给出 controlled-phase resource state 的两个 Gaussian 态分解；Sec. 4 构造 phase-sensitive FLO statevector 模拟；Sec. 5 用 reverse gadget 将 controlled-phase 门转为资源态投影。论文明确把 statevector 分解而非 density-matrix 分解认定为性能改进来源。 |
| 4 / 34 | **PASS** | 期刊元数据逐项吻合：三位作者、2024-12-04、Quantum 卷 8 页 1549、DOI `10.22331/q-2024-12-04-1549`。 |

---

### arXiv 2009.11884 / SciPost Phys. 10, 066

来源：[Windt et al., SciPost Phys. 10, 066 (2021)](https://doi.org/10.21468/SciPostPhys.10.3.066)。**同行评审：是。**

| 来源内 index / ledger | 判定 | 证据与边界 |
|---|---|---|
| 0 / 35 | **PASS** | 摘要、Sec. IV 和 Discussion 明确提出在纯玻色/费米 Gaussian 态流形上极值化任意可微实函数的局部优化算法，并允许由子群生成的局部约束。边界：这是局部优化，不保证全局最优；需要可计算目标及其梯度，仅处理纯 Gaussian 态流形。 |
| 1 / 36 | **PASS，需注明宇称分支** | 论文给出 \(M_b=Sp(2N,\mathbb R)/U(N)\)、\(M_f=O(2N)/U(N)\)，并利用群作用保持正交切基来避免每步重算度量。固定宇称连通分支应写 \(SO(2N)\)，而不是无条件使用完整 \(O(2N)\)。 |
| 2 / 37 | **PASS** | Sec. III 系统给出 covariance matrix、linear complex structure、characteristic/quasiprobability functions、Gaussian unitaries、Bogoliubov transformations、纯/混态波函数间的转换公式。 |
| 3 / 38 | **PASS，需限定 Gaussian** | Sec. V 覆盖 Gaussian 变分基态近似、Gaussian EoP、Gaussian complexity of purification；正文也讨论 Gaussian circuit complexity。不能扩张为一般量子态上的精确基态、电路复杂度或 EoP 算法。 |
| 4 / 39 | **PASS** | Sec. VI 明确提出 Gaussian purification 足以计算任意 mixed Gaussian state EoP 的 conjecture，并给出小规模费米系统数值比较、解析上下界及局部最优性证明。它仍是猜想；论文明确承认有限非 Gaussian 变换可能降低目标值尚未排除。 |

---

### arXiv 2004.01015 / SciPost Phys. 9, 048

来源：[Hackl et al., SciPost Phys. 9, 048 (2020)](https://doi.org/10.21468/SciPostPhys.9.4.048)。**同行评审：是。**

| 来源内 index / ledger | 判定 | 证据与边界 |
|---|---|---|
| 0 / 60 | **PASS** | 摘要及 Secs. IV–V 明确统一处理实时演化、激发谱、谱函数和虚时演化；应用族包括玻色/费米 Gaussian states、群论相干态和 generalized Gaussian states。边界：研究的是封闭系统纯态的变分流形，不是泛指所有“变分量子算法”。 |
| 1 / 61 | **PASS** | 论文以 \(iT_\psi M=T_\psi M\)／\(J^2=-1\) 表征 Kähler 性，并指出传统等价的变分投影依赖该性质；其具体 generalized Gaussian 类是 manifestly non-Kähler。不能外推为所有广义 Gaussian ansatz 都必然 non-Kähler。 |
| 2 / 62 | **PASS** | Eq. (25) 给出两种投影：\(P_\psi(i\partial_t-H)|\psi\rangle=0\) 与 \(P_\psi(\partial_t+iH)|\psi\rangle=0\)。复切空间中只差 \(i\)，非 Kähler 实切空间中 \(i\) 不与投影交换，分别导向 Lagrangian 与 McLachlan 原理。应表述为“两种变分处方不再等价”，而不是基本薛定谔方程本身不唯一。 |
| 3 / 63 | **UNVERIFIED（复合主张）** | Eq. (164) 确实给出 \(dx^\mu/d\tau=-G^{\mu\nu}\partial_\nu E\)，Eq. (166) 证明 \(dE/d\tau\le0\)，正文称其为 Riemannian gradient descent。可是全文没有 ML、Fisher information、Amari 或 natural gradient；所以“与 ML natural gradient 相同且由该文直接支撑”不能通过。可保留物理/几何结论，并把 ML 连接标成后续数学解释。 |
| 4 / 64 | **PASS，需保留稳定性条件** | Eq. (16) 在近似基态线性化得到 \(K^\mu{}_\nu\)，谱成 \(\pm i\omega_\ell\)，振荡频率近似激发能。正文/脚注依赖该点是局部能量极小、Hessian 正定；还可能出现约束产生的零模或 spurious Goldstone mode。 |

---

### par.nsf 10303113 / SciPost Phys. Core 4, 025

来源映射：[Hackl & Bianchi, SciPost Phys. Core 4, 025 (2021)](https://doi.org/10.21468/SciPostPhysCore.4.3.025)，对应 [arXiv:2010.15518](https://arxiv.org/abs/2010.15518)。**同行评审：是。** 期刊版为 2021；arXiv v4 在 2024-11-30 修订。

| 来源内 index / ledger | 判定 | 证据与边界 |
|---|---|---|
| 0 / 65 | **REFUTE（原句过宽）** | \(J^2=-1\) 的纯态和 \(J^2\ne-1\) 的混态结构本身正确。但正文 Eq. (121) 明确说纯 Gaussian 态由 **位移 \(z\) 加 \(J\)** 唯一刻画；Sec. 3 也写“\(J\)（玻色情形还需 \(z\)）”。不同 coherent displacements 可共享同一个 \(J\)。修正版：零一阶矩/零位移的 Gaussian 态由 \(J\) 唯一刻画；一般玻色态需 \((J,z)\)，混态同理。 |
| 1 / 66 | **REFUTE（把两个群层级混合）** | 全 Gaussian 变换的相空间结构群确为 \(O(2N,\mathbb R)\)，玻色情形为 \(Sp(2N,\mathbb R)\)，且共同稳定子是 \(U(N)=\{M\in G\mid[M,J]=0\}\)。但论文 Fig. 2、Sec. 2.3.4 明确指出：由二次算符指数生成、与恒等元连通的费米分支只有 \(SO(2N)\)；\(\det M=-1\) 的 \(O^{-}\) 元素需线性 Majorana/Pin 表示并切换宇称。因此不能把通常的二次哈密顿量 FLO 直接等同于完整 \(O(2N)\)。 |
| 2 / 67 | **PASS** | Introduction 明确指向伴随论文：Gaussian states 是 Kähler 变分流形的主要范例；另一篇用这些流形寻找可微函数局部极值并综述参数化。该主张也已由上面的 `2004.01015` 和 `2009.11884` 独立核实。 |
| 3 / 68 | **PASS** | Introduction 和 Table I 明确区分：玻色情形 canonical \(\Omega\) 由 Poisson/CCR 决定、\(G\) 随态；费米情形 canonical \(G\) 由 CAR 决定、\(\Omega\) 随态。 |
| 4 / 69 | **PASS** | Introduction、Sec. 4.1.3 和 Conclusion 都明确说明：von Neumann entropy、部分复杂度等公式写成 \(J\) 后对玻色和费米取相同形式。边界：这是 Gaussian 态内部的统一表达，不意味着两类系统的 Hilbert 空间、动力学或全部信息量等价。 |

## 建议写回 ledger 的状态

- `PASS`: 25–39、60–62、64、67–69。
- `UNVERIFIED`: 63。
- `REFUTE / rewrite-required`: 65、66。
- 对 27、29、31、32、36、38 加强制 caveat，避免它们虽标 PASS 却在综合报告中被再次放大。

本次只读核验，未修改任何文件。
