"""Offline KATs for the T22-A1 exact coordinator/domain launch binding."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_exact_launch_binding_v1.py"
spec = importlib.util.spec_from_file_location("t22a1_exact_launch_binding_kat", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

SOURCE_COMMIT = "a" * 40
RUN_ID = "t22-a1-20260722T235000.000000z-123456789abc"
NOW = datetime(2026, 7, 22, 23, 50, tzinfo=timezone.utc)


def sha(label: str) -> str:
    return hashlib.sha256(f"T22_A1_EXACT_LAUNCH_SYNTHETIC:{label}".encode()).hexdigest()


def expect_failure(action, expected: str) -> None:  # noqa: ANN001
    try:
        action()
    except module.SafeFailure as error:
        assert str(error) == expected, (str(error), expected)
        return
    raise AssertionError(f"unsafe exact launch input admitted: {expected}")


assert module.status()["exact_launch_binding_activation_ready"] is False
missing = Path("/synthetic/not-opened")
expect_failure(
    lambda: module.serve_domain_agent(
        "domain-1", missing, missing, missing, missing, missing, missing,
        SOURCE_COMMIT,
    ),
    "E_EXACT_LAUNCH_ACTIVATION_NOT_READY",
)
expect_failure(
    lambda: module.run_coordinator(
        missing, missing, missing, missing, missing, missing, missing,
        SOURCE_COMMIT,
    ),
    "E_EXACT_LAUNCH_ACTIVATION_NOT_READY",
)
negative_count = 2

ssh_keygen = Path(shutil.which("ssh-keygen") or "").resolve()
assert ssh_keygen.is_file()
ssh_keygen_sha256 = hashlib.sha256(ssh_keygen.read_bytes()).hexdigest()

with tempfile.TemporaryDirectory(prefix="t22-a1-exact-launch-kat-") as directory:
    root = Path(directory).resolve()
    root.chmod(0o700)
    reservation_root = root / "reservations"
    reservation_root.mkdir(mode=0o700)
    private_key = root / "domain-1-operator"
    subprocess.run(
        [str(ssh_keygen), "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={"LANG": "C", "LC_ALL": "C"}, shell=False, check=True,
    )
    private_key.chmod(0o600)
    public_key = Path(str(private_key) + ".pub")
    session = module.load_lane_module().load_session_module()
    _canonical_public, public_key_sha256 = session.canonical_public_key(public_key)

    endpoint = {
        "content_sha256": sha("endpoint"),
        "domains": [
            {
                "domain_id": f"domain-{number}", "overlay_ip": f"100.64.90.{number}",
                "agent_control_port": 29000, "etcd_client_port": 2379,
                "etcd_peer_port": 2380, "openbao_api_port": 8200,
                "openbao_cluster_port": 8201,
            }
            for number in (1, 2, 3)
        ],
    }
    packet = {
        "source_commit": SOURCE_COMMIT, "run_id": RUN_ID, "domain_id": "domain-1",
        "collected_at": module.utc_text(NOW - timedelta(minutes=1)),
        "expires_at": module.utc_text(NOW + timedelta(minutes=10)),
        "bindings": {
            "domain_attestation_packet_sha256": sha("attestation:domain-1"),
            "private_endpoint_manifest_content_sha256": endpoint["content_sha256"],
            "runtime_credential_manifest_content_sha256": sha("credential"),
        },
        "endpoint_binding": dict(endpoint["domains"][0]),
        "toolchain": {"executables": [{
            "name": "ssh-keygen", "path": str(ssh_keygen), "sha256": ssh_keygen_sha256,
        }]},
        "local_paths": {"execution_reservation_dir": str(reservation_root)},
        "credential_placement": {
            "domain_operator_public_key_path": str(public_key),
            "domain_operator_private_key_path": str(private_key),
            "coordinator_trust_material": {"runtime_public_key_path": str(root / "coordinator.pub")},
        },
        "signature_binding": {"signer_public_key_sha256": public_key_sha256},
    }
    readiness_module = module.load_readiness_module()
    packet["content_sha256"] = readiness_module.digest(packet)
    packet_raw = readiness_module.canonical(packet) + b"\n"
    signature_path = root / "domain-1.json.sig"
    result = subprocess.run(
        [str(ssh_keygen), "-Y", "sign", "-f", str(private_key),
         "-n", readiness_module.SIGNATURE_NAMESPACE],
        input=packet_raw, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        env={"LANG": "C", "LC_ALL": "C"}, shell=False, check=False,
    )
    assert result.returncode == 0 and result.stdout.startswith(b"-----BEGIN SSH SIGNATURE-----")
    signature_path.write_bytes(result.stdout)
    signature_path.chmod(0o600)
    signature_sha256 = hashlib.sha256(result.stdout).hexdigest()

    execution = {
        "source_commit": SOURCE_COMMIT, "run_id": RUN_ID,
        "content_sha256": sha("execution"),
        "expires_at": module.utc_text(NOW + timedelta(minutes=5)),
        "private_runtime": {
            "private_endpoint_manifest_content_sha256": endpoint["content_sha256"],
            "runtime_credential_manifest_content_sha256": sha("credential"),
        },
        "runtime_admission": {
            "packet_bindings": [
                {"domain_id": domain_id, "readiness_packet_sha256": packet["content_sha256"] if domain_id == "domain-1" else sha(f"readiness:{domain_id}")}
                for domain_id in module.DOMAIN_IDS
            ],
            "signature_bindings": [
                {
                    "domain_id": domain_id,
                    "signature_sha256": signature_sha256 if domain_id == "domain-1" else sha(f"signature:{domain_id}"),
                    "public_key_sha256": public_key_sha256 if domain_id == "domain-1" else sha(f"key:{domain_id}"),
                }
                for domain_id in module.DOMAIN_IDS
            ],
        },
        "admission_bindings": {"domain_bindings": [
            {
                "domain_id": domain_id,
                "attestation_packet_sha256": sha(f"attestation:{domain_id}"),
                "domain_public_key_sha256": public_key_sha256 if domain_id == "domain-1" else sha(f"key:{domain_id}"),
            }
            for domain_id in module.DOMAIN_IDS
        ]},
    }
    lane_module = module.load_lane_module()
    lane_module.AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY = True
    validated = module.validate_readiness_launch_binding(
        packet, packet_raw, signature_path, public_key,
        "domain-1", execution, endpoint, NOW,
    )
    assert validated == packet

    bad_endpoint = copy.deepcopy(endpoint)
    bad_endpoint["domains"][0]["overlay_ip"] = "100.64.90.99"
    expect_failure(
        lambda: module.validate_readiness_launch_binding(
            packet, packet_raw, signature_path, public_key,
            "domain-1", execution, bad_endpoint, NOW,
        ),
        "E_EXACT_LAUNCH_READINESS_ENDPOINT",
    )
    negative_count += 1
    expect_failure(
        lambda: module.validate_readiness_launch_binding(
            packet, packet_raw, signature_path, public_key,
            "domain-1", execution, endpoint, NOW + timedelta(minutes=11),
        ),
        "E_EXACT_LAUNCH_READINESS_CURRENT",
    )
    negative_count += 1
    bad_signature = bytearray(result.stdout)
    body = bad_signature.find(b"\n") + 1
    bad_signature[body] = ord("A") if bad_signature[body] != ord("A") else ord("B")
    signature_path.write_bytes(bad_signature)
    expect_failure(
        lambda: module.validate_readiness_launch_binding(
            packet, packet_raw, signature_path, public_key,
            "domain-1", execution, endpoint, NOW,
        ),
        "E_AUTH_LANE_SIGNATURE_INVALID",
    )
    negative_count += 1
    signature_path.write_bytes(result.stdout)

    admission = {"content_sha256": sha("admission")}
    terminal_path = module.reserve_domain_launch(execution, admission, packet, NOW)
    assert terminal_path == reservation_root / f"{admission['content_sha256']}.domain-agent.terminal.json"
    expect_failure(
        lambda: module.reserve_domain_launch(execution, admission, packet, NOW),
        "E_EXACT_LAUNCH_RESERVATION_EXISTS",
    )
    negative_count += 1

    # Prove the concrete domain entrypoint ordering without opening a socket.
    order: list[str] = []
    synthetic_terminal_root = root / "ordered-reservations"
    synthetic_terminal_root.mkdir(mode=0o700)
    ordered_readiness = copy.deepcopy(packet)
    ordered_readiness["local_paths"]["execution_reservation_dir"] = str(synthetic_terminal_root)
    original_reserve = module.reserve_domain_launch

    class FakeReadinessModule:
        @staticmethod
        def read_canonical_packet(_path):  # noqa: ANN001, ANN205
            order.append("private_runtime_input")
            return ordered_readiness, b"synthetic"

    class FakePlanModule:
        @staticmethod
        def build_plan(_execution, _endpoint, _readiness):  # noqa: ANN001, ANN205
            return {"domain_id": "domain-1"}

    class FakeSession:
        state = "TERMINAL_SUCCEEDED"

    class FakeCore:
        session = FakeSession()

    class FakeServer:
        def __init__(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
            assert order[-1] == "reservation"
            order.append("listener")

        @staticmethod
        def serve() -> dict:
            return {"all_owned_processes_cleaned": True, "all_owned_ports_released": True}

    class FakeLaneModule:
        @staticmethod
        def build_live_domain_core(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN205
            return FakeCore()

        @staticmethod
        def coordinator_route_plan(_plan, _endpoint):  # noqa: ANN001, ANN205
            return {}

        DomainAgentServer = FakeServer

    module.require_activation_chain = lambda role: order.append(f"activation:{role}")
    module.authorize_role = lambda *_args, **_kwargs: (order.append("authorization") or (execution, admission, sha("owner-signature")))
    module.read_endpoint_manifest = lambda *_args, **_kwargs: endpoint
    module.load_readiness_module = lambda: FakeReadinessModule
    module.validate_readiness_launch_binding = lambda *_args, **_kwargs: ordered_readiness
    module.load_plan_module = lambda: FakePlanModule
    module.load_lane_module = lambda: FakeLaneModule

    def ordered_reserve(*args):  # noqa: ANN002, ANN202
        value = original_reserve(*args)
        order.append("reservation")
        return value

    module.reserve_domain_launch = ordered_reserve
    domain_terminal = module.serve_domain_agent(
        "domain-1", missing, missing, missing, missing, missing, missing,
        SOURCE_COMMIT, lambda: NOW,
    )
    assert domain_terminal["status"] == "PASS_T22_A1_DOMAIN_AGENT_TERMINAL"
    assert order == ["activation:DOMAIN_AGENT", "authorization", "private_runtime_input", "reservation", "listener"]

    # Prove coordinator runtime inputs stay inside the consumer callback.
    coordinator_order: list[str] = []

    class FakeConsumer:
        @staticmethod
        def consume_and_dispatch(*args):  # noqa: ANN002, ANN205
            runner = args[5]
            coordinator_order.append("owner_signature_admission_and_reservation")
            return runner(execution, admission)

    module.load_consumer_module = lambda: FakeConsumer
    module.coordinator_runner = lambda *_args, **_kwargs: coordinator_order.append("private_runtime_inputs") or {"status": "synthetic"}
    coordinator_result = module.run_coordinator(
        missing, missing, missing, missing, missing, missing, missing,
        SOURCE_COMMIT, lambda: NOW,
    )
    assert coordinator_result == {"status": "synthetic"}
    assert coordinator_order == ["owner_signature_admission_and_reservation", "private_runtime_inputs"]
    lane_module.AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY = False

status = module.status()
assert status["exact_launch_binding_activation_ready"] is False
assert status["owner_signature_verified_independently_per_role"] is True
assert status["admission_verified_before_runtime_input_read"] is True
assert status["domain_reservation_created_before_listener"] is True
assert status["coordinator_runtime_inputs_loaded_only_after_consumer_reservation"] is True
assert status["real_private_inputs_read"] == status["credential_files_read"] == 0
assert status["network_accessed"] is False and status["listeners_started"] == 0
assert status["processes_started"] == status["faults_injected"] == status["spend_usd_cents"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

print("t22_a1_exact_launch_binding_check\tpass")
print("synthetic_exact_readiness_signature_reverification_count\t1")
print("synthetic_domain_reservation_before_listener_count\t1")
print("synthetic_coordinator_post_reservation_lazy_load_count\t1")
print(f"directed_negative_test_count\t{negative_count}")
print("real_private_inputs_read\t0")
print("credential_files_read\t0")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("processes_started\t0")
print("faults_injected\t0")
print("production_admissible\tfalse")
