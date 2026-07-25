# FH-L8 D47：固定 64-target 可复现归档包

D47 将 D42–D46 的五份冻结 receipt 及其 SHA-256、验证命令、结构 digest、动作数、条目范围和受控 RSS 窗口固化到 manifest。校验器只读取并核对文件，不执行科学 kernel；本门 verifier 的科学动作数为 0。

归档包的结论仍仅限固定 64-target source-bound fixture：不读取 packed-q3、不执行 full-53、不提供 full-run 资源估计，也不构成外部授权。下一门是独立 consumer check 或直接归档。
