#!/usr/bin/env python3
"""Independent contract/adversarial checker for the isolated-lab T10 verifier."""

from __future__ import annotations

import argparse
import ast
import copy
import dataclasses
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Mapping, NoReturn

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SOURCE_REL = "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_synthetic_exact_t09_receipt_track_observed_at_validation_checked_at_decision_recheck_at_expires_at_and_max_age_seconds_verifier_isolated_lab_v1.py"
FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_synthetic_exact_t09_receipt_track_observed_at_validation_checked_at_decision_recheck_at_expires_at_and_max_age_seconds_verifier_isolated_lab_v1_pack_synthetic_v0.json"
SCHEMA_REL = "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-freshness-synthetic-exact-t09-receipt-track-observed-at-validation-checked-at-decision-recheck-at-expires-at-and-max-age-seconds-verifier-isolated-lab-v1.schema.json"
T09_FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1_pack_synthetic_v0.json"
T08_FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1_pack_synthetic_v0.json"
T07_FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_synthetic_exact_packet_profile_provider_or_lab_profile_namespace_configuration_sha256_and_non_substitutable_track_verifier_isolated_lab_v1_pack_synthetic_v0.json"
T06_FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack_synthetic_v0.json"
T05_FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack_synthetic_v0.json"
OWNER_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
AUTHORITY_GATE_REL = "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-freshness-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh"
SEMANTIC_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"

DATE = "2026-07-19"
SYNTHETIC_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"
POLICY_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.freshness_synthetic_policy_isolated_lab_kat.v1"
RECEIPT_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.freshness_synthetic_exact_t09_receipt_track_observed_at_validation_checked_at_decision_recheck_at_expires_at_and_max_age_seconds_verifier_isolated_lab_v1.receipt.v0"
FIXTURE_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.freshness_synthetic_exact_t09_receipt_track_observed_at_validation_checked_at_decision_recheck_at_expires_at_and_max_age_seconds_verifier_isolated_lab_v1_pack.synthetic.v0"
PACK_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.freshness_synthetic_exact_t09_receipt_track_observed_at_validation_checked_at_decision_recheck_at_expires_at_and_max_age_seconds_verifier_isolated_lab_v1_pack.receipt.v0"
STATUS = "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_FRESHNESS_SYNTHETIC_EXACT_T09_RECEIPT_TRACK_OBSERVED_AT_VALIDATION_CHECKED_AT_DECISION_RECHECK_AT_EXPIRES_AT_AND_MAX_AGE_SECONDS_VERIFIED_ISOLATED_LAB_COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
AUTHORIZED_UNIT = "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_FRESHNESS_SYNTHETIC_EXACT_T09_RECEIPT_TRACK_OBSERVED_AT_VALIDATION_CHECKED_AT_DECISION_RECHECK_AT_EXPIRES_AT_AND_MAX_AGE_SECONDS_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
DECISION = "T10_SYNTHETIC_EXACT_FRESHNESS_COMPONENT_CONFORMANT_PRODUCTION_PATH_FAIL_CLOSED"
COMPONENT_STATE = "BOUND_SYNTHETIC_STALENESS_LABELS_TO_EXACT_T09_RECEIPT_CHAIN_ONLY"
FRESHNESS_RELATION = "OBSERVED_AT_LE_VALIDATION_CHECKED_AT_LE_DECISION_RECHECK_AT_LT_EXPIRES_AT_AND_EACH_CHECK_AGE_LE_MAX_AGE"
PACK_DOMAIN = "AB_TRACK_B_T10_FRESHNESS_ISOLATED_LAB_PACK_RECEIPT_V1"
RECEIPT_DOMAIN = "AB_TRACK_B_T10_FRESHNESS_ISOLATED_LAB_KAT_RECEIPT_V1"
MATCHING = "EXACT_ALL_FIELDS_AND_SIGNED_INT64_VALUES_EQUAL"
DEFAULT = "REJECTED_FAIL_CLOSED"
REQUEST_FIELDS = ("observed_at_unix_seconds", "validation_checked_at_unix_seconds", "decision_recheck_at_unix_seconds", "expires_at_unix_seconds", "max_age_seconds")
MATCH_FIELDS = ("t09_receipt_content_sha256", "track_id", *REQUEST_FIELDS)
POLICY_KEYS = ("default_disposition", "matching_profile", "profiles", "reject_on_multiple_matches", "reject_on_zero_matches", "schema", "schema_version")
AUTHORITY_COMMIT = "7873f24dddb6ed96e9ae9cb0358f6c5ff030a00d"
AUTHORITY_SOURCE = "7f35c89329cc423c65a12176e8c10e3e9815782b"
OWNER_SHA = "c4344cec98344f717fd78253e2dd70c04b9cbeb6895cb3a58652e4f6260bcfa1"
AUTHORITY_GATE_SHA = "9979e715cb7f5b4c22c9a5b2abf9046300f13841a23e791ee869ec7dd39bb932"
T09_SOURCE_SHA = "ff5aae17b727b70430235294d5ec8101fb44f88bde743b05fe2ea12850f4e68e"
T09_FIXTURE_SHA = "5575b982e0e0da0130ff2dfcba2f3fc3c7198644fe2db960432d3b8ae31fe5e4"
SEMANTIC_SHA = "3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6"

