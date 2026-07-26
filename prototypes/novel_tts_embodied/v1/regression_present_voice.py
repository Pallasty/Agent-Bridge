#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "ab_runner.py"
VALIDATOR = ROOT / "validate_outputs.py"


def _run(cmd: list[str], env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _reset_state(path: Path) -> None:
    path.write_text("{}", encoding="utf-8")


def _write_executor(script_path: Path, mode: str, state_path: Path) -> None:
    script = '''#!/usr/bin/env python3
import json
from pathlib import Path
import os
import sys

mode = os.environ.get("AB_VOICE_EXEC_MODE", "json")
state_path = Path("__STATE_PATH__")
state = {}
if state_path.exists():
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        state = {}

state.setdefault(mode, 0)
state[mode] += 1
state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

payload = json.loads(sys.stdin.read() or "{}")
output_file = payload.get("output_file")

if mode == "json":
    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(output_file).write_text("audio", encoding="utf-8")
    print(json.dumps({
        "status_code": 0,
        "status": "ok",
        "verify_status": "verified",
        "output_file": output_file,
        "message": "ok",
    }, ensure_ascii=False))
elif mode == "non_json":
    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(output_file).write_text("audio", encoding="utf-8")
    print(f"status=ok verify=verified status_code=0 output_file={output_file} message=ok")
elif mode == "retry_then_ok":
    if state[mode] < 2:
        print(json.dumps({
            "status_code": 1,
            "status": "failed",
            "verify_status": "mismatch",
            "message": "need_retry",
        }, ensure_ascii=False))
    else:
        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            Path(output_file).write_text("audio", encoding="utf-8")
        print(json.dumps({
            "status_code": 0,
            "status": "ok",
            "verify_status": "verified",
            "output_file": output_file,
            "message": "ok_after_retry",
        }, ensure_ascii=False))
elif mode == "conflict_status_verify":
    print(json.dumps({
        "status_code": 0,
        "status": "failed",
        "verify_status": "verified",
        "message": "ambiguous",
    }, ensure_ascii=False))
else:
    print(json.dumps({"status_code": 0, "status": "ok"}))
'''.replace("__STATE_PATH__", str(state_path).replace("\\", "\\\\"))
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o755)


def _run_runner(
    output_dir: Path,
    input_text: str,
    executor: str | None,
    mode: str,
    retry_limit: int,
    dry_run: bool = False,
    validate_outputs: bool = True,
    annotations: list[dict] | dict | None = None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(RUNNER),
        "--emit-voice",
        "--input-text",
        input_text,
        "--output-dir",
        str(output_dir),
        "--segment-limit",
        "200",
        "--plan-retry-limit",
        str(retry_limit),
    ]
    if dry_run:
        cmd.append("--dry-run")
    if annotations is not None:
        task_json = output_dir / "task_json.json"
        task_payload = {
            "task_id": f"{output_dir.name}-annotations",
            "input": {"text": input_text},
            "annotations": annotations,
        }
        task_json.write_text(json.dumps(task_payload, ensure_ascii=False), encoding="utf-8")
        cmd.extend(["--task-json", str(task_json)])
    env = os.environ.copy()
    if executor:
        env["NOVEL_PRESENT_VOICE_EXECUTOR"] = executor
        env["AB_VOICE_EXEC_MODE"] = mode

    result = _run(cmd, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"ab_runner failed: {result.stdout}{result.stderr}")

    payload = _load_json(output_dir / "result.json")
    if validate_outputs:
        validate = _run([sys.executable, str(VALIDATOR), "--output-dir", str(output_dir), "--require-plan"], env=os.environ.copy())
        if validate.returncode != 0:
            raise RuntimeError(f"validate_outputs failed: {validate.stdout}{validate.stderr}")
    return payload


def _read_first_voice_row(output_dir: Path) -> dict:
    rows_path = output_dir / "present_voice_results.jsonl"
    with rows_path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if raw:
                return json.loads(raw)
    raise AssertionError(f"missing voice result row in {rows_path}")


