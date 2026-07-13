#!/usr/bin/env python3
"""Static tests for the non-authoritative adaptive-K v5 design probe."""

from __future__ import annotations

import copy
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
    "hubbard_l8_adaptive_k_v5_design_probe",
    "hubbard_l8_adaptive_k_v5_design_probe.py",
)
V4 = load_module(
    "hubbard_l8_adaptive_k_v4_design_probe_for_v5_tests",
    "hubbard_l8_adaptive_k_v4_design_probe.py",
)
KERNEL = load_module(
    "hubbard_l8_adaptive_k_arithmetic_v2_for_v5_tests",
    "hubbard_l8_adaptive_k_arithmetic_v2.py",
)

EXPECTED = {
    "magnetization": {
        "filename": "hubbard_l8_magnetization_adaptive_k_v5_design_transcript.json",
        "v4_filename": "hubbard_l8_magnetization_adaptive_k_v4_design_transcript.json",
        "file_sha256": "384f9d0e0d3551f08765bec337286f2ab6745a63479fc07bc39bb99d685f645e",
        "candidate_sha256": "df6c7d8e7f972c1cc37816a1fb497880018b64972b6308488af8897148880b9e",
        "records_sha256": "8c6890194032d3821fd527f39f05171628610892442cf1cac953a4095a783f0f",
        "failure_sha256": "2a56eb2440e1a0f14757fc9972bfb437e05af9636c5abe88cd8d718d6665a958",
        "history_sha256": "faa53d05bb1835d16165f73b1dba86a3e5a96673a657f08baf66b6b549ae0024",
        "override_sha256": "1de8c6a4aa2ede0891f1d14585c36e834a6eba6f90c323351244025a83e0359f",
        "parent_effective_override_sha256": (
            "d6a02107c5a9aff244956b200f6057140cb998e0cff9c6e9144c4d26b2466114"
        ),
        "failure_checkpoint": 39,
        "completed_checkpoints": 38,
        "minimum_K": 521_800,
        "K_excess": 13_896,
        "peak": 714_754,
        "visits": 86_294_299,
        "new_selected_tail": [475_136, 475_136, 491_520],
        "coefficient_bits": 57,
        "product_bits": 121,
        "rounding": "127805726756259592706463222",
    },
    "double_occupancy": {
        "filename": "hubbard_l8_double_occupancy_adaptive_k_v5_design_transcript.json",
        "v4_filename": "hubbard_l8_double_occupancy_adaptive_k_v4_design_transcript.json",
        "file_sha256": "50d0f956f1e0e5fa379334be98d857882cca28e1a48644b3faf1b59711bfddd0",
        "candidate_sha256": "1870c4bb262d57c2c5e274e2ee5246e190be65e7d30959a2d77ef9a2bd756eee",
        "records_sha256": "5313834ddd9fd97c4538027da898b19354d63e385511a05028653a57a6230875",
        "failure_sha256": "88eb879eca02fc4546c045de48afd0538dffa025f75c6a3503e38551710ad4da",
        "history_sha256": "6d995ee10be6aff2d1d85df475810e21b6b9b55070d2d68937c14a7c18b56fa6",
        "override_sha256": "bc47e8b68f062348f1a73ee7be65b87f336cf8c7bcf597c566d488db54d6a83d",
        "parent_effective_override_sha256": (
            "5e10af74c19304e1a4cbe0409d9c64e3ff579daf56a1e423158fb6cec22d3614"
        ),
        "failure_checkpoint": 32,
        "completed_checkpoints": 31,
        "minimum_K": 518_097,
        "K_excess": 10_193,
        "peak": 694_872,
        "visits": 76_953_164,
        "new_selected_tail": [475_136, 475_136, 507_904, 507_904],
        "coefficient_bits": 63,
        "product_bits": 120,
        "rounding": "105466515292594861008702687",
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


class AdaptiveKV5DesignProbeTests(unittest.TestCase):
    def test_01_base_probe_is_exactly_pinned_and_injected(self):
        payload = (HERE / PROBE.BASE_PROBE_NAME).read_bytes()
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(), PROBE.EXPECTED_BASE_PROBE_SHA256
        )
        isolated = PROBE.load_verified_base(HERE)
        self.assertIsNot(isolated, V4)
        self.assertEqual(isolated._VERIFIED_SELF_SOURCE_BYTES, payload)
        self.assertEqual(isolated.M_CANDIDATES, V4.M_CANDIDATES)
        self.assertEqual(isolated.D_CANDIDATES, V4.D_CANDIDATES)

    def test_02_kernel_edge_candidate_ladders_are_exact(self):
        self.assertEqual(PROBE.M_CANDIDATES, tuple(range(65_536, 507_905, 16_384)))
        self.assertEqual(PROBE.M_CANDIDATES[:-3], V4.M_CANDIDATES)
        self.assertEqual(PROBE.D_CANDIDATES[:-3], V4.D_CANDIDATES)
        self.assertEqual(PROBE.M_CANDIDATES[-3:], PROBE.EXTENSION)
        self.assertEqual(PROBE.D_CANDIDATES[-3:], PROBE.EXTENSION)
        self.assertEqual(len(PROBE.M_CANDIDATES), 28)
        self.assertEqual(len(PROBE.D_CANDIDATES), 32)
        self.assertEqual(
            KERNEL.canonical_sha256(list(PROBE.M_CANDIDATES)),
            "df6c7d8e7f972c1cc37816a1fb497880018b64972b6308488af8897148880b9e",
        )
        self.assertEqual(
            KERNEL.canonical_sha256(list(PROBE.D_CANDIDATES)),
            "1870c4bb262d57c2c5e274e2ee5246e190be65e7d30959a2d77ef9a2bd756eee",
        )
        self.assertEqual(
            len(PROBE.D_CANDIDATES), KERNEL.RESOURCE_LIMITS["max_candidate_count"]
        )
        self.assertLess(
            PROBE.D_CANDIDATES[-1], KERNEL.RESOURCE_LIMITS["max_retained_K"]
        )

    def test_03_only_candidate_caps_are_relaxed_from_v4(self):
        expected = dict(V4.POLICY_CAPS_BASE)
        expected["max_candidate_K"] = 507_904
        expected["max_output_terms_if_successful"] = 507_904
        self.assertEqual(PROBE.POLICY_CAPS_BASE, expected)
        for key, value in PROBE.POLICY_CAPS_BASE.items():
            kernel_key = {
                "max_candidate_K": "max_retained_K",
                "max_output_terms_if_successful": "max_retained_K",
            }.get(key, key)
            if kernel_key in KERNEL.RESOURCE_LIMITS:
                self.assertLessEqual(value, KERNEL.RESOURCE_LIMITS[kernel_key])

    def test_04_configuration_is_isolated_and_output_names_are_new(self):
        old_config = copy.deepcopy(V4.MODE_CONFIG)
        old_caps = dict(V4.POLICY_CAPS_BASE)
        configured = PROBE.configured_base(HERE, "double_occupancy")
        for mode in PROBE.MODE_CONFIG:
            self.assertEqual(
                configured.MODE_CONFIG[mode]["candidates"],
                PROBE.MODE_CONFIG[mode]["candidates"],
            )
            self.assertNotEqual(
                configured.MODE_CONFIG[mode]["output_name"],
                V4.MODE_CONFIG[mode]["output_name"],
            )
        self.assertEqual(configured.POLICY_CAPS_BASE, PROBE.POLICY_CAPS_BASE)
        self.assertEqual(V4.MODE_CONFIG, old_config)
        self.assertEqual(V4.POLICY_CAPS_BASE, old_caps)

    def test_05_public_run_cannot_bypass_fresh_self_execution(self):
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

    def valid_parent_result(self, mode):
        candidates = list(PROBE.MODE_CONFIG[mode]["candidates"])
        candidate_sha = KERNEL.canonical_sha256(candidates)
        effective = PROBE.parent_effective_override(mode, candidate_sha)
        return {
            "schema_version": 1,
            "design_probe_source_sha256": PROBE.EXPECTED_BASE_PROBE_SHA256,
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_v4_higher_K_deterministic_design_probe_v1"
            ),
            "probe_generation": "v4_higher_K_458752",
            "implementation_parent_probe_relative_path": (
                "hubbard_l8_adaptive_k_v3_design_probe.py"
            ),
            "implementation_parent_probe_source_sha256": (
                PROBE.EXPECTED_GRANDPARENT_V3_PROBE_SHA256
            ),
            "implementation_parent_compiled_from_verified_bytes": True,
            "implementation_parent_module_isolated": True,
            "implementation_parent_original_fingerprint": (
                "hubbard_l8_adaptive_k_v3_extended_K_deterministic_design_probe_v1"
            ),
            "implementation_parent_original_generation": "v3_extended_K_393216",
            "implementation_base_source_sha256": (
                PROBE.EXPECTED_IMPLEMENTATION_V2_PROBE_SHA256
            ),
            "implementation_base_compiled_from_verified_bytes": True,
            "implementation_base_module_isolated": True,
            "implementation_source_chain_sha256": (
                PROBE.EXPECTED_V4_SOURCE_CHAIN_SHA256
            ),
            "candidate_K_values": candidates,
            "candidate_K_values_sha256": candidate_sha,
            "proposed_policy_caps": {
                **PROBE.POLICY_CAPS_BASE,
                "max_candidate_count": len(candidates),
            },
            "configuration_override": effective,
            "configuration_override_sha256": KERNEL.canonical_sha256(effective),
            "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
            "candidate_policy_precommitted_at_probe_time": False,
            "child_boundary_committed": False,
            "positive_artifact_generated": False,
            "root_globals_unchanged": True,
            "root_globals_before": {"sentinel": 1},
            "root_globals_after": {"sentinel": 1},
            "source_custody": {
                "hubbard_l8_adaptive_k_v3_design_probe.py": (
                    PROBE.EXPECTED_GRANDPARENT_V3_PROBE_SHA256
                ),
                "hubbard_l8_adaptive_k_v2_design_probe.py": (
                    PROBE.EXPECTED_IMPLEMENTATION_V2_PROBE_SHA256
                ),
            },
        }

    def test_06_parent_effective_and_direct_overrides_remain_distinct(self):
        fresh = PROBE.fresh_self_module()
        parent = self.valid_parent_result("magnetization")
        original_effective = dict(parent["configuration_override"])
        result = fresh.validate_and_relabel(parent, "magnetization")
        self.assertEqual(
            result["implementation_parent_effective_configuration_override"],
            original_effective,
        )
        self.assertEqual(
            result["configuration_override"]["candidate_ladder_extension"],
            list(PROBE.EXTENSION),
        )
        self.assertEqual(
            result["configuration_override"]["base_configuration_override_sha256"],
            PROBE.CANONICAL_V4_MODE["magnetization"][
                "configuration_override_sha256"
            ],
        )

    def test_07_four_layer_provenance_is_preserved_and_tamper_checked(self):
        fresh = PROBE.fresh_self_module()
        result = fresh.validate_and_relabel(
            self.valid_parent_result("double_occupancy"), "double_occupancy"
        )
        self.assertEqual(
            [item["role"] for item in result["implementation_source_layers"]],
            [
                "v5_design_probe",
                "v4_parent_probe",
                "v3_grandparent_probe",
                "v2_implementation_probe",
            ],
        )
        self.assertEqual(
            result["implementation_grandparent_probe_source_sha256"],
            PROBE.EXPECTED_GRANDPARENT_V3_PROBE_SHA256,
        )
        self.assertEqual(
            result["implementation_base_source_sha256"],
            PROBE.EXPECTED_IMPLEMENTATION_V2_PROBE_SHA256,
        )
        tamper_cases = {
            "schema_version": 2,
            "design_probe_source_sha256": "0" * 64,
            "probe_generation": "wrong",
            "implementation_parent_probe_relative_path": "wrong.py",
            "implementation_parent_original_fingerprint": "wrong",
            "implementation_parent_original_generation": "wrong",
            "implementation_source_chain_sha256": "0" * 64,
            "candidate_K_values_sha256": "0" * 64,
            "candidate_policy_precommitted_at_probe_time": True,
            "root_globals_unchanged": False,
        }
        for key, value in tamper_cases.items():
            with self.subTest(key=key):
                tampered = self.valid_parent_result("double_occupancy")
                tampered[key] = value
                with self.assertRaises(RuntimeError):
                    fresh.validate_and_relabel(tampered, "double_occupancy")

    def test_08_verified_run_uses_parent_private_path_and_propagates_resources(self):
        fresh = PROBE.fresh_self_module()
        parent = self.valid_parent_result("magnetization")
        case = self

        class Stub:
            def run(self, *_args):
                case.fail("parent public run used")

            def _run_verified(self, repo, mode):
                case.assertEqual(repo, HERE.resolve())
                case.assertEqual(mode, "magnetization")
                return parent

        original = fresh.configured_base
        fresh.configured_base = lambda _repo, _mode: Stub()
        try:
            result = fresh._run_verified(HERE, "magnetization")
            self.assertEqual(result["probe_generation"], "v5_kernel_edge_K_507904")

            class FailingStub:
                @staticmethod
                def _run_verified(_repo, _mode):
                    raise RuntimeError("resource cap sentinel")

            fresh.configured_base = lambda _repo, _mode: FailingStub()
            with self.assertRaisesRegex(RuntimeError, "resource cap sentinel"):
                fresh._run_verified(HERE, "magnetization")
        finally:
            fresh.configured_base = original

    def test_09_atomic_output_is_bounded_and_never_reuses_v4_names(self):
        for mode in PROBE.MODE_CONFIG:
            self.assertNotEqual(
                PROBE.MODE_CONFIG[mode]["output_name"],
                V4.MODE_CONFIG[mode]["output_name"],
            )
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "transcript.json"
            PROBE.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "output byte cap"):
                PROBE.write_atomic_bounded(output, b"x" * (PROBE.MAX_OUTPUT_BYTES + 1))
            self.assertEqual(output.read_bytes(), b"{}")
            self.assertEqual(list(pathlib.Path(directory).glob("*.tmp")), [])

    def test_10_scope_is_diagnostic_only(self):
        source = (HERE / PROBE.SELF_NAME).read_text()
        for forbidden in (
            "dual_screen_checker",
            "formal_witness",
            "boundary_sidecar",
            "READY_FOR_BENCHMARK",
            "traceback",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("candidate_policy_precommitted_at_probe_time", source)
        self.assertIn("child_boundary_committed", source)
        self.assertIn("positive_artifact_generated", source)

    def test_11_transcripts_are_canonical_four_layer_diagnostics(self):
        probe_sha = hashlib.sha256((HERE / PROBE.SELF_NAME).read_bytes()).hexdigest()
        self.assertEqual(
            probe_sha,
            "19ec2b54f177248b1b5a98f69afbde0cf74dd8fece66ebb742eec60f247544ec",
        )
        expected_chain = KERNEL.canonical_sha256([
            probe_sha,
            PROBE.EXPECTED_BASE_PROBE_SHA256,
            PROBE.EXPECTED_GRANDPARENT_V3_PROBE_SHA256,
            PROBE.EXPECTED_IMPLEMENTATION_V2_PROBE_SHA256,
        ])
        self.assertEqual(
            expected_chain,
            "d3f0972d24372abc4e6633ed7396bc38e94022928f299c71af19acdddd7586bd",
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
                transcript["implementation_grandparent_probe_source_sha256"],
                PROBE.EXPECTED_GRANDPARENT_V3_PROBE_SHA256,
            )
            self.assertEqual(
                transcript["implementation_base_source_sha256"],
                PROBE.EXPECTED_IMPLEMENTATION_V2_PROBE_SHA256,
            )
            self.assertEqual(
                transcript["implementation_source_chain_sha256"], expected_chain
            )
            self.assertEqual(
                KERNEL.canonical_sha256(transcript["implementation_source_layers"]),
                transcript["implementation_source_layers_sha256"],
            )
            self.assertEqual(
                transcript["implementation_source_layers_sha256"],
                "a39afa00428fa4ce3ae837983213397c9e4481ece7d9cf0c53fd33fde73bf3dc",
            )
            self.assertEqual(
                [item["sha256"] for item in transcript["implementation_source_layers"]],
                [
                    probe_sha,
                    PROBE.EXPECTED_BASE_PROBE_SHA256,
                    PROBE.EXPECTED_GRANDPARENT_V3_PROBE_SHA256,
                    PROBE.EXPECTED_IMPLEMENTATION_V2_PROBE_SHA256,
                ],
            )
            for filename, source_sha in (
                (PROBE.BASE_PROBE_NAME, PROBE.EXPECTED_BASE_PROBE_SHA256),
                (
                    "hubbard_l8_adaptive_k_v3_design_probe.py",
                    PROBE.EXPECTED_GRANDPARENT_V3_PROBE_SHA256,
                ),
                (
                    "hubbard_l8_adaptive_k_v2_design_probe.py",
                    PROBE.EXPECTED_IMPLEMENTATION_V2_PROBE_SHA256,
                ),
            ):
                self.assertEqual(transcript["source_custody"][filename], source_sha)
            self.assertEqual(
                transcript["configuration_override_sha256"], expected["override_sha256"]
            )
            self.assertEqual(
                KERNEL.canonical_sha256(transcript["configuration_override"]),
                expected["override_sha256"],
            )
            self.assertEqual(
                transcript[
                    "implementation_parent_effective_configuration_override_sha256"
                ],
                expected["parent_effective_override_sha256"],
            )
            self.assertEqual(
                KERNEL.canonical_sha256(
                    transcript["implementation_parent_effective_configuration_override"]
                ),
                expected["parent_effective_override_sha256"],
            )
            self.assertEqual(
                transcript["configuration_override"]["candidate_ladder_extension"],
                list(PROBE.EXTENSION),
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

    def test_13_frozen_failure_resource_and_kernel_edge_summaries(self):
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
            self.assertGreater(expected["minimum_K"], 507_904)
            self.assertLessEqual(expected["minimum_K"], 524_288)
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
            self.assertEqual(caps["max_candidate_K"], 507_904)
        _raw, double = load_transcript("double_occupancy")
        self.assertEqual(
            double["proposed_policy_caps"]["max_candidate_count"],
            KERNEL.RESOURCE_LIMITS["max_candidate_count"],
        )

    def test_14_v4_prefix_and_failure_handoff_are_exact(self):
        stable_top = (
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
            _raw, v5 = load_transcript(mode)
            v4 = json.loads((HERE / expected["v4_filename"]).read_bytes())
            for field in stable_top:
                self.assertEqual(v5[field], v4[field])
            committed_count = v4["completed_checkpoint_count"]
            for index in range(committed_count):
                old = dict(v4["records"][index])
                new = dict(v5["records"][index])
                old_candidates = old.pop("candidate_records")
                new_candidates = new.pop("candidate_records")
                self.assertEqual(new, old)
                self.assertEqual(
                    new_candidates[:len(v4["candidate_K_values"])], old_candidates
                )
            old_failure = v4["records"][committed_count]
            handoff = v5["records"][committed_count]
            for field in handoff_fields:
                self.assertEqual(handoff[field], old_failure[field])
            self.assertEqual(
                handoff["candidate_records"][:len(v4["candidate_K_values"])],
                old_failure["candidate_records"],
            )
            self.assertEqual(
                handoff["status"], "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
            )
            self.assertEqual(handoff["selected_K"], 475_136)
            self.assertEqual(
                v5["selected_K_history"][committed_count:],
                expected["new_selected_tail"],
            )


if __name__ == "__main__":
    unittest.main()
