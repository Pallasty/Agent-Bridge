# FH-L8 D18-C：fresh-exclusive packed-q3 有界消费者 V2

D18-C V2 已在冻结的 512 MiB cgroup 包络内，从 committed packed q3 的前 4,096 条唯一有序记录完成一次 q3→q4 **有界部分** action，并由第二遍 naive replay 与外部 scratch checker 复核。结果状态为
`VERIFIED_D18C_FRESH_EXCLUSIVE_PACKED_Q3_BOUNDED_4096_PREFLIGHT`。

这里的正结论只覆盖这 4,096 条 q3 source rows、8,192 次冻结 `_reduced_column` 调用、对应 spill/merge 和部分 target。它没有物化完整 q4，部分 target 禁止作为 q4、contraction、q5 或任何下游数值运算的输入，也没有授权完整 53-shard 执行。

## V1 零动作失败与废弃

本报告中的 V1/V2 是两次冻结尝试的谱系标签，不是 JSON schema 版本；V2 contract 的固定 ID 仍为
`FH-L8-INDEPENDENT-REFERENCE-D18-C-FRESH-CONSUMER-V1`。

第一次尝试冻结了 implementation commit
`732643eb856da31e68541df603ed88481a9063cd`，随后以
`34006de5f3548432c7f6e24e1fd3527fab49cb53` 添加 contract。contract checker 在 launcher 和任何 scientific action 之前读取 hash-pinned legacy D18 result；通用 strict-JSON reader 遇到该历史文件的
`elapsed_seconds: 66.543` 后按设计拒绝浮点，返回：

```text
source authority documents rejected: floating-point JSON number forbidden: 66.543
```

因此 V1：

- 没有启动 runner；
- 没有建立 action scratch；
- `scientific_action_calls=0`，q3 rows acted 为 0；
- 没有 C3/result commit，也没有可采信的执行结果。

V1 两提交只保留为失败审计记录，现已废弃；不得把它们解释为 negative scientific result，也不得与 V2 implementation/contract 混用。

V2 没有放宽 D18-C 主 JSON、contract 或 result 的整数-only 规则。它只为 exact-SHA-pinned legacy D18 observation 增加一个窄 reader：先校验完整文件 SHA-256
`7fa505485fc718db39d9918ec459094f3766f014fd2ddee7d108f01fae4842c4`，仍拒绝 duplicate keys 与 `NaN`/`Infinity`，并把有限小数 token 保留为 opaque string。该历史耗时字段不进入任何采信比较、算术、receipt 或 authority。

## V2 三提交 chronology

V2 从 evidence baseline `26c49b6e7bcddc22a1fc88f3743befa1b6de4446` 重新开始，不以 V1 commits 为父提交：

| 阶段 | Commit | 唯一新增内容 | 执行边界 |
| --- | --- | --- | --- |
| C1 implementation freeze | `8cf944e42fd9a981cd78f584885a5c525dd2abd9` | runner、checker、launcher、test 四文件 | contract/result 均不存在，零 action |
| C2 authorization freeze | `9e4266600439143d7fdaaf76331dc9780cecd55c` | `fh_l8_fresh_consumer_d18c_contract.json` | 只授权 4,096 rows / 8,192 kernel evaluations；完整 53 shards 仍为 false |
| C3 result freeze | `10d56da28318d622e791f5f5d39932d7a4a39e11` | `fh_l8_fresh_consumer_d18c_result.json` | 只记录已完成的 bounded partial action |

三者构成严格父子链
`26c49b6e → 8cf944e4 → 9e426660 → 10d56da2`；C2 的 contract checker stdout 也记录 C1 只有一个父提交、C2 前 result 不存在。

## Source 全量准入与 action 基数

runner 在 action 前完整读取并校验 packed q3，而不是只验证将要消费的前缀：

| 项目 | 已验证值 |
| --- | ---: |
| 全量 source records | 213,099 |
| record bytes | 32 |
| payload bytes | 6,819,168 |
| payload SHA-256 | `db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231` |
| rank permutation | complete / valid |
| first-4096 raw SHA-256 | `77bbed3b7a5244bf789fd3652b351d59d1045db238637f4ddc6cfa146ab41e33` |
| first-4096 representative/amplitude projection SHA-256 | `99d1ea17d1dedb08bcb65b5de5875088b96c638e1bf6d42b8b9ada7f20da7c31` |

