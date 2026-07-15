#!/usr/bin/env python3
"""Regression tests for the non-authoritative Majorana P6 D0 probe."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re
import subprocess
import tempfile
import unittest
from unittest import mock


BASE = Path(__file__).resolve().parent


def _load_probe():
    path = BASE / "majorana_certificate_p6_design_probe.py"
    spec = importlib.util.spec_from_file_location("majorana_p6_d0_probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P6 = _load_probe()


class MajoranaP6DesignProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = P6.load_json(BASE / P6.POLICY_NAME)
        cls.fixture = P6.load_json(BASE / P6.FIXTURE_NAME)

    def _control_witness(self):
        projection = copy.deepcopy(
            self.policy["expected_P5_K37_control_resource_projection"]
        )
        return {
            "schema_version": 1,
            "probe_type": P6.PROBE_TYPE,
            "scientific_authority": "NONE",
            "certificate_eligible": False,
            "result_contract_eligible": False,
            "resource_observations_only": True,
            "candidate": {
                "candidate_id": P6.CANDIDATE_IDS[P6.CONTROL_MODE],
                "probe_mode": P6.CONTROL_MODE,
                "identity": P6.CONTROL_MODE,
                "control_candidate": True,
                "formal_candidate": False,
                "step1_path": "fixed_P3_2^-34",
                "step2_path": "fixed_P5_K37_resource_control",
            },
            "step1": projection["step1"],
            "step2": projection["step2"],
            "step_link": projection["step_link"],
            "selection_resources": projection["selection_resources"],
            "explicit_exclusions": [
                "scientific_local_or_cumulative_error_values",
                "allocation_assessment_or_candidate_selection",
                "term_or_drop_stream_commitments",
                "checkerboard_observable_center_or_interval",
                "adaptive_execution_branch_as_scientific_evidence",
                "scientific_witness_result_contract_certificate_or_READY_authority",
            ],
        }

    def _adaptive_witness(self):
        witness = self._control_witness()
        witness["candidate"] = {
            "candidate_id": P6.CANDIDATE_IDS[P6.ADAPTIVE_MODE],
            "probe_mode": P6.ADAPTIVE_MODE,
            "identity": P6.ADAPTIVE_MODE,
            "control_candidate": False,
            "formal_candidate": True,
            "step1_path": "fixed_P3_2^-34",
            "step2_path": "full_domain_E768_MAX_LAZY37_V1",
        }
        witness["selection_resources"] = {
            "total_ranking_scan_term_visits": 10,
            "total_sort_work_items": 20,
            "total_tick_evaluations": 30,
            "total_selected_membership_insertions": 40,
            "peak_ranking_buffer_terms": 20,
            "total_selection_work_units": 100,
            "completed_selection_boundary_count": 768,
        }
        return witness

    def _completed_observation(self, mode, witness):
        stdout = P6.canonical_bytes(witness) + b"\n"
        stderr = b"synthetic-time-diagnostics"
        return {
            "probe_mode": mode,
            "candidate_id": P6.CANDIDATE_IDS[mode],
            "process_returncode": 0,
            "outer_timeout_triggered": False,
            "stdout_bytes": len(stdout),
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_bytes": len(stderr),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "outer_monotonic_elapsed_ns": 1_000_000_000,
            "time_diagnostics": {
                "user_time_seconds": "1.00",
                "system_time_seconds": "0.01",
                "elapsed_wall_clock": "0:01.01",
                "maximum_resident_set_size_KiB": 100000,
                "minor_page_faults": 10,
                "major_page_faults": 0,
            },
            "host_failure_has_no_mathematical_authority": True,
            "status": "COMPLETED_RESOURCE_OBSERVATION",
            "resource_witness": witness,
            "resource_witness_sha256": P6.canonical_sha256(witness),
        }

    def _base_report(self):
        observations = [
            self._completed_observation(P6.CONTROL_MODE, self._control_witness()),
            self._completed_observation(P6.ADAPTIVE_MODE, self._adaptive_witness()),
        ]
        with tempfile.TemporaryDirectory(prefix="majorana-p6-report-test-") as root:
            manifest = P6.stage_probe_tree(Path(root), self.policy)
        return {
            "schema_version": 1,
            "report_type": P6.REPORT_TYPE,
            "policy_id": P6.POLICY_ID,
            "policy_sha256": P6.file_sha256(BASE / P6.POLICY_NAME),
            "fixture_id": P6.FIXTURE_ID,
            "fixture_sha256": P6.file_sha256(BASE / P6.FIXTURE_NAME),
            "fixture_canonical_sha256": P6.canonical_sha256(self.fixture),
            "preprobe_commit_sha": "a" * 40,
            "scientific_authority": "NONE",
            "certificate_eligible": False,
            "formal_candidate_was_frozen_before_probe":
                P6.CANDIDATE_IDS[P6.ADAPTIVE_MODE],
            "control_is_not_selectable": True,
            "staging_manifest": manifest,
            "staging_manifest_sha256": P6.canonical_sha256(manifest),
            "host_caps": self.policy["D0_host_supervisor_caps"],
            "observations": observations,
            "formal_resource_envelope":
                P6._derive_formal_resource_envelope(observations, self.policy),
            "authority_exclusions": self.policy["authority_exclusions"],
        }

    def _assert_report_rejected(self, report):
        with mock.patch.object(P6, "_validate_preprobe_commit_identity"):
            with self.assertRaises(P6.ProbeError):
                P6.validate_report(report)

    def _refresh_observation_custody(self, report, index=1):
        row = report["observations"][index]
        witness = row["resource_witness"]
        stdout = P6.canonical_bytes(witness) + b"\n"
        row["stdout_bytes"] = len(stdout)
        row["stdout_sha256"] = hashlib.sha256(stdout).hexdigest()
        row["resource_witness_sha256"] = P6.canonical_sha256(witness)
        report["formal_resource_envelope"] = P6._derive_formal_resource_envelope(
            report["observations"], self.policy,
        )

    def test_policy_fixture_and_historical_report_absence_are_valid(self) -> None:
        validated = P6.validate_policy(
            self.policy, require_report_absent=False,
        )
        self.assertEqual(validated["policy_id"], P6.POLICY_ID)
        self.assertEqual(self.fixture["fixture_id"], P6.FIXTURE_ID)
        for relative in P6.RESULT_ARTIFACTS:
            artifact = (
                "2483450e9ae93402a5315dae21b142d08742e783:"
                "docs/research/fermion-frontier/" + relative
            )
            process = subprocess.run(
                ["git", "cat-file", "-e", artifact], cwd=BASE,
                check=False, capture_output=True,
            )
            with self.subTest(relative=relative):
                self.assertNotEqual(process.returncode, 0)

    def test_single_candidate_and_control_are_frozen(self) -> None:
        design = self.policy["candidate_design"]
        self.assertEqual(design["probe_mode_order"], list(P6.MODE_ORDER))
        self.assertTrue(design["exactly_one_formal_candidate"])
        self.assertTrue(design["control_can_never_enter_a_formal_selector"])
        self.assertEqual(
            design["formal_candidate_order_is_frozen_before_any_D0_output"],
            ["E768-MAX-LAZY37-V1"],
        )
        self.assertTrue(
            self.fixture["candidate_design"]
            ["formal_threshold_argument_cannot_create_a_hard_scientific_eligibility_gate"]
        )

    def test_prefix_integer_schedule_has_exact_endpoints(self) -> None:
        grid = 1 << 128
        local = (grid - 1) // 400000
        self.assertEqual(local, 850705917302346158658436518579420)
        target = lambda raw: ((raw + 1) * local) // 768
        self.assertEqual(target(0), 1107689996487429894086505883566)
        self.assertEqual(target(767), local)
        self.assertTrue(all(target(index) < target(index + 1) for index in range(767)))
        rule = self.fixture["full_domain_adaptive_rule"]
        self.assertEqual(rule["raw_boundary_indices"], "0_through_767")
        self.assertIn("raw_boundary_index+1", rule["prefix_target_formula"])
        self.assertIn("cumulative_product_ticks", rule["available_ticks_formula"])

    def test_local_pass_would_imply_the_fixed_cumulative_pass(self) -> None:
        grid = 1 << 128
        local = (grid - 1) // 400000
        cumulative = (grid - 1) // 200000
        inherited_e1 = 296986546391593866116533250955376
        self.assertEqual(
            cumulative - inherited_e1 - local,
            553719370910752292541903267624045,
        )
        self.assertGreater(cumulative, inherited_e1 + local)

    def test_hindsight_firewall_excludes_P5_scientific_values(self) -> None:
        firewall = self.policy["hindsight_firewall"]
        self.assertTrue(firewall["P5_informed"])
        self.assertTrue(firewall["P6_result_unpinned"])
        joined = json.dumps(
            firewall["forbidden_P5_scientific_design_inputs"],
            sort_keys=True,
        ).lower()
        for token in ("exact", "slack", "digest", "neel", "budget"):
            self.assertIn(token, joined)
        forbidden_decimal_signatures = {
            (34, "be9c19f665df3671fda3bed3d23aaaf247c3b3a39d0963cd2a02ce201b493b45"),
            (33, "c1023e44cbc0bab2216090015ee171d76b92c83c720ca7c15da0b7f8ad7d3557"),
        }
        scanned = set()
        prefix = "docs/research/fermion-frontier/"
        for repository_path in P6.PREPROBE_CHANGED_PATHS:
            relative = repository_path.removeprefix(prefix)
            body = (BASE / relative).read_bytes()
            for match in re.finditer(rb"[0-9]+", body):
                token = match.group()
                scanned.add((len(token), hashlib.sha256(token).hexdigest()))
        self.assertTrue(forbidden_decimal_signatures.isdisjoint(scanned))

    def test_source_pins_are_exact_and_complete(self) -> None:
        pins = P6._source_pins(self.policy)
        self.assertEqual(
            set(pins), set((*P6.STAGED_PATHS, Path(P6.__file__).name)),
        )
        for relative, row in pins.items():
            with self.subTest(relative=relative):
                path = BASE / relative
                self.assertEqual(path.stat().st_size, row["size_bytes"])
                self.assertEqual(P6.file_sha256(path), row["sha256"])

    def test_staging_changes_only_the_P5_candidate_copy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="majorana-p6-d0-test-") as temporary:
            rows = P6.stage_probe_tree(Path(temporary), self.policy)
            self.assertEqual(
                tuple(row["relative_path"] for row in rows), P6.STAGED_PATHS,
            )
            changed = [
                row["relative_path"] for row in rows
                if row["candidate_algorithm_transform_applied"]
            ]
            self.assertEqual(changed, [P6.P5_RUNNER])
            for row in rows:
                equal = row["repository_sha256"] == row["staged_sha256"]
                self.assertEqual(equal, row["relative_path"] != P6.P5_RUNNER)

    def test_P5_transform_is_unique_fail_closed_and_nonmutating(self) -> None:
        source = (BASE / P6.P5_RUNNER).read_bytes()
        transformed = P6._instrument_p5(source, self.policy)
        for replacement in (
            P6.PREPARE_REPLACEMENT,
            P6.CALLBACK_REPLACEMENT,
            P6.VALIDATION_REPLACEMENT,
        ):
            self.assertIn(replacement.encode(), transformed)
        self.assertEqual((BASE / P6.P5_RUNNER).read_bytes(), source)
        with self.assertRaisesRegex(
            P6.ProbeError, "already transformed|occurrence count",
        ):
            P6._instrument_p5(transformed, self.policy)
        with self.assertRaisesRegex(P6.ProbeError, "occurrence count"):
            P6._instrument_p5(
                source.replace(P6.CALLBACK_NEEDLE.encode(), b"missing"),
                self.policy,
            )

    def test_caps_match_fixture_and_selection_work_is_frozen(self) -> None:
        caps = self.policy["D0_deterministic_resource_caps"]
        for section in (
            "deterministic_step2_probe_caps",
            "deterministic_selection_probe_caps",
        ):
            for key, value in self.fixture[section].items():
                self.assertEqual(caps[key], value)
        self.assertEqual(
            caps["total_selection_work_units_formula"],
            "ranking_scan_term_visits_plus_sort_input_items_plus_"
            "tick_evaluations_plus_selected_membership_insertions",
        )
        accounting = self.fixture["selection_resource_accounting"]
        self.assertTrue(
            accounting[
                "each_component_and_the_combined_total_are_checked_before_"
                "the_corresponding_operation"
            ]
        )
        observation_contract = self.policy["D0_observation_contract"]
        self.assertEqual(
            observation_contract["public_cap_event_name_allowlist"],
            sorted(P6.CAP_EVENT_NAMES),
        )
        self.assertEqual(
            observation_contract["public_resource_identities"],
            list(P6.PUBLIC_RESOURCE_IDENTITIES),
        )

    def test_lazy_reference_matches_full_sort_randomized(self) -> None:
        rng = random.Random(0xE76837)
        threshold = 0x3DA0000000000000
        for _ in range(3000):
            rows = []
            for mask in range(rng.randrange(0, 60)):
                bits = rng.randrange(threshold - 1000, threshold + 1000)
                cost = (bits - (threshold - 1000)) // 7
                rows.append({
                    "point_abs_ticks": cost,
                    "abs_bits": bits,
                    "mask": mask,
                    "coefficient_bits": bits,
                })
            available = rng.randrange(0, 3000)
            self.assertEqual(
                P6.lazy_reference_select(rows, available),
                P6.brute_force_reference_select(rows, available),
            )

    def test_lazy_tier2_is_required_and_exact_fit_is_selected(self) -> None:
        threshold = 0x3DA0000000000000
        rows = [
            {"point_abs_ticks": 0, "abs_bits": 0, "mask": 9},
            {"point_abs_ticks": 2, "abs_bits": threshold - 1, "mask": 7},
            {"point_abs_ticks": 3, "abs_bits": threshold, "mask": 5},
            {"point_abs_ticks": 4, "abs_bits": threshold + 1, "mask": 3},
        ]
        selected = P6.lazy_reference_select(rows, 5)
        self.assertEqual([row["mask"] for row in selected], [9, 7, 5])
        self.assertEqual(selected, P6.brute_force_reference_select(rows, 5))
        self.assertNotIn(3, [row["mask"] for row in selected])

    def test_first_nonfitting_row_stops_without_skipping(self) -> None:
        threshold = 0x3DA0000000000000
        rows = [
            {"point_abs_ticks": 2, "abs_bits": threshold - 3, "mask": 1},
            {"point_abs_ticks": 4, "abs_bits": threshold - 2, "mask": 2},
            {"point_abs_ticks": 4, "abs_bits": threshold - 1, "mask": 3},
        ]
        self.assertEqual(
            [row["mask"] for row in P6.lazy_reference_select(rows, 5)], [1],
        )

    def test_signed_zero_ties_and_input_order_are_deterministic(self) -> None:
        rows = [
            {"point_abs_ticks": 0, "abs_bits": 0, "mask": 8,
             "coefficient_bits": 0x8000000000000000},
            {"point_abs_ticks": 0, "abs_bits": 0, "mask": 2,
             "coefficient_bits": 0},
            {"point_abs_ticks": 1, "abs_bits": 1, "mask": 4,
             "coefficient_bits": 1},
        ]
        expected = [2, 8]
        for permutation in (rows, list(reversed(rows)), [rows[1], rows[2], rows[0]]):
            selected = P6.lazy_reference_select(permutation, 0)
            self.assertEqual([row["mask"] for row in selected], expected)
            self.assertEqual(
                {row["coefficient_bits"] for row in selected},
                {0, 0x8000000000000000},
            )

    def test_control_projection_and_public_witness_are_valid(self) -> None:
        witness = self._control_witness()
        validated = P6.validate_public_witness(
            witness, mode=P6.CONTROL_MODE,
        )
        self.assertEqual(validated["candidate"]["candidate_id"],
                         "P5-K37-RESOURCE-CONTROL")
        self.assertFalse(any(validated["selection_resources"].values()))
        observation = {
            "status": "COMPLETED_RESOURCE_OBSERVATION",
            "resource_witness": witness,
        }
        P6._validate_control(observation, self.policy)

    def test_public_witness_rejects_scientific_and_selection_mutations(self) -> None:
        mutations = []
        scientific = self._control_witness()
        scientific["step2"]["operator_error_ticks"] = "1"
        mutations.append(scientific)
        selection = self._control_witness()
        selection["selection_resources"]["total_tick_evaluations"] = 1
        selection["selection_resources"]["total_selection_work_units"] = 1
        mutations.append(selection)
        boolean_count = self._control_witness()
        boolean_count["selection_resources"][
            "total_ranking_scan_term_visits"
        ] = False
        mutations.append(boolean_count)
        identity = self._control_witness()
        identity["candidate"]["candidate_id"] = "E768-MAX-LAZY37-V1"
        mutations.append(identity)
        detached_link = self._control_witness()
        detached_link["step_link"]["step1_final_term_count"] += 1
        detached_link["step_link"]["step2_input_term_count"] += 1
        mutations.append(detached_link)
        missing_step2 = self._control_witness()
        missing_step2["step2"] = None
        missing_step2["step_link"] = None
        mutations.append(missing_step2)
        cap_context = self._control_witness()
        step2_limits = P6._step_cap_limits("step2")
        cap_context["step2"]["cap_event"] = {
            "cap_name": "maximum_premerge_terms",
            "limit": step2_limits["maximum_premerge_terms"],
            "attempted": step2_limits["maximum_premerge_terms"] + 1,
            "context": {
                "operation": "resource_cap_precheck",
                "operator_error_ticks": "1",
            },
            "rejected_operation_was_not_executed_after_cap_detection": True,
        }
        cap_context["step2"]["final_retained_term_count"] = None
        mutations.append(cap_context)
        for witness in mutations:
            with self.subTest(candidate=witness["candidate"]["candidate_id"]):
                with self.assertRaises(P6.ProbeError):
                    P6.validate_public_witness(witness, mode=P6.CONTROL_MODE)

    def test_legitimate_capped_progress_relations_are_accepted(self) -> None:
        witness = self._adaptive_witness()
        step2 = witness["step2"]
        limits = P6._step_cap_limits("step2")
        step2["cap_event"] = {
            "cap_name": "maximum_boundary_retained_terms",
            "limit": limits["maximum_boundary_retained_terms"],
            "attempted": limits["maximum_boundary_retained_terms"] + 1,
            "context": {
                "boundary_index": 767,
                "operation": "resource_cap_precheck",
            },
            "rejected_operation_was_not_executed_after_cap_detection": True,
        }
        step2["final_retained_term_count"] = None
        final_visits = step2["P2_resource_counters"][
            "final_evaluation_term_visits"
        ]
        step2["P2_resource_counters"]["final_evaluation_term_visits"] = 0
        step2["P2_resource_counters"]["total_charged_term_visits"] -= final_visits
        step2["total_P2_plus_accuracy_charged_event_count"] -= final_visits
        step2["completed_composite_count"] = 511
        step2["completed_constituent_count"] = 1151
        step2["completed_truncation_boundary_count"] = 767
        step2["threshold_dropped_term_count"] -= 1
        witness["selection_resources"][
            "completed_selection_boundary_count"
        ] = 768
        self.assertIs(
            P6.validate_public_witness(witness, mode=P6.ADAPTIVE_MODE), witness,
        )

    def test_observation_status_and_stdout_custody_fail_closed(self) -> None:
        host = self.policy["D0_host_supervisor_caps"]
        completed = self._completed_observation(
            P6.ADAPTIVE_MODE, self._adaptive_witness(),
        )
        P6._validate_observation(completed, P6.ADAPTIVE_MODE, host)

        for mutation in (
            {"process_returncode": 1},
            {"outer_timeout_triggered": True},
            {"stdout_bytes": host["maximum_stdout_bytes"] + 1},
            {"stderr_bytes": host["maximum_stderr_bytes"] + 1},
            {"stdout_sha256": "g" * 64},
        ):
            row = copy.deepcopy(completed)
            row.update(mutation)
            with self.subTest(mutation=mutation):
                with self.assertRaises(P6.ProbeError):
                    P6._validate_observation(row, P6.ADAPTIVE_MODE, host)

        for host_failure in (
            {"process_returncode": 1},
            {"outer_timeout_triggered": True},
            {"stdout_bytes": host["maximum_stdout_bytes"] + 1},
            {"stderr_bytes": host["maximum_stderr_bytes"] + 1},
        ):
            row = copy.deepcopy(completed)
            row.pop("resource_witness_sha256")
            row["status"] = "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
            row["resource_witness"] = None
            row.update(host_failure)
            P6._validate_observation(row, P6.ADAPTIVE_MODE, host)

        fake_host_failure = copy.deepcopy(completed)
        fake_host_failure.pop("resource_witness_sha256")
        fake_host_failure["status"] = "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
        fake_host_failure["resource_witness"] = None
        with self.assertRaisesRegex(P6.ProbeError, "has no host failure"):
            P6._validate_observation(
                fake_host_failure, P6.ADAPTIVE_MODE, host,
            )

    def test_formal_envelope_is_exact_and_not_bounded_by_D0_caps(self) -> None:
        observations = [
            self._completed_observation(P6.CONTROL_MODE, self._control_witness()),
            self._completed_observation(P6.ADAPTIVE_MODE, self._adaptive_witness()),
        ]
        step2_probe = self.fixture["deterministic_step2_probe_caps"]
        selection_probe = self.fixture["deterministic_selection_probe_caps"]
        adaptive = observations[1]["resource_witness"]
        accuracy = adaptive["step2"]["accuracy_event_counters"]
        accuracy.update({
            "anticommuting_event_count": 30_000_000,
            "product_defect_event_count": 60_000_000,
            "merge_defect_event_count": 8_000_000,
            "drop_defect_event_count": 10_000_000,
            "accuracy_charged_event_count": 78_000_000,
        })
        adaptive["step2"]["anticommuting_split_count"] = 30_000_000
        adaptive["step2"]["threshold_dropped_term_count"] = 10_000_000
        adaptive["step2"]["total_P2_plus_accuracy_charged_event_count"] = (
            adaptive["step2"]["P2_resource_counters"]
            ["total_charged_term_visits"]
            + accuracy["accuracy_charged_event_count"]
        )
        selection = adaptive["selection_resources"]
        selection["total_ranking_scan_term_visits"] = selection_probe[
            "maximum_ranking_scan_term_visits"
        ]
        selection["total_selection_work_units"] = (
            selection["total_ranking_scan_term_visits"]
            + selection["total_sort_work_items"]
            + selection["total_tick_evaluations"]
            + selection["total_selected_membership_insertions"]
        )
        envelope = P6._derive_formal_resource_envelope(observations, self.policy)
        self.assertEqual(
            envelope["status"], "ESTABLISHED_FOR_FUTURE_S0_PRECOMMIT",
        )
        self.assertGreater(
            envelope["formal_step2_caps"][
                "maximum_step2_accuracy_charged_events"
            ],
            step2_probe["maximum_step2_accuracy_charged_events"],
        )
        self.assertGreater(
            envelope["formal_selection_caps"]["maximum_ranking_scan_term_visits"],
            selection_probe["maximum_ranking_scan_term_visits"],
        )
        self.assertEqual(
            envelope["formal_host_caps"]["maximum_stderr_bytes"], 64,
        )

        capped = copy.deepcopy(observations)
        capped[1]["resource_witness"]["step2"] = None
        step1_limit = P6._step_cap_limits("step1")["maximum_premerge_terms"]
        capped[1]["resource_witness"]["step1"]["cap_event"] = {
            "cap_name": "maximum_premerge_terms",
            "limit": step1_limit, "attempted": step1_limit + 1,
            "context": {"operation": "resource_cap_precheck"},
            "rejected_operation_was_not_executed_after_cap_detection": True,
        }
        self.assertEqual(
            P6._derive_formal_resource_envelope(capped, self.policy)["status"],
            "NOT_ESTABLISHED_DETERMINISTIC_CAP",
        )

    def test_report_schema_manifest_and_internal_links_fail_closed(self) -> None:
        report = self._base_report()
        with mock.patch.object(P6, "_validate_preprobe_commit_identity") as check:
            self.assertIs(P6.validate_report(report), report)
            check.assert_called_once_with("a" * 40)

        mutations = []
        top = copy.deepcopy(report)
        top["operator_error_ticks"] = "1"
        mutations.append(top)
        observation = copy.deepcopy(report)
        observation["observations"][1]["operator_error_ticks"] = "1"
        mutations.append(observation)
        stdout = copy.deepcopy(report)
        stdout["observations"][1]["stdout_bytes"] += 1
        mutations.append(stdout)
        witness_sha = copy.deepcopy(report)
        witness_sha["observations"][1]["resource_witness_sha256"] = "0" * 64
        mutations.append(witness_sha)
        link = copy.deepcopy(report)
        link["observations"][1]["resource_witness"]["step_link"][
            "step1_final_term_count"
        ] += 1
        mutations.append(link)
        manifest = copy.deepcopy(report)
        manifest["staging_manifest"][0]["staged_sha256"] = "0" * 64
        manifest["staging_manifest_sha256"] = P6.canonical_sha256(
            manifest["staging_manifest"],
        )
        mutations.append(manifest)
        nondict_manifest = copy.deepcopy(report)
        nondict_manifest["staging_manifest"][0] = None
        nondict_manifest["staging_manifest_sha256"] = P6.canonical_sha256(
            nondict_manifest["staging_manifest"],
        )
        mutations.append(nondict_manifest)
        host = copy.deepcopy(report)
        host["host_caps"]["MemoryMax_bytes"] += 1
        mutations.append(host)
        envelope = copy.deepcopy(report)
        envelope["formal_resource_envelope"]["formal_host_caps"][
            "maximum_stderr_bytes"
        ] += 1
        mutations.append(envelope)
        fake_cap = copy.deepcopy(report)
        fake_step2 = fake_cap["observations"][1]["resource_witness"]["step2"]
        fake_step2["cap_event"] = {
            "cap_name": "maximum_totally_fake",
            "limit": 1,
            "attempted": 2,
            "context": {"operation": "resource_cap_precheck"},
            "rejected_operation_was_not_executed_after_cap_detection": True,
        }
        fake_step2["final_retained_term_count"] = None
        self._refresh_observation_custody(fake_cap)
        mutations.append(fake_cap)
        broken_accuracy = copy.deepcopy(report)
        broken_accuracy["observations"][1]["resource_witness"]["step2"][
            "accuracy_event_counters"
        ]["accuracy_charged_event_count"] += 1
        self._refresh_observation_custody(broken_accuracy)
        mutations.append(broken_accuracy)
        excess_boundaries = copy.deepcopy(report)
        excess_boundaries["observations"][1]["resource_witness"][
            "selection_resources"
        ]["completed_selection_boundary_count"] = 769
        self._refresh_observation_custody(excess_boundaries)
        mutations.append(excess_boundaries)
        diagnostic_injection = copy.deepcopy(report)
        diagnostic_injection["observations"][1]["time_diagnostics"][
            "elapsed_wall_clock"
        ] = "operator_error_ticks=123"
        mutations.append(diagnostic_injection)
        boolean_schema = copy.deepcopy(report)
        boolean_schema["schema_version"] = True
        mutations.append(boolean_schema)
        for index, mutated in enumerate(mutations):
            with self.subTest(index=index):
                self._assert_report_rejected(mutated)

    def test_report_host_status_cannot_carry_a_witness(self) -> None:
        report = self._base_report()
        row = report["observations"][1]
        row.pop("resource_witness_sha256")
        row["status"] = "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
        row["process_returncode"] = 1
        row["resource_witness"]["operator_error_ticks"] = "1"
        report["formal_resource_envelope"] = P6._derive_formal_resource_envelope(
            report["observations"], self.policy,
        )
        self._assert_report_rejected(report)

    def test_preprobe_commit_identity_is_fail_closed_before_commit(self) -> None:
        for value in (None, "0" * 39, "G" * 40, P6.DIRECT_PARENT):
            with self.subTest(value=value):
                with self.assertRaises(P6.ProbeError):
                    P6._validate_preprobe_commit_identity(value)

    def test_control_stop_branches_are_classified_without_a_report(self) -> None:
        host_failure = {
            "status": "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
            "resource_witness": None,
        }
        with self.assertRaisesRegex(P6.ProbeError, "CONTROL_INDETERMINATE"):
            P6._validate_control(host_failure, self.policy)

        cap_limit = P6._step_cap_limits("step2")["maximum_premerge_terms"]
        capped = self._control_witness()
        capped["step2"]["cap_event"] = {
            "cap_name": "maximum_premerge_terms",
            "limit": cap_limit,
            "attempted": cap_limit + 1,
            "context": {"operation": "resource_cap_precheck"},
            "rejected_operation_was_not_executed_after_cap_detection": True,
        }
        capped["step2"]["final_retained_term_count"] = None
        with self.assertRaisesRegex(
            P6.ProbeError, "RESOURCE_ENVELOPE_NOT_ESTABLISHED",
        ):
            P6._validate_control({
                "status": "COMPLETED_RESOURCE_OBSERVATION",
                "resource_witness": capped,
            }, self.policy)
        stop = self.policy["stop_rules"]
        self.assertTrue(
            stop[
                "control_host_failure_terminates_before_candidate_and_report_"
                "as_INDETERMINATE_without_authority"
            ]
        )
        self.assertTrue(
            stop[
                "control_deterministic_cap_terminates_before_candidate_and_"
                "report_as_D0_RESOURCE_ENVELOPE_NOT_ESTABLISHED_without_authority"
            ]
        )

        capped_observation = {
            "status": "COMPLETED_RESOURCE_OBSERVATION",
            "resource_witness": capped,
        }
        for observation, message in (
            (host_failure, "CONTROL_INDETERMINATE"),
            (capped_observation, "RESOURCE_ENVELOPE_NOT_ESTABLISHED"),
        ):
            with self.subTest(orchestration=message):
                with tempfile.TemporaryDirectory(
                    prefix="majorana-p6-control-stop-",
                ) as root:
                    root = Path(root)
                    julia = root / "julia"
                    julia.write_bytes(b"frozen-test-runtime")
                    depot = root / "depot"
                    depot.mkdir()
                    output = root / P6.REPORT_NAME
                    with (
                        mock.patch.object(
                            P6, "validate_policy", return_value=self.policy,
                        ),
                        mock.patch.object(P6, "_validate_preprobe_commit"),
                        mock.patch.object(
                            P6, "file_sha256",
                            return_value=self.policy["runtime"]
                            ["julia_executable_sha256"],
                        ),
                        mock.patch.object(
                            P6, "_run_candidate", return_value=observation,
                        ) as runner,
                    ):
                        with self.assertRaisesRegex(P6.ProbeError, message):
                            P6.run_probe("a" * 40, julia, depot, output)
                    self.assertEqual(runner.call_count, 1)
                    self.assertFalse(output.exists())

    def test_policy_mutations_fail_closed(self) -> None:
        mutations = []
        authority = copy.deepcopy(self.policy)
        authority["scientific_authority"] = "RESOURCE_AND_ERROR_BOUND"
        mutations.append(authority)
        candidates = copy.deepcopy(self.policy)
        candidates["candidate_design"]["formal_candidates"].append(
            copy.deepcopy(candidates["candidate_design"]["formal_candidates"][0])
        )
        mutations.append(candidates)
        transform = copy.deepcopy(self.policy)
        transform["staged_instrumentation_transform"]["callback_replacement"] += " "
        mutations.append(transform)
        host = copy.deepcopy(self.policy)
        host["D0_host_supervisor_caps"]["MemoryMax_bytes"] += 1
        mutations.append(host)
        for policy in mutations:
            with self.assertRaises(P6.ProbeError):
                P6.validate_policy(policy, require_report_absent=True)

    def test_source_pin_mutation_fails_closed(self) -> None:
        mutated = copy.deepcopy(self.policy)
        mutated["source_files"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(P6.ProbeError, "source hash drift"):
            P6.validate_policy(mutated, require_report_absent=True)

    def test_driver_has_no_public_scientific_result_path(self) -> None:
        driver = (BASE / P6.PROBE_DRIVER).read_text(encoding="utf-8")
        self.assertIn('scientific_authority="NONE"', driver)
        self.assertIn("p6_assert_public_vocabulary(raw)", driver)
        self.assertIn("p6_prefix_target(boundary_index", driver)
        self.assertIn("tier2_original_snapshot_rescan", driver)
        self.assertIn("p6_validate_selected_drop_ticks!", driver)
        self.assertIn(
            'result["operation"] = "resource_cap_precheck"', driver,
        )
        self.assertNotIn("candidate_local_allocation_pass=", driver)
        self.assertNotIn("checkerboard_Neel_center=", driver)

    def test_preprobe_changed_path_allowlist_is_exact(self) -> None:
        self.assertEqual(len(P6.PREPROBE_CHANGED_PATHS), 5)
        self.assertIn(
            "docs/research/fermion-frontier/"
            "test_majorana_certificate_p6_design_probe.py",
            P6.PREPROBE_CHANGED_PATHS,
        )
        self.assertNotIn(
            f"docs/research/fermion-frontier/{P6.REPORT_NAME}",
            P6.PREPROBE_CHANGED_PATHS,
        )


if __name__ == "__main__":
    unittest.main()