def _read_segments(output_dir: Path) -> list[dict]:
    path = output_dir / "segments.jsonl"
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if raw:
                rows.append(json.loads(raw))
    return rows


def _read_manifest(output_dir: Path) -> dict:
    return _load_json(output_dir / "manifest.json")


def _assert(condition: bool, msg: str) -> None:
    if not condition:
        raise AssertionError(msg)


def scenario_no_executor(tmpdir: Path) -> None:
    out = tmpdir / "no_executor"
    payload = _run_runner(
        output_dir=out,
        input_text="这是一个纯测试段落。",
        executor=None,
        mode="json",
        retry_limit=0,
    )

    _assert(payload.get("present_voice_status") == "pending", "expected pending when no executor set")
    _assert(payload.get("present_voice_summary", {}).get("ok_count") == 0, "expected 0 ok counts")


def scenario_json_executor(tmpdir: Path, executor: Path) -> None:
    out = tmpdir / "json_executor"
    payload = _run_runner(
        output_dir=out,
        input_text="这是一个普通测试段落，用于验证 JSON 回执解析。",
        executor=str(executor),
        mode="json",
        retry_limit=0,
    )

    summary = payload.get("present_voice_summary") or {}
    _assert(summary.get("ok_count") == 1, "json executor should report ok_count=1")
    _assert(summary.get("status_counts", {}).get("ok") == 1, "json executor should report status=ok")

    row = _read_first_voice_row(out)
    _assert(row.get("status") == "ok", "first row status should be ok")
    _assert(row.get("raw_status") == "ok", "first row raw_status should be ok")
    _assert(row.get("verify_status") == "verified", "first row verify_status should be verified")
    _assert(row.get("output_file_exists") is True, "json executor should emit output_file_exists=true")
    _assert(row.get("executed") is True, "executor-backed row should mark executed=true")


def scenario_non_json_executor(tmpdir: Path, executor: Path) -> None:
    out = tmpdir / "non_json_executor"
    payload = _run_runner(
        output_dir=out,
        input_text="这是一个普通测试段落，用于验证非 JSON 回执解析。",
        executor=str(executor),
        mode="non_json",
        retry_limit=0,
    )

    summary = payload.get("present_voice_summary") or {}
    _assert(summary.get("ok_count") == 1, "non-JSON executor should parse to ok")

    row = _read_first_voice_row(out)
    _assert(row.get("status") == "ok", "non-JSON executor row status should be ok")
    _assert(row.get("output_file_exists") is True, "non-JSON executor should report file existence")
    _assert(row.get("executed") is True, "executor-backed row should mark executed=true")


def scenario_retry_then_ok(tmpdir: Path, executor: Path, state_path: Path) -> None:
    out = tmpdir / "retry_then_ok"
    payload = _run_runner(
        output_dir=out,
        input_text="这是用于重试验证的文本段落。",
        executor=str(executor),
        mode="retry_then_ok",
        retry_limit=1,
    )

    summary = payload.get("present_voice_summary") or {}
    _assert(summary.get("ok_count") == 1, "retry executor should recover to ok_count=1")
    _assert(summary.get("attempts") == 2, "retry executor should attempt twice")
    _assert(summary.get("status_counts", {}).get("ok") == 1, "retry executor should have one ok status")

    if state_path.exists():
        state = _load_json(state_path)
        _assert(state.get("retry_then_ok") == 2, "executor should have been called twice")


def scenario_conflict_status_verify(tmpdir: Path, executor: Path) -> None:
    out = tmpdir / "conflict_status_verify"
    payload = _run_runner(
        output_dir=out,
        input_text="这是冲突状态回执测试段落。",
        executor=str(executor),
        mode="conflict_status_verify",
        retry_limit=0,
    )

    summary = payload.get("present_voice_summary") or {}
    _assert(summary.get("ok_count") == 0, "conflict status/verify should not be treated as ok")
    _assert(summary.get("status_counts", {}).get("failed") == 1, "conflict status/verify should be failed")

    row = _read_first_voice_row(out)
    _assert(row.get("status") == "failed", "conflict row status should be failed")
    _assert(row.get("raw_status") == "failed", "raw_status should be failed")
    _assert(row.get("verify_status") == "verified", "verify_status should be parsed")
    _assert(row.get("executed") is True, "executor-backed row should mark executed=true")


