#!/usr/bin/env python3
"""Real isolated CLI regression: weekly reports the saved key without nested output."""
import argparse
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from dream_identity_cli_parity import setup, invoke

BINARY = None


class SnapshotCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env, self.db = setup(self.root)

    def run_cli(self, *args):
        run, _, _ = invoke(BINARY, self.root, self.env, ['dream', *args])
        self.assertEqual(run.returncode, 0, run.stderr.decode())
        return run.stdout.decode(), run.stderr.decode()

    def keys(self):
        with sqlite3.connect(f'file:{self.db}?mode=ro', uri=True) as db:
            return [row[0] for row in db.execute("SELECT key FROM memories WHERE kind='snapshot'")]

    def test_weekly_json_is_one_document_with_persisted_key(self):
        out, err = self.run_cli('weekly', '--json')
        report = json.loads(out)  # Reject concatenated snapshot + weekly JSON.
        self.assertEqual(self.keys(), [report['snapshot_key']])
        self.assertNotIn('saved as memory:', err)

    def test_weekly_text_reports_persisted_key_without_snapshot_payload(self):
        out, err = self.run_cli('weekly')
        keys = self.keys(); self.assertEqual(len(keys), 1)
        self.assertIn('  saved: ' + keys[0] + '\n', out)
        self.assertNotIn('"schema_version"', out)
        self.assertNotIn('self-portrait snapshot', out)
        self.assertNotIn('saved as memory:', err)

    def test_weekly_no_snapshot_does_not_save(self):
        out, _ = self.run_cli('weekly', '--no-snapshot', '--json')
        self.assertIsNone(json.loads(out)['snapshot_key'])
        self.assertEqual(self.keys(), [])

    def test_failed_save_leaves_single_report_null_key_and_warning(self):
        self.run_cli('weekly', '--no-snapshot', '--json')
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TRIGGER deny_snapshot BEFORE INSERT ON memories WHEN NEW.kind='snapshot' BEGIN SELECT RAISE(ABORT, 'fixture denies snapshot'); END")
        out, err = self.run_cli('weekly', '--json')
        self.assertIsNone(json.loads(out)['snapshot_key'])
        self.assertEqual(self.keys(), [])
        self.assertIn('snapshot save skipped:', err)

    def test_standalone_json_keeps_payload_and_saved_acknowledgement(self):
        out, err = self.run_cli('snapshot', '--name', 'fixture', '--json')
        self.assertIn('schema_version', json.loads(out))
        keys = self.keys(); self.assertEqual(len(keys), 1)
        self.assertIn('saved as memory: ' + keys[0], err)

    def test_standalone_text_keeps_payload_and_saved_acknowledgement(self):
        out, err = self.run_cli('snapshot', '--name', 'fixture')
        self.assertIn('self-portrait snapshot', out)
        keys = self.keys(); self.assertEqual(len(keys), 1)
        self.assertIn('saved as memory: ' + keys[0], err)

    def test_print_only_keeps_json_without_saving(self):
        out, err = self.run_cli('snapshot', '--print-only', '--json')
        self.assertIn('schema_version', json.loads(out))
        self.assertEqual(self.keys(), [])
        self.assertIn('--print-only: not saving', err)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    BINARY = args.binary.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SnapshotCompositionTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
