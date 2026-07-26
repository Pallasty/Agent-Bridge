import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_object_cost_measurement_d54r2_aggregator as aggregator
import fh_l8_object_cost_measurement_d54r2_launcher as launcher


class D54ExecutionTests(unittest.TestCase):
    def test_exact_plan(self):
        plan = launcher.plan()
        self.assertEqual(len(plan), 70)
        self.assertEqual(sum(row["sample_kind"] == "warmup" for row in plan), 20)
        self.assertEqual(sum(row["sample_kind"] == "measured" for row in plan), 50)
        self.assertEqual(len({launcher.sample_name(row) for row in plan}), 70)

    def test_envelope_fails_closed_on_swap_oom_and_identity(self):
        sample = launcher.plan()[0]
        base = {
            "sample": sample, "runner_return_code": 0, "runner_stderr_bytes": 0,
            "cgroup_swap_current_bytes": 0,
            "cgroup_memory_events_delta": {"oom": 0, "oom_kill": 0},
            "network_interfaces": ["lo"],
            "runner_stdout": json.dumps({**sample, "packed_q3_reads": 0}),
            "runner_stderr": "",
        }
        self.assertEqual(launcher.validate_envelope(json.dumps(base).encode(), sample)["sample"], sample)
        for mutation in (
            {"cgroup_swap_current_bytes": 1},
            {"cgroup_memory_events_delta": {"oom": 1, "oom_kill": 0}},
            {"runner_return_code": 1},
            {"network_interfaces": ["eth0", "lo"]},
        ):
            value = {**base, **mutation}
            with self.assertRaises(launcher.LaunchError):
                launcher.validate_envelope(json.dumps(value).encode(), sample)

    def test_publish_is_no_replace(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "receipt.json"
            launcher.publish(path, b"one\n")
            with self.assertRaises(launcher.LaunchError):
                launcher.publish(path, b"two\n")
            self.assertEqual(path.read_bytes(), b"one\n")

    def test_aggregator_rejects_incomplete_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "launcher-state.json").write_text(
                json.dumps({"status": "D54_RAW_SAMPLE_SET_COMPLETE", "sample_count": 69})
            )
            with self.assertRaises(aggregator.AggregateError):
                aggregator.aggregate(root)

    def test_launcher_requires_clean_committed_source(self):
        clean = mock.Mock(stdout="abc\n")
        dirty = mock.Mock(stdout=" M file\n")
        with mock.patch.object(launcher.subprocess, "run", side_effect=[clean, dirty]):
            with self.assertRaises(launcher.LaunchError):
                launcher.git_identity()


if __name__ == "__main__":
    unittest.main()
