#!/usr/bin/env python3
"""Pure public isolated-lab T13 replay-triple verifier."""
from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from typing import Any,Mapping,NoReturn
import biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_synthetic_exact_t11_receipt_track_validation_owner_epoch_and_decision_recheck_owner_epoch_verifier_isolated_lab_v1 as predecessor

SYNTHETIC_KAT_MODE="SYNTHETIC_KAT";PRODUCTION_MODE="PRODUCTION"
POLICY_SCHEMA="agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.replay_synthetic_policy_isolated_lab_kat.v1"
RECEIPT_SCHEMA="agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.replay_synthetic_exact_t12_receipt_track_reserved_issuer_nonce_sequence_and_packet_identity_submitted_issuer_nonce_sequence_and_packet_identity_verifier_isolated_lab_v1.receipt.v0"
STATUS="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_REPLAY_SYNTHETIC_EXACT_T12_RECEIPT_TRACK_RESERVED_ISSUER_NONCE_SEQUENCE_AND_PACKET_IDENTITY_SUBMITTED_ISSUER_NONCE_SEQUENCE_AND_PACKET_IDENTITY_VERIFIED_ISOLATED_LAB_COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
AUTHORIZED_UNIT="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_REPLAY_SYNTHETIC_EXACT_T12_RECEIPT_TRACK_RESERVED_ISSUER_NONCE_SEQUENCE_AND_PACKET_IDENTITY_SUBMITTED_ISSUER_NONCE_SEQUENCE_AND_PACKET_IDENTITY_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
COMPONENT_STATE="BOUND_SYNTHETIC_REPLAY_TRIPLE_TO_EXACT_T12_RECEIPT_CHAIN_ONLY"
RECEIPT_DOMAIN="AB_TRACK_B_T13_REPLAY_ISOLATED_LAB_KAT_RECEIPT_V1"
TARGET_PRODUCTION_FAILURE_CODE="E_PRODUCTION_REPLAY_REJECTED";DEFAULT_DISPOSITION="REJECTED_FAIL_CLOSED";MATCHING_PROFILE="EXACT_ALL_FIELDS_EQUAL"
MAX_POLICY_BYTES=65536;MAX_REQUEST_BYTES=16384;MAX_INT=2**63-1
REQUEST_FIELDS=("submitted_issuer_nonce","submitted_sequence","submitted_packet_identity_sha256")
MATCH_FIELDS=("t12_receipt_content_sha256","track_id",*REQUEST_FIELDS)
PROFILE_FIELDS=("t12_receipt_content_sha256","track_id","reserved_issuer_nonce","reserved_sequence","reserved_packet_identity_sha256",*REQUEST_FIELDS)
POLICY_KEYS=("default_disposition","matching_profile","profiles","reject_on_multiple_matches","reject_on_zero_matches","schema","schema_version")

@dataclass(frozen=True)
class ReplayProfile:
    t12_receipt_content_sha256:str;track_id:str;reserved_issuer_nonce:str;reserved_sequence:int;reserved_packet_identity_sha256:str;submitted_issuer_nonce:str;submitted_sequence:int;submitted_packet_identity_sha256:str
PROFILES=(
 ReplayProfile("ddb58a2e4db7c74aedbf2504dcf38bde8419722429aeb3dba9cd61273ba3177d","MANAGED_SPANNER_CLOUD_KMS","managed-reserved-0001",4100,"fbce175924579ab998990a7438b611cfd419937903d180e930c11058999ccbdc","managed-submitted-0002",4101,"1074bc0412ef81ad6f7afba63816dabebabe53afdbc0bb368a35877add958b77"),
 ReplayProfile("d51f20f0c0b6ba03cb8fcc8b561c671d38b59fdc80a6fe35beafa0ae9d2f5eee","SELF_HOSTED_ETCD_OPENBAO","selfhosted-reserved-0001",7300,"6a1363823cdcc2664a4428625e60ae83183ea3728975589dbb64aedca07082c3","selfhosted-submitted-0002",7301,"df6a8ab7205db8eb3e91dbfb323d4fba68a61484d13981d7d3eaa08eba6fd680"),)

class ReplayReviewError(ValueError):
 def __init__(self,code:str,detail:str,*,detail_code:str|None=None):super().__init__(f"{code}: {detail}");self.code=code;self.detail=detail;self.detail_code=detail_code
