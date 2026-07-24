# FH-L8 D27：单次微型科学 action 的双重授权

## 结论

`NO_GO_D27_INDEPENDENT_MICRO_ACTION_APPROVAL_ABSENT`。D27 定义了只允许一次 `_reduced_column`、零 packed-q3 读取、零 full-shard 的请求范围，以及 512 MiB、零 swap、180 秒的上限。它没有提供独立签发的 approval，也没有调用内核。

审批必须来自不同于请求方的 authority，绑定 D5 和 D18-C 源码哈希，并与动作/资源范围逐字段完全相同；自批准、两次调用或任何资源范围漂移都会拒绝。即使获得可接纳审批，它也只涉及单次微型动作，绝不授予 full-53。

## 下一门

必须由独立方提供该单次动作审批及隔离资源收据。当前会话无法代替该外部签发，故在其出现前不能执行内核。
