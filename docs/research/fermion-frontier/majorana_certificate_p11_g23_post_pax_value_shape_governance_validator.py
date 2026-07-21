#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path

H=Path(__file__).resolve().parent
C=H/'majorana_certificate_p11_g23_post_pax_value_shape_governance.json'
R=H/'majorana_certificate_p11_g23_post_pax_value_shape_governance_record.json'
P='bf19ad9d2568f833b32d41ff14a85fd23018cd42'
BASE='docs/research/fermion-frontier/'
RESULT='majorana_certificate_p11e4u_pax_value_shape_result.json'
RAW_SHA='e226a3aadc17de2e0a2eabbaa350bd9ac54d3218ddcc0f40656ea8dd2032924d'

def verify():
    c=json.loads(C.read_bytes());r=json.loads(R.read_bytes())
    head=subprocess.run(['git','rev-parse','HEAD'],cwd=H.parents[2],check=True,capture_output=True,text=True).stdout.strip()
    raw=subprocess.run(['git','show',f'{P}:{BASE}{RESULT}'],cwd=H.parents[2],check=True,capture_output=True).stdout
    e=json.loads(raw)
    if head!=P or hashlib.sha256(raw).hexdigest()!=RAW_SHA: raise ValueError('custody')
    if e['headers_total']!=149865 or e['payload_bytes']!=0 or e['source_text_read'] or e['disposition']!='PAX_VALUE_SHAPE_CLASSIFICATION_COMPLETE': raise ValueError('execution')
    f=c['findings']; sc=e['shape_counts']['path']
    if f!={'headers_total':149865,'path_missing':149190,'path_equal_name':621,'path_other_relation':54,'all_time_values_decimal':True,'payload_bytes':0,'source_text_read':False}: raise ValueError('findings')
    if sc!={'equal_name':621,'missing':149190,'other_relation':54} or any(e['shape_counts'][k]!={'decimal':149865} for k in ('atime','ctime','mtime')): raise ValueError('shape_counts')
    d=c['decision']
    if d['disposition']!='REJECT_CURRENT_PAX_POLICY_AS_INSUFFICIENT_FOR_MATERIALIZATION' or any(d[k] for k in ('materialization_authorized','policy_relaxation_authorized')) or d['scientific_authority']!='NONE': raise ValueError('boundary')
    if r!={'disposition':d['disposition'],'finding_count':6,'finding_pass_count':6,'next_route':d['next_route'],'parent_commit':P,'schema_version':1,'scientific_authority':'NONE'}: raise ValueError('record')
    return {'status':'PASS','next_route':d['next_route']}

if __name__=='__main__':
    try: print(json.dumps(verify(),sort_keys=True,separators=(',',':')))
    except Exception as e: print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
