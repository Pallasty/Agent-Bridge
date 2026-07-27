# FH-L8 D57 production streaming adapter 契约

D57 提供可导入的 adapter 模块，固定数据流：单条 32-byte packed source 解码、调用方提供
的 mock kernel 产生 column、编码 32-byte partition spill records、在返回或失败前于
`finally` 清空 column、规划最多 32-way merge、最后按固定顺序 publish。

synthetic tests 只在内存中构造单条 source，且 `packed_q3_reads=0`、production I/O 为零。
它用于检查格式、spill/merge/publish 顺序与逐 source column 释放，不能替代 production
或 full-53 路径。

`run_full53()` 恒定抛出 `Full53Unauthorized`。D5 的 `_reduced_column` 仅是已钉扎的未来
绑定符号；D57 验证不导入或调用科学 kernel。数值内存、运行时间、外部资源预留和 full-53
授权仍均为 false。

下一阶段由 D58、D59、D60 并行承接：分别闭合 live allocation、production I/O/page-cache 与
预承诺时间界规则。
