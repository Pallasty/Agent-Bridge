#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_resource_reservation_d24 as d24


def receipt():
    return {"schema_version": 1, "receipt_id": "slot-001", "issuer": "external-scheduler", "issued_unix_ns": 1,
            "not_before_unix_ns": 2, "not_after_unix_ns": 3, "exclusive_execution_slot": True, "isolation_id": "isolated-1",
            "scratch_free_bytes": d24.REQUIRED_SCRATCH_BYTES, "scratch_free_inodes": d24.REQUIRED_FILES,
            "memory_max_bytes": 1, "runtime_upper_bound_ns": 1, "immutable_receipt_sha256": "a" * 64}


class D24ReservationTests(unittest.TestCase):
    def test_absence_is_no_go(self):
        self.assertEqual(d24.no_receipt()["status"], "NO_GO_D24_EXTERNAL_RESOURCE_RECEIPT_ABSENT")

    def test_admissible_receipt_never_authorizes_action(self):
        result = d24.admit(receipt())
        self.assertTrue(result["receipt_admissible"])
        self.assertTrue(result["disk_and_file_reservation_satisfies_d23_guardrail"])
        self.assertFalse(result["full_53_scientific_execution_authorized"])

    def test_short_capacity_is_reported_not_authorized(self):
        value = receipt(); value["scratch_free_bytes"] -= 1
        self.assertFalse(d24.admit(value)["disk_and_file_reservation_satisfies_d23_guardrail"])

    def test_schema_drift_rejected(self):
        value = receipt(); value["extra"] = True
        with self.assertRaisesRegex(d24.ReservationError, "schema"):
            d24.admit(value)

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            path.write_text('{"schema_version":1,"schema_version":1}')
            with self.assertRaisesRegex(d24.ReservationError, "duplicate"):
                d24.load_receipt(path)


if __name__ == "__main__": unittest.main()
