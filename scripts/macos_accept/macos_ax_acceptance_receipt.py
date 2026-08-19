#!/usr/bin/env python3
"""Write or validate a bounded, read-only macOS AX acceptance receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "agent_bridge.macos_ax_acceptance_receipt.v0"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _check(checks: list[dict[str, Any]], check_id: str, passed: bool, evidence: Any) -> None:
    checks.append({"id": check_id, "passed": bool(passed), "evidence": evidence})


def build_receipt(
    *,
    source_commit: str,
    probe_script: Path,
    verify_script: Path,
    probe: dict[str, Any],
    trust_verify: dict[str, Any],
    app_verify: dict[str, Any],
    window_verify: dict[str, Any],
) -> dict[str, Any]:
    windows = probe.get("windows") if isinstance(probe.get("windows"), list) else []
    stable = [
        window
        for window in windows
        if isinstance(window, dict)
        and isinstance(window.get("identity"), dict)
        and window["identity"].get("stable_across_samples") is True
    ]
    sample_local = [
        window
        for window in windows
        if isinstance(window, dict)
        and isinstance(window.get("identity"), dict)
        and window["identity"].get("stable_across_samples") is False
    ]
    identities_complete = len(stable) + len(sample_local) == len(windows)
    checks: list[dict[str, Any]] = []
    _check(checks, "source_commit_valid", bool(re.fullmatch(r"[0-9a-f]{40,64}", source_commit)), source_commit)
    _check(checks, "probe_schema", probe.get("schema") == "macos_ax_probe/v0", probe.get("schema"))
    _check(checks, "probe_read_only", probe.get("read_only") is True, probe.get("read_only"))
    _check(checks, "probe_ready", probe.get("status") == "ready", probe.get("status"))
    _check(
        checks,
        "ax_trusted",
        (probe.get("permission") or {}).get("ax_trusted") is True,
        probe.get("permission"),
    )
    _check(checks, "probe_error_free", probe.get("errors") == [], probe.get("errors"))
    _check(checks, "frontmost_app_observed", isinstance(probe.get("frontmost_app"), dict), probe.get("frontmost_app"))
    _check(checks, "bounded_windows", len(windows) <= 50 and (probe.get("limits") or {}).get("max_windows", 51) <= 50, probe.get("limits"))
    _check(checks, "window_identity_declared", identities_complete, {"stable": len(stable), "sample_local": len(sample_local), "total": len(windows)})
    _check(checks, "trust_verified", trust_verify.get("verdict") == "verified" and trust_verify.get("recover") == "proceed", {"verdict": trust_verify.get("verdict"), "recover": trust_verify.get("recover")})
    _check(checks, "frontmost_app_verified", app_verify.get("verdict") == "verified" and app_verify.get("recover") == "proceed", {"verdict": app_verify.get("verdict"), "recover": app_verify.get("recover")})
    _check(checks, "window_presence_verified", window_verify.get("verdict") == "verified" and window_verify.get("recover") == "proceed", {"verdict": window_verify.get("verdict"), "recover": window_verify.get("recover")})

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(item["passed"] for item in checks) else "failed",
        "source": {
            "commit": source_commit,
            "scripts": {
                "probe": {"path": str(probe_script), "sha256": _sha256(probe_script)},
                "verify": {"path": str(verify_script), "sha256": _sha256(verify_script)},
            },
        },
        "environment": {
            "hostname": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
        },
        "channels": {
            "selected": [
                "ax_trust",
                "system_events_frontmost_application",
                "bounded_ax_window_observation",
                "read_only_postcondition_verification",
            ],
            "skipped": [
                {"channel": "screenshot", "reason": "semantic AX evidence was sufficient"},
                {"channel": "ocr", "reason": "semantic AX evidence was sufficient"},
                {"channel": "coordinate_input", "reason": "read-only acceptance forbids input"},
                {"channel": "desktop_mutation", "reason": "no macOS action adapter is under acceptance"},
            ],
        },
        "identity_coverage": {
            "stable_ax_identifier_count": len(stable),
            "sample_local_index_count": len(sample_local),
            "total_windows": len(windows),
            "all_windows_declared": identities_complete,
        },
        "phases": {
            "probe": {"payload": probe, "payload_sha256": _payload_sha256(probe)},
            "trust_verify": {"payload": trust_verify, "payload_sha256": _payload_sha256(trust_verify)},
            "app_verify": {"payload": app_verify, "payload_sha256": _payload_sha256(app_verify)},
            "window_verify": {"payload": window_verify, "payload_sha256": _payload_sha256(window_verify)},
        },
        "checks": checks,
    }


def validate_receipt(receipt: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if receipt.get("schema") != SCHEMA:
        errors.append("schema_invalid")
    checks = receipt.get("checks")
    if not isinstance(checks, list) or len(checks) != 12:
        errors.append("check_coverage_invalid")
    elif any(not isinstance(item, dict) or item.get("passed") is not True for item in checks):
        errors.append("required_check_failed")
    if receipt.get("status") != "passed":
        errors.append("status_not_passed")
    channels = receipt.get("channels") or {}
    selected = channels.get("selected") or []
    skipped = channels.get("skipped") or []
    if "read_only_postcondition_verification" not in selected:
        errors.append("postcondition_channel_missing")
    if not any(item.get("channel") == "desktop_mutation" for item in skipped if isinstance(item, dict)):
        errors.append("mutation_skip_missing")
    phases = receipt.get("phases") or {}
    for name in ("probe", "trust_verify", "app_verify", "window_verify"):
        phase = phases.get(name) or {}
        payload = phase.get("payload")
        if not isinstance(payload, dict) or phase.get("payload_sha256") != _payload_sha256(payload):
            errors.append(f"{name}_payload_digest_invalid")
    return errors


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    write = subparsers.add_parser("write")
    write.add_argument("--output", type=Path, required=True)
    write.add_argument("--source-commit", required=True)
    write.add_argument("--probe-script", type=Path, required=True)
    write.add_argument("--verify-script", type=Path, required=True)
    write.add_argument("--probe", type=Path, required=True)
    write.add_argument("--trust-verify", type=Path, required=True)
    write.add_argument("--app-verify", type=Path, required=True)
    write.add_argument("--window-verify", type=Path, required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("receipt", type=Path)
    args = parser.parse_args(argv)

    if args.command == "validate":
        errors = validate_receipt(_read(args.receipt))
        print(json.dumps({"status": "passed" if not errors else "failed", "errors": errors}))
        return 0 if not errors else 1

    receipt = build_receipt(
        source_commit=args.source_commit,
        probe_script=args.probe_script,
        verify_script=args.verify_script,
        probe=_read(args.probe),
        trust_verify=_read(args.trust_verify),
        app_verify=_read(args.app_verify),
        window_verify=_read(args.window_verify),
    )
    _atomic_write(args.output, receipt)
    errors = validate_receipt(receipt)
    print(json.dumps({"status": "passed" if not errors else "failed", "receipt": str(args.output.resolve()), "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
