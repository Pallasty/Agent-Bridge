import hashlib
import json
import sqlite3
import stat
import wave
from datetime import datetime
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESULT = (
    ROOT
    / "docs/design/voice-scene/"
    "s617_story_bounded_render_execution_result.json"
)
RESULT_SCHEMA = (
    ROOT
    / "docs/design/voice-scene/"
    "story_bounded_render_execution_result.schema.json"
)
RENDER_SCHEMA = (
    ROOT / "docs/design/voice-scene/story_bounded_render_receipt.schema.json"
)
OUTPUT = Path(
    "/Data/Models/agent-bridge/evidence/voice-scene/"
    "story-command-runtime/s617-bounded-render"
)
RENDER_RECEIPT = OUTPUT / "render-receipt.json"
NONCE_STORE = Path(
    "/home/pallasting/.agent-bridge-secure/story-render/"
    "story-render-nonces.sqlite3"
)
KEY_BUNDLE = Path(
    "/home/pallasting/.agent-bridge-secure/story-render/"
    "authority-keys.v1.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_validate(path: Path, schema_path: Path):
    jsonschema = pytest.importorskip("jsonschema")
    value = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(value)) == []
    return value


def test_s617_result_is_redacted_exact_and_bound_to_live_receipt():
    result = load_and_validate(RESULT, RESULT_SCHEMA)
    receipt = load_and_validate(RENDER_RECEIPT, RENDER_SCHEMA)

    authorization = result["authorization"]
    issued = datetime.fromisoformat(authorization["issued_at"])
    expires = datetime.fromisoformat(authorization["expires_at"])
    assert (expires - issued).total_seconds() == 300
    encoded = json.dumps(result, sort_keys=True)
    for forbidden in (
        "mac_sha256",
        "single_use_nonce",
        receipt["authorization_id"],
    ):
        assert forbidden not in encoded
    assert "authorization_id" not in authorization

    execution = result["execution"]
    assert sha256_file(RENDER_RECEIPT) == execution["render_receipt_sha256"]
    assert [row["sha256"] for row in receipt["segments"]] == execution[
        "segment_audio_sha256"
    ]
    assert receipt["assembly"]["sha256"] == execution["assembly"][
        "audio_sha256"
    ]
    assert receipt["assembly"]["duration_seconds"] == execution["assembly"][
        "duration_seconds"
    ]
    assert receipt["playback_authorized"] is False
    assert receipt["memory_authorized"] is False


def test_s617_live_audio_and_nonce_state_are_machine_verified():
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    receipt = json.loads(RENDER_RECEIPT.read_text(encoding="utf-8"))
    expected_paths = [OUTPUT / f"{index:02d}.wav" for index in range(3)]
    expected_paths.append(OUTPUT / "chapter.wav")
    assert sorted(path.name for path in OUTPUT.iterdir()) == [
        "00.wav",
        "01.wav",
        "02.wav",
        "chapter.wav",
        "render-receipt.json",
    ]
    assert stat.S_IMODE(OUTPUT.lstat().st_mode) == 0o777
    assert result["execution"]["output_filesystem"] == "fuseblk"
    assert result["execution"]["output_permission_semantics"] == (
        "mount_reports_fixed_permissions_posix_privacy_not_claimed"
    )

    receipt_audio = [row["sha256"] for row in receipt["segments"]]
    receipt_audio.append(receipt["assembly"]["sha256"])
    for path, expected_sha256 in zip(expected_paths, receipt_audio, strict=True):
        assert sha256_file(path) == expected_sha256
        with wave.open(str(path), "rb") as stream:
            assert stream.getnchannels() == 1
            assert stream.getsampwidth() == 2
            assert stream.getframerate() == 24000
            assert stream.getnframes() > 0

    nonce_metadata = NONCE_STORE.lstat()
    assert stat.S_ISREG(nonce_metadata.st_mode)
    assert stat.S_IMODE(nonce_metadata.st_mode) == 0o600
    assert nonce_metadata.st_nlink == 1
    for sidecar in (
        Path(str(NONCE_STORE) + "-wal"),
        Path(str(NONCE_STORE) + "-shm"),
        Path(str(NONCE_STORE) + ".lock"),
    ):
        if sidecar.exists():
            sidecar_metadata = sidecar.lstat()
            assert stat.S_ISREG(sidecar_metadata.st_mode)
            assert stat.S_IMODE(sidecar_metadata.st_mode) == 0o600
            assert sidecar_metadata.st_nlink == 1
    with sqlite3.connect(f"file:{NONCE_STORE}?mode=ro", uri=True) as connection:
        row_count = connection.execute(
            "select count(*) from consumed_nonces"
        ).fetchone()[0]
    assert row_count == result["execution"]["nonce_rows_after_execution"] == 2
    assert result["execution"]["failed_post_nonce_attempts"] == 1
    assert result["execution"]["failed_attempt_cleanup_verified"] is True

    key_metadata = KEY_BUNDLE.lstat()
    assert stat.S_ISREG(key_metadata.st_mode)
    assert stat.S_IMODE(key_metadata.st_mode) == 0o600
    assert key_metadata.st_nlink == 1
    assert not list(OUTPUT.glob("*.part"))


def test_s617_records_only_the_bounded_runtime_effects():
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    effects = result["runtime_effects"]
    assert all(
        effects[name]
        for name in (
            "read_real_key",
            "generated_real_mac",
            "created_output_root",
            "created_nonce_store",
            "consumed_nonce",
            "imported_executor",
            "called_executor",
            "loaded_model",
            "executed_onnx",
            "rendered_audio",
        )
    )
    assert all(
        effects[name] is False
        for name in (
            "played_audio",
            "recorded_audio",
            "wrote_cache",
            "wrote_memory",
        )
    )
    assert result["authorization"][
        "grant_references_discarded_after_execution"
    ] is True
    assert result["authorization"]["total_real_key_load_count"] == 3
    assert result["authorization"]["real_mac_generated_count"] == 3
    assert "grant_destroyed_after_execution" not in result
