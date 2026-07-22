# FH-L8 外部来源追踪与采集包

该包把五路线的可验证来源路径与采集请求固定在 `fh_l8_external_source_acquisition_plan.json`。它记录的是截至 2026-07-21 的、范围受限的公开检索结论，不是对互联网或作者私有工件的全局否定。

## 路线结论与优先级

| 优先级 | 路线 | 已识别公开路径 | 分类 | 下一动作 |
| --- | --- | --- | --- | --- |
| 1 | 两条 dynamic-JW | arXiv:2605.12600v1、Innsbruck 发布页 | 论文/TeX，缺原始导出 | 向该预印本团队索取两份互不复用的 FH-L8 原始 export |
| 2 | standard 与 ladder FSN | arXiv:1711.04789；OpenFermion v1.7.1 | 有公开通用代码，缺目标 export | 索取各路线 release-pinned FH-L8 export；不得由本项目运行库重建 |
| 3 | native fermions | PNAS/PMC10468619；arXiv:2303.06985 | 主文数据/门图，缺事件 export | 向论文团队索取本工作负载的原始事件或编译导出 |

OpenFermion 的公开函数与 FSN 论文相容，且可以给出 Hamiltonian 项的模拟顺序；它仍不是本项目目标工作负载的原始、版本化导出，故不能直接准入。dynamic-JW 的 arXiv 记录可定位版本、提交团队与 TeX，但也没有列出补充导出。

## 可直接转发的最小请求

请为指定路线提供一个不可变版本的 FH-L8 (`U/t=8`, `tT=1`, `L=8`, `R=100`) 原始 JSON compiler export，并附：HTTPS 原始来源、release/tag 或 commit、原始 SHA-256、`PRIMARY_EXTERNAL_RAW_EXPORT` 保管声明、compiler 名称/版本、compiler 配置 SHA-256、环境锁 SHA-256，以及每一 Trotter step 完整有序的 individual-term event list。

收到后只需通过现有 [接收器](/Data/CascadeProjects/agent-bridge/docs/research/fermion-frontier/fh_l8_external_evidence_intake.py)。接收器未返回全部路线 `ADMITTED` 前，不会启动跨路线比较。
