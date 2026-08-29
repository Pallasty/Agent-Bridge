#!/usr/bin/env python3
"""Record and reduce privacy-minimal Agent-Bridge benefit dogfood events."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import stat
import time
import uuid
from pathlib import Path
from typing import Any


EVENT_SCHEMA = "agent_bridge.benefit_dogfood_event.v1"
REPORT_SCHEMA = "agent_bridge.benefit_dogfood_report.v1"
AGGREGATE_SCHEMA = "agent_bridge.benefit_dogfood_aggregate.v1"
EVENT_TYPES = ("continuity", "avatar", "embodied", "voice")
RECALL_OUTCOMES = ("used", "no_recall", "missing", "stale", "harmful")
AVATAR_RATINGS = ("helpful", "neutral", "distracting")
VOICE_WORKER_STATES = ("warm", "cold")
CONTINUITY_TARGET = 20
AVATAR_TARGET = 20
EMBODIED_DOMAIN_TARGET = 2
VOICE_WARM_TARGET = 2
CONTINUITY_SUCCESS_TARGET = 0.80
AVATAR_HELPFUL_TARGET = 0.60
AVATAR_DISTRACTING_LIMIT = 0.10
EMBODIED_REDUCTION_TARGET = 0.30
VOICE_P50_LIMIT_MS = 2_000
VOICE_P95_LIMIT_MS = 5_000
MAX_LEDGER_BYTES = 16_000_000
MAX_RECEIPT_BYTES = 4_000_000
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMON_KEYS = {
    "schema",
    "event_id",
    "event_type",
    "observed_at",
    "subject_sha256",
    "real_task_attested",
    "metrics",
}
METRIC_KEYS = {
    "continuity": {
        "recall_outcome",
        "owner_restatements",
        "task_completed",
        "recovery_seconds",
    },
    "avatar": {
        "owner_rating",
        "completed",
        "elapsed_ms",
        "heartbeat_failures",
        "sidecar_read_failures",
        "transition_count",
        "peak_rss_bytes",
        "physical_display_confirmed",
    },
    "embodied": {
        "domain_sha256",
        "baseline_owner_restatements",
        "trial_owner_restatements",
        "baseline_manual_interventions",
        "trial_manual_interventions",
        "baseline_agent_calls",
        "trial_agent_calls",
        "duplicate_actions",
        "safety_failure",
        "cleanup_verified",
    },
    "voice": {
        "worker_state",
        "session_average_latency_ms",
        "invocation_count",
        "utterance_count",
        "failure_count",
        "audible_confirmed",
        "continuous_listening",
    },
}


class DogfoodError(Exception):
    """Structured failure that never includes retained task content."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def resolve_log_path(explicit: Path | None) -> Path:
    """Resolve one deliberate ledger path without guessing a platform fallback."""

    try:
        if explicit is not None:
            path = explicit.expanduser()
        else:
            state_dir = os.environ.get("AGENT_BRIDGE_STATE_DIR")
            if not state_dir:
                raise DogfoodError("LOG_PATH_REQUIRED")
            state_root = Path(state_dir).expanduser()
            if not state_root.is_absolute():
                raise DogfoodError("LOG_PATH_NOT_ABSOLUTE")
            if state_root.anchor != os.sep or ".." in state_root.parts:
                raise DogfoodError("LOG_PATH_NOT_NORMALIZED")
            if state_root.resolve(strict=False) == Path(os.sep):
                raise DogfoodError("LOG_PATH_TOO_BROAD")
            path = state_root / "dogfood" / "benefit-v1.jsonl"
    except (OSError, RuntimeError) as exc:
        raise DogfoodError("INVALID_LOG_PATH") from exc
    if not path.is_absolute():
        raise DogfoodError("LOG_PATH_NOT_ABSOLUTE")
    if path.anchor != os.sep or ".." in path.parts:
        raise DogfoodError("LOG_PATH_NOT_NORMALIZED")
    return path


