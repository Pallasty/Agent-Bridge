import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("fh_l8_intake", HERE / "fh_l8_external_evidence_intake.py")
INTAKE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(INTAKE)
SPEC = importlib.util.spec_from_file_location(
    "term_order_validator", HERE / "term_order_validator.py"
)
TERM_ORDER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(TERM_ORDER)


def load(name):
    return json.loads((HERE / name).read_text())


class ExternalEvidenceIntakeTests(unittest.TestCase):
    GROUP_ORDER = ["H1", "H2", "HU", "H3", "H4", "H4", "H3", "HU", "H2", "H1"]

    def setUp(self):
        self.contract = load("fh_l8_external_evidence_intake_contract.json")
        self.registry = load("fh_l8_external_evidence_registry_template.json")

    @staticmethod
    def _registration(route: str, artifact_path: str, sha256: str) -> dict:
        return {
            "artifact_path": artifact_path,
            "sha256": sha256,
            "source_url": "https://example.invalid/export",
            "release_or_commit": "v1",
            "evidence_class": "PRIMARY_EXTERNAL_RAW_EXPORT",
            "provenance_attestation": "custody statement",
            "compiler_identity": "compiler",
            "compiler_version": "1",
            "compiler_configuration_sha256": "1" * 64,
            "environment_lock_sha256": "2" * 64,
        }

    @staticmethod
    def _fixture_export(route: str, linear_size: int = 8, trotter_steps: int = 100) -> dict:
        terms_by_group = TERM_ORDER.expected_terms(linear_size)
        steps = []
        for step in range(trotter_steps):
            events = [
                {"group": group, "terms": list(terms_by_group[group])}
                for group in ExternalEvidenceIntakeTests.GROUP_ORDER
            ]
            steps.append({"step": step, "events": events})
        return {
            "schema_version": 1,
            "route": route,
            "linear_size": linear_size,
            "trotter_steps": trotter_steps,
            "workload_fingerprint": "FH_L8_UoverT8_tT1_half_filling",
            "steps": steps,
        }

    def test_empty_registry_is_incomplete(self):
        result = INTAKE.assess(self.contract, self.registry, HERE)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["routes"]["native_fermions"]["status"], "INCOMPLETE")

    def test_reused_artifact_hash_is_rejected_even_if_all_routes_report_admitted(self):
        registry = copy.deepcopy(self.registry)
        registry["artifacts"] = {
            route: self._registration(route, "missing.json", "a" * 64)
            for route in self.contract["required_routes"]
        }

        def admitted_with_reused_hash(contract, path_root, route, registration):
            return {
                "status": "ADMITTED",
                "errors": [],
                "warnings": [],
                "artifact_sha256": "d" * 64,
                "sequence_ready": True,
            }

        with patch.object(INTAKE, "route_admission", new=admitted_with_reused_hash):
            result = INTAKE.assess(self.contract, registry, HERE)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(any(
            "a raw artifact hash is reused by multiple routes" in error
            for error in result["errors"]
        ))

    def test_registration_route_field_mismatch_is_rejected(self):
        registration = self._registration(
            "native_fermions",
            "missing.json",
            "0" * 64,
        )
        registration["route"] = "dynamic_jw_local_grid_source_leading"
        registry = copy.deepcopy(self.registry)
        registry["artifacts"] = {"native_fermions": registration}
        result = INTAKE.assess(self.contract, registry, HERE)
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["routes"]["native_fermions"]["status"], "REJECTED")
        self.assertTrue(
            any(
                "registration route does not match route key" in error
                for error in result["routes"]["native_fermions"]["errors"]
            )
        )

    def test_route_key_mismatch_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = self._fixture_export("dynamic_jw_local_grid_source_leading")
            (root / "native.json").write_text(json.dumps(artifact, sort_keys=True))
            registration = self._registration(
                "native_fermions", "native.json", INTAKE.digest(root / "native.json")
            )
            registry = copy.deepcopy(self.registry)
            registry["artifacts"] = {"native_fermions": registration}
            result = INTAKE.assess(self.contract, registry, root)
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["routes"]["native_fermions"]["status"], "REJECTED")
        self.assertTrue(
            any(
                "artifact route does not match route key" in error
                for error in result["routes"]["native_fermions"]["errors"]
            )
        )

    def test_missing_custody_fields_are_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["artifacts"] = {"native_fermions": {"artifact_path": "missing.json"}}
        result = INTAKE.assess(self.contract, registry, HERE)
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["routes"]["native_fermions"]["status"], "REJECTED")

    def test_no_primary_external_declaration_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["artifacts"] = {"native_fermions": {
            "artifact_path": "missing.json", "sha256": "0" * 64,
            "source_url": "https://example.invalid/export", "release_or_commit": "v1",
            "provenance_attestation": "custody statement",
            "compiler_identity": "compiler", "compiler_version": "1",
            "compiler_configuration_sha256": "1" * 64, "environment_lock_sha256": "2" * 64
        }}
        result = INTAKE.assess(self.contract, registry, HERE)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(any(
            "PRIMARY_EXTERNAL_RAW_EXPORT" in error
            for error in result["routes"]["native_fermions"]["errors"]
        ))

    def test_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "artifact.json").write_text("{}")
            registry = copy.deepcopy(self.registry)
            registry["artifacts"] = {"native_fermions": {
                "artifact_path": "artifact.json", "sha256": "0" * 64,
                "source_url": "https://example.invalid/export", "release_or_commit": "v1",
                "evidence_class": "PRIMARY_EXTERNAL_RAW_EXPORT", "provenance_attestation": "custody statement",
                "compiler_identity": "compiler", "compiler_version": "1",
                "compiler_configuration_sha256": "1" * 64, "environment_lock_sha256": "2" * 64
            }}
            result = INTAKE.assess(self.contract, registry, root)
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("SHA-256 mismatch", result["routes"]["native_fermions"]["errors"][0])

    def test_path_escape_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["artifacts"] = {"native_fermions": {
            "artifact_path": "../outside.json", "sha256": "0" * 64,
            "source_url": "https://example.invalid/export", "release_or_commit": "v1",
            "evidence_class": "PRIMARY_EXTERNAL_RAW_EXPORT", "provenance_attestation": "custody statement",
            "compiler_identity": "compiler", "compiler_version": "1",
            "compiler_configuration_sha256": "1" * 64, "environment_lock_sha256": "2" * 64
        }}
        result = INTAKE.assess(self.contract, registry, HERE)
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("escapes", result["routes"]["native_fermions"]["errors"][0])


if __name__ == "__main__":
    unittest.main()
