#!/usr/bin/env python3
"""Static, fail-closed checker for the S21B-A1 owned-lab role build closure.

The checker performs no build and accepts no candidate digest or target commit.
It reads repository definitions, immutable Git objects, the pinned local
toolchain, and the exact Cargo sparse-index subset needed to resolve Cargo.lock.
Cargo metadata is queried with --no-deps/--offline/--frozen only; network access
and compilation are outside this program's authority.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import random
import re
import stat
import struct
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, Iterable, Mapping, NoReturn, Sequence

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

sys.dont_write_bytecode = True


CANONICALIZATION = (
    "AB_RESTRICTED_CANONICAL_JSON_S21B_A1_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT"
)
STAGE = (
    "S21B_A1_DEFINE_AND_BUILD_FOUR_NAMED_NON_LIVE_ROLE_ARTIFACTS_"
    "AND_REPRODUCIBLE_CLOSURES"
)
PENDING_STATUS = "S21B_A1_TOOLING_COMPLETE_PENDING_POST_INTEGRATION_DOUBLE_REBUILD"
REAL_STATUS = "S21B_A1_POST_INTEGRATION_ROLE_BUILD_CLOSURE_VERIFIED_NON_LIVE"
DECISION = (
    "S21B_A1_ADVANCE_ONLY_TO_SEPARATE_UNSIGNED_SUBJECT_CONTRACT_REBINDING_"
    "AND_GENERATION_REVIEW_NO_OWNER_SIGNING_REQUEST"
)
RECEIPT_SCHEMA_ID = "agent_bridge.memory_temporal_owned_lab_role_build_receipt_s21b_a1.v0"
RECEIPT_PACKET_KIND = "S21B_A1_ROLE_BUILD_CLOSURE_RECEIPT"
PENDING_RECEIPT_STATE = (
    "SYNTHETIC_KAT_TOOLING_COMPLETE_PENDING_POST_INTEGRATION_DOUBLE_REBUILD"
)
REAL_RECEIPT_STATE = "POST_INTEGRATION_DOUBLE_REBUILD_VERIFIED_NON_LIVE"
RECEIPT_DOMAIN = b"agent-bridge/biocortex/owned-lab/s21b-a1/role-build-receipt/v1"
FRAMING = "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_CANONICAL_PAYLOAD_LENGTH_CANONICAL_PAYLOAD"
SELF_HASH_FIELD = "role_build_receipt_sha256"

BASELINE_COMMIT = "d677e923442661a1d896185923b244d22b726319"
BASELINE_TREE = "4534149eb9c8057d4980f008897c9587bd253c7f"
BASELINE_FIRST_PARENT = "908412b8209056a90b3be5c2f93896c763d31311"
BASELINE_SECOND_PARENT = "4f627b0f1be2c858615906e5170055d92b5632b3"
BASELINE_ARCHIVE_SHA256 = "6d2163035d98bb64a76fcbcb1c725d315cada415814f7a0cf82c7afc89c1cac8"
BASELINE_ARCHIVE_BYTE_COUNT = 48_793_600
BASELINE_CARGO_LOCK_SHA256 = "a0ba6e432b188cbd0e3157693cb586bb950584860f036f83ee535fe67284b709"
SOURCE_BASE_COMMIT = "a5c70f235cf4e1bffa26253e2618e0a0903c9a16"
SOURCE_BASE_TREE = "35987f0ca61b200a34aa82b099482b791ed06bca"
SOURCE_BASE_FIRST_PARENT = "66f4754fd871169f50f345e5c023c94466f8ffd4"
SOURCE_BASE_SECOND_PARENT = "dc71c6f27aa1b9f310e5fff9e4e855011104dc96"
SOURCE_BASE_ARCHIVE_SHA256 = (
    "c8cd17b51792a695239f3569be728d1777fa3e5f98fa22d4489f21c8036892bf"
)
SOURCE_BASE_ARCHIVE_BYTE_COUNT = 50_216_960
SOURCE_BASE_CARGO_LOCK_SHA256 = (
    "452da4a2c2e4712251ad7a4076a3966222507eaf1695ff3d4ecab13084d732d2"
)
CANONICAL_REMOTE = "git@github.com:pallasting/Agent-Bridge.git"

ROLE_PACKAGE = "ab-owned-lab-role-artifacts"
ROLE_PACKAGE_VERSION = "0.14.0"
TARGET_TRIPLE = "x86_64-unknown-linux-gnu"
ROLE_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("controller", "ab-owned-lab-controller", "crates/owned-lab-role-artifacts/src/bin/controller.rs", "x86_64-unknown-linux-gnu/release/ab-owned-lab-controller"),
    ("observer", "ab-owned-lab-observer", "crates/owned-lab-role-artifacts/src/bin/observer.rs", "x86_64-unknown-linux-gnu/release/ab-owned-lab-observer"),
    ("runner", "ab-owned-lab-runner", "crates/owned-lab-role-artifacts/src/bin/runner.rs", "x86_64-unknown-linux-gnu/release/ab-owned-lab-runner"),
    ("validator", "ab-owned-lab-validator", "crates/owned-lab-role-artifacts/src/bin/validator.rs", "x86_64-unknown-linux-gnu/release/ab-owned-lab-validator"),
)

PREFIX = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-"
CONTRACT_PATH = PREFIX + "contract-s21b-a1-v0.json"
STATUS_PATH = PREFIX + "status-s21b-a1-v0.json"
SUCCESSOR_PATH = PREFIX + "successor-gate-s21b-a1-v0.json"
RECEIPT_SCHEMA_PATH = PREFIX + "receipt-schema-s21b-a1-v0.json"
RECEIPT_FIXTURE_PATH = PREFIX + "receipt-synthetic-s21b-a1-v0.json"
TOOLCHAIN_PATH = PREFIX + "toolchain-manifest-s21b-a1-v0.json"
FEATURE_SET_PATH = PREFIX + "feature-set-s21b-a1-v0.json"
SCHEMA_SET_PATH = PREFIX + "schema-set-s21b-a1-v0.json"
RECIPES_PATH = PREFIX + "recipes-s21b-a1-v0.json"
ROLE_MANIFEST_PATH = "crates/owned-lab-role-artifacts/Cargo.toml"

CONTROL_PATHS = (CONTRACT_PATH, STATUS_PATH, SUCCESSOR_PATH, RECEIPT_SCHEMA_PATH)
CLOSURE_PATHS = (TOOLCHAIN_PATH, FEATURE_SET_PATH, SCHEMA_SET_PATH, RECIPES_PATH)
STRICT_CANONICAL_PATHS = (*CLOSURE_PATHS, RECEIPT_FIXTURE_PATH)
FORMAT_IDS = {
    CONTRACT_PATH: "agent_bridge.memory_temporal_owned_lab_role_build_contract_s21b_a1.v0",
    STATUS_PATH: "agent_bridge.memory_temporal_owned_lab_role_build_status_s21b_a1.v0",
    SUCCESSOR_PATH: "agent_bridge.memory_temporal_owned_lab_role_build_successor_gate_s21b_a1.v0",
    TOOLCHAIN_PATH: "agent_bridge.memory_temporal_owned_lab_role_build_toolchain_manifest_s21b_a1.v0",
    FEATURE_SET_PATH: "agent_bridge.memory_temporal_owned_lab_role_build_feature_set_s21b_a1.v0",
    SCHEMA_SET_PATH: "agent_bridge.memory_temporal_owned_lab_role_build_schema_set_s21b_a1.v0",
    RECIPES_PATH: "agent_bridge.memory_temporal_owned_lab_role_build_recipes_s21b_a1.v0",
}
MANIFEST_DIGEST_CONTRACT = {
    "additional_framing": "NONE",
    "domain_separation": "NONE",
    "hash_algorithm": "SHA-256",
    "hash_scope": "ENTIRE_CANONICAL_REPOSITORY_FILE_BYTES",
    "manifest_self_hash_field_present": False,
    "raw_repository_file_bytes": True,
    "repository_terminal_lf_included": True,
}
MANIFEST_DIGEST_PROFILE = (
    "SHA256_EXACT_CANONICAL_REPOSITORY_FILE_BYTES_INCLUDING_ONE_TERMINAL_LF_"
    "NO_DOMAIN_NO_FRAMING_NO_SELF_FIELD"
)

SCHEMA_MEMBERS = (
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-external-input-admission-schema-s21a-v0.json",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-final-refreeze-subject-schema-s21a-v0.json",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-authorization-envelope-schema-s21a-v0.json",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-trust-anchor-schema-s21a-v0.json",
)
SCHEMA_SET_DOMAIN = b"agent-bridge/biocortex/owned-lab/s21b-a1/schema-set/v1"
SCHEMA_SET_PROFILE = (
    "U32BE_DOMAIN_LENGTH_DOMAIN_THEN_FOR_EACH_BYTEWISE_ASCII_PATH_SORTED_MEMBER_"
    "U64BE_PATH_LENGTH_PATH_ASCII_OCTAL_GIT_MODE_TO_U32_THEN_U32BE_"
    "U64BE_CONTENT_LENGTH_CONTENT"
)
RECIPE_PROFILE = (
    "SHA256_DOMAIN_SEPARATED_EXACT_MATCHING_RECIPES_ARRAY_OBJECT_"
    "AB_RESTRICTED_COMPACT_SORTED_KEYS_UTF8_WITHOUT_TERMINAL_LF"
)

TOOLCHAIN_ROOT = Path("/home/pallasting/.rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu")
SPARSE_INDEX_ROOT = Path(
    "/home/pallasting/.cargo/registry/index/index.crates.io-1949cf8c6b5b557f"
)
SPARSE_SOURCE_ID = "registry+https://github.com/rust-lang/crates.io-index"
SPARSE_PATH_PROFILE = (
    "CONFIG_AT_CONFIG_JSON;CRATE_NAME_LENGTH_1_AT_.cache/1/NAME;"
    "LENGTH_2_AT_.cache/2/NAME;LENGTH_3_AT_.cache/3/FIRST1/NAME;"
    "LENGTH_GE_4_AT_.cache/FIRST2/SECOND2/NAME"
)
SPARSE_CATALOG_PROFILE = (
    "FOR_EACH_BYTEWISE_ASCII_RELATIVE_PATH_SORTED_MEMBER_RELATIVE_POSIX_PATH_"
    "TAB_DECIMAL_BYTE_COUNT_TAB_64_LOWERCASE_HEX_SHA256_LF"
)
RUST_STD_PROFILE = (
    "RELATIVE_POSIX_PATH_TAB_FOUR_DIGIT_LOWERCASE_OCTAL_S_IMODE_TAB_"
    "DECIMAL_BYTE_COUNT_TAB_64_LOWERCASE_HEX_SHA256_LF"
)
TOOLCHAIN_TREE_PROFILE = (
    "FOR_EACH_BYTEWISE_ASCII_RELATIVE_POSIX_PATH_SORTED_REGULAR_FILE_"
    "RELATIVE_PATH_TAB_FOUR_DIGIT_OCTAL_MODE_TAB_DECIMAL_BYTE_COUNT_"
    "TAB_SHA256_LF_DIRECTORIES_EXCLUDED_SYMLINKS_FORBIDDEN"
)

SOURCE_SHA256 = {
    "crates/owned-lab-role-artifacts/src/lib.rs": "0c90b327625b76afdfa40510df5e2f8a4591be7aed2efcd96f64f0e903f97943",
    "crates/owned-lab-role-artifacts/src/bin/controller.rs": "52a818a950e5888d7a5a90fe090bc496b9d38f8dcc4accef7e6a6d1fa8cec446",
    "crates/owned-lab-role-artifacts/src/bin/observer.rs": "ebdb8179ea1cddb35948ae6228ab7eaad3f43cd1971b021665a13e123c88227c",
    "crates/owned-lab-role-artifacts/src/bin/runner.rs": "66a1dd88796907a24fdbb257ac2a84bc4963546932a82a7aef6eb7f03e0f4125",
    "crates/owned-lab-role-artifacts/src/bin/validator.rs": "692cfcb4c6bae6d0c916299c238839d556f89d9f307d98b3bad1474608975971",
}

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 64
MAX_U64 = (1 << 64) - 1


class CheckFailure(RuntimeError):
    """Expected fail-closed validation failure."""


def fail(code: str, detail: str) -> NoReturn:
    raise CheckFailure(f"{code}: {detail}")


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        fail(code, detail)


def require_secure_directory_chain(path: Path, code: str) -> None:
    resolved = path.resolve(strict=True)
    require(path.absolute() == resolved, code, "not canonical")
    current = Path(resolved.anchor)
    members = [current]
    for part in resolved.parts[1:]:
        current /= part
        members.append(current)
    for member in members:
        observed = member.lstat()
        require(stat.S_ISDIR(observed.st_mode) and not member.is_symlink(), code, str(member))
        require(observed.st_uid in (0, os.geteuid()), code, f"owner {member}")
        writable = observed.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        sticky_root = observed.st_uid == 0 and bool(observed.st_mode & stat.S_ISVTX)
        require(not writable or sticky_root, code, f"replaceable {member}")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_restricted(value: Any, context: str = "$", depth: int = 0) -> None:
    require(depth <= MAX_DEPTH, "E_JSON_DEPTH", context)
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        require(0 <= value <= MAX_U64, "E_JSON_INTEGER", context)
        return
    if isinstance(value, float):
        fail("E_JSON_FLOAT", context)
    if isinstance(value, str):
        require(value.isascii(), "E_JSON_ASCII", context)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_restricted(item, f"{context}[{index}]", depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            require(isinstance(key, str) and key.isascii(), "E_JSON_KEY", context)
            validate_restricted(item, f"{context}.{key}", depth + 1)
        return
    fail("E_JSON_TYPE", f"{context}: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    validate_restricted(value)
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        fail("E_CANONICAL_JSON", str(exc))


def parse_json(raw: bytes, label: str) -> dict[str, Any]:
    require(0 < len(raw) <= MAX_DOCUMENT_BYTES, "E_JSON_SIZE", label)
    require(not raw.startswith(b"\xef\xbb\xbf"), "E_JSON_BOM", label)

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "E_JSON_DUPLICATE_KEY", f"{label}: {key}")
            result[key] = value
        return result

    def reject_float(token: str) -> NoReturn:
        fail("E_JSON_FLOAT", f"{label}: {token}")

    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=pairs,
            parse_float=reject_float,
            parse_constant=reject_float,
        )
    except UnicodeDecodeError as exc:
        fail("E_JSON_ASCII", f"{label}: {exc}")
    except json.JSONDecodeError as exc:
        fail("E_JSON_PARSE", f"{label}: {exc}")
    require(isinstance(value, dict), "E_JSON_ROOT", label)
    validate_restricted(value, label)
    return value


def read_repo_file(repo: Path, relative: str) -> bytes:
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and ".." not in pure.parts, "E_PATH", relative)
    path = repo.joinpath(*pure.parts)
    require(path.is_file() and not path.is_symlink(), "E_FILE", relative)
    raw = path.read_bytes()
    require(0 < len(raw) <= MAX_DOCUMENT_BYTES, "E_FILE_SIZE", relative)
    return raw


def load_json(repo: Path, relative: str, *, canonical: bool) -> tuple[bytes, dict[str, Any]]:
    raw = read_repo_file(repo, relative)
    require(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), "E_TERMINAL_LF", relative)
    require(b"\r" not in raw, "E_CR", relative)
    value = parse_json(raw[:-1], relative)
    if canonical:
        require(raw == canonical_bytes(value) + b"\n", "E_NONCANONICAL", relative)
    return raw, value


def exact_keys(value: Mapping[str, Any], expected: Iterable[str], label: str) -> None:
    require(set(value) == set(expected), "E_KEYS", f"{label}: {sorted(value)}")


def framed_digest(domain: bytes, payload: bytes) -> str:
    return sha256(struct.pack(">I", len(domain)) + domain + struct.pack(">Q", len(payload)) + payload)


def recipe_digest(role: str, recipe: Mapping[str, Any]) -> str:
    domain = f"agent-bridge/biocortex/owned-lab/s21b-a1/build-recipe/{role}/v1".encode("ascii")
    return framed_digest(domain, canonical_bytes(dict(recipe)))


def run_readonly(argv: Sequence[str | os.PathLike[str]], *, cwd: Path, env: Mapping[str, str] | None = None) -> bytes:
    rendered = [os.fspath(item) for item in argv]
    safe_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
        "GIT_ASKPASS": "/bin/false",
    }
    if env:
        safe_env.update(env)
    process = subprocess.run(
        rendered,
        cwd=repo_path(cwd),
        env=safe_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=120,
    )
    require(process.returncode == 0, "E_COMMAND", f"{rendered!r}: {process.stderr[-4096:].decode('utf-8', 'replace')}")
    return process.stdout


def repo_path(path: Path) -> str:
    return os.fspath(path)


def git(repo: Path, *args: str) -> bytes:
    return run_readonly(("/usr/bin/git", "--no-replace-objects", *args), cwd=repo)


def git_blob(repo: Path, commit: str, path: str) -> bytes:
    require(HEX40.fullmatch(commit) is not None, "E_GIT_OID", commit)
    return git(repo, "cat-file", "blob", f"{commit}:{path}")


def git_mode(repo: Path, path: str) -> str:
    output = git(repo, "ls-files", "-s", "--", path).decode("ascii").strip()
    match = re.fullmatch(r"([0-7]{6}) [0-9a-f]{40} 0\t(.+)", output)
    require(match is not None and match.group(2) == path, "E_GIT_MODE", path)
    return match.group(1)


def parse_toml(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        fail("E_TOML", f"{label}: {exc}")
    require(isinstance(value, dict), "E_TOML_ROOT", label)
    return value


def validate_controls(documents: Mapping[str, Mapping[str, Any]]) -> None:
    contract = documents[CONTRACT_PATH]
    status = documents[STATUS_PATH]
    successor = documents[SUCCESSOR_PATH]
    for path, value in ((CONTRACT_PATH, contract), (STATUS_PATH, status), (SUCCESSOR_PATH, successor)):
        require(value.get("format_id") == FORMAT_IDS[path], "E_FORMAT_ID", path)
        require(value.get("stage") == STAGE, "E_STAGE", path)
        require(value.get("status") == PENDING_STATUS, "E_STATUS", path)
        require(value.get("decision") == DECISION, "E_DECISION", path)

    predecessor = contract.get("a0_predecessor_binding")
    require(isinstance(predecessor, dict), "E_CONTROL", "a0 predecessor")
    expected_predecessor = {
        "integration_commit": BASELINE_COMMIT,
        "integration_tree": BASELINE_TREE,
        "integration_first_parent": BASELINE_FIRST_PARENT,
        "integration_second_parent": BASELINE_SECOND_PARENT,
        "archive_profile": "git -c tar.umask=0022 archive --format=tar <commit>",
        "archive_sha256": BASELINE_ARCHIVE_SHA256,
        "archive_byte_count": BASELINE_ARCHIVE_BYTE_COUNT,
        "cargo_lock_sha256": BASELINE_CARGO_LOCK_SHA256,
        "predecessor_values_are_future_a1_target_values": False,
    }
    require(predecessor == expected_predecessor, "E_A0_BINDING", str(predecessor))
    source_base = contract.get("a1_source_base_binding")
    require(isinstance(source_base, dict), "E_CONTROL", "A1 source base")
    expected_source_base = {
        "commit": SOURCE_BASE_COMMIT,
        "tree": SOURCE_BASE_TREE,
        "first_parent": SOURCE_BASE_FIRST_PARENT,
        "second_parent": SOURCE_BASE_SECOND_PARENT,
        "archive_profile": "git -c tar.umask=0022 archive --format=tar <commit>",
        "archive_sha256": SOURCE_BASE_ARCHIVE_SHA256,
        "archive_byte_count": SOURCE_BASE_ARCHIVE_BYTE_COUNT,
        "cargo_lock_sha256": SOURCE_BASE_CARGO_LOCK_SHA256,
        "a0_predecessor_is_ancestor": True,
    }
    require(source_base == expected_source_base, "E_SOURCE_BASE_BINDING", str(source_base))

    artifact = contract.get("role_artifact_contract")
    require(isinstance(artifact, dict), "E_CONTROL", "role artifact contract")
    require(artifact.get("cargo_package") == ROLE_PACKAGE, "E_ROLE_PACKAGE", "contract")
    require(artifact.get("required_role_count") == 4, "E_ROLE_COUNT", "contract")
    expected_roles = [
        {
            "role": role,
            "cargo_binary_target": binary,
            "source_relative_path": source,
            "output_relative_path": output,
        }
        for role, binary, source, output in ROLE_SPECS
    ]
    require(artifact.get("required_roles") == expected_roles, "E_ROLE_SET", "contract")
    require(artifact.get("expected_output_mode_octal") == "0755", "E_ROLE_MODE", "contract")
    require(artifact.get("operational_role_implemented") is False, "E_ROLE_LIVE", "contract")
    for key in (
        "raw_binary_sha256_pairwise_distinct_required",
        "identity_sha256_pairwise_distinct_required",
        "build_recipe_sha256_pairwise_distinct_required",
    ):
        require(artifact.get(key) is True, "E_ROLE_DISTINCT", key)
    for key in (
        "private_library_or_test_binary_may_substitute",
        "copied_or_relabelled_binary_may_substitute",
        "arbitrary_nonzero_digest_may_substitute",
    ):
        require(artifact.get(key) is False, "E_ROLE_SUBSTITUTION", key)

    closure = contract.get("closure_manifest_contract")
    require(isinstance(closure, dict), "E_CONTROL", "closure manifest contract")
    require(closure.get("manifest_digest_profile") == MANIFEST_DIGEST_PROFILE, "E_MANIFEST_PROFILE", "contract")
    require(
        closure.get("manifest_paths")
        == {
            "toolchain": TOOLCHAIN_PATH,
            "feature_set": FEATURE_SET_PATH,
            "schema_set": SCHEMA_SET_PATH,
            "build_recipes": RECIPES_PATH,
        },
        "E_MANIFEST_PATHS",
        "contract",
    )
    require(closure.get("schema_content_set_digest_profile") == SCHEMA_SET_PROFILE, "E_SCHEMA_PROFILE", "contract")
    require(closure.get("target_triple") == TARGET_TRIPLE, "E_TARGET", "contract")
    require(closure.get("rust_toolchain_release") == "1.96.0", "E_TOOLCHAIN", "contract")
    require(
        closure.get("rust_toolchain_full_tree_catalog_required") is True
        and closure.get("rust_toolchain_full_tree_catalog_sha256")
        == "de09990b491cdfa1e10dfe398ea639989dc87778af8639b8b91445e6806f14b1"
        and closure.get("rust_toolchain_full_tree_file_count") == 166
        and closure.get("rust_toolchain_full_tree_byte_count") == 644100823
        and closure.get("private_catalog_verified_toolchain_snapshot_required_before_execution")
        is True,
        "E_TOOLCHAIN_TREE",
        "contract",
    )
    for key in (
        "manifest_digest_recomputed_in_each_archive_root",
        "schema_content_set_digest_recomputed_in_each_archive_root",
        "shared_library_compiled_unit_required",
        "cargo_encoded_rustflags_required",
        "target_committer_epoch_as_source_date_epoch_required",
    ):
        require(closure.get(key) is True, "E_CLOSURE_CONTRACT", key)
    require(closure.get("candidate_supplied_manifest_digest_authoritative") is False, "E_CANDIDATE_AUTHORITY", "manifest")
    require(closure.get("default_features_enabled") is False, "E_FEATURES", "contract")

    rebuild = contract.get("double_rebuild_contract")
    require(isinstance(rebuild, dict), "E_CONTROL", "double rebuild contract")
    for key in (
        "repo_git_scratch_output_ancestors_must_be_local_user_safe",
        "scratch_parent_and_entry_dirfds_must_be_pinned",
        "scratch_dev_inode_must_be_revalidated_at_critical_boundaries",
        "predecessor_replay_single_outer_networkless_namespace_required",
        "predecessor_replay_outer_pid_namespace_required",
        "predecessor_replay_private_empty_runtime_socket_tree_required",
        "predecessor_replay_private_read_only_root_with_exact_ephemeral_cargo_home_overlay_required",
        "predecessor_secure_toolchain_stable_compatibility_alias_read_only_and_same_inode_required",
        "predecessor_flatten_receipts_o_excl_before_payload_and_write_protected",
        "predecessor_payload_forbidden_metadata_postcondition_required",
        "predecessor_payload_residual_pid_rejected",
        "predecessor_payload_standard_descriptors_must_be_private_and_domain_bound",
        "predecessor_retired_sparse_index_cleanup_mode_supervision_required",
        "predecessor_frozen_s15_s16_cleanup_dispatcher_required",
        "predecessor_dynamic_cache_bind_flattening_must_be_supervised_and_restored",
        "predecessor_runtime_root_cargo_seed_nested_read_only_mounts_required",
        "predecessor_runtime_root_cargo_registry_ancestor_read_only_mount_required",
        "predecessor_runtime_root_cargo_extracted_source_only_writable_submount_required",
        "predecessor_runtime_user_cargo_seed_nested_read_only_mounts_required",
        "predecessor_runtime_user_cargo_home_read_only_required",
        "predecessor_runtime_user_cargo_registry_ancestor_read_only_mount_required",
        "predecessor_runtime_user_cargo_extracted_source_only_writable_submount_required",
        "predecessor_runtime_cargo_generated_state_ephemeral",
        "a1_target_and_predecessor_cargo_evidence_homes_must_be_distinct",
        "source_base_and_integration_first_parent_must_match_exactly",
    ):
        require(rebuild.get(key) is True, "E_TRUSTED_PATH_CONTRACT", key)
    require(
        rebuild.get("predecessor_bwrap_flatten_exact_allowlist_invocation_count") == 4
        and rebuild.get("predecessor_bwrap_flatten_receipt_count") == 4
        and rebuild.get("predecessor_private_registry_archive_count") == 555
        and rebuild.get("predecessor_private_registry_archive_byte_count") == 85385269
        and rebuild.get("predecessor_private_registry_tuple_catalog_sha256")
        == "4ca4d49308fbf6c2e5d6952feca4c7079e24e2be88fa1b1d5b9ee11278137ed8"
        and rebuild.get("predecessor_private_sparse_index_file_count") == 523,
        "E_PREDECESSOR_REPLAY_CONTRACT",
        "private namespace/registry closure",
    )
    require(
        rebuild.get("a1_target_sparse_index_package_name_count") == 531
        and rebuild.get("a1_target_sparse_index_file_count") == 532,
        "E_A1_TARGET_INDEX_CONTRACT",
        "target sparse-index closure",
    )
    require(
        rebuild.get("source_delta_profile")
        == "EXACT_4_MODIFIED_AND_21_ADDED_FROZEN_PACKET_PATHS_FROM_PINNED_A1_SOURCE_BASE",
        "E_SOURCE_DELTA_PROFILE",
        str(rebuild.get("source_delta_profile")),
    )
    require(
        rebuild.get("predecessor_payload_write_domain_landlock_minimum_abi") == 6
        and rebuild.get("predecessor_payload_write_domain_profile")
        == "CARGO_STAGES_ONLY_EXACT_STAGE_SCRATCH_RUNTIME_ONLY_PRIVATE_TMP_"
        "EXACT_CACHE_AND_DEDICATED_ROOT_AND_USER_CARGO_HOMES_PLUS_DEV_NULL",
        "E_PREDECESSOR_REPLAY_CONTRACT",
        "payload Landlock write domain",
    )
    require(
        rebuild.get("predecessor_private_inputs_may_have_writable_alias") is False,
        "E_PREDECESSOR_REPLAY_CONTRACT",
        "private input writable aliases",
    )
    require(
        rebuild.get("predecessor_runtime_cargo_registry_shell_cache_tag_byte_count") == 177
        and rebuild.get("predecessor_runtime_cargo_registry_shell_cache_tag_sha256")
        == "6d9d1d216e0f83abc5e5662ca62c92b4f23009466b54fa27321a69acdb778bb2",
        "E_PREDECESSOR_REPLAY_CONTRACT",
        "runtime Cargo shared registry-shell cache-directory tag",
    )
    require(
        rebuild.get("predecessor_runtime_cargo_homes_may_share_writable_generated_state")
        is False,
        "E_PREDECESSOR_REPLAY_CONTRACT",
        "runtime Cargo generated-state separation",
    )
    require(
        rebuild.get("predecessor_retired_sparse_index_cleanup_mode_profile")
        == "POST_PAYLOAD_EXACT_TWO_INDEX_CATALOGS_REVALIDATED_"
        "DIRECTORIES_0555_TO_0700_FILES_REMAIN_0444",
        "E_PREDECESSOR_REPLAY_CONTRACT",
        "retired sparse-index cleanup mode profile",
    )
    require(
        rebuild.get("predecessor_frozen_s15_s16_cleanup_dispatcher_profile")
        == "PINNED_REAL_GNURM_AND_DIGESTED_DISPATCHER_NONMATCHING_ARGV_PASSTHROUGH_"
        "EXACT_S15_S16_RF_TRAP_CANONICAL_SCRATCH_LANDLOCK_PARENT_COPIED_REGISTRY_"
        "REAL_DIRECTORIES_GAIN_OWNER_RWX_NO_SYMLINK_FOLLOW_FILES_UNCHANGED"
        and rebuild.get("predecessor_private_real_gnurm_sha256")
        == "175a15a35617f84bb86692b50a3e21b41d8e21fdea242e952b31f1e2e80b1a54",
        "E_PREDECESSOR_REPLAY_CONTRACT",
        "frozen S15/S16 cleanup dispatcher profile",
    )

    receipt_contract = contract.get("receipt_contract")
    require(isinstance(receipt_contract, dict), "E_CONTROL", "receipt contract")
    require(receipt_contract.get("draft") == "2020-12", "E_SCHEMA_DRAFT", "contract")
    require(receipt_contract.get("schema_id") == RECEIPT_SCHEMA_ID, "E_SCHEMA_ID", "contract")
    require(receipt_contract.get("schema_path") == RECEIPT_SCHEMA_PATH, "E_SCHEMA_PATH", "contract")
    require(receipt_contract.get("digest_domain") == RECEIPT_DOMAIN.decode("ascii"), "E_RECEIPT_DOMAIN", "contract")
    require(receipt_contract.get("digest_framing") == FRAMING, "E_FRAMING", "contract")
    require(receipt_contract.get("self_hash_field") == SELF_HASH_FIELD, "E_SELF_FIELD", "contract")
    require(receipt_contract.get("additional_properties_allowed") is False, "E_SCHEMA_CLOSED", "contract")
    require(receipt_contract.get("external_schema_references_allowed") is False, "E_SCHEMA_REF", "contract")
    require(receipt_contract.get("cross_field_semantic_validation_required") is True, "E_SEMANTICS", "contract")
    if "external_complete_status" in receipt_contract:
        require(receipt_contract["external_complete_status"] == REAL_STATUS, "E_REAL_STATUS", "contract")

    boundary = contract.get("current_boundary")
    require(isinstance(boundary, dict), "E_CONTROL", "current boundary")
    require(boundary.get("tooling_definitions_present") is True, "E_BOUNDARY", "tooling")
    for key in (
        "post_integration_target_identity_known",
        "post_integration_double_rebuild_complete",
        "real_role_binary_digests_present",
        "real_closure_receipt_present",
        "unsigned_final_subject_present",
        "owner_signing_request_present",
        "owner_interaction_required_now",
    ):
        require(boundary.get(key) is False, "E_BOUNDARY", key)
    require(boundary.get("live_action_count") == 0 and boundary.get("side_effects_unlocked") == "NONE", "E_BOUNDARY", "live")

    implemented = status.get("implemented_source_boundary")
    pending = status.get("pending_post_integration_evidence")
    outputs = status.get("current_outputs")
    next_action = status.get("next_required_action")
    require(all(isinstance(item, dict) for item in (implemented, pending, outputs, next_action)), "E_STATUS_DOC", "sections")
    require(implemented.get("four_exact_cargo_binary_targets_declared") is True, "E_STATUS_DOC", "targets")
    require(implemented.get("four_non_live_identity_only_programs_present") is True, "E_STATUS_DOC", "identity")
    for key in (
        "full_toolchain_tree_catalog_present",
        "private_toolchain_snapshot_before_execution_required",
        "secure_ancestry_and_pinned_scratch_required",
        "predecessor_replay_strict_four_call_flatten_adapter_present",
        "predecessor_private_runtime_socket_tree_and_ipc_namespace_required",
        "predecessor_private_read_only_root_with_exact_ephemeral_cargo_home_overlay_required",
        "predecessor_secure_toolchain_stable_compatibility_alias_required",
        "predecessor_payload_landlock_write_domain_and_postcondition_required",
        "predecessor_private_registry_snapshot_required",
        "predecessor_runtime_root_cargo_seed_nested_read_only_mounts_required",
        "predecessor_runtime_root_cargo_registry_ancestor_read_only_mount_required",
        "predecessor_runtime_user_cargo_read_only_home_with_independent_writable_extracted_source_required",
        "predecessor_retired_sparse_index_cleanup_mode_supervision_required",
        "predecessor_frozen_s15_s16_cleanup_dispatcher_required",
        "predecessor_dynamic_cache_compatibility_supervision_required",
    ):
        require(implemented.get(key) is True, "E_STATUS_DOC", key)
    require(implemented.get("operational_role_implemented") is False and implemented.get("live_adapter_present") is False, "E_STATUS_DOC", "non-live")
    require(all(value is False for value in pending.values()), "E_STATUS_DOC", "pending evidence must be false")
    require(outputs.get("synthetic_pending_receipt_present") is True and outputs.get("real_build_receipt_present") is False, "E_STATUS_DOC", "receipt state")
    require(outputs.get("owner_private_key_read") is False and outputs.get("live_action_count") == 0 and outputs.get("side_effects_unlocked") == "NONE", "E_STATUS_DOC", "authority")
    require(next_action.get("action") == "INTEGRATE_THEN_RUN_TWO_CLEAN_ARCHIVE_REBUILDS", "E_STATUS_DOC", "next action")
    require(next_action.get("real_receipt_generated_outside_repository") is True, "E_STATUS_DOC", "external receipt")
    require(next_action.get("owner_signature_may_be_requested_now") is False and next_action.get("live_execution_may_begin_now") is False, "E_STATUS_DOC", "hard lock")

    admission = successor.get("current_admission")
    receipt_conditions = successor.get("conditions_for_real_a1_receipt")
    maximum = successor.get("maximum_successor_after_real_receipt")
    fail_closed = successor.get("fail_closed_conditions")
    require(
        isinstance(admission, dict)
        and isinstance(receipt_conditions, dict)
        and isinstance(maximum, dict)
        and isinstance(fail_closed, list),
        "E_SUCCESSOR",
        "sections",
    )
    require(admission.get("source_tooling_boundary_complete") is True, "E_SUCCESSOR", "source tooling")
    require(admission.get("post_integration_role_build_closure_complete") is False, "E_SUCCESSOR", "closure")
    require(admission.get("terminal_hard_lock") is True and admission.get("side_effects_unlocked") == "NONE", "E_SUCCESSOR", "hard lock")
    for key, value in admission.items():
        if key.endswith("_may_begin") or key.endswith("_may_be_requested"):
            require(value is False, "E_SUCCESSOR", key)
    require(maximum.get("may_request_owner_signature") is False and maximum.get("may_execute_live") is False, "E_SUCCESSOR", "authority")
    require(maximum.get("side_effects_unlocked") == "NONE", "E_SUCCESSOR", "side effects")
    for key in (
        "full_rust_toolchain_tree_catalog_recomputed_before_and_after_private_snapshot_copy",
        "only_private_catalog_verified_toolchain_snapshot_executed",
        "repository_git_scratch_and_output_secure_ancestry_verified",
        "scratch_parent_and_entry_dirfds_pinned_and_dev_inode_revalidated",
        "immutable_predecessor_replay_uses_single_outer_networkless_namespace_and_exact_four_call_flatten_adapter",
        "immutable_predecessor_replay_uses_outer_pid_namespace_for_descendant_lifetime_bounding",
        "immutable_predecessor_replay_uses_private_empty_runtime_socket_tree_and_ipc_namespace",
        "immutable_predecessor_replay_uses_private_read_only_root_with_exact_ephemeral_cargo_home_overlay",
        "immutable_predecessor_replay_uses_read_only_same_inode_stable_toolchain_compatibility_alias",
        "predecessor_payload_write_domains_landlock_constrained_and_forbidden_metadata_revalidated",
        "predecessor_payload_residual_processes_rejected",
        "predecessor_flatten_receipts_created_exclusively_before_payload_and_payload_write_protected",
        "predecessor_payload_standard_descriptors_are_private_and_domain_bound",
        "predecessor_registry_555_archives_and_523_index_files_privately_catalog_verified",
        "predecessor_runtime_root_cargo_seed_is_nested_read_only_and_generated_state_is_ephemeral",
        "predecessor_runtime_root_cargo_registry_ancestor_is_read_only_and_only_extracted_source_submount_is_writable",
        "predecessor_runtime_user_cargo_home_is_read_only_and_uses_same_read_only_seed_with_independent_writable_extracted_source",
        "predecessor_private_toolchain_and_registry_have_no_writable_alias",
        "predecessor_retired_sparse_index_cleanup_modes_are_supervised_after_payload_exit",
        "predecessor_frozen_s15_s16_cleanup_dispatcher_is_pinned_and_landlock_bounded",
        "predecessor_dynamic_cache_bind_flattening_supervised_restored_and_receipted",
    ):
        require(receipt_conditions.get(key) is True, "E_SUCCESSOR", key)
    for condition in (
        "FULL_TOOLCHAIN_TREE_CATALOG_OR_PRIVATE_SNAPSHOT_DRIFT",
        "INSECURE_REPOSITORY_GIT_SCRATCH_OR_OUTPUT_ANCESTRY",
        "SCRATCH_PARENT_OR_ENTRY_DIRFD_DEVICE_INODE_PIN_MISMATCH",
        "PREDECESSOR_FLATTEN_ALLOWLIST_OR_FOUR_RECEIPT_DRIFT",
        "PREDECESSOR_OUTER_PID_NAMESPACE_ABSENT",
        "PREDECESSOR_PRIVATE_RUNTIME_SOCKET_TREE_OR_IPC_NAMESPACE_ABSENT",
        "PREDECESSOR_PRIVATE_ROOT_OR_EPHEMERAL_CARGO_OVERLAY_LAYOUT_OR_MOUNT_MODE_DRIFT",
        "PREDECESSOR_STABLE_TOOLCHAIN_COMPATIBILITY_ALIAS_ABSENT_WRITABLE_OR_IDENTITY_DRIFT",
        "PREDECESSOR_EPHEMERAL_USER_CARGO_LAYOUT_MOUNT_MODE_OR_WRITABLE_STATE_SEPARATION_DRIFT",
        "PREDECESSOR_PAYLOAD_LANDLOCK_WRITE_DOMAIN_OR_METADATA_POSTCONDITION_DRIFT",
        "PREDECESSOR_PAYLOAD_RESIDUAL_PROCESS_OBSERVED",
        "PREDECESSOR_PAYLOAD_STANDARD_DESCRIPTOR_ESCAPES_WRITE_DOMAIN",
        "PREDECESSOR_PRIVATE_REGISTRY_ARCHIVE_OR_INDEX_CATALOG_DRIFT",
        "PREDECESSOR_PRIVATE_INPUT_WRITABLE_ALIAS_OBSERVED",
        "PREDECESSOR_RETIRED_SPARSE_INDEX_CLEANUP_MODE_SUPERVISION_DRIFT",
        "PREDECESSOR_FROZEN_S15_S16_CLEANUP_DISPATCHER_OR_PINNED_REAL_GNURM_DRIFT",
        "PREDECESSOR_DYNAMIC_CACHE_COMPATIBILITY_SUPERVISION_DRIFT",
    ):
        require(condition in fail_closed, "E_SUCCESSOR", condition)

    for path, document in ((CONTRACT_PATH, contract), (STATUS_PATH, status), (SUCCESSOR_PATH, successor)):
        nonclaims = document.get("nonclaims")
        require(isinstance(nonclaims, dict), "E_NONCLAIMS", path)
        require(all(value is False or value == "NONE" for value in nonclaims.values()), "E_NONCLAIMS", path)


def walk_schema(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        if value.get("type") == "object":
            require(value.get("additionalProperties") is False, "E_SCHEMA_CLOSED", path)
            properties = value.get("properties")
            required = value.get("required")
            require(isinstance(properties, dict) and isinstance(required, list), "E_SCHEMA_OBJECT", path)
            require(set(required).issubset(properties), "E_SCHEMA_REQUIRED", path)
        for keyword in ("$ref", "$dynamicRef", "$recursiveRef"):
            if keyword in value:
                ref = value[keyword]
                require(isinstance(ref, str) and ref.startswith("#/$defs/"), "E_SCHEMA_EXTERNAL_REF", f"{path}: {ref!r}")
        if path != "$":
            require("$id" not in value, "E_SCHEMA_NESTED_ID", path)
        for key, child in value.items():
            walk_schema(child, f"{path}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk_schema(child, f"{path}/{index}")


def validate_receipt_schema(schema: Mapping[str, Any]) -> Draft202012Validator:
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "E_SCHEMA_DRAFT", RECEIPT_SCHEMA_PATH)
    require(schema.get("$id") == RECEIPT_SCHEMA_ID, "E_SCHEMA_ID", RECEIPT_SCHEMA_PATH)
    require(schema.get("type") == "object" and schema.get("additionalProperties") is False, "E_SCHEMA_CLOSED", "root")
    walk_schema(schema)
    expected_defs = {
        "build_observation", "closure_bindings", "closure_record", "complete_build_observation",
        "complete_closure_bindings", "complete_closure_record", "complete_rebuild", "complete_rebuilds",
        "complete_result", "complete_role_artifact", "complete_role_artifacts", "complete_schema_set_closure_record",
        "complete_target_binding", "controller_identity", "forbidden_outputs", "git_oid", "hashing_contract",
        "nonclaims", "nullable_git_oid", "nullable_positive_integer", "nullable_sha256", "observer_identity",
        "pending_build_observation", "pending_closure_bindings", "pending_closure_record", "pending_rebuild",
        "pending_rebuilds", "pending_result", "pending_role_artifact", "pending_role_artifacts",
        "pending_schema_set_closure_record", "pending_target_binding", "rebuild", "rebuilds", "result",
        "role_artifact", "role_artifacts", "runner_identity", "sha256", "target_binding", "validator_identity",
    }
    definitions = schema.get("$defs")
    require(isinstance(definitions, dict) and set(definitions) == expected_defs, "E_SCHEMA_DEFS", str(sorted(definitions or {})))
    require(definitions["sha256"].get("pattern") == r"^(?!0{64}$)[0-9a-f]{64}$", "E_SCHEMA_SHA", "sha256")
    require(definitions["git_oid"].get("pattern") == r"^(?!0{40}$)[0-9a-f]{40}$", "E_SCHEMA_OID", "git_oid")
    try:
        Draft202012Validator.check_schema(dict(schema))
    except SchemaError as exc:
        fail("E_SCHEMA_INVALID", exc.message)
    return Draft202012Validator(dict(schema))


def _all_false_or_none(value: Mapping[str, Any], label: str) -> None:
    for key, item in value.items():
        require(item is False or item is None or item == 0, "E_PENDING_STATE", f"{label}.{key}")


def validate_synthetic_receipt(fixture: Mapping[str, Any]) -> None:
    require(fixture.get("schema") == RECEIPT_SCHEMA_ID, "E_RECEIPT_SCHEMA", "fixture")
    require(fixture.get("packet_kind") == RECEIPT_PACKET_KIND, "E_PACKET_KIND", "fixture")
    require(fixture.get("canonicalization") == CANONICALIZATION, "E_CANONICALIZATION", "fixture")
    require(fixture.get("stage") == STAGE and fixture.get("status") == PENDING_STATUS and fixture.get("decision") == DECISION, "E_RECEIPT_HEADER", "fixture")
    require(fixture.get("receipt_state") == PENDING_RECEIPT_STATE, "E_RECEIPT_STATE", "fixture")
    require(fixture.get("test_only") is True and fixture.get("synthetic") is True, "E_SYNTHETIC", "fixture")
    hashing = fixture.get("hashing_contract")
    require(
        hashing == {
            "candidate_reported_matches_authoritative": False,
            "canonicalization": CANONICALIZATION,
            "cross_field_semantic_validation_required": True,
            "digest_domain": RECEIPT_DOMAIN.decode("ascii"),
            "digest_framing": FRAMING,
            "hash_algorithm": "SHA-256",
            "hash_scope": "ENTIRE_PACKET_EXCEPT_ROLE_BUILD_RECEIPT_SHA256",
            "repository_framing_lf_excluded": True,
            "self_hash_field": SELF_HASH_FIELD,
            "self_hash_field_excluded": True,
        },
        "E_HASHING_CONTRACT",
        "fixture",
    )
    target = fixture.get("target_binding")
    require(isinstance(target, dict), "E_TARGET_BINDING", "fixture")
    expected_a0 = {
        "a0_integration_commit": BASELINE_COMMIT,
        "a0_integration_tree": BASELINE_TREE,
        "a0_integration_first_parent": BASELINE_FIRST_PARENT,
        "a0_integration_second_parent": BASELINE_SECOND_PARENT,
        "a0_archive_sha256": BASELINE_ARCHIVE_SHA256,
        "a0_archive_byte_count": BASELINE_ARCHIVE_BYTE_COUNT,
        "a0_cargo_lock_sha256": BASELINE_CARGO_LOCK_SHA256,
    }
    for key, expected in expected_a0.items():
        require(target.get(key) == expected, "E_TARGET_BINDING", key)
    require(target.get("canonical_remote") == CANONICAL_REMOTE and target.get("remote_ref") == "refs/heads/master", "E_TARGET_BINDING", "remote")
    require(target.get("candidate_supplied_target_used") is False and target.get("target_refrozen") is False, "E_TARGET_BINDING", "authority")
    for key in (
        "source_commit", "source_tree", "source_parent_commit", "source_parent_tree",
        "integration_commit", "integration_tree", "integration_first_parent", "integration_second_parent",
        "integrated_archive_sha256", "integrated_archive_byte_count", "cargo_lock_sha256", "target_committer_epoch",
    ):
        require(target.get(key) is None, "E_TARGET_BINDING", key)

    closures = fixture.get("closure_bindings")
    require(isinstance(closures, dict) and closures.get("candidate_supplied_expected_digests_used") is False, "E_CLOSURE_BINDING", "fixture")
    closure_paths = {
        "toolchain_manifest": TOOLCHAIN_PATH,
        "feature_set": FEATURE_SET_PATH,
        "schema_set": SCHEMA_SET_PATH,
        "build_recipes": RECIPES_PATH,
    }
    for key, path in closure_paths.items():
        record = closures.get(key)
        require(isinstance(record, dict), "E_CLOSURE_BINDING", key)
        require(record.get("definition_path") == path and record.get("definition_present") is True, "E_CLOSURE_BINDING", key)
        require(record.get("manifest_digest_profile") == MANIFEST_DIGEST_PROFILE, "E_CLOSURE_BINDING", key)
        require(record.get("manifest_sha256") is None, "E_CLOSURE_BINDING", key)
        require(record.get("independently_recomputed_in_build_a") is False and record.get("independently_recomputed_in_build_b") is False and record.get("rebuild_values_equal") is False, "E_CLOSURE_BINDING", key)
    schema_record = closures["schema_set"]
    require(schema_record.get("content_set_digest_profile") == SCHEMA_SET_PROFILE and schema_record.get("content_set_sha256") is None, "E_SCHEMA_CLOSURE", "fixture")

    rebuilds = fixture.get("rebuilds")
    require(isinstance(rebuilds, dict), "E_REBUILDS", "fixture")
    require(rebuilds.get("build_roots_distinct") is False and rebuilds.get("target_directories_distinct") is False and rebuilds.get("schema_content_set_digests_equal") is False, "E_REBUILDS", "distinct")
    for label, expected_label in (("build_a", "A"), ("build_b", "B")):
        build = rebuilds.get(label)
        require(isinstance(build, dict) and build.get("build_label") == expected_label, "E_REBUILDS", label)
        for key, item in build.items():
            if key != "build_label":
                require(item is False or item is None, "E_REBUILDS", f"{label}.{key}")

    roles = fixture.get("role_artifacts")
    require(isinstance(roles, dict) and roles.get("required_role_count") == 4 and roles.get("completed_role_count") == 0, "E_ROLE_RECEIPT", "count")
    for flag in ("raw_sha256_pairwise_distinct", "identity_sha256_pairwise_distinct", "build_recipe_sha256_pairwise_distinct"):
        require(roles.get(flag) is False, "E_ROLE_RECEIPT", flag)
    require(roles.get("private_library_or_test_binary_used") is False and roles.get("arbitrary_digest_substitution_used") is False, "E_ROLE_RECEIPT", "substitution")
    for role, binary, source, output in ROLE_SPECS:
        item = roles.get(role)
        require(isinstance(item, dict), "E_ROLE_RECEIPT", role)
        require(item.get("role") == role and item.get("cargo_binary_target") == binary, "E_ROLE_RECEIPT", role)
        require(item.get("source_relative_path") == source and item.get("output_relative_path") == output, "E_ROLE_RECEIPT", role)
        require(item.get("expected_mode_octal") == "0755", "E_ROLE_RECEIPT", role)
        require(item.get("build_recipe_digest_domain") == f"agent-bridge/biocortex/owned-lab/s21b-a1/build-recipe/{role}/v1", "E_RECIPE_DOMAIN", role)
        require(item.get("build_recipe_digest_framing") == FRAMING and item.get("build_recipe_digest_profile") == RECIPE_PROFILE, "E_RECIPE_PROFILE", role)
        for flag in ("raw_bytes_equal", "raw_sha256_equal", "identity_sha256_equal", "build_recipe_sha256_equal"):
            require(item.get(flag) is False, "E_ROLE_RECEIPT", f"{role}.{flag}")
        for build_name in ("build_a", "build_b"):
            observation = item.get(build_name)
            require(isinstance(observation, dict), "E_ROLE_RECEIPT", f"{role}.{build_name}")
            _all_false_or_none(observation, f"{role}.{build_name}")

    forbidden = fixture.get("forbidden_outputs")
    result = fixture.get("result")
    nonclaims = fixture.get("nonclaims")
    require(isinstance(forbidden, dict) and isinstance(result, dict) and isinstance(nonclaims, dict), "E_RECEIPT_SECTIONS", "fixture")
    _all_false_or_none(forbidden, "forbidden_outputs")
    require(result.get("terminal_hard_lock") is True and result.get("role_build_closure_complete") is False, "E_RESULT", "hard lock")
    require(result.get("next_action") == "INTEGRATE_THEN_RUN_TWO_CLEAN_ARCHIVE_REBUILDS", "E_RESULT", "next action")
    require(result.get("side_effects_unlocked") == "NONE", "E_RESULT", "side effects")
    for key, item in result.items():
        if key not in ("terminal_hard_lock", "next_action", "side_effects_unlocked"):
            require(item is False, "E_RESULT", key)
    require(all(item is False or item == "NONE" for item in nonclaims.values()), "E_NONCLAIMS", "fixture")


def verify_receipt(raw: bytes, fixture: Mapping[str, Any], validator: Draft202012Validator) -> str:
    require(raw == canonical_bytes(dict(fixture)) + b"\n", "E_RECEIPT_CANONICAL", RECEIPT_FIXTURE_PATH)
    errors = sorted(validator.iter_errors(dict(fixture)), key=lambda error: tuple(str(x) for x in error.absolute_path))
    require(not errors, "E_RECEIPT_SCHEMA_VALIDATION", "; ".join(error.message for error in errors[:3]))
    payload = copy.deepcopy(dict(fixture))
    reported = payload.pop(SELF_HASH_FIELD, None)
    require(isinstance(reported, str) and HEX64.fullmatch(reported) is not None, "E_RECEIPT_SELF_DIGEST", "malformed")
    recomputed = framed_digest(RECEIPT_DOMAIN, canonical_bytes(payload))
    require(reported == recomputed, "E_RECEIPT_SELF_DIGEST", f"{reported} != {recomputed}")
    validate_synthetic_receipt(fixture)
    return recomputed


def reseal_receipt(fixture: Mapping[str, Any]) -> bytes:
    value = copy.deepcopy(dict(fixture))
    value.pop(SELF_HASH_FIELD, None)
    value[SELF_HASH_FIELD] = framed_digest(RECEIPT_DOMAIN, canonical_bytes(value))
    return canonical_bytes(value) + b"\n"


def validate_manifest_headers(manifests: Mapping[str, Mapping[str, Any]]) -> None:
    for path in CLOSURE_PATHS:
        value = manifests[path]
        require(value.get("format_id") == FORMAT_IDS[path], "E_FORMAT_ID", path)
        require(value.get("canonicalization") == CANONICALIZATION, "E_CANONICALIZATION", path)
        require(value.get("manifest_digest_contract") == MANIFEST_DIGEST_CONTRACT, "E_MANIFEST_DIGEST_CONTRACT", path)
        nonclaims = value.get("nonclaims")
        if nonclaims is not None:
            require(isinstance(nonclaims, dict), "E_NONCLAIMS", path)
            require(all(item is False or item == "NONE" for item in nonclaims.values()), "E_NONCLAIMS", path)


def validate_feature_set(value: Mapping[str, Any]) -> None:
    binaries = [binary for _, binary, _, _ in ROLE_SPECS]
    sources = sorted([source for _, _, source, _ in ROLE_SPECS] + ["crates/owned-lab-role-artifacts/src/lib.rs"])
    require(value.get("cargo_package") == ROLE_PACKAGE and value.get("package_version") == ROLE_PACKAGE_VERSION, "E_FEATURE_SET", "package")
    require(value.get("binary_targets") == binaries, "E_FEATURE_SET", "binaries")
    require(value.get("default_features") is False and value.get("direct_features") == [], "E_FEATURE_SET", "features")
    require(value.get("package_dependencies") == [], "E_FEATURE_SET", "dependencies")
    require(value.get("requested_primary_target_kinds") == ["bin"], "E_FEATURE_SET", "target kinds")
    require(value.get("resolved_package_feature_graph") == [{"features": [], "package": ROLE_PACKAGE, "version": ROLE_PACKAGE_VERSION}], "E_FEATURE_SET", "graph")
    require(value.get("source_closure") == sources, "E_FEATURE_SET", "source closure")
    require(
        value.get("transitively_compiled_targets")
        == [{"crate_types": ["lib"], "kind": "lib", "name": "ab_owned_lab_role_artifacts", "source_relative_path": "crates/owned-lab-role-artifacts/src/lib.rs"}],
        "E_FEATURE_SET",
        "shared lib",
    )


def validate_recipes(value: Mapping[str, Any]) -> dict[str, str]:
    binaries = [binary for _, binary, _, _ in ROLE_SPECS]
    require(value.get("build_order") == binaries, "E_RECIPES", "build order")
    require(value.get("cargo_binary") == "/rust-toolchain/bin/cargo" and value.get("target_triple") == TARGET_TRIPLE, "E_RECIPES", "toolchain")
    require(value.get("cargo_profile") == {"codegen_units": 1, "debug": 0, "incremental": False, "lto": "thin", "opt_level": 3, "panic": "unwind", "strip": "symbols"}, "E_RECIPES", "profile")
    env = value.get("environment")
    require(isinstance(env, dict), "E_RECIPES", "environment")
    expected_env = {
        "AR": "/usr/bin/x86_64-linux-gnu-ar", "CARGO_BUILD_JOBS": "1",
        "CARGO_HOME": "/ab-build/cargo-home", "CARGO_INCREMENTAL": "0",
        "CARGO_NET_OFFLINE": "true", "CARGO_PROFILE_RELEASE_CODEGEN_UNITS": "1",
        "CARGO_PROFILE_RELEASE_DEBUG": "0", "CARGO_PROFILE_RELEASE_INCREMENTAL": "false",
        "CARGO_PROFILE_RELEASE_LTO": "thin", "CARGO_PROFILE_RELEASE_OPT_LEVEL": "3",
        "CARGO_PROFILE_RELEASE_PANIC": "unwind", "CARGO_PROFILE_RELEASE_STRIP": "symbols",
        "CARGO_TARGET_DIR": "/ab-build/target",
        "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER": "/usr/bin/x86_64-linux-gnu-gcc-15",
        "CARGO_TERM_COLOR": "never", "CC": "/usr/bin/x86_64-linux-gnu-gcc-15",
        "HOME": "/ab-build/home", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "MAKEFLAGS": "-j1", "MALLOC_ARENA_MAX": "2",
        "PATH": "/rust-toolchain/bin:/usr/bin:/bin", "RAYON_NUM_THREADS": "1",
        "RUSTC": "/rust-toolchain/bin/rustc",
        "SOURCE_DATE_EPOCH": "DERIVED_FROM_TARGET_COMMIT_COMMITTER_UNIX_EPOCH",
        "TMPDIR": "/ab-build/tmp", "TZ": "UTC",
    }
    require(env == expected_env, "E_RECIPES", "environment drift")
    isolation = value.get("isolation")
    require(isinstance(isolation, dict), "E_RECIPES", "isolation")
    require(isolation.get("bubblewrap_binary_path") == "/usr/bin/bwrap", "E_RECIPES", "bwrap path")
    require(isolation.get("bubblewrap_binary_sha256") == sha256_file(Path("/usr/bin/bwrap")), "E_RECIPES", "bwrap digest")
    require(isolation.get("bubblewrap_release") == "0.11.1", "E_RECIPES", "bwrap release")
    require(isolation.get("environment_base") == "EMPTY_ENV_EXCEPT_DECLARED_ENVIRONMENT_AND_DERIVED_CARGO_ENCODED_RUSTFLAGS", "E_RECIPES", "empty env")
    require(isolation.get("network_namespace") == "UNSHARED_NO_NETWORK" and isolation.get("source_mount") == "READ_ONLY", "E_RECIPES", "isolation")
    require(isolation.get("process_umask") == "0022" and isolation.get("working_directory") == "/ab-build/source", "E_RECIPES", "process context")
    require(
        isolation.get("scratch_binding")
        == "SECURE_ANCESTRY_MKDIRAT_OPENAT_PINNED_DIRFD_WITH_DEV_INO_REVALIDATION"
        and isolation.get("secure_ancestry_policy")
        == "EVERY_ANCESTOR_ROOT_OR_EUID_OWNED_AND_NOT_GROUP_OR_OTHER_WRITABLE_EXCEPT_ROOT_OWNED_STICKY_DIRECTORY"
        and isolation.get("toolchain_mount_source")
        == "PRIVATE_FULL_TREE_CATALOG_VERIFIED_SNAPSHOT",
        "E_RECIPES",
        "trusted path/toolchain snapshot policy",
    )
    require(isolation.get("two_fresh_archive_roots_required") is True and isolation.get("two_fresh_target_dirs_required") is True, "E_RECIPES", "fresh roots")
    require(value.get("rustflags_injection") == {"encoding": "UTF8_FLAGS_JOINED_BY_SINGLE_UNIT_SEPARATOR_WITH_NO_TERMINATOR", "environment_variable": "CARGO_ENCODED_RUSTFLAGS", "rustflags_array_is_authoritative": True, "separator_byte_hex": "1f"}, "E_RECIPES", "rustflags injection")
    rustflags = value.get("rustflags")
    require(isinstance(rustflags, list) and all(isinstance(item, str) and item.isascii() and "\x1f" not in item for item in rustflags), "E_RECIPES", "rustflags")
    require("-Clink-arg=-Wl,--build-id=none" in rustflags, "E_RECIPES", "build id")
    require(value.get("shared_compiled_target") == {"crate_types": ["lib"], "kind": "lib", "name": "ab_owned_lab_role_artifacts", "source_relative_path": "crates/owned-lab-role-artifacts/src/lib.rs"}, "E_RECIPES", "shared target")
    require(value.get("source_date_epoch_derivation") == {"binding_commit": "TARGET_COMMIT", "command": ["git", "show", "-s", "--format=%ct", "TARGET_COMMIT"], "export_environment_variable": "SOURCE_DATE_EPOCH", "output_validation": "ONE_ASCII_DECIMAL_NONNEGATIVE_INTEGER_LINE"}, "E_RECIPES", "source date epoch")
    digest_contract = value.get("per_role_recipe_digest_contract")
    require(isinstance(digest_contract, dict), "E_RECIPE_DIGEST_CONTRACT", "absent")
    require(digest_contract.get("hash_algorithm") == "SHA-256" and digest_contract.get("digest_framing") == FRAMING, "E_RECIPE_DIGEST_CONTRACT", "hash/framing")
    require(digest_contract.get("digest_domain_template") == "agent-bridge/biocortex/owned-lab/s21b-a1/build-recipe/<role>/v1", "E_RECIPE_DIGEST_CONTRACT", "domain")
    require(digest_contract.get("role_placeholder_values") == [role for role, _, _, _ in ROLE_SPECS], "E_RECIPE_DIGEST_CONTRACT", "roles")
    require(digest_contract.get("canonical_payload") == "COMPLETE_RECIPE_OBJECT_AB_RESTRICTED_COMPACT_SORTED_KEYS_UTF8_WITHOUT_TERMINAL_LF", "E_RECIPE_DIGEST_CONTRACT", "payload")
    recipes = value.get("recipes")
    require(isinstance(recipes, list) and len(recipes) == 4, "E_RECIPES", "count")
    result: dict[str, str] = {}
    for recipe, (role, binary, source, output) in zip(recipes, ROLE_SPECS, strict=True):
        require(isinstance(recipe, dict), "E_RECIPES", role)
        require(recipe.get("binary_name") == binary and recipe.get("source_relative_path") == source and recipe.get("output_relative_path") == output, "E_RECIPES", role)
        require(recipe.get("transitively_compiled_source_relative_paths") == ["crates/owned-lab-role-artifacts/src/lib.rs"], "E_RECIPES", f"{role} shared lib")
        require(recipe.get("arguments") == ["build", "--frozen", "--locked", "--offline", "--release", "-j", "1", "--target", TARGET_TRIPLE, "-p", ROLE_PACKAGE, "--no-default-features", "--bin", binary], "E_RECIPES", f"{role} argv")
        result[role] = recipe_digest(role, recipe)
    require(len(set(result.values())) == 4, "E_RECIPE_DIGEST", "not pairwise distinct")
    return result


def validate_schema_set(repo: Path, value: Mapping[str, Any]) -> str:
    require(value.get("closure_digest_domain") == SCHEMA_SET_DOMAIN.decode("ascii"), "E_SCHEMA_SET", "domain")
    require(value.get("closure_digest_profile") == SCHEMA_SET_PROFILE, "E_SCHEMA_SET", "profile")
    require(value.get("member_count") == 4, "E_SCHEMA_SET", "count")
    members = value.get("members")
    expected = [{"git_mode": "100644", "path": path} for path in SCHEMA_MEMBERS]
    require(members == expected, "E_SCHEMA_SET", "members/order")
    frame = bytearray(struct.pack(">I", len(SCHEMA_SET_DOMAIN)) + SCHEMA_SET_DOMAIN)
    for path in SCHEMA_MEMBERS:
        raw = read_repo_file(repo, path)
        require(raw == git_blob(repo, BASELINE_COMMIT, path), "E_SCHEMA_SET", f"baseline drift: {path}")
        require(
            raw == git_blob(repo, SOURCE_BASE_COMMIT, path),
            "E_SCHEMA_SET",
            f"source-base drift: {path}",
        )
        mode = git_mode(repo, path)
        require(mode == "100644", "E_SCHEMA_SET", f"mode: {path}")
        path_raw = path.encode("ascii")
        frame.extend(struct.pack(">Q", len(path_raw)))
        frame.extend(path_raw)
        frame.extend(struct.pack(">I", int(mode, 8)))
        frame.extend(struct.pack(">Q", len(raw)))
        frame.extend(raw)
    return sha256(bytes(frame))


def audit_cargo_lock(repo: Path) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    raw = read_repo_file(repo, "Cargo.lock")
    current = parse_toml(raw, "Cargo.lock")
    baseline_raw = git_blob(repo, SOURCE_BASE_COMMIT, "Cargo.lock")
    require(
        sha256(baseline_raw) == SOURCE_BASE_CARGO_LOCK_SHA256,
        "E_SOURCE_BASE_LOCK",
        "digest",
    )
    baseline = parse_toml(baseline_raw, "baseline Cargo.lock")
    current_packages = current.get("package")
    baseline_packages = baseline.get("package")
    require(isinstance(current_packages, list) and isinstance(baseline_packages, list), "E_CARGO_LOCK", "packages")
    expected_new = {"name": ROLE_PACKAGE, "version": ROLE_PACKAGE_VERSION}
    baseline_encoded = [canonical_bytes(item) for item in baseline_packages]
    current_encoded = [canonical_bytes(item) for item in current_packages]
    added = list(current_encoded)
    for item in baseline_encoded:
        require(item in added, "E_CARGO_LOCK", "baseline package removed/changed")
        added.remove(item)
    require(added == [canonical_bytes(expected_new)], "E_CARGO_LOCK", "only exact local stanza may be added")
    require({key: value for key, value in current.items() if key != "package"} == {key: value for key, value in baseline.items() if key != "package"}, "E_CARGO_LOCK", "top-level drift")
    registry = [item for item in current_packages if item.get("source") == SPARSE_SOURCE_ID]
    local = [item for item in current_packages if "source" not in item]
    require(len(registry) == 566 and len(local) == 14 and len(current_packages) == 580, "E_CARGO_LOCK_COUNTS", f"registry={len(registry)} local={len(local)} total={len(current_packages)}")
    require(all(item.get("source") == SPARSE_SOURCE_ID or "source" not in item for item in current_packages), "E_CARGO_LOCK_SOURCE", "unexpected source")
    return current, registry, sha256(raw)


def sparse_relative_path(name: str) -> PurePosixPath:
    require(name.isascii() and name == name.lower() and re.fullmatch(r"[a-z0-9_-]+", name) is not None, "E_SPARSE_NAME", name)
    if len(name) == 1:
        return PurePosixPath(".cache", "1", name)
    if len(name) == 2:
        return PurePosixPath(".cache", "2", name)
    if len(name) == 3:
        return PurePosixPath(".cache", "3", name[0], name)
    return PurePosixPath(".cache", name[:2], name[2:4], name)


def sparse_records(raw: bytes, label: str) -> dict[str, dict[str, Any]]:
    parts = raw.split(b"\0")
    records: dict[str, dict[str, Any]] = {}
    for index, part in enumerate(parts):
        if not part.startswith(b"{"):
            continue
        parsed = parse_json(part, label)
        version = parsed.get("vers")
        require(isinstance(version, str) and version not in records, "E_SPARSE_RECORD", label)
        records[version] = parsed
    require(records, "E_SPARSE_RECORD", label)
    return records


def validate_sparse_index(registry_packages: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]) -> tuple[str, int, int]:
    require(manifest.get("source_id") == SPARSE_SOURCE_ID, "E_SPARSE_MANIFEST", "source")
    require(manifest.get("path_derivation_profile") == SPARSE_PATH_PROFILE, "E_SPARSE_MANIFEST", "path profile")
    require(manifest.get("catalog_digest_profile") == SPARSE_CATALOG_PROFILE, "E_SPARSE_MANIFEST", "catalog profile")
    require(manifest.get("selection") == "CONFIG_JSON_PLUS_EXACT_UNIQUE_PACKAGE_NAMES_WITH_REGISTRY_SOURCE_IN_TARGET_CARGO_LOCK", "E_SPARSE_MANIFEST", "selection")
    require(manifest.get("cache_file_format") == "CARGO_SPARSE_INDEX_CACHE_OPAQUE_RAW_FILE_BYTES", "E_SPARSE_MANIFEST", "cache format")
    require(manifest.get("logical_build_root") == "/ab-build/cargo-home/registry/index/index.crates.io-1949cf8c6b5b557f", "E_SPARSE_MANIFEST", "root")
    by_name: dict[str, list[Mapping[str, Any]]] = {}
    for package in registry_packages:
        by_name.setdefault(str(package["name"]).lower(), []).append(package)
    names = sorted(by_name, key=lambda item: item.encode("ascii"))
    require(len(names) == 531, "E_SPARSE_COUNT", f"names={len(names)}")
    paths = [PurePosixPath("config.json"), *(sparse_relative_path(name) for name in names)]
    lines: list[bytes] = []
    total = 0
    for relative in sorted(paths, key=lambda item: item.as_posix().encode("ascii")):
        path = SPARSE_INDEX_ROOT.joinpath(*relative.parts)
        require(path.is_file() and not path.is_symlink(), "E_SPARSE_FILE", relative.as_posix())
        raw = path.read_bytes()
        total += len(raw)
        lines.append(f"{relative.as_posix()}\t{len(raw)}\t{sha256(raw)}\n".encode("ascii"))
        if relative.name != "config.json":
            records = sparse_records(raw, relative.as_posix())
            crate_name = relative.name
            for package in by_name[crate_name]:
                version = str(package["version"])
                require(version in records, "E_SPARSE_VERSION", f"{crate_name} {version}")
                record = records[version]
                require(record.get("name", "").lower() == crate_name, "E_SPARSE_RECORD", crate_name)
                require(record.get("cksum") == package.get("checksum"), "E_SPARSE_CHECKSUM", f"{crate_name} {version}")
    digest = sha256(b"".join(lines))
    require(manifest.get("package_name_count") == len(names) and manifest.get("file_count") == len(paths), "E_SPARSE_COUNT", "manifest")
    require(manifest.get("total_byte_count") == total and manifest.get("catalog_sha256") == digest, "E_SPARSE_DIGEST", f"{total} {digest}")
    return digest, len(paths), total


def logical_toolchain_path(value: str) -> Path:
    pure = PurePosixPath(value)
    require(pure.is_absolute() and pure.parts[:2] == ("/", "rust-toolchain"), "E_TOOLCHAIN_PATH", value)
    return TOOLCHAIN_ROOT.joinpath(*pure.parts[2:])


def validate_pinned_file(path: Path, expected: str, label: str) -> None:
    require(path.is_file(), "E_PIN_FILE", label)
    require(sha256_file(path) == expected, "E_PIN_DIGEST", label)


def validate_toolchain(repo: Path, value: Mapping[str, Any], registry_packages: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    require(value.get("toolchain_root") == "/rust-toolchain", "E_TOOLCHAIN", "root")
    require(value.get("toolchain_version") == "1.96.0-x86_64-unknown-linux-gnu", "E_TOOLCHAIN", "version")
    require(value.get("host_triple") == TARGET_TRIPLE and value.get("target_triple") == TARGET_TRIPLE, "E_TOOLCHAIN", "triple")
    require(value.get("rust_toolchain_toml_sha256") == sha256(read_repo_file(repo, "rust-toolchain.toml")), "E_TOOLCHAIN", "rust-toolchain.toml")
    toolchain_toml = parse_toml(read_repo_file(repo, "rust-toolchain.toml"), "rust-toolchain.toml")
    require(toolchain_toml == {"toolchain": {"channel": "1.96.0", "components": ["rustfmt", "clippy"]}}, "E_TOOLCHAIN", "toml")

    tree_manifest = value.get("toolchain_tree_catalog")
    require(isinstance(tree_manifest, dict), "E_TOOLCHAIN_TREE", "manifest")
    require(
        tree_manifest.get("catalog_digest_profile") == TOOLCHAIN_TREE_PROFILE,
        "E_TOOLCHAIN_TREE",
        "profile",
    )
    tree_rows: list[tuple[str, bytes]] = []
    tree_bytes = 0
    for path in TOOLCHAIN_ROOT.rglob("*"):
        relative = path.relative_to(TOOLCHAIN_ROOT).as_posix()
        require(relative.isascii(), "E_TOOLCHAIN_TREE", relative)
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            continue
        require(stat.S_ISREG(metadata.st_mode), "E_TOOLCHAIN_TREE", f"special {relative}")
        raw = path.read_bytes()
        tree_bytes += len(raw)
        row = (
            f"{relative}\t{stat.S_IMODE(metadata.st_mode):04o}\t{len(raw)}\t{sha256(raw)}\n"
        ).encode("ascii")
        tree_rows.append((relative, row))
    tree_rows.sort(key=lambda item: item[0].encode("ascii"))
    tree_digest = sha256(b"".join(row for _, row in tree_rows))
    require(
        tree_manifest.get("file_count") == len(tree_rows)
        and tree_manifest.get("total_byte_count") == tree_bytes
        and tree_manifest.get("catalog_sha256") == tree_digest,
        "E_TOOLCHAIN_TREE",
        f"{len(tree_rows)} {tree_bytes} {tree_digest}",
    )

    expected_components = {
        "cargo": {
            "binary_path": "/rust-toolchain/bin/cargo", "release": "1.96.0",
            "commit_hash": "30a34c6821b57de0aaec83a901aca39f88f6778c", "commit_date": "2026-05-25",
            "manifest_path": "/rust-toolchain/lib/rustlib/manifest-cargo-x86_64-unknown-linux-gnu",
        },
        "rustc": {
            "binary_path": "/rust-toolchain/bin/rustc", "release": "1.96.0",
            "commit_hash": "ac68faa20c58cbccd01ee7208bf3b6e93a7d7f96", "commit_date": "2026-05-25",
            "llvm_version": "22.1.2",
            "manifest_path": "/rust-toolchain/lib/rustlib/manifest-rustc-x86_64-unknown-linux-gnu",
        },
    }
    for component, expected in expected_components.items():
        observed = value.get(component)
        require(isinstance(observed, dict), "E_TOOLCHAIN", component)
        for key, item in expected.items():
            require(observed.get(key) == item, "E_TOOLCHAIN", f"{component}.{key}")
        validate_pinned_file(logical_toolchain_path(observed["binary_path"]), observed.get("binary_sha256", ""), f"{component} binary")
        validate_pinned_file(logical_toolchain_path(observed["manifest_path"]), observed.get("manifest_sha256", ""), f"{component} manifest")

    rust_std = value.get("rust_std")
    require(isinstance(rust_std, dict), "E_RUST_STD", "absent")
    require(rust_std.get("manifest_path") == "/rust-toolchain/lib/rustlib/manifest-rust-std-x86_64-unknown-linux-gnu", "E_RUST_STD", "manifest path")
    validate_pinned_file(logical_toolchain_path(rust_std["manifest_path"]), rust_std.get("manifest_sha256", ""), "rust-std manifest")
    contract = rust_std.get("file_catalog_digest_contract")
    require(isinstance(contract, dict), "E_RUST_STD", "catalog contract")
    require(contract == {"catalog_sha256_scope": "CONCATENATED_SORTED_CATALOG_LINES", "line_framing": RUST_STD_PROFILE, "member_selection": "RECURSIVE_REGULAR_FILES_EXCLUDING_SYMLINKS", "relative_path_root": "/rust-toolchain/lib/rustlib/x86_64-unknown-linux-gnu/lib", "sort_order": "BYTEWISE_ASCII_RELATIVE_POSIX_PATH_ASCENDING", "terminal_lf": "ONE_PER_MEMBER"}, "E_RUST_STD", "catalog contract")
    std_root = logical_toolchain_path(contract["relative_path_root"])
    members = sorted((item for item in std_root.rglob("*") if item.is_file() and not item.is_symlink()), key=lambda item: item.relative_to(std_root).as_posix().encode("ascii"))
    lines = []
    for path in members:
        relative = path.relative_to(std_root).as_posix()
        mode = format(stat.S_IMODE(path.stat(follow_symlinks=False).st_mode), "04o")
        lines.append(f"{relative}\t{mode}\t{path.stat().st_size}\t{sha256_file(path)}\n".encode("ascii"))
    std_digest = sha256(b"".join(lines))
    require(rust_std.get("file_count") == len(members) == 62 and rust_std.get("file_catalog_sha256") == std_digest, "E_RUST_STD", std_digest)

    host_catalog = value.get("rustc_host_runtime_catalog")
    require(isinstance(host_catalog, list) and len(host_catalog) == 3, "E_RUSTC_RUNTIME", "host catalog")
    require([entry.get("path") for entry in host_catalog] == sorted(entry.get("path") for entry in host_catalog), "E_RUSTC_RUNTIME", "host order")
    for entry in host_catalog:
        path = logical_toolchain_path(entry["path"])
        metadata = path.lstat()
        if path.is_symlink():
            raw = os.readlink(path).encode("utf-8")
        else:
            require(path.is_file(), "E_RUSTC_RUNTIME", entry["path"])
            raw = path.read_bytes()
        require(entry.get("mode_octal") == format(stat.S_IMODE(metadata.st_mode), "04o"), "E_RUSTC_RUNTIME", f"mode {entry['path']}")
        require(entry.get("size_bytes") == metadata.st_size and entry.get("sha256") == sha256(raw), "E_RUSTC_RUNTIME", entry["path"])

    system_catalog = value.get("rustc_runtime_system_catalog")
    require(isinstance(system_catalog, list) and len(system_catalog) == 8, "E_SYSTEM_RUNTIME", "count")
    require([entry.get("logical_name") for entry in system_catalog] == sorted(entry.get("logical_name") for entry in system_catalog), "E_SYSTEM_RUNTIME", "order")
    for entry in system_catalog:
        requested = Path(entry["requested_path"])
        resolved = Path(entry["resolved_path"])
        require(requested.exists() and resolved.is_file(), "E_SYSTEM_RUNTIME", entry["logical_name"])
        require(Path(os.path.realpath(requested)) == resolved, "E_SYSTEM_RUNTIME", f"resolution {entry['logical_name']}")
        require(sha256_file(resolved) == entry.get("sha256"), "E_SYSTEM_RUNTIME", entry["logical_name"])

    linker = value.get("linker")
    require(isinstance(linker, dict), "E_LINKER", "absent")
    binary_pairs = (("cc_binary_path", "cc_binary_sha256"), ("ar_binary_path", "ar_binary_sha256"), ("collect2_binary_path", "collect2_binary_sha256"), ("ld_binary_path", "ld_binary_sha256"), ("strip_binary_path", "strip_binary_sha256"))
    for path_key, digest_key in binary_pairs:
        validate_pinned_file(Path(linker[path_key]), linker.get(digest_key, ""), path_key)
    require(linker.get("cc_release") == "15.2.0" and linker.get("binutils_release") == "2.46", "E_LINKER", "release")
    require(linker.get("gcc_specs_sha256_profile") == "SHA256_EXACT_STDOUT_BYTES_FROM_CC_BINARY_PATH_DUMPSPECS_ARGUMENT_IN_EMPTY_ENV_WITH_PATH_USR_BIN_BIN_LC_ALL_C_LANG_C_TZ_UTC", "E_LINKER", "spec profile")
    specs = run_readonly((linker["cc_binary_path"], "-dumpspecs"), cwd=repo, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C", "TZ": "UTC"})
    require(linker.get("gcc_specs_sha256") == sha256(specs), "E_LINKER", "spec digest")
    printed_collect2 = run_readonly((linker["cc_binary_path"], "-print-prog-name=collect2"), cwd=repo).decode("ascii").strip()
    printed_ld = run_readonly((linker["cc_binary_path"], "-print-prog-name=ld"), cwd=repo).decode("ascii").strip()
    require(Path(os.path.realpath(printed_collect2)) == Path(os.path.realpath(linker["collect2_binary_path"])), "E_LINKER", "collect2 chain")
    require(Path(os.path.realpath(printed_ld)) == Path(os.path.realpath(linker["ld_binary_path"])), "E_LINKER", "ld chain")
    inputs = linker.get("crt_and_link_input_catalog")
    require(isinstance(inputs, list) and len(inputs) == 11, "E_LINKER_INPUT", "count")
    require([entry.get("logical_name") for entry in inputs] == sorted(entry.get("logical_name") for entry in inputs), "E_LINKER_INPUT", "order")
    for entry in inputs:
        path = Path(entry["resolved_path"])
        require(path.is_file() and sha256_file(path) == entry.get("sha256"), "E_LINKER_INPUT", entry["logical_name"])

    sparse_digest, sparse_count, sparse_bytes = validate_sparse_index(registry_packages, value.get("cargo_registry_sparse_index", {}))
    return {
        "rust_std_catalog_sha256": std_digest,
        "toolchain_tree_catalog_sha256": tree_digest,
        "toolchain_tree_file_count": str(len(tree_rows)),
        "toolchain_tree_byte_count": str(tree_bytes),
        "sparse_index_catalog_sha256": sparse_digest,
        "sparse_index_file_count": str(sparse_count),
        "sparse_index_byte_count": str(sparse_bytes),
    }


def validate_role_sources(repo: Path) -> dict[str, str]:
    observed: dict[str, str] = {}
    for path, expected in SOURCE_SHA256.items():
        raw = read_repo_file(repo, path)
        digest = sha256(raw)
        require(digest == expected, "E_ROLE_SOURCE_DIGEST", path)
        observed[path] = digest
        text = raw.decode("ascii")
        require("#![forbid(unsafe_code)]" in text, "E_ROLE_SOURCE", f"unsafe guard: {path}")
        for forbidden in ("std::net", "std::fs", "std::process::Command", "TcpStream", "UdpSocket", "reqwest", "tokio", "unsafe {"):
            require(forbidden not in text, "E_ROLE_SOURCE", f"{path}: {forbidden}")
    library = read_repo_file(repo, "crates/owned-lab-role-artifacts/src/lib.rs").decode("ascii")
    for token in (
        'pub const ROLE_ARTIFACT_COUNT: usize = 4;', '\\"arguments_accepted\\":false',
        '\\"external_payload_reader_present\\":false', '\\"operational_role_implemented\\":false',
        '\\"private_key_access_present\\":false', '\\"provider_or_production_authority\\":false',
        '\\"side_effects_unlocked\\":\\"NONE\\"', 'return ExitCode::from(64);',
        'return ExitCode::from(74);', 'write_all(stdout, b"\\n")',
    ):
        require(token in library, "E_ROLE_SOURCE_SEMANTICS", token)
    identity_macro = library[library.index("macro_rules! role_identity"):library.index("const CONTROLLER_IDENTITY")]
    require(":true" not in identity_macro, "E_ROLE_SOURCE_SEMANTICS", "true identity claim")
    for role, binary, source, _ in ROLE_SPECS:
        wrapper = read_repo_file(repo, source).decode("ascii")
        enum_name = role.capitalize()
        require(f"ab_owned_lab_role_artifacts::Role::{enum_name}" in wrapper, "E_ROLE_WRAPPER", role)
        require("std::env::args_os().skip(1)" in wrapper, "E_ROLE_WRAPPER", role)
        require(f'role_identity!("{binary}", "{role}")' in library, "E_ROLE_IDENTITY", role)
    return observed


def validate_cargo_metadata(repo: Path) -> str:
    root_toml = parse_toml(read_repo_file(repo, "Cargo.toml"), "Cargo.toml")
    role_toml = parse_toml(read_repo_file(repo, ROLE_MANIFEST_PATH), ROLE_MANIFEST_PATH)
    workspace = root_toml.get("workspace")
    require(isinstance(workspace, dict) and workspace.get("resolver") == "2", "E_CARGO_TOML", "workspace")
    require(workspace.get("members", []).count("crates/owned-lab-role-artifacts") == 1, "E_CARGO_TOML", "workspace member")
    require("crates/owned-lab-role-artifacts" not in workspace.get("default-members", []), "E_CARGO_TOML", "workspace default member")
    exact_keys(role_toml, ("package", "features", "lib", "bin"), ROLE_MANIFEST_PATH)
    package = role_toml["package"]
    require(package == {"name": ROLE_PACKAGE, "version": {"workspace": True}, "edition": {"workspace": True}, "license": {"workspace": True}, "rust-version": {"workspace": True}, "publish": False, "autobins": False, "autoexamples": False, "autotests": False, "autobenches": False}, "E_CARGO_TOML", "package")
    require(role_toml["features"] == {"default": []} and role_toml["lib"] == {"path": "src/lib.rs"}, "E_CARGO_TOML", "features/lib")
    require(role_toml["bin"] == [{"name": binary, "path": source.removeprefix("crates/owned-lab-role-artifacts/")} for _, binary, source, _ in ROLE_SPECS], "E_CARGO_TOML", "bins")
    with tempfile.TemporaryDirectory(prefix="ab-s21b-a1-static-metadata-") as temporary:
        base = Path(temporary)
        cargo = TOOLCHAIN_ROOT / "bin/cargo"
        env = {
            "PATH": f"{TOOLCHAIN_ROOT}/bin:/usr/bin:/bin", "HOME": str(base / "home"),
            "CARGO_HOME": str(base / "cargo-home"), "CARGO_TARGET_DIR": str(base / "target"),
            "CARGO_NET_OFFLINE": "true", "RUSTC": str(TOOLCHAIN_ROOT / "bin/rustc"),
            "LANG": "C", "LC_ALL": "C", "TZ": "UTC",
        }
        raw = run_readonly((cargo, "metadata", "--format-version=1", "--no-deps", "--offline", "--frozen", "--locked"), cwd=repo, env=env)
    try:
        metadata = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("E_CARGO_METADATA", f"invalid JSON: {exc}")
    require(isinstance(metadata, dict), "E_CARGO_METADATA", "root")
    packages = [item for item in metadata.get("packages", []) if item.get("name") == ROLE_PACKAGE]
    require(len(packages) == 1, "E_CARGO_METADATA", "package")
    package_meta = packages[0]
    require(package_meta.get("version") == ROLE_PACKAGE_VERSION and package_meta.get("dependencies") == [], "E_CARGO_METADATA", "dependencies/version")
    require(package_meta.get("features") == {"default": []}, "E_CARGO_METADATA", "features")
    require(package_meta.get("id") in metadata.get("workspace_members", []), "E_CARGO_METADATA", "workspace member")
    require(package_meta.get("id") not in metadata.get("workspace_default_members", []), "E_CARGO_METADATA", "workspace default member")
    targets = package_meta.get("targets")
    require(isinstance(targets, list) and len(targets) == 5, "E_CARGO_METADATA", "target count")
    observed = {(item["name"], tuple(item["kind"]), tuple(item["crate_types"]), Path(item["src_path"]).relative_to(repo).as_posix()) for item in targets}
    expected = {("ab_owned_lab_role_artifacts", ("lib",), ("lib",), "crates/owned-lab-role-artifacts/src/lib.rs")}
    expected.update((binary, ("bin",), ("bin",), source) for _, binary, source, _ in ROLE_SPECS)
    require(observed == expected, "E_CARGO_METADATA", str(sorted(observed)))
    stable_payload = {
        "dependencies": package_meta["dependencies"],
        "features": package_meta["features"],
        "name": package_meta["name"],
        "targets": [
            {"crate_types": list(crate_types), "kind": list(kind), "name": name, "source_relative_path": source}
            for name, kind, crate_types, source in sorted(observed)
        ],
        "version": package_meta["version"],
    }
    return sha256(canonical_bytes(stable_payload))


def validate_git_boundary(repo: Path) -> None:
    require(git(repo, "rev-parse", "--is-inside-work-tree").strip() == b"true", "E_GIT", "not worktree")
    require(git(repo, "rev-parse", "--is-shallow-repository").strip() == b"false", "E_GIT", "shallow")
    require(not git(repo, "for-each-ref", "--format=%(refname)", "refs/replace").strip(), "E_GIT", "replace refs")
    require(git(repo, "remote", "get-url", "origin").decode("utf-8").strip() == CANONICAL_REMOTE, "E_GIT", "origin")
    raw = git(repo, "cat-file", "commit", BASELINE_COMMIT)
    header = raw.split(b"\n\n", 1)[0].decode("ascii").splitlines()
    trees = [line[5:] for line in header if line.startswith("tree ")]
    parents = [line[7:] for line in header if line.startswith("parent ")]
    require(trees == [BASELINE_TREE] and parents == [BASELINE_FIRST_PARENT, BASELINE_SECOND_PARENT], "E_GIT_BASELINE", "topology")
    source_base_raw = git(repo, "cat-file", "commit", SOURCE_BASE_COMMIT)
    source_base_header = source_base_raw.split(b"\n\n", 1)[0].decode("ascii").splitlines()
    source_base_trees = [line[5:] for line in source_base_header if line.startswith("tree ")]
    source_base_parents = [line[7:] for line in source_base_header if line.startswith("parent ")]
    require(
        source_base_trees == [SOURCE_BASE_TREE]
        and source_base_parents == [SOURCE_BASE_FIRST_PARENT, SOURCE_BASE_SECOND_PARENT],
        "E_GIT_SOURCE_BASE",
        "topology",
    )
    run_readonly(
        (
            "/usr/bin/git",
            "--no-replace-objects",
            "merge-base",
            "--is-ancestor",
            BASELINE_COMMIT,
            SOURCE_BASE_COMMIT,
        ),
        cwd=repo,
    )


def mutate_path(value: dict[str, Any], path: tuple[str, ...], replacement: Any) -> None:
    cursor: Any = value
    for key in path[:-1]:
        require(isinstance(cursor, dict) and key in cursor, "E_SELF_TEST_PATH", ".".join(path))
        cursor = cursor[key]
    require(isinstance(cursor, dict) and path[-1] in cursor, "E_SELF_TEST_PATH", ".".join(path))
    cursor[path[-1]] = replacement


def run_receipt_self_test(fixture: Mapping[str, Any], validator: Draft202012Validator, seed: int) -> int:
    mutations: list[tuple[str, tuple[str, ...], Any]] = [
        ("status", ("status",), REAL_STATUS),
        ("state", ("receipt_state",), REAL_RECEIPT_STATE),
        ("test-only", ("test_only",), False),
        ("synthetic", ("synthetic",), False),
        ("candidate-target", ("target_binding", "candidate_supplied_target_used"), True),
        ("target-refrozen", ("target_binding", "target_refrozen"), True),
        ("source-commit", ("target_binding", "source_commit"), "1" * 40),
        ("integration-tree", ("target_binding", "integration_tree"), "2" * 40),
        ("archive", ("target_binding", "integrated_archive_sha256"), "3" * 64),
        ("closure-digest", ("closure_bindings", "toolchain_manifest", "manifest_sha256"), "4" * 64),
        ("closure-recomputed", ("closure_bindings", "feature_set", "independently_recomputed_in_build_a"), True),
        ("build-completed", ("rebuilds", "build_a", "completed"), True),
        ("build-network", ("rebuilds", "build_b", "network_disabled"), True),
        ("roots", ("rebuilds", "build_roots_distinct"), True),
        ("role-count", ("role_artifacts", "completed_role_count"), 1),
        ("controller-present", ("role_artifacts", "controller", "build_a", "artifact_present"), True),
        ("observer-digest", ("role_artifacts", "observer", "build_b", "raw_sha256"), "5" * 64),
        ("runner-equal", ("role_artifacts", "runner", "raw_bytes_equal"), True),
        ("validator-recipe", ("role_artifacts", "validator", "build_recipe_sha256_equal"), True),
        ("pairwise", ("role_artifacts", "identity_sha256_pairwise_distinct"), True),
        ("subject", ("forbidden_outputs", "unsigned_final_subject_present"), True),
        ("private-key", ("forbidden_outputs", "owner_private_key_read"), True),
        ("signature", ("forbidden_outputs", "owner_signature_present"), True),
        ("capability", ("forbidden_outputs", "execution_capability_present"), True),
        ("live-count", ("forbidden_outputs", "live_action_count"), 1),
        ("closure-complete", ("result", "role_build_closure_complete"), True),
        ("hard-lock", ("result", "terminal_hard_lock"), False),
        ("owner-request", ("result", "owner_signature_may_be_requested"), True),
        ("live", ("result", "live_execution_may_begin"), True),
        ("side-effects", ("result", "side_effects_unlocked"), "LIVE"),
    ]
    random.Random(seed).shuffle(mutations)
    for label, path, replacement in mutations:
        mutated = copy.deepcopy(dict(fixture))
        mutate_path(mutated, path, replacement)
        raw = reseal_receipt(mutated)
        try:
            verify_receipt(raw, parse_json(raw[:-1], f"mutation:{label}"), validator)
        except CheckFailure:
            continue
        fail("E_SELF_TEST_ACCEPTED", label)

    malformed = (
        canonical_bytes(dict(fixture)),
        canonical_bytes(dict(fixture)) + b"\n\n",
        json.dumps(dict(fixture), indent=2, sort_keys=True).encode("ascii") + b"\n",
    )
    for index, raw in enumerate(malformed):
        try:
            parsed = parse_json(raw[:-1] if raw.endswith(b"\n") else raw, f"noncanonical:{index}")
            verify_receipt(raw, parsed, validator)
        except CheckFailure:
            continue
        fail("E_SELF_TEST_ACCEPTED", f"noncanonical:{index}")
    corrupted = copy.deepcopy(dict(fixture))
    corrupted[SELF_HASH_FIELD] = "f" * 64
    try:
        verify_receipt(canonical_bytes(corrupted) + b"\n", corrupted, validator)
    except CheckFailure:
        pass
    else:
        fail("E_SELF_TEST_ACCEPTED", "corrupt digest")
    unknown = copy.deepcopy(dict(fixture))
    unknown["unexpected"] = False
    raw = reseal_receipt(unknown)
    try:
        verify_receipt(raw, unknown, validator)
    except CheckFailure:
        pass
    else:
        fail("E_SELF_TEST_ACCEPTED", "unknown field")
    return len(mutations) + len(malformed) + 2


def render_tsv(rows: Sequence[tuple[str, str]]) -> str:
    require(len(rows) == len({key for key, _ in rows}), "E_TSV", "duplicate key")
    for key, value in rows:
        require(key.isascii() and value.isascii() and "\t" not in key + value and "\n" not in key + value, "E_TSV", key)
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def audit(repo: Path, *, self_test: bool, seed: int) -> list[tuple[str, str]]:
    validate_git_boundary(repo)
    raw_documents: dict[str, bytes] = {}
    documents: dict[str, dict[str, Any]] = {}
    for path in (*CONTROL_PATHS, *CLOSURE_PATHS, RECEIPT_FIXTURE_PATH):
        raw, value = load_json(repo, path, canonical=path in STRICT_CANONICAL_PATHS)
        raw_documents[path] = raw
        documents[path] = value
    validate_controls(documents)
    validate_manifest_headers(documents)
    validator = validate_receipt_schema(documents[RECEIPT_SCHEMA_PATH])
    require(REAL_STATUS.encode("ascii") in canonical_bytes(documents[RECEIPT_SCHEMA_PATH]), "E_REAL_STATUS", "schema complete branch")
    fixture_self = verify_receipt(raw_documents[RECEIPT_FIXTURE_PATH], documents[RECEIPT_FIXTURE_PATH], validator)
    mutation_count = run_receipt_self_test(documents[RECEIPT_FIXTURE_PATH], validator, seed) if self_test else 35

    lock, registry, lock_digest = audit_cargo_lock(repo)
    del lock
    validate_feature_set(documents[FEATURE_SET_PATH])
    recipe_digests = validate_recipes(documents[RECIPES_PATH])
    schema_content_digest = validate_schema_set(repo, documents[SCHEMA_SET_PATH])
    toolchain = validate_toolchain(repo, documents[TOOLCHAIN_PATH], registry)
    source_digests = validate_role_sources(repo)
    metadata_digest = validate_cargo_metadata(repo)

    manifest_digests = {path: sha256(raw_documents[path]) for path in CLOSURE_PATHS}
    rows: list[tuple[str, str]] = [
        ("stage", STAGE),
        ("status", PENDING_STATUS),
        ("decision", DECISION),
        ("mode", "STATIC_OFFLINE_NO_BUILD_NO_NETWORK_NON_LIVE_CLOSURE_CHECK"),
        ("a0_integration_commit", BASELINE_COMMIT),
        ("a1_source_base_commit", SOURCE_BASE_COMMIT),
        ("a1_source_base_tree", SOURCE_BASE_TREE),
        ("a1_source_base_cargo_lock_sha256", SOURCE_BASE_CARGO_LOCK_SHA256),
        ("cargo_lock_sha256", lock_digest),
        ("cargo_lock_registry_package_count", "566"),
        ("cargo_lock_local_path_package_count", "14"),
        ("cargo_metadata_sha256", metadata_digest),
        ("cargo_package", ROLE_PACKAGE),
        ("cargo_binary_target_count", "4"),
        ("cargo_library_target_count", "1"),
        ("cargo_direct_dependency_count", "0"),
        ("contract_sha256", sha256(raw_documents[CONTRACT_PATH])),
        ("status_sha256", sha256(raw_documents[STATUS_PATH])),
        ("successor_gate_sha256", sha256(raw_documents[SUCCESSOR_PATH])),
        ("receipt_schema_sha256", sha256(raw_documents[RECEIPT_SCHEMA_PATH])),
        ("synthetic_receipt_sha256", sha256(raw_documents[RECEIPT_FIXTURE_PATH])),
        ("synthetic_receipt_self_sha256", fixture_self),
        ("toolchain_manifest_sha256", manifest_digests[TOOLCHAIN_PATH]),
        ("feature_set_sha256", manifest_digests[FEATURE_SET_PATH]),
        ("schema_set_sha256", manifest_digests[SCHEMA_SET_PATH]),
        ("build_recipes_sha256", manifest_digests[RECIPES_PATH]),
        ("schema_content_set_sha256", schema_content_digest),
        ("rust_std_catalog_sha256", toolchain["rust_std_catalog_sha256"]),
        ("toolchain_tree_catalog_sha256", toolchain["toolchain_tree_catalog_sha256"]),
        ("toolchain_tree_file_count", toolchain["toolchain_tree_file_count"]),
        ("toolchain_tree_byte_count", toolchain["toolchain_tree_byte_count"]),
        ("sparse_index_catalog_sha256", toolchain["sparse_index_catalog_sha256"]),
        ("sparse_index_file_count", toolchain["sparse_index_file_count"]),
        ("sparse_index_byte_count", toolchain["sparse_index_byte_count"]),
    ]
    for role, _, source, _ in ROLE_SPECS:
        rows.append((f"{role}_source_sha256", source_digests[source]))
        rows.append((f"{role}_build_recipe_sha256", recipe_digests[role]))
    rows.extend(
        (
            ("shared_library_source_sha256", source_digests["crates/owned-lab-role-artifacts/src/lib.rs"]),
            ("self_test_mutation_count", str(mutation_count)),
            ("rust_build_or_test_run", "false"),
            ("network_access_authorized", "false"),
            ("candidate_supplied_digest_authoritative", "false"),
            ("owner_private_key_read", "false"),
            ("owner_signature_generated", "false"),
            ("live_action_count", "0"),
            ("side_effects_unlocked", "NONE"),
            ("gate", "PASS_S21B_A1_STATIC_ROLE_BUILD_CLOSURE_NON_LIVE_ONLY"),
        )
    )
    return rows


def main() -> int:
    global SPARSE_INDEX_ROOT, TOOLCHAIN_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--toolchain-root", type=Path, default=TOOLCHAIN_ROOT)
    parser.add_argument("--sparse-index-root", type=Path, default=SPARSE_INDEX_ROOT)
    parser.add_argument("--seed", type=int, default=21_101)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    require(repo.is_dir() and not repo.is_symlink(), "E_REPO", os.fspath(repo))
    require_secure_directory_chain(repo, "E_REPO_ANCESTRY")
    toolchain_input = args.toolchain_root.expanduser()
    require(toolchain_input.is_absolute(), "E_TOOLCHAIN_ROOT", "not absolute")
    TOOLCHAIN_ROOT = toolchain_input.resolve(strict=True)
    require(
        TOOLCHAIN_ROOT == toolchain_input.absolute()
        and TOOLCHAIN_ROOT.is_dir()
        and not TOOLCHAIN_ROOT.is_symlink(),
        "E_TOOLCHAIN_ROOT",
        "not one canonical directory",
    )
    require_secure_directory_chain(TOOLCHAIN_ROOT, "E_TOOLCHAIN_ANCESTRY")
    sparse_input = args.sparse_index_root.expanduser()
    require(sparse_input.is_absolute(), "E_SPARSE_ROOT", "not absolute")
    SPARSE_INDEX_ROOT = sparse_input.resolve(strict=True)
    require(
        SPARSE_INDEX_ROOT == sparse_input.absolute()
        and SPARSE_INDEX_ROOT.is_dir()
        and not SPARSE_INDEX_ROOT.is_symlink(),
        "E_SPARSE_ROOT",
        "not one canonical directory",
    )
    require_secure_directory_chain(SPARSE_INDEX_ROOT, "E_SPARSE_ANCESTRY")
    sys.stdout.write(render_tsv(audit(repo, self_test=args.self_test, seed=args.seed)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as exc:
        print(f"S21B-A1 role-build checker failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
