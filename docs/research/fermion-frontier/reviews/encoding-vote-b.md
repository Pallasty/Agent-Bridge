## 编码／原生费米硬件主张：对抗验证 B

总体判定：**12 PASS / 2 REFUTE / 1 UNVERIFIED**。需要按现有措辞重写的全局索引为 **43、46**；**54** 的构造上界可信，但“门数也已证明渐近最优”在 v1 中没有找到对应下界证明，故不把整条升级为 PASS。

本票独立审查 `gap345-claims.json` 全局索引 40–54，仅使用三篇主源、正式出版元数据及正文所指向的原始构件实验；未读取其他验证票。判定重点是资源单位、比较基线和实验成熟度，而不是论文摘要是否逐字出现同一句营销表述。

### 统一资源口径与成熟度

| 来源 | 规模符号与资源单位 | 实验／出版状态 |
|---|---|---|
| HATT, arXiv:2409.02010 / HPCA 2025 | $N$ 是费米模式数，也等于映射后的 qubit 数；mapping 构造时间与量子电路成本是两类资源。论文的 gate count 主要指指定编译流程后的 **CNOT 数**，depth 指逻辑门层数。 | [IEEE HPCA 2025，DOI 10.1109/HPCA61900.2025.00022](https://doi.org/10.1109/HPCA61900.2025.00022)，同行评审。大部分结果是经典编译／噪声模拟；真机只运行 4-mode H2、1000 shots。 |
| PNAS 120, e2304294120 (2023) | $L$ 是 microtraps／费米模式数，$N$ 是原子／粒子数；$O(L)$ 不能改写成粒子数 $O(N)$。gate/depth 以作者提出的原生费米门集 $\mathcal G$ 为单位，不含完整 tweezer 搬运时间。 | [PNAS 正式论文](https://doi.org/10.1073/pnas.2304294120)，同行评审。整机是 blueprint／理论提案；Rydberg gate、motional control 等分别有既往构件实验，不是本文的集成整机实验。 |
| arXiv:2605.12600v1 | 一般 $N$ 是费米模式数 = logical qubit 数；自旋ful $L\times L$ 方格例中 $N=2L^2$。gate 多指 two-qubit Clifford／CNOT；surface-code 的 $O(1)$ 是 logical measurement-round depth。 | [2026-05-12 v1](https://arxiv.org/abs/2605.12600)，截至审查日无 journal reference／DOI；理论构造和资源估算，无硬件实验，尚未同行评审。 |

### HATT / HPCA 2025：全局 40–44

- **idx 40 — PASS，置信度 0.96。** 位置：Abstract；§V-B/C，Tables I–V。电子结构平均值相对 JW 为 Pauli weight -14.77%、CNOT -25.84%、depth -19.33%；Fermi-Hubbard 相对 JW 为 -20.90%、-22.90%、-7.88%，相对 BK/BTT 也给出相应降幅，足以支持“约 5–20% 级总体改善”的核心。必须保留三点：这些是**按模型、基线和 compiler 聚合的平均值或 up-to 值**，不是每个实例都改善；neutrino 对 JW 的 CNOT 平均仅 -4.01%，小实例还有 HATT depth/gate 更差的反例；“gate count”在主表是 Paulihedral/Rustiq/Tetris + Qiskit L3 后的 CNOT 数，不是所有原生门总数。连接图也分 all-to-all、Manhattan、Sycamore、Montreal，百分比不可跨拓扑混用。

- **idx 41 — PASS，置信度 0.96。** 位置：§III-C Complexity；§IV-A–C，Algorithms 2–3；§V-E/F。operator pairing 将每步候选从三节点选择收紧为二节点选择，双向 map 缓存再把 `descZ`／`traverse_up` 从最坏 $O(N)$ 降为 $O(1)$，论文据此从 $O(N^4)$ 降至 $O(N^3)$；有效 Majorana pair 保证 vacuum 映为 $|0\rangle^{\otimes N}$。关键隐藏条件：§III-C 明说**忽略 Pauli-weight 计算本身，并把它视为由输入 Hamiltonian 决定的常数**，所以 $O(N^3)$ 不是对项数随 $N$ 快速增长的任意 Hamiltonian 的完整端到端复杂度。vacuum preservation 不增加候选搜索阶数，但 Table VI 显示映射权重仍有约 0.43% 的实例平均差异，不能说逐实例性能严格不变。

- **idx 42 — PASS，置信度 0.91。** 位置：Introduction；§V-C/E，Tables I–II，Fig. 12。小例中 Fermihedral 的完成型 SAT 解提供最优 Pauli-weight 基线；当 Fermihedral 只返回带 `*` 的未证最优 incumbent 时，HATT 在列出的电子结构例中更好；约 20 modes 后 Fermihedral 在该实验配置中无法完成，而 HATT 显示多项式增长。这里没有 HATT 的 approximation ratio，也没有证明所有 SAT 实现都在同一阈值失败；“close-to-optimal”“SAT intrinsic hardness”是**有限 benchmark + worst-case complexity 的解释**，不能升级为一般最优性或普适运行时下界。Fermihedral 优化的是 Pauli weight，不保证同时最优 CNOT/depth。

- **idx 43 — REFUTE（部分），置信度 0.99。** 位置：§V-B.5、§V-D.2、Fig. 11、Table I。描述性数字成立：IonQ Forte 1 上仅有 H2 STO-3G（4 modes），1000 shots；论文报告 HATT 的 dispersion/“variance”最小，平均能量与理论值的距离排第二，仅次于 FH。但 ledger 的因果结论不成立：HATT 与 JW 在该实例的 Pauli weight 都为 32、CNOT 都为 21、depth 都为 34；HATT 平均值 -1.511 与 BTT -1.509 的差异远小于图中波动，正文没有独立重复、置信区间或显著性检验。因此这个单例证明“测到了不同输出分布”，不能证明是 Pauli-weight 优化导致、不能证明一般 noise resistance 最佳。修正版应写成**小型构件级真机观察，与噪声抗性假说一致，但不构成因果或可扩展性验证**。

- **idx 44 — PASS，置信度 1.00。** 位置：IEEE/Crossref 元数据和 arXiv journal reference。题名、作者、HPCA 2025 proceedings 与 DOI `10.1109/HPCA61900.2025.00022` 一致，故可标同行评审。HPCA 的社区地位不替代对百分比、拓扑和单例实验边界的审计。

### PNAS 2023 中性原子费米处理器：全局 45–49

- **idx 45 — PASS，置信度 0.96。** 位置：§II Hardwired Fermi Statistics，Eqs. (1)–(3)。JW 下两个沿 canonical order 相距 $O(L)$ 的 mode 的 tunneling gate 需要 $O(L)$ entangling gates；直接实现 $\mathcal G$ 中 tunneling gate 后，逻辑门深度不随 $L$ 增长。这里 $L$ 是 traps/modes，$N$ 在该文是原子数。$O(L)$ 是远距离／最坏尺度，不是每个 JW hopping 都线性；native constant depth 还依赖 all-to-all tweezer rearrangement、ground-state motional control 和 arbitrary-angle gates，并未计入约 500 μs 级搬运、校准或误差纠正时间。

- **idx 46 — REFUTE（部分），置信度 0.99。** 位置：§III，Eqs. (5)–(6)，Fig. 3(a–c)。论文原句是两个 decomposition 具有 “constant circuit **depth of 5 gates**”，不是“每个只用总计 5 个基础门”；Fig. 3(a) 的 pair-tunneling 在若干层内含并行的多只 interaction gates，总 gate count 大于五。exact 在所写角度下成立；“optimal”是作者在所选原生门集 $\mathcal G$ 与其变分搜索中的表述，正文未给跨门集的全局门数／深度下界。正确资源单位是**五层 native-gate depth**，并依赖 atom-array all-to-all connectivity；不能写成五个通用两比特门。

- **idx 47 — PASS，置信度 0.97。** 位置：Significance、§I–II、Figs. 1–2。用同种费米原子的 occupation Fock register，反对易关系和交换符号来自原子全同性；若 motional wavefunctions 能相干重叠，native tunneling 不需软件 JW string。这是物理层面直接连接，不是类比。必须同时写出工程条件：每个 trap 的 motional ground state、indistinguishability、低 leakage/dephasing、可合并／搬运 tweezers；§V 估计在一个 Li-6 参数例中无 echo 时 coherence 只够约 4 次移动。它免去的是指定 native fermionic subroutine 的 JW overhead，不是任意费米算法的所有编译、搬运和纠错开销。

- **idx 48 — PASS，置信度 0.98。** 位置：§I、§II interaction-gate 段、§V Experimental Challenges。论文明确使用 “envision”“blueprint”“proposed processor”，没有集成费米处理器、VQE 或 LGT 真机数据。$U_{ij}^{(int)}(\theta)$ 被称为与已在 alkali／alkaline-earth atoms 上实现的 Rydberg entangling gate **essentially equivalent**；MERGE 所需 motional control 也有分离的 proof-of-principle 先例。故成熟度可写“相关物理构件已有实验，整套 motional fermionic register + gate set 尚是提案”，不能写成本文已经在费米寄存器上集成实现了该门。

- **idx 49 — PASS，置信度 0.99。** 位置：§III LiH VQE/Fig. 3；§IV Z2 LGT/Fig. 4；对应 PNAS 版 Figs. 4–5。LiH 是带 trap fluctuation error model 的数值示例，LGT 是 circuit/Trotter 构造，两者均非整机实验。局部 LGT 项可并行且无 JW strings，所以在作者 native gate/connectivity 模型下单步 depth 为常数；更大分子随 orbital 数增长的优势明确留给 separate work，是预期而非验证结果。

### arXiv:2605.12600v1：全局 50–54

- **idx 50 — PASS，置信度 0.97，必须收窄“所有”。** 位置：Abstract；§II Complementary Encodings；Appendix D–E，Theorem 16。对固定几何作用半径 $\delta=O(1)$ 的**所有 pairwise basic fermionic interactions**，四个局部覆盖 partition 加互补 boustrophedon JW encodings 可在 $N$ 个 qubits 上用 $O(N)$ two-qubit gates 实现；输入有 $N$ modes，输出正好 $N$ logical qubits，基础 unitary 构造不引入编码 ancilla。它不是任意高体数 local Hamiltonian 的现成定理；“site”必须按一个 fermionic mode 计，自旋ful 一个空间 site 有两个 modes/qubits。零 space overhead 指 F2Q 数据编码，不包括 surface-code physical qubits 或 idx 51 的 lattice-surgery ancilla patches。

- **idx 51 — PASS，置信度 0.97。** 位置：Abstract；Appendix B Theorem 8/Corollary 10；Appendix C Corollary 11；Appendix E Theorem 16。nearest-neighbor square qubit lattice 上 encoding switch 用 $O(N)$ Clifford gates、depth $O(\sqrt N)$，与 light-cone/FSN 的渐近 depth 相同；支持行列 nonlocal interactions 的 fully connected/reconfigurable setting 可把 CNOT ladders 降为 $O(\log N)$；lattice surgery 可用 $O(N)$ logical operations 在 $O(1)$ measurement-round depth 完成。后两档不是免费：neutral-atom 说法假设并行 row/column connectivity且未计移动时间；lattice surgery 明确引入 auxiliary logical patch、joint-Pauli measurements、feed-forward 和 code-distance physical cycles，故 $O(1)$ 不是恒定物理门时延，也不能与 idx 50 的“无编码 ancilla”混为一谈。

- **idx 52 — PASS，置信度 0.94。** 位置：Introduction 前两页；§IV Discussion；Appendix E。标准 JW + local FSN 在二维固定度 lattice 上为 $O(N^{3/2})$ local two-qubit interactions、$O(\sqrt N)$ depth；理想 native fermion lattice 对同一组几何局部项为 $O(N)$ interactions、edge-coloring 后 $O(1)$ depth。本文把 qubit gate count 恢复到 $O(N)$，但普通 local lattice 仍有 $O(\sqrt N)$ encoding-switch depth；lattice-surgery 逻辑成本模型中该 depth 也可为 $O(1)$。这里消除的是**渐近 interaction-count 差距**，不是常数、纠错空间或物理时延；native-fermion 基线也假设固定作用半径和可并行原生局部门。因而“容错下深度优势消失”只能限定为该 logical lattice-surgery cost model，不能宣称两种硬件端到端资源完全相等。

- **idx 53 — PASS，置信度 0.98。** 位置：§II 2D lattices 的显式 bounds；§III-A Table I/Fig. 5；Appendix I。一般 boustrophedon-to-boustrophedon switch 的 **two-qubit Clifford** 上界为 $C<6N+O(\sqrt N)$、逻辑 depth $T<6\sqrt N+O(1)$。Table I 的 $21N,30N,19\tfrac23N,24N$ 是 spinful 模型**单个二阶 Trotter step 的 leading-order CNOT count**，对应 depths 分别为 $4\sqrt{N/2}$ 或 $12\sqrt{N/6}$；此处 $N$ 是总 spin-orbitals/qubits，例如 $5\times5$ 空间 lattice 为 50 qubits。5×5 gate-count 和大于 7×7 depth crossover 是对 Fig. 5 所选 standard/ladder FSN 实现及其 accounting 的数值结果；Appendix I 明说忽略首个 Trotter step 不能与前一步融合的额外成本，并假定 hopping/FSWAP 各按 2 CNOT 分解，不能当硬件无关阈值。

- **idx 54 — UNVERIFIED（复合主张），置信度 0.86。** 位置：§III-B、Table II；Appendix G/H。可核验部分全部正确：无 ancilla 的 2D local qubit lattice 上，作者构造 FFFT 上界为 gate count $O(N^{3/2})$、depth $O(\sqrt N)$；Table II 对比 Constantinides et al. 的 $O(N^{3/2}\log^2N)/O(\sqrt N\log^2N)$ 和 Givens network 的 $O(N^2)/O(N)$；Appendix G 将 local-lattice depth 扩展为 $O(N^{1/d})$，Appendix H 的 fermion routing depth 匹配 qubit routing。未核验的是“**门数和深度均已证明渐近最优**”：v1 对全局 Fourier transform 的 light-cone depth 最优性给出清楚动机，但没有找到 FFFT gate-count 的独立下界 theorem；Table II 只优于两个已选方法，不等于排除所有 $o(N^{3/2})$ gate 构造。建议改为“达到与 local fermion-lattice 实现相同的已知上界，depth 在该 locality 模型下渐近最优；gate-count optimality 为作者主张，尚需明确下界来源”。该篇仍是未经同行评审、无硬件实验的 v1。

### 建议写回 ledger

- `PASS`：**40–42、44–45、47–53**。
- `REFUTE / rewrite-required`：**43、46**。
- `UNVERIFIED / split-required`：**54**。
- 综合时必须把四个层级分开：mapping 预处理时间、logical two-qubit gate count、logical circuit depth、物理执行时间／纠错空间。尤其不能把“原生 fermionic gate 一层”“lattice-surgery 一轮”和“常数墙钟时间”视为同一个资源单位。
