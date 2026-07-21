#!/usr/bin/env python3
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11e4r_nested_source_materialization_validator.py';S=importlib.util.spec_from_file_location('e4r',P);M=importlib.util.module_from_spec(S);sys.modules['e4r']=M;S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_pass(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_authority_closed(self):
  c=json.loads(M.C.read_bytes());self.assertTrue(all(v is False for k,v in c['current_authority'].items() if k!='scientific_authority'));self.assertEqual(c['current_authority']['scientific_authority'],'NONE')
 def test_one_layer_nonrecursive(self):
  x=json.loads(M.C.read_bytes())['resource_limits'];self.assertEqual(x['maximum_nesting_layers_materialized'],1);self.assertFalse(x['recursive_archive_discovery_or_extraction'])
 def test_new_root_and_independent_authorization(self):
  c=json.loads(M.C.read_bytes());self.assertNotEqual(c['future_operation_identity']['immutable_E3R_root'],c['future_operation_identity']['new_empty_derived_root']);self.assertTrue(c['future_operation_requires_independent_authorization'])
 def reject_contract(self,edit,message):
  original=M.C
  try:
   with tempfile.TemporaryDirectory() as directory:
    value=json.loads(original.read_bytes());edit(value);path=Path(directory)/'contract.json';path.write_text(json.dumps(value))
    M.C=path
    with self.assertRaisesRegex(ValueError,message):M.verify()
  finally:M.C=original
 def test_rejects_reopened_authority(self):self.reject_contract(lambda c:c['current_authority'].__setitem__('nested_archive_open_list_or_materialization_authorized',True),'authority reopened')
 def test_rejects_recursive_or_second_layer_scope(self):self.reject_contract(lambda c:c['resource_limits'].__setitem__('maximum_nesting_layers_materialized',2),'resource policy drift')
if __name__=='__main__':unittest.main()
