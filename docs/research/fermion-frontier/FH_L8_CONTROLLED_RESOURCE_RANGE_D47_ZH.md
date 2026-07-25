# FH-L8 D47：受控 replay 资源区间汇总

D47 汇总 D45 与 D46 在同一受控条件（CPU 0、512 MiB 地址空间上限、零 swap）下的两次 replay 资源观测。

- 结构摘要保持一致：`38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12`，每次 `67` 个科学动作，`packed_q3_reads=0`，`full_53_scientific_execution_authorized=false`。
- 时间区间：`wall=1.10 s`（D45）与 `0.90 s`（D46），范围为 `0.90–1.10 s`，`Δ=0.20 s`。
- 内存区间：`ru_maxrss=40,664 KiB`（D45）与 `38,208 KiB`（D46），范围为 `38,208–40,664 KiB`，`Δ=2,456 KiB`。
- 与 D44 的 `ru_maxrss_process_peak` 规范一致；D45/D46 的波动仍归类为同约束下的运行时噪声，不构成 full-53 外推结论。

下一门：`D48_CONTROLLED_REPLAY_THIRD_SAMPLE_OR_STOP_LOCAL_LANE`。本门不执行新科学动作，不新增 full-53 授权。
