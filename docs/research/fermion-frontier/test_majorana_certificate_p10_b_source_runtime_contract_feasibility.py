#!/usr/bin/env python3
"""Adversarial tests for the P10-B nonexecuting contract-feasibility audit."""

from __future__ import annotations

import ast
import copy
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
PATH = BASE / "majorana_certificate_p10_b_source_runtime_contract_feasibility_validator.py"
SPEC = importlib.util.spec_from_file_location("p10b_audit", PATH)
assert SPEC and SPEC.loader
P10B = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = P10B
SPEC.loader.exec_module(P10B)


class P10BContractFeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.contract_raw = P10B.load_json(BASE / P10B.CONTRACT_NAME, "contract")
        P10B.validate_contract(cls.contract)
        cls.facts = P10B.source_facts(cls.contract)
        cls.expected = P10B.expected_record(cls.contract, cls.contract_raw, cls.facts)
        cls.record, cls.record_raw = P10B.load_json(BASE / P10B.RECORD_NAME, "record", canonical=True)

    def test_content_and_canonical_record_close_without_byte_claim(self) -> None:
        result = P10B.validate_content()
        self.assertEqual(result["outcome"], P10B.OUTCOME)
        self.assertEqual(result["execution_gate"], "CLOSED")
        self.assertEqual(self.record_raw, P10B.canonical_bytes(self.record))
        self.assertIsNone(self.record["exact_static_peak_bytes"])
        self.assertFalse(self.record["resource_no_go_inference"])

    def test_all_seven_obligations_remain_without_an_independent_contract(self) -> None:
        self.assertEqual(len(self.record["evidence_ledger"]), 7)
        self.assertEqual(tuple(row["obligation_id"] for row in self.record["evidence_ledger"]), P10B.OBLIGATION_IDS)
        self.assertTrue(all(row["status"] == P10B.EVIDENCE_STATUS for row in self.record["evidence_ledger"]))

    def test_authority_outcome_and_record_mutations_fail_closed(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["scope"]["Julia_execution_allowed"] = True
        with self.assertRaises(P10B.AuditError):
            P10B.validate_contract(contract)
        for key, value in (("outcome", "EVIDENCE_ROUTE_IDENTIFIED_NOT_A_BYTE_PROOF"), ("exact_static_peak_bytes", 1), ("execution_gate", "OPEN"), ("resource_no_go_inference", True)):
            record = copy.deepcopy(self.record)
            record[key] = value
            with self.subTest(key=key), self.assertRaises(P10B.AuditError):
                P10B.validate_record(record, self.expected)
        record = copy.deepcopy(self.record)
        record["evidence_ledger"][0]["status"] = "VERIFIED"
        with self.assertRaises(P10B.AuditError):
            P10B.validate_record(record, self.expected)

    def test_strict_json_and_frozen_source_digest_drift_fail(self) -> None:
        with self.assertRaisesRegex(P10B.AuditError, "duplicate JSON key"):
            P10B.load_json(self._write_temp(b'{"x":1,"x":2}'), "duplicate")
        with self.assertRaisesRegex(P10B.AuditError, "non-finite"):
            P10B.load_json(self._write_temp(b'{"x":NaN}'), "nonfinite")
        changed = copy.deepcopy(self.contract)
        changed["source_inputs"][0]["sha256"] = "0" * 64
        with self.assertRaises(P10B.AuditError):
            P10B.source_facts(changed)

    def _write_temp(self, raw: bytes) -> Path:
        path = BASE / ".p10b-test-tmp.json"
        self.addCleanup(path.unlink, missing_ok=True)
        path.write_bytes(raw)
        return path

    def test_lifecycle_requires_exact_direct_child_path_set(self) -> None:
        staged = "".join(f"{status}\t{path}\n" for path, status in P10B.CHANGED_PATHS.items())
        def good(*args):
            if args == ("rev-parse", "HEAD"):
                return P10B.DIRECT_PARENT + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return staged
            if args in (("diff", "--name-only"), ("ls-files", "--others", "--exclude-standard")):
                return ""
            raise AssertionError(args)
        with mock.patch.object(P10B, "_git", side_effect=good):
            self.assertEqual(P10B.validate_lifecycle(), "STAGED_DIRECT_CHILD")
        with mock.patch.object(P10B, "_git", side_effect=lambda *args: "wrong\n" if args == ("rev-parse", "HEAD") else ""):
            with self.assertRaises(P10B.AuditError):
                P10B.validate_lifecycle()

    def test_validator_is_read_only_and_never_launches_julia_or_candidate(self) -> None:
        source = PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"]
        self.assertEqual(len(calls), 1)
        command = calls[0].args[0]
        self.assertIsInstance(command, ast.Tuple)
        self.assertEqual(command.elts[0].value, "git")
        self.assertNotIn("systemd-run", source)
        self.assertNotIn("eval(", source)


if __name__ == "__main__":
    unittest.main()
