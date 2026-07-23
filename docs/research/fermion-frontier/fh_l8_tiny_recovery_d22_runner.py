#!/usr/bin/env python3
"""Executable D22 shard/recovery protocol on a synthetic tiny fixture only."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import stat
import struct
import tempfile
import uuid
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
CONTRACT_NAME = "fh_l8_tiny_recovery_d22_contract.json"
SPILL = struct.Struct(">Qq")
ZERO_SHA256 = "0" * 64


class RunnerError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> None:
    raise RunnerError(code, message)


def _reject_float(token: str) -> Any:
    _fail("JSON_FLOAT", f"floating-point JSON forbidden: {token}")


def _reject_constant(token: str) -> Any:
    _fail("JSON_NONFINITE", f"non-finite JSON forbidden: {token}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            _fail("JSON_DUPLICATE", f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")


def _load_json(path: Path, maximum: int = 262_144) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        _fail("READ", f"cannot read {path}: {exc}")
    if not raw or len(raw) > maximum:
        _fail("JSON_SIZE", f"JSON size outside bound: {path}")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_pairs,
        )
    except RunnerError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        _fail("JSON_PARSE", f"invalid JSON {path}: {exc}")
    if not isinstance(value, dict):
        _fail("JSON_TYPE", f"top-level object required: {path}")
    return value


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha_file(path: Path, maximum: int = 16_777_216) -> tuple[int, str]:
    total = 0
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                block = handle.read(1 << 20)
                if not block:
                    break
                total += len(block)
                if total > maximum:
                    _fail("FILE_SIZE", f"file exceeds bound: {path}")
                digest.update(block)
    except RunnerError:
        raise
    except OSError as exc:
        _fail("READ", f"cannot hash {path}: {exc}")
    return total, digest.hexdigest()


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _publish_noreplace(path: Path, payload: bytes, mode: int = 0o644) -> dict[str, Any]:
    if path.exists() or path.is_symlink():
        _fail("NO_REPLACE", f"publication target already exists: {path}")
    temp = path.parent / f".{path.name}.stage-{uuid.uuid4().hex}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = -1
    try:
        fd = os.open(temp, flags, mode)
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                _fail("WRITE", f"short write: {temp}")
            view = view[written:]
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.link(temp, path)
        os.unlink(temp)
        _fsync_dir(path.parent)
    except RunnerError:
        if fd >= 0:
            os.close(fd)
        try:
            temp.unlink()
        except OSError:
            pass
        raise
    except OSError as exc:
        if fd >= 0:
            os.close(fd)
        try:
            temp.unlink()
        except OSError:
            pass
        _fail("PUBLICATION", f"cannot publish {path}: {exc}")
    return {"path": path.name, "bytes": len(payload), "sha256": _sha(payload)}


def _validate_contract(contract: dict[str, Any]) -> None:
    if set(contract) != {
        "schema_version",
        "contract_id",
        "analysis_class",
        "implementation",
        "fixture",
        "protocol",
        "production_authority",
        "expected",
        "limitations",
    }:
        _fail("CONTRACT_SCHEMA", "contract key drift")
    if contract["schema_version"] != 1:
        _fail("CONTRACT_SCHEMA", "schema version drift")
    if contract["contract_id"] != "FH-L8-INDEPENDENT-REFERENCE-D22-TINY-RECOVERY-V1":
        _fail("CONTRACT_ID", "contract id drift")
    if contract["analysis_class"] != "SYNTHETIC_TINY_FIXTURE_RECOVERY_NO_PRODUCTION_SCIENTIFIC_ACTION":
        _fail("CONTRACT_CLASS", "analysis class drift")
    fixture = contract["fixture"]
    if fixture != {
        "fixture_id": "D22-SYNTHETIC-U64-I64-V1",
        "source_values": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        "shard_size": 4,
        "shard_count": 3,
        "last_shard_records": 3,
        "partition_count": 4,
        "spill_record_bytes": 16,
    }:
        _fail("FIXTURE_SCHEMA", "fixture drift")
    protocol = contract["protocol"]
    required_true = {
        "fresh_exclusive_scratch",
        "exclusive_nonblocking_lock",
        "per_shard_manifest",
        "per_shard_receipt_sha256_chain",
        "atomic_no_replace_files",
        "manifest_only_merge",
        "exact_frontier_resume",
        "gap_overlap_orphan_fail_closed",
        "partition_hash_revalidation",
        "partial_publication_fail_closed",
        "terminal_receipt_last",
    }
    if set(protocol) != required_true or any(protocol[key] is not True for key in required_true):
        _fail("PROTOCOL_SCHEMA", "protocol drift")
    authority = contract["production_authority"]
    if authority != {
        "production_mode_available": False,
        "production_checkpoint_reads_authorized": 0,
        "production_q3_rows_authorized": 0,
        "production_scientific_kernel_calls_authorized": 0,
        "full_53_shard_execution_authorized": False,
        "full_q4_target_materialized": False,
    }:
        _fail("PRODUCTION_AUTHORITY", "production authority drift")


def _tiny_kernel(source: int) -> list[tuple[int, int]]:
    return [
        (source % 7, source),
        ((source * 3) % 11, -source),
        ((source + 5) % 13, (source % 3) + 1),
    ]


def _partition(target: int, count: int) -> int:
    return hashlib.sha256(target.to_bytes(8, "big")).digest()[0] % count


def _source_bytes(values: list[int]) -> bytes:
    return b"".join(struct.pack(">q", value) for value in values)


def _scratch_stat(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        _fail("SCRATCH", f"cannot stat scratch: {exc}")
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        _fail("SCRATCH", "scratch is not a real directory")
    if stat.S_IMODE(info.st_mode) != 0o700:
        _fail("SCRATCH_MODE", "scratch mode must be 0700")


def _acquire(root: Path, resume: bool) -> int:
    if resume:
        _scratch_stat(root)
    else:
        try:
            root.mkdir(mode=0o700)
        except OSError as exc:
            _fail("SCRATCH_CREATE", f"cannot create fresh scratch: {exc}")
        os.chmod(root, 0o700)
        _publish_noreplace(root / "exclusive.lock", b"D22\n", 0o600)
    lock = root / "exclusive.lock"
    fd = -1
    try:
        info = lock.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            _fail("LOCK_TYPE", "lock is not a regular file")
        if stat.S_IMODE(info.st_mode) != 0o600:
            _fail("LOCK_MODE", "lock mode must be 0600")
        fd = os.open(lock, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except RunnerError:
        raise
    except BlockingIOError:
        if fd >= 0:
            os.close(fd)
        _fail("LOCK_BUSY", "scratch lock is held")
    except OSError as exc:
        if fd >= 0:
            os.close(fd)
        _fail("LOCK", f"cannot acquire lock: {exc}")
    return fd


def _shard_name(index: int) -> str:
    return f"shard-{index:03d}"


def _partition_name(index: int) -> str:
    return f"p{index:03d}.bin"


def _write_shard(
    root: Path,
    contract: dict[str, Any],
    index: int,
    previous_receipt_sha256: str,
) -> dict[str, Any]:
    fixture = contract["fixture"]
    values = fixture["source_values"]
    start = index * fixture["shard_size"]
    end = min(start + fixture["shard_size"], len(values))
    selected = values[start:end]
    staging = root / f".{_shard_name(index)}.stage-{uuid.uuid4().hex}"
    final = root / _shard_name(index)
    if final.exists() or final.is_symlink():
        _fail("SHARD_EXISTS", f"shard already exists: {index}")
    staging.mkdir(mode=0o700)
    buffers: list[list[tuple[int, int]]] = [
        [] for _ in range(fixture["partition_count"])
    ]
    for source in selected:
        for target, delta in _tiny_kernel(source):
            buffers[_partition(target, fixture["partition_count"])].append(
                (target, delta)
            )
    partitions: list[dict[str, Any]] = []
    try:
        for partition, records in enumerate(buffers):
            records.sort()
            payload = b"".join(SPILL.pack(target, delta) for target, delta in records)
            record = _publish_noreplace(
                staging / _partition_name(partition), payload
            )
            record.update({"partition": partition, "records": len(records)})
            partitions.append(record)
        manifest = {
            "schema_version": 1,
            "fixture_id": fixture["fixture_id"],
            "shard_index": index,
            "source_start": start,
            "source_end_exclusive": end,
            "source_records": len(selected),
            "source_sha256": _sha(_source_bytes(selected)),
            "previous_receipt_sha256": previous_receipt_sha256,
            "partition_count": fixture["partition_count"],
            "spill_record_bytes": SPILL.size,
            "partitions": partitions,
        }
        manifest_identity = _publish_noreplace(
            staging / "manifest.json", _canonical(manifest)
        )
        receipt = {
            "schema_version": 1,
            "fixture_id": fixture["fixture_id"],
            "shard_index": index,
            "previous_receipt_sha256": previous_receipt_sha256,
            "manifest": manifest_identity,
            "status": "D22_TINY_SHARD_COMMITTED",
        }
        receipt_identity = _publish_noreplace(
            staging / "receipt.json", _canonical(receipt)
        )
        final.mkdir(mode=0o700)
        publish_order = [
            *[
                _partition_name(partition)
                for partition in range(fixture["partition_count"])
            ],
            "manifest.json",
            "receipt.json",
        ]
        for name in publish_order:
            os.link(staging / name, final / name)
        _fsync_dir(final)
        for name in publish_order:
            (staging / name).unlink()
        staging.rmdir()
        _fsync_dir(root)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "index": index,
        "receipt_sha256": receipt_identity["sha256"],
        "source_records": len(selected),
        "spill_records": sum(len(records) for records in buffers),
    }


def _validate_shard(
    root: Path,
    contract: dict[str, Any],
    index: int,
    previous_receipt_sha256: str,
) -> dict[str, Any]:
    fixture = contract["fixture"]
    directory = root / _shard_name(index)
    try:
        info = directory.lstat()
    except OSError as exc:
        _fail("FRONTIER_GAP", f"missing shard {index}: {exc}")
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        _fail("SHARD_TYPE", f"invalid shard directory: {index}")
    expected_files = {
        "manifest.json",
        "receipt.json",
        *{
            _partition_name(partition)
            for partition in range(fixture["partition_count"])
        },
    }
    try:
        names = {entry.name for entry in directory.iterdir()}
    except OSError as exc:
        _fail("SHARD_ENUM", f"cannot enumerate shard {index}: {exc}")
    if names != expected_files:
        _fail("SHARD_ORPHAN", f"shard {index} file-set drift")
    manifest_path = directory / "manifest.json"
    receipt_path = directory / "receipt.json"
    manifest = _load_json(manifest_path)
    receipt = _load_json(receipt_path)
    start = index * fixture["shard_size"]
    end = min(start + fixture["shard_size"], len(fixture["source_values"]))
    selected = fixture["source_values"][start:end]
    expected_manifest_scalars = {
        "schema_version": 1,
        "fixture_id": fixture["fixture_id"],
        "shard_index": index,
        "source_start": start,
        "source_end_exclusive": end,
        "source_records": len(selected),
        "source_sha256": _sha(_source_bytes(selected)),
        "previous_receipt_sha256": previous_receipt_sha256,
        "partition_count": fixture["partition_count"],
        "spill_record_bytes": SPILL.size,
    }
    if {key: manifest.get(key) for key in expected_manifest_scalars} != expected_manifest_scalars:
        _fail("MANIFEST_DRIFT", f"shard {index} manifest scalar drift")
    if set(manifest) != {*expected_manifest_scalars, "partitions"}:
        _fail("MANIFEST_SCHEMA", f"shard {index} manifest key drift")
    partitions = manifest["partitions"]
    if not isinstance(partitions, list) or len(partitions) != fixture["partition_count"]:
        _fail("MANIFEST_SCHEMA", f"shard {index} partition list drift")
    spill_records = 0
    for partition, record in enumerate(partitions):
        if set(record) != {"path", "bytes", "sha256", "partition", "records"}:
            _fail("PARTITION_SCHEMA", f"shard {index} partition schema drift")
        if record["path"] != _partition_name(partition) or record["partition"] != partition:
            _fail("PARTITION_ORDER", f"shard {index} partition order drift")
        path = directory / record["path"]
        try:
            pinfo = path.lstat()
        except OSError as exc:
            _fail("PARTITION_READ", f"missing partition: {exc}")
        if not stat.S_ISREG(pinfo.st_mode) or stat.S_ISLNK(pinfo.st_mode):
            _fail("PARTITION_TYPE", "partition is not regular")
        size, digest = _sha_file(path)
        if size != record["bytes"] or digest != record["sha256"]:
            _fail("PARTITION_HASH", f"shard {index} partition identity drift")
        if size != record["records"] * SPILL.size:
            _fail("PARTITION_SIZE", f"shard {index} partition record drift")
        prior: tuple[int, int] | None = None
        raw = path.read_bytes()
        for offset in range(0, len(raw), SPILL.size):
            item = SPILL.unpack(raw[offset : offset + SPILL.size])
            if prior is not None and item < prior:
                _fail("PARTITION_SORT", "partition not sorted")
            if _partition(item[0], fixture["partition_count"]) != partition:
                _fail("PARTITION_SELECTOR", "partition selector drift")
            prior = item
        spill_records += record["records"]
    manifest_size, manifest_sha = _sha_file(manifest_path)
    expected_receipt = {
        "schema_version": 1,
        "fixture_id": fixture["fixture_id"],
        "shard_index": index,
        "previous_receipt_sha256": previous_receipt_sha256,
        "manifest": {
            "path": "manifest.json",
            "bytes": manifest_size,
            "sha256": manifest_sha,
        },
        "status": "D22_TINY_SHARD_COMMITTED",
    }
    if receipt != expected_receipt:
        _fail("RECEIPT_DRIFT", f"shard {index} receipt drift")
    _, receipt_sha = _sha_file(receipt_path)
    return {
        "index": index,
        "receipt_sha256": receipt_sha,
        "source_records": len(selected),
        "spill_records": spill_records,
    }


def _admit_frontier(root: Path, contract: dict[str, Any]) -> list[dict[str, Any]]:
    fixture = contract["fixture"]
    try:
        names = {entry.name for entry in root.iterdir()}
    except OSError as exc:
        _fail("SCRATCH_ENUM", f"cannot enumerate scratch: {exc}")
    if any(name.startswith(".") for name in names):
        _fail("ORPHAN", "staging/orphan path present")
    terminal_set = {"target.bin", "target.manifest.json", "terminal-receipt.json"}
    present_terminal = names & terminal_set
    if present_terminal and present_terminal != terminal_set:
        _fail("PARTIAL_PUBLICATION", "partial final publication present")
    shard_names = sorted(name for name in names if name.startswith("shard-"))
    other = names - {"exclusive.lock"} - set(shard_names) - terminal_set
    if other:
        _fail("ORPHAN", f"unexpected scratch entries: {sorted(other)}")
    expected_names = [_shard_name(index) for index in range(len(shard_names))]
    if shard_names != expected_names:
        _fail("FRONTIER_GAP", "shard frontier is not exact contiguous prefix")
    if len(shard_names) > fixture["shard_count"]:
        _fail("FRONTIER_OVERLAP", "too many shards")
    previous = ZERO_SHA256
    records: list[dict[str, Any]] = []
    for index in range(len(shard_names)):
        record = _validate_shard(root, contract, index, previous)
        previous = record["receipt_sha256"]
        records.append(record)
    if present_terminal:
        if len(records) != fixture["shard_count"]:
            _fail("PARTIAL_PUBLICATION", "terminal files before full frontier")
        _validate_terminal(root, contract, records)
    return records


def _merge(root: Path, contract: dict[str, Any], shards: list[dict[str, Any]]) -> dict[str, Any]:
    fixture = contract["fixture"]
    totals: dict[int, int] = {}
    for partition in range(fixture["partition_count"]):
        for shard in shards:
            manifest = _load_json(
                root / _shard_name(shard["index"]) / "manifest.json"
            )
            record = manifest["partitions"][partition]
            path = root / _shard_name(shard["index"]) / record["path"]
            raw = path.read_bytes()
            for offset in range(0, len(raw), SPILL.size):
                target, delta = SPILL.unpack(raw[offset : offset + SPILL.size])
                totals[target] = totals.get(target, 0) + delta
    items = sorted((target, delta) for target, delta in totals.items() if delta)
    if any(delta < -(1 << 63) or delta >= (1 << 63) for _, delta in items):
        _fail("ARITHMETIC", "tiny merge escaped signed i64")
    payload = b"".join(SPILL.pack(target, delta) for target, delta in items)
    target_identity = _publish_noreplace(root / "target.bin", payload)
    tail = shards[-1]["receipt_sha256"] if shards else ZERO_SHA256
    manifest = {
        "schema_version": 1,
        "fixture_id": fixture["fixture_id"],
        "ordering": "target_u64_ascending",
        "target_records": len(items),
        "target": target_identity,
        "shard_count": len(shards),
        "receipt_chain_tail_sha256": tail,
    }
    manifest_identity = _publish_noreplace(
        root / "target.manifest.json", _canonical(manifest)
    )
    receipt_set_digest = hashlib.sha256()
    for shard in shards:
        receipt_set_digest.update(bytes.fromhex(shard["receipt_sha256"]))
    terminal = {
        "schema_version": 1,
        "fixture_id": fixture["fixture_id"],
        "status": "VERIFIED_D22_TINY_FIXTURE_COMPLETE",
        "source_records": len(fixture["source_values"]),
        "shard_count": len(shards),
        "spill_records": sum(shard["spill_records"] for shard in shards),
        "receipt_chain_tail_sha256": tail,
        "receipt_set_sha256": receipt_set_digest.hexdigest(),
        "target_manifest": manifest_identity,
        "target": target_identity,
        "production_checkpoint_reads": 0,
        "production_q3_rows_acted": 0,
        "production_scientific_kernel_calls": 0,
        "full_53_shard_execution_authorized": False,
    }
    terminal_identity = _publish_noreplace(
        root / "terminal-receipt.json", _canonical(terminal)
    )
    terminal["terminal_receipt_sha256"] = terminal_identity["sha256"]
    return terminal


def _expected_target(contract: dict[str, Any]) -> bytes:
    totals: dict[int, int] = {}
    for source in contract["fixture"]["source_values"]:
        for target, delta in _tiny_kernel(source):
            totals[target] = totals.get(target, 0) + delta
    return b"".join(
        SPILL.pack(target, delta)
        for target, delta in sorted(totals.items())
        if delta
    )


def _validate_terminal(
    root: Path, contract: dict[str, Any], shards: list[dict[str, Any]]
) -> dict[str, Any]:
    terminal = _load_json(root / "terminal-receipt.json")
    target_manifest = _load_json(root / "target.manifest.json")
    target_size, target_sha = _sha_file(root / "target.bin")
    expected = _expected_target(contract)
    if target_size != len(expected) or target_sha != _sha(expected):
        _fail("TARGET_DRIFT", "target differs from independent fixture oracle")
    manifest_size, manifest_sha = _sha_file(root / "target.manifest.json")
    tail = shards[-1]["receipt_sha256"]
    receipt_set = hashlib.sha256()
    for shard in shards:
        receipt_set.update(bytes.fromhex(shard["receipt_sha256"]))
    expected_terminal = {
        "schema_version": 1,
        "fixture_id": contract["fixture"]["fixture_id"],
        "status": "VERIFIED_D22_TINY_FIXTURE_COMPLETE",
        "source_records": len(contract["fixture"]["source_values"]),
        "shard_count": len(shards),
        "spill_records": sum(shard["spill_records"] for shard in shards),
        "receipt_chain_tail_sha256": tail,
        "receipt_set_sha256": receipt_set.hexdigest(),
        "target_manifest": {
            "path": "target.manifest.json",
            "bytes": manifest_size,
            "sha256": manifest_sha,
        },
        "target": {"path": "target.bin", "bytes": target_size, "sha256": target_sha},
        "production_checkpoint_reads": 0,
        "production_q3_rows_acted": 0,
        "production_scientific_kernel_calls": 0,
        "full_53_shard_execution_authorized": False,
    }
    if terminal != expected_terminal:
        _fail("TERMINAL_DRIFT", "terminal receipt drift")
    if target_manifest["target"] != expected_terminal["target"]:
        _fail("TARGET_MANIFEST_DRIFT", "target manifest identity drift")
    _, terminal_sha = _sha_file(root / "terminal-receipt.json")
    terminal = dict(terminal)
    terminal["terminal_receipt_sha256"] = terminal_sha
    return terminal


def run_tiny(
    contract: dict[str, Any],
    scratch: Path,
    *,
    resume: bool = False,
    stop_after_shards: int | None = None,
) -> dict[str, Any]:
    _validate_contract(contract)
    fd = _acquire(scratch, resume)
    try:
        existing = _admit_frontier(scratch, contract)
        terminal = scratch / "terminal-receipt.json"
        if terminal.exists():
            return _validate_terminal(scratch, contract, existing)
        previous = existing[-1]["receipt_sha256"] if existing else ZERO_SHA256
        shards = list(existing)
        for index in range(len(existing), contract["fixture"]["shard_count"]):
            record = _write_shard(scratch, contract, index, previous)
            previous = record["receipt_sha256"]
            shards.append(record)
            if (
                stop_after_shards is not None
                and len(shards) >= stop_after_shards
                and len(shards) < contract["fixture"]["shard_count"]
            ):
                return {
                    "status": "D22_TINY_FIXTURE_INTERRUPTED_AT_EXACT_FRONTIER",
                    "completed_shards": len(shards),
                    "receipt_chain_tail_sha256": previous,
                    "production_checkpoint_reads": 0,
                    "production_q3_rows_acted": 0,
                    "production_scientific_kernel_calls": 0,
                }
        return _merge(scratch, contract, shards)
    finally:
        os.close(fd)


def run_production(contract: dict[str, Any], _checkpoint: Path) -> None:
    _validate_contract(contract)
    _fail(
        "PRODUCTION_NOT_AUTHORIZED",
        "D22 production checkpoint reads and scientific action are forbidden",
    )


def _expect_failure(callable_obj: Any, expected_code: str) -> str:
    try:
        callable_obj()
    except RunnerError as exc:
        if exc.code != expected_code:
            _fail(
                "SELF_TEST_CLASSIFICATION",
                f"expected {expected_code}, observed {exc.code}",
            )
        return exc.code
    _fail("SELF_TEST_MISSED_FAILURE", f"expected failure {expected_code}")


def self_test(contract: dict[str, Any]) -> dict[str, Any]:
    _validate_contract(contract)
    outcomes: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="fh-l8-d22-") as temp:
        base = Path(temp)
        clean = base / "clean"
        clean_result = run_tiny(contract, clean)

        resumed = base / "resumed"
        interrupted = run_tiny(contract, resumed, stop_after_shards=1)
        resumed_result = run_tiny(contract, resumed, resume=True)
        if clean_result["target"] != resumed_result["target"]:
            _fail("SELF_TEST_EQUIVALENCE", "clean/resumed target mismatch")

        gap = base / "gap"
        run_tiny(contract, gap, stop_after_shards=1)
        (gap / "shard-000").rename(gap / "shard-001")
        outcomes["gap"] = _expect_failure(
            lambda: run_tiny(contract, gap, resume=True), "FRONTIER_GAP"
        )

        overlap = base / "overlap"
        run_tiny(contract, overlap, stop_after_shards=1)
        shutil.copytree(overlap / "shard-000", overlap / "shard-001")
        outcomes["overlap"] = _expect_failure(
            lambda: run_tiny(contract, overlap, resume=True), "MANIFEST_DRIFT"
        )

        orphan = base / "orphan"
        run_tiny(contract, orphan, stop_after_shards=1)
        (orphan / "orphan.bin").write_bytes(b"x")
        outcomes["orphan"] = _expect_failure(
            lambda: run_tiny(contract, orphan, resume=True), "ORPHAN"
        )

        drift = base / "drift"
        run_tiny(contract, drift, stop_after_shards=1)
        partition = next(
            path
            for path in sorted((drift / "shard-000").glob("p*.bin"))
            if path.stat().st_size
        )
        raw = bytearray(partition.read_bytes())
        raw[0] ^= 1
        partition.write_bytes(raw)
        outcomes["hash_drift"] = _expect_failure(
            lambda: run_tiny(contract, drift, resume=True), "PARTITION_HASH"
        )

        busy = base / "busy"
        run_tiny(contract, busy, stop_after_shards=1)
        held = os.open(busy / "exclusive.lock", os.O_RDWR)
        try:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            outcomes["stale_lock"] = _expect_failure(
                lambda: run_tiny(contract, busy, resume=True), "LOCK_BUSY"
            )
        finally:
            os.close(held)

        partial = base / "partial"
        run_tiny(contract, partial)
        (partial / "terminal-receipt.json").unlink()
        outcomes["partial_publication"] = _expect_failure(
            lambda: run_tiny(contract, partial, resume=True),
            "PARTIAL_PUBLICATION",
        )

        outcomes["production_rejection"] = _expect_failure(
            lambda: run_production(contract, base / "forbidden-checkpoint.bin"),
            "PRODUCTION_NOT_AUTHORIZED",
        )

    return {
        "schema_version": 1,
        "contract_id": contract["contract_id"],
        "status": "VERIFIED_D22_TINY_FIXTURE_SUCCESS_RESUME_AND_FAULT_MATRIX",
        "verified": True,
        "fixture": {
            "source_records": len(contract["fixture"]["source_values"]),
            "shards": contract["fixture"]["shard_count"],
            "partitions": contract["fixture"]["partition_count"],
            "clean_target": clean_result["target"],
            "resumed_target": resumed_result["target"],
            "clean_terminal_receipt_sha256": clean_result[
                "terminal_receipt_sha256"
            ],
            "resumed_terminal_receipt_sha256": resumed_result[
                "terminal_receipt_sha256"
            ],
            "interrupted_completed_shards": interrupted["completed_shards"],
        },
        "fault_matrix": outcomes,
        "production_authority": {
            "production_checkpoint_reads": 0,
            "production_q3_rows_acted": 0,
            "production_scientific_kernel_calls": 0,
            "full_53_shard_execution_authorized": False,
            "full_q4_target_materialized": False,
        },
        "next_gate": "FULL_53_SHARD_SCIENTIFIC_KERNEL_BINDING_AND_WORST_CASE_RESOURCE_PROOF",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after-shards", type=int)
    parser.add_argument("--attempt-production", action="store_true")
    args = parser.parse_args()
    try:
        contract = _load_json(HERE / CONTRACT_NAME)
        if args.attempt_production:
            run_production(contract, HERE / "fh_l8_packed_q3_checkpoint_d11_bundle/checkpoint.bin")
            _fail("PRODUCTION_GUARD", "production rejection did not fire")
        if args.self_test:
            result = self_test(contract)
        elif args.scratch is not None:
            result = run_tiny(
                contract,
                args.scratch,
                resume=args.resume,
                stop_after_shards=args.stop_after_shards,
            )
        else:
            _fail("CLI", "--self-test or --scratch required")
    except RunnerError as exc:
        print(
            json.dumps(
                {
                    "status": "D22_RUNNER_REJECTED",
                    "verified": False,
                    "error_code": exc.code,
                    "error": str(exc),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
