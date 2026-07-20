#!/usr/bin/env python3
"""Pure public isolated-lab T16 ordered-set completeness verifier."""
from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from typing import Any,Mapping,NoReturn
import biocortex_ab_track_b_reference_provider_fault_injection_runner_set_completeness_synthetic_exact_t14_receipt_track_and_ordered_validated_entry_t01_through_t14_verifier_isolated_lab_v1 as predecessor

SYNTHETIC_KAT_MODE="SYNTHETIC_KAT";PRODUCTION_MODE="PRODUCTION"
POLICY_SCHEMA="agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.owner_set_synthetic_policy_isolated_lab_kat.v1"
RECEIPT_SCHEMA="agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.owner_set_synthetic_exact_t15_receipt_track_and_ordered_owner_entry_t01_through_t15_verifier_isolated_lab_v1.receipt.v0"
STATUS="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_OWNER_SET_SYNTHETIC_EXACT_T15_RECEIPT_TRACK_AND_ORDERED_VALIDATED_ENTRY_T01_THROUGH_T15_VERIFIED_ISOLATED_LAB_COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
AUTHORIZED_UNIT="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_OWNER_SET_SYNTHETIC_EXACT_T15_RECEIPT_TRACK_AND_ORDERED_VALIDATED_ENTRY_T01_THROUGH_T15_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
COMPONENT_STATE="BOUND_SYNTHETIC_EXACT_ORDERED_T01_THROUGH_T15_SET_TO_EXACT_T15_RECEIPT_CHAIN_ONLY"
RECEIPT_DOMAIN="AB_TRACK_B_T16_OWNER_SET_ISOLATED_LAB_KAT_RECEIPT_V1";ENTRY_DOMAIN=b"AB_T16_OWNER_SET_SYNTHETIC_ENTRY_V1";TARGET_PRODUCTION_FAILURE_CODE="E_PRODUCTION_OWNER_SET_FAILED"
DEFAULT_DISPOSITION="REJECTED_FAIL_CLOSED";MATCHING_PROFILE="EXACT_ALL_FIELDS_EQUAL";MAX_POLICY_BYTES=131072;MAX_REQUEST_BYTES=65536
REQUEST_FIELDS=("ordered_owner_entries",);ENTRY_FIELDS=("ordinal","case_id","validated_receipt_content_sha256");MATCH_FIELDS=("t15_receipt_content_sha256","track_id","ordered_owner_entries");PROFILE_FIELDS=MATCH_FIELDS
POLICY_KEYS=("default_disposition","matching_profile","profiles","reject_on_multiple_matches","reject_on_zero_matches","schema","schema_version")
@dataclass(frozen=True)
class OwnerProfile:t15_receipt_content_sha256:str;track_id:str;ordered_owner_entries:tuple[str,...]
def entry_hash(track:str,n:int)->str:return hashlib.sha256(ENTRY_DOMAIN+b"\0"+track.encode()+b"\0"+f"T{n:02d}".encode()).hexdigest()
def entries(track:str)->tuple[str,...]:return tuple(entry_hash(track,n)for n in range(1,16))
PROFILES=(OwnerProfile("ef7e1cecb967a4d8240839319e65fa1030bed9acee6c1a29a85a9a73f1ff1d70","MANAGED_SPANNER_CLOUD_KMS",entries("MANAGED_SPANNER_CLOUD_KMS")),OwnerProfile("33e7774c242ecc6fc0c5e94bd42148a50abcff986d79c36ad0c2d7151822a0da","SELF_HOSTED_ETCD_OPENBAO",entries("SELF_HOSTED_ETCD_OPENBAO")))
class OwnerSetReviewError(ValueError):
 def __init__(self,code:str,detail:str,*,detail_code:str|None=None):super().__init__(f"{code}: {detail}");self.code=code;self.detail=detail;self.detail_code=detail_code
def fail(c:str,d:str)->NoReturn:raise OwnerSetReviewError(c,d)
def require(x:bool,c:str,d:str)->None:
 if not x:fail(c,d)
