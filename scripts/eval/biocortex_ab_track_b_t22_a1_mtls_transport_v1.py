"""Bounded mTLS framing and context construction for T22-A1 domain agents.

The framing and validation paths are pure. TLS contexts may read only exact
plan-bound CA/certificate/key files and remain disabled until the complete
runner, evidence builder, and final activation audit are frozen.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import socket
import ssl
import stat
import struct
from pathlib import Path
from urllib.parse import urlsplit

MESSAGE_FRAME_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/mtls-message-frame/v1\0"
MESSAGE_MAGIC = b"T22A1M1\0"
SECRET_MAGIC = b"T22A1S1\0"
SECRET_KIND_OPENBAO_BOOTSTRAP_BUNDLE = 1
MAX_MESSAGE_FRAME_BYTES = 512 * 1024
MAX_MESSAGE_BYTES = 64 * 1024
MAX_SIGNATURE_BYTES = 64 * 1024
MAX_PAYLOAD_BYTES = 256 * 1024
MAX_SECRET_BYTES = 4096
TRANSPORT_ACTIVATION_READY = False
SOCKET_ADAPTER_ACTIVATION_READY = False
MAX_SOCKET_TIMEOUT_SECONDS = 30.0


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def domain_digest(value: object) -> str:
    return hashlib.sha256(MESSAGE_FRAME_DOMAIN + canonical(value)).hexdigest()


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and value != "0" * 64 and all(character in "0123456789abcdef" for character in value)


def canonical_json_line(raw: bytes, maximum: int, code: str) -> dict:
    require(0 < len(raw) <= maximum and raw.endswith(b"\n") and raw.count(b"\n") == 1, f"{code}_FRAMING")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure(f"{code}_JSON") from error
    require(raw == canonical(value) + b"\n", f"{code}_NOT_CANONICAL")
    require(isinstance(value, dict), f"{code}_SHAPE")
    return value


def decode_base64(value: object, maximum: int, code: str) -> bytes:
    require(isinstance(value, str), code)
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise SafeFailure(code) from error
    require(0 < len(raw) <= maximum, code)
    return raw


def encode_message_frame(direction: str, domain_id: str, message_raw: bytes, signature_raw: bytes, payload_raw: bytes) -> bytes:
    require(direction in {"COORDINATOR_TO_DOMAIN", "DOMAIN_TO_COORDINATOR"}, "E_MTLS_FRAME_DIRECTION")
    require(domain_id in {"domain-1", "domain-2", "domain-3"}, "E_MTLS_FRAME_DOMAIN")
    message = canonical_json_line(message_raw, MAX_MESSAGE_BYTES, "E_MTLS_FRAME_MESSAGE")
    payload = canonical_json_line(payload_raw, MAX_PAYLOAD_BYTES, "E_MTLS_FRAME_PAYLOAD")
    require(0 < len(signature_raw) <= MAX_SIGNATURE_BYTES, "E_MTLS_FRAME_SIGNATURE")
    require(message.get("direction") == direction and message.get("domain_id") == domain_id, "E_MTLS_FRAME_MESSAGE_BINDING")
    require(message.get("run_id") == payload.get("run_id") and message.get("source_commit") == payload.get("source_commit"), "E_MTLS_FRAME_PAYLOAD_RUN")
    require(message.get("execution_contract_sha256") == payload.get("execution_contract_sha256"), "E_MTLS_FRAME_PAYLOAD_EXECUTION")
    payload_sha256 = hashlib.sha256(payload_raw).hexdigest()
    require(message.get("payload_sha256") == payload_sha256, "E_MTLS_FRAME_PAYLOAD_BINDING")
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.mtls_message_frame.v1",
        "direction": direction,
        "domain_id": domain_id,
        "run_id": message["run_id"],
        "source_commit": message["source_commit"],
        "execution_contract_sha256": message["execution_contract_sha256"],
        "sequence": message["sequence"],
        "message_sha256": hashlib.sha256(message_raw).hexdigest(),
        "signature_sha256": hashlib.sha256(signature_raw).hexdigest(),
        "payload_sha256": payload_sha256,
        "message_base64": base64.b64encode(message_raw).decode(),
        "signature_base64": base64.b64encode(signature_raw).decode(),
        "payload_base64": base64.b64encode(payload_raw).decode(),
        "contains_secret_frame": False,
        "raw_endpoint_embedded": False,
        "production_admissible": False,
    }
    value["content_sha256"] = domain_digest(value)
    body = canonical(value) + b"\n"
    require(len(body) <= MAX_MESSAGE_FRAME_BYTES, "E_MTLS_FRAME_SIZE")
    return MESSAGE_MAGIC + struct.pack("!I", len(body)) + body


def decode_message_frame(
    frame: bytes,
    expected_direction: str,
    expected_domain_id: str,
    expected_run_id: str,
    expected_source_commit: str,
    expected_execution_contract_sha256: str,
) -> dict:
    require(len(frame) >= 12 and frame[:8] == MESSAGE_MAGIC, "E_MTLS_FRAME_MAGIC")
    length = struct.unpack("!I", frame[8:12])[0]
    require(0 < length <= MAX_MESSAGE_FRAME_BYTES and len(frame) == 12 + length, "E_MTLS_FRAME_LENGTH")
    value = canonical_json_line(frame[12:], MAX_MESSAGE_FRAME_BYTES, "E_MTLS_FRAME_ENVELOPE")
    required = {
        "schema", "direction", "domain_id", "run_id", "source_commit",
        "execution_contract_sha256", "sequence", "message_sha256",
        "signature_sha256", "payload_sha256", "message_base64",
        "signature_base64", "payload_base64", "contains_secret_frame",
        "raw_endpoint_embedded", "production_admissible", "content_sha256",
    }
    require(set(value) == required, "E_MTLS_FRAME_SHAPE")
    require(value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.mtls_message_frame.v1", "E_MTLS_FRAME_SCHEMA")
    require(value["direction"] == expected_direction and value["domain_id"] == expected_domain_id, "E_MTLS_FRAME_ROUTE")
    require(value["run_id"] == expected_run_id and value["source_commit"] == expected_source_commit, "E_MTLS_FRAME_RUN")
    require(value["execution_contract_sha256"] == expected_execution_contract_sha256, "E_MTLS_FRAME_EXECUTION")
    require(value["contains_secret_frame"] is False and value["raw_endpoint_embedded"] is False, "E_MTLS_FRAME_BOUNDARY")
    require(value["production_admissible"] is False, "E_MTLS_FRAME_CLAIMS")
    message_raw = decode_base64(value["message_base64"], MAX_MESSAGE_BYTES, "E_MTLS_FRAME_MESSAGE_BASE64")
    signature_raw = decode_base64(value["signature_base64"], MAX_SIGNATURE_BYTES, "E_MTLS_FRAME_SIGNATURE_BASE64")
    payload_raw = decode_base64(value["payload_base64"], MAX_PAYLOAD_BYTES, "E_MTLS_FRAME_PAYLOAD_BASE64")
    message = canonical_json_line(message_raw, MAX_MESSAGE_BYTES, "E_MTLS_FRAME_MESSAGE")
    payload = canonical_json_line(payload_raw, MAX_PAYLOAD_BYTES, "E_MTLS_FRAME_PAYLOAD")
    require(hashlib.sha256(message_raw).hexdigest() == value["message_sha256"], "E_MTLS_FRAME_MESSAGE_DIGEST")
    require(hashlib.sha256(signature_raw).hexdigest() == value["signature_sha256"], "E_MTLS_FRAME_SIGNATURE_DIGEST")
    require(hashlib.sha256(payload_raw).hexdigest() == value["payload_sha256"], "E_MTLS_FRAME_PAYLOAD_DIGEST")
    require(message.get("direction") == value["direction"] and message.get("domain_id") == value["domain_id"], "E_MTLS_FRAME_MESSAGE_BINDING")
    require(message.get("run_id") == value["run_id"] == payload.get("run_id"), "E_MTLS_FRAME_PAYLOAD_RUN")
    require(message.get("source_commit") == value["source_commit"] == payload.get("source_commit"), "E_MTLS_FRAME_PAYLOAD_RUN")
    require(message.get("execution_contract_sha256") == value["execution_contract_sha256"] == payload.get("execution_contract_sha256"), "E_MTLS_FRAME_PAYLOAD_EXECUTION")
    require(message.get("sequence") == value["sequence"] and message.get("payload_sha256") == value["payload_sha256"], "E_MTLS_FRAME_SEQUENCE_PAYLOAD")
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256")
    require(claimed == domain_digest(unsigned), "E_MTLS_FRAME_DIGEST")
    return {
        "envelope": value,
        "message": message,
        "message_raw": message_raw,
        "signature_raw": signature_raw,
        "payload": payload,
        "payload_raw": payload_raw,
    }


def encode_secret_frame(secret: bytearray) -> bytes:
    require(isinstance(secret, bytearray) and 16 <= len(secret) <= MAX_SECRET_BYTES, "E_MTLS_SECRET_VALUE")
    raw = bytes(secret)
    return SECRET_MAGIC + bytes([SECRET_KIND_OPENBAO_BOOTSTRAP_BUNDLE]) + struct.pack("!I", len(raw)) + hashlib.sha256(raw).digest() + raw


def decode_secret_frame(frame: bytes, expected_sha256: str) -> bytearray:
    header_size = 8 + 1 + 4 + 32
    require(len(frame) >= header_size and frame[:8] == SECRET_MAGIC, "E_MTLS_SECRET_MAGIC")
    require(frame[8] == SECRET_KIND_OPENBAO_BOOTSTRAP_BUNDLE, "E_MTLS_SECRET_KIND")
    length = struct.unpack("!I", frame[9:13])[0]
    require(16 <= length <= MAX_SECRET_BYTES and len(frame) == header_size + length, "E_MTLS_SECRET_LENGTH")
    claimed = frame[13:45]
    secret = bytearray(frame[45:])
    observed = hashlib.sha256(secret).digest()
    if observed != claimed or observed.hex() != expected_sha256:
        zeroize(secret)
        raise SafeFailure("E_MTLS_SECRET_DIGEST")
    return secret


def zeroize(secret: bytearray) -> None:
    require(isinstance(secret, bytearray), "E_MTLS_SECRET_ZEROIZE_TYPE")
    secret[:] = b"\0" * len(secret)


def read_bound_certificate_file(path_text: object, expected_sha256: object, code: str) -> Path:
    require(TRANSPORT_ACTIVATION_READY, "E_MTLS_TRANSPORT_ACTIVATION_NOT_READY")
    require(isinstance(path_text, str) and Path(path_text).is_absolute() and is_sha256(expected_sha256), code)
    path = Path(path_text)
    require(path.is_file() and not path.is_symlink(), code)
    metadata = path.stat()
    require(
        stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.geteuid()
        and metadata.st_mode & 0o077 == 0 and 0 < metadata.st_size <= 256 * 1024,
        code,
    )
    require(hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256, code)
    return path


def read_bound_private_key(path_text: object, code: str) -> Path:
    require(TRANSPORT_ACTIVATION_READY, "E_MTLS_TRANSPORT_ACTIVATION_NOT_READY")
    require(isinstance(path_text, str) and Path(path_text).is_absolute(), code)
    path = Path(path_text)
    require(path.is_file() and not path.is_symlink(), code)
    metadata = path.stat()
    require(
        stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.geteuid()
        and metadata.st_mode & 0o077 == 0 and 0 < metadata.st_size <= 256 * 1024,
        code,
    )
    return path


def configure_context(context: ssl.SSLContext) -> ssl.SSLContext:
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.options |= ssl.OP_NO_COMPRESSION
    return context


def build_server_context(plan: dict) -> ssl.SSLContext:
    credentials = plan["credentials"]
    require(
        is_sha256(credentials.get("domain_spki_sha256"))
        and credentials.get("domain_private_key_spki_sha256") == credentials["domain_spki_sha256"],
        "E_MTLS_SERVER_KEY_BINDING",
    )
    expected_coordinator_peer_certificate_der_sha256(plan)
    ca = read_bound_certificate_file(credentials["ca_certificate_path"], credentials["ca_certificate_sha256"], "E_MTLS_SERVER_CA")
    certificate = read_bound_certificate_file(credentials["domain_certificate_path"], credentials["domain_certificate_sha256"], "E_MTLS_SERVER_CERTIFICATE")
    private_key = read_bound_private_key(credentials["domain_private_key_path"], "E_MTLS_SERVER_PRIVATE_KEY")
    context = configure_context(ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER))
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=str(ca))
    context.load_cert_chain(certfile=str(certificate), keyfile=str(private_key))
    return context


def build_client_context(coordinator_plan: dict) -> ssl.SSLContext:
    credentials = coordinator_plan["credentials"]
    coordinator = credentials.get("coordinator_material")
    coordinator_trust = credentials.get("coordinator_trust_material")
    require(isinstance(coordinator, dict), "E_MTLS_CLIENT_COORDINATOR_MATERIAL")
    require(isinstance(coordinator_trust, dict), "E_MTLS_CLIENT_COORDINATOR_TRUST")
    require(
        is_sha256(coordinator.get("spki_sha256"))
        and coordinator.get("private_key_spki_sha256") == coordinator["spki_sha256"],
        "E_MTLS_CLIENT_KEY_BINDING",
    )
    require(
        coordinator.get("certificate_path") == coordinator_trust.get("certificate_path")
        and coordinator.get("certificate_sha256") == coordinator_trust.get("certificate_sha256")
        and coordinator.get("spki_sha256") == coordinator_trust.get("spki_sha256"),
        "E_MTLS_CLIENT_COORDINATOR_TRUST_BINDING",
    )
    ca = read_bound_certificate_file(credentials["ca_certificate_path"], credentials["ca_certificate_sha256"], "E_MTLS_CLIENT_CA")
    certificate = read_bound_certificate_file(coordinator["certificate_path"], coordinator["certificate_sha256"], "E_MTLS_CLIENT_CERTIFICATE")
    private_key = read_bound_private_key(coordinator["private_key_path"], "E_MTLS_CLIENT_PRIVATE_KEY")
    context = configure_context(ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_verify_locations(cafile=str(ca))
    context.load_cert_chain(certfile=str(certificate), keyfile=str(private_key))
    return context


def expected_coordinator_peer_certificate_der_sha256(plan: dict) -> str:
    credentials = plan.get("credentials", {})
    trust = credentials.get("coordinator_trust_material")
    require(isinstance(trust, dict), "E_MTLS_SERVER_COORDINATOR_TRUST")
    require(is_sha256(trust.get("spki_sha256")), "E_MTLS_SERVER_COORDINATOR_TRUST")
    certificate = read_bound_certificate_file(
        trust.get("certificate_path"), trust.get("certificate_sha256"),
        "E_MTLS_SERVER_COORDINATOR_CERTIFICATE",
    )
    try:
        der = ssl.PEM_cert_to_DER_cert(certificate.read_text(encoding="ascii"))
    except (OSError, UnicodeError, ValueError) as error:
        raise SafeFailure("E_MTLS_SERVER_COORDINATOR_CERTIFICATE") from error
    require(isinstance(der, bytes) and der, "E_MTLS_SERVER_COORDINATOR_CERTIFICATE")
    return hashlib.sha256(der).hexdigest()


def verify_coordinator_peer_certificate(
    plan: dict,
    tls_object: ssl.SSLObject | ssl.SSLSocket,
) -> str:
    return verify_peer_certificate_sha256(
        tls_object,
        expected_coordinator_peer_certificate_der_sha256(plan),
    )


def verify_peer_certificate_sha256(
    tls_object: ssl.SSLObject | ssl.SSLSocket,
    expected_der_sha256: str,
) -> str:
    require(is_sha256(expected_der_sha256), "E_MTLS_PEER_CERTIFICATE_EXPECTED_DIGEST")
    certificate = tls_object.getpeercert(binary_form=True)
    require(isinstance(certificate, bytes) and certificate, "E_MTLS_PEER_CERTIFICATE")
    observed = hashlib.sha256(certificate).hexdigest()
    require(observed == expected_der_sha256, "E_MTLS_PEER_CERTIFICATE_BINDING")
    return observed


def agent_address(plan: dict) -> tuple[int, str, int]:
    network = plan.get("network", {})
    ip_text = network.get("overlay_ip")
    endpoint_text = network.get("agent_control_endpoint")
    require(isinstance(ip_text, str) and isinstance(endpoint_text, str), "E_MTLS_AGENT_ENDPOINT")
    try:
        address = ipaddress.ip_address(ip_text)
        parsed = urlsplit(endpoint_text)
        port = parsed.port
        parsed_hostname = parsed.hostname
        parsed_username = parsed.username
        parsed_password = parsed.password
    except (ValueError, TypeError) as error:
        raise SafeFailure("E_MTLS_AGENT_ENDPOINT") from error
    require(
        parsed.scheme == "https" and parsed_hostname == address.compressed
        and parsed_username is None and parsed_password is None
        and parsed.path == "" and parsed.query == "" and parsed.fragment == ""
        and isinstance(port, int) and 1 <= port <= 65535,
        "E_MTLS_AGENT_ENDPOINT",
    )
    canonical_host = f"[{address.compressed}]" if address.version == 6 else address.compressed
    require(endpoint_text == f"https://{canonical_host}:{port}", "E_MTLS_AGENT_ENDPOINT")
    family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
    return family, address.compressed, port


def bounded_timeout(value: object) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and 0 < float(value) <= MAX_SOCKET_TIMEOUT_SECONDS,
        "E_MTLS_SOCKET_TIMEOUT",
    )
    return float(value)


def validate_connection_plans(coordinator_plan: dict, domain_plan: dict) -> None:
    require(coordinator_plan.get("domain_id") == "domain-1", "E_MTLS_COORDINATOR_PLAN")
    require(domain_plan.get("domain_id") in {"domain-1", "domain-2", "domain-3"}, "E_MTLS_DOMAIN_PLAN")
    for field in ("run_id", "source_commit"):
        require(
            coordinator_plan.get(field) == domain_plan.get(field)
            and isinstance(coordinator_plan.get(field), str),
            "E_MTLS_PLAN_RUN_BINDING",
        )
    coordinator_execution = coordinator_plan.get("bindings", {}).get("execution_contract_sha256")
    domain_execution = domain_plan.get("bindings", {}).get("execution_contract_sha256")
    require(
        is_sha256(coordinator_execution) and coordinator_execution == domain_execution,
        "E_MTLS_PLAN_EXECUTION_BINDING",
    )


def connect_coordinator_to_domain(
    coordinator_plan: dict,
    domain_plan: dict,
    expected_domain_certificate_der_sha256: str,
    timeout_seconds: float,
) -> ssl.SSLSocket:
    require(SOCKET_ADAPTER_ACTIVATION_READY, "E_MTLS_SOCKET_ADAPTER_ACTIVATION_NOT_READY")
    validate_connection_plans(coordinator_plan, domain_plan)
    require(is_sha256(expected_domain_certificate_der_sha256), "E_MTLS_DOMAIN_PEER_EXPECTED_DIGEST")
    timeout = bounded_timeout(timeout_seconds)
    family, ip_text, port = agent_address(domain_plan)
    coordinator_family, coordinator_ip_text, _coordinator_port = agent_address(coordinator_plan)
    require(coordinator_family == family, "E_MTLS_COORDINATOR_ADDRESS_FAMILY")
    context = build_client_context(coordinator_plan)
    raw_socket: socket.socket | None = None
    tls_socket: ssl.SSLSocket | None = None
    try:
        raw_socket = socket.socket(family, socket.SOCK_STREAM)
        raw_socket.settimeout(timeout)
        raw_socket.bind((coordinator_ip_text, 0))
        raw_socket.connect((ip_text, port))
        tls_socket = context.wrap_socket(raw_socket, server_hostname=ip_text)
        verify_peer_certificate_sha256(tls_socket, expected_domain_certificate_der_sha256)
        return tls_socket
    except SafeFailure:
        if tls_socket is not None:
            tls_socket.close()
        elif raw_socket is not None:
            raw_socket.close()
        raise
    except (OSError, ssl.SSLError, ValueError) as error:
        if tls_socket is not None:
            tls_socket.close()
        elif raw_socket is not None:
            raw_socket.close()
        raise SafeFailure("E_MTLS_CLIENT_CONNECTION") from error


class DomainAgentListener:
    """One-shot exact-address listener; no retry or second accept is exposed."""

    def __init__(self, plan: dict, listener: socket.socket, context: ssl.SSLContext, timeout_seconds: float) -> None:
        self.plan = plan
        self.listener = listener
        self.context = context
        self.timeout_seconds = timeout_seconds
        self.consumed = False

    def close(self) -> None:
        self.listener.close()

    def accept_exact_coordinator(self, coordinator_plan: dict) -> ssl.SSLSocket:
        require(not self.consumed, "E_MTLS_LISTENER_ALREADY_CONSUMED")
        self.consumed = True
        validate_connection_plans(coordinator_plan, self.plan)
        _family, expected_ip, _port = agent_address(coordinator_plan)
        accepted: socket.socket | None = None
        tls_socket: ssl.SSLSocket | None = None
        try:
            accepted, peer = self.listener.accept()
            self.listener.close()
            require(isinstance(peer, tuple) and len(peer) >= 2 and isinstance(peer[0], str), "E_MTLS_COORDINATOR_SOURCE_IP")
            try:
                observed_ip = ipaddress.ip_address(peer[0]).compressed
            except ValueError as error:
                raise SafeFailure("E_MTLS_COORDINATOR_SOURCE_IP") from error
            require(observed_ip == expected_ip, "E_MTLS_COORDINATOR_SOURCE_IP")
            accepted.settimeout(self.timeout_seconds)
            tls_socket = self.context.wrap_socket(accepted, server_side=True)
            verify_coordinator_peer_certificate(self.plan, tls_socket)
            return tls_socket
        except SafeFailure:
            if tls_socket is not None:
                tls_socket.close()
            elif accepted is not None:
                accepted.close()
            self.listener.close()
            raise
        except (OSError, ssl.SSLError, ValueError) as error:
            if tls_socket is not None:
                tls_socket.close()
            elif accepted is not None:
                accepted.close()
            self.listener.close()
            raise SafeFailure("E_MTLS_SERVER_CONNECTION") from error


def open_domain_agent_listener(plan: dict, timeout_seconds: float) -> DomainAgentListener:
    require(SOCKET_ADAPTER_ACTIVATION_READY, "E_MTLS_SOCKET_ADAPTER_ACTIVATION_NOT_READY")
    timeout = bounded_timeout(timeout_seconds)
    family, ip_text, port = agent_address(plan)
    context = build_server_context(plan)
    listener: socket.socket | None = None
    try:
        listener = socket.socket(family, socket.SOCK_STREAM)
        listener.settimeout(timeout)
        listener.bind((ip_text, port))
        listener.listen(1)
        return DomainAgentListener(plan, listener, context, timeout)
    except (OSError, ssl.SSLError, ValueError) as error:
        if listener is not None:
            listener.close()
        raise SafeFailure("E_MTLS_SERVER_LISTENER") from error


def receive_exact(tls_socket: ssl.SSLSocket, length: int, code: str) -> bytes:
    require(isinstance(length, int) and 0 < length <= MAX_MESSAGE_FRAME_BYTES, code)
    value = bytearray()
    while len(value) < length:
        try:
            chunk = tls_socket.recv(length - len(value))
        except (OSError, ssl.SSLError) as error:
            raise SafeFailure(code) from error
        require(isinstance(chunk, bytes) and chunk, code)
        value.extend(chunk)
    return bytes(value)


def _send_bounded_frame(tls_socket: ssl.SSLSocket, frame: bytes, expected_magic: bytes, maximum: int) -> None:
    require(isinstance(frame, bytes) and len(frame) <= maximum and frame.startswith(expected_magic), "E_MTLS_SEND_FRAME")
    try:
        tls_socket.sendall(frame)
    except (OSError, ssl.SSLError) as error:
        raise SafeFailure("E_MTLS_SEND_FRAME") from error


def send_message_frame(tls_socket: ssl.SSLSocket, frame: bytes) -> None:
    require(
        isinstance(frame, bytes) and len(frame) >= 12
        and struct.unpack("!I", frame[8:12])[0] == len(frame) - 12,
        "E_MTLS_SEND_FRAME",
    )
    _send_bounded_frame(tls_socket, frame, MESSAGE_MAGIC, 12 + MAX_MESSAGE_FRAME_BYTES)


def send_secret_frame(tls_socket: ssl.SSLSocket, frame: bytes) -> None:
    require(
        isinstance(frame, bytes) and len(frame) >= 45
        and frame[8] == SECRET_KIND_OPENBAO_BOOTSTRAP_BUNDLE
        and struct.unpack("!I", frame[9:13])[0] == len(frame) - 45,
        "E_MTLS_SEND_FRAME",
    )
    _send_bounded_frame(tls_socket, frame, SECRET_MAGIC, 45 + MAX_SECRET_BYTES)


def receive_message_frame(tls_socket: ssl.SSLSocket) -> bytes:
    header = receive_exact(tls_socket, 12, "E_MTLS_RECEIVE_MESSAGE")
    require(header[:8] == MESSAGE_MAGIC, "E_MTLS_RECEIVE_MESSAGE")
    length = struct.unpack("!I", header[8:])[0]
    require(0 < length <= MAX_MESSAGE_FRAME_BYTES, "E_MTLS_RECEIVE_MESSAGE")
    return header + receive_exact(tls_socket, length, "E_MTLS_RECEIVE_MESSAGE")


def receive_secret_frame(tls_socket: ssl.SSLSocket) -> bytes:
    header = receive_exact(tls_socket, 45, "E_MTLS_RECEIVE_SECRET")
    require(header[:8] == SECRET_MAGIC and header[8] == SECRET_KIND_OPENBAO_BOOTSTRAP_BUNDLE, "E_MTLS_RECEIVE_SECRET")
    length = struct.unpack("!I", header[9:13])[0]
    require(16 <= length <= MAX_SECRET_BYTES, "E_MTLS_RECEIVE_SECRET")
    return header + receive_exact(tls_socket, length, "E_MTLS_RECEIVE_SECRET")


def status() -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.mtls_transport_status.v0",
        "status": "OFFLINE_MTLS_FRAMING_AND_LIVE_SOCKET_ADAPTER_READY_ACTIVATION_GATE_CLOSED",
        "transport_activation_ready": TRANSPORT_ACTIVATION_READY,
        "socket_adapter_activation_ready": SOCKET_ADAPTER_ACTIVATION_READY,
        "real_certificate_or_key_files_read": 0,
        "network_accessed": False,
        "listeners_started": 0,
        "external_hosts_contacted": 0,
        "secret_frames_persisted": 0,
        "services_started": 0,
        "faults_injected": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }


if __name__ == "__main__":
    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
