#!/usr/bin/env python3
"""Independent adversarial checker for the public isolated-lab T12 verifier."""
from __future__ import annotations
import argparse, ast, copy, hashlib, importlib.util, json, sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, NoReturn

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SOURCE = "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_synthetic_exact_t11_receipt_track_validation_owner_epoch_and_decision_recheck_owner_epoch_verifier_isolated_lab_v1.py"
T11_CHECKER = "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_synthetic_exact_t10_receipt_track_validation_reference_time_decision_recheck_reference_time_and_maximum_clock_skew_seconds_verifier_isolated_lab_v1_pack.py"
OWNER = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
SEMANTIC = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
DOMAIN = "AB_TRACK_B_T12_OWNER_TOCTOU_ISOLATED_LAB_PACK_RECEIPT_V1"

class CheckError(ValueError): pass
def require(ok: bool, code: str, detail: str) -> None:
    if not ok: raise CheckError(f"{code}: {detail}")
def cb(v: Any) -> bytes: return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def path(rel: str) -> Path:
    p=ROOT.joinpath(*rel.split("/")); r=p.resolve(strict=True); require(ROOT in r.parents and p.is_file() and not p.is_symlink(),"E_PATH",rel); return p
def load(rel: str) -> dict[str,Any]: return json.loads(path(rel).read_text())
def module(rel: str, name: str) -> ModuleType:
    p=path(rel); spec=importlib.util.spec_from_file_location(name,p); require(spec is not None and spec.loader is not None,"E_IMPORT",rel)
    inserted=str(p.parent) not in sys.path
    if inserted: sys.path.insert(0,str(p.parent))
    try:
        m=importlib.util.module_from_spec(spec); sys.modules[name]=m; spec.loader.exec_module(m); return m
    finally:
        if inserted: sys.path.remove(str(p.parent))

def vectors(subject: ModuleType) -> tuple[list[tuple[Any,...]], list[dict[str,Any]]]:
    t11c=module(T11_CHECKER,"_t11_checker_for_t12"); t11=subject.predecessor
    base, profiles, count=t11c.build_vectors(t11); require(count==2 and len(base)==2,"E_T11_VECTORS","two predecessor tracks")
    policy=subject.known_answer_owner_toctou_policy_bytes(); out=[]
    for vector, profile in zip(base, profiles, strict=True):
        require(len(vector)==16 and vector[-1]==subject.SYNTHETIC_KAT_MODE,"E_T11_TOPOLOGY","16 inputs")
        request=subject.known_answer_owner_toctou_request_bytes(profile["track_id"])
        out.append((*vector[:-1],policy,request,subject.SYNTHETIC_KAT_MODE))
    return out,profiles

def mutate(raw: bytes, op: Callable[[dict[str,Any]],None]) -> bytes:
    value=json.loads(raw); op(value); return cb(value)
def rejected(subject: ModuleType, vector: tuple[Any,...], outer: str, detail: str|None=None) -> None:
    try: subject.review_owner_toctou(*vector)
    except subject.OwnerToctouReviewError as error:
        require(error.code==outer,"E_REJECTION_CODE",f"{error.code} != {outer}")
        if detail is not None: require(error.detail_code==detail,"E_DETAIL_CODE",f"{error.detail_code} != {detail}")
    else: raise CheckError("E_ACCEPTED_MUTATION")

def validate_receipt(subject: ModuleType, receipt: dict[str,Any], track: str) -> None:
    expected_hash={"MANAGED_SPANNER_CLOUD_KMS":"63f0c26f10f42c923b55c4e651c001f7c38c42d9e25d7db772b4abbeadbe2ed8","SELF_HOSTED_ETCD_OPENBAO":"ce5af4f0ada753ed9a526909d071e5cb14959a6183f9169e67854d9ebcc4aee1"}[track]
    require(receipt["track_id"]==track and receipt["predecessor_receipt_content_sha256"]==expected_hash,"E_BINDING","receipt/track")
    require(receipt["public_input_count"]==18 and receipt["binding_policy_match_dimension_count"]==4 and receipt["binding_request_field_count"]==2,"E_TOPOLOGY","counts")
    require(receipt["validation_owner_epoch"]==receipt["decision_recheck_owner_epoch"],"E_EPOCH_EQUALITY","equal")
    require(receipt["isolated_lab_candidate_surface_component_total"]==10 and receipt["t12_owner_toctou_implemented"] is True and receipt["t13_authorized"] is False,"E_BOUNDARY","T12 only")
    require(receipt["implementation_authority_single_use_consumed"] is True and receipt["runtime_authority"] is False and receipt["provider_authority"] is False and receipt["production_admissible"] is False,"E_AUTHORITY","closed")
    copied=dict(receipt); observed=copied.pop("content_sha256")
    require(observed==sha(subject.RECEIPT_HASH_DOMAIN.encode()+b"\0"+cb(copied)),"E_RECEIPT_HASH","domain hash")

