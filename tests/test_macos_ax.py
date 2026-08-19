import argparse
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import macos_ax_probe
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

    def test_probe_does_not_fold_failed_window_read_into_empty_ready_state(self):
        payload = {
            "frontmost_app": {
                "name": "Finder", "pid": 42, "bundle_id": "com.apple.finder", "role": "AXApplication"
            },
            "windows_read_ok": False,
            "window_count": 0,
            "windows": [],
        }
        stdout = io.StringIO()
        with (
            mock.patch.object(macos_ax_probe.platform, "system", return_value="Darwin"),
            mock.patch.object(macos_ax_probe.platform, "release", return_value="test"),
            mock.patch.object(macos_ax_probe.platform, "machine", return_value="arm64"),
            mock.patch.object(macos_ax_probe, "_ax_is_trusted", return_value=(True, None)),
            mock.patch.object(macos_ax_probe, "_frontmost_jxa", return_value=(payload, None)),
            redirect_stdout(stdout),
        ):
            self.assertEqual(macos_ax_probe.main(["--compact"]), 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["status"], "degraded")
        self.assertFalse(result["windows_read_ok"])
        self.assertEqual(result["errors"][0]["stage"], "system_events_windows")


if __name__ == "__main__":
    unittest.main()
