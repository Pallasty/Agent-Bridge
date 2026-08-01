import json
import stat
from datetime import datetime
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = (
    ROOT
    / "docs/design/voice-scene/"
    "s616_story_render_owner_signed_preparation_result.json"
)
SCHEMA = (
    ROOT
    / "docs/design/voice-scene/"
    "story_render_owner_signed_preparation_result.schema.json"
)
RUNTIME = Path("/home/pallasting/.agent-bridge-secure/story-render")
KEY_BUNDLE = RUNTIME / "authority-keys.v1.json"
NONCE_STORE = RUNTIME / "story-render-nonces.sqlite3"
OUTPUT = Path(
    "/Data/Models/agent-bridge/evidence/voice-scene/"
    "story-command-runtime/s616-owner-signed-preparation"
)


def test_recorded_s616_result_is_redacted_exact_and_live_safe():
    jsonschema = pytest.importorskip("jsonschema")
    result = json.loads(RECEIPT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(result)) == []

    authorization = result["authorization"]
    issued = datetime.fromisoformat(authorization["issued_at"])
    expires = datetime.fromisoformat(authorization["expires_at"])
    assert (expires - issued).total_seconds() == 300
    encoded = json.dumps(result, sort_keys=True)
    assert "mac_sha256" not in encoded
    assert "single_use_nonce" not in encoded
    assert "authorization_id" not in encoded
    assert authorization["key_material_disclosed"] is False
    assert authorization["mac_disclosed"] is False
    assert authorization["nonce_disclosed"] is False
    assert authorization["envelope_persisted"] is False

    key_metadata = KEY_BUNDLE.lstat()
    assert stat.S_ISREG(key_metadata.st_mode)
    assert stat.S_IMODE(key_metadata.st_mode) == 0o600
    assert key_metadata.st_nlink == 1
    assert result["preparation"]["real_key_load_count"] == 1
    assert result["preparation"]["loaded_key_buffer_cleared"] is True
    assert all(
        not path.exists()
        for path in (
            NONCE_STORE,
            Path(str(NONCE_STORE) + "-wal"),
            Path(str(NONCE_STORE) + "-shm"),
            Path(str(NONCE_STORE) + ".lock"),
        )
    )
    assert not OUTPUT.exists()
    assert result["execution_authorized"] is False
    assert result["grant_references_discarded_after_preparation"] is True
    assert "grant_destroyed_after_preparation" not in result


def test_s616_result_records_only_authorized_real_effects():
    result = json.loads(RECEIPT.read_text(encoding="utf-8"))
    effects = result["runtime_effects"]
    assert effects["read_real_key"] is True
    assert effects["generated_real_mac"] is True
    assert all(
        effects[name] is False
        for name in (
            "created_nonce_store",
            "consumed_nonce",
            "imported_executor",
            "called_executor",
            "loaded_model",
            "executed_onnx",
            "rendered_audio",
            "played_audio",
            "recorded_audio",
            "wrote_memory",
        )
    )
