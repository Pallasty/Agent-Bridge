import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest


HERE = pathlib.Path(__file__).resolve().parent
MODULE_PATH = HERE / "fb_s2_hbr_r1_adapter_eligibility.py"
CONTRACT_PATH = HERE / "fb_s2_hbr_r1_adapter_eligibility_contract.json"
SPEC = importlib.util.spec_from_file_location("fb_s2_eligibility", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def eligible_runtime(contract):
    values = {}
    for key, expected in contract["eligibility_gates"]["authority"].items():
        values[key] = "true" if expected else "false"
    for key, expected in contract["eligibility_gates"]["implementation"].items():
        if key == "candidate_sources_are_in_cargo_or_module_targets":
            continue
        if key.startswith("minimum_"):
            values[key[len("minimum_") :]] = str(expected)
        else:
            values[key] = "true" if expected else "false"
    return values


def eligible_mapping(contract):
    result = {}
    for key, expected in contract["eligibility_gates"]["fermion_mapping"].items():
        if isinstance(expected, bool):
            result[key] = "true" if expected else "false"
        elif isinstance(expected, list):
            result[key] = "|".join(expected)
        else:
            result[key] = str(expected)
    return result


class FbS2EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.contract = MODULE.load_contract(CONTRACT_PATH)
        self.snapshot = {"exact_commit_tree_and_file_bindings": True}
        self.runtime = eligible_runtime(self.contract)
        self.source = {
            "source_bindings_pass": True,
            "candidate_sources_are_in_cargo_or_module_targets": True,
        }
        self.mapping = eligible_mapping(self.contract)
        roles = self.contract["eligibility_gates"]["fermion_mapping_artifacts"][
            "required_roles"
        ]
        self.mapping_artifact_checks = {
            "fermion_mapping_artifacts.artifact_roles_declared": True,
            "fermion_mapping_artifacts.paths_distinct": True,
            "fermion_mapping_artifacts.equivalence_receipt_valid": True,
            "fermion_mapping_artifacts.independent_review_receipt_valid": True,
            **{
                f"fermion_mapping_artifacts.identity.{role}": True
                for role in roles
            },
        }
        self.mapping_artifact_evidence = {"synthetic_logic_control_only": True}
        self.record_evidence = {
            "all_path_hash_pairs_pass": True,
            "cross_record": {"pass": True},
            "protocol_commit_verified_before_gate": True,
        }
        self.integrity = {
            "executed": True,
            "launch_error": None,
            "returncode": 0,
            "fields": {
                "binding_status": self.contract["eligibility_gates"]
                ["source_and_provenance"]["artifact_integrity_binding_status"],
                "contract_gate_entered": "true",
            },
            "resource_envelope": {
                "memory_max_bytes": 1073741824,
                "memory_swap_max_bytes": 0,
            },
        }

    def evaluate(self, **overrides):
        arguments = {
            "contract": self.contract,
            "snapshot": self.snapshot,
            "runtime": self.runtime,
            "source_inspection": self.source,
            "mapping": self.mapping,
            "mapping_artifact_checks": self.mapping_artifact_checks,
            "mapping_artifact_evidence": self.mapping_artifact_evidence,
            "record_evidence": self.record_evidence,
            "integrity": self.integrity,
        }
        arguments.update(overrides)
        return MODULE.evaluate(**arguments)

    def test_frozen_contract_loads_and_is_explicitly_post_reconnaissance(self):
        self.assertEqual(MODULE.sha256_path(CONTRACT_PATH), MODULE.FROZEN_CONTRACT_SHA256)
        self.assertTrue(
            self.contract["chronology"]["manual_reconnaissance_preceded_protocol_freeze"]
        )
        self.assertFalse(self.contract["confirmation_authority"])
        self.assertFalse(self.contract["positive_qualification_authority"])
        self.assertFalse(
            self.contract["chronology"]["outcome_blind_preregistration_claimed"]
        )

    def test_any_contract_byte_drift_is_rejected(self):
        mutated = copy.deepcopy(self.contract)
        mutated["eligibility_gates"]["implementation"][
            "minimum_registered_arm_executor_impl_head_count"
        ] = 0
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "contract.json"
            path.write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.EligibilityError, "frozen contract hash"):
                MODULE.load_contract(path)

    def test_all_apparent_gates_require_a_new_positive_v2(self):
        status, checks, evidence = self.evaluate()
        self.assertEqual(status, MODULE.REQUIRES_V2)
        self.assertTrue(all(checks.values()))
        self.assertEqual(evidence["passed_gate_count"], evidence["required_gate_count"])
        self.assertFalse(self.contract["conditional_fb_s2b"]["performance_execution_authority_granted_here"])
        self.assertFalse(
            self.contract["conditional_fb_s2b"]["this_protocol_can_authorize_fb_s2b_design"]
        )

    def test_every_authority_field_fails_closed(self):
        for key, expected in self.contract["eligibility_gates"]["authority"].items():
            mutated = dict(self.runtime)
            mutated[key] = "false" if expected else "true"
            with self.subTest(key=key):
                status, checks, _ = self.evaluate(runtime=mutated)
                self.assertEqual(status, MODULE.NO_GO)
                self.assertFalse(checks[f"authority.{key}"])

    def test_unbound_integrity_gate_is_no_go(self):
        integrity = copy.deepcopy(self.integrity)
        integrity["fields"]["binding_status"] = (
            "VALID_UNBOUND_LANGUAGE_P3A2_HBR_R1_RUNTIME_ADAPTER_ENTRY_CONTRACT_CANDIDATE"
        )
        integrity["fields"]["contract_gate_entered"] = "false"
        status, checks, _ = self.evaluate(integrity=integrity)
        self.assertEqual(status, MODULE.NO_GO)
        self.assertFalse(
            checks["source_and_provenance.artifact_integrity_binding_status"]
        )

    def test_unrunnable_or_unbound_source_is_indeterminate(self):
        status, _, _ = self.evaluate(
            integrity={
                "executed": False,
                "launch_error": "not runnable",
                "returncode": None,
                "fields": {},
                "resource_envelope": {},
            }
        )
        self.assertEqual(status, MODULE.INDETERMINATE)
        status, _, _ = self.evaluate(
            snapshot={"exact_commit_tree_and_file_bindings": False}
        )
        self.assertEqual(status, MODULE.INDETERMINATE)

    def test_missing_or_leaky_fermion_mapping_is_no_go(self):
        status, checks, _ = self.evaluate(mapping=None)
        self.assertEqual(status, MODULE.NO_GO)
        self.assertTrue(all(not value for key, value in checks.items() if key.startswith("fermion_mapping.")))
        mutation = dict(self.mapping)
        mutation["target_or_label_values_enter_recurrent_state"] = "true"
        status, checks, _ = self.evaluate(mapping=mutation)
        self.assertEqual(status, MODULE.NO_GO)
        self.assertFalse(
            checks["fermion_mapping.target_or_label_values_enter_recurrent_state"]
        )

    def test_gate_parser_accepts_bound_real_format_and_fixed_terminal_line(self):
        value = (
            b"binding_status=VALID_UNBOUND_TEST\n"
            b"contract_gate_entered=false\n"
            b"language P3-A2 HBR-R1 runtime-adapter entry contract passed\n"
        )
        parsed = MODULE.parse_gate_map(value, "test gate")
        self.assertEqual(parsed["binding_status"], "VALID_UNBOUND_TEST")
        self.assertEqual(parsed["contract_gate_entered"], "false")
        self.assertIn("runtime-adapter entry contract passed", parsed["terminal_message"])
        with self.assertRaisesRegex(MODULE.EligibilityError, "terminal message"):
            MODULE.parse_gate_map(b"binding_status=VALID_UNBOUND_TEST\n", "test gate")

    def test_observed_nonzero_gate_is_no_go_not_indeterminate(self):
        integrity = copy.deepcopy(self.integrity)
        integrity["returncode"] = 1
        integrity["fields"] = {}
        status, checks, evidence = self.evaluate(integrity=integrity)
        self.assertEqual(status, MODULE.NO_GO)
        self.assertTrue(evidence["integrity_observed"])
        self.assertFalse(
            checks["source_and_provenance.artifact_integrity_gate_returncode"]
        )

    def test_tsv_map_rejects_duplicate_or_wide_rows(self):
        for value in (b"key\tone\nkey\ttwo\n", b"key\tone\textra\n"):
            with self.subTest(value=value):
                with self.assertRaises(MODULE.EligibilityError):
                    MODULE.parse_tsv_map(value, "test")

    def test_source_bindings_pin_full_commit_tree_and_executable_gate(self):
        paths = {row["path"]: row for row in self.contract["source_bindings"]}
        self.assertEqual(
            self.contract["upstream"]["commit"],
            "1539a6ff33867e4cb34f5530cfc137229f7f63f5",
        )
        self.assertEqual(
            self.contract["upstream"]["tree"],
            "1b4eeda4bba8b0d564a216e6841de99a9dd590a2",
        )
        gate = paths[
            "scripts/check_language_p3a2_hbr_r1_runtime_adapter_entry_contract.sh"
        ]
        self.assertEqual(gate["mode"], "100755")
        self.assertEqual(len(paths), 15)

    def test_nonclaims_and_stop_rules_are_closed(self):
        self.assertTrue(all(value is False for value in self.contract["nonclaims"].values()))
        self.assertTrue(all(self.contract["stop_rules"].values()))
        self.assertFalse(self.contract["conditional_fb_s2b"]["performance_execution_authority_granted_here"])
        self.assertFalse(self.contract["positive_qualification_authority"])


if __name__ == "__main__":
    unittest.main()
