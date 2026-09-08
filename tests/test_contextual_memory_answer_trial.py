"""No-provider tests for isolation, provenance and failed-run retention."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts/eval"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("contextual_answer_trial", SCRIPTS / "contextual_memory_answer_trial.py")
assert SPEC and SPEC.loader
TRIAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRIAL)


class FakeMcp:
    instances = []
    fail_search = False

    def __init__(self, binary, cwd, db_path, stderr_path, timeout, child_env=None):
        self.env, self.closed, self.calls = child_env, False, []
        self.db = sqlite3.connect(db_path)
        self.db.execute("CREATE TABLE IF NOT EXISTS memories (key TEXT, embedding_backend TEXT)")
        stderr_path.write_text("fake MCP diagnostics\n")
        self.instances.append(self)

    def request(self, method, args):
        self.calls.append((method, args))
        if method == "initialize":
            return {"serverInfo": {"name": "fake", "version": "test"}}, 1
        if args["name"] == "memory_save":
            self.db.execute("INSERT INTO memories VALUES (?, 'fnv1a-hash-384')", (args["arguments"]["key"],))
            self.db.commit()
            return {"content": [{"type": "text", "text": "saved"}]}, 2
        if self.fail_search:
            return {"isError": True, "content": [{"type": "text", "text": "raw failure reason"}]}, 3
        return {"content": [{"type": "text", "text": json.dumps([
            {"record": {"key": "memory-alpha", "content": "普通来源内容"}}
        ])}]}, 3

    def notify(self, method):
        pass

    def close(self):
        self.closed = True
        self.db.close()


class ContextualAnswerTrialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.input = self.root / "input.json"
        self.spec = {
            "trial_id": "INTERNAL_TRIAL_ONLY", "common_instruction": "根据给出的记忆回答请求。",
            "memories": [{"key": "memory-alpha", "kind": "fact", "content": "普通来源内容", "scope": "domain:trial"}],
            "cases": [{"case_id": "internal_case", "query": "自然检索词", "as_of": 100,
                       "scope": "domain:trial", "request": "请说明目前情况。",
                       "required_claims": ["GOLD_SECRET"], "reference_answer": "REFERENCE_SECRET"}],
        }
        self.save_input()
        self.binary = self.root / "fake-binary"
        self.binary.write_bytes(b"fake binary")
        FakeMcp.instances = []
        FakeMcp.fail_search = False

    def save_input(self):
        TRIAL.write_json(self.input, self.spec)

    def capture(self, name="capture"):
        directory = self.root / name
        with patch.object(TRIAL, "McpClient", FakeMcp), patch.object(
            TRIAL.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "fake version", "")
        ):
            result = TRIAL.capture(self.input, directory, self.binary, 10)
        return directory, result

    def test_prompt_excludes_internal_and_gold_fields(self):
        prompt = TRIAL.build_prompt(self.spec, self.spec["cases"][0], "OBSERVED_MEMORY")
        for forbidden in ("INTERNAL_TRIAL_ONLY", "internal_case", "GOLD_SECRET", "REFERENCE_SECRET", "自然检索词"):
            self.assertNotIn(forbidden, prompt)
        for required in ("请说明目前情况", "T100", "OBSERVED_MEMORY", "150"):
            self.assertIn(required, prompt)

    def test_input_rejects_bool_as_time(self):
        self.spec["cases"][0]["as_of"] = True
        self.save_input()
        with self.assertRaises(TRIAL.TrialError):
            TRIAL.read_input(self.input)

    def test_mcp_environment_is_allowlisted_and_home_preserved(self):
        creds = self.root / "empty"
        creds.touch()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "secret", "AGENT_BRIDGE_DB": "/production.db",
                                   "AGENT_BRIDGE_LLM_ENDPOINT": "private", "HOME": "/original-home"}):
            env = TRIAL.clean_mcp_env(creds)
        self.assertEqual(env["HOME"], "/original-home")
        self.assertEqual(env["AGENT_BRIDGE_EMBED_BACKEND"], "hash")
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("AGENT_BRIDGE_DB", env)
        self.assertFalse(any(key.startswith("AGENT_BRIDGE_LLM_") for key in env))

    def test_mcp_helper_preserves_legacy_env_but_accepts_explicit_clean_env(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-secret"}), patch(
            "portfolio_continuity_ab_trial.subprocess.Popen"
        ) as process:
            process.return_value.returncode = 0
            legacy = TRIAL.McpClient(self.binary, self.root, self.root / "legacy.db", self.root / "legacy.stderr", 10)
            self.assertEqual(process.call_args.kwargs["env"]["OPENAI_API_KEY"], "test-only-secret")
            legacy.close()
            supplied = {"HOME": "/original-home"}
            isolated = TRIAL.McpClient(self.binary, self.root, self.root / "isolated.db", self.root / "isolated.stderr", 10, child_env=supplied)
            effective = process.call_args.kwargs["env"]
            self.assertNotIn("OPENAI_API_KEY", effective)
            self.assertEqual(effective["AGENT_BRIDGE_DB"], str(self.root / "isolated.db"))
            self.assertEqual(effective["AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS"], "eval")
            self.assertEqual(supplied, {"HOME": "/original-home"})
            isolated.close()

    def test_credentials_must_exist_empty_and_regular(self):
        creds = self.root / "credentials"
        for setup in (lambda: None, lambda: creds.write_text("secret")):
            setup()
            with self.assertRaises(TRIAL.TrialError):
                TRIAL.clean_mcp_env(creds)
        creds.unlink()
        creds.symlink_to(self.input)
        with self.assertRaises(TRIAL.TrialError):
            TRIAL.clean_mcp_env(creds)

    def test_capture_fixed_search_no_backfill_and_seed_closed_before_backup(self):
        real_backup = TRIAL.sqlite_backup
        def checked_backup(source, destination):
            self.assertTrue(all(client.closed for client in FakeMcp.instances))
            real_backup(source, destination)
        with patch.object(TRIAL, "sqlite_backup", side_effect=checked_backup):
            directory, result = self.capture()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["backend_observed"], [("fnv1a-hash-384", 1)])
        row = result["cases"][0]
        self.assertEqual(row["returned_keys"], ["memory-alpha"])
        self.assertEqual(row["search_arguments"], {"query": "自然检索词", "mode": "hybrid",
                         "scope": "domain:trial", "scope_mode": "local_only", "limit": 8, "compact": False})
        self.assertEqual(len(FakeMcp.instances), 2)
        self.assertEqual([args["name"] for method, args in FakeMcp.instances[1].calls if method == "tools/call"], ["memory_search"])
        self.assertTrue((directory / "internal_case/context.txt").exists())

    def test_capture_refuses_existing_output_before_starting_child(self):
        output = self.root / "existing"
        output.mkdir()
        with patch.object(TRIAL, "McpClient") as child, self.assertRaises(TRIAL.TrialError):
            TRIAL.capture(self.input, output, self.binary, 10)
        child.assert_not_called()

    def test_capture_keeps_raw_tool_error_and_manifest(self):
        FakeMcp.fail_search = True
        with self.assertRaises(TRIAL.TrialError):
            self.capture()
        directory = self.root / "capture"
        manifest = json.loads((directory / "manifest.json").read_text())
        raw = json.loads((directory / "internal_case/memory_search.json").read_text())
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(raw["raw_result"]["content"][0]["text"], "raw failure reason")
        self.assertTrue(all(client.closed for client in FakeMcp.instances))

    def test_generation_rejects_changed_input_before_provider(self):
        capture, _ = self.capture()
        self.spec["cases"][0]["request"] = "changed task"
        self.save_input()
        with patch.object(TRIAL.subprocess, "Popen") as child, self.assertRaises(TRIAL.TrialError):
            TRIAL.generate(self.input, capture, self.root / "answers", None, 10, str(self.binary))
        child.assert_not_called()
        self.assertFalse((self.root / "answers").exists())

    def test_generation_rejects_changed_capture_before_provider(self):
        capture, _ = self.capture()
        (capture / "internal_case/context.txt").write_text("injected")
        with patch.object(TRIAL.subprocess, "Popen") as child, self.assertRaises(TRIAL.TrialError):
            TRIAL.generate(self.input, capture, self.root / "answers", None, 10, str(self.binary))
        child.assert_not_called()

    def test_command_disables_tools_hooks_memories_and_uses_current_model(self):
        command = TRIAL.codex_command("codex", self.root, self.root / "answer")
        for feature in ("hooks", "shell_tool", "apps", "plugins", "memories", "external_agent_memory_import"):
            index = command.index(feature)
            self.assertEqual(command[index - 1], "--disable")
        self.assertIn("--ignore-user-config", command)
        self.assertIn("--ignore-rules", command)
        self.assertIn("gpt-6-astra", command)
        self.assertIn('model_reasoning_effort="medium"', command)
        self.assertEqual(command[-1], "-")

    def test_generation_failure_retains_all_artifacts_and_never_retries(self):
        capture, _ = self.capture()
        class FailedProcess:
            returncode = 7
            def __init__(self, command, **kwargs):
                self.stdin_data = None
                kwargs["stdout"].write(b'{"type":"turn.failed","error":{"message":"failed"}}\n')
                kwargs["stderr"].write(b"provider diagnostic\n")
            def communicate(self, data=None, timeout=None):
                self.stdin_data = data
        with patch.object(TRIAL.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "fake CLI", "")), patch.object(
            TRIAL.subprocess, "Popen", side_effect=FailedProcess
        ) as child:
            result = TRIAL.generate(self.input, capture, self.root / "answers", None, 10, str(self.binary))
        self.assertEqual(child.call_count, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["cases"][0]["exit_status"], 7)
        directory = self.root / "answers/internal_case"
        for name in ("prompt.txt", "stdout.jsonl", "stderr.txt", "answer.txt", "result.json"):
            self.assertTrue((directory / name).is_file(), name)
        self.assertTrue(result["cases"][0]["neutral_workspace_removed"])

    def test_generation_with_tool_event_is_not_admissible_even_with_answer(self):
        capture, _ = self.capture()
        class ToolUsingProcess:
            returncode = 0
            def __init__(self, command, **kwargs):
                Path(command[command.index("--output-last-message") + 1]).write_text("一份可读回答")
                kwargs["stdout"].write(b'{"type":"item.completed","item":{"type":"mcp_tool_call","tool":"memory_search"}}\n')
                kwargs["stdout"].write(b'{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}\n')
            def communicate(self, data=None, timeout=None):
                pass
        with patch.object(TRIAL.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "fake CLI", "")), patch.object(
            TRIAL.subprocess, "Popen", side_effect=ToolUsingProcess
        ):
            result = TRIAL.generate(self.input, capture, self.root / "answers", None, 10, str(self.binary))
        row = result["cases"][0]
        self.assertEqual(row["exit_status"], 0)
        self.assertFalse(row["admissible"])
        self.assertEqual(row["unexpected_item_event_count"], 1)
        self.assertEqual(row["event_metadata"][0]["usage"]["input_tokens"], 10)
        self.assertEqual(result["status"], "failed")

    def test_generation_success_retains_usage_and_requires_observed_completion(self):
        capture, _ = self.capture()
        class AnswerProcess:
            returncode = 0
            def __init__(self, command, **kwargs):
                assert all("internal_case" not in argument for argument in command)
                assert "internal_case" not in str(kwargs["cwd"])
                assert list(kwargs["cwd"].iterdir()) == []
                Path(command[command.index("--output-last-message") + 1]).write_text("正常回答")
                kwargs["stdout"].write(b'{"type":"item.completed","item":{"type":"agent_message","text":"answer"}}\n')
                kwargs["stdout"].write(b'{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}\n')
            def communicate(self, data=None, timeout=None):
                pass
        with patch.object(TRIAL.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "fake CLI", "")), patch.object(
            TRIAL.subprocess, "Popen", side_effect=AnswerProcess
        ):
            result = TRIAL.generate(self.input, capture, self.root / "answers", None, 10, str(self.binary))
        row = result["cases"][0]
        self.assertTrue(row["admissible"])
        self.assertEqual(row["completed_turn_count"], 1)
        self.assertEqual(row["observed_item_types"], ["agent_message"])
        self.assertIsNone(row["actual_model"])
        self.assertTrue(row["provider_workspace_initially_empty"])
        self.assertTrue(row["neutral_workspace_removed"])
        self.assertEqual(result["status"], "complete")

    def test_timeout_stops_owned_process_group_and_retains_failure(self):
        capture, _ = self.capture()
        class TimedOutProcess:
            pid = 98765
            returncode = -9
            calls = 0
            def __init__(self, command, **kwargs):
                self.command = command
                self.started_own_group = kwargs["start_new_session"]
            def communicate(self, data=None, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired(self.command, timeout)
        with patch.object(TRIAL.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "fake CLI", "")), patch.object(
            TRIAL.subprocess, "Popen", side_effect=TimedOutProcess
        ) as child, patch.object(TRIAL.os, "killpg") as kill:
            result = TRIAL.generate(self.input, capture, self.root / "answers", None, 10, str(self.binary))
        self.assertEqual(child.call_count, 1)
        self.assertTrue(child.call_args.kwargs["start_new_session"])
        kill.assert_called_once_with(98765, TRIAL.signal.SIGKILL)
        self.assertTrue(result["cases"][0]["timed_out"])
        self.assertFalse(result["cases"][0]["admissible"])
        self.assertTrue((self.root / "answers/internal_case/result.json").is_file())

    def test_only_exact_disabled_host_diagnostic_is_admissible(self):
        directory = self.root / "events"
        directory.mkdir()
        (directory / "answer.txt").write_text("保留原回答")
        for message, expected in ((TRIAL.DISABLED_HOST_DIAGNOSTIC, True),
                                  (TRIAL.DISABLED_HOST_DIAGNOSTIC + " unexpected", False),
                                  ("Unknown tool error", False)):
            events = [{"type": "item.completed", "item": {"type": "error", "message": message}},
                      {"type": "item.completed", "item": {"type": "agent_message", "text": "保留原回答"}},
                      {"type": "turn.completed", "usage": {"output_tokens": 5}}]
            (directory / "stdout.jsonl").write_text("\n".join(json.dumps(event) for event in events))
            row = {"exit_status": 0}
            TRIAL.classify_answer(directory, row)
            self.assertEqual(row["admissible"], expected)
            self.assertEqual(row["known_disabled_host_diagnostic_count"], int(expected))
            self.assertEqual(row["unexpected_item_event_count"], int(not expected))

    def test_reclassification_preserves_original_receipt_answer_and_never_runs_provider(self):
        generation = self.root / "generation"
        directory = generation / "internal_case"
        directory.mkdir(parents=True)
        (directory / "answer.txt").write_text("原回答一次保留")
        events = [{"type": "item.completed", "item": {"type": "error", "message": TRIAL.DISABLED_HOST_DIAGNOSTIC}},
                  {"type": "item.completed", "item": {"type": "agent_message", "text": "原回答一次保留"}},
                  {"type": "turn.completed", "usage": {"output_tokens": 5}}]
        (directory / "stdout.jsonl").write_text("\n".join(json.dumps(event) for event in events))
        original = {"phase": "generate", "status": "failed", "trial_id": "test",
                    "source_sha256": TRIAL.source_hashes(self.input),
                    "cases": [{"case_id": "internal_case", "exit_status": 0, "status": "failed"}]}
        TRIAL.finish(generation, original)
        before = {str(path): TRIAL.sha(path) for path in generation.rglob("*") if path.is_file()}
        with patch.object(TRIAL.subprocess, "Popen") as child, patch.object(TRIAL.subprocess, "run") as process:
            result = TRIAL.reclassify(self.input, generation, self.root / "reclassified")
        child.assert_not_called()
        process.assert_not_called()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result["cases"][0]["known_disabled_host_diagnostic_count"], 1)
        self.assertEqual(before, {str(path): TRIAL.sha(path) for path in generation.rglob("*") if path.is_file()})


if __name__ == "__main__":
    unittest.main()
