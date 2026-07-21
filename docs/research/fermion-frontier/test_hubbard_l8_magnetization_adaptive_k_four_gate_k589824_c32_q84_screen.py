#!/usr/bin/env python3
"""Static and synthetic tests for the M K589824/C32 q84 screen."""

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
    "k589824_c32_q84_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "594f03e397c5887df335d05971297a1d00e06b1ea19140003e7842a5ca897fb0"
)
EXPECTED_CANONICAL = {
    "file_size_bytes": 748_013,
    "file_sha256": "cf93ebcccde4ff10adee2e600a13ef1c0f979e89fe151fca16d4eae79da2420f",
    "top_level_key_count": 94,
    "record_count": 84,
    "candidate_row_count": 32,
    "total_candidate_row_count": 2_688,
    "component_count": 11,
    "custody_count": 10,
    "candidate_sha256": "94c062a2f562b7ce9e095ce9585ac4087b7bfef2af492b45762ca5d732ae9b80",
    "records_sha256": "2e1c35996258d985ee4808e2e86235ce004de0e4d843043bec71a29fe12f8a32",
    "history_sha256": "ba0a38f3cdf13114aaa7e00f2889bc221ad7afa1b42d038cc4a4ed710a21df5c",
    "failure_sha256": None,
    "components_sha256": "d06e3651d1a645e296a29dc82f6fbbb05a6d790e674c78c43649bc94bb423f41",
    "configuration_reference_sha256": "a4d0b5a8736f2ffba7f83bf90685b5ce57920dee5028f9949159d5c3110a2138",
    "configuration_override_sha256": "217273e8b2918b5b56544d9db4ef862a2be7c5c0cd0bc2657fe92837ab3b0f72",
    "kernel_override_sha256": "99e98aa38690973611ac376f997f24b7ddba37f431027751e62e3241b4cca019",
    "parent_horizon_override_sha256": "c0d860b56e0d4fb9c29e0227f4e8801a3d89d2e7e62de7945fd53075557aa924",
    "route_reference_sha256": "4ce409275ca09feb675278ee033ca4966b9c2b90d15cab46a97f1b1a6d71774c",
    "handoff_sha256": "3555e090193a1df52ec56a9236086aac3a72408c2de25950fe9209b22e5194fb",
    "transform_sha256": "b9c59f7a0f07b27292e50595c01d027dbf7e5d860792e3ca180a5ba4f0135361",
    "source_custody_sha256": "7eb06bdf58ff5303bf8cd1d9bc08c169340365230e207514ab43e9deac199006",
    "policy_caps_sha256": "b29dd116b68d3cfc32142368abcc58109536d5fbd0efd83f00b08f8c24fbd00a",
    "sequence_sha256": "6856197e9f50ef42036e2097dcb36ae4d48049cd3c8ad93885d0e6dd2ba726a7",
    "arithmetic_commit_sha256": "d20271851f9f11f3c9a23bbf1b4a461ae22f0f84f9011ea177d345cc14b96c2d",
    "input_boundary_custody_sha256": "ffea6f3b7f6e9d02ca6328727e9a2fce51d5f0e48efbf013c48e0b09be0a627d",
    "root_globals_sha256": "4a6a1f974f485a636062bec3b50030856728c581a33c155821214a83f12736d6",
    "kernel_limits_sha256": "c64a6feea0557a8668614a4076b249e88e2df8a090371e1701f06a9c1cf7e34e",
    "q83_record_sha256": "2694da34f21f9679d6076ed9d657ab87208c47896dd0bc63e4f80e137eb33840",
    "q83_rows_sha256": "d15fbbbf4c012b4bbc9d87045f24143727da8dd42becf76fe2bf95a8b2cbc62a",
    "q84_record_sha256": "ed97e80cc71f6738865abf849e7fc722f42429bb7acf6a5f93f1ec319cc291fa",
    "q84_rows_sha256": "4ee3094b55c50770667572e1ff3274ef2ef6268cea969cb03c5afa5eceedf72e",
    "all_candidate_rows_sha256": "1977a6505d828a900baa26099515214e27b18f2fd6f8a6ac354345c0de00170b",
    "selected_indices_sha256": "b7330885358789963e7d36b8b0c9beee32fd630aba6df3726557a2f640e9583f",
    "last_E": "1700230728891281",
    "peak": 694_130,
    "visits": 96_423_989,
    "coefficient_bits": 57,
    "product_bits": 121,
    "rounding": "136134157765376532642684017",
    "q84_input_count": 573_440,
    "q84_input_sha256": "3f1d6ed2ceaf852c812050697a4304e519ee51dedd146c8a21bfcbe9b929e2ee",
    "q84_pretruncation_count": 694_130,
    "q84_pretruncation_sha256": "8a94047240887ad36b304aead80ea0d2797f86539eaa5986cebed38b1b4800f8",
    "q84_ranked_suffix_sha256": "c952bc468c9723a115a96e7d29a9bbe37b7c863d3daddd7a8b6922aa12d3b2b6",
    "q84_gate_batch_sha256": "f4ca4e8e21afaba023ce05219980246219c4a2200c8ee3d6a0fd71384af8be64",
    "q84_E_before_ticks": "1700088465879056",
    "q84_budget_prefix_cap_ticks": "1700277307664702",
    "q84_prefix_slack_ticks": "188841785646",
    "q84_selected_drop_ticks": "142263012225",
    "q84_selected_dropped_term_count": 104_306,
    "q84_selected_dropped_terms_sha256": "688be370068519de85f640b3fd357773aac54ad60713bb48ae005d2416fc7f38",
    "q84_retained_expansion_sha256": "35971741409db21c05aaffcda87ef034a5eebe2199f3ba4b03e62c12bbc24eba",
    "q84_minimum_retained_abs_upper_ticks": "11595697",
    "q84_maximum_dropped_abs_upper_ticks": "11593412",
    "q84_rounding_increment": "4946447685197593922339623",
    "q84_visits_increment": 2_458_778,
}


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("m_k589824_c32_q84_screen", SCREEN_NAME)


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
    return json.loads(
        (HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes()
    )


def mapped_rows(old_record):
    rows = []
    for new_index, old_row in enumerate(old_record["candidate_records"][1:]):
        row = copy.deepcopy(old_row)
        row["candidate_index"] = new_index
        rows.append(row)
    return rows


def appended_row(record, *, drop_ticks=0):
    pre_count = record["pretruncation_expansion_count"]
    effective = min(SCREEN.K589824, pre_count)
    E_after = int(record["E_before_ticks"]) + drop_ticks
    return {
        "candidate_index": 31,
        "configured_K": SCREEN.K589824,
        "effective_retained_count": effective,
        "dropped_term_count": pre_count - effective,
        "drop_ticks": str(drop_ticks),
        "E_after_if_selected_ticks": str(E_after),
        "feasible_under_current_prefix_cap": (
            E_after <= int(record["budget_prefix_cap_ticks"])
        ),
    }


def synthetic_parent_result():
    predecessor = load_predecessor()
    records = []
    for old in predecessor["records"][:83]:
        new = copy.deepcopy(old)
        new["candidate_records"] = mapped_rows(old) + [appended_row(old)]
        new["selected_candidate_index"] = old["selected_candidate_index"] - 1
        records.append(new)

    old_q84 = predecessor["records"][83]
    q84 = {
        key: copy.deepcopy(value)
        for key, value in old_q84.items()
        if key not in {
            "candidate_records",
            "status",
            "selected_candidate_index",
            "selected_K",
            *SCREEN.FAILURE_ONLY_RECORD_KEYS,
        }
    }
    q84["candidate_records"] = mapped_rows(old_q84) + [
        appended_row(old_q84)
    ]
    selected = q84["candidate_records"][31]
    q84.update({
        "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
        "selected_candidate_index": 31,
        "selected_K": SCREEN.K589824,
        "selected_effective_retained_count": SCREEN.K589824,
        "selected_dropped_term_count": 104_306,
        "selected_drop_ticks": selected["drop_ticks"],
        "selected_dropped_terms_sha256": "3" * 64,
        "retained_expansion_count": SCREEN.K589824,
        "retained_expansion_sha256": "4" * 64,
        "minimum_retained_abs_upper_ticks": "1",
        "maximum_dropped_abs_upper_ticks": "1",
        "E_after_ticks": selected["E_after_if_selected_ticks"],
    })
    records.append(q84)
    history = copy.deepcopy(predecessor["selected_K_history"]) + [
        SCREEN.K589824
    ]

    result = {
        key: copy.deepcopy(predecessor[key])
        for key in SCREEN.EXPECTED_PARENT_RESULT_KEYS
    }
    components = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
    configuration = {"synthetic_parent_configuration": True}
    transform = {"synthetic_parent_transform": True}
    result.update({
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
        ),
        "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
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
        "kernel_capability_limits": (
            SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        ),
        "records": records,
        "records_sha256": digest(records),
        "selected_K_history": history,
        "selected_K_history_sha256": digest(history),
        "attempted_checkpoint_count": 84,
        "completed_checkpoint_count": 84,
        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
        "failure_checkpoint_included": False,
        "failure_record_sha256": None,
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": True,
        "last_committed_cumulative_drop_ticks": q84["E_after_ticks"],
        "screen_execution_components": components,
        "screen_execution_components_sha256": digest(components),
        "configuration_reference": configuration,
        "configuration_reference_sha256": digest(configuration),
        "checkpoint_transform": transform,
        "checkpoint_transform_sha256": digest(transform),
        "source_custody": copy.deepcopy(SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY),
    })
    return result


