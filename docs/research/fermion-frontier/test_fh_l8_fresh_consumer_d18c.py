import builtins
import copy
import hashlib
import importlib.util
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "fh_l8_fresh_consumer_d18c_runner.py"
CHECKER_PATH = HERE / "fh_l8_fresh_consumer_d18c_checker.py"
LAUNCHER_PATH = HERE / "fh_l8_fresh_consumer_d18c_launcher.py"
CONTRACT_PATH = HERE / "fh_l8_fresh_consumer_d18c_contract.json"
RESULT_PATH = HERE / "fh_l8_fresh_consumer_d18c_result.json"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


RUNNER = _load_module("fh_l8_d18c_runner_test_subject", RUNNER_PATH)
CHECKER = _load_module("fh_l8_d18c_checker_test_subject", CHECKER_PATH)
LAUNCHER = _load_module("fh_l8_d18c_launcher_test_subject", LAUNCHER_PATH)

ZERO_SHA256 = "0" * 64
ZERO_SHA1 = "0" * 40
FIXTURE_SEMANTIC_SHA256 = hashlib.sha256(
    b"d18c-fixture-globally-sorted-target"
).hexdigest()
AUTHORITY_CEILING_KEYS = (
    "full_q4_target_materialized",
    "bounded_output_admissible_as_q4_operand",
    "d12_d13_numeric_authority_restored",
    "d16w_full_h_numeric_authority",
    "full_53_shard_executed",
    "full_53_shard_authorization_granted",
    "runner_terminal_receipt_publication_self_attested",
    "q5_executed",
    "degree6_remainder_bounded",
    "two_step_cumulative_error_bounded",
    "full_R100_error_bounded",
    "physical_reference_qualified",
    "hardware_result_available",
    "quantum_advantage_claimed",
    "ready_gate_eligible",
)


def _contract_fixture():
    implementation_item = {
        "path": RUNNER.RUNNER_NAME,
        "mode": "100644",
        "blob": ZERO_SHA1,
        "bytes": 1,
        "sha256": ZERO_SHA256,
    }
    checker_item = copy.deepcopy(implementation_item)
    checker_item["path"] = RUNNER.CHECKER_NAME
    launcher_item = copy.deepcopy(implementation_item)
    launcher_item["path"] = RUNNER.LAUNCHER_NAME
    test_item = copy.deepcopy(implementation_item)
    test_item["path"] = RUNNER.TEST_NAME
    return {
        "schema_version": 1,
        "contract_id": RUNNER.CONTRACT_ID,
        "analysis_class": "PREREGISTERED_BOUNDED_SCIENTIFIC_ACTION",
        "chronology": {
            "evidence_baseline_commit": ZERO_SHA1,
            "implementation_freeze_commit": ZERO_SHA1,
            "contract_must_be_execution_head": True,
            "checker_and_runner_precede_contract": True,
            "result_absent_through_contract": True,
        },
        "implementation": {
            "runner": implementation_item,
            "checker": checker_item,
            "launcher": launcher_item,
            "test": test_item,
        },
        "source_authority": {
            "packed_c3_commit": RUNNER.PACKED_C3_COMMIT,
            "packed_checkpoint": {
                "path": RUNNER.SOURCE_NAME,
                "mode": "100644",
                "blob": RUNNER.PACKED_BLOB,
                "bytes": RUNNER.SOURCE_RECORDS * RUNNER.SOURCE_RECORD.size,
                "records": RUNNER.SOURCE_RECORDS,
                "record_bytes": RUNNER.SOURCE_RECORD.size,
                "sha256": RUNNER.PACKED_SHA256,
            },
            "packed_result_sha256": RUNNER.PACKED_RESULT_SHA256,
            "packed_terminal_receipt_sha256": RUNNER.PACKED_RECEIPT_SHA256,
            "packed_shard_manifest_sha256": RUNNER.PACKED_SHARD_MANIFEST_SHA256,
            "first_4096_raw_sha256": RUNNER.FIRST_4096_RAW_SHA256,
            "first_4096_projection_sha256": (
                RUNNER.FIRST_4096_PROJECTION_SHA256
            ),
            "d5_checker_sha256": RUNNER.D5_SHA256,
            "kernel_source_pins": copy.deepcopy(
                RUNNER.EXPECTED_KERNEL_SOURCE_PINS
            ),
            "d16_forensic_result_sha256": RUNNER.D16_RESULT_SHA256,
            "d17_contract_sha256": RUNNER.D17_CONTRACT_SHA256,
            "d17_result_sha256": RUNNER.D17_RESULT_SHA256,
            "legacy_spool_or_target_permitted": False,
        },
        "execution_authorization": {
            "bounded_preflight_execution_authorized": True,
            "authorized_unique_q3_rows": RUNNER.BOUNDED_ROWS,
            "authorized_row_start": 0,
            "authorized_row_end_exclusive": RUNNER.BOUNDED_ROWS,
            "authorized_kernel_evaluations": RUNNER.BOUNDED_ROWS * 2,
            "full_53_shard_execution_authorized": False,
        },
        "consumer_protocol": {
            "fresh_exclusive_scratch": True,
            "allowed_scratch_parent": "/Data/CascadeProjects/.ab-experiments",
            "deny_filesystem_types": ["ramfs", "tmpfs"],
            "exclusive_lock": True,
            "full_source_validation_before_action": True,
            "source_rehash_after_action": True,
            "partition_count": RUNNER.PARTITIONS,
            "partition_selector": "SHA256(target_u128_be)[0]",
            "spill_record_bytes": RUNNER.SPILL_RECORD.size,
            "scaled_denominator": 8,
            "manifest_only_merge": True,
            "atomic_no_replace_publication": True,
            "directory_fsync": True,
            "second_pass_naive_aggregation_replay": True,
            "bounded_output_is_full_q4_operand": False,
        },
        "resource_limits": copy.deepcopy(RUNNER.EXPECTED_LIMITS),
        "diagnostic_comparator": copy.deepcopy(RUNNER.EXPECTED_COMPARATOR),
        "decision_rule": copy.deepcopy(RUNNER.EXPECTED_DECISION_RULE),
        "authority_ceiling": {key: False for key in AUTHORITY_CEILING_KEYS},
        "limitations": list(RUNNER.EXPECTED_LIMITATIONS),
    }


