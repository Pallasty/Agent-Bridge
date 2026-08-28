from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
import pathlib
import sqlite3
import stat
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-r9-installed-receipt-restart.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_r9_installed_receipt_restart", SCRIPT
)
assert SPEC and SPEC.loader
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)
SESSION_ID = "ses-123e4567-e89b-42d3-a456-426614174001"
SPAN_ID = "agent-spawn-123e4567-e89b-42d3-a456-426614174000"


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_mode(path: pathlib.Path, payload: bytes, mode: int) -> None:
    path.write_bytes(payload)
    path.chmod(mode)


def manifest_fixture() -> dict[str, object]:
    return {
        "schema": 2,
        "receipt_id": "a" * 32,
        "span_id": SPAN_ID,
        "runtime": "claude-code",
        "unit": "agent-bridge-agent-" + "c" * 32 + ".scope",
        "nonce": "d" * 32,
    }


def spawn_payload_fixture(
    *, session_id: str = SESSION_ID, span_id: str = SPAN_ID
) -> dict[str, object]:
    return {
        "id": session_id,
        "runtime_id": "claude-code",
        "body_scheduling_event_recorded": True,
        "body_task_span": {
            "span_id": span_id,
            "state": "active",
            "completion": "agent_session_wait",
            "automatic_completion": "session_terminal_observer",
            "process_binding": {
                "status": "attached",
                "scope": "local_workload_root",
            },
        },
    }


def receipt_fixture(manifest: dict[str, object]) -> dict[str, object]:
    return {
        "schema": 2,
        "receipt_id": manifest["receipt_id"],
        "span_id": manifest["span_id"],
        "nonce": manifest["nonce"],
        "unit": manifest["unit"],
        "resources": {
            "status": "complete",
            "source": "linux_cgroup_v2_systemd_delegated_scope",
            "scope": "delegated_session_workload_tree",
            "controllers": ["cpu", "memory", "pids"],
            "cpu_usage_usec": 12,
            "cpu_user_usec": 8,
            "cpu_system_usec": 4,
            "memory_peak_bytes": 4096,
            "pids_peak": 2,
            "oom_events": 0,
            "oom_kill_events": 0,
            "populated_zero_observed": True,
            "start_before_exec": True,
            "complete_for_cpu_memory_workload_tree": True,
            "complete_for_pids_workload_tree": True,
            "generation_count": 1,
            "captured_generation_count": 1,
        },
    }


def task_terminal_resources_fixture() -> dict[str, object]:
    return {
        "schema_version": "agent_bridge.task_terminal_resources.v0",
        "accounting_status": "complete",
        "source": "linux_raw_waitid_wnowait_rusage",
        "scope": "waited_child_generations",
        "descendant_coverage": "not_proven",
        "workload_lifetime_covered": False,
        "spawned_attempt_count": 1,
        "captured_attempt_count": 1,
        "known_user_cpu_us": 3,
        "known_system_cpu_us": 2,
        "known_peak_resident_bytes": 8192,
        "complete_for_spawned_attempts": True,
        "complete_for_workload_tree": False,
        "terminal_condition": "all_spawned_children_observed_before_reap",
        "peak_resident_semantics": (
            "max_ru_maxrss_across_attempts_not_concurrent_tree_peak"
        ),
    }


def task_workload_resources_fixture(
    manifest: dict[str, object], receipt: dict[str, object], receipt_sha: str
) -> dict[str, object]:
    resources = receipt["resources"]
    assert isinstance(resources, dict)
    return {
        "schema_version": "agent_bridge.task_workload_resources.v1",
        "accounting_status": resources["status"],
        "source": resources["source"],
        "scope": resources["scope"],
        "controllers": resources["controllers"],
        "workload_lifetime_covered": resources["populated_zero_observed"],
        "generation_count": resources["generation_count"],
        "captured_generation_count": resources["captured_generation_count"],
        "known_total_cpu_us": resources["cpu_usage_usec"],
        "known_user_cpu_us": resources["cpu_user_usec"],
        "known_system_cpu_us": resources["cpu_system_usec"],
        "known_peak_memory_bytes": resources["memory_peak_bytes"],
        "known_peak_pids": resources["pids_peak"],
        "known_oom_event_count": resources["oom_events"],
        "known_oom_kill_count": resources["oom_kill_events"],
        "start_before_exec": True,
        "final_populated_zero": True,
        "complete_for_cpu_memory_workload_tree": True,
        "complete_for_pids_workload_tree": True,
        "durable_receipts": [
            {"receipt_id": manifest["receipt_id"], "sha256": receipt_sha}
        ],
        "io_accounting_status": "unknown_not_delegated",
        "terminal_condition": "all_generations_populated_zero",
        "failure_reason": None,
        "trust_boundary": "same_uid_non_adversarial_cgroup_membership",
    }


