# Harness² 借鉴：执行差异经验审阅

日期：2026-10-26。状态：代码与离线验证完成；不代表实际任务收益已验证。

## 目标与范围

用户明确要求“将 harness2 可实施的内容落地实施”。本次选择一个可直接使用的增量：让现有 Experience Object 的经验判断能关联实际修改文件与执行记录，并在证据不足时不生成可晋升的结论。

它回应前轮调查暴露的问题：报告被接受、检查通过和局部修改完成，不足以证明用户交付已改善。这里检查执行对比的基本依据；不从数值变化自动判断目标漂移。

复用 `agent_bridge.experience.v0`，增加可选 `execution_contrast` 附件。现有经验、Rust CLI、存储模式与运行策略不变；不复制上游代码、安装依赖或引入递归执行器。此次授权限于离线实现，不重新开放冻结的产品或采集目标。

## 已实现

入口：[workflow_experience_contrast.py](../../scripts/eval/workflow_experience_contrast.py)。
完整操作说明与示例：[WORKFLOW_EXPERIENCE_CONTRAST](../operations/WORKFLOW_EXPERIENCE_CONTRAST.md)。

- 将组件修改描述绑定到实际 before/after 文件哈希；将 baseline/candidate 绑定到运行记录及观测指标。
- 比较声明的任务、输入摘要、模型和环境；输出原始指标差值，不用一条模型填写的 evidence 字符串替代检查。
- 明确保留 `helped`、`hurt`、`no_observed_effect`、`confounded`、`insufficient_evidence`。
- 单对执行、多组件同时修改、条件不同、指标改善与退化混杂时不作单一修改归因。
- 失败和未运行记录仍留在本次提交的样本计数中；缺指标不当成零，成本不全不当成免费。
- 核验哈希、拒绝重复运行ID/相同文件冒充多次支持、路径逃逸、非有限数字和歧义JSON。
- 只打印审阅结果，不保存/晋升经验或改变权限。`REVIEW_LESSON`只是人工复核入口；其余有效结果为`NO_ENTRY`。有效审阅退出0，输入损坏退出2。

方法借鉴上游固定版本 `1cfe254e8d25b15f37048c3730134686abe60335`
的 [experience 提示逻辑](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/prompts.py#L1105)。实现独立编写，无上游代码复制。

## 验证

- 先建立测试并确认缺失模块无法运行；首轮测试助手方法名与 unittest 冲突，改名后13项通过。
- 增补数值边界时，超大整数触发未捕获溢出；修复为结构化拒绝，并检查累计成本溢出。最终 **18项测试通过**，覆盖正负结果、无效果、混杂、缺证据、篡改、重复、退出码及只读性。
- 实际执行文档命令：一个明确标为合成的示例返回 `helped / REVIEW_LESSON`；两个既有经验fixture均返回 `insufficient_evidence / NO_ENTRY`，原因是没有绑定的执行对比。历史正文未改，不否定其原有验收。
- 三次命令输入执行前后哈希一致。运行回执与输出保留在本机私有目录 `/home/pallasting/.agent-bridge-secure/research/harness2-contrast-implementation-20261026/`。
- 文档链接与Git差异检查；无需Rust编译、模型调用、MCP重连或AB重新部署。未触发CI，未写生产记忆。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p test_workflow_experience_contrast.py
```

## 解释限制与收口

“两个配对”只是复核最低要求，不能证明统计显著性。条件、指标、组件划分及运行记录由调用方提供，哈希不认证测量真实性；改ID、隐瞒尝试或隐藏其他修改仍需审阅识别。成本单列，不因某个指标改善就声称净收益。

`causal_effect_proven=false`、`runtime_influence_allowed=false`始终保留。此工具不认证独立任务验收、完整尝试分母或迁移效果，不产生自动学习/自我改写权限。

本增量在命令可用、反例检查通过、现有fixture兼容后收口。后续普通任务已有可比执行证据时即可使用；不为填满样本额外运行任务，不自动追加候选校验平台、匿名评审服务或递归优化阶段。
