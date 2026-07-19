#!/usr/bin/env python3
"""Independent S21B-A0 pre-sign closure checker.

This checker reconstructs the frozen S21A integration identity and archive from
Git objects selected by constants in this program.  Candidate documents cannot
select a commit, tree, archive digest, Cargo.lock digest, or binary target.  The
checker never reads a private key, creates a signature, or emits a signable
subject or signing message.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import random
import re
import subprocess
import sys
import tarfile
import tomllib
from dataclasses import dataclass
from typing import Any, BinaryIO, Iterable, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

sys.dont_write_bytecode = True


TARGET_COMMIT = "34b1c7e6ca9c2b75fd2ef3cf418a444353059511"
TARGET_TREE = "00bbf534c33ecfa56d05579d8a7f4c83e60b208e"
TARGET_PARENTS = (
    "8521ff6a9784a6d74be2b8ee0e02f3aba6b9f8a5",
    "ed5d959489f88d0eead21b604d03a142e0584982",
)
SOURCE_COMMIT = TARGET_PARENTS[1]
SOURCE_TREE = "7d1db2c9eb04d75cc980ea83d369b9129155252f"
SOURCE_PARENT = "33c2c4df78ef302fd0538986b95fa40a3711ba86"
SOURCE_PARENT_TREE = "6f92c687b61e1433e693ca6cd1bc6390dda97f29"
ARCHIVE_SHA256 = "d45312d5b343dd036ef6906af0abe9f59da8220cf6ef16fb87caf8c1265c0bb5"
ARCHIVE_BYTE_COUNT = 48_107_520
CARGO_LOCK_SHA256 = "408e0aa5e6bc3f2a318719c57419ece60b507df0a11c1738fd40dda66aac1f59"

REQUIRED_ROLE_BINARIES = (
    "ab-owned-lab-controller",
    "ab-owned-lab-observer",
    "ab-owned-lab-runner",
    "ab-owned-lab-validator",
)

STAGE = "S21B_A0_NON_LIVE_PRESIGN_CLOSURE_AND_ROLE_ARTIFACT_EXISTENCE_AUDIT"
STATUS = "S21B_A0_BLOCKED_MISSING_ROLE_ARTIFACTS_AND_REPRODUCIBLE_CLOSURES"
DECISION = "S21B_A0_REMAINS_BLOCKED_NO_UNSIGNED_SUBJECT_OR_OWNER_SIGNING_REQUEST"
MODE = "READ_ONLY_IDENTITY_AND_EXISTENCE_AUDIT_WITH_SYNTHETIC_BLOCKED_RECEIPT_ONLY"
RECEIPT_SCHEMA_ID = (
    "agent_bridge.memory_temporal_owned_lab_presign_closure_receipt_s21b_a0.v0"
)
RECEIPT_KIND = "S21B_A0_PRESIGN_CLOSURE_RECEIPT"
RECEIPT_STATE = "SYNTHETIC_KAT_BLOCKED_MISSING_FOUR_ROLE_ARTIFACTS_AND_REBUILD_CLOSURES"
CANONICALIZATION = (
    "AB_RESTRICTED_CANONICAL_JSON_S21B_A0_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT"
)
RECEIPT_DOMAIN = (
    "agent-bridge/biocortex/owned-lab/s21b-a0/presign-closure-receipt/v1"
)
FRAMING = (
    "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_CANONICAL_PAYLOAD_LENGTH_CANONICAL_PAYLOAD"
)
SELF_HASH_FIELD = "presign_closure_receipt_sha256"

PREFIX = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-"
CONTRACT_PATH = PREFIX + "presign-closure-contract-s21b-a0-v0.json"
STATUS_PATH = PREFIX + "presign-closure-status-s21b-a0-v0.json"
SCHEMA_PATH = PREFIX + "presign-closure-receipt-schema-s21b-a0-v0.json"
FIXTURE_PATH = PREFIX + "presign-closure-receipt-synthetic-s21b-a0-v0.json"
SUCCESSOR_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s21b-a0-v0.json"

MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
MAX_JSON_DEPTH = 20
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class CheckFailure(RuntimeError):
    """Expected fail-closed validation error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, UnicodeEncodeError, ValueError) as exc:
        raise CheckFailure(f"restricted canonical JSON encoding failed: {exc}") from exc


