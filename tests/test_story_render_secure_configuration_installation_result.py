import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "docs/design/voice-scene/s614_story_render_secure_configuration_installation_result.json"
SCHEMA = ROOT / "docs/design/voice-scene/story_render_secure_configuration_installation_result.schema.json"
BINDING = ROOT / "scripts/story_executor_posix_runtime_binding.py"
RUNTIME = Path("/home/pallasting/.agent-bridge-secure/story-render")
KEY_BUNDLE = RUNTIME / "authority-keys.v1.json"
NONCE_STORE = RUNTIME / "story-render-nonces.sqlite3"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recorded_installation_result_validates_and_matches_custody():
    jsonschema = pytest.importorskip("jsonschema")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
    assert receipt["installation"]["runtime_directory"] == str(RUNTIME)
    assert receipt["installation"]["key_bundle"] == str(KEY_BUNDLE)
    runtime_metadata = RUNTIME.lstat()
    key_metadata = KEY_BUNDLE.lstat()
    assert stat.S_ISDIR(runtime_metadata.st_mode)
    assert stat.S_IMODE(runtime_metadata.st_mode) == 0o700
    assert stat.S_ISREG(key_metadata.st_mode)
    assert stat.S_IMODE(key_metadata.st_mode) == 0o600
    assert key_metadata.st_uid == os.getuid()
    assert key_metadata.st_gid == os.getgid()
    assert key_metadata.st_nlink == 1
    assert {path.name for path in RUNTIME.iterdir()} == {KEY_BUNDLE.name}
    assert not NONCE_STORE.exists()
    assert not (RUNTIME / ".authority-keys.v1.json.installing").exists()
    encoded = json.dumps(receipt, sort_keys=True)
    assert "key_hex" not in encoded
    assert receipt["installation"]["key_material_disclosed"] is False
    assert receipt["execution_authorized"] is False


def test_fixed_loader_accepts_installed_key_without_exposing_it():
    binding = load(BINDING, "s614_installed_acceptance")
    loaded = binding.load_installed_authority_key("story-render-owner-v1")
    assert loaded.key_id == "story-render-owner-v1"
    assert loaded.cleared is False
    loaded.clear()
    assert loaded.cleared is True
