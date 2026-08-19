#!/usr/bin/env python3
"""macOS AX read-only, fail-closed verifier.

Re-observes the same bounded surface as macos_ax_probe.py and checks one
predicate. It never explicitly requests permission, activates apps, focuses
windows, clicks, types, or mutates desktop state. System Events reads inherit
the shared probe's best-effort no-ask Automation preflight.
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from typing import Any

from macos_ax_probe import (
    _annotate_window_identities,
    _ax_is_trusted,
    _frontmost_app_identity_valid,
    _frontmost_jxa,
    _strict_nonnegative_int,
)

SCHEMA_VERSION = "macos_ax_verify/v0"
EXPECTS = {
    "ax_trusted_is",
    "frontmost_app_is",
    "window_appeared",
    "window_gone",
    "window_focused",
}
WINDOW_EXPECTS = {"window_appeared", "window_gone", "window_focused"}
MATCH = "match"
NO_MATCH = "no_match"
UNKNOWN = "unknown"


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _bool_arg(value: str | None) -> bool | None:
    if value is None:
        return None
    lower = value.strip().lower()
    if lower in {"true", "1", "yes", "y"}:
        return True
    if lower in {"false", "0", "no", "n"}:
        return False
    return None


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _selector_error(args: argparse.Namespace) -> str | None:
    for key in ("app", "bundle_id", "title", "role", "ax_identifier"):
        value = getattr(args, key)
        if value is not None and not _nonempty_string(value):
            return f"invalid_selector:{key}_must_be_nonempty"
    if args.pid is not None and (
        not isinstance(args.pid, int) or isinstance(args.pid, bool) or args.pid <= 0
    ):
        return "invalid_selector:pid_must_be_positive_integer"
    if args.index is not None and (
        not isinstance(args.index, int) or isinstance(args.index, bool) or args.index < 0
    ):
        return "invalid_selector:index_must_be_nonnegative_integer"

    if args.expect == "ax_trusted_is":
        if _bool_arg(args.state) is None:
            return "invalid_selector:state_must_be_true_or_false"
        return None
    if args.expect == "frontmost_app_is":
        if not (
            args.pid is not None
            or _nonempty_string(args.app)
            or _nonempty_string(args.bundle_id)
        ):
            return "invalid_selector:frontmost_app_selector_required"
        return None
    if args.expect in WINDOW_EXPECTS:
        # Window observations are scoped to the frontmost process. A bundle id
        # or PID is required because an app display name is not a process identity.
        if not (args.pid is not None or _nonempty_string(args.bundle_id)):
            return "invalid_selector:window_app_scope_requires_bundle_id_or_pid"
        if not any(
            _nonempty_string(getattr(args, key))
            for key in ("title", "role", "ax_identifier")
        ):
            return "invalid_selector:window_selector_required_index_is_sample_local"
        if args.expect == "window_gone" and args.index is not None:
            return "invalid_selector:window_gone_cannot_use_sample_local_index"
    return None


def _selector(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "app": args.app,
        "bundle_id": args.bundle_id,
        "pid": args.pid,
        "title": args.title,
        "role": args.role,
        "index": args.index,
        "ax_identifier": args.ax_identifier,
        "state": args.state,
    }


def _probe(
    max_windows: int,
    jxa_timeout_secs: float,
    *,
    include_windows: bool = True,
) -> tuple[dict[str, Any], str | None]:
    started = time.time()
    system = platform.system()
    errors: list[dict[str, Any]] = []
    ax_trusted, ax_error = _ax_is_trusted()
    if ax_error:
        errors.append({"stage": "ax_trust", "message": ax_error})

    frontmost: dict[str, Any] | None = None
    windows: list[dict[str, Any]] = []
    source_window_count: int | None = None
    windows_read_ok: bool | None = None
    truncated = False

    if system != "Darwin":
        status = "unsupported_platform"
    elif not include_windows and isinstance(ax_trusted, bool):
        status = "ready"
    elif ax_trusted is not True:
        if ax_trusted is None and not ax_error:
            errors.append({"stage": "ax_trust", "message": "AX trust status unavailable"})
        status = "degraded"
    else:
        jxa_payload, jxa_error = _frontmost_jxa(max_windows, jxa_timeout_secs)
        if jxa_error:
            errors.append({"stage": "system_events", "message": jxa_error})
            status = "degraded"
        elif not isinstance(jxa_payload, dict):
            errors.append({"stage": "system_events", "message": "invalid JXA payload"})
            status = "degraded"
        else:
            frontmost = jxa_payload.get("frontmost_app")
            raw_windows = jxa_payload.get("windows")
            source_window_count = jxa_payload.get("window_count")
            windows_read_ok = jxa_payload.get("windows_read_ok")
            if isinstance(raw_windows, list) and all(
                isinstance(window, dict) for window in raw_windows
            ):
                windows = _annotate_window_identities(raw_windows)
            else:
                errors.append(
                    {
                        "stage": "system_events_windows",
                        "message": "invalid windows payload",
                    }
                )
            if windows_read_ok is not True:
                errors.append(
                    {
                        "stage": "system_events_windows",
                        "message": "window enumeration failed",
                    }
                )
            if not _strict_nonnegative_int(source_window_count):
                errors.append(
                    {
                        "stage": "system_events_window_count",
                        "message": "invalid source window count",
                    }
                )
            elif source_window_count < len(windows):
                errors.append(
                    {
                        "stage": "system_events_window_count",
                        "message": "source window count is smaller than returned windows",
                    }
                )
            truncated = bool(
                _strict_nonnegative_int(source_window_count)
                and source_window_count > len(windows)
            )
            status = (
                "ready"
                if _frontmost_app_identity_valid(frontmost)
                and windows_read_ok is True
                and _strict_nonnegative_int(source_window_count)
                and source_window_count >= len(windows)
                and not errors
                else "degraded"
            )

    probe = {
        "platform": {
            "system": system,
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "status": status,
        "permission": {
            "ax_trusted": ax_trusted,
            "method": "AXIsProcessTrusted",
            "prompted": False,
        },
        "frontmost_app": frontmost,
        "windows": windows,
        "window_count": len(windows),
        "source_window_count": source_window_count,
        "windows_read_ok": windows_read_ok,
        "app_identity_valid": _frontmost_app_identity_valid(frontmost),
        "counts_consistent": bool(
            _strict_nonnegative_int(source_window_count)
            and source_window_count == len(windows)
        ),
        "limits": {
            "max_windows": max_windows,
            "truncated": truncated,
            "include_windows": include_windows,
        },
        "errors": errors,
        "elapsed_ms": int((time.time() - started) * 1000),
    }
    incomplete_reasons = _window_coverage_incomplete_reasons(probe)
    probe["coverage_complete"] = not incomplete_reasons
    probe["incomplete_reasons"] = incomplete_reasons
    if status == "unsupported_platform":
        return probe, "unsupported_platform"
    if status == "degraded":
        return probe, "probe_degraded"
    return probe, None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _relevant_errors(probe: dict[str, Any], *, include_windows: bool) -> list[dict[str, Any]]:
    errors = probe.get("errors")
    if not isinstance(errors, list):
        return [{"stage": "probe", "message": "invalid errors payload"}]
    valid = [error for error in errors if isinstance(error, dict)]
    if len(valid) != len(errors):
        valid.append({"stage": "probe", "message": "invalid error entry"})
    if include_windows:
        return valid
    return [
        error
        for error in valid
        if error.get("stage") not in {"system_events_windows", "system_events_window_count"}
    ]


def _trust_incomplete_reasons(probe: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if (probe.get("platform") or {}).get("system") != "Darwin":
        reasons.append("unsupported_platform")
    permission = probe.get("permission")
    trusted = permission.get("ax_trusted") if isinstance(permission, dict) else None
    if not isinstance(trusted, bool):
        reasons.append("ax_trust_unknown")
    if any(
        error.get("stage") == "ax_trust"
        for error in _relevant_errors(probe, include_windows=False)
    ):
        reasons.append("ax_trust_error")
    return _dedupe(reasons)


def _app_incomplete_reasons(probe: dict[str, Any]) -> list[str]:
    reasons = _trust_incomplete_reasons(probe)
    permission = probe.get("permission")
    if not isinstance(permission, dict) or permission.get("ax_trusted") is not True:
        reasons.append("ax_not_trusted")
    if not _frontmost_app_identity_valid(probe.get("frontmost_app")):
        reasons.append("frontmost_app_identity_invalid")
    if _relevant_errors(probe, include_windows=False):
        reasons.append("app_observation_error")
    return _dedupe(reasons)


def _window_evidence_incomplete_reasons(probe: dict[str, Any]) -> list[str]:
    """Return reasons that make even a positive window witness unsafe."""
    reasons = _app_incomplete_reasons(probe)
    if _relevant_errors(probe, include_windows=True):
        reasons.append("window_observation_error")
    if probe.get("windows_read_ok") is not True:
        reasons.append("window_enumeration_unconfirmed")
    windows = probe.get("windows")
    if not isinstance(windows, list) or any(not isinstance(window, dict) for window in windows):
        reasons.append("windows_invalid")
        returned_count: int | None = None
    else:
        returned_count = len(windows)
    window_count = probe.get("window_count")
    source_count = probe.get("source_window_count")
    if not _strict_nonnegative_int(window_count):
        reasons.append("window_count_invalid")
    elif returned_count is not None and window_count != returned_count:
        reasons.append("window_count_mismatch")
    if not _strict_nonnegative_int(source_count):
        reasons.append("source_window_count_invalid")
    elif returned_count is not None and source_count < returned_count:
        reasons.append("source_window_count_mismatch")
    truncated = (probe.get("limits") or {}).get("truncated")
    if not isinstance(truncated, bool):
        reasons.append("truncation_status_unknown")
    elif (
        returned_count is not None
        and _strict_nonnegative_int(source_count)
        and truncated is not (source_count > returned_count)
    ):
        reasons.append("truncation_status_mismatch")
    return _dedupe(reasons)


def _window_coverage_incomplete_reasons(probe: dict[str, Any]) -> list[str]:
    reasons = _window_evidence_incomplete_reasons(probe)
    windows = probe.get("windows")
    source_count = probe.get("source_window_count")
    if isinstance(windows, list) and _strict_nonnegative_int(source_count):
        if source_count != len(windows):
            reasons.append("window_enumeration_truncated")
    if (probe.get("limits") or {}).get("truncated") is not False:
        reasons.append("window_enumeration_incomplete")
    return _dedupe(reasons)


def _text_comparison(
    actual: Any,
    expected: str | None,
    *,
    exact: bool = False,
    case_sensitive: bool = False,
) -> str:
    if expected is None:
        return MATCH
    if not isinstance(actual, str):
        return UNKNOWN
    if exact:
        if case_sensitive:
            return MATCH if actual == expected else NO_MATCH
        return MATCH if _norm(actual) == _norm(expected) else NO_MATCH
    return MATCH if _norm(expected) in _norm(actual) else NO_MATCH


def _compare_app(app: Any, args: argparse.Namespace) -> str:
    if not isinstance(app, dict):
        return UNKNOWN
    comparisons = [
        _text_comparison(app.get("name"), args.app),
        _text_comparison(app.get("bundle_id"), args.bundle_id, exact=True),
    ]
    if args.pid is not None:
        actual_pid = app.get("pid")
        if not isinstance(actual_pid, int) or isinstance(actual_pid, bool) or actual_pid <= 0:
            comparisons.append(UNKNOWN)
        else:
            comparisons.append(MATCH if actual_pid == args.pid else NO_MATCH)
    if NO_MATCH in comparisons:
        return NO_MATCH
    return UNKNOWN if UNKNOWN in comparisons else MATCH


def _match_app(app: dict[str, Any] | None, args: argparse.Namespace) -> bool:
    return _compare_app(app, args) == MATCH


def _compare_window(window: Any, args: argparse.Namespace) -> str:
    if not isinstance(window, dict):
        return UNKNOWN
    comparisons = [
        _text_comparison(
            window.get("ax_identifier"),
            args.ax_identifier,
            exact=True,
            case_sensitive=True,
        ),
        _text_comparison(window.get("title"), args.title),
        _text_comparison(window.get("role"), args.role),
    ]
    if args.index is not None:
        actual_index = window.get("index")
        if not _strict_nonnegative_int(actual_index):
            comparisons.append(UNKNOWN)
        else:
            comparisons.append(MATCH if actual_index == args.index else NO_MATCH)
    if NO_MATCH in comparisons:
        return NO_MATCH
    return UNKNOWN if UNKNOWN in comparisons else MATCH


def _match_window(window: dict[str, Any], args: argparse.Namespace) -> bool:
    return _compare_window(window, args) == MATCH


def _evaluate(
    args: argparse.Namespace,
    probe: dict[str, Any],
    *,
    coverage_complete: bool,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], str | None]:
    expect = args.expect
    if expect == "ax_trusted_is":
        wanted = _bool_arg(args.state)
        if wanted is None:
            return UNKNOWN, [], [], "invalid_selector:state_must_be_true_or_false"
        actual = probe.get("permission", {}).get("ax_trusted")
        return (MATCH if actual is wanted else NO_MATCH), [{"ax_trusted": actual}], [], None

    app = probe.get("frontmost_app")
    if expect == "frontmost_app_is":
        comparison = _compare_app(app, args)
        return comparison, [app] if comparison == MATCH and isinstance(app, dict) else [], [], None

    windows = probe.get("windows") or []
    candidates = [window for window in windows if _compare_window(window, args) == MATCH]
    unknowns = [window for window in windows if _compare_window(window, args) == UNKNOWN]
    if expect == "window_appeared":
        if candidates:
            return MATCH, candidates, unknowns, None
        return (UNKNOWN if unknowns or not coverage_complete else NO_MATCH), [], unknowns, None
    if expect == "window_gone":
        if candidates:
            return NO_MATCH, candidates, unknowns, None
        return (UNKNOWN if unknowns or not coverage_complete else MATCH), [], unknowns, None
    if expect == "window_focused":
        focused = [w for w in candidates if w.get("focused") is True]
        focus_unknowns = [w for w in candidates if not isinstance(w.get("focused"), bool)]
        if focused:
            return MATCH, focused, unknowns + focus_unknowns, None
        if unknowns or focus_unknowns or not coverage_complete:
            return UNKNOWN, candidates, unknowns + focus_unknowns, None
        return NO_MATCH, candidates, [], None
    return UNKNOWN, [], [], f"unsupported_expect:{expect}"


def _recover(_expect: str, verdict: str, probe_error: str | None) -> str:
    if verdict == "verified":
        return "proceed"
    if verdict == "unmet":
        return "retry"
    if verdict == "indeterminate":
        return "replan"
    if probe_error and (
        probe_error.startswith("probe_read_failed")
        or probe_error.startswith("ax_trust_read_failed")
    ):
        return "escalate"
    return "replan"


def _required_evidence(expect: str) -> str:
    if expect == "ax_trusted_is":
        return "ax_trust"
    if expect == "frontmost_app_is":
        return "frontmost_app_identity"
    return "frontmost_app_window_observation"


def _evidence_reasons(expect: str, probe: dict[str, Any]) -> list[str]:
    if expect == "ax_trusted_is":
        return _trust_incomplete_reasons(probe)
    if expect == "frontmost_app_is":
        return _app_incomplete_reasons(probe)
    return _window_evidence_incomplete_reasons(probe)


def _evidence_read_failed(expect: str, probe: dict[str, Any]) -> bool:
    if expect == "ax_trusted_is":
        return bool(_relevant_errors(probe, include_windows=False))
    if expect == "frontmost_app_is":
        return bool(_relevant_errors(probe, include_windows=False))
    return (
        bool(_relevant_errors(probe, include_windows=True))
        or probe.get("windows_read_ok") is not True
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compact", action="store_true", help="Accepted for MCP wrapper parity.")
    parser.add_argument("--expect", choices=sorted(EXPECTS), required=True)
    parser.add_argument("--app", help="Frontmost app name substring.")
    parser.add_argument("--bundle-id", help="Exact frontmost app bundle id (case-insensitive).")
    parser.add_argument("--pid", type=int, help="Frontmost app pid.")
    parser.add_argument("--title", help="Window title substring.")
    parser.add_argument("--role", help="Window AXRole substring.")
    parser.add_argument(
        "--index",
        type=int,
        help="Sampling-local window index; rejected for window_gone and insufficient alone.",
    )
    parser.add_argument(
        "--ax-identifier",
        help="Exact stable AXIdentifier from macos_ax_probe when the app exposes one.",
    )
    parser.add_argument("--state", help="Expected boolean state for ax_trusted_is.")
    parser.add_argument("--max-windows", type=int, default=8)
    parser.add_argument("--jxa-timeout-secs", type=float, default=4.0)
    parser.add_argument("--timeout", type=float, default=4.0, help="Poll timeout seconds.")
    parser.add_argument("--poll-interval", type=float, default=0.3)
    parser.add_argument("--settle", type=float, default=0.0)
    args = parser.parse_args(argv)

    started_wall = time.time()
    started_monotonic = time.monotonic()
    max_windows = max(0, min(args.max_windows, 50))
    jxa_timeout_secs = max(0.25, min(args.jxa_timeout_secs, 10.0))
    timeout = max(0.0, min(args.timeout, 30.0))
    poll_interval = max(0.05, min(args.poll_interval, 5.0))
    settle = max(0.0, min(args.settle, 5.0))
    polls = 0
    last_probe: dict[str, Any] = {}
    last_matches: list[dict[str, Any]] = []
    last_unknowns: list[dict[str, Any]] = []
    last_scope_match: bool | None = None
    last_truth = UNKNOWN
    error = _selector_error(args)
    outcome_kind = "error" if error else "indeterminate"
    proof_complete = False
    verified = False

    if error is None:
        if settle > 0:
            time.sleep(settle)
        deadline = time.monotonic() + timeout
        while True:
            if polls > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                probe_timeout = max(0.01, min(jxa_timeout_secs, remaining))
            else:
                probe_timeout = jxa_timeout_secs
            polls += 1
            probe, probe_error = _probe(
                max_windows,
                probe_timeout,
                include_windows=args.expect != "ax_trusted_is",
            )
            last_probe = probe
            reasons = _evidence_reasons(args.expect, probe)
            if probe_error == "unsupported_platform":
                error = "unsupported_platform"
                outcome_kind = "error"
                break
            if reasons:
                error = (
                    "probe_read_failed"
                    if _evidence_read_failed(args.expect, probe)
                    else "incomplete_evidence"
                )
                outcome_kind = "error" if error == "probe_read_failed" else "indeterminate"
                last_scope_match = None
                last_truth = UNKNOWN
                proof_complete = False
                last_matches = []
                last_unknowns = []
            else:
                if args.expect in WINDOW_EXPECTS:
                    scope_comparison = _compare_app(probe.get("frontmost_app"), args)
                    last_scope_match = scope_comparison == MATCH
                    if scope_comparison != MATCH:
                        error = (
                            "frontmost_app_scope_unknown"
                            if scope_comparison == UNKNOWN
                            else "frontmost_app_scope_mismatch"
                        )
                        outcome_kind = "indeterminate"
                        last_truth = UNKNOWN
                        proof_complete = False
                        last_matches = []
                        last_unknowns = []
                    else:
                        coverage_complete = probe.get("coverage_complete") is True
                        last_truth, last_matches, last_unknowns, eval_error = _evaluate(
                            args,
                            probe,
                            coverage_complete=coverage_complete,
                        )
                        error = eval_error
                        outcome_kind = "error" if eval_error else "indeterminate"
                        proof_complete = last_truth != UNKNOWN and eval_error is None
                else:
                    last_truth, last_matches, last_unknowns, eval_error = _evaluate(
                        args,
                        probe,
                        coverage_complete=probe.get("coverage_complete") is True,
                    )
                    error = eval_error
                    outcome_kind = "error" if eval_error else "indeterminate"
                    proof_complete = last_truth != UNKNOWN and eval_error is None

                if last_truth == MATCH and error is None:
                    verified = True
                    break
                if last_truth == NO_MATCH and error is None:
                    outcome_kind = "unmet"
                elif last_truth == UNKNOWN and error is None:
                    error = "predicate_indeterminate"
                    outcome_kind = "indeterminate"
            if time.monotonic() >= deadline:
                break
            time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))

    held_after_ms = int((time.monotonic() - started_monotonic) * 1000)
    # v0 keeps its original three-value verdict contract. Unknown/incomplete
    # evidence is typed by `error` and `recover`, rather than adding a fourth
    # top-level verdict that older consumers would not recognize.
    verdict = "verified" if verified else ("unmet" if outcome_kind == "unmet" else "error")
    coverage_reasons = last_probe.get("incomplete_reasons")
    if not isinstance(coverage_reasons, list):
        coverage_reasons = [error] if error else []
    payload = {
        "schema": SCHEMA_VERSION,
        "ts": int(started_wall + (time.monotonic() - started_monotonic)),
        "expect": args.expect,
        "selector": _selector(args),
        "scope": {
            "source": "frontmost_app_windows",
            "platform": last_probe.get("platform", {}),
            "max_windows": max_windows,
        },
        "verdict": verdict,
        "recover": _recover(args.expect, verdict, error),
        "change": None,
        "held_after_ms": held_after_ms if verified else None,
        "polls": polls,
        "observed": {
            "probe_status": last_probe.get("status"),
            "permission": last_probe.get("permission"),
            "frontmost_app": last_probe.get("frontmost_app"),
            "count": len(last_matches),
            "matches": last_matches,
            "unknown_count": len(last_unknowns),
            "unknowns": last_unknowns,
            "window_count": last_probe.get("window_count"),
            "source_window_count": last_probe.get("source_window_count"),
            "windows_read_ok": last_probe.get("windows_read_ok"),
            "app_identity_valid": last_probe.get("app_identity_valid"),
            "counts_consistent": last_probe.get("counts_consistent"),
            "limits": last_probe.get("limits"),
            "scope_match": last_scope_match,
            "coverage_complete": last_probe.get("coverage_complete") is True,
            "incomplete_reasons": coverage_reasons,
            "proof_complete": proof_complete,
            "coverage": {
                "complete": last_probe.get("coverage_complete") is True,
                "reasons": coverage_reasons,
            },
            "proof": {
                "complete": proof_complete,
                "truth": last_truth,
                "required_evidence": _required_evidence(args.expect),
            },
            "errors": last_probe.get("errors", []),
        },
        "error": error,
    }
    print(json.dumps(payload, ensure_ascii=False))
    if verdict == "verified":
        return 0
    if verdict == "unmet":
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