def _empty_state():
    return {
        "source_admitted": True,
        "action_started": False,
        "unique_q3_rows_acted": 0,
        "kernel_evaluations": 0,
        "validation_replay_rows": 0,
        "spill_complete": False,
        "merge_complete": False,
        "bounded_target_materialized": False,
        "naive_equivalence_complete": False,
        "full_53_shard_executed": False,
        "full_q4_target_materialized": False,
    }


def _source_payload():
    first = (1 << 64) - 1
    second = first - 3 + (1 << 64) + (1 << 65)
    records = (
        RUNNER.SOURCE_RECORD.pack(first.to_bytes(16, "big"), 1, 8, 0, 0, 0),
        RUNNER.SOURCE_RECORD.pack(second.to_bytes(16, "big"), -1, 8, 0, 0, 1),
    )
    return records


def _spill_manifest(partitions):
    empty_sha = hashlib.sha256(b"").hexdigest()
    entries = [
        {
            "partition": index,
            "path": f"p{index:03d}.bin",
            "records": 0,
            "bytes": 0,
            "sha256": empty_sha,
        }
        for index in range(partitions)
    ]
    return {
        "schema_version": 1,
        "contract_id": RUNNER.CONTRACT_ID,
        "source_row_start": 0,
        "source_row_end_exclusive": RUNNER.BOUNDED_ROWS,
        "source_rows": RUNNER.BOUNDED_ROWS,
        "source_first_4096_raw_sha256": ZERO_SHA256,
        "record_bytes": RUNNER.SPILL_RECORD.size,
        "scaled_denominator": 8,
        "partition_count": partitions,
        "partition_selector": "SHA256(target_u128_be)[0]",
        "spill_records": 0,
        "spill_bytes": 0,
        "reduced_columns": 0,
        "projected_zero_outputs": 0,
        "zero_coefficients_dropped": 0,
        "partitions": entries,
        "complete": True,
    }


