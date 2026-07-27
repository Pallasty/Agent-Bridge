# FH-L8 D59 production I/O 与 page-cache 决议

D59 固定了 source checkpoint、partition spill、两代 external merge 与 target publication 的
生产 I/O 生命周期。它保留 D51 的 256 partitions、32-way merge、两代 spill 同时存在与旧 run
在 terminal receipt 前不可删除的约束。

但 Linux/文件系统的 dirty/writeback/page-cache 生命周期、cgroup file-page accounting、target
size 与 fsync 规则尚无可验证环境契约。故 spill 文件字节数不能等同 page-cache peak，任何 host
观测也不能成为跨环境上界。D59 返回 NO-GO，不执行 production I/O、科学 kernel 或 packed-q3
读取；numeric peak 与 full-53 授权维持 false。

下一门为 D60：在任何支持性 timing 测量前冻结 operation population、环境与 margin/static rule。
