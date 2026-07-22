#!/usr/bin/env python3
"""D3 streaming pair floor and fixed Pauli-L1 MITM proof-obligation gate."""
from __future__ import annotations
import hashlib, importlib.util, json, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
STATUS="VERIFIED_D3_STREAMING_PAIR_CAP_AND_MITM_COMPOSITION_GAP"
OBSERVABLES=("staggered_magnetization","double_occupancy")
_CACHE=None
class VerificationError(ValueError): pass
def _load_json(path):
 value=json.loads(path.read_text(encoding="utf-8"))
 if not isinstance(value,dict): raise VerificationError("JSON root must be object")
 return value
def _sha(value): return hashlib.sha256(json.dumps(value,allow_nan=False,ensure_ascii=True,separators=(",",":"),sort_keys=True).encode("ascii")).hexdigest()
def _load_d2(contract):
 pins=contract.get("source_pins"); limit=contract["resource_limits"]["max_source_bytes"]
 if not isinstance(pins,list) or len(pins)!=3: raise VerificationError("three source pins required")
 loaded={}
 for pin in pins:
  path=HERE/pin.get("path",""); raw=path.read_bytes() if path.parent==HERE and path.is_file() else b""
  if not raw or len(raw)>limit or hashlib.sha256(raw).hexdigest()!=pin.get("sha256"): raise VerificationError(f"source pin drift: {path.name}")
  loaded[path.name]=raw
 parent=_load_json(HERE/"fh_l8_two_step_scalar_defect_d2_result.json")
 if parent.get("status")!="VERIFIED_D2_DEGREE6_REMAINDER_RESOURCE_THRESHOLD" or parent.get("degree_six_gate",{}).get("weak_composition_count")!=74613: raise VerificationError("D2 parent drift")
 source=loaded["fh_l8_two_step_scalar_defect_d2_checker.py"]; spec=importlib.util.spec_from_loader("pinned_d3_d2",loader=None); module=importlib.util.module_from_spec(spec); module.__file__=str(HERE/"fh_l8_two_step_scalar_defect_d2_checker.py"); exec(compile(source,module.__file__,"exec"),module.__dict__); return module
def _stream_probe(d2,module,backend,groups,stages,observable,limits):
 module.RESOURCE_LIMITS["max_pair_products"]=limits["max_prefix_pair_products_per_observable"]
 module.RESOURCE_LIMITS["max_expansion_terms"]=limits["max_expansion_terms"]
 counter=module.ComputationCounter(); state={"floor":0,"leaves":0,"prefixes":1,"peak_live":len(observable),"terminal":None}; cap=limits["max_degree6_prospective_pair_products_per_observable"]
 def dfs(prefix,last,expansion,live):
  if state["terminal"] is not None: return
  state["peak_live"]=max(state["peak_live"],live)
  if live>limits["max_live_path_terms"]: raise VerificationError("live path cap exceeded")
  if len(prefix)==5:
   state["leaves"]+=1
   for stage_index in range(last,len(stages)):
    pairs=len(expansion)*len(groups[stages[stage_index][0]])
    if state["floor"]+pairs>cap:
     state["terminal"]={"terminal_prefix":list(prefix),"terminal_next_stage":stage_index,"terminal_parent_terms":len(expansion),"terminal_next_group":stages[stage_index][0],"terminal_next_pairs":pairs,"degree6_floor_before":state["floor"],"degree6_floor_after":state["floor"]+pairs}; return
    state["floor"]+=pairs
   return
  for stage_index in range(last,len(stages)):
   child=module._commutator(backend,groups[stages[stage_index][0]],expansion,counter); state["prefixes"]+=1; dfs(prefix+(stage_index,),stage_index,child,live+len(child))
   if state["terminal"] is not None: return
 dfs((),0,observable,len(observable))
 if state["terminal"] is None: raise VerificationError("streaming pair cap was not reached")
 return {"completed_depth5_leaves":state["leaves"],"computed_prefixes":state["prefixes"],"prefix_pair_products":counter.pair_products,"peak_expansion_terms":counter.peak_terms,"peak_live_path_terms":state["peak_live"],**state["terminal"],"degree6_children_materialized":False}
def recompute(contract):
 global _CACHE
 digest=_sha(contract)
 if _CACHE is not None and _CACHE[0]==digest: return json.loads(json.dumps(_CACHE[1]))
 if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D3" or contract.get("parent_contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D2": raise VerificationError("identity drift")
 if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=contract.get("checker_self_sha256"): raise VerificationError("checker self pin drift")
 d2=_load_d2(contract); d2_contract=_load_json(HERE/"fh_l8_two_step_scalar_defect_d2_contract.json"); module=d2._load_upstream(d2_contract); backend=module._load_backend(); groups=backend.canonical_group_expansions(8); stages=d2._merged_stages(module); limits=contract["resource_limits"]; records={}
 for name in OBSERVABLES:
  observable,identity=module._observable_expansion(backend,8,name); measured=_stream_probe(d2,module,backend,groups,stages,observable,limits); expected=contract["expected_streaming_thresholds"][name]
  for key,value in expected.items():
   if measured.get(key)!=value: raise VerificationError(f"{name} {key} drift")
  records[name]={"observable_identity":identity,"streaming_threshold":measured}
 mitm=contract["candidates"]["PAULI_L1_MEET_IN_THE_MIDDLE"]
 if mitm.get("identity_available") is not False or mitm.get("numerically_executed") is not False: raise VerificationError("MITM gate drift")
 evidence={"contract_id":contract["contract_id"],"status":STATUS,"verified":True,"terminal_branch":contract["terminal_branch"],"next_branch":contract["next_branch"],"degree6_remainder_bounded":False,"two_step_cumulative_error_bounded":False,"full_R100_error_bounded":False,"physical_reference_qualified":False,"ready_gate_eligible":False,"candidates":{"DEPTH_FIRST_STREAMING":{"decision":"PAIR_CAP_EXCEEDED","memory_architecture_feasible":True,"observables":records},"PAULI_L1_MEET_IN_THE_MIDDLE":{"decision":"BLOCKED_MISSING_COMPOSITION_PROOF","required_missing_identity":mitm["required_missing_identity"],"numerically_executed":False}},"limitations":["The 2B floor is for the fixed DFS Pauli-L1 path architecture, not all streaming algorithms.","No general MITM no-go is claimed; the fixed candidate lacks a certified nonlinear L1 composition rule.","No degree-six child expansion or numerical remainder was produced."]}
 _CACHE=(digest,json.loads(json.dumps(evidence))); return evidence
def verify(contract,result):
 evidence=recompute(contract)
 if result!=evidence: raise VerificationError("result does not equal recomputed evidence")
 return evidence
def main(argv=None):
 args=list(sys.argv[1:] if argv is None else argv); contract=_load_json(HERE/"fh_l8_degree6_streaming_d3_contract.json")
 try:
  evidence=recompute(contract)
  if "--evidence" not in args: evidence=verify(contract,_load_json(HERE/"fh_l8_degree6_streaming_d3_result.json"))
 except (OSError,json.JSONDecodeError,VerificationError,ValueError,TypeError,KeyError) as exc:
  print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(exc)},sort_keys=True)); return 1
 print(json.dumps(evidence,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
