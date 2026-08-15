import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "eval" / "qwen3_token_boundary_probe.py"
SPEC = importlib.util.spec_from_file_location("qwen3_token_boundary_probe", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Holder:
    def method(self):
        return "class"


class TokenBoundaryProbeTests(unittest.TestCase):
    def test_select_case_requires_exactly_one_match(self):
        corpus = {"cases": [{"id": "a"}, {"id": "b"}]}
        self.assertEqual(MODULE.select_case(corpus, "b")["id"], "b")
        with self.assertRaises(ValueError):
            MODULE.select_case(corpus, "missing")

    def test_temporary_override_removes_instance_shadow(self):
        holder = Holder()
        restoration = {}
        with MODULE.temporary_instance_override(
            holder,
            "method",
            lambda: "override",
            restoration,
        ):
            self.assertEqual(holder.method(), "override")
            self.assertIn("method", holder.__dict__)
        self.assertEqual(holder.method(), "class")
        self.assertNotIn("method", holder.__dict__)
        self.assertTrue(restoration["method"])

    def test_temporary_override_restores_existing_instance_value(self):
        holder = Holder()
        original = lambda: "instance"
        holder.method = original
        restoration = {}
        with MODULE.temporary_instance_override(
            holder,
            "method",
            lambda: "override",
            restoration,
        ):
            self.assertEqual(holder.method(), "override")
        self.assertIs(holder.__dict__["method"], original)
        self.assertTrue(restoration["method"])

    def test_output_path_rejects_forbidden_root_and_existing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            forbidden = root / "model"
            forbidden.mkdir()
            with self.assertRaises(ValueError):
                MODULE.validate_output_path(forbidden / "report.json", [forbidden])
            existing = root / "existing.json"
            existing.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                MODULE.validate_output_path(existing, [forbidden])

    def test_exclusive_write_is_owner_only_and_non_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            MODULE.exclusive_write_json(output, {"status": "ok"})
            self.assertEqual(json.loads(output.read_text())["status"], "ok")
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                MODULE.exclusive_write_json(output, {"status": "again"})


if __name__ == "__main__":
    unittest.main()