def _result_fixture(contract):
    target = contract["diagnostic_comparator"]
    state = {
        "source_admitted": True,
        "action_started": True,
        "unique_q3_rows_acted": CHECKER.BOUNDED_ROWS,
        "kernel_evaluations": CHECKER.BOUNDED_ROWS * 2,
        "validation_replay_rows": CHECKER.BOUNDED_ROWS,
        "spill_complete": True,
        "merge_complete": True,
        "bounded_target_materialized": True,
        "naive_equivalence_complete": True,
        "full_53_shard_executed": False,
        "full_q4_target_materialized": False,
    }
    authority = {
        "bounded_4096_preflight_executed": True,
        "partial_q3_to_q4_action_executed": True,
        **contract["authority_ceiling"],
    }
    return {
        "schema_version": 1,
        "contract_id": CHECKER.CONTRACT_ID,
        "status": "VERIFIED_D18C_FRESH_EXCLUSIVE_PACKED_Q3_BOUNDED_4096_PREFLIGHT",
        "verified": True,
        "analysis_class": "BOUNDED_PARTIAL_Q3_TO_Q4_SCIENTIFIC_ACTION",
        "implementation_freeze_commit": contract["chronology"][
            "implementation_freeze_commit"
        ],
        "contract_freeze_commit": ZERO_SHA1,
        "source": {
            "records_validated": CHECKER.SOURCE_RECORDS,
            "record_bytes": CHECKER.SOURCE_RECORD.size,
            "payload_bytes": CHECKER.SOURCE_RECORDS * CHECKER.SOURCE_RECORD.size,
            "payload_sha256": contract["source_authority"]["packed_checkpoint"][
                "sha256"
            ],
            "first_4096_raw_sha256": contract["source_authority"][
                "first_4096_raw_sha256"
            ],
            "first_4096_projection_sha256": contract["source_authority"][
                "first_4096_projection_sha256"
            ],
            "first_representative_hex": "0x1",
            "last_selected_representative_hex": "0x2",
            "rank_permutation_valid": True,
            "source_stat": {
                "device": 1,
                "inode": 2,
                "mode": 0o644,
                "size": CHECKER.SOURCE_RECORDS * CHECKER.SOURCE_RECORD.size,
                "mtime_ns": 3,
                "ctime_ns": 4,
            },
        },
        "source_authority": {
            "packed_c3_ancestor": True,
            "d18_result_ancestor": True,
            "d16_packed_q3_admissible": True,
            "d16_legacy_q4_quarantined": True,
            "d17_prior_bounded_execution_authorized": False,
            "d18_diagnostic_execution_authority_admitted": False,
        },
        "kernel_custody": {
            "artifacts": [
                {
                    "path": pin["path"],
                    "bytes": 1,
                    "sha256": pin["sha256"],
                    "device": 1,
                    "inode": index + 1,
                    "mode": 0o644,
                    "mtime_ns": 1,
                    "ctime_ns": 1,
                    "git_blob": ZERO_SHA1,
                }
                for index, pin in enumerate(
                    contract["source_authority"]["kernel_source_pins"]
                )
            ],
            "compiled_from_single_pre_action_byte_snapshot": True,
            "transitive_worktree_module_or_contract_loads_during_action": False,
        },
        "scratch_custody": {
            "filesystem_type": "ext4",
            "scratch_parent_device": 1,
            "scratch_parent_owner_uid": 1_000,
            "scratch_parent_mode": 0o700,
            "scratch_root_device": 1,
            "scratch_root_inode": 2,
            "scratch_root_owner_uid": 1_000,
            "scratch_root_mode": 0o700,
            "exclusive_lock_device": 1,
            "exclusive_lock_inode": 3,
            "exclusive_lock_owner_uid": 1_000,
            "exclusive_lock_mode": 0o600,
            "exclusive_lock": True,
            "created_regular_files_before_receipt": sorted(
                {
                    "exclusive.lock",
                    "bounded-q4-partial.bin",
                    "bounded-q4-partial.manifest.json",
                    "spill/manifest.json",
                }
                | {
                    f"spill/p{index:03d}.bin"
                    for index in range(CHECKER.PARTITIONS)
                }
            ),
        },
        "state": state,
        "spill": {
            "manifest": {
                "path": "manifest.json",
                "bytes": 1,
                "sha256": ZERO_SHA256,
            },
            "spill_records": target["spill_records"],
            "spill_bytes": target["spill_records"] * CHECKER.SPILL_RECORD.size,
            "reduced_columns": target["reduced_columns"],
            "projected_zero_outputs": target["projected_zero_outputs"],
            "zero_coefficients_dropped": 0,
            "partition_count": target["partition_count"],
        },
        "bounded_partial_target": {
            "target": {
                "path": "bounded-q4-partial.bin",
                "bytes": target["target_bytes"],
                "sha256": target["target_sha256"],
            },
            "manifest": {
                "path": "bounded-q4-partial.manifest.json",
                "bytes": 1,
                "sha256": ZERO_SHA256,
            },
            "target_records": target["target_records"],
            "target_bytes": target["target_bytes"],
            "target_sha256": target["target_sha256"],
            "ordering": "partition_sha256_byte_then_target_u128",
            "partition_target_counts": [
                target["target_records"],
                *([0] * (CHECKER.PARTITIONS - 1)),
            ],
        },
        "naive_equivalence": {
            "verified": True,
            "source_rows_replayed": CHECKER.BOUNDED_ROWS,
            "target_records": target["target_records"],
            "target_sorted_semantic_sha256": FIXTURE_SEMANTIC_SHA256,
        },
        "diagnostic_comparator": {
            "authority": False,
            "role": "PREREGISTERED_NON_AUTHORITATIVE_REPRODUCIBILITY_GUARD",
            "mismatch_is_preflight_no_go": True,
            "match": True,
            "target_records": target["target_records"],
            "target_bytes": target["target_bytes"],
            "target_sha256": target["target_sha256"],
            "spill_records": target["spill_records"],
            "reduced_columns": target["reduced_columns"],
            "projected_zero_outputs": target["projected_zero_outputs"],
            "partition_count": target["partition_count"],
        },
        "resources": {
            "cgroup_path": "/user.slice/ab-fh-l8-d18c-fixture.service",
            "cgroup_inode": 1,
            "memory_current_before_bytes": 1,
            "memory_current_after_bytes": 1,
            "memory_peak_before_bytes": 1,
            "memory_peak_after_bytes": 1,
            "memory_max": contract["resource_limits"]["memory_max"],
            "memory_high": contract["resource_limits"]["memory_high"],
            "memory_swap_current_after_bytes": 0,
            "memory_swap_max": contract["resource_limits"]["memory_swap_max"],
            "process_peak_rss_bytes": 1,
            "elapsed_monotonic_ns": 1,
            "observation_scope": (
                "after_bounded_target_and_manifests;"
                "before_runner_terminal_receipt_publication"
            ),
            "memory_event_delta": {
                "high": 0,
                "max": 0,
                "oom": 0,
                "oom_kill": 0,
            },
        },
        "authority": authority,
        "limitations": contract["limitations"],
        "next_gate": contract["decision_rule"]["next_gate"],
        "terminal_receipt": {
            "path": "terminal-receipt.json",
            "bytes": 1,
            "sha256": ZERO_SHA256,
        },
        "launcher_receipt": {
            "path": "launcher-receipt.json",
            "bytes": 1,
            "sha256": ZERO_SHA256,
        },
    }


