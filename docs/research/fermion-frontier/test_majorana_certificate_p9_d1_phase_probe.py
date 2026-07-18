#!/usr/bin/env python3
"""Tests for the P9-D1 coarse phase-only diagnostic contract."""

from __future__ import annotations

import ast
import importlib.util
import inspect
import unittest
from pathlib import Path
from types import SimpleNamespace


BASE = Path(__file__).resolve().parent
MODULE_PATH = BASE / "majorana_certificate_p9_d1_phase_probe.py"
SPEC = importlib.util.spec_from_file_location("majorana_p9_d1_phase", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load P9-D1 module")
D1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D1)


class MajoranaP9D1CoarsePhaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = D1.load_json(BASE / D1.FIXTURE_NAME)

    def _collector(self, events: list[str]) -> SimpleNamespace:
        lines = [
            D1.canonical_bytes({"event": event, "sequence": index}) + b"\n"
            for index, event in enumerate(events)
        ]
        return SimpleNamespace(
            overflow=False, partial=False, failure=False, lines=lines, eof=True,
        )

    def test_fixture_binds_the_only_coarse_parent_projection(self) -> None:
        fixture = D1._validate_fixture(self.fixture)
        self.assertEqual(fixture["scientific_authority"], "NONE")
        self.assertFalse(fixture["certificate_eligible"])
        self.assertFalse(fixture["result_contract_eligible"])
        _driver, _p9_fixture, projection = D1._target_p9_b1_projection()
        self.assertEqual(projection, D1.P9_B1_ALLOWED_PROJECTION)
        self.assertIn(D1.RUNTIME_LOCK_NAME, D1.SOURCE_PATHS)
        D1._validate_runtime_lock_bytes(fixture["runtime_custody"])

    def test_static_clone_is_exactly_forward_and_reverse_derived(self) -> None:
        relation = D1._validate_static_clone(self.fixture)
        self.assertTrue(relation["forward_byte_construction_matches"])
        self.assertTrue(relation["reverse_deletion_matches_frozen_P9"])
        self.assertEqual(relation["exact_marker_insertion_block_count"], 8)
        self.assertTrue(relation["marker_blocks_contain_no_forbidden_live_state_tokens"])

    def test_both_complete_phase_languages_are_accepted(self) -> None:
        for branch, sequence in D1.TERMINALS.items():
            events, terminal = D1._validate_phase_trace(
                self._collector(sequence), self.fixture,
            )
            self.assertEqual(terminal, branch)
            self.assertEqual([row["event"] for row in events], sequence)

    def test_interrupted_trace_must_be_a_legal_prefix(self) -> None:
        events, terminal = D1._validate_phase_trace(
            self._collector(D1.TERMINALS["STEP3_RETURNED"][:7]), self.fixture,
        )
        self.assertIsNone(terminal)
        self.assertEqual(len(events), 7)
        with self.assertRaises(D1.ProbeError):
            D1._validate_phase_trace(
                self._collector([
                    "D1_RUNNER_STARTED",
                    "STEP3_ENGINE_STARTED",
                ]),
                self.fixture,
            )

    def test_phase_only_observation_excludes_measurements_and_witnesses(self) -> None:
        full = D1.TERMINALS["STEP3_RETURNED"]
        observation = {
            "status": "COMPLETED_PHASE_DIAGNOSTIC",
            "diagnostic_terminal_branch": "STEP3_RETURNED",
            "phase_trace_status": "COMPLETE_TERMINAL_SEQUENCE",
            "phase_events": [
                {"sequence": index, "event": event}
                for index, event in enumerate(full)
            ],
            "phase_event_count": len(full),
            "phase_trace_protocol_sha256": D1.canonical_sha256([
                {"sequence": index, "event": event}
                for index, event in enumerate(full)
            ]),
            "last_phase_event": "D1_DIAGNOSTIC_COMPLETED",
            "outer_timeout_triggered": False,
            "host_failure_observed": False,
            "resource_witness": None,
            "host_failure_has_no_mathematical_authority": True,
        }
        D1._validate_observation(observation, self.fixture)
        forbidden = {
            "outer_monotonic_elapsed_ns", "stderr_bytes", "stdout_bytes",
            "time_diagnostics", "maximum_resident_set_size", "resource_witness_sha256",
        }
        self.assertTrue(forbidden.isdisjoint(observation))

    def test_outer_parent_projection_function_has_no_timing_or_stderr_access(self) -> None:
        source = inspect.getsource(D1._target_p9_b1_projection)
        for forbidden in (
            "stderr", "stdout", "returncode", "elapsed", "time_diagnostics",
            "maximum_resident", "rss",
        ):
            self.assertNotIn(forbidden, source)

    def test_no_runtime_source_or_ast_transform_route_exists(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        self.assertFalse(any("majorana_certificate_p9_bit_order_resource_probe" in item for item in imports))
        self.assertNotIn("runpy", source)
        self.assertNotIn("exec(", source)
        self.assertNotIn("eval(", source)
        self.assertNotIn("ast.parse(", inspect.getsource(D1._build_expected_clone))

    def test_frozen_preprobe_or_report_is_verifiable_after_commit(self) -> None:
        report_path = BASE / D1.REPORT_NAME
        head = D1._git_text("rev-parse", "HEAD").strip()
        if report_path.exists():
            report = D1.verify_report(report_path)
            self.assertEqual(report["report_type"], D1.REPORT_TYPE)
            self.assertEqual(D1.RESULT_CHANGED_PATHS, (D1.ROOT + D1.REPORT_NAME,))
        elif head != D1.P9_RESULT_COMMIT:
            receipt = D1.verify_preprobe()
            self.assertEqual(receipt["status"], "VERIFIED_P9_D1_COARSE_PHASE_PREPROBE")
        else:
            self.skipTest("P9-D1 B0 is not yet committed")


if __name__ == "__main__":
    unittest.main()