action 只消费前 4,096 条唯一、严格递增记录。第一遍执行 4,096 次 spill kernel evaluation，第二遍 naive replay 再执行 4,096 次，总计 8,192 次 `_reduced_column` 调用；其余 209,003 条 source records 没有进入 action。source 在 action 后按相同 device/inode/mode/size/timestamps 和完整 SHA-256 重新校验。

## 四份 kernel snapshot

scientific context 在 action 前一次性读取四份冻结 bytes，并绑定 working file、Git blob、mode、size 与 SHA-256：

| Snapshot | SHA-256 |
| --- | --- |
| `fh_l8_symmetry_orbit_quotient_d5_checker.py` | `681bc63fedce8b71cfb536c66d321467bc8f01cb5947bee59b4291e2ac51a022` |
| `fh_l8_symmetry_orbit_quotient_d5_contract.json` | `1ebd1d38c0c40ca9617f86e09c86d528196260dd6b6b6692c34dacfe7a28d392` |
| `fh_l8_scalar_supremum_d4_checker.py` | `86692e68cee1475d3cee2dbd0e866f68d5c5514ff37268c601819bd8f4ed48f2` |
| `hubbard_strang_commutator_checker.py` | `e3144590c0e00bb2bd69bc50b1bdf3d7d6c3043c8697d5050202404590138fa7` |

执行上下文由同一组 pre-action byte snapshots 编译或解析；action 期间没有从 worktree 追加加载传递模块或 contract。action 后又逐文件复核同一 custody 元数据和摘要。

## Spill、部分 target 与语义等价

| 项目 | 结果 |
| --- | ---: |
| partitions | 256 |
| spill records | 868,786 |
| spill bytes | 27,801,152 |
| reduced columns | 868,786 |
| projected-zero outputs | 22 |
| zero coefficients dropped | 0 |
| spill manifest SHA-256 | `0dec36b9e678ff21ee559c02d86c5fab160fa18e35148d44d00482cfc1eff827` |
| bounded target records | 424,682 |
| bounded target bytes | 13,589,824 |
| bounded target SHA-256 | `8b43b76f1e7a45f12e220905bcba41dc7cfef9fce66f0257cb3c9dff9623fa5f` |

on-disk target 顺序是 `partition_sha256_byte_then_target_u128`。external checker 逐分区验证严格 target 顺序和 selector，再用最多 256-way heap 对这些已排序 runs 做有界全局归并。得到的 globally sorted semantic SHA-256 为
`da049d945738630c66b8118ec58627a09910887e7263f91e4b08417ef7bafb34`，与第二遍 naive replay 的独立聚合摘要完全相同。

legacy D18 的 424,682 records、13,589,824 bytes、target digest 以及 spill/reduced/projected-zero counts 也全部匹配，但它只作为
`PREREGISTERED_NON_AUTHORITATIVE_REPRODUCIBILITY_GUARD`；`authority=false`。这个匹配不能恢复 legacy D18、D12/D13 或 D16-W 的数值权威。

naive replay 独立检查的是 consumer aggregation、manifest-only merge 与 publication；它仍调用同一组冻结 scientific kernel，不能被描述成对 kernel 数学正确性的独立实现验证。

## Scratch 与资源证据

官方 scratch 位于
`/Data/CascadeProjects/.ab-experiments/fh-l8-d18c-official-v2-20260722`。它是 fresh-exclusive `f2fs` 目录，root mode 为 `0700`、lock mode 为 `0600`。runner receipt 前有 260 个 regular files，加入 terminal receipt 后为 261；launcher 再加入 runner stdout、contract-checker stdout 和 launcher receipt，external checker 看到的最终 exact file set 为 264。

| 资源指标 | 观测值 |
| --- | ---: |
| `memory.max` | 536,870,912 bytes |
| `memory.high` | 402,653,184 bytes |
| `memory.swap.max` / action 后 swap current | 0 / 0 |
| 初始 `memory.current` | 17,100,800 bytes |
| action 后 `memory.current` | 156,459,008 bytes |
| 初始 cgroup peak | 19,587,072 bytes |
| runner action 后 / systemd post-exit peak | 224,747,520 bytes |
| process max RSS | 193,392,640 bytes |
| runner pre-publication elapsed | 57,941,070,334 ns |
| `high` / `max` / `oom` / `oom_kill` deltas | 0 / 0 / 0 / 0 |

