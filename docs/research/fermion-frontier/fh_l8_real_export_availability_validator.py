#!/usr/bin/env python3
import json,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent;C=H/'fh_l8_real_export_availability_contract.json';R=H/'fh_l8_real_export_availability_result.json';P='514aff86488c13c695709ef474d4b67b87887fe7'
def verify():
 c=json.loads(C.read_bytes());r=json.loads(R.read_bytes());head=subprocess.run(['git','rev-parse','HEAD'],cwd=H.parents[2],check=True,capture_output=True,text=True).stdout.strip()
 if head!=P or c['required_direct_parent_commit']!=P or r['working_tree_commit']!=P: raise ValueError('lifecycle')
 if r['audit_disposition']!='NO_ADMISSIBLE_REAL_FIVE_ROUTE_EXPORT_SET_AVAILABLE' or r['candidate_counts'] or any(r['compiler_packages_available'].values()): raise ValueError('availability')
 if r['required_routes_missing']!=c['required_routes'] or r['synthetic_or_handwritten_sequence_accepted'] or r['scientific_authority']!='NONE' or r['next_state']!=c['expected_next_state']: raise ValueError('boundary')
 if c['boundaries']!={'network_access_authorized':False,'package_installation_authorized':False,'synthetic_or_handwritten_sequence_admissible':False,'source_or_hardware_claim_authorized':False}: raise ValueError('contract')
 return {'status':'PASS','next_state':r['next_state']}
if __name__=='__main__':
 try: print(json.dumps(verify(),sort_keys=True,separators=(',',':')))
 except Exception as e: print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
