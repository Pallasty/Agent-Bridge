import importlib.util
import unittest
from pathlib import Path

H = Path(__file__).resolve().parent
s = importlib.util.spec_from_file_location("d79", H / "fh_l8_runtime_scope_lock_d79.py")
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)  # type: ignore[misc]


class D79Tests(unittest.TestCase):
    def test_verify(self):
        self.assertEqual(m.verify()["status"], "VERIFIED_D79_RUNTIME_SCOPE_LOCK_INCOMPLETE")
        self.assertEqual(m.verify()["scope_mode_admissible"], False)
        self.assertFalse(m.verify()["authority"]["runtime_lock_precommitted"])

    def test_probe_modes_captured(self):
        self.assertEqual(m.verify()["service_memory_max"], "1073741824")
        self.assertEqual(m.verify()["scope_probe_exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
