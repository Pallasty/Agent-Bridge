# FH-L8 D8：packed depth-3 quotient checkpoint 协议

D8 落地了 D7 所要求的前置协议，但不执行科学计算。checkpoint 采用固定 32-byte 记录：16-byte 大端 canonical representative、8-byte 小端有符号 amplitude、1-byte orbit size 与 7-byte 零保留区。`213099` 条记录的最大 payload 为 `6819168` bytes。

记录按 representative 升序、每 4096 条一 shard，共 53 个 shard，末 shard 为 107 条。每个完整 shard 必须先 fsync payload、再写入含 shard hash 的 manifest；恢复只能从已 hash-bound 的完整 shard 边界开始。

本门未物化 checkpoint 或 source vector，未授权或执行 depth-3→4 quotient-H action。下一门是有独立授权的 bounded packed-checkpoint preflight protocol。
