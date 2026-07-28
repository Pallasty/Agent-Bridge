import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fh_l8_object_cost_measurement_d54r_result_checker as checker


class D54RResultCheckerTests(unittest.TestCase):
    def test_receipt_identity_is_ordered_and_complete(self):
        with tempfile.TemporaryDirectory() as root:
            samples = Path(root) / "samples"
            samples.mkdir()
            (samples / "000.json").write_bytes(b"first")
            (samples / "001.json").write_bytes(b"second")
            individual = [
                hashlib.sha256(value).hexdigest() for value in (b"first", b"second")
            ]
            expected = hashlib.sha256("\n".join(individual).encode("ascii")).hexdigest()
            self.assertEqual(checker.receipt_set_identity(Path(root), 2), expected)

    def test_committed_result_mismatch_fails_closed(self):
        with patch.object(checker, "observed_result", return_value={"status": "observed"}):
            with self.assertRaises(checker.ResultError):
                checker.verify({"status": "different"})

    def test_exact_result_verifies(self):
        observed = {"status": "observed"}
        with patch.object(checker, "observed_result", return_value=observed):
            self.assertEqual(checker.verify(observed), observed)


if __name__ == "__main__":
    unittest.main()
