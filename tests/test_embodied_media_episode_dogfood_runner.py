import hashlib
import importlib.util
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load("embodied_media_runner", "scripts/embodied-media-episode-dogfood-runner.py")
fixtures = load("embodied_media_collector_fixtures", "tests/test_embodied_media_episode_dogfood_collector.py")


class FakeClient:
    def __init__(self, calls, fail_at=None):
        self.calls = list(calls)
        self.seen = []
        self.fail_at = fail_at

    def call_tool(self, tool, args):
        index = len(self.seen)
        self.seen.append((tool, args))
        if self.fail_at == index:
            raise runner.RunnerError(tool, "injected_failure")
        expected_tool, payload = self.calls.pop(0)
        if expected_tool != tool:
            raise AssertionError(f"expected {expected_tool}, got {tool}")
        return payload


class MemorySink:
    def __init__(self, fail_at=None):
        self.items = []
        self.fail_at = fail_at

    def write(self, index, tool, payload):
        if self.fail_at == index:
            raise runner.RunnerError(tool, "receipt_write_failed")
        self.items.append((index, tool, payload))


def op():
    value = "pair03-operation"
    return value, hashlib.sha256(value.encode()).hexdigest()


def run(client, sink, side="baseline", cleanup=None):
    operation_id, digest = op()
    ticks = iter((10.0, 11.0))
    return runner.run_side(
        client,
        pair_id="embodied-media-pair-03",
        side=side,
        operation_id=operation_id,
        operation_id_sha256=digest,
        player="rhythmbox",
        serial="private-serial",
        bind="192.168.1.16",
        sink=sink,
        clock=lambda: next(ticks),
        adb_cleanup=cleanup,
    )


