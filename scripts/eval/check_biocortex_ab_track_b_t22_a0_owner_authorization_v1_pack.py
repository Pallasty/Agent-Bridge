"""Synthetic cryptographic and semantic checks; never installs an owner anchor."""
import copy
import importlib.util
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a0_owner_authorization_v1.py"
spec = importlib.util.spec_from_file_location("t22auth", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
proposal = json.loads(module.PROPOSAL_PATH.read_text())
assert module.status()["status"] == "BLOCKED_OWNER_TRUST_ANCHOR_REQUIRED"

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    key = root / "synthetic-test-key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "T22_SYNTHETIC_TEST_ONLY", "-f", str(key)], check=True)
    public_key = key.with_suffix(".pub").read_bytes()
    anchor = {
        "schema": "agent_bridge.biocortex.track_b.t22_a0.owner_trust_anchor.v1",
        "owner_id": "pallasting", "owner_role": "PROJECT_OWNER",
        "proposal_sha256": proposal["proposal_sha256"], "host": module.socket.gethostname(),
        "public_key": public_key.decode(),
        "public_key_sha256": module.hashlib.sha256(public_key).hexdigest(),
        "public_key_fingerprint": module.public_key_fingerprint(public_key),
    }
    now = datetime.now(timezone.utc)
    payload = module.build_payload(anchor, proposal, now, "1" * 40)
    payload_path = root / "payload.json"
    payload_path.write_bytes(module.canonical(payload) + b"\n")
    subprocess.run(["ssh-keygen", "-Y", "sign", "-q", "-f", str(key), "-n", module.NAMESPACE, str(payload_path)], check=True)
    module.verify_signature(payload_path, Path(str(payload_path) + ".sig"), public_key)
    mutations = (
        lambda x: x.update(decision="PRODUCTION"), lambda x: x.update(host="other"),
        lambda x: x.update(source_commit="bad"), lambda x: x.update(expires_at=x["issued_at"]),
        lambda x: x.update(execution_contract_sha256="0" * 64),
        lambda x: x.update(spend_limit_usd=1), lambda x: x.update(physical_host_count=3),
        lambda x: x.update(failure_domain_claim="THREE_HOSTS"), lambda x: x["allowed_after_signature"].append("CLOUD"),
        lambda x: x["forbidden"].remove("CLOUD_OR_PROVIDER_ACCESS"),
        lambda x: x.update(signature_namespace="other"), lambda x: x.update(content_sha256="0" * 64),
    )
    for mutate in mutations:
        candidate = copy.deepcopy(payload); mutate(candidate)
        try: module.validate_payload(candidate, anchor, proposal, now)
        except (AssertionError, KeyError, TypeError, ValueError): continue
        raise AssertionError("unsafe authorization mutation admitted")

assert not module.ANCHOR_PATH.exists()
print("t22_a0_owner_authorization_check\tpass")
print(f"directed_negative_test_count\t{len(mutations)}")
print("repository_owner_trust_anchor_present\tfalse")
