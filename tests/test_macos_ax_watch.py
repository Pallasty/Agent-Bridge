import copy
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from macos_ax_watch import (
    DEFAULT_TOKEN_MAX_AGE_MS,
    compare_before_token,
    compare_state_sequence,
    desktop_state,
    diff_samples,
    watch,
)


def sample(pid=7, identifier="main", focused=False, sampled_at=1.0):
    window = {
        "index": 0,
        "ax_identifier": identifier,
        "title": "Main",
        "role": "AXWindow",
        "subrole": "AXStandardWindow",
        "focused": focused,
        "rect": {"x": 10, "y": 20, "width": 800, "height": 600},
        "identity": {"kind": "ax_identifier", "value": identifier, "stable_across_samples": True},
    }
    return {
        "sampled_at": sampled_at,
        "status": "ready",
        "permission": {"ax_trusted": True, "prompted": False},
        "frontmost_app": {
            "name": "Notes", "pid": pid, "bundle_id": "com.apple.Notes", "role": "AXApplication"
        },
        "windows": [window],
        "source_window_count": 1,
        "windows_read_ok": True,
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
        before["source_window_count"] = 2
        after = sample(focused=True)
        after["windows"].append(dict(duplicate, focused=False))
        after["source_window_count"] = 2
        self.assertEqual(diff_samples(before, after, 2.0), [])

    def test_identifier_becoming_ambiguous_is_not_disappearance(self):
        before = sample()
        after = sample()
        after["windows"].append(dict(after["windows"][0], index=1))
        after["source_window_count"] = 2
        self.assertEqual(diff_samples(before, after, 2.0), [])

    def test_truncated_sample_does_not_claim_lifecycle(self):
        before = sample(identifier="old")
        after = sample(identifier="new")
        after["truncated"] = True
        self.assertEqual(diff_samples(before, after, 2.0), [])

    def test_focus_event_requires_complete_samples_and_boolean_values(self):
        unknown = sample(focused=False)
        unknown["windows"][0]["focused"] = None
        self.assertEqual(diff_samples(unknown, sample(focused=True), 2.0), [])

        truncated = sample(focused=False)
        truncated["truncated"] = True
        truncated["source_window_count"] = 2
        self.assertEqual(diff_samples(truncated, sample(focused=True), 2.0), [])

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
        self.assertEqual(result["drift"]["decision"]["verdict"], "drifted")
        self.assertEqual(result["drift"]["decision"]["recover"], "replan")
        self.assertEqual(result["verification"]["verdict"], "not_verified")
        self.assertEqual(result["verification"]["recover"], "replan")
        self.assertEqual(result["evidence_verification"]["verdict"], "verified")
        self.assertEqual(result["current_state"]["schema"], "agent_bridge.desktop_state.v0")
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
        self.assertEqual(result["drift"]["decision"]["verdict"], "indeterminate")

    def test_degraded_sample_does_not_emit_false_app_change(self):
        before = sample()
        after = sample(pid=8)
        after["status"] = "degraded"
        after["frontmost_app"] = None
        after["windows"] = []
        after["source_window_count"] = None
        after["windows_read_ok"] = False
        after["errors"] = ["osascript timed out"]
        self.assertEqual(diff_samples(before, after, 2.0), [])

    def test_canonical_state_ignores_timestamp_index_and_window_order(self):
        before = sample(sampled_at=1.0)
        second = copy.deepcopy(before["windows"][0])
        second.update(index=1, ax_identifier=None, title="Aux")
        second["identity"] = {
            "kind": "sample_index", "value": "1", "stable_across_samples": False
        }
        before["windows"].append(second)
        before["source_window_count"] = 2
        after = copy.deepcopy(before)
        after["sampled_at"] = 999.0
        after["windows"].reverse()
        after["windows"][0]["index"] = 91
        after["windows"][0]["identity"]["value"] = "91"

        old_state = desktop_state(before, token_max_age_ms=30_000)
        new_state = desktop_state(after, token_max_age_ms=30_000)
        self.assertNotEqual(old_state["captured_at_unix_ms"], new_state["captured_at_unix_ms"])
        self.assertEqual(
            old_state["fingerprints"]["scope"]["value"],
            new_state["fingerprints"]["scope"]["value"],
        )
        self.assertEqual(
            old_state["fingerprints"]["state"]["value"],
            new_state["fingerprints"]["state"]["value"],
        )

    def test_real_semantic_change_changes_state_hash(self):
        before = sample(focused=False)
        after = sample(focused=True)
        states = [
            desktop_state(value, token_max_age_ms=30_000) for value in (before, after)
        ]
        self.assertNotEqual(
            states[0]["fingerprints"]["state"]["value"],
            states[1]["fingerprints"]["state"]["value"],
        )
        comparison = compare_state_sequence(states)
        self.assertEqual(comparison["verdict"], "drifted")
        self.assertEqual(comparison["relation"], "same_scope")

    def test_app_change_is_scope_change_not_window_lifecycle(self):
        before = sample(pid=7, identifier="notes")
        after = sample(pid=8, identifier="finder")
        after["frontmost_app"] = {
            "name": "Finder", "pid": 8, "bundle_id": "com.apple.finder", "role": "AXApplication"
        }
        states = [
            desktop_state(value, token_max_age_ms=30_000) for value in (before, after)
        ]
        comparison = compare_state_sequence(states)
        self.assertEqual(comparison["verdict"], "scope_changed")
        self.assertEqual(comparison["relation"], "scope_changed")
        self.assertEqual(
            [event["type"] for event in diff_samples(before, after, 2.0)],
            ["frontmost_app_changed"],
        )

    def test_truncated_state_is_incomparable_and_never_unchanged(self):
        value = sample()
        value["truncated"] = True
        value["source_window_count"] = 2
        state = desktop_state(value, token_max_age_ms=30_000)
        self.assertFalse(state["coverage"]["complete"])
        self.assertIn("window_enumeration_truncated", state["coverage"]["incomplete_reasons"])
        self.assertEqual(compare_state_sequence([state, state])["verdict"], "indeterminate")

    def test_missing_process_identity_and_unconfirmed_window_read_fail_closed(self):
        missing_identity = sample()
        missing_identity["frontmost_app"] = {
            "name": None, "pid": None, "bundle_id": None, "role": None
        }
        identity_state = desktop_state(missing_identity, token_max_age_ms=30_000)
        self.assertFalse(identity_state["coverage"]["complete"])
        self.assertIn(
            "frontmost_app_identity_invalid",
            identity_state["coverage"]["incomplete_reasons"],
        )

        unreadable = sample()
        unreadable["windows"] = []
        unreadable["source_window_count"] = 0
        unreadable["windows_read_ok"] = False
        unreadable_state = desktop_state(unreadable, token_max_age_ms=30_000)
        self.assertFalse(unreadable_state["coverage"]["complete"])
        self.assertIn(
            "window_enumeration_unconfirmed",
            unreadable_state["coverage"]["incomplete_reasons"],
        )

    def test_before_token_same_state_proceeds_and_drift_replans(self):
        before = desktop_state(sample(sampled_at=1.0), token_max_age_ms=30_000)
        same = desktop_state(sample(sampled_at=2.0), token_max_age_ms=30_000)
        unchanged = compare_before_token(
            before["token"], same, now_ms=2_000, max_token_age_ms=30_000
        )
        self.assertEqual(unchanged["verdict"], "unchanged")
        self.assertEqual(unchanged["recover"], "proceed")

        changed_sample = sample(focused=True, sampled_at=2.0)
        changed = desktop_state(changed_sample, token_max_age_ms=30_000)
        drifted = compare_before_token(
            before["token"], changed, now_ms=2_000, max_token_age_ms=30_000
        )
        self.assertEqual(drifted["verdict"], "drifted")
        self.assertEqual(drifted["recover"], "replan")

    def test_stale_future_and_invalid_tokens_fail_closed(self):
        current = desktop_state(sample(sampled_at=100.0), token_max_age_ms=30_000)
        stale = copy.deepcopy(current["token"])
        stale["captured_at_unix_ms"] = 1_000
        self.assertEqual(
            compare_before_token(
                stale, current, now_ms=100_000, max_token_age_ms=30_000
            )["reason"],
            "before_token_stale",
        )
        future = copy.deepcopy(current["token"])
        future["captured_at_unix_ms"] = 100_001
        self.assertEqual(
            compare_before_token(
                future, current, now_ms=100_000, max_token_age_ms=30_000
            )["reason"],
            "before_token_from_future",
        )
        invalid = copy.deepcopy(current["token"])
        invalid["state_sha256"] = "sha256:not-a-hash"
        decision = compare_before_token(
            invalid, current, now_ms=100_000, max_token_age_ms=30_000
        )
        self.assertEqual(decision["verdict"], "indeterminate")
        self.assertEqual(decision["recover"], "replan")

        bool_age = copy.deepcopy(current["token"])
        bool_age["max_age_ms"] = True
        self.assertEqual(
            compare_before_token(
                bool_age, current, now_ms=100_000, max_token_age_ms=30_000
            )["reason"],
            "before_token_age_limit_invalid",
        )

    def test_watch_accepts_exact_prior_token(self):
        first_values = iter([sample(sampled_at=1.0), sample(sampled_at=1.1)])
        first = watch(
            sample_count=2,
            interval_secs=0.1,
            max_windows=8,
            max_events=8,
            jxa_timeout_secs=1.0,
            include_samples=False,
            sampler=lambda: next(first_values),
            sleeper=lambda _: None,
        )
        second_values = iter([sample(sampled_at=1.2), sample(sampled_at=1.3)])
        second = watch(
            sample_count=2,
            interval_secs=0.1,
            max_windows=8,
            max_events=8,
            jxa_timeout_secs=1.0,
            include_samples=False,
            before_token=first["current_state"]["token"],
            max_token_age_ms=DEFAULT_TOKEN_MAX_AGE_MS,
            sampler=lambda: next(second_values),
            sleeper=lambda _: None,
        )
        self.assertEqual(second["drift"]["against_baseline"]["verdict"], "unchanged")
        self.assertEqual(second["drift"]["decision"]["verdict"], "unchanged")
        self.assertEqual(second["drift"]["decision"]["recover"], "proceed")

    def test_watch_stale_baseline_is_top_level_incomplete(self):
        old = desktop_state(sample(sampled_at=1.0), token_max_age_ms=30_000)["token"]
        values = iter([sample(sampled_at=40.0), sample(sampled_at=40.1)])
        result = watch(
            sample_count=2,
            interval_secs=0.1,
            max_windows=8,
            max_events=8,
            jxa_timeout_secs=1.0,
            include_samples=False,
            before_token=old,
            max_token_age_ms=30_000,
            sampler=lambda: next(values),
            sleeper=lambda _: None,
        )
        self.assertEqual(result["evidence_verification"]["verdict"], "verified")
        self.assertEqual(result["drift"]["decision"]["verdict"], "indeterminate")
        self.assertEqual(result["verification"]["verdict"], "incomplete")
        self.assertEqual(result["verification"]["recover"], "replan")
        self.assertEqual(result["verification"]["reason"], "before_token_stale")


if __name__ == "__main__":
    unittest.main()
