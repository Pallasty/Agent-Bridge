# FH-L8 D12：q4→q5 当前信封成本门

D11 的 depth-4 target 有 `10,785,545` 个 signed quotient source。按冻结的每行至多 225 个 Hamiltonian 项，q4→q5 的 raw candidate 上界为 `2,426,747,625`；加上 signed D4 canonicalization 后，总群图像上界为 `19,500,265,360`，32-byte primary spill 上界为 `77,655,924,000` bytes。

这些数值分别超过当前 D10/D7 信封的 raw-candidate、group-image、8-GiB cumulative-spill 与 128-MiB live-buffer 上限。因此状态为 `NO_GO_D12_Q4_TO_Q5_CURRENT_D10_ENVELOPE`，q5 未执行。

唯一后继是 `Q4_TO_Q5_ALGORITHM_OR_RESOURCE_ENVELOPE_REDESIGN`：必须先提出并独立验证更强压缩/截断证书或新的资源信封，不能直接复用 D11 runner。
