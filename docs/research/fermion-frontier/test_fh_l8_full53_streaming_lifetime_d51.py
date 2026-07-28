import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fh_l8_d51",
    HERE / "fh_l8_full53_streaming_lifetime_d51.py",
)
D51 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(D51)


class FHFull53StreamingLifetimeD51Tests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(D51.CONTRACT.read_text(encoding="utf-8"))

    def _mutated_check(self, mutate):
        contract = copy.deepcopy(self.contract)
        mutate(contract)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            return D51.check(path)

    def test_committed_design_verifies_and_remains_non_authoritative(self):
        result = D51.check()
        self.assertEqual(
            result["status"],
            "VERIFIED_D51_STREAMING_LIFETIME_AND_WORK_UNIT_DESIGN_RESOURCE_NOT_READY",
        )
        self.assertEqual(result["design_required_scratch_bytes"], 3_110_572_064)
        self.assertEqual(result["d23_shortfall_bytes"], 359_759_114)
        self.assertEqual(result["known_buffer_subtotal_bytes"], 35_520_512)
        self.assertEqual(result["merge_record_reads_upper"], 95_894_550)
        self.assertEqual(result["merge_heap_comparisons_design_upper"], 958_945_500)
        self.assertFalse(result["numeric_peak_memory_proven"])
        self.assertFalse(result["numeric_runtime_seconds_proven"])
        self.assertFalse(result["full53_execution_authorized"])
        committed = json.loads(
            (HERE / "fh_l8_full53_streaming_lifetime_d51_result.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(result, committed)

    def test_scratch_arithmetic_drift_fails_closed(self):
        with self.assertRaisesRegex(D51.D51Error, "scratch lifetime arithmetic drift"):
            self._mutated_check(
                lambda contract: contract["disk_lifetime_design"].update(
                    {"design_required_scratch_bytes": 3_110_572_063}
                )
            )

    def test_runtime_work_unit_drift_fails_closed(self):
        with self.assertRaisesRegex(D51.D51Error, "runtime work-unit arithmetic drift"):
            self._mutated_check(
                lambda contract: contract["runtime_work_units"].update(
                    {"merge_record_reads_upper": 1}
                )
            )

    def test_known_buffer_drift_fails_closed(self):
        with self.assertRaisesRegex(D51.D51Error, "known-buffer arithmetic drift"):
            self._mutated_check(
                lambda contract: contract["streaming_design"].update(
                    {"known_buffer_subtotal_bytes": 1}
                )
            )

    def test_open_authority_fails_closed(self):
        with self.assertRaisesRegex(D51.D51Error, "authority unexpectedly open"):
            self._mutated_check(
                lambda contract: contract["authority"].update(
                    {"full53_execution_authorized": True}
                )
            )

    def test_source_pin_drift_fails_closed(self):
        with self.assertRaisesRegex(D51.D51Error, "source pin mismatch"):
            self._mutated_check(
                lambda contract: contract["source_pins"].update(
                    {"fh_l8_full53_kernel_fanout_d50_result.json": "0" * 64}
                )
            )


if __name__ == "__main__":
    unittest.main()
