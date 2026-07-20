#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];C=HERE/'majorana_certificate_p11_g19_post_archive_metadata_inspection_governance_contract.json';R=HERE/'majorana_certificate_p11_g19_post_archive_metadata_inspection_governance_record.json';P='768be532aa3d550408b16a5988eac8b90925bb0a';BASE='docs/research/fermion-frontier/'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def verify():
 c=json.loads(C.read_bytes());b=R.read_bytes();r=json.loads(b);head=subprocess.run(['git','rev-parse','HEAD'],cwd=REPO,check=True,capture_output=True,text=True).stdout.strip()
 if b.rstrip(b'\n')!=canon(r) or head!=P or c['required_direct_parent_commit']!=P:raise ValueError('lifecycle drift')
 x=c['E4S_custody'];raw=subprocess.run(['git','show',f"{P}:{BASE}{x['result_relative_path']}"],cwd=REPO,check=True,capture_output=True).stdout;e=json.loads(raw)
 if sha(raw)!=x['result_raw_sha256'] or e['disposition']!=x['expected_disposition'] or e['next_gate']!=x['expected_next_gate']:raise ValueError('E4S custody drift')
 h=e['header_counts'];zero=['gnu_sparse_typeflag','pax_extended','pax_global','pax_sparse_keys','tarinfo_sparse_map','xattr_or_acl_or_capability_keys']
 if h['headers_total']!=149865 or h['pax_member_with_headers']!=149865 or any(h[k] for k in zero) or sorted(e['metadata_key_names'])!=['atime','ctime','mtime','path'] or e['source_payload_bytes_read']!=0 or e['source_text_semantically_read'] or e['verbatim_member_path_or_link_target_recorded']:raise ValueError('metadata boundary drift')
 d=c['decision'];closed=[k for k,v in d.items() if isinstance(v,bool)]
 if any(d[k] for k in closed) or d['scientific_authority']!='NONE' or not all(c['future_design_requirements'].values()):raise ValueError('authority drift')
 if len(c['findings'])!=5 or any(v['status']!='PASS' for v in c['findings']) or r['parent_commit']!=P or r['next_gate']!=d['only_allowed_next_gate'] or r['finding_pass_count']!=5 or r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('record drift')
 return {'next_gate':d['only_allowed_next_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
