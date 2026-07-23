"""Fail-closed live local-process backend for one T22-A1 domain.

The backend implements the fixed ``Backend`` protocol consumed by
``FixedCommandExecutor``.  It starts only the two exact plan-bound service
argv vectors, uses no shell, inherits no environment, tracks only its own
``Popen`` objects, bounds in-memory service logs, and can stop/restart only
those owned objects.  Cluster operations use literal-IP, source-bound mTLS
JSON requests to the local etcd/OpenBao endpoints.

The activation constant remains false.  The cross-domain bootstrap exchange
is an injected, memory-only interface so this module cannot invent a hidden
transport or persist bootstrap material.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import ipaddress
import json
import os
import socket
import ssl
import stat
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

LIVE_LOCAL_BACKEND_ACTIVATION_READY = False
MAX_SERVICE_LOG_BYTES = 2 * 1024 * 1024
MAX_JSON_RESPONSE_BYTES = 1024 * 1024
MAX_BOOTSTRAP_BYTES = 4096
MAX_FIXED_TOOL_OUTPUT_BYTES = 256 * 1024
HTTP_TIMEOUT_SECONDS = 10.0
HEALTH_WAIT_SECONDS = 90.0
HEALTH_POLL_SECONDS = 0.25
PROCESS_STOP_GRACE_SECONDS = 10.0
BACKEND_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/live-local-backend/v1\0"
SECRET_MAGIC = b"T22A1S1\0"
SECRET_KIND_OPENBAO_BOOTSTRAP_BUNDLE = 1
BOOTSTRAP_SCHEMA = "agent_bridge.biocortex.track_b.t22_a1.openbao_bootstrap_bundle.v1"


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(BACKEND_DOMAIN + canonical(value)).hexdigest()


def is_sha256(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and value != "0" * 64
        and all(character in "0123456789abcdef" for character in value)
    )


def hash_file(path: Path) -> str:
    value = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                value.update(chunk)
    except OSError as error:
        raise SafeFailure("E_LIVE_BACKEND_FILE_READ") from error
    return value.hexdigest()


def zeroize(value: bytearray | None) -> None:
    if isinstance(value, bytearray):
        value[:] = b"\0" * len(value)


def secret_frame_sha256(secret: bytearray) -> str:
    require(isinstance(secret, bytearray) and 16 <= len(secret) <= MAX_BOOTSTRAP_BYTES, "E_LIVE_BACKEND_BOOTSTRAP_SIZE")
    raw = bytes(secret)
    frame = (
        SECRET_MAGIC + bytes([SECRET_KIND_OPENBAO_BOOTSTRAP_BUNDLE])
        + len(raw).to_bytes(4, "big") + hashlib.sha256(raw).digest() + raw
    )
    return hashlib.sha256(frame).hexdigest()


def effects(
    *,
    network_accessed: bool = False,
    listeners_started: int = 0,
    listeners_stopped: int = 0,
    service_processes_started: int = 0,
    service_processes_stopped: int = 0,
    faults_injected: int = 0,
) -> dict:
    return {
        "network_accessed": network_accessed,
        "listeners_started": listeners_started,
        "listeners_stopped": listeners_stopped,
        "service_processes_started": service_processes_started,
        "service_processes_stopped": service_processes_stopped,
        "faults_injected": faults_injected,
        "spend_usd_cents": 0,
    }


def exact_plan(plan: dict, expected_sha256: str) -> None:
    require(isinstance(plan, dict) and plan.get("content_sha256") == expected_sha256, "E_LIVE_BACKEND_PLAN_BINDING")
    # The workload-plan module owns the domain-separated plan digest.  Here we
    # bind exact object identity to the already validated executor input and do
    # not create a second, incompatible plan hash definition.
    require(plan.get("command_policy", {}).get("arbitrary_command_or_shell_allowed") is False, "E_LIVE_BACKEND_SHELL_POLICY")
    require(plan.get("command_policy", {}).get("automatic_retry_allowed") is False, "E_LIVE_BACKEND_RETRY_POLICY")
    require(plan.get("command_policy", {}).get("owned_processes_only") is True, "E_LIVE_BACKEND_PROCESS_SCOPE")
    require(plan.get("processes", {}).get("environment_inherits_parent") is False, "E_LIVE_BACKEND_ENVIRONMENT_POLICY")


class BootstrapExchange(Protocol):
    """One-run memory-only exchange implemented by the authenticated lane."""

    def publish(self, secret: bytearray) -> str: ...
    def consume(self) -> tuple[bytearray, str]: ...


class ProcessRuntime(Protocol):
    """Host-local process and evidence operations."""

    def preflight(self, plan: dict) -> dict: ...
    def start_services(self, plan: dict) -> dict: ...
    def stop_services(self, plan: dict) -> dict: ...
    def services_alive(self) -> bool: ...
    def cleanup(self, plan: dict, secret_values: list[bytes]) -> dict: ...
    def abort_cleanup(self, plan: dict) -> dict: ...


class ClusterControl(Protocol):
    """mTLS etcd/OpenBao operations over the already started local services."""

    def initialize_leader(self, plan: dict) -> bytearray: ...
    def join_and_unseal(self, plan: dict, bootstrap: bytearray) -> None: ...
    def query_cluster(self, plan: dict, bootstrap: bytearray) -> dict: ...
    def authorize_consume(self, plan: dict, bootstrap: bytearray) -> dict: ...
    def create_transit_signature(self, plan: dict, bootstrap: bytearray) -> dict: ...
    def verify_survivor(self, plan: dict, bootstrap: bytearray) -> dict: ...
    def verify_transit_signature(self, plan: dict, bootstrap: bytearray, challenge: bytes, signature: str) -> bool: ...
    def verify_rejoin(self, plan: dict, bootstrap: bytearray) -> dict: ...
    def secret_scan_values(self, plan: dict, bootstrap: bytearray) -> list[bytes]: ...


@dataclass
class OwnedProcess:
    name: str
    process: subprocess.Popen[bytes]
    stdout_path: Path
    stderr_path: Path
    stdout: bytearray = field(default_factory=bytearray)
    stderr: bytearray = field(default_factory=bytearray)
    overflow: bool = False
    readers: list[threading.Thread] = field(default_factory=list)


class BoundedLocalProcessRuntime:
    """Concrete no-shell runtime that owns only its two exact child objects."""

    def __init__(self) -> None:
        require(LIVE_LOCAL_BACKEND_ACTIVATION_READY, "E_LIVE_BACKEND_ACTIVATION_NOT_READY")
        self._owned: dict[str, OwnedProcess] = {}
        self._completed_logs: dict[str, bytearray] = {
            "etcd.stdout": bytearray(), "etcd.stderr": bytearray(),
            "openbao.stdout": bytearray(), "openbao.stderr": bytearray(),
        }
        self._generation = 0

    @staticmethod
    def _regular_owner_file(path: Path, maximum: int | None, private: bool, code: str) -> os.stat_result:
        require(path.is_absolute() and path.is_file() and not path.is_symlink(), code)
        try:
            metadata = path.stat()
        except OSError as error:
            raise SafeFailure(code) from error
        require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.geteuid() and metadata.st_size > 0, code)
        if maximum is not None:
            require(metadata.st_size <= maximum, code)
        if private:
            require(metadata.st_mode & 0o077 == 0, code)
        return metadata

    @staticmethod
    def _owner_directory(path: Path, empty: bool, code: str) -> None:
        require(path.is_absolute() and path.is_dir() and not path.is_symlink(), code)
        metadata = path.stat()
        require(metadata.st_uid == os.geteuid() and metadata.st_mode & 0o077 == 0, code)
        if empty:
            try:
                require(next(path.iterdir(), None) is None, code)
            except OSError as error:
                raise SafeFailure(code) from error

    @staticmethod
    def _fixed_tool(plan: dict, name: str) -> Path:
        row = plan["tools"][name]
        path = Path(row["path"])
        BoundedLocalProcessRuntime._regular_owner_file(path, None, False, "E_LIVE_BACKEND_TOOL_FILE")
        require(os.access(path, os.X_OK) and hash_file(path) == row["sha256"], "E_LIVE_BACKEND_TOOL_BINDING")
        return path

    @staticmethod
    def _fixed_run(argv: list[str], environment: dict[str, str], input_bytes: bytes | None = None) -> bytes:
        require(argv and all(isinstance(item, str) and item and "\0" not in item for item in argv), "E_LIVE_BACKEND_FIXED_ARGV")
        require(set(environment) == {"HOME", "LANG", "LC_ALL", "NO_PROXY"}, "E_LIVE_BACKEND_FIXED_ENVIRONMENT")
        require(input_bytes is None or len(input_bytes) <= MAX_FIXED_TOOL_OUTPUT_BYTES, "E_LIVE_BACKEND_FIXED_INPUT")
        try:
            result = subprocess.run(
                argv, input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=environment, shell=False, close_fds=True, timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SafeFailure("E_LIVE_BACKEND_FIXED_TOOL") from error
        require(
            len(result.stdout) <= MAX_FIXED_TOOL_OUTPUT_BYTES
            and len(result.stderr) <= MAX_FIXED_TOOL_OUTPUT_BYTES
            and result.returncode == 0,
            "E_LIVE_BACKEND_FIXED_TOOL",
        )
        return result.stdout

    @staticmethod
    def _spki(plan: dict, certificate: Path, private_key: Path) -> str:
        openssl = str(BoundedLocalProcessRuntime._fixed_tool(plan, "openssl"))
        environment = plan["processes"]["environment"]
        certificate_public = BoundedLocalProcessRuntime._fixed_run(
            [openssl, "x509", "-in", str(certificate), "-pubkey", "-noout"], environment,
        )
        certificate_der = BoundedLocalProcessRuntime._fixed_run(
            [openssl, "pkey", "-pubin", "-outform", "DER"], environment, certificate_public,
        )
        key_der = BoundedLocalProcessRuntime._fixed_run(
            [openssl, "pkey", "-in", str(private_key), "-pubout", "-outform", "DER"], environment,
        )
        require(certificate_der == key_der, "E_LIVE_BACKEND_CREDENTIAL_KEY_MISMATCH")
        return hashlib.sha256(certificate_der).hexdigest()

    @staticmethod
    def _ports_available(plan: dict) -> bool:
        ip_text = plan["network"]["overlay_ip"]
        try:
            address = ipaddress.ip_address(ip_text)
        except ValueError as error:
            raise SafeFailure("E_LIVE_BACKEND_OVERLAY_IP") from error
        family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        ports = []
        # The authenticated domain-agent listener already owns its control
        # port when PRELIGHT is dispatched.  This backend owns only the four
        # service ports and must neither probe nor stop the agent listener.
        endpoint_fields = (
            "etcd_client_endpoint", "etcd_peer_endpoint",
            "openbao_api_endpoint", "openbao_cluster_endpoint",
        )
        for field_name in endpoint_fields:
            parsed = urlsplit(plan["network"][field_name])
            require(parsed.hostname == address.compressed and isinstance(parsed.port, int), "E_LIVE_BACKEND_PORT_BINDING")
            ports.append(parsed.port)
        require(len(set(ports)) == 4, "E_LIVE_BACKEND_PORT_DUPLICATE")
        probes: list[socket.socket] = []
        try:
            for port in ports:
                probe = socket.socket(family, socket.SOCK_STREAM)
                probes.append(probe)
                probe.bind((address.compressed, port))
        except OSError:
            return False
        finally:
            for probe in probes:
                probe.close()
        return True

    def preflight(self, plan: dict) -> dict:
        require(not self._owned and self._generation == 0, "E_LIVE_BACKEND_PREFLIGHT_REPLAY")
        for name in ("python3", "etcd", "etcdctl", "bao", "openssl", "ssh-keygen"):
            self._fixed_tool(plan, name)
        credentials = plan["credentials"]
        ca = Path(credentials["ca_certificate_path"])
        certificate = Path(credentials["domain_certificate_path"])
        private_key = Path(credentials["domain_private_key_path"])
        self._regular_owner_file(ca, 256 * 1024, True, "E_LIVE_BACKEND_CA_FILE")
        self._regular_owner_file(certificate, 256 * 1024, True, "E_LIVE_BACKEND_CERTIFICATE_FILE")
        self._regular_owner_file(private_key, 256 * 1024, True, "E_LIVE_BACKEND_PRIVATE_KEY_FILE")
        require(hash_file(ca) == credentials["ca_certificate_sha256"], "E_LIVE_BACKEND_CA_BINDING")
        require(hash_file(certificate) == credentials["domain_certificate_sha256"], "E_LIVE_BACKEND_CERTIFICATE_BINDING")
        require(
            self._spki(plan, certificate, private_key)
            == credentials["domain_spki_sha256"]
            == credentials["domain_private_key_spki_sha256"],
            "E_LIVE_BACKEND_CREDENTIAL_SPKI_BINDING",
        )
        for field_name in ("domain_private_root", "etcd_data_dir", "openbao_data_dir", "owned_logs_dir", "domain_evidence_dir", "config_dir", "execution_reservation_dir"):
            self._owner_directory(Path(plan["paths"][field_name]), field_name in {"etcd_data_dir", "openbao_data_dir", "owned_logs_dir", "config_dir"}, "E_LIVE_BACKEND_PRIVATE_DIRECTORY")
        require(self._ports_available(plan), "E_LIVE_BACKEND_PORT_UNAVAILABLE")
        row = {
            "domain_id": plan["domain_id"], "plan_sha256": plan["content_sha256"],
            "tool_set_sha256": digest(plan["tools"]),
            "credential_set_sha256": digest({key: value for key, value in credentials.items() if key.endswith("sha256")}),
            "path_set_sha256": digest(plan["paths"]),
        }
        return {
            "tool_hash_set_verified": True,
            "credential_hash_and_key_match_verified": True,
            "owned_paths_private_and_empty": True,
            "exact_ports_available": True,
            "ambient_credentials_absent": plan["processes"]["environment_inherits_parent"] is False,
            "preflight_receipt_sha256": digest(row),
        }

    @staticmethod
    def _write_exact(path: Path, raw: bytes) -> None:
        require(path.is_absolute() and not path.exists() and not path.is_symlink(), "E_LIVE_BACKEND_CONFIG_OUTPUT")
        descriptor = -1
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            written = 0
            while written < len(raw):
                count = os.write(descriptor, raw[written:])
                require(count > 0, "E_LIVE_BACKEND_CONFIG_WRITE")
                written += count
            os.fsync(descriptor)
        except OSError as error:
            raise SafeFailure("E_LIVE_BACKEND_CONFIG_WRITE") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @staticmethod
    def _drain(owned: OwnedProcess, stream, target: bytearray) -> None:  # noqa: ANN001
        try:
            while chunk := stream.read(64 * 1024):
                if len(target) + len(chunk) > MAX_SERVICE_LOG_BYTES:
                    owned.overflow = True
                    try:
                        owned.process.terminate()
                    except OSError:
                        pass
                    return
                target.extend(chunk)
        except OSError:
            owned.overflow = True

    def _spawn(self, plan: dict, name: str) -> OwnedProcess:
        spec = plan["processes"][name]
        argv = spec["argv"]
        require(argv[0] == plan["tools"]["etcd" if name == "etcd" else "bao"]["path"], "E_LIVE_BACKEND_SERVICE_ARGV")
        self._fixed_tool(plan, "etcd" if name == "etcd" else "bao")
        require(spec["stdin"] == "DEVNULL", "E_LIVE_BACKEND_SERVICE_STDIN")
        environment = plan["processes"]["environment"]
        require(set(environment) == {"HOME", "LANG", "LC_ALL", "NO_PROXY"}, "E_LIVE_BACKEND_SERVICE_ENVIRONMENT")
        try:
            process = subprocess.Popen(
                argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=plan["paths"]["domain_private_root"], env=environment,
                shell=False, close_fds=True, start_new_session=True,
            )
        except OSError as error:
            raise SafeFailure("E_LIVE_BACKEND_SERVICE_START") from error
        require(process.stdout is not None and process.stderr is not None, "E_LIVE_BACKEND_SERVICE_PIPE")
        owned = OwnedProcess(
            name=name, process=process,
            stdout_path=Path(spec["stdout_log_path"]), stderr_path=Path(spec["stderr_log_path"]),
        )
        for stream, target in ((process.stdout, owned.stdout), (process.stderr, owned.stderr)):
            reader = threading.Thread(target=self._drain, args=(owned, stream, target), daemon=True)
            reader.start()
            owned.readers.append(reader)
        return owned

    def start_services(self, plan: dict) -> dict:
        require(not self._owned, "E_LIVE_BACKEND_SERVICE_ALREADY_OWNED")
        config = plan["processes"]["openbao"]
        config_path = Path(config["config_path"])
        raw_config = config["config_text"].encode()
        require(hashlib.sha256(raw_config).hexdigest() == config["config_content_sha256"], "E_LIVE_BACKEND_CONFIG_BINDING")
        if self._generation == 0:
            self._write_exact(config_path, raw_config)
        else:
            require(
                config_path.is_file() and not config_path.is_symlink()
                and config_path.stat().st_mode & 0o077 == 0
                and config_path.read_bytes() == raw_config,
                "E_LIVE_BACKEND_CONFIG_RESTART_BINDING",
            )
        started: dict[str, OwnedProcess] = {}
        try:
            for name in ("etcd", "openbao"):
                started[name] = self._spawn(plan, name)
            time.sleep(0.05)
            require(all(row.process.poll() is None and not row.overflow for row in started.values()), "E_LIVE_BACKEND_SERVICE_EARLY_EXIT")
        except Exception:
            for row in reversed(list(started.values())):
                self._stop_one(row)
            raise
        self._owned = started
        self._generation += 1
        binding = {
            "domain_id": plan["domain_id"], "generation": self._generation,
            "plan_sha256": plan["content_sha256"],
            "argv_sha256": {name: digest(plan["processes"][name]["argv"]) for name in ("etcd", "openbao")},
        }
        return {
            "owned_process_set_sha256": digest(binding),
            "process_receipt_sha256": digest({**binding, "started": True}),
        }

    @staticmethod
    def _stop_one(owned: OwnedProcess) -> None:
        process = owned.process
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=PROCESS_STOP_GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=PROCESS_STOP_GRACE_SECONDS)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SafeFailure("E_LIVE_BACKEND_SERVICE_STOP") from error
        for reader in owned.readers:
            reader.join(timeout=2)
        require(process.poll() is not None and not any(reader.is_alive() for reader in owned.readers), "E_LIVE_BACKEND_SERVICE_STOP")

    def _archive(self, owned: OwnedProcess) -> None:
        require(not owned.overflow, "E_LIVE_BACKEND_SERVICE_LOG_OVERFLOW")
        for suffix, raw in (("stdout", owned.stdout), ("stderr", owned.stderr)):
            target = self._completed_logs[f"{owned.name}.{suffix}"]
            require(len(target) + len(raw) <= MAX_SERVICE_LOG_BYTES, "E_LIVE_BACKEND_SERVICE_LOG_OVERFLOW")
            target.extend(raw)

    def stop_services(self, plan: dict) -> dict:
        require(set(self._owned) == {"etcd", "openbao"}, "E_LIVE_BACKEND_NO_OWNED_SERVICE_SET")
        current = self._owned
        for name in ("openbao", "etcd"):
            self._stop_one(current[name])
            self._archive(current[name])
        self._owned = {}
        return {
            "stopped_owned_process_set_sha256": digest({
                "domain_id": plan["domain_id"], "generation": self._generation,
                "plan_sha256": plan["content_sha256"], "stopped": ["etcd", "openbao"],
            }),
        }

    def services_alive(self) -> bool:
        return (
            set(self._owned) == {"etcd", "openbao"}
            and all(row.process.poll() is None and not row.overflow for row in self._owned.values())
        )

    @staticmethod
    def _write_log(path: Path, raw: bytes) -> None:
        BoundedLocalProcessRuntime._write_exact(path, raw if raw else b"\n")

    def cleanup(self, plan: dict, secret_values: list[bytes]) -> dict:
        if self._owned:
            self.stop_services(plan)
        require(not self._owned, "E_LIVE_BACKEND_CLEANUP_PROCESS")
        paths = {
            "etcd.stdout": Path(plan["processes"]["etcd"]["stdout_log_path"]),
            "etcd.stderr": Path(plan["processes"]["etcd"]["stderr_log_path"]),
            "openbao.stdout": Path(plan["processes"]["openbao"]["stdout_log_path"]),
            "openbao.stderr": Path(plan["processes"]["openbao"]["stderr_log_path"]),
        }
        require(all(isinstance(value, bytes) and value for value in secret_values), "E_LIVE_BACKEND_SECRET_SCAN_SET")
        exact_matches = sum(raw.count(secret) for raw in self._completed_logs.values() for secret in secret_values)
        require(exact_matches == 0, "E_LIVE_BACKEND_SECRET_LEAK")
        rows = []
        for name, path in paths.items():
            raw = bytes(self._completed_logs[name])
            self._write_log(path, raw)
            rows.append({"name": name, "sha256": hash_file(path), "bytes": path.stat().st_size})
        require(self._ports_available(plan), "E_LIVE_BACKEND_PORT_NOT_RELEASED")
        return {
            "all_owned_processes_stopped": True,
            "all_owned_ports_released": True,
            "owned_process_log_set_sha256": digest(rows),
            "owned_process_log_count": 4,
            "cleanup_receipt_sha256": digest({"domain_id": plan["domain_id"], "logs": rows, "ports_released": True}),
            "secret_value_scan_passed": True,
            "exact_secret_match_count": 0,
        }

    def abort_cleanup(self, plan: dict) -> dict:
        try:
            if self._owned:
                self.stop_services(plan)
            ports_released = self._ports_available(plan)
        except Exception:
            return {"all_owned_processes_cleaned": False, "all_owned_ports_released": False}
        return {"all_owned_processes_cleaned": not self._owned, "all_owned_ports_released": ports_released}


class LiteralIpMtlsJsonClient:
    """Bounded local-endpoint HTTPS client with exact source and leaf pinning."""

    def __init__(self, plan: dict) -> None:
        require(LIVE_LOCAL_BACKEND_ACTIVATION_READY, "E_LIVE_BACKEND_ACTIVATION_NOT_READY")
        self.plan = plan
        self.source_ip = ipaddress.ip_address(plan["network"]["overlay_ip"]).compressed
        credentials = plan["credentials"]
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.context.maximum_version = ssl.TLSVersion.TLSv1_3
        self.context.check_hostname = True
        self.context.verify_mode = ssl.CERT_REQUIRED
        self.context.load_verify_locations(cafile=credentials["ca_certificate_path"])
        self.context.load_cert_chain(
            certfile=credentials["domain_certificate_path"],
            keyfile=credentials["domain_private_key_path"],
        )
        try:
            pem = Path(credentials["domain_certificate_path"]).read_text(encoding="ascii")
            self.expected_leaf_der_sha256 = hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()
        except (OSError, UnicodeError, ValueError) as error:
            raise SafeFailure("E_LIVE_BACKEND_TLS_CERTIFICATE") from error

    @staticmethod
    def _endpoint(endpoint: str) -> tuple[str, int]:
        try:
            parsed = urlsplit(endpoint)
            address = ipaddress.ip_address(parsed.hostname or "")
        except (ValueError, TypeError) as error:
            raise SafeFailure("E_LIVE_BACKEND_HTTPS_ENDPOINT") from error
        require(
            parsed.scheme == "https" and isinstance(parsed.port, int)
            and parsed.username is None and parsed.password is None
            and parsed.path == "" and parsed.query == "" and parsed.fragment == "",
            "E_LIVE_BACKEND_HTTPS_ENDPOINT",
        )
        return address.compressed, parsed.port

    def request(
        self,
        endpoint: str,
        method: str,
        path: str,
        body: dict | None,
        token: str | None = None,
        allowed_statuses: tuple[int, ...] = (200,),
    ) -> dict:
        host, port = self._endpoint(endpoint)
        require(host == self.source_ip, "E_LIVE_BACKEND_LOCAL_ENDPOINT_ONLY")
        require(
            method in {"GET", "POST", "PUT"}
            and (path.startswith("/v1/") or path.startswith("/v3/")),
            "E_LIVE_BACKEND_HTTP_REQUEST",
        )
        raw = b"" if body is None else canonical(body)
        require(len(raw) <= 256 * 1024, "E_LIVE_BACKEND_HTTP_REQUEST_SIZE")
        headers = {"Accept": "application/json"}
        if raw:
            headers["Content-Type"] = "application/json"
        if token is not None:
            require(0 < len(token) <= MAX_BOOTSTRAP_BYTES and "\r" not in token and "\n" not in token, "E_LIVE_BACKEND_TOKEN")
            headers["X-Vault-Token"] = token
        connection = http.client.HTTPSConnection(
            host, port, timeout=HTTP_TIMEOUT_SECONDS, context=self.context,
            source_address=(self.source_ip, 0),
        )
        try:
            connection.connect()
            certificate = connection.sock.getpeercert(binary_form=True) if connection.sock is not None else None
            require(
                isinstance(certificate, bytes)
                and hashlib.sha256(certificate).hexdigest() == self.expected_leaf_der_sha256,
                "E_LIVE_BACKEND_TLS_PEER_BINDING",
            )
            connection.request(method, path, body=raw if raw else None, headers=headers)
            response = connection.getresponse()
            response_raw = response.read(MAX_JSON_RESPONSE_BYTES + 1)
            require(len(response_raw) <= MAX_JSON_RESPONSE_BYTES and response.status in allowed_statuses, "E_LIVE_BACKEND_HTTP_RESPONSE")
        except (ConnectionRefusedError, TimeoutError) as error:
            raise SafeFailure("E_LIVE_BACKEND_HTTP_UNAVAILABLE") from error
        except (OSError, ssl.SSLError, http.client.HTTPException) as error:
            raise SafeFailure("E_LIVE_BACKEND_HTTP_IO") from error
        finally:
            connection.close()
        try:
            value = json.loads(response_raw) if response_raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise SafeFailure("E_LIVE_BACKEND_HTTP_JSON") from error
        require(isinstance(value, dict), "E_LIVE_BACKEND_HTTP_JSON")
        return value


class EtcdOpenBaoControl:
    """Concrete etcd v3-gateway and OpenBao HTTP control implementation."""

    def __init__(self, plan: dict, client: LiteralIpMtlsJsonClient | None = None) -> None:
        require(LIVE_LOCAL_BACKEND_ACTIVATION_READY, "E_LIVE_BACKEND_ACTIVATION_NOT_READY")
        self.client = client or LiteralIpMtlsJsonClient(plan)
        self.transit_challenge: bytes | None = None
        self.transit_signature: str | None = None

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.b64encode(value).decode()

    @staticmethod
    def _validate_bootstrap_values(root_token: object, unseal_key: object) -> tuple[str, str]:
        require(
            isinstance(root_token, str) and isinstance(unseal_key, str)
            and 8 <= len(root_token) <= 2048 and 8 <= len(unseal_key) <= 2048,
            "E_LIVE_BACKEND_BOOTSTRAP",
        )
        try:
            token_raw = root_token.encode("ascii")
            unseal_raw = base64.b64decode(unseal_key, validate=True)
        except (UnicodeEncodeError, ValueError) as error:
            raise SafeFailure("E_LIVE_BACKEND_BOOTSTRAP") from error
        require(
            token_raw and all(0x21 <= value <= 0x7E for value in token_raw)
            and 8 <= len(unseal_raw) <= 2048,
            "E_LIVE_BACKEND_BOOTSTRAP",
        )
        return root_token, unseal_key

    @staticmethod
    def _encode_bootstrap(plan: dict, root_token: str, unseal_key: str) -> bytearray:
        root_token, unseal_key = EtcdOpenBaoControl._validate_bootstrap_values(root_token, unseal_key)
        value = bytearray(canonical({
            "schema": BOOTSTRAP_SCHEMA,
            "run_id": plan["run_id"], "source_commit": plan["source_commit"],
            "execution_contract_sha256": plan["bindings"]["execution_contract_sha256"],
            "root_token": root_token, "unseal_key_base64": unseal_key,
        }))
        require(16 <= len(value) <= MAX_BOOTSTRAP_BYTES, "E_LIVE_BACKEND_BOOTSTRAP_SIZE")
        return value

    @staticmethod
    def _bootstrap(plan: dict, value: bytearray) -> tuple[str, str]:
        require(isinstance(value, bytearray) and 16 <= len(value) <= MAX_BOOTSTRAP_BYTES, "E_LIVE_BACKEND_BOOTSTRAP")
        try:
            decoded = json.loads(value)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise SafeFailure("E_LIVE_BACKEND_BOOTSTRAP") from error
        require(
            isinstance(decoded, dict) and set(decoded) == {
                "schema", "run_id", "source_commit", "execution_contract_sha256",
                "root_token", "unseal_key_base64",
            },
            "E_LIVE_BACKEND_BOOTSTRAP",
        )
        require(
            decoded["schema"] == BOOTSTRAP_SCHEMA
            and decoded["run_id"] == plan["run_id"]
            and decoded["source_commit"] == plan["source_commit"]
            and decoded["execution_contract_sha256"] == plan["bindings"]["execution_contract_sha256"],
            "E_LIVE_BACKEND_BOOTSTRAP_BINDING",
        )
        root_token = decoded["root_token"]
        unseal_key = decoded["unseal_key_base64"]
        return EtcdOpenBaoControl._validate_bootstrap_values(root_token, unseal_key)

    def _bao(self, plan: dict, method: str, path: str, body: dict | None, token: str | None = None, statuses: tuple[int, ...] = (200,)) -> dict:
        return self.client.request(plan["network"]["openbao_api_endpoint"], method, path, body, token, statuses)

    def _etcd(self, plan: dict, path: str, body: dict) -> dict:
        return self.client.request(plan["network"]["etcd_client_endpoint"], "POST", path, body)

    def _wait_health(self, plan: dict, expected_initialized: bool | None) -> dict:
        deadline = time.monotonic() + HEALTH_WAIT_SECONDS
        while True:
            try:
                value = self._bao(plan, "GET", "/v1/sys/health", None, statuses=(200, 429, 472, 473, 501, 503))
                if expected_initialized is None or value.get("initialized") is expected_initialized:
                    return value
            except SafeFailure as error:
                # A bounded readiness probe may repeat only while the exact
                # local listener is not yet available.  TLS, peer identity,
                # framing and response failures are integrity failures and
                # terminate immediately.
                if str(error) != "E_LIVE_BACKEND_HTTP_UNAVAILABLE":
                    raise
            require(time.monotonic() < deadline, "E_LIVE_BACKEND_OPENBAO_HEALTH_TIMEOUT")
            time.sleep(HEALTH_POLL_SECONDS)

    def initialize_leader(self, plan: dict) -> bytearray:
        health = self._wait_health(plan, False)
        require(health.get("initialized") is False, "E_LIVE_BACKEND_OPENBAO_ALREADY_INITIALIZED")
        initialized = self._bao(plan, "POST", "/v1/sys/init", {"secret_shares": 1, "secret_threshold": 1})
        keys = initialized.get("keys_base64")
        root_token = initialized.get("root_token")
        require(isinstance(keys, list) and len(keys) == 1 and isinstance(keys[0], str), "E_LIVE_BACKEND_OPENBAO_INIT")
        require(isinstance(root_token, str) and root_token, "E_LIVE_BACKEND_OPENBAO_INIT")
        bootstrap = self._encode_bootstrap(plan, root_token, keys[0])
        unsealed = self._bao(plan, "POST", "/v1/sys/unseal", {"key": keys[0]})
        require(unsealed.get("sealed") is False, "E_LIVE_BACKEND_OPENBAO_UNSEAL")
        self._bao(plan, "POST", f"/v1/sys/mounts/{plan['workload']['openbao_transit_mount']}", {"type": "transit"}, root_token, statuses=(200, 204))
        self._bao(
            plan, "POST",
            f"/v1/{plan['workload']['openbao_transit_mount']}/keys/{plan['workload']['openbao_transit_key']}",
            {"type": plan["workload"]["openbao_transit_key_type"]}, root_token, statuses=(200, 204),
        )
        return bootstrap

    def join_and_unseal(self, plan: dict, bootstrap: bytearray) -> None:
        _root_token, unseal_key = self._bootstrap(plan, bootstrap)
        health = self._wait_health(plan, True)
        if health.get("sealed") is not False:
            unsealed = self._bao(plan, "POST", "/v1/sys/unseal", {"key": unseal_key})
            require(unsealed.get("sealed") is False, "E_LIVE_BACKEND_OPENBAO_UNSEAL")

    @staticmethod
    def _members(value: dict) -> tuple[int, int]:
        members = value.get("members")
        require(isinstance(members, list), "E_LIVE_BACKEND_ETCD_MEMBER_RESPONSE")
        voters = sum(row.get("isLearner", row.get("is_learner", False)) is False for row in members if isinstance(row, dict))
        return len(members), voters

    @staticmethod
    def _raft(value: dict) -> tuple[int, int]:
        servers = value.get("data", {}).get("config", {}).get("servers")
        require(isinstance(servers, list), "E_LIVE_BACKEND_OPENBAO_RAFT_RESPONSE")
        voters = sum(row.get("voter") is True for row in servers if isinstance(row, dict))
        return len(servers), voters

    def _range(self, plan: dict) -> dict:
        key = plan["workload"]["authority_key"].encode()
        return self._etcd(plan, "/v3/kv/range", {"key": self._b64(key)})

    def query_cluster(self, plan: dict, bootstrap: bytearray) -> dict:
        root_token, _unseal_key = self._bootstrap(plan, bootstrap)
        members, voters = self._members(self._etcd(plan, "/v3/cluster/member/list", {"linearizable": True}))
        self._range(plan)
        health = self._bao(plan, "GET", "/v1/sys/health", None, statuses=(200, 429, 472, 473))
        bao_members, bao_voters = self._raft(self._bao(plan, "GET", "/v1/sys/storage/raft/configuration", None, root_token))
        return {
            "etcd_member_count": members, "etcd_voter_count": voters,
            "openbao_member_count": bao_members, "openbao_voter_count": bao_voters,
            "local_etcd_healthy": True,
            "local_openbao_unsealed": health.get("initialized") is True and health.get("sealed") is False,
        }

    @staticmethod
    def _range_value(response: dict) -> bytes | None:
        kvs = response.get("kvs", [])
        if not kvs:
            return None
        require(isinstance(kvs, list) and len(kvs) == 1 and isinstance(kvs[0], dict), "E_LIVE_BACKEND_ETCD_RANGE")
        try:
            return base64.b64decode(kvs[0]["value"], validate=True)
        except (KeyError, ValueError, TypeError) as error:
            raise SafeFailure("E_LIVE_BACKEND_ETCD_RANGE") from error

    @staticmethod
    def _txn_range(value: dict, index: int) -> dict:
        responses = value.get("responses")
        require(isinstance(responses, list) and len(responses) > index, "E_LIVE_BACKEND_ETCD_TXN")
        row = responses[index]
        require(isinstance(row, dict) and isinstance(row.get("response_range"), dict), "E_LIVE_BACKEND_ETCD_TXN")
        return row["response_range"]

    @staticmethod
    def _revision_digest(value: dict) -> str:
        header = value.get("header")
        require(isinstance(header, dict), "E_LIVE_BACKEND_ETCD_REVISION")
        revision = header.get("revision")
        require(
            isinstance(revision, (str, int)) and not isinstance(revision, bool)
            and str(revision).isdigit() and int(revision) > 0,
            "E_LIVE_BACKEND_ETCD_REVISION",
        )
        return digest({"revision": str(revision)})

    def authorize_consume(self, plan: dict, bootstrap: bytearray) -> dict:
        self._bootstrap(plan, bootstrap)
        key = plan["workload"]["authority_key"].encode()
        authorized = plan["workload"]["authorized_unclaimed_value"].encode()
        consumed = plan["workload"]["consumed_value"].encode()
        encoded_key = self._b64(key)
        authorized_txn = self._etcd(plan, "/v3/kv/txn", {
            "compare": [{"key": encoded_key, "result": "EQUAL", "target": "VERSION", "version": "0"}],
            "success": [{"requestPut": {"key": encoded_key, "value": self._b64(authorized)}}],
            "failure": [{"requestRange": {"key": encoded_key}}],
        })
        require(authorized_txn.get("succeeded") is True, "E_LIVE_BACKEND_ETCD_AUTHORITY_ALREADY_USED")
        consume = self._etcd(plan, "/v3/kv/txn", {
            "compare": [{"key": encoded_key, "result": "EQUAL", "target": "VALUE", "value": self._b64(authorized)}],
            "success": [
                {"requestPut": {"key": encoded_key, "value": self._b64(consumed)}},
                {"requestRange": {"key": encoded_key}},
            ],
            "failure": [{"requestRange": {"key": encoded_key}}],
        })
        require(consume.get("succeeded") is True, "E_LIVE_BACKEND_ETCD_CONSUME")
        require(self._range_value(self._txn_range(consume, 1)) == consumed, "E_LIVE_BACKEND_ETCD_CONSUMED_VALUE")
        replay = self._etcd(plan, "/v3/kv/txn", {
            "compare": [{"key": encoded_key, "result": "EQUAL", "target": "VALUE", "value": self._b64(authorized)}],
            "success": [{"requestPut": {"key": encoded_key, "value": self._b64(consumed)}}],
            "failure": [{"requestRange": {"key": encoded_key}}],
        })
        require(replay.get("succeeded") is False, "E_LIVE_BACKEND_ETCD_REPLAY_ACCEPTED")
        require(self._range_value(self._txn_range(replay, 0)) == consumed, "E_LIVE_BACKEND_ETCD_REPLAY_STATE")
        consume_revision = self._revision_digest(consume)
        replay_revision = self._revision_digest(replay)
        return {
            "linearizable_authorize_consume_observed": True,
            "replay_consume_rejected": True,
            "consume_revision_sha256": consume_revision,
            "replay_revision_sha256": replay_revision,
        }

    def create_transit_signature(self, plan: dict, bootstrap: bytearray) -> dict:
        root_token, _unseal_key = self._bootstrap(plan, bootstrap)
        state = self._range(plan)
        require(self._range_value(state) == plan["workload"]["consumed_value"].encode(), "E_LIVE_BACKEND_PREFAULT_STATE")
        challenge = canonical({
            "run_id": plan["run_id"], "execution_contract_sha256": plan["bindings"]["execution_contract_sha256"],
            "consumed_value_sha256": plan["workload"]["consumed_value_sha256"],
        })
        response = self._bao(
            plan, "POST",
            f"/v1/{plan['workload']['openbao_transit_mount']}/sign/{plan['workload']['openbao_transit_key']}",
            {"input": self._b64(challenge)}, root_token,
        )
        signature = response.get("data", {}).get("signature")
        require(isinstance(signature, str) and 0 < len(signature) <= 8192, "E_LIVE_BACKEND_TRANSIT_SIGNATURE")
        self.transit_challenge = challenge
        self.transit_signature = signature
        return {"challenge": challenge, "signature": signature}

    def verify_survivor(self, plan: dict, bootstrap: bytearray) -> dict:
        cluster = self.query_cluster(plan, bootstrap)
        current = self._range(plan)
        return {
            "surviving_two_domain_etcd_quorum_observed": cluster["etcd_voter_count"] >= 2,
            "surviving_two_domain_openbao_available": cluster["openbao_voter_count"] >= 2 and cluster["local_openbao_unsealed"],
            "prefault_state_match_verified": self._range_value(current) == plan["workload"]["consumed_value"].encode(),
        }

    def verify_transit_signature(self, plan: dict, bootstrap: bytearray, challenge: bytes, signature: str) -> bool:
        root_token, _unseal_key = self._bootstrap(plan, bootstrap)
        response = self._bao(
            plan, "POST",
            f"/v1/{plan['workload']['openbao_transit_mount']}/verify/{plan['workload']['openbao_transit_key']}",
            {"input": self._b64(challenge), "signature": signature}, root_token,
        )
        return response.get("data", {}).get("valid") is True

    def verify_rejoin(self, plan: dict, bootstrap: bytearray) -> dict:
        return self.query_cluster(plan, bootstrap)

    def secret_scan_values(self, plan: dict, bootstrap: bytearray) -> list[bytes]:
        root_token, unseal_key = self._bootstrap(plan, bootstrap)
        return [bytes(bootstrap), root_token.encode(), unseal_key.encode()]


@dataclass
class LiveLocalBackend:
    """Fixed-command backend with no generic command or shell entry point."""

    plan: dict
    runtime: ProcessRuntime
    control: ClusterControl
    exchange: BootstrapExchange
    synthetic_only: bool = False
    bootstrap: bytearray | None = None
    bootstrap_frame_sha256: str | None = None
    prefault_challenge: bytes | None = None
    prefault_signature: str | None = None
    started: bool = False
    stopped_for_fault: bool = False
    cleaned: bool = False

    def __post_init__(self) -> None:
        require(LIVE_LOCAL_BACKEND_ACTIVATION_READY, "E_LIVE_BACKEND_ACTIVATION_NOT_READY")
        require(self.synthetic_only is False, "E_LIVE_BACKEND_SYNTHETIC_FLAG")
        self.plan_sha256 = self.plan.get("content_sha256")
        require(is_sha256(self.plan_sha256), "E_LIVE_BACKEND_PLAN_DIGEST")
        exact_plan(self.plan, self.plan_sha256)

    def _plan(self, plan: dict) -> None:
        exact_plan(plan, self.plan_sha256)
        require(plan == self.plan, "E_LIVE_BACKEND_PLAN_IDENTITY")
        require(not self.cleaned, "E_LIVE_BACKEND_ALREADY_CLEANED")

    def _secret(self) -> bytearray:
        require(isinstance(self.bootstrap, bytearray) and 16 <= len(self.bootstrap) <= MAX_BOOTSTRAP_BYTES, "E_LIVE_BACKEND_BOOTSTRAP_MISSING")
        return self.bootstrap

    def preflight(self, plan: dict) -> dict:
        self._plan(plan)
        require(not self.started and self.bootstrap is None, "E_LIVE_BACKEND_PREFLIGHT_STATE")
        return {"observation": self.runtime.preflight(plan), "effects": effects()}

    def start_owned_cluster_members(self, plan: dict) -> dict:
        self._plan(plan)
        require(not self.started and not self.stopped_for_fault and self.bootstrap is None, "E_LIVE_BACKEND_START_STATE")
        process = self.runtime.start_services(plan)
        try:
            if plan["domain_id"] == "domain-1":
                secret = self.control.initialize_leader(plan)
                frame_sha256 = self.exchange.publish(secret)
                action = "PRODUCED_MEMORY_ONLY"
                role = "LEADER_INITIALIZE_AND_HOLD_MEMORY_ONLY"
            else:
                secret, frame_sha256 = self.exchange.consume()
                self.control.join_and_unseal(plan, secret)
                action = "CONSUMED_MEMORY_ONLY"
                role = "FOLLOWER_RETRY_JOIN_AND_UNSEAL"
            require(is_sha256(frame_sha256) and frame_sha256 == secret_frame_sha256(secret), "E_LIVE_BACKEND_SECRET_FRAME_BINDING")
            require(self.runtime.services_alive(), "E_LIVE_BACKEND_SERVICES_NOT_ALIVE")
        except Exception:
            zeroize(locals().get("secret"))
            self.runtime.abort_cleanup(plan)
            raise
        self.bootstrap = secret
        self.bootstrap_frame_sha256 = frame_sha256
        self.started = True
        return {
            "observation": {
                "etcd_process_started": True, "openbao_process_started": True,
                "owned_process_set_sha256": process["owned_process_set_sha256"],
                "process_receipt_sha256": process["process_receipt_sha256"],
                "openbao_bootstrap_role": role, "secret_frame_action": action,
                "secret_frame_sha256": frame_sha256, "secret_frame_persisted": False,
            },
            "effects": effects(network_accessed=True, listeners_started=4, service_processes_started=2),
        }

    def query_cluster_state(self, plan: dict) -> dict:
        self._plan(plan)
        require(self.started and not self.stopped_for_fault and self.runtime.services_alive(), "E_LIVE_BACKEND_QUERY_STATE")
        value = self.control.query_cluster(plan, self._secret())
        require(set(value) == {
            "etcd_member_count", "etcd_voter_count", "openbao_member_count", "openbao_voter_count",
            "local_etcd_healthy", "local_openbao_unsealed",
        }, "E_LIVE_BACKEND_CLUSTER_SHAPE")
        observation = dict(value)
        observation["cluster_observation_sha256"] = digest({"domain_id": plan["domain_id"], **value})
        return {"observation": observation, "effects": effects(network_accessed=True)}

    def execute_authorize_consume(self, plan: dict) -> dict:
        self._plan(plan)
        require(plan["domain_id"] == "domain-1" and self.started, "E_LIVE_BACKEND_COORDINATOR_COMMAND")
        value = self.control.authorize_consume(plan, self._secret())
        require(set(value) == {
            "linearizable_authorize_consume_observed", "replay_consume_rejected",
            "consume_revision_sha256", "replay_revision_sha256",
        }, "E_LIVE_BACKEND_AUTHORIZE_SHAPE")
        return {
            "observation": {
                **value,
                "authorized_value_sha256": plan["workload"]["authorized_unclaimed_value_sha256"],
                "consumed_value_sha256": plan["workload"]["consumed_value_sha256"],
            },
            "effects": effects(network_accessed=True),
        }

    def create_prefault_transit_signature(self, plan: dict) -> dict:
        self._plan(plan)
        require(plan["domain_id"] == "domain-1" and self.started, "E_LIVE_BACKEND_COORDINATOR_COMMAND")
        value = self.control.create_transit_signature(plan, self._secret())
        challenge = value.get("challenge")
        signature = value.get("signature")
        require(isinstance(challenge, bytes) and challenge and isinstance(signature, str) and signature, "E_LIVE_BACKEND_TRANSIT_RESULT")
        self.prefault_challenge = challenge
        self.prefault_signature = signature
        return {
            "observation": {
                "prefault_transit_signature_created": True,
                "transit_challenge_sha256": hashlib.sha256(challenge).hexdigest(),
                "transit_signature_sha256": hashlib.sha256(signature.encode()).hexdigest(),
                "consumed_state_sha256": plan["workload"]["consumed_value_sha256"],
            },
            "effects": effects(network_accessed=True),
        }

    def stop_owned_service_set(self, plan: dict) -> dict:
        self._plan(plan)
        require(plan["role"]["this_domain_is_fault_target"] is True and self.started and not self.stopped_for_fault, "E_LIVE_BACKEND_STOP_STATE")
        value = self.runtime.stop_services(plan)
        require(not self.runtime.services_alive(), "E_LIVE_BACKEND_STOP_FAILED")
        self.stopped_for_fault = True
        return {
            "observation": {
                "target_domain_id": plan["domain_id"],
                "etcd_process_stopped": True, "openbao_process_stopped": True,
                "stopped_owned_process_set_sha256": value["stopped_owned_process_set_sha256"],
            },
            "effects": effects(service_processes_stopped=2, faults_injected=1),
        }

    def verify_surviving_quorum_and_state(self, plan: dict) -> dict:
        self._plan(plan)
        require(plan["role"]["this_domain_is_fault_target"] is False and self.started and self.runtime.services_alive(), "E_LIVE_BACKEND_SURVIVOR_STATE")
        value = self.control.verify_survivor(plan, self._secret())
        require(set(value) == {
            "surviving_two_domain_etcd_quorum_observed",
            "surviving_two_domain_openbao_available", "prefault_state_match_verified",
        }, "E_LIVE_BACKEND_SURVIVOR_SHAPE")
        observation = dict(value)
        observation["survivor_observation_sha256"] = digest({"domain_id": plan["domain_id"], **value})
        return {"observation": observation, "effects": effects(network_accessed=True)}

    def verify_postfault_transit_signature(self, plan: dict) -> dict:
        self._plan(plan)
        require(
            plan["domain_id"] == "domain-1" and isinstance(self.prefault_challenge, bytes)
            and isinstance(self.prefault_signature, str),
            "E_LIVE_BACKEND_PREFAULT_MISSING",
        )
        require(
            self.control.verify_transit_signature(
                plan, self._secret(), self.prefault_challenge, self.prefault_signature,
            ),
            "E_LIVE_BACKEND_TRANSIT_VERIFY",
        )
        return {
            "observation": {
                "postfault_transit_signature_verified": True,
                "transit_challenge_sha256": hashlib.sha256(self.prefault_challenge).hexdigest(),
                "transit_signature_sha256": hashlib.sha256(self.prefault_signature.encode()).hexdigest(),
            },
            "effects": effects(network_accessed=True),
        }

    def restart_owned_service_set(self, plan: dict) -> dict:
        self._plan(plan)
        require(plan["role"]["this_domain_is_fault_target"] is True and self.started and self.stopped_for_fault, "E_LIVE_BACKEND_RESTART_STATE")
        secret, frame_sha256 = self.exchange.consume()
        try:
            require(is_sha256(frame_sha256) and frame_sha256 == secret_frame_sha256(secret), "E_LIVE_BACKEND_SECRET_FRAME_BINDING")
            process = self.runtime.start_services(plan)
            self.control.join_and_unseal(plan, secret)
            require(self.runtime.services_alive(), "E_LIVE_BACKEND_SERVICES_NOT_ALIVE")
        except Exception:
            zeroize(secret)
            self.runtime.abort_cleanup(plan)
            raise
        zeroize(self.bootstrap)
        self.bootstrap = secret
        self.bootstrap_frame_sha256 = frame_sha256
        self.stopped_for_fault = False
        return {
            "observation": {
                "target_domain_id": plan["domain_id"],
                "etcd_process_restarted": True, "openbao_process_restarted": True,
                "restarted_owned_process_set_sha256": process["owned_process_set_sha256"],
                "secret_frame_action": "CONSUMED_MEMORY_ONLY",
                "secret_frame_sha256": frame_sha256, "secret_frame_persisted": False,
            },
            "effects": effects(network_accessed=True, listeners_started=4, service_processes_started=2),
        }

    def verify_target_rejoin(self, plan: dict) -> dict:
        self._plan(plan)
        require(plan["role"]["this_domain_is_fault_target"] is True and self.started and not self.stopped_for_fault, "E_LIVE_BACKEND_REJOIN_STATE")
        value = self.control.verify_rejoin(plan, self._secret())
        require(
            value.get("etcd_member_count") == value.get("etcd_voter_count") == 3
            and value.get("openbao_member_count") == value.get("openbao_voter_count") == 3
            and value.get("local_etcd_healthy") is True and value.get("local_openbao_unsealed") is True,
            "E_LIVE_BACKEND_REJOIN",
        )
        return {
            "observation": {
                "target_domain_id": plan["domain_id"],
                "target_etcd_rejoined": True, "target_openbao_rejoined": True,
                "etcd_voter_count": 3, "openbao_voter_count": 3,
                "rejoin_observation_sha256": digest({"domain_id": plan["domain_id"], **value}),
            },
            "effects": effects(network_accessed=True),
        }

    def cleanup_owned_processes(self, plan: dict) -> dict:
        self._plan(plan)
        require(self.started and not self.stopped_for_fault, "E_LIVE_BACKEND_CLEANUP_STATE")
        secret = self._secret()
        scan_values = self.control.secret_scan_values(plan, secret)
        value = self.runtime.cleanup(plan, scan_values)
        zeroize(self.bootstrap)
        self.bootstrap = None
        self.cleaned = True
        return {
            "observation": value,
            "effects": effects(listeners_stopped=4, service_processes_stopped=2),
        }

    def terminal_status(self, plan: dict, previous_receipt_sha256: str) -> dict:
        require(plan == self.plan and self.cleaned and not self.runtime.services_alive(), "E_LIVE_BACKEND_TERMINAL_STATE")
        require(is_sha256(previous_receipt_sha256), "E_LIVE_BACKEND_TERMINAL_HEAD")
        return {
            "observation": {
                "lifecycle_succeeded": True,
                "command_receipt_count": len(plan["command_policy"]["allowed_commands"]),
                "domain_evidence_head_sha256": previous_receipt_sha256,
            },
            "effects": effects(),
        }

    def abort_cleanup(self) -> dict:
        result = self.runtime.abort_cleanup(self.plan)
        zeroize(self.bootstrap)
        self.bootstrap = None
        self.cleaned = True
        return result


def status() -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.live_local_backend_status.v0",
        "status": "OFFLINE_REVIEWED_LOCAL_PROCESS_AND_MTLS_JSON_BACKEND_PRESENT_ACTIVATION_CLOSED",
        "live_local_backend_activation_ready": LIVE_LOCAL_BACKEND_ACTIVATION_READY,
        "shell_or_arbitrary_command_surface": False,
        "automatic_retry_allowed": False,
        "real_private_plans_read": 0,
        "credential_files_read": 0,
        "network_accessed": False,
        "listeners_started": 0,
        "processes_started": 0,
        "faults_injected": 0,
        "spend_usd_cents": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }


if __name__ == "__main__":
    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
