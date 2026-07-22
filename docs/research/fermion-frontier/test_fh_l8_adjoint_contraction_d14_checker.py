import copy
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("d14", HERE / "fh_l8_adjoint_contraction_d14_checker.py")
d14 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d14)


class D14Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((HERE / d14.CONTRACT_NAME).read_text())
        cls.result = json.loads((HERE / d14.RESULT_NAME).read_text())
        cls.evidence = d14.verify(cls.contract, cls.result)

    def test_design_boundary(self):
        self.assertTrue(self.evidence["moment_identity_certified"])
        self.assertFalse(self.evidence["generic_d2_word_reduction_certified"])
        self.assertFalse(self.evidence["q5_executed"])

    def test_neel_preconditions_and_metric(self):
        self.assertTrue(self.evidence["neel_eigenvalue_preconditions_certified"])
        self.assertTrue(self.evidence["signed_quotient_inner_product_certified"])
        self.assertFalse(self.evidence["observable_commutation_claimed"])

    def test_identity_mutation_rejected(self):
        bad = copy.deepcopy(self.contract)
        bad["hermitian_moment_identity"]["requires_observable_commutation"] = True
        with self.assertRaises(d14.VerificationError):
            d14.recompute(bad)

    def test_authority_mutation_rejected(self):
        bad = copy.deepcopy(self.contract)
        bad["authority_exclusions"]["ready_gate_eligible"] = True
        with self.assertRaises(d14.VerificationError):
            d14.recompute(bad)


if __name__ == "__main__":
    unittest.main()
