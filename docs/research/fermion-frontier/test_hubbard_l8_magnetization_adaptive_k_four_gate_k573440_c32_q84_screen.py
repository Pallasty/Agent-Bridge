#!/usr/bin/env python3
"""Static and synthetic tests for the M K573440/C32 q84 screen."""

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
SCREEN_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k573440_c32_q84_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "1246023edea93e89db2ec0071c51c1cb15f60b8a928b934aad08cebb593240b2"
)
EXPECTED_CANONICAL = {
    "file_sha256": "f379f6a72caba82c0f1aca599ef9872666cfed8b4ea72003194438ed01806f48",
    "candidate_sha256": "b46d0b11cbb16260d7d3b76b4a42d0013c74dae767e39a5b11bf50d8fdddb428",
    "records_sha256": "35479fdf0715400b6b022ad5a538edc5eb21ed3f08b25896555496763f6ba26d",
    "history_sha256": "cb4e935c2e8bd0458d7164701d79251b9a5d5f3d80f949ff8f8953ce561b6cc6",
    "failure_sha256": "1f2587a16f11ab3b6eb02aedcaf661bda5ba3acfc1afffe1cc06e03c79cc76c7",
    "components_sha256": "728ba2a42b4190bc6240a567d136c1c26aee528c2cce190280b2b24a0d7aa093",
    "configuration_reference_sha256": "a4d0b5a8736f2ffba7f83bf90685b5ce57920dee5028f9949159d5c3110a2138",
    "configuration_override_sha256": "8858e3d76caf4c3fbb6d9e589544e9fbd14d6871cd8ca50a44ed7c96f09f8596",
    "kernel_override_sha256": "1c1817a00304d28ac457ef8126c2efb8ec6831f586b9af571387f7d633e13d9a",
    "parent_horizon_override_sha256": "c0d860b56e0d4fb9c29e0227f4e8801a3d89d2e7e62de7945fd53075557aa924",
    "route_reference_sha256": "a32e2d53d7eb8d7a2fb5564e6375f880c1fde9b1f52da038240f9c2e4a6514d0",
    "handoff_sha256": "ae9b904f1fcd0de59235b2a402ec9963a7836d2890312359a495ae84a884562d",
    "transform_sha256": "54b79fb46252b6457fb2e428cf5fae87969e96d1e88c42519a48bb588081f563",
    "last_E": "1700088465879056",
    "peak": 694_130,
    "visits": 96_423_989,
    "coefficient_bits": 57,
    "product_bits": 121,
    "rounding": "136134157765376532642684017",
}


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("m_k573440_c32_q84_screen", SCREEN_NAME)


