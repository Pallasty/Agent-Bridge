"""Generate and verify the exact, short-lived T22-A0 owner authorization."""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROPOSAL_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a0-real-lab-owner-authorization-proposal-v1.json"
ANCHOR_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a0-owner-trust-anchor-v1.json"
NAMESPACE = "agent-bridge-t22-a0-owner-v1"
PAYLOAD_DOMAIN = b"AB_TRACK_B_T22_A0_EXACT_OWNER_AUTHORIZATION_V1\0"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(PAYLOAD_DOMAIN + canonical(value)).hexdigest()


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo == timezone.utc
    return parsed


def public_key_fingerprint(public_key: bytes) -> str:
    assert public_key.endswith(b"\n") and public_key.count(b"\n") == 1
    assert public_key.startswith(b"ssh-ed25519 ")
    with tempfile.NamedTemporaryFile() as handle:
        handle.write(public_key)
        handle.flush()
        result = subprocess.run(
            ["ssh-keygen", "-lf", handle.name, "-E", "sha256"],
            check=True, capture_output=True, text=True,
        )
    fields = result.stdout.split()
    assert len(fields) >= 2 and fields[1].startswith("SHA256:")
    return fields[1]


def validate_anchor(anchor: dict, proposal: dict) -> bytes:
    assert anchor["schema"] == "agent_bridge.biocortex.track_b.t22_a0.owner_trust_anchor.v1"
    assert anchor["owner_id"] == "pallasting" and anchor["owner_role"] == "PROJECT_OWNER"
    assert anchor["proposal_sha256"] == proposal["proposal_sha256"]
    assert anchor["host"] == socket.gethostname()
    public_key = anchor["public_key"].encode()
    assert hashlib.sha256(public_key).hexdigest() == anchor["public_key_sha256"]
    assert public_key_fingerprint(public_key) == anchor["public_key_fingerprint"]
    return public_key


def build_payload(anchor: dict, proposal: dict, issued_at: datetime, source_commit: str) -> dict:
    assert issued_at.tzinfo == timezone.utc
    validate_anchor(anchor, proposal)
    body = {
        "schema": "agent_bridge.biocortex.track_b.t22_a0.exact_owner_authorization.v1",
        "decision": "AUTHORIZE_T22_A0_SINGLE_HOST_REAL_PROCESS_PILOT_ONLY",
        "owner_id": "pallasting",
        "owner_role": "PROJECT_OWNER",
        "track_id": "SELF_HOSTED_ETCD_OPENBAO",
        "host": socket.gethostname(),
        "source_commit": source_commit,
        "proposal_sha256": proposal["proposal_sha256"],
        "owner_public_key_sha256": anchor["public_key_sha256"],
        "owner_public_key_fingerprint": anchor["public_key_fingerprint"],
        "issued_at": issued_at.isoformat().replace("+00:00", "Z"),
        "not_before": issued_at.isoformat().replace("+00:00", "Z"),
        "expires_at": (issued_at + timedelta(seconds=14400)).isoformat().replace("+00:00", "Z"),
        "maximum_runtime_seconds": 14400,
        "spend_limit_usd": 0,
        "physical_host_count": 1,
        "failure_domain_claim": "PROCESS_ONLY_SINGLE_PHYSICAL_HOST",
        "allowed_after_signature": [
            "HASH_PINNED_PUBLIC_RELEASE_DOWNLOAD",
            "OWNED_PROCESS_START_STOP_KILL_RESTART",
            "LOOPBACK_TOXIPROXY_FAULT",
            "OWNED_LAB_SNAPSHOT_ROLLBACK",
            "NONSECRET_REAL_EVIDENCE_WRITE_UNDER_EXACT_ARTIFACT_ROOT",
        ],
        "forbidden": [
            "CREDENTIAL_DISCOVERY_OR_ACCESS",
            "CLOUD_OR_PROVIDER_ACCESS",
            "NONZERO_SPEND",
            "PRODUCTION_OR_CUSTOMER_DATA",
            "HOST_GLOBAL_IPTABLES_OR_TC_MUTATION",
            "THREE_FAILURE_DOMAIN_EXTERNAL_ANTI_ROLLBACK_OR_PRODUCTION_CLAIM",
        ],
        "artifact_root": proposal["scope"]["artifact_root"],
        "signature_namespace": NAMESPACE,
        "content_sha256": "0" * 64,
    }
    unsigned = dict(body)
    unsigned.pop("content_sha256")
    body["content_sha256"] = digest(unsigned)
    validate_payload(body, anchor, proposal, issued_at)
    return body


