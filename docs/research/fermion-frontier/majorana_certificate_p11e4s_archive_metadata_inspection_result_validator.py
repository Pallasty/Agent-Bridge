#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];C=HERE/'majorana_certificate_p11e4s_archive_metadata_failure_receipt_contract.json';R=HERE/'majorana_certificate_p11e4s_archive_metadata_inspection_result.json';P='03096a3d747e77ddc81e7ffc9b31536f9a487aef'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def verify():
 r=json.loads(R.read_bytes());c=json.loads(C.read_bytes());head=subprocess.run(['git','rev-parse','HEAD'],cwd=REPO,check=True,capture_output=True,text=True).stdout.strip()
 if R.read_bytes().rstrip(b'\n')!=canon(r) or head!=P:raise ValueError('lifecycle drift')
 root=Path(r['receipt_root'])/'receipts';attempt=(root/'attempt.json').read_bytes();success=(root/'success.json').read_bytes()
 if (root/'failure.json').exists() or sha(attempt)!=r['attempt_receipt_raw_sha256'] or sha(success)!=r['success_receipt_raw_sha256']:raise ValueError('receipt drift')
 s=json.loads(success)
 if r['contract_raw_sha256']!=sha(C.read_bytes()) or r['authorization_commit']!=P or s['outcome']!='ARCHIVE_HEADER_METADATA_INSPECTION_COMPLETE':raise ValueError('custody drift')
 if r['header_counts']!=s['counts'] or sorted(r['metadata_key_names'])!=sorted(s['metadata_keys']) or r['source_payload_bytes_read']!=0 or r['source_text_semantically_read'] or r['verbatim_member_path_or_link_target_recorded'] or r['scientific_authority']!='NONE':raise ValueError('boundary drift')
 if r['header_counts']['pax_member_with_headers']!=r['header_counts']['headers_total'] or any(r['header_counts'][k] for k in ['gnu_sparse_typeflag','pax_sparse_keys','tarinfo_sparse_map','xattr_or_acl_or_capability_keys']):raise ValueError('classification drift')
 return {'headers_total':r['header_counts']['headers_total'],'next_gate':r['next_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
