from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/agent-bridge-benefit-dogfood.py"
SPEC = importlib.util.spec_from_file_location("benefit_dogfood", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def digest(label: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


def event(event_type: str, label: str, metrics: dict) -> dict:
    return {
        "schema": MODULE.EVENT_SCHEMA,
        "event_id": str(
            uuid.UUID(bytes=uuid.uuid5(uuid.NAMESPACE_URL, label).bytes, version=4)
        ),
        "event_type": event_type,
        "observed_at": int(time.time()),
        "subject_sha256": digest(label),
        "real_task_attested": True,
        "metrics": metrics,
    }


def continuity(label: str, **overrides) -> dict:
    metrics = {
        "recall_outcome": "used",
        "owner_restatements": 0,
        "task_completed": True,
        "recovery_seconds": 30,
    }
    metrics.update(overrides)
    return event("continuity", label, metrics)


def avatar(label: str, rating: str = "helpful", **overrides) -> dict:
    metrics = {
        "owner_rating": rating,
        "completed": True,
        "elapsed_ms": 30_000,
        "heartbeat_failures": 0,
        "sidecar_read_failures": 0,
        "transition_count": 2,
        "peak_rss_bytes": 64 * 1024 * 1024,
        "physical_display_confirmed": True,
    }
    metrics.update(overrides)
    return event("avatar", label, metrics)


def embodied(label: str, domain: str, **overrides) -> dict:
    metrics = {
        "domain_sha256": digest(domain),
        "baseline_owner_restatements": 1,
        "trial_owner_restatements": 0,
        "baseline_manual_interventions": 1,
        "trial_manual_interventions": 0,
        "baseline_agent_calls": 7,
        "trial_agent_calls": 2,
        "duplicate_actions": 0,
        "safety_failure": False,
        "cleanup_verified": True,
    }
    metrics.update(overrides)
    return event("embodied", label, metrics)


def voice(label: str, latency: int, **overrides) -> dict:
    metrics = {
        "worker_state": "warm",
        "session_average_latency_ms": latency,
        "invocation_count": 1,
        "utterance_count": 1,
        "failure_count": 0,
        "audible_confirmed": True,
        "continuous_listening": False,
    }
    metrics.update(overrides)
    return event("voice", label, metrics)


def linux_live_receipt() -> dict:
    return {
        "surface": "linux_avatar_live_receipt",
        "schema": 1,
        "dry_run": False,
        "completed": True,
        "elapsed_ms": 30_000,
        "presence": {
            "session_id": "private-session-must-not-persist",
            "heartbeat_count": 8,
            "heartbeat_failures": 0,
            "last_error": None,
        },
        "observation": {
            "surface": "linux_avatar_live_observation",
            "schema": 1,
            "read_only": True,
            "sidecar": {
                "read_failures": 0,
                "transition_count": 3,
                "transition_samples": [{"from": "working", "to": "verified"}],
            },
            "resources": {
                "process_peak_rss_bytes": 60_000_000,
                "worker_vram_observed": False,
            },
            "claims": {
                "compositor_pixels_observed": False,
                "physical_display_observed": False,
                "physical_audio_observed": False,
            },
        },
        "voice_feedback": {
            "surface": "linux_avatar_live_voice_receipt",
            "schema": 1,
            "enabled": True,
            "backend": "qwen3",
            "invocation_count": 1,
            "utterance_count": 1,
            "failure_count": 0,
            "invocation_latency_ms": {"count": 1, "average": 1800, "max": 1800},
            "continuous_listening": False,
        },
        "safety": {
            "foreground_only": True,
            "installs_service": False,
            "controls_desktop": False,
            "executes_actions": False,
            "enables_embodiment_runtime_p4": False,
        },
    }


class BenefitDogfoodTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.log = Path(self.temp.name) / "private" / "benefit.jsonl"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def passing_rows(self) -> list[dict]:
        rows = [continuity(f"continuity-{index}") for index in range(20)]
        rows.extend(avatar(f"avatar-{index}") for index in range(20))
        rows.extend(
            [
                embodied("embodied-1", "media"),
                embodied("embodied-2", "mobile"),
                voice("voice-1", 1000),
                voice("voice-2", 3000),
            ]
        )
        return rows

    def test_private_append_only_ledger_and_duplicate_subject_guard(self) -> None:
        row = continuity("task-1")
        result = MODULE.record_event(self.log, row)
        self.assertEqual(result["status"], "RECORDED")
        self.assertEqual(stat.S_IMODE(self.log.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.log.parent.stat().st_mode), 0o700)
        with self.assertRaisesRegex(MODULE.DogfoodError, "EVENT_SUBJECT_ALREADY_RECORDED"):
            MODULE.record_event(
                self.log,
                {**row, "event_id": str(uuid.uuid4())},
            )

    def test_closed_schema_rejects_content_fields(self) -> None:
        for field in ("task_text", "prompt", "transcript", "note", "path"):
            candidate = continuity("task-1")
            candidate[field] = "secret"
            with self.subTest(field=field), self.assertRaises(MODULE.DogfoodError):
                MODULE.validate_event(candidate)

    def test_collecting_report_is_empty_and_non_influential(self) -> None:
        report = MODULE.build_report([])
        self.assertEqual(report["verdict"], "COLLECTING_TWO_WEEK_DOGFOOD")
        self.assertEqual(report["continuity"]["remaining_tasks"], 20)
        self.assertFalse(report["guardrails"]["runtime_influence_allowed"])

    def test_all_four_kpi_gates_pass_at_locked_targets(self) -> None:
        report = MODULE.build_report(self.passing_rows())
        self.assertEqual(report["verdict"], "READY_FOR_OWNER_ADOPTION_REVIEW")
        self.assertEqual(set(report["gates"].values()), {"PASS"})
        self.assertEqual(report["voice"]["warm_latency_p50_ms"], 2000)
        self.assertEqual(report["voice"]["warm_latency_p95_ms"], 2900)
        self.assertEqual(report["embodied"]["observed_domains"], 2)

    def test_harmful_recall_stops_even_before_target(self) -> None:
        report = MODULE.build_report(
            [continuity("harmful", recall_outcome="harmful")]
        )
        self.assertEqual(report["verdict"], "STOP_AND_REVIEW")
        self.assertEqual(report["continuity"]["harmful_count"], 1)

    def test_failed_value_gate_retains_on_demand_after_complete_sample(self) -> None:
        rows = self.passing_rows()
        rows = [
            avatar(row["event_id"], "distracting")
            if row["event_type"] == "avatar"
            else row
            for row in rows
        ]
        report = MODULE.build_report(rows)
        self.assertEqual(report["gates"]["avatar"], "FAIL")
        self.assertEqual(report["verdict"], "RETAIN_ON_DEMAND")

    def test_duplicate_external_action_is_a_hard_guardrail(self) -> None:
        report = MODULE.build_report(
            [embodied("episode", "media", duplicate_actions=1)]
        )
        self.assertEqual(report["verdict"], "STOP_AND_REVIEW")

    def test_avatar_receipt_is_reduced_without_session_or_transition_content(self) -> None:
        row = MODULE.avatar_event_from_receipt(
            linux_live_receipt(),
            digest("receipt"),
            owner_rating="helpful",
            physical_display_confirmed=True,
        )
        encoded = json.dumps(row)
        self.assertNotIn("private-session", encoded)
        self.assertNotIn("verified", encoded)
        self.assertEqual(row["metrics"]["transition_count"], 3)

    def test_avatar_receipt_rejects_crossed_safety_boundary(self) -> None:
        receipt = linux_live_receipt()
        receipt["safety"]["executes_actions"] = True
        with self.assertRaisesRegex(MODULE.DogfoodError, "SAFETY_BOUNDARY_CROSSED"):
            MODULE.avatar_event_from_receipt(
                receipt,
                digest("receipt"),
                owner_rating="helpful",
                physical_display_confirmed=True,
            )

    def test_voice_receipt_tracks_session_average_and_owner_audibility(self) -> None:
        row = MODULE.voice_event_from_receipt(
            linux_live_receipt(),
            digest("voice-receipt"),
            worker_state="warm",
            audible_confirmed=True,
        )
        self.assertEqual(row["metrics"]["session_average_latency_ms"], 1800)
        self.assertTrue(row["metrics"]["audible_confirmed"])

    def test_voice_receipt_rejects_latency_count_mismatch(self) -> None:
        receipt = linux_live_receipt()
        receipt["voice_feedback"]["invocation_latency_ms"]["count"] = 2
        with self.assertRaisesRegex(MODULE.DogfoodError, "INVALID_LINUX_LIVE_VOICE"):
            MODULE.voice_event_from_receipt(
                receipt,
                digest("voice-receipt"),
                worker_state="warm",
                audible_confirmed=True,
            )

    def test_process_observation_cannot_claim_physical_display(self) -> None:
        receipt = linux_live_receipt()
        receipt["observation"]["claims"]["physical_display_observed"] = True
        with self.assertRaisesRegex(MODULE.DogfoodError, "INVALID_LINUX_LIVE_OBSERVATION"):
            MODULE.avatar_event_from_receipt(
                receipt,
                digest("receipt"),
                owner_rating="helpful",
                physical_display_confirmed=True,
            )

    def test_continuous_listening_is_never_admitted(self) -> None:
        candidate = voice("voice", 1000, continuous_listening=True)
        with self.assertRaisesRegex(MODULE.DogfoodError, "CONTINUOUS_LISTENING_FORBIDDEN"):
            MODULE.validate_event(candidate)

    def test_hash_bound_aggregate_contains_no_rows(self) -> None:
        rows = [continuity("task-1")]
        raw = (json.dumps(rows[0]) + "\n").encode()
        aggregate = MODULE.build_aggregate(rows, raw, digest("node"))
        self.assertFalse(aggregate["contains_event_rows"])
        self.assertNotIn("subject_sha256", json.dumps(aggregate))
        self.assertEqual(aggregate["ledger_sha256"], MODULE._sha256_bytes(raw))

    def test_insecure_or_symlink_ledger_fails_closed(self) -> None:
        self.log.parent.mkdir(mode=0o700)
        self.log.write_text("")
        self.log.chmod(0o644)
        with self.assertRaisesRegex(MODULE.DogfoodError, "INSECURE_LEDGER_PERMISSIONS"):
            MODULE.read_rows(self.log)
        self.log.unlink()
        target = Path(self.temp.name) / "target"
        target.write_text("")
        target.chmod(0o600)
        self.log.symlink_to(target)
        with self.assertRaises(MODULE.DogfoodError):
            MODULE.read_rows(self.log)

    def test_cli_empty_report_is_structured(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--log", str(self.log), "report"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(
            json.loads(completed.stdout)["verdict"],
            "COLLECTING_TWO_WEEK_DOGFOOD",
        )
        self.assertEqual(completed.stderr, "")

    def test_concurrent_cli_records_remain_complete(self) -> None:
        processes = []
        for index in range(8):
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(MODULE_PATH),
                        "--log",
                        str(self.log),
                        "record-continuity",
                        "--attest-real-task",
                        "--subject-sha256",
                        digest(f"concurrent-{index}"),
                        "--recall-outcome",
                        "used",
                        "--owner-restatements",
                        "0",
                        "--task-completed",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )
        outputs = [process.communicate(timeout=10) for process in processes]
        self.assertTrue(all(process.returncode == 0 for process in processes), outputs)
        self.assertEqual(len(MODULE.read_rows(self.log)), 8)


if __name__ == "__main__":
    unittest.main()
