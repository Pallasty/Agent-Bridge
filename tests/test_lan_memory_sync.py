"""LAN helper acceptance using isolated Git repositories, SQLite and subprocesses.

No installed AB command, production state, SSH endpoint or service is accessed.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lan-memory-sync.py"
SPEC = importlib.util.spec_from_file_location("lan_memory_sync_under_test", SCRIPT)
LAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAN)

# The SQLite column uses VersionVector Display/FromStr's compact text, not
# serde JSON (crates/store/src/version_vector.rs). Keep it opaque in proofs.
PRODUCTION_VECTOR = "cf70d7ef01acb816:1788934278"


class LanMemorySyncTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ab-lan-helper-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Avoid loading the developer's global Git configuration or contacting
        # configured remotes. Every remote below is a temporary local bare repo.
        self.env_patch = mock.patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        })
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.remote = self.root / "lan.git"
        self.repo = self.root / "node-a"
        self.peer = self.root / "node-b"
        self.git(None, "init", "--bare", "--initial-branch=main", str(self.remote))
        self.git(None, "clone", str(self.remote), str(self.repo))
        self.configure_author(self.repo)
        self.commit(self.repo, "memory.jsonl", '{"key":"seed"}\n')
        self.git(self.repo, "push", "--set-upstream", "origin", "main")
        self.git(None, "clone", str(self.remote), str(self.peer))
        self.configure_author(self.peer)
        self.db = self.root / "isolated.db"
        with contextlib.closing(sqlite3.connect(self.db)) as con:
            con.execute("CREATE TABLE memories (key TEXT PRIMARY KEY, content TEXT, "
                        "updated_at INTEGER, status TEXT, version_vector TEXT)")
            con.execute("INSERT INTO memories VALUES (?, ?, ?, ?, ?)", (
                "handoff", "Mac 的真实交接测试内容", 1788920000, "active",
                PRODUCTION_VECTOR,
            ))
            con.commit()
        self.wrapper = self.root / "fake-sync"
        self.set_fake_sync()
        self.config = {
            "version": 1, "node": "isolated-a", "db": str(self.db),
            "locks_dir": str(self.root / "locks"),
            "state_dir": str(self.root / "state"),
            "wrapper": str(self.wrapper),
            "channels": {"lan": {
                "repo": str(self.repo), "origin": str(self.remote),
                "branch": "main", "timeout_seconds": 3,
            }},
        }
        self.channel = self.config["channels"]["lan"]
        self.env = LAN.sync_env(self.config, self.channel)

    def git(self, repo, *args):
        argv = ["git"] + (["-C", str(repo)] if repo is not None else []) + list(args)
        return subprocess.run(argv, check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True).stdout.strip()

    def configure_author(self, repo):
        self.git(repo, "config", "user.name", "Isolated LAN Test")
        self.git(repo, "config", "user.email", "lan-test@example.invalid")
        self.git(repo, "config", "commit.gpgsign", "false")

    def commit(self, repo, filename, content):
        (repo / filename).write_text(content, encoding="utf-8")
        self.git(repo, "add", filename)
        self.git(repo, "commit", "-m", "isolated fixture [skip ci]")
        return self.git(repo, "rev-parse", "HEAD")

    def set_fake_sync(self, exit_code=0, log=None):
        if log is None:
            log = ("[sync] memory import: inserted=1 updated=0 skipped=0 malformed=0 "
                   "conflict_copies=0 edges_upserted=0 edges_malformed=0 "
                   "edges_skipped_dangling=0\n[sync] no changes to push.\n")
        body = ("#!" + sys.executable + "\nimport sys\n"
                + "sys.stdout.write(" + repr(log) + ")\n"
                + "sys.exit(" + repr(exit_code) + ")\n")
        self.wrapper.write_text(body)
        self.wrapper.chmod(0o700)

    def remote_tip(self):
        return self.git(self.remote, "rev-parse", "refs/heads/main")

    def run_round(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return LAN.run_round(self.config, "lan")

    def receipt(self, name="last-round"):
        return json.loads((Path(self.config["state_dir"]) / ("lan." + name + ".json")).read_text())

    def test_committed_but_unsent_work_is_pushed_without_file_changes(self):
        head = self.commit(self.repo, "memory.jsonl", '{"key":"new-local-memory"}\n')
        self.assertEqual(self.git(self.repo, "status", "--porcelain"), "")
        self.assertNotEqual(self.remote_tip(), head)
        self.assertEqual(self.run_round(), 0)
        self.assertEqual(self.remote_tip(), head)
        receipt = self.receipt()
        self.assertEqual(receipt["retried_ahead_commits"], 1)
        self.assertEqual(receipt["published_commit"], head)
        self.assertEqual(receipt["state"], "complete")
        self.assertTrue(receipt["target_database_import"].startswith("not_claimed"))

    def test_fetch_url_drift_is_rejected_before_publish(self):
        self.git(self.repo, "remote", "set-url", "origin", str(self.root / "unexpected.git"))
        with self.assertRaisesRegex(RuntimeError, "configuration drift"):
            LAN.reconcile_push(self.config, self.channel, self.env)

    def test_extra_push_url_is_rejected_even_when_first_matches(self):
        self.git(self.repo, "config", "--add", "remote.origin.pushurl", str(self.remote))
        self.git(self.repo, "config", "--add", "remote.origin.pushurl", str(self.root / "cloud.git"))
        with self.assertRaisesRegex(RuntimeError, "configuration drift"):
            LAN.reconcile_push(self.config, self.channel, self.env)

    def test_upstream_drift_is_rejected(self):
        self.git(self.repo, "remote", "add", "other", str(self.remote))
        self.git(self.repo, "fetch", "other")
        self.git(self.repo, "branch", "--set-upstream-to=other/main", "main")
        with self.assertRaisesRegex(RuntimeError, "upstream configuration drift"):
            LAN.reconcile_push(self.config, self.channel, self.env)

    def test_configuration_is_revalidated_after_acquiring_shared_lock(self):
        original_lock = LAN.sync_lock

        @contextlib.contextmanager
        def changing_lock(config):
            self.git(self.repo, "remote", "set-url", "origin", str(self.root / "unexpected.git"))
            with original_lock(config):
                yield

        with mock.patch.object(LAN, "sync_lock", changing_lock):
            with self.assertRaisesRegex(RuntimeError, "configuration drift"):
                LAN.reconcile_push(self.config, self.channel, self.env)

    def test_disconnected_remote_is_explicit_failure_without_success_receipt(self):
        self.remote.rename(self.root / "offline.git")
        self.assertEqual(self.run_round(), 1)
        self.assertEqual(self.receipt()["state"], "failed")
        self.assertFalse((Path(self.config["state_dir"]) / "lan.last-success.json").exists())

    def test_remote_already_advanced_returns_retry_preserving_both_histories(self):
        local = self.commit(self.repo, "local.jsonl", "local payload\n")
        peer = self.commit(self.peer, "peer.jsonl", "peer payload\n")
        self.git(self.peer, "push", "origin", "main")
        result = LAN.reconcile_push(self.config, self.channel, self.env)
        self.assertEqual(result["transport_state"], "peer_advanced_retry")
        self.assertEqual((result["ahead"], result["behind"]), (1, 1))
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), local)
        self.assertEqual(self.remote_tip(), peer)

    def test_remote_racing_between_fetch_and_push_is_never_force_pushed(self):
        local = self.commit(self.repo, "local.jsonl", "local payload\n")
        peer = self.commit(self.peer, "peer.jsonl", "peer payload\n")
        original_git = LAN.git
        issued = []

        def racing_git(repo, args, env, timeout=20, check=True):
            issued.append(list(args))
            if args[0] == "push":
                self.git(self.peer, "push", "origin", "main")
            return original_git(repo, args, env, timeout, check)

        with mock.patch.object(LAN, "git", racing_git):
            with self.assertRaisesRegex(RuntimeError, "command failed"):
                LAN.reconcile_push(self.config, self.channel, self.env)
        self.assertEqual(self.remote_tip(), peer)
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), local)
        self.assertFalse(any("--force" in arg or arg.startswith("+")
                             for args in issued for arg in args))
        self.assertFalse(any(args[0] == "reset" for args in issued))

    def test_existing_shared_lock_is_not_stolen_or_modified(self):
        path = Path(self.config["locks_dir"]) / "memory-sync.lock"
        path.parent.mkdir()
        body = b'{"resource":"memory-sync","owner_pid":99999999,"acquired_at":0}'
        path.write_bytes(body)
        identity = path.stat().st_ino
        with self.assertRaises(LAN.Busy):
            LAN.reconcile_push(self.config, self.channel, self.env)
        self.assertEqual(path.read_bytes(), body)
        self.assertEqual(path.stat().st_ino, identity)

    def test_shared_lock_cleanup_does_not_remove_replacement_lock(self):
        path = Path(self.config["locks_dir"]) / "memory-sync.lock"
        with LAN.sync_lock(self.config):
            held = json.loads(path.read_text())
            self.assertEqual(held["resource"], "memory-sync")
            self.assertEqual(held["owner_pid"], os.getpid())
            path.rename(path.with_suffix(".retired"))
            path.write_text("replacement lock")
        self.assertEqual(path.read_text(), "replacement lock")

    def test_sync_skip_is_busy_and_never_records_success(self):
        self.set_fake_sync(log="[sync] another sync is already running; skipping this round\n")
        self.assertEqual(self.run_round(), 3)
        self.assertEqual(self.receipt()["state"], "busy")
        self.assertFalse((Path(self.config["state_dir"]) / "lan.last-success.json").exists())

    def test_failed_sync_does_not_overwrite_previous_success(self):
        self.assertEqual(self.run_round(), 0)
        success_path = Path(self.config["state_dir"]) / "lan.last-success.json"
        previous = success_path.read_bytes()
        self.set_fake_sync(exit_code=7)
        self.assertEqual(self.run_round(), 1)
        self.assertEqual(self.receipt()["state"], "failed")
        self.assertEqual(self.receipt()["sync_exit_code"], 7)
        self.assertEqual(success_path.read_bytes(), previous)

    def test_malformed_import_is_failure_not_complete(self):
        self.set_fake_sync(log="[sync] memory import: inserted=1 malformed=1 edges_malformed=0\n")
        self.assertEqual(self.run_round(), 1)
        self.assertEqual(self.receipt()["state"], "failed")

    def test_verify_requires_all_identity_and_revision_fields(self):
        expected = LAN.memory_proof(self.config, "handoff")
        self.assertEqual(expected["content_sha256"], hashlib.sha256("Mac 的真实交接测试内容".encode()).hexdigest())
        self.assertEqual(expected["version_vector"], PRODUCTION_VECTOR)
        self.assertTrue(LAN.memory_proof(self.config, "handoff", expected)["matches_expected"])
        changed = {
            "key": "different-key", "content_sha256": "0" * 64,
            "updated_at": expected["updated_at"] + 1, "status": "tombstoned",
            "version_vector": "cf70d7ef01acb816:1788934279",
        }
        for field, value in changed.items():
            with self.subTest(field=field):
                wrong = copy.deepcopy(expected)
                wrong[field] = value
                self.assertFalse(LAN.memory_proof(self.config, "handoff", wrong)["matches_expected"])
                del wrong[field]
                self.assertFalse(LAN.memory_proof(self.config, "handoff", wrong)["matches_expected"])

    def test_empty_legacy_vector_is_retained_and_compared_exactly(self):
        with contextlib.closing(sqlite3.connect(self.db)) as con:
            con.execute("UPDATE memories SET version_vector='' WHERE key='handoff'")
            con.commit()
        expected = LAN.memory_proof(self.config, "handoff")
        self.assertEqual(expected["version_vector"], "")
        self.assertTrue(LAN.memory_proof(self.config, "handoff", expected)["matches_expected"])
        for wrong in (None, {}, PRODUCTION_VECTOR):
            with self.subTest(wrong=wrong):
                changed = {**expected, "version_vector": wrong}
                self.assertFalse(LAN.memory_proof(self.config, "handoff", changed)["matches_expected"])
        del expected["version_vector"]
        self.assertFalse(LAN.memory_proof(self.config, "handoff", expected)["matches_expected"])

    def test_multiple_node_vector_is_retained_without_reinterpretation(self):
        vector = "2a:7,cf70d7ef01acb816:1788934278"
        with contextlib.closing(sqlite3.connect(self.db)) as con:
            con.execute("UPDATE memories SET version_vector=? WHERE key='handoff'", (vector,))
            con.commit()
        expected = LAN.memory_proof(self.config, "handoff")
        self.assertEqual(expected["version_vector"], vector)
        self.assertTrue(LAN.memory_proof(self.config, "handoff", expected)["matches_expected"])
        for wrong in ("2a:8,cf70d7ef01acb816:1788934278",
                      "2a:7,cf70d7ef01acb816:1788934279", PRODUCTION_VECTOR):
            with self.subTest(wrong=wrong):
                changed = {**expected, "version_vector": wrong}
                self.assertFalse(LAN.memory_proof(self.config, "handoff", changed)["matches_expected"])

    def test_verify_cli_accepts_compact_vector_proof_and_rejects_changed_version(self):
        config_path = self.root / "config.json"
        expected_path = self.root / "expected.json"
        config_path.write_text(json.dumps(self.config))
        expected = LAN.memory_proof(self.config, "handoff")
        expected_path.write_text(json.dumps(expected))
        argv = [sys.executable, str(SCRIPT), "--config", str(config_path),
                "verify", "--key", "handoff", "--expected", str(expected_path)]
        good = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertTrue(json.loads(good.stdout)["matches_expected"])
        expected["version_vector"] = "cf70d7ef01acb816:1788934279"
        expected_path.write_text(json.dumps(expected))
        bad = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(bad.returncode, 1, bad.stderr)
        self.assertFalse(json.loads(bad.stdout)["matches_expected"])

    def test_missing_memory_cannot_satisfy_verify(self):
        expected = LAN.memory_proof(self.config, "handoff")
        result = LAN.memory_proof(self.config, "absent", expected)
        self.assertFalse(result["exists"])
        self.assertFalse(result["matches_expected"])

    def test_tombstone_proof_requires_the_exact_persisted_status(self):
        active = LAN.memory_proof(self.config, "handoff")
        with contextlib.closing(sqlite3.connect(self.db)) as con:
            con.execute("UPDATE memories SET status='tombstoned', updated_at=updated_at+1 WHERE key='handoff'")
            con.commit()
        tombstone = LAN.memory_proof(self.config, "handoff")
        self.assertTrue(tombstone["exists"])
        self.assertEqual(tombstone["status"], "tombstoned")
        self.assertFalse(LAN.memory_proof(self.config, "handoff", active)["matches_expected"])
        self.assertTrue(LAN.memory_proof(self.config, "handoff", tombstone)["matches_expected"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
