#!/usr/bin/env python3
"""Signed D4 custody and bounded orbit-prefix measurement for FH-L8 Krylov."""
from __future__ import annotations
import hashlib, importlib.util, json, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
STATUS="VERIFIED_D5_SIGNED_D4_CUSTODY_AND_DEPTH3_ORBIT_PREFIX_BOUNDARY"
_CACHE=None
class VerificationError(ValueError): pass
def _load_json(path):
 value=json.loads(path.read_text(encoding="utf-8"))
 if not isinstance(value,dict): raise VerificationError("JSON root must be object")
 return value
def _sha(value): return hashlib.sha256(json.dumps(value,allow_nan=False,ensure_ascii=True,separators=(",",":"),sort_keys=True).encode("ascii")).hexdigest()
def _load_d4(contract):
 pins=contract.get("source_pins"); lim=contract["resource_limits"]["max_source_bytes"]
 if not isinstance(pins,list) or len(pins)!=3: raise VerificationError("three source pins required")
 loaded={}
 for pin in pins:
  path=HERE/pin.get("path","");raw=path.read_bytes() if path.parent==HERE and path.is_file() else b""
  if not raw or len(raw)>lim or hashlib.sha256(raw).hexdigest()!=pin.get("sha256"): raise VerificationError(f"source pin drift: {path.name}")
  loaded[path.name]=raw
 parent=_load_json(HERE/"fh_l8_scalar_supremum_d4_result.json")
 if parent.get("status")!="VERIFIED_D4_SCALAR_SUPREMUM_CANDIDATE_FAILURE_THRESHOLDS": raise VerificationError("D4 parent drift")
 source=loaded["fh_l8_scalar_supremum_d4_checker.py"]; spec=importlib.util.spec_from_loader("pinned_d5_d4",loader=None); m=importlib.util.module_from_spec(spec);m.__file__=str(HERE/"fh_l8_scalar_supremum_d4_checker.py");exec(compile(source,m.__file__,"exec"),m.__dict__);return m
def _build_perms(L=8):
 transforms=[("id",lambda r,c:(r,c),0),("r90_spinflip",lambda r,c:(c,L-1-r),1),("r180",lambda r,c:(L-1-r,L-1-c),0),("r270_spinflip",lambda r,c:(L-1-c,r),1),("fv_spinflip",lambda r,c:(r,L-1-c),1),("fh_spinflip",lambda r,c:(L-1-r,c),1),("diag",lambda r,c:(c,r),0),("adiag",lambda r,c:(L-1-c,L-1-r),0)]
 perms=[]
 for name,f,swap in transforms:
  p=[]
  for mode in range(128):
   site,spin=divmod(mode,2);r,c=divmod(site,L);rr,cc=f(r,c);p.append(2*(rr*L+cc)+(spin^swap))
  perms.append((name,p))
 return perms
def _transform(x,p):
 occupied=[i for i in range(128) if (x>>i)&1];mapped=[p[i] for i in occupied];target=0;inversions=0
 for i,a in enumerate(mapped): target|=1<<a;inversions+=sum(z<a for z in mapped[i+1:])
 return target,(-1 if inversions&1 else 1)
def _digest_orbits(vector,perms,limit=None):
 reps={}; processed=0
 for state in vector:
  if limit is not None and processed>=limit: break
  rep=min(_transform(state,p)[0] for _,p in perms);reps[rep]=reps.get(rep,0)+1;processed+=1
 records=[[hex(state),str(count)] for state,count in sorted(reps.items())]
 return {"processed":processed,"orbits":len(reps),"digest":hashlib.sha256(json.dumps(records,separators=(",",":")).encode("ascii")).hexdigest()}
def _sector_action(module,backend,bonds,vector,state_cap):
 output={}
 for basis,amplitude in vector.items():
  diagonal=(8*sum(((basis>>(2*site))&3)==3 for site in range(64))-128)*amplitude
  if diagonal: output[basis]=output.get(basis,0)+diagonal
  for group in ("H1","H2","H3","H4"):
   for left,right in bonds[group]:
    if ((basis>>left)&1)==((basis>>right)&1): continue
    inner=((basis>>(left+1))&((1<<(right-left-1))-1)).bit_count();target=basis^((1<<left)|(1<<right));output[target]=output.get(target,0)-((-1 if inner&1 else 1)*amplitude)
 if len(output)>state_cap: raise VerificationError("state cap exceeded")
 return {x:a for x,a in output.items() if a}
def _transform_vector(vector,p):
 output={}
 for state,amp in vector.items(): target,sign=_transform(state,p);output[target]=output.get(target,0)+sign*amp
 return {x:a for x,a in output.items() if a}
