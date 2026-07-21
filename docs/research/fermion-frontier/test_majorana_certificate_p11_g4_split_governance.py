#!/usr/bin/env python3
"""Adversarial tests for P11-G4 split governance."""

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
PATH = BASE / "majorana_certificate_p11_g4_split_governance_validator.py"
SPEC = importlib.util.spec_from_file_location("p11g4", PATH)
assert SPEC and SPEC.loader
G4 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = G4
SPEC.loader.exec_module(G4)


class P11G4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.raw = G4.load_json(BASE / G4.CONTRACT_NAME, "contract")
        G4.validate_contract(cls.contract)
        cls.projection = G4.validate_p11d(cls.contract)
        cls.expected = G4.expected_record(cls.contract, cls.raw, cls.projection)
        cls.record, cls.record_raw = G4.load_json(BASE / G4.RECORD_NAME, "record", canonical=True)

    def test_content_opens_only_p11e0_contract_pack(self) -> None:
        result = G4.validate_content()
        self.assertEqual(result["disposition"], G4.DISPOSITION)
        self.assertEqual(result["next_gate"], G4.NEXT_GATE)
        self.assertEqual(result["deferred_gate"], G4.DEFERRED_GATE)
        self.assertEqual(self.record_raw, G4.canonical_bytes(self.record))
        self.assertEqual(self.record["route_A_contract_pack_allowed"], True)
        self.assertEqual(self.record["source_archive_download_allowed"], False)

    def test_p11d_topology_custody_and_projection(self) -> None:
        self.assertEqual(G4._parent(G4.DIRECT_PARENT), G4.G3)
        self.assertEqual(G4._paths(G4.DIRECT_PARENT), G4.P11D_PATHS)
        self.assertEqual(
            self.projection["P11_D_outcome"],
            "SOURCE_CUSTODY_ROUTE_IDENTIFIED_STATIC_KERNEL_ACCOUNTING_NOT_ESTABLISHED",
        )
        self.assertEqual(self.projection["evidence_class_count"], 7)
        self.assertFalse(self.projection["source_archive_custody_established"])
        self.assertFalse(self.projection["static_kernel_cgroup_accounting_bound_established"])

    def test_route_a_cannot_mutate_or_acquire(self) -> None:
        keys = (
            "package_source_configuration_mutation_allowed",
            "package_index_refresh_allowed",
            "binary_or_source_archive_download_allowed",
            "archive_unpack_or_patch_application_allowed",
            "source_tree_materialization_allowed",
            "candidate_source_allowed",
            "compilation_linking_disassembly_or_execution_allowed",
        )
        for key in keys:
            changed = copy.deepcopy(self.contract)
            changed["route_A_source_archive_custody"][key] = True
            with self.subTest(key=key), self.assertRaises(G4.GovernanceError):
                G4.validate_contract(changed)

    def test_route_b_cannot_open_before_custody_and_new_governance(self) -> None:
        keys = (
            "kernel_source_reading_or_bound_derivation_allowed",
            "dynamic_kernel_or_candidate_measurement_allowed",
            "static_kernel_cgroup_accounting_bound_established",
        )
        for key in keys:
            changed = copy.deepcopy(self.contract)
            changed["route_B_static_kernel_accounting_bound"][key] = True
            with self.subTest(key=key), self.assertRaises(G4.GovernanceError):
                G4.validate_contract(changed)
        changed = copy.deepcopy(self.contract)
        changed["route_B_static_kernel_accounting_bound"]["exact_static_process_peak_bytes"] = 1028653056
        with self.assertRaises(G4.GovernanceError):
            G4.validate_contract(changed)

    def test_exact_source_identity_and_dependency_order_are_pinned(self) -> None:
        self.assertEqual(
            self.record["required_exact_source_identities"],
            [
                "gcc-15=15.2.0-16ubuntu1",
                "binutils=2.46-3ubuntu2",
                "linux=7.0.0-28.28",
                "linux-signed=7.0.0-28.28",
            ],
        )
        self.assertEqual(self.record["ordered_successor_sequence"], G4.SEQUENCE)
        changed = copy.deepcopy(self.contract)
        changed["ordered_successor_sequence"] = list(reversed(G4.SEQUENCE))
        with self.assertRaises(G4.GovernanceError):
            G4.validate_contract(changed)

    def test_record_cannot_claim_custody_bound_headroom_or_open_gates(self) -> None:
        mutations = (
            ("source_archive_download_allowed", True),
            ("source_archive_custody_established", True),
            ("static_kernel_cgroup_accounting_bound_established", True),
            ("exact_static_process_peak_bytes", 1028653056),
            ("difference_is_proven_headroom", True),
            ("semantic_equivalence_established", True),
            ("implementation_gate", "OPEN"),
            ("execution_gate", "OPEN"),
            ("resource_no_go_inference", True),
        )
        for key, value in mutations:
            changed = copy.deepcopy(self.record)
            changed[key] = value
            with self.subTest(key=key):
                self.assertNotEqual(changed, self.expected)

    def test_p11d_blob_drift_fails(self) -> None:
        with mock.patch.object(G4, "_git_bytes", return_value=b"wrong"):
            with self.assertRaises(G4.GovernanceError):
                G4.validate_p11d(self.contract)

    def test_exact_staged_lifecycle(self) -> None:
        staged = "".join(f"{status}\t{path}\n" for path, status in G4.CHANGED_PATHS.items())

        def good(*args):
            if args == ("rev-parse", "HEAD"):
                return G4.DIRECT_PARENT + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return staged
            if args in (("diff", "--name-only"), ("ls-files", "--others", "--exclude-standard")):
                return ""
            raise AssertionError(args)

        with mock.patch.object(G4, "_git", side_effect=good):
            self.assertEqual(G4.validate_lifecycle(), "STAGED_DIRECT_CHILD")

    def test_subprocesses_are_git_only(self) -> None:
        tree = ast.parse(PATH.read_text(encoding="utf-8"))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ]
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual(call.args[0].elts[0].value, "git")


if __name__ == "__main__":
    unittest.main()
