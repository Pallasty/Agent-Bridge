import importlib.util
import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/story_executor_posix_runtime_binding.py"


def load_module():
    assert MODULE.exists(), "S612 POSIX runtime binding is missing"
    spec = importlib.util.spec_from_file_location("s612", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_bundle(tmp_path: Path, *, mode=0o600, status="active", extra=None):
    os.chmod(tmp_path, 0o700)
    path = tmp_path / "authority-keys.v1.json"
    value = {
        "schema": "agent_bridge.story_render_authority_keys.v1",
        "active_key_id": "story-render-owner-v1",
        "keys": [{"key_id": "story-render-owner-v1", "status": status,
                  "key_hex": "21" * 32}],
    }
    if extra:
        value.update(extra)
    path.write_text(json.dumps(value))
    os.chmod(path, mode)
    return path


def test_fd_loader_returns_requested_key_and_clears_context(tmp_path):
    module = load_module()
    path = write_bundle(tmp_path)
    loaded = module._load_authority_key(path, "story-render-owner-v1")
    with loaded as key:
        assert key.expose() == bytes.fromhex("21" * 32)
        assert key.key_id == "story-render-owner-v1"
        assert key.cleared is False
    assert loaded.cleared is True
    assert loaded.expose() == b"\0" * 32


def test_loader_rejects_mode_symlink_and_hardlink(tmp_path):
    module = load_module()
    path = write_bundle(tmp_path, mode=0o644)
    with pytest.raises(ValueError, match="identity"):
        module._load_authority_key(path, "story-render-owner-v1")
    os.chmod(path, 0o600)
    hardlink = tmp_path / "second-name"
    os.link(path, hardlink)
    with pytest.raises(ValueError, match="identity"):
        module._load_authority_key(path, "story-render-owner-v1")
    hardlink.unlink()
    target = tmp_path / "target"
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises(ValueError, match="open"):
        module._load_authority_key(path, "story-render-owner-v1")


def test_loader_rejects_unknown_revoked_and_non_closed_schema(tmp_path):
    module = load_module()
    path = write_bundle(tmp_path)
    with pytest.raises(ValueError, match="key id"):
        module._load_authority_key(path, "missing")
    path = write_bundle(tmp_path)
    value = json.loads(path.read_text())
    value["keys"].append({"key_id": "retired", "status": "revoked", "key_hex": "22" * 32})
    path.write_text(json.dumps(value))
    os.chmod(path, 0o600)
    with pytest.raises(ValueError, match="revoked"):
        module._load_authority_key(path, "retired")
    path = write_bundle(tmp_path, extra={"unexpected": True})
    with pytest.raises(ValueError, match="schema"):
        module._load_authority_key(path, "story-render-owner-v1")


def test_fixed_binding_comes_from_s611_with_key_installed_and_nonce_absent():
    module = load_module()
    nonce = module.secure_nonce_store_path()
    key_path = module.secure_key_bundle_path()
    assert nonce == Path("/home/pallasting/.agent-bridge-secure/story-render/story-render-nonces.sqlite3")
    assert key_path == Path("/home/pallasting/.agent-bridge-secure/story-render/authority-keys.v1.json")
    assert not nonce.exists()
    assert key_path.is_file()


def test_source_uses_fd_identity_checks_and_has_no_fallback_surface():
    source = MODULE.read_text()
    assert "os.open(" in source
    assert "os.O_NOFOLLOW" in source
    assert "os.O_CLOEXEC" in source
    assert "os.fstat(" in source
    assert "os.environ" not in source
    assert "read_text" not in source
    assert "secrets.token_bytes" not in source
    assert "import sqlite3" not in source
