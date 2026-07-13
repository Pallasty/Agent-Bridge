# DESIGN — nightly digest-author（`dream digest`，propose-only + eval-gated）

状态：**设计稿，未实现**。owner 签字后才动代码；wire 进 systemd 是更后面的独立决定。
日期：2026-07-13。上游决定：`ab_memory_architecture_consolidation_middle_thesis_20260712`（巩固中段论点，owner 认可）。

## 0. 一句话

每晚用 `claude -p` 把散落在多行里的情景记忆**向上合成**为一条可引用、可审计的 `digest` 语义行（回答载体），全程 propose-only；候选晋升为 live 行必须先过**影子库离线评测门**（answer_vehicle top-5 命中 + set_recall any_mode 不回归）。

## 1. 证据基线（为什么建这个）

| 证据 | 数据 |
|---|---|
| 综合类检索失败是写入侧问题 | S1-S13 评测集 set_recall any_mode 0.753，gold 成员散在多个不连通图分量（`synthesis_assembly_connectivity_diagnostic_20260712`）；PPR/图前端已关门（Gate A，2026-07-10） |
| digest 原型正向 | 手写一条 `digest_ab_disproven_graph_gnn_retrieval_routes_20260712` 后，S3 从 0.20 散落变为 fts#2/sem#2 单行答案；防过拟合转述查询 sem#1（`outcome_digest_answer_vehicle_prototype_validated_20260712`） |
| 指标已就位 | answer_vehicle 指标已入 eval（分支 `bc2c54c0`）：hit@5=1.0，但只覆盖 **3/13** 题——10 题缺 digest = 本自动化要填的缺口 |
| 需求是真实高频 | memory_query_stats 14 天 top-miss 前两名**各 22 次**，正是 S1/S2 两条综合类查询——不是评测集虚构的工作负载 |
| 外部背书 | 11+ 外部系统零 online 学习环（全在优化读端）；AB 差异化 = 写入侧巩固 |

## 2. 形态总览（镜像 `dream distill`）

新子命令 `agent-bridge dream digest --top-n 3`，systemd oneshot + timer，每晚 **05:00**（03:42 hygiene → 04:30 distill → 05:00 digest，看到的是当晚已清洁、已出蒸馏稿的库）。短生命进程、独立 sqlite 句柄、WAL 容忍并发活读——与 `dream_distill.rs` 完全同构。

流水线四段：

```
选题器(确定性 Rust) → 素材装配(确定性) → 撰写(claude -p, 唯一 LLM 点) → digest_draft 行(propose-only)
                                                    ↓ (独立步骤,非每晚流程)
                                       影子库评测门 → 通过才晋升 live digest
```

**与 distill 的两点刻意差异**：
1. distill 是"一源行→一公共行"的降噪蒸馏；digest 是"多源行→一合成行"的向上巩固——素材是一个簇不是一个候选。
2. distill 出队靠人审；digest 晋升多一道**机器可判的评测门**（因为 digest 的目的就是可检索性，这恰好可以离线量化）。

## 3. 选题器（确定性，无 LLM）

> 修正早前"Haiku 选题"的想法：选题三个来源全部可确定性枚举，LLM 进选题只损失可审计性。免训练可解释遍历是本库反复亲证的赢家形态，选题器遵循同一纪律。

每晚从三个来源生成候选主题，按分数排序取 top-N（默认 3）：

- **T1 评测集载体缺口**（最高优先）：读 `scripts/eval/fixtures/synthesis_queries.json`，凡 `answer_vehicle` 为空的题（当前 10/13）即一个主题；分数 = 该题当前 set_recall 的缺口（越差越优先）。查询即目标查询，gold_set 即素材种子。
- **T2 遥测 miss 簇**：`memory_query_log` 窗口内 count ≥ 3 的 NL miss 查询（排除裸 key 查询——那是 get 失败不是综合失败），按 count 排序。查询即目标查询。
- **T3 结构散落簇**（补位）：supersede 链长 ≥3、或同 tag/co-cite 行数 ≥5 且互相无 digest 覆盖的簇。**没有天然目标查询**——目标查询由撰写者提出（见 §5），门禁照过。

**领地排除**：`portfolio_state_digest` 不在本管线领地内——它按 2026-07-10 裁决走**手动刷新纪律**（状态实质变化的会话收口时刷新，`ab_writeside_digest_successor_no_advance_20260710`），选题器硬排除其已覆盖的主题（S1/S2 已声明它为载体，天然不在缺口集）。本管线只产**新主题**digest，不碰既有手动维护行。

**去重（确定性）**：候选主题先对既有 `digest_draft` + live `digest` 行做两道排除——(a) 目标查询与既有 digest 的 retrieval_trigger/目标查询精确或高相似（GTE embedding cosine > 0.85）命中即跳过；(b) 素材种子集合与既有 digest 的 related_keys 交并比 > 0.6 即跳过。**drafted-once**：与 distill 同义——主题出过草稿就不再出，除非草稿被删（删=重新排队）。