PROFILES = (
    {"track_id":"MANAGED_SPANNER_CLOUD_KMS","t09_receipt_content_sha256":"707017354e9943d9049acf546124e5c2115b49258420fa83c3e9c1e681024953","observed_at_unix_seconds":2000000000,"validation_checked_at_unix_seconds":2000000060,"decision_recheck_at_unix_seconds":2000000120,"expires_at_unix_seconds":2000000300,"max_age_seconds":300,"case_id":"VALID_MANAGED_FRESHNESS_V1","predecessor_case_id":"VALID_MANAGED_CONTENT_IDENTITY_V1","receipt_sha256":"620dc08e2f8b41cac5bf0944b50ecc9d2435e59fb5c01e68544270ca94d03714"},
    {"track_id":"SELF_HOSTED_ETCD_OPENBAO","t09_receipt_content_sha256":"e7fb01f915b6436f2503be78cac1957d93197e8e1dd4ca336a711c5ec08e7ed6","observed_at_unix_seconds":2100000000,"validation_checked_at_unix_seconds":2100000060,"decision_recheck_at_unix_seconds":2100000120,"expires_at_unix_seconds":2100000300,"max_age_seconds":300,"case_id":"VALID_SELF_HOSTED_FRESHNESS_V1","predecessor_case_id":"VALID_SELF_HOSTED_CONTENT_IDENTITY_V1","receipt_sha256":"16c7b9228bf36329723376aba4f273f9356759037b4f31ca5a4adbf810bee14d"},
)


class CheckError(ValueError): pass
def require(ok: bool, code: str, detail: str) -> None:
    if not ok: raise CheckError(f"{code}: {detail}")
def cb(value: Any) -> bytes: return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def domain_sha(domain: str, value: Any) -> str: return sha(domain.encode("ascii")+b"\x00"+cb(value))
def path(relative: str) -> Path:
    require(type(relative) is str and relative and not relative.startswith("/") and all(x not in ("", ".", "..") for x in relative.split("/")),"E_PATH",relative)
    candidate=ROOT.joinpath(*relative.split("/")); resolved=candidate.resolve(strict=True)
    require(ROOT in resolved.parents and candidate.is_file() and not candidate.is_symlink(),"E_PATH_ESCAPE",relative); return candidate
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
    source=path(SOURCE_REL); spec=importlib.util.spec_from_file_location("_t10_subject",source); require(spec is not None and spec.loader is not None,"E_IMPORT",SOURCE_REL)
    inserted=str(source.parent) not in sys.path
    if inserted: sys.path.insert(0,str(source.parent))
    try:
        module=importlib.util.module_from_spec(spec); sys.modules["_t10_subject"]=module; spec.loader.exec_module(module); return module
    finally:
        if inserted: sys.path.remove(str(source.parent))
def expected_policy() -> dict[str,Any]:
    return {"default_disposition":DEFAULT,"matching_profile":MATCHING,"profiles":[{k:p[k] for k in MATCH_FIELDS} for p in PROFILES],"reject_on_multiple_matches":True,"reject_on_zero_matches":True,"schema":POLICY_SCHEMA,"schema_version":1}
