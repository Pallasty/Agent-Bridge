#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_external_intake_d28 as d28


class D28IntakeTests(unittest.TestCase):
    def test_empty_bundle_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = d28.preflight(Path(tmp))
            self.assertEqual(result["status"], "NO_GO_D28_EXTERNAL_SIGNED_BUNDLE_ABSENT")
            self.assertFalse(result["bundle_admissible"])
            self.assertEqual(result["scientific_action_calls"], 0)

    def test_present_files_do_not_authorize(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in d28.REQUIRED: (root / name).write_bytes(b"placeholder")
            result = d28.preflight(root)
            self.assertFalse(result["bundle_admissible"])
            self.assertFalse(result["full_53_scientific_execution_authorized"])


if __name__ == "__main__": unittest.main()
