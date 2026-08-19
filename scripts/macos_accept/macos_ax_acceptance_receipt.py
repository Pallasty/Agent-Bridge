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
EXPECTED_CHECK_IDS = (
    "source_commit_valid",
    "probe_schema",
    "probe_read_only",
    "probe_ready",
    "ax_trusted",
    "probe_error_free",
    "frontmost_app_observed",
    "bounded_windows",
    "window_identity_declared",
    "verify_probe_dependency_matches",
    "trust_verified",
    "frontmost_app_verified",
    "window_presence_verified",
)


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


def _strict_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _app_identity_valid(app: Any) -> bool:
    if not isinstance(app, dict):
        return False
    pid = app.get("pid")
    return bool(
        isinstance(pid, int)
        and not isinstance(pid, bool)
        and pid > 0
        and any(
            isinstance(app.get(key), str) and bool(app[key].strip())
            for key in ("name", "bundle_id")
        )
    )


def _verify_evidence_admissible(
    payload: dict[str, Any],
    expect: str,
    expected_pid: int | None,
) -> bool:
    if not (
        payload.get("schema") == "macos_ax_verify/v0"
        and payload.get("expect") == expect
        and payload.get("verdict") == "verified"
        and payload.get("recover") == "proceed"
        and "error" in payload
        and payload.get("error") is None
    ):
        return False
    observed = payload.get("observed")
    selector = payload.get("selector")
    scope = payload.get("scope")
    if not (
        isinstance(observed, dict)
        and isinstance(selector, dict)
        and isinstance(scope, dict)
        and scope.get("source") == "frontmost_app_windows"
        and isinstance(scope.get("platform"), dict)
        and scope["platform"].get("system") == "Darwin"
    ):
        return False
    proof = observed.get("proof")
    expected_evidence = {
        "ax_trusted_is": "ax_trust",
        "frontmost_app_is": "frontmost_app_identity",
        "window_appeared": "frontmost_app_window_observation",
    }[expect]
    if not (
        isinstance(proof, dict)
        and proof.get("complete") is True
        and proof.get("truth") == "match"
        and proof.get("required_evidence") == expected_evidence
        and observed.get("proof_complete") is True
    ):
        return False
    permission = observed.get("permission")
    if not (
        isinstance(permission, dict)
        and permission.get("ax_trusted") is True
        and permission.get("prompted") is False
        and permission.get("method") == "AXIsProcessTrusted"
    ):
        return False
    if expect == "ax_trusted_is":
        return bool(
            isinstance(selector.get("state"), str)
            and selector["state"].strip().lower() in {"true", "1", "yes", "y"}
            and all(
                selector.get(key) is None
                for key in (
                    "app",
                    "bundle_id",
                    "pid",
                    "title",
                    "role",
                    "index",
                    "ax_identifier",
                )
            )
            and scope.get("max_windows") == 0
            and observed.get("probe_status") == "ready"
            and observed.get("errors") == []
            and isinstance(observed.get("matches"), list)
            and len(observed["matches"]) == 1
            and isinstance(observed["matches"][0], dict)
            and observed["matches"][0].get("ax_trusted") is True
        )
    if not (
        isinstance(expected_pid, int)
        and not isinstance(expected_pid, bool)
        and expected_pid > 0
        and selector.get("pid") == expected_pid
        and observed.get("app_identity_valid") is True
        and _app_identity_valid(observed.get("frontmost_app"))
        and observed["frontmost_app"].get("pid") == expected_pid
    ):
        return False
    if expect == "frontmost_app_is":
        errors = observed.get("errors")
        return (
            scope.get("max_windows") == 8
            and isinstance(observed.get("probe_status"), str)
            and observed["probe_status"] in {"ready", "degraded"}
            and all(
                selector.get(key) is None
                for key in ("app", "bundle_id", "title", "role", "index", "ax_identifier", "state")
            )
            and observed.get("count") == 1
            and isinstance(observed.get("matches"), list)
            and len(observed["matches"]) == 1
            and isinstance(observed["matches"][0], dict)
            and observed["matches"][0].get("pid") == expected_pid
            and isinstance(errors, list)
            and all(
                isinstance(error, dict)
                and error.get("stage")
                in {"system_events_windows", "system_events_window_count"}
                for error in errors
            )
        )
    matches = observed.get("matches")
    limits = observed.get("limits")
    coverage = observed.get("coverage")
    window_count = observed.get("window_count")
    source_window_count = observed.get("source_window_count")
    counts_equal = bool(
        _strict_nonnegative_int(window_count)
        and _strict_nonnegative_int(source_window_count)
        and source_window_count == window_count
    )
    counts_ordered = bool(
        _strict_nonnegative_int(window_count)
        and _strict_nonnegative_int(source_window_count)
        and source_window_count >= window_count
    )
    coverage_reasons = coverage.get("reasons") if isinstance(coverage, dict) else None
    return bool(
        scope.get("max_windows") == 8
        and selector.get("role") == "AXWindow"
        and all(
            selector.get(key) is None
            for key in ("app", "bundle_id", "title", "index", "ax_identifier", "state")
        )
        and observed.get("probe_status") == "ready"
        and observed.get("scope_match") is True
        and observed.get("windows_read_ok") is True
        and observed.get("errors") == []
        and isinstance(limits, dict)
        and limits.get("max_windows") == scope.get("max_windows")
        and limits.get("include_windows") is True
        and counts_ordered
        and window_count <= limits["max_windows"]
        and limits.get("truncated") is (source_window_count > window_count)
        and observed.get("counts_consistent") is counts_equal
        and isinstance(coverage, dict)
        and coverage.get("complete") is counts_equal
        and observed.get("coverage_complete") is counts_equal
        and isinstance(coverage_reasons, list)
        and observed.get("incomplete_reasons") == coverage_reasons
        and bool(coverage_reasons) is (not counts_equal)
        and _strict_nonnegative_int(observed.get("count"))
        and observed["count"] > 0
        and isinstance(matches, list)
        and len(matches) == observed["count"]
        and len(matches) <= window_count
        and any(
            isinstance(match, dict)
            and isinstance(match.get("role"), str)
            and "axwindow" in match["role"].strip().lower()
            for match in matches
        )
    )