def mutate(value: Mapping[str,Any], operation: Callable[[dict[str,Any]],None]) -> bytes:
    result=copy.deepcopy(value); operation(result); return cb(result)


def build_vectors(module: ModuleType) -> tuple[list[tuple[Any,...]],list[dict[str,Any]],int]:
    fixture,t09,t08,t07,t06,t05=map(load_json,(FIXTURE_REL,T09_FIXTURE_REL,T08_FIXTURE_REL,T07_FIXTURE_REL,T06_FIXTURE_REL,T05_FIXTURE_REL))
    require(fixture["schema"]==FIXTURE_SCHEMA and fixture["public_only"] is True and fixture["contains_private_or_seed_material"] is False,"E_FIXTURE_HEADER","truth")
    bindings=fixture["source_bindings"]
    require(bindings["authority_decision_integration_commit"]==AUTHORITY_COMMIT and bindings["authority_decision_source_commit"]==AUTHORITY_SOURCE,"E_FIXTURE_AUTHORITY","drift")
    require(bindings["owner_decision_sha256"]==OWNER_SHA==raw_sha(OWNER_REL),"E_OWNER_HASH","drift")
    require(bindings["authority_decision_gate_sha256"]==AUTHORITY_GATE_SHA==raw_sha(AUTHORITY_GATE_REL),"E_AUTHORITY_GATE_HASH","drift")
    require(raw_sha(T09_FIXTURE_REL)==T09_FIXTURE_SHA and raw_sha(SEMANTIC_REL)==SEMANTIC_SHA,"E_DEPENDENCY_HASH","drift")
    require(fixture["separately_injected_synthetic_freshness_policy"]==expected_policy(),"E_FIXTURE_POLICY","drift")
    cases=[{x["case_id"]:x for x in item["valid_cases"]} for item in (t09,t08,t07,t06,t05)]
    real=module.predecessor.review_content_identity_and_quarantine_custody; calls=[]; vectors=[]; receipts=[]
    def counted(*args:Any,**kwargs:Any)->Any: calls.append(args); return real(*args,**kwargs)
    module.predecessor.review_content_identity_and_quarantine_custody=counted
    try:
        for index,p in enumerate(PROFILES):
            x9=cases[0][p["predecessor_case_id"]]; x8=cases[1][x9["predecessor_case_id"]]; x7=cases[2][x8["predecessor_case_id"]]; x6=cases[3][x7["predecessor_case_id"]]; x5=cases[4][x6["predecessor_case_id"]]
            request={k:p[k] for k in REQUEST_FIELDS}
            vector=(x5["frame_utf8"].encode(),cb(x5["detached_authentication_bundle"]),cb(t05["separately_injected_synthetic_trust_policy"]),cb(t06["separately_injected_synthetic_signer_authorization_policy"]),cb(x6["detached_authorization_request"]),cb(t07["separately_injected_synthetic_track_profile_binding_policy"]),cb(x7["detached_track_profile_binding_request"]),cb(t08["separately_injected_synthetic_end_to_end_subject_binding_policy"]),cb(x8["detached_end_to_end_subject_binding_request"]),cb(t09["separately_injected_synthetic_content_identity_and_quarantine_custody_policy"]),cb(x9["detached_content_identity_and_quarantine_custody_request"]),cb(expected_policy()),cb(request),SYNTHETIC_MODE)
            before=len(calls); receipt=module.review_freshness(*vector); require(len(calls)==before+1,"E_REAL_CALL_COUNT",p["track_id"])
            validate_receipt(receipt,p,vector[11],vector[12]); require(receipt["content_sha256"]==p["receipt_sha256"],"E_RECEIPT_HASH",p["track_id"])
            require(fixture["valid_cases"][index]["detached_freshness_request"]==request and fixture["expected_receipt_content_sha256"][p["track_id"]]==p["receipt_sha256"],"E_FIXTURE_CASE",p["track_id"])
            vectors.append(vector); receipts.append(receipt)
    finally: module.predecessor.review_content_identity_and_quarantine_custody=real
    require(len(calls)==2,"E_REAL_CALL_TOTAL",str(len(calls))); return vectors,receipts,len(calls)