def canonical_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_predecessor():
    return json.loads((HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes())


def appended_row(record):
    effective = min(SCREEN.K573440, record["pretruncation_expansion_count"])
    return {
        "candidate_index": 31,
        "configured_K": SCREEN.K573440,
        "effective_retained_count": effective,
        "dropped_term_count": record["pretruncation_expansion_count"] - effective,
        "drop_ticks": "0",
        "E_after_if_selected_ticks": record["E_before_ticks"],
        "feasible_under_current_prefix_cap": True,
    }


def synthetic_parent_result():
    predecessor = load_predecessor()
    records = copy.deepcopy(predecessor["records"])
    for record in records[:82]:
        record["candidate_records"].append(appended_row(record))

    q83 = records[82]
    row = appended_row(q83)
    q83["candidate_records"].append(row)
    for key in (
        "maximum_candidate_drop_excess_over_slack_ticks",
        "minimum_effective_K_to_meet_prefix",
        "required_K_excess_over_policy_maximum",
    ):
        q83.pop(key, None)
    q83.update({
        "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
        "selected_candidate_index": 31,
        "selected_K": SCREEN.K573440,
        "selected_effective_retained_count": SCREEN.K573440,
        "selected_dropped_term_count": 78_576,
        "selected_drop_ticks": row["drop_ticks"],
        "selected_dropped_terms_sha256": "1" * 64,
        "maximum_dropped_abs_upper_ticks": "1",
        "minimum_retained_abs_upper_ticks": "1",
        "retained_expansion_count": SCREEN.K573440,
        "retained_expansion_sha256": "2" * 64,
        "E_after_ticks": row["E_after_if_selected_ticks"],
    })

    E_before = int(q83["E_after_ticks"])
    pre_count = 600_000
    rows = []
    for candidate_index, configured_K in enumerate(SCREEN.M_CANDIDATES):
        effective = min(configured_K, pre_count)
        rows.append({
            "candidate_index": candidate_index,
            "configured_K": configured_K,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
            "drop_ticks": "1",
            "E_after_if_selected_ticks": str(E_before + 1),
            "feasible_under_current_prefix_cap": False,
        })
    q84 = {
        "checkpoint_index_zero_based": 83,
        "checkpoint_number_one_based": 84,
        "E_before_ticks": q83["E_after_ticks"],
        "input_expansion_count": SCREEN.K573440,
        "input_expansion_sha256": q83["retained_expansion_sha256"],
        "pretruncation_expansion_count": pre_count,
        "budget_prefix_cap_ticks": str(E_before),
        "prefix_slack_before_selection_ticks": "0",
        "candidate_records": rows,
        "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "selected_candidate_index": None,
        "selected_K": None,
        "minimum_effective_K_to_meet_prefix": SCREEN.K573440 + 1,
        "required_K_excess_over_policy_maximum": 1,
        "maximum_candidate_drop_excess_over_slack_ticks": "1",
    }
    records.append(q84)
    history = copy.deepcopy(predecessor["selected_K_history"]) + [SCREEN.K573440]
    components = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
    configuration = {"synthetic_parent_configuration": True}
    transform = {"synthetic_parent_transform": True}
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
        "screen_horizon_checkpoint_count": 84,
        "candidate_K_values": list(SCREEN.M_CANDIDATES),
        "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **SCREEN.POLICY_CAPS_BASE,
            "max_candidate_count": 32,
        },
        "kernel_capability_limits": SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        "records": records,
        "records_sha256": digest(records),
        "selected_K_history": history,
        "selected_K_history_sha256": digest(history),
        "attempted_checkpoint_count": 84,
        "completed_checkpoint_count": 83,
        "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "failure_checkpoint_included": True,
        "failure_record_sha256": digest(q84),
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": False,
        "last_committed_cumulative_drop_ticks": q83["E_after_ticks"],
        "screen_execution_components": components,
        "screen_execution_components_sha256": digest(components),
        "configuration_reference": configuration,
        "configuration_reference_sha256": digest(configuration),
        "checkpoint_transform": transform,
        "checkpoint_transform_sha256": digest(transform),
        "source_custody": {},
    }