launcher 记录 runner exit code 0、stderr 0 bytes，并在捕获 runner terminal receipt 后停止 transient unit。停止后 unit 为 `inactive/dead`，pre-stop 和 post-stop `ControlGroup` 均为空；因此只保留 runner 观测到的 exact unit cgroup path，不虚构一个 post-exit cgroup path。
systemd 的 post-exit `MemoryCurrent` 返回 `[not set]`；空 `ControlGroup` 只说明该 cgroup
已经移除，不能据此补造精确的 post-exit memory current 或路径。

关键 receipt identities 为：

- terminal receipt SHA-256：
  `ae2867319f8e7af8a6a691aa85ca68c6ff0960e04b03aadd1ef3da42a67a9905`；
- launcher receipt SHA-256：
  `61e6799f5d7f4cee6e34bd32b4acdedc4aa7b2548fafb018f45d337bbf46e973`；
- captured runner stdout SHA-256：
  `081eda68d3cc4e96add2dc94187f108967490a9e0c6fec313774a50352e018be`；
- captured contract-checker stdout SHA-256：
  `8614becdd1d4fe61c4ae2e4ca9c2bd42fff0ddb6181c7a7d597dd1b42e36c01d`。

## Static 与 external checker 的不同权限

只运行 committed result 的 static 检查返回
`D18C_COMMITTED_RESULT_SCHEMA_AND_GIT_PROVENANCE_ONLY`。它确认 result schema、三提交 chronology、Git blobs、source/kernel pins 和 authority ceiling，但明确给出：

- `external_scratch_verified=false`；
- `executed_authority_verified=false`；
- `scientific_outcome_verified=false`。

因此 committed result 中的 `verified:true` 不能脱离 external terminal evidence 单独解释为执行复核。

向同一冻结 checker 提供上述 scratch 后，external 模式还会重验 terminal/launcher receipts、captured stdout、spill manifest、所有 256 partitions、部分 target、global semantic digest、scratch custody 和 exact 264-file set。该模式返回
`VERIFIED_D18C_RESULT_AND_EXTERNAL_TERMINAL_EVIDENCE` 与
`external_scratch_verified=true`。这个 external 结论才是本报告引用的完整 bounded-run 证据；scratch 若遗失，未来只能恢复 static provenance 结论。
该 external scratch 当前占用 41,465,952 bytes，未纳入 Git 且仍是可变的本地证据；
它一旦遗失或发生漂移，C3 不再足以恢复 executed/scientific verification。

launcher receipt 的 `command_sha256` 还绑定官方执行工作树
`/Data/CascadeProjects/.ab-worktrees/agent-bridge-fh-l8-d18c-fresh-consumer-v2-20260722`
中的绝对 runner、contract 和 capture 路径。因而把 checker 与同一 scratch 移到另一个
worktree 后，会按设计返回 `launcher command digest drift`；这说明 external evidence
具有 execution-custody location binding，并非结果失效。完整 external 复核必须保留这条
原始 custody 路径，或在未来先冻结独立的 evidence-transfer/verifier contract；当前集成
worktree 和普通远端 clone 只能独立恢复 static Git/schema provenance，不能改写 receipt
来伪造可移植性。

## Authority ceiling

本门新增的正 authority 只有：

- `bounded_4096_preflight_executed=true`；
- `partial_q3_to_q4_action_executed=true`。

以下仍全部为 false：完整 q4 materialization、bounded output 作为 q4 operand、完整 53-shard authorization/execution、D12/D13 numeric authority、D16-W full-H numeric authority、q5、degree-six remainder、two-step cumulative error、full-R100 error、physical reference、hardware result、quantum advantage 与 READY eligibility。

特别地，`bounded-q4-partial.bin` 只是前 4,096 source rows 的部分和。禁止把它复制、重命名或包装成完整 q4，也禁止送入 contraction、q5 或任何下游数值结论。

## 下一 gate

下一 gate 是
`CLEAN_BOUNDED_PREFLIGHT_REVIEW_AND_FULL_53_SHARD_AUTHORIZATION_DECISION`。

这是一次 review/authorization decision，不是现成的 full-run 权限。进入下一门前至少要：

1. 保留并可重放当前 external scratch 及其四个 receipt/captured-output identities；
2. 审核 bounded action 的 source、snapshot、语义摘要和资源证据；
3. 为完整 53 shards 单独冻结实现与 contract，重新规定全量 spill/merge、恢复、资源和 terminal publication 边界；
4. 明确禁止复用本门 partial target 作为完整 q4 输入。

在新的授权提交出现之前，不得启动完整 53-shard action。
