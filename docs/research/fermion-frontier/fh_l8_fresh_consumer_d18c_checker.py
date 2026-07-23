#!/usr/bin/env python3
"""Independent protocol/result checker for FH-L8 D18-C."""
from __future__ import annotations

import argparse
import ast
import hashlib
import heapq
import json
import os
import re
import stat
import struct
import subprocess
import sys
import types
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
KERNEL_SOURCE_NAMES = (
    "fh_l8_symmetry_orbit_quotient_d5_checker.py",
    "fh_l8_symmetry_orbit_quotient_d5_contract.json",
    "fh_l8_scalar_supremum_d4_checker.py",
    "hubbard_strang_commutator_checker.py",
)
RUNNER_PATH = HERE / RUNNER_NAME
CHECKER_PATH = HERE / CHECKER_NAME
LAUNCHER_PATH = HERE / LAUNCHER_NAME
TEST_PATH = HERE / TEST_NAME
CONTRACT_PATH = HERE / CONTRACT_NAME
RESULT_PATH = HERE / RESULT_NAME
SOURCE_PATH = HERE / SOURCE_NAME
CONTRACT_ID = "FH-L8-INDEPENDENT-REFERENCE-D18-C-FRESH-CONSUMER-V1"
SOURCE_RECORD = struct.Struct(">16sqBBHI")
SPILL_RECORD = struct.Struct(">16sqQ")
SOURCE_RECORDS = 213_099
BOUNDED_ROWS = 4_096
PARTITIONS = 256
SHA256_RE = re.compile(r"[0-9a-f]{64}")
SHA1_RE = re.compile(r"[0-9a-f]{40}")
UNIT_RE = re.compile(r"ab-fh-l8-d18c-[a-z0-9][a-z0-9-]{0,47}")
EXPECTED_COMPARATOR_COUNTS = {
    "spill_records": 868_786,
    "reduced_columns": 868_786,
    "projected_zero_outputs": 22,
    "partition_count": PARTITIONS,
}


class VerificationError(ValueError):
    """A frozen protocol, result, resource, or custody condition failed."""


def _duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise VerificationError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> Any:
    raise VerificationError(f"non-finite JSON constant: {value}")


def _reject_float(value: str) -> Any:
    raise VerificationError(f"floating-point JSON number forbidden: {value}")


def _load_json_bytes(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_object,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except VerificationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError("JSON root must be an object")
    return value


def _load_json(path: Path, maximum_bytes: int | None = None) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise VerificationError(f"cannot read {path.name}: {exc}") from exc
    if maximum_bytes is not None and len(raw) > maximum_bytes:
        raise VerificationError(f"{path.name} exceeds byte cap")
    return _load_json_bytes(raw)


def _canonical_json(value: Any) -> bytes:
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


def _strict_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _strict_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _strict_equal(left, right)
            for left, right in zip(actual, expected, strict=True)
        )
    return actual == expected


def _exact_keys(value: Mapping[str, Any], keys: Iterable[str], label: str) -> None:
    if set(value) != set(keys):
        raise VerificationError(f"{label} schema drift")


def _strict_int(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise VerificationError(f"{label} must be an integer >= {minimum}")
    return value


def _strict_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise VerificationError(f"{label} must be a boolean")
    return value


def _strict_sha(value: Any, label: str, sha1: bool = False) -> str:
    pattern = SHA1_RE if sha1 else SHA256_RE
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise VerificationError(f"{label} is not a canonical hash")
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
                    raise VerificationError(f"{path.name} exceeds byte cap")
                digest.update(block)
    except VerificationError:
        raise
    except OSError as exc:
        raise VerificationError(f"cannot hash {path.name}: {exc}") from exc
    return total, digest.hexdigest()


def _filesystem_type(path: Path) -> str:
    """Resolve the actual mount type rather than trusting receipt metadata."""
    try:
        resolved = str(path.resolve(strict=True))
        lines = Path("/proc/self/mountinfo").read_text(
            encoding="utf-8", errors="strict"
        ).splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise VerificationError(f"cannot determine scratch filesystem: {exc}") from exc
    best: tuple[int, str] | None = None
    for line in lines:
        fields = line.split()
        if "-" not in fields or len(fields) < 5:
            continue
        split = fields.index("-")
        if split + 1 >= len(fields):
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
        raise VerificationError("scratch filesystem is absent from mountinfo")
    return best[1]


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if check and completed.returncode:
        raise VerificationError(f"git query failed: {' '.join(args)}")
    return completed


def _commit_record(commit: str) -> dict[str, Any]:
    _strict_sha(commit, "commit", sha1=True)
    resolved = _git("rev-parse", f"{commit}^{{commit}}").stdout.decode().strip()
    if resolved != commit:
        raise VerificationError("commit is not exact")
    fields = _git("rev-list", "--parents", "-n", "1", commit).stdout.decode().split()
    return {
        "commit": commit,
        "tree": _git("rev-parse", f"{commit}^{{tree}}").stdout.decode().strip(),
        "parents": fields[1:],
    }


def _git_path_exists(commit: str, relative: str) -> bool:
    completed = _git("ls-tree", commit, "--", relative, check=False)
    if completed.returncode:
        raise VerificationError("git path existence query failed")
    return bool(completed.stdout.strip())


def _git_blob(commit: str, relative: str) -> dict[str, Any]:
    fields = _git("ls-tree", commit, relative).stdout.decode().split()
    if len(fields) < 3 or fields[1] != "blob":
        raise VerificationError(f"missing Git blob: {relative}")
    return {
        "mode": fields[0],
        "blob": fields[2],
        "bytes": int(_git("cat-file", "-s", f"{commit}:{relative}").stdout),
    }


def _verify_kernel_custody(
    contract: Mapping[str, Any],
    custody: Mapping[str, Any],
    *,
    bind_commit: str | None = None,
) -> None:
    if not isinstance(custody, dict):
        raise VerificationError("kernel custody must be an object")
    _exact_keys(
        custody,
        (
            "artifacts",
            "compiled_from_single_pre_action_byte_snapshot",
            "transitive_worktree_module_or_contract_loads_during_action",
        ),
        "kernel custody",
    )
    if (
        not _strict_bool(
            custody["compiled_from_single_pre_action_byte_snapshot"],
            "kernel_custody.compiled_from_single_pre_action_byte_snapshot",
        )
        or _strict_bool(
            custody["transitive_worktree_module_or_contract_loads_during_action"],
            "kernel_custody.transitive_worktree_module_or_contract_loads_during_action",
        )
    ):
        raise VerificationError("kernel custody execution model drift")
    pins = contract["source_authority"]["kernel_source_pins"]
    artifacts = custody["artifacts"]
    if (
        not isinstance(pins, list)
        or not isinstance(artifacts, list)
        or len(pins) != len(KERNEL_SOURCE_NAMES)
        or len(artifacts) != len(KERNEL_SOURCE_NAMES)
    ):
        raise VerificationError("kernel custody artifact count drift")
    for expected_path, pin, artifact in zip(
        KERNEL_SOURCE_NAMES, pins, artifacts, strict=True
    ):
        if not isinstance(pin, dict) or not isinstance(artifact, dict):
            raise VerificationError("kernel custody entries must be objects")
        _exact_keys(pin, ("path", "sha256"), "kernel source pin")
        _exact_keys(
            artifact,
            (
                "path",
                "bytes",
                "sha256",
                "device",
                "inode",
                "mode",
                "mtime_ns",
                "ctime_ns",
                "git_blob",
            ),
            "kernel custody artifact",
        )
        if (
            pin["path"] != expected_path
            or artifact["path"] != expected_path
            or artifact["sha256"] != pin["sha256"]
            or _strict_int(
                artifact["bytes"], f"kernel_custody.{expected_path}.bytes", 1
            )
            > 1_048_576
            or _strict_int(
                artifact["device"], f"kernel_custody.{expected_path}.device"
            )
            < 0
            or _strict_int(
                artifact["inode"], f"kernel_custody.{expected_path}.inode", 1
            )
            < 1
            or _strict_int(
                artifact["mode"], f"kernel_custody.{expected_path}.mode"
            )
            != 0o644
            or _strict_int(
                artifact["mtime_ns"], f"kernel_custody.{expected_path}.mtime_ns"
            )
            < 0
            or _strict_int(
                artifact["ctime_ns"], f"kernel_custody.{expected_path}.ctime_ns"
            )
            < 0
        ):
            raise VerificationError("kernel custody artifact identity drift")
        _strict_sha(pin["sha256"], f"kernel pin {expected_path}")
        _strict_sha(artifact["sha256"], f"kernel artifact {expected_path}")
        _strict_sha(
            artifact["git_blob"], f"kernel artifact {expected_path}.git_blob", sha1=True
        )
        if bind_commit is None:
            continue
        path = HERE / expected_path
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise VerificationError(
                f"kernel artifact unavailable: {expected_path}: {exc}"
            ) from exc
        size, digest = _sha_file(path, 1_048_576)
        git_identity = _git_blob(bind_commit, f"{REL_PREFIX}{expected_path}")
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != artifact["mode"]
            or size != artifact["bytes"]
            or digest != artifact["sha256"]
            or git_identity
            != {
                "mode": "100644",
                "blob": artifact["git_blob"],
                "bytes": artifact["bytes"],
            }
        ):
            raise VerificationError(
                f"kernel artifact working/Git binding drift: {expected_path}"
            )


