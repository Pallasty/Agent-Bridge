from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/preflight-macos-trusted-deployment.py"
SPEC = importlib.util.spec_from_file_location("macos_trusted_preflight", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, argv):
        command = tuple(argv)
        self.commands.append(command)
        if command[:3] == ("/bin/ls", "-ldeO@", command[2]):
            return MODULE.CommandResult(0, "drwx------  2 owner staff 64 root\n")
        if command[:3] == ("/usr/bin/stat", "-f", "%T"):
            return MODULE.CommandResult(0, "apfs\n")
        if command[:3] == ("/usr/bin/codesign", "--verify", "--strict"):
            return MODULE.CommandResult(0, "")
        if command[:3] == ("/usr/bin/codesign", "-dv", "--verbose=4"):
            return MODULE.CommandResult(0, "", "Identifier=agent-bridge\n")
        if command[:2] == ("/bin/launchctl", "print"):
            return MODULE.CommandResult(0, "\tpath = /Library/LaunchAgents/test.plist\n\tprogram = /trusted/agent-bridge\n")
        if command[:3] == ("/usr/sbin/lsof", "-n", "-Fpcufn"):
            return MODULE.CommandResult(1, "")
        raise AssertionError(f"unexpected command: {command}")


class DarwinTrustedPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "trusted"
        self.root.mkdir(mode=0o700)
        self.root.chmod(0o700)
        self.binary = self.base / "agent-bridge.real"
        self.binary.write_bytes(b"darwin fixture")
        self.binary.chmod(0o755)
        self.database = self.base / "state.db"
        self.database.write_bytes(b"sqlite fixture")
        self.runner = FakeRunner()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_complete_snapshot_is_ready_and_deterministic(self) -> None:
        first = MODULE.build_preflight(
            root=self.root, installed_binary=self.binary,
            state_database=self.database, runner=self.runner, system="Darwin",
        )
        second = MODULE.build_preflight(
            root=self.root, installed_binary=self.binary,
            state_database=self.database, runner=self.runner, system="Darwin",
        )
        self.assertEqual(first, second)
        self.assertEqual(first["verdict"], "READY")
        self.assertTrue(first["read_only"])
        self.assertFalse(first["action_performed"])
        self.assertFalse(first["permission_requested"])
        forbidden = {"mkdir", "chmod", "chown", "bootstrap", "bootout", "kickstart", "open"}
        self.assertTrue(forbidden.isdisjoint(word for command in self.runner.commands for word in command))

    def test_missing_root_reports_hold_without_creating_it(self) -> None:
        missing = self.base / "missing"
        result = MODULE.build_preflight(
            root=missing, installed_binary=self.base / "missing-bin",
            state_database=self.base / "missing.db", runner=self.runner,
            system="Darwin",
        )
        self.assertEqual(result["verdict"], "HOLD")
        self.assertIn("ROOT_OR_ANCESTOR_ABSENT", result["blockers"])
        self.assertFalse(missing.exists())

    def test_wrong_platform_and_cloud_root_fail_closed(self) -> None:
        cloud = Path("/Users/example/Library/CloudStorage/AgentBridge")
        result = MODULE.build_preflight(
            root=cloud, installed_binary=self.base / "missing-bin",
            state_database=self.base / "missing.db", runner=self.runner,
            system="Linux",
        )
        self.assertIn("PLATFORM_NOT_DARWIN", result["blockers"])
        self.assertIn("ROOT_CLOUD_SYNCHRONIZED", result["blockers"])

    def test_extended_metadata_and_unsupported_filesystem_are_blockers(self) -> None:
        def runner(argv):
            if argv[0:2] == ("/bin/ls", "-ldeO@"):
                return MODULE.CommandResult(0, "drwx------ root\n 0: group:everyone deny delete\n")
            if argv[0:3] == ("/usr/bin/stat", "-f", "%T"):
                return MODULE.CommandResult(0, "nfs\n")
            return self.runner(argv)

        result = MODULE.build_preflight(
            root=self.root, installed_binary=self.binary,
            state_database=self.database, runner=runner, system="Darwin",
        )
        self.assertIn("ROOT_EXTENDED_METADATA_PRESENT", result["blockers"])
        self.assertIn("ROOT_FILESYSTEM_NOT_LOCAL_SUPPORTED", result["blockers"])

    def test_sqlite_sidecar_and_open_descriptor_fail_closed(self) -> None:
        Path(str(self.database) + "-wal").write_bytes(b"wal")

        def runner(argv):
            if argv[0:3] == ("/usr/sbin/lsof", "-n", "-Fpcufn"):
                return MODULE.CommandResult(0, "p123\ncagent-bridge\nf12u\n")
            return self.runner(argv)

        result = MODULE.build_preflight(
            root=self.root, installed_binary=self.binary,
            state_database=self.database, runner=runner, system="Darwin",
        )
        self.assertIn("SQLITE_SIDECAR_PRESENT", result["blockers"])
        self.assertIn("SQLITE_OPEN_DESCRIPTOR_PRESENT", result["blockers"])

    def test_no_write_or_permission_api_is_used(self) -> None:
        with mock.patch.object(Path, "mkdir", side_effect=AssertionError("write")), \
             mock.patch.object(Path, "write_bytes", side_effect=AssertionError("write")), \
             mock.patch.object(os, "chmod", side_effect=AssertionError("write")):
            result = MODULE.build_preflight(
                root=self.root, installed_binary=self.binary,
                state_database=self.database, runner=self.runner, system="Darwin",
            )
        self.assertEqual(result["verdict"], "READY")


if __name__ == "__main__":
    unittest.main()
