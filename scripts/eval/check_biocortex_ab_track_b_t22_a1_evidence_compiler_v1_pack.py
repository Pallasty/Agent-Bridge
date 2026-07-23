"""Synthetic signed-chain KAT for the T22-A1 evidence compiler."""
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
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_evidence_compiler_v1.py"
WRITER_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_evidence_writer_v1.py"
spec = importlib.util.spec_from_file_location("t22a1evidencecompiler", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
writer_spec = importlib.util.spec_from_file_location("t22a1evidencewriter", WRITER_SOURCE)
assert writer_spec and writer_spec.loader
writer_module = importlib.util.module_from_spec(writer_spec)
sys.modules[writer_spec.name] = writer_module
writer_spec.loader.exec_module(writer_module)
executor_module = module.load_executor_module()
plan_module = executor_module.load_plan_module()
transport_module = module.load_transport_module()

SOURCE_COMMIT = "a" * 40
RUN_ID = "t22-a1-20260722T220000.000000z-123456789abc"
NOW = datetime(2026, 7, 22, 22, 0, tzinfo=timezone.utc)
SECRET_RAW = b"SYNTHETIC-T22-A1-UNSEAL-SHARE"
SSH_KEYGEN = Path(shutil.which("ssh-keygen") or "").resolve()
assert SSH_KEYGEN.is_file()


def sha(label: str) -> str:
    return hashlib.sha256(f"T22_A1_EVIDENCE_SYNTHETIC:{label}".encode()).hexdigest()


def public_key(raw: bytes) -> tuple[bytes, str]:
    value = module.load_challenge_module().canonical_public_key_bytes(raw)
    return value, hashlib.sha256(value).hexdigest()


def log_set_digest(domain_id: str, rows: list[dict]) -> str:
    manifest = [
        {"name": row["name"], "size_bytes": len(row["raw"]), "sha256": hashlib.sha256(row["raw"]).hexdigest()}
        for row in rows
    ]
    return module.digest(module.LOG_SET_DOMAIN, {"domain_id": domain_id, "logs": manifest})


def effects(command: str) -> dict:
    value = {
        "network_accessed": command not in {"PREFLIGHT", "STOP_OWNED_SERVICE_SET"},
        "listeners_started": 0, "listeners_stopped": 0,
        "service_processes_started": 0, "service_processes_stopped": 0,
        "faults_injected": 0, "spend_usd_cents": 0,
    }
    if command == "START_OWNED_CLUSTER_MEMBERS":
        value.update(listeners_started=4, service_processes_started=2)
    elif command == "STOP_OWNED_SERVICE_SET":
        value.update(service_processes_stopped=2, faults_injected=1)
    elif command == "RESTART_OWNED_SERVICE_SET":
        value.update(service_processes_started=2)
    elif command == "CLEANUP_OWNED_PROCESSES":
        value.update(listeners_stopped=4, service_processes_stopped=2)
    return value


class SyntheticBackend:
    synthetic_only = True

    def __init__(self, domain_id: str, log_digest: str, secret_frame_sha256: str):
        self.domain_id = domain_id
        self.log_digest = log_digest
        self.secret_frame_sha256 = secret_frame_sha256
        self.prefault_challenge = sha("transit-challenge")
        self.prefault_signature = sha("transit-signature")

    def result(self, command: str, observation: dict) -> dict:
        return {"observation": observation, "effects": effects(command)}

    def preflight(self, plan: dict) -> dict:
        return self.result("PREFLIGHT", {
            "tool_hash_set_verified": True, "credential_hash_and_key_match_verified": True,
            "owned_paths_private_and_empty": True, "exact_ports_available": True,
            "ambient_credentials_absent": True, "preflight_receipt_sha256": sha(f"preflight:{self.domain_id}"),
        })

    def start_owned_cluster_members(self, plan: dict) -> dict:
        leader = self.domain_id == "domain-1"
        return self.result("START_OWNED_CLUSTER_MEMBERS", {
            "etcd_process_started": True, "openbao_process_started": True,
            "owned_process_set_sha256": sha(f"process-set:{self.domain_id}"),
            "process_receipt_sha256": sha(f"process-receipt:{self.domain_id}"),
            "openbao_bootstrap_role": "LEADER_INITIALIZE_AND_HOLD_MEMORY_ONLY" if leader else "FOLLOWER_RETRY_JOIN_AND_UNSEAL",
            "secret_frame_action": "PRODUCED_MEMORY_ONLY" if leader else "CONSUMED_MEMORY_ONLY",
            "secret_frame_sha256": self.secret_frame_sha256, "secret_frame_persisted": False,
        })

    def query_cluster_state(self, plan: dict) -> dict:
        return self.result("QUERY_CLUSTER_STATE", {
            "etcd_member_count": 3, "etcd_voter_count": 3,
            "openbao_member_count": 3, "openbao_voter_count": 3,
            "local_etcd_healthy": True, "local_openbao_unsealed": True,
            "cluster_observation_sha256": sha(f"cluster:{self.domain_id}"),
        })

    def execute_authorize_consume(self, plan: dict) -> dict:
        return self.result("EXECUTE_AUTHORIZE_CONSUME", {
            "linearizable_authorize_consume_observed": True, "replay_consume_rejected": True,
            "authorized_value_sha256": plan["workload"]["authorized_unclaimed_value_sha256"],
            "consumed_value_sha256": plan["workload"]["consumed_value_sha256"],
            "consume_revision_sha256": sha("consume-revision"), "replay_revision_sha256": sha("replay-revision"),
        })

    def create_prefault_transit_signature(self, plan: dict) -> dict:
        return self.result("CREATE_PREFAULT_TRANSIT_SIGNATURE", {
            "prefault_transit_signature_created": True,
            "transit_challenge_sha256": self.prefault_challenge,
            "transit_signature_sha256": self.prefault_signature,
            "consumed_state_sha256": plan["workload"]["consumed_value_sha256"],
        })

    def stop_owned_service_set(self, plan: dict) -> dict:
        return self.result("STOP_OWNED_SERVICE_SET", {
            "target_domain_id": plan["role"]["fault_target_domain_id"],
            "etcd_process_stopped": True, "openbao_process_stopped": True,
            "stopped_owned_process_set_sha256": sha(f"stopped:{self.domain_id}"),
        })

    def verify_surviving_quorum_and_state(self, plan: dict) -> dict:
        return self.result("VERIFY_SURVIVING_QUORUM_AND_STATE", {
            "surviving_two_domain_etcd_quorum_observed": True,
            "surviving_two_domain_openbao_available": True, "prefault_state_match_verified": True,
            "survivor_observation_sha256": sha(f"survivor:{self.domain_id}"),
        })

    def verify_postfault_transit_signature(self, plan: dict) -> dict:
        return self.result("VERIFY_POSTFAULT_TRANSIT_SIGNATURE", {
            "postfault_transit_signature_verified": True,
            "transit_challenge_sha256": self.prefault_challenge,
            "transit_signature_sha256": self.prefault_signature,
        })

    def restart_owned_service_set(self, plan: dict) -> dict:
        return self.result("RESTART_OWNED_SERVICE_SET", {
            "target_domain_id": plan["role"]["fault_target_domain_id"],
            "etcd_process_restarted": True, "openbao_process_restarted": True,
            "restarted_owned_process_set_sha256": sha(f"restarted:{self.domain_id}"),
            "secret_frame_action": "CONSUMED_MEMORY_ONLY", "secret_frame_sha256": self.secret_frame_sha256,
            "secret_frame_persisted": False,
        })

    def verify_target_rejoin(self, plan: dict) -> dict:
        return self.result("VERIFY_TARGET_REJOIN", {
            "target_domain_id": plan["role"]["fault_target_domain_id"],
            "target_etcd_rejoined": True, "target_openbao_rejoined": True,
            "etcd_voter_count": 3, "openbao_voter_count": 3,
            "rejoin_observation_sha256": sha(f"rejoin:{self.domain_id}"),
        })

    def cleanup_owned_processes(self, plan: dict) -> dict:
        return self.result("CLEANUP_OWNED_PROCESSES", {
            "all_owned_processes_stopped": True, "all_owned_ports_released": True,
            "owned_process_log_set_sha256": self.log_digest, "owned_process_log_count": 4,
            "cleanup_receipt_sha256": sha(f"cleanup:{self.domain_id}"),
            "secret_value_scan_passed": True, "exact_secret_match_count": 0,
        })

    def terminal_status(self, plan: dict, previous_receipt_sha256: str) -> dict:
        return self.result("TERMINAL_STATUS", {
            "lifecycle_succeeded": True,
            "command_receipt_count": len(plan["command_policy"]["allowed_commands"]),
            "domain_evidence_head_sha256": previous_receipt_sha256,
        })


SEQUENCES = {
    "domain-1": [
        "PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE",
        "EXECUTE_AUTHORIZE_CONSUME", "CREATE_PREFAULT_TRANSIT_SIGNATURE",
        "VERIFY_SURVIVING_QUORUM_AND_STATE", "VERIFY_POSTFAULT_TRANSIT_SIGNATURE",
        "CLEANUP_OWNED_PROCESSES", "TERMINAL_STATUS",
    ],
    "domain-2": [
        "PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE",
        "VERIFY_SURVIVING_QUORUM_AND_STATE", "CLEANUP_OWNED_PROCESSES", "TERMINAL_STATUS",
    ],
    "domain-3": [
        "PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE",
        "STOP_OWNED_SERVICE_SET", "RESTART_OWNED_SERVICE_SET", "VERIFY_TARGET_REJOIN",
        "CLEANUP_OWNED_PROCESSES", "TERMINAL_STATUS",
    ],
}
OFFSETS = {
    "domain-1": [0, 3, 6, 9, 10, 12, 14, 17, 20],
    "domain-2": [1, 4, 7, 13, 18, 21],
    "domain-3": [2, 5, 8, 11, 15, 16, 19, 22],
}


def identity(root: Path, name: str) -> dict:
    return {
        "certificate_path": str(root / f"{name}.crt"), "private_key_path": str(root / f"{name}.key"),
        "certificate_sha256": sha(f"certificate:{root}:{name}"), "spki_sha256": sha(f"spki:{root}:{name}"),
        "private_key_spki_sha256": sha(f"spki:{root}:{name}"), "private_key_file_mode": "0600",
        "certificate_private_key_match_verified": True,
    }


def sign(payload_raw: bytes, private_key_path: Path) -> bytes:
    result = subprocess.run(
        [str(SSH_KEYGEN), "-Y", "sign", "-f", str(private_key_path), "-n", module.SIGNATURE_NAMESPACE],
        input=payload_raw, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        env={"LANG": "C", "LC_ALL": "C"},
    )
    assert result.returncode == 0 and result.stdout.startswith(b"-----BEGIN SSH SIGNATURE-----")
    return result.stdout


def expect_failure(action, expected: str) -> None:  # noqa: ANN001
    try:
        action()
    except module.SafeFailure as error:
        assert str(error) == expected, (str(error), expected)
        return
    raise AssertionError(f"unsafe evidence compiler input admitted: {expected}")


def expect_writer_failure(action, expected: str) -> None:  # noqa: ANN001
    try:
        action()
    except writer_module.SafeFailure as error:
        assert str(error) == expected, (str(error), expected)
        return
    raise AssertionError(f"unsafe evidence writer input admitted: {expected}")


with tempfile.TemporaryDirectory(prefix="t22-a1-evidence-kat-") as directory:
    root = Path(directory).resolve()
    keys: dict[str, tuple[Path, bytes, str]] = {}
    for domain_id in module.DOMAIN_IDS:
        private = root / f"{domain_id}-operator"
        result = subprocess.run(
            [str(SSH_KEYGEN), "-q", "-t", "ed25519", "-N", "", "-f", str(private)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        assert result.returncode == 0
        canonical_key, key_sha256 = public_key(private.with_suffix(".pub").read_bytes())
        keys[domain_id] = (private, canonical_key, key_sha256)

    logs = {
        domain_id: [
            {"name": name, "raw": f"synthetic {domain_id} {name}\n".encode()}
            for name in module.EXPECTED_LOG_NAMES
        ]
        for domain_id in module.DOMAIN_IDS
    }
    log_digests = {domain_id: log_set_digest(domain_id, rows) for domain_id, rows in logs.items()}
    secret_frame_sha256 = hashlib.sha256(transport_module.encode_secret_frame(bytearray(SECRET_RAW))).hexdigest()

    endpoint = {
        "source_commit": SOURCE_COMMIT, "run_id": RUN_ID, "content_sha256": sha("endpoint"),
        "domains": [
            {
                "domain_id": f"domain-{number}", "overlay_ip": f"100.64.50.{number}",
                "agent_control_port": 29000, "etcd_client_port": 2379, "etcd_peer_port": 2380,
                "openbao_api_port": 8200, "openbao_cluster_port": 8201,
                "bind_exact_overlay_ip_only": True, "public_listener_allowed": False,
            }
            for number in (1, 2, 3)
        ],
    }
    domain_bindings = [
        {
            "domain_id": domain_id, "attestation_packet_sha256": sha(f"attestation:{domain_id}"),
            "attestation_signature_sha256": sha(f"attestation-signature:{domain_id}"),
            "domain_public_key_sha256": keys[domain_id][2],
        }
        for domain_id in module.DOMAIN_IDS
    ]
    execution = {
        "source_commit": SOURCE_COMMIT, "run_id": RUN_ID, "content_sha256": sha("execution"),
        "expires_at": "2026-07-22T23:00:00Z",
        "private_runtime": {
            "private_endpoint_manifest_content_sha256": endpoint["content_sha256"],
            "runtime_credential_manifest_content_sha256": sha("credentials"),
            "credential_verifier_ssh_keygen_executable_path": str(SSH_KEYGEN),
            "credential_verifier_ssh_keygen_executable_sha256": hashlib.sha256(SSH_KEYGEN.read_bytes()).hexdigest(),
        },
        "topology": {"domains": [
            {
                "domain_id": f"domain-{number}",
                "role": "COORDINATOR_VOTER" if number == 1 else "PARTICIPANT_VOTER",
                "etcd_member": f"etcd-{number}", "openbao_member": f"bao-{number}",
            }
            for number in (1, 2, 3)
        ]},
        "fault": {"target_domain_id": "domain-3"},
        "authorization": {"maximum_runtime_seconds": 3600, "automatic_retry_allowed": False},
        "budget": {"maximum_spend_usd_cents": 0},
        "admission_bindings": {
            "admission_contract_sha256": sha("admission-contract"),
            "owner_decision_proposal_sha256": sha("proposal"),
            "exact_three_domain_attestation_packet_set_sha256": sha("attestation-set"),
            "domain_bindings": domain_bindings,
        },
        "network": {"peer_endpoint_set_sha256": sha("endpoint-set"), "acl_policy_receipt_sha256": sha("acl")},
        "artifact_scope": {"run_evidence_root": str(root / "run-evidence")},
    }
    Path(execution["artifact_scope"]["run_evidence_root"]).mkdir(mode=0o700)
    Path(execution["artifact_scope"]["run_evidence_root"]).chmod(0o700)

    readiness_packets = []
    for number in (1, 2, 3):
        domain_id = f"domain-{number}"
        domain_root = root / domain_id
        credentials = domain_root / "credentials"
        endpoint_row = endpoint["domains"][number - 1]
        coordinator = None if number != 1 else {
            "client_identity": identity(credentials, "coordinator"),
            "runtime_public_key_path": str(credentials / "coordinator-runtime.pub"),
            "runtime_private_key_path": str(credentials / "coordinator-runtime"),
        }
        coordinator_identity = identity(credentials, "coordinator")
        coordinator_trust = {
            "certificate_path": coordinator_identity["certificate_path"],
            "certificate_sha256": coordinator_identity["certificate_sha256"],
            "spki_sha256": coordinator_identity["spki_sha256"],
            "runtime_public_key_path": str(credentials / "coordinator-runtime.pub"),
            "runtime_public_key_sha256": sha("coordinator-runtime"),
        }
        readiness_packets.append({
            "source_commit": SOURCE_COMMIT, "run_id": RUN_ID, "domain_id": domain_id,
            "content_sha256": sha(f"readiness:{number}"),
            "bindings": {
                "private_endpoint_manifest_content_sha256": endpoint["content_sha256"],
                "runtime_credential_manifest_content_sha256": execution["private_runtime"]["runtime_credential_manifest_content_sha256"],
            },
            "endpoint_binding": {key: endpoint_row[key] for key in (
                "overlay_ip", "agent_control_port", "etcd_client_port", "etcd_peer_port",
                "openbao_api_port", "openbao_cluster_port",
            )},
            "toolchain": {"executables": [
                {"name": name, "path": str(root / "tools" / domain_id / name), "sha256": sha(f"tool:{number}:{name}")}
                for name in plan_module.TOOL_NAMES
            ]},
            "local_paths": {
                "domain_private_root": str(domain_root), "etcd_data_dir": str(domain_root / "etcd"),
                "openbao_data_dir": str(domain_root / "openbao"), "owned_logs_dir": str(domain_root / "logs"),
                "domain_evidence_dir": str(domain_root / "evidence"),
                "execution_reservation_dir": str(domain_root / "execution-reservations"),
            },
            "credential_placement": {
                "mode": "OWNER_MEDIATED_OUT_OF_BAND_EXACT_HASH_PLACEMENT", "all_paths_local_to_attested_host": True,
                "ca_certificate_path": str(credentials / "ca.crt"), "ca_certificate_sha256": sha(f"ca:{number}"),
                "domain_identity": identity(credentials, "domain"),
                "domain_operator_public_key_path": str(credentials / "domain-operator.pub"),
                "domain_operator_private_key_path": str(credentials / "domain-operator"),
                "coordinator_trust_material": coordinator_trust,
                "coordinator_material": coordinator,
            },
        })
    plans = [plan_module.build_plan(execution, endpoint, readiness) for readiness in readiness_packets]
    receipt_chains = {}
    for plan, readiness in zip(plans, readiness_packets, strict=True):
        domain_id = plan["domain_id"]
        executor = executor_module.FixedCommandExecutor(
            plan, execution, endpoint, readiness,
            SyntheticBackend(domain_id, log_digests[domain_id], secret_frame_sha256),
        )
        for command, offset in zip(SEQUENCES[domain_id], OFFSETS[domain_id], strict=True):
            executor.execute(command, NOW + timedelta(seconds=offset))
        receipt_chains[domain_id] = executor.receipts

    event_plan = module.resolve_event_plan(execution["fault"]["target_domain_id"])

    def make_signed_events(chains: dict[str, list[dict]]) -> list[dict]:
        receipt_map = {
            f"{domain_id}:{receipt['command']}": receipt
            for domain_id, chain in chains.items() for receipt in chain
        }
        domain_sequences = {domain_id: 0 for domain_id in module.DOMAIN_IDS}
        domain_heads = {domain_id: module.ZERO_SHA256 for domain_id in module.DOMAIN_IDS}
        values = []
        for domain_id, command, event_type in event_plan:
            binding = next(row for row in domain_bindings if row["domain_id"] == domain_id)
            payload = module.build_domain_event_payload(
                receipt_map[f"{domain_id}:{command}"], event_type,
                domain_sequences[domain_id], domain_heads[domain_id],
                binding["attestation_packet_sha256"], binding["domain_public_key_sha256"],
            )
            payload_raw = module.canonical(payload) + b"\n"
            values.append({"payload_raw": payload_raw, "signature_raw": sign(payload_raw, keys[domain_id][0])})
            domain_sequences[domain_id] += 1
            domain_heads[domain_id] = payload["content_sha256"]
        return values

    signed_events = make_signed_events(receipt_chains)

    admission = {
        "status": "AUTHORIZED_T22_A1_EXACT_OWNER_SIGNED_NONPRODUCTION_EXECUTION_ADMISSION",
        "run_id": RUN_ID, "source_commit": SOURCE_COMMIT,
        "execution_contract_sha256": execution["content_sha256"], "content_sha256": sha("admission"),
    }
    secret = bytearray(SECRET_RAW)
    result = module.compile_terminal_evidence(
        execution, admission, plans, receipt_chains, signed_events,
        {domain_id: row[1] for domain_id, row in keys.items()}, logs, [secret], 2, True,
    )
    assert secret == bytearray(len(secret))
    terminal = result["terminal_evidence"]
    assert len(result["coordinator_events"]) == len(module.EVENT_PLAN) == 21
    assert terminal["event_chain"]["event_count"] == 21
    assert terminal["event_chain"]["event_chain_head_sha256"] == result["coordinator_events"][-1]["event_sha256"]
    assert terminal["cluster_evidence"]["target_domain_rejoined"] is True
    assert terminal["cleanup"]["secret_value_scan_passed"] is True
    assert terminal["claims"]["production_admissible"] is False
    assert result["synthetic_only"] is True and result["persistent_outputs_created"] == 0

    domain_public_keys = {domain_id: row[1] for domain_id, row in keys.items()}
    publication = writer_module.persist_evidence_set(
        execution, result, signed_events, domain_public_keys, True,
    )
    assert publication["status"] == "PASS_T22_A1_PRIVATE_EVIDENCE_SET_ATOMICALLY_PUBLISHED"
    assert publication["artifact_file_count_including_manifest"] == 65
    assert publication["readback_and_signature_reverification_passed"] is True
    evidence_set = Path(execution["artifact_scope"]["run_evidence_root"]) / "evidence-set"
    persisted_manifest = writer_module.validate_persisted_set(
        evidence_set, execution, result, signed_events, domain_public_keys, True,
    )
    assert persisted_manifest["content_sha256"] == publication["evidence_manifest_content_sha256"]

    writer_negative_count = 0
    expect_writer_failure(
        lambda: writer_module.persist_evidence_set(
            execution, result, signed_events, domain_public_keys, True,
        ),
        "E_EVIDENCE_WRITER_OUTPUT_EXISTS",
    )
    writer_negative_count += 1

    wrong_writer_events = copy.deepcopy(signed_events)
    wrong_writer_events[0]["signature_raw"] = signed_events[1]["signature_raw"]
    wrong_writer_execution = copy.deepcopy(execution)
    wrong_writer_root = root / "wrong-writer-signature"
    wrong_writer_root.mkdir(mode=0o700)
    wrong_writer_execution["artifact_scope"]["run_evidence_root"] = str(wrong_writer_root)
    expect_writer_failure(
        lambda: writer_module.persist_evidence_set(
            wrong_writer_execution, result, wrong_writer_events, domain_public_keys, True,
        ),
        "E_EVIDENCE_DOMAIN_EVENT_SIGNATURE",
    )
    assert not (wrong_writer_root / ".evidence-set.publication-reserved.json").exists()
    writer_negative_count += 1

    unsafe_writer_execution = copy.deepcopy(execution)
    unsafe_writer_root = root / "unsafe-writer-root"
    unsafe_writer_root.mkdir(mode=0o755)
    unsafe_writer_execution["artifact_scope"]["run_evidence_root"] = str(unsafe_writer_root)
    expect_writer_failure(
        lambda: writer_module.persist_evidence_set(
            unsafe_writer_execution, result, signed_events, domain_public_keys, True,
        ),
        "E_EVIDENCE_WRITER_PRIVATE_DIRECTORY",
    )
    writer_negative_count += 1

    failed_writer_execution = copy.deepcopy(execution)
    failed_writer_root = root / "failed-writer-root"
    failed_writer_root.mkdir(mode=0o700)
    failed_writer_execution["artifact_scope"]["run_evidence_root"] = str(failed_writer_root)
    original_write_private_file = writer_module.write_private_file
    injected_write_count = [0]

    def fail_second_write(path: Path, raw: bytes) -> None:
        injected_write_count[0] += 1
        if injected_write_count[0] == 2:
            raise OSError("synthetic injected writer failure")
        original_write_private_file(path, raw)

    writer_module.write_private_file = fail_second_write
    try:
        expect_writer_failure(
            lambda: writer_module.persist_evidence_set(
                failed_writer_execution, result, signed_events, domain_public_keys, True,
            ),
            "E_EVIDENCE_WRITER_LOCAL_IO",
        )
    finally:
        writer_module.write_private_file = original_write_private_file
    assert (failed_writer_root / ".evidence-set.publication-reserved.json").is_file()
    assert not (failed_writer_root / "evidence-set").exists()
    assert not any(path.name.startswith(".evidence-set.staging-") for path in failed_writer_root.iterdir())
    writer_negative_count += 1

    negative_count = 0
    broken_coordinator_chain = copy.deepcopy(result["coordinator_events"])
    broken_coordinator_chain[1]["previous_event_sha256"] = sha("wrong-coordinator-previous")
    expect_failure(
        lambda: module.validate_coordinator_chain(broken_coordinator_chain, execution),
        "E_EVIDENCE_COORDINATOR_EVENT_CHAIN",
    )
    negative_count += 1

    forged_terminal = copy.deepcopy(terminal)
    forged_terminal["content_sha256"] = sha("forged-terminal")
    expect_failure(
        lambda: module.validate_terminal_value(
            forged_terminal, execution, len(result["coordinator_events"]),
            result["coordinator_events"][-1]["event_sha256"],
        ),
        "E_EVIDENCE_TERMINAL_DIGEST",
    )
    negative_count += 1

    expect_failure(
        lambda: module.compile_terminal_evidence(execution, admission, plans, receipt_chains, signed_events,
            {domain_id: row[1] for domain_id, row in keys.items()}, logs, [bytearray(SECRET_RAW)], 2, False),
        "E_EVIDENCE_SYNTHETIC_DECLARATION",
    )
    negative_count += 1

    bad_plan = copy.deepcopy(plans)
    bad_plan[0]["content_sha256"] = sha("bad-plan")
    expect_failure(
        lambda: module.compile_terminal_evidence(execution, admission, bad_plan, receipt_chains, signed_events,
            {domain_id: row[1] for domain_id, row in keys.items()}, logs, [bytearray(SECRET_RAW)], 2, True),
        "E_EVIDENCE_PLAN_DIGEST",
    )
    negative_count += 1

    bad_receipts = copy.deepcopy(receipt_chains)
    bad_receipts["domain-1"][0]["content_sha256"] = sha("forged-receipt")
    expect_failure(
        lambda: module.compile_terminal_evidence(execution, admission, plans, bad_receipts, signed_events,
            {domain_id: row[1] for domain_id, row in keys.items()}, logs, [bytearray(SECRET_RAW)], 2, True),
        "E_DOMAIN_EXECUTOR_RECEIPT_DIGEST",
    )
    negative_count += 1

    bad_keys = {domain_id: row[1] for domain_id, row in keys.items()}
    bad_keys["domain-1"] = keys["domain-2"][1]
    expect_failure(
        lambda: module.compile_terminal_evidence(execution, admission, plans, receipt_chains, signed_events,
            bad_keys, logs, [bytearray(SECRET_RAW)], 2, True),
        "E_EVIDENCE_DOMAIN_PUBLIC_KEY_BINDING",
    )
    negative_count += 1

    bad_logs = copy.deepcopy(logs)
    bad_logs["domain-1"][0]["raw"] += b"changed"
    expect_failure(
        lambda: module.compile_terminal_evidence(execution, admission, plans, receipt_chains, signed_events,
            {domain_id: row[1] for domain_id, row in keys.items()}, bad_logs, [bytearray(SECRET_RAW)], 2, True),
        "E_EVIDENCE_LOG_SET_BINDING",
    )
    negative_count += 1

    bad_signature_events = copy.deepcopy(signed_events)
    bad_signature_events[0]["signature_raw"] = signed_events[1]["signature_raw"]
    expect_failure(
        lambda: module.compile_terminal_evidence(execution, admission, plans, receipt_chains, bad_signature_events,
            {domain_id: row[1] for domain_id, row in keys.items()}, logs, [bytearray(SECRET_RAW)], 2, True),
        "E_EVIDENCE_DOMAIN_EVENT_SIGNATURE",
    )
    negative_count += 1

    bad_payload_events = copy.deepcopy(signed_events)
    payload = json.loads(bad_payload_events[0]["payload_raw"])
    payload["event_type"] = "DOMAIN_PROCESS_STARTED"
    payload.pop("content_sha256")
    payload["content_sha256"] = module.digest(module.DOMAIN_EVENT_DOMAIN, payload)
    bad_payload_events[0]["payload_raw"] = module.canonical(payload) + b"\n"
    bad_payload_events[0]["signature_raw"] = sign(bad_payload_events[0]["payload_raw"], keys["domain-1"][0])
    expect_failure(
        lambda: module.compile_terminal_evidence(execution, admission, plans, receipt_chains, bad_payload_events,
            {domain_id: row[1] for domain_id, row in keys.items()}, logs, [bytearray(SECRET_RAW)], 2, True),
        "E_EVIDENCE_DOMAIN_EVENT_RECONSTRUCTION",
    )
    negative_count += 1

    expect_failure(
        lambda: module.compile_terminal_evidence(execution, admission, plans, receipt_chains, signed_events[:-1],
            {domain_id: row[1] for domain_id, row in keys.items()}, logs, [bytearray(SECRET_RAW)], 2, True),
        "E_EVIDENCE_SIGNED_EVENT_SET",
    )
    negative_count += 1

    wrong_secret = bytearray(b"SYNTHETIC-WRONG-UNSEAL-SHARE")
    expect_failure(
        lambda: module.compile_terminal_evidence(execution, admission, plans, receipt_chains, signed_events,
            {domain_id: row[1] for domain_id, row in keys.items()}, logs, [wrong_secret], 2, True),
        "E_EVIDENCE_SECRET_FRAME_BINDING",
    )
    assert wrong_secret == bytearray(len(wrong_secret))
    negative_count += 1

    leaked_logs = copy.deepcopy(logs)
    leaked_logs["domain-1"][0]["raw"] = SECRET_RAW
    leaked_digest = log_set_digest("domain-1", leaked_logs["domain-1"])
    leak_receipts = copy.deepcopy(receipt_chains)
    cleanup_index = SEQUENCES["domain-1"].index("CLEANUP_OWNED_PROCESSES")
    leak_receipts["domain-1"][cleanup_index]["observation"]["owned_process_log_set_sha256"] = leaked_digest
    for index in range(cleanup_index, len(leak_receipts["domain-1"])):
        receipt = leak_receipts["domain-1"][index]
        if index > cleanup_index:
            receipt["previous_receipt_sha256"] = leak_receipts["domain-1"][index - 1]["content_sha256"]
            if receipt["command"] == "TERMINAL_STATUS":
                receipt["observation"]["domain_evidence_head_sha256"] = receipt["previous_receipt_sha256"]
        receipt.pop("content_sha256")
        receipt["content_sha256"] = executor_module.receipt_digest(receipt)
    leak_secret = bytearray(SECRET_RAW)
    leak_events = make_signed_events(leak_receipts)
    expect_failure(
        lambda: module.compile_terminal_evidence(execution, admission, plans, leak_receipts, leak_events,
            {domain_id: row[1] for domain_id, row in keys.items()}, leaked_logs, [leak_secret], 2, True),
        "E_EVIDENCE_SECRET_VALUE_LEAK",
    )
    assert leak_secret == bytearray(len(leak_secret))
    negative_count += 1

    expect_failure(lambda: module.decode_domain_event(b"{}\n"), "E_EVIDENCE_DOMAIN_EVENT_SHAPE")
    negative_count += 1
    expect_failure(lambda: module.canonical({"unsafe": 1.5}), "E_EVIDENCE_FLOAT_FORBIDDEN")
    negative_count += 1
    expect_failure(
        lambda: module.compile_terminal_evidence(execution, admission, plans, receipt_chains, signed_events,
            {domain_id: row[1] for domain_id, row in keys.items()}, logs, [bytearray(SECRET_RAW)], 301, True),
        "E_EVIDENCE_CLOCK_SKEW",
    )
    negative_count += 1

status = module.status()
assert status["status"] == "SIGNED_EVENT_COMPILER_AND_ATOMIC_WRITER_READY_EXACT_FINALIZER_PRESENT_REAL_ACTIVATION_CLOSED"
assert status["evidence_activation_ready"] is False
assert status["real_execution_or_receipt_inputs_read"] == status["real_domain_signatures_read"] == 0
assert status["real_secret_values_read"] == status["persistent_outputs_created"] == 0
assert status["network_accessed"] is False and status["listeners_started"] == status["processes_started"] == 0
assert status["services_started"] == status["faults_injected"] == status["spend_usd_cents"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False
writer_status = writer_module.status()
assert writer_status["status"] == "ATOMIC_PRIVATE_EVIDENCE_WRITER_READY_EXACT_RUNNER_FINALIZER_PRESENT_REAL_ACTIVATION_CLOSED"
assert writer_status["evidence_writer_activation_ready"] is False
assert writer_status["real_execution_or_signature_inputs_read"] == 0
assert writer_status["persistent_evidence_sets_created"] == 0
assert writer_status["network_accessed"] is False and writer_status["listeners_started"] == 0
assert writer_status["processes_started"] == writer_status["services_started"] == 0
assert writer_status["faults_injected"] == writer_status["spend_usd_cents"] == 0
assert writer_status["execution_authorized"] is False and writer_status["production_admissible"] is False

print("t22_a1_evidence_compiler_check\tpass")
print("synthetic_signed_source_domain_event_count\t21")
print("synthetic_coordinator_event_count\t21")
print("synthetic_terminal_evidence_count\t1")
print(f"directed_negative_test_count\t{negative_count}")
print("synthetic_atomic_evidence_set_count\t1")
print("synthetic_persisted_evidence_file_count\t65")
print(f"writer_directed_negative_test_count\t{writer_negative_count}")
print("real_execution_or_receipt_inputs_read\t0")
print("real_domain_signatures_read\t0")
print("real_secret_values_read\t0")
print("persistent_outputs_created\t0")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("processes_started\t0")
print("faults_injected\t0")
print("production_admissible\tfalse")
