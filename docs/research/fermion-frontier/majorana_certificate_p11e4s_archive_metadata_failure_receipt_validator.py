#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];C=HERE/'majorana_certificate_p11e4s_archive_metadata_failure_receipt_contract.json';R=HERE/'majorana_certificate_p11e4s_archive_metadata_failure_receipt_record.json';P='ddd29e194cfc47666a998ead0a7a76c04cb9c42a';BASE='docs/research/fermion-frontier/'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.run(['git',*a],cwd=REPO,check=True,capture_output=True).stdout
def verify():
 c=json.loads(C.read_bytes());b=R.read_bytes();r=json.loads(b)
 if b.rstrip(b'\n')!=canon(r) or git('rev-parse','HEAD').decode().strip()!=P or c['required_direct_parent_commit']!=P:raise ValueError('lifecycle drift')
 x=c['P11_G17_custody'];raw=git('show',f"{P}:{BASE}{x['record_relative_path']}");g=json.loads(raw)
 if sha(raw)!=x['record_raw_sha256'] or g['disposition']!=x['expected_disposition'] or g['next_gate']!=x['expected_next_gate'] or g['scientific_authority']!='NONE':raise ValueError('G17 custody drift')
 a=c['current_authority']
 if any(v for k,v in a.items() if k!='scientific_authority') or a['scientific_authority']!='NONE':raise ValueError('authority reopened')
 i=c['future_input_identity'];root=Path(i['immutable_E3R_root']);mb=(root/i['tree_manifest_relative_path']).read_bytes()
 if sha(mb)!=i['tree_manifest_raw_sha256'] or [v for v in json.loads(mb) if v.get('relative_path')==i['archive_row']['relative_path']]!=[i['archive_row']]:raise ValueError('archive custody drift')
 receipt=Path(c['future_receipt_identity']['new_empty_receipt_root'])
 if receipt.exists() or receipt.is_symlink():raise ValueError('receipt root already exists')
 rp=c['future_receipt_identity'];required=[k for k,v in rp.items() if isinstance(v,bool)]
 if not all(rp[k] for k in required):raise ValueError('receipt policy drift')
 m=c['future_metadata_operation']
 bools=[v for v in m.values() if isinstance(v,bool)]
 if not all(bools) or m['maximum_member_headers']!=200000 or m['maximum_recorded_distinct_metadata_keys']!=512:raise ValueError('metadata policy drift')
 if not all(c['future_result_scope'].values()) or not c['future_operation_requires_independent_authorization'] or c['only_allowed_next_gate']!='P11-G18-ARCHIVE-METADATA-INSPECTION-AUTHORIZATION-V1':raise ValueError('result boundary drift')
 if r['parent_commit']!=P or r['next_gate']!=c['only_allowed_next_gate'] or r['scientific_authority']!='NONE' or r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('record drift')
 return {'next_gate':c['only_allowed_next_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
