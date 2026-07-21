#!/usr/bin/env python3
"""Exact-result regression tests for the formal Majorana P4 S0v2 replay."""

from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import importlib.util
from pathlib import Path
import unittest


BASE = Path(__file__).resolve().parent
FILE_HASHES = {
    "majorana_certificate_p4_contract.json": "7d71cf5f71f8efc15f5cb4b9f1cac27f23d3a6ef05ab6925cc2e54772fa3be60",
    "majorana_certificate_p4_certificate.json": "70aa96ff57cf2021099f79786d8f3f14a5d23f0459023603d65f475a463563a0",
    "majorana_certificate_p4_precommit_contract.json": "7dad4f999a84b092785479db7e177b03eb98f20c65cf58a7f63f8089d949972b",
    "majorana_certificate_p4_checker.py": "f1d60e24182b7a1cad805c34e891ee970260b652f7bd69313a3b66fd8e4e6f1c",
    "majorana_certificate_p4/majorana_p4_runner.jl": "f425dbab80d60c49fceefc2b3e805fd3a4b29037f0e95491c50891ed7b7b9f47",
    "majorana_certificate_p4_fixture.json": "b020b6bcc0ed56010af9ed3b1836469c084b9244a9303a8101cf7657adb79964",
    "majorana_certificate_p4_policy.json": "662f8cc345a222c00a61d54b566845c26e008102d4e62e0e065617fd12dc96f4",
    "majorana_certificate_p0_runtime_lock.json": "d54b68d9960cc9912f09a8a20b337804e198c61d5c68852db985cc4b537a1e17",
    "majorana_certificate_p3_contract.json": "1b795f11e76fca543028ce6b82d26b76711598efee61da12de0177a9d577af33",
    "majorana_certificate_p3_certificate.json": "cd861b06721ea945d312c60dac309dd5d350848f3daec42d8eab5892f92ea1bc",
}
PRECOMMIT_COMMIT = "c6c2614186a8315775fa477e025195741c36d582"
REPLAY_PACKAGE_SHA256 = "70ae863ea05192486a371b9981ac7ae397b6bf5bc8a791142ca497bd3370176a"
RAW_WITNESS_SHA256 = "869504938d4081d15fbd62e1353026141ebe41bef019c8a49ff79aebc515c493"
RAW_TRANSCRIPT_SHA256 = "3cdb1108a53cebf604529357c2ea43744f1327982f9bd280ce2787088d2cc2f8"
WITNESS_SHA256 = "b42b1ec0555f8dad15d35fd0f8ef0d35755175b91b3fec9a6e2970bfc406442a"
OUTER_CUSTODY_SHA256 = "21d1ee5bf8073635786deab0d3b52762c441b6cb8548a55c6d77342941e7ec7c"
RUNNER_STAGING_SHA256 = "c6b5ef70816c9a035a8605c65f60c2fd087d936cef1101391e698644bab2e141"
RUNNER_STAGING_TREE_SHA256 = "38e33c7e6c349a2a7b818548ad6272560618eec2cb1b3b37208ee11c5d968312"
ENVIRONMENT_SHA256 = "07860c1eac760479a92059c00dd573f5de571bc13928e6bcde6cd31d22470d3f"
DEPOT_CUSTODY_SHA256 = "ce59b3c6d22e4894f8c93034ef30b5de52a925159c9fe8b492d39ae79a8172a5"
HOST_RESOURCE_SHA256 = "d3657213de1960746bdfa9fa9a7b943c41df0d8faa86432d36a42c7770003e1f"
COMPONENT_HASHES = {
    "raw_witness": RAW_WITNESS_SHA256,
    "parent_P3": "df7de3c75388471ba581603668212fa9f76f5005804bceec35f898096be695e7",
    "telescoping_ledger": "4e66c7b123ac0636de3b5159ee0782852e103228b44d34e1ba389da6b3b0382f",
    "authoritative_final": "8ab3151b766499918cd2808453784001bf3a519110a8c9b3c05b0af9d4f4093f",
    "authoritative_interval": "8ae7d13a3fd6aeeff859abad6a3819ee7a1e886c4429864118da13e345c6d0fd",
    "scope": "2617eed526a2d065c393adfdf98399261d1e94463af36393277a4020d7db9ff7",
    "runtime": "5161103e46ab4b2b647b1a4215faa75e094a7c182c05a4e1ad413cf4f0a58c54",
    "upstream": "8926d042a9f1dd2ad3e3bd09ca338f0e14f8a7528103a43f434a5f2e4b75e149",
    "initial": "862dd596ff43a349e9735e049acae39b9d5697e81ea16313c86095411fea63ae",
    "schedule": "30b8715d2bd878bf1868d0c18c35c85c18b30ee9ac68fbd9be9948cb42a06007",
    "trig_table": "e9debed19b33f2fb497b2a576c8b0509bcf4547551dc8a6fb9bbaf688061b649",
    "trig_entries": "2cf79510f1f76728e9cbe22cd168d220845b0be328833d04f0da322da331ee0a",
    "step_boundary_link": "e1f89a571357ebd2499c28476a357c0829c60a1c473dfcb402283785144d3e8f",
}
STEP_HASHES = {
    "step1": "5e590bc8f296b14f853c2e601454759ccb336972f1537b547b0db526c3b80cc6",
    "step2": "777b933140d99e06ef70640567dc623bc38da1561aa4a9b7f9fc33a176074741",
    "step1_execution": "0ce9fa3907257064d784ced229641f68e8761cb4b304630444b8db65a5624394",
    "step2_execution": "6df0d0e81fc53d6a618a758781c51cff7a73d8a243ba8317f7b7c73f6b74ea17",
    "step1_ledger": "19774d946e85f04fbe1d3f97d85d62644adb9ff3e253546ead1e1ddd31abddd3",
    "step2_ledger": "d57a0a30a07f03b5682eb6c1a55b9b0dd9e5023daccfcaeb8628eee4a4c502e8",
    "step1_transitions": "f7e8e0e262a78b165a64d2014a7b5cad08014be8a3f2dab38d20d39dfe12d357",
    "step2_transitions": "1d68bf6b5694cc7c2300d3f69fa351fc9e9e9e9a86888b69e8551146df10a477",
    "step1_boundaries": "82a4e39d22faf87a15aad083b9c57b245187de82ac97d4e6796ba2f66d601d9f",
    "step2_boundaries": "b0194330310fcd7d7a2e9564a7395c895453695b77dbd476d3ed2fb1b452af01",
    "step1_stages": "e43d24de27a615209bfbb50ea364246bc3c185647e5dd0e1a5d56d9ed91f8c70",
    "step2_stages": "3189829c3f56c9eca98fe46178c55c6941ab495588be4871890a3a5c6b35dd40",
    "step1_final": "1aba5cd54742310cd6fa54f90654eb7cafde9a28e12850a93f2ea0c5cc0514d3",
    "step2_local_final": "d27f2871425eb788aa93e385914244a9a90c490fefe6e965488127f087b74731",
}
GRID = 340282366920938463463374607431768211456
PARENT_TICKS = 296986546391593866116533250955376
STEP2_PRODUCT_TICKS = 148110706480666299015145
STEP2_MERGE_TICKS = 145718728421478199062528
STEP2_DROP_TICKS = 4432692192952477384756578989637632
STEP2_LOCAL_TICKS = 4432692193246306819658723487715305
CUMULATIVE_TICKS = 4729678739637900685775256738670681