def reject_mode(m:str)->None:
 if type(m)is not str:fail("E_OWNER_SET_MODE_UNKNOWN","exact string")
 if m==PRODUCTION_MODE:fail("E_OWNER_SET_PRODUCTION_MODE_NOT_AUTHORIZED","production review unavailable")
 if m!=SYNTHETIC_KAT_MODE:fail("E_OWNER_SET_MODE_UNKNOWN","only SYNTHETIC_KAT")
def pairs(items:list[tuple[str,Any]])->dict[str,Any]:
 out={}
 for k,v in items:require(type(k)is str and k not in out,"E_JSON_DUPLICATE_KEY","duplicate");out[k]=v
 return out
def no_num(v:str)->NoReturn:fail("E_JSON_NON_INTEGER_NUMBER",v)
def parse_int(v:str)->int:x=int(v);require(-(2**63)<=x<=2**63-1,"E_JSON_INT_RANGE",v);return x
def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def decode(raw:bytes,limit:int,label:str)->dict[str,Any]:
 require(type(raw)is bytes,f"E_{label}_TYPE","bytes");require(0<len(raw)<=limit,f"E_{label}_SIZE","bound")
 try:text=raw.decode('utf-8','strict');d=json.JSONDecoder(object_pairs_hook=pairs,parse_int=parse_int,parse_float=no_num,parse_constant=no_num,strict=True);v,end=d.raw_decode(text)
 except OwnerSetReviewError:raise
 except Exception as e:fail(f"E_{label}_JSON",str(e))
 require(end==len(text)and type(v)is dict,f"E_{label}_ROOT_OR_TRAILING","closed");require(canonical(v)==raw,f"E_{label}_NONCANONICAL","canonical");return v
def exact(v:Mapping[str,Any],f:tuple[str,...],c:str)->None:require(type(v)is dict and set(v)==set(f),c,"fields")
def sha(v:Any)->bool:return type(v)is str and len(v)==64 and all(c in '0123456789abcdef'for c in v)
def pd(p:OwnerProfile)->dict[str,Any]:return {"t15_receipt_content_sha256":p.t15_receipt_content_sha256,"track_id":p.track_id,"ordered_owner_entries":list(p.ordered_owner_entries)}
def known_answer_owner_set_policy()->dict[str,Any]:return {"default_disposition":DEFAULT_DISPOSITION,"matching_profile":MATCHING_PROFILE,"profiles":[pd(p)for p in PROFILES],"reject_on_multiple_matches":True,"reject_on_zero_matches":True,"schema":POLICY_SCHEMA,"schema_version":1}
def known_answer_owner_set_policy_bytes()->bytes:return canonical(known_answer_owner_set_policy())
def known_answer_owner_set_request(track_id:str)->dict[str,Any]:
 for p in PROFILES:
  if p.track_id==track_id:return {"ordered_owner_entries":[{"ordinal":n,"case_id":f"T{n:02d}","validated_receipt_content_sha256":h}for n,h in enumerate(p.ordered_owner_entries,1)]}
 fail("E_OWNER_SET_TRACK_UNKNOWN",track_id)
def known_answer_owner_set_request_bytes(track_id:str)->bytes:return canonical(known_answer_owner_set_request(track_id))
def validate_hashes(v:Any)->list[str]:require(type(v)is list and len(v)==15,"E_OWNER_SET_ENTRY_COUNT","fourteen");require(all(sha(x)for x in v),"E_OWNER_SET_ENTRY_HASH","sha256");require(len(set(v))==15,"E_OWNER_SET_ENTRY_DUPLICATE","unique");return v
def validate_policy(v:Mapping[str,Any])->tuple[Mapping[str,Any],...]:
 exact(v,POLICY_KEYS,"E_OWNER_SET_POLICY_FIELDS");require(v["schema"]==POLICY_SCHEMA and type(v["schema"])is str,"E_OWNER_SET_POLICY_SCHEMA","schema");require(type(v["schema_version"])is int and v["schema_version"]==1,"E_OWNER_SET_POLICY_VERSION","version");require(v["default_disposition"]==DEFAULT_DISPOSITION and v["matching_profile"]==MATCHING_PROFILE,"E_OWNER_SET_POLICY_MATCHING","matching");require(v["reject_on_zero_matches"]is True and v["reject_on_multiple_matches"]is True,"E_OWNER_SET_POLICY_AMBIGUITY","deny");ps=v["profiles"];require(type(ps)is list and len(ps)==2,"E_OWNER_SET_POLICY_PROFILES","two")
 for c,f in zip(ps,PROFILES,strict=True):exact(c,PROFILE_FIELDS,"E_OWNER_SET_PROFILE_FIELDS");require(sha(c["t15_receipt_content_sha256"]),"E_OWNER_SET_T15_SHA","hash");validate_hashes(c["ordered_owner_entries"]);require(c==pd(f),"E_OWNER_SET_PROFILE_EXACT","frozen")
 return tuple(ps)
