import importlib.util
import sys
import unittest
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d57", HERE / "fh_l8_production_streaming_adapter_d57.py"
)
D57 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = D57
SPEC.loader.exec_module(D57)


def source_record(rep=7, amplitude=-3, orbit=8, rank=11):
    return D57.SOURCE_RECORD.pack(rep.to_bytes(16, "big"), amplitude, orbit, 0, 0, rank)


class Sink:
    def __init__(self, fail=False):
        self.rows = []
        self.fail = fail

    def emit(self, partition, payload):
        if self.fail:
            raise RuntimeError("synthetic sink failure")
        self.rows.append((partition, payload))


class D57Tests(unittest.TestCase):
    def test_decode_and_spill_formats_are_exact(self):
        row = D57.decode_one_source_record(source_record())
        self.assertEqual((row.representative, row.amplitude, row.orbit_size, row.insertion_rank),
                         (7, -3, 8, 11))
        spill = D57.SpillRow(19, -24)
        raw = D57.encode_spill_record(spill)
        self.assertEqual(len(raw), 32)
        self.assertEqual(D57.decode_spill_record(raw), spill)

    def test_malformed_source_and_spill_fail_closed(self):
        for raw in (b"", b"x" * 31, source_record(amplitude=0), source_record(orbit=2)):
            with self.assertRaises(D57.AdapterError):
                D57.decode_one_source_record(raw)
        bad = bytearray(D57.encode_spill_record(D57.SpillRow(1, 2)))
        bad[-1] = 1
        with self.assertRaises(D57.AdapterError):
            D57.decode_spill_record(bytes(bad))

    def test_one_source_emits_and_releases_column(self):
        column = {9: Fraction(1, 8), 4: Fraction(-1, 4)}
        sink = Sink()
        receipt = D57.process_one_source(source_record(), lambda _: column, sink)
        self.assertEqual(receipt.column_entries, 2)
        self.assertEqual(receipt.spill_records, 2)
        self.assertTrue(receipt.column_released_before_return)
        self.assertEqual(column, {})
        self.assertEqual(len(sink.rows), 2)

    def test_failure_still_releases_column(self):
        column = {9: Fraction(1, 8)}
        with self.assertRaises(RuntimeError):
            D57.process_one_source(source_record(), lambda _: column, Sink(fail=True))
        self.assertEqual(column, {})

    def test_column_cap_and_fraction_grid_fail_closed(self):
        oversized = {index: Fraction(1, 8) for index in range(226)}
        with self.assertRaises(D57.AdapterError):
            D57.process_one_source(source_record(), lambda _: oversized, Sink())
        self.assertEqual(oversized, {})
        off_grid = {1: Fraction(1, 5)}
        with self.assertRaises(D57.AdapterError):
            D57.process_one_source(source_record(), lambda _: off_grid, Sink())
        self.assertEqual(off_grid, {})

    def test_merge_and_publication_plans_are_bounded(self):
        levels = D57.merge_batches(tuple(f"run-{index}" for index in range(53)))
        self.assertEqual([len(level) for level in levels], [2, 1])
        self.assertTrue(all(len(batch) <= 32 for level in levels for batch in level))
        order = D57.publication_order()
        self.assertEqual(len(order), 259)
        self.assertEqual(order[0], "partition-000.bin")
        self.assertEqual(order[-1], "terminal-receipt.json")

    def test_full53_entrypoint_is_fail_closed(self):
        self.assertFalse(D57.FULL53_EXECUTION_AUTHORIZED)
        with self.assertRaises(D57.Full53Unauthorized):
            D57.run_full53()


if __name__ == "__main__":
    unittest.main()
