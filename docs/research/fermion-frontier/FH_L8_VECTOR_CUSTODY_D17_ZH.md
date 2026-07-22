# FH-L8 D17：向量保管与双向量收缩协议处置

D17 复核 D16-F 后得出 fail-closed 结论：已提交的 packed q3 是唯一可准入源（213,099 条、6,819,168 bytes、SHA-256 `db2ce0…f840231`）；遗留 q4 target 的生产托管已断裂，必须隔离，不能作为收缩的左或右向量。

此外，q0、q1、q2 尚无本门可准入的独立 packed payload。因此 q0–q4 完整向量保管和双向量收缩协议均不可物化，任何数值收缩都被拒绝。

唯一后续路线是从 committed packed q3 出发，采用全新独占 scratch root、预读哈希校验、禁止 shared append spool、manifest-only merge 与 fail-closed recovery 的消费者实现；第一步只能申请有界 4,096-source preflight 的单独授权。该预飞尚未获执行授权。
