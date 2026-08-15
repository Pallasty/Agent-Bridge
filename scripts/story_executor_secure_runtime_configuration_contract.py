#!/usr/bin/env python3
"""Build S611's read-only secure runtime configuration installation contract."""

from __future__ import annotations

import argparse
import grp
import hashlib
import json
import os
import pwd
import stat
from pathlib import Path
from typing import Any


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required:{path}")
    return value


def _validate_s610(review: dict[str, Any]) -> None:
    bound = {key: review[key] for key in (
        "evidence", "boundaries", "blockers", "implementation_present",
        "configuration_installed", "execution_authorized", "runtime_effects")}
    if (review.get("schema")
            != "agent_bridge.story_executor_secure_runtime_composition_review.v1"
            or review.get("decision")
            != "preparation_composition_accepted_invocation_blocked"
            or review.get("next_gate")
            != "story_executor_secure_runtime_configuration_installation_contract"
            or review.get("execution_authorized") is not False
            or any(review.get("runtime_effects", {}).values())
            or _digest(bound) != review.get("review_sha256")):
        raise ValueError("S610 review invalid")


def _unescape_mount(value: str) -> str:
    for encoded, plain in (("\\040", " "), ("\\011", "\t"),
                           ("\\012", "\n"), ("\\134", "\\")):
        value = value.replace(encoded, plain)
    return value


def _filesystem_type(path: Path, mountinfo_path: Path) -> str:
    target = str(path.resolve(strict=False))
    matches: list[tuple[int, str]] = []
    for line in mountinfo_path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        separator = fields.index("-")
        mountpoint = _unescape_mount(fields[4]).rstrip("/") or "/"
        if target == mountpoint or target.startswith(mountpoint.rstrip("/") + "/"):
            matches.append((len(mountpoint), fields[separator + 1]))
    if not matches:
        raise ValueError(f"filesystem mount not found:{path}")
    return max(matches)[1]


def _secure_root_record(path: Path, mountinfo_path: Path) -> dict[str, Any]:
    metadata = path.lstat()
    mode = stat.S_IMODE(metadata.st_mode)
    if not stat.S_ISDIR(metadata.st_mode) or path.is_symlink():
        raise ValueError("secure root must be a non-symlink directory")
    if mode != 0o700:
        raise ValueError("secure root mode must be 0700")
    if metadata.st_uid != os.getuid() or metadata.st_gid != os.getgid():
        raise ValueError("secure root owner must match current user")
    filesystem = _filesystem_type(path, mountinfo_path)
    if filesystem not in {"ext4", "xfs", "btrfs"}:
        raise ValueError("secure root filesystem is not approved POSIX storage")
    return {
        "path": str(path), "filesystem_type": filesystem, "mode": "0700",
        "uid": metadata.st_uid, "gid": metadata.st_gid,
        "owner": pwd.getpwuid(metadata.st_uid).pw_name,
        "group": grp.getgrgid(metadata.st_gid).gr_name,
        "symlink": False, "already_present": True,
    }


