#!/usr/bin/env python3
import argparse,copy,hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];REV='scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_custody_chain_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py';DOMAIN='AB_T17_CUSTODY_AUTHORITY_CHECK_V1'
def mod():
 p=ROOT/REV;s=importlib.util.spec_from_file_location('_r',p);m=importlib.util.module_from_spec(s);sys.modules['_r']=m;s.loader.exec_module(m);return m
def evaluate():
 m=mod();o=m.load(m.OWNER);s=m.load(m.SEMANTIC);p=m.load(m.T16);base=m.validate(o,s,p);ops=[lambda o,s,p:o.update(decision='x'),lambda o,s,p:o.update(next_unit='x'),lambda o,s,p:o['predecessor'].update(t16_implemented=False),lambda o,s,p:o['contract'].update(public_input_count=27),lambda o,s,p:o['contract']['request_fields'].pop(),lambda o,s,p:o['contract']['match_fields'].pop(),lambda o,s,p:o['contract']['profiles'].reverse(),lambda o,s,p:o['contract']['profiles'][0].update(t16_receipt_content_sha256='0'*64),lambda o,s,p:o['contract']['profiles'][0].update(segment_count=5),lambda o,s,p:o['authority'].update(consumed=True),lambda o,s,p:o['boundary'].update(t17_implemented=True),lambda o,s,p:o['boundary'].update(t18_authorized=True),lambda o,s,p:o['resources'].update(network=True),lambda o,s,p:next(x for x in s['threat_cases']if x['case_id']=='T17').update(threat_class='X'),lambda o,s,p:p['boundary'].update(t16_implemented_after_integrated_full=False)]
 for i,op in enumerate(ops):
  a,b,c=copy.deepcopy(o),copy.deepcopy(s),copy.deepcopy(p);op(a,b,c)
  try:m.validate(a,b,c)
  except Exception:continue
  raise ValueError(f'mutation accepted: {i}')
 r={'schema':'agent_bridge.biocortex.custody_authority.check.v0','status':base['status'],'reviewer_stdout_line_count':len(base),'directed_negative_test_count':len(ops),'public_input_count':28,'profile_count':2,'custody_segment_count':6,'match_dimension_count':4,'t17_implemented':False,'authority_consumed':False,'runtime_authority':False,'provider_authority':False,'owner_raw_sha256':base['owner_raw_sha256'],'reviewer_raw_sha256':hashlib.sha256((ROOT/REV).read_bytes()).hexdigest(),'semantic_raw_sha256':base['semantic_raw_sha256'],'t16_manifest_raw_sha256':base['t16_manifest_raw_sha256'],'content_sha256':'0'*64};x=dict(r);del x['content_sha256'];r['content_sha256']=hashlib.sha256(DOMAIN.encode()+b'\0'+json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest();return ''.join(f"{k}\t{str(v).lower()if type(v)is bool else v}\n"for k,v in r.items())
def main():
 a=argparse.ArgumentParser();a.add_argument('--self-test',action='store_true');n=a.parse_args()
 try:o=evaluate();sys.stdout.write('self_test_contract\tpass\nself_test_mutations\tpass\nself_test_boundary\tpass\n'if n.self_test else o);return 0
 except Exception as e:print(f'check_error\t{e}',file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
