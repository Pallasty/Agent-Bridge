"""Synthetic no-socket KAT for T22-A1 mTLS contexts and framing."""
from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import shutil
import ssl
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_mtls_transport_v1.py"
spec = importlib.util.spec_from_file_location("t22a1mtlstransport", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

RUN_ID = "t22-a1-20260722T220000.000000z-123456789abc"
SOURCE_COMMIT = "a" * 40
EXECUTION_SHA256 = hashlib.sha256(b"synthetic-execution").hexdigest()


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def certificate_der_sha256(path: Path) -> str:
    der = ssl.PEM_cert_to_DER_cert(path.read_text())
    return hashlib.sha256(der).hexdigest()


def run(arguments: list[str]) -> None:
    result = subprocess.run(arguments, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    assert result.returncode == 0, arguments


def create_ca(root: Path, name: str) -> tuple[Path, Path]:
    key = root / f"{name}.key"
    certificate = root / f"{name}.crt"
    run([OPENSSL, "genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", str(key)])
    run([
        OPENSSL, "req", "-x509", "-new", "-key", str(key), "-sha256", "-days", "1",
        "-subj", f"/CN={name}", "-addext", "basicConstraints=critical,CA:TRUE,pathlen:0",
        "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-out", str(certificate),
    ])
    return key, certificate


def create_leaf(root: Path, ca_key: Path, ca_certificate: Path, name: str, usage: str, ip: str | None) -> tuple[Path, Path]:
    key = root / f"{name}.key"
    request = root / f"{name}.csr"
    certificate = root / f"{name}.crt"
    extensions = root / f"{name}.ext"
    run([OPENSSL, "genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", str(key)])
    run([OPENSSL, "req", "-new", "-key", str(key), "-subj", f"/CN={name}", "-out", str(request)])
    lines = ["basicConstraints=critical,CA:FALSE", "keyUsage=critical,digitalSignature", f"extendedKeyUsage={usage}"]
    if ip is not None:
        lines.append(f"subjectAltName=IP:{ip}")
    extensions.write_text("\n".join(lines) + "\n")
    serial = root / f"{name}.srl"
    run([
        OPENSSL, "x509", "-req", "-in", str(request), "-CA", str(ca_certificate),
        "-CAkey", str(ca_key), "-CAcreateserial", "-CAserial", str(serial),
        "-out", str(certificate), "-days", "1", "-sha256", "-extfile", str(extensions),
    ])
    request.unlink()
    extensions.unlink()
    if serial.exists():
        serial.unlink()
    return key, certificate


def plan(
    ca: Path,
    domain_certificate: Path,
    domain_key: Path,
    coordinator_trust_certificate: Path,
    coordinator_key: Path | None = None,
    domain_id: str = "domain-1",
    overlay_ip: str = "100.64.50.1",
) -> dict:
    coordinator = None
    if coordinator_key is not None:
        coordinator = {
            "certificate_path": str(coordinator_trust_certificate),
            "private_key_path": str(coordinator_key),
            "certificate_sha256": sha_file(coordinator_trust_certificate),
            "spki_sha256": hashlib.sha256(b"synthetic-coordinator-spki").hexdigest(),
            "private_key_spki_sha256": hashlib.sha256(b"synthetic-coordinator-spki").hexdigest(),
        }
    return {
        "domain_id": domain_id,
        "run_id": RUN_ID,
        "source_commit": SOURCE_COMMIT,
        "bindings": {"execution_contract_sha256": EXECUTION_SHA256},
        "network": {
            "overlay_ip": overlay_ip,
            "agent_control_endpoint": f"https://{overlay_ip}:29000",
        },
        "credentials": {
            "ca_certificate_path": str(ca), "ca_certificate_sha256": sha_file(ca),
            "domain_certificate_path": str(domain_certificate),
            "domain_certificate_sha256": sha_file(domain_certificate),
            "domain_spki_sha256": hashlib.sha256(b"synthetic-domain-spki").hexdigest(),
            "domain_private_key_spki_sha256": hashlib.sha256(b"synthetic-domain-spki").hexdigest(),
            "domain_private_key_path": str(domain_key),
            "coordinator_trust_material": {
                "certificate_path": str(coordinator_trust_certificate),
                "certificate_sha256": sha_file(coordinator_trust_certificate),
                "spki_sha256": hashlib.sha256(b"synthetic-coordinator-spki").hexdigest(),
                "runtime_public_key_path": str(coordinator_trust_certificate.parent / "coordinator-runtime.pub"),
                "runtime_public_key_sha256": hashlib.sha256(b"synthetic-runtime-public-key").hexdigest(),
            },
            "coordinator_material": coordinator,
        },
    }


def transfer(source: ssl.MemoryBIO, target: ssl.MemoryBIO) -> int:
    raw = source.read()
    if not raw:
        return 0
    target.write(raw)
    return len(raw)


def memory_handshake(client_context: ssl.SSLContext, server_context: ssl.SSLContext, server_hostname: str) -> tuple[ssl.SSLObject, ssl.SSLObject, ssl.MemoryBIO, ssl.MemoryBIO]:
    client_in, client_out = ssl.MemoryBIO(), ssl.MemoryBIO()
    server_in, server_out = ssl.MemoryBIO(), ssl.MemoryBIO()
    client = client_context.wrap_bio(client_in, client_out, server_side=False, server_hostname=server_hostname)
    server = server_context.wrap_bio(server_in, server_out, server_side=True)
    client_done = server_done = False
    for _ in range(100):
        if not client_done:
            try:
                client.do_handshake()
                client_done = True
            except ssl.SSLWantReadError:
                pass
        transfer(client_out, server_in)
        if not server_done:
            try:
                server.do_handshake()
                server_done = True
            except ssl.SSLWantReadError:
                pass
        transfer(server_out, client_in)
        if client_done and server_done:
            return client, server, client_out, server_in
    raise AssertionError("synthetic in-memory TLS handshake did not complete")


def message_and_payload(direction: str = "COORDINATOR_TO_DOMAIN", domain_id: str = "domain-1") -> tuple[bytes, bytes]:
    payload = {
        "schema": "synthetic.t22_a1.command_payload.v0", "run_id": RUN_ID,
        "source_commit": SOURCE_COMMIT, "execution_contract_sha256": EXECUTION_SHA256,
        "domain_id": domain_id, "command": "PREFLIGHT",
    }
    payload_raw = module.canonical(payload) + b"\n"
    message = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_agent_message.v1",
        "direction": direction, "domain_id": domain_id, "run_id": RUN_ID,
        "source_commit": SOURCE_COMMIT, "execution_contract_sha256": EXECUTION_SHA256,
        "sequence": 0, "payload_sha256": hashlib.sha256(payload_raw).hexdigest(),
    }
    return module.canonical(message) + b"\n", payload_raw


def expect_failure(action, expected: str) -> None:  # noqa: ANN001
    try:
        action()
    except module.SafeFailure as error:
        assert str(error) == expected, (str(error), expected)
        return
    raise AssertionError(f"unsafe mTLS transport input admitted: {expected}")


message_raw, payload_raw = message_and_payload()
signature_raw = b"-----BEGIN SSH SIGNATURE-----\nSYNTHETIC\n-----END SSH SIGNATURE-----\n"
frame = module.encode_message_frame("COORDINATOR_TO_DOMAIN", "domain-1", message_raw, signature_raw, payload_raw)
decoded = module.decode_message_frame(
    frame, "COORDINATOR_TO_DOMAIN", "domain-1", RUN_ID, SOURCE_COMMIT, EXECUTION_SHA256,
)
assert decoded["message_raw"] == message_raw and decoded["payload_raw"] == payload_raw
assert decoded["signature_raw"] == signature_raw

negative_count = 0
for arguments, expected in (
    ((frame, "DOMAIN_TO_COORDINATOR", "domain-1", RUN_ID, SOURCE_COMMIT, EXECUTION_SHA256), "E_MTLS_FRAME_ROUTE"),
    ((frame, "COORDINATOR_TO_DOMAIN", "domain-2", RUN_ID, SOURCE_COMMIT, EXECUTION_SHA256), "E_MTLS_FRAME_ROUTE"),
    ((frame, "COORDINATOR_TO_DOMAIN", "domain-1", "other-run", SOURCE_COMMIT, EXECUTION_SHA256), "E_MTLS_FRAME_RUN"),
    ((frame, "COORDINATOR_TO_DOMAIN", "domain-1", RUN_ID, "b" * 40, EXECUTION_SHA256), "E_MTLS_FRAME_RUN"),
    ((frame, "COORDINATOR_TO_DOMAIN", "domain-1", RUN_ID, SOURCE_COMMIT, hashlib.sha256(b"other").hexdigest()), "E_MTLS_FRAME_EXECUTION"),
):
    expect_failure(lambda arguments=arguments: module.decode_message_frame(*arguments), expected)
    negative_count += 1

expect_failure(lambda: module.decode_message_frame(b"BADMAGIC" + frame[8:], "COORDINATOR_TO_DOMAIN", "domain-1", RUN_ID, SOURCE_COMMIT, EXECUTION_SHA256), "E_MTLS_FRAME_MAGIC")
negative_count += 1
expect_failure(lambda: module.decode_message_frame(frame[:-1], "COORDINATOR_TO_DOMAIN", "domain-1", RUN_ID, SOURCE_COMMIT, EXECUTION_SHA256), "E_MTLS_FRAME_LENGTH")
negative_count += 1


def mutate_frame(mutation, rehash: bool = True) -> bytes:  # noqa: ANN001
    value = json.loads(frame[12:])
    mutation(value)
    if rehash:
        value.pop("content_sha256", None)
        value["content_sha256"] = module.domain_digest(value)
    body = module.canonical(value) + b"\n"
    return module.MESSAGE_MAGIC + struct.pack("!I", len(body)) + body


for mutation, expected in (
    (lambda x: x.update(contains_secret_frame=True), "E_MTLS_FRAME_BOUNDARY"),
    (lambda x: x.update(raw_endpoint_embedded=True), "E_MTLS_FRAME_BOUNDARY"),
    (lambda x: x.update(production_admissible=True), "E_MTLS_FRAME_CLAIMS"),
    (lambda x: x.update(message_base64="%%%"), "E_MTLS_FRAME_MESSAGE_BASE64"),
    (lambda x: x.update(payload_sha256=hashlib.sha256(b"other-payload").hexdigest()), "E_MTLS_FRAME_PAYLOAD_DIGEST"),
):
    expect_failure(
        lambda mutation=mutation, expected=expected: module.decode_message_frame(
            mutate_frame(mutation), "COORDINATOR_TO_DOMAIN", "domain-1", RUN_ID, SOURCE_COMMIT, EXECUTION_SHA256,
        ),
        expected,
    )
    negative_count += 1
expect_failure(
    lambda: module.decode_message_frame(mutate_frame(lambda x: x.update(content_sha256=hashlib.sha256(b"forged").hexdigest()), rehash=False), "COORDINATOR_TO_DOMAIN", "domain-1", RUN_ID, SOURCE_COMMIT, EXECUTION_SHA256),
    "E_MTLS_FRAME_DIGEST",
)
negative_count += 1

wrong_message, _ = message_and_payload(direction="DOMAIN_TO_COORDINATOR")
expect_failure(lambda: module.encode_message_frame("COORDINATOR_TO_DOMAIN", "domain-1", wrong_message, signature_raw, payload_raw), "E_MTLS_FRAME_MESSAGE_BINDING")
negative_count += 1
bad_payload = copy.deepcopy(json.loads(payload_raw))
bad_payload["run_id"] = "other-run"
bad_payload_raw = module.canonical(bad_payload) + b"\n"
expect_failure(lambda: module.encode_message_frame("COORDINATOR_TO_DOMAIN", "domain-1", message_raw, signature_raw, bad_payload_raw), "E_MTLS_FRAME_PAYLOAD_RUN")
negative_count += 1

secret = bytearray(b"SYNTHETIC-UNSEAL-SHARE-ONLY")
secret_sha256 = hashlib.sha256(secret).hexdigest()
secret_frame = module.encode_secret_frame(secret)
decoded_secret = module.decode_secret_frame(secret_frame, secret_sha256)
assert decoded_secret == secret
module.zeroize(decoded_secret)
assert decoded_secret == bytearray(len(decoded_secret))
log_rows = [
    {"name": name, "raw": f"T22_A1_SYNTHETIC_ONLY:{name}\n".encode()}
    for name in module.EXPECTED_LOG_NAMES
]
log_frame = module.encode_log_bundle_frame(
    "domain-1", RUN_ID, SOURCE_COMMIT, EXECUTION_SHA256, log_rows,
)
assert module.decode_log_bundle_frame(
    log_frame, "domain-1", RUN_ID, SOURCE_COMMIT, EXECUTION_SHA256,
) == log_rows
tampered_log_frame = bytearray(log_frame)
tampered_log_frame[-1] ^= 1
expect_failure(
    lambda: module.decode_log_bundle_frame(
        bytes(tampered_log_frame), "domain-1", RUN_ID, SOURCE_COMMIT, EXECUTION_SHA256,
    ),
    "E_MTLS_LOG_FRAME_DIGEST",
)
negative_count += 1
for candidate, expected in (
    (b"BADMAGIC" + secret_frame[8:], "E_MTLS_SECRET_MAGIC"),
    (secret_frame[:8] + b"\x02" + secret_frame[9:], "E_MTLS_SECRET_KIND"),
    (secret_frame[:-1], "E_MTLS_SECRET_LENGTH"),
):
    expect_failure(lambda candidate=candidate: module.decode_secret_frame(candidate, secret_sha256), expected)
    negative_count += 1
expect_failure(lambda: module.decode_secret_frame(secret_frame, hashlib.sha256(b"other-secret").hexdigest()), "E_MTLS_SECRET_DIGEST")
negative_count += 1

OPENSSL = shutil.which("openssl") or ""
assert OPENSSL
with tempfile.TemporaryDirectory(prefix="t22-a1-mtls-kat-") as directory:
    root = Path(directory).resolve()
    ca_key, ca_certificate = create_ca(root, "synthetic-ca")
    server_key, server_certificate = create_leaf(root, ca_key, ca_certificate, "domain-1", "serverAuth,clientAuth", "100.64.50.1")
    client_key, client_certificate = create_leaf(root, ca_key, ca_certificate, "coordinator", "clientAuth", None)
    impostor_client_key, impostor_client_certificate = create_leaf(root, ca_key, ca_certificate, "same-ca-impostor", "clientAuth", None)
    wrong_ca_key, wrong_ca_certificate = create_ca(root, "wrong-ca")
    wrong_client_key, wrong_client_certificate = create_leaf(root, wrong_ca_key, wrong_ca_certificate, "wrong-client", "clientAuth", None)
    for path in root.iterdir():
        if path.is_file():
            path.chmod(0o600)

    server_plan = plan(ca_certificate, server_certificate, server_key, client_certificate)
    client_plan = plan(ca_certificate, server_certificate, server_key, client_certificate, client_key)
    expect_failure(lambda: module.build_server_context(server_plan), "E_MTLS_TRANSPORT_ACTIVATION_NOT_READY")
    negative_count += 1
    module.TRANSPORT_ACTIVATION_READY = True
    server_context = module.build_server_context(server_plan)
    client_context = module.build_client_context(client_plan)
    client_tls, server_tls, client_out, server_in = memory_handshake(client_context, server_context, "100.64.50.1")
    module.verify_peer_certificate_sha256(client_tls, certificate_der_sha256(server_certificate))
    module.verify_coordinator_peer_certificate(server_plan, server_tls)
    expect_failure(
        lambda: module.verify_peer_certificate_sha256(client_tls, hashlib.sha256(b"other-certificate").hexdigest()),
        "E_MTLS_PEER_CERTIFICATE_BINDING",
    )
    negative_count += 1
    assert client_tls.version() in {"TLSv1.2", "TLSv1.3"}

    client_tls.write(frame)
    transfer(client_out, server_in)
    received = bytearray()
    while len(received) < len(frame):
        try:
            received.extend(server_tls.read(len(frame) - len(received)))
        except ssl.SSLWantReadError:
            transfer(client_out, server_in)
    assert bytes(received) == frame
    module.decode_message_frame(bytes(received), "COORDINATOR_TO_DOMAIN", "domain-1", RUN_ID, SOURCE_COMMIT, EXECUTION_SHA256)

    impostor_client_plan = plan(ca_certificate, server_certificate, server_key, impostor_client_certificate, impostor_client_key)
    impostor_client_context = module.build_client_context(impostor_client_plan)
    _impostor_client_tls, impostor_server_tls, _impostor_client_out, _impostor_server_in = memory_handshake(
        impostor_client_context, server_context, "100.64.50.1",
    )
    expect_failure(
        lambda: module.verify_coordinator_peer_certificate(server_plan, impostor_server_tls),
        "E_MTLS_PEER_CERTIFICATE_BINDING",
    )
    negative_count += 1

    bad_client_plan = plan(ca_certificate, server_certificate, server_key, wrong_client_certificate, wrong_client_key)
    bad_client_context = module.build_client_context(bad_client_plan)
    try:
        memory_handshake(bad_client_context, server_context, "100.64.50.1")
    except ssl.SSLError:
        pass
    else:
        raise AssertionError("client certificate from wrong CA admitted")
    negative_count += 1

    try:
        memory_handshake(client_context, server_context, "100.64.50.9")
    except ssl.SSLError:
        pass
    else:
        raise AssertionError("wrong TLS server IP admitted")
    negative_count += 1

    wrong_hash_plan = copy.deepcopy(server_plan)
    wrong_hash_plan["credentials"]["domain_certificate_sha256"] = hashlib.sha256(b"wrong").hexdigest()
    expect_failure(lambda: module.build_server_context(wrong_hash_plan), "E_MTLS_SERVER_CERTIFICATE")
    negative_count += 1

    wrong_ca_hash_plan = copy.deepcopy(server_plan)
    wrong_ca_hash_plan["credentials"]["ca_certificate_sha256"] = hashlib.sha256(b"wrong-ca").hexdigest()
    expect_failure(lambda: module.build_server_context(wrong_ca_hash_plan), "E_MTLS_SERVER_CA")
    negative_count += 1

    server_certificate.chmod(0o644)
    expect_failure(lambda: module.build_server_context(server_plan), "E_MTLS_SERVER_CERTIFICATE")
    server_certificate.chmod(0o600)
    negative_count += 1

    server_key.chmod(0o644)
    expect_failure(lambda: module.build_server_context(server_plan), "E_MTLS_SERVER_PRIVATE_KEY")
    server_key.chmod(0o600)
    negative_count += 1

    target_plan = plan(
        ca_certificate, server_certificate, server_key, client_certificate,
        domain_id="domain-2", overlay_ip="100.64.50.2",
    )
    expect_failure(
        lambda: module.connect_coordinator_to_domain(
            client_plan, target_plan, certificate_der_sha256(server_certificate), 5,
        ),
        "E_MTLS_SOCKET_ADAPTER_ACTIVATION_NOT_READY",
    )
    negative_count += 1

    class FakeTLSSocket:
        def __init__(self, peer_der: bytes, incoming: bytes = b"") -> None:
            self.peer_der = peer_der
            self.incoming = bytearray(incoming)
            self.sent = bytearray()
            self.closed = False
            self.timeout: float | None = None

        def getpeercert(self, binary_form: bool = False):  # noqa: ANN201
            return self.peer_der if binary_form else {}

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def sendall(self, value: bytes) -> None:
            self.sent.extend(value)

        def recv(self, length: int) -> bytes:
            value = bytes(self.incoming[:length])
            del self.incoming[:length]
            return value

        def close(self) -> None:
            self.closed = True

    class FakeRawSocket:
        def __init__(self, accepted: tuple[FakeTLSSocket, tuple] | None = None) -> None:
            self.accepted = accepted
            self.timeout: float | None = None
            self.connected: tuple | None = None
            self.bound: tuple | None = None
            self.backlog: int | None = None
            self.closed = False

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def connect(self, address: tuple) -> None:
            self.connected = address

        def bind(self, address: tuple) -> None:
            self.bound = address

        def listen(self, backlog: int) -> None:
            self.backlog = backlog

        def accept(self) -> tuple[FakeTLSSocket, tuple]:
            assert self.accepted is not None
            return self.accepted

        def close(self) -> None:
            self.closed = True

    class FakeContext:
        def __init__(self, tls_socket: FakeTLSSocket) -> None:
            self.tls_socket = tls_socket
            self.server_hostname: str | None = None
            self.server_side: bool | None = None

        def wrap_socket(self, _raw_socket, server_hostname=None, server_side=False):  # noqa: ANN001, ANN201
            self.server_hostname = server_hostname
            self.server_side = server_side
            return self.tls_socket

    server_der = ssl.PEM_cert_to_DER_cert(server_certificate.read_text())
    coordinator_der = ssl.PEM_cert_to_DER_cert(client_certificate.read_text())
    original_socket_factory = module.socket.socket
    original_client_context_builder = module.build_client_context
    original_server_context_builder = module.build_server_context
    module.SOCKET_ADAPTER_ACTIVATION_READY = True
    try:
        fake_client_raw = FakeRawSocket()
        fake_client_tls = FakeTLSSocket(server_der)
        fake_client_context = FakeContext(fake_client_tls)
        module.socket.socket = lambda _family, _kind: fake_client_raw
        module.build_client_context = lambda _plan: fake_client_context
        connected = module.connect_coordinator_to_domain(
            client_plan, target_plan, hashlib.sha256(server_der).hexdigest(), 5,
        )
        assert connected is fake_client_tls
        assert fake_client_raw.bound == ("100.64.50.1", 0)
        assert fake_client_raw.connected == ("100.64.50.2", 29000)
        assert fake_client_raw.timeout == 5 and fake_client_context.server_hostname == "100.64.50.2"

        ipv6_target_plan = copy.deepcopy(target_plan)
        ipv6_target_plan["network"]["overlay_ip"] = "fd00::2"
        ipv6_target_plan["network"]["agent_control_endpoint"] = "https://[fd00::2]:29000"
        expect_failure(
            lambda: module.connect_coordinator_to_domain(
                client_plan, ipv6_target_plan, hashlib.sha256(server_der).hexdigest(), 5,
            ),
            "E_MTLS_COORDINATOR_ADDRESS_FAMILY",
        )
        negative_count += 1

        fake_received = FakeTLSSocket(server_der, frame + secret_frame + log_frame)
        assert module.receive_message_frame(fake_received) == frame
        assert module.receive_secret_frame(fake_received) == secret_frame
        assert module.receive_log_bundle_frame(fake_received) == log_frame
        module.send_message_frame(fake_received, frame)
        module.send_secret_frame(fake_received, secret_frame)
        module.send_log_bundle_frame(fake_received, log_frame)
        assert bytes(fake_received.sent) == frame + secret_frame + log_frame

        accepted_socket = FakeTLSSocket(coordinator_der)
        fake_listener_raw = FakeRawSocket((accepted_socket, ("100.64.50.1", 45000)))
        fake_server_context = FakeContext(accepted_socket)
        module.socket.socket = lambda _family, _kind: fake_listener_raw
        module.build_server_context = lambda _plan: fake_server_context
        listener = module.open_domain_agent_listener(target_plan, 5)
        assert fake_listener_raw.bound == ("100.64.50.2", 29000) and fake_listener_raw.backlog == 1
        accepted_tls = listener.accept_exact_coordinator(client_plan)
        assert accepted_tls is accepted_socket and fake_server_context.server_side is True
        expect_failure(lambda: listener.accept_exact_coordinator(client_plan), "E_MTLS_LISTENER_ALREADY_CONSUMED")
        negative_count += 1

        wrong_source_socket = FakeTLSSocket(coordinator_der)
        wrong_source_listener = FakeRawSocket((wrong_source_socket, ("100.64.50.9", 45000)))
        module.socket.socket = lambda _family, _kind: wrong_source_listener
        second_listener = module.open_domain_agent_listener(target_plan, 5)
        expect_failure(lambda: second_listener.accept_exact_coordinator(client_plan), "E_MTLS_COORDINATOR_SOURCE_IP")
        negative_count += 1
    finally:
        module.socket.socket = original_socket_factory
        module.build_client_context = original_client_context_builder
        module.build_server_context = original_server_context_builder
        module.SOCKET_ADAPTER_ACTIVATION_READY = False

    malformed_endpoint_plan = copy.deepcopy(target_plan)
    malformed_endpoint_plan["network"]["agent_control_endpoint"] = "https://example.invalid:29000"
    expect_failure(lambda: module.agent_address(malformed_endpoint_plan), "E_MTLS_AGENT_ENDPOINT")
    negative_count += 1
    expect_failure(lambda: module.bounded_timeout(31), "E_MTLS_SOCKET_TIMEOUT")
    negative_count += 1
    mismatched_run_plan = copy.deepcopy(target_plan)
    mismatched_run_plan["run_id"] = "other-run"
    expect_failure(lambda: module.validate_connection_plans(client_plan, mismatched_run_plan), "E_MTLS_PLAN_RUN_BINDING")
    negative_count += 1
    expect_failure(lambda: module.receive_message_frame(FakeTLSSocket(server_der, b"short")), "E_MTLS_RECEIVE_MESSAGE")
    negative_count += 1
    expect_failure(lambda: module.send_message_frame(FakeTLSSocket(server_der), frame[:-1]), "E_MTLS_SEND_FRAME")
    negative_count += 1
    module.TRANSPORT_ACTIVATION_READY = False

status = module.status()
assert status["status"] == "OFFLINE_MTLS_FRAMING_AND_LIVE_SOCKET_ADAPTER_READY_ACTIVATION_GATE_CLOSED"
assert status["transport_activation_ready"] is False
assert status["socket_adapter_activation_ready"] is False
assert status["real_certificate_or_key_files_read"] == 0
assert status["network_accessed"] is False and status["listeners_started"] == status["external_hosts_contacted"] == 0
assert status["secret_frames_persisted"] == status["services_started"] == status["faults_injected"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

print("t22_a1_mtls_transport_check\tpass")
print("synthetic_memory_bio_mutual_tls_handshake_count\t1")
print("synthetic_tls_message_frame_roundtrip_count\t1")
print("synthetic_secret_frame_roundtrip_count\t1")
print("synthetic_log_bundle_roundtrip_count\t1")
print(f"directed_negative_test_count\t{negative_count}")
print("real_certificate_or_key_files_read\t0")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("external_hosts_contacted\t0")
print("secret_frames_persisted\t0")
print("production_admissible\tfalse")
