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


def plan(ca: Path, domain_certificate: Path, domain_key: Path, coordinator_certificate: Path | None = None, coordinator_key: Path | None = None) -> dict:
    coordinator = None
    if coordinator_certificate is not None and coordinator_key is not None:
        coordinator = {
            "certificate_path": str(coordinator_certificate),
            "private_key_path": str(coordinator_key),
            "certificate_sha256": sha_file(coordinator_certificate),
            "spki_sha256": hashlib.sha256(b"synthetic-coordinator-spki").hexdigest(),
            "private_key_spki_sha256": hashlib.sha256(b"synthetic-coordinator-spki").hexdigest(),
        }
    return {
        "domain_id": "domain-1",
        "network": {"overlay_ip": "100.64.50.1"},
        "credentials": {
            "ca_certificate_path": str(ca), "ca_certificate_sha256": sha_file(ca),
            "domain_certificate_path": str(domain_certificate),
            "domain_certificate_sha256": sha_file(domain_certificate),
            "domain_spki_sha256": hashlib.sha256(b"synthetic-domain-spki").hexdigest(),
            "domain_private_key_spki_sha256": hashlib.sha256(b"synthetic-domain-spki").hexdigest(),
            "domain_private_key_path": str(domain_key),
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
    wrong_ca_key, wrong_ca_certificate = create_ca(root, "wrong-ca")
    wrong_client_key, wrong_client_certificate = create_leaf(root, wrong_ca_key, wrong_ca_certificate, "wrong-client", "clientAuth", None)
    for path in root.iterdir():
        if path.is_file():
            path.chmod(0o600)

    server_plan = plan(ca_certificate, server_certificate, server_key)
    client_plan = plan(ca_certificate, server_certificate, server_key, client_certificate, client_key)
    expect_failure(lambda: module.build_server_context(server_plan), "E_MTLS_TRANSPORT_ACTIVATION_NOT_READY")
    negative_count += 1
    module.TRANSPORT_ACTIVATION_READY = True
    server_context = module.build_server_context(server_plan)
    client_context = module.build_client_context(client_plan)
    client_tls, server_tls, client_out, server_in = memory_handshake(client_context, server_context, "100.64.50.1")
    module.verify_peer_certificate_sha256(client_tls, certificate_der_sha256(server_certificate))
    module.verify_peer_certificate_sha256(server_tls, certificate_der_sha256(client_certificate))
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
    module.TRANSPORT_ACTIVATION_READY = False

status = module.status()
assert status["status"] == "OFFLINE_MTLS_FRAMING_READY_LIVE_SOCKET_ADAPTER_AND_ACTIVATION_ABSENT"
assert status["transport_activation_ready"] is False
assert status["real_certificate_or_key_files_read"] == 0
assert status["network_accessed"] is False and status["listeners_started"] == status["external_hosts_contacted"] == 0
assert status["secret_frames_persisted"] == status["services_started"] == status["faults_injected"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

print("t22_a1_mtls_transport_check\tpass")
print("synthetic_memory_bio_mutual_tls_handshake_count\t1")
print("synthetic_tls_message_frame_roundtrip_count\t1")
print("synthetic_secret_frame_roundtrip_count\t1")
print(f"directed_negative_test_count\t{negative_count}")
print("real_certificate_or_key_files_read\t0")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("external_hosts_contacted\t0")
print("secret_frames_persisted\t0")
print("production_admissible\tfalse")
