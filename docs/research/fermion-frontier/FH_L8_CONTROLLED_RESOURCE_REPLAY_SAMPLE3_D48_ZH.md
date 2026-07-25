# FH-L8 D48：受控 replay 第三次样本

在与 D45/D46 同类可比约束（CPU 0、512 MiB AS、固定两点种子路径）下执行第三次样本，结果如下：

- wall：`0.87 s`
- `ru_maxrss`：`38,336 KiB`
- 动作数：`67`
- packed-q3：`0`
- full-53 科学执行授权：`false`
- 结构摘要：`38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12`（与 D45/D46 一致）

与 D45/D46 的区间比较，`0.87 s / 38,336 KiB` 落在控制观测范围内，未出现超界扩散。下一门已转为 `D49_CONTROLLED_RESOURCE_STABILITY_DECISION`，本门不触发 full-53 与外推。 
