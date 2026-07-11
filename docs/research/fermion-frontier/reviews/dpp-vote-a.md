# DPP Batch 2：独立验证者 A

## 总判定

按持久 ledger 的实际来源映射，本批审计集合为全局索引 **5–24、55–59**；任务原写的 50–54 实际属于 `2605.12600` 的费米子—量子比特编码，已与主审确认留给编码批次。

25 条最终票：**23 PASS、1 REFUTE、1 UNVERIFIED**。

- `#5` 第三票：**PASS**。`2411.00611` 确实首次给出特定 DPP coreset 严格优于独立采样的基数/误差率结果，但只对满足数据生成、密度估计、函数正则性等条件的特制离散多元 OPE 核成立，不是任意 DPP 的普遍优势。
- `#16`：**REFUTE as written**。定理控制的是 SGD **梯度估计器**，不是 loss estimator；改正对象后，条件方差 \(O_P(m^{-(1+1/d)})\) 及无偏性均成立。
- `#55`：**UNVERIFIED as written**。DPP 精确概率推断成立，但“唯一已知的全局负相关且完全 tractable 模型族”是排他性综述判断，不是论文证明的定理。

## 1. `2411.00611`：Small coresets via negative dependence

一手来源：[NeurIPS 2024 正式论文](https://proceedings.neurips.cc/paper_files/paper/2024/hash/997089469acbeb410405e43f0011be1f-Abstract-Conference.html)。NeurIPS 官方会程标为 **Spotlight Poster**；同行评审：是。

| 全局 / 来源内 | Verdict | 定理证据、条件与边界 |
|---|---|---|
| 5 / 0 | **PASS** | Theorem 6 + Remarks 6.1、4.1：特制 discretized multivariate OPE DPP 的方差为 \(O(m^{-(1+1/d)})\)，统一 coreset 误差可取任意略慢于 \(m^{-(1/2+1/(2d))}\)，严格优于 i.i.d. 的 \(m^{-1/2}\)。等价地，给定误差所需基数指数严格小于 2。条件包括：数据由超立方体内密度 \(\gamma\) i.i.d. 生成；需要良好估计 \(\tilde\gamma\)；参考测度及 query 有正则性；核对角元有下界；函数族满足有限维线性包或有限维 Lipschitz 参数化。优势为 \(1/d\)，高维时消失；论文也明确称 KDE 和 DPP 采样成本是实践限制。 |
| 6 / 1 | **PASS** | coreset loss 恰为线性统计 \(\Lambda(f/K)\)。Theorem 1 覆盖 Polish 空间上的一般 Hermitian、非投影核；Theorem 2 覆盖有限 ground set 上的非对称核；Theorem 3 覆盖 Hermitian 核的向量值统计。非对称结果的容许偏差区间受 \(\|K\|_{\mathrm{op}},\|K\|_\*,\|\phi\|_\infty\) 限制；向量结果含维数因子 \(2p\)。因此“超越投影/对称核”成立，但不是无条件全尺度 Bernstein 界。 |
| 7 / 2 | **PASS** | Introduction 明确指出非对称核已用于推荐等 ML 场景，理论工具有限，Theorem 2 扩展了工具箱。此票仅确认论文的文献定位及其新集中界，不把“此前有限”提升成穷尽性定理。 |
| 8 / 3 | **PASS** | Theorem 3、Theorem 5 首次在该文框架中处理向量值线性统计和向量值 coreset 目标。原主张写的是“论文声称首次”，与正文 “we inaugurate their study” 一致；优先权本身仍属于作者声明，不等于完成全领域穷尽检索。 |
| 9 / 4 | **PASS** | NeurIPS proceedings 确认卷 37 正式收录、四位作者吻合；NeurIPS 官方虚拟会程明确显示 “Spotlight Poster”。论文脚注确认作者按姓氏字母序排列。 |

## 2. `2005.03185`：DPPs in Randomized Numerical Linear Algebra

来源为 Dereziński–Mahoney 的正式综述，后发表于 *Notices of the AMS* 68(1), 34–45 (2021)。其中公式分别追溯到 JMLR、NeurIPS、SODA/COLT 等一手结果；以下判定同时保留原定理条件。

| 全局 / 来源内 | Verdict | 定理证据、条件与边界 |
|---|---|---|
| 10 / 0 | **PASS** | Theorem 2：对满列秩 \(X\in\mathbb R^{n\times d}\)，若 \(S\sim d\text{-DPP}_L(XX^\top)\)，DPP 只选择可逆的 \(d\times d\) 子矩阵，且 \(\mathbb E[X_S^{-1}y_S]=X^\dagger y=w^\*\)。这是对任意固定响应 \(y\) 的精确无偏性；普通 i.i.d. 行采样通常不具此性质。 |
| 11 / 1 | **PASS** | Theorem 4：额外要求 \(X\) 的行处于 general position，即每个 \(d\)-行子集都非退化；此时 \(\mathbb E[L(X_S^{-1}y_S)]=(d+1)L(w^\*)\)，且一般情形下 \(d+1\) 不可改善。这里 \(L\) 是固定设计训练平方损失，不是泛化误差。 |
| 12 / 2 | **PASS，必须限定比较对象** | Theorem 8 证明 projection DPP 的单点边缘就是 leverage scores。projection DPP 用恰好 \(d\) 行以概率 1 保秩；i.i.d. leverage sampling 为获得高概率 rank-preservation/subspace-embedding 通常需 \(d\log d\) 行。因此 log 因子成立于这个保证。不能写成“同一 \((1+\epsilon)\) loss 精度下普遍节省 log d”：\(d\)-DPP 的相关 loss 保证是期望因子 \(d+1\)。 |
| 13 / 3 | **PASS** | Theorem 6：对 cardinality-constrained \(k\)-DPP，\(k\ge r+r/\epsilon-1\) 时 \(\mathbb E E_r(S)\le(1+\epsilon)\|X_{(r)}-X\|_F^2\)，该样本量最坏情形最优。Theorem 7 给出 Nyström 的相同样本量和期望 trace/nuclear-norm 保证。结论针对期望误差与 volume-sampling \(k\)-DPP，不是每次样本都满足。 |
| 14 / 4 | **PASS** | Theorem 13：给定核访问，distortion-free intermediate sampling 首个精确样本耗时 \(n\,\mathrm{poly}(k)\mathrm{polylog}(n)\)，后续样本 \(\mathrm{poly}(k)\)；若输入为高瘦 \(X\)，首个样本 \(O(nd\log n+\mathrm{poly}(d))\)，后续 \(\mathrm{poly}(d)\)。多项式次数和常数被隐藏，“只适度更贵”是综述性判断。 |

## 3. `2502.07285`：Negative Dependence as a toolbox for ML

来源：[arXiv:2502.07285v4](https://arxiv.org/abs/2502.07285)，截至 v4 仍是**未列期刊的预印本综述 + 新结果**。其中 #15 的原定理发表于 *Annals of Applied Probability*，#16 的原定理发表于 NeurIPS 2021；#19 的新 pruning 结果本身尚未同行评审。

| 全局 / 来源内 | Verdict | 定理证据、条件与边界 |
|---|---|---|
| 15 / 0 | **PASS** | Theorem 4.1（源自 Bardenet–Hardy）：节点由 multivariate Legendre/OPE projection DPP 产生，参考测度是 \([-1,1]^d\) 上均匀测度，\(f\in C^1\) 且紧支撑于开超立方体时，估计器无偏且 \(\mathrm{Var}[E_N(f)]=O(N^{-(1+1/d)})\)。不是任意 DPP、任意 \(C^1\) 边界行为或任意测度；更一般测度需原论文额外 Nevai/正则条件。 |
| 16 / 1 | **REFUTE as written；改正后可 PASS** | Theorem 6.4 / NeurIPS 2021 原文控制的是 SGD **经验风险梯度估计器** \(\Xi_{A,\mathrm{DPP}}\)：条件于数据集无偏，且高概率于数据集有 \(\mathrm{Var}[\Xi_{A,\mathrm{DPP}}\mid D]=O_P(m^{-(1+1/d)})\)，独立/Poisson minibatch 为 \(O_P(m^{-1})\)。原 ledger 错写为 loss estimator，并把 coreset 的一般 Horvitz–Thompson 无偏性拼接进同一定理。条件很强：数据 i.i.d. 来自紧支撑连续密度、密度有正下界、\(N\gg m,d\)、特制 OPE 核及谱投影、加权梯度满足有界/Lipschitz 正则性；坏的 DPP 甚至可能比 i.i.d. 方差更大。 |
| 17 / 2 | **PASS，需澄清单位** | 标准 spectral sampler 的完整核特征分解为 \(O(N^3)\)，低秩 \(r\) 时可降至 \(O(r^2N)\)。树结构把**每次选择一个 item 的树遍历**从 \(O(N)\) 降至 \(O(\log N)\)；生成含 \(k\) 个点的完整 DPP 子集至少还需约 \(k\) 次遍历及随 \(k,r\) 增长的矩阵更新。因此不能把 \(O(\log N)\) 写成完整子集样本的总成本。 |
| 18 / 3 | **PASS（综述性主张，不是统一定理）** | 摘要确实综述 DPP、strongly Rayleigh measures、perturbed lattices、随机函数零点在优化、采样、降维、稀疏恢复等任务中相对独立方案的已报道优势，并直接追溯 DPP 到量子/费米系统。它证明的是多个有条件结果的集合，不存在“负相依在所有这些任务中普遍优于独立”的统一定理；从费米来源到 ML 应用属于结构迁移，不是物理量子优势。 |
| 19 / 4 | **PASS，强边界** | Sec. 10 确实给出新的 DPP neural-network pruning 定理。Theorem 10.2 只在理想两层 teacher–student 模型中成立：Gaussian 输入、erf 激活、单遍大数据假设 H1、\(N\to\infty\) 的 H2、teacher 隐层权重正交、student 已到特定完美重构固定点、特定二层重加权；在相同 inclusion marginals 的随机采样器中，DPP 的期望泛化误差最小。不能外推到一般深网或通用网络压缩；结果为预印本。 |

## 4. `1907.03411`：Unbiased estimators for random design regression

一手正式来源：[JMLR 23(167), 1–46 (2022)](https://www.jmlr.org/papers/v23/19-571.html)。同行评审：是。

| 全局 / 来源内 | Verdict | 定理证据、条件与边界 |
|---|---|---|
| 20 / 0 | **PASS** | Theorem 2.10：对任意联合分布 \(D\)，只要求 \(\mathbb E\|x\|^2<\infty\)、\(\mathbb E y^2<\infty\)、\(\Sigma=\mathbb E[xx^\top]\) 可逆，且给定输入后响应条件独立；volume-rescaled 非 i.i.d. 设计使最小二乘解严格无偏。无需线性响应或 Gaussian 噪声。论文所说 i.i.d. “almost always biased”是一般现象，不是每个分布都偏。 |
| 21 / 1 | **PASS** | Theorem 3.1：对任意 \(\epsilon>0\)，以 \(d\) 个 volume-rescaled 点加 \(k-d\) 个 leverage-distribution 点构造加权最小二乘，\(k=O(d\log d+d/\epsilon)\)，同时无偏且 \(\mathbb E L_D(\hat w)\le(1+\epsilon)L_D(w^\*)\)。该界不是 vanilla volume sampling 单独实现；后者可有很差 loss。 |
| 22 / 2 | **PASS** | Theorems 2.4、2.10：size-\(k\) volume-rescaled design 可分解为 \(k-d\) 个 i.i.d. 点和 \(d\) 个按 \(\det(X^\top X)\) 即张成体积平方重加权的联合点；增加这 \(d\) 个点即可消除偏差。对有限固定设计，它就是 projection/volume DPP；连续情形是相对于输入测度的 determinantal volume-rescaled 分布。仍需上述二阶矩与可逆协方差。 |
| 23 / 3 | **PASS** | 固定设计 \(X\in\mathbb R^{n\times d},n\gg d\) 下，Theorems 5.6、5.9 给出 distortion-free intermediate sampling：预处理 \(O(nd\log n+d^4\log d)\,\mathrm{polylog}(1/\delta)\)，随后精确 size-\(d\) volume/Projection-DPP 样本约 \(O(d^4)\,\mathrm{polylog}(1/\delta)\)，优于旧 \(O(nd^2)\)。所谓“时间只随样本量”指预处理后的采样阶段；整体仍必须近线性读数据。 |
| 24 / 4 | **PASS（实验性证据）** | Fig. 1.1 确为 \(d=5\) 标准 Gaussian 输入、非线性 \(\xi(x)=\sum_i(x_i+x_i^3/3)\) 加 Gaussian 噪声。所测 i.i.d. least-squares 在 \(k=10,20,40\) 均有偏，模型平均停在偏差底；加入 size-\(d\) volume-rescaled 样本后无偏，平均估计误差随独立估计器数 \(T\) 呈 \(1/T\)。这是合成实验，不是“所有 k 的数值定理”；理论无偏性的总体条件如 #20。 |

## 5. `1207.6083`：Determinantal point processes for machine learning

正式来源：[Kulesza–Taskar, *Foundations and Trends in Machine Learning* 5(2–3), 123–286](https://doi.org/10.1561/2200000044)。同行评审：是。

| 全局 / 来源内 | Verdict | 定理证据、条件与边界 |
|---|---|---|
| 55 / 0 | **UNVERIFIED as written；核心子句 PASS** | 对有限离散 DPP，归一化 \(\det(L+I)\)、边缘化、条件化及精确采样都有多项式时间精确算法；一般 MRF 的 marginal/conditioning 为 NP-hard 且难近似。可是 ledger 增加的“唯一已知的、全局负相关下仍完全 tractable 的概率模型族”不是定理，也未由 2012 文献完成穷尽性证明；且 DPP 的 MAP 本身 NP-hard。最终报告应保留“DPP 将全局负相关与一组精确概率推断算法结合”，删除“唯一已知/完全 tractable”。 |
| 56 / 1 | **PASS** | Sec. 2.4.4：给定 \(L\) 的 eigendecomposition，HKPV Algorithm 1 总运行时 \(O(Nk^3)\)，其中 \(k=|V|\)；主要循环含 \(O(Nk^2)\) Gram–Schmidt。一次性完整 eigendecomposition 为 \(O(N^3)\)，可在多次采样间复用；书中 2012 年硬件数字为 \(N\!\approx\!10^3\) 数秒、\(N\!\approx\!10^4\) 约十分钟，只能作为当时实践量级，不应当作当前硬件上限。 |
| 57 / 2 | **PASS，后半句必须改写** | Theorem 2.9：对 PSD \(L\)，最大化 \(\det(L_Y)\) 的 DPP mode/MAP 是 NP-hard，且达到优于 \(8/9+\epsilon\) 的近似比仍 NP-hard；X3C 归约还说明在 cardinality constraint 下仍难。书中给出的 size-\(k\) greedy 保证约 \(O(1/k!)\)，仅对固定 \(k\) 可称“常数”，不是与 \(k\) 无关的强常数近似。因此可解性边界是“概率推断可解、MAP 难”，不能写“MAP 只需基数约束就有良好常数近似”。 |
| 58 / 3 | **PASS，物理范围需收紧** | Sec. 2 明确追溯 Macchi 的 “fermion processes”，并把 Pauli 排斥导致的 antibunching 与 DPP 相关函数相连。这是自由/理想、quasi-free fermion 平衡态或相应探测过程中的字面 determinantal 结构，不是任意有相互作用费米体系的热平衡分布都为 DPP。应写“DPP 对某类非相互作用费米过程是精确模型”，而不是泛指所有费米子。 |
| 59 / 4 | **PASS** | 当 \(L=B^\top B\)、\(B\in\mathbb R^{D\times N}\)、\(D\ll N\) 时，dual kernel \(C=BB^\top\) 共享非零谱。归一化需 \(O(D^\omega)\)，单个 marginal query 对 \(N\) 为常数；完整 dual sampler 为 \(O(NDk^2+D^2k^3)\)，故固定 \(D,k\) 时对 \(N\) 线性。若要计算全部 \(N\) 个 marginals 仍至少线性于 \(N\)；“常数时间”只指固定查询且相对于 \(N\)。 |

## 建议写回 ledger

- `PASS`: 5–15、17–24、56–59。
- `REFUTE / rewrite-required`: 16。
- `UNVERIFIED / rewrite-required`: 55。
- 强制 caveat：5、6、12、15、17–19、21–24、57–59。

本文件为验证报告；未修改原始 claim ledger 或其他研究工件。
