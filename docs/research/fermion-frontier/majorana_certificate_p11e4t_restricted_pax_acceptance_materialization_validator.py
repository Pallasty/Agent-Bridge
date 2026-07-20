#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];C=HERE/'majorana_certificate_p11e4t_restricted_pax_acceptance_materialization_contract.json';R=HERE/'majorana_certificate_p11e4t_restricted_pax_acceptance_materialization_record.json';P='4014db37863af2cf7a3e8eba67e94768032c36ef';BASE='docs/research/fermion-frontier/'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def verify():
 c=json.loads(C.read_bytes());b=R.read_bytes();r=json.loads(b);head=subprocess.run(['git','rev-parse','HEAD'],cwd=REPO,check=True,capture_output=True,text=True).stdout.strip()
 if b.rstrip(b'\n')!=canon(r) or head!=P or c['required_direct_parent_commit']!=P:raise ValueError('lifecycle drift')
 x=c['P11_G19_custody'];raw=subprocess.run(['git','show',f"{P}:{BASE}{x['record_relative_path']}"],cwd=REPO,check=True,capture_output=True).stdout;g=json.loads(raw)
 if sha(raw)!=x['record_raw_sha256'] or g['disposition']!=x['expected_disposition'] or g['next_gate']!=x['expected_next_gate']:raise ValueError('G19 drift')
 a=c['current_authority'];p=c['future_restricted_PAX_policy']
 if any(v for k,v in a.items() if k!='scientific_authority') or a['scientific_authority']!='NONE' or p['exact_required_key_set']!=['atime','ctime','mtime','path'] or not all(v for k,v in p.items() if k!='exact_required_key_set'):raise ValueError('policy drift')
 if not all(c['future_materialization_repair'].values()) or not c['future_operation_requires_independent_authorization'] or c['only_allowed_next_gate']!='P11-G20-RESTRICTED-PAX-VALIDATION-AUTHORIZATION-V1':raise ValueError('boundary drift')
 if r['parent_commit']!=P or r['next_gate']!=c['only_allowed_next_gate'] or r['scientific_authority']!='NONE' or r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('record drift')
 return {'next_gate':c['only_allowed_next_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