class MagnetizationK589824C32Q84ScreenTests(unittest.TestCase):
    def test_01_exact_source_wrapper_and_route_pins(self):
        exact = {
            SCREEN.CONTROL_FLOW_PARENT_NAME: (
                SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256
            ),
            SCREEN.V6_BASELINE_CONFIGURATION_NAME: (
                SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
            ),
            SCREEN.V2_ARITHMETIC_NAME: SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
            SCREEN.KERNEL_WRAPPER_NAME: SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME: (
                SCREEN.EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256
            ),
        }
        for filename, expected in exact.items():
            self.assertEqual(
                hashlib.sha256((HERE / filename).read_bytes()).hexdigest(),
                expected,
            )
        self.assertEqual(
            hashlib.sha256(
                (HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes()
            ).hexdigest(),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((HERE / SCREEN_NAME).read_bytes()).hexdigest(),
            EXPECTED_SCREEN_SHA256,
        )
        fresh = SCREEN.fresh_self_module()
        self.assertEqual(
            fresh._VERIFIED_SELF_SOURCE_BYTES,
            (HERE / SCREEN_NAME).read_bytes(),
        )

    def test_02_candidate_replacement_caps_and_horizon_are_exact(self):
        SCREEN.validate_local_configuration()
        self.assertEqual(len(SCREEN.V6_M_CANDIDATES), 29)
        self.assertEqual(len(SCREEN.PREDECESSOR_M_CANDIDATES), 32)
        self.assertEqual(len(SCREEN.M_CANDIDATES), 32)
        self.assertEqual(
            SCREEN.M_CANDIDATES,
            SCREEN.PREDECESSOR_M_CANDIDATES[1:] + (SCREEN.K589824,),
        )
        self.assertEqual(SCREEN.PREDECESSOR_M_CANDIDATES[0], SCREEN.K65536)
        self.assertNotIn(SCREEN.K65536, SCREEN.M_CANDIDATES)
        self.assertEqual(
            digest(list(SCREEN.M_CANDIDATES)),
            SCREEN.EXPECTED_CANDIDATE_SHA256,
        )
        self.assertEqual(
            SCREEN.changed_mapping_keys(
                SCREEN.EXPECTED_PREDECESSOR_POLICY_CAPS,
                SCREEN.POLICY_CAPS_BASE,
            ),
            {"max_candidate_K", "max_output_terms_if_successful"},
        )
        self.assertEqual(
            SCREEN.POLICY_CAPS_BASE["max_candidate_K"], SCREEN.K589824
        )
        configuration, baseline_m = SCREEN.load_configured_v6_baseline(HERE)
        self.assertEqual(tuple(baseline_m), SCREEN.V6_M_CANDIDATES)
        self.assertEqual(
            tuple(configuration.MODE_CONFIG[SCREEN.MODE]["candidates"]),
            SCREEN.M_CANDIDATES,
        )
        parent = SCREEN.load_control_flow_parent(HERE)
        before = copy.deepcopy(parent.MODE_CONFIG)
        wrapper, _sha, _manifest = SCREEN.load_kernel_wrapper(HERE)
        horizon = SCREEN.configure_parent_execution(
            parent, configuration, wrapper
        )
        self.assertEqual(
            horizon["changed_fields"],
            ["MODE_CONFIG.magnetization.horizon_checkpoint_count"],
        )
        self.assertEqual(before[SCREEN.MODE]["horizon_checkpoint_count"], 80)
        self.assertEqual(
            parent.MODE_CONFIG[SCREEN.MODE]["horizon_checkpoint_count"], 84
        )
        self.assertEqual(
            parent.MODE_CONFIG["double_occupancy"],
            before["double_occupancy"],
        )

    def test_03_wrapper_authority_and_reference_nonexecution(self):
        wrapper, wrapper_sha, manifest = SCREEN.load_kernel_wrapper(HERE)
        self.assertEqual(wrapper_sha, SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256)
        self.assertEqual(
            wrapper.RESOURCE_LIMITS,
            SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        )
        self.assertEqual(wrapper.RESOURCE_LIMITS["max_candidate_count"], 32)
        self.assertEqual(wrapper.RESOURCE_LIMITS["max_retained_K"], 589_824)
        self.assertEqual(
            [item["relative_path"] for item in manifest["source_layers"]],
            [SCREEN.KERNEL_WRAPPER_NAME, SCREEN.V2_ARITHMETIC_NAME],
        )
        self.assertEqual(
            digest(manifest["source_layers"]),
            SCREEN.EXPECTED_KERNEL_SOURCE_LAYERS_SHA256,
        )
        route = manifest["route_predecessor_reference"]
        cross = manifest["cross_route_reference"]
        self.assertEqual(
            digest(route), SCREEN.EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256
        )
        self.assertEqual(
            digest(cross), SCREEN.EXPECTED_KERNEL_CROSS_ROUTE_REFERENCE_SHA256
        )
        for reference in (route, cross):
            self.assertFalse(reference["compiled"])
            self.assertFalse(reference["executed"])
            self.assertFalse(reference["execution_source_layer"])
        capability = SCREEN.kernel_capability_override(wrapper_sha, manifest)
        self.assertEqual(
            capability["execution_source_layers"],
            [SCREEN.KERNEL_WRAPPER_NAME, SCREEN.V2_ARITHMETIC_NAME],
        )
        self.assertFalse(capability["route_predecessor_is_execution_source"])

    def test_04_private_root_parent_path_and_exception_identity(self):
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
                configured = parent.load_v6_configuration(inner_repo)
                observed["candidates"] = configured.MODE_CONFIG[mode][
                    "candidates"
                ]
                helper = parent.load_v2_helper(inner_repo)
                active, _root, _modules, _custody = (
                    parent.load_execution_sources(inner_repo, helper, mode)
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
        self.assertEqual(observed["candidates"], SCREEN.M_CANDIDATES)
        self.assertEqual(
            observed["limits"],
            SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        )

        resource_error = RuntimeError("resource identity")
        failing = SCREEN.fresh_self_module()
        failing_original = failing.load_control_flow_parent

        def load_failing_parent(repo):
            parent = failing_original(repo)

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

    def test_06_predecessor_is_closed_exact_post_replay_reference(self):
        predecessor, reference = SCREEN.load_route_predecessor_reference(HERE)
        self.assertEqual(
            frozenset(predecessor), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS
        )
        self.assertEqual(len(predecessor["records"]), 84)
        self.assertEqual(len(predecessor["selected_K_history"]), 83)
        self.assertNotIn(SCREEN.K65536, predecessor["selected_K_history"])
        removed_rows = []
        for checkpoint_index, record in enumerate(predecessor["records"]):
            expected = (
                SCREEN.SUCCESS_RECORD_KEYS
                if checkpoint_index < 83
                else SCREEN.FAILURE_RECORD_KEYS
            )
            self.assertEqual(frozenset(record), expected)
            self.assertEqual(len(record["candidate_records"]), 32)
            for row in record["candidate_records"]:
                self.assertEqual(frozenset(row), SCREEN.CANDIDATE_RECORD_KEYS)
            removed = record["candidate_records"][0]
            self.assertEqual(removed["configured_K"], SCREEN.K65536)
            self.assertFalse(removed["feasible_under_current_prefix_cap"])
            removed_rows.append(removed)
        self.assertEqual(
            digest(removed_rows), SCREEN.EXPECTED_REMOVED_K65536_ROW_SET_SHA256
        )
        self.assertEqual(
            predecessor["records"][82]["selected_candidate_index"], 31
        )
        self.assertEqual(predecessor["records"][82]["selected_K"], 573_440)
        self.assertEqual(
            predecessor["records"][83]["minimum_effective_K_to_meet_prefix"],
            586_381,
        )
        self.assertEqual(reference["relationship"], "trajectory_preserving_candidate_replacement")
        self.assertNotIn("q82_ancestry", reference)
        self.assertFalse(reference["screen"]["compiled"])
        self.assertFalse(reference["screen"]["executed"])
        self.assertFalse(reference["canonical_transcript"]["state_resume_input"])
        self.assertFalse(reference["canonical_transcript"]["execution_source_layer"])

    def test_07_synthetic_replacement_handoff_and_fail_closed_schemas(self):
        predecessor = load_predecessor()
        result = synthetic_parent_result()
        handoff = SCREEN.validate_replay_handoff(result, predecessor)
        self.assertEqual(
            handoff["route_semantics"],
            "selected_and_state_trajectory_preserving_replacement",
        )
        self.assertFalse(handoff["candidate_row_prefix_exact"])
        self.assertTrue(handoff["q1_through_q83_selected_K_history_exact"])
        self.assertTrue(
            handoff["q1_through_q83_old_indices_1_31_to_new_0_30_rows_exact"]
        )
        self.assertEqual(handoff["q83_predecessor_selected_candidate_index"], 31)
        self.assertEqual(handoff["q83_selected_candidate_index"], 30)
        self.assertEqual(handoff["q84_selected_candidate_index"], 31)
        self.assertEqual(handoff["q84_selected_K"], 589_824)
        self.assertEqual(
            handoff["selected_K_history_sha256"],
            SCREEN.EXPECTED_Q84_SUCCESS_HISTORY_SHA256,
        )
        self.assertEqual(
            handoff["selected_index_history_sha256"],
            SCREEN.EXPECTED_SELECTED_INDEX_HISTORY_SHA256,
        )
        self.assertFalse(handoff["q84_outcome_precommitted"])

        tamper_cases = {
            "state": lambda item: item["records"][0].__setitem__("stage_index", 99),
            "shift": lambda item: item["records"][1].__setitem__(
                "selected_candidate_index", 7
            ),
            "mapped row": lambda item: item["records"][2]["candidate_records"][0].__setitem__(
                "drop_ticks", "9"
            ),
            "q83 index": lambda item: item["records"][82].__setitem__(
                "selected_candidate_index", 31
            ),
            "q84 discriminator": lambda item: item["records"][83]["candidate_records"][31].__setitem__(
                "configured_K", 573_440
            ),
            "history": lambda item: item["selected_K_history"].__setitem__(83, 573_440),
        }
        for label, mutate in tamper_cases.items():
            with self.subTest(label=label):
                tampered = synthetic_parent_result()
                mutate(tampered)
                tampered["records_sha256"] = digest(tampered["records"])
                tampered["selected_K_history_sha256"] = digest(
                    tampered["selected_K_history"]
                )
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(tampered, predecessor)

        extra_top = synthetic_parent_result()
        extra_top["untrusted"] = True
        with self.assertRaisesRegex(RuntimeError, "top-level exact key-set drift"):
            SCREEN.validate_replay_handoff(extra_top, predecessor)
        missing_top = synthetic_parent_result()
        missing_top.pop("sequence")
        with self.assertRaisesRegex(RuntimeError, "top-level exact key-set drift"):
            SCREEN.validate_replay_handoff(missing_top, predecessor)
        extra_record = synthetic_parent_result()
        extra_record["records"][0]["untrusted"] = True
        extra_record["records_sha256"] = digest(extra_record["records"])
        with self.assertRaisesRegex(RuntimeError, "exact key-set drift"):
            SCREEN.validate_replay_handoff(extra_record, predecessor)
        extra_row = synthetic_parent_result()
        extra_row["records"][83]["candidate_records"][31]["untrusted"] = True
        extra_row["records_sha256"] = digest(extra_row["records"])
        with self.assertRaisesRegex(RuntimeError, "exact key-set drift"):
            SCREEN.validate_replay_handoff(extra_row, predecessor)

        forged_removed_evidence = copy.deepcopy(predecessor)
        forged_removed_evidence["records"][0]["candidate_records"][0][
            "feasible_under_current_prefix_cap"
        ] = True
        forged_removed_evidence["records_sha256"] = digest(
            forged_removed_evidence["records"]
        )
        with self.assertRaises(RuntimeError):
            SCREEN.validate_replay_handoff(
                synthetic_parent_result(), forged_removed_evidence
            )

    def test_08_synthetic_relabel_is_layered_closed_and_diagnostic(self):
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
            {
                "changed_fields": [
                    "MODE_CONFIG.magnetization.horizon_checkpoint_count"
                ]
            },
        )
        self.assertEqual(
            frozenset(result), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS
        )
        self.assertEqual(
            result["transcript_fingerprint"],
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k589824_c32_q84_screen_v1",
        )
        self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertTrue(result["control_flow_parent_private_entrypoint_called"])
        self.assertFalse(result["control_flow_owned_by_screen"])
        self.assertTrue(result["control_flow_owned_by_verified_parent"])
        self.assertFalse(result["child_boundary_committed"])
        self.assertFalse(result["positive_artifact_generated"])
        self.assertFalse(
            result["predecessor_handoff_validation"]["candidate_row_prefix_exact"]
        )
        self.assertFalse(
            result["predecessor_handoff_validation"]["q84_outcome_precommitted"]
        )
        config = result["configuration_override"]
        route = config["incremental_route_override_from_k573440_c32_q84"]
        self.assertEqual(route["candidate_count"], {"before": 32, "after": 32})
        self.assertEqual(route["candidate_ladder_removed"], [65_536])
        self.assertEqual(route["candidate_ladder_added"], [589_824])
        paths = {
            item["relative_path"] for item in result["screen_execution_components"]
        }
        self.assertIn(SCREEN_NAME, paths)
        self.assertIn(SCREEN.CONTROL_FLOW_PARENT_NAME, paths)
        self.assertIn(SCREEN.KERNEL_WRAPPER_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, paths)
        expected_custody = {
            **SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY,
            SCREEN_NAME: EXPECTED_SCREEN_SHA256,
            SCREEN.CONTROL_FLOW_PARENT_NAME: (
                SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256
            ),
            SCREEN.KERNEL_WRAPPER_NAME: SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
        }
        self.assertEqual(len(result["source_custody"]), 10)
        self.assertEqual(result["source_custody"], expected_custody)
        for field in (
            "screen_execution_components",
            "configuration_reference",
            "configuration_override",
            "kernel_capability_override",
            "parent_horizon_override",
            "route_predecessor_reference",
            "predecessor_handoff_validation",
            "checkpoint_transform",
        ):
            self.assertEqual(result[f"{field}_sha256"], digest(result[field]))

        first_parent_path = next(iter(SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY))
        custody_tamper_cases = {}
        missing = synthetic_parent_result()
        missing["source_custody"].pop(first_parent_path)
        custody_tamper_cases["missing"] = missing
        extra = synthetic_parent_result()
        extra["source_custody"]["untrusted_source.py"] = "0" * 64
        custody_tamper_cases["extra"] = extra
        wrong_hash = synthetic_parent_result()
        wrong_hash["source_custody"][first_parent_path] = "0" * 64
        custody_tamper_cases["wrong hash"] = wrong_hash
        wrong_path = synthetic_parent_result()
        old_hash = wrong_path["source_custody"].pop(first_parent_path)
        wrong_path["source_custody"]["../" + first_parent_path] = old_hash
        custody_tamper_cases["wrong path"] = wrong_path
        for label, tampered in custody_tamper_cases.items():
            with self.subTest(custody_tamper=label):
                with self.assertRaisesRegex(RuntimeError, "source custody"):
                    fresh.validate_and_relabel(
                        tampered,
                        predecessor,
                        reference,
                        baseline_m,
                        wrapper_sha,
                        manifest,
                        {
                            "changed_fields": [
                                "MODE_CONFIG.magnetization."
                                "horizon_checkpoint_count"
                            ]
                        },
                    )

    def test_09_execution_component_schema_and_atomic_output(self):
        components = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        effective = SCREEN.execution_components(
            components, EXPECTED_SCREEN_SHA256, SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256
        )
        self.assertEqual(effective[0]["relative_path"], SCREEN_NAME)
        duplicate = copy.deepcopy(components)
        duplicate.append(copy.deepcopy(duplicate[0]))
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            SCREEN.execution_components(
                duplicate,
                EXPECTED_SCREEN_SHA256,
                SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            )
        injected = copy.deepcopy(components)
        injected[0]["untrusted"] = True
        with self.assertRaisesRegex(RuntimeError, "component schema drift"):
            SCREEN.execution_components(
                injected,
                EXPECTED_SCREEN_SHA256,
                SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            )

        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary) / "transcript.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "exact bytes"):
                SCREEN.write_atomic_bounded(output, bytearray(b"{}"))
            with self.assertRaisesRegex(RuntimeError, "byte cap"):
                SCREEN.write_atomic_bounded(
                    output, b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1)
                )
            original_replace = SCREEN.os.replace

            def fail_replace(_source, _destination):
                raise OSError("synthetic replace failure")

            try:
                SCREEN.os.replace = fail_replace
                with self.assertRaisesRegex(OSError, "synthetic replace"):
                    SCREEN.write_atomic_bounded(output, b'{"new":true}')
            finally:
                SCREEN.os.replace = original_replace
            self.assertEqual(output.read_bytes(), b"{}")
            self.assertEqual(
                list(pathlib.Path(temporary).glob("transcript.json.*.tmp")), []
            )

    def test_10_canonical_transcript_and_full_84x32_ledger(self):
        canonical_path = HERE / SCREEN.OUTPUT_NAME
        self.assertTrue(canonical_path.is_file())
        raw = canonical_path.read_bytes()
        self.assertEqual(len(raw), EXPECTED_CANONICAL["file_size_bytes"])
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            EXPECTED_CANONICAL["file_sha256"],
        )
        transcript = json.loads(raw)
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertEqual(
            frozenset(transcript), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS
        )
        self.assertEqual(
            len(transcript), EXPECTED_CANONICAL["top_level_key_count"]
        )

        exact_top = {
            "schema_version": 1,
            "transcript_fingerprint": (
                "hubbard_l8_magnetization_adaptive_k_four_gate_"
                "k589824_c32_q84_screen_v1"
            ),
            "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
            "screen_source_sha256": EXPECTED_SCREEN_SHA256,
            "screen_horizon_checkpoint_count": 84,
            "attempted_checkpoint_count": 84,
            "completed_checkpoint_count": 84,
            "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
            "failure_checkpoint_included": False,
            "failure_record_sha256": EXPECTED_CANONICAL["failure_sha256"],
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": True,
            "candidate_K_values": list(SCREEN.M_CANDIDATES),
            "candidate_K_values_sha256": EXPECTED_CANONICAL[
                "candidate_sha256"
            ],
            "child_boundary_committed": False,
            "positive_artifact_generated": False,
            "candidate_policy_precommitted_at_probe_time": False,
            "diagnostic_candidate_ladder_precommitted_before_replay": True,
            "diagnostic_horizon_precommitted_before_replay": True,
            "same_byte_self_execution": True,
            "v2_run_entrypoint_called": False,
            "v6_execution_invoked": False,
            "v6_same_byte_execution_parent": False,
            "control_flow_owned_by_screen": False,
            "control_flow_owned_by_verified_parent": True,
            "control_flow_parent_private_entrypoint_called": True,
            "runtime_RSS_host_timestamp_and_float_fields_excluded": True,
        }
        for field, expected in exact_top.items():
            with self.subTest(top_field=field):
                self.assertEqual(transcript[field], expected)

        embedded_digests = (
            (
                "candidate_K_values",
                "candidate_K_values_sha256",
                "candidate_sha256",
            ),
            ("records", "records_sha256", "records_sha256"),
            (
                "selected_K_history",
                "selected_K_history_sha256",
                "history_sha256",
            ),
            (
                "screen_execution_components",
                "screen_execution_components_sha256",
                "components_sha256",
            ),
            (
                "configuration_reference",
                "configuration_reference_sha256",
                "configuration_reference_sha256",
            ),
            (
                "configuration_override",
                "configuration_override_sha256",
                "configuration_override_sha256",
            ),
            (
                "kernel_capability_override",
                "kernel_capability_override_sha256",
                "kernel_override_sha256",
            ),
            (
                "parent_horizon_override",
                "parent_horizon_override_sha256",
                "parent_horizon_override_sha256",
            ),
            (
                "route_predecessor_reference",
                "route_predecessor_reference_sha256",
                "route_reference_sha256",
            ),
            (
                "predecessor_handoff_validation",
                "predecessor_handoff_validation_sha256",
                "handoff_sha256",
            ),
            (
                "checkpoint_transform",
                "checkpoint_transform_sha256",
                "transform_sha256",
            ),
        )
        for value_field, digest_field, expected_field in embedded_digests:
            with self.subTest(nested_field=value_field):
                expected = EXPECTED_CANONICAL[expected_field]
                self.assertEqual(transcript[digest_field], expected)
                self.assertEqual(digest(transcript[value_field]), expected)

        unembedded_digests = {
            "source_custody": "source_custody_sha256",
            "proposed_policy_caps": "policy_caps_sha256",
            "sequence": "sequence_sha256",
            "arithmetic_kernel_commit": "arithmetic_commit_sha256",
            "input_boundary_custody": "input_boundary_custody_sha256",
            "root_globals_before": "root_globals_sha256",
            "root_globals_after": "root_globals_sha256",
            "kernel_capability_limits": "kernel_limits_sha256",
        }
        for value_field, expected_field in unembedded_digests.items():
            with self.subTest(unembedded_nested_field=value_field):
                self.assertEqual(
                    digest(transcript[value_field]),
                    EXPECTED_CANONICAL[expected_field],
                )

        records = transcript["records"]
        history = transcript["selected_K_history"]
        self.assertEqual(len(records), EXPECTED_CANONICAL["record_count"])
        self.assertEqual(len(history), EXPECTED_CANONICAL["record_count"])
        self.assertEqual(digest(records), EXPECTED_CANONICAL["records_sha256"])
        self.assertEqual(digest(history), EXPECTED_CANONICAL["history_sha256"])
        self.assertNotIn(SCREEN.K65536, history)

        components = transcript["screen_execution_components"]
        self.assertEqual(
            len(components), EXPECTED_CANONICAL["component_count"]
        )
        component_paths = []
        for component in components:
            self.assertEqual(
                frozenset(component), {"relative_path", "role", "sha256"}
            )
            relative = pathlib.Path(component["relative_path"])
            self.assertFalse(relative.is_absolute())
            self.assertNotIn("..", relative.parts)
            self.assertTrue(SCREEN.is_canonical_sha256(component["sha256"]))
            self.assertEqual(
                hashlib.sha256((HERE / relative).read_bytes()).hexdigest(),
                component["sha256"],
            )
            component_paths.append(component["relative_path"])
        self.assertEqual(len(component_paths), len(set(component_paths)))
        self.assertIn(SCREEN_NAME, component_paths)
        self.assertIn(SCREEN.CONTROL_FLOW_PARENT_NAME, component_paths)
        self.assertIn(SCREEN.KERNEL_WRAPPER_NAME, component_paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, component_paths)
        self.assertNotIn(
            SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, component_paths
        )

        expected_custody = {
            **SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY,
            SCREEN_NAME: EXPECTED_SCREEN_SHA256,
            SCREEN.CONTROL_FLOW_PARENT_NAME: (
                SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256
            ),
            SCREEN.KERNEL_WRAPPER_NAME: SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
        }
        self.assertEqual(
            len(transcript["source_custody"]),
            EXPECTED_CANONICAL["custody_count"],
        )
        self.assertEqual(transcript["source_custody"], expected_custody)
        for relative_path, expected_sha in expected_custody.items():
            self.assertEqual(
                hashlib.sha256((HERE / relative_path).read_bytes()).hexdigest(),
                expected_sha,
            )

        self.assertTrue(transcript["root_globals_unchanged"])
        self.assertEqual(
            transcript["root_globals_before"], transcript["root_globals_after"]
        )
        maximum_drop_ticks = (1 << 64) // 4_000
        self.assertEqual(
            transcript["maximum_cumulative_drop_ticks"],
            str(maximum_drop_ticks),
        )
        denominator = (
            transcript["remaining_mapped_steps_including_attempt"]
            * transcript["sequence"]["checkpoint_count"]
        )
        self.assertEqual(denominator, 27_936)
        self.assertEqual(transcript["future_checkpoint_denominator"], denominator)
        self.assertEqual(
            transcript["prefix_cap_formula"],
            "E3+floor(q*(B-E3)/(97*288))",
        )

        def exact_nonnegative_decimal(value):
            self.assertIs(type(value), str)
            parsed = int(value)
            self.assertGreaterEqual(parsed, 0)
            self.assertEqual(value, str(parsed))
            return parsed

        E_input = exact_nonnegative_decimal(
            transcript["input_cumulative_drop_ticks"]
        )
        previous_E = E_input
        previous_count = transcript["input_boundary_custody"]["term_count"]
        previous_sha = transcript["input_boundary_custody"]["expansion_sha256"]
        visits_cumulative = 0
        rounding_cumulative = 0
        peak_cumulative = 0
        coefficient_bits_cumulative = 0
        product_bits_cumulative = 0
        selected_indices = []
        all_candidate_rows = []
        canonical_hash_fields = (
            "input_expansion_sha256",
            "pretruncation_expansion_sha256",
            "ranked_suffix_sha256",
            "gate_batch_sha256",
            "selected_dropped_terms_sha256",
            "retained_expansion_sha256",
        )
        for checkpoint_index, record in enumerate(records):
            checkpoint_number = checkpoint_index + 1
            with self.subTest(checkpoint=checkpoint_number):
                self.assertEqual(frozenset(record), SCREEN.SUCCESS_RECORD_KEYS)
                self.assertEqual(
                    record["status"], "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
                )
                self.assertEqual(
                    record["checkpoint_index_zero_based"], checkpoint_index
                )
                self.assertEqual(
                    record["checkpoint_number_one_based"], checkpoint_number
                )
                if checkpoint_index == 0:
                    self.assertEqual(record["stage_index"], 0)
                    self.assertEqual(record["batch_in_stage"], 0)
                else:
                    previous_record = records[checkpoint_index - 1]
                    if record["stage_index"] == previous_record["stage_index"]:
                        self.assertEqual(
                            record["batch_in_stage"],
                            previous_record["batch_in_stage"] + 1,
                        )
                    else:
                        self.assertEqual(
                            record["stage_index"],
                            previous_record["stage_index"] + 1,
                        )
                        self.assertEqual(record["batch_in_stage"], 0)
                self.assertEqual(
                    record["stage_group"],
                    transcript["sequence"]["stage_groups"][
                        record["stage_index"]
                    ],
                )
                self.assertEqual(
                    record["gate_occurrence_first_zero_based"],
                    checkpoint_index * 4,
                )
                self.assertEqual(
                    record["gate_occurrence_last_zero_based"],
                    checkpoint_index * 4 + 3,
                )
                self.assertEqual(record["input_expansion_count"], previous_count)
                self.assertEqual(record["input_expansion_sha256"], previous_sha)
                for hash_field in canonical_hash_fields:
                    self.assertTrue(
                        SCREEN.is_canonical_sha256(record[hash_field]),
                        hash_field,
                    )

                E_before = exact_nonnegative_decimal(record["E_before_ticks"])
                self.assertEqual(E_before, previous_E)
                expected_cap = (
                    E_input
                    + checkpoint_number * (maximum_drop_ticks - E_input)
                    // denominator
                )
                prefix_cap = exact_nonnegative_decimal(
                    record["budget_prefix_cap_ticks"]
                )
                self.assertEqual(prefix_cap, expected_cap)
                self.assertEqual(
                    exact_nonnegative_decimal(
                        record["prefix_slack_before_selection_ticks"]
                    ),
                    prefix_cap - E_before,
                )

                pre_count = record["pretruncation_expansion_count"]
                self.assertIs(type(pre_count), int)
                self.assertGreaterEqual(pre_count, 0)
                rows = record["candidate_records"]
                self.assertEqual(
                    len(rows), EXPECTED_CANONICAL["candidate_row_count"]
                )
                drops = []
                feasible_indices = []
                for candidate_index, (configured_K, row) in enumerate(
                    zip(SCREEN.M_CANDIDATES, rows)
                ):
                    self.assertEqual(
                        frozenset(row), SCREEN.CANDIDATE_RECORD_KEYS
                    )
                    effective = min(configured_K, pre_count)
                    self.assertEqual(row["candidate_index"], candidate_index)
                    self.assertEqual(row["configured_K"], configured_K)
                    self.assertEqual(row["effective_retained_count"], effective)
                    self.assertEqual(
                        row["dropped_term_count"], pre_count - effective
                    )
                    drop = exact_nonnegative_decimal(row["drop_ticks"])
                    E_after_candidate = exact_nonnegative_decimal(
                        row["E_after_if_selected_ticks"]
                    )
                    self.assertEqual(E_after_candidate, E_before + drop)
                    feasible = E_after_candidate <= prefix_cap
                    self.assertIs(
                        row["feasible_under_current_prefix_cap"], feasible
                    )
                    drops.append(drop)
                    if feasible:
                        feasible_indices.append(candidate_index)
                self.assertEqual(drops, sorted(drops, reverse=True))
                self.assertTrue(feasible_indices)
                selected_index = record["selected_candidate_index"]
                self.assertIs(type(selected_index), int)
                self.assertEqual(selected_index, feasible_indices[0])
                self.assertEqual(
                    feasible_indices,
                    list(range(selected_index, len(SCREEN.M_CANDIDATES))),
                )
                selected_indices.append(selected_index)
                selected_row = rows[selected_index]
                selected_expected = {
                    "selected_K": selected_row["configured_K"],
                    "selected_effective_retained_count": selected_row[
                        "effective_retained_count"
                    ],
                    "selected_dropped_term_count": selected_row[
                        "dropped_term_count"
                    ],
                    "selected_drop_ticks": selected_row["drop_ticks"],
                    "retained_expansion_count": selected_row[
                        "effective_retained_count"
                    ],
                    "E_after_ticks": selected_row[
                        "E_after_if_selected_ticks"
                    ],
                }
                for field, expected in selected_expected.items():
                    self.assertEqual(record[field], expected)
                self.assertEqual(history[checkpoint_index], record["selected_K"])
                self.assertGreaterEqual(
                    exact_nonnegative_decimal(
                        record["minimum_retained_abs_upper_ticks"]
                    ),
                    exact_nonnegative_decimal(
                        record["maximum_dropped_abs_upper_ticks"]
                    ),
                )

                visits_increment = record["term_gate_visits_increment"]
                self.assertIs(type(visits_increment), int)
                self.assertGreater(visits_increment, 0)
                visits_cumulative += visits_increment
                self.assertEqual(
                    record["term_gate_visits_cumulative"], visits_cumulative
                )
                rounding_increment = exact_nonnegative_decimal(
                    record["rounding_increment_scaled_ticks_squared"]
                )
                rounding_cumulative += rounding_increment
                self.assertEqual(
                    exact_nonnegative_decimal(
                        record["rounding_cumulative_scaled_ticks_squared"]
                    ),
                    rounding_cumulative,
                )
                peak_this = record["peak_live_terms_this_checkpoint"]
                self.assertEqual(peak_this, pre_count)
                peak_cumulative = max(peak_cumulative, peak_this)
                self.assertEqual(
                    record["peak_live_terms_cumulative"], peak_cumulative
                )
                coefficient_bits = record[
                    "maximum_expansion_coefficient_tick_bits"
                ]
                product_bits = record["maximum_product_bits"]
                self.assertGreaterEqual(
                    coefficient_bits, coefficient_bits_cumulative
                )
                self.assertGreaterEqual(product_bits, product_bits_cumulative)
                coefficient_bits_cumulative = coefficient_bits
                product_bits_cumulative = product_bits

                previous_E = exact_nonnegative_decimal(record["E_after_ticks"])
                self.assertLessEqual(previous_E, prefix_cap)
                previous_count = record["retained_expansion_count"]
                previous_sha = record["retained_expansion_sha256"]
                all_candidate_rows.append(rows)

        self.assertEqual(
            sum(len(rows) for rows in all_candidate_rows),
            EXPECTED_CANONICAL["total_candidate_row_count"],
        )
        self.assertEqual(
            digest(all_candidate_rows),
            EXPECTED_CANONICAL["all_candidate_rows_sha256"],
        )
        self.assertEqual(
            digest(selected_indices),
            EXPECTED_CANONICAL["selected_indices_sha256"],
        )
        self.assertEqual(previous_E, int(EXPECTED_CANONICAL["last_E"]))
        self.assertEqual(
            transcript["last_committed_cumulative_drop_ticks"],
            EXPECTED_CANONICAL["last_E"],
        )
        observed = {
            "observed_peak_single_expansion_terms": peak_cumulative,
            "observed_term_gate_visits_including_terminal_attempt": (
                visits_cumulative
            ),
            "observed_maximum_expansion_coefficient_tick_bits": (
                coefficient_bits_cumulative
            ),
            "observed_maximum_product_bits": product_bits_cumulative,
            "observed_rounding_cumulative_scaled_ticks_squared": str(
                rounding_cumulative
            ),
        }
        for field, expected in observed.items():
            self.assertEqual(transcript[field], expected)
        self.assertEqual(peak_cumulative, EXPECTED_CANONICAL["peak"])
        self.assertEqual(visits_cumulative, EXPECTED_CANONICAL["visits"])
        self.assertEqual(
            coefficient_bits_cumulative, EXPECTED_CANONICAL["coefficient_bits"]
        )
        self.assertEqual(
            product_bits_cumulative, EXPECTED_CANONICAL["product_bits"]
        )
        self.assertEqual(
            str(rounding_cumulative), EXPECTED_CANONICAL["rounding"]
        )

        policy = transcript["proposed_policy_caps"]
        self.assertLessEqual(peak_cumulative, policy["max_single_expansion_terms"])
        self.assertLessEqual(visits_cumulative, policy["max_term_gate_visits"])
        self.assertLessEqual(
            coefficient_bits_cumulative,
            policy["max_expansion_coefficient_tick_bits"],
        )
        self.assertLessEqual(product_bits_cumulative, policy["max_product_bits"])
        self.assertLessEqual(
            max(history), policy["max_output_terms_if_successful"]
        )

        q83 = records[82]
        q84 = records[83]
        self.assertEqual(digest(q83), EXPECTED_CANONICAL["q83_record_sha256"])
        self.assertEqual(
            digest(q83["candidate_records"]),
            EXPECTED_CANONICAL["q83_rows_sha256"],
        )
        self.assertEqual(q83["selected_candidate_index"], 30)
        self.assertEqual(q83["selected_K"], 573_440)
        self.assertEqual(q83["E_after_ticks"], EXPECTED_CANONICAL["q84_E_before_ticks"])
        self.assertEqual(digest(q84), EXPECTED_CANONICAL["q84_record_sha256"])
        self.assertEqual(
            digest(q84["candidate_records"]),
            EXPECTED_CANONICAL["q84_rows_sha256"],
        )
        exact_q84 = {
            "checkpoint_index_zero_based": 83,
            "checkpoint_number_one_based": 84,
            "stage_index": 2,
            "stage_group": "HU",
            "batch_in_stage": 27,
            "gate_occurrence_first_zero_based": 332,
            "gate_occurrence_last_zero_based": 335,
            "gate_batch_sha256": EXPECTED_CANONICAL["q84_gate_batch_sha256"],
            "input_expansion_count": EXPECTED_CANONICAL["q84_input_count"],
            "input_expansion_sha256": EXPECTED_CANONICAL["q84_input_sha256"],
            "pretruncation_expansion_count": EXPECTED_CANONICAL[
                "q84_pretruncation_count"
            ],
            "pretruncation_expansion_sha256": EXPECTED_CANONICAL[
                "q84_pretruncation_sha256"
            ],
            "ranked_suffix_sha256": EXPECTED_CANONICAL[
                "q84_ranked_suffix_sha256"
            ],
            "E_before_ticks": EXPECTED_CANONICAL["q84_E_before_ticks"],
            "budget_prefix_cap_ticks": EXPECTED_CANONICAL[
                "q84_budget_prefix_cap_ticks"
            ],
            "prefix_slack_before_selection_ticks": EXPECTED_CANONICAL[
                "q84_prefix_slack_ticks"
            ],
            "selected_candidate_index": 31,
            "selected_K": SCREEN.K589824,
            "selected_effective_retained_count": SCREEN.K589824,
            "selected_dropped_term_count": EXPECTED_CANONICAL[
                "q84_selected_dropped_term_count"
            ],
            "selected_drop_ticks": EXPECTED_CANONICAL[
                "q84_selected_drop_ticks"
            ],
            "selected_dropped_terms_sha256": EXPECTED_CANONICAL[
                "q84_selected_dropped_terms_sha256"
            ],
            "retained_expansion_count": SCREEN.K589824,
            "retained_expansion_sha256": EXPECTED_CANONICAL[
                "q84_retained_expansion_sha256"
            ],
            "minimum_retained_abs_upper_ticks": EXPECTED_CANONICAL[
                "q84_minimum_retained_abs_upper_ticks"
            ],
            "maximum_dropped_abs_upper_ticks": EXPECTED_CANONICAL[
                "q84_maximum_dropped_abs_upper_ticks"
            ],
            "E_after_ticks": EXPECTED_CANONICAL["last_E"],
            "peak_live_terms_this_checkpoint": EXPECTED_CANONICAL["peak"],
            "peak_live_terms_cumulative": EXPECTED_CANONICAL["peak"],
            "term_gate_visits_increment": EXPECTED_CANONICAL[
                "q84_visits_increment"
            ],
            "term_gate_visits_cumulative": EXPECTED_CANONICAL["visits"],
            "rounding_increment_scaled_ticks_squared": EXPECTED_CANONICAL[
                "q84_rounding_increment"
            ],
            "rounding_cumulative_scaled_ticks_squared": EXPECTED_CANONICAL[
                "rounding"
            ],
            "maximum_expansion_coefficient_tick_bits": EXPECTED_CANONICAL[
                "coefficient_bits"
            ],
            "maximum_product_bits": EXPECTED_CANONICAL["product_bits"],
        }
        for field, expected in exact_q84.items():
            with self.subTest(q84_field=field):
                self.assertEqual(q84[field], expected)
        self.assertEqual(
            [
                index
                for index, row in enumerate(q84["candidate_records"])
                if row["feasible_under_current_prefix_cap"]
            ],
            [31],
        )
        self.assertEqual(
            q84["candidate_records"][31],
            {
                "candidate_index": 31,
                "configured_K": SCREEN.K589824,
                "effective_retained_count": SCREEN.K589824,
                "dropped_term_count": EXPECTED_CANONICAL[
                    "q84_selected_dropped_term_count"
                ],
                "drop_ticks": EXPECTED_CANONICAL["q84_selected_drop_ticks"],
                "E_after_if_selected_ticks": EXPECTED_CANONICAL["last_E"],
                "feasible_under_current_prefix_cap": True,
            },
        )

        predecessor, _reference = SCREEN.load_route_predecessor_reference(HERE)
        handoff = SCREEN.validate_replay_handoff(transcript, predecessor)
        self.assertEqual(handoff, transcript["predecessor_handoff_validation"])
        self.assertEqual(digest(handoff), EXPECTED_CANONICAL["handoff_sha256"])
        for checkpoint_index, (old, new) in enumerate(
            zip(predecessor["records"], records)
        ):
            old_rows = old["candidate_records"]
            new_rows = new["candidate_records"]
            self.assertEqual(old_rows[0]["configured_K"], SCREEN.K65536)
            self.assertFalse(
                old_rows[0]["feasible_under_current_prefix_cap"]
            )
            for new_index, (old_row, new_row) in enumerate(
                zip(old_rows[1:], new_rows[:31])
            ):
                normalized_old = copy.deepcopy(old_row)
                normalized_old["candidate_index"] = new_index
                self.assertEqual(new_row, normalized_old)
            self.assertEqual(new_rows[31]["candidate_index"], 31)
            self.assertEqual(new_rows[31]["configured_K"], SCREEN.K589824)
            if checkpoint_index < 83:
                old_common = {
                    key: value for key, value in old.items()
                    if key not in {"candidate_records", "selected_candidate_index"}
                }
                new_common = {
                    key: value for key, value in new.items()
                    if key not in {"candidate_records", "selected_candidate_index"}
                }
                self.assertEqual(new_common, old_common)
                self.assertEqual(
                    new["selected_candidate_index"],
                    old["selected_candidate_index"] - 1,
                )
            else:
                excluded = {
                    "candidate_records",
                    "status",
                    "selected_candidate_index",
                    "selected_K",
                    *SCREEN.FAILURE_ONLY_RECORD_KEYS,
                }
                old_shared = {
                    key: value for key, value in old.items() if key not in excluded
                }
                self.assertEqual(
                    {key: new[key] for key in old_shared}, old_shared
                )
        self.assertEqual(history[:83], predecessor["selected_K_history"])

    @unittest.skipUnless(
        os.environ.get("RUN_M_K589824_C32_Q84_REPLAY") == "1",
        "expensive deterministic q84 replay is opt-in",
    )
    def test_11_real_replay_is_opt_in(self):
        result = SCREEN.run(HERE)
        predecessor = load_predecessor()
        handoff = SCREEN.validate_replay_handoff(result, predecessor)
        self.assertEqual(result["completed_checkpoint_count"], 84)
        self.assertEqual(result["records"][-1]["selected_K"], 589_824)
        self.assertFalse(handoff["q84_outcome_precommitted"])


if __name__ == "__main__":
    unittest.main()