def _receipt_evidence_checks(receipt: dict[str, Any]) -> dict[str, bool]:
    phases = receipt.get("phases")
    phases = phases if isinstance(phases, dict) else {}

    def phase_payload(name: str) -> dict[str, Any]:
        phase = phases.get(name)
        if not isinstance(phase, dict):
            return {}
        payload = phase.get("payload")
        return payload if isinstance(payload, dict) else {}

    probe = phase_payload("probe")
    trust_verify = phase_payload("trust_verify")
    app_verify = phase_payload("app_verify")
    window_verify = phase_payload("window_verify")
    windows = probe.get("windows") if isinstance(probe.get("windows"), list) else []
    window_count = probe.get("window_count")
    source_window_count = probe.get("source_window_count")
    limits = probe.get("limits") if isinstance(probe.get("limits"), dict) else {}
    counts_complete = bool(
        _strict_nonnegative_int(window_count)
        and _strict_nonnegative_int(source_window_count)
        and window_count == source_window_count == len(windows)
    )
    identities_complete = all(
        isinstance(window, dict)
        and isinstance(window.get("identity"), dict)
        and isinstance(window["identity"].get("stable_across_samples"), bool)
        for window in windows
    )
    app_identity_valid = _app_identity_valid(probe.get("frontmost_app"))
    permission = probe.get("permission")
    probe_ready = bool(
        probe.get("status") == "ready"
        and isinstance(permission, dict)
        and permission.get("ax_trusted") is True
        and permission.get("prompted") is False
        and permission.get("method") == "AXIsProcessTrusted"
        and probe.get("windows_read_ok") is True
        and probe.get("app_identity_valid") is True
        and app_identity_valid
        and probe.get("counts_consistent") is True
        and counts_complete
        and probe.get("coverage_complete") is True
        and probe.get("incomplete_reasons") == []
        and limits.get("truncated") is False
        and limits.get("include_windows") is True
    )
    probe_pid = (
        probe["frontmost_app"].get("pid")
        if isinstance(probe.get("frontmost_app"), dict)
        else None
    )

    source = receipt.get("source")
    source = source if isinstance(source, dict) else {}
    scripts = source.get("scripts")
    scripts = scripts if isinstance(scripts, dict) else {}
    probe_script = scripts.get("probe")
    verify_script = scripts.get("verify")
    dependency = scripts.get("verify_probe_dependency")
    probe_script = probe_script if isinstance(probe_script, dict) else {}
    verify_script = verify_script if isinstance(verify_script, dict) else {}
    dependency = dependency if isinstance(dependency, dict) else {}

    def valid_sha256(value: Any) -> bool:
        return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None

    probe_sha = probe_script.get("sha256")
    dependency_sha = dependency.get("sha256")
    dependency_matches = bool(
        valid_sha256(probe_sha)
        and valid_sha256(verify_script.get("sha256"))
        and valid_sha256(dependency_sha)
        and dependency_sha == probe_sha
    )
    return {
        "source_commit_valid": bool(
            re.fullmatch(r"[0-9a-f]{40,64}", str(source.get("commit", "")))
        ),
        "probe_schema": probe.get("schema") == "macos_ax_probe/v0",
        "probe_read_only": probe.get("read_only") is True,
        "probe_ready": probe_ready,
        "ax_trusted": isinstance(permission, dict)
        and permission.get("ax_trusted") is True,
        "probe_error_free": probe.get("errors") == [],
        "frontmost_app_observed": app_identity_valid,
        "bounded_windows": bool(
            counts_complete
            and _strict_nonnegative_int(limits.get("max_windows"))
            and len(windows) <= limits["max_windows"] <= 50
        ),
        "window_identity_declared": identities_complete,
        "verify_probe_dependency_matches": dependency_matches,
        "trust_verified": _verify_evidence_admissible(
            trust_verify, "ax_trusted_is", probe_pid
        ),
        "frontmost_app_verified": _verify_evidence_admissible(
            app_verify, "frontmost_app_is", probe_pid
        ),
        "window_presence_verified": _verify_evidence_admissible(
            window_verify, "window_appeared", probe_pid
        ),
    }


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
    app_identity_valid = _app_identity_valid(probe.get("frontmost_app"))
    window_count = probe.get("window_count")
    source_window_count = probe.get("source_window_count")
    limits = probe.get("limits") if isinstance(probe.get("limits"), dict) else {}
    counts_complete = bool(
        _strict_nonnegative_int(window_count)
        and _strict_nonnegative_int(source_window_count)
        and window_count == source_window_count == len(windows)
    )
    probe_evidence_complete = bool(
        probe.get("status") == "ready"
        and isinstance(probe.get("permission"), dict)
        and probe["permission"].get("ax_trusted") is True
        and probe["permission"].get("prompted") is False
        and probe["permission"].get("method") == "AXIsProcessTrusted"
        and probe.get("windows_read_ok") is True
        and probe.get("app_identity_valid") is True
        and app_identity_valid
        and probe.get("counts_consistent") is True
        and counts_complete
        and probe.get("coverage_complete") is True
        and probe.get("incomplete_reasons") == []
        and limits.get("truncated") is False
        and limits.get("include_windows") is True
    )
    verify_probe_dependency = verify_script.with_name("macos_ax_probe.py")
    dependency_matches = bool(
        verify_probe_dependency.is_file()
        and probe_script.is_file()
        and _sha256(verify_probe_dependency) == _sha256(probe_script)
    )
    checks: list[dict[str, Any]] = []
    probe_pid = (
        probe["frontmost_app"].get("pid")
        if isinstance(probe.get("frontmost_app"), dict)
        else None
    )
    _check(checks, "source_commit_valid", bool(re.fullmatch(r"[0-9a-f]{40,64}", source_commit)), source_commit)
    _check(checks, "probe_schema", probe.get("schema") == "macos_ax_probe/v0", probe.get("schema"))
    _check(checks, "probe_read_only", probe.get("read_only") is True, probe.get("read_only"))
    _check(
        checks,
        "probe_ready",
        probe_evidence_complete,
        {
            "status": probe.get("status"),
            "coverage_complete": probe.get("coverage_complete"),
            "incomplete_reasons": probe.get("incomplete_reasons"),
        },
    )
    permission = probe.get("permission")
    _check(
        checks,
        "ax_trusted",
        isinstance(permission, dict) and permission.get("ax_trusted") is True,
        permission,
    )
    _check(checks, "probe_error_free", probe.get("errors") == [], probe.get("errors"))
    _check(checks, "frontmost_app_observed", app_identity_valid, probe.get("frontmost_app"))
    _check(
        checks,
        "bounded_windows",
        counts_complete
        and _strict_nonnegative_int(limits.get("max_windows"))
        and len(windows) <= limits["max_windows"] <= 50,
        {"limits": limits, "window_count": window_count, "source_window_count": source_window_count},
    )
    _check(checks, "window_identity_declared", identities_complete, {"stable": len(stable), "sample_local": len(sample_local), "total": len(windows)})
    _check(
        checks,
        "verify_probe_dependency_matches",
        dependency_matches,
        {"path": str(verify_probe_dependency), "probe_path": str(probe_script)},
    )
    _check(
        checks,
        "trust_verified",
        _verify_evidence_admissible(trust_verify, "ax_trusted_is", probe_pid),
        trust_verify,
    )
    _check(
        checks,
        "frontmost_app_verified",
        _verify_evidence_admissible(app_verify, "frontmost_app_is", probe_pid),
        app_verify,
    )
    _check(
        checks,
        "window_presence_verified",
        _verify_evidence_admissible(window_verify, "window_appeared", probe_pid),
        window_verify,
    )

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(item["passed"] for item in checks) else "failed",
        "source": {
            "commit": source_commit,
            "scripts": {
                "probe": {"path": str(probe_script), "sha256": _sha256(probe_script)},
                "verify": {"path": str(verify_script), "sha256": _sha256(verify_script)},
                "verify_probe_dependency": {
                    "path": str(verify_probe_dependency),
                    "sha256": _sha256(verify_probe_dependency)
                    if verify_probe_dependency.is_file()
                    else None,
                },
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
    check_ids = (
        [item.get("id") for item in checks if isinstance(item, dict)]
        if isinstance(checks, list)
        else []
    )
    if (
        not isinstance(checks, list)
        or len(checks) != len(EXPECTED_CHECK_IDS)
        or len(check_ids) != len(EXPECTED_CHECK_IDS)
        or any(not isinstance(check_id, str) for check_id in check_ids)
        or set(check_ids) != set(EXPECTED_CHECK_IDS)
    ):
        errors.append("check_coverage_invalid")
    elif any(not isinstance(item, dict) or item.get("passed") is not True for item in checks):
        errors.append("required_check_failed")
    evidence_checks = _receipt_evidence_checks(receipt)
    if any(evidence_checks.get(check_id) is not True for check_id in EXPECTED_CHECK_IDS):
        errors.append("evidence_contract_invalid")
    if isinstance(checks, list):
        stored_checks = {
            item.get("id"): item.get("passed")
            for item in checks
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        if any(
            stored_checks.get(check_id) is not evidence_checks.get(check_id)
            for check_id in EXPECTED_CHECK_IDS
        ):
            errors.append("check_recomputation_mismatch")
    if receipt.get("status") != "passed":
        errors.append("status_not_passed")
    channels = receipt.get("channels")
    channels = channels if isinstance(channels, dict) else {}
    selected = channels.get("selected")
    skipped = channels.get("skipped")
    selected = selected if isinstance(selected, list) else []
    skipped = skipped if isinstance(skipped, list) else []
    if "read_only_postcondition_verification" not in selected:
        errors.append("postcondition_channel_missing")
    if not any(item.get("channel") == "desktop_mutation" for item in skipped if isinstance(item, dict)):
        errors.append("mutation_skip_missing")
    phases = receipt.get("phases")
    phases = phases if isinstance(phases, dict) else {}
    for name in ("probe", "trust_verify", "app_verify", "window_verify"):
        phase = phases.get(name)
        phase = phase if isinstance(phase, dict) else {}
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
