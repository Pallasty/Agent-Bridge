# FH-L8 D22：合成 53-shard 消费者状态机

## 结论

`VERIFIED_D22_SYNTHETIC_53_SHARD_STATE_MACHINE`。D22 用 53 个微型合成分片验证了可执行的分片前沿、分区归并、故障中断后恢复、哈希校验和 no-replace 发布语义。

它不是 q3 消费运行：输入只在内存中构造，代码没有读取 packed q3，也没有 Hamiltonian 或其他科学核调用。因此 `scientific_action_calls=0`、full 53-shard 科学执行授权仍为 `false`。

## 已验证的 fail-closed 条件

- 完整前沿必须连续覆盖 0–52；间隙或重叠拒绝恢复。
- 每个 spill 与 manifest 均绑定 SHA-256；孤儿字节、spill 漂移、manifest 漂移、fixture 漂移均拒绝。
- 在第 17 个合成分片中断后，可以从已验证前沿继续至 53。
- 归并按分区、再按分片确定性排序；目标用 `O_EXCL` 发布，既有目标绝不替换。

## 下一门

状态机存在并经微型故障矩阵验证，但还没有真实 full-run 的最坏磁盘、文件数、内存和运行时上界。下一门为 `FULL_53_WORST_CASE_RESOURCE_AND_FILE_ENVELOPE_AUTHORIZATION`；在此之前不得读取真实 q3 或执行 full action。
