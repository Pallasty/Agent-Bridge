#!/usr/bin/env python3
"""D22 synthetic-only, restart-safe 53-shard consumer state machine.

This is deliberately an execution *mechanism* validation, not a FH-L8 q3
consumer.  It accepts only a tiny in-memory fixture and rejects any attempt to
point it at the packed scientific input.  The output is a deterministic set of
per-shard manifests plus a no-replace merged target.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

SHARD_COUNT = 53
PARTITION_COUNT = 8                 # tiny-fixture stand-in; not the D20 256 plan
FIXTURE_KIND = "FH-L8-D22-SYNTHETIC-ONLY-V1"


class ConsumerError(ValueError):
    pass


class SimulatedInterruption(RuntimeError):
    pass


def _canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def tiny_fixture() -> dict:
    """Return 53 deterministic, non-scientific synthetic shard payloads."""
    shards = []
    for shard in range(SHARD_COUNT):
        rows = [
            {"synthetic_key": f"d22-{shard:02d}-a", "value": shard * 2},
            {"synthetic_key": f"d22-{shard:02d}-b", "value": shard * 2 + 1},
        ]
        shards.append(rows)
    fixture = {"kind": FIXTURE_KIND, "shards": shards}
    fixture["sha256"] = _sha_bytes(_canon({"kind": fixture["kind"], "shards": shards}))
    return fixture


def _validate_fixture(fixture: dict) -> None:
    if set(fixture) != {"kind", "shards", "sha256"} or fixture["kind"] != FIXTURE_KIND:
        raise ConsumerError("synthetic fixture identity drift")
    if not isinstance(fixture["shards"], list) or len(fixture["shards"]) != SHARD_COUNT:
        raise ConsumerError("D22 requires exactly 53 synthetic shards")
    actual = _sha_bytes(_canon({"kind": fixture["kind"], "shards": fixture["shards"]}))
    if actual != fixture["sha256"]:
        raise ConsumerError("synthetic fixture hash drift")
    for rows in fixture["shards"]:
        if not isinstance(rows, list) or not rows:
            raise ConsumerError("empty synthetic shard")
        for row in rows:
            if set(row) != {"synthetic_key", "value"} or not isinstance(row["synthetic_key"], str):
                raise ConsumerError("non-synthetic row rejected")


def _paths(scratch: Path) -> dict[str, Path]:
    return {"root": scratch, "manifests": scratch / "manifests", "spills": scratch / "spills",
            "target": scratch / "published-target.json"}


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ConsumerError(f"no-replace publication refused: {path.name}") from exc
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _partition(row: dict) -> int:
    return hashlib.sha256(row["synthetic_key"].encode()).digest()[0] % PARTITION_COUNT


def _manifest_path(paths: dict[str, Path], shard: int) -> Path:
    return paths["manifests"] / f"shard-{shard:02d}.json"


def _load_manifest(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConsumerError(f"invalid manifest: {path.name}") from exc
    if raw.get("manifest_sha256") != _sha_bytes(_canon({k: v for k, v in raw.items() if k != "manifest_sha256"})):
        raise ConsumerError(f"manifest hash drift: {path.name}")
    return raw


def _completed(paths: dict[str, Path], fixture_sha: str) -> list[dict]:
    manifests = []
    for shard in range(SHARD_COUNT):
        path = _manifest_path(paths, shard)
        if not path.exists():
            break
        manifest = _load_manifest(path)
        if manifest.get("shard") != shard or manifest.get("fixture_sha256") != fixture_sha:
            raise ConsumerError("resume frontier identity drift")
        for item in manifest.get("spills", []):
            spill = paths["spills"] / item["name"]
            if not spill.is_file() or _sha_file(spill) != item["sha256"]:
                raise ConsumerError("resume spill hash drift")
        manifests.append(manifest)
    # A gap is unsafe even if later manifests look sound.
    later = [p for p in paths["manifests"].glob("shard-*.json") if int(p.stem.split("-")[1]) >= len(manifests)]
    if later:
        raise ConsumerError("resume frontier gap or overlap")
    expected = {item["name"] for manifest in manifests for item in manifest["spills"]}
    actual = {p.name for p in paths["spills"].glob("*.jsonl")}
    if actual != expected:
        raise ConsumerError("orphan or missing spill bytes")
    return manifests


def _emit_shard(paths: dict[str, Path], fixture_sha: str, shard: int, rows: list[dict]) -> dict:
    buckets: dict[int, list[dict]] = {}
    for row in rows:
        buckets.setdefault(_partition(row), []).append(row)
    spills = []
    for partition, payload in sorted(buckets.items()):
        name = f"shard-{shard:02d}-partition-{partition:02d}.jsonl"
        data = b"".join(_canon(row) + b"\n" for row in payload)
        _write_exclusive(paths["spills"] / name, data)
        spills.append({"name": name, "partition": partition, "sha256": _sha_bytes(data), "rows": len(payload)})
    manifest = {"kind": FIXTURE_KIND, "fixture_sha256": fixture_sha, "shard": shard, "spills": spills}
    manifest["manifest_sha256"] = _sha_bytes(_canon(manifest))
    _write_exclusive(_manifest_path(paths, shard), _canon(manifest) + b"\n")
    return manifest


def _publish(paths: dict[str, Path], manifests: list[dict], fixture_sha: str) -> dict:
    if len(manifests) != SHARD_COUNT:
        raise ConsumerError("merge requires exact 53-shard frontier")
    rows = []
    for partition in range(PARTITION_COUNT):
        for manifest in manifests:
            for item in manifest["spills"]:
                if item["partition"] == partition:
                    rows.extend(json.loads(line) for line in (paths["spills"] / item["name"]).read_text().splitlines())
    target = {"kind": FIXTURE_KIND, "fixture_sha256": fixture_sha, "shards": SHARD_COUNT,
              "partitions": PARTITION_COUNT, "rows": rows}
    target["sha256"] = _sha_bytes(_canon(target))
    _write_exclusive(paths["target"], _canon(target) + b"\n")
    return target


def run_fixture(scratch: Path, fixture: dict, interrupt_after: int | None = None) -> dict:
    """Process/resume a synthetic fixture.  Existing target is never replaced."""
    _validate_fixture(fixture)
    paths = _paths(Path(scratch))
    paths["manifests"].mkdir(parents=True, exist_ok=True)
    paths["spills"].mkdir(parents=True, exist_ok=True)
    manifests = _completed(paths, fixture["sha256"])
    if paths["target"].exists():
        raise ConsumerError("target already published; no replacement allowed")
    for shard in range(len(manifests), SHARD_COUNT):
        _emit_shard(paths, fixture["sha256"], shard, fixture["shards"][shard])
        manifests.append(_load_manifest(_manifest_path(paths, shard)))
        if interrupt_after is not None and len(manifests) == interrupt_after:
            raise SimulatedInterruption(f"synthetic interruption at frontier {interrupt_after}")
    target = _publish(paths, manifests, fixture["sha256"])
    return {"status": "VERIFIED_D22_SYNTHETIC_53_SHARD_STATE_MACHINE", "fixture_sha256": fixture["sha256"],
            "completed_shards": len(manifests), "rows": len(target["rows"]), "target_sha256": target["sha256"],
            "scientific_action_calls": 0, "full_53_execution_authorized": False}
