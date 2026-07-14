# BioCortex × Agent-Bridge Track B strict-review source pack

Date: 2026-07-14

Frozen source parent: `ddebacba20146a90546db9e4ea4bd2795b9ecc1a`

Decision: `SOURCE_STRICT_REVIEW_IMPLEMENTED_NOT_LIVE_BOUND`

## 技术摘要

本单元把 Track B 的两个第二波公开节点实现为可冻结源码：
`truth_inputs.strict_case_algorithm_sha256` 与
`review_and_blinding.review_receipt_schema_sha256`。严格判定粒度固定为
`case_id × opaque answer_id`；每行必须同时通过三个独立的确定性 truth
gate（仅 answer case 适用）以及两个不同 reviewer slot 的逐项规则，才得到
`strict_rule_pass=true`。两个评审之间不平均、不择优、不互相救援；agreement
只输出为诊断。case sampling weight 也不在这里应用，避免重复加权。

同时，本单元定义一条 provider-neutral 的单次盲评 receipt 形状，用精确字节
SHA-256 串联 command、stdin request、raw response sink 与 populated review，
并绑定 packet、instruction、reviewer slot、roster、conflict manifest、执行环境、
writer、时间及资源记录。这里的 raw response 特指 reviewer 写入私有 response
sink 的规范 review 文件字节，不包括 CLI stdout、stderr 或执行日志。

结论边界同样明确：**schema 不是 receipt；通过合成输入得到的
`strict_rule_pass` 不是 score claim。** 本单元没有真实 reviewer invocation、
runtime truth-gate producer、来源溯源、custody proof、unblind 或 scoring
authority，也没有创建 contract-scoped O_EXCL score claim。结果状态固定为
`VALIDATION_ONLY_NOT_SCORE_CLAIM`，live ledger 与 admission packet 保持不变。

## 范围与定义

| 对象 | 本单元的严格定义 | 本单元不声称 |
|---|---|---|
| strict-case 行 | 一条 `case_id × opaque answer_id` 记录 | condition 级、case 平均分或整 trial 分数 |
| review | 一个完整 `trial × reviewer_slot` 的盲评对象 | reviewer 身份、独立性或实际执行的证明 |
| review receipt schema | 一次零重试 invocation 的封闭、定界记录结构 | receipt 实例、provider 签名、custody 或执行事实 |
| deterministic truth gates | answer 行上的 `authority_exists`、`all_gold_recalled`、`current_referent_correct` 三个独立布尔输入 | 这些布尔值的生产者、依据字节或 provenance 已验证 |
| strict pass | 三个 truth gates 与两个 reviewer rule pass 的逻辑 AND | 可发布 score、胜负、效果量或实跑准入 |
| agreement | 两评审字段级相等的分子/分母 | 通过阈值、多数票或失败救援机制 |
| synthetic closure | 对结构、连接、真值表与失败路径的可重复机制验证 | 真实数据质量、模型效果或运行时安全性 |

“opaque answer” 保持盲态身份：严格输出可以包含 case/answer handle、失败规则、
计数与输入承诺，但不得包含 condition ID、condition mapping、condition weight、
blind map 或 reviewer preference。这样可以在解盲之前判定完整性和严格失败，
而不把条件归属泄漏进公开源码路径。

本报告没有增加流程图。该单元的核心风险是精确粒度、字段覆盖、哈希连接和
authority 边界；下列真值表与审计字段比概念性流程图更能暴露漏连、错连和
越权解释。

## 方法

本单元从冻结 dependency graph、live-binding ledger、real-run admission、
foundational schema pack 与 identity-composition pack 推导两个直接后继。两者
均为 `INDEPENDENT_PUBLIC`、`PRE_OUTPUT_ADMISSION` 源码节点，且没有远端副作用。

- `review_and_blinding.review_receipt_schema_sha256` 只直接依赖已冻结的
  review-command schema 与 populated-review schema。
- `truth_inputs.strict_case_algorithm_sha256` 只直接依赖 populated-review
  schema 与 truth-manifest schema。
- receipt schema 不是 strict-case algorithm 的伪造前置依赖；真实 receipt
  验证尚未接入算法，输出也必须如实标记 `review_receipts_verified=false`。

本单元两个 source artifact 的冻结字节为：

