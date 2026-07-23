"""Synthetic KATs for the T22-A1 authenticated domain lane."""
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
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_authenticated_domain_lane_v1.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    value = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


module = load("t22a1_authenticated_lane_kat", SOURCE)
plan_module = load(
    "t22a1_authenticated_lane_plan_kat",
    ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_workload_plan_v1.py",
)
executor_module = load(
    "t22a1_authenticated_lane_executor_kat",
    ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_executor_core_v1.py",
)
runner_module = load(
    "t22a1_authenticated_lane_runner_kat",
    ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_source_bound_runner_v1.py",
)
finalizer_module = load(
    "t22a1_authenticated_lane_exact_finalizer_kat",
    ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_exact_evidence_finalizer_v1.py",
)
transport_module = module.load_transport_module()

SOURCE_COMMIT = "a" * 40
RUN_ID = "t22-a1-20260722T230000.000000z-123456789abc"
EXECUTION_SHA256 = hashlib.sha256(b"T22_A1_AUTH_LANE_SYNTHETIC_EXECUTION").hexdigest()
NOW = datetime(2026, 7, 22, 23, 0, tzinfo=timezone.utc)


def sha(value: object) -> str:
    raw = value if isinstance(value, bytes) else str(value).encode()
    return hashlib.sha256(raw).hexdigest()


def expect_failure(action, expected: str) -> None:  # noqa: ANN001
    try:
        action()
    except (module.SafeFailure, RuntimeError) as error:
        assert str(error) == expected, (str(error), expected)
        return
    raise AssertionError(f"unsafe authenticated lane path admitted: {expected}")


assert module.status()["authenticated_domain_lane_activation_ready"] is False
expect_failure(
    lambda: module.CoordinatorBootstrapStore(),
    "E_AUTH_LANE_ACTIVATION_NOT_READY",
)


class Clock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self) -> datetime:
        self.value += timedelta(milliseconds=1)
        return self.value


clock = Clock()
ssh_keygen = Path(shutil.which("ssh-keygen") or "")
assert ssh_keygen.is_absolute() and ssh_keygen.is_file()
ssh_keygen_sha256 = hashlib.sha256(ssh_keygen.read_bytes()).hexdigest()


