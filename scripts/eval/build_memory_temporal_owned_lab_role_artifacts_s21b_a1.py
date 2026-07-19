#!/usr/bin/env python3
"""Build and attest the four S21B-A1 non-live role artifacts.

This program intentionally accepts no candidate receipt and no expected digest.
It derives every observation from one immutable Git commit, independently
recreates two clean archives, builds them in separate offline sandboxes, and
emits one external canonical receipt.  It does not create a subject, signing
message, key, signature, admission packet, execution capability, or live action.

The caller is responsible for placing this process in the documented outer
3.5 GiB memory / 256 MiB swap cgroup.  The two builds themselves are serial and
use one Cargo job.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import fcntl
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import tomllib
from typing import Any, Iterable, Iterator, Mapping, NoReturn, Sequence


CANONICALIZATION = (
    "AB_RESTRICTED_CANONICAL_JSON_S21B_A1_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT"
)
STAGE = (
    "S21B_A1_DEFINE_AND_BUILD_FOUR_NAMED_NON_LIVE_ROLE_ARTIFACTS_"
    "AND_REPRODUCIBLE_CLOSURES"
)
STATUS = "S21B_A1_POST_INTEGRATION_ROLE_BUILD_CLOSURE_VERIFIED_NON_LIVE"
DECISION = (
    "S21B_A1_ADVANCE_ONLY_TO_SEPARATE_UNSIGNED_SUBJECT_CONTRACT_REBINDING_"
    "AND_GENERATION_REVIEW_NO_OWNER_SIGNING_REQUEST"
)
RECEIPT_SCHEMA = "agent_bridge.memory_temporal_owned_lab_role_build_receipt_s21b_a1.v0"
RECEIPT_PACKET_KIND = "S21B_A1_ROLE_BUILD_CLOSURE_RECEIPT"
RECEIPT_STATE = "POST_INTEGRATION_DOUBLE_REBUILD_VERIFIED_NON_LIVE"
RECEIPT_DOMAIN = b"agent-bridge/biocortex/owned-lab/s21b-a1/role-build-receipt/v1"
SCHEMA_CONTENT_PROFILE = (
    "U32BE_DOMAIN_LENGTH_DOMAIN_THEN_FOR_EACH_BYTEWISE_ASCII_PATH_SORTED_MEMBER_"
    "U64BE_PATH_LENGTH_PATH_ASCII_OCTAL_GIT_MODE_TO_U32_THEN_U32BE_"
    "U64BE_CONTENT_LENGTH_CONTENT"
)
MANIFEST_DIGEST_PROFILE = (
    "SHA256_EXACT_CANONICAL_REPOSITORY_FILE_BYTES_INCLUDING_ONE_TERMINAL_LF_"
    "NO_DOMAIN_NO_FRAMING_NO_SELF_FIELD"
)
RECIPE_DIGEST_PROFILE = (
    "SHA256_DOMAIN_SEPARATED_EXACT_MATCHING_RECIPES_ARRAY_OBJECT_AB_RESTRICTED_"
    "COMPACT_SORTED_KEYS_UTF8_WITHOUT_TERMINAL_LF"
)
RECIPE_DIGEST_FRAMING = (
    "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_CANONICAL_PAYLOAD_LENGTH_CANONICAL_PAYLOAD"
)
IDENTITY_DIGEST_PROFILE = (
    "SHA256_RAW_CANONICAL_IDENTITY_BYTES_EXCLUDING_SINGLE_TERMINAL_LF"
)
SPARSE_INDEX_SOURCE_ID = "registry+https://github.com/rust-lang/crates.io-index"
SPARSE_INDEX_CATALOG_PROFILE = (
    "FOR_EACH_BYTEWISE_ASCII_RELATIVE_PATH_SORTED_MEMBER_RELATIVE_POSIX_PATH_"
    "TAB_DECIMAL_BYTE_COUNT_TAB_64_LOWERCASE_HEX_SHA256_LF"
)
SPARSE_INDEX_PATH_PROFILE = (
    "CONFIG_AT_CONFIG_JSON;CRATE_NAME_LENGTH_1_AT_.cache/1/NAME;"
    "LENGTH_2_AT_.cache/2/NAME;LENGTH_3_AT_.cache/3/FIRST1/NAME;"
    "LENGTH_GE_4_AT_.cache/FIRST2/SECOND2/NAME"
)
PREDECESSOR_SPARSE_INDEX_CATALOG = {
    "catalog_sha256": "7044882c2233da1cda77c67a63cc9a333a5c70ef02ed2e804dd8b5783f1b426e",
    "file_count": 523,
    "total_byte_count": 33_739_989,
}
PREDECESSOR_REGISTRY_ARCHIVE_CATALOG = {
    "archive_count": 555,
    "total_byte_count": 85_385_269,
    "tuple_catalog_sha256": "4ca4d49308fbf6c2e5d6952feca4c7079e24e2be88fa1b1d5b9ee11278137ed8",
}
PREDECESSOR_CARGO_CACHE_TAG = (
    b"Signature: 8a477f597d28d172789f06886806bc55\n"
    b"# This file is a cache directory tag created by cargo.\n"
    b"# For information about cache directory tags see https://bford.info/cachedir/\n"
)
PREDECESSOR_RETIRED_SPARSE_INDEX_CLEANUP_MODE_PROFILE = (
    "POST_PAYLOAD_EXACT_TWO_INDEX_CATALOGS_REVALIDATED_"
    "DIRECTORIES_0555_TO_0700_FILES_REMAIN_0444"
)
PREDECESSOR_FROZEN_GATE_SCRATCH_CLEANUP_PROFILE = (
    "PINNED_REAL_GNURM_AND_DIGESTED_DISPATCHER_NONMATCHING_ARGV_PASSTHROUGH_"
    "EXACT_S15_S16_RF_TRAP_CANONICAL_SCRATCH_LANDLOCK_PARENT_COPIED_REGISTRY_"
    "REAL_DIRECTORIES_GAIN_OWNER_RWX_NO_SYMLINK_FOLLOW_FILES_UNCHANGED"
)
PREDECESSOR_BWRAP_FLATTEN_LAUNCHER = b'''#!/usr/bin/python3 -I
import runpy
import sys

namespace = runpy.run_path(
    "/opt/scripts/eval/build_memory_temporal_owned_lab_role_artifacts_s21b_a1.py",
    run_name="a1_predecessor_flatten_adapter",
)
namespace["run_predecessor_bwrap_flatten_adapter"](sys.argv[1:])
'''
PREDECESSOR_BWRAP_FLATTEN_LAUNCHER_SHA256 = (
    "22f0d16e7d0caae1642088a3b9736d21391e8fcc508edbabe8044f791fc85a83"
)
PREDECESSOR_GNURM_CLEANUP_LAUNCHER = b'''#!/usr/bin/python3 -I
import runpy
import sys

namespace = runpy.run_path(
    "/opt/scripts/eval/build_memory_temporal_owned_lab_role_artifacts_s21b_a1.py",
    run_name="a1_predecessor_gnurm_cleanup_adapter",
)
namespace["run_predecessor_gnurm_cleanup_adapter"](sys.argv[1:])
'''
PREDECESSOR_REAL_GNURM_SHA256 = (
    "175a15a35617f84bb86692b50a3e21b41d8e21fdea242e952b31f1e2e80b1a54"
)

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
SOURCE_BASE_CARGO_LOCK_SHA256 = (
    "452da4a2c2e4712251ad7a4076a3966222507eaf1695ff3d4ecab13084d732d2"
)
CANONICAL_REMOTE = "git@github.com:pallasting/Agent-Bridge.git"
REMOTE_REF = "refs/heads/master"
ARCHIVE_PROFILE = "git -c tar.umask=0022 archive --format=tar <commit>"
BASELINE_WORKSPACE_MEMBERS_TAIL = (
    b'    "crates/memory-columnar",\n'
    b'    "bin/agent-cli",\n'
    b']\n\nexclude = [\n'
)
A1_WORKSPACE_MEMBERS_TAIL = (
    b'    "crates/memory-columnar",\n'
    b'    "crates/owned-lab-role-artifacts",\n'
    b'    "bin/agent-cli",\n'
    b']\n\nexclude = [\n'
)

TOOLCHAIN_HOST_ROOT = pathlib.Path(
    "/home/pallasting/.rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu"
)
TRUSTED_CARGO_REGISTRY = pathlib.Path("/home/pallasting/.cargo/registry")
GIT = pathlib.Path("/usr/bin/git")
BWRAP = pathlib.Path("/usr/bin/bwrap")
READELF = pathlib.Path("/usr/bin/readelf")
STRINGS = pathlib.Path("/usr/bin/strings")

TOOLCHAIN_MANIFEST_REL = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-owned-lab-role-build-toolchain-manifest-s21b-a1-v0.json"
)
FEATURE_SET_REL = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-owned-lab-role-build-feature-set-s21b-a1-v0.json"
)
SCHEMA_SET_REL = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-owned-lab-role-build-schema-set-s21b-a1-v0.json"
)
RECIPES_REL = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-owned-lab-role-build-recipes-s21b-a1-v0.json"
)
RECEIPT_SCHEMA_REL = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-owned-lab-role-build-receipt-schema-s21b-a1-v0.json"
)
ROLE_PACKAGE_MANIFEST_REL = "crates/owned-lab-role-artifacts/Cargo.toml"

A1_PACKET_PATHS: dict[str, tuple[str, str]] = {
    "Cargo.lock": ("M", "100644"),
    "Cargo.toml": ("M", "100644"),
    "rust-toolchain.toml": ("M", "100644"),
    "scripts/verify-agent-bridge-release-truth-gate.sh": ("M", "100755"),
    "crates/owned-lab-role-artifacts/Cargo.toml": ("A", "100644"),
    "crates/owned-lab-role-artifacts/src/lib.rs": ("A", "100644"),
    "crates/owned-lab-role-artifacts/src/bin/controller.rs": ("A", "100644"),
    "crates/owned-lab-role-artifacts/src/bin/observer.rs": ("A", "100644"),
    "crates/owned-lab-role-artifacts/src/bin/runner.rs": ("A", "100644"),
    "crates/owned-lab-role-artifacts/src/bin/validator.rs": ("A", "100644"),
    "docs/design/MEMORY_TEMPORAL_OWNED_LAB_ROLE_BUILD_CLOSURE_S21B_A1_2026_07_18.md": ("A", "100644"),
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-contract-s21b-a1-v0.json": ("A", "100644"),
    FEATURE_SET_REL: ("A", "100644"),
    RECEIPT_SCHEMA_REL: ("A", "100644"),
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-receipt-synthetic-s21b-a1-v0.json": ("A", "100644"),
    RECIPES_REL: ("A", "100644"),
    SCHEMA_SET_REL: ("A", "100644"),
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-status-s21b-a1-v0.json": ("A", "100644"),
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-successor-gate-s21b-a1-v0.json": ("A", "100644"),
    TOOLCHAIN_MANIFEST_REL: ("A", "100644"),
    "docs/reports/goal-c-u/2026-07-18-biocortex-ab-track-b-owned-lab-role-build-closure-s21b-a1-prereg.md": ("A", "100644"),
    "scripts/eval/build_memory_temporal_owned_lab_role_artifacts_s21b_a1.py": ("A", "100755"),
    "scripts/eval/check_memory_temporal_owned_lab_role_build_s21b_a1.py": ("A", "100755"),
    "scripts/eval/fixtures/memory_temporal_owned_lab_role_build_s21b_a1.expected.v0.tsv": ("A", "100644"),
    "scripts/check-memory-temporal-owned-lab-role-build-s21b-a1.sh": ("A", "100755"),
}

MANIFEST_PATHS = {
    "toolchain_manifest": TOOLCHAIN_MANIFEST_REL,
    "feature_set": FEATURE_SET_REL,
    "schema_set": SCHEMA_SET_REL,
    "build_recipes": RECIPES_REL,
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

ROLE_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "controller",
        "ab-owned-lab-controller",
        "crates/owned-lab-role-artifacts/src/bin/controller.rs",
        "x86_64-unknown-linux-gnu/release/ab-owned-lab-controller",
    ),
    (
        "observer",
        "ab-owned-lab-observer",
        "crates/owned-lab-role-artifacts/src/bin/observer.rs",
        "x86_64-unknown-linux-gnu/release/ab-owned-lab-observer",
    ),
    (
        "runner",
        "ab-owned-lab-runner",
        "crates/owned-lab-role-artifacts/src/bin/runner.rs",
        "x86_64-unknown-linux-gnu/release/ab-owned-lab-runner",
    ),
    (
        "validator",
        "ab-owned-lab-validator",
        "crates/owned-lab-role-artifacts/src/bin/validator.rs",
        "x86_64-unknown-linux-gnu/release/ab-owned-lab-validator",
    ),
)

EXPECTED_SCHEMA_MEMBERS = (
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-external-input-admission-schema-s21a-v0.json",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-final-refreeze-subject-schema-s21a-v0.json",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-authorization-envelope-schema-s21a-v0.json",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-trust-anchor-schema-s21a-v0.json",
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MAX_U64 = (1 << 64) - 1


class BuildError(RuntimeError):
    """A fail-closed validation or build error."""


def fail(message: str) -> NoReturn:
    raise BuildError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def files_equal(left: pathlib.Path, right: pathlib.Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as a, right.open("rb") as b:
        while True:
            av = a.read(1024 * 1024)
            bv = b.read(1024 * 1024)
            if av != bv:
                return False
            if not av:
                return True


def validate_restricted_json(value: Any, context: str = "$") -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        require(0 <= value <= MAX_U64, f"{context}: integer is outside u64")
        return
    if isinstance(value, float):
        fail(f"{context}: floats are forbidden")
    if isinstance(value, str):
        require(value.isascii(), f"{context}: non-ASCII string is forbidden")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_restricted_json(item, f"{context}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            require(isinstance(key, str) and key.isascii(), f"{context}: invalid object key")
            validate_restricted_json(item, f"{context}.{key}")
        return
    fail(f"{context}: unsupported JSON value type {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    validate_restricted_json(value)
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(raw: bytes, context: str) -> Any:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise BuildError(f"{context}: JSON is not ASCII") from exc

    def reject_float(value: str) -> NoReturn:
        fail(f"{context}: floating-point token forbidden: {value}")

    def reject_constant(value: str) -> NoReturn:
        fail(f"{context}: non-finite token forbidden: {value}")

    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, BuildError) as exc:
        if isinstance(exc, BuildError):
            raise
        raise BuildError(f"{context}: invalid JSON: {exc}") from exc
    validate_restricted_json(parsed, context)
    return parsed


def load_canonical_repository_json(path: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    require(path.is_file() and not path.is_symlink(), f"canonical JSON absent: {path}")
    raw = path.read_bytes()
    require(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), f"{path}: terminal LF invalid")
    parsed = parse_json(raw[:-1], str(path))
    require(isinstance(parsed, dict), f"{path}: top-level JSON must be an object")
    require(raw == canonical_json_bytes(parsed) + b"\n", f"{path}: repository JSON is not canonical")
    return parsed, raw


def framed_digest(domain: bytes, payload: bytes) -> str:
    frame = struct.pack(">I", len(domain)) + domain + struct.pack(">Q", len(payload)) + payload
    return sha256_bytes(frame)


def recipe_digest(role: str, recipe: Mapping[str, Any]) -> str:
    domain = f"agent-bridge/biocortex/owned-lab/s21b-a1/build-recipe/{role}/v1".encode(
        "ascii"
    )
    return framed_digest(domain, canonical_json_bytes(dict(recipe)))


def command_env() -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "LANG": "C",
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


def run_command(
    argv: Sequence[str | os.PathLike[str]],
    *,
    cwd: pathlib.Path | None = None,
    env: Mapping[str, str] | None = None,
    allowed_returncodes: frozenset[int] = frozenset({0}),
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    rendered = [os.fspath(item) for item in argv]
    completed = subprocess.run(
        rendered,
        cwd=os.fspath(cwd) if cwd else None,
        env=dict(env) if env is not None else command_env(),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode not in allowed_returncodes:
        stderr = completed.stderr[-16_384:].decode("utf-8", "replace")
        stdout = completed.stdout[-16_384:].decode("utf-8", "replace")
        fail(
            f"command failed ({completed.returncode}): {rendered!r}\n"
            f"stdout tail:\n{stdout}\nstderr tail:\n{stderr}"
        )
    return completed


def git(repo: pathlib.Path, *arguments: str, allowed: frozenset[int] = frozenset({0})) -> bytes:
    return run_command(
        [
            GIT,
            "--no-replace-objects",
            "-C",
            repo,
            "-c",
            f"safe.directory={repo}",
            "-c",
            "core.attributesFile=/dev/null",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.commitGraph=false",
            *arguments,
        ],
        env=command_env(),
        allowed_returncodes=allowed,
    ).stdout


def parse_commit(repo: pathlib.Path, oid: str) -> dict[str, Any]:
    require(bool(HEX40.fullmatch(oid)), f"invalid commit OID: {oid}")
    raw = git(repo, "cat-file", "commit", oid)
    headers = raw.split(b"\n\n", 1)[0].splitlines()
    tree_values: list[str] = []
    parents: list[str] = []
    committer_epoch: int | None = None
    for line in headers:
        if line.startswith(b"tree "):
            tree_values.append(line[5:].decode("ascii"))
        elif line.startswith(b"parent "):
            parents.append(line[7:].decode("ascii"))
        elif line.startswith(b"committer "):
            match = re.search(rb" ([0-9]+) [+-][0-9]{4}$", line)
            require(match is not None, f"{oid}: malformed committer header")
            committer_epoch = int(match.group(1))
    require(len(tree_values) == 1 and HEX40.fullmatch(tree_values[0]) is not None, f"{oid}: tree invalid")
    require(all(HEX40.fullmatch(parent) is not None for parent in parents), f"{oid}: parent invalid")
    require(committer_epoch is not None and committer_epoch > 0, f"{oid}: committer epoch invalid")
    return {
        "oid": oid,
        "tree": tree_values[0],
        "parents": parents,
        "committer_epoch": committer_epoch,
        "raw_sha256": sha256_bytes(raw),
    }


def ensure_git_object_boundary(repo: pathlib.Path) -> None:
    require(GIT.is_file() and os.access(GIT, os.X_OK), "fixed Git binary unavailable")
    require(git(repo, "rev-parse", "--is-inside-work-tree").strip() == b"true", "repo is not a worktree")
    require(
        git(repo, "rev-parse", "--is-shallow-repository").strip() == b"false",
        "shallow repository forbidden",
    )
    require(not git(repo, "for-each-ref", "--format=%(refname)", "refs/replace").strip(), "replace refs forbidden")
    for git_path in ("info/grafts", "info/attributes", "objects/info/alternates"):
        value = git(repo, "rev-parse", "--git-path", git_path).decode("utf-8").strip()
        path = pathlib.Path(value)
        if not path.is_absolute():
            path = repo / path
        require(not path.exists() and not path.is_symlink(), f"Git {git_path} forbidden")
    partial = git(
        repo,
        "config",
        "--local",
        "--get-regexp",
        r"^remote\..*\.(promisor|partialclonefilter)$",
        allowed=frozenset({0, 1}),
    )
    require(not partial.strip(), "partial-clone/promisor configuration forbidden")
    remote = git(repo, "remote", "get-url", "origin").decode("utf-8").strip()
    require(remote == CANONICAL_REMOTE, f"origin is not the canonical GitHub remote: {remote!r}")


def validate_target_topology(repo: pathlib.Path, target: str) -> dict[str, Any]:
    require(bool(HEX40.fullmatch(target)), "--target must be one lowercase 40-hex commit OID")
    object_type = git(repo, "cat-file", "-t", target).strip()
    require(object_type == b"commit", "target is not a commit")
    baseline = parse_commit(repo, BASELINE_COMMIT)
    require(baseline["tree"] == BASELINE_TREE, "A0 baseline tree drift")
    require(
        baseline["parents"] == [BASELINE_FIRST_PARENT, BASELINE_SECOND_PARENT],
        "A0 baseline parent topology drift",
    )
    source_base = parse_commit(repo, SOURCE_BASE_COMMIT)
    require(source_base["tree"] == SOURCE_BASE_TREE, "A1 source-base tree drift")
    require(
        source_base["parents"]
        == [SOURCE_BASE_FIRST_PARENT, SOURCE_BASE_SECOND_PARENT],
        "A1 source-base parent topology drift",
    )
    require(
        sha256_bytes(git(repo, "show", f"{SOURCE_BASE_COMMIT}:Cargo.lock"))
        == SOURCE_BASE_CARGO_LOCK_SHA256,
        "A1 source-base Cargo.lock drift",
    )
    source_base_ancestry = run_command(
        [
            GIT,
            "-C",
            repo,
            "-c",
            f"safe.directory={repo}",
            "merge-base",
            "--is-ancestor",
            BASELINE_COMMIT,
            SOURCE_BASE_COMMIT,
        ],
        env=command_env(),
        allowed_returncodes=frozenset({0, 1}),
    )
    require(source_base_ancestry.returncode == 0, "A1 source base is not an A0 descendant")
    target_commit = parse_commit(repo, target)
    require(len(target_commit["parents"]) == 2, "real A1 receipt requires an ordinary two-parent integration")
    first_parent, source_oid = target_commit["parents"]
    require(first_parent == SOURCE_BASE_COMMIT, "integration first parent is not the exact A1 source base")
    source = parse_commit(repo, source_oid)
    require(
        source["parents"] == [SOURCE_BASE_COMMIT],
        "A1 source must be one exact commit over the refrozen source base",
    )
    source_already_integrated = run_command(
        [GIT, "-C", repo, "-c", f"safe.directory={repo}", "merge-base", "--is-ancestor", source_oid, first_parent],
        env=command_env(),
        allowed_returncodes=frozenset({0, 1}),
    )
    require(source_already_integrated.returncode == 1, "integration first parent already contains the A1 source")

    def exact_delta(left: str, right: str, label: str) -> None:
        raw = git(
            repo,
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "--no-renames",
            "-r",
            left,
            right,
        )
        observed: dict[str, str] = {}
        for line in raw.decode("ascii").splitlines():
            parts = line.split("\t")
            require(len(parts) == 2, f"{label}: malformed delta row")
            status, path = parts
            require(status in ("A", "M") and path not in observed, f"{label}: invalid delta row")
            observed[path] = status
        expected = {path: status for path, (status, _) in A1_PACKET_PATHS.items()}
        require(observed == expected, f"{label}: A1 packet delta is not exact 4M+21A")

    exact_delta(SOURCE_BASE_COMMIT, source_oid, "source delta")
    exact_delta(first_parent, target, "integration delta")
    for path, (_, expected_mode) in A1_PACKET_PATHS.items():
        source_entry = git(repo, "ls-tree", source_oid, "--", path)
        target_entry = git(repo, "ls-tree", target, "--", path)
        require(source_entry == target_entry and source_entry, f"source/integration packet blob drift: {path}")
        require(source_entry.decode("ascii").split(" ", 1)[0] == expected_mode, f"packet Git mode drift: {path}")
    require(
        not git(repo, "ls-tree", "-r", target, "--", ".cargo").strip(),
        "target-local Cargo configuration is outside the frozen build recipe",
    )
    return {
        "baseline": baseline,
        "source_base": source_base,
        "source": source,
        "source_parent": source_base,
        "integration": target_commit,
        "integration_first_parent": first_parent,
        "integration_second_parent": source_oid,
    }


def create_private_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(path, 0o700)
    observed = path.lstat()
    require(stat.S_ISDIR(observed.st_mode) and not path.is_symlink(), f"private directory invalid: {path}")
    require(stat.S_IMODE(observed.st_mode) == 0o700, f"private directory mode invalid: {path}")


def prepare_scratch(
    parent: pathlib.Path,
    parent_descriptor: int,
    parent_identity: tuple[int, int],
    name: str,
    resources: contextlib.ExitStack,
) -> tuple[pathlib.Path, int, tuple[int, int]]:
    require_pinned_directory(parent, parent_descriptor, parent_identity)
    created = False
    try:
        entry = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        os.mkdir(name, mode=0o700, dir_fd=parent_descriptor)
        os.fsync(parent_descriptor)
        created = True
        entry = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    require(stat.S_ISDIR(entry.st_mode), "scratch exists but is not a directory")
    require(stat.S_IMODE(entry.st_mode) == 0o700, "scratch mode is not 0700")
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=parent_descriptor,
    )
    resources.callback(os.close, descriptor)
    identity = directory_identity(descriptor)
    require(identity == (entry.st_dev, entry.st_ino), "scratch entry identity changed while pinning")
    require(not os.listdir(descriptor), "scratch must be absent or empty")
    if created:
        os.fchmod(descriptor, 0o700)
        os.fsync(descriptor)
    require_pinned_child_directory(
        parent,
        parent_descriptor,
        parent_identity,
        name,
        descriptor,
        identity,
    )
    pinned_path = parent / name
    pinned = os.stat(pinned_path, follow_symlinks=False)
    require(
        stat.S_ISDIR(pinned.st_mode) and (pinned.st_dev, pinned.st_ino) == identity,
        "scratch pathname binding is invalid",
    )
    return pinned_path, descriptor, identity


def create_archive(repo: pathlib.Path, target: str, destination: pathlib.Path) -> tuple[str, int]:
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            process = subprocess.Popen(
                [
                    os.fspath(GIT),
                    "--no-replace-objects",
                    "-C",
                    os.fspath(repo),
                    "-c",
                    f"safe.directory={repo}",
                    "-c",
                    "core.attributesFile=/dev/null",
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-c",
                    "core.fsmonitor=false",
                    "-c",
                    "core.commitGraph=false",
                    "-c",
                    "tar.umask=0022",
                    "archive",
                    "--format=tar",
                    target,
                ],
                env=command_env(),
                stdout=output,
                stderr=subprocess.PIPE,
            )
            _, stderr = process.communicate()
            if process.returncode != 0:
                fail(f"git archive failed: {stderr.decode('utf-8', 'replace')[-8192:]}")
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            destination.unlink()
        raise
    require(destination.is_file() and not destination.is_symlink(), "archive output invalid")
    return sha256_file(destination), destination.stat().st_size


def _safe_relative_tar_path(name: str) -> pathlib.PurePosixPath:
    require(name and name.isascii() and "\\" not in name and "\x00" not in name, "unsafe tar member name")
    path = pathlib.PurePosixPath(name)
    require(not path.is_absolute(), f"absolute tar member forbidden: {name}")
    require(all(part not in ("", ".", "..") for part in path.parts), f"traversal tar member forbidden: {name}")
    return path


def _mkdir_secure_parents(root: pathlib.Path, relative: pathlib.PurePosixPath) -> None:
    current = root
    for part in relative.parts:
        current = current / part
        if current.exists():
            observed = current.lstat()
            require(stat.S_ISDIR(observed.st_mode) and not current.is_symlink(), f"unsafe extracted parent: {current}")
        else:
            current.mkdir(mode=0o700)


def safe_extract_archive(archive: pathlib.Path, destination: pathlib.Path) -> tuple[int, int]:
    create_private_dir(destination)
    seen: set[str] = set()
    directories: list[tuple[pathlib.Path, int, int]] = []
    file_count = 0
    byte_count = 0
    with tarfile.open(archive, mode="r:") as bundle:
        for member in bundle:
            relative = _safe_relative_tar_path(member.name.rstrip("/") if member.isdir() else member.name)
            key = relative.as_posix()
            require(key not in seen, f"duplicate tar member: {key}")
            seen.add(key)
            target = destination.joinpath(*relative.parts)
            require(os.path.commonpath([destination, target]) == os.fspath(destination), "tar member escaped destination")
            require(not (member.issym() or member.islnk()), f"archive links forbidden: {key}")
            if member.isdir():
                require(member.mode & 0o022 == 0, f"group/world-writable archive directory forbidden: {key}")
                _mkdir_secure_parents(destination, relative.parent)
                if not target.exists():
                    target.mkdir(mode=0o700)
                require(target.is_dir() and not target.is_symlink(), f"invalid archive directory: {key}")
                directories.append((target, member.mode & 0o777, member.mtime))
                continue
            require(member.isreg(), f"special tar member forbidden: {key}")
            require(member.mode & 0o777 in (0o644, 0o755), f"unexpected archive file mode: {key}")
            _mkdir_secure_parents(destination, relative.parent)
            source = bundle.extractfile(member)
            require(source is not None, f"cannot read tar member: {key}")
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                member.mode & 0o777,
            )
            written = 0
            with source, os.fdopen(descriptor, "wb") as output:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(block)
                    written += len(block)
            require(written == member.size, f"tar member size mismatch: {key}")
            os.chmod(target, member.mode & 0o777, follow_symlinks=False)
            os.utime(target, (member.mtime, member.mtime), follow_symlinks=False)
            file_count += 1
            byte_count += written
    for directory, mode, mtime in reversed(directories):
        os.chmod(directory, mode or 0o755, follow_symlinks=False)
        os.utime(directory, (mtime, mtime), follow_symlinks=False)
    require(file_count > 0 and byte_count > 0, "empty Git archive")
    return file_count, byte_count


def git_blob_mode(repo: pathlib.Path, target: str, relative_path: str) -> str:
    output = git(repo, "ls-tree", target, "--", relative_path).decode("utf-8").strip()
    require(output, f"Git tree member absent: {relative_path}")
    match = re.fullmatch(r"([0-7]{6}) blob [0-9a-f]{40}\t(.+)", output)
    require(match is not None and match.group(2) == relative_path, f"Git tree member ambiguous: {relative_path}")
    return match.group(1)


@contextlib.contextmanager
def process_umask(mask: int) -> Iterator[None]:
    previous = os.umask(mask)
    try:
        yield
    finally:
        os.umask(previous)


def require_exact_keys(value: Mapping[str, Any], keys: Iterable[str], context: str) -> None:
    expected = set(keys)
    observed = set(value)
    require(observed == expected, f"{context}: keys differ: missing={sorted(expected - observed)!r}, extra={sorted(observed - expected)!r}")


def require_regular_input(path: pathlib.Path, context: str, mode: int | None = None) -> os.stat_result:
    require(path.exists() and not path.is_symlink(), f"{context}: missing or symlink: {path}")
    observed = path.lstat()
    require(stat.S_ISREG(observed.st_mode), f"{context}: not a regular file: {path}")
    require(observed.st_mode & 0o022 == 0, f"{context}: group/world writable input: {path}")
    if mode is not None:
        require(stat.S_IMODE(observed.st_mode) == mode, f"{context}: mode is not {mode:04o}: {path}")
    return observed


def source_base_blob(repo: pathlib.Path, relative_path: str) -> bytes:
    return git(repo, "show", f"{SOURCE_BASE_COMMIT}:{relative_path}")


def expected_a1_workspace_manifest(baseline_workspace: bytes) -> bytes:
    """Insert A1 only at the uniquely contextualized workspace-members tail."""
    require(
        baseline_workspace.count(BASELINE_WORKSPACE_MEMBERS_TAIL) == 1,
        "baseline Cargo.toml workspace-members tail drift",
    )
    return baseline_workspace.replace(
        BASELINE_WORKSPACE_MEMBERS_TAIL,
        A1_WORKSPACE_MEMBERS_TAIL,
        1,
    )


def validate_source_graph(
    root: pathlib.Path, repo: pathlib.Path, target: str
) -> tuple[str, list[str]]:
    """Validate that A1 changes the workspace/lock/toolchain only as preregistered."""
    baseline_workspace = source_base_blob(repo, "Cargo.toml")
    expected_workspace = expected_a1_workspace_manifest(baseline_workspace)
    workspace_path = root / "Cargo.toml"
    require_regular_input(workspace_path, "workspace manifest", 0o644)
    require(workspace_path.read_bytes() == expected_workspace, "target Cargo.toml is not the exact A1 member insertion")

    baseline_toolchain = source_base_blob(repo, "rust-toolchain.toml")
    require(baseline_toolchain.count(b'channel = "stable"') == 1, "baseline toolchain marker drift")
    expected_toolchain = baseline_toolchain.replace(
        b'channel = "stable"', b'channel = "1.96.0"', 1
    )
    toolchain_path = root / "rust-toolchain.toml"
    require_regular_input(toolchain_path, "rust-toolchain.toml", 0o644)
    require(toolchain_path.read_bytes() == expected_toolchain, "target rust-toolchain.toml is not exactly pinned to 1.96.0")

    baseline_lock = source_base_blob(repo, "Cargo.lock")
    lock_marker = b'[[package]]\nname = "ab-store"\nversion = "0.14.0"\n'
    require(baseline_lock.count(lock_marker) == 1, "baseline Cargo.lock insertion marker drift")
    role_lock_entry = b'[[package]]\nname = "ab-owned-lab-role-artifacts"\nversion = "0.14.0"\n\n'
    expected_lock = baseline_lock.replace(lock_marker, role_lock_entry + lock_marker, 1)
    lock_path = root / "Cargo.lock"
    require_regular_input(lock_path, "Cargo.lock", 0o644)
    lock_raw = lock_path.read_bytes()
    require(lock_raw == expected_lock, "target Cargo.lock is not the exact A1 zero-dependency insertion")
    try:
        lock = tomllib.loads(lock_raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise BuildError(f"Cargo.lock parsing failed: {exc}") from exc
    packages = lock.get("package")
    require(isinstance(packages, list), "Cargo.lock packages absent")
    role_entries = [item for item in packages if item.get("name") == "ab-owned-lab-role-artifacts"]
    require(role_entries == [{"name": "ab-owned-lab-role-artifacts", "version": "0.14.0"}], "role lock entry is not exact")
    registry_packages = [item for item in packages if item.get("source") == SPARSE_INDEX_SOURCE_ID]
    require(len(packages) == 580 and len(registry_packages) == 566, "Cargo.lock package/source counts drift")
    require(
        all("checksum" in item and isinstance(item["checksum"], str) and HEX64.fullmatch(item["checksum"]) for item in registry_packages),
        "registry package checksum missing or malformed",
    )
    require(
        all(item.get("source") in (None, SPARSE_INDEX_SOURCE_ID) for item in packages),
        "unapproved Cargo.lock source",
    )
    registry_names = sorted({item["name"] for item in registry_packages})
    require(len(registry_names) == 531, "unique registry package-name count drift")
    require(all(isinstance(name, str) and name.isascii() and re.fullmatch(r"[A-Za-z0-9_-]+", name) for name in registry_names), "registry package name invalid")

    package_path = root / ROLE_PACKAGE_MANIFEST_REL
    require_regular_input(package_path, "role package manifest", 0o644)
    try:
        package = tomllib.loads(package_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise BuildError(f"role package manifest parsing failed: {exc}") from exc
    expected_package = {
        "package": {
            "name": "ab-owned-lab-role-artifacts",
            "version": {"workspace": True},
            "edition": {"workspace": True},
            "license": {"workspace": True},
            "rust-version": {"workspace": True},
            "publish": False,
            "autobins": False,
            "autoexamples": False,
            "autotests": False,
            "autobenches": False,
        },
        "features": {"default": []},
        "lib": {"path": "src/lib.rs"},
        "bin": [
            {"name": binary, "path": source.removeprefix("crates/owned-lab-role-artifacts/")}
            for _, binary, source, _ in ROLE_SPECS
        ],
    }
    require(package == expected_package, "role package manifest drift or dependency/build-script surface present")
    expected_files = sorted(
        [ROLE_PACKAGE_MANIFEST_REL, "crates/owned-lab-role-artifacts/src/lib.rs"]
        + [source for _, _, source, _ in ROLE_SPECS]
    )
    tracked = git(repo, "ls-tree", "-r", "--name-only", target, "--", "crates/owned-lab-role-artifacts").decode("ascii").splitlines()
    require(sorted(tracked) == expected_files, "role package tracked source closure drift")
    for relative in expected_files:
        require(git_blob_mode(repo, target, relative) == "100644", f"role package Git mode drift: {relative}")
        require_regular_input(root / relative, f"role source {relative}", 0o644)
    return sha256_bytes(lock_raw), registry_names


def validate_manifest_common(value: Mapping[str, Any], format_id: str, context: str) -> None:
    require(value.get("canonicalization") == CANONICALIZATION, f"{context}: canonicalization drift")
    require(value.get("format_id") == format_id, f"{context}: format_id drift")
    require(value.get("manifest_digest_contract") == MANIFEST_DIGEST_CONTRACT, f"{context}: digest contract drift")


def expected_feature_set() -> dict[str, Any]:
    return {
        "binary_targets": [binary for _, binary, _, _ in ROLE_SPECS],
        "canonicalization": CANONICALIZATION,
        "cargo_package": "ab-owned-lab-role-artifacts",
        "default_features": False,
        "direct_features": [],
        "format_id": "agent_bridge.memory_temporal_owned_lab_role_build_feature_set_s21b_a1.v0",
        "manifest_digest_contract": MANIFEST_DIGEST_CONTRACT,
        "package_dependencies": [],
        "package_version": "0.14.0",
        "requested_primary_target_kinds": ["bin"],
        "resolved_package_feature_graph": [
            {"features": [], "package": "ab-owned-lab-role-artifacts", "version": "0.14.0"}
        ],
        "source_closure": [source for _, _, source, _ in ROLE_SPECS]
        + ["crates/owned-lab-role-artifacts/src/lib.rs"],
        "transitively_compiled_targets": [
            {
                "crate_types": ["lib"],
                "kind": "lib",
                "name": "ab_owned_lab_role_artifacts",
                "source_relative_path": "crates/owned-lab-role-artifacts/src/lib.rs",
            }
        ],
    }


def expected_schema_set() -> dict[str, Any]:
    return {
        "canonicalization": CANONICALIZATION,
        "closure_digest_domain": "agent-bridge/biocortex/owned-lab/s21b-a1/schema-set/v1",
        "closure_digest_profile": SCHEMA_CONTENT_PROFILE,
        "format_id": "agent_bridge.memory_temporal_owned_lab_role_build_schema_set_s21b_a1.v0",
        "manifest_digest_contract": MANIFEST_DIGEST_CONTRACT,
        "member_count": 4,
        "members": [{"git_mode": "100644", "path": path} for path in EXPECTED_SCHEMA_MEMBERS],
        "set_scope": "S21A_FINAL_REFREEZE_OWNER_BINDING_AND_EXTERNAL_INPUT_PACKET_SCHEMAS_ONLY",
    }


def expected_recipes() -> dict[str, Any]:
    environment = {
        "AR": "/usr/bin/x86_64-linux-gnu-ar",
        "CARGO_BUILD_JOBS": "1",
        "CARGO_HOME": "/ab-build/cargo-home",
        "CARGO_INCREMENTAL": "0",
        "CARGO_NET_OFFLINE": "true",
        "CARGO_PROFILE_RELEASE_CODEGEN_UNITS": "1",
        "CARGO_PROFILE_RELEASE_DEBUG": "0",
        "CARGO_PROFILE_RELEASE_INCREMENTAL": "false",
        "CARGO_PROFILE_RELEASE_LTO": "thin",
        "CARGO_PROFILE_RELEASE_OPT_LEVEL": "3",
        "CARGO_PROFILE_RELEASE_PANIC": "unwind",
        "CARGO_PROFILE_RELEASE_STRIP": "symbols",
        "CARGO_TARGET_DIR": "/ab-build/target",
        "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER": "/usr/bin/x86_64-linux-gnu-gcc-15",
        "CARGO_TERM_COLOR": "never",
        "CC": "/usr/bin/x86_64-linux-gnu-gcc-15",
        "HOME": "/ab-build/home",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "MAKEFLAGS": "-j1",
        "MALLOC_ARENA_MAX": "2",
        "PATH": "/rust-toolchain/bin:/usr/bin:/bin",
        "RAYON_NUM_THREADS": "1",
        "RUSTC": "/rust-toolchain/bin/rustc",
        "SOURCE_DATE_EPOCH": "DERIVED_FROM_TARGET_COMMIT_COMMITTER_UNIX_EPOCH",
        "TMPDIR": "/ab-build/tmp",
        "TZ": "UTC",
    }
    recipes = []
    for _, binary, source, output in ROLE_SPECS:
        recipes.append(
            {
                "arguments": [
                    "build", "--frozen", "--locked", "--offline", "--release",
                    "-j", "1", "--target", "x86_64-unknown-linux-gnu", "-p",
                    "ab-owned-lab-role-artifacts", "--no-default-features", "--bin", binary,
                ],
                "binary_name": binary,
                "output_relative_path": output,
                "source_relative_path": source,
                "transitively_compiled_source_relative_paths": [
                    "crates/owned-lab-role-artifacts/src/lib.rs"
                ],
            }
        )
    return {
        "build_order": [binary for _, binary, _, _ in ROLE_SPECS],
        "canonicalization": CANONICALIZATION,
        "cargo_binary": "/rust-toolchain/bin/cargo",
        "cargo_profile": {
            "codegen_units": 1, "debug": 0, "incremental": False, "lto": "thin",
            "opt_level": 3, "panic": "unwind", "strip": "symbols",
        },
        "environment": environment,
        "format_id": "agent_bridge.memory_temporal_owned_lab_role_build_recipes_s21b_a1.v0",
        "isolation": {
            "bubblewrap_binary_path": "/usr/bin/bwrap",
            "bubblewrap_binary_sha256": "0abea81db798ebf6b4742ac0664802d97521547a353c2a0dbdc21d76cbbfd2c0",
            "bubblewrap_release": "0.11.1",
            "canonical_cargo_home": "/ab-build/cargo-home",
            "canonical_home": "/ab-build/home",
            "canonical_source": "/ab-build/source",
            "canonical_target": "/ab-build/target",
            "canonical_tmp": "/ab-build/tmp",
            "environment_base": "EMPTY_ENV_EXCEPT_DECLARED_ENVIRONMENT_AND_DERIVED_CARGO_ENCODED_RUSTFLAGS",
            "network_namespace": "UNSHARED_NO_NETWORK",
            "process_umask": "0022",
            "scratch_binding": "SECURE_ANCESTRY_MKDIRAT_OPENAT_PINNED_DIRFD_WITH_DEV_INO_REVALIDATION",
            "secure_ancestry_policy": "EVERY_ANCESTOR_ROOT_OR_EUID_OWNED_AND_NOT_GROUP_OR_OTHER_WRITABLE_EXCEPT_ROOT_OWNED_STICKY_DIRECTORY",
            "source_mount": "READ_ONLY",
            "toolchain_mount_source": "PRIVATE_FULL_TREE_CATALOG_VERIFIED_SNAPSHOT",
            "two_fresh_archive_roots_required": True,
            "two_fresh_target_dirs_required": True,
            "working_directory": "/ab-build/source",
        },
        "manifest_digest_contract": MANIFEST_DIGEST_CONTRACT,
        "nonclaims": {
            "build_equality_proves_behavioral_correctness": False,
            "build_equality_proves_cross_host_reproducibility": False,
            "build_recipe_authorizes_live_execution": False,
            "provider_or_production_authority": False,
            "side_effects_unlocked": "NONE",
        },
        "per_role_recipe_digest_contract": {
            "canonical_payload": "COMPLETE_RECIPE_OBJECT_AB_RESTRICTED_COMPACT_SORTED_KEYS_UTF8_WITHOUT_TERMINAL_LF",
            "digest_domain_template": "agent-bridge/biocortex/owned-lab/s21b-a1/build-recipe/<role>/v1",
            "digest_framing": RECIPE_DIGEST_FRAMING,
            "hash_algorithm": "SHA-256",
            "role_placeholder_values": [role for role, _, _, _ in ROLE_SPECS],
        },
        "recipes": recipes,
        "rustflags": [
            "--remap-path-prefix=/ab-build/source=/agent-bridge",
            "--remap-path-prefix=/ab-build/target=/agent-bridge-target",
            "--remap-path-prefix=/ab-build/cargo-home=/cargo-home",
            "-Ctarget-cpu=x86-64", "-Cdebuginfo=0", "-Cstrip=symbols",
            "-Ccodegen-units=1", "-Clink-arg=-Wl,--build-id=none",
        ],
        "rustflags_injection": {
            "encoding": "UTF8_FLAGS_JOINED_BY_SINGLE_UNIT_SEPARATOR_WITH_NO_TERMINATOR",
            "environment_variable": "CARGO_ENCODED_RUSTFLAGS",
            "rustflags_array_is_authoritative": True,
            "separator_byte_hex": "1f",
        },
        "shared_compiled_target": {
            "crate_types": ["lib"], "kind": "lib", "name": "ab_owned_lab_role_artifacts",
            "source_relative_path": "crates/owned-lab-role-artifacts/src/lib.rs",
        },
        "source_date_epoch_derivation": {
            "binding_commit": "TARGET_COMMIT",
            "command": ["git", "show", "-s", "--format=%ct", "TARGET_COMMIT"],
            "export_environment_variable": "SOURCE_DATE_EPOCH",
            "output_validation": "ONE_ASCII_DECIMAL_NONNEGATIVE_INTEGER_LINE",
        },
        "target_triple": "x86_64-unknown-linux-gnu",
    }


def sparse_index_relative_path(package_name: str) -> pathlib.PurePosixPath:
    require(package_name.isascii() and re.fullmatch(r"[A-Za-z0-9_-]+", package_name) is not None, "invalid sparse-index package name")
    name = package_name.lower()
    if len(name) == 1:
        tail = pathlib.PurePosixPath("1", name)
    elif len(name) == 2:
        tail = pathlib.PurePosixPath("2", name)
    elif len(name) == 3:
        tail = pathlib.PurePosixPath("3", name[0], name)
    else:
        tail = pathlib.PurePosixPath(name[:2], name[2:4], name)
    return pathlib.PurePosixPath(".cache") / tail


def sparse_index_observation(registry_names: Sequence[str]) -> tuple[dict[str, Any], list[tuple[pathlib.PurePosixPath, pathlib.Path]]]:
    logical_root = "/ab-build/cargo-home/registry/index/index.crates.io-1949cf8c6b5b557f"
    host_root = TRUSTED_CARGO_REGISTRY / "index" / pathlib.PurePosixPath(logical_root).name
    require(host_root.is_dir() and not host_root.is_symlink(), "trusted sparse-index root absent or symlinked")
    relatives = [pathlib.PurePosixPath("config.json")] + [sparse_index_relative_path(name) for name in registry_names]
    require(
        len(relatives) == len(set(relatives)) == len(registry_names) + 1,
        "sparse-index selected path count drift",
    )
    selected: list[tuple[pathlib.PurePosixPath, pathlib.Path]] = []
    lines: list[bytes] = []
    total = 0
    for relative in sorted(relatives, key=lambda item: item.as_posix().encode("ascii")):
        source = host_root.joinpath(*relative.parts)
        require(source.exists() and not source.is_symlink(), f"sparse-index member absent or symlinked: {relative}")
        observed = source.lstat()
        require(stat.S_ISREG(observed.st_mode), f"sparse-index member is not regular: {relative}")
        size = observed.st_size
        digest = sha256_file(source)
        line = f"{relative.as_posix()}\t{size}\t{digest}\n".encode("ascii")
        lines.append(line)
        total += size
        selected.append((relative, source))
    result = {
        "cache_file_format": "CARGO_SPARSE_INDEX_CACHE_OPAQUE_RAW_FILE_BYTES",
        "catalog_digest_profile": SPARSE_INDEX_CATALOG_PROFILE,
        "catalog_sha256": sha256_bytes(b"".join(lines)),
        "file_count": len(selected),
        "logical_build_root": logical_root,
        "package_name_count": len(registry_names),
        "path_derivation_profile": SPARSE_INDEX_PATH_PROFILE,
        "selection": "CONFIG_JSON_PLUS_EXACT_UNIQUE_PACKAGE_NAMES_WITH_REGISTRY_SOURCE_IN_TARGET_CARGO_LOCK",
        "source_id": SPARSE_INDEX_SOURCE_ID,
        "total_byte_count": total,
    }
    return result, selected


def copy_sparse_index(cargo_home: pathlib.Path, selected: Sequence[tuple[pathlib.PurePosixPath, pathlib.Path]]) -> None:
    require(cargo_home.is_dir() and not cargo_home.is_symlink(), "fresh Cargo home invalid")
    registry_root = cargo_home / "registry"
    registry_index_root = registry_root / "index"
    create_private_dir(registry_root)
    create_private_dir(registry_index_root)
    index_root = registry_index_root / "index.crates.io-1949cf8c6b5b557f"
    create_private_dir(index_root)
    created_directories: set[pathlib.Path] = {index_root}
    for relative, source in selected:
        destination = index_root.joinpath(*relative.parts)
        current = index_root
        for part in relative.parent.parts:
            current /= part
            if not current.exists():
                current.mkdir(mode=0o700)
                created_directories.add(current)
            else:
                require(current.is_dir() and not current.is_symlink(), "sparse-index destination parent invalid")
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        with source.open("rb") as input_stream, os.fdopen(descriptor, "wb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.chmod(destination, 0o444, follow_symlinks=False)
        require(sha256_file(destination) == sha256_file(source), f"sparse-index copy mismatch: {relative}")
    for directory in sorted(created_directories, key=lambda item: len(item.parts), reverse=True):
        os.chmod(directory, 0o555)


def validate_sparse_index_copy(
    cargo_home: pathlib.Path,
    expected: Mapping[str, Any],
    selected: Sequence[tuple[pathlib.PurePosixPath, pathlib.Path]],
) -> None:
    index_root = cargo_home / "registry/index/index.crates.io-1949cf8c6b5b557f"
    expected_relatives = {relative.as_posix() for relative, _ in selected}
    observed_relatives: set[str] = set()
    lines: list[bytes] = []
    total = 0
    for path in index_root.rglob("*"):
        relative = path.relative_to(index_root).as_posix()
        observed = path.lstat()
        if stat.S_ISDIR(observed.st_mode):
            require(stat.S_IMODE(observed.st_mode) == 0o555, f"copied sparse-index directory is not read-only: {relative}")
            continue
        require(stat.S_ISREG(observed.st_mode) and not path.is_symlink(), f"copied sparse-index special member: {relative}")
        require(stat.S_IMODE(observed.st_mode) == 0o444, f"copied sparse-index file is not 0444: {relative}")
        require(relative in expected_relatives, f"unselected sparse-index file copied: {relative}")
        observed_relatives.add(relative)
        digest = sha256_file(path)
        lines.append(f"{relative}\t{observed.st_size}\t{digest}\n".encode("ascii"))
        total += observed.st_size
    require(observed_relatives == expected_relatives, "copied sparse-index member set mismatch")
    lines.sort(key=lambda line: line.split(b"\t", 1)[0])
    require(len(lines) == expected["file_count"], "copied sparse-index file count mismatch")
    require(total == expected["total_byte_count"], "copied sparse-index byte count mismatch")
    require(sha256_bytes(b"".join(lines)) == expected["catalog_sha256"], "copied sparse-index catalog digest mismatch")


def _locked_registry_packages(lock_path: pathlib.Path) -> list[dict[str, str]]:
    raw = lock_path.read_bytes()
    require(
        sha256_bytes(raw) == BASELINE_CARGO_LOCK_SHA256,
        "predecessor Cargo.lock digest drift",
    )
    lock = tomllib.loads(raw.decode("utf-8"))
    packages: list[dict[str, str]] = []
    for package in lock["package"]:
        if package.get("source") != SPARSE_INDEX_SOURCE_ID:
            continue
        name = package.get("name")
        version = package.get("version")
        checksum = package.get("checksum")
        require(
            isinstance(name, str)
            and name.isascii()
            and isinstance(version, str)
            and version.isascii()
            and isinstance(checksum, str)
            and HEX64.fullmatch(checksum) is not None,
            "locked registry package identity is invalid",
        )
        packages.append({"name": name, "version": version, "checksum": checksum})
    packages.sort(key=lambda item: (item["name"], item["version"], item["checksum"]))
    require(len(packages) == 555, "locked registry archive package count drift")
    return packages


def observe_locked_registry_archives(
    lock_path: pathlib.Path,
    cache_root: pathlib.Path,
) -> tuple[dict[str, Any], list[tuple[pathlib.PurePosixPath, pathlib.Path, str, int]]]:
    root_entry = cache_root.lstat()
    require(
        stat.S_ISDIR(root_entry.st_mode) and not cache_root.is_symlink(),
        "registry archive cache root is invalid",
    )
    rows: list[bytes] = []
    selected: list[tuple[pathlib.PurePosixPath, pathlib.Path, str, int]] = []
    total_byte_count = 0
    for package in _locked_registry_packages(lock_path):
        archive_name = f"{package['name']}-{package['version']}.crate"
        matches = list(cache_root.rglob(archive_name))
        require(len(matches) == 1, f"registry archive multiplicity drift: {archive_name}")
        source = matches[0]
        relative = pathlib.PurePosixPath(source.relative_to(cache_root).as_posix())
        require(
            len(relative.parts) == 2 and relative.name == archive_name,
            f"registry archive layout drift: {relative}",
        )
        parent_entry = source.parent.lstat()
        before = source.lstat()
        require(
            stat.S_ISDIR(parent_entry.st_mode)
            and not source.parent.is_symlink()
            and stat.S_ISREG(before.st_mode)
            and not source.is_symlink(),
            f"registry archive type drift: {relative}",
        )
        descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            opened = os.fstat(descriptor)
            require(
                (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                == (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns),
                f"registry archive identity changed while opening: {relative}",
            )
            digest = hashlib.sha256()
            observed_size = 0
            while True:
                block = os.read(descriptor, 1024 * 1024)
                if not block:
                    break
                digest.update(block)
                observed_size += len(block)
            after = os.fstat(descriptor)
            require(
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                == (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns),
                f"registry archive changed while reading: {relative}",
            )
        finally:
            os.close(descriptor)
        require(observed_size == before.st_size, f"registry archive size drift: {relative}")
        require(digest.hexdigest() == package["checksum"], f"registry archive checksum drift: {relative}")
        rows.append(
            f"{package['name']}\t{package['version']}\t{package['checksum']}\n".encode("ascii")
        )
        selected.append((relative, source, package["checksum"], observed_size))
        total_byte_count += observed_size
    rows.sort()
    selected.sort(key=lambda item: item[0].as_posix().encode("ascii"))
    return (
        {
            "archive_count": len(selected),
            "total_byte_count": total_byte_count,
            "tuple_catalog_sha256": sha256_bytes(b"".join(rows)),
        },
        selected,
    )


def copy_locked_registry_archive_snapshot(
    lock_path: pathlib.Path,
    destination_cache_root: pathlib.Path,
) -> dict[str, Any]:
    expected = {
        "archive_count": 555,
        "total_byte_count": 85_385_269,
        "tuple_catalog_sha256": "4ca4d49308fbf6c2e5d6952feca4c7079e24e2be88fa1b1d5b9ee11278137ed8",
    }
    source_cache_root = TRUSTED_CARGO_REGISTRY / "cache"
    observed_before, selected = observe_locked_registry_archives(lock_path, source_cache_root)
    require(observed_before == expected, "host locked registry archive closure drift before copy")
    create_private_dir(destination_cache_root)
    destination_directories: set[pathlib.Path] = {destination_cache_root}
    for relative, source, checksum, expected_size in selected:
        destination_parent = destination_cache_root / relative.parts[0]
        if not destination_parent.exists():
            create_private_dir(destination_parent)
            destination_directories.add(destination_parent)
        else:
            parent_entry = destination_parent.lstat()
            require(
                stat.S_ISDIR(parent_entry.st_mode) and not destination_parent.is_symlink(),
                f"private registry archive parent invalid: {relative}",
            )
        destination = destination_cache_root.joinpath(*relative.parts)
        before = source.lstat()
        source_descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        destination_descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o400,
        )
        try:
            opened = os.fstat(source_descriptor)
            require(
                (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                == (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns),
                f"registry archive identity changed before copy: {relative}",
            )
            digest = hashlib.sha256()
            copied = 0
            while True:
                block = os.read(source_descriptor, 1024 * 1024)
                if not block:
                    break
                digest.update(block)
                copied += len(block)
                view = memoryview(block)
                while view:
                    written = os.write(destination_descriptor, view)
                    require(written > 0, "registry archive copy made no progress")
                    view = view[written:]
            os.fchmod(destination_descriptor, 0o444)
            os.fsync(destination_descriptor)
            after = os.fstat(source_descriptor)
            require(
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                == (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns),
                f"registry archive changed during copy: {relative}",
            )
            require(
                copied == expected_size and digest.hexdigest() == checksum,
                f"registry archive copy checksum drift: {relative}",
            )
        finally:
            os.close(destination_descriptor)
            os.close(source_descriptor)
    for directory in sorted(destination_directories, key=lambda item: len(item.parts), reverse=True):
        os.chmod(directory, 0o555, follow_symlinks=False)
    observed_destination, _ = observe_locked_registry_archives(lock_path, destination_cache_root)
    require(observed_destination == expected, "private locked registry archive closure drift")
    observed_after, _ = observe_locked_registry_archives(lock_path, source_cache_root)
    require(observed_after == expected, "host locked registry archive closure drift after copy")
    return expected


def _adapter_fail(message: str) -> NoReturn:
    print(
        f"A1 predecessor bwrap flatten adapter denied invocation: {message}",
        file=sys.stderr,
    )
    raise SystemExit(125)


def _adapter_require_directory(path: pathlib.Path, expected_mode: int) -> None:
    observed = path.lstat()
    if path.is_symlink() or not stat.S_ISDIR(observed.st_mode):
        _adapter_fail(f"unsafe directory type: {path}")
    if (
        observed.st_uid != 0
        or observed.st_gid != 0
        or stat.S_IMODE(observed.st_mode) != expected_mode
    ):
        _adapter_fail(f"unsafe directory owner or mode: {path}")


def _adapter_validate_runtime_cargo_seed(
    cargo_home: pathlib.Path,
    *,
    label: str,
    pristine: bool,
    home_must_be_writable: bool,
    initial_extra_entries: Sequence[str] = (),
) -> None:
    registry = cargo_home / "registry"
    index_container = registry / "index"
    cache_root = registry / "cache"
    source_root = registry / "src"
    for path, mode in (
        (cargo_home, 0o700),
        (registry, 0o555),
        (index_container, 0o700),
        (cache_root, 0o555),
        (source_root, 0o700),
    ):
        _adapter_require_directory(path, mode)
        if path.resolve(strict=True) != path:
            _adapter_fail(f"{label} path is not canonical: {path}")
    home_is_read_only = bool(os.statvfs(cargo_home).f_flag & os.ST_RDONLY)
    if home_is_read_only == home_must_be_writable:
        _adapter_fail(f"{label} home mount mode drift")
    for path in (registry, index_container, cache_root):
        if not os.statvfs(path).f_flag & os.ST_RDONLY:
            _adapter_fail(f"{label} seed is not read-only mounted: {path}")
    if os.statvfs(source_root).f_flag & os.ST_RDONLY:
        _adapter_fail(f"{label} extracted-source root is not writable")
    expected_entries = {"registry", *initial_extra_entries}
    observed_entries = set(os.listdir(cargo_home))
    if pristine or not home_must_be_writable:
        if observed_entries != expected_entries:
            _adapter_fail(f"{label} home is not initially pristine")
    else:
        generated_entries = observed_entries - expected_entries
        allowed_generated_entries = {
            ".global-cache",
            ".package-cache",
            ".package-cache-mutate",
        }
        if not expected_entries.issubset(observed_entries) or not generated_entries.issubset(
            allowed_generated_entries
        ):
            _adapter_fail(f"{label} generated top-level member set drift")
        home_device = cargo_home.lstat().st_dev
        for name in generated_entries:
            path = cargo_home / name
            observed = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISREG(observed.st_mode)
                or observed.st_dev != home_device
                or observed.st_uid != 0
                or observed.st_gid != 0
                or observed.st_nlink != 1
                or stat.S_IMODE(observed.st_mode) & (stat.S_IWGRP | stat.S_IWOTH)
            ):
                _adapter_fail(f"{label} generated top-level member identity drift: {name}")
    if pristine and any(source_root.iterdir()):
        _adapter_fail(f"{label} extracted-source root is not initially empty")
    for config_name in ("config", "config.toml"):
        config_path = cargo_home / config_name
        if config_path.exists() or config_path.is_symlink():
            _adapter_fail(f"{label} Cargo configuration injection observed: {config_name}")
    if sorted(os.listdir(registry), key=os.fsencode) != [
        "CACHEDIR.TAG",
        "cache",
        "index",
        "src",
    ]:
        _adapter_fail(f"{label} registry layout drift")

    cache_tag = registry / "CACHEDIR.TAG"
    tag_observed = cache_tag.lstat()
    if (
        cache_tag.is_symlink()
        or not stat.S_ISREG(tag_observed.st_mode)
        or tag_observed.st_uid != 0
        or tag_observed.st_gid != 0
        or tag_observed.st_nlink != 1
        or stat.S_IMODE(tag_observed.st_mode) != 0o444
        or cache_tag.read_bytes() != PREDECESSOR_CARGO_CACHE_TAG
    ):
        _adapter_fail(f"{label} cache-directory tag drift")

    observed_index = _adapter_observe_retired_sparse_index_tree(
        index_container,
        index_container.lstat().st_dev,
        0o555,
    )
    if observed_index != PREDECESSOR_SPARSE_INDEX_CATALOG:
        _adapter_fail(f"{label} sparse-index catalog drift")

    cache_children = sorted(os.listdir(cache_root), key=os.fsencode)
    registry_name = "index.crates.io-1949cf8c6b5b557f"
    if cache_children != [registry_name]:
        _adapter_fail(f"{label} archive-cache layout drift")
    archive_directory = cache_root / registry_name
    _adapter_require_directory(archive_directory, 0o555)
    cache_device = cache_root.lstat().st_dev
    if archive_directory.lstat().st_dev != cache_device:
        _adapter_fail(f"{label} archive-cache device drift")
    archive_files = sorted(archive_directory.iterdir(), key=lambda item: os.fsencode(item.name))
    if len(archive_files) != PREDECESSOR_REGISTRY_ARCHIVE_CATALOG["archive_count"]:
        _adapter_fail(f"{label} archive-cache file-count drift")
    for path in archive_files:
        observed = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(observed.st_mode)
            or observed.st_dev != cache_device
            or observed.st_uid != 0
            or observed.st_gid != 0
            or observed.st_nlink != 1
            or stat.S_IMODE(observed.st_mode) != 0o444
        ):
            _adapter_fail(f"{label} archive identity drift: {path}")
    observed_archives, _ = observe_locked_registry_archives(
        pathlib.Path("/opt/Cargo.lock"),
        cache_root,
    )
    if observed_archives != PREDECESSOR_REGISTRY_ARCHIVE_CATALOG:
        _adapter_fail(f"{label} archive catalog drift")


def _adapter_validate_runtime_user_cargo_proxy_bin() -> None:
    proxy_bin = pathlib.Path("/home/pallasting/.cargo/bin")
    _adapter_require_directory(proxy_bin, 0o700)
    if not os.statvfs(proxy_bin).f_flag & os.ST_RDONLY:
        _adapter_fail("runtime user Cargo proxy bin is not read-only")
    names = ("cargo", "rustc", "rustdoc", "rustfmt")
    if sorted(os.listdir(proxy_bin), key=os.fsencode) != sorted(names, key=os.fsencode):
        _adapter_fail("runtime user Cargo proxy-bin member set drift")
    for name in names:
        path = proxy_bin / name
        target = f"/home/pallasting/.rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu/bin/{name}"
        if not path.is_symlink() or os.readlink(path) != target:
            _adapter_fail(f"runtime user Cargo proxy identity drift: {name}")


def _adapter_validate_runtime_cargo_cross_home_identities() -> None:
    root_cargo = pathlib.Path("/root/.cargo")
    user_cargo = pathlib.Path("/home/pallasting/.cargo")
    if root_cargo.samefile(user_cargo):
        _adapter_fail("runtime root and user Cargo homes share an identity")
    if (root_cargo / "registry/src").samefile(user_cargo / "registry/src"):
        _adapter_fail("runtime root and user Cargo extracted-source roots share an identity")
    for relative in (
        pathlib.PurePosixPath("registry"),
        pathlib.PurePosixPath("registry/CACHEDIR.TAG"),
        pathlib.PurePosixPath("registry/index"),
        pathlib.PurePosixPath("registry/cache"),
    ):
        if not root_cargo.joinpath(*relative.parts).samefile(
            user_cargo.joinpath(*relative.parts)
        ):
            _adapter_fail(f"runtime Cargo shared read-only seed identity drift: {relative}")


def _adapter_validate_bwrap_flatten_launcher() -> None:
    launcher = pathlib.Path("/usr/bin/bwrap")
    observed = launcher.lstat()
    if (
        launcher.is_symlink()
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_uid != 0
        or observed.st_gid != 0
        or observed.st_nlink != 1
        or stat.S_IMODE(observed.st_mode) != 0o500
        or not os.statvfs(launcher).f_flag & os.ST_RDONLY
    ):
        _adapter_fail("predecessor bwrap flatten launcher identity drift")
    payload = launcher.read_bytes()
    if (
        payload != PREDECESSOR_BWRAP_FLATTEN_LAUNCHER
        or hashlib.sha256(payload).hexdigest()
        != PREDECESSOR_BWRAP_FLATTEN_LAUNCHER_SHA256
    ):
        _adapter_fail("predecessor bwrap flatten launcher content drift")


def _adapter_validate_outer_namespace() -> None:
    if os.geteuid() != 0 or os.getegid() != 0:
        _adapter_fail("outer namespace identity is not root-mapped")
    _adapter_require_directory(pathlib.Path("/tmp"), 0o1777)
    _adapter_require_directory(pathlib.Path("/run"), 0o755)
    _adapter_require_directory(pathlib.Path("/root"), 0o755)
    _adapter_require_directory(pathlib.Path("/Data/CascadeProjects"), 0o700)
    _adapter_require_directory(pathlib.Path("/home/pallasting"), 0o700)
    if (
        sorted(os.listdir("/run"), key=os.fsencode) != ["a1-real-gnurm"]
        or pathlib.Path("/var/run").resolve() != pathlib.Path("/run")
    ):
        _adapter_fail("outer runtime namespace is not private with the exact pinned rm")
    if sorted(os.listdir("/root"), key=os.fsencode) != [".cargo"]:
        _adapter_fail("outer root home contains an unexpected entry")
    if sorted(os.listdir("/home/pallasting"), key=os.fsencode) != [
        ".cache",
        ".cargo",
        ".rustup",
    ]:
        _adapter_fail("outer user home contains an unexpected entry")
    if not os.statvfs("/").f_flag & os.ST_RDONLY:
        _adapter_fail("outer root is not read-only")
    for path in (
        "/root",
        "/home/pallasting/.cargo",
        "/home/pallasting/.cargo/bin",
        "/home/pallasting/.cargo/registry",
        "/home/pallasting/.rustup",
        "/home/pallasting/.rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu",
        "/home/pallasting/.rustup/toolchains/stable-x86_64-unknown-linux-gnu",
        "/usr/bin/bwrap",
        "/usr/bin/gnurm",
        "/usr/bin/rm",
    ):
        if not os.statvfs(path).f_flag & os.ST_RDONLY:
            _adapter_fail(f"security input is not read-only: {path}")
    _adapter_validate_bwrap_flatten_launcher()
    _adapter_validate_gnurm_cleanup_launcher()
    canonical_toolchain = pathlib.Path(
        "/home/pallasting/.rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu"
    )
    stable_toolchain = pathlib.Path(
        "/home/pallasting/.rustup/toolchains/stable-x86_64-unknown-linux-gnu"
    )
    _adapter_require_directory(canonical_toolchain, 0o700)
    _adapter_require_directory(stable_toolchain, 0o700)
    for relative in (
        pathlib.PurePosixPath("."),
        pathlib.PurePosixPath("bin/cargo"),
        pathlib.PurePosixPath("bin/rustc"),
        pathlib.PurePosixPath("bin/rustdoc"),
        pathlib.PurePosixPath("bin/rustfmt"),
        pathlib.PurePosixPath("lib/rustlib/x86_64-unknown-linux-gnu/lib"),
    ):
        canonical_member = canonical_toolchain.joinpath(*relative.parts)
        stable_member = stable_toolchain.joinpath(*relative.parts)
        if not canonical_member.samefile(stable_member):
            _adapter_fail(f"stable Rust toolchain compatibility alias drift: {relative}")
        if relative.parts and relative.parts[0] == "bin":
            observed = stable_member.lstat()
            if (
                stable_member.is_symlink()
                or not stat.S_ISREG(observed.st_mode)
                or stat.S_IMODE(observed.st_mode) & 0o111 == 0
            ):
                _adapter_fail(f"stable Rust toolchain executable identity drift: {relative}")
    _adapter_validate_runtime_user_cargo_proxy_bin()
    _adapter_validate_runtime_cargo_seed(
        pathlib.Path("/root/.cargo"),
        label="runtime root Cargo",
        pristine=True,
        home_must_be_writable=True,
    )
    _adapter_validate_runtime_cargo_seed(
        pathlib.Path("/home/pallasting/.cargo"),
        label="runtime user Cargo",
        pristine=True,
        home_must_be_writable=False,
        initial_extra_entries=("bin",),
    )
    _adapter_validate_runtime_cargo_cross_home_identities()
    network_interfaces = []
    for line in pathlib.Path("/proc/net/dev").read_text(encoding="ascii").splitlines()[2:]:
        if ":" in line:
            network_interfaces.append(line.split(":", 1)[0].strip())
    if network_interfaces != ["lo"]:
        _adapter_fail("outer network namespace exposes a non-loopback interface")
    if len(pathlib.Path("/proc/net/route").read_text(encoding="ascii").splitlines()) != 1:
        _adapter_fail("outer network namespace exposes an IP route")
    process_status = {}
    for line in pathlib.Path("/proc/self/status").read_text(encoding="ascii").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            process_status[key] = value.strip()
    if (
        process_status.get("CapEff") != "0000000000000000"
        or process_status.get("CapBnd") != "0000000000000000"
    ):
        _adapter_fail("outer namespace retained capabilities")
    if process_status.get("NoNewPrivs") != "1":
        _adapter_fail("outer namespace did not set no_new_privs")


_LANDLOCK_CREATE_RULESET_VERSION = 1
_LANDLOCK_RULE_PATH_BENEATH = 1
_LANDLOCK_SCOPE_ABSTRACT_UNIX_SOCKET = 1 << 0
_LANDLOCK_SCOPE_SIGNAL = 1 << 1
_LANDLOCK_WRITE_ACCESS = (
    (1 << 1)  # WRITE_FILE
    | (1 << 4)  # REMOVE_DIR
    | (1 << 5)  # REMOVE_FILE
    | (1 << 6)  # MAKE_CHAR
    | (1 << 7)  # MAKE_DIR
    | (1 << 8)  # MAKE_REG
    | (1 << 9)  # MAKE_SOCK
    | (1 << 10)  # MAKE_FIFO
    | (1 << 11)  # MAKE_BLOCK
    | (1 << 12)  # MAKE_SYM
    | (1 << 13)  # REFER
    | (1 << 14)  # TRUNCATE
    | (1 << 15)  # IOCTL_DEV
)
_LANDLOCK_ALLOWED_PATH_ACCESS = _LANDLOCK_WRITE_ACCESS & ~(1 << 15)


def _adapter_landlock_buffer(payload: bytes) -> ctypes.Array[ctypes.c_char]:
    return ctypes.create_string_buffer(payload, len(payload))


def _adapter_apply_landlock_write_domain(allowed_paths: Sequence[pathlib.Path]) -> None:
    if os.uname().machine != "x86_64":
        _adapter_fail("Landlock syscall profile requires x86_64")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    abi = libc.syscall(444, 0, 0, _LANDLOCK_CREATE_RULESET_VERSION)
    if abi < 6:
        _adapter_fail("Landlock ABI 6 or newer is unavailable")
    ruleset_payload = _adapter_landlock_buffer(
        struct.pack(
            "=QQQ",
            _LANDLOCK_WRITE_ACCESS,
            0,
            _LANDLOCK_SCOPE_ABSTRACT_UNIX_SOCKET | _LANDLOCK_SCOPE_SIGNAL,
        )
    )
    ruleset_descriptor = libc.syscall(
        444,
        ctypes.byref(ruleset_payload),
        len(ruleset_payload),
        0,
    )
    if ruleset_descriptor < 0:
        error = ctypes.get_errno()
        _adapter_fail(f"cannot create Landlock ruleset: errno {error}")
    try:
        for path in allowed_paths:
            _adapter_require_directory(path, 0o700 if path != pathlib.Path("/tmp") else 0o1777)
            if path.resolve(strict=True) != path:
                _adapter_fail(f"Landlock write root is not canonical: {path}")
            path_descriptor = os.open(
                path,
                os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            )
            try:
                rule_payload = _adapter_landlock_buffer(
                    struct.pack("=Qi", _LANDLOCK_ALLOWED_PATH_ACCESS, path_descriptor)
                )
                if libc.syscall(
                    445,
                    ruleset_descriptor,
                    _LANDLOCK_RULE_PATH_BENEATH,
                    ctypes.byref(rule_payload),
                    0,
                ) != 0:
                    error = ctypes.get_errno()
                    _adapter_fail(f"cannot add Landlock write root {path}: errno {error}")
            finally:
                os.close(path_descriptor)
        null_path = pathlib.Path("/dev/null")
        null_observed = null_path.lstat()
        if null_path.is_symlink() or not stat.S_ISCHR(null_observed.st_mode):
            _adapter_fail("Landlock /dev/null identity drift")
        null_descriptor = os.open(
            null_path,
            os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            null_rule_payload = _adapter_landlock_buffer(
                struct.pack("=Qi", (1 << 1) | (1 << 14), null_descriptor)
            )
            if libc.syscall(
                445,
                ruleset_descriptor,
                _LANDLOCK_RULE_PATH_BENEATH,
                ctypes.byref(null_rule_payload),
                0,
            ) != 0:
                error = ctypes.get_errno()
                _adapter_fail(f"cannot add Landlock /dev/null rule: errno {error}")
        finally:
            os.close(null_descriptor)
        if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
            error = ctypes.get_errno()
            _adapter_fail(f"cannot retain no_new_privs for Landlock: errno {error}")
        if libc.syscall(446, ruleset_descriptor, 0) != 0:
            error = ctypes.get_errno()
            _adapter_fail(f"cannot enforce Landlock write domain: errno {error}")
    finally:
        os.close(ruleset_descriptor)


def _adapter_open_descriptor_set() -> set[int]:
    descriptors: set[int] = set()
    for member in os.listdir("/proc/self/fd"):
        if not member.isdigit() or int(member) <= 2:
            continue
        descriptor = int(member)
        try:
            os.readlink(f"/proc/self/fd/{descriptor}")
        except FileNotFoundError:
            continue
        descriptors.add(descriptor)
    return descriptors


def _adapter_close_inherited_descriptors() -> None:
    for member in os.listdir("/proc/self/fd"):
        if not member.isdigit() or int(member) <= 2:
            continue
        try:
            os.close(int(member))
        except OSError:
            pass


def _adapter_validate_standard_descriptors(
    allowed_write_roots: Sequence[pathlib.Path],
) -> None:
    for root in allowed_write_roots:
        observed = root.lstat()
        if root.is_symlink() or not stat.S_ISDIR(observed.st_mode) or root.resolve(strict=True) != root:
            _adapter_fail(f"payload write root is not canonical: {root}")
    stdin_observed = os.fstat(0)
    null_observed = pathlib.Path("/dev/null").stat()
    if (
        not stat.S_ISCHR(stdin_observed.st_mode)
        or stdin_observed.st_rdev != null_observed.st_rdev
        or fcntl.fcntl(0, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY
    ):
        _adapter_fail("payload stdin is not read-only /dev/null")
    for descriptor in (1, 2):
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            _adapter_fail(f"payload descriptor {descriptor} is not a regular stage log")
        access_mode = fcntl.fcntl(descriptor, fcntl.F_GETFL) & os.O_ACCMODE
        if access_mode not in (os.O_WRONLY, os.O_RDWR):
            _adapter_fail(f"payload descriptor {descriptor} is not writable")
        target_text = os.readlink(f"/proc/self/fd/{descriptor}")
        target = pathlib.Path(target_text)
        if not target.is_absolute() or " (deleted)" in target_text:
            _adapter_fail(f"payload descriptor {descriptor} target is not canonical")
        resolved = target.resolve(strict=True)
        if not any(resolved == root or root in resolved.parents for root in allowed_write_roots):
            _adapter_fail(f"payload descriptor {descriptor} escapes its write domain")
        rebound = resolved.stat()
        if (
            not stat.S_ISREG(rebound.st_mode)
            or (rebound.st_dev, rebound.st_ino) != (observed.st_dev, observed.st_ino)
        ):
            _adapter_fail(f"payload descriptor {descriptor} path identity drift")


def _adapter_process_catalog() -> tuple[tuple[int, int], ...]:
    processes: list[tuple[int, int]] = []
    for member in sorted(pathlib.Path("/proc").iterdir(), key=lambda item: item.name):
        if not member.name.isdigit():
            continue
        try:
            raw = (member / "stat").read_text(encoding="ascii")
        except (FileNotFoundError, ProcessLookupError):
            continue
        closing = raw.rfind(")")
        if closing < 0:
            _adapter_fail("malformed process stat row")
        fields = raw[closing + 2 :].split()
        if len(fields) < 20:
            _adapter_fail("short process stat row")
        processes.append((int(member.name), int(fields[19])))
    return tuple(processes)


def _adapter_forbidden_metadata_catalog(
    excluded_roots: Sequence[pathlib.Path],
) -> tuple[int, str]:
    roots = (
        pathlib.Path("/Data/CascadeProjects"),
        pathlib.Path("/home/pallasting"),
        pathlib.Path("/tmp"),
        pathlib.Path("/run"),
        pathlib.Path("/root"),
        pathlib.Path("/mnt"),
        pathlib.Path("/dev"),
    )
    excluded = {path.as_posix() for path in excluded_roots}
    digest = hashlib.sha256()
    count = 0

    def visit(path: pathlib.Path) -> None:
        nonlocal count
        if path.as_posix() in excluded:
            return
        observed = path.lstat()
        link_target = os.readlink(path) if stat.S_ISLNK(observed.st_mode) else ""
        row = (
            f"{path.as_posix()}\t{observed.st_dev}\t{observed.st_ino}\t"
            f"{observed.st_mode}\t{observed.st_uid}\t{observed.st_gid}\t"
            f"{observed.st_nlink}\t{observed.st_size}\t{observed.st_mtime_ns}\t"
            f"{observed.st_ctime_ns}\t{observed.st_rdev}\t{link_target}\n"
        ).encode("utf-8")
        digest.update(row)
        count += 1
        if stat.S_ISDIR(observed.st_mode):
            with os.scandir(path) as iterator:
                children = sorted(iterator, key=lambda item: os.fsencode(item.name))
            for child in children:
                visit(path / child.name)

    for root in roots:
        visit(root)
    return count, digest.hexdigest()


def _adapter_observe_retired_sparse_index_tree(
    index_container: pathlib.Path,
    expected_device: int,
    expected_directory_mode: int,
) -> dict[str, Any]:
    """Catalog one stage-local sparse index without following any link."""
    owner = os.geteuid()
    group = os.getegid()
    container_observed = index_container.lstat()
    if (
        index_container.is_symlink()
        or not stat.S_ISDIR(container_observed.st_mode)
        or stat.S_IMODE(container_observed.st_mode) != 0o700
        or container_observed.st_uid != owner
        or container_observed.st_gid != group
        or container_observed.st_dev != expected_device
        or index_container.resolve(strict=True) != index_container
    ):
        _adapter_fail(f"retired sparse-index container identity drift: {index_container}")
    registry_name = "index.crates.io-1949cf8c6b5b557f"
    children = sorted(os.listdir(index_container), key=os.fsencode)
    if children != [registry_name]:
        _adapter_fail(f"retired sparse-index container member drift: {index_container}")
    index_root = index_container / registry_name
    root_observed = index_root.lstat()
    if (
        index_root.is_symlink()
        or not stat.S_ISDIR(root_observed.st_mode)
        or root_observed.st_dev != expected_device
        or root_observed.st_uid != owner
        or root_observed.st_gid != group
        or stat.S_IMODE(root_observed.st_mode) != expected_directory_mode
    ):
        _adapter_fail(f"retired sparse-index root identity drift: {index_root}")

    rows: list[bytes] = []
    total_byte_count = 0
    for directory_text, directory_names, file_names, directory_descriptor in os.fwalk(
        index_root,
        topdown=True,
        follow_symlinks=False,
    ):
        directory = pathlib.Path(directory_text)
        directory_observed = os.fstat(directory_descriptor)
        if (
            not stat.S_ISDIR(directory_observed.st_mode)
            or directory_observed.st_dev != expected_device
            or directory_observed.st_uid != owner
            or directory_observed.st_gid != group
            or stat.S_IMODE(directory_observed.st_mode) != expected_directory_mode
        ):
            _adapter_fail(f"retired sparse-index directory identity drift: {directory}")
        if not directory_names and not file_names:
            _adapter_fail(f"retired sparse-index contains an empty directory: {directory}")
        for name in directory_names:
            child = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
            if (
                not stat.S_ISDIR(child.st_mode)
                or child.st_dev != expected_device
                or child.st_uid != owner
                or child.st_gid != group
                or stat.S_IMODE(child.st_mode) != expected_directory_mode
            ):
                _adapter_fail(f"retired sparse-index special directory: {directory / name}")
        for name in file_names:
            before = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_dev != expected_device
                or before.st_uid != owner
                or before.st_gid != group
                or before.st_nlink != 1
                or stat.S_IMODE(before.st_mode) != 0o444
            ):
                _adapter_fail(f"retired sparse-index special or mutable file: {directory / name}")
            descriptor = os.open(
                name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=directory_descriptor,
            )
            try:
                opened = os.fstat(descriptor)
                identity = (
                    before.st_dev,
                    before.st_ino,
                    before.st_mode,
                    before.st_uid,
                    before.st_gid,
                    before.st_nlink,
                    before.st_size,
                    before.st_mtime_ns,
                )
                if (
                    opened.st_dev,
                    opened.st_ino,
                    opened.st_mode,
                    opened.st_uid,
                    opened.st_gid,
                    opened.st_nlink,
                    opened.st_size,
                    opened.st_mtime_ns,
                ) != identity:
                    _adapter_fail(f"retired sparse-index file identity raced: {directory / name}")
                digest = hashlib.sha256()
                observed_size = 0
                while True:
                    block = os.read(descriptor, 1024 * 1024)
                    if not block:
                        break
                    digest.update(block)
                    observed_size += len(block)
                after = os.fstat(descriptor)
                if (
                    after.st_dev,
                    after.st_ino,
                    after.st_mode,
                    after.st_uid,
                    after.st_gid,
                    after.st_nlink,
                    after.st_size,
                    after.st_mtime_ns,
                ) != identity or observed_size != before.st_size:
                    _adapter_fail(f"retired sparse-index file changed while reading: {directory / name}")
            finally:
                os.close(descriptor)
            relative = (directory.relative_to(index_root) / name).as_posix()
            if not relative.isascii():
                _adapter_fail(f"non-ASCII retired sparse-index path: {relative}")
            rows.append(
                f"{relative}\t{before.st_size}\t{digest.hexdigest()}\n".encode("ascii")
            )
            total_byte_count += before.st_size
    rows.sort(key=lambda row: row.split(b"\t", 1)[0])
    return {
        "catalog_sha256": hashlib.sha256(b"".join(rows)).hexdigest(),
        "file_count": len(rows),
        "total_byte_count": total_byte_count,
    }


def _adapter_prepare_retired_sparse_index_tree_for_cleanup(
    index_container: pathlib.Path,
    expected_device: int,
    expected_catalog: Mapping[str, Any],
) -> None:
    """Make only verified, retired index directories removable by frozen gates."""
    expected_keys = {"catalog_sha256", "file_count", "total_byte_count"}
    if set(expected_catalog) != expected_keys:
        _adapter_fail("retired sparse-index expected catalog shape drift")
    before = _adapter_observe_retired_sparse_index_tree(
        index_container,
        expected_device,
        0o555,
    )
    if before != dict(expected_catalog):
        _adapter_fail(f"retired sparse-index catalog drift: {index_container}")
    index_root = index_container / "index.crates.io-1949cf8c6b5b557f"
    for _, _, _, directory_descriptor in os.fwalk(
        index_root,
        topdown=False,
        follow_symlinks=False,
    ):
        observed = os.fstat(directory_descriptor)
        if (
            not stat.S_ISDIR(observed.st_mode)
            or observed.st_dev != expected_device
            or observed.st_uid != os.geteuid()
            or observed.st_gid != os.getegid()
            or stat.S_IMODE(observed.st_mode) != 0o555
        ):
            _adapter_fail("retired sparse-index directory changed before cleanup preparation")
        os.fchmod(directory_descriptor, 0o700)
        os.fsync(directory_descriptor)
    after = _adapter_observe_retired_sparse_index_tree(
        index_container,
        expected_device,
        0o700,
    )
    if after != dict(expected_catalog):
        _adapter_fail(f"retired sparse-index cleanup catalog drift: {index_container}")


def _adapter_prepare_stage_retired_sparse_indexes_for_cleanup(
    scratch: pathlib.Path,
) -> None:
    scratch_observed = scratch.lstat()
    if (
        scratch.is_symlink()
        or not stat.S_ISDIR(scratch_observed.st_mode)
        or scratch.resolve(strict=True) != scratch
    ):
        _adapter_fail("retired sparse-index stage scratch identity drift")
    for relative in (
        pathlib.PurePosixPath("cargo-seed-registry/index"),
        pathlib.PurePosixPath("cargo-home/registry/index"),
    ):
        index_container = scratch.joinpath(*relative.parts)
        try:
            index_container.relative_to(scratch)
        except ValueError:
            _adapter_fail("retired sparse-index cleanup path escaped stage scratch")
        _adapter_prepare_retired_sparse_index_tree_for_cleanup(
            index_container,
            scratch_observed.st_dev,
            PREDECESSOR_SPARSE_INDEX_CATALOG,
        )


def _adapter_prepare_owned_registry_tree_for_removal(registry: pathlib.Path) -> int:
    """Add owner rwx only to real directories in one verified copied registry."""
    owner = os.geteuid()
    group = os.getegid()
    supplied = registry.absolute()
    observed_root = supplied.lstat()
    if (
        supplied.is_symlink()
        or not stat.S_ISDIR(observed_root.st_mode)
        or supplied.resolve(strict=True) != supplied
        or observed_root.st_uid != owner
        or observed_root.st_gid != group
        or stat.S_IMODE(observed_root.st_mode) & 0o500 != 0o500
        or stat.S_IMODE(observed_root.st_mode) & 0o022
        or observed_root.st_mode & 0o7000
    ):
        _adapter_fail(f"frozen-gate copied registry identity drift: {supplied}")
    expected_device = observed_root.st_dev
    expected_root_identity = (observed_root.st_dev, observed_root.st_ino)
    directory_identities: set[tuple[int, int]] = set()
    directory_count = 0
    for directory_text, directory_names, _, directory_descriptor in os.fwalk(
        supplied,
        topdown=False,
        onerror=lambda error: _adapter_fail(
            f"frozen-gate cleanup traversal failed: {error}"
        ),
        follow_symlinks=False,
    ):
        directory = pathlib.Path(directory_text)
        try:
            directory.relative_to(supplied)
        except ValueError:
            _adapter_fail("frozen-gate cleanup traversal escaped copied registry")
        before = os.fstat(directory_descriptor)
        identity = (before.st_dev, before.st_ino)
        if (
            not stat.S_ISDIR(before.st_mode)
            or before.st_dev != expected_device
            or before.st_uid != owner
            or before.st_gid != group
            or stat.S_IMODE(before.st_mode) & 0o022
            or before.st_mode & 0o7000
            or identity in directory_identities
        ):
            _adapter_fail(f"frozen-gate cleanup directory identity drift: {directory}")
        directory_identities.add(identity)
        for name in directory_names:
            child = os.stat(
                name,
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
            if stat.S_ISLNK(child.st_mode):
                continue
            if (
                not stat.S_ISDIR(child.st_mode)
                or child.st_dev != expected_device
                or child.st_uid != owner
                or child.st_gid != group
                or stat.S_IMODE(child.st_mode) & 0o022
                or child.st_mode & 0o7000
            ):
                _adapter_fail(f"frozen-gate cleanup child identity drift: {directory / name}")
        os.fchmod(directory_descriptor, stat.S_IMODE(before.st_mode) | 0o700)
        after = os.fstat(directory_descriptor)
        if (
            (after.st_dev, after.st_ino) != identity
            or after.st_uid != owner
            or after.st_gid != group
            or stat.S_IMODE(after.st_mode) != (stat.S_IMODE(before.st_mode) | 0o700)
        ):
            _adapter_fail(f"frozen-gate cleanup directory raced: {directory}")
        directory_count += 1
    after_root = supplied.lstat()
    if (
        (after_root.st_dev, after_root.st_ino) != expected_root_identity
        or after_root.st_uid != owner
        or after_root.st_gid != group
        or stat.S_IMODE(after_root.st_mode)
        != (stat.S_IMODE(observed_root.st_mode) | 0o700)
        or expected_root_identity not in directory_identities
        or directory_count != len(directory_identities)
    ):
        _adapter_fail("frozen-gate copied registry changed during cleanup preparation")
    return directory_count


def _adapter_validate_gnurm_cleanup_launcher() -> None:
    launcher = pathlib.Path("/usr/bin/gnurm")
    observed = launcher.lstat()
    if (
        launcher.is_symlink()
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_uid != 0
        or observed.st_gid != 0
        or observed.st_nlink != 1
        or stat.S_IMODE(observed.st_mode) != 0o500
        or launcher.read_bytes() != PREDECESSOR_GNURM_CLEANUP_LAUNCHER
        or not os.statvfs(launcher).f_flag & os.ST_RDONLY
    ):
        _adapter_fail("frozen-gate gnurm cleanup launcher identity drift")
    rm_alias = pathlib.Path("/usr/bin/rm")
    alias_observed = rm_alias.lstat()
    bin_observed = pathlib.Path("/usr/bin").lstat()
    if (
        not stat.S_ISLNK(alias_observed.st_mode)
        or alias_observed.st_uid != bin_observed.st_uid
        or alias_observed.st_gid != bin_observed.st_gid
        or alias_observed.st_nlink != 1
        or stat.S_IMODE(alias_observed.st_mode) != 0o777
        or os.readlink(rm_alias) != "gnurm"
        or not rm_alias.samefile(launcher)
        or not os.statvfs(rm_alias).f_flag & os.ST_RDONLY
    ):
        _adapter_fail("frozen-gate rm alias does not resolve to the pinned dispatcher")
    real_rm = pathlib.Path("/run/a1-real-gnurm")
    real_observed = real_rm.lstat()
    if (
        real_rm.is_symlink()
        or not stat.S_ISREG(real_observed.st_mode)
        or real_observed.st_uid != 0
        or real_observed.st_gid != 0
        or real_observed.st_nlink != 1
        or stat.S_IMODE(real_observed.st_mode) != 0o755
        or not os.statvfs(real_rm).f_flag & os.ST_RDONLY
        or hashlib.sha256(real_rm.read_bytes()).hexdigest()
        != PREDECESSOR_REAL_GNURM_SHA256
        or launcher.samefile(real_rm)
    ):
        _adapter_fail("pinned real GNURM identity drift")


def run_predecessor_gnurm_cleanup_adapter(arguments: Sequence[str]) -> NoReturn:
    """Dispatch ambient rm; prepare only exact frozen S15/S16 trap cleanup."""
    exact_arguments = list(arguments)
    if os.geteuid() != 0 or os.getegid() != 0:
        _adapter_fail("frozen-gate gnurm adapter identity is not root-mapped")
    _adapter_validate_gnurm_cleanup_launcher()
    if (
        len(exact_arguments) != 3
        or exact_arguments[:2] != ["-rf", "--"]
        or re.fullmatch(
            r"/Data/CascadeProjects/\.ab-gate-tmp/(s15|s16)-gate\.[A-Za-z0-9]{8}",
            exact_arguments[2] if len(exact_arguments) == 3 else "",
        )
        is None
    ):
        os.execve(
            "/run/a1-real-gnurm",
            ["/usr/bin/rm", *exact_arguments],
            dict(os.environ),
        )
    scratch_text = exact_arguments[2]
    parent = pathlib.Path("/Data/CascadeProjects/.ab-gate-tmp")
    _adapter_require_directory(parent, 0o700)
    if parent.resolve(strict=True) != parent:
        _adapter_fail("frozen-gate cleanup parent is not canonical")
    scratch = pathlib.Path(scratch_text)
    if scratch.parent != parent:
        _adapter_fail("frozen-gate cleanup scratch parent drift")
    if not scratch.exists() and not scratch.is_symlink():
        os.execve(
            "/run/a1-real-gnurm",
            ["/usr/bin/gnurm", *exact_arguments],
            dict(os.environ),
        )
    _adapter_require_directory(scratch, 0o700)
    if (
        scratch.resolve(strict=True) != scratch
        or scratch.lstat().st_dev != parent.lstat().st_dev
    ):
        _adapter_fail("frozen-gate cleanup scratch identity drift")
    cargo_home = scratch / "cargo-home"
    if cargo_home.exists() or cargo_home.is_symlink():
        observed_cargo_home = cargo_home.lstat()
        if (
            cargo_home.is_symlink()
            or not stat.S_ISDIR(observed_cargo_home.st_mode)
            or cargo_home.resolve(strict=True) != cargo_home
            or observed_cargo_home.st_dev != scratch.lstat().st_dev
            or observed_cargo_home.st_uid != os.geteuid()
            or observed_cargo_home.st_gid != os.getegid()
            or stat.S_IMODE(observed_cargo_home.st_mode) != 0o700
        ):
            _adapter_fail("frozen-gate cleanup Cargo home identity drift")
    _adapter_apply_landlock_write_domain([parent])
    registry = cargo_home / "registry"
    if registry.exists() or registry.is_symlink():
        if registry.is_symlink() or not registry.is_dir():
            _adapter_fail("frozen-gate cleanup copied registry is not a real directory")
        _adapter_prepare_owned_registry_tree_for_removal(registry)
    os.execve(
        "/run/a1-real-gnurm",
        ["/usr/bin/gnurm", *exact_arguments],
        dict(os.environ),
    )


def _adapter_run_landlocked_payload(
    command: Sequence[str],
    environment: Mapping[str, str],
    working_directory: pathlib.Path,
    allowed_write_roots: Sequence[pathlib.Path],
) -> int:
    _adapter_validate_standard_descriptors(allowed_write_roots)
    forbidden_before = _adapter_forbidden_metadata_catalog(allowed_write_roots)
    processes_before = _adapter_process_catalog()
    child = os.fork()
    if child == 0:
        try:
            _adapter_close_inherited_descriptors()
            os.chdir(working_directory)
            _adapter_apply_landlock_write_domain(allowed_write_roots)
            inherited = _adapter_open_descriptor_set()
            if inherited:
                _adapter_fail(f"payload inherited unexpected descriptors: {sorted(inherited)}")
            os.execve(command[0], list(command), dict(environment))
        except BaseException as exc:
            try:
                os.write(2, f"A1 Landlock payload setup failed: {exc}\n".encode("utf-8"))
            finally:
                os._exit(125)
    while True:
        try:
            waited, status = os.waitpid(child, 0)
            break
        except InterruptedError:
            continue
    if waited != child:
        _adapter_fail("Landlock payload wait identity drift")
    if _adapter_process_catalog() != processes_before:
        _adapter_fail("Landlock payload left a process behind")
    if _adapter_forbidden_metadata_catalog(allowed_write_roots) != forbidden_before:
        _adapter_fail("Landlock payload changed a forbidden filesystem node")
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    _adapter_fail("Landlock payload returned an unsupported wait status")


def _adapter_write_receipt(stage: str, arguments: Sequence[str]) -> None:
    control = pathlib.Path("/mnt")
    _adapter_require_directory(control, 0o700)
    rows = (
        f"stage\t{stage}\n"
        "mode\tFLATTENED_ALREADY_SANDBOXED_PREDECESSOR_REPLAY\n"
        f"argv_sha256\t{hashlib.sha256(os.fsencode(chr(0).join(arguments))).hexdigest()}\n"
        "gate\tPASS_STRICT_ALLOWLIST_AND_LANDLOCK_BEFORE_EXEC\n"
    ).encode("ascii")
    directory_descriptor = os.open(
        control,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        descriptor = os.open(
            f"flattened-{stage}.receipt",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=directory_descriptor,
        )
        try:
            view = memoryview(rows)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    _adapter_fail("flatten receipt write made no progress")
                view = view[written:]
            os.fchmod(descriptor, 0o600)
            os.fsync(descriptor)
            observed = os.fstat(descriptor)
            if (
                not stat.S_ISREG(observed.st_mode)
                or stat.S_IMODE(observed.st_mode) != 0o600
                or observed.st_uid != os.geteuid()
                or observed.st_gid != os.getegid()
                or observed.st_nlink != 1
            ):
                _adapter_fail("flatten receipt identity drift")
        finally:
            os.close(descriptor)
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def _adapter_run_runtime_predecessor(arguments: list[str]) -> NoReturn:
    if arguments.count("--chdir") != 1:
        _adapter_fail("runtime predecessor chdir is ambiguous")
    chdir_index = arguments.index("--chdir")
    if chdir_index + 2 >= len(arguments):
        _adapter_fail("runtime predecessor payload is absent")
    predecessor_repo = arguments[chdir_index + 1]
    runtime_root_match = re.fullmatch(
        r"(/tmp/agent-bridge-runner-runtime-prerequisite-evidence-validator-v1\.[A-Za-z0-9]{6})/predecessor-repo",
        predecessor_repo,
    )
    if runtime_root_match is None:
        _adapter_fail("runtime predecessor repository path is invalid")
    runtime_root = runtime_root_match.group(1)
    if "--bind" not in arguments:
        _adapter_fail("runtime predecessor cache bind is absent")
    try:
        cache_destination_index = arguments.index("/home/pallasting/.cache")
    except ValueError:
        _adapter_fail("runtime predecessor cache destination is absent")
    if cache_destination_index < 2 or arguments[cache_destination_index - 2] != "--bind":
        _adapter_fail("runtime predecessor cache bind is malformed")
    predecessor_cache = arguments[cache_destination_index - 1]
    if re.fullmatch(
        r"/Data/CascadeProjects/\.ab-gate-tmp/"
        r"runner-runtime-evidence-offline-boundary-v1\.[A-Za-z0-9]{6}/"
        r"\.ab-gate-tmp/runner-runtime-evidence-predecessor-cache\.[A-Za-z0-9]{6}",
        predecessor_cache,
    ) is None:
        _adapter_fail("runtime predecessor cache source is invalid")
    predecessor_gate = (
        f"{predecessor_repo}/scripts/"
        "check-biocortex-ab-track-b-reference-provider-fault-injection-runner-"
        "runtime-prerequisite-evidence-plan-and-owner-decision-preregistration-v1-pack.sh"
    )
    expected_arguments = [
        "--die-with-parent",
        "--new-session",
        "--unshare-net",
        "--ro-bind",
        "/",
        "/",
        "--dev-bind",
        "/dev",
        "/dev",
        "--proc",
        "/proc",
        "--bind",
        "/tmp",
        "/tmp",
        "--bind",
        predecessor_cache,
        "/home/pallasting/.cache",
        "--chdir",
        predecessor_repo,
        predecessor_gate,
        "full-replay",
    ]
    if arguments != expected_arguments:
        _adapter_fail("runtime predecessor argv is outside the exact allowlist")
    for variable in (
        "LD_AUDIT",
        "LD_LIBRARY_PATH",
        "LD_PRELOAD",
        "PYTHONPATH",
        "PYTHONHOME",
    ):
        if variable in os.environ:
            _adapter_fail(f"forbidden environment variable: {variable}")
    if os.environ.get("PATH") != "/usr/bin:/bin:/home/pallasting/.cargo/bin":
        _adapter_fail("runtime predecessor PATH drift")
    source = pathlib.Path(predecessor_cache)
    _adapter_require_directory(source, 0o700)
    if source.resolve(strict=True).as_posix() != predecessor_cache or any(source.iterdir()):
        _adapter_fail("runtime predecessor cache is not canonical and empty")
    private_cache = pathlib.Path("/home/pallasting/.cache")
    _adapter_require_directory(private_cache, 0o700)
    if any(private_cache.iterdir()):
        _adapter_fail("private compatibility cache is not empty")
    backup = pathlib.Path("/home/pallasting/.cache.a1-empty")
    if backup.exists() or backup.is_symlink():
        _adapter_fail("private cache backup path is occupied")
    os.rename(private_cache, backup)
    os.symlink(predecessor_cache, private_cache)
    result: int | None = None
    try:
        if not private_cache.is_symlink() or os.readlink(private_cache) != predecessor_cache:
            _adapter_fail("private cache compatibility link drift")
        _adapter_write_receipt("runtime-prerequisite", arguments)
        result = _adapter_run_landlocked_payload(
            [predecessor_gate, "full-replay"],
            dict(os.environ),
            pathlib.Path(predecessor_repo),
            [
                pathlib.Path("/tmp"),
                source,
                pathlib.Path("/root/.cargo"),
                pathlib.Path("/home/pallasting/.cargo"),
            ],
        )
    finally:
        if not private_cache.is_symlink() or os.readlink(private_cache) != predecessor_cache:
            _adapter_fail("private cache compatibility link changed during replay")
        private_cache.unlink()
        os.rename(backup, private_cache)
    _adapter_require_directory(private_cache, 0o700)
    if any(private_cache.iterdir()) or any(source.iterdir()):
        _adapter_fail("runtime predecessor cache residue observed")
    _adapter_validate_runtime_user_cargo_proxy_bin()
    _adapter_validate_runtime_cargo_seed(
        pathlib.Path("/root/.cargo"),
        label="runtime root Cargo",
        pristine=False,
        home_must_be_writable=True,
    )
    _adapter_validate_runtime_cargo_seed(
        pathlib.Path("/home/pallasting/.cargo"),
        label="runtime user Cargo",
        pristine=False,
        home_must_be_writable=False,
        initial_extra_entries=("bin",),
    )
    _adapter_validate_runtime_cargo_cross_home_identities()
    raise SystemExit(result if result is not None else 125)


def run_predecessor_bwrap_flatten_adapter(arguments: Sequence[str]) -> NoReturn:
    exact_arguments = list(arguments)
    _adapter_validate_outer_namespace()
    if "/home/pallasting/.cache" in exact_arguments:
        _adapter_run_runtime_predecessor(exact_arguments)

    try:
        chdir_index = exact_arguments.index("--chdir")
    except ValueError:
        _adapter_fail("missing chdir")
    if exact_arguments.count("--chdir") != 1 or chdir_index + 1 >= len(exact_arguments):
        _adapter_fail("ambiguous chdir")
    head = exact_arguments[chdir_index + 1]
    if not head.endswith("/head"):
        _adapter_fail("unexpected replay working directory")
    scratch = head[:-5]
    match = re.fullmatch(
        r"/Data/CascadeProjects/\.ab-(s21a|s20b|s20)-gate\.[A-Za-z0-9]{8}",
        scratch,
    )
    if match is None:
        _adapter_fail("unexpected replay scratch path")
    stage = match.group(1)
    specifications = {
        "s21a": (
            "temporal-evidence-s21a-owned-lab-final-refreeze-admission-synthetic",
            "s21a_",
            "AB_S21A_TEST_SCRATCH",
            "s21a-scratch",
            ["--ro-bind", "/", "/", "--bind", scratch, scratch],
        ),
        "s20b": (
            "temporal-evidence-s20b-owned-lab-rich-packet-validators-synthetic",
            "trusted_controller_orchestration",
            "AB_S20_TEST_SCRATCH",
            "s20b-sqlite",
            ["--bind", "/", "/"],
        ),
        "s20": (
            "temporal-evidence-s20-owned-lab-trusted-controller-orchestration-synthetic",
            "s20_",
            "AB_S20_TEST_SCRATCH",
            "s20-sqlite",
            ["--bind", "/", "/"],
        ),
    }
    feature, test_filter, scratch_variable, test_scratch_name, mount_arguments = specifications[stage]
    expected_arguments = [
        "--die-with-parent",
        "--unshare-net",
        *mount_arguments,
        "--dev",
        "/dev",
        "--chdir",
        head,
        "/usr/bin/time",
        "-v",
        "-o",
        f"{scratch}/rust-time.log",
        "/home/pallasting/.cargo/bin/cargo",
        "test",
        "--locked",
        "--offline",
        "-p",
        "ab-store",
        "--lib",
        "--no-default-features",
        "--features",
        feature,
        "-j1",
        test_filter,
        "--",
        "--test-threads=1",
    ]
    if exact_arguments != expected_arguments:
        _adapter_fail("argv is outside the exact three-command allowlist")

    expected_environment = {
        "PATH": "/usr/bin:/bin:/home/pallasting/.cargo/bin",
        "HOME": f"{scratch}/home",
        "TMPDIR": f"{scratch}/cargo-tmp",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "RUSTUP_HOME": "/home/pallasting/.rustup",
        "CARGO_HOME": f"{scratch}/cargo-home",
        "CARGO_TARGET_DIR": f"{scratch}/cargo-target",
        "CARGO_BUILD_JOBS": "1",
        "CARGO_INCREMENTAL": "0",
        "CARGO_NET_OFFLINE": "true",
        "CARGO_TERM_COLOR": "never",
        "CARGO_PROFILE_DEV_CODEGEN_UNITS": "256",
        "CARGO_PROFILE_TEST_CODEGEN_UNITS": "256",
        "CARGO_PROFILE_DEV_DEBUG": "0",
        "CARGO_PROFILE_TEST_DEBUG": "0",
        "RUSTC": "/home/pallasting/.cargo/bin/rustc",
        "RUSTFLAGS": "-C debuginfo=0",
        "RUST_TEST_THREADS": "1",
        "TOKIO_WORKER_THREADS": "1",
        "MALLOC_ARENA_MAX": "2",
        scratch_variable: f"{scratch}/{test_scratch_name}",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }
    if dict(os.environ) != expected_environment:
        _adapter_fail("environment is outside the exact stage allowlist")

    _adapter_require_directory(pathlib.Path(scratch), 0o700)
    if pathlib.Path(scratch).resolve(strict=True).as_posix() != scratch:
        _adapter_fail("replay scratch is not canonical")
    if not pathlib.Path(head).is_dir() or pathlib.Path(head).is_symlink():
        _adapter_fail("replay working directory is invalid")
    _adapter_write_receipt(stage, exact_arguments)
    result = _adapter_run_landlocked_payload(
        expected_arguments[chdir_index + 2 :],
        expected_environment,
        pathlib.Path(head),
        [pathlib.Path(scratch)],
    )
    _adapter_prepare_stage_retired_sparse_indexes_for_cleanup(pathlib.Path(scratch))
    raise SystemExit(result)


def fixed_tool_environment() -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C", "TZ": "UTC"}


def verbose_version_fields(binary: pathlib.Path) -> dict[str, str]:
    output = run_command([binary, "--version", "--verbose"], env=fixed_tool_environment()).stdout
    try:
        text = output.decode("ascii")
    except UnicodeDecodeError as exc:
        raise BuildError(f"non-ASCII verbose version output from {binary}") from exc
    fields: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if ": " in line:
            key, value = line.split(": ", 1)
            require(key not in fields, f"duplicate verbose version field from {binary}: {key}")
            fields[key] = value
    return fields


def toolchain_tree_catalog(root: pathlib.Path) -> dict[str, Any]:
    require(root.is_dir() and not root.is_symlink(), "toolchain tree root unavailable")
    entries: list[tuple[str, str, int, str]] = []
    total = 0
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        require(relative.isascii(), "non-ASCII toolchain tree path")
        observed = path.lstat()
        if stat.S_ISDIR(observed.st_mode):
            continue
        require(stat.S_ISREG(observed.st_mode), f"toolchain tree special member: {path}")
        digest = sha256_file(path)
        entries.append(
            (relative, f"{stat.S_IMODE(observed.st_mode):04o}", observed.st_size, digest)
        )
        total += observed.st_size
    entries.sort(key=lambda item: item[0].encode("ascii"))
    lines = [f"{relative}\t{mode}\t{size}\t{digest}\n".encode("ascii") for relative, mode, size, digest in entries]
    return {
        "catalog_digest_profile": (
            "FOR_EACH_BYTEWISE_ASCII_RELATIVE_POSIX_PATH_SORTED_REGULAR_FILE_"
            "RELATIVE_PATH_TAB_FOUR_DIGIT_OCTAL_MODE_TAB_DECIMAL_BYTE_COUNT_"
            "TAB_SHA256_LF_DIRECTORIES_EXCLUDED_SYMLINKS_FORBIDDEN"
        ),
        "catalog_sha256": sha256_bytes(b"".join(lines)),
        "file_count": len(entries),
        "total_byte_count": total,
    }


def copy_secure_toolchain(
    source_root: pathlib.Path,
    destination_root: pathlib.Path,
    expected_catalog: Mapping[str, Any],
) -> None:
    require(toolchain_tree_catalog(source_root) == dict(expected_catalog), "host toolchain tree drift before copy")
    create_private_dir(destination_root)
    for source_directory, directory_names, file_names in os.walk(
        source_root, topdown=True, followlinks=False
    ):
        source_directory_path = pathlib.Path(source_directory)
        relative_directory = source_directory_path.relative_to(source_root)
        destination_directory = destination_root / relative_directory
        directory_names.sort(key=lambda value: value.encode("ascii"))
        file_names.sort(key=lambda value: value.encode("ascii"))
        for name in directory_names:
            source = source_directory_path / name
            observed = source.lstat()
            require(stat.S_ISDIR(observed.st_mode) and not source.is_symlink(), f"toolchain copy directory invalid: {source}")
            create_private_dir(destination_directory / name)
        for name in file_names:
            source = source_directory_path / name
            before = source.lstat()
            require(stat.S_ISREG(before.st_mode) and not source.is_symlink(), f"toolchain copy member invalid: {source}")
            destination = destination_directory / name
            source_descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            destination_descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                stat.S_IMODE(before.st_mode),
            )
            try:
                while True:
                    block = os.read(source_descriptor, 1024 * 1024)
                    if not block:
                        break
                    view = memoryview(block)
                    while view:
                        written = os.write(destination_descriptor, view)
                        require(written > 0, "toolchain copy made no progress")
                        view = view[written:]
                os.fchmod(destination_descriptor, stat.S_IMODE(before.st_mode))
                os.fsync(destination_descriptor)
                source_after = os.fstat(source_descriptor)
                require(
                    (source_after.st_dev, source_after.st_ino, source_after.st_size, source_after.st_mtime_ns)
                    == (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns),
                    f"toolchain source changed during copy: {source}",
                )
            finally:
                os.close(destination_descriptor)
                os.close(source_descriptor)
    require(toolchain_tree_catalog(destination_root) == dict(expected_catalog), "secure toolchain copy digest drift")
    require(toolchain_tree_catalog(source_root) == dict(expected_catalog), "host toolchain tree drift after copy")


def rust_std_catalog(toolchain_root: pathlib.Path) -> tuple[str, int]:
    root = toolchain_root / "lib/rustlib/x86_64-unknown-linux-gnu/lib"
    require(root.is_dir() and not root.is_symlink(), "Rust standard-library root invalid")
    entries: list[tuple[str, pathlib.Path]] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        require(relative.isascii(), "non-ASCII Rust standard-library path")
        observed = path.lstat()
        if stat.S_ISDIR(observed.st_mode) or stat.S_ISLNK(observed.st_mode):
            continue
        require(stat.S_ISREG(observed.st_mode), f"special Rust standard-library member: {path}")
        entries.append((relative, path))
    entries.sort(key=lambda item: item[0].encode("ascii"))
    lines: list[bytes] = []
    for relative, path in entries:
        observed = path.lstat()
        line = f"{relative}\t{stat.S_IMODE(observed.st_mode):04o}\t{observed.st_size}\t{sha256_file(path)}\n"
        lines.append(line.encode("ascii"))
    return sha256_bytes(b"".join(lines)), len(entries)


def toolchain_file(toolchain_root: pathlib.Path, logical_path: str) -> pathlib.Path:
    prefix = "/rust-toolchain/"
    require(logical_path.startswith(prefix), f"invalid logical toolchain path: {logical_path}")
    path = toolchain_root / logical_path.removeprefix(prefix)
    require(path.exists() and not path.is_symlink(), f"toolchain input absent or symlinked: {path}")
    require(path.is_file(), f"toolchain input is not regular: {path}")
    return path


def observed_toolchain_manifest(
    source_root: pathlib.Path,
    registry_names: Sequence[str],
    toolchain_root: pathlib.Path = TOOLCHAIN_HOST_ROOT,
) -> tuple[dict[str, Any], list[tuple[pathlib.PurePosixPath, pathlib.Path]]]:
    require(toolchain_root.is_dir() and not toolchain_root.is_symlink(), "pinned toolchain root unavailable")
    cargo_logical = "/rust-toolchain/bin/cargo"
    rustc_logical = "/rust-toolchain/bin/rustc"
    cargo_path = toolchain_file(toolchain_root, cargo_logical)
    rustc_path = toolchain_file(toolchain_root, rustc_logical)
    cargo_fields = verbose_version_fields(cargo_path)
    rustc_fields = verbose_version_fields(rustc_path)
    require(cargo_fields.get("host") == "x86_64-unknown-linux-gnu", "Cargo host drift")
    require(rustc_fields.get("host") == "x86_64-unknown-linux-gnu", "rustc host drift")

    cargo_manifest_logical = "/rust-toolchain/lib/rustlib/manifest-cargo-x86_64-unknown-linux-gnu"
    rustc_manifest_logical = "/rust-toolchain/lib/rustlib/manifest-rustc-x86_64-unknown-linux-gnu"
    rust_std_manifest_logical = "/rust-toolchain/lib/rustlib/manifest-rust-std-x86_64-unknown-linux-gnu"
    std_catalog_sha, std_file_count = rust_std_catalog(toolchain_root)
    tree_catalog = toolchain_tree_catalog(toolchain_root)
    sparse, selected = sparse_index_observation(registry_names)

    crt_paths = (
        ("Scrt1.o", "/usr/lib/x86_64-linux-gnu/Scrt1.o"),
        ("crtbeginS.o", "/usr/lib/gcc/x86_64-linux-gnu/15/crtbeginS.o"),
        ("crtendS.o", "/usr/lib/gcc/x86_64-linux-gnu/15/crtendS.o"),
        ("crti.o", "/usr/lib/x86_64-linux-gnu/crti.o"),
        ("crtn.o", "/usr/lib/x86_64-linux-gnu/crtn.o"),
        ("ld-linux-x86-64.so.2", "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"),
        ("libc.so", "/usr/lib/x86_64-linux-gnu/libc.so"),
        ("libc.so.6", "/usr/lib/x86_64-linux-gnu/libc.so.6"),
        ("libgcc.a", "/usr/lib/gcc/x86_64-linux-gnu/15/libgcc.a"),
        ("libgcc_s.so", "/usr/lib/gcc/x86_64-linux-gnu/15/libgcc_s.so"),
        ("libgcc_s.so.1", "/usr/lib/x86_64-linux-gnu/libgcc_s.so.1"),
    )
    crt_catalog = []
    for logical_name, resolved_path in crt_paths:
        path = pathlib.Path(resolved_path)
        require(path.exists() and path.is_file(), f"link input absent: {resolved_path}")
        crt_catalog.append({"logical_name": logical_name, "resolved_path": resolved_path, "sha256": sha256_file(path)})

    runtime_paths = (
        ("ld-linux-x86-64.so.2", "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2", "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"),
        ("libc.so.6", "/usr/lib/x86_64-linux-gnu/libc.so.6", "/usr/lib/x86_64-linux-gnu/libc.so.6"),
        ("libdl.so.2", "/usr/lib/x86_64-linux-gnu/libdl.so.2", "/usr/lib/x86_64-linux-gnu/libdl.so.2"),
        ("libgcc_s.so.1", "/usr/lib/x86_64-linux-gnu/libgcc_s.so.1", "/usr/lib/x86_64-linux-gnu/libgcc_s.so.1"),
        ("libm.so.6", "/usr/lib/x86_64-linux-gnu/libm.so.6", "/usr/lib/x86_64-linux-gnu/libm.so.6"),
        ("libpthread.so.0", "/usr/lib/x86_64-linux-gnu/libpthread.so.0", "/usr/lib/x86_64-linux-gnu/libpthread.so.0"),
        ("librt.so.1", "/usr/lib/x86_64-linux-gnu/librt.so.1", "/usr/lib/x86_64-linux-gnu/librt.so.1"),
        ("libz.so.1", "/usr/lib/x86_64-linux-gnu/libz.so.1", "/usr/lib/x86_64-linux-gnu/libz.so.1.3.1"),
    )
    runtime_catalog = []
    for logical_name, requested, resolved in runtime_paths:
        require(os.path.realpath(requested) == resolved, f"runtime resolution drift: {requested}")
        runtime_catalog.append({
            "logical_name": logical_name,
            "requested_path": requested,
            "resolved_path": resolved,
            "sha256": sha256_file(pathlib.Path(resolved)),
        })

    host_runtime_logical = (
        "/rust-toolchain/lib/libLLVM-22-rust-1.96.0-stable.so",
        "/rust-toolchain/lib/libLLVM.so.22.1-rust-1.96.0-stable",
        "/rust-toolchain/lib/librustc_driver-4d71126a08f22b4a.so",
    )
    host_runtime_catalog = []
    for logical_path in host_runtime_logical:
        path = toolchain_file(toolchain_root, logical_path)
        observed = path.lstat()
        host_runtime_catalog.append({
            "mode_octal": f"{stat.S_IMODE(observed.st_mode):04o}",
            "path": logical_path,
            "sha256": sha256_file(path),
            "size_bytes": observed.st_size,
        })

    cc_path = pathlib.Path("/usr/bin/x86_64-linux-gnu-gcc-15")
    ar_path = pathlib.Path("/usr/bin/x86_64-linux-gnu-ar")
    collect2_path = pathlib.Path("/usr/libexec/gcc/x86_64-linux-gnu/15/collect2")
    ld_path = pathlib.Path("/usr/bin/x86_64-linux-gnu-ld.bfd")
    strip_path = pathlib.Path("/usr/bin/x86_64-linux-gnu-strip")
    for path in (cc_path, ar_path, collect2_path, ld_path, strip_path):
        require(path.exists() and path.is_file(), f"linker tool absent: {path}")
    cc_release = run_command([cc_path, "-dumpfullversion", "-dumpversion"], env=fixed_tool_environment()).stdout.decode("ascii").strip()
    require(re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", cc_release) is not None, "GCC release output malformed")
    binutils_outputs = [
        run_command([path, "--version"], env=fixed_tool_environment()).stdout.decode("ascii").splitlines()[0]
        for path in (ar_path, ld_path, strip_path)
    ]
    require(all(re.search(r"(?:^| )2\.46(?: |$)", line) for line in binutils_outputs), "binutils release drift")
    specs = run_command([cc_path, "-dumpspecs"], env=fixed_tool_environment()).stdout

    observed_manifest = {
        "canonicalization": CANONICALIZATION,
        "cargo": {
            "binary_path": cargo_logical,
            "binary_sha256": sha256_file(cargo_path),
            "commit_date": cargo_fields.get("commit-date"),
            "commit_hash": cargo_fields.get("commit-hash"),
            "manifest_path": cargo_manifest_logical,
            "manifest_sha256": sha256_file(toolchain_file(toolchain_root, cargo_manifest_logical)),
            "release": cargo_fields.get("release"),
        },
        "cargo_registry_sparse_index": sparse,
        "format_id": "agent_bridge.memory_temporal_owned_lab_role_build_toolchain_manifest_s21b_a1.v0",
        "host_triple": "x86_64-unknown-linux-gnu",
        "linker": {
            "ar_binary_path": os.fspath(ar_path),
            "ar_binary_sha256": sha256_file(ar_path),
            "binutils_release": "2.46",
            "cc_binary_path": os.fspath(cc_path),
            "cc_binary_sha256": sha256_file(cc_path),
            "cc_release": cc_release,
            "collect2_binary_path": os.fspath(collect2_path),
            "collect2_binary_sha256": sha256_file(collect2_path),
            "crt_and_link_input_catalog": crt_catalog,
            "gcc_specs_sha256": sha256_bytes(specs),
            "gcc_specs_sha256_profile": "SHA256_EXACT_STDOUT_BYTES_FROM_CC_BINARY_PATH_DUMPSPECS_ARGUMENT_IN_EMPTY_ENV_WITH_PATH_USR_BIN_BIN_LC_ALL_C_LANG_C_TZ_UTC",
            "ld_binary_path": os.fspath(ld_path),
            "ld_binary_sha256": sha256_file(ld_path),
            "strip_binary_path": os.fspath(strip_path),
            "strip_binary_sha256": sha256_file(strip_path),
        },
        "manifest_digest_contract": MANIFEST_DIGEST_CONTRACT,
        "nonclaims": {
            "cross_host_reproducibility_proved": False,
            "full_operating_system_supply_chain_attested": False,
            "hermetic_static_binary_produced": False,
            "provider_or_production_authority": False,
            "side_effects_unlocked": "NONE",
        },
        "rust_std": {
            "file_catalog_digest_contract": {
                "catalog_sha256_scope": "CONCATENATED_SORTED_CATALOG_LINES",
                "line_framing": "RELATIVE_POSIX_PATH_TAB_FOUR_DIGIT_LOWERCASE_OCTAL_S_IMODE_TAB_DECIMAL_BYTE_COUNT_TAB_64_LOWERCASE_HEX_SHA256_LF",
                "member_selection": "RECURSIVE_REGULAR_FILES_EXCLUDING_SYMLINKS",
                "relative_path_root": "/rust-toolchain/lib/rustlib/x86_64-unknown-linux-gnu/lib",
                "sort_order": "BYTEWISE_ASCII_RELATIVE_POSIX_PATH_ASCENDING",
                "terminal_lf": "ONE_PER_MEMBER",
            },
            "file_catalog_sha256": std_catalog_sha,
            "file_count": std_file_count,
            "manifest_path": rust_std_manifest_logical,
            "manifest_sha256": sha256_file(toolchain_file(toolchain_root, rust_std_manifest_logical)),
        },
        "rust_toolchain_toml_sha256": sha256_file(source_root / "rust-toolchain.toml"),
        "rustc": {
            "binary_path": rustc_logical,
            "binary_sha256": sha256_file(rustc_path),
            "commit_date": rustc_fields.get("commit-date"),
            "commit_hash": rustc_fields.get("commit-hash"),
            "llvm_version": rustc_fields.get("LLVM version"),
            "manifest_path": rustc_manifest_logical,
            "manifest_sha256": sha256_file(toolchain_file(toolchain_root, rustc_manifest_logical)),
            "release": rustc_fields.get("release"),
        },
        "rustc_host_runtime_catalog": host_runtime_catalog,
        "rustc_runtime_system_catalog": runtime_catalog,
        "target_triple": "x86_64-unknown-linux-gnu",
        "toolchain_root": "/rust-toolchain",
        "toolchain_tree_catalog": tree_catalog,
        "toolchain_version": "1.96.0-x86_64-unknown-linux-gnu",
    }
    return observed_manifest, selected


def schema_content_digest(root: pathlib.Path, repo: pathlib.Path, target: str, schema_set: Mapping[str, Any]) -> str:
    domain = str(schema_set["closure_digest_domain"]).encode("ascii")
    digest = hashlib.sha256()
    digest.update(struct.pack(">I", len(domain)))
    digest.update(domain)
    members = schema_set["members"]
    require(isinstance(members, list) and len(members) == 4, "schema-set member list invalid")
    paths = [item["path"] for item in members]
    require(paths == sorted(paths, key=lambda value: value.encode("ascii")), "schema-set members not bytewise ASCII sorted")
    for member in members:
        relative = member["path"]
        mode_text = member["git_mode"]
        require(relative.isascii() and mode_text == "100644", f"schema-set member metadata invalid: {relative}")
        require(git_blob_mode(repo, target, relative) == mode_text, f"schema-set Git mode mismatch: {relative}")
        path = root / relative
        require_regular_input(path, f"schema-set content {relative}", 0o644)
        content = path.read_bytes()
        path_bytes = relative.encode("ascii")
        digest.update(struct.pack(">Q", len(path_bytes)))
        digest.update(path_bytes)
        digest.update(struct.pack(">I", int(mode_text, 8)))
        digest.update(struct.pack(">Q", len(content)))
        digest.update(content)
    return digest.hexdigest()


def load_and_validate_closures(
    root: pathlib.Path,
    repo: pathlib.Path,
    target: str,
    expected_toolchain: Mapping[str, Any],
) -> dict[str, Any]:
    values: dict[str, dict[str, Any]] = {}
    raw_values: dict[str, bytes] = {}
    digests: dict[str, str] = {}
    for name, relative in MANIFEST_PATHS.items():
        path = root / relative
        require_regular_input(path, f"{name} manifest", 0o644)
        value, raw = load_canonical_repository_json(path)
        values[name] = value
        raw_values[name] = raw
        digests[name] = sha256_bytes(raw)
    validate_manifest_common(
        values["toolchain_manifest"],
        "agent_bridge.memory_temporal_owned_lab_role_build_toolchain_manifest_s21b_a1.v0",
        "toolchain manifest",
    )
    require(values["toolchain_manifest"] == dict(expected_toolchain), "toolchain manifest does not equal independently observed closure")
    require(values["feature_set"] == expected_feature_set(), "feature-set manifest drift")
    require(values["schema_set"] == expected_schema_set(), "schema-set manifest drift")
    recipes_expected = expected_recipes()
    require(values["build_recipes"] == recipes_expected, "build-recipes manifest drift")

    require(BWRAP.is_file() and not BWRAP.is_symlink() and os.access(BWRAP, os.X_OK), "pinned bubblewrap binary unavailable")
    require(sha256_file(BWRAP) == recipes_expected["isolation"]["bubblewrap_binary_sha256"], "bubblewrap binary digest drift")
    bwrap_version = run_command([BWRAP, "--version"], env=fixed_tool_environment()).stdout.decode("ascii").strip()
    require(bwrap_version == "bubblewrap 0.11.1", "bubblewrap release drift")

    content_digest = schema_content_digest(root, repo, target, values["schema_set"])
    recipe_objects = values["build_recipes"]["recipes"]
    recipe_digests: dict[str, str] = {}
    for role, binary, _, _ in ROLE_SPECS:
        matches = [item for item in recipe_objects if item.get("binary_name") == binary]
        require(len(matches) == 1, f"build recipe selector is not unique: {binary}")
        recipe_digests[role] = recipe_digest(role, matches[0])
    require(len(set(recipe_digests.values())) == 4, "per-role recipe digests are not pairwise distinct")
    return {
        "values": values,
        "raw_values": raw_values,
        "manifest_digests": digests,
        "schema_content_sha256": content_digest,
        "recipe_digests": recipe_digests,
    }


def make_build_root(scratch: pathlib.Path, label: str, archive: pathlib.Path) -> dict[str, pathlib.Path]:
    root = scratch / f"build-{label.lower()}"
    create_private_dir(root)
    source = root / "source"
    safe_extract_archive(archive, source)
    paths = {"root": root, "source": source}
    for name in ("cargo-home", "target", "home", "tmp"):
        path = root / name
        create_private_dir(path)
        paths[name.replace("-", "_")] = path
    return paths


def bwrap_platform_prefix() -> list[str]:
    require(pathlib.Path("/usr").is_dir(), "/usr unavailable for build sandbox")
    require(pathlib.Path("/etc/ld.so.cache").is_file(), "dynamic-loader cache unavailable")
    return [
        os.fspath(BWRAP),
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--cap-drop", "ALL",
        "--clearenv",
        "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64",
        "--symlink", "usr/sbin", "/sbin",
        "--dir", "/etc",
        "--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache",
        "--proc", "/proc",
        "--dev", "/dev",
        "--dir", "/ab-build",
    ]


def cargo_sandbox_command(
    paths: Mapping[str, pathlib.Path],
    environment: Mapping[str, str],
    arguments: Sequence[str],
    toolchain_root: pathlib.Path,
) -> list[str]:
    command = bwrap_platform_prefix()
    command.extend([
        "--ro-bind", os.fspath(toolchain_root), "/rust-toolchain",
        "--ro-bind", os.fspath(paths["source"]), "/ab-build/source",
        "--bind", os.fspath(paths["cargo_home"]), "/ab-build/cargo-home",
        "--bind", os.fspath(paths["target"]), "/ab-build/target",
        "--bind", os.fspath(paths["home"]), "/ab-build/home",
        "--bind", os.fspath(paths["tmp"]), "/ab-build/tmp",
    ])
    for key in sorted(environment):
        command.extend(["--setenv", key, environment[key]])
    command.extend(["--chdir", "/ab-build/source", "/rust-toolchain/bin/cargo", *arguments])
    return command


def identity_sandbox_command(target_root: pathlib.Path, output_relative_path: str, argument: str | None = None) -> list[str]:
    command = bwrap_platform_prefix()
    command.extend([
        "--ro-bind", os.fspath(target_root), "/ab-build/target",
        "--tmpfs", "/tmp",
        "--setenv", "HOME", "/tmp",
        "--setenv", "LANG", "C.UTF-8",
        "--setenv", "LC_ALL", "C.UTF-8",
        "--setenv", "PATH", "/usr/bin:/bin",
        "--setenv", "TZ", "UTC",
        "--chdir", "/tmp",
        f"/ab-build/target/{output_relative_path}",
    ])
    if argument is not None:
        command.append(argument)
    return command


def expected_identity(role: str, binary: str) -> dict[str, Any]:
    return {
        "arguments_accepted": False,
        "artifact_class": "DECLARED_CARGO_BINARY",
        "binary_name": binary,
        "canonicalization": CANONICALIZATION,
        "credential_access_present": False,
        "execution_capability_present": False,
        "external_payload_reader_present": False,
        "format_id": "agent_bridge.memory_temporal_owned_lab_role_artifact_identity_s21b_a1.v0",
        "implementation_mode": "NON_LIVE_IDENTITY_ONLY",
        "live_adapter_present": False,
        "network_access_present": False,
        "operational_role_implemented": False,
        "owner_authority_present": False,
        "package_version": "0.14.0",
        "packet_kind": "S21B_A1_NON_LIVE_ROLE_ARTIFACT_IDENTITY",
        "private_key_access_present": False,
        "provider_or_production_authority": False,
        "role": role,
        "side_effects_unlocked": "NONE",
        "signing_present": False,
        "synthetic": False,
        "test_only": False,
    }


def observe_artifact(
    paths: Mapping[str, pathlib.Path], role: str, binary: str, output_relative_path: str, recipe_sha256: str
) -> dict[str, Any]:
    artifact = paths["target"] / output_relative_path
    require(artifact.exists() and not artifact.is_symlink(), f"role artifact absent or symlinked: {role}")
    observed = artifact.lstat()
    require(stat.S_ISREG(observed.st_mode), f"role artifact is not regular: {role}")
    mode = stat.S_IMODE(observed.st_mode)
    require(mode == 0o755 and mode & 0o111 != 0, f"role artifact mode is not 0755: {role}")
    require(observed.st_size > 0, f"empty role artifact: {role}")
    require(READELF.is_file() and os.access(READELF, os.X_OK), "fixed readelf binary unavailable")
    require(STRINGS.is_file() and os.access(STRINGS, os.X_OK), "fixed strings binary unavailable")
    elf_header = run_command([READELF, "-hW", artifact], env=fixed_tool_environment()).stdout.decode("ascii", "strict")
    require("Class:                             ELF64" in elf_header, f"artifact is not ELF64: {role}")
    require("Data:                              2's complement, little endian" in elf_header, f"artifact endianness drift: {role}")
    require("Machine:                           Advanced Micro Devices X86-64" in elf_header, f"artifact machine is not x86-64: {role}")
    require(re.search(r"^  Type:\s+(?:EXEC|DYN)\b", elf_header, re.MULTILINE) is not None, f"artifact is not an executable ELF type: {role}")
    require(re.search(r"^  Entry point address:\s+0x[1-9a-fA-F][0-9a-fA-F]*$", elf_header, re.MULTILINE) is not None, f"artifact has no executable entry point: {role}")
    elf_notes = run_command([READELF, "-nW", artifact], env=fixed_tool_environment()).stdout
    require(b"Build ID:" not in elf_notes, f"GNU Build ID unexpectedly present: {role}")
    string_bytes = run_command([STRINGS, "-a", artifact], env=fixed_tool_environment()).stdout
    forbidden_paths = [
        os.fsencode(paths["root"]),
        os.fsencode(paths["source"]),
        os.fsencode(paths["target"]),
        os.fsencode(paths["cargo_home"]),
        b"/ab-build/source",
        b"/ab-build/target",
        b"/ab-build/cargo-home",
    ]
    require(all(value not in string_bytes for value in forbidden_paths), f"unremapped build path leaked into artifact: {role}")

    identity_run = run_command(identity_sandbox_command(paths["target"], output_relative_path), env=fixed_tool_environment())
    require(identity_run.stderr == b"", f"identity-only role wrote stderr: {role}")
    expected_payload = canonical_json_bytes(expected_identity(role, binary))
    require(identity_run.stdout == expected_payload + b"\n", f"identity packet mismatch: {role}")
    require(identity_run.stdout.count(b"\n") == 1, f"identity terminal-LF count mismatch: {role}")
    parsed = parse_json(identity_run.stdout[:-1], f"{role} identity")
    require(parsed == expected_identity(role, binary), f"identity semantics mismatch: {role}")

    forbidden = run_command(
        identity_sandbox_command(paths["target"], output_relative_path, "__operational_command_forbidden__"),
        env=fixed_tool_environment(),
        allowed_returncodes=frozenset({64}),
    )
    require(forbidden.stdout == b"", f"argument rejection wrote stdout: {role}")
    require(
        forbidden.stderr == b"S21B_A1_NON_LIVE_IDENTITY_ONLY: arguments and operational commands are forbidden\n",
        f"argument rejection stderr mismatch: {role}",
    )
    return {
        "artifact_present": True,
        "regular_file": True,
        "executable": True,
        "observed_mode_octal": "0755",
        "byte_count": observed.st_size,
        "raw_sha256": sha256_file(artifact),
        "identity_sha256": sha256_bytes(expected_payload),
        "identity_packet_kind": "S21B_A1_NON_LIVE_ROLE_ARTIFACT_IDENTITY",
        "identity_terminal_lf_count": 1,
        "build_recipe_sha256": recipe_sha256,
    }


def run_role_build(
    paths: Mapping[str, pathlib.Path],
    recipes: Mapping[str, Any],
    recipe_digests: Mapping[str, str],
    epoch: int,
    toolchain_root: pathlib.Path,
) -> dict[str, dict[str, Any]]:
    environment = dict(recipes["environment"])
    environment["SOURCE_DATE_EPOCH"] = str(epoch)
    environment["CARGO_ENCODED_RUSTFLAGS"] = "\x1f".join(recipes["rustflags"])
    require(set(environment) == set(recipes["environment"]) | {"CARGO_ENCODED_RUSTFLAGS"}, "derived build environment drift")
    observations: dict[str, dict[str, Any]] = {}
    for role, binary, _, output in ROLE_SPECS:
        matches = [item for item in recipes["recipes"] if item["binary_name"] == binary]
        require(len(matches) == 1, f"recipe not unique during build: {role}")
        with process_umask(0o022):
            run_command(
                cargo_sandbox_command(
                    paths, environment, matches[0]["arguments"], toolchain_root
                ),
                env=fixed_tool_environment(),
            )
        observations[role] = observe_artifact(paths, role, binary, output, recipe_digests[role])
    require(len({item["raw_sha256"] for item in observations.values()}) == 4, "role binary hashes are not pairwise distinct")
    require(len({item["identity_sha256"] for item in observations.values()}) == 4, "role identity hashes are not pairwise distinct")
    require(len({item["build_recipe_sha256"] for item in observations.values()}) == 4, "role recipe hashes are not pairwise distinct")
    return observations


def _json_schema_type_matches(instance: Any, expected: str) -> bool:
    if expected == "null":
        return instance is None
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    fail(f"receipt schema uses unsupported type: {expected}")


def validate_json_schema(instance: Any, schema: Any, root_schema: Mapping[str, Any], context: str = "$") -> None:
    """Evaluate the closed keyword subset used by the repository receipt schema."""
    if isinstance(schema, bool):
        require(schema, f"{context}: rejected by false schema")
        return
    require(isinstance(schema, dict), f"{context}: schema node is not an object")
    if "$ref" in schema:
        reference = schema["$ref"]
        require(isinstance(reference, str) and re.fullmatch(r"#/\$defs/[A-Za-z0-9_]+", reference), f"{context}: external or malformed schema reference")
        name = reference.rsplit("/", 1)[1]
        definitions = root_schema.get("$defs")
        require(isinstance(definitions, dict) and name in definitions, f"{context}: unresolved schema reference {reference}")
        validate_json_schema(instance, definitions[name], root_schema, context)
    if "allOf" in schema:
        require(isinstance(schema["allOf"], list), f"{context}: allOf invalid")
        for child in schema["allOf"]:
            validate_json_schema(instance, child, root_schema, context)
    if "oneOf" in schema:
        require(isinstance(schema["oneOf"], list), f"{context}: oneOf invalid")
        matches = 0
        for child in schema["oneOf"]:
            try:
                validate_json_schema(instance, child, root_schema, context)
            except BuildError:
                continue
            matches += 1
        require(matches == 1, f"{context}: oneOf matched {matches} branches")
    if "if" in schema:
        try:
            validate_json_schema(instance, schema["if"], root_schema, context)
            branch = schema.get("then")
        except BuildError:
            branch = schema.get("else")
        if branch is not None:
            validate_json_schema(instance, branch, root_schema, context)
    if "type" in schema:
        expected_type = schema["type"]
        if isinstance(expected_type, list):
            require(any(_json_schema_type_matches(instance, item) for item in expected_type), f"{context}: JSON type mismatch")
        else:
            require(isinstance(expected_type, str) and _json_schema_type_matches(instance, expected_type), f"{context}: JSON type mismatch")
    if "const" in schema:
        require(instance == schema["const"] and type(instance) is type(schema["const"]), f"{context}: const mismatch")
    if "enum" in schema:
        require(any(instance == value and type(instance) is type(value) for value in schema["enum"]), f"{context}: enum mismatch")
    if isinstance(instance, int) and not isinstance(instance, bool):
        if "minimum" in schema:
            require(instance >= schema["minimum"], f"{context}: below minimum")
        if "maximum" in schema:
            require(instance <= schema["maximum"], f"{context}: above maximum")
    if isinstance(instance, str) and "pattern" in schema:
        require(re.search(schema["pattern"], instance) is not None, f"{context}: pattern mismatch")
    if isinstance(instance, dict):
        required = schema.get("required", [])
        require(isinstance(required, list) and all(isinstance(item, str) for item in required), f"{context}: required invalid")
        for name in required:
            require(name in instance, f"{context}: required property absent: {name}")
        properties = schema.get("properties", {})
        require(isinstance(properties, dict), f"{context}: properties invalid")
        for name, child in properties.items():
            if name in instance:
                validate_json_schema(instance[name], child, root_schema, f"{context}.{name}")
        if schema.get("additionalProperties") is False:
            extras = set(instance) - set(properties)
            require(not extras, f"{context}: additional properties forbidden: {sorted(extras)!r}")
    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            validate_json_schema(item, schema["items"], root_schema, f"{context}[{index}]")


def load_receipt_schema(source_root: pathlib.Path) -> dict[str, Any]:
    path = source_root / RECEIPT_SCHEMA_REL
    require_regular_input(path, "receipt schema", 0o644)
    raw = path.read_bytes()
    schema = parse_json(raw, str(path))
    require(isinstance(schema, dict), "receipt schema is not an object")
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "receipt schema draft drift")
    require(schema.get("$id") == RECEIPT_SCHEMA, "receipt schema ID drift")

    def inspect(value: Any) -> None:
        if isinstance(value, dict):
            if "$ref" in value:
                require(isinstance(value["$ref"], str) and value["$ref"].startswith("#/$defs/"), "receipt schema external reference forbidden")
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    inspect(schema)
    return schema


def closure_record(relative: str, digest: str) -> dict[str, Any]:
    return {
        "definition_path": relative,
        "definition_present": True,
        "manifest_digest_profile": MANIFEST_DIGEST_PROFILE,
        "manifest_sha256": digest,
        "independently_recomputed_in_build_a": True,
        "independently_recomputed_in_build_b": True,
        "rebuild_values_equal": True,
    }


def rebuild_record(
    label: str,
    archive_sha256: str,
    archive_byte_count: int,
    cargo_lock_sha256: str,
    closure: Mapping[str, Any],
) -> dict[str, Any]:
    digests = closure["manifest_digests"]
    return {
        "build_label": label,
        "completed": True,
        "clean_archive_root_fresh": True,
        "target_directory_fresh": True,
        "incremental_state_shared": False,
        "network_disabled": True,
        "source_archive_sha256": archive_sha256,
        "source_archive_byte_count": archive_byte_count,
        "cargo_lock_sha256": cargo_lock_sha256,
        "toolchain_manifest_sha256": digests["toolchain_manifest"],
        "feature_set_sha256": digests["feature_set"],
        "schema_set_sha256": digests["schema_set"],
        "schema_content_set_sha256": closure["schema_content_sha256"],
        "build_recipes_sha256": digests["build_recipes"],
        "candidate_supplied_expected_digests_used": False,
    }


def build_complete_receipt(
    topology: Mapping[str, Any],
    archive_sha256: str,
    archive_byte_count: int,
    lock_sha256: str,
    closure_a: Mapping[str, Any],
    closure_b: Mapping[str, Any],
    observations_a: Mapping[str, Mapping[str, Any]],
    observations_b: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    digests = closure_a["manifest_digests"]
    closure_bindings: dict[str, Any] = {
        "toolchain_manifest": closure_record(TOOLCHAIN_MANIFEST_REL, digests["toolchain_manifest"]),
        "feature_set": closure_record(FEATURE_SET_REL, digests["feature_set"]),
        "schema_set": closure_record(SCHEMA_SET_REL, digests["schema_set"]),
        "build_recipes": closure_record(RECIPES_REL, digests["build_recipes"]),
        "candidate_supplied_expected_digests_used": False,
    }
    closure_bindings["schema_set"].update({
        "content_set_digest_profile": SCHEMA_CONTENT_PROFILE,
        "content_set_sha256": closure_a["schema_content_sha256"],
    })

    roles: dict[str, Any] = {
        "required_role_count": 4,
        "completed_role_count": 4,
        "raw_sha256_pairwise_distinct": True,
        "identity_sha256_pairwise_distinct": True,
        "build_recipe_sha256_pairwise_distinct": True,
        "private_library_or_test_binary_used": False,
        "arbitrary_digest_substitution_used": False,
    }
    for role, binary, source, output in ROLE_SPECS:
        roles[role] = {
            "role": role,
            "cargo_binary_target": binary,
            "source_relative_path": source,
            "output_relative_path": output,
            "expected_mode_octal": "0755",
            "identity_digest_profile": IDENTITY_DIGEST_PROFILE,
            "build_recipe_digest_profile": RECIPE_DIGEST_PROFILE,
            "build_recipe_digest_domain": f"agent-bridge/biocortex/owned-lab/s21b-a1/build-recipe/{role}/v1",
            "build_recipe_digest_framing": RECIPE_DIGEST_FRAMING,
            "build_a": dict(observations_a[role]),
            "build_b": dict(observations_b[role]),
            "raw_bytes_equal": True,
            "raw_sha256_equal": True,
            "identity_sha256_equal": True,
            "build_recipe_sha256_equal": True,
        }

    baseline = topology["baseline"]
    source_commit = topology["source"]
    source_parent = topology["source_parent"]
    integration = topology["integration"]
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "packet_kind": RECEIPT_PACKET_KIND,
        "canonicalization": CANONICALIZATION,
        "stage": STAGE,
        "status": STATUS,
        "decision": DECISION,
        "hashing_contract": {
            "hash_algorithm": "SHA-256",
            "canonicalization": CANONICALIZATION,
            "digest_domain": RECEIPT_DOMAIN.decode("ascii"),
            "digest_framing": RECIPE_DIGEST_FRAMING,
            "hash_scope": "ENTIRE_PACKET_EXCEPT_ROLE_BUILD_RECEIPT_SHA256",
            "self_hash_field": "role_build_receipt_sha256",
            "self_hash_field_excluded": True,
            "repository_framing_lf_excluded": True,
            "cross_field_semantic_validation_required": True,
            "candidate_reported_matches_authoritative": False,
        },
        "receipt_state": RECEIPT_STATE,
        "test_only": False,
        "synthetic": False,
        "target_binding": {
            "canonical_remote": CANONICAL_REMOTE,
            "remote_ref": REMOTE_REF,
            "a0_integration_commit": baseline["oid"],
            "a0_integration_tree": baseline["tree"],
            "a0_integration_first_parent": baseline["parents"][0],
            "a0_integration_second_parent": baseline["parents"][1],
            "a0_archive_sha256": BASELINE_ARCHIVE_SHA256,
            "a0_archive_byte_count": BASELINE_ARCHIVE_BYTE_COUNT,
            "a0_cargo_lock_sha256": BASELINE_CARGO_LOCK_SHA256,
            "archive_profile": ARCHIVE_PROFILE,
            "target_refrozen": True,
            "source_commit": source_commit["oid"],
            "source_tree": source_commit["tree"],
            "source_parent_commit": source_parent["oid"],
            "source_parent_tree": source_parent["tree"],
            "integration_commit": integration["oid"],
            "integration_tree": integration["tree"],
            "integration_first_parent": integration["parents"][0],
            "integration_second_parent": integration["parents"][1],
            "target_committer_epoch": integration["committer_epoch"],
            "integrated_archive_sha256": archive_sha256,
            "integrated_archive_byte_count": archive_byte_count,
            "cargo_lock_sha256": lock_sha256,
            "candidate_supplied_target_used": False,
        },
        "closure_bindings": closure_bindings,
        "rebuilds": {
            "build_a": rebuild_record("A", archive_sha256, archive_byte_count, lock_sha256, closure_a),
            "build_b": rebuild_record("B", archive_sha256, archive_byte_count, lock_sha256, closure_b),
            "build_roots_distinct": True,
            "target_directories_distinct": True,
            "all_closure_digests_equal": True,
            "schema_content_set_digests_equal": True,
            "all_role_outputs_byte_equal": True,
        },
        "role_artifacts": roles,
        "forbidden_outputs": {
            "unsigned_final_subject_present": False,
            "unsigned_final_subject_sha256": None,
            "owner_signing_request_present": False,
            "owner_signing_message_sha256": None,
            "owner_anchor_present": False,
            "owner_private_key_read": False,
            "owner_signature_present": False,
            "owner_signature_sha256": None,
            "owner_authorization_envelope_present": False,
            "external_input_admission_present": False,
            "execution_capability_present": False,
            "live_adapter_present": False,
            "live_action_count": 0,
        },
        "result": {
            "role_build_closure_complete": True,
            "terminal_hard_lock": False,
            "next_action": "BEGIN_SEPARATE_UNSIGNED_SUBJECT_CONTRACT_REBINDING_AND_GENERATION_REVIEW",
            "owner_interaction_required_now": False,
            "separate_unsigned_subject_contract_stage_may_begin": True,
            "unsigned_final_subject_may_be_generated_by_this_stage": False,
            "owner_signature_may_be_requested": False,
            "live_execution_may_begin": False,
            "side_effects_unlocked": "NONE",
        },
        "nonclaims": {
            "receipt_is_unsigned_final_subject": False,
            "receipt_is_owner_signing_request": False,
            "receipt_is_owner_authority": False,
            "receipt_is_execution_capability": False,
            "identity_only_binaries_are_operational_roles": False,
            "build_equality_proves_behavioral_correctness": False,
            "build_equality_proves_cross_host_reproducibility": False,
            "build_equality_proves_complete_supply_chain_provenance": False,
            "synthetic_fixture_is_real_build_evidence": False,
            "provider_or_production_authority": False,
            "side_effects_unlocked": "NONE",
        },
    }
    payload = canonical_json_bytes(receipt)
    receipt["role_build_receipt_sha256"] = framed_digest(RECEIPT_DOMAIN, payload)
    return receipt


def is_within(path: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def require_secure_directory_chain(path: pathlib.Path, context: str) -> None:
    resolved = path.resolve(strict=True)
    require(resolved == path.absolute(), f"{context} is not canonical")
    euid = os.geteuid()
    current = pathlib.Path(resolved.anchor)
    members = [current]
    for part in resolved.parts[1:]:
        current /= part
        members.append(current)
    for member in members:
        observed = member.lstat()
        require(stat.S_ISDIR(observed.st_mode) and not member.is_symlink(), f"{context} ancestor is not a directory: {member}")
        require(observed.st_uid in (0, euid), f"{context} ancestor has an untrusted owner: {member}")
        writable = observed.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        sticky_root = observed.st_uid == 0 and bool(observed.st_mode & stat.S_ISVTX)
        require(not writable or sticky_root, f"{context} ancestor is replaceable by another local user: {member}")


def directory_identity(descriptor: int) -> tuple[int, int]:
    observed = os.fstat(descriptor)
    require(stat.S_ISDIR(observed.st_mode), "pinned output parent is not a directory")
    return observed.st_dev, observed.st_ino


def require_pinned_directory(
    path: pathlib.Path, descriptor: int, expected_identity: tuple[int, int]
) -> None:
    observed = os.stat(path, follow_symlinks=False)
    require(stat.S_ISDIR(observed.st_mode), "output parent path stopped naming a directory")
    require(
        (observed.st_dev, observed.st_ino) == expected_identity
        and directory_identity(descriptor) == expected_identity,
        "output parent path identity changed",
    )


def require_pinned_child_directory(
    parent: pathlib.Path,
    parent_descriptor: int,
    parent_identity: tuple[int, int],
    name: str,
    child_descriptor: int,
    child_identity: tuple[int, int],
) -> None:
    require_pinned_directory(parent, parent_descriptor, parent_identity)
    entry = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    require(
        stat.S_ISDIR(entry.st_mode)
        and (entry.st_dev, entry.st_ino) == child_identity
        and directory_identity(child_descriptor) == child_identity,
        "scratch path identity changed",
    )


def write_external_receipt(
    parent: pathlib.Path,
    parent_descriptor: int,
    parent_identity: tuple[int, int],
    name: str,
    raw: bytes,
) -> None:
    require_pinned_directory(parent, parent_descriptor, parent_identity)
    try:
        os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        raise BuildError("output already exists; overwrite is forbidden")

    descriptor = os.open(
        name,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
        dir_fd=parent_descriptor,
    )
    created_identity: tuple[int, int] | None = None
    try:
        created = os.fstat(descriptor)
        require(stat.S_ISREG(created.st_mode), "external receipt is not a regular file")
        created_identity = (created.st_dev, created.st_ino)
        remaining = memoryview(raw)
        while remaining:
            written = os.write(descriptor, remaining)
            require(written > 0, "external receipt write made no progress")
            remaining = remaining[written:]
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        observed = bytearray()
        while len(observed) < len(raw):
            block = os.read(descriptor, min(1024 * 1024, len(raw) - len(observed)))
            require(block != b"", "external receipt readback ended early")
            observed.extend(block)
        require(os.read(descriptor, 1) == b"", "external receipt readback has trailing bytes")
        require(bytes(observed) == raw, "external receipt write verification failed")
        final_file = os.fstat(descriptor)
        require(stat.S_IMODE(final_file.st_mode) == 0o600, "external receipt mode drift")
        entry = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        require(
            stat.S_ISREG(entry.st_mode)
            and (entry.st_dev, entry.st_ino) == created_identity,
            "external receipt directory entry identity changed",
        )
        os.fsync(parent_descriptor)
        require_pinned_directory(parent, parent_descriptor, parent_identity)
    except BaseException:
        if created_identity is not None:
            with contextlib.suppress(FileNotFoundError):
                entry = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
                if (entry.st_dev, entry.st_ino) == created_identity:
                    os.unlink(name, dir_fd=parent_descriptor)
                    os.fsync(parent_descriptor)
        raise
    finally:
        os.close(descriptor)


def execute(
    repo_argument: str,
    target: str,
    scratch_argument: str,
    output_argument: str,
    resources: contextlib.ExitStack,
) -> tuple[pathlib.Path, str]:
    repo_input = pathlib.Path(repo_argument).expanduser()
    scratch_input = pathlib.Path(scratch_argument).expanduser()
    output_input = pathlib.Path(output_argument).expanduser()
    require(repo_input.is_absolute(), "--repo must be an absolute path")
    require(scratch_input.is_absolute(), "--scratch must be an absolute path")
    require(output_input.is_absolute(), "--output must be an absolute path")
    require(repo_input.is_dir() and not repo_input.is_symlink(), "--repo is not a non-symlink directory")
    repo = repo_input.resolve(strict=True)
    require(repo_input.absolute() == repo, "--repo must already be a canonical path")
    require_secure_directory_chain(repo, "--repo")
    output_parent = output_input.parent.resolve(strict=True)
    require(
        output_parent.is_dir()
        and not output_parent.is_symlink()
        and output_input.parent.absolute() == output_parent,
        "--output parent must already be one canonical non-symlink directory",
    )
    require_secure_directory_chain(output_parent, "--output parent")
    output = output_parent / output_input.name
    require(output.name not in ("", ".", ".."), "--output filename invalid")
    require(not output.exists() and not output.is_symlink(), "--output must be a new path")
    output_parent_descriptor = os.open(
        output_parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    resources.callback(os.close, output_parent_descriptor)
    output_parent_identity = directory_identity(output_parent_descriptor)
    require_pinned_directory(output_parent, output_parent_descriptor, output_parent_identity)
    scratch_parent = scratch_input.parent.resolve(strict=True)
    require(
        scratch_parent.is_dir()
        and not scratch_parent.is_symlink()
        and scratch_input.parent.absolute() == scratch_parent,
        "--scratch parent must already be one canonical non-symlink directory",
    )
    require_secure_directory_chain(scratch_parent, "--scratch parent")
    scratch_parent_descriptor = os.open(
        scratch_parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    resources.callback(os.close, scratch_parent_descriptor)
    scratch_parent_identity = directory_identity(scratch_parent_descriptor)
    require_pinned_directory(scratch_parent, scratch_parent_descriptor, scratch_parent_identity)
    require(scratch_input.name not in ("", ".", ".."), "--scratch basename invalid")
    scratch_candidate = scratch_parent / scratch_input.name
    require(output != scratch_candidate, "--output and --scratch must be distinct paths")

    ensure_git_object_boundary(repo)
    git_dir_raw = git(repo, "rev-parse", "--path-format=absolute", "--absolute-git-dir")
    git_dir = pathlib.Path(git_dir_raw.decode("utf-8").strip()).resolve(strict=True)
    require(git_dir.is_dir() and not git_dir.is_symlink(), "Git worktree directory is not canonical")
    require_secure_directory_chain(git_dir, "Git worktree directory")
    common_dir_raw = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    common_dir = pathlib.Path(common_dir_raw.decode("utf-8").strip()).resolve(strict=True)
    require(common_dir.is_dir() and not common_dir.is_symlink(), "Git common directory is not canonical")
    require_secure_directory_chain(common_dir, "Git common directory")
    require(
        not is_within(scratch_candidate, repo) and not is_within(scratch_candidate, common_dir),
        "--scratch must be outside the repository and Git common directory",
    )
    require(
        not is_within(output, repo) and not is_within(output, common_dir),
        "--output must be outside the repository and Git common directory",
    )
    topology = validate_target_topology(repo, target)
    scratch, scratch_descriptor, scratch_identity = prepare_scratch(
        scratch_parent,
        scratch_parent_descriptor,
        scratch_parent_identity,
        scratch_candidate.name,
        resources,
    )
    require_pinned_child_directory(
        scratch_parent,
        scratch_parent_descriptor,
        scratch_parent_identity,
        scratch_candidate.name,
        scratch_descriptor,
        scratch_identity,
    )
    require(
        not is_within(output, scratch_candidate) or output.parent == scratch_candidate,
        "nested output under a build subtree is forbidden",
    )

    baseline_archive = scratch / "a0-baseline.tar"
    baseline_sha, baseline_size = create_archive(repo, BASELINE_COMMIT, baseline_archive)
    require(baseline_sha == BASELINE_ARCHIVE_SHA256, "A0 baseline archive digest drift")
    require(baseline_size == BASELINE_ARCHIVE_BYTE_COUNT, "A0 baseline archive byte-count drift")
    baseline_archive.unlink()
    require_pinned_child_directory(
        scratch_parent, scratch_parent_descriptor, scratch_parent_identity,
        scratch_candidate.name, scratch_descriptor, scratch_identity,
    )

    archive_a = scratch / "integration-a.tar"
    archive_b = scratch / "integration-b.tar"
    archive_a_sha, archive_a_size = create_archive(repo, target, archive_a)
    archive_b_sha, archive_b_size = create_archive(repo, target, archive_b)
    require(archive_a_sha == archive_b_sha and archive_a_size == archive_b_size, "independent target archive digests differ")
    require(files_equal(archive_a, archive_b), "independent target archive bytes differ")
    require_pinned_child_directory(
        scratch_parent, scratch_parent_descriptor, scratch_parent_identity,
        scratch_candidate.name, scratch_descriptor, scratch_identity,
    )

    paths_a = make_build_root(scratch, "A", archive_a)
    paths_b = make_build_root(scratch, "B", archive_b)
    require(paths_a["root"].resolve() != paths_b["root"].resolve(), "build roots are not distinct")
    require(paths_a["target"].resolve() != paths_b["target"].resolve(), "target directories are not distinct")
    require_pinned_child_directory(
        scratch_parent, scratch_parent_descriptor, scratch_parent_identity,
        scratch_candidate.name, scratch_descriptor, scratch_identity,
    )

    lock_a_sha, registry_names_a = validate_source_graph(paths_a["source"], repo, target)
    lock_b_sha, registry_names_b = validate_source_graph(paths_b["source"], repo, target)
    require(lock_a_sha == lock_b_sha, "Cargo.lock digests differ between archive roots")
    require((paths_a["source"] / "Cargo.lock").read_bytes() == (paths_b["source"] / "Cargo.lock").read_bytes(), "Cargo.lock bytes differ between roots")
    require(registry_names_a == registry_names_b, "registry package-name closure differs between roots")

    expected_toolchain = load_canonical_repository_json(
        paths_a["source"] / TOOLCHAIN_MANIFEST_REL
    )[0]
    secure_toolchain = scratch / "secure-toolchain"
    copy_secure_toolchain(
        TOOLCHAIN_HOST_ROOT,
        secure_toolchain,
        expected_toolchain["toolchain_tree_catalog"],
    )
    observed_toolchain, selected_index = observed_toolchain_manifest(
        paths_a["source"], registry_names_a, secure_toolchain
    )
    require(
        observed_toolchain == expected_toolchain,
        "secure toolchain snapshot differs from the declared host closure",
    )
    closure_a = load_and_validate_closures(paths_a["source"], repo, target, observed_toolchain)
    closure_b = load_and_validate_closures(paths_b["source"], repo, target, observed_toolchain)
    require(closure_a["manifest_digests"] == closure_b["manifest_digests"], "closure manifest digests differ between roots")
    require(closure_a["schema_content_sha256"] == closure_b["schema_content_sha256"], "schema content-set digests differ between roots")
    require(closure_a["recipe_digests"] == closure_b["recipe_digests"], "recipe digests differ between roots")
    for name in MANIFEST_PATHS:
        require(closure_a["raw_values"][name] == closure_b["raw_values"][name], f"closure manifest bytes differ: {name}")

    sparse_expected = observed_toolchain["cargo_registry_sparse_index"]
    copy_sparse_index(paths_a["cargo_home"], selected_index)
    validate_sparse_index_copy(paths_a["cargo_home"], sparse_expected, selected_index)
    sparse_after_a, _ = sparse_index_observation(registry_names_a)
    require(sparse_after_a == sparse_expected, "trusted sparse-index changed during build-A copy")
    copy_sparse_index(paths_b["cargo_home"], selected_index)
    validate_sparse_index_copy(paths_b["cargo_home"], sparse_expected, selected_index)
    sparse_after_b, _ = sparse_index_observation(registry_names_a)
    require(sparse_after_b == sparse_expected, "trusted sparse-index changed during build-B copy")

    epoch = topology["integration"]["committer_epoch"]
    observations_a = run_role_build(
        paths_a,
        closure_a["values"]["build_recipes"],
        closure_a["recipe_digests"],
        epoch,
        secure_toolchain,
    )
    observations_b = run_role_build(
        paths_b,
        closure_b["values"]["build_recipes"],
        closure_b["recipe_digests"],
        epoch,
        secure_toolchain,
    )
    require_pinned_child_directory(
        scratch_parent, scratch_parent_descriptor, scratch_parent_identity,
        scratch_candidate.name, scratch_descriptor, scratch_identity,
    )
    observed_toolchain_after_builds, _ = observed_toolchain_manifest(
        paths_a["source"], registry_names_a, secure_toolchain
    )
    require(
        observed_toolchain_after_builds == observed_toolchain,
        "secure toolchain/system/sparse-index closure changed during the two builds",
    )
    for role, _, _, relative_output in ROLE_SPECS:
        artifact_a = paths_a["target"] / relative_output
        artifact_b = paths_b["target"] / relative_output
        require(files_equal(artifact_a, artifact_b), f"role artifact bytes differ across rebuilds: {role}")
        require(observations_a[role] == observations_b[role], f"role artifact observations differ: {role}")

    schema_a_path = paths_a["source"] / RECEIPT_SCHEMA_REL
    schema_b_path = paths_b["source"] / RECEIPT_SCHEMA_REL
    require(schema_a_path.read_bytes() == schema_b_path.read_bytes(), "receipt schema differs between archive roots")
    receipt_schema = load_receipt_schema(paths_a["source"])
    receipt = build_complete_receipt(
        topology,
        archive_a_sha,
        archive_a_size,
        lock_a_sha,
        closure_a,
        closure_b,
        observations_a,
        observations_b,
    )
    validate_json_schema(receipt, receipt_schema, receipt_schema)
    self_digest = receipt["role_build_receipt_sha256"]
    require(isinstance(self_digest, str) and HEX64.fullmatch(self_digest) is not None, "receipt self digest malformed")
    without_self = dict(receipt)
    del without_self["role_build_receipt_sha256"]
    require(framed_digest(RECEIPT_DOMAIN, canonical_json_bytes(without_self)) == self_digest, "receipt self digest recomputation failed")
    raw_receipt = canonical_json_bytes(receipt) + b"\n"
    require(raw_receipt.count(b"\n") == 1 and raw_receipt.endswith(b"\n"), "receipt repository framing invalid")
    require_pinned_child_directory(
        scratch_parent, scratch_parent_descriptor, scratch_parent_identity,
        scratch_candidate.name, scratch_descriptor, scratch_identity,
    )
    write_external_receipt(
        output_parent,
        output_parent_descriptor,
        output_parent_identity,
        output.name,
        raw_receipt,
    )
    return output, self_digest


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Perform two serial, offline, clean-archive builds of the four exact "
            "S21B-A1 non-live role binaries and write a new external canonical receipt."
        )
    )
    parser.add_argument("--repo", required=True, help="absolute path to the canonical Agent-Bridge Git worktree")
    parser.add_argument("--target", required=True, help="immutable lowercase 40-hex ordinary integration commit")
    parser.add_argument("--scratch", required=True, help="absolute absent or empty private 0700 scratch directory")
    parser.add_argument("--output", required=True, help="absolute new repository-external receipt file")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        with contextlib.ExitStack() as resources:
            output, digest = execute(
                arguments.repo,
                arguments.target,
                arguments.scratch,
                arguments.output,
                resources,
            )
    except (BuildError, OSError, UnicodeError, ValueError) as exc:
        print(f"S21B_A1_BUILD_ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"S21B_A1_ROLE_BUILD_RECEIPT_WRITTEN path={output} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
