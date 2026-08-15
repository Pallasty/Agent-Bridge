import importlib.util
import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/story_executor_secure_runtime_configuration_contract.py"
S610 = ROOT / "docs/design/voice-scene/s610_story_executor_secure_runtime_composition_review.json"
SECURE_ROOT = Path("/home/pallasting/.agent-bridge-secure")
RUNTIME_DIR = SECURE_ROOT / "story-render"
LEGACY_NONCE = Path("/Data/Models/agent-bridge/runtime/voice-scene/story-render-nonces.sqlite3")


def load_module():
    assert MODULE.exists(), "S611 configuration contract builder is missing"
    spec = importlib.util.spec_from_file_location("s611", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(module, **overrides):
    args = dict(prior_review_path=S610, secure_root=SECURE_ROOT,
                runtime_directory=RUNTIME_DIR, legacy_nonce_path=LEGACY_NONCE,
                mountinfo_path=Path("/proc/self/mountinfo"))
    args.update(overrides)
    return module.build_contract(**args)


def test_contract_selects_posix_private_custody_in_synthetic_preinstall_root(
        tmp_path):
    secure_root = tmp_path / "secure-root"
    secure_root.mkdir(mode=0o700)
    os.chmod(secure_root, 0o700)
    runtime_directory = secure_root / "story-render"
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text(
        "1 0 0:1 / / rw - ext4 /dev/synthetic rw\n"
        "2 1 0:2 / /Data rw - fuseblk /dev/synthetic-data rw\n",
        encoding="utf-8",
    )
    result = build(
        load_module(), secure_root=secure_root,
        runtime_directory=runtime_directory, mountinfo_path=mountinfo)
    assert result["status"] == "story_executor_secure_runtime_configuration_contract_reviewable"
    assert result["decision"] == "posix_private_custody_selected_installation_blocked"
    custody = result["custody"]
    assert custody["secure_root"]["filesystem_type"] == "ext4"
    assert custody["secure_root"]["mode"] == "0700"
    assert custody["runtime_directory"]["path"] == str(runtime_directory)
    assert custody["runtime_directory"]["mode"] == "0700"
    assert custody["key_bundle"]["path"] == str(
        runtime_directory / "authority-keys.v1.json")
    assert custody["key_bundle"]["mode"] == "0600"
    assert custody["key_bundle"]["key_bytes"] == 32
    assert custody["key_bundle"]["required_link_count"] == 1
    assert custody["key_bundle"]["environment_source_allowed"] is False
    assert custody["key_bundle"]["generation_fallback_allowed"] is False
    assert custody["key_bundle"]["loader_open_flags"] == ["O_RDONLY", "O_NOFOLLOW", "O_CLOEXEC"]
    assert custody["key_bundle"]["loader_identity_check"] == "fstat_same_fd_regular_uid_gid_mode_nlink"
    assert custody["key_bundle"]["content_digest_in_public_receipt"] is False
    assert custody["nonce_store"]["path"] == str(
        runtime_directory / "story-render-nonces.sqlite3")
    assert custody["nonce_store"]["mode"] == "0600"
    assert custody["nonce_store"]["trusted_schema"] is False
    assert custody["nonce_store"]["synchronous"] == "FULL"
    assert custody["nonce_store"]["application_id"] == 1094865475
    assert custody["nonce_store"]["user_version"] == 1
    assert custody["nonce_store"]["sidecars"] == ["database", "wal", "shm", "lock"]
    assert custody["legacy_nonce_path"]["path"] == str(LEGACY_NONCE)
    assert custody["legacy_nonce_path"]["filesystem_type"] == "fuseblk"
    assert custody["legacy_nonce_path"]["allowed"] is False
    assert result["installation_authorized"] is False
    assert result["execution_authorized"] is False
    assert not any(result["runtime_effects"].values())
    assert not runtime_directory.exists()
    assert result["next_gate"] == "story_executor_posix_runtime_binding_implementation_review"


def test_contract_requires_exact_private_root_mode(tmp_path):
    module = load_module()
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir(mode=0o755)
    os.chmod(unsafe, 0o755)
    with pytest.raises(ValueError, match="mode"):
        build(module, secure_root=unsafe, runtime_directory=unsafe / "story-render")


def test_contract_rejects_existing_runtime_target(tmp_path):
    module = load_module()
    existing = tmp_path / "already-there"
    existing.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        build(module, runtime_directory=existing)


def test_contract_rejects_s610_drift(tmp_path):
    module = load_module()
    value = json.loads(S610.read_text())
    value["decision"] = "drift"
    path = tmp_path / "s610.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="S610"):
        build(module, prior_review_path=path)