def validate_restricted_value(value: Any, depth: int = 0) -> None:
    require(depth <= MAX_JSON_DEPTH, "restricted JSON nesting exceeds limit")
    if value is None or type(value) in (bool, int):
        return
    if isinstance(value, str):
        require(value.isascii(), "restricted JSON string is not ASCII")
        return
    if isinstance(value, list):
        for item in value:
            validate_restricted_value(item, depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            require(isinstance(key, str) and key.isascii(), "restricted JSON key is not ASCII")
            validate_restricted_value(item, depth + 1)
        return
    raise CheckFailure(f"restricted JSON forbids value type {type(value).__name__}")


def parse_json(raw: bytes, label: str) -> dict[str, Any]:
    require(0 < len(raw) <= MAX_DOCUMENT_BYTES, f"document size outside bound: {label}")
    require(not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {label}")

    def duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {label}: {key}")
            result[key] = value
        return result

    def reject_float(_: str) -> Any:
        raise CheckFailure(f"floating-point value forbidden: {label}")

    def reject_constant(_: str) -> Any:
        raise CheckFailure(f"non-finite number forbidden: {label}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=duplicate_pairs,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckFailure(f"invalid JSON: {label}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root is not an object: {label}")
    validate_restricted_value(value)
    return value


def framed_digest(domain: str, payload: bytes) -> str:
    domain_raw = domain.encode("ascii")
    frame = (
        len(domain_raw).to_bytes(4, "big")
        + domain_raw
        + len(payload).to_bytes(8, "big")
        + payload
    )
    return sha256(frame)


def read_repo_file(repo: Path, relative: str) -> bytes:
    path = repo / relative
    require(path.is_file(), f"missing regular artifact: {relative}")
    require(not path.is_symlink(), f"symlink artifact forbidden: {relative}")
    require(path.resolve() == path, f"non-canonical artifact path: {relative}")
    raw = path.read_bytes()
    require(0 < len(raw) <= MAX_DOCUMENT_BYTES, f"artifact size outside bound: {relative}")
    return raw


def load_repo_json(repo: Path, relative: str) -> tuple[bytes, dict[str, Any]]:
    raw = read_repo_file(repo, relative)
    return raw, parse_json(raw, relative)


def git_environment() -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "LANG": "C",
        "TZ": "UTC",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
        "GIT_ASKPASS": "/bin/false",
    }


def run_git(repo: Path, args: Iterable[str]) -> bytes:
    command = ["/usr/bin/git", "--no-replace-objects", *args]
    process = subprocess.run(
        command,
        cwd=repo,
        env=git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    require(
        process.returncode == 0,
        f"Git command failed: {' '.join(command)}: {process.stderr.decode('utf-8', 'replace').strip()}",
    )
    return process.stdout


def parse_commit_object(raw: bytes, label: str) -> tuple[str, tuple[str, ...]]:
    try:
        header = raw.split(b"\n\n", 1)[0].decode("ascii")
    except UnicodeDecodeError as exc:
        raise CheckFailure(f"non-ASCII commit header: {label}") from exc
    tree: str | None = None
    parents: list[str] = []
    for line in header.splitlines():
        if line.startswith("tree "):
            require(tree is None, f"duplicate tree header: {label}")
            tree = line[5:]
        elif line.startswith("parent "):
            parents.append(line[7:])
    require(tree is not None and HEX_40.fullmatch(tree) is not None, f"invalid tree: {label}")
    require(all(HEX_40.fullmatch(parent) for parent in parents), f"invalid parent: {label}")
    return tree, tuple(parents)


class HashingReader(io.RawIOBase):
    """Read-through archive hasher without materializing the 48 MB tar."""

    def __init__(self, source: BinaryIO):
        self.source = source
        self.digest = hashlib.sha256()
        self.byte_count = 0

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        raw = self.source.read(size)
        self.digest.update(raw)
        self.byte_count += len(raw)
        return raw


@dataclass(frozen=True)
class GitAudit:
    target_tree: str
    target_parents: tuple[str, ...]
    source_tree: str
    archive_sha256: str
    archive_byte_count: int
    cargo_lock_sha256: str
    cargo_manifest_count: int
    cargo_binary_targets: tuple[str, ...]
    cargo_binary_target_set_sha256: str
    missing_role_binaries: tuple[str, ...]


@dataclass(frozen=True)
class DocumentAudit:
    contract_sha256: str
    status_sha256: str
    schema_sha256: str
    fixture_sha256: str
    fixture_self_sha256: str
    successor_sha256: str
    self_test_mutation_count: int


def inferred_explicit_name(entry: Mapping[str, Any]) -> str | None:
    name = entry.get("name")
    if isinstance(name, str) and name:
        return name
    path = entry.get("path")
    if not isinstance(path, str) or not path:
        return None
    pure = PurePosixPath(path)
    if pure.name == "main.rs" and pure.parent.name:
        return pure.parent.name
    return pure.stem or None


def enumerate_binary_targets(
    manifests: Mapping[str, bytes], archive_members: set[str]
) -> tuple[str, ...]:
    targets: set[str] = set()
    for manifest_path, raw in sorted(manifests.items()):
        try:
            manifest = tomllib.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            raise CheckFailure(f"Cargo manifest parse failed: {manifest_path}: {exc}") from exc
        require(isinstance(manifest, dict), f"Cargo manifest root invalid: {manifest_path}")
        package = manifest.get("package")
        explicit = manifest.get("bin", [])
        require(isinstance(explicit, list), f"Cargo [[bin]] table invalid: {manifest_path}")
        directory = str(PurePosixPath(manifest_path).parent)
        prefix = "" if directory == "." else directory + "/"
        explicit_paths: set[str] = set()
        for entry in explicit:
            require(isinstance(entry, dict), f"Cargo [[bin]] entry invalid: {manifest_path}")
            name = inferred_explicit_name(entry)
            require(name is not None, f"Cargo [[bin]] lacks inferable name: {manifest_path}")
            targets.add(name)
            path = entry.get("path")
            if isinstance(path, str) and path:
                explicit_paths.add(prefix + str(PurePosixPath(path)))

        if not isinstance(package, dict) or package.get("autobins", True) is False:
            continue
        package_name = package.get("name")
        require(isinstance(package_name, str) and package_name, f"Cargo package name invalid: {manifest_path}")
        main_path = prefix + "src/main.rs"
        if main_path in archive_members and main_path not in explicit_paths:
            targets.add(package_name)
        bin_prefix = prefix + "src/bin/"
        for member in archive_members:
            if not member.startswith(bin_prefix):
                continue
            relative = member[len(bin_prefix) :]
            parts = PurePosixPath(relative).parts
            if member in explicit_paths:
                continue
            if len(parts) == 1 and parts[0].endswith(".rs"):
                targets.add(PurePosixPath(parts[0]).stem)
            elif len(parts) == 2 and parts[1] == "main.rs":
                targets.add(parts[0])
    return tuple(sorted(targets))


def audit_archive(repo: Path) -> tuple[str, int, str, int, tuple[str, ...]]:
    command = [
        "/usr/bin/git",
        "--no-replace-objects",
        "-c",
        "tar.umask=0022",
        "archive",
        "--format=tar",
        TARGET_COMMIT,
    ]
    process = subprocess.Popen(
        command,
        cwd=repo,
        env=git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    require(process.stdout is not None and process.stderr is not None, "Git archive pipes absent")
    reader = HashingReader(process.stdout)
    manifests: dict[str, bytes] = {}
    members: set[str] = set()
    cargo_lock: bytes | None = None
    try:
        with tarfile.open(fileobj=reader, mode="r|") as archive:
            for member in archive:
                require(member.name not in members, f"duplicate archive path: {member.name}")
                members.add(member.name)
                if not member.isfile():
                    continue
                if member.name == "Cargo.lock" or member.name == "Cargo.toml" or member.name.endswith("/Cargo.toml"):
                    extracted = archive.extractfile(member)
                    require(extracted is not None, f"archive member unreadable: {member.name}")
                    raw = extracted.read()
                    require(len(raw) == member.size, f"archive member short read: {member.name}")
                    if member.name == "Cargo.lock":
                        require(cargo_lock is None, "duplicate root Cargo.lock")
                        cargo_lock = raw
                    else:
                        manifests[member.name] = raw
        while reader.read(1024 * 1024):
            pass
    except Exception:
        process.kill()
        process.wait()
        raise
    stderr = process.stderr.read()
    returncode = process.wait()
    require(
        returncode == 0,
        f"Git archive failed: {stderr.decode('utf-8', 'replace').strip()}",
    )
    require(cargo_lock is not None, "frozen archive lacks root Cargo.lock")
    require(manifests, "frozen archive lacks Cargo manifests")
    targets = enumerate_binary_targets(manifests, members)
    return (
        reader.digest.hexdigest(),
        reader.byte_count,
        sha256(cargo_lock),
        len(manifests),
        targets,
    )


def audit_git(repo: Path) -> GitAudit:
    require(run_git(repo, ["cat-file", "-t", TARGET_COMMIT]) == b"commit\n", "target object is not a commit")
    require(run_git(repo, ["cat-file", "-t", SOURCE_COMMIT]) == b"commit\n", "source object is not a commit")
    target_tree, target_parents = parse_commit_object(
        run_git(repo, ["cat-file", "commit", TARGET_COMMIT]), "target commit"
    )
    source_tree, source_parents = parse_commit_object(
        run_git(repo, ["cat-file", "commit", SOURCE_COMMIT]), "source commit"
    )
    parent_tree, _ = parse_commit_object(
        run_git(repo, ["cat-file", "commit", SOURCE_PARENT]), "source parent commit"
    )
    require(target_tree == TARGET_TREE, "target integration tree drift")
    require(target_parents == TARGET_PARENTS, "target integration parent order drift")
    require(source_tree == SOURCE_TREE, "S21A source tree drift")
    require(source_parents == (SOURCE_PARENT,), "S21A source parent drift")
    require(parent_tree == SOURCE_PARENT_TREE, "S21A source-parent tree drift")
    require(run_git(repo, ["cat-file", "-t", TARGET_TREE]) == b"tree\n", "target tree object absent")
    require(run_git(repo, ["cat-file", "-t", SOURCE_TREE]) == b"tree\n", "source tree object absent")
    require(
        run_git(repo, ["merge-base", "--is-ancestor", TARGET_COMMIT, "HEAD"]) == b"",
        "frozen S21A integration is not an ancestor of the audited checkout",
    )

    archive_digest, archive_bytes, lock_digest, manifest_count, targets = audit_archive(repo)
    require(archive_digest == ARCHIVE_SHA256, "independently reconstructed archive digest drift")
    require(archive_bytes == ARCHIVE_BYTE_COUNT, "independently reconstructed archive size drift")
    require(lock_digest == CARGO_LOCK_SHA256, "Cargo.lock digest drift")
    missing = tuple(name for name in REQUIRED_ROLE_BINARIES if name not in targets)
    require(missing == REQUIRED_ROLE_BINARIES, "one or more required role binaries unexpectedly exist")
    target_set_digest = sha256(("\n".join(targets) + "\n").encode("ascii"))
    return GitAudit(
        target_tree=target_tree,
        target_parents=target_parents,
        source_tree=source_tree,
        archive_sha256=archive_digest,
        archive_byte_count=archive_bytes,
        cargo_lock_sha256=lock_digest,
        cargo_manifest_count=manifest_count,
        cargo_binary_targets=targets,
        cargo_binary_target_set_sha256=target_set_digest,
        missing_role_binaries=missing,
    )


def walk_schema(node: Any, label: str = "$") -> None:
    if isinstance(node, dict):
        reference = node.get("$ref")
        if reference is not None:
            require(
                isinstance(reference, str) and reference.startswith("#/$defs/"),
                f"external or non-local schema reference: {label}",
            )
        require(
            node.get("additionalProperties") is not True,
            f"schema explicitly permits additional properties: {label}",
        )
        if node.get("type") == "object":
            require(
                node.get("additionalProperties") is False,
                f"schema object is not closed: {label}",
            )
        for key, value in node.items():
            walk_schema(value, f"{label}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            walk_schema(value, f"{label}[{index}]")


def validate_control_documents(
    contract: Mapping[str, Any], status: Mapping[str, Any], successor: Mapping[str, Any]
) -> None:
    for label, document in (("contract", contract), ("status", status), ("successor", successor)):
        require(document.get("status") == STATUS, f"{label} status drift")
        require(document.get("decision") == DECISION, f"{label} decision drift")
    require(
        contract.get("stage")
        == "S21B_A0_NON_LIVE_PRESIGN_CLOSURE_AND_ROLE_ARTIFACT_EXISTENCE_AUDIT",
        "contract stage drift",
    )
    target = contract.get("target_binding")
    require(isinstance(target, dict), "contract target binding absent")
    expected_target = {
        "s21a_source_commit": SOURCE_COMMIT,
        "s21a_source_tree": SOURCE_TREE,
        "s21a_integration_commit": TARGET_COMMIT,
        "s21a_integration_tree": TARGET_TREE,
        "integration_first_parent": TARGET_PARENTS[0],
        "integration_second_parent": TARGET_PARENTS[1],
        "observed_integrated_archive_sha256": ARCHIVE_SHA256,
        "cargo_lock_sha256": CARGO_LOCK_SHA256,
    }
    require(
        all(target.get(key) == value for key, value in expected_target.items()),
        "contract target identity drift",
    )
    forbidden = contract.get("forbidden_outputs")
    require(isinstance(forbidden, dict), "contract forbidden outputs absent")
    require(
        forbidden.get("unsigned_final_subject_may_be_emitted") is False
        and forbidden.get("owner_signing_request_may_be_emitted") is False
        and forbidden.get("owner_signing_message_may_be_emitted") is False
        and forbidden.get("owner_private_key_may_be_requested_or_stored") is False
        and forbidden.get("owner_signature_may_be_requested") is False
        and forbidden.get("live_execution_may_begin") is False
        and forbidden.get("side_effects_unlocked") == "NONE",
        "contract output prohibition drift",
    )
    current_outputs = status.get("current_outputs")
    require(isinstance(current_outputs, dict), "status current outputs absent")
    require(
        current_outputs.get("unsigned_final_subject_present") is False
        and current_outputs.get("owner_signing_request_present") is False
        and current_outputs.get("owner_signing_message_present") is False
        and current_outputs.get("owner_private_key_present") is False
        and current_outputs.get("owner_signature_present") is False
        and current_outputs.get("execution_capability_present") is False
        and current_outputs.get("live_action_count") == 0
        and current_outputs.get("side_effects_unlocked") == "NONE",
        "status output boundary drift",
    )
    admission = successor.get("admission_decision")
    require(isinstance(admission, dict), "successor admission decision absent")
    require(
        admission.get("presign_closure_complete") is False
        and admission.get("unsigned_final_subject_generation_may_begin") is False
        and admission.get("owner_signature_may_be_requested") is False
        and admission.get("live_execution_may_begin") is False
        and admission.get("terminal_hard_lock") is True
        and admission.get("side_effects_unlocked") == "NONE",
        "successor hard-lock drift",
    )


def validate_fixture_semantics(fixture: Mapping[str, Any]) -> None:
    require(fixture.get("schema") == RECEIPT_SCHEMA_ID, "receipt schema id drift")
    require(fixture.get("packet_kind") == RECEIPT_KIND, "receipt kind drift")
    require(fixture.get("canonicalization") == CANONICALIZATION, "canonicalization drift")
    require(fixture.get("receipt_state") == RECEIPT_STATE, "receipt state drift")
    require(fixture.get("test_only") is True and fixture.get("synthetic") is True, "KAT mode drift")
    hashing = fixture.get("hashing_contract")
    require(isinstance(hashing, dict), "hashing contract absent")
    require(
        hashing.get("digest_domain") == RECEIPT_DOMAIN
        and hashing.get("digest_framing") == FRAMING
        and hashing.get("self_hash_field") == SELF_HASH_FIELD
        and hashing.get("self_hash_field_excluded") is True
        and hashing.get("candidate_reported_matches_authoritative") is False,
        "hashing contract drift",
    )
    target = fixture.get("target_binding")
    require(isinstance(target, dict), "receipt target binding absent")
    expected_target = {
        "s21a_source_commit": SOURCE_COMMIT,
        "s21a_source_tree": SOURCE_TREE,
        "s21a_integration_commit": TARGET_COMMIT,
        "s21a_integration_tree": TARGET_TREE,
        "integration_first_parent": TARGET_PARENTS[0],
        "integration_second_parent": TARGET_PARENTS[1],
        "observed_integrated_archive_sha256": ARCHIVE_SHA256,
        "cargo_lock_sha256": CARGO_LOCK_SHA256,
    }
    require(
        all(target.get(key) == value for key, value in expected_target.items()),
        "receipt target identity drift",
    )
    verification = fixture.get("target_verification")
    require(isinstance(verification, dict), "target verification absent")
    require(
        all(value is False for value in verification.values()),
        "synthetic receipt claims real target verification",
    )
    roles = fixture.get("role_artifact_audit")
    require(isinstance(roles, dict), "role artifact audit absent")
    require(
        roles.get("required_role_artifact_count") == 4
        and roles.get("existing_required_role_artifact_count") == 0
        and roles.get("unrelated_backfill_embeddings_is_role_artifact") is False
        and roles.get("private_library_or_test_binary_is_role_artifact") is False
        and roles.get("arbitrary_nonzero_digest_may_substitute_for_missing_artifact") is False,
        "role artifact audit boundary drift",
    )
    for role in ("controller", "observer", "runner", "validator"):
        item = roles.get(role)
        require(isinstance(item, dict), f"role audit absent: {role}")
        require(
            item.get("required_artifact_name") == role
            and item.get("cargo_binary_declared") is False
            and item.get("declared_cargo_target") is None
            and item.get("exact_artifact_path") is None
            and item.get("artifact_exists") is False
            and item.get("artifact_sha256") is None
            and item.get("build_recipe_sha256") is None
            and item.get("independent_rebuild_count") == 0,
            f"missing role is presented as an artifact: {role}",
        )
    closure = fixture.get("reproducible_closure_audit")
    require(isinstance(closure, dict), "reproducible closure audit absent")
    require(
        all(value is False or value is None for value in closure.values()),
        "synthetic receipt claims reproducible closure",
    )
    outputs = fixture.get("forbidden_outputs")
    require(isinstance(outputs, dict), "forbidden outputs absent")
    require(
        all(value is False or value is None for value in outputs.values()),
        "synthetic receipt carries a forbidden output",
    )
    result = fixture.get("result")
    require(isinstance(result, dict), "receipt result absent")
    require(
        result.get("stage_status") == STATUS
        and result.get("presign_closure_complete") is False
        and result.get("terminal_hard_lock") is True
        and result.get("owner_interaction_required_now") is False
        and result.get("unsigned_final_subject_may_be_generated") is False
        and result.get("owner_signature_may_be_requested") is False
        and result.get("live_execution_may_begin") is False
        and result.get("side_effects_unlocked") == "NONE",
        "receipt result boundary drift",
    )
    nonclaims = fixture.get("nonclaims")
    require(isinstance(nonclaims, dict), "receipt nonclaims absent")
    require(
        all(value is False or value == "NONE" for value in nonclaims.values()),
        "receipt nonclaim drift",
    )


def verify_fixture(
    raw: bytes, fixture: Mapping[str, Any], validator: Draft202012Validator
) -> str:
    require(raw == canonical_bytes(fixture) + b"\n", "receipt is not canonical JSON plus one LF")
    errors = sorted(validator.iter_errors(fixture), key=lambda error: list(error.path))
    require(not errors, f"receipt schema rejection: {[error.message for error in errors[:2]]}")
    candidate = dict(fixture)
    reported = candidate.pop(SELF_HASH_FIELD, None)
    require(isinstance(reported, str) and HEX_64.fullmatch(reported), "receipt self digest malformed")
    recomputed = framed_digest(RECEIPT_DOMAIN, canonical_bytes(candidate))
    require(reported == recomputed, "receipt self digest mismatch")
    validate_fixture_semantics(fixture)
    return recomputed


def reseal_fixture(fixture: Mapping[str, Any]) -> bytes:
    candidate = copy.deepcopy(dict(fixture))
    candidate.pop(SELF_HASH_FIELD, None)
    candidate[SELF_HASH_FIELD] = framed_digest(RECEIPT_DOMAIN, canonical_bytes(candidate))
    return canonical_bytes(candidate) + b"\n"


def mutate_path(value: dict[str, Any], path: tuple[str, ...], replacement: Any) -> None:
    cursor: Any = value
    for key in path[:-1]:
        require(isinstance(cursor, dict) and key in cursor, f"mutation path absent: {path}")
        cursor = cursor[key]
    require(isinstance(cursor, dict) and path[-1] in cursor, f"mutation leaf absent: {path}")
    cursor[path[-1]] = replacement


def run_self_tests(
    fixture: dict[str, Any], validator: Draft202012Validator, seed: int
) -> int:
    mutations: list[tuple[str, tuple[str, ...], Any]] = [
        ("state", ("receipt_state",), "BLOCKED_MISSING_FOUR_ROLE_ARTIFACTS_AND_REBUILD_CLOSURES"),
        ("test-only", ("test_only",), False),
        ("synthetic", ("synthetic",), False),
        ("target-commit", ("target_binding", "s21a_integration_commit"), "f" * 40),
        ("target-tree", ("target_binding", "s21a_integration_tree"), "e" * 40),
        ("archive", ("target_binding", "observed_integrated_archive_sha256"), "f" * 64),
        ("lock", ("target_binding", "cargo_lock_sha256"), "e" * 64),
        ("verified", ("target_verification", "two_parent_topology_independently_verified"), True),
        ("role-count", ("role_artifact_audit", "existing_required_role_artifact_count"), 1),
        ("controller-declared", ("role_artifact_audit", "controller", "cargo_binary_declared"), True),
        ("observer-exists", ("role_artifact_audit", "observer", "artifact_exists"), True),
        ("runner-path", ("role_artifact_audit", "runner", "exact_artifact_path"), "/tmp/runner"),
        ("validator-digest", ("role_artifact_audit", "validator", "artifact_sha256"), "d" * 64),
        ("test-binary-role", ("role_artifact_audit", "private_library_or_test_binary_is_role_artifact"), True),
        ("arbitrary-digest", ("role_artifact_audit", "arbitrary_nonzero_digest_may_substitute_for_missing_artifact"), True),
        ("toolchain", ("reproducible_closure_audit", "toolchain_manifest_definition_present"), True),
        ("first-rebuild", ("reproducible_closure_audit", "first_clean_archive_rebuild_completed"), True),
        ("rebuild-match", ("reproducible_closure_audit", "independent_rebuild_outputs_match"), True),
        ("subject", ("forbidden_outputs", "final_unsigned_subject_present"), True),
        ("message", ("forbidden_outputs", "owner_signing_request_present"), True),
        ("private-key", ("forbidden_outputs", "owner_private_key_present"), True),
        ("signature", ("forbidden_outputs", "detached_owner_signature_present"), True),
        ("permit", ("forbidden_outputs", "execution_capability_present"), True),
        ("closure", ("result", "presign_closure_complete"), True),
        ("owner-interaction", ("result", "owner_interaction_required_now"), True),
        ("owner-signature-request", ("result", "owner_signature_may_be_requested"), True),
        ("live", ("result", "live_execution_may_begin"), True),
        ("side-effects", ("result", "side_effects_unlocked"), "LIVE"),
    ]
    random.Random(seed).shuffle(mutations)
    for label, path, replacement in mutations:
        mutated = copy.deepcopy(fixture)
        mutate_path(mutated, path, replacement)
        raw = reseal_fixture(mutated)
        parsed = parse_json(raw, f"mutation:{label}")
        try:
            verify_fixture(raw, parsed, validator)
        except CheckFailure:
            continue
        raise CheckFailure(f"unsafe receipt mutation accepted: {label}")

    malformed = (
        canonical_bytes(fixture),
        canonical_bytes(fixture) + b"\n\n",
        json.dumps(fixture, indent=2, sort_keys=True).encode("ascii") + b"\n",
    )
    for index, raw in enumerate(malformed):
        parsed = parse_json(raw, f"noncanonical:{index}")
        try:
            verify_fixture(raw, parsed, validator)
        except CheckFailure:
            continue
        raise CheckFailure(f"noncanonical receipt accepted: {index}")
    corrupted = copy.deepcopy(fixture)
    corrupted[SELF_HASH_FIELD] = "f" * 64
    raw = canonical_bytes(corrupted) + b"\n"
    try:
        verify_fixture(raw, corrupted, validator)
    except CheckFailure:
        pass
    else:
        raise CheckFailure("corrupted self digest accepted")
    unknown = copy.deepcopy(fixture)
    unknown["unexpected"] = False
    raw = reseal_fixture(unknown)
    try:
        verify_fixture(raw, parse_json(raw, "unknown-field"), validator)
    except CheckFailure:
        pass
    else:
        raise CheckFailure("unknown receipt field accepted")
    return len(mutations) + len(malformed) + 2


def audit_documents(repo: Path, run_mutations: bool, seed: int) -> DocumentAudit:
    contract_raw, contract = load_repo_json(repo, CONTRACT_PATH)
    status_raw, status = load_repo_json(repo, STATUS_PATH)
    schema_raw, schema = load_repo_json(repo, SCHEMA_PATH)
    fixture_raw, fixture = load_repo_json(repo, FIXTURE_PATH)
    successor_raw, successor = load_repo_json(repo, SUCCESSOR_PATH)
    require(
        schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
        "receipt schema draft drift",
    )
    require(schema.get("$id") == RECEIPT_SCHEMA_ID, "receipt schema id drift")
    walk_schema(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise CheckFailure(f"Draft 2020-12 schema invalid: {exc.message}") from exc
    definitions = schema.get("$defs")
    require(isinstance(definitions, dict), "receipt schema definitions absent")
    require(
        definitions.get("sha256", {}).get("pattern") == r"^(?!0{64}$)[0-9a-f]{64}$"
        and definitions.get("git_oid", {}).get("pattern") == r"^(?!0{40}$)[0-9a-f]{40}$",
        "receipt schema permits zero or malformed security identity",
    )
    validator = Draft202012Validator(schema)
    fixture_self = verify_fixture(fixture_raw, fixture, validator)
    validate_control_documents(contract, status, successor)
    mutation_count = run_self_tests(fixture, validator, seed) if run_mutations else 33
    return DocumentAudit(
        contract_sha256=sha256(contract_raw),
        status_sha256=sha256(status_raw),
        schema_sha256=sha256(schema_raw),
        fixture_sha256=sha256(fixture_raw),
        fixture_self_sha256=fixture_self,
        successor_sha256=sha256(successor_raw),
        self_test_mutation_count=mutation_count,
    )


def render(rows: list[tuple[str, str]]) -> str:
    require(len(rows) == len({key for key, _ in rows}), "duplicate TSV row key")
    for key, value in rows:
        require("\t" not in key + value and "\n" not in key + value, "invalid TSV field")
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def minimal_rows(audit: GitAudit, documents: DocumentAudit) -> list[tuple[str, str]]:
    return [
        ("stage", STAGE),
        ("status", STATUS),
        ("decision", DECISION),
        ("mode", MODE),
        ("target_commit", TARGET_COMMIT),
        ("target_tree", audit.target_tree),
        ("target_first_parent", audit.target_parents[0]),
        ("target_second_parent", audit.target_parents[1]),
        ("source_commit", SOURCE_COMMIT),
        ("source_tree", audit.source_tree),
        ("source_parent_commit", SOURCE_PARENT),
        ("source_parent_tree", SOURCE_PARENT_TREE),
        ("integrated_archive_sha256", audit.archive_sha256),
        ("integrated_archive_byte_count", str(audit.archive_byte_count)),
        ("cargo_lock_sha256", audit.cargo_lock_sha256),
        ("cargo_manifest_count", str(audit.cargo_manifest_count)),
        ("cargo_binary_target_count", str(len(audit.cargo_binary_targets))),
        ("cargo_binary_target_set_sha256", audit.cargo_binary_target_set_sha256),
        ("required_role_binary_count", str(len(REQUIRED_ROLE_BINARIES))),
        ("required_role_binary_present_count", "0"),
        ("required_role_binary_missing_count", str(len(audit.missing_role_binaries))),
        ("controller_binary_target", "ABSENT"),
        ("observer_binary_target", "ABSENT"),
        ("runner_binary_target", "ABSENT"),
        ("validator_binary_target", "ABSENT"),
        ("receipt_schema_id", RECEIPT_SCHEMA_ID),
        ("receipt_schema_sha256", documents.schema_sha256),
        ("blocked_fixture_sha256", documents.fixture_sha256),
        ("blocked_fixture_self_sha256", documents.fixture_self_sha256),
        ("contract_sha256", documents.contract_sha256),
        ("status_sha256", documents.status_sha256),
        ("successor_gate_sha256", documents.successor_sha256),
        ("self_test_mutation_count", str(documents.self_test_mutation_count)),
        ("candidate_digest_strings_authoritative", "false"),
        ("external_owner_private_key_read", "false"),
        ("owner_signature_artifact_generated", "false"),
        ("signable_subject_emitted", "false"),
        ("signing_message_emitted", "false"),
        ("live_canary", "NOT_RUN"),
        ("side_effects_unlocked", "NONE"),
        ("gate", "BLOCKED_PRESIGN_CLOSURE_AUDIT_PASS_NON_LIVE_ONLY"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--seed", type=int, default=21_100)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    require(repo.is_dir() and not repo.is_symlink(), "repository root is not canonical")
    audit = audit_git(repo)
    documents = audit_documents(repo, args.self_test, args.seed)
    sys.stdout.write(render(minimal_rows(audit, documents)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as exc:
        print(f"S21B-A0 pre-sign closure checker failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