def validate_receipt(receipt: Mapping[str,Any],p: Mapping[str,Any],policy_raw: bytes,request_raw: bytes) -> None:
    schema=load_json(SCHEMA_REL); keys=tuple(schema["required"]); require(set(keys)==set(schema["propertyNames"]["enum"])==set(receipt) and len(keys)==90,"E_RECEIPT_KEYS",str(len(receipt)))
    expected={"authorized_unit":AUTHORIZED_UNIT,"binding_match_count":1,"binding_policy_match_dimension_count":7,"binding_policy_match_fields":list(MATCH_FIELDS),"binding_profile_count":2,"binding_request_field_count":5,"binding_request_fields":list(REQUEST_FIELDS),"component_state":COMPONENT_STATE,"decision_recheck_at_unix_seconds":p["decision_recheck_at_unix_seconds"],"default_disposition":DEFAULT,"downstream_gate_count":4,"execution_mode":SYNTHETIC_MODE,"expires_at_unix_seconds":p["expires_at_unix_seconds"],"freshness_arithmetic_relation":FRESHNESS_RELATION,"freshness_policy_sha256":sha(policy_raw),"freshness_request_sha256":sha(request_raw),"isolated_lab_candidate_surface_component_total":8,"isolated_lab_candidate_surface_components_implemented":8,"isolated_lab_candidate_surface_components_locally_kat_exercised":8,"local_threat_specifications_covered":10,"local_threat_specifications_covered_ids":[f"T{x:02d}" for x in range(1,11)],"matching_profile":MATCHING,"max_age_seconds":p["max_age_seconds"],"observed_at_unix_seconds":p["observed_at_unix_seconds"],"predecessor_receipt_content_sha256":p["t09_receipt_content_sha256"],"predecessor_receipt_schema":RECEIPT_SCHEMA.replace("freshness_synthetic_exact_t09_receipt_track_observed_at_validation_checked_at_decision_recheck_at_expires_at_and_max_age_seconds_verifier_isolated_lab_v1.receipt.v0","content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1.receipt.v0"),"predecessor_review_count":1,"production_ingestion_control_count":14,"production_threat_specification_count":20,"public_input_count":14,"runtime_prerequisite_count":16,"schema":RECEIPT_SCHEMA,"schema_version":1,"side_effects_unlocked":"NONE","status":STATUS,"target_production_control":"TRUSTED_TIME_FRESHNESS","target_production_failure_code":"E_PRODUCTION_FRESHNESS_FAILED","track_id":p["track_id"],"track_identity_source":"T09_PREDECESSOR_RECEIPT_ONLY","validation_checked_at_unix_seconds":p["validation_checked_at_unix_seconds"]}
    for key,value in expected.items(): require(type(receipt[key]) is type(value) and receipt[key]==value,"E_RECEIPT_VALUE",key)
    true_fields=("decision_recheck_required","decision_recheck_staleness_within_max_age","freshness_policy_separately_injected","freshness_request_detached","freshness_request_observed_after_policy","local_t09_specification_exercised","local_t10_specification_exercised","predecessor_receipt_and_track_non_substitutable","reject_on_multiple_matches","reject_on_zero_matches","stale_at_decision_recheck_rejected","stale_at_validation_rejected","synthetic_fixture","t09_content_identity_and_quarantine_custody_implemented","t10_freshness_implemented","validation_checked_staleness_within_max_age")
    zero_fields=("downstream_gates_authorized","production_ingestion_controls_implemented","production_ingestion_controls_runtime_exercised","production_threat_specifications_runtime_exercised","production_validated_evidence_items","real_evidence_items_present","runtime_evidence_accepted","runtime_prerequisites_satisfied")
    false_fields=set(receipt)-set(expected)-set(true_fields)-set(zero_fields)-{"content_sha256"}
    for key in true_fields: require(receipt[key] is True,"E_RECEIPT_TRUE",key)
    for key in zero_fields: require(type(receipt[key]) is int and receipt[key]==0,"E_RECEIPT_ZERO",key)
    for key in false_fields: require(receipt[key] is False,"E_RECEIPT_FALSE",key)
    without=dict(receipt); observed=without.pop("content_sha256"); require(observed==sha(RECEIPT_DOMAIN.encode()+b"\x00"+cb(without)),"E_RECEIPT_CONTENT_HASH",p["track_id"])


