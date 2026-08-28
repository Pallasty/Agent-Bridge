from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify-r9-installed-deployment.py"
SPEC = importlib.util.spec_from_file_location("verify_r9_installed_deployment", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InstalledFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.binary = root / "agent-bridge.real"
        self.binary.write_bytes(b"fixture installed agent bridge\n")
        self.binary.chmod(0o755)
        self.expected_sha256 = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        self.expected_commit = "a" * 40

        self.receipt_root = root / "production-receipts"
        self.receipt_root.mkdir(mode=0o700)
        self.receipt_root.chmod(0o700)

        self.systemd_runtime_base = root / "run-user"
        self.systemd_runtime_base.mkdir(mode=0o755)
        self.systemd_runtime_dir = self.systemd_runtime_base / str(os.geteuid())
        self.systemd_runtime_dir.mkdir(mode=0o700)
        self.systemd_runtime_dir.chmod(0o700)
        self.systemd_bus = self.systemd_runtime_dir / "bus"
        self.systemd_bus_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.systemd_bus_socket.bind(str(self.systemd_bus))
        self.systemd_environment = {
            "XDG_RUNTIME_DIR": str(self.systemd_runtime_dir),
            "DBUS_SESSION_BUS_ADDRESS": f"unix:path={self.systemd_bus}",
        }

        self.proc_root = root / "proc"
        self.proc_root.mkdir()
        self.identifiers = {
            "agent-bridge-daemon.service": 900000001,
            "agent-bridge-daemon-http.service": 900000002,
            "agent-bridge-palace.service": 900000003,
        }
        for identifier in self.identifiers.values():
            process = self.proc_root / str(identifier)
            process.mkdir()
            (process / "exe").symlink_to(self.binary)
            (process / "environ").write_bytes(
                b"IGNORED_SECRET=never-publish-this\0"
                + b"AGENT_BRIDGE_CGROUP_RECEIPT_DIR="
                + os.fsencode(self.receipt_root)
                + b"\0"
            )

        self.service_active = {unit: True for unit in self.identifiers}
        self.version_stdout = (
            b"agent-bridge 0.14.0 (v0.14.0-1-gaaaaaaa; aaaaaaaaaaaa)\n"
        )
        self.doctor_stdout = json.dumps(
            {
                "ok": True,
                "fails": 0,
                "warns": 0,
                "checks": [{"name": "workload_receipt_root", "status": "ok"}],
            }
        ).encode("utf-8")
        self.health_bodies = {7878: b"ok", 7979: b"ok"}
        self.commands: list[tuple[str, ...]] = []
        self.command_environments: list[dict[str, str] | None] = []

    def runner(
        self,
        argv: list[str],
        _timeout: int,
        explicit_env: dict[str, str] | None,
    ):
        self.commands.append(tuple(argv))
        self.command_environments.append(explicit_env)
        if argv == [str(self.binary), "--version"]:
            if explicit_env is not None:
                raise AssertionError("version must not receive an explicit override")
            return MODULE.CommandObservation(0, self.version_stdout)
        if argv == [str(self.binary), "doctor", "--json"]:
            expected_environment = dict(self.systemd_environment)
            expected_environment["AGENT_BRIDGE_CGROUP_RECEIPT_DIR"] = str(
                self.receipt_root
            )
            if explicit_env != expected_environment:
                raise AssertionError("doctor receipt-root binding mismatch")
            return MODULE.CommandObservation(0, self.doctor_stdout)
        if argv[0] == MODULE.SYSTEMCTL and argv[1:3] == ["--user", "show"]:
            if explicit_env != self.systemd_environment:
                raise AssertionError("systemctl user-bus binding mismatch")
            unit = argv[3]
            active = self.service_active[unit]
            identifier = self.identifiers[unit] if active else 0
            output = (
                "LoadState=loaded\n"
                f"ActiveState={'active' if active else 'inactive'}\n"
                f"MainPID={identifier}\n"
            ).encode("utf-8")
            return MODULE.CommandObservation(0, output)
        raise AssertionError(f"unexpected command shape: {argv!r}")

    def health_reader(self, port: int, target: str, _timeout: float):
        if target != "/healthz" or port not in self.health_bodies:
            raise AssertionError("unexpected health target")
        return MODULE.HttpObservation(200, self.health_bodies[port])

    def verify(self, **overrides):
        arguments = {
            "binary": str(self.binary),
            "expected_sha256": self.expected_sha256,
            "expected_commit": self.expected_commit,
            "receipt_root": str(self.receipt_root),
            "runner": self.runner,
            "health_reader": self.health_reader,
            "proc_root": self.proc_root,
            "systemd_runtime_base": self.systemd_runtime_base,
            "euid": os.geteuid(),
        }
        arguments.update(overrides)
        return MODULE.verify_installed_deployment(**arguments)


class InstalledDeploymentVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.fixture = InstalledFixture(Path(self.temporary.name))

    def tearDown(self) -> None:
        self.fixture.systemd_bus_socket.close()
        self.temporary.cleanup()

    def test_complete_fake_installed_snapshot_passes_and_is_privacy_bounded(self) -> None:
        report = self.fixture.verify()

        self.assertEqual(report["schema"], MODULE.SCHEMA)
        self.assertEqual(report["verdict"], "PASS")
        self.assertTrue(report["read_only"])
        self.assertEqual(report["failures"], [])
        self.assertTrue(
            all(row["status"] == "PASS" for row in report["checks"].values())
        )
        self.assertEqual(
            report["security_boundaries"],
            {
                "installed_binary": {"status": "PASS"},
                "production_receipt_root": {"status": "PASS"},
            },
        )

        rendered = json.dumps(report, sort_keys=True)
        self.assertNotIn(str(self.fixture.root), rendered)
        self.assertNotIn("/proc/", rendered)
        self.assertNotIn("never-publish-this", rendered)
        for identifier in self.fixture.identifiers.values():
            self.assertNotIn(str(identifier), rendered)

        command_words = [word for command in self.fixture.commands for word in command]
        for mutating_word in ("start", "restart", "stop", "kill", "enable"):
            self.assertNotIn(mutating_word, command_words)
        systemctl_commands = [
            command
            for command in self.fixture.commands
            if command[0] == MODULE.SYSTEMCTL
        ]
        self.assertEqual(len(systemctl_commands), 12)
        self.assertTrue(all(command[2] == "show" for command in systemctl_commands))
        doctor_index = self.fixture.commands.index(
            (str(self.fixture.binary), "doctor", "--json")
        )
        self.assertEqual(
            self.fixture.command_environments[doctor_index],
            {
                **self.fixture.systemd_environment,
                "AGENT_BRIDGE_CGROUP_RECEIPT_DIR": str(self.fixture.receipt_root),
            },
        )

    def test_binary_and_receipt_security_boundaries_fail_independently(self) -> None:
        self.fixture.binary.chmod(0o775)
        self.fixture.receipt_root.chmod(0o750)

        report = self.fixture.verify()

        self.assertEqual(report["verdict"], "FAIL_CLOSED")
        self.assertEqual(
            report["security_boundaries"]["installed_binary"]["status"], "FAIL"
        )
        self.assertEqual(
            report["security_boundaries"]["production_receipt_root"]["status"],
            "FAIL",
        )
        self.assertEqual(
            report["checks"]["binary_owner_permissions"]["status"], "FAIL"
        )
        self.assertEqual(
            report["checks"]["binary_content_sha256"]["status"], "PASS"
        )
        self.assertEqual(
            report["checks"]["binary_version_commit"]["status"], "NOT_RUN"
        )
        self.assertIn("BINARY_GROUP_OR_OTHER_WRITABLE", report["failures"])
        self.assertIn("RECEIPT_ROOT_MODE_NOT_0700", report["failures"])

    def test_writable_direct_parent_fails_both_replacement_boundaries(self) -> None:
        self.fixture.root.chmod(0o777)

        report = self.fixture.verify()

        self.assertEqual(
            report["checks"]["binary_owner_permissions"]["status"], "FAIL"
        )
        self.assertEqual(
            report["checks"]["receipt_root_owner_mode"]["status"], "FAIL"
        )
        self.assertIn(
            "BINARY_PARENT_GROUP_OR_OTHER_WRITABLE", report["failures"]
        )
        self.assertIn(
            "RECEIPT_ROOT_PARENT_GROUP_OR_OTHER_WRITABLE", report["failures"]
        )

    def test_writable_non_direct_ancestor_is_rejected(self) -> None:
        writable_ancestor = self.fixture.root / "writable-ancestor"
        writable_ancestor.mkdir(mode=0o777)
        writable_ancestor.chmod(0o777)
        secure_parent = writable_ancestor / "secure-parent"
        secure_parent.mkdir(mode=0o700)
        secure_parent.chmod(0o700)
        leaf = secure_parent / "leaf"
        leaf.write_bytes(b"leaf")

        reason = MODULE._parent_chain_security(
            str(leaf), euid=os.geteuid(), direct_parent_allows_root=False
        )

        self.assertEqual(reason, "ANCESTOR_GROUP_OR_OTHER_WRITABLE")

    def test_symlinked_binary_is_rejected_without_execution(self) -> None:
        binary_alias = self.fixture.root / "binary-alias"
        binary_alias.symlink_to(self.fixture.binary)

        report = self.fixture.verify(binary=str(binary_alias))

        self.assertEqual(report["verdict"], "FAIL_CLOSED")
        self.assertEqual(
            report["checks"]["binary_physical_identity"]["status"], "FAIL"
        )
        self.assertIn("BINARY_SYMLINK_COMPONENT", report["failures"])
        self.assertFalse(
            any(command and command[0] == str(binary_alias) for command in self.fixture.commands)
        )

    def test_binary_special_mode_bits_are_rejected_without_execution(self) -> None:
        for mode in (0o4755, 0o2755, 0o1755):
            with self.subTest(mode=oct(mode)):
                self.fixture.commands.clear()
                self.fixture.command_environments.clear()
                self.fixture.binary.chmod(mode)

                report = self.fixture.verify()

                self.assertEqual(report["verdict"], "FAIL_CLOSED")
                self.assertEqual(
                    report["checks"]["binary_owner_permissions"]["status"],
                    "FAIL",
                )
                self.assertEqual(
                    report["checks"]["binary_version_commit"]["status"],
                    "NOT_RUN",
                )
                self.assertIn("BINARY_SPECIAL_MODE_BITS", report["failures"])
                self.assertFalse(
                    any(
                        command and command[0] == str(self.fixture.binary)
                        for command in self.fixture.commands
                    )
                )

    def test_missing_receipt_root_is_not_created(self) -> None:
        missing = self.fixture.root / "absent-production-root"
        self.assertFalse(missing.exists())

        report = self.fixture.verify(receipt_root=str(missing))

        self.assertEqual(report["verdict"], "FAIL_CLOSED")
        self.assertFalse(missing.exists())
        self.assertEqual(
            report["checks"]["receipt_root_physical_identity"]["status"], "FAIL"
        )
        self.assertIn("RECEIPT_ROOT_UNAVAILABLE", report["failures"])
        self.assertNotIn(
            (str(self.fixture.binary), "doctor", "--json"), self.fixture.commands
        )

    def test_receipt_root_atomic_replacement_during_doctor_fails_closed(self) -> None:
        old_root = self.fixture.root / "old-production-receipts"

        def replacing_runner(argv, timeout, explicit_env):
            observed = self.fixture.runner(argv, timeout, explicit_env)
            if argv == [str(self.fixture.binary), "doctor", "--json"]:
                self.fixture.receipt_root.rename(old_root)
                self.fixture.receipt_root.mkdir(mode=0o700)
                self.fixture.receipt_root.chmod(0o700)
            return observed

        report = self.fixture.verify(runner=replacing_runner)

        self.assertEqual(report["verdict"], "FAIL_CLOSED")
        self.assertEqual(
            report["checks"]["receipt_root_physical_identity"]["status"], "FAIL"
        )
        self.assertEqual(
            report["checks"]["receipt_root_owner_mode"]["status"], "FAIL"
        )
        self.assertIn(
            "RECEIPT_ROOT_CHANGED_DURING_VERIFICATION", report["failures"]
        )
        self.assertIn(
            "RECEIPT_ROOT_BOUNDARY_CHANGED_DURING_VERIFICATION",
            report["failures"],
        )

    def test_expected_hash_and_version_commit_are_both_fail_closed(self) -> None:
        wrong_hash = self.fixture.verify(expected_sha256="0" * 64)
        self.assertEqual(
            wrong_hash["checks"]["binary_content_sha256"]["status"], "FAIL"
        )
        self.assertEqual(
            wrong_hash["checks"]["binary_version_commit"]["status"], "NOT_RUN"
        )
        self.assertIn("BINARY_SHA256_MISMATCH", wrong_hash["failures"])

        self.fixture.version_stdout = (
            b"agent-bridge 0.14.0 (v0.14.0-1-gbbbbbbb; bbbbbbbbbbbb)\n"
        )
        wrong_version = self.fixture.verify()
        self.assertEqual(
            wrong_version["checks"]["binary_content_sha256"]["status"], "PASS"
        )
        self.assertEqual(
            wrong_version["checks"]["binary_version_commit"]["status"], "FAIL"
        )
        self.assertIn("BINARY_VERSION_COMMIT_MISMATCH", wrong_version["failures"])

    def test_service_requires_active_stable_non_deleted_matching_executable(self) -> None:
        inactive_unit = "agent-bridge-daemon-http.service"
        self.fixture.service_active[inactive_unit] = False

        deleted_unit = "agent-bridge-palace.service"
        deleted_identifier = self.fixture.identifiers[deleted_unit]
        deleted_link = self.fixture.proc_root / str(deleted_identifier) / "exe"
        deleted_link.unlink()
        deleted_link.symlink_to(f"{self.fixture.binary} (deleted)")

        report = self.fixture.verify()

        self.assertEqual(report["verdict"], "FAIL_CLOSED")
        self.assertEqual(report["services"]["daemon_http"]["active"], "FAIL")
        self.assertEqual(
            report["services"]["palace"]["executable_content_sha256"], "FAIL"
        )
        self.assertIn("SERVICE_DAEMON_HTTP_NOT_ACTIVE", report["failures"])
        self.assertIn("SERVICE_PALACE_EXECUTABLE_DELETED", report["failures"])

    def test_service_executable_content_must_match_installed_hash(self) -> None:
        unit = "agent-bridge-daemon.service"
        identifier = self.fixture.identifiers[unit]
        other_binary = self.fixture.root / "other-agent-bridge.real"
        other_binary.write_bytes(b"different executable content\n")
        other_binary.chmod(0o755)
        executable_link = self.fixture.proc_root / str(identifier) / "exe"
        executable_link.unlink()
        executable_link.symlink_to(other_binary)

        real_readlink = os.readlink

        def proc_readlink(path):
            if Path(path) == executable_link:
                # A procfs magic link can report the installed pathname while
                # its open executable inode still carries different bytes.
                return str(self.fixture.binary)
            return real_readlink(path)

        with mock.patch.object(MODULE.os, "readlink", side_effect=proc_readlink):
            report = self.fixture.verify()

        self.assertEqual(
            report["services"]["daemon"]["executable_content_sha256"], "FAIL"
        )
        self.assertIn(
            "SERVICE_DAEMON_EXECUTABLE_SHA256_MISMATCH", report["failures"]
        )

    def test_service_executable_must_be_the_explicit_path_even_with_same_bytes(self) -> None:
        unit = "agent-bridge-daemon.service"
        identifier = self.fixture.identifiers[unit]
        copied_binary = self.fixture.root / "same-content-copy.real"
        copied_binary.write_bytes(self.fixture.binary.read_bytes())
        copied_binary.chmod(0o755)
        executable_link = self.fixture.proc_root / str(identifier) / "exe"
        executable_link.unlink()
        executable_link.symlink_to(copied_binary)

        report = self.fixture.verify()

        self.assertEqual(
            report["services"]["daemon"]["executable_content_sha256"], "FAIL"
        )
        self.assertIn(
            "SERVICE_DAEMON_EXECUTABLE_TARGET_MISMATCH", report["failures"]
        )

    def test_final_service_sweep_rejects_earlier_pid_switch_during_later_probe(self) -> None:
        unit = "agent-bridge-daemon.service"
        original_identifier = self.fixture.identifiers[unit]
        replacement_identifier = original_identifier + 100
        doctor_completed = False
        switched = False

        def switching_runner(argv, timeout, explicit_env):
            nonlocal doctor_completed, switched
            observed = self.fixture.runner(argv, timeout, explicit_env)
            if argv == [str(self.fixture.binary), "doctor", "--json"]:
                doctor_completed = True
            elif (
                doctor_completed
                and not switched
                and argv[0] == MODULE.SYSTEMCTL
                and argv[1:3] == ["--user", "show"]
                and argv[3] == "agent-bridge-daemon-http.service"
            ):
                self.fixture.identifiers[unit] = replacement_identifier
                switched = True
            return observed

        report = self.fixture.verify(runner=switching_runner)

        self.assertEqual(report["verdict"], "FAIL_CLOSED")
        self.assertEqual(report["services"]["daemon"]["active"], "FAIL")
        self.assertEqual(
            report["services"]["daemon"]["executable_content_sha256"], "FAIL"
        )
        self.assertEqual(
            report["services"]["daemon"]["receipt_root_binding"], "FAIL"
        )
        self.assertEqual(
            report["checks"]["systemd_units_active"]["status"], "FAIL"
        )
        self.assertIn(
            "SERVICE_DAEMON_LATE_IDENTITY_UNSTABLE", report["failures"]
        )
        rendered = json.dumps(report, sort_keys=True)
        self.assertNotIn(str(original_identifier), rendered)
        self.assertNotIn(str(replacement_identifier), rendered)

    def test_final_service_sweep_rejects_late_executable_switch(self) -> None:
        unit = "agent-bridge-daemon.service"
        identifier = self.fixture.identifiers[unit]
        copied_binary = self.fixture.root / "late-same-content-copy.real"
        copied_binary.write_bytes(self.fixture.binary.read_bytes())
        copied_binary.chmod(0o755)
        executable_link = self.fixture.proc_root / str(identifier) / "exe"

        def switching_runner(argv, timeout, explicit_env):
            observed = self.fixture.runner(argv, timeout, explicit_env)
            if argv == [str(self.fixture.binary), "doctor", "--json"]:
                executable_link.unlink()
                executable_link.symlink_to(copied_binary)
            return observed

        report = self.fixture.verify(runner=switching_runner)

        self.assertEqual(report["verdict"], "FAIL_CLOSED")
        self.assertEqual(
            report["services"]["daemon"]["executable_content_sha256"], "FAIL"
        )
        self.assertEqual(
            report["checks"]["systemd_executable_content_sha256"]["status"],
            "FAIL",
        )
        self.assertIn(
            "SERVICE_DAEMON_LATE_EXECUTABLE_TARGET_MISMATCH",
            report["failures"],
        )
        self.assertNotIn(str(copied_binary), json.dumps(report, sort_keys=True))

    def test_service_receipt_environment_is_bounded_strict_and_private(self) -> None:
        unit = "agent-bridge-daemon.service"
        identifier = self.fixture.identifiers[unit]
        environment = self.fixture.proc_root / str(identifier) / "environ"
        expected_assignment = (
            b"AGENT_BRIDGE_CGROUP_RECEIPT_DIR="
            + os.fsencode(self.fixture.receipt_root)
        )
        cases = {
            "wrong_root": (
                b"SECRET_TOKEN=do-not-publish\0"
                b"AGENT_BRIDGE_CGROUP_RECEIPT_DIR=/private/wrong-root\0"
            ),
            "duplicate": expected_assignment + b"\0" + expected_assignment + b"\0",
            "empty": b"AGENT_BRIDGE_CGROUP_RECEIPT_DIR=\0",
            "malformed": b"AGENT_BRIDGE_CGROUP_RECEIPT_DIR\0",
            "noncanonical": (
                b"AGENT_BRIDGE_CGROUP_RECEIPT_DIR=/private/../receipt-root\0"
            ),
            "missing_relevant": b"SECRET_TOKEN=do-not-publish\0PATH=/usr/bin\0",
            "oversized": b"IGNORED=" + b"x" * MODULE.MAX_PROC_ENV_BYTES + b"\0",
        }

        for name, payload in cases.items():
            with self.subTest(name=name):
                environment.write_bytes(payload)
                report = self.fixture.verify()
                self.assertEqual(
                    report["services"]["daemon"]["receipt_root_binding"],
                    "FAIL",
                )
                self.assertEqual(
                    report["checks"]["systemd_receipt_root_binding"]["status"],
                    "FAIL",
                )
                self.assertIn(
                    "SERVICE_DAEMON_RECEIPT_ROOT_BINDING_INVALID",
                    report["failures"],
                )
                rendered = json.dumps(report, sort_keys=True)
                self.assertNotIn("do-not-publish", rendered)
                self.assertNotIn("/private/wrong-root", rendered)

    def test_receipt_environment_resolver_uses_exact_r9_precedence(self) -> None:
        rows = {
            "all": (
                b"AGENT_BRIDGE_CGROUP_RECEIPT_DIR=/explicit/receipts\0"
                b"AGENT_BRIDGE_DB=/database/state.db\0"
                b"AGENT_BRIDGE_STATE_DIR=/state\0"
                b"XDG_DATA_HOME=/xdg\0HOME=/home/person\0"
            ),
            "database": (
                b"AGENT_BRIDGE_DB=/database/state.db\0"
                b"AGENT_BRIDGE_STATE_DIR=/state\0XDG_DATA_HOME=/xdg\0"
                b"HOME=/home/person\0"
            ),
            "state": (
                b"AGENT_BRIDGE_STATE_DIR=/state\0XDG_DATA_HOME=/xdg\0"
                b"HOME=/home/person\0"
            ),
            "xdg": b"XDG_DATA_HOME=/xdg\0HOME=/home/person\0",
            "home": b"HOME=/home/person\0",
        }
        expected = {
            "all": "/explicit/receipts",
            "database": "/database/workload-receipts",
            "state": "/state/workload-receipts",
            "xdg": "/xdg/agent-bridge/workload-receipts",
            "home": "/home/person/.local/share/agent-bridge/workload-receipts",
        }

        for name, payload in rows.items():
            with self.subTest(name=name):
                self.assertEqual(
                    MODULE._resolved_receipt_root_from_environment(payload),
                    expected[name],
                )

    def test_receipt_environment_rejects_root_database_like_rust(self) -> None:
        payload = (
            b"AGENT_BRIDGE_DB=/\0"
            b"AGENT_BRIDGE_STATE_DIR=/otherwise-valid-state\0"
        )

        self.assertIsNone(
            MODULE._resolved_receipt_root_from_environment(payload)
        )

    def test_final_service_sweep_reads_receipt_environment_twice(self) -> None:
        unit = "agent-bridge-daemon.service"
        identifier = self.fixture.identifiers[unit]
        environment = self.fixture.proc_root / str(identifier) / "environ"
        real_match = MODULE._service_receipt_root_matches
        daemon_reads = 0

        def changing_match(environment_path, expected_root):
            nonlocal daemon_reads
            result = real_match(environment_path, expected_root)
            if Path(environment_path) == environment:
                daemon_reads += 1
                if daemon_reads == 3:
                    environment.write_bytes(
                        b"SECRET_TOKEN=late-do-not-publish\0"
                        b"AGENT_BRIDGE_CGROUP_RECEIPT_DIR=/private/late-root\0"
                    )
            return result

        with mock.patch.object(
            MODULE,
            "_service_receipt_root_matches",
            side_effect=changing_match,
        ):
            report = self.fixture.verify()

        self.assertEqual(daemon_reads, 4)
        self.assertEqual(report["verdict"], "FAIL_CLOSED")
        self.assertEqual(
            report["services"]["daemon"]["receipt_root_binding"], "FAIL"
        )
        self.assertEqual(
            report["checks"]["systemd_receipt_root_binding"]["status"], "FAIL"
        )
        self.assertIn(
            "SERVICE_DAEMON_LATE_RECEIPT_ROOT_BINDING_INVALID",
            report["failures"],
        )
        rendered = json.dumps(report, sort_keys=True)
        self.assertNotIn("late-do-not-publish", rendered)
        self.assertNotIn("/private/late-root", rendered)

    def test_unprivate_systemd_runtime_never_reaches_systemctl_or_doctor(self) -> None:
        self.fixture.systemd_runtime_dir.chmod(0o755)

        report = self.fixture.verify()

        self.assertEqual(
            report["checks"]["systemd_user_bus_binding"]["status"], "FAIL"
        )
        self.assertIn("SYSTEMD_USER_BUS_BINDING_UNSAFE", report["failures"])
        self.assertFalse(
            any(command[0] == MODULE.SYSTEMCTL for command in self.fixture.commands)
        )
        self.assertNotIn(
            (str(self.fixture.binary), "doctor", "--json"), self.fixture.commands
        )

    def test_health_body_must_be_exactly_ok(self) -> None:
        self.fixture.health_bodies[7979] = b"ok\n"

        report = self.fixture.verify()

        self.assertEqual(report["health"]["palace"], "FAIL")
        self.assertEqual(
            report["checks"]["loopback_health_exact_ok"]["status"], "FAIL"
        )
        self.assertIn("HEALTH_PALACE_NOT_EXACT_OK", report["failures"])

    def test_doctor_requires_boolean_ok_and_exact_integer_zero_counts(self) -> None:
        for doctor_stdout in (
            b'{"ok":true,"fails":0,"warns":1}',
            b'{"ok":true,"fails":0,"warns":false}',
            b'{"ok":true,"fails":0,"warns":0,"warns":0}',
            b'{"ok":true,"fails":0,"warns":0,"checks":[]}',
            b'{"ok":true,"fails":0,"warns":0,"checks":'
            b'[{"name":"workload_receipt_root","status":"warn"}]}',
        ):
            with self.subTest(doctor_stdout=doctor_stdout):
                self.fixture.doctor_stdout = doctor_stdout
                report = self.fixture.verify()
                self.assertEqual(
                    report["checks"]["doctor_strict_zero"]["status"], "FAIL"
                )
                self.assertIn("DOCTOR_NOT_STRICT_ZERO", report["failures"])

    def test_non_absolute_or_noncanonical_inputs_are_rejected_without_echo(self) -> None:
        report = self.fixture.verify(
            binary="relative/private-binary",
            receipt_root="/private/../receipt-root",
        )

        self.assertEqual(report["checks"]["input_contract"]["status"], "FAIL")
        self.assertIn("BINARY_NOT_ABSOLUTE", report["failures"])
        self.assertIn("RECEIPT_ROOT_NON_CANONICAL", report["failures"])
        rendered = json.dumps(report, sort_keys=True)
        self.assertNotIn("relative/private-binary", rendered)
        self.assertNotIn("/private/../receipt-root", rendered)

    def test_command_environment_is_an_explicit_non_secret_allowlist(self) -> None:
        ambient = {
            "HOME": "/bounded-home",
            "XDG_RUNTIME_DIR": "/attacker/runtime",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/attacker/bus",
            "AGENT_BRIDGE_TOOLSET": "codex-essential",
            "AGENT_BRIDGE_INSTALL_DIR": "/ambient/untrusted",
            "AGENT_BRIDGE_CGROUP_RECEIPT_DIR": "/ambient/receipt-root",
            "AGENT_BRIDGE_MOBILE_PROJECTION_TOKEN": "secret-token",
            "AB_SYSTEM_CONTROL_BIN": "/untrusted/executable",
            "AWS_SECRET_ACCESS_KEY": "secret-cloud-key",
            "HTTPS_PROXY": "http://credential.invalid",
            "LD_PRELOAD": "/untrusted/library.so",
        }
        with mock.patch.dict(os.environ, ambient, clear=True):
            unbound_environment = MODULE.command_environment(
                ["/secure/install/agent-bridge.real", "--version"]
            )
            environment = MODULE.command_environment(
                ["/secure/install/agent-bridge.real", "doctor", "--json"],
                {
                    "AGENT_BRIDGE_CGROUP_RECEIPT_DIR": "/verified/receipt-root",
                    "XDG_RUNTIME_DIR": "/run/user/1000",
                    "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
                },
            )

        self.assertNotIn(
            "AGENT_BRIDGE_CGROUP_RECEIPT_DIR", unbound_environment
        )
        self.assertNotIn("XDG_RUNTIME_DIR", unbound_environment)
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", unbound_environment)
        self.assertEqual(environment["HOME"], "/bounded-home")
        self.assertEqual(environment["XDG_RUNTIME_DIR"], "/run/user/1000")
        self.assertEqual(
            environment["AGENT_BRIDGE_INSTALL_DIR"], "/secure/install"
        )
        self.assertEqual(
            environment["AGENT_BRIDGE_CGROUP_RECEIPT_DIR"],
            "/verified/receipt-root",
        )
        self.assertEqual(environment["XDG_RUNTIME_DIR"], "/run/user/1000")
        self.assertEqual(
            environment["DBUS_SESSION_BUS_ADDRESS"],
            "unix:path=/run/user/1000/bus",
        )
        self.assertNotIn("/attacker", json.dumps(environment))
        self.assertEqual(
            environment["PATH"], "/usr/bin:/bin"
        )
        for secret_name in (
            "AGENT_BRIDGE_MOBILE_PROJECTION_TOKEN",
            "AB_SYSTEM_CONTROL_BIN",
            "AWS_SECRET_ACCESS_KEY",
            "HTTPS_PROXY",
            "LD_PRELOAD",
        ):
            self.assertNotIn(secret_name, environment)

    def test_cli_argument_rejection_is_json_and_does_not_echo_private_values(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            returncode = MODULE.main(
                ["--unknown-option", "/private/operator/supplied/path"]
            )

        self.assertEqual(returncode, 2)
        self.assertEqual(stderr.getvalue(), "")
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["verdict"], "FAIL_CLOSED")
        self.assertEqual(report["failures"], ["INVALID_ARGUMENTS"])
        self.assertNotIn("/private/operator/supplied/path", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
