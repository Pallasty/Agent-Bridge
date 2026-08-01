import hashlib
import hmac
import importlib.util
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/story_render_authorization_proposal.py"
BASE_TEST = ROOT / "tests/test_story_executor_secure_runtime_composition.py"
VERIFIERS = ROOT / "scripts/story_executor_runtime_verifiers.py"
RUNTIME_CONTRACT = (
    ROOT
    / "docs/design/voice-scene/s608_story_executor_authority_model_nonce_contract.json"
)
KEY_BUNDLE = Path(
    "/home/pallasting/.agent-bridge-secure/story-render/authority-keys.v1.json"
)
NONCE_STORE = Path(
    "/home/pallasting/.agent-bridge-secure/story-render/story-render-nonces.sqlite3"
)


def load(path: Path, name: str):
    assert path.exists(), f"missing module:{path}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture():
    base_test = load(BASE_TEST, "s615_base_fixture")
    _composition, contract, _envelope, synthetic_key, request = (
        base_test.fixture()
    )
    request = json.loads(json.dumps(request))
    request["output_directory"] = (
        contract["bounds"]["output_root"] + "/s615-owner-proposal"
    )
    return contract, synthetic_key, request


def deterministic_identity(module, monkeypatch):
    now = datetime(2026, 8, 1, 20, 0, tzinfo=timezone.utc)
    values = iter(("ab" * 16, "cd" * 32))
    monkeypatch.setattr(module, "_utc_now", lambda: now)
    monkeypatch.setattr(module, "_random_hex", lambda _bytes: next(values))
    return now


def digest(value):
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_public_proposal_binds_exact_request_without_signing(monkeypatch):
    module = load(MODULE, "s615")
    contract, _key, request = fixture()
    now = deterministic_identity(module, monkeypatch)

    result = module.build_story_render_authorization_proposal(
        execution_contract=contract,
        request=request,
    )

    signature = inspect.signature(
        module.build_story_render_authorization_proposal
    )
    assert list(signature.parameters) == ["execution_contract", "request"]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    signed = result["proposal"]["signed_fields"]
    assert signed == {
        "authorization_id": "story-render-auth-" + "ab" * 16,
        "contract_sha256": contract["contract_sha256"],
        "preflight_sha256": contract["evidence"]["preflight_sha256"],
        "output_directory": request["output_directory"],
        "action": "render",
        "issued_at": now.isoformat(),
        "expires_at": "2026-08-01T20:05:00+00:00",
        "single_use_nonce": "cd" * 32,
        "issuer": "agent-bridge-owner-console",
        "subject": "story-bounded-render-executor",
        "key_id": "story-render-owner-v1",
    }
    assert result["schema"] == (
        "agent_bridge.story_render_authorization_proposal.v1"
    )
    assert result["status"] == "story_render_authorization_proposal_reviewable"
    assert result["decision"] == "owner_signature_required_execution_blocked"
    assert result["proposal"]["request_sha256"] == digest(request)
    assert result["proposal"]["signed_fields_sha256"] == digest(signed)
    assert result["proposal"]["proof_field"] == "mac_sha256"
    assert result["proposal"]["proof_present"] is False
    assert result["proposal"]["ttl_seconds"] == 300
    assert result["owner_signature_required"] is True
    assert result["execution_authorized"] is False
    assert not any(result["runtime_effects"].values())
    assert result["next_gate"] == (
        "owner_authorized_story_render_envelope_signing_preflight"
    )


def test_proposal_rejects_output_effect_and_model_drift(monkeypatch):
    module = load(MODULE, "s615_rejections")
    contract, _key, request = fixture()
    deterministic_identity(module, monkeypatch)

    outside = json.loads(json.dumps(request))
    outside["output_directory"] = "/tmp/s615-outside-contract"
    with pytest.raises(ValueError, match="output directory"):
        module.build_story_render_authorization_proposal(
            execution_contract=contract,
            request=outside,
        )

    playback = dict(request, playback=True)
    with pytest.raises(ValueError, match="effects"):
        module.build_story_render_authorization_proposal(
            execution_contract=contract,
            request=playback,
        )

    changed_model = json.loads(json.dumps(request))
    changed_model["model"]["tts_dir"] = "/tmp/caller-selected"
    with pytest.raises(ValueError, match="model"):
        module.build_story_render_authorization_proposal(
            execution_contract=contract,
            request=changed_model,
        )


def test_unsigned_proposal_matches_s609_canonical_fields_after_synthetic_mac(
    monkeypatch,
):
    module = load(MODULE, "s615_synthetic_proof")
    verifiers = load(VERIFIERS, "s615_verifiers")
    contract, synthetic_key, request = fixture()
    deterministic_identity(module, monkeypatch)
    result = module.build_story_render_authorization_proposal(
        execution_contract=contract,
        request=request,
    )
    envelope = dict(result["proposal"]["signed_fields"])
    runtime_contract = json.loads(RUNTIME_CONTRACT.read_text(encoding="utf-8"))
    message = verifiers.canonical_authorization_message(
        envelope,
        runtime_contract,
    )
    envelope["mac_sha256"] = hmac.new(
        synthetic_key,
        message,
        hashlib.sha256,
    ).hexdigest()
    authority_verifier = verifiers.build_authority_verifier(
        envelope=envelope,
        key=synthetic_key,
        contract=runtime_contract,
    )
    narrow = {
        name: envelope[name]
        for name in verifiers.EXECUTOR_AUTHORIZATION_FIELDS
    }
    assert authority_verifier(narrow) is True
    assert result["proposal"]["proof_present"] is False


def test_proposal_reads_no_real_key_and_creates_no_nonce(monkeypatch):
    module = load(MODULE, "s615_no_secret")
    contract, _key, request = fixture()
    deterministic_identity(module, monkeypatch)
    before = KEY_BUNDLE.lstat()

    result = module.build_story_render_authorization_proposal(
        execution_contract=contract,
        request=request,
    )

    after = KEY_BUNDLE.lstat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    assert not NONCE_STORE.exists()
    assert result["boundaries"]["real_key_read"] is False
    assert result["boundaries"]["real_mac_generated"] is False
    assert result["boundaries"]["nonce_store_created"] is False
    assert result["boundaries"]["executor_invoked"] is False


def test_proposal_rejects_unreviewed_s614_receipt_drift(
    monkeypatch, tmp_path
):
    module = load(MODULE, "s615_receipt_drift")
    contract, _key, request = fixture()
    deterministic_identity(module, monkeypatch)
    installation_result = json.loads(
        module.INSTALLATION_RESULT_PATH.read_text(encoding="utf-8")
    )
    installation_result["unreviewed_extra_field"] = True
    changed = tmp_path / "s614-installation-result.json"
    changed.write_text(json.dumps(installation_result), encoding="utf-8")
    monkeypatch.setattr(module, "INSTALLATION_RESULT_PATH", changed)

    with pytest.raises(ValueError, match="source drift"):
        module.build_story_render_authorization_proposal(
            execution_contract=contract,
            request=request,
        )


def test_source_has_no_secret_loader_executor_or_runtime_surface():
    source = MODULE.read_text(encoding="utf-8")
    assert "load_installed_authority_key" not in source
    assert "authority-keys.v1.json" not in source
    assert "hmac" not in source
    assert "execute_bounded_render" not in source
    assert "sqlite3" not in source
    assert "onnxruntime" not in source
    assert "subprocess" not in source
    assert "os.environ" not in source
    assert 'if __name__ == "__main__"' not in source
