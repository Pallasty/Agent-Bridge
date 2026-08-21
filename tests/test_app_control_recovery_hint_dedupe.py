import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/app-control-recovery-hint-dedupe.py"
spec = importlib.util.spec_from_file_location("recovery_hint_dedupe", SCRIPT)
DEDUPE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(DEDUPE)


def bootstrap(remaining=900, record="d" * 64, operation="ab-episode-" + "c" * 32):
    return f"""=== Bootstrap ===

=== Durable Media Recovery Candidates (1) — read-only, not selected ===
Current workspace/intent binding: unverified. Automatic execution: forbidden.
  • operation_id={operation} player=\"rhythmbox\" ttl=3600s remaining≈{remaining}s record_sha256={record}
Next: explicitly review one candidate, then revalidate its exact operation_id + record_sha256 before using the normal recovery path.

=== Session Lifecycle Reminder ===
keep me
"""


class RecoveryHintDedupeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp.name) / "state"

    def tearDown(self):
        self.temp.cleanup()

    def apply(self, text, session="session-a", now=1000):
        return DEDUPE.filter_hint(text, self.state_dir, session, now)

    def test_first_hint_is_visible_and_repeat_is_suppressed(self):
        first = self.apply(bootstrap(900), now=1000)
        state_file = next(self.state_dir.glob("*.json"))
        before = (state_file.read_bytes(), state_file.stat().st_mtime_ns)
        second = self.apply(bootstrap(850), now=1050)
        self.assertIn("Durable Media Recovery Candidates", first)
        self.assertNotIn("Media Recovery Candidates", second)
        self.assertIn("Session Lifecycle Reminder", second)
        directory_mode = self.state_dir.stat().st_mode & 0o777
        self.assertEqual(directory_mode, 0o700)
        self.assertEqual(state_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(before, (state_file.read_bytes(), state_file.stat().st_mtime_ns))

    def test_record_change_and_urgency_transitions_remind(self):
        self.apply(bootstrap(900), now=1000)
        self.assertNotIn("Media Recovery Candidates", self.apply(bootstrap(800), now=1010))
        self.assertIn("Media Recovery Candidates", self.apply(bootstrap(300), now=1020))
        self.assertNotIn("Media Recovery Candidates", self.apply(bootstrap(250), now=1030))
        self.assertIn("Media Recovery Candidates", self.apply(bootstrap(60), now=1040))
        self.assertIn("Media Recovery Candidates", self.apply(bootstrap(50, record="e" * 64), now=1050))

    def test_new_session_still_sees_full_hint(self):
        self.apply(bootstrap(), session="session-a")
        self.assertIn("Media Recovery Candidates", self.apply(bootstrap(), session="session-b"))

    def test_disappearance_emits_one_non_authoritative_update(self):
        self.apply(bootstrap())
        absent = "=== Bootstrap ===\n\n=== Session Lifecycle Reminder ===\n"
        first = self.apply(absent, now=1100)
        second = self.apply(absent, now=1200)
        self.assertIn("not present in this bootstrap output", first)
        self.assertIn("No action was executed", first)
        self.assertNotIn("candidate update", second)

    def test_malformed_block_and_state_failure_preserve_original(self):
        malformed = bootstrap().replace("record_sha256=" + "d" * 64, "record_sha256=bad")
        self.assertEqual(self.apply(malformed), malformed)
        unsafe = Path(self.temp.name) / "unsafe"
        unsafe.write_text("not a directory")
        self.assertEqual(DEDUPE.filter_hint(bootstrap(), unsafe, "session-a", 1000), bootstrap())

    def test_state_file_count_is_bounded(self):
        for index in range(DEDUPE.MAX_STATE_FILES + 5):
            self.apply(bootstrap(), session=f"session-{index}", now=1000 + index)
        self.assertLessEqual(len(list(self.state_dir.glob("*.json"))), DEDUPE.MAX_STATE_FILES)


if __name__ == "__main__":
    unittest.main()
