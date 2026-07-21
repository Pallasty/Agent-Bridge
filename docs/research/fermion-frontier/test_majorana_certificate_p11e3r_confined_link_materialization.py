#!/usr/bin/env python3
import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11e3r_confined_link_materialization_validator.py';S=importlib.util.spec_from_file_location('e3r',P);M=importlib.util.module_from_spec(S);sys.modules['e3r']=M;S.loader.exec_module(M)
class TestE3R(unittest.TestCase):
 def test_contract_passes(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_confined_link(self):self.assertEqual(M.confined_target('pkg/Changes','Documentation/Changes'),'pkg/Documentation/Changes')
 def test_escape_absolute_cycle_and_dangling_fail(self):
  for fn,args in ((M.confined_target,('pkg/x','../../etc/passwd')),(M.confined_target,('pkg/x','/etc/passwd')),(M.verify_graph,({'pkg/a'},{'pkg/a':'a'})),(M.verify_graph,({'pkg/a'},{'pkg/x':'missing'}))):
   with self.subTest(args=args),self.assertRaises(ValueError):fn(*args)
if __name__=='__main__':unittest.main()
