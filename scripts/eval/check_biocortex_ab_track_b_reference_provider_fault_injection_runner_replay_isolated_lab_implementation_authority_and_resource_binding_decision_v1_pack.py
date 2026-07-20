#!/usr/bin/env python3
"""Independent mutation checker for the T13 replay authority decision."""
from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, sys
from pathlib import Path
from typing import Any, Callable

ROOT=Path(__file__).resolve().parents[2]
REVIEWER_REL="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py"
DOMAIN="AB_TRACK_B_T13_REPLAY_AUTHORITY_CHECK_V1"
def require(ok:bool,detail:str)->None:
    if not ok: raise ValueError(detail)
def path(rel:str)->Path:
    p=ROOT.joinpath(*rel.split('/')); r=p.resolve(strict=True); require(ROOT in r.parents and p.is_file() and not p.is_symlink(),rel); return p
def sha(rel:str)->str:return hashlib.sha256(path(rel).read_bytes()).hexdigest()
def load_module():
    p=path(REVIEWER_REL); spec=importlib.util.spec_from_file_location("_t13_authority",p); require(spec is not None and spec.loader is not None,"import")
    m=importlib.util.module_from_spec(spec); sys.modules["_t13_authority"]=m; spec.loader.exec_module(m); return m
def rejected(m:Any,owner:dict[str,Any],semantic:dict[str,Any],manifest:dict[str,Any])->None:
    try:m.validate(owner,semantic,manifest)
    except Exception:return
    raise ValueError("mutation accepted")
def evaluate()->str:
    m=load_module(); owner=m.load(m.OWNER_REL); semantic=m.load(m.SEMANTIC_REL); manifest=m.load(m.T12_MANIFEST_REL); base=m.validate(owner,semantic,manifest)
    tests:list[tuple[str,Callable[[dict[str,Any],dict[str,Any],dict[str,Any]],None]]]=[
      ("decision",lambda o,s,p:o.update(decision="NO")),("unit",lambda o,s,p:o.update(next_unit="NO")),("actor",lambda o,s,p:o["owner_implementation_actor"].update(actor_id="other")),
      ("predecessor",lambda o,s,p:o["predecessor"].update(t12_implemented=False)),("count",lambda o,s,p:o["authorized_component_contract"]["input_topology"].update(public_input_count=19)),
      ("order",lambda o,s,p:o["authorized_component_contract"]["input_topology"]["review_order"].reverse()),("request_fields",lambda o,s,p:o["authorized_component_contract"]["replay_binding"]["request_fields"].reverse()),
      ("match_fields",lambda o,s,p:o["authorized_component_contract"]["replay_binding"]["policy_match_fields"].pop()),("profile_fields",lambda o,s,p:o["authorized_component_contract"]["replay_binding"]["profile_fields"].pop()),
      ("profile_order",lambda o,s,p:o["authorized_component_contract"]["replay_binding"]["profiles"].reverse()),("receipt",lambda o,s,p:o["authorized_component_contract"]["replay_binding"]["profiles"][0].update(t12_receipt_content_sha256="0"*64)),
      ("nonce_replay",lambda o,s,p:o["authorized_component_contract"]["replay_binding"]["profiles"][0].update(submitted_issuer_nonce="managed-reserved-0001")),
      ("sequence_replay",lambda o,s,p:o["authorized_component_contract"]["replay_binding"]["profiles"][0].update(submitted_sequence=4100)),
      ("packet_replay",lambda o,s,p:o["authorized_component_contract"]["replay_binding"]["profiles"][0].update(submitted_packet_identity_sha256="fbce175924579ab998990a7438b611cfd419937903d180e930c11058999ccbdc")),
      ("negative_sequence",lambda o,s,p:o["authorized_component_contract"]["replay_binding"]["profiles"][0].update(submitted_sequence=-1)),
      ("boolean_sequence",lambda o,s,p:o["authorized_component_contract"]["replay_binding"]["profiles"][0].update(submitted_sequence=True)),
      ("packet_hash",lambda o,s,p:o["authorized_component_contract"]["replay_binding"]["profiles"][0].update(submitted_packet_identity_sha256="ABC")),
      ("extra_profile",lambda o,s,p:o["authorized_component_contract"]["replay_binding"]["profiles"][0].update(extra=1)),
      ("authority",lambda o,s,p:o["implementation_authority"].update(non_transitive=False)),("forbidden",lambda o,s,p:o["implementation_authority"]["forbidden_operations"].pop()),
      ("boundary",lambda o,s,p:o["boundary"].update(t13_implemented=True)),("t14",lambda o,s,p:o["boundary"].update(t14_authorized=True)),
      ("network",lambda o,s,p:o["resource_binding"].update(network=True)),("workers",lambda o,s,p:o["resource_binding"].update(max_parallel_workers=2)),
      ("consumed",lambda o,s,p:o["state_machine"].update(decision_full_gate_consumes_new_authority=True)),
      ("semantic",lambda o,s,p:next(x for x in s["threat_cases"] if x["case_id"]=="T13").update(threat_class="OTHER")),
      ("manifest",lambda o,s,p:p["boundary"].update(t12_owner_toctou_implemented_after_integrated_full=False)),
    ]
    for _,operation in tests:
        o,s,p=copy.deepcopy(owner),copy.deepcopy(semantic),copy.deepcopy(manifest); operation(o,s,p); rejected(m,o,s,p)
    receipt={"schema":"agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.replay_authority_decision.check.v0","status":base["status"],"reviewer_stdout_line_count":len(base),"directed_negative_test_count":len(tests),"public_input_count":base["public_input_count"],"profile_count":base["profile_count"],"request_field_count":base["request_field_count"],"profile_field_count":base["profile_field_count"],"policy_match_dimension_count":base["policy_match_dimension_count"],"t13_implemented":False,"authority_consumed":False,"runtime_authority":False,"provider_authority":False,"owner_raw_sha256":base["owner_raw_sha256"],"reviewer_raw_sha256":sha(REVIEWER_REL),"semantic_raw_sha256":base["semantic_raw_sha256"],"t12_manifest_raw_sha256":base["t12_manifest_raw_sha256"],"content_sha256":"0"*64}
    copied=dict(receipt);del copied["content_sha256"];receipt["content_sha256"]=hashlib.sha256(DOMAIN.encode()+b"\0"+json.dumps(copied,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return ''.join(f"{k}\t{str(v).lower() if type(v) is bool else v}\n" for k,v in receipt.items())
def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--self-test",action="store_true");args=parser.parse_args()
    try:
        output=evaluate();sys.stdout.write("self_test_contract\tpass\nself_test_mutations\tpass\nself_test_boundary\tpass\n" if args.self_test else output);return 0
    except Exception as error:print(f"check_error\t{error}",file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