class MagnetizationK573440C32Q84ScreenTests(unittest.TestCase):
    def test_01_exact_source_wrapper_and_route_pins(self):
        exact = {
            SCREEN.CONTROL_FLOW_PARENT_NAME: SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            SCREEN.V6_BASELINE_CONFIGURATION_NAME: (
                SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
            ),
            SCREEN.V2_ARITHMETIC_NAME: SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
            SCREEN.KERNEL_WRAPPER_NAME: SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME: (
                SCREEN.EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256
            ),
            SCREEN.ROUTE_Q82_SCREEN_NAME: SCREEN.EXPECTED_ROUTE_Q82_SCREEN_SHA256,
        }
        for filename, expected in exact.items():
            self.assertEqual(
                hashlib.sha256((HERE / filename).read_bytes()).hexdigest(), expected
            )
        self.assertEqual(
            hashlib.sha256((HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes()).hexdigest(),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((HERE / SCREEN.ROUTE_Q82_TRANSCRIPT_NAME).read_bytes()).hexdigest(),
            SCREEN.EXPECTED_ROUTE_Q82_TRANSCRIPT_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((HERE / SCREEN_NAME).read_bytes()).hexdigest(),
            EXPECTED_SCREEN_SHA256,
        )
        fresh = SCREEN.fresh_self_module()
        self.assertEqual(fresh._VERIFIED_SELF_SOURCE_BYTES, (HERE / SCREEN_NAME).read_bytes())
        wrapper, wrapper_sha, manifest = SCREEN.load_kernel_wrapper(HERE)
        self.assertEqual(wrapper_sha, SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256)
        self.assertEqual(
            digest(manifest), SCREEN.EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256
        )
        self.assertEqual(
            wrapper.capability_manifest_sha256(),
            SCREEN.EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256,
        )
        self.assertEqual(
            digest(manifest["source_layers"]),
            SCREEN.EXPECTED_KERNEL_SOURCE_LAYERS_SHA256,
        )
        self.assertEqual(
            digest(manifest["route_predecessor_reference"]),
            SCREEN.EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256,
        )

    def test_02_candidate_config_caps_and_horizon_are_exact(self):
        SCREEN.validate_local_configuration()
        self.assertEqual(len(SCREEN.V6_M_CANDIDATES), 29)
        self.assertEqual(len(SCREEN.PREDECESSOR_M_CANDIDATES), 31)
        self.assertEqual(len(SCREEN.M_CANDIDATES), 32)
        self.assertEqual(
            SCREEN.M_CANDIDATES, SCREEN.PREDECESSOR_M_CANDIDATES + (573_440,)
        )
        self.assertEqual(digest(list(SCREEN.M_CANDIDATES)), SCREEN.EXPECTED_CANDIDATE_SHA256)
        changed = SCREEN.changed_mapping_keys(
            SCREEN.EXPECTED_PREDECESSOR_POLICY_CAPS, SCREEN.POLICY_CAPS_BASE
        )
        self.assertEqual(changed, {"max_candidate_K", "max_output_terms_if_successful"})
        self.assertEqual(SCREEN.POLICY_CAPS_BASE["max_candidate_K"], 573_440)
        configuration, baseline_m = SCREEN.load_configured_v6_baseline(HERE)
        self.assertEqual(tuple(baseline_m), SCREEN.V6_M_CANDIDATES)
        self.assertEqual(tuple(configuration.MODE_CONFIG[SCREEN.MODE]["candidates"]), SCREEN.M_CANDIDATES)
        baseline_configuration, _ = SCREEN.load_pinned_module(
            HERE,
            SCREEN.V6_BASELINE_CONFIGURATION_NAME,
            SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
            "pristine_v6_for_m_screen_test",
        )
        self.assertEqual(
            configuration.MODE_CONFIG["double_occupancy"],
            baseline_configuration.MODE_CONFIG["double_occupancy"],
        )
        parent = SCREEN.load_control_flow_parent(HERE)
        before = copy.deepcopy(parent.MODE_CONFIG)
        wrapper, _sha, _manifest = SCREEN.load_kernel_wrapper(HERE)
        horizon = SCREEN.configure_parent_execution(parent, configuration, wrapper)
        self.assertEqual(
            horizon["changed_fields"],
            ["MODE_CONFIG.magnetization.horizon_checkpoint_count"],
        )
        self.assertEqual(before[SCREEN.MODE]["horizon_checkpoint_count"], 80)
        self.assertEqual(parent.MODE_CONFIG[SCREEN.MODE]["horizon_checkpoint_count"], 84)
        self.assertEqual(parent.MODE_CONFIG["double_occupancy"], before["double_occupancy"])

    def test_03_wrapper_capability_and_nonexecution_lineage(self):
        wrapper, wrapper_sha, manifest = SCREEN.load_kernel_wrapper(HERE)
        self.assertEqual(wrapper.RESOURCE_LIMITS, SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS)
        self.assertEqual(wrapper.RESOURCE_LIMITS["max_candidate_count"], 32)
        self.assertEqual(wrapper.RESOURCE_LIMITS["max_retained_K"], 573_440)
        self.assertEqual(
            [item["relative_path"] for item in manifest["source_layers"]],
            [SCREEN.KERNEL_WRAPPER_NAME, SCREEN.V2_ARITHMETIC_NAME],
        )
        route = manifest["route_predecessor_reference"]
        self.assertEqual(route["source_sha256"], SCREEN.EXPECTED_ROUTE_PREDECESSOR_KERNEL_SHA256)
        self.assertFalse(route["compiled"])
        self.assertFalse(route["executed"])
        self.assertFalse(route["execution_source_layer"])
        capability = SCREEN.kernel_capability_override(wrapper_sha, manifest)
        self.assertEqual(capability["execution_source_layers"], [SCREEN.KERNEL_WRAPPER_NAME, SCREEN.V2_ARITHMETIC_NAME])
        self.assertFalse(capability["route_predecessor_is_execution_source"])

    def test_04_private_parent_path_and_exception_identity(self):
        fresh = SCREEN.fresh_self_module()
        original_loader = fresh.load_control_flow_parent
        observed = {}

        def load_sentinel_parent(repo):
            parent = original_loader(repo)

            def private_sentinel(inner_repo, mode):
                observed["repo"] = inner_repo
                observed["mode"] = mode
                observed["horizon"] = parent.MODE_CONFIG[mode][
                    "horizon_checkpoint_count"
                ]
                observed["D_config"] = copy.deepcopy(
                    parent.MODE_CONFIG["double_occupancy"]
                )
                configured = parent.load_v6_configuration(inner_repo)
                observed["candidates"] = configured.MODE_CONFIG[mode]["candidates"]
                observed["caps"] = copy.deepcopy(configured.POLICY_CAPS_BASE)
                helper = parent.load_v2_helper(inner_repo)
                active, _root, _modules, _custody = parent.load_execution_sources(
                    inner_repo, helper, mode
                )
                observed["limits"] = copy.deepcopy(active.RESOURCE_LIMITS)
                return {"private": True}

            parent._run_verified = private_sentinel
            return parent

        fresh.load_control_flow_parent = load_sentinel_parent
        fresh.validate_and_relabel = lambda result, *_args: result
        self.assertEqual(fresh._run_verified(HERE), {"private": True})
        self.assertEqual(observed["repo"], HERE.resolve())
        self.assertEqual(observed["mode"], SCREEN.MODE)
        self.assertEqual(observed["horizon"], 84)
        self.assertEqual(observed["D_config"]["horizon_checkpoint_count"], 66)
        self.assertEqual(observed["candidates"], SCREEN.M_CANDIDATES)
        self.assertEqual(observed["caps"], SCREEN.POLICY_CAPS_BASE)
        self.assertEqual(
            observed["limits"], SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        )

        resource_error = RuntimeError("resource identity")
        failing = SCREEN.fresh_self_module()
        failing_original_loader = failing.load_control_flow_parent

        def load_failing_parent(repo):
            parent = failing_original_loader(repo)

            def private_failure(_repo, _mode):
                raise resource_error

            parent._run_verified = private_failure
            return parent

        failing.load_control_flow_parent = load_failing_parent
        with self.assertRaises(RuntimeError) as caught:
            failing._run_verified(HERE)
        self.assertIs(caught.exception, resource_error)

    def test_05_public_run_always_uses_fresh_self(self):
        sentinel = {"fresh": True}

        class Inner:
            @staticmethod
            def _run_verified(repo):
                self.assertEqual(repo, HERE)
                return sentinel

        original = SCREEN.fresh_self_module
        try:
            SCREEN.fresh_self_module = lambda: Inner()
            self.assertIs(SCREEN.run(HERE), sentinel)
        finally:
            SCREEN.fresh_self_module = original

    def test_06_synthetic_prefix_handoff_and_tamper_checks(self):
        predecessor = load_predecessor()
        result = synthetic_parent_result()
        handoff = SCREEN.validate_replay_handoff(result, predecessor)
        self.assertTrue(handoff["q1_through_q82_common_records_exact"])
        self.assertEqual(handoff["q83_selected_candidate_index"], 31)
        self.assertEqual(handoff["q83_selected_K"], 573_440)
        self.assertEqual(
            handoff["q83_selected_history_prefix_sha256"],
            SCREEN.EXPECTED_Q83_SELECTED_HISTORY_PREFIX_SHA256,
        )
        tamper_cases = {
            "prefix common": lambda item: item["records"][0].__setitem__("stage_index", 99),
            "prefix candidate": lambda item: item["records"][1]["candidate_records"][0].__setitem__("drop_ticks", "9"),
            "q83 appended count": lambda item: item["records"][82]["candidate_records"][31].__setitem__("dropped_term_count", 78_577),
            "q83 selected": lambda item: item["records"][82].__setitem__("selected_K", 557_056),
            "history": lambda item: item["selected_K_history"].__setitem__(82, 557_056),
        }
        for label, mutate in tamper_cases.items():
            with self.subTest(label=label):
                tampered = synthetic_parent_result()
                mutate(tampered)
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(tampered, predecessor)

        missing_commit = synthetic_parent_result()
        missing_commit["records"][82].pop("selected_dropped_terms_sha256")
        missing_commit["records_sha256"] = digest(missing_commit["records"])
        with self.assertRaisesRegex(RuntimeError, "field schema drift"):
            SCREEN.validate_replay_handoff(missing_commit, predecessor)

        extra_field = synthetic_parent_result()
        extra_field["records"][82]["untrusted_propagation_note"] = "forged"
        extra_field["records_sha256"] = digest(extra_field["records"])
        with self.assertRaisesRegex(RuntimeError, "field schema drift"):
            SCREEN.validate_replay_handoff(extra_field, predecessor)

        missing_continuity = synthetic_parent_result()
        missing_continuity["records"][82].pop("retained_expansion_sha256")
        missing_continuity["records"][83].pop("input_expansion_sha256")
        missing_continuity["records_sha256"] = digest(
            missing_continuity["records"]
        )
        missing_continuity["failure_record_sha256"] = digest(
            missing_continuity["records"][83]
        )
        with self.assertRaisesRegex(RuntimeError, "field schema drift"):
            SCREEN.validate_replay_handoff(missing_continuity, predecessor)

        successful = synthetic_parent_result()
        q84 = successful["records"][83]
        for key in (
            "minimum_effective_K_to_meet_prefix",
            "required_K_excess_over_policy_maximum",
            "maximum_candidate_drop_excess_over_slack_ticks",
        ):
            q84.pop(key)
        selected = q84["candidate_records"][31]
        selected["drop_ticks"] = "0"
        selected["E_after_if_selected_ticks"] = q84["E_before_ticks"]
        selected["feasible_under_current_prefix_cap"] = True
        q84.update({
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            "selected_candidate_index": 31,
            "selected_K": SCREEN.K573440,
            "selected_effective_retained_count": selected["effective_retained_count"],
            "selected_dropped_term_count": selected["dropped_term_count"],
            "selected_drop_ticks": "0",
            "selected_dropped_terms_sha256": "3" * 64,
            "retained_expansion_count": selected["effective_retained_count"],
            "retained_expansion_sha256": "4" * 64,
            "minimum_retained_abs_upper_ticks": "1",
            "maximum_dropped_abs_upper_ticks": "1",
            "E_after_ticks": q84["E_before_ticks"],
        })
        successful["selected_K_history"].append(SCREEN.K573440)
        successful["records_sha256"] = digest(successful["records"])
        successful["selected_K_history_sha256"] = digest(
            successful["selected_K_history"]
        )
        successful["completed_checkpoint_count"] = 84
        successful["screen_terminal_condition"] = "DIAGNOSTIC_HORIZON_REACHED"
        successful["failure_checkpoint_included"] = False
        successful["failure_record_sha256"] = None
        successful["horizon_reached_with_committed_checkpoint"] = True
        successful["last_committed_cumulative_drop_ticks"] = q84["E_after_ticks"]
        self.assertFalse(
            SCREEN.validate_replay_handoff(successful, predecessor)[
                "q84_outcome_precommitted"
            ]
        )

        forged_failure = synthetic_parent_result()
        forged_failure["failure_checkpoint_included"] = False
        with self.assertRaisesRegex(RuntimeError, "failure summary drift"):
            SCREEN.validate_replay_handoff(forged_failure, predecessor)

        forged_success = synthetic_parent_result()
        forged_success["records"][83] = {
            "checkpoint_index_zero_based": 83,
            "checkpoint_number_one_based": 84,
            "input_expansion_count": SCREEN.K573440,
            "input_expansion_sha256": forged_success["records"][82][
                "retained_expansion_sha256"
            ],
            "E_before_ticks": forged_success["records"][82]["E_after_ticks"],
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
        }
        forged_success["selected_K_history"].append(123)
        forged_success["records_sha256"] = digest(forged_success["records"])
        forged_success["selected_K_history_sha256"] = digest(
            forged_success["selected_K_history"]
        )
        forged_success["completed_checkpoint_count"] = 84
        with self.assertRaisesRegex(RuntimeError, "expansion count type drift"):
            SCREEN.validate_replay_handoff(forged_success, predecessor)

    def test_07_synthetic_relabel_provenance_is_layered_and_diagnostic(self):
        fresh = SCREEN.fresh_self_module()
        predecessor, reference = fresh.load_route_predecessor_reference(HERE)
        _configuration, baseline_m = fresh.load_configured_v6_baseline(HERE)
        _wrapper, wrapper_sha, manifest = fresh.load_kernel_wrapper(HERE)
        result = fresh.validate_and_relabel(
            synthetic_parent_result(),
            predecessor,
            reference,
            baseline_m,
            wrapper_sha,
            manifest,
            {"changed_fields": ["MODE_CONFIG.magnetization.horizon_checkpoint_count"]},
        )
        self.assertEqual(
            result["transcript_fingerprint"],
            "hubbard_l8_magnetization_adaptive_k_four_gate_k573440_c32_q84_screen_v1",
        )
        self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertTrue(result["control_flow_parent_private_entrypoint_called"])
        self.assertFalse(result["control_flow_owned_by_screen"])
        paths = [item["relative_path"] for item in result["screen_execution_components"]]
        self.assertIn(SCREEN.CONTROL_FLOW_PARENT_NAME, paths)
        self.assertIn(SCREEN.KERNEL_WRAPPER_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, paths)
        self.assertNotIn("hubbard_l8_adaptive_k_arithmetic_k557056.py", paths)
        route = result["route_predecessor_reference"]
        self.assertFalse(route["screen"]["compiled"])
        self.assertFalse(route["screen"]["executed"])
        self.assertFalse(route["canonical_transcript"]["propagation_input"])
        self.assertFalse(route["canonical_transcript"]["state_resume_input"])
        self.assertFalse(route["q82_ancestry"]["compiled"])
        self.assertFalse(route["q82_ancestry"]["executed"])
        self.assertFalse(route["q82_ancestry"]["state_resume_input"])
        for key, value_key in (
            ("screen_execution_components_sha256", "screen_execution_components"),
            ("configuration_reference_sha256", "configuration_reference"),
            ("configuration_override_sha256", "configuration_override"),
            ("kernel_capability_override_sha256", "kernel_capability_override"),
            ("route_predecessor_reference_sha256", "route_predecessor_reference"),
            ("predecessor_handoff_validation_sha256", "predecessor_handoff_validation"),
            ("checkpoint_transform_sha256", "checkpoint_transform"),
        ):
            self.assertEqual(result[key], digest(result[value_key]))
        self.assertFalse(result["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(result["child_boundary_committed"])
        self.assertFalse(result["positive_artifact_generated"])
        injected = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        injected.append({
            "relative_path": "untrusted_execution_parent.py",
            "role": "execution_source",
            "sha256": "0" * 64,
        })
        with self.assertRaisesRegex(RuntimeError, "component schema drift"):
            SCREEN.execution_components(injected, "0" * 64, wrapper_sha)
        duplicated = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        duplicated.append(copy.deepcopy(duplicated[0]))
        with self.assertRaisesRegex(RuntimeError, "duplicate parent"):
            SCREEN.execution_components(duplicated, "0" * 64, wrapper_sha)

    def test_08_atomic_output_is_bounded_and_failure_preserving(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "transcript.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "exact bytes"):
                SCREEN.write_atomic_bounded(output, bytearray(b"[]"))
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "output byte cap"):
                SCREEN.write_atomic_bounded(output, b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1))
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

    def test_09_canonical_transcript_ledger_if_present(self):
        path = HERE / SCREEN.OUTPUT_NAME
        if not path.exists():
            self.skipTest("canonical q84 result requires opt-in replay")
        raw = path.read_bytes()
        transcript = json.loads(raw)
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertLessEqual(len(raw), SCREEN.MAX_OUTPUT_BYTES)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         EXPECTED_CANONICAL["file_sha256"])
        self.assertEqual(transcript["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(transcript["candidate_K_values"], list(SCREEN.M_CANDIDATES))
        self.assertEqual(transcript["candidate_K_values_sha256"],
                         EXPECTED_CANONICAL["candidate_sha256"])
        exact_fields = {
            "records_sha256": "records_sha256",
            "selected_K_history_sha256": "history_sha256",
            "failure_record_sha256": "failure_sha256",
            "screen_execution_components_sha256": "components_sha256",
            "configuration_reference_sha256": "configuration_reference_sha256",
            "configuration_override_sha256": "configuration_override_sha256",
            "kernel_capability_override_sha256": "kernel_override_sha256",
            "parent_horizon_override_sha256": "parent_horizon_override_sha256",
            "route_predecessor_reference_sha256": "route_reference_sha256",
            "predecessor_handoff_validation_sha256": "handoff_sha256",
            "checkpoint_transform_sha256": "transform_sha256",
        }
        for transcript_field, expected_field in exact_fields.items():
            self.assertEqual(
                transcript[transcript_field],
                EXPECTED_CANONICAL[expected_field],
                transcript_field,
            )
        self.assertEqual(transcript["attempted_checkpoint_count"], 84)
        self.assertEqual(transcript["completed_checkpoint_count"], 83)
        self.assertEqual(
            transcript["screen_terminal_condition"],
            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        )
        self.assertTrue(transcript["failure_checkpoint_included"])
        self.assertFalse(transcript["horizon_reached_with_committed_checkpoint"])
        self.assertEqual(len(transcript["records"]), 84)
        self.assertEqual(len(transcript["selected_K_history"]), 83)
        self.assertEqual(
            transcript["last_committed_cumulative_drop_ticks"],
            EXPECTED_CANONICAL["last_E"],
        )
        self.assertEqual(transcript["observed_peak_single_expansion_terms"],
                         EXPECTED_CANONICAL["peak"])
        self.assertEqual(
            transcript["observed_term_gate_visits_including_terminal_attempt"],
            EXPECTED_CANONICAL["visits"],
        )
        self.assertEqual(
            transcript["observed_maximum_expansion_coefficient_tick_bits"],
            EXPECTED_CANONICAL["coefficient_bits"],
        )
        self.assertEqual(transcript["observed_maximum_product_bits"],
                         EXPECTED_CANONICAL["product_bits"])
        self.assertEqual(
            transcript["observed_rounding_cumulative_scaled_ticks_squared"],
            EXPECTED_CANONICAL["rounding"],
        )
        predecessor = load_predecessor()
        SCREEN.validate_replay_handoff(transcript, predecessor)
        self.assertEqual(
            transcript["selected_K_history"][:82],
            predecessor["selected_K_history"],
        )
        q83 = transcript["records"][82]
        self.assertEqual(q83["checkpoint_number_one_based"], 83)
        self.assertEqual(q83["pretruncation_expansion_count"], 652_016)
        self.assertEqual(q83["prefix_slack_before_selection_ticks"],
                         "133727664071")
        self.assertEqual(q83["selected_candidate_index"], 31)
        self.assertEqual(q83["selected_K"], 573_440)
        self.assertEqual(q83["selected_drop_ticks"], "49417284097")
        self.assertEqual(q83["selected_dropped_term_count"], 78_576)
        self.assertEqual(q83["E_after_ticks"], EXPECTED_CANONICAL["last_E"])
        q84 = transcript["records"][83]
        self.assertEqual(q84["checkpoint_number_one_based"], 84)
        self.assertEqual(q84["gate_occurrence_first_zero_based"], 332)
        self.assertEqual(q84["gate_occurrence_last_zero_based"], 335)
        self.assertEqual(q84["stage_group"], "HU")
        self.assertEqual(q84["stage_index"], 2)
        self.assertEqual(q84["batch_in_stage"], 27)
        self.assertEqual(q84["input_expansion_count"], 573_440)
        self.assertEqual(q84["pretruncation_expansion_count"], 694_130)
        self.assertEqual(q84["budget_prefix_cap_ticks"], "1700277307664702")
        self.assertEqual(q84["prefix_slack_before_selection_ticks"],
                         "188841785646")
        self.assertEqual(q84["minimum_effective_K_to_meet_prefix"], 586_381)
        self.assertEqual(q84["required_K_excess_over_policy_maximum"], 12_941)
        self.assertEqual(
            q84["maximum_candidate_drop_excess_over_slack_ticks"],
            "177725804621",
        )
        final_row = q84["candidate_records"][-1]
        self.assertEqual(final_row["candidate_index"], 31)
        self.assertEqual(final_row["configured_K"], 573_440)
        self.assertEqual(final_row["drop_ticks"], "366567590267")
        self.assertEqual(final_row["dropped_term_count"], 120_690)
        self.assertFalse(final_row["feasible_under_current_prefix_cap"])
        maximum_drop = (1 << 64) // 4000
        E_input = int(transcript["input_cumulative_drop_ticks"])
        denominator = transcript["future_checkpoint_denominator"]
        cumulative = E_input
        history = []
        for q, record in enumerate(transcript["records"], 1):
            cap = E_input + q * (maximum_drop - E_input) // denominator
            self.assertEqual(record["checkpoint_number_one_based"], q)
            self.assertEqual(int(record["budget_prefix_cap_ticks"]), cap)
            self.assertEqual(int(record["E_before_ticks"]), cumulative)
            rows = record["candidate_records"]
            self.assertEqual([row["configured_K"] for row in rows], list(SCREEN.M_CANDIDATES))
            feasible = []
            drops = []
            for index, row in enumerate(rows):
                drop = int(row["drop_ticks"])
                drops.append(drop)
                self.assertEqual(row["candidate_index"], index)
                self.assertEqual(int(row["E_after_if_selected_ticks"]), cumulative + drop)
                expected = cumulative + drop <= cap
                self.assertIs(row["feasible_under_current_prefix_cap"], expected)
                if expected:
                    feasible.append(index)
            self.assertEqual(drops, sorted(drops, reverse=True))
            if record["status"] == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
                selected = feasible[0]
                self.assertEqual(record["selected_candidate_index"], selected)
                cumulative += drops[selected]
                self.assertEqual(int(record["E_after_ticks"]), cumulative)
                history.append(SCREEN.M_CANDIDATES[selected])
            else:
                self.assertFalse(feasible)
        self.assertEqual(history, transcript["selected_K_history"])

    def test_10_scope_is_diagnostic_only(self):
        source = (HERE / SCREEN_NAME).read_text()
        for forbidden in (
            "dual_screen_checker",
            "formal_witness",
            "boundary_sidecar",
            "READY_FOR_BENCHMARK",
            "traceback",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("candidate_policy_precommitted_at_probe_time", source)
        self.assertIn("positive_artifact_generated", source)

    @unittest.skipUnless(
        os.environ.get("RUN_HUBBARD_L8_M_K573440_C32_Q84_REPLAY") == "1",
        "expensive deterministic q84 replay is opt-in",
    )
    def test_11_real_replay_is_opt_in(self):
        result = SCREEN.run(HERE)
        self.assertEqual(result["attempted_checkpoint_count"], 84)
        self.assertIn(result["completed_checkpoint_count"], (83, 84))
        self.assertEqual(result["selected_K_history"][82], 573_440)


if __name__ == "__main__":
    unittest.main()
