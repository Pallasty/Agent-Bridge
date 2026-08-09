# FH-L8 D60 CPU15 isolation 可回滚事务 D82R

D82R 把 D82 唯一剩余的 host-admin load-isolation 操作固化为五态工具：`plan`、`apply`、
`verify`、`run`、`rollback`。目标仍是
`/fh-l8-d60-isolated.slice/fh-l8-d82-measurement.service`：父 cgroup 为 partition root，
service 为 isolated partition，CPU/exclusive 均固定为无 SMT sibling 的 CPU15；所有可枚举
IRQ affinity 必须移出 CPU15。

事务在首个 host mutation 前原子写入 `/run/fh-l8-d82-isolation-transaction.json`，保存
root cpuset 原状态和逐 IRQ original/applied 值。apply 中任一步失败都会自动 rollback；
rollback 遇到 populated service 或第三方 IRQ drift 时拒绝覆盖。root cpuset 只有在本事务
启用时才会在 rollback 禁用。

十一项模拟回归覆盖：完整 apply/verify/rollback、写入故障自动恢复、IRQ drift 不覆盖、
populated service 拒绝、非 root 拒绝、run 的 applied/green 前置条件，以及 admitted/
nonadmitted receipt、exclusive-create、inactive IRQ 跳过与 exclusive active IRQ 零写入阻断。
当前 live 管理员执行通过 preflight 并验证了 cgroup partition 创建，但在 managed NVMe IRQ
边界失败并完整回滚；复核证明 state file 与目标 cgroup 均不存在，root
`cgroup.subtree_control` 仍为 `cpu memory pids`，receipt 未生成。

管理员维护窗口的精确顺序：

```bash
sudo python3 docs/research/fermion-frontier/fh_l8_d60_isolation_transaction_d82r.py plan
sudo python3 docs/research/fermion-frontier/fh_l8_d60_isolation_transaction_d82r.py apply
sudo python3 docs/research/fermion-frontier/fh_l8_d60_isolation_transaction_d82r.py verify
sudo python3 docs/research/fermion-frontier/fh_l8_d60_isolation_transaction_d82r.py run -- \
  python3 docs/research/fermion-frontier/fh_l8_d60_isolation_receipt_capture_d82r.py
sudo python3 docs/research/fermion-frontier/fh_l8_d60_isolation_transaction_d82r.py rollback
```

`run` 只允许 applied state + green verify，并把子进程迁入 exact service cgroup 后固定 affinity
为 CPU15。receipt 使用 exclusive-create 写到 `.ab-evidence`，已有文件时拒绝覆盖。rollback
后必须重新运行 D82R checker，并独立审查 fresh receipt，才可讨论 D83。

2026-08-09 live 管理员执行补充取证：cgroup isolated partition 可成功创建，但 IRQ2
（inactive，effective affinity 为空）与 IRQ175（`nvme0q15`，configured/effective 都固定为
CPU15）的 affinity 写入均被内核以 `EPERM` 拒绝，事务均完整回滚。工具现在以 effective
affinity 排除 inactive IRQ，并在任何 mutation 前以
`target_cpu_has_exclusive_active_irq_affinity` 阻断单 CPU active IRQ。主机所有 CPU 都存在
至少一个 NVMe 单 CPU IRQ，因此换核不能满足 D82 的 zero-IRQ 条件；下一门是 boot-time
managed-IRQ housekeeping 方案的独立 owner gate，而不是继续重试 live apply。

本门没有 timing measurement、scientific call、numeric runtime proof 或 full53 authority。
