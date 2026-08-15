from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/agent-bridge-memory-usefulness.py"
SPEC = importlib.util.spec_from_file_location("memory_usefulness", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def row(task_id: str, outcome: str = "used", **extra):
    value = {
        "schema": MODULE.SCHEMA,
        "task_id": str(
            uuid.UUID(bytes=uuid.uuid5(uuid.NAMESPACE_URL, task_id).bytes, version=4)
        ),
        "task_kind": "repo_truth",
        "observed_at": int(time.time()),
        "recall_outcome": outcome,
        "repeated_explanations": 0,
        "real_task_attested": True,
    }
    value.update(extra)
    return value


class MemoryUsefulnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.log = Path(self.temp.name) / "private" / "ledger.jsonl"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_record_creates_private_append_only_ledger(self) -> None:
        original = row("task-1")
        receipt = MODULE.record_task(self.log, original)
        self.assertEqual(receipt["status"], "RECORDED")
        self.assertEqual(stat.S_IMODE(self.log.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.log.parent.stat().st_mode), 0o700)
        self.assertEqual(MODULE.read_rows(self.log), [original])

    def test_duplicate_task_id_is_rejected_without_append(self) -> None:
        first = row("task-1")
        MODULE.record_task(self.log, first)
        before = self.log.read_bytes()
        with self.assertRaisesRegex(MODULE.LedgerError, "TASK_ID_ALREADY_RECORDED"):
            MODULE.record_task(self.log, row("task-1", "stale"))
        self.assertEqual(self.log.read_bytes(), before)

    def test_report_collects_until_twenty(self) -> None:
        report = MODULE.build_report([row("task-1")], 20)
        self.assertEqual(report["verdict"], "COLLECTING_REAL_TASKS")
        self.assertEqual(report["remaining_tasks"], 19)
        self.assertEqual(report["used_task_rate"], 1.0)

    def test_report_ready_at_twenty_unique_tasks(self) -> None:
        rows = [row(f"task-{index}") for index in range(20)]
        report = MODULE.build_report(rows, 20)
        self.assertEqual(report["verdict"], "READY_FOR_PRODUCT_DECISION")
        self.assertEqual(report["remaining_tasks"], 0)

    def test_target_cannot_weaken_twenty_task_minimum(self) -> None:
        with self.assertRaisesRegex(MODULE.LedgerError, "INVALID_TARGET"):
            MODULE.build_report([row("task-1")], 1)

    def test_negative_and_optional_metrics_are_aggregate_only(self) -> None:
        rows = [
            row("task-1", "used", recovery_seconds=30, retrieval_payload_bytes=1000),
            row("task-2", "stale", repeated_explanations=2),
            row("task-3", "harmful", recovery_seconds=90),
        ]
        report = MODULE.build_report(rows, 20)
        self.assertEqual(report["negative_recall_count"], 2)
        self.assertEqual(report["tasks_with_repeated_explanation"], 1)
        self.assertEqual(report["average_recovery_seconds"], 60.0)
        self.assertEqual(report["average_retrieval_payload_bytes"], 1000.0)
        self.assertFalse(report["privacy"]["task_text_stored"])

    def test_invalid_or_tampered_row_fails_closed(self) -> None:
        self.log.parent.mkdir(mode=0o700)
        self.log.write_text('{"task_id":"leak"}\n')
        self.log.chmod(0o600)
        with self.assertRaises(MODULE.LedgerError):
            MODULE.read_rows(self.log)

    def test_insecure_permissions_fail_closed(self) -> None:
        self.log.parent.mkdir(mode=0o700)
        self.log.write_text("")
        self.log.chmod(0o644)
        with self.assertRaisesRegex(MODULE.LedgerError, "INSECURE_LEDGER_PERMISSIONS"):
            MODULE.read_rows(self.log)

    def test_symlink_is_rejected(self) -> None:
        self.log.parent.mkdir(mode=0o700)
        target = Path(self.temp.name) / "target"
        target.write_text("")
        target.chmod(0o600)
        self.log.symlink_to(target)
        with self.assertRaises(MODULE.LedgerError):
            MODULE.read_rows(self.log)

    def test_oversized_ledger_is_rejected_before_decode(self) -> None:
        self.log.parent.mkdir(mode=0o700)
        with self.log.open("wb") as handle:
            handle.truncate(MODULE.MAX_LEDGER_BYTES + 1)
        self.log.chmod(0o600)
        with self.assertRaisesRegex(MODULE.LedgerError, "LEDGER_TOO_LARGE"):
            MODULE.read_rows(self.log)

    def test_unterminated_row_is_rejected(self) -> None:
        self.log.parent.mkdir(mode=0o700)
        self.log.write_text(json.dumps(row("task-1")))
        self.log.chmod(0o600)
        with self.assertRaisesRegex(MODULE.LedgerError, "UNTERMINATED_LEDGER_ROW"):
            MODULE.read_rows(self.log)

    def test_append_that_crosses_limit_is_rejected_without_change(self) -> None:
        original = (json.dumps(row("task-1"), separators=(",", ":")) + "\n").encode()
        self.log.parent.mkdir(mode=0o700)
        self.log.write_bytes(original)
        self.log.chmod(0o600)
        previous_limit = MODULE.MAX_LEDGER_BYTES
        MODULE.MAX_LEDGER_BYTES = len(original) + 1
        try:
            with self.assertRaisesRegex(MODULE.LedgerError, "LEDGER_TOO_LARGE"):
                MODULE.record_task(self.log, row("task-2"))
        finally:
            MODULE.MAX_LEDGER_BYTES = previous_limit
        self.assertEqual(self.log.read_bytes(), original)

    def test_partial_write_failure_rolls_back_to_original_size(self) -> None:
        MODULE.record_task(self.log, row("task-1"))
        original = self.log.read_bytes()
        real_write = os.write
        calls = 0

        def fail_after_partial(fd, payload):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_write(fd, payload[:5])
            raise OSError("injected")

        with mock.patch.object(MODULE.os, "write", side_effect=fail_after_partial):
            with self.assertRaisesRegex(MODULE.LedgerError, "LEDGER_WRITE_FAILED"):
                MODULE.record_task(self.log, row("task-2"))
        self.assertEqual(self.log.read_bytes(), original)

    def test_exact_reader_tolerates_short_reads(self) -> None:
        chunks = iter((b"ab", b"c", b"def"))
        with mock.patch.object(
            MODULE.os, "read", side_effect=lambda _fd, _n: next(chunks)
        ):
            self.assertEqual(MODULE._read_exact(123, 6), b"abcdef")

    def test_schema_rejects_content_paths_and_unknown_fields(self) -> None:
        for forbidden in (
            "task_text",
            "prompt",
            "transcript",
            "memory_key",
            "path",
            "note",
        ):
            with self.subTest(forbidden=forbidden), self.assertRaises(
                MODULE.LedgerError
            ):
                MODULE.validate_row(row("task-1", **{forbidden: "secret"}))

    def test_task_id_kind_and_attestation_are_closed(self) -> None:
        with self.assertRaisesRegex(MODULE.LedgerError, "INVALID_TASK_ID"):
            MODULE.validate_row({**row("task-1"), "task_id": "private-project"})
        with self.assertRaisesRegex(MODULE.LedgerError, "INVALID_TASK_KIND"):
            MODULE.validate_row({**row("task-1"), "task_kind": "secret-project"})
        with self.assertRaisesRegex(
            MODULE.LedgerError, "REAL_TASK_ATTESTATION_REQUIRED"
        ):
            MODULE.validate_row({**row("task-1"), "real_task_attested": False})

    def test_cli_report_missing_file_is_structured_collecting(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--log", str(self.log), "report"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 4)
        self.assertEqual(json.loads(completed.stdout)["observed_tasks"], 0)
        self.assertEqual(completed.stderr, "")

    def test_cli_rejects_target_below_twenty(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "--log",
                str(self.log),
                "report",
                "--target",
                "1",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["error_code"], "INVALID_TARGET")

    def test_concurrent_cli_records_remain_complete(self) -> None:
        commands = []
        for _ in range(8):
            commands.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(MODULE_PATH),
                        "--log",
                        str(self.log),
                        "record",
                        "--task-kind",
                        "implementation",
                        "--attest-real-task",
                        "--recall-outcome",
                        "used",
                        "--repeated-explanations",
                        "0",
                    ],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            )
        results = [process.communicate(timeout=10) for process in commands]
        self.assertTrue(all(process.returncode == 0 for process in commands), results)
        self.assertEqual(len(MODULE.read_rows(self.log)), 8)


if __name__ == "__main__":
    unittest.main()
