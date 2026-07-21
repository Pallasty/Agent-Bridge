#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path

H=Path(__file__).resolve().parent
C=H/'majorana_certificate_p11e4v_path_relation_proof_contract.json'
R=H/'majorana_certificate_p11e4v_path_relation_proof_record.json'
P='6dc3d4535c7c8ce7859ca755739adeaed9191158'
BASE='docs/research/fermion-frontier/'

def canon(x): return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def show(path): return subprocess.run(['git','show',f'{P}:{BASE}{path}'],cwd=H.parents[2],check=True,capture_output=True).stdout
def verify():
    c=json.loads(C.read_bytes());r=json.loads(R.read_bytes())
    head=subprocess.run(['git','rev-parse','HEAD'],cwd=H.parents[2],check=True,capture_output=True,text=True).stdout.strip()
    if head!=P or c['required_direct_parent_commit']!=P or r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)): raise ValueError('lifecycle')
    custody=c['G23_custody'];g=show(custody['governance_relative_path']);e=show(custody['result_relative_path'])
    if sha(g)!=custody['governance_raw_sha256'] or sha(e)!=custody['result_raw_sha256']: raise ValueError('custody')
    g=json.loads(g);e=json.loads(e)
    if g['decision']['disposition']!=custody['expected_disposition'] or g['decision']['materialization_authorized'] or e['shape_counts']['path']['other_relation']!=custody['expected_other_relation_count'] or e['payload_bytes']!=0 or e['source_text_read']: raise ValueError('premise')
    if any(v for k,v in c['current_authority'].items() if k!='scientific_authority') or c['current_authority']['scientific_authority']!='NONE': raise ValueError('authority')
    op=c['future_operation'];root=Path(c['future_input']['new_empty_receipt_root'])
    if root.exists() or op['payload_bytes_read_must_be_zero'] is not True or op['expected_eligible_member_count']!=54 or op['maximum_eligible_members']!=54 or not op['no_path_or_member_name_may_be_recorded_verbatim'] or not op['no_per_member_identifier_or_value_hash_may_be_recorded'] or op['allowed_aggregate_relation_classes'][-1]!='unsafe_or_unproven_relation': raise ValueError('boundary')
    if c['future_result']['no_policy_relaxation_or_materialization_in_same_operation'] is not True or c['only_allowed_next_gate']!='P11-G24-E4V-PATH-RELATION-PROOF-AUTHORIZATION-V1': raise ValueError('gate')
    return {'status':'PASS','next_gate':c['only_allowed_next_gate']}

if __name__=='__main__':
    try: print(canon(verify()).decode())
    except Exception as e: print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
