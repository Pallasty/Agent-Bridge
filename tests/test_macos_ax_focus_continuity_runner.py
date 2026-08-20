import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/macos-ax-focus-continuity-runner.py"
SPEC = importlib.util.spec_from_file_location("macos_ax_focus_continuity_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


TARGET = {
    "pid": 4242,
    "bundle_id": "com.openai.codex",
    "ax_identifier": "target-window",
    "expected_role": "AXWindow",
    "expected_title": "Target",
}


def window(identifier, title, focused):
    return {
        "index": 0 if identifier == "target-window" else 1,
        "ax_identifier": identifier,
        "title": title,
        "role": "AXWindow",
        "focused": focused,
        "identity": {
            "kind": "ax_identifier",
            "value": identifier,
            "stable_across_samples": True,
        },
    }


def probe():
    windows = [window("target-window", "Target", False), window("other-window", "Other", True)]
    return {
        "schema": "macos_ax_probe/v0",
        "status": "ready",
        "read_only": True,
        "platform": {"system": "Darwin"},
        "permission": {"ax_trusted": True, "prompted": False},
        "frontmost_app": {"name": "Codex", "pid": 4242, "bundle_id": "com.openai.codex"},
        "windows": windows,
        "window_count": 2,
        "source_window_count": 2,
        "windows_read_ok": True,
        "app_identity_valid": True,
        "counts_consistent": True,
        "coverage_complete": True,
        "incomplete_reasons": [],
        "limits": {"max_windows": 50, "truncated": False, "include_windows": True},
        "errors": [],
    }


def admission():
    return {
        "schema": "macos_ax_action_admission/v1",
        "status": "preview_only",
        "operation": "focus_window",
        "risk": {"class": "embodied_navigation", "rank": 1},
        "decision": "admit",
        "execution": {"performed": False, "executor_present": False},
        "authority": {"scope": "owner_standing", "per_action_prompt_default": False},
        "preconditions": {"target_exact": True, "receipt_complete": True, "target_bound": True, "surface_fresh": True},
    }


def focus():
    return {
        "schema": "macos_ax_focus_transaction/v0",
        "status": "verified",
        "operation": "focus_window",
        "read_only": False,
        "target": {"pid": 4242, "bundle_id": "com.openai.codex", "selector": {"ax_identifier": "target-window", "expected_role": "AXWindow", "expected_title": "Target"}},
        "verification": {"verdict": "verified", "independent_contract_ok": True, "recover": "proceed"},
        "mcp_wrapper": {"transaction_closed": True},
    }


def verify(*, verified=True):
    selector = {"bundle_id": "com.openai.codex", "pid": 4242, "ax_identifier": "target-window", "role": "AXWindow", "title": "Target"}
    return {
        "schema": "agent_bridge.semantic_bus.macos_ax_verify.v0",
        "read_only": True,
        "semantic_objects": [{"state": {"expect": "window_focused", "selector": selector, "source_verdict": "verified" if verified else "unmet", "source_recover": "proceed" if verified else "retry"}}],
        "verification": {
            "verdict": "verified" if verified else "not_verified",
            "source_verdict": "verified" if verified else "unmet",
            "recover": "proceed" if verified else "reobserve",
            "reason": None if verified else "postcondition_unmet",
            "evidence": {
                "expect": "window_focused", "selector": selector,
                "wrapper_exit_code": 0, "proof_complete": True,
                "proof_truth": "match" if verified else "no_match",
                "scope_match": True, "coverage_complete": True,
                "windows_read_ok": True, "app_identity_valid": True,
                "counts_consistent": True, "truncated": False,
            },
        },
    }


class FakeClient:
    def __init__(self, overrides=None):
        self.calls = []
        self.overrides = overrides or {}

    def call_tool(self, name, args):
        self.calls.append((name, args))
        if name in self.overrides:
            value = self.overrides[name]
            return value() if callable(value) else value
        if name == "embodiment_lease":
            if args.get("op") == "acquire":
                return {"schema": "agent_bridge.embodiment_lease.v0", "op": "acquire", "acquired": True, "lease_id": "lease-1"}
            return {"schema": "agent_bridge.embodiment_lease.v0", "op": "release", "released": True, "lease_id": args.get("lease_id")}
        return {
            "macos_ax_probe": probe(),
            "macos_ax_action_admission": admission(),
            "macos_ax_focus_transaction": focus(),
            "macos_ax_verify": verify(),
        }[name]


class FocusContinuityRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.journal = pathlib.Path(self.temp.name) / "journal"
        self.journal.mkdir(mode=0o700)

    def tearDown(self):
        self.temp.cleanup()

    def execute_episode(self, client, operation_id="focus-op-1", **kwargs):
        return RUNNER.run_episode(
            client,
            operation_id=operation_id,
            target=dict(TARGET),
            journal_directory=self.journal,
            operation_ttl_secs=3600,
            clock=kwargs.pop("clock", lambda: 1000.0),
            **kwargs,
        )

    def record(self, operation_id="focus-op-1"):
        key = hashlib.sha256(operation_id.encode()).hexdigest()
        return json.loads((self.journal / f"{key}.json").read_text())

    def test_fresh_verified_dispatches_once_and_terminal_replay_is_read_only(self):
        first_client = FakeClient()
        first = self.execute_episode(first_client)
        self.assertEqual(first["status"], "verified")
        self.assertEqual(first["dispatch_count"], 1)
        self.assertTrue(first["focus_dispatch_invoked_in_this_call"])
        self.assertFalse(first["recovered_after_interruption"])
        self.assertEqual(
            [name for name, _ in first_client.calls],
            ["macos_ax_probe", "macos_ax_action_admission", "embodiment_lease", "macos_ax_focus_transaction", "embodiment_lease"],
        )
        self.assertEqual(self.record()["phase"], "terminal")

        replay_client = FakeClient()
        replay = self.execute_episode(replay_client)
        self.assertEqual(replay_client.calls, [])
        self.assertTrue(replay["idempotent_replay"])
        self.assertFalse(replay["external_execution_repeated"])
        self.assertFalse(replay["focus_dispatch_invoked_in_this_call"])
        self.assertTrue(replay["focus_dispatch_invoked_in_originating_call"])

    def test_registered_response_loss_recovers_read_only_without_redispatch(self):
        first_client = FakeClient()
        lost = self.execute_episode(first_client, fault_injection=RUNNER.FAULT)
        self.assertEqual(lost["status"], "response_lost")
        self.assertEqual(self.record()["phase"], "dispatch_started")
        self.assertEqual(self.record()["dispatch_count"], 1)
        self.assertIn("macos_ax_focus_transaction", [name for name, _ in first_client.calls])
        self.assertEqual([name for name, _ in first_client.calls].count("embodiment_lease"), 2)

        recovery_client = FakeClient()
        recovered = self.execute_episode(recovery_client)
        self.assertEqual([name for name, _ in recovery_client.calls], ["macos_ax_verify"])
        self.assertEqual(recovered["status"], "verified")
        self.assertTrue(recovered["recovered_after_interruption"])
        self.assertEqual(recovered["causal_attribution"], "unknown_after_interruption")
        self.assertFalse(recovered["redispatched"])
        self.assertFalse(recovered["focus_dispatch_invoked_in_this_call"])
        self.assertEqual(self.record()["phase"], "terminal")

    def test_incomplete_recovery_remains_dispatch_started_and_never_dispatches(self):
        self.execute_episode(FakeClient(), fault_injection=RUNNER.FAULT)
        client = FakeClient({"macos_ax_verify": verify(verified=False)})
        result = self.execute_episode(client)
        self.assertEqual(result["status"], "reobserve")
        self.assertEqual([name for name, _ in client.calls], ["macos_ax_verify"])
        self.assertEqual(self.record()["phase"], "dispatch_started")
        self.assertEqual(self.record()["dispatch_count"], 1)

    def test_prepared_crash_point_retries_admission_then_dispatches_once(self):
        unavailable = FakeClient({"embodiment_lease": {"schema": "agent_bridge.embodiment_lease.v0", "op": "acquire", "acquired": False}})
        with self.assertRaisesRegex(RUNNER.RunnerError, "lease_acquire_failed"):
            self.execute_episode(unavailable)
        self.assertEqual(self.record()["phase"], "prepared")
        self.assertEqual(self.record()["dispatch_count"], 0)

        resumed = FakeClient()
        result = self.execute_episode(resumed)
        self.assertEqual(result["status"], "verified")
        self.assertEqual([name for name, _ in resumed.calls].count("macos_ax_focus_transaction"), 1)

    def test_prepared_resume_rechecks_expiry_after_lease_before_dispatch(self):
        unavailable = FakeClient({"embodiment_lease": {"schema": "agent_bridge.embodiment_lease.v0", "op": "acquire", "acquired": False}})
        with self.assertRaisesRegex(RUNNER.RunnerError, "lease_acquire_failed"):
            self.execute_episode(unavailable)
        record = self.record()
        record["expires_at"] = 1000.5
        key = hashlib.sha256(b"focus-op-1").hexdigest()
        path = self.journal / f"{key}.json"
        path.write_text(json.dumps(record))
        os.chmod(path, 0o600)
        times = iter((1000.0, 1000.0, 1001.0))
        client = FakeClient()
        with self.assertRaisesRegex(RUNNER.RunnerError, "operation_expired"):
            self.execute_episode(client, clock=lambda: next(times))
        names = [name for name, _ in client.calls]
        self.assertNotIn("macos_ax_focus_transaction", names)
        self.assertEqual(names[-2:], ["embodiment_lease", "embodiment_lease"])
        self.assertEqual(self.record()["phase"], "prepared")

    def test_unverified_lease_cleanup_never_terminalizes(self):
        def lease_response():
            lease_calls = [args for name, args in client.calls if name == "embodiment_lease"]
            if lease_calls[-1]["op"] == "acquire":
                return {"schema": "agent_bridge.embodiment_lease.v0", "op": "acquire", "acquired": True, "lease_id": "lease-1"}
            return {"schema": "agent_bridge.embodiment_lease.v0", "op": "release", "released": False, "lease_id": "lease-1"}

        client = FakeClient({"embodiment_lease": lease_response})
        with self.assertRaisesRegex(RUNNER.RunnerError, "lease_cleanup_not_verified"):
            self.execute_episode(client)
        self.assertEqual(self.record()["phase"], "dispatch_started")
        self.assertEqual(self.record()["dispatch_count"], 1)

    def test_forged_terminal_receipt_is_not_replayed(self):
        self.execute_episode(FakeClient())
        record = self.record()
        record["receipt"]["redispatched"] = True
        key = hashlib.sha256(b"focus-op-1").hexdigest()
        path = self.journal / f"{key}.json"
        path.write_text(json.dumps(record))
        os.chmod(path, 0o600)
        client = FakeClient()
        with self.assertRaisesRegex(RUNNER.RunnerError, "terminal_receipt_invalid"):
            self.execute_episode(client)
        self.assertEqual(client.calls, [])

    def test_probe_requires_two_complete_distinct_stable_windows(self):
        bad = probe()
        bad["windows"] = bad["windows"][:1]
        bad["window_count"] = 1
        bad["source_window_count"] = 1
        client = FakeClient({"macos_ax_probe": bad})
        with self.assertRaisesRegex(RUNNER.RunnerError, "two_distinct_stable_windows_required"):
            self.execute_episode(client)
        self.assertEqual([name for name, _ in client.calls], ["macos_ax_probe"])
        self.assertFalse(list(self.journal.glob("*.json")))

    def test_already_focused_target_is_ineligible_without_dispatch(self):
        bad = probe()
        bad["windows"][0]["focused"] = True
        client = FakeClient({"macos_ax_probe": bad})
        with self.assertRaisesRegex(RUNNER.RunnerError, "target_must_start_unfocused"):
            self.execute_episode(client)
        self.assertNotIn("macos_ax_focus_transaction", [name for name, _ in client.calls])

    def test_same_id_different_request_and_expired_record_fail_before_tools(self):
        self.execute_episode(FakeClient(), fault_injection=RUNNER.FAULT)
        changed = dict(TARGET)
        changed["ax_identifier"] = "other-window"
        client = FakeClient()
        with self.assertRaisesRegex(RUNNER.RunnerError, "invalid_or_conflicting"):
            RUNNER.run_episode(client, operation_id="focus-op-1", target=changed, journal_directory=self.journal, operation_ttl_secs=3600, clock=lambda: 1000.0)
        self.assertEqual(client.calls, [])

        record = self.record()
        record["expires_at"] = 1000.5
        key = hashlib.sha256(b"focus-op-1").hexdigest()
        (self.journal / f"{key}.json").write_text(json.dumps(record))
        os.chmod(self.journal / f"{key}.json", 0o600)
        expired_client = FakeClient()
        with self.assertRaisesRegex(RUNNER.RunnerError, "operation_expired"):
            self.execute_episode(expired_client, clock=lambda: 1001.0)
        self.assertEqual(expired_client.calls, [])

    def test_corrupt_record_and_busy_lock_fail_closed(self):
        key = hashlib.sha256(b"focus-op-1").hexdigest()
        path = self.journal / f"{key}.json"
        path.write_text("not-json")
        os.chmod(path, 0o600)
        with self.assertRaisesRegex(RUNNER.RunnerError, "operation_record_invalid"):
            self.execute_episode(FakeClient())

        path.unlink()
        held = RUNNER.OperationJournal(self.journal, "focus-op-1")
        try:
            with self.assertRaisesRegex(RUNNER.RunnerError, "operation_lock_busy"):
                self.execute_episode(FakeClient())
        finally:
            held.close()

    def test_wrong_types_and_relative_journal_are_rejected(self):
        for target in (
            {**TARGET, "pid": True},
            {**TARGET, "ax_identifier": " bad"},
            {**TARGET, "expected_role": ""},
        ):
            with self.subTest(target=target):
                with self.assertRaises(RUNNER.RunnerError):
                    RUNNER.canonical_request("focus-op-1", target, 3600)
        with self.assertRaisesRegex(RUNNER.RunnerError, "journal_directory_not_absolute"):
            RUNNER.OperationJournal(pathlib.Path("relative"), "focus-op-1")


if __name__ == "__main__":
    unittest.main()