def _diff_entries(commit: str) -> list[str]:
    return _git(
        "diff-tree", "--no-commit-id", "--name-status", "-r", commit
    ).stdout.decode("utf-8").splitlines()


def _load_runner() -> types.ModuleType:
    raw = RUNNER_PATH.read_bytes()
    module = types.ModuleType("fh_l8_d18c_runner_checked")
    module.__file__ = str(RUNNER_PATH)
    sys.modules[module.__name__] = module
    try:
        exec(compile(raw, str(RUNNER_PATH), "exec"), module.__dict__)
    except Exception as exc:
        raise VerificationError(f"runner cannot be loaded: {exc}") from exc
    return module


def verify_implementation_source(
    contract_must_be_absent: bool = True,
    result_must_be_absent: bool = True,
) -> dict[str, Any]:
    """Verify the zero-action C1 source set before or after its freeze."""
    runner_raw = RUNNER_PATH.read_bytes()
    checker_raw = CHECKER_PATH.read_bytes()
    launcher_raw = LAUNCHER_PATH.read_bytes()
    test_raw = TEST_PATH.read_bytes()
    try:
        runner_tree = ast.parse(runner_raw, filename=str(RUNNER_PATH))
        ast.parse(checker_raw, filename=str(CHECKER_PATH))
        ast.parse(launcher_raw, filename=str(LAUNCHER_PATH))
        ast.parse(test_raw, filename=str(TEST_PATH))
    except SyntaxError as exc:
        raise VerificationError(f"implementation syntax failure: {exc}") from exc
    forbidden = (
        b"fh_l8_checkpointed_quotient_h_d11_runner.py",
        b"def full_spill",
        b"def full_merge",
        b"--full-spill",
        b"--full-merge",
    )
    if any(token in runner_raw for token in forbidden):
        raise VerificationError("legacy/full consumer entrypoint present in D18-C runner")
    function_names = {
        node.name for node in ast.walk(runner_tree) if isinstance(node, ast.FunctionDef)
    }
    required = {
        "_admit_source",
        "_spill",
        "_load_spill_manifest",
        "_merge",
        "_naive_replay",
        "_resource_delta",
        "_atomic_publish",
        "run",
    }
    if not required.issubset(function_names):
        raise VerificationError("required bounded consumer functions missing")
    if contract_must_be_absent and os.path.lexists(CONTRACT_PATH):
        raise VerificationError("contract must be absent at implementation freeze")
    if result_must_be_absent and os.path.lexists(RESULT_PATH):
        raise VerificationError("result must be absent before official action")
    runner = _load_runner()
    if (
        runner.CONTRACT_ID != CONTRACT_ID
        or runner.BOUNDED_ROWS != BOUNDED_ROWS
        or runner.SOURCE_RECORDS != SOURCE_RECORDS
        or runner.PARTITIONS != PARTITIONS
        or runner.SOURCE_RECORD.size != SOURCE_RECORD.size
        or runner.SPILL_RECORD.size != SPILL_RECORD.size
    ):
        raise VerificationError("runner constants drift")
    return {
        "status": "VERIFIED_D18C_ZERO_ACTION_IMPLEMENTATION_SOURCE",
        "verified": True,
        "scientific_action_calls": 0,
        "q3_rows_acted": 0,
        "action_started": False,
        "contract_present": CONTRACT_PATH.exists(),
        "result_present": RESULT_PATH.exists(),
        "runner_sha256": hashlib.sha256(runner_raw).hexdigest(),
        "checker_sha256": hashlib.sha256(checker_raw).hexdigest(),
        "launcher_sha256": hashlib.sha256(launcher_raw).hexdigest(),
        "test_sha256": hashlib.sha256(test_raw).hexdigest(),
    }


def _verify_source_authority(contract: Mapping[str, Any]) -> dict[str, Any]:
    source = contract["source_authority"]
    packed = source["packed_checkpoint"]
    if _git(
        "merge-base",
        "--is-ancestor",
        source["packed_c3_commit"],
        "HEAD",
        check=False,
    ).returncode:
        raise VerificationError("packed C3 is not an ancestor of execution line")
    identity = _git_blob(
        source["packed_c3_commit"], f"{REL_PREFIX}{packed['path']}"
    )
    expected_identity = {
        "mode": packed["mode"],
        "blob": packed["blob"],
        "bytes": packed["bytes"],
    }
    if identity != expected_identity:
        raise VerificationError("packed checkpoint Git identity drift")
    try:
        source_stat = SOURCE_PATH.lstat()
    except OSError as exc:
        raise VerificationError(f"packed checkpoint stat failed: {exc}") from exc
    size, digest = _sha_file(SOURCE_PATH, packed["bytes"])
    expected_mode = int(packed["mode"], 8) & 0o7777
    if (
        not stat.S_ISREG(source_stat.st_mode)
        or stat.S_IMODE(source_stat.st_mode) != expected_mode
        or size != packed["bytes"]
        or digest != packed["sha256"]
    ):
        raise VerificationError("packed checkpoint working identity drift")
    raw_prefix = SOURCE_PATH.read_bytes()[: BOUNDED_ROWS * SOURCE_RECORD.size]
    if hashlib.sha256(raw_prefix).hexdigest() != source["first_4096_raw_sha256"]:
        raise VerificationError("first-4096 raw prefix drift")
    projection = hashlib.sha256()
    prior = -1
    for offset in range(0, len(raw_prefix), SOURCE_RECORD.size):
        representative_raw, amplitude, _, _, _, _ = SOURCE_RECORD.unpack(
            raw_prefix[offset : offset + SOURCE_RECORD.size]
        )
        representative = int.from_bytes(representative_raw, "big")
        if representative <= prior:
            raise VerificationError("first-4096 projection order drift")
        prior = representative
        projection.update(representative_raw)
        projection.update(struct.pack(">q", amplitude))
    if projection.hexdigest() != source["first_4096_projection_sha256"]:
        raise VerificationError("first-4096 projection digest drift")
    return {
        "packed_c3_ancestor": True,
        "payload_bytes": size,
        "payload_sha256": digest,
        "first_4096_raw_sha256": hashlib.sha256(raw_prefix).hexdigest(),
        "first_4096_projection_sha256": projection.hexdigest(),
    }


