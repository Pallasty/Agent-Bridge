#!/usr/bin/env python3
"""Bounded first-shard signed quotient-H preflight; never performs depth-4 run."""
from __future__ import annotations
import hashlib,importlib.util,json,resource,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
class PreflightError(ValueError): pass
def _json(path): return json.loads(path.read_text(encoding="utf-8"))
def _load(contract):
 pin=contract["d5_checker_sha256"];path=HERE/"fh_l8_symmetry_orbit_quotient_d5_checker.py"
 if hashlib.sha256(path.read_bytes()).hexdigest()!=pin: raise PreflightError("D5B checker pin drift")
 spec=importlib.util.spec_from_file_location("d5b_preflight",path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def _memory_current():
 path=Path("/sys/fs/cgroup/memory.current")
 return int(path.read_text().strip()) if path.is_file() else None
def run(contract):
 d5=_load(contract);d5c=_json(HERE/"fh_l8_symmetry_orbit_quotient_d5_contract.json");d4,d4c,_=d5._verify_parent_sources(d5c);d3=d4._load_d3(d4c);d3c=_json(HERE/"fh_l8_degree6_streaming_d3_contract.json");d2=d3._load_d2(d3c);d2c=_json(HERE/"fh_l8_two_step_scalar_defect_d2_contract.json");up=d2._load_upstream(d2c);backend=up._load_backend();bonds={n:backend._hopping_bonds(8,n) for n in ("H1","H2","H3","H4")};syms,_=d5._build_symmetries(d5c);q={up._neel_basis(8):1};d5._ACTIVE_DEADLINE=time.monotonic()+contract["limits"]["source_replay_seconds"]
 for _ in range(3):q,_record=d5._quotient_step(d4,backend,bonds,q,syms)
 if len(q)!=213099:raise PreflightError("depth3 quotient count drift")
 sources=list(q.items())[:contract["limits"]["source_representatives"]];started=time.monotonic();before=_memory_current();outputs={};raw_terms=0;reduced=0;zero=0
 for index,(rep,amp) in enumerate(sources):
  column,_,dropped=d5._reduced_column(d4,backend,bonds,rep,syms);raw_terms+=len(d4._sector_action(backend,bonds,{rep:1},2000000));reduced+=len(column);zero+=dropped
  for target,coefficient in column.items():outputs[target]=outputs.get(target,0)+amp*coefficient
 elapsed=time.monotonic()-started;after=_memory_current();cleaned={target:value for target,value in outputs.items() if value}
 if any(value.denominator!=1 for value in cleaned.values()):raise PreflightError("nonintegral preflight quotient amplitude")
 if raw_terms>contract["limits"]["max_raw_terms"] or elapsed>contract["limits"]["max_shard_seconds"]:raise PreflightError("preflight cap exceeded")
 memory_probe=before is not None and after is not None
 status="VERIFIED_D9_BOUNDED_QUOTIENT_H_PREFLIGHT_NO_FULL_ACTION" if memory_probe else "VERIFIED_D9_PREFLIGHT_MEMORY_PROBE_UNAVAILABLE_NO_FULL_RUN_AUTHORIZATION"
 return {"status":status,"verified":True,"source_representatives":len(sources),"raw_terms":raw_terms,"reduced_terms":reduced,"projected_zero_terms":zero,"nonzero_targets":len(cleaned),"integral_amplitudes":True,"elapsed_seconds":round(elapsed,3),"memory_current_before":before,"memory_current_after":after,"memory_probe_available":memory_probe,"full_run_authorized":False,"fourth_action_executed":False,"next_gate":"CGROUP_V2_MEMORY_CURRENT_REQUIRED_FOR_FULL_RUN_AUTHORIZATION" if not memory_probe else "FULL_RUN_AUTHORITY_DECISION_FROM_MEASURED_PREFLIGHT"}
def main():
 try:print(json.dumps(run(_json(HERE/"fh_l8_depth4_preflight_d9_contract.json")),indent=2,sort_keys=True));return 0
 except Exception as exc:print(json.dumps({"status":"PREFLIGHT_FAILED","verified":False,"error":str(exc)},sort_keys=True));return 1
if __name__=="__main__":raise SystemExit(main())
