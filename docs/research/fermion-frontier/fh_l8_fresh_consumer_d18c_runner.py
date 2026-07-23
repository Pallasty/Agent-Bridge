#!/usr/bin/env python3
"""Fresh-exclusive, bounded packed-q3 consumer for FH-L8 D18-C.

This implementation can act on exactly the first 4,096 records of the
committed packed-q3 checkpoint, but only after a separately committed contract
explicitly authorizes that bounded action.  It never consumes the legacy D11
spool or target.
"""
from __future__ import annotations

import argparse
import array
import fcntl
import hashlib
import json
import os
import re
import resource
import shutil
import stat
import struct
import subprocess
import sys
import time
import types
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
REL_PREFIX = "docs/research/fermion-frontier/"
RUNNER_NAME = "fh_l8_fresh_consumer_d18c_runner.py"
CHECKER_NAME = "fh_l8_fresh_consumer_d18c_checker.py"
LAUNCHER_NAME = "fh_l8_fresh_consumer_d18c_launcher.py"
TEST_NAME = "test_fh_l8_fresh_consumer_d18c.py"
CONTRACT_NAME = "fh_l8_fresh_consumer_d18c_contract.json"
RESULT_NAME = "fh_l8_fresh_consumer_d18c_result.json"
SOURCE_NAME = "fh_l8_packed_q3_checkpoint_d11_bundle/checkpoint.bin"
D5_NAME = "fh_l8_symmetry_orbit_quotient_d5_checker.py"
D5_CONTRACT_NAME = "fh_l8_symmetry_orbit_quotient_d5_contract.json"
D4_NAME = "fh_l8_scalar_supremum_d4_checker.py"
BACKEND_NAME = "hubbard_strang_commutator_checker.py"
D16_RESULT_NAME = "fh_l8_packed_consumer_forensic_d16_result.json"
D17_CONTRACT_NAME = "fh_l8_vector_custody_d17_contract.json"
D17_RESULT_NAME = "fh_l8_vector_custody_d17_result.json"
D11_RESULT_NAME = "fh_l8_packed_q3_checkpoint_d11_bundle/result.json"
D11_RECEIPT_NAME = "fh_l8_packed_q3_checkpoint_d11_terminal_receipt.json"
D18_RESULT_NAME = "fh_l8_clean_q3_preflight_d18_result.json"

RUNNER_PATH = HERE / RUNNER_NAME
CHECKER_PATH = HERE / CHECKER_NAME
LAUNCHER_PATH = HERE / LAUNCHER_NAME
TEST_PATH = HERE / TEST_NAME
CONTRACT_PATH = HERE / CONTRACT_NAME
RESULT_PATH = HERE / RESULT_NAME
SOURCE_PATH = HERE / SOURCE_NAME
D5_PATH = HERE / D5_NAME

CONTRACT_ID = "FH-L8-INDEPENDENT-REFERENCE-D18-C-FRESH-CONSUMER-V1"
SOURCE_RECORD = struct.Struct(">16sqBBHI")
SPILL_RECORD = struct.Struct(">16sqQ")
SOURCE_RECORDS = 213_099
BOUNDED_ROWS = 4_096
PARTITIONS = 256
SHA256_RE = re.compile(r"[0-9a-f]{64}")
SHA1_RE = re.compile(r"[0-9a-f]{40}")
PACKED_C3_COMMIT = "784f01b8e3c589b7c6ab25773f93937d5a1344f8"
PACKED_BLOB = "c71a85fd8ad1787e007da4576dbbe29f1f189e82"
PACKED_SHA256 = "db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231"
PACKED_RESULT_SHA256 = "f372a2eedabfc57d049d6a8c6d0609c1b7bcf25aae760353699916a6f1bc4bf5"
PACKED_RECEIPT_SHA256 = "deafacbcbb77885353254306200137c7248321641b0eb197494d5cbd0d3a9ab2"
PACKED_SHARD_MANIFEST_SHA256 = (
    "c2b4586ed67c4e3b4fd029bc96c3004bfb313fd12e6330a5c24353bed9c60dfb"
)
FIRST_4096_RAW_SHA256 = "77bbed3b7a5244bf789fd3652b351d59d1045db238637f4ddc6cfa146ab41e33"
FIRST_4096_PROJECTION_SHA256 = (
    "99d1ea17d1dedb08bcb65b5de5875088b96c638e1bf6d42b8b9ada7f20da7c31"
)
D5_SHA256 = "681bc63fedce8b71cfb536c66d321467bc8f01cb5947bee59b4291e2ac51a022"
EXPECTED_KERNEL_SOURCE_PINS = [
    {
        "path": D5_NAME,
        "sha256": D5_SHA256,
    },
    {
        "path": D5_CONTRACT_NAME,
        "sha256": "1ebd1d38c0c40ca9617f86e09c86d528196260dd6b6b6692c34dacfe7a28d392",
    },
    {
        "path": D4_NAME,
        "sha256": "86692e68cee1475d3cee2dbd0e866f68d5c5514ff37268c601819bd8f4ed48f2",
    },
    {
        "path": BACKEND_NAME,
        "sha256": "e3144590c0e00bb2bd69bc50b1bdf3d7d6c3043c8697d5050202404590138fa7",
    },
]
D16_RESULT_SHA256 = "686043604180a195a2924c72215b1d23ef80b7765f0d7ddd51eba7fcef604501"
D17_CONTRACT_SHA256 = "7bcf51180e372509669dd5e1730e8460e76e496e7ecf5a2fa2c8fefd8de0da73"
D17_RESULT_SHA256 = "11d3ccc2f8bb1b194de78c9433ffdc9be6ff36b9cbcbcb7debd9c2f8c480c473"
D18_RESULT_COMMIT = "51643e67fbb33148b231a4bf1251923c621fd11b"
D18_RESULT_SHA256 = "7fa505485fc718db39d9918ec459094f3766f014fd2ddee7d108f01fae4842c4"
EXPECTED_LIMITS = {
    "cgroup_path_component": "ab-fh-l8-d18c",
    "memory_max": "536870912",
    "memory_high": "402653184",
    "memory_swap_max": "0",
    "max_initial_memory_peak_bytes": 67_108_864,
    "max_final_memory_peak_bytes": 335_544_320,
    "max_process_peak_rss_bytes": 301_989_888,
    "max_spill_bytes": 40_000_000,
    "max_target_bytes": 16_777_216,
    "max_manifest_bytes": 262_144,
    "max_receipt_bytes": 262_144,
    "internal_deadline_seconds": 180,
    "read_chunk_bytes": 1_048_576,
    "maximum_runner_created_regular_files": 261,
    "maximum_final_external_regular_files": 264,
}
EXPECTED_COMPARATOR = {
    "d18_result_commit": D18_RESULT_COMMIT,
    "d18_result_sha256": D18_RESULT_SHA256,
    "d18_execution_authority_admitted": False,
    "role": "PREREGISTERED_NON_AUTHORITATIVE_REPRODUCIBILITY_GUARD",
    "mismatch_is_preflight_no_go": True,
    "legacy_observation_is_authority": False,
    "target_records": 424_682,
    "target_bytes": 13_589_824,
    "target_sha256": "8b43b76f1e7a45f12e220905bcba41dc7cfef9fce66f0257cb3c9dff9623fa5f",
    "spill_records": 868_786,
    "reduced_columns": 868_786,
    "projected_zero_outputs": 22,
    "partition_count": PARTITIONS,
}
EXPECTED_DECISION_RULE = {
    "verified": "VERIFIED_D18C_FRESH_EXCLUSIVE_PACKED_Q3_BOUNDED_4096_PREFLIGHT",
    "resource_or_timeout": "NO_GO_D18C_RESOURCE_ENVELOPE_OR_TIMEOUT",
    "identity_or_custody_failure": "NO_GO_D18C_IDENTITY_OR_CUSTODY",
    "arithmetic_or_equivalence_failure": "NO_GO_D18C_ARITHMETIC_OR_EQUIVALENCE",
    "diagnostic_reproducibility_mismatch": (
        "NO_GO_D18C_DIAGNOSTIC_REPRODUCIBILITY_MISMATCH"
    ),
    "next_gate": "CLEAN_BOUNDED_PREFLIGHT_REVIEW_AND_FULL_53_SHARD_AUTHORIZATION_DECISION",
}
EXPECTED_LIMITATIONS = [
    "D18-C acts on 4,096 unique sorted packed-q3 source rows; 4,096 spill evaluations plus 4,096 validation-replay evaluations produce exactly 8,192 _reduced_column calls, and no call uses any of the remaining 209,003 rows.",
    "The resulting bounded partial vector is not a complete q4 vector and is forbidden as a q4, contraction, q5, or downstream numerical operand.",
    "The original D18 observation is not admitted as scientific authority; its frozen count/bytes/digest serve only as a preregistered reproducibility guard, whose mismatch conservatively prevents a VERIFIED D18-C outcome.",
    "The runner resource snapshot ends immediately before its terminal-receipt publication; a separately frozen launcher must attest runner exit and post-publication systemd MemoryPeak.",
    "The second-pass naïve comparison re-evaluates all 4,096 rows but uses the same frozen scientific _reduced_column kernel; it independently checks consumer aggregation and publication, not the scientific kernel itself.",
    "The D16-W full-H numerical branch and D12-D13 numerical conclusions remain without clean input authority; only their explicitly abstract design observations remain design-only.",
    "No full 53-shard run, q5 action, degree-six remainder, cumulative error, full-R100 error, physical reference, hardware result, quantum advantage, or READY conclusion is authorized.",
]


