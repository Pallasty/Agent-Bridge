import importlib.util
import inspect
import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/story_executor_secure_configuration_installer.py"
BINDING = ROOT / "scripts/story_executor_posix_runtime_binding.py"
RESULT_SCHEMA = ROOT / "docs/design/voice-scene/story_render_secure_configuration_installation_result.schema.json"
FIXED_RUNTIME = Path("/home/pallasting/.agent-bridge-secure/story-render")


def load(path: Path, name: str):
    assert path.exists(), f"missing module:{path}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def private_root(tmp_path: Path):
    secure_root = tmp_path / "secure-root"
    secure_root.mkdir(mode=0o700)
    os.chmod(secure_root, 0o700)
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text(
        f"1 0 0:1 / {secure_root} rw - ext4 /dev/synthetic rw\n",
        encoding="utf-8",
    )
    return secure_root, mountinfo


def install(module, tmp_path: Path, **overrides):
    secure_root, mountinfo = private_root(tmp_path)
    values = dict(
        secure_root=secure_root,
        runtime_directory=secure_root / "story-render",
        key_id="story-render-owner-v1",
        key_factory=lambda size: b"\x21" * size,
        mountinfo_path=mountinfo,
        step_hook=lambda _step, _runtime: None,
    )
    values.update(overrides)
    return module._install_secure_configuration(**values), values


def test_transaction_installs_loader_compatible_bundle_without_nonce(tmp_path):
    module = load(MODULE, "s614")
    binding = load(BINDING, "s614_binding")
    result, values = install(module, tmp_path)
    runtime = values["runtime_directory"]
    key_path = runtime / "authority-keys.v1.json"
    nonce_path = runtime / "story-render-nonces.sqlite3"

    assert oct(runtime.stat().st_mode & 0o777) == "0o700"
    assert oct(key_path.stat().st_mode & 0o777) == "0o600"
    assert key_path.stat().st_nlink == 1
    assert not nonce_path.exists()
    bundle = json.loads(key_path.read_text(encoding="utf-8"))
    assert bundle == {
        "schema": "agent_bridge.story_render_authority_keys.v1",
        "active_key_id": "story-render-owner-v1",
        "keys": [{
            "key_id": "story-render-owner-v1",
            "status": "active",
            "key_hex": "21" * 32,
        }],
    }
    with binding._load_authority_key(key_path, "story-render-owner-v1") as loaded:
        assert loaded.expose() == b"\x21" * 32
    encoded = json.dumps(result, sort_keys=True)
    assert "key_hex" not in encoded
    assert "21" * 32 not in encoded
    assert result["runtime_effects"] == {
        "created_runtime_directory": True,
        "created_key_bundle": True,
        "generated_key": True,
        "created_nonce_store": False,
        "called_executor": False,
        "loaded_model": False,
        "rendered_audio": False,
        "wrote_memory": False,
    }
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(result)) == []


def test_transaction_rejects_unsafe_or_preexisting_targets(tmp_path):
    module = load(MODULE, "s614_preconditions")
    secure_root, mountinfo = private_root(tmp_path)
    os.chmod(secure_root, 0o755)
    with pytest.raises(ValueError, match="0700"):
        module._install_secure_configuration(
            secure_root=secure_root,
            runtime_directory=secure_root / "story-render",
            key_id="story-render-owner-v1",
            key_factory=lambda size: b"\x21" * size,
            mountinfo_path=mountinfo,
            step_hook=lambda _step, _runtime: None,
        )
    os.chmod(secure_root, 0o700)
    runtime = secure_root / "story-render"
    runtime.mkdir(mode=0o700)
    marker = runtime / "owner-data"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        module._install_secure_configuration(
            secure_root=secure_root,
            runtime_directory=runtime,
            key_id="story-render-owner-v1",
            key_factory=lambda size: b"\x21" * size,
            mountinfo_path=mountinfo,
            step_hook=lambda _step, _runtime: None,
        )
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_transaction_rejects_bad_key_material_and_rolls_back(tmp_path):
    module = load(MODULE, "s614_key_rejection")
    secure_root, mountinfo = private_root(tmp_path)
    runtime = secure_root / "story-render"
    for key in (b"\x21" * 31, b"\0" * 32):
        with pytest.raises(ValueError, match="key material"):
            module._install_secure_configuration(
                secure_root=secure_root,
                runtime_directory=runtime,
                key_id="story-render-owner-v1",
                key_factory=lambda _size, value=key: value,
                mountinfo_path=mountinfo,
                step_hook=lambda _step, _runtime: None,
            )
        assert not runtime.exists()


