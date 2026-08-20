#!/usr/bin/env python3
"""Closed evidence checks for the private macOS focus-continuity dogfood."""
from __future__ import annotations

import hashlib
import json
from typing import Any


SCHEMA = "agent_bridge.macos_ax_focus_continuity_episode.v0"
JOURNAL_SCHEMA = "agent_bridge.macos_ax_focus_continuity_operation.v0"


class ContractError(ValueError):
    pass


def _strict_int(value: Any, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_probe(payload: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    windows = payload.get("windows")
    frontmost = payload.get("frontmost_app")
    if (
        payload.get("schema") != "macos_ax_probe/v0"
        or payload.get("status") != "ready"
        or payload.get("read_only") is not True
        or payload.get("platform", {}).get("system") != "Darwin"
        or payload.get("permission", {}).get("ax_trusted") is not True
        or payload.get("permission", {}).get("prompted") is not False
        or payload.get("windows_read_ok") is not True
        or payload.get("coverage_complete") is not True
        or payload.get("counts_consistent") is not True
        or payload.get("errors") != []
        or payload.get("incomplete_reasons") != []
        or not isinstance(windows, list)
        or not isinstance(frontmost, dict)
    ):
        raise ContractError("probe_incomplete")
    if (
        frontmost.get("bundle_id") != target["bundle_id"]
        or frontmost.get("pid") != target["pid"]
        or payload.get("app_identity_valid") is not True
        or payload.get("limits", {}).get("include_windows") is not True
        or payload.get("limits", {}).get("truncated") is not False
        or not _strict_int(payload.get("window_count"))
        or not _strict_int(payload.get("source_window_count"))
        or payload["window_count"] != len(windows)
        or payload["source_window_count"] != len(windows)
    ):
        raise ContractError("probe_scope_or_counts_invalid")
    stable: list[dict[str, Any]] = []
    for window in windows:
        if not isinstance(window, dict):
            raise ContractError("window_not_object")
        identity = window.get("identity")
        if (
            not isinstance(identity, dict)
            or identity.get("kind") != "ax_identifier"
            or identity.get("stable_across_samples") is not True
            or not isinstance(identity.get("value"), str)
            or not identity["value"]
            or window.get("ax_identifier") != identity["value"]
            or not isinstance(window.get("role"), str)
            or not window["role"]
            or not isinstance(window.get("title"), str)
            or not isinstance(window.get("focused"), bool)
        ):
            raise ContractError("window_identity_or_selector_incomplete")
        stable.append(window)
    identities = [window["ax_identifier"] for window in stable]
    if len(stable) < 2 or len(set(identities)) != len(identities):
        raise ContractError("two_distinct_stable_windows_required")
    matches = [
        window
        for window in stable
        if window["ax_identifier"] == target["ax_identifier"]
        and window["role"] == target["expected_role"]
        and (
            target.get("expected_title") is None
            or window["title"] == target["expected_title"]
        )
    ]
    if len(matches) != 1:
        raise ContractError("target_not_unique")
    if matches[0]["focused"] is not False:
        raise ContractError("target_must_start_unfocused")
    return {
        "probe_sha256": canonical_sha256(payload),
        "stable_window_count": len(stable),
        "target_initially_unfocused": True,
    }


def validate_admission(payload: dict[str, Any]) -> None:
    if (
        payload.get("schema") != "macos_ax_action_admission/v1"
        or payload.get("status") != "preview_only"
        or payload.get("operation") != "focus_window"
        or payload.get("decision") != "admit"
        or payload.get("risk") != {"class": "embodied_navigation", "rank": 1}
        or payload.get("execution", {}).get("performed") is not False
        or payload.get("authority", {}).get("scope") != "owner_standing"
        or payload.get("authority", {}).get("per_action_prompt_default") is not False
    ):
        raise ContractError("admission_not_exactly_admitted")
    preconditions = payload.get("preconditions", {})
    for key in ("target_exact", "receipt_complete", "target_bound", "surface_fresh"):
        if preconditions.get(key) is not True:
            raise ContractError(f"admission_{key}_false")


def validate_focus(payload: dict[str, Any], target: dict[str, Any]) -> None:
    selector = payload.get("target", {}).get("selector", {})
    if (
        payload.get("schema") != "macos_ax_focus_transaction/v0"
        or payload.get("status") != "verified"
        or payload.get("operation") != "focus_window"
        or payload.get("read_only") is not False
        or payload.get("verification", {}).get("verdict") != "verified"
        or payload.get("verification", {}).get("independent_contract_ok") is not True
        or payload.get("verification", {}).get("recover") != "proceed"
        or payload.get("mcp_wrapper", {}).get("transaction_closed") is not True
        or payload.get("target", {}).get("pid") != target["pid"]
        or payload.get("target", {}).get("bundle_id") != target["bundle_id"]
        or selector.get("ax_identifier") != target["ax_identifier"]
        or selector.get("expected_role") != target["expected_role"]
        or selector.get("expected_title") != target.get("expected_title")
    ):
        raise ContractError("focus_transaction_not_verified")


def validate_terminal_receipt(payload: dict[str, Any], request: dict[str, Any]) -> None:
    if (
        payload.get("schema") != SCHEMA
        or payload.get("status") != "verified"
        or payload.get("operation_id") != request["operation_id"]
        or payload.get("request_sha256") != canonical_sha256(request)
        or payload.get("phase") != "terminal"
        or payload.get("dispatch_count") != 1
        or payload.get("recover") != "proceed"
        or payload.get("redispatched") is not False
        or payload.get("idempotent_replay") is not False
        or payload.get("external_execution_repeated") is not False
        or payload.get("new_runtime_authority_granted") is not False
        or payload.get("contract_bound_dispatch_count") != 1
        or payload.get("focus_dispatch_invoked_in_this_call") not in {True, False}
        or payload.get("cross_app_activation_performed") is not False
        or payload.get("content_mutation_performed") is not False
        or payload.get("recovered_after_interruption") not in {True, False}
        or payload.get("causal_attribution")
        not in {"fresh_verified_transaction", "unknown_after_interruption"}
        or (
            payload.get("recovered_after_interruption") is True
            and payload.get("causal_attribution") != "unknown_after_interruption"
        )
        or (
            payload.get("recovered_after_interruption") is False
            and payload.get("causal_attribution") != "fresh_verified_transaction"
        )
    ):
        raise ContractError("terminal_receipt_invalid")


def validate_recovery(payload: dict[str, Any], target: dict[str, Any]) -> None:
    verification = payload.get("verification", {})
    evidence = verification.get("evidence", {})
    selector = evidence.get("selector", {})
    state = (
        payload.get("semantic_objects", [{}])[0].get("state", {})
        if isinstance(payload.get("semantic_objects"), list)
        and len(payload["semantic_objects"]) == 1
        and isinstance(payload["semantic_objects"][0], dict)
        else {}
    )
    if (
        payload.get("schema") != "agent_bridge.semantic_bus.macos_ax_verify.v0"
        or payload.get("read_only") is not True
        or verification.get("verdict") != "verified"
        or verification.get("recover") != "proceed"
        or verification.get("source_verdict") != "verified"
        or verification.get("reason") is not None
        or evidence.get("expect") != "window_focused"
        or evidence.get("wrapper_exit_code") != 0
        or evidence.get("proof_complete") is not True
        or evidence.get("proof_truth") != "match"
        or evidence.get("scope_match") is not True
        or evidence.get("coverage_complete") is not True
        or evidence.get("windows_read_ok") is not True
        or evidence.get("app_identity_valid") is not True
        or evidence.get("counts_consistent") is not True
        or evidence.get("truncated") is not False
        or state.get("expect") != "window_focused"
        or state.get("source_verdict") != "verified"
        or state.get("source_recover") != "proceed"
        or state.get("selector") != selector
        or selector.get("bundle_id") != target["bundle_id"]
        or selector.get("pid") != target["pid"]
        or selector.get("ax_identifier") != target["ax_identifier"]
        or selector.get("role") != target["expected_role"]
        or selector.get("title") != target.get("expected_title")
    ):
        raise ContractError("recovery_postcondition_not_verified")
