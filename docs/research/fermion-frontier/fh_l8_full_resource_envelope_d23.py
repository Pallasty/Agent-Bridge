#!/usr/bin/env python3
"""D23 resource/file envelope preflight; no scientific input or action."""
from __future__ import annotations

import json
import os
from pathlib import Path

SHARDS = 53
PARTITIONS = 256
SPILL_FILES = SHARDS * PARTITIONS
MANIFESTS = SHARDS
TARGETS = 1
BLOCK_RESERVE = 4096
MANIFEST_MAX_BYTES = 65536

# Exact D21 planning values: a non-authoritative D18-C linear extrapolation
# with the frozen 5/4 margin.  They are a capacity guardrail, not a proof.
MARGIN_SPILL_BYTES = 1_807_982_694
MARGIN_TARGET_BYTES = 883_782_320


class PreflightError(ValueError):
    pass


def envelope() -> dict:
    spill_inode_reserve = SPILL_FILES * BLOCK_RESERVE
    manifest_reserve = MANIFESTS * MANIFEST_MAX_BYTES
    scratch_bytes = MARGIN_SPILL_BYTES + MARGIN_TARGET_BYTES + spill_inode_reserve + manifest_reserve
    return {
        "shards": SHARDS,
        "partitions": PARTITIONS,
        "max_spill_files": SPILL_FILES,
        "max_manifest_files": MANIFESTS,
        "max_target_files": TARGETS,
        "max_files": SPILL_FILES + MANIFESTS + TARGETS,
        "margin_spill_bytes": MARGIN_SPILL_BYTES,
        "margin_target_bytes": MARGIN_TARGET_BYTES,
        "spill_inode_reserve_bytes": spill_inode_reserve,
        "manifest_reserve_bytes": manifest_reserve,
        "required_free_scratch_bytes": scratch_bytes,
        "role": "NON_AUTHORITATIVE_CAPACITY_GUARDRAIL_ONLY",
    }


def host_snapshot(scratch: Path) -> dict:
    stat = os.statvfs(scratch)
    memory_max = Path("/sys/fs/cgroup/memory.max")
    memory_current = Path("/sys/fs/cgroup/memory.current")
    # Missing or unlimited cgroup values are intentionally not converted into
    # a capacity claim.  A full run needs an explicit bounded envelope.
    cgroup_values = {}
    for key, path in (("memory_max", memory_max), ("memory_current", memory_current)):
        try:
            raw = path.read_text(encoding="ascii").strip()
            cgroup_values[key] = int(raw) if raw.isdecimal() else None
        except OSError:
            cgroup_values[key] = None
    return {
        "scratch": str(scratch.resolve()),
        "free_bytes": stat.f_bavail * stat.f_frsize,
        "free_inodes": stat.f_favail,
        "memory_max_bytes": cgroup_values["memory_max"],
        "memory_current_bytes": cgroup_values["memory_current"],
        "runtime_upper_bound_ns": None,
    }


def decide(snapshot: dict, model: dict | None = None) -> dict:
    model = envelope() if model is None else model
    expected = {"scratch", "free_bytes", "free_inodes", "memory_max_bytes", "memory_current_bytes", "runtime_upper_bound_ns"}
    if set(snapshot) != expected or type(snapshot["free_bytes"]) is not int or type(snapshot["free_inodes"]) is not int:
        raise PreflightError("host snapshot schema drift")
    disk_ok = snapshot["free_bytes"] >= model["required_free_scratch_bytes"]
    inode_ok = snapshot["free_inodes"] >= model["max_files"]
    # D23 does not invent memory or runtime requirements.  Without separately
    # frozen bounds, both predicates must remain false.
    memory_bound_present = type(snapshot["memory_max_bytes"]) is int and type(snapshot["memory_current_bytes"]) is int
    runtime_bound_present = type(snapshot["runtime_upper_bound_ns"]) is int and snapshot["runtime_upper_bound_ns"] > 0
    authorized = disk_ok and inode_ok and memory_bound_present and runtime_bound_present
    return {
        "status": "NO_GO_D23_FULL_53_RESOURCE_ENVELOPE_INCOMPLETE" if not authorized else "UNREACHABLE_D23_AUTHORIZATION_ERROR",
        "disk_capacity_guardrail_satisfied": disk_ok,
        "file_count_guardrail_satisfied": inode_ok,
        "memory_bound_present": memory_bound_present,
        "runtime_bound_present": runtime_bound_present,
        "full_53_scientific_execution_authorized": False,
        "scientific_action_calls": 0,
        "next_gate": "FULL_53_EXPLICIT_MEMORY_RUNTIME_AND_EXTERNAL_RESOURCE_RESERVATION",
    }


def main() -> int:
    model = envelope()
    snapshot = host_snapshot(Path("/tmp"))
    print(json.dumps({"model": model, "host": snapshot, "decision": decide(snapshot, model)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