def _load_checker():
    path = BASE / "majorana_certificate_p4_checker.py"
    spec = importlib.util.spec_from_file_location(
        "majorana_p4_checker_for_result_tests", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P4 = _load_checker()


class MajoranaP4ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = P4.load_json(BASE / P4.RESULT_CONTRACT_NAME)
        cls.certificate = P4.load_json(BASE / P4.CERTIFICATE_NAME)
        cls.precommit = P4.load_json(BASE / P4.PRECOMMIT_CONTRACT_NAME)
        cls.fixture = P4.validate_fixture(P4.load_json(BASE / P4.FIXTURE_NAME))
        cls.runtime = P4.P0.validate_runtime_lock(P4.load_json(BASE / P4.RUNTIME_LOCK_NAME))
        cls.policy = P4.validate_policy(P4.load_json(BASE / P4.POLICY_NAME), cls.runtime)
        cls.package = P4._package_from_result(cls.result, cls.precommit, BASE)
        cls.witness = cls.result["witness"]
        cls.raw = cls.witness["raw_witness"]
        cls.step1, cls.step2 = cls.raw["steps"]
        cls.telescoping = cls.witness["telescoping_ledger"]
        cls.final = cls.witness["authoritative_two_step_final_state"]

    def test_exact_artifact_hashes_canonical_bytes_and_v2_identity(self) -> None:
        for relative, expected in FILE_HASHES.items():
            with self.subTest(relative=relative):
                self.assertEqual(P4.file_sha256(BASE / relative), expected)
        self.assertEqual((BASE / P4.RESULT_CONTRACT_NAME).read_bytes(), P4.canonical_bytes(self.result) + b"\n")
        self.assertEqual((BASE / P4.CERTIFICATE_NAME).read_bytes(), P4.canonical_bytes(self.certificate) + b"\n")
        self.assertEqual(self.result["contract_type"], "majorana_p4_formal_two_step_result_contract_v2")
        self.assertEqual(self.certificate["certificate_type"], "majorana_p4_adjacent_two_step_local_defect_bound_subcertificate_v2")
        self.assertEqual(self.fixture["fixture_id"], "MAJORANA-P4-L8-FUSED-TWO-STEP-LOCAL-DEFECT-V2")
        self.assertEqual(self.policy["policy_id"], "MAJORANA-P4-S0V2")

    def test_final_verifier_accepts_the_formal_result_once(self) -> None:
        summary = P4.verify_final(BASE)
        self.assertEqual(
            summary,
            {
                "status": P4.EXCEEDS_STATUS,
                "terminal_branch": "TWO_STEP_CUMULATIVE_BOUND_EXCEEDS_ALLOCATION",
                "precommit_commit_sha": PRECOMMIT_COMMIT,
                "raw_witness_sha256": RAW_WITNESS_SHA256,
                "canonical_witness_sha256": WITNESS_SHA256,
                "result_contract_sha256": FILE_HASHES[P4.RESULT_CONTRACT_NAME],
                "certificate_sha256": FILE_HASHES[P4.CERTIFICATE_NAME],
                "policy_id": "MAJORANA-P4-S0V2",
            },
        )

    def test_replay_package_custody_freshness_and_isolation_are_exact(self) -> None:
        self.assertEqual(self.result["precommit_commit_sha"], PRECOMMIT_COMMIT)
        self.assertEqual(self.result["precommit_contract_sha256"], FILE_HASHES[P4.PRECOMMIT_CONTRACT_NAME])
        self.assertEqual(self.result["replay_package_sha256"], REPLAY_PACKAGE_SHA256)
        self.assertEqual(hashlib.sha256(P4.canonical_bytes(self.package) + b"\n").hexdigest(), REPLAY_PACKAGE_SHA256)
        custody = {
            "outer": (self.package["outer_custody_manifest"], OUTER_CUSTODY_SHA256),
            "runner": (self.package["runner_staging_manifest"], RUNNER_STAGING_SHA256),
            "environment": (self.result["host_abi_and_locale_custody"], ENVIRONMENT_SHA256),
            "depot": (self.result["depot_custody"], DEPOT_CUSTODY_SHA256),
            "host_resource": (self.result["host_resource_enforcement"], HOST_RESOURCE_SHA256),
        }
        for label, (value, expected) in custody.items():
            with self.subTest(label=label):
                self.assertEqual(P4.canonical_sha256(value), expected)
        self.assertEqual(self.result["outer_custody_manifest_sha256"], OUTER_CUSTODY_SHA256)
        self.assertEqual(self.result["runner_staging_manifest_sha256"], RUNNER_STAGING_SHA256)
        self.assertEqual(self.result["runner_staging_tree_sha256"], RUNNER_STAGING_TREE_SHA256)
        self.assertEqual(self.result["host_abi_and_locale_custody_sha256"], ENVIRONMENT_SHA256)
        self.assertEqual(self.package["package_type"], "majorana_p4_formal_fresh_two_step_replay_package_v2")
        self.assertEqual(self.result["fresh_process_count"], 2)
        self.assertTrue(self.result["each_process_executes_step1_then_step2_same_process"])
        self.assertTrue(self.result["stdout_byte_identical"])
        self.assertEqual(self.result["raw_transcript_sha256_in_order"], [RAW_TRANSCRIPT_SHA256] * 2)
        self.assertEqual(self.result["raw_witness_sha256"], RAW_WITNESS_SHA256)
        self.assertEqual(self.result["canonical_witness_sha256"], WITNESS_SHA256)
        self.assertEqual(self.result["network_isolation"], "bubblewrap_unshared_network_namespace")
        self.assertEqual(self.result["PID_isolation"], "bubblewrap_unshared_PID_namespace")
        self.assertEqual(self.result["mount_isolation"], "eight_file_runner_stage_plus_runtime_depot_scratch_18_file_host_environment_and_private_proc_dev_only")
        self.assertEqual(self.result["host_resource_enforcement"]["MemoryMax_bytes"], 4294967296)
        self.assertEqual(self.result["host_resource_enforcement"]["RuntimeMaxSec"], "600s")

    def test_exact_composed_raw_and_common_component_hashes(self) -> None:
        objects = {
            "raw_witness": self.raw,
            "parent_P3": self.witness["parent_P3"],
            "telescoping_ledger": self.telescoping,
            "authoritative_final": self.final,
            "authoritative_interval": self.final["declared_expectation_interval"],
            "scope": self.witness["scope"],
            "runtime": self.raw["runtime"],
            "upstream": self.raw["upstream"],
            "initial": self.raw["initial_observable"],
            "schedule": self.raw["schedule"],
            "trig_table": self.raw["trig_table"],
            "trig_entries": self.raw["trig_table"]["entries"],
            "step_boundary_link": self.raw["step_boundary_link"],
        }
        self.assertEqual(P4.canonical_sha256(self.witness), WITNESS_SHA256)
        for label, value in objects.items():
            with self.subTest(label=label):
                self.assertEqual(P4.canonical_sha256(value), COMPONENT_HASHES[label])
        self.assertEqual(self.witness["fixture_canonical_sha256"], "40f79c2a7fb9119f4014c9674a7a2f87ed7104d1b49ecf439a3a99097ca18d38")

    def test_both_steps_have_exact_schedule_counts_and_record_hashes(self) -> None:
        schedule = self.raw["schedule"]
        self.assertEqual((schedule["composite_count"], schedule["constituent_count"]), (512, 1152))
        self.assertEqual((schedule["truncation_boundary_count"], schedule["stage_count"]), (768, 9))
        objects = {
            "step1": self.step1,
            "step2": self.step2,
            "step1_execution": self.step1["execution"],
            "step2_execution": self.step2["execution"],
            "step1_ledger": self.step1["accuracy_ledger"],
            "step2_ledger": self.step2["accuracy_ledger"],
            "step1_transitions": self.step1["execution"]["transition_records"],
            "step2_transitions": self.step2["execution"]["transition_records"],
            "step1_boundaries": self.step1["execution"]["boundary_records"],
            "step2_boundaries": self.step2["execution"]["boundary_records"],
            "step1_stages": self.step1["execution"]["stage_records"],
            "step2_stages": self.step2["execution"]["stage_records"],
            "step1_final": self.step1["final_state"],
            "step2_local_final": self.step2["final_state"],
        }
        for label, value in objects.items():
            with self.subTest(label=label):
                self.assertEqual(P4.canonical_sha256(value), STEP_HASHES[label])
        for index, step in enumerate((self.step1, self.step2), 1):
            execution = step["execution"]
            self.assertEqual(step["step_index"], index)
            self.assertIsNone(execution["cap_event"])
            self.assertEqual((execution["completed_composite_count"], execution["completed_constituent_count"], execution["completed_truncation_boundary_count"]), (512, 1152, 768))
            self.assertEqual(tuple(map(len, (execution["transition_records"], execution["boundary_records"], execution["stage_records"]))), (1152, 768, 9))
        self.assertEqual((self.step1["final_state"]["retained_term_count"], self.step2["final_state"]["retained_term_count"]), (42704, 72808))

    def test_step_boundary_is_same_process_and_step2_resets_local_accounting(self) -> None:
        link = self.raw["step_boundary_link"]
        expected_stream = "067f02a72d50f8061c746896d9eb02e3b60f7e5d6b42f21f0191b8e5887a9c9e"
        self.assertEqual(
            link,
            {
                "no_serialization": True,
                "same_process": True,
                "step1_output_term_count": 42704,
                "step1_output_term_stream_sha256": expected_stream,
                "step2_input_term_count": 42704,
                "step2_input_term_stream_sha256": expected_stream,
            },
        )
        self.assertEqual(self.step2["input_state"], {"term_count": 42704, "term_stream_sha256": expected_stream})
        self.assertEqual(self.step1["final_state"]["term_stream_sha256"], expected_stream)
        self.assertEqual(self.step2["accuracy_ledger"]["total_operator_error_ticks"], str(STEP2_LOCAL_TICKS))
        self.assertFalse(self.step2["final_state"]["exact_dyadic_center_and_declared_interval_are_authoritative"])
        self.assertTrue(self.step2["final_state"]["local_only_interval_is_not_two_step_authority"])
        self.assertFalse(self.raw["scope"]["checkpoint_or_serialized_state_used"])

    def test_parent_p3_conforms_and_its_error_is_inherited_exactly_once(self) -> None:
        parent = self.witness["parent_P3"]
        self.assertEqual(parent["direct_parent_commit"], "d5b63abe941ff0a723dd7c15a61b9ab8298286ab")
        self.assertEqual(parent["result_contract_sha256"], FILE_HASHES["majorana_certificate_p3_contract.json"])
        self.assertEqual(parent["certificate_sha256"], FILE_HASHES["majorana_certificate_p3_certificate.json"])
        self.assertEqual(parent["canonical_witness_sha256"], "6b4354b7f26db198427a74cfc7eac08c1895fda8d397918a9733fe7e32e8d7f5")
        self.assertEqual(parent["fresh_step1_projection_sha256"], parent["canonical_witness_sha256"])
        self.assertTrue(parent["fresh_step1_fieldwise_conformance"])
        self.assertTrue(parent["operator_error_inheritance_applied"])
        self.assertEqual(parent["operator_error_charge_multiplicity"], 1)
        self.assertEqual(int(self.telescoping["parent_P3_operator_error_ticks"]), PARENT_TICKS)
        self.assertEqual(int(self.telescoping["fresh_step1_recomputed_operator_error_ticks"]), PARENT_TICKS)
        self.assertTrue(self.telescoping["fresh_step1_recomputation_is_conformance_not_a_second_charge"])
        self.assertEqual(self.telescoping["exact_unitary_parent_error_propagation_factor"], 1)
        self.assertEqual(CUMULATIVE_TICKS, PARENT_TICKS + STEP2_LOCAL_TICKS)
        self.assertNotEqual(CUMULATIVE_TICKS, PARENT_TICKS * 2 + STEP2_LOCAL_TICKS)

    def test_step2_local_defect_ledger_is_exact_and_drop_dominated(self) -> None:
        ledger = self.step2["accuracy_ledger"]
        self.assertEqual(int(ledger["product_defect_ticks"]), STEP2_PRODUCT_TICKS)
        self.assertEqual(int(ledger["merge_defect_ticks"]), STEP2_MERGE_TICKS)
        self.assertEqual(int(ledger["drop_defect_ticks"]), STEP2_DROP_TICKS)
        self.assertEqual(int(ledger["total_operator_error_ticks"]), STEP2_LOCAL_TICKS)
        self.assertEqual(STEP2_LOCAL_TICKS, STEP2_PRODUCT_TICKS + STEP2_MERGE_TICKS + STEP2_DROP_TICKS)
        self.assertGreater(STEP2_DROP_TICKS, STEP2_PRODUCT_TICKS + STEP2_MERGE_TICKS)
        self.assertEqual(
            (ledger["product_defect_event_count"], ledger["merge_defect_event_count"], ledger["drop_defect_event_count"]),
            (4603256, 633544, 1637980),
        )
        self.assertEqual(ledger["accuracy_charged_event_count"], 6874780)
        self.assertEqual(ledger["product_defect_event_count"], 2 * ledger["anticommuting_event_count"])
        self.assertEqual(self.telescoping["composition_identity"], "parent_E1_once_plus_step2_local_increment")
        self.assertTrue(self.telescoping["outward_widening_not_double_counted"])

    def test_exact_integer_allocations_select_the_cumulative_exceeds_branch(self) -> None:
        self.assertEqual(int(self.telescoping["grid_denominator"]), GRID)
        self.assertEqual(int(self.telescoping["step2_local_increment_ticks"]), STEP2_LOCAL_TICKS)
        self.assertEqual(int(self.telescoping["cumulative_two_step_operator_error_ticks"]), CUMULATIVE_TICKS)
        self.assertEqual(self.telescoping["step2_local_allocation"], "1/400000")
        self.assertEqual(self.telescoping["two_step_cumulative_allocation"], "1/200000")
        self.assertFalse(self.telescoping["step2_strictly_within_allocation"])
        self.assertFalse(self.telescoping["two_step_strictly_within_allocation"])
        self.assertGreaterEqual(STEP2_LOCAL_TICKS * 400000, GRID)
        self.assertGreaterEqual(CUMULATIVE_TICKS * 200000, GRID)
        self.assertEqual(self.result["terminal_branch"], "TWO_STEP_CUMULATIVE_BOUND_EXCEEDS_ALLOCATION")
        self.assertEqual(self.result["status"], P4.EXCEEDS_STATUS)
        self.assertNotEqual(self.result["status"], P4.MAXIMUM_STATUS)
        self.assertEqual(self.witness["terminal_branch"], self.result["terminal_branch"])
        self.assertEqual(self.certificate["status"], self.result["status"])

    def test_neel_center_and_cumulative_interval_are_exact(self) -> None:
        center = 339332875093402413778729622401137508352
        lower = center - CUMULATIVE_TICKS
        upper = center + CUMULATIVE_TICKS
        self.assertEqual(self.final["center_lower_ticks"], str(center))
        self.assertEqual(self.final["center_upper_ticks"], str(center))
        self.assertEqual(self.final["declared_expectation_lower_ticks"], str(lower))
        self.assertEqual(self.final["declared_expectation_upper_ticks"], str(upper))
        self.assertEqual(self.final["checkerboard_Neel_exact_dyadic_center"], str(Fraction(center, GRID)))
        self.assertEqual(self.final["declared_expectation_interval"], {"lower": str(Fraction(lower, GRID)), "upper": str(Fraction(upper, GRID))})
        self.assertEqual(self.final["retained_term_count"], 72808)
        self.assertEqual(self.final["term_stream_sha256"], "3f7e40ece6f7a15c06f30dce25b862fc476d39fc98089ead41cefdf1e2b07d6d")
        self.assertEqual(self.final["checkerboard_Neel_contribution_stream_sha256"], "7aa130e9e6f44283fe0e3e7542704dfbc50f308b473c647d69738bb68f12c518")
        self.assertEqual(self.final["checkerboard_Neel_expectation_rows_sha256"], "21e4a78037aff07b64d32db07cac90823d5ddd08515ac1e94392919b3745bbc2")
        self.assertEqual(self.final["checkerboard_Neel_expectation_Float64_diagnostic_bits_hex"], "3fefe9244e08ec99")
        self.assertTrue(self.final["declared_interval_uses_parent_E1_once_plus_step2_local_increment"])
        self.assertTrue(self.final["exact_dyadic_center_and_declared_interval_are_authoritative"])
        self.assertNotIn("local_only_interval_is_not_two_step_authority", self.final)

    def test_certificate_claims_exclusions_and_scope_are_exact(self) -> None:
        self.assertEqual(self.certificate["result_contract_sha256"], FILE_HASHES[P4.RESULT_CONTRACT_NAME])
        self.assertEqual(self.certificate["raw_witness_sha256"], RAW_WITNESS_SHA256)
        self.assertEqual(self.certificate["canonical_witness_sha256"], WITNESS_SHA256)
        self.assertEqual(self.certificate["telescoping_ledger_sha256"], COMPONENT_HASHES["telescoping_ledger"])
        self.assertEqual(tuple(self.certificate["claims"]), P4.CERTIFICATE_CLAIMS)
        self.assertEqual(tuple(self.certificate["explicit_exclusions"]), P4.CERTIFICATE_EXCLUSIONS)
        self.assertEqual(self.certificate["authority"], "fixed_L8_first_two_adjacent_fused_product_formula_steps_operator_and_checkerboard_Neel_expectation_enclosure_only")
        self.assertFalse(self.certificate["ready_gate_eligible"])
        expected_scope = {"maximum_positive_status": P4.MAXIMUM_STATUS, **self.policy["scope_boundary"]}
        self.assertEqual(self.result["scope"], expected_scope)
        self.assertEqual(self.result["scope"], self.witness["scope"])
        self.assertEqual(self.result["scope"]["remaining_98_mapped_steps_or_full_R100"], "NOT_ASSESSED")
        self.assertEqual(self.result["scope"]["product_formula_to_exact_Hubbard_error_or_exact_time_evolution"], "NOT_ASSESSED")
        self.assertFalse(self.result["scope"]["ready_gate_eligible"])
        self.assertTrue(self.result["scope"]["P4_does_not_retroactively_expand_P3_authority"])

    def test_legacy_v1_raw_and_package_identities_fail_closed(self) -> None:
        legacy_package = copy.deepcopy(self.package)
        legacy_package["package_type"] = "majorana_p4_formal_fresh_two_step_replay_package_v1"
        with self.assertRaisesRegex(P4.SchemaError, "unexpected P4 replay package identity"):
            P4._validate_replay_package(legacy_package, BASE)
        legacy_raw = copy.deepcopy(self.raw)
        legacy_raw["witness_type"] = "majorana_p4_L8_two_fused_steps_execution_raw_v1"
        with self.assertRaisesRegex(P4.SchemaError, "unexpected P4 raw witness identity"):
            P4.validate_raw_witness(legacy_raw, self.fixture, self.runtime, BASE)
        legacy_types = {
            "majorana_p4_L8_two_step_composed_authoritative_witness_v1",
            "majorana_p4_formal_two_step_result_contract_v1",
            "majorana_p4_adjacent_two_step_local_defect_bound_subcertificate_v1",
        }
        current_types = {
            self.witness["witness_type"],
            self.result["contract_type"],
            self.certificate["certificate_type"],
        }
        self.assertTrue(legacy_types.isdisjoint(current_types))
        self.assertNotIn(b"majorana_p4_formal_two_step_result_contract_v1", P4.canonical_bytes(self.result))


if __name__ == "__main__":
    unittest.main()
