#!/usr/bin/env python3
"""Result-unpinned policy, custody, branch, and isolation tests for M q90 S0."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECKER = load_module(
    "hubbard_l8_magnetization_q90_formal_s0_checker",
    "hubbard_l8_magnetization_q90_formal_s0_checker.py",
)


def raw(filename: str) -> bytes:
    return (HERE / filename).read_bytes()


def load_json(filename: str):
    return CHECKER.strict_json_bytes(raw(filename), filename)


POLICY = load_json(CHECKER.POLICY_NAME)
CONTRACT = load_json(CHECKER.PRECOMMIT_CONTRACT_NAME)


def collect_hex_digests(value):
    output = set()
    if isinstance(value, dict):
        for key, item in value.items():
            output.update(collect_hex_digests(key))
            output.update(collect_hex_digests(item))
    elif isinstance(value, list):
        for item in value:
            output.update(collect_hex_digests(item))
    elif isinstance(value, str) and len(value) == 64:
        try:
            int(value, 16)
        except ValueError:
            pass
        else:
            output.add(value)
    return output


class MQ90FormalS0PrecommitTests(unittest.TestCase):
    def test_01_policy_checker_and_contract_hashes_are_exact(self):
        policy_sha = hashlib.sha256(raw(CHECKER.POLICY_NAME)).hexdigest()
        checker_sha = hashlib.sha256(raw(CHECKER.SELF_NAME)).hexdigest()
        self.assertEqual(policy_sha, CHECKER.POLICY_FILE_SHA256)
        self.assertEqual(CHECKER.canonical_sha256(POLICY), CHECKER.POLICY_CANONICAL_SHA256)
        self.assertEqual(CONTRACT["policy_file_sha256"], policy_sha)
        self.assertEqual(CONTRACT["checker_source_sha256"], checker_sha)

    def test_02_public_precommit_verifier_same_byte_executes_and_passes(self):
        result = CHECKER.verify_precommit(CONTRACT, POLICY)
        self.assertTrue(result["verified"])
        self.assertEqual(result["source_pin_count"], 13)
        self.assertEqual(result["legal_terminal_branches"], list(CHECKER.LEGAL_BRANCHES))

    def test_03_precommit_validation_never_calls_replay(self):
        with mock.patch.object(
            CHECKER, "_run_fresh_replay", side_effect=AssertionError("replay was called")
        ):
            result = CHECKER._verify_precommit_impl(CONTRACT, POLICY)
        self.assertTrue(result["verified"])

    def test_04_public_verifier_ignores_live_monkeypatch(self):
        forged = {"status": "FORGED", "verified": True}
        with mock.patch.object(CHECKER, "_verify_precommit_impl", return_value=forged):
            result = CHECKER.verify_precommit(CONTRACT, POLICY)
        self.assertNotEqual(result["status"], "FORGED")

    def test_05_policy_source_pins_match_regular_file_bytes(self):
        sources = CHECKER._read_pinned_sources(POLICY)
        self.assertEqual(len(sources), 13)
        for pin in POLICY["source_pins"]:
            payload = sources[pin["relative_path"]]
            self.assertEqual(len(payload), pin["size_bytes"])
            self.assertEqual(hashlib.sha256(payload).hexdigest(), pin["sha256"])

    def test_06_staging_tree_is_exactly_13_files_and_excludes_outcomes(self):
        sources = CHECKER._read_pinned_sources(POLICY)
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = CHECKER._stage_sources(root, POLICY, sources)
            self.assertEqual(len(manifest), 13)
            self.assertEqual(manifest, CHECKER._tree_manifest(root))
            paths = {item["relative_path"] for item in manifest}
            self.assertIn("hubbard_l8_adaptive_k_four_gate_granularity_screen.py", paths)
            self.assertTrue(all("_q90_transcript.json" not in path for path in paths))
            self.assertTrue(all("_c33_" not in path for path in paths))
            self.assertTrue(all(not path.startswith("test_") for path in paths))

    def test_07_nonempty_or_symlink_staging_tree_is_rejected(self):
        sources = CHECKER._read_pinned_sources(POLICY)
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "sentinel").symlink_to(HERE / CHECKER.POLICY_NAME)
            with self.assertRaises(CHECKER.SchemaError):
                CHECKER._stage_sources(root, POLICY, sources)

    def test_08_all_five_synthetic_terminal_shapes_classify_exactly(self):
        success = CHECKER.SUCCESS_STATUS
        failure = CHECKER.FAILURE_STATUS
        cases = [
            ([success] * 88 + [failure], None, CHECKER.LEGAL_BRANCHES[0]),
            ([success] * 88, 89, CHECKER.LEGAL_BRANCHES[1]),
            ([success] * 89 + [failure], None, CHECKER.LEGAL_BRANCHES[2]),
            ([success] * 89, 90, CHECKER.LEGAL_BRANCHES[3]),
            ([success] * 90, None, CHECKER.LEGAL_BRANCHES[4]),
        ]
        for statuses, abort_checkpoint, expected in cases:
            self.assertEqual(
                CHECKER.derive_terminal_branch(statuses, abort_checkpoint), expected
            )
        authorities = [
            CHECKER.classify_terminal_branch(branch)["scientific_negative_authority"]
            for branch in CHECKER.LEGAL_BRANCHES
        ]
        self.assertEqual(authorities, [False, False, True, False, False])

    def test_09_illegal_or_ambiguous_terminal_shapes_are_rejected(self):
        success = CHECKER.SUCCESS_STATUS
        failure = CHECKER.FAILURE_STATUS
        bad = [
            ([success] * 87, None),
            ([success] * 88 + [failure], 90),
            ([success] * 89 + [failure], 90),
            ([success] * 90, 90),
            ([success] * 88 + ["UNKNOWN"], None),
        ]
        for statuses, abort_checkpoint in bad:
            with self.assertRaises(CHECKER.VerificationError):
                CHECKER.derive_terminal_branch(statuses, abort_checkpoint)

    def test_10_candidate_matrix_recomputes_feasibility_and_monotonicity(self):
        record = {
            "pretruncation_expansion_count": 30,
            "candidate_records": [
                {
                    "candidate_index": 0,
                    "configured_K": 10,
                    "effective_retained_count": 10,
                    "dropped_term_count": 20,
                    "drop_ticks": "20",
                    "E_after_if_selected_ticks": "120",
                    "feasible_under_current_prefix_cap": False,
                },
                {
                    "candidate_index": 1,
                    "configured_K": 20,
                    "effective_retained_count": 20,
                    "dropped_term_count": 10,
                    "drop_ticks": "10",
                    "E_after_if_selected_ticks": "110",
                    "feasible_under_current_prefix_cap": True,
                },
            ],
        }
        self.assertEqual(
            CHECKER._validate_candidate_matrix(record, [10, 20], 100, 115), [1]
        )
        tampered = copy.deepcopy(record)
        tampered["candidate_records"][0]["feasible_under_current_prefix_cap"] = True
        with self.assertRaises(CHECKER.VerificationError):
            CHECKER._validate_candidate_matrix(tampered, [10, 20], 100, 115)
        tampered = copy.deepcopy(record)
        tampered["candidate_records"][1]["drop_ticks"] = "30"
        tampered["candidate_records"][1]["E_after_if_selected_ticks"] = "130"
        tampered["candidate_records"][1]["feasible_under_current_prefix_cap"] = False
        with self.assertRaises(CHECKER.VerificationError):
            CHECKER._validate_candidate_matrix(tampered, [10, 20], 100, 115)

    def test_11_policy_branch_or_type_tamper_is_rejected(self):
        tampered = copy.deepcopy(POLICY)
        tampered["legal_terminal_branches"].pop()
        with self.assertRaises(CHECKER.VerificationError):
            CHECKER._validate_policy(tampered)
        tampered = copy.deepcopy(POLICY)
        tampered["candidate_policy"]["configured_candidate_count"] = True
        with self.assertRaises(CHECKER.VerificationError):
            CHECKER._validate_policy(tampered)

    def test_12_strict_json_rejects_duplicate_keys_nonfinite_and_extra_contract_key(self):
        with self.assertRaises(CHECKER.SchemaError):
            CHECKER.strict_json_bytes(b'{"x":1,"x":2}', "duplicate")
        with self.assertRaises(CHECKER.SchemaError):
            CHECKER.strict_json_bytes(b'{"x":NaN}', "nonfinite")
        tampered = copy.deepcopy(CONTRACT)
        tampered["unexpected"] = False
        with self.assertRaises(CHECKER.SchemaError):
            CHECKER._validate_precommit_contract(
                tampered,
                POLICY,
                hashlib.sha256(raw(CHECKER.SELF_NAME)).hexdigest(),
            )

    def test_13_checker_contains_no_unregistered_64_hex_result_pin(self):
        tree = ast.parse(raw(CHECKER.SELF_NAME).decode("utf-8"))
        observed = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and len(node.value) == 64
            and all(character in "0123456789abcdef" for character in node.value)
        }
        allowed = collect_hex_digests(POLICY) | {
            CHECKER.POLICY_FILE_SHA256,
            CHECKER.POLICY_CANONICAL_SHA256,
        }
        self.assertEqual(observed - allowed, set())

    def test_14_result_artifacts_are_declared_outside_the_precommit_commit(self):
        self.assertEqual(
            CONTRACT["result_artifacts_absent_from_precommit_commit"],
            list(CHECKER.RESULT_ARTIFACTS),
        )
        pinned_paths = {pin["relative_path"] for pin in POLICY["source_pins"]}
        self.assertTrue(pinned_paths.isdisjoint(CHECKER.RESULT_ARTIFACTS))

    def test_15_cli_precommit_check_is_replay_free_and_successful(self):
        result = subprocess.run(
            ["python3", str(HERE / CHECKER.SELF_NAME)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["verified"])
        self.assertEqual(payload["source_pin_count"], 13)


if __name__ == "__main__":
    unittest.main()
