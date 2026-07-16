#!/usr/bin/env python3
"""Result-blind contract tests for the Majorana P6 S0 precommit.

The suite exercises frozen inputs, deterministic CAP/IO/LIFE boundaries, and
small independent selection oracles.  It never launches Julia and never
materializes a P6 result artifact.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import unittest
from unittest import mock


BASE = Path(__file__).resolve().parent
REQUIRED_PARENT_COMMIT = "f62005b435a0c033d42aae0d05c05e234faab059"
CANDIDATE_ID = "E768-MAX-LAZY37-V1"
CONTROL_CANDIDATE_ID = "P5-K37-RESOURCE-CONTROL"
CONTROL_IDENTITY = "P5_K37_RESOURCE_CONTROL"

FIXTURE_NAME = "majorana_certificate_p6_fixture.json"
POLICY_NAME = "majorana_certificate_p6_policy.json"
PRECOMMIT_CONTRACT_NAME = "majorana_certificate_p6_precommit_contract.json"

RESULT_ARTIFACTS = (
    "majorana_certificate_p6_contract.json",
    "majorana_certificate_p6_certificate.json",
    "test_majorana_certificate_p6_result.py",
)

EXPECTED_CHANGED_PATHS = tuple(sorted((
    "majorana_certificate_p6/majorana_p6_runner.jl",
    "majorana_certificate_p6_checker.py",
    FIXTURE_NAME,
    POLICY_NAME,
    PRECOMMIT_CONTRACT_NAME,
    "test_majorana_certificate_p6.py",
)))

EXPECTED_RUNNER_STAGED_PATHS = {
    "majorana_certificate_p0/Manifest.toml",
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p2/majorana_p2_runner.jl",
    "majorana_certificate_p2_fixture.json",
    "majorana_certificate_p3/majorana_p3_runner.jl",
    "majorana_certificate_p3_fixture.json",
    "majorana_certificate_p4/majorana_p4_runner.jl",
    "majorana_certificate_p4_fixture.json",
    "majorana_certificate_p5_fixture.json",
    "majorana_certificate_p6/majorana_p6_runner.jl",
    FIXTURE_NAME,
}

EXPECTED_STEP2_CAPS = {
    "maximum_step2_accuracy_charged_events": 67_108_864,
    "maximum_step2_anticommuting_events": 16_777_216,
    "maximum_step2_boundary_retained_terms": 1_048_576,
    "maximum_step2_cap_scan_term_visits": 536_870_912,
    "maximum_step2_current_terms_before_constituent": 1_048_576,
    "maximum_step2_drop_defect_events": 16_777_216,
    "maximum_step2_final_retained_terms": 1_048_576,
    "maximum_step2_merge_defect_events": 4_194_304,
    "maximum_step2_premerge_terms": 1_048_576,
    "maximum_step2_product_defect_events": 33_554_432,
    "maximum_step2_propagation_term_visits": 536_870_912,
    "maximum_step2_total_P2_charged_term_visits": 1_073_741_824,
    "maximum_step2_total_P2_plus_accuracy_charged_events": 1_073_741_824,
    "maximum_step2_truncation_term_visits": 268_435_456,
}

EXPECTED_SELECTION_CAPS = {
    "maximum_peak_ranking_buffer_terms": 1_048_576,
    "maximum_ranking_scan_term_visits": 268_435_456,
    "maximum_selected_membership_insertions": 16_777_216,
    "maximum_sort_input_items": 67_108_864,
    "maximum_tick_evaluations": 67_108_864,
    "maximum_total_selection_work_units": 536_870_912,
}


def _load_checker():
    path = BASE / "majorana_certificate_p6_checker.py"
    spec = importlib.util.spec_from_file_location(
        "majorana_certificate_p6_checker_for_tests", path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P6 = _load_checker()


def _load_json(path: Path):
    return json.loads(path.read_bytes())


def _repo() -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=BASE,
        check=True,
        stdout=subprocess.PIPE,
    )
    return Path(completed.stdout.decode().strip()).resolve()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_ids(value):
    result = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "candidate_id":
                result.append(child)
            else:
                result.extend(_candidate_ids(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(_candidate_ids(child))
    return result


class MajoranaP6PrecommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _load_json(BASE / FIXTURE_NAME)
        cls.policy = _load_json(BASE / POLICY_NAME)

    def _precommit(self):
        path = BASE / PRECOMMIT_CONTRACT_NAME
        self.assertTrue(path.is_file(), "P6 precommit contract is not materialized")
        return _load_json(path)

    def _recorded_precommit_commit(self) -> str | None:
        repo = _repo()
        relative = (BASE / PRECOMMIT_CONTRACT_NAME).relative_to(repo)
        completed = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(relative)],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        )
        return completed.stdout.decode().strip() or None

    def test_required_public_interface_is_present(self) -> None:
        self.assertEqual(P6.BASE, BASE)
        self.assertEqual(P6.REQUIRED_PARENT_COMMIT, REQUIRED_PARENT_COMMIT)
        self.assertEqual(P6.CANDIDATE_ID, CANDIDATE_ID)
        for name in (
            "validate_fixture",
            "validate_policy",
            "validate_precommit_contract",
            "brute_force_select",
            "lazy_select",
            "_derive_raw_witness_schema_max_bytes",
            "_derive_persisted_result_byte_cap",
            "verify_precommit",
        ):
            self.assertTrue(callable(getattr(P6, name, None)), name)

    def test_public_validators_accept_the_frozen_inputs(self) -> None:
        precommit = self._precommit()
        self.assertIs(P6.validate_fixture(self.fixture, BASE), self.fixture)
        self.assertIs(
            P6.validate_policy(self.policy, self.fixture, BASE), self.policy,
        )
        self.assertIs(
            P6.validate_precommit_contract(
                precommit, BASE, verify_source_files=True,
            ),
            precommit,
        )

    def test_single_formal_candidate_is_exact_and_control_is_excluded(self) -> None:
        candidate = self.fixture["adaptive_candidate"]
        self.assertLessEqual({
            "candidate_id",
            "algorithm_id",
            "formal_candidate_count",
            "fresh_process_count",
            "step1_threshold_Float64_bits_hex",
            "lazy_anchor_Float64_bits_hex",
            "each_fresh_process_starts_from_O0",
            "both_fresh_processes_execute_complete_step1_and_step2",
            "replays_share_no_process_state_cache_checkpoint_scratch_or_depot_prefix",
            "P5_K37_resource_control_is_not_a_formal_candidate_or_stage_input",
            "D0_control_is_not_a_formal_candidate",
            "candidate_selection_CLI_or_environment_override_forbidden",
            "fallback_no_drop_fixed_threshold_or_alternative_candidate_forbidden",
            "candidate_is_frozen_before_any_formal_P6_output",
        }, set(candidate))
        self.assertEqual(candidate["candidate_id"], CANDIDATE_ID)
        self.assertEqual(
            candidate["algorithm_id"], "MAJORANA-P6-E768-MAX-LAZY37-V1",
        )
        self.assertEqual(candidate["formal_candidate_count"], 1)
        self.assertEqual(candidate["fresh_process_count"], 2)
        self.assertEqual(
            candidate["step1_threshold_Float64_bits_hex"], "3dd0000000000000",
        )
        self.assertEqual(
            candidate["lazy_anchor_Float64_bits_hex"], "3da0000000000000",
        )
        self.assertTrue(candidate["each_fresh_process_starts_from_O0"])
        self.assertTrue(
            candidate["both_fresh_processes_execute_complete_step1_and_step2"],
        )
        self.assertTrue(
            candidate[
                "replays_share_no_process_state_cache_checkpoint_scratch_or_depot_prefix"
            ],
        )
        self.assertTrue(
            candidate[
                "P5_K37_resource_control_is_not_a_formal_candidate_or_stage_input"
            ],
        )
        self.assertTrue(candidate["D0_control_is_not_a_formal_candidate"])
        self.assertTrue(
            candidate["candidate_selection_CLI_or_environment_override_forbidden"],
        )
        self.assertTrue(
            candidate[
                "fallback_no_drop_fixed_threshold_or_alternative_candidate_forbidden"
            ],
        )
        self.assertTrue(candidate["candidate_is_frozen_before_any_formal_P6_output"])
        self.assertEqual(_candidate_ids(self.fixture), [CANDIDATE_ID])
        encoded = json.dumps(candidate, sort_keys=True).encode()
        self.assertNotIn(CONTROL_CANDIDATE_ID.encode(), encoded)
        self.assertNotIn(CONTROL_IDENTITY.encode(), encoded)

    def test_d0_derived_formal_caps_are_frozen_exactly(self) -> None:
        resource = self.fixture["deterministic_resource_caps"]
        self.assertEqual(
            {key: resource[key] for key in EXPECTED_STEP2_CAPS},
            EXPECTED_STEP2_CAPS,
        )
        selection = self.fixture["deterministic_selection_caps"]
        self.assertEqual(
            {key: selection[key] for key in EXPECTED_SELECTION_CAPS},
            EXPECTED_SELECTION_CAPS,
        )
        self.assertEqual(resource["maximum_BigInt_bit_length"], 2048)
        self.assertEqual(resource["maximum_trig_table_entries"], 6)
        self.assertTrue(resource["caps_are_checked_before_the_rejected_operation"])
        self.assertTrue(
            resource[
                "caps_are_checked_before_the_corresponding_scan_allocation_sort_or_tick_evaluation"
            ],
        )
        self.assertTrue(
            resource["no_operation_occurs_after_the_first_deterministic_cap_event"],
        )
        self.assertEqual(set(selection), set(EXPECTED_SELECTION_CAPS))
        self.assertTrue(
            self.fixture["conditional_authority"][
                "deterministic_cap_branch_has_resource_guard_authority_only"
            ],
        )

    def test_host_caps_and_isolation_are_frozen_exactly(self) -> None:
        host = self.fixture["host_supervisor_caps"]
        self.assertEqual(host["MemoryMax_bytes"], 2_147_483_648)
        self.assertEqual(host["MemorySwapMax_bytes"], 0)
        self.assertEqual(host["RuntimeMaxSec"], "1800s")
        self.assertEqual(host["outer_safety_timeout_seconds"], 1830)
        self.assertEqual(host["maximum_stdout_bytes"], 33_554_432)
        self.assertEqual(host["maximum_stderr_bytes"], 4096)
        self.assertTrue(host["systemd_user_scope_cgroup_v2_required"])
        self.assertTrue(host["network_namespace_unshared"])
        self.assertTrue(host["PID_namespace_unshared"])
        self.assertTrue(host["private_proc_and_dev_required"])
        self.assertTrue(
            host["fresh_writable_scratch_and_depot_prefix_per_process"],
        )
        self.assertEqual(host["host_cap_failure_branch"], "INDETERMINATE")

    def test_cap_and_control_mutations_fail_closed(self) -> None:
        bad_resource = copy.deepcopy(self.fixture)
        bad_resource["deterministic_resource_caps"][
            "maximum_step2_premerge_terms"
        ] += 1
        bad_selection = copy.deepcopy(self.fixture)
        bad_selection["deterministic_selection_caps"][
            "maximum_total_selection_work_units"
        ] -= 1
        bad_host = copy.deepcopy(self.fixture)
        bad_host["host_supervisor_caps"]["MemorySwapMax_bytes"] = 1
        bad_control = copy.deepcopy(self.fixture)
        bad_control["adaptive_candidate"][
            "P5_K37_resource_control_is_not_a_formal_candidate_or_stage_input"
        ] = False
        for name, value in (
            ("resource", bad_resource),
            ("selection", bad_selection),
            ("host", bad_host),
            ("control", bad_control),
        ):
            with self.subTest(name=name), self.assertRaises(
                (P6.SchemaError, P6.VerificationError),
            ):
                P6.validate_fixture(value, BASE)

        bad_policy = copy.deepcopy(self.policy)
        bad_policy["unauthorized_control_fallback"] = CONTROL_CANDIDATE_ID
        with self.assertRaises((P6.SchemaError, P6.VerificationError)):
            P6.validate_policy(bad_policy, self.fixture, BASE)

    def test_result_blind_pre_replay_validation_never_opens_D0_bytes(self) -> None:
        original_hash = P6.file_sha256
        original_load = P6.load_json
        original_read_bytes = Path.read_bytes
        forbidden = {
            (BASE / relative).resolve()
            for relative in P6.RUNNER_FORBIDDEN_PATHS
            if (BASE / relative).exists()
        }
        opened = []

        def guard_path(path, mechanism):
            resolved = Path(path).resolve()
            if resolved in forbidden:
                opened.append((mechanism, resolved))
                raise AssertionError(f"pre-replay D0 read: {resolved}")
            return resolved

        def guarded_hash(path):
            guard_path(path, "file_sha256")
            return original_hash(path)

        def guarded_load(path):
            guard_path(path, "load_json")
            return original_load(path)

        def guarded_read_bytes(path):
            guard_path(path, "Path.read_bytes")
            return original_read_bytes(path)

        with (
            mock.patch.object(P6, "file_sha256", side_effect=guarded_hash),
            mock.patch.object(P6, "load_json", side_effect=guarded_load),
            mock.patch.object(Path, "read_bytes", new=guarded_read_bytes),
            mock.patch.object(
                P6, "_git_committed_bytes",
                side_effect=AssertionError("pre-replay committed result read"),
            ),
        ):
            fixture, runtime, policy, contract = (
                P6._validate_result_blind_pre_replay_inputs(BASE)
            )
        self.assertEqual(opened, [])
        self.assertEqual(fixture["fixture_id"], self.fixture["fixture_id"])
        self.assertEqual(policy["policy_id"], self.policy["policy_id"])
        self.assertEqual(contract["required_parent_commit"], REQUIRED_PARENT_COMMIT)
        self.assertEqual(runtime["schema_version"], 1)

    def test_selection_peak_cap_precedes_snapshot_materialization(self) -> None:
        class SpyState(dict):
            materialized = False

            def items(self):
                self.materialized = True
                return super().items()

        state = SpyState({1: 0})
        tracker = P6._empty_selection_tracker(EXPECTED_SELECTION_CAPS)
        tracker["caps"]["maximum_peak_ranking_buffer_terms"] = 0
        with self.assertRaises(P6.P4._CapExceeded):
            P6._p6_select_rows_for_boundary(
                state=state,
                ticks={"product": 0, "merge": 0, "drop": 0},
                boundary_index=0,
                maximum_bits=2048,
                selection_tracker=tracker,
            )
        self.assertFalse(state.materialized)
        runner_source = (BASE / P6.RUNNER_RELATIVE_PATH).read_text()
        snapshot_block = runner_source.split(
            "function p6_snapshot_rows", 1,
        )[1].split("\nend", 1)[0]
        allocation = snapshot_block.index("rows = P6SnapshotRow[]")
        self.assertLess(
            snapshot_block.index("p6_observe_ranking_buffer!"), allocation,
        )
        self.assertLess(snapshot_block.index("p6_charge_selection!"), allocation)

    def test_raw_and_persisted_io_caps_are_schema_derived_and_result_blind(self) -> None:
        with mock.patch.object(
            P6, "load_json", side_effect=AssertionError("external JSON read"),
            create=True,
        ):
            raw_bound = P6._derive_raw_witness_schema_max_bytes(self.fixture)
            persisted = P6._derive_persisted_result_byte_cap(self.fixture)
        self.assertIs(type(raw_bound), int)
        self.assertGreater(raw_bound, 16 * 1024**2)
        self.assertLessEqual(raw_bound, 32 * 1024**2)
        expected_stdout = 1 << (raw_bound - 1).bit_length()
        self.assertEqual(
            self.fixture["host_supervisor_caps"]["maximum_stdout_bytes"],
            expected_stdout,
        )
        self.assertEqual(persisted, 2 * expected_stdout)
        self.assertEqual(persisted, 67_108_864)
        budget = self.fixture["scientific_output_schema_budget"]
        self.assertTrue(
            budget["derivation_is_frozen_and_result_blind_before_formal_execution"],
        )
        self.assertEqual(budget["fresh_process_count"], 2)
        self.assertEqual(
            budget["stdout_cap_rule"],
            "smallest_power_of_two_at_least_raw_witness_schema_max_bytes",
        )
        self.assertEqual(
            budget["persisted_result_cap_rule"],
            "fresh_process_count_times_maximum_stdout_bytes",
        )
        self.assertTrue(budget["full_ranking_or_membership_arrays_forbidden"])

    def test_lazy_tier2_is_required_and_exact_fit_is_selected(self) -> None:
        threshold = 0x3DA0000000000000
        rows = [
            {"point_abs_ticks": 0, "abs_bits": 0, "mask": 9},
            {"point_abs_ticks": 2, "abs_bits": threshold - 1, "mask": 7},
            {"point_abs_ticks": 3, "abs_bits": threshold, "mask": 5},
            {"point_abs_ticks": 4, "abs_bits": threshold + 1, "mask": 3},
        ]
        original = copy.deepcopy(rows)
        selected = P6.lazy_select(rows, 5)
        self.assertEqual([row["mask"] for row in selected], [9, 7, 5])
        self.assertEqual(selected, P6.brute_force_select(rows, 5))
        self.assertEqual(rows, original)

    def test_first_nonfitting_ranked_row_stops_without_skipping(self) -> None:
        threshold = 0x3DA0000000000000
        rows = [
            {"point_abs_ticks": 2, "abs_bits": threshold - 3, "mask": 1},
            {"point_abs_ticks": 4, "abs_bits": threshold - 2, "mask": 2},
            {"point_abs_ticks": 4, "abs_bits": threshold - 1, "mask": 3},
        ]
        selected = P6.lazy_select(rows, 5)
        self.assertEqual([row["mask"] for row in selected], [1])
        self.assertEqual(selected, P6.brute_force_select(rows, 5))

    def test_signed_zero_ties_are_deterministic(self) -> None:
        rows = [
            {
                "point_abs_ticks": 0,
                "abs_bits": 0,
                "mask": 8,
                "coefficient_bits": 0x8000000000000000,
            },
            {
                "point_abs_ticks": 0,
                "abs_bits": 0,
                "mask": 2,
                "coefficient_bits": 0,
            },
            {
                "point_abs_ticks": 1,
                "abs_bits": 1,
                "mask": 4,
                "coefficient_bits": 1,
            },
        ]
        for permutation in (
            rows,
            list(reversed(rows)),
            [rows[1], rows[2], rows[0]],
        ):
            selected = P6.lazy_select(permutation, 0)
            self.assertEqual([row["mask"] for row in selected], [2, 8])
            self.assertEqual(
                {row["coefficient_bits"] for row in selected},
                {0, 0x8000000000000000},
            )
            self.assertEqual(selected, P6.brute_force_select(permutation, 0))

    def test_lazy_matches_full_sort_on_deterministic_random_microcases(self) -> None:
        rng = random.Random(0xE76837)
        threshold = 0x3DA0000000000000
        for _ in range(1000):
            rows = []
            for mask in range(rng.randrange(0, 60)):
                bits = rng.randrange(threshold - 1000, threshold + 1000)
                rows.append({
                    "point_abs_ticks": (bits - (threshold - 1000)) // 7,
                    "abs_bits": bits,
                    "mask": mask,
                    "coefficient_bits": bits,
                })
            available = rng.randrange(0, 3000)
            self.assertEqual(
                P6.lazy_select(rows, available),
                P6.brute_force_select(rows, available),
            )

    def test_runner_stage_is_exact_and_result_blind(self) -> None:
        staged = tuple(P6.RUNNER_STAGED_PATHS)
        forbidden = set(P6.RUNNER_FORBIDDEN_PATHS)
        self.assertEqual(len(staged), len(EXPECTED_RUNNER_STAGED_PATHS))
        self.assertEqual(set(staged), EXPECTED_RUNNER_STAGED_PATHS)
        self.assertFalse(set(staged) & forbidden)
        self.assertNotIn(
            "majorana_certificate_p5/majorana_p5_runner.jl", staged,
        )
        self.assertIn(
            "majorana_certificate_p5/majorana_p5_runner.jl", forbidden,
        )
        for name in (
            "majorana_certificate_p6_design_probe_fixture.json",
            "majorana_certificate_p6_design_probe_policy.json",
            "majorana_certificate_p6_design_probe_report.json",
            "majorana_certificate_p6_design_probe/majorana_p6_adaptive_drop_resource_probe.jl",
            *RESULT_ARTIFACTS,
        ):
            self.assertIn(name, forbidden)
        self.assertTrue(
            self.policy["runner_visibility_and_precommit_boundary"][
                "formal_stage_contains_only_the_standalone_P6_runner_P0_runtime_"
                "P2_P3_P4_sources_and_fixtures_and_P5_workload_fixture"
            ],
        )

    def test_precommit_changed_path_allowlist_is_exactly_six(self) -> None:
        self.assertEqual(P6.PRECOMMIT_CHANGED_PATHS, EXPECTED_CHANGED_PATHS)
        self.assertEqual(len(P6.PRECOMMIT_CHANGED_PATHS), 6)
        self.assertFalse(set(P6.PRECOMMIT_CHANGED_PATHS) & set(RESULT_ARTIFACTS))
        if self._recorded_precommit_commit() is None:
            repo = _repo()
            prefix = BASE.relative_to(repo)
            status = subprocess.run(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout.decode().splitlines()
            paths = {
                row[3:] for row in status
                if "/__pycache__/" not in row[3:]
            }
            expected = {
                (prefix / relative).as_posix()
                for relative in EXPECTED_CHANGED_PATHS
            }
            self.assertEqual(paths, expected)

    def test_precommit_contract_closes_stage_and_result_absence(self) -> None:
        precommit = self._precommit()
        self.assertEqual(
            precommit["required_parent_commit"], REQUIRED_PARENT_COMMIT,
        )
        self.assertEqual(
            set(precommit["runner_staged_files"]),
            EXPECTED_RUNNER_STAGED_PATHS,
        )
        self.assertEqual(
            tuple(precommit["result_artifacts_required_absent"]),
            RESULT_ARTIFACTS,
        )
        source_paths = [row["relative_path"] for row in precommit["source_files"]]
        self.assertEqual(len(source_paths), 66)
        self.assertEqual(len(P6.PRECOMMIT_SOURCE_PATHS), 66)
        self.assertEqual(len(source_paths), len(set(source_paths)))
        self.assertNotIn(PRECOMMIT_CONTRACT_NAME, source_paths)
        for row in precommit["source_files"]:
            path = BASE / row["relative_path"]
            self.assertEqual(path.stat().st_size, row["size_bytes"])
            self.assertEqual(_sha256(path), row["sha256"])
        commit = self._recorded_precommit_commit()
        if commit is not None:
            repo = _repo()
            prefix = BASE.relative_to(repo)
            for row in precommit["source_files"]:
                body = subprocess.run(
                    [
                        "git", "show",
                        f"{commit}:{(prefix / row['relative_path']).as_posix()}",
                    ],
                    cwd=repo,
                    check=True,
                    stdout=subprocess.PIPE,
                ).stdout
                self.assertEqual(len(body), row["size_bytes"])
                self.assertEqual(hashlib.sha256(body).hexdigest(), row["sha256"])

    def test_precommit_contract_mutations_fail_closed(self) -> None:
        precommit = self._precommit()
        mutations = []

        wrong_parent = copy.deepcopy(precommit)
        wrong_parent["required_parent_commit"] = "0" * 40
        mutations.append(wrong_parent)

        result_set = copy.deepcopy(precommit)
        result_set["result_artifacts_required_absent"] = list(RESULT_ARTIFACTS[:-1])
        mutations.append(result_set)

        exposed_result = copy.deepcopy(precommit)
        exposed_result["runner_staged_files"].append(RESULT_ARTIFACTS[0])
        mutations.append(exposed_result)

        duplicate_source = copy.deepcopy(precommit)
        duplicate_source["source_files"].append(
            copy.deepcopy(duplicate_source["source_files"][-1]),
        )
        mutations.append(duplicate_source)

        for index, value in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(
                (P6.SchemaError, P6.VerificationError),
            ):
                P6.validate_precommit_contract(
                    value, BASE, verify_source_files=False,
                )

    def test_verify_precommit_is_read_only_and_never_replays(self) -> None:
        repo = _repo()
        result_paths = {(BASE / name).resolve() for name in RESULT_ARTIFACTS}
        original_exists = Path.exists

        def precommit_phase_exists(path: Path) -> bool:
            if path.resolve() in result_paths:
                return False
            return original_exists(path)

        status_before = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout
        with (
            mock.patch.object(
                P6, "fresh_replay", side_effect=AssertionError("replay called"),
                create=True,
            ),
            mock.patch.object(
                P6,
                "materialize_result",
                side_effect=AssertionError("result materialized"),
                create=True,
            ),
            mock.patch.object(
                P6,
                "_run_one_isolated_replay",
                side_effect=AssertionError("process started"),
                create=True,
            ),
            mock.patch.object(
                Path, "write_bytes", side_effect=AssertionError("file written"),
            ),
            mock.patch.object(
                Path, "write_text", side_effect=AssertionError("file written"),
            ),
            mock.patch.object(
                P6.os, "replace", side_effect=AssertionError("file replaced"),
            ),
            mock.patch.object(Path, "exists", new=precommit_phase_exists),
        ):
            summary = P6.verify_precommit(BASE)
        self.assertEqual(summary["required_parent_commit"], REQUIRED_PARENT_COMMIT)
        self.assertEqual(summary["candidate_id"], CANDIDATE_ID)
        self.assertEqual(summary["fresh_process_count"], 2)
        status_after = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout
        self.assertEqual(status_after, status_before)

    def test_all_five_materializable_branches_are_narrowly_authorized(self) -> None:
        authorities = {
            row["branch"]: row["authority"]
            for row in self.policy["qualification_and_terminal_truth_table"][
                "legal_terminal_branches"
            ]
        }

        def package(branch, qualified, local=None, cumulative=None):
            telescoping = None
            if local is not None:
                telescoping = {
                    "candidate_step2_strictly_within_allocation": local,
                    "candidate_cumulative_strictly_within_allocation": cumulative,
                }
            return {
                "terminal_branch": branch,
                "witness": {
                    "candidate_qualified": qualified,
                    "candidate_result": {
                        "telescoping_ledger": telescoping,
                        "first_policy_cap_event": (
                            {"cap_name": "test"}
                            if branch == "DETERMINISTIC_POLICY_CAP_EXCEEDED"
                            else None
                        ),
                        "step1_P3_fieldwise_conformance": (
                            False
                            if branch == "FAILED_P3_POST_REPLAY_CONFORMANCE"
                            else True
                        ),
                    },
                },
            }

        cases = (
            ("CANDIDATE_QUALIFIED", True, True, True),
            ("CANDIDATE_LOCAL_ALLOCATION_EXCEEDED", False, False, True),
            (
                "CANDIDATE_LOCAL_AND_CUMULATIVE_ALLOCATIONS_EXCEEDED",
                False, False, False,
            ),
            ("DETERMINISTIC_POLICY_CAP_EXCEEDED", None, None, None),
            ("FAILED_P3_POST_REPLAY_CONFORMANCE", None, None, None),
        )
        for branch, qualified, local, cumulative in cases:
            with self.subTest(branch=branch):
                authority, claims = P6._certificate_authority_and_claims(
                    package(branch, qualified, local, cumulative),
                )
                self.assertEqual(authority, authorities[branch])
                self.assertTrue(claims)
                if branch != "CANDIDATE_QUALIFIED":
                    self.assertNotIn(
                        "fixed_E768_candidate_passes_both_strict_allocations",
                        claims,
                    )
                if branch == "DETERMINISTIC_POLICY_CAP_EXCEEDED":
                    self.assertNotIn(
                        "fixed_L8_P3_2^-34_step1_then_fixed_E768_MAX_"
                        "LAZY37_V1_step2_execution",
                        claims,
                    )

        impossible = package(
            "CANDIDATE_LOCAL_ALLOCATION_EXCEEDED", False, True, False,
        )
        with self.assertRaises(P6.VerificationError):
            P6._certificate_authority_and_claims(impossible)

    def test_cap_and_conformance_failure_never_unlock_P3_E1(self) -> None:
        lineage = (
            {"report_type": "test_D0"},
            {"result_commit_sha": "0" * 40, "status": "test", "selected_candidate_id": None},
            {},
            {
                "result_commit_sha": "0" * 40,
                "status": "pinned_only",
                "terminal_branch": "pinned_only",
                "result_contract_sha256": "0" * 64,
                "certificate_sha256": "0" * 64,
                "canonical_witness_sha256": "0" * 64,
                "accuracy_ledger_sha256": "0" * 64,
            },
        )
        cap_raw = {
            "step1": {"execution": {"cap_event": {"cap_name": "test"}}},
            "step2": None,
            "selection_resources": {},
        }
        with (
            mock.patch.object(
                P6, "_verify_design_parent_and_nonnumeric_lineage",
                return_value=lineage,
            ),
            mock.patch.object(
                P6, "_load_p3_witness_for_uninterpreted_fieldwise_comparison",
                side_effect=AssertionError("P3 comparison opened on cap"),
            ),
            mock.patch.object(
                P6.P4, "_verify_parent_p3",
                side_effect=AssertionError("P3 E1 unlocked on cap"),
            ),
        ):
            cap_witness = P6._compose_authoritative_witness(
                {CANDIDATE_ID: cap_raw}, self.fixture, self.policy, BASE,
            )
        self.assertEqual(
            cap_witness["terminal_branch"], "DETERMINISTIC_POLICY_CAP_EXCEEDED",
        )
        self.assertEqual(
            cap_witness["parent_P3_authority"]["E1_charge_multiplicity"], 0,
        )
        self.assertFalse(
            cap_witness["parent_P3_authority"][
                "active_result_authority_verified_after_fieldwise_conformance"
            ],
        )

        failed_raw = {
            "step1": {"execution": {"cap_event": None}},
            "step2": {"execution": {"cap_event": None}},
            "selection_resources": {},
        }
        with (
            mock.patch.object(
                P6, "_verify_design_parent_and_nonnumeric_lineage",
                return_value=lineage,
            ),
            mock.patch.object(P6, "_step1_p3_projection", return_value={"x": 1}),
            mock.patch.object(
                P6, "_load_p3_witness_for_uninterpreted_fieldwise_comparison",
                return_value={"x": 2},
            ),
            mock.patch.object(
                P6.P4, "_verify_parent_p3",
                side_effect=AssertionError("P3 E1 unlocked after failed conformance"),
            ),
        ):
            failed_witness = P6._compose_authoritative_witness(
                {CANDIDATE_ID: failed_raw}, self.fixture, self.policy, BASE,
            )
        self.assertEqual(
            failed_witness["terminal_branch"],
            "FAILED_P3_POST_REPLAY_CONFORMANCE",
        )
        self.assertEqual(
            failed_witness["parent_P3_authority"]["E1_charge_multiplicity"], 0,
        )
        self.assertFalse(
            failed_witness["parent_P3_authority"][
                "active_result_authority_verified_after_fieldwise_conformance"
            ],
        )

    def test_result_artifacts_are_absent_from_the_s0_lifecycle_point(self) -> None:
        repo = _repo()
        commit = self._recorded_precommit_commit()
        if commit is None:
            for name in RESULT_ARTIFACTS:
                self.assertFalse((BASE / name).exists(), name)
            return

        parent = subprocess.run(
            ["git", "rev-parse", f"{commit}^"],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
        self.assertEqual(parent, REQUIRED_PARENT_COMMIT)
        changed = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().splitlines()
        prefix = BASE.relative_to(repo)
        expected = {
            (prefix / relative).as_posix()
            for relative in EXPECTED_CHANGED_PATHS
        }
        self.assertEqual(set(changed), expected)
        tree = set(subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", commit],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().splitlines())
        for name in RESULT_ARTIFACTS:
            self.assertNotIn((prefix / name).as_posix(), tree)


if __name__ == "__main__":
    unittest.main()