def build_contract(*, prior_review_path: Path, secure_root: Path,
                   runtime_directory: Path, legacy_nonce_path: Path,
                   mountinfo_path: Path) -> dict[str, Any]:
    prior = _read(prior_review_path)
    _validate_s610(prior)
    root = _secure_root_record(secure_root, mountinfo_path)
    if runtime_directory.exists() or runtime_directory.is_symlink():
        raise ValueError("runtime directory already exists; adoption review required")
    if runtime_directory.parent != secure_root:
        raise ValueError("runtime directory must be a direct child of secure root")
    key_path = runtime_directory / "authority-keys.v1.json"
    nonce_path = runtime_directory / "story-render-nonces.sqlite3"
    legacy_fs = _filesystem_type(legacy_nonce_path, mountinfo_path)
    custody = {
        "secure_root": root,
        "runtime_directory": {
            "path": str(runtime_directory), "filesystem_type": root["filesystem_type"],
            "mode": "0700", "uid": root["uid"], "gid": root["gid"],
            "symlink_allowed": False, "installed_now": False,
        },
        "key_bundle": {
            "path": str(key_path), "schema": "agent_bridge.story_render_authority_keys.v1",
            "mode": "0600", "uid": root["uid"], "gid": root["gid"],
            "key_bytes": 32, "encoding": "lowercase_hex", "zero_key_allowed": False,
            "maximum_versions": 16, "active_key_count": 1,
            "states": ["active", "verify_only", "revoked"],
            "random_source": "python_secrets_token_bytes_os_csprng",
            "required_link_count": 1, "environment_source_allowed": False,
            "default_path_allowed": False, "generation_fallback_allowed": False,
            "runtime_caller_path_override_allowed": False,
            "loader_open_flags": ["O_RDONLY", "O_NOFOLLOW", "O_CLOEXEC"],
            "loader_identity_check": "fstat_same_fd_regular_uid_gid_mode_nlink",
            "parent_walk": "dirfd_O_DIRECTORY_O_NOFOLLOW_each_component",
            "content_digest_in_public_receipt": False,
            "raw_key_in_logs_or_receipts": False, "symlink_allowed": False,
            "installed_now": False,
        },
        "nonce_store": {
            "path": str(nonce_path), "backend": "sqlite3", "mode": "0600",
            "uid": root["uid"], "gid": root["gid"], "symlink_allowed": False,
            "journal_mode": "WAL", "transaction": "BEGIN IMMEDIATE",
            "primary_key": "single_use_nonce", "installed_now": False,
            "trusted_schema": False, "synchronous": "FULL",
            "application_id": 1094865475, "user_version": 1,
            "sidecars": ["database", "wal", "shm", "lock"],
            "sidecar_mode": "0600", "sidecar_symlink_allowed": False,
            "automatic_corruption_recovery": False,
        },
        "legacy_nonce_path": {
            "path": str(legacy_nonce_path), "filesystem_type": legacy_fs,
            "allowed": False, "reason": "fuse_or_shared_storage_not_secret_custody",
        },
    }
    installation = {
        "authorized_now": False,
        "preconditions": [
            "fresh_owner_authorization", "runtime_directory_still_absent",
            "secure_root_identity_mode_owner_and_filesystem_reverified",
            "absolute_canonical_paths", "lstat_no_symlink_in_any_existing_component",
            "process_umask_0077",
        ],
        "creation_order": [
            "mkdir_runtime_directory_0700", "fsync_secure_root",
            "create_key_bundle_with_O_CREAT_O_EXCL_O_NOFOLLOW_0600",
            "write_complete_bundle_and_fsync_file", "fsync_runtime_directory",
            "leave_nonce_database_absent_until_first_authorized_consumption",
        ],
        "rotation": {
            "temporary_file_same_directory": True, "temporary_mode": "0600",
            "temporary_link_count": 1,
            "fsync_before_atomic_replace": True, "directory_fsync_after_replace": True,
            "retain_previous_as_verify_only": True, "raw_key_backup_forbidden": True,
        },
        "rollback": {
            "initial_install_failure": "remove_only_transaction_owned_new_files_then_runtime_directory",
            "preexisting_targets_deleted": False,
            "key_material_printed": False,
            "nonce_history_reverted": False,
            "automatic_rollback_after_key_use_or_nonce_consumption": False,
        },
        "acceptance_checks": [
            "lstat_non_symlink_types_and_nlink_one", "exact_uid_gid_and_modes",
            "key_bundle_schema_and_single_active_key", "nonzero_32_byte_key",
            "legacy_path_unused", "nonce_store_absent_before_first_authorized_use",
        ],
    }
    blockers = [
        "posix_nonce_and_key_binding_not_implemented",
        "owner_authorized_secure_configuration_installation_not_granted",
        "executor_invocation_not_authorized",
    ]
    runtime_effects = {
        "created_runtime_directory": False, "created_key_bundle": False,
        "generated_key": False, "created_nonce_store": False,
        "changed_permissions": False, "created_symlink": False,
        "loaded_secret": False, "called_executor": False, "loaded_model": False,
        "executed_onnx": False, "rendered_audio": False, "played_audio": False,
        "recorded_audio": False, "wrote_memory": False,
    }
    evidence = {
        "s610_review_file_sha256": _sha(prior_review_path),
        "s610_review_sha256": prior["review_sha256"],
        "mountinfo_path": str(mountinfo_path), "mountinfo_read_only": True,
        "current_uid": os.getuid(), "current_gid": os.getgid(),
        "runtime_directory_absent": True, "key_bundle_absent": True,
        "nonce_store_absent": True,
    }
    bound = {"evidence": evidence, "custody": custody, "installation": installation,
             "blockers": blockers, "installation_authorized": False,
             "execution_authorized": False, "runtime_effects": runtime_effects}
    return {
        "schema": "agent_bridge.story_executor_secure_runtime_configuration_contract.v1",
        "status": "story_executor_secure_runtime_configuration_contract_reviewable",
        "decision": "posix_private_custody_selected_installation_blocked",
        **bound, "contract_sha256": _digest(bound),
        "claims": {
            "posix_private_custody_selected": True,
            "legacy_fuse_custody_rejected": True,
            "atomic_install_and_rollback_defined": True,
            "configuration_installed": False, "real_key_generated": False,
            "executor_invoked": False,
        },
        "next_gate": "story_executor_posix_runtime_binding_implementation_review",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-review", type=Path, required=True)
    parser.add_argument("--secure-root", type=Path, required=True)
    parser.add_argument("--runtime-directory", type=Path, required=True)
    parser.add_argument("--legacy-nonce-path", type=Path, required=True)
    parser.add_argument("--mountinfo", type=Path, default=Path("/proc/self/mountinfo"))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    value = build_contract(prior_review_path=args.prior_review,
        secure_root=args.secure_root, runtime_directory=args.runtime_directory,
        legacy_nonce_path=args.legacy_nonce_path, mountinfo_path=args.mountinfo)
    print(json.dumps(value, ensure_ascii=False, indent=2 if args.pretty else None,
                     separators=None if args.pretty else (",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
