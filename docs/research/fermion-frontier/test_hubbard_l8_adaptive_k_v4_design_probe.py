#!/usr/bin/env python3
"""Static tests for the non-authoritative adaptive-K v4 design probe."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


HERE = pathlib.Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PROBE = load_module(
    "hubbard_l8_adaptive_k_v4_design_probe",
    "hubbard_l8_adaptive_k_v4_design_probe.py",
)
V3 = load_module(
    "hubbard_l8_adaptive_k_v3_design_probe_for_v4_tests",
    "hubbard_l8_adaptive_k_v3_design_probe.py",
)
KERNEL = load_module(
    "hubbard_l8_adaptive_k_arithmetic_v2_for_v4_tests",
    "hubbard_l8_adaptive_k_arithmetic_v2.py",
)

EXPECTED = {
    "magnetization": {
        "filename": "hubbard_l8_magnetization_adaptive_k_v4_design_transcript.json",
        "v3_filename": "hubbard_l8_magnetization_adaptive_k_v3_design_transcript.json",
        "file_sha256": "962a3b14c5836e12d50debc82b0f4681fe167e075d4b7579766354ff2c3e79db",
        "candidate_sha256": "dca926aa22de4a5a040cafe30007b74f07bef131ecb97a3b247cdb3adb17071a",
        "records_sha256": "2f1a3d7940f788c684821317b478c28e3b2f9389705503f587c9cad5b437b102",
        "failure_sha256": "499b7b62cc085de1c31ec7b785419ad6d3799c48937f3a9459a5b3e2a9b2abc7",
        "history_sha256": "52c17264fd74185c3aa7bf1d82036e01d394b6514f9b695c51d51d0893992fb2",
        "override_sha256": "595cde3aac5071c475fb7737eb1d08844f36bd229a2f6db6f993dda18705f294",
        "failure_checkpoint": 36,
        "completed_checkpoints": 35,
        "minimum_K": 464_310,
        "K_excess": 5_558,
        "peak": 660_262,
        "visits": 73_130_963,
        "new_selected_tail": [409_600, 425_984, 442_368],
        "coefficient_bits": 57,
        "product_bits": 121,
        "rounding": "101717905738679242884894734",
    },
    "double_occupancy": {
        "filename": "hubbard_l8_double_occupancy_adaptive_k_v4_design_transcript.json",
        "v3_filename": "hubbard_l8_double_occupancy_adaptive_k_v3_design_transcript.json",
        "file_sha256": "e6f5e2299f3f892d2f24230df32a93a8acb10d49433079db500ee0102d085350",
        "candidate_sha256": "1e96d6a8a0be0b27baf12d866fd0aafce4966a1f51bb4f881898f4d1eec0734a",
        "records_sha256": "0b1cd5fd8843536865e8e40287e8a75c19e8c2f60b1786e5411616760d7582e1",
        "failure_sha256": "508d20f1289b50b9cf453d395c47ec7398fa0dfbc4621f6658c094bb865af068",
        "history_sha256": "d9d00934e13eaa2822b368aa8f4090e5e1d9afe95b17a95a9941e295485bd528",
        "override_sha256": "6176e7d026af1255b21a092b66dfbb3c7b5904741b7a5793fc7702059c8de425",
        "failure_checkpoint": 28,
        "completed_checkpoints": 27,
        "minimum_K": 461_297,
        "K_excess": 2_545,
        "peak": 591_330,
        "visits": 59_719_825,
        "new_selected_tail": [409_600, 425_984, 442_368, 458_752],
        "coefficient_bits": 63,
        "product_bits": 120,
        "rounding": "84053148756510526668921730",
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


class AdaptiveKV4DesignProbeTests(unittest.TestCase):
    def test_01_base_probe_is_exactly_pinned_and_injected(self):
        payload = (HERE / PROBE.BASE_PROBE_NAME).read_bytes()
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            PROBE.EXPECTED_BASE_PROBE_SHA256,
        )
        isolated = PROBE.load_verified_base(HERE)
        self.assertIsNot(isolated, V3)
        self.assertEqual(isolated._VERIFIED_SELF_SOURCE_BYTES, payload)
        self.assertEqual(isolated.M_CANDIDATES, V3.M_CANDIDATES)
        self.assertEqual(isolated.D_CANDIDATES, V3.D_CANDIDATES)

    def test_02_higher_candidate_ladders_are_exact(self):
        self.assertEqual(PROBE.M_CANDIDATES, tuple(range(65_536, 458_753, 16_384)))
        self.assertEqual(len(PROBE.M_CANDIDATES), 25)
        self.assertEqual(PROBE.D_CANDIDATES[:25], V3.D_CANDIDATES)
        self.assertEqual(
            PROBE.D_CANDIDATES[25:],
            (409_600, 425_984, 442_368, 458_752),
        )
        self.assertEqual(len(PROBE.D_CANDIDATES), 29)
        self.assertEqual(
            KERNEL.canonical_sha256(list(PROBE.M_CANDIDATES)),
            "dca926aa22de4a5a040cafe30007b74f07bef131ecb97a3b247cdb3adb17071a",
        )
        self.assertEqual(
            KERNEL.canonical_sha256(list(PROBE.D_CANDIDATES)),
            "1e96d6a8a0be0b27baf12d866fd0aafce4966a1f51bb4f881898f4d1eec0734a",
        )
        for candidates in (PROBE.M_CANDIDATES, PROBE.D_CANDIDATES):
            self.assertEqual(tuple(sorted(set(candidates))), candidates)
            self.assertLessEqual(len(candidates), KERNEL.RESOURCE_LIMITS["max_candidate_count"])
            self.assertLessEqual(candidates[-1], KERNEL.RESOURCE_LIMITS["max_retained_K"])

    def test_03_only_candidate_caps_are_relaxed_from_v3(self):
        expected = dict(V3.POLICY_CAPS_BASE)
        expected["max_candidate_K"] = 458_752
        expected["max_output_terms_if_successful"] = 458_752
        self.assertEqual(PROBE.POLICY_CAPS_BASE, expected)
        for key, value in PROBE.POLICY_CAPS_BASE.items():
            kernel_key = {
                "max_candidate_K": "max_retained_K",
                "max_output_terms_if_successful": "max_retained_K",
            }.get(key, key)
            if kernel_key in KERNEL.RESOURCE_LIMITS:
                self.assertLessEqual(value, KERNEL.RESOURCE_LIMITS[kernel_key])

    def test_04_configuration_is_isolated_and_v3_globals_stay_frozen(self):
        old_config = V3.copy.deepcopy(V3.MODE_CONFIG)
        old_caps = dict(V3.POLICY_CAPS_BASE)
        configured = PROBE.configured_base(HERE, "magnetization")
        self.assertEqual(
            configured.MODE_CONFIG["magnetization"]["candidates"], PROBE.M_CANDIDATES
        )
        self.assertEqual(
            configured.MODE_CONFIG["double_occupancy"]["candidates"],
            PROBE.D_CANDIDATES,
        )
        self.assertEqual(configured.POLICY_CAPS_BASE, PROBE.POLICY_CAPS_BASE)
        for mode in PROBE.MODE_CONFIG:
            self.assertNotEqual(
                configured.MODE_CONFIG[mode]["output_name"],
                V3.MODE_CONFIG[mode]["output_name"],
            )
            self.assertEqual(
                set(configured.MODE_CONFIG[mode]), set(V3.MODE_CONFIG[mode])
            )
        self.assertEqual(V3.MODE_CONFIG, old_config)
        self.assertEqual(V3.POLICY_CAPS_BASE, old_caps)

    def test_05_scope_is_diagnostic_only(self):
        source = (HERE / "hubbard_l8_adaptive_k_v4_design_probe.py").read_text()
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

    def test_06_public_run_cannot_bypass_fresh_self_execution(self):
        sentinel = {"same_byte": True}

        class Inner:
            @staticmethod
            def _run_verified(repo, mode):
                self.assertEqual(repo, HERE)
                self.assertEqual(mode, "double_occupancy")
                return sentinel

        original_bytes = PROBE._VERIFIED_SELF_SOURCE_BYTES
        original_run = PROBE._run_verified
        original_fresh = PROBE.fresh_self_module
        try:
            PROBE._VERIFIED_SELF_SOURCE_BYTES = b"forged"
            PROBE._run_verified = lambda *_args: self.fail("live _run_verified used")
            PROBE.fresh_self_module = lambda: Inner()
            self.assertIs(PROBE.run(HERE, "double_occupancy"), sentinel)
        finally:
            PROBE._VERIFIED_SELF_SOURCE_BYTES = original_bytes
            PROBE._run_verified = original_run
            PROBE.fresh_self_module = original_fresh

    def test_07_fresh_module_captures_exact_wrapper_bytes(self):
        fresh = PROBE.fresh_self_module()
        payload = (HERE / "hubbard_l8_adaptive_k_v4_design_probe.py").read_bytes()
        self.assertEqual(fresh._VERIFIED_SELF_SOURCE_BYTES, payload)
        self.assertEqual(
            hashlib.sha256(fresh._VERIFIED_SELF_SOURCE_BYTES).hexdigest(),
            hashlib.sha256(payload).hexdigest(),
        )

    def valid_parent_result(self, mode):
        candidates = list(PROBE.MODE_CONFIG[mode]["candidates"])
        return {
            "design_probe_source_sha256": PROBE.EXPECTED_BASE_PROBE_SHA256,
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_v3_extended_K_deterministic_design_probe_v1"
            ),
            "probe_generation": "v3_extended_K_393216",
            "implementation_base_source_sha256": (
                PROBE.EXPECTED_TRANSITIVE_V2_PROBE_SHA256
            ),
            "candidate_K_values": candidates,
            "candidate_K_values_sha256": KERNEL.canonical_sha256(candidates),
            "proposed_policy_caps": {
                **PROBE.POLICY_CAPS_BASE,
                "max_candidate_count": len(candidates),
            },
            "candidate_policy_precommitted_at_probe_time": False,
            "child_boundary_committed": False,
            "positive_artifact_generated": False,
            "root_globals_unchanged": True,
            "root_globals_before": {"sentinel": 1},
            "root_globals_after": {"sentinel": 1},
            "source_custody": {
                "hubbard_l8_adaptive_k_v2_design_probe.py": (
                    PROBE.EXPECTED_TRANSITIVE_V2_PROBE_SHA256
                ),
            },
        }

    def test_08_parent_result_is_checked_before_provenance_relabel(self):
        fresh = PROBE.fresh_self_module()
        parent = self.valid_parent_result("magnetization")
        result = fresh.validate_and_relabel(parent, "magnetization")
        self.assertEqual(
            result["implementation_base_source_sha256"],
            PROBE.EXPECTED_TRANSITIVE_V2_PROBE_SHA256,
        )
        self.assertEqual(
            result["implementation_parent_probe_source_sha256"],
            PROBE.EXPECTED_BASE_PROBE_SHA256,
        )
        self.assertEqual(
            result["configuration_override"]["output_name"],
            PROBE.MODE_CONFIG["magnetization"]["output_name"],
        )
        self.assertEqual(
            result["configuration_override_sha256"],
            KERNEL.canonical_sha256(result["configuration_override"]),
        )
        tamper_cases = {
            "design_probe_source_sha256": "0" * 64,
            "probe_generation": "wrong",
            "candidate_K_values_sha256": "0" * 64,
            "candidate_policy_precommitted_at_probe_time": True,
            "root_globals_unchanged": False,
        }
        for key, value in tamper_cases.items():
            with self.subTest(key=key):
                tampered = self.valid_parent_result("magnetization")
                tampered[key] = value
                with self.assertRaises(RuntimeError):
                    fresh.validate_and_relabel(tampered, "magnetization")

    def test_09_verified_run_calls_parent_private_path_and_propagates_errors(self):
        fresh = PROBE.fresh_self_module()
        parent = self.valid_parent_result("double_occupancy")
        case = self

        class Stub:
            def run(self, *_args):
                case.fail("parent public run used")

            def _run_verified(self, repo, mode):
                case.assertEqual(repo, HERE.resolve())
                case.assertEqual(mode, "double_occupancy")
                return parent

        original = fresh.configured_base
        fresh.configured_base = lambda _repo, _mode: Stub()
        try:
            result = fresh._run_verified(HERE, "double_occupancy")
            self.assertEqual(result["probe_generation"], "v4_higher_K_458752")

            class FailingStub:
                @staticmethod
                def _run_verified(_repo, _mode):
                    raise RuntimeError("resource cap sentinel")

            fresh.configured_base = lambda _repo, _mode: FailingStub()
            with self.assertRaisesRegex(RuntimeError, "resource cap sentinel"):
                fresh._run_verified(HERE, "double_occupancy")
        finally:
            fresh.configured_base = original

    def test_10_atomic_output_is_bounded_and_never_reuses_v3_names(self):
        for mode in PROBE.MODE_CONFIG:
            self.assertNotEqual(
                PROBE.MODE_CONFIG[mode]["output_name"],
                V3.MODE_CONFIG[mode]["output_name"],
            )
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "transcript.json"
            PROBE.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "output byte cap"):
                PROBE.write_atomic_bounded(output, b"x" * (PROBE.MAX_OUTPUT_BYTES + 1))
            self.assertEqual(output.read_bytes(), b"{}")
            self.assertEqual(list(pathlib.Path(directory).glob("*.tmp")), [])

    def test_11_transcripts_are_canonical_three_layer_diagnostics(self):
        probe_sha = hashlib.sha256(
            (HERE / "hubbard_l8_adaptive_k_v4_design_probe.py").read_bytes()
        ).hexdigest()
        self.assertEqual(
            probe_sha,
            "9067055bb4134d43001d5a2f05ff40c668a9d880ab11e6052193cccf80b5ca30",
        )
        expected_chain = KERNEL.canonical_sha256([
            probe_sha,
            PROBE.EXPECTED_BASE_PROBE_SHA256,
            PROBE.EXPECTED_TRANSITIVE_V2_PROBE_SHA256,
        ])
        self.assertEqual(
            expected_chain,
            "88fbf351a9e8996247f562f80ec945130436548335e2396b0774496d4e8c9be4",
        )
        for mode, expected in EXPECTED.items():
            raw, transcript = load_transcript(mode)
            self.assertLessEqual(len(raw), PROBE.MAX_OUTPUT_BYTES)
            self.assertEqual(raw, canonical_bytes(transcript))
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["file_sha256"])
            self.assertEqual(transcript["design_probe_source_sha256"], probe_sha)
            self.assertEqual(
                transcript["implementation_parent_probe_source_sha256"],
                PROBE.EXPECTED_BASE_PROBE_SHA256,
            )
            self.assertEqual(
                transcript["implementation_base_source_sha256"],
                PROBE.EXPECTED_TRANSITIVE_V2_PROBE_SHA256,
            )
            self.assertEqual(
                transcript["implementation_source_chain_sha256"], expected_chain
            )
            self.assertEqual(
                transcript["source_custody"][PROBE.BASE_PROBE_NAME],
                PROBE.EXPECTED_BASE_PROBE_SHA256,
            )
            self.assertEqual(
                transcript["source_custody"][
                    "hubbard_l8_adaptive_k_v2_design_probe.py"
                ],
                PROBE.EXPECTED_TRANSITIVE_V2_PROBE_SHA256,
            )
            self.assertEqual(
                transcript["configuration_override_sha256"],
                expected["override_sha256"],
            )
            self.assertEqual(
                KERNEL.canonical_sha256(transcript["configuration_override"]),
                expected["override_sha256"],
            )
            self.assertEqual(
                transcript["configuration_override"]["output_name"],
                PROBE.MODE_CONFIG[mode]["output_name"],
            )
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

    def test_12_checkpoint_ledgers_recompute_exactly(self):
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

    def test_13_frozen_failure_and_resource_summaries(self):
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
            self.assertEqual(caps["max_candidate_K"], 458_752)
            self.assertLess(expected["minimum_K"], 475_136)

    def test_14_v3_prefix_and_failure_handoff_are_exact(self):
        committed_stable_top = (
            "input_boundary_custody",
            "input_cumulative_drop_ticks",
            "maximum_cumulative_drop_ticks",
            "remaining_mapped_steps_including_attempt",
            "future_checkpoint_denominator",
            "prefix_cap_formula",
            "selection_rule",
            "single_propagation_and_single_ranking_per_checkpoint",
            "sequence",
            "kernel_capability_limits",
            "root_globals_before",
            "root_globals_after",
        )
        handoff_fields = (
            "checkpoint_index_zero_based",
            "checkpoint_number_one_based",
            "stage_index",
            "stage_group",
            "batch_in_stage",
            "gate_occurrence_first_zero_based",
            "gate_occurrence_last_zero_based",
            "gate_batch_sha256",
            "input_expansion_count",
            "input_expansion_sha256",
            "pretruncation_expansion_count",
            "pretruncation_expansion_sha256",
            "ranked_suffix_sha256",
            "budget_prefix_cap_ticks",
            "E_before_ticks",
            "prefix_slack_before_selection_ticks",
            "peak_live_terms_this_checkpoint",
            "peak_live_terms_cumulative",
            "term_gate_visits_increment",
            "term_gate_visits_cumulative",
            "rounding_increment_scaled_ticks_squared",
            "rounding_cumulative_scaled_ticks_squared",
            "maximum_expansion_coefficient_tick_bits",
            "maximum_product_bits",
        )
        for mode, expected in EXPECTED.items():
            _raw, v4 = load_transcript(mode)
            v3 = json.loads((HERE / expected["v3_filename"]).read_bytes())
            for field in committed_stable_top:
                self.assertEqual(v4[field], v3[field])
            committed_count = v3["completed_checkpoint_count"]
            for index in range(committed_count):
                old = dict(v3["records"][index])
                new = dict(v4["records"][index])
                old_candidates = old.pop("candidate_records")
                new_candidates = new.pop("candidate_records")
                self.assertEqual(new, old)
                self.assertEqual(
                    new_candidates[:len(v3["candidate_K_values"])], old_candidates
                )
            old_failure = v3["records"][committed_count]
            handoff = v4["records"][committed_count]
            for field in handoff_fields:
                self.assertEqual(handoff[field], old_failure[field])
            self.assertEqual(
                handoff["candidate_records"][:len(v3["candidate_K_values"])],
                old_failure["candidate_records"],
            )
            self.assertEqual(
                handoff["status"], "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
            )
            self.assertEqual(handoff["selected_K"], 409_600)
            self.assertEqual(
                v4["selected_K_history"][committed_count:],
                expected["new_selected_tail"],
            )


if __name__ == "__main__":
    unittest.main()
