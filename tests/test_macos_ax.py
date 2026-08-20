import argparse
import copy
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import macos_ax_probe
import macos_ax_verify
from macos_ax_probe import _annotate_window_identities
from macos_ax_verify import _match_window, _selector


def _args(**overrides):
    values = {
        "expect": "window_appeared",
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


def _app(
    *,
    name="Codex",
    pid=42,
    bundle_id="com.openai.codex",
):
    return {
        "name": name,
        "pid": pid,
        "bundle_id": bundle_id,
        "role": "AXApplication",
    }


def _window(*, title="Editor", focused=False, index=0, ax_identifier="editor"):
    return {
        "index": index,
        "ax_identifier": ax_identifier,
        "title": title,
        "role": "AXWindow",
        "subrole": "AXStandardWindow",
        "focused": focused,
        "rect": {"x": 0, "y": 0, "width": 800, "height": 600},
    }


def _jxa_payload(*, app=None, windows=None, source_count=None, windows_read_ok=True):
    windows = [] if windows is None else windows
    return {
        "frontmost_app": _app() if app is None else app,
        "windows_read_ok": windows_read_ok,
        "window_count": len(windows) if source_count is None else source_count,
        "windows": windows,
    }


def _automation_framework(
    *,
    create_status=0,
    permission_status=0,
    dispose_status=0,
    missing_symbol=None,
):
    class Framework:
        pass

    framework = Framework()
    functions = {
        "AECreateDesc": mock.Mock(return_value=create_status),
        "AEDeterminePermissionToAutomateTarget": mock.Mock(
            return_value=permission_status
        ),
        "AEDisposeDesc": mock.Mock(return_value=dispose_status),
    }
    for name, function in functions.items():
        if name != missing_symbol:
            setattr(framework, name, function)
    return framework


def _osascript_success():
    return mock.Mock(
        returncode=0,
        stdout=json.dumps(_jxa_payload()),
        stderr="",
    )


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
                "name": "Finder",
                "pid": 42,
                "bundle_id": "com.apple.finder",
                "role": "AXApplication",
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
        self.assertFalse(result["coverage_complete"])
        self.assertIn("window_enumeration_unconfirmed", result["incomplete_reasons"])
        self.assertEqual(result["errors"][0]["stage"], "system_events_windows")


class MacosAxAutomationPreflightTests(unittest.TestCase):
    def _run(self, framework):
        run = mock.Mock(return_value=_osascript_success())
        with (
            mock.patch.object(macos_ax_probe.platform, "system", return_value="Darwin"),
            mock.patch.object(macos_ax_probe.ctypes, "CDLL", return_value=framework),
            mock.patch.object(macos_ax_probe.subprocess, "run", run),
        ):
            payload, error = macos_ax_probe._frontmost_jxa(8, 1.0)
        return payload, error, run

    def test_allowed_preflight_runs_osascript_with_audited_ctypes_abi(self):
        framework = _automation_framework()
        payload, error, run = self._run(framework)

        self.assertIsNone(error)
        self.assertIsInstance(payload, dict)
        run.assert_called_once()
        framework.AEDisposeDesc.assert_called_once()
        self.assertEqual(
            framework.AECreateDesc.argtypes,
            [
                macos_ax_probe.ctypes.c_uint32,
                macos_ax_probe.ctypes.c_void_p,
                macos_ax_probe.ctypes.c_long,
                macos_ax_probe.ctypes.POINTER(macos_ax_probe._AEDesc),
            ],
        )
        self.assertIs(framework.AECreateDesc.restype, macos_ax_probe.ctypes.c_int16)
        self.assertEqual(
            framework.AEDeterminePermissionToAutomateTarget.argtypes,
            [
                macos_ax_probe.ctypes.POINTER(macos_ax_probe._AEDesc),
                macos_ax_probe.ctypes.c_uint32,
                macos_ax_probe.ctypes.c_uint32,
                macos_ax_probe.ctypes.c_ubyte,
            ],
        )
        self.assertIs(
            framework.AEDeterminePermissionToAutomateTarget.restype,
            macos_ax_probe.ctypes.c_int32,
        )
        self.assertEqual(
            framework.AEDisposeDesc.argtypes,
            [macos_ax_probe.ctypes.POINTER(macos_ax_probe._AEDesc)],
        )
        self.assertIs(framework.AEDisposeDesc.restype, macos_ax_probe.ctypes.c_int16)
        permission_call = framework.AEDeterminePermissionToAutomateTarget.call_args
        self.assertEqual(permission_call.args[1:3], (0x2A2A2A2A, 0x2A2A2A2A))
        self.assertEqual(permission_call.args[3].value, 0)

    def test_known_and_unknown_denials_fail_closed_and_dispose_once(self):
        cases = {
            -1743: "type=not_permitted",
            -1744: "type=would_require_user_consent",
            -600: "type=target_not_running",
            -9999: "type=unknown",
        }
        for status, expected in cases.items():
            with self.subTest(status=status):
                framework = _automation_framework(permission_status=status)
                payload, error, run = self._run(framework)
                self.assertIsNone(payload)
                self.assertIn("automation_preflight_permission_denied", error)
                self.assertIn(expected, error)
                self.assertIn(f"status={status}", error)
                run.assert_not_called()
                framework.AEDisposeDesc.assert_called_once()

    def test_descriptor_creation_failure_is_typed_and_does_not_dispose(self):
        framework = _automation_framework(create_status=-1700)
        payload, error, run = self._run(framework)

        self.assertIsNone(payload)
        self.assertEqual(
            error,
            "automation_preflight_descriptor_create_failed: status=-1700",
        )
        run.assert_not_called()
        framework.AEDeterminePermissionToAutomateTarget.assert_not_called()
        framework.AEDisposeDesc.assert_not_called()

    def test_missing_framework_and_symbols_fail_closed_with_typed_errors(self):
        run = mock.Mock(return_value=_osascript_success())
        with (
            mock.patch.object(macos_ax_probe.platform, "system", return_value="Darwin"),
            mock.patch.object(
                macos_ax_probe.ctypes,
                "CDLL",
                side_effect=OSError("not available"),
            ),
            mock.patch.object(macos_ax_probe.subprocess, "run", run),
        ):
            payload, error = macos_ax_probe._frontmost_jxa(8, 1.0)
        self.assertIsNone(payload)
        self.assertIn("automation_preflight_framework_unavailable", error)
        run.assert_not_called()

        for symbol in (
            "AECreateDesc",
            "AEDeterminePermissionToAutomateTarget",
            "AEDisposeDesc",
        ):
            with self.subTest(symbol=symbol):
                framework = _automation_framework(missing_symbol=symbol)
                payload, error, run = self._run(framework)
                self.assertIsNone(payload)
                self.assertEqual(
                    error,
                    f"automation_preflight_symbol_missing: {symbol}",
                )
                run.assert_not_called()

    def test_dispose_failure_blocks_osascript_after_allowed_permission(self):
        framework = _automation_framework(dispose_status=-1700)
        payload, error, run = self._run(framework)

        self.assertIsNone(payload)
        self.assertEqual(
            error,
            "automation_preflight_descriptor_dispose_failed: status=-1700",
        )
        run.assert_not_called()
        framework.AEDeterminePermissionToAutomateTarget.assert_called_once()
        framework.AEDisposeDesc.assert_called_once()

    def test_non_darwin_path_keeps_existing_osascript_behavior(self):
        run = mock.Mock(return_value=_osascript_success())
        cdll = mock.Mock()
        with (
            mock.patch.object(macos_ax_probe.platform, "system", return_value="Linux"),
            mock.patch.object(macos_ax_probe.ctypes, "CDLL", cdll),
            mock.patch.object(macos_ax_probe.subprocess, "run", run),
        ):
            payload, error = macos_ax_probe._frontmost_jxa(8, 1.0)
        self.assertIsNone(error)
        self.assertIsInstance(payload, dict)
        cdll.assert_not_called()
        run.assert_called_once()


class MacosAxVerifyCompletenessTests(unittest.TestCase):
    def _run(self, argv, payloads, *, trusted=True, ax_error=None):
        if isinstance(payloads, list):
            side_effect = [(copy.deepcopy(payload), None) for payload in payloads]
            jxa = mock.Mock(side_effect=side_effect)
        else:
            jxa = mock.Mock(return_value=(copy.deepcopy(payloads), None))
        stdout = io.StringIO()
        with (
            mock.patch.object(macos_ax_verify.platform, "system", return_value="Darwin"),
            mock.patch.object(macos_ax_verify.platform, "release", return_value="test"),
            mock.patch.object(macos_ax_verify.platform, "machine", return_value="arm64"),
            mock.patch.object(
                macos_ax_verify,
                "_ax_is_trusted",
                return_value=(trusted, ax_error),
            ),
            mock.patch.object(macos_ax_verify, "_frontmost_jxa", jxa),
            redirect_stdout(stdout),
        ):
            rc = macos_ax_verify.main(argv)
        return rc, json.loads(stdout.getvalue()), jxa

    def test_invalid_window_selector_fails_before_observation(self):
        rc, result, jxa = self._run(
            [
                "--expect",
                "window_gone",
                "--app",
                "Codex",
                "--title",
                "Editor",
                "--timeout",
                "0",
            ],
            _jxa_payload(),
        )
        self.assertEqual(rc, 3)
        self.assertEqual(result["verdict"], "error")
        self.assertEqual(result["recover"], "replan")
        self.assertEqual(result["polls"], 0)
        self.assertIn("bundle_id_or_pid", result["error"])
        jxa.assert_not_called()

    def test_selector_contract_rejects_empty_and_unstable_targets(self):
        cases = [
            (
                _args(expect="frontmost_app_is"),
                "frontmost_app_selector_required",
            ),
            (
                _args(expect="frontmost_app_is", app="   "),
                "app_must_be_nonempty",
            ),
            (
                _args(expect="frontmost_app_is", pid=True),
                "pid_must_be_positive_integer",
            ),
            (
                _args(
                    expect="window_appeared",
                    bundle_id="com.openai.codex",
                    index=0,
                ),
                "window_selector_required",
            ),
            (
                _args(
                    expect="window_gone",
                    bundle_id="com.openai.codex",
                    title="Editor",
                    index=0,
                ),
                "window_gone_cannot_use_sample_local_index",
            ),
        ]
        for args, expected in cases:
            with self.subTest(expected=expected):
                self.assertIn(expected, macos_ax_verify._selector_error(args))

    def test_window_gone_rejects_unreadable_empty_enumeration(self):
        rc, result, _ = self._run(
            [
                "--expect",
                "window_gone",
                "--bundle-id",
                "com.openai.codex",
                "--title",
                "Editor",
                "--timeout",
                "0",
            ],
            _jxa_payload(windows_read_ok=False),
        )
        self.assertEqual(rc, 3)
        self.assertEqual(result["verdict"], "error")
        self.assertNotEqual(result["recover"], "proceed")
        self.assertFalse(result["observed"]["coverage"]["complete"])
        self.assertFalse(result["observed"]["windows_read_ok"])
        self.assertIn(
            "window_enumeration_unconfirmed",
            result["observed"]["coverage"]["reasons"],
        )

    def test_window_gone_is_indeterminate_when_truncated_without_match(self):
        rc, result, _ = self._run(
            [
                "--expect",
                "window_gone",
                "--bundle-id",
                "com.openai.codex",
                "--title",
                "Editor",
                "--timeout",
                "0",
            ],
            _jxa_payload(
                windows=[_window(title="Other", ax_identifier="other")],
                source_count=2,
            ),
        )
        self.assertEqual(rc, 3)
        self.assertEqual(result["verdict"], "error")
        self.assertEqual(result["recover"], "replan")
        self.assertFalse(result["observed"]["proof"]["complete"])
        self.assertIn(
            "window_enumeration_truncated",
            result["observed"]["coverage"]["reasons"],
        )

    def test_complete_empty_enumeration_proves_window_gone(self):
        rc, result, _ = self._run(
            [
                "--expect",
                "window_gone",
                "--bundle-id",
                "com.openai.codex",
                "--title",
                "Editor",
                "--timeout",
                "0",
            ],
            _jxa_payload(),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(result["verdict"], "verified")
        self.assertEqual(result["recover"], "proceed")
        self.assertTrue(result["observed"]["coverage"]["complete"])
        self.assertTrue(result["observed"]["proof"]["complete"])
        self.assertTrue(result["observed"]["scope_match"])

    def test_truncated_positive_witness_is_still_decisive(self):
        payload = _jxa_payload(windows=[_window()], source_count=2)
        appeared_rc, appeared, _ = self._run(
            [
                "--expect",
                "window_appeared",
                "--bundle-id",
                "com.openai.codex",
                "--title",
                "Editor",
                "--timeout",
                "0",
            ],
            payload,
        )
        gone_rc, gone, _ = self._run(
            [
                "--expect",
                "window_gone",
                "--bundle-id",
                "com.openai.codex",
                "--title",
                "Editor",
                "--timeout",
                "0",
            ],
            payload,
        )
        self.assertEqual(appeared_rc, 0)
        self.assertEqual(appeared["verdict"], "verified")
        self.assertFalse(appeared["observed"]["coverage"]["complete"])
        self.assertTrue(appeared["observed"]["proof"]["complete"])
        self.assertEqual(gone_rc, 2)
        self.assertEqual(gone["verdict"], "unmet")
        self.assertEqual(gone["recover"], "retry")

    def test_unknown_window_field_cannot_prove_absence(self):
        rc, result, _ = self._run(
            [
                "--expect",
                "window_gone",
                "--bundle-id",
                "com.openai.codex",
                "--title",
                "Editor",
                "--timeout",
                "0",
            ],
            _jxa_payload(windows=[_window(title=None)]),
        )
        self.assertEqual(rc, 3)
        self.assertEqual(result["verdict"], "error")
        self.assertEqual(result["observed"]["unknown_count"], 1)
        self.assertFalse(result["observed"]["proof"]["complete"])

    def test_unknown_focus_cannot_prove_focused_or_unfocused(self):
        rc, result, _ = self._run(
            [
                "--expect",
                "window_focused",
                "--bundle-id",
                "com.openai.codex",
                "--title",
                "Editor",
                "--timeout",
                "0",
            ],
            _jxa_payload(windows=[_window(focused=None)]),
        )
        self.assertEqual(rc, 3)
        self.assertEqual(result["verdict"], "error")
        self.assertEqual(result["recover"], "replan")

    def test_focused_witness_reports_all_selector_candidates_for_exactness(self):
        rc, result, _ = self._run(
            [
                "--expect",
                "window_focused",
                "--bundle-id",
                "com.openai.codex",
                "--ax-identifier",
                "editor",
                "--timeout",
                "0",
            ],
            _jxa_payload(
                windows=[
                    _window(focused=True, index=0, ax_identifier="editor"),
                    _window(focused=False, index=1, ax_identifier="editor"),
                ]
            ),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(result["verdict"], "verified")
        self.assertEqual(result["observed"]["count"], 1)
        self.assertEqual(result["observed"]["selector_candidate_count"], 2)

    def test_focused_witness_exposes_unreadable_hidden_candidate(self):
        rc, result, _ = self._run(
            [
                "--expect",
                "window_focused",
                "--bundle-id",
                "com.openai.codex",
                "--ax-identifier",
                "editor",
                "--timeout",
                "0",
            ],
            _jxa_payload(
                windows=[
                    _window(focused=True, index=0, ax_identifier="editor"),
                    _window(focused=False, index=1, ax_identifier=None),
                ]
            ),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(result["verdict"], "verified")
        self.assertEqual(result["observed"]["count"], 1)
        self.assertEqual(result["observed"]["selector_candidate_count"], 1)
        self.assertEqual(result["observed"]["unknown_count"], 1)
        self.assertEqual(len(result["observed"]["unknowns"]), 1)

    def test_window_scope_mismatch_is_not_absence(self):
        finder = _app(name="Finder", pid=77, bundle_id="com.apple.finder")
        rc, result, _ = self._run(
            [
                "--expect",
                "window_gone",
                "--bundle-id",
                "com.openai.codex",
                "--title",
                "Editor",
                "--timeout",
                "0",
            ],
            _jxa_payload(app=finder),
        )
        self.assertEqual(rc, 3)
        self.assertEqual(result["verdict"], "error")
        self.assertEqual(result["recover"], "replan")
        self.assertFalse(result["observed"]["scope_match"])

    def test_bundle_scope_is_exact_not_substring(self):
        rc, result, _ = self._run(
            [
                "--expect",
                "window_gone",
                "--bundle-id",
                "openai.codex",
                "--title",
                "Editor",
                "--timeout",
                "0",
            ],
            _jxa_payload(),
        )
        self.assertEqual(rc, 3)
        self.assertEqual(result["verdict"], "error")
        self.assertFalse(result["observed"]["scope_match"])

    def test_invalid_source_count_cannot_prove_absence(self):
        for source_count in (None, True, -1):
            with self.subTest(source_count=source_count):
                payload = _jxa_payload()
                payload["window_count"] = source_count
                rc, result, _ = self._run(
                    [
                        "--expect",
                        "window_gone",
                        "--bundle-id",
                        "com.openai.codex",
                        "--title",
                        "Editor",
                        "--timeout",
                        "0",
                    ],
                    payload,
                )
                self.assertEqual(rc, 3)
                self.assertEqual(result["verdict"], "error")
                self.assertNotEqual(result["recover"], "proceed")

    def test_invalid_frontmost_identity_cannot_enter_window_scope(self):
        invalid_apps = [
            _app(pid=True),
            _app(pid=0),
            _app(name=None, bundle_id=None),
        ]
        for app in invalid_apps:
            with self.subTest(app=app):
                rc, result, _ = self._run(
                    [
                        "--expect",
                        "window_gone",
                        "--bundle-id",
                        "com.openai.codex",
                        "--title",
                        "Editor",
                        "--timeout",
                        "0",
                    ],
                    _jxa_payload(app=app),
                )
                self.assertEqual(rc, 3)
                self.assertNotEqual(result["verdict"], "verified")
                self.assertNotEqual(result["recover"], "proceed")

    def test_frontmost_app_proof_does_not_depend_on_window_enumeration(self):
        rc, result, _ = self._run(
            [
                "--expect",
                "frontmost_app_is",
                "--bundle-id",
                "com.openai.codex",
                "--timeout",
                "0",
            ],
            _jxa_payload(windows_read_ok=False),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(result["verdict"], "verified")
        self.assertEqual(result["recover"], "proceed")
        self.assertFalse(result["observed"]["coverage"]["complete"])
        self.assertTrue(result["observed"]["proof"]["complete"])

    def test_ax_trust_verification_does_not_run_jxa(self):
        rc, result, jxa = self._run(
            [
                "--expect",
                "ax_trusted_is",
                "--state",
                "false",
                "--timeout",
                "0",
            ],
            _jxa_payload(),
            trusted=False,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(result["verdict"], "verified")
        self.assertTrue(result["observed"]["proof"]["complete"])
        jxa.assert_not_called()

    def test_unknown_ax_trust_fails_closed_without_running_jxa(self):
        rc, result, jxa = self._run(
            [
                "--expect",
                "ax_trusted_is",
                "--state",
                "true",
                "--timeout",
                "0",
            ],
            _jxa_payload(),
            trusted=None,
            ax_error="AXIsProcessTrusted failed",
        )
        self.assertEqual(rc, 3)
        self.assertEqual(result["verdict"], "error")
        self.assertEqual(result["recover"], "escalate")
        jxa.assert_not_called()

    def test_polling_can_recover_after_scope_returns(self):
        finder = _jxa_payload(
            app=_app(name="Finder", pid=77, bundle_id="com.apple.finder")
        )
        target = _jxa_payload()
        rc, result, jxa = self._run(
            [
                "--expect",
                "window_gone",
                "--bundle-id",
                "com.openai.codex",
                "--title",
                "Editor",
                "--timeout",
                "0.2",
                "--poll-interval",
                "0.05",
            ],
            [finder, target],
        )
        self.assertEqual(rc, 0)
        self.assertEqual(result["verdict"], "verified")
        self.assertEqual(result["polls"], 2)
        self.assertEqual(jxa.call_count, 2)

    def test_non_verified_results_never_proceed(self):
        for verdict in ("unmet", "error"):
            with self.subTest(verdict=verdict):
                self.assertNotEqual(
                    macos_ax_verify._recover("window_gone", verdict, "incomplete_evidence"),
                    "proceed",
                )


if __name__ == "__main__":
    unittest.main()