def fail(code:str,detail:str)->NoReturn:raise ReplayReviewError(code,detail)
def require(ok:bool,code:str,detail:str)->None:
 if not ok:fail(code,detail)
def reject_mode(mode:str)->None:
 if type(mode) is not str:fail("E_REPLAY_MODE_UNKNOWN","exact string required")
 if mode==PRODUCTION_MODE:fail("E_REPLAY_PRODUCTION_MODE_NOT_AUTHORIZED","production replay state unavailable")
 if mode!=SYNTHETIC_KAT_MODE:fail("E_REPLAY_MODE_UNKNOWN","only SYNTHETIC_KAT")
def pairs(items:list[tuple[str,Any]])->dict[str,Any]:
 out={}
 for k,v in items:require(type(k)is str and k not in out,"E_JSON_DUPLICATE_KEY","duplicate");out[k]=v
 return out
def no_number(v:str)->NoReturn:fail("E_JSON_NON_INTEGER_NUMBER",v)
def parse_int(v:str)->int:
 value=int(v);require(-(2**63)<=value<=MAX_INT,"E_JSON_INT_RANGE",v);return value
def canonical(v:Mapping[str,Any])->bytes:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def decode(raw:bytes,limit:int,label:str)->dict[str,Any]:
 require(type(raw)is bytes,f"E_{label}_TYPE","bytes");require(0<len(raw)<=limit,f"E_{label}_SIZE","bound")
 try:text=raw.decode('utf-8','strict');d=json.JSONDecoder(object_pairs_hook=pairs,parse_int=parse_int,parse_float=no_number,parse_constant=no_number,strict=True);value,end=d.raw_decode(text)
 except ReplayReviewError:raise
 except Exception as e:fail(f"E_{label}_JSON",str(e))
 require(end==len(text)and type(value)is dict,f"E_{label}_ROOT_OR_TRAILING","closed object");require(canonical(value)==raw,f"E_{label}_NONCANONICAL","canonical");return value
def exact(value:Mapping[str,Any],fields:tuple[str,...],code:str)->None:require(type(value)is dict and set(value)==set(fields),code,"closed fields")
def lower_sha(v:Any)->bool:return type(v)is str and len(v)==64 and all(c in '0123456789abcdef' for c in v)
def nonce(v:Any,field:str)->str:require(type(v)is str and 0<len(v.encode())<=256 and v==v.strip() and '*' not in v and '?' not in v,f"E_{field.upper()}","nonce");return v
def sequence(v:Any,field:str)->int:require(type(v)is int and 0<=v<=MAX_INT,f"E_{field.upper()}","sequence");return v
def profile_dict(p:ReplayProfile)->dict[str,Any]:return {f:getattr(p,f)for f in PROFILE_FIELDS}
def known_answer_replay_policy()->dict[str,Any]:return {"default_disposition":DEFAULT_DISPOSITION,"matching_profile":MATCHING_PROFILE,"profiles":[profile_dict(p)for p in PROFILES],"reject_on_multiple_matches":True,"reject_on_zero_matches":True,"schema":POLICY_SCHEMA,"schema_version":1}
def known_answer_replay_policy_bytes()->bytes:return canonical(known_answer_replay_policy())
def known_answer_replay_request(track_id:str)->dict[str,Any]:
 for p in PROFILES:
  if p.track_id==track_id:return {f:getattr(p,f)for f in REQUEST_FIELDS}
 fail("E_REPLAY_TRACK_UNKNOWN",track_id)
