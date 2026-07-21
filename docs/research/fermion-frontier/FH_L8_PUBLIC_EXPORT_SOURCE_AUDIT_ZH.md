# FH-L8 公开原始导出来源审计

审计日期：2026-07-20。该记录只审阅公开落地页与可见元数据；没有下载工件、安装依赖或执行第三方代码。

## 结论

截至审计日，在所列的 dynamic-JW、FSN 和 native 原始公开来源中，未识别出可直接准入的 FH-L8 五路线机器可读 compiler export。因此结论是受范围约束的 `NO_ADMISSIBLE_PUBLIC_FIVE_ROUTE_EXPORT_SET_IDENTIFIED`，不是“互联网上不存在任何工件”的全局否定。

论文和图示可用于定位算法路线，不能替代逐项事件序列。尤其不能从图或文字手工还原 term order，并把它伪装为编译器导出。

## 已审阅的公开来源

| 路线 | 公开原始来源 | 审计结果 |
| --- | --- | --- |
| dynamic-JW 两条 | arXiv:2605.12600 | 未识别到版本化 FH-L8 逐项 compiler export |
| FSN standard / ladder | arXiv:1711.04789 | 给出通用 FSN 与 Hubbard 构造；未识别到目标 workload 的逐项 export |
| native fermions | PNAS 120 e2304294120 / PMC10468619 | 正文声明研究数据含于主文；未识别到版本化 FH-L8 逐项 compiler export |
| native gate 背景 | PMC13083236 | 属于门级背景，非 FH-L8 五路线导出 |

各源的 URL、适用路线及机器可读导出状态由 `fh_l8_public_export_source_audit_result.json` 固定；验证器不发起网络请求。

## 最小对外采集请求

每条路线都需要一个可公开定位、不可变版本的原始导出，连同 SHA-256、发布标签或 source commit、FH-L8 参数与路线来源、每个 Trotter step 的完整有序 individual-term event list，以及 compiler 名称/版本、配置摘要和环境锁摘要。只有五条路线全部满足这些条件，才允许由 `UNRESOLVED_EXTERNAL_EXPORT_REQUIRED` 转为可比较证据。

在此之前，FH-L8 的跨路线序列结论保持未决，且不得用合成、手写或图示重建的序列填补。
