# DPP / 负相依主张：对抗验证 B

总体判定：**20 PASS / 5 REFUTE / 0 UNVERIFIED**。需要按现有措辞降级的全局索引是 **16、18、22、55、58**。这些 REFUTE 多数不是否定底层 DPP 定理，而是拒绝把“特定行列式概率模型的结果”升级成“物理费米子资源已经直接带来 ML 优势”，或拒绝把尚未严密完成的分析写成已证明定理。

### 范围修正与方法

- 本票最初收到的范围含全局索引 `50–54`；经上游纠正，实际范围为 **`5–24, 55–59`**，共 25 条。`50–54` 属于 F2Q 批次，**未纳入本报告，也未参与计数**。
- 审计对象为 `gap345-claims.json`，SHA-256：`ab11ba7a7648c6e2f5d37254d4500a8c405633280c443e4d83e9b2afd673fa81`。
- 只使用论文正文、正式 proceedings／期刊页面及被审论文所依赖的原始研究论文。尤其是 `arXiv:2502.07285` 本身是“review and new developments”；对其 Monte Carlo、SGD 和快速采样转述，分别回溯了 Bardenet–Hardy、Bardenet–Ghosh–Lin 及 Gillenwater et al. 的原始论文。
- `PASS` 表示数学／算法核心成立，但下列“必须保留”的假设也是结论的一部分；`REFUTE（部分）` 表示主张内有真结果，但当前因果、范围或证明强度存在实质错误；置信度是对判定本身的主观概率。

### arXiv:2411.00611 / NeurIPS 2024：全局 5–9

