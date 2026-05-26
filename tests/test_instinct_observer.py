import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOK = ROOT / "crates/bridge/src/hooks/ab-instinct-observer-hook.py"
AUDIT = ROOT / "scripts/instinct_density_audit.py"


def run_hook(home, payload):
    env = os.environ.copy()
    env["HOME"] = str(home)
    subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        env=env,
        check=True,
    )


def read_observations(home):
    path = home / ".cache/agent-bridge/instinct-probe/observations.jsonl"
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class InstinctObserverHookTests(unittest.TestCase):
    def test_stderr_only_success_is_not_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            run_hook(
                home,
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": "s1",
                    "cwd": str(ROOT),
                    "tool_name": "Bash",
                    "tool_input": {"command": "git clone example"},
                    "tool_response": {
                        "stdout": "ok",
                        "stderr": "Cloning into 'repo'...",
                        "exit_code": 0,
                    },
                },
            )
            rec = read_observations(home)[0]
            self.assertFalse(rec["err"])
            self.assertIsNone(rec["err_source"])
            self.assertTrue(rec["stderr_nonempty"])

    def test_explicit_nonzero_exit_code_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            run_hook(
                home,
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": "s1",
                    "cwd": str(ROOT),
                    "tool_name": "Bash",
                    "tool_input": {"command": "false"},
                    "tool_response": {"stdout": "", "stderr": "", "exit_code": 1},
                },
            )
            rec = read_observations(home)[0]
            self.assertTrue(rec["err"])
            self.assertEqual(rec["err_source"], "exit_code")


class InstinctDensityAuditTests(unittest.TestCase):
    def test_audit_separates_clean_errors_from_legacy_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = pathlib.Path(tmp) / "observations.jsonl"
            rows = [
                {
                    "ts": 1,
                    "sid": "legacy",
                    "ev": "PostToolUse",
                    "tool": "Bash",
                    "err": True,
                },
                {
                    "ts": 2,
                    "sid": "legacy",
                    "ev": "PostToolUse",
                    "tool": "Bash",
                    "err": False,
                },
                {
                    "ts": 3,
                    "sid": "clean",
                    "ev": "PostToolUse",
                    "tool": "Bash",
                    "err": True,
                    "err_source": "exit_code",
                },
                {
                    "ts": 4,
                    "sid": "clean",
                    "ev": "PostToolUse",
                    "tool": "Bash",
                    "err": False,
                },
            ]
            with log.open("w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row) + "\n")

            out = subprocess.check_output(
                [sys.executable, str(AUDIT), "--log", str(log), "--json"],
                text=True,
            )
            data = json.loads(out)
            summary = data["summary"]
            self.assertEqual(summary["total_clean_mineable"], 1)
            self.assertEqual(summary["total_legacy_upper_bound_mineable"], 2)
            self.assertEqual(summary["legacy_untrusted_errors"], 1)


if __name__ == "__main__":
    unittest.main()