def scenario_dry_run(tmpdir: Path, executor: Path) -> None:
    out = tmpdir / "dry_run_queued"
    payload = _run_runner(
        output_dir=out,
        input_text="这是 dry-run 回执证据测试段落。",
        executor=str(executor),
        mode="json",
        retry_limit=0,
        dry_run=True,
        validate_outputs=False,
    )

    _assert(payload.get("present_voice_status") == "queued", "dry-run should report queued")
    _assert(payload.get("present_voice_summary", {}).get("segments") == 1, "dry-run should emit one segment")
    _assert(payload.get("present_voice_summary", {}).get("executed_count") == 0, "dry-run should not execute any segment")

    row = _read_first_voice_row(out)
    _assert(row.get("status") == "queued", "dry-run row status should be queued")
    _assert(row.get("executed") is False, "dry-run row should be executed=false")
    _assert(row.get("attempts") == 0, "dry-run attempts should be 0")
    _assert(row.get("reason") == "dry_run_no_call", "dry-run reason should be explicit")


def scenario_annotations_happy_path(tmpdir: Path) -> None:
    out = tmpdir / "annotations_happy"
    payload = _run_runner(
        output_dir=out,
        input_text="小雨：先说一句试音。\n\n周芷：再接着说一句。",
        executor=None,
        mode="json",
        retry_limit=0,
        annotations=[
            {
                "index": 0,
                "speaker": {
                    "id": "spk_xiaoyu",
                    "name": "小雨",
                    "gender": "female",
                    "confidence": 0.93,
                    "source": "test_subagent",
                },
                "emotion": {
                    "label": "happy",
                    "intensity": 2,
                    "confidence": 0.91,
                    "source": "test_subagent",
                },
            },
            {
                "index": 1,
                "speaker": {
                    "id": "spk_zhouzhi",
                    "name": "周芷",
                    "gender": "male",
                    "confidence": 0.95,
                    "source": "test_subagent",
                },
                "emotion": {
                    "label": "tense",
                    "intensity": 1,
                    "confidence": 0.88,
                    "source": "test_subagent",
                },
            },
        ],
    )

    _assert(payload["status"] == "ok", "annotation happy path should be ok")
    manifest = _read_manifest(out)
    annotation_summary = manifest.get("annotation_issues", {}).get("summary", {})
    _assert(annotation_summary.get("count", 1) == 0, "valid annotations should not emit issues")

    segs = _read_segments(out)
    _assert(segs[0]["speaker"]["id"] == "spk_xiaoyu", "segment 0 should keep injected speaker id")
    _assert(segs[0]["emotion"]["label"] == "happy", "segment 0 emotion should keep injected label")
    _assert(segs[1]["speaker"]["id"] == "spk_zhouzhi", "segment 1 should keep injected speaker id")
    _assert(segs[1]["emotion"]["label"] == "tense", "segment 1 emotion should keep injected label")
    _assert("annotation:" not in "".join(segs[0]["fallbacks"]), "valid annotations should not create annotation fallbacks")


