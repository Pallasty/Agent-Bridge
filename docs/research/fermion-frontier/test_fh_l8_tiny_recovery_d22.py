import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d22_checker", HERE / "fh_l8_tiny_recovery_d22_checker.py"
)
D22 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D22)
RUNNER = D22.RUNNER


@unittest.skipUnless(
    (HERE / "fh_l8_tiny_recovery_d22_contract.json").exists()
    and (HERE / "fh_l8_tiny_recovery_d22_result.json").exists(),
    "D22 contract/result not frozen yet",
)
class D22Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = D22.load_json(
            HERE / "fh_l8_tiny_recovery_d22_contract.json"
        )
        cls.result = D22.load_json(
            HERE / "fh_l8_tiny_recovery_d22_result.json"
        )

    def test_live_result_verifies(self):
        evidence = D22.verify(self.contract, self.result)
        self.assertTrue(evidence["live_tiny_fixture_replayed"])
        self.assertTrue(
            evidence["authority"]["tiny_fixture_fault_matrix_verified"]
        )

    def test_clean_and_resume_are_byte_identical(self):
        with tempfile.TemporaryDirectory(prefix="d22-test-") as temp:
            root = Path(temp)
            clean = RUNNER.run_tiny(self.contract, root / "clean")
            RUNNER.run_tiny(
                self.contract, root / "resume", stop_after_shards=1
            )
            resumed = RUNNER.run_tiny(
                self.contract, root / "resume", resume=True
            )
        self.assertEqual(clean["target"], resumed["target"])
        self.assertEqual(
            clean["terminal_receipt_sha256"],
            resumed["terminal_receipt_sha256"],
        )

    def test_full_fault_matrix(self):
        evidence = RUNNER.self_test(self.contract)
        self.assertEqual(
            evidence["fault_matrix"],
            {
                "gap": "FRONTIER_GAP",
                "overlap": "MANIFEST_DRIFT",
                "orphan": "ORPHAN",
                "hash_drift": "PARTITION_HASH",
                "stale_lock": "LOCK_BUSY",
                "partial_publication": "PARTIAL_PUBLICATION",
                "production_rejection": "PRODUCTION_NOT_AUTHORIZED",
            },
        )

    def test_production_rejected_before_checkpoint_read(self):
        with tempfile.TemporaryDirectory(prefix="d22-prod-") as temp:
            forbidden = Path(temp) / "does-not-exist.bin"
            with self.assertRaises(RUNNER.RunnerError) as caught:
                RUNNER.run_production(self.contract, forbidden)
        self.assertEqual(caught.exception.code, "PRODUCTION_NOT_AUTHORIZED")

    def test_authorization_mutation_rejected(self):
        bad = copy.deepcopy(self.contract)
        bad["production_authority"]["full_53_shard_execution_authorized"] = True
        with self.assertRaises(RUNNER.RunnerError):
            D22.recompute(bad)

    def test_protocol_mutation_rejected(self):
        bad = copy.deepcopy(self.contract)
        bad["protocol"]["exact_frontier_resume"] = False
        with self.assertRaises(RUNNER.RunnerError):
            D22.recompute(bad)

    def test_result_authority_mutation_rejected(self):
        bad = copy.deepcopy(self.result)
        bad["authority"]["full_53_shard_execution_authorized"] = True
        with self.assertRaises(D22.VerificationError):
            D22.verify(self.contract, bad)

    def test_float_rejected(self):
        with self.assertRaises(D22.VerificationError):
            json.loads('{"x":1.5}', parse_float=D22._reject_float)

    def test_duplicate_key_rejected(self):
        with self.assertRaises(D22.VerificationError):
            json.loads('{"x":1,"x":2}', object_pairs_hook=D22._pairs)


if __name__ == "__main__":
    unittest.main()
