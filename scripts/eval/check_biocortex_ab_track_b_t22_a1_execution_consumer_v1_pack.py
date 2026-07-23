"""Synthetic KAT for the T22-A1 single-use execution consumer core."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_execution_consumer_v1.py"
spec = importlib.util.spec_from_file_location("t22a1executionconsumer", SOURCE)
assert spec and spec.loader
consumer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = consumer
spec.loader.exec_module(consumer)
execution = consumer.load_execution_module()
evidence_compiler = consumer.load_evidence_compiler_module()
counter, collection, attestation, runtime, preparation, material, contract, proposal, schema = execution.load_inputs()
consumer.load_execution_module = lambda: execution
execution.load_inputs = lambda: (counter, collection, attestation, runtime, preparation, material, contract, proposal, schema)
execution.EXECUTION_ACTIVATION_READY = True

NOW = datetime.now(timezone.utc).replace(microsecond=0)
SOURCE_COMMIT = "a" * 40
RUN_ID = f"t22-a1-{NOW.strftime('%Y%m%dT%H%M%S')}.000000z-abcdef123456"
SSH_KEYGEN = Path(shutil.which("ssh-keygen") or "").resolve(strict=True)


def sha(label: str) -> str:
    return hashlib.sha256(f"T22_A1_CONSUMER_KAT:{label}".encode()).hexdigest()


def write_private(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    path.write_bytes(consumer.canonical(value) + b"\n")
    path.chmod(0o600)


def sign(path: Path, key: Path) -> Path:
    signature = path.with_suffix(path.suffix + ".sig")
    if signature.exists():
        signature.unlink()
    result = subprocess.run(
        [str(SSH_KEYGEN), "-Y", "sign", "-f", str(key), "-n", execution.SIGNATURE_NAMESPACE, str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    assert result.returncode == 0 and signature.is_file()
    signature.chmod(0o600)
    return signature


def execution_packet(root: Path, label: str) -> dict:
    value = {
        "schema": "synthetic.execution.consumer.kat.v1",
        "run_id": RUN_ID,
        "source_commit": SOURCE_COMMIT,
        "issued_at": execution.utc_text(NOW),
        "expires_at": execution.utc_text(NOW + timedelta(minutes=30)),
        "artifact_scope": {
            "private_artifact_root": str(root),
            "execution_admission_receipt_output_path": str(root / "admissions" / "final-execution-admission.json"),
            "run_evidence_root": str(root / "runs" / RUN_ID),
            "repository_output_allowed": False,
            "directory_mode": "0700",
            "file_mode": "0600",
        },
        "authorization": {"maximum_runtime_seconds": 1200},
        "admission_bindings": {
            "admission_contract_sha256": contract["contract_sha256"],
            "owner_decision_proposal_sha256": proposal["proposal_sha256"],
            "exact_three_domain_attestation_packet_set_sha256": sha(f"attestation-set:{label}"),
            "domain_bindings": [
                {"domain_id": f"domain-{number}", "attestation_packet_sha256": sha(f"attestation:{label}:{number}")}
                for number in (1, 2, 3)
            ],
        },
        "runtime_admission": {
            "runtime_readiness_set_sha256": sha(f"runtime-readiness-set:{label}"),
            "source_artifact_set_sha256": sha(f"source-artifact-set:{label}"),
        },
        "network": {
            "peer_endpoint_set_sha256": sha(f"endpoints:{label}"),
            "acl_policy_receipt_sha256": sha(f"acl:{label}"),
        },
        "budget": {"maximum_spend_usd_cents": 0},
        "fault": {"target_domain_id": "domain-2"},
        "synthetic_label": label,
    }
    value["content_sha256"] = execution.contract_digest(value)
    return value


def validate_synthetic_execution(value, _schema, _contract, _proposal, source_commit, now):  # noqa: ANN001
    consumer.require(value["schema"] == "synthetic.execution.consumer.kat.v1", "E_TEST_EXECUTION_SCHEMA")
    consumer.require(value["source_commit"] == source_commit, "E_TEST_EXECUTION_SOURCE")
    consumer.require(value["content_sha256"] == execution.contract_digest(value), "E_TEST_EXECUTION_DIGEST")
    consumer.require(execution.parse_time(value["issued_at"], "E_TEST_ISSUED") <= now < execution.parse_time(value["expires_at"], "E_TEST_EXPIRES"), "E_TEST_EXECUTION_CURRENT")
    execution.validate_artifact_scope(value["artifact_scope"], value["run_id"])
    return value


execution.validate_execution_contract = validate_synthetic_execution
execution.require_clean_tracked_tree = lambda: SOURCE_COMMIT


def admission_receipt(value: dict, owner_signature_sha256: str, admitted_at: datetime) -> dict:
    receipt = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.execution_admission_receipt.v1",
        "status": "AUTHORIZED_T22_A1_EXACT_OWNER_SIGNED_NONPRODUCTION_EXECUTION_ADMISSION",
        "run_id": value["run_id"], "source_commit": value["source_commit"],
        "execution_contract_sha256": value["content_sha256"],
        "owner_execution_signature_sha256": owner_signature_sha256,
        "owner_countersigned_attestation_set_receipt_sha256": sha("admitted-set"),
        "runtime_preparation_terminal_receipt_sha256": sha("preparation"),
        "private_endpoint_manifest_content_sha256": sha("endpoint"),
        "runtime_credential_manifest_content_sha256": sha("credential"),
        "coordinator_runtime_public_key_sha256": sha("coordinator-runtime-key"),
        "runtime_readiness_set_verification_receipt_sha256": sha("runtime-readiness-verification"),
        "runtime_readiness_set_sha256": value["runtime_admission"]["runtime_readiness_set_sha256"],
        "source_artifact_set_sha256": value["runtime_admission"]["source_artifact_set_sha256"],
        "all_three_domain_attestations_reverified_current": True,
        "all_three_runtime_readiness_packets_reverified_current": True,
        "all_three_runtime_readiness_signatures_reverified": True,
        "source_artifacts_rehashed_from_clean_source_commit": True,
        "owner_set_countersignature_reverified": True,
        "owner_runtime_preparation_signature_reverified": True,
        "owner_execution_signature_verified": True,
        "credential_files_read_only_after_owner_execution_signature": True,
        "certificate_count": 5, "private_key_count": 5,
        "all_credential_files_verified": True,
        "one_execution_per_admission_receipt": True,
        "automatic_retry_allowed": False,
        "raw_endpoint_or_credential_values_in_receipt": False,
        "network_accessed": False, "external_hosts_contacted": 0,
        "listeners_started": 0, "services_started": 0, "faults_injected": 0,
        "spend_usd_cents": 0, "execution_authorized": True,
        "production_admissible": False, "expires_at": value["expires_at"],
        "admitted_at": execution.utc_text(admitted_at),
    }
    receipt["content_sha256"] = execution.digest(execution.ADMISSION_RECEIPT_DOMAIN, receipt)
    execution.validate_admission_receipt(receipt, value, admitted_at)
    return receipt


def runner_result(
    value: dict,
    receipt: dict,
    status: str = "PASS_T22_A1_TERMINAL_EVIDENCE_READY",
    terminal_sha256: str | None = None,
    manifest_sha256: str | None = None,
) -> dict:
    success = status.startswith("PASS_")
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.source_bound_runner_result.v1",
        "status": status,
        "failure_code": None if success else "E_SYNTHETIC_RUNNER_FAILURE",
        "run_id": value["run_id"], "source_commit": value["source_commit"],
        "execution_contract_sha256": value["content_sha256"],
        "execution_admission_receipt_sha256": receipt["content_sha256"],
        "evidence_manifest_content_sha256": manifest_sha256 if success else None,
        "terminal_evidence_content_sha256": terminal_sha256 if success else None,
        "all_owned_processes_cleaned": success,
        "all_owned_ports_released": success,
        "secret_value_scan_passed": success,
        "automatic_retry_allowed": False, "production_admissible": False,
    }


def terminal_evidence(
    value: dict,
    started: datetime,
    completed: datetime,
    event_count: int,
    event_head_sha256: str,
) -> dict:
    rows = [{
        "domain_id": row["domain_id"],
        "attestation_packet_sha256": row["attestation_packet_sha256"],
        "attestation_signature_verified": True,
        "signed_event_chain_head_sha256": sha(f"domain-chain:{value['synthetic_label']}:{row['domain_id']}"),
        "domain_event_count": 5,
        "domain_event_signatures_verified": True,
        "preflight_receipt_sha256": sha(f"preflight:{value['synthetic_label']}:{row['domain_id']}"),
        "process_receipt_sha256": sha(f"process:{value['synthetic_label']}:{row['domain_id']}"),
        "cleanup_receipt_sha256": sha(f"cleanup:{value['synthetic_label']}:{row['domain_id']}"),
        "owned_process_log_set_sha256": sha(f"logs:{value['synthetic_label']}:{row['domain_id']}"),
        "owned_process_logs_hashed": True, "cleanup_receipt_verified": True,
        "all_owned_processes_stopped": True, "all_owned_ports_released": True,
        "secret_value_scan_passed": True,
    } for row in value["admission_bindings"]["domain_bindings"]]
    evidence = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.terminal_evidence.v1",
        "packet_kind": "T22_A1_H_TERMINAL_EVIDENCE",
        "hashing_contract": {
            "hash_algorithm": "SHA-256", "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
            "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/terminal-evidence/v1",
            "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256", "self_hash_field": "content_sha256",
            "self_hash_field_excluded": True, "cross_field_semantic_validation_required": True,
        },
        "status": "PASS_T22_A1_THREE_HOST_OWNED_SERVICE_SET_LOSS_RECOVERY", "failure_code": None,
        "run_id": value["run_id"], "source_commit": value["source_commit"],
        "bindings": {
            "execution_contract_sha256": value["content_sha256"],
            "owner_authorization_content_sha256": value["content_sha256"],
            "admission_contract_sha256": value["admission_bindings"]["admission_contract_sha256"],
            "owner_decision_proposal_sha256": value["admission_bindings"]["owner_decision_proposal_sha256"],
            "exact_three_domain_attestation_packet_set_sha256": value["admission_bindings"]["exact_three_domain_attestation_packet_set_sha256"],
            "peer_endpoint_set_sha256": value["network"]["peer_endpoint_set_sha256"],
            "acl_policy_receipt_sha256": value["network"]["acl_policy_receipt_sha256"],
        },
        "timing": {
            "started_at": execution.utc_text(started), "completed_at": execution.utc_text(completed),
            "runtime_seconds": int((completed - started).total_seconds()),
            "signed_maximum_runtime_seconds": value["authorization"]["maximum_runtime_seconds"],
            "runtime_within_signed_limit": True, "maximum_observed_clock_skew_seconds": 1,
            "clock_skew_within_bound": True,
        },
        "domains": rows,
        "cluster_evidence": {
            "etcd_distinct_voter_domain_count": 3, "openbao_distinct_voter_domain_count": 3,
            "linearizable_authorize_consume_observed": True, "replay_consume_rejected": True,
            "prefault_transit_signature_created": True,
            "fault_target_domain_id": value["fault"]["target_domain_id"], "fault_target_was_non_coordinator": True,
            "target_owned_service_set_stopped": True,
            "surviving_two_domain_etcd_quorum_observed": True,
            "surviving_two_domain_openbao_available": True,
            "postfault_transit_signature_verified": True,
            "target_owned_service_set_restarted": True, "target_domain_rejoined": True,
        },
        "event_chain": {
            "event_count": event_count, "event_chain_head_sha256": event_head_sha256,
            "canonical_coordinator_hash_chain_verified": True,
            "all_source_domain_signatures_verified": True, "terminal_event_present": True,
        },
        "cleanup": {
            "all_owned_processes_stopped": True, "all_owned_ports_released": True,
            "all_domain_cleanup_receipts_verified": True, "secret_value_scan_passed": True,
            "host_global_network_mutated": False, "ambient_or_external_credentials_accessed": False,
            "public_listeners_created": False, "spend_usd_cents": 0,
            "signed_maximum_spend_usd_cents": value["budget"]["maximum_spend_usd_cents"],
            "spend_within_signed_limit": True,
        },
        "claims": {
            "maximum_claim": "THREE_DISTINCT_PHYSICAL_HOST_PLACEMENT_AND_ONE_HOST_SCOPED_OWNED_SERVICE_SET_LOSS_RECOVERY_NONPRODUCTION",
            "admissible_claim_earned": True, "host_power_loss_proved": False,
            "site_power_network_independence_proved": False, "storage_device_durability_proved": False,
            "provider_durability_proved": False, "external_anti_rollback_proved": False,
            "production_admissible": False,
        },
        "completed_at": execution.utc_text(completed),
    }
    evidence["content_sha256"] = hashlib.sha256(
        consumer.TERMINAL_EVIDENCE_DOMAIN + consumer.canonical(evidence),
    ).hexdigest()
    return evidence


def coordinator_events(value: dict, started: datetime) -> tuple[list[dict], list[dict]]:
    events = []
    sources = []
    previous = "0" * 64
    domain_sequences = {domain_id: 0 for domain_id in evidence_compiler.DOMAIN_IDS}
    domain_heads = {domain_id: "0" * 64 for domain_id in evidence_compiler.DOMAIN_IDS}
    for sequence, (domain_id, command, event_type) in enumerate(
        evidence_compiler.resolve_event_plan(value["fault"]["target_domain_id"]),
    ):
        observed_at = execution.utc_text(started + timedelta(microseconds=sequence))
        observation = {"synthetic_observation_sha256": sha(f"observation:{value['synthetic_label']}:{sequence}")}
        attestation_sha256 = next(
            row["attestation_packet_sha256"]
            for row in value["admission_bindings"]["domain_bindings"] if row["domain_id"] == domain_id
        )
        domain_key_sha256 = sha(f"domain-key:{value['synthetic_label']}:{domain_id}")
        receipt = {
            "run_id": value["run_id"], "source_commit": value["source_commit"],
            "execution_contract_sha256": value["content_sha256"], "domain_id": domain_id,
            "command": command, "content_sha256": sha(f"receipt:{value['synthetic_label']}:{sequence}"),
            "observation": observation, "observed_at": observed_at,
        }
        payload = evidence_compiler.build_domain_event_payload(
            receipt, event_type, domain_sequences[domain_id], domain_heads[domain_id],
            attestation_sha256, domain_key_sha256,
        )
        payload_raw = evidence_compiler.canonical(payload) + b"\n"
        signature_raw = f"SYNTHETIC-CONSUMER-SIGNATURE:{sequence}\n".encode()
        event = {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.distributed_event.v1",
            "run_id": value["run_id"], "source_commit": value["source_commit"],
            "execution_contract_sha256": value["content_sha256"],
            "sequence": sequence, "previous_event_sha256": previous,
            "observed_at": observed_at,
            "source_domain_id": domain_id, "event_type": event_type,
            "observation_sha256": payload["observation_sha256"],
            "source_domain_evidence": {
                "attestation_packet_sha256": attestation_sha256,
                "domain_event_payload_sha256": payload["content_sha256"],
                "detached_signature_sha256": hashlib.sha256(signature_raw).hexdigest(),
                "domain_public_key_sha256": domain_key_sha256,
                "signature_scheme": "OPENSSH_SSHSIG_ED25519",
                "signature_namespace": evidence_compiler.SIGNATURE_NAMESPACE,
                "signature_verified": True,
            },
            "contains_raw_endpoint": False, "contains_secret_material": False,
        }
        event["event_sha256"] = evidence_compiler.digest(evidence_compiler.EVENT_DOMAIN, event)
        events.append(event)
        sources.append({"payload_raw": payload_raw, "signature_raw": signature_raw})
        previous = event["event_sha256"]
        domain_sequences[domain_id] += 1
        domain_heads[domain_id] = payload["content_sha256"]
    evidence_compiler.validate_coordinator_chain(events, value)
    return events, sources


def write_closed_evidence_set(
    value: dict,
    evidence: dict,
    events: list[dict],
    sources: list[dict],
) -> dict:
    root = Path(value["artifact_scope"]["run_evidence_root"]) / "evidence-set"
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    root.chmod(0o700)
    rows = []
    for sequence, (event, source) in enumerate(zip(events, sources, strict=True)):
        source_stem = f"{sequence:04d}-{event['source_domain_id']}-{event['event_type'].lower()}"
        files = {
            Path("source-domain-events") / f"{source_stem}.event.json": (
                source["payload_raw"]
            ),
            Path("source-domain-events") / f"{source_stem}.event.sshsig": (
                source["signature_raw"]
            ),
            Path("coordinator-events") / f"{sequence:04d}-{event['event_type'].lower()}.json": (
                consumer.canonical(event) + b"\n"
            ),
        }
        for relative, raw in files.items():
            path = root / relative
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.parent.chmod(0o700)
            path.write_bytes(raw)
            path.chmod(0o600)
    terminal_path = root / "terminal-evidence.json"
    write_private(terminal_path, evidence)
    for path in sorted((path for path in root.rglob("*") if path.is_file()), key=lambda item: item.relative_to(root).as_posix()):
        raw = path.read_bytes()
        rows.append({
            "relative_path": path.relative_to(root).as_posix(),
            "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        })
    manifest = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.evidence_set_manifest.v1",
        "packet_kind": "T22_A1_PRIVATE_ATOMIC_EVIDENCE_SET_MANIFEST",
        "run_id": value["run_id"], "source_commit": value["source_commit"],
        "execution_contract_sha256": value["content_sha256"],
        "source_domain_signed_event_count": 21, "coordinator_event_count": 21,
        "coordinator_event_chain_head_sha256": events[-1]["event_sha256"],
        "terminal_evidence_content_sha256": evidence["content_sha256"],
        "artifact_file_count_excluding_manifest": len(rows), "artifact_files": rows,
        "all_files_owner_only": True, "single_publication_attempt_reserved": True,
        "automatic_retry_allowed": False, "raw_endpoint_or_secret_in_manifest": False,
        "production_admissible": False,
    }
    manifest["content_sha256"] = hashlib.sha256(
        consumer.EVIDENCE_MANIFEST_DOMAIN + consumer.canonical(manifest),
    ).hexdigest()
    write_private(root / "evidence-manifest.json", manifest)
    return manifest


with tempfile.TemporaryDirectory(prefix="t22-a1-execution-consumer-kat-") as directory:
    base = Path(directory).resolve()
    owner_key = base / "owner"
    wrong_key = base / "wrong"
    for key in (owner_key, wrong_key):
        subprocess.run([str(SSH_KEYGEN), "-q", "-t", "ed25519", "-N", "", "-C", "T22_A1_CONSUMER_SYNTHETIC", "-f", str(key)], check=True)
    anchor = collection.build_anchor(Path(str(owner_key) + ".pub"), proposal, proposal["proposal_sha256"])
    anchor_path = base / "owner-anchor.json"
    write_private(anchor_path, anchor)
    collection.ANCHOR_PATH = anchor_path

    def build_chain(label: str) -> tuple[Path, Path, Path, dict, dict]:
        artifact_root = base / label
        artifact_root.mkdir(mode=0o700)
        artifact_root.chmod(0o700)
        value = execution_packet(artifact_root, label)
        value_path = artifact_root / "authorizations" / "final-execution-contract.json"
        write_private(value_path, value)
        signature_path = sign(value_path, owner_key)
        signature_sha256 = hashlib.sha256(signature_path.read_bytes()).hexdigest()
        receipt = admission_receipt(value, signature_sha256, NOW + timedelta(seconds=1))
        receipt_path = Path(value["artifact_scope"]["execution_admission_receipt_output_path"])
        write_private(receipt_path, receipt)
        return value_path, signature_path, receipt_path, value, receipt

    execution_path, signature_path, admission_path, execution_value, admission_value = build_chain("success")
    callback_count = 0

    def successful_runner(value: dict, receipt: dict) -> dict:
        global callback_count
        callback_count += 1
        reservation = Path(value["artifact_scope"]["private_artifact_root"]) / "execution-consumption-uses" / f"{receipt['content_sha256']}.reserved.json"
        assert reservation.is_file()
        events, sources = coordinator_events(value, NOW + timedelta(seconds=2))
        evidence = terminal_evidence(
            value, NOW + timedelta(seconds=2), NOW + timedelta(seconds=3),
            len(events), events[-1]["event_sha256"],
        )
        manifest = write_closed_evidence_set(value, evidence, events, sources)
        return runner_result(
            value, receipt, terminal_sha256=evidence["content_sha256"],
            manifest_sha256=manifest["content_sha256"],
        )

    terminal = consumer.consume_and_dispatch(
        execution_path, signature_path, admission_path, SOURCE_COMMIT,
        NOW + timedelta(seconds=2), successful_runner,
        clock=lambda: NOW + timedelta(seconds=3),
    )
    assert callback_count == 1
    assert terminal["status"] == "PASS_T22_A1_RUNNER_RESULT_RECORDED"
    assert terminal["owner_execution_signature_reverified_before_private_receipt_read"] is True
    assert terminal["admission_receipt_read_after_owner_signature"] is True
    assert terminal["single_execution_reserved"] is True and terminal["runner_invoked_after_reservation"] is True
    assert terminal["consumer_core_network_accessed"] is False
    assert terminal["consumer_core_listeners_started"] == terminal["consumer_core_workload_processes_started"] == terminal["consumer_core_faults_injected"] == 0
    terminal_path = Path(execution_value["artifact_scope"]["private_artifact_root"]) / "execution-consumption-uses" / f"{admission_value['content_sha256']}.terminal.json"
    assert json.loads(terminal_path.read_text()) == terminal
    evidence_path = Path(execution_value["artifact_scope"]["run_evidence_root"]) / "evidence-set" / "terminal-evidence.json"
    original_evidence = json.loads(evidence_path.read_text())
    evidence_mutations = (
        lambda x: x.update(status="FAIL_T22_A1_DISTRIBUTED_EXECUTION"),
        lambda x: x.update(source_commit="b" * 40),
        lambda x: x["bindings"].update(execution_contract_sha256=sha("wrong-execution")),
        lambda x: x["bindings"].update(owner_authorization_content_sha256=sha("wrong-authorization")),
        lambda x: x["timing"].update(runtime_seconds=2),
        lambda x: x["timing"].update(signed_maximum_runtime_seconds=1199),
        lambda x: x["cluster_evidence"].update(fault_target_domain_id="domain-3"),
        lambda x: x["domains"][1].update(attestation_packet_sha256=sha("wrong-domain-packet")),
        lambda x: x["cleanup"].update(signed_maximum_spend_usd_cents=1),
        lambda x: x["cleanup"].update(spend_usd_cents=1),
        lambda x: x.update(content_sha256=sha("forged-self-digest")),
    )
    for index, mutation in enumerate(evidence_mutations):
        candidate = copy.deepcopy(original_evidence)
        mutation(candidate)
        if index != len(evidence_mutations) - 1:
            candidate.pop("content_sha256", None)
            candidate["content_sha256"] = hashlib.sha256(
                consumer.TERMINAL_EVIDENCE_DOMAIN + consumer.canonical(candidate),
            ).hexdigest()
        write_private(evidence_path, candidate)
        try:
            consumer.validate_terminal_evidence(evidence_path, execution_value, admission_value)
        except consumer.SafeFailure:
            continue
        raise AssertionError("unsafe terminal evidence admitted by consumer")
    write_private(evidence_path, original_evidence)

    evidence_root = evidence_path.parent
    manifest_path = evidence_root / "evidence-manifest.json"
    original_manifest = json.loads(manifest_path.read_text())
    closure_result = runner_result(
        execution_value, admission_value,
        terminal_sha256=original_evidence["content_sha256"],
        manifest_sha256=original_manifest["content_sha256"],
    )
    evidence_set_negative_count = 0
    source_signature_path = sorted((evidence_root / "source-domain-events").glob("*.event.sshsig"))[0]
    original_source_signature = source_signature_path.read_bytes()
    source_signature_path.write_bytes(original_source_signature + b"tampered")
    source_signature_path.chmod(0o600)
    try:
        consumer.validate_evidence_set(execution_value, admission_value, closure_result)
    except consumer.SafeFailure as error:
        assert str(error) == "E_CONSUMER_EVIDENCE_FILE_DIGEST"
    else:
        raise AssertionError("tampered source signature admitted by evidence-set closure")
    source_signature_path.write_bytes(original_source_signature)
    source_signature_path.chmod(0o600)
    evidence_set_negative_count += 1

    source_signature_path.write_bytes(original_source_signature + b"reclosed-tamper")
    source_signature_path.chmod(0o600)
    reclosed_signature_manifest = copy.deepcopy(original_manifest)
    signature_relative = source_signature_path.relative_to(evidence_root).as_posix()
    signature_row = next(
        item for item in reclosed_signature_manifest["artifact_files"]
        if item["relative_path"] == signature_relative
    )
    reclosed_signature_raw = source_signature_path.read_bytes()
    signature_row["size_bytes"] = len(reclosed_signature_raw)
    signature_row["sha256"] = hashlib.sha256(reclosed_signature_raw).hexdigest()
    reclosed_signature_manifest.pop("content_sha256")
    reclosed_signature_manifest["content_sha256"] = hashlib.sha256(
        consumer.EVIDENCE_MANIFEST_DOMAIN + consumer.canonical(reclosed_signature_manifest),
    ).hexdigest()
    write_private(manifest_path, reclosed_signature_manifest)
    reclosed_signature_result = copy.deepcopy(closure_result)
    reclosed_signature_result["evidence_manifest_content_sha256"] = reclosed_signature_manifest["content_sha256"]
    try:
        consumer.validate_evidence_set(execution_value, admission_value, reclosed_signature_result)
    except consumer.SafeFailure as error:
        assert str(error) == "E_CONSUMER_SOURCE_SIGNATURE_BINDING"
    else:
        raise AssertionError("reclosed source signature tamper admitted")
    source_signature_path.write_bytes(original_source_signature)
    source_signature_path.chmod(0o600)
    write_private(manifest_path, original_manifest)
    evidence_set_negative_count += 1

    forged_manifest = copy.deepcopy(original_manifest)
    forged_manifest["content_sha256"] = sha("forged-manifest")
    write_private(manifest_path, forged_manifest)
    try:
        consumer.validate_evidence_set(execution_value, admission_value, closure_result)
    except consumer.SafeFailure as error:
        assert str(error) == "E_CONSUMER_EVIDENCE_MANIFEST_DIGEST"
    else:
        raise AssertionError("forged evidence manifest admitted")
    write_private(manifest_path, original_manifest)
    evidence_set_negative_count += 1

    coordinator_path = sorted((evidence_root / "coordinator-events").glob("*.json"))[0]
    original_coordinator_raw = coordinator_path.read_bytes()
    forged_coordinator = json.loads(original_coordinator_raw)
    forged_coordinator["event_sha256"] = sha("forged-coordinator-event")
    write_private(coordinator_path, forged_coordinator)
    coordinator_relative = coordinator_path.relative_to(evidence_root).as_posix()
    reclosed_manifest = copy.deepcopy(original_manifest)
    row = next(item for item in reclosed_manifest["artifact_files"] if item["relative_path"] == coordinator_relative)
    forged_coordinator_raw = coordinator_path.read_bytes()
    row["size_bytes"] = len(forged_coordinator_raw)
    row["sha256"] = hashlib.sha256(forged_coordinator_raw).hexdigest()
    reclosed_manifest.pop("content_sha256")
    reclosed_manifest["content_sha256"] = hashlib.sha256(
        consumer.EVIDENCE_MANIFEST_DOMAIN + consumer.canonical(reclosed_manifest),
    ).hexdigest()
    write_private(manifest_path, reclosed_manifest)
    reclosed_result = copy.deepcopy(closure_result)
    reclosed_result["evidence_manifest_content_sha256"] = reclosed_manifest["content_sha256"]
    try:
        consumer.validate_evidence_set(execution_value, admission_value, reclosed_result)
    except consumer.SafeFailure as error:
        assert str(error) == "E_EVIDENCE_COORDINATOR_EVENT_DIGEST"
    else:
        raise AssertionError("reclosed forged coordinator event admitted")
    coordinator_path.write_bytes(original_coordinator_raw)
    coordinator_path.chmod(0o600)
    write_private(manifest_path, original_manifest)
    evidence_set_negative_count += 1

    try:
        consumer.consume_and_dispatch(
            execution_path, signature_path, admission_path, "b" * 40,
            NOW + timedelta(seconds=2), successful_runner,
            clock=lambda: NOW + timedelta(seconds=3),
        )
    except consumer.SafeFailure as error:
        assert str(error) == "E_CONSUMER_SOURCE_COMMIT"
    else:
        raise AssertionError("caller-selected source commit admitted")
    assert callback_count == 1

    terminal_mutations = (
        lambda x: x.update(status="PRODUCTION_AUTHORIZED"),
        lambda x: x.update(source_commit="b" * 40),
        lambda x: x.update(execution_contract_sha256=sha("wrong-execution")),
        lambda x: x.update(execution_admission_receipt_sha256="0" * 64),
        lambda x: x.update(owner_execution_signature_reverified_before_private_receipt_read=False),
        lambda x: x.update(admission_receipt_read_after_owner_signature=False),
        lambda x: x.update(single_execution_reserved=False),
        lambda x: x.update(runner_invoked_after_reservation=False),
        lambda x: x.update(consumer_core_network_accessed=True),
        lambda x: x.update(consumer_core_workload_processes_started=1),
        lambda x: x.update(automatic_retry_allowed=True),
        lambda x: x.update(production_admissible=True),
        lambda x: x.update(unexpected="field"),
    )
    for mutation in terminal_mutations:
        candidate = copy.deepcopy(terminal)
        mutation(candidate)
        candidate.pop("content_sha256", None)
        candidate["content_sha256"] = consumer.digest(candidate)
        try:
            consumer.validate_terminal(candidate, execution_value)
        except consumer.SafeFailure:
            continue
        raise AssertionError("unsafe execution-consumption terminal admitted")

    result = runner_result(
        execution_value, admission_value, terminal_sha256=sha("synthetic-terminal"),
        manifest_sha256=sha("synthetic-manifest"),
    )
    result_mutations = (
        lambda x: x.update(status="PRODUCTION_PASS"),
        lambda x: x.update(run_id="t22-a1-20260722T000000.000000z-000000000000"),
        lambda x: x.update(execution_contract_sha256=sha("wrong-execution")),
        lambda x: x.update(execution_admission_receipt_sha256=sha("wrong-admission")),
        lambda x: x.update(evidence_manifest_content_sha256=None),
        lambda x: x.update(terminal_evidence_content_sha256=None),
        lambda x: x.update(all_owned_processes_cleaned=False),
        lambda x: x.update(all_owned_ports_released=False),
        lambda x: x.update(secret_value_scan_passed=False),
        lambda x: x.update(automatic_retry_allowed=True),
        lambda x: x.update(production_admissible=True),
        lambda x: x.update(unexpected="field"),
    )
    for mutation in result_mutations:
        candidate = copy.deepcopy(result)
        mutation(candidate)
        try:
            consumer.validate_runner_result(candidate, execution_value, admission_value)
        except consumer.SafeFailure:
            continue
        raise AssertionError("unsafe source-bound runner result admitted")

    # Replay is terminal before the callback can be reached.
    try:
        consumer.consume_and_dispatch(
            execution_path, signature_path, admission_path, SOURCE_COMMIT,
            NOW + timedelta(seconds=3), successful_runner,
            clock=lambda: NOW + timedelta(seconds=4),
        )
    except consumer.SafeFailure as error:
        assert str(error) == "E_CONSUMER_OUTPUT_EXISTS"
    else:
        raise AssertionError("execution admission consumed twice")
    assert callback_count == 1

    # A bad final owner signature cannot cause the private admission receipt to be read.
    wrong_execution_path, valid_signature, wrong_admission_path, _value, _receipt = build_chain("wrong-signature")
    wrong_signature_path = wrong_execution_path.with_suffix(wrong_execution_path.suffix + ".wrong.sig")
    valid_signature.unlink()
    result = subprocess.run(
        [str(SSH_KEYGEN), "-Y", "sign", "-f", str(wrong_key), "-n", execution.SIGNATURE_NAMESPACE, str(wrong_execution_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    generated_wrong = wrong_execution_path.with_suffix(wrong_execution_path.suffix + ".sig")
    generated_wrong.rename(wrong_signature_path)
    assert result.returncode == 0
    original_read_bytes = Path.read_bytes

    def protected_read(path: Path) -> bytes:
        if path.resolve(strict=False) == wrong_admission_path.resolve(strict=False):
            raise AssertionError("private admission receipt read before owner signature verification")
        return original_read_bytes(path)

    Path.read_bytes = protected_read
    try:
        try:
            consumer.consume_and_dispatch(
                wrong_execution_path, wrong_signature_path, wrong_admission_path,
                SOURCE_COMMIT, NOW + timedelta(seconds=2), successful_runner,
                clock=lambda: NOW + timedelta(seconds=3),
            )
        except consumer.SafeFailure as error:
            assert str(error) == "E_EXECUTION_OWNER_SIGNATURE_INVALID"
        else:
            raise AssertionError("wrong owner signature admitted")
    finally:
        Path.read_bytes = original_read_bytes

    # A runner failure is recorded terminally and is never retried.
    failure_execution_path, failure_signature_path, failure_admission_path, failure_value, failure_admission = build_chain("runner-failure")
    try:
        consumer.consume_and_dispatch(
            failure_execution_path, failure_signature_path, failure_admission_path,
            SOURCE_COMMIT, NOW + timedelta(seconds=2),
            lambda value, receipt: runner_result(value, receipt, "FAIL_T22_A1_DISTRIBUTED_RUN"),
            clock=lambda: NOW + timedelta(seconds=3),
        )
    except consumer.SafeFailure as error:
        assert str(error) == "E_SYNTHETIC_RUNNER_FAILURE"
    else:
        raise AssertionError("failed runner reported as success")
    failure_terminal_path = Path(failure_value["artifact_scope"]["private_artifact_root"]) / "execution-consumption-uses" / f"{failure_admission['content_sha256']}.terminal.json"
    failure_terminal = json.loads(failure_terminal_path.read_text())
    assert failure_terminal["status"] == "FAIL_T22_A1_EXECUTION_CONSUMPTION_NO_RETRY"
    assert failure_terminal["automatic_retry_allowed"] is False

    expiry_execution_path, expiry_signature_path, expiry_admission_path, expiry_value, expiry_admission = build_chain("runner-expiry")
    try:
        consumer.consume_and_dispatch(
            expiry_execution_path, expiry_signature_path, expiry_admission_path,
            SOURCE_COMMIT, NOW + timedelta(seconds=2),
            lambda value, receipt: runner_result(
                value, receipt, terminal_sha256=sha("late-terminal"),
                manifest_sha256=sha("late-manifest"),
            ),
            clock=lambda: NOW + timedelta(minutes=31),
        )
    except consumer.SafeFailure as error:
        assert str(error) == "E_CONSUMER_EXECUTION_EXPIRED_AFTER_RUNNER"
    else:
        raise AssertionError("runner success recorded after execution expiry")
    expiry_terminal_path = Path(expiry_value["artifact_scope"]["private_artifact_root"]) / "execution-consumption-uses" / f"{expiry_admission['content_sha256']}.terminal.json"
    expiry_terminal = json.loads(expiry_terminal_path.read_text())
    assert expiry_terminal["status"] == "FAIL_T22_A1_EXECUTION_CONSUMPTION_NO_RETRY"
    assert expiry_terminal["automatic_retry_allowed"] is False

    missing_execution_path, missing_signature_path, missing_admission_path, _missing_value, _missing_admission = build_chain("missing-terminal-evidence")
    try:
        consumer.consume_and_dispatch(
            missing_execution_path, missing_signature_path, missing_admission_path,
            SOURCE_COMMIT, NOW + timedelta(seconds=2),
            lambda value, receipt: runner_result(
                value, receipt, terminal_sha256=sha("missing-terminal"),
                manifest_sha256=sha("missing-manifest"),
            ),
            clock=lambda: NOW + timedelta(seconds=3),
        )
    except consumer.SafeFailure as error:
        assert str(error) == "E_CONSUMER_EVIDENCE_SET_MISSING"
    else:
        raise AssertionError("runner success admitted without terminal evidence file")

execution.EXECUTION_ACTIVATION_READY = False
try:
    consumer.consume_and_dispatch(
        execution_path, signature_path, admission_path, SOURCE_COMMIT,
        NOW + timedelta(seconds=3), successful_runner,
        clock=lambda: NOW + timedelta(seconds=4),
    )
except consumer.SafeFailure as error:
    assert str(error) == "E_EXECUTION_ACTIVATION_NOT_READY"
else:
    raise AssertionError("consumer dispatched while execution activation gate was closed")
assert callback_count == 1
ready = consumer.status()
assert ready["status"] == "OFFLINE_SINGLE_USE_CONSUMER_CORE_READY_EXECUTION_ACTIVATION_GATE_CLOSED"
assert ready["execution_activation_ready"] is False
assert ready["private_admission_receipt_read"] is False and ready["credential_files_read"] is False
assert ready["network_accessed"] is False and ready["listeners_started"] == ready["workload_processes_started"] == ready["faults_injected"] == 0
assert ready["runner_invoked"] is False and ready["production_admissible"] is False

negative_count = len(terminal_mutations) + len(result_mutations) + len(evidence_mutations) + evidence_set_negative_count + 7
print("t22_a1_execution_consumer_check\tpass")
print("synthetic_single_use_dispatch_success_count\t1")
print(f"directed_negative_test_count\t{negative_count}")
print("real_execution_contracts_read\t0")
print("real_private_admission_receipts_read\t0")
print("real_credential_files_read\t0")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("workload_processes_started\t0")
print("faults_injected\t0")
print("production_admissible\tfalse")
