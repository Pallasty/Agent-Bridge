#!/usr/bin/env python3
"""Static, synthetic and opt-in tests for the four-gate K=540672 screen."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import types
import unittest


HERE = pathlib.Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module(
    "hubbard_l8_adaptive_k_four_gate_k540672_screen_for_tests",
    "hubbard_l8_adaptive_k_four_gate_k540672_screen.py",
)
KERNEL = load_module(
    "hubbard_l8_adaptive_k_arithmetic_k540672_for_tests",
    "hubbard_l8_adaptive_k_arithmetic_k540672.py",
)
V6 = load_module(
    "hubbard_l8_adaptive_k_v6_for_k540672_tests",
    "hubbard_l8_adaptive_k_v6_design_probe.py",
)
BASE_KERNEL = load_module(
    "hubbard_l8_adaptive_k_arithmetic_v2_for_k540672_tests",
    "hubbard_l8_adaptive_k_arithmetic_v2.py",
)

EXPECTED_SCREEN_SHA256 = (
    "81ac62fa093c48d57667cb56958ad58a8ed26e8ff81abd7c35365e01fb981d6f"
)
EXPECTED_KERNEL_SHA256 = (
    "327837e4646cb79cb237611ab49e645b51a47a36a97006e94838d1f5fa05af60"
)
EXPECTED_MANIFEST_SHA256 = (
    "d51151fc1d6c73c33f1b50da0a09de4d3346212599716feaba578839dde37526"
)
BASE_TRANSCRIPT_NAMES = {
    "magnetization": (
        "hubbard_l8_magnetization_adaptive_k_"
        "four_gate_granularity_transcript.json"
    ),
    "double_occupancy": (
        "hubbard_l8_double_occupancy_adaptive_k_"
        "four_gate_granularity_transcript.json"
    ),
}
HANDOFF = {
    "magnetization": {
        "checkpoint": 78,
        "candidate_index": 29,
        "pretruncation_count": 643_624,
        "dropped_term_count": 102_952,
        "selected_drop_ticks": "140167648063",
        "old_minimum_K": 529_897,
        "old_excess": 5_609,
    },
    "double_occupancy": {
        "checkpoint": 65,
        "candidate_index": 31,
        "pretruncation_count": 645_011,
        "dropped_term_count": 104_339,
        "selected_drop_ticks": "133481299363",
        "old_minimum_K": 532_869,
        "old_excess": 8_581,
    },
}
EXPECTED_CANONICAL = {
    "magnetization": {
        "file_sha256": (
            "d4a0f952a3d4a93bd78d370fae50c5c043e33caa4d1452e841987976e43354a5"
        ),
        "records_sha256": (
            "c433c9c1231c9ec464b669b545efb3c18d5aefa4be48d780642994219b34dd91"
        ),
        "history_sha256": (
            "43dabd7d34c8de39a91388080dac5e941c162867771fe39fe8a216f7ad00dcc9"
        ),
        "failure_sha256": None,
        "components_sha256": (
            "de6aae57cbcc4a7cffdc80ea9e4f13326f02782958695be3161e833008237d76"
        ),
        "configuration_reference_sha256": (
            "f1a3f80a12cffdf9c274e76a08b9ed9048af36f5ed24ba52b83f0803bfd06d60"
        ),
        "configuration_override_sha256": (
            "abc21d86243ad2460afaadc7c09f0f15f7eb544c5aeb40abdba01c7f9d6eedcf"
        ),
        "kernel_override_sha256": (
            "faef7d40b627387b8a9cb0d3e2cee84d91cbe1eefb32847a8aba6fef5c2da4e6"
        ),
        "transform_sha256": (
            "b82a83a062881bf7ce02de1f962a51b07215696aa150a1821d5df1c0154e5b19"
        ),
        "attempted": 80,
        "completed": 80,
        "terminal": "DIAGNOSTIC_HORIZON_REACHED",
        "last_E": "1699769017939651",
        "peak": 643_624,
        "visits": 87_032_691,
        "coefficient_bits": 57,
        "product_bits": 121,
        "rounding": "120344136051784940341544289",
    },
    "double_occupancy": {
        "file_sha256": (
            "5ced57f7f6fc8aef50a6536920243d00af083b0a113b09d19f239bc1266fd8a5"
        ),
        "records_sha256": (
            "6e38b93fadec1baee53621c3a9ea28c25c8a39ead0d7fbd25a26fcc4295c4423"
        ),
        "history_sha256": (
            "81da7db6f4553e0411d30b23bf6b6e45966158178c3c3e55880b821bbad7ea37"
        ),
        "failure_sha256": (
            "c70ba1f0c695af397f15083859d25119e20ca4f40c103a605af7c37dea449d24"
        ),
        "components_sha256": (
            "b41a28e5a05bbf7e6ff8aa107e12f2331f6ac97f7ce41621f0f8909148e2d19f"
        ),
        "configuration_reference_sha256": (
            "73eefafb16c57d87b5656af91be09482ac027a045854d0dcb95e6edd4519e39f"
        ),
        "configuration_override_sha256": (
            "46e1483315c259fb7afc8686466b29e9938e8372fd6c7b99d64c9cac6c47f90c"
        ),
        "kernel_override_sha256": (
            "faef7d40b627387b8a9cb0d3e2cee84d91cbe1eefb32847a8aba6fef5c2da4e6"
        ),
        "transform_sha256": (
            "b82a83a062881bf7ce02de1f962a51b07215696aa150a1821d5df1c0154e5b19"
        ),
        "attempted": 66,
        "completed": 65,
        "terminal": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "last_E": "2288446837155308",
        "peak": 679_285,
        "visits": 77_762_021,
        "coefficient_bits": 63,
        "product_bits": 120,
        "rounding": "102525536747237809612715364",
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


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def walk(value):
    yield value
    if type(value) is dict:
        for key, child in value.items():
            yield key
            yield from walk(child)
    elif type(value) is list:
        for child in value:
            yield from walk(child)


class FourGateK540672ScreenTests(unittest.TestCase):
    def test_01_exact_source_pins_and_isolated_fresh_modules(self):
        screen_payload = (HERE / SCREEN.SELF_NAME).read_bytes()
        wrapper_payload = (HERE / SCREEN.KERNEL_WRAPPER_NAME).read_bytes()
        parent_payload = (HERE / SCREEN.CONTROL_FLOW_PARENT_NAME).read_bytes()
        v6_payload = (HERE / SCREEN.V6_BASELINE_CONFIGURATION_NAME).read_bytes()
        v2_payload = (HERE / SCREEN.V2_ARITHMETIC_NAME).read_bytes()
        self.assertEqual(sha256(screen_payload), EXPECTED_SCREEN_SHA256)
        self.assertEqual(sha256(wrapper_payload), EXPECTED_KERNEL_SHA256)
        self.assertEqual(
            sha256(parent_payload), SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256
        )
        self.assertEqual(
            sha256(v6_payload), SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
        )
        self.assertEqual(sha256(v2_payload), SCREEN.EXPECTED_V2_ARITHMETIC_SHA256)
        self.assertEqual(SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256, EXPECTED_KERNEL_SHA256)
        self.assertEqual(
            SCREEN.EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256,
            EXPECTED_MANIFEST_SHA256,
        )

        fresh_screen = SCREEN.fresh_self_module()
        self.assertIsNot(fresh_screen, SCREEN)
        self.assertEqual(fresh_screen._VERIFIED_SELF_SOURCE_BYTES, screen_payload)
        first_parent = SCREEN.load_control_flow_parent(HERE)
        second_parent = SCREEN.load_control_flow_parent(HERE)
        self.assertIsNot(first_parent, second_parent)
        self.assertEqual(first_parent._VERIFIED_SELF_SOURCE_BYTES, parent_payload)

        capability, observed, manifest = SCREEN.load_kernel_wrapper(HERE)
        self.assertEqual(observed, EXPECTED_KERNEL_SHA256)
        self.assertEqual(capability._VERIFIED_SELF_SOURCE_BYTES, wrapper_payload)
        self.assertEqual(capability._VERIFIED_BASE_KERNEL_SOURCE_BYTES, v2_payload)
        self.assertIsNot(capability, KERNEL)
        self.assertEqual(sha256(canonical_bytes(manifest)), EXPECTED_MANIFEST_SHA256)

        first = KERNEL.load_pinned_capability(EXPECTED_KERNEL_SHA256)
        second = KERNEL.load_pinned_capability(EXPECTED_KERNEL_SHA256)
        self.assertIsNot(first, second)
        self.assertIsNot(first._BASE_KERNEL_MODULE, second._BASE_KERNEL_MODULE)
        with self.assertRaisesRegex(RuntimeError, "wrapper source pin drift"):
            KERNEL.load_pinned_capability("0" * 64)

        partial = types.ModuleType("partial_k540672_injection_for_test")
        partial.__file__ = str(HERE / SCREEN.KERNEL_WRAPPER_NAME)
        partial.__package__ = ""
        partial.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = wrapper_payload
        with self.assertRaisesRegex(RuntimeError, "requires exact self and"):
            exec(compile(wrapper_payload, partial.__file__, "exec"), partial.__dict__)

    def test_02_kernel_changes_only_retained_K_and_binds_v2_providers(self):
        capability, wrapper_sha, manifest = SCREEN.load_kernel_wrapper(HERE)
        before = manifest["resource_limits_before_extension"]
        after = manifest["resource_limits_after_extension"]
        changed = {
            key for key in set(before) | set(after)
            if before.get(key) != after.get(key)
        }
        self.assertEqual(changed, {"max_retained_K"})
        self.assertEqual(before["max_retained_K"], 524_288)
        self.assertEqual(after["max_retained_K"], 540_672)
        self.assertEqual(
            manifest["resource_limit_delta"],
            {"max_retained_K": {"before": 524_288, "after": 540_672}},
        )
        self.assertEqual(manifest["changed_resource_limit_keys"], ["max_retained_K"])
        self.assertEqual(manifest["certificate_authority"], "NONE")
        self.assertEqual(wrapper_sha, EXPECTED_KERNEL_SHA256)
        self.assertEqual(capability.capability_manifest_sha256(), EXPECTED_MANIFEST_SHA256)

        self.assertEqual(capability.validate_candidates((540_672,)), (540_672,))
        with self.assertRaises(capability.SchemaError):
            capability.validate_candidates((540_673,))
        with self.assertRaises(BASE_KERNEL.SchemaError):
            BASE_KERNEL.validate_candidates((540_672,))

        base = capability._BASE_KERNEL_MODULE
        self.assertIs(capability.RESOURCE_LIMITS, base.RESOURCE_LIMITS)
        for name in capability.BASE_ARITHMETIC_FUNCTION_EXPORTS:
            function = getattr(capability, name)
            self.assertIs(function, getattr(base, name), name)
            self.assertEqual(function.__module__, capability.BASE_PROVIDER_MODULE_NAME)
            self.assertEqual(
                pathlib.Path(function.__code__.co_filename).name,
                SCREEN.V2_ARITHMETIC_NAME,
            )
            self.assertIs(function.__globals__["RESOURCE_LIMITS"], capability.RESOURCE_LIMITS)
        counter = capability.PropagationCounterV2
        self.assertIs(counter, base.PropagationCounterV2)
        self.assertEqual(counter.__module__, capability.BASE_PROVIDER_MODULE_NAME)
        for method_name in (
            "__init__",
            "visit",
            "observe_count",
            "observe",
            "begin_window",
            "observe_interval",
            "observe_product_bits",
        ):
            self.assertIs(
                getattr(counter, method_name).__globals__["RESOURCE_LIMITS"],
                capability.RESOURCE_LIMITS,
            )

    def test_03_exact_M30_D32_candidate_constructions_and_hashes(self):
        old_m = tuple(V6.MODE_CONFIG["magnetization"]["candidates"])
        old_d = tuple(V6.MODE_CONFIG["double_occupancy"]["candidates"])
        self.assertEqual(SCREEN.M_CANDIDATES, old_m + (540_672,))
        self.assertEqual(SCREEN.D_CANDIDATES, old_d[1:] + (540_672,))
        self.assertEqual(old_d[0], 65_536)
        self.assertEqual(old_d.count(65_536), 1)
        self.assertEqual(len(SCREEN.M_CANDIDATES), 30)
        self.assertEqual(len(SCREEN.D_CANDIDATES), 32)
        self.assertIn(65_536, SCREEN.M_CANDIDATES)
        self.assertNotIn(65_536, SCREEN.D_CANDIDATES)
        self.assertNotIn(491_520, SCREEN.D_CANDIDATES)
        self.assertEqual(SCREEN.M_CANDIDATES[-1], 540_672)
        self.assertEqual(SCREEN.D_CANDIDATES[-1], 540_672)
        for mode in SCREEN.MODE_CONFIG:
            candidates = SCREEN.MODE_CONFIG[mode]["candidates"]
            self.assertEqual(
                sha256(canonical_bytes(list(candidates))),
                SCREEN.EXPECTED_CANDIDATE_SHA256[mode],
            )
            self.assertTrue(
                all(left < right for left, right in zip(candidates, candidates[1:]))
            )
        self.assertEqual(
            SCREEN.EXPECTED_CANDIDATE_SHA256,
            {
                "magnetization": (
                    "9baadb7bea90ac503ec3f68cd05fa01d967376fedff59aaedcbf2d009c46fb95"
                ),
                "double_occupancy": (
                    "071999328539f944d72affe0dc14999ef6c1d728bef8a4f94266b1b9950e1133"
                ),
            },
        )

    def test_04_D_65536_removal_basis_recomputed_from_pinned_canonical(self):
        path = HERE / BASE_TRANSCRIPT_NAMES["double_occupancy"]
        raw = path.read_bytes()
        transcript = json.loads(raw)
        anchors = SCREEN.BASE_FOUR_GATE_CANONICAL_ANCHORS["double_occupancy"]
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertEqual(sha256(raw), anchors["transcript_file_sha256"])
        self.assertEqual(
            sha256(canonical_bytes(transcript["records"])),
            anchors["records_sha256"],
        )
        history = transcript["selected_K_history"]
        self.assertEqual(
            sha256(canonical_bytes(history)),
            anchors["selected_K_history_sha256"],
        )
        self.assertEqual(len(transcript["records"]), 65)
        self.assertEqual(len(history), 64)
        feasible_checkpoints = []
        for checkpoint, record in enumerate(transcript["records"], start=1):
            rows = {
                item["configured_K"]: item for item in record["candidate_records"]
            }
            self.assertIn(65_536, rows)
            if rows[65_536]["feasible_under_current_prefix_cap"]:
                feasible_checkpoints.append(checkpoint)
        selected_checkpoints = [
            checkpoint for checkpoint, selected in enumerate(history, start=1)
            if selected == 65_536
        ]
        self.assertEqual(feasible_checkpoints, [])
        self.assertEqual(selected_checkpoints, [])
        self.assertTrue(set(history).issubset(set(SCREEN.D_CANDIDATES)))
        self.assertNotIn(65_536, history)
        self.assertNotIn(491_520, history)
        self.assertEqual(
            SCREEN.configuration_override("double_occupancy")[
                "removed_candidate_precommit_basis"
            ],
            {
                "configured_K": 65_536,
                "canonical_checkpoint_number_range_audited": [1, 65],
                "canonical_candidate_row_feasible_checkpoint_numbers": [],
                "canonical_selected_checkpoint_numbers": [],
                "smallest_baseline_candidate": True,
                "claim_scope": (
                    "all_65_candidate_rows_in_the_pinned_base_four_gate_transcript"
                ),
            },
        )

    def test_05_policy_changes_only_two_K_caps_and_preserves_non_K_budget(self):
        before = SCREEN.EXPECTED_V6_POLICY_CAPS
        after = SCREEN.POLICY_CAPS_BASE
        changed = {
            key for key in set(before) | set(after)
            if before.get(key) != after.get(key)
        }
        self.assertEqual(
            changed,
            {"max_candidate_K", "max_output_terms_if_successful"},
        )
        self.assertEqual(after["max_candidate_K"], 540_672)
        self.assertEqual(after["max_output_terms_if_successful"], 540_672)
        for key in before:
            if key not in changed:
                self.assertEqual(after[key], before[key], key)
        self.assertEqual(
            after["max_single_expansion_terms"],
            after["max_digest_terms"],
        )
        self.assertEqual(after["max_single_expansion_terms"], 786_432)
        for mode in SCREEN.MODE_CONFIG:
            override = SCREEN.configuration_override(mode)
            self.assertEqual(set(override["policy_cap_changes"]), changed)
            self.assertEqual(
                override["unchanged_policy_caps"],
                {key: before[key] for key in before if key not in changed},
            )

    def test_06_horizons_geometry_denominators_and_aligned_budgets_are_exact(self):
        parent = SCREEN.load_control_flow_parent(HERE)
        helper = parent.load_v2_helper(HERE)
        kernel, root, _modules, _custody = parent.load_execution_sources(
            HERE, helper, "magnetization"
        )
        _stages, _trig, sequence, transform = parent.build_four_gate_sequence(
            helper, root, kernel
        )
        self.assertEqual(
            (
                sequence["stage_count"],
                sequence["gate_count"],
                sequence["checkpoint_count"],
                sequence["gates_per_checkpoint"],
            ),
            (9, 1_152, 288, 4),
        )
        self.assertEqual(
            transform["screen_geometry"],
            {
                "stage_count": 9,
                "gate_count": 1_152,
                "gates_per_checkpoint": 4,
                "checkpoints_per_mapped_step": 288,
            },
        )
        expected = {
            "magnetization": (80, 27_936),
            "double_occupancy": (66, 28_224),
        }
        for mode, (horizon, denominator4) in expected.items():
            self.assertEqual(
                SCREEN.MODE_CONFIG[mode]["horizon_checkpoint_count"], horizon
            )
            config = helper.CONFIG[mode]
            remaining = 100 - config["input_step_index"]
            self.assertEqual(denominator4, remaining * 288)
            denominator8 = remaining * 144
            E = config["input_cumulative_drop_ticks"]
            B = helper.MAXIMUM_DROP_TICKS
            for q8 in range(145):
                cap8 = E + q8 * (B - E) // denominator8
                cap4 = E + (2 * q8) * (B - E) // denominator4
                self.assertEqual(cap4, cap8, (mode, q8))

    def test_07_public_entry_uses_fresh_self_and_parent_private_path(self):
        sentinel = {"fresh": True}

        class Inner:
            @staticmethod
            def _run_verified(repo, mode):
                self.assertEqual(repo, HERE)
                self.assertEqual(mode, "magnetization")
                return sentinel

        original_fresh = SCREEN.fresh_self_module
        original_private = SCREEN._run_verified
        try:
            SCREEN._run_verified = lambda *_args: self.fail("live screen path used")
            SCREEN.fresh_self_module = lambda: Inner()
            self.assertIs(SCREEN.run(HERE, "magnetization"), sentinel)
        finally:
            SCREEN.fresh_self_module = original_fresh
            SCREEN._run_verified = original_private

        fresh = SCREEN.fresh_self_module()
        resource_error = RuntimeError("K540672 resource sentinel")

        class Parent:
            @staticmethod
            def _run_verified(_repo, _mode):
                raise resource_error

        fresh.load_control_flow_parent = lambda _repo: Parent()
        fresh.load_configured_v6_baseline = lambda *_args: object()
        fresh.load_kernel_wrapper = lambda _repo: (object(), "a" * 64, {})
        fresh.configure_parent_execution = lambda *_args: None
        with self.assertRaises(RuntimeError) as caught:
            fresh._run_verified(HERE, "double_occupancy")
        self.assertIs(caught.exception, resource_error)

    def synthetic_parent_result(self, mode):
        components = [
            {
                "relative_path": SCREEN.CONTROL_FLOW_PARENT_NAME,
                "role": "four_gate_screen_execution_source",
                "sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            },
            {
                "relative_path": SCREEN.V6_BASELINE_CONFIGURATION_NAME,
                "role": "v6_candidates_and_caps_reference_only",
                "sha256": SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
            },
            {
                "relative_path": SCREEN.V2_ARITHMETIC_NAME,
                "role": "v2_arithmetic_kernel",
                "sha256": SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
            },
        ]
        configuration = {
            "source_sha256": SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
            "role": "candidates_and_caps_reference_only",
        }
        transform = {"transform_id": "synthetic-four-gate-parent"}
        candidates = list(SCREEN.MODE_CONFIG[mode]["candidates"])
        return {
            "schema_version": 1,
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
            "same_byte_self_execution": True,
            "v2_run_entrypoint_called": False,
            "v6_execution_invoked": False,
            "v6_same_byte_execution_parent": False,
            "control_flow_owned_by_screen": True,
            "candidate_policy_precommitted_at_probe_time": False,
            "child_boundary_committed": False,
            "positive_artifact_generated": False,
            "candidate_K_values": candidates,
            "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256[mode],
            "proposed_policy_caps": {
                **SCREEN.POLICY_CAPS_BASE,
                "max_candidate_count": len(candidates),
            },
            "kernel_capability_limits": copy.deepcopy(
                SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
            ),
            "screen_horizon_checkpoint_count": SCREEN.MODE_CONFIG[mode][
                "horizon_checkpoint_count"
            ],
            "source_custody": {
                SCREEN.V6_BASELINE_CONFIGURATION_NAME: (
                    SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
                ),
                SCREEN.V2_ARITHMETIC_NAME: SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
            },
            "screen_execution_components": components,
            "screen_execution_components_sha256": sha256(
                canonical_bytes(components)
            ),
            "configuration_reference": configuration,
            "configuration_reference_sha256": sha256(
                canonical_bytes(configuration)
            ),
            "checkpoint_transform": transform,
            "checkpoint_transform_sha256": sha256(canonical_bytes(transform)),
        }

    def test_08_synthetic_relabel_provenance_and_hashes_are_exact(self):
        fresh = SCREEN.fresh_self_module()
        _kernel, wrapper_sha, manifest = fresh.load_kernel_wrapper(HERE)
        for mode in fresh.MODE_CONFIG:
            with self.subTest(mode=mode):
                result = fresh.validate_and_relabel(
                    self.synthetic_parent_result(mode),
                    mode,
                    wrapper_sha,
                    manifest,
                )
                self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
                self.assertFalse(result["control_flow_owned_by_screen"])
                self.assertTrue(result["control_flow_owned_by_verified_parent"])
                self.assertTrue(result["control_flow_parent_private_entrypoint_called"])
                self.assertTrue(result["control_flow_parent_same_byte_execution"])
                self.assertEqual(
                    result["control_flow_parent_source_sha256"],
                    SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
                )
                self.assertTrue(result["v6_configuration_source_used_as_baseline_only"])
                self.assertTrue(result["v6_runtime_configuration_override_applied"])
                self.assertEqual(
                    result["kernel_capability_wrapper_source_sha256"],
                    EXPECTED_KERNEL_SHA256,
                )
                self.assertEqual(
                    result["kernel_capability_override"][
                        "capability_manifest_sha256"
                    ],
                    EXPECTED_MANIFEST_SHA256,
                )
                roles = {
                    item["relative_path"]: item["role"]
                    for item in result["screen_execution_components"]
                }
                self.assertEqual(
                    roles[SCREEN.SELF_NAME],
                    "k540672_fresh_same_byte_screen_wrapper",
                )
                self.assertEqual(
                    roles[SCREEN.CONTROL_FLOW_PARENT_NAME],
                    "four_gate_control_flow_parent_private_entrypoint",
                )
                self.assertEqual(
                    roles[SCREEN.V2_ARITHMETIC_NAME],
                    "v2_arithmetic_bytes_beneath_capability_wrapper",
                )
                self.assertEqual(
                    roles[SCREEN.KERNEL_WRAPPER_NAME],
                    "k540672_capability_override_provider",
                )
                for field, value in (
                    (
                        "screen_execution_components_sha256",
                        result["screen_execution_components"],
                    ),
                    (
                        "configuration_reference_sha256",
                        result["configuration_reference"],
                    ),
                    (
                        "configuration_override_sha256",
                        result["configuration_override"],
                    ),
                    (
                        "kernel_capability_override_sha256",
                        result["kernel_capability_override"],
                    ),
                    (
                        "checkpoint_transform_sha256",
                        result["checkpoint_transform"],
                    ),
                ):
                    self.assertEqual(result[field], sha256(canonical_bytes(value)))
                self.assertEqual(
                    result["source_custody"][SCREEN.SELF_NAME],
                    EXPECTED_SCREEN_SHA256,
                )
                self.assertFalse(result["candidate_policy_precommitted_at_probe_time"])
                self.assertFalse(result["child_boundary_committed"])
                self.assertFalse(result["positive_artifact_generated"])

    def test_09_four_MiB_atomic_output_is_failure_preserving(self):
        self.assertEqual(SCREEN.MAX_OUTPUT_BYTES, 4_194_304)
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "screen.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "exact bytes"):
                SCREEN.write_atomic_bounded(output, bytearray(b"[]"))
            with self.assertRaisesRegex(RuntimeError, "output byte cap"):
                SCREEN.write_atomic_bounded(
                    output,
                    b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1),
                )
            self.assertEqual(output.read_bytes(), b"{}")

            replace_error = OSError("replace sentinel")
            original_replace = SCREEN.os.replace
            try:
                SCREEN.os.replace = lambda *_args: (_ for _ in ()).throw(
                    replace_error
                )
                with self.assertRaises(OSError) as caught:
                    SCREEN.write_atomic_bounded(output, b"[]")
                self.assertIs(caught.exception, replace_error)
            finally:
                SCREEN.os.replace = original_replace
            self.assertEqual(output.read_bytes(), b"{}")
            self.assertEqual(list(pathlib.Path(directory).glob("*.tmp")), [])

    def test_10_scope_is_diagnostic_only(self):
        for mode in SCREEN.MODE_CONFIG:
            override = SCREEN.configuration_override(mode)
            self.assertTrue(override["diagnostic_ladder_precommitted_before_replay"])
            self.assertEqual(
                set(override["overridden_fields"]),
                {
                    f"MODE_CONFIG.{mode}.candidates",
                    "POLICY_CAPS_BASE.max_candidate_K",
                    "POLICY_CAPS_BASE.max_output_terms_if_successful",
                },
            )
        source = (HERE / SCREEN.SELF_NAME).read_text()
        for forbidden in (
            "READY_FOR_BENCHMARK",
            "formal_witness",
            "boundary_sidecar",
            "dual_screen_checker",
        ):
            self.assertNotIn(forbidden, source)

    def assert_full_ledger(self, mode, transcript, expected):
        parent = SCREEN.load_control_flow_parent(HERE)
        helper = parent.load_v2_helper(HERE)
        kernel, root, _modules, _custody = parent.load_execution_sources(
            HERE, helper, mode
        )
        stages, _trig, sequence, _transform = parent.build_four_gate_sequence(
            helper, root, kernel
        )
        gates = [gate for stage in stages for gate in stage["gates"]]
        self.assertEqual(len(gates), sequence["gate_count"])

        candidates = list(SCREEN.MODE_CONFIG[mode]["candidates"])
        helper_config = helper.CONFIG[mode]
        E_input = helper_config["input_cumulative_drop_ticks"]
        maximum_drop = helper.MAXIMUM_DROP_TICKS
        denominator = transcript["future_checkpoint_denominator"]
        cumulative = E_input
        visits = 0
        rounding = 0
        peak = 0
        coefficient_bits = 0
        product_bits = 0
        selected_history = []
        previous = None

        self.assertEqual(len(transcript["records"]), expected["attempted"])
        for index, record in enumerate(transcript["records"]):
            checkpoint = index + 1
            self.assertEqual(record["checkpoint_index_zero_based"], index)
            self.assertEqual(record["checkpoint_number_one_based"], checkpoint)
            self.assertEqual(record["gate_occurrence_first_zero_based"], 4 * index)
            self.assertEqual(record["gate_occurrence_last_zero_based"], 4 * index + 3)
            self.assertEqual(
                record["gate_batch_sha256"],
                helper.gate_batch_sha256(gates[4 * index:4 * index + 4]),
            )
            if previous is not None:
                self.assertEqual(
                    record["input_expansion_count"],
                    previous["retained_expansion_count"],
                )
                self.assertEqual(
                    record["input_expansion_sha256"],
                    previous["retained_expansion_sha256"],
                )

            cap = E_input + checkpoint * (maximum_drop - E_input) // denominator
            self.assertEqual(int(record["budget_prefix_cap_ticks"]), cap)
            self.assertEqual(int(record["E_before_ticks"]), cumulative)
            slack = cap - cumulative
            self.assertEqual(int(record["prefix_slack_before_selection_ticks"]), slack)

            visits += record["term_gate_visits_increment"]
            self.assertEqual(record["term_gate_visits_cumulative"], visits)
            rounding += int(record["rounding_increment_scaled_ticks_squared"])
            self.assertEqual(
                int(record["rounding_cumulative_scaled_ticks_squared"]), rounding
            )
            peak = max(peak, record["peak_live_terms_this_checkpoint"])
            self.assertEqual(record["peak_live_terms_cumulative"], peak)
            self.assertGreaterEqual(
                record["maximum_expansion_coefficient_tick_bits"], coefficient_bits
            )
            self.assertGreaterEqual(record["maximum_product_bits"], product_bits)
            coefficient_bits = record["maximum_expansion_coefficient_tick_bits"]
            product_bits = record["maximum_product_bits"]

            candidate_records = record["candidate_records"]
            self.assertEqual(
                [item["configured_K"] for item in candidate_records], candidates
            )
            drops = []
            feasible_indices = []
            for candidate_index, item in enumerate(candidate_records):
                self.assertEqual(item["candidate_index"], candidate_index)
                effective = min(
                    item["configured_K"], record["pretruncation_expansion_count"]
                )
                self.assertEqual(item["effective_retained_count"], effective)
                self.assertEqual(
                    item["dropped_term_count"],
                    record["pretruncation_expansion_count"] - effective,
                )
                drop = int(item["drop_ticks"])
                drops.append(drop)
                self.assertEqual(
                    int(item["E_after_if_selected_ticks"]), cumulative + drop
                )
                feasible = cumulative + drop <= cap
                self.assertIs(item["feasible_under_current_prefix_cap"], feasible)
                if feasible:
                    feasible_indices.append(candidate_index)
            self.assertEqual(drops, sorted(drops, reverse=True))

            if record["status"] == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
                self.assertTrue(feasible_indices)
                selected = feasible_indices[0]
                selected_row = candidate_records[selected]
                self.assertEqual(record["selected_candidate_index"], selected)
                self.assertEqual(record["selected_K"], candidates[selected])
                self.assertEqual(int(record["selected_drop_ticks"]), drops[selected])
                self.assertEqual(
                    record["selected_effective_retained_count"],
                    selected_row["effective_retained_count"],
                )
                self.assertEqual(
                    record["selected_dropped_term_count"],
                    selected_row["dropped_term_count"],
                )
                self.assertEqual(
                    record["retained_expansion_count"],
                    selected_row["effective_retained_count"],
                )
                cumulative += drops[selected]
                self.assertEqual(int(record["E_after_ticks"]), cumulative)
                selected_history.append(candidates[selected])
                previous = record
            else:
                self.assertEqual(
                    record["status"],
                    "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                )
                self.assertFalse(feasible_indices)
                self.assertIsNone(record["selected_candidate_index"])
                self.assertIsNone(record["selected_K"])
                self.assertEqual(
                    int(record["maximum_candidate_drop_excess_over_slack_ticks"]),
                    drops[-1] - slack,
                )
                self.assertEqual(index, len(transcript["records"]) - 1)

        self.assertEqual(selected_history, transcript["selected_K_history"])
        self.assertEqual(len(selected_history), expected["completed"])
        self.assertEqual(str(cumulative), expected["last_E"])
        self.assertEqual(transcript["last_committed_cumulative_drop_ticks"], expected["last_E"])
        self.assertEqual(visits, expected["visits"])
        self.assertEqual(peak, expected["peak"])
        self.assertEqual(coefficient_bits, expected["coefficient_bits"])
        self.assertEqual(product_bits, expected["product_bits"])
        self.assertEqual(str(rounding), expected["rounding"])
        self.assertEqual(
            transcript["observed_term_gate_visits_including_terminal_attempt"],
            expected["visits"],
        )
        self.assertEqual(
            transcript["observed_peak_single_expansion_terms"], expected["peak"]
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
        self.assertTrue(transcript["root_globals_unchanged"])
        self.assertEqual(
            transcript["root_globals_before"], transcript["root_globals_after"]
        )

    def assert_shared_canonical_prefix(self, mode, transcript, base):
        prefix_count = base["completed_checkpoint_count"]
        self.assertEqual(
            transcript["selected_K_history"][:prefix_count],
            base["selected_K_history"],
        )
        for index in range(prefix_count):
            old = base["records"][index]
            new = transcript["records"][index]
            old_common = {
                key: value for key, value in old.items()
                if key not in {"candidate_records", "selected_candidate_index"}
            }
            new_common = {
                key: value for key, value in new.items()
                if key not in {"candidate_records", "selected_candidate_index"}
            }
            self.assertEqual(new_common, old_common, (mode, index + 1))
            old_rows = {
                item["configured_K"]: {
                    key: value for key, value in item.items()
                    if key != "candidate_index"
                }
                for item in old["candidate_records"]
                if item["configured_K"] in SCREEN.MODE_CONFIG[mode]["candidates"]
            }
            new_rows = {
                item["configured_K"]: {
                    key: value for key, value in item.items()
                    if key != "candidate_index"
                }
                for item in new["candidate_records"]
                if item["configured_K"] in old_rows
            }
            self.assertEqual(new_rows, old_rows, (mode, index + 1))
            if mode == "magnetization":
                self.assertEqual(
                    new["selected_candidate_index"], old["selected_candidate_index"]
                )
            else:
                self.assertEqual(
                    new["selected_candidate_index"],
                    old["selected_candidate_index"] - 1,
                )

    def assert_canonical_transcript_when_available(self, mode):
        path = HERE / SCREEN.MODE_CONFIG[mode]["output_name"]
        if not path.exists():
            self.skipTest(f"canonical K=540672 {mode} transcript not generated yet")
        expected = EXPECTED_CANONICAL[mode]
        raw = path.read_bytes()
        transcript = json.loads(raw)
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertEqual(sha256(raw), expected["file_sha256"])
        self.assertLessEqual(len(raw), SCREEN.MAX_OUTPUT_BYTES)
        self.assertEqual(
            transcript["transcript_fingerprint"],
            "hubbard_l8_adaptive_k_four_gate_k540672_screen_v1",
        )
        self.assertEqual(transcript["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            transcript["status"], "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS"
        )
        self.assertFalse(transcript["control_flow_owned_by_screen"])
        self.assertTrue(transcript["control_flow_owned_by_verified_parent"])
        self.assertTrue(transcript["control_flow_parent_private_entrypoint_called"])
        self.assertFalse(transcript["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(transcript["child_boundary_committed"])
        self.assertFalse(transcript["positive_artifact_generated"])
        self.assertEqual(
            transcript["candidate_K_values"],
            list(SCREEN.MODE_CONFIG[mode]["candidates"]),
        )
        self.assertEqual(
            transcript["candidate_K_values_sha256"],
            SCREEN.EXPECTED_CANDIDATE_SHA256[mode],
        )
        self.assertEqual(
            transcript["proposed_policy_caps"],
            {
                **SCREEN.POLICY_CAPS_BASE,
                "max_candidate_count": len(SCREEN.MODE_CONFIG[mode]["candidates"]),
            },
        )
        self.assertEqual(
            transcript["kernel_capability_limits"],
            SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        )
        self.assertEqual(
            transcript["screen_horizon_checkpoint_count"],
            SCREEN.MODE_CONFIG[mode]["horizon_checkpoint_count"],
        )
        self.assertEqual(transcript["attempted_checkpoint_count"], expected["attempted"])
        self.assertEqual(transcript["completed_checkpoint_count"], expected["completed"])
        self.assertEqual(transcript["screen_terminal_condition"], expected["terminal"])
        for field, value in (
            (
                "screen_execution_components_sha256",
                transcript["screen_execution_components"],
            ),
            (
                "configuration_reference_sha256",
                transcript["configuration_reference"],
            ),
            (
                "configuration_override_sha256",
                transcript["configuration_override"],
            ),
            (
                "kernel_capability_override_sha256",
                transcript["kernel_capability_override"],
            ),
            (
                "checkpoint_transform_sha256",
                transcript["checkpoint_transform"],
            ),
            ("records_sha256", transcript["records"]),
            ("selected_K_history_sha256", transcript["selected_K_history"]),
        ):
            self.assertEqual(transcript[field], sha256(canonical_bytes(value)))
        self.assertEqual(transcript["records_sha256"], expected["records_sha256"])
        self.assertEqual(
            transcript["selected_K_history_sha256"], expected["history_sha256"]
        )
        self.assertEqual(
            transcript["failure_record_sha256"], expected["failure_sha256"]
        )
        self.assertEqual(
            transcript["screen_execution_components_sha256"],
            expected["components_sha256"],
        )
        self.assertEqual(
            transcript["configuration_reference_sha256"],
            expected["configuration_reference_sha256"],
        )
        self.assertEqual(
            transcript["configuration_override_sha256"],
            expected["configuration_override_sha256"],
        )
        self.assertEqual(
            transcript["kernel_capability_override_sha256"],
            expected["kernel_override_sha256"],
        )
        self.assertEqual(
            transcript["checkpoint_transform_sha256"],
            expected["transform_sha256"],
        )
        for component in transcript["screen_execution_components"]:
            payload = (HERE / component["relative_path"]).read_bytes()
            self.assertEqual(sha256(payload), component["sha256"])

        base_path = HERE / BASE_TRANSCRIPT_NAMES[mode]
        base = json.loads(base_path.read_bytes())
        self.assert_full_ledger(mode, transcript, expected)
        self.assert_shared_canonical_prefix(mode, transcript, base)
        handoff = HANDOFF[mode]
        checkpoint = handoff["checkpoint"]
        self.assertGreaterEqual(len(transcript["records"]), checkpoint)
        self.assertEqual(
            transcript["selected_K_history"][: checkpoint - 1],
            base["selected_K_history"],
        )
        self.assertEqual(transcript["selected_K_history"][checkpoint - 1], 540_672)
        old_failure = base["records"][-1]
        new_handoff = transcript["records"][checkpoint - 1]
        self.assertEqual(
            old_failure["minimum_effective_K_to_meet_prefix"],
            handoff["old_minimum_K"],
        )
        self.assertEqual(
            old_failure["required_K_excess_over_policy_maximum"],
            handoff["old_excess"],
        )
        for key in (
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
        ):
            self.assertEqual(new_handoff[key], old_failure[key], key)
        self.assertEqual(new_handoff["status"], "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED")
        self.assertEqual(new_handoff["selected_K"], 540_672)
        self.assertEqual(
            new_handoff["selected_candidate_index"], handoff["candidate_index"]
        )
        self.assertEqual(
            new_handoff["pretruncation_expansion_count"],
            handoff["pretruncation_count"],
        )
        self.assertEqual(new_handoff["selected_effective_retained_count"], 540_672)
        self.assertEqual(
            new_handoff["selected_dropped_term_count"],
            handoff["dropped_term_count"],
        )
        self.assertEqual(
            new_handoff["selected_drop_ticks"], handoff["selected_drop_ticks"]
        )
        self.assertLessEqual(
            int(new_handoff["E_after_ticks"]),
            int(new_handoff["budget_prefix_cap_ticks"]),
        )
        shared_old = {
            item["configured_K"]: {
                key: value for key, value in item.items() if key != "candidate_index"
            }
            for item in old_failure["candidate_records"]
            if item["configured_K"] in SCREEN.MODE_CONFIG[mode]["candidates"]
        }
        shared_new = {
            item["configured_K"]: {
                key: value for key, value in item.items() if key != "candidate_index"
            }
            for item in new_handoff["candidate_records"]
            if item["configured_K"] in shared_old
        }
        self.assertEqual(shared_new, shared_old)
        if mode == "double_occupancy":
            old_counterfactual = dict(old_failure["removed_491520_counterfactual"])
            new_counterfactual = dict(new_handoff["removed_491520_counterfactual"])
            self.assertIsNone(old_counterfactual.pop("actual_selected_K"))
            self.assertEqual(new_counterfactual.pop("actual_selected_K"), 540_672)
            self.assertEqual(
                new_counterfactual,
                old_counterfactual,
            )
        if mode == "magnetization":
            self.assertFalse(transcript["failure_checkpoint_included"])
            self.assertTrue(transcript["horizon_reached_with_committed_checkpoint"])
            self.assertEqual(
                [record["selected_K"] for record in transcript["records"][-3:]],
                [540_672, 540_672, 540_672],
            )
            self.assertEqual(
                [record["pretruncation_expansion_count"] for record in transcript["records"][-3:]],
                [643_624, 624_312, 587_900],
            )
        else:
            self.assertTrue(transcript["failure_checkpoint_included"])
            self.assertFalse(transcript["horizon_reached_with_committed_checkpoint"])
            failure = transcript["records"][-1]
            self.assertEqual(failure["checkpoint_number_one_based"], 66)
            self.assertEqual(
                (
                    failure["gate_occurrence_first_zero_based"],
                    failure["gate_occurrence_last_zero_based"],
                ),
                (260, 263),
            )
            self.assertEqual(failure["pretruncation_expansion_count"], 679_285)
            self.assertEqual(failure["minimum_effective_K_to_meet_prefix"], 558_598)
            self.assertEqual(failure["required_K_excess_over_policy_maximum"], 17_926)
            self.assertEqual(786_432 - failure["pretruncation_expansion_count"], 107_147)
            self.assertLess(557_056, failure["minimum_effective_K_to_meet_prefix"])
            self.assertEqual(
                ((failure["minimum_effective_K_to_meet_prefix"] + 16_383) // 16_384)
                * 16_384,
                573_440,
            )
            self.assertEqual(
                set(transcript["selected_K_history"]),
                set(SCREEN.D_CANDIDATES),
            )
            self.assertEqual(
                sha256(canonical_bytes(failure)), expected["failure_sha256"]
            )
        for item in walk(transcript):
            self.assertIsNot(type(item), float)
            if type(item) is str:
                self.assertFalse(item.startswith("/"))

    def test_11_magnetization_canonical_transcript_when_available(self):
        self.assert_canonical_transcript_when_available("magnetization")

    def test_12_double_occupancy_canonical_transcript_when_available(self):
        self.assert_canonical_transcript_when_available("double_occupancy")

    @unittest.skipUnless(
        os.environ.get("RUN_HUBBARD_L8_FOUR_GATE_K540672_CANONICAL_REPLAY") == "1",
        "expensive deterministic K=540672 canonical replays are opt-in",
    )
    def test_13_real_canonical_replays_are_opt_in(self):
        for mode in SCREEN.MODE_CONFIG:
            with self.subTest(mode=mode):
                path = HERE / SCREEN.MODE_CONFIG[mode]["output_name"]
                self.assertTrue(path.exists(), f"missing canonical transcript: {mode}")
                expected = path.read_bytes()
                self.assertEqual(canonical_bytes(SCREEN.run(HERE, mode)), expected)


if __name__ == "__main__":
    unittest.main()