def validate_payload(payload: dict, anchor: dict, proposal: dict, now: datetime) -> bytes:
    public_key = validate_anchor(anchor, proposal)
    assert payload["schema"] == "agent_bridge.biocortex.track_b.t22_a0.exact_owner_authorization.v1"
    assert payload["decision"] == "AUTHORIZE_T22_A0_SINGLE_HOST_REAL_PROCESS_PILOT_ONLY"
    assert payload["owner_id"] == "pallasting" and payload["owner_role"] == "PROJECT_OWNER"
    assert payload["track_id"] == "SELF_HOSTED_ETCD_OPENBAO"
    assert payload["host"] == anchor["host"] == socket.gethostname()
    assert len(payload["source_commit"]) == 40 and all(c in "0123456789abcdef" for c in payload["source_commit"])
    assert payload["proposal_sha256"] == proposal["proposal_sha256"]
    assert payload["owner_public_key_sha256"] == anchor["public_key_sha256"]
    assert payload["owner_public_key_fingerprint"] == anchor["public_key_fingerprint"]
    issued, not_before, expires = map(parse_time, (payload["issued_at"], payload["not_before"], payload["expires_at"]))
    assert issued == not_before and expires - issued == timedelta(seconds=14400)
    assert not_before <= now < expires
    assert payload["maximum_runtime_seconds"] == 14400 and payload["spend_limit_usd"] == 0
    assert payload["physical_host_count"] == 1
    assert payload["failure_domain_claim"] == "PROCESS_ONLY_SINGLE_PHYSICAL_HOST"
    assert payload["allowed_after_signature"] == [
        "HASH_PINNED_PUBLIC_RELEASE_DOWNLOAD", "OWNED_PROCESS_START_STOP_KILL_RESTART",
        "LOOPBACK_TOXIPROXY_FAULT", "OWNED_LAB_SNAPSHOT_ROLLBACK",
        "NONSECRET_REAL_EVIDENCE_WRITE_UNDER_EXACT_ARTIFACT_ROOT",
    ]
    assert payload["forbidden"] == [
        "CREDENTIAL_DISCOVERY_OR_ACCESS", "CLOUD_OR_PROVIDER_ACCESS", "NONZERO_SPEND",
        "PRODUCTION_OR_CUSTOMER_DATA", "HOST_GLOBAL_IPTABLES_OR_TC_MUTATION",
        "THREE_FAILURE_DOMAIN_EXTERNAL_ANTI_ROLLBACK_OR_PRODUCTION_CLAIM",
    ]
    assert payload["artifact_root"] == proposal["scope"]["artifact_root"]
    assert payload["signature_namespace"] == NAMESPACE
    unsigned = dict(payload)
    claimed = unsigned.pop("content_sha256")
    assert claimed == digest(unsigned)
    return public_key


def verify_signature(payload_path: Path, signature_path: Path, public_key: bytes) -> None:
    with tempfile.NamedTemporaryFile(mode="wb") as allowed:
        allowed.write(b"pallasting " + public_key)
        allowed.flush()
        result = subprocess.run(
            ["ssh-keygen", "-Y", "verify", "-f", allowed.name, "-I", "pallasting",
             "-n", NAMESPACE, "-s", str(signature_path)],
            input=payload_path.read_bytes(), capture_output=True,
        )
    assert result.returncode == 0, result.stderr.decode(errors="replace")


def status() -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a0.owner_authorization_status.v0",
        "status": "BLOCKED_OWNER_TRUST_ANCHOR_REQUIRED" if not ANCHOR_PATH.is_file() else "READY_TO_GENERATE_EXACT_PAYLOAD",
        "owner_trust_anchor_present": ANCHOR_PATH.is_file(),
        "owner_signature_verified": False,
        "real_process_execution_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    generate = sub.add_parser("generate")
    generate.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--payload", type=Path, required=True)
    verify.add_argument("--signature", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
        return
    proposal = json.loads(PROPOSAL_PATH.read_text())
    anchor = json.loads(ANCHOR_PATH.read_text())
    now = datetime.now(timezone.utc)
    if args.command == "generate":
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
        payload = build_payload(anchor, proposal, now, commit)
        args.output.write_bytes(canonical(payload) + b"\n")
        print(json.dumps({"status": "EXACT_PAYLOAD_GENERATED_AWAITING_OWNER_SIGNATURE", "payload": str(args.output), "content_sha256": payload["content_sha256"]}, sort_keys=True, separators=(",", ":")))
        return
    payload = json.loads(args.payload.read_text())
    public_key = validate_payload(payload, anchor, proposal, now)
    verify_signature(args.payload, args.signature, public_key)
    print(json.dumps({"status": "AUTHORIZED_T22_A0_EXACT_OWNER_SIGNATURE_VERIFIED", "content_sha256": payload["content_sha256"], "expires_at": payload["expires_at"], "real_process_execution_authorized": True, "production_admissible": False}, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