def task_span_facts_fixture(
    manifest: dict[str, object], receipt: dict[str, object], receipt_sha: str
) -> dict[str, object]:
    return {
        "schema_version": "agent_bridge.task_resource_span.v4",
        "span_id": manifest["span_id"],
        "task_kind": "agent_spawn",
        "state": "closed",
        "started_at_unix_ms": 100_000,
        "ended_at_unix_ms": 100_050,
        "duration_ms": 50,
        "checkpoint_count": 0,
        "sampling_gaps": 0,
        "before_pressure": "nominal",
        "after_pressure": "nominal",
        "memory_available_delta_bytes": 1024,
        "storage_available_delta_bytes": -2048,
        "process_resident_delta_bytes": 4096,
        "task_process_scope": "best_effort_linux_same_user_process_tree",
        "task_process_capture_complete": False,
        "task_process_count_before": 1,
        "task_process_count_after": None,
        "task_process_resident_delta_bytes": None,
        "task_process_sampling_gaps": 1,
        "task_process_binding_status": "attached",
        "task_process_binding_reason": None,
        "task_process_baseline_phase": "post_spawn",
        "task_process_whole_task_prefix_covered": False,
        "task_process_terminal_status": "root_unavailable",
        "task_process_endpoint_semantics": "procfs_sample_attempt_at_finish",
        "task_terminal_resources": task_terminal_resources_fixture(),
        "task_workload_resources": task_workload_resources_fixture(
            manifest, receipt, receipt_sha
        ),
        "abandonment_reason": None,
    }


def scheduling_advice_fixture() -> dict[str, object]:
    return {
        "schema_version": "agent_bridge.body_scheduling_advice.v0",
        "mode": "shadow_only",
        "read_only": True,
        "blocked": False,
        "execution_changed": False,
        "changes_routing": False,
        "changes_parallelism": False,
        "pressure": "nominal",
        "workload_class": "heavy",
        "requested_parallelism": 1,
        "suggested_max_parallelism": 1,
        "recommendation": "start_as_requested",
    }


def event_descriptor_fixture(
    *, object_type: str, label: str, object_id: object, expected_effect: str
) -> dict[str, object]:
    return {
        "object": {
            "object_type": object_type,
            "source_adapter": "body_telemetry",
            "label": label,
            "object_id": object_id,
        },
        "affordance": {
            "action_type": "observe",
            "risk_level": "low",
            "requires_gate": False,
            "expected_effect": expected_effect,
        },
    }


def create_receipt_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE workload_receipt_commits (
            schema_version TEXT NOT NULL,
            receipt_id TEXT PRIMARY KEY,
            span_id TEXT NOT NULL,
            recorded_at INTEGER NOT NULL,
            receipt_sha256 TEXT NOT NULL,
            commit_kind TEXT NOT NULL,
            redacted_facts_json TEXT NOT NULL,
            record_sha256 TEXT NOT NULL
        );
        CREATE TABLE semantic_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            actor TEXT NOT NULL,
            source TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT,
            verdict_status TEXT NOT NULL,
            verdict_method TEXT NOT NULL,
            evidence TEXT,
            facts TEXT NOT NULL,
            descriptor TEXT
        );
        """
    )


def insert_live_snapshot(
    connection: sqlite3.Connection,
    manifest: dict[str, object],
    receipt_sha: str,
    receipt: dict[str, object] | None = None,
    session_id: str = SESSION_ID,
) -> None:
    receipt = receipt or receipt_fixture(manifest)
    facts = task_span_facts_fixture(manifest, receipt, receipt_sha)
    facts_json = json.dumps(facts, sort_keys=True, separators=(",", ":"))
    claim = {
        "schema_version": "agent_bridge.workload_receipt_commit.v1",
        "receipt_id": manifest["receipt_id"],
        "span_id": manifest["span_id"],
        "recorded_at": 100,
        "receipt_sha256": receipt_sha,
        "commit_kind": "live_body_span",
        "redacted_facts": facts,
    }
    record_sha = "sha256:" + digest(
        json.dumps(claim, sort_keys=True, separators=(",", ":")).encode()
    )
    connection.execute(
        """
        INSERT INTO workload_receipt_commits VALUES
          (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "agent_bridge.workload_receipt_commit.v1",
            manifest["receipt_id"],
            manifest["span_id"],
            100,
            receipt_sha,
            "live_body_span",
            facts_json,
            record_sha,
        ),
    )
    connection.execute(
        """
        INSERT INTO semantic_events
          (ts, actor, source, action, target, verdict_status, verdict_method,
           evidence, facts, descriptor)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            99,
            "mcp",
            "body_telemetry",
            "scheduling_advice_observed",
            manifest["span_id"],
            "unknown",
            "shadow_advice_has_no_causal_outcome_claim",
            json.dumps(
                {
                    "advice_computed": True,
                    "causal_quality_evaluable": False,
                    "execution_changed": False,
                },
                separators=(",", ":"),
            ),
            json.dumps(
                {
                    "schema_version": "agent_bridge.body_scheduling_advice.v0",
                    "session_id": session_id,
                    "runtime_id": "claude-code",
                    "span_id": manifest["span_id"],
                    "advice": scheduling_advice_fixture(),
                },
                separators=(",", ":"),
            ),
            json.dumps(
                event_descriptor_fixture(
                    object_type="body_scheduling_advice",
                    label="heavy",
                    object_id=manifest["span_id"],
                    expected_effect=(
                        "record a compact shadow scheduling recommendation for later evaluation"
                    ),
                ),
                separators=(",", ":"),
            ),
        ),
    )
    connection.execute(
        """
        INSERT INTO semantic_events
          (ts, actor, source, action, target, verdict_status, verdict_method,
           evidence, facts, descriptor)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            100,
            "mcp",
            "body_telemetry",
            "task_span_closed",
            manifest["span_id"],
            "verified",
            "before_after_body_observation_with_delegated_cpu_memory_workload_tree",
            json.dumps(
                {
                    "before_present": True,
                    "after_present": True,
                    "checkpoint_count": 0,
                    "sampling_gaps": 0,
                    "workload_cpu_memory_tree_complete": True,
                    "durable_receipt_count": 1,
                    "durable_commit_required": True,
                },
                separators=(",", ":"),
            ),
            facts_json,
            json.dumps(
                event_descriptor_fixture(
                    object_type="task_resource_span",
                    label="agent_spawn",
                    object_id=manifest["span_id"],
                    expected_effect="record a bounded task resource-span receipt",
                ),
                separators=(",", ":"),
            ),
        ),
    )
    connection.commit()


class SourceAndCopyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.payload = (
            b"#!/bin/sh\n# agent_bridge.workload_receipt_commit.v1\nexit 0\n"
        )
        self.source = self.root / "agent-bridge.real"
        write_mode(self.source, self.payload, 0o777)
        self.expected = digest(self.payload)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_source_owner_and_writable_mode_are_observations(self) -> None:
        inspected = HARNESS.inspect_source_binary(str(self.source), self.expected)
        self.assertTrue(inspected["group_or_other_writable"])
        current_uid = os.geteuid()
        with mock.patch.object(HARNESS.os, "geteuid", return_value=current_uid + 1):
            inspected = HARNESS.inspect_source_binary(str(self.source), self.expected)
        self.assertFalse(inspected["owner_is_current_user"])

    def test_source_rejects_relative_symlink_and_digest_mismatch(self) -> None:
        with self.assertRaisesRegex(HARNESS.HarnessError, "absolute"):
            HARNESS.inspect_source_binary("agent-bridge.real", self.expected)
        link = self.root / "linked"
        link.symlink_to(self.source)
        with self.assertRaisesRegex(HARNESS.HarnessError, "physical"):
            HARNESS.inspect_source_binary(str(link), self.expected)
        with self.assertRaisesRegex(HARNESS.HarnessError, "digest"):
            HARNESS.inspect_source_binary(str(self.source), "f" * 64)

    def test_source_rejects_absent_r9_marker_and_finds_cross_chunk_marker(self) -> None:
        absent = self.root / "old-agent-bridge.real"
        write_mode(absent, b"old binary without the schema discriminator", 0o755)
        with self.assertRaisesRegex(HARNESS.HarnessError, "R9 schema marker"):
            HARNESS.inspect_source_binary(str(absent), digest(absent.read_bytes()))

        boundary = self.root / "boundary-agent-bridge.real"
        marker = HARNESS.R9_LEDGER_SCHEMA_MARKER
        boundary_payload = b"x" * (1024 * 1024 - 7) + marker + b"tail"
        write_mode(boundary, boundary_payload, 0o755)
        inspected = HARNESS.inspect_source_binary(
            str(boundary), digest(boundary_payload)
        )
        self.assertTrue(inspected["marker_present"])

    def test_private_copy_is_exact_owner_bound_0700_and_revalidated(self) -> None:
        destination = self.root / "copy"
        fingerprint = HARNESS.copy_pinned_binary(
            self.source, destination, self.expected
        )
        self.assertEqual(destination.read_bytes(), self.payload)
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o700)
        HARNESS.validate_trial_binary(destination, self.expected, fingerprint)
        destination.write_bytes(self.payload + b"tamper")
        destination.chmod(0o700)
        with self.assertRaises(HARNESS.HarnessError):
            HARNESS.validate_trial_binary(destination, self.expected, fingerprint)


