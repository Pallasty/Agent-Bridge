#!/usr/bin/env python3
"""Build and validate durable receipts for the isolated desktop acceptance.

The acceptance shell script remains the executor.  This module only turns its
bounded A-D observations into a portable receipt and rejects receipts that do
not prove the isolation, postcondition, provenance, and coverage invariants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.desktop_acceptance_receipt.v0"
HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
COMMIT_ID = re.compile(r"^[0-9a-f]{40,64}$")
PHYSICAL_OUTPUT = re.compile(r"^(?:DP|HDMI)-", re.IGNORECASE)

REQUIRED_CHECKS = {
    "binary_source_clean",
    "virtual_outputs_only",
    "snapshot_sees_target",
    "isolated_invoke_allowed",
    "isolated_invoke_rc_zero",
    "isolated_target_confirmed",
    "isolated_invoke_activated_once",
    "postcondition_verified",
    "postcondition_recover_proceed",
    "dry_run_allowed",
    "dry_run_no_extra_activation",
    "host_invoke_denied",
    "host_invoke_no_activation",
    "transaction_status_verified",
    "transaction_verdict_verified",
    "transaction_recover_proceed",
    "transaction_mode_isolated",
    "transaction_activated_once",
}

REQUIRED_SELECTED_CHANNELS = {
    "atspi_snapshot",
    "atspi_semantic_action",
    "atspi_postcondition",
    "sway_process_isolation",
}

REQUIRED_SKIPPED_CHANNELS = {
    "screenshot",
    "ocr",
    "coordinate_input",
    "host_mutation",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _value_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_payload(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "_parse_error": str(exc),
            "_raw_text": raw,
        }
    if not isinstance(value, dict):
        return {
            "_parse_error": "payload is not a JSON object",
            "_raw_value": value,
        }
    return value


def _nested(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _binary_commit(version: str) -> str | None:
    candidates = re.findall(r"\b[0-9a-f]{8,64}\b", version)
    return max(candidates, key=len) if candidates else None


def _check(check_id: str, passed: bool, evidence: Any) -> dict[str, Any]:
    return {"id": check_id, "passed": bool(passed), "evidence": evidence}


def build_receipt(
    *,
    source_commit: str,
    binary_path: Path,
    binary_version: str,
    backend: str,
    output_names: list[str],
    display: str,
    sway_pid: int,
    snapshot_target_present: bool,
    isolated_invoke: dict[str, Any],
    postcondition_verify: dict[str, Any],
    dry_run_invoke: dict[str, Any],
    host_invoke: dict[str, Any],
    semantic_task: dict[str, Any],
    activation_counts: dict[str, int],
    hostname: str | None = None,
    architecture: str | None = None,
) -> dict[str, Any]:
    """Return one self-contained acceptance receipt.

    A failed acceptance still produces a receipt.  ``status`` becomes
    ``failed`` and the validator reports the exact unmet invariant.
    """

    binary_path = binary_path.resolve(strict=True)
    binary_commit = _binary_commit(binary_version)
    binary_dirty = "-dirty" in binary_version
    output_names = [name.strip() for name in output_names if name.strip()]
    physical_outputs = [name for name in output_names if PHYSICAL_OUTPUT.match(name)]

    isolated_allowed = isolated_invoke.get("allowed") is True
    isolated_rc_zero = isolated_invoke.get("rc") == 0
    target_isolated = _nested(isolated_invoke, "found", "isolated") is True
    verify_verdict = postcondition_verify.get("verdict")
    verify_recover = postcondition_verify.get("recover")
    dry_run_allowed = dry_run_invoke.get("allowed") is True
    host_denied = host_invoke.get("allowed") is False
    transaction_status = semantic_task.get("status")
    transaction_verdict = semantic_task.get("verdict")
    transaction_recover = semantic_task.get("recover")
    transaction_mode = _nested(semantic_task, "safety", "mode")

    checks = [
        _check(
            "binary_source_clean",
            not binary_dirty,
            {"version": binary_version, "dirty": binary_dirty},
        ),
        _check(
            "virtual_outputs_only",
            bool(output_names) and not physical_outputs,
            {"outputs": output_names, "physical_outputs": physical_outputs},
        ),
        _check(
            "snapshot_sees_target",
            snapshot_target_present,
            {"target_present": snapshot_target_present},
        ),
        _check(
            "isolated_invoke_allowed",
            isolated_allowed,
            {"allowed": isolated_invoke.get("allowed")},
        ),
        _check(
            "isolated_invoke_rc_zero",
            isolated_rc_zero,
            {"rc": isolated_invoke.get("rc")},
        ),
        _check(
            "isolated_target_confirmed",
            target_isolated,
            {"isolated": _nested(isolated_invoke, "found", "isolated")},
        ),
        _check(
            "isolated_invoke_activated_once",
            activation_counts.get("isolated") == 1,
            {"activations": activation_counts.get("isolated")},
        ),
        _check(
            "postcondition_verified",
            verify_verdict == "verified",
            {"verdict": verify_verdict},
        ),
        _check(
            "postcondition_recover_proceed",
            verify_recover == "proceed",
            {"recover": verify_recover},
        ),
        _check(
            "dry_run_allowed",
            dry_run_allowed,
            {"allowed": dry_run_invoke.get("allowed")},
        ),
        _check(
            "dry_run_no_extra_activation",
            activation_counts.get("dry_run") == 1,
            {"activations": activation_counts.get("dry_run")},
        ),
        _check(
            "host_invoke_denied",
            host_denied,
            {"allowed": host_invoke.get("allowed")},
        ),
        _check(
            "host_invoke_no_activation",
            activation_counts.get("host_denied") == 1,
            {"activations": activation_counts.get("host_denied")},
        ),
        _check(
            "transaction_status_verified",
            transaction_status == "verified",
            {"status": transaction_status},
        ),
        _check(
            "transaction_verdict_verified",
            transaction_verdict == "verified",
            {"verdict": transaction_verdict},
        ),
        _check(
            "transaction_recover_proceed",
            transaction_recover == "proceed",
            {"recover": transaction_recover},
        ),
        _check(
            "transaction_mode_isolated",
            transaction_mode == "isolated",
            {"mode": transaction_mode},
        ),
        _check(
            "transaction_activated_once",
            activation_counts.get("transaction") == 2,
            {"activations": activation_counts.get("transaction")},
        ),
    ]
    passed = all(item["passed"] for item in checks)

    selected_channels = [
        {
            "id": "atspi_snapshot",
            "reason": "read-only semantic target observation before mutation",
        },
        {
            "id": "atspi_semantic_action",
            "reason": "invoke the named accessible action without coordinates",
        },
        {
            "id": "atspi_postcondition",
            "reason": "read-only re-observation of the required element postcondition",
        },
        {
            "id": "sway_process_isolation",
            "reason": "bind the target to a nested compositor PID subtree and audit outputs",
        },
    ]
    skipped_channels = [
        {
            "id": "screenshot",
            "reason": "the target and postcondition are available through AT-SPI",
        },
        {
            "id": "ocr",
            "reason": "the accessible name provides a stronger semantic selector",
        },
        {
            "id": "coordinate_input",
            "reason": "semantic Action.do_action is sufficient and avoids coordinate ambiguity",
        },
        {
            "id": "host_mutation",
            "reason": "the acceptance permits real mutation only inside the nested Sway process cage",
        },
    ]

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed",
        "source": {"commit": source_commit},
        "binary": {
            "path": str(binary_path),
            "sha256": _sha256_file(binary_path),
            "version": binary_version,
            "source_commit": binary_commit,
            "dirty": binary_dirty,
        },
        "environment": {
            "hostname": hostname or platform.node(),
            "architecture": architecture or platform.machine(),
            "compositor": "sway",
            "backend": backend,
            "display": display,
            "sway_pid": sway_pid,
            "outputs": output_names,
            "physical_outputs": physical_outputs,
        },
        "case": {
            "id": "linux_atspi_nested_sway_semantic_task",
            "selector": {
                "app": "toy_button",
                "role": "button",
                "name": "INVOKE_TARGET",
            },
            "postcondition": "element_appeared",
        },
        "channels": {
            "selected": selected_channels,
            "skipped": skipped_channels,
        },
        "phases": {
            "snapshot": {"target_present": snapshot_target_present},
            "isolated_invoke": {
                "payload": isolated_invoke,
                "activations": activation_counts.get("isolated"),
            },
            "postcondition_verify": {"payload": postcondition_verify},
            "dry_run": {
                "payload": dry_run_invoke,
                "activations": activation_counts.get("dry_run"),
            },
            "host_denial": {
                "payload": host_invoke,
                "activations": activation_counts.get("host_denied"),
            },
            "semantic_task": {
                "payload": semantic_task,
                "payload_sha256": _value_sha256(semantic_task),
                "activations": activation_counts.get("transaction"),
            },
        },
        "checks": checks,
    }


def validate_receipt(receipt: Any) -> list[str]:
    """Return deterministic validation errors; an empty list means PASS."""

    if not isinstance(receipt, dict):
        return ["receipt_not_object"]

    errors: list[str] = []

    def require(condition: bool, code: str) -> None:
        if not condition:
            errors.append(code)

    require(receipt.get("schema") == SCHEMA, "schema_invalid")
    require(receipt.get("status") == "passed", "status_not_passed")
    require(
        isinstance(_nested(receipt, "source", "commit"), str)
        and bool(COMMIT_ID.fullmatch(_nested(receipt, "source", "commit"))),
        "source_commit_invalid",
    )
    require(
        isinstance(_nested(receipt, "binary", "sha256"), str)
        and bool(HEX_DIGEST.fullmatch(_nested(receipt, "binary", "sha256"))),
        "binary_sha256_invalid",
    )
    binary_commit = _nested(receipt, "binary", "source_commit")
    source_commit = _nested(receipt, "source", "commit")
    require(
        isinstance(binary_commit, str)
        and 8 <= len(binary_commit) <= 64
        and bool(re.fullmatch(r"[0-9a-f]+", binary_commit)),
        "binary_source_commit_invalid",
    )
    require(
        isinstance(binary_commit, str)
        and isinstance(source_commit, str)
        and source_commit.startswith(binary_commit),
        "binary_source_commit_mismatch",
    )
    require(
        _nested(receipt, "binary", "dirty") is False,
        "binary_source_dirty",
    )
    require(
        _nested(receipt, "environment", "backend") in {"wayland", "headless"},
        "backend_invalid",
    )
    outputs = _nested(receipt, "environment", "outputs")
    require(isinstance(outputs, list) and bool(outputs), "outputs_missing")
    require(
        isinstance(outputs, list)
        and not any(isinstance(name, str) and PHYSICAL_OUTPUT.match(name) for name in outputs),
        "physical_output_present",
    )
    require(
        _nested(receipt, "environment", "physical_outputs") == [],
        "physical_output_audit_failed",
    )

    selected = _nested(receipt, "channels", "selected")
    selected_ids = {
        item.get("id")
        for item in selected or []
        if isinstance(item, dict) and item.get("reason")
    }
    require(
        REQUIRED_SELECTED_CHANNELS.issubset(selected_ids),
        "selected_channels_incomplete",
    )
    skipped = _nested(receipt, "channels", "skipped")
    skipped_ids = {
        item.get("id")
        for item in skipped or []
        if isinstance(item, dict) and item.get("reason")
    }
    require(
        REQUIRED_SKIPPED_CHANNELS.issubset(skipped_ids),
        "skipped_channels_incomplete",
    )

    checks = receipt.get("checks")
    checks_by_id = {
        item.get("id"): item
        for item in checks or []
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    require(REQUIRED_CHECKS.issubset(checks_by_id), "check_coverage_incomplete")
    require(
        REQUIRED_CHECKS.issubset(checks_by_id)
        and all(checks_by_id[check_id].get("passed") is True for check_id in REQUIRED_CHECKS),
        "required_check_failed",
    )

    require(
        _nested(receipt, "phases", "isolated_invoke", "payload", "allowed") is True,
        "isolated_invoke_not_allowed",
    )
    require(
        _nested(
            receipt,
            "phases",
            "isolated_invoke",
            "payload",
            "found",
            "isolated",
        )
        is True,
        "isolated_target_unproven",
    )
    require(
        _nested(receipt, "phases", "postcondition_verify", "payload", "verdict")
        == "verified",
        "postcondition_not_verified",
    )
    require(
        _nested(receipt, "phases", "host_denial", "payload", "allowed") is False,
        "host_denial_unproven",
    )
    semantic_task = _nested(receipt, "phases", "semantic_task", "payload")
    require(isinstance(semantic_task, dict), "semantic_task_payload_missing")
    if isinstance(semantic_task, dict):
        require(semantic_task.get("status") == "verified", "semantic_task_status_invalid")
        require(semantic_task.get("verdict") == "verified", "semantic_task_verdict_invalid")
        require(semantic_task.get("recover") == "proceed", "semantic_task_recover_invalid")
        require(
            _nested(semantic_task, "safety", "mode") == "isolated",
            "semantic_task_not_isolated",
        )
        require(
            _nested(receipt, "phases", "semantic_task", "payload_sha256")
            == _value_sha256(semantic_task),
            "semantic_task_payload_digest_mismatch",
        )
    require(
        _nested(receipt, "phases", "isolated_invoke", "activations") == 1,
        "isolated_activation_count_invalid",
    )
    require(
        _nested(receipt, "phases", "dry_run", "activations") == 1,
        "dry_run_activation_count_invalid",
    )
    require(
        _nested(receipt, "phases", "host_denial", "activations") == 1,
        "host_activation_count_invalid",
    )
    require(
        _nested(receipt, "phases", "semantic_task", "activations") == 2,
        "semantic_task_activation_count_invalid",
    )
    return errors


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _add_write_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("write", help="write and validate one acceptance receipt")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--binary-version", required=True)
    parser.add_argument("--backend", choices=("wayland", "headless"), required=True)
    parser.add_argument("--output-names", required=True)
    parser.add_argument("--display", required=True)
    parser.add_argument("--sway-pid", type=int, required=True)
    parser.add_argument(
        "--snapshot-target-present", choices=("true", "false"), required=True
    )
    parser.add_argument("--isolated-invoke", type=Path, required=True)
    parser.add_argument("--postcondition-verify", type=Path, required=True)
    parser.add_argument("--dry-run-invoke", type=Path, required=True)
    parser.add_argument("--host-invoke", type=Path, required=True)
    parser.add_argument("--semantic-task", type=Path, required=True)
    parser.add_argument("--isolated-activations", type=int, required=True)
    parser.add_argument("--dry-run-activations", type=int, required=True)
    parser.add_argument("--host-activations", type=int, required=True)
    parser.add_argument("--transaction-activations", type=int, required=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_write_parser(subparsers)
    validate = subparsers.add_parser("validate", help="validate an existing receipt")
    validate.add_argument("receipt", type=Path)
    args = parser.parse_args(argv)

    if args.command == "validate":
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        errors = validate_receipt(receipt)
        print(json.dumps({"status": "passed" if not errors else "failed", "errors": errors}))
        return 0 if not errors else 1

    receipt = build_receipt(
        source_commit=args.source_commit,
        binary_path=args.binary,
        binary_version=args.binary_version,
        backend=args.backend,
        output_names=args.output_names.split(","),
        display=args.display,
        sway_pid=args.sway_pid,
        snapshot_target_present=args.snapshot_target_present == "true",
        isolated_invoke=_read_payload(args.isolated_invoke),
        postcondition_verify=_read_payload(args.postcondition_verify),
        dry_run_invoke=_read_payload(args.dry_run_invoke),
        host_invoke=_read_payload(args.host_invoke),
        semantic_task=_read_payload(args.semantic_task),
        activation_counts={
            "isolated": args.isolated_activations,
            "dry_run": args.dry_run_activations,
            "host_denied": args.host_activations,
            "transaction": args.transaction_activations,
        },
    )
    _atomic_write_json(args.output, receipt)
    errors = validate_receipt(receipt)
    print(
        json.dumps(
            {
                "status": "passed" if not errors else "failed",
                "receipt": str(args.output.resolve()),
                "errors": errors,
            }
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
