"""Deterministic unit tests for desktop_verify decision logic.

The live AT-SPI/sway behaviour is exercised by the cage acceptance harness; here we
pin the pure functions that map observations -> verdict -> recover hint, since those
are what a caller's loop depends on."""
import argparse
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import desktop_verify as dv  # noqa: E402


def ns(**kw):
    base = dict(
        expect="element_gone", app=None, role=None, name=None, nth=0, cage_pid=None,
        state=None, win_app_id=None, win_pid=None, win_title=None, swaysock=None,
        timeout=1.0, poll_interval=0.3, settle=0.0, before_present=None, before_focus=None,
        search_budget=2.0, search_max_nodes=2000, search_max_depth=32,
        compact=True,
    )
    base.update(kw)
    return argparse.Namespace(**base)


class RecoverHintTests(unittest.TestCase):
    def test_truth_table(self):
        # verified -> proceed regardless of change
        self.assertEqual(dv.recover_hint("verified", None), "proceed")
        self.assertEqual(dv.recover_hint("verified", "unchanged"), "proceed")
        # error -> escalate
        self.assertEqual(dv.recover_hint("error", None), "escalate")
        # unmet + diverged -> replan (state moved unexpectedly: do NOT blindly retry)
        self.assertEqual(dv.recover_hint("unmet", "diverged"), "replan")
        # unmet + unchanged (or unknown) -> retry (idempotent retry is safe)
        self.assertEqual(dv.recover_hint("unmet", "unchanged"), "retry")
        self.assertEqual(dv.recover_hint("unmet", None), "retry")


class WindowMatchesTests(unittest.TestCase):
    def test_requires_at_least_one_selector(self):
        win = {"app_id": "zenity", "pid": 10, "title": "Save?"}
        self.assertFalse(dv.window_matches(win, None, None, None))

    def test_app_id_substring(self):
        win = {"app_id": "org.gnome.zenity", "pid": 10, "title": "Save?"}
        self.assertTrue(dv.window_matches(win, "zenity", None, None))
        self.assertFalse(dv.window_matches(win, "firefox", None, None))

    def test_pid_exact_and_title_substring(self):
        win = {"app_id": "zenity", "pid": 4242, "title": "Really delete?"}
        self.assertTrue(dv.window_matches(win, None, 4242, None))
        self.assertFalse(dv.window_matches(win, None, 4243, None))
        self.assertTrue(dv.window_matches(win, None, None, "delete"))
        # combined: all provided must hold
        self.assertTrue(dv.window_matches(win, "zenity", 4242, "delete"))
        self.assertFalse(dv.window_matches(win, "zenity", 4242, "save"))

    def test_title_matches_the_sway_name_key(self):
        # regression: sway windows carry the title under 'name' (desktop_snapshot
        # _walk_tree), NOT 'title'. win_title matching must read 'name' or it silently
        # never matches (the latent bug the act-loop dogfood surfaced).
        win = {"app_id": "zenity", "pid": 7, "name": "Really delete?"}
        self.assertTrue(dv.window_matches(win, None, None, "delete"))
        self.assertEqual(dv._win_title(win), "Really delete?")
        # 'title' is still accepted as a fallback for any caller that set it
        self.assertEqual(dv._win_title({"title": "X"}), "X")
        self.assertEqual(dv._win_title({}), "")


class ClassifyChangeTests(unittest.TestCase):
    def test_element_unchanged_when_presence_equals_before(self):
        # expected gone, was present, STILL present -> nothing moved -> unchanged
        obs = {"count": 1}
        self.assertEqual(dv.classify_change(ns(expect="element_gone", before_present=True), obs), "unchanged")

    def test_element_diverged_when_presence_flips_unexpectedly(self):
        # expected gone, was ABSENT before, now present -> appeared unexpectedly -> diverged
        obs = {"count": 1}
        self.assertEqual(dv.classify_change(ns(expect="element_gone", before_present=False), obs), "diverged")

    def test_no_before_means_no_change_label(self):
        self.assertIsNone(dv.classify_change(ns(expect="element_gone", before_present=None), {"count": 1}))

    def test_focus_unchanged_when_still_on_before_target(self):
        obs = {"focused": {"app_id": "cursor", "title": "agent-bridge - Cursor"}}
        a = ns(expect="focus_is", before_focus="cursor|agent-bridge - Cursor")
        self.assertEqual(dv.classify_change(a, obs), "unchanged")

    def test_focus_diverged_when_moved_elsewhere(self):
        obs = {"focused": {"app_id": "firefox", "title": "Mozilla"}}
        a = ns(expect="focus_is", before_focus="cursor|agent-bridge")
        self.assertEqual(dv.classify_change(a, obs), "diverged")


