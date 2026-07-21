# Native-fermion primary-source evidence ledger

核查日期：2026-07-11

## 三层证据分开保存

| 来源 | 已直接支持 | 仍不能支持 |
|---|---|---|
| [PNAS 2023 proposal](https://pmc.ncbi.nlm.nih.gov/articles/PMC10468619/) | MERGE/SHUTTLE fermionic tunneling primitives、Rydberg interaction gate、可并行化的 fermionic gate protocols；对移动、加热、trap inhomogeneity、echo 等工程问题给出讨论和组件级估计。 | 没有完整 L=8 四-matching compiled export、连续 movement transition table、任意角 hopping/onsite integrated timing、完整空间占用或实机端到端 Hubbard campaign。 |
| [Nature 2026 collisional-gate experiment](https://www.nature.com/articles/s41586-026-10356-3) | ^6Li 双阱中的局部 spin/charge collisional gates；`√SWAP` gate duration `1.125 ms`；最多 20 次连续 gate、64 个 lattice sites 的分析，得到 `99.75(6)%` 平均两体 entangling-gate fidelity；Bell-state coherence 估计超过 10 s。 | 这是 adjacent-atom double-well primitive，带 SPAM/post-selection 口径；没有二维四 matching 的任意角 hopping、onsite density phase、长程移动、回位、并行 route timing 或完整 Hubbard Trotter step。 |
| [arXiv:2604.13160 (2026) global-control proposal](https://arxiv.org/abs/2604.13160) | 提出以全局控制的 tunneling、gradient、interaction 和 control fermion movement 实现 universal fermionic processing；讨论多 control heads、二维扩展和 hybrid analog-digital Fermi-Hubbard。 | 仍是理论/协议 proposal；没有与本任务 `L=8, U/t=8, tT=1, R=100` 对齐的实验 count/depth/time/fidelity 或 compiled event export。 |

## 对模型字段的裁决

1. Nature 的 `99.75(6)%` 和 `1.125 ms` 只能作为局部 primitive evidence，不能填入
   `native_fermions` 的完整 route timing。
2. PNAS 的 move/heating 数值继续作为 component-level planning anchors；它们不是
   inclusive matching transition time，也不是完成项序的下界。
3. 2026 global-control proposal 可进入“新候选架构”参考层，但不能改变当前
   `compiled_exact=false`、首步账本 `UNRESOLVED` 的状态。
4. native route 只有在连续 matching movement、任意目标角、cooling/echo/回位、
   loss/leakage、storage/workspace 和 individual-term export 齐全后，才可进入统一
   evidence manifest 的 `COMPLETE` 分支。
