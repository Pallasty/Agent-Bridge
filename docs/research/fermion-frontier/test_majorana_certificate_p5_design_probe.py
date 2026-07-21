#!/usr/bin/env python3
"""Regression tests for the non-authoritative Majorana P5 D0 probe."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


BASE = Path(__file__).resolve().parent


def _load_probe():
    path = BASE / "majorana_certificate_p5_design_probe.py"
    spec = importlib.util.spec_from_file_location("majorana_p5_d0_probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P5 = _load_probe()


class MajoranaP5DesignProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = P5.load_json(BASE / P5.POLICY_NAME)

    def test_preprobe_policy_is_valid_and_result_was_absent_at_preprobe_commit(self) -> None:
        validated = P5.validate_policy(self.policy, require_report_absent=False)
        self.assertEqual(
            validated["policy_id"],
            "MAJORANA-P5-CONDITIONAL-STEP2-THRESHOLD-D0-V1",
        )
        path_at_preprobe = (
            "f65ceb94494d71a2de1cd6057405a583fa388f82:"
            "docs/research/fermion-frontier/" + P5.REPORT_NAME
        )
        process = subprocess.run(
            ["git", "cat-file", "-e", path_at_preprobe],
            cwd=BASE,
            check=False,
            capture_output=True,
        )
        self.assertNotEqual(process.returncode, 0)

    def test_candidate_set_is_frozen_before_resource_observation(self) -> None:
        design = self.policy["candidate_design"]
        self.assertEqual(design["probe_order_step2_threshold_exponents"], [34, 36, 37])
        self.assertEqual(design["formal_candidates_step2_threshold_exponents"], [36, 37])
        self.assertEqual(design["step1_threshold_exponent_for_every_candidate"], 34)
        self.assertTrue(design["formal_candidates_are_frozen_before_any_probe_output"])
        self.assertTrue(design["candidate_state_is_not_shared"])

    def test_D0_has_no_scientific_or_certificate_authority(self) -> None:
        self.assertEqual(self.policy["scientific_authority"], "NONE")
        self.assertFalse(self.policy["certificate_eligible"])
        boundary = self.policy["probe_observation_boundary"]
        self.assertTrue(boundary["probe_output_cannot_be_a_formal_runner_input"])
        self.assertTrue(boundary["probe_output_cannot_select_remove_or_reorder_formal_candidates"])
        self.assertIn("allocation_comparison_or_candidate_ranking", boundary["forbidden"])
        self.assertIn("Neel_center_expectation_or_interval", boundary["forbidden"])

    def test_source_pins_are_exact_and_complete(self) -> None:
        pins = P5._source_pins(self.policy)
        self.assertEqual(set(pins), set((*P5.STAGED_PATHS, P5.Path(P5.__file__).name)))
        for relative, row in pins.items():
            with self.subTest(relative=relative):
                path = BASE / relative
                self.assertEqual(path.stat().st_size, row["size_bytes"])
                self.assertEqual(P5.file_sha256(path), row["sha256"])

    def test_staging_changes_only_the_P3_probe_copy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="majorana-p5-d0-test-") as temporary:
            destination = Path(temporary)
            rows = P5.stage_probe_tree(destination, self.policy)
            self.assertEqual(tuple(row["relative_path"] for row in rows), P5.STAGED_PATHS)
            changed = [row["relative_path"] for row in rows if row["instrumented_copy"]]
            self.assertEqual(changed, [P5.P3_RUNNER])
            for row in rows:
                with self.subTest(relative=row["relative_path"]):
                    if row["relative_path"] == P5.P3_RUNNER:
                        self.assertNotEqual(row["repository_sha256"], row["staged_sha256"])
                    else:
                        self.assertEqual(row["repository_sha256"], row["staged_sha256"])

    def test_P3_transform_is_unique_fail_closed_and_does_not_touch_repository(self) -> None:
        source = (BASE / P5.P3_RUNNER).read_bytes()
        transformed = P5._instrument_p3(source)
        self.assertIn(P5.P3_SELECTOR_INSERTION.encode(), transformed)
        self.assertIn(P5.P3_DROP_REPLACEMENT.encode(), transformed)
        self.assertNotIn(P5.P3_DROP_NEEDLE.encode(), transformed)
        self.assertEqual((BASE / P5.P3_RUNNER).read_bytes(), source)
        with self.assertRaisesRegex(P5.ProbeError, "occurrence count is not one"):
            P5._instrument_p3(transformed)
        with self.assertRaisesRegex(P5.ProbeError, "occurrence count is not one"):
            P5._instrument_p3(source.replace(P5.P3_DROP_NEEDLE.encode(), b"missing"))

    def test_control_projection_is_the_formal_P4_resource_projection(self) -> None:
        control = self.policy["expected_2^-34_control_resource_projection"]
        self.assertEqual(control["step1"]["final_retained_term_count"], 42704)
        self.assertEqual(control["step2"]["final_retained_term_count"], 72808)
        self.assertEqual(control["step2"]["threshold_dropped_term_count"], 1637980)
        self.assertEqual(
            control["step2"]["P2_resource_counters"]["total_charged_term_visits"],
            179304556,
        )
        self.assertIsNone(control["step1"]["cap_event"])
        self.assertIsNone(control["step2"]["cap_event"])
        self.assertTrue(control["step_link"]["same_process"])

    def test_probe_caps_are_exactly_the_frozen_P4_step2_caps(self) -> None:
        p4_caps = P5.load_json(BASE / "majorana_certificate_p4_fixture.json")[
            "deterministic_resource_caps"
        ]
        expected = {key: p4_caps[key] for key in P5.STEP2_CAP_KEYS}
        self.assertEqual(self.policy["deterministic_step2_probe_caps"], expected)

    def test_cap_derivation_cannot_selectively_exclude_a_candidate(self) -> None:
        rule = self.policy["formal_cap_derivation_rule"]
        self.assertTrue(rule["requires_both_2^-36_and_2^-37_to_complete_without_host_or_deterministic_cap"])
        self.assertTrue(rule["one_common_cap_set_must_cover_both_formal_candidates"])
        self.assertTrue(rule["a_cap_or_host_failure_requires_a_new_versioned_D0_probe_and_cannot_be_repaired_in_place"])

    def test_authority_candidate_transform_and_host_mutations_fail_closed(self) -> None:
        mutations = []
        authority = copy.deepcopy(self.policy)
        authority["scientific_authority"] = "RESOURCE_AND_ERROR_BOUND"
        mutations.append((authority, "scientific authority"))
        candidates = copy.deepcopy(self.policy)
        candidates["candidate_design"]["formal_candidates_step2_threshold_exponents"] = [36]
        mutations.append((candidates, "formal candidate set drift"))
        transform = copy.deepcopy(self.policy)
        transform["staged_instrumentation_transform"]["drop_replacement"] += " "
        mutations.append((transform, "instrumentation transform drift"))
        host = copy.deepcopy(self.policy)
        host["host_caps"]["MemoryMax_bytes"] += 1
        mutations.append((host, "host caps drift"))
        for mutated, message in mutations:
            with self.subTest(message=message):
                with self.assertRaisesRegex(P5.ProbeError, message):
                    P5.validate_policy(mutated, require_report_absent=True)

    def test_source_pin_mutation_fails_closed(self) -> None:
        mutated = copy.deepcopy(self.policy)
        mutated["source_files"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(P5.ProbeError, "source hash drift"):
            P5.validate_policy(mutated, require_report_absent=True)

    def test_driver_does_not_emit_an_accuracy_ledger_or_scientific_result(self) -> None:
        driver = (BASE / P5.PROBE_DRIVER).read_text(encoding="utf-8")
        self.assertNotIn("build_accuracy_ledger(", driver)
        self.assertNotIn("build_execution_witness(", driver)
        self.assertNotIn("canonical_witness", driver)
        self.assertIn('scientific_authority="NONE"', driver)
        self.assertIn("resource_observations_only=true", driver)


if __name__ == "__main__":
    unittest.main()
