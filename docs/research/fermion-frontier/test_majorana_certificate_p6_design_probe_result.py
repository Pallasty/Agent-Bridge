#!/usr/bin/env python3
"""Exact-result tests for the non-authoritative Majorana P6 D0 report."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


BASE = Path(__file__).resolve().parent
REPORT_SHA256 = "7c591111ee99b18bf2ccaca2d8157e93a19a3db49b6a680c01b0be13f570fc56"


def _load_probe():
    path = BASE / "majorana_certificate_p6_design_probe.py"
    spec = importlib.util.spec_from_file_location("majorana_p6_d0_result", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P6 = _load_probe()


class MajoranaP6DesignProbeResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = P6.validate_report(P6.load_json(BASE / P6.REPORT_NAME))
        cls.observations = {
            row["probe_mode"]: row for row in cls.report["observations"]
        }

    def test_report_hash_canonical_identity_and_authority_are_exact(self) -> None:
        path = BASE / P6.REPORT_NAME
        self.assertEqual(P6.file_sha256(path), REPORT_SHA256)
        self.assertEqual(path.read_bytes(), P6.canonical_bytes(self.report) + b"\n")
        self.assertEqual(
            self.report["report_type"],
            "majorana_p6_e768_max_lazy37_resource_report_d0_v1",
        )
        self.assertEqual(self.report["scientific_authority"], "NONE")
        self.assertFalse(self.report["certificate_eligible"])
        self.assertEqual(
            self.report["formal_candidate_was_frozen_before_probe"],
            "E768-MAX-LAZY37-V1",
        )
        self.assertTrue(self.report["control_is_not_selectable"])

    def test_preprobe_policy_fixture_and_staging_custody_are_exact(self) -> None:
        self.assertEqual(
            self.report["preprobe_commit_sha"],
            "2483450e9ae93402a5315dae21b142d08742e783",
        )
        self.assertEqual(
            self.report["policy_sha256"],
            "6a8b9c1c2584cbe8998643e0644f35896d54fe57444eff795a93a83987fa87ab",
        )
        self.assertEqual(
            self.report["fixture_sha256"],
            "2e5254b7a98cf4b0ba08c5674215d78a59a78ddf0b0e27460b7cf82ac7be3b6e",
        )
        self.assertEqual(
            self.report["fixture_canonical_sha256"],
            "9b02421b53ef407531b95e1f9d4f48f29642f88962be297789ecbc88792755ba",
        )
        self.assertEqual(
            self.report["staging_manifest_sha256"],
            "f15196a28aaeeb2535d719f533dd4cb5f6c17f51e184450fa7a02f547358788f",
        )
        self.assertEqual(len(self.report["staging_manifest"]), 12)

    def test_control_and_adaptive_observations_completed_without_caps(self) -> None:
        self.assertEqual(tuple(self.observations), P6.MODE_ORDER)
        for mode, row in self.observations.items():
            with self.subTest(mode=mode):
                self.assertEqual(row["status"], "COMPLETED_RESOURCE_OBSERVATION")
                self.assertEqual(row["process_returncode"], 0)
                self.assertFalse(row["outer_timeout_triggered"])
                self.assertIsNone(row["resource_witness"]["step1"]["cap_event"])
                self.assertIsNone(row["resource_witness"]["step2"]["cap_event"])
                self.assertTrue(
                    row["host_failure_has_no_mathematical_authority"],
                )

    def test_control_projection_and_fresh_step1_are_exact(self) -> None:
        control = self.observations[P6.CONTROL_MODE]["resource_witness"]
        adaptive = self.observations[P6.ADAPTIVE_MODE]["resource_witness"]
        self.assertEqual(
            P6._control_projection(control),
            P6.load_json(BASE / P6.POLICY_NAME)
            ["expected_P5_K37_control_resource_projection"],
        )
        self.assertFalse(any(control["selection_resources"].values()))
        self.assertEqual(adaptive["step1"], control["step1"])
        self.assertEqual(adaptive["step_link"], control["step_link"])

    def test_adaptive_aggregate_resources_are_exact(self) -> None:
        row = self.observations[P6.ADAPTIVE_MODE]
        witness = row["resource_witness"]
        step2 = witness["step2"]
        self.assertEqual(step2["peak_premerge_contribution_count"], 307507)
        self.assertEqual(step2["peak_postmerge_unique_term_count"], 303027)
        self.assertEqual(step2["final_retained_term_count"], 284847)
        self.assertEqual(step2["threshold_dropped_term_count"], 4208292)
        self.assertEqual(
            step2["P2_resource_counters"]["total_charged_term_visits"],
            426811185,
        )
        self.assertEqual(
            step2["total_P2_plus_accuracy_charged_event_count"], 445136171,
        )
        self.assertEqual(witness["selection_resources"], {
            "completed_selection_boundary_count": 768,
            "peak_ranking_buffer_terms": 303027,
            "total_ranking_scan_term_visits": 114104682,
            "total_selected_membership_insertions": 4208292,
            "total_selection_work_units": 160531288,
            "total_sort_work_items": 20263438,
            "total_tick_evaluations": 21954876,
        })
        self.assertEqual(
            row["time_diagnostics"]["maximum_resident_set_size_KiB"], 892140,
        )
        self.assertEqual(row["time_diagnostics"]["elapsed_wall_clock"], "14:33.41")
        self.assertEqual(row["outer_monotonic_elapsed_ns"], 873437951168)
        self.assertEqual(row["stderr_bytes"], 1412)

    def test_formal_resource_envelope_is_exact_and_rederived(self) -> None:
        expected = {
            "status": "ESTABLISHED_FOR_FUTURE_S0_PRECOMMIT",
            "formal_host_caps": {
                "MemoryMax_bytes": 2147483648,
                "MemorySwapMax_bytes": 0,
                "RuntimeMaxSec": "1800s",
                "maximum_stderr_bytes": 4096,
            },
            "formal_selection_caps": {
                "maximum_peak_ranking_buffer_terms": 1048576,
                "maximum_ranking_scan_term_visits": 268435456,
                "maximum_selected_membership_insertions": 16777216,
                "maximum_sort_input_items": 67108864,
                "maximum_tick_evaluations": 67108864,
                "maximum_total_selection_work_units": 536870912,
            },
            "formal_step2_caps": {
                "maximum_step2_accuracy_charged_events": 67108864,
                "maximum_step2_anticommuting_events": 16777216,
                "maximum_step2_boundary_retained_terms": 1048576,
                "maximum_step2_cap_scan_term_visits": 536870912,
                "maximum_step2_current_terms_before_constituent": 1048576,
                "maximum_step2_drop_defect_events": 16777216,
                "maximum_step2_final_retained_terms": 1048576,
                "maximum_step2_merge_defect_events": 4194304,
                "maximum_step2_premerge_terms": 1048576,
                "maximum_step2_product_defect_events": 33554432,
                "maximum_step2_propagation_term_visits": 536870912,
                "maximum_step2_total_P2_charged_term_visits": 1073741824,
                "maximum_step2_total_P2_plus_accuracy_charged_events":
                    1073741824,
                "maximum_step2_truncation_term_visits": 268435456,
            },
        }
        self.assertEqual(self.report["formal_resource_envelope"], expected)
        self.assertEqual(
            P6._derive_formal_resource_envelope(
                self.report["observations"],
                P6.load_json(BASE / P6.POLICY_NAME),
            ),
            expected,
        )

    def test_report_contains_no_scientific_result_vocabulary(self) -> None:
        forbidden = (
            "operator_error_ticks", "product_defect_ticks",
            "merge_defect_ticks", "drop_defect_ticks", "allocation_pass",
            "budget", "slack", "coefficient_bits", "mask_hex", "drop_rows",
            "term_stream", "neel", "winner", "fallback",
        )

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    lower = str(key).lower()
                    self.assertFalse(any(token in lower for token in forbidden), key)
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
            elif isinstance(value, str):
                lower = value.lower()
                self.assertFalse(any(token in lower for token in forbidden), value)

        walk(self.report)


if __name__ == "__main__":
    unittest.main()
