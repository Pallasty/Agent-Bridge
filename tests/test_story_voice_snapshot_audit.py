from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_voice_snapshot_audit.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_snapshot_static_audit.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_snapshot_audit", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_variant(root: Path, name: str, *, missing: str | None = None) -> None:
    variant = root / name
    variant.mkdir(parents=True)
    device, precision = name.split("_", 1)
    filenames = {
        "code_predictor": "code_predictor.onnx",
        "codec_embed": "codec_embed.onnx",
    }
    (variant / "manifest.json").write_text(
        json.dumps(
            {
                "device": device,
                "precision": precision,
                "execution_provider": (
                    "CPUExecutionProvider"
                    if device == "cpu"
                    else "CUDAExecutionProvider"
                ),
                "sub_models": {
                    key: {"filename": value}
                    for key, value in filenames.items()
                },
            }
        )
    )
    for filename in filenames.values():
        if filename != missing:
            (variant / filename).write_bytes(b"not-executed-onnx-fixture")


def make_snapshot(root: Path, *, license_file: bool = True) -> None:
    root.mkdir()
    (root / "README.md").write_text("---\nlicense: apache-2.0\n---\n")
    (root / "requirements.txt").write_text(
        "onnxruntime>=1.20\nnumpy\nsoundfile\n"
    )
    (root / "inference.py").write_text("import numpy\n")
    if license_file:
        (root / "LICENSE").write_text("Apache License\nVersion 2.0\n")
    for name in (
        "cpu_fp16",
        "cpu_fp32",
        "cpu_int4",
        "cuda_fp16",
        "cuda_fp32",
        "cuda_int4",
    ):
        make_variant(root, name)


def test_complete_snapshot_inventory_never_executes_model_code(
    tmp_path: Path,
) -> None:
    audit = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)

    receipt = audit.audit_snapshot(
        snapshot,
        repository="owner/model",
        revision="a" * 40,
        expected_size_bytes=None,
        hash_files=False,
    )

    assert receipt["inventory"]["variant_count"] == 6
    assert receipt["inventory"]["incomplete_files"] == []
    assert receipt["inventory"]["symlinks"] == []
    assert receipt["manifest_audit"]["missing_files"] == []
    assert receipt["runtime_effects"] == {
        "imported_community_code": False,
        "loaded_onnx": False,
        "installed_dependencies": False,
        "used_gpu": False,
        "rendered_audio": False,
        "played_audio": False,
    }


def test_mutable_revision_and_missing_standalone_license_block_promotion(
    tmp_path: Path,
) -> None:
    audit = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot, license_file=False)

    receipt = audit.audit_snapshot(
        snapshot,
        repository="owner/model",
        revision="master",
        expected_size_bytes=None,
        hash_files=False,
    )

    assert receipt["status"] == "blocked"
    assert receipt["license_audit"] == {
        "declared": "apache-2.0",
        "standalone_file": None,
        "status": "declaration_only",
    }
    assert receipt["blockers"] == [
        "revision_not_immutable",
        "standalone_license_file_missing",
    ]


def test_manifest_reference_to_missing_model_is_blocked(tmp_path: Path) -> None:
    audit = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    (snapshot / "cpu_int4" / "codec_embed.onnx").unlink()

    receipt = audit.audit_snapshot(
        snapshot,
        repository="owner/model",
        revision="b" * 40,
        expected_size_bytes=None,
        hash_files=False,
    )

    assert receipt["status"] == "blocked"
    assert receipt["manifest_audit"]["missing_files"] == [
        "cpu_int4/codec_embed.onnx"
    ]
    assert "manifest_references_missing_files" in receipt["blockers"]


def test_incomplete_file_and_symlink_are_fail_closed(tmp_path: Path) -> None:
    audit = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    (snapshot / "partial.onnx.incomplete").write_bytes(b"partial")
    (snapshot / "escape.onnx").symlink_to("/tmp/outside.onnx")

    receipt = audit.audit_snapshot(
        snapshot,
        repository="owner/model",
        revision="c" * 40,
        expected_size_bytes=None,
        hash_files=False,
    )

    assert receipt["inventory"]["incomplete_files"] == [
        "partial.onnx.incomplete"
    ]
    assert receipt["inventory"]["symlinks"] == ["escape.onnx"]
    assert "incomplete_files_present" in receipt["blockers"]
    assert "symlinks_present" in receipt["blockers"]


