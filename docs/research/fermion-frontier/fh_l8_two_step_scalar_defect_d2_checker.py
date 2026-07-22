#!/usr/bin/env python3
"""Two-step scalar defect through D5 and failure-local D6 resource gate."""
from __future__ import annotations
import hashlib, importlib.util, json, math, sys
from fractions import Fraction
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent
STATUS="VERIFIED_D2_DEGREE6_REMAINDER_RESOURCE_THRESHOLD"
OBSERVABLES=("staggered_magnetization","double_occupancy")
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
def _load_upstream(contract):
 pins=contract.get("source_pins"); limit=contract["resource_limits"]["max_source_bytes"]
 if not isinstance(pins,list) or len(pins)!=4: raise VerificationError("four source pins required")
 loaded={}
 for pin in pins:
  path=HERE/pin.get("path",""); raw=path.read_bytes() if path.parent==HERE and path.is_file() else b""
  if not raw or len(raw)>limit or hashlib.sha256(raw).hexdigest()!=pin.get("sha256"): raise VerificationError(f"source pin drift: {path.name}")
  loaded[path.name]=raw
 parent=_load_json(HERE/"fh_l8_state_specific_defect_d1_result.json")
 if parent.get("status")!="VERIFIED_FH_L8_K0_K1_STATE_SPECIFIC_DEFECT_WITHIN_ALLOCATION" or parent.get("verified") is not True: raise VerificationError("D1 parent is not positive")
 source=loaded["hubbard_strang_observable_taylor_step_checker.py"]; spec=importlib.util.spec_from_loader("pinned_d2_upstream",loader=None); module=importlib.util.module_from_spec(spec); module.__file__=str(HERE/"hubbard_strang_observable_taylor_step_checker.py"); exec(compile(source,module.__file__,"exec"),module.__dict__); return module
def _merged_stages(module):
 out=[]
 for group,coefficient in list(module.STAGES)*2:
  if out and out[-1][0]==group: out[-1]=(group,out[-1][1]+coefficient)
  else: out.append((group,coefficient))
 if len(out)!=17 or out[8]!=("H1",Fraction(1)): raise VerificationError("two-step stage merge drift")
 return tuple(out)
def _formal(module,backend,groups,observable,stages,counter):
 degree=5; polynomial=[dict(observable)]+[{} for _ in range(degree)]
 for group,coefficient in stages:
  updated=[{} for _ in range(degree+1)]
  for base,expansion in enumerate(polynomial):
   nested=dict(expansion)
   for power in range(degree-base+1):
    if power: nested=module._commutator(backend,groups[group],nested,counter)
    module._add_scaled(backend,updated[base+power],nested,module._i_scalar(backend,power,coefficient**power/Fraction(math.factorial(power))))
  polynomial=updated
 return polynomial
def _diagonal(module,backend,expansion,basis):
 value=(Fraction(0),Fraction(0))
 for key,coefficient in expansion.items():
  target,phase=backend._basis_pauli_action(key,basis)
  if target==basis: value=backend._g_add(value,backend._g_mul(coefficient,phase))
 if value[1]!=0: raise VerificationError("non-real diagonal")
 return value[0]
