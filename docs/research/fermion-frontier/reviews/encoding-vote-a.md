# 编码与原生费米硬件 Batch 3：独立验证者 A

## 总判定

本批核验全局索引 **40–54**，共 15 条：**14 PASS、1 REFUTE、0 UNVERIFIED**。

- 唯一反驳项是 **#46**。PNAS 论文确实给出两个 exact、system-size-independent-depth 分解，但密度依赖隧穿的 Eq. (7) 是 **4 个顺序基本门**；pair-tunneling 的 Eq. (9) 才可读作 **5 个顺序复合门层**。而且“minimizes total circuit depth”只明确用于变分搜索得到的 pair-tunneling 构造，并不是“两种门均有 5 门且全局最优”的定理。
- `#40–44` 的 HATT 结论来自已同行评审的 HPCA 2025 论文；只有 `#43` 含真机实验，而且只是 IonQ Forte 1 上的 H2、1000 shots。
- `#45–49` 的中性原子费米处理器来自已同行评审的 PNAS 2023 论文，但整机是**理论蓝图**；Rydberg interaction gate 和部分相干运动/隧穿操作属于既有**构件级实验**。
- `#50–54` 来自 `arXiv:2605.12600v1`（2026-05-12），是**未同行评审的理论构造 + 数值资源计数**，没有完整硬件实验。

## 统一资源口径

| 来源 | 系统大小 | 门与深度 | 拓扑、预处理及摊销 |
|---|---|---|---|
| HATT | \(N\) 是费米模式数；映射使用 \(N\) qubits。 | 主要表格报告 mapped Hamiltonian 的 Pauli weight，以及经 Paulihedral/Rustiq/Tetris 与 Qiskit 优化后的 CNOT、U3 和逻辑电路深度；不是统一物理原生门时间。 | HATT 映射构造是经典预处理，复杂度 \(O(N^3)\)。IonQ Forte 1 为 36-qubit all-to-all ion trap；体系结构表还分别测试 Manhattan、Sycamore、Montreal。 |
| PNAS 原生费米处理器 | \(L\) 是 microtraps/费米模式数，\(N\) 是原子/粒子数，通常 \(N\le L\)；不能把二者互换。 | \(\mathcal G\) 中的 tunneling/interaction 是费米原生门。Eq. (9) 的一个符号可代表两个并行门，所以“门层”与“单个基本门数”必须分开。 | 常数逻辑深度依赖可重构 tweezers、可并行 MERGE/SHUTTLE 和非局域移动；原子搬运时间、冷却、泄漏和相干保持不包含在抽象电路深度内。子程序可预编译。 |
| `2605.12600v1` | 定理中的 \(N=L^d\) 是费米**模式/格点数**，并等于 qubit 数；spinful \(L\times L\) Hubbard 方格中 \(N=2L^2\)，不是 \(L^2\) 个物理位置。 | 普通 2D 网格的 count/depth 是最近邻 Clifford/CNOT 口径。Table I 是 leading-order CNOT count/depth；lattice surgery 的 \(O(1)\) 是逻辑测量轮深度。 | 普通网格假设 2D nearest-neighbor；\(O(\log N)\) 需要 all-to-all 或至少行/列内非局域连接；\(O(1)\) 需要 surface-code patches、辅助逻辑 qubits、并行 joint-Pauli measurements 和 feed-forward。Trotter 表格吸收相邻步的门并忽略首步额外成本。 |

---

## 1. HATT：`arXiv:2409.02010` / HPCA 2025

