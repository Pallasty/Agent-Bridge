#!/usr/bin/env python3
"""Pure public isolated-lab T14 concurrent-replay verifier."""
from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from typing import Any,Mapping,NoReturn
import biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_synthetic_exact_t12_receipt_track_reserved_issuer_nonce_sequence_and_packet_identity_submitted_issuer_nonce_sequence_and_packet_identity_verifier_isolated_lab_v1 as predecessor

SYNTHETIC_KAT_MODE="SYNTHETIC_KAT";PRODUCTION_MODE="PRODUCTION"
POLICY_SCHEMA="agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.concurrent_replay_synthetic_policy_isolated_lab_kat.v1"
RECEIPT_SCHEMA="agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.concurrent_replay_synthetic_exact_t13_receipt_track_reservation_key_contender_a_and_b_observed_generation_and_cas_result_verifier_isolated_lab_v1.receipt.v0"
STATUS="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_CONCURRENT_REPLAY_SYNTHETIC_EXACT_T13_RECEIPT_TRACK_RESERVATION_KEY_CONTENDER_A_AND_B_OBSERVED_GENERATION_AND_CAS_RESULT_VERIFIED_ISOLATED_LAB_COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
AUTHORIZED_UNIT="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_CONCURRENT_REPLAY_SYNTHETIC_EXACT_T13_RECEIPT_TRACK_RESERVATION_KEY_CONTENDER_A_AND_B_OBSERVED_GENERATION_AND_CAS_RESULT_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
COMPONENT_STATE="BOUND_SYNTHETIC_SAME_GENERATION_XOR_CAS_TO_EXACT_T13_RECEIPT_CHAIN_ONLY"
RECEIPT_DOMAIN="AB_TRACK_B_T14_CONCURRENT_REPLAY_ISOLATED_LAB_KAT_RECEIPT_V1";TARGET_PRODUCTION_FAILURE_CODE="E_PRODUCTION_REPLAY_REJECTED"
DEFAULT_DISPOSITION="REJECTED_FAIL_CLOSED";MATCHING_PROFILE="EXACT_ALL_FIELDS_EQUAL";MAX_POLICY_BYTES=65536;MAX_REQUEST_BYTES=16384;MAX_INT=2**63-1
REQUEST_FIELDS=("reservation_key_sha256","contender_a_observed_generation","contender_b_observed_generation","contender_a_cas_result","contender_b_cas_result")
MATCH_FIELDS=("t13_receipt_content_sha256","track_id",*REQUEST_FIELDS);PROFILE_FIELDS=MATCH_FIELDS
POLICY_KEYS=("default_disposition","matching_profile","profiles","reject_on_multiple_matches","reject_on_zero_matches","schema","schema_version")
@dataclass(frozen=True)
class ConcurrentReplayProfile:
 t13_receipt_content_sha256:str;track_id:str;reservation_key_sha256:str;contender_a_observed_generation:int;contender_b_observed_generation:int;contender_a_cas_result:bool;contender_b_cas_result:bool
PROFILES=(ConcurrentReplayProfile("5f42f7ee62ddfb470113726fd1ced0e0cbaa0be2162f8665027692690626154a","MANAGED_SPANNER_CLOUD_KMS","a37cbdb5fbd121c64113679585142ec3d177765b88062d1d45c445e43a01febc",101,101,True,False),ConcurrentReplayProfile("ecc9d3f5ca738f3bfc199c35dde7f178657865aee2e05f3561a0ee11c39848ae","SELF_HOSTED_ETCD_OPENBAO","c696b8de01706eb5c9d93348fcb32ce6316a14b6dc8f6060bfd5db16102d4ce6",202,202,False,True))
class ConcurrentReplayReviewError(ValueError):
 def __init__(self,code:str,detail:str,*,detail_code:str|None=None):super().__init__(f"{code}: {detail}");self.code=code;self.detail=detail;self.detail_code=detail_code
def fail(c:str,d:str)->NoReturn:raise ConcurrentReplayReviewError(c,d)
def require(x:bool,c:str,d:str)->None:
 if not x:fail(c,d)
