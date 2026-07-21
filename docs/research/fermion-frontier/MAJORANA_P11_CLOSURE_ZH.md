# Majorana P11 收口档案

状态：已收口；当前 PAX 路径映射路线终止。

本档案将 P11 的“显式内存候选设计”与其后续工具链源码证据路线区分开来。它不是候选实现、2 GiB 峰值证明、构建结果、运行结果或科学结论。

## 已经建立的内容

- P11-A（`71967df1b328cc40ad28c555f0c6ff9152f87774`）提出单线程、AOT、固定 arena、固定容量表和 2048-bit 整数的显式内存路线。其 872,415,232-byte arena 与 1,028,653,056-byte 设计账本是规划输入，而不是已证明的进程峰值。
- P11-B/C 固定 C17/GNU x86-64 静态 ELF、布局、算术、生命周期与独立检查器契约，但没有编写、编译或执行候选程序。
- E2R 完成四个精确版本源码包的字节保全；E3R 在受限链接规则下生成树清单与源位置收据。这些是版本和位置证据，不自动构成源语义或内存峰值证据。
- E4/E4R 均在读取语义源码前 fail-closed。E4R 的归档元数据预检发现 PAX 指示，未创建物化树、未提取字节、未读源码文本。
- E4S、E4U 与 E4V 对 PAX 元数据逐步缩小不确定性；所有运行均为头部层面，结果收据均记录零成员负载读取和零源码文本读取。

## PAX 路线的最终证据

| 运行 | 覆盖 | 关键观察 | 结论 |
|---|---:|---|---|
| E4S | 149,865 headers | 仅 `path`、`atime`、`ctime`、`mtime` 四类每成员 PAX 键 | 可做更窄的元数据检查，不能物化 |
| G20R | 149,865 headers | 严格四键策略下 149,244 条不合格 | 严格策略失败 |
| E4U | 149,865 headers | path: missing 149,190 / equal 621 / other 54 | 缺失和异常关系不支持映射 |
| E4V | 54 exceptional headers | `unsafe_or_unproven_relation=54`；三种可接受等价类均为 0 | 没有安全路径映射 |

E4U 成功收据的 SHA-256 为
`e61e46c0d72c1feab4736c0b76255ea8d6f0a918028f5e42d29b72e957570a5d`；E4V 成功收据的 SHA-256 为
`5b7e863d7f8fbe33f09aaea2eec2f39e8cdf37bc580d8084727eac8442fcc42a`。

G25（`056fd4d13fb0d29b296dd3f21445490090d4dde3`）的正式结论是
`CLOSE_P11_PAX_PATH_MAPPING_AS_UNPROVEN`。它禁止重试、策略放宽、物化、成员负载或源码语义读取，并且不授权新的后续契约。

## 关键提交链

P11-A 是当前路线祖先。与 PAX 关闭直接相关的连续链为：

`G16 0d875167 → E4R c16223ef → G17 ddd29e19 → E4S 496de839 → G18 03096a3d → E4S-run 768be532 → G19 4014db37 → E4T fd0f111c → G20 5667fc19 → G20R-design ee085a02 → G20R-auth 16705672 → G20R-run 0ae6f115 → G21 be6cef15 → E4U-design ebe4abdb → G22 df5c3058 → E4U-run bf19ad9d → G23 6dc3d453 → E4V-design e42b3905 → G24 373957f3 → E4V-run aaa2d5bf → G25 056fd4d1`.

运行 `python3 docs/research/fermion-frontier/majorana_p11_closure_validator.py` 可复核关键父提交、外部收据哈希及 G25 的范围受限结论。

## 不应作出的推断

- PAX 路线关闭不表示 GCC 源码本身不可安全物化，也不表示任何替代源码保全策略不可行。
- 设计账本与 2 GiB 上限的差额不是已证明的运行时余量。
- P11 尚未获得候选程序、编译产物、静态进程峰值、语义等价、S0 或科学结论。
- 任何替代策略都必须从新的上层治理或独立研究设计开始，不能继承 G25 已关闭的 PAX 权限。
