# FH-L8 D60 owner policy 与 load-isolation 门 D82

D82 接受 owner 对推荐路线的确认并冻结两项政策：运行时声明仅为
`EMPIRICAL_ADMISSION_RUNTIME_ENVELOPE_NOT_DETERMINISTIC_WORST_CASE`；五类 operation
各使用 459 个 fresh confirmatory samples，以样本最大值形成 distribution-free 单侧
tolerance limit。总 confirmatory population 为 2,295，单类 coverage/confidence 均为
99%，由 Bonferroni 得到的五类 family-wise confidence 下界为 95%。D54R/D54R2 仍只能
用于 pilot 与热点排序；scalar margin、事后样本排除、deadline multiplier 均被禁止。
该 tolerance limit 只约束注册的 batch-cost population，不能解释成 whole-run tail 或
worst-case proof。

timeout policy 同时冻结：每个 confirmatory sample 的操作性上限为 240 秒；full-run
deadline 只能由最终 sealed empirical envelope 向上取整产生。超时返回
`INDETERMINATE_MEASUREMENT_FAILURE`，不自动重试、不延长 deadline，systemd `Type=exec`
配合 `RuntimeMaxSec`，终止顺序为 SIGTERM、30 秒 grace、SIGKILL。timeout 不构成
scientific NO-GO，也不升级为 numeric worst-case proof。

## 当前 live isolation 判决

目标机制固定为 cgroup v2 `cpuset.cpus.partition=isolated`，目标为无 SMT sibling 的
CPU15。精确目标 cgroup 是
`/fh-l8-d60-isolated.slice/fh-l8-d82-measurement.service`；CPU effective、exclusive
effective、process affinity 和 root isolated membership 必须都严格等于 `15`，并且所有
可枚举 IRQ affinity 都必须排除 CPU15。

当前主机只有根层 `cgroup.controllers` 暴露 cpuset；根 `cgroup.subtree_control` 未启用
cpuset，当前进程仍位于普通 `session-3.scope`，affinity 为 0-15，root isolated CPU 集合
为空，并存在 CPU15 IRQ affinity 冲突。当前会话也没有 non-interactive sudo。D82 因而
返回 `BLOCKED_D82_OWNER_POLICY_FROZEN_HOST_ISOLATION_NOT_ADMITTED`，只剩
`concurrent_load_exclusion_mechanism` 一个 missing input。

本门未尝试管理员级 cgroup/IRQ 修改，执行了 0 timing measurement、0 production I/O、
0 external request、0 scientific kernel call。它没有生成 D83 measurement authorization，
没有证明 numeric runtime，也没有授予 full53。

## 管理员交接条件

管理员必须在受控维护窗口内建立 exact isolated service cgroup、排除 CPU15 IRQ，并在该
service 内运行 D82 verifier。由于 D81 冻结的是旧 `session-3.scope`，切换 cgroup 后必须
重新 capture 环境身份；不能把旧 D81 cgroup path 当成通过证据。只有 fresh D82 receipt
十一项 isolation 谓词全部为 true，才可生成 D83 sealed premeasurement packet；D83 还需
冻结互斥 operation-class batch/cost attribution，并且只能授权精确的 2,295 样本计划。

验证：

```bash
python3 docs/research/fermion-frontier/test_fh_l8_d60_owner_policy_isolation_d82.py
python3 docs/research/fermion-frontier/fh_l8_d60_owner_policy_isolation_d82.py
```