def expect(module: ModuleType,vector: tuple[Any,...],*,code: str|None=None,detail: str|None=None) -> None:
    try: module.review_freshness(*vector)
    except module.FreshnessReviewError as error:
        if code: require(error.code==code,"E_REJECT_CODE",error.code)
        if detail: require(error.detail_code==detail,"E_REJECT_DETAIL",str(error.detail_code))
    else: raise CheckError("E_MUTATION_ACCEPTED")


def mode_checks(module: ModuleType) -> int:
    count=0
    for mode,code in ((PRODUCTION_MODE,"E_FRESHNESS_PRODUCTION_MODE_NOT_AUTHORIZED"),("UNKNOWN","E_FRESHNESS_MODE_UNKNOWN"),(None,"E_FRESHNESS_MODE_UNKNOWN")):
        expect(module,tuple([object()]*13+[mode]),code=code); count+=1
    class Evil(str):
        def __eq__(self,other:object)->bool: raise AssertionError("observed subclass")
    expect(module,tuple([object()]*13+[Evil(SYNTHETIC_MODE)]),code="E_FRESHNESS_MODE_UNKNOWN"); return count+1


def directed(module: ModuleType,vector: tuple[Any,...]) -> dict[str,int]:
    counts={"policy_json":0,"request_json":0,"policy_closed_world":0,"request_exact_field":0,"arithmetic":0,"predecessor_binding":0,"default_deny":0}
    policy=json.loads(vector[11]); request=json.loads(vector[12])
    bad_json=(b"",b"{} ",b'{"a":1,"a":2}',b'{"x":NaN}',b'{"x":1.0}',b"[]",b"null",b"\xff",b"{}{}",b"{",b'{"x":9223372036854775808}')
    for raw in bad_json:
        changed=list(vector); changed[11]=raw; expect(module,tuple(changed),code="E_FRESHNESS_POLICY_REJECTED"); counts["policy_json"]+=1
        changed=list(vector); changed[12]=raw; expect(module,tuple(changed),code="E_PRODUCTION_FRESHNESS_FAILED"); counts["request_json"]+=1
    for key in POLICY_KEYS:
        changed=list(vector); changed[11]=mutate(policy,lambda x,k=key:x.pop(k)); expect(module,tuple(changed)); counts["policy_closed_world"]+=1
    changed=list(vector); changed[11]=mutate(policy,lambda x:x.__setitem__("extra",False)); expect(module,tuple(changed)); counts["policy_closed_world"]+=1
    for index in range(2):
        for field in MATCH_FIELDS:
            changed=list(vector); changed[11]=mutate(policy,lambda x,i=index,f=field:x["profiles"][i].pop(f)); expect(module,tuple(changed)); counts["policy_closed_world"]+=1
            drift="0"*64 if field=="t09_receipt_content_sha256" else ("DRIFT" if field=="track_id" else policy["profiles"][index][field]+1)
            changed=list(vector); changed[11]=mutate(policy,lambda x,i=index,f=field,v=drift:x["profiles"][i].__setitem__(f,v)); expect(module,tuple(changed)); counts["policy_closed_world"]+=1
    operations=(lambda x:x.__setitem__("profiles",list(reversed(x["profiles"]))),lambda x:x.__setitem__("profiles",[x["profiles"][0]]),lambda x:x.__setitem__("profiles",[x["profiles"][0],x["profiles"][0]]),lambda x:x.__setitem__("default_disposition","ALLOW"),lambda x:x.__setitem__("matching_profile","PREFIX"),lambda x:x.__setitem__("reject_on_zero_matches",False),lambda x:x.__setitem__("reject_on_multiple_matches",False))
    for operation in operations:
        changed=list(vector); changed[11]=mutate(policy,operation); expect(module,tuple(changed)); counts["policy_closed_world"]+=1
    for field in REQUEST_FIELDS:
        changed=list(vector); changed[12]=mutate(request,lambda x,f=field:x.pop(f)); expect(module,tuple(changed)); counts["request_exact_field"]+=1
        for value in (-1,2**63,True,str(request[field]),request[field]+1):
            changed=list(vector); changed[12]=mutate(request,lambda x,f=field,v=value:x.__setitem__(f,v)); expect(module,tuple(changed)); counts["request_exact_field"]+=1
    changed=list(vector); changed[12]=mutate(request,lambda x:x.__setitem__("track_id",PROFILES[0]["track_id"])); expect(module,tuple(changed)); counts["request_exact_field"]+=1
    original=module.PROFILES
    arithmetic=(
        ({"validation_checked_at_unix_seconds":1999999999},"E_FRESHNESS_VALIDATION_BEFORE_OBSERVATION"),
        ({"decision_recheck_at_unix_seconds":2000000059},"E_FRESHNESS_DECISION_BEFORE_VALIDATION"),
        ({"expires_at_unix_seconds":2000000120},"E_FRESHNESS_EXPIRED_AT_DECISION_RECHECK"),
        ({"expires_at_unix_seconds":2000000119},"E_FRESHNESS_EXPIRED_AT_DECISION_RECHECK"),
        ({"max_age_seconds":59},"E_FRESHNESS_STALE_AT_VALIDATION"),
        ({"max_age_seconds":119},"E_FRESHNESS_STALE_AT_DECISION_RECHECK"),
    )
    try:
        for updates,detail in arithmetic:
            profile=dataclasses.replace(original[0],**updates); module.PROFILES=(profile,original[1])
            changed=list(vector); changed[11]=module.known_answer_freshness_policy_bytes(); changed[12]=module.known_answer_freshness_request_bytes(profile.track_id)
            expect(module,tuple(changed),code="E_PRODUCTION_FRESHNESS_FAILED",detail=detail); counts["arithmetic"]+=1
    finally: module.PROFILES=original
    real=module.predecessor.review_content_identity_and_quarantine_custody; baseline=real(*vector[:11],SYNTHETIC_MODE)
    mutations=(("track_id","SELF_HOSTED_ETCD_OPENBAO"),("content_sha256","0"*64),("schema","drift"),("execution_mode","PRODUCTION"),("isolated_lab_candidate_surface_component_total",6),("isolated_lab_candidate_surface_components_implemented",6),("local_t09_specification_exercised",False),("local_t10_specification_exercised",True),("production_admissible",True),("production_quarantine_custody_implemented",True),("provider_authority",True),("runtime_authority",True))
    try:
        for field,value in mutations:
            fake=copy.deepcopy(baseline); fake[field]=value; calls=[]
            def spy(*args:Any,_fake=fake,**kwargs:Any)->Any: calls.append(args); return copy.deepcopy(_fake)
            module.predecessor.review_content_identity_and_quarantine_custody=spy; expect(module,vector); require(len(calls)==1,"E_SPY_CALL_COUNT",field); counts["predecessor_binding"]+=1
    finally: module.predecessor.review_content_identity_and_quarantine_custody=real
    for operation in (lambda x:x.__setitem__("profiles",[]),lambda x:x.__setitem__("profiles",[x["profiles"][0],x["profiles"][0]])):
        changed=list(vector); changed[11]=mutate(policy,operation); expect(module,tuple(changed)); counts["default_deny"]+=1
    return counts


