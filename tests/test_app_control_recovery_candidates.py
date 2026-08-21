import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

APP = load("recovery_test_app", ROOT / "scripts/app_control.py")
INDEX = load("recovery_index", ROOT / "scripts/app-control-recovery-candidates.py")


class RecoveryCandidateIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name); os.chmod(self.directory, 0o700)
        self.operation_id = "ab-episode-0123456789abcdef0123456789abcdef"
        self.key = hashlib.sha256(self.operation_id.encode()).hexdigest()

    def tearDown(self): self.temp.cleanup()

    def write_candidate(self, **changes):
        request = APP.operation_request("next", "rhythmbox", 3600)
        record = APP.operation_record(
            self.operation_id, APP.operation_request_digest("next", "rhythmbox", 3600), request,
            created_at=1000.0, expires_at=4600.0, phase="dispatch_started", dispatch_count=1,
            player="rhythmbox", baseline={"player": "rhythmbox", "track_id": "/track/a"},
        )
        record.update(changes)
        record_path = self.directory / f"{self.key}.json"
        lock_path = self.directory / f"{self.key}.lock"
        record_path.write_text(json.dumps(record)); lock_path.write_text("")
        os.chmod(record_path, 0o600); os.chmod(lock_path, 0o600)
        return record_path, lock_path

    def test_discovers_one_unexpired_recovery_anchor_without_mutation(self):
        record_path, lock_path = self.write_candidate()
        before = (record_path.read_bytes(), lock_path.read_bytes(), record_path.stat().st_mtime_ns)
        result = INDEX.discover(self.directory, now=1100.0)
        self.assertEqual(result["verdict"], "verified")
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["operation_id"], self.operation_id)
        self.assertEqual(result["candidates"][0]["request"], APP.operation_request("next", "rhythmbox", 3600))
        self.assertEqual(result["candidates"][0]["request_digest"], APP.operation_request_digest("next", "rhythmbox", 3600))
        self.assertTrue(result["candidates"][0]["revalidation_required"])
        self.assertFalse(result["candidates"][0]["automatic_execution_allowed"])
        self.assertFalse(result["action_invoked"]); self.assertFalse(result["media_observed"])
        self.assertEqual(result["admission"], "eligible_candidate_present")
        self.assertEqual(result["recover"], "proceed")
        self.assertEqual(before, (record_path.read_bytes(), lock_path.read_bytes(), record_path.stat().st_mtime_ns))

    def test_expired_terminal_and_nonopaque_ids_are_not_candidates(self):
        for changes in ({"expires_at": 1000.0}, {"phase": "terminal"}):
            with self.subTest(changes=changes):
                self.write_candidate(**changes)
                self.assertEqual(INDEX.discover(self.directory, now=1100.0)["candidate_count"], 0)
                for path in self.directory.iterdir(): path.unlink()
        self.operation_id = "meaningful-user-text"
        self.key = hashlib.sha256(self.operation_id.encode()).hexdigest()
        self.write_candidate()
        self.assertEqual(INDEX.discover(self.directory, now=1100.0)["candidate_count"], 0)

    def test_busy_lock_skips_without_reading_or_claiming_candidate(self):
        _, lock_path = self.write_candidate()
        with lock_path.open("r") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = INDEX.discover(self.directory, now=1100.0)
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["skipped_count"], 1)

    def test_request_ttl_selector_and_digest_must_be_canonical(self):
        for changes in (
            {"request_digest": "0" * 64},
            {"request": APP.operation_request("next", None, 3600)},
            {"request": {**APP.operation_request("next", "rhythmbox", 3600), "extra": True}},
        ):
            with self.subTest(changes=changes):
                self.write_candidate(**changes)
                self.assertEqual(INDEX.discover(self.directory, now=1100.0)["candidate_count"], 0)
                for path in self.directory.iterdir(): path.unlink()

    def test_unexpired_but_insufficient_window_is_blocked(self):
        self.write_candidate(expires_at=1103.0)
        result = INDEX.discover(self.directory, now=1100.0, minimum_recovery_secs=5.0)
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["blocked_count"], 1)
        self.assertEqual(len(result["blocked_operation_id_sha256"]), 1)
        self.assertEqual(result["minimum_recovery_secs"], 5.0)
        self.assertEqual(result["admission"], "blocked_insufficient_recovery_window")
        self.assertEqual(result["recover"], "replan")

    def test_sufficient_window_remains_candidate(self):
        self.write_candidate(expires_at=1106.0)
        result = INDEX.discover(self.directory, now=1100.0, minimum_recovery_secs=5.0)
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["blocked_count"], 0)

    def test_empty_scan_is_not_a_recovery_admission(self):
        result = INDEX.discover(self.directory, now=1100.0)
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["admission"], "no_recovery_candidate")
        self.assertEqual(result["recover"], "replan")

    def test_exact_selection_requires_unchanged_record_sha(self):
        record_path, _ = self.write_candidate()
        raw_sha = __import__("hashlib").sha256(record_path.read_bytes()).hexdigest()
        selected = INDEX.discover(self.directory, now=1100.0, selected_operation_id=self.operation_id, expected_record_sha256=raw_sha)
        self.assertEqual(selected["candidate_count"], 1)
        record_path.write_text(record_path.read_text().replace('"phase": "dispatch_started"', '"phase": "retryable"'))
        conflicted = INDEX.discover(self.directory, now=1100.0, selected_operation_id=self.operation_id, expected_record_sha256=raw_sha)
        self.assertEqual(conflicted["candidate_count"], 0)
        self.assertEqual(conflicted["admission"], "selection_conflict")
        self.assertEqual(conflicted["recover"], "replan")

    def test_selected_missing_or_bad_digest_never_becomes_candidate(self):
        self.write_candidate()
        missing = INDEX.discover(self.directory, now=1100.0, selected_operation_id="ab-episode-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        self.assertEqual(missing["admission"], "selection_conflict")
        bad = INDEX.discover(self.directory, now=1100.0, selected_operation_id=self.operation_id, expected_record_sha256="0" * 64)
        self.assertEqual(bad["admission"], "selection_conflict")

    def test_unsafe_or_corrupt_journal_fails_entire_scan_closed(self):
        record_path, _ = self.write_candidate()
        record_path.write_text("{")
        result = INDEX.discover(self.directory, now=1100.0)
        self.assertEqual(result["verdict"], "error")
        self.assertFalse(result["scan_complete"])
        self.assertEqual(result["candidates"], [])

    def test_source_has_no_execution_or_player_observation(self):
        source = (ROOT / "scripts/app-control-recovery-candidates.py").read_text()
        self.assertNotIn("subprocess", source)
        self.assertNotIn("execute_once", source)
        self.assertNotIn("recover_dispatch_started_operation", source)
        self.assertNotIn("playerctl", source)
        self.assertNotIn('"journal": str(directory)', source)

    def test_readonly_evidence_records_empty_cold_start_without_authority(self):
        path = ROOT / "docs/design/evidence/app_control_recovery_candidate_index_readonly_2026_08_20.json"
        value = json.loads(path.read_text())
        self.assertEqual(value["decision"]["status"], "READY_FOR_FUTURE_OPAQUE_ID_HANDOFF")
        self.assertEqual(value["observation"]["candidate_count"], 0)
        self.assertTrue(value["observation"]["journal_manifest_unchanged"])
        self.assertFalse(value["decision"]["automatic_recovery_authorized"])
        self.assertTrue(all(item is False for item in value["claim_boundary"].values()))


if __name__ == "__main__": unittest.main()
