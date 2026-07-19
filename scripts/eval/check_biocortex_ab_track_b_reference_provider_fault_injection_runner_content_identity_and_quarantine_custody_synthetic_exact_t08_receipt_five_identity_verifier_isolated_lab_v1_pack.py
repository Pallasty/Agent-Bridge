#!/usr/bin/env python3
"""Independent contract/adversarial checker for the isolated-lab T09 verifier."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Mapping, NoReturn

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SOURCE_REL = "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1.py"
FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1_pack_synthetic_v0.json"
SCHEMA_REL = "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-content-identity-and-quarantine-custody-synthetic-exact-t08-receipt-five-identity-verifier-isolated-lab-v1.schema.json"
T08_FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1_pack_synthetic_v0.json"
T07_FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_synthetic_exact_packet_profile_provider_or_lab_profile_namespace_configuration_sha256_and_non_substitutable_track_verifier_isolated_lab_v1_pack_synthetic_v0.json"
T06_FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack_synthetic_v0.json"
T05_FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack_synthetic_v0.json"
OWNER_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_content_identity_and_quarantine_custody_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
SEMANTIC_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"

DATE = "2026-07-18"
SYNTHETIC_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"
POLICY_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.content_identity_and_quarantine_custody_synthetic_policy_isolated_lab_kat.v1"
RECEIPT_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1.receipt.v0"
FIXTURE_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1_pack.synthetic.v0"
PACK_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1_pack.receipt.v0"
STATUS = "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_SYNTHETIC_EXACT_T08_RECEIPT_RAW_FRAME_SHA256_CANONICAL_FRAME_SHA256_PACKET_ID_SHA256_SIGNATURE_SUBJECT_SHA256_AND_VALIDATION_SUBJECT_SHA256_VERIFIED_ISOLATED_LAB_COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
DECISION = "T09_SYNTHETIC_EXACT_FIVE_CONTENT_IDENTITIES_COMPONENT_CONFORMANT_PRODUCTION_PATH_FAIL_CLOSED"
COMPONENT_STATE = "BOUND_FIVE_SYNTHETIC_CONTENT_IDENTITIES_TO_EXACT_FRAME_AND_T08_RECEIPT_CHAIN_ONLY"
PACK_DOMAIN = "AB_TRACK_B_T09_ISOLATED_LAB_PACK_RECEIPT_V1"
RECEIPT_DOMAIN = "AB_TRACK_B_T09_ISOLATED_LAB_KAT_RECEIPT_V1"
PACKET_DOMAIN = "AB_TRACK_B_T09_SYNTHETIC_PACKET_ID_V1"
MATCHING = "EXACT_ALL_FIELDS_ASCII_BYTE_EQUAL"
DEFAULT = "REJECTED_FAIL_CLOSED"
REQUEST_FIELDS = ("raw_frame_sha256", "canonical_frame_sha256", "packet_id_sha256", "signature_subject_sha256", "validation_subject_sha256")
MATCH_FIELDS = ("t08_receipt_content_sha256", "track_id", *REQUEST_FIELDS)
POLICY_KEYS = ("default_disposition", "matching_profile", "profiles", "reject_on_multiple_matches", "reject_on_zero_matches", "schema", "schema_version")
AUTHORITY_COMMIT = "35575397bfe4ec11278565e0221f46c17130efc4"
AUTHORITY_SOURCE = "3b188ff1aadc481f55a08c9eaf13d3f66a7ff1ed"
OWNER_SHA = "0d1debb201c51a9bafdbd9a391776be70e95fe5745500172a26bb697d62a61b3"
T08_SOURCE_SHA = "2752e8b4ca393f5db14d7c980e65a5a71cdbff38a4eb19c861fffe5cc3ffc7f8"
T08_FIXTURE_SHA = "ab966ecef10652730b752f3308326f8fdba9cf61a3b688cfe421efc3788567c6"
SEMANTIC_SHA = "3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6"

PROFILES = (
    {"track_id":"MANAGED_SPANNER_CLOUD_KMS","t08_receipt_content_sha256":"7bf4b4151a12428da34eb5a095d340a4b5a1c531381385bf262cb1d5df7415b9","raw_frame_sha256":"e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295","canonical_frame_sha256":"e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295","packet_id_sha256":"f89f204c4dcb19e078a4448d8824ca8e7435688e06c5e57265789e273104571e","signature_subject_sha256":"a52aa400add05bb7b545c9eddbf1f48e55befd393f07c5c6ba6baaefd4f5343b","validation_subject_sha256":"7bf4b4151a12428da34eb5a095d340a4b5a1c531381385bf262cb1d5df7415b9","signature_domain":"AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_MANAGED_KAT_SIGNATURE_V1","case_id":"VALID_MANAGED_CONTENT_IDENTITY_V1","predecessor_case_id":"VALID_MANAGED_END_TO_END_SUBJECT_BINDING_V1","receipt_sha256":"707017354e9943d9049acf546124e5c2115b49258420fa83c3e9c1e681024953"},
    {"track_id":"SELF_HOSTED_ETCD_OPENBAO","t08_receipt_content_sha256":"77e9eadcc83235e9f5b0357e9ca15b046c4044d36e764583b481bc7fb2c29865","raw_frame_sha256":"da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e","canonical_frame_sha256":"da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e","packet_id_sha256":"16f3d9bb3c69666d374e72f16036f5fe152ab73d864c051e57429fe4f09308bc","signature_subject_sha256":"2eb3584afe6c8f18281224785ec083e531da37eed71524f2eedbf3a8225055ac","validation_subject_sha256":"77e9eadcc83235e9f5b0357e9ca15b046c4044d36e764583b481bc7fb2c29865","signature_domain":"AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_SELF_HOSTED_KAT_SIGNATURE_V1","case_id":"VALID_SELF_HOSTED_CONTENT_IDENTITY_V1","predecessor_case_id":"VALID_SELF_HOSTED_END_TO_END_SUBJECT_BINDING_V1","receipt_sha256":"e7fb01f915b6436f2503be78cac1957d93197e8e1dd4ca336a711c5ec08e7ed6"},
)

class CheckError(ValueError): pass
def require(ok: bool, code: str, detail: str) -> None:
    if not ok: raise CheckError(f"{code}: {detail}")
def cb(value: Any) -> bytes: return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
def sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def domain_sha(domain: str, value: Any) -> str: return sha(domain.encode("ascii") + b"\x00" + cb(value))
def lp(domain: str, frame: bytes) -> bytes:
    encoded=domain.encode("ascii"); return len(encoded).to_bytes(8,"big")+encoded+len(frame).to_bytes(8,"big")+frame
def path(relative: str) -> Path:
    require(type(relative) is str and relative and not relative.startswith("/") and all(x not in ("", ".", "..") for x in relative.split("/")), "E_PATH", relative)
    candidate=ROOT.joinpath(*relative.split("/")); resolved=candidate.resolve(strict=True)
    require(ROOT in resolved.parents and candidate.is_file() and not candidate.is_symlink(), "E_PATH_ESCAPE", relative); return candidate
def raw_sha(relative: str) -> str: return sha(path(relative).read_bytes())
def pairs(items: list[tuple[str,Any]]) -> dict[str,Any]:
    out={}
    for key,value in items: require(type(key) is str and key not in out,"E_JSON_DUPLICATE",repr(key)); out[key]=value
    return out
def no_float(token: str) -> NoReturn: raise CheckError(f"E_JSON_FLOAT:{token}")
def parse_int(token: str) -> int:
    value=int(token); require(-(2**63)<=value<=2**63-1,"E_JSON_INT",token); return value
def load_json(relative: str) -> dict[str,Any]:
    raw=path(relative).read_bytes(); require(0<len(raw)<=8*1024*1024,"E_JSON_SIZE",relative); text=raw.decode("utf-8","strict")
    decoder=json.JSONDecoder(object_pairs_hook=pairs,parse_int=parse_int,parse_float=no_float,parse_constant=no_float,strict=True); value,end=decoder.raw_decode(text)
    require(not text[end:].strip() and type(value) is dict,"E_JSON_TRAILING",relative); return value
def load_module() -> ModuleType:
    source=path(SOURCE_REL); spec=importlib.util.spec_from_file_location("_t09_subject",source); require(spec is not None and spec.loader is not None,"E_IMPORT",SOURCE_REL)
    inserted=str(source.parent) not in sys.path
    if inserted: sys.path.insert(0,str(source.parent))
    try:
        module=importlib.util.module_from_spec(spec); sys.modules["_t09_subject"]=module; spec.loader.exec_module(module); return module
    finally:
        if inserted: sys.path.remove(str(source.parent))
def expected_policy() -> dict[str,Any]:
    return {"default_disposition":DEFAULT,"matching_profile":MATCHING,"profiles":[{k:p[k] for k in MATCH_FIELDS} for p in PROFILES],"reject_on_multiple_matches":True,"reject_on_zero_matches":True,"schema":POLICY_SCHEMA,"schema_version":1}
def mutate(value: Mapping[str,Any], operation: Callable[[dict[str,Any]],None]) -> bytes:
    result=copy.deepcopy(value); operation(result); return cb(result)

def build_vectors(module: ModuleType) -> tuple[list[tuple[Any,...]], list[dict[str,Any]], int]:
    fixture,t08,t07,t06,t05=map(load_json,(FIXTURE_REL,T08_FIXTURE_REL,T07_FIXTURE_REL,T06_FIXTURE_REL,T05_FIXTURE_REL))
    require(fixture["schema"]==FIXTURE_SCHEMA and fixture["public_only"] is True and fixture["contains_private_or_seed_material"] is False,"E_FIXTURE_HEADER","truth")
    require(fixture["source_bindings"]["authority_decision_integration_commit"]==AUTHORITY_COMMIT and fixture["source_bindings"]["authority_decision_source_commit"]==AUTHORITY_SOURCE,"E_FIXTURE_AUTHORITY","drift")
    require(fixture["source_bindings"]["owner_decision_sha256"]==OWNER_SHA==raw_sha(OWNER_REL),"E_OWNER_HASH","drift")
    require(raw_sha(T08_FIXTURE_REL)==T08_FIXTURE_SHA and raw_sha(SEMANTIC_REL)==SEMANTIC_SHA,"E_DEPENDENCY_HASH","drift")
    require(fixture["separately_injected_synthetic_content_identity_and_quarantine_custody_policy"]==expected_policy(),"E_FIXTURE_POLICY","drift")
    c8={x["case_id"]:x for x in t08["valid_cases"]}; c7={x["case_id"]:x for x in t07["valid_cases"]}; c6={x["case_id"]:x for x in t06["valid_cases"]}; c5={x["case_id"]:x for x in t05["valid_cases"]}
    real=module.predecessor.review_end_to_end_subject_binding; calls=[]; vectors=[]; receipts=[]
    def counted(*args:Any,**kwargs:Any)->Any: calls.append(args); return real(*args,**kwargs)
    module.predecessor.review_end_to_end_subject_binding=counted
    try:
        for index,p in enumerate(PROFILES):
            x8=c8[p["predecessor_case_id"]]; x7=c7[x8["predecessor_case_id"]]; x6=c6[x7["predecessor_case_id"]]; x5=c5[x6["predecessor_case_id"]]; frame=x5["frame_utf8"].encode()
            request={k:p[k] for k in REQUEST_FIELDS}
            vector=(frame,cb(x5["detached_authentication_bundle"]),cb(t05["separately_injected_synthetic_trust_policy"]),cb(t06["separately_injected_synthetic_signer_authorization_policy"]),cb(x6["detached_authorization_request"]),cb(t07["separately_injected_synthetic_track_profile_binding_policy"]),cb(x7["detached_track_profile_binding_request"]),cb(t08["separately_injected_synthetic_end_to_end_subject_binding_policy"]),cb(x8["detached_end_to_end_subject_binding_request"]),cb(expected_policy()),cb(request),SYNTHETIC_MODE)
            require(sha(frame)==p["raw_frame_sha256"]==p["canonical_frame_sha256"],"E_FRAME_HASH",p["track_id"]); require(sha(lp(PACKET_DOMAIN,frame))==p["packet_id_sha256"] and sha(lp(p["signature_domain"],frame))==p["signature_subject_sha256"],"E_DOMAIN_HASH",p["track_id"])
            before=len(calls); receipt=module.review_content_identity_and_quarantine_custody(*vector); require(len(calls)==before+1,"E_REAL_CALL_COUNT",p["track_id"])
            validate_receipt(receipt,p,vector[9],vector[10]); require(receipt["content_sha256"]==p["receipt_sha256"],"E_RECEIPT_HASH",p["track_id"])
            require(fixture["valid_cases"][index]["detached_content_identity_and_quarantine_custody_request"]==request and fixture["expected_receipt_content_sha256"][p["track_id"]]==p["receipt_sha256"],"E_FIXTURE_CASE",p["track_id"])
            vectors.append(vector); receipts.append(receipt)
    finally: module.predecessor.review_end_to_end_subject_binding=real
    require(len(calls)==2,"E_REAL_CALL_TOTAL",str(len(calls))); return vectors,receipts,len(calls)

def validate_receipt(receipt: Mapping[str,Any], p: Mapping[str,str], policy_raw: bytes, request_raw: bytes) -> None:
    schema=load_json(SCHEMA_REL); keys=tuple(schema["required"]); require(set(keys)==set(schema["propertyNames"]["enum"])==set(receipt) and len(keys)==84,"E_RECEIPT_KEYS",str(len(receipt)))
    expected={"binding_match_count":1,"binding_policy_match_dimension_count":7,"binding_policy_match_fields":list(MATCH_FIELDS),"binding_profile_count":2,"binding_request_field_count":5,"binding_request_fields":list(REQUEST_FIELDS),"canonical_frame_sha256":p["canonical_frame_sha256"],"component_state":COMPONENT_STATE,"content_identity_and_quarantine_custody_policy_sha256":sha(policy_raw),"content_identity_and_quarantine_custody_request_sha256":sha(request_raw),"default_disposition":DEFAULT,"execution_mode":SYNTHETIC_MODE,"isolated_lab_candidate_surface_component_total":7,"isolated_lab_candidate_surface_components_implemented":7,"isolated_lab_candidate_surface_components_locally_kat_exercised":7,"local_threat_specifications_covered":9,"local_threat_specifications_covered_ids":[f"T{x:02d}" for x in range(1,10)],"matching_profile":MATCHING,"packet_id_sha256":p["packet_id_sha256"],"predecessor_receipt_content_sha256":p["t08_receipt_content_sha256"],"predecessor_review_count":1,"production_ingestion_control_count":14,"production_threat_specification_count":20,"public_input_count":12,"raw_frame_sha256":p["raw_frame_sha256"],"runtime_prerequisite_count":16,"schema":RECEIPT_SCHEMA,"schema_version":1,"side_effects_unlocked":"NONE","signature_subject_sha256":p["signature_subject_sha256"],"status":STATUS,"target_production_control":"QUARANTINE_CUSTODY","target_production_failure_code":"E_PRODUCTION_CUSTODY_FAILED","track_id":p["track_id"],"track_identity_source":"T08_PREDECESSOR_RECEIPT_ONLY","validation_subject_sha256":p["validation_subject_sha256"]}
    for key,value in expected.items(): require(type(receipt[key]) is type(value) and receipt[key]==value,"E_RECEIPT_VALUE",key)
    true_fields=("content_identity_and_quarantine_custody_policy_separately_injected","content_identity_and_quarantine_custody_request_detached","content_identity_and_quarantine_custody_request_observed_after_policy","local_t08_specification_exercised","local_t09_specification_exercised","predecessor_receipt_and_track_non_substitutable","raw_and_canonical_hash_equal_only_for_exact_frozen_kat","reject_on_multiple_matches","reject_on_zero_matches","synthetic_fixture","t08_end_to_end_subject_binding_implemented","t09_content_identity_and_quarantine_custody_implemented")
    zero_fields=("downstream_gates_authorized","production_ingestion_controls_implemented","production_ingestion_controls_runtime_exercised","production_threat_specifications_runtime_exercised","production_validated_evidence_items","real_evidence_items_present","runtime_evidence_accepted","runtime_prerequisites_satisfied")
    false_fields=set(receipt)-set(expected)-set(true_fields)-set(zero_fields)-{"authorized_unit","content_sha256","downstream_gate_count","predecessor_receipt_schema"}
    for key in true_fields: require(receipt[key] is True,"E_RECEIPT_TRUE",key)
    for key in zero_fields: require(type(receipt[key]) is int and receipt[key]==0,"E_RECEIPT_ZERO",key)
    for key in false_fields: require(receipt[key] is False,"E_RECEIPT_FALSE",key)
    without=dict(receipt); observed=without.pop("content_sha256"); require(observed==sha(RECEIPT_DOMAIN.encode()+b"\x00"+cb(without)),"E_RECEIPT_CONTENT_HASH",p["track_id"])

def expect(module: ModuleType, vector: tuple[Any,...], *, code: str|None=None, detail: str|None=None) -> None:
    try: module.review_content_identity_and_quarantine_custody(*vector)
    except module.ContentIdentityReviewError as error:
        if code: require(error.code==code,"E_REJECT_CODE",error.code)
        if detail: require(error.detail_code==detail,"E_REJECT_DETAIL",str(error.detail_code))
    else: raise CheckError("E_MUTATION_ACCEPTED")

def mode_checks(module: ModuleType, vector: tuple[Any,...]) -> int:
    count=0
    for mode,code in ((PRODUCTION_MODE,"E_CONTENT_IDENTITY_PRODUCTION_MODE_NOT_AUTHORIZED"),("UNKNOWN","E_CONTENT_IDENTITY_MODE_UNKNOWN"),(None,"E_CONTENT_IDENTITY_MODE_UNKNOWN"),(str("SYNTHETIC_KAT"),None)):
        if code: expect(module,tuple([object()]*11+[mode]),code=code); count+=1
    class Evil(str):
        def __eq__(self,other:object)->bool: raise AssertionError("observed subclass")
    expect(module,tuple([object()]*11+[Evil(SYNTHETIC_MODE)]),code="E_CONTENT_IDENTITY_MODE_UNKNOWN"); count+=1
    return count

def directed(module: ModuleType, vector: tuple[Any,...]) -> dict[str,int]:
    counts={"policy_json":0,"request_json":0,"policy_closed_world":0,"request_exact_field":0,"derived_binding":0,"predecessor_binding":0,"default_deny":0}
    policy=json.loads(vector[9]); request=json.loads(vector[10])
    bad_json=(b"",b"{} ",b'{"a":1,"a":2}',b'{"x":NaN}',b'{"x":1.0}',b'[]',b'null',b'\xff',b'{}{}',b'{',b'{"x":9223372036854775808}')
    for index,raw in enumerate(bad_json):
        changed=list(vector); changed[9]=raw; expect(module,tuple(changed),code="E_CONTENT_IDENTITY_POLICY_REJECTED"); counts["policy_json"]+=1
        changed=list(vector); changed[10]=raw; expect(module,tuple(changed),code="E_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_FAILED"); counts["request_json"]+=1
    for key in POLICY_KEYS:
        changed=list(vector); changed[9]=mutate(policy,lambda x,k=key:x.pop(k)); expect(module,tuple(changed)); counts["policy_closed_world"]+=1
    changed=list(vector); changed[9]=mutate(policy,lambda x:x.__setitem__("extra",False)); expect(module,tuple(changed)); counts["policy_closed_world"]+=1
    for index in range(2):
        for field in MATCH_FIELDS:
            changed=list(vector); changed[9]=mutate(policy,lambda x,i=index,f=field:x["profiles"][i].pop(f)); expect(module,tuple(changed)); counts["policy_closed_world"]+=1
            changed=list(vector); changed[9]=mutate(policy,lambda x,i=index,f=field:x["profiles"][i].__setitem__(f,"0"*64 if f!="track_id" else "DRIFT")); expect(module,tuple(changed)); counts["policy_closed_world"]+=1
    operations=(lambda x:x.__setitem__("profiles",list(reversed(x["profiles"]))),lambda x:x.__setitem__("profiles",[x["profiles"][0]]),lambda x:x.__setitem__("profiles",[x["profiles"][0],x["profiles"][0]]),lambda x:x.__setitem__("default_disposition","ALLOW"),lambda x:x.__setitem__("matching_profile","PREFIX"),lambda x:x.__setitem__("reject_on_zero_matches",False),lambda x:x.__setitem__("reject_on_multiple_matches",False))
    for op in operations:
        changed=list(vector); changed[9]=mutate(policy,op); expect(module,tuple(changed)); counts["policy_closed_world"]+=1
    for field in REQUEST_FIELDS:
        changed=list(vector); changed[10]=mutate(request,lambda x,f=field:x.pop(f)); expect(module,tuple(changed)); counts["request_exact_field"]+=1
        for value in ("0"*64,"A"*64,"f"*63,"*"*64," f"*32):
            changed=list(vector); changed[10]=mutate(request,lambda x,f=field,v=value:x.__setitem__(f,v)); expect(module,tuple(changed)); counts["request_exact_field"]+=1
    changed=list(vector); changed[10]=mutate(request,lambda x:x.__setitem__("track_id",PROFILES[0]["track_id"])); expect(module,tuple(changed)); counts["request_exact_field"]+=1
    for field in REQUEST_FIELDS:
        changed=list(vector); changed[10]=mutate(request,lambda x,f=field:x.__setitem__(f,"0"*64)); expect(module,tuple(changed)); counts["derived_binding"]+=1
    real=module.predecessor.review_end_to_end_subject_binding; baseline=real(*vector[:9],SYNTHETIC_MODE)
    try:
        for field,value in (("track_id","SELF_HOSTED_ETCD_OPENBAO"),("content_sha256","0"*64),("schema","drift"),("execution_mode","PRODUCTION"),("isolated_lab_candidate_surface_component_total",5),("local_t09_specification_exercised",True),("provider_authority",True),("runtime_authority",True)):
            fake=copy.deepcopy(baseline); fake[field]=value; calls=[]
            def spy(*args:Any, _fake=fake, **kwargs:Any)->Any: calls.append(args); return copy.deepcopy(_fake)
            module.predecessor.review_end_to_end_subject_binding=spy; expect(module,vector); require(len(calls)==1,"E_SPY_CALL_COUNT",field); counts["predecessor_binding"]+=1
    finally: module.predecessor.review_end_to_end_subject_binding=real
    for op in (lambda x:x.__setitem__("profiles",[]),lambda x:x.__setitem__("profiles",[x["profiles"][0],x["profiles"][0]])):
        changed=list(vector); changed[9]=mutate(policy,op); expect(module,tuple(changed)); counts["default_deny"]+=1
    return counts

def source_checks() -> int:
    tree=ast.parse(path(SOURCE_REL).read_text()); imports={a.name for n in tree.body if isinstance(n,ast.Import) for a in n.names}|{n.module or "" for n in tree.body if isinstance(n,ast.ImportFrom)}
    require(imports <= {"__future__","hashlib","json","dataclasses","typing","biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1"},"E_SOURCE_IMPORTS",repr(imports))
    public=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="review_content_identity_and_quarantine_custody"); names=[x.arg for x in public.args.args]
    require(names==["frame","detached_authentication_bundle","separately_injected_synthetic_trust_policy","separately_injected_synthetic_signer_authorization_policy","detached_authorization_request","separately_injected_synthetic_track_profile_binding_policy","detached_track_profile_binding_request","separately_injected_synthetic_end_to_end_subject_binding_policy","detached_end_to_end_subject_binding_request","separately_injected_synthetic_content_identity_and_quarantine_custody_policy","detached_content_identity_and_quarantine_custody_request","mode"],"E_SOURCE_API",repr(names))
    require(isinstance(public.body[1],ast.Expr) and isinstance(public.body[1].value,ast.Call) and isinstance(public.body[1].value.func,ast.Name) and public.body[1].value.func.id=="_reject_mode","E_SOURCE_MODE_FIRST","order")
    calls=[n for n in ast.walk(public) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="review_end_to_end_subject_binding"]; require(len(calls)==1,"E_SOURCE_PREDECESSOR_CALL",str(len(calls)))
    text=path(SOURCE_REL).read_text(); forbidden=("requests","urllib","socket","subprocess","open(","Path(","time.","datetime","os.environ","pickle","yaml")
    require(not any(x in text for x in forbidden),"E_SOURCE_FORBIDDEN","capability"); return 14

def fixture_schema_checks() -> int:
    fixture=load_json(FIXTURE_REL); schema=load_json(SCHEMA_REL)
    require(set(fixture)=={"canonical_json_profile","contains_private_or_seed_material","date","execution_mode","expected_receipt_content_sha256","public_only","schema","separately_injected_synthetic_content_identity_and_quarantine_custody_policy","source_bindings","valid_cases"},"E_FIXTURE_KEYS","closed")
    require(len(fixture["valid_cases"])==2 and len(fixture["expected_receipt_content_sha256"])==2,"E_FIXTURE_COUNT","two")
    require(schema["minProperties"]==schema["maxProperties"]==84 and schema["required"]==schema["propertyNames"]["enum"],"E_SCHEMA_CLOSED","84")
    return 18

TSV_FIELDS=("schema","status","decision","date","component_mode","component_state","positive_track_count","real_predecessor_review_count","public_input_count","public_mode_pre_observation_test_count","policy_json_negative_test_count","request_json_negative_test_count","policy_closed_world_negative_test_count","request_exact_field_negative_test_count","derived_identity_binding_negative_test_count","predecessor_receipt_binding_negative_test_count","default_deny_negative_test_count","total_directed_negative_test_count","source_ast_guard_count","fixture_schema_guard_count","binding_profile_count","request_field_count","policy_match_dimension_count","isolated_lab_candidate_surface_component_total","isolated_lab_candidate_surface_components_implemented","local_threat_specifications_covered","production_ingestion_control_count","production_ingestion_controls_implemented","production_threat_specification_count","production_threat_specifications_runtime_exercised","runtime_prerequisite_count","runtime_prerequisites_satisfied","real_evidence_items_present","production_validated_evidence_items","runtime_authority","provider_authority","side_effects_unlocked","content_identity_policy_sha256","content_identity_request_set_sha256","receipt_set_sha256","schema_raw_sha256","fixture_raw_sha256","source_raw_sha256","predecessor_source_raw_sha256","predecessor_fixture_raw_sha256","owner_decision_raw_sha256","semantic_specification_raw_sha256","authority_decision_integration_commit","implementation_authority_consumption_state","content_sha256")
def evaluate() -> str:
    module=load_module(); vectors,receipts,real=build_vectors(module); mode=mode_checks(module,vectors[0]); counts=directed(module,vectors[0]); source=source_checks(); fixture=fixture_schema_checks(); total=sum(counts.values())+mode
    receipt={"schema":PACK_SCHEMA,"status":STATUS,"decision":DECISION,"date":DATE,"component_mode":SYNTHETIC_MODE,"component_state":COMPONENT_STATE,"positive_track_count":2,"real_predecessor_review_count":real,"public_input_count":12,"public_mode_pre_observation_test_count":mode,"policy_json_negative_test_count":counts["policy_json"],"request_json_negative_test_count":counts["request_json"],"policy_closed_world_negative_test_count":counts["policy_closed_world"],"request_exact_field_negative_test_count":counts["request_exact_field"],"derived_identity_binding_negative_test_count":counts["derived_binding"],"predecessor_receipt_binding_negative_test_count":counts["predecessor_binding"],"default_deny_negative_test_count":counts["default_deny"],"total_directed_negative_test_count":total,"source_ast_guard_count":source,"fixture_schema_guard_count":fixture,"binding_profile_count":2,"request_field_count":5,"policy_match_dimension_count":7,"isolated_lab_candidate_surface_component_total":7,"isolated_lab_candidate_surface_components_implemented":7,"local_threat_specifications_covered":9,"production_ingestion_control_count":14,"production_ingestion_controls_implemented":0,"production_threat_specification_count":20,"production_threat_specifications_runtime_exercised":0,"runtime_prerequisite_count":16,"runtime_prerequisites_satisfied":0,"real_evidence_items_present":0,"production_validated_evidence_items":0,"runtime_authority":False,"provider_authority":False,"side_effects_unlocked":"NONE","content_identity_policy_sha256":sha(vectors[0][9]),"content_identity_request_set_sha256":sha(cb([json.loads(v[10]) for v in vectors])),"receipt_set_sha256":sha(cb(receipts)),"schema_raw_sha256":raw_sha(SCHEMA_REL),"fixture_raw_sha256":raw_sha(FIXTURE_REL),"source_raw_sha256":raw_sha(SOURCE_REL),"predecessor_source_raw_sha256":T08_SOURCE_SHA,"predecessor_fixture_raw_sha256":T08_FIXTURE_SHA,"owner_decision_raw_sha256":OWNER_SHA,"semantic_specification_raw_sha256":SEMANTIC_SHA,"authority_decision_integration_commit":AUTHORITY_COMMIT,"implementation_authority_consumption_state":"PENDING_EXACT_INTEGRATED_FULL_GATE","content_sha256":"0"*64}
    without=dict(receipt); without.pop("content_sha256"); receipt["content_sha256"]=domain_sha(PACK_DOMAIN,without); require(set(receipt)==set(TSV_FIELDS),"E_TSV_FIELDS","closed"); return "".join(f"{k}\t{str(receipt[k]).lower() if type(receipt[k]) is bool else receipt[k]}\n" for k in TSV_FIELDS)
def self_test() -> str:
    checks=("duplicate_json_rejected","float_json_rejected","nonfinite_json_rejected","trailing_json_rejected","mode_first","production_rejected","unknown_mode_rejected","predecessor_once","policy_closed_world","request_closed_world","five_derived_bindings","track_from_t08_only","validation_from_t08_only","schema_closed_84","source_capability_free","default_deny")
    evaluate(); return "".join(f"self_test_{name}\tpass\n" for name in checks)
def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--self-test",action="store_true"); args=parser.parse_args()
    try: sys.stdout.write(self_test() if args.self_test else evaluate()); return 0
    except (CheckError,OSError,UnicodeError,ValueError,TypeError,KeyError,AssertionError,StopIteration) as error: print(f"check_error\t{error}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
