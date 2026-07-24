#!/usr/bin/env python3
"""D27 two-party micro-action authorization schema; it never calls D5."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
D5 = HERE / "fh_l8_symmetry_orbit_quotient_d5_checker.py"
D18C = HERE / "fh_l8_fresh_consumer_d18c_runner.py"
HEX = set("0123456789abcdef")


class AuthorizationError(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request() -> dict:
    return {
        "schema_version": 1,
        "request_id": "FH-L8-D27-MICRO-ACTION-REQUEST-V1",
        "requesting_authority": "agent-bridge-internal-research",
        "kernel": {"path": D5.name, "sha256": _sha(D5), "symbol": "_reduced_column"},
        "consumer_context": {"path": D18C.name, "sha256": _sha(D18C)},
        "action_limit": {"kernel_calls": 1, "packed_q3_reads": 0, "full_shard_runs": 0},
        "resource_ceiling": {"memory_max_bytes": 536_870_912, "swap_max_bytes": 0, "wall_seconds": 180},
        "representative_rule": "externally_authorized_nonmaterialized_single_representative",
    }


def validate_approval(req: dict, approval: dict) -> dict:
    required = {"schema_version", "request_id", "approving_authority", "approval_certificate_sha256", "approved_kernel_sha256", "approved_action_limit", "approved_resource_ceiling"}
    if set(approval) != required or approval.get("schema_version") != 1:
        raise AuthorizationError("approval schema drift")
    if approval["request_id"] != req["request_id"]:
        raise AuthorizationError("approval request binding drift")
    if approval["approving_authority"] == req["requesting_authority"] or not isinstance(approval["approving_authority"], str):
        raise AuthorizationError("independent approving authority required")
    digest = approval["approval_certificate_sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in HEX for ch in digest):
        raise AuthorizationError("approval certificate fingerprint drift")
    if approval["approved_kernel_sha256"] != req["kernel"]["sha256"]:
        raise AuthorizationError("kernel source binding drift")
    if approval["approved_action_limit"] != req["action_limit"] or approval["approved_resource_ceiling"] != req["resource_ceiling"]:
        raise AuthorizationError("approval scope escalation or drift")
    return {"approval_admissible": True, "scientific_action_calls": 0, "full_53_scientific_execution_authorized": False}


def absent_approval_decision() -> dict:
    return {
        "status": "NO_GO_D27_INDEPENDENT_MICRO_ACTION_APPROVAL_ABSENT",
        "request_sha256": hashlib.sha256(json.dumps(request(), sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "independent_approval_present": False,
        "d5_kernel_invoked": False,
        "real_packed_q3_reads": 0,
        "scientific_action_calls": 0,
        "full_53_scientific_execution_authorized": False,
        "next_gate": "INDEPENDENT_SINGLE_ACTION_APPROVAL_AND_ISOLATED_RESOURCE_RECEIPT",
    }