def source_checks() -> int:
    source_text=path(SOURCE_REL).read_text(); tree=ast.parse(source_text)
    imports={alias.name for node in tree.body if isinstance(node,ast.Import) for alias in node.names}|{node.module or "" for node in tree.body if isinstance(node,ast.ImportFrom)}
    require(imports <= {"__future__","hashlib","json","dataclasses","typing","biocortex_ab_track_b_reference_provider_fault_injection_runner_content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1"},"E_SOURCE_IMPORTS",repr(imports))
    public=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="review_freshness"); names=[item.arg for item in public.args.args]
    require(names==["frame","detached_authentication_bundle","separately_injected_synthetic_trust_policy","separately_injected_synthetic_signer_authorization_policy","detached_authorization_request","separately_injected_synthetic_track_profile_binding_policy","detached_track_profile_binding_request","separately_injected_synthetic_end_to_end_subject_binding_policy","detached_end_to_end_subject_binding_request","separately_injected_synthetic_content_identity_and_quarantine_custody_policy","detached_content_identity_and_quarantine_custody_request","separately_injected_synthetic_freshness_policy","detached_freshness_request","mode"],"E_SOURCE_API",repr(names))
    require(isinstance(public.body[1],ast.Expr) and isinstance(public.body[1].value,ast.Call) and isinstance(public.body[1].value.func,ast.Name) and public.body[1].value.func.id=="_reject_mode","E_SOURCE_MODE_FIRST","order")
    calls=[node for node in ast.walk(public) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=="review_content_identity_and_quarantine_custody"]; require(len(calls)==1,"E_SOURCE_PREDECESSOR_CALL",str(len(calls)))
    predecessor_line=calls[0].lineno; policy_line=next(node.lineno for node in ast.walk(public) if isinstance(node,ast.Constant) and node.value=="FRESHNESS_POLICY"); request_line=next(node.lineno for node in ast.walk(public) if isinstance(node,ast.Constant) and node.value=="FRESHNESS_REQUEST")
    require(predecessor_line<policy_line<request_line,"E_SOURCE_OBSERVATION_ORDER",f"{predecessor_line}/{policy_line}/{request_line}")
    forbidden=("requests","urllib","socket","subprocess","open(","Path(","time.","datetime","os.environ","pickle","yaml","get_clock","clock_gettime")
    require(not any(item in source_text for item in forbidden),"E_SOURCE_FORBIDDEN","capability")
    return 16