class RunnerError(ValueError):
    """A frozen identity, resource, custody, or arithmetic condition failed."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> None:
    raise RunnerError(code, message)


def _duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("JSON_DUPLICATE_KEY", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    _fail("JSON_NONFINITE", f"non-finite JSON constant: {value}")


def _reject_float(value: str) -> Any:
    _fail("JSON_FLOAT", f"floating-point JSON number forbidden: {value}")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_object,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except RunnerError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("JSON_INVALID", f"cannot load {path.name}: {exc}")
    if not isinstance(value, dict):
        _fail("JSON_SCHEMA", f"{path.name} root must be an object")
    return value


def _load_legacy_d18_observation(
    path: Path, expected_sha256: str
) -> dict[str, Any]:
    """Read the hash-pinned legacy D18 record without using its float field."""
    try:
        raw = path.read_bytes()
        if len(raw) > 262_144:
            _fail("JSON_OVERSIZE", "legacy D18 observation exceeds cap")
        if (
            SHA256_RE.fullmatch(expected_sha256) is None
            or hashlib.sha256(raw).hexdigest() != expected_sha256
        ):
            _fail("SOURCE_AUTHORITY", "legacy D18 observation identity drift")
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_object,
            parse_constant=_reject_constant,
            # The legacy elapsed-seconds diagnostic is irrelevant to every
            # admitted field below. Preserve any finite decimal token as an
            # opaque string so it cannot enter D18-C arithmetic.
            parse_float=lambda token: token,
        )
    except RunnerError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("JSON_INVALID", f"cannot load legacy D18 observation: {exc}")
    if not isinstance(value, dict):
        _fail("JSON_SCHEMA", "legacy D18 observation root must be an object")
    return value


def _canonical_json(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
            + b"\n"
        )
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        _fail("JSON_CANONICALIZATION", str(exc))


def _exact_keys(value: Mapping[str, Any], keys: Iterable[str], label: str) -> None:
    expected = set(keys)
    if set(value) != expected:
        _fail("CONTRACT_SCHEMA", f"{label} keys drift")


def _strict_int(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail("CONTRACT_SCHEMA", f"{label} must be an integer >= {minimum}")
    return value


def _strict_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        _fail("CONTRACT_SCHEMA", f"{label} must be a boolean")
    return value


def _strict_sha(value: Any, label: str, sha1: bool = False) -> str:
    pattern = SHA1_RE if sha1 else SHA256_RE
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _fail("CONTRACT_SCHEMA", f"{label} must be a canonical hash")
    return value


def _sha_file(path: Path, maximum_bytes: int | None = None) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    try:
        with path.open("rb", buffering=0) as handle:
            while True:
                block = handle.read(1 << 20)
                if not block:
                    break
                total += len(block)
                if maximum_bytes is not None and total > maximum_bytes:
                    _fail("ARTIFACT_OVERSIZE", f"{path.name} exceeds byte cap")
                digest.update(block)
    except RunnerError:
        raise
    except OSError as exc:
        _fail("ARTIFACT_READ", f"cannot hash {path.name}: {exc}")
    return total, digest.hexdigest()


def _git(*args: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), *args], stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError as exc:
        _fail("GIT_IDENTITY", f"git identity query failed: {' '.join(args)}")


def _git_path_exists(commit: str, relative: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-tree", commit, "--", relative],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode:
        _fail("GIT_IDENTITY", "git path-existence query failed")
    return bool(completed.stdout.strip())


def _head() -> str:
    return _git("rev-parse", "HEAD^{commit}").decode("ascii").strip()


def _git_blob(commit: str, relative: str) -> dict[str, Any]:
    line = _git("ls-tree", commit, relative).decode("ascii").strip()
    fields = line.split()
    if len(fields) < 3 or fields[1] != "blob":
        _fail("GIT_IDENTITY", f"missing Git blob: {relative}")
    size = int(_git("cat-file", "-s", f"{commit}:{relative}"))
    return {"mode": fields[0], "blob": fields[2], "bytes": size}


def _require_clean_execution_tree(contract: Mapping[str, Any]) -> str:
    chronology = contract["chronology"]
    head = _head()
    contract_commit = head
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        _fail("EXECUTION_TREE_DIRTY", "official action requires a clean worktree")
    entries = _git(
        "diff-tree", "--no-commit-id", "--name-status", "-r", contract_commit
    ).decode("utf-8").splitlines()
    expected = [f"A\t{REL_PREFIX}{CONTRACT_NAME}"]
    if entries != expected:
        _fail("CHRONOLOGY_DRIFT", "contract freeze must add only the contract")
    parent = _git("rev-parse", f"{contract_commit}^").decode("ascii").strip()
    if parent != chronology["implementation_freeze_commit"]:
        _fail("CHRONOLOGY_DRIFT", "contract parent is not implementation freeze")
    if _git_path_exists(parent, f"{REL_PREFIX}{CONTRACT_NAME}"):
        _fail("CHRONOLOGY_DRIFT", "contract existed before authorization freeze")
    if _git_path_exists(parent, f"{REL_PREFIX}{RESULT_NAME}"):
        _fail("CHRONOLOGY_DRIFT", "result existed before authorization freeze")
    return contract_commit


def _verify_execution_head(frozen_head: str, phase: str) -> None:
    if _head() != frozen_head:
        _fail("EXECUTION_TREE_TOCTOU", f"execution HEAD changed at {phase}")
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        _fail("EXECUTION_TREE_TOCTOU", f"worktree changed at {phase}")


def _verify_contract_bytes(contract: Mapping[str, Any]) -> None:
    expected = _canonical_json(contract)
    try:
        frozen = CONTRACT_PATH.read_bytes()
    except OSError as exc:
        _fail("CONTRACT_IDENTITY", f"cannot read frozen contract: {exc}")
    if frozen != expected:
        _fail(
            "CONTRACT_IDENTITY",
            "loaded contract is not byte-identical to canonical frozen contract",
        )
    head = _head()
    identity = _git_blob(head, f"{REL_PREFIX}{CONTRACT_NAME}")
    if identity["mode"] != "100644" or identity["bytes"] != len(frozen):
        _fail("CONTRACT_IDENTITY", "frozen contract Git mode/size drift")
    blob_bytes = _git("cat-file", "blob", identity["blob"])
    if blob_bytes != frozen:
        _fail("CONTRACT_IDENTITY", "working contract differs from HEAD blob")


def _validate_contract(contract: Mapping[str, Any]) -> None:
    _exact_keys(
        contract,
        (
            "schema_version",
            "contract_id",
            "analysis_class",
            "chronology",
            "implementation",
            "source_authority",
            "execution_authorization",
            "consumer_protocol",
            "resource_limits",
            "diagnostic_comparator",
            "decision_rule",
            "authority_ceiling",
            "limitations",
        ),
        "contract",
    )
    if _strict_int(contract["schema_version"], "schema_version") != 1:
        _fail("CONTRACT_SCHEMA", "schema version drift")
    if contract["contract_id"] != CONTRACT_ID:
        _fail("CONTRACT_ID", "contract id drift")
    if contract["analysis_class"] != "PREREGISTERED_BOUNDED_SCIENTIFIC_ACTION":
        _fail("CONTRACT_SCHEMA", "analysis class drift")

    chronology = contract["chronology"]
    _exact_keys(
        chronology,
        (
            "evidence_baseline_commit",
            "implementation_freeze_commit",
            "contract_must_be_execution_head",
            "checker_and_runner_precede_contract",
            "result_absent_through_contract",
        ),
        "chronology",
    )
    for key in (
        "evidence_baseline_commit",
        "implementation_freeze_commit",
    ):
        _strict_sha(chronology[key], f"chronology.{key}", sha1=True)
    if not _strict_bool(
        chronology["contract_must_be_execution_head"],
        "contract_must_be_execution_head",
    ):
        _fail("CONTRACT_SCHEMA", "contract must be the execution HEAD")
    if not _strict_bool(
        chronology["checker_and_runner_precede_contract"],
        "checker_and_runner_precede_contract",
    ):
        _fail("CONTRACT_SCHEMA", "checker/runner chronology not authorized")
    if not _strict_bool(
        chronology["result_absent_through_contract"],
        "result_absent_through_contract",
    ):
        _fail("CONTRACT_SCHEMA", "result chronology not authorized")

    implementation = contract["implementation"]
    _exact_keys(
        implementation, ("runner", "checker", "launcher", "test"), "implementation"
    )
    for label, expected_name in (
        ("runner", RUNNER_NAME),
        ("checker", CHECKER_NAME),
        ("launcher", LAUNCHER_NAME),
        ("test", TEST_NAME),
    ):
        item = implementation[label]
        _exact_keys(item, ("path", "mode", "blob", "bytes", "sha256"), label)
        if item["path"] != expected_name or item["mode"] != "100644":
            _fail("CONTRACT_SCHEMA", f"{label} path/mode drift")
        _strict_sha(item["blob"], f"{label}.blob", sha1=True)
        _strict_int(item["bytes"], f"{label}.bytes", 1)
        _strict_sha(item["sha256"], f"{label}.sha256")

    source = contract["source_authority"]
    _exact_keys(
        source,
        (
            "packed_c3_commit",
            "packed_checkpoint",
            "packed_result_sha256",
            "packed_terminal_receipt_sha256",
            "packed_shard_manifest_sha256",
            "first_4096_raw_sha256",
            "first_4096_projection_sha256",
            "d5_checker_sha256",
            "kernel_source_pins",
            "d16_forensic_result_sha256",
            "d17_contract_sha256",
            "d17_result_sha256",
            "legacy_spool_or_target_permitted",
        ),
        "source_authority",
    )
    _strict_sha(source["packed_c3_commit"], "packed_c3_commit", sha1=True)
    packed = source["packed_checkpoint"]
    _exact_keys(
        packed,
        ("path", "mode", "blob", "bytes", "records", "record_bytes", "sha256"),
        "packed_checkpoint",
    )
    if (
        packed["path"] != SOURCE_NAME
        or packed["mode"] != "100644"
        or _strict_int(packed["bytes"], "packed.bytes") != SOURCE_RECORDS * SOURCE_RECORD.size
        or _strict_int(packed["records"], "packed.records") != SOURCE_RECORDS
        or _strict_int(packed["record_bytes"], "packed.record_bytes") != SOURCE_RECORD.size
    ):
        _fail("CONTRACT_SCHEMA", "packed checkpoint dimensions drift")
    _strict_sha(packed["blob"], "packed.blob", sha1=True)
    for key in (
        "sha256",
        "packed_terminal_receipt_sha256",
        "packed_result_sha256",
        "packed_shard_manifest_sha256",
        "first_4096_raw_sha256",
        "first_4096_projection_sha256",
        "d5_checker_sha256",
        "d16_forensic_result_sha256",
        "d17_contract_sha256",
        "d17_result_sha256",
    ):
        value = packed[key] if key == "sha256" else source[key]
        _strict_sha(value, key)
    expected_source_scalars = {
        "packed_c3_commit": PACKED_C3_COMMIT,
        "packed_result_sha256": PACKED_RESULT_SHA256,
        "packed_terminal_receipt_sha256": PACKED_RECEIPT_SHA256,
        "packed_shard_manifest_sha256": PACKED_SHARD_MANIFEST_SHA256,
        "first_4096_raw_sha256": FIRST_4096_RAW_SHA256,
        "first_4096_projection_sha256": FIRST_4096_PROJECTION_SHA256,
        "d5_checker_sha256": D5_SHA256,
        "d16_forensic_result_sha256": D16_RESULT_SHA256,
        "d17_contract_sha256": D17_CONTRACT_SHA256,
        "d17_result_sha256": D17_RESULT_SHA256,
        "legacy_spool_or_target_permitted": False,
    }
    if any(source[key] != value for key, value in expected_source_scalars.items()):
        _fail("CONTRACT_SCHEMA", "source authority pin drift")
    if (
        packed["path"] != SOURCE_NAME
        or packed["mode"] != "100644"
        or packed["blob"] != PACKED_BLOB
        or packed["bytes"] != SOURCE_RECORDS * SOURCE_RECORD.size
        or packed["records"] != SOURCE_RECORDS
        or packed["record_bytes"] != SOURCE_RECORD.size
        or packed["sha256"] != PACKED_SHA256
    ):
        _fail("CONTRACT_SCHEMA", "packed checkpoint fixed identity drift")
    if source["kernel_source_pins"] != EXPECTED_KERNEL_SOURCE_PINS:
        _fail("CONTRACT_SCHEMA", "bounded kernel source pin set drift")
    if _strict_bool(
        source["legacy_spool_or_target_permitted"], "legacy_spool_or_target_permitted"
    ):
        _fail("CONTRACT_SCHEMA", "legacy spool/target must remain forbidden")

    authorization = contract["execution_authorization"]
    _exact_keys(
        authorization,
        (
            "bounded_preflight_execution_authorized",
            "authorized_unique_q3_rows",
            "authorized_row_start",
            "authorized_row_end_exclusive",
            "authorized_kernel_evaluations",
            "full_53_shard_execution_authorized",
        ),
        "execution_authorization",
    )
    if not _strict_bool(
        authorization["bounded_preflight_execution_authorized"],
        "bounded_preflight_execution_authorized",
    ):
        _fail("EXECUTION_NOT_AUTHORIZED", "bounded action is not authorized")
    if (
        _strict_int(authorization["authorized_unique_q3_rows"], "authorized rows")
        != BOUNDED_ROWS
        or _strict_int(authorization["authorized_row_start"], "authorized start") != 0
        or _strict_int(
            authorization["authorized_row_end_exclusive"], "authorized end"
        )
        != BOUNDED_ROWS
        or _strict_int(
            authorization["authorized_kernel_evaluations"], "authorized evaluations"
        )
        != BOUNDED_ROWS * 2
    ):
        _fail("CONTRACT_SCHEMA", "bounded action cardinality drift")
    if _strict_bool(
        authorization["full_53_shard_execution_authorized"],
        "full_53_shard_execution_authorized",
    ):
        _fail("CONTRACT_SCHEMA", "full execution must remain forbidden")

    protocol = contract["consumer_protocol"]
    _exact_keys(
        protocol,
        (
            "fresh_exclusive_scratch",
            "allowed_scratch_parent",
            "deny_filesystem_types",
            "exclusive_lock",
            "full_source_validation_before_action",
            "source_rehash_after_action",
            "partition_count",
            "partition_selector",
            "spill_record_bytes",
            "scaled_denominator",
            "manifest_only_merge",
            "atomic_no_replace_publication",
            "directory_fsync",
            "second_pass_naive_aggregation_replay",
            "bounded_output_is_full_q4_operand",
        ),
        "consumer_protocol",
    )
    for key in (
        "fresh_exclusive_scratch",
        "exclusive_lock",
        "full_source_validation_before_action",
        "source_rehash_after_action",
        "manifest_only_merge",
        "atomic_no_replace_publication",
        "directory_fsync",
        "second_pass_naive_aggregation_replay",
    ):
        if not _strict_bool(protocol[key], key):
            _fail("CONTRACT_SCHEMA", f"{key} must be true")
    if _strict_bool(
        protocol["bounded_output_is_full_q4_operand"],
        "bounded_output_is_full_q4_operand",
    ):
        _fail("CONTRACT_SCHEMA", "bounded output cannot be a full q4 operand")
    if (
        protocol["allowed_scratch_parent"] != "/Data/CascadeProjects/.ab-experiments"
        or protocol["deny_filesystem_types"] != ["ramfs", "tmpfs"]
        or _strict_int(protocol["partition_count"], "partition_count") != PARTITIONS
        or protocol["partition_selector"] != "SHA256(target_u128_be)[0]"
        or _strict_int(protocol["spill_record_bytes"], "spill_record_bytes")
        != SPILL_RECORD.size
        or _strict_int(protocol["scaled_denominator"], "scaled_denominator") != 8
    ):
        _fail("CONTRACT_SCHEMA", "consumer protocol drift")

    limits = contract["resource_limits"]
    _exact_keys(
        limits,
        (
            "cgroup_path_component",
            "memory_max",
            "memory_high",
            "memory_swap_max",
            "max_initial_memory_peak_bytes",
            "max_final_memory_peak_bytes",
            "max_process_peak_rss_bytes",
            "max_spill_bytes",
            "max_target_bytes",
            "max_manifest_bytes",
            "max_receipt_bytes",
            "internal_deadline_seconds",
            "read_chunk_bytes",
            "maximum_runner_created_regular_files",
            "maximum_final_external_regular_files",
        ),
        "resource_limits",
    )
    if limits != EXPECTED_LIMITS:
        _fail("CONTRACT_SCHEMA", "resource limits drift")
    for key in (
        "max_initial_memory_peak_bytes",
        "max_final_memory_peak_bytes",
        "max_process_peak_rss_bytes",
        "max_spill_bytes",
        "max_target_bytes",
        "max_manifest_bytes",
        "max_receipt_bytes",
        "internal_deadline_seconds",
        "read_chunk_bytes",
        "maximum_runner_created_regular_files",
        "maximum_final_external_regular_files",
    ):
        _strict_int(limits[key], key, 1)

    comparator = contract["diagnostic_comparator"]
    _exact_keys(
        comparator,
        (
            "d18_result_commit",
            "d18_result_sha256",
            "d18_execution_authority_admitted",
            "role",
            "mismatch_is_preflight_no_go",
            "legacy_observation_is_authority",
            "target_records",
            "target_bytes",
            "target_sha256",
            "spill_records",
            "reduced_columns",
            "projected_zero_outputs",
            "partition_count",
        ),
        "diagnostic_comparator",
    )
    _strict_sha(comparator["d18_result_commit"], "d18_result_commit", sha1=True)
    _strict_sha(comparator["d18_result_sha256"], "d18_result_sha256")
    if _strict_bool(
        comparator["d18_execution_authority_admitted"],
        "d18_execution_authority_admitted",
    ):
        _fail("CONTRACT_SCHEMA", "D18 execution authority cannot be admitted")
    if comparator["role"] != "PREREGISTERED_NON_AUTHORITATIVE_REPRODUCIBILITY_GUARD":
        _fail("CONTRACT_SCHEMA", "diagnostic comparator role drift")
    if not _strict_bool(
        comparator["mismatch_is_preflight_no_go"],
        "mismatch_is_preflight_no_go",
    ):
        _fail("CONTRACT_SCHEMA", "diagnostic mismatch must fail closed")
    if _strict_bool(
        comparator["legacy_observation_is_authority"],
        "legacy_observation_is_authority",
    ):
        _fail("CONTRACT_SCHEMA", "legacy observation cannot be authority")
    _strict_int(comparator["target_records"], "comparator.target_records", 1)
    _strict_int(comparator["target_bytes"], "comparator.target_bytes", 1)
    _strict_sha(comparator["target_sha256"], "comparator.target_sha256")
    _strict_int(comparator["spill_records"], "comparator.spill_records", 1)
    _strict_int(comparator["reduced_columns"], "comparator.reduced_columns", 1)
    _strict_int(
        comparator["projected_zero_outputs"],
        "comparator.projected_zero_outputs",
    )
    _strict_int(comparator["partition_count"], "comparator.partition_count", 1)
    if comparator != EXPECTED_COMPARATOR:
        _fail("CONTRACT_SCHEMA", "diagnostic comparator drift")

    ceiling = contract["authority_ceiling"]
    required_false = {
        "full_q4_target_materialized",
        "bounded_output_admissible_as_q4_operand",
        "d12_d13_numeric_authority_restored",
        "d16w_full_h_numeric_authority",
        "full_53_shard_executed",
        "full_53_shard_authorization_granted",
        "runner_terminal_receipt_publication_self_attested",
        "q5_executed",
        "degree6_remainder_bounded",
        "two_step_cumulative_error_bounded",
        "full_R100_error_bounded",
        "physical_reference_qualified",
        "hardware_result_available",
        "quantum_advantage_claimed",
        "ready_gate_eligible",
    }
    if set(ceiling) != required_false or any(
        _strict_bool(value, f"authority_ceiling.{key}")
        for key, value in ceiling.items()
    ):
        _fail("CONTRACT_SCHEMA", "authority ceiling drift")
    if contract["limitations"] != EXPECTED_LIMITATIONS:
        _fail("CONTRACT_SCHEMA", "limitations drift")
    _exact_keys(
        contract["decision_rule"],
        (
            "verified",
            "resource_or_timeout",
            "identity_or_custody_failure",
            "arithmetic_or_equivalence_failure",
            "diagnostic_reproducibility_mismatch",
            "next_gate",
        ),
        "decision_rule",
    )
    if contract["decision_rule"] != EXPECTED_DECISION_RULE:
        _fail("CONTRACT_SCHEMA", "decision rule drift")


def _verify_implementation(contract: Mapping[str, Any]) -> None:
    freeze = contract["chronology"]["implementation_freeze_commit"]
    for label, path in (
        ("runner", RUNNER_PATH),
        ("checker", CHECKER_PATH),
        ("launcher", LAUNCHER_PATH),
        ("test", TEST_PATH),
    ):
        expected = contract["implementation"][label]
        actual = _git_blob(freeze, f"{REL_PREFIX}{expected['path']}")
        if actual != {
            "mode": expected["mode"],
            "blob": expected["blob"],
            "bytes": expected["bytes"],
        }:
            _fail("IMPLEMENTATION_IDENTITY", f"{label} Git identity drift")
        size, digest = _sha_file(path, expected["bytes"])
        if size != expected["bytes"] or digest != expected["sha256"]:
            _fail("IMPLEMENTATION_IDENTITY", f"{label} working bytes drift")


def _is_ancestor(commit: str, descendant: str = "HEAD") -> bool:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", commit, descendant],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode not in (0, 1):
        _fail("GIT_IDENTITY", "ancestor query failed")
    return completed.returncode == 0


def _verify_authority_documents(contract: Mapping[str, Any]) -> dict[str, Any]:
    source = contract["source_authority"]
    if not _is_ancestor(PACKED_C3_COMMIT):
        _fail("SOURCE_AUTHORITY", "packed C3 is not in the execution ancestry")
    if not _is_ancestor(D18_RESULT_COMMIT):
        _fail("SOURCE_AUTHORITY", "diagnostic D18 result is not in the evidence baseline")
    d11_result = _load_json(HERE / D11_RESULT_NAME)
    checkpoint = d11_result.get("checkpoint")
    if not isinstance(checkpoint, dict) or (
        checkpoint.get("record_count") != SOURCE_RECORDS
        or checkpoint.get("record_bytes") != SOURCE_RECORD.size
        or checkpoint.get("file_bytes") != SOURCE_RECORDS * SOURCE_RECORD.size
        or checkpoint.get("packed_sorted_binary_sha256") != PACKED_SHA256
        or checkpoint.get("strictly_ascending_representatives") is not True
        or checkpoint.get("insertion_ranks_complete_permutation") is not True
    ):
        _fail("SOURCE_AUTHORITY", "packed D11 result semantics drift")
    d11_receipt = _load_json(HERE / D11_RECEIPT_NAME)
    terminal = d11_receipt.get("runner_terminal_evidence")
    if not isinstance(terminal, dict) or (
        d11_receipt.get("runner_exit_code") != 0
        or terminal.get("checkpoint_sha256") != PACKED_SHA256
        or terminal.get("result_sha256") != PACKED_RESULT_SHA256
        or terminal.get("depth3_to_depth4_action_executed") is not False
        or terminal.get("single_bundle_renameat2_noreplace_completed") is not True
    ):
        _fail("SOURCE_AUTHORITY", "packed D11 terminal receipt semantics drift")
    d16 = _load_json(HERE / D16_RESULT_NAME)
    packed_audit = d16.get("packed_source_audit")
    if not isinstance(packed_audit, dict) or (
        d16.get("status")
        != "NO_GO_D16_LEGACY_TARGET_CUSTODY_BROKEN_ASSOCIATED_SPOOL_DUPLICATED_TARGET_QUARANTINED"
        or d16.get("authority", {}).get("packed_q3_source_admissible") is not True
        or d16.get("authority", {}).get("legacy_q4_target_digest_authoritative")
        is not False
        or packed_audit.get("source_shard_manifest_sha256")
        != PACKED_SHARD_MANIFEST_SHA256
    ):
        _fail("SOURCE_AUTHORITY", "D16-F custody authority drift")
    d17_contract = _load_json(HERE / D17_CONTRACT_NAME)
    d17_result = _load_json(HERE / D17_RESULT_NAME)
    if (
        d17_contract.get("contract_id") != "FH-L8-INDEPENDENT-REFERENCE-D17"
        or d17_contract.get("fresh_successor_protocol", {}).get(
            "bounded_preflight_execution_authorized"
        )
        is not False
        or d17_result.get("status")
        != "NO_GO_D17_Q0_TO_Q4_DUAL_VECTOR_CUSTODY_INCOMPLETE"
        or d17_result.get("q3_source_admissible") is not True
        or d17_result.get("q4_vector_admissible") is not False
    ):
        _fail("SOURCE_AUTHORITY", "D17 vector custody authority drift")
    d18_result = _load_legacy_d18_observation(
        HERE / D18_RESULT_NAME, D18_RESULT_SHA256
    )
    if (
        d18_result.get("status")
        != "VERIFIED_D18_FRESH_EXCLUSIVE_PACKED_Q3_BOUNDED_PREFLIGHT"
        or d18_result.get("merge", {}).get("target_records")
        != EXPECTED_COMPARATOR["target_records"]
        or d18_result.get("merge", {}).get("payload_bytes")
        != EXPECTED_COMPARATOR["target_bytes"]
        or d18_result.get("merge", {}).get("payload_sha256")
        != EXPECTED_COMPARATOR["target_sha256"]
    ):
        _fail("SOURCE_AUTHORITY", "diagnostic D18 observation drift")
    return {
        "packed_c3_ancestor": True,
        "d18_result_ancestor": True,
        "d16_packed_q3_admissible": True,
        "d16_legacy_q4_quarantined": True,
        "d17_prior_bounded_execution_authorized": False,
        "d18_diagnostic_execution_authority_admitted": False,
    }


def _cgroup_root() -> tuple[Path, str]:
    try:
        lines = Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
    except OSError as exc:
        _fail("CGROUP_UNAVAILABLE", str(exc))
    entries = [line.split(":", 2)[2] for line in lines if line.startswith("0::")]
    if len(entries) != 1:
        _fail("CGROUP_UNAVAILABLE", "unified cgroup-v2 path unavailable")
    relative = entries[0]
    root = Path("/sys/fs/cgroup") / relative.lstrip("/")
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        _fail("CGROUP_UNAVAILABLE", str(exc))
    return resolved, relative


def _read_scalar(path: Path) -> str:
    try:
        return path.read_text(encoding="ascii").strip()
    except OSError as exc:
        _fail("CGROUP_UNAVAILABLE", f"cannot read {path.name}: {exc}")


def _read_events(path: Path) -> dict[str, int]:
    events: dict[str, int] = {}
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except OSError as exc:
        _fail("CGROUP_UNAVAILABLE", f"cannot read memory.events: {exc}")
    for line in lines:
        fields = line.split()
        if len(fields) != 2 or not fields[1].isdigit() or fields[0] in events:
            _fail("CGROUP_UNAVAILABLE", "malformed memory.events")
        events[fields[0]] = int(fields[1])
    for key in ("high", "max", "oom", "oom_kill"):
        if key not in events:
            _fail("CGROUP_UNAVAILABLE", f"memory.events lacks {key}")
    return events


def _cgroup_snapshot() -> dict[str, Any]:
    root, relative = _cgroup_root()
    try:
        inode = root.stat().st_ino
    except OSError as exc:
        _fail("CGROUP_UNAVAILABLE", str(exc))
    return {
        "pid": os.getpid(),
        "path": relative,
        "inode": inode,
        "memory_current_bytes": int(_read_scalar(root / "memory.current")),
        "memory_peak_bytes": int(_read_scalar(root / "memory.peak")),
        "memory_max": _read_scalar(root / "memory.max"),
        "memory_high": _read_scalar(root / "memory.high"),
        "memory_swap_current_bytes": int(_read_scalar(root / "memory.swap.current")),
        "memory_swap_max": _read_scalar(root / "memory.swap.max"),
        "memory_events": _read_events(root / "memory.events"),
    }


def _validate_initial_cgroup(snapshot: Mapping[str, Any], limits: Mapping[str, Any]) -> None:
    if limits["cgroup_path_component"] not in snapshot["path"]:
        _fail("CGROUP_ENVELOPE", "not running in the dedicated D18-C scope")
    for key in ("memory_max", "memory_high", "memory_swap_max"):
        if snapshot[key] != limits[key]:
            _fail("CGROUP_ENVELOPE", f"{key} drift")
    if snapshot["memory_swap_current_bytes"] != 0:
        _fail("CGROUP_ENVELOPE", "initial swap is non-zero")
    if snapshot["memory_peak_bytes"] > limits["max_initial_memory_peak_bytes"]:
        _fail("CGROUP_ENVELOPE", "initial cgroup peak exceeds cap")


def _resource_delta(
    before: Mapping[str, Any], after: Mapping[str, Any], limits: Mapping[str, Any]
) -> dict[str, Any]:
    if (
        before["pid"] != after["pid"]
        or before["path"] != after["path"]
        or before["inode"] != after["inode"]
    ):
        _fail("CGROUP_ENVELOPE", "cgroup or process identity changed")
    for key in ("memory_max", "memory_high", "memory_swap_max"):
        if before[key] != after[key] or after[key] != limits[key]:
            _fail("CGROUP_ENVELOPE", f"{key} changed")
    keys = set(before["memory_events"]) | set(after["memory_events"])
    event_delta = {
        key: after["memory_events"].get(key, 0) - before["memory_events"].get(key, 0)
        for key in sorted(keys)
    }
    if any(value < 0 for value in event_delta.values()):
        _fail("CGROUP_ENVELOPE", "memory.events decreased")
    if any(event_delta.get(key, 0) for key in ("high", "max", "oom", "oom_kill")):
        _fail("RESOURCE_NO_GO", "memory pressure/OOM event occurred")
    if after["memory_swap_current_bytes"] != 0:
        _fail("RESOURCE_NO_GO", "swap was consumed")
    process_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    if (
        after["memory_peak_bytes"] > limits["max_final_memory_peak_bytes"]
        or process_peak > limits["max_process_peak_rss_bytes"]
    ):
        _fail("RESOURCE_NO_GO", "memory peak cap exceeded")
    return {
        "cgroup_path": after["path"],
        "cgroup_inode": after["inode"],
        "memory_current_before_bytes": before["memory_current_bytes"],
        "memory_current_after_bytes": after["memory_current_bytes"],
        "memory_peak_before_bytes": before["memory_peak_bytes"],
        "memory_peak_after_bytes": after["memory_peak_bytes"],
        "memory_max": after["memory_max"],
        "memory_high": after["memory_high"],
        "memory_swap_current_after_bytes": after["memory_swap_current_bytes"],
        "memory_swap_max": after["memory_swap_max"],
        "memory_event_delta": event_delta,
        "process_peak_rss_bytes": process_peak,
        "observation_scope": (
            "after_bounded_target_and_manifests;"
            "before_runner_terminal_receipt_publication"
        ),
    }


def _filesystem_type(path: Path) -> str:
    resolved = str(path.resolve(strict=True))
    best: tuple[int, str] | None = None
    try:
        lines = Path("/proc/self/mountinfo").read_text(
            encoding="utf-8", errors="strict"
        ).splitlines()
    except OSError as exc:
        _fail("SCRATCH_CUSTODY", f"cannot read mountinfo: {exc}")
    for line in lines:
        fields = line.split()
        if "-" not in fields:
            continue
        split = fields.index("-")
        if split + 1 >= len(fields) or len(fields) < 5:
            continue
        mountpoint = (
            fields[4]
            .replace("\\040", " ")
            .replace("\\011", "\t")
            .replace("\\012", "\n")
            .replace("\\134", "\\")
        )
        if resolved == mountpoint or resolved.startswith(mountpoint.rstrip("/") + "/"):
            candidate = (len(mountpoint), fields[split + 1])
            if best is None or candidate[0] > best[0]:
                best = candidate
    if best is None:
        _fail("SCRATCH_CUSTODY", "scratch filesystem not found in mountinfo")
    return best[1]


def _prepare_scratch(path: Path, contract: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    protocol = contract["consumer_protocol"]
    if not path.is_absolute():
        _fail("SCRATCH_CUSTODY", "scratch path must be absolute")
    if os.path.lexists(path):
        _fail("SCRATCH_CUSTODY", "scratch path must not already exist")
    allowed = Path(protocol["allowed_scratch_parent"]).resolve(strict=True)
    if (
        path.parent.resolve(strict=True) != allowed
        or path != allowed / path.name
        or re.fullmatch(r"fh-l8-d18c-[a-z0-9][a-z0-9-]{0,47}", path.name) is None
    ):
        _fail("SCRATCH_CUSTODY", "scratch parent is not authorized")
    allowed_stat = allowed.stat()
    if allowed_stat.st_uid != os.getuid() or stat.S_IMODE(allowed_stat.st_mode) & 0o022:
        _fail("SCRATCH_CUSTODY", "scratch parent ownership/mode is unsafe")
    fs_type = _filesystem_type(allowed)
    if fs_type in protocol["deny_filesystem_types"]:
        _fail("SCRATCH_CUSTODY", f"scratch filesystem {fs_type} is forbidden")
    try:
        path.mkdir(mode=0o700)
        scratch_stat = path.lstat()
        parent_fd = os.open(allowed, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        lock_path = path / "exclusive.lock"
        lock_fd = os.open(
            lock_path,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_stat = os.fstat(lock_fd)
    except OSError as exc:
        _fail("SCRATCH_CUSTODY", f"cannot establish exclusive scratch: {exc}")
    return lock_fd, {
        "filesystem_type": fs_type,
        "scratch_parent_device": allowed.stat().st_dev,
        "scratch_parent_owner_uid": allowed_stat.st_uid,
        "scratch_parent_mode": stat.S_IMODE(allowed_stat.st_mode),
        "scratch_root_device": scratch_stat.st_dev,
        "scratch_root_inode": scratch_stat.st_ino,
        "scratch_root_owner_uid": scratch_stat.st_uid,
        "scratch_root_mode": stat.S_IMODE(scratch_stat.st_mode),
        "exclusive_lock_device": lock_stat.st_dev,
        "exclusive_lock_inode": lock_stat.st_ino,
        "exclusive_lock_owner_uid": lock_stat.st_uid,
        "exclusive_lock_mode": stat.S_IMODE(lock_stat.st_mode),
        "exclusive_lock": True,
    }


def _verify_scratch_identity(
    path: Path, record: Mapping[str, Any], lock_fd: int, phase: str
) -> None:
    try:
        root = path.lstat()
        lock_path = (path / "exclusive.lock").lstat()
        lock = os.fstat(lock_fd)
    except OSError as exc:
        _fail("SCRATCH_TOCTOU", f"scratch identity unavailable at {phase}: {exc}")
    if (
        not stat.S_ISDIR(root.st_mode)
        or root.st_dev != record["scratch_root_device"]
        or root.st_ino != record["scratch_root_inode"]
        or root.st_uid != record["scratch_root_owner_uid"]
        or stat.S_IMODE(root.st_mode) != record["scratch_root_mode"]
        or not stat.S_ISREG(lock.st_mode)
        or not stat.S_ISREG(lock_path.st_mode)
        or lock.st_dev != record["exclusive_lock_device"]
        or lock.st_ino != record["exclusive_lock_inode"]
        or lock_path.st_dev != record["exclusive_lock_device"]
        or lock_path.st_ino != record["exclusive_lock_inode"]
        or lock_path.st_nlink != 1
        or lock.st_uid != record["exclusive_lock_owner_uid"]
        or stat.S_IMODE(lock.st_mode) != record["exclusive_lock_mode"]
    ):
        _fail("SCRATCH_TOCTOU", f"scratch root/lock identity drift at {phase}")


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_publish(path: Path, payload: bytes, maximum: int) -> dict[str, Any]:
    if len(payload) > maximum:
        _fail("PUBLICATION_OVERSIZE", f"{path.name} exceeds cap")
    temporary = path.with_name(f".{path.name}.staging-{os.getpid()}")
    if os.path.lexists(path) or os.path.lexists(temporary):
        _fail("PUBLICATION_COLLISION", f"{path.name} already exists")
    try:
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(fd, "wb", buffering=0) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path, follow_symlinks=False)
        os.unlink(temporary)
        _fsync_dir(path.parent)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        _fail("PUBLICATION_FAILED", f"cannot publish {path.name}: {exc}")
    size, digest = _sha_file(path, maximum)
    if size != len(payload) or digest != hashlib.sha256(payload).hexdigest():
        _fail("PUBLICATION_FAILED", f"{path.name} post-publication rehash drift")
    return {"path": path.name, "bytes": size, "sha256": digest}


def _admit_source(contract: Mapping[str, Any]) -> tuple[list[tuple[int, int]], dict[str, Any]]:
    source = contract["source_authority"]
    packed = source["packed_checkpoint"]
    git_identity = _git_blob(
        source["packed_c3_commit"], f"{REL_PREFIX}{packed['path']}"
    )
    if git_identity != {
        "mode": packed["mode"],
        "blob": packed["blob"],
        "bytes": packed["bytes"],
    }:
        _fail("SOURCE_IDENTITY", "packed checkpoint Git identity drift")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(SOURCE_PATH, flags)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size != packed["bytes"]:
            _fail("SOURCE_IDENTITY", "packed checkpoint type/size drift")
        digest = hashlib.sha256()
        first_digest = hashlib.sha256()
        projection_digest = hashlib.sha256()
        ranks = bytearray(SOURCE_RECORDS)
        selected: list[tuple[int, int]] = []
        prior = -1
        even_mask = int("55" * 16, 16)
        records = 0
        while True:
            block = os.read(fd, 1 << 20)
            if not block:
                break
            if len(block) % SOURCE_RECORD.size:
                _fail("SOURCE_FORMAT", "source chunk alignment drift")
            digest.update(block)
            take = max(0, min(len(block), BOUNDED_ROWS * SOURCE_RECORD.size - records * SOURCE_RECORD.size))
            if take:
                first_digest.update(block[:take])
            for offset in range(0, len(block), SOURCE_RECORD.size):
                raw = block[offset : offset + SOURCE_RECORD.size]
                representative_raw, amplitude, orbit, record_flags, reserved, rank = (
                    SOURCE_RECORD.unpack(raw)
                )
                representative = int.from_bytes(representative_raw, "big")
                if representative <= prior:
                    _fail("SOURCE_FORMAT", "representatives not strictly ascending")
                if amplitude == 0 or orbit not in (1, 4, 8):
                    _fail("SOURCE_FORMAT", "amplitude/orbit drift")
                if record_flags != 0 or reserved != 0:
                    _fail("SOURCE_FORMAT", "flags/reserved drift")
                if rank >= SOURCE_RECORDS or ranks[rank]:
                    _fail("SOURCE_FORMAT", "rank is not a permutation")
                if (
                    (representative & even_mask).bit_count() != 32
                    or ((representative >> 1) & even_mask).bit_count() != 32
                ):
                    _fail("SOURCE_FORMAT", "representative escaped particle sector")
                ranks[rank] = 1
                prior = representative
                if records < BOUNDED_ROWS:
                    selected.append((representative, amplitude))
                    projection_digest.update(representative_raw)
                    projection_digest.update(struct.pack(">q", amplitude))
                records += 1
        after = os.fstat(fd)
    except RunnerError:
        raise
    except OSError as exc:
        _fail("SOURCE_READ", f"cannot read packed checkpoint: {exc}")
    finally:
        if "fd" in locals():
            os.close(fd)
    if (
        records != SOURCE_RECORDS
        or not all(ranks)
        or digest.hexdigest() != packed["sha256"]
        or first_digest.hexdigest() != source["first_4096_raw_sha256"]
        or projection_digest.hexdigest() != source["first_4096_projection_sha256"]
    ):
        _fail("SOURCE_IDENTITY", "packed checkpoint content/coverage drift")
    stable_fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, key) != getattr(after, key) for key in stable_fields):
        _fail("SOURCE_TOCTOU", "packed checkpoint changed during admission")
    return selected, {
        "records_validated": records,
        "record_bytes": SOURCE_RECORD.size,
        "payload_bytes": packed["bytes"],
        "payload_sha256": digest.hexdigest(),
        "first_4096_raw_sha256": first_digest.hexdigest(),
        "first_4096_projection_sha256": projection_digest.hexdigest(),
        "first_representative_hex": hex(selected[0][0]),
        "last_selected_representative_hex": hex(selected[-1][0]),
        "rank_permutation_valid": True,
        "source_stat": {
            "device": before.st_dev,
            "inode": before.st_ino,
            "mode": stat.S_IMODE(before.st_mode),
            "size": before.st_size,
            "mtime_ns": before.st_mtime_ns,
            "ctime_ns": before.st_ctime_ns,
        },
    }


def _snapshot_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_object,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except RunnerError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("KERNEL_IDENTITY", f"invalid {label} snapshot JSON: {exc}")
    if not isinstance(value, dict):
        _fail("KERNEL_IDENTITY", f"{label} snapshot must be an object")
    return value


def _snapshot_kernel_sources(
    contract: Mapping[str, Any],
) -> tuple[dict[str, bytes], dict[str, Any]]:
    if contract["source_authority"]["kernel_source_pins"] != EXPECTED_KERNEL_SOURCE_PINS:
        _fail("KERNEL_IDENTITY", "kernel source pin contract drift")
    loaded: dict[str, bytes] = {}
    records: list[dict[str, Any]] = []
    head = _head()
    for pin in EXPECTED_KERNEL_SOURCE_PINS:
        path = HERE / pin["path"]
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > 1_048_576:
                _fail("KERNEL_IDENTITY", f"kernel source type/size drift: {path.name}")
            chunks: list[bytes] = []
            total = 0
            while True:
                block = os.read(fd, 1 << 20)
                if not block:
                    break
                total += len(block)
                if total > 1_048_576:
                    _fail("KERNEL_IDENTITY", f"kernel source exceeds cap: {path.name}")
                chunks.append(block)
            after = os.fstat(fd)
        except RunnerError:
            raise
        except OSError as exc:
            _fail("KERNEL_IDENTITY", f"cannot snapshot {path.name}: {exc}")
        finally:
            if "fd" in locals():
                os.close(fd)
                del fd
        raw = b"".join(chunks)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != pin["sha256"]:
            _fail("KERNEL_IDENTITY", f"kernel source hash drift: {path.name}")
        stable = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, key) != getattr(after, key) for key in stable):
            _fail("KERNEL_TOCTOU", f"kernel source changed during snapshot: {path.name}")
        git_identity = _git_blob(head, f"{REL_PREFIX}{path.name}")
        if (
            git_identity["mode"] != "100644"
            or git_identity["bytes"] != len(raw)
            or _git("cat-file", "blob", git_identity["blob"]) != raw
        ):
            _fail("KERNEL_IDENTITY", f"kernel source differs from HEAD: {path.name}")
        loaded[path.name] = raw
        records.append(
            {
                "path": path.name,
                "bytes": len(raw),
                "sha256": digest,
                "device": before.st_dev,
                "inode": before.st_ino,
                "mode": stat.S_IMODE(before.st_mode),
                "mtime_ns": before.st_mtime_ns,
                "ctime_ns": before.st_ctime_ns,
                "git_blob": git_identity["blob"],
            }
        )
    return loaded, {
        "artifacts": records,
        "compiled_from_single_pre_action_byte_snapshot": True,
        "transitive_worktree_module_or_contract_loads_during_action": False,
    }


def _compile_snapshot_module(name: str, path: Path, raw: bytes) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), "exec"), module.__dict__)
    except Exception as exc:
        _fail("KERNEL_LOAD", f"cannot compile {path.name} snapshot: {exc}")
    return module


def _kernel_context(
    snapshots: Mapping[str, bytes],
) -> tuple[types.ModuleType, tuple[Any, Any, Any, Any]]:
    try:
        d5 = _compile_snapshot_module(
            "fh_l8_d18c_snapshot_d5", HERE / D5_NAME, snapshots[D5_NAME]
        )
        d4 = _compile_snapshot_module(
            "fh_l8_d18c_snapshot_d4", HERE / D4_NAME, snapshots[D4_NAME]
        )
        backend = _compile_snapshot_module(
            "fh_l8_d18c_snapshot_backend",
            HERE / BACKEND_NAME,
            snapshots[BACKEND_NAME],
        )
        backend.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = snapshots[BACKEND_NAME]
        d5_contract = _snapshot_json(
            snapshots[D5_CONTRACT_NAME], D5_CONTRACT_NAME
        )
        if (
            d5_contract.get("contract_id") != "FH-L8-INDEPENDENT-REFERENCE-D5"
            or d5_contract.get("checker_self_sha256") != D5_SHA256
        ):
            _fail("KERNEL_CONTEXT", "snapshot D5 contract identity drift")
        d4_pin = next(
            (
                pin
                for pin in d5_contract.get("source_pins", [])
                if pin.get("path") == D4_NAME
            ),
            None,
        )
        if not isinstance(d4_pin, dict) or d4_pin.get("sha256") != EXPECTED_KERNEL_SOURCE_PINS[2]["sha256"]:
            _fail("KERNEL_CONTEXT", "D5 contract does not bind snapshot D4 kernel")
        bonds = {
            name: backend._hopping_bonds(8, name)
            for name in ("H1", "H2", "H3", "H4")
        }
        symmetries, _ = d5._build_symmetries(d5_contract)
    except RunnerError:
        raise
    except Exception as exc:
        _fail("KERNEL_CONTEXT", f"cannot establish snapshot scientific context: {exc}")
    return d5, (d4, backend, bonds, symmetries)


def _rehash_kernel_sources(record: Mapping[str, Any]) -> None:
    for item in record["artifacts"]:
        path = HERE / item["path"]
        size, digest = _sha_file(path, 1_048_576)
        current = path.stat()
        if (
            size != item["bytes"]
            or digest != item["sha256"]
            or current.st_dev != item["device"]
            or current.st_ino != item["inode"]
            or stat.S_IMODE(current.st_mode) != item["mode"]
            or current.st_mtime_ns != item["mtime_ns"]
            or current.st_ctime_ns != item["ctime_ns"]
        ):
            _fail("KERNEL_TOCTOU", f"kernel source changed after snapshot: {path.name}")


def _scaled_delta(amplitude: int, coefficient: Fraction) -> int:
    if coefficient.denominator <= 0 or 8 % coefficient.denominator:
        _fail("ARITHMETIC", "non-octadic quotient coefficient")
    delta = amplitude * coefficient.numerator * (8 // coefficient.denominator)
    if not -(1 << 63) <= delta < (1 << 63):
        _fail("ARITHMETIC", "scaled spill delta exceeds signed i64")
    return delta


def _spill(
    contract: Mapping[str, Any],
    scratch: Path,
    sources: list[tuple[int, int]],
    d5: types.ModuleType,
    context: tuple[Any, Any, Any, Any],
    deadline: float,
    state: dict[str, Any],
) -> dict[str, Any]:
    d4, backend, bonds, symmetries = context
    if len(sources) != BOUNDED_ROWS:
        _fail("ACTION_BUDGET", "source selection must contain exactly 4,096 rows")
    representatives = [item[0] for item in sources]
    if any(
        representatives[index] >= representatives[index + 1]
        for index in range(len(representatives) - 1)
    ):
        _fail("ACTION_BUDGET", "source selection must be unique and strictly ascending")
    buffers = {index: bytearray() for index in range(PARTITIONS)}
    reduced_columns = 0
    projected_zero = 0
    zero_coefficients = 0
    state["action_started"] = True
    for index, (representative, amplitude) in enumerate(sources):
        if time.monotonic() > deadline:
            _fail("RESOURCE_TIMEOUT", "deadline exceeded during spill action")
        if index >= BOUNDED_ROWS:
            _fail("ACTION_BUDGET", "more than 4,096 unique q3 rows requested")
        state["unique_q3_rows_acted"] += 1
        state["kernel_evaluations"] += 1
        try:
            column, _, dropped = d5._reduced_column(
                d4, backend, bonds, representative, symmetries
            )
        except Exception as exc:
            _fail("SCIENTIFIC_KERNEL", f"bounded action failed at row {index}: {exc}")
        projected_zero += dropped
        reduced_columns += len(column)
        for target, coefficient in column.items():
            if not coefficient:
                zero_coefficients += 1
                continue
            delta = _scaled_delta(amplitude, coefficient)
            partition = hashlib.sha256(target.to_bytes(16, "big")).digest()[0]
            buffers[partition].extend(
                SPILL_RECORD.pack(target.to_bytes(16, "big"), delta, 0)
            )
    if state["unique_q3_rows_acted"] != BOUNDED_ROWS:
        _fail("ACTION_BUDGET", "bounded action did not consume exactly 4,096 rows")

    spool = scratch / "spill"
    spool.mkdir(mode=0o700)
    partition_records: list[dict[str, Any]] = []
    spill_bytes = 0
    spill_records = 0
    for partition in range(PARTITIONS):
        raw = bytes(buffers[partition])
        name = f"p{partition:03d}.bin"
        identity = _atomic_publish(
            spool / name, raw, contract["resource_limits"]["max_spill_bytes"]
        )
        record = {
            "partition": partition,
            "path": name,
            "records": len(raw) // SPILL_RECORD.size,
            **{key: identity[key] for key in ("bytes", "sha256")},
        }
        partition_records.append(record)
        spill_bytes += record["bytes"]
        spill_records += record["records"]
    if spill_bytes > contract["resource_limits"]["max_spill_bytes"]:
        _fail("RESOURCE_NO_GO", "total spill bytes exceed cap")
    manifest = {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "source_row_start": 0,
        "source_row_end_exclusive": BOUNDED_ROWS,
        "source_rows": BOUNDED_ROWS,
        "source_first_4096_raw_sha256": contract["source_authority"][
            "first_4096_raw_sha256"
        ],
        "record_bytes": SPILL_RECORD.size,
        "scaled_denominator": 8,
        "partition_count": PARTITIONS,
        "partition_selector": "SHA256(target_u128_be)[0]",
        "spill_records": spill_records,
        "spill_bytes": spill_bytes,
        "reduced_columns": reduced_columns,
        "projected_zero_outputs": projected_zero,
        "zero_coefficients_dropped": zero_coefficients,
        "partitions": partition_records,
        "complete": True,
    }
    manifest_identity = _atomic_publish(
        spool / "manifest.json",
        _canonical_json(manifest),
        contract["resource_limits"]["max_manifest_bytes"],
    )
    _fsync_dir(spool)
    state["spill_complete"] = True
    return {
        "manifest": manifest_identity,
        "spill_records": spill_records,
        "spill_bytes": spill_bytes,
        "reduced_columns": reduced_columns,
        "projected_zero_outputs": projected_zero,
        "zero_coefficients_dropped": zero_coefficients,
        "partition_count": PARTITIONS,
    }


def _load_spill_manifest(contract: Mapping[str, Any], spool: Path) -> dict[str, Any]:
    manifest_path = spool / "manifest.json"
    manifest = _load_json(manifest_path)
    allowed = {"manifest.json"} | {f"p{index:03d}.bin" for index in range(PARTITIONS)}
    try:
        entries = list(os.scandir(spool))
        if any(entry.is_symlink() or not entry.is_file(follow_symlinks=False) for entry in entries):
            _fail("MANIFEST_CUSTODY", "spill contains a symlink/non-regular file")
        observed = {entry.name for entry in entries}
    except OSError as exc:
        _fail("MANIFEST_CUSTODY", f"cannot enumerate spill: {exc}")
    if observed != allowed:
        _fail("MANIFEST_CUSTODY", "spill contains missing or unmanifested paths")
    expected_top = {
        "schema_version",
        "contract_id",
        "source_row_start",
        "source_row_end_exclusive",
        "source_rows",
        "source_first_4096_raw_sha256",
        "record_bytes",
        "scaled_denominator",
        "partition_count",
        "partition_selector",
        "spill_records",
        "spill_bytes",
        "reduced_columns",
        "projected_zero_outputs",
        "zero_coefficients_dropped",
        "partitions",
        "complete",
    }
    if set(manifest) != expected_top or manifest["contract_id"] != CONTRACT_ID:
        _fail("MANIFEST_CUSTODY", "spill manifest schema/id drift")
    if (
        manifest["source_row_start"] != 0
        or manifest["source_row_end_exclusive"] != BOUNDED_ROWS
        or manifest["source_rows"] != BOUNDED_ROWS
        or manifest["record_bytes"] != SPILL_RECORD.size
        or manifest["scaled_denominator"] != 8
        or manifest["partition_count"] != PARTITIONS
        or manifest["partition_selector"] != "SHA256(target_u128_be)[0]"
        or manifest["complete"] is not True
    ):
        _fail("MANIFEST_CUSTODY", "spill manifest protocol drift")
    for key in (
        "source_row_start",
        "source_row_end_exclusive",
        "source_rows",
        "record_bytes",
        "scaled_denominator",
        "partition_count",
        "spill_records",
        "spill_bytes",
        "reduced_columns",
        "projected_zero_outputs",
        "zero_coefficients_dropped",
    ):
        _strict_int(manifest[key], f"spill_manifest.{key}")
    partitions = manifest["partitions"]
    if not isinstance(partitions, list) or len(partitions) != PARTITIONS:
        _fail("MANIFEST_CUSTODY", "partition manifest count drift")
    total_records = 0
    total_bytes = 0
    for index, item in enumerate(partitions):
        if not isinstance(item, dict) or set(item) != {
            "partition",
            "path",
            "records",
            "bytes",
            "sha256",
        }:
            _fail("MANIFEST_CUSTODY", "partition entry schema drift")
        name = f"p{index:03d}.bin"
        if item["partition"] != index or item["path"] != name:
            _fail("MANIFEST_CUSTODY", "partition order/path drift")
        if "/" in item["path"] or "\\" in item["path"] or item["path"] in (".", ".."):
            _fail("MANIFEST_CUSTODY", "partition path traversal")
        _strict_int(item["partition"], "partition.partition")
        _strict_int(item["records"], "partition.records")
        _strict_int(item["bytes"], "partition.bytes")
        _strict_sha(item["sha256"], "partition.sha256")
        path = spool / name
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            _fail("MANIFEST_CUSTODY", f"partition {index} type/link drift")
        size, digest = _sha_file(
            path, contract["resource_limits"]["max_spill_bytes"]
        )
        if (
            size != item["bytes"]
            or digest != item["sha256"]
            or size != item["records"] * SPILL_RECORD.size
        ):
            _fail("MANIFEST_CUSTODY", f"partition {index} identity drift")
        total_records += item["records"]
        total_bytes += item["bytes"]
    if (
        total_records != manifest["spill_records"]
        or total_bytes != manifest["spill_bytes"]
        or total_bytes > contract["resource_limits"]["max_spill_bytes"]
    ):
        _fail("MANIFEST_CUSTODY", "spill totals drift")
    return manifest


def _merge(
    contract: Mapping[str, Any],
    scratch: Path,
    deadline: float,
    state: dict[str, Any],
) -> tuple[dict[int, int], dict[str, Any]]:
    spool = scratch / "spill"
    manifest = _load_spill_manifest(contract, spool)
    target_map: dict[int, int] = {}
    payload = bytearray()
    partition_target_counts: list[int] = []
    for item in manifest["partitions"]:
        if time.monotonic() > deadline:
            _fail("RESOURCE_TIMEOUT", "deadline exceeded during manifest-only merge")
        partition = item["partition"]
        raw = (spool / item["path"]).read_bytes()
        if (
            len(raw) != item["bytes"]
            or hashlib.sha256(raw).hexdigest() != item["sha256"]
        ):
            _fail("MANIFEST_CUSTODY", "partition changed after manifest admission")
        values: list[tuple[bytes, int]] = []
        for offset in range(0, len(raw), SPILL_RECORD.size):
            target_raw, delta, reserved = SPILL_RECORD.unpack(
                raw[offset : offset + SPILL_RECORD.size]
            )
            if reserved != 0:
                _fail("ARITHMETIC", "spill reserved field is nonzero")
            if hashlib.sha256(target_raw).digest()[0] != partition:
                _fail("MANIFEST_CUSTODY", "spill target in wrong partition")
            values.append((target_raw, delta))
        values.sort(key=lambda item_: item_[0])
        index = 0
        partition_count = 0
        while index < len(values):
            target_raw = values[index][0]
            total = 0
            while index < len(values) and values[index][0] == target_raw:
                total += values[index][1]
                index += 1
            if total == 0:
                continue
            if total % 8:
                _fail("ARITHMETIC", "scaled merge is not divisible by eight")
            amplitude = total // 8
            if not -(1 << 63) <= amplitude < (1 << 63):
                _fail("ARITHMETIC", "bounded target amplitude exceeds signed i64")
            target = int.from_bytes(target_raw, "big")
            if target in target_map:
                _fail("ARITHMETIC", "target appears in multiple partitions")
            target_map[target] = amplitude
            payload.extend(SPILL_RECORD.pack(target_raw, amplitude, 0))
            partition_count += 1
        partition_target_counts.append(partition_count)
    if len(payload) > contract["resource_limits"]["max_target_bytes"]:
        _fail("RESOURCE_NO_GO", "bounded target exceeds byte cap")
    target_identity = _atomic_publish(
        scratch / "bounded-q4-partial.bin",
        bytes(payload),
        contract["resource_limits"]["max_target_bytes"],
    )
    target_manifest = {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "classification": "BOUNDED_FIRST_4096_Q3_ROWS_PARTIAL_Q4_NOT_A_FULL_Q4_OPERAND",
        "ordering": "partition_sha256_byte_then_target_u128",
        "source_rows_acted": BOUNDED_ROWS,
        "partition_count": PARTITIONS,
        "partition_target_counts": partition_target_counts,
        "record_bytes": SPILL_RECORD.size,
        "target_records": len(target_map),
        "target_bytes": len(payload),
        "target_sha256": target_identity["sha256"],
        "complete": True,
    }
    manifest_identity = _atomic_publish(
        scratch / "bounded-q4-partial.manifest.json",
        _canonical_json(target_manifest),
        contract["resource_limits"]["max_manifest_bytes"],
    )
    state["merge_complete"] = True
    state["bounded_target_materialized"] = True
    return target_map, {
        "target": target_identity,
        "manifest": manifest_identity,
        "target_records": len(target_map),
        "target_bytes": len(payload),
        "target_sha256": target_identity["sha256"],
        "ordering": target_manifest["ordering"],
        "partition_target_counts": partition_target_counts,
    }


def _naive_replay(
    sources: list[tuple[int, int]],
    d5: types.ModuleType,
    context: tuple[Any, Any, Any, Any],
    actual: Mapping[int, int],
    deadline: float,
    state: dict[str, Any],
) -> dict[str, Any]:
    d4, backend, bonds, symmetries = context
    expected_scaled: dict[int, int] = {}
    for index, (representative, amplitude) in enumerate(sources):
        if time.monotonic() > deadline:
            _fail("RESOURCE_TIMEOUT", "deadline exceeded during naïve replay")
        if index >= BOUNDED_ROWS:
            _fail("ACTION_BUDGET", "naïve replay exceeded source-row budget")
        state["kernel_evaluations"] += 1
        state["validation_replay_rows"] += 1
        try:
            column, _, _ = d5._reduced_column(
                d4, backend, bonds, representative, symmetries
            )
        except Exception as exc:
            _fail("SCIENTIFIC_KERNEL", f"naïve replay failed at row {index}: {exc}")
        for target, coefficient in column.items():
            if coefficient:
                expected_scaled[target] = expected_scaled.get(target, 0) + _scaled_delta(
                    amplitude, coefficient
                )
    expected: dict[int, int] = {}
    for target, scaled in expected_scaled.items():
        if scaled == 0:
            continue
        if scaled % 8:
            _fail("ARITHMETIC", "naïve scaled sum is not divisible by eight")
        expected[target] = scaled // 8
    if expected != actual:
        _fail("EQUIVALENCE_FAILURE", "manifest-only merge differs from naïve replay")
    state["naive_equivalence_complete"] = True
    semantic = hashlib.sha256()
    for target in sorted(expected):
        semantic.update(SPILL_RECORD.pack(target.to_bytes(16, "big"), expected[target], 0))
    return {
        "verified": True,
        "source_rows_replayed": BOUNDED_ROWS,
        "target_records": len(expected),
        "target_sorted_semantic_sha256": semantic.hexdigest(),
    }


def _rehash_source(contract: Mapping[str, Any], admitted: Mapping[str, Any]) -> None:
    size, digest = _sha_file(
        SOURCE_PATH, contract["source_authority"]["packed_checkpoint"]["bytes"]
    )
    current = SOURCE_PATH.stat()
    prior = admitted["source_stat"]
    if (
        size != prior["size"]
        or digest != admitted["payload_sha256"]
        or current.st_dev != prior["device"]
        or current.st_ino != prior["inode"]
        or stat.S_IMODE(current.st_mode) != prior["mode"]
        or current.st_mtime_ns != prior["mtime_ns"]
        or current.st_ctime_ns != prior["ctime_ns"]
    ):
        _fail("SOURCE_TOCTOU", "packed source changed after bounded action")


def _created_files(scratch: Path) -> list[str]:
    result: list[str] = []
    for path in sorted(scratch.rglob("*")):
        if path.is_symlink():
            _fail("SCRATCH_CUSTODY", "symlink appeared in scratch")
        if path.is_file():
            result.append(str(path.relative_to(scratch)))
        elif not path.is_dir():
            _fail("SCRATCH_CUSTODY", "non-file object appeared in scratch")
    return result


def run(contract: Mapping[str, Any], scratch: Path) -> dict[str, Any]:
    """Execute the contract-authorized bounded action once."""
    _validate_contract(contract)
    _verify_contract_bytes(contract)
    contract_commit = _require_clean_execution_tree(contract)
    _verify_implementation(contract)
    for name, expected in (
        (D11_RESULT_NAME, contract["source_authority"]["packed_result_sha256"]),
        (
            D11_RECEIPT_NAME,
            contract["source_authority"]["packed_terminal_receipt_sha256"],
        ),
        (D16_RESULT_NAME, contract["source_authority"]["d16_forensic_result_sha256"]),
        (D17_CONTRACT_NAME, contract["source_authority"]["d17_contract_sha256"]),
        (D17_RESULT_NAME, contract["source_authority"]["d17_result_sha256"]),
        (D18_RESULT_NAME, contract["diagnostic_comparator"]["d18_result_sha256"]),
    ):
        _, observed = _sha_file(HERE / name)
        if observed != expected:
            _fail("SOURCE_AUTHORITY", f"{name} identity drift")
    authority_record = _verify_authority_documents(contract)

    initial = _cgroup_snapshot()
    _validate_initial_cgroup(initial, contract["resource_limits"])
    lock_fd, scratch_record = _prepare_scratch(scratch, contract)
    state = {
        "source_admitted": False,
        "action_started": False,
        "unique_q3_rows_acted": 0,
        "kernel_evaluations": 0,
        "validation_replay_rows": 0,
        "spill_complete": False,
        "merge_complete": False,
        "bounded_target_materialized": False,
        "naive_equivalence_complete": False,
        "full_53_shard_executed": False,
        "full_q4_target_materialized": False,
    }
    started_ns = time.monotonic_ns()
    deadline = time.monotonic() + contract["resource_limits"]["internal_deadline_seconds"]
    try:
        sources, source_record = _admit_source(contract)
        state["source_admitted"] = True
        _verify_execution_head(contract_commit, "before_kernel_snapshot")
        _verify_scratch_identity(
            scratch, scratch_record, lock_fd, "before_kernel_snapshot"
        )
        kernel_snapshots, kernel_custody = _snapshot_kernel_sources(contract)
        d5, context = _kernel_context(kernel_snapshots)
        _verify_execution_head(
            contract_commit, "after_kernel_snapshot_before_action"
        )
        _verify_scratch_identity(
            scratch,
            scratch_record,
            lock_fd,
            "after_kernel_snapshot_before_action",
        )
        d5._ACTIVE_DEADLINE = deadline
        spill = _spill(contract, scratch, sources, d5, context, deadline, state)
        _verify_scratch_identity(scratch, scratch_record, lock_fd, "after_spill")
        actual, merged = _merge(contract, scratch, deadline, state)
        _verify_scratch_identity(scratch, scratch_record, lock_fd, "after_merge")
        equivalence = _naive_replay(
            sources, d5, context, actual, deadline, state
        )
        _verify_scratch_identity(
            scratch, scratch_record, lock_fd, "after_validation_replay"
        )
        _rehash_source(contract, source_record)
        _rehash_kernel_sources(kernel_custody)
        _verify_execution_head(contract_commit, "before_terminal_snapshot")
        d5._ACTIVE_DEADLINE = None
        if state != {
            "source_admitted": True,
            "action_started": True,
            "unique_q3_rows_acted": BOUNDED_ROWS,
            "kernel_evaluations": BOUNDED_ROWS * 2,
            "validation_replay_rows": BOUNDED_ROWS,
            "spill_complete": True,
            "merge_complete": True,
            "bounded_target_materialized": True,
            "naive_equivalence_complete": True,
            "full_53_shard_executed": False,
            "full_q4_target_materialized": False,
        }:
            _fail("STATE_MACHINE", "bounded action state machine drift")
        comparator = contract["diagnostic_comparator"]
        comparator_match = (
            merged["target_records"] == comparator["target_records"]
            and merged["target_bytes"] == comparator["target_bytes"]
            and merged["target_sha256"] == comparator["target_sha256"]
            and spill["spill_records"] == comparator["spill_records"]
            and spill["reduced_columns"] == comparator["reduced_columns"]
            and spill["projected_zero_outputs"]
            == comparator["projected_zero_outputs"]
            and spill["partition_count"] == comparator["partition_count"]
        )
        if not comparator_match:
            _fail("DIAGNOSTIC_DRIFT", "bounded result differs from preregistered comparator")
        files_before_receipt = _created_files(scratch)
        if (
            len(files_before_receipt) + 1
            > contract["resource_limits"]["maximum_runner_created_regular_files"]
        ):
            _fail("RESOURCE_NO_GO", "created-file cap exceeded")
        final = _cgroup_snapshot()
        resources = _resource_delta(initial, final, contract["resource_limits"])
        elapsed_ns = time.monotonic_ns() - started_ns
        if elapsed_ns > contract["resource_limits"]["internal_deadline_seconds"] * 1_000_000_000:
            _fail("RESOURCE_TIMEOUT", "terminal publication deadline exceeded")
        receipt = {
            "schema_version": 1,
            "contract_id": CONTRACT_ID,
            "status": "VERIFIED_D18C_FRESH_EXCLUSIVE_PACKED_Q3_BOUNDED_4096_PREFLIGHT",
            "verified": True,
            "analysis_class": "BOUNDED_PARTIAL_Q3_TO_Q4_SCIENTIFIC_ACTION",
            "implementation_freeze_commit": contract["chronology"][
                "implementation_freeze_commit"
            ],
            "contract_freeze_commit": contract_commit,
            "source": source_record,
            "source_authority": authority_record,
            "kernel_custody": kernel_custody,
            "scratch_custody": {
                **scratch_record,
                "created_regular_files_before_receipt": files_before_receipt,
            },
            "state": state,
            "spill": spill,
            "bounded_partial_target": merged,
            "naive_equivalence": equivalence,
            "diagnostic_comparator": {
                "authority": False,
                "role": comparator["role"],
                "mismatch_is_preflight_no_go": True,
                "match": comparator_match,
                "target_records": comparator["target_records"],
                "target_bytes": comparator["target_bytes"],
                "target_sha256": comparator["target_sha256"],
                "spill_records": comparator["spill_records"],
                "reduced_columns": comparator["reduced_columns"],
                "projected_zero_outputs": comparator[
                    "projected_zero_outputs"
                ],
                "partition_count": comparator["partition_count"],
            },
            "resources": {**resources, "elapsed_monotonic_ns": elapsed_ns},
            "authority": {
                "bounded_4096_preflight_executed": True,
                "partial_q3_to_q4_action_executed": True,
                **contract["authority_ceiling"],
            },
            "limitations": contract["limitations"],
            "next_gate": contract["decision_rule"]["next_gate"],
        }
        receipt_identity = _atomic_publish(
            scratch / "terminal-receipt.json",
            _canonical_json(receipt),
            contract["resource_limits"]["max_receipt_bytes"],
        )
        _fsync_dir(scratch)
        _verify_execution_head(contract_commit, "after_terminal_receipt")
        _verify_scratch_identity(
            scratch, scratch_record, lock_fd, "after_terminal_receipt"
        )
        return {**receipt, "terminal_receipt": receipt_identity}
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = run(_load_json(args.contract), args.scratch)
    except RunnerError as exc:
        print(
            json.dumps(
                {
                    "status": "D18C_RUNNER_FAILED",
                    "verified": False,
                    "error_code": exc.code,
                    "error": str(exc),
                },
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1
    except Exception as exc:  # fail closed on an unclassified implementation fault
        print(
            json.dumps(
                {
                    "status": "D18C_RUNNER_FAILED",
                    "verified": False,
                    "error_code": "UNCLASSIFIED_FAILURE",
                    "error": f"{type(exc).__name__}: {exc}",
                },
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(receipt, allow_nan=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