class GateAndEnvironmentTests(unittest.TestCase):
    def test_spawn_identities_require_canonical_lowercase_uuid_v4(self) -> None:
        self.assertEqual(
            HARNESS._validate_spawn_payload(spawn_payload_fixture()),
            (SESSION_ID, SPAN_ID),
        )
        invalid_sessions = (
            "ses-/private/session",
            "ses-123e4567-e89b-12d3-a456-426614174001",
            "ses-123e4567-e89b-42d3-7456-426614174001",
            "ses-123E4567-E89B-42D3-A456-426614174001",
        )
        for session_id in invalid_sessions:
            with self.subTest(session_id=session_id):
                with self.assertRaises(HARNESS.HarnessError):
                    HARNESS._validate_spawn_payload(
                        spawn_payload_fixture(session_id=session_id)
                    )
        invalid_spans = (
            "agent-spawn-/private/span",
            "agent-spawn-" + "b" * 32,
            "agent-spawn-123e4567-e89b-12d3-a456-426614174000",
            "agent-spawn-123E4567-E89B-42D3-A456-426614174000",
        )
        for span_id in invalid_spans:
            with self.subTest(span_id=span_id):
                with self.assertRaises(HARNESS.HarnessError):
                    HARNESS._validate_spawn_payload(
                        spawn_payload_fixture(span_id=span_id)
                    )

    def test_default_and_bad_confirmation_never_call_execute(self) -> None:
        ready = {"public": {"ready": True}}
        argv = ["--binary", "/physical", "--expected-sha256", "a" * 64]
        with mock.patch.object(HARNESS, "build_preflight", return_value=ready), mock.patch.object(
            HARNESS, "execute_acceptance"
        ) as execute:
            status, packet = HARNESS.run(argv)
            self.assertEqual(status, 0)
            self.assertEqual(packet["verdict"], "PREFLIGHT_READY")
            self.assertFalse(packet["executed"])
            execute.assert_not_called()

            status, packet = HARNESS.run(
                argv + ["--execute-r9-installed-restart", "almost"]
            )
            self.assertEqual(status, 2)
            self.assertFalse(packet["executed"])
            self.assertEqual(packet["error"]["code"], "execution_confirmation_rejected")
            execute.assert_not_called()

    def test_exact_confirmation_is_the_only_execute_route(self) -> None:
        ready = {"public": {"ready": True}}
        accepted = {"crash_point": HARNESS.CRASH_POINT}
        argv = [
            "--binary",
            "/physical",
            "--expected-sha256",
            "a" * 64,
            "--execute-r9-installed-restart",
            HARNESS.EXECUTION_CONFIRMATION,
        ]
        with mock.patch.object(HARNESS, "build_preflight", return_value=ready), mock.patch.object(
            HARNESS, "execute_acceptance", return_value=accepted
        ) as execute:
            status, packet = HARNESS.run(argv)
        self.assertEqual(status, 0)
        self.assertTrue(packet["executed"])
        self.assertEqual(packet["acceptance"]["crash_point"], HARNESS.CRASH_POINT)
        execute.assert_called_once()

    def test_environment_is_fixed_allowlist_without_ambient_secret_or_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            runtime = root / "runtime"
            runtime.mkdir(mode=0o700)
            preflight = {
                "runtime_dir": runtime,
                "bus_path": runtime / "bus",
            }
            with mock.patch.dict(
                os.environ,
                {
                    "AWS_SECRET_ACCESS_KEY": "secret",
                    "AGENT_BRIDGE_WORKLOAD_RECEIPT_BINDING": "forged",
                },
                clear=False,
            ):
                env = HARNESS.build_isolated_environment(root, preflight, 90)
            self.assertEqual(set(env), HARNESS.MCP_ENV_KEYS)
            self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
            self.assertNotIn("AGENT_BRIDGE_WORKLOAD_RECEIPT_BINDING", env)
            self.assertEqual(env["AGENT_BRIDGE_CGROUP_CUSTODY"], "on")
            self.assertEqual(env["AGENT_BRIDGE_CLAUDE_BIN"], "/bin/sh")
            self.assertEqual(env["AB_ALLOW_AGENT_SPAWN"], "true")
            self.assertEqual(env["AB_ALLOW_SHELL_EXEC"], "false")
            for name in ("home", "tmp", "xdg-data", "xdg-config", "xdg-cache", "xdg-state", "workspace", "spool"):
                self.assertEqual(stat.S_IMODE((root / name).stat().st_mode), 0o700)


class ReceiptProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.spool = self.root / "spool"
        self.spool.mkdir(mode=0o700)
        self.manifest = manifest_fixture()
        write_mode(self.spool / ".spool.lock", b"", 0o600)
        self.entry = self.spool / ("receipt-" + str(self.manifest["receipt_id"]))
        self.entry.mkdir(mode=0o700)
        write_mode(self.entry / "producer.lock", b"", 0o600)
        write_mode(
            self.entry / "manifest.json",
            json.dumps(self.manifest, separators=(",", ":")).encode() + b"\n",
            0o600,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_manifest_then_0500_fault_then_terminal_receipt(self) -> None:
        entry, parsed = HARNESS.find_and_validate_manifest(
            self.spool, str(self.manifest["span_id"])
        )
        self.assertEqual(entry, self.entry)
        self.assertEqual(parsed, self.manifest)
        HARNESS.set_spool_mode(self.spool, 0o500)
        self.assertEqual(stat.S_IMODE(self.spool.stat().st_mode), 0o500)
        receipt = receipt_fixture(self.manifest)
        raw = json.dumps(receipt, separators=(",", ":")).encode() + b"\n"
        write_mode(self.entry / "receipt.json", raw, 0o600)
        parsed_receipt, receipt_sha = HARNESS.wait_for_receipt(
            self.entry, self.manifest, HARNESS.Deadline(1)
        )
        self.assertEqual(parsed_receipt, receipt)
        self.assertEqual(receipt_sha, "sha256:" + digest(raw))
        HARNESS.set_spool_mode(self.spool, 0o700)

    def test_manifest_rejects_span_mismatch_and_duplicate_json_keys(self) -> None:
        with self.assertRaises(HARNESS.HarnessError):
            HARNESS.find_and_validate_manifest(
                self.spool, "agent-spawn-" + "e" * 32
            )
        with self.assertRaises(ValueError):
            HARNESS.strict_json_loads('{"a":1,"a":2}')

    def test_manifest_rejects_non_uuid_scope_unit(self) -> None:
        self.manifest["unit"] = "agent-bridge-agent-production.scope"
        write_mode(
            self.entry / "manifest.json",
            json.dumps(self.manifest, separators=(",", ":")).encode() + b"\n",
            0o600,
        )
        with self.assertRaisesRegex(HARNESS.HarnessError, "binding"):
            HARNESS.find_and_validate_manifest(
                self.spool, str(self.manifest["span_id"])
            )

    def test_receipt_rejects_bool_counter_and_unknown_resource_key(self) -> None:
        for mutate in (
            lambda resources: resources.__setitem__("generation_count", True),
            lambda resources: resources.__setitem__("cgroup_path", "/private"),
        ):
            receipt = receipt_fixture(self.manifest)
            resources = receipt["resources"]
            assert isinstance(resources, dict)
            mutate(resources)
            with self.assertRaises(HARNESS.HarnessError):
                HARNESS.validate_terminal_workload_receipt(receipt, self.manifest)

    def test_receipt_rejects_free_form_incomplete_reason_values(self) -> None:
        receipt = receipt_fixture(self.manifest)
        resources = receipt["resources"]
        assert isinstance(resources, dict)
        resources["incomplete_reasons"] = [
            "prompt copied from /private/session with pid 123"
        ]
        with self.assertRaisesRegex(HARNESS.HarnessError, "complete"):
            HARNESS.validate_terminal_workload_receipt(receipt, self.manifest)

    def test_producer_lock_must_be_released(self) -> None:
        lock = self.entry / "producer.lock"
        fd = os.open(lock, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(HARNESS.HarnessError, "still held"):
                HARNESS.assert_producer_lock_released(self.entry)
            fcntl.flock(fd, fcntl.LOCK_UN)
            HARNESS.assert_producer_lock_released(self.entry)
        finally:
            os.close(fd)


class StandinExecutionTests(unittest.TestCase):
    def test_attempt_ledger_counts_entry_and_first_marker_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            script = root / "standin.sh"
            attempts = root / "standin.attempts"
            started = root / "standin.started"
            release = root / "standin.release"
            HARNESS.create_standin_script(script)
            write_mode(attempts, b"", 0o600)
            write_mode(release, b"release\n", 0o600)
            env = {
                "PATH": "/usr/bin:/bin",
                "AB_R9_ATTEMPTS_FILE": str(attempts),
                "AB_R9_STARTED_FILE": str(started),
                "AB_R9_RELEASE_FILE": str(release),
            }

            first = subprocess.run(
                ["/bin/sh", "-p", str(script)],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=2,
            )
            self.assertEqual(first.returncode, 0)
            HARNESS.validate_standin_execution(attempts, started)

            second = subprocess.run(
                ["/bin/sh", "-p", str(script)],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=2,
            )
            self.assertEqual(second.returncode, 91)
            self.assertEqual(
                attempts.read_bytes(), HARNESS.STANDIN_ATTEMPT_TOKEN * 2
            )
            self.assertEqual(started.read_bytes(), b"started\n")
            with self.assertRaisesRegex(HARNESS.HarnessError, "execution count"):
                HARNESS.validate_standin_execution(attempts, started)


class FinalSpoolIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.spool = self.root / "spool"
        self.spool.mkdir(mode=0o700)
        write_mode(self.spool / ".spool.lock", b"", 0o600)
        self.fingerprint = HARNESS.capture_spool_fingerprint(self.spool)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_final_empty_spool_preserves_original_private_root(self) -> None:
        HARNESS.assert_residual_spool_empty(self.spool, self.fingerprint)

    def test_final_spool_rejects_non_private_mode(self) -> None:
        self.spool.chmod(0o755)
        with self.assertRaisesRegex(HARNESS.HarnessError, "spool root"):
            HARNESS.assert_residual_spool_empty(self.spool, self.fingerprint)

    def test_final_spool_rejects_symlink_root(self) -> None:
        original = self.root / "original-spool"
        self.spool.rename(original)
        self.spool.symlink_to(original, target_is_directory=True)
        with self.assertRaisesRegex(HARNESS.HarnessError, "spool root"):
            HARNESS.assert_residual_spool_empty(self.spool, self.fingerprint)

    def test_final_spool_rejects_replacement_directory_inode(self) -> None:
        original = self.root / "original-spool"
        self.spool.rename(original)
        self.spool.mkdir(mode=0o700)
        write_mode(self.spool / ".spool.lock", b"", 0o600)
        with self.assertRaisesRegex(HARNESS.HarnessError, "spool root"):
            HARNESS.assert_residual_spool_empty(self.spool, self.fingerprint)


class ScopeCleanupProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.unit = "agent-bridge-agent-" + "c" * 32 + ".scope"
        self.systemctl = pathlib.Path("/usr/bin/systemctl")

    def test_pre_spawn_baseline_is_bounded_and_strictly_parsed(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(self.unit + " loaded active running test scope\n").encode(),
            stderr=b"",
        )
        with mock.patch.object(
            HARNESS, "_run_systemctl", return_value=completed
        ) as runner:
            baseline = HARNESS.capture_matching_scope_baseline(
                self.systemctl, {}, HARNESS.Deadline(1)
            )
        self.assertEqual(baseline, frozenset({self.unit}))
        self.assertIn("list-units", runner.call_args.args[2])

        invalid = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"agent-bridge-agent-production.scope loaded active running forged\n",
            stderr=b"",
        )
        with mock.patch.object(HARNESS, "_run_systemctl", return_value=invalid):
            with self.assertRaisesRegex(HARNESS.HarnessError, "baseline"):
                HARNESS.capture_matching_scope_baseline(
                    self.systemctl, {}, HARNESS.Deadline(1)
                )

    def test_preexisting_or_forged_manifest_unit_never_authorizes_stop(self) -> None:
        with self.assertRaisesRegex(HARNESS.HarnessError, "existed before"):
            HARNESS.claim_cleanup_scope(
                self.unit, frozenset({self.unit}), "loaded"
            )

        forged = "agent-bridge-agent-production.scope"
        with mock.patch.object(HARNESS, "_run_systemctl") as runner:
            self.assertTrue(
                HARNESS._stop_exact_scope(
                    self.systemctl,
                    {},
                    self.unit,
                    None,
                    HARNESS.Deadline(1),
                )
            )
            self.assertTrue(
                HARNESS._stop_exact_scope(
                    self.systemctl,
                    {},
                    forged,
                    forged,
                    HARNESS.Deadline(1),
                )
            )
        runner.assert_not_called()

    def test_only_new_loaded_scope_is_stopped_and_absence_is_confirmed(self) -> None:
        authority = HARNESS.claim_cleanup_scope(
            self.unit, frozenset(), "loaded"
        )
        loaded = subprocess.CompletedProcess([], 0, b"loaded\n", b"")
        stopped = subprocess.CompletedProcess([], 0, b"", b"")
        absent = subprocess.CompletedProcess([], 0, b"not-found\n", b"")
        with mock.patch.object(
            HARNESS,
            "_run_systemctl",
            side_effect=[loaded, stopped, absent],
        ) as runner:
            self.assertTrue(
                HARNESS._stop_exact_scope(
                    self.systemctl,
                    {},
                    self.unit,
                    authority,
                    HARNESS.Deadline(1),
                )
            )
        self.assertEqual(runner.call_count, 3)
        self.assertEqual(runner.call_args_list[1].args[2], ["stop", "--", self.unit])

    def test_unknown_post_baseline_scope_holds_trial_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = pathlib.Path(temp)
            root = runtime / (HARNESS.WORK_ROOT_PREFIX + "owned")
            root.mkdir(mode=0o700)
            preflight = {
                "runtime_dir": runtime,
                "runtime_dev": root.stat().st_dev,
                "systemctl": self.systemctl,
            }
            remaining = frozenset({self.unit})
            with mock.patch.object(
                HARNESS,
                "capture_matching_scope_baseline",
                return_value=remaining,
            ):
                cleaned = HARNESS.cleanup_work_root(
                    root,
                    preflight,
                    None,
                    None,
                    [],
                    {},
                    None,
                    None,
                    frozenset(),
                    False,
                )
            self.assertFalse(cleaned)
            self.assertTrue(root.exists())

    def test_proven_exact_absence_does_not_hold_for_unrelated_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = pathlib.Path(temp)
            root = runtime / (HARNESS.WORK_ROOT_PREFIX + "owned")
            root.mkdir(mode=0o700)
            preflight = {
                "runtime_dir": runtime,
                "runtime_dev": root.stat().st_dev,
                "systemctl": self.systemctl,
            }
            with mock.patch.object(
                HARNESS, "capture_matching_scope_baseline"
            ) as capture:
                cleaned = HARNESS.cleanup_work_root(
                    root,
                    preflight,
                    None,
                    None,
                    [],
                    {},
                    self.unit,
                    None,
                    frozenset(),
                    True,
                )
            self.assertTrue(cleaned)
            self.assertFalse(root.exists())
            capture.assert_not_called()


class McpClientProtocolTests(unittest.TestCase):
    def test_fake_stdio_server_exercises_initialize_tools_and_clean_eof(self) -> None:
        payload = b'''#!/usr/bin/python3
# agent_bridge.workload_receipt_commit.v1
import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    if method == "notifications/initialized":
        continue
    if method == "initialize":
        result = {"serverInfo": {"name": "agent-bridge", "version": "test"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "agent_spawn"}, {"name": "agent_session_wait"}]}
    elif method == "tools/call":
        result = {
            "content": [{"type": "text", "text": "{\\"ok\\":true}"}],
            "isError": False,
        }
        sys.stderr.write("fixed-test-marker\\n")
        sys.stderr.flush()
    else:
        result = {}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}) + "\\n")
    sys.stdout.flush()
'''
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            binary = root / "agent-bridge.real"
            write_mode(binary, payload, 0o700)
            expected = digest(payload)
            fingerprint = HARNESS.validate_trial_binary(binary, expected)
            deadline = HARNESS.Deadline(5)
            client = HARNESS.McpClient(
                binary,
                {"HOME": str(root), "PATH": "/usr/bin:/bin"},
                expected,
                fingerprint,
                deadline,
            )
            result = client.call_tool("agent_spawn", {}, deadline)
            self.assertEqual(result, {"ok": True})
            self.assertIn("fixed-test-marker", client.wait_stderr("fixed-test-marker", deadline))
            client.close_clean()
            self.assertEqual(client.stderr_marker_count("fixed-test-marker"), 1)


class DatabaseAndPrivacyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.database = self.root / "state.db"
        self.manifest = manifest_fixture()
        self.receipt = receipt_fixture(self.manifest)
        self.receipt_sha = "sha256:" + "f" * 64
        connection = sqlite3.connect(self.database)
        try:
            create_receipt_schema(connection)
            insert_live_snapshot(
                connection, self.manifest, self.receipt_sha, self.receipt
            )
        finally:
            connection.close()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def validate_snapshot(
        self, snapshot: dict[str, tuple[tuple[object, ...], ...]]
    ) -> None:
        HARNESS.validate_live_commit_snapshot(
            snapshot,
            self.manifest,
            self.receipt,
            self.receipt_sha,
            SESSION_ID,
        )

    def mutate_ledger_facts(
        self,
        snapshot: dict[str, tuple[tuple[object, ...], ...]],
        mutation: object,
    ) -> dict[str, tuple[tuple[object, ...], ...]]:
        ledger = list(snapshot["ledger"][0])
        index = HARNESS.LEDGER_COLUMNS.index("redacted_facts_json")
        facts = json.loads(ledger[index])
        assert isinstance(facts, dict)
        assert callable(mutation)
        mutation(facts)
        ledger[index] = json.dumps(facts, sort_keys=True, separators=(",", ":"))
        return {"ledger": (tuple(ledger),), "events": snapshot["events"]}

    def mutate_event_json(
        self,
        snapshot: dict[str, tuple[tuple[object, ...], ...]],
        action: str,
        column: str,
        mutation: object,
    ) -> dict[str, tuple[tuple[object, ...], ...]]:
        events = [list(row) for row in snapshot["events"]]
        action_index = HARNESS.EVENT_COLUMNS.index("action")
        column_index = HARNESS.EVENT_COLUMNS.index(column)
        row = next(row for row in events if row[action_index] == action)
        value = json.loads(row[column_index]) if row[column_index] is not None else None
        assert callable(mutation)
        replacement = mutation(value)
        row[column_index] = (
            None
            if replacement is None
            else json.dumps(replacement, separators=(",", ":"))
        )
        return {
            "ledger": snapshot["ledger"],
            "events": tuple(tuple(row) for row in events),
        }

    def test_full_sqlite_rows_validate_and_compare_byte_for_byte(self) -> None:
        before = HARNESS.read_database_snapshot(self.database)
        self.validate_snapshot(before)
        after = HARNESS.read_database_snapshot(self.database)
        self.assertEqual(before, after)
        self.assertEqual(len(before["ledger"]), 1)
        self.assertEqual(len(before["events"]), 2)

    def test_sqlite_schema_and_rows_are_read_under_explicit_begin(self) -> None:
        trace: list[str] = []
        real_connect = sqlite3.connect

        def traced_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
            connection = real_connect(*args, **kwargs)
            connection.set_trace_callback(trace.append)
            return connection

        with mock.patch.object(HARNESS.sqlite3, "connect", side_effect=traced_connect):
            HARNESS.read_database_snapshot(self.database)
        normalized = [statement.strip().upper() for statement in trace]
        begin_index = normalized.index("BEGIN")
        schema_index = next(
            index for index, statement in enumerate(normalized) if "TABLE_INFO" in statement
        )
        ledger_index = next(
            index
            for index, statement in enumerate(normalized)
            if statement.startswith("SELECT SCHEMA_VERSION")
        )
        event_index = next(
            index
            for index, statement in enumerate(normalized)
            if statement.startswith("SELECT ID,TS")
        )
        self.assertLess(begin_index, schema_index)
        self.assertLess(begin_index, ledger_index)
        self.assertLess(begin_index, event_index)

    def test_reconciliation_event_is_not_accepted_as_unchanged_live_projection(self) -> None:
        connection = sqlite3.connect(self.database)
        try:
            connection.execute(
                "UPDATE semantic_events SET action='workload_receipt_reconciled' WHERE id=1"
            )
            connection.commit()
        finally:
            connection.close()
        snapshot = HARNESS.read_database_snapshot(self.database)
        with self.assertRaises(HARNESS.HarnessError):
            HARNESS.validate_live_commit_snapshot(
                snapshot,
                self.manifest,
                self.receipt,
                self.receipt_sha,
                SESSION_ID,
            )

    def test_redacted_facts_reject_unknown_private_and_normalized_keys(self) -> None:
        snapshot = HARNESS.read_database_snapshot(self.database)
        for key in ("future_metric", "prompt", "cwd", "CgRoUp-PaTh", "owner-PID"):
            with self.subTest(key=key):
                mutated = self.mutate_ledger_facts(
                    snapshot, lambda facts, key=key: facts.__setitem__(key, "private")
                )
                with self.assertRaises(HARNESS.HarnessError):
                    self.validate_snapshot(mutated)

    def test_receipt_to_workload_mapping_is_exact(self) -> None:
        snapshot = HARNESS.read_database_snapshot(self.database)

        def alter(facts: dict[str, object]) -> None:
            workload = facts["task_workload_resources"]
            assert isinstance(workload, dict)
            workload["known_total_cpu_us"] = 13

        with self.assertRaisesRegex(HARNESS.HarnessError, "workload"):
            self.validate_snapshot(self.mutate_ledger_facts(snapshot, alter))

    def test_json_and_sqlite_integer_fields_reject_booleans(self) -> None:
        snapshot = HARNESS.read_database_snapshot(self.database)

        def bool_counter(facts: dict[str, object]) -> None:
            terminal = facts["task_terminal_resources"]
            assert isinstance(terminal, dict)
            terminal["spawned_attempt_count"] = True

        with self.assertRaises(HARNESS.HarnessError):
            self.validate_snapshot(
                self.mutate_ledger_facts(snapshot, bool_counter)
            )

        ledger = list(snapshot["ledger"][0])
        ledger[HARNESS.LEDGER_COLUMNS.index("recorded_at")] = True
        with self.assertRaisesRegex(HARNESS.HarnessError, "ledger"):
            self.validate_snapshot(
                {"ledger": (tuple(ledger),), "events": snapshot["events"]}
            )

        def bool_advice(value: object) -> object:
            assert isinstance(value, dict)
            advice = value["advice"]
            assert isinstance(advice, dict)
            advice["requested_parallelism"] = True
            return value

        with self.assertRaisesRegex(HARNESS.HarnessError, "advice"):
            self.validate_snapshot(
                self.mutate_event_json(
                    snapshot,
                    "scheduling_advice_observed",
                    "facts",
                    bool_advice,
                )
            )

    def test_scheduling_event_requires_exact_evidence_facts_and_descriptor(self) -> None:
        snapshot = HARNESS.read_database_snapshot(self.database)
        mutations = (
            ("evidence", lambda _value: {}),
            ("descriptor", lambda _value: None),
            (
                "facts",
                lambda value: {
                    **value,
                    "prompt": "secret prompt from /private/session",
                },
            ),
        )
        for column, mutation in mutations:
            with self.subTest(column=column):
                mutated = self.mutate_event_json(
                    snapshot,
                    "scheduling_advice_observed",
                    column,
                    mutation,
                )
                with self.assertRaises(HARNESS.HarnessError):
                    self.validate_snapshot(mutated)

    def test_terminal_event_requires_exact_facts_evidence_and_descriptor(self) -> None:
        snapshot = HARNESS.read_database_snapshot(self.database)

        def mismatched_facts(value: object) -> object:
            assert isinstance(value, dict)
            value["after_pressure"] = "critical"
            return value

        for column, mutation in (
            ("evidence", lambda _value: {}),
            ("descriptor", lambda _value: None),
            ("facts", mismatched_facts),
        ):
            with self.subTest(column=column):
                mutated = self.mutate_event_json(
                    snapshot, "task_span_closed", column, mutation
                )
                with self.assertRaises(HARNESS.HarnessError):
                    self.validate_snapshot(mutated)

    def test_duplicate_startup_log_requires_all_zero_and_one_counters(self) -> None:
        line = (
            "INFO durable workload receipt startup reconciliation completed "
            "scanned=1 inserted=0 duplicate=1 conflicts=0 acknowledged=1 "
            "already_acknowledged=0 acknowledgement_failures=0 unresolved=0 active_producers=0 "
            "invalid=0 commit_failures=0"
        )
        HARNESS.validate_duplicate_reconciliation_log(line)
        with self.assertRaises(HARNESS.HarnessError):
            HARNESS.validate_duplicate_reconciliation_log(
                line.replace("duplicate=1", "duplicate=0")
            )
        with self.assertRaises(HARNESS.HarnessError):
            HARNESS.validate_duplicate_reconciliation_log(
                line + " duplicate=0"
            )

    def test_public_packet_rejects_private_identity_keys(self) -> None:
        packet = HARNESS.public_packet(
            verdict="PASS",
            executed=True,
            acceptance={
                "crash_point": HARNESS.CRASH_POINT,
                "rows_unchanged_across_restart": True,
            },
        )
        encoded = json.dumps(packet)
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn(str(self.manifest["unit"]), encoded)
        with self.assertRaisesRegex(HARNESS.HarnessError, "privacy"):
            HARNESS.public_packet(
                verdict="PASS", executed=True, acceptance={"unit": "private"}
            )


if __name__ == "__main__":
    unittest.main()
