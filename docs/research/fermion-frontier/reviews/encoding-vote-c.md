# 编码主张独立复核 C：全局索引 40–54

复核日期：2026-07-11

复核范围：`gap345-claims.json` 全局索引 40–54，共 15 条。本报告只核对原始论文、正式出版信息和论文自身的图表/定理；未读取其他投票报告。置信度表示“本次投票是否由所列原文充分支持”，不表示结论已经获得独立复现。

## 结论摘要

| 投票 | 数量 | 索引 |
|---|---:|---|
| PASS | 14 | 40–45、47–54 |
| REFUTE | 1 | 46 |
| UNVERIFIED | 0 | — |

唯一驳回项 46 是资源单位错误：PNAS 论文说的是原生门集下的**电路深度为常数、上限为 5 个门层**，不是 pair-tunneling 与 density-dependent tunneling 两个电路都只含“总计 5 个门”。该项的“精确、最优、相对 JW 有深度优势”部分有原文支持，但复合主张中的总门数表述不能保留。

## 跨架构资源口径

| 工作 | 规模变量 | 门数与深度口径 | 拓扑、预处理与实验成熟度 |
|---|---|---|---|
| HATT | `N = 费米模式数 = 映射后的 qubit 数` | Pauli weight 是映射后各 Pauli string 权重的总和；论文的“gate count”主要是编译后的 CNOT 数，depth 是编译电路深度，不能当作物理脉冲数或运行时间。 | `O(N^3)` 是每个哈密顿量的**经典映射构造/编译预处理**，不是量子门复杂度；能否摊销取决于同一映射被重复执行多少次。主体证据是经典编译与仿真；真机证据仅为 IonQ Forte 1 上的 4-mode H2、1,000 shots。 |
| PNAS 费米处理器 | `L = microtraps/费米模式数`，`N = 原子/粒子数`，通常 `N <= L` | 门集 `G` 的 tunneling 与 interaction gate 是高层原生费米门；一个原生门可能包含光镊移动、合并/穿梭和 Rydberg 脉冲，不能与一枚 CNOT 等价计价。“depth 5”是原生门层数，不是总门数或物理时长。 | 常数深度依赖可并行的光镊重排、合适的全连接访问和有界局域项。门分解可预编译，但每次调用仍支付相应执行成本。论文是同行评审的**理论架构提案**；只引用了等价 Rydberg entangler 的构件级实验，没有集成整机实验。 |
| arXiv:2605.12600v1 | `N = 费米模式数 = 逻辑 qubit 数`。spinful 方晶格为 `N=2L^2`；Lieb/Kagome 三站点晶胞为 `N=6L^2`。 | 通用切换的 `C` 是两比特 Clifford 门数，应用表主要报 CNOT 数；`T` 是逻辑/CNOT 层深度。`O(1)` interaction overhead 指渐近阶不增加，不表示常数为 1。 | 2D 最近邻 qubit lattice、行/列可重构阵列、surface-code lattice surgery 是三种不同原语模型。所谓“零空间开销”只指 F2Q 数据编码一 mode 一 logical qubit；不计 surface-code 物理 qubits、手术辅助 patch、测量轮次与 code-distance 时间。全部结果为 2026-05-12 的 v1 理论预印本，无硬件实验、无同行评审。 |

## 逐条投票

### HATT / HPCA 2025（40–44）

