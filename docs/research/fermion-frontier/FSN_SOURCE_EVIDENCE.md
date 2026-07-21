# FSN primary-source evidence ledger

核查日期：2026-07-11

## 直接支持的 FSN 结论

| 来源 | 可直接使用 | 不能直接移植 |
|---|---|---|
| [Kivlichan et al., PRL 120, 110501 (2018)](https://arxiv.org/abs/1711.04789) | 一般 N-spin-orbital electronic-structure Hamiltonian 的 fermionic-swap network：单个 Trotter step 可用 exact `N` depth、`N²/2` 两比特 entangling gates；网络由 odd-even transposition layers 反转 canonical ordering。 | 该结果针对全 pair interaction 的一般电子结构 Hamiltonian；不能直接当作二维 NN Hubbard 的 standard/ladder 有限尺寸 count，也没有当前 Fig.15 的二维 embedding 与首步边界。 |
| [Dynamic-JW arXiv v1, Fig. 5/Fig. 15](https://arxiv.org/abs/2605.12600) | 明确比较 NN square Hubbard 的 dynamic encoding、standard FSN 和 ladder-like FSN；standard 只需 1D NN line，ladder 利用 spin-separated ladder/rung connectivity；作者假设相邻 Trotter steps 的末/首 hopping 可融合。 | 图示策略和 plotted points 没有作为机器可读 finite-size formula 发布；正文没有给 standard/ladder 的完整 event list、exact count/depth 或首步额外字段。 |
| Dynamic-JW Fig. 5 caption | NN square 比较域是 `L=4...10`，qubit layout 为 `L × (2L)`，其中 2L 反映 spin。 | 从图上拟合出的 `16L³-2L(L-1)`、`8L³-2L(L-1)` 等表达式仍是 candidate fits，不是作者声明的公式。 |

## 当前资源模型中的安全口径

1. Kivlichan 的 exact generic FSN 定理保留为“通用 FSN primary-source anchor”，不
   直接填入二维 Hubbard route ledger。
2. standard/ladder 的有限尺寸数值继续标记为 `candidate_fit_to_figure_not_source_formula`，
   只在 Fig. 5 的绘图域输出。
3. 相邻步融合假设可以进入 group-level bookkeeping，但不等于首步已闭账；首步
   count/depth/time 仍必须由 route export 提供。
4. `term_order_cross_route.py` 仍要求 standard/ladder 的 individual-term export；
   当前没有真实 FSN export，因此 unified evidence manifest 不能升级到
   `READY_FOR_BENCHMARK`。