| binding | repo path | SHA-256 |
|---|---|---|
| `review_and_blinding.review_receipt_schema_sha256` | `docs/design/fixtures/biocortex-ab-track-b-review-receipt-schema-v0.json` | `f8af1331ae134be0f09a5e546b2d67e0db8ebfabb2177dc14a376bac773f463c` |
| `truth_inputs.strict_case_algorithm_sha256` | `scripts/eval/biocortex_ab_track_b_strict_case_v0.py` | `816c00eaff6c7e9df6ecca849e8c01ab8dbfe8a80834b37612d89f0a4ffa68b2` |

推导与组成检查固定引用以下证据字节：

| 证据 | SHA-256 |
|---|---|
| artifact dependency graph | `8f618659cb90cc311ef79aafa3fc536bacc3f428f82291998174a0e374d993af` |
| live-binding ledger | `764f063fefe0e516547f9bd1e71417242daf292d57e480ae39b73df8bcda341e` |
| real-run admission | `1508c0c990ccf9ce26fa0eb524194bb587816cc78d4546236c8d9c00dd3b306e` |
| identity-composition source manifest | `c1a6c5a6c83d61f92d35948432b139749d19d5828f68a7fc2473859bba21a7e9` |
| identity-composition synthetic fixture | `094a7343543be2a9b32fc996dc3e7006bc9d02f87f8cc9bdd269ef9fb61a341a` |
| review-command schema | `40df0e39f36df01d414487c496cf09b5ffbed89cafc540dc89e6e57bea4466f5` |
| populated-review schema | `2745cd373d4f99cdd4bb3d0bc9d9087966adb3a9d0594749cb1150b90d1e9422` |
| truth-manifest schema | `520070d1eb4852fd2a005d63b3d087769b3240902289ff5c44f11c109bd1cde6` |
| truth-referent schema | `5da057e70675cbd259e0d1beb98039d2eee8589c73aa910f92f90cb0374545a8` |

实现采用三层验证：

1. 字节层：只接受 canonical UTF-8 JSON，拒绝 BOM、重复 key、NaN/Infinity、
   非规范字节、漂移的冻结 schema hash 与超限输入；CLI 的 `exact_files`
   模式按外部文件原始字节计算承诺。
2. 组成层：要求 truth、两份 review 与 truth-gate 输入在 trial、contract、
   blind packet、truth manifest、referent schema、review instruction、case 顺序、
   answer 顺序及 score-rubric 覆盖上精确连接；两个 reviewer slot 必须不同。
3. 决策层：先按四象限校验 response/abstention 语义，再逐 reviewer 应用严格
   规则，最后与独立 deterministic truth gates 做逐行逻辑 AND。

对象 API 的 `synthetic_object` 模式只服务于仓库内合成闭环；它不能冒充对外部
字节的校验。CLI 的 `exact_files` 模式虽然校验真实文件字节，仍不验证这些文件
的 custody、producer 或 authority。

## 关键发现与严格语义

### 1. 判定粒度与组合规则

严格规则作用于每个 `case_id × answer_id`，不是先汇总 claim、answer 或 reviewer
再比较。每行的逻辑为：

```text
strict_rule_pass =
    deterministic_truth_gate_pass
    AND reviewer_slot_1_rule_pass
    AND reviewer_slot_2_rule_pass
```

answer case 的 `deterministic_truth_gate_pass` 又是三项独立事实的 AND：

```text
authority_exists
AND all_gold_recalled
AND current_referent_correct
```

abstention case 没有声称需要召回的 gold assertion，因而三项 gate 记为
`NOT_APPLICABLE_ABSTENTION`，而不是用三个任意 `true` 制造通过。它仍必须通过
两个 reviewer 对 abstention、currentness、unsupported/stale assertion 与
usefulness 的判断。

任何一个 reviewer 失败都会使该行失败。两位 reviewer 的 agreement 即使很高
也不能覆盖确定性 gate 失败；agreement 很低也不会使原本逐项全部通过的行自动
失败。两位 reviewer 的各项判断都保留，case weight 留给解盲后的唯一一次下游
应用。

### 2. 四象限 response/abstention 真值表

| truth expected mode | reviewer observed mode | 必须记录的 `abstention_assessment` | strict review 含义 |
|---|---|---|---|
| `answer` | `answer` | `not_required` | 继续检查全部 score rubric |
| `answer` | `abstain` | `fail` | response-mode mismatch，严格失败 |
| `abstain` | `abstain` | `pass` | 正确弃答，继续检查其余 guardrail |
| `abstain` | `answer` | `fail` | response-mode mismatch，严格失败 |

