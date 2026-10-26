# Harness² 借鉴：本地技能候选脚本检查

日期：2026-10-26。状态：静态检查工具已实现；不代表技能运行或收益通过。

用户明确要求继续落地下一个可实施目标。本轮选择先前已提出的候选可用性检查，交付一个可直接调用、只读、不执行候选代码的命令。停止条件为明确的必需脚本缺失与Python编译问题能被检出、教学示例不被误判为强制依赖、实际文件保持不变。

## 实现与取舍

- 新入口：`scripts/eval/workflow_candidate_check.py --skill PATH`。
- `--required-script`可重复，用于明确声明真实必需的helper；缺失判`FAIL`。
- 从文字发现的缺失脚本引用标为`NEEDS_REVIEW`，动态引用和其他语言未检查项也明确保留。
- 遍历候选自身`scripts/`下Python文件，只编译，不执行/import、不写pyc；包括未被正文引用的Python helper。
- 报告消费文件哈希、Python版本、引用与问题；显式拒绝路径越界和符号链接，复用上一增量的有界文件读取函数。
- 不修改现有Rust技能风险lint、安装流程或MCP接口。没有复制上游代码或新增依赖。

已有`crates/bridge/src/skills.rs::lint_body`主要检查危险命令、凭据路径等文本风险；本轮补的是文件依赖与Python编译。不同客户端的frontmatter、技能发现、触发和实际加载行为保持未验，不能照搬Harness²“技能名必须在常驻提示中”的前提。

[操作说明](../operations/WORKFLOW_CANDIDATE_CHECK.md)明确PASS_SCOPED、NEEDS_REVIEW、FAIL和INVALID_INPUT的语义与退出码。静态通过不建立执行权限、安全性或任务价值。

## 验证与发现

- 先写10项测试，确认模块缺失时失败；实现后通过。
- 对现有skill-creator目录只读试用，发现文档中的`rotate_pdf.py`教学示例被误判为必需依赖。保留该失败观察，增加反例，并区分显式必需依赖与文本引用。新增断言先失败，修正后通过。
- 最终11项候选检查测试通过，覆盖缺件、未引用Python语法错误、代码不执行/不import、不写pyc、路径边界、动态引用、其他语言、教学示例、退出码和只读性。
- 共享文件读取函数的调用没有修改原实现；上一增量18项经验对比测试全部通过。
- 实际skill-creator目录最终返回`NEEDS_REVIEW`：3个Python helper编译通过，示例引用需要人工确认。检查前后SKILL.md及3个helper的SHA-256不变。未把这个结果描述为上游技能不可用。
- 本机私有回执：`/home/pallasting/.agent-bridge-secure/research/harness2-candidate-check-20261026/existing-skill-review.json`。

未安装或运行技能，未调用模型，未部署AB、写生产记忆或触发CI。本轮检查不包含真实任务收益实验，也不要求其他会话改用此命令。

## 收口

当前交付限本地候选脚本静态检查。普通维护中需要修改技能时可直接使用；通过后返回原交付，必要的行为与安全验收仍按原要求执行。没有候选变更需求时不批量扫描技能、不制造后续任务，不自动增加递归执行、匿名评审或安装阶段。