def recompute(contract):
 global _CACHE
 digest=_sha(contract)
 if _CACHE is not None and _CACHE[0]==digest: return json.loads(json.dumps(_CACHE[1]))
 if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D2" or contract.get("parent_contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D1": raise VerificationError("contract identity drift")
 if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=contract.get("checker_self_sha256"): raise VerificationError("checker self pin drift")
 module=_load_upstream(contract); limits=contract["resource_limits"]; module.RESOURCE_LIMITS["max_pair_products"]=limits["max_pair_products_per_observable"]; module.RESOURCE_LIMITS["max_expansion_terms"]=limits["max_expansion_terms"]
 backend=module._load_backend(); groups=backend.canonical_group_expansions(8); hamiltonian=backend._merge_expansions([groups[x] for x in module.GROUPS]); basis=module._neel_basis(8); stages=_merged_stages(module); records={}
 for name in OBSERVABLES:
  counter=module.ComputationCounter(); observable,identity=module._observable_expansion(backend,8,name); product=_formal(module,backend,groups,observable,stages,counter); nested=dict(observable); ideal=[]
  for degree in range(6):
   if degree: nested=module._commutator(backend,hamiltonian,nested,counter)
   item={}; module._add_scaled(backend,item,nested,module._i_scalar(backend,degree,Fraction(2**degree,math.factorial(degree)))); ideal.append(item)
  degrees={}
  for degree in (3,4,5):
   defect=module._subtract(backend,product[degree],ideal[degree]); degrees[str(degree)]={"Neel_expectation":_fmt(_diagonal(module,backend,defect,basis)),"L1":_fmt(module._l1(defect)),"term_count":len(defect),"defect_expansion_sha256":backend._expansion_sha256(defect),"product_term_count":len(product[degree]),"ideal_term_count":len(ideal[degree])}
  expected=contract["expected_exact_values"][name]
  for degree in (3,4,5):
   if _fraction(expected[f"D{degree}_Neel_expectation"])!=_fraction(degrees[str(degree)]["Neel_expectation"]) or _fraction(expected[f"D{degree}_L1"])!=_fraction(degrees[str(degree)]["L1"]): raise VerificationError(f"{name} D{degree} drift")
  if degrees["5"]["defect_expansion_sha256"]!=expected["D5_defect_sha256"]: raise VerificationError(f"{name} D5 digest drift")
  records[name]={"observable_identity":identity,"degrees":degrees,"degree_four_absolute_contribution":_fmt(Fraction(1,100)**4*abs(_fraction(degrees["4"]["Neel_expectation"]))),"resource_usage":{"pair_products":counter.pair_products,"peak_expansion_terms":counter.peak_terms}}
 requirements=contract["degree_six_requirements"]; paths=math.comb(22,6); prefixes=math.comb(23,6)
 if (paths,prefixes)!=(requirements["weak_composition_count"],requirements["full_prefix_count"]): raise VerificationError("degree-six combinatorics drift")
 path_over=paths>limits["max_degree_six_weak_compositions"]; prefix_over=prefixes>limits["max_degree_six_prefixes"]
 if not path_over or not prefix_over: raise VerificationError("degree-six failure branch not reached")
 evidence={"contract_id":contract["contract_id"],"status":STATUS,"verified":True,"terminal_branch":contract["terminal_branch"],"next_branch":contract["next_branch"],"two_step_cumulative_error_bounded":False,"full_R100_error_bounded":False,"physical_reference_qualified":False,"ready_gate_eligible":False,"merged_stage_count":len(stages),"observables":records,"degree_six_gate":{"weak_composition_count":paths,"weak_composition_cap":limits["max_degree_six_weak_compositions"],"weak_composition_cap_exceeded":path_over,"full_prefix_count":prefixes,"prefix_cap":limits["max_degree_six_prefixes"],"prefix_cap_exceeded":prefix_over,"remainder_numerically_evaluated":False},"limitations":["D3 through D5 scalar coefficients are exact, but the degree-six remainder is not bounded.","The D4 contribution alone is not a two-step cumulative error certificate.","D1 is not added as a scalar telescoping term."]}
 _CACHE=(digest,json.loads(json.dumps(evidence))); return evidence
def verify(contract,result):
 evidence=recompute(contract)
 if result!=evidence: raise VerificationError("result does not equal recomputed evidence")
 return evidence
def main(argv=None):
 args=list(sys.argv[1:] if argv is None else argv); contract=_load_json(HERE/"fh_l8_two_step_scalar_defect_d2_contract.json")
 try:
  evidence=recompute(contract)
  if "--evidence" not in args: evidence=verify(contract,_load_json(HERE/"fh_l8_two_step_scalar_defect_d2_result.json"))
 except (OSError,json.JSONDecodeError,VerificationError,ValueError,TypeError,KeyError) as exc:
  print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(exc)},sort_keys=True)); return 1
 print(json.dumps(evidence,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
