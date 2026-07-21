#!/usr/bin/env python3
"""Adversarial tests for the nonexecuting P11-E0 acquisition contract pack."""

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
PATH = BASE / "majorana_certificate_p11e0_source_archive_acquisition_validator.py"
SPEC = importlib.util.spec_from_file_location("p11e0", PATH)
assert SPEC and SPEC.loader
E0 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = E0
SPEC.loader.exec_module(E0)


class P11E0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.raw = E0.load_json(BASE / E0.CONTRACT_NAME, "contract")
        E0.validate_contract(cls.contract)
        cls.projection = E0.validate_g4(cls.contract)
        cls.expected = E0.expected_record(cls.contract, cls.raw, cls.projection)
        cls.record, cls.record_raw = E0.load_json(BASE / E0.RECORD_NAME, "record", canonical=True)

    def test_content_establishes_contract_pack_without_acquisition(self) -> None:
        result = E0.validate_content()
        self.assertEqual(result["outcome"], E0.OUTCOME)
        self.assertEqual(result["next_governance_gate"], E0.NEXT_GATE)
        self.assertFalse(result["source_archive_acquisition_authorized"])
        self.assertEqual(self.record_raw, E0.canonical_bytes(self.record))
        self.assertFalse(self.record["source_archive_custody_established"])
        self.assertEqual(self.record["implementation_gate"], "CLOSED")
        self.assertEqual(self.record["execution_gate"], "CLOSED")

    def test_g4_topology_blob_custody_and_snapshot_anchor(self) -> None:
        self.assertEqual(E0._parent(E0.DIRECT_PARENT), E0.P11D)
        self.assertEqual(E0._paths(E0.DIRECT_PARENT), E0.G4_PATHS)
        self.assertEqual(E0._commit_snapshot_id(E0.P11D), E0.SNAPSHOT_ID)
        self.assertTrue(self.projection["route_A_contract_pack_allowed"])
        self.assertFalse(self.projection["source_archive_download_allowed"])
        self.assertFalse(self.projection["kernel_accounting_bound_design_allowed"])

    def test_exact_source_identities_and_snapshot_are_immutable(self) -> None:
        self.assertEqual(self.record["exact_source_identities"], E0.IDENTITIES)
        self.assertEqual(self.record["snapshot_id"], E0.SNAPSHOT_ID)
        changed = copy.deepcopy(self.contract)
        changed["snapshot_anchor"]["fallback_to_latest_or_different_snapshot_allowed"] = True
        with self.assertRaises(E0.ContractError):
            E0.validate_contract(changed)
        changed = copy.deepcopy(self.contract)
        changed["exact_source_identities"][0]["source_version"] = "latest"
        with self.assertRaises(E0.ContractError):
            E0.validate_contract(changed)

    def test_deb822_and_apt_config_are_isolated_and_authenticated(self) -> None:
        deb822 = self.contract["deb822_source_template"]
        self.assertEqual(deb822["exact_utf8_text"], E0.DEB822)
        self.assertNotIn("Trusted: yes", E0.DEB822)
        self.assertEqual(E0.DEB822.count("Types: deb-src\n"), 2)
        self.assertEqual(E0.DEB822.count(f"Snapshot: {E0.SNAPSHOT_ID}\n"), 2)
        lines = self.contract["apt_config_template"]["exact_lines"]
        self.assertEqual(lines, E0.APT_LINES)
        self.assertIn('Dir::State::status "${CUSTODY_ROOT}/apt/empty-status";', lines)
        self.assertIn('Acquire::AllowInsecureRepositories "false";', lines)
        self.assertNotIn("/var/lib/apt", "\n".join(lines))

    def test_future_commands_are_exact_download_only_and_forbidden_now(self) -> None:
        commands = self.contract["future_P11_E1_command_plan"]
        self.assertEqual(commands, E0._planned_commands())
        self.assertEqual(len(commands), 5)
        for row in commands:
            self.assertFalse(row["allowed_in_P11_E0"])
            self.assertEqual(row["argv"][0], "apt-get")
            self.assertIn(E0.SNAPSHOT_ID, row["argv"])
        for row in commands[1:]:
            self.assertIn("--download-only", row["argv"])
            self.assertIn("--only-source", row["argv"])
            self.assertNotIn("--compile", row["argv"])

    def test_authentication_chain_requires_double_manifest_set_equality(self) -> None:
        auth = self.contract["authentication_and_completeness_rules"]
        self.assertEqual(len(auth["archive_trust_chain"]), 6)
        self.assertEqual(len(auth["required_set_equalities"]), 3)
        self.assertFalse(auth["unsigned_or_unverifiable_repository_metadata_allowed"])
        self.assertEqual(auth["unexpected_extra_archive_file"], "FAIL_CLOSED")
        self.assertEqual(auth["missing_referenced_archive_file"], "FAIL_CLOSED")
        parser = auth["dsc_parser"]
        self.assertTrue(parser["duplicate_control_fields_forbidden"])
        self.assertTrue(parser["duplicate_Checksums_Sha256_filenames_forbidden"])

    def test_space_transaction_receipt_and_retry_fail_closed(self) -> None:
        space = self.contract["space_and_transaction_rules"]
        self.assertEqual(
            space["minimum_free_bytes_formula"],
            "expected_download_bytes + max(67108864, ceil(expected_download_bytes / 10))",
        )
        self.assertFalse(space["partial_package_acceptance_allowed"])
        receipt = self.contract["canonical_receipt_contract"]
        self.assertEqual(len(receipt["required_fields"]), 16)
        self.assertTrue(receipt["receipt_without_retained_verified_bytes_is_not_custody"])
        failure = self.contract["failure_cleanup_and_retry"]
        self.assertFalse(failure["resume_or_reuse_of_partial_download_bytes_allowed"])
        self.assertTrue(failure["network_success_without_complete_authentication_and_set_equality_is_failure"])

    def test_authority_mutations_fail(self) -> None:
        authority_keys = (
            "package_or_environment_mutation_authority",
            "network_or_source_archive_acquisition_authority",
            "source_archive_unpack_or_materialization_authority",
            "kernel_accounting_bound_design_authority",
            "implementation_authority",
            "execution_authority",
        )
        for key in authority_keys:
            changed = copy.deepcopy(self.contract)
            changed["authority"][key] = True
            with self.subTest(key=key), self.assertRaises(E0.ContractError):
                E0.validate_contract(changed)

    def test_record_cannot_claim_acquisition_custody_bound_or_open_gates(self) -> None:
        mutations = (
            ("P11_E1_source_archive_acquisition_authorized", True),
            ("source_archive_custody_established", True),
            ("archive_unpack_or_source_tree_materialization_allowed", True),
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

    def test_g4_blob_drift_fails(self) -> None:
        with mock.patch.object(E0, "_git_bytes", return_value=b"wrong"):
            with self.assertRaises(E0.ContractError):
                E0.validate_g4(self.contract)

    def test_exact_staged_lifecycle(self) -> None:
        staged = "".join(f"{status}\t{path}\n" for path, status in E0.CHANGED_PATHS.items())

        def good(*args):
            if args == ("rev-parse", "HEAD"):
                return E0.DIRECT_PARENT + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return staged
            if args in (("diff", "--name-only"), ("ls-files", "--others", "--exclude-standard")):
                return ""
            raise AssertionError(args)

        with mock.patch.object(E0, "_git", side_effect=good):
            self.assertEqual(E0.validate_lifecycle(), "STAGED_DIRECT_CHILD")

    def test_validator_subprocesses_are_git_only(self) -> None:
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