def verify_contract() -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise VerificationError("contract verification requires a clean worktree")
    implementation = verify_implementation_source(
        contract_must_be_absent=False, result_must_be_absent=True
    )
    contract = _load_json(CONTRACT_PATH, 262_144)
    if CONTRACT_PATH.read_bytes() != _canonical_json(contract):
        raise VerificationError("contract is not canonical JSON")
    runner = _load_runner()
    try:
        runner._validate_contract(contract)
    except Exception as exc:
        raise VerificationError(f"runner rejects frozen contract: {exc}") from exc
    chronology = contract["chronology"]
    head = _git("rev-parse", "HEAD^{commit}").stdout.decode().strip()
    parent = _git("rev-parse", "HEAD^").stdout.decode().strip()
    if parent != chronology["implementation_freeze_commit"]:
        raise VerificationError("contract parent drift")
    if _diff_entries(head) != [f"A\t{REL_PREFIX}{CONTRACT_NAME}"]:
        raise VerificationError("contract freeze did not add only the contract")
    contract_identity = _git_blob(head, f"{REL_PREFIX}{CONTRACT_NAME}")
    if (
        contract_identity["mode"] != "100644"
        or contract_identity["bytes"] != CONTRACT_PATH.stat().st_size
        or _git("cat-file", "blob", contract_identity["blob"]).stdout
        != CONTRACT_PATH.read_bytes()
    ):
        raise VerificationError("contract working bytes/Git blob drift")
    if _git_path_exists(parent, f"{REL_PREFIX}{CONTRACT_NAME}") or _git_path_exists(
        parent, f"{REL_PREFIX}{RESULT_NAME}"
    ):
        raise VerificationError("contract/result existed before contract freeze")
    implementation_commit = _commit_record(parent)
    baseline = chronology["evidence_baseline_commit"]
    if implementation_commit["parents"] != [baseline]:
        raise VerificationError("implementation freeze parent drift")
    if sorted(_diff_entries(parent)) != sorted(
        [
            f"A\t{REL_PREFIX}{RUNNER_NAME}",
            f"A\t{REL_PREFIX}{CHECKER_NAME}",
            f"A\t{REL_PREFIX}{LAUNCHER_NAME}",
            f"A\t{REL_PREFIX}{TEST_NAME}",
        ]
    ):
        raise VerificationError("implementation freeze artifact set drift")
    for label in ("runner", "checker", "launcher", "test"):
        expected = contract["implementation"][label]
        observed = _git_blob(parent, f"{REL_PREFIX}{expected['path']}")
        if observed != {
            "mode": expected["mode"],
            "blob": expected["blob"],
            "bytes": expected["bytes"],
        }:
            raise VerificationError(f"{label} Git pin drift")
        size, digest = _sha_file(HERE / expected["path"], expected["bytes"])
        if size != expected["bytes"] or digest != expected["sha256"]:
            raise VerificationError(f"{label} SHA pin drift")
    source_record = _verify_source_authority(contract)
    try:
        authority_record = runner._verify_authority_documents(contract)
    except Exception as exc:
        raise VerificationError(f"source authority documents rejected: {exc}") from exc
    return {
        "status": "VERIFIED_D18C_CONTRACT_FROZEN_AFTER_ZERO_ACTION_IMPLEMENTATION",
        "verified": True,
        "implementation": implementation,
        "chronology": {
            "evidence_baseline_commit": baseline,
            "implementation_freeze": implementation_commit,
            "contract_freeze_commit": head,
            "result_absent": True,
        },
        "source": source_record,
        "source_authority": authority_record,
        "execution_authorization": contract["execution_authorization"],
        "authority_ceiling": contract["authority_ceiling"],
    }


def _verify_target(
    contract: Mapping[str, Any], scratch: Path, receipt: Mapping[str, Any]
) -> dict[str, Any]:
    target = scratch / "bounded-q4-partial.bin"
    manifest_path = scratch / "bounded-q4-partial.manifest.json"
    target_record = receipt["bounded_partial_target"]
    size, digest = _sha_file(target, contract["resource_limits"]["max_target_bytes"])
    if (
        size != target_record["target_bytes"]
        or digest != target_record["target_sha256"]
        or size != target_record["target_records"] * SPILL_RECORD.size
    ):
        raise VerificationError("bounded target identity drift")
    manifest = _load_json(
        manifest_path, contract["resource_limits"]["max_manifest_bytes"]
    )
    if (
        manifest.get("contract_id") != CONTRACT_ID
        or manifest.get("classification")
        != "BOUNDED_FIRST_4096_Q3_ROWS_PARTIAL_Q4_NOT_A_FULL_Q4_OPERAND"
        or manifest.get("ordering")
        != "partition_sha256_byte_then_target_u128"
        or manifest.get("complete") is not True
        or manifest.get("target_records") != target_record["target_records"]
        or manifest.get("target_bytes") != target_record["target_bytes"]
        or manifest.get("target_sha256") != target_record["target_sha256"]
    ):
        raise VerificationError("bounded target manifest drift")
    counts = manifest.get("partition_target_counts")
    if (
        not isinstance(counts, list)
        or len(counts) != PARTITIONS
        or any(type(item) is not int or item < 0 for item in counts)
        or sum(counts) != target_record["target_records"]
    ):
        raise VerificationError("bounded target partition counts drift")
    partition_order_digest = hashlib.sha256()
    partition_offsets: list[int] = []
    observed_records = 0
    offset = 0
    with target.open("rb", buffering=0) as handle:
        for partition, count in enumerate(counts):
            partition_offsets.append(offset)
            prior = -1
            for _ in range(count):
                raw = handle.read(SPILL_RECORD.size)
                if len(raw) != SPILL_RECORD.size:
                    raise VerificationError("bounded target truncated")
                target_raw, amplitude, reserved = SPILL_RECORD.unpack(raw)
                target_int = int.from_bytes(target_raw, "big")
                if (
                    reserved != 0
                    or amplitude == 0
                    or target_int <= prior
                    or hashlib.sha256(target_raw).digest()[0] != partition
                ):
                    raise VerificationError("bounded target semantic drift")
                prior = target_int
                partition_order_digest.update(raw)
                observed_records += 1
                offset += SPILL_RECORD.size
        if handle.read(1):
            raise VerificationError("bounded target has trailing bytes")
    if observed_records != target_record["target_records"] or offset != size:
        raise VerificationError("bounded target record coverage drift")

    # The on-disk order is partition-first, while the naïve replay commits to
    # globally increasing target representatives.  Merge the 256 already-sorted
    # partition runs with a bounded heap and bind that digest explicitly.
    global_digest = hashlib.sha256()
    heap: list[tuple[bytes, int, int, bytes]] = []
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(target, flags)
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != size:
            raise VerificationError("bounded target type/size drift")
        for partition, count in enumerate(counts):
            if not count:
                continue
            raw = os.pread(fd, SPILL_RECORD.size, partition_offsets[partition])
            if len(raw) != SPILL_RECORD.size:
                raise VerificationError("bounded target partition run truncated")
            target_raw, _, _ = SPILL_RECORD.unpack(raw)
            heapq.heappush(heap, (target_raw, partition, 0, raw))
        prior_global: bytes | None = None
        merged_records = 0
        while heap:
            target_raw, partition, index, raw = heapq.heappop(heap)
            if prior_global is not None and target_raw <= prior_global:
                raise VerificationError("bounded target global ordering drift")
            prior_global = target_raw
            global_digest.update(raw)
            merged_records += 1
            next_index = index + 1
            if next_index < counts[partition]:
                next_raw = os.pread(
                    fd,
                    SPILL_RECORD.size,
                    partition_offsets[partition] + next_index * SPILL_RECORD.size,
                )
                if len(next_raw) != SPILL_RECORD.size:
                    raise VerificationError("bounded target partition run truncated")
                next_target_raw, _, _ = SPILL_RECORD.unpack(next_raw)
                heapq.heappush(
                    heap, (next_target_raw, partition, next_index, next_raw)
                )
    except OSError as exc:
        raise VerificationError(f"bounded target global merge failed: {exc}") from exc
    finally:
        if "fd" in locals():
            os.close(fd)
    global_semantic_sha256 = global_digest.hexdigest()
    if (
        merged_records != target_record["target_records"]
        or global_semantic_sha256
        != receipt["naive_equivalence"]["target_sorted_semantic_sha256"]
    ):
        raise VerificationError(
            "naive semantic digest is not bound to external globally sorted target"
        )
    return {
        "target_records": observed_records,
        "target_bytes": size,
        "target_sha256": digest,
        "partition_order_valid": True,
        "partition_order_semantic_sha256": partition_order_digest.hexdigest(),
        "global_sorted_semantic_sha256": global_semantic_sha256,
        "naive_semantic_digest_bound": True,
        "full_q4_operand": False,
    }


