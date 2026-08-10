import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d85", HERE / "fh_l8_d60_nvme_queue_control_gate_d85.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D85Tests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))

    def test_committed_result_is_exact_and_closed(self):
        result = MODULE.verify()
        self.assertEqual(result, MODULE.load(MODULE.RESULT))
        self.assertFalse(result["d82r_transaction_authorized"])
        self.assertFalse(result["full53_execution_authorized"])

    def test_irq_number_is_not_used_as_identity(self):
        snapshot = copy.deepcopy(self.contract["observed_snapshot"])
        snapshot["target_irq"] = 999
        result = MODULE.evaluate(self.contract, snapshot)
        self.assertEqual(result["target_irq_action"], "nvme0q15")
        self.assertFalse(result["target_irq_number_is_stable_identity"])

    def test_partial_controls_never_count_as_total_queue_control(self):
        snapshot = copy.deepcopy(self.contract["observed_snapshot"])
        snapshot["nvme_module_parameters"] = ["io_queue_depth", "write_queues", "poll_queues"]
        self.assertFalse(
            MODULE.evaluate(self.contract, snapshot)["supported_total_queue_parameter_present"]
        )

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["custom_kernel_authorized"] = True
        with self.assertRaisesRegex(MODULE.D85Error, "authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
