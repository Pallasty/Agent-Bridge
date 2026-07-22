import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("fh_l8_intake", HERE / "fh_l8_external_evidence_intake.py")
INTAKE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(INTAKE)


def load(name):
    return json.loads((HERE / name).read_text())


class ExternalEvidenceIntakeTests(unittest.TestCase):
    def setUp(self):
        self.contract = load("fh_l8_external_evidence_intake_contract.json")
        self.registry = load("fh_l8_external_evidence_registry_template.json")

    def test_empty_registry_is_incomplete(self):
        result = INTAKE.assess(self.contract, self.registry, HERE)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["routes"]["native_fermions"]["status"], "INCOMPLETE")

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