class RunnerTests(unittest.TestCase):
    def test_baseline_success_is_decided_by_collector(self):
        bundle = fixtures.baseline_bundle()
        calls = [(item["tool"], item["payload"]) for item in bundle["receipts"]]
        client = FakeClient(calls)
        result = run(client, MemorySink())
        self.assertEqual(result["status"], "VERIFIED_PRIVATE_RECEIPTS_NORMALIZED")
        self.assertEqual(result["agent_orchestration_calls"], 7)
        self.assertEqual([tool for tool, _ in client.seen], list(runner.collector.BASELINE_TOOLS))

    def test_trial_success_is_exactly_pending_then_composite(self):
        bundle = fixtures.trial_bundle()
        calls = [(item["tool"], item["payload"]) for item in bundle["receipts"]]
        result = run(FakeClient(calls), MemorySink(), side="trial")
        self.assertEqual(result["agent_orchestration_calls"], 2)

    def test_sync_binding_failure_stops_known_session(self):
        bundle = fixtures.baseline_bundle()
        prefix = bundle["receipts"][:5]
        prefix[4]["payload"]["projection_update"]["revision"] = 0
        stop = bundle["receipts"][6]
        client = FakeClient([(x["tool"], x["payload"]) for x in prefix + [stop]])
        fallback = []
        with self.assertRaisesRegex(runner.RunnerError, "projection_binding_missing"):
            run(client, MemorySink(), cleanup=lambda serial: fallback.append(serial) or True)
        self.assertEqual(client.seen[-1][0], "mobile_projection_stop")
        self.assertEqual(fallback, [])

    def test_lost_start_response_uses_allowlisted_fallback_cleanup(self):
        bundle = fixtures.baseline_bundle()
        calls = [(x["tool"], x["payload"]) for x in bundle["receipts"][:3]]
        client = FakeClient(calls, fail_at=2)
        fallback = []
        with self.assertRaisesRegex(runner.RunnerError, "injected_failure"):
            run(client, MemorySink(), cleanup=lambda serial: fallback.append(serial) or True)
        self.assertEqual(fallback, ["private-serial"])

    def test_stop_failure_retries_then_falls_back_and_never_collects(self):
        bundle = fixtures.baseline_bundle()
        calls = [(x["tool"], x["payload"]) for x in bundle["receipts"][:6]]
        client = FakeClient(calls, fail_at=6)
        fallback = []
        with self.assertRaises(runner.RunnerError):
            run(client, MemorySink(), cleanup=lambda serial: fallback.append(serial) or True)
        self.assertGreaterEqual(sum(1 for tool, _ in client.seen if tool == "mobile_projection_stop"), 2)
        self.assertEqual(fallback, ["private-serial"])

    def test_receipt_sink_failure_after_start_uses_fallback(self):
        bundle = fixtures.baseline_bundle()
        calls = [(x["tool"], x["payload"]) for x in bundle["receipts"][:3]]
        fallback = []
        with self.assertRaisesRegex(runner.RunnerError, "receipt_write_failed"):
            run(FakeClient(calls), MemorySink(fail_at=3), cleanup=lambda serial: fallback.append(serial) or True)
        self.assertEqual(fallback, ["private-serial"])

    def test_operation_hash_mismatch_precedes_any_call(self):
        client = FakeClient([])
        with self.assertRaisesRegex(runner.RunnerError, "operation_id_hash_mismatch"):
            runner.run_side(
                client, pair_id="embodied-media-pair-03", side="trial",
                operation_id="pair03-operation", operation_id_sha256="0" * 64,
                player="rhythmbox", serial="private", bind="192.168.1.16",
                sink=MemorySink(),
            )
        self.assertEqual(client.seen, [])

    def test_all_public_bindings_are_validated_before_pending_dispatch(self):
        operation_id, digest = op()
        cases = [
            {"pair_id":"bad","serial":"private","bind":"192.168.1.16","owner_restatements":0},
            {"pair_id":"embodied-media-pair-03","serial":"","bind":"192.168.1.16","owner_restatements":0},
            {"pair_id":"embodied-media-pair-03","serial":"private","bind":"not-an-ip","owner_restatements":0},
            {"pair_id":"embodied-media-pair-03","serial":"private","bind":"192.168.1.16","owner_restatements":True},
        ]
        for values in cases:
            client = FakeClient([])
            with self.assertRaises(runner.RunnerError):
                runner.run_side(
                    client, side="trial", operation_id=operation_id,
                    operation_id_sha256=digest, player="rhythmbox",
                    sink=MemorySink(), manual_interventions=0, **values,
                )
            self.assertEqual(client.seen, [])

    def test_trial_failure_without_verified_cleanup_uses_fallback(self):
        bundle = fixtures.trial_bundle()
        bundle["receipts"][1]["payload"]["cleanup"]["verified"] = False
        client = FakeClient([(x["tool"], x["payload"]) for x in bundle["receipts"]])
        fallback = []
        with self.assertRaises(runner.collector.ContractError):
            run(client, MemorySink(), side="trial", cleanup=lambda serial: fallback.append(serial) or True)
        self.assertEqual(fallback, ["private-serial"])

    def test_collector_rejection_cannot_be_upgraded_by_runner(self):
        bundle = fixtures.baseline_bundle()
        bundle["receipts"][5]["payload"]["draw_report"]["frame_sha256"] = "d" * 64
        client = FakeClient([(x["tool"], x["payload"]) for x in bundle["receipts"]])
        with self.assertRaises(runner.collector.ContractError):
            run(client, MemorySink())

    def test_private_sink_is_owner_only_and_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "receipts"
            sink = runner.PrivateReceiptSink(path)
            sink.write(1, "app_control", {"private": "value"})
            receipt = path / "01-app_control.json"
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
            with self.assertRaisesRegex(runner.RunnerError, "receipt_write_failed"):
                sink.write(1, "app_control", {})

    def test_private_sink_rejects_existing_directory_without_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(runner.RunnerError, "receipt_directory_unavailable"):
                runner.PrivateReceiptSink(pathlib.Path(tmp))

    def test_fallback_force_stop_uses_only_fixed_argv(self):
        self.assertEqual(runner.COMPANION_PACKAGE, "dev.agentbridge.companion")
        completed = subprocess.CompletedProcess([], 0)
        with mock.patch.object(runner.subprocess, "run", return_value=completed) as called:
            self.assertTrue(runner.fallback_force_stop("/usr/bin/adb", "serial-01", 7.0))
        called.assert_called_once_with(
            ["/usr/bin/adb", "-s", "serial-01", "shell", "am", "force-stop", runner.COMPANION_PACKAGE],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=7.0, check=False,
        )

    def test_rejected_output_is_content_free(self):
        result = runner.rejected(runner.RunnerError("sync", "collector_contract_rejected"))
        self.assertEqual(set(result), {"schema", "status", "phase", "code", "enrollment_allowed", "runtime_influence_allowed"})
        self.assertFalse(result["enrollment_allowed"])


if __name__ == "__main__":
    unittest.main()
