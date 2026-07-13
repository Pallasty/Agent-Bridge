#!/usr/bin/env python3
"""Static tests for the non-authoritative adaptive-K v3 design probe."""

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
    "hubbard_l8_adaptive_k_v3_design_probe",
    "hubbard_l8_adaptive_k_v3_design_probe.py",
)
V2 = load_module(
    "hubbard_l8_adaptive_k_v2_design_probe_for_v3_tests",
    "hubbard_l8_adaptive_k_v2_design_probe.py",
)
KERNEL = load_module(
    "hubbard_l8_adaptive_k_arithmetic_v2_for_v3_tests",
    "hubbard_l8_adaptive_k_arithmetic_v2.py",
)

EXPECTED = {
    "magnetization": {
        "filename": "hubbard_l8_magnetization_adaptive_k_v3_design_transcript.json",
        "v2_filename": "hubbard_l8_magnetization_adaptive_k_v2_design_transcript.json",
        "file_sha256": "8ac6f010a136ace8f1d5be73e0d076c7090e4ee7d70adef86ae72c0782a2703e",
        "candidate_sha256": "e75d0f271a169dbdc7818025d4e7a6753ca032c49967d5df32f71583da04b4aa",
        "records_sha256": "148f5bea8b3f890a257531e02946e586d825aba6802ba147d3e68a8ff4c5ec78",
        "failure_sha256": "1359c1ed7dafc795fae35160e192739441d81febfe4da72ce955de4c2927c6f4",
        "history_sha256": "b40b0c5b429d7db40f811fa06906ea7f3570dda29e844180d4ada97f4e07ff96",
        "failure_checkpoint": 33,
        "completed_checkpoints": 32,
        "minimum_K": 405_291,
        "K_excess": 12_075,
        "peak": 550_806,
        "visits": 61_421_993,
        "old_failure_selected_K": 344_064,
        "coefficient_bits": 57,
        "product_bits": 121,
        "rounding": "77759026235362785437379075",
    },
    "double_occupancy": {
        "filename": "hubbard_l8_double_occupancy_adaptive_k_v3_design_transcript.json",
        "v2_filename": "hubbard_l8_double_occupancy_adaptive_k_v2_design_transcript.json",
        "file_sha256": "263636de9e788bde4ad0b85f872fcfa22fae9ac73a5029af4c81383360584d90",
        "candidate_sha256": "cef955fb3d8fc87ead2ee9473e136ce38039f7d2c3b17cc9c08d5a496b00bebe",
        "records_sha256": "d2f5ba406ede7a4d638e2a3b6b3ce770bf0053bcd336c88f692eb4147a9b8fa1",
        "failure_sha256": "e09cd47557fd6d48d03d1114da729fedc632f5cb208c39c94b1959f77f65e203",
        "history_sha256": "83bcc8376d16f54c3f3d421f5e2ef346158b34474b2a22941cdafb74581e73d9",
        "failure_checkpoint": 24,
        "completed_checkpoints": 23,
        "minimum_K": 397_750,
        "K_excess": 4_534,
        "peak": 525_968,
        "visits": 44_079_570,
        "old_failure_selected_K": 360_448,
        "coefficient_bits": 63,
        "product_bits": 120,
        "rounding": "63635410048435642569805475",
    },
}


def canonical_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def load_transcript(mode):
    expected = EXPECTED[mode]
    raw = (HERE / expected["filename"]).read_bytes()
    return raw, json.loads(raw)


def walk(value):
    yield value
    if type(value) is dict:
        for key, child in value.items():
            yield key
            yield from walk(child)
    elif type(value) is list:
        for child in value:
            yield from walk(child)


