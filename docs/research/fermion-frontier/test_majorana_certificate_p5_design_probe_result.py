#!/usr/bin/env python3
"""Exact-result tests for the Majorana P5 D0 resource-only report."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


BASE = Path(__file__).resolve().parent
REPORT_SHA256 = "602c4eddea30c20ddb793e2641b1e8b55e4767a62366b946892a19c3802dffc5"


def _load_probe():
    path = BASE / "majorana_certificate_p5_design_probe.py"
    spec = importlib.util.spec_from_file_location("majorana_p5_d0_result", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P5 = _load_probe()


def _next_power_of_two_at_least_twice(value: int) -> int:
    target = 2 * value
    return 1 << (target - 1).bit_length()


class MajoranaP5DesignProbeResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = P5.validate_report(P5.load_json(BASE / P5.REPORT_NAME))
        cls.observations = {
            row["step2_threshold_exponent"]: row
            for row in cls.report["observations"]
        }

    def test_report_hash_canonical_bytes_identity_and_authority_are_exact(self) -> None:
        path = BASE / P5.REPORT_NAME
        self.assertEqual(P5.file_sha256(path), REPORT_SHA256)
        self.assertEqual(path.read_bytes(), P5.canonical_bytes(self.report) + b"\n")
        self.assertEqual(
            self.report["report_type"],
            "majorana_p5_conditional_step2_threshold_resource_report_d0_v1",
        )
        self.assertEqual(self.report["scientific_authority"], "NONE")
        self.assertFalse(self.report["certificate_eligible"])
        self.assertTrue(self.report["probe_results_must_not_be_runner_inputs_for_formal_P5"])

    def test_preprobe_policy_staging_and_control_custody_are_exact(self) -> None:
        self.assertEqual(
            self.report["preprobe_commit_sha"],
            "f65ceb94494d71a2de1cd6057405a583fa388f82",
        )
        self.assertEqual(
            self.report["policy_sha256"],
            "e47ad24291f217b0b5d54ba6aa120c479d522bd23c74faf41b5bde6da2413aa2",
        )
        self.assertEqual(
            self.report["staging_manifest_sha256"],
            "8146322aab025311be873daaf58a61fa0e6ad5123d68182894a1706c40d2eeab",
        )
        P5._validate_control(self.observations[34], P5.load_json(BASE / P5.POLICY_NAME))

    def test_every_candidate_completed_without_host_or_deterministic_cap(self) -> None:
        self.assertEqual(tuple(self.observations), (34, 36, 37))
        for exponent, row in self.observations.items():
            with self.subTest(exponent=exponent):
                self.assertEqual(row["status"], "COMPLETED_RESOURCE_OBSERVATION")
                self.assertEqual(row["process_returncode"], 0)
                self.assertFalse(row["outer_timeout_triggered"])
                self.assertIsNone(row["resource_witness"]["step1"]["cap_event"])
                self.assertIsNone(row["resource_witness"]["step2"]["cap_event"])

    def test_common_step1_resource_projection_is_identical_for_all_candidates(self) -> None:
        control_step1 = self.observations[34]["resource_witness"]["step1"]
        for exponent in (36, 37):
            self.assertEqual(
                self.observations[exponent]["resource_witness"]["step1"],
                control_step1,
            )
        self.assertEqual(control_step1["final_retained_term_count"], 42704)

    def test_candidate_thresholds_and_resource_growth_are_exact(self) -> None:
        expected = {
            36: {
                "bits": "3db0000000000000",
                "rational": "1/68719476736",
                "peak_premerge": 186102,
                "peak_postmerge": 183704,
                "final_terms": 174280,
                "drops": 2754752,
                "P2_total": 279133312,
                "combined": 290750192,
                "RSS_KiB": 731012,
            },
            37: {
                "bits": "3da0000000000000",
                "rational": "1/137438953472",
                "peak_premerge": 257558,
                "peak_postmerge": 253710,
                "final_terms": 241120,
                "drops": 3682224,
                "P2_total": 372980288,
                "combined": 388900128,
                "RSS_KiB": 734516,
            },
        }
        for exponent, values in expected.items():
            row = self.observations[exponent]
            witness = row["resource_witness"]
            step2 = witness["step2"]
            with self.subTest(exponent=exponent):
                self.assertEqual(witness["candidate"]["step2_threshold_Float64_bits_hex"], values["bits"])
                self.assertEqual(witness["candidate"]["step2_threshold_rational"], values["rational"])
                self.assertEqual(step2["peak_premerge_contribution_count"], values["peak_premerge"])
                self.assertEqual(step2["peak_postmerge_unique_term_count"], values["peak_postmerge"])
                self.assertEqual(step2["final_retained_term_count"], values["final_terms"])
                self.assertEqual(step2["threshold_dropped_term_count"], values["drops"])
                self.assertEqual(step2["P2_resource_counters"]["total_charged_term_visits"], values["P2_total"])
                self.assertEqual(step2["total_P2_plus_accuracy_charged_event_count"], values["combined"])
                self.assertEqual(row["time_diagnostics"]["maximum_resident_set_size_KiB"], values["RSS_KiB"])

    def test_derived_common_formal_caps_follow_the_precommitted_rule(self) -> None:
        candidates = [self.observations[k]["resource_witness"]["step2"] for k in (36, 37)]
        maximum = lambda getter: max(getter(row) for row in candidates)
        derived = {
            "maximum_step2_current_terms_before_constituent": _next_power_of_two_at_least_twice(maximum(lambda row: row["peak_postmerge_unique_term_count"])),
            "maximum_step2_boundary_retained_terms": _next_power_of_two_at_least_twice(maximum(lambda row: row["peak_postmerge_unique_term_count"])),
            "maximum_step2_final_retained_terms": _next_power_of_two_at_least_twice(maximum(lambda row: row["final_retained_term_count"])),
            "maximum_step2_premerge_terms": _next_power_of_two_at_least_twice(maximum(lambda row: row["peak_premerge_contribution_count"])),
            "maximum_step2_cap_scan_term_visits": _next_power_of_two_at_least_twice(maximum(lambda row: row["P2_resource_counters"]["cap_scan_term_visits"])),
            "maximum_step2_propagation_term_visits": _next_power_of_two_at_least_twice(maximum(lambda row: row["P2_resource_counters"]["propagation_term_visits"])),
            "maximum_step2_truncation_term_visits": _next_power_of_two_at_least_twice(maximum(lambda row: row["P2_resource_counters"]["truncation_term_visits"])),
            "maximum_step2_total_P2_charged_term_visits": _next_power_of_two_at_least_twice(maximum(lambda row: row["P2_resource_counters"]["total_charged_term_visits"])),
            "maximum_step2_anticommuting_events": _next_power_of_two_at_least_twice(maximum(lambda row: row["accuracy_event_counters"]["anticommuting_event_count"])),
            "maximum_step2_product_defect_events": _next_power_of_two_at_least_twice(maximum(lambda row: row["accuracy_event_counters"]["product_defect_event_count"])),
            "maximum_step2_merge_defect_events": _next_power_of_two_at_least_twice(maximum(lambda row: row["accuracy_event_counters"]["merge_defect_event_count"])),
            "maximum_step2_drop_defect_events": _next_power_of_two_at_least_twice(maximum(lambda row: row["accuracy_event_counters"]["drop_defect_event_count"])),
            "maximum_step2_accuracy_charged_events": _next_power_of_two_at_least_twice(maximum(lambda row: row["accuracy_event_counters"]["accuracy_charged_event_count"])),
            "maximum_step2_total_P2_plus_accuracy_charged_events": _next_power_of_two_at_least_twice(maximum(lambda row: row["total_P2_plus_accuracy_charged_event_count"])),
        }
        self.assertEqual(derived, {
            "maximum_step2_current_terms_before_constituent": 524288,
            "maximum_step2_boundary_retained_terms": 524288,
            "maximum_step2_final_retained_terms": 524288,
            "maximum_step2_premerge_terms": 524288,
            "maximum_step2_cap_scan_term_visits": 536870912,
            "maximum_step2_propagation_term_visits": 536870912,
            "maximum_step2_truncation_term_visits": 268435456,
            "maximum_step2_total_P2_charged_term_visits": 1073741824,
            "maximum_step2_anticommuting_events": 16777216,
            "maximum_step2_product_defect_events": 33554432,
            "maximum_step2_merge_defect_events": 4194304,
            "maximum_step2_drop_defect_events": 8388608,
            "maximum_step2_accuracy_charged_events": 33554432,
            "maximum_step2_total_P2_plus_accuracy_charged_events": 1073741824,
        })

    def test_report_contains_no_scientific_result_fields(self) -> None:
        forbidden_key_fragments = (
            "_ticks", "allocation", "Neel", "term_stream", "drop_rows",
            "expectation", "canonical_witness",
        )

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    self.assertFalse(
                        any(fragment in key for fragment in forbidden_key_fragments),
                        key,
                    )
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(self.report)


if __name__ == "__main__":
    unittest.main()