def validate_request(v:Mapping[str,Any])->list[str]:
 exact(v,REQUEST_FIELDS,"E_OWNER_SET_REQUEST_FIELDS");e=v["ordered_owner_entries"];require(type(e)is list and len(e)==15,"E_OWNER_SET_ENTRY_COUNT","fourteen");out=[]
 for n,x in enumerate(e,1):exact(x,ENTRY_FIELDS,"E_OWNER_SET_ENTRY_FIELDS");require(type(x["ordinal"])is int and x["ordinal"]==n and x["case_id"]==f"T{n:02d}" and type(x["case_id"])is str,"E_OWNER_SET_ENTRY_ORDER","ordinal/case");require(sha(x["validated_receipt_content_sha256"]),"E_OWNER_SET_ENTRY_HASH","sha256");out.append(x["validated_receipt_content_sha256"])
 require(len(set(out))==15,"E_OWNER_SET_ENTRY_DUPLICATE","unique");return out
def review_owner_set(frame:bytes,detached_authentication_bundle:bytes,separately_injected_synthetic_trust_policy:bytes,separately_injected_synthetic_signer_authorization_policy:bytes,detached_authorization_request:bytes,separately_injected_synthetic_track_profile_binding_policy:bytes,detached_track_profile_binding_request:bytes,separately_injected_synthetic_end_to_end_subject_binding_policy:bytes,detached_end_to_end_subject_binding_request:bytes,separately_injected_synthetic_content_identity_and_quarantine_custody_policy:bytes,detached_content_identity_and_quarantine_custody_request:bytes,separately_injected_synthetic_freshness_policy:bytes,detached_freshness_request:bytes,separately_injected_synthetic_clock_skew_policy:bytes,detached_clock_skew_request:bytes,separately_injected_synthetic_owner_toctou_policy:bytes,detached_owner_toctou_request:bytes,separately_injected_synthetic_replay_policy:bytes,detached_replay_request:bytes,separately_injected_synthetic_concurrent_replay_policy:bytes,detached_concurrent_replay_request:bytes,separately_injected_synthetic_set_completeness_policy:bytes,detached_set_completeness_request:bytes,separately_injected_synthetic_owner_set_policy:bytes,detached_owner_set_request:bytes,mode:str)->dict[str,Any]:
 reject_mode(mode)
 try:prior=predecessor.review_set_completeness(frame,detached_authentication_bundle,separately_injected_synthetic_trust_policy,separately_injected_synthetic_signer_authorization_policy,detached_authorization_request,separately_injected_synthetic_track_profile_binding_policy,detached_track_profile_binding_request,separately_injected_synthetic_end_to_end_subject_binding_policy,detached_end_to_end_subject_binding_request,separately_injected_synthetic_content_identity_and_quarantine_custody_policy,detached_content_identity_and_quarantine_custody_request,separately_injected_synthetic_freshness_policy,detached_freshness_request,separately_injected_synthetic_clock_skew_policy,detached_clock_skew_request,separately_injected_synthetic_owner_toctou_policy,detached_owner_toctou_request,separately_injected_synthetic_replay_policy,detached_replay_request,separately_injected_synthetic_concurrent_replay_policy,detached_concurrent_replay_request,separately_injected_synthetic_set_completeness_policy,detached_set_completeness_request,predecessor.SYNTHETIC_KAT_MODE)
 except predecessor.SetCompletenessReviewError as e:raise OwnerSetReviewError("E_PREDECESSOR_CONCURRENT_REPLAY_REJECTED",f"{e.code}: {e.detail}",detail_code=e.code)from e
 try:profiles=validate_policy(decode(separately_injected_synthetic_owner_set_policy,MAX_POLICY_BYTES,"OWNER_SET_POLICY"))
 except OwnerSetReviewError as e:raise OwnerSetReviewError("E_OWNER_SET_POLICY_REJECTED",f"{e.code}: {e.detail}",detail_code=e.code)from e
 try:
  ordered=validate_request(decode(detached_owner_set_request,MAX_REQUEST_BYTES,"OWNER_SET_REQUEST"));vals={"t15_receipt_content_sha256":prior.get("content_sha256"),"track_id":prior.get("track_id"),"ordered_owner_entries":ordered};matches=[p for p in profiles if all(type(p[f])is type(vals[f])and p[f]==vals[f]for f in MATCH_FIELDS)];require(len(matches)==1,"E_OWNER_SET_EXACT_MATCH","one");require(prior.get("schema")==predecessor.RECEIPT_SCHEMA and prior.get("t15_set_completeness_implemented")is True and prior.get("t16_authorized")is False and prior.get("isolated_lab_candidate_surface_component_total")==13,"E_T15_RECEIPT_TRUTH","T15")
 except OwnerSetReviewError as e:raise OwnerSetReviewError(TARGET_PRODUCTION_FAILURE_CODE,f"{e.code}: {e.detail}",detail_code=e.code)from e
 set_hash=hashlib.sha256(b"AB_T16_ORDERED_SET_V1\0"+canonical(ordered)).hexdigest();r={"authority_decision_exact_source_commit":"8e51f8ea","authority_decision_release_commit":"ec67d4e3ba11c69b1b7cf28fbaf6d1030e731aab","authorized_unit":AUTHORIZED_UNIT,"binding_match_count":1,"binding_policy_match_dimension_count":3,"binding_profile_count":2,"binding_request_field_count":1,"component_state":COMPONENT_STATE,"content_sha256":"0"*64,"execution_mode":SYNTHETIC_KAT_MODE,"implementation_authority_single_use_consumed":True,"isolated_lab_candidate_surface_component_total":14,"isolated_lab_candidate_surface_components_implemented":14,"local_threat_specifications_covered":16,"network_accessed":False,"ordered_entry_count":15,"ordered_owner_set_sha256":set_hash,"predecessor_receipt_content_sha256":prior["content_sha256"],"predecessor_receipt_schema":predecessor.RECEIPT_SCHEMA,"predecessor_review_count":1,"production_admissible":False,"production_ingestion_control_count":14,"production_ingestion_controls_implemented":0,"production_threat_specification_count":20,"production_threat_specifications_runtime_exercised":0,"production_validated_evidence_items":0,"provider_authority":False,"public_input_count":26,"real_evidence_items_present":0,"runtime_authority":False,"runtime_prerequisite_count":16,"runtime_prerequisites_satisfied":0,"schema":RECEIPT_SCHEMA,"schema_version":1,"side_effects_unlocked":"NONE","status":STATUS,"synthetic_fixture":True,"synthetic_set_is_production_owner_handoff":False,"t15_set_completeness_implemented":True,"t16_owner_set_implemented":True,"t17_authorized":False,"target_production_failure_code":TARGET_PRODUCTION_FAILURE_CODE,"track_id":prior["track_id"]};x=dict(r);del x["content_sha256"];r["content_sha256"]=hashlib.sha256(RECEIPT_DOMAIN.encode()+b"\0"+canonical(x)).hexdigest();return r
__all__=["AUTHORIZED_UNIT","POLICY_SCHEMA","PROFILES","RECEIPT_DOMAIN","RECEIPT_SCHEMA","REQUEST_FIELDS","SYNTHETIC_KAT_MODE","PRODUCTION_MODE","TARGET_PRODUCTION_FAILURE_CODE","OwnerSetReviewError","known_answer_owner_set_policy_bytes","known_answer_owner_set_request_bytes","review_owner_set"]
