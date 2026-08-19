#!/usr/bin/env python3
"""Bounded, read-only short-term event stream over macOS AX observations."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import time
from typing import Any, Callable

from macos_ax_probe import _annotate_window_identities, _ax_is_trusted, _frontmost_jxa

SCHEMA_VERSION = "macos_ax_watch/v0"
STATE_SCHEMA_VERSION = "agent_bridge.desktop_state.v0"
TOKEN_SCHEMA_VERSION = "agent_bridge.desktop_state_token.v0"
SCOPE_PROJECTION = "agent_bridge.desktop_scope_projection.v1"
STATE_PROJECTION = "agent_bridge.desktop_state_projection.v1"
DEFAULT_TOKEN_MAX_AGE_MS = 30_000
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _projection_sha256(projection: str, value: Any) -> str:
    """Hash a canonical projection with explicit domain/length framing."""
    digest = hashlib.sha256()
    for part in (
        b"agent-bridge/desktop-state",
        projection.encode("utf-8"),
        _canonical_json(value),
    ):
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return f"sha256:{digest.hexdigest()}"


def _normalized_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _strict_int(value: Any, *, minimum: int | None = None, maximum: int | None = None) -> bool:
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    return (minimum is None or value >= minimum) and (maximum is None or value <= maximum)


def _normalized_rect(window: dict[str, Any]) -> dict[str, int | float | None] | None:
    rect = window.get("rect")
    if not isinstance(rect, dict):
        return None
    return {
        key: _normalized_number(rect.get(key))
        for key in ("x", "y", "width", "height")
    }


def _normalized_windows(sample: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    raw_windows = [window for window in sample.get("windows") or [] if isinstance(window, dict)]
    identifiers: dict[str, int] = {}
    for window in raw_windows:
        identifier = window.get("ax_identifier")
        if isinstance(identifier, str) and identifier.strip():
            value = identifier.strip()
            identifiers[value] = identifiers.get(value, 0) + 1

    normalized: list[dict[str, Any]] = []
    counts = {"stable": 0, "ambiguous": 0, "sample_local": 0}
    for window in raw_windows:
        identifier = window.get("ax_identifier")
        value = identifier.strip() if isinstance(identifier, str) and identifier.strip() else None
        if value is None:
            identity = {"kind": "sample_local", "stable_across_samples": False}
            counts["sample_local"] += 1
        elif identifiers[value] == 1:
            identity = {
                "kind": "ax_identifier",
                "value": value,
                "stable_across_samples": True,
                "unique_in_sample": True,
            }
            counts["stable"] += 1
        else:
            identity = {
                "kind": "ambiguous_ax_identifier",
                "value": value,
                "stable_across_samples": False,
                "unique_in_sample": False,
            }
            counts["ambiguous"] += 1
        normalized.append(
            {
                "identity": identity,
                "title": window.get("title") if isinstance(window.get("title"), str) else None,
                "role": window.get("role") if isinstance(window.get("role"), str) else None,
                "subrole": window.get("subrole") if isinstance(window.get("subrole"), str) else None,
                "focused": window.get("focused") if isinstance(window.get("focused"), bool) else None,
                "rect": _normalized_rect(window),
            }
        )
    normalized.sort(key=_canonical_json)
    return normalized, counts


def _frontmost_app_identity_valid(sample: dict[str, Any]) -> bool:
    app = sample.get("frontmost_app")
    pid = app.get("pid") if isinstance(app, dict) else None
    name = app.get("name") if isinstance(app, dict) else None
    bundle_id = app.get("bundle_id") if isinstance(app, dict) else None
    return bool(
        isinstance(pid, int)
        and not isinstance(pid, bool)
        and pid > 0
        and (
            (isinstance(name, str) and bool(name.strip()))
            or (isinstance(bundle_id, str) and bool(bundle_id.strip()))
        )
    )


def _sample_app_observation_complete(sample: dict[str, Any]) -> bool:
    permission = sample.get("permission") or {}
    return bool(
        sample.get("status") == "ready"
        and isinstance(permission, dict)
        and permission.get("ax_trusted") is True
        and _frontmost_app_identity_valid(sample)
        and not sample.get("errors")
    )


def _sample_incomplete_reasons(sample: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if sample.get("status") != "ready":
        reasons.append("sample_not_ready")
    permission = sample.get("permission") or {}
    if not isinstance(permission, dict) or permission.get("ax_trusted") is not True:
        reasons.append("ax_not_trusted")
    if not _frontmost_app_identity_valid(sample):
        reasons.append("frontmost_app_identity_invalid")
    if sample.get("errors"):
        reasons.append("sample_errors")
    if sample.get("truncated") is True:
        reasons.append("window_enumeration_truncated")
    if sample.get("windows_read_ok") is not True:
        reasons.append("window_enumeration_unconfirmed")
    windows = sample.get("windows")
    if not isinstance(windows, list) or any(not isinstance(window, dict) for window in windows):
        reasons.append("windows_invalid")
    source_count = sample.get("source_window_count")
    if not _strict_int(source_count, minimum=0):
        reasons.append("source_window_count_missing")
    elif isinstance(windows, list) and source_count != len(windows):
        reasons.append("window_count_mismatch")
    return list(dict.fromkeys(reasons))


def desktop_state(sample: dict[str, Any], *, token_max_age_ms: int) -> dict[str, Any]:
    """Build an order-independent semantic state and a short-lived comparison token."""
    app = sample.get("frontmost_app") if isinstance(sample.get("frontmost_app"), dict) else {}
    scope_projection = {
        "platform": "macos",
        "frontmost_process": {
            "pid": app.get("pid") if isinstance(app.get("pid"), int) else None,
            "bundle_id": app.get("bundle_id") if isinstance(app.get("bundle_id"), str) else None,
            "name": app.get("name") if isinstance(app.get("name"), str) else None,
        },
    }
    windows, identity_counts = _normalized_windows(sample)
    state_projection = {
        "frontmost_application": {
            "name": app.get("name") if isinstance(app.get("name"), str) else None,
            "role": app.get("role") if isinstance(app.get("role"), str) else None,
        },
        "windows": windows,
        "window_count": len(windows),
    }
    reasons = _sample_incomplete_reasons(sample)
    captured_at_unix_ms = int(float(sample.get("sampled_at") or time.time()) * 1000)
    scope_sha256 = _projection_sha256(SCOPE_PROJECTION, scope_projection)
    state_sha256 = _projection_sha256(STATE_PROJECTION, state_projection)
    complete = not reasons
    token = {
        "schema": TOKEN_SCHEMA_VERSION,
        "captured_at_unix_ms": captured_at_unix_ms,
        "max_age_ms": token_max_age_ms,
        "coverage_complete": complete,
        "scope_projection": SCOPE_PROJECTION,
        "state_projection": STATE_PROJECTION,
        "scope_sha256": scope_sha256,
        "state_sha256": state_sha256,
    }
    return {
        "schema": STATE_SCHEMA_VERSION,
        "captured_at_unix_ms": captured_at_unix_ms,
        "scope": scope_projection,
        "coverage": {
            "complete": complete,
            "truncated": sample.get("truncated") is True,
            "errors": list(sample.get("errors") or []),
            "incomplete_reasons": reasons,
            "sources": ["ax", "system_events"],
            "enumerated_window_count": len(windows),
            "source_window_count": sample.get("source_window_count"),
            "stable_window_count": identity_counts["stable"],
            "ambiguous_ax_identifier_count": identity_counts["ambiguous"],
            "sample_local_window_count": identity_counts["sample_local"],
            "sample_local_semantics_in_state_hash": True,
            "object_continuity_claimed_for_sample_local": False,
        },
        "state": state_projection,
        "fingerprints": {
            "scope": {
                "algorithm": "sha256",
                "projection": SCOPE_PROJECTION,
                "value": scope_sha256,
            },
            "state": {
                "algorithm": "sha256",
                "projection": STATE_PROJECTION,
                "value": state_sha256,
            },
        },
        "token": token,
    }


def _decision(verdict: str, relation: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "verdict": verdict,
        "relation": relation,
        "recover": "proceed" if verdict == "unchanged" else "replan",
        "reason": reason,
        **extra,
    }


def compare_state_sequence(states: list[dict[str, Any]]) -> dict[str, Any]:
    if not states or any(not state["coverage"]["complete"] for state in states):
        return _decision(
            "indeterminate", "incomparable", "one_or_more_samples_incomplete",
            changed_transition_count=None,
        )
    scope_changes = 0
    state_changes = 0
    for before, after in zip(states, states[1:]):
        if before["token"]["scope_sha256"] != after["token"]["scope_sha256"]:
            scope_changes += 1
        elif before["token"]["state_sha256"] != after["token"]["state_sha256"]:
            state_changes += 1
    if scope_changes:
        return _decision(
            "scope_changed", "scope_changed", "frontmost_process_changed_during_watch",
            changed_transition_count=scope_changes + state_changes,
            scope_changed_transition_count=scope_changes,
            state_changed_transition_count=state_changes,
        )
    if state_changes:
        return _decision(
            "drifted", "same_scope", "semantic_state_changed_during_watch",
            changed_transition_count=state_changes,
            scope_changed_transition_count=0,
            state_changed_transition_count=state_changes,
        )
    return _decision(
        "unchanged", "same_scope", "semantic_state_stable_during_watch",
        changed_transition_count=0,
        scope_changed_transition_count=0,
        state_changed_transition_count=0,
    )


def compare_before_token(
    before_token: dict[str, Any] | None,
    current_state: dict[str, Any],
    *,
    now_ms: int,
    max_token_age_ms: int,
) -> dict[str, Any]:
    if before_token is None:
        return {
            "supplied": False,
            "verdict": "not_compared",
            "relation": "unknown",
            "recover": None,
            "reason": "before_state_token_not_supplied",
        }
    base = {"supplied": True}
    if not isinstance(before_token, dict):
        return {**base, **_decision("indeterminate", "incomparable", "before_token_not_object")}
    required = {
        "schema": TOKEN_SCHEMA_VERSION,
        "scope_projection": SCOPE_PROJECTION,
        "state_projection": STATE_PROJECTION,
    }
    if any(before_token.get(key) != value for key, value in required.items()):
        return {**base, **_decision("indeterminate", "incomparable", "before_token_contract_mismatch")}
    if before_token.get("coverage_complete") is not True:
        return {**base, **_decision("indeterminate", "incomparable", "before_token_incomplete")}
    if not all(
        isinstance(before_token.get(key), str) and _SHA256_RE.fullmatch(before_token[key])
        for key in ("scope_sha256", "state_sha256")
    ):
        return {**base, **_decision("indeterminate", "incomparable", "before_token_hash_invalid")}
    captured_at = before_token.get("captured_at_unix_ms")
    if not _strict_int(captured_at, minimum=1):
        return {**base, **_decision("indeterminate", "incomparable", "before_token_time_invalid")}
    token_age_limit = before_token.get("max_age_ms")
    if not _strict_int(token_age_limit, minimum=1_000, maximum=300_000):
        return {**base, **_decision("indeterminate", "incomparable", "before_token_age_limit_invalid")}
    age_ms = now_ms - captured_at
    effective_max_age_ms = min(max_token_age_ms, token_age_limit)
    if age_ms < 0:
        return {
            **base,
            **_decision("indeterminate", "incomparable", "before_token_from_future"),
            "age_ms": age_ms,
            "effective_max_age_ms": effective_max_age_ms,
        }
    if age_ms > effective_max_age_ms:
        return {
            **base,
            **_decision("indeterminate", "incomparable", "before_token_stale"),
            "age_ms": age_ms,
            "effective_max_age_ms": effective_max_age_ms,
        }
    if current_state["coverage"]["complete"] is not True:
        return {
            **base,
            **_decision("indeterminate", "incomparable", "current_state_incomplete"),
            "age_ms": age_ms,
            "effective_max_age_ms": effective_max_age_ms,
        }
    current = current_state["token"]
    if before_token["scope_sha256"] != current["scope_sha256"]:
        verdict = _decision("scope_changed", "scope_changed", "frontmost_process_scope_changed")
    elif before_token["state_sha256"] != current["state_sha256"]:
        verdict = _decision("drifted", "same_scope", "semantic_state_changed")
    else:
        verdict = _decision("unchanged", "same_scope", "semantic_state_unchanged")
    return {
        **base,
        **verdict,
        "age_ms": age_ms,
        "effective_max_age_ms": effective_max_age_ms,
    }


def _slug(value: str) -> str:
    output: list[str] = []
    last_dash = False
    for character in value:
        if character.isascii() and character.isalnum():
            output.append(character.lower())
            last_dash = False
        elif output and not last_dash:
            output.append("-")
            last_dash = True
    return "".join(output).rstrip("-") or "unknown"


def _stable_window_partition(
    sample: dict[str, Any],
) -> tuple[dict[tuple[int, str], dict[str, Any]], int, set[tuple[int, str]]]:
    app = sample.get("frontmost_app") or {}
    pid = app.get("pid")
    if not isinstance(pid, int):
        return {}, 0, set()
    candidates: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for window in sample.get("windows") or []:
        identity = window.get("identity") if isinstance(window, dict) else None
        if not isinstance(identity, dict) or identity.get("stable_across_samples") is not True:
            continue
        value = identity.get("value")
        if isinstance(value, str) and value:
            candidates.setdefault((pid, value), []).append(window)
    unique = {key: values[0] for key, values in candidates.items() if len(values) == 1}
    ambiguous = sum(len(values) for values in candidates.values() if len(values) > 1)
    ambiguous_keys = {key for key, values in candidates.items() if len(values) > 1}
    return unique, ambiguous, ambiguous_keys


def _stable_windows(sample: dict[str, Any]) -> dict[tuple[int, str], dict[str, Any]]:
    return _stable_window_partition(sample)[0]


def _app_identity(sample: dict[str, Any]) -> dict[str, Any] | None:
    app = sample.get("frontmost_app")
    if not isinstance(app, dict):
        return None
    return {key: app.get(key) for key in ("name", "pid", "bundle_id")}


def diff_samples(before: dict[str, Any], after: dict[str, Any], observed_at: float) -> list[dict[str, Any]]:
    """Return only claims supported by stable identity or explicit app identity."""
    events: list[dict[str, Any]] = []
    before_app = _app_identity(before)
    after_app = _app_identity(after)
    app_observations_complete = all(
        _sample_app_observation_complete(sample) for sample in (before, after)
    )
    if app_observations_complete and before_app != after_app:
        events.append(
            {
                "type": "frontmost_app_changed",
                "observed_at": observed_at,
                "before": before_app,
                "after": after_app,
                "identity_basis": "process_identity",
            }
        )

    # The probe is intentionally scoped to the frontmost application. When the
    # app changes, absence means "left observation scope", not "window closed".
    # Lifecycle/focus claims therefore require the same process on both sides.
    if not app_observations_complete or before_app != after_app:
        return events

    old, _, old_ambiguous = _stable_window_partition(before)
    new, _, new_ambiguous = _stable_window_partition(after)
    lifecycle_complete = all(not _sample_incomplete_reasons(sample) for sample in (before, after))
    ambiguous = old_ambiguous | new_ambiguous
    disappeared = old.keys() - new.keys() - ambiguous if lifecycle_complete else set()
    appeared = new.keys() - old.keys() - ambiguous if lifecycle_complete else set()
    for key in sorted(disappeared):
        events.append(
            {
                "type": "window_disappeared",
                "observed_at": observed_at,
                "object_id": f"desktop:macos:window:{key[0]}:ax:{_slug(key[1])}",
                "window": old[key],
                "identity_basis": "ax_identifier",
            }
        )
    for key in sorted(appeared):
        events.append(
            {
                "type": "window_appeared",
                "observed_at": observed_at,
                "object_id": f"desktop:macos:window:{key[0]}:ax:{_slug(key[1])}",
                "window": new[key],
                "identity_basis": "ax_identifier",
            }
        )
    for key in sorted(old.keys() & new.keys()):
        old_focused = old[key].get("focused")
        new_focused = new[key].get("focused")
        if (
            lifecycle_complete
            and isinstance(old_focused, bool)
            and isinstance(new_focused, bool)
            and old_focused != new_focused
        ):
            events.append(
                {
                    "type": "window_focus_changed",
                    "observed_at": observed_at,
                    "object_id": f"desktop:macos:window:{key[0]}:ax:{_slug(key[1])}",
                    "before": old_focused,
                    "after": new_focused,
                    "identity_basis": "ax_identifier",
                }
            )
    return events


def _sample(max_windows: int, jxa_timeout_secs: float) -> dict[str, Any]:
    trusted, trust_error = _ax_is_trusted()
    payload, jxa_error = (None, None)
    if trusted:
        payload, jxa_error = _frontmost_jxa(max_windows, jxa_timeout_secs)
    windows = _annotate_window_identities((payload or {}).get("windows", []))
    source_count = (payload or {}).get("window_count")
    windows_read_ok = (payload or {}).get("windows_read_ok")
    errors = [error for error in (trust_error, jxa_error) if error]
    if payload and windows_read_ok is not True:
        errors.append("window enumeration failed")
    return {
        "sampled_at": time.time(),
        "status": "ready" if trusted and payload and payload.get("frontmost_app") and windows_read_ok is True else "degraded",
        "permission": {"ax_trusted": trusted, "prompted": False},
        "frontmost_app": (payload or {}).get("frontmost_app"),
        "windows": windows,
        "source_window_count": source_count,
        "windows_read_ok": windows_read_ok,
        "truncated": bool(source_count is not None and len(windows) < source_count),
        "errors": errors,
    }


def watch(
    *,
    sample_count: int,
    interval_secs: float,
    max_windows: int,
    max_events: int,
    jxa_timeout_secs: float,
    include_samples: bool,
    before_token: dict[str, Any] | None = None,
    max_token_age_ms: int = DEFAULT_TOKEN_MAX_AGE_MS,
    sampler: Callable[[], dict[str, Any]] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    take_sample = sampler or (lambda: _sample(max_windows, jxa_timeout_secs))
    samples: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    dropped_events = 0
    for index in range(sample_count):
        current = take_sample()
        samples.append(current)
        if index:
            delta = diff_samples(samples[index - 1], current, current.get("sampled_at", time.time()))
            room = max(0, max_events - len(events))
            events.extend(delta[:room])
            dropped_events += max(0, len(delta) - room)
        if index + 1 < sample_count:
            sleeper(interval_secs)

    stable_observations = sum(len(_stable_windows(sample)) for sample in samples)
    ambiguous_identifier_observations = sum(
        _stable_window_partition(sample)[1] for sample in samples
    )
    sample_local_observations = sum(
        1
        for sample in samples
        for window in sample.get("windows") or []
        if (window.get("identity") or {}).get("stable_across_samples") is False
    )
    states = [desktop_state(sample, token_max_age_ms=max_token_age_ms) for sample in samples]
    ready = bool(states) and all(state["coverage"]["complete"] for state in states)
    within_watch = compare_state_sequence(states)
    against_baseline = compare_before_token(
        before_token,
        states[-1],
        now_ms=states[-1]["captured_at_unix_ms"],
        max_token_age_ms=max_token_age_ms,
    )
    if dropped_events:
        decision = _decision("indeterminate", "incomparable", "event_budget_exhausted")
    elif within_watch["verdict"] != "unchanged":
        decision = dict(within_watch)
    elif against_baseline["supplied"]:
        decision = {key: value for key, value in against_baseline.items() if key != "supplied"}
    else:
        decision = dict(within_watch)
    evidence_verification = {
        "verdict": "verified" if ready and dropped_events == 0 else "incomplete",
        "reason": None if ready and dropped_events == 0 else "sample_error_or_event_budget_exhausted",
    }
    decision_verdict = decision["verdict"]
    result: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "captured_at": time.time(),
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "read_only": True,
        "status": "ready" if ready else "degraded",
        "limits": {
            "sample_count": sample_count,
            "interval_secs": interval_secs,
            "max_windows_per_sample": max_windows,
            "max_events": max_events,
            "jxa_timeout_secs": jxa_timeout_secs,
        },
        "coverage": {
            "samples_completed": len(samples),
            "complete_samples": sum(state["coverage"]["complete"] for state in states),
            "incomplete_samples": sum(not state["coverage"]["complete"] for state in states),
            "stable_window_observations": stable_observations,
            "ambiguous_ax_identifier_observations": ambiguous_identifier_observations,
            "sample_local_window_observations": sample_local_observations,
            "event_identity_requirement": "same_process_complete_samples_unique_ax_identifier",
        },
        "events": events,
        "event_count": len(events),
        "dropped_events": dropped_events,
        "current_state": states[-1],
        "drift": {
            "comparison_scope": "frontmost_process_and_order_independent_window_semantics",
            "sample_local_identity_limit": "semantic_change_only_no_object_continuity_claim",
            "within_watch": within_watch,
            "against_baseline": against_baseline,
            "decision": decision,
        },
        "evidence_verification": evidence_verification,
        "verification": {
            "verdict": (
                "verified"
                if decision_verdict == "unchanged"
                else "incomplete"
                if decision_verdict == "indeterminate"
                else "not_verified"
            ),
            "recover": decision["recover"],
            "change": decision_verdict,
            "reason": decision["reason"],
        },
    }
    if include_samples:
        result["samples"] = samples
    else:
        result["sample_summaries"] = [
            {
                "sampled_at": sample.get("sampled_at"),
                "status": sample.get("status"),
                "frontmost_app": sample.get("frontmost_app"),
                "window_count": len(sample.get("windows") or []),
                "stable_window_count": len(_stable_windows(sample)),
                "ambiguous_ax_identifier_count": _stable_window_partition(sample)[1],
                "truncated": sample.get("truncated"),
                "errors": sample.get("errors"),
                "coverage_complete": state["coverage"]["complete"],
                "scope_sha256": state["token"]["scope_sha256"],
                "state_sha256": state["token"]["state_sha256"],
            }
            for sample, state in zip(samples, states)
        ]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval", type=float, default=0.3)
    parser.add_argument("--max-windows", type=int, default=8)
    parser.add_argument("--max-events", type=int, default=32)
    parser.add_argument("--jxa-timeout-secs", type=float, default=4.0)
    parser.add_argument("--include-samples", action="store_true")
    parser.add_argument(
        "--before-token-json",
        help="Optional exact current_state.token JSON from an earlier complete watch.",
    )
    parser.add_argument("--max-token-age-ms", type=int, default=DEFAULT_TOKEN_MAX_AGE_MS)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    if not 2 <= args.samples <= 10:
        parser.error("--samples must be between 2 and 10")
    if not 0.05 <= args.interval <= 5.0:
        parser.error("--interval must be between 0.05 and 5.0")
    if not 0 <= args.max_windows <= 50:
        parser.error("--max-windows must be between 0 and 50")
    if not 1 <= args.max_events <= 100:
        parser.error("--max-events must be between 1 and 100")
    if not 0.25 <= args.jxa_timeout_secs <= 10.0:
        parser.error("--jxa-timeout-secs must be between 0.25 and 10.0")
    if not 1_000 <= args.max_token_age_ms <= 300_000:
        parser.error("--max-token-age-ms must be between 1000 and 300000")
    before_token = None
    if args.before_token_json:
        try:
            before_token = json.loads(args.before_token_json)
        except json.JSONDecodeError as exc:
            parser.error(f"--before-token-json is not valid JSON: {exc}")
    payload = watch(
        sample_count=args.samples,
        interval_secs=args.interval,
        max_windows=args.max_windows,
        max_events=args.max_events,
        jxa_timeout_secs=args.jxa_timeout_secs,
        include_samples=args.include_samples,
        before_token=before_token,
        max_token_age_ms=args.max_token_age_ms,
    )
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2))
    return 0 if payload["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
