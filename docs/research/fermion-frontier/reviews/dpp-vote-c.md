# 独立验证者 C：DPP / 负相依证据投票（Batch 2）

## 范围与结论

本轮实际范围是 ledger 的 **#5–24、#55–59，共 25 条**。任务早期出现的 “#50–54” 是费米子—量子比特编码组，不属于 DPP 组；本报告没有把它们混入计数。

总体判定：**Needs revision**。

- PASS：22
- REFUTE：3（#16、#55、#57）
- UNVERIFIED：0

判定标准：PASS 表示主张的数学/书目信息核心由正文支撑，但表内的强制边界仍须进入最终稿；REFUTE 表示当前复合措辞含有改变结论的对象错误、量词扩大或与原文相反的复杂性陈述。作者的 “first/novel” 优先权声明只验证为“论文确实如此声称”，不等于我完成了穷尽文献检索。

本报告优先用原始论文和官方会议/期刊版本验证定理。综述只用于核对“该综述说了什么”及审计来源层级，不能被当成另一张独立实验证据票。

## arXiv:2411.00611 / NeurIPS 2024：#5–9（第三票）

一手来源：[NeurIPS 2024 正式论文](https://proceedings.neurips.cc/paper_files/paper/2024/hash/997089469acbeb410405e43f0011be1f-Abstract-Conference.html)、[论文 PDF](https://proceedings.neurips.cc/paper_files/paper/2024/file/997089469acbeb410405e43f0011be1f-Paper-Conference.pdf)、[NeurIPS Spotlight 官方活动页](https://neurips.cc/virtual/2024/events/spotlight-posters-2024)。

| ledger | 判定 | 证据层级、边界与直接 ML 支撑 |
|---|---|---|
| #5 | **PASS，高** | 定理与具体构造。正文明确给出：当所选 DPP 的线性统计方差为 $O(m^{-(1+\delta)})$、$\delta>0$ 时，coreset 基数可达 $m=O(\epsilon^{-2/(1+\delta)})$，严格优于独立抽样的 $O(\epsilon^{-2})$；离散多元 OPE 给出 $\delta=1/d$ 的实例。必须改成“**精心选择、满足方差缩放和 coreset 假设的 DPP**”，不是任意 DPP 都更小。论文自己列出的限制包括：数据由大支撑密度 i.i.d. 生成、需要良好且昂贵的密度估计、收益随维度以 $1/d$ 消失、锐利定理目前只覆盖离散化 OPE。它对 ML coreset 是直接支撑；把这种收益称作一般“费米子优势”仍是解释。 |
| #6 | **PASS，高** | Theorem 1 覆盖 Polish 空间上的 Hermitian、非投影核；Theorem 2 覆盖有限底集的非对称核；Theorem 3 再处理向量值线性统计。非对称结果只在由方差、$\|K\|_{op}$、$\|K\|_*$ 和 $\|f\|_\infty$ 控制的偏差区间内成立，不能写成无条件全尺度集中界。 |
| #7 | **PASS，中** | 论文确实把非对称 DPP 在 coreset 外的 ML 兴趣及“理论工具箱有限”作为动机，并把新集中界定位为扩展。它是作者对已有文献的定位，不是“所有非对称 DPP 都提升 ML”的定理，也不提供物理费米系统到 ML 的因果迁移。 |
| #8 | **PASS，高** | 摘要明确声称 vector-valued objective coresets 是 coreset 文献中的 novelty；Theorems 3、5 给出相应数学结果。可引用为作者的优先权声明，不能把“first”当作独立复现结论。 |
| #9 | **PASS，高** | 官方 proceedings 确认 NeurIPS 2024 正式接收；官方 Spotlight 页面列出该论文。论文首页列 Bardenet、Ghosh、Simon-Onfroy、Tran，并注明按姓氏字母序。它可以作为同行评审的定理来源。 |

**第三票结论：#5–9 全部 PASS；#5 必须保留“特定核、特定数据生成与函数族假设”，不能在汇总时恢复成无条件 DPP 优势。**

## arXiv:2005.03185 / Notices AMS 综述：#10–14

ledger 来源 [Determinantal Point Processes in Randomized Numerical Linear Algebra](https://arxiv.org/abs/2005.03185) 自称 “overview”，不是承载这些结果的独立原始研究。核心结果已回溯到一手来源，包括 [JMLR 2018 volume sampling](https://jmlr.org/papers/v19/17-781.html)、[NeurIPS 2017 volume sampling](https://proceedings.neurips.cc/paper/2017/hash/54e36c5ff5f6a1802925ca009f3ebb68-Abstract.html)、[COLT 2019 distortion-free sampling](https://proceedings.mlr.press/v99/derezinski19a.html)、[NeurIPS 2019 DPP-VFX](https://proceedings.neurips.cc/paper/2019/hash/fa3060edb66e6ff4507886f9912e1ab9-Abstract.html)、[Theory of Computing 的 volume-sampling 论文](https://theoryofcomputing.org/articles/v002a012/) 与 [Guruswami–Sinop 原始稿](https://arxiv.org/abs/1104.1732)。

| ledger | 判定 | 证据层级、边界与直接 ML 支撑 |
|---|---|---|
| #10 | **PASS，高** | 固定设计、满列秩 $X$ 下，$S\sim d$-DPP$(XX^\top)$ 的支撑只含可逆的 $d\times d$ 子矩阵，且 $\mathbb E[X_S^{-1}y_S]=w^*$。一手 volume-sampling 论文确认无偏性。关于 i.i.d. 的否定应限定为“同一未加权子问题解的 i.i.d. 行抽样不能普遍保持该恒等式”，不是说任何经重加权设计的独立无偏估计量都不存在。 |
| #11 | **PASS，高，需补条件** | 精确式 $(d+1)L(w^*)$ 与不可改进因子由定理支持，但 ledger 漏掉关键条件：$X$ 的行处于 general position，即任意 $d$ 行均非退化。没有该条件不能原样引用等式。 |
| #12 | **PASS，中高，必须限定保证类型** | 投影 DPP 的单点边缘确为 leverage scores。$d$ 对 $d\log d$ 的比较是**最坏情形/高概率的秩保持（subspace embedding）**：投影 DPP 以恰好 $d$ 行保持满秩，而独立 leverage 抽样在最坏情形有 coupon-collector 型对数代价。它不是所有损失、所有矩阵上同等准确度所需样本的普遍比值。 |
| #13 | **PASS，高，需收窄“最优”** | $k$-DPP 在 $k\ge r+r/\epsilon-1$ 时给出期望 Frobenius 误差 $(1+\epsilon)$ 界；Nyström 给出期望 nuclear/trace-norm 对应界，且该样本量贸易在最坏情形最优。最优的是这个**期望误差范数下的样本量贸易**，不是运行时间、所有误差范数或 DPP 的唯一性。 |
| #14 | **PASS，中高** | 原始 DPP-VFX 定理支持：给定对 $L$ 的访问，首样本为 $n\,\mathrm{poly}(k)\,\mathrm{polylog}(n)$，后续独立样本为 $\mathrm{poly}(k)$；$L=XX^\top$ 时有更具体的 $O(nd\log n+\mathrm{poly}(d))$ 预处理。隐藏的 $\mathrm{poly}(k)$、核访问模型和多次采样摊销不可省略。“只是适度更贵”是综述的定性总结，不是独立复杂度定理。 |

## arXiv:2502.07285 v4：#15–19

ledger 来源 [Negative Dependence as a toolbox for machine learning](https://arxiv.org/abs/2502.07285) 截至核验日仍是 **review + new developments 的 arXiv preprint**。#15–18 是综述层；#19 的 Section 10 才是该稿新增定理。相应一手来源为 [Bardenet–Hardy, Annals of Applied Probability](https://doi.org/10.1214/19-AAP1504)、[NeurIPS 2021 SGD minibatch 论文](https://proceedings.neurips.cc/paper/2021/hash/8744cf92c88433f8cb04a02e6db69a0d-Abstract.html) 和 [ICML 2019 tree sampler](https://proceedings.mlr.press/v97/gillenwater19a.html)。

| ledger | 判定 | 证据层级、边界与直接 ML 支撑 |
|---|---|---|
| #15 | **PASS，中高，强制收紧函数类** | Theorem 4.1 正确转述原始 quadrature 定理的 $O(N^{-(1+1/d)})$ 方差率，相对 i.i.d. 的 $O(N^{-1})$ 更快。准确前提是：均匀测度、特定 Legendre/OPE DPP、且 $f\in C^1$ **紧支撑于开立方体 $(-1,1)^d$ 内部**。ledger 的“$C^1$ functions on the hypercube”若被理解为所有边界行为均可则过宽；也不能推广成任意 DPP。 |
| #16 | **REFUTE，高** | 对象写错。Theorem 6.4 及 NeurIPS 2021 原始论文研究的是 SGD 的**梯度估计量** $\sum_{i\in S}\nabla_\theta\ell_\theta(x_i)/K_{ii}$，不是 loss estimator，也不是一般 coreset loss；其无偏性是对 empirical gradient 的条件无偏。$O_P(m^{-(1+1/d)})$ 还依赖：数据由超立方体上的连续密度 i.i.d. 生成、特定多元 OPE、谱近似得到秩 $m$ 投影 DPP，以及正则性和“大 batch”渐近。修正版应写：**特定 OPE-DPP minibatch 的无偏梯度估计量具有该方差率；这不是任意 SGD、训练损失或 coreset 的收敛定理。** |
| #17 | **PASS，中高，资源计数须展开** | 稠密谱采样器确有一次性 $O(N^3)$ 特征分解瓶颈。tree sampler 的准确计数是 $O(ND^2)$ 预处理、固定大小 $k$ 的非个性化样本 $O(k^4D\log N+D)$；个性化版本为 $O(k^2D^2\log N+D^3)$。所以 “$O(\log N)$ per sample”只表示在固定 $k,D$ 时对 $N$ 的依赖，不能作为完整总成本。 |
| #18 | **PASS，中，仅作为综述立场** | 摘要确实提出负相依在优化、采样、降维和稀疏恢复等任务中常优于独立方法，并追溯 DPP 的费米子起源。但这是作者综述叙事，例子有不同假设、指标与算法；它不构成跨任务统一优势定理。这里的“直接桥”只在数学模型/历史来源层面直接，不能推导物理费米硬件会提升 AI。 |
| #19 | **PASS，高，证据成熟度低** | Section 10 明确标作 “New results”，Theorem 10.2 在相同 inclusion marginals 下比较 DPP 与任意随机 sampler 的期望重加权剪枝误差。它仍是未同行评审预印本，并依赖理想 teacher 权重正交、H1（样本最多访问一次）、H2（$N\to\infty$）和特定 student/teacher 统计力学框架；不是现代深网的一般剪枝保证。 |

## arXiv:1907.03411 / JMLR 23(167), 2022：#20–24

一手来源：[JMLR 正式页面与论文](https://www.jmlr.org/papers/v23/19-571.html)。

| ledger | 判定 | 证据层级、边界与直接 ML 支撑 |
|---|---|---|
| #20 | **PASS，高** | Theorem 2.10 证明 volume-rescaled non-i.i.d. design 对任意条件响应模型给出严格无偏最优线性预测器。统一前提还包括有限二阶矩、$\mathbb E[xx^\top]$ 可逆、给定输入后响应条件独立且 $y_i$ 的条件分布只依赖 $x_i$。“i.i.d. almost always biased”是作者的概括并有反例/下界支撑，不是对每个可能分布的无例外定理。 |
| #21 | **PASS，高，需写全构造** | Theorem 3.1 给出总样本数 $O(d\log d+d/\epsilon)$、严格无偏和期望 $(1+\epsilon)$ 损失界。构造不是任意“随机设计”：前 $d$ 点来自 volume-rescaled sample，余下来自 leverage-score distribution，且使用 $1/l_x$ 加权最小二乘。样本复杂度与构造条件必须一起引用。 |
| #22 | **PASS，高** | 论文的 decomposition property 和摘要直接支持：size-$d$ 的 volume-rescaled 联合样本可与已有 i.i.d. 点组合；密度相对乘积分布由样本协方差行列式（张成体积平方）重加权。这里确是行列式构造，不只是营销类比。 |
| #23 | **PASS，高** | 固定 $n\gg d$ 数据集上，Theorem 5.9 给出 $O(nd\log n+d^4\log d)\,\mathrm{polylog}(1/\delta)$ 预处理并以高概率返回精确 volume sample；预处理后单样本 $O(d^4)$。作者确称这是首个近线性数据时间的此类无偏估计/首个对 $n$ 无关的 $\mathrm{poly}(d)$ 投影 DPP 单样本方法。优先权是作者声明；不是任意 DPP 都有该成本。 |
| #24 | **PASS，中高，实验与定理要分层** | Figure 1.1 是 $d=5$、Gaussian 输入、cubic 非线性响应，展示的 $k$ 为 10、20、40，每个点平均 50 次运行。红线的 i.i.d. 平均不趋于最优，蓝线的无偏设计呈 $1/T$ 的**平均参数估计平方误差**下降；不是单个估计器的 loss 以 $1/T$ 下降，也不是实验穷举了所有 $k$。ledger 列出的有限二阶矩/可逆协方差正确，但一般定理还需上述条件响应结构。 |

## arXiv:1207.6083 / Foundations and Trends in ML：#55–59

ledger 来源 [Kulesza–Taskar 单著](https://arxiv.org/abs/1207.6083) 的正式出版信息见 [Now Publishers 页面](https://www.nowpublishers.com/article/Details/MAL-044)。它是同行评审 monograph/tutorial，不能给全部五条统一贴 “primary”；Theorem 2.9 和 dual algorithms 可视为该书自身承载的结果，而历史与经典采样部分是综合。费米命名另以 [Macchi 1975 原始论文](https://www.cambridge.org/core/journals/advances-in-applied-probability/article/abs/coincidence-approach-to-stochastic-point-processes/1EED58D03316134553E83A9E96501FE1) 核对。

| ledger | 判定 | 证据层级、边界与直接 ML 支撑 |
|---|---|---|
| #55 | **REFUTE，高** | 前半正确：有限离散 DPP 的归一化、边缘、条件化和精确采样可归约为线性代数；书中对 repulsive MRF/Markov point processes 给出一般 NP-hard/近似困难对照。错误在“**唯一已知、全局负相关下完全 tractable 的概率模型族、核心定理级**”：原文只是 2012 年相关 point-process 讨论中的定性 “essentially unique among this class / in this sense unique”，没有对所有全局负相依模型给出唯一性定理；同书也明确 MAP 不 tractable。修正版应去掉“唯一已知”和“完全”，限定为：**DPP 是一类对若干概率推断任务有精确多项式算法的全局排斥模型。** |
| #56 | **PASS，高** | Algorithm 1 在给定特征分解后按书中计数为 $O(Nk^3)$，一次性稠密 eigendecomposition 为 $O(N^3)$，且 $Z=\det(L+I)$。$k$ 是第一阶段选中的特征向量数/最终随机基数。$N\approx10^3$ 秒级、$10^4$ 十分钟是 2012 年指定 Xeon 机器的历史 benchmark，不是 2026 年的普适可行阈值；多样本时分解可摊销。 |
| #57 | **REFUTE，高** | Theorem 2.9 的核心硬度正确：$\max_Y\det(L_Y)$ NP-hard，并且 $8/9+\epsilon$ 因子内近似仍 NP-hard；书中说明 Ko et al. 首先给出相关硬度，本书证明改编 Çivril–Magdon-Ismail 的 volume 论证。末句与正文相反：硬度**即使在 cardinality constraint 下仍成立**；书中列出的固定 $k$ 贪心保证是 $O(1/k!)$，随 $k$ 衰减，不是通常意义上与 $k$ 无关的常数因子。正确结论是“概率推断 tractable 不延伸到 MAP；基数约束也不消除最坏情形硬度”。 |
| #58 | **PASS，中高，物理量词必须收紧** | Macchi 原始论文确实引入适用于排斥点的 “fermion process”；单著把热平衡费米过程、Pauli anti-bunching 和 DPP 直接连接。因此这不是纯修辞类比。精确现代措辞应是**自由/准自由费米态的某些位置或探测点过程具有行列式关联**，而非任意相互作用费米系统的全部热分布都等于 ML 中的有限 DPP。此历史同源也不证明 ML 性能来自物理量子效应。 |
| #59 | **PASS，高，需计入建核成本** | 对 $L=B^\top B$、$B\in\mathbb R^{D\times N}$，$C=BB^\top$ 共享非零谱；归一化 $\det(C+I)$ 为 $O(D^\omega)$，单点 marginal 在预分解后 $O(D^2)$，大小 $k$ 子集 marginal 为 $O(D^2k^2+k^\omega)$，dual sampling 总计 $O(NDk^2+D^2k^3)$。所以“归一化/边缘化对 $N$ 常数、采样对 $N$ 线性”在 **$B/C$ 已可用且 $D\ll N$** 时成立；形成 $C$ 本身通常要 $O(ND^2)$，不能从总资源账中删除。 |

## 资源计数复核

| 场景 | 可保留的准确计数 | 容易误读之处 |
|---|---|---|
| OPE-DPP coreset | $m=O(\epsilon^{-2/(1+\delta)})$；具体例 $\delta=1/d$ | 是特定方差缩放下的样本复杂度；一般 DPP 不自动获得。论文实现的 DPP 抽样约 $O(nm^2)$，KDE 未预计算时可达 $O(n^2+nm^2)$。 |
| 经典稠密 DPP | eigendecomposition $O(N^3)$；给定分解后 $O(Nk^3)$ | $N\approx10^4$ 是 2012 benchmark，不是现代硬阈值。 |
| tree sampler | preprocess $O(ND^2)$；sample $O(k^4D\log N+D)$ | “$O(\log N)$”只描述固定 $k,D$ 后的 $N$ 缩放。 |
| DPP-VFX / intermediate | 首样本 $n\mathrm{poly}(k)\mathrm{polylog}(n)$，后续 $\mathrm{poly}(k)$ | 依赖核访问、重复采样摊销，隐藏多项式不能省略。 |
| random-design regression | $O(d\log d+d/\epsilon)$ 个点；固定数据总时间 $O(nd\log n+d^4\log d+d^3/\epsilon)$ | 需要 volume + leverage 的混合设计和加权估计器。 |
| 低秩 dual DPP | 构造 $C$ 通常 $O(ND^2)$；分解约 $O(D^3)$；sample $O(NDk^2+D^2k^3)$ | “inference 对 $N$ 常数”只适用于 $C$ 已形成后的指定查询。 |

## 来源质量、独立性与“费米子 → AI”证据链

| 来源族 | 层级 | 独立性结论 |
|---|---|---|
| 2411.00611 | NeurIPS 2024 Spotlight，原始定理 + 小规模实验 | 可作为 coreset 定理主证据。 |
| 2502.07285 | 未同行评审的 review + Section 10 新结果 | Tran、Bardenet、Ghosh 同时是 2411.00611 作者；其 coreset/SGD 叙述不能给 2411 再加一张独立票。#15–17 应计原始论文，而非该 review。 |
| 2005.03185 | RandNLA overview，后发表于 Notices AMS | Dereziński 同时参与它综述的多篇原始工作，并且是 1907.03411 作者；#10–14 与 #20–24 是同一研究脉络，不是两个独立作者群的复现。ledger 的 blanket “primary” 标签错误。 |
| 1907.03411 | JMLR 同行评审原始研究，定理 + 实验 | 是 random-design regression 的主证据；实验只做例证，不替代一般定理条件。 |
| 1207.6083 | 同行评审 monograph，教程/综述与作者结果混合 | 可作 DPP 算法的权威入口，但历史、经典采样和其他作者硬度不能一律标 primary。 |

直接 ML/AI 支撑是实在的，但对象是**经典概率模型与算法**：coreset、SGD gradient minibatch、Monte Carlo、linear regression/RandNLA、Nyström、推荐/信息检索和理想化神经网络剪枝。物理费米联系的直接证据只说明某些自由费米点关联与 DPP 同构、共享行列式排斥结构。当前证据链没有证明：

1. 在物理费米硬件上实现 DPP 会自动提高上述 ML 指标；
2. “费米子性”本身而非精心选择的核、权重、数据分布和估计器造成所有优势；
3. 负相依在任意任务、维度和计算预算下都优于独立抽样。

## 建议写回 ledger

必须重写：

1. **#16**：将 loss/coreset estimator 改成特定 OPE-DPP 的无偏 **gradient estimator**，并列出数据、核、谱近似和渐近条件。
2. **#55**：删除 “唯一已知”“完全 tractable”“核心定理级”；保留“有限 DPP 对若干概率推断任务有精确多项式算法，而一般 repulsive MRF 困难”的限定比较。
3. **#57**：改成“MAP 在基数约束下仍 NP-hard；文中固定 $k$ 贪心保证为 $O(1/k!)$”，不能称一般常数因子可解。

虽为 PASS 但进入综合报告前必须收紧：#5、#11–15、#17–19、#21、#24、#56、#58、#59。