来源：[HATT 预印本与正式发表元数据](https://arxiv.org/abs/2409.02010)，HPCA DOI [`10.1109/HPCA61900.2025.00022`](https://doi.org/10.1109/HPCA61900.2025.00022)。**同行评审：是。** 工作类型：编译算法、经典复杂度分析、仿真/编译 benchmark，外加一个小规模真机案例。

| 全局 / 来源内 | 判定 | 置信度 | 定理/资源证据与适用边界 |
|---|---|---|---|
| 40 / 0 | **PASS** | 高 | Abstract、Introduction、Sec. V-C、Tables I–V 支持。电子结构 benchmark 相对 JW 的平均降幅为 Pauli weight 14.77%、CNOT 25.84%、depth 19.33%；相对 BK/BTT 也有相近量级。Fermi-Hubbard 相对 JW 为 20.90%、22.90%、7.88%。正文因此总结约 15% Pauli、5–20% depth、10–30% CNOT。必须写成**这些 benchmark、编译链和逻辑门基下的经验结果**，不是对任意 Hamiltonian 或硬件的保证。Rustiq/Tetris 的 “up to” 结果也不能与跨 benchmark 平均值混算。 |
| 41 / 1 | **PASS** | 高 | Introduction contributions、Sec. IV-C、Algorithm 2：缓存 `descZ`/向上追踪结果，把单次最坏 \(O(N)\) tree traversal 降至 \(O(1)\)，总构造复杂度由 \(O(N^4)\) 降为 \(O(N^3)\)。Sec. IV-A/B 证明构造保持 vacuum-state preservation。此处 \(N\) 是费米模式/映射 qubit 数；这是**经典映射编译时间**，不是量子电路深度。论文还报告优化前后 Pauli weight 平均只差约 0.43%，但这不是严格的零性能损失定理。 |
| 42 / 2 | **PASS，需收紧“接近最优”** | 中 | Introduction、Sec. V-C/E、Tables I–II、Fig. 12：Fermihedral 用 SAT 在小规模求最小 Pauli weight，在约 20 modes 后失败/不可扩展；Table I 的 `*` 是未收敛的近似解，HATT 在这些电子结构例上优于它。HATT 是 \(O(N^3)\) 构造，且大例优于 JW/BK/BTT。可是“close-to-optimal”是作者的经验描述，并无 approximation-ratio 定理；例如 Hubbard 小例中 HATT 对 FH 最优 Pauli weight 仍可有明显差距。比较目标主要是 Pauli weight，最终 CNOT/depth 还依赖后续编译器。 |
| 43 / 3 | **PASS，证据仅限单案例** | 中 | Sec. V-B.5、Sec. V-D.2、Fig. 11：在 IonQ Forte 1 上只执行 H2，1000 shots；HATT 的能量均值离理论值第二近（FH 最接近），样本方差最低。可写“该小实验观察到方差优势”，不能据此确立 Pauli-weight 优化对任意体系/设备的普遍噪声抗性，更不能作因果归因；样本方差也不等于完整 error-mitigation 或 fault-tolerance 指标。 |
| 44 / 4 | **PASS** | 高 | arXiv journal reference 与 DOI 均指向 2025 IEEE HPCA 正式论文。资源计数可标为**同行评审的 benchmark 结果**；仍须保留 #40–43 的经验范围，同行评审本身不把 benchmark 外推为定理。 |

---

## 2. PNAS 2023：可编程中性原子阵列上的费米处理

来源：[González-Cuadra et al., PNAS 120, e2304294120 (2023)](https://doi.org/10.1073/pnas.2304294120)，可核对的 [PMC 全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC10468619/)。**同行评审：是。** 工作类型：整机架构与门分解的理论提案、误差建模；引用了构件级实验，未展示完整费米处理器。

| 全局 / 来源内 | 判定 | 置信度 | 定理/资源证据与适用边界 |
|---|---|---|---|
| 45 / 0 | **PASS** | 高 | “Hardwired Fermi Statistics” 与 Eqs. (1)–(3) 明说：JW 下一个远距 tunneling gate 需 \(O(L)\) entangling gates，而 motional-ground-state fermionic atoms 可直接实现 \(\mathcal G=\{U^{(\mathrm{int})},U^{(t)}\}\)。这里 \(L\) 是 microtraps/modes，不是原子数 \(N\)。所谓常数深度是每个原生门/局域子程序的**逻辑门层**，依赖可重构 tweezers 与并行移动；不包含随距离变化的搬运时长、冷却和控制开销，也不是所有完整算法都自动常数深度。 |
| 46 / 1 | **REFUTE as written** | 高 | Eqs. (5)–(9)、Fig. 3B/C：两种分解都 exact，且深度不随 \(L\) 增长；但 Eq. (7) 的 density-dependent tunneling 明确是两个 tunneling 加两个 interaction gates，即 **4 个顺序基本门**。Eq. (9) 的 pair-tunneling 可视为 **5 个顺序复合门层**；其中每个 \(U^{(t)}_{i,k}U^{(t)}_{j,l}\) 或 \(U^{(\mathrm{int})}_{i,j}U^{(\mathrm{int})}_{k,l}\) 又含两个并行基本门，所以不能称“两者固定 5 个门”。正文只对变分优化得到的 pair-tunneling 紧凑分解说其 minimizes total circuit depth；未给两种门的普适全局最优下界。修正版应写：“dt 为 4 层；pt 为 5 层复合并行门；二者 exact 且深度与 \(L\) 无关，pt 的最小化限定于论文采用的变分构造。” |
| 47 / 2 | **PASS** | 高 | “Hardwired Fermi Statistics”、Fig. 1：\(N\) 个全同费米原子占据 \(L\) 个 microtraps 的 occupation Fock register，运动基态模式定义 \(c_j,c_j^\dagger\)，硬件粒子全同性给出反对易统计；直接 tunneling 避免 JW parity strings。边界是粒子数守恒门集、良好 motional-ground-state preparation 与可相干重叠/移动；泄漏到激发运动态会破坏这个理想寄存器假设。 |
| 48 / 3 | **PASS** | 高 | tunneling-gate 与 interaction-gate 小节、Experimental Challenges：Rydberg-blockade interaction gate 本质等同既有 neutral-atom entangler，已在 alkali 与 alkaline-earth 平台实现；MERGE 所依赖的相干隧穿/运动控制也有 proof-of-principle 实验。与此同时正文用 “envision”“blueprint”“proposed processor”，并把 coherent motional control 列为主要新挑战。故正确成熟度是**构件级已有实验、完整费米处理器仍为提案**。不能把既有 Rydberg qubit gate 当成整套 fermionic gate set 已集成验证。 |
| 49 / 4 | **PASS** | 高 | Fig. 4 与 Methods 是 LiH（2 electrons、4 active orbitals）的 VQE 电路和噪声模型数值分析，不是真机 VQE。Eq. (12)、Fig. 5B 给出局域 \(Z_2\) LGT 的理论 Trotter step；利用局域项并行和原生 tunneling，抽象逻辑深度与系统大小无关，而 JW 对应多 qubit strings 的两比特门数随 \(L\) 增长。更大分子/advanced VQE 的优势明确属于未来预期，不能写成已实验验证的 scaling advantage。 |

---

## 3. `arXiv:2605.12600v1`：同尺寸 qubit lattice 的动态 JW 编码

来源：[Aigner et al., arXiv:2605.12600v1 (2026-05-12)](https://arxiv.org/abs/2605.12600)。**同行评审：否（截至该 v1 无期刊/会议引用）。** 工作类型：理论构造、证明、资源估算与经典数值 benchmark；无硬件实验。

| 全局 / 来源内 | 判定 | 置信度 | 定理/资源证据与适用边界 |
|---|---|---|---|
| 50 / 0 | **PASS，需把“所有相互作用”限定为局域 pairwise** | 高 | Abstract、Sec. II、Appendix E Theorem 16：在 \(N=L^2\) 个模式的 square fermion lattice 与同尺寸 NN qubit lattice 上，通过互补 boustrophedon JW orderings 之间的动态切换，可用 \(O(N)\) qubit gates 实现所有满足固定 \(\|x_i-x_j\|_\infty\le\delta\) 的**两模式/成对**费米相互作用；相对原生的 \(O(N)\) 无渐近 interaction-count overhead，并保持一模式一 qubit。无 encoding ancillas，但实际 gate synthesis 或 surface code 仍可使用工作/逻辑辅助 qubits。若“site”指 spinful 物理位置，必须改写：每个 spin-orbital 才是一个 mode/qubit。 |
| 51 / 1 | **PASS，必须标明深度单位和连接模型** | 高 | Abstract、Theorem 8、Corollaries 10–11、Theorem 16：square NN qubit lattice 为 \(O(\sqrt N)\) Clifford depth；all-to-all（或行/列内非局域）连接为 \(O(\log N)\)；lattice-surgery surface codes 为 \(O(1)\) logical depth。前两者对应其连接图的 light-cone scaling。\(O(\log N)\) 不是把中性原子物理搬运时间计入后的 wall-clock；\(O(1)\) 具体是 3 轮 logical Pauli measurements + 4 轮 single-qubit Cliffords 的常数轮数，隐藏 code distance、每轮 syndrome cycles、辅助 logical patches 和 feed-forward。 |
| 52 / 2 | **PASS，结论仅为渐近资源比较** | 中 | Sec. I 明确给出 standard JW+FSN 在 2D qubit lattice 上需 \(O(N^{3/2})\) local two-qubit interactions、\(O(\sqrt N)\) depth，而相应 native fermion lattice 为 \(O(N)\)、\(O(1)\)。Theorem 16 将新方案降至 \(O(N)\) gates，但普通网格仍为 \(O(\sqrt N)\) depth；Corollary 11 的 lattice-surgery 口径降至 \(O(1)\)。因此“interaction-count gap 消失、普通 qubit 网格只剩渐近深度差”成立；“容错下优势也消失”只能写成**深度指数/渐近标度差消失**，不能抹去常数、Clifford 总数、surface-code space-time volume 或原生费米硬件与表面码之间的物理实现差异。 |
| 53 / 3 | **PASS，计数必须称 leading-order CNOT 资源** | 高 | Sec. II 给出任意 boustrophedon-to-boustrophedon switch 的 \(C<6N+O(\sqrt N)\)、\(T<6\sqrt N+O(1)\)。Table I 与 Appendix I 给出一个 spinful、second-order Trotter step 的 leading-order CNOT count/depth：Square NN \(21N,4\sqrt{N/2}\)；NNN \(30N,4\sqrt{N/2}\)；Lieb \(19\frac23N,12\sqrt{N/6}\)；Kagome \(24N,12\sqrt{N/6}\)。Fig. 5/正文的 crossover 为 \(5\times5\) 物理方格即 \(N=50\) spin-orbitals 时 count 更低，超过 \(7\times7\) 后 depth 更低。计数采用 hopping/FSWAP = 2 CNOT 的分解、融合前后相邻 hopping 层，并对所有比较共同忽略第一 Trotter step 不能向前吸收的额外成本；所以不是未经限定的精确总门数。 |
| 54 / 4 | **PASS，最优性限定于局域连接渐近模型** | 中 | Sec. III-B、Table II：无辅助 qubit 的 2D local qubit lattice 上，所构造 FFFT 为 \(O(N^{3/2})\) gates、\(O(\sqrt N)\) depth；表中对比 Constantinides et al. 的 \(O(N^{3/2}\log^2N)\)/\(O(\sqrt N\log^2N)\) 和 Givens network 的 \(O(N^2)\)/\(O(N)\)。Introduction、Appendices G/H 将编码切换及 fermion routing 推广至固定 \(d\) 维，深度 \(O(N^{1/d})\)，匹配该局域 routing/light-cone 标度；2D gate scaling 也与同拓扑 native fermion lattice 相同。所谓“渐近最优”只在固定维、局域连接、其门/深度成本模型下成立，不是常数最优、全连接设备最优或带容错 space-time volume 的最优性；比较论文和本结论均主要是理论上界，且本源仍是 v1 预印本。 |

## 建议写回 ledger

- `PASS`: **40–45、47–54**。
- `REFUTE / rewrite-required`: **46**。
- `UNVERIFIED`: 无。
- 强制 caveat：**42、43、45、47–54**；其中 `#50–54` 必须整体标注“arXiv v1、未同行评审、理论构造/资源估算，无完整系统实验”。
