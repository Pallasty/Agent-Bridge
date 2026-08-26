import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]/"scripts/app-control-mobile-recovery-signer.py"
S=importlib.util.spec_from_file_location("mobile_signer",P); M=importlib.util.module_from_spec(S); S.loader.exec_module(M)
class T(unittest.TestCase):
 def setUp(self): self.p={"schema":M.REQ,"operation_id":"ab-episode-"+"1"*32,"record_sha256":"2"*64,"request_sha256":"3"*64,"workspace_sha256":"4"*64,"session_sha256":"5"*64,"requested_at_unix_seconds":1,"maximum_receipt_ttl_secs":300,"request_nonce":"6"*32}
 def export_line(self,profile="biometric_strong",key="pin"):
  return M.PREFIX+'{"schema":"'+M.EXPORT+'","status":"signed","receipt":"x.y","public_key_b64":"'+key+'","authentication_profile":"'+profile+'","private_key_exported":false,"action_invoked":false}'
 def test_argv_has_no_shell(self):
  a=M.request_argv("adb","serial",self.p,"biometric_strong")
  self.assertEqual(a[:4],["adb","-s","serial","shell"]); self.assertNotIn("sh",a)
  self.assertEqual(a[-3:],["--es","authentication_profile","biometric_strong"])
 def test_profile_configuration_is_required_and_es256_only(self):
  for environ in ({}, {M.PROFILE_ENV:"automatic",M.ALGORITHM_ENV:"ES256"},
                  {M.PROFILE_ENV:"biometric_strong"},
                  {M.PROFILE_ENV:"biometric_strong",M.ALGORITHM_ENV:"Ed25519"}):
   with self.subTest(environ=environ), self.assertRaises(ValueError): M.configured_profile(environ)
  self.assertEqual(M.configured_profile({M.PROFILE_ENV:"device_credential",M.ALGORITHM_ENV:"ES256"}),"device_credential")
 def test_export_requires_matching_profile_and_pinned_key(self):
  out=M.parse_export(self.export_line(),"pin","biometric_strong")
  self.assertTrue(out["public_key_bound"]); self.assertTrue(out["authentication_profile_bound"])
  with self.assertRaisesRegex(ValueError,"device_public_key_conflict"):
   M.parse_export(self.export_line(),"other","biometric_strong")
  with self.assertRaisesRegex(ValueError,"device_authentication_profile_conflict"):
   M.parse_export(self.export_line("device_credential"),"pin","biometric_strong")
 def test_export_missing_or_illegal_profile_is_rejected(self):
  without_profile=self.export_line().replace(',"authentication_profile":"biometric_strong"',"")
  with self.assertRaisesRegex(ValueError,"receipt_export_invalid"):
   M.parse_export(without_profile,"pin","biometric_strong")
  with self.assertRaisesRegex(ValueError,"invalid_authentication_profile"):
   M.parse_export(self.export_line(),"pin","automatic")
 def test_bad_binding_rejected(self):
  with self.assertRaises(ValueError): M.request_argv("adb","s",{**self.p,"record_sha256":"bad"},"biometric_strong")
  with self.assertRaises(ValueError): M.request_argv("adb","s",self.p,"automatic")
if __name__=="__main__": unittest.main()
