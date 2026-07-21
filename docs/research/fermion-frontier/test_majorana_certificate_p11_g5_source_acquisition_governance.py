#!/usr/bin/env python3
"""Adversarial tests for P11-G5 source-acquisition governance."""

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
PATH = BASE / "majorana_certificate_p11_g5_source_acquisition_governance_validator.py"
SPEC = importlib.util.spec_from_file_location("p11g5", PATH)
assert SPEC and SPEC.loader
G5 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = G5
SPEC.loader.exec_module(G5)


class P11G5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.raw = G5.load_json(BASE / G5.CONTRACT_NAME, "contract")
        G5.validate_contract(cls.contract)
        cls.projection = G5.validate_p11e0(cls.contract)
        cls.expected = G5.expected_record(cls.contract, cls.raw, cls.projection)
        cls.record, cls.record_raw = G5.load_json(BASE / G5.RECORD_NAME, "record", canonical=True)

    def test_content_authorizes_only_exact_p11e1_and_does_not_consume_it(self) -> None:
        result = G5.validate_content()
        self.assertEqual(result["disposition"], G5.DISPOSITION)
        self.assertEqual(result["next_gate"], G5.NEXT_GATE)
        self.assertFalse(result["P11_E1_authority_consumed"])
        self.assertEqual(self.record_raw, G5.canonical_bytes(self.record))
        self.assertTrue(self.record["P11_E1_source_archive_acquisition_authorized"])
        self.assertFalse(self.record["source_archive_custody_established"])

    def test_p11e0_topology_blob_custody_and_projection(self) -> None:
        self.assertEqual(G5._parent(G5.DIRECT_PARENT), G5.G4)
        self.assertEqual(G5._paths(G5.DIRECT_PARENT), G5.E0_PATHS)
        self.assertEqual(
            self.projection["P11_E0_outcome"],
            "SOURCE_ARCHIVE_ACQUISITION_CONTRACT_PACK_ESTABLISHED_AWAITING_INDEPENDENT_AUTHORIZATION",
        )
        self.assertEqual(self.projection["snapshot_id"], G5.SNAPSHOT_ID)
        self.assertEqual(self.projection["planned_future_command_count"], 5)
        self.assertFalse(self.projection["source_archive_acquisition_previously_authorized"])

    def test_all_ten_readiness_checks_are_exact_and_pass(self) -> None:
        rows = self.contract["readiness_review"]
        self.assertEqual([row["check_id"] for row in rows], G5.READINESS_IDS)
        self.assertEqual([row["status"] for row in rows], ["PASS"] * 10)
        changed = copy.deepcopy(self.contract)
        changed["readiness_review"][3]["status"] = "UNKNOWN"
        with self.assertRaises(G5.GovernanceError):
            G5.validate_contract(changed)

    def test_snapshot_sources_root_and_origins_are_pinned(self) -> None:
        auth = self.contract["P11_E1_authorization"]
        self.assertEqual(auth["snapshot_id"], G5.SNAPSHOT_ID)
        self.assertEqual(auth["exact_source_identities"], G5.IDENTITIES)
        self.assertEqual(auth["exact_custody_root"], G5.CUSTODY_ROOT)
        self.assertEqual(auth["allowed_network_origins"], G5.ORIGINS)
        for key, value in (
            ("snapshot_id", "latest"),
            ("exact_custody_root", "/tmp/p11"),
            ("allowed_network_origins", G5.ORIGINS + ["https://example.invalid/"]),
        ):
            changed = copy.deepcopy(self.contract)
            changed["P11_E1_authorization"][key] = value
            with self.subTest(key=key), self.assertRaises(G5.GovernanceError):
                G5.validate_contract(changed)

    def test_required_operational_authorities_cannot_be_removed(self) -> None:
        keys = (
            "operational_acquisition_runner_source_allowed",
            "create_and_write_exact_custody_root_allowed",
            "read_apt_get_binary_ubuntu_keyring_and_declared_system_identity_inputs_allowed",
            "network_snapshot_index_and_source_archive_acquisition_allowed",
            "run_only_the_five_exact_P11_E0_apt_get_argv_allowed",
            "hash_parse_verify_receipt_and_atomic_acceptance_allowed",
        )
        for key in keys:
            changed = copy.deepcopy(self.contract)
            changed["P11_E1_authorization"][key] = False
            with self.subTest(key=key), self.assertRaises(G5.GovernanceError):
                G5.validate_contract(changed)

    def test_forbidden_authorities_cannot_be_opened(self) -> None:
        keys = (
            "host_etc_apt_var_lib_apt_var_cache_apt_or_dpkg_status_write_allowed",
            "sudo_root_or_privilege_escalation_allowed",
            "credentials_tokens_private_mirrors_proxies_or_third_party_keys_allowed",
            "latest_version_alternate_snapshot_suite_component_package_or_version_substitution_allowed",
            "archive_unpack_patch_or_source_tree_materialization_allowed",
            "kernel_source_reading_or_kernel_accounting_bound_derivation_allowed",
            "candidate_source_linker_script_object_or_executable_allowed",
            "compile_link_disassemble_execute_benchmark_or_dynamic_measurement_allowed",
            "Julia_or_P9_candidate_execution_allowed",
            "scientific_schedule_semantics_or_cap_change_allowed",
        )
        for key in keys:
            changed = copy.deepcopy(self.contract)
            changed["P11_E1_authorization"][key] = True
            with self.subTest(key=key), self.assertRaises(G5.GovernanceError):
                G5.validate_contract(changed)

    def test_attempt_environment_and_offline_validation_limits_are_exact(self) -> None:
        limits = self.contract["P11_E1_execution_order_and_limits"]
        self.assertEqual(len(limits["required_step_order"]), 12)
        self.assertEqual(limits["APT_update_attempt_limit"], 1)
        self.assertEqual(limits["source_download_attempt_limit_per_package"], 2)
        self.assertEqual(limits["Acquire_Retries_inside_each_apt_command"], 0)
        self.assertTrue(limits["runner_must_use_direct_argv_without_shell"])
        self.assertTrue(limits["runner_must_not_read_proxy_or_credential_environment_variables"])
        self.assertTrue(limits["network_phase_ends_before_independent_validator"])

    def test_outputs_outcomes_and_post_gate_are_bounded(self) -> None:
        outputs = self.contract["P11_E1_required_outputs"]
        self.assertEqual(len(outputs["external_outputs"]), 7)
        self.assertEqual(len(outputs["repository_outputs"]), 5)
        self.assertEqual(self.contract["P11_E1_allowed_outcomes"], G5.ALLOWED_OUTCOMES)
        self.assertEqual(self.record["post_P11_E1_gate"], G5.POST_GATE)
        self.assertEqual(self.record["P11_E1_exact_changed_path_count"], 7)

    def test_record_cannot_claim_consumption_custody_bound_or_candidate_authority(self) -> None:
        mutations = (
            ("P11_E1_authority_consumed", True),
            ("source_archive_custody_established", True),
            ("archive_unpack_or_source_tree_materialization_allowed", True),
            ("kernel_source_reading_or_accounting_bound_design_allowed", True),
            ("candidate_implementation_allowed", True),
            ("candidate_execution_allowed", True),
            ("exact_static_process_peak_bytes", 1028653056),
            ("difference_is_proven_headroom", True),
            ("semantic_equivalence_established", True),
            ("resource_no_go_inference", True),
        )
        for key, value in mutations:
            changed = copy.deepcopy(self.record)
            changed[key] = value
            with self.subTest(key=key):
                self.assertNotEqual(changed, self.expected)

    def test_p11e0_blob_drift_fails(self) -> None:
        with mock.patch.object(G5, "_git_bytes", return_value=b"wrong"):
            with self.assertRaises(G5.GovernanceError):
                G5.validate_p11e0(self.contract)

    def test_exact_staged_lifecycle(self) -> None:
        staged = "".join(f"{status}\t{path}\n" for path, status in G5.CHANGED_PATHS.items())

        def good(*args):
            if args == ("rev-parse", "HEAD"):
                return G5.DIRECT_PARENT + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return staged
            if args in (("diff", "--name-only"), ("ls-files", "--others", "--exclude-standard")):
                return ""
            raise AssertionError(args)

        with mock.patch.object(G5, "_git", side_effect=good):
            self.assertEqual(G5.validate_lifecycle(), "STAGED_DIRECT_CHILD")

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
