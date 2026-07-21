#!/usr/bin/env python3
"""Exact-result regression tests for the formal Majorana P6 S0 replay."""

from __future__ import annotations

from fractions import Fraction
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest import mock


BASE = Path(__file__).resolve().parent
FILE_HASHES = {
    "majorana_certificate_p6_contract.json": "dfe4f6194a0ec6c2f4597c164e30959289e85adc3f31c21cbf899c47494f90ce",
    "majorana_certificate_p6_certificate.json": "4d5eac4084b97021d85995be44d4b829a6281e4a6cf1f0566fd4a9e3319df357",
    "majorana_certificate_p6_precommit_contract.json": "4837c0411ea2392f07340b689e5faf4f04516cf1acb5a0336db1a2b1366c244f",
    "majorana_certificate_p6_checker.py": "5db54434427079c6201c9006f4597ba6e557335577a38ed7230800e101c00b57",
    "majorana_certificate_p6/majorana_p6_runner.jl": "b63143c066d3d258594e27ee4062632632030e9962a0fcd127fcd5000ff9cc1c",
    "majorana_certificate_p6_fixture.json": "fb381c613d675551d33680484a88870020a494e4a356dafd9fd869714c9d475d",
    "majorana_certificate_p6_policy.json": "942dc400a0df39541b083eb4de0e7d16bbc3b975b025a6ac3b6b3911efc8dd47",
    "majorana_certificate_p0_runtime_lock.json": "d54b68d9960cc9912f09a8a20b337804e198c61d5c68852db985cc4b537a1e17",
    "majorana_certificate_p6_design_probe_policy.json": "6a8b9c1c2584cbe8998643e0644f35896d54fe57444eff795a93a83987fa87ab",
    "majorana_certificate_p6_design_probe_report.json": "7c591111ee99b18bf2ccaca2d8157e93a19a3db49b6a680c01b0be13f570fc56",
    "majorana_certificate_p5_contract.json": "8177c2ebe24ef9da5d796ea61fac1ea035b9d1460d9708df0271edd988bd6c32",
    "majorana_certificate_p5_certificate.json": "e99e6d5b9f4f037132d337c203ac5baf4527065f3a2ba2ee2f27565ab935c516",
    "majorana_certificate_p3_contract.json": "1b795f11e76fca543028ce6b82d26b76711598efee61da12de0177a9d577af33",
    "majorana_certificate_p3_certificate.json": "cd861b06721ea945d312c60dac309dd5d350848f3daec42d8eab5892f92ea1bc",
}

PRECOMMIT_COMMIT = "e9c3b2ee9c095d0be6f834fa5f49ede9ec035e75"
CANDIDATE_ID = "E768-MAX-LAZY37-V1"
REPLAY_PACKAGE_SHA256 = "256fba0bcbfbc967717b602773d29e8135e36032dcb2737bab15c467fdc9c8c8"
RAW_WITNESS_SHA256 = "33d4c30f00fae1797cbf266dcdf9eb6e5af4f60868c6bf6a2a081a44ce3c65e9"
RAW_TRANSCRIPT_SHA256 = "bcd72c0291cb98a674cfc2185d711c0a33ea4948c42d630e55d5dd3407d68341"
WITNESS_SHA256 = "73c988137eba4e180ebe98101dd93a06d62f8a9a055ad9db1cf5d94bc77e9d25"
CANDIDATE_DESCRIPTOR_SHA256 = "4255f864e3674af8a70100f8e290497d15b0e66d4362a8d8db0782a43e78a843"
CANDIDATE_RESULT_SHA256 = "6260be7e2fe1009772d64658c8cb2f148bf9ee419759a0cf8e29fe20060f0046"

