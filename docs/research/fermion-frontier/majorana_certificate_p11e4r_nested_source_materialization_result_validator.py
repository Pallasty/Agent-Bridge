#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
C=HERE/'majorana_certificate_p11e4r_nested_source_materialization_contract.json';R=HERE/'majorana_certificate_p11e4r_nested_source_materialization_result.json';P='0d875167aa289de0e2eb84f1beb5195335950e50'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def verify():
 r=json.loads(R.read_bytes());c=json.loads(C.read_bytes())
 head=subprocess.run(['git','rev-parse','HEAD'],cwd=REPO,check=True,capture_output=True,text=True).stdout.strip()
 if R.read_bytes().rstrip(b'\n')!=canon(r) or head!=P:raise ValueError('lifecycle drift')
 if r['contract_raw_sha256']!=sha(C.read_bytes()) or r['authorization_commit']!=P:raise ValueError('custody drift')
 if r['disposition']!='STOPPED_FAIL_CLOSED_DURING_PREWRITE_METADATA_PREFLIGHT' or r['failure']['code']!='PAX_OR_SPARSE_MEMBER_REJECTED':raise ValueError('failure classification drift')
 if any(r[k] for k in ['derived_root_created','staging_directory_created','tree_manifest_created','source_text_semantically_read']):raise ValueError('prewrite boundary drift')
 if r['scientific_authority']!='NONE' or r['next_gate']!='P11-G17-POST-NESTED-SOURCE-MATERIALIZATION-GOVERNANCE-V1':raise ValueError('authority drift')
 if Path(c['future_operation_identity']['new_empty_derived_root']).exists():raise ValueError('unexpected derived root')
 return {'derived_root_created':False,'next_gate':r['next_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
