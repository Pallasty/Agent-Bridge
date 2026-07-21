#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent;R=H/'majorana_certificate_p11_g21_post_restricted_pax_validation_governance_record.json';C=H/'majorana_certificate_p11_g21_post_restricted_pax_validation_governance_contract.json';P='0ae6f1154e480c15cb457412f34dec848957ee0a';BASE='docs/research/fermion-frontier/'
def verify():
 c=json.loads(C.read_bytes());r=json.loads(R.read_bytes());head=subprocess.run(['git','rev-parse','HEAD'],cwd=H.parents[2],check=True,capture_output=True,text=True).stdout.strip();raw=subprocess.run(['git','show',f"{P}:{BASE}{c['PAX_validation_custody']['result_relative_path']}"],cwd=H.parents[2],check=True,capture_output=True).stdout;e=json.loads(raw)
 if head!=P or hashlib.sha256(raw).hexdigest()!=c['PAX_validation_custody']['result_raw_sha256'] or e['headers_total']!=149865 or e['invalid_headers']!=149244 or e['payload_bytes']!=0 or e['source_text_read'] or e['disposition']!=c['PAX_validation_custody']['expected_disposition']:raise ValueError('custody')
 if len(c['findings'])!=5 or any(x['status']!='PASS' for x in c['findings']) or any(c['decision'][k] for k in ['PAX_retry_or_policy_relaxation_authorized','materialization_authorized','source_payload_or_semantic_read_authorized']) or c['decision']['scientific_authority']!='NONE':raise ValueError('boundary')
 return {'status':'PASS','next_gate':r['next_gate']}
if __name__=='__main__':
 try:print(json.dumps(verify(),sort_keys=True,separators=(',',':')))
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
