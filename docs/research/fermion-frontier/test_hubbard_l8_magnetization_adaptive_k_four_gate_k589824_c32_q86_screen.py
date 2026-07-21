#!/usr/bin/env python3
"""Static, synthetic and opt-in tests for the M K589824/C32 q86 screen."""

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
SCREEN_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k589824_c32_q86_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "002cc87d5d1a8f1908a837e8612e3a9d4a4c5ebbf68e41f841ba4a5a639ff878"
)
EXPECTED_CANONICAL = {
    "file_size_bytes": 758_536,
    "file_sha256": "c24a665d543323a0e7f28ac4023fe5ae3d54b39c4e2991cba3e70e9371d0053d",
    "candidate_sha256": "94c062a2f562b7ce9e095ce9585ac4087b7bfef2af492b45762ca5d732ae9b80",
    "records_sha256": "aa3f493f3779da261261cef49bc12654fc8e8f44889cd14a979f5c77413336c0",
    "history_sha256": "ba0a38f3cdf13114aaa7e00f2889bc221ad7afa1b42d038cc4a4ed710a21df5c",
    "failure_sha256": "5c7f0315f858635b5784cc26a8f5bcd8171805ea957b7d782692cee0ae4e1235",
    "components_sha256": "f8eddd7b546f0e8293290b9cabac6da6bcb39588b6452905657dd4293ddc8464",
    "configuration_reference_sha256": "a4d0b5a8736f2ffba7f83bf90685b5ce57920dee5028f9949159d5c3110a2138",
    "configuration_override_sha256": "b75d14b07fe59af899fb9d1cc289d58f04bd83cf91e5b10a4fbc6a762c52ea3b",
    "kernel_override_sha256": "a0e1f3e7750341a49732024034fa3853927d839e45b51a811e87df152b342d66",
    "parent_horizon_override_sha256": "28acb72f3a225fe867961936044687d3ae5556d7be70d28c0c4e68074daf9a9e",
    "route_reference_sha256": "4ea7baa4294bacb554d652da98b410239c64d5a585865564f8b813a155010527",
    "handoff_sha256": "69d5e3695fca27676a3b7b8db0e626f04a0b02c02e9d3eb086fa3494541e5c47",
    "transform_sha256": "8ce85c741f471aef368a4eb35a564f25fce5345b0aaf9b93d1ec6af997f21e57",
    "source_custody_sha256": "c7c1b66db33f03fd24e3fd74aba6b761b4918dba5706f1a83a36bb8dbb41db3e",
    "policy_caps_sha256": "b29dd116b68d3cfc32142368abcc58109536d5fbd0efd83f00b08f8c24fbd00a",
    "sequence_sha256": "6856197e9f50ef42036e2097dcb36ae4d48049cd3c8ad93885d0e6dd2ba726a7",
    "arithmetic_commit_sha256": "d20271851f9f11f3c9a23bbf1b4a461ae22f0f84f9011ea177d345cc14b96c2d",
    "input_boundary_sha256": "ffea6f3b7f6e9d02ca6328727e9a2fce51d5f0e48efbf013c48e0b09be0a627d",
    "root_globals_sha256": "4a6a1f974f485a636062bec3b50030856728c581a33c155821214a83f12736d6",
    "kernel_limits_sha256": "c64a6feea0557a8668614a4076b249e88e2df8a090371e1701f06a9c1cf7e34e",
    "parent_witness_sha256": "e5a1fec288bbb118fbc56adfa2ee9d21e0e5f4eb49196a7301d70b361c592ff7",
    "q1_q84_records_sha256": "2e1c35996258d985ee4808e2e86235ce004de0e4d843043bec71a29fe12f8a32",
    "q1_q84_rows_sha256": "1977a6505d828a900baa26099515214e27b18f2fd6f8a6ac354345c0de00170b",
    "q85_record_sha256": "5c7f0315f858635b5784cc26a8f5bcd8171805ea957b7d782692cee0ae4e1235",
    "q85_rows_sha256": "cd9c9907b58f6cf5c0fd43e562d48a450f416190f859cb5cdbe639dddcd6848c",
    "q85_max_row_sha256": "36011e8e252661e65eac91884602603f460700b13a7ad0ef3321b0d259c4b9da",
    "all_rows_sha256": "cdf10157382ae8f14361ec6e611601b53d5f4d0021e243cadecd1e81d34b0dcd",
    "selected_indices_sha256": "1869b333010f06aa40ff923c7eb86c3a1a2ba742294133ea60420e7bbd16cac1",
    "q85_pretruncation_sha256": "c7e3390b1e0a4926e5e08fb02bab86a4ecfb2874d54ac773efeeb786e29691fa",
    "q85_ranked_suffix_sha256": "7596c4738c7f0d7be43ac86c8cdb9d628c9df62d72b47bae797235f0e3b51b8b",
    "q85_rounding_cumulative": "140304369975807495608715337",
}


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("m_k589824_c32_q86_for_tests", SCREEN_NAME)


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


