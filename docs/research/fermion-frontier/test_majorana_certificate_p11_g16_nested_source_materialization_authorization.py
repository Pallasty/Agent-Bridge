#!/usr/bin/env python3
import importlib.util,json,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11_g16_nested_source_materialization_authorization_validator.py';S=importlib.util.spec_from_file_location('g16',P);M=importlib.util.module_from_spec(S);sys.modules['g16']=M;S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_pass(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_exactly_one_byte_level_run(self):
  x=json.loads(M.C.read_bytes())['operation_limits'];self.assertEqual(x['maximum_authorized_runs'],1);self.assertEqual(x['materialized_nesting_layers'],1);self.assertFalse(x['recursive_archive_extraction'])
 def test_source_semantics_and_E4_retry_closed(self):
  d=json.loads(M.C.read_bytes())['decision'];self.assertFalse(d['source_text_semantic_read_or_excerpt_authorized']);self.assertFalse(d['E4_analysis_retry_authorized']);self.assertEqual(d['scientific_authority'],'NONE')
 def test_target_root_is_absent_before_operation(self):self.assertFalse(Path(json.loads(M.C.read_bytes())['E4R_custody'] and json.loads(M.git('show',f"{M.P}:docs/research/fermion-frontier/majorana_certificate_p11e4r_nested_source_materialization_contract.json"))['future_operation_identity']['new_empty_derived_root']).exists())
if __name__=='__main__':unittest.main()
