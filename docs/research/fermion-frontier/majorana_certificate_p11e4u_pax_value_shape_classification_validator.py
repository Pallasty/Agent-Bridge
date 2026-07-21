#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent;C=H/'majorana_certificate_p11e4u_pax_value_shape_classification_contract.json';R=H/'majorana_certificate_p11e4u_pax_value_shape_classification_record.json';P='be6cef15713d938d596a177171aab385d456da0d'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def verify():
 c=json.loads(C.read_bytes());r=json.loads(R.read_bytes());head=subprocess.run(['git','rev-parse','HEAD'],cwd=H.parents[2],check=True,capture_output=True,text=True).stdout.strip()
 if head!=P or c['required_direct_parent_commit']!=P or r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('lifecycle')
 if any(v for k,v in c['current_authority'].items() if k!='scientific_authority') or c['current_authority']['scientific_authority']!='NONE':raise ValueError('authority')
 op=c['future_operation'];root=Path(c['future_input']['new_empty_receipt_root'])
 if root.exists() or op['payload_bytes_read_must_be_zero'] is not True or op['path_and_time_values_may_be_classified_but_not_recorded_verbatim'] is not True or c['future_input']['expected_keys']!=['atime','ctime','mtime','path']:raise ValueError('boundary')
 return {'status':'PASS','next_gate':c['only_allowed_next_gate']}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
