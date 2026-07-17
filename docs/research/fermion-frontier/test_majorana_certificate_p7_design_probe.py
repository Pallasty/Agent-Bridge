#!/usr/bin/env python3
"""Preprobe and adversarial tests for the non-authoritative P7 D0 probe."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import random
import re
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


BASE = Path(__file__).resolve().parent


def _load_probe():
    path = BASE / "majorana_certificate_p7_design_probe.py"
    spec = importlib.util.spec_from_file_location("majorana_p7_d0", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P7 = _load_probe()


class MajoranaP7DesignProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = P7._validate_fixture(P7.load_json(BASE / P7.FIXTURE_NAME))
        cls.policy = P7.validate_policy(
            P7.load_json(BASE / P7.POLICY_NAME), require_report_absent=True,
        )

    def _complete_witness(self) -> dict:
        projection = copy.deepcopy(
            self.fixture["expected_P6_prefix_resource_projection"]
        )
        step1 = projection["step1"]
        step2 = projection["step2"]
        link12 = {
            "same_process": projection["step_link"]["same_process"],
            "checkpoint_or_serialized_state_used": projection[
                "step_link"
            ]["checkpoint_or_serialized_state_used"],
            "previous_step_final_term_count":
                projection["step_link"]["step1_final_term_count"],
            "next_step_input_term_count":
                projection["step_link"]["step2_input_term_count"],
        }
        step3 = copy.deepcopy(step2)
        link23 = {
            "same_process": True,
            "checkpoint_or_serialized_state_used": False,
            "previous_step_final_term_count":
                step2["final_retained_term_count"],
            "next_step_input_term_count":
                step2["final_retained_term_count"],
        }
        fixture_path = BASE / P7.FIXTURE_NAME
        return {
            "schema_version": 1,
            "probe_type": P7.PROBE_TYPE,
            "fixture_id": P7.FIXTURE_ID,
            "fixture_sha256": P7.file_sha256(fixture_path),
            "fixture_canonical_sha256": P7.canonical_sha256(self.fixture),
            "scientific_authority": "NONE",
            "certificate_eligible": False,
            "result_contract_eligible": False,
            "resource_observations_only": True,
            "candidate": {
                "candidate_id": P7.CANDIDATE_ID,
                "probe_mode": P7.PROBE_MODE,
                "identity": P7.PROBE_MODE,
                "formal_candidate": True,
                "step1_path": "fixed_P3_2^-34",
                "step2_path": "frozen_P6_E768_MAX_LAZY37_V1",
                "step3_path": "full_domain_E768_MAX_LAZY37_STEP3_V1",
            },
            "runtime_custody": copy.deepcopy(self.fixture["runtime_custody"]),
            "step1": step1,
            "step2": step2,
            "step3": step3,
            "step1_to_step2_link": link12,
            "step2_to_step3_link": link23,
            "step2_selection_resources":
                projection["selection_resources"],
            "step3_selection_resources":
                copy.deepcopy(projection["selection_resources"]),
            "P6_prefix_resource_projection_conformed": True,
            "step3_started": True,
            "explicit_exclusions": copy.deepcopy(P7.PUBLIC_EXCLUSIONS),
        }

    def _cap_summary(self, summary: dict, label: str) -> None:
        limits = P7._step_cap_limits(label)
        cap_name = (
            "final_evaluation_term_visits"
            if label == "step1"
            else "maximum_final_evaluation_term_visits"
        )
        old_final = summary["P2_resource_counters"][
            "final_evaluation_term_visits"
        ]
        summary["P2_resource_counters"]["final_evaluation_term_visits"] = 0
        summary["P2_resource_counters"]["total_charged_term_visits"] -= old_final
        summary["total_P2_plus_accuracy_charged_event_count"] -= old_final
        summary["final_retained_term_count"] = None
        context = {"operation": "resource_cap_precheck"}
        if label == "step3":
            context["mapped_step_index"] = 3
        summary["cap_event"] = {
            "cap_name": cap_name,
            "limit": limits[cap_name],
            "attempted": limits[cap_name] + 1,
            "context": context,
            "rejected_operation_was_not_executed_after_cap_detection": True,
        }

    def _observation(self, witness: dict | None = None) -> dict:
        witness = self._complete_witness() if witness is None else witness
        stdout = P7.canonical_bytes(witness) + b"\n"
        return {
            "probe_mode": P7.PROBE_MODE,
            "candidate_id": P7.CANDIDATE_ID,
            "process_returncode": 0,
            "outer_timeout_triggered": False,
            "stdout_bytes": len(stdout),
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_bytes": 0,
            "stderr_sha256": hashlib.sha256(b"").hexdigest(),
            "outer_monotonic_elapsed_ns": 1,
            "time_diagnostics": {
                "user_time_seconds": "1.0",
                "system_time_seconds": "0.1",
                "elapsed_wall_clock": "0:01.00",
                "maximum_resident_set_size_KiB": 1,
                "minor_page_faults": 0,
                "major_page_faults": 0,
            },
            "host_failure_has_no_mathematical_authority": True,
            "status": "COMPLETED_RESOURCE_OBSERVATION",
            "resource_witness": witness,
            "resource_witness_sha256": P7.canonical_sha256(witness),
        }

    def _indeterminate_observation(self) -> dict:
        row = self._observation()
        row.pop("resource_witness_sha256")
        row.update({
            "process_returncode": -9,
            "stdout_bytes": 0,
            "stdout_sha256": hashlib.sha256(b"").hexdigest(),
            "status": "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
            "resource_witness": None,
            "time_diagnostics": {},
        })
        return row

    def _staging_manifest(self) -> list[dict]:
        with tempfile.TemporaryDirectory() as temporary:
            return P7.stage_probe_tree(Path(temporary), self.policy)

    def _report(self, observation: dict | None = None) -> dict:
        observation = self._observation() if observation is None else observation
        manifest = self._staging_manifest()
        return {
            "schema_version": 1,
            "report_type": P7.REPORT_TYPE,
            "policy_id": P7.POLICY_ID,
            "policy_sha256": P7.file_sha256(BASE / P7.POLICY_NAME),
            "fixture_id": P7.FIXTURE_ID,
            "fixture_sha256": P7.file_sha256(BASE / P7.FIXTURE_NAME),
            "fixture_canonical_sha256": P7.canonical_sha256(self.fixture),
            "preprobe_commit_sha": "a" * 40,
            "scientific_authority": "NONE",
            "certificate_eligible": False,
            "formal_candidate_was_frozen_before_probe": P7.CANDIDATE_ID,
            "staging_manifest": manifest,
            "staging_manifest_sha256": P7.canonical_sha256(manifest),
            "host_caps": copy.deepcopy(self.fixture["host_supervisor_caps"]),
            "observations": [observation],
            "fixed_formal_admission":
                P7._fixed_formal_admission(observation, self.policy),
            "authority_exclusions":
                copy.deepcopy(self.policy["authority_exclusions"]),
        }

    def test_duplicate_key_json_is_rejected(self) -> None:
        with self.assertRaisesRegex(P7.ProbeError, "duplicate JSON key"):
            P7.loads_json('{"a":1,"a":2}', "duplicate")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.json"
            path.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaisesRegex(P7.ProbeError, "duplicate JSON key"):
                P7.load_json(path)

    def test_policy_fixture_identity_and_preprobe_absence(self) -> None:
        self.assertEqual(self.fixture["fixture_id"], P7.FIXTURE_ID)
        self.assertEqual(self.policy["policy_id"], P7.POLICY_ID)
        self.assertEqual(
            self.fixture["required_direct_parent_commit"], P7.DIRECT_PARENT,
        )
        self.assertFalse((BASE / P7.REPORT_NAME).exists())
        for relative in P7.RESULT_ARTIFACTS:
            self.assertFalse((BASE / relative).exists(), relative)

    def test_single_candidate_P6_informed_firewall_is_frozen(self) -> None:
        design = self.fixture["candidate_design"]
        self.assertEqual(design["formal_candidates"], [P7.CANDIDATE_ID])
        self.assertEqual(design["formal_candidate_count"], 1)
        self.assertIsNone(design["control_candidate"])
        self.assertEqual(
            design["design_disclosure"], "P6_INFORMED_P7_RESULT_UNPINNED",
        )
        self.assertTrue(design["P6_observed_local_slack_is_not_a_step3_budget_input"])
        self.assertNotIn("CONTROL_MODE", vars(P7))
        self.assertNotIn("CANDIDATE_IDS", vars(P7))

    def test_fixed_admission_and_schedule_derived_caps_are_exact(self) -> None:
        caps = self.fixture["deterministic_step3_probe_caps"]
        selection = self.fixture["deterministic_step3_selection_probe_caps"]
        host = self.fixture["host_supervisor_caps"]
        self.assertEqual(
            caps["maximum_step3_current_terms_before_constituent"], 1 << 20,
        )
        self.assertEqual(caps["maximum_step3_total_P2_charged_term_visits"], 1 << 32)
        self.assertEqual(caps["maximum_step3_accuracy_charged_events"], 1 << 33)
        self.assertEqual(selection["maximum_total_selection_work_units"], 1 << 32)
        self.assertEqual(
            (host["MemoryMax_bytes"], host["MemorySwapMax_bytes"],
             host["RuntimeMaxSec"]),
            (1 << 31, 0, "1800s"),
        )
        text = P7.canonical_bytes(self.policy).decode()
        self.assertNotIn("two_times_the_maximum_completed", text)

    def test_lazy_reference_matches_full_domain_bruteforce_randomized(self) -> None:
        generator = random.Random(0xE76837)
        split = 0x3DA0000000000000
        for case in range(3000):
            rows = []
            for mask in range(generator.randrange(0, 60)):
                bits = generator.randrange(split - 1000, split + 1000)
                rows.append({
                    "point_abs_ticks": (bits - (split - 1000)) // 7,
                    "abs_bits": bits,
                    "mask": mask,
                    "coefficient_bits": bits,
                })
            generator.shuffle(rows)
            available = generator.randrange(0, 3000)
            with self.subTest(case=case, available=available):
                self.assertEqual(
                    P7.lazy_reference_select(rows, available),
                    P7.brute_force_reference_select(rows, available),
                )

    def test_lazy_reference_tier2_exact_fit_first_nonfit_and_signed_zero(self) -> None:
        split = 0x3DA0000000000000
        tier1 = {"point_abs_ticks": 2, "abs_bits": split - 1, "mask": 9}
        tier2_exact = {
            "point_abs_ticks": 3, "abs_bits": split, "mask": 7,
        }
        tier2_nonfit = {
            "point_abs_ticks": 4, "abs_bits": split + 1, "mask": 5,
        }
        tier2_later = {
            "point_abs_ticks": 5, "abs_bits": split + 2, "mask": 3,
        }
        rows = [tier2_later, tier2_nonfit, tier1, tier2_exact]
        self.assertEqual(
            P7.lazy_reference_select(rows, 5), [tier1, tier2_exact],
        )
        self.assertEqual(
            P7.lazy_reference_select(rows, 6), [tier1, tier2_exact],
        )
        self.assertEqual(
            P7.lazy_reference_select(rows, 6),
            P7.brute_force_reference_select(rows, 6),
        )

        positive = {
            "point_abs_ticks": 1, "abs_bits": 1, "mask": 4,
            "coefficient_bits": 1,
        }
        signed_zeros = [
            {
                "point_abs_ticks": 0, "abs_bits": 0, "mask": 8,
                "coefficient_bits": 0x8000000000000000,
            },
            {
                "point_abs_ticks": 0, "abs_bits": 0, "mask": 2,
                "coefficient_bits": 0,
            },
            positive,
        ]
        permutations = (
            signed_zeros,
            list(reversed(signed_zeros)),
            [signed_zeros[1], signed_zeros[2], signed_zeros[0]],
        )
        for rows in permutations:
            selected = P7.lazy_reference_select(rows, 0)
            self.assertEqual([row["mask"] for row in selected], [2, 8])
            self.assertEqual(
                {row["coefficient_bits"] for row in selected},
                {0, 0x8000000000000000},
            )
            self.assertEqual(
                selected, P7.brute_force_reference_select(rows, 0),
            )

    def test_step3_local_and_three_step_schedule_boundaries_are_exact(self) -> None:
        rule = self.fixture["step3_adaptive_rule"]
        grid = 1 << 128
        maximum_local = (grid - 1) // 400000
        self.assertEqual(
            str(maximum_local), rule["maximum_strictly_legal_local_ticks"],
        )
        self.assertEqual(maximum_local // 768, (1 * maximum_local) // 768)
        self.assertEqual((768 * maximum_local) // 768, maximum_local)
        self.assertLess(maximum_local * 400000, grid)
        self.assertGreaterEqual((maximum_local + 1) * 400000, grid)

        maximum_cumulative = (3 * grid - 1) // 400000
        self.assertEqual(
            str(maximum_cumulative),
            rule["future_S0_maximum_strictly_legal_cumulative_ticks"],
        )
        self.assertLess(maximum_cumulative * 400000, 3 * grid)
        self.assertGreaterEqual(
            (maximum_cumulative + 1) * 400000, 3 * grid,
        )

    def test_step3_global_boundary_mapping_is_1536_through_2303(self) -> None:
        rule = self.fixture["step3_adaptive_rule"]
        self.assertEqual(rule["local_raw_boundary_indices"], "0_through_767")
        self.assertEqual(rule["global_raw_boundary_indices"], "1536_through_2303")
        self.assertEqual(
            rule["global_raw_boundary_index_formula"],
            "1536_plus_local_raw_boundary_index",
        )
        self.assertTrue(
            rule["prefix_target_uses_local_q_not_the_global_boundary_index"]
        )
        mapping = [(local, 1536 + local, local + 1) for local in range(768)]
        self.assertEqual(mapping[0], (0, 1536, 1))
        self.assertEqual(mapping[-1], (767, 2303, 768))

    def test_source_pins_and_thirteen_byte_identical_staged_paths(self) -> None:
        pins = P7._source_pins(self.policy)
        self.assertEqual(set(pins), set((*P7.STAGED_PATHS, Path(P7.__file__).name)))
        self.assertEqual(len(P7.STAGED_PATHS), 13)
        manifest = self._staging_manifest()
        self.assertEqual(len(manifest), 13)
        for row in manifest:
            self.assertTrue(row["byte_identical_to_repository"])
            self.assertEqual(row["repository_sha256"], row["staged_sha256"])
        P7._validate_staging_manifest(
            manifest, self.policy, P7.canonical_sha256(manifest),
        )
        bad = copy.deepcopy(manifest)
        bad[0]["byte_identical_to_repository"] = False
        with self.assertRaises(P7.ProbeError):
            P7._validate_staging_manifest(
                bad, self.policy, P7.canonical_sha256(bad),
            )

    def test_frozen_P6_runner_matches_the_precommit_blob(self) -> None:
        precommit = "e9c3b2ee9c095d0be6f834fa5f49ede9ec035e75"
        staged = P7.P6_RUNNER
        relative = f"docs/research/fermion-frontier/{staged}"
        frozen = subprocess.check_output(
            ["git", "show", f"{precommit}:{relative}"], cwd=BASE,
        )
        self.assertEqual((BASE / staged).read_bytes(), frozen)

    def test_complete_public_witness_is_valid(self) -> None:
        witness = self._complete_witness()
        self.assertIs(P7.validate_public_witness(witness), witness)

    def test_prefix_mismatch_has_a_dedicated_nonexecuting_terminal_state(self) -> None:
        witness = self._complete_witness()
        witness["step2"]["exact_zero_dropped_term_count"] += 1
        witness["P6_prefix_resource_projection_conformed"] = False
        witness["step3_started"] = False
        witness["step3"] = None
        witness["step2_to_step3_link"] = None
        witness["step3_selection_resources"] = None
        P7.validate_public_witness(witness)
        admission = P7._fixed_formal_admission(
            self._observation(witness), self.policy,
        )
        self.assertEqual(
            admission["status"],
            "NOT_ESTABLISHED_INVALID_PREFIX_RESOURCE_CONFORMANCE",
        )
        bad = copy.deepcopy(witness)
        bad["step3_started"] = True
        with self.assertRaises(P7.ProbeError):
            P7.validate_public_witness(bad)

    def test_step1_cap_forbids_all_later_work(self) -> None:
        witness = self._complete_witness()
        self._cap_summary(witness["step1"], "step1")
        for key in (
            "step2", "step3", "step1_to_step2_link",
            "step2_to_step3_link", "step2_selection_resources",
            "step3_selection_resources",
        ):
            witness[key] = None
        witness["P6_prefix_resource_projection_conformed"] = False
        witness["step3_started"] = False
        P7.validate_public_witness(witness)
        self.assertEqual(
            P7._fixed_formal_admission(
                self._observation(witness), self.policy,
            )["status"],
            "NOT_ESTABLISHED_DETERMINISTIC_STEP1_CAP",
        )
        bad = copy.deepcopy(witness)
        bad["step3"] = copy.deepcopy(
            self.fixture["expected_P6_prefix_resource_projection"]["step2"]
        )
        with self.assertRaises(P7.ProbeError):
            P7.validate_public_witness(bad)

    def test_step2_cap_forbids_step3(self) -> None:
        witness = self._complete_witness()
        self._cap_summary(witness["step2"], "step2")
        witness["step3"] = None
        witness["step2_to_step3_link"] = None
        witness["step3_selection_resources"] = None
        witness["P6_prefix_resource_projection_conformed"] = False
        witness["step3_started"] = False
        P7.validate_public_witness(witness)
        self.assertEqual(
            P7._fixed_formal_admission(
                self._observation(witness), self.policy,
            )["status"],
            "NOT_ESTABLISHED_DETERMINISTIC_STEP2_CAP",
        )

    def test_step3_cap_partial_progress_is_resource_only(self) -> None:
        witness = self._complete_witness()
        self._cap_summary(witness["step3"], "step3")
        P7.validate_public_witness(witness)
        self.assertEqual(
            P7._fixed_formal_admission(
                self._observation(witness), self.policy,
            )["status"],
            "NOT_ESTABLISHED_DETERMINISTIC_STEP3_CAP",
        )
        bad = copy.deepcopy(witness)
        bad["step3"]["cap_event"]["attempted"] = bad[
            "step3"
        ]["cap_event"]["limit"]
        with self.assertRaises(P7.ProbeError):
            P7.validate_public_witness(bad)
        bad = copy.deepcopy(witness)
        del bad["step3"]["cap_event"]["context"]["mapped_step_index"]
        with self.assertRaises(P7.ProbeError):
            P7.validate_public_witness(bad)

    def test_prefix_and_link_mutations_fail_closed(self) -> None:
        for mutate in (
            lambda value: value["candidate"].__setitem__("candidate_id", "other"),
            lambda value: value["step1_to_step2_link"].__setitem__(
                "next_step_input_term_count", 0,
            ),
            lambda value: value["step2_to_step3_link"].__setitem__(
                "checkpoint_or_serialized_state_used", True,
            ),
            lambda value: value["step2_selection_resources"].__setitem__(
                "total_selection_work_units", 0,
            ),
            lambda value: value.__setitem__(
                "fixture_canonical_sha256", "0" * 64,
            ),
        ):
            bad = self._complete_witness()
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(P7.ProbeError):
                P7.validate_public_witness(bad)

    def test_scientific_public_vocabulary_is_rejected(self) -> None:
        for key, value in (
            ("operator_error_ticks", "1"),
            ("allocation_pass", True),
            ("term_stream_sha256", "0" * 64),
            ("mask_hex", "00"),
        ):
            bad = self._complete_witness()
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(P7.ProbeError):
                P7.validate_public_witness(bad)

    def test_observation_stdout_and_host_truth_are_fail_closed(self) -> None:
        row = self._observation()
        P7._validate_observation(row, self.fixture["host_supervisor_caps"])
        bad = copy.deepcopy(row)
        bad["stdout_sha256"] = "0" * 64
        with self.assertRaises(P7.ProbeError):
            P7._validate_observation(bad, self.fixture["host_supervisor_caps"])
        indeterminate = self._indeterminate_observation()
        P7._validate_observation(
            indeterminate, self.fixture["host_supervisor_caps"],
        )
        bad = copy.deepcopy(indeterminate)
        bad["resource_witness"] = self._complete_witness()
        with self.assertRaises(P7.ProbeError):
            P7._validate_observation(bad, self.fixture["host_supervisor_caps"])

    def test_exit_66_is_invalid_without_report_or_stderr_disclosure(self) -> None:
        host = self.fixture["host_supervisor_caps"]
        classify = P7._candidate_process_status
        self.assertEqual(P7.INVALID_D0_PROBE_EXIT_CODE, 66)
        self.assertEqual(P7.JULIA_RUNTIME_FAILURE_EXIT_CODE, 70)
        self.assertEqual(
            classify(
                returncode=66, timed_out=False, stdout_bytes=0,
                stderr_bytes=0, host=host,
            ),
            "INVALID_D0_PROBE",
        )
        for returncode in (70, -9, 1, 127):
            with self.subTest(returncode=returncode):
                self.assertEqual(
                    classify(
                        returncode=returncode, timed_out=False,
                        stdout_bytes=0, stderr_bytes=0, host=host,
                    ),
                    "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
                )
        self.assertEqual(
            classify(
                returncode=66, timed_out=True, stdout_bytes=0,
                stderr_bytes=0, host=host,
            ),
            "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
        )

        secret_stderr = b"private scientific stderr must never be disclosed"

        def run_fake(returncode: int):
            process = SimpleNamespace(returncode=returncode)
            process.communicate = mock.Mock(return_value=(b"", secret_stderr))
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                scratch = root / "scratch"
                scratch.mkdir()
                with mock.patch.object(P7.subprocess, "Popen", return_value=process):
                    return P7._run_candidate(
                        root / "staging", root / "julia", root / "depot",
                        host, scratch,
                    )

        self.assertFalse((BASE / P7.REPORT_NAME).exists())
        with self.assertRaisesRegex(P7.ProbeError, "^INVALID_D0_PROBE") as caught:
            run_fake(66)
        self.assertNotIn(secret_stderr.decode(), str(caught.exception))
        self.assertFalse((BASE / P7.REPORT_NAME).exists())

        indeterminate = run_fake(70)
        self.assertEqual(
            indeterminate["status"],
            "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
        )
        self.assertIsNone(indeterminate["resource_witness"])
        self.assertNotIn(
            secret_stderr.decode(),
            P7.canonical_bytes(indeterminate).decode("utf-8"),
        )

    def test_fixed_admission_never_derives_from_observation(self) -> None:
        admission = P7._fixed_formal_admission(
            self._observation(), self.policy,
        )
        self.assertEqual(
            admission["status"], "ESTABLISHED_FOR_FUTURE_S0_PRECOMMIT",
        )
        self.assertFalse(admission["derived_from_observation"])
        self.assertTrue(admission["same_as_D0_admission"])
        self.assertEqual(
            admission["formal_host_caps"], self.fixture["host_supervisor_caps"],
        )
        failed = P7._fixed_formal_admission(
            self._indeterminate_observation(), self.policy,
        )
        self.assertEqual(
            failed["status"],
            "NOT_ESTABLISHED_INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
        )

    def test_report_schema_manifest_and_admission_links(self) -> None:
        report = self._report()
        with mock.patch.object(P7, "_validate_preprobe_commit_identity"):
            self.assertIs(P7.validate_report(report), report)
        for mutate in (
            lambda value: value["observations"].append(
                copy.deepcopy(value["observations"][0])
            ),
            lambda value: value["fixed_formal_admission"].__setitem__(
                "derived_from_observation", True,
            ),
            lambda value: value["staging_manifest"][0].__setitem__(
                "staged_sha256", "0" * 64,
            ),
            lambda value: value.__setitem__(
                "formal_candidate_was_frozen_before_probe", "other",
            ),
        ):
            bad = self._report()
            mutate(bad)
            with self.subTest(mutate=mutate), mock.patch.object(
                P7, "_validate_preprobe_commit_identity",
            ), self.assertRaises(P7.ProbeError):
                P7.validate_report(bad)

    def test_indeterminate_report_is_canonical_resource_only(self) -> None:
        report = self._report(self._indeterminate_observation())
        with mock.patch.object(P7, "_validate_preprobe_commit_identity"):
            P7.validate_report(report)
        self.assertEqual(
            report["fixed_formal_admission"]["status"],
            "NOT_ESTABLISHED_INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
        )
        self.assertIsNone(report["observations"][0]["resource_witness"])

    def test_preprobe_commit_identity_and_five_path_allowlist(self) -> None:
        self.assertEqual(len(P7.PREPROBE_CHANGED_PATHS), 5)
        self.assertIn(
            "docs/research/fermion-frontier/"
            "test_majorana_certificate_p7_design_probe.py",
            P7.PREPROBE_CHANGED_PATHS,
        )
        for value in ("", "A" * 40, "a" * 39, "g" * 40):
            with self.subTest(value=value), self.assertRaises(P7.ProbeError):
                P7._validate_preprobe_commit_identity(value)

    def test_policy_and_fixture_mutations_fail_closed(self) -> None:
        for target, mutate in (
            ("policy", lambda value: value.__setitem__("policy_id", "other")),
            ("policy", lambda value: value["candidate_design"].__setitem__(
                "probe_mode_order", [],
            )),
            ("policy", lambda value: value["D0_host_supervisor_caps"].__setitem__(
                "MemoryMax_bytes", 1 << 32,
            )),
            ("policy", lambda value: value[
                "fixed_formal_admission_schema"
            ].__setitem__(
                "step1_cap_status", "NOT_ESTABLISHED_DETERMINISTIC_POLICY_CAP",
            )),
            ("policy", lambda value: value[
                "staged_source_custody"
            ]["staged_path_order"].reverse()),
            ("fixture", lambda value: value["candidate_design"].__setitem__(
                "formal_candidate_count", 2,
            )),
            ("fixture", lambda value: value["step3_adaptive_rule"].__setitem__(
                "mapped_step_index", 2,
            )),
            ("fixture", lambda value: value["host_supervisor_caps"].__setitem__(
                "RuntimeMaxSec", "3600s",
            )),
            ("fixture", lambda value: value["step3_adaptive_rule"].__setitem__(
                "global_raw_boundary_indices", "0_through_767",
            )),
            ("fixture", lambda value: value[
                "exact_lazy_implementation"
            ].__setitem__("split_threshold_Float64_bits_hex", "3da0000000000001")),
        ):
            value = copy.deepcopy(
                self.policy if target == "policy" else self.fixture
            )
            mutate(value)
            with self.subTest(target=target, mutate=mutate), self.assertRaises(
                P7.ProbeError,
            ):
                if target == "policy":
                    P7.validate_policy(value, require_report_absent=True)
                else:
                    P7._validate_fixture(value)

    def test_source_pin_mutation_fails_closed(self) -> None:
        bad = copy.deepcopy(self.policy)
        bad["source_files"][0]["sha256"] = "0" * 64
        with self.assertRaises(P7.ProbeError):
            P7.validate_policy(bad, require_report_absent=True)

    def test_policy_governance_semantic_pin_fails_closed(self) -> None:
        semantic_policy = {
            key: value for key, value in self.policy.items()
            if key != "source_files"
        }
        self.assertEqual(
            P7.canonical_sha256(semantic_policy), P7.POLICY_SEMANTIC_SHA256,
        )
        mutations = (
            lambda value: value["stop_rules"].__setitem__(
                "custody_schema_source_runtime_or_forbidden_output_failure_"
                "returns_INVALID_D0_PROBE", False,
            ),
            lambda value: value["stop_rules"].__setitem__(
                "host_timeout_OOM_cgroup_supervisor_environment_sandbox_or_"
                "generation_failure_returns_INDETERMINATE", False,
            ),
            lambda value: value["D0_observation_contract"][
                "forbidden_outputs"
            ].pop(),
            lambda value: value["D0_observation_contract"].__setitem__(
                "operator_must_not_inspect_suppressed_scientific_fields",
                False,
            ),
            lambda value: value["D0_observation_contract"].__setitem__(
                "D0_raw_stdout_checkpoint_state_or_private_scientific_"
                "sidecar_must_not_be_persisted", False,
            ),
            lambda value: value[
                "state_custody_and_runner_visibility"
            ].__setitem__(
                "formal_finalizer_scientific_values_remain_transient_private",
                False,
            ),
            lambda value: value["authority_exclusions"].remove(
                "D0_complete_formal_finalizer_execution_and_its_public_"
                "resource_counts_have_no_scientific_authority"
            ),
        )
        for mutate in mutations:
            bad = copy.deepcopy(self.policy)
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(P7.ProbeError):
                P7.validate_policy(bad, require_report_absent=True)

    def test_runtime_lock_bytes_and_source_closures_are_exact(self) -> None:
        runtime = self.fixture["runtime_custody"]
        P7._validate_runtime_lock_bytes(runtime)
        lock_path = BASE / P7.RUNTIME_LOCK_NAME
        lock = P7.loads_json(lock_path.read_bytes(), str(lock_path))
        packages = lock["direct_and_semantic_upstream_packages"]
        self.assertEqual(
            packages["MajoranaPropagation"]["installed_source_closure"],
            P7.MAJORANA_SOURCE_TREE_CLOSURE,
        )
        self.assertEqual(
            packages["PauliPropagation"]["installed_source_closure"],
            P7.PAULI_SOURCE_TREE_CLOSURE,
        )
        self.assertTrue(runtime["runtime_lock_bytes_verified_by_preprobe_checker"])

        bad_runtime = copy.deepcopy(runtime)
        bad_runtime["MajoranaPropagation_source_tree_closure"][
            "closure_sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(P7.ProbeError, "MajoranaPropagation"):
            P7._validate_runtime_custody_shape(bad_runtime, "mutated")

        tampered_lock = copy.deepcopy(lock)
        tampered_lock["direct_and_semantic_upstream_packages"][
            "PauliPropagation"
        ]["installed_source_closure"]["closure_sha256"] = "0" * 64
        tampered_bytes = P7.canonical_bytes(tampered_lock) + b"\n"
        original_read_bytes = Path.read_bytes

        def substituted_read_bytes(path: Path) -> bytes:
            if path == lock_path:
                return tampered_bytes
            return original_read_bytes(path)

        with mock.patch.object(Path, "read_bytes", new=substituted_read_bytes):
            with self.assertRaisesRegex(P7.ProbeError, "bytes SHA-256 mismatch"):
                P7._validate_runtime_lock_bytes(runtime)

        with mock.patch.object(P7, "_validate_runtime_lock_bytes") as validator:
            P7.validate_policy(
                copy.deepcopy(self.policy), require_report_absent=True,
            )
            validator.assert_called_once_with(runtime)

    def test_transient_finalizer_science_is_not_publicly_disclosed(self) -> None:
        driver = (BASE / P7.PROBE_DRIVER).read_text(encoding="utf-8")
        p3_runner = (
            BASE / "majorana_certificate_p3/majorana_p3_runner.jl"
        ).read_text(encoding="utf-8")
        self.assertIn("finalize_p3_state!", driver)
        for token in (
            "term_stream_sha256",
            "checkerboard_Neel_exact_dyadic_center",
            "declared_expectation_interval",
            "error_ticks = total_ticks(execution.ticks)",
        ):
            self.assertIn(token, p3_runner)

        summary_start = driver.index("function p7_resource_summary")
        summary_end = driver.index("function p7_execute_adaptive_step")
        public_summary_source = driver[summary_start:summary_end]
        self.assertIn("final_state.retained_term_count", public_summary_source)
        for forbidden in (
            "term_stream_sha256", "checkerboard_Neel", "error_ticks",
            "declared_expectation_interval",
        ):
            self.assertNotIn(forbidden, public_summary_source)

        public_bytes = P7.canonical_bytes(self._complete_witness()).lower()
        for forbidden in (
            b"term_stream_sha256", b"checkerboard_neel",
            b"operator_error_ticks", b"declared_expectation_interval",
        ):
            self.assertNotIn(forbidden, public_bytes)
        with self.assertRaises(P7.ProbeError):
            P7._reject_public_scientific_vocabulary({
                "nested": {"checkerboard_Neel_center": "suppressed"},
            })
        observation = self.policy["D0_observation_contract"]
        self.assertEqual(
            observation["formal_finalizer_privacy"], P7.FINALIZER_PRIVACY,
        )
        self.assertEqual(
            self.fixture["scope"]["D0_formal_finalizer_privacy"],
            P7.FINALIZER_PRIVACY,
        )
        self.assertEqual(
            self.fixture["scope"]["checkerboard_Neel_expectation"],
            P7.CHECKERBOARD_NEEL_SCOPE,
        )
        self.assertTrue(observation[
            "operator_must_not_inspect_suppressed_scientific_fields"
        ])
        self.assertTrue(observation[
            "D0_raw_stdout_checkpoint_state_or_private_scientific_sidecar_"
            "must_not_be_persisted"
        ])

    def test_driver_maps_each_step_caps_and_resets_selection_state(self) -> None:
        driver = (BASE / P7.PROBE_DRIVER).read_text(encoding="utf-8")
        self.assertRegex(
            driver,
            r"function\s+p7_step3_engine_caps\(caps(?:\s*::[^)]*)?\)",
        )
        step3_cap_keys = sorted(
            key for key in self.fixture["deterministic_step3_probe_caps"]
            if key.startswith("maximum_step3_")
        )
        self.assertEqual(len(step3_cap_keys), 14)
        for step3_key in step3_cap_keys:
            step2_key = step3_key.replace("maximum_step3_", "maximum_step2_", 1)
            pattern = (
                re.escape(f'"{step2_key}"')
                + r"\s*=>\s*caps\["
                + re.escape(f'"{step3_key}"')
                + r"\]"
            )
            with self.subTest(step3_key=step3_key):
                self.assertRegex(driver, pattern)

        for pattern in (
            r'step2_caps\s*=\s*p6_fixture\["deterministic_resource_caps"\]',
            r'step2_selection_caps\s*=\s*'
            r'p6_fixture\["deterministic_selection_caps"\]',
            r'step3_caps\s*=\s*p7_step3_engine_caps\(\s*'
            r'p7_fixture\["deterministic_step3_probe_caps"\]\s*,?\s*\)',
            r'step3_selection_caps\s*=\s*'
            r'p7_fixture\["deterministic_step3_selection_probe_caps"\]',
            r"function\s+p7_execute_adaptive_step\(",
            r"P4_ACTIVE_STEP2_CAPS\[\]\s*=\s*engine_caps",
        ):
            self.assertRegex(driver, pattern)

        ordered_patterns = (
            r"P4_ACTIVE_STEP2_CAPS\[\]\s*=\s*engine_caps",
            r"p6_reset_selection_state!\(\s*selection_caps\s*\)",
            r"selection_resources\s*=\s*p6_public_selection_resources\(\)",
            r"finally",
            r"p6_clear_selection_state!\(\)",
            r"P4_ACTIVE_STEP2_CAPS\[\]\s*=\s*nothing",
        )
        offset = 0
        for pattern in ordered_patterns:
            match = re.search(pattern, driver[offset:])
            self.assertIsNotNone(match, pattern)
            assert match is not None
            offset += match.end()

        call_starts = [
            match.start() for match in re.finditer(
                r"\bp7_execute_adaptive_step\(", driver,
            )
        ]
        self.assertEqual(len(call_starts), 3)
        step2_call = driver[call_starts[1]:call_starts[2]]
        step3_call = driver[call_starts[2]:call_starts[2] + 2000]
        self.assertIn("step2_caps", step2_call)
        self.assertIn("step2_selection_caps", step2_call)
        self.assertIn("step3_caps", step3_call)
        self.assertIn("step3_selection_caps", step3_call)

    def test_driver_and_orchestrator_have_no_result_input_path(self) -> None:
        driver = (BASE / P7.PROBE_DRIVER).read_text(encoding="utf-8")
        orchestrator = (BASE / Path(P7.__file__).name).read_text(
            encoding="utf-8",
        )
        parent_result_inputs = (
            "majorana_certificate_p6_design_probe_report.json",
            "majorana_certificate_p6_precommit_contract.json",
            "majorana_certificate_p6_contract.json",
            "majorana_certificate_p6_certificate.json",
            "test_majorana_certificate_p6_design_probe_result.py",
            "test_majorana_certificate_p6_result.py",
        )
        future_P7_result_inputs = (
            "majorana_certificate_p7_design_probe_report.json",
            "majorana_certificate_p7_precommit_contract.json",
            "majorana_certificate_p7_contract.json",
            "majorana_certificate_p7_certificate.json",
            "test_majorana_certificate_p7_result.py",
        )
        for token in (*parent_result_inputs, *future_P7_result_inputs):
            self.assertNotIn(token, driver)
        for token in parent_result_inputs:
            self.assertNotIn(token, orchestrator)


if __name__ == "__main__":
    unittest.main()
