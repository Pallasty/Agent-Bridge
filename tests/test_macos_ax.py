import argparse
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from macos_ax_probe import _annotate_window_identities
from macos_ax_verify import _match_window, _selector


def _args(**overrides):
    values = {
        "app": None,
        "bundle_id": None,
        "pid": None,
        "title": None,
        "role": None,
        "index": None,
        "ax_identifier": None,
        "state": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class MacosAxIdentityTests(unittest.TestCase):
    def test_ax_identifier_is_marked_stable(self):
        windows = _annotate_window_identities(
            [{"index": 3, "ax_identifier": "window-main"}]
        )
        self.assertEqual(
            windows[0]["identity"],
            {
                "kind": "ax_identifier",
                "value": "window-main",
                "stable_across_samples": True,
            },
        )

    def test_missing_ax_identifier_is_explicitly_sample_local(self):
        windows = _annotate_window_identities([{"index": 3, "ax_identifier": None}])
        self.assertEqual(
            windows[0]["identity"],
            {
                "kind": "sample_index",
                "value": "3",
                "stable_across_samples": False,
            },
        )

    def test_verify_matches_ax_identifier_exactly(self):
        window = {
            "index": 0,
            "ax_identifier": "window-main",
            "title": "Document",
            "role": "AXWindow",
        }
        self.assertTrue(_match_window(window, _args(ax_identifier="window-main")))
        self.assertFalse(_match_window(window, _args(ax_identifier="WINDOW-MAIN")))

    def test_selector_exposes_ax_identifier(self):
        selector = _selector(_args(ax_identifier="window-main"))
        self.assertEqual(selector["ax_identifier"], "window-main")


if __name__ == "__main__":
    unittest.main()