def _observable_values(state):
 staggered=sum((1 if (site//8+site%8)%2==0 else -1)*(((state>>(2*site))&1)-((state>>(2*site+1))&1)) for site in range(64))
 double=sum(((state>>(2*site))&3)==3 for site in range(64))
 return staggered,double
def _verify_observable_map(perms,L=8):
 for _,p in perms:
  site_targets={}
  for mode,target in enumerate(p):
   site,spin=divmod(mode,2);ts,tsn=divmod(target,2)
   parity=(-1)**((site//L+site%L)%2);tparity=(-1)**((ts//L+ts%L)%2)
   if parity*(1 if spin==0 else -1)!=tparity*(1 if tsn==0 else -1):
    raise VerificationError("staggered observable map drift")
   site_targets.setdefault(site,set()).add(ts)
  if any(len(targets)!=1 for targets in site_targets.values()):
   raise VerificationError("double-occupancy site map drift")
def recompute(contract):
 global _CACHE
 digest=_sha(contract)
 if _CACHE is not None and _CACHE[0]==digest:return json.loads(json.dumps(_CACHE[1]))
 if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D5" or contract.get("parent_contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D4":raise VerificationError("identity drift")
 if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=contract.get("checker_self_sha256"):raise VerificationError("checker self pin drift")
 d4=_load_d4(contract);d4c=_load_json(HERE/"fh_l8_scalar_supremum_d4_contract.json");d3=d4._load_d3(d4c);d3c=_load_json(HERE/"fh_l8_degree6_streaming_d3_contract.json");d2=d3._load_d2(d3c);d2c=_load_json(HERE/"fh_l8_two_step_scalar_defect_d2_contract.json");module=d2._load_upstream(d2c);backend=module._load_backend();perms=_build_perms();q=module._neel_basis(8);chars=[]
 for _,p in perms:
  target,sign=_transform(q,p)
  if target!=q:raise VerificationError("Néel set not stabilized")
  chars.append(sign)
 if chars!=[1]*8:raise VerificationError("Néel character drift")
 _verify_observable_map(perms);bonds={g:backend._hopping_bonds(8,g) for g in ("H1","H2","H3","H4")};vector={q:1};records={};equivariance=[]
 for depth in range(4):
  orbit=_digest_orbits(vector,perms,contract["resource_limits"]["max_depth3_prefix_states"] if depth==3 else None)
  expected=contract["expected_orbits"][f"depth{depth}"]
  if depth<3 and (len(vector)!=expected["states"] or orbit["orbits"]!=expected["orbits"] or orbit["digest"]!=expected["digest"]):raise VerificationError(f"depth{depth} orbit drift")
  if depth==3 and (len(vector)!=expected["states"] or orbit["processed"]!=expected["prefix_states_processed"] or orbit["orbits"]!=expected["prefix_orbits"] or orbit["digest"]!=expected["prefix_digest"]):raise VerificationError("depth3 prefix drift")
  if depth<3:
   equivariance.append(all(_transform_vector(vector,p)==vector for _,p in perms))
   if not equivariance[-1]:raise VerificationError(f"state equivariance failure at depth {depth}")
  else: equivariance.append(None)
  for state in list(vector)[:min(10000,len(vector))]:
   vals=_observable_values(state)
   for _,p in perms:
    target,_=_transform(state,p)
    if _observable_values(target)!=vals:raise VerificationError("observable invariance failure")
  records[f"depth{depth}"]={"state_count":len(vector),"orbit_measurement":orbit,"equivariance":equivariance[-1]}
  if depth<3:vector=_sector_action(module,backend,bonds,vector,contract["resource_limits"]["max_materialized_states"])
 evidence={"contract_id":contract["contract_id"],"status":STATUS,"verified":True,"signed_group_order":8,"Neel_characters":chars,"hamiltonian_equivariance":True,"observable_invariance":True,"orbit_records":records,"depth3_full_orbit_count_certified":False,"next_branch":"BYTE_TABLE_SIGNED_BIT_PERMUTATION_ORBIT_CANONICALIZATION","degree6_remainder_bounded":False,"two_step_cumulative_error_bounded":False,"full_R100_error_bounded":False,"physical_reference_qualified":False,"ready_gate_eligible":False,"terminal_branch":contract["terminal_branch"],"limitations":["Depth-3 full orbit count is not certified; only the first 100,000 states are measured.","The quotient is custody-positive but no compressed H action or D6 remainder was executed.","No cumulative, R100, physical reference or READY authority."]}
 _CACHE=(digest,json.loads(json.dumps(evidence)));return evidence
def verify(contract,result):
 evidence=recompute(contract)
 if result!=evidence:raise VerificationError("result does not equal recomputed evidence")
 return evidence
def main(argv=None):
 args=list(sys.argv[1:] if argv is None else argv);contract=_load_json(HERE/"fh_l8_signed_d4_orbit_d5_contract.json")
 try:
  evidence=recompute(contract)
  if "--evidence" not in args:evidence=verify(contract,_load_json(HERE/"fh_l8_signed_d4_orbit_d5_result.json"))
 except (OSError,json.JSONDecodeError,VerificationError,ValueError,TypeError,KeyError) as exc:
  print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(exc)},sort_keys=True));return 1
 print(json.dumps(evidence,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
