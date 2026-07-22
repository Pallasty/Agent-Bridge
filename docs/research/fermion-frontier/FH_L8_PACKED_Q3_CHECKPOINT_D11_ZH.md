# FH-L8 D11：packed depth-3 quotient checkpoint 物化与复验

## 判决

D11 已按预注册协议物化并认证 depth-3 quotient source checkpoint。机器状态为
`VERIFIED_D11_PACKED_DEPTH3_QUOTIENT_CHECKPOINT_MATERIALIZED_NO_Q4_AUTHORITY`，合同 ID 为
`FH-L8-D11-PACKED-D3-QUOTIENT-CHECKPOINT-MATERIALIZATION-V1`。

本门只固定可供后续协议消费的 `q3` 源，不执行也不授权 `q3→q4`。下一门精确为
`CHECKPOINTED_FULL_QUOTIENT_H_RUNNER_IMPLEMENTATION_AND_AUTHORIZATION`；它要求先冻结专用
checkpointed full quotient-H runner 及其独立授权，不能由 D11 的成功自动解锁执行。

## C1→C2→C3 冻结顺序

Git 拓扑把源、合同和结果分成三个直接相邻的提交：

1. C1 `49ac8a25faf80c85fab9acaa7390fda7b4c0d7f2`，tree
   `75f8034aec9c95d02b4647c5908aea17c1835115`，直接父为基线
   `b620f02ff53ed84472d0f38c775bdeb584fdf736`。该提交只新增冻结的 checker 与 runner，尚无
   contract 或输出。
2. C2 `429f31d0b82284f07860b3eb460102816fae1e17`，tree
   `3d0ce731c6ae6c3697eb691823e95e527ae4918f`，直接父为 C1。该提交只新增 contract；正式
   replay 前 checkpoint、result 和 terminal receipt 均不存在。
3. C3 `784f01b8e3c589b7c6ab25773f93937d5a1344f8`，tree
   `801d335d7edf39de22a24f969c1a81396c065095`，直接父为 C2。该提交恰好新增三个 `100644`
   结果文件：6,819,168-byte `checkpoint.bin`、8,608-byte `result.json` 和 2,470-byte
   terminal execution receipt；没有夹带代码或其他路径变更。

terminal receipt 记录 runner exit code 为 `0`、stderr 为 `0` bytes，并把 C1、C2、checkpoint
和 result 的身份重新绑定。receipt 自身 SHA-256 为
`deafacbcbb77885353254306200137c7248321641b0eb197494d5cbd0d3a9ab2`。

## 固定宽度编码与语义检查

checkpoint 无 header、无 trailer，共 `213,099 × 32 = 6,819,168` bytes。记录按 unsigned
representative 严格升序：

| offset | bytes | 字段 | 约束 |
|---:|---:|---|---|
| 0 | 16 | representative | unsigned u128，大端 |
| 16 | 8 | amplitude | signed i64 two's-complement，大端且非零 |
| 24 | 1 | orbit size | 只允许 `1`、`4`、`8` |
| 25 | 1 | flags | 必须为零 |
| 26 | 2 | reserved | unsigned u16 大端，必须为零 |
| 28 | 4 | D5B insertion rank | unsigned u32 大端，必须构成 `0..213098` 的完整置换 |

静态审计逐条确认 representative 唯一且留在 `N_up=32,N_down=32` 扇区，D5B signed
canonicality 与 D6 support-table nomination 均通过。振幅中正值 `106,583` 条、负值
`106,516` 条、零值 `0` 条，总和为 `-2,385,544`，观测到的最大绝对值为 `2,181,376`，低于
冻结上限 `43,614,208`。orbit 直方图为 `{1: 1, 4: 125, 8: 212973}`，coverage sum 为
`1,704,285`。

D8 只是未物化的早期协议：其 amplitude 规划为小端，尾部字段也没有 D11 的 D5B insertion
rank。D11 是单独冻结的自验证大端格式，不声称与 D8 byte-for-byte 兼容；二者相同的
`32-byte × 213,099` 上限不能被解释为编码兼容证据。

## 四类 digest

