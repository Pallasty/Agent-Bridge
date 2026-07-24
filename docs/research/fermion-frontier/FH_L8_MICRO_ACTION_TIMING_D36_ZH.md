# FH-L8 D36：单次微型 action 的源码固定时间收据

固定 D30/D5/D4/backend SHA-256 后，以 D5 契约的非物化 Neel 单代表元执行一次 `_reduced_column`。观测 wall time 为 0.46 秒、峰值 RSS 为 40,420 KiB，输出为 29 条且摘要保持 `eae426…f515`。这只是单进程观测，禁止外推为 full-53 资源上界；q3 reads=0，full-53 未授权。
