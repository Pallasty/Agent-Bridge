#!/usr/bin/env python3
"""Static and adversarial tests for the P9 post-D4 G0 closure."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


sys.dont_write_bytecode = True

BASE = Path(__file__).resolve().parent
MODULE_PATH = BASE / "majorana_certificate_p9_g0_post_d4_governance_closure_validator.py"
SPEC = importlib.util.spec_from_file_location("majorana_p9_g0_governance", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
G0 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = G0
SPEC.loader.exec_module(G0)


def nested_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from nested_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_keys(child)


class P9G0GovernanceClosureTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.contract_raw = G0.load_json(BASE / G0.CONTRACT_NAME, "G0 contract")
        cls.contract = G0.validate_contract(cls.contract)
        cls.report, cls.names, cls.projection = G0.validate_d4_evidence(cls.contract)
        cls.record, cls.record_raw = G0.load_json(
            BASE / G0.RECORD_NAME, "G0 record", require_canonical=True,
        )
        G0.validate_record(
            cls.record, cls.contract, cls.contract_raw, cls.report, cls.names,
        )

    def test_positive_content_closure(self) -> None:
        result = G0.validate_content()
        self.assertEqual(result["disposition"], G0.DISPOSITION)
        self.assertEqual(result["matched_target_count"], 0)
        self.assertEqual(
            result["status"],
            "VERIFIED_P9_G0_POST_D4_GOVERNANCE_CLOSURE_CONTENT",
        )
        self.assertEqual(self.record_raw, G0.canonical_bytes(self.record))
        self.assertNotEqual(self.contract_raw, G0.canonical_payload(self.contract))

    def test_strict_json_rejects_duplicates_nonfinite_and_noncanonical_record(self) -> None:
        with self.assertRaisesRegex(G0.GovernanceError, "duplicate JSON key"):
            G0.loads_strict(b'{"x":1,"x":2}', "duplicate fixture")
        with self.assertRaisesRegex(G0.GovernanceError, "non-finite"):
            G0.loads_strict(b'{"x":NaN}', "nonfinite fixture")
        pretty = json.dumps(self.record, indent=2, sort_keys=True).encode("ascii") + b"\n"
        self.assertNotEqual(pretty, G0.canonical_bytes(self.record))

    def test_d4_b0_b1_topology_and_all_source_pins_are_closed(self) -> None:
        G0._validate_d4_topology_and_sources(self.contract)
        pins = self.contract["d4_result_custody"]["preprobe_source_pins"]
        self.assertEqual(tuple(pins), G0.D4_SOURCE_PINS)
        self.assertEqual(G0._commit_parent(G0.D4_B0), G0.D3_B1)
        self.assertEqual(G0._commit_parent(G0.D4_B1), G0.D4_B0)
        self.assertEqual(G0._changed_paths(G0.D4_B1), {G0.D4_REPORT_REPO_PATH: "A"})
        with mock.patch.object(G0, "_git_bytes", return_value=b"wrong"), self.assertRaisesRegex(
            G0.GovernanceError, "differs from B0"
        ):
            G0._validate_d4_topology_and_sources(self.contract)

    def test_minimal_projection_excludes_host_diagnostics_and_event_payload(self) -> None:
        forbidden = {
            "outer_monotonic_elapsed_ns", "outer_timeout_triggered", "process_returncode",
            "stdout", "stdout_bytes", "stdout_sha256", "stderr", "stderr_bytes",
            "stderr_sha256", "RSS", "memory", "time_diagnostics", "host_failure_observed",
            "phase_events", "phase_trace_protocol_sha256",
        }
        self.assertFalse(forbidden & set(nested_keys(self.record["D4_minimal_governance_projection"])))
        self.assertFalse(
            forbidden
            & set(nested_keys(self.contract["allowed_D4_governance_projection"]))
        )
        mutated = copy.deepcopy(self.contract)
        mutated["allowed_D4_governance_projection"]["observation"]["outer_timeout_triggered"] = False
        with self.assertRaisesRegex(G0.GovernanceError, "forbidden host diagnostic"):
            G0.validate_contract(mutated)

    def test_actual_same_trace_predicates_match_nothing(self) -> None:
        evaluations = G0.evaluate_review_targets(
            self.names, self.report["observation"]["phase_trace_status"],
        )
        self.assertEqual([row["matched"] for row in evaluations], [False] * 4)
        self.assertEqual(self.record["matched_targets"], [])
        self.assertEqual(self.record["disposition"], G0.DISPOSITION)

    def test_cross_run_D3_ALPHA_splice_is_rejected(self) -> None:
        spliced_names = [*self.names, "STEP3_SEGMENT_D_SUBGRID_ALPHA_REACHED"]
        with self.assertRaisesRegex(G0.GovernanceError, "validated D4 B1"):
            G0.evaluate_review_targets(spliced_names, "LEGAL_PREFIX_INTERRUPTED")
        with self.assertRaisesRegex(G0.GovernanceError, "minimal projection|validated D4 B1"):
            G0.validate_record(
                self.record, self.contract, self.contract_raw, self.report, spliced_names,
            )

    def test_fabricated_review_target_and_authority_are_rejected(self) -> None:
        fabricated = copy.deepcopy(self.record)
        fabricated["matched_targets"] = ["SEGMENT_D_COMPOSITE_KAPPA_STATIC_INTERVAL"]
        fabricated["matched_target_count"] = 1
        with self.assertRaisesRegex(G0.GovernanceError, "matched-target"):
            G0.validate_record(
                fabricated, self.contract, self.contract_raw, self.report, self.names,
            )
        for key in (
            "execution_authority", "candidate_selection_authority",
            "candidate_or_cap_change_authority", "resource_or_no_go_authority",
            "S0_authority", "certificate_eligible",
            "result_contract_eligible",
        ):
            mutated = copy.deepcopy(self.record)
            mutated[key] = True
            with self.subTest(key=key), self.assertRaisesRegex(
                G0.GovernanceError, "scalar drift"
            ):
                G0.validate_record(
                    mutated, self.contract, self.contract_raw, self.report, self.names,
                )

    def test_missing_or_reordered_proof_obligations_fail_closed(self) -> None:
        mutated = copy.deepcopy(self.contract)
        mutated["proof_obligation_ledger"]["obligations"].pop()
        with self.assertRaisesRegex(G0.GovernanceError, "proof_obligation_ledger"):
            G0.validate_contract(mutated)
        record = copy.deepcopy(self.record)
        record["proof_obligation_ledger"]["obligations"].reverse()
        with self.assertRaisesRegex(G0.GovernanceError, "proof-obligation"):
            G0.validate_record(
                record, self.contract, self.contract_raw, self.report, self.names,
            )

    def test_coordinated_contract_and_receipt_mutation_still_fails(self) -> None:
        mutated_contract = copy.deepcopy(self.contract)
        mutated_contract["decision_rules"]["complete_invalid_or_outside_target_D4_traces_create_no_review_target"] = False
        mutated_record = copy.deepcopy(self.record)
        mutated_raw = G0.canonical_bytes(mutated_contract)
        mutated_record["contract_receipt"].update({
            "size_bytes": len(mutated_raw),
            "raw_sha256": G0._sha256(mutated_raw),
            "canonical_sha256": G0.canonical_sha256(mutated_contract),
        })
        with self.assertRaisesRegex(G0.GovernanceError, "semantic section drift"):
            G0.validate_contract(mutated_contract)

    def test_next_gate_is_proof_only_and_not_D5_or_execution(self) -> None:
        gate = self.record["next_gate"]
        self.assertEqual(gate["status"], "PROOF_ONLY_DESIGN_PROPOSAL_REQUIRED")
        self.assertEqual(gate["allowed_proposal"], G0.NEXT_GATE_ID)
        self.assertFalse(gate["execution_authorized"])
        self.assertFalse(gate["D5_authorized"])
        self.assertFalse(gate["candidate_or_cap_change_authorized"])
        self.assertTrue(gate["all_seven_obligations_positive_required_before_future_execution_governance"])
        self.assertTrue(gate["static_resource_envelope_established_required_before_future_execution_governance"])
        self.assertTrue(gate["peak_bound_strictly_below_2147483648_bytes_required_before_future_execution_governance"])
        self.assertTrue(gate["ASSESSED_NOT_ESTABLISHED_keeps_execution_closed"])
        self.assertEqual(self.record["proof_obligation_ledger"]["admission_status"], "NOT_ESTABLISHED")
        self.assertEqual(self.record["scientific_authority"], "NONE")
        self.assertFalse(self.record["S0_admission"]["derived_from_D4"])

    def test_staged_six_path_gate_accepts_only_the_exact_set(self) -> None:
        staged_text = "".join(
            f"{status}\t{path}\n" for path, status in G0.G0_STAGED_STATUS.items()
        )

        def good_git(*args):
            if args == ("rev-parse", "HEAD"):
                return G0.D4_B1 + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return staged_text
            if args in (("diff", "--name-only"), ("ls-files", "--others", "--exclude-standard")):
                return ""
            raise AssertionError(args)

        with mock.patch.object(G0, "_git", side_effect=good_git):
            self.assertEqual(G0.validate_lifecycle(), "STAGED_DIRECT_CHILD")

        bad_text = staged_text + "A\tdocs/research/fermion-frontier/forbidden.json\n"

        def bad_git(*args):
            if args == ("rev-parse", "HEAD"):
                return G0.D4_B1 + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return bad_text
            return ""

        with mock.patch.object(G0, "_git", side_effect=bad_git), self.assertRaisesRegex(
            G0.GovernanceError, "changed-path set"
        ):
            G0.validate_lifecycle()

        deleted_text = staged_text + "D\tdocs/research/fermion-frontier/README.md\n"

        def deleted_git(*args):
            if args == ("rev-parse", "HEAD"):
                return G0.D4_B1 + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return deleted_text
            return ""

        with mock.patch.object(G0, "_git", side_effect=deleted_git), self.assertRaisesRegex(
            G0.GovernanceError, "invalid Git name-status"
        ):
            G0.validate_lifecycle()

    def test_committed_gate_requires_direct_parent_exact_paths_and_clean_blobs(self) -> None:
        head = "a" * 40

        def fake_git(*args):
            if args == ("rev-parse", "HEAD"):
                return head + "\n"
            if args == ("status", "--porcelain=v1"):
                return ""
            raise AssertionError(args)

        with mock.patch.object(G0, "_git", side_effect=fake_git), mock.patch.object(
            G0, "_commit_parent", return_value=G0.D4_B1,
        ), mock.patch.object(
            G0, "_changed_paths", return_value=G0.G0_STAGED_STATUS,
        ), mock.patch.object(
            G0, "_read_regular", return_value=b"same",
        ), mock.patch.object(
            G0, "_git_bytes", return_value=b"same",
        ):
            self.assertEqual(G0.validate_lifecycle(), "COMMITTED_DIRECT_CHILD")

        cases = (
            ("bad_parent", "b" * 40, G0.G0_STAGED_STATUS, "", b"same", b"same", "direct child"),
            ("extra_path", G0.D4_B1, {**G0.G0_STAGED_STATUS, "forbidden": "A"}, "", b"same", b"same", "changed-path"),
            ("dirty", G0.D4_B1, G0.G0_STAGED_STATUS, " M dirty\n", b"same", b"same", "clean"),
            ("blob", G0.D4_B1, G0.G0_STAGED_STATUS, "", b"current", b"frozen", "blob drift"),
        )
        for name, parent, paths, status_text, current, frozen, message in cases:
            def case_git(*args, _status=status_text):
                if args == ("rev-parse", "HEAD"):
                    return head + "\n"
                if args == ("status", "--porcelain=v1"):
                    return _status
                raise AssertionError(args)

            with self.subTest(name=name), mock.patch.object(
                G0, "_git", side_effect=case_git,
            ), mock.patch.object(
                G0, "_commit_parent", return_value=parent,
            ), mock.patch.object(
                G0, "_changed_paths", return_value=paths,
            ), mock.patch.object(
                G0, "_read_regular", return_value=current,
            ), mock.patch.object(
                G0, "_git_bytes", return_value=frozen,
            ), self.assertRaisesRegex(G0.GovernanceError, message):
                G0.validate_lifecycle()

    def test_validator_subprocesses_are_git_only_and_no_candidate_launcher_exists(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
                and node.func.attr == "run"
            ):
                calls.append(node)
        self.assertEqual(len(calls), 2)
        for call in calls:
            command = call.args[0]
            self.assertIsInstance(command, ast.List)
            first = command.elts[0]
            self.assertIsInstance(first, ast.Constant)
            self.assertEqual(first.value, "git")
        lowered = source.lower()
        forbidden_subprocess_attributes = {
            "popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput",
        }
        forbidden_os_prefixes = ("exec", "spawn")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = node.func.value
            if isinstance(owner, ast.Name) and owner.id == "subprocess":
                self.assertNotIn(node.func.attr, forbidden_subprocess_attributes)
            if isinstance(owner, ast.Name) and owner.id == "os":
                self.assertNotEqual(node.func.attr, "system")
                self.assertFalse(node.func.attr.startswith(forbidden_os_prefixes))
        self.assertNotIn("systemd-run", lowered)
        self.assertNotIn("--run", lowered)
        self.assertNotIn("execution_claim", lowered)


if __name__ == "__main__":
    unittest.main()