def known_answer_replay_request_bytes(track_id:str)->bytes:return canonical(known_answer_replay_request(track_id))
def validate_policy(policy:Mapping[str,Any])->tuple[Mapping[str,Any],...]:
 exact(policy,POLICY_KEYS,"E_REPLAY_POLICY_FIELDS");require(policy["schema"]==POLICY_SCHEMA and type(policy["schema"])is str,"E_REPLAY_POLICY_SCHEMA","schema");require(type(policy["schema_version"])is int and policy["schema_version"]==1,"E_REPLAY_POLICY_VERSION","version");require(policy["default_disposition"]==DEFAULT_DISPOSITION and policy["matching_profile"]==MATCHING_PROFILE,"E_REPLAY_POLICY_MATCHING","exact deny");require(policy["reject_on_zero_matches"]is True and policy["reject_on_multiple_matches"]is True,"E_REPLAY_POLICY_AMBIGUITY","reject")
 profiles=policy["profiles"];require(type(profiles)is list and len(profiles)==2,"E_REPLAY_POLICY_PROFILES","two")
 for candidate,frozen in zip(profiles,PROFILES,strict=True):
  exact(candidate,PROFILE_FIELDS,"E_REPLAY_PROFILE_FIELDS");nonce(candidate["reserved_issuer_nonce"],"reserved_issuer_nonce");nonce(candidate["submitted_issuer_nonce"],"submitted_issuer_nonce");sequence(candidate["reserved_sequence"],"reserved_sequence");sequence(candidate["submitted_sequence"],"submitted_sequence");require(lower_sha(candidate["reserved_packet_identity_sha256"])and lower_sha(candidate["submitted_packet_identity_sha256"]),"E_REPLAY_PACKET_SHA","hash");require(candidate==profile_dict(frozen),"E_REPLAY_PROFILE_EXACT","frozen/order")
 return tuple(profiles)
def validate_request(request:Mapping[str,Any])->Mapping[str,Any]:
 exact(request,REQUEST_FIELDS,"E_REPLAY_REQUEST_FIELDS");nonce(request["submitted_issuer_nonce"],"submitted_issuer_nonce");sequence(request["submitted_sequence"],"submitted_sequence");require(lower_sha(request["submitted_packet_identity_sha256"]),"E_SUBMITTED_PACKET_IDENTITY_SHA256","hash");return request

