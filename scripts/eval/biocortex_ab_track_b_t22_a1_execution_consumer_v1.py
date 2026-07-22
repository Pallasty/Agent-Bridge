"""Single-use T22-A1 execution-admission consumer core.

The core verifies the exact final owner SSHSIG before reading the private
execution-admission receipt, atomically reserves one execution, and only then
hands control to an injected source-bound runner. It opens no socket, starts no
listener, workload, or service process, injects no fault, and performs no cloud
or provider call.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
EXECUTION_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_execution_authorization_v1.py"
TERMINAL_EVIDENCE_SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-terminal-evidence-schema-v1.json"
EXPECTED_TERMINAL_EVIDENCE_SCHEMA_SHA256 = "f3e6b833b04150376d09f3926dc75601acced248ebd9f9e08d70a86cc51e2a1a"
TERMINAL_EVIDENCE_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/terminal-evidence/v1\0"
RUNNER_RESULT_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/source-bound-runner-result/v1\0"
TERMINAL_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/execution-consumption-terminal/v1\0"
MAX_JSON_BYTES = 256 * 1024


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def foreign_call(function, *arguments, **keywords):  # noqa: ANN001, ANN002, ANN003
    try:
        return function(*arguments, **keywords)
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error


def load_execution_module():
    spec = importlib.util.spec_from_file_location("t22a1_execution_for_consumer", EXECUTION_SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(TERMINAL_DOMAIN + canonical(value)).hexdigest()


def utc_text(value: datetime) -> str:
    require(value.tzinfo is not None and value.utcoffset().total_seconds() == 0, "E_CONSUMER_TIMEZONE")
    return value.isoformat().replace("+00:00", "Z")


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and value != "0" * 64 and all(character in "0123456789abcdef" for character in value)


def ensure_private_directory(path: Path, create: bool) -> None:
    require(path.is_absolute() and not path.is_symlink(), "E_CONSUMER_PRIVATE_DIRECTORY")
    if not path.exists() and create:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
        path.chmod(0o700)
    require(
        path.is_dir() and not path.is_symlink()
        and stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
        "E_CONSUMER_PRIVATE_DIRECTORY",
    )


def write_exclusive(path: Path, value: dict) -> None:
    require(path.is_absolute() and not path.exists() and not path.is_symlink(), "E_CONSUMER_OUTPUT_EXISTS")
    ensure_private_directory(path.parent, create=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def terminal_value(body: dict) -> dict:
    value = dict(body)
    value["content_sha256"] = digest(value)
    return value


def validate_terminal(value: object, execution: dict) -> dict:
    required = {
        "schema", "status", "failure_code", "run_id", "source_commit",
        "execution_contract_sha256", "execution_admission_receipt_sha256",
        "owner_execution_signature_sha256", "runner_result_sha256",
        "owner_execution_signature_reverified_before_private_receipt_read",
        "admission_receipt_read_after_owner_signature", "single_execution_reserved",
        "runner_invoked_after_reservation", "consumer_core_network_accessed",
        "consumer_core_listeners_started", "consumer_core_workload_processes_started",
        "consumer_core_faults_injected", "automatic_retry_allowed",
        "production_admissible", "completed_at", "content_sha256",
    }
    require(isinstance(value, dict) and set(value) == required, "E_CONSUMER_TERMINAL_SHAPE")
    assert isinstance(value, dict)
    require(value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.execution_consumption_terminal.v1", "E_CONSUMER_TERMINAL_SCHEMA")
    require(value["status"] in {"PASS_T22_A1_RUNNER_RESULT_RECORDED", "FAIL_T22_A1_EXECUTION_CONSUMPTION_NO_RETRY"}, "E_CONSUMER_TERMINAL_STATUS")
    if value["status"].startswith("PASS_"):
        require(value["failure_code"] is None and is_sha256(value["runner_result_sha256"]), "E_CONSUMER_TERMINAL_RESULT")
        completed = load_execution_module().parse_time(value["completed_at"], "E_CONSUMER_COMPLETED_AT")
        require(completed < load_execution_module().parse_time(execution["expires_at"], "E_CONSUMER_EXECUTION_EXPIRY"), "E_CONSUMER_TERMINAL_EXPIRED_SUCCESS")
    else:
        require(isinstance(value["failure_code"], str) and value["failure_code"].startswith("E_") and value["runner_result_sha256"] is None, "E_CONSUMER_TERMINAL_RESULT")
    require(value["run_id"] == execution["run_id"] and value["source_commit"] == execution["source_commit"], "E_CONSUMER_TERMINAL_RUN")
    require(value["execution_contract_sha256"] == execution["content_sha256"], "E_CONSUMER_TERMINAL_EXECUTION")
    require(is_sha256(value["execution_admission_receipt_sha256"]) and is_sha256(value["owner_execution_signature_sha256"]), "E_CONSUMER_TERMINAL_DIGEST_BINDING")
    require(value["owner_execution_signature_reverified_before_private_receipt_read"] is True, "E_CONSUMER_TERMINAL_ORDERING")
    require(value["admission_receipt_read_after_owner_signature"] is True and value["single_execution_reserved"] is True, "E_CONSUMER_TERMINAL_ORDERING")
    require(value["runner_invoked_after_reservation"] is True, "E_CONSUMER_TERMINAL_ORDERING")
    require(value["consumer_core_network_accessed"] is False and value["consumer_core_listeners_started"] == 0, "E_CONSUMER_TERMINAL_CORE_SIDE_EFFECT")
    require(value["consumer_core_workload_processes_started"] == value["consumer_core_faults_injected"] == 0, "E_CONSUMER_TERMINAL_CORE_SIDE_EFFECT")
    require(value["automatic_retry_allowed"] is False and value["production_admissible"] is False, "E_CONSUMER_TERMINAL_CLAIMS")
    execution_module = load_execution_module()
    foreign_call(execution_module.parse_time, value["completed_at"], "E_CONSUMER_COMPLETED_AT")
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256")
    require(claimed == digest(unsigned), "E_CONSUMER_TERMINAL_DIGEST")
    return value


def validate_runner_result(value: object, execution: dict, admission: dict) -> dict:
    required = {
        "schema", "status", "failure_code", "run_id", "source_commit",
        "execution_contract_sha256", "execution_admission_receipt_sha256",
        "terminal_evidence_content_sha256", "all_owned_processes_cleaned",
        "all_owned_ports_released", "secret_value_scan_passed",
        "automatic_retry_allowed", "production_admissible",
    }
    require(isinstance(value, dict) and set(value) == required, "E_CONSUMER_RUNNER_RESULT_SHAPE")
    assert isinstance(value, dict)
    require(value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.source_bound_runner_result.v1", "E_CONSUMER_RUNNER_RESULT_SCHEMA")
    require(value["status"] in {"PASS_T22_A1_TERMINAL_EVIDENCE_READY", "FAIL_T22_A1_DISTRIBUTED_RUN"}, "E_CONSUMER_RUNNER_RESULT_STATUS")
    require(value["run_id"] == execution["run_id"] and value["source_commit"] == execution["source_commit"], "E_CONSUMER_RUNNER_RESULT_RUN")
    require(value["execution_contract_sha256"] == execution["content_sha256"], "E_CONSUMER_RUNNER_RESULT_EXECUTION")
    require(value["execution_admission_receipt_sha256"] == admission["content_sha256"], "E_CONSUMER_RUNNER_RESULT_ADMISSION")
    if value["status"].startswith("PASS_"):
        require(value["failure_code"] is None and is_sha256(value["terminal_evidence_content_sha256"]), "E_CONSUMER_RUNNER_RESULT_PASS")
        require(value["all_owned_processes_cleaned"] is True and value["all_owned_ports_released"] is True and value["secret_value_scan_passed"] is True, "E_CONSUMER_RUNNER_RESULT_CLEANUP")
    else:
        require(isinstance(value["failure_code"], str) and value["failure_code"].startswith("E_"), "E_CONSUMER_RUNNER_RESULT_FAIL")
        require(value["terminal_evidence_content_sha256"] is None or is_sha256(value["terminal_evidence_content_sha256"]), "E_CONSUMER_RUNNER_RESULT_FAIL")
    require(value["automatic_retry_allowed"] is False and value["production_admissible"] is False, "E_CONSUMER_RUNNER_RESULT_CLAIMS")
    return value


def validate_terminal_evidence(path: Path, execution: dict, admission: dict) -> dict:
    expected = Path(execution["artifact_scope"]["run_evidence_root"]) / "terminal-evidence.json"
    require(path.is_absolute() and path.resolve(strict=False) == expected.resolve(strict=False), "E_CONSUMER_TERMINAL_EVIDENCE_PATH")
    execution_module = load_execution_module()
    value, _raw = foreign_call(execution_module.read_canonical_json, path, "E_CONSUMER_TERMINAL_EVIDENCE")
    schema_raw = TERMINAL_EVIDENCE_SCHEMA_PATH.read_bytes()
    require(hashlib.sha256(schema_raw).hexdigest() == EXPECTED_TERMINAL_EVIDENCE_SCHEMA_SHA256, "E_CONSUMER_TERMINAL_EVIDENCE_SCHEMA_DIGEST")
    try:
        evidence_schema = json.loads(schema_raw)
        validator = Draft202012Validator(evidence_schema, format_checker=FormatChecker())
    except Exception as error:
        raise SafeFailure("E_CONSUMER_TERMINAL_EVIDENCE_SCHEMA_INVALID") from error
    require(not list(validator.iter_errors(value)), "E_CONSUMER_TERMINAL_EVIDENCE_SCHEMA")
    require(value["status"] == "PASS_T22_A1_THREE_HOST_OWNED_SERVICE_SET_LOSS_RECOVERY" and value["failure_code"] is None, "E_CONSUMER_TERMINAL_EVIDENCE_STATUS")
    require(value["run_id"] == execution["run_id"] and value["source_commit"] == execution["source_commit"], "E_CONSUMER_TERMINAL_EVIDENCE_RUN")
    bindings = value["bindings"]
    admission_bindings = execution["admission_bindings"]
    require(bindings == {
        "execution_contract_sha256": execution["content_sha256"],
        "owner_authorization_content_sha256": execution["content_sha256"],
        "admission_contract_sha256": admission_bindings["admission_contract_sha256"],
        "owner_decision_proposal_sha256": admission_bindings["owner_decision_proposal_sha256"],
        "exact_three_domain_attestation_packet_set_sha256": admission_bindings["exact_three_domain_attestation_packet_set_sha256"],
        "peer_endpoint_set_sha256": execution["network"]["peer_endpoint_set_sha256"],
        "acl_policy_receipt_sha256": execution["network"]["acl_policy_receipt_sha256"],
    }, "E_CONSUMER_TERMINAL_EVIDENCE_BINDINGS")
    started = execution_module.parse_time(value["timing"]["started_at"], "E_CONSUMER_TERMINAL_STARTED_AT")
    completed = execution_module.parse_time(value["timing"]["completed_at"], "E_CONSUMER_TERMINAL_COMPLETED_AT")
    signed_maximum = execution["authorization"]["maximum_runtime_seconds"]
    require(started <= completed < execution_module.parse_time(execution["expires_at"], "E_CONSUMER_EXECUTION_EXPIRY"), "E_CONSUMER_TERMINAL_EVIDENCE_TIME")
    require(value["completed_at"] == value["timing"]["completed_at"], "E_CONSUMER_TERMINAL_EVIDENCE_TIME")
    require(value["timing"]["runtime_seconds"] == int((completed - started).total_seconds()), "E_CONSUMER_TERMINAL_EVIDENCE_RUNTIME")
    require(value["timing"]["signed_maximum_runtime_seconds"] == signed_maximum and value["timing"]["runtime_seconds"] <= signed_maximum, "E_CONSUMER_TERMINAL_EVIDENCE_RUNTIME")
    require(value["cluster_evidence"]["fault_target_domain_id"] == execution["fault"]["target_domain_id"], "E_CONSUMER_TERMINAL_EVIDENCE_FAULT")
    packet_hashes = {row["domain_id"]: row["attestation_packet_sha256"] for row in admission_bindings["domain_bindings"]}
    require({row["domain_id"]: row["attestation_packet_sha256"] for row in value["domains"]} == packet_hashes, "E_CONSUMER_TERMINAL_EVIDENCE_DOMAINS")
    require(value["cleanup"]["signed_maximum_spend_usd_cents"] == execution["budget"]["maximum_spend_usd_cents"], "E_CONSUMER_TERMINAL_EVIDENCE_BUDGET")
    require(value["cleanup"]["spend_usd_cents"] <= value["cleanup"]["signed_maximum_spend_usd_cents"], "E_CONSUMER_TERMINAL_EVIDENCE_BUDGET")
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256")
    observed = hashlib.sha256(TERMINAL_EVIDENCE_DOMAIN + canonical(unsigned)).hexdigest()
    require(claimed == observed, "E_CONSUMER_TERMINAL_EVIDENCE_DIGEST")
    require(admission["execution_contract_sha256"] == execution["content_sha256"], "E_CONSUMER_TERMINAL_EVIDENCE_ADMISSION")
    return value


def reserve(root: Path, execution: dict, admission: dict, now: datetime) -> Path:
    ensure_private_directory(root, create=False)
    uses = root / "execution-consumption-uses"
    ensure_private_directory(uses, create=True)
    stem = admission["content_sha256"]
    reservation = uses / f"{stem}.reserved.json"
    terminal = uses / f"{stem}.terminal.json"
    write_exclusive(reservation, {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.execution_consumption_reservation.v1",
        "status": "EXACT_EXECUTION_ADMISSION_RESERVED_SINGLE_USE",
        "run_id": execution["run_id"], "source_commit": execution["source_commit"],
        "execution_contract_sha256": execution["content_sha256"],
        "execution_admission_receipt_sha256": admission["content_sha256"],
        "reserved_at": utc_text(now), "automatic_retry_allowed": False,
        "production_admissible": False,
    })
    return terminal


def consume_and_dispatch(
    execution_contract_path: Path,
    owner_signature_path: Path,
    admission_receipt_path: Path,
    source_commit: str,
    now: datetime,
    runner: Callable[[dict, dict], dict],
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict:
    execution_module = load_execution_module()
    require(execution_module.EXECUTION_ACTIVATION_READY, "E_EXECUTION_ACTIVATION_NOT_READY")
    observed_source_commit = foreign_call(execution_module.require_clean_tracked_tree)
    require(source_commit == observed_source_commit, "E_CONSUMER_SOURCE_COMMIT")
    _counter, collection, _attestation, _runtime, _preparation, _material, contract, proposal, schema = execution_module.load_inputs()
    try:
        anchor = json.loads(collection.ANCHOR_PATH.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SafeFailure("E_CONSUMER_OWNER_ANCHOR") from error
    public_key = foreign_call(collection.validate_anchor, anchor, proposal)
    execution, raw = foreign_call(execution_module.read_canonical_json, execution_contract_path, "E_CONSUMER_EXECUTION_CONTRACT")
    foreign_call(execution_module.validate_execution_contract, execution, schema, contract, proposal, source_commit, now)
    owner_signature_sha256 = foreign_call(execution_module.verify_owner_signature, raw, owner_signature_path, public_key)

    # This is the first private admission-receipt read; it is intentionally
    # ordered after the exact final owner signature verification above.
    admission = foreign_call(execution_module.parse_admission_receipt, admission_receipt_path, execution, now)
    require(admission["owner_execution_signature_sha256"] == owner_signature_sha256, "E_CONSUMER_OWNER_SIGNATURE_BINDING")
    root = foreign_call(execution_module.validate_artifact_scope, execution["artifact_scope"], execution["run_id"])
    terminal_path = reserve(root, execution, admission, now)
    invoked = False
    try:
        invoked = True
        result = validate_runner_result(runner(execution, admission), execution, admission)
        require(result["status"] == "PASS_T22_A1_TERMINAL_EVIDENCE_READY", result["failure_code"] or "E_CONSUMER_RUNNER_FAILED")
        result_sha256 = hashlib.sha256(RUNNER_RESULT_DOMAIN + canonical(result)).hexdigest()
        completion_time = clock()
        require(completion_time.tzinfo is not None and completion_time.utcoffset().total_seconds() == 0, "E_CONSUMER_COMPLETION_TIME")
        require(completion_time < execution_module.parse_time(execution["expires_at"], "E_CONSUMER_EXECUTION_EXPIRY"), "E_CONSUMER_EXECUTION_EXPIRED_AFTER_RUNNER")
        terminal_evidence = validate_terminal_evidence(
            Path(execution["artifact_scope"]["run_evidence_root"]) / "terminal-evidence.json",
            execution, admission,
        )
        require(result["terminal_evidence_content_sha256"] == terminal_evidence["content_sha256"], "E_CONSUMER_RUNNER_TERMINAL_EVIDENCE_BINDING")
        terminal = terminal_value({
            "schema": "agent_bridge.biocortex.track_b.t22_a1.execution_consumption_terminal.v1",
            "status": "PASS_T22_A1_RUNNER_RESULT_RECORDED", "failure_code": None,
            "run_id": execution["run_id"], "source_commit": source_commit,
            "execution_contract_sha256": execution["content_sha256"],
            "execution_admission_receipt_sha256": admission["content_sha256"],
            "owner_execution_signature_sha256": owner_signature_sha256,
            "runner_result_sha256": result_sha256,
            "owner_execution_signature_reverified_before_private_receipt_read": True,
            "admission_receipt_read_after_owner_signature": True,
            "single_execution_reserved": True, "runner_invoked_after_reservation": True,
            "consumer_core_network_accessed": False, "consumer_core_listeners_started": 0,
            "consumer_core_workload_processes_started": 0, "consumer_core_faults_injected": 0,
            "automatic_retry_allowed": False, "production_admissible": False,
            "completed_at": utc_text(completion_time),
        })
        validate_terminal(terminal, execution)
        write_exclusive(terminal_path, terminal)
        return terminal
    except Exception as error:
        failure_code = str(error) if isinstance(error, RuntimeError) and str(error).startswith("E_") else "E_CONSUMER_LOCAL_FAILURE"
        if not terminal_path.exists():
            completion_time = clock()
            if completion_time.tzinfo is None or completion_time.utcoffset().total_seconds() != 0:
                completion_time = now
            terminal = terminal_value({
                "schema": "agent_bridge.biocortex.track_b.t22_a1.execution_consumption_terminal.v1",
                "status": "FAIL_T22_A1_EXECUTION_CONSUMPTION_NO_RETRY", "failure_code": failure_code,
                "run_id": execution["run_id"], "source_commit": source_commit,
                "execution_contract_sha256": execution["content_sha256"],
                "execution_admission_receipt_sha256": admission["content_sha256"],
                "owner_execution_signature_sha256": owner_signature_sha256,
                "runner_result_sha256": None,
                "owner_execution_signature_reverified_before_private_receipt_read": True,
                "admission_receipt_read_after_owner_signature": True,
                "single_execution_reserved": True, "runner_invoked_after_reservation": invoked,
                "consumer_core_network_accessed": False, "consumer_core_listeners_started": 0,
                "consumer_core_workload_processes_started": 0, "consumer_core_faults_injected": 0,
                "automatic_retry_allowed": False, "production_admissible": False,
                "completed_at": utc_text(completion_time),
            })
            validate_terminal(terminal, execution)
            write_exclusive(terminal_path, terminal)
        raise SafeFailure(failure_code) from error


def status() -> dict:
    execution_module = load_execution_module()
    execution_module.load_inputs()
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.execution_consumer_status.v0",
        "status": "OFFLINE_SINGLE_USE_CONSUMER_CORE_READY_EXECUTION_ACTIVATION_GATE_CLOSED" if not execution_module.EXECUTION_ACTIVATION_READY else "OFFLINE_SINGLE_USE_CONSUMER_CORE_READY_SOURCE_BOUND_RUNNER_AND_REAL_ADMISSION_REQUIRED",
        "execution_activation_ready": execution_module.EXECUTION_ACTIVATION_READY,
        "execution_contract_read": False, "owner_signature_read": False,
        "private_admission_receipt_read": False, "credential_files_read": False,
        "network_accessed": False, "listeners_started": 0, "workload_processes_started": 0,
        "faults_injected": 0, "runner_invoked": False,
        "execution_authorized": False, "production_admissible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_subparsers(dest="command", required=True).add_parser("status")
    arguments = parser.parse_args()
    if arguments.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except SafeFailure as error:
        print(json.dumps({"status": "BLOCKED_FAIL_CLOSED", "failure_code": str(error)}, sort_keys=True, separators=(",", ":")))
        sys.exit(1)
