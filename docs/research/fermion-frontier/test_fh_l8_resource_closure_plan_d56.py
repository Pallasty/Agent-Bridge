import copy
import unittest

import fh_l8_resource_closure_plan_d56 as d56


class D56Tests(unittest.TestCase):
    def setUp(self):
        self.contract = d56.load(d56.CONTRACT)

    def test_committed_plan_verifies(self):
        result = d56.verify()
        self.assertEqual(result["work_package_count"], 6)
        self.assertEqual(result["parallel_gate_count_after_d57"], 3)
        self.assertFalse(result["full53_execution_authorized"])

    def test_requirement_mapping_fails_closed(self):
        mutated = copy.deepcopy(self.contract)
        mutated["work_packages"][0]["closes_requirement"] = "invented"
        with self.assertRaises(d56.D56Error):
            d56.validate(mutated)

    def test_forward_dependency_fails_closed(self):
        mutated = copy.deepcopy(self.contract)
        mutated["work_packages"][0]["depends_on"] = [
            "D58_LIVE_ALLOCATION_CLASS_STATIC_BOUND"
        ]
        with self.assertRaises(d56.D56Error):
            d56.validate(mutated)

    def test_incomplete_join_fails_closed(self):
        mutated = copy.deepcopy(self.contract)
        mutated["work_packages"][4]["depends_on"].pop()
        with self.assertRaises(d56.D56Error):
            d56.validate(mutated)

    def test_open_authority_fails_closed(self):
        mutated = copy.deepcopy(self.contract)
        mutated["authority"]["full53_execution_authorized"] = True
        with self.assertRaises(d56.D56Error):
            d56.validate(mutated)

    def test_phase_stage_and_operation_coverage_fail_closed(self):
        variants = []
        phase = copy.deepcopy(self.contract)
        phase["coverage_matrix"]["D51_lifetime_phases"].pop("target_publication")
        variants.append(phase)
        stage = copy.deepcopy(self.contract)
        stage["coverage_matrix"]["D52_adapter_stages"]["invoke_bound_reduced_column"] = []
        variants.append(stage)
        operation = copy.deepcopy(self.contract)
        operation["coverage_matrix"]["D52_operation_bounds"].pop("source_records")
        variants.append(operation)
        for mutated in variants:
            with self.assertRaises(d56.D56Error):
                d56.validate(mutated)

    def test_future_gate_authority_fails_closed(self):
        mutated = copy.deepcopy(self.contract)
        mutated["future_gate_authority_rules"][
            "D59_PRODUCTION_IO_PAGE_CACHE_BOUND"
        ]["production_io_execution_authorized_by_D56"] = True
        with self.assertRaises(d56.D56Error):
            d56.validate(mutated)


if __name__ == "__main__":
    unittest.main()