class FreshConsumerD18CRunnerTests(unittest.TestCase):
    def assert_runner_error(self, code, callable_, *args):
        with self.assertRaises(RUNNER.RunnerError) as caught:
            callable_(*args)
        self.assertEqual(caught.exception.code, code)

    def test_contract_schema_extra_key_and_bool_as_int_fail_closed(self):
        contract = _contract_fixture()
        RUNNER._validate_contract(contract)

        mutations = []
        schema = copy.deepcopy(contract)
        schema["schema_version"] = 2
        mutations.append(schema)
        extra = copy.deepcopy(contract)
        extra["unexpected"] = False
        mutations.append(extra)
        bool_as_int = copy.deepcopy(contract)
        bool_as_int["execution_authorization"][
            "bounded_preflight_execution_authorized"
        ] = 1
        mutations.append(bool_as_int)
        launcher_path = copy.deepcopy(contract)
        launcher_path["implementation"]["launcher"]["path"] = "../launcher.py"
        mutations.append(launcher_path)

        for mutation in mutations:
            with self.subTest(keys=sorted(mutation)):
                self.assert_runner_error(
                    "CONTRACT_SCHEMA", RUNNER._validate_contract, mutation
                )

    def test_legacy_d18_float_is_opaque_and_authority_lineage_verifies(self):
        with tempfile.TemporaryDirectory() as temporary:
            legacy = Path(temporary) / "legacy-d18.json"
            raw = b'{"elapsed_seconds":66.543,"status":"fixture"}'
            legacy.write_bytes(raw)
            observed = RUNNER._load_legacy_d18_observation(
                legacy, hashlib.sha256(raw).hexdigest()
            )
            self.assertEqual(observed["elapsed_seconds"], "66.543")
            self.assert_runner_error(
                "SOURCE_AUTHORITY",
                RUNNER._load_legacy_d18_observation,
                legacy,
                ZERO_SHA256,
            )
            raw = b'{"value":NaN}'
            legacy.write_bytes(raw)
            self.assert_runner_error(
                "JSON_NONFINITE",
                RUNNER._load_legacy_d18_observation,
                legacy,
                hashlib.sha256(raw).hexdigest(),
            )
            raw = b'{"value":1,"value":2}'
            legacy.write_bytes(raw)
            self.assert_runner_error(
                "JSON_DUPLICATE_KEY",
                RUNNER._load_legacy_d18_observation,
                legacy,
                hashlib.sha256(raw).hexdigest(),
            )

        authority = RUNNER._verify_authority_documents(_contract_fixture())
        self.assertTrue(authority["packed_c3_ancestor"])
        self.assertTrue(authority["d18_result_ancestor"])
        self.assertFalse(authority["d18_diagnostic_execution_authority_admitted"])

    def test_kernel_context_uses_only_four_frozen_snapshots_without_action(self):
        contract = _contract_fixture()
        snapshots, custody = RUNNER._snapshot_kernel_sources(contract)
        expected_paths = tuple(
            pin["path"] for pin in RUNNER.EXPECTED_KERNEL_SOURCE_PINS
        )
        self.assertEqual(tuple(snapshots), expected_paths)
        self.assertEqual(
            tuple(item["path"] for item in custody["artifacts"]), expected_paths
        )
        self.assertEqual(len(snapshots), 4)

        original_compile = RUNNER._compile_snapshot_module
        calls = []
        d5_action = None
        backend_certificate = None

        def compile_guard(name, path, raw):
            nonlocal d5_action, backend_certificate
            calls.append(path.name)
            module = original_compile(name, path, raw)
            if path.name == RUNNER.D5_NAME:
                d5_action = mock.Mock(
                    side_effect=AssertionError("scientific action was reached")
                )
                module._reduced_column = d5_action
            elif path.name == RUNNER.BACKEND_NAME:
                backend_certificate = mock.Mock(
                    side_effect=AssertionError(
                        "backend certificate loaded transitive worktree dependencies"
                    )
                )
                module.verify_certificate = backend_certificate
            return module

        def unexpected_read(*args, **kwargs):
            raise AssertionError(
                f"kernel context performed an extra worktree read: {args!r}"
            )

        with (
            mock.patch.object(
                RUNNER, "_compile_snapshot_module", side_effect=compile_guard
            ),
            mock.patch.object(Path, "open", side_effect=unexpected_read),
            mock.patch.object(Path, "read_bytes", side_effect=unexpected_read),
            mock.patch.object(Path, "read_text", side_effect=unexpected_read),
            mock.patch.object(builtins, "open", side_effect=unexpected_read),
        ):
            d5, context = RUNNER._kernel_context(snapshots)

        self.assertEqual(
            calls, [RUNNER.D5_NAME, RUNNER.D4_NAME, RUNNER.BACKEND_NAME]
        )
        self.assertIs(d5._reduced_column, d5_action)
        d5_action.assert_not_called()
        backend_certificate.assert_not_called()
        self.assertEqual(set(context[2]), {"H1", "H2", "H3", "H4"})
        self.assertEqual(len(context[3]), 8)

    def test_existing_regular_and_symlink_scratch_fail_before_action(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            contract = {
                "consumer_protocol": {
                    "allowed_scratch_parent": str(parent),
                    "deny_filesystem_types": ["ramfs", "tmpfs"],
                }
            }
            existing = parent / "existing"
            existing.mkdir()
            regular = parent / "regular"
            regular.write_bytes(b"not a directory")
            symlink = parent / "symlink"
            symlink.symlink_to(parent / "missing-target")

            for path in (existing, regular, symlink):
                with self.subTest(path=path.name):
                    with mock.patch.object(
                        RUNNER,
                        "_filesystem_type",
                        side_effect=AssertionError("scratch type probe reached"),
                    ):
                        self.assert_runner_error(
                            "SCRATCH_CUSTODY",
                            RUNNER._prepare_scratch,
                            path,
                            contract,
                        )

    def test_fresh_scratch_establishes_real_exclusive_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            scratch = parent / "fh-l8-d18c-fixture"
            contract = {
                "consumer_protocol": {
                    "allowed_scratch_parent": str(parent),
                    "deny_filesystem_types": ["ramfs", "tmpfs"],
                }
            }
            with mock.patch.object(
                RUNNER, "_filesystem_type", return_value="ext4"
            ):
                lock_fd, custody = RUNNER._prepare_scratch(scratch, contract)
            try:
                self.assertTrue(scratch.is_dir())
                self.assertEqual(custody["scratch_root_mode"], 0o700)
                self.assertEqual(custody["exclusive_lock_mode"], 0o600)
                self.assertEqual(
                    (scratch / "exclusive.lock").stat().st_ino,
                    custody["exclusive_lock_inode"],
                )
            finally:
                RUNNER.fcntl.flock(lock_fd, RUNNER.fcntl.LOCK_UN)
                RUNNER.os.close(lock_fd)

    def test_source_content_mutation_is_rejected_without_kernel(self):
        first, second = _source_payload()
        original = first + second
        mutated_first = RUNNER.SOURCE_RECORD.pack(
            int.from_bytes(first[:16], "big").to_bytes(16, "big"),
            2,
            8,
            0,
            0,
            0,
        )
        mutated = mutated_first + second
        with tempfile.TemporaryDirectory() as temporary:
            source_path = Path(temporary) / "checkpoint.bin"
            source_path.write_bytes(mutated)
            packed = {
                "path": RUNNER.SOURCE_NAME,
                "mode": "100644",
                "blob": ZERO_SHA1,
                "bytes": len(original),
                "sha256": hashlib.sha256(original).hexdigest(),
            }
            contract = {
                "source_authority": {
                    "packed_c3_commit": ZERO_SHA1,
                    "packed_checkpoint": packed,
                    "first_4096_raw_sha256": hashlib.sha256(first).hexdigest(),
                }
            }
            with (
                mock.patch.object(RUNNER, "SOURCE_PATH", source_path),
                mock.patch.object(RUNNER, "SOURCE_RECORDS", 2),
                mock.patch.object(RUNNER, "BOUNDED_ROWS", 1),
                mock.patch.object(
                    RUNNER,
                    "_git_blob",
                    return_value={
                        "mode": packed["mode"],
                        "blob": packed["blob"],
                        "bytes": packed["bytes"],
                    },
                ),
            ):
                self.assert_runner_error(
                    "SOURCE_IDENTITY", RUNNER._admit_source, contract
                )

    def test_4097_and_duplicate_source_rows_are_rejected_pre_kernel(self):
        d5 = types.SimpleNamespace(
            _reduced_column=mock.Mock(
                side_effect=AssertionError("scientific kernel was reached")
            )
        )
        context = (None, None, None, None)
        contract = {"resource_limits": {"max_spill_bytes": 1}}
        cases = (
            [(index, 1) for index in range(RUNNER.BOUNDED_ROWS + 1)],
            [(1, 1)] * RUNNER.BOUNDED_ROWS,
        )
        for sources in cases:
            with self.subTest(source_rows=len(sources)):
                self.assert_runner_error(
                    "ACTION_BUDGET",
                    RUNNER._spill,
                    contract,
                    Path("/not-created"),
                    sources,
                    d5,
                    context,
                    float("inf"),
                    _empty_state(),
                )
        d5._reduced_column.assert_not_called()

    def test_manifest_traversal_and_extra_partition_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            spool = Path(temporary)
            contract = {
                "source_authority": {"first_4096_raw_sha256": ZERO_SHA256},
                "resource_limits": {"max_spill_bytes": 1_024},
            }
            with mock.patch.object(RUNNER, "PARTITIONS", 2):
                for index in range(2):
                    (spool / f"p{index:03d}.bin").write_bytes(b"")

                missing = _spill_manifest(2)
                missing["partition_count"] = 2
                (spool / "p001.bin").unlink()
                (spool / "manifest.json").write_bytes(
                    RUNNER._canonical_json(missing)
                )
                self.assert_runner_error(
                    "MANIFEST_CUSTODY",
                    RUNNER._load_spill_manifest,
                    contract,
                    spool,
                )
                (spool / "p001.bin").write_bytes(b"")

                traversal = _spill_manifest(2)
                traversal["partition_count"] = 2
                traversal["partitions"][0]["path"] = "../p000.bin"
                (spool / "manifest.json").write_bytes(
                    RUNNER._canonical_json(traversal)
                )
                self.assert_runner_error(
                    "MANIFEST_CUSTODY",
                    RUNNER._load_spill_manifest,
                    contract,
                    spool,
                )

                extra_partition = _spill_manifest(2)
                extra_partition["partition_count"] = 2
                extra_partition["partitions"].append(
                    {
                        "partition": 2,
                        "path": "p002.bin",
                        "records": 0,
                        "bytes": 0,
                        "sha256": hashlib.sha256(b"").hexdigest(),
                    }
                )
                (spool / "manifest.json").write_bytes(
                    RUNNER._canonical_json(extra_partition)
                )
                self.assert_runner_error(
                    "MANIFEST_CUSTODY",
                    RUNNER._load_spill_manifest,
                    contract,
                    spool,
                )

    def test_cgroup_events_and_resource_caps_fail_closed(self):
        limits = _contract_fixture()["resource_limits"]
        before = {
            "pid": 11,
            "path": "/user.slice/ab-fh-l8-d18c.scope",
            "inode": 22,
            "memory_current_bytes": 32,
            "memory_peak_bytes": 64,
            "memory_max": limits["memory_max"],
            "memory_high": limits["memory_high"],
            "memory_swap_current_bytes": 0,
            "memory_swap_max": limits["memory_swap_max"],
            "memory_events": {"high": 0, "max": 0, "oom": 0, "oom_kill": 0},
        }
        RUNNER._validate_initial_cgroup(before, limits)

        event_after = copy.deepcopy(before)
        event_after["memory_events"]["high"] = 1
        self.assert_runner_error(
            "RESOURCE_NO_GO", RUNNER._resource_delta, before, event_after, limits
        )

        peak_after = copy.deepcopy(before)
        peak_after["memory_peak_bytes"] = limits["max_final_memory_peak_bytes"] + 1
        with mock.patch.object(
            RUNNER.resource,
            "getrusage",
            return_value=types.SimpleNamespace(ru_maxrss=0),
        ):
            self.assert_runner_error(
                "RESOURCE_NO_GO", RUNNER._resource_delta, before, peak_after, limits
            )

        identity_after = copy.deepcopy(before)
        identity_after["inode"] += 1
        self.assert_runner_error(
            "CGROUP_ENVELOPE",
            RUNNER._resource_delta,
            before,
            identity_after,
            limits,
        )

    def test_atomic_publication_never_replaces_existing_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "terminal-receipt.json"
            target.write_bytes(b"original")
            self.assert_runner_error(
                "PUBLICATION_COLLISION",
                RUNNER._atomic_publish,
                target,
                b"replacement",
                64,
            )
            self.assertEqual(target.read_bytes(), b"original")


class FreshConsumerD18CLauncherTests(unittest.TestCase):
    def test_launcher_source_is_bound_and_invalid_unit_is_pre_subprocess(self):
        evidence = CHECKER.verify_implementation_source(
            contract_must_be_absent=False,
            result_must_be_absent=False,
        )
        self.assertEqual(
            evidence["launcher_sha256"],
            hashlib.sha256(LAUNCHER_PATH.read_bytes()).hexdigest(),
        )
        with mock.patch.object(
            LAUNCHER.subprocess,
            "run",
            side_effect=AssertionError("launcher subprocess was reached"),
        ) as run:
            with self.assertRaises(LAUNCHER.LauncherError):
                LAUNCHER.launch("INVALID/UNIT", Path("/not-created"))
            run.assert_not_called()

    def test_launcher_atomic_publication_never_replaces_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "launcher-receipt.json"
            target.write_bytes(b"original")
            with self.assertRaises(LAUNCHER.LauncherError):
                LAUNCHER._atomic_publish(target, b"replacement")
            self.assertEqual(target.read_bytes(), b"original")

    def test_final_receipt_has_no_post_publication_reread(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "launcher-receipt.json"
            payload = b'{"status":"fixture"}\n'
            staging, identity = LAUNCHER._prepare_final_publication(
                target, payload
            )
            original_read_bytes = Path.read_bytes

            def guarded_read_bytes(path):
                if path == target:
                    raise AssertionError("final receipt was reread after publication")
                return original_read_bytes(path)

            with mock.patch.object(Path, "read_bytes", guarded_read_bytes):
                LAUNCHER._publish_prepared_final(target, staging)
            self.assertEqual(original_read_bytes(target), payload)
            self.assertEqual(identity["bytes"], len(payload))
            self.assertEqual(identity["sha256"], hashlib.sha256(payload).hexdigest())

    def test_final_receipt_fsync_failure_removes_visible_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "launcher-receipt.json"
            staging, _ = LAUNCHER._prepare_final_publication(
                target, b'{"status":"fixture"}\n'
            )
            with (
                mock.patch.object(
                    LAUNCHER,
                    "_fsync_dir",
                    side_effect=OSError("injected directory fsync failure"),
                ),
                self.assertRaises(OSError),
            ):
                LAUNCHER._publish_prepared_final(target, staging)
            self.assertFalse(target.exists())


class FreshConsumerD18CCheckerTests(unittest.TestCase):
    def test_c1_implementation_state_has_no_contract_result_or_action(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(
                CHECKER, "CONTRACT_PATH", Path(temporary) / "missing-contract.json"
            ),
            mock.patch.object(
                CHECKER, "RESULT_PATH", Path(temporary) / "missing-result.json"
            ),
        ):
            evidence = CHECKER.verify_implementation_source()
        self.assertEqual(
            evidence["status"], "VERIFIED_D18C_ZERO_ACTION_IMPLEMENTATION_SOURCE"
        )
        self.assertTrue(evidence["verified"])
        self.assertEqual(evidence["scientific_action_calls"], 0)
        self.assertEqual(evidence["q3_rows_acted"], 0)
        self.assertFalse(evidence["action_started"])
        self.assertFalse(evidence["contract_present"])
        self.assertFalse(evidence["result_present"])
        self.assertEqual(
            evidence["launcher_sha256"],
            hashlib.sha256(LAUNCHER_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            evidence["test_sha256"],
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        )

    def test_checker_rejects_duplicate_nonfinite_and_float_json(self):
        for raw in (
            b'{"value":1,"value":2}',
            b'{"value":NaN}',
            b'{"value":1.25}',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(CHECKER.VerificationError):
                    CHECKER._load_json_bytes(raw)

    def test_result_schema_extra_bool_source_and_authority_mutations_fail(self):
        contract = _contract_fixture()
        result = _result_fixture(contract)
        CHECKER._verify_result_schema(contract, result)

        mutations = []
        extra = copy.deepcopy(result)
        extra["unexpected"] = False
        mutations.append(extra)
        bool_as_int = copy.deepcopy(result)
        bool_as_int["schema_version"] = True
        mutations.append(bool_as_int)
        source = copy.deepcopy(result)
        source["source"]["payload_sha256"] = "1" * 64
        mutations.append(source)
        source_projection = copy.deepcopy(result)
        source_projection["source"]["first_4096_projection_sha256"] = "1" * 64
        mutations.append(source_projection)
        source_extra = copy.deepcopy(result)
        source_extra["source"]["unexpected"] = False
        mutations.append(source_extra)
        authority = copy.deepcopy(result)
        authority["authority"]["full_q4_target_materialized"] = True
        mutations.append(authority)
        resource = copy.deepcopy(result)
        resource["resources"]["memory_event_delta"]["oom"] = 1
        mutations.append(resource)
        initial_peak = copy.deepcopy(result)
        initial_peak["resources"]["memory_peak_before_bytes"] = (
            contract["resource_limits"]["max_initial_memory_peak_bytes"] + 1
        )
        mutations.append(initial_peak)
        tmpfs = copy.deepcopy(result)
        tmpfs["scratch_custody"]["filesystem_type"] = "tmpfs"
        mutations.append(tmpfs)
        source_mode = copy.deepcopy(result)
        source_mode["source"]["source_stat"]["mode"] = 0o600
        mutations.append(source_mode)
        semantic_digest = copy.deepcopy(result)
        semantic_digest["naive_equivalence"][
            "target_sorted_semantic_sha256"
        ] = "not-a-sha256"
        mutations.append(semantic_digest)
        spill_records = copy.deepcopy(result)
        spill_records["spill"]["spill_records"] += 1
        mutations.append(spill_records)
        reduced_columns = copy.deepcopy(result)
        reduced_columns["spill"]["reduced_columns"] += 1
        mutations.append(reduced_columns)
        projected_zero = copy.deepcopy(result)
        projected_zero["spill"]["projected_zero_outputs"] += 1
        mutations.append(projected_zero)
        partition_count = copy.deepcopy(result)
        partition_count["spill"]["partition_count"] -= 1
        mutations.append(partition_count)
        source_authority = copy.deepcopy(result)
        source_authority["source_authority"][
            "d18_diagnostic_execution_authority_admitted"
        ] = True
        mutations.append(source_authority)
        launcher_path = copy.deepcopy(result)
        launcher_path["launcher_receipt"]["path"] = "../launcher-receipt.json"
        mutations.append(launcher_path)
        launcher_bool = copy.deepcopy(result)
        launcher_bool["launcher_receipt"]["bytes"] = True
        mutations.append(launcher_bool)
        launcher_extra = copy.deepcopy(result)
        launcher_extra["launcher_receipt"]["unexpected"] = False
        mutations.append(launcher_extra)

        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                with self.assertRaises(CHECKER.VerificationError):
                    CHECKER._verify_result_schema(contract, mutation)

    def test_static_result_does_not_return_execution_authority(self):
        contract = _contract_fixture()
        implementation_commit = "a" * 40
        contract_commit = "b" * 40
        result_commit = "c" * 40
        contract_blob = "d" * 40
        result_blob = "e" * 40
        contract["chronology"]["implementation_freeze_commit"] = (
            implementation_commit
        )
        result = _result_fixture(contract)
        result["contract_freeze_commit"] = contract_commit
        contract_raw = CHECKER._canonical_json(contract)
        result_raw = CHECKER._canonical_json(result)

        def git_result(*args, **kwargs):
            if args[:2] == ("status", "--porcelain=v1"):
                stdout = b""
            elif args == ("rev-parse", f"{contract_commit}^"):
                stdout = f"{implementation_commit}\n".encode()
            elif args and args[0] == "log":
                stdout = f"{result_commit}\n".encode()
            elif args == ("rev-parse", f"{result_commit}^"):
                stdout = f"{contract_commit}\n".encode()
            elif args == ("cat-file", "blob", contract_blob):
                stdout = contract_raw
            elif args == ("cat-file", "blob", result_blob):
                stdout = result_raw
            else:
                raise AssertionError(f"unexpected static-result Git query: {args!r}")
            return types.SimpleNamespace(stdout=stdout, returncode=0)

        def diff_entries(commit):
            if commit == contract_commit:
                return [f"A\t{CHECKER.REL_PREFIX}{CHECKER.CONTRACT_NAME}"]
            if commit == result_commit:
                return [f"A\t{CHECKER.REL_PREFIX}{CHECKER.RESULT_NAME}"]
            raise AssertionError(f"unexpected diff commit: {commit}")

        def git_blob(commit, relative):
            if commit == contract_commit and relative.endswith(
                CHECKER.CONTRACT_NAME
            ):
                return {
                    "mode": "100644",
                    "blob": contract_blob,
                    "bytes": len(contract_raw),
                }
            if commit == result_commit and relative.endswith(CHECKER.RESULT_NAME):
                return {
                    "mode": "100644",
                    "blob": result_blob,
                    "bytes": len(result_raw),
                }
            raise AssertionError(
                f"unexpected static-result blob query: {commit} {relative}"
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path = root / CHECKER.CONTRACT_NAME
            result_path = root / CHECKER.RESULT_NAME
            contract_path.write_bytes(contract_raw)
            result_path.write_bytes(result_raw)
            runner = types.SimpleNamespace(_validate_contract=lambda value: None)
            with (
                mock.patch.object(CHECKER, "CONTRACT_PATH", contract_path),
                mock.patch.object(CHECKER, "RESULT_PATH", result_path),
                mock.patch.object(CHECKER, "_load_runner", return_value=runner),
                mock.patch.object(CHECKER, "_git", side_effect=git_result),
                mock.patch.object(
                    CHECKER, "_diff_entries", side_effect=diff_entries
                ),
                mock.patch.object(CHECKER, "_git_blob", side_effect=git_blob),
                mock.patch.object(
                    CHECKER, "_verify_source_authority", return_value={}
                ),
                mock.patch.object(
                    CHECKER, "_verify_kernel_custody", return_value=None
                ),
            ):
                static = CHECKER.verify_result()

        self.assertTrue(static["schema_and_git_provenance_verified"])
        self.assertFalse(static["external_scratch_verified"])
        self.assertFalse(static["executed_authority_verified"])
        self.assertFalse(static["scientific_outcome_verified"])
        self.assertNotIn("verified", static)
        self.assertNotIn("authority", static)
        self.assertFalse(static.get("execution_authority_admitted", False))


if __name__ == "__main__":
    unittest.main()