def test_prepublication_failure_removes_only_transaction_owned_objects(tmp_path):
    module = load(MODULE, "s614_rollback")
    secure_root, mountinfo = private_root(tmp_path)
    runtime = secure_root / "story-render"

    def fail(step, _runtime):
        if step == "key_file_fsynced":
            raise RuntimeError("synthetic prepublication fault")

    with pytest.raises(RuntimeError, match="prepublication"):
        module._install_secure_configuration(
            secure_root=secure_root,
            runtime_directory=runtime,
            key_id="story-render-owner-v1",
            key_factory=lambda size: b"\x21" * size,
            mountinfo_path=mountinfo,
            step_hook=fail,
        )
    assert secure_root.exists()
    assert not runtime.exists()


def test_prepublication_rollback_fsyncs_removed_directory_chain(
        tmp_path, monkeypatch):
    module = load(MODULE, "s614_rollback_fsync")
    secure_root, mountinfo = private_root(tmp_path)
    root_inode = secure_root.stat().st_ino
    fsynced_inodes = []
    real_fsync = module.os.fsync

    def record_fsync(descriptor):
        fsynced_inodes.append(module.os.fstat(descriptor).st_ino)
        return real_fsync(descriptor)

    def fail(step, _runtime):
        if step == "key_file_fsynced":
            raise RuntimeError("synthetic rollback fsync fault")

    monkeypatch.setattr(module.os, "fsync", record_fsync)
    with pytest.raises(RuntimeError, match="rollback fsync"):
        module._install_secure_configuration(
            secure_root=secure_root,
            runtime_directory=secure_root / "story-render",
            key_id="story-render-owner-v1",
            key_factory=lambda size: b"\x21" * size,
            mountinfo_path=mountinfo,
            step_hook=fail,
        )
    assert fsynced_inodes[-1] == root_inode


def test_publication_collision_preserves_unowned_target(tmp_path):
    module = load(MODULE, "s614_collision")
    secure_root, mountinfo = private_root(tmp_path)
    runtime = secure_root / "story-render"
    collision = runtime / "authority-keys.v1.json"

    def collide(step, _runtime):
        if step == "key_file_fsynced":
            collision.write_bytes(b"unowned-collision")
            os.chmod(collision, 0o600)

    with pytest.raises(FileExistsError):
        module._install_secure_configuration(
            secure_root=secure_root,
            runtime_directory=runtime,
            key_id="story-render-owner-v1",
            key_factory=lambda size: b"\x21" * size,
            mountinfo_path=mountinfo,
            step_hook=collide,
        )
    assert collision.read_bytes() == b"unowned-collision"
    assert list(runtime.iterdir()) == [collision]


def test_postpublication_failure_requires_recovery_without_deleting_key(tmp_path):
    module = load(MODULE, "s614_recovery")
    secure_root, mountinfo = private_root(tmp_path)
    runtime = secure_root / "story-render"
    key_path = runtime / "authority-keys.v1.json"

    def fail(step, _runtime):
        if step == "key_published":
            raise RuntimeError("synthetic postpublication fault")

    with pytest.raises(module.InstallationRecoveryRequired, match="recovery"):
        module._install_secure_configuration(
            secure_root=secure_root,
            runtime_directory=runtime,
            key_id="story-render-owner-v1",
            key_factory=lambda size: b"\x21" * size,
            mountinfo_path=mountinfo,
            step_hook=fail,
        )
    assert runtime.exists()
    assert key_path.exists()
    assert not (runtime / module.TEMPORARY_KEY_NAME).exists()
    assert not (runtime / "story-render-nonces.sqlite3").exists()


def test_process_umask_is_restored_after_success(tmp_path):
    module = load(MODULE, "s614_umask")
    before = os.umask(0o077)
    os.umask(before)
    install(module, tmp_path)
    after = os.umask(0o077)
    os.umask(after)
    assert after == before


def test_public_surface_is_fixed_and_not_invoked_by_tests():
    module = load(MODULE, "s614_surface")
    signature = inspect.signature(module.install_story_render_secure_configuration)
    assert list(signature.parameters) == []
    source = MODULE.read_text(encoding="utf-8")
    assert "secrets.token_bytes" in source
    assert "os.O_EXCL" in source
    assert "os.O_NOFOLLOW" in source
    assert "os.O_CLOEXEC" in source
    assert "os.fsync" in source
    assert "os.link" in source
    assert "os.umask(0o077)" in source
    assert "import sqlite3" not in source
    assert "execute_bounded_render" not in source
    assert "onnxruntime" not in source
    assert "os.environ" not in source
    assert 'if __name__ == "__main__"' not in source
    assert not FIXED_RUNTIME.exists()


def test_fixed_policy_parses_the_same_bytes_that_were_hashed(monkeypatch):
    module = load(MODULE, "s614_policy_bytes")
    real_read_text = Path.read_text

    def forbid_second_policy_read(path, *args, **kwargs):
        if path in {module.S611_CONTRACT_PATH, module.S613_REVIEW_PATH}:
            raise AssertionError("pinned policy was read a second time")
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", forbid_second_policy_read)
    module._validate_fixed_policy()
