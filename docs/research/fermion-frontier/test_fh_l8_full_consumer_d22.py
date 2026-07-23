#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_full_consumer_d22 as d22


class D22FixtureConsumerTests(unittest.TestCase):
    def test_full_tiny_fixture_is_exactly_53_shards(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = d22.run_fixture(Path(tmp), d22.tiny_fixture())
            self.assertEqual(result["completed_shards"], 53)
            self.assertEqual(result["rows"], 106)
            self.assertEqual(result["scientific_action_calls"], 0)
            self.assertFalse(result["full_53_execution_authorized"])

    def test_interruption_then_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(d22.SimulatedInterruption):
                d22.run_fixture(Path(tmp), d22.tiny_fixture(), interrupt_after=17)
            result = d22.run_fixture(Path(tmp), d22.tiny_fixture())
            self.assertEqual(result["completed_shards"], 53)

    def test_orphan_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(d22.SimulatedInterruption): d22.run_fixture(root, d22.tiny_fixture(), interrupt_after=2)
            (root / "spills" / "orphan.jsonl").write_text("{}\n")
            with self.assertRaisesRegex(d22.ConsumerError, "orphan"):
                d22.run_fixture(root, d22.tiny_fixture())

    def test_manifest_hash_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(d22.SimulatedInterruption): d22.run_fixture(root, d22.tiny_fixture(), interrupt_after=1)
            path = root / "manifests" / "shard-00.json"
            data = json.loads(path.read_text()); data["shard"] = 4; path.write_text(json.dumps(data))
            with self.assertRaisesRegex(d22.ConsumerError, "manifest hash drift"):
                d22.run_fixture(root, d22.tiny_fixture())

    def test_fixture_hash_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = d22.tiny_fixture(); fixture["shards"][0][0]["value"] = 99
            with self.assertRaisesRegex(d22.ConsumerError, "fixture hash drift"):
                d22.run_fixture(Path(tmp), fixture)

    def test_no_replace_target_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); d22.run_fixture(root, d22.tiny_fixture())
            with self.assertRaisesRegex(d22.ConsumerError, "target already published"):
                d22.run_fixture(root, d22.tiny_fixture())

    def test_gap_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(d22.SimulatedInterruption): d22.run_fixture(root, d22.tiny_fixture(), interrupt_after=2)
            (root / "manifests" / "shard-00.json").unlink()
            with self.assertRaisesRegex(d22.ConsumerError, "gap"):
                d22.run_fixture(root, d22.tiny_fixture())


if __name__ == "__main__": unittest.main()
