#!/usr/bin/env python3
"""Inventory local FH-L8 compiler-export availability without fabricating evidence."""
import hashlib,importlib.util,json,subprocess,sys
from collections import Counter
from pathlib import Path

H=Path(__file__).resolve().parent
CONTRACT=H/'fh_l8_real_export_availability_contract.json'
def canon(x): return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':'))
def looks_like_real_export(path):
    if path.suffix!='.json': return False
    try: value=json.loads(path.read_bytes())
    except (OSError,ValueError,json.JSONDecodeError): return False
    if not isinstance(value,dict): return False
    required={'route','linear_size','trotter_steps','steps','compiler_identity','compiler_version','compiler_configuration_sha256','environment_lock_sha256','raw_artifact_sha256','provenance'}
    if not required.issubset(value): return False
    return isinstance(value['steps'],list) and any(isinstance(s,dict) and isinstance(s.get('events'),list) and any(isinstance(e,dict) and isinstance(e.get('terms'),list) for e in s['events']) for s in value['steps'])
def main():
    c=json.loads(CONTRACT.read_bytes());root=Path(c['audit_scope']['filesystem_root']);
    if not root.is_dir(): raise ValueError('audit root unavailable')
    files=subprocess.run(['rg','--files',str(root)],check=True,capture_output=True,text=True).stdout.splitlines()
    exts=set(c['audit_scope']['candidate_extensions']);candidates=[Path(p) for p in files if Path(p).suffix in exts and any(t in Path(p).name.lower() for t in ('export','compiler','term_order','dynamic_jw','fsn','fermi_hubbard'))]
    classes=Counter('real_export' if looks_like_real_export(p) else 'nonadmissible_candidate' for p in candidates)
    packages={name:bool(importlib.util.find_spec(name)) for name in c['audit_scope']['python_compiler_packages']}
    head=subprocess.run(['git','rev-parse','HEAD'],cwd=H.parents[2],check=True,capture_output=True,text=True).stdout.strip()
    out={'audit_disposition':'NO_ADMISSIBLE_REAL_FIVE_ROUTE_EXPORT_SET_AVAILABLE','working_tree_commit':head,'workload_fingerprint':c['workload_fingerprint'],'filesystem_root':str(root),'filename_inventory_only':True,'candidate_counts':dict(classes),'compiler_packages_available':packages,'required_routes_missing':c['required_routes'],'synthetic_or_handwritten_sequence_accepted':False,'next_state':c['expected_next_state'],'scientific_authority':'NONE'}
    print(canon(out))
if __name__=='__main__':
    try: main()
    except Exception as e: print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
