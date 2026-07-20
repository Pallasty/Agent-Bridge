#!/usr/bin/env python3
"""Offline tests for the P11-E2R contract pack."""

from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent
PATH = BASE / "majorana_certificate_p11e2r_remedial_acquisition_operational_validator.py"
SPEC = importlib.util.spec_from_file_location("p11e2r", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class P11E2RTests(unittest.TestCase):
    def test_contract_pack_passes_before_result_commit(self) -> None:
        self.assertEqual(MODULE.verify()["status"], "PASS")

    def test_new_root_and_old_evidence_exclusion_are_exact(self) -> None:
        identity = MODULE.load(MODULE.CONTRACT)["future_operation_identity"]
        self.assertEqual(identity["new_external_root"], "/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e2r-source-custody")
        self.assertIn("p11-e1-source-custody", identity["old_P11_E1_root_is_excluded_and_must_not_be_read_written_or_reused"])
        self.assertTrue(identity["P11_E1_accepted_bytes_may_not_satisfy_any_P11_E2R_completeness_check"])

    def test_contract_is_nonexecuting(self) -> None:
        tree = ast.parse(PATH.read_text(encoding="utf-8"))
        literals = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertNotIn("apt-get", literals)
        self.assertNotIn("apt-config", literals)


if __name__ == "__main__":
    unittest.main()
