#!/usr/bin/env python3
"""Static tests for the non-authoritative adaptive-K v6 design probe."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
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
    "hubbard_l8_adaptive_k_v6_design_probe",
    "hubbard_l8_adaptive_k_v6_design_probe.py",
)
V5 = load_module(
    "hubbard_l8_adaptive_k_v5_design_probe_for_v6_tests",
    "hubbard_l8_adaptive_k_v5_design_probe.py",
)
KERNEL = load_module(
    "hubbard_l8_adaptive_k_arithmetic_v2_for_v6_tests",
    "hubbard_l8_adaptive_k_arithmetic_v2.py",
)

EXPECTED_CANDIDATE_SHA256 = {
    "magnetization": (
        "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
    ),
    "double_occupancy": (
        "df55613f1fbd691f42319976d4722e614b25a8c985cdae5df9797f2e49660160"
    ),
}

EXPECTED_MAGNETIZATION = {
    "probe_sha256": "3e7f9ff0546addfaa23f351f3569b102d0c3ebb578dbc4873b042bac21070af2",
    "file_sha256": "7b0f4509a067a41da849c86c0e3e8e0ec585217d6c44a7d48aeeedc2e9aa6102",
    "records_sha256": "3ca92ec2275b2d52a4fdd62ee5921e51ff9f1c1beb9fea5fca5f4b9bd7beae04",
    "failure_sha256": "48bcd8e3363377ef32c59066c302907f87395b3dde1c0c1bc35d0c58553ec812",
    "history_sha256": "9826a280f9234143f06409cfda14d1fed98b284f41d52a4060087e62f442ed33",
    "override_sha256": "66df5707921f1fd35e525627f1f4932c07d46867f695810d15dcc0c697d0415e",
    "parent_effective_override_sha256": (
        "53fa934fc12b41d9beee125ac0bef2d5213477550753c961d942b83d32e5eaf2"
    ),
    "grandparent_effective_override_sha256": (
        "b0791ee57cbccbde1030a87b8c7a3df5195529ddcd2c91f7b761e9c09ec600dc"
    ),
    "layers_sha256": "07a45b33919829644ceaf1f3de64b89e4f28d58700b0889ec0ac430951e2415c",
    "chain_sha256": "d51828b42752953aae6eaaf0c1659cc1cca41f30452460e2dad55fab5b8ea4cc",
    "completed_checkpoints": 39,
    "failure_checkpoint": 40,
    "minimum_K": 525_859,
    "K_excess": 1_571,
    "peak": 714_754,
    "visits": 91_034_065,
    "coefficient_bits": 57,
    "product_bits": 121,
    "rounding": "135665238155550863746961978",
    "last_E": "1699615972440884",
}


def canonical_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def without_keys(value, *keys):
    output = dict(value)
    for key in keys:
        output.pop(key, None)
    return output


def walk(value):
    yield value
    if type(value) is dict:
        for key, child in value.items():
            yield key
            yield from walk(child)
    elif type(value) is list:
        for child in value:
            yield from walk(child)


class AdaptiveKV6DesignProbeTests(unittest.TestCase):
    def valid_configured_v5_result(self, mode):
        candidates = list(PROBE.MODE_CONFIG[mode]["candidates"])
        candidate_sha = PROBE.sha256(PROBE.canonical_bytes(candidates))
        v5_effective = PROBE.configured_v5_effective_override(mode, candidate_sha)
        v4_effective = PROBE.configured_v4_effective_override(mode, candidate_sha)
        parent_layers = PROBE.expected_v5_layers()
        return {
            "schema_version": 1,
            "design_probe_source_sha256": PROBE.EXPECTED_BASE_PROBE_SHA256,
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_v5_kernel_edge_K_"
                "deterministic_design_probe_v1"
            ),
            "probe_generation": "v5_kernel_edge_K_507904",
            "implementation_parent_probe_relative_path": PROBE.V4_PROBE_NAME,
            "implementation_parent_probe_source_sha256": (
                PROBE.EXPECTED_V4_PROBE_SHA256
            ),
            "implementation_parent_compiled_from_verified_bytes": True,
            "implementation_parent_module_isolated": True,
            "implementation_parent_original_fingerprint": (
                "hubbard_l8_adaptive_k_v4_higher_K_"
                "deterministic_design_probe_v1"
            ),
            "implementation_parent_original_generation": "v4_higher_K_458752",
            "implementation_parent_original_source_chain_sha256": (
                PROBE.EXPECTED_V4_SOURCE_CHAIN_SHA256
            ),
            "implementation_parent_effective_configuration_override": v4_effective,
            "implementation_parent_effective_configuration_override_sha256": (
                PROBE.sha256(PROBE.canonical_bytes(v4_effective))
            ),
            "implementation_grandparent_probe_relative_path": PROBE.V3_PROBE_NAME,
            "implementation_grandparent_probe_source_sha256": (
                PROBE.EXPECTED_V3_PROBE_SHA256
            ),
            "implementation_grandparent_compiled_from_verified_bytes": True,
            "implementation_grandparent_module_isolated": True,
            "implementation_grandparent_original_fingerprint": (
                "hubbard_l8_adaptive_k_v3_extended_K_"
                "deterministic_design_probe_v1"
            ),
            "implementation_grandparent_original_generation": (
                "v3_extended_K_393216"
            ),
            "implementation_base_source_sha256": PROBE.EXPECTED_V2_PROBE_SHA256,
            "implementation_base_compiled_from_verified_bytes": True,
            "implementation_base_module_isolated": True,
            "implementation_source_layers": parent_layers,
            "implementation_source_layers_sha256": (
                PROBE.EXPECTED_V5_SOURCE_LAYERS_SHA256
            ),
            "implementation_source_chain_sha256": (
                PROBE.EXPECTED_V5_SOURCE_CHAIN_SHA256
            ),
            "candidate_K_values": candidates,
            "candidate_K_values_sha256": candidate_sha,
            "proposed_policy_caps": {
                **PROBE.POLICY_CAPS_BASE,
                "max_candidate_count": len(candidates),
            },
            "kernel_capability_limits": {
                "max_candidate_count": PROBE.KERNEL_MAX_CANDIDATE_COUNT,
                "max_retained_K": PROBE.KERNEL_MAX_RETAINED_K,
            },
            "configuration_override": v5_effective,
            "configuration_override_sha256": PROBE.sha256(
                PROBE.canonical_bytes(v5_effective)
            ),
            "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
            "candidate_policy_precommitted_at_probe_time": False,
            "child_boundary_committed": False,
            "positive_artifact_generated": False,
            "root_globals_unchanged": True,
            "root_globals_before": {"sentinel": 1},
            "root_globals_after": {"sentinel": 1},
            "source_custody": {
                PROBE.V4_PROBE_NAME: PROBE.EXPECTED_V4_PROBE_SHA256,
                PROBE.V3_PROBE_NAME: PROBE.EXPECTED_V3_PROBE_SHA256,
                PROBE.V2_PROBE_NAME: PROBE.EXPECTED_V2_PROBE_SHA256,
            },
        }

    def test_01_v5_parent_is_exactly_pinned_and_same_byte_injected(self):
        payload = (HERE / PROBE.BASE_PROBE_NAME).read_bytes()
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(), PROBE.EXPECTED_BASE_PROBE_SHA256
        )
        isolated = PROBE.load_verified_base(HERE)
        self.assertIsNot(isolated, V5)
        self.assertEqual(isolated._VERIFIED_SELF_SOURCE_BYTES, payload)
        self.assertEqual(isolated.M_CANDIDATES, V5.M_CANDIDATES)
        self.assertEqual(isolated.D_CANDIDATES, V5.D_CANDIDATES)
        fresh = PROBE.fresh_self_module()
        self.assertEqual(
            fresh._VERIFIED_SELF_SOURCE_BYTES, (HERE / PROBE.SELF_NAME).read_bytes()
        )
        with self.assertRaisesRegex(RuntimeError, "same-byte"):
            PROBE.validate_and_relabel(
                self.valid_configured_v5_result("magnetization"), "magnetization"
            )

    def test_02_kernel_limit_candidate_ladders_are_exact(self):
        self.assertEqual(PROBE.ADDED_CANDIDATES, (524_288,))
        self.assertEqual(PROBE.M_CANDIDATES[:-1], V5.M_CANDIDATES)
        self.assertEqual(PROBE.M_CANDIDATES[-1], 524_288)
        self.assertEqual(len(PROBE.M_CANDIDATES), 29)

        expected_d = tuple(value for value in V5.D_CANDIDATES if value != 491_520)
        expected_d += (524_288,)
        self.assertEqual(PROBE.D_CANDIDATES, expected_d)
        self.assertNotIn(491_520, PROBE.D_CANDIDATES)
        self.assertEqual(PROBE.D_CANDIDATES[-2:], (507_904, 524_288))
        self.assertEqual(len(PROBE.D_CANDIDATES), 32)
        self.assertEqual(
            len(PROBE.D_CANDIDATES), KERNEL.RESOURCE_LIMITS["max_candidate_count"]
        )

        for mode, candidates in (
            ("magnetization", PROBE.M_CANDIDATES),
            ("double_occupancy", PROBE.D_CANDIDATES),
        ):
            self.assertEqual(
                KERNEL.canonical_sha256(list(candidates)),
                EXPECTED_CANDIDATE_SHA256[mode],
            )
            self.assertEqual(candidates[-1], KERNEL.RESOURCE_LIMITS["max_retained_K"])
        PROBE.validate_local_configuration()

    def test_03_only_the_two_K_caps_change_from_v5(self):
        expected = dict(V5.POLICY_CAPS_BASE)
        expected["max_candidate_K"] = 524_288
        expected["max_output_terms_if_successful"] = 524_288
        self.assertEqual(PROBE.POLICY_CAPS_BASE, expected)
        changed = {
            key
            for key in expected
            if expected[key] != V5.POLICY_CAPS_BASE[key]
        }
        self.assertEqual(
            changed, {"max_candidate_K", "max_output_terms_if_successful"}
        )
        self.assertEqual(
            PROBE.POLICY_CAPS_BASE["max_candidate_K"],
            KERNEL.RESOURCE_LIMITS["max_retained_K"],
        )

    def test_04_configuration_is_isolated_and_names_are_new(self):
        old_config = copy.deepcopy(V5.MODE_CONFIG)
        old_caps = dict(V5.POLICY_CAPS_BASE)
        configured = PROBE.configured_base(HERE, "double_occupancy")
        self.assertIsNot(configured, V5)
        for mode in PROBE.MODE_CONFIG:
            self.assertEqual(
                configured.MODE_CONFIG[mode]["candidates"],
                PROBE.MODE_CONFIG[mode]["candidates"],
            )
            self.assertEqual(
                configured.MODE_CONFIG[mode]["output_name"],
                PROBE.MODE_CONFIG[mode]["output_name"],
            )
            self.assertNotEqual(
                configured.MODE_CONFIG[mode]["output_name"],
                V5.MODE_CONFIG[mode]["output_name"],
            )
        self.assertEqual(configured.POLICY_CAPS_BASE, PROBE.POLICY_CAPS_BASE)
        self.assertEqual(V5.MODE_CONFIG, old_config)
        self.assertEqual(V5.POLICY_CAPS_BASE, old_caps)

    def test_05_public_run_always_uses_a_fresh_self_module(self):
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
            PROBE._run_verified = lambda *_args: self.fail("live private path used")
            PROBE.fresh_self_module = lambda: Inner()
            self.assertIs(PROBE.run(HERE, "magnetization"), sentinel)
        finally:
            PROBE._VERIFIED_SELF_SOURCE_BYTES = original_bytes
            PROBE._run_verified = original_run
            PROBE.fresh_self_module = original_fresh

    def test_06_private_parent_path_and_resource_exception_identity(self):
        fresh = PROBE.fresh_self_module()
        parent = self.valid_configured_v5_result("magnetization")
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
            self.assertEqual(result["probe_generation"], "v6_kernel_limit_K_524288")

            resource_error = RuntimeError("resource cap sentinel")

            class FailingStub:
                @staticmethod
                def _run_verified(_repo, _mode):
                    raise resource_error

            fresh.configured_base = lambda _repo, _mode: FailingStub()
            with self.assertRaises(RuntimeError) as caught:
                fresh._run_verified(HERE, "magnetization")
            self.assertIs(caught.exception, resource_error)
        finally:
            fresh.configured_base = original

    def test_07_three_override_layers_are_distinct_and_exact(self):
        mode = "double_occupancy"
        fresh = PROBE.fresh_self_module()
        parent = self.valid_configured_v5_result(mode)
        configured_v5 = copy.deepcopy(parent["configuration_override"])
        configured_v4 = copy.deepcopy(
            parent["implementation_parent_effective_configuration_override"]
        )
        result = fresh.validate_and_relabel(parent, mode)

        direct_v6 = result["configuration_override"]
        self.assertEqual(
            direct_v6,
            PROBE.direct_v6_override(
                mode, EXPECTED_CANDIDATE_SHA256["double_occupancy"]
            ),
        )
        self.assertEqual(direct_v6["candidate_ladder_added"], [524_288])
        self.assertEqual(direct_v6["candidate_ladder_removed"], [491_520])
        self.assertEqual(
            direct_v6["base_configuration_override_sha256"],
            PROBE.CANONICAL_V5_MODE[mode]["configuration_override_sha256"],
        )
        self.assertEqual(
            result["implementation_parent_effective_configuration_override"],
            configured_v5,
        )
        self.assertEqual(
            configured_v5["base_configuration_override_sha256"],
            PROBE.CANONICAL_V4_MODE[mode]["configuration_override_sha256"],
        )
        self.assertEqual(
            result["implementation_grandparent_effective_configuration_override"],
            configured_v4,
        )
        self.assertNotIn("base_configuration_override_sha256", configured_v4)
        self.assertNotEqual(direct_v6, configured_v5)
        self.assertNotEqual(configured_v5, configured_v4)
        for value, digest_key in (
            (direct_v6, "configuration_override_sha256"),
            (
                configured_v5,
                "implementation_parent_effective_configuration_override_sha256",
            ),
            (
                configured_v4,
                "implementation_grandparent_effective_configuration_override_sha256",
            ),
        ):
            self.assertEqual(PROBE.sha256(PROBE.canonical_bytes(value)), result[digest_key])

    def test_08_five_layer_provenance_and_tamper_checks(self):
        fresh = PROBE.fresh_self_module()
        result = fresh.validate_and_relabel(
            self.valid_configured_v5_result("double_occupancy"), "double_occupancy"
        )
        layers = result["implementation_source_layers"]
        self.assertEqual(
            [item["role"] for item in layers],
            [
                "v6_design_probe",
                "v5_parent_probe",
                "v4_grandparent_probe",
                "v3_great_grandparent_probe",
                "v2_implementation_probe",
            ],
        )
        self.assertEqual(
            [item["sha256"] for item in layers][1:],
            [
                PROBE.EXPECTED_BASE_PROBE_SHA256,
                PROBE.EXPECTED_V4_PROBE_SHA256,
                PROBE.EXPECTED_V3_PROBE_SHA256,
                PROBE.EXPECTED_V2_PROBE_SHA256,
            ],
        )
        self.assertEqual(
            result["implementation_source_layers_sha256"],
            PROBE.sha256(PROBE.canonical_bytes(layers)),
        )
        self.assertEqual(
            result["implementation_source_chain_sha256"],
            PROBE.sha256(
                PROBE.canonical_bytes([item["sha256"] for item in layers])
            ),
        )
        for filename, digest in (
            (PROBE.BASE_PROBE_NAME, PROBE.EXPECTED_BASE_PROBE_SHA256),
            (PROBE.V4_PROBE_NAME, PROBE.EXPECTED_V4_PROBE_SHA256),
            (PROBE.V3_PROBE_NAME, PROBE.EXPECTED_V3_PROBE_SHA256),
            (PROBE.V2_PROBE_NAME, PROBE.EXPECTED_V2_PROBE_SHA256),
        ):
            self.assertEqual(result["source_custody"][filename], digest)

        def set_value(key, value):
            return lambda item: item.__setitem__(key, value)

        tamper_cases = (
            ("schema", set_value("schema_version", 2)),
            ("identity", set_value("design_probe_source_sha256", "0" * 64)),
            ("fingerprint", set_value("transcript_fingerprint", "wrong")),
            ("generation", set_value("probe_generation", "wrong")),
            (
                "parent path",
                set_value("implementation_parent_probe_relative_path", "wrong.py"),
            ),
            (
                "parent flag",
                set_value("implementation_parent_module_isolated", False),
            ),
            (
                "layers",
                lambda item: item["implementation_source_layers"][0].__setitem__(
                    "sha256", "0" * 64
                ),
            ),
            (
                "layers digest",
                set_value("implementation_source_layers_sha256", "0" * 64),
            ),
            (
                "chain digest",
                set_value("implementation_source_chain_sha256", "0" * 64),
            ),
            ("candidate digest", set_value("candidate_K_values_sha256", "0" * 64)),
            (
                "configured v5 override",
                lambda item: item["configuration_override"].__setitem__(
                    "max_candidate_K", 507_904
                ),
            ),
            (
                "embedded v4 override",
                lambda item: item[
                    "implementation_parent_effective_configuration_override"
                ].__setitem__("max_candidate_K", 507_904),
            ),
            (
                "kernel capability",
                lambda item: item["kernel_capability_limits"].__setitem__(
                    "max_retained_K", 507_904
                ),
            ),
            ("diagnostic authority", set_value("positive_artifact_generated", True)),
            ("globals", set_value("root_globals_unchanged", False)),
            (
                "custody",
                lambda item: item["source_custody"].__setitem__(
                    PROBE.V4_PROBE_NAME, "0" * 64
                ),
            ),
        )
        for label, mutate in tamper_cases:
            with self.subTest(label=label):
                tampered = self.valid_configured_v5_result("double_occupancy")
                mutate(tampered)
                with self.assertRaises(RuntimeError):
                    fresh.validate_and_relabel(tampered, "double_occupancy")

    def test_09_atomic_output_is_exact_bounded_and_failure_preserving(self):
        for mode in PROBE.MODE_CONFIG:
            self.assertNotEqual(
                PROBE.MODE_CONFIG[mode]["output_name"],
                V5.MODE_CONFIG[mode]["output_name"],
            )
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "transcript.json"
            PROBE.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "exact bytes"):
                PROBE.write_atomic_bounded(output, bytearray(b"[]"))
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "output byte cap"):
                PROBE.write_atomic_bounded(output, b"x" * (PROBE.MAX_OUTPUT_BYTES + 1))
            self.assertEqual(output.read_bytes(), b"{}")
            self.assertEqual(list(pathlib.Path(directory).glob("*.tmp")), [])

    def test_10_scope_and_synthetic_results_are_diagnostic_only(self):
        source = (HERE / PROBE.SELF_NAME).read_text()
        for forbidden in (
            "dual_screen_checker",
            "formal_witness",
            "boundary_sidecar",
            "READY_FOR_BENCHMARK",
            "traceback",
        ):
            self.assertNotIn(forbidden, source)
        fresh = PROBE.fresh_self_module()
        for mode in PROBE.MODE_CONFIG:
            result = fresh.validate_and_relabel(
                self.valid_configured_v5_result(mode), mode
            )
            self.assertEqual(
                result["status"], "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS"
            )
            self.assertFalse(result["candidate_policy_precommitted_at_probe_time"])
            self.assertFalse(result["child_boundary_committed"])
            self.assertFalse(result["positive_artifact_generated"])

    def test_11_magnetization_v5_prefix_when_canonical_transcript_exists(self):
        mode = "magnetization"
        v6_path = HERE / PROBE.MODE_CONFIG[mode]["output_name"]
        if not v6_path.exists():
            self.skipTest(
                "TODO: pin canonical v6 magnetization summaries after generation"
            )

        v6_raw = v6_path.read_bytes()
        v6 = json.loads(v6_raw)
        v5_path = HERE / V5.MODE_CONFIG[mode]["output_name"]
        v5 = json.loads(v5_path.read_bytes())
        self.assertEqual(v6_raw, canonical_bytes(v6))
        self.assertLessEqual(len(v6_raw), PROBE.MAX_OUTPUT_BYTES)
        self.assertEqual(
            hashlib.sha256((HERE / PROBE.SELF_NAME).read_bytes()).hexdigest(),
            EXPECTED_MAGNETIZATION["probe_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(v6_raw).hexdigest(),
            EXPECTED_MAGNETIZATION["file_sha256"],
        )
        self.assertEqual(
            v6["design_probe_source_sha256"],
            EXPECTED_MAGNETIZATION["probe_sha256"],
        )
        self.assertEqual(
            v6["candidate_K_values"], list(PROBE.MODE_CONFIG[mode]["candidates"])
        )
        self.assertEqual(
            v6["candidate_K_values_sha256"], EXPECTED_CANDIDATE_SHA256[mode]
        )
        self.assertEqual(
            PROBE.sha256(PROBE.canonical_bytes(v6["implementation_source_layers"])),
            EXPECTED_MAGNETIZATION["layers_sha256"],
        )
        self.assertEqual(
            v6["implementation_source_layers_sha256"],
            EXPECTED_MAGNETIZATION["layers_sha256"],
        )
        self.assertEqual(
            PROBE.sha256(
                PROBE.canonical_bytes(
                    [item["sha256"] for item in v6["implementation_source_layers"]]
                )
            ),
            EXPECTED_MAGNETIZATION["chain_sha256"],
        )
        self.assertEqual(
            v6["implementation_source_chain_sha256"],
            EXPECTED_MAGNETIZATION["chain_sha256"],
        )
        for value, digest_key, expected_key in (
            (v6["configuration_override"], "configuration_override_sha256", "override_sha256"),
            (
                v6["implementation_parent_effective_configuration_override"],
                "implementation_parent_effective_configuration_override_sha256",
                "parent_effective_override_sha256",
            ),
            (
                v6["implementation_grandparent_effective_configuration_override"],
                "implementation_grandparent_effective_configuration_override_sha256",
                "grandparent_effective_override_sha256",
            ),
        ):
            self.assertEqual(
                PROBE.sha256(PROBE.canonical_bytes(value)),
                EXPECTED_MAGNETIZATION[expected_key],
            )
            self.assertEqual(v6[digest_key], EXPECTED_MAGNETIZATION[expected_key])
        self.assertEqual(
            v6["status"], "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS"
        )
        self.assertFalse(v6["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(v6["child_boundary_committed"])
        self.assertFalse(v6["positive_artifact_generated"])
        for value in walk(v6):
            self.assertNotIsInstance(value, float)
            if type(value) is str:
                self.assertFalse(value.startswith("/Data/"))
                self.assertFalse(value.startswith("/tmp/"))

        committed = v5["completed_checkpoint_count"]
        self.assertGreaterEqual(v6["completed_checkpoint_count"], committed + 1)
        self.assertEqual(
            v6["selected_K_history"][:committed],
            v5["selected_K_history"][:committed],
        )
        for index in range(committed):
            old = v5["records"][index]
            new = v6["records"][index]
            self.assertEqual(
                without_keys(new, "candidate_records"),
                without_keys(old, "candidate_records"),
            )
            self.assertEqual(
                new["candidate_records"][:len(v5["candidate_K_values"])],
                old["candidate_records"],
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
        old_failure = v5["records"][committed]
        handoff = v6["records"][committed]
        for field in handoff_fields:
            self.assertEqual(handoff[field], old_failure[field])
        self.assertEqual(
            handoff["candidate_records"][:len(v5["candidate_K_values"])],
            old_failure["candidate_records"],
        )
        self.assertEqual(handoff["status"], "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED")
        self.assertEqual(handoff["selected_K"], 524_288)

        failure = v6["records"][-1]
        self.assertEqual(
            v6["completed_checkpoint_count"],
            EXPECTED_MAGNETIZATION["completed_checkpoints"],
        )
        self.assertEqual(
            failure["checkpoint_number_one_based"],
            EXPECTED_MAGNETIZATION["failure_checkpoint"],
        )
        self.assertEqual(
            failure["minimum_effective_K_to_meet_prefix"],
            EXPECTED_MAGNETIZATION["minimum_K"],
        )
        self.assertEqual(
            failure["required_K_excess_over_policy_maximum"],
            EXPECTED_MAGNETIZATION["K_excess"],
        )
        self.assertEqual(
            v6["observed_peak_single_expansion_terms"],
            EXPECTED_MAGNETIZATION["peak"],
        )
        self.assertEqual(
            v6["observed_term_gate_visits_including_failure"],
            EXPECTED_MAGNETIZATION["visits"],
        )
        self.assertEqual(
            v6["observed_maximum_expansion_coefficient_tick_bits"],
            EXPECTED_MAGNETIZATION["coefficient_bits"],
        )
        self.assertEqual(
            v6["observed_maximum_product_bits"],
            EXPECTED_MAGNETIZATION["product_bits"],
        )
        self.assertEqual(
            v6["observed_rounding_cumulative_scaled_ticks_squared"],
            EXPECTED_MAGNETIZATION["rounding"],
        )
        self.assertEqual(
            v6["last_committed_cumulative_drop_ticks"],
            EXPECTED_MAGNETIZATION["last_E"],
        )
        self.assertEqual(
            PROBE.sha256(PROBE.canonical_bytes(failure)),
            EXPECTED_MAGNETIZATION["failure_sha256"],
        )
        self.assertEqual(
            v6["failure_record_sha256"],
            EXPECTED_MAGNETIZATION["failure_sha256"],
        )

    def test_12_magnetization_checkpoint_ledger_recomputes_exactly(self):
        path = HERE / PROBE.MODE_CONFIG["magnetization"]["output_name"]
        raw = path.read_bytes()
        transcript = json.loads(raw)
        records = transcript["records"]
        candidates = transcript["candidate_K_values"]
        self.assertEqual(
            PROBE.sha256(PROBE.canonical_bytes(records)),
            EXPECTED_MAGNETIZATION["records_sha256"],
        )
        self.assertEqual(
            transcript["records_sha256"],
            EXPECTED_MAGNETIZATION["records_sha256"],
        )

        maximum_drop = (1 << 64) // 4000
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
                self.assertEqual(int(record["selected_drop_ticks"]), drops[selected])
                cumulative += drops[selected]
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
            PROBE.sha256(PROBE.canonical_bytes(selected_history)),
            EXPECTED_MAGNETIZATION["history_sha256"],
        )
        self.assertEqual(
            transcript["selected_K_history_sha256"],
            EXPECTED_MAGNETIZATION["history_sha256"],
        )
        self.assertEqual(str(cumulative), EXPECTED_MAGNETIZATION["last_E"])

    def test_13_double_occupancy_resource_failure_has_no_canonical_output(self):
        mode = "double_occupancy"
        output_name = PROBE.MODE_CONFIG[mode]["output_name"]
        self.assertNotEqual(output_name, V5.MODE_CONFIG[mode]["output_name"])
        self.assertFalse(
            (HERE / output_name).exists(),
            "resource-failed D replay must not leave a canonical transcript",
        )

    @unittest.skipUnless(
        os.environ.get("RUN_HUBBARD_L8_V6_RESOURCE_REPLAY") == "1",
        "expensive deterministic D resource-failure replay is opt-in",
    )
    def test_14_double_occupancy_real_resource_failure_is_opt_in(self):
        output = HERE / PROBE.MODE_CONFIG["double_occupancy"]["output_name"]
        self.assertFalse(output.exists())
        with self.assertRaisesRegex(
            RuntimeError, "design policy live-term cap exceeded"
        ):
            PROBE.run(HERE, "double_occupancy")
        self.assertFalse(output.exists())

    @unittest.skipUnless(
        os.environ.get("RUN_HUBBARD_L8_V6_RESOURCE_MEASUREMENT") == "1",
        "expensive D kernel-cap resource measurement is opt-in",
    )
    def test_15_double_occupancy_kernel_cap_measurement_is_opt_in(self):
        measurement = V5.fresh_self_module()
        measurement.MODE_CONFIG = copy.deepcopy(measurement.MODE_CONFIG)
        measurement.MODE_CONFIG["double_occupancy"]["candidates"] = (
            PROBE.D_CANDIDATES
        )
        measurement.MODE_CONFIG["double_occupancy"]["output_name"] = (
            "noncanonical_v6_double_occupancy_resource_measurement.json"
        )
        measurement.POLICY_CAPS_BASE = dict(PROBE.POLICY_CAPS_BASE)
        measurement.POLICY_CAPS_BASE["max_single_expansion_terms"] = (
            KERNEL.RESOURCE_LIMITS["max_single_expansion_terms"]
        )
        measurement.POLICY_CAPS_BASE["max_digest_terms"] = (
            KERNEL.RESOURCE_LIMITS["max_digest_terms"]
        )

        result = measurement._run_verified(HERE, "double_occupancy")
        failure = result["records"][-1]
        self.assertEqual(result["completed_checkpoint_count"], 32)
        self.assertEqual(result["selected_K_history"][-1], 524_288)
        self.assertEqual(failure["checkpoint_number_one_based"], 33)
        self.assertEqual(failure["pretruncation_expansion_count"], 825_000)
        self.assertEqual(failure["minimum_effective_K_to_meet_prefix"], 553_717)
        self.assertEqual(failure["required_K_excess_over_policy_maximum"], 29_429)
        self.assertEqual(result["observed_peak_single_expansion_terms"], 825_000)
        self.assertEqual(
            result["observed_term_gate_visits_including_failure"], 82_050_350
        )


if __name__ == "__main__":
    unittest.main()