def review_replay(frame:bytes,detached_authentication_bundle:bytes,separately_injected_synthetic_trust_policy:bytes,separately_injected_synthetic_signer_authorization_policy:bytes,detached_authorization_request:bytes,separately_injected_synthetic_track_profile_binding_policy:bytes,detached_track_profile_binding_request:bytes,separately_injected_synthetic_end_to_end_subject_binding_policy:bytes,detached_end_to_end_subject_binding_request:bytes,separately_injected_synthetic_content_identity_and_quarantine_custody_policy:bytes,detached_content_identity_and_quarantine_custody_request:bytes,separately_injected_synthetic_freshness_policy:bytes,detached_freshness_request:bytes,separately_injected_synthetic_clock_skew_policy:bytes,detached_clock_skew_request:bytes,separately_injected_synthetic_owner_toctou_policy:bytes,detached_owner_toctou_request:bytes,separately_injected_synthetic_replay_policy:bytes,detached_replay_request:bytes,mode:str)->dict[str,Any]:
 reject_mode(mode)
 try:prior=predecessor.review_owner_toctou(frame,detached_authentication_bundle,separately_injected_synthetic_trust_policy,separately_injected_synthetic_signer_authorization_policy,detached_authorization_request,separately_injected_synthetic_track_profile_binding_policy,detached_track_profile_binding_request,separately_injected_synthetic_end_to_end_subject_binding_policy,detached_end_to_end_subject_binding_request,separately_injected_synthetic_content_identity_and_quarantine_custody_policy,detached_content_identity_and_quarantine_custody_request,separately_injected_synthetic_freshness_policy,detached_freshness_request,separately_injected_synthetic_clock_skew_policy,detached_clock_skew_request,separately_injected_synthetic_owner_toctou_policy,detached_owner_toctou_request,predecessor.SYNTHETIC_KAT_MODE)
 except predecessor.OwnerToctouReviewError as e:raise ReplayReviewError("E_PREDECESSOR_OWNER_TOCTOU_REJECTED",f"{e.code}: {e.detail}",detail_code=e.code)from e
 try:profiles=validate_policy(decode(separately_injected_synthetic_replay_policy,MAX_POLICY_BYTES,"REPLAY_POLICY"))
 except ReplayReviewError as e:raise ReplayReviewError("E_REPLAY_POLICY_REJECTED",f"{e.code}: {e.detail}",detail_code=e.code)from e
 try:
  request=validate_request(decode(detached_replay_request,MAX_REQUEST_BYTES,"REPLAY_REQUEST"));values={"t12_receipt_content_sha256":prior.get("content_sha256"),"track_id":prior.get("track_id"),**request};matches=[p for p in profiles if all(type(p[f])is type(values[f])and p[f]==values[f]for f in MATCH_FIELDS)];require(len(matches)==1,"E_REPLAY_EXACT_MATCH","one profile");selected=matches[0];require(prior.get("schema")==predecessor.RECEIPT_SCHEMA and prior.get("t12_owner_toctou_implemented")is True and prior.get("t13_authorized")is False and prior.get("isolated_lab_candidate_surface_component_total")==10,"E_T12_RECEIPT_TRUTH","T12")
  require(request["submitted_issuer_nonce"]!=selected["reserved_issuer_nonce"],"E_ISSUER_NONCE_REPLAY","reserved nonce");require(request["submitted_sequence"]!=selected["reserved_sequence"],"E_SEQUENCE_REPLAY","reserved sequence");require(request["submitted_packet_identity_sha256"]!=selected["reserved_packet_identity_sha256"],"E_PACKET_IDENTITY_REPLAY","reserved packet")
 except ReplayReviewError as e:raise ReplayReviewError(TARGET_PRODUCTION_FAILURE_CODE,f"{e.code}: {e.detail}",detail_code=e.code)from e
 receipt={"authority_decision_exact_source_commit":"6455890d869f16d34a93b3ec1e3e3220567435d1","authority_decision_release_commit":"a6369cea107adfe5e1366d6749c638d6001de62b","authorized_unit":AUTHORIZED_UNIT,"binding_match_count":1,"binding_policy_match_dimension_count":5,"binding_profile_count":2,"binding_request_field_count":3,"component_state":COMPONENT_STATE,"content_sha256":"0"*64,"execution_mode":SYNTHETIC_KAT_MODE,"implementation_authority_single_use_consumed":True,"isolated_lab_candidate_surface_component_total":11,"isolated_lab_candidate_surface_components_implemented":11,"local_threat_specifications_covered":13,"network_accessed":False,"predecessor_receipt_content_sha256":prior["content_sha256"],"predecessor_receipt_schema":predecessor.RECEIPT_SCHEMA,"predecessor_review_count":1,"production_admissible":False,"production_ingestion_control_count":14,"production_ingestion_controls_implemented":0,"production_threat_specification_count":20,"production_threat_specifications_runtime_exercised":0,"production_validated_evidence_items":0,"provider_authority":False,"public_input_count":20,"real_evidence_items_present":0,"replay_policy_separately_injected":True,"replay_policy_sha256":hashlib.sha256(separately_injected_synthetic_replay_policy).hexdigest(),"replay_request_detached":True,"replay_request_observed_after_policy":True,"replay_request_sha256":hashlib.sha256(detached_replay_request).hexdigest(),"reserved_issuer_nonce":selected["reserved_issuer_nonce"],"reserved_packet_identity_sha256":selected["reserved_packet_identity_sha256"],"reserved_sequence":selected["reserved_sequence"],"runtime_authority":False,"runtime_prerequisite_count":16,"runtime_prerequisites_satisfied":0,"schema":RECEIPT_SCHEMA,"schema_version":1,"side_effects_unlocked":"NONE","status":STATUS,"submitted_issuer_nonce":request["submitted_issuer_nonce"],"submitted_packet_identity_sha256":request["submitted_packet_identity_sha256"],"submitted_sequence":request["submitted_sequence"],"synthetic_identifiers_are_durable_replay_state":False,"t12_owner_toctou_implemented":True,"t13_replay_implemented":True,"t14_authorized":False,"target_production_failure_code":TARGET_PRODUCTION_FAILURE_CODE,"track_id":prior["track_id"]}
 copied=dict(receipt);del copied["content_sha256"];receipt["content_sha256"]=hashlib.sha256(RECEIPT_DOMAIN.encode()+b"\0"+canonical(copied)).hexdigest();return receipt
__all__=["AUTHORIZED_UNIT","COMPONENT_STATE","DEFAULT_DISPOSITION","MATCH_FIELDS","MATCHING_PROFILE","POLICY_SCHEMA","PRODUCTION_MODE","PROFILES","PROFILE_FIELDS","RECEIPT_DOMAIN","RECEIPT_SCHEMA","REQUEST_FIELDS","STATUS","SYNTHETIC_KAT_MODE","TARGET_PRODUCTION_FAILURE_CODE","ReplayProfile","ReplayReviewError","known_answer_replay_policy","known_answer_replay_policy_bytes","known_answer_replay_request","known_answer_replay_request_bytes","review_replay"]
