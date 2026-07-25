# FH-L8 D48：可复现归档包 Consumer 检查

D48 只做 D47 的独立静态 consumer 检查：对 `fh_l8_fixed64_repro_packet_d47_manifest.json` 与
`fh_l8_fixed64_repro_packet_d47_result.json` 进行内容固定、哈希锁定和关键边界核验。

核验要点：

- 验收 `D47` status 为 `VERIFIED_D47_FIXED64_REPRO_PACKET`，且 `next_gate` 正确为 `D48_REPRO_PACKET_CONSUMER_CHECK_OR_ARCHIVE`。
- 检查 `receipts_verified = [d42, d43, d44, d45, d46]`、`selected_representatives = 64`、`scientific_action_calls = 67`。
- 核验 `packed_q3_reads = 0`、`full_53_scientific_execution_authorized = false`、`full53_extrapolation_forbidden = true`。
- 核验 manifest/结果中的结构摘要均为 `38aaeffb...`，并逐项固定化核验
  `d42/d43/d44/d45/d46` 的 receipt SHA-256。

本门不执行科学动作（verifier 动作数 0），不触发任何 full-53 授权，不做任何归档下载或外部读取，结论仅用于将可复现归档包收束为可归档状态。
