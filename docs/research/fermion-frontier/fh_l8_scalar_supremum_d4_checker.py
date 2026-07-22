#!/usr/bin/env python3
"""D4 gate for generic derivative, Cauchy, and exact sparse-sector Krylov routes."""
from __future__ import annotations
import hashlib, importlib.util, json, math, sys
from fractions import Fraction
from pathlib import Path
HERE=Path(__file__).resolve().parent
STATUS="VERIFIED_D4_SCALAR_SUPREMUM_CANDIDATE_FAILURE_THRESHOLDS"
_CACHE=None
class VerificationError(ValueError): pass
def _load_json(path):
 value=json.loads(path.read_text(encoding="utf-8"))
 if not isinstance(value,dict): raise VerificationError("JSON root must be object")
 return value
def _fraction(value):
 if not isinstance(value,str) or "/" not in value: raise VerificationError("fraction string required")
 return Fraction(value)
def _fmt(value): return f"{value.numerator}/{value.denominator}"
def _sha(value): return hashlib.sha256(json.dumps(value,allow_nan=False,ensure_ascii=True,separators=(",",":"),sort_keys=True).encode("ascii")).hexdigest()
def _load_d3(contract):
 pins=contract.get("source_pins"); limit=contract["resource_limits"]["max_source_bytes"]
 if not isinstance(pins,list) or len(pins)!=3: raise VerificationError("three source pins required")
 loaded={}
 for pin in pins:
  path=HERE/pin.get("path",""); raw=path.read_bytes() if path.parent==HERE and path.is_file() else b""
  if not raw or len(raw)>limit or hashlib.sha256(raw).hexdigest()!=pin.get("sha256"): raise VerificationError(f"source pin drift: {path.name}")
  loaded[path.name]=raw
 parent=_load_json(HERE/"fh_l8_degree6_streaming_d3_result.json")
 if parent.get("status")!="VERIFIED_D3_STREAMING_PAIR_CAP_AND_MITM_COMPOSITION_GAP": raise VerificationError("D3 parent drift")
 source=loaded["fh_l8_degree6_streaming_d3_checker.py"]; spec=importlib.util.spec_from_loader("pinned_d4_d3",loader=None); module=importlib.util.module_from_spec(spec); module.__file__=str(HERE/"fh_l8_degree6_streaming_d3_checker.py"); exec(compile(source,module.__file__,"exec"),module.__dict__); return module
def _vector_digest(vector): return hashlib.sha256(json.dumps([[hex(x),str(a)] for x,a in sorted(vector.items())],separators=(",",":")).encode("ascii")).hexdigest()
def _sector_action(backend,bonds,vector,state_cap):
 output={}
 for basis,amplitude in vector.items():
  diagonal=(8*sum(((basis>>(2*site))&3)==3 for site in range(64))-128)*amplitude
  if diagonal: output[basis]=output.get(basis,0)+diagonal
  for group in ("H1","H2","H3","H4"):
   for left,right in bonds[group]:
    if ((basis>>left)&1)==((basis>>right)&1): continue
    interior=((basis>>(left+1))&((1<<(right-left-1))-1)).bit_count(); sign=-1 if interior%2 else 1; target=basis^((1<<left)|(1<<right)); output[target]=output.get(target,0)-sign*amplitude
 if len(output)>state_cap: raise VerificationError("materialized state cap exceeded")
 return {basis:amplitude for basis,amplitude in output.items() if amplitude}
