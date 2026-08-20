#!/usr/bin/env python3
"""Validate private embodied-media receipts into a closed, content-free result.

This collector is deliberately read-only. It never starts MCP, touches a media
player, opens ADB, or writes raw receipts. A later live runner must call these
same validators before it may enroll a paired task.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

INPUT_SCHEMA = "agent_bridge.embodied_media_episode_collector_input.v0"
RESULT_SCHEMA = "agent_bridge.embodied_media_episode_collector_result.v0"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
BASELINE_TOOLS = (
    "app_control", "app_control", "mobile_projection_start",
    "mobile_projection_wait", "mobile_projection_sync_media",
    "mobile_projection_wait", "mobile_projection_stop",
)
TRIAL_TOOLS = ("app_control", "advance_track_then_project")


class ContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def strict_int(value: Any, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def lowercase_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def validate_pending(payload: dict[str, Any]) -> dict[str, Any]:
    require(payload.get("schema") == "agent_bridge.app_control.v0", "pending schema")
    require(payload.get("status") == "indeterminate", "pending status")
    require(payload.get("verdict") == "error" and payload.get("recover") == "retry", "pending truth")
    require(payload.get("error", {}).get("code") == "operation_effect_not_settled", "pending error")
    tx = payload.get("transaction", {})
    require(tx.get("phase") == "dispatch_started" and tx.get("dispatch_count") == 1, "pending transaction")
    require(tx.get("idempotent_replay") is False, "pending replay")
    require(tx.get("recovered_after_interruption") is False, "pending recovered")
    require(tx.get("external_execution_repeated") is False, "pending repeat")
    dispatch = payload.get("dispatch", {})
    player = payload.get("player")
    require(isinstance(player, str) and player, "pending player")
    require(dispatch.get("argv") == ["playerctl", "-p", player, "next"], "pending argv")
    require(dispatch.get("rc") == 0 and type(dispatch.get("rc")) is int, "pending rc")
    verification = payload.get("verification", {})
    settlement = verification.get("settlement", {})
    require(verification.get("predicate") == "track_identity_change_not_settled", "pending predicate")
    require(settlement.get("schema") == "agent_bridge.app_control.track_settlement.v0", "pending settlement schema")
    require(settlement.get("settled") is False, "pending settled")
    require(payload.get("mcp_wrapper", {}).get("source_contract_ok") is True, "pending wrapper contract")
    return {"player": player, "before_track_id": payload.get("before", {}).get("track_id")}


def validate_recovery(payload: dict[str, Any], pending: dict[str, Any]) -> dict[str, Any]:
    require(payload.get("schema") == "agent_bridge.app_control.v0", "recovery schema")
    require(payload.get("status") == "verified" and payload.get("verdict") == "verified", "recovery truth")
    require(payload.get("recover") == "proceed", "recovery recover")
    require("dispatch" not in payload, "recovery dispatch must be absent")
    require(payload.get("player") == pending["player"], "recovery player")
    before = payload.get("before", {}).get("track_id")
    after = payload.get("after", {}).get("track_id")
    require(isinstance(before, str) and before == pending["before_track_id"], "recovery baseline")
    require(isinstance(after, str) and after and after != before, "recovery changed track")
    verification = payload.get("verification", {})
    settlement = verification.get("settlement", {})
    require(verification.get("predicate") == "track_identity_changed_after_restart_settled", "recovery predicate")
    require(verification.get("reason") is None and "reason" in verification, "recovery reason")
    require(verification.get("observation_error") is None and "observation_error" in verification, "recovery observation")
    require(settlement.get("candidate_track_id") == after, "recovery candidate")
    require(settlement.get("required_consecutive_observations") == 3, "recovery sample requirement")
    require(strict_int(settlement.get("observed_consecutive_observations"), 3), "recovery samples")
    require(settlement.get("required_stable_ms") == 500, "recovery span requirement")
    require(strict_int(settlement.get("observed_stable_ms"), 500), "recovery span")
    require(settlement.get("settled") is True, "recovery settled")
    tx = payload.get("transaction", {})
    require(tx.get("dispatch_count") == 1 and type(tx.get("dispatch_count")) is int, "recovery count")
    require(tx.get("recovered_after_interruption") is True, "recovery flag")
    require(tx.get("external_execution_repeated") is False, "recovery repeat")
    require(payload.get("mcp_wrapper", {}).get("source_contract_ok") is True, "recovery wrapper contract")
    return {"player": pending["player"], "before_track_id": before, "after_track_id": after}


def validate_baseline(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    require(len(receipts) == len(BASELINE_TOOLS), "baseline requires exactly seven calls")
    require(tuple(item.get("tool") for item in receipts) == BASELINE_TOOLS, "baseline call order")
    pending = validate_pending(receipts[0].get("payload", {}))
    recovery = validate_recovery(receipts[1].get("payload", {}), pending)
    start = receipts[2].get("payload", {})
    require(start.get("auto_connect") is True, "baseline auto-connect")
    require(start.get("confirmation_mode") == "test_only_auto_connect", "baseline confirmation mode")
    session = start.get("session_id")
    require(isinstance(session, str) and session, "baseline session")
    connection = receipts[3].get("payload", {})
    require(connection.get("schema") == "agent_bridge.mobile_projection_wait.v1", "connection schema")
    require(connection.get("session_id") == session, "connection session")
    require(connection.get("status") == "test_only_authenticated_connection_observed", "connection status")
    require(connection.get("verdict") == "verified", "connection verdict")
    sync = receipts[4].get("payload", {})
    require(sync.get("schema") == "agent_bridge.mobile_projection_sync_media.v0", "sync schema")
    require(sync.get("session_id") == session and sync.get("status") == "updated", "sync status")
    require(sync.get("app_control", {}).get("player") == recovery["player"], "sync player")
    projected_track = sync.get("media_context", {}).get("track_id")
    require(projected_track == recovery["after_track_id"], "sync track_id path or binding")
    update = sync.get("projection_update", {})
    revision = update.get("revision")
    digest = update.get("frame_sha256")
    require(strict_int(revision, 1) and lowercase_sha256(digest), "sync revision digest")
    draw = receipts[5].get("payload", {})
    require(draw.get("schema") == "agent_bridge.mobile_projection_wait.v1", "draw schema")
    require(draw.get("session_id") == session, "draw session")
    require(draw.get("target_revision") == revision and draw.get("target_frame_sha256") == digest, "draw target")
    require(draw.get("verdict") == "verified" and draw.get("exact_revision_and_digest_draw_reported") is True, "draw verdict")
    report = draw.get("draw_report", {})
    require(report.get("revision") == revision and report.get("frame_sha256") == digest, "draw report binding")
    require(draw.get("claim_boundary", {}).get("human_observed") is False, "human boundary")
    require(draw.get("claim_boundary", {}).get("pixel_verified") is False, "pixel boundary")
    stop = receipts[6].get("payload", {})
    require(stop.get("session_id") == session and stop.get("listener_stop_requested") is True, "stop receipt")
    require(stop.get("adb_force_stop", {}).get("exit_code") == 0, "stop force-stop")
    return {
        "player_binding_verified": True,
        "track_binding_verified": True,
        "exact_draw_verified": True,
        "cleanup_verified": True,
        "reported_dispatch_count": 1,
        "external_execution_repeated": False,
        "before_track_id_sha256": sha256_text(recovery["before_track_id"]),
        "after_track_id_sha256": sha256_text(recovery["after_track_id"]),
        "target_frame_sha256": digest,
    }


def validate_trial(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    require(len(receipts) == 2, "trial requires exactly two calls")
    require(tuple(item.get("tool") for item in receipts) == TRIAL_TOOLS, "trial call order")
    pending = validate_pending(receipts[0].get("payload", {}))
    episode = receipts[1].get("payload", {})
    require(episode.get("schema") == "agent_bridge.advance_track_then_project.v0", "trial schema")
    require(episode.get("verdict") == "verified" and episode.get("recover") == "proceed", "trial truth")
    require(episode.get("last_completed_phase") == "projection_stopped", "trial phase")
    action = episode.get("steps", {}).get("app_control", {})
    require("dispatch" not in action, "trial recovery dispatch must be absent")
    require(action.get("player") == pending["player"], "trial player")
    after = action.get("after", {}).get("track_id")
    require(isinstance(after, str) and after and after != pending["before_track_id"], "trial track")
    require(action.get("transaction", {}).get("dispatch_count") == 1, "trial dispatch count")
    require(action.get("transaction", {}).get("recovered_after_interruption") is True, "trial recovered")
    require(action.get("transaction", {}).get("external_execution_repeated") is False, "trial repeat")
    verification = action.get("verification", {})
    settlement = verification.get("settlement", {})
    require(verification.get("predicate") == "track_identity_changed_after_restart_settled", "trial predicate")
    require(verification.get("reason") is None and "reason" in verification, "trial reason")
    require(verification.get("observation_error") is None and "observation_error" in verification, "trial observation")
    require(settlement.get("candidate_track_id") == after, "trial settlement candidate")
    require(settlement.get("required_consecutive_observations") == 3, "trial sample requirement")
    require(strict_int(settlement.get("observed_consecutive_observations"), 3), "trial samples")
    require(settlement.get("required_stable_ms") == 500, "trial span requirement")
    require(strict_int(settlement.get("observed_stable_ms"), 500), "trial span")
    require(settlement.get("settled") is True, "trial settled")
    require(action.get("source_contract_ok") is True, "trial source contract")
    binding = episode.get("binding", {})
    require(binding.get("player_exact_match") is True, "trial player binding")
    require(binding.get("track_exact_match") is True and binding.get("projected_track_id") == after, "trial track binding")
    require(binding.get("revision_and_digest_exact_match") is True, "trial revision binding")
    digest = binding.get("target_frame_sha256")
    revision = binding.get("target_revision")
    require(strict_int(revision, 1) and lowercase_sha256(digest), "trial revision digest")
    draw = episode.get("steps", {}).get("wait", {})
    require(draw.get("schema") == "agent_bridge.mobile_projection_wait.v1", "trial draw schema")
    require(draw.get("verdict") == "verified", "trial draw verdict")
    require(draw.get("target_revision") == revision and draw.get("target_frame_sha256") == digest, "trial draw target")
    report = draw.get("draw_report", {})
    require(report.get("revision") == revision and report.get("frame_sha256") == digest, "trial draw report")
    require(draw.get("claim_boundary", {}).get("device_activity_draw_reported") is True, "trial device draw")
    require(draw.get("claim_boundary", {}).get("human_observed") is False, "trial human boundary")
    require(draw.get("claim_boundary", {}).get("pixel_verified") is False, "trial pixel boundary")
    cleanup = episode.get("cleanup", {})
    require(cleanup.get("attempted") is True and cleanup.get("verified") is True, "trial cleanup")
    return {
        "player_binding_verified": True,
        "track_binding_verified": True,
        "exact_draw_verified": True,
        "cleanup_verified": True,
        "reported_dispatch_count": 1,
        "external_execution_repeated": False,
        "before_track_id_sha256": sha256_text(pending["before_track_id"]),
        "after_track_id_sha256": sha256_text(after),
        "target_frame_sha256": digest,
    }


def collect(bundle: dict[str, Any]) -> dict[str, Any]:
    require(set(bundle) == {"schema", "pair_id", "side", "operation_id_sha256", "receipts", "metrics"}, "input fields")
    require(bundle.get("schema") == INPUT_SCHEMA, "input schema")
    pair_id = bundle.get("pair_id")
    side = bundle.get("side")
    require(isinstance(pair_id, str) and re.fullmatch(r"embodied-media-pair-[0-9]{2}", pair_id), "pair id")
    require(side in {"baseline", "trial"}, "side")
    require(lowercase_sha256(bundle.get("operation_id_sha256")), "operation hash")
    receipts = bundle.get("receipts")
    require(isinstance(receipts, list) and all(isinstance(item, dict) and set(item) == {"tool", "payload"} for item in receipts), "receipts")
    metrics = bundle.get("metrics")
    require(isinstance(metrics, dict) and set(metrics) == {"owner_restatements", "manual_interventions", "failed_or_replanned_calls", "elapsed_ms"}, "metrics fields")
    for key in metrics:
        require(strict_int(metrics[key]), f"metric {key}")
    evidence = validate_baseline(receipts) if side == "baseline" else validate_trial(receipts)
    return {
        "schema": RESULT_SCHEMA,
        "status": "VERIFIED_PRIVATE_RECEIPTS_NORMALIZED",
        "pair_id": pair_id,
        "side": side,
        "operation_id_sha256": bundle["operation_id_sha256"],
        "agent_orchestration_calls": len(receipts),
        "metrics": metrics,
        "evidence": evidence,
        "privacy": {
            "raw_receipts_persisted_by_collector": False,
            "operation_id_present": False,
            "device_identifier_present": False,
            "session_id_present": False,
            "track_metadata_present": False,
        },
        "claim_boundary": {
            "global_dispatch_count_proven": False,
            "exclusive_causation_proven": False,
            "human_observation_proven": False,
            "pixel_verification_proven": False,
            "runtime_influence_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        result = collect(bundle)
    except (OSError, json.JSONDecodeError, ContractError) as error:
        print(json.dumps({"schema": RESULT_SCHEMA, "status": "REJECTED", "error": str(error)}, separators=(",", ":")))
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
