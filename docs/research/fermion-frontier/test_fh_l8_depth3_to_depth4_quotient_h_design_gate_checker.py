import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
CHECKER = HERE / "fh_l8_depth3_to_depth4_quotient_h_design_gate_checker.py"
CONTRACT = HERE / "fh_l8_depth3_to_depth4_quotient_h_design_gate_contract.json"
CHECKER_FREEZE_COMMIT = "8ecf55a7355bef2d76c4ce56ad3d37bf821adfeb"
CHECKER_FREEZE_TREE = "7c4d702336456898e4d269636568cf824511c3c8"
CONTRACT_FREEZE_COMMIT = "4544d4c0e02103c76e465abea43a08b91367a286"
CONTRACT_FREEZE_TREE = "7a62380575c61f600ea662e6d4f48b625682f5b6"
CHECKER_SHA256 = "b43fcf1613fd2f3abd378c66261d2d01ca325446820bea735b5af4605dd379ae"
CONTRACT_SHA256 = "9557b9523b5d5f29d76a3d02dc50b76553879961dae7d168dc90080529fc61ed"

SPEC = importlib.util.spec_from_file_location("fh_l8_qh_design_gate", CHECKER)
D7 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(D7)


class Depth3ToDepth4QuotientHDesignGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_contract = CONTRACT.read_bytes()
        cls.contract = json.loads(cls.raw_contract)
        cls.evidence = D7.recompute(cls.contract, CONTRACT_FREEZE_COMMIT)

    def test_frozen_identity_chronology_and_no_execution_artifacts(self):
        self.assertEqual(len(CHECKER.read_bytes()), 38614)
        self.assertEqual(hashlib.sha256(CHECKER.read_bytes()).hexdigest(), CHECKER_SHA256)
        self.assertEqual(len(self.raw_contract), 15890)
        self.assertEqual(hashlib.sha256(self.raw_contract).hexdigest(), CONTRACT_SHA256)
        self.assertEqual(self.evidence["contract_id"], D7.CONTRACT_ID)
        self.assertEqual(self.evidence["status"], D7.STATUS)
        self.assertTrue(self.evidence["verified"])
        self.assertEqual(
            self.evidence["chronology"],
            {
                "checker_freeze_commit": CHECKER_FREEZE_COMMIT,
                "checker_freeze_tree": CHECKER_FREEZE_TREE,
                "contract_freeze_commit": CONTRACT_FREEZE_COMMIT,
                "contract_freeze_tree": CONTRACT_FREEZE_TREE,
                "checker_preceded_contract": True,
                "execution_artifacts_absent": True,
            },
        )
        for relative in D7.FORBIDDEN_DESIGN_PATHS:
            self.assertFalse((HERE.parents[2] / relative).exists())

    def test_two_evidence_lanes_are_distinct_nonadditive_and_exactly_pinned(self):
        source = self.contract["source_evidence"]
        self.assertEqual(
            source["full_quotient_semantics_lane"]["route_alias"], D7.FULL_ALIAS
        )
        self.assertEqual(source["support_orbit_lane"]["route_alias"], D7.SUPPORT_ALIAS)
        self.assertNotEqual(
            source["full_quotient_semantics_lane"]["outcome"]["commit"],
            source["support_orbit_lane"]["outcome"]["commit"],
        )
        self.assertTrue(source["relationship"]["shared_D4_inputs"])
        self.assertFalse(source["relationship"]["evidence_is_additive"])
        self.assertTrue(
            source["relationship"]["support_lane_does_not_supply_quotient_hamiltonian_amplitudes"]
        )
        self.assertEqual(self.evidence["source_evidence"]["shared_depth3_counts"], {
            "full_states": 1704285,
            "representatives": 213099,
        })

    def test_raw_candidate_and_group_image_budgets_are_independent(self):
        arithmetic = self.evidence["design_arithmetic"]
        self.assertEqual(213099 * 225, 47947275)
        self.assertEqual(47947275 * 8, 383578200)
        self.assertEqual(213099 * 8, 1704792)
        self.assertEqual(383578200 + 1704792, 385282992)
        self.assertEqual(arithmetic["raw_candidate_action_upper_bound"], 47947275)
        self.assertEqual(arithmetic["candidate_group_image_upper_bound"], 383578200)
        self.assertEqual(arithmetic["total_group_image_upper_bound"], 385282992)
        self.assertEqual(arithmetic["total_byte_table_lookup_upper_bound"], 6164527872)
        self.assertLess(
            arithmetic["raw_candidate_action_upper_bound"],
            arithmetic["inherited_d5b_raw_candidate_cap"],
        )

    def test_fraction_free_bounds_require_checked_i128_merge(self):
        numeric = self.evidence["numeric_bounds"]
        self.assertEqual(numeric["source_amplitude_absolute_upper_bound"], 352**3)
        self.assertEqual(numeric["target_amplitude_absolute_upper_bound"], 352**4)
        self.assertEqual(
            numeric["scaled_target_amplitude_absolute_upper_bound"], 8 * 352**4
        )
        self.assertLess(numeric["single_raw_scaled_delta_absolute_upper_bound"], 2**63)
        self.assertGreater(
            numeric["all_raw_records_partial_sum_absolute_upper_bound"], 2**63 - 1
        )
        self.assertTrue(numeric["global_merge_accumulator_requires_signed_i128"])

    def test_streaming_plan_preserves_memory_and_disk_boundaries_without_certifying_them(self):
        planning = self.contract["future_runner_planning_caps"]
        schedule = planning["schedule"]
        self.assertEqual(52 * 4096 + 107, 213099)
        self.assertEqual(schedule["source_shard_count"], 53)
        self.assertEqual(schedule["max_primary_spool_bytes"], 47947275 * 32)
        self.assertEqual(schedule["max_sort_chunk_bytes"], 262144 * 32)
        self.assertEqual(schedule["max_merge_fan_in"], 32)
        self.assertEqual(schedule["merge_fd_reserve"], 4)
        self.assertEqual(schedule["max_open_file_descriptors"], 64)
        self.assertLessEqual(
            schedule["max_merge_fan_in"] + schedule["merge_fd_reserve"],
            schedule["max_open_file_descriptors"],
        )
        self.assertLessEqual(
            planning["max_live_algorithm_buffer_bytes"], planning["max_process_peak_rss_bytes"]
        )
        self.assertLess(
            planning["max_process_peak_rss_bytes"], planning["memory_high_water_abort_bytes"]
        )
        self.assertLess(
            planning["memory_high_water_abort_bytes"], planning["outer_memory_max_bytes"]
        )
        self.assertEqual(planning["outer_swap_max_bytes"], 0)
        self.assertFalse(planning["packed_source_checkpoint"]["certified_in_this_unit"])
        self.assertFalse(planning["performance_evidence"]["runtime_projection_available"])
        self.assertFalse(planning["performance_evidence"]["measured_peak_RSS_available"])

    def test_lower_static_caps_produce_scoped_no_go_and_never_authorize_execution(self):
        arithmetic = self.contract["design_arithmetic"]
        cap_names = {
            "max_raw_candidate_actions": "raw_candidate_action_upper_bound",
            "max_candidate_canonicalizations": "candidate_canonicalization_upper_bound",
            "max_candidate_group_images": "candidate_group_image_upper_bound",
            "max_source_canonicality_group_images": "source_canonicality_group_image_upper_bound",
            "max_total_group_images": "total_group_image_upper_bound",
        }
        for cap_name, arithmetic_name in cap_names.items():
            caps = copy.deepcopy(self.contract["future_runner_planning_caps"])
            caps[cap_name] = arithmetic[arithmetic_name] - 1
            decision = D7.evaluate_resource_gate(arithmetic, caps)
            self.assertEqual(decision["status"], D7.RESOURCE_NO_GO)
            self.assertFalse(decision["execution_authorized"])
        lowered_contract = copy.deepcopy(self.contract)
        lowered_contract["future_runner_planning_caps"]["max_total_group_images"] -= 1
        evidence = D7.recompute(lowered_contract, CONTRACT_FREEZE_COMMIT)
        self.assertEqual(evidence["status"], D7.RESOURCE_NO_GO)
        self.assertFalse(evidence["resource_decision"]["execution_authorized"])
        self.assertFalse(evidence["authority"]["depth3_to_depth4_execution_authorized"])

    def test_identity_source_arithmetic_cap_and_authority_mutations_fail_closed(self):
        mutations = []
        identity = copy.deepcopy(self.contract)
        identity["contract_id"] = "FH-L8-INDEPENDENT-REFERENCE-D7"
        mutations.append(identity)
        chronology = copy.deepcopy(self.contract)
        chronology["chronology"]["checker_freeze"]["tree"] = "0" * 40
        mutations.append(chronology)
        lane_swap = copy.deepcopy(self.contract)
        lane_swap["source_evidence"]["full_quotient_semantics_lane"]["route_alias"] = D7.SUPPORT_ALIAS
        mutations.append(lane_swap)
        d5a_substitution = copy.deepcopy(self.contract)
        d5a_substitution["source_evidence"]["full_quotient_semantics_lane"]["outcome"]["commit"] = (
            "72fe3b79a79501d5d523dc959a6a98b36a470bd4"
        )
        mutations.append(d5a_substitution)
        artifact = copy.deepcopy(self.contract)
        artifact["source_evidence"]["support_orbit_lane"]["artifacts"][0]["sha256"] = "0" * 64
        mutations.append(artifact)
        additive = copy.deepcopy(self.contract)
        additive["source_evidence"]["relationship"]["evidence_is_additive"] = True
        mutations.append(additive)
        shared = copy.deepcopy(self.contract)
        shared["source_evidence"]["relationship"]["shared_D4_inputs"] = False
        mutations.append(shared)
        duplicate = copy.deepcopy(self.contract)
        duplicate["source_evidence"]["support_orbit_lane"]["artifacts"][0] = copy.deepcopy(
            duplicate["source_evidence"]["support_orbit_lane"]["artifacts"][1]
        )
        mutations.append(duplicate)
        arithmetic = copy.deepcopy(self.contract)
        arithmetic["design_arithmetic"]["symmetry_group_order"] = 225
        mutations.append(arithmetic)
        numeric = copy.deepcopy(self.contract)
        numeric["numeric_bounds"]["global_merge_accumulator_requires_signed_i128"] = False
        mutations.append(numeric)
        fd = copy.deepcopy(self.contract)
        fd["future_runner_planning_caps"]["schedule"]["max_open_file_descriptors"] = 35
        mutations.append(fd)
        cap_uplift = copy.deepcopy(self.contract)
        cap_uplift["future_runner_planning_caps"]["max_candidate_group_images"] += 1
        mutations.append(cap_uplift)
        timing_uplift = copy.deepcopy(self.contract)
        timing_uplift["future_runner_planning_caps"]["performance_evidence"][
            "D6_unretained_14_856_seconds_certifying"
        ] = True
        mutations.append(timing_uplift)
        authority = copy.deepcopy(self.contract)
        authority["authority"]["depth3_to_depth4_execution_authorized"] = True
        mutations.append(authority)
        schema = copy.deepcopy(self.contract)
        schema["unexpected"] = True
        mutations.append(schema)
        for mutation in mutations:
            with self.assertRaises(D7.VerificationError):
                D7.recompute(mutation, CONTRACT_FREEZE_COMMIT)

    def test_design_checker_has_no_scientific_execution_entrypoint(self):
        tree = ast.parse(CHECKER.read_text(encoding="utf-8"))
        imports = {node.names[0].name for node in tree.body if isinstance(node, ast.Import)}
        imports |= {
            node.module
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        self.assertTrue({"hashlib", "json", "subprocess", "pathlib"}.issubset(imports))
        self.assertTrue({"importlib", "numpy", "scipy"}.isdisjoint(imports))
        call_names = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        self.assertTrue(
            {"_sector_action", "_quotient_step", "_canonical_info", "_orbit_digest"}.isdisjoint(
                call_names
            )
        )

    def test_cli_is_structured_for_success_and_malformed_invocation(self):
        success = subprocess.run(
            ["python3", "-B", str(CHECKER), "--contract-commit", CONTRACT_FREEZE_COMMIT],
            cwd=HERE,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(success.returncode, 0, success.stdout + success.stderr)
        self.assertEqual(json.loads(success.stdout)["status"], D7.STATUS)
        malformed = subprocess.run(
            ["python3", "-B", str(CHECKER), "--contract-commit"],
            cwd=HERE,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(malformed.returncode, 1)
        failure = json.loads(malformed.stdout)
        self.assertEqual(failure["status"], "VERIFICATION_FAILED")
        self.assertFalse(failure["verified"])


if __name__ == "__main__":
    unittest.main()
