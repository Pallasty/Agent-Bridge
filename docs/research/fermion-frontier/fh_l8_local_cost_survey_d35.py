#!/usr/bin/env python3
"""D32 bounded, deterministic local D5 cost survey; no packed-q3 access."""
from __future__ import annotations
import hashlib, importlib.util, json, resource
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load(name, filename):
 s=importlib.util.spec_from_file_location(name,HERE/filename);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def run():
 resource.setrlimit(resource.RLIMIT_AS,(536_870_912,536_870_912))
 d5=load('d32_d5','fh_l8_symmetry_orbit_quotient_d5_checker.py');d4=load('d32_d4','fh_l8_scalar_supremum_d4_checker.py');b=load('d32_b','hubbard_strang_commutator_checker.py')
 c=json.loads((HERE/'fh_l8_symmetry_orbit_quotient_d5_contract.json').read_text());syms,_=d5._build_symmetries(c);bonds={n:b._hopping_bonds(8,n) for n in ('H1','H2','H3','H4')}
 neel=int(c['workload']['neel_basis_hex'],16); seed,_,_=d5._reduced_column(d4,b,bonds,neel,syms)
 reps=sorted(seed)[:16]; rows=[]
 for rep in reps:
  col,orbit,dropped=d5._reduced_column(d4,b,bonds,rep,syms)
  rows.append({'representative_hex':hex(rep),'entries':len(col),'orbit':orbit,'dropped':dropped})
 payload=json.dumps(rows,sort_keys=True,separators=(',',':')).encode()
 return {'status':'VERIFIED_D32_BOUNDED_LOCAL_COST_SURVEY','seed_representative_hex':hex(neel),'selected_representatives':len(reps),'rows':rows,'rows_sha256':hashlib.sha256(payload).hexdigest(),'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'packed_q3_reads':0,'scientific_action_calls':1+len(reps),'full_53_scientific_execution_authorized':False}
if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