def reject_mode(m:str)->None:
 if type(m)is not str:fail("E_CONCURRENT_REPLAY_MODE_UNKNOWN","exact string")
 if m==PRODUCTION_MODE:fail("E_CONCURRENT_REPLAY_PRODUCTION_MODE_NOT_AUTHORIZED","production concurrency unavailable")
 if m!=SYNTHETIC_KAT_MODE:fail("E_CONCURRENT_REPLAY_MODE_UNKNOWN","only SYNTHETIC_KAT")
def pairs(items:list[tuple[str,Any]])->dict[str,Any]:
 out={}
 for k,v in items:require(type(k)is str and k not in out,"E_JSON_DUPLICATE_KEY","duplicate");out[k]=v
 return out
def no_num(v:str)->NoReturn:fail("E_JSON_NON_INTEGER_NUMBER",v)
def parse_int(v:str)->int:
 x=int(v);require(-(2**63)<=x<=MAX_INT,"E_JSON_INT_RANGE",v);return x
def canonical(v:Mapping[str,Any])->bytes:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def decode(raw:bytes,limit:int,label:str)->dict[str,Any]:
 require(type(raw)is bytes,f"E_{label}_TYPE","bytes");require(0<len(raw)<=limit,f"E_{label}_SIZE","bound")
 try:text=raw.decode('utf-8','strict');d=json.JSONDecoder(object_pairs_hook=pairs,parse_int=parse_int,parse_float=no_num,parse_constant=no_num,strict=True);v,end=d.raw_decode(text)
 except ConcurrentReplayReviewError:raise
 except Exception as e:fail(f"E_{label}_JSON",str(e))
 require(end==len(text)and type(v)is dict,f"E_{label}_ROOT_OR_TRAILING","closed");require(canonical(v)==raw,f"E_{label}_NONCANONICAL","canonical");return v
def exact(v:Mapping[str,Any],f:tuple[str,...],c:str)->None:require(type(v)is dict and set(v)==set(f),c,"fields")
def sha(v:Any)->bool:return type(v)is str and len(v)==64 and all(c in '0123456789abcdef'for c in v)
def generation(v:Any,f:str)->int:require(type(v)is int and 0<=v<=MAX_INT,f"E_{f.upper()}","generation");return v
def pd(p:ConcurrentReplayProfile)->dict[str,Any]:return {f:getattr(p,f)for f in PROFILE_FIELDS}
def known_answer_concurrent_replay_policy()->dict[str,Any]:return {"default_disposition":DEFAULT_DISPOSITION,"matching_profile":MATCHING_PROFILE,"profiles":[pd(p)for p in PROFILES],"reject_on_multiple_matches":True,"reject_on_zero_matches":True,"schema":POLICY_SCHEMA,"schema_version":1}
def known_answer_concurrent_replay_policy_bytes()->bytes:return canonical(known_answer_concurrent_replay_policy())
def known_answer_concurrent_replay_request(track_id:str)->dict[str,Any]:
 for p in PROFILES:
  if p.track_id==track_id:return {f:getattr(p,f)for f in REQUEST_FIELDS}
 fail("E_CONCURRENT_REPLAY_TRACK_UNKNOWN",track_id)
def known_answer_concurrent_replay_request_bytes(track_id:str)->bytes:return canonical(known_answer_concurrent_replay_request(track_id))
def validate_policy(v:Mapping[str,Any])->tuple[Mapping[str,Any],...]:
 exact(v,POLICY_KEYS,"E_CONCURRENT_REPLAY_POLICY_FIELDS");require(v["schema"]==POLICY_SCHEMA and type(v["schema"])is str,"E_CONCURRENT_REPLAY_POLICY_SCHEMA","schema");require(type(v["schema_version"])is int and v["schema_version"]==1,"E_CONCURRENT_REPLAY_POLICY_VERSION","version");require(v["default_disposition"]==DEFAULT_DISPOSITION and v["matching_profile"]==MATCHING_PROFILE,"E_CONCURRENT_REPLAY_POLICY_MATCHING","matching");require(v["reject_on_zero_matches"]is True and v["reject_on_multiple_matches"]is True,"E_CONCURRENT_REPLAY_POLICY_AMBIGUITY","deny")
 ps=v["profiles"];require(type(ps)is list and len(ps)==2,"E_CONCURRENT_REPLAY_POLICY_PROFILES","two")
 for c,f in zip(ps,PROFILES,strict=True):
  exact(c,PROFILE_FIELDS,"E_CONCURRENT_REPLAY_PROFILE_FIELDS");require(sha(c["t13_receipt_content_sha256"])and sha(c["reservation_key_sha256"]),"E_CONCURRENT_REPLAY_SHA","hash");generation(c["contender_a_observed_generation"],"contender_a_observed_generation");generation(c["contender_b_observed_generation"],"contender_b_observed_generation");require(type(c["contender_a_cas_result"])is bool and type(c["contender_b_cas_result"])is bool,"E_CONCURRENT_REPLAY_CAS_TYPE","bool");require(c==pd(f),"E_CONCURRENT_REPLAY_PROFILE_EXACT","frozen")
 return tuple(ps)
