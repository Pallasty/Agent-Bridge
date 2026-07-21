# FH-L8 matched benchmark 外部证据激活

当前仓库已经具备模型、模板和局部验证器；它不具备五条路线的真实编译器导出、真实测量或经固定机器检查的独立有界 reference。`matched_benchmark_evidence_activation_contract.json` 因此固定这些空模板的哈希和预期 fail-closed 状态。

在任何外部实验或编译器数据接入前，运行：

```sh
python3 docs/research/fermion-frontier/matched_benchmark_evidence_activation_validator.py
```

预期状态为 `BASELINE_UNRESOLVED_EXTERNAL_EVIDENCE_REQUIRED`，不是 READY。要解除该状态，必须同时满足契约列出的八项条件：真实五路线 term export、完整 first-step ledger、campaign 参数、独立有界 reference、双观测量收敛、native transition、surface place-and-route，以及同误差 A/B 核算。合成 fixture、assumed/derived 硬件数字、未认证 reference 和空模板都不能代替其中任何一项。
