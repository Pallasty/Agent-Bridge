#!/usr/bin/env python3
"""Precommit, arithmetic, and adversarial tests for the Majorana P3 route."""

from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import importlib.util
import inspect
import math
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock


BASE = Path(__file__).resolve().parent

PARENT_COMMIT = "c90014ed8569924350d5d3fce4959d31021e0461"
PARENT_STATUS = (
    "VERIFIED_MAJORANA_P2_L8_STAGGERED_MAGNETIZATION_ONE_STEP_"
    "BOUNDED_PREFIX_RESOURCE_FEASIBILITY_SUBCERTIFICATE"
)
P3_RESULT_ARTIFACTS = (
    "majorana_certificate_p3_contract.json",
    "majorana_certificate_p3_certificate.json",
    "test_majorana_certificate_p3_result.py",
)
P2_RESULT_CANARIES = (
    "majorana_certificate_p2_contract.json",
    "majorana_certificate_p2_certificate.json",
    "test_majorana_certificate_p2_result.py",
)
RUNNER_STAGED_PATHS = (
    "majorana_certificate_p0/Manifest.toml",
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p2/majorana_p2_runner.jl",
    "majorana_certificate_p2_fixture.json",
    "majorana_certificate_p3/majorana_p3_runner.jl",
    "majorana_certificate_p3_fixture.json",
)
REPLAY_ENVIRONMENT_TARGETS = (
    ("ELF_DYNAMIC_LOADER", "/lib64/ld-linux-x86-64.so.2"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_ADDRESS"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_COLLATE"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_CTYPE"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_IDENTIFICATION"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_MEASUREMENT"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_MESSAGES/SYS_LC_MESSAGES"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_MONETARY"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_NAME"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_NUMERIC"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_PAPER"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_TELEPHONE"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_TIME"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/libc.so.6"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/libdl.so.2"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/libm.so.6"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/libpthread.so.0"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/librt.so.1"),
)
EXPECTED_SOURCE_PATHS = tuple(
    sorted(
        (
            "majorana_certificate_p0/Manifest.toml",
            "majorana_certificate_p0/Project.toml",
            "majorana_certificate_p0_checker.py",
            "majorana_certificate_p0_runtime_lock.json",
            "majorana_certificate_p1/majorana_p1_runner.jl",
            "majorana_certificate_p1_certificate.json",
            "majorana_certificate_p1_checker.py",
            "majorana_certificate_p1_contract.json",
            "majorana_certificate_p1_fixture.json",
            "majorana_certificate_p1_policy.json",
            "majorana_certificate_p1_precommit_contract.json",
            "majorana_certificate_p2/majorana_p2_runner.jl",
            "majorana_certificate_p2_certificate.json",
            "majorana_certificate_p2_checker.py",
            "majorana_certificate_p2_contract.json",
            "majorana_certificate_p2_fixture.json",
            "majorana_certificate_p2_policy.json",
            "majorana_certificate_p2_precommit_contract.json",
            "majorana_certificate_p3/majorana_p3_runner.jl",
            "majorana_certificate_p3_checker.py",
            "majorana_certificate_p3_fixture.json",
            "majorana_certificate_p3_policy.json",
            "test_majorana_certificate_p1_result.py",
            "test_majorana_certificate_p1.py",
            "test_majorana_certificate_p2.py",
            "test_majorana_certificate_p2_result.py",
            "test_majorana_certificate_p3.py",
        )
    )
)


def _load_checker():
    path = BASE / "majorana_certificate_p3_checker.py"
    spec = importlib.util.spec_from_file_location("majorana_p3_checker_for_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P3 = _load_checker()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _floor_scaled(value: Fraction, denominator: int) -> int:
    return (value.numerator * denominator) // value.denominator


def _ceil_scaled(value: Fraction, denominator: int) -> int:
    return -((-value.numerator * denominator) // value.denominator)


def _expected_trig_ticks(
    theta: Fraction, kind: str, *, order: int = 7, denominator: int = 2**128
) -> tuple[int, int]:
    if kind == "sin":
        point = sum(
            (
                Fraction((-1) ** index * theta ** (2 * index + 1), math.factorial(2 * index + 1))
                for index in range(order + 1)
            ),
            Fraction(0),
        )
        remainder = Fraction(
            abs(theta) ** (2 * order + 3), math.factorial(2 * order + 3)
        )
    elif kind == "cos":
        point = sum(
            (
                Fraction((-1) ** index * theta ** (2 * index), math.factorial(2 * index))
                for index in range(order + 1)
            ),
            Fraction(0),
        )
        remainder = Fraction(
            abs(theta) ** (2 * order + 2), math.factorial(2 * order + 2)
        )
    else:
        raise AssertionError(f"unsupported trig kind: {kind}")
    return (
        _floor_scaled(point - remainder, denominator),
        _ceil_scaled(point + remainder, denominator),
    )


def _repo() -> Path:
    return Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=BASE,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
    ).resolve()


class MajoranaP3PrecommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = P3.load_json(BASE / P3.FIXTURE_NAME)
        cls.policy = P3.load_json(BASE / P3.POLICY_NAME)
        cls.runtime_lock = P3.load_json(BASE / "majorana_certificate_p0_runtime_lock.json")
        cls.precommit = P3.load_json(BASE / P3.PRECOMMIT_CONTRACT_NAME)
        cls.schedule = P3.expected_schedule()

    def test_fixture_is_exact_and_contains_no_P3_result_pins(self) -> None:
        validated = P3.validate_fixture(self.fixture)
        self.assertEqual(validated["schema_version"], 1)
        self.assertEqual(
            validated["fixture_id"], "MAJORANA-P3-L8-FUSED-ONE-STEP-LOCAL-DEFECT-V1"
        )
        # The direct P2 result/certificate digests are legitimate custody anchors.
        # Result pins remain forbidden everywhere outside that named parent block.
        unpinned_surface = copy.deepcopy(self.fixture)
        del unpinned_surface["required_parent"]
        encoded = P3.canonical_bytes(unpinned_surface)
        for forbidden in self.policy["forbidden_formal_result_pins"]:
            self.assertNotIn(f'"{forbidden}":'.encode(), encoded)

    def test_policy_is_exact_result_unpinned_and_terminal_unpromised(self) -> None:
        validated = P3.validate_policy(self.policy, self.runtime_lock)
        self.assertEqual(validated["policy_id"], "MAJORANA-P3-S0")
        boundary = validated["precommit_boundary"]
        self.assertFalse(boundary["policy_contains_observed_P3_replay_results"])
        self.assertFalse(boundary["policy_contains_P3_witness_or_result_hashes"])
        self.assertFalse(boundary["policy_promises_a_terminal_branch"])
        encoded = P3.canonical_bytes(validated)
        for forbidden in validated["forbidden_formal_result_pins"]:
            self.assertNotIn(f'"{forbidden}":'.encode(), encoded)

    def test_precommit_contract_closes_every_outer_input(self) -> None:
        validated = P3.validate_precommit_contract(self.precommit)
        self.assertEqual(
            validated["contract_type"],
            "majorana_p3_result_unpinned_formal_replay_input_and_isolation_contract_v1",
        )
        self.assertEqual(
            validated["self_relative_path"], P3.PRECOMMIT_CONTRACT_NAME
        )
        self.assertEqual(validated["required_parent_commit"], PARENT_COMMIT)
        self.assertEqual(
            tuple(row["relative_path"] for row in validated["source_files"]),
            EXPECTED_SOURCE_PATHS,
        )
        self.assertEqual(
            tuple(validated["forbidden_formal_result_pins"]),
            tuple(self.policy["forbidden_formal_result_pins"]),
        )

    def test_outer_closure_is_the_P1_P2_lifecycle_union_plus_P3(self) -> None:
        p1 = P3.load_json(BASE / "majorana_certificate_p1_precommit_contract.json")
        p2 = P3.load_json(BASE / "majorana_certificate_p2_precommit_contract.json")
        inherited = {
            row["relative_path"]
            for contract in (p1, p2)
            for row in contract["source_files"]
        }
        expected = inherited | {
            "majorana_certificate_p2_precommit_contract.json",
            *P2_RESULT_CANARIES,
            "majorana_certificate_p3/majorana_p3_runner.jl",
            "majorana_certificate_p3_checker.py",
            "majorana_certificate_p3_fixture.json",
            "majorana_certificate_p3_policy.json",
            "test_majorana_certificate_p3.py",
        }
        self.assertEqual(set(EXPECTED_SOURCE_PATHS), expected)

    def test_source_pins_are_sorted_regular_and_same_byte(self) -> None:
        paths = []
        for row in self.precommit["source_files"]:
            relative = row["relative_path"]
            paths.append(relative)
            self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
            path = BASE / relative
            self.assertFalse(path.is_symlink(), relative)
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(path.stat().st_size, row["size_bytes"], relative)
            self.assertEqual(_sha256(path), row["sha256"], relative)
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(tuple(paths), EXPECTED_SOURCE_PATHS)

    def test_runner_stage_is_the_exact_six_file_subset(self) -> None:
        staged = tuple(self.precommit["runner_staged_files"])
        self.assertEqual(staged, RUNNER_STAGED_PATHS)
        source_paths = {row["relative_path"] for row in self.precommit["source_files"]}
        self.assertTrue(set(staged).issubset(source_paths))
        self.assertEqual(tuple(self.precommit["runner_forbidden_paths"]), (*P2_RESULT_CANARIES, *P3_RESULT_ARTIFACTS))
        self.assertTrue(set(P2_RESULT_CANARIES).isdisjoint(staged))
        self.assertTrue(set(P3_RESULT_ARTIFACTS).isdisjoint(staged))
        self.assertNotIn(P3.POLICY_NAME, staged)
        self.assertNotIn(P3.CHECKER_NAME, staged)

    def test_runner_staging_runtime_canary_cannot_see_P2_results(self) -> None:
        with tempfile.TemporaryDirectory(prefix="majorana-p3-stage-test-") as directory:
            root = Path(directory)
            for relative in self.precommit["runner_staged_files"]:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch()
            for forbidden in (*P2_RESULT_CANARIES, *P3_RESULT_ARTIFACTS):
                self.assertFalse((root / forbidden).exists(), forbidden)
            staged_files = tuple(
                sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
            )
            self.assertEqual(staged_files, RUNNER_STAGED_PATHS)

    def test_P3_result_artifacts_are_absent_at_the_precommit_lifecycle_boundary(self) -> None:
        result_path = BASE / P3.RESULT_CONTRACT_NAME
        if not result_path.exists():
            for artifact in P3_RESULT_ARTIFACTS:
                self.assertFalse((BASE / artifact).exists(), artifact)
            return

        result = P3.load_json(result_path)
        precommit_commit = result["precommit_commit_sha"]
        repo = _repo()
        base_relative = BASE.resolve().relative_to(repo)
        for artifact in P3_RESULT_ARTIFACTS:
            relative = (base_relative / artifact).as_posix()
            probe = subprocess.run(
                ["git", "cat-file", "-e", f"{precommit_commit}:{relative}"],
                cwd=repo,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(probe.returncode, 0, artifact)

    def test_verify_precommit_is_lifecycle_aware_and_replay_free(self) -> None:
        result_paths = {(BASE / name).resolve() for name in P3_RESULT_ARTIFACTS}
        original_exists = Path.exists

        def precommit_phase_exists(path: Path) -> bool:
            if path.resolve() in result_paths:
                return False
            return original_exists(path)

        with mock.patch.object(P3, "fresh_replay", side_effect=AssertionError("replay called"), create=True):
            if any(original_exists(path) for path in result_paths):
                with mock.patch.object(Path, "exists", new=precommit_phase_exists):
                    summary = P3.verify_precommit()
            else:
                summary = P3.verify_precommit()
        self.assertEqual(summary["scope_ceiling"], P3.MAXIMUM_STATUS)
        self.assertEqual(summary["required_parent_commit"], PARENT_COMMIT)
        self.assertEqual(summary["required_parent_status"], PARENT_STATUS)

    def test_direct_parent_artifacts_match_fixture_and_parent_commit(self) -> None:
        anchors = {
            "result_contract_sha256": "majorana_certificate_p2_contract.json",
            "certificate_sha256": "majorana_certificate_p2_certificate.json",
            "fixture_sha256": "majorana_certificate_p2_fixture.json",
            "policy_sha256": "majorana_certificate_p2_policy.json",
            "runner_sha256": "majorana_certificate_p2/majorana_p2_runner.jl",
            "checker_sha256": "majorana_certificate_p2_checker.py",
        }
        parent = self.fixture["required_parent"]
        self.assertEqual(parent["commit"], PARENT_COMMIT)
        self.assertEqual(parent["status"], PARENT_STATUS)
        repo = _repo()
        base_relative = BASE.resolve().relative_to(repo)
        resolved = subprocess.run(
            ["git", "rev-parse", PARENT_COMMIT],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
        self.assertEqual(resolved, PARENT_COMMIT)
        for field, relative in anchors.items():
            active = (BASE / relative).read_bytes()
            self.assertEqual(hashlib.sha256(active).hexdigest(), parent[field], relative)
            committed = subprocess.run(
                ["git", "show", f"{PARENT_COMMIT}:{(base_relative / relative).as_posix()}"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout
            self.assertEqual(active, committed, relative)
        parent_certificate = P3.load_json(BASE / "majorana_certificate_p2_certificate.json")
        self.assertEqual(parent_certificate["status"], PARENT_STATUS)

    def test_fixed_schedule_and_exact_angle_domain(self) -> None:
        relation = self.fixture["frozen_execution_relation"]
        self.assertEqual(relation["composite_count"], 512)
        self.assertEqual(relation["constituent_count"], 1152)
        self.assertEqual(relation["truncation_boundary_count"], 768)
        self.assertEqual(relation["threshold_rational"], "1/17179869184")
        self.assertEqual(relation["threshold_Float64_bits_hex"], "3dd0000000000000")
        self.assertTrue(relation["P3_must_freshly_execute_the_route"])
        self.assertTrue(relation["P2_result_is_post_replay_conformance_evidence_not_a_runner_input"])
        self.assertEqual(self.schedule["stage_count"], 9)
        self.assertEqual(self.schedule["composite_count"], 512)
        self.assertEqual(self.schedule["constituent_count"], 1152)
        self.assertEqual(self.schedule["truncation_boundary_count"], 768)
        self.assertEqual(
            set(self.fixture["exact_prefix_target"]["allowed_exact_applied_angles"]),
            {"-1/50", "-1/100", "-1/200", "1/200", "1/100", "1/50"},
        )

    def test_constituents_remain_unsigned_mask_sorted(self) -> None:
        for composite in self.schedule["composites"]:
            masks = [int(row["mask_hex"], 16) for row in composite["constituents"]]
            self.assertEqual(masks, sorted(masks))
            self.assertEqual(len(masks), len(set(masks)))

    def test_accuracy_arithmetic_and_allocation_are_frozen(self) -> None:
        arithmetic = self.fixture["outward_arithmetic"]
        self.assertEqual(arithmetic["taylor_order"], 7)
        self.assertEqual(arithmetic["maximum_absolute_exact_angle"], "1/50")
        self.assertEqual(int(arithmetic["trig_grid_denominator"]), 2**128)
        self.assertEqual(int(arithmetic["defect_grid_denominator"]), 2**128)
        self.assertEqual(arithmetic["maximum_BigInt_bit_length"], 2048)
        self.assertTrue(arithmetic["no_scalar_double_count_of_outward_widening"])
        allocation = self.fixture["allocation"]
        self.assertEqual(Fraction(allocation["prefix_total_error_allocation"]), Fraction(1, 400000))
        self.assertEqual(allocation["comparison"], "strict_total_operator_error_upper_less_than_allocation")

    def test_accuracy_event_caps_are_exact_and_additive(self) -> None:
        caps = self.fixture["deterministic_resource_caps"]
        self.assertEqual(caps["maximum_anticommuting_events"], 2**19)
        self.assertEqual(caps["maximum_product_defect_events"], 2**20)
        self.assertEqual(caps["maximum_merge_defect_events"], 2**19)
        self.assertEqual(caps["maximum_drop_defect_events"], 2**19)
        self.assertEqual(caps["maximum_accuracy_charged_events"], 2**21)
        self.assertEqual(
            caps["maximum_accuracy_charged_events"],
            caps["maximum_product_defect_events"]
            + caps["maximum_merge_defect_events"]
            + caps["maximum_drop_defect_events"],
        )
        self.assertEqual(caps["maximum_total_P2_plus_accuracy_charged_events"], 2**26)
        self.assertEqual(caps["maximum_trig_table_entries"], 6)

    def test_host_caps_and_fail_closed_branch_are_frozen(self) -> None:
        host = self.fixture["host_supervisor_caps"]
        self.assertTrue(host["systemd_user_scope_cgroup_v2_required"])
        self.assertEqual(host["RuntimeMaxSec"], "300s")
        self.assertEqual(host["MemoryMax_bytes"], 2**32)
        self.assertEqual(host["subprocess_safety_timeout_seconds"], 330)
        self.assertEqual(host["maximum_stdout_bytes"], 2**23)
        self.assertEqual(host["maximum_stderr_bytes"], 2**20)
        self.assertEqual(host["host_cap_failure_branch"], "INDETERMINATE")

    def test_replay_environment_custody_is_exact_and_outside_both_closures(self) -> None:
        custody = self.policy["replay_environment_custody"]
        rows = custody["exact_sandbox_regular_file_targets"]
        observed = tuple((row["role"], row["sandbox_path"]) for row in rows)
        self.assertEqual(observed, REPLAY_ENVIRONMENT_TARGETS)
        self.assertEqual(custody["exact_sandbox_regular_file_target_count"], 18)
        self.assertEqual(
            [row["sandbox_path"] for row in rows],
            sorted(row["sandbox_path"] for row in rows),
        )
        self.assertEqual(len({row["sandbox_path"] for row in rows}), 18)
        self.assertTrue(custody["all_environment_custody_targets_are_read_only"])
        self.assertEqual(custody["only_writable_host_backed_bind_mount_target"], "/scratch")
        self.assertEqual(custody["private_kernel_virtual_mount_targets"], ["/dev", "/proc"])
        self.assertEqual((custody["LANG"], custody["LC_ALL"]), ("C.UTF-8", "C.UTF-8"))
        self.assertTrue(custody["pre_and_post_replay_manifests_must_match_exactly"])
        self.assertEqual(
            custody["package_manifest_row_exact_keys"],
            ["role", "sandbox_path", "mode", "size_bytes", "sha256"],
        )
        self.assertEqual(custody["package_manifest_rows_are_sorted_by"], "sandbox_path")
        self.assertTrue(custody["package_excludes_host_source_absolute_path_mtime_and_inode"])
        self.assertTrue(custody["canonical_witness_excludes_replay_environment_custody"])
        self.assertEqual(
            custody["generation_missing_nonregular_or_changed_custody_branch"],
            "INDETERMINATE",
        )
        self.assertEqual(
            custody["recorded_package_structure_or_digest_mismatch_branch"],
            "INVALID_REPLAY",
        )
        self.assertTrue(self.policy["result_determinism"]["PID_namespace_unshared"])
        source_paths = {row["relative_path"] for row in self.precommit["source_files"]}
        self.assertEqual(len(source_paths), 27)
        self.assertEqual(len(self.precommit["runner_staged_files"]), 6)
        for _role, sandbox_path in REPLAY_ENVIRONMENT_TARGETS:
            self.assertNotIn(sandbox_path, source_paths)
            self.assertNotIn(sandbox_path, self.precommit["runner_staged_files"])

    def test_recorded_replay_environment_manifest_schema_fails_closed(self) -> None:
        rows = [
            {
                "role": role,
                "sandbox_path": sandbox_path,
                "mode": 0o644,
                "size_bytes": 1,
                "sha256": hashlib.sha256(sandbox_path.encode()).hexdigest(),
            }
            for role, sandbox_path in REPLAY_ENVIRONMENT_TARGETS
        ]
        self.assertEqual(P3._validate_environment_manifest(copy.deepcopy(rows)), rows)
        mutants = []
        candidate = copy.deepcopy(rows)
        candidate[0:2] = reversed(candidate[0:2])
        mutants.append(candidate)
        candidate = copy.deepcopy(rows)
        candidate[0]["sandbox_path"] = "/"
        mutants.append(candidate)
        candidate = copy.deepcopy(rows)
        candidate[0]["source_realpath"] = "/host/loader"
        mutants.append(candidate)
        candidate = copy.deepcopy(rows)
        candidate[0]["size_bytes"] = 0
        mutants.append(candidate)
        candidate = copy.deepcopy(rows)
        candidate[0]["role"] = "UNDECLARED_ROLE"
        mutants.append(candidate)
        for candidate in mutants:
            with self.assertRaises((P3.SchemaError, P3.VerificationError)):
                P3._validate_environment_manifest(candidate)
        package_validator_source = inspect.getsource(P3._validate_replay_package)
        self.assertIn("host_abi_and_locale_custody_sha256", package_validator_source)
        self.assertIn("canonical_sha256(environment)", package_validator_source)
        self.assertIn("PID_isolation", package_validator_source)

    def test_binary64_decode_is_exact_dyadic_and_rejects_nonfinite(self) -> None:
        self.assertEqual(P3.decode_binary64_bits("0000000000000000"), Fraction(0))
        self.assertEqual(P3.decode_binary64_bits("3ff0000000000000"), Fraction(1))
        self.assertEqual(P3.decode_binary64_bits("c004000000000000"), Fraction(-5, 2))
        self.assertEqual(P3.decode_binary64_bits("0000000000000001"), Fraction(1, 2**1074))
        for bits in ("7ff0000000000000", "fff0000000000000", "7ff8000000000001"):
            with self.assertRaises((P3.SchemaError, P3.VerificationError)):
                P3.decode_binary64_bits(bits)

    def test_binary64_rounding_is_round_to_nearest_ties_to_even(self) -> None:
        round_bits = P3.round_fraction_to_binary64_bits
        self.assertEqual(round_bits(Fraction(1)), "3ff0000000000000")
        self.assertEqual(round_bits(Fraction(-5, 2)), "c004000000000000")
        self.assertEqual(round_bits(Fraction(1) + Fraction(1, 2**53)), "3ff0000000000000")
        self.assertEqual(
            round_bits(Fraction(1) + Fraction(1, 2**53) + Fraction(1, 2**55)),
            "3ff0000000000001",
        )
        self.assertEqual(
            round_bits(Fraction(1) + Fraction(3, 2**53)),
            "3ff0000000000002",
        )
        self.assertEqual(round_bits(Fraction(-1) - Fraction(1, 2**53)), "bff0000000000000")
        self.assertEqual(round_bits(Fraction(1, 2**1075)), "0000000000000000")
        self.assertEqual(round_bits(Fraction(3, 2**1075)), "0000000000000002")
        self.assertEqual(
            round_bits(Fraction(2**53 - 1, 2**1075)),
            "0010000000000000",
        )

    def test_binary64_add_and_multiply_use_the_integer_RNE_oracle(self) -> None:
        self.assertEqual(
            P3.binary64_add_bits("3ff0000000000000", "3ca0000000000000"),
            "3ff0000000000000",
        )
        self.assertEqual(
            P3.binary64_add_bits("3ff0000000000000", "3cb0000000000000"),
            "3ff0000000000001",
        )
        self.assertEqual(
            P3.binary64_add_bits("3ff0000000000000", "bff0000000000000"),
            "0000000000000000",
        )
        self.assertEqual(
            P3.binary64_mul_bits("3ff8000000000000", "4000000000000000"),
            "4008000000000000",
        )
        self.assertEqual(
            P3.binary64_mul_bits("bfe0000000000000", "4000000000000000"),
            "bff0000000000000",
        )

    def test_binary64_signed_zero_rules_are_bit_exact(self) -> None:
        positive_zero = "0000000000000000"
        negative_zero = "8000000000000000"
        positive_two = "4000000000000000"
        negative_two = "c000000000000000"
        self.assertEqual(P3.binary64_add_bits(negative_zero, negative_zero), negative_zero)
        self.assertEqual(P3.binary64_add_bits(positive_zero, negative_zero), positive_zero)
        self.assertEqual(P3.binary64_mul_bits(negative_zero, positive_two), negative_zero)
        self.assertEqual(P3.binary64_mul_bits(negative_zero, negative_two), positive_zero)

    def test_trig_intervals_equal_an_independent_order7_fraction_oracle(self) -> None:
        for encoded in self.fixture["exact_prefix_target"]["allowed_exact_applied_angles"]:
            theta = Fraction(encoded)
            for kind in ("sin", "cos"):
                expected = _expected_trig_ticks(theta, kind)
                observed = P3.trig_interval_ticks(
                    theta, kind, order=7, denominator=2**128
                )
                self.assertEqual(observed, expected, (encoded, kind))

    def test_trig_zero_and_parity_are_exact(self) -> None:
        grid = 2**128
        self.assertEqual(P3.trig_interval_ticks(Fraction(0), "sin"), (0, 0))
        self.assertEqual(P3.trig_interval_ticks(Fraction(0), "cos"), (grid, grid))
        for theta in (Fraction(1, 200), Fraction(1, 100), Fraction(1, 50)):
            sin_pos = P3.trig_interval_ticks(theta, "sin")
            sin_neg = P3.trig_interval_ticks(-theta, "sin")
            cos_pos = P3.trig_interval_ticks(theta, "cos")
            cos_neg = P3.trig_interval_ticks(-theta, "cos")
            self.assertEqual(sin_neg, (-sin_pos[1], -sin_pos[0]))
            self.assertEqual(cos_neg, cos_pos)

    def test_local_product_defect_rounds_outward_and_never_down(self) -> None:
        grid = 2**128
        one = "3ff0000000000000"
        minus_two = "c000000000000000"
        self.assertEqual(
            P3.local_product_defect_upper_ticks(one, one, (grid, grid)), 0
        )
        self.assertEqual(
            P3.local_product_defect_upper_ticks(one, one, (grid - 1, grid)), 1
        )
        self.assertEqual(
            P3.local_product_defect_upper_ticks(
                minus_two, one, (grid - 2, grid + 1)
            ),
            4,
        )
        self.assertEqual(
            P3.local_product_defect_upper_ticks(
                minus_two, one, (grid - 2, grid + 1), sign=-1
            ),
            4,
        )

    def test_merge_and_drop_defects_use_exact_dyadics_and_outward_ticks(self) -> None:
        one = "3ff0000000000000"
        half = "3fe0000000000000"
        two_to_minus_53 = "3ca0000000000000"
        threshold = "3dd0000000000000"
        self.assertEqual(P3.merge_defect_upper_ticks(half, half, one), 0)
        self.assertEqual(
            P3.merge_defect_upper_ticks(one, two_to_minus_53, one),
            2**75,
        )
        self.assertEqual(P3.drop_defect_upper_ticks(threshold), 2**94)
        self.assertEqual(P3.drop_defect_upper_ticks("0000000000000000"), 0)
        self.assertEqual(P3.drop_defect_upper_ticks("8000000000000000"), 0)

    def test_majorana_local_target_and_sign_are_independent(self) -> None:
        self.assertFalse(P3._majorana_commutes(0x3, 0x5))
        self.assertTrue(P3._majorana_commutes(0x3, 0xC))
        self.assertEqual(P3._majorana_product_target_sign(0x3, 0x5), (0x6, 1))
        self.assertEqual(P3._majorana_product_target_sign(0x3, 0x2), (0x1, -1))

    def test_parent_P2_post_replay_conformance_rejects_digest_mutations(self) -> None:
        self.assertTrue(callable(P3._validate_parent_p2_conformance))
        parent = P3.load_json(BASE / "majorana_certificate_p2_contract.json")["witness"]
        p2_execution = parent["execution"]
        direct_fields = (
            "completed_composite_count",
            "completed_constituent_count",
            "completed_truncation_boundary_count",
            "peak_premerge_contribution_count",
            "peak_postmerge_unique_term_count",
            "anticommuting_split_count",
            "threshold_dropped_term_count",
            "exact_zero_dropped_term_count",
            "cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex",
        )
        final_fields = (
            "retained_term_count",
            "term_stream_sha256",
            "checkerboard_Neel_occupied_mask_hex",
            "checkerboard_Neel_up_count",
            "checkerboard_Neel_down_count",
            "checkerboard_Neel_expectation_Float64_diagnostic_bits_hex",
            "checkerboard_Neel_contribution_stream_sha256",
        )
        witness = {
            "initial_observable": copy.deepcopy(parent["initial_observable"]),
            "schedule": copy.deepcopy(parent["schedule"]),
            "execution": {
                **{field: p2_execution[field] for field in direct_fields},
                "P2_resource_counters": copy.deepcopy(p2_execution["counters"]),
                "P2_transition_records_sha256": p2_execution["transition_records_sha256"],
                "P2_boundary_records_sha256": p2_execution["boundary_records_sha256"],
                "P2_stage_records_sha256": p2_execution["stage_records_sha256"],
            },
            "final_state": {
                field: copy.deepcopy(parent["final_state"][field])
                for field in final_fields
            },
        }
        P3._validate_parent_p2_conformance(witness, self.fixture)
        mutations = (
            ("execution", "P2_transition_records_sha256"),
            ("final_state", "term_stream_sha256"),
            ("final_state", "checkerboard_Neel_contribution_stream_sha256"),
        )
        for section, field in mutations:
            candidate = copy.deepcopy(witness)
            candidate[section][field] = "0" * 64
            with self.assertRaises((P3.SchemaError, P3.VerificationError)):
                P3._validate_parent_p2_conformance(candidate, self.fixture)

    def test_runner_declares_only_aggregate_schema_and_no_parent_result_canary(self) -> None:
        source = (BASE / P3.RUNNER_RELATIVE_PATH).read_text()
        for canary in P2_RESULT_CANARIES:
            self.assertNotIn(canary, source)
        for key in (
            "runtime",
            "upstream",
            "initial_observable",
            "schedule",
            "trig_table",
            "execution",
            "accuracy_ledger",
            "final_state",
            "scope",
        ):
            self.assertRegex(source, re.compile(rf'(?:"{key}"|\b{key}\s*=)'))
        self.assertIn("length(ARGS) == 2", source)
        self.assertIn("P3_FIXTURE.json P2_FIXTURE.json", source)
        self.assertRegex(source, re.compile(r"P3[^\n=]*=\s*abspath\(ARGS\[1\]\)", re.IGNORECASE))
        self.assertRegex(source, re.compile(r"P2[^\n=]*=\s*abspath\(ARGS\[2\]\)", re.IGNORECASE))
        self.assertNotIn("million_row", source.lower())

    def test_bubblewrap_never_exposes_the_host_root_read_only(self) -> None:
        source = (BASE / P3.CHECKER_NAME).read_text()
        normalized = " ".join(source.replace("\n", " ").split())
        self.assertNotIn('"--ro-bind", "/", "/"', normalized)
        self.assertNotIn("--ro-bind / /", normalized)
        for required in ("--unshare-net", "--ro-bind", "staging", "depot", "scratch"):
            self.assertIn(required, source)
        self.assertEqual(tuple(P3.REPLAY_ENVIRONMENT_TARGETS), REPLAY_ENVIRONMENT_TARGETS)
        self.assertNotIn("locale.rglob", source)
        self.assertNotIn("locale.glob", source)
        for broad_mount in ("/usr", "/usr/lib", "/lib", "/lib64", "/etc", "/Data"):
            self.assertNotIn(f'"--ro-bind", "{broad_mount}", "{broad_mount}"', normalized)
        self.assertIn("C.UTF-8", source)
        for canary in P2_RESULT_CANARIES:
            self.assertNotIn(f'runner_visible:{canary}', source)

    def test_isolated_replay_closes_pid_stream_and_executable_identity_gaps(self) -> None:
        source = inspect.getsource(P3._run_one_isolated_replay)
        self.assertIn('"--unshare-pid"', source)
        join_position = source.rfind("reader.join")
        self.assertGreater(join_position, 0)
        post_join = source[join_position:]
        self.assertIn("stdout_exceeded.is_set()", post_join)
        self.assertIn("stderr_exceeded.is_set()", post_join)
        self.assertRegex(
            post_join,
            re.compile(r'len\(stdout\)\s*>\s*host\["maximum_stdout_bytes"\]'),
        )
        self.assertRegex(
            post_join,
            re.compile(r'len\(stderr\)\s*>\s*host\["maximum_stderr_bytes"\]'),
        )
        self.assertIn("julia_executable.resolve()", source)
        self.assertRegex(
            source,
            re.compile(r'runtime_root\s*/\s*"bin"\s*/\s*"julia"'),
        )
        self.assertIn("sandbox Julia executable", source)

    def test_checker_binary64_oracle_has_no_math_libm_or_struct_fallback(self) -> None:
        source = (BASE / P3.CHECKER_NAME).read_text()
        self.assertNotRegex(source, re.compile(r"(?m)^\s*import\s+math(?:\s|$)"))
        self.assertNotRegex(source, re.compile(r"(?m)^\s*from\s+math\s+import\s+"))
        self.assertNotIn("math.sin", source)
        self.assertNotIn("math.cos", source)
        self.assertNotIn("struct.pack", source)
        self.assertNotIn("struct.unpack", source)

    def test_scope_and_statuses_cannot_promote_to_R100_reference_or_READY(self) -> None:
        scope = self.policy["scope_boundary"]
        self.assertTrue(scope["fixed_L8_first_fused_mapped_step_exact_prefix_only"])
        self.assertEqual(scope["remaining_99_mapped_steps_or_full_R100"], "NOT_ASSESSED")
        self.assertEqual(scope["product_formula_to_exact_Hubbard_error"], "NOT_ASSESSED")
        self.assertEqual(scope["double_occupancy"], "NOT_ASSESSED")
        self.assertFalse(scope["physical_reference_qualified"])
        self.assertFalse(scope["ready_gate_eligible"])
        branches = {row["branch"]: row for row in self.policy["legal_terminal_branches"]}
        self.assertEqual(branches["BOUND_WITHIN_PREFIX_ALLOCATION"]["maximum_status"], P3.MAXIMUM_STATUS)
        self.assertEqual(branches["BOUND_EXCEEDS_PREFIX_ALLOCATION"]["maximum_status"], P3.EXCEEDS_STATUS)
        self.assertEqual(branches["DETERMINISTIC_POLICY_CAP_EXCEEDED"]["maximum_status"], P3.CAP_STATUS)

    def test_fixture_policy_and_contract_mutations_fail_closed(self) -> None:
        fixture_mutants = []
        mutant = copy.deepcopy(self.fixture)
        mutant["outward_arithmetic"]["taylor_order"] = 6
        fixture_mutants.append(mutant)
        mutant = copy.deepcopy(self.fixture)
        mutant["outward_arithmetic"]["trig_grid_denominator"] = str(2**127)
        fixture_mutants.append(mutant)
        mutant = copy.deepcopy(self.fixture)
        mutant["allocation"]["prefix_total_error_allocation"] = "1/399999"
        fixture_mutants.append(mutant)
        mutant = copy.deepcopy(self.fixture)
        mutant["frozen_execution_relation"]["P2_result_is_post_replay_conformance_evidence_not_a_runner_input"] = False
        fixture_mutants.append(mutant)
        for candidate in fixture_mutants:
            with self.assertRaises((P3.SchemaError, P3.VerificationError)):
                P3.validate_fixture(candidate)

        policy_mutants = []
        mutant_policy = copy.deepcopy(self.policy)
        mutant_policy["scope_boundary"]["ready_gate_eligible"] = True
        policy_mutants.append(mutant_policy)
        mutant_policy = copy.deepcopy(self.policy)
        mutant_policy["replay_environment_custody"]["exact_sandbox_regular_file_targets"][0][
            "sandbox_path"
        ] = "/"
        policy_mutants.append(mutant_policy)
        mutant_policy = copy.deepcopy(self.policy)
        custody = mutant_policy["replay_environment_custody"]
        custody["exact_sandbox_regular_file_targets"][0:2] = reversed(
            custody["exact_sandbox_regular_file_targets"][0:2]
        )
        policy_mutants.append(mutant_policy)
        mutant_policy = copy.deepcopy(self.policy)
        mutant_policy["replay_environment_custody"][
            "all_environment_custody_targets_are_read_only"
        ] = False
        policy_mutants.append(mutant_policy)
        mutant_policy = copy.deepcopy(self.policy)
        mutant_policy["replay_environment_custody"][
            "only_writable_host_backed_bind_mount_target"
        ] = "/"
        policy_mutants.append(mutant_policy)
        mutant_policy = copy.deepcopy(self.policy)
        mutant_policy["replay_environment_custody"][
            "private_kernel_virtual_mount_targets"
        ].append("/sys")
        policy_mutants.append(mutant_policy)
        mutant_policy = copy.deepcopy(self.policy)
        mutant_policy["replay_environment_custody"]["LC_ALL"] = "C"
        policy_mutants.append(mutant_policy)
        mutant_policy = copy.deepcopy(self.policy)
        mutant_policy["replay_environment_custody"][
            "generation_missing_nonregular_or_changed_custody_branch"
        ] = "BOUND_WITHIN_PREFIX_ALLOCATION"
        policy_mutants.append(mutant_policy)
        for candidate in policy_mutants:
            with self.assertRaises((P3.SchemaError, P3.VerificationError)):
                P3.validate_policy(candidate, self.runtime_lock)

        mutant_contract = copy.deepcopy(self.precommit)
        mutant_contract["required_parent_commit"] = "0" * 40
        with self.assertRaises((P3.SchemaError, P3.VerificationError)):
            P3.validate_precommit_contract(mutant_contract)

        mutant_contract = copy.deepcopy(self.precommit)
        mutant_contract["self_relative_path"] = "majorana_certificate_p3_contract.json"
        with self.assertRaises((P3.SchemaError, P3.VerificationError)):
            P3.validate_precommit_contract(mutant_contract)

        mutant_contract = copy.deepcopy(self.precommit)
        mutant_contract["runner_staged_files"].append("majorana_certificate_p2_contract.json")
        with self.assertRaises((P3.SchemaError, P3.VerificationError)):
            P3.validate_precommit_contract(mutant_contract)

        mutant_contract = copy.deepcopy(self.precommit)
        mutant_contract["source_files"][0]["sha256"] = "0" * 64
        with self.assertRaises((P3.SchemaError, P3.VerificationError)):
            P3.validate_precommit_contract(mutant_contract)

    def test_strict_json_rejects_duplicate_keys_and_float_tokens(self) -> None:
        with self.assertRaises(P3.SchemaError):
            P3.strict_json_loads(b'{"x":1,"x":2}', source="duplicate")
        with self.assertRaises(P3.SchemaError):
            P3.strict_json_loads(b'{"x":1.5}', source="float")

    def test_required_adversarial_mutation_classes_are_all_precommitted(self) -> None:
        mutations = set(self.policy["required_adversarial_mutations"])
        required = {
            "USE_FLOAT_ANGLE_AS_THE_IDEAL_ANGLE",
            "REMOVE_OR_INWARD_ROUND_THE_TAYLOR_REMAINDER",
            "ROUND_ONE_DEFECT_ROW_DOWN_BY_ONE_TICK",
            "OMIT_A_COSINE_OR_SINE_CONTRIBUTION",
            "FLIP_A_MAJORANA_BRANCH_SIGN_OR_TARGET_MASK",
            "OMIT_A_MERGE_COLLISION_OR_TREAT_FLOAT_ADDITION_AS_EXACT",
            "CHANGE_STRICT_THRESHOLD_TO_LESS_OR_EQUAL_OR_TRUNCATE_BEFORE_MERGE",
            "REUSE_THE_P2_FLOAT_DIAGNOSTIC_DROP_SUM_OR_EXPECTATION_AS_AUTHORITY",
            "USE_COEFFICIENT_L2_INSTEAD_OF_L1_FOR_AN_OPERATOR_BOUND",
            "READ_THE_P2_RESULT_AS_A_JULIA_EXECUTION_INPUT",
            "TREAT_TIMEOUT_OOM_OR_SANDBOX_FAILURE_AS_AN_ALLOCATION_RESULT",
            "MOUNT_HOST_ROOT_OR_A_BROAD_HOST_DIRECTORY_IN_THE_RUNNER_SANDBOX",
            "OMIT_CHANGE_OR_MAKE_WRITABLE_A_HOST_ABI_OR_C_UTF_8_CUSTODY_TARGET",
            "PUT_HOST_SOURCE_PATH_MTIME_INODE_OR_ENVIRONMENT_CUSTODY_IN_THE_CANONICAL_WITNESS",
            "FORGE_THE_RECORDED_REPLAY_ENVIRONMENT_PACKAGE_MANIFEST_OR_DIGEST",
            "TREAT_MISSING_OR_CHANGED_GENERATION_ENVIRONMENT_CUSTODY_AS_A_MATHEMATICAL_RESULT",
            "ALLOW_A_P3_RESULT_ARTIFACT_IN_THE_PRECOMMIT_TREE",
            "EXPAND_AUTHORITY_TO_RAW_THRESHOLD_R100_EXACT_HUBBARD_REFERENCE_OR_READY",
        }
        self.assertTrue(required.issubset(mutations))

    def test_contract_has_no_placeholder_or_observed_result_pin(self) -> None:
        raw = (BASE / P3.PRECOMMIT_CONTRACT_NAME).read_bytes()
        self.assertNotIn(b"PENDING_SHA256", raw)
        self.assertNotIn(b"PLACEHOLDER", raw)
        for forbidden in self.policy["forbidden_formal_result_pins"]:
            self.assertNotRegex(raw, re.compile(rb'"' + re.escape(forbidden.encode()) + rb'"\s*:'))


if __name__ == "__main__":
    unittest.main()