def validate_request(v:Mapping[str,Any])->Mapping[str,Any]:
 exact(v,REQUEST_FIELDS,"E_CONCURRENT_REPLAY_REQUEST_FIELDS");require(sha(v["reservation_key_sha256"]),"E_RESERVATION_KEY_SHA256","hash");generation(v["contender_a_observed_generation"],"contender_a_observed_generation");generation(v["contender_b_observed_generation"],"contender_b_observed_generation");require(type(v["contender_a_cas_result"])is bool and type(v["contender_b_cas_result"])is bool,"E_CONCURRENT_REPLAY_CAS_TYPE","bool");return v
def review_concurrent_replay(frame:bytes,detached_authentication_bundle:bytes,separately_injected_synthetic_trust_policy:bytes,separately_injected_synthetic_signer_authorization_policy:bytes,detached_authorization_request:bytes,separately_injected_synthetic_track_profile_binding_policy:bytes,detached_track_profile_binding_request:bytes,separately_injected_synthetic_end_to_end_subject_binding_policy:bytes,detached_end_to_end_subject_binding_request:bytes,separately_injected_synthetic_content_identity_and_quarantine_custody_policy:bytes,detached_content_identity_and_quarantine_custody_request:bytes,separately_injected_synthetic_freshness_policy:bytes,detached_freshness_request:bytes,separately_injected_synthetic_clock_skew_policy:bytes,detached_clock_skew_request:bytes,separately_injected_synthetic_owner_toctou_policy:bytes,detached_owner_toctou_request:bytes,separately_injected_synthetic_replay_policy:bytes,detached_replay_request:bytes,separately_injected_synthetic_concurrent_replay_policy:bytes,detached_concurrent_replay_request:bytes,mode:str)->dict[str,Any]:
 reject_mode(mode)
 try:prior=predecessor.review_replay(frame,detached_authentication_bundle,separately_injected_synthetic_trust_policy,separately_injected_synthetic_signer_authorization_policy,detached_authorization_request,separately_injected_synthetic_track_profile_binding_policy,detached_track_profile_binding_request,separately_injected_synthetic_end_to_end_subject_binding_policy,detached_end_to_end_subject_binding_request,separately_injected_synthetic_content_identity_and_quarantine_custody_policy,detached_content_identity_and_quarantine_custody_request,separately_injected_synthetic_freshness_policy,detached_freshness_request,separately_injected_synthetic_clock_skew_policy,detached_clock_skew_request,separately_injected_synthetic_owner_toctou_policy,detached_owner_toctou_request,separately_injected_synthetic_replay_policy,detached_replay_request,predecessor.SYNTHETIC_KAT_MODE)
 except predecessor.ReplayReviewError as e:raise ConcurrentReplayReviewError("E_PREDECESSOR_REPLAY_REJECTED",f"{e.code}: {e.detail}",detail_code=e.code)from e
 try:profiles=validate_policy(decode(separately_injected_synthetic_concurrent_replay_policy,MAX_POLICY_BYTES,"CONCURRENT_REPLAY_POLICY"))
 except ConcurrentReplayReviewError as e:raise ConcurrentReplayReviewError("E_CONCURRENT_REPLAY_POLICY_REJECTED",f"{e.code}: {e.detail}",detail_code=e.code)from e
 try:
  req=validate_request(decode(detached_concurrent_replay_request,MAX_REQUEST_BYTES,"CONCURRENT_REPLAY_REQUEST"));vals={"t13_receipt_content_sha256":prior.get("content_sha256"),"track_id":prior.get("track_id"),**req};matches=[p for p in profiles if all(type(p[f])is type(vals[f])and p[f]==vals[f]for f in MATCH_FIELDS)];require(len(matches)==1,"E_CONCURRENT_REPLAY_EXACT_MATCH","one");require(prior.get("schema")==predecessor.RECEIPT_SCHEMA and prior.get("t13_replay_implemented")is True and prior.get("t14_authorized")is False and prior.get("isolated_lab_candidate_surface_component_total")==11,"E_T13_RECEIPT_TRUTH","T13");require(req["contender_a_observed_generation"]==req["contender_b_observed_generation"],"E_CONCURRENT_REPLAY_GENERATION_RACE","same generation");require(req["contender_a_cas_result"]^req["contender_b_cas_result"],"E_CONCURRENT_REPLAY_WINNER_CARDINALITY","exactly one")
 except ConcurrentReplayReviewError as e:raise ConcurrentReplayReviewError(TARGET_PRODUCTION_FAILURE_CODE,f"{e.code}: {e.detail}",detail_code=e.code)from e
 r={"authority_decision_exact_source_commit":"0340a15d001cb00ea9aabcf98577affb2bc609da","authority_decision_release_commit":"f65f7c03dfeec92bbc1180dd15b57bddc1bfce2e","authorized_unit":AUTHORIZED_UNIT,"binding_match_count":1,"binding_policy_match_dimension_count":7,"binding_profile_count":2,"binding_request_field_count":5,"component_state":COMPONENT_STATE,"content_sha256":"0"*64,"contender_a_cas_result":req["contender_a_cas_result"],"contender_a_observed_generation":req["contender_a_observed_generation"],"contender_b_cas_result":req["contender_b_cas_result"],"contender_b_observed_generation":req["contender_b_observed_generation"],"execution_mode":SYNTHETIC_KAT_MODE,"implementation_authority_single_use_consumed":True,"isolated_lab_candidate_surface_component_total":12,"isolated_lab_candidate_surface_components_implemented":12,"local_threat_specifications_covered":14,"network_accessed":False,"predecessor_receipt_content_sha256":prior["content_sha256"],"predecessor_receipt_schema":predecessor.RECEIPT_SCHEMA,"predecessor_review_count":1,"production_admissible":False,"production_ingestion_control_count":14,"production_ingestion_controls_implemented":0,"production_threat_specification_count":20,"production_threat_specifications_runtime_exercised":0,"production_validated_evidence_items":0,"provider_authority":False,"public_input_count":22,"real_concurrency_or_linearizability_proved":False,"real_evidence_items_present":0,"reservation_key_sha256":req["reservation_key_sha256"],"runtime_authority":False,"runtime_prerequisite_count":16,"runtime_prerequisites_satisfied":0,"schema":RECEIPT_SCHEMA,"schema_version":1,"side_effects_unlocked":"NONE","status":STATUS,"synthetic_fixture":True,"t13_replay_implemented":True,"t14_concurrent_replay_implemented":True,"t15_authorized":False,"target_production_failure_code":TARGET_PRODUCTION_FAILURE_CODE,"track_id":prior["track_id"]};x=dict(r);del x["content_sha256"];r["content_sha256"]=hashlib.sha256(RECEIPT_DOMAIN.encode()+b"\0"+canonical(x)).hexdigest();return r
__all__=["AUTHORIZED_UNIT","POLICY_SCHEMA","PROFILES","RECEIPT_DOMAIN","RECEIPT_SCHEMA","REQUEST_FIELDS","SYNTHETIC_KAT_MODE","PRODUCTION_MODE","TARGET_PRODUCTION_FAILURE_CODE","ConcurrentReplayReviewError","known_answer_concurrent_replay_policy_bytes","known_answer_concurrent_replay_request_bytes","review_concurrent_replay"]
