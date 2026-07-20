#!/usr/bin/env python3
"""Review the exact T13 replay isolated-lab implementation authority decision."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
from typing import Any, NoReturn

ROOT=Path(__file__).resolve().parents[2]
OWNER_REL="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
SEMANTIC_REL="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
T12_MANIFEST_REL="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_synthetic_exact_t11_receipt_track_validation_owner_epoch_and_decision_recheck_owner_epoch_verifier_isolated_lab_v1_pack_v0.json"
AUTHORIZED="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_REPLAY_SYNTHETIC_EXACT_T12_RECEIPT_TRACK_RESERVED_ISSUER_NONCE_SEQUENCE_AND_PACKET_IDENTITY_SUBMITTED_ISSUER_NONCE_SEQUENCE_AND_PACKET_IDENTITY_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
REQUEST=("submitted_issuer_nonce","submitted_sequence","submitted_packet_identity_sha256")
MATCH=("t12_receipt_content_sha256","track_id",*REQUEST)
PROFILE=("t12_receipt_content_sha256","track_id","reserved_issuer_nonce","reserved_sequence","reserved_packet_identity_sha256",*REQUEST)
ORDER=("MANAGED_SPANNER_CLOUD_KMS","SELF_HOSTED_ETCD_OPENBAO")
EXPECTED_RECEIPTS=("ddb58a2e4db7c74aedbf2504dcf38bde8419722429aeb3dba9cd61273ba3177d","d51f20f0c0b6ba03cb8fcc8b561c671d38b59fdc80a6fe35beafa0ae9d2f5eee")
DOMAIN="AB_TRACK_B_T13_REPLAY_AUTHORITY_DECISION_V1"

class ReviewError(ValueError): pass
def fail(code:str,detail:str)->NoReturn: raise ReviewError(f"{code}: {detail}")
def require(ok:bool,code:str,detail:str)->None:
    if not ok: fail(code,detail)
def path(rel:str)->Path:
    p=ROOT.joinpath(*rel.split('/')); r=p.resolve(strict=True); require(ROOT in r.parents and p.is_file() and not p.is_symlink(),"E_PATH",rel); return p
def load(rel:str)->dict[str,Any]:
    value=json.loads(path(rel).read_text()); require(type(value) is dict,"E_JSON_ROOT",rel); return value
def sha(rel:str)->str: return hashlib.sha256(path(rel).read_bytes()).hexdigest()
def lower_sha(value:Any)->bool: return type(value) is str and len(value)==64 and all(c in "0123456789abcdef" for c in value)

def validate(owner:dict[str,Any],semantic:dict[str,Any],manifest:dict[str,Any])->dict[str,Any]:
    require(owner["decision"]=="AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_T13_REPLAY_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED","E_DECISION","exact")
    require(owner["next_unit"]==AUTHORIZED,"E_UNIT","exact")
    actor=owner["owner_implementation_actor"]; require(actor=={"actor_class":"PROJECT_OWNER","actor_id":"pallasting","semantic_owner_directive":"CONTINUE_NEXT_SEMANTIC_UNIT_USING_AGENT_RECOMMENDED_ORDER"},"E_ACTOR","owner")
    pred=owner["predecessor"]; require(pred=={"exact_release_commit":"0fb3c55bf263317d6435d6ed2ed007baf0887719","implementation_authority_consumed":True,"t12_implemented":True},"E_PREDECESSOR","T12")
    contract=owner["authorized_component_contract"]; topology=contract["input_topology"]
    require(topology["public_input_count"]==20 and topology["review_order"]==["MODE_PREOBSERVATION_GUARD","T12_OWNER_TOCTOU_REVIEW_EXACTLY_ONCE","SEPARATE_REPLAY_POLICY_REVIEW","DETACHED_REPLAY_REQUEST_REVIEW_LAST","EXACT_SINGLE_PROFILE_MATCH","ANY_RESERVED_IDENTIFIER_EQUALITY_REJECTS"],"E_TOPOLOGY","20/order")
    replay=contract["replay_binding"]
    require(tuple(replay["request_fields"])==REQUEST and tuple(replay["policy_match_fields"])==MATCH and tuple(replay["profile_fields"])==PROFILE,"E_FIELDS","closed")
    require(tuple(replay["profile_order"])==ORDER and len(replay["profiles"])==2,"E_PROFILES","ordered two")
    for i,(profile,track,receipt) in enumerate(zip(replay["profiles"],ORDER,EXPECTED_RECEIPTS,strict=True)):
        require(type(profile) is dict and set(profile)==set(PROFILE),"E_PROFILE_FIELDS",str(i))
        require(profile["track_id"]==track and profile["t12_receipt_content_sha256"]==receipt,"E_PROFILE_BINDING",str(i))
        require(lower_sha(profile["reserved_packet_identity_sha256"]) and lower_sha(profile["submitted_packet_identity_sha256"]),"E_PACKET_HASH",str(i))
        require(type(profile["reserved_sequence"]) is int and type(profile["submitted_sequence"]) is int and 0<=profile["reserved_sequence"]<=2**63-1 and 0<=profile["submitted_sequence"]<=2**63-1,"E_SEQUENCE",str(i))
        require(type(profile["reserved_issuer_nonce"]) is str and type(profile["submitted_issuer_nonce"]) is str and profile["reserved_issuer_nonce"] and profile["submitted_issuer_nonce"],"E_NONCE",str(i))
        require(profile["reserved_issuer_nonce"]!=profile["submitted_issuer_nonce"] and profile["reserved_sequence"]!=profile["submitted_sequence"] and profile["reserved_packet_identity_sha256"]!=profile["submitted_packet_identity_sha256"],"E_FRESH_TRIPLE",str(i))
    authority=owner["implementation_authority"]
    require(authority["current_state"]=="AUTHORIZED_T13_REPLAY_ISOLATED_LAB_EXACT_UNIT" and authority["exact_next_unit_authorized"] is True and authority["non_transitive"] is True and authority["single_successor_intent"] is True,"E_AUTHORITY","state")
    require(authority["forbidden_operations"]==["ACCESS_OR_MUTATE_DURABLE_REPLAY_STATE","CLAIM_ATOMIC_NONCE_OR_SEQUENCE_RESERVATION","BIND_OR_CLAIM_REAL_ISSUER_AUTHENTICATION","PERFORM_NETWORK_PROVIDER_RUNTIME_OR_PRODUCTION_ACTION"],"E_FORBIDDEN","closed")
    boundary=owner["boundary"]
    require(boundary=={"current_released_component_total":10,"future_successor_component_total_after_exact_integrated_full_gate":11,"production_ingestion_controls_implemented":0,"provider_authority":False,"runtime_authority":False,"t12_implemented":True,"t13_implemented":False,"t14_authorized":False},"E_BOUNDARY","truth")
    resource=owner["resource_binding"]
    require(resource=={"effective_external_paid_spend_cap":0,"max_parallel_workers":1,"max_predecessor_review_calls":1,"max_private_scratch_bytes":67108864,"network":False,"replay_policy_max_bytes":65536,"replay_request_max_bytes":16384},"E_RESOURCE","bounded")
    require(owner["state_machine"]=={"decision_full_gate_consumes_new_authority":False,"future_successor_integrated_full_consumes_authority":True},"E_STATE_MACHINE","activation")
    require(manifest["boundary"]["t12_owner_toctou_implemented_after_integrated_full"] is True and manifest["boundary"]["component_total_after_integrated_full"]==10 and manifest["authority"]["implementation_consumes_authority_after_integrated_full"] is True,"E_T12_MANIFEST","released")
    t13=next(x for x in semantic["threat_cases"] if x["case_id"]=="T13")
    require(t13=={"case_id":"T13","expected_disposition":"REJECTED_FAIL_CLOSED","expected_reason_code":"E_PRODUCTION_REPLAY_REJECTED","mutation":"Previously reserved issuer nonce, sequence, or packet identity is submitted again","threat_class":"REPLAY"},"E_T13_SEMANTIC","exact")
    receipt={"schema":"agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.replay_authority_decision.receipt.v0","status":"APPROVE_T13_REPLAY_AUTHORITY_DECISION","authorized_unit":AUTHORIZED,"public_input_count":20,"profile_count":2,"request_field_count":3,"profile_field_count":8,"policy_match_dimension_count":5,"t12_implemented":True,"t13_implemented":False,"authority_consumed":False,"future_component_total":11,"runtime_authority":False,"provider_authority":False,"network":False,"max_parallel_workers":1,"owner_raw_sha256":sha(OWNER_REL),"semantic_raw_sha256":sha(SEMANTIC_REL),"t12_manifest_raw_sha256":sha(T12_MANIFEST_REL),"content_sha256":"0"*64}
    copied=dict(receipt); del copied["content_sha256"]; receipt["content_sha256"]=hashlib.sha256(DOMAIN.encode()+b"\0"+json.dumps(copied,sort_keys=True,separators=(',',':')).encode()).hexdigest(); return receipt

def main()->int:
    try:
        receipt=validate(load(OWNER_REL),load(SEMANTIC_REL),load(T12_MANIFEST_REL))
        for k,v in receipt.items(): print(f"{k}\t{str(v).lower() if type(v) is bool else v}")
        return 0
    except Exception as error: print(f"review_error\t{error}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
