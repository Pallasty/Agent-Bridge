#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_kernel_resource_audit_d25 as d25


def source_fixture(root: Path) -> Path:
    """Copy only D25's audited text/JSON surface, never packed-q3 bytes."""
    root.mkdir()
    names = [d25.CONTRACT.name, *d25.SOURCES.values()]
    for name in names:
        (root / name).write_bytes((HERE / name).read_bytes())
    return root


class D25KernelResourceAuditTests(unittest.TestCase):
    def test_pinned_audit_is_no_go_without_q3_read_or_action(self):
        result = d25.audit()
        self.assertEqual(result["status"], "NO_GO_D25_FULL_53_KERNEL_AND_RESOURCE_REQUIREMENT_PROOF_ABSENT")
        self.assertFalse(result["d20_scientific_kernel_bound"])
        self.assertFalse(result["d20_resource_model_present"])
        self.assertEqual(result["real_packed_q3_reads"], 0)
        self.assertEqual(result["scientific_action_calls"], 0)
        self.assertFalse(result["full_53_scientific_execution_authorized"])

    def test_frozen_result_rederives_exactly(self):
        frozen = json.loads((HERE / "fh_l8_kernel_resource_audit_d25_result.json").read_text(encoding="utf-8"))
        self.assertEqual(frozen, d25.audit())

    def test_d20_source_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = source_fixture(Path(tmp) / "ff")
            (root / "fh_l8_full_consumer_d20.py").write_text("# drift\n", encoding="utf-8")
            with self.assertRaisesRegex(d25.AuditError, "custody"):
                d25.audit(root)

    def test_contract_duplicate_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = source_fixture(Path(tmp) / "ff")
            contract = root / "fh_l8_kernel_resource_audit_d25_contract.json"
            contract.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
            with self.assertRaisesRegex(d25.AuditError, "duplicate"):
                d25.audit(root)

    def test_authority_mutation_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = source_fixture(Path(tmp) / "ff")
            contract = root / "fh_l8_kernel_resource_audit_d25_contract.json"
            value = json.loads(contract.read_text(encoding="utf-8"))
            value["authority"]["scientific_kernel_authorized"] = True
            contract.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(d25.AuditError, "authority"):
                d25.audit(root)


if __name__ == "__main__":
    unittest.main()