with tempfile.TemporaryDirectory(prefix="t22-a1-authenticated-lane-kat-") as directory:
    private_root = Path(directory).resolve()
    keys_root = private_root / "keys"
    keys_root.mkdir(mode=0o700)
    coordinator_key = keys_root / "coordinator-runtime"
    domain_keys = {domain_id: keys_root / f"{domain_id}-operator" for domain_id in ("domain-1", "domain-2", "domain-3")}
    for key in (coordinator_key, *domain_keys.values()):
        subprocess.run(
            [str(ssh_keygen), "-q", "-t", "ed25519", "-N", "", "-C", "T22_A1_SYNTHETIC_ONLY", "-f", str(key)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={"LANG": "C", "LC_ALL": "C"}, shell=False, check=True,
        )
        key.chmod(0o600)

    session_module = module.load_session_module()

    def public_sha(path: Path) -> str:
        _raw, digest = session_module.canonical_public_key(Path(str(path) + ".pub"))
        return digest

    coordinator_public_sha256 = public_sha(coordinator_key)
    domain_public_sha256 = {domain_id: public_sha(key) for domain_id, key in domain_keys.items()}

    endpoint = {
        "source_commit": SOURCE_COMMIT, "run_id": RUN_ID,
        "content_sha256": sha("endpoint-manifest"),
        "domains": [
            {
                "domain_id": f"domain-{number}", "hostname": f"synthetic-domain-{number}",
                "overlay_ip": f"100.64.70.{number}", "agent_control_port": 29000,
                "etcd_client_port": 2379, "etcd_peer_port": 2380,
                "openbao_api_port": 8200, "openbao_cluster_port": 8201,
                "bind_exact_overlay_ip_only": True, "public_listener_allowed": False,
            }
            for number in (1, 2, 3)
        ],
    }
    execution = {
        "source_commit": SOURCE_COMMIT, "run_id": RUN_ID, "content_sha256": EXECUTION_SHA256,
        "private_runtime": {
            "private_endpoint_manifest_content_sha256": endpoint["content_sha256"],
            "runtime_credential_manifest_content_sha256": sha("credential-manifest"),
            "credential_verifier_ssh_keygen_executable_path": str(ssh_keygen),
            "credential_verifier_ssh_keygen_executable_sha256": ssh_keygen_sha256,
        },
        "topology": {"domains": [
            {
                "domain_id": f"domain-{number}", "role": "COORDINATOR_AND_MEMBER" if number == 1 else "MEMBER",
                "etcd_member": f"etcd-{number}", "openbao_member": f"bao-{number}",
            }
            for number in (1, 2, 3)
        ]},
        "fault": {"target_domain_id": "domain-3"},
        "authorization": {"maximum_runtime_seconds": 3600, "automatic_retry_allowed": False},
        "budget": {"maximum_spend_usd_cents": 0},
        "admission_bindings": {
            "admission_contract_sha256": sha("admission-contract"),
            "owner_decision_proposal_sha256": sha("owner-proposal"),
            "exact_three_domain_attestation_packet_set_sha256": sha("attestation-set"),
            "domain_bindings": [
                {
                    "domain_id": domain_id,
                    "attestation_packet_sha256": sha(f"attestation:{number}"),
                    "attestation_signature_sha256": sha(f"attestation-signature:{number}"),
                    "domain_public_key_sha256": domain_public_sha256[domain_id],
                }
                for number, domain_id in enumerate(("domain-1", "domain-2", "domain-3"), start=1)
            ],
        },
        "network": {
            "peer_endpoint_set_sha256": sha("peer-endpoint-set"),
            "acl_policy_receipt_sha256": sha("acl-policy-receipt"),
        },
        "artifact_scope": {"run_evidence_root": str(private_root / "run-evidence")},
        "expires_at": "2026-07-23T00:00:00Z",
    }
    Path(execution["artifact_scope"]["run_evidence_root"]).mkdir(mode=0o700)
    Path(execution["artifact_scope"]["run_evidence_root"]).chmod(0o700)

    def identity(root: Path, name: str) -> dict:
        return {
            "certificate_path": str(root / f"{name}.crt"),
            "private_key_path": str(root / f"{name}.key"),
            "certificate_sha256": sha(f"certificate:{root}:{name}"),
            "spki_sha256": sha(f"spki:{root}:{name}"),
            "private_key_spki_sha256": sha(f"spki:{root}:{name}"),
            "private_key_file_mode": "0600", "certificate_private_key_match_verified": True,
        }

    def readiness(number: int) -> dict:
        domain_id = f"domain-{number}"
        root = private_root / domain_id
        credentials = root / "credentials"
        row = endpoint["domains"][number - 1]
        coordinator_identity = identity(credentials, "coordinator")
        coordinator = None if number != 1 else {
            "client_identity": coordinator_identity,
            "runtime_public_key_path": str(coordinator_key) + ".pub",
            "runtime_private_key_path": str(coordinator_key),
            "runtime_public_key_sha256": coordinator_public_sha256,
            "runtime_private_key_file_mode": "0600", "runtime_key_pair_verified": True,
        }
        return {
            "source_commit": SOURCE_COMMIT, "run_id": RUN_ID, "domain_id": domain_id,
            "content_sha256": sha(f"readiness:{number}"),
            "bindings": {
                "domain_attestation_packet_sha256": sha(f"attestation:{number}"),
                "private_endpoint_manifest_content_sha256": endpoint["content_sha256"],
                "runtime_credential_manifest_content_sha256": execution["private_runtime"]["runtime_credential_manifest_content_sha256"],
            },
            "endpoint_binding": {key: row[key] for key in (
                "overlay_ip", "agent_control_port", "etcd_client_port", "etcd_peer_port",
                "openbao_api_port", "openbao_cluster_port",
            )},
            "toolchain": {"executables": [
                {
                    "name": name,
                    "path": str(ssh_keygen) if name == "ssh-keygen" else str(private_root / "tools" / domain_id / name),
                    "sha256": ssh_keygen_sha256 if name == "ssh-keygen" else sha(f"tool:{number}:{name}"),
                }
                for name in plan_module.TOOL_NAMES
            ]},
            "local_paths": {
                "domain_private_root": str(root), "etcd_data_dir": str(root / "etcd"),
                "openbao_data_dir": str(root / "openbao"), "owned_logs_dir": str(root / "logs"),
                "domain_evidence_dir": str(root / "evidence"),
                "execution_reservation_dir": str(root / "execution-reservations"),
            },
            "credential_placement": {
                "mode": "OWNER_MEDIATED_OUT_OF_BAND_EXACT_HASH_PLACEMENT",
                "all_paths_local_to_attested_host": True,
                "ca_certificate_path": str(credentials / "ca.crt"),
                "ca_certificate_sha256": sha("shared-ca"),
                "domain_identity": identity(credentials, "domain"),
                "domain_operator_public_key_path": str(domain_keys[domain_id]) + ".pub",
                "domain_operator_private_key_path": str(domain_keys[domain_id]),
                "domain_operator_public_key_sha256": domain_public_sha256[domain_id],
                "domain_operator_private_key_file_mode": "0600",
                "coordinator_trust_material": {
                    "certificate_path": coordinator_identity["certificate_path"],
                    "certificate_sha256": coordinator_identity["certificate_sha256"],
                    "spki_sha256": coordinator_identity["spki_sha256"],
                    "runtime_public_key_path": str(coordinator_key) + ".pub",
                    "runtime_public_key_sha256": coordinator_public_sha256,
                },
                "coordinator_material": coordinator,
            },
        }

    readiness_packets = [readiness(number) for number in (1, 2, 3)]
    plans = [plan_module.build_plan(execution, endpoint, packet) for packet in readiness_packets]

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
            value.update(listeners_started=4, service_processes_started=2)
        elif command == "CLEANUP_OWNED_PROCESSES":
            value.update(listeners_stopped=4, service_processes_stopped=2)
        return value

    class RealFakeBackend:
        synthetic_only = False

        def __init__(self, plan: dict, exchange: module.ServerBootstrapExchange, fail_preflight: bool = False) -> None:
            self.plan, self.exchange, self.fail_preflight = plan, exchange, fail_preflight
            self.prefault_challenge, self.prefault_signature = sha("challenge"), sha("signature")
            self.abort_count = 0

        def result(self, command: str, observation: dict) -> dict:
            return {"observation": observation, "effects": effects(command)}

        def preflight(self, _plan: dict) -> dict:
            if self.fail_preflight:
                raise RuntimeError("E_SYNTHETIC_DIRECTED_BACKEND_FAILURE")
            return self.result("PREFLIGHT", {
                "tool_hash_set_verified": True, "credential_hash_and_key_match_verified": True,
                "owned_paths_private_and_empty": True, "exact_ports_available": True,
                "ambient_credentials_absent": True, "preflight_receipt_sha256": sha(f"preflight:{self.plan['domain_id']}"),
            })

        def start_owned_cluster_members(self, _plan: dict) -> dict:
            leader = self.plan["domain_id"] == "domain-1"
            if leader:
                frame_sha256 = self.exchange.publish(bytearray(b"synthetic-memory-only-openbao-bootstrap-bundle"))
            else:
                secret, frame_sha256 = self.exchange.consume()
                transport_module.zeroize(secret)
            return self.result("START_OWNED_CLUSTER_MEMBERS", {
                "etcd_process_started": True, "openbao_process_started": True,
                "owned_process_set_sha256": sha(f"processes:{self.plan['domain_id']}"),
                "process_receipt_sha256": sha(f"start:{self.plan['domain_id']}"),
                "openbao_bootstrap_role": "LEADER_INITIALIZE_AND_HOLD_MEMORY_ONLY" if leader else "FOLLOWER_RETRY_JOIN_AND_UNSEAL",
                "secret_frame_action": "PRODUCED_MEMORY_ONLY" if leader else "CONSUMED_MEMORY_ONLY",
                "secret_frame_sha256": frame_sha256, "secret_frame_persisted": False,
            })

        def query_cluster_state(self, _plan: dict) -> dict:
            return self.result("QUERY_CLUSTER_STATE", {
                "etcd_member_count": 3, "etcd_voter_count": 3,
                "openbao_member_count": 3, "openbao_voter_count": 3,
                "local_etcd_healthy": True, "local_openbao_unsealed": True,
                "cluster_observation_sha256": sha(f"cluster:{self.plan['domain_id']}"),
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
                "stopped_owned_process_set_sha256": sha(f"stopped:{self.plan['domain_id']}"),
            })

        def verify_surviving_quorum_and_state(self, _plan: dict) -> dict:
            return self.result("VERIFY_SURVIVING_QUORUM_AND_STATE", {
                "surviving_two_domain_etcd_quorum_observed": True,
                "surviving_two_domain_openbao_available": True, "prefault_state_match_verified": True,
                "survivor_observation_sha256": sha(f"survivor:{self.plan['domain_id']}"),
            })

        def verify_postfault_transit_signature(self, _plan: dict) -> dict:
            return self.result("VERIFY_POSTFAULT_TRANSIT_SIGNATURE", {
                "postfault_transit_signature_verified": True,
                "transit_challenge_sha256": self.prefault_challenge,
                "transit_signature_sha256": self.prefault_signature,
            })

        def restart_owned_service_set(self, plan: dict) -> dict:
            secret, frame_sha256 = self.exchange.consume()
            transport_module.zeroize(secret)
            return self.result("RESTART_OWNED_SERVICE_SET", {
                "target_domain_id": plan["role"]["fault_target_domain_id"],
                "etcd_process_restarted": True, "openbao_process_restarted": True,
                "restarted_owned_process_set_sha256": sha(f"restarted:{self.plan['domain_id']}"),
                "secret_frame_action": "CONSUMED_MEMORY_ONLY", "secret_frame_sha256": frame_sha256,
                "secret_frame_persisted": False,
            })

        def verify_target_rejoin(self, plan: dict) -> dict:
            return self.result("VERIFY_TARGET_REJOIN", {
                "target_domain_id": plan["role"]["fault_target_domain_id"],
                "target_etcd_rejoined": True, "target_openbao_rejoined": True,
                "etcd_voter_count": 3, "openbao_voter_count": 3,
                "rejoin_observation_sha256": sha(f"rejoin:{self.plan['domain_id']}"),
            })

        def cleanup_owned_processes(self, _plan: dict) -> dict:
            logs = self.evidence_logs()
            return self.result("CLEANUP_OWNED_PROCESSES", {
                "all_owned_processes_stopped": True, "all_owned_ports_released": True,
                "owned_process_log_set_sha256": module.evidence_log_set_sha256(self.plan["domain_id"], logs),
                "owned_process_log_count": 4, "cleanup_receipt_sha256": sha(f"cleanup:{self.plan['domain_id']}"),
                "secret_value_scan_passed": True, "exact_secret_match_count": 0,
            })

        def evidence_logs(self) -> list[dict]:
            return [
                {"name": name, "raw": f"T22_A1_SYNTHETIC_ONLY:{self.plan['domain_id']}:{name}\n".encode()}
                for name in transport_module.EXPECTED_LOG_NAMES
            ]

        def terminal_status(self, plan: dict, previous_receipt_sha256: str) -> dict:
            return self.result("TERMINAL_STATUS", {
                "lifecycle_succeeded": True,
                "command_receipt_count": len(plan["command_policy"]["allowed_commands"]),
                "domain_evidence_head_sha256": previous_receipt_sha256,
            })

        def abort_cleanup(self) -> dict:
            self.abort_count += 1
            return {"all_owned_processes_cleaned": True, "all_owned_ports_released": True}

    class MemoryRoundTrip:
        def __init__(self, core: module.DomainAgentCore) -> None:
            self.core, self.closed = core, False
            self.exchange_count = 0

        def exchange(
            self, request_frame: bytes, incoming_secret_frame: bytes | None,
            expect_outgoing_secret: bool, expect_log_bundle: bool,
        ):  # noqa: ANN201
            assert not self.closed
            self.exchange_count += 1
            reply = self.core.handle(request_frame, incoming_secret_frame, clock())
            outgoing = bytes(reply.outgoing_secret_frame) if reply.outgoing_secret_frame is not None else None
            log_bundle = reply.log_bundle_frame
            reply.clear_secret()
            if outgoing is not None:
                assert expect_outgoing_secret
            if log_bundle is not None:
                assert expect_log_bundle
            return reply.response_frame, outgoing, log_bundle, clock()

        def close(self) -> None:
            self.closed = True

    module.AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY = True
    executor_module.EXECUTOR_ACTIVATION_READY = True
    bootstrap_store = module.CoordinatorBootstrapStore()
    evidence_collector = module.EvidenceCollector("domain-3")
    cores: dict[str, module.DomainAgentCore] = {}
    lanes: dict[str, module.AuthenticatedDomainLane] = {}
    backends: dict[str, RealFakeBackend] = {}
    for plan, packet in zip(plans, readiness_packets, strict=True):
        exchange = module.ServerBootstrapExchange()
        backend = RealFakeBackend(plan, exchange)
        executor = executor_module.FixedCommandExecutor(plan, execution, endpoint, packet, backend)
        core = module.DomainAgentCore(
            plan, packet, executor, backend, exchange,
            Path(str(coordinator_key) + ".pub"), Path(str(domain_keys[plan["domain_id"]]) + ".pub"),
            domain_keys[plan["domain_id"]], clock,
        )
        roundtrip = MemoryRoundTrip(core)
        lane = module.AuthenticatedDomainLane(
            plans[0], plan, packet,
            Path(str(coordinator_key) + ".pub"), coordinator_key,
            Path(str(domain_keys[plan["domain_id"]]) + ".pub"), roundtrip,
            bootstrap_store, evidence_collector, clock,
        )
        cores[plan["domain_id"]], lanes[plan["domain_id"]], backends[plan["domain_id"]] = core, lane, backend

    admission = {
        "status": "AUTHORIZED_T22_A1_EXACT_OWNER_SIGNED_NONPRODUCTION_EXECUTION_ADMISSION",
        "run_id": RUN_ID, "source_commit": SOURCE_COMMIT,
        "execution_contract_sha256": EXECUTION_SHA256,
        "content_sha256": sha("synthetic-admission"),
    }
    runner_module.RUNNER_ACTIVATION_READY = True
    finalizer_module.EXACT_EVIDENCE_FINALIZER_ACTIVATION_READY = True
    finalizer_compiler = finalizer_module.load_compiler_module()
    finalizer_writer = finalizer_module.load_writer_module()
    finalizer_compiler.EVIDENCE_ACTIVATION_READY = True
    finalizer_writer.EVIDENCE_WRITER_ACTIVATION_READY = True
    exact_finalizer = finalizer_module.ExactEvidenceFinalizer(
        evidence_collector, bootstrap_store,
        {domain_id: Path(str(key) + ".pub").read_bytes() for domain_id, key in domain_keys.items()},
        False,
    )
    runner_result = runner_module.run_source_bound(
        execution, admission, endpoint, readiness_packets,
        lambda plan, _packet: lanes[plan["domain_id"]],
        exact_finalizer,
        clock, False,
    )
    runner_module.RUNNER_ACTIVATION_READY = False
    finalizer_module.EXACT_EVIDENCE_FINALIZER_ACTIVATION_READY = False
    finalizer_compiler.EVIDENCE_ACTIVATION_READY = False
    finalizer_writer.EVIDENCE_WRITER_ACTIVATION_READY = False
    assert runner_result["status"] == "PASS_T22_A1_TERMINAL_EVIDENCE_READY", runner_result
    assert sum(lane.receipt_sequence for lane in lanes.values()) == 23
    evidence_collector.validate_complete()
    assert len(evidence_collector.signed_events) == 21 and len(evidence_collector.log_sets) == 3
    assert evidence_collector.maximum_observed_clock_skew_seconds == 1
    # The exact finalizer retained the one memory-only value through cleanup,
    # scanned it against all evidence, and zeroized it before publication.
    assert bootstrap_store.frame is None and bootstrap_store.frame_sha256 is None and bootstrap_store.secret is None
    evidence_set = Path(execution["artifact_scope"]["run_evidence_root"]) / "evidence-set"
    assert evidence_set.is_dir() and len([path for path in evidence_set.rglob("*") if path.is_file()]) == 65
    terminal_evidence = json.loads((evidence_set / "terminal-evidence.json").read_bytes())
    assert terminal_evidence["timing"]["maximum_observed_clock_skew_seconds"] == 1
    expect_failure(
        lambda: exact_finalizer(execution, admission, plans, {}, []),
        "E_EXACT_FINALIZER_SINGLE_ATTEMPT",
    )
    for plan in plans:
        chain = executor_module.validate_receipt_chain(
            cores[plan["domain_id"]].executor.receipts, plan,
        )
        assert chain["state"] == "TERMINAL_SUCCEEDED" and chain["synthetic_backend"] is False
        assert lanes[plan["domain_id"]].session.state == "TERMINAL_SUCCEEDED"
        assert cores[plan["domain_id"]].session.state == "TERMINAL_SUCCEEDED"
        assert lanes[plan["domain_id"]].abort_cleanup() == {
            "all_owned_processes_cleaned": True, "all_owned_ports_released": True,
        }
    negative_count = 0
    expect_failure(
        lambda: evidence_collector.record_clock_observation(
            NOW, module.utc_text(NOW + timedelta(seconds=301)), NOW + timedelta(seconds=1),
        ),
        "E_AUTH_LANE_CLOCK_SKEW",
    )
    negative_count += 1
    expect_failure(
        lambda: module.request_payload(plans[0], "PREFLIGHT", "NORMAL", sha("unexpected")),
        "E_AUTH_LANE_SECRET_BINDING",
    )
    negative_count += 1
    expect_failure(
        lambda: module.request_payload(plans[1], "START_OWNED_CLUSTER_MEMBERS", "NORMAL", None),
        "E_AUTH_LANE_SECRET_BINDING",
    )
    negative_count += 1
    expect_failure(
        lambda: module.request_payload(plans[0], "PREFLIGHT", "EMERGENCY_CLEANUP", None),
        "E_AUTH_LANE_EMERGENCY_COMMAND",
    )
    negative_count += 1
    bad_cleanup = module.emergency_cleanup_payload(plans[0], {
        "all_owned_processes_cleaned": False, "all_owned_ports_released": True,
    })
    expect_failure(lambda: module.validate_cleanup_payload(bad_cleanup, plans[0]), "E_AUTH_LANE_CLEANUP_PAYLOAD_BINDING")
    negative_count += 1
    expect_failure(
        lambda: module.SshSigTool(str(ssh_keygen), sha("wrong-tool")),
        "E_AUTH_LANE_SSH_KEYGEN_BINDING",
    )
    negative_count += 1

    isolated_store = module.CoordinatorBootstrapStore()
    secret_frame = transport_module.encode_secret_frame(bytearray(b"synthetic-directed-bootstrap-value"))
    secret_frame_sha256 = hashlib.sha256(secret_frame).hexdigest()
    isolated_store.capture(secret_frame, secret_frame_sha256)
    assert isolated_store.frame is not None
    isolated_store.frame[-1] ^= 1
    expect_failure(isolated_store.outbound, "E_AUTH_LANE_COORDINATOR_BOOTSTRAP_MUTATED")
    negative_count += 1
    isolated_store.clear()

    def fresh_failure_lane():  # noqa: ANN202
        plan, packet = plans[0], readiness_packets[0]
        exchange = module.ServerBootstrapExchange()
        backend = RealFakeBackend(plan, exchange, fail_preflight=True)
        executor = executor_module.FixedCommandExecutor(plan, execution, endpoint, packet, backend)
        core = module.DomainAgentCore(
            plan, packet, executor, backend, exchange,
            Path(str(coordinator_key) + ".pub"), Path(str(domain_keys["domain-1"]) + ".pub"),
            domain_keys["domain-1"], clock,
        )
        lane = module.AuthenticatedDomainLane(
            plans[0], plan, packet,
            Path(str(coordinator_key) + ".pub"), coordinator_key,
            Path(str(domain_keys["domain-1"]) + ".pub"), MemoryRoundTrip(core),
            module.CoordinatorBootstrapStore(), module.EvidenceCollector("domain-3"), clock,
        )
        return lane, core, backend

    failure_lane, failure_core, failure_backend = fresh_failure_lane()
    expect_failure(
        lambda: failure_lane.dispatch("PREFLIGHT", clock()),
        "E_DOMAIN_EXECUTOR_BACKEND_FAILURE",
    )
    assert failure_lane.remote_cleanup_confirmed is True
    assert failure_core.session.state == "TERMINAL_FAILED" and failure_backend.abort_count == 1
    negative_count += 1

    emergency_lane, emergency_core, emergency_backend = fresh_failure_lane()
    emergency_backend.fail_preflight = False
    emergency_lane.dispatch("PREFLIGHT", clock())
    assert emergency_lane.abort_cleanup() == {
        "all_owned_processes_cleaned": True, "all_owned_ports_released": True,
    }
    assert emergency_lane.session.state == "TERMINAL_FAILED"
    assert emergency_core.session.state == "TERMINAL_FAILED" and emergency_backend.abort_count == 1

    # A detached signature mutation is rejected before the executor is called.
    plan, packet = plans[0], readiness_packets[0]
    exchange = module.ServerBootstrapExchange()
    backend = RealFakeBackend(plan, exchange)
    executor = executor_module.FixedCommandExecutor(plan, execution, endpoint, packet, backend)
    core = module.DomainAgentCore(
        plan, packet, executor, backend, exchange,
        Path(str(coordinator_key) + ".pub"), Path(str(domain_keys["domain-1"]) + ".pub"),
        domain_keys["domain-1"], clock,
    )
    tool = module.SshSigTool(str(ssh_keygen), ssh_keygen_sha256)
    coordinator_session = module.SessionMachine(
        plan, Path(str(coordinator_key) + ".pub"), coordinator_public_sha256,
        Path(str(domain_keys["domain-1"]) + ".pub"), domain_public_sha256["domain-1"], tool,
    )
    valid_frame = coordinator_session.build_request(
        "PREFLIGHT", module.request_payload(plan, "PREFLIGHT", "NORMAL", None),
        clock(), coordinator_key,
    )
    decoded = transport_module.decode_message_frame(
        valid_frame, "COORDINATOR_TO_DOMAIN", "domain-1", RUN_ID, SOURCE_COMMIT, EXECUTION_SHA256,
    )
    bad_signature = bytearray(decoded["signature_raw"])
    body_index = bad_signature.find(b"\n") + 1
    assert body_index > 0 and bad_signature[body_index] not in b"\r\n-"
    bad_signature[body_index] = ord("A") if bad_signature[body_index] != ord("A") else ord("B")
    tampered_frame = transport_module.encode_message_frame(
        "COORDINATOR_TO_DOMAIN", "domain-1", decoded["message_raw"],
        bytes(bad_signature), decoded["payload_raw"],
    )
    expect_failure(lambda: core.prepare(tampered_frame, clock()), "E_AUTH_LANE_SIGNATURE_INVALID")
    assert executor.receipts == []
    negative_count += 1

    route = module.coordinator_route_plan(plans[2], endpoint)
    assert route["domain_id"] == "domain-1" and route["network"]["agent_control_endpoint"] == "https://100.64.70.1:29000"
    bad_endpoint = copy.deepcopy(endpoint)
    bad_endpoint["domains"] = bad_endpoint["domains"][1:]
    expect_failure(lambda: module.coordinator_route_plan(plans[2], bad_endpoint), "E_AUTH_LANE_ENDPOINT_SET")
    negative_count += 1

    module.AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY = False
    executor_module.EXECUTOR_ACTIVATION_READY = False

assert module.status()["authenticated_domain_lane_activation_ready"] is False
assert finalizer_module.status()["exact_evidence_finalizer_activation_ready"] is False
print("t22_a1_authenticated_domain_lane_check\tpass")
print("signed_fixed_command_roundtrip_count\t23")
print("memory_only_bootstrap_publish_count\t1")
print("memory_only_bootstrap_consume_count\t3")
print("signed_emergency_cleanup_count\t1")
print("kat_exact_evidence_finalization_count\t1")
print("kat_atomic_evidence_file_count\t65")
print("kat_maximum_observed_clock_skew_seconds\t1")
print(f"directed_negative_test_count\t{negative_count}")
print("real_private_inputs_read\t0")
print("real_certificate_or_key_files_read\t0")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("service_processes_started\t0")
print("faults_injected\t0")
print("secret_frames_persisted\t0")
print("production_admissible\tfalse")
