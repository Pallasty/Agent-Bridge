#!/usr/bin/env python3
"""Adversarial tests for P11-D evidence-feasibility audit."""

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
PATH = BASE / "majorana_certificate_p11d_source_runtime_evidence_feasibility_validator.py"
SPEC = importlib.util.spec_from_file_location("p11d", PATH)
assert SPEC and SPEC.loader
P11D = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = P11D
SPEC.loader.exec_module(P11D)


class P11DEvidenceFeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.raw = P11D.load_json(BASE / P11D.CONTRACT_NAME, "contract")
        P11D.validate_contract(cls.contract)
        cls.sources = P11D.validate_sources(cls.contract)
        cls.local = P11D.validate_local_snapshot(cls.contract)
        cls.evidence = P11D.validate_evidence(cls.contract)
        cls.expected = P11D.expected_report(cls.contract, cls.raw, cls.sources, cls.local, cls.evidence)
        cls.report, cls.report_raw = P11D.load_json(BASE / P11D.REPORT_NAME, "report", canonical=True)

    def test_content_identifies_source_route_but_not_kernel_bound(self) -> None:
        result = P11D.validate_content()
        self.assertEqual(result["outcome"], P11D.OUTCOME)
        self.assertFalse(result["source_archive_custody_established"])
        self.assertFalse(result["static_kernel_bound_established"])
        self.assertEqual(result["implementation_gate"], "CLOSED")
        self.assertEqual(result["execution_gate"], "CLOSED")
        self.assertEqual(self.report, self.expected)
        self.assertEqual(self.report_raw, P11D.canonical_bytes(self.report))

    def test_toolchain_source_identities_are_exact_but_not_custody(self) -> None:
        self.assertEqual(self.local["toolchain_source_packages"], ["gcc-15=15.2.0-16ubuntu1", "binutils=2.46-3ubuntu2"])
        self.assertFalse(self.local["deb_src_enabled"])
        self.assertEqual(self.local["source_index_file_count"], 0)
        self.assertEqual(self.local["visible_matching_source_archive_count"], 0)
        self.assertFalse(self.report["source_archive_custody_established"])

    def test_authenticated_source_route_requires_future_bytes(self) -> None:
        route = self.report["source_custody_route"]
        self.assertEqual(route["status"], "FEASIBLE_AUTHENTICATED_EXACT_VERSION_ROUTE_IDENTIFIED_NOT_ACQUIRED")
        self.assertEqual(len(route["required_future_steps_under_new_governance"]), 6)
        self.assertFalse(route["source_archive_custody_established"])

    def test_cgroup_interfaces_are_dynamic_not_static_peak_proof(self) -> None:
        kernel = self.report["static_kernel_accounting_assessment"]
        self.assertEqual(self.local["cgroup_filesystem"], "cgroup2")
        self.assertEqual(self.local["cgroup_interface_file_count"], 7)
        self.assertFalse(self.local["dynamic_measurement_performed"])
        self.assertFalse(kernel["static_kernel_cgroup_accounting_bound_established"])
        self.assertTrue(kernel["memory_current_or_memory_peak_measurement_would_not_by_itself_prove_a_static_all_execution_peak"])
        self.assertIsNone(self.report["exact_static_process_peak_bytes"])

    def test_all_seven_evidence_classes_fail_closed_where_required(self) -> None:
        rows = self.report["evidence_class_disposition"]
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[0]["status"], "IDENTITY_ESTABLISHED_FROM_LOCAL_BINARY_METADATA_AND_DEBIAN_POLICY")
        self.assertTrue(all(row["status"] != "ESTABLISHED" for row in rows[2:]))
        self.assertFalse(self.report["difference_is_proven_headroom"])

    def test_official_sources_are_primary_pointers_not_byte_custody(self) -> None:
        rows = self.report["official_primary_sources"]
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["url"].startswith(("https://www.debian.org/", "https://manpages.ubuntu.com/", "https://docs.kernel.org/")) for row in rows))
        self.assertTrue(all(row["byte_pinned"] is False for row in rows))

    def test_authority_mutations_fail(self) -> None:
        for key in ("candidate_source_allowed", "C_assembly_or_linker_script_source_allowed", "compilation_or_linking_allowed",
                    "Julia_or_candidate_execution_allowed", "benchmark_or_dynamic_memory_measurement_allowed",
                    "package_index_update_installation_or_environment_mutation_allowed", "binary_or_source_archive_download_allowed",
                    "scientific_schedule_semantics_or_cap_change_allowed"):
            changed = copy.deepcopy(self.contract)
            changed["scope"][key] = True
            with self.subTest(key=key), self.assertRaises(P11D.AuditError):
                P11D.validate_contract(changed)

    def test_report_cannot_claim_custody_peak_or_equivalence(self) -> None:
        for key, value in (("source_archive_custody_established", True), ("static_kernel_cgroup_accounting_bound_established", True),
                           ("dynamic_memory_measurement_performed", True), ("candidate_implementation_present", True),
                           ("difference_is_proven_headroom", True), ("exact_static_process_peak_bytes", 1028653056),
                           ("semantic_equivalence_established", True), ("implementation_gate", "OPEN"),
                           ("execution_gate", "OPEN"), ("resource_no_go_inference", True)):
            changed = copy.deepcopy(self.report)
            changed[key] = value
            with self.subTest(key=key):
                self.assertNotEqual(changed, self.expected)

    def test_source_and_local_receipt_drift_fail(self) -> None:
        with mock.patch.object(P11D, "_git_bytes", return_value=b"wrong"):
            with self.assertRaises(P11D.AuditError):
                P11D.validate_sources(self.contract)
        bad = mock.Mock(returncode=0, stdout=b"wrong", stderr=b"")
        with mock.patch.object(P11D, "_run_local", return_value=bad):
            with self.assertRaises(P11D.AuditError):
                P11D.validate_local_snapshot(self.contract)

    def test_exact_staged_lifecycle(self) -> None:
        staged = "".join(f"{status}\t{path}\n" for path, status in P11D.CHANGED_PATHS.items())
        def good(*args):
            if args == ("rev-parse", "HEAD"):
                return P11D.DIRECT_PARENT + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return staged
            if args in (("diff", "--name-only"), ("ls-files", "--others", "--exclude-standard")):
                return ""
            raise AssertionError(args)
        with mock.patch.object(P11D, "_git", side_effect=good):
            self.assertEqual(P11D.validate_lifecycle(), "STAGED_DIRECT_CHILD")

    def test_subprocesses_are_git_or_exact_read_only_allowlist(self) -> None:
        source = PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"]
        self.assertEqual(len(calls), 3)
        self.assertIn("ALLOWED_COMMANDS", source)
        self.assertIn("non-allowlisted local identity command", source)
        self.assertNotIn("apt-get", source)


if __name__ == "__main__":
    unittest.main()
