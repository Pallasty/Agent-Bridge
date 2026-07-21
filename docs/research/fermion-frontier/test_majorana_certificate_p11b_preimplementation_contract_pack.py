#!/usr/bin/env python3
"""Adversarial tests for the P11-B preimplementation contract pack."""

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
PATH = BASE / "majorana_certificate_p11b_preimplementation_contract_pack_validator.py"
SPEC = importlib.util.spec_from_file_location("p11b", PATH)
assert SPEC and SPEC.loader
P11B = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = P11B
SPEC.loader.exec_module(P11B)


class P11BContractPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.raw = P11B.load_json(BASE / P11B.CONTRACT_NAME, "contract")
        P11B.validate_contract(cls.contract)
        cls.sources = P11B.validate_sources(cls.contract)
        cls.derived = {}
        for check in (P11B.validate_layout, P11B.validate_arena, P11B.validate_arithmetic, P11B.validate_runtime, P11B.validate_toolchain_shape):
            cls.derived.update(check(cls.contract))
        cls.expected = P11B.expected_report(cls.contract, cls.raw, cls.sources, cls.derived)
        cls.report, cls.report_raw = P11B.load_json(BASE / P11B.REPORT_NAME, "report", canonical=True)

    def test_content_defines_contracts_without_opening_gates(self) -> None:
        result = P11B.validate_content()
        self.assertEqual(result["outcome"], P11B.OUTCOME)
        self.assertEqual(result["implementation_gate"], "CLOSED")
        self.assertEqual(result["execution_gate"], "CLOSED")
        self.assertEqual(self.report_raw, P11B.canonical_bytes(self.report))
        self.assertIsNone(self.report["exact_static_process_peak_bytes"])
        self.assertFalse(self.report["difference_is_proven_headroom"])

    def test_read_only_local_toolchain_identity_matches_receipt(self) -> None:
        result = P11B.verify_local_toolchain(self.contract)
        self.assertEqual(result["status"], "VERIFIED_READ_ONLY_LOCAL_TOOLCHAIN_IDENTITY")
        self.assertEqual(result["binary_count"], 8)

    def test_layout_offsets_cannot_overlap_or_escape_slots(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["byte_layout_contract"]["slot_layouts"][0]["fields"][1]["offset"] = 31
        with self.assertRaises(P11B.ContractError):
            P11B.validate_layout(changed)
        changed = copy.deepcopy(self.contract)
        changed["byte_layout_contract"]["slot_layouts"][0]["fields"][0]["size"] = 65
        with self.assertRaises(P11B.ContractError):
            P11B.validate_layout(changed)

    def test_arena_must_be_contiguous_aligned_and_nonaliasing(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["arena_contract"]["regions_in_offset_order"][3]["offset_bytes"] += 64
        with self.assertRaises(P11B.ContractError):
            P11B.validate_arena(changed)
        changed = copy.deepcopy(self.contract)
        changed["arena_contract"]["all_regions_reserved_simultaneously_and_never_alias"] = False
        with self.assertRaises(P11B.ContractError):
            P11B.validate_arena(changed)

    def test_arithmetic_scratch_and_runtime_sum_fail_closed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["arithmetic_width_contract"]["reused_wide_scratch_limb_count"] = 32
        with self.assertRaises(P11B.ContractError):
            P11B.validate_arithmetic(changed)
        changed = copy.deepcopy(self.contract)
        changed["runtime_bound_target_ledger"][0]["target_bytes"] -= 1
        with self.assertRaises(P11B.ContractError):
            P11B.validate_runtime(changed)
        changed = copy.deepcopy(self.contract)
        changed["runtime_target_rules"]["difference_is_not_proven_headroom"] = False
        with self.assertRaises(P11B.ContractError):
            P11B.validate_runtime(changed)

    def test_no_serialized_step2_state_forces_full_prelude(self) -> None:
        prelude = self.report["prelude_requirement"]
        self.assertFalse(prelude["serialized_P6_step2_term_state_available"])
        self.assertEqual(prelude["required_action"], "reconstruct_frozen_step1_and_step2_in_the_same_explicit_memory_process_before_step3")
        self.assertEqual(prelude["step2_output_term_count"], 284847)

    def test_authority_and_result_mutations_fail(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["compilation_or_linking_allowed"] = True
        with self.assertRaises(P11B.ContractError):
            P11B.validate_contract(changed)
        for key, value in (("implementation_gate", "OPEN"), ("execution_gate", "OPEN"), ("exact_static_process_peak_bytes", 1028653056), ("difference_is_proven_headroom", True), ("semantic_equivalence_established", True), ("resource_no_go_inference", True)):
            changed_report = copy.deepcopy(self.report)
            changed_report[key] = value
            with self.subTest(key=key):
                self.assertNotEqual(changed_report, self.expected)

    def test_source_and_toolchain_digest_drift_fail(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["source_inputs"][0]["sha256"] = "0" * 64
        with self.assertRaises(P11B.ContractError):
            P11B.validate_sources(changed)
        changed = copy.deepcopy(self.contract)
        changed["local_toolchain_identity_receipt"]["binaries"][0]["sha256"] = "0" * 64
        with self.assertRaises(P11B.ContractError):
            P11B.verify_local_toolchain(changed)

    def test_exact_staged_lifecycle(self) -> None:
        staged = "".join(f"{status}\t{path}\n" for path, status in P11B.CHANGED_PATHS.items())
        def good(*args):
            if args == ("rev-parse", "HEAD"):
                return P11B.DIRECT_PARENT + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return staged
            if args in (("diff", "--name-only"), ("ls-files", "--others", "--exclude-standard")):
                return ""
            raise AssertionError(args)
        with mock.patch.object(P11B, "_git", side_effect=good):
            self.assertEqual(P11B.validate_lifecycle(), "STAGED_DIRECT_CHILD")

    def test_subprocess_calls_are_git_or_exact_identity_allowlists(self) -> None:
        source = PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess"]
        self.assertEqual(len(calls), 3)
        self.assertIn("allowed =", source)
        self.assertIn("non-allowlisted identity command", source)
        for forbidden in ("systemd-run", "curl ", "wget ", "cargo build", "gcc -c", "rustc "):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
