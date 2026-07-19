#!/usr/bin/env python3
"""Adversarial static tests for the proof-only P10-A design assessment."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
MODULE_PATH = BASE / "majorana_certificate_p10a_static_resource_envelope.py"
SPEC = importlib.util.spec_from_file_location(
    "majorana_certificate_p10a_static_resource_envelope", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
P10 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = P10
SPEC.loader.exec_module(P10)


class MajoranaP10AStaticResourceEnvelopeTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads((BASE / P10.FIXTURE_NAME).read_text(encoding="utf-8"))
        cls.policy = json.loads((BASE / P10.POLICY_NAME).read_text(encoding="utf-8"))

    def test_fixture_policy_source_pins_and_semantic_hashes(self) -> None:
        P10._validate_fixture(self.fixture)
        P10._validate_policy(self.policy)
        self.assertEqual(
            P10.canonical_sha256(self.fixture), P10.FIXTURE_CANONICAL_SHA256
        )
        self.assertEqual(
            P10.canonical_sha256(P10._policy_semantic(self.policy)),
            P10.POLICY_SEMANTIC_SHA256,
        )
        self.assertEqual(
            [row["relative_path"] for row in self.policy["source_files"]],
            list(P10.SOURCE_PATHS),
        )
        for row in self.policy["source_files"]:
            path = BASE / row["relative_path"]
            self.assertTrue(path.is_file())
            self.assertFalse(path.is_symlink())
            raw = path.read_bytes()
            self.assertEqual(len(raw), row["size_bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"])

    def test_frozen_static_facts_and_integer_formulas_are_rederived(self) -> None:
        facts = P10._extract_static_facts()
        self.assertEqual(facts, self.fixture["declared_static_facts"])
        self.assertEqual(facts["schedule"], {
            "stage_count": 9,
            "composite_count": 512,
            "constituent_count": 1152,
            "truncation_boundary_count": 768,
        })
        self.assertEqual(facts["segment_D"], {
            "stage_index": 3,
            "group": "H3",
            "composite_count": 48,
            "constituent_count": 96,
            "truncation_boundary_count": 48,
        })
        self.assertEqual(
            facts["static_prefix_before_segment_D"],
            {
                "completed_stage_count": 3,
                "transition_record_count": 416,
                "boundary_record_count": 304,
                "stage_record_count": 3,
            },
        )
        caps = facts["cardinality_and_arithmetic_caps"]
        self.assertEqual(caps["logical_term_cap_M"], 1 << 20)
        self.assertEqual(caps["maximum_BigInt_bit_length_L"], 2048)
        self.assertEqual(caps["frozen_step2_final_retained_term_count_N0"], 284847)
        work = facts["abstract_work_bounds"]
        self.assertEqual(work["full_schedule_selection_work_units"], 4 * 768 * (1 << 20))
        self.assertEqual(
            work["full_schedule_sort_scale_units"],
            (2 * 1152 + 3 * 768) * (1 << 20) * 20,
        )
        self.assertEqual(
            work["segment_D_sort_scale_units"],
            (2 * 96 + 3 * 48) * (1 << 20) * 20,
        )

    def test_count_relations_accept_boundaries_and_reject_off_by_one(self) -> None:
        m = 1 << 20
        accepted = P10.validate_count_relations(
            n_i=m // 2,
            a_i=m // 2,
            c_i=m // 4,
            p_i=3 * m // 4,
            ell_j=m // 3,
            k_j=m // 4,
        )
        self.assertEqual(accepted["logical_term_cap_M"], m)
        P10.validate_count_relations(
            n_i=m, a_i=0, c_i=0, p_i=m, ell_j=m, k_j=m
        )
        invalid = (
            dict(n_i=m + 1, a_i=0, c_i=0, p_i=m, ell_j=None, k_j=None),
            dict(n_i=m, a_i=1, c_i=0, p_i=m, ell_j=None, k_j=None),
            dict(n_i=3, a_i=4, c_i=0, p_i=3, ell_j=None, k_j=None),
            dict(n_i=3, a_i=2, c_i=3, p_i=3, ell_j=None, k_j=None),
            dict(n_i=3, a_i=2, c_i=1, p_i=m + 1, ell_j=None, k_j=None),
            dict(n_i=3, a_i=2, c_i=1, p_i=3, ell_j=2, k_j=3),
            dict(n_i=True, a_i=0, c_i=0, p_i=0, ell_j=None, k_j=None),
        )
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(P10.ProofError):
                P10.validate_count_relations(**row)
        with self.assertRaisesRegex(P10.ProofError, "both present or both absent"):
            P10.validate_count_relations(
                n_i=3, a_i=2, c_i=1, p_i=3, ell_j=2, k_j=None
            )

    def test_selected_source_anchors_are_exact_but_not_claimed_as_closure(self) -> None:
        summary = P10._source_anchor_summary()
        self.assertEqual(summary["anchor_count"], len(P10.SOURCE_ANCHORS))
        self.assertGreaterEqual(summary["anchor_count"], 20)
        self.assertEqual(
            summary["closure_status"],
            "SELECTED_CORE_ANCHORS_ONLY_NOT_TRANSITIVE_ALLOCATION_CLOSURE",
        )
        ids = {row["anchor_id"] for row in summary["anchors"]}
        self.assertIn("P9_DROPPED_VECTOR", ids)
        self.assertIn("P3_FINALIZER_ENTRY", ids)
        self.assertIn("P9_STEP3_INPUT_DEEPCOPY_CUSTODY", ids)
        target = P10.SOURCE_ANCHORS[1]
        original_read = P10._read_regular

        def drifted(path: Path, label: str) -> bytes:
            raw = original_read(path, label)
            if path == BASE / target[1]:
                return raw.replace(target[2], b"mutated-anchor", 1)
            return raw

        with mock.patch.object(P10, "_read_regular", side_effect=drifted):
            with self.assertRaisesRegex(P10.ProofError, "source anchor count drift"):
                P10._source_anchor_summary()

    def test_g0_projection_is_gate_obligation_and_authority_only(self) -> None:
        g0 = P10._load_json_file(P10.G0_CONTRACT)
        projection = P10._validate_g0_projection(g0)
        self.assertEqual(projection["gate_id"], P10.GATE_ID)
        self.assertEqual(projection["obligation_ids"], list(P10.OBLIGATION_IDS))
        self.assertEqual(projection["authority"]["scientific_authority"], "NONE")
        self.assertFalse(projection["authority"]["execution_authority"])
        mutated = copy.deepcopy(g0)
        mutated["execution_authority"] = True
        with self.assertRaisesRegex(P10.ProofError, "authority projection drift"):
            P10._validate_g0_projection(mutated)
        mutated = copy.deepcopy(g0)
        mutated["next_gate_contract"]["only_allowed_next_gate"] = "D5"
        with self.assertRaisesRegex(P10.ProofError, "next-gate projection drift"):
            P10._validate_g0_projection(mutated)

    def test_assessment_is_closed_while_admission_remains_not_established(self) -> None:
        assessment = P10.build_assessment(self.fixture, self.policy)
        self.assertEqual(assessment["assessment_lifecycle_status"], "CLOSED")
        self.assertEqual(assessment["outcome_classification"], "ASSESSED_NOT_ESTABLISHED")
        self.assertIsNone(assessment["byte_envelope"]["exact_static_peak_bytes"])
        self.assertIsNone(
            assessment["byte_envelope"]["strict_integer_peak_less_than_cap"]
        )
        self.assertEqual(assessment["admission"]["execution_gate"], "CLOSED")
        self.assertFalse(assessment["admission"]["future_execution_prerequisite_satisfied"])
        obligations = assessment["proof_obligations"]
        self.assertEqual(obligations["obligation_count"], 7)
        self.assertEqual(obligations["verified_obligation_count"], 0)
        self.assertFalse(obligations["all_seven_obligations_positive"])
        self.assertEqual(
            {row["current_status"] for row in obligations["rows"]},
            {"NOT_ESTABLISHED"},
        )
        self.assertTrue(assessment["operation_cost"]["units_are_not_seconds"])
        self.assertTrue(
            assessment["operation_cost"]["sort_scale_is_not_an_actual_comparison_count"]
        )

    def _valid_in_memory_report(self) -> dict:
        return {
            "schema_version": 1,
            "report_type": P10.REPORT_TYPE,
            "status": P10.REPORT_STATUS,
            "gate_id": P10.GATE_ID,
            "fixture_id": P10.FIXTURE_ID,
            "policy_id": P10.POLICY_ID,
            "preprobe_commit": "a" * 40,
            "preprobe_source_summary": P10._preprobe_source_summary(self.policy),
            "authority": copy.deepcopy(self.fixture["authority"]),
            "assessment": P10.build_assessment(self.fixture, self.policy),
        }

    def test_report_rejects_forged_positive_peak_authority_and_no_go(self) -> None:
        report = self._valid_in_memory_report()
        lifecycle_patches = (
            mock.patch.object(P10, "_validate_preprobe_commit"),
            mock.patch.object(P10, "_assert_current_preprobe_blobs"),
        )
        with lifecycle_patches[0], lifecycle_patches[1]:
            self.assertEqual(P10.validate_report(report), report)
            mutations = []
            positive = copy.deepcopy(report)
            positive["assessment"]["outcome_classification"] = (
                "ADMISSION_BOUND_ESTABLISHED_STRICTLY_BELOW_FIXED_CAP"
            )
            mutations.append(positive)
            peak = copy.deepcopy(report)
            peak["assessment"]["byte_envelope"]["exact_static_peak_bytes"] = (
                P10.FIXED_CAP_BYTES - 1
            )
            peak["assessment"]["byte_envelope"][
                "strict_integer_peak_less_than_cap"
            ] = True
            mutations.append(peak)
            equal_cap = copy.deepcopy(report)
            equal_cap["assessment"]["byte_envelope"]["exact_static_peak_bytes"] = (
                P10.FIXED_CAP_BYTES
            )
            equal_cap["assessment"]["byte_envelope"][
                "strict_integer_peak_less_than_cap"
            ] = True
            mutations.append(equal_cap)
            authority = copy.deepcopy(report)
            authority["authority"]["execution_authority"] = True
            mutations.append(authority)
            no_go = copy.deepcopy(report)
            no_go["assessment"]["byte_envelope"]["resource_no_go_inference"] = True
            mutations.append(no_go)
            obligation = copy.deepcopy(report)
            obligation["assessment"]["proof_obligations"]["rows"][0][
                "current_status"
            ] = "VERIFIED"
            mutations.append(obligation)
            for mutated in mutations:
                with self.subTest(mutated=mutated), self.assertRaises(P10.ProofError):
                    P10.validate_report(mutated)

    def test_fixture_policy_and_source_pin_mutations_fail_closed(self) -> None:
        mutated_fixture = copy.deepcopy(self.fixture)
        mutated_fixture["fixed_cap_contract"]["fixed_process_cap_bytes"] += 1
        with self.assertRaisesRegex(P10.ProofError, "canonical hash drift"):
            P10._validate_fixture(mutated_fixture)
        mutated_fixture = copy.deepcopy(self.fixture)
        del mutated_fixture["live_set_component_model"]["finalizer_components"]
        with self.assertRaisesRegex(P10.ProofError, "canonical hash drift"):
            P10._validate_fixture(mutated_fixture)
        mutated_policy = copy.deepcopy(self.policy)
        mutated_policy["fixed_cap_decision_rule"][
            "positive_branch_requires_peak_strictly_less_than_fixed_cap"
        ] = False
        with self.assertRaisesRegex(P10.ProofError, "semantic drift"):
            P10._validate_policy(mutated_policy)
        mutated_policy = copy.deepcopy(self.policy)
        mutated_policy["source_files"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(P10.ProofError, "source pin drift"):
            P10._validate_policy(mutated_policy)

    def test_strict_json_rejects_duplicates_nonfinite_and_noncanonical_report(self) -> None:
        with self.assertRaisesRegex(P10.ProofError, "duplicate JSON key"):
            P10.loads_json(b'{"a":1,"a":2}', "duplicate")
        for raw in (b'{"a":NaN}', b'{"a":Infinity}', b'{"a":-Infinity}'):
            with self.subTest(raw=raw), self.assertRaisesRegex(
                P10.ProofError, "non-finite JSON constant"
            ):
                P10.loads_json(raw, "nonfinite")
        with self.assertRaisesRegex(P10.ProofError, "UTF-8 BOM"):
            P10.loads_json(b"\xef\xbb\xbf{}", "bom")
        report_path = BASE / P10.REPORT_NAME
        if report_path.exists():
            report = P10.validate_report()
            self.assertEqual(report_path.read_bytes(), P10.canonical_bytes(report))

    def test_git_status_diff_and_parent_parsers_fail_closed(self) -> None:
        path = P10.PREPROBE_CHANGED_PATHS[0]
        with mock.patch.object(P10, "_git_bytes", return_value=f"A  {path}\0".encode()):
            self.assertEqual(P10._status_records(), (("A ", path),))
        with mock.patch.object(P10, "_git_bytes", return_value=f"AM {path}\0".encode()):
            self.assertEqual(P10._status_records(), (("AM", path),))
        with mock.patch.object(P10, "_git_bytes", return_value=f"R  {path}\0".encode()):
            with self.assertRaisesRegex(P10.ProofError, "renames and copies"):
                P10._status_records()
        with mock.patch.object(P10, "_git_bytes", return_value=f"A\0{path}\0".encode()):
            self.assertEqual(P10._commit_added_paths("a" * 40), (path,))
        with mock.patch.object(P10, "_git_bytes", return_value=f"M\0{path}\0".encode()):
            with self.assertRaisesRegex(P10.ProofError, "additions only"):
                P10._commit_added_paths("a" * 40)
        with mock.patch.object(
            P10, "_git", return_value=f"{'a' * 40} {'b' * 40} {'c' * 40}\n"
        ):
            with self.assertRaisesRegex(P10.ProofError, "exactly one parent"):
                P10._commit_parent("a" * 40)

    def test_result_time_rebinds_every_preprobe_blob(self) -> None:
        self.assertEqual(P10.PREPROBE_BLOB_NAMES, (
            P10.FIXTURE_NAME,
            P10.POLICY_NAME,
            P10.MODULE_NAME,
            P10.TEST_NAME,
        ))
        with mock.patch.object(P10, "_read_regular", return_value=b"current"), mock.patch.object(
            P10, "_git_bytes", return_value=b"frozen"
        ):
            with self.assertRaisesRegex(P10.ProofError, "preprobe blob drift"):
                P10._assert_current_preprobe_blobs("a" * 40)
        with mock.patch.object(P10, "_read_regular", return_value=b"same") as read, mock.patch.object(
            P10, "_git_bytes", return_value=b"same"
        ) as show:
            P10._assert_current_preprobe_blobs("a" * 40)
        self.assertEqual(read.call_count, 4)
        self.assertEqual(show.call_count, 4)
        self.assertIn(
            "_assert_current_preprobe_blobs(preprobe_commit)",
            inspect.getsource(P10.assess),
        )
        self.assertIn(
            "_assert_current_preprobe_blobs(preprobe_commit)",
            inspect.getsource(P10.validate_report),
        )
        self.assertIn(
            "_assert_current_preprobe_blobs(preprobe_commit)",
            inspect.getsource(P10.verify_result),
        )

    def test_module_has_no_candidate_execution_or_raw_D4_input_path(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        subprocess_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ]
        self.assertEqual(len(subprocess_calls), 3)
        for call in subprocess_calls:
            self.assertEqual(call.func.attr, "run")
            command = call.args[0]
            self.assertIsInstance(command, ast.Tuple)
            self.assertIsInstance(command.elts[0], ast.Constant)
            self.assertEqual(command.elts[0].value, "git")
        forbidden_calls = {"system", "popen", "spawnl", "spawnv", "execv", "execl"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr.lower(), forbidden_calls)
        self.assertNotIn("majorana_certificate_p9_d4_", source)
        self.assertFalse(
            any("majorana_certificate_p9_d4_" in path for path in P10.SOURCE_PATHS)
        )
        self.assertNotIn("eval(", source)

    def test_report_presence_check_is_stage_aware(self) -> None:
        report = BASE / P10.REPORT_NAME
        if report.exists():
            validated = P10.validate_report()
            self.assertEqual(validated["status"], P10.REPORT_STATUS)
        else:
            self.assertFalse(report.is_symlink())


if __name__ == "__main__":
    unittest.main()