class ExitCodeTests(unittest.TestCase):
    def test_unknown_expect_is_rejected_by_argparse(self):
        # argparse choices guard: a bogus expect must not silently run
        with self.assertRaises(SystemExit):
            dv.parser().parse_args(["--expect", "teleport"])

    def test_help_does_not_require_pyatspi(self):
        with self.assertRaises(SystemExit) as cm:
            dv.parser().parse_args(["--help"])
        self.assertEqual(cm.exception.code, 0)


class BoundedResolutionTests(unittest.TestCase):
    def test_state_is_uses_resolved_match_states(self):
        original = dv.resolve_atspi_matches
        dv.resolve_atspi_matches = lambda *args, **kwargs: (
            [{"states": ["checked", "enabled"]}], None, {"complete": True}
        )
        try:
            holds, observed, error = dv.evaluate(
                ns(expect="state_is", app="player", state="checked")
            )
        finally:
            dv.resolve_atspi_matches = original
        self.assertTrue(holds)
        self.assertEqual(observed["count"], 1)
        self.assertIsNone(error)

    def test_state_expectation_without_state_fails_closed(self):
        holds, observed, error = dv.evaluate(ns(expect="state_is", app="player"))
        self.assertFalse(holds)
        self.assertEqual(observed, {})
        self.assertEqual(error["code"], "invalid_expectation")

    def test_state_expectation_rejects_unknown_state(self):
        holds, _, error = dv.evaluate(
            ns(expect="state_not", app="player", state="teleported")
        )
        self.assertFalse(holds)
        self.assertEqual(error["code"], "invalid_expectation")

    def test_element_expectation_without_selector_fails_closed(self):
        holds, _, error = dv.evaluate(ns(expect="element_gone"))
        self.assertFalse(holds)
        self.assertEqual(error["code"], "invalid_expectation")

    def test_window_expectation_without_selector_fails_closed(self):
        holds, _, error = dv.evaluate(ns(expect="focus_is"))
        self.assertFalse(holds)
        self.assertEqual(error["code"], "invalid_expectation")

    def test_incomplete_search_cannot_verify_element_gone(self):
        coverage = {"complete": False, "stop_reason": "node_budget"}
        original = dv.resolve_atspi_matches
        dv.resolve_atspi_matches = lambda *args, **kwargs: ([], None, coverage)
        try:
            holds, observed, error = dv.evaluate(ns(expect="element_gone", app="large"))
        finally:
            dv.resolve_atspi_matches = original
        self.assertFalse(holds)
        self.assertEqual(observed["search"], coverage)
        self.assertEqual(error["code"], "search_incomplete")

    def test_incomplete_search_replans_instead_of_retrying(self):
        coverage = {"complete": False, "stop_reason": "time_budget"}
        original = dv.resolve_atspi_matches
        dv.resolve_atspi_matches = lambda *args, **kwargs: ([], None, coverage)
        try:
            result = dv.run(ns(expect="state_not", app="large", state="checked", timeout=0))
        finally:
            dv.resolve_atspi_matches = original
        self.assertEqual(result["verdict"], "error")
        self.assertEqual(result["recover"], "replan")
        self.assertEqual(result["error"]["code"], "search_incomplete")

    def test_verify_forwards_exact_nth_to_shared_resolver(self):
        seen = []
        original = dv.find_element
        original_pyatspi = sys.modules.get("pyatspi")
        dv.find_element = lambda app, role, name, nth, **kwargs: (
            seen.append(nth) or (None, None, None, {"complete": True})
        )
        sys.modules["pyatspi"] = object()
        try:
            matches, error, coverage = dv.resolve_atspi_matches(
                "large", "button", None, 3, None
            )
        finally:
            dv.find_element = original
            if original_pyatspi is None:
                sys.modules.pop("pyatspi", None)
            else:
                sys.modules["pyatspi"] = original_pyatspi
        self.assertEqual(seen, [3])
        self.assertEqual(matches, [])
        self.assertIsNone(error)
        self.assertTrue(coverage["complete"])


if __name__ == "__main__":
    unittest.main()
