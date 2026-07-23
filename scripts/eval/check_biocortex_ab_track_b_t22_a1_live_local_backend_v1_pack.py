"""Synthetic, zero-I/O KAT for the T22-A1 live local-process backend."""
from __future__ import annotations

import copy
import base64
import hashlib
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_live_local_backend_v1.py"
EXECUTOR_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_executor_core_v1.py"
RUNNER_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_source_bound_runner_v1.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    value = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


module = load("t22a1livelocalbackend", SOURCE)
executor = load("t22a1executorforlivebackend", EXECUTOR_SOURCE)
runner = load("t22a1runnerforlivebackend", RUNNER_SOURCE)
plan_module = executor.load_plan_module()

SOURCE_COMMIT = "a" * 40
RUN_ID = "t22-a1-20260722T230000.000000z-123456789abc"
NOW = datetime(2026, 7, 22, 23, 0, tzinfo=timezone.utc)
SYNTHETIC_UNSEAL_KEY = base64.b64encode(b"synthetic-unseal-key").decode()


def sha(label: str) -> str:
    return hashlib.sha256(f"T22_A1_LIVE_LOCAL_BACKEND_SYNTHETIC:{label}".encode()).hexdigest()


ENDPOINT = {
    "source_commit": SOURCE_COMMIT,
    "run_id": RUN_ID,
    "content_sha256": sha("endpoint"),
    "domains": [
        {
            "domain_id": f"domain-{number}", "overlay_ip": f"100.64.70.{number}",
            "agent_control_port": 29000, "etcd_client_port": 2379,
            "etcd_peer_port": 2380, "openbao_api_port": 8200,
            "openbao_cluster_port": 8201, "bind_exact_overlay_ip_only": True,
            "public_listener_allowed": False,
        }
        for number in (1, 2, 3)
    ],
}
EXECUTION = {
    "source_commit": SOURCE_COMMIT, "run_id": RUN_ID,
    "content_sha256": sha("execution"),
    "private_runtime": {
        "private_endpoint_manifest_content_sha256": ENDPOINT["content_sha256"],
        "runtime_credential_manifest_content_sha256": sha("credentials"),
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
    "expires_at": "2026-07-23T00:00:00Z",
}


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
    root = Path(f"/synthetic/private/t22-a1/{RUN_ID}/{domain_id}")
    credentials = root / "credentials"
    endpoint = ENDPOINT["domains"][number - 1]
    coordinator_identity = identity(credentials, "coordinator")
    coordinator = None if number != 1 else {
        "client_identity": coordinator_identity,
        "runtime_public_key_path": str(credentials / "coordinator-runtime.pub"),
        "runtime_private_key_path": str(credentials / "coordinator-runtime"),
    }
    return {
        "source_commit": SOURCE_COMMIT, "run_id": RUN_ID,
        "domain_id": domain_id, "content_sha256": sha(f"readiness:{number}"),
        "bindings": {
            "private_endpoint_manifest_content_sha256": ENDPOINT["content_sha256"],
            "runtime_credential_manifest_content_sha256": EXECUTION["private_runtime"]["runtime_credential_manifest_content_sha256"],
        },
        "endpoint_binding": {key: endpoint[key] for key in (
            "overlay_ip", "agent_control_port", "etcd_client_port", "etcd_peer_port",
            "openbao_api_port", "openbao_cluster_port",
        )},
        "toolchain": {"executables": [
            {"name": name, "path": f"/synthetic/tools/{domain_id}/{name}", "sha256": sha(f"tool:{number}:{name}")}
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
            "ca_certificate_sha256": sha(f"ca:{number}"),
            "domain_identity": identity(credentials, "domain"),
            "domain_operator_public_key_path": str(credentials / "domain-operator.pub"),
            "domain_operator_private_key_path": str(credentials / "domain-operator"),
            "coordinator_trust_material": {
                "certificate_path": coordinator_identity["certificate_path"],
                "certificate_sha256": coordinator_identity["certificate_sha256"],
                "spki_sha256": coordinator_identity["spki_sha256"],
                "runtime_public_key_path": str(credentials / "coordinator-runtime.pub"),
                "runtime_public_key_sha256": sha("coordinator-runtime"),
            },
            "coordinator_material": coordinator,
        },
    }


READINESS = [readiness(number) for number in (1, 2, 3)]
PLANS = [plan_module.build_plan(EXECUTION, ENDPOINT, packet) for packet in READINESS]


def expect_failure(action, expected: str) -> None:  # noqa: ANN001
    try:
        action()
    except (module.SafeFailure, executor.SafeFailure) as error:
        assert str(error) == expected, (str(error), expected)
        return
    raise AssertionError(f"unsafe live-local-backend path admitted: {expected}")


class MemoryExchange:
    def __init__(self) -> None:
        self.master: bytearray | None = None
        self.frame_sha256: str | None = None

    def publish(self, secret: bytearray) -> str:
        if self.master is not None:
            raise module.SafeFailure("E_SYNTHETIC_EXCHANGE_REPLAY")
        self.master = bytearray(secret)
        self.frame_sha256 = module.secret_frame_sha256(self.master)
        return self.frame_sha256

    def consume(self) -> tuple[bytearray, str]:
        if self.master is None or self.frame_sha256 is None:
            raise module.SafeFailure("E_SYNTHETIC_EXCHANGE_EMPTY")
        return bytearray(self.master), self.frame_sha256


class FakeRuntime:
    def __init__(self, fail: str | None = None) -> None:
        self.fail = fail
        self.alive = False
        self.generation = 0
        self.aborted = False

    def preflight(self, plan: dict) -> dict:
        if self.fail == "preflight":
            raise module.SafeFailure("E_SYNTHETIC_PREFLIGHT")
        return {
            "tool_hash_set_verified": True,
            "credential_hash_and_key_match_verified": True,
            "owned_paths_private_and_empty": True,
            "exact_ports_available": True, "ambient_credentials_absent": True,
            "preflight_receipt_sha256": sha(f"preflight:{plan['domain_id']}"),
        }

    def start_services(self, plan: dict) -> dict:
        if self.fail == "start":
            raise module.SafeFailure("E_SYNTHETIC_START")
        if self.alive:
            raise module.SafeFailure("E_SYNTHETIC_ALREADY_ALIVE")
        self.alive = True
        self.generation += 1
        return {
            "owned_process_set_sha256": sha(f"processes:{plan['domain_id']}:{self.generation}"),
            "process_receipt_sha256": sha(f"process-receipt:{plan['domain_id']}:{self.generation}"),
        }

    def stop_services(self, plan: dict) -> dict:
        if not self.alive:
            raise module.SafeFailure("E_SYNTHETIC_NOT_ALIVE")
        self.alive = False
        return {"stopped_owned_process_set_sha256": sha(f"stopped:{plan['domain_id']}:{self.generation}")}

    def services_alive(self) -> bool:
        return self.alive

    def cleanup(self, plan: dict, secret_values: list[bytes]) -> dict:
        if self.fail == "secret-leak":
            exact_matches = 1
        else:
            exact_matches = 0
        self.alive = False
        logs = self.evidence_logs(plan)
        return {
            "all_owned_processes_stopped": True, "all_owned_ports_released": True,
            "owned_process_log_set_sha256": module.evidence_log_set_sha256(plan["domain_id"], logs),
            "owned_process_log_count": 4,
            "cleanup_receipt_sha256": sha(f"cleanup:{plan['domain_id']}"),
            "secret_value_scan_passed": exact_matches == 0,
            "exact_secret_match_count": exact_matches,
        }

    def evidence_logs(self, plan: dict) -> list[dict]:
        return [
            {"name": name, "raw": f"T22_A1_SYNTHETIC_ONLY:{plan['domain_id']}:{name}\n".encode()}
            for name in ("etcd.stderr.log", "etcd.stdout.log", "openbao.stderr.log", "openbao.stdout.log")
        ]

    def abort_cleanup(self, plan: dict) -> dict:
        self.alive = False
        self.aborted = True
        return {"all_owned_processes_cleaned": True, "all_owned_ports_released": True}


class FakeControl:
    def __init__(self, bad: str | None = None) -> None:
        self.bad = bad
        self.challenge = b"synthetic-prefault-transit-challenge"
        self.signature = "vault:v1:synthetic-signature"

    @staticmethod
    def bootstrap(plan: dict) -> bytearray:
        return module.EtcdOpenBaoControl._encode_bootstrap(
            plan, "synthetic-root-token", SYNTHETIC_UNSEAL_KEY,
        )

    def initialize_leader(self, plan: dict) -> bytearray:
        if self.bad == "initialize":
            raise module.SafeFailure("E_SYNTHETIC_INITIALIZE")
        return self.bootstrap(plan)

    def join_and_unseal(self, plan: dict, bootstrap: bytearray) -> None:
        if self.bad == "unseal" or bootstrap != self.bootstrap(plan):
            raise module.SafeFailure("E_SYNTHETIC_UNSEAL")

    def query_cluster(self, plan: dict, bootstrap: bytearray) -> dict:
        count = 2 if self.bad == "cluster-count" else 3
        return {
            "etcd_member_count": count, "etcd_voter_count": count,
            "openbao_member_count": count, "openbao_voter_count": count,
            "local_etcd_healthy": True, "local_openbao_unsealed": True,
        }

    def authorize_consume(self, plan: dict, bootstrap: bytearray) -> dict:
        return {
            "linearizable_authorize_consume_observed": self.bad != "consume",
            "replay_consume_rejected": True,
            "consume_revision_sha256": sha("consume-revision"),
            "replay_revision_sha256": sha("replay-revision"),
        }

    def create_transit_signature(self, plan: dict, bootstrap: bytearray) -> dict:
        if self.bad == "transit-create":
            return {"challenge": b"", "signature": ""}
        return {"challenge": self.challenge, "signature": self.signature}

    def verify_survivor(self, plan: dict, bootstrap: bytearray) -> dict:
        return {
            "surviving_two_domain_etcd_quorum_observed": self.bad != "survivor",
            "surviving_two_domain_openbao_available": True,
            "prefault_state_match_verified": True,
        }

    def verify_transit_signature(self, plan: dict, bootstrap: bytearray, challenge: bytes, signature: str) -> bool:
        return self.bad != "transit-verify" and challenge == self.challenge and signature == self.signature

    def verify_rejoin(self, plan: dict, bootstrap: bytearray) -> dict:
        return self.query_cluster(plan, bootstrap)

    def secret_scan_values(self, plan: dict, bootstrap: bytearray) -> list[bytes]:
        return [bytes(bootstrap), b"synthetic-root-token", SYNTHETIC_UNSEAL_KEY.encode()]


# Both real constructors reject before touching paths, processes, sockets or
# credentials while the committed activation constant is false.
expect_failure(lambda: module.BoundedLocalProcessRuntime(), "E_LIVE_BACKEND_ACTIVATION_NOT_READY")
expect_failure(
    lambda: module.LiveLocalBackend(PLANS[0], FakeRuntime(), FakeControl(), MemoryExchange()),
    "E_LIVE_BACKEND_ACTIVATION_NOT_READY",
)

# The KAT explicitly opts into the object graph with injected fakes.  No real
# runtime or HTTP client is constructed.
module.LIVE_LOCAL_BACKEND_ACTIVATION_READY = True
executor.EXECUTOR_ACTIVATION_READY = True

exchange = MemoryExchange()
runtimes = [FakeRuntime() for _ in range(3)]
controls = [FakeControl() for _ in range(3)]
backends = [
    module.LiveLocalBackend(plan, runtimes[index], controls[index], exchange)
    for index, plan in enumerate(PLANS)
]
executors = [
    executor.FixedCommandExecutor(PLANS[index], EXECUTION, ENDPOINT, READINESS[index], backends[index])
    for index in range(3)
]
by_domain = {value.plan["domain_id"]: value for value in executors}
receipt_count = 0
for sequence, (domain_id, command) in enumerate(runner.global_schedule("domain-3")):
    receipt = by_domain[domain_id].execute(command, NOW + timedelta(seconds=sequence))
    assert receipt["synthetic_backend"] is False
    assert receipt["arbitrary_command_or_shell_used"] is False
    assert receipt["automatic_retry_allowed"] is False
    assert receipt["production_admissible"] is False
    receipt_count += 1
assert receipt_count == 23
for value in executors:
    summary = executor.validate_receipt_chain(value.receipts, value.plan)
    assert summary["state"] == "TERMINAL_SUCCEEDED"
    assert summary["synthetic_backend"] is False
assert exchange.master is not None and exchange.frame_sha256 == module.secret_frame_sha256(exchange.master)
assert all(runtime.alive is False for runtime in runtimes)
for backend in backends:
    logs = backend.evidence_logs()
    cleanup = next(receipt for receipt in by_domain[backend.plan["domain_id"]].receipts if receipt["command"] == "CLEANUP_OWNED_PROCESSES")
    assert module.evidence_log_set_sha256(backend.plan["domain_id"], logs) == cleanup["observation"]["owned_process_log_set_sha256"]


def fresh(number: int, *, runtime_fail: str | None = None, control_bad: str | None = None, shared: MemoryExchange | None = None):
    selected_exchange = shared or MemoryExchange()
    runtime = FakeRuntime(runtime_fail)
    control = FakeControl(control_bad)
    backend = module.LiveLocalBackend(PLANS[number - 1], runtime, control, selected_exchange)
    value = executor.FixedCommandExecutor(
        PLANS[number - 1], EXECUTION, ENDPOINT, READINESS[number - 1], backend,
    )
    return value, backend, runtime, selected_exchange


expect_failure(
    lambda: module.LiveLocalBackend(PLANS[0], FakeRuntime(), FakeControl(), MemoryExchange(), synthetic_only=True),
    "E_LIVE_BACKEND_SYNTHETIC_FLAG",
)

value, backend, _runtime, _exchange = fresh(1)
wrong_plan = copy.deepcopy(PLANS[0])
wrong_plan["content_sha256"] = sha("wrong-plan")
expect_failure(lambda: backend.preflight(wrong_plan), "E_LIVE_BACKEND_PLAN_BINDING")

value, _backend, _runtime, _exchange = fresh(1, runtime_fail="preflight")
expect_failure(lambda: value.execute("PREFLIGHT", NOW), "E_DOMAIN_EXECUTOR_BACKEND_FAILURE")
assert value.state == "TERMINAL_FAILED"

value, backend, runtime, _exchange = fresh(1, runtime_fail="start")
value.execute("PREFLIGHT", NOW)
expect_failure(lambda: value.execute("START_OWNED_CLUSTER_MEMBERS", NOW + timedelta(seconds=1)), "E_DOMAIN_EXECUTOR_BACKEND_FAILURE")
assert value.state == "TERMINAL_FAILED" and runtime.alive is False

value, backend, runtime, _exchange = fresh(1, control_bad="initialize")
value.execute("PREFLIGHT", NOW)
expect_failure(lambda: value.execute("START_OWNED_CLUSTER_MEMBERS", NOW + timedelta(seconds=1)), "E_DOMAIN_EXECUTOR_BACKEND_FAILURE")
assert runtime.aborted is True and runtime.alive is False

value, backend, runtime, _exchange = fresh(2)
value.execute("PREFLIGHT", NOW)
expect_failure(lambda: value.execute("START_OWNED_CLUSTER_MEMBERS", NOW + timedelta(seconds=1)), "E_DOMAIN_EXECUTOR_BACKEND_FAILURE")
assert runtime.aborted is True

duplicate = MemoryExchange()
secret = FakeControl.bootstrap(PLANS[0])
duplicate.publish(secret)
expect_failure(lambda: duplicate.publish(secret), "E_SYNTHETIC_EXCHANGE_REPLAY")

value, backend, _runtime, _exchange = fresh(1)
expect_failure(lambda: backend.query_cluster_state(PLANS[0]), "E_LIVE_BACKEND_QUERY_STATE")
expect_failure(lambda: backend.stop_owned_service_set(PLANS[0]), "E_LIVE_BACKEND_STOP_STATE")
expect_failure(lambda: backend.verify_postfault_transit_signature(PLANS[0]), "E_LIVE_BACKEND_PREFAULT_MISSING")
expect_failure(lambda: backend.cleanup_owned_processes(PLANS[0]), "E_LIVE_BACKEND_CLEANUP_STATE")
expect_failure(lambda: backend.terminal_status(PLANS[0], sha("head")), "E_LIVE_BACKEND_TERMINAL_STATE")

value, backend, _runtime, _exchange = fresh(1, control_bad="cluster-count")
value.execute("PREFLIGHT", NOW)
value.execute("START_OWNED_CLUSTER_MEMBERS", NOW + timedelta(seconds=1))
expect_failure(lambda: value.execute("QUERY_CLUSTER_STATE", NOW + timedelta(seconds=2)), "E_DOMAIN_EXECUTOR_ETCD_CLUSTER")

value, backend, _runtime, _exchange = fresh(1, control_bad="consume")
for offset, command in enumerate(("PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE")):
    value.execute(command, NOW + timedelta(seconds=offset))
expect_failure(lambda: value.execute("EXECUTE_AUTHORIZE_CONSUME", NOW + timedelta(seconds=3)), "E_DOMAIN_EXECUTOR_CONSUME")

value, backend, _runtime, _exchange = fresh(1, control_bad="transit-create")
for offset, command in enumerate(("PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE", "EXECUTE_AUTHORIZE_CONSUME")):
    value.execute(command, NOW + timedelta(seconds=offset))
expect_failure(lambda: value.execute("CREATE_PREFAULT_TRANSIT_SIGNATURE", NOW + timedelta(seconds=4)), "E_DOMAIN_EXECUTOR_BACKEND_FAILURE")

value, backend, _runtime, _exchange = fresh(1, control_bad="transit-verify")
for offset, command in enumerate((
    "PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE",
    "EXECUTE_AUTHORIZE_CONSUME", "CREATE_PREFAULT_TRANSIT_SIGNATURE",
    "VERIFY_SURVIVING_QUORUM_AND_STATE",
)):
    value.execute(command, NOW + timedelta(seconds=offset))
expect_failure(lambda: value.execute("VERIFY_POSTFAULT_TRANSIT_SIGNATURE", NOW + timedelta(seconds=6)), "E_DOMAIN_EXECUTOR_BACKEND_FAILURE")

shared = MemoryExchange()
shared.publish(FakeControl.bootstrap(PLANS[0]))
value, backend, _runtime, _exchange = fresh(3, control_bad="cluster-count", shared=shared)
for offset, command in enumerate(("PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE")):
    if command == "QUERY_CLUSTER_STATE":
        # The bad count is exercised only at the later rejoin verifier.
        backend.control.bad = None
    value.execute(command, NOW + timedelta(seconds=offset))
value.execute("STOP_OWNED_SERVICE_SET", NOW + timedelta(seconds=3))
backend.control.bad = "cluster-count"
value.execute("RESTART_OWNED_SERVICE_SET", NOW + timedelta(seconds=4))
expect_failure(lambda: value.execute("VERIFY_TARGET_REJOIN", NOW + timedelta(seconds=5)), "E_DOMAIN_EXECUTOR_BACKEND_FAILURE")

value, backend, _runtime, _exchange = fresh(1, runtime_fail="secret-leak")
for offset, command in enumerate((
    "PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE",
    "EXECUTE_AUTHORIZE_CONSUME", "CREATE_PREFAULT_TRANSIT_SIGNATURE",
    "VERIFY_SURVIVING_QUORUM_AND_STATE", "VERIFY_POSTFAULT_TRANSIT_SIGNATURE",
)):
    value.execute(command, NOW + timedelta(seconds=offset))
expect_failure(lambda: value.execute("CLEANUP_OWNED_PROCESSES", NOW + timedelta(seconds=7)), "E_DOMAIN_EXECUTOR_CLEANUP_EVIDENCE")

value, backend, runtime, _exchange = fresh(1)
value.execute("PREFLIGHT", NOW)
value.execute("START_OWNED_CLUSTER_MEMBERS", NOW + timedelta(seconds=1))
result = backend.abort_cleanup()
assert result == {"all_owned_processes_cleaned": True, "all_owned_ports_released": True}
assert runtime.alive is False and backend.bootstrap is None and backend.cleaned is True

expect_failure(lambda: module.LiteralIpMtlsJsonClient._endpoint("https://example.com:8200"), "E_LIVE_BACKEND_HTTPS_ENDPOINT")
expect_failure(lambda: module.EtcdOpenBaoControl._bootstrap(PLANS[0], bytearray(b"too-short")), "E_LIVE_BACKEND_BOOTSTRAP")
wrong_bundle_plan = copy.deepcopy(PLANS[0])
wrong_bundle_plan["run_id"] = "t22-a1-other-run"
expect_failure(
    lambda: module.EtcdOpenBaoControl._bootstrap(
        wrong_bundle_plan, FakeControl.bootstrap(PLANS[0]),
    ),
    "E_LIVE_BACKEND_BOOTSTRAP_BINDING",
)
expect_failure(lambda: module.EtcdOpenBaoControl._range_value({"kvs": [{"value": "%%%"}]}), "E_LIVE_BACKEND_ETCD_RANGE")
expect_failure(lambda: module.EtcdOpenBaoControl._members({"members": "bad"}), "E_LIVE_BACKEND_ETCD_MEMBER_RESPONSE")
expect_failure(lambda: module.EtcdOpenBaoControl._raft({"data": {}}), "E_LIVE_BACKEND_OPENBAO_RAFT_RESPONSE")
expect_failure(lambda: module.EtcdOpenBaoControl._revision_digest({"header": {}}), "E_LIVE_BACKEND_ETCD_REVISION")
expect_failure(
    lambda: module.EtcdOpenBaoControl._validate_bootstrap_values(
        "synthetic-root-token", "not-base64!!",
    ),
    "E_LIVE_BACKEND_BOOTSTRAP",
)


class RecordingClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []

    def request(self, endpoint, method, path, body, token=None, allowed_statuses=(200,)):  # noqa: ANN001
        self.requests.append({
            "endpoint": endpoint, "method": method, "path": path,
            "body": body, "token": token, "allowed_statuses": allowed_statuses,
        })
        assert self.responses
        return self.responses.pop(0)


init_client = RecordingClient([
    {"initialized": False, "sealed": True},
    {"keys_base64": [SYNTHETIC_UNSEAL_KEY], "root_token": "synthetic-root-token"},
    {"sealed": False}, {}, {},
])
init_control = module.EtcdOpenBaoControl(PLANS[0], client=init_client)
init_bootstrap = init_control.initialize_leader(PLANS[0])
assert init_bootstrap == FakeControl.bootstrap(PLANS[0])
assert [(row["method"], row["path"]) for row in init_client.requests] == [
    ("GET", "/v1/sys/health"),
    ("POST", "/v1/sys/init"),
    ("POST", "/v1/sys/unseal"),
    ("POST", "/v1/sys/mounts/t22-a1-transit"),
    ("POST", "/v1/t22-a1-transit/keys/t22-a1-ed25519"),
]

join_client = RecordingClient([
    {"initialized": True, "sealed": True}, {"sealed": False},
])
join_control = module.EtcdOpenBaoControl(PLANS[1], client=join_client)
join_control.join_and_unseal(PLANS[1], FakeControl.bootstrap(PLANS[1]))
assert [(row["method"], row["path"]) for row in join_client.requests] == [
    ("GET", "/v1/sys/health"), ("POST", "/v1/sys/unseal"),
]

consumed_b64 = base64.b64encode(PLANS[0]["workload"]["consumed_value"].encode()).decode()
txn_client = RecordingClient([
    {"header": {"revision": "1"}, "succeeded": True, "responses": [{"response_put": {}}]},
    {
        "header": {"revision": "2"}, "succeeded": True,
        "responses": [{"response_put": {}}, {"response_range": {"kvs": [{"value": consumed_b64}]}}],
    },
    {
        "header": {"revision": "2"}, "succeeded": False,
        "responses": [{"response_range": {"kvs": [{"value": consumed_b64}]}}],
    },
])
txn_control = module.EtcdOpenBaoControl(PLANS[0], client=txn_client)
txn_result = txn_control.authorize_consume(PLANS[0], FakeControl.bootstrap(PLANS[0]))
assert txn_result["linearizable_authorize_consume_observed"] is True
assert txn_result["replay_consume_rejected"] is True
assert all(row["path"] == "/v3/kv/txn" and row["method"] == "POST" for row in txn_client.requests)
for row in txn_client.requests:
    operations = [*row["body"]["success"], *row["body"]["failure"]]
    assert all(set(operation) <= {"requestPut", "requestRange"} for operation in operations)

temporary_secret = FakeControl.bootstrap(PLANS[0])
assert module.is_sha256(module.secret_frame_sha256(temporary_secret))
module.zeroize(temporary_secret)
assert temporary_secret and set(temporary_secret) == {0}

module.LIVE_LOCAL_BACKEND_ACTIVATION_READY = False
executor.EXECUTOR_ACTIVATION_READY = False
status = module.status()
assert status["live_local_backend_activation_ready"] is False
assert status["shell_or_arbitrary_command_surface"] is False
assert status["automatic_retry_allowed"] is False
assert status["real_private_plans_read"] == status["credential_files_read"] == 0
assert status["network_accessed"] is False
assert status["listeners_started"] == status["processes_started"] == 0
assert status["faults_injected"] == status["spend_usd_cents"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

negative_count = 28
print("t22_a1_live_local_backend_check\tpass")
print("synthetic_live_backend_domain_lifecycle_count\t3")
print(f"synthetic_live_backend_command_receipt_count\t{receipt_count}")
print(f"directed_negative_test_count\t{negative_count}")
print("real_private_plans_read\t0")
print("credential_files_read\t0")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("processes_started\t0")
print("faults_injected\t0")
print("production_admissible\tfalse")
