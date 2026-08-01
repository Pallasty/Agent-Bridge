from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_bounded_render_executor_source_review.py"
EXECUTOR_PATH = ROOT / "scripts" / "story_bounded_render_executor.py"
EXECUTOR_TEST_PATH = ROOT / "tests" / "test_story_bounded_render_executor.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
S605_PATH = VOICE_SCENE / "s605_story_bounded_render_executor_implementation_review.json"
S604_PATH = VOICE_SCENE / "s604_story_bounded_render_execution_contract.json"
RUNNER_PATH = ROOT / "scripts" / "story_voice_existing_onnx_trusted_runner.py"
SCHEMA_PATH = VOICE_SCENE / "story_bounded_render_executor_source_review.schema.json"
RECEIPT_PATH = VOICE_SCENE / "s607_story_bounded_render_executor_source_review.json"


def load_module():
    assert MODULE_PATH.exists(), "S607 source-review module is missing"
    spec = importlib.util.spec_from_file_location(
        "story_bounded_render_executor_source_review", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    module = load_module()
    kwargs = {
        "executor_path": EXECUTOR_PATH,
        "executor_test_path": EXECUTOR_TEST_PATH,
        "implementation_review_path": S605_PATH,
        "execution_contract_path": S604_PATH,
        "trusted_runner_path": RUNNER_PATH,
    }
    return module.build_source_review(**{**kwargs, **overrides})


def test_review_accepts_source_but_keeps_runtime_blocked() -> None:
    result = build()

    assert result["status"] == "story_bounded_render_executor_source_reviewable"
    assert result["decision"] == "source_implementation_accepted_runtime_blocked"
    assert result["source"]["executor_path"] == str(EXECUTOR_PATH.resolve())
    assert len(result["source"]["executor_sha256"]) == 64
    assert result["source"]["has_cli_entrypoint"] is False
    assert result["source"]["has_mcp_or_rust_wiring"] is False
    assert result["implementation_present"] is True
    assert result["deployment_authorized"] is False
    assert result["execution_authorized"] is False
    assert all(value is False for value in result["runtime_effects"].values())


def test_review_proves_authority_model_nonce_and_output_order() -> None:
    result = build()

    assert result["call_order"] == [
        "validate_contract",
        "validate_request",
        "validate_authorization",
        "model_verifier",
        "consume_nonce",
        "create_output_directory",
        "load_runner",
    ]
    assert result["boundaries"] == {
        "external_authority_verifier_required": True,
        "external_model_bundle_verifier_required": True,
        "authority_before_model_admission": True,
        "nonce_before_output_directory": True,
        "nonce_before_runner_load": True,
        "single_use_nonce_persistent_sqlite": True,
        "existing_output_rejected": True,
        "atomic_segment_and_receipt_finalization": True,
        "cleanup_scoped_to_owned_paths": True,
        "machine_pcm_and_non_silence_gate": True,
        "playback_absent": True,
        "recording_absent": True,
        "memory_integration_absent": True,
        "runner_override_absent": True,
        "shell_and_subprocess_absent": True,
    }


def test_review_records_external_blockers_and_next_contract() -> None:
    result = build()

    assert result["blockers"] == [
        "authority_verifier_implementation_external",
        "model_bundle_verifier_implementation_external",
        "model_directory_manifest_not_bound_by_s604_contract",
        "nonce_store_path_not_contract_bound_or_deployed",
        "secure_runtime_configuration_not_installed",
        "bounded_render_receipt_schema_not_defined",
    ]
    assert result["claims"]["real_model_executed"] is False
    assert result["claims"]["runtime_execution_admitted"] is False
    assert result["next_gate"] == "story_executor_authority_model_nonce_contract"


def test_review_rejects_missing_model_verifier_or_runner_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    original_read_text = Path.read_text

    def replace_source(replacement: str):
        def read_text(path: Path, *args, **kwargs):
            if path == EXECUTOR_PATH:
                return replacement
            return original_read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)

    replace_source(source.replace("    model_verifier: ModelVerifier,\n", ""))
    with pytest.raises(ValueError, match="executor signature boundary invalid"):
        build()

    replace_source(
        source.replace(
            "    nonce_store_path: Path,\n",
            "    nonce_store_path: Path,\n    runner_override: Runner | None = None,\n",
        )
    )
    with pytest.raises(ValueError, match="runner override forbidden"):
        build()


def test_review_rejects_s605_or_runner_drift(tmp_path: Path) -> None:
    prior = json.loads(S605_PATH.read_text(encoding="utf-8"))
    prior["execution_authorized"] = True
    changed_prior = tmp_path / "s605.json"
    changed_prior.write_text(json.dumps(prior), encoding="utf-8")
    with pytest.raises(ValueError, match="S605 authority boundary invalid"):
        build(implementation_review_path=changed_prior)

    digest_drift = json.loads(S605_PATH.read_text(encoding="utf-8"))
    digest_drift["blockers"].append("synthetic-drift")
    changed_digest = tmp_path / "s605-digest.json"
    changed_digest.write_text(json.dumps(digest_drift), encoding="utf-8")
    with pytest.raises(ValueError, match="S605 review SHA-256 invalid"):
        build(implementation_review_path=changed_digest)

    runner = tmp_path / "runner.py"
    runner.write_text(RUNNER_PATH.read_text(encoding="utf-8") + "\n# drift\n")
    with pytest.raises(ValueError, match="trusted runner SHA-256 mismatch"):
        build(trusted_runner_path=runner)


def test_review_is_deterministic_and_receipt_validates() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    generated = build()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    assert generated == build()
    assert len(generated["review_sha256"]) == 64
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(generated)) == []
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
    assert receipt == generated
