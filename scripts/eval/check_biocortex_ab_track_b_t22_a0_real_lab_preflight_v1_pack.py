"""Directed negative checks for the T22-A0 unsigned authorization proposal."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a0_real_lab_preflight_v1.py"
spec = importlib.util.spec_from_file_location("t22a0", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
base = json.loads(module.PROPOSAL.read_text())
module.validate_proposal(base)

mutations = (
    lambda x: x.update(state="AUTHORIZED"),
    lambda x: x.update(track_id="MANAGED_SPANNER_CLOUD_KMS"),
    lambda x: x["scope"].update(physical_host_count=3),
    lambda x: x["scope"].update(spend_limit_usd=1),
    lambda x: x["scope"].update(credential_access_before_signature=True),
    lambda x: x["scope"].update(preexisting_or_ambient_credential_access=True),
    lambda x: x["scope"].update(ephemeral_lab_bootstrap_material_after_signature=False),
    lambda x: x["scope"].update(ephemeral_lab_bootstrap_material_persisted=True),
    lambda x: x["scope"].update(provider_or_cloud_access=True),
    lambda x: x["scope"].update(production_or_customer_data=True),
    lambda x: x["scope"].update(host_global_network_mutation=True),
    lambda x: x["execution_contract"].update(contract_sha256="0" * 64),
    lambda x: x["allowed_faults_after_signature"].append("HOST_GLOBAL_TC"),
    lambda x: x["acceptance"].remove("ALL_SERVICES_STOPPED_AND_ARTIFACT_ROOT_SCOPED_AT_END"),
    lambda x: x["signing"].update(owner_public_key="forged"),
    lambda x: x["claims"].update(real_process_execution_authorized=True),
    lambda x: x["claims"].update(external_anti_rollback_evidence=True),
    lambda x: x.update(proposal_sha256="0" * 64),
)
for mutate in mutations:
    candidate = copy.deepcopy(base)
    mutate(candidate)
    try:
        module.validate_proposal(candidate)
    except (AssertionError, KeyError, TypeError):
        continue
    raise AssertionError("unsafe or drifted proposal admitted")

receipt = module.inspect()
assert receipt["status"] == "BLOCKED_OWNER_SIGNATURE_AND_PINNED_TOOLS_REQUIRED"
assert receipt["owner_public_key_bound"] is True
assert receipt["owner_signature_verified"] is False
assert receipt["credentials_accessed"] is False
assert receipt["network_accessed"] is False
assert receipt["services_started"] == 0
assert receipt["faults_injected"] == 0
print("t22_a0_real_lab_preflight_check\tpass")
print(f"directed_negative_test_count\t{len(mutations)}")
