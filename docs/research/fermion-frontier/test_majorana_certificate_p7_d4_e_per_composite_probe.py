#!/usr/bin/env python3
"""Preprobe tests for the non-authoritative Majorana P7 D4 diagnostic."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


sys.dont_write_bytecode = True
FROZEN_HASHLIB_SHA256 = hashlib.sha256

BASE = Path(__file__).resolve().parent
MODULE_PATH = BASE / "majorana_certificate_p7_d4_e_per_composite_probe.py"
SPEC = importlib.util.spec_from_file_location("majorana_p7_d4", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load P7 D4 E-per-composite-probe module")
D4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D4)


def collector_for(
    names: list[str], *, eof: bool = True, read_failure: bool = False,
) -> D4._PhaseCollector:
    protocol = D4.load_json(BASE / D4.FIXTURE_NAME)["phase_event_protocol"]
    collector = D4._PhaseCollector(
        -1, 0,
        max_line_bytes=protocol["maximum_line_bytes_including_newline"],
        max_total_bytes=protocol["maximum_total_channel_bytes"],
        max_events=protocol["maximum_event_count"],
    )
    raw = b""
    for sequence, event in enumerate(names):
        line = D4.canonical_bytes({"event": event, "sequence": sequence}) + b"\n"
        raw += line
        collector.lines.append((line, 100 + sequence))
    collector.total_bytes = len(raw)
    collector.digest.update(raw)
    collector.eof = eof
    collector.read_failure = read_failure
    return collector


def complete_time_stderr() -> bytes:
    return b"\n".join((
        b"User time (seconds): 1.00",
        b"System time (seconds): 0.10",
        b"Elapsed (wall clock) time (h:mm:ss or m:ss): 0:01.10",
        b"Maximum resident set size (kbytes): 1234",
        b"Minor (reclaiming a frame) page faults: 3",
        b"Major (requiring I/O) page faults: 0",
        b"",
    ))


def stream_fields(stdout: bytes = b"", stderr: bytes = b"") -> dict[str, object]:
    return {
        "stdout_bytes": len(stdout),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_bytes": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stderr_for_time": stderr,
    }


class P7D4EPerCompositePreprobeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = D4.load_json(BASE / D4.FIXTURE_NAME)
        cls.policy = D4.load_json(BASE / D4.POLICY_NAME)

    def test_fixture_protocol_and_static_marker_map_are_exact(self) -> None:
        fixture = D4._validate_fixture(self.fixture)
        self.assertEqual(
            D4.canonical_sha256(fixture), D4.FIXTURE_CANONICAL_SHA256,
        )
        protocol = fixture["phase_event_protocol"]
        self.assertEqual(
            D4.canonical_sha256(protocol), D4.PHASE_PROTOCOL_CANONICAL_SHA256,
        )
        self.assertEqual(len(protocol["allowed_events"]), 65)
        self.assertEqual(len(protocol["step3_internal_event_sequence"]), 40)
        self.assertEqual(len(protocol["full_success_sequence"]), 61)
        self.assertEqual(protocol["maximum_event_count"], 61)
        self.assertEqual(protocol["maximum_successful_trace_event_count"], 61)
        self.assertEqual(protocol["maximum_total_channel_bytes"], 8192)
        grammar = protocol["parameterized_step3_deterministic_cap_terminal"]
        self.assertEqual(
            grammar["allowed_internal_prefix_event_counts"],
            list(D4.STEP3_CAP_INTERNAL_PREFIX_EVENT_COUNTS),
        )
        self.assertEqual(
            grammar[
                "forbidden_segment_returned_prefix_event_counts_without_next_segment_started"
            ],
            list(D4.UNREACHABLE_SEGMENT_RETURNED_CAP_PREFIX_COUNTS),
        )
        self.assertEqual(
            grammar["exact_reachable_internal_prefix_event_count_cardinality"],
            32,
        )
        self.assertEqual(
            D4.UNREACHABLE_SEGMENT_RETURNED_CAP_PREFIX_COUNTS,
            (4, 8, 12, 16, 24, 28, 32, 36),
        )
        self.assertIn(40, D4.STEP3_CAP_INTERNAL_PREFIX_EVENT_COUNTS)
        marker = fixture["step3_schedule_marker_map"]
        segments = marker["segments"]
        self.assertEqual(marker["segment_order"], list("ABCDEFGHI"))
        self.assertEqual([row["frozen_group"] for row in segments], [
            "H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1",
        ])
        counts = [row["frozen_composite_count"] for row in segments]
        self.assertEqual(counts, [64, 48, 64, 48, 64, 48, 64, 48, 64])
        self.assertEqual(sum(counts), 512)
        self.assertEqual(
            [row["checkpoint_1_completed_composites"] for row in segments],
            [22, 16, 22, 16, 22, 16, 22, 16, 22],
        )
        self.assertEqual(
            [row["checkpoint_2_completed_composites"] for row in segments],
            [43, 32, 43, 32, 43, 32, 43, 32, 43],
        )
        segment_e = segments[4]
        self.assertEqual(
            segment_e["D4_per_composite_completed_composite_ordinals"],
            list(D4.E_PER_COMPOSITE_ORDINALS),
        )
        self.assertEqual(marker["E_per_composite_marker_map"], [
            {
                "completed_composite_ordinal": ordinal,
                "event": f"STEP3_SEGMENT_E_COMPOSITE_{ordinal}_REACHED",
            }
            for ordinal in D4.E_PER_COMPOSITE_ORDINALS
        ])
        self.assertTrue(
            marker["per_composite_resolution_is_limited_to_E_ordinals_23_through_26"]
        )
        self.assertTrue(
            marker["post_26_progress_until_checkpoint_2_remains_checkpoint_granularity"]
        )
        for reachable_after_E_CP1 in (19, 20, 21, 22, 23, 25, 40):
            self.assertIn(
                reachable_after_E_CP1,
                D4.STEP3_CAP_INTERNAL_PREFIX_EVENT_COUNTS,
            )

    def test_policy_semantics_sources_and_staging_are_frozen(self) -> None:
        policy = D4.validate_policy(self.policy, require_report_absent=True)
        semantic = {
            key: value for key, value in policy.items() if key != "source_files"
        }
        self.assertEqual(
            D4.canonical_sha256(semantic), D4.POLICY_SEMANTIC_SHA256,
        )
        self.assertEqual(policy["source_file_pins_status"], "FROZEN_EXACT")
        self.assertEqual(policy["exact_source_file_count"], 28)
        pins = D4._source_pins(policy)
        self.assertEqual(set(pins), set(D4.SOURCE_PATHS))
        self.assertEqual(len(pins), 28)
        self.assertEqual(len(D4.STAGED_PATHS), 15)
        self.assertEqual(tuple(D4.STAGED_PATHS[:13]), tuple(D4.D0.STAGED_PATHS))
        self.assertEqual(D4.STAGED_PATHS[-2:], (D4.FIXTURE_NAME, D4.PROBE_DRIVER))
        self.assertNotIn(D4.D3_REPORT_NAME, D4.STAGED_PATHS)
        self.assertNotIn(D4.D3_REPORT_NAME, D4.SOURCE_PATHS)
        self.assertEqual(
            policy["staged_source_custody"]["staged_path_order"],
            list(D4.STAGED_PATHS),
        )
        self.assertEqual(
            policy["static_schedule_marker_policy"][
                "segment_E_fixed_per_composite_completed_composite_ordinals"
            ],
            list(D4.E_PER_COMPOSITE_ORDINALS),
        )
        marker_policy = policy["static_schedule_marker_policy"]
        for conditional_key in (
            "per_composite_resolution_is_limited_to_the_D3_local_E_23_through_26_window",
            "a_terminal_prefix_within_E_ordinals_23_through_26_has_single_composite_marker_resolution",
            "a_trace_reaching_E_composite_26_then_continuing_toward_checkpoint_2_remains_coarse_after_26",
            "D4_does_not_assert_a_global_maximum_unresolved_window_of_one_composite_for_all_terminal_paths",
        ):
            self.assertTrue(marker_policy[conditional_key])

    def test_local_window_and_post_26_resolution_claims_fail_closed(self) -> None:
        policy_keys = (
            "per_composite_resolution_is_limited_to_the_D3_local_E_23_through_26_window",
            "a_terminal_prefix_within_E_ordinals_23_through_26_has_single_composite_marker_resolution",
            "a_trace_reaching_E_composite_26_then_continuing_toward_checkpoint_2_remains_coarse_after_26",
            "D4_does_not_assert_a_global_maximum_unresolved_window_of_one_composite_for_all_terminal_paths",
        )
        for key in policy_keys:
            mutated = copy.deepcopy(self.policy)
            mutated["static_schedule_marker_policy"][key] = False
            semantic = {
                name: value for name, value in mutated.items()
                if name != "source_files"
            }
            with self.subTest(policy_key=key), mock.patch.object(
                D4, "POLICY_SEMANTIC_SHA256", D4.canonical_sha256(semantic),
            ), self.assertRaises(D4.ProbeError):
                D4.validate_policy(mutated, require_report_absent=True)

        for section, key in (
            (
                "step3_schedule_marker_map",
                "per_composite_resolution_is_limited_to_E_ordinals_23_through_26",
            ),
            (
                "step3_schedule_marker_map",
                "post_26_progress_until_checkpoint_2_remains_checkpoint_granularity",
            ),
            (
                "observation_scope",
                "post_26_progress_until_checkpoint_2_remains_coarse_and_cannot_be_claimed_as_single_composite_resolution",
            ),
        ):
            mutated_fixture = copy.deepcopy(self.fixture)
            mutated_fixture[section][key] = False
            with self.subTest(fixture_key=key), mock.patch.object(
                D4, "FIXTURE_CANONICAL_SHA256",
                D4.canonical_sha256(mutated_fixture),
            ), self.assertRaises(D4.ProbeError):
                D4._validate_fixture(mutated_fixture)

    def test_D3_parent_firewall_uses_only_frozen_coarse_facts(self) -> None:
        custody = D4._validate_d3_parent(self.fixture)
        report_path = BASE / D4.D3_REPORT_NAME
        self.assertEqual(D4.file_sha256(report_path), D4.D3_REPORT_SHA256)
        self.assertEqual(report_path.stat().st_size, D4.D3_REPORT_SIZE_BYTES)
        self.assertIs(custody, self.fixture["D3_parent_custody"])
        self.assertEqual(custody["scientific_authority"], "NONE")
        self.assertTrue(custody["resource_witness_is_null"])
        firewall = self.policy["hindsight_firewall"]
        self.assertTrue(firewall["allowed_D3_result_facts_are_exhaustive"])
        self.assertEqual(firewall["allowed_D3_result_facts"], [
            "D3_report_identity_and_scientific_authority_NONE",
            "D3_trace_was_a_legal_interrupted_protocol_prefix",
            "D3_segments_A_through_D_returned",
            "D3_segment_E_started_and_checkpoint_1_reached",
            "D3_segment_E_subgrid_26_30_34_and_38_markers_were_absent",
            "D3_segment_E_checkpoint_2_and_returned_markers_were_absent",
            "D3_later_segment_step3_engine_return_and_step3_finalizer_markers_were_absent",
            "D3_resource_witness_is_null",
            "D3_future_S0_admission_is_not_established",
        ])
        for key in (
            "D3_parent_report_validator_must_not_be_called",
            "D3_parent_report_access_is_limited_to_the_exhaustive_allowed_coarse_facts",
            "D3_parent_report_object_must_not_be_returned_forwarded_or_enter_the_runner",
        ):
            self.assertTrue(firewall[key])
        for key in (
            "D3_parent_report_access_is_limited_to_the_exhaustive_allowed_coarse_facts",
            "D3_parent_report_object_must_not_be_returned_forwarded_or_enter_the_runner",
        ):
            self.assertTrue(self.fixture["observation_scope"][key])
        forbidden = " ".join(
            firewall["forbidden_D3_or_suppressed_inputs"]
        ).lower()
        for fragment in (
            "exact_times", "return_code", "stderr", "phase_channel",
            "event_count", "rss", "tick", "mask", "coefficient",
            "digest", "neel", "final_state",
        ):
            self.assertIn(fragment, forbidden)
        dependency = self.policy["frozen_D3_dependency"]
        self.assertEqual(dependency, self.fixture["D3_parent_custody"])
        self.assertEqual(set(dependency), {
            "result_commit_sha", "report_relative_path", "report_size_bytes",
            "report_sha256", "report_type", "scientific_authority",
            "certificate_eligible", "result_contract_eligible",
            "phase_trace_status",
            "segments_A_through_D_returned_markers_reached",
            "segment_E_started_marker_reached",
            "segment_E_checkpoint_1_marker_reached",
            "segment_E_subgrid_26_marker_reached",
            "segment_E_subgrid_30_marker_reached",
            "segment_E_subgrid_34_marker_reached",
            "segment_E_subgrid_38_marker_reached",
            "segment_E_checkpoint_2_marker_reached",
            "segment_E_returned_marker_reached", "later_segment_markers_reached",
            "step3_engine_returned_marker_reached",
            "step3_finalizer_started_marker_reached",
            "step3_finalizer_returned_marker_reached",
            "resource_witness_is_null", "future_S0_admission_status",
            "allowed_result_informed_facts_are_exhaustive",
        })
        self.assertFalse({
            "observation", "status", "diagnostic_terminal_branch",
            "process_returncode", "outer_monotonic_elapsed_ns",
            "stderr_bytes", "stderr_sha256", "phase_channel_bytes",
            "phase_channel_sha256", "phase_event_count", "time_diagnostics",
        } & set(dependency))

    def test_D3_parent_AST_callgraph_and_field_projection_are_closed(self) -> None:
        module_bytes = MODULE_PATH.read_bytes()
        self.assertEqual(len(module_bytes), 79560)
        self.assertEqual(
            hashlib.sha256(module_bytes).hexdigest(),
            "8e6da1351187e87766c9dae92d52bf52f57b7a8f9d6f3ceae952359fa7391d54",
        )
        module_source = MODULE_PATH.read_text(encoding="utf-8")
        module_tree = ast.parse(module_source)
        critical_bindings = {
            name: [] for name in (
                "D3", "D0", "D3_REPORT_NAME", "loads_json", "hashlib",
                "ProbeError",
                "_expected_d3_parent_custody", "_validate_d3_parent",
                "len", "isinstance", "set",
            )
        }

        def record_target(target: ast.AST, kind: str) -> None:
            if isinstance(target, ast.Name):
                if target.id in critical_bindings:
                    critical_bindings[target.id].append(kind)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for item in target.elts:
                    record_target(item, kind)
            elif isinstance(target, ast.Starred):
                record_target(target.value, kind)

        for node in ast.walk(module_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in critical_bindings:
                    critical_bindings[node.name].append(type(node).__name__)
            elif isinstance(node, ast.ClassDef):
                if node.name in critical_bindings:
                    critical_bindings[node.name].append("ClassDef")
            elif isinstance(node, ast.Assign):
                value_source = ast.get_source_segment(module_source, node.value)
                for target in node.targets:
                    record_target(target, f"Assign:{value_source}")
            elif isinstance(node, ast.AnnAssign):
                value_source = ast.get_source_segment(module_source, node.value)
                record_target(node.target, f"AnnAssign:{value_source}")
            elif isinstance(node, ast.NamedExpr):
                value_source = ast.get_source_segment(module_source, node.value)
                record_target(node.target, f"NamedExpr:{value_source}")
            elif isinstance(node, ast.AugAssign):
                record_target(node.target, "AugAssign")
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                record_target(node.target, type(node).__name__)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if item.optional_vars is not None:
                        record_target(item.optional_vars, type(node).__name__)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                if node.name in critical_bindings:
                    critical_bindings[node.name].append("ExceptHandler")
            elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
                if node.name in critical_bindings:
                    critical_bindings[node.name].append(type(node).__name__)
            elif isinstance(node, ast.arg) and node.arg in critical_bindings:
                critical_bindings[node.arg].append("argument")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    if bound in critical_bindings:
                        critical_bindings[bound].append(
                            f"Import:{alias.name}:{alias.asname}",
                        )
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    bound = alias.asname or alias.name
                    if bound in critical_bindings:
                        critical_bindings[bound].append(
                            f"ImportFrom:{node.module}:{alias.name}:{alias.asname}",
                        )
        self.assertEqual(critical_bindings, {
            "D3": ["Assign:importlib.util.module_from_spec(_D3_SPEC)"],
            "D0": ["Assign:D3.D0"],
            "D3_REPORT_NAME": [
                'Assign:"majorana_certificate_p7_d3_e_subgrid_probe_report.json"'
            ],
            "loads_json": ["Assign:D0.loads_json"],
            "hashlib": ["Import:hashlib:None"],
            "ProbeError": ["ClassDef"],
            "_expected_d3_parent_custody": ["FunctionDef"],
            "_validate_d3_parent": ["FunctionDef"],
            "len": [],
            "isinstance": [],
            "set": [],
        })
        self.assertIs(D4.loads_json, D4.D0.loads_json)
        self.assertIs(D4.hashlib, hashlib)
        self.assertIs(D4.hashlib.sha256, FROZEN_HASHLIB_SHA256)
        self.assertEqual(
            Path(D4.loads_json.__code__.co_filename).resolve(),
            (BASE / D4.D0_ORCHESTRATOR_NAME).resolve(),
        )
        for builtin_name in ("len", "isinstance", "set"):
            self.assertNotIn(builtin_name, D4.__dict__)

        mutation_targets = sorted(
            ast.get_source_segment(module_source, node)
            for node in ast.walk(module_tree)
            if isinstance(node, (ast.Attribute, ast.Subscript))
            and isinstance(node.ctx, (ast.Store, ast.Del))
        )
        self.assertEqual(mutation_targets, sorted([
            "sys.dont_write_bytecode",
            "pins[relative]",
            'row["D4_per_composite_completed_composite_ordinals"]',
            'row["D4_per_composite_events"]',
        ]))
        forbidden_reflection_attributes = {
            "__dict__", "__globals__", "__code__", "__defaults__",
            "__kwdefaults__", "__setattr__", "__delattr__",
            "__getattribute__",
        }
        self.assertFalse(any(
            isinstance(node, ast.Attribute)
            and node.attr in forbidden_reflection_attributes
            for node in ast.walk(module_tree)
        ))
        forbidden_reflection_calls = {
            "getattr", "setattr", "delattr", "vars", "globals", "locals",
            "exec", "eval", "compile", "__import__",
        }
        self.assertFalse(any(
            isinstance(node, ast.Call)
            and (
                isinstance(node.func, ast.Name)
                and node.func.id in forbidden_reflection_calls
                or isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden_reflection_calls
            )
            for node in ast.walk(module_tree)
        ))
        self.assertFalse(any(
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in forbidden_reflection_attributes
            for node in ast.walk(module_tree)
        ))
        mutable_mapping_calls = sorted(
            ast.get_source_segment(module_source, node.func)
            for node in ast.walk(module_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {
                "update", "setdefault", "pop", "popitem", "clear",
            }
        )
        self.assertEqual(mutable_mapping_calls, ["environment.update"])

        assigned_D3_names = {
            target.id
            for node in ast.walk(module_tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            if isinstance(target, ast.Name) and target.id.startswith("D3_")
        }
        self.assertEqual(assigned_D3_names, {
            "D3_ORCHESTRATOR_NAME", "D3_POLICY_NAME", "D3_FIXTURE_NAME",
            "D3_REPORT_NAME", "D3_REPORT_SHA256", "D3_REPORT_SIZE_BYTES",
            "D3_ADMISSION_STATUS",
        })
        parent_validators = [
            node for node in module_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_validate_d3_parent"
        ]
        custody_helpers = [
            node for node in module_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_expected_d3_parent_custody"
        ]
        self.assertEqual(len(parent_validators), 1)
        self.assertEqual(len(custody_helpers), 1)
        parent_validator = parent_validators[0]
        custody_helper = custody_helpers[0]
        self.assertEqual(
            [argument.arg for argument in parent_validator.args.args],
            ["fixture"],
        )
        self.assertFalse(parent_validator.args.defaults)
        self.assertFalse(parent_validator.args.kw_defaults)
        self.assertIsNone(parent_validator.args.vararg)
        self.assertIsNone(parent_validator.args.kwarg)
        self.assertFalse(parent_validator.args.kwonlyargs)
        self.assertFalse(custody_helper.args.args)
        self.assertFalse(custody_helper.args.defaults)
        self.assertFalse(custody_helper.args.kw_defaults)
        self.assertIsNone(custody_helper.args.vararg)
        self.assertIsNone(custody_helper.args.kwarg)
        self.assertFalse(custody_helper.args.kwonlyargs)
        self.assertEqual(
            D4._validate_d3_parent.__code__.co_firstlineno,
            parent_validator.lineno,
        )
        self.assertEqual(
            D4._expected_d3_parent_custody.__code__.co_firstlineno,
            custody_helper.lineno,
        )
        self.assertEqual(len(custody_helper.body), 1)
        self.assertIsInstance(custody_helper.body[0], ast.Return)
        self.assertIsInstance(custody_helper.body[0].value, ast.Dict)
        self.assertFalse(any(
            isinstance(node, (ast.Call, ast.NamedExpr, ast.Subscript))
            for node in ast.walk(custody_helper.body[0])
        ))
        custody_literal = custody_helper.body[0].value
        assert isinstance(custody_literal, ast.Dict)
        self.assertTrue(all(
            isinstance(key, ast.Constant) and isinstance(key.value, str)
            for key in custody_literal.keys
        ))
        self.assertEqual(
            {key.value for key in custody_literal.keys},
            set(self.fixture["D3_parent_custody"]),
        )

        # Keep the report projection as a closed, auditable leaf.  In
        # particular, defaults on a nested callable must not be able to bind
        # D3 or the full report and invoke an otherwise invisible helper.
        for node in ast.walk(parent_validator):
            if node is parent_validator:
                continue
            self.assertNotIsInstance(node, (
                ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda,
                ast.ClassDef, ast.Match, ast.Global, ast.Nonlocal,
            ))
        actual_call_targets = sorted(
            ast.get_source_segment(module_source, node.func)
            for node in ast.walk(parent_validator)
            if isinstance(node, ast.Call)
        )
        expected_call_targets = sorted(
            ["D3._classify_event_names"]
            + ["ProbeError"] * 12
            + [
                "_expected_d3_parent_custody",
                "admission.get",
                "fixture.get",
                "hashlib.sha256",
                "hashlib.sha256(body).hexdigest",
            ]
            + ["isinstance"] * 7
            + [
                "len",
                "loads_json",
                "name_set.isdisjoint",
                "names.append",
            ]
            + ["observation.get"] * 3
            + ["report.get"] * 6
            + [
                "report_path.is_file",
                "report_path.is_symlink",
                "report_path.read_bytes",
                "required.issubset",
                "row.get",
                "set",
            ]
        )
        self.assertEqual(actual_call_targets, expected_call_targets)
        validator_source = ast.get_source_segment(module_source, parent_validator)
        self.assertIsNotNone(validator_source)
        assert validator_source is not None
        for forbidden_field_token in (
            "process_started", "process_returncode", "outer_timeout_triggered",
            "outer_monotonic_elapsed_ns", "stdout_bytes", "stdout_sha256",
            "stderr_bytes", "stderr_sha256", "time_diagnostics",
            "diagnostic_terminal_branch", "phase_event_count",
            "phase_trace_protocol_sha256", "phase_channel_bytes",
            "phase_channel_sha256", "phase_channel_eof", "last_phase_event",
            "outer_receive_elapsed_ns", "maximum_resident_set_size", "rss",
            "candidate", "staging_manifest", "instrumented_kernel_custody",
            "host_caps", "scientific_values", "majoranas", "coefficient",
            "selected_mask", "ticks", "final_state",
        ):
            with self.subTest(forbidden_D3_field=forbidden_field_token):
                self.assertNotIn(forbidden_field_token, validator_source.lower())
        # The only bare `status` key is the explicitly allowed S0 status.
        self.assertEqual(validator_source.count('"status"'), 1)

        parents = {
            child: node
            for node in ast.walk(module_tree)
            for child in ast.iter_child_nodes(node)
        }
        report_name_shapes: list[str] = []
        for node in ast.walk(module_tree):
            if not isinstance(node, ast.Name) or node.id != "D3_REPORT_NAME":
                continue
            parent = parents[node]
            if isinstance(node.ctx, ast.Store):
                self.assertIsInstance(parent, ast.Assign)
                self.assertEqual(
                    ast.get_source_segment(module_source, parent),
                    'D3_REPORT_NAME = '
                    '"majorana_certificate_p7_d3_e_subgrid_probe_report.json"',
                )
                report_name_shapes.append("Store:constant-assignment")
            elif isinstance(parent, ast.Dict):
                matching_indexes = [
                    index for index, value in enumerate(parent.values)
                    if value is node
                ]
                self.assertEqual(len(matching_indexes), 1)
                key = parent.keys[matching_indexes[0]]
                self.assertIsInstance(key, ast.Constant)
                self.assertEqual(key.value, "report_relative_path")
                report_name_shapes.append("Load:sanitized-custody-dict")
            elif isinstance(parent, ast.BinOp):
                self.assertIsInstance(parent.op, ast.Div)
                self.assertIs(parent.right, node)
                self.assertIsInstance(parent.left, ast.Name)
                self.assertEqual(parent.left.id, "BASE")
                report_name_shapes.append("Load:validator-path")
            elif isinstance(parent, ast.Call):
                self.assertIsInstance(parent.func, ast.Name)
                self.assertEqual(parent.func.id, "loads_json")
                self.assertEqual(len(parent.args), 2)
                self.assertIs(parent.args[1], node)
                report_name_shapes.append("Load:validator-parser-context")
            else:
                self.fail("D3 report name escaped its frozen custody uses")
        self.assertEqual(sorted(report_name_shapes), sorted([
            "Store:constant-assignment",
            "Load:sanitized-custody-dict",
            "Load:validator-path",
            "Load:validator-parser-context",
        ]))
        report_name_literals = [
            node for node in ast.walk(module_tree)
            if isinstance(node, ast.Constant)
            and node.value
            == "majorana_certificate_p7_d3_e_subgrid_probe_report.json"
        ]
        self.assertEqual(len(report_name_literals), 1)
        self.assertIsInstance(parents[report_name_literals[0]], ast.Assign)

        loads_json_calls = [
            node for node in ast.walk(parent_validator)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "loads_json"
        ]
        self.assertEqual(len(loads_json_calls), 1)
        loads_json_call = loads_json_calls[0]
        loads_json_parent = parents[loads_json_call]
        self.assertIsInstance(loads_json_parent, ast.Assign)
        self.assertEqual(len(loads_json_parent.targets), 1)
        self.assertIsInstance(loads_json_parent.targets[0], ast.Name)
        self.assertEqual(loads_json_parent.targets[0].id, "report")
        self.assertIs(loads_json_parent.value, loads_json_call)
        self.assertEqual(
            ast.get_source_segment(module_source, loads_json_parent),
            "report = loads_json(body, D3_REPORT_NAME)",
        )
        d3_attributes: list[str] = []
        d3_bootstrap_argument_count = 0
        d3_store_count = 0
        for node in ast.walk(module_tree):
            if not isinstance(node, ast.Name) or node.id != "D3":
                continue
            parent = parents[node]
            if isinstance(node.ctx, ast.Store):
                self.assertIsInstance(parent, ast.Assign)
                self.assertEqual(
                    ast.get_source_segment(module_source, parent),
                    "D3 = importlib.util.module_from_spec(_D3_SPEC)",
                )
                d3_store_count += 1
            elif (
                isinstance(parent, ast.Attribute)
                and parent.value is node
            ):
                self.assertIsInstance(parent.ctx, ast.Load)
                d3_attributes.append(parent.attr)
            elif (
                isinstance(parent, ast.Call)
                and isinstance(parent.func, ast.Attribute)
                and parent.func.attr == "exec_module"
                and len(parent.args) == 1
                and parent.args[0] is node
                and not parent.keywords
            ):
                self.assertEqual(
                    ast.get_source_segment(module_source, parent.func),
                    "_D3_SPEC.loader.exec_module",
                )
                d3_bootstrap_argument_count += 1
            else:
                self.fail("bare or aliased D3 reference bypasses the firewall")
        self.assertEqual(d3_store_count, 1)
        self.assertEqual(d3_bootstrap_argument_count, 1)
        self.assertEqual(sorted(d3_attributes), sorted([
            "D2", "D1", "D0", "CANDIDATE_ID",
            "SCIENTIFIC_PROBE_MODE", "ALGORITHM_ID",
            "REPORT_TYPE", "REPORT_TYPE", "_classify_event_names",
        ]))

        d3_calls: list[str] = []
        for node in ast.walk(module_tree):
            if not isinstance(node, ast.Call):
                continue
            d3_in_callable = any(
                isinstance(item, ast.Name) and item.id == "D3"
                for item in ast.walk(node.func)
            )
            if d3_in_callable and (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "D3"
                and node.func.attr == "_classify_event_names"
            ):
                d3_calls.append(node.func.attr)
            elif d3_in_callable:
                self.fail("non-allowlisted D3 call bypasses the firewall")
            d3_forwarded = any(
                isinstance(item, ast.Name) and item.id == "D3"
                for argument in (*node.args, *(item.value for item in node.keywords))
                for item in ast.walk(argument)
            )
            frozen_import_bootstrap = (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "exec_module"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "loader"
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "_D3_SPEC"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "D3"
                and not node.keywords
            )
            if d3_forwarded and not frozen_import_bootstrap:
                self.fail("D3 module was forwarded to another callable")
        self.assertEqual(d3_calls, ["_classify_event_names"])

        allowed_d3_attribute_assignments = {
            ("D2", "D2"), ("D1", "D1"), ("D0", "D0"),
            ("CANDIDATE_ID", "CANDIDATE_ID"),
            ("SCIENTIFIC_PROBE_MODE", "SCIENTIFIC_PROBE_MODE"),
            ("ALGORITHM_ID", "ALGORITHM_ID"),
        }
        actual_d3_attribute_assignments: set[tuple[str, str]] = set()
        for node in ast.walk(module_tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value
            elif isinstance(node, ast.NamedExpr):
                targets = [node.target]
                value = node.value
            else:
                continue
            if value is None:
                continue
            d3_attributes = [
                item for item in ast.walk(value)
                if isinstance(item, ast.Attribute)
                and isinstance(item.value, ast.Name)
                and item.value.id == "D3"
            ]
            if not d3_attributes:
                continue
            if (
                len(targets) == 1
                and isinstance(targets[0], ast.Name)
                and isinstance(value, ast.Attribute)
                and isinstance(value.value, ast.Name)
                and value.value.id == "D3"
            ):
                actual_d3_attribute_assignments.add((targets[0].id, value.attr))
            else:
                self.assertEqual(
                    {item.attr for item in d3_attributes}, {"REPORT_TYPE"},
                )
        self.assertEqual(
            actual_d3_attribute_assignments,
            allowed_d3_attribute_assignments,
        )

        allowed_keys = {
            "report": {
                "report_type", "scientific_authority", "certificate_eligible",
                "result_contract_eligible", "observation", "S0_admission",
            },
            "observation": {
                "phase_trace_status", "resource_witness", "phase_events",
            },
            "admission": {"status"},
            "row": {"event"},
        }
        sensitive_usage_shapes = {name: [] for name in allowed_keys}
        sensitive_usage_shapes["phase_events"] = []
        for node in ast.walk(parent_validator):
            if (
                not isinstance(node, ast.Name)
                or node.id not in sensitive_usage_shapes
            ):
                continue
            parent = parents[node]
            if isinstance(node.ctx, ast.Store):
                if node.id == "row":
                    self.assertIsInstance(parent, ast.For)
                    self.assertIs(parent.target, node)
                    self.assertIsInstance(parent.iter, ast.Name)
                    self.assertEqual(parent.iter.id, "phase_events")
                    shape = "Store:for.target"
                else:
                    self.assertIsInstance(parent, ast.Assign)
                    self.assertEqual(len(parent.targets), 1)
                    self.assertIs(parent.targets[0], node)
                    shape = "Store:assign"
            elif (
                isinstance(parent, ast.Attribute)
                and parent.value is node
            ):
                self.assertEqual(parent.attr, "get")
                self.assertIsInstance(parent.ctx, ast.Load)
                call = parents[parent]
                self.assertIsInstance(call, ast.Call)
                self.assertIs(call.func, parent)
                shape = "Load:get"
            elif isinstance(parent, ast.Call) and node in parent.args:
                self.assertIsInstance(parent.func, ast.Name)
                self.assertEqual(parent.func.id, "isinstance")
                self.assertEqual(len(parent.args), 2)
                self.assertIs(parent.args[0], node)
                self.assertIsInstance(parent.args[1], ast.Name)
                self.assertFalse(parent.keywords)
                shape = f"Load:isinstance:{parent.args[1].id}"
            elif (
                node.id == "phase_events"
                and isinstance(parent, ast.For)
                and parent.iter is node
            ):
                shape = "Load:for.iter"
            else:
                self.fail(
                    f"nonprojective use of D3 parent object {node.id}"
                )
            sensitive_usage_shapes[node.id].append(shape)
        self.assertEqual(
            {name: sorted(shapes)
             for name, shapes in sensitive_usage_shapes.items()},
            {
                "report": sorted(
                    ["Store:assign", "Load:isinstance:dict"]
                    + ["Load:get"] * 6
                ),
                "observation": sorted(
                    ["Store:assign", "Load:isinstance:dict"]
                    + ["Load:get"] * 3
                ),
                "admission": sorted([
                    "Store:assign", "Load:isinstance:dict", "Load:get",
                ]),
                "phase_events": sorted([
                    "Store:assign", "Load:isinstance:list", "Load:for.iter",
                ]),
                "row": sorted([
                    "Store:for.target", "Load:isinstance:dict", "Load:get",
                ]),
            },
        )

        def parent_signatures(name: str) -> list[tuple[str, str, str]]:
            return sorted(
                (
                    type(node.ctx).__name__,
                    type(parents[node]).__name__,
                    ast.get_source_segment(module_source, parents[node]),
                )
                for node in ast.walk(parent_validator)
                if isinstance(node, ast.Name) and node.id == name
            )

        self.assertEqual(parent_signatures("body"), sorted([
            ("Store", "Assign", "body = report_path.read_bytes()"),
            ("Load", "Call", "len(body)"),
            ("Load", "Call", "hashlib.sha256(body)"),
            ("Load", "Call", "loads_json(body, D3_REPORT_NAME)"),
        ]))
        self.assertEqual(parent_signatures("names"), sorted([
            ("Store", "AnnAssign", "names: list[str] = []"),
            ("Load", "Attribute", "names.append"),
            ("Load", "Call", "D3._classify_event_names(names)"),
            ("Load", "Call", "set(names)"),
        ]))
        self.assertEqual(parent_signatures("event_name"), sorted([
            ("Store", "Assign", 'event_name = row.get("event")'),
            ("Load", "Call", "isinstance(event_name, str)"),
            ("Load", "Call", "names.append(event_name)"),
        ]))
        self.assertEqual(parent_signatures("name_set"), sorted([
            ("Store", "Assign", "name_set = set(names)"),
            ("Load", "Call", "required.issubset(name_set)"),
            ("Load", "Attribute", "name_set.isdisjoint"),
        ]))

        marker_set_assignments = {
            name: [
                node for node in ast.walk(parent_validator)
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == name
            ]
            for name in ("required", "forbidden")
        }
        self.assertTrue(all(
            len(nodes) == 1 for nodes in marker_set_assignments.values()
        ))
        for nodes in marker_set_assignments.values():
            self.assertIsInstance(nodes[0].value, ast.Set)
            self.assertTrue(all(
                isinstance(item, ast.Constant) and isinstance(item.value, str)
                for item in nodes[0].value.elts
            ))
        required_assignment = marker_set_assignments["required"][0]
        forbidden_assignment = marker_set_assignments["forbidden"][0]
        assert isinstance(required_assignment.value, ast.Set)
        assert isinstance(forbidden_assignment.value, ast.Set)
        self.assertEqual(
            {item.value for item in required_assignment.value.elts},
            {
                "STEP3_SEGMENT_A_RETURNED", "STEP3_SEGMENT_B_RETURNED",
                "STEP3_SEGMENT_C_RETURNED", "STEP3_SEGMENT_D_RETURNED",
                "STEP3_SEGMENT_E_STARTED",
                "STEP3_SEGMENT_E_CHECKPOINT_1_REACHED",
            },
        )
        self.assertEqual(
            {item.value for item in forbidden_assignment.value.elts},
            {
                "STEP3_SEGMENT_E_SUBGRID_26_REACHED",
                "STEP3_SEGMENT_E_SUBGRID_30_REACHED",
                "STEP3_SEGMENT_E_SUBGRID_34_REACHED",
                "STEP3_SEGMENT_E_SUBGRID_38_REACHED",
                "STEP3_SEGMENT_E_CHECKPOINT_2_REACHED",
                "STEP3_SEGMENT_E_RETURNED",
                "STEP3_SEGMENT_F_STARTED", "STEP3_SEGMENT_G_STARTED",
                "STEP3_SEGMENT_H_STARTED", "STEP3_SEGMENT_I_STARTED",
                "STEP3_ENGINE_RETURNED", "STEP3_FINALIZER_STARTED",
                "STEP3_FINALIZER_RETURNED",
            },
        )
        self.assertEqual(parent_signatures("required"), sorted([
            ("Store", "Assign", ast.get_source_segment(
                module_source, required_assignment,
            )),
            ("Load", "Attribute", "required.issubset"),
        ]))
        self.assertEqual(parent_signatures("forbidden"), sorted([
            ("Store", "Assign", ast.get_source_segment(
                module_source, forbidden_assignment,
            )),
            ("Load", "Call", "name_set.isdisjoint(forbidden)"),
        ]))
        accessed_keys = {name: set() for name in allowed_keys}
        for node in ast.walk(parent_validator):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in allowed_keys
            ):
                self.assertEqual(node.func.attr, "get")
                self.assertEqual(len(node.args), 1)
                self.assertFalse(node.keywords)
                self.assertIsInstance(node.args[0], ast.Constant)
                self.assertIsInstance(node.args[0].value, str)
                accessed_keys[node.func.value.id].add(node.args[0].value)
            elif (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id in allowed_keys
            ):
                self.assertIsInstance(node.slice, ast.Constant)
                self.assertIsInstance(node.slice.value, str)
                accessed_keys[node.value.id].add(node.slice.value)
        self.assertEqual(accessed_keys, allowed_keys)

        allowed_sensitive_extracts = {
            ("observation", "report", "observation"),
            ("admission", "report", "S0_admission"),
            ("phase_events", "observation", "phase_events"),
            ("event_name", "row", "event"),
        }
        actual_sensitive_extracts: set[tuple[str, str, str]] = set()
        sensitive_names = set(allowed_keys) | {"phase_events"}

        def sensitive_references(node: ast.AST | None) -> set[str]:
            if node is None:
                return set()
            return {
                item.id for item in ast.walk(node)
                if isinstance(item, ast.Name) and item.id in sensitive_names
            }

        for node in ast.walk(parent_validator):
            if isinstance(node, ast.Assign):
                targets = node.targets
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value
            elif isinstance(node, ast.NamedExpr):
                targets = [node.target]
                value = node.value
            else:
                continue
            if not sensitive_references(value):
                continue
            self.assertEqual(len(targets), 1)
            self.assertIsInstance(targets[0], ast.Name)
            self.assertIsInstance(value, ast.Call)
            self.assertIsInstance(value.func, ast.Attribute)
            self.assertIsInstance(value.func.value, ast.Name)
            self.assertEqual(value.func.attr, "get")
            self.assertEqual(len(value.args), 1)
            self.assertIsInstance(value.args[0], ast.Constant)
            actual_sensitive_extracts.add((
                targets[0].id, value.func.value.id, value.args[0].value,
            ))
        self.assertEqual(actual_sensitive_extracts, allowed_sensitive_extracts)

        for node in ast.walk(parent_validator):
            if isinstance(node, (ast.For, ast.AsyncFor)) and (
                sensitive_references(node.iter)
                or sensitive_references(node.target)
            ):
                self.assertIsInstance(node.target, ast.Name)
                self.assertEqual(node.target.id, "row")
                self.assertIsInstance(node.iter, ast.Name)
                self.assertEqual(node.iter.id, "phase_events")
            elif isinstance(node, ast.comprehension) and (
                sensitive_references(node.iter)
                or sensitive_references(node.target)
            ):
                self.fail("comprehension aliases a D3 parent report projection")
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if (
                        sensitive_references(item.context_expr)
                        or sensitive_references(item.optional_vars)
                    ):
                        self.fail("with-as aliases a D3 parent report projection")
            elif isinstance(node, ast.AugAssign) and (
                sensitive_references(node.target)
                or sensitive_references(node.value)
            ):
                self.fail("augmented assignment aliases a D3 report projection")

        for node in ast.walk(parent_validator):
            if not isinstance(node, ast.Call):
                continue
            sensitive_arguments = {
                item.id
                for argument in (*node.args, *(item.value for item in node.keywords))
                for item in ast.walk(argument)
                if isinstance(item, ast.Name) and item.id in sensitive_names
            }
            if sensitive_arguments:
                self.assertIsInstance(node.func, ast.Name)
                self.assertEqual(node.func.id, "isinstance")
        returns = [
            node for node in ast.walk(parent_validator)
            if isinstance(node, ast.Return)
        ]
        self.assertEqual(len(returns), 1)
        self.assertIsInstance(returns[0].value, ast.Name)
        self.assertEqual(returns[0].value.id, "custody")
        self.assertFalse(any(
            isinstance(node, (ast.Yield, ast.YieldFrom))
            for node in ast.walk(parent_validator)
        ))

    def test_V2_supersedes_only_the_unexecuted_V1_preprobe(self) -> None:
        self.assertEqual(
            D4.POLICY_ID,
            "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D4-E-PER-COMPOSITE-V2",
        )
        self.assertEqual(
            D4.REPORT_TYPE,
            "majorana_p7_step3_e768_max_lazy37_e_per_composite_report_d4_v2",
        )
        self.assertEqual(
            D4.DIAGNOSTIC_MODE,
            "E768_MAX_LAZY37_STEP3_D4_E_PER_COMPOSITE_V2",
        )
        self.assertEqual(
            D4.SUPERSEDED_D4_V1_PREPROBE_COMMIT,
            "c8a4d9e137d4976e1b8841041a72b53993068e46",
        )
        D4._validate_superseded_d4_v1_preprobe_identity()
        role = self.fixture["diagnostic_role"]
        firewall = self.policy["hindsight_firewall"]
        for key, value in D4.D4_V1_SUPERSESSION_ASSERTIONS.items():
            self.assertEqual(role[key], value)
            self.assertEqual(firewall[key], value)
        self.assertNotEqual(D4.SUPERSEDED_D4_V1_PREPROBE_COMMIT, D4.DIRECT_PARENT)
        self.assertEqual(
            self.policy["frozen_D3_dependency"]["result_commit_sha"],
            D4.DIRECT_PARENT,
        )
        self.assertNotIn(
            D4.SUPERSEDED_D4_V1_PREPROBE_COMMIT,
            self.policy["frozen_D3_dependency"].values(),
        )

    def test_candidate_algorithm_caps_and_S0_nonadmission_are_unchanged(self) -> None:
        identity = self.fixture["frozen_candidate_identity"]
        self.assertEqual(identity["candidate_id"], D4.CANDIDATE_ID)
        self.assertEqual(identity["scientific_probe_mode"], D4.SCIENTIFIC_PROBE_MODE)
        self.assertEqual(identity["algorithm_id"], D4.ALGORITHM_ID)
        self.assertTrue(identity["D4_does_not_define_a_new_scientific_candidate"])
        d0_fixture = D4.D0._validate_fixture(D4.load_json(BASE / D4.D0_FIXTURE_NAME))
        self.assertEqual(self.fixture["host_supervisor_caps"], d0_fixture["host_supervisor_caps"])
        self.assertEqual(self.fixture["runtime_custody"], d0_fixture["runtime_custody"])
        self.assertEqual(self.fixture["host_supervisor_caps"]["MemoryMax_bytes"], 2 * 1024**3)
        self.assertEqual(self.fixture["host_supervisor_caps"]["MemorySwapMax_bytes"], 0)
        self.assertEqual(self.fixture["host_supervisor_caps"]["RuntimeMaxSec"], "1800s")
        self.assertEqual(D4.S0_ADMISSION, {
            "status": "NOT_ESTABLISHED_BY_D4_E_PER_COMPOSITE_DIAGNOSTIC",
            "derived_from_D4": False,
            "D3_status_unchanged": "NOT_ESTABLISHED_BY_D3_E_SUBGRID_DIAGNOSTIC",
            "same_host_admission_as_D0_D1_D2_and_D3": True,
        })

    def test_all_fixed_and_parameterized_terminal_sequences_are_exact(self) -> None:
        terminal_paths = D4._terminal_paths()
        self.assertEqual(len(terminal_paths), 36)
        self.assertEqual(len(D4._step3_cap_sequences()), 32)
        branch_counts: dict[str, int] = {}
        for branch, sequence in terminal_paths:
            branch_counts[branch] = branch_counts.get(branch, 0) + 1
            legal, terminal = D4._classify_event_names(sequence)
            self.assertTrue(legal)
            self.assertEqual(terminal, branch)
            events, actual = D4._validate_phase_trace(
                collector_for(sequence), self.fixture,
            )
            self.assertEqual(actual, branch)
            self.assertEqual([row["event"] for row in events], sequence)
            for size in range(len(sequence)):
                prefix_legal, _ = D4._classify_event_names(sequence[:size])
                self.assertTrue(prefix_legal)
        self.assertEqual(branch_counts, {
            "FULL_PATH_RETURNED": 1,
            "STEP1_DETERMINISTIC_CAP": 1,
            "STEP2_DETERMINISTIC_CAP": 1,
            "P6_PREFIX_RESOURCE_CONFORMANCE_FAILURE": 1,
            "STEP3_DETERMINISTIC_CAP": 32,
        })
        after_26_then_checkpoint_2 = list(
            D4._COMMON_TO_STEP3 + D4.INTERNAL_SCHEDULE_EVENTS[:23]
        )
        self.assertEqual(after_26_then_checkpoint_2[-2:], [
            "STEP3_SEGMENT_E_COMPOSITE_26_REACHED",
            "STEP3_SEGMENT_E_CHECKPOINT_2_REACHED",
        ])
        self.assertTrue(D4._classify_event_names(after_26_then_checkpoint_2)[0])
        self.assertNotIn("STEP3_SEGMENT_E_COMPOSITE_27_REACHED", D4.ALLOWED_EVENTS)

    def test_zero_internal_cap_gap_duplicate_and_unknown_are_rejected(self) -> None:
        zero_internal_cap = list(D4._COMMON_TO_STEP3 + (
            "STEP3_ENGINE_RETURNED", "STEP3_DETERMINISTIC_CAP_TERMINAL",
        ) + D4._SERIALIZATION_SUFFIX)
        legal, terminal = D4._classify_event_names(zero_internal_cap)
        self.assertFalse(legal)
        self.assertIsNone(terminal)

        for size in D4.UNREACHABLE_SEGMENT_RETURNED_CAP_PREFIX_COUNTS:
            unreachable_cap = list(
                D4._COMMON_TO_STEP3 + D4.INTERNAL_SCHEDULE_EVENTS[:size] + (
                    "STEP3_ENGINE_RETURNED",
                    "STEP3_DETERMINISTIC_CAP_TERMINAL",
                ) + D4._SERIALIZATION_SUFFIX
            )
            with self.subTest(unreachable_cap_prefix=size):
                legal, terminal = D4._classify_event_names(unreachable_cap)
                self.assertFalse(legal)
                self.assertIsNone(terminal)

        internal = list(D4.INTERNAL_SCHEDULE_EVENTS)
        invalid_sequences = (
            list(D4._COMMON_TO_STEP3) + internal[:1] + internal[2:3],
            list(D4._COMMON_TO_STEP3) + [internal[0], internal[0]],
            list(D4._COMMON_TO_STEP3) + ["UNKNOWN"],
        )
        for names in invalid_sequences:
            with self.subTest(names=names[-2:]), self.assertRaises(D4.ProbeError):
                D4._validate_phase_trace(collector_for(names), self.fixture)

    def test_complete_cap_and_interrupted_observations_are_classified(self) -> None:
        completed = D4._observation_from_process(
            process_started=True, returncode=0, timed_out=False,
            **stream_fields(stderr=complete_time_stderr()),
            elapsed_ns=1_000_000_000,
            collector=collector_for(D4.FIXED_TERMINAL_SEQUENCES["FULL_PATH_RETURNED"]),
            fixture=self.fixture,
        )
        self.assertEqual(completed["status"], "COMPLETED_E_PER_COMPOSITE_DIAGNOSTIC")
        self.assertEqual(completed["diagnostic_terminal_branch"], "FULL_PATH_RETURNED")
        self.assertIsNone(completed["resource_witness"])

        cap_sequence = D4._step3_cap_sequences()[17]
        cap = D4._observation_from_process(
            process_started=True, returncode=0, timed_out=False,
            **stream_fields(stderr=complete_time_stderr()),
            elapsed_ns=1_000_000_000,
            collector=collector_for(cap_sequence), fixture=self.fixture,
        )
        self.assertEqual(cap["diagnostic_terminal_branch"], "STEP3_DETERMINISTIC_CAP")

        prefix = list(D4._COMMON_TO_STEP3) + list(D4.INTERNAL_SCHEDULE_EVENTS[:9])
        interrupted = D4._observation_from_process(
            process_started=True, returncode=70, timed_out=False,
            **stream_fields(), elapsed_ns=1_800_000_000_000,
            collector=collector_for(prefix), fixture=self.fixture,
        )
        self.assertEqual(interrupted["status"], "INDETERMINATE_HOST_OR_RUNTIME_FAILURE")
        self.assertEqual(interrupted["phase_trace_status"], "LEGAL_PREFIX_INTERRUPTED")
        self.assertEqual(interrupted["last_phase_event"], prefix[-1])

        transport = D4._observation_from_process(
            process_started=True, returncode=0, timed_out=False,
            **stream_fields(), elapsed_ns=1000,
            collector=collector_for(prefix, eof=False, read_failure=True),
            fixture=self.fixture,
        )
        self.assertEqual(transport["status"], "INDETERMINATE_HOST_OR_RUNTIME_FAILURE")

    def test_nonempty_stdout_exit66_and_incomplete_clean_exit_are_invalid(self) -> None:
        prefix = list(D4._COMMON_TO_STEP3)
        with self.assertRaises(D4.ProbeError):
            D4._observation_from_process(
                process_started=True, returncode=0, timed_out=False,
                **stream_fields(stdout=b"x"), elapsed_ns=1000,
                collector=collector_for(prefix), fixture=self.fixture,
            )
        with self.assertRaises(D4.ProbeError):
            D4._observation_from_process(
                process_started=True, returncode=66, timed_out=False,
                **stream_fields(), elapsed_ns=1000,
                collector=collector_for(prefix), fixture=self.fixture,
            )
        with self.assertRaises(D4.ProbeError):
            D4._observation_from_process(
                process_started=True, returncode=0, timed_out=False,
                **stream_fields(), elapsed_ns=1000,
                collector=collector_for(prefix), fixture=self.fixture,
            )

    def test_process_not_started_observation_has_one_reachable_shape(self) -> None:
        unstarted = D4._observation_from_process(
            process_started=False, returncode=-1, timed_out=False,
            **stream_fields(), elapsed_ns=1000,
            collector=collector_for([]), fixture=self.fixture,
        )
        self.assertEqual(
            unstarted["status"], "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
        )
        self.assertEqual(unstarted["phase_events"], [])
        self.assertIsNone(unstarted["diagnostic_terminal_branch"])

        invalid_cases = (
            (0, False, b"", []),
            (-1, True, b"", []),
            (-1, False, b"x", []),
            (-1, False, b"", ["D4_RUNNER_STARTED"]),
        )
        for returncode, timed_out, stderr, events in invalid_cases:
            with self.subTest(
                returncode=returncode, timed_out=timed_out,
                stderr=stderr, events=events,
            ), self.assertRaises(D4.ProbeError):
                D4._observation_from_process(
                    process_started=False, returncode=returncode,
                    timed_out=timed_out, **stream_fields(stderr=stderr),
                    elapsed_ns=1000, collector=collector_for(events),
                    fixture=self.fixture,
                )

    def test_pipe_records_are_canonical_contiguous_and_bounded(self) -> None:
        collector = collector_for(["D4_RUNNER_STARTED"])
        bad = D4.canonical_bytes({
            "event": "D4_INPUT_AND_RUNTIME_CUSTODY_VALIDATED", "sequence": 7,
        }) + b"\n"
        collector.lines.append((bad, 102))
        collector.total_bytes += len(bad)
        collector.digest.update(bad)
        with self.assertRaises(D4.ProbeError):
            D4._validate_phase_trace(collector, self.fixture)

        noncanonical = collector_for([])
        line = b'{"sequence":0,"event":"D4_RUNNER_STARTED"}\n'
        noncanonical.lines.append((line, 1))
        noncanonical.total_bytes = len(line)
        noncanonical.digest.update(line)
        with self.assertRaises(D4.ProbeError):
            D4._validate_phase_trace(noncanonical, self.fixture)

        overflow = collector_for(["D4_RUNNER_STARTED"])
        overflow.overflow = True
        with self.assertRaises(D4.ProbeError):
            D4._validate_phase_trace(overflow, self.fixture)

    def test_instrumented_kernel_is_exactly_derived_and_reverse_equal(self) -> None:
        relation = D4._validate_instrumented_kernel()
        self.assertEqual(relation, {
            "frozen_P6_runner_sha256": D4.P6_RUNNER_SHA256,
            "frozen_P6_function_slice_sha256": D4.P6_FUNCTION_SLICE_SHA256,
            "instrumented_D4_function_slice_sha256": (
                "c7443273a6edff6f637d3e3fa7274b299fc04c31889be84e02b0e90ec80b8972"
            ),
            "exact_function_name_substitution_count": 1,
            "exact_marker_insertion_block_count": 4,
            "forward_byte_construction_matches": True,
            "reverse_deletion_matches_frozen_P6_function": True,
            "marker_blocks_contain_no_live_scientific_state_tokens": True,
        })
        contract = self.fixture["scientific_kernel_byte_equivalence"]
        self.assertEqual(
            contract["normalization_contract"]["D4_function_name"],
            "execute_p6_step2_d4",
        )

    def test_scientific_or_marker_mutations_fail_byte_equivalence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p7-d4-kernel-") as temporary:
            root = Path(temporary)
            frozen = root / D4.P6_RUNNER_NAME
            driver = root / D4.PROBE_DRIVER
            frozen.parent.mkdir(parents=True)
            driver.parent.mkdir(parents=True)
            shutil.copyfile(BASE / D4.P6_RUNNER_NAME, frozen)
            shutil.copyfile(BASE / D4.PROBE_DRIVER, driver)
            with mock.patch.object(D4, "BASE", root):
                D4._validate_instrumented_kernel()
                body = driver.read_bytes()
                old = b"    maximum_combined = Int(caps["
                self.assertEqual(body.count(old), 1)
                driver.write_bytes(body.replace(
                    old, b"    maximum_combined = 0 + Int(caps[", 1,
                ))
                with self.assertRaises(D4.ProbeError):
                    D4._validate_instrumented_kernel()

        insertion = D4.MARKER_INSERTIONS[0]
        bad_insertions = (
            (insertion[0], insertion[1] + b"    cache\n", insertion[2]),
            *D4.MARKER_INSERTIONS[1:],
        )
        with mock.patch.object(D4, "MARKER_INSERTIONS", bad_insertions):
            with self.assertRaises(D4.ProbeError):
                D4._validate_instrumented_kernel()

    def test_Julia_driver_instruments_only_step3_and_reads_no_D3_artifact(self) -> None:
        source = (BASE / D4.PROBE_DRIVER).read_text(encoding="utf-8")
        self.assertIn("function execute_p6_step2_d4(", source)
        self.assertEqual(source.count("execute_p6_step2_d4("), 2)
        self.assertIn("if mapped_step_index == 2", source)
        self.assertIn("execution = execute_p6_step2(\n", source)
        self.assertIn("execution = execute_p6_step2_d4(\n", source)
        self.assertIn("3 <= phase_fd <= typemax(Cint)", source)
        self.assertEqual(source.count("include(joinpath("), 1)
        self.assertIn(
            '"majorana_certificate_p7_design_probe",\n'
            '    "majorana_p7_step3_resource_probe.jl",',
            source,
        )
        d3_report = "majorana_certificate_p7_d3_e_subgrid_probe_report.json"
        self.assertEqual(source.count(d3_report), 1)
        self.assertIn(
            '"report_relative_path" =>\n            "' + d3_report + '",',
            source,
        )
        self.assertEqual(source.count("JSON.parsefile("), 7)
        for fixture_variable in (
            "d4_fixture_path", "d0_fixture_path", "p6_fixture_path",
            "p5_fixture_path", "p4_fixture_path", "p3_fixture_path",
            "p2_fixture_path",
        ):
            self.assertIn(f"JSON.parsefile({fixture_variable})", source)
        for excluded_artifact in (
            D4.D3_ORCHESTRATOR_NAME, D4.D3_POLICY_NAME, D4.D3_FIXTURE_NAME,
        ):
            self.assertNotIn(excluded_artifact, source)
        self.assertNotIn(f'JSON.parsefile("{d3_report}")', source)
        self.assertNotIn("time_ns(", source)
        self.assertNotIn("@elapsed", source)
        self.assertNotIn("@timed", source)
        declared = source.split("const P7_D4_PHASE_EVENTS = (", 1)[1].split("\n)", 1)[0]
        names = [line.split('"')[1] for line in declared.splitlines() if '"' in line]
        self.assertEqual(names, self.fixture["phase_event_protocol"]["allowed_events"])

    def test_standard_and_phase_file_descriptors_are_fail_closed(self) -> None:
        D4._validate_standard_fds_open()
        real_fstat = os.fstat
        for closed_descriptor in (0, 1, 2):
            def checked_fstat(
                descriptor: int, *, closed: int = closed_descriptor,
            ) -> os.stat_result:
                if descriptor == closed:
                    raise OSError("closed for test")
                return real_fstat(descriptor)

            with self.subTest(closed_descriptor=closed_descriptor), mock.patch.object(
                D4.os, "fstat", side_effect=checked_fstat,
            ), self.assertRaises(D4.ProbeError):
                D4._validate_standard_fds_open()

        for pipe_fds in ((0, 3), (3, 2)):
            with self.subTest(pipe_fds=pipe_fds), tempfile.TemporaryDirectory(
                prefix="p7-d4-low-fd-",
            ) as temporary, mock.patch.object(
                D4.os, "pipe", return_value=pipe_fds,
            ), mock.patch.object(D4.os, "close") as close_mock, mock.patch.object(
                D4.subprocess, "Popen",
            ) as popen_mock, self.assertRaises(D4.ProbeError):
                root = Path(temporary)
                D4._run_candidate(
                    root, root, root, self.fixture, root,
                )
            popen_mock.assert_not_called()
            close_mock.assert_has_calls(
                [mock.call(descriptor) for descriptor in set(pipe_fds)],
                any_order=True,
            )

        run_source = MODULE_PATH.read_text(encoding="utf-8").split(
            "def run_probe(", 1,
        )[1].split("def _validate_staging_manifest(", 1)[0]
        self.assertLess(
            run_source.index("_validate_standard_fds_open()"),
            run_source.index("_acquire_execution_claim("),
        )

    def test_stage_excludes_D3_results_drivers_and_sidecars(self) -> None:
        joined = " ".join(D4.STAGED_PATHS).lower()
        for fragment in (
            "d1_phase", "d2_schedule", "d3_e_subgrid", "_report.json",
            "_certificate.json", "_contract.json",
            "replay_package", "sidecar", "checkpoint",
        ):
            self.assertNotIn(fragment, joined)
        with tempfile.TemporaryDirectory(prefix="p7-d4-stage-") as temporary:
            rows = D4.stage_probe_tree(Path(temporary), self.policy)
            self.assertEqual(len(rows), 15)
            self.assertTrue(all(row["byte_identical_to_repository"] for row in rows))

    def test_preprobe_path_allowlist_parent_and_result_absence_are_exact(self) -> None:
        self.assertEqual(D4.DIRECT_PARENT, "70b5095fde9fdb743d1e5910b80bbcac88de4fca")
        self.assertEqual(len(D4.PREPROBE_CHANGED_PATHS), 5)
        self.assertEqual(D4.PREPROBE_CHANGED_PATHS, frozenset({
            f"docs/research/fermion-frontier/{D4.POLICY_NAME}",
            f"docs/research/fermion-frontier/{D4.FIXTURE_NAME}",
            f"docs/research/fermion-frontier/{MODULE_PATH.name}",
            f"docs/research/fermion-frontier/{D4.PROBE_DRIVER}",
            f"docs/research/fermion-frontier/{D4.TEST_NAME}",
        }))
        self.assertFalse((BASE / D4.REPORT_NAME).exists())
        self.assertFalse((BASE / D4.EXECUTION_CLAIM_NAME).exists())
        self.assertIsNone(self.fixture["observation_scope"]["resource_witness"])

    def test_plain_cli_import_creates_no_local_bytecode_cache(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p7-d4-pycache-") as temporary:
            environment = os.environ.copy()
            environment.pop("PYTHONDONTWRITEBYTECODE", None)
            environment["PYTHONPYCACHEPREFIX"] = temporary
            process = subprocess.run(
                [sys.executable, str(MODULE_PATH), "--verify-preprobe"],
                cwd=BASE, env=environment, capture_output=True, check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr.decode())
            local_caches = [
                path for path in Path(temporary).rglob("*.pyc")
                if "majorana_certificate_p7" in path.name
            ]
            self.assertEqual(local_caches, [])

    def test_run_output_is_canonical_and_repeat_claim_is_exclusive(self) -> None:
        with self.assertRaises(D4.ProbeError):
            D4._canonical_output_path(Path("/tmp/p7-d4-repeat.json"))
        with tempfile.TemporaryDirectory(prefix="p7-d4-claim-") as temporary:
            root = Path(temporary)
            with mock.patch.object(D4, "BASE", root):
                claim = D4._acquire_execution_claim("a" * 40)
                self.assertEqual(claim.read_text(), "a" * 40 + "\n")
                with self.assertRaises(D4.ProbeError):
                    D4._acquire_execution_claim("a" * 40)


if __name__ == "__main__":
    unittest.main()
