#!/usr/bin/env python3
"""Byte-table signed-D4 orbit certification for the FH-L8 depth-3 sector."""
from __future__ import annotations
import hashlib, importlib.util, json, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
STATUS="VERIFIED_D6_BYTE_TABLE_SIGNED_D4_DEPTH3_ORBITS"
_CACHE=None
class VerificationError(ValueError): pass
def _json(path):
 value=json.loads(path.read_text(encoding="utf-8"))
 if not isinstance(value,dict): raise VerificationError("JSON root must be object")
 return value
def _sha(value): return hashlib.sha256(json.dumps(value,allow_nan=False,ensure_ascii=True,separators=(",",":"),sort_keys=True).encode("ascii")).hexdigest()
def _load_parent(contract):
 pins=contract.get("source_pins",[]);loaded={};limit=contract["resource_limits"]["max_source_bytes"]
 if len(pins)!=3: raise VerificationError("three D5 source pins required")
 for pin in pins:
  path=HERE/pin.get("path","");raw=path.read_bytes() if path.parent==HERE and path.is_file() else b""
  if not raw or len(raw)>limit or hashlib.sha256(raw).hexdigest()!=pin.get("sha256"): raise VerificationError("D5 source pin drift")
  loaded[path.name]=raw
 parent=_json(HERE/"fh_l8_signed_d4_orbit_d5_result.json")
 if parent.get("status")!="VERIFIED_D5_SIGNED_D4_CUSTODY_AND_DEPTH3_ORBIT_PREFIX_BOUNDARY": raise VerificationError("D5 parent result drift")
 source=loaded["fh_l8_signed_d4_orbit_d5_checker.py"];spec=importlib.util.spec_from_loader("pinned_d6_d5",loader=None);m=importlib.util.module_from_spec(spec);m.__file__=str(HERE/"fh_l8_signed_d4_orbit_d5_checker.py");exec(compile(source,m.__file__,"exec"),m.__dict__)
 return m
def _tables(perms):
 output=[]
 for _,p in perms:
  chunks=[]
  for offset in range(0,128,8):
   chunks.append([sum((1<<p[offset+bit]) for bit in range(8) if value>>bit&1) for value in range(256)])
  output.append(chunks)
 return output
def _fast(x,t):
 return t[0][x&255]|t[1][(x>>8)&255]|t[2][(x>>16)&255]|t[3][(x>>24)&255]|t[4][(x>>32)&255]|t[5][(x>>40)&255]|t[6][(x>>48)&255]|t[7][(x>>56)&255]|t[8][(x>>64)&255]|t[9][(x>>72)&255]|t[10][(x>>80)&255]|t[11][(x>>88)&255]|t[12][(x>>96)&255]|t[13][(x>>104)&255]|t[14][(x>>112)&255]|t[15][(x>>120)&255]
def _orbit_digest(states,tables):
 reps={}
 for state in states:
  best=_fast(state,tables[0])
  for table in tables[1:]:
   candidate=_fast(state,table)
   if candidate<best: best=candidate
  reps[best]=reps.get(best,0)+1
 records=[[hex(state),str(count)] for state,count in sorted(reps.items())]
 return {"states":len(states),"orbits":len(reps),"digest":hashlib.sha256(json.dumps(records,separators=(",",":")).encode("ascii")).hexdigest()}
def recompute(contract):
 global _CACHE
 digest=_sha(contract)
 if _CACHE is not None and _CACHE[0]==digest:return json.loads(json.dumps(_CACHE[1]))
 if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D6" or contract.get("parent_contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D5": raise VerificationError("identity drift")
 if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=contract.get("checker_self_sha256"): raise VerificationError("checker self pin drift")
 d5=_load_parent(contract);d5c=_json(HERE/"fh_l8_signed_d4_orbit_d5_contract.json");d5e=d5.recompute(d5c);perms=d5._build_perms();tables=_tables(perms)
 d4=d5._load_d4(d5c);d4c=_json(HERE/"fh_l8_scalar_supremum_d4_contract.json");d3=d4._load_d3(d4c);d3c=_json(HERE/"fh_l8_degree6_streaming_d3_contract.json");d2=d3._load_d2(d3c);d2c=_json(HERE/"fh_l8_two_step_scalar_defect_d2_contract.json");module=d2._load_upstream(d2c);backend=module._load_backend();q=module._neel_basis(8);bonds={g:backend._hopping_bonds(8,g) for g in ("H1","H2","H3","H4")};vector={q:1}
 for _ in range(3): vector=d5._sector_action(module,backend,bonds,vector,contract["resource_limits"]["max_materialized_states"])
 states=list(vector);sample=states[:contract["resource_limits"]["signed_equivalence_sample_states"]]
 for state in sample:
  for (_,p),table in zip(perms,tables):
   target,_=d5._transform(state,p)
   if _fast(state,table)!=target: raise VerificationError("byte table differs from signed Fock support action")
 started=time.monotonic();orbit=_orbit_digest(states,tables);elapsed=time.monotonic()-started
 if elapsed>contract["resource_limits"]["max_live_canonicalization_seconds"]: raise VerificationError("full canonicalization time cap exceeded")
 if orbit["states"]!=d5e["orbit_records"]["depth3"]["state_count"]: raise VerificationError("depth3 state count drift")
 evidence={"contract_id":contract["contract_id"],"status":STATUS,"verified":True,"signed_support_equivalence_samples":len(sample),"depth3_orbit":orbit,"canonicalization_within_seconds_cap":True,"compression_ratio_denominator":orbit["orbits"],"fourth_layer_feasibility":"NOT_EXECUTED_OR_CERTIFIED","degree6_remainder_bounded":False,"two_step_cumulative_error_bounded":False,"full_R100_error_bounded":False,"physical_reference_qualified":False,"ready_gate_eligible":False,"next_branch":"QUOTIENT_HAMILTONIAN_ACTION_AND_FOURTH_LAYER_COST_GATE","limitations":["The byte table is proven against the signed Fock support action on a deterministic sample; canonicalization needs only support orbits.","No quotient Hamiltonian action or fourth-layer Krylov action was executed.","No D6 remainder, cumulative, R100, physical reference, or READY authority."]}
 _CACHE=(digest,json.loads(json.dumps(evidence)));return evidence
def verify(contract,result):
 evidence=recompute(contract)
 if evidence!=result: raise VerificationError("result does not equal recomputed evidence")
 return evidence
def main(argv=None):
 args=list(sys.argv[1:] if argv is None else argv);contract=_json(HERE/"fh_l8_byte_table_orbit_d6_contract.json")
 try:
  evidence=recompute(contract)
  if "--evidence" not in args: evidence=verify(contract,_json(HERE/"fh_l8_byte_table_orbit_d6_result.json"))
 except (OSError,json.JSONDecodeError,VerificationError,ValueError,TypeError,KeyError) as exc:
  print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(exc)},sort_keys=True));return 1
 print(json.dumps(evidence,indent=2,sort_keys=True));return 0
if __name__=="__main__": raise SystemExit(main())
