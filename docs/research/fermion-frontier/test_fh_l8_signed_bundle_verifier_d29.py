#!/usr/bin/env python3
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent; sys.path.insert(0,str(HERE))
import fh_l8_micro_action_authorization_d27 as d27
import fh_l8_signed_bundle_verifier_d29 as d29

def signed(path, stem, value):
    message=path/f"{stem}.json"; message.write_bytes(json.dumps(value,sort_keys=True,separators=(',',':')).encode())
    private=path/f"{stem}-private.pem"; public=path/("approval-public-key.pem" if stem=="approval" else "resource-public-key.pem"); signature=path/f"{stem}.ed25519.sig"
    subprocess.run(["openssl","genpkey","-algorithm","ED25519","-out",str(private)],check=True,capture_output=True)
    subprocess.run(["openssl","pkey","-in",str(private),"-pubout","-out",str(public)],check=True,capture_output=True)
    subprocess.run(["openssl","pkeyutl","-sign","-inkey",str(private),"-rawin","-in",str(message),"-out",str(signature)],check=True,capture_output=True)
    private.unlink()

def bundle(path):
    req=d27.request(); approval={"schema_version":1,"request_id":req["request_id"],"approving_authority":"workspace-owner","approval_certificate_sha256":"a"*64,"approved_kernel_sha256":req["kernel"]["sha256"],"approved_action_limit":req["action_limit"],"approved_resource_ceiling":req["resource_ceiling"]}
    receipt={"schema_version":1,"request_id":req["request_id"],"resource_authority":"workspace-owner","receipt_id":"one","not_before_unix_ns":1,"not_after_unix_ns":2,"exclusive_execution_slot":"slot","isolation_id":"isolated","scratch_free_bytes":d29.MIN_SCRATCH_BYTES,"scratch_free_inodes":d29.MIN_INODES,"memory_max_bytes":536870912,"swap_max_bytes":0,"wall_seconds":180}
    signed(path,"approval",approval); signed(path,"resource-receipt",receipt)

class D29Tests(unittest.TestCase):
 def test_signed_exact_bundle_is_admissible_not_executed(self):
  with tempfile.TemporaryDirectory() as tmp:
   bundle(Path(tmp)); result=d29.verify(Path(tmp)); self.assertTrue(result["synthetic_kernel_fixture_authorized"]); self.assertEqual(result["scientific_action_calls"],0)
 def test_tampered_signed_bytes_fail_closed(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); bundle(root); (root/"approval.json").write_bytes(b"{}")
   with self.assertRaisesRegex(d29.BundleError,"signature"): d29.verify(root)
