# 情境记忆首轮离线验证

日期：2026-09-08。范围：用户认可 Metis 研究建议后的最小落地。

## 已完成的增量

长期方向、证据边界及后续触发条件已写入 [情境记忆计划](../../design/CONTEXTUAL-MEMORY-EVOLUTION.md)，并从 [当前路线图](../../ACTIVE-PRODUCT-ROADMAP.md) 链接。

本轮复用 `portfolio_continuity_eval.py` 的既有格式和评分逻辑，新增 12 个合成案例、6 组成对情境及对应手工参考标签。没有新增 scorer、在线策略、数据表、经验收集器、模型训练或调用。

| 组合 | 改变的条件 | 必须保住的区别 |
| --- | --- | --- |
| owner detail / collaborator summary | 明确给定的对象与细节要求 | 相关且真实的内容仍可能不适合当前输出；允许的摘要不能一起被压掉 |
| relevant / unrelated task | 当前请求是否需要该组经历 | 无关时不注入历史；仍正常回答当前问题 |
| before / after update | 事实有效时间 | 当前承诺转到新依据，过期、未来与 superseded 依据不能冒充当前 |
| project A / B | 同名承诺所属项目 | 同样的 claim 必须绑定对应项目的证据 |
| current action / retrospective | 当前执行或历史回顾 | 保留撤销历史，不复活旧计划；历史不能替代当前承诺 |
| inference / external verification | 尚属推断或已有外部验证 | 推断标签支持其归属，验证事实需要外部证据；允许补充此前推断的历史 |

每组的证据目录相同。将左侧参考输出原样移到右侧、只更改 case 标识时，六组都被评分器拒绝。这证明契约确实表达了不同情境下的不同要求；不证明模型已经能自主做出这种选择。

## 验证结果

- 新增 Python 契约测试：**16 passed**。
- 既有 `verify-portfolio-continuity-eval.sh`：**PASS**，已将新契约测试接到这个入口末尾；原有检查和新增 16 项一并通过，评分器代码保持不变。
- 合成参考标签：**12/12** 通过；它是测试 oracle，不是 AB 或 Metis 的模型输出。
- 对抗检查包括：不确定措辞夹带禁止内容、其他项目的有效证据、过期/被替代/未来证据、当前承诺缺失、旧计划复活、推断升级、全部拒答、过度抑制、未知字段。
- 真实 bootstrap 的隔离 store 回归：**2 passed / 0 failed / 0 ignored**，2,194 项未选中；两项测试实际执行 8 次 `SessionBootstrapTool` 调用及 2 次保留历史的语义搜索，测试耗时 6.95 秒。

Rust 回归保持同一个临时 store，分别改变项目 A/B、定向 query/无 query、Warp/Claude 输出模式。在单条结果预算下故意让全局无关记忆更贴近查询，检查当前项目 handoff 仍获得其保证的优先位置；全局、其他项目、stale handoff 不占该位置。相关反馈保留，定向请求省略通用反馈前言；历史与全局记录仍可搜索。断言限定在有承诺的 section/优先位，不把“不给优先位”误写成“任何位置都不能出现”。

本次没有发现需要修改生产策略的缺陷；改动仅扩展既有测试。构建因缓存指纹差异重编依赖，单 job 构建耗时约 7 分钟；有既存警告但无编译错误。编译时间与测试执行时间都不是用户任务性能测量。

`git diff --check` 通过。整份 `tests.rs` 的 rustfmt 检查仍报告 97 处既存格式差异；将格式差异与本轮修改区间对照，交集为 0。本轮未顺带重排无关测试。

独立审阅确认了历史证据和情境契约的解释边界。审阅提出的“验证后仍允许说明此前推断沿革”已补入 optional history，并增加正反测试。

## 复现

在包含本次更改的仓库根目录运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p 'test_contextual_memory_contract.py' -v

bash scripts/verify-portfolio-continuity-eval.sh

CARGO_BUILD_JOBS=1 \
CARGO_TARGET_DIR=/var/tmp/cargo-target-attempt-final-audit \
  cargo test --locked -p ab-bridge --lib session_bootstrap_contextual_ \
    -- --test-threads=1
```

Rust 的 target 必须在磁盘上，路径可改为本机磁盘缓存。使用测试名过滤器，不使用未限定模块路径的 `--exact`，并确认实际执行数大于 0。

## 结论的范围

本轮完成的是逐步改善记忆所需的评估与回归基础。案例中对象、允许的输出和 claim 标签均由测试明确给定，尚未测量自然语言答案的恰当性、学习效果或真实任务收益。对象组也改变了细节要求，目的组改变了请求意图；这些不是各因素独立作用的因果测量。

合成参考中的 `context_tokens=0`、`latency_ms=0` 是未测量占位，**不是零成本**。既有 scorer 会将字段齐全标为 `cost_diagnostics_complete=true`；本轮不将该字段作为测量证据。此报告的成本状态是 `cost_metrics_measured=false`，真实 token 成本、延迟和用户时间均未知。

本轮没有完整 30 天自然事件分母或逐次用户成本，也没有重新采集普通 R1 正向样本。08-10 无关面板问题已修复，历史 portfolio digest `NO_ADVANCE` 继续有效。下一步在普通任务出现有意义负例时，先正确完成任务，再将纠正和独立结果用于同模型、同预算的最小比较；无需专门制造事件填满计数器。