def _verify_result_schema(
    contract: Mapping[str, Any], result: Mapping[str, Any]
) -> None:
    _exact_keys(
        result,
        (
            "schema_version",
            "contract_id",
            "status",
            "verified",
            "analysis_class",
            "implementation_freeze_commit",
            "contract_freeze_commit",
            "source",
            "source_authority",
            "kernel_custody",
            "scratch_custody",
            "state",
            "spill",
            "bounded_partial_target",
            "naive_equivalence",
            "diagnostic_comparator",
            "resources",
            "authority",
            "limitations",
            "next_gate",
            "terminal_receipt",
            "launcher_receipt",
        ),
        "result",
    )
    if (
        _strict_int(result["schema_version"], "result.schema_version") != 1
        or result["contract_id"] != CONTRACT_ID
        or result["status"]
        != "VERIFIED_D18C_FRESH_EXCLUSIVE_PACKED_Q3_BOUNDED_4096_PREFLIGHT"
        or not _strict_bool(result["verified"], "result.verified")
        or result["analysis_class"]
        != "BOUNDED_PARTIAL_Q3_TO_Q4_SCIENTIFIC_ACTION"
    ):
        raise VerificationError("result header drift")
    if result["implementation_freeze_commit"] != contract["chronology"][
        "implementation_freeze_commit"
    ]:
        raise VerificationError("result implementation commit drift")
    _strict_sha(result["contract_freeze_commit"], "result.contract_freeze_commit", sha1=True)
    state = result["state"]
    expected_state = {
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
    }
    if not _strict_equal(state, expected_state):
        raise VerificationError("result state machine drift")
    source = result["source"]
    _exact_keys(
        source,
        (
            "records_validated",
            "record_bytes",
            "payload_bytes",
            "payload_sha256",
            "first_4096_raw_sha256",
            "first_4096_projection_sha256",
            "first_representative_hex",
            "last_selected_representative_hex",
            "rank_permutation_valid",
            "source_stat",
        ),
        "result source",
    )
    if (
        _strict_int(source["records_validated"], "source.records_validated")
        != SOURCE_RECORDS
        or _strict_int(source["record_bytes"], "source.record_bytes")
        != SOURCE_RECORD.size
        or _strict_int(source["payload_bytes"], "source.payload_bytes")
        != SOURCE_RECORDS * SOURCE_RECORD.size
        or source["payload_sha256"]
        != contract["source_authority"]["packed_checkpoint"]["sha256"]
        or source["first_4096_raw_sha256"]
        != contract["source_authority"]["first_4096_raw_sha256"]
        or source["first_4096_projection_sha256"]
        != contract["source_authority"]["first_4096_projection_sha256"]
        or not _strict_bool(
            source["rank_permutation_valid"], "source.rank_permutation_valid"
        )
    ):
        raise VerificationError("result source record drift")
    for key in ("payload_sha256", "first_4096_raw_sha256", "first_4096_projection_sha256"):
        _strict_sha(source[key], f"source.{key}")
    if (
        not isinstance(source["first_representative_hex"], str)
        or not isinstance(source["last_selected_representative_hex"], str)
        or re.fullmatch(r"0x[0-9a-f]+", source["first_representative_hex"]) is None
        or re.fullmatch(r"0x[0-9a-f]+", source["last_selected_representative_hex"])
        is None
    ):
        raise VerificationError("result source representative drift")
    source_stat = source["source_stat"]
    _exact_keys(
        source_stat,
        ("device", "inode", "mode", "size", "mtime_ns", "ctime_ns"),
        "result source stat",
    )
    for key in ("device", "inode", "mode", "size", "mtime_ns", "ctime_ns"):
        _strict_int(source_stat[key], f"source_stat.{key}")
    expected_source_mode = (
        int(contract["source_authority"]["packed_checkpoint"]["mode"], 8) & 0o7777
    )
    if (
        source_stat["size"] != SOURCE_RECORDS * SOURCE_RECORD.size
        or source_stat["mode"] != expected_source_mode
    ):
        raise VerificationError("result source stat size/mode drift")
    expected_source_authority = {
        "packed_c3_ancestor": True,
        "d18_result_ancestor": True,
        "d16_packed_q3_admissible": True,
        "d16_legacy_q4_quarantined": True,
        "d17_prior_bounded_execution_authorized": False,
        "d18_diagnostic_execution_authority_admitted": False,
    }
    if not _strict_equal(result["source_authority"], expected_source_authority):
        raise VerificationError("result source authority drift")
    _verify_kernel_custody(contract, result["kernel_custody"])
    scratch = result["scratch_custody"]
    _exact_keys(
        scratch,
        (
            "filesystem_type",
            "scratch_parent_device",
            "scratch_parent_owner_uid",
            "scratch_parent_mode",
            "scratch_root_device",
            "scratch_root_inode",
            "scratch_root_owner_uid",
            "scratch_root_mode",
            "exclusive_lock_device",
            "exclusive_lock_inode",
            "exclusive_lock_owner_uid",
            "exclusive_lock_mode",
            "exclusive_lock",
            "created_regular_files_before_receipt",
        ),
        "scratch custody",
    )
    if (
        not isinstance(scratch["filesystem_type"], str)
        or not scratch["filesystem_type"]
        or scratch["filesystem_type"]
        in contract["consumer_protocol"]["deny_filesystem_types"]
        or _strict_int(
            scratch["scratch_parent_device"], "scratch_parent_device"
        )
        < 0
        or _strict_int(
            scratch["scratch_parent_owner_uid"], "scratch_parent_owner_uid"
        )
        < 0
        or _strict_int(scratch["scratch_parent_mode"], "scratch_parent_mode") > 0o7777
        or _strict_int(scratch["scratch_root_device"], "scratch_root_device") < 0
        or _strict_int(scratch["scratch_root_inode"], "scratch_root_inode") < 1
        or _strict_int(scratch["scratch_root_owner_uid"], "scratch_root_owner_uid") < 0
        or _strict_int(scratch["scratch_root_mode"], "scratch_root_mode") > 0o7777
        or _strict_int(scratch["exclusive_lock_device"], "exclusive_lock_device") < 0
        or _strict_int(scratch["exclusive_lock_inode"], "exclusive_lock_inode") < 1
        or _strict_int(
            scratch["exclusive_lock_owner_uid"], "exclusive_lock_owner_uid"
        )
        < 0
        or _strict_int(scratch["exclusive_lock_mode"], "exclusive_lock_mode") > 0o7777
        or not _strict_bool(scratch["exclusive_lock"], "exclusive_lock")
        or not isinstance(scratch["created_regular_files_before_receipt"], list)
        or len(scratch["created_regular_files_before_receipt"])
        != contract["resource_limits"]["maximum_runner_created_regular_files"] - 1
        or any(
            not isinstance(item, str) or not item
            for item in scratch["created_regular_files_before_receipt"]
        )
    ):
        raise VerificationError("result scratch custody drift")
    expected_pre_receipt_files = sorted(
        {
            "exclusive.lock",
            "bounded-q4-partial.bin",
            "bounded-q4-partial.manifest.json",
            "spill/manifest.json",
        }
        | {f"spill/p{index:03d}.bin" for index in range(PARTITIONS)}
    )
    if (
        sorted(scratch["created_regular_files_before_receipt"])
        != expected_pre_receipt_files
        or scratch["scratch_parent_mode"] & 0o022
        or scratch["scratch_root_mode"] != 0o700
        or scratch["exclusive_lock_mode"] != 0o600
        or scratch["scratch_root_owner_uid"] != scratch["scratch_parent_owner_uid"]
        or scratch["exclusive_lock_owner_uid"] != scratch["scratch_root_owner_uid"]
    ):
        raise VerificationError("result scratch exact file/mode custody drift")
    spill = result["spill"]
    _exact_keys(
        spill,
        (
            "manifest",
            "spill_records",
            "spill_bytes",
            "reduced_columns",
            "projected_zero_outputs",
            "zero_coefficients_dropped",
            "partition_count",
        ),
        "result spill",
    )
    for key in (
        "spill_records",
        "spill_bytes",
        "reduced_columns",
        "projected_zero_outputs",
        "zero_coefficients_dropped",
        "partition_count",
    ):
        _strict_int(spill[key], f"spill.{key}")
    comparator = contract["diagnostic_comparator"]
    for key, expected in EXPECTED_COMPARATOR_COUNTS.items():
        if _strict_int(comparator[key], f"comparator.{key}") != expected:
            raise VerificationError("frozen diagnostic comparator count drift")
    if (
        spill["spill_records"] != comparator["spill_records"]
        or spill["reduced_columns"] != comparator["reduced_columns"]
        or spill["projected_zero_outputs"]
        != comparator["projected_zero_outputs"]
        or spill["zero_coefficients_dropped"] != 0
        or spill["partition_count"] != comparator["partition_count"]
        or spill["spill_bytes"] != spill["spill_records"] * SPILL_RECORD.size
        or spill["spill_bytes"] > contract["resource_limits"]["max_spill_bytes"]
    ):
        raise VerificationError("result spill frozen comparator/count drift")
    _exact_keys(spill["manifest"], ("path", "bytes", "sha256"), "spill manifest")
    if spill["manifest"]["path"] != "manifest.json":
        raise VerificationError("result spill manifest path drift")
    _strict_int(spill["manifest"]["bytes"], "spill.manifest.bytes", 1)
    _strict_sha(spill["manifest"]["sha256"], "spill.manifest.sha256")
    target = result["bounded_partial_target"]
    _exact_keys(
        target,
        (
            "target",
            "manifest",
            "target_records",
            "target_bytes",
            "target_sha256",
            "ordering",
            "partition_target_counts",
        ),
        "bounded partial target",
    )
    for key, name in (("target", "bounded-q4-partial.bin"), ("manifest", "bounded-q4-partial.manifest.json")):
        _exact_keys(target[key], ("path", "bytes", "sha256"), f"target.{key}")
        if target[key]["path"] != name:
            raise VerificationError(f"target {key} path drift")
        _strict_int(target[key]["bytes"], f"target.{key}.bytes", 1)
        _strict_sha(target[key]["sha256"], f"target.{key}.sha256")
    _strict_int(target["target_records"], "target.target_records", 1)
    _strict_int(target["target_bytes"], "target.target_bytes", 1)
    _strict_sha(target["target_sha256"], "target.target_sha256")
    if (
        target["target"]["bytes"] != target["target_bytes"]
        or target["target"]["sha256"] != target["target_sha256"]
        or target["ordering"] != "partition_sha256_byte_then_target_u128"
        or not isinstance(target["partition_target_counts"], list)
        or len(target["partition_target_counts"]) != PARTITIONS
        or any(
            type(item) is not int or item < 0
            for item in target["partition_target_counts"]
        )
        or sum(target["partition_target_counts"]) != target["target_records"]
    ):
        raise VerificationError("bounded partial target structure drift")
    if (
        target.get("target_records") != comparator["target_records"]
        or target.get("target_bytes") != comparator["target_bytes"]
        or target.get("target_sha256") != comparator["target_sha256"]
        or result["naive_equivalence"].get("verified") is not True
        or result["naive_equivalence"].get("source_rows_replayed") != BOUNDED_ROWS
        or result["naive_equivalence"].get("target_records")
        != comparator["target_records"]
    ):
        raise VerificationError("result arithmetic/equivalence drift")
    equivalence = result["naive_equivalence"]
    _exact_keys(
        equivalence,
        (
            "verified",
            "source_rows_replayed",
            "target_records",
            "target_sorted_semantic_sha256",
        ),
        "second-pass equivalence",
    )
    if (
        not _strict_bool(equivalence["verified"], "equivalence.verified")
        or _strict_int(
            equivalence["source_rows_replayed"], "equivalence.source_rows_replayed"
        )
        != BOUNDED_ROWS
        or _strict_int(
            equivalence["target_records"], "equivalence.target_records"
        )
        != comparator["target_records"]
    ):
        raise VerificationError("second-pass equivalence drift")
    _strict_sha(
        equivalence["target_sorted_semantic_sha256"],
        "equivalence.target_sorted_semantic_sha256",
    )
    diagnostic = result["diagnostic_comparator"]
    _exact_keys(
        diagnostic,
        (
            "authority",
            "role",
            "mismatch_is_preflight_no_go",
            "match",
            "target_records",
            "target_bytes",
            "target_sha256",
            "spill_records",
            "reduced_columns",
            "projected_zero_outputs",
            "partition_count",
        ),
        "result diagnostic comparator",
    )
    if (
        _strict_bool(diagnostic["authority"], "diagnostic.authority") is not False
        or diagnostic["role"]
        != "PREREGISTERED_NON_AUTHORITATIVE_REPRODUCIBILITY_GUARD"
        or not _strict_bool(
            diagnostic["mismatch_is_preflight_no_go"],
            "diagnostic.mismatch_is_preflight_no_go",
        )
        or not _strict_bool(diagnostic["match"], "diagnostic.match")
        or _strict_int(diagnostic["target_records"], "diagnostic.target_records")
        != comparator["target_records"]
        or _strict_int(diagnostic["target_bytes"], "diagnostic.target_bytes")
        != comparator["target_bytes"]
        or diagnostic["target_sha256"] != comparator["target_sha256"]
        or _strict_int(diagnostic["spill_records"], "diagnostic.spill_records")
        != comparator["spill_records"]
        or _strict_int(
            diagnostic["reduced_columns"], "diagnostic.reduced_columns"
        )
        != comparator["reduced_columns"]
        or _strict_int(
            diagnostic["projected_zero_outputs"],
            "diagnostic.projected_zero_outputs",
        )
        != comparator["projected_zero_outputs"]
        or _strict_int(
            diagnostic["partition_count"], "diagnostic.partition_count", 1
        )
        != comparator["partition_count"]
    ):
        raise VerificationError("diagnostic comparator authority drift")
    _strict_sha(diagnostic["target_sha256"], "diagnostic.target_sha256")
    resources = result["resources"]
    _exact_keys(
        resources,
        (
            "cgroup_path",
            "cgroup_inode",
            "memory_current_before_bytes",
            "memory_current_after_bytes",
            "memory_peak_before_bytes",
            "memory_peak_after_bytes",
            "memory_max",
            "memory_high",
            "memory_swap_current_after_bytes",
            "memory_swap_max",
            "memory_event_delta",
            "process_peak_rss_bytes",
            "observation_scope",
            "elapsed_monotonic_ns",
        ),
        "result resources",
    )
    limits = contract["resource_limits"]
    if (
        resources.get("memory_max") != limits["memory_max"]
        or resources.get("memory_high") != limits["memory_high"]
        or resources.get("memory_swap_max") != limits["memory_swap_max"]
        or resources.get("memory_swap_current_after_bytes") != 0
        or resources.get("memory_peak_before_bytes", 1 << 63)
        > limits["max_initial_memory_peak_bytes"]
        or resources.get("memory_peak_after_bytes", -1)
        < resources.get("memory_peak_before_bytes", 0)
        or resources.get("memory_peak_after_bytes", 1 << 63)
        > limits["max_final_memory_peak_bytes"]
        or resources.get("process_peak_rss_bytes", 1 << 63)
        > limits["max_process_peak_rss_bytes"]
        or resources.get("elapsed_monotonic_ns", 1 << 63)
        > limits["internal_deadline_seconds"] * 1_000_000_000
        or resources.get("observation_scope")
        != (
            "after_bounded_target_and_manifests;"
            "before_runner_terminal_receipt_publication"
        )
    ):
        raise VerificationError("result resource envelope drift")
    for key in (
        "cgroup_inode",
        "memory_current_before_bytes",
        "memory_current_after_bytes",
        "memory_peak_before_bytes",
        "memory_peak_after_bytes",
        "memory_swap_current_after_bytes",
        "process_peak_rss_bytes",
        "elapsed_monotonic_ns",
    ):
        _strict_int(resources[key], f"resources.{key}")
    if (
        not isinstance(resources["cgroup_path"], str)
        or "ab-fh-l8-d18c" not in resources["cgroup_path"]
    ):
        raise VerificationError("result cgroup path drift")
    events = resources.get("memory_event_delta")
    if not isinstance(events, dict) or any(
        type(value) is not int or value < 0 for value in events.values()
    ) or any(events.get(key, -1) != 0 for key in ("high", "max", "oom", "oom_kill")):
        raise VerificationError("result memory event drift")
    expected_authority = {
        "bounded_4096_preflight_executed": True,
        "partial_q3_to_q4_action_executed": True,
        **contract["authority_ceiling"],
    }
    if not _strict_equal(result["authority"], expected_authority):
        raise VerificationError("result authority ceiling drift")
    if result["limitations"] != contract["limitations"]:
        raise VerificationError("result limitations drift")
    if result["next_gate"] != contract["decision_rule"]["next_gate"]:
        raise VerificationError("result next gate drift")
    receipt = result["terminal_receipt"]
    _exact_keys(receipt, ("path", "bytes", "sha256"), "terminal_receipt")
    if receipt["path"] != "terminal-receipt.json":
        raise VerificationError("terminal receipt path drift")
    _strict_int(receipt["bytes"], "terminal_receipt.bytes", 1)
    _strict_sha(receipt["sha256"], "terminal_receipt.sha256")
    launcher = result["launcher_receipt"]
    _exact_keys(launcher, ("path", "bytes", "sha256"), "launcher_receipt")
    if launcher["path"] != "launcher-receipt.json":
        raise VerificationError("launcher receipt path drift")
    _strict_int(launcher["bytes"], "launcher_receipt.bytes", 1)
    _strict_sha(launcher["sha256"], "launcher_receipt.sha256")


