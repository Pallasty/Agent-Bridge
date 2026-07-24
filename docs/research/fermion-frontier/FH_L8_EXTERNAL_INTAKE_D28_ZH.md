# FH-L8 D28：独立签发材料的安全导入

签发方需要交付一个目录，其中每个 JSON 都以**原始 UTF-8 字节**做 Ed25519 detached signature；不得在签名后重新格式化 JSON：

1. `approval.json`：包含 D27 的 `request_id`、D5 源码哈希、单次调用/零 q3/零 full-shard 范围、资源上限和独立签发方身份。
2. `approval.ed25519.sig` 与 `approval-public-key.pem`：上述原始文件的签名与公钥。
3. `resource-receipt.json`：包含同一 `request_id`、专属隔离槽、时间窗、scratch bytes/inodes、memory cap、swap=0、wall-time cap 和资源签发方身份。
4. `resource-receipt.ed25519.sig` 与 `resource-public-key.pem`：该收据的签名与公钥。

签发方必须独立于 `agent-bridge-internal-research`，并保留其私钥；私钥、token 或可复用访问凭据均不得提交。D28 在材料缺失时拒绝；即使六个文件都存在，也只进入后续专用签名验证器，绝不直接执行内核或授予 full-53。
