## 对抗验证 B 结果

总体判定：**22 PASS / 3 REFUTE / 0 UNVERIFIED**。需要降级的是全局索引 **27、63、65**；其余可进入证据表，但若干项必须保留边界条件。

审计对象为 `gap345_claims.min.json` 全局索引 25–39、60–69；文件 SHA-256 为 `ab11ba7a7648c6e2f5d37254d4500a8c405633280c443e4d83e9b2afd673fa81`。仅使用论文正文和期刊元数据，未编辑任何文件。

### Quantum 8, 1350

主源：[Classical simulation of non-Gaussian fermionic circuits](https://quantum-journal.org/papers/q-2024-05-21-1350/)

- **idx 25 — PASS，置信度 0.94。** 摘要及 §1.5、Tables 3–4 确实给出精确和近似模拟：代价对模式数、误差参数以及 Gaussian rank/extent 为多项式，近似算法对 extent 线性。重要隐藏条件是：达到该 extent 的高斯分解必须作为输入给出；论文明确说计算 extent 或寻找最优分解超出范围。extent 本身也可能随系统规模指数增长。因此只能表述为“资源参数化算法”，不能说任意非高斯态都可端到端高效模拟。

- **idx 26 — PASS，置信度 0.95。** 摘要和 §1.2、§1.4 明确利用 gadget 把非高斯操作转成非高斯资源初态，从而扩展模拟。边界是必须存在相应 gadget，且仍受纯态、宇称、数占据测量等模型假设约束；不是任意黑盒非高斯门自动可折算。

- **idx 27 — REFUTE（部分），置信度 0.94。** 原文只称 Clifford+非稳定子问题与 FLO+非高斯问题“analogous”，并说明若已有所需字典操作、overlap 和相位追踪子程序，某些算法可迁移。论文没有证明两套资源理论“形式同构”。“非类比外推”更与原文措辞相反。建议改为：**“两者有可操作的算法对应；稳定子模拟中的若干分解与稀疏化技术可迁入费米子设定，但未建立资源理论同构。”**

- **idx 28 — PASS，置信度 0.98。** §3 明确指出协方差矩阵不保留全局相位，而高斯态叠加需要相对相位；扩展描述 \((\Gamma,x,r)\) 及 Theorem 3.2 可在 \(O(n^3)\) 内计算带相位的 overlap 和演化。这里的“修补”准确，但不能反向说普通协方差形式连单个高斯态可观测量也无法处理。

- **idx 29 — PASS，置信度 0.98。** §1.5、Eq. (9) 及 §§5–7 证明：一般字典中 fidelity 乘性在相应条件下推出 extent 乘性；本文具体证明两个任意四模式、正宇称纯态的乘积。论文也明确把更一般情形列为开放问题。

### Quantum 8, 1549

主源：[Improved simulation of quantum circuits dominated by free fermionic operations](https://quantum-journal.org/papers/q-2024-12-04-1549/)

- **idx 30 — PASS，置信度 0.95。** Theorems 2–3 给出 FLO 与相邻 controlled-phase 电路的加性误差 Born 概率估计算法；运行时间对普通参数为多项式，对 \(\xi^\*\) 线性。必须保留：偶宇称计算基输入/输出、加性误差、相邻 controlled-phase，以及这不是高效的乘性误差算法或通用实用采样器。

- **idx 31 — PASS，置信度 0.91。** Theorem 1 给出单个 controlled-phase 资源态的精确 extent；CZ/swap 对应最大值 2，因此算法的**资源指数因子**为 \(2^k\)。所谓“恰好翻倍”只适用于该因子；总运行时间还含随 \(n,k,\epsilon,\delta,p\) 变化的多项式项。

- **idx 32 — PASS，置信度 0.88。** §6 Eqs. (115)–(117) 比较旧方法约 \(9^k\) 与新方法约 \(2^k\)，得到约 \((9/2)^k=4.5^k\) 的渐近改进。它是指数因子的理论比值，不是新算法本身运行时间为 \(O(4.5^k)\)，也不是端到端实测加速；论文承认新相位敏感单步子程序更慢。

- **idx 33 — PASS，置信度 0.96。** 摘要及 §§4–5 直接支持：任意相位 controlled-phase 通过资源态 gadget 化，新的相位敏感 FLO 正规形允许在 statevector 层分解，而此前比较方法在密度矩阵层工作。相位信息来自扩展状态描述，不是普通协方差矩阵单独恢复。

- **idx 34 — PASS，置信度 1.00。** 期刊页面元数据确认作者、2024-12-04、Quantum 8:1549 和 DOI `10.22331/q-2024-12-04-1549`。

### arXiv:2009.11884 / SciPost Physics 10, 066

主源：[Local optimization on pure Gaussian state manifolds](https://arxiv.org/abs/2009.11884)

- **idx 35 — PASS，置信度 0.96。** 摘要和 §IV 给出适用于玻色与费米纯高斯流形的局部几何梯度算法，并允许局部约束。这里“高效”是消除冗余方向、提高每步梯度计算效率；没有全局最优或总体多项式收敛保证。

- **idx 36 — PASS，置信度 0.97。** Eqs. (1)–(2) 把流形写为 \(Sp(2N,\mathbb R)/U(N)\) 与 \(O(2N)/U(N)\)，正文明确说自然群作用使几何梯度可高效计算。固定费米宇称扇区时应收紧到 \(SO(2N)\)。

- **idx 37 — PASS，置信度 0.98。** §III 和摘要明确以协方差矩阵、线性复结构为主参数，并提供纯态波函数、准概率分布、Gaussian unitary/Bogoliubov 变换等互换公式。

- **idx 38 — PASS，置信度 0.87。** §§V A–C 确实覆盖近似基态、Gaussian EoP 和 complexity of purification。建议把“已验证应用范围”改成“论文演示或综述的应用”，避免误解为对任意目标都验证了全局正确性。

- **idx 39 — PASS，置信度 0.98。** §VI 明确把“任意混合高斯态的 EoP 可由高斯纯化达到”列为 Conjecture 1，并提供有限规模数值比较、解析界和局部最优性论证。它仍是猜想，ledger 已正确标注，不能升级为定理。

### arXiv:2004.01015 / SciPost Physics 9, 048

主源：[Geometry of variational methods: dynamics of closed quantum systems](https://arxiv.org/abs/2004.01015)

- **idx 60 — PASS，置信度 0.97。** 摘要及 §§IV A–D 系统处理实时演化、激发谱、谱函数、虚时演化；§V 覆盖普通高斯态、群论相干态和广义高斯态。这里是统一几何框架，不是统一的单一数值算法。

- **idx 61 — PASS，置信度 0.96。** 摘要和 Table II 明确：Kähler 流形上多种传统变分原理等价；广义高斯态可能非 Kähler，需区分处理。非 Kähler 并不等于所有方法“失效”，而是等价性破裂、不同投影具有不同守恒性质。

- **idx 62 — PASS，置信度 0.98。** Eq. (25) 和 §IV A 明确给出两种投影；复切空间上因只差 \(i\) 而等价，非 Kähler 的实切空间上不等价，分别对应 Lagrangian 与 McLachlan 原理。“演化方程不唯一”应限定为**变分投影处方不唯一**，不是物理薛定谔方程本身含糊。

- **idx 63 — REFUTE（部分），置信度 0.97。** Eqs. (27)–(28) 和 Proposition 11 Eqs. (164)–(166) 确实证明投影虚时演化是流形度量下的黎曼梯度流，并单调不增能量。但论文没有提 machine learning、Fisher metric 或 natural gradient，也没有声称与 ML natural gradient 的联系“非类比外推”。建议拆成两句：**物理数学结论可 PASS；与 ML 的连接只能标为数学迁移/解释性类比，需另找直接主源。**

- **idx 64 — PASS，置信度 0.94。** §§IV B、V A 把玻色与费米高斯态重写为几何形式，并从近似基态附近线性化流的 \(K\) 谱读取 \(\pm i\omega_\ell\) 激发频率。必须保留论文自己的警告：该谱不是变分上界，可能出现 spurious Goldstone/零模，不能保证每个 \(\omega_\ell\) 对应真实本征态。

### NSF 10303113，对应 arXiv:2010.15518

主源：[Bosonic and Fermionic Gaussian States from Kähler Structures](https://arxiv.org/abs/2010.15518)

- **idx 65 — REFUTE（部分），置信度 0.98。** 正文 §III A 明确说一般纯玻色高斯态是 \(|J,z\rangle\)，由 **\(J\) 加 displacement \(z\)** 才能在忽略整体相位后唯一确定；混合态同样写作 \(\rho(J,z)\)。只有中心化 \(z=0\) 的情形，或物理费米高斯态因宇称而 \(z=0\)，才可说 J 单独刻画。Eq. (123) 还表明给定背景结构时 J 与 covariance 等价，不能宣称表达力上“超越”协方差。建议改为：**“中心化高斯态可由 J 等价刻画；一般玻色态还需一阶矩 z。”**

- **idx 66 — PASS，置信度 0.92。** Eqs. (8)、(13)、(16)–(17) 明确给出费米 \(O(2N,\mathbb R)\)、玻色 \(Sp(2N,\mathbb R)\)，以及共同稳定子 \(U(N)=\{M\in\mathcal G\mid[M,J]=0\}\)。精确物理措辞应补充：连续二次哈密顿量演化位于 \(SO(2N)\) 的恒等连通分支；作用于态矢量的是其 Spin/Pin 双覆盖，而非字面上的 O 矩阵本身。

- **idx 67 — PASS，置信度 0.95。** 引言明确把本工作与两篇姊妹论文衔接：一篇以高斯态为 Kähler 变分流形主要例子，另一篇在这些流形上求可微函数局部极值并比较参数化。它是直接的文献链，但优化算法属于姊妹论文，不是本论文自身新结果。

- **idx 68 — PASS，置信度 0.99。** 引言直接说明：玻色情形 \(\Omega\) 由 CCR/泊松结构固定、\(G\) 携带态相关；费米情形 \(G\) 由 CAR 固定、\(\Omega\) 携带态相关。仅需注明讨论的是二点相关/高斯框架。

- **idx 69 — PASS，置信度 0.92。** 引言及 Eq. (236) 确实给出用受限复结构 \(J_A\) 表示时玻色和费米纠缠熵完全相同的紧凑公式。把它称为“费米子连续性”的收益是报告作者的解释标签，不是论文术语；可保留为 interpretation，不能列作论文直接结论。

最关键的修订原则是：idx 25/30 的“高效”必须写成条件化资源复杂度；idx 39 必须保持 conjecture；idx 63 的 ML 迁移与 idx 69 的“连续性”标签必须与物理论文直接结论分层。