## 4. 素材装配（确定性）

每主题：目标查询跑三模 `memory_search`（fts/hybrid/semantic）各 top-10 取并集，加上选题器给的种子行（gold_set / 簇成员），按 any_mode 最优名次排序取前 **M=12** 行的**全文**进 prompt。硬上限 ~24k 字符（超限截 M）。装配清单（key+kind+scope+全文）原样进草稿行的审计段，评审者看得到模型看到的一切。

## 5. 撰写契约（`claude -p`，prompt `digest_v1`）

沿用 distill 验证过的通道：本地 `claude -p`，零 API key，`AGENT_BRIDGE_CLAUDE_BIN` 覆盖。模型：**默认模型**起步（与 distill pilot 同条件基线）；`--model` 作为旋钮留出。不给 Haiku 撰写——合成 12 行全文是本流水线唯一真需要智力的点，省这一步的钱毁整条管线的品。

输出严格 JSON：

```json
{"verdict":"author|decline",
 "reasoning":"1-2 句",
 "draft": {"key":"digest_<topic_slug>_<yyyymmdd>",
           "content":"…（引用账本体）…",
           "tags":["digest","derived:digest_author", "..."],
           "retrieval_trigger":"…",
           "source_keys":["…"],
           "target_queries":["…1-3 条自然语言查询…"]}}
```

**四条硬纪律**（镜像 distill 四纪律，全部机器可验或评审可验）：

1. **引用账本体**：content 的每一个事实性断言必须行内标注来源 key（格式 `（→ key）`）。digest 不是散文,是带出处的台账。
2. **source_keys ⊆ 装配清单**：Rust 侧验证——引用了没给它看的 key 即整条作废。**这一条在结构上杀死 v21 Appendix A 的"审计丢失"反对**：幻觉引用无法通过 parse 门。
3. **空白段强制**：content 末尾必须有"空白/未定：…"一段，写明素材**没有**覆盖的相邻问题。防过度声称——digest 的毒性主要来自把局部素材说成全貌。
4. **decline 光荣**：素材不构成一个连贯主题、或已有 digest 实质覆盖时，输出 decline + 理由。宁缺毋滥（distill pilot 实测过撰写者的许可偏置,这里同样假设存在）。

`target_queries`：T1/T2 主题预填选题器的真实查询,撰写者可追加转述变体；T3 主题由撰写者提出 1-3 条（模拟未来提问者)。这是评测门的输入。

Rust 验证门（镜像 `parse_verdict`）：JSON 可解析、verdict 合法、key 前缀 `digest_`、source_keys 非空且 ⊆ 装配清单、content 非空且含"空白"段落标记、target_queries 非空。任一不过 = 不写草稿行,候选留队明晚重试。

## 6. 草稿行与生命周期（镜像 distill 自清洁队列）

- 行：key = `digest_draft_<topic_slug>`，kind = `digest_draft`，importance 0.4，tags 含 `digest_draft` / `digest_prompt:v1` / `batch:YYYY-MM-DD` / `proposes:<digest_key>`，related_keys = source_keys 全量（出处边 `derived_from` 逐条落）。
- content = 评审包：主题来源（T1/T2/T3 + 分数）、目标查询、装配清单、模型原始 JSON、建议评审动作。
- 出队三条件（自清洁,零强制记账）：(a) 提议的 digest key 出现为 live 行（晋升执行）；(b) 草稿获 `resolved:*` tag（人工否决）；(c) TTL 14 天自然过期扫走（评测门连续不过/没人管 = 自动放弃)。删除草稿 = 主题重新排队。
- **本模块永不写 kind=digest 行**——与 distill 永不写 pub_* 同一条铁律。

## 7. 评测门与晋升（新机制,本设计的核心增量）

晋升是**独立于每晚撰写的步骤**,由 `scripts/eval/digest_gate.py`（待建,复用 ab_eval 机械）离线执行：

1. 拷贝 live `state.db` 到 scratch 目录,`XDG_DATA_HOME=<scratch>` 指向副本（`default_db_path()` 已支持,亲验于 sqlite.rs:764）。
2. 在**副本**里把候选草稿物化为 live digest 行。
3. 对副本跑两道检查：
   - **命中门**：每条 target_query 跑三模检索,候选 key 在 ≥1 条 target_query 的 ≥1 模式中 rank ≤ 5。
   - **不回归门**：全量 synthesis 评测 vs 当前 baseline,set_recall any_mode 降幅 < 0.02（防 fts 顶座挤出——原型日实测过 fts 微降 0.583→0.564,这是要盯的真实副作用）。
4. 两门全过 → 输出 PASS 报告；晋升动作（在**活库** memory_save 该 digest 行 + 若刷新旧主题则 supersedes 旧 digest）v1 阶段仍由 agent 会话执行并留 outcome 行。