def fixture_schema_checks() -> int:
    fixture=load_json(FIXTURE_REL); schema=load_json(SCHEMA_REL)
    require(set(fixture)=={"canonical_json_profile","contains_private_or_seed_material","date","execution_mode","expected_receipt_content_sha256","public_only","schema","separately_injected_synthetic_freshness_policy","source_bindings","valid_cases"},"E_FIXTURE_KEYS","closed")
    require(len(fixture["valid_cases"])==2 and len(fixture["expected_receipt_content_sha256"])==2,"E_FIXTURE_COUNT","two")
    require(schema["minProperties"]==schema["maxProperties"]==90 and schema["required"]==schema["propertyNames"]["enum"],"E_SCHEMA_CLOSED","90")
    require(schema["properties"]["t11_clock_skew_implemented"]["const"] is False and schema["properties"]["t12_owner_toctou_implemented"]["const"] is False,"E_SCHEMA_SUCCESSOR_BOUNDARY","closed")
    return 20


TSV_FIELDS=("schema","status","decision","date","component_mode","component_state","positive_track_count","real_predecessor_review_count","public_input_count","public_mode_pre_observation_test_count","policy_json_negative_test_count","request_json_negative_test_count","policy_closed_world_negative_test_count","request_exact_field_negative_test_count","freshness_arithmetic_negative_test_count","predecessor_receipt_binding_negative_test_count","default_deny_negative_test_count","total_directed_negative_test_count","source_ast_guard_count","fixture_schema_guard_count","binding_profile_count","request_field_count","policy_match_dimension_count","isolated_lab_candidate_surface_component_total","isolated_lab_candidate_surface_components_implemented","local_threat_specifications_covered","local_t10_specification_exercised","local_t11_specification_exercised","production_ingestion_control_count","production_ingestion_controls_implemented","production_threat_specification_count","production_threat_specifications_runtime_exercised","runtime_prerequisite_count","runtime_prerequisites_satisfied","real_evidence_items_present","production_validated_evidence_items","runtime_authority","provider_authority","side_effects_unlocked","freshness_policy_sha256","freshness_request_set_sha256","receipt_set_sha256","schema_raw_sha256","fixture_raw_sha256","source_raw_sha256","predecessor_source_raw_sha256","predecessor_fixture_raw_sha256","owner_decision_raw_sha256","authority_gate_raw_sha256","semantic_specification_raw_sha256","authority_decision_integration_commit","authority_state_before_consumption","implementation_authority_consumption_state","content_sha256")


