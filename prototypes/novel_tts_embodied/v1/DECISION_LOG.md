# 决策沉淀（novel_tts_embodied v1）

更新日期：2026-07-25

## 已落地决策

1. `present_voice` 执行器回执解析采用分层判定，避免把 stdout 漂移当失败：
   - 优先解析 JSON 回执（支持全文/逐行/花括号平衡提取）；
   - 再做非 JSON 文本回执解析（`status`/`status_code`/`verify_status`/`output_file` 等）；
   - 回退到执行器返回码。

2. `status_code=0` 的判定不再通过 `or` 丢失：所有返回码用 `coalesce` 后直接保留整数 0。

3. 成功判定函数 `_is_success_status` 收紧为显式规则：
   - 明确返回码失败先行裁定；
   - 先按 `verify_status` 作显式正负判定；
   - 再按 `status` 作显式判定；
   - 其余在返回码正常时默认视为成功，减少误判边界。

4. `output_file` 字段可被执行器回执覆盖：在回执中带 `output_file` 时，结果文件元数据以回执路径为准。

5. 运行期回归脚本 `regression_present_voice.py` 覆盖：
   - 无执行器（`skipped`）;
   - JSON 回执成功;
   - 非 JSON 文本回执成功;
   - 首次失败后重试成功。

6. 冲突状态处理规则落地：当 `status` 与 `verify_status` 均为显式值且互相冲突（如 `status=failed` + `verify_status=verified`），直接判为失败，避免回执不一致导致误放行。

7. dry-run 证据最小字段落地：
   - 新增 `executed`（是否实际触发执行器）和 `executed_count`（汇总）；
   - 干跑场景统一返回 `status=queued`、`executed=false`，用于回放/审计复用。

8. 提供标准 `present_voice` CLI 适配器 `adapters/present_voice_cli.py`：
   - 统一 JSON 输入协议（`backend/text/voice/.../output_file`）；
   - 默认实现 `backend=ab-tts` 的占位 `wav` 回执链路，确保 AB 可复放；
   - 支持 `NOVEL_PRESENT_VOICE_BACKEND_CMD` 外置真实后端命令模板；
   - 回归新增 `scenario_cli_adapter` 覆盖 adapter 真实接线。

9. `annotations` 输入契约固定与接线：
   - `parse_annotations` 改为返回 `(overrides, annotation_issues)`；
   - `run_pipeline` 将 `annotation_issues_summary` 落盘到 `manifest.annotation_issues` 与 `result.json.annotation_issues_summary`；
   - `segment.debug.annotation_issues` 记录段级问题；
   - `build_segments` 对每段保留 `annotation:...` 形式的回退证据；
   - 回归补充两类场景：合法注入落库、非法注入回退且不阻断主流程。

## 回滚策略

- 若回执判定出现误判，可回退到 `ab_runner.py` 中 `_is_success_status` 与 `_extract_freeform_receipt` 的上一版本实现。
- 回归可快速验证：`python3 regression_present_voice.py --workdir /tmp/novel_tts_embodied_regression`。