**分阶段收权**（每阶段独立可回滚,推进以数据为闸）：
- **S1（本提案范围）**：nightly 只产草稿；门禁脚本手动/会话内跑；晋升全人工（agent 会话执行,owner 可见）。
- **S2**：连续 ≥10 条草稿零幻觉引用、零门禁误放后,门禁进 nightly 尾段自动跑,PASS 的草稿在 bootstrap 评审块带"已过门"标记,晋升仍人工。
- **S3（需 owner 单独批）**：PASS 即自动晋升,带 `digest:probation` tag,次晚门禁复跑不过即自动 archive。

## 8. 可逆性与红线

- **一键回滚**：所有本管线产物带 `derived:digest_author` tag——`UPDATE ... SET status='archived' WHERE tags LIKE '%derived:digest_author%'` 一条语句全量撤回（archive 可恢复,非删除）。
- **kill switch**：`systemctl --user disable --now agent-bridge-digest.timer`；另设 `AB_DIGEST_AUTHOR_DISABLE=1` env 闸（镜像 surfacing 的闸形态）。
- **不触检索运行时**：零 ranking 代码改动、零新检索模式、零 schema 迁移（digest 就是普通 memory 行）。本设计整体在"可回滚即自主"半径内,但因涉及每晚自动 LLM 写库,**wire 进 systemd 前仍请 owner 签字**（与 distill 上线时同规格）。
- **供给上限**：每晚 ≤3 草稿；每主题至多 1 条 live digest（刷新走 supersede,不叠加)——顶座挤出的结构性上限。

## 9. 成本包络与排程

distill 实测 62-130s/候选（prompt ~数 KB）。digest prompt 更大（12 行全文,~24k 字符上限）,估 **90-180s/主题**;top-3 ≈ 5-9 分钟,TimeoutStartSec=3900 富余。每晚 3 次 `claude -p` 调用,与 distill 的 5 次同量级,零 API key 成本。

## 10. 成功判据（30 天）

1. answer_vehicle 覆盖 3/13 → ≥10/13,hit@5 保持 ≥0.9。
2. 两条 22 次 top-miss 查询（S1/S2 同源）获得 rank ≤5 的载体行,后续遥测窗口内该两条 miss count 显著下降（这是唯一的**线上真实**判据,评测集之外）。
3. set_recall any_mode 全程 ≥ 0.74（基线 0.753 - 容差）。
4. 幻觉引用率 = 0（source_keys 验证门拦截数即观测量,拦截≠事故,穿透才是）。
5. decline 率健康（>0——撰写者从不 decline 即许可偏置复发信号,参照 distill pilot ruling #1）。

## 11. 对既有反对意见的正面回应（v21 Appendix A）

v21 曾三条理由拒绝 LLM 合成巩固,本设计逐条处理而非绕开：

1. **"审计丢失"** → 引用账本体 + source_keys ⊆ 装配清单的机器验证 + `derived_from` 出处边。digest 的每句话可回溯到具体源行,审计强于人写的散文型 memory 行。
2. **"质量永久毒化"** → propose-only + 评测双门 + probation/supersede/archive 全链可逆 + 每主题单行上限。毒化需要"写入即不可撤",本管线没有这个性质。
3. **"错过原语痕迹"** → v21 选的痕迹路线(v22 基质)已于 2026-05-24 被 P6 null-path 证伪(NO_RECALL_ADVANTAGE)。内容层合成是幸存路线,且已有 S3 原型正向实证。

另有一条**更近的前置裁决**需要正面调和——`ab_writeside_digest_successor_no_advance_20260710`（successor v2 盲评协议失败后的写入侧落点）：

- 该裁决**成立且本设计遵守的部分**：digest=语料侧补丁成立（本设计正是语料侧补丁）；digest=上下文替代 hybrid 无有效验证（本设计不做上下文替代，digest 走普通检索通道）；`portfolio_state_digest` 手动刷新纪律（本设计选题器硬排除其领地，见 §3）。
- 该裁决**"自动再生成不推进"的依据是证据性而非原则性**——当时的分数因评审 provenance 失败整体不可采，"缺乏有效验证"所以不推进。本设计补上的正是缺的那块：评测门是**确定性排名读数**（rank≤5 / set_recall 数值），不依赖任何 LLM/人类评审判断,结构上免疫那次协议失败的失败模式（同族会话收敛≈自我一致）。且 S1 阶段自动化止步于**草稿**，晋升仍人工——"自动再生成"在有效验证到位并分阶段收权之前不发生。

## 12. 待 owner 决定

1. 本设计方向签字（签字后我实现 S1：`dream_digest.rs` + `digest_v1` prompt + `digest_gate.py` + 金测试,PR 走正常评审）。
2. eval 分支 `628ee719`+`bc2c54c0`（answer_vehicle 指标）合 master——本管线的门禁依赖它。
3. S3 自动晋升留到 S2 数据出来再议,本次不需要决定。
