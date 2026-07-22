"""Offline, synthetic safety checks for the T22-A0 real-process runner."""
from __future__ import annotations

import copy
import io
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
    expected_state = (
        "BLOCKED_EXACT_SIGNED_PAYLOAD_AND_SOURCE_BOUND_TOOL_RECEIPT_REQUIRED"
        if status["pinned_tools_present"]
        else "BLOCKED_EXACT_SIGNED_PAYLOAD_AND_PINNED_TOOLS_REQUIRED"
    )
    assert status["status"] == expected_state
    assert status["owner_trust_anchor_present"] is True
    assert status["owner_trust_anchor_valid"] is True
    assert isinstance(status["pinned_tools_present"], bool)
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

failure_range = {
    "header": {"revision": "8"}, "count": "1",
    "kvs": [{"key": module.b64(key), "value": module.b64(consumed)}],
}
for rejected in (
    {"responses": [{"response_range": failure_range}]},
    {"succeeded": False, "responses": [{"response_range": failure_range}]},
):
    assert module.exact_rejected_txn_range(rejected, key, consumed, "7") == "8"
wrong_value_range = copy.deepcopy(failure_range)
wrong_value_range["kvs"][0]["value"] = module.b64(seed)
old_revision_range = copy.deepcopy(failure_range)
old_revision_range["header"]["revision"] = "6"
for unsafe in (
    {"succeeded": True, "responses": [{"response_range": failure_range}]},
    {"responses": []},
    {"responses": [{"response_put": {"header": {"revision": "8"}}}]},
    {"responses": [{"response_range": wrong_value_range}]},
    {"responses": [{"response_range": old_revision_range}]},
):
    try:
        module.exact_rejected_txn_range(unsafe, key, consumed, "7")
    except module.SafeFailure:
        continue
    raise AssertionError("replay transaction without exact failure-range proof admitted")

sync_unseal = {"type": "shamir", "initialized": True, "sealed": False, "t": 1, "n": 1}
async_unseal = {"type": "shamir", "initialized": False, "sealed": True, "t": 1, "n": 1}
assert module.exact_unseal_submission(sync_unseal, False) == sync_unseal
assert module.exact_unseal_submission(async_unseal, True) == async_unseal
assert module.exact_unsealed_health(sync_unseal) == sync_unseal
assert module.exact_unsealed_health(async_unseal) is None
for unsafe, asynchronous_allowed in (
    ({**sync_unseal, "type": "recovery"}, False),
    ({**sync_unseal, "sealed": "false"}, False),
    ({**sync_unseal, "t": 2}, False),
    ({**sync_unseal, "n": True}, False),
    (async_unseal, False),
):
    try:
        module.exact_unseal_submission(unsafe, asynchronous_allowed)
    except module.SafeFailure:
        continue
    raise AssertionError("unsafe OpenBao unseal response admitted")

bao_nodes = contract["topology"]["openbao"]
voting_servers = [
    {
        "address": f'127.0.0.1:{node["cluster_port"]}',
        "leader": index == 0,
        "node_id": node["node"],
        "protocol_version": "3",
        "voter": True,
    }
    for index, node in enumerate(bao_nodes)
]
voting_response = {"data": {"config": {"index": 42, "servers": voting_servers}}}
assert module.exact_three_voter_configuration(voting_response, bao_nodes, "bao-1") == voting_servers
unsafe_configurations = []
for mutation in (
    lambda x: x["data"]["config"]["servers"][1].update(voter=False),
    lambda x: x["data"]["config"]["servers"][0].update(leader=False),
    lambda x: x["data"]["config"]["servers"][1].update(leader=True),
    lambda x: x["data"]["config"]["servers"][2].update(address="127.0.0.1:9999"),
    lambda x: x["data"]["config"]["servers"][2].update(node_id="bao-2"),
):
    candidate = copy.deepcopy(voting_response)
    mutation(candidate)
    assert module.exact_three_voter_configuration(candidate, bao_nodes, "bao-1") is None
    unsafe_configurations.append(candidate)

assert module.classify_loopback_http_error(TimeoutError()) == "E_LOOPBACK_HTTP_TIMEOUT"
assert module.classify_loopback_http_error(
    module.urllib.error.URLError(TimeoutError())
) == "E_LOOPBACK_HTTP_TIMEOUT"
status_error = module.urllib.error.HTTPError(
    "http://127.0.0.1:28201/v1/sys/init", 500, "synthetic", {}, io.BytesIO(b"not inspected")
)
assert module.classify_loopback_http_error(status_error) == "E_LOOPBACK_HTTP_STATUS_500"
status_error.close()
assert module.classify_loopback_http_error(ConnectionError()) == "E_LOOPBACK_HTTP_TRANSPORT"

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
    assert events.event_types == {"SYNTHETIC_FIRST", "SYNTHETIC_SECOND"}
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

    synthetic_runner.config = root
    synthetic_runner.data = root / "data"
    synthetic_runner.data.mkdir()
    synthetic_node = {"node": "bao-synthetic", "api_port": 28201, "cluster_port": 28301}
    config_path = module.Runner.write_bao_config(synthetic_runner, synthetic_node)
    config_text = config_path.read_text()
    assert "performance_multiplier = 1" in config_text
    assert "disable_mlock" not in config_text

authorization = module.load_acquisition_module().load_authorization_module()
assert authorization.ANCHOR_PATH.is_file()
authorization.validate_anchor(
    json.loads(authorization.ANCHOR_PATH.read_text()),
    json.loads(authorization.PROPOSAL_PATH.read_text()),
)
print("t22_a0_real_process_runner_check\tpass")
print(f"directed_negative_test_count\t{len(mutations) + len(unsafe_configurations) + 27}")
print("network_attempted\tfalse")
print("processes_started\t0")
print("faults_injected\t0")
print("real_evidence_items_created\t0")