这张表区分“schema-valid 的失败判断”和“非法 review”。review 可以合法记录
`fail`，严格算法据此返回 `strict_rule_pass=false`；只有字段矛盾、缺失、覆盖
漂移或身份连接失败才会使整个输入终止。这样不会因 schema 只允许成功记录而
丢失反例。

### 3. 每位 reviewer 的严格通过条件

answer case 必须同时满足：

- observed response mode 为 `answer`，assessment 为 `not_required`；
- 所有 score rubric 的 `score` 均为 `2`，不得以平均分或另一 claim 补偿；
- `currentness=pass`；
- registered forbidden assertion 命中数为 `0` 且 handle 列表为空；
- unmatched unsupported assertion 数为 `0`；
- `usefulness >= 4`。

abstention case 必须同时满足：

- observed response mode 为 `abstain`，assessment 为 `pass`；
- claim-score 数组为空；
- `currentness=pass`、forbidden 与 unmatched unsupported 均为零；
- `usefulness >= 4`。

reviewer 的 `score=2` 只代表盲评 rubric 判断，不能替代
`authority_exists`、`all_gold_recalled` 或 `current_referent_correct`。三项事实门
必须由独立输入提供，这正是本单元显式暴露、但尚未解决 provenance 的接口。

### 4. 覆盖、唯一性与连接

两份 review 必须覆盖相同且完整的 case/answer 有序集合，并与 truth manifest
完全一致。每个 answer 的 claim-score 顺序和集合必须与该 case 的 score rubric
一致；重复 case、answer、claim、referent/predicate 或 assertion handle 均被
拒绝。registered forbidden assertion 的 count 必须等于唯一 handle 数，handle
必须属于该 case 的 truth registry，避免把未知 assertion 混入已注册命中。

因此，完整性不是“数量恰好相同”，而是 identity、顺序、集合与 exact-byte hash
同时相等；referential integrity 一直延伸到 `trial → truth → review → answer →
claim rubric`。这也是本单元把精确审计字段置于可视化之前的原因。

## Review receipt hash chain 与边界

每个 receipt 只描述一个 reviewer slot 的一次 invocation，固定
`invocation_index=1`、`retry_count=0`、`exit_code=0`、空 stderr、零 tool/MCP/
external-fact access 与空工作目录。核心字节链为：

| 环节 | receipt 中的绑定 | 连接要求 |
|---|---|---|
| review command | SHA-256 与 byte length、command schema hash | 精确绑定该 slot、cwd、profile、packet、instruction 与 response sink |
| stdin request | SHA-256 与 byte length | 精确绑定送入 reviewer 的请求字节 |
| raw response sink | SHA-256 与 byte length、私有 sink path hash | 必须等于规范 populated-review 文件的精确字节 |
| populated review | SHA-256 与 byte length、review schema hash | 必须连接相同 trial、contract、packet、instruction 与 reviewer slot |
| execution/custody metadata | custodian、environment、session、usage、trace、nonce、roster、conflict manifest、writer hashes | 仅形成待验证承诺；不能由 self-attestation 自动升级为事实 |

每份 receipt 还必须携带当前 review-receipt schema 的 exact-byte SHA-256
`f8af1331ae134be0f09a5e546b2d67e0db8ebfabb2177dc14a376bac773f463c`，
因此不能只用相同的 `v0` 名称替换 schema bytes。

response sink 记录 `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC`、文件模式
`0600`、父目录模式 `0700`、`nlink=1`、file/parent-directory fsync，以及写入前
不存在、独占创建等字段。这些字段是未来 provenance checker 必须验证的陈述；
JSON Schema 能检查值和形状，却不能证明内核实际执行了这些操作。

schema 因而明确固定：private record、raw response private、无 condition mapping、
不授权 scoring/unblinding、没有创建 score claim、self-attestation 不充分，并且
schema acceptance 不证明 execution。合成 checker 构造出来的 schema-valid
receipt 也只属于 `SCHEMA_VALIDATION_ONLY_NOT_CUSTODY_RECEIPT`，不得写回 live
ledger 或替代 custodian-private receipt chain。

## Synthetic closure 与 adversarial validation

合成 fixture 复用上一单元冻结的 identity-composition fixture，并在不复制其
private condition mapping 的前提下派生第二份 review、两个合成 invocation
receipt 和四条 deterministic truth-gate row。当前正向闭环的预期形状是：