class AdaptiveKV3DesignProbeTests(unittest.TestCase):
    def test_01_base_probe_is_exactly_pinned(self):
        payload = (HERE / PROBE.BASE_PROBE_NAME).read_bytes()
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            PROBE.EXPECTED_BASE_PROBE_SHA256,
        )
        isolated = PROBE.load_verified_base(HERE)
        self.assertIsNot(isolated, V2)
        self.assertEqual(isolated.M_CANDIDATES, V2.M_CANDIDATES)
        self.assertEqual(isolated.D_CANDIDATES, V2.D_CANDIDATES)

    def test_02_extended_candidate_ladders_are_exact(self):
        self.assertEqual(PROBE.M_CANDIDATES, tuple(range(65_536, 393_217, 16_384)))
        self.assertEqual(len(PROBE.M_CANDIDATES), 21)
        self.assertEqual(PROBE.D_CANDIDATES[:21], V2.D_CANDIDATES)
        self.assertEqual(
            PROBE.D_CANDIDATES[21:],
            (344_064, 360_448, 376_832, 393_216),
        )
        self.assertEqual(len(PROBE.D_CANDIDATES), 25)
        for candidates in (PROBE.M_CANDIDATES, PROBE.D_CANDIDATES):
            self.assertEqual(tuple(sorted(set(candidates))), candidates)
            self.assertLessEqual(len(candidates), KERNEL.RESOURCE_LIMITS["max_candidate_count"])
            self.assertLessEqual(candidates[-1], KERNEL.RESOURCE_LIMITS["max_retained_K"])

    def test_03_only_candidate_caps_are_relaxed_from_v2(self):
        expected = dict(V2.POLICY_CAPS_BASE)
        expected["max_candidate_K"] = 393_216
        expected["max_output_terms_if_successful"] = 393_216
        self.assertEqual(PROBE.POLICY_CAPS_BASE, expected)
        for key, value in PROBE.POLICY_CAPS_BASE.items():
            kernel_key = {
                "max_candidate_K": "max_retained_K",
                "max_output_terms_if_successful": "max_retained_K",
            }.get(key, key)
            if kernel_key in KERNEL.RESOURCE_LIMITS:
                self.assertLessEqual(value, KERNEL.RESOURCE_LIMITS[kernel_key])

    def test_04_configuration_is_isolated_and_v2_globals_stay_frozen(self):
        v2_m = V2.CONFIG["magnetization"]["candidates"]
        v2_d = V2.CONFIG["double_occupancy"]["candidates"]
        v2_caps = dict(V2.POLICY_CAPS_BASE)
        configured = PROBE.configured_base(HERE, "magnetization")
        self.assertEqual(
            configured.CONFIG["magnetization"]["candidates"], PROBE.M_CANDIDATES
        )
        self.assertEqual(
            configured.CONFIG["double_occupancy"]["candidates"], PROBE.D_CANDIDATES
        )
        self.assertEqual(configured.POLICY_CAPS_BASE, PROBE.POLICY_CAPS_BASE)
        self.assertEqual(V2.CONFIG["magnetization"]["candidates"], v2_m)
        self.assertEqual(V2.CONFIG["double_occupancy"]["candidates"], v2_d)
        self.assertEqual(V2.POLICY_CAPS_BASE, v2_caps)

    def test_05_scope_is_diagnostic_only(self):
        source = (HERE / "hubbard_l8_adaptive_k_v3_design_probe.py").read_text()
        for forbidden in (
            "dual_screen_checker",
            "formal_witness",
            "boundary_sidecar",
            "READY_FOR_BENCHMARK",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("candidate_policy_precommitted_at_probe_time", source)
        self.assertIn("child_boundary_committed", source)
        self.assertIn("positive_artifact_generated", source)

    def test_06_verified_loader_rejects_path_aliases_and_unpinned_sources(self):
        configured = PROBE.configured_base(HERE, "double_occupancy")
        with self.assertRaisesRegex(RuntimeError, "must be a Path"):
            configured.load_module("bad", str(HERE / configured.KERNEL_NAME))
        with self.assertRaisesRegex(RuntimeError, "outside the verified source set"):
            configured.load_module("bad", pathlib.Path("/tmp") / configured.KERNEL_NAME)
        with self.assertRaisesRegex(RuntimeError, "outside the verified source set"):
            configured.load_module("bad", HERE / "unknown.py")

    def test_07_public_run_fresh_executes_same_wrapper_bytes(self):
        fresh = PROBE.fresh_self_module()
        self.assertIsInstance(fresh._VERIFIED_SELF_SOURCE_BYTES, bytes)
        self.assertEqual(
            hashlib.sha256(fresh._VERIFIED_SELF_SOURCE_BYTES).hexdigest(),
            hashlib.sha256(
                (HERE / "hubbard_l8_adaptive_k_v3_design_probe.py").read_bytes()
            ).hexdigest(),
        )

    def test_08_public_run_cannot_bypass_fresh_self_execution(self):
        sentinel = {"same_byte": True}

        class Inner:
            @staticmethod
            def _run_verified(repo, mode):
                self.assertEqual(repo, HERE)
                self.assertEqual(mode, "magnetization")
                return sentinel

        original_bytes = PROBE._VERIFIED_SELF_SOURCE_BYTES
        original_run = PROBE._run_verified
        original_fresh = PROBE.fresh_self_module
        try:
            PROBE._VERIFIED_SELF_SOURCE_BYTES = b"forged"
            PROBE._run_verified = lambda *_args: self.fail("live _run_verified used")
            PROBE.fresh_self_module = lambda: Inner()
            self.assertIs(PROBE.run(HERE, "magnetization"), sentinel)
        finally:
            PROBE._VERIFIED_SELF_SOURCE_BYTES = original_bytes
            PROBE._run_verified = original_run
            PROBE.fresh_self_module = original_fresh

    def test_09_transcripts_are_canonical_same_byte_diagnostics(self):
        probe_sha = hashlib.sha256(
            (HERE / "hubbard_l8_adaptive_k_v3_design_probe.py").read_bytes()
        ).hexdigest()
        self.assertEqual(
            probe_sha,
            "cf0c1a6cc64011bb98f07a0dc97495e4c3278e89773e4b94764483e8a387d066",
        )
        for mode, expected in EXPECTED.items():
            raw, transcript = load_transcript(mode)
            self.assertEqual(raw, canonical_bytes(transcript))
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["file_sha256"])
            self.assertEqual(transcript["design_probe_source_sha256"], probe_sha)
            self.assertEqual(
                transcript["implementation_base_source_sha256"],
                PROBE.EXPECTED_BASE_PROBE_SHA256,
            )
            self.assertEqual(
                transcript["source_custody"][PROBE.BASE_PROBE_NAME],
                PROBE.EXPECTED_BASE_PROBE_SHA256,
            )
            self.assertTrue(transcript["implementation_base_compiled_from_verified_bytes"])
            self.assertTrue(transcript["implementation_base_module_isolated"])
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

    def test_10_checkpoint_ledgers_recompute_exactly(self):
        maximum_drop = (1 << 64) // 4000
        for mode, expected in EXPECTED.items():
            _raw, transcript = load_transcript(mode)
            records = transcript["records"]
            candidates = transcript["candidate_K_values"]
            self.assertEqual(candidates, list(PROBE.MODE_CONFIG[mode]["candidates"]))
            self.assertEqual(
                KERNEL.canonical_sha256(candidates), expected["candidate_sha256"]
            )
            self.assertEqual(
                transcript["candidate_K_values_sha256"], expected["candidate_sha256"]
            )
            self.assertEqual(KERNEL.canonical_sha256(records), expected["records_sha256"])
            self.assertEqual(transcript["records_sha256"], expected["records_sha256"])
            E_input = int(transcript["input_cumulative_drop_ticks"])
            denominator = transcript["future_checkpoint_denominator"]
            cumulative = E_input
            selected_history = []
            for checkpoint_number, record in enumerate(records, 1):
                self.assertEqual(record["checkpoint_number_one_based"], checkpoint_number)
                self.assertEqual(record["checkpoint_index_zero_based"], checkpoint_number - 1)
                cap = E_input + checkpoint_number * (maximum_drop - E_input) // denominator
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
                KERNEL.canonical_sha256(selected_history), expected["history_sha256"]
            )
            self.assertEqual(
                transcript["selected_K_history_sha256"], expected["history_sha256"]
            )
            self.assertEqual(
                str(cumulative), transcript["last_committed_cumulative_drop_ticks"]
            )

    def test_11_frozen_failure_and_resource_summaries(self):
        for mode, expected in EXPECTED.items():
            _raw, transcript = load_transcript(mode)
            failure = transcript["records"][-1]
            self.assertEqual(KERNEL.canonical_sha256(failure), expected["failure_sha256"])
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
            self.assertEqual(
                transcript["observed_maximum_expansion_coefficient_tick_bits"],
                expected["coefficient_bits"],
            )
            self.assertEqual(
                transcript["observed_maximum_product_bits"], expected["product_bits"]
            )
            self.assertEqual(
                transcript["observed_rounding_cumulative_scaled_ticks_squared"],
                expected["rounding"],
            )
            caps = transcript["proposed_policy_caps"]
            self.assertLessEqual(expected["peak"], caps["max_single_expansion_terms"])
            self.assertLessEqual(expected["visits"], caps["max_term_gate_visits"])
            self.assertEqual(caps["max_candidate_K"], 393_216)

    def test_12_v2_committed_prefix_and_failure_handoff_are_exact(self):
        stable_fields = (
            "checkpoint_index_zero_based",
            "checkpoint_number_one_based",
            "stage_index",
            "stage_group",
            "batch_in_stage",
            "gate_batch_sha256",
            "input_expansion_count",
            "input_expansion_sha256",
            "pretruncation_expansion_count",
            "pretruncation_expansion_sha256",
            "ranked_suffix_sha256",
            "budget_prefix_cap_ticks",
            "E_before_ticks",
            "prefix_slack_before_selection_ticks",
            "selected_K",
            "selected_drop_ticks",
            "selected_dropped_terms_sha256",
            "retained_expansion_sha256",
            "E_after_ticks",
        )
        for mode, expected in EXPECTED.items():
            _raw, v3 = load_transcript(mode)
            v2 = json.loads((HERE / expected["v2_filename"]).read_bytes())
            committed_count = v2["completed_checkpoint_count"]
            for index in range(committed_count):
                old = v2["records"][index]
                new = v3["records"][index]
                for field in stable_fields:
                    self.assertEqual(new[field], old[field])
                self.assertEqual(
                    new["candidate_records"][:len(v2["candidate_K_values"])],
                    old["candidate_records"],
                )
            handoff = v3["records"][committed_count]
            self.assertEqual(
                handoff["status"], "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
            )
            self.assertEqual(handoff["selected_K"], expected["old_failure_selected_K"])
            if mode == "double_occupancy":
                candidate_344064 = next(
                    item for item in handoff["candidate_records"]
                    if item["configured_K"] == 344_064
                )
                self.assertFalse(
                    candidate_344064["feasible_under_current_prefix_cap"]
                )


if __name__ == "__main__":
    unittest.main()
