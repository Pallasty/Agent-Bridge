import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from macos_ax_watch import diff_samples, watch


def sample(pid=7, identifier="main", focused=False, sampled_at=1.0):
    window = {
        "index": 0,
        "ax_identifier": identifier,
        "title": "Main",
        "focused": focused,
        "identity": {"kind": "ax_identifier", "value": identifier, "stable_across_samples": True},
    }
    return {
        "sampled_at": sampled_at,
        "status": "ready",
        "permission": {"ax_trusted": True, "prompted": False},
        "frontmost_app": {"name": "Notes", "pid": pid, "bundle_id": "com.apple.Notes"},
        "windows": [window],
        "truncated": False,
        "errors": [],
    }


class MacosAxWatchTests(unittest.TestCase):
    def test_focus_change_requires_stable_identity(self):
        events = diff_samples(sample(focused=False), sample(focused=True), 2.0)
        self.assertEqual([event["type"] for event in events], ["window_focus_changed"])
        self.assertEqual(events[0]["identity_basis"], "ax_identifier")

    def test_sample_local_windows_do_not_emit_false_lifecycle(self):
        before = sample()
        after = sample()
        for value, index in ((before, 0), (after, 1)):
            value["windows"][0]["ax_identifier"] = None
            value["windows"][0]["index"] = index
            value["windows"][0]["identity"] = {
                "kind": "sample_index", "value": str(index), "stable_across_samples": False
            }
        self.assertEqual(diff_samples(before, after, 2.0), [])

    def test_app_change_does_not_claim_window_lifecycle(self):
        before = sample(pid=7, identifier="notes")
        after = sample(pid=8, identifier="finder")
        after["frontmost_app"] = {"name": "Finder", "pid": 8, "bundle_id": "com.apple.finder"}
        types = [event["type"] for event in diff_samples(before, after, 2.0)]
        self.assertEqual(types, ["frontmost_app_changed"])

    def test_duplicate_ax_identifier_is_not_treated_as_unique(self):
        before = sample(focused=False)
        duplicate = dict(before["windows"][0])
        duplicate["index"] = 1
        before["windows"].append(duplicate)
        after = sample(focused=True)
        after["windows"].append(dict(duplicate, focused=False))
        self.assertEqual(diff_samples(before, after, 2.0), [])

    def test_identifier_becoming_ambiguous_is_not_disappearance(self):
        before = sample()
        after = sample()
        after["windows"].append(dict(after["windows"][0], index=1))
        self.assertEqual(diff_samples(before, after, 2.0), [])

    def test_truncated_sample_does_not_claim_lifecycle(self):
        before = sample(identifier="old")
        after = sample(identifier="new")
        after["truncated"] = True
        self.assertEqual(diff_samples(before, after, 2.0), [])

    def test_unique_stable_window_lifecycle_within_same_app(self):
        before = sample(identifier="old")
        after = sample(identifier="new")
        types = [event["type"] for event in diff_samples(before, after, 2.0)]
        self.assertEqual(types, ["window_disappeared", "window_appeared"])

    def test_watch_is_bounded_and_reports_coverage(self):
        values = iter([sample(focused=False, sampled_at=1.0), sample(focused=True, sampled_at=2.0)])
        result = watch(
            sample_count=2,
            interval_secs=0.1,
            max_windows=8,
            max_events=1,
            jxa_timeout_secs=1.0,
            include_samples=False,
            sampler=lambda: next(values),
            sleeper=lambda _: None,
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["event_count"], 1)
        self.assertEqual(result["dropped_events"], 0)
        self.assertEqual(
            result["coverage"]["event_identity_requirement"],
            "same_process_complete_samples_unique_ax_identifier",
        )
        self.assertNotIn("samples", result)

    def test_budget_exhaustion_is_not_verified(self):
        before = sample(pid=7, identifier="notes")
        after = sample(pid=7, identifier="finder")
        values = iter([before, after])
        result = watch(
            sample_count=2,
            interval_secs=0.1,
            max_windows=8,
            max_events=1,
            jxa_timeout_secs=1.0,
            include_samples=True,
            sampler=lambda: next(values),
            sleeper=lambda _: None,
        )
        self.assertGreater(result["dropped_events"], 0)
        self.assertEqual(result["verification"]["verdict"], "incomplete")
        self.assertEqual(result["verification"]["recover"], "replan")


if __name__ == "__main__":
    unittest.main()