主源：[Small Coresets via Negative Dependence: DPPs, Linear Statistics, and Concentration](https://arxiv.org/abs/2411.00611)；[NeurIPS 2024 proceedings 页面](https://papers.nips.cc/paper_files/paper/2024/hash/997089469acbeb410405e43f0011be1f-Abstract-Conference.html)。

- **idx 5 — PASS，置信度 0.97。** Theorem 6 和 Remark 6.1 确实给出一个构造性存在结果：精心选择的、离散化 OPE 投影 DPP 可达到接近 (m^{-(1/2+1/(2d))}) 的 coreset 精度率，而独立采样至多为 (m^{-1/2})，所以在同一目标精度下可用更小基数。必须写成“该特定 DPP 构造在定理假设下可以”，不能写成任意 DPP 都优于任意独立 coreset。§5.1 还要求数据由大支撑上的密度 i.i.d. 生成、该密度有良好近似；优势仅为 (1/d)，高维时消失，采样在已对角化核下仍耗 (O(nm^2))。

- **idx 6 — PASS，置信度 0.98。** §2.3 将加权 coreset loss 明确写为随机集合的线性统计量；Theorems 1–3 给出新集中界。边界不能合并：Theorem 1 覆盖一般 Polish 空间上的 Hermitian、非投影核；Theorem 2 覆盖有限基集上的非对称核，且允许的偏差范围额外依赖 ‖(K)‖ 的 operator/nuclear norm；向量值 Theorem 3 又只针对 Hermitian 核。原文没有一个定理同时覆盖“非对称 + 向量值 + 任意空间”。

- **idx 7 — PASS，置信度 0.86。** 论文确实把非对称 DPP 在其他 ML 场景的兴起和理论工具不足作为动机，并把 Theorem 2 定位为工具箱扩展。这是作者对文献状态和适用边界的判断，不是一个可从 Theorem 2 单独推出的“此前完全没有保证”定理；最终报告宜写成“作者指出／定位为”。

- **idx 8 — PASS，置信度 0.90。** 摘要和 §1 明说 vector-valued objective 是 coreset 文献中的 novelty，Theorem 3 及后续 coreset 推导给出实质内容。这里通过的是“论文作出首次性主张且提供对应结果”；仅凭作者自述不能独立完成全历史优先权证明，故不要改写成无保留的“已穷尽文献确认全球首次”。

- **idx 9 — PASS，置信度 0.99。** NeurIPS proceedings 确认题名、四位作者与 2024 同行评审出版；arXiv 作者元数据明确写有 “Accepted at NeurIPS 2024 (Spotlight Paper). Authors are listed in alphabetical order”。Spotlight 标签来自作者提交元数据，proceedings 页面本身未显示该标签，但不存在仅预印本问题。

### arXiv:2005.03185 与其原始结果：全局 10–14

审计入口：[Determinantal Point Processes in Randomized Numerical Linear Algebra](https://arxiv.org/abs/2005.03185)。关键原始论文包括 [Unbiased estimates for linear regression via volume sampling](https://arxiv.org/abs/1705.06908)、[Optimal Column-Based Low-Rank Matrix Reconstruction](https://arxiv.org/abs/1104.1732)、[Fast DPPs via distortion-free intermediate sampling](https://arxiv.org/abs/1811.03717) 和 [Exact DPP sampling with sublinear-time preprocessing](https://arxiv.org/abs/1905.13476)。`2005.03185` 自称 overview，不能把它误列成以下每个定理的首发论文。

- **idx 10 — PASS，置信度 0.98。** 对满列秩 (X\in\mathbb R^{n\times d})，projection (d)-DPP (S\sim d\text{-DPP}_L(XX^\top)) 总是选出保秩的 (d) 行，且 Theorem 2 给出精确恒等式 (\mathbb E[X_S^{-1}y_S]=w^*\)。原始 volume-sampling 论文也证明相同无偏性。这里的 i.i.d. 对照应表述为“任何 i.i.d. 行采样方法不能同时普遍满足该精确恒等式”，而非“每个具体 i.i.d. 估计在每个线性模型中都必然有偏”。

- **idx 11 — PASS，置信度 0.97，必须补假设。** Theorem 4／原始论文 Theorem 5 的确是精确等式 (\mathbb E[L(X_S^{-1}y_S)]=(d+1)L(w^*)\)，并给出不可改进实例。等式要求 **general position：任意 (d) 行均非退化**；原始论文还说明不满足 general position 时只保留 ≤((d+1)L(w^*)) 的上界。Ledger 省略该条件，最终引用必须补回。

- **idx 12 — PASS，置信度 0.95，比较对象需收窄。** Theorem 8 精确证明 projection DPP 的一阶边缘概率就是 leverage scores；正文比较的是“保秩 sketch／覆盖所有 (d) 个方向”：DPP 恰取 (d) 行，i.i.d. leverage-score sampling 为高概率保秩通常需 (d\log d) 行。这个 (\log d) 不是任意误差指标、任意失败概率或所有 RandNLA 任务的统一加速因子，也不是同一 ((1+\epsilon)) 期望损失保证的直接横比。

- **idx 13 — PASS，置信度 0.95。** Theorems 6–7 给出：当 (k\ge r+r/\epsilon-1) 时，volume/DPP 采样的列子集低秩逼近期望 Frobenius 误差和 Nyström 期望 nuclear/trace-norm 误差均为 ((1+\epsilon)) 倍最优，且该样本基数最坏情形最优。综述所谓 “optimal randomized algorithm” 只在**期望误差 + 样本基数 + 指定范数**意义下成立；它不是运行时最优、逐样本高概率最优，也不是对所有低秩目标的统一最优性。

- **idx 14 — PASS，置信度 0.96。** Theorem 13 确实把一般 (L)-ensemble／(k)-DPP 的首个精确样本降到 (n\,\mathrm{poly}(k)\,\mathrm{polylog}(n))，之后独立样本为 (\mathrm{poly}(k))；若 (L=XX^\top)，首样本为 (O(nd\log n+\mathrm{poly}(d)))，之后 (\mathrm{poly}(d))。必须区分一次预处理／首样本与摊销后的后续样本，并保留“可访问核／低秩因子、隐藏多项式及数值子程序”的条件；“只是适度更贵”是综述性评价，不是无条件资源上界。

### arXiv:2502.07285 及回溯原始论文：全局 15–19

审计入口：[Negative Dependence as a toolbox for machine learning: review and new developments](https://arxiv.org/abs/2502.07285)。原始对照：[Monte Carlo with determinantal point processes](https://arxiv.org/abs/1605.00361)、[Determinantal point processes based on orthogonal polynomials for sampling minibatches in SGD](https://arxiv.org/abs/2112.06007)、[A Tree-Based Method for Fast Repeated Sampling of DPPs](https://proceedings.mlr.press/v97/gillenwater19a.html)。

- **idx 15 — PASS，置信度 0.98。** 综述 Theorem 4.1 忠实重述 Bardenet–Hardy 的定理：均匀测度超立方体、特定 multivariate Legendre/OPE DPP、(f\in C^1) 且支撑紧含于开立方体 ((-1,1)^d) 时，加权估计无偏并有 (O(N^{-(1+1/d)})) 方差。它严格快于同等有限方差条件下 i.i.d. Monte Carlo 的 (O(N^{-1}))，但只对这类 OPE 构造和固定 (d) 成立；原论文还提醒并非任意 projection kernel 都降低方差。把它称为“费米子统计优势”只能是数学 DPP 层标签，不能作为物理费米硬件资源定理。

- **idx 16 — REFUTE（部分），置信度 0.98。** 无偏部分成立：Bardenet–Ghosh–Lin Proposition 2 严格证明实际离散 DPP **梯度估计量** (\Xi_{A,\mathrm{DPP}}) 在给定数据集下无偏。可是原论文 Proposition 4 只对一个 smoothed theoretical estimator (\Xi_{A,s}) 正式证明 (O_P(m^{-(1+1/d)}))；对实际离散 DPP，正文仅说附录分析 “indicates a fluctuation bound”，附录 §S3.3 又明确称 spectral approximation 仍需 “further tightened and rigorised”。2025 综述把它升级为 Theorem 6.4 的“authors proved”表述，强于原始证据。此外 (L_S(\theta)) 在该节是**梯度向量估计量**，不是 scalar loss／一般 coreset loss；假设还包括连续超立方体数据、密度和 OPE/KDE 正则性、(N,m,d) 的渐近关系等。修正版应拆开写：**实际 DPP 梯度无偏已证；目标方差指数对平滑估计器已证、对实际离散 DPP 在原论文中仍是带未严密化谱逼近的分析性主张。**

- **idx 17 — PASS，置信度 0.94，复杂度必须完整写出。** 一般密核特征分解确为 (O(N^3))。Gillenwater et al. 的精确低秩树采样器假设 (L=B^\top B, B\in\mathbb R^{D\times N})：一次构树／双核预处理为 (O(ND^2))，之后一个大小为 (k) 的样本为 (O(k^4\log N+D))；个性化版本为 (O(k^2D^2\log N+D^3))。所以“每样本 (O(\log N))”仅表示在 (k,D) 视为固定且完成预处理后，对 (N) 的依赖为对数；不能隐藏 (k^4,D) 并把它写成总成本纯 (O(\log N))。

- **idx 18 — REFUTE（部分），置信度 0.98。** 综述确实罗列了负相依方法在 Monte Carlo、SGD、coreset、降维、信号恢复等任务中的若干定理和实验，也正确追溯 DPP 的量子／费米来源；但“often outperform”是跨异质问题的综述总括，不是一个统一支配定理。更关键的是，经典 ML 算法使用的是可在经典机上定义和采样的 DPP／负相依概率结构；来源没有证明“物理费米子排斥”因果性地转化成这些计算或统计优势。可保留为**直接的数学结构／历史来源桥接 + 各任务独立定理**，不能写成已经证成的“费米物理资源 → 经典 ML 优势”桥。

- **idx 19 — PASS，置信度 0.96。** 该预印本 §10 确实包含作者称为 new results 的神经网络剪枝理论；Theorem 10.2 在两层 teacher–student、Gaussian 输入、erf 激活、online／(N\to\infty)、正交 teacher weights、特定完美重构和重加权结构下，证明在**相同边缘包含概率**的随机采样器中 DPP 的期望泛化误差最小。边界很窄，不能扩成一般深网压缩定理；论文还说明分析最初来自共同作者的硕士论文，且当前仅是未列期刊版的预印本。“previously unpublished”只能作为作者的版本状态陈述。

### arXiv:1907.03411：全局 20–24

主源：[Unbiased estimators for random design regression](https://arxiv.org/abs/1907.03411)。

- **idx 20 — PASS，置信度 0.98。** Theorem 2.10 对 volume-rescaled、非 i.i.d. 设计给出严格无偏性，而且允许任意条件响应分布 (D_{Y\mid x})。基本条件是 (\mathbb E\|x\|^2<\infty)、(\mathbb E[y^2]<\infty)、(\Sigma_{D_X}=\mathbb E[xx^\top]) 可逆，并按给定输入条件独立查询响应。“i.i.d. almost always biased”是作者对一般非线性随机设计的典型性描述，不表示线性正确设定等所有特例也有偏。

- **idx 21 — PASS，置信度 0.98。** Theorem 3.1 确实以 (k=O(d\log d+d/\epsilon)) 同时实现无偏和 (\mathbb E L_D(\hat w)\le(1+\epsilon)L_D(w^*))。构造不是裸 volume-rescaled sample：它组合一个大小 (d) 的 volume-rescaled sample 与 (k-d) 个 leverage-score samples，并作相应重加权；“任意输入分布”仍受上一条有限二阶矩和非奇异协方差条件约束。

- **idx 22 — REFUTE（部分），置信度 0.98。** 构造机制本身为真：Theorem 2.4 表明大小 (k) 的 volume-rescaled 设计可分解为 (k-d) 个 i.i.d. 点加 (d) 个按平方体积／determinant 联合重加权的点；当 (k=d) 时作者称其为一种 DPP，Theorem 2.10 的无偏证明直接使用 determinant／adjugate 恒等式。可是论文从未把该机制归因于“费米子式排斥”，也没有物理费米系统、CAR 或 Pauli 资源参与。正确结论是：**行列式／volume-sampling 结构是无偏性的构造性来源；把它再命名为物理费米子因果来源属于未证外推。**

- **idx 23 — PASS，置信度 0.97。** 固定 (n\gg d) 设计下，Theorem 5.9 给出成功概率 (1-\delta)、运行时 (O(nd\log n+d^4\log d)\,\mathrm{polylog}(1/\delta)) 的精确 discrete volume sample；摘要将 distortion-free intermediate sampling 定位为首个使 DPP 后段采样只对样本量呈多项式的方法。这里“近线性”仍包含读取／sketch 整个 (n\times d) 输入的代价；不能说端到端完全与 (n) 无关，且“first”是作者优先权主张。

- **idx 24 — PASS，置信度 0.98。** Figure 1.1 的确使用 (d=5) 标准 Gaussian 输入、含 cubic 非线性与 Gaussian 噪声的响应；在该特定实验中，i.i.d. LS 对测试的各 (k) 有偏，模型平均停在非零误差，而增补 volume-rescaled (d) 点后的无偏估计平均误差呈 (1/T)。Ledger 已基本保留理论假设，但“任何样本量 (k)”应限定为这个响应模型／所测设置，不能外推成所有 (D) 的 i.i.d. LS 都有偏；(1/T) 是独立无偏有限方差平均的均方误差率。

### arXiv:1207.6083 / Foundations and Trends in ML：全局 55–59

主源：[Determinantal Point Processes for Machine Learning](https://arxiv.org/abs/1207.6083)。这是正式出版的 ML 专著／综述；其中算法和 hardness 结论均给出明确推导或回溯原始理论来源。

- **idx 55 — REFUTE（部分），置信度 0.99。** 对有限离散 DPP，normalizer、marginals、conditioning 和 exact sampling 的确可由 determinant／eigendecomposition 在多项式时间完成；一般 loopy MRF 的概率推断及近似也确有 hardness 结果。但 claim 把“general MRF”误写成所有 MRF：树上 belief propagation 和若干 associative/submodular 特例是可解的，源文 §2.5 也仅称 DPP 在**所讨论的 repulsive point-process 类**中 “essentially unique”。“唯一已知的、全局负相关下仍完全 tractable 的概率模型族”是无依据的全概率模型宇宙量词；强 Rayleigh 等家族及其子类也不能被这句顺手排除。此外 tractable inference 不包括 MAP（见 idx 57）。

- **idx 56 — PASS，置信度 0.99。** Algorithm 1 在完成特征分解后为 (O(Nk^3))，其中第二阶段最重的 Gram–Schmidt 为 (O(Nk^2))；一般稠密 (L) 的一次特征分解为 (O(N^3))，且 normalizer 是 (\det(L+I))。(N\approx10^3) 数秒、(N\approx10^4) 十分钟是 **2012 年专著所述硬件经验值**，不是 2026 年阈值；可保留为历史可扩展性证据，不能当当前硬件 benchmark。

- **idx 57 — PASS，置信度 0.98。** Theorem 2.9 通过 X3C 归约证明 (\max_Y\det L_Y) 的 DPP mode/MAP NP-hard，且 NP-hard 到 (8/9+\epsilon) 近似；正文进一步指出固定 cardinality 也不消除 hardness。因此 exact probabilistic sampling／marginalization 不推出 exact MAP。需谨慎解释后半句：书中列出的 greedy 保证可低至 (O(1/k!))，所谓 “constant factor under cardinality constraints” 依赖所用目标、约束与 (k)，不能理解成任意 (k) 下接近 1 的统一常数近似。

- **idx 58 — REFUTE（部分），置信度 0.99。** §2 确实直接记载 Macchi 称其为 “fermion processes”，并把 thermal fermion anti-bunching 与 DPP 联系起来；所以这是实质性的物理来源／结构连接，不只是营销式“quantum-inspired”命名。但“DPP 与费米子字面等价”是双向、全称命题，来源并未证明：DPP 是数学概率模型，物理上的 determinant 形式对应理想／准自由、Slater／Gaussian 一类费米关联结构，并非任意相互作用费米体系；反向也不能把每个机器学习 DPP 当成实际热平衡费米系统。允许的表述是**特定费米系统的点配置／关联函数严格为 determinantal，Pauli anti-bunching 提供直接历史与结构锚点**，而不是“所有 DPP = 所有费米子”。

- **idx 59 — PASS，置信度 0.98。** 对 (L=B^\top B, B\in\mathbb R^{D\times N}, D\ll N)，Proposition 3.1 证明双核 (C=BB^\top) 共享全部非零特征值；normalizer (\det(C+I)) 为 (O(D^\omega))，小集合 marginal 查询为 (O(D^2k^2+k^\omega))，这些在 (C) 已构成后对 (N) 为常数。exact sampling 仍线性依赖 (N)，且构造 (C)／树或读取 (B) 通常要 (O(ND^2))；因此“normalization/marginalization 对 (N) 常数”是**预处理后的查询复杂度**，不是端到端无 (N) 成本。

### 建议写回 ledger

- `PASS`：**5–15、17、19–21、23–24、56–57、59**。
- `REFUTE / rewrite-required`：**16、18、22、55、58**。
- 最重要的合成规则：将“DPP 定理”与“物理费米子资源”分层。直接成立的是 determinant／DPP 的概率结构、负相依与具体算法定理；只有在论文明确给出 fermionic state／CAR／Wick 等物理映射时，才能把连接写成物理机制。历史起源或同一 determinant 形式本身，不足以证明物理费米系统为经典 ML 提供了额外计算资源。
