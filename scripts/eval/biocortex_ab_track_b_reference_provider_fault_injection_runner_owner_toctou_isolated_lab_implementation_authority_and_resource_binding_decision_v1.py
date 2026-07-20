#!/usr/bin/env python3
"""Deterministic reviewer for the bounded T12 owner-TOCTOU authority decision."""

from __future__ import annotations
import copy, hashlib, json, sys
from pathlib import Path
from typing import Any, Mapping

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
OWNER_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
SEMANTIC_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
T11_MANIFEST_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_synthetic_exact_t10_receipt_track_validation_reference_time_decision_recheck_reference_time_and_maximum_clock_skew_seconds_verifier_isolated_lab_v1_pack_v0.json"
NEXT = "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_OWNER_TOCTOU_SYNTHETIC_EXACT_T11_RECEIPT_TRACK_VALIDATION_OWNER_EPOCH_AND_DECISION_RECHECK_OWNER_EPOCH_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
STATE = "AUTHORIZED_T12_OWNER_TOCTOU_ISOLATED_LAB_EXACT_UNIT"
DECISION = "AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_T12_OWNER_TOCTOU_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED"
PROFILE_FIELDS = ("t11_receipt_content_sha256","track_id","validation_owner_epoch","decision_recheck_owner_epoch")
REQUEST_FIELDS = ("validation_owner_epoch","decision_recheck_owner_epoch")
RECEIPTS = {"MANAGED_SPANNER_CLOUD_KMS":"63f0c26f10f42c923b55c4e651c001f7c38c42d9e25d7db772b4abbeadbe2ed8","SELF_HOSTED_ETCD_OPENBAO":"ce5af4f0ada753ed9a526909d071e5cb14959a6183f9169e67854d9ebcc4aee1"}

class ReviewError(ValueError): pass
def require(ok: bool, code: str) -> None:
    if not ok: raise ReviewError(code)
def load(rel: str) -> dict[str,Any]:
    p=ROOT/rel; require(p.is_file() and not p.is_symlink(),"E_PATH")
    return json.loads(p.read_text("utf-8"))
def canonical(v: Any)->bytes: return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha(v: bytes)->str: return hashlib.sha256(v).hexdigest()

