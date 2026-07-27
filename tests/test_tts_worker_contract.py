import importlib.util
from pathlib import Path


_PATH = Path(__file__).parents[1] / "scripts" / "validate_tts_worker_contract.py"
_SPEC = importlib.util.spec_from_file_location("validate_tts_worker_contract", _PATH)
assert _SPEC and _SPEC.loader
validator = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(validator)


def _health(**overrides):
    value = {
        "ok": True, "state": "ready", "protocol": "ab.tts.worker.v1",
        "engine": "qwen3-pytorch", "model": "local/model", "device": "mps",
        "dtype": "float16", "capabilities": ["custom_voice", "instruct", "zh"],
    }
    value.update(overrides)
    return value


def test_health_contract_accepts_declared_qwen_worker():
    assert validator.validate_health(_health(), "qwen3-pytorch", ("zh",)) == []


def test_health_contract_rejects_wrong_identity_and_capability():
    errors = validator.validate_health(_health(protocol="v0", capabilities=["zh"]),
                                      "onnxruntime", ("instruct",))
    assert "protocol must be 'ab.tts.worker.v1'" in errors
    assert "engine must be 'onnxruntime', got 'qwen3-pytorch'" in errors
    assert "missing capabilities: instruct" in errors


def test_health_contract_rejects_malformed_metadata():
    errors = validator.validate_health(_health(model="", capabilities="zh"))
    assert "missing non-empty model" in errors
    assert "capabilities must be a string array" in errors
