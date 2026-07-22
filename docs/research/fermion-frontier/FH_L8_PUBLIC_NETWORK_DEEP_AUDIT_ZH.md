# FH-L8 公开网络深度取证结论

审计日期：2026-07-21。公开网络路径已在列明范围内完成深检，但没有找到能通过现有 intake 的 FH-L8 五路线原始 compiler export。该结论是 `PUBLIC_NETWORK_PATH_EXHAUSTED_WITHIN_NAMED_SCOPE`，不声称作者私有存档或未来发布中不存在工件。

## 审计结果

| 路线 | 新发现 | 准入判决 |
| --- | --- | --- |
| dynamic-JW 两条 | arXiv v1、TeX source 入口及 Innsbruck 发布记录；未发现作者仓库或 Zenodo 数据集 | 仍需外部原始 export |
| standard / ladder FSN | OpenFermion v1.7.1 的通用 term-order helper；OpenFermion-Cirq 的 FSN ansatz 与四量子位示例 | 方法代码，不是 L8 两路线原始 export |
| native fermions | 2023 论文正文数据；2026 collisional-gate 图表 source data；另有 2025 光晶格 FH 复现仓库/Zenodo | 前两者仅背景/实验图数据；后者属于不同论文和工作负载 |

特别值得保留的负结论是：公开代码“能够生成某类线路”与“作者公开了本 benchmark 的原始编译导出”是两种证据。前者不能提供原始配置、路线身份、环境锁或工件保管链，因此不能跨越 intake。

本轮没有下载或执行第三方代码，没有安装依赖，也没有从论文、TeX 或图表重建序列。候选 URL、分类和拒收理由固定在 `fh_l8_public_network_deep_audit_result.json`，验证器只做离线结构检查。

## 后继方向

在无法外部联络、公开网络路径也没有目标工件的条件下，继续增加 export 模板不会带来新证据。下一条独立且可推进的路线是 `PIVOT_TO_INDEPENDENT_REFERENCE_CERTIFICATION`：构造与 compiler export 无关、可独立检查的 FH-L8 observable reference/bound，使 benchmark 的 reference 组件先取得实质进展，同时保留五路线 term-order 为 `UNRESOLVED`。