def recompute(contract):
 global _CACHE
 digest=_sha(contract)
 if _CACHE is not None and _CACHE[0]==digest: return json.loads(json.dumps(_CACHE[1]))
 if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D4" or contract.get("parent_contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D3": raise VerificationError("identity drift")
 if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=contract.get("checker_self_sha256"): raise VerificationError("checker self pin drift")
 d3=_load_d3(contract); d3_contract=_load_json(HERE/"fh_l8_degree6_streaming_d3_contract.json"); d2=d3._load_d2(d3_contract); d2_contract=_load_json(HERE/"fh_l8_two_step_scalar_defect_d2_contract.json"); module=d2._load_upstream(d2_contract); backend=module._load_backend(); groups=backend.canonical_group_expansions(8)
 l1={name:module._l1(groups[name]) for name in module.GROUPS}; expected_global=contract["global_norm_candidate"]
 for name,value in l1.items():
  if value!=_fraction(expected_global["group_L1"][name]): raise VerificationError("group L1 drift")
 total=sum(l1.values(),Fraction(0)); base=4*total; m6=2*base**6
 if total!=_fraction(expected_global["total_H_L1"]) or base!=_fraction(expected_global["two_step_conjugation_derivative_base"]) or m6!=_fraction(expected_global["difference_M6_bound"]): raise VerificationError("global derivative arithmetic drift")
 allocation=_fraction(contract["two_step_allocation"]); budgets={}
 for name,lead_text in contract["degree_four_contributions"].items():
  slack=allocation-_fraction(lead_text); ceiling=720*slack/Fraction(1,100)**6; expected=contract["expected_budget_arithmetic"][name]
  if slack!=_fraction(expected["remainder_slack"]) or ceiling!=_fraction(expected["M6_ceiling"]): raise VerificationError("budget arithmetic drift")
  budgets[name]={"degree_four_contribution":lead_text,"remainder_slack":_fmt(slack),"M6_ceiling":_fmt(ceiling),"generic_M6_to_ceiling_ratio":_fmt(m6/ceiling)}
 a=_fraction(contract["cauchy_candidate"]["dimensionless_exponent_rate"]); cauchy_floor=a**7/630
 if cauchy_floor!=_fraction(contract["cauchy_candidate"]["global_lower_bound_from_exp_y_ge_y7_over_7factorial"]): raise VerificationError("Cauchy floor drift")
 krylov=contract["sector_krylov_candidate"]; q=module._neel_basis(8); bonds={g:backend._hopping_bonds(8,g) for g in ("H1","H2","H3","H4")}; vector={q:1}; counts=[]; digests=[]
 for depth in range(4):
  counts.append(len(vector)); digests.append(_vector_digest(vector))
  if depth<3: vector=_sector_action(backend,bonds,vector,contract["resource_limits"]["max_materialized_states"])
 if counts!=krylov["reachable_state_counts"] or digests!=krylov["state_digests"]: raise VerificationError("Krylov prefix drift")
 next_floor=len(vector)*krylov["candidate_actions_per_state"]
 if next_floor!=krylov["next_action_candidate_floor"] or next_floor<=krylov["next_action_cap"]: raise VerificationError("Krylov next-action branch drift")
 evidence={"contract_id":contract["contract_id"],"status":STATUS,"verified":True,"terminal_branch":contract["terminal_branch"],"next_branch":contract["next_branch"],"degree6_remainder_bounded":False,"two_step_cumulative_error_bounded":False,"full_R100_error_bounded":False,"physical_reference_qualified":False,"ready_gate_eligible":False,"budget_gate":budgets,"candidates":{"GENERIC_DERIVATIVE":{"decision":"NUMERICALLY_INADEQUATE","H_L1":_fmt(total),"M6_bound":_fmt(m6)},"COMPLEX_CAUCHY":{"decision":"NUMERICALLY_INADEQUATE","majorant_global_lower_bound":_fmt(cauchy_floor),"proof":"exp(y)>=y^7/7! and x^2/(x-1)>=4 for x>1"},"EXACT_SECTOR_KRYLOV":{"decision":"NEXT_ACTION_CAP_EXCEEDED","reachable_state_counts":counts,"state_digests":digests,"candidate_actions_per_state":krylov["candidate_actions_per_state"],"next_action_candidate_floor":next_floor,"next_action_cap":krylov["next_action_cap"],"next_action_executed":False}},"limitations":["Each decision closes only the fixed candidate and constants in the contract.","The Cauchy result evaluates the current global-norm majorant, not all complex-analytic bounds.","The Krylov result stops before H acts on the depth-three vector."]}
 _CACHE=(digest,json.loads(json.dumps(evidence))); return evidence
def verify(contract,result):
 evidence=recompute(contract)
 if result!=evidence: raise VerificationError("result does not equal recomputed evidence")
 return evidence
def main(argv=None):
 args=list(sys.argv[1:] if argv is None else argv); contract=_load_json(HERE/"fh_l8_scalar_supremum_d4_contract.json")
 try:
  evidence=recompute(contract)
  if "--evidence" not in args: evidence=verify(contract,_load_json(HERE/"fh_l8_scalar_supremum_d4_result.json"))
 except (OSError,json.JSONDecodeError,VerificationError,ValueError,TypeError,KeyError) as exc:
  print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(exc)},sort_keys=True)); return 1
 print(json.dumps(evidence,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
