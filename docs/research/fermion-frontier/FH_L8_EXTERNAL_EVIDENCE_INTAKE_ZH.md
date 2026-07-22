# FH-L8 外部证据接收与准入

`fh_l8_external_evidence_intake.py` 是真实 compiler export 的唯一接收入口。它不下载、执行或生成导出；调用方将已经取得的原始 JSON 放在独立 intake 目录，并在 registry 中登记相对路径与来源链。

## 提交格式

以 `fh_l8_external_evidence_registry_template.json` 为起点。每条必需路线分别登记：原始文件相对路径、原始 SHA-256、HTTPS 来源 URL、不可变 release/commit、`PRIMARY_EXTERNAL_RAW_EXPORT` 证据类别和来源保管声明、compiler 名称与版本、compiler 配置 SHA-256、环境锁 SHA-256。原始 JSON 本身还必须声明路线、`FH_L8_UoverT8_tT1_half_filling`、`linear_size=8`、`trotter_steps=100`，并通过既有逐项 term validator。

执行：

```bash
python3 docs/research/fermion-frontier/fh_l8_external_evidence_intake.py \
  --registry /secure/intake/registry.json --intake-root /secure/intake
```

返回值含义：

- `INCOMPLETE`：尚未提交全部五路线，或登记的文件尚未到位；
- `REJECTED`：有字段、路径、哈希、工作负载或逐项 term sequence 错误；
- `READY_FOR_CROSS_ROUTE_COMPARISON`：五条路线均已通过准入，输出中附带既有比较器的 `MATCHED` 或 `MISMATCH` 结果。

没有所有路线的 `ADMITTED` 状态时，绝不会执行跨路线比较。合成 fixture、手写序列和图文重建被契约明确排除，未登记文件也不会被自动发现或接纳。