| 项目 | 预期值 |
|---|---:|
| cases | 2 |
| opaque answer rows | 4 |
| reviewer slots | 2 |
| reviewer evaluations | 8 |
| synthetic receipts | 2 |
| strict pass rows | 2 |
| strict fail rows | 2 |

两个通过行分别覆盖 answer 与 correct-abstention 路径；两个失败行分别覆盖独立
truth gate 失败以及单 reviewer response-mode 失败。这样可以证明“一个 reviewer
通过不能救另一个 reviewer”与“全体 reviewer 通过不能救 deterministic gate”两
条关键反例。agreement 同时覆盖相等和不相等字段，但不参与 gate。

purpose checker 的 adversarial suite 已覆盖并固定以下类别：

- canonical JSON、重复 key、冻结 schema/source hash 与输入大小漂移；
- receipt 缺字段、时间倒序、slot/packet/instruction/command/request/response/review
  hash 或 byte-length 断链、非独占 writer 声明；
- reviewer 数量不为二、slot 重复、case/answer/rubric 覆盖漂移；
- 四象限 assessment 矛盾、forbidden count/handle 不一致、未知 handle；
- 三个 truth gate 分别失败、truth-gate row 缺失/重复/乱序/错 identity；
- condition/map/weight/preference 泄漏与 source manifest 漂移；
- schema-valid 的失败判断仍应被接受为正控制，并输出 strict false。

本地冻结结果为：normal receipt 61 行，SHA-256
`1e596192f941ac2131e7f7637b08aa315f27882dcc7825c62063efd0ac10b394`；
self-test 单行 SHA-256
`a87d1c277dfe0b26f2ab05a7e529f7c8c6ec8805bdaa0a37e732d28825e45fa0`。
自测按 JSON/schema/receipt/command/strict protocol/fixture/manifest 七类分别拒绝
5/57/83/20/26/12/12 个 mutation，共 215 个；另有 10 个 schema-valid、
strict-failing judgement 正控制被正确接受。独立的输入次序正控制还证明交换两份
review 后结果逐字节不变；exact-file API 正控制进一步确认
`input_mode=exact_files`、`synthetic_input=false`，且交换两份 raw review bytes 后
renderer 仍逐字节不变。两条路径均输出 8 条 reviewer-slot-hash 级诊断。这里同时
包含正向闭环、合法失败控制和定向反例，而不只是一次 happy path。

## 资源上限

| 资源 | 上限 | 目的 |
|---|---:|---|
| truth cases | 4,096 | 限制 case 级遍历 |
| opaque answer rows | 262,144 | 限制 case × answer 粒度 |
| two-review evaluations | 524,288 | 显式限制两评审乘积 |
| 两份 review 合计 claim scores | 1,048,576 | 防止局部 schema 合法但全局乘积失控 |
| 单个 strict-case 输入 | 32 MiB | 有界读取、降低内存风险 |
| strict-case 总输入 | 64 MiB | 限制 truth + two reviews + gates 总和 |
| strict-case 输出 | 32 MiB | 限制逐 answer 诊断输出 |
| 单个冻结 schema | 1 MiB | 限制本地 schema 解析 |
| 单个 receipt instance | 1 MiB | 限制 receipt 自身结构，不包含被 hash 绑定的外部流 |
| receipt 中单个计数字节流 | 16 MiB | 限制 command/request/response/review 长度声明 |

这些上限与逐文件 stat-size/read-length 一致性检查用于减小 OOM、文件竞态
和组合爆炸风险。它们是防御边界，不是性能基准；本单元不声称吞吐量、延迟或
大规模生产适用性。

## Limitations 与 robustness

### 已验证的 robustness

- 严格粒度、两 reviewer AND、四象限、三 truth gates 的规则可确定性重放；
- valid-but-failing review 被保留，missing/invalid input 则 fail closed；
- agreement 仅诊断、case weight 未应用、condition mapping 未输出；
- frozen review/truth/referent schema hashes 与 exact-byte input commitment 可检查；
- 对本地可见 artifact 的覆盖、唯一性、顺序、字节长度与 SHA 连接可检查；
- 所有输出显式否认 scoring/unblinding authority 与 side effects。

### 仍然真实存在的阻塞

1. `DETERMINISTIC_TRUTH_GATE_PRODUCER_AND_PROVENANCE_UNBOUND`：没有 runtime
   producer、authority/gold/currentness 依据字节或 provenance checker；三项
   布尔值目前只是受限输入，不能从 reviewer score 推导。
