import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
PACKAGE = HERE / "fh_l8_external_evidence_handoff"
SPEC = importlib.util.spec_from_file_location(
    "fh_l8_handoff_checker",
    HERE / "fh_l8_external_evidence_handoff_checker.py",
)
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECKER)


class FHExternalEvidenceHandoffCheckerTests(unittest.TestCase):
    def test_committed_package_verifies(self):
        result = CHECKER.validate()
        self.assertEqual(
            result["status"],
            "VERIFIED_FH_L8_EXTERNAL_EVIDENCE_HANDOFF_PACKAGE",
        )
        self.assertEqual(result["route_count"], 5)
        self.assertEqual(result["routes_admitted"], 0)
        self.assertFalse(result["real_exports_included"])
        self.assertFalse(result["ready_for_benchmark"])

    def test_route_template_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "package"
            shutil.copytree(PACKAGE, package)
            template_path = (
                package
                / "native_fermions"
                / "registration.template.json"
            )
            template = json.loads(template_path.read_text(encoding="utf-8"))
            template["route"] = "fsn_standard_figure_candidate_fit"
            template_path.write_text(json.dumps(template), encoding="utf-8")

            result = CHECKER.validate(package)

        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(any("registration route mismatch" in error for error in result["errors"]))

    def test_nonblank_custody_placeholder_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "package"
            shutil.copytree(PACKAGE, package)
            template_path = (
                package
                / "fsn_ladder_figure_candidate_fit"
                / "registration.template.json"
            )
            template = json.loads(template_path.read_text(encoding="utf-8"))
            template["sha256"] = "0" * 64
            template_path.write_text(json.dumps(template), encoding="utf-8")

            result = CHECKER.validate(package)

        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(any("placeholder must remain blank" in error for error in result["errors"]))

    def test_unregistered_package_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "package"
            shutil.copytree(PACKAGE, package)
            (package / "unexpected.txt").write_text("unexpected", encoding="utf-8")

            result = CHECKER.validate(package)

        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("handoff package file set drift", result["errors"])


if __name__ == "__main__":
    unittest.main()