def evaluate() -> str:
    module=load_module(); vectors,receipts,real=build_vectors(module); mode=mode_checks(module); counts=directed(module,vectors[0]); source=source_checks(); fixture=fixture_schema_checks(); total=sum(counts.values())+mode
    receipt={"schema":PACK_SCHEMA,"status":STATUS,"decision":DECISION,"date":DATE,"component_mode":SYNTHETIC_MODE,"component_state":COMPONENT_STATE,"positive_track_count":2,"real_predecessor_review_count":real,"public_input_count":14,"public_mode_pre_observation_test_count":mode,"policy_json_negative_test_count":counts["policy_json"],"request_json_negative_test_count":counts["request_json"],"policy_closed_world_negative_test_count":counts["policy_closed_world"],"request_exact_field_negative_test_count":counts["request_exact_field"],"freshness_arithmetic_negative_test_count":counts["arithmetic"],"predecessor_receipt_binding_negative_test_count":counts["predecessor_binding"],"default_deny_negative_test_count":counts["default_deny"],"total_directed_negative_test_count":total,"source_ast_guard_count":source,"fixture_schema_guard_count":fixture,"binding_profile_count":2,"request_field_count":5,"policy_match_dimension_count":7,"isolated_lab_candidate_surface_component_total":8,"isolated_lab_candidate_surface_components_implemented":8,"local_threat_specifications_covered":10,"local_t10_specification_exercised":True,"local_t11_specification_exercised":False,"production_ingestion_control_count":14,"production_ingestion_controls_implemented":0,"production_threat_specification_count":20,"production_threat_specifications_runtime_exercised":0,"runtime_prerequisite_count":16,"runtime_prerequisites_satisfied":0,"real_evidence_items_present":0,"production_validated_evidence_items":0,"runtime_authority":False,"provider_authority":False,"side_effects_unlocked":"NONE","freshness_policy_sha256":sha(vectors[0][11]),"freshness_request_set_sha256":sha(cb([json.loads(vector[12]) for vector in vectors])),"receipt_set_sha256":sha(cb(receipts)),"schema_raw_sha256":raw_sha(SCHEMA_REL),"fixture_raw_sha256":raw_sha(FIXTURE_REL),"source_raw_sha256":raw_sha(SOURCE_REL),"predecessor_source_raw_sha256":T09_SOURCE_SHA,"predecessor_fixture_raw_sha256":T09_FIXTURE_SHA,"owner_decision_raw_sha256":OWNER_SHA,"authority_gate_raw_sha256":AUTHORITY_GATE_SHA,"semantic_specification_raw_sha256":SEMANTIC_SHA,"authority_decision_integration_commit":AUTHORITY_COMMIT,"authority_state_before_consumption":"AUTHORIZED_T10_FRESHNESS_ISOLATED_LAB_EXACT_UNIT","implementation_authority_consumption_state":"PENDING_EXACT_INTEGRATED_FULL_GATE","content_sha256":"0"*64}
    without=dict(receipt); without.pop("content_sha256"); receipt["content_sha256"]=domain_sha(PACK_DOMAIN,without); require(set(receipt)==set(TSV_FIELDS),"E_TSV_FIELDS","closed")
    return "".join(f"{key}\t{str(receipt[key]).lower() if type(receipt[key]) is bool else receipt[key]}\n" for key in TSV_FIELDS)


def self_test() -> str:
    checks=("duplicate_json_rejected","float_json_rejected","nonfinite_json_rejected","trailing_json_rejected","mode_first","production_rejected","unknown_mode_rejected","predecessor_once","policy_closed_world","request_closed_world","five_integer_fields","validation_staleness","decision_recheck_staleness","schema_closed_90","source_clock_capability_free","default_deny")
    evaluate(); return "".join(f"self_test_{name}\tpass\n" for name in checks)


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--self-test",action="store_true"); args=parser.parse_args()
    try: sys.stdout.write(self_test() if args.self_test else evaluate()); return 0
    except (CheckError,OSError,UnicodeError,ValueError,TypeError,KeyError,AssertionError,StopIteration) as error: print(f"check_error\t{error}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