2. `REVIEW_RECEIPT_WRITER_AND_PROVENANCE_CHECKER_UNBOUND`：定义了 receipt
   schema，但没有受信 writer、provider/custodian attestation 验证器或真实 receipt
   instance。
3. `REVIEWER_ROSTER_INSTRUCTION_AND_CONFLICT_MANIFEST_UNBOUND`：没有绑定真实
   reviewer roster、review instruction bytes、独立性及 conflict/overlap manifest。
4. `REVIEW_RAW_RESPONSE_SCHEMA_UNBOUND`：合成路径把 raw response 定义为
   canonical review sink bytes；尚无独立 raw-response envelope/schema 或从模型
   原生输出到 review 的受证 projection chain。
5. `CONTRACT_SCOPED_O_EXCL_SCORE_CLAIM_UNCREATED`：response sink 的 O_EXCL
   字段不是 score-claim O_EXCL proof，未创建 contract-scoped score claim。
6. `SOURCE_ARTIFACTS_ARE_NOT_RUNTIME_INSTANCES`：公开源码 hash 不能替代私有
   runtime packet、review、receipt、custody 或 stage-order artifact。

此外，算法输出仍如实标记
`authority_basis_bytes_verified=false`、
`gold_evidence_bytes_verified=false`、
`currentness_basis_bytes_verified=false`、
`truth_gate_source_provenance_verified=false`、
`blind_packet_bytes_verified=false`、
`review_instruction_bytes_verified=false`、
`review_receipts_verified=false` 与
`reviewer_roster_verified=false`。

S5 candidate binding 不能填补这些缺口。S5 是 default-off、synthetic-only 的
request-scoped opaque-handle candidate interface；它没有 live producer、truth
authority、custody、gold evidence、review provenance 或 scoring authority。
把 S5 的 schema compatibility 当作本单元的 authority/gold/currentness 依据会构成
authority laundering，因此严格 fail closed。

历史盲评中的 reviewer agreement 也只能帮助选择需要加强的 rubric 或 adjudication
点，不能作为真值或当前性替代品。对 unsupported count、usefulness 等主观维度的
分歧应保留为诊断，而不能用平均值把一个严格失败变成通过。

## 下一步

本单元完成后，九个已作者化的公开源节点将导出恰好三个下一波候选：

1. `reference_condition.context_builder_sha256`
2. `sampling.sampling_seed_derivation_sha256`
3. `sampling.sampling_selection_algorithm_sha256`

在继续扩大公开源码面之前，真实运行的关键路径仍应由 custodian 补齐：

1. 冻结 deterministic truth-gate producer 输入/输出、authority/gold/currentness
   basis bytes 与 provenance checker；
2. 冻结 reviewer roster、instruction bytes、conflict/overlap manifest、raw-response
   envelope/projection 以及受信 O_EXCL receipt writer；
3. 实现两条 command → request → raw response → review → receipt 的私有 exact-byte
   chain，并在任何 unblind 之前验证；
4. 由 contract-scoped O_EXCL writer 创建唯一 score claim，随后才允许解盲、应用
   case weight 一次并生成 trial-level 统计；
5. 保留 live ledger 中三个 `PRE_UNBLIND` obligation 和 map-bijection 的
   `POST_GENERATION_PRE_REVIEW` obligation，直到绑定字段和私有 stage artifact
   都真实存在。

## 开放问题

- deterministic truth-gate producer 应从哪个受 custody 的 authority/gold/
  currentness substrate 读取，谁负责签署其 provenance？
- raw response 是否应保留 provider-native envelope，再以单独 projection receipt
  生成 canonical review，而不是直接要求 response sink 与 review 字节相等？
- reviewer roster、冲突披露和独立性应由同一 custodian manifest 绑定，还是拆成
  可独立审计的三个对象？
- contract-scoped score claim 的唯一命名、目录 fsync、失败恢复和重放策略如何与
  已有 stage-order receipt 对齐？
- 三个下一波公开节点中，是否先实现 context builder 以暴露 truth producer 所需
  的输入边界，还是先完成 sampling pair 以冻结 trial frame？

这些问题不影响本单元作为源码/机制包的可验证性，但在答案明确并形成受约束的
runtime artifact 之前，Track B 仍必须保持 `BLOCKED_FAIL_CLOSED`。