def scenario_annotations_invalid_inputs(tmpdir: Path) -> None:
    out = tmpdir / "annotations_invalid"
    payload = _run_runner(
        output_dir=out,
        input_text="这是一个正常段落。\n\n这是第二个段落。",
        executor=None,
        mode="json",
        retry_limit=0,
        annotations=[
            {
                "index": 0,
                "speaker": {
                    "id": "",
                    "name": "",
                    "gender": "robot",
                    "confidence": 1.8,
                    "source": "test_subagent",
                },
                "emotion": {
                    "label": "ecstatic",
                    "intensity": 99,
                    "confidence": -1,
                    "source": "test_subagent",
                },
            },
            {
                "index": 999,
                "speaker": {
                    "id": "spk_out_of_range",
                    "name": "越界",
                    "gender": "male",
                    "confidence": 0.9,
                    "source": "test_subagent",
                },
            },
            {
                "index": "one",
                "speaker": {
                    "id": "spk_invalid_key",
                    "name": "无效索引",
                    "gender": "female",
                    "confidence": 0.9,
                },
            },
        ],
    )

    _assert(payload["status"] != "failed", "invalid annotations should not fail pipeline")
    manifest = _read_manifest(out)
    annotation_summary = manifest.get("annotation_issues", {}).get("summary", {})
    _assert(annotation_summary.get("count", 0) > 0, "invalid annotations should emit issues")
    _assert(annotation_summary.get("row_count", 0) >= 1, "invalid annotations should map to segment rows")

    segs = _read_segments(out)
    _assert(any("annotation:" in fb for fb in segs[0]["fallbacks"]), "invalid annotation should add annotation fallback")

    global_out = tmpdir / "annotations_invalid_global_root"
    payload = _run_runner(
        output_dir=global_out,
        input_text="这是一个正常段落。",
        executor=None,
        mode="json",
        retry_limit=0,
        annotations="bad-root",
    )
    manifest = _read_manifest(global_out)
    annotation_summary = manifest.get("annotation_issues", {}).get("summary", {})
    _assert(payload["status"] == "ok", "global-invalid annotations should still run")
    _assert(annotation_summary.get("global_count", 0) >= 1, "invalid root should be recorded as global issue")


def scenario_cli_adapter(tmpdir: Path, adapter_path: Path) -> None:
    out = tmpdir / "cli_adapter"
    payload = _run_runner(
        output_dir=out,
        input_text="这是 adapter 回归段落，测试标准 JSON 协议。",
        executor=f"python3 {adapter_path}",
        mode="json",
        retry_limit=0,
    )

    summary = payload.get("present_voice_summary") or {}
    _assert(summary.get("ok_count") == 1, "cli adapter should report ok_count=1")
    _assert(summary.get("executed_count") == 1, "cli adapter should execute one plan")
    _assert(summary.get("status_counts", {}).get("ok") == 1, "cli adapter should report status=ok")

    row = _read_first_voice_row(out)
    _assert(row.get("status") == "ok", "cli adapter row status should be ok")
    _assert(row.get("executed") is True, "cli adapter row should mark executed=true")
    _assert(row.get("status_code") == 0, "cli adapter row status_code should be 0")
    _assert(row.get("output_file_exists") is True, "cli adapter should report output_file_exists=true")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lightweight regression checks for novel_tts_embodied v1 present_voice paths")
    parser.add_argument("--workdir", default=None)
    args = parser.parse_args()

    base = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="novel_tts_embodied_regression_"))
    base.mkdir(parents=True, exist_ok=True)

    executor = base / "mock_present_voice.py"
    state_path = base / "executor_state.json"
    _reset_state(state_path)
    _write_executor(executor, "json", state_path)

    try:
        scenario_no_executor(base)
        _reset_state(state_path)
        scenario_json_executor(base, executor)

        _reset_state(state_path)
        _write_executor(executor, "non_json", state_path)
        scenario_non_json_executor(base, executor)

        _reset_state(state_path)
        _write_executor(executor, "retry_then_ok", state_path)
        scenario_retry_then_ok(base, executor, state_path)

        _reset_state(state_path)
        _write_executor(executor, "conflict_status_verify", state_path)
        scenario_conflict_status_verify(base, executor)

        _reset_state(state_path)
        _write_executor(executor, "json", state_path)
        scenario_dry_run(base, executor)

        scenario_annotations_happy_path(base)
        scenario_annotations_invalid_inputs(base)

        scenario_cli_adapter(
            tmpdir=base,
            adapter_path=ROOT / "adapters" / "present_voice_cli.py",
        )
    finally:
        pass

    print(f"regression checks passed: {base}")


if __name__ == "__main__":
    main()
