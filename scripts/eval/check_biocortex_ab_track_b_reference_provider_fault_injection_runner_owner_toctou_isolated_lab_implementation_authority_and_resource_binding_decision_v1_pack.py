#!/usr/bin/env python3
"""Independent checker for the T12 owner-TOCTOU authority decision."""

from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, sys
from pathlib import Path
from typing import Any, Callable

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
REVIEWER_REL="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py"
OWNER_REL="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
SEMANTIC_REL="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
T11_REL="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_synthetic_exact_t10_receipt_track_validation_reference_time_decision_recheck_reference_time_and_maximum_clock_skew_seconds_verifier_isolated_lab_v1_pack_v0.json"
class CheckError(ValueError): pass
def req(ok:bool,code:str)->None:
    if not ok: raise CheckError(code)
def load(rel:str)->dict[str,Any]: return json.loads((ROOT/rel).read_text("utf-8"))
def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def module():
    p=ROOT/REVIEWER_REL;s=importlib.util.spec_from_file_location("_t12_auth",p);req(s is not None and s.loader is not None,"E_IMPORT");m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def reject(m:Any,owner:dict[str,Any],semantic:dict[str,Any],t11:dict[str,Any])->None:
    try:m.validate(owner,semantic,t11)
    except Exception:return
    raise CheckError("E_MUTATION_ACCEPTED")
def directed(m:Any,owner:dict[str,Any],semantic:dict[str,Any],t11:dict[str,Any])->int:
    ops:list[Callable[[dict[str,Any]],None]]=[
      lambda x:x.__setitem__("decision","ALLOW"),
      lambda x:x.__setitem__("next_unit","DRIFT"),
      lambda x:x["owner_implementation_actor"].__setitem__("actor_id","other"),
      lambda x:x["predecessor"].__setitem__("t11_implemented",False),
      lambda x:x["authorized_component_contract"]["input_topology"].__setitem__("public_input_count",17),
      lambda x:x["authorized_component_contract"]["input_topology"].__setitem__("review_order",list(reversed(x["authorized_component_contract"]["input_topology"]["review_order"]))),
      lambda x:x["authorized_component_contract"]["owner_epoch_binding"].__setitem__("profile_order",list(reversed(x["authorized_component_contract"]["owner_epoch_binding"]["profile_order"]))),
      lambda x:x["authorized_component_contract"]["owner_epoch_binding"]["profiles"][0].__setitem__("decision_recheck_owner_epoch",42),
      lambda x:x["authorized_component_contract"]["owner_epoch_binding"]["profiles"][1].__setitem__("validation_owner_epoch",-1),
      lambda x:x["authorized_component_contract"]["owner_epoch_binding"]["profiles"][0].__setitem__("validation_owner_epoch",True),
      lambda x:x["authorized_component_contract"]["owner_epoch_binding"]["profiles"][0].__setitem__("t11_receipt_content_sha256","0"*64),
      lambda x:x["authorized_component_contract"]["owner_epoch_binding"]["profiles"].reverse(),
      lambda x:x["implementation_authority"].__setitem__("current_state","CONSUMED"),
      lambda x:x["implementation_authority"].__setitem__("non_transitive",False),
      lambda x:x["implementation_authority"].__setitem__("forbidden_operations",[]),
      lambda x:x["state_machine"].__setitem__("decision_full_gate_consumes_new_authority",True),
      lambda x:x["boundary"].__setitem__("t12_implemented",True),
      lambda x:x["boundary"].__setitem__("runtime_authority",True),
      lambda x:x["resource_binding"].__setitem__("network",True),
      lambda x:x["resource_binding"].__setitem__("max_predecessor_review_calls",2),
    ]
    for op in ops:
        v=copy.deepcopy(owner);op(v);reject(m,v,semantic,t11)
    bad=copy.deepcopy(semantic);next(x for x in bad["threat_cases"] if x["case_id"]=="T12")["threat_class"]="OTHER";reject(m,owner,bad,t11)
    bad=copy.deepcopy(t11);bad["boundary"]["t11_clock_skew_implemented_after_integrated_full"]=False;reject(m,owner,semantic,bad)
    return len(ops)+2
def evaluate()->str:
    m=module();owner,semantic,t11=map(load,(OWNER_REL,SEMANTIC_REL,T11_REL));m.validate(owner,semantic,t11);neg=directed(m,owner,semantic,t11)
    receipt={"schema":"agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.owner_toctou_authority_decision.check.v0","status":"APPROVE_T12_OWNER_TOCTOU_AUTHORITY_DECISION","reviewer_stdout_line_count":19,"directed_negative_test_count":neg,"public_input_count":18,"profile_count":2,"request_field_count":2,"policy_match_dimension_count":4,"t12_implemented":False,"authority_consumed":False,"runtime_authority":False,"provider_authority":False,"owner_raw_sha256":sha((ROOT/OWNER_REL).read_bytes()),"reviewer_raw_sha256":sha((ROOT/REVIEWER_REL).read_bytes()),"semantic_raw_sha256":sha((ROOT/SEMANTIC_REL).read_bytes()),"t11_manifest_raw_sha256":sha((ROOT/T11_REL).read_bytes()),"content_sha256":"0"*64}
    w=dict(receipt);w.pop("content_sha256");receipt["content_sha256"]=sha(b"AB_TRACK_B_T12_OWNER_TOCTOU_AUTHORITY_CHECK_V1\0"+json.dumps(w,sort_keys=True,separators=(",",":")).encode())
    return "".join(f"{k}\t{str(v).lower() if type(v) is bool else v}\n" for k,v in receipt.items())
def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--self-test",action="store_true");a=p.parse_args()
    try:
      if a.self_test:
        evaluate();sys.stdout.write("self_test_contract\tpass\nself_test_mutations\tpass\nself_test_boundary\tpass\n")
      else:sys.stdout.write(evaluate())
      return 0
    except Exception as e:print(f"check_error\t{e}",file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