def verify_result(scratch: Path | None = None) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise VerificationError("result verification requires a clean worktree")
    contract = _load_json(CONTRACT_PATH, 262_144)
    runner = _load_runner()
    try:
        runner._validate_contract(contract)
    except Exception as exc:
        raise VerificationError(f"runner rejects contract: {exc}") from exc
    result_raw = RESULT_PATH.read_bytes()
    result = _load_json_bytes(result_raw)
    if result_raw != _canonical_json(result):
        raise VerificationError("result is not canonical JSON with one trailing newline")
    _verify_result_schema(contract, result)
    contract_commit = result["contract_freeze_commit"]
    if _diff_entries(contract_commit) != [f"A\t{REL_PREFIX}{CONTRACT_NAME}"]:
        raise VerificationError("result contract commit is not contract-only")
    if _git("rev-parse", f"{contract_commit}^").stdout.decode().strip() != contract[
        "chronology"
    ]["implementation_freeze_commit"]:
        raise VerificationError("result contract parent drift")
    additions = _git(
        "log",
        "--format=%H",
        "--diff-filter=A",
        "--",
        f"{REL_PREFIX}{RESULT_NAME}",
    ).stdout.decode().splitlines()
    if len(additions) != 1:
        raise VerificationError("result must have exactly one addition commit")
    result_commit = additions[0]
    if (
        _git("rev-parse", f"{result_commit}^").stdout.decode().strip()
        != contract_commit
        or _diff_entries(result_commit) != [f"A\t{REL_PREFIX}{RESULT_NAME}"]
    ):
        raise VerificationError("result freeze must be result-only after contract")
    contract_identity = _git_blob(
        contract_commit, f"{REL_PREFIX}{CONTRACT_NAME}"
    )
    result_identity = _git_blob(result_commit, f"{REL_PREFIX}{RESULT_NAME}")
    if (
        contract_identity["mode"] != "100644"
        or result_identity["mode"] != "100644"
        or contract_identity["bytes"] != CONTRACT_PATH.stat().st_size
        or result_identity["bytes"] != len(result_raw)
        or _git("cat-file", "blob", contract_identity["blob"]).stdout
        != CONTRACT_PATH.read_bytes()
        or _git("cat-file", "blob", result_identity["blob"]).stdout != result_raw
    ):
        raise VerificationError("current contract/result bytes differ from frozen Git blobs")
    _verify_kernel_custody(
        contract, result["kernel_custody"], bind_commit=result_commit
    )
    if scratch is None:
        return {
            "status": "D18C_COMMITTED_RESULT_SCHEMA_AND_GIT_PROVENANCE_ONLY",
            "verification_scope": "SCHEMA_AND_GIT_PROVENANCE_ONLY",
            "schema_and_git_provenance_verified": True,
            "external_scratch_verified": False,
            "executed_authority_verified": False,
            "scientific_outcome_verified": False,
        }
    if not scratch.is_absolute() or scratch.parent.resolve(strict=True) != Path(
        contract["consumer_protocol"]["allowed_scratch_parent"]
    ).resolve(strict=True):
        raise VerificationError("external scratch path is not authorized")
    custody = result["scratch_custody"]
    try:
        scratch_stat = scratch.lstat()
        parent_stat = scratch.parent.lstat()
        lock_stat = (scratch / "exclusive.lock").lstat()
    except OSError as exc:
        raise VerificationError(f"external scratch identity unavailable: {exc}") from exc
    if (
        not stat.S_ISDIR(scratch_stat.st_mode)
        or scratch_stat.st_dev != custody["scratch_root_device"]
        or scratch_stat.st_ino != custody["scratch_root_inode"]
        or scratch_stat.st_uid != custody["scratch_root_owner_uid"]
        or stat.S_IMODE(scratch_stat.st_mode) != custody["scratch_root_mode"]
        or parent_stat.st_dev != custody["scratch_parent_device"]
        or parent_stat.st_uid != custody["scratch_parent_owner_uid"]
        or stat.S_IMODE(parent_stat.st_mode) != custody["scratch_parent_mode"]
        or not stat.S_ISREG(lock_stat.st_mode)
        or lock_stat.st_dev != custody["exclusive_lock_device"]
        or lock_stat.st_ino != custody["exclusive_lock_inode"]
        or lock_stat.st_uid != custody["exclusive_lock_owner_uid"]
        or stat.S_IMODE(lock_stat.st_mode) != custody["exclusive_lock_mode"]
        or lock_stat.st_nlink != 1
    ):
        raise VerificationError("external scratch root/lock identity drift")
    actual_filesystem_type = _filesystem_type(scratch)
    if (
        actual_filesystem_type != custody["filesystem_type"]
        or actual_filesystem_type
        in contract["consumer_protocol"]["deny_filesystem_types"]
    ):
        raise VerificationError("external scratch filesystem type is forbidden/drifted")
    receipt_path = scratch / result["terminal_receipt"]["path"]
    size, digest = _sha_file(
        receipt_path, contract["resource_limits"]["max_receipt_bytes"]
    )
    if (
        size != result["terminal_receipt"]["bytes"]
        or digest != result["terminal_receipt"]["sha256"]
    ):
        raise VerificationError("external terminal receipt identity drift")
    external_receipt = _load_json(
        receipt_path, contract["resource_limits"]["max_receipt_bytes"]
    )
    if receipt_path.read_bytes() != _canonical_json(external_receipt):
        raise VerificationError("external terminal receipt is not canonical")
    expected_receipt = dict(result)
    del expected_receipt["terminal_receipt"]
    del expected_receipt["launcher_receipt"]
    if not _strict_equal(external_receipt, expected_receipt):
        raise VerificationError("committed result differs from terminal receipt")
    launcher_path = scratch / result["launcher_receipt"]["path"]
    launcher_size, launcher_digest = _sha_file(
        launcher_path, contract["resource_limits"]["max_receipt_bytes"]
    )
    if (
        launcher_size != result["launcher_receipt"]["bytes"]
        or launcher_digest != result["launcher_receipt"]["sha256"]
    ):
        raise VerificationError("external launcher receipt identity drift")
    launcher = _load_json(
        launcher_path, contract["resource_limits"]["max_receipt_bytes"]
    )
    if launcher_path.read_bytes() != _canonical_json(launcher):
        raise VerificationError("external launcher receipt is not canonical")
    _exact_keys(
        launcher,
        (
            "schema_version",
            "contract_id",
            "status",
            "verified",
            "unit",
            "command_sha256",
            "contract_checker_stdout",
            "runner_return_code",
            "runner_stdout",
            "runner_stderr_bytes",
            "runner_stderr_sha256",
            "systemd_properties",
            "systemd_stop_return_code",
            "post_stop_systemd_properties",
            "post_exit_cgroup",
            "post_exit_memory_peak_bytes",
            "terminal_receipt",
            "observation_scope",
        ),
        "launcher external receipt",
    )
    if (
        _strict_int(launcher["schema_version"], "launcher.schema_version") != 1
        or launcher["contract_id"] != CONTRACT_ID
        or launcher["status"] != "VERIFIED_D18C_POST_EXIT_LAUNCHER_RECEIPT"
        or not _strict_bool(launcher["verified"], "launcher.verified")
        or _strict_int(
            launcher["runner_return_code"], "launcher.runner_return_code"
        )
        != 0
        or _strict_int(
            launcher["runner_stderr_bytes"], "launcher.runner_stderr_bytes"
        )
        != 0
        or _strict_int(
            launcher["systemd_stop_return_code"],
            "launcher.systemd_stop_return_code",
        )
        != 0
        or launcher["runner_stderr_sha256"] != hashlib.sha256(b"").hexdigest()
        or _strict_int(
            launcher["post_exit_memory_peak_bytes"],
            "launcher.post_exit_memory_peak_bytes",
        )
        > contract["resource_limits"]["max_final_memory_peak_bytes"]
        or launcher["terminal_receipt"] != result["terminal_receipt"]
        or launcher["observation_scope"]
        != (
            "after_runner_exit_runner_terminal_receipt_systemd_stop_and_"
            "capture_removal;"
            "before_launcher_receipt_publication"
        )
    ):
        raise VerificationError("launcher terminal evidence drift")
    if not isinstance(launcher["unit"], str) or UNIT_RE.fullmatch(launcher["unit"]) is None:
        raise VerificationError("launcher unit drift")
    _strict_sha(launcher["command_sha256"], "launcher.command_sha256")
    capture_root = scratch.parent / f".{launcher['unit']}-capture"
    expected_command = [
        "/usr/bin/systemd-run",
        "--user",
        "--quiet",
        "--remain-after-exit",
        f"--unit={launcher['unit']}",
        "--service-type=exec",
        "--property=MemoryAccounting=yes",
        f"--property=MemoryMax={contract['resource_limits']['memory_max']}",
        f"--property=MemoryHigh={contract['resource_limits']['memory_high']}",
        f"--property=MemorySwapMax={contract['resource_limits']['memory_swap_max']}",
        "--property=OOMPolicy=stop",
        "--property=TimeoutStartSec=240s",
        "--property=RuntimeMaxSec=240s",
        "--property=TasksMax=64",
        f"--property=StandardOutput=file:{capture_root / 'stdout'}",
        f"--property=StandardError=file:{capture_root / 'stderr'}",
        "/usr/bin/env",
        "-i",
        f"HOME={Path.home()}",
        "PATH=/usr/bin:/bin",
        "LANG=C.UTF-8",
        "LC_ALL=C.UTF-8",
        "PYTHONDONTWRITEBYTECODE=1",
        sys.executable,
        "-I",
        "-B",
        str(RUNNER_PATH),
        "--contract",
        str(CONTRACT_PATH),
        "--scratch",
        str(scratch),
    ]
    expected_command_sha = hashlib.sha256(
        b"\0".join(item.encode("utf-8") for item in expected_command)
    ).hexdigest()
    if launcher["command_sha256"] != expected_command_sha:
        raise VerificationError("launcher command digest drift")
    properties = launcher["systemd_properties"]
    if not isinstance(properties, dict):
        raise VerificationError("launcher systemd property type drift")
    _exact_keys(
        properties,
        (
            "Id",
            "ActiveState",
            "SubState",
            "Result",
            "ExecMainCode",
            "ExecMainStatus",
            "MemoryPeak",
            "MemoryCurrent",
            "ControlGroup",
        ),
        "launcher systemd properties",
    )
    if (
        properties.get("Id") != f"{launcher['unit']}.service"
        or properties.get("ActiveState") != "active"
        or properties.get("SubState") != "exited"
        or properties.get("Result") != "success"
        or properties.get("ExecMainCode") not in ("1", "exited")
        or properties.get("ExecMainStatus") != "0"
        or properties.get("MemoryPeak") != str(launcher["post_exit_memory_peak_bytes"])
        or not result["resources"]["cgroup_path"].endswith(
            f"/{launcher['unit']}.service"
        )
        or properties.get("ControlGroup") != ""
    ):
        raise VerificationError("launcher systemd property drift")
    memory_current = properties["MemoryCurrent"]
    if memory_current != "[not set]" and (
        not memory_current.isdigit()
        or int(memory_current) > int(contract["resource_limits"]["memory_max"])
    ):
        raise VerificationError("launcher MemoryCurrent drift")
    post_stop = launcher["post_stop_systemd_properties"]
    if not isinstance(post_stop, dict):
        raise VerificationError("launcher post-stop property type drift")
    _exact_keys(
        post_stop,
        ("Id", "LoadState", "ActiveState", "SubState", "ControlGroup"),
        "launcher post-stop systemd properties",
    )
    if (
        post_stop["Id"] != f"{launcher['unit']}.service"
        or post_stop["LoadState"] not in ("loaded", "not-found")
        or post_stop["ActiveState"] != "inactive"
        or post_stop["SubState"] != "dead"
        or post_stop["ControlGroup"] != ""
    ):
        raise VerificationError("launcher post-stop systemd property drift")
    post_exit_cgroup = launcher["post_exit_cgroup"]
    if not isinstance(post_exit_cgroup, dict):
        raise VerificationError("launcher post-exit cgroup record type drift")
    _exact_keys(
        post_exit_cgroup,
        (
            "runner_observed_path",
            "pre_stop_control_group",
            "post_stop_control_group",
            "state",
            "explanation",
        ),
        "launcher post-exit cgroup",
    )
    expected_cgroup_explanation = (
        "systemd reported an empty ControlGroup in the post-exit snapshot and "
        "again after the successful stop; the runner's own cgroup path remains "
        "bound to the exact unit Id, but no post-exit ControlGroup path is asserted"
    )
    if (
        post_exit_cgroup["runner_observed_path"] != result["resources"]["cgroup_path"]
        or post_exit_cgroup["pre_stop_control_group"] != ""
        or post_exit_cgroup["post_stop_control_group"] != ""
        or post_exit_cgroup["state"]
        != "ABSENT_AT_POST_EXIT_INSPECTION_AND_AFTER_STOP"
        or post_exit_cgroup["explanation"] != expected_cgroup_explanation
    ):
        raise VerificationError("launcher post-exit cgroup semantics drift")
    stdout_record = launcher["runner_stdout"]
    _exact_keys(stdout_record, ("path", "bytes", "sha256"), "runner_stdout")
    if stdout_record["path"] != "runner-stdout.json":
        raise VerificationError("runner stdout path drift")
    _strict_int(stdout_record["bytes"], "runner_stdout.bytes", 1)
    _strict_sha(stdout_record["sha256"], "runner_stdout.sha256")
    stdout_size, stdout_digest = _sha_file(
        scratch / stdout_record["path"],
        contract["resource_limits"]["max_receipt_bytes"],
    )
    if stdout_size != stdout_record["bytes"] or stdout_digest != stdout_record["sha256"]:
        raise VerificationError("runner stdout identity drift")
    runner_stdout = _load_json(
        scratch / stdout_record["path"],
        contract["resource_limits"]["max_receipt_bytes"],
    )
    expected_stdout = dict(result)
    del expected_stdout["launcher_receipt"]
    if not _strict_equal(runner_stdout, expected_stdout):
        raise VerificationError("captured runner stdout differs from committed result")
    contract_stdout_record = launcher["contract_checker_stdout"]
    _exact_keys(
        contract_stdout_record, ("path", "bytes", "sha256"), "contract_checker_stdout"
    )
    if contract_stdout_record["path"] != "contract-checker-stdout.json":
        raise VerificationError("contract checker stdout path drift")
    _strict_int(contract_stdout_record["bytes"], "contract_checker_stdout.bytes", 1)
    _strict_sha(contract_stdout_record["sha256"], "contract_checker_stdout.sha256")
    contract_stdout_size, contract_stdout_digest = _sha_file(
        scratch / contract_stdout_record["path"],
        contract["resource_limits"]["max_receipt_bytes"],
    )
    if (
        contract_stdout_size != contract_stdout_record["bytes"]
        or contract_stdout_digest != contract_stdout_record["sha256"]
    ):
        raise VerificationError("contract checker stdout identity drift")
    contract_stdout = _load_json(
        scratch / contract_stdout_record["path"],
        contract["resource_limits"]["max_receipt_bytes"],
    )
    if (
        contract_stdout.get("status")
        != "VERIFIED_D18C_CONTRACT_FROZEN_AFTER_ZERO_ACTION_IMPLEMENTATION"
        or contract_stdout.get("verified") is not True
        or contract_stdout.get("chronology", {}).get("contract_freeze_commit")
        != result["contract_freeze_commit"]
        or contract_stdout.get("chronology", {}).get("result_absent") is not True
        or contract_stdout.get("execution_authorization")
        != contract["execution_authorization"]
        or contract_stdout.get("authority_ceiling") != contract["authority_ceiling"]
    ):
        raise VerificationError("captured contract checker evidence drift")
    try:
        spill_manifest = runner._load_spill_manifest(contract, scratch / "spill")
    except Exception as exc:
        raise VerificationError(f"external spill verification failed: {exc}") from exc
    spill_manifest_size, spill_manifest_digest = _sha_file(
        scratch / "spill" / "manifest.json",
        contract["resource_limits"]["max_manifest_bytes"],
    )
    if (
        spill_manifest_size != result["spill"]["manifest"]["bytes"]
        or spill_manifest_digest != result["spill"]["manifest"]["sha256"]
    ):
        raise VerificationError("external spill manifest receipt binding drift")
    for key in (
        "spill_records",
        "spill_bytes",
        "reduced_columns",
        "projected_zero_outputs",
        "zero_coefficients_dropped",
        "partition_count",
    ):
        if spill_manifest[key] != result["spill"][key]:
            raise VerificationError(
                f"external spill manifest/result count drift: {key}"
            )
    target = _verify_target(contract, scratch, result)
    target_manifest_size, target_manifest_digest = _sha_file(
        scratch / "bounded-q4-partial.manifest.json",
        contract["resource_limits"]["max_manifest_bytes"],
    )
    if (
        target_manifest_size != result["bounded_partial_target"]["manifest"]["bytes"]
        or target_manifest_digest
        != result["bounded_partial_target"]["manifest"]["sha256"]
    ):
        raise VerificationError("external target manifest receipt binding drift")
    allowed = {
        "exclusive.lock",
        "bounded-q4-partial.bin",
        "bounded-q4-partial.manifest.json",
        "terminal-receipt.json",
        "runner-stdout.json",
        "contract-checker-stdout.json",
        "launcher-receipt.json",
        "spill/manifest.json",
    } | {f"spill/p{index:03d}.bin" for index in range(PARTITIONS)}
    observed: set[str] = set()
    for path in scratch.rglob("*"):
        if path.is_symlink():
            raise VerificationError("symlink in external scratch")
        if path.is_file():
            metadata = path.lstat()
            if (
                metadata.st_nlink != 1
                or metadata.st_uid != custody["scratch_root_owner_uid"]
                or not stat.S_ISREG(metadata.st_mode)
            ):
                raise VerificationError("external file owner/link/type drift")
            observed.add(str(path.relative_to(scratch)))
        elif path.is_dir():
            metadata = path.lstat()
            if (
                metadata.st_uid != custody["scratch_root_owner_uid"]
                or not stat.S_ISDIR(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) & 0o022
            ):
                raise VerificationError("external directory owner/mode/type drift")
        else:
            raise VerificationError("unsupported external scratch object")
    if observed != allowed:
        raise VerificationError("external scratch exact file set drift")
    if len(observed) != contract["resource_limits"]["maximum_final_external_regular_files"]:
        raise VerificationError("external scratch regular-file cap drift")
    return {
        "status": "VERIFIED_D18C_RESULT_AND_EXTERNAL_TERMINAL_EVIDENCE",
        "verified": True,
        "external_scratch_verified": True,
        "terminal_receipt_sha256": digest,
        "spill_manifest": {
            "spill_records": spill_manifest["spill_records"],
            "spill_bytes": spill_manifest["spill_bytes"],
            "partition_count": spill_manifest["partition_count"],
        },
        "bounded_target": target,
        "authority": result["authority"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", required=True, choices=("implementation", "contract", "result")
    )
    parser.add_argument("--scratch", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.mode == "implementation":
            if args.scratch is not None:
                raise VerificationError("--scratch is invalid for implementation mode")
            evidence = verify_implementation_source()
        elif args.mode == "contract":
            if args.scratch is not None:
                raise VerificationError("--scratch is invalid for contract mode")
            evidence = verify_contract()
        else:
            evidence = verify_result(args.scratch)
    except VerificationError as exc:
        print(
            json.dumps(
                {
                    "status": "D18C_VERIFICATION_FAILED",
                    "verified": False,
                    "error": str(exc),
                },
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "D18C_VERIFICATION_FAILED",
                    "verified": False,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(evidence, allow_nan=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
