"""Owner-gated T22-A0 etcd/OpenBao real-process isolated-lab runner.

`status` is offline and side-effect free. `execute` requires an unexpired exact
owner SSHSIG, the exact signed source commit, a clean tracked tree, and the
verified pinned-tool acquisition receipt before reserving one authorization use
or starting any process. Runtime traffic is restricted to 127.0.0.1.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a0-real-process-execution-contract-v1.json"
ACQUISITION_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a0_acquire_pinned_tools_v1.py"
CONTRACT_DOMAIN = b"AB_TRACK_B_T22_A0_REAL_PROCESS_EXECUTION_CONTRACT_V1\0"
RECEIPT_DOMAIN = b"AB_TRACK_B_T22_A0_REAL_PROCESS_RECEIPT_V1\0"
EVENT_DOMAIN = b"AB_TRACK_B_T22_A0_REAL_PROCESS_EVENT_V1\0"
MAXIMUM_HTTP_RESPONSE_BYTES = 4 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024


class SafeFailure(RuntimeError):
    """A stable, non-secret failure code suitable for a receipt."""


def classify_loopback_http_error(error: BaseException) -> str:
    """Return a non-secret transport class without inspecting response bodies."""
    if isinstance(error, urllib.error.HTTPError):
        status = error.code
        if type(status) is int and 100 <= status <= 599:
            return f"E_LOOPBACK_HTTP_STATUS_{status}"
        return "E_LOOPBACK_HTTP_STATUS"
    if isinstance(error, TimeoutError):
        return "E_LOOPBACK_HTTP_TIMEOUT"
    if isinstance(error, urllib.error.URLError) and isinstance(error.reason, TimeoutError):
        return "E_LOOPBACK_HTTP_TIMEOUT"
    return "E_LOOPBACK_HTTP_TRANSPORT"


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def domain_digest(domain: bytes, value: object) -> str:
    return hashlib.sha256(domain + canonical(value)).hexdigest()


def add_receipt_digest(value: dict) -> dict:
    receipt = dict(value)
    receipt["content_sha256"] = "0" * 64
    unsigned = dict(receipt)
    unsigned.pop("content_sha256")
    receipt["content_sha256"] = domain_digest(RECEIPT_DOMAIN, unsigned)
    return receipt


def write_exclusive_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(READ_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_receipt_file(path: Path) -> dict:
    raw = path.read_bytes()
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "E_RECEIPT_FRAMING")
    try:
        receipt = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure("E_RECEIPT_JSON") from error
    require(raw == canonical(receipt) + b"\n", "E_RECEIPT_NOT_CANONICAL")
    unsigned = dict(receipt)
    claimed = unsigned.pop("content_sha256", None)
    require(claimed == domain_digest(RECEIPT_DOMAIN, unsigned), "E_RECEIPT_DIGEST")
    return receipt


def verify_event_log(path: Path) -> dict:
    previous = "0" * 64
    count = 0
    for line in path.read_bytes().splitlines(keepends=True):
        require(line.endswith(b"\n"), "E_EVENT_FRAMING")
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise SafeFailure("E_EVENT_JSON") from error
        require(line == canonical(event) + b"\n", "E_EVENT_NOT_CANONICAL")
        claimed = event.pop("event_sha256", None)
        require(event["sequence"] == count and event["previous_event_sha256"] == previous, "E_EVENT_CHAIN_ORDER")
        require(claimed == domain_digest(EVENT_DOMAIN, event), "E_EVENT_DIGEST")
        previous = claimed
        count += 1
    require(count > 0, "E_EVENT_LOG_EMPTY")
    return {"event_count": count, "event_chain_head_sha256": previous}


def load_acquisition_module():
    spec = importlib.util.spec_from_file_location("t22_a0_acquisition", ACQUISITION_SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_contract(contract: dict) -> None:
    require(contract["schema"] == "agent_bridge.biocortex.track_b.t22_a0.real_process_execution_contract.v1", "E_CONTRACT_SCHEMA")
    require(contract["execution_mode"] == "OWNER_SIGNED_SINGLE_HOST_REAL_PROCESS_ISOLATED_LAB", "E_CONTRACT_MODE")
    require(contract["track_id"] == "SELF_HOSTED_ETCD_OPENBAO", "E_CONTRACT_TRACK")
    require(contract["artifact_root"] == "/Data/CascadeProjects/.artifacts/agent-bridge/biocortex-track-b-t22-a0-real-lab", "E_CONTRACT_ROOT")
    require(contract["authorization"] == {
        "verified_unexpired_owner_sshsig_required": True,
        "exact_source_commit_required": True,
        "clean_tracked_tree_required": True,
        "pinned_tool_acquisition_receipt_required": True,
        "one_run_per_authorization_content_sha256": True,
        "maximum_runtime_seconds": 14400,
        "spend_limit_usd": 0,
    }, "E_CONTRACT_AUTHORIZATION")
    require(contract["network"] == {
        "runtime_addresses": ["127.0.0.1"],
        "runtime_external_network_allowed": False,
        "host_global_iptables_or_tc_allowed": False,
        "proxy_environment_inherited": False,
    }, "E_CONTRACT_NETWORK")
    topology = contract["topology"]
    require(topology["etcd"] == [
        {"node": "etcd-1", "client_port": 23791, "peer_port": 23801},
        {"node": "etcd-2", "client_port": 23792, "peer_port": 23802},
        {"node": "etcd-3", "client_port": 23793, "peer_port": 23803},
    ], "E_CONTRACT_ETCD_TOPOLOGY")
    require(topology["openbao"] == [
        {"node": "bao-1", "api_port": 28201, "cluster_port": 28301},
        {"node": "bao-2", "api_port": 28202, "cluster_port": 28302},
        {"node": "bao-3", "api_port": 28203, "cluster_port": 28303},
    ], "E_CONTRACT_BAO_TOPOLOGY")
    require(topology["toxiproxy"] == {"api_port": 28474, "etcd_proxy_port": 23790}, "E_CONTRACT_PROXY_TOPOLOGY")
    ports = [item[key] for group, keys in ((topology["etcd"], ("client_port", "peer_port")), (topology["openbao"], ("api_port", "cluster_port"))) for item in group for key in keys]
    ports += list(topology["toxiproxy"].values())
    require(len(ports) == len(set(ports)) == 14, "E_CONTRACT_PORT_SET")
    bootstrap = contract["ephemeral_lab_bootstrap_material"]
    require(bootstrap == {
        "openbao_unseal_key_share_count": 1,
        "openbao_unseal_threshold": 1,
        "openbao_initial_root_token_generated": True,
        "held_in_process_memory_only": True,
        "command_line_or_environment_exposure_allowed": False,
        "log_receipt_or_artifact_persistence_allowed": False,
        "preexisting_ambient_or_external_credentials_allowed": False,
        "exact_value_leak_scan_before_success_receipt": True,
    }, "E_CONTRACT_BOOTSTRAP")
    workload = contract["workload"]
    require(workload == {
        "etcd_authority_key_prefix": "/agent-bridge/t22-a0/authority/",
        "seed_state": "AUTHORIZED_UNCLAIMED",
        "consumed_state": "CONSUMED_FOR_EXACT_RUN",
        "seed_create_revision_zero_transaction_required": True,
        "consume_exact_value_compare_and_swap_required": True,
        "default_linearizable_range_read_required": True,
        "replay_consume_must_fail_required": True,
        "openbao_transit_mount": "t22-transit",
        "openbao_transit_key": "t22-a0-ed25519",
        "openbao_transit_key_type": "ed25519",
        "post_failover_signature_verification_required": True,
    }, "E_CONTRACT_WORKLOAD")
    require(contract["faults"] == [
        {
            "id": "ETCD_LOOPBACK_PROXY_DISCONNECT_AND_RECOVER",
            "target": "etcd-1 client endpoint through Toxiproxy",
            "inject": "DISABLE_OWNED_LOOPBACK_PROXY",
            "required_observation": "PROXIED_LINEARIZABLE_READ_FAILS_DURING_DISCONNECT_AND_MATCHES_CONSUMED_STATE_AFTER_REENABLE",
        },
        {
            "id": "OPENBAO_ACTIVE_PROCESS_KILL_FAILOVER_AND_RESTART",
            "target": "observed active OpenBao process",
            "inject": "SIGKILL_OWNED_PROCESS",
            "required_observation": "DIFFERENT_NODE_BECOMES_ACTIVE_TRANSIT_SIGNATURE_VERIFIES_AND_KILLED_NODE_REJOINS_UNSEALED",
        },
    ], "E_CONTRACT_FAULTS")
    require(contract["timeouts_seconds"] == {
        "individual_http_request": 5,
        "process_ready": 120,
        "cluster_recovery": 180,
        "graceful_cleanup": 10,
    }, "E_CONTRACT_TIMEOUTS")
    require(contract["evidence"] == {
        "canonical_preflight_receipt": True,
        "canonical_hash_chained_event_log": True,
        "canonical_cleanup_receipt": True,
        "canonical_terminal_receipt": True,
        "owned_process_logs_hashed": True,
        "stdout_or_stderr_model_output_allowed": False,
        "secret_values_allowed": False,
    }, "E_CONTRACT_EVIDENCE")
    require(contract["claims"] == {
        "single_physical_host_process_evidence_only": True,
        "three_failure_domain_evidence": False,
        "external_anti_rollback_evidence": False,
        "production_admissible": False,
    }, "E_CONTRACT_CLAIMS")
    unsigned = dict(contract)
    claimed = unsigned.pop("contract_sha256")
    require(claimed == domain_digest(CONTRACT_DOMAIN, unsigned), "E_CONTRACT_DIGEST")


def load_contract() -> dict:
    contract = json.loads(CONTRACT_PATH.read_text())
    validate_contract(contract)
    return contract


def allowed_ports(contract: dict) -> frozenset[int]:
    topology = contract["topology"]
    values = [item[key] for group, keys in ((topology["etcd"], ("client_port", "peer_port")), (topology["openbao"], ("api_port", "cluster_port"))) for item in group for key in keys]
    values += list(topology["toxiproxy"].values())
    return frozenset(values)


def validate_loopback_url(url: str, contract: dict) -> None:
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == "http" and parsed.hostname == "127.0.0.1", "E_NON_LOOPBACK_RUNTIME_URL")
    require(parsed.port in allowed_ports(contract), "E_UNBOUND_RUNTIME_PORT")
    require(parsed.username is None and parsed.password is None and not parsed.fragment, "E_RUNTIME_URL_AUTHORITY")


def verify_tool_receipt(payload: dict, contract: dict, acquisition) -> tuple[Path, dict]:  # noqa: ANN001
    artifact_root = Path(contract["artifact_root"])
    require(payload["artifact_root"] == str(artifact_root), "E_ARTIFACT_ROOT_BINDING")
    tools_root = artifact_root / "tools"
    receipt_path = tools_root / "acquisition-receipt.json"
    require(receipt_path.is_file() and not receipt_path.is_symlink(), "E_TOOL_RECEIPT_MISSING")
    receipt = json.loads(receipt_path.read_text())
    require(receipt["schema"] == "agent_bridge.biocortex.track_b.t22_a0.pinned_tool_acquisition_receipt.v1", "E_TOOL_RECEIPT_SCHEMA")
    require(receipt["status"] == "PINNED_PUBLIC_RELEASE_TOOLS_ACQUIRED", "E_TOOL_RECEIPT_STATUS")
    require(receipt["owner_authorization_content_sha256"] == payload["content_sha256"], "E_TOOL_RECEIPT_AUTH_BINDING")
    require(receipt["source_commit"] == payload["source_commit"], "E_TOOL_RECEIPT_SOURCE_BINDING")
    require(receipt["pins_sha256"] == hashlib.sha256(acquisition.PINS_PATH.read_bytes()).hexdigest(), "E_TOOL_RECEIPT_PINS")
    require(receipt["production_admissible"] is False, "E_TOOL_RECEIPT_CLAIM")
    installed = receipt["installed_binaries"]
    require({item["name"] for item in installed} == {"etcd", "etcdctl", "bao", "toxiproxy-server"}, "E_TOOL_BINARY_SET")
    for item in installed:
        path = tools_root / "bin" / item["name"]
        require(path.is_file() and not path.is_symlink(), "E_TOOL_BINARY_MISSING")
        require(path.stat().st_size == item["bytes"] and sha256_file(path) == item["sha256"], "E_TOOL_BINARY_DRIFT")
    return tools_root / "bin", receipt


def ports_are_free(contract: dict) -> None:
    sockets: list[socket.socket] = []
    try:
        for port in sorted(allowed_ports(contract)):
            handle = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            handle.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            handle.bind(("127.0.0.1", port))
            sockets.append(handle)
    except OSError as error:
        raise SafeFailure("E_BOUND_LOOPBACK_PORT_NOT_FREE") from error
    finally:
        for handle in sockets:
            handle.close()


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode()


def decoded(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise SafeFailure("E_INVALID_BASE64_RESPONSE") from error


def etcd_seed_request(key: bytes, value: bytes) -> dict:
    return {
        "compare": [{"target": "CREATE", "result": "EQUAL", "key": b64(key), "create_revision": "0"}],
        "success": [{"request_put": {"key": b64(key), "value": b64(value)}}],
        "failure": [{"request_range": {"key": b64(key)}}],
    }


def etcd_consume_request(key: bytes, expected: bytes, consumed: bytes) -> dict:
    return {
        "compare": [{"target": "VALUE", "result": "EQUAL", "key": b64(key), "value": b64(expected)}],
        "success": [{"request_put": {"key": b64(key), "value": b64(consumed)}}],
        "failure": [{"request_range": {"key": b64(key)}}],
    }


def etcd_range_request(key: bytes) -> dict:
    return {"key": b64(key)}


def exact_range_value(response: dict, expected_key: bytes) -> tuple[bytes, str]:
    require(response.get("count") in (1, "1"), "E_ETCD_RANGE_CARDINALITY")
    require(len(response.get("kvs", [])) == 1, "E_ETCD_RANGE_ROWS")
    row = response["kvs"][0]
    require(decoded(row["key"]) == expected_key, "E_ETCD_RANGE_KEY")
    revision = response.get("header", {}).get("revision")
    require(isinstance(revision, str) and revision.isdigit(), "E_ETCD_RANGE_REVISION")
    return decoded(row["value"]), revision


def exact_rejected_txn_range(
    response: dict, expected_key: bytes, expected_value: bytes, minimum_revision: str,
) -> str:
    # Protobuf JSON may omit the default false scalar. The applied failure
    # branch is therefore proven by its exact RangeResponse, not by accepting a
    # missing `succeeded` field on its own.
    require(response.get("succeeded", False) is False, "E_ETCD_REPLAY_CONSUME_ADMITTED")
    operations = response.get("responses")
    require(isinstance(operations, list) and len(operations) == 1, "E_ETCD_REPLAY_FAILURE_RESPONSE")
    operation = operations[0]
    require(isinstance(operation, dict) and set(operation) == {"response_range"}, "E_ETCD_REPLAY_FAILURE_RESPONSE")
    range_response = operation["response_range"]
    require(isinstance(range_response, dict), "E_ETCD_REPLAY_FAILURE_RESPONSE")
    value, revision = exact_range_value(range_response, expected_key)
    require(value == expected_value, "E_ETCD_REPLAY_FAILURE_VALUE")
    require(int(revision) >= int(minimum_revision), "E_ETCD_REPLAY_FAILURE_REVISION")
    return revision


class EventLog:
    def __init__(self, path: Path):
        self.path = path
        self.sequence = 0
        self.previous = "0" * 64
        self.event_types: set[str] = set()

    def append(self, event_type: str, details: dict) -> dict:
        body = {
            "schema": "agent_bridge.biocortex.track_b.t22_a0.real_process_event.v1",
            "sequence": self.sequence,
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event_type": event_type,
            "details": details,
            "previous_event_sha256": self.previous,
        }
        body["event_sha256"] = domain_digest(EVENT_DOMAIN, body)
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, "ab") as handle:
            handle.write(canonical(body) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.sequence += 1
        self.previous = body["event_sha256"]
        self.event_types.add(event_type)
        return body


@dataclass
class ManagedProcess:
    label: str
    generation: int
    process: subprocess.Popen
    stdout_path: Path
    stderr_path: Path


class Runner:
    def __init__(self, contract: dict, payload: dict, binary_root: Path, run_root: Path):
        self.contract = contract
        self.payload = payload
        self.binary_root = binary_root
        self.run_root = run_root
        self.logs = run_root / "logs"
        self.data = run_root / "data"
        self.config = run_root / "config"
        self.home = run_root / "home"
        self.tmp = run_root / "tmp"
        for directory in (self.logs, self.data, self.config, self.home, self.tmp):
            directory.mkdir(mode=0o700)
        self.events = EventLog(run_root / "events.jsonl")
        self.processes: list[ManagedProcess] = []
        self.process_generations: dict[str, int] = {}
        self.maximum_concurrent_process_count = 0
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.started_monotonic = time.monotonic()
        self.deadline_monotonic = self.started_monotonic + min(
            payload["maximum_runtime_seconds"],
            max(0.0, (datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds()),
        )
        self.unseal_key: str | None = None
        self.root_token: str | None = None
        self.previous_signal_handlers: dict[int, object] = {}

    def install_signal_handlers(self) -> None:
        def interrupted(_signum, _frame):  # noqa: ANN001
            raise SafeFailure("E_EXECUTION_INTERRUPTED")
        for signum in (signal.SIGINT, signal.SIGTERM):
            self.previous_signal_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, interrupted)

    def restore_signal_handlers(self) -> None:
        for signum, handler in self.previous_signal_handlers.items():
            signal.signal(signum, handler)

    def remaining(self) -> float:
        remaining = self.deadline_monotonic - time.monotonic()
        require(remaining > 0, "E_AUTHORIZATION_RUNTIME_EXPIRED")
        return remaining

    def clean_environment(self) -> dict[str, str]:
        return {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.home),
            "TMPDIR": str(self.tmp),
            "LANG": "C",
            "LC_ALL": "C",
        }

    def start_process(self, label: str, arguments: list[str]) -> ManagedProcess:
        require(all(self.root_token not in argument for argument in arguments) if self.root_token else True, "E_SECRET_IN_PROCESS_ARGUMENT")
        require(all(self.unseal_key not in argument for argument in arguments) if self.unseal_key else True, "E_SECRET_IN_PROCESS_ARGUMENT")
        generation = self.process_generations.get(label, 0) + 1
        self.process_generations[label] = generation
        stdout_path = self.logs / f"{label}.g{generation}.stdout.log"
        stderr_path = self.logs / f"{label}.g{generation}.stderr.log"
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            process = subprocess.Popen(
                arguments, cwd=self.run_root, env=self.clean_environment(),
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, close_fds=True,
            )
        managed = ManagedProcess(label, generation, process, stdout_path, stderr_path)
        self.processes.append(managed)
        live_count = sum(item.process.poll() is None for item in self.processes)
        self.maximum_concurrent_process_count = max(self.maximum_concurrent_process_count, live_count)
        self.events.append("OWNED_PROCESS_STARTED", {"label": label, "generation": generation, "pid": process.pid})
        return managed

    def live_process(self, label: str) -> ManagedProcess:
        candidates = [item for item in self.processes if item.label == label and item.process.poll() is None]
        require(len(candidates) == 1, "E_OWNED_PROCESS_LIVENESS")
        return candidates[0]

    def kill_process(self, label: str) -> None:
        managed = self.live_process(label)
        managed.process.kill()
        try:
            managed.process.wait(timeout=self.contract["timeouts_seconds"]["graceful_cleanup"])
        except subprocess.TimeoutExpired as error:
            raise SafeFailure("E_SIGKILL_WAIT_TIMEOUT") from error
        self.events.append("OWNED_PROCESS_SIGKILL_OBSERVED", {
            "label": label, "generation": managed.generation,
            "returncode": managed.process.returncode,
        })

    def cleanup(self) -> dict:
        requested = 0
        killed = 0
        for managed in reversed(self.processes):
            if managed.process.poll() is None:
                requested += 1
                managed.process.terminate()
                try:
                    managed.process.wait(timeout=self.contract["timeouts_seconds"]["graceful_cleanup"])
                except subprocess.TimeoutExpired:
                    managed.process.kill()
                    managed.process.wait(timeout=self.contract["timeouts_seconds"]["graceful_cleanup"])
                    killed += 1
        all_stopped = all(item.process.poll() is not None for item in self.processes)
        receipt = add_receipt_digest({
            "schema": "agent_bridge.biocortex.track_b.t22_a0.cleanup_receipt.v1",
            "status": "ALL_OWNED_PROCESSES_STOPPED" if all_stopped else "CLEANUP_INCOMPLETE",
            "process_instance_count": len(self.processes),
            "termination_requested_count": requested,
            "cleanup_sigkill_count": killed,
            "all_owned_processes_stopped": all_stopped,
            "host_global_network_mutated": False,
            "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "production_admissible": False,
        })
        write_exclusive_json(self.run_root / "cleanup-receipt.json", receipt)
        return receipt

    def http_bytes(self, base: str, path: str, method: str = "GET", payload: dict | None = None, token: str | None = None, timeout: float | None = None) -> bytes:
        url = base + path
        validate_loopback_url(url, self.contract)
        body = None if payload is None else canonical(payload)
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Vault-Token"] = token
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        request_timeout = min(timeout or self.contract["timeouts_seconds"]["individual_http_request"], self.remaining())
        try:
            with self.opener.open(request, timeout=request_timeout) as response:
                validate_loopback_url(response.geturl(), self.contract)
                content = response.read(MAXIMUM_HTTP_RESPONSE_BYTES + 1)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            if isinstance(error, urllib.error.HTTPError):
                validate_loopback_url(error.geturl(), self.contract)
                error.close()
            raise SafeFailure(classify_loopback_http_error(error)) from error
        require(len(content) <= MAXIMUM_HTTP_RESPONSE_BYTES, "E_HTTP_RESPONSE_TOO_LARGE")
        return content

    def http_json(self, base: str, path: str, method: str = "GET", payload: dict | None = None, token: str | None = None, timeout: float | None = None) -> dict:
        content = self.http_bytes(base, path, method, payload, token, timeout)
        if not content:
            return {}
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise SafeFailure("E_INVALID_JSON_RESPONSE") from error
        require(isinstance(parsed, dict), "E_NON_OBJECT_JSON_RESPONSE")
        return parsed

    def wait(self, code: str, seconds: int, predicate, process: ManagedProcess | None = None):  # noqa: ANN001
        deadline = min(self.deadline_monotonic, time.monotonic() + seconds)
        while time.monotonic() < deadline:
            if process is not None and process.process.poll() is not None:
                raise SafeFailure("E_PROCESS_EXITED_BEFORE_READY")
            try:
                result = predicate()
                if result:
                    return result
            except SafeFailure:
                pass
            time.sleep(0.25)
        raise SafeFailure(code)

    def etcd_base(self, node: dict) -> str:
        return f"http://127.0.0.1:{node['client_port']}"

    def etcd_arguments(self, node: dict, cluster: str, state: str) -> list[str]:
        client = self.etcd_base(node)
        peer = f"http://127.0.0.1:{node['peer_port']}"
        return [
            str(self.binary_root / "etcd"), f"--name={node['node']}",
            f"--data-dir={self.data / node['node']}",
            f"--listen-client-urls={client}", f"--advertise-client-urls={client}",
            f"--listen-peer-urls={peer}", f"--initial-advertise-peer-urls={peer}",
            f"--initial-cluster={cluster}", f"--initial-cluster-state={state}",
            f"--initial-cluster-token=t22-a0-{self.payload['content_sha256'][:16]}",
            "--logger=zap", "--log-level=warn",
        ]

    def start_etcd_cluster(self) -> list[ManagedProcess]:
        nodes = self.contract["topology"]["etcd"]
        cluster = ",".join(f"{node['node']}=http://127.0.0.1:{node['peer_port']}" for node in nodes)
        processes = [self.start_process(node["node"], self.etcd_arguments(node, cluster, "new")) for node in nodes]
        for node, process in zip(nodes, processes):
            self.wait("E_ETCD_NODE_NOT_READY", self.contract["timeouts_seconds"]["process_ready"], lambda node=node: self.http_json(self.etcd_base(node), "/health").get("health") in (True, "true"), process)
        statuses = [self.http_json(self.etcd_base(node), "/v3/maintenance/status", "POST", {}) for node in nodes]
        cluster_ids = {status.get("header", {}).get("cluster_id") for status in statuses}
        require(len(cluster_ids) == 1 and None not in cluster_ids, "E_ETCD_CLUSTER_ID")
        self.events.append("ETCD_THREE_PROCESS_CLUSTER_READY", {"cluster_id": next(iter(cluster_ids)), "member_count": 3})
        return processes

    def execute_etcd_workload(self, run_id: str) -> dict:
        first = self.contract["topology"]["etcd"][0]
        base = self.etcd_base(first)
        key = (self.contract["workload"]["etcd_authority_key_prefix"] + run_id).encode()
        seed = canonical({"generation": 0, "run_id": run_id, "state": self.contract["workload"]["seed_state"]})
        consumed = canonical({"generation": 1, "run_id": run_id, "state": self.contract["workload"]["consumed_state"]})
        seeded = self.http_json(base, "/v3/kv/txn", "POST", etcd_seed_request(key, seed))
        require(seeded.get("succeeded") is True, "E_ETCD_SEED_CAS")
        consumed_response = self.http_json(base, "/v3/kv/txn", "POST", etcd_consume_request(key, seed, consumed))
        require(consumed_response.get("succeeded") is True, "E_ETCD_CONSUME_CAS")
        revision = consumed_response.get("header", {}).get("revision")
        require(isinstance(revision, str) and revision.isdigit(), "E_ETCD_CONSUME_REVISION")
        read_value, read_revision = exact_range_value(self.http_json(base, "/v3/kv/range", "POST", etcd_range_request(key)), key)
        require(read_value == consumed and int(read_revision) >= int(revision), "E_ETCD_LINEARIZABLE_READBACK")
        replay = self.http_json(base, "/v3/kv/txn", "POST", etcd_consume_request(key, seed, consumed))
        replay_revision = exact_rejected_txn_range(replay, key, consumed, read_revision)
        self.events.append("ETCD_LINEARIZABLE_AUTHORIZE_CONSUME_OBSERVED", {
            "authority_key_sha256": hashlib.sha256(key).hexdigest(),
            "seed_value_sha256": hashlib.sha256(seed).hexdigest(),
            "consumed_value_sha256": hashlib.sha256(consumed).hexdigest(),
            "consume_revision": revision,
            "linearizable_read_revision": read_revision,
            "replay_consume_rejected": True,
            "replay_failure_read_revision": replay_revision,
        })
        return {"key": key, "consumed": consumed, "revision": revision, "read_revision": read_revision}

    def start_and_fault_toxiproxy(self, etcd_state: dict) -> dict:
        topology = self.contract["topology"]
        api = f"http://127.0.0.1:{topology['toxiproxy']['api_port']}"
        process = self.start_process("toxiproxy", [
            str(self.binary_root / "toxiproxy-server"), "-host", "127.0.0.1",
            "-port", str(topology["toxiproxy"]["api_port"]),
        ])
        self.wait("E_TOXIPROXY_NOT_READY", self.contract["timeouts_seconds"]["process_ready"], lambda: bool(self.http_bytes(api, "/version")), process)
        proxy = {
            "name": "t22-etcd-client", "listen": f"127.0.0.1:{topology['toxiproxy']['etcd_proxy_port']}",
            "upstream": f"127.0.0.1:{topology['etcd'][0]['client_port']}", "enabled": True,
        }
        created = self.http_json(api, "/proxies", "POST", proxy)
        require(created.get("name") == proxy["name"] and created.get("enabled") is True, "E_TOXIPROXY_CREATE")
        proxied = f"http://127.0.0.1:{topology['toxiproxy']['etcd_proxy_port']}"
        initial, _ = exact_range_value(self.http_json(proxied, "/v3/kv/range", "POST", etcd_range_request(etcd_state["key"])), etcd_state["key"])
        require(initial == etcd_state["consumed"], "E_TOXIPROXY_INITIAL_READ")
        disabled = self.http_json(api, "/proxies/t22-etcd-client", "POST", {**proxy, "enabled": False})
        require(disabled.get("enabled") is False, "E_TOXIPROXY_DISABLE")
        transport_failed = False
        try:
            self.http_json(proxied, "/v3/kv/range", "POST", etcd_range_request(etcd_state["key"]), timeout=2)
        except SafeFailure as error:
            transport_failed = str(error) in {"E_LOOPBACK_HTTP_TRANSPORT", "E_LOOPBACK_HTTP_TIMEOUT"}
        require(transport_failed, "E_TOXIPROXY_DISCONNECT_NOT_OBSERVED")
        enabled = self.http_json(api, "/proxies/t22-etcd-client", "POST", {**proxy, "enabled": True})
        require(enabled.get("enabled") is True, "E_TOXIPROXY_REENABLE")
        recovered = self.wait("E_TOXIPROXY_RECOVERY", self.contract["timeouts_seconds"]["cluster_recovery"], lambda: self.http_json(proxied, "/v3/kv/range", "POST", etcd_range_request(etcd_state["key"])))
        recovered_value, recovered_revision = exact_range_value(recovered, etcd_state["key"])
        require(recovered_value == etcd_state["consumed"], "E_TOXIPROXY_RECOVERED_VALUE")
        self.events.append("ETCD_LOOPBACK_PROXY_DISCONNECT_AND_RECOVERED", {
            "proxy": "t22-etcd-client", "disconnect_observed": True,
            "recovered_linearizable_revision": recovered_revision,
            "consumed_value_match": True,
        })
        return {"fault_id": "ETCD_LOOPBACK_PROXY_DISCONNECT_AND_RECOVER", "recovered_revision": recovered_revision}

    def bao_base(self, node: dict) -> str:
        return f"http://127.0.0.1:{node['api_port']}"

    def write_bao_config(self, node: dict) -> Path:
        path = self.config / f"{node['node']}.hcl"
        data_path = self.data / node["node"]
        data_path.mkdir(mode=0o700)
        text = (
            'ui = false\n'
            'log_level = "warn"\n'
            f'api_addr = "http://127.0.0.1:{node["api_port"]}"\n'
            f'cluster_addr = "https://127.0.0.1:{node["cluster_port"]}"\n'
            f'storage "raft" {{\n  path = "{data_path}"\n  node_id = "{node["node"]}"\n'
            '  performance_multiplier = 1\n}\n'
            f'listener "tcp" {{\n  address = "127.0.0.1:{node["api_port"]}"\n'
            f'  cluster_address = "127.0.0.1:{node["cluster_port"]}"\n  tls_disable = 1\n}}\n'
        )
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(text)
        return path

    def bao_health(self, node: dict) -> dict:
        return self.http_json(
            self.bao_base(node),
            "/v1/sys/health?standbycode=200&sealedcode=200&uninitcode=200&drsecondarycode=200&performancestandbycode=200",
        )

    def start_bao_node(self, node: dict, config_path: Path) -> ManagedProcess:
        return self.start_process(node["node"], [str(self.binary_root / "bao"), "server", f"-config={config_path}"])

    def wait_bao_listener(self, node: dict, process: ManagedProcess) -> dict:
        return self.wait("E_BAO_LISTENER_NOT_READY", self.contract["timeouts_seconds"]["process_ready"], lambda: self.bao_health(node), process)

    def unseal_bao(self, node: dict) -> dict:
        require(self.unseal_key is not None, "E_BAO_UNSEAL_KEY_ABSENT")
        result = self.http_json(self.bao_base(node), "/v1/sys/unseal", "POST", {"key": self.unseal_key})
        require(result.get("sealed") is False, "E_BAO_UNSEAL")
        return result

    def initialize_bao_cluster(self) -> tuple[list[dict], dict]:
        nodes = self.contract["topology"]["openbao"]
        configs = {node["node"]: self.write_bao_config(node) for node in nodes}
        first_process = self.start_bao_node(nodes[0], configs[nodes[0]["node"]])
        initial_health = self.wait_bao_listener(nodes[0], first_process)
        require(initial_health.get("initialized") is False, "E_BAO_UNEXPECTED_INITIALIZATION")
        initialized = self.http_json(self.bao_base(nodes[0]), "/v1/sys/init", "POST", {"secret_shares": 1, "secret_threshold": 1})
        keys = initialized.get("keys_base64")
        require(isinstance(keys, list) and len(keys) == 1 and isinstance(keys[0], str) and len(keys[0]) >= 16, "E_BAO_INIT_UNSEAL_MATERIAL")
        require(isinstance(initialized.get("root_token"), str) and len(initialized["root_token"]) >= 16, "E_BAO_INIT_ROOT_TOKEN")
        self.unseal_key = keys[0]
        self.root_token = initialized["root_token"]
        first_unsealed = self.unseal_bao(nodes[0])
        cluster_id = first_unsealed.get("cluster_id")
        require(isinstance(cluster_id, str) and cluster_id, "E_BAO_CLUSTER_ID")
        for node in nodes[1:]:
            process = self.start_bao_node(node, configs[node["node"]])
            health = self.wait_bao_listener(node, process)
            require(health.get("initialized") is False, "E_BAO_JOINER_ALREADY_INITIALIZED")
            joined = self.http_json(self.bao_base(node), "/v1/sys/storage/raft/join", "POST", {"leader_api_addr": self.bao_base(nodes[0])})
            require(joined.get("joined") is True, "E_BAO_RAFT_JOIN")
            self.unseal_bao(node)
            ready = self.wait("E_BAO_JOINER_NOT_READY", self.contract["timeouts_seconds"]["cluster_recovery"], lambda node=node: self.bao_health(node))
            require(ready.get("initialized") is True and ready.get("sealed") is False, "E_BAO_JOINER_HEALTH")
        active = self.wait("E_BAO_ACTIVE_NOT_ELECTED", self.contract["timeouts_seconds"]["cluster_recovery"], lambda: self.find_bao_active(nodes))
        configuration = self.wait("E_BAO_RAFT_MEMBER_COUNT", self.contract["timeouts_seconds"]["cluster_recovery"], lambda: self.bao_raft_configuration(active))
        self.events.append("OPENBAO_THREE_PROCESS_RAFT_CLUSTER_READY", {
            "cluster_id": cluster_id, "raft_member_count": len(configuration),
            "active_node": active["node"], "bootstrap_material_persisted": False,
        })
        return nodes, {"configs": configs, "cluster_id": cluster_id, "active": active}

    def find_bao_active(self, nodes: list[dict], exclude: str | None = None) -> dict | None:
        active: list[dict] = []
        for node in nodes:
            if node["node"] == exclude:
                continue
            try:
                health = self.bao_health(node)
            except SafeFailure:
                continue
            if health.get("initialized") is True and health.get("sealed") is False and health.get("standby") is False:
                active.append(node)
        require(len(active) <= 1, "E_BAO_MULTIPLE_ACTIVE")
        return active[0] if active else None

    def bao_raft_configuration(self, active: dict) -> list[dict] | None:
        require(self.root_token is not None, "E_BAO_TOKEN_ABSENT")
        try:
            response = self.http_json(self.bao_base(active), "/v1/sys/storage/raft/configuration", token=self.root_token)
        except SafeFailure:
            return None
        servers = response.get("data", {}).get("config", {}).get("servers")
        if not isinstance(servers, list) or len(servers) != 3:
            return None
        node_ids = {server.get("node_id") for server in servers}
        return servers if node_ids == {"bao-1", "bao-2", "bao-3"} else None

    def execute_bao_fault(self, nodes: list[dict], state: dict) -> dict:
        require(self.root_token is not None, "E_BAO_TOKEN_ABSENT")
        active = state["active"]
        base = self.bao_base(active)
        workload = self.contract["workload"]
        mount = workload["openbao_transit_mount"]
        key = workload["openbao_transit_key"]
        self.http_json(base, f"/v1/sys/mounts/{mount}", "POST", {"type": "transit"}, self.root_token)
        self.http_json(base, f"/v1/{mount}/keys/{key}", "POST", {"type": workload["openbao_transit_key_type"]}, self.root_token)
        challenge = canonical({"authorization": self.payload["content_sha256"], "purpose": "T22_A0_FAILOVER_VERIFY"})
        signed = self.http_json(base, f"/v1/{mount}/sign/{key}", "POST", {"input": b64(challenge)}, self.root_token)
        signature_value = signed.get("data", {}).get("signature")
        require(isinstance(signature_value, str) and signature_value.startswith("vault:v"), "E_BAO_TRANSIT_SIGNATURE")
        killed_label = active["node"]
        self.kill_process(killed_label)
        replacement = self.wait("E_BAO_FAILOVER_NOT_OBSERVED", self.contract["timeouts_seconds"]["cluster_recovery"], lambda: self.find_bao_active(nodes, killed_label))
        require(replacement["node"] != killed_label, "E_BAO_FAILOVER_SAME_NODE")
        verified = self.http_json(
            self.bao_base(replacement), f"/v1/{mount}/verify/{key}", "POST",
            {"input": b64(challenge), "signature": signature_value}, self.root_token,
        )
        require(verified.get("data", {}).get("valid") is True, "E_BAO_POST_FAILOVER_VERIFY")
        killed_node = next(node for node in nodes if node["node"] == killed_label)
        restarted = self.start_bao_node(killed_node, state["configs"][killed_label])
        self.wait_bao_listener(killed_node, restarted)
        self.unseal_bao(killed_node)
        recovered = self.wait("E_BAO_RESTART_NOT_READY", self.contract["timeouts_seconds"]["cluster_recovery"], lambda: self.bao_health(killed_node))
        require(recovered.get("initialized") is True and recovered.get("sealed") is False, "E_BAO_RESTART_HEALTH")
        configuration = self.wait("E_BAO_RESTART_MEMBER_COUNT", self.contract["timeouts_seconds"]["cluster_recovery"], lambda: self.bao_raft_configuration(replacement))
        self.events.append("OPENBAO_ACTIVE_PROCESS_KILL_FAILOVER_AND_RESTART_OBSERVED", {
            "killed_active_node": killed_label, "replacement_active_node": replacement["node"],
            "transit_challenge_sha256": hashlib.sha256(challenge).hexdigest(),
            "transit_signature_sha256": hashlib.sha256(signature_value.encode()).hexdigest(),
            "post_failover_signature_valid": True, "restarted_node_unsealed": True,
            "raft_member_count": len(configuration),
        })
        return {
            "fault_id": "OPENBAO_ACTIVE_PROCESS_KILL_FAILOVER_AND_RESTART",
            "killed_active_node": killed_label, "replacement_active_node": replacement["node"],
            "post_failover_signature_valid": True, "restarted_node_unsealed": True,
        }

    def scan_for_secret_values(self) -> dict:
        secrets = [value.encode() for value in (self.unseal_key, self.root_token) if value]
        require(len(secrets) == 2, "E_SECRET_SCAN_INPUT")
        files = 0
        bytes_scanned = 0
        maximum = max(len(secret) for secret in secrets)
        for path in self.run_root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            files += 1
            overlap = b""
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    bytes_scanned += len(chunk)
                    candidate = overlap + chunk
                    require(not any(secret in candidate for secret in secrets), "E_EPHEMERAL_BOOTSTRAP_MATERIAL_PERSISTED")
                    overlap = candidate[-maximum:]
        return {"file_count": files, "byte_count": bytes_scanned, "exact_secret_match_count": 0}

    def log_evidence(self) -> list[dict]:
        return [
            {"path": str(path.relative_to(self.run_root)), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in sorted(self.logs.glob("*.log"))
        ]


def reserve_authorization_use(artifact_root: Path, payload: dict, run_id: str) -> Path:
    path = artifact_root / "authorization-uses" / f"{payload['content_sha256']}.reserved.json"
    receipt = add_receipt_digest({
        "schema": "agent_bridge.biocortex.track_b.t22_a0.authorization_use_reservation.v1",
        "status": "AUTHORIZATION_IRREVERSIBLY_RESERVED_FOR_ONE_RUN",
        "authorization_content_sha256": payload["content_sha256"],
        "run_id": run_id,
        "reserved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "automatic_retry_allowed": False,
        "production_admissible": False,
    })
    try:
        write_exclusive_json(path, receipt)
    except FileExistsError as error:
        raise SafeFailure("E_AUTHORIZATION_ALREADY_RESERVED") from error
    return path


def verify_preconditions(payload_path: Path, signature_path: Path) -> tuple[dict, dict, Path, dict, object]:
    contract = load_contract()
    acquisition = load_acquisition_module()
    payload, _authorization = acquisition.verify_authorization(payload_path, signature_path)
    require(payload["execution_contract_sha256"] == contract["contract_sha256"], "E_SIGNED_CONTRACT_BINDING")
    require("EPHEMERAL_LAB_BOOTSTRAP_MATERIAL_GENERATE_AND_MEMORY_ONLY_USE" in payload["allowed_after_signature"], "E_BOOTSTRAP_AUTHORITY_MISSING")
    require("LOOPBACK_TOXIPROXY_FAULT" in payload["allowed_after_signature"], "E_PROXY_FAULT_AUTHORITY_MISSING")
    require("OWNED_PROCESS_START_STOP_KILL_RESTART" in payload["allowed_after_signature"], "E_PROCESS_FAULT_AUTHORITY_MISSING")
    require("PREEXISTING_AMBIENT_OR_EXTERNAL_CREDENTIAL_DISCOVERY_OR_ACCESS" in payload["forbidden"], "E_AMBIENT_CREDENTIAL_BOUNDARY_MISSING")
    binary_root, tool_receipt = verify_tool_receipt(payload, contract, acquisition)
    ports_are_free(contract)
    return contract, payload, binary_root, tool_receipt, acquisition


def execute(payload_path: Path, signature_path: Path) -> dict:
    contract, payload, binary_root, tool_receipt, _acquisition = verify_preconditions(payload_path, signature_path)
    artifact_root = Path(contract["artifact_root"])
    run_id = "t22-a0-" + payload["issued_at"].replace(":", "").replace("-", "").replace("Z", "z") + "-" + payload["content_sha256"][:12]
    run_root = artifact_root / "runs" / run_id
    require(not run_root.exists(), "E_RUN_ROOT_EXISTS")
    reserve_authorization_use(artifact_root, payload, run_id)
    run_root.mkdir(parents=True, mode=0o700)
    preflight = add_receipt_digest({
        "schema": "agent_bridge.biocortex.track_b.t22_a0.execution_preflight_receipt.v1",
        "status": "AUTHORIZED_REAL_PROCESS_EXECUTION_PREFLIGHT_PASS",
        "run_id": run_id,
        "host": socket.gethostname(),
        "physical_host_count": 1,
        "authorization_content_sha256": payload["content_sha256"],
        "source_commit": payload["source_commit"],
        "proposal_sha256": payload["proposal_sha256"],
        "execution_contract_sha256": contract["contract_sha256"],
        "tool_acquisition_pins_sha256": tool_receipt["pins_sha256"],
        "loopback_port_count": len(allowed_ports(contract)),
        "all_loopback_ports_free": True,
        "preexisting_ambient_or_external_credentials_accessed": False,
        "spend_authorized_usd": 0,
        "production_admissible": False,
    })
    write_exclusive_json(run_root / "preflight-receipt.json", preflight)
    runner = Runner(contract, payload, binary_root, run_root)
    success: dict | None = None
    failure_code: str | None = None
    cleanup: dict | None = None
    try:
        runner.install_signal_handlers()
        runner.events.append("EXECUTION_PREFLIGHT_ACCEPTED", {"run_id": run_id, "authorization_content_sha256": payload["content_sha256"]})
        runner.start_etcd_cluster()
        etcd_state = runner.execute_etcd_workload(run_id)
        etcd_fault = runner.start_and_fault_toxiproxy(etcd_state)
        bao_nodes, bao_state = runner.initialize_bao_cluster()
        bao_fault = runner.execute_bao_fault(bao_nodes, bao_state)
        success = {"etcd_fault": etcd_fault, "openbao_fault": bao_fault}
    except SafeFailure as error:
        failure_code = str(error)
    except BaseException as error:
        failure_code = "E_INTERNAL_" + type(error).__name__.upper()
    finally:
        try:
            cleanup = runner.cleanup()
        except BaseException:
            failure_code = failure_code or "E_CLEANUP_RECEIPT"
        runner.restore_signal_handlers()
    if cleanup is None or cleanup["all_owned_processes_stopped"] is not True:
        failure_code = failure_code or "E_CLEANUP_INCOMPLETE"
    secret_scan: dict | None = None
    if runner.unseal_key is not None and runner.root_token is not None:
        try:
            secret_scan = runner.scan_for_secret_values()
        except SafeFailure as error:
            failure_code = str(error)
    evidence_validation: dict | None = None
    try:
        event_validation = verify_event_log(run_root / "events.jsonl")
        verified_preflight = verify_receipt_file(run_root / "preflight-receipt.json")
        verified_cleanup = verify_receipt_file(run_root / "cleanup-receipt.json")
        require(verified_preflight["run_id"] == run_id, "E_PREFLIGHT_RECEIPT_RUN_BINDING")
        require(verified_cleanup["all_owned_processes_stopped"] is True, "E_CLEANUP_RECEIPT_STATE")
        evidence_validation = {
            **event_validation,
            "canonical_preflight_receipt_verified": True,
            "canonical_cleanup_receipt_verified": True,
        }
    except SafeFailure as error:
        failure_code = failure_code or str(error)
    if success is None:
        failure_code = failure_code or "E_EXECUTION_NO_SUCCESS_STATE"
    terminal_status = "PASS_T22_A0_REAL_PROCESS_FAULT_EVIDENCE" if failure_code is None else "FAIL_T22_A0_REAL_PROCESS_EXECUTION"
    terminal = add_receipt_digest({
        "schema": "agent_bridge.biocortex.track_b.t22_a0.real_process_terminal_receipt.v1",
        "status": terminal_status,
        "failure_code": failure_code,
        "run_id": run_id,
        "host": socket.gethostname(),
        "physical_host_count": 1,
        "authorization_content_sha256": payload["content_sha256"],
        "source_commit": payload["source_commit"],
        "execution_contract_sha256": contract["contract_sha256"],
        "event_count": evidence_validation["event_count"] if evidence_validation else runner.events.sequence,
        "event_chain_head_sha256": evidence_validation["event_chain_head_sha256"] if evidence_validation else runner.events.previous,
        "evidence_validation": evidence_validation,
        "process_instance_count": len(runner.processes),
        "maximum_concurrent_process_count": runner.maximum_concurrent_process_count,
        "etcd_linearizable_authorize_consume_observed": "ETCD_LINEARIZABLE_AUTHORIZE_CONSUME_OBSERVED" in runner.events.event_types,
        "etcd_loopback_proxy_disconnect_recovered": "ETCD_LOOPBACK_PROXY_DISCONNECT_AND_RECOVERED" in runner.events.event_types,
        "openbao_active_process_failover_recovered": "OPENBAO_ACTIVE_PROCESS_KILL_FAILOVER_AND_RESTART_OBSERVED" in runner.events.event_types,
        "openbao_post_failover_signature_verified": "OPENBAO_ACTIVE_PROCESS_KILL_FAILOVER_AND_RESTART_OBSERVED" in runner.events.event_types,
        "faults": success,
        "secret_leak_scan": secret_scan,
        "owned_process_logs": runner.log_evidence(),
        "all_owned_processes_stopped": cleanup is not None and cleanup["all_owned_processes_stopped"] is True,
        "host_global_network_mutated": False,
        "preexisting_ambient_or_external_credentials_accessed": False,
        "spend_usd": 0,
        "single_physical_host_process_evidence_only": True,
        "three_failure_domain_evidence": False,
        "external_anti_rollback_evidence": False,
        "production_admissible": False,
        "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })
    write_exclusive_json(run_root / "terminal-receipt.json", terminal)
    use_terminal = add_receipt_digest({
        "schema": "agent_bridge.biocortex.track_b.t22_a0.authorization_use_terminal.v1",
        "status": "AUTHORIZATION_USE_SUCCEEDED" if failure_code is None else "AUTHORIZATION_USE_FAILED_NO_RETRY",
        "authorization_content_sha256": payload["content_sha256"],
        "run_id": run_id,
        "terminal_receipt_sha256": terminal["content_sha256"],
        "automatic_retry_allowed": False,
        "production_admissible": False,
    })
    write_exclusive_json(artifact_root / "authorization-uses" / f"{payload['content_sha256']}.terminal.json", use_terminal)
    return terminal


def status() -> dict:
    contract = load_contract()
    acquisition = load_acquisition_module()
    authorization_status = acquisition.load_authorization_module().status()
    tools_present = (Path(contract["artifact_root"]) / "tools" / "acquisition-receipt.json").is_file()
    if not authorization_status["owner_trust_anchor_present"]:
        state = "BLOCKED_OWNER_TRUST_ANCHOR_AND_EXACT_SIGNATURE_REQUIRED"
    elif not authorization_status["owner_trust_anchor_valid"]:
        state = "BLOCKED_OWNER_TRUST_ANCHOR_INVALID"
    elif tools_present:
        state = "BLOCKED_EXACT_SIGNED_PAYLOAD_AND_SOURCE_BOUND_TOOL_RECEIPT_REQUIRED"
    else:
        state = "BLOCKED_EXACT_SIGNED_PAYLOAD_AND_PINNED_TOOLS_REQUIRED"
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a0.real_process_runner_status.v1",
        "status": state,
        "proposal_sha256": json.loads(acquisition.load_authorization_module().PROPOSAL_PATH.read_text())["proposal_sha256"],
        "execution_contract_sha256": contract["contract_sha256"],
        "owner_trust_anchor_present": authorization_status["owner_trust_anchor_present"],
        "owner_trust_anchor_valid": authorization_status["owner_trust_anchor_valid"],
        "owner_signature_verified": False,
        "pinned_tools_present": tools_present,
        "network_attempted": False,
        "processes_started": 0,
        "faults_injected": 0,
        "real_evidence_items_created": 0,
        "production_admissible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status")
    execute_parser = subcommands.add_parser("execute")
    execute_parser.add_argument("--payload", type=Path, required=True)
    execute_parser.add_argument("--signature", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
        return
    terminal = execute(arguments.payload, arguments.signature)
    print(json.dumps(terminal, sort_keys=True, separators=(",", ":")))
    if terminal["status"] != "PASS_T22_A0_REAL_PROCESS_FAULT_EVIDENCE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