四个 digest 绑定不同的字节或语义序列，不能彼此替代：

| digest | SHA-256 | 所绑定内容 |
|---|---|---|
| packed sorted binary | `db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231` | C3 中 6,819,168 个原始 bytes |
| sorted semantic | `56584a95835d7a0535d118bbcc50f3670ad71f54c6b0e61597f0004483bba619` | 升序的 representative、amplitude、orbit size 与 D5B rank |
| legacy D5B insertion order | `7230d8bd0e726535cb5da01bc191313b25e38b83a6b809a7e6e39823a418757e` | 按 D5B 插入顺序重排的 signed quotient 坐标 |
| D6 sorted support-orbit | `7e4f0d2526b49c786b124a8b45dc82cc8892a7798e7c4c362cd4aa15db74ca26` | 升序 representative 与 orbit size，不含 phase 或 amplitude |

此外，`8 × 16 × 256 = 32,768` 个 byte-table 定义项已逐项对照直接 reference；524,288-byte
表序列的 SHA-256 为
`55ba9e8c99fb56545ab4ec64e43ab5f9d1b106a9e53b086009f9b983510b45e5`。这只认证 support
permutation，不赋予 fermionic phase 或 quotient amplitude 权限。

## 正式生成与独立 heavy replay

正式生成由 checker 在 fresh user `systemd` scope 中启动 runner，并要求
`memory.max=1,073,741,824`、`memory.high=805,306,368`、`memory.swap.max=0`，internal / outer
deadline 分别为 `300 / 330` 秒。terminal publication receipt 的 elapsed 为
`86,972,280,118 ns`；cgroup peak 为 `406,224,896` bytes，process max RSS 为
`414,253,056` bytes，swap current 为零，`max/oom/oom_kill/oom_group_kill` 事件增量均为零。

提交 C3 后，checker 的 heavy 模式又在另一个 fresh 1 GiB、zero-swap scope 中从冻结输入重放
depth 0→3，并逐 byte 比较已提交 checkpoint。该进程 exit code 为 `0`，观测为：

| 项目 | 独立 heavy replay |
|---|---:|
| elapsed | `78,866,810,663 ns` |
| cgroup current，before → after | `75,792,384 → 194,985,984` bytes |
| cgroup peak，before → after | `90,681,344 → 418,836,480` bytes |
| process max RSS | `417,328 KiB`（`427,343,872` bytes） |
| memory.max / memory.high | `1,073,741,824 / 805,306,368` bytes |
| swap current / max | `0 / 0` bytes |
| memory events | `low/high/max/oom/oom_kill/oom_group_kill` 全为 `0` |
| checkpoint equality | byte-for-byte `true`，SHA-256 为 `db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231` |

heavy replay 是与正式 materialization 分开的 outcome 验证运行，并使用不同的 checker 控制流与
序列化路径；合同不声称存在第二套独立编写的 Hamiltonian 实现。

## 权限边界与下一门

正式生成和 heavy replay 都只允许三次 Hamiltonian action，acted source depths 精确为
`[0,1,2]`，最大 acted depth 为 `2`。两次验证都确认第四次调用在进入 backend 前被拒绝：
`depth3_source_rows_visited=0`、`q4_records_emitted=0`、底层 action call count 仍为 `3`，且
`q3_to_q4_executed=false`。

因此 D11 没有认证 depth-4 target 的 cardinality、vector 或 digest，也没有认证 degree-6
remainder、two-step/full-R100 error、physical reference、hardware、quantum advantage 或
READY。尤其是，checkpoint 生成和重放的 elapsed、RSS、cgroup peak 只描述 depth 0→3 重放、
q3 orbit 审计与 packing；不得外推为 `q3→q4` 的运行时间、内存可行性或性能数字。

下一 bounded unit 只能实现并冻结
`CHECKPOINTED_FULL_QUOTIENT_H_RUNNER_IMPLEMENTATION_AND_AUTHORIZATION` 所要求的 runner、
资源/停止规则与独立执行授权。在新的 contract freeze 完成以前，D11 的 checkpoint 只能作为
hash-bound 输入，不能被用来启动第四次 Krylov Hamiltonian action。
