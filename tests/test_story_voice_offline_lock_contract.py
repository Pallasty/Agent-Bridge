from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_voice_offline_lock_contract.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_offline_lock_contract.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_offline_lock_contract", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs(tmp_path: Path) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "source-model"
    converter = tmp_path / "community-converter"
    current = tmp_path / "current-onnx"
    for path in (source, converter, current):
        path.mkdir()
    s5s = {
        "status": "audited_lock_and_execution_blocked",
        "snapshot": str(converter),
        "source_identity": {
            "files": {
                "optimize.py": "a" * 64,
                "user_script.py": "b" * 64,
                "requirements.txt": "c" * 64,
            }
        },
    }
    s5r = {
        "weight_payload_fixed_revision_equivalent": True,
        "source": {"snapshot": str(source)},
        "current_onnx_snapshot": str(current),
    }
    return {
        "s5s_receipt": s5s,
        "s5r_receipt": s5r,
        "workspace": tmp_path / "future-workspace",
        "wheelhouse": tmp_path / "future-wheelhouse",
        "venv": tmp_path / "future-venv",
        "available_bytes": 512 * 1024**3,
    }


def test_contract_selects_exact_critical_direct_versions(tmp_path: Path) -> None:
    contract = load_module().build_contract(**inputs(tmp_path))
    selected = {
        item["name"]: item["version"]
        for item in contract["dependency_lock"]["critical_direct_pins"]
    }

    assert selected == {
        "python": "3.12.13",
        "torch": "2.12.0+cpu",
        "torchvision": "0.27.0+cpu",
        "transformers": "4.57.3",
        "olive-ai": "0.13.0",
        "onnx": "1.21.0",
        "onnxruntime": "1.27.0",
    }
    assert contract["dependency_lock"]["critical_direct_pins_exact"] is True
    assert contract["dependency_lock"]["transitive_lock_complete"] is False
    assert contract["dependency_lock"]["wheel_hash_ledger_complete"] is False


def test_contract_excludes_unused_or_rejected_packages(tmp_path: Path) -> None:
    contract = load_module().build_contract(**inputs(tmp_path))
    excluded = {
        item["name"]: item["reason"]
        for item in contract["dependency_lock"]["excluded"]
    }

    assert "not_imported_by_converter" in excluded["torchaudio"]
    assert "modelbuilder_path_rejected" in excluded["onnxruntime-genai"]


def test_contract_requires_absent_disjoint_destinations(tmp_path: Path) -> None:
    kwargs = inputs(tmp_path)
    kwargs["workspace"].mkdir()
    with pytest.raises(ValueError, match="must not already exist"):
        load_module().build_contract(**kwargs)

    kwargs = inputs(tmp_path / "overlap")
    kwargs["workspace"] = (
        Path(kwargs["s5s_receipt"]["snapshot"]) / "nested-workspace"
    )
    with pytest.raises(ValueError, match="overlaps protected path"):
        load_module().build_contract(**kwargs)


def test_install_template_is_offline_and_converter_stays_blocked(
    tmp_path: Path,
) -> None:
    contract = load_module().build_contract(**inputs(tmp_path))
    install = contract["commands"]["offline_install_argv_template"]

    assert "--no-index" in install
    assert "--find-links" in install
    assert "--require-hashes" in install
    assert contract["commands"]["converter_argv"] is None
    assert contract["readiness"]["offline_install_ready"] is False
    assert contract["readiness"]["converter_execution_ready"] is False


def test_contract_records_zero_runtime_effects(tmp_path: Path) -> None:
    contract = load_module().build_contract(**inputs(tmp_path))

    assert set(contract["runtime_effects"].values()) == {False}
    assert contract["status"] == "direct_lock_contract_ready_wheelhouse_pending"


def test_repository_shape_validates_against_schema(tmp_path: Path) -> None:
    jsonschema = __import__("jsonschema")
    contract = load_module().build_contract(**inputs(tmp_path))

    jsonschema.validate(contract, json.loads(SCHEMA_PATH.read_text()))
