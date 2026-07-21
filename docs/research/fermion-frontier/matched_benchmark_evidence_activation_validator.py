#!/usr/bin/env python3
"""Verify the fail-closed external-evidence activation baseline for FH-L8."""
import hashlib,importlib.util,json,sys
from pathlib import Path

H=Path(__file__).resolve().parent
def load_json(name): return json.loads((H/name).read_bytes())
def load_module(name):
    p=H/f'{name}.py';s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def verify():
    c=load_json('matched_benchmark_evidence_activation_contract.json')
    if c['schema_version']!=1 or c['workload_fingerprint']!='FH_L8_UoverT8_tT1_half_filling': raise ValueError('contract')
    for name,expected in c['template_custody'].items():
        if hashlib.sha256((H/name).read_bytes()).hexdigest()!=expected: raise ValueError(f'custody:{name}')
    term=load_module('term_order_cross_route');campaign=load_module('measurement_campaign_validator');reference=load_module('reference_qualification_validator');native=load_module('native_transition_validator');surface=load_module('surface_place_route_validator');evidence=load_module('fermi_hubbard_evidence')
    evidence_contract=load_json('evidence_manifest_contract.json')
    statuses={
      'term_order':term.compare_routes(load_json('term_order_contract.json'),load_json('term_order_cross_route_template.json'))['status'],
      'campaign':campaign.assess_campaign(load_json('measurement_campaign_contract.json'),load_json('measurement_campaign_template.json'),evidence_contract)['status'],
      'reference':reference.validate_ledger(load_json('reference_qualification_contract.json'),load_json('reference_qualification_template.json'),artifact_root=H)['status'],
      'native_transition':native.validate_ledger(load_json('native_transition_contract.json'),load_json('native_transition_template.json'))['status'],
      'surface_place_route':surface.validate_ledger(load_json('surface_place_route_contract.json'),load_json('surface_place_route_template.json'))['status'],
      'matched_manifest':evidence.validate_manifest(evidence_contract,load_json('evidence_manifest_template.json'),load_json('term_order_contract.json'),load_json('first_step_contract.json'),load_json('native_transition_contract.json'),load_json('surface_place_route_contract.json'))['status']}
    if statuses!=c['current_baseline']['component_statuses']: raise ValueError(f'baseline:{statuses}')
    if len(c['admission_requirements'])!=8 or not all(c['prohibitions'].values()): raise ValueError('boundary')
    return {'status':c['current_baseline']['status'],'components':statuses}
if __name__=='__main__':
    try: print(json.dumps(verify(),sort_keys=True,separators=(',',':')))
    except Exception as e: print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
