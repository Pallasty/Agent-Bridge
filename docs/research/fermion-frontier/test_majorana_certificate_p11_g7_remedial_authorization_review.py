#!/usr/bin/env python3
"""Offline tests for the P11-G7 authorization review."""

from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent
PATH = BASE / "majorana_certificate_p11_g7_remedial_authorization_review_validator.py"
SPEC = importlib.util.spec_from_file_location("p11g7", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class P11G7Tests(unittest.TestCase):
    def test_review_passes_before_result_commit(self) -> None:
        result = MODULE.verify()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["readiness_pass_count"], 6)

    def test_only_nonexecuting_contract_design_is_opened(self) -> None:
        contract = MODULE.load(MODULE.CONTRACT)
        decision = contract["decision"]
        self.assertEqual(decision["only_allowed_next_gate"], "P11-E2R-REMEDIAL-ACQUISITION-OPERATIONAL-CONTRACT-PACK-V1")
        self.assertFalse(decision["network_or_archive_acquisition_authorized"])
        self.assertFalse(decision["source_unpack_or_reading_authorized"])

    def test_validator_contains_no_acquisition_tool(self) -> None:
        tree = ast.parse(PATH.read_text(encoding="utf-8"))
        literals = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertNotIn("apt-get", literals)
        self.assertNotIn("curl", literals)


if __name__ == "__main__":
    unittest.main()
