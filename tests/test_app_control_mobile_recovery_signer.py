import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]/"scripts/app-control-mobile-recovery-signer.py"
S=importlib.util.spec_from_file_location("mobile_signer",P); M=importlib.util.module_from_spec(S); S.loader.exec_module(M)
class T(unittest.TestCase):
 def setUp(self): self.p={"schema":M.REQ,"operation_id":"ab-episode-"+"1"*32,"record_sha256":"2"*64,"request_sha256":"3"*64,"workspace_sha256":"4"*64,"session_sha256":"5"*64,"requested_at_unix_seconds":1,"maximum_receipt_ttl_secs":300,"request_nonce":"6"*32}
 def test_argv_has_no_shell(self):
  a=M.request_argv("adb","serial",self.p); self.assertEqual(a[:4],["adb","-s","serial","shell"]); self.assertNotIn("sh",a)
 def test_export_requires_pinned_key(self):
  line=M.PREFIX+'{"schema":"'+M.EXPORT+'","status":"signed","receipt":"x.y","public_key_b64":"pin","private_key_exported":false,"action_invoked":false}'
  self.assertTrue(M.parse_export(line,"pin")["public_key_bound"])
  with self.assertRaises(ValueError): M.parse_export(line,"other")
 def test_bad_binding_rejected(self):
  with self.assertRaises(ValueError): M.request_argv("adb","s",{**self.p,"record_sha256":"bad"})
if __name__=="__main__": unittest.main()