def _exact_keys(value: Any, expected: set[str], code: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise DogfoodError(code)
    return value


def _require_bool(value: Any, code: str) -> bool:
    if type(value) is not bool:
        raise DogfoodError(code)
    return value


def _require_count(
    value: Any,
    code: str,
    *,
    maximum: int = 1_000_000_000_000,
) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise DogfoodError(code)
    return value


def _require_optional_count(
    value: Any,
    code: str,
    *,
    maximum: int = 1_000_000_000_000,
) -> int | None:
    if value is None:
        return None
    return _require_count(value, code, maximum=maximum)


def _require_sha256(value: Any, code: str) -> str:
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        raise DogfoodError(code)
    return value


def validate_event(value: Any) -> dict[str, Any]:
    row = _exact_keys(value, COMMON_KEYS, "INVALID_EVENT_KEYS")
    if row["schema"] != EVENT_SCHEMA:
        raise DogfoodError("INVALID_EVENT_SCHEMA")
    if type(row["event_id"]) is not str or UUID_RE.fullmatch(row["event_id"]) is None:
        raise DogfoodError("INVALID_EVENT_ID")
    if row["event_type"] not in EVENT_TYPES:
        raise DogfoodError("INVALID_EVENT_TYPE")
    _require_count(row["observed_at"], "INVALID_OBSERVED_AT", maximum=2**63 - 1)
    if row["observed_at"] == 0:
        raise DogfoodError("INVALID_OBSERVED_AT")
    _require_sha256(row["subject_sha256"], "INVALID_SUBJECT_SHA256")
    if row["real_task_attested"] is not True:
        raise DogfoodError("REAL_TASK_ATTESTATION_REQUIRED")

    event_type = row["event_type"]
    metrics = _exact_keys(
        row["metrics"], METRIC_KEYS[event_type], "INVALID_METRIC_KEYS"
    )
    if event_type == "continuity":
        if metrics["recall_outcome"] not in RECALL_OUTCOMES:
            raise DogfoodError("INVALID_RECALL_OUTCOME")
        _require_count(
            metrics["owner_restatements"],
            "INVALID_OWNER_RESTATEMENTS",
            maximum=20,
        )
        _require_bool(metrics["task_completed"], "INVALID_TASK_COMPLETED")
        _require_optional_count(
            metrics["recovery_seconds"],
            "INVALID_RECOVERY_SECONDS",
            maximum=86_400,
        )
    elif event_type == "avatar":
        if metrics["owner_rating"] not in AVATAR_RATINGS:
            raise DogfoodError("INVALID_AVATAR_RATING")
        for key in ("completed", "physical_display_confirmed"):
            _require_bool(metrics[key], f"INVALID_AVATAR_{key.upper()}")
        for key in (
            "elapsed_ms",
            "heartbeat_failures",
            "sidecar_read_failures",
            "transition_count",
        ):
            _require_count(metrics[key], f"INVALID_AVATAR_{key.upper()}")
        _require_optional_count(
            metrics["peak_rss_bytes"], "INVALID_AVATAR_PEAK_RSS_BYTES"
        )
    elif event_type == "embodied":
        _require_sha256(metrics["domain_sha256"], "INVALID_DOMAIN_SHA256")
        for key in (
            "baseline_owner_restatements",
            "trial_owner_restatements",
            "baseline_manual_interventions",
            "trial_manual_interventions",
            "baseline_agent_calls",
            "trial_agent_calls",
            "duplicate_actions",
        ):
            _require_count(metrics[key], f"INVALID_EMBODIED_{key.upper()}")
        for key in ("safety_failure", "cleanup_verified"):
            _require_bool(metrics[key], f"INVALID_EMBODIED_{key.upper()}")
    else:
        if metrics["worker_state"] not in VOICE_WORKER_STATES:
            raise DogfoodError("INVALID_VOICE_WORKER_STATE")
        _require_optional_count(
            metrics["session_average_latency_ms"],
            "INVALID_VOICE_LATENCY_MS",
            maximum=86_400_000,
        )
        for key in ("invocation_count", "utterance_count", "failure_count"):
            _require_count(metrics[key], f"INVALID_VOICE_{key.upper()}")
        for key in ("audible_confirmed", "continuous_listening"):
            _require_bool(metrics[key], f"INVALID_VOICE_{key.upper()}")
        if metrics["continuous_listening"]:
            raise DogfoodError("CONTINUOUS_LISTENING_FORBIDDEN")
        if (
            metrics["invocation_count"] == 0
            and metrics["session_average_latency_ms"] is not None
        ):
            raise DogfoodError("VOICE_LATENCY_WITHOUT_INVOCATION")
        if metrics["utterance_count"] > metrics["invocation_count"]:
            raise DogfoodError("VOICE_UTTERANCES_EXCEED_INVOCATIONS")
    return row


def _open_flags(write: bool) -> int:
    if not hasattr(os, "O_NOFOLLOW"):
        raise DogfoodError("NOFOLLOW_UNAVAILABLE")
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND if write else os.O_RDONLY
    return flags | os.O_NOFOLLOW


def _verify_ledger_file(fd: int) -> None:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise DogfoodError("UNSAFE_LEDGER_FILE")
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise DogfoodError("INSECURE_LEDGER_PERMISSIONS")
    if info.st_size > MAX_LEDGER_BYTES:
        raise DogfoodError("LEDGER_TOO_LARGE")


def _prepare_parent(path: Path) -> None:
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.parent.is_symlink():
            raise DogfoodError("UNSAFE_LEDGER_DIRECTORY")
        if stat.S_IMODE(path.parent.stat().st_mode) != 0o700:
            raise DogfoodError("INSECURE_LEDGER_DIRECTORY_PERMISSIONS")
    except DogfoodError:
        raise
    except OSError as exc:
        raise DogfoodError("LEDGER_DIRECTORY_FAILED") from exc


def _read_exact(fd: int, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = os.read(fd, remaining)
        if not chunk:
            raise DogfoodError("LEDGER_SHORT_READ")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise DogfoodError("LEDGER_WRITE_FAILED")
        offset += written


def _decode_rows(raw: bytes) -> list[dict[str, Any]]:
    if not raw:
        return []
    if not raw.endswith(b"\n"):
        raise DogfoodError("UNTERMINATED_LEDGER_ROW")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise DogfoodError("INVALID_LEDGER_ENCODING") from exc
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line:
            raise DogfoodError("INVALID_EMPTY_ROW")
        try:
            rows.append(validate_event(json.loads(line)))
        except json.JSONDecodeError as exc:
            raise DogfoodError("INVALID_LEDGER_JSON") from exc
    if len({row["event_id"] for row in rows}) != len(rows):
        raise DogfoodError("DUPLICATE_EVENT_ID_IN_LEDGER")
    identities = {(row["event_type"], row["subject_sha256"]) for row in rows}
    if len(identities) != len(rows):
        raise DogfoodError("DUPLICATE_EVENT_SUBJECT_IN_LEDGER")
    return rows


def read_ledger(path: Path) -> tuple[list[dict[str, Any]], bytes]:
    try:
        fd = os.open(path, _open_flags(write=False))
    except FileNotFoundError:
        return [], b""
    except OSError as exc:
        raise DogfoodError("LEDGER_OPEN_FAILED") from exc
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        _verify_ledger_file(fd)
        raw = _read_exact(fd, os.fstat(fd).st_size)
        return _decode_rows(raw), raw
    except DogfoodError:
        raise
    except OSError as exc:
        raise DogfoodError("LEDGER_READ_FAILED") from exc
    finally:
        os.close(fd)


def read_rows(path: Path) -> list[dict[str, Any]]:
    return read_ledger(path)[0]


def record_event(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    validate_event(row)
    _prepare_parent(path)
    try:
        fd = os.open(path, _open_flags(write=True), 0o600)
    except OSError as exc:
        raise DogfoodError("LEDGER_OPEN_FAILED") from exc
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        _verify_ledger_file(fd)
        original_size = os.fstat(fd).st_size
        os.lseek(fd, 0, os.SEEK_SET)
        rows = _decode_rows(_read_exact(fd, original_size))
        if any(row["event_id"] == existing["event_id"] for existing in rows):
            raise DogfoodError("EVENT_ID_ALREADY_RECORDED")
        if any(
            row["event_type"] == existing["event_type"]
            and row["subject_sha256"] == existing["subject_sha256"]
            for existing in rows
        ):
            raise DogfoodError("EVENT_SUBJECT_ALREADY_RECORDED")
        payload = (
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        )
        if original_size + len(payload) > MAX_LEDGER_BYTES:
            raise DogfoodError("LEDGER_TOO_LARGE")
        try:
            _write_all(fd, payload)
            os.fsync(fd)
        except (DogfoodError, OSError) as exc:
            try:
                os.ftruncate(fd, original_size)
                os.fsync(fd)
            except OSError as rollback_exc:
                raise DogfoodError("LEDGER_WRITE_UNCERTAIN") from rollback_exc
            raise DogfoodError("LEDGER_WRITE_FAILED") from exc
        return {
            "status": "RECORDED",
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "event_count": len(rows) + 1,
        }
    except DogfoodError:
        raise
    except OSError as exc:
        raise DogfoodError("LEDGER_IO_FAILED") from exc
    finally:
        os.close(fd)


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _average(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _percentile(values: list[int], quantile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def _gate(ready: bool, passed: bool) -> str:
    if not ready:
        return "COLLECTING"
    return "PASS" if passed else "FAIL"


def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        validate_event(row)
    if len({row["event_id"] for row in rows}) != len(rows):
        raise DogfoodError("DUPLICATE_EVENT_ID_IN_LEDGER")
    if len({(row["event_type"], row["subject_sha256"]) for row in rows}) != len(
        rows
    ):
        raise DogfoodError("DUPLICATE_EVENT_SUBJECT_IN_LEDGER")

    continuity = [row["metrics"] for row in rows if row["event_type"] == "continuity"]
    continuity_successes = sum(
        metric["owner_restatements"] == 0
        and metric["recall_outcome"] not in ("stale", "harmful")
        and metric["task_completed"]
        for metric in continuity
    )
    harmful_count = sum(metric["recall_outcome"] == "harmful" for metric in continuity)
    stale_count = sum(metric["recall_outcome"] == "stale" for metric in continuity)
    continuity_rate = _rate(continuity_successes, len(continuity))
    continuity_ready = len(continuity) >= CONTINUITY_TARGET
    continuity_passed = (
        continuity_ready
        and continuity_rate is not None
        and continuity_rate >= CONTINUITY_SUCCESS_TARGET
        and harmful_count == 0
    )
    recovery_values = [
        metric["recovery_seconds"]
        for metric in continuity
        if metric["recovery_seconds"] is not None
    ]

    avatar = [row["metrics"] for row in rows if row["event_type"] == "avatar"]
    helpful_count = sum(metric["owner_rating"] == "helpful" for metric in avatar)
    distracting_count = sum(
        metric["owner_rating"] == "distracting" for metric in avatar
    )
    avatar_operational_failures = sum(
        not metric["completed"]
        or metric["heartbeat_failures"] > 0
        or metric["sidecar_read_failures"] > 0
        for metric in avatar
    )
    helpful_rate = _rate(helpful_count, len(avatar))
    distracting_rate = _rate(distracting_count, len(avatar))
    avatar_ready = len(avatar) >= AVATAR_TARGET
    avatar_passed = (
        avatar_ready
        and helpful_rate is not None
        and helpful_rate >= AVATAR_HELPFUL_TARGET
        and distracting_rate is not None
        and distracting_rate <= AVATAR_DISTRACTING_LIMIT
        and avatar_operational_failures == 0
    )

    embodied = [row["metrics"] for row in rows if row["event_type"] == "embodied"]
    domains = {metric["domain_sha256"] for metric in embodied}
    burden_fields = (
        ("baseline_owner_restatements", "trial_owner_restatements"),
        ("baseline_manual_interventions", "trial_manual_interventions"),
        ("baseline_agent_calls", "trial_agent_calls"),
    )
    baseline_burden = sum(
        metric[baseline] for metric in embodied for baseline, _trial in burden_fields
    )
    trial_burden = sum(
        metric[trial] for metric in embodied for _baseline, trial in burden_fields
    )
    burden_reduction_rate = (
        round((baseline_burden - trial_burden) / baseline_burden, 4)
        if baseline_burden
        else None
    )
    burden_regressions = sum(
        any(metric[trial] > metric[baseline] for baseline, trial in burden_fields)
        for metric in embodied
    )
    duplicate_actions = sum(metric["duplicate_actions"] for metric in embodied)
    embodied_safety_failures = sum(metric["safety_failure"] for metric in embodied)
    cleanup_failures = sum(not metric["cleanup_verified"] for metric in embodied)
    embodied_ready = len(domains) >= EMBODIED_DOMAIN_TARGET
    embodied_passed = (
        embodied_ready
        and burden_reduction_rate is not None
        and burden_reduction_rate >= EMBODIED_REDUCTION_TARGET
        and burden_regressions == 0
        and duplicate_actions == 0
        and embodied_safety_failures == 0
        and cleanup_failures == 0
    )

    voice = [row["metrics"] for row in rows if row["event_type"] == "voice"]
    warm_voice = [metric for metric in voice if metric["worker_state"] == "warm"]
    cold_voice = [metric for metric in voice if metric["worker_state"] == "cold"]
    warm_latencies = [
        metric["session_average_latency_ms"]
        for metric in warm_voice
        if metric["session_average_latency_ms"] is not None
    ]
    cold_latencies = [
        metric["session_average_latency_ms"]
        for metric in cold_voice
        if metric["session_average_latency_ms"] is not None
    ]
    voice_failures = sum(metric["failure_count"] for metric in voice)
    warm_audible_count = sum(metric["audible_confirmed"] for metric in warm_voice)
    warm_p50 = _percentile(warm_latencies, 0.50)
    warm_p95 = _percentile(warm_latencies, 0.95)
    voice_ready = len(warm_voice) >= VOICE_WARM_TARGET
    voice_passed = (
        voice_ready
        and len(warm_latencies) == len(warm_voice)
        and warm_audible_count == len(warm_voice)
        and voice_failures == 0
        and warm_p50 is not None
        and warm_p50 <= VOICE_P50_LIMIT_MS
        and warm_p95 is not None
        and warm_p95 <= VOICE_P95_LIMIT_MS
    )

    gates = {
        "continuity": _gate(continuity_ready, continuity_passed),
        "avatar": _gate(avatar_ready, avatar_passed),
        "embodied": _gate(embodied_ready, embodied_passed),
        "voice": _gate(voice_ready, voice_passed),
    }
    hard_guardrail_breaches = harmful_count + duplicate_actions + embodied_safety_failures
    if hard_guardrail_breaches:
        verdict = "STOP_AND_REVIEW"
    elif "COLLECTING" in gates.values():
        verdict = "COLLECTING_TWO_WEEK_DOGFOOD"
    elif all(value == "PASS" for value in gates.values()):
        verdict = "READY_FOR_OWNER_ADOPTION_REVIEW"
    else:
        verdict = "RETAIN_ON_DEMAND"

    return {
        "schema": REPORT_SCHEMA,
        "verdict": verdict,
        "event_count": len(rows),
        "gates": gates,
        "continuity": {
            "target_tasks": CONTINUITY_TARGET,
            "observed_tasks": len(continuity),
            "remaining_tasks": max(0, CONTINUITY_TARGET - len(continuity)),
            "no_restatement_success_count": continuity_successes,
            "no_restatement_success_rate": continuity_rate,
            "target_success_rate": CONTINUITY_SUCCESS_TARGET,
            "harmful_count": harmful_count,
            "stale_count": stale_count,
            "average_recovery_seconds": _average(recovery_values),
            "recovery_seconds_coverage": len(recovery_values),
        },
        "avatar": {
            "target_sessions": AVATAR_TARGET,
            "rated_sessions": len(avatar),
            "remaining_sessions": max(0, AVATAR_TARGET - len(avatar)),
            "helpful_count": helpful_count,
            "helpful_rate": helpful_rate,
            "target_helpful_rate": AVATAR_HELPFUL_TARGET,
            "distracting_count": distracting_count,
            "distracting_rate": distracting_rate,
            "distracting_rate_limit": AVATAR_DISTRACTING_LIMIT,
            "operational_failure_sessions": avatar_operational_failures,
            "physical_display_confirmation_count": sum(
                metric["physical_display_confirmed"] for metric in avatar
            ),
            "peak_rss_bytes_max": max(
                (
                    metric["peak_rss_bytes"]
                    for metric in avatar
                    if metric["peak_rss_bytes"] is not None
                ),
                default=None,
            ),
        },
        "embodied": {
            "target_domains": EMBODIED_DOMAIN_TARGET,
            "paired_events": len(embodied),
            "observed_domains": len(domains),
            "remaining_domains": max(0, EMBODIED_DOMAIN_TARGET - len(domains)),
            "baseline_burden": baseline_burden,
            "trial_burden": trial_burden,
            "burden_reduction_rate": burden_reduction_rate,
            "target_reduction_rate": EMBODIED_REDUCTION_TARGET,
            "burden_regression_events": burden_regressions,
            "duplicate_actions": duplicate_actions,
            "safety_failures": embodied_safety_failures,
            "cleanup_failures": cleanup_failures,
        },
        "voice": {
            "target_warm_sessions": VOICE_WARM_TARGET,
            "warm_sessions": len(warm_voice),
            "cold_sessions": len(cold_voice),
            "remaining_warm_sessions": max(0, VOICE_WARM_TARGET - len(warm_voice)),
            "warm_latency_coverage": len(warm_latencies),
            "warm_latency_p50_ms": warm_p50,
            "warm_latency_p95_ms": warm_p95,
            "warm_latency_p50_limit_ms": VOICE_P50_LIMIT_MS,
            "warm_latency_p95_limit_ms": VOICE_P95_LIMIT_MS,
            "cold_latency_average_ms": _average(cold_latencies),
            "failure_count": voice_failures,
            "warm_audible_confirmation_count": warm_audible_count,
        },
        "guardrails": {
            "hard_breach_count": hard_guardrail_breaches,
            "runtime_influence_allowed": False,
            "automatic_service_install_allowed": False,
            "automatic_voice_enable_allowed": False,
            "embodiment_p4_allowed": False,
        },
        "privacy": {
            "task_text_stored": False,
            "prompt_or_transcript_stored": False,
            "memory_content_or_key_stored": False,
            "avatar_session_id_stored": False,
            "receipt_body_in_aggregate": False,
            "free_text_fields_present": False,
        },
        "nonclaims": [
            "operator attestation is not independent task-provenance verification",
            "process receipts do not prove physical pixels or audible sound",
            "paired burden changes do not establish exclusive causation",
            "session-average adapter latency is not model-only inference latency",
            "a passing report requires a separate owner adoption decision",
        ],
    }


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def build_aggregate(
    rows: list[dict[str, Any]], ledger_bytes: bytes, source_node_sha256: str
) -> dict[str, Any]:
    _require_sha256(source_node_sha256, "INVALID_SOURCE_NODE_SHA256")
    report = build_report(rows)
    return {
        "schema": AGGREGATE_SCHEMA,
        "generated_at": int(time.time()),
        "source_node_sha256": source_node_sha256,
        "ledger_sha256": _sha256_bytes(ledger_bytes),
        "report_sha256": _sha256_bytes(_canonical_json(report)),
        "report": report,
        "contains_event_rows": False,
        "contains_task_or_prompt_content": False,
    }


def _read_receipt(path: Path) -> tuple[dict[str, Any], str]:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECEIPT_BYTES:
            raise DogfoodError("INVALID_RECEIPT_FILE")
        raw = path.read_bytes()
        value = json.loads(raw)
    except DogfoodError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise DogfoodError("INVALID_RECEIPT_FILE") from exc
    if type(value) is not dict:
        raise DogfoodError("INVALID_RECEIPT_ROOT")
    return value, _sha256_bytes(raw)


def _linux_live_receipt(value: dict[str, Any]) -> dict[str, Any]:
    if (
        value.get("surface") != "linux_avatar_live_receipt"
        or value.get("schema") != 1
        or value.get("dry_run") is not False
    ):
        raise DogfoodError("INVALID_LINUX_LIVE_RECEIPT")
    safety = value.get("safety")
    if type(safety) is not dict:
        raise DogfoodError("INVALID_LINUX_LIVE_SAFETY")
    required_safety = {
        "foreground_only": True,
        "installs_service": False,
        "controls_desktop": False,
        "executes_actions": False,
        "enables_embodiment_runtime_p4": False,
    }
    if any(safety.get(key) is not expected for key, expected in required_safety.items()):
        raise DogfoodError("LINUX_LIVE_SAFETY_BOUNDARY_CROSSED")
    return value


def avatar_event_from_receipt(
    receipt: dict[str, Any],
    subject_sha256: str,
    *,
    owner_rating: str,
    physical_display_confirmed: bool,
) -> dict[str, Any]:
    value = _linux_live_receipt(receipt)
    observation = value.get("observation")
    presence = value.get("presence")
    if type(observation) is not dict or type(presence) is not dict:
        raise DogfoodError("INVALID_LINUX_LIVE_OBSERVATION")
    if observation.get("surface") != "linux_avatar_live_observation":
        raise DogfoodError("INVALID_LINUX_LIVE_OBSERVATION")
    sidecar = observation.get("sidecar")
    resources = observation.get("resources")
    claims = observation.get("claims")
    if (
        observation.get("read_only") is not True
        or type(sidecar) is not dict
        or type(resources) is not dict
        or type(claims) is not dict
        or resources.get("worker_vram_observed") is not False
        or claims.get("compositor_pixels_observed") is not False
        or claims.get("physical_display_observed") is not False
        or claims.get("physical_audio_observed") is not False
    ):
        raise DogfoodError("INVALID_LINUX_LIVE_OBSERVATION")
    row = _new_event(
        "avatar",
        subject_sha256,
        {
            "owner_rating": owner_rating,
            "completed": value.get("completed"),
            "elapsed_ms": value.get("elapsed_ms"),
            "heartbeat_failures": presence.get("heartbeat_failures"),
            "sidecar_read_failures": sidecar.get("read_failures"),
            "transition_count": sidecar.get("transition_count"),
            "peak_rss_bytes": resources.get("process_peak_rss_bytes"),
            "physical_display_confirmed": physical_display_confirmed,
        },
    )
    return validate_event(row)


def voice_event_from_receipt(
    receipt: dict[str, Any],
    subject_sha256: str,
    *,
    worker_state: str,
    audible_confirmed: bool,
) -> dict[str, Any]:
    value = _linux_live_receipt(receipt)
    voice = value.get("voice_feedback")
    if (
        type(voice) is not dict
        or voice.get("surface") != "linux_avatar_live_voice_receipt"
        or voice.get("schema") != 1
        or voice.get("enabled") is not True
        or voice.get("backend") != "qwen3"
        or voice.get("continuous_listening") is not False
    ):
        raise DogfoodError("INVALID_LINUX_LIVE_VOICE_RECEIPT")
    latency = voice.get("invocation_latency_ms")
    if type(latency) is not dict:
        raise DogfoodError("INVALID_LINUX_LIVE_VOICE_RECEIPT")
    invocation_count = voice.get("invocation_count")
    if latency.get("count") != invocation_count:
        raise DogfoodError("INVALID_LINUX_LIVE_VOICE_RECEIPT")
    if audible_confirmed and voice.get("utterance_count") == 0:
        raise DogfoodError("AUDIBLE_CONFIRMATION_WITHOUT_UTTERANCE")
    row = _new_event(
        "voice",
        subject_sha256,
        {
            "worker_state": worker_state,
            "session_average_latency_ms": latency.get("average"),
            "invocation_count": invocation_count,
            "utterance_count": voice.get("utterance_count"),
            "failure_count": voice.get("failure_count"),
            "audible_confirmed": audible_confirmed,
            "continuous_listening": voice.get("continuous_listening"),
        },
    )
    return validate_event(row)


def _new_event(event_type: str, subject_sha256: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": EVENT_SCHEMA,
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "observed_at": int(time.time()),
        "subject_sha256": subject_sha256,
        "real_task_attested": True,
        "metrics": metrics,
    }


def _emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _subject(value: str) -> str:
    return _require_sha256(value, "INVALID_SUBJECT_SHA256")


def _add_attestation(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--attest-real-task", required=True, action="store_true")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log",
        type=Path,
        help=(
            "absolute owner-local ledger path; when omitted, derive it only from "
            "AGENT_BRIDGE_STATE_DIR"
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    continuity = commands.add_parser("record-continuity")
    _add_attestation(continuity)
    continuity.add_argument("--subject-sha256", required=True)
    continuity.add_argument("--recall-outcome", required=True, choices=RECALL_OUTCOMES)
    continuity.add_argument("--owner-restatements", required=True, type=int)
    completion = continuity.add_mutually_exclusive_group(required=True)
    completion.add_argument("--task-completed", dest="task_completed", action="store_true")
    completion.add_argument(
        "--task-not-completed", dest="task_completed", action="store_false"
    )
    continuity.add_argument("--recovery-seconds", type=int)

    avatar = commands.add_parser("record-avatar")
    _add_attestation(avatar)
    avatar.add_argument("--receipt", required=True, type=Path)
    avatar.add_argument("--owner-rating", required=True, choices=AVATAR_RATINGS)
    avatar.add_argument("--physical-display-confirmed", action="store_true")

    embodied = commands.add_parser("record-embodied")
    _add_attestation(embodied)
    embodied.add_argument("--subject-sha256", required=True)
    embodied.add_argument("--domain-sha256", required=True)
    for name in (
        "baseline-owner-restatements",
        "trial-owner-restatements",
        "baseline-manual-interventions",
        "trial-manual-interventions",
        "baseline-agent-calls",
        "trial-agent-calls",
        "duplicate-actions",
    ):
        embodied.add_argument(f"--{name}", required=True, type=int)
    embodied.add_argument("--safety-failure", action="store_true")
    embodied.add_argument("--cleanup-verified", action="store_true")

    voice = commands.add_parser("record-voice")
    _add_attestation(voice)
    voice.add_argument("--receipt", required=True, type=Path)
    voice.add_argument("--worker-state", required=True, choices=VOICE_WORKER_STATES)
    voice.add_argument("--audible-confirmed", action="store_true")

    commands.add_parser("report")
    export = commands.add_parser("export-aggregate")
    export.add_argument("--source-node-sha256", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        log_path = resolve_log_path(args.log)
        if args.command == "record-continuity":
            row = _new_event(
                "continuity",
                _subject(args.subject_sha256),
                {
                    "recall_outcome": args.recall_outcome,
                    "owner_restatements": args.owner_restatements,
                    "task_completed": args.task_completed,
                    "recovery_seconds": args.recovery_seconds,
                },
            )
            _emit(record_event(log_path, row))
            return 0
        if args.command == "record-avatar":
            receipt, digest = _read_receipt(args.receipt)
            row = avatar_event_from_receipt(
                receipt,
                digest,
                owner_rating=args.owner_rating,
                physical_display_confirmed=args.physical_display_confirmed,
            )
            _emit(record_event(log_path, row))
            return 0
        if args.command == "record-embodied":
            row = _new_event(
                "embodied",
                _subject(args.subject_sha256),
                {
                    "domain_sha256": _require_sha256(
                        args.domain_sha256, "INVALID_DOMAIN_SHA256"
                    ),
                    "baseline_owner_restatements": args.baseline_owner_restatements,
                    "trial_owner_restatements": args.trial_owner_restatements,
                    "baseline_manual_interventions": args.baseline_manual_interventions,
                    "trial_manual_interventions": args.trial_manual_interventions,
                    "baseline_agent_calls": args.baseline_agent_calls,
                    "trial_agent_calls": args.trial_agent_calls,
                    "duplicate_actions": args.duplicate_actions,
                    "safety_failure": args.safety_failure,
                    "cleanup_verified": args.cleanup_verified,
                },
            )
            _emit(record_event(log_path, row))
            return 0
        if args.command == "record-voice":
            receipt, digest = _read_receipt(args.receipt)
            row = voice_event_from_receipt(
                receipt,
                digest,
                worker_state=args.worker_state,
                audible_confirmed=args.audible_confirmed,
            )
            _emit(record_event(log_path, row))
            return 0

        rows, ledger_bytes = read_ledger(log_path)
        if args.command == "report":
            _emit(build_report(rows))
            return 0
        _emit(build_aggregate(rows, ledger_bytes, args.source_node_sha256))
        return 0
    except DogfoodError as exc:
        _emit(
            {
                "schema": REPORT_SCHEMA,
                "verdict": "HOLD_INVALID_EVIDENCE",
                "error_code": exc.code,
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
