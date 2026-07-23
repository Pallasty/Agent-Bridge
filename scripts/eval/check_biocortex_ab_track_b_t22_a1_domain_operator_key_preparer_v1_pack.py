"""Offline KATs for T22-A1 dedicated domain-key preparation."""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_operator_key_preparer_v1.py"
spec = importlib.util.spec_from_file_location("t22a1_domain_key_preparer_kat", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

NOW = datetime(2026, 7, 23, 3, 0, tzinfo=timezone.utc)
SOURCE_COMMIT = "a" * 40
SSH_KEYGEN = Path(shutil.which("ssh-keygen") or "").resolve()
assert SSH_KEYGEN.is_file()
SSH_KEYGEN_SHA256 = hashlib.sha256(SSH_KEYGEN.read_bytes()).hexdigest()


def expect_failure(action, expected: str) -> None:  # noqa: ANN001
    try:
        action()
    except module.SafeFailure as error:
        assert str(error) == expected, (str(error), expected)
        return
    raise AssertionError(f"unsafe domain key preparation admitted: {expected}")


with tempfile.TemporaryDirectory(prefix="t22-a1-domain-key-preparer-kat-") as directory:
    parent = Path(directory).resolve()
    parent.chmod(0o700)
    root = parent / "domain-2"
    result = module.prepare(
        "domain-2", "synthetic-mac", root, SSH_KEYGEN, SSH_KEYGEN_SHA256,
        SOURCE_COMMIT, NOW, hostname_observer=lambda: "synthetic-mac",
    )
    assert result["status"] == "PASS_T22_A1_DEDICATED_DOMAIN_OPERATOR_KEY_PREPARED"
    assert result["domain_id"] == "domain-2" and result["key_pair_verified"] is True
    assert result["private_key_exported"] is False
    assert result["stable_host_identity_read"] is False
    assert result["ambient_or_existing_credentials_accessed"] is False
    assert result["network_accessed"] is False
    assert result["external_hosts_contacted"] == result["services_started"] == result["faults_injected"] == 0
    private_key = Path(result["private_key_path"])
    public_key = Path(result["public_key_path"])
    assert private_key.is_file() and public_key.is_file()
    assert private_key.stat().st_mode & 0o077 == 0 and public_key.stat().st_mode & 0o077 == 0
    unsigned = dict(result)
    claimed = unsigned.pop("content_sha256")
    assert claimed == module.digest(unsigned)

    negative_count = 0
    expect_failure(
        lambda: module.prepare(
            "domain-2", "synthetic-mac", root, SSH_KEYGEN, SSH_KEYGEN_SHA256,
            SOURCE_COMMIT, NOW, hostname_observer=lambda: "synthetic-mac",
        ),
        "E_DOMAIN_KEY_OUTPUT_EXISTS",
    )
    negative_count += 1
    wrong_hash_root = parent / "wrong-hash"
    expect_failure(
        lambda: module.prepare(
            "domain-3", "synthetic-third", wrong_hash_root, SSH_KEYGEN, "1" * 64,
            SOURCE_COMMIT, NOW, hostname_observer=lambda: "synthetic-third",
        ),
        "E_DOMAIN_KEY_SSH_KEYGEN_BINDING",
    )
    assert not wrong_hash_root.exists()
    negative_count += 1
    wrong_host_root = parent / "wrong-host"
    expect_failure(
        lambda: module.prepare(
            "domain-3", "synthetic-third", wrong_host_root, SSH_KEYGEN, SSH_KEYGEN_SHA256,
            SOURCE_COMMIT, NOW, hostname_observer=lambda: "different-host",
        ),
        "E_DOMAIN_KEY_HOST_BINDING",
    )
    assert not wrong_host_root.exists()
    negative_count += 1
    expect_failure(
        lambda: module.prepare(
            "domain-4", "synthetic-fourth", parent / "invalid-domain",
            SSH_KEYGEN, SSH_KEYGEN_SHA256, SOURCE_COMMIT, NOW,
        ),
        "E_DOMAIN_KEY_DOMAIN",
    )
    negative_count += 1
    expect_failure(
        lambda: module.prepare(
            "domain-3", "synthetic-third", ROOT / "unsafe-key-root",
            SSH_KEYGEN, SSH_KEYGEN_SHA256, SOURCE_COMMIT, NOW,
            hostname_observer=lambda: "synthetic-third",
        ),
        "E_DOMAIN_KEY_PRIVATE_ROOT",
    )
    negative_count += 1

    failure_root = parent / "failure"

    def failing_runner(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        raise OSError("synthetic key generator failure")

    expect_failure(
        lambda: module.prepare(
            "domain-3", "synthetic-third", failure_root,
            SSH_KEYGEN, SSH_KEYGEN_SHA256, SOURCE_COMMIT, NOW,
            hostname_observer=lambda: "synthetic-third", command_runner=failing_runner,
        ),
        "E_DOMAIN_KEY_GENERATION",
    )
    assert not (failure_root / "keys" / "domain-3-operator").exists()
    assert not (failure_root / "keys" / "domain-3-operator.pub").exists()
    assert (failure_root / "key-preparation" / "domain-3.reserved.json").is_file()
    assert (failure_root / "key-preparation" / "domain-3.terminal.json").is_file()
    negative_count += 1

status = module.status()
assert status["real_key_items_created"] == 0
assert status["stable_host_identity_read"] is False
assert status["ambient_or_existing_credentials_accessed"] is False
assert status["network_accessed"] is False
assert status["external_hosts_contacted"] == status["services_started"] == 0
assert status["faults_injected"] == status["spend_usd_cents"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

print("t22_a1_domain_operator_key_preparer_check\tpass")
print("synthetic_dedicated_domain_key_success_count\t1")
print(f"directed_negative_test_count\t{negative_count}")
print("real_key_items_created\t0")
print("stable_host_identity_read\tfalse")
print("ambient_or_existing_credentials_accessed\tfalse")
print("network_accessed\tfalse")
print("external_hosts_contacted\t0")
print("services_started\t0")
print("faults_injected\t0")
print("production_admissible\tfalse")