def directed(subject: ModuleType, valid: tuple[Any,...]) -> int:
    count=0
    def check(v: tuple[Any,...], outer: str, detail: str|None=None) -> None:
        nonlocal count; rejected(subject,v,outer,detail); count+=1
    for mode,code in (("PRODUCTION","E_OWNER_TOCTOU_PRODUCTION_MODE_NOT_AUTHORIZED"),("UNKNOWN","E_OWNER_TOCTOU_MODE_UNKNOWN"),(True,"E_OWNER_TOCTOU_MODE_UNKNOWN")):
        v=list(valid); v[-1]=mode; check(tuple(v),code)
    calls=0
    original=subject.predecessor.review_clock_skew
    def forbidden_predecessor(*args: Any,**kwargs: Any) -> Any:
        nonlocal calls; calls+=1; raise AssertionError("predecessor observed before mode rejection")
    subject.predecessor.review_clock_skew=forbidden_predecessor
    try:
        check(tuple([object() for _ in valid[:-1]]+["PRODUCTION"]),"E_OWNER_TOCTOU_PRODUCTION_MODE_NOT_AUTHORIZED")
    finally: subject.predecessor.review_clock_skew=original
    require(calls==0,"E_MODE_PREOBSERVATION","predecessor called")
    policy_i=-3; request_i=-2
    mutations=[
      (policy_i,lambda x:x.update(schema="drift"),"E_OWNER_TOCTOU_POLICY_REJECTED","E_OWNER_TOCTOU_POLICY_SCHEMA"),
      (policy_i,lambda x:x["profiles"].reverse(),"E_OWNER_TOCTOU_POLICY_REJECTED","E_OWNER_TOCTOU_PROFILE_EXACT"),
      (policy_i,lambda x:x.update(reject_on_zero_matches=False),"E_OWNER_TOCTOU_POLICY_REJECTED","E_OWNER_TOCTOU_POLICY_AMBIGUITY"),
      (policy_i,lambda x:x["profiles"][0].update(validation_owner_epoch=42),"E_OWNER_TOCTOU_POLICY_REJECTED","E_OWNER_TOCTOU_PROFILE_EXACT"),
      (policy_i,lambda x:x["profiles"][0].update(extra=1),"E_OWNER_TOCTOU_POLICY_REJECTED","E_OWNER_TOCTOU_PROFILE_FIELDS"),
      (request_i,lambda x:x.update(validation_owner_epoch=-1),subject.TARGET_PRODUCTION_FAILURE_CODE,"E_VALIDATION_OWNER_EPOCH_RANGE"),
      (request_i,lambda x:x.update(validation_owner_epoch=True),subject.TARGET_PRODUCTION_FAILURE_CODE,"E_VALIDATION_OWNER_EPOCH_TYPE"),
      (request_i,lambda x:x.update(decision_recheck_owner_epoch=42),subject.TARGET_PRODUCTION_FAILURE_CODE,"E_OWNER_TOCTOU_EXACT_MATCH"),
      (request_i,lambda x:x.update(extra=1),subject.TARGET_PRODUCTION_FAILURE_CODE,"E_OWNER_TOCTOU_REQUEST_FIELDS"),
    ]
    for index,op,outer,detail in mutations:
        v=list(valid); v[index]=mutate(v[index],op); check(tuple(v),outer,detail)
    for raw,outer in ((b"{}","E_OWNER_TOCTOU_POLICY_REJECTED"),(b"{}",subject.TARGET_PRODUCTION_FAILURE_CODE),(b'{"validation_owner_epoch":41,"validation_owner_epoch":41,"decision_recheck_owner_epoch":41}',subject.TARGET_PRODUCTION_FAILURE_CODE),(b'{"decision_recheck_owner_epoch":41,"validation_owner_epoch":41} ',subject.TARGET_PRODUCTION_FAILURE_CODE)):
        v=list(valid); v[policy_i if count==13 else request_i]=raw; check(tuple(v),outer)
    v=list(valid); v[policy_i]=b"{}"; v[request_i]=b"{}"; check(tuple(v),"E_OWNER_TOCTOU_POLICY_REJECTED")
    original=subject.predecessor.review_clock_skew
    calls=0
    def wrapped(*args: Any,**kwargs: Any) -> Any:
        nonlocal calls; calls+=1; return original(*args,**kwargs)
    subject.predecessor.review_clock_skew=wrapped
    try: subject.review_owner_toctou(*valid)
    finally: subject.predecessor.review_clock_skew=original
    require(calls==1,"E_PREDECESSOR_CALL_COUNT",str(calls)); count+=1
    return count

