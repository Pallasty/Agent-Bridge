#!/usr/bin/env python3
"""Static adversarial tests for the nonexecuting P10-G1 governance closure."""

from __future__ import annotations

import ast
import copy
import importlib.util
import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
MODULE_PATH = BASE / "majorana_certificate_p10_g1_post_assessment_governance_validator.py"
SPEC = importlib.util.spec_from_file_location("majorana_p10_g1_governance", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
G1 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = G1
SPEC.loader.exec_module(G1)


def nested_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from nested_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_keys(child)


class MajoranaP10G1GovernanceTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.contract_raw = G1.load_json(BASE / G1.CONTRACT_NAME, "contract")
        cls.contract = G1.validate_contract(cls.contract)
        cls.p10_report = G1._validate_p10_topology(cls.contract)
        cls.projection = G1._project_p10_report(cls.p10_report, cls.contract)
        cls.record, cls.record_raw = G1.load_json(BASE / G1.RECORD_NAME, "record", require_canonical=True)
        G1.validate_record(cls.record, cls.contract, cls.contract_raw, cls.projection)

    def test_content_closure_and_canonical_record(self) -> None:
        result = G1.validate_content()
        self.assertEqual(result["disposition"], G1.DISPOSITION)
        self.assertEqual(result["next_gate"], G1.NEXT_GATE)
        self.assertEqual(result["status"], "VERIFIED_P10_G1_POST_ASSESSMENT_GOVERNANCE_CONTENT")
        self.assertEqual(self.record_raw, G1.canonical_bytes(self.record))

    def test_p10_b0_b1_topology_report_and_source_blobs_are_closed(self) -> None:
        self.assertEqual(G1._commit_parent(G1.P10_B0), G1.G0)
        self.assertEqual(G1._commit_parent(G1.DIRECT_PARENT), G1.P10_B0)
        self.assertEqual(set(G1._changed_paths(G1.P10_B0)), G1.P10_B0_PATHS)
        self.assertEqual(G1._changed_paths(G1.DIRECT_PARENT), {G1.P10_REPORT_PATH: "A"})
        G1._validate_p10_topology(self.contract)
        with mock.patch.object(G1, "_git_blob", return_value=b"wrong"):
            with self.assertRaises(G1.GovernanceError):
                G1._validate_p10_topology(self.contract)

    def test_projection_is_minimal_and_excludes_host_or_d4_data(self) -> None:
        forbidden = {
            "phase_events", "markers", "RSS", "memory", "time", "stderr", "stdout",
            "returncode", "host_failure", "selected_source_anchor_custody", "known_static_facts",
        }
        self.assertFalse(forbidden & set(nested_keys(self.projection)))
        self.assertEqual(self.projection["outcome_classification"], "ASSESSED_NOT_ESTABLISHED")
        self.assertIsNone(self.projection["exact_static_peak_bytes"])
        self.assertFalse(self.projection["resource_no_go_inference"])
        self.assertEqual(self.projection["execution_gate"], "CLOSED")

    def test_contract_and_record_mutations_fail_closed(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["decision_rules"]["P10_G1_must_not_relax_the_fixed_2147483648_byte_cap"] = False
        with self.assertRaisesRegex(G1.GovernanceError, "semantic drift"):
            G1.validate_contract(contract)
        for key in (
            "execution_authority", "candidate_selection_authority", "candidate_or_cap_change_authority",
            "resource_or_no_go_authority", "S0_authority", "certificate_eligible", "result_contract_eligible",
        ):
            record = copy.deepcopy(self.record)
            record[key] = True
            with self.subTest(key=key), self.assertRaisesRegex(G1.GovernanceError, "reconstruction drift"):
                G1.validate_record(record, self.contract, self.contract_raw, self.projection)
        for field, value in (
            ("P10_B_candidate_execution_allowed", True),
            ("P10_B_Julia_execution_allowed", True),
            ("P10_B_resource_no_go_allowed", True),
            ("P10_B_gate", "D5"),
        ):
            record = copy.deepcopy(self.record)
            record["next_gate"][field] = value
            with self.subTest(field=field), self.assertRaises(G1.GovernanceError):
                G1.validate_record(record, self.contract, self.contract_raw, self.projection)

    def test_negative_assessment_cannot_be_rewritten_as_admission_or_no_go(self) -> None:
        for field, value in (
            ("outcome_classification", "ADMISSION_BOUND_ESTABLISHED_STRICTLY_BELOW_FIXED_CAP"),
            ("exact_static_peak_bytes", G1.FIXED_CAP_BYTES if hasattr(G1, "FIXED_CAP_BYTES") else 2147483648),
            ("resource_no_go_inference", True),
            ("execution_gate", "OPEN"),
        ):
            projection = copy.deepcopy(self.projection)
            projection[field] = value
            with self.subTest(field=field), self.assertRaises(G1.GovernanceError):
                G1.validate_record(self.record, self.contract, self.contract_raw, projection)
        record = copy.deepcopy(self.record)
        record["proof_obligation_ledger"]["obligations"][0]["status"] = "VERIFIED"
        with self.assertRaises(G1.GovernanceError):
            G1.validate_record(record, self.contract, self.contract_raw, self.projection)

    def test_strict_json_rejects_duplicate_nonfinite_and_noncanonical_record(self) -> None:
        with self.assertRaisesRegex(G1.GovernanceError, "duplicate JSON key"):
            G1.loads_strict(b'{"x":1,"x":2}', "duplicate")
        with self.assertRaisesRegex(G1.GovernanceError, "non-finite"):
            G1.loads_strict(b'{"x":NaN}', "nonfinite")
        pretty = json.dumps(self.record, indent=2, sort_keys=True).encode("ascii") + b"\n"
        self.assertNotEqual(pretty, G1.canonical_bytes(self.record))

    def test_staged_and_committed_lifecycle_require_exact_path_set(self) -> None:
        staged = "".join(f"{status}\t{path}\n" for path, status in G1.G1_CHANGED_PATHS.items())

        def good_git(*args):
            if args == ("rev-parse", "HEAD"):
                return G1.DIRECT_PARENT + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return staged
            if args in (("diff", "--name-only"), ("ls-files", "--others", "--exclude-standard")):
                return ""
            raise AssertionError(args)

        with mock.patch.object(G1, "_git", side_effect=good_git):
            self.assertEqual(G1.validate_lifecycle(), "STAGED_DIRECT_CHILD")
        bad = staged + "A\tdocs/research/fermion-frontier/forbidden.json\n"

        def bad_git(*args):
            if args == ("rev-parse", "HEAD"):
                return G1.DIRECT_PARENT + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return bad
            return ""

        with mock.patch.object(G1, "_git", side_effect=bad_git):
            with self.assertRaisesRegex(G1.GovernanceError, "changed-path set"):
                G1.validate_lifecycle()

    def test_validator_is_read_only_git_only_and_does_not_import_p10a_or_d4(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"]
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual(call.func.attr, "run")
            command = call.args[0]
            self.assertIsInstance(command, ast.Tuple)
            self.assertEqual(command.elts[0].value, "git")
        self.assertNotIn("majorana_certificate_p10a_static_resource_envelope import", source)
        self.assertNotIn("majorana_certificate_p9_d4_", source)
        self.assertNotIn("systemd-run", source)
        self.assertNotIn("eval(", source)
        self.assertIn("_validate_p10_topology", inspect.getsource(G1.validate_content))


if __name__ == "__main__":
    unittest.main()
