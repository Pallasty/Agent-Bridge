from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs/design/voice-scene"
RESULT_PATH = (
    VOICE_SCENE / "s637_story_render_real_worker_adapter_implementation.json"
)
SCHEMA_PATH = (
    VOICE_SCENE / "story_render_real_worker_adapter_implementation.schema.json"
)
ADR_PATH = VOICE_SCENE / "S637_STORY_RENDER_REAL_WORKER_ADAPTER_IMPLEMENTATION.md"
WORKER_PATH = ROOT / "scripts/story_render_one_shot_worker.py"
EXECUTOR_PATH = ROOT / "scripts/story_bounded_render_executor.py"


def load_result() -> dict[str, object]:
    value = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("S637 result must be an object")
    return value


def digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def receipt_projection(result: dict[str, object]) -> dict[str, object]:
    names = (
        "decision",
        "implementation",
        "response_policy",
        "current_real_path",
        "blockers",
        "authority",
        "runtime_effects",
        "claims",
        "nonclaims",
        "next_gate",
    )
    return {name: result[name] for name in names}


def historical_payload(path: str, expected_sha256: str) -> bytes:
    current = ROOT / path
    if current.is_file():
        payload = current.read_bytes()
        if hashlib.sha256(payload).hexdigest() == expected_sha256:
            return payload
    revisions = subprocess.run(
        ["git", "log", "--all", "--format=%H", "--", path],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.splitlines()
    for revision in revisions:
        shown = subprocess.run(
            ["git", "show", f"{revision}:{path}"],
            cwd=ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if (
            shown.returncode == 0
            and hashlib.sha256(shown.stdout).hexdigest() == expected_sha256
        ):
            return shown.stdout
    raise AssertionError(f"no evidence payload matches:{path}")


def function_source(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function missing:{name}")


def called_names(node: ast.AST) -> set[str]:
    result: set[str] = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        if isinstance(item.func, ast.Name):
            result.add(item.func.id)
        elif isinstance(item.func, ast.Attribute):
            result.add(item.func.attr)
    return result


class StoryRenderRealWorkerAdapterContractTests(unittest.TestCase):
    def test_receipt_is_schema_valid_and_hash_bound(self) -> None:
        result = load_result()
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(result))
        self.assertEqual(errors, [])
        self.assertEqual(
            result["receipt_sha256"],
            digest(receipt_projection(result)),
        )

    def test_source_evidence_matches_current_or_landed_history(self) -> None:
        result = load_result()
        source_evidence = result["source_evidence"]
        self.assertGreaterEqual(len(source_evidence), 8)
        for entry in source_evidence:
            payload = historical_payload(entry["path"], entry["sha256"])
            self.assertEqual(hashlib.sha256(payload).hexdigest(), entry["sha256"])

    def test_authority_loaders_exist_only_inside_real_execution(self) -> None:
        source = WORKER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        process = function_source(tree, "process_request")
        execute_real = function_source(tree, "execute_real")

        self.assertNotIn("_load_installed_composition", called_names(process))
        self.assertNotIn("_load_executor", called_names(process))
        self.assertIn("_load_installed_composition", called_names(execute_real))
        self.assertIn("_load_executor", called_names(execute_real))
        self.assertNotIn("onnxruntime", source)
        self.assertNotIn("import torch", source)
        self.assertNotIn("sounddevice", source)
        self.assertNotIn("os.environ", source)
        self.assertNotIn("subprocess", source)

    def test_real_path_checks_custody_before_key_and_nonce_before_output(self) -> None:
        worker_source = WORKER_PATH.read_text(encoding="utf-8")
        executor_source = EXECUTOR_PATH.read_text(encoding="utf-8")
        execute_source = ast.get_source_segment(
            worker_source,
            function_source(ast.parse(worker_source), "execute_real"),
        )
        self.assertIsNotNone(execute_source)
        self.assertLess(
            execute_source.index("_require_compatible_execution_contract("),
            execute_source.index("_load_installed_composition()"),
        )
        self.assertLess(
            execute_source.index("_load_installed_composition()"),
            execute_source.index("_load_executor()"),
        )
        self.assertLess(
            executor_source.index("_consume_nonce("),
            executor_source.index("output.mkdir(mode=0o700)"),
        )

    def test_s637_closes_only_worker_entrypoint_and_keeps_runtime_closed(self) -> None:
        result = load_result()
        self.assertEqual(result["blockers"]["B1_REAL_WORKER_ENTRYPOINT"], "closed")
        self.assertTrue(
            all(
                value == "open"
                for key, value in result["blockers"].items()
                if key != "B1_REAL_WORKER_ENTRYPOINT"
            )
        )
        self.assertTrue(all(value is False for value in result["authority"].values()))
        self.assertFalse(result["claims"]["real_render_executable"])
        self.assertFalse(result["claims"]["runtime_adoption_ready"])
        self.assertEqual(
            result["next_gate"],
            {
                "id": "S638",
                "name": "story_render_artifact_identity_and_python_package",
                "authority": "source_and_isolated_package_tests",
                "runtime_enablement": "not_authorized",
            },
        )
        adr = ADR_PATH.read_text(encoding="utf-8")
        self.assertIn("source-only one-shot Worker implementation", adr)
        self.assertIn("S638", adr)


if __name__ == "__main__":
    unittest.main()
