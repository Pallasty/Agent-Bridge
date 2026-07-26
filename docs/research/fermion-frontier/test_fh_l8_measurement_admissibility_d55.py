import copy
import unittest

import fh_l8_measurement_admissibility_d55 as d55


class D55Tests(unittest.TestCase):
    def setUp(self):
        self.contract = d55.load(d55.CONTRACT)

    def test_committed_contract_and_result_verify(self):
        result = d55.verify()
        self.assertEqual(result["measurement_target_count"], 10)
        self.assertEqual(result["replay_count"], 2)
        self.assertFalse(result["full53_execution_authorized"])

    def test_missing_target_fails_closed(self):
        mutated = copy.deepcopy(self.contract)
        del mutated["target_decisions"]["filesystem_page_cache_accounting"]
        with self.assertRaises(d55.D55Error):
            d55.validate(mutated)

    def test_unknown_level_fails_closed(self):
        mutated = copy.deepcopy(self.contract)
        mutated["target_decisions"]["per_operation_host_time_ns"]["level"] = "BOUND"
        with self.assertRaises(d55.D55Error):
            d55.validate(mutated)

    def test_open_authority_fails_closed(self):
        mutated = copy.deepcopy(self.contract)
        mutated["authority"]["numeric_runtime_seconds_proven"] = True
        with self.assertRaises(d55.D55Error):
            d55.validate(mutated)

    def test_missing_basis_fails_closed(self):
        mutated = copy.deepcopy(self.contract)
        mutated["target_decisions"]["fraction_object_peak"]["basis"] = ""
        with self.assertRaises(d55.D55Error):
            d55.validate(mutated)


if __name__ == "__main__":
    unittest.main()
