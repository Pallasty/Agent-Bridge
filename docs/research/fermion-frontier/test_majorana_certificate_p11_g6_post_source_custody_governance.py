#!/usr/bin/env python3
"""Offline checks for P11-G6 governance artifacts."""

from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent
PATH = BASE / "majorana_certificate_p11_g6_post_source_custody_governance_validator.py"
SPEC = importlib.util.spec_from_file_location("p11g6", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class P11G6Tests(unittest.TestCase):
    def test_governance_verification_passes_before_result_commit(self) -> None:
        self.assertEqual(MODULE.verify()["status"], "PASS")

    def test_record_is_canonical_and_closes_network_and_downstream_work(self) -> None:
        record = MODULE.load(MODULE.RECORD, canonical_required=True)
        self.assertTrue(record["P11_E1_network_authority_consumed"])
        self.assertFalse(record["retry_or_network_acquisition_authorized"])
        self.assertFalse(record["archive_unpack_or_source_reading_authorized"])
        self.assertFalse(record["candidate_implementation_or_execution_authorized"])

    def test_validator_invokes_only_git_subprocess(self) -> None:
        tree = ast.parse(PATH.read_text(encoding="utf-8"))
        literals = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        self.assertIn("git", literals)
        self.assertNotIn("apt-get", literals)
        self.assertNotIn("curl", literals)


if __name__ == "__main__":
    unittest.main()