原始来源：[arXiv:2409.02010v2](https://arxiv.org/abs/2409.02010)、[PDF](https://arxiv.org/pdf/2409.02010)、[IEEE DOI 10.1109/HPCA61900.2025.00022](https://doi.org/10.1109/HPCA61900.2025.00022)、[HPCA 2025 主会日程](https://hpca-conf.org/2025/main-program/)。

| 索引 | 投票与置信度 | 原文位置 | 复核结论、限定条件与资源单位 |
|---:|---|---|---|
| 40 | **PASS — 0.90（高）** | arXiv v2 Abstract；§VI-A/VI-B，Tables I–IV，pp. 9–12 | 论文确实报告约 5–20% 的摘要级改善，并给出约 15% Pauli weight、5–20% depth、10–30% CNOT 的概括。必须写成“作者在所测 benchmark/编译链上报告的平均或摘要范围”，不能写成逐体系、逐基线保证：例如 neutrino 对 JW 的平均 CNOT 改善约 4%，个别电路指标也会退化。CNOT 与 depth 是 Paulihedral/Rustiq/Tetris 加 Qiskit 编译后的逻辑指标，受编译器与耦合图影响，不是 topology-independent native-gate 优势。最终 HPCA 版本摘要使用约 5–25%，因此引用数字时须标注采用 arXiv v2 还是 proceedings。 |
| 41 | **PASS — 0.97（高）** | Abstract；§V-A/§V-B、Algorithms 1–2，pp. 7–8 | 原始 bottom-up 搜索为 `N` 轮、每轮最坏 `O(N^3)`，总计 `O(N^4)`；限制候选并缓存树路径后，每轮 `O(N^2)`、总计 `O(N^3)`，缓存把反复 traversal 查询从 `O(N)` 降为 `O(1)`。这里 `N` 是 modes/qubits，且这是经典、Hamiltonian-specific preprocessing；论文也证明/构造了 vacuum-preserving Majorana pairing。缓存有额外经典内存，复杂度下降不等于量子深度下降。 |
| 42 | **PASS — 0.92（高）** | §II 对 Fermihedral 的说明；§VI-A/VI-B，Figs. 7–10、Tables II–IV，pp. 2、9–12 | 小规模实例上 HATT 接近 Fermihedral 的 SAT 最优解；Fermihedral 在更大实例上只能给近似解或无法完成，而 HATT 的多项式构造在列出的近似案例中可胜出。结论是有限 benchmark 的经验结果，不是 HATT 的近似比或全局最优性证明。独立性偏低：HATT 与 Fermihedral 有 Yuhao Liu、Gushu Li、Yunong Shi 三位共同作者，比较不是外部复现。 |
| 43 | **PASS — 0.82（中）** | §VI-C，Fig. 11，p. 12 | 在 IonQ Forte 1 的 H2 实验中，HATT 的样本方差最小、平均能量误差排序第二，仅次于 exact Fermihedral，数值次序与主张一致。但实验只有 H2 的 4 modes/4 qubits、1,000 shots、单一 all-to-all trapped-ion 设备，论文未给方差差异的置信区间或显著性检验。“噪声抗性最好”只能作为该样本的描述，不能证明一般性的因果转化或可扩展硬件优势。成熟度：真实整机上的小规模编译实验，不是 HATT 专用硬件，也不是大规模费米模拟。 |
| 44 | **PASS — 0.99（高）** | arXiv metadata 的 Journal reference/Related DOI；HPCA 2025 Main Program 的 Session 2A；IEEE proceedings DOI | 正式出版和会议接收可核实，故可标为同行评审的 HPCA 2025 proceedings，而不是仅有预印本。HPCA 是否称“顶会”属于声誉判断，不应被当作资源计数正确性的额外证据；具体数字仍是同一作者团队的一项研究，未因此获得独立复现。 |

### PNAS 2023 费米量子处理器（45–49）

原始来源：[PNAS DOI 10.1073/pnas.2304294120](https://doi.org/10.1073/pnas.2304294120)、[PMC 开放全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC10468619/)。正式发表为 PNAS 120(35), e2304294120，同行评审研究论文。

| 索引 | 投票与置信度 | 原文位置 | 复核结论、限定条件与资源单位 |
|---:|---|---|---|
| 45 | **PASS — 0.89（中高）** | §II “Hardwired Fermi Statistics”，pp. 2–3 | 原文明确把 JW 下的一般 tunneling gate 计为 `O(L)` entangling gates，并提出用运动基态中的费米原子直接实现 `G`。`L` 是 microtraps/modes，不是粒子数 `N`；`O(L)` 是最坏/一般长 JW string，若两模式在 JW 次序中相邻则为 `O(1)`。原生侧的常数深度是以 tunneling/interaction 为硬件宏门并假设移动和局域项可并行，不含移动距离、脉冲时长和错误校正成本。故这是条件化的逻辑门深度比较，不是同一物理原语下的 wall-clock 比较。 |
| 46 | **REFUTE — 0.98（高）** | §III，Eqs. (5)–(7)、Fig. 3(a,b)，p. 4 | 原文支持“两种分解 exact and optimal，且原生门电路深度为常数、上限为 5”，也支持相对 JW 的深度优势；但不支持“两者都总计固定 5 个门”。Fig. 3(a) 的一个层中有多个并行原生门，Eq. (7) 的 density-dependent 分解本身列出四个顺序因子。应改为：“在门集 `G` 下，pair-tunneling 与 density-dependent tunneling 有 exact/optimal 的常数深度分解，深度不超过 5 个原生门层。”论文该段也未把一个 `G` gate 展开为 CNOT 或物理脉冲，因而不能跨架构按“5 CNOT”引用。 |
| 47 | **PASS — 0.93（高）** | §II，Eq. (1)–(3)，pp. 2–3 | 光镊运动基态中的同种费米原子以占据数 Fock basis 承载模式，硬件的粒子交换统计给出 CAR，并通过 Merge/Shuttle 与 Rydberg 过程实现 `G`，所以不需软件维护 JW parity string。限定：所谓“非局域”门需要先物理重排/搬运原子，不是瞬时远程门；保持不可分辨性和运动基态是正确性条件，也是论文列出的主要实验挑战。结论属于架构设计，不是整机实证。 |
| 48 | **PASS — 0.86（中）** | §II interaction-gate 段，p. 4；§V，pp. 6–7 | 论文是整机蓝图，并明确列出“to build”的挑战；没有展示集成费米量子处理器。它指出 `U_int` **本质等价于**已在 alkali/alkaline-earth neutral atoms 上用 Rydberg blockade 实现的标准 qubit entangler，并说明如何通过相位选择得到目标门（差一个单粒子相位）。因此“构件级已有实验”可保留，但必须写成等价纠缠原语的先前实验，而不是移动费米寄存器中完整 `U_int` 工作流已经验证。论文自身是同行评审理论提案。 |
| 49 | **PASS — 0.96（高）** | §III Fig. 3(d,e) 与 LiH 段，pp. 4–5；§IV Fig. 4(b)，pp. 5–6；Conclusion，p. 7 | 论文给出 LiH VQE 的理论/误差模型示例，以及 Z2 LGT 一阶 Trotter step 的电路构造；LGT 常数深度依赖局域 Hamiltonian、并行费米门和无 JW strings。LiH 不是硬件运行，脚注条件为 2 electrons/4 active orbitals；更大分子优势随 orbital 数增长是作者明确留待 separate work 的预期，不能写成本文验证结果。预编译只节省分解搜索，执行时每个 Trotter/ansatz 调用仍要支付原生门成本。 |

### 动态 JW / 同尺寸 qubit lattice（50–54）

原始来源：[arXiv:2605.12600v1](https://arxiv.org/abs/2605.12600)、[PDF](https://arxiv.org/pdf/2605.12600)。截至复核日，arXiv 仅列 2026-05-12 提交的 v1，没有期刊/会议引用；以下均应标为未同行评审的理论预印本结果。

| 索引 | 投票与置信度 | 原文位置 | 复核结论、限定条件与资源单位 |
|---:|---|---|---|
| 50 | **PASS — 0.94（高）** | Abstract；§II，pp. 4–5；Appendix E, Theorem 16/Corollary 17，pp. 18–19 | 构造在同尺寸 2D qubit grid 上切换互补 boustrophedon JW orderings，以 `O(N)` 两比特门覆盖 `O(N)` 个有界范围相互作用，且不加 F2Q 数据 ancilla。严格定理针对 `||x_i-x_j||_infty <= delta`、`delta=O(1)` 的**pairwise** fermionic interactions；“all geometrically local”不应扩展到无界 range、任意高体数或稠密量子化学项。`N` 应读作 fermionic modes/logical qubits；若“物理站点”含两个 spin modes，则一站点对应两 qubits。“零空间开销”不含容错编码与手术 ancillas。 |
| 51 | **PASS — 0.95（高）** | Abstract/Introduction，p. 1；§II，pp. 4–5；Appendix C, Corollary 11，pp. 16–17 | 三档逻辑深度与原文一致：2D nearest-neighbor qubit lattice 为 `O(sqrt(N))`，有合适非局域行/列连接的可重构阵列为 `O(log N)`，lattice-surgery surface-code 模型为 `O(1)`。前者匹配 lattice light cone；中者假设可并行的 row/column connectivity；后者用并行 Pauli measurements、feed-forward 和 auxiliary logical patches 实现 CNOT ladders。`O(1)` 是 logical-round depth，不代表恒定物理时间、零辅助空间或零 code-distance 成本。它与普通裸 qubit lattice 的 depth 不是同一资源模型。 |
| 52 | **PASS — 0.94（高）** | §I，p. 3；§III-A，p. 7；§IV，p. 9 | 论文确实以标准 JW+FSN 为基线给出 `O(N^(3/2))` local interactions、`O(sqrt(N))` depth，并与几何匹配的原生费米处理器 `O(N)` interactions、`O(1)` depth 比较；新方法把 qubit 侧 interaction/gate-count 的渐近阶降到 `O(N)`，只留下架构依赖的深度差。这里“消除差距”只指渐近 scaling，不指常数相同，更不等于相同保真度或 wall-clock。原生 `O(1)` 假设 bounded-degree local terms 可按常数层并行；fault-tolerant 侧“连深度优势也消失”仅在论文的 lattice-surgery logical-depth 成本模型成立，物理 qubit-time 成本仍未比较。 |
| 53 | **PASS — 0.98（高）** | §II，p. 4 的 `C,T` 上界；§III-A Fig. 5/Table I，pp. 6–7；Appendix I，pp. 26–27 | 数字均可在原文核到：任意 boustrophedon switch 有 `C < 6N + O(sqrt(N))` 两比特门与 `T < 6sqrt(N)+O(1)` 深度；spinful 二阶 Trotter step 的 leading CNOT counts 为 square NN `21N`、square NNN `30N`、Lieb `19 2/3 N`、Kagome `24N`，对应 depths 为 square `4sqrt(N/2)`、Lieb/Kagome `12sqrt(N/6)`。此处 `N` 是 spin-orbitals/qubits：5x5 square 为 `N=50`。5x5 gate-count 与大于 7x7 depth crossover 只针对 Fig. 5 的 NN square、指定 standard/ladder FSN 分解。计数忽略单比特门，并允许把相邻二阶 Trotter steps 的边界 hopping 融合；论文明确说首步额外成本被忽略，因此不是孤立首步的完整 native-gate 总账。 |
| 54 | **PASS — 0.93（高）** | Abstract；§III-B Fig. 6/Table II，pp. 7–8；Appendix G–I，pp. 21–25 | Table II 给出的 ancilla-free 2D nearest-neighbor qubit-lattice 资源确为本文 `O(N^(3/2))` gates / `O(sqrt(N))` depth，对比 Constantinides et al. 的 `O(N^(3/2) log^2 N)` / `O(sqrt(N) log^2 N)` 与 Givens network 的 `O(N^2)` / `O(N)`。论文把“渐近最优”严格限定在 ancilla-free、局域连接、两比特门/电路深度的模型下；不是任意 connectivity 或 fault-tolerant spacetime 的无条件最优。d 维推广给出 depth `O(N^(1/d))`，fermion routing 在 d-D lattice 上匹配 qubit permutation-routing 的渐近深度/门数尺度。比较和最优性证明均来自本论文作者，尚无同行评审或独立复现。 |

## 来源独立性与可引用等级

| 证据组 | 出版状态 | 独立性判断 | 建议引用强度 |
|---|---|---|---|
| 40–44 HATT | HPCA 2025 同行评审 proceedings；arXiv v2 与最终摘要数字略有版本差异 | 所有性能数字来自同一 HATT 团队；Fermihedral 比较有三位共同作者；IonQ 是作者执行的单任务实验 | 可引用为“同行评审论文报告”，数字必须带 benchmark、compiler、topology 与版本限定；不能称独立复现。 |
| 45–49 PNAS | PNAS 2023 同行评审论文 | 架构、资源分析、LiH/LGT 示例均来自同一论文。相互作用门借助多篇先前中性原子实验，但本次未把那些先前论文当作整机验证 | 可引用理论架构与构件可行性；必须明确“component experiment / integrated processor proposal”的边界。 |
| 50–54 动态 JW | arXiv v1，2026-05-12；无正式出版记录 | 四位作者均来自 Innsbruck/Parity Quantum 同一团队；与既有方法的数值比较是提案方自己的解析和编译计数 | 只能写“v1 预印本证明/报告”。适合作为待复核上界和研究方向，不能提升为实验事实或社区共识。 |

## 可直接替换的关键表述

- 索引 46：将“固定的 5 个门”改为“在论文定义的原生费米门集 `G` 下，两类子程序具有 exact/optimal 的常数深度分解，电路深度不超过 5 个原生门层；该数字不是 CNOT 数、物理脉冲数或总门数”。
- 索引 50–52：统一把 `N` 写成“fermionic modes/logical qubits”；spinful 模型另写 `N=2 x 空间站点数`。将“无开销”改成“无**渐近 interaction-count** 开销、无额外 F2Q **logical data qubit**”。
- 索引 43：将“噪声抗性最好”改成“在 4-mode H2、1,000-shot 的 IonQ Forte 1 样本中，HATT 的样本方差最小；尚无跨实例显著性或可扩展性验证”。