GRID = 340282366920938463463374607431768211456
PARENT_E1_TICKS = 296986546391593866116533250955376
PRODUCT_TICKS = 148897211350102647194854
MERGE_TICKS = 144697018805603317475573
DROP_TICKS = 850704722871123727134215450394624
LOCAL_TICKS = 850704723164717957289921415065051
CUMULATIVE_TICKS = 1147691269556311823406454666020427
LOCAL_STRICT_MARGIN = 477655051280547406041405747811456
CUMULATIVE_STRICT_MARGIN = 110744113009676098782083674227682811456
LOCAL_FLOOR_SLACK_TICKS = 1194137628201368515103514369
CUMULATIVE_FLOOR_SLACK_TICKS = 553720565048380493910418371138414

COMPONENT_HASHES = {
    "scope": "e4668326eab9e4a8ae9422d000c32de6c0e36f9730bf1fec826cab4fe33d2970",
    "design_parent": "3d73a5552237502d1574e4670242ead75ce0986c3d3b4bc3049d7bf5022238cd",
    "parent_p5": "d03e133be7badba6456732d62e3be742618cc8ace3530b9d6774522117b6c195",
    "parent_p3": "b2b0acaaa46f0458cf9336618fc5b52429d1cf50552847bbc7fb1ec323094f97",
    "candidate_descriptor": CANDIDATE_DESCRIPTOR_SHA256,
    "candidate_result": CANDIDATE_RESULT_SHA256,
    "selection": "8b5e90f03c631c3698656b14e973ecf6852228f88301ed1ef73c7920e75a8f38",
    "step1": "5e590bc8f296b14f853c2e601454759ccb336972f1537b547b0db526c3b80cc6",
    "step1_execution": "0ce9fa3907257064d784ced229641f68e8761cb4b304630444b8db65a5624394",
    "step1_ledger": "19774d946e85f04fbe1d3f97d85d62644adb9ff3e253546ead1e1ddd31abddd3",
    "step1_final": "1aba5cd54742310cd6fa54f90654eb7cafde9a28e12850a93f2ea0c5cc0514d3",
    "step2": "0d25702fc8a27734b491edba7a3e48588adff2ae2109a406c07e3dcfc9649202",
    "step2_execution": "1dc282ef5e219f4129454395ec87628b5ac328fc68234e3dc5a895ea26849568",
    "step2_ledger": "7d13000909f2da1956f953ee5123632d597503c3cc7c551f9da9865f807f001b",
    "step2_final": "106c4a9efaf23972f381a55c80fb20ca1eecf6f6f1d8af611b7f4da78565cfb1",
    "telescoping": "35d07efdc898992cf40190ea95610c196ec9e9937aef132b5d95840a9f1adeab",
    "authoritative_final": "384d1224306ed3c9e2a80b3c5a220841665b530abf1faab66c580f80f73e35b3",
    "authoritative_interval": "f0536260a33bc2f61b5ff539ccda782c1755ff429684c3a89c7d37fa01fd76fc",
}

SELECTION_RESOURCES = {
    "completed_selection_boundary_count": 768,
    "peak_ranking_buffer_terms": 303027,
    "total_ranking_scan_term_visits": 114104682,
    "total_selected_membership_insertions": 4208292,
    "total_selection_work_units": 160531288,
    "total_sort_work_items": 20263438,
    "total_tick_evaluations": 21954876,
}