class MagnetizationK589824C32Q86Tests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.anchor, self.route_reference = SCREEN.load_route_reference(HERE)

    @staticmethod
    def synthetic_sha(checkpoint: int, label: str) -> str:
        return hashlib.sha256(
            f"synthetic-M-q{checkpoint}-{label}".encode("ascii")
        ).hexdigest()

    def make_extended_record(self, previous, checkpoint, success):
        record = copy.deepcopy(self.anchor["records"][83])
        E_before = int(previous["E_after_ticks"])
        prefix_cap = int(
            SCREEN.EXPECTED_Q85_PREFIX_CAP_TICKS
            if checkpoint == 85
            else SCREEN.EXPECTED_Q86_PREFIX_CAP_TICKS
        )
        slack = prefix_cap - E_before
        pre_count = 700_000
        record.update({
            "checkpoint_index_zero_based": checkpoint - 1,
            "checkpoint_number_one_based": checkpoint,
            "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
            "gate_occurrence_last_zero_based": 4 * checkpoint - 1,
            **SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint],
            "input_expansion_count": previous["retained_expansion_count"],
            "input_expansion_sha256": previous["retained_expansion_sha256"],
            "E_before_ticks": str(E_before),
            "budget_prefix_cap_ticks": str(prefix_cap),
            "prefix_slack_before_selection_ticks": str(slack),
            "pretruncation_expansion_count": pre_count,
            "pretruncation_expansion_sha256": self.synthetic_sha(
                checkpoint, "pretruncation"
            ),
            "ranked_suffix_sha256": self.synthetic_sha(checkpoint, "suffix"),
            "peak_live_terms_this_checkpoint": pre_count,
            "peak_live_terms_cumulative": max(
                previous["peak_live_terms_cumulative"], pre_count
            ),
            "term_gate_visits_increment": (
                4 * previous["retained_expansion_count"]
            ),
            "term_gate_visits_cumulative": (
                previous["term_gate_visits_cumulative"]
                + 4 * previous["retained_expansion_count"]
            ),
            "maximum_expansion_coefficient_tick_bits": previous[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "maximum_product_bits": previous["maximum_product_bits"],
            "rounding_increment_scaled_ticks_squared": "1",
            "rounding_cumulative_scaled_ticks_squared": str(
                int(previous["rounding_cumulative_scaled_ticks_squared"]) + 1
            ),
        })
        rows = []
        for index, configured_K in enumerate(SCREEN.M_CANDIDATES):
            effective = min(configured_K, pre_count)
            drop = (32 - index) if success else (slack + 32 - index)
            rows.append({
                "candidate_index": index,
                "configured_K": configured_K,
                "effective_retained_count": effective,
                "dropped_term_count": pre_count - effective,
                "drop_ticks": str(drop),
                "E_after_if_selected_ticks": str(E_before + drop),
                "feasible_under_current_prefix_cap": drop <= slack,
            })
        record["candidate_records"] = rows
        if success:
            selected = rows[0]
            for field in SCREEN.FAILURE_ONLY_RECORD_KEYS:
                record.pop(field, None)
            record.update({
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
                "selected_candidate_index": 0,
                "selected_K": SCREEN.M_CANDIDATES[0],
                "selected_effective_retained_count": selected[
                    "effective_retained_count"
                ],
                "selected_dropped_term_count": selected["dropped_term_count"],
                "selected_drop_ticks": selected["drop_ticks"],
                "selected_dropped_terms_sha256": self.synthetic_sha(
                    checkpoint, "dropped"
                ),
                "retained_expansion_count": selected[
                    "effective_retained_count"
                ],
                "retained_expansion_sha256": self.synthetic_sha(
                    checkpoint, "retained"
                ),
                "minimum_retained_abs_upper_ticks": "1",
                "maximum_dropped_abs_upper_ticks": "1",
                "E_after_ticks": selected["E_after_if_selected_ticks"],
            })
        else:
            for field in SCREEN.SUCCESS_ONLY_RECORD_KEYS:
                record.pop(field, None)
            record.update({
                "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                "selected_candidate_index": None,
                "selected_K": None,
                "minimum_effective_K_to_meet_prefix": SCREEN.K589824 + 1,
                "required_K_excess_over_policy_maximum": 1,
                "maximum_candidate_drop_excess_over_slack_ticks": "1",
            })
        return record

    def make_raw_result(self, branch):
        result = {
            key: copy.deepcopy(self.anchor[key])
            for key in SCREEN.EXPECTED_PARENT_RESULT_KEYS
        }
        result.update({
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_ROOT_SHA256,
            "control_flow_owned_by_screen": True,
            "screen_horizon_checkpoint_count": SCREEN.EXTENDED_HORIZON,
        })
        components = copy.deepcopy(
            list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)
        )
        result["screen_execution_components"] = components
        result["screen_execution_components_sha256"] = digest(components)
        configuration = {"synthetic_raw_configuration_reference": True}
        result["configuration_reference"] = configuration
        result["configuration_reference_sha256"] = digest(configuration)
        transform = copy.deepcopy(
            self.anchor["checkpoint_transform"]
            ["physical_four_gate_control_flow_parent_transform"]
        )
        result["checkpoint_transform"] = transform
        result["checkpoint_transform_sha256"] = digest(transform)
        result["source_custody"] = copy.deepcopy(
            SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY
        )

        records = copy.deepcopy(self.anchor["records"])
        history = list(self.anchor["selected_K_history"])
        if branch == "q85_failure":
            q85 = self.make_extended_record(records[-1], 85, False)
            records.append(q85)
            terminal = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            horizon_attempted = False
            horizon_committed = False
            last_E = SCREEN.EXPECTED_Q84_E_AFTER_TICKS
        elif branch in {"q86_failure", "q86_success"}:
            q85 = self.make_extended_record(records[-1], 85, True)
            records.append(q85)
            history.append(q85["selected_K"])
            q86 = self.make_extended_record(
                records[-1], 86, branch == "q86_success"
            )
            records.append(q86)
            horizon_attempted = True
            if branch == "q86_failure":
                terminal = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
                horizon_committed = False
                last_E = q85["E_after_ticks"]
            else:
                terminal = "DIAGNOSTIC_HORIZON_REACHED"
                horizon_committed = True
                history.append(q86["selected_K"])
                last_E = q86["E_after_ticks"]
        else:
            raise AssertionError(branch)
        final = records[-1]
        failed = final["status"] == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        result.update({
            "records": records,
            "records_sha256": digest(records),
            "selected_K_history": history,
            "selected_K_history_sha256": digest(history),
            "attempted_checkpoint_count": len(records),
            "completed_checkpoint_count": len(history),
            "screen_terminal_condition": terminal,
            "horizon_checkpoint_attempted": horizon_attempted,
            "horizon_reached_with_committed_checkpoint": horizon_committed,
            "failure_checkpoint_included": failed,
            "failure_record_sha256": digest(final) if failed else None,
            "last_committed_cumulative_drop_ticks": last_E,
            "observed_peak_single_expansion_terms": final[
                "peak_live_terms_cumulative"
            ],
            "observed_term_gate_visits_including_terminal_attempt": final[
                "term_gate_visits_cumulative"
            ],
            "observed_maximum_expansion_coefficient_tick_bits": final[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "observed_maximum_product_bits": final["maximum_product_bits"],
            "observed_rounding_cumulative_scaled_ticks_squared": final[
                "rounding_cumulative_scaled_ticks_squared"
            ],
        })
        self.assertEqual(frozenset(result), SCREEN.EXPECTED_PARENT_RESULT_KEYS)
        return result

    def make_context(self, parent):
        _wrapper, wrapper_sha, manifest = parent.load_kernel_wrapper(HERE)
        return {
            "baseline_m": tuple(parent.V6_M_CANDIDATES),
            "wrapper_sha": wrapper_sha,
            "wrapper_manifest": copy.deepcopy(manifest),
            "raw_control_flow_horizon_override": {
                "changed_fields": [
                    "MODE_CONFIG.magnetization.horizon_checkpoint_count"
                ],
                "semantic_delta": {
                    "MODE_CONFIG.magnetization.horizon_checkpoint_count": {
                        "before": 80,
                        "after": 86,
                    }
                },
            },
            "execution_parent_private_entrypoint_called": True,
            "q84_canonical_loaded_before_replay": False,
            "execution_parent_route_loader_suppressed": True,
        }

    def test_01_source_parent_and_q84_canonical_pins(self):
        self.assertEqual(
            hashlib.sha256((HERE / SCREEN_NAME).read_bytes()).hexdigest(),
            EXPECTED_SCREEN_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                (HERE / SCREEN.EXECUTION_PARENT_NAME).read_bytes()
            ).hexdigest(),
            SCREEN.EXPECTED_EXECUTION_PARENT_SHA256,
        )
        route_raw = (HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes()
        self.assertEqual(len(route_raw), SCREEN.EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE)
        self.assertEqual(
            hashlib.sha256(route_raw).hexdigest(),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
        )
        self.assertEqual(route_raw, canonical_bytes(json.loads(route_raw)))
        self.assertEqual(
            digest(self.anchor["records"]),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        )
        self.assertEqual(
            digest(self.anchor["selected_K_history"]),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        )
        self.assertEqual(
            digest(self.anchor["records"][-1]),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_Q84_RECORD_SHA256,
        )
        canonical_reference = self.route_reference["canonical_transcript"]
        self.assertFalse(canonical_reference["compiled"])
        self.assertFalse(canonical_reference["executed"])
        self.assertFalse(canonical_reference["loaded_before_replay"])
        self.assertTrue(
            canonical_reference[
                "loaded_after_full_replay_as_exact_reference"
            ]
        )
        self.assertFalse(canonical_reference["propagation_input"])
        self.assertFalse(canonical_reference["state_resume_input"])
        parent_reference = self.route_reference["execution_parent_screen"]
        self.assertTrue(parent_reference["compiled"])
        self.assertTrue(parent_reference["executed"])
        self.assertTrue(parent_reference["private_entrypoint_called"])

    def test_02_exact_candidates_caps_schemas_and_parent_contract(self):
        SCREEN.validate_local_configuration()
        self.assertEqual(len(SCREEN.M_CANDIDATES), 32)
        self.assertEqual(SCREEN.M_CANDIDATES[-1], SCREEN.K589824)
        self.assertEqual(
            digest(list(SCREEN.M_CANDIDATES)),
            SCREEN.EXPECTED_CANDIDATE_SHA256,
        )
        self.assertEqual(
            SCREEN.POLICY_CAPS_BASE["max_candidate_K"], SCREEN.K589824
        )
        self.assertEqual(
            SCREEN.POLICY_CAPS_BASE["max_output_terms_if_successful"],
            SCREEN.K589824,
        )
        self.assertEqual(
            SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS["max_retained_K"],
            SCREEN.K589824,
        )
        self.assertEqual(
            {
                "raw": len(SCREEN.EXPECTED_PARENT_RESULT_KEYS),
                "final": len(SCREEN.EXPECTED_RELABELLED_RESULT_KEYS),
                "success": len(SCREEN.SUCCESS_RECORD_KEYS),
                "failure": len(SCREEN.FAILURE_RECORD_KEYS),
                "row": len(SCREEN.CANDIDATE_RECORD_KEYS),
            },
            {"raw": 65, "final": 94, "success": 37, "failure": 31, "row": 7},
        )
        parent = SCREEN.load_execution_parent(HERE)
        self.assertIsInstance(parent, types.ModuleType)
        self.assertEqual(parent.EXTENDED_HORIZON, 84)
        self.assertEqual(parent.M_CANDIDATES, SCREEN.M_CANDIDATES)
        self.assertEqual(parent.POLICY_CAPS_BASE, SCREEN.POLICY_CAPS_BASE)
        self.assertEqual(
            parent.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
            SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        )

    def test_03_q84_private_entrypoint_adapter_and_exception_identity(self):
        parent = SCREEN.load_execution_parent(HERE)
        observed = {}

        class Inner:
            def _run_verified(self, repo, mode):
                observed["repo"] = repo
                observed["mode"] = mode
                return {"raw": True}

        inner = Inner()
        configuration = object()
        wrapper = object()
        manifest = {"synthetic_manifest": True}
        parent.load_control_flow_parent = lambda _repo: inner
        parent.load_configured_v6_baseline = lambda _repo: (
            configuration,
            parent.V6_M_CANDIDATES,
        )
        parent.load_kernel_wrapper = lambda _repo: (
            wrapper,
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            manifest,
        )
        parent.load_route_predecessor_reference = lambda _repo: (_ for _ in ()).throw(
            AssertionError("q84 predecessor loader must be suppressed")
        )

        def configure(observed_inner, observed_configuration, observed_wrapper):
            self.assertIs(observed_inner, inner)
            self.assertIs(observed_configuration, configuration)
            self.assertIs(observed_wrapper, wrapper)
            observed["horizon"] = parent.EXTENDED_HORIZON
            return {
                "changed_fields": [
                    "MODE_CONFIG.magnetization.horizon_checkpoint_count"
                ]
            }

        parent.configure_parent_execution = configure
        result, context = SCREEN.execute_parent_replay(parent, HERE)
        self.assertEqual(result, {"raw": True})
        self.assertEqual(observed["repo"], HERE.resolve())
        self.assertEqual(observed["mode"], SCREEN.MODE)
        self.assertEqual(observed["horizon"], 86)
        self.assertEqual(parent.EXTENDED_HORIZON, 84)
        self.assertTrue(context["execution_parent_private_entrypoint_called"])
        self.assertFalse(context["q84_canonical_loaded_before_replay"])
        self.assertTrue(context["execution_parent_route_loader_suppressed"])
        self.assertEqual(context["wrapper_sha"], SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256)
        self.assertEqual(context["wrapper_manifest"], manifest)

        resource_error = RuntimeError("resource identity")
        failing_parent = SCREEN.load_execution_parent(HERE)

        class FailingInner:
            @staticmethod
            def _run_verified(_repo, _mode):
                raise resource_error

        failing_parent.load_control_flow_parent = lambda _repo: FailingInner()
        failing_parent.load_configured_v6_baseline = lambda _repo: (
            object(),
            failing_parent.V6_M_CANDIDATES,
        )
        failing_parent.load_kernel_wrapper = lambda _repo: (
            object(),
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            manifest,
        )
        failing_parent.configure_parent_execution = lambda *_args: {
            "changed_fields": [
                "MODE_CONFIG.magnetization.horizon_checkpoint_count"
            ]
        }
        with self.assertRaises(RuntimeError) as caught:
            SCREEN.execute_parent_replay(failing_parent, HERE)
        self.assertIs(caught.exception, resource_error)
        self.assertEqual(failing_parent.EXTENDED_HORIZON, 84)

    def test_04_all_three_terminal_branches_are_closed(self):
        expected = {
            "q85_failure": (
                "Q85_FAILURE_Q86_NOT_ATTEMPTED",
                85,
                84,
                True,
            ),
            "q86_failure": (
                "Q85_SUCCESS_Q86_FAILURE",
                86,
                85,
                True,
            ),
            "q86_success": (
                "Q85_AND_Q86_SUCCESS_HORIZON_REACHED",
                86,
                86,
                False,
            ),
        }
        for branch, (
            expected_branch,
            attempted,
            completed,
            failure_included,
        ) in expected.items():
            with self.subTest(branch=branch):
                result = self.make_raw_result(branch)
                handoff = SCREEN.validate_replay_handoff(result, self.anchor)
                self.assertEqual(handoff["terminal_branch"], expected_branch)
                self.assertTrue(handoff["q1_through_q84_records_exact"])
                self.assertTrue(
                    handoff["q1_through_q84_all_32_candidate_rows_exact"]
                )
                self.assertFalse(
                    handoff["q85_and_q86_outcomes_precommitted"]
                )
                self.assertEqual(result["attempted_checkpoint_count"], attempted)
                self.assertEqual(result["completed_checkpoint_count"], completed)
                self.assertIs(
                    result["failure_checkpoint_included"], failure_included
                )

    def test_05_terminal_shapes_prefix_and_digests_fail_closed(self):
        cases = {}
        extra_top = self.make_raw_result("q85_failure")
        extra_top["untrusted"] = True
        cases["top schema"] = extra_top
        prefix = self.make_raw_result("q85_failure")
        prefix["records"][0]["stage_index"] = 99
        prefix["records_sha256"] = digest(prefix["records"])
        cases["q1-q84 prefix"] = prefix
        history = self.make_raw_result("q86_success")
        history["selected_K_history"][0] = SCREEN.K589824
        history["selected_K_history_sha256"] = digest(
            history["selected_K_history"]
        )
        cases["history prefix"] = history
        missing_q86 = self.make_raw_result("q86_success")
        missing_q86["records"].pop()
        missing_q86["records_sha256"] = digest(missing_q86["records"])
        cases["q85 success missing q86"] = missing_q86
        extra_after_failure = self.make_raw_result("q85_failure")
        extra_after_failure["records"].append(
            copy.deepcopy(self.make_raw_result("q86_success")["records"][-1])
        )
        extra_after_failure["records_sha256"] = digest(
            extra_after_failure["records"]
        )
        cases["q85 failure continued"] = extra_after_failure
        bad_failure_sha = self.make_raw_result("q86_failure")
        bad_failure_sha["failure_record_sha256"] = "0" * 64
        cases["failure digest"] = bad_failure_sha
        bad_records_sha = self.make_raw_result("q86_success")
        bad_records_sha["records_sha256"] = "0" * 64
        cases["records digest"] = bad_records_sha
        bad_resource = self.make_raw_result("q85_failure")
        bad_resource["observed_maximum_product_bits"] += 1
        cases["resource summary"] = bad_resource
        synchronized_transform = self.make_raw_result("q86_success")
        synchronized_transform["checkpoint_transform"] = {
            "physical_gate_sequence_changed": True,
            "control_flow_changes": ["tampered"],
        }
        synchronized_transform["checkpoint_transform_sha256"] = digest(
            synchronized_transform["checkpoint_transform"]
        )
        cases["synchronized transform and digest"] = synchronized_transform
        bool_as_schema_version = self.make_raw_result("q85_failure")
        bool_as_schema_version["schema_version"] = True
        cases["bool as schema version"] = bool_as_schema_version
        int_as_invariant_bool = self.make_raw_result("q85_failure")
        int_as_invariant_bool["v2_run_entrypoint_called"] = 0
        cases["int as invariant bool"] = int_as_invariant_bool
        for field, forged in (
            ("horizon_checkpoint_attempted", 1),
            ("horizon_reached_with_committed_checkpoint", 1),
            ("failure_checkpoint_included", 0),
        ):
            terminal_bool = self.make_raw_result("q86_success")
            terminal_bool[field] = forged
            cases[f"int as terminal bool {field}"] = terminal_bool
        for label, result in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(result, self.anchor)

    def test_06_extension_record_ledger_and_schema_tamper_rejected(self):
        previous = self.anchor["records"][-1]
        good = self.make_extended_record(previous, 85, True)
        self.assertEqual(
            SCREEN.validate_extended_record(good, previous, 85),
            SCREEN.M_CANDIDATES[0],
        )
        failure = self.make_extended_record(previous, 85, False)
        self.assertIsNone(
            SCREEN.validate_extended_record(failure, previous, 85)
        )
        tamper_cases = {
            "extra record key": lambda item: item.__setitem__("untrusted", True),
            "pretruncation hash": lambda item: item.__setitem__(
                "pretruncation_expansion_sha256", "not-canonical"
            ),
            "ranked suffix hash": lambda item: item.__setitem__(
                "ranked_suffix_sha256", "A" * 64
            ),
            "cap": lambda item: item.__setitem__(
                "budget_prefix_cap_ticks", SCREEN.EXPECTED_Q86_PREFIX_CAP_TICKS
            ),
            "input continuity": lambda item: item.__setitem__(
                "input_expansion_count", 1
            ),
            "rounding recurrence": lambda item: item.__setitem__(
                "rounding_cumulative_scaled_ticks_squared", "0"
            ),
            "visit recurrence": lambda item: item.__setitem__(
                "term_gate_visits_cumulative",
                item["term_gate_visits_cumulative"] + 1,
            ),
            "peak recurrence": lambda item: item.__setitem__(
                "peak_live_terms_cumulative",
                item["peak_live_terms_cumulative"] + 1,
            ),
            "coefficient maximum decrease": lambda item: item.__setitem__(
                "maximum_expansion_coefficient_tick_bits",
                previous["maximum_expansion_coefficient_tick_bits"] - 1,
            ),
            "product maximum decrease": lambda item: item.__setitem__(
                "maximum_product_bits", previous["maximum_product_bits"] - 1
            ),
            "row schema": lambda item: item["candidate_records"][0].__setitem__(
                "untrusted", True
            ),
            "row identity": lambda item: item["candidate_records"][0].__setitem__(
                "configured_K", SCREEN.K589824
            ),
            "false as row index": lambda item: item["candidate_records"][0].__setitem__(
                "candidate_index", False
            ),
            "true as row index": lambda item: item["candidate_records"][1].__setitem__(
                "candidate_index", True
            ),
            "bool as configured K": lambda item: item["candidate_records"][0].__setitem__(
                "configured_K", True
            ),
            "bool as effective count": lambda item: item["candidate_records"][0].__setitem__(
                "effective_retained_count", True
            ),
            "bool as dropped count": lambda item: item["candidate_records"][0].__setitem__(
                "dropped_term_count", True
            ),
            "row E recurrence": lambda item: item["candidate_records"][0].__setitem__(
                "E_after_if_selected_ticks", "0"
            ),
            "row feasibility": lambda item: item["candidate_records"][0].__setitem__(
                "feasible_under_current_prefix_cap", False
            ),
            "selected index": lambda item: item.__setitem__(
                "selected_candidate_index", 1
            ),
            "false as selected index": lambda item: item.__setitem__(
                "selected_candidate_index", False
            ),
            "bool as checkpoint index": lambda item: item.__setitem__(
                "checkpoint_index_zero_based", True
            ),
            "retained digest": lambda item: item.__setitem__(
                "retained_expansion_sha256", "0"
            ),
        }
        for label, mutate in tamper_cases.items():
            with self.subTest(label=label):
                tampered = copy.deepcopy(good)
                mutate(tampered)
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_extended_record(tampered, previous, 85)

        forged_zero_drop = copy.deepcopy(good)
        forged_zero_drop["pretruncation_expansion_count"] = 81_920
        forged_zero_drop["peak_live_terms_this_checkpoint"] = previous[
            "retained_expansion_count"
        ]
        forged_zero_drop["peak_live_terms_cumulative"] = previous[
            "peak_live_terms_cumulative"
        ]
        E_before = int(forged_zero_drop["E_before_ticks"])
        for row in forged_zero_drop["candidate_records"]:
            row.update({
                "effective_retained_count": 81_920,
                "dropped_term_count": 0,
                "drop_ticks": "1",
                "E_after_if_selected_ticks": str(E_before + 1),
                "feasible_under_current_prefix_cap": True,
            })
        forged_zero_drop.update({
            "selected_candidate_index": 0,
            "selected_K": 81_920,
            "selected_effective_retained_count": 81_920,
            "selected_dropped_term_count": 0,
            "selected_drop_ticks": "1",
            "retained_expansion_count": 81_920,
            "E_after_ticks": str(E_before + 1),
        })
        with self.assertRaisesRegex(RuntimeError, "zero equivalence"):
            SCREEN.validate_extended_record(forged_zero_drop, previous, 85)

        failure_tampers = {
            "feasible failure row": lambda item: item["candidate_records"][-1].update({
                "drop_ticks": "0",
                "E_after_if_selected_ticks": item["E_before_ticks"],
                "feasible_under_current_prefix_cap": True,
            }),
            "minimum K": lambda item: item.__setitem__(
                "minimum_effective_K_to_meet_prefix", SCREEN.K589824
            ),
            "excess": lambda item: item.__setitem__(
                "required_K_excess_over_policy_maximum", 2
            ),
        }
        for label, mutate in failure_tampers.items():
            with self.subTest(failure_tamper=label):
                tampered = copy.deepcopy(failure)
                mutate(tampered)
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_extended_record(tampered, previous, 85)

    def test_07_relabel_closes_provenance_components_custody_and_digests(self):
        fresh = SCREEN.fresh_self_module()
        parent = fresh.load_execution_parent(HERE)
        context = self.make_context(parent)
        result = fresh.validate_and_relabel(
            self.make_raw_result("q86_success"),
            self.anchor,
            self.route_reference,
            parent,
            context,
        )
        self.assertEqual(
            frozenset(result), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS
        )
        self.assertEqual(
            result["transcript_fingerprint"],
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k589824_c32_q86_screen_v1",
        )
        self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            result["control_flow_parent_relative_path"],
            SCREEN.EXECUTION_PARENT_NAME,
        )
        self.assertEqual(
            result["control_flow_parent_source_sha256"],
            SCREEN.EXPECTED_EXECUTION_PARENT_SHA256,
        )
        self.assertTrue(result["control_flow_parent_private_entrypoint_called"])
        self.assertFalse(result["control_flow_owned_by_screen"])
        self.assertTrue(result["control_flow_owned_by_verified_parent"])
        self.assertFalse(result["child_boundary_committed"])
        self.assertFalse(result["positive_artifact_generated"])
        self.assertEqual(
            result["predecessor_handoff_validation"]["terminal_branch"],
            "Q85_AND_Q86_SUCCESS_HORIZON_REACHED",
        )
        delta = result["checkpoint_transform"][
            "incremental_route_semantic_delta"
        ]
        self.assertEqual(delta, {
            "candidate_K_values_changed": False,
            "policy_caps_changed": False,
            "kernel_capability_limits_changed": False,
            "horizon_checkpoint_count": {"before": 84, "after": 86},
        })
        self.assertEqual(
            result["checkpoint_transform"]["overridden_semantics"],
            ["magnetization_horizon_checkpoint_count"],
        )
        components = result["screen_execution_components"]
        self.assertEqual(len(components), 11)
        paths = [item["relative_path"] for item in components]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertIn(SCREEN.SELF_NAME, paths)
        self.assertIn(SCREEN.EXECUTION_PARENT_NAME, paths)
        self.assertIn(SCREEN.KERNEL_WRAPPER_NAME, paths)
        self.assertNotIn(SCREEN.CONTROL_FLOW_ROOT_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, paths)
        custody = result["source_custody"]
        self.assertEqual(len(custody), 10)
        self.assertEqual(
            custody,
            SCREEN.expected_final_source_custody(EXPECTED_SCREEN_SHA256),
        )
        self.assertNotIn(SCREEN.CONTROL_FLOW_ROOT_NAME, custody)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, custody)
        for path, expected_sha in custody.items():
            self.assertEqual(
                hashlib.sha256((HERE / path).read_bytes()).hexdigest(),
                expected_sha,
            )
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
        horizon = result["parent_horizon_override"]
        self.assertEqual(
            horizon["changed_fields"], ["screen_horizon_checkpoint_count"]
        )
        self.assertFalse(horizon["candidate_K_values_changed"])
        self.assertFalse(horizon["policy_caps_changed"])
        self.assertFalse(horizon["kernel_capability_limits_changed"])
        self.assertFalse(horizon["q84_canonical_loaded_before_replay"])
        self.assertTrue(horizon["execution_parent_route_loader_suppressed"])

    def test_08_custody_components_and_nested_digests_fail_closed(self):
        raw = self.make_raw_result("q85_failure")
        custody_cases = {}
        missing = copy.deepcopy(raw)
        missing["source_custody"].pop(next(iter(missing["source_custody"])))
        custody_cases["missing"] = missing
        extra = copy.deepcopy(raw)
        extra["source_custody"]["untrusted.py"] = "0" * 64
        custody_cases["extra"] = extra
        wrong = copy.deepcopy(raw)
        first = next(iter(wrong["source_custody"]))
        wrong["source_custody"][first] = "0" * 64
        custody_cases["wrong hash"] = wrong
        for label, item in custody_cases.items():
            with self.subTest(custody=label):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(item, self.anchor)

        duplicate = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        duplicate.append(copy.deepcopy(duplicate[0]))
        with self.assertRaises(RuntimeError):
            SCREEN.execution_components(duplicate, EXPECTED_SCREEN_SHA256)
        injected = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        injected[0]["untrusted"] = True
        with self.assertRaises(RuntimeError):
            SCREEN.execution_components(injected, EXPECTED_SCREEN_SHA256)

        fresh = SCREEN.fresh_self_module()
        parent = fresh.load_execution_parent(HERE)
        context = self.make_context(parent)
        bad_component_digest = self.make_raw_result("q85_failure")
        bad_component_digest["screen_execution_components_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            RuntimeError, "digest drift: screen_execution_components"
        ):
            fresh.validate_and_relabel(
                bad_component_digest,
                self.anchor,
                self.route_reference,
                parent,
                context,
            )
        bad_configuration_digest = self.make_raw_result("q85_failure")
        bad_configuration_digest["configuration_reference_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            RuntimeError, "digest drift: configuration_reference"
        ):
            fresh.validate_and_relabel(
                bad_configuration_digest,
                self.anchor,
                self.route_reference,
                parent,
                context,
            )
        bad_transform_digest = self.make_raw_result("q85_failure")
        bad_transform_digest["checkpoint_transform_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            RuntimeError, "digest drift: checkpoint_transform"
        ):
            fresh.validate_and_relabel(
                bad_transform_digest,
                self.anchor,
                self.route_reference,
                parent,
                context,
            )

    def test_09_run_order_is_replay_then_post_replay_q84_reference(self):
        fresh = SCREEN.fresh_self_module()
        parent = types.SimpleNamespace(parent=True)
        raw = {"raw": True}
        context = {"context": True}
        predecessor = {"predecessor": True}
        route = {"route": True}
        final = {"final": True}
        order = []
        fresh.load_execution_parent = lambda repo: (
            order.append(("load_parent", repo)),
            parent,
        )[1]
        fresh.execute_parent_replay = lambda observed_parent, repo: (
            order.append(("replay", observed_parent, repo)),
            (raw, context),
        )[1]
        fresh.load_route_reference = lambda repo: (
            order.append(("load_q84_after_replay", repo)),
            (predecessor, route),
        )[1]

        def relabel(*args):
            order.append(("relabel", args))
            return final

        fresh.validate_and_relabel = relabel
        self.assertIs(fresh._run_verified(HERE), final)
        self.assertEqual(
            [event[0] for event in order],
            ["load_parent", "replay", "load_q84_after_replay", "relabel"],
        )
        self.assertEqual(order[1][1], parent)
        self.assertEqual(order[3][1], (raw, predecessor, route, parent, context))

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

    def test_10_atomic_output_is_bounded_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary) / "transcript.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "exact bytes"):
                SCREEN.write_atomic_bounded(output, bytearray(b"{}"))
            with self.assertRaisesRegex(RuntimeError, "byte"):
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

    def test_11_canonical_transcript_exact_prefix_and_q85_failure_ledger(self):
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
        self.assertEqual(len(transcript), 94)

        exact_top = {
            "schema_version": 1,
            "transcript_fingerprint": (
                "hubbard_l8_magnetization_adaptive_k_four_gate_"
                "k589824_c32_q86_screen_v1"
            ),
            "screen_source_sha256": EXPECTED_SCREEN_SHA256,
            "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
            "screen_horizon_checkpoint_count": 86,
            "attempted_checkpoint_count": 85,
            "completed_checkpoint_count": 84,
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "failure_checkpoint_included": True,
            "failure_record_sha256": EXPECTED_CANONICAL["failure_sha256"],
            "horizon_checkpoint_attempted": False,
            "horizon_reached_with_committed_checkpoint": False,
            "last_committed_cumulative_drop_ticks": (
                SCREEN.EXPECTED_Q84_E_AFTER_TICKS
            ),
            "candidate_K_values": list(SCREEN.M_CANDIDATES),
            "candidate_K_values_sha256": EXPECTED_CANONICAL[
                "candidate_sha256"
            ],
            "control_flow_owned_by_screen": False,
            "control_flow_owned_by_verified_parent": True,
            "control_flow_parent_private_entrypoint_called": True,
            "candidate_policy_precommitted_at_probe_time": False,
            "child_boundary_committed": False,
            "positive_artifact_generated": False,
        }
        for field, expected in exact_top.items():
            with self.subTest(top_field=field):
                self.assertTrue(
                    SCREEN.exact_value_equal(transcript[field], expected)
                )

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
            "input_boundary_custody": "input_boundary_sha256",
            "root_globals_before": "root_globals_sha256",
            "root_globals_after": "root_globals_sha256",
            "kernel_capability_limits": "kernel_limits_sha256",
        }
        for value_field, expected_field in unembedded_digests.items():
            with self.subTest(unembedded_field=value_field):
                self.assertEqual(
                    digest(transcript[value_field]),
                    EXPECTED_CANONICAL[expected_field],
                )
        self.assertEqual(
            transcript["parent_expected_witness_sha256"],
            EXPECTED_CANONICAL["parent_witness_sha256"],
        )

        records = transcript["records"]
        history = transcript["selected_K_history"]
        self.assertEqual(len(records), 85)
        self.assertEqual(len(history), 84)
        self.assertEqual(digest(records), EXPECTED_CANONICAL["records_sha256"])
        self.assertEqual(digest(history), EXPECTED_CANONICAL["history_sha256"])
        self.assertTrue(
            SCREEN.exact_value_equal(records[:84], self.anchor["records"])
        )
        self.assertTrue(
            SCREEN.exact_value_equal(
                history, self.anchor["selected_K_history"]
            )
        )
        self.assertEqual(
            digest(records[:84]),
            EXPECTED_CANONICAL["q1_q84_records_sha256"],
        )
        prefix_rows = []
        for checkpoint_index, (record, anchored) in enumerate(
            zip(records[:84], self.anchor["records"])
        ):
            with self.subTest(prefix_checkpoint=checkpoint_index + 1):
                self.assertEqual(frozenset(record), SCREEN.SUCCESS_RECORD_KEYS)
                self.assertTrue(SCREEN.exact_value_equal(record, anchored))
                self.assertEqual(len(record["candidate_records"]), 32)
                self.assertTrue(
                    SCREEN.exact_value_equal(
                        record["candidate_records"],
                        anchored["candidate_records"],
                    )
                )
                for row in record["candidate_records"]:
                    self.assertEqual(
                        frozenset(row), SCREEN.CANDIDATE_RECORD_KEYS
                    )
                prefix_rows.append(record["candidate_records"])
        self.assertEqual(sum(map(len, prefix_rows)), 2_688)
        self.assertEqual(
            digest(prefix_rows), EXPECTED_CANONICAL["q1_q84_rows_sha256"]
        )

        q84 = records[83]
        q85 = records[84]
        self.assertEqual(frozenset(q85), SCREEN.FAILURE_RECORD_KEYS)
        self.assertEqual(digest(q85), EXPECTED_CANONICAL["q85_record_sha256"])
        self.assertEqual(
            digest(q85["candidate_records"]),
            EXPECTED_CANONICAL["q85_rows_sha256"],
        )
        exact_q85 = {
            "checkpoint_index_zero_based": 84,
            "checkpoint_number_one_based": 85,
            "stage_index": 2,
            "stage_group": "HU",
            "batch_in_stage": 28,
            "gate_occurrence_first_zero_based": 336,
            "gate_occurrence_last_zero_based": 339,
            "gate_batch_sha256": (
                "34a10608b11edb722a301d2fd60689a6b29389d1ba6dc76376cbb124ae32d77c"
            ),
            "input_expansion_count": SCREEN.K589824,
            "input_expansion_sha256": (
                SCREEN.EXPECTED_Q84_RETAINED_EXPANSION_SHA256
            ),
            "pretruncation_expansion_count": 673_356,
            "pretruncation_expansion_sha256": EXPECTED_CANONICAL[
                "q85_pretruncation_sha256"
            ],
            "ranked_suffix_sha256": EXPECTED_CANONICAL[
                "q85_ranked_suffix_sha256"
            ],
            "E_before_ticks": SCREEN.EXPECTED_Q84_E_AFTER_TICKS,
            "budget_prefix_cap_ticks": SCREEN.EXPECTED_Q85_PREFIX_CAP_TICKS,
            "prefix_slack_before_selection_ticks": "151110179092",
            "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
            "selected_candidate_index": None,
            "selected_K": None,
            "minimum_effective_K_to_meet_prefix": 592_290,
            "required_K_excess_over_policy_maximum": 2_466,
            "maximum_candidate_drop_excess_over_slack_ticks": "33848350434",
            "peak_live_terms_this_checkpoint": 673_356,
            "peak_live_terms_cumulative": 694_130,
            "term_gate_visits_increment": 2_484_542,
            "term_gate_visits_cumulative": 98_908_531,
            "rounding_increment_scaled_ticks_squared": (
                "4170212210430962966031320"
            ),
            "rounding_cumulative_scaled_ticks_squared": EXPECTED_CANONICAL[
                "q85_rounding_cumulative"
            ],
            "maximum_expansion_coefficient_tick_bits": 57,
            "maximum_product_bits": 121,
        }
        for field, expected in exact_q85.items():
            with self.subTest(q85_field=field):
                self.assertTrue(SCREEN.exact_value_equal(q85[field], expected))
        for hash_field in (
            "gate_batch_sha256",
            "input_expansion_sha256",
            "pretruncation_expansion_sha256",
            "ranked_suffix_sha256",
        ):
            self.assertTrue(SCREEN.is_canonical_sha256(q85[hash_field]))

        E_before = SCREEN.parse_canonical_nonnegative_decimal(
            q85["E_before_ticks"], "q85 E-before"
        )
        prefix_cap = SCREEN.parse_canonical_nonnegative_decimal(
            q85["budget_prefix_cap_ticks"], "q85 prefix cap"
        )
        slack = SCREEN.parse_canonical_nonnegative_decimal(
            q85["prefix_slack_before_selection_ticks"], "q85 slack"
        )
        self.assertEqual(slack, prefix_cap - E_before)
        drops = []
        for candidate_index, (configured_K, row) in enumerate(
            zip(SCREEN.M_CANDIDATES, q85["candidate_records"])
        ):
            with self.subTest(q85_candidate=candidate_index):
                self.assertEqual(
                    frozenset(row), SCREEN.CANDIDATE_RECORD_KEYS
                )
                effective = min(
                    configured_K, q85["pretruncation_expansion_count"]
                )
                expected_identity = {
                    "candidate_index": candidate_index,
                    "configured_K": configured_K,
                    "effective_retained_count": effective,
                    "dropped_term_count": (
                        q85["pretruncation_expansion_count"] - effective
                    ),
                }
                for field, expected in expected_identity.items():
                    self.assertTrue(
                        SCREEN.exact_value_equal(row[field], expected)
                    )
                drop = SCREEN.parse_canonical_nonnegative_decimal(
                    row["drop_ticks"], f"q85 row {candidate_index} drop"
                )
                E_after = SCREEN.parse_canonical_nonnegative_decimal(
                    row["E_after_if_selected_ticks"],
                    f"q85 row {candidate_index} E-after",
                )
                self.assertEqual(E_after, E_before + drop)
                self.assertIs(
                    row["feasible_under_current_prefix_cap"],
                    E_after <= prefix_cap,
                )
                self.assertFalse(row["feasible_under_current_prefix_cap"])
                self.assertIs(
                    row["dropped_term_count"] == 0,
                    drop == 0,
                )
                drops.append(drop)
        self.assertEqual(drops, sorted(drops, reverse=True))
        self.assertEqual(len(q85["candidate_records"]), 32)
        max_row = q85["candidate_records"][-1]
        self.assertEqual(
            digest(max_row), EXPECTED_CANONICAL["q85_max_row_sha256"]
        )
        self.assertEqual(max_row, {
            "candidate_index": 31,
            "configured_K": SCREEN.K589824,
            "effective_retained_count": SCREEN.K589824,
            "dropped_term_count": 83_532,
            "drop_ticks": "184958529526",
            "E_after_if_selected_ticks": "1700415687420807",
            "feasible_under_current_prefix_cap": False,
        })
        self.assertEqual(
            int(q85["maximum_candidate_drop_excess_over_slack_ticks"]),
            drops[-1] - slack,
        )
        self.assertEqual(
            q85["required_K_excess_over_policy_maximum"],
            q85["minimum_effective_K_to_meet_prefix"] - SCREEN.K589824,
        )

        self.assertEqual(
            q85["input_expansion_count"], q84["retained_expansion_count"]
        )
        self.assertEqual(
            q85["input_expansion_sha256"],
            q84["retained_expansion_sha256"],
        )
        self.assertEqual(q85["E_before_ticks"], q84["E_after_ticks"])
        self.assertEqual(
            q85["term_gate_visits_cumulative"],
            q84["term_gate_visits_cumulative"]
            + q85["term_gate_visits_increment"],
        )
        self.assertEqual(
            int(q85["rounding_cumulative_scaled_ticks_squared"]),
            int(q84["rounding_cumulative_scaled_ticks_squared"])
            + int(q85["rounding_increment_scaled_ticks_squared"]),
        )
        self.assertEqual(
            q85["peak_live_terms_cumulative"],
            max(
                q84["peak_live_terms_cumulative"],
                q85["peak_live_terms_this_checkpoint"],
            ),
        )
        self.assertGreaterEqual(
            q85["maximum_expansion_coefficient_tick_bits"],
            q84["maximum_expansion_coefficient_tick_bits"],
        )
        self.assertGreaterEqual(
            q85["maximum_product_bits"], q84["maximum_product_bits"]
        )
        observed_resources = {
            "observed_peak_single_expansion_terms": 694_130,
            "observed_term_gate_visits_including_terminal_attempt": 98_908_531,
            "observed_maximum_expansion_coefficient_tick_bits": 57,
            "observed_maximum_product_bits": 121,
            "observed_rounding_cumulative_scaled_ticks_squared": (
                EXPECTED_CANONICAL["q85_rounding_cumulative"]
            ),
        }
        for field, expected in observed_resources.items():
            self.assertTrue(
                SCREEN.exact_value_equal(transcript[field], expected)
            )

        all_rows = [record["candidate_records"] for record in records]
        self.assertEqual(sum(map(len, all_rows)), 2_720)
        self.assertEqual(
            digest(all_rows), EXPECTED_CANONICAL["all_rows_sha256"]
        )
        self.assertEqual(
            digest([record["selected_candidate_index"] for record in records]),
            EXPECTED_CANONICAL["selected_indices_sha256"],
        )

        expected_components = SCREEN.execution_components(
            copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)),
            EXPECTED_SCREEN_SHA256,
        )
        self.assertTrue(
            SCREEN.exact_value_equal(
                transcript["screen_execution_components"],
                expected_components,
            )
        )
        self.assertEqual(len(expected_components), 11)
        component_paths = []
        for component in expected_components:
            self.assertEqual(
                frozenset(component), {"relative_path", "role", "sha256"}
            )
            self.assertEqual(
                hashlib.sha256(
                    (HERE / component["relative_path"]).read_bytes()
                ).hexdigest(),
                component["sha256"],
            )
            component_paths.append(component["relative_path"])
        self.assertEqual(len(component_paths), len(set(component_paths)))
        self.assertNotIn(SCREEN.CONTROL_FLOW_ROOT_NAME, component_paths)
        self.assertNotIn(
            SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, component_paths
        )

        expected_custody = SCREEN.expected_final_source_custody(
            EXPECTED_SCREEN_SHA256
        )
        self.assertEqual(len(expected_custody), 10)
        self.assertTrue(
            SCREEN.exact_value_equal(
                transcript["source_custody"], expected_custody
            )
        )
        for relative_path, expected_sha in expected_custody.items():
            self.assertEqual(
                hashlib.sha256((HERE / relative_path).read_bytes()).hexdigest(),
                expected_sha,
            )

        config = transcript["configuration_override"]
        self.assertTrue(
            config[
                "candidate_policy_and_kernel_capability_unchanged_on_route"
            ]
        )
        self.assertEqual(
            config["overridden_fields_on_incremental_route"],
            ["screen_horizon_checkpoint_count"],
        )
        parent_config = config["execution_parent_configuration_override"]
        self.assertEqual(
            config["execution_parent_configuration_override_sha256"],
            digest(parent_config),
        )
        capability = transcript["kernel_capability_override"]
        parent_capability = capability[
            "execution_parent_kernel_capability_override"
        ]
        self.assertEqual(
            capability["execution_parent_kernel_capability_override_sha256"],
            digest(parent_capability),
        )
        manifest = parent_capability["capability_manifest"]
        self.assertEqual(
            parent_capability["capability_manifest_sha256"], digest(manifest)
        )

        horizon = transcript["parent_horizon_override"]
        self.assertEqual(
            horizon["changed_fields"], ["screen_horizon_checkpoint_count"]
        )
        self.assertEqual(
            horizon["semantic_delta"]["screen_horizon_checkpoint_count"],
            {"before": 84, "after": 86},
        )
        self.assertFalse(horizon["candidate_K_values_changed"])
        self.assertFalse(horizon["policy_caps_changed"])
        self.assertFalse(horizon["kernel_capability_limits_changed"])

        transform = transcript["checkpoint_transform"]
        physical = transform[
            "physical_four_gate_control_flow_parent_transform"
        ]
        self.assertEqual(
            transform[
                "physical_four_gate_control_flow_parent_transform_sha256"
            ],
            SCREEN.EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256,
        )
        self.assertEqual(
            digest(physical), SCREEN.EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256
        )
        self.assertEqual(
            transform["execution_parent_q84_transform_sha256"],
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
        )
        self.assertFalse(transform["physical_gate_sequence_changed"])
        self.assertFalse(transform["q85_and_q86_outcomes_precommitted"])
        self.assertEqual(
            transform["overridden_semantics"],
            ["magnetization_horizon_checkpoint_count"],
        )

        route = transcript["route_predecessor_reference"]
        route_canonical = route["canonical_transcript"]
        self.assertFalse(route_canonical["compiled"])
        self.assertFalse(route_canonical["executed"])
        self.assertFalse(route_canonical["loaded_before_replay"])
        self.assertTrue(
            route_canonical["loaded_after_full_replay_as_exact_reference"]
        )
        self.assertFalse(route_canonical["propagation_input"])
        self.assertFalse(route_canonical["state_resume_input"])
        self.assertEqual(
            route_canonical["records_sha256"],
            EXPECTED_CANONICAL["q1_q84_records_sha256"],
        )

        handoff = transcript["predecessor_handoff_validation"]
        self.assertEqual(
            handoff["terminal_branch"],
            "Q85_FAILURE_Q86_NOT_ATTEMPTED",
        )
        self.assertTrue(handoff["q1_through_q84_records_exact"])
        self.assertTrue(handoff["q1_through_q84_all_32_candidate_rows_exact"])
        self.assertTrue(handoff["q1_through_q84_selected_history_exact"])
        self.assertFalse(handoff["q85_and_q86_outcomes_precommitted"])
        self.assertEqual(
            handoff["q85_input_retained_sha256"],
            SCREEN.EXPECTED_Q84_RETAINED_EXPANSION_SHA256,
        )
        self.assertEqual(
            handoff["q85_prefix_cap_ticks"],
            SCREEN.EXPECTED_Q85_PREFIX_CAP_TICKS,
        )

    @unittest.skipUnless(
        os.environ.get("RUN_M_K589824_C32_Q86_REPLAY") == "1",
        "expensive deterministic q86 replay is opt-in",
    )
    def test_12_real_replay_is_opt_in(self):
        result = SCREEN.run(HERE)
        self.assertIn(len(result["records"]), (85, 86))
        self.assertEqual(result["records"][:84], self.anchor["records"])
        self.assertIn(
            result["predecessor_handoff_validation"]["terminal_branch"],
            {
                "Q85_FAILURE_Q86_NOT_ATTEMPTED",
                "Q85_SUCCESS_Q86_FAILURE",
                "Q85_AND_Q86_SUCCESS_HORIZON_REACHED",
            },
        )


if __name__ == "__main__":
    unittest.main()
