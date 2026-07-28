import copy
import unittest
import fh_l8_live_allocation_bound_d58 as d58


class D58Tests(unittest.TestCase):
    def setUp(self): self.contract = d58.load(d58.CONTRACT)
    def test_committed_inventory_verifies(self):
        result = d58.verify()
        self.assertEqual(result["bound_variable_count"], 8)
        self.assertFalse(result["numeric_peak_memory_proven"])
    def test_missing_variable_fails_closed(self):
        value = copy.deepcopy(self.contract)
        value["bound_variables"].pop()
        with self.assertRaises(d58.D58Error): d58.validate(value)
    def test_merge_heap_lifetime_fails_closed(self):
        value = copy.deepcopy(self.contract)
        value["phase_expressions"]["partition_external_merge"].remove("A_sort_key_heap")
        with self.assertRaises(d58.D58Error): d58.validate(value)
    def test_open_authority_fails_closed(self):
        value = copy.deepcopy(self.contract)
        value["authority"]["numeric_peak_memory_proven"] = True
        with self.assertRaises(d58.D58Error): d58.validate(value)


if __name__ == "__main__": unittest.main()
