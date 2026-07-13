#!/usr/bin/env python3
"""Static and semantic tests for the non-authoritative adaptive-K v2 probes."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PROBE = load_module(
    "hubbard_l8_adaptive_k_v2_design_probe",
    "hubbard_l8_adaptive_k_v2_design_probe.py",
)
KERNEL = load_module(
    "hubbard_l8_adaptive_k_arithmetic_v2_for_probe_tests",
    "hubbard_l8_adaptive_k_arithmetic_v2.py",
)

EXPECTED = {
    "magnetization": {
        "filename": "hubbard_l8_magnetization_adaptive_k_v2_design_transcript.json",
        "file_sha256": "aaed027aa212f60a40eea93c0826c45cfe5ffa23ef94b0b616213d794e83fd12",
        "records_sha256": "30c538ed5faee21fe92a547ead1e3e2f1726f9ebebaad6f7fa815b64f36ca6fa",
        "failure_sha256": "1a8ec75243bc2e3134c1df4586ebcbbbc4f12b9d5b286d5bb0801f37f5702894",
        "failure_checkpoint": 29,
        "completed_checkpoints": 28,
        "minimum_K": 333_983,
        "K_excess": 6_303,
        "peak": 397_526,
        "visits": 48_646_721,
    },
    "double_occupancy": {
        "filename": "hubbard_l8_double_occupancy_adaptive_k_v2_design_transcript.json",
        "file_sha256": "4223155009f7dc4c8fe883a75ac71116ddaff82492e1e1602685e893c4c2368c",
        "records_sha256": "504964a8ab8cb0d68ccf203f8c70876bbf21b5bd631d621bdaef8500c479b051",
        "failure_sha256": "f3e78409683eb88c21861a0ae4b1029b8247629d458eb836b30edeaeb2e50820",
        "failure_checkpoint": 22,
        "completed_checkpoints": 21,
        "minimum_K": 350_604,
        "K_excess": 22_924,
        "peak": 501_254,
        "visits": 37_271_764,
    },
}


def load_transcript(mode: str):
    expected = EXPECTED[mode]
    raw = (HERE / expected["filename"]).read_bytes()
    value = json.loads(raw)
    canonical = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return raw, canonical, value


def walk(value):
    yield value
    if type(value) is dict:
        for key, child in value.items():
            yield key
            yield from walk(child)
    elif type(value) is list:
        for child in value:
            yield from walk(child)


class AdaptiveKV2DesignProbeTests(unittest.TestCase):
    def test_01_probe_source_and_kernel_are_pinned(self):
        probe_sha = hashlib.sha256(
            (HERE / "hubbard_l8_adaptive_k_v2_design_probe.py").read_bytes()
        ).hexdigest()
        kernel_sha = hashlib.sha256(
            (HERE / "hubbard_l8_adaptive_k_arithmetic_v2.py").read_bytes()
        ).hexdigest()
        self.assertEqual(
            probe_sha,
            "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3",
        )
        self.assertEqual(kernel_sha, PROBE.EXPECTED_KERNEL_SHA256)
        for mode in EXPECTED:
            _raw, _canonical, transcript = load_transcript(mode)
            self.assertEqual(transcript["design_probe_source_sha256"], probe_sha)
            self.assertEqual(
                transcript["source_custody"][PROBE.KERNEL_NAME], kernel_sha
            )

    def test_02_new_step_arithmetic_is_local_to_v2(self):
        source = (HERE / "hubbard_l8_adaptive_k_v2_design_probe.py").read_text()
        for forbidden in (
            "root._propagate_gate",
            "root._multiply_ticks",
            "root._add_tick_term",
            "root._tick_digest",
            "root._truncate",
            "root._expectation_ticks",
            "root.PropagationCounter",
        ):
            self.assertNotIn(forbidden, source)
        for required in (
            "kernel.PropagationCounterV2",
            "kernel.propagate_batch",
            "kernel.tick_digest",
            "kernel.rank_with_suffix",
            "kernel.evaluate_candidates",
            "kernel.commit_candidate",
            "kernel.expectation_ticks",
        ):
            self.assertIn(required, source)

    def test_03_transcripts_are_canonical_diagnostic_only(self):
        for mode, expected in EXPECTED.items():
            raw, canonical, transcript = load_transcript(mode)
            self.assertEqual(raw, canonical)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["file_sha256"])
            self.assertEqual(
                transcript["status"], "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS"
            )
            self.assertFalse(transcript["candidate_policy_precommitted_at_probe_time"])
            self.assertFalse(transcript["child_boundary_committed"])
            self.assertFalse(transcript["positive_artifact_generated"])
            self.assertTrue(transcript["root_globals_unchanged"])
            self.assertEqual(
                transcript["root_globals_before"], transcript["root_globals_after"]
            )
            for value in walk(transcript):
                self.assertNotIsInstance(value, float)
                if type(value) is str:
                    self.assertFalse(value.startswith("/Data/"))
                    self.assertFalse(value.startswith("/tmp/"))

    def test_04_checkpoint_ledgers_recompute_exactly(self):
        B = (1 << 64) // 4000
        for mode, expected in EXPECTED.items():
            _raw, _canonical, transcript = load_transcript(mode)
            records = transcript["records"]
            candidates = transcript["candidate_K_values"]
            self.assertEqual(
                KERNEL.canonical_sha256(records), expected["records_sha256"]
            )
            self.assertEqual(transcript["records_sha256"], expected["records_sha256"])
            self.assertEqual(
                transcript["candidate_K_values_sha256"],
                KERNEL.canonical_sha256(candidates),
            )
            E_input = int(transcript["input_cumulative_drop_ticks"])
            denominator = transcript["future_checkpoint_denominator"]
            cumulative = E_input
            selected_history = []
            for checkpoint_number, record in enumerate(records, 1):
                self.assertEqual(record["checkpoint_number_one_based"], checkpoint_number)
                self.assertEqual(record["checkpoint_index_zero_based"], checkpoint_number - 1)
                cap = E_input + checkpoint_number * (B - E_input) // denominator
                self.assertEqual(int(record["budget_prefix_cap_ticks"]), cap)
                self.assertEqual(int(record["E_before_ticks"]), cumulative)
                self.assertEqual(
                    int(record["prefix_slack_before_selection_ticks"]), cap - cumulative
                )
                candidate_records = record["candidate_records"]
                self.assertEqual(
                    [item["configured_K"] for item in candidate_records], candidates
                )
                drops = []
                feasible_indices = []
                for index, item in enumerate(candidate_records):
                    drop = int(item["drop_ticks"])
                    drops.append(drop)
                    self.assertEqual(item["candidate_index"], index)
                    self.assertEqual(
                        item["effective_retained_count"],
                        min(item["configured_K"], record["pretruncation_expansion_count"]),
                    )
                    self.assertEqual(
                        int(item["E_after_if_selected_ticks"]), cumulative + drop
                    )
                    feasible = cumulative + drop <= cap
                    self.assertIs(item["feasible_under_current_prefix_cap"], feasible)
                    if feasible:
                        feasible_indices.append(index)
                self.assertEqual(drops, sorted(drops, reverse=True))
                if record["status"] == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
                    self.assertTrue(feasible_indices)
                    selected = feasible_indices[0]
                    self.assertEqual(record["selected_candidate_index"], selected)
                    self.assertEqual(record["selected_K"], candidates[selected])
                    drop = int(record["selected_drop_ticks"])
                    self.assertEqual(drop, drops[selected])
                    cumulative += drop
                    self.assertEqual(int(record["E_after_ticks"]), cumulative)
                    selected_history.append(candidates[selected])
                else:
                    self.assertEqual(
                        record["status"], "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
                    )
                    self.assertFalse(feasible_indices)
                    self.assertIsNone(record["selected_candidate_index"])
                    self.assertEqual(
                        int(record["maximum_candidate_drop_excess_over_slack_ticks"]),
                        drops[-1] - (cap - cumulative),
                    )
            self.assertEqual(selected_history, transcript["selected_K_history"])
            self.assertEqual(
                KERNEL.canonical_sha256(selected_history),
                transcript["selected_K_history_sha256"],
            )
            self.assertEqual(
                str(cumulative), transcript["last_committed_cumulative_drop_ticks"]
            )

    def test_05_frozen_design_failure_summaries(self):
        for mode, expected in EXPECTED.items():
            _raw, _canonical, transcript = load_transcript(mode)
            failure = transcript["records"][-1]
            self.assertEqual(
                KERNEL.canonical_sha256(failure), expected["failure_sha256"]
            )
            self.assertEqual(transcript["failure_record_sha256"], expected["failure_sha256"])
            self.assertEqual(
                transcript["completed_checkpoint_count"], expected["completed_checkpoints"]
            )
            self.assertEqual(
                failure["checkpoint_number_one_based"], expected["failure_checkpoint"]
            )
            self.assertEqual(
                failure["minimum_effective_K_to_meet_prefix"], expected["minimum_K"]
            )
            self.assertEqual(
                failure["required_K_excess_over_policy_maximum"], expected["K_excess"]
            )
            self.assertEqual(
                transcript["observed_peak_single_expansion_terms"], expected["peak"]
            )
            self.assertEqual(
                transcript["observed_term_gate_visits_including_failure"],
                expected["visits"],
            )
            caps = transcript["proposed_policy_caps"]
            self.assertLessEqual(expected["peak"], caps["max_single_expansion_terms"])
            self.assertLessEqual(expected["visits"], caps["max_term_gate_visits"])


if __name__ == "__main__":
    unittest.main()
