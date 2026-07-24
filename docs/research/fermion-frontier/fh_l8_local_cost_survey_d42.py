#!/usr/bin/env python3
"""D42 two-seed source-bound local survey; no packed-q3."""
from __future__ import annotations
import hashlib, importlib.util, json, resource, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
PINS=("fh_l8_symmetry_orbit_quotient_d5_checker.py","fh_l8_scalar_supremum_d4_checker.py","hubbard_strang_commutator_checker.py","fh_l8_symmetry_orbit_quotient_d5_contract.json")
def load(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def run():
 resource.setrlimit(resource.RLIMIT_AS,(536_870_912,536_870_912));d5=load('d42_d5',PINS[0]);d4=load('d42_d4',PINS[1]);b=load('d42_b',PINS[2]);c=json.loads((HERE/PINS[3]).read_text());syms,_=d5._build_symmetries(c);bonds={n:b._hopping_bonds(8,n) for n in ('H1','H2','H3','H4')};seed=int(c['workload']['neel_basis_hex'],16);initial,_,_=d5._reduced_column(d4,b,bonds,seed,syms);pool=set(initial);collector_calls=0
 second_seed=sorted(initial)[0];second,_,_=d5._reduced_column(d4,b,bonds,second_seed,syms);pool.update(second);collector_calls=1
 for candidate in sorted(initial):
  if len(pool)>=64: break
  child,_,_=d5._reduced_column(d4,b,bonds,candidate,syms);pool.update(child);collector_calls+=1
 reps=sorted(pool)[:64]
 if len(reps)<64: raise RuntimeError('two-seed fixture insufficient')
 rows=[]
 for rep in reps:
  started=time.monotonic_ns();col,orbit,dropped=d5._reduced_column(d4,b,bonds,rep,syms);rows.append({'representative_hex':hex(rep),'entries':len(col),'orbit':orbit,'dropped':dropped,'elapsed_ns':time.monotonic_ns()-started})
 payload=json.dumps([{k:v for k,v in row.items() if k!='elapsed_ns'} for row in rows],sort_keys=True,separators=(',',':')).encode();return {'status':'VERIFIED_D42_TWO_SEED_FIXED64_LOCAL_COST_SURVEY','fixture':'D5_CONTRACT_NEEL_PLUS_FIRST_CANONICAL_TARGET','seed_representative_hex':hex(seed),'second_seed_hex':hex(second_seed),'selection_collector_calls':collector_calls,'selected_representatives':len(reps),'rows':rows,'structural_rows_sha256':hashlib.sha256(payload).hexdigest(),'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'packed_q3_reads':0,'scientific_action_calls':2+collector_calls+len(reps),'full_53_scientific_execution_authorized':False,'full53_extrapolation_forbidden':True}
if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
