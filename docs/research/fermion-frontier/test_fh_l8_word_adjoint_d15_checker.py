import copy
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("d15", HERE / "fh_l8_word_adjoint_d15_checker.py")
d15 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d15)


class D15Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((HERE / d15.CONTRACT_NAME).read_text())
        cls.result = json.loads((HERE / d15.RESULT_NAME).read_text())
        cls.evidence = d15.verify(cls.contract, cls.result)

    def test_exact_decomposition_and_metric(self):
        self.assertTrue(self.evidence["exact_word_decomposition_certified"])
        self.assertTrue(self.evidence["signed_quotient_contraction_identity_certified"])
        self.assertTrue(self.evidence["left_transfer_requires_metric_hermiticity"])

    def test_no_unsafe_word_acceptance(self):
        self.assertFalse(self.evidence["generic_unpinned_or_truncated_word_accepted"])
        self.assertFalse(self.evidence["contraction_executed"])

    def test_missing_reversal_rejected(self):
        bad = copy.deepcopy(self.contract)
        bad["mandatory_rejections"]["missing_adjoint_reversal_witness"] = False
        with self.assertRaises(d15.VerificationError):
            d15.recompute(bad)

    def test_metric_mutation_rejected(self):
        bad = copy.deepcopy(self.contract)
        bad["quotient_contraction"]["metric"] = "identity"
        with self.assertRaises(d15.VerificationError):
            d15.recompute(bad)


if __name__ == "__main__":
    unittest.main()
