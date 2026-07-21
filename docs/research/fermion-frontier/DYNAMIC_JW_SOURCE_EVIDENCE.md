# Dynamic-JW primary-source evidence ledger

核查日期：2026-07-11
主源：[Aigner et al., arXiv:2605.12600v1](https://arxiv.org/abs/2605.12600)

## 已直接确认

| 主源位置 | 可支持的结论 | 证据层级 |
|---|---|---|
| Abstract / Sec. III A / Table I | NN square spinful Hubbard 的单个二阶 Trotter step 给出 leading CNOT count `21N`；深度表给出 `4√(N/2)`。 | source-reported leading subtotal |
| Fig. 5 caption | NN/NNN square 使用 `L × (2L)` qubit grid；绘图尺寸为 `L=4...10`，并比较 dynamic encoding、standard FSN、ladder-like FSN。 | source figure domain and topology |
| Fig. 14 caption | 分组级流程是当前 boustrophedon encoding 下的 hopping、density-density、encoding switch、另一半 hopping，随后执行 Strang reverse sequence；相邻边界可融合。 | group-level sequence only |
| Appendix I, NN Hubbard subsection | leading gate bookkeeping 可分为 encoding switch `6.5N`、density-density `N`、hopping `4N`，并由此得到 `21N`。 | source leading decomposition |
| Appendix I, same subsection | CNOT-depth leading term写成 `2N_R`；作者明确说明首个 Trotter step 因无法向前融合而产生的额外 circuit cost 被忽略，且 literature methods 同样处理。 | first-step omission is explicit |
| Definition 7 / Appendix C | `C2D = C↑† C←† CZ C← C↑`；lattice-surgery 实现使该 encoding switch 达到常深度的渐近结论。 | primitive/asymptotic FT evidence |

## 当前不能从主源直接填写

主源没有提供：

1. `H1...H4` 每个 matching 内 individual fermionic term 的排列及其跨路线对应关系；
2. 首个 Trotter step 相对稳态的 exact CNOT count/depth/non-CNOT time；
3. 给定 `L=8, R=100` 的完整 compiled event list、transition timing 或 active layout；
4. 将 leading `21N` 分解为可直接输入首步账本的 exact compiled route 记录。

因此本仓库保留两层状态：Fig. 14 的分组顺序作为 `term_order_contract.json` 的
验证目标；individual-term equality 和首步完整资源仍由
`term_order_cross_route.py`、`first_step_ledger_validator.py` 和统一 evidence
manifest 阻断为 `UNRESOLVED`。任何 synthetic export 只能用于测试 validator，不得
升级为论文结果或硬件 benchmark。

## 对当前模型的影响

- `21N` 仍可作为 dynamic-JW source-leading subtotal；
- 首步字段继续保持 `null`，不能用 `R × steady` 代替完整总量；
- `R=100` 继续是规划输入，而不是主源给出的收敛证书；
- 下一项真实证据必须是 compiler export 或作者补充材料中的机器可读 event list，
  而不是从 Fig. 14 图形反推 individual order。