def _load_checker():
    path = BASE / "majorana_certificate_p6_checker.py"
    spec = importlib.util.spec_from_file_location(
        "majorana_p6_checker_for_result_tests", path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P6 = _load_checker()


class MajoranaP6ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = P6._load_persisted_json(BASE / P6.RESULT_CONTRACT_NAME, BASE)
        cls.certificate = P6._load_persisted_json(BASE / P6.CERTIFICATE_NAME, BASE)
        cls.precommit = P6.load_json(BASE / P6.PRECOMMIT_CONTRACT_NAME)
        cls.fixture = P6.validate_fixture(P6.load_json(BASE / P6.FIXTURE_NAME), BASE)
        cls.runtime = P6.P0.validate_runtime_lock(
            P6.load_json(BASE / P6.RUNTIME_LOCK_NAME),
        )
        cls.policy = P6.validate_policy(
            P6.load_json(BASE / P6.POLICY_NAME), cls.fixture, BASE,
        )
        cls.package = P6._package_from_result(cls.result, cls.precommit, BASE)
        cls.witness = cls.result["witness"]
        cls.raw = cls.witness["raw_witness"]
        cls.candidate = cls.witness["candidate_result"]

    def test_exact_artifact_hashes_canonical_bytes_and_identities(self) -> None:
        for relative, expected in FILE_HASHES.items():
            with self.subTest(relative=relative):
                self.assertEqual(P6.file_sha256(BASE / relative), expected)
        self.assertEqual(
            (BASE / P6.RESULT_CONTRACT_NAME).read_bytes(),
            P6.canonical_bytes(self.result) + b"\n",
        )
        self.assertEqual(
            (BASE / P6.CERTIFICATE_NAME).read_bytes(),
            P6.canonical_bytes(self.certificate) + b"\n",
        )
        self.assertEqual(self.result["contract_type"], P6.RESULT_CONTRACT_TYPE)
        self.assertEqual(
            self.certificate["certificate_type"], P6.CERTIFICATE_TYPE,
        )
        self.assertEqual(self.fixture["fixture_id"], P6.FIXTURE_ID)

    def test_final_verifier_accepts_the_exact_formal_result(self) -> None:
        self.assertEqual(P6.verify_final(BASE), {
            "status": P6.ACCEPT_STATUS,
            "terminal_branch": "CANDIDATE_QUALIFIED",
            "candidate_id": CANDIDATE_ID,
            "candidate_qualified": True,
            "precommit_commit_sha": PRECOMMIT_COMMIT,
            "raw_witness_sha256": RAW_WITNESS_SHA256,
            "canonical_witness_sha256": WITNESS_SHA256,
            "result_contract_sha256": FILE_HASHES[P6.RESULT_CONTRACT_NAME],
            "certificate_sha256": FILE_HASHES[P6.CERTIFICATE_NAME],
            "policy_id": "MAJORANA-P6-S0-E768-MAX-LAZY37-HARDENING-V1",
        })

    def test_replay_package_freshness_isolation_and_custody_are_exact(self) -> None:
        self.assertEqual(self.result["precommit_commit_sha"], PRECOMMIT_COMMIT)
        self.assertEqual(
            self.result["precommit_contract_sha256"],
            FILE_HASHES[P6.PRECOMMIT_CONTRACT_NAME],
        )
        self.assertEqual(self.result["replay_package_sha256"], REPLAY_PACKAGE_SHA256)
        self.assertEqual(
            hashlib.sha256(P6.canonical_bytes(self.package) + b"\n").hexdigest(),
            REPLAY_PACKAGE_SHA256,
        )
        custody = {
            "outer": (self.package["outer_custody_manifest"], "f12ea56fb93c85e8de3bd29fbea2af2c7714c066dfe7fb90bce197d83681ddab"),
            "runner": (self.package["runner_staging_manifest"], "ef54a532a2e679554ce366c3b7028a01d20051a5ffda1bb08f8a060d0429ca46"),
            "environment": (self.result["host_abi_and_locale_custody"], "07860c1eac760479a92059c00dd573f5de571bc13928e6bcde6cd31d22470d3f"),
            "depot": (self.result["depot_custody"], "ce59b3c6d22e4894f8c93034ef30b5de52a925159c9fe8b492d39ae79a8172a5"),
            "host": (self.result["host_resource_enforcement"], "2779b45404366f73d2e237aa349b4ed4e5e834cd97b1678ff1bff0924b5c03c5"),
            "bindings": (self.result["process_bindings"], "280cce47a44a5a09d725f9fbfcf6f38de12a01b8da8573f0970f5e2f42fd0e24"),
        }
        for label, (value, expected) in custody.items():
            with self.subTest(label=label):
                self.assertEqual(P6.canonical_sha256(value), expected)
        self.assertEqual(len(self.package["outer_custody_manifest"]), 67)
        self.assertEqual(len(self.package["runner_staging_manifest"]), 11)
        self.assertEqual(self.result["candidate_id"], CANDIDATE_ID)
        self.assertEqual(self.result["fresh_process_count"], 2)
        self.assertTrue(self.result["two_fresh_processes"])
        self.assertTrue(
            self.result["each_process_executes_step1_then_adaptive_step2_same_process"],
        )
        self.assertFalse(
            self.result[
                "cross_process_state_cache_checkpoint_scratch_or_ranking_state_shared"
            ],
        )
        self.assertTrue(self.result["pair_stdout_byte_identical"])
        self.assertEqual(
            self.result["raw_transcript_sha256_in_order"],
            [RAW_TRANSCRIPT_SHA256, RAW_TRANSCRIPT_SHA256],
        )
        self.assertEqual(
            [row["fresh_replay_ordinal"] for row in self.result["process_bindings"]],
            [1, 2],
        )

    def test_raw_witness_candidate_and_lineage_hashes_are_exact(self) -> None:
        self.assertEqual(P6.canonical_sha256(self.raw), RAW_WITNESS_SHA256)
        self.assertEqual(
            hashlib.sha256(P6.canonical_bytes(self.raw) + b"\n").hexdigest(),
            RAW_TRANSCRIPT_SHA256,
        )
        self.assertEqual(P6.canonical_sha256(self.witness), WITNESS_SHA256)
        self.assertEqual(self.result["canonical_witness_sha256"], WITNESS_SHA256)
        self.assertEqual(self.result["raw_witness_sha256"], RAW_WITNESS_SHA256)
        self.assertEqual(self.witness["raw_witness_sha256"], RAW_WITNESS_SHA256)
        objects = {
            "scope": self.witness["scope"],
            "design_parent": self.witness["design_parent_D0"],
            "parent_p5": self.witness["parent_P5_lineage"],
            "parent_p3": self.witness["parent_P3_authority"],
            "candidate_descriptor": self.raw["candidate"],
            "candidate_result": self.candidate,
            "selection": self.raw["selection_resources"],
        }
        for label, value in objects.items():
            with self.subTest(label=label):
                self.assertEqual(P6.canonical_sha256(value), COMPONENT_HASHES[label])
        self.assertEqual(self.raw["candidate"]["candidate_id"], CANDIDATE_ID)
        self.assertTrue(self.raw["candidate"]["D0_control_candidate_excluded"])
        for forbidden in (
            "candidate_qualified", "terminal_branch", "status",
            "candidate_local_allocation_pass",
        ):
            self.assertNotIn(forbidden, self.raw)

    def test_step1_is_the_exact_P3_prefix_and_E1_is_inherited_once(self) -> None:
        step1 = self.raw["step1"]
        objects = {
            "step1": step1,
            "step1_execution": step1["execution"],
            "step1_ledger": step1["accuracy_ledger"],
            "step1_final": step1["final_state"],
        }
        for label, value in objects.items():
            self.assertEqual(P6.canonical_sha256(value), COMPONENT_HASHES[label])
        self.assertEqual(step1["final_state"]["retained_term_count"], 42704)
        self.assertEqual(
            int(step1["accuracy_ledger"]["total_operator_error_ticks"]),
            PARENT_E1_TICKS,
        )
        parent = self.witness["parent_P3_authority"]
        self.assertEqual(parent["E1_charge_multiplicity"], 1)
        self.assertTrue(parent["active_result_authority_verified_after_fieldwise_conformance"])
        self.assertTrue(self.candidate["step1_P3_fieldwise_conformance"])
        self.assertTrue(self.candidate["parent_P3_E1_inherited"])
        self.assertEqual(
            self.candidate["step1_P3_projection_sha256"],
            parent["canonical_witness_sha256"],
        )
        self.assertFalse(
            self.witness["parent_P5_lineage"]["numeric_error_or_final_state_inherited"],
        )
        self.assertFalse(
            self.certificate[
                "P4_or_P5_numeric_E12_step2_error_final_state_or_terminal_result_inherited"
            ],
        )

    def test_step2_ledgers_resources_selection_and_hashes_are_exact(self) -> None:
        step2 = self.raw["step2"]
        execution = step2["execution"]
        ledger = step2["accuracy_ledger"]
        telescoping = self.candidate["telescoping_ledger"]
        final = self.candidate["authoritative_two_step_final_state"]
        objects = {
            "step2": step2,
            "step2_execution": execution,
            "step2_ledger": ledger,
            "step2_final": step2["final_state"],
            "telescoping": telescoping,
            "authoritative_final": final,
            "authoritative_interval": final["declared_expectation_interval"],
        }
        for label, value in objects.items():
            self.assertEqual(P6.canonical_sha256(value), COMPONENT_HASHES[label])
        self.assertEqual(int(ledger["product_defect_ticks"]), PRODUCT_TICKS)
        self.assertEqual(int(ledger["merge_defect_ticks"]), MERGE_TICKS)
        self.assertEqual(int(ledger["drop_defect_ticks"]), DROP_TICKS)
        self.assertEqual(int(ledger["total_operator_error_ticks"]), LOCAL_TICKS)
        self.assertEqual(LOCAL_TICKS, PRODUCT_TICKS + MERGE_TICKS + DROP_TICKS)
        self.assertIsNone(execution["cap_event"])
        self.assertEqual(
            (
                execution["completed_composite_count"],
                execution["completed_constituent_count"],
                execution["completed_truncation_boundary_count"],
            ),
            (512, 1152, 768),
        )
        self.assertEqual(execution["peak_premerge_contribution_count"], 307507)
        self.assertEqual(execution["peak_postmerge_unique_term_count"], 303027)
        self.assertEqual(execution["threshold_dropped_term_count"], 4208292)
        self.assertEqual(execution["exact_zero_dropped_term_count"], 25344)
        self.assertEqual(
            execution["P2_resource_counters"],
            {
                "cap_scan_term_visits": 159226435,
                "final_evaluation_term_visits": 284847,
                "propagation_term_visits": 159226435,
                "total_charged_term_visits": 426811185,
                "truncation_term_visits": 108073468,
            },
        )
        self.assertEqual(execution["total_P2_plus_accuracy_charged_event_count"], 445136171)
        self.assertEqual(self.raw["selection_resources"], SELECTION_RESOURCES)
        self.assertEqual(self.candidate["selection_resources"], SELECTION_RESOURCES)
        self.assertTrue(
            self.candidate["independent_lazy_equals_full_domain_at_every_completed_boundary"],
        )

    def test_strict_integer_slacks_and_candidate_qualification_are_exact(self) -> None:
        telescoping = self.candidate["telescoping_ledger"]
        self.assertEqual(
            int(telescoping["candidate_step2_local_increment_ticks"]), LOCAL_TICKS,
        )
        self.assertEqual(
            int(telescoping["candidate_cumulative_two_step_operator_error_ticks"]),
            CUMULATIVE_TICKS,
        )
        self.assertEqual(CUMULATIVE_TICKS, PARENT_E1_TICKS + LOCAL_TICKS)
        self.assertEqual(GRID - LOCAL_TICKS * 400000, LOCAL_STRICT_MARGIN)
        self.assertEqual(
            GRID - CUMULATIVE_TICKS * 200000, CUMULATIVE_STRICT_MARGIN,
        )
        self.assertEqual((GRID - 1) // 400000 - LOCAL_TICKS, LOCAL_FLOOR_SLACK_TICKS)
        self.assertEqual(
            (GRID - 1) // 200000 - CUMULATIVE_TICKS,
            CUMULATIVE_FLOOR_SLACK_TICKS,
        )
        self.assertGreater(LOCAL_STRICT_MARGIN, 0)
        self.assertGreater(CUMULATIVE_STRICT_MARGIN, 0)
        self.assertTrue(telescoping["candidate_step2_strictly_within_allocation"])
        self.assertTrue(
            telescoping["candidate_cumulative_strictly_within_allocation"],
        )
        self.assertTrue(
            telescoping["candidate_qualified_iff_both_strict_comparisons"],
        )
        self.assertTrue(self.witness["candidate_qualified"])
        self.assertEqual(self.result["terminal_branch"], "CANDIDATE_QUALIFIED")
        self.assertEqual(self.result["status"], P6.ACCEPT_STATUS)

    def test_authoritative_final_state_is_exact(self) -> None:
        final = self.candidate["authoritative_two_step_final_state"]
        center = 339332874966526595046794425569795637248
        lower = 339331727275257038734971019115129616821
        upper = 339334022657796151358617832024461657675
        self.assertEqual(final["center_lower_ticks"], str(center))
        self.assertEqual(final["center_upper_ticks"], str(center))
        self.assertEqual(final["declared_expectation_lower_ticks"], str(lower))
        self.assertEqual(final["declared_expectation_upper_ticks"], str(upper))
        self.assertEqual(center - lower, CUMULATIVE_TICKS)
        self.assertEqual(upper - center, CUMULATIVE_TICKS)
        self.assertEqual(
            final["checkerboard_Neel_exact_dyadic_center"],
            "1205552546560279108145133/1208925819614629174706176",
        )
        self.assertEqual(
            Fraction(final["checkerboard_Neel_exact_dyadic_center"]),
            Fraction(center, GRID),
        )
        self.assertEqual(final["retained_term_count"], 284847)
        self.assertEqual(
            final["term_stream_sha256"],
            "9bd44992823cc6f8cf731f84954840d4927a972fb6a78c1583c3d8c0983a7c51",
        )
        self.assertEqual(
            final["checkerboard_Neel_contribution_stream_sha256"],
            "040bbec32479375bf9241651eb2c42c96c79747efbc236d9922be8cc4514d25c",
        )
        self.assertEqual(
            final["checkerboard_Neel_expectation_rows_sha256"],
            "4d80c34957c12d8f89f6c966c79292159cb844a388cf2fe75bd6aa5505f4f761",
        )
        self.assertEqual(
            final["checkerboard_Neel_expectation_Float64_diagnostic_bits_hex"],
            "3fefe9244dd5aded",
        )
        self.assertTrue(
            final["declared_interval_uses_parent_E1_once_plus_step2_local_increment"],
        )
        self.assertTrue(final["exact_dyadic_center_and_declared_interval_are_authoritative"])

    def test_certificate_authority_claims_exclusions_and_scope_are_narrow(self) -> None:
        self.assertEqual(
            self.certificate["result_contract_sha256"],
            FILE_HASHES[P6.RESULT_CONTRACT_NAME],
        )
        self.assertEqual(self.certificate["candidate_id"], CANDIDATE_ID)
        self.assertTrue(self.certificate["candidate_qualified"])
        self.assertEqual(self.certificate["status"], P6.ACCEPT_STATUS)
        self.assertEqual(self.certificate["terminal_branch"], "CANDIDATE_QUALIFIED")
        self.assertEqual(
            self.certificate["authority"],
            "fixed_L8_P3_2^-34_step1_then_E768_MAX_LAZY37_V1_step2_two_step_operator_and_checkerboard_Neel_enclosure_only",
        )
        self.assertEqual(tuple(self.certificate["claims"]), P6.CERTIFICATE_CLAIMS)
        self.assertEqual(
            tuple(self.certificate["explicit_exclusions"]),
            P6.CERTIFICATE_EXCLUSIONS,
        )
        self.assertFalse(self.certificate["ready_gate_eligible"])
        self.assertFalse(
            self.certificate["D0_has_scientific_or_qualification_authority"],
        )
        self.assertFalse(
            self.certificate[
                "P4_or_P5_numeric_E12_step2_error_final_state_or_terminal_result_inherited"
            ],
        )
        expected_scope = {"maximum_positive_status": P6.MAXIMUM_STATUS, **self.policy["scope_boundary"]}
        self.assertEqual(self.result["scope"], expected_scope)
        self.assertEqual(self.result["scope"], self.witness["scope"])
        self.assertEqual(
            self.result["scope"]["remaining_98_mapped_steps_or_full_R100"],
            "NOT_ASSESSED",
        )
        self.assertFalse(self.result["scope"]["physical_reference_qualified"])
        self.assertFalse(self.result["scope"]["ready_gate_eligible"])

    def test_tampered_raw_authority_selection_and_json_fail_closed(self) -> None:
        bad_raw = {
            **self.raw,
            "candidate": {**self.raw["candidate"], "candidate_id": "P5-K37-RESOURCE-CONTROL"},
        }
        with (
            mock.patch.object(P6, "_verify_signed_zero_micro_oracle"),
            self.assertRaises((P6.SchemaError, P6.VerificationError)),
        ):
            P6.validate_raw_witness(
                bad_raw, self.fixture, self.runtime, CANDIDATE_ID, BASE,
            )

        bad_authority = {
            **self.package,
            "witness": {**self.witness, "candidate_qualified": False},
        }
        with self.assertRaises(P6.VerificationError):
            P6._certificate_authority_and_claims(bad_authority)

        bad_result = {
            **self.candidate,
            "selection_resources": {
                **self.candidate["selection_resources"],
                "total_selection_work_units": SELECTION_RESOURCES[
                    "total_selection_work_units"
                ] + 1,
            },
        }
        bad_witness = {**self.witness, "candidate_result": bad_result}
        with (
            mock.patch.object(P6, "validate_raw_witness", return_value=self.raw),
            mock.patch.object(
                P6, "_compose_authoritative_witness", return_value=self.witness,
            ),
            self.assertRaises(P6.VerificationError),
        ):
            P6.validate_composed_witness(
                bad_witness, self.fixture, self.policy, self.runtime, BASE,
            )

        for payload in (b'{"x":1,"x":2}', b'{"x":1.0}', b'{"x":-0}'):
            with self.subTest(payload=payload), self.assertRaises(P6.SchemaError):
                P6._strict_persisted_json_loads(
                    payload, source="tampered P6 result", maximum_bytes=1024,
                )

    def test_result_artifacts_were_absent_at_exact_six_precommit(self) -> None:
        repo = Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=BASE, check=True, stdout=subprocess.PIPE,
        ).stdout.decode().strip()).resolve()
        self.assertEqual(
            subprocess.run(
                ["git", "rev-parse", f"{PRECOMMIT_COMMIT}^"],
                cwd=repo, check=True, stdout=subprocess.PIPE,
            ).stdout.decode().strip(),
            P6.REQUIRED_PARENT_COMMIT,
        )
        prefix = BASE.relative_to(repo)
        changed = set(subprocess.run(
            [
                "git", "diff-tree", "--no-commit-id", "--name-only", "-r",
                "--no-renames", PRECOMMIT_COMMIT,
            ],
            cwd=repo, check=True, stdout=subprocess.PIPE,
        ).stdout.decode().splitlines())
        self.assertEqual(changed, {
            (prefix / relative).as_posix()
            for relative in P6.PRECOMMIT_CHANGED_PATHS
        })
        tree = set(subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", PRECOMMIT_COMMIT],
            cwd=repo, check=True, stdout=subprocess.PIPE,
        ).stdout.decode().splitlines())
        self.assertEqual(
            tuple(self.precommit["result_artifacts_required_absent"]),
            P6.RESULT_ARTIFACTS,
        )
        for name in self.precommit["result_artifacts_required_absent"]:
            self.assertNotIn((prefix / name).as_posix(), tree)
        self.assertNotIn(P6.RESULT_TEST_NAME, P6.PRECOMMIT_SOURCE_PATHS)


if __name__ == "__main__":
    unittest.main()