def test_python_static_audit_flags_process_network_and_dynamic_calls(
    tmp_path: Path,
) -> None:
    audit = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    (snapshot / "inference.py").write_text(
        "import requests\nimport subprocess\n"
        "subprocess.run(['x'])\nexec('x = 1')\n"
    )

    receipt = audit.audit_snapshot(
        snapshot,
        repository="owner/model",
        revision="d" * 40,
        expected_size_bytes=None,
        hash_files=False,
    )

    finding = next(
        row
        for row in receipt["python_audit"]
        if row["path"] == "inference.py"
    )
    assert finding["findings"] == [
        "dynamic_execution:exec",
        "network_import:requests",
        "process_execution:subprocess.run",
    ]
    assert "python_dangerous_primitives_present" in receipt["blockers"]


def test_expected_size_mismatch_is_blocked(tmp_path: Path) -> None:
    audit = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)

    receipt = audit.audit_snapshot(
        snapshot,
        repository="owner/model",
        revision="e" * 40,
        expected_size_bytes=1,
        hash_files=False,
    )

    assert receipt["integrity"]["expected_size_bytes"] == 1
    assert receipt["integrity"]["size_matches"] is False
    assert "snapshot_size_mismatch" in receipt["blockers"]


def test_blocked_snapshot_receipt_validates_against_schema(
    tmp_path: Path,
) -> None:
    jsonschema = __import__("jsonschema")
    audit = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot, license_file=False)
    receipt = audit.audit_snapshot(
        snapshot,
        repository="owner/model",
        revision="master",
        expected_size_bytes=None,
        hash_files=False,
    )

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(receipt, schema)


def test_onnx_inventory_collects_operators_without_external_data_load(
    tmp_path: Path,
) -> None:
    audit = load_module()
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    model_path = snapshot / "cpu_int4" / "talker.onnx"
    model_path.parent.mkdir()
    model_path.write_bytes(b"fixture")
    calls = []

    def load_model(path: str, *, load_external_data: bool):
        calls.append((path, load_external_data))
        return SimpleNamespace(
            graph=SimpleNamespace(
                node=[
                    SimpleNamespace(domain="", op_type="MatMul"),
                    SimpleNamespace(
                        domain="com.microsoft", op_type="MatMulNBits"
                    ),
                ],
                initializer=[
                    SimpleNamespace(
                        data_location=1,
                        external_data=[
                            SimpleNamespace(
                                key="location", value="talker.onnx.data"
                            )
                        ],
                    ),
                    SimpleNamespace(
                        data_location=1,
                        external_data=[
                            SimpleNamespace(
                                key="location", value="talker.onnx.data"
                            )
                        ],
                    ),
                ],
            ),
            opset_import=[
                SimpleNamespace(domain="", version=18),
                SimpleNamespace(domain="com.microsoft", version=1),
            ],
        )

    result = audit.audit_onnx_graphs(snapshot, load_model=load_model)

    assert calls == [(str(model_path), False)]
    assert result["status"] == "inventoried"
    assert result["model_count"] == 1
    assert result["operators"] == [
        {"domain": "ai.onnx", "op_type": "MatMul", "count": 1},
        {
            "domain": "com.microsoft",
            "op_type": "MatMulNBits",
            "count": 1,
        },
    ]
    assert result["external_data"] == [
        {
            "model": "cpu_int4/talker.onnx",
            "location": "talker.onnx.data",
            "safe_relative": True,
            "exists": False,
        }
    ]


def test_snapshot_receipt_can_include_onnx_inventory(tmp_path: Path) -> None:
    audit = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)

    def load_model(_path: str, *, load_external_data: bool):
        assert load_external_data is False
        return SimpleNamespace(
            graph=SimpleNamespace(node=[], initializer=[]),
            opset_import=[],
        )

    receipt = audit.audit_snapshot(
        snapshot,
        repository="owner/model",
        revision="f" * 40,
        expected_size_bytes=None,
        hash_files=False,
        onnx_loader=load_model,
    )

    assert receipt["onnx_audit"]["status"] == "inventoried"
    assert receipt["onnx_audit"]["model_count"] == 12
