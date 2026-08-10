from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/agent-bridge-project-truth-snapshot.py"
SPEC = importlib.util.spec_from_file_location("project_truth_snapshot", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def command(*args: str, cwd: Path) -> str:
    completed = subprocess.run(
        args, cwd=cwd, text=True, capture_output=True, check=True
    )
    return completed.stdout.strip()


class ProjectFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.repo = root / "repo"
        self.gitlab = root / "gitlab.git"
        self.github = root / "github.git"
        self.binary = root / "agent-bridge-real"
        self.repo.mkdir()
        command("git", "init", "-b", "master", cwd=self.repo)
        command("git", "config", "user.email", "test@example.invalid", cwd=self.repo)
        command("git", "config", "user.name", "Test", cwd=self.repo)
        (self.repo / "README.md").write_text("fixture\n")
        command("git", "add", "README.md", cwd=self.repo)
        command("git", "commit", "-m", "fixture", cwd=self.repo)
        self.head = command("git", "rev-parse", "HEAD", cwd=self.repo)
        command("git", "init", "--bare", str(self.gitlab), cwd=root)
        command("git", "init", "--bare", str(self.github), cwd=root)
        command("git", "remote", "add", "origin", str(self.gitlab), cwd=self.repo)
        command(
            "git",
            "remote",
            "set-url",
            "--add",
            "--push",
            "origin",
            str(self.gitlab),
            cwd=self.repo,
        )
        command(
            "git",
            "remote",
            "set-url",
            "--add",
            "--push",
            "origin",
            str(self.github),
            cwd=self.repo,
        )
        command("git", "push", "-u", "origin", "master", cwd=self.repo)
        command("git", "push", str(self.github), "master", cwd=self.repo)
        self.binary.write_text(
            "#!/bin/sh\nprintf '%s\\n' 'agent-bridge 0.14.0 (v0.14.0-1-g"
            + self.head[:7]
            + "; "
            + self.head[:12]
            + ")'\n"
        )
        self.binary.chmod(0o755)

    def snapshot(self, **overrides):
        args = {
            "remote": "origin",
            "remote_branch": "master",
            "probe_remotes": True,
            "binary": str(self.binary),
            "inspect_worktrees": True,
        }
        args.update(overrides)
        return MODULE.build_snapshot(self.repo, **args)


class ProjectTruthSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = ProjectFixture(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_aligned_clean_fixture_is_ready(self) -> None:
        packet = self.fixture.snapshot()
        self.assertEqual(packet["schema"], MODULE.SCHEMA)
        self.assertEqual(packet["verdict"], "READY_ALIGNED")
        self.assertTrue(packet["ready"])
        self.assertTrue(packet["remotes"]["consensus"])
        self.assertEqual(packet["remotes"]["consensus_sha"], self.fixture.head)
        self.assertFalse(packet["source"]["working_tree"]["dirty"])
        self.assertEqual(packet["worktrees"]["total"], 1)
        self.assertEqual(packet["worktrees"]["rows"], [])
        self.assertEqual(packet["summary"]["mismatches"], [])

    def test_dirty_checkout_is_hold_and_inventory_only(self) -> None:
        (self.fixture.repo / "local-wip.txt").write_text("do not delete\n")
        packet = self.fixture.snapshot()
        self.assertEqual(packet["verdict"], "HOLD_SOURCE_RUNTIME_REMOTE_DIVERGENCE")
        self.assertTrue(packet["source"]["working_tree"]["dirty"])
        self.assertEqual(packet["source"]["working_tree"]["untracked"], 1)
        self.assertEqual(len(packet["worktrees"]["rows"]), 1)
        self.assertIn("SOURCE_WORKTREE_DIRTY", packet["summary"]["mismatches"])
        self.assertEqual(packet["summary"]["source_dirty_entries"], 1)
        self.assertTrue((self.fixture.repo / "local-wip.txt").exists())

    def test_remote_disagreement_is_hold(self) -> None:
        (self.fixture.repo / "README.md").write_text("second\n")
        command("git", "commit", "-am", "second", cwd=self.fixture.repo)
        command(
            "git", "push", str(self.fixture.github), "master", cwd=self.fixture.repo
        )
        packet = self.fixture.snapshot()
        self.assertFalse(packet["remotes"]["consensus"])
        self.assertEqual(packet["verdict"], "HOLD_INCOMPLETE_OBSERVATION")

    def test_no_remote_probe_is_explicitly_incomplete(self) -> None:
        packet = self.fixture.snapshot(probe_remotes=False)
        self.assertEqual(packet["verdict"], "HOLD_INCOMPLETE_OBSERVATION")
        self.assertTrue(
            all(
                row["probe_status"] == "NOT_REQUESTED"
                for row in packet["remotes"]["endpoints"]
            )
        )
        self.assertFalse(packet["observed_effects"]["network_read"])

    def test_missing_binary_is_incomplete(self) -> None:
        packet = self.fixture.snapshot(binary=str(Path(self.temp.name) / "missing"))
        self.assertFalse(packet["installed_binary"]["observed"])
        self.assertEqual(packet["verdict"], "HOLD_INCOMPLETE_OBSERVATION")

    def test_semver_only_or_short_sha_binary_is_incomplete(self) -> None:
        for output in (
            "agent-bridge 0.14.0",
            "agent-bridge 0.14.0 (v0.14.0-1-gabcdef0; abcdef0)",
        ):
            with self.subTest(output=output):
                self.fixture.binary.write_text(
                    "#!/bin/sh\nprintf '%s\\n' " + repr(output) + "\n"
                )
                self.fixture.binary.chmod(0o755)
                packet = self.fixture.snapshot()
                self.assertFalse(packet["installed_binary"]["observed"])
                self.assertFalse(packet["installed_binary"]["provenance_observed"])
                self.assertEqual(packet["verdict"], "HOLD_INCOMPLETE_OBSERVATION")

    def test_endpoint_identity_never_returns_credentials(self) -> None:
        identity = MODULE.endpoint_identity(
            "https://user:secret@example.com/org/repo.git"
        )
        self.assertEqual(identity["host"], "example.com")
        self.assertEqual(identity["path"], "org/repo.git")
        self.assertTrue(identity["credentialed_url_rejected"])
        self.assertNotIn("secret", json.dumps(identity))
        query = MODULE.endpoint_identity(
            "https://example.com/org/repo.git?token=secret"
        )
        self.assertTrue(query["credentialed_url_rejected"])
        self.assertNotIn("secret", json.dumps(query))

    def test_file_and_ssh_endpoint_identity(self) -> None:
        file_identity = MODULE.endpoint_identity("file:///tmp/repo.git")
        self.assertEqual(file_identity["path"], "/tmp/repo.git")
        ssh_identity = MODULE.endpoint_identity("ssh://git@example.com/org/repo.git")
        self.assertFalse(ssh_identity["credentialed_url_rejected"])
        self.assertEqual(ssh_identity["host"], "example.com")

    def test_unobserved_source_status_is_incomplete_with_actionable_mismatch(
        self,
    ) -> None:
        unavailable = {
            "observed": False,
            "dirty": None,
            "entries": None,
            "staged": None,
            "unstaged": None,
            "untracked": None,
        }
        with mock.patch.object(MODULE, "status_counts", return_value=unavailable):
            packet = self.fixture.snapshot(inspect_worktrees=False)
        self.assertEqual(packet["verdict"], "HOLD_INCOMPLETE_OBSERVATION")
        self.assertIn(
            "SOURCE_WORKTREE_STATUS_UNOBSERVED", packet["summary"]["mismatches"]
        )
        self.assertEqual(
            packet["summary"]["next_action"],
            "complete missing source, remote, installed-binary, and worktree observations",
        )

    def test_worktree_counts_keep_unobserved_separate(self) -> None:
        rows = [
            {"status": {"observed": True, "dirty": True}},
            {"status": {"observed": True, "dirty": False}},
            {"status": {"observed": False, "dirty": None}},
        ]
        self.assertEqual(
            MODULE.worktree_status_totals(rows),
            {"dirty": 1, "clean": 1, "unobserved": 1},
        )

    def test_cli_outside_git_is_structured_hold(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--repo", self.temp.name],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(
            json.loads(completed.stdout)["verdict"], "HOLD_NOT_A_GIT_REPOSITORY"
        )
        self.assertEqual(completed.stderr, "")

    def test_snapshot_does_not_change_head_or_status(self) -> None:
        before_head = command("git", "rev-parse", "HEAD", cwd=self.fixture.repo)
        before_status = command(
            "git", "status", "--porcelain=v1", cwd=self.fixture.repo
        )
        index = self.fixture.repo / ".git" / "index"
        before_index = (index.read_bytes(), index.stat().st_mtime_ns)
        self.fixture.snapshot()
        after_index = (index.read_bytes(), index.stat().st_mtime_ns)
        after_head = command("git", "rev-parse", "HEAD", cwd=self.fixture.repo)
        after_status = command("git", "status", "--porcelain=v1", cwd=self.fixture.repo)
        self.assertEqual((before_head, before_status), (after_head, after_status))
        self.assertEqual(before_index, after_index)

    def test_binary_probe_side_effects_are_not_overclaimed(self) -> None:
        packet = self.fixture.snapshot()
        effects = packet["observed_effects"]
        self.assertTrue(effects["external_binary_probe_spawned"])
        self.assertEqual(effects["external_binary_probe_side_effects"], "unproven")


if __name__ == "__main__":
    unittest.main()
