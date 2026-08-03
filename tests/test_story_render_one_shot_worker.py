from __future__ import annotations

import copy
import importlib.util
import io
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / "scripts/story_render_one_shot_worker.py"
CODEC_PATH = ROOT / "scripts/story_render_worker_protocol.py"
CONTRACT_PATH = (
    ROOT
    / "docs/design/voice-scene/s620_story_render_one_shot_worker_protocol_contract.json"
)
EXECUTION_CONTRACT_PATH = (
    ROOT / "docs/design/voice-scene/s604_story_bounded_render_execution_contract.json"
)
PREFLIGHT_RECEIPT_PATH = (
    ROOT / "docs/design/voice-scene/s602_story_fixture_mcp_preflight_receipt.json"
)
ACCEPTED_RECEIPT_PATH = (
    ROOT / "docs/design/voice-scene/s603_story_fixture_bounded_render_receipt.json"
)
RUNTIME_CONTRACT_PATH = (
    ROOT
    / "docs/design/voice-scene/s608_story_executor_authority_model_nonce_contract.json"
)
REQUEST_ID = "12" * 16


def load(path: Path, name: str):
    if not path.is_file():
        raise AssertionError(f"missing module:{path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load module:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contract() -> dict[str, object]:
    value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("S620 contract must be an object")
    return value


def request() -> dict[str, object]:
    protocol_contract = contract()
    fixture = copy.deepcopy(protocol_contract["request"]["fixture"])
    return {
        "protocol": protocol_contract["protocol"]["name"],
        "request_id": REQUEST_ID,
        "fixture": fixture,
        "authorization": {
            "authorization_id": "story-render-auth-" + "ab" * 16,
            "contract_sha256": protocol_contract["contract_sha256"],
            "preflight_sha256": fixture["preflight_sha256"],
            "output_directory": (
                protocol_contract["output_custody"]["root"] + "/" + REQUEST_ID
            ),
            "action": "render",
            "issued_at": "2026-08-02T12:00:00+00:00",
            "expires_at": "2026-08-02T12:05:00+00:00",
            "single_use_nonce": "cd" * 32,
            "issuer": "agent-bridge-owner-console",
            "subject": "story-bounded-render-executor",
            "key_id": "story-render-owner-v1",
            "mac_sha256": "ef" * 32,
        },
    }


def encoded(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"JSON object required:{path}")
    return value


def private_receipt() -> dict[str, object]:
    return {
        "schema": "agent_bridge.story_bounded_render_receipt.v1",
        "status": "bounded_render_machine_verified",
        "authorization_id": "PRIVATE-AUTHORIZATION-MARKER",
        "segments": [
            {"audio_path": "/private/00.wav"},
            {"audio_path": "/private/01.wav"},
            {"audio_path": "/private/02.wav"},
        ],
        "assembly": {
            "sha256": "34" * 32,
            "sample_rate_hz": 24_000,
            "channels": 1,
            "frames": 72_000,
            "duration_seconds": 3.0,
            "audio_path": "/private/chapter.wav",
            "gap_seconds": [1.0, 1.0],
        },
        "playback_authorized": False,
        "memory_authorized": False,
        "runtime_effects": {
            "created_output_directory": True,
            "loaded_model": True,
            "executed_onnx": True,
            "rendered_audio": True,
            "played_audio": False,
            "recorded_audio": False,
            "wrote_cache": False,
            "wrote_memory": False,
            "consumed_render_nonce": True,
        },
    }


class StoryRenderOneShotWorkerTests(unittest.TestCase):
    def test_valid_request_emits_one_strict_redacted_success_response(self) -> None:
        worker = load(WORKER_PATH, "s637_worker_success")
        codec = load(CODEC_PATH, "s637_codec_success")
        calls: list[dict[str, object]] = []

        def execute(decoded: dict[str, object]) -> dict[str, object]:
            calls.append(copy.deepcopy(decoded))
            return private_receipt()

        raw = worker.process_request(
            encoded(request()),
            protocol_contract=contract(),
            codec=codec,
            execute=execute,
        )

        response = codec.validate_worker_response(
            raw,
            contract(),
            expected_request_id=REQUEST_ID,
        )
        self.assertEqual(calls, [request()])
        self.assertEqual(
            response,
            {
                "protocol": "agent_bridge.story-render-worker.v1",
                "request_id": REQUEST_ID,
                "status": "success",
                "render_id": REQUEST_ID,
                "segment_count": 3,
                "assembly": {
                    "sha256": "34" * 32,
                    "sample_rate_hz": 24_000,
                    "channels": 1,
                    "frames": 72_000,
                    "duration_seconds": 3.0,
                },
                "playback_authorized": False,
                "memory_authorized": False,
            },
        )
        self.assertNotIn(b"PRIVATE-AUTHORIZATION-MARKER", raw)
        self.assertNotIn(b"/private/", raw)

    def test_invalid_request_returns_fixed_error_without_calling_executor(self) -> None:
        worker = load(WORKER_PATH, "s637_worker_invalid_request")
        codec = load(CODEC_PATH, "s637_codec_invalid_request")
        calls: list[dict[str, object]] = []

        try:
            raw = worker.process_request(
                b'{"authorization":"TOP-SECRET-MARKER"}',
                protocol_contract=contract(),
                codec=codec,
                execute=lambda decoded: calls.append(decoded),
            )
        except Exception as error:  # RED: the adapter must contain codec failures.
            self.fail(f"process_request raised {type(error).__name__}")

        response = codec.validate_worker_response(
            raw,
            contract(),
            expected_request_id="0" * 32,
        )
        self.assertEqual(
            response,
            {
                "protocol": "agent_bridge.story-render-worker.v1",
                "request_id": "0" * 32,
                "status": "error",
                "code": "invalid_request",
                "retryable": False,
            },
        )
        self.assertEqual(calls, [])
        self.assertNotIn(b"TOP-SECRET-MARKER", raw)

    def test_typed_execution_failure_returns_only_contract_error_fields(self) -> None:
        worker = load(WORKER_PATH, "s637_worker_typed_failure")
        codec = load(CODEC_PATH, "s637_codec_typed_failure")

        def reject(_decoded: dict[str, object]) -> dict[str, object]:
            raise worker.WorkerFailure(
                "model_rejected",
                retryable=True,
                private_detail="TOP-SECRET-MODEL-PATH",
            )

        try:
            raw = worker.process_request(
                encoded(request()),
                protocol_contract=contract(),
                codec=codec,
                execute=reject,
            )
        except Exception as error:  # RED: execution failures become responses.
            self.fail(f"process_request raised {type(error).__name__}")

        self.assertEqual(
            codec.validate_worker_response(
                raw,
                contract(),
                expected_request_id=REQUEST_ID,
            ),
            {
                "protocol": "agent_bridge.story-render-worker.v1",
                "request_id": REQUEST_ID,
                "status": "error",
                "code": "model_rejected",
                "retryable": True,
            },
        )
        self.assertNotIn(b"TOP-SECRET-MODEL-PATH", raw)

    def test_invalid_typed_failure_code_degrades_to_internal_failure(self) -> None:
        worker = load(WORKER_PATH, "s637_worker_invalid_typed_failure")
        codec = load(CODEC_PATH, "s637_codec_invalid_typed_failure")

        def reject(_decoded: dict[str, object]) -> dict[str, object]:
            raise worker.WorkerFailure(
                "TOP-SECRET-NOT-A-PUBLIC-CODE",
                retryable=False,
            )

        try:
            raw = worker.process_request(
                encoded(request()),
                protocol_contract=contract(),
                codec=codec,
                execute=reject,
            )
        except Exception as error:  # RED: invalid internal codes cannot escape.
            self.fail(f"process_request raised {type(error).__name__}")

        response = codec.validate_worker_response(
            raw,
            contract(),
            expected_request_id=REQUEST_ID,
        )
        self.assertEqual(response.get("code"), "internal_failure")
        self.assertNotIn(b"TOP-SECRET", raw)

    def test_unexpected_or_malformed_execution_result_fails_closed(self) -> None:
        worker = load(WORKER_PATH, "s637_worker_internal_failure")
        codec = load(CODEC_PATH, "s637_codec_internal_failure")

        def unexpected(_decoded: dict[str, object]) -> dict[str, object]:
            raise RuntimeError("TOP-SECRET-TRACEBACK-MARKER")

        def malformed(_decoded: dict[str, object]) -> dict[str, object]:
            value = private_receipt()
            value["schema"] = "wrong"
            value["assembly"]["audio_path"] = "/private/chapter.wav"
            return value

        for execute, marker in (
            (unexpected, b"TOP-SECRET-TRACEBACK-MARKER"),
            (malformed, b"/private/chapter.wav"),
        ):
            with self.subTest(execute=execute.__name__):
                try:
                    raw = worker.process_request(
                        encoded(request()),
                        protocol_contract=contract(),
                        codec=codec,
                        execute=execute,
                    )
                except Exception as error:  # RED: internals never escape.
                    self.fail(f"process_request raised {type(error).__name__}")
                response = codec.validate_worker_response(
                    raw,
                    contract(),
                    expected_request_id=REQUEST_ID,
                )
                self.assertEqual(response.get("code"), "internal_failure")
                self.assertNotIn(marker, raw)

    def test_private_receipt_with_forbidden_runtime_effect_fails_closed(self) -> None:
        worker = load(WORKER_PATH, "s637_worker_effect_failure")
        codec = load(CODEC_PATH, "s637_codec_effect_failure")
        unsafe = private_receipt()
        unsafe["runtime_effects"]["played_audio"] = True

        raw = worker.process_request(
            encoded(request()),
            protocol_contract=contract(),
            codec=codec,
            execute=lambda _decoded: unsafe,
        )

        response = codec.validate_worker_response(
            raw,
            contract(),
            expected_request_id=REQUEST_ID,
        )
        self.assertEqual(response.get("code"), "internal_failure")

    def test_main_reads_once_to_the_bound_and_writes_exactly_one_response(self) -> None:
        worker = load(WORKER_PATH, "s637_worker_main")
        codec = load(CODEC_PATH, "s637_codec_main")

        class RecordingInput(io.BytesIO):
            def __init__(self, payload: bytes) -> None:
                super().__init__(payload)
                self.read_sizes: list[int] = []

            def read(self, size: int = -1) -> bytes:
                self.read_sizes.append(size)
                return super().read(size)

        class RecordingOutput(io.BytesIO):
            def __init__(self) -> None:
                super().__init__()
                self.write_count = 0

            def write(self, payload: bytes) -> int:
                self.write_count += 1
                return super().write(payload)

        stdin = RecordingInput(encoded(request()))
        stdout = RecordingOutput()

        self.assertTrue(hasattr(worker, "main"), "one-shot main is missing")
        exit_code = worker.main(
            stdin=stdin,
            stdout=stdout,
            protocol_contract=contract(),
            codec=codec,
            execute=lambda _decoded: private_receipt(),
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            stdin.read_sizes,
            [contract()["protocol"]["stdin_max_bytes"] + 1],
        )
        self.assertEqual(stdout.write_count, 1)
        self.assertFalse(stdout.getvalue().endswith(b"\n"))
        self.assertEqual(
            codec.validate_worker_response(
                stdout.getvalue(),
                contract(),
                expected_request_id=REQUEST_ID,
            )["status"],
            "success",
        )

    def test_fixed_executor_request_uses_only_repository_bound_fixture_data(
        self,
    ) -> None:
        worker = load(WORKER_PATH, "s637_worker_fixed_request")
        self.assertTrue(
            hasattr(worker, "build_fixed_executor_request"),
            "fixed executor request builder is missing",
        )

        built = worker.build_fixed_executor_request(
            decoded_request=request(),
            protocol_contract=contract(),
            execution_contract=read_object(EXECUTION_CONTRACT_PATH),
            preflight_receipt=read_object(PREFLIGHT_RECEIPT_PATH),
            accepted_receipt=read_object(ACCEPTED_RECEIPT_PATH),
            runtime_contract=read_object(RUNTIME_CONTRACT_PATH),
        )

        self.assertEqual(
            set(built),
            {
                "preflight",
                "model",
                "output_directory",
                "playback",
                "record",
                "write_memory",
            },
        )
        self.assertEqual(
            built["output_directory"],
            request()["authorization"]["output_directory"],
        )
        self.assertIs(built["playback"], False)
        self.assertIs(built["record"], False)
        self.assertIs(built["write_memory"], False)
        self.assertEqual(
            [row["text"] for row in built["preflight"]["render_requests"]],
            ["苏岚回答。", "我听见钟声了。", "苏岚打开了旧木门。"],
        )
        self.assertEqual(
            [row["event_id"] for row in built["preflight"]["render_requests"]],
            [
                "s620-fixed-chapter-2-segment-0",
                "s620-fixed-chapter-2-segment-1",
                "s620-fixed-chapter-2-segment-2",
            ],
        )
        self.assertEqual(
            built["preflight"]["assembly_gap_seconds"],
            [1.0, 1.0],
        )
        self.assertEqual(
            set(built["model"]),
            {"inference_path", "model_path", "tts_dir"},
        )
        self.assertNotIn("authorization", built)

    def test_current_contract_mismatch_rejects_before_installed_key_composition(
        self,
    ) -> None:
        worker = load(WORKER_PATH, "s637_worker_real_gate")
        codec = load(CODEC_PATH, "s637_codec_real_gate")
        self.assertTrue(
            hasattr(worker, "execute_real"),
            "real execution function is missing",
        )
        decoded = codec.decode_request(encoded(request()), contract())
        composition_loads: list[bool] = []
        worker._load_installed_composition = lambda: composition_loads.append(True)

        with self.assertRaises(worker.WorkerFailure) as caught:
            worker.execute_real(decoded, protocol_contract=contract())

        self.assertEqual(caught.exception.code, "custody_rejected")
        self.assertIs(caught.exception.retryable, False)
        self.assertEqual(composition_loads, [])

    def test_real_subprocess_emits_one_custody_error_without_stderr(self) -> None:
        codec = load(CODEC_PATH, "s637_codec_subprocess")
        completed = subprocess.run(
            ["/usr/bin/python3", str(WORKER_PATH)],
            cwd=ROOT,
            input=encoded(request()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",
            },
            check=False,
            timeout=10,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, b"")
        self.assertTrue(completed.stdout, "subprocess emitted no response")
        self.assertEqual(
            codec.validate_worker_response(
                completed.stdout,
                contract(),
                expected_request_id=REQUEST_ID,
            ),
            {
                "protocol": "agent_bridge.story-render-worker.v1",
                "request_id": REQUEST_ID,
                "status": "error",
                "code": "custody_rejected",
                "retryable": False,
            },
        )
        self.assertEqual(completed.stdout.count(b'{"code"'), 1)
        self.assertNotIn(b"authorization", completed.stdout)


if __name__ == "__main__":
    unittest.main()
