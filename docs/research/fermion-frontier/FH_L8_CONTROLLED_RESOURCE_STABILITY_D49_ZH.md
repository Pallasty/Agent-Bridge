# FH-L8 D49：受控资源稳定性决策

依据 D45/D46/D48 三次同约束受控复放（CPU 0、512 MiB AS、零 swap）结果，作如下稳定性结论：

- 结构摘要始终一致：`38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12`
- 动作数恒定：`67`，`packed_q3_reads=0`，`full_53_scientific_execution_authorized=false`
- 资源区间：
  - wall：`0.87–1.10 s`
  - ru_maxrss：`38,208–40,664 KiB`
  - 其中 D48 样本 3 为 `0.87 s / 38,336 KiB`

决策：三点复放未出现新扩散迹象，判定 `stabilized`。当前不再追加扩规模受控复放；下一门接续 `D48_REPRO_PACKET_CONSUMER_CHECK_OR_ARCHIVE`（不触发 full-53 外推）。 