def validate(owner: Mapping[str,Any], semantic: Mapping[str,Any], t11: Mapping[str,Any]) -> None:
    require(owner["decision"]==DECISION and owner["next_unit"]==NEXT,"E_DECISION")
    require(owner["owner_implementation_actor"]=={"actor_class":"PROJECT_OWNER","actor_id":"pallasting","semantic_owner_directive":"CONTINUE_NEXT_BOUNDED_UNIT_USING_AGENT_RECOMMENDED_ORDER"},"E_ACTOR")
    require(owner["predecessor"]["exact_release_commit"]=="a5c70f235cf4e1bffa26253e2618e0a0903c9a16" and owner["predecessor"]["t11_implemented"] is True,"E_PREDECESSOR")
    require(t11["authority"]["decision_integration_commit"]=="66f4754fd871169f50f345e5c023c94466f8ffd4" and t11["boundary"]["t11_clock_skew_implemented_after_integrated_full"] is True,"E_T11_MANIFEST")
    contract=owner["authorized_component_contract"]; topology=contract["input_topology"]; binding=contract["owner_epoch_binding"]
    require(topology["public_input_count"]==18 and topology["review_order"]==["MODE_PREOBSERVATION_GUARD","T11_CLOCK_SKEW_REVIEW_EXACTLY_ONCE","SEPARATE_OWNER_EPOCH_POLICY_REVIEW","DETACHED_OWNER_EPOCH_REQUEST_REVIEW_LAST","EXACT_SINGLE_PROFILE_MATCH","EPOCH_EQUALITY"],"E_TOPOLOGY")
    require(binding["policy_match_fields"]==list(PROFILE_FIELDS) and binding["request_fields"]==list(REQUEST_FIELDS),"E_FIELDS")
    require(binding["profile_order"]==["MANAGED_SPANNER_CLOUD_KMS","SELF_HOSTED_ETCD_OPENBAO"] and len(binding["profiles"])==2,"E_PROFILE_ORDER")
    for profile, epoch in zip(binding["profiles"],(41,73),strict=True):
        require(set(profile)==set(PROFILE_FIELDS),"E_PROFILE_FIELDS")
        require(profile["track_id"] in RECEIPTS and profile["t11_receipt_content_sha256"]==RECEIPTS[profile["track_id"]],"E_RECEIPT")
        require(type(profile["validation_owner_epoch"]) is int and type(profile["decision_recheck_owner_epoch"]) is int,"E_EPOCH_TYPE")
        require(0<=profile["validation_owner_epoch"]<=2**63-1 and profile["validation_owner_epoch"]==profile["decision_recheck_owner_epoch"]==epoch,"E_EPOCH_EQUALITY")
    auth=owner["implementation_authority"]; require(auth["current_state"]==STATE and auth["exact_next_unit_authorized"] is True and auth["non_transitive"] is True,"E_AUTHORITY")
    require({"ACCESS_AMBIENT_SYSTEM_OR_PROVIDER_OWNER_STATE","BIND_OR_CLAIM_REAL_OWNER_IDENTITY_OR_SIGNATURE","CLAIM_PRODUCTION_OWNER_WINDOW"}<=set(auth["forbidden_operations"]),"E_FORBIDDEN")
    require(owner["state_machine"]["decision_full_gate_consumes_new_authority"] is False and owner["state_machine"]["future_successor_integrated_full_consumes_authority"] is True,"E_STATE")
    require(owner["boundary"]["current_released_component_total"]==9 and owner["boundary"]["future_successor_component_total_after_exact_integrated_full_gate"]==10 and owner["boundary"]["t12_implemented"] is False and owner["boundary"]["runtime_authority"] is False and owner["boundary"]["provider_authority"] is False,"E_BOUNDARY")
    resources=owner["resource_binding"]
    require(resources["network"] is False and resources["effective_external_paid_spend_cap"]==0 and resources["max_parallel_workers"]==1 and resources["max_predecessor_review_calls"]==1 and resources["max_private_scratch_bytes"]==67108864 and resources["owner_epoch_policy_max_bytes"]==65536 and resources["owner_epoch_request_max_bytes"]==16384,"E_RESOURCES")
    threat={x["case_id"]:x for x in semantic["threat_cases"]}["T12"]
    require(threat["threat_class"]=="OWNER_TOCTOU" and threat["expected_reason_code"]=="E_PRODUCTION_OWNER_IDENTITY_OR_WINDOW_FAILED","E_SEMANTIC")

def evaluate()->str:
    owner,semantic,t11=map(load,(OWNER_REL,SEMANTIC_REL,T11_MANIFEST_REL)); validate(owner,semantic,t11)
    r={"schema":"agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.owner_toctou_authority_decision.receipt.v0","status":"T12_OWNER_TOCTOU_AUTHORITY_CANDIDATE_PENDING_INTEGRATED_FULL_GATE","decision":DECISION,"authorized_unit":NEXT,"authorization_candidate_state":STATE,"public_input_count":18,"profile_count":2,"request_field_count":2,"policy_match_dimension_count":4,"predecessor_t11_released":True,"t12_owner_toctou_implemented":False,"decision_full_gate_consumes_new_authority":False,"implementation_authority_single_use_consumed":False,"runtime_authority":False,"provider_authority":False,"production_controls_implemented":0,"real_evidence_items_present":0,"network":False,"content_sha256":"0"*64}
    w=dict(r);w.pop("content_sha256");r["content_sha256"]=sha(b"AB_TRACK_B_T12_OWNER_TOCTOU_AUTHORITY_V1\0"+canonical(w))
    return "".join(f"{k}\t{str(v).lower() if type(v) is bool else v}\n" for k,v in r.items())

if __name__=="__main__":
    try: sys.stdout.write(evaluate())
    except Exception as e: print(f"review_error\t{e}",file=sys.stderr); raise SystemExit(1)
