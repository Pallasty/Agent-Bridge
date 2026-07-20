#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent;REPO=H.parents[2];C=H/'majorana_certificate_p11_g20r_execution_binding_authorization_contract.json';R=H/'majorana_certificate_p11_g20r_execution_binding_authorization_record.json';B=H/'majorana_certificate_p11g20r_pax_validation_execution_binding_contract.json';P='ee085a02c8cca5fd8d3d8c023529b38a556ac299'
def sha(b):return hashlib.sha256(b).hexdigest()
def verify():
 c=json.loads(C.read_bytes());r=json.loads(R.read_bytes());b=json.loads(B.read_bytes());head=subprocess.run(['git','rev-parse','HEAD'],cwd=REPO,check=True,capture_output=True,text=True).stdout.strip()
 if head!=P or c['required_direct_parent_commit']!=P or sha(B.read_bytes())!=c['binding_contract_raw_sha256']:raise ValueError('custody drift')
 if Path(b['future_execution_binding']['new_empty_receipt_root']).exists():raise ValueError('receipt root exists')
 if len(c['readiness_review'])!=5 or any(x['status']!='PASS' for x in c['readiness_review']):raise ValueError('readiness')
 d=c['decision'];l=c['operation_limits']
 if not d['archive_header_and_exact_PAX_value_validation_authorized'] or not d['new_receipt_root_creation_authorized'] or d['payload_read_extraction_materialization_authorized'] or d['source_root_creation_authorized'] or l['payload_bytes']!=0 or l['exact_keys']!=['atime','ctime','mtime','path']:raise ValueError('authority')
 if r['contract_raw_sha256']!=sha(C.read_bytes()) or r['parent_commit']!=P or r['scientific_authority']!='NONE':raise ValueError('record')
 return {'status':'PASS','next_gate':r['next_gate']}
if __name__=='__main__':
 try:print(json.dumps(verify(),sort_keys=True,separators=(',',':')))
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
