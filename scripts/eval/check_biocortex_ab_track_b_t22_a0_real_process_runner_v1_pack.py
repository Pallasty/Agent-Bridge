"""Offline, synthetic safety checks for the T22-A0 real-process runner."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a0_real_process_runner_v1.py"
spec = importlib.util.spec_from_file_location("t22runner", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

contract = module.load_contract()


def expect_contract_rejected(candidate: dict) -> None:
    try:
        module.validate_contract(candidate)
    except (module.SafeFailure, KeyError, TypeError, ValueError):
        return
    raise AssertionError("unsafe execution-contract mutation admitted")


mutations = []
for mutation in (
    lambda x: x.update(schema="other"),
    lambda x: x.update(execution_mode="PRODUCTION"),
    lambda x: x.update(track_id="MANAGED_SPANNER_CLOUD_KMS"),
    lambda x: x.update(artifact_root="/tmp"),
    lambda x: x["authorization"].update(verified_unexpired_owner_sshsig_required=False),
    lambda x: x["authorization"].update(one_run_per_authorization_content_sha256=False),
    lambda x: x["authorization"].update(spend_limit_usd=1),
    lambda x: x["network"].update(runtime_external_network_allowed=True),
    lambda x: x["network"].update(proxy_environment_inherited=True),
    lambda x: x["topology"]["etcd"][0].update(client_port=443),
    lambda x: x["topology"]["openbao"][0].update(api_port=23791),
    lambda x: x["ephemeral_lab_bootstrap_material"].update(held_in_process_memory_only=False),
    lambda x: x["ephemeral_lab_bootstrap_material"].update(log_receipt_or_artifact_persistence_allowed=True),
    lambda x: x["ephemeral_lab_bootstrap_material"].update(preexisting_ambient_or_external_credentials_allowed=True),
    lambda x: x["workload"].update(replay_consume_must_fail_required=False),
    lambda x: x["faults"].reverse(),
    lambda x: x["timeouts_seconds"].update(cluster_recovery=3600),
    lambda x: x["evidence"].update(secret_values_allowed=True),
    lambda x: x["claims"].update(three_failure_domain_evidence=True),
    lambda x: x.update(contract_sha256="0" * 64),
):
    candidate = copy.deepcopy(contract)
    mutation(candidate)
    expect_contract_rejected(candidate)
    mutations.append(candidate)


class ForbiddenCall:
    def __init__(self, name: str):
        self.name = name

    def __call__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError(f"{self.name} called before exact owner authorization")


original_opener = module.urllib.request.build_opener
original_popen = module.subprocess.Popen
original_socket = module.socket.socket
module.urllib.request.build_opener = ForbiddenCall("network opener")
module.subprocess.Popen = ForbiddenCall("process start")
module.socket.socket = ForbiddenCall("port bind")
try:
    status = module.status()
    assert status["status"] == "BLOCKED_EXACT_SIGNED_PAYLOAD_AND_PINNED_TOOLS_REQUIRED"
    assert status["owner_trust_anchor_present"] is True
    assert status["owner_trust_anchor_valid"] is True
    assert status["network_attempted"] is False
    assert status["processes_started"] == status["faults_injected"] == 0
    try:
        module.execute(Path("/missing-payload"), Path("/missing-signature"))
    except (AssertionError, FileNotFoundError):
        pass
    else:
        raise AssertionError("execution admitted without exact owner signature and pinned tools")
finally:
    module.urllib.request.build_opener = original_opener
    module.subprocess.Popen = original_popen
    module.socket.socket = original_socket


key = b"/agent-bridge/t22-a0/authority/synthetic"
seed = module.canonical({"generation": 0, "state": "AUTHORIZED_UNCLAIMED"})
consumed = module.canonical({"generation": 1, "state": "CONSUMED_FOR_EXACT_RUN"})
seed_request = module.etcd_seed_request(key, seed)
assert seed_request["compare"] == [{
    "target": "CREATE", "result": "EQUAL", "key": module.b64(key), "create_revision": "0",
}]
consume_request = module.etcd_consume_request(key, seed, consumed)
assert consume_request["compare"] == [{
    "target": "VALUE", "result": "EQUAL", "key": module.b64(key), "value": module.b64(seed),
}]
assert consume_request["success"] == [{"request_put": {"key": module.b64(key), "value": module.b64(consumed)}}]
value, revision = module.exact_range_value({
    "count": "1", "header": {"revision": "7"},
    "kvs": [{"key": module.b64(key), "value": module.b64(consumed)}],
}, key)
assert value == consumed and revision == "7"

try:
    module.validate_loopback_url("https://example.com:443/x", contract)
except module.SafeFailure:
    pass
else:
    raise AssertionError("external runtime URL admitted")
try:
    module.validate_loopback_url("http://127.0.0.1:9999/x", contract)
except module.SafeFailure:
    pass
else:
    raise AssertionError("unbound loopback port admitted")


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    events = module.EventLog(root / "events.jsonl")
    first = events.append("SYNTHETIC_FIRST", {"value": 1})
    second = events.append("SYNTHETIC_SECOND", {"value": 2})
    assert first["sequence"] == 0 and first["previous_event_sha256"] == "0" * 64
    assert second["sequence"] == 1 and second["previous_event_sha256"] == first["event_sha256"]
    for event in (first, second):
        claimed = event["event_sha256"]
        unsigned = dict(event); unsigned.pop("event_sha256")
        assert claimed == module.domain_digest(module.EVENT_DOMAIN, unsigned)
    verified_events = module.verify_event_log(root / "events.jsonl")
    assert verified_events == {"event_count": 2, "event_chain_head_sha256": second["event_sha256"]}

    receipt_path = root / "receipt.json"
    receipt = module.add_receipt_digest({"schema": "synthetic", "status": "PASS"})
    module.write_exclusive_json(receipt_path, receipt)
    assert module.verify_receipt_file(receipt_path) == receipt
    try:
        module.write_exclusive_json(receipt_path, receipt)
    except FileExistsError:
        pass
    else:
        raise AssertionError("exclusive durable receipt overwrite admitted")

    synthetic_runner = object.__new__(module.Runner)
    synthetic_runner.run_root = root
    synthetic_runner.unseal_key = "synthetic-unseal-key-never-real"
    synthetic_runner.root_token = "synthetic-root-token-never-real"
    (root / "safe.log").write_text("non-secret synthetic log")
    scan = module.Runner.scan_for_secret_values(synthetic_runner)
    assert scan["exact_secret_match_count"] == 0
    (root / "leak.log").write_text("prefix synthetic-root-token-never-real suffix")
    try:
        module.Runner.scan_for_secret_values(synthetic_runner)
    except module.SafeFailure as error:
        assert str(error) == "E_EPHEMERAL_BOOTSTRAP_MATERIAL_PERSISTED"
    else:
        raise AssertionError("exact ephemeral bootstrap-material leak admitted")

authorization = module.load_acquisition_module().load_authorization_module()
assert authorization.ANCHOR_PATH.is_file()
authorization.validate_anchor(
    json.loads(authorization.ANCHOR_PATH.read_text()),
    json.loads(authorization.PROPOSAL_PATH.read_text()),
)
print("t22_a0_real_process_runner_check\tpass")
print(f"directed_negative_test_count\t{len(mutations) + 7}")
print("network_attempted\tfalse")
print("processes_started\t0")
print("faults_injected\t0")
print("real_evidence_items_created\t0")