def source_guards() -> int:
    tree=ast.parse(path(SOURCE).read_text()); imports=set()
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): imports.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node,ast.ImportFrom) and node.module: imports.add(node.module.split('.')[0])
    allowed={"__future__","hashlib","json","dataclasses","typing","biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_synthetic_exact_t10_receipt_track_validation_reference_time_decision_recheck_reference_time_and_maximum_clock_skew_seconds_verifier_isolated_lab_v1"}
    require(imports<=allowed,"E_SOURCE_IMPORTS",repr(imports-allowed))
    text=path(SOURCE).read_text();
    for token in ("socket","requests","urllib","subprocess","time.time","datetime","os.environ","open("): require(token not in text,"E_SOURCE_CAPABILITY",token)
    return 8

def evaluate() -> str:
    subject=module(SOURCE,"_t12_subject"); valid,profiles=vectors(subject); receipts=[]
    for vector,profile in zip(valid,profiles,strict=True):
        receipt=subject.review_owner_toctou(*vector); validate_receipt(subject,receipt,profile["track_id"]); receipts.append(receipt)
    negatives=directed(subject,valid[0]); guards=source_guards(); owner=load(OWNER); semantic=load(SEMANTIC)
    require(owner["boundary"]["t12_implemented"] is False and owner["state_machine"]["future_successor_integrated_full_consumes_authority"] is True,"E_OWNER_AUTHORITY","active")
    t12=next(x for x in semantic["threat_cases"] if x["case_id"]=="T12")
    require(t12["threat_class"]=="OWNER_TOCTOU" and t12["expected_reason_code"]==subject.TARGET_PRODUCTION_FAILURE_CODE,"E_SEMANTIC","T12")
    pack={"schema":"agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.owner_toctou_isolated_lab_v1_pack.receipt.v0","status":"APPROVE_T12_OWNER_TOCTOU_SYNTHETIC_EXACT_VERIFIER","valid_case_count":2,"directed_negative_test_count":negatives,"source_ast_guard_count":guards,"public_input_count":18,"profile_count":2,"request_field_count":2,"policy_match_dimension_count":4,"predecessor_review_count_per_case":1,"isolated_lab_candidate_surface_component_total":10,"production_ingestion_controls_implemented":0,"runtime_threats_exercised":0,"runtime_prerequisites_satisfied":0,"real_evidence_items_present":0,"runtime_authority":False,"provider_authority":False,"t12_implemented":True,"t13_authorized":False,"managed_receipt_content_sha256":receipts[0]["content_sha256"],"self_hosted_receipt_content_sha256":receipts[1]["content_sha256"],"owner_raw_sha256":sha(path(OWNER).read_bytes()),"semantic_raw_sha256":sha(path(SEMANTIC).read_bytes()),"source_raw_sha256":sha(path(SOURCE).read_bytes()),"content_sha256":"0"*64}
    copied=dict(pack); del copied["content_sha256"]; pack["content_sha256"]=sha(DOMAIN.encode()+b"\0"+cb(copied))
    return "".join(f"{k}\t{json.dumps(v,separators=(',',':')) if isinstance(v,(bool,list,dict)) else v}\n" for k,v in pack.items())

def main() -> int:
    args=argparse.ArgumentParser(); args.add_argument("--self-test",action="store_true"); ns=args.parse_args()
    try:
        output=evaluate()
        if ns.self_test: sys.stdout.write("self_test_contract\tpass\nself_test_mutations\tpass\nself_test_boundary\tpass\n")
        else: sys.stdout.write(output)
        return 0
    except Exception as error: print(f"check_error\t{error}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
