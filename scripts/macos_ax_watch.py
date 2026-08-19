#!/usr/bin/env python3
"""Bounded, read-only short-term event stream over macOS AX observations."""
from __future__ import annotations

import argparse
import json
import platform
import time
from typing import Any, Callable

from macos_ax_probe import _annotate_window_identities, _ax_is_trusted, _frontmost_jxa

SCHEMA_VERSION = "macos_ax_watch/v0"


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
    if before_app != after_app:
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
    if before_app != after_app:
        return events

    old, _, old_ambiguous = _stable_window_partition(before)
    new, _, new_ambiguous = _stable_window_partition(after)
    lifecycle_complete = all(
        sample.get("status") == "ready"
        and sample.get("truncated") is not True
        and not sample.get("errors")
        for sample in (before, after)
    )
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
        old_focused = old[key].get("focused") is True
        new_focused = new[key].get("focused") is True
        if old_focused != new_focused:
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
    errors = [error for error in (trust_error, jxa_error) if error]
    return {
        "sampled_at": time.time(),
        "status": "ready" if trusted and payload and payload.get("frontmost_app") else "degraded",
        "permission": {"ax_trusted": trusted, "prompted": False},
        "frontmost_app": (payload or {}).get("frontmost_app"),
        "windows": windows,
        "source_window_count": source_count,
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
    ready = bool(samples) and all(sample.get("status") == "ready" for sample in samples)
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
            "stable_window_observations": stable_observations,
            "ambiguous_ax_identifier_observations": ambiguous_identifier_observations,
            "sample_local_window_observations": sample_local_observations,
            "event_identity_requirement": "same_process_complete_samples_unique_ax_identifier",
        },
        "events": events,
        "event_count": len(events),
        "dropped_events": dropped_events,
        "verification": {
            "verdict": "verified" if ready and dropped_events == 0 else "incomplete",
            "recover": "proceed" if ready and dropped_events == 0 else "replan",
            "reason": None if ready and dropped_events == 0 else "sample_error_or_event_budget_exhausted",
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
            }
            for sample in samples
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
    payload = watch(
        sample_count=args.samples,
        interval_secs=args.interval,
        max_windows=args.max_windows,
        max_events=args.max_events,
        jxa_timeout_secs=args.jxa_timeout_secs,
        include_samples=args.include_samples,
    )
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2))
    return 0 if payload["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
