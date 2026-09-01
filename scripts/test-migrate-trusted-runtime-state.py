#!/usr/bin/python3
"""Isolated stdlib tests for migrate-trusted-runtime-state.py.

The fixtures live entirely below per-test temporary directories.  Unit state is
supplied by an in-process fake, and no live Agent Bridge service, state path, or
systemd manager is touched.
"""

from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("migrate-trusted-runtime-state.py")
SPEC = importlib.util.spec_from_file_location("ab_trusted_state_migration", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MIGRATION = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MIGRATION
SPEC.loader.exec_module(MIGRATION)
REAL_SCAN_OPEN_FDS = MIGRATION.scan_open_fds


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)


def inactive_unit(unit: str) -> dict[str, str]:
    if unit.endswith(".timer"):
        return {
            "ActiveState": "inactive",
            "LoadState": "loaded",
            "SubState": "dead",
            "UnitFileState": "disabled",
        }
    return {
        "ActiveState": "inactive",
        "LoadState": "loaded",
        "MainPID": "0",
        "SubState": "dead",
    }


def unloaded_launchd_jobs() -> list[dict[str, object]]:
    return [
        {
            "domain": f"gui/{os.geteuid()}",
            "loaded": False,
            "name": label,
            "type": "launchd",
        }
        for label in MIGRATION.DARWIN_LAUNCHD_JOBS
    ]


class Fixture:
    def __init__(self, *, wal: bool = False) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="ab-r9-m1-")
        self.base = Path(self.temporary.name)
        self.root = self.base / "deploy-root"
        self.legacy = self.base / "legacy-state"
        private_dir(self.root)
        private_dir(self.legacy)
        # The live FUSE legacy source is root-owned/mode-0777.  Tests cannot
        # chown without privilege, but mode 0777 proves it is treated as
        # untrusted input rather than a private authority file.
        self.legacy.chmod(0o777)

        for relative in (
            "source/agent-bridge/scripts",
            "publisher-state/deploy",
            "config/agent-bridge",
            "runtime-state",
            "bin",
            "share/ab-tts",
            "lib/agent-bridge/scripts",
        ):
            private_dir(self.root / relative)
        for path in self.root.rglob("*"):
            if path.is_dir():
                path.chmod(0o700)
        for leaf in MIGRATION.RUNTIME_LEAVES:
            private_dir(self.root / "runtime-state" / leaf)

        self.installed_script = (
            self.root / "source/agent-bridge/scripts/migrate-trusted-runtime-state.py"
        )
        shutil.copyfile(SCRIPT, self.installed_script)
        self.installed_script.chmod(0o700)
        self.repo = self.root / "source/agent-bridge"
        self._git("init", "-q")
        self._git("add", "scripts/migrate-trusted-runtime-state.py")
        self._git(
            "-c",
            "user.name=R9 Migration Test",
            "-c",
            "user.email=r9-migration@example.invalid",
            "commit",
            "-q",
            "-m",
            "fixture",
        )
        self.candidate = self._git("rev-parse", "HEAD").stdout.decode().strip()
        self._git("remote", "add", "gitlab", MIGRATION.GITLAB_REMOTE_URL)
        self._git("update-ref", "refs/remotes/gitlab/master", self.candidate)
        for path in (
            self.root / "source",
            self.repo,
            self.repo / ".git",
            self.repo / "scripts",
        ):
            path.chmod(0o700)

        self.binary = self.root / "bin/agent-bridge.real"
        self.binary.write_bytes(b"\x7fELF-r9-migration-fixture\n")
        self.binary.chmod(0o755)
        self.lock = self.root / "publisher-state/deploy/publisher.kernel.lock"
        self.lock.write_bytes(b"")
        self.lock.chmod(0o600)

        self.database = self.legacy / "state.db"
        if wal:
            self._create_wal_database()
        else:
            connection = sqlite3.connect(self.database)
            connection.execute("CREATE TABLE memories(id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
            connection.execute("INSERT INTO memories(body) VALUES ('base-row')")
            connection.commit()
            connection.close()
        self.database.chmod(0o777)

        self.sidecars = self.legacy / "sidecars"
        private_dir(self.sidecars)
        self.sidecars.chmod(0o777)
        self.events = self.sidecars / "events.jsonl"
        self.events.write_text('{"event":"ready","value":1}\n', encoding="utf-8")
        self.events.chmod(0o666)

        self.pending = self.root / "publisher-state/deploy/pending-admission.meta"
        self._write_pending()
        self.plan_path = self.root / "config/agent-bridge/state-migration.json"
        self.plan = self._default_plan()
        self.write_plan()

    def close(self) -> None:
        self.temporary.cleanup()

    def _git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ("/usr/bin/git", "-C", str(self.repo), *args),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def _create_wal_database(self) -> None:
        code = r"""
import os, sqlite3, sys
path = sys.argv[1]
db = sqlite3.connect(path)
assert db.execute('PRAGMA journal_mode=WAL').fetchone()[0].lower() == 'wal'
db.execute('PRAGMA wal_autocheckpoint=0')
db.execute('CREATE TABLE memories(id INTEGER PRIMARY KEY, body TEXT NOT NULL)')
db.commit()
db.execute("INSERT INTO memories(body) VALUES ('base-row')")
db.execute("INSERT INTO memories(body) VALUES ('wal-row')")
db.commit()
assert os.path.getsize(path + '-wal') > 0
os._exit(0)
"""
        subprocess.run(
            ("/usr/bin/python3", "-I", "-B", "-c", code, str(self.database)),
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if not Path(str(self.database) + "-wal").is_file():
            raise AssertionError("fixture did not retain a WAL")
        if Path(str(self.database) + "-wal").stat().st_size <= 0:
            raise AssertionError("fixture WAL is empty")
        # WAL read-only mode needs the matching shared-memory file on older
        # SQLite builds; the unclean exit normally leaves it.  Assert rather
        # than synthesizing an invalid DB family.
        if not Path(str(self.database) + "-shm").is_file():
            raise AssertionError("fixture did not retain SQLite SHM")
        Path(str(self.database) + "-wal").chmod(0o666)
        Path(str(self.database) + "-shm").chmod(0o666)

    def _write_pending(self) -> None:
        real = str(self.binary)
        shared = "|".join(
            (
                real,
                str(self.root / "share/ab-tts/audio_embody.py"),
                str(self.root / "lib/agent-bridge/scripts"),
                str(self.root / "bin/agent-bridge"),
            )
        )
        lines = (
            "schema=agent_bridge.publisher_pending_admission.v0",
            "lease_id=test-lease-r9-m1",
            "challenge=" + "1" * 64,
            "real_path=" + real,
            "shared_targets=" + shared,
            "candidate_commit=" + self.candidate,
            "installed_binary_sha256=" + sha256(self.binary),
            "installed_binary_inode=" + str(self.binary.stat().st_ino),
            "installed_binary_mode=755",
            "installed_assets_sha256=" + "2" * 64,
            "installed_at=2026-08-28T12:00:00Z",
            "fresh_mcp=unverified",
            "force_reinstall=0",
            "force_reason=",
        )
        self.pending.write_text("\n".join(lines) + "\n", encoding="ascii")
        self.pending.chmod(0o600)

    def _default_plan(self) -> dict[str, object]:
        names = {entry.name for entry in self.legacy.iterdir()}
        leaves = []
        for name in sorted(
            names | {"state.db-wal", "state.db-shm", "state.db-journal"}
        ):
            if name in ("state.db-wal", "state.db-shm", "state.db-journal"):
                decision = "reconstruct"
            else:
                decision = "retain"
            leaves.append({"decision": decision, "name": name})
        return {
            "candidate_commit": self.candidate,
            "inventory_roots": [{"leaves": leaves, "path": str(self.legacy)}],
            "limits": {
                "max_bytes": 128 * 1024 * 1024,
                "max_file_bytes": 64 * 1024 * 1024,
                "max_files": 1000,
                "reserve_bytes": 1024 * 1024,
            },
            "mappings": [
                {
                    "kind": "sqlite",
                    "source": str(self.database),
                    "target": MIGRATION.SQLITE_TARGET,
                    "validation": "sqlite",
                },
                {
                    "kind": "tree",
                    "source": str(self.sidecars),
                    "target": "data/agent-bridge/sidecars",
                    "validation": "jsonl",
                },
            ],
            "pending_admission_sha256": sha256(self.pending),
            "schema": MIGRATION.PLAN_SCHEMA,
        }

    def refresh_inventory(self) -> None:
        existing = {
            leaf["name"]: leaf["decision"]
            for leaf in self.plan["inventory_roots"][0]["leaves"]  # type: ignore[index]
        }
        leaves = []
        for name in sorted({entry.name for entry in self.legacy.iterdir()} | set(existing)):
            leaves.append(
                {
                    "decision": existing.get(name, "retain"),
                    "name": name,
                }
            )
        self.plan["inventory_roots"][0]["leaves"] = leaves  # type: ignore[index]

    def write_plan(self) -> None:
        self.plan_path.write_text(
            json.dumps(self.plan, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="ascii",
        )
        self.plan_path.chmod(0o600)

    @property
    def confirmation(self) -> str:
        return "MIGRATE:" + self.candidate + ":" + sha256(self.pending)

    def execute(
        self,
        command: str,
        *,
        confirmation: str | None = None,
        inherited_lock_fd: int | None = None,
        unit_state=inactive_unit,
        fd_scan=None,
        platform: str | None = None,
    ):
        if fd_scan is None:
            fd_scan = lambda _paths: None
        if platform is None:
            platform = "darwin" if sys.platform == "darwin" else "linux"
        with mock.patch.object(
            MIGRATION, "running_script_path", return_value=str(self.installed_script)
        ), mock.patch.object(
            MIGRATION, "query_unit_state", side_effect=unit_state
        ), mock.patch.object(
            MIGRATION, "scan_open_fds", side_effect=fd_scan
        ), mock.patch.object(
            MIGRATION, "collect_launchd_quiescence", return_value=unloaded_launchd_jobs()
        ), mock.patch.object(MIGRATION, "runtime_platform", return_value=platform):
            return MIGRATION.execute(
                command,
                str(self.root),
                confirmation=confirmation,
                inherited_lock_fd=inherited_lock_fd,
            )


def snapshot(paths: list[Path]) -> dict[str, tuple[object, ...]]:
    result: dict[str, tuple[object, ...]] = {}
    for base in paths:
        for root, directories, files in os.walk(base):
            directories.sort()
            files.sort()
            root_path = Path(root)
            key = str(root_path)
            st = root_path.lstat()
            result[key] = (
                "dir",
                st.st_mode & 0o7777,
                st.st_uid,
                st.st_dev,
                st.st_ino,
                st.st_nlink,
            )
            for name in files:
                path = root_path / name
                st = path.lstat()
                result[str(path)] = (
                    "file",
                    st.st_mode & 0o7777,
                    st.st_uid,
                    st.st_dev,
                    st.st_ino,
                    st.st_nlink,
                    st.st_size,
                    sha256(path),
                )
    return result


class MigrationTests(unittest.TestCase):
    maxDiff = None

    def test_darwin_system_python_binds_xcrun_selected_interpreter(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["/usr/bin/xcrun", "--find", "python3"],
            returncode=0,
            stdout=b"/Applications/Xcode.app/Contents/Developer/usr/bin/python3\n",
            stderr=b"",
        )
        interpreter = mock.Mock(st_mode=0o100755, st_uid=0)
        with mock.patch.object(MIGRATION.sys, "platform", "darwin"), \
             mock.patch.object(MIGRATION.subprocess, "run", return_value=completed), \
             mock.patch.object(MIGRATION.os, "stat", return_value=interpreter), \
             mock.patch.object(MIGRATION.os, "access", return_value=True):
            observed = MIGRATION.system_python_executable()
        self.assertEqual(
            observed,
            "/Applications/Xcode.app/Contents/Developer/usr/bin/python3",
        )

    def test_darwin_system_python_resolution_fails_closed(self) -> None:
        cases = (
            subprocess.CompletedProcess([], 1, b"", b"unavailable"),
            subprocess.CompletedProcess([], 0, b"relative/python3\n", b""),
        )
        for completed in cases:
            with self.subTest(returncode=completed.returncode, stdout=completed.stdout), \
                 mock.patch.object(MIGRATION.sys, "platform", "darwin"), \
                 mock.patch.object(MIGRATION.subprocess, "run", return_value=completed):
                with self.assertRaises(MIGRATION.MigrationError):
                    MIGRATION.system_python_executable()

    def test_darwin_rename_exchange_binds_fixed_abi_and_fails_closed(self) -> None:
        class FakeRename:
            argtypes = None
            restype = None

            def __init__(self) -> None:
                self.arguments = None

            def __call__(self, *arguments):
                self.arguments = arguments
                MIGRATION.ctypes.set_errno(MIGRATION.errno.EXDEV)
                return -1

        rename = FakeRename()
        libc = types.SimpleNamespace(renameatx_np=rename)
        with mock.patch.object(MIGRATION, "runtime_platform", return_value="darwin"), \
             mock.patch.object(MIGRATION.ctypes, "CDLL", return_value=libc):
            self.assert_rejected(
                lambda: MIGRATION.rename_exchange("/private/left", "/private/right"),
                "renameatx_np swap",
            )
        self.assertEqual(
            rename.arguments,
            (-2, b"/private/left", -2, b"/private/right", 0x00000002),
        )
        self.assertEqual(rename.restype, MIGRATION.ctypes.c_int)

        with mock.patch.object(MIGRATION, "runtime_platform", return_value="darwin"), \
             mock.patch.object(
                 MIGRATION.ctypes, "CDLL", return_value=types.SimpleNamespace()
             ):
            self.assert_rejected(
                lambda: MIGRATION.rename_exchange("/private/left", "/private/right"),
                "renameatx_np swap is required",
            )

    @unittest.skipUnless(sys.platform == "darwin", "requires Darwin renameatx_np")
    def test_darwin_atomic_directory_exchange_and_reversal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ab-darwin-swap-") as base:
            left = Path(base) / "left"
            right = Path(base) / "right"
            private_dir(left)
            private_dir(right)
            (left / "marker").write_text("left\n", encoding="ascii")
            (right / "marker").write_text("right\n", encoding="ascii")
            left_inode = left.stat().st_ino
            right_inode = right.stat().st_ino

            MIGRATION.rename_exchange(str(left), str(right))
            self.assertEqual(left.stat().st_ino, right_inode)
            self.assertEqual(right.stat().st_ino, left_inode)
            self.assertEqual((left / "marker").read_text(encoding="ascii"), "right\n")
            self.assertEqual((right / "marker").read_text(encoding="ascii"), "left\n")

            MIGRATION.rename_exchange(str(left), str(right))
            self.assertEqual(left.stat().st_ino, left_inode)
            self.assertEqual(right.stat().st_ino, right_inode)

    def fixture(self, *, wal: bool = False) -> Fixture:
        value = Fixture(wal=wal)
        self.addCleanup(value.close)
        return value

    def test_darwin_launchd_quiescence_requires_fixed_jobs_unloaded(self) -> None:
        missing = subprocess.CompletedProcess(
            args=("/bin/launchctl",),
            returncode=113,
            stdout="",
            stderr='Could not find service "fixture" in domain for user gui: 501\n',
        )
        with mock.patch.object(
            MIGRATION.subprocess, "run", return_value=missing
        ) as run:
            baseline = MIGRATION.collect_launchd_quiescence()
        self.assertEqual(len(baseline), len(MIGRATION.DARWIN_LAUNCHD_JOBS))
        self.assertEqual(
            [record["name"] for record in baseline],
            list(MIGRATION.DARWIN_LAUNCHD_JOBS),
        )
        self.assertTrue(all(record["loaded"] is False for record in baseline))
        self.assertEqual(run.call_count, len(MIGRATION.DARWIN_LAUNCHD_JOBS))
        with mock.patch.object(MIGRATION, "runtime_platform", return_value="darwin"):
            self.assertIs(MIGRATION.validate_unit_baseline(baseline), baseline)
            tampered = [dict(record) for record in baseline]
            tampered[0]["loaded"] = True
            self.assert_rejected(
                lambda: MIGRATION.validate_unit_baseline(tampered),
                "exact quiesced job set",
            )

        loaded = subprocess.CompletedProcess(
            args=("/bin/launchctl",), returncode=0, stdout="state = running\n", stderr=""
        )
        with mock.patch.object(MIGRATION.subprocess, "run", return_value=loaded):
            self.assert_rejected(
                MIGRATION.collect_launchd_quiescence,
                "loaded or triggerable",
            )

    def test_darwin_launchd_inventory_failure_is_not_unloaded(self) -> None:
        failure = subprocess.CompletedProcess(
            args=("/bin/launchctl",), returncode=1, stdout="", stderr="unexpected\n"
        )
        with mock.patch.object(MIGRATION.subprocess, "run", return_value=failure):
            self.assert_rejected(
                lambda: MIGRATION.query_launchd_loaded(
                    MIGRATION.DARWIN_LAUNCHD_JOBS[0]
                ),
                "cannot query",
            )

    def test_darwin_lsof_inventory_fails_closed_on_external_holder(self) -> None:
        path = "/private/var/tmp/agent-bridge/state.db"
        empty = subprocess.CompletedProcess(
            args=("/usr/sbin/lsof",), returncode=1, stdout="", stderr=""
        )
        with mock.patch.object(MIGRATION.subprocess, "run", return_value=empty):
            MIGRATION.scan_darwin_open_fds({path})

        own = subprocess.CompletedProcess(
            args=("/usr/sbin/lsof",),
            returncode=0,
            stdout=f"p{os.getpid()}\ncpython3\nu{os.geteuid()}\nf5u\nn{path}\n",
            stderr="",
        )
        with mock.patch.object(MIGRATION.subprocess, "run", return_value=own):
            MIGRATION.scan_darwin_open_fds({path})

        external = subprocess.CompletedProcess(
            args=("/usr/sbin/lsof",),
            returncode=0,
            stdout=f"p{os.getpid() + 1}\ncagent-bridge\nu{os.geteuid()}\nf12u\nn{path}\n",
            stderr="",
        )
        with mock.patch.object(MIGRATION.subprocess, "run", return_value=external):
            self.assert_rejected(
                lambda: MIGRATION.scan_darwin_open_fds({path}),
                "external process",
            )

        incomplete = subprocess.CompletedProcess(
            args=("/usr/sbin/lsof",), returncode=2, stdout="", stderr="denied\n"
        )
        with mock.patch.object(MIGRATION.subprocess, "run", return_value=incomplete):
            self.assert_rejected(
                lambda: MIGRATION.scan_darwin_open_fds({path}),
                "cannot enumerate",
            )

    def test_sqlite_busy_statuses_support_apple_python_39(self) -> None:
        self.assertEqual(
            MIGRATION.sqlite_busy_statuses(types.SimpleNamespace()),
            (MIGRATION.SQLITE_BUSY_CODE, MIGRATION.SQLITE_LOCKED_CODE),
        )

    def test_wal_backup_normalizes_delete_mode_and_removes_sidecars(self) -> None:
        fixture = self.fixture(wal=True)
        target = fixture.base / "backup.db"
        input_sha = sha256(fixture.database)
        observed_input_sha, source_fact, target_fact = (
            MIGRATION.sqlite_checkpoint_and_backup(str(fixture.database), str(target))
        )
        self.assertEqual(observed_input_sha, input_sha)
        self.assertEqual(source_fact["path"], str(fixture.database))
        self.assertEqual(target_fact["path"], MIGRATION.SQLITE_TARGET)
        for database in (fixture.database, target):
            for suffix in MIGRATION.SQLITE_SIDECAR_SUFFIXES:
                self.assertFalse(Path(str(database) + suffix).exists())
            connection = sqlite3.connect(database)
            try:
                self.assertEqual(
                    connection.execute("PRAGMA journal_mode").fetchone(),
                    ("delete",),
                )
                self.assertEqual(
                    [
                        row[0]
                        for row in connection.execute(
                            "SELECT body FROM memories ORDER BY id"
                        )
                    ],
                    ["base-row", "wal-row"],
                )
            finally:
                connection.close()

    def test_obsolete_shm_cleanup_rejects_symlink_and_hardlink(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ab-obsolete-shm-") as base:
            source = Path(base) / "state.db"
            source.write_bytes(b"database")
            shm = Path(str(source) + "-shm")
            shm.write_bytes(b"shm")
            wal = Path(str(source) + "-wal")
            wal.write_bytes(b"wal")
            self.assert_rejected(
                lambda: MIGRATION.remove_obsolete_sqlite_shm(str(source)),
                "while WAL or journal exists",
            )
            self.assertTrue(shm.exists())
            wal.unlink()
            journal = Path(str(source) + "-journal")
            journal.write_bytes(b"journal")
            self.assert_rejected(
                lambda: MIGRATION.remove_obsolete_sqlite_shm(str(source)),
                "while WAL or journal exists",
            )
            self.assertTrue(shm.exists())
            journal.unlink()
            shm.unlink()
            shm.symlink_to(source)
            self.assert_rejected(
                lambda: MIGRATION.remove_obsolete_sqlite_shm(str(source)),
                "single-link physical regular file",
            )
            shm.unlink()
            anchor = Path(base) / "anchor"
            anchor.write_bytes(b"shm")
            os.link(anchor, shm)
            self.assert_rejected(
                lambda: MIGRATION.remove_obsolete_sqlite_shm(str(source)),
                "single-link physical regular file",
            )

    def assert_rejected(self, callback, fragment: str | None = None) -> str:
        with self.assertRaises(MIGRATION.MigrationError) as caught:
            callback()
        text = str(caught.exception)
        if fragment is not None:
            self.assertIn(fragment, text)
        return text

    def test_happy_wal_backup_sidecar_verify_and_idempotent_replay(self) -> None:
        fixture = self.fixture(wal=True)
        platform = "darwin" if sys.platform == "darwin" else "linux"
        wal = Path(str(fixture.database) + "-wal")
        self.assertGreater(wal.stat().st_size, 0)
        before_preflight = snapshot([fixture.root, fixture.legacy])
        preflight = fixture.execute("preflight", platform=platform)
        self.assertEqual(preflight["status"], "ready_quiesced")
        self.assertEqual(
            preflight["sqlite_integrity"], "deferred_wal_to_confirmed_migrate"
        )
        self.assertEqual(before_preflight, snapshot([fixture.root, fixture.legacy]))
        self.assert_rejected(
            lambda: fixture.execute(
                "migrate", confirmation="WRONG-CONFIRMATION", platform=platform
            ),
            "confirmation",
        )
        self.assertEqual(before_preflight, snapshot([fixture.root, fixture.legacy]))
        migrated = fixture.execute(
            "migrate", confirmation=fixture.confirmation, platform=platform
        )
        self.assertEqual(migrated["status"], "migrated_quiesced")
        self.assertFalse(Path(str(fixture.database) + "-wal").exists())
        self.assertFalse(Path(str(fixture.database) + "-shm").exists())

        target = fixture.root / "runtime-state" / MIGRATION.SQLITE_TARGET
        connection = sqlite3.connect(f"file:{target}?mode=ro&immutable=1", uri=True)
        rows = [row[0] for row in connection.execute("SELECT body FROM memories ORDER BY id")]
        connection.close()
        self.assertEqual(rows, ["base-row", "wal-row"])
        self.assertEqual(
            (fixture.root / "runtime-state/data/agent-bridge/sidecars/events.jsonl").read_bytes(),
            fixture.events.read_bytes(),
        )
        verified = fixture.execute("verify", platform=platform)
        self.assertEqual(verified["receipt_digest"], migrated["receipt_digest"])
        before = snapshot([fixture.root / "runtime-state", fixture.root / "publisher-state/migrations"])
        replay = fixture.execute(
            "migrate", confirmation=fixture.confirmation, platform=platform
        )
        self.assertEqual(replay["status"], "already_migrated")
        self.assertEqual(
            before,
            snapshot([fixture.root / "runtime-state", fixture.root / "publisher-state/migrations"]),
        )

    def test_preflight_is_zero_write(self) -> None:
        fixture = self.fixture()
        before = snapshot([fixture.root, fixture.legacy])
        result = fixture.execute("preflight")
        self.assertEqual(result["status"], "ready_quiesced")
        self.assertEqual(before, snapshot([fixture.root, fixture.legacy]))
        self.assertFalse((fixture.root / "publisher-state/migrations").exists())

    def test_strict_json_duplicate_key_and_unknown_inventory_leaf(self) -> None:
        fixture = self.fixture()
        raw = fixture.plan_path.read_text(encoding="ascii").rstrip()
        fixture.plan_path.write_text(raw[:-1] + ',"schema":"duplicate"}\n', encoding="ascii")
        fixture.plan_path.chmod(0o600)
        self.assert_rejected(lambda: fixture.execute("preflight"), "duplicate JSON key")

        fixture = self.fixture()
        fixture.plan["unknown_contract_key"] = True
        fixture.write_plan()
        self.assert_rejected(lambda: fixture.execute("preflight"), "unknown=unknown_contract_key")

        fixture = self.fixture()
        (fixture.legacy / "surprise").write_text("unlisted", encoding="ascii")
        self.assert_rejected(lambda: fixture.execute("preflight"), "unknown, missing")

        fixture = self.fixture()
        bundle = fixture.legacy / "bundle"
        private_dir(bundle)
        (bundle / "mapped.json").write_text('{"mapped":true}\n', encoding="utf-8")
        (bundle / "omitted.json").write_text('{"omitted":true}\n', encoding="utf-8")
        fixture.plan["mappings"].append(
            {
                "kind": "regular",
                "source": str(bundle / "mapped.json"),
                "target": "data/bundle/mapped.json",
                "validation": "json",
            }
        )
        fixture.refresh_inventory()
        fixture.write_plan()
        self.assert_rejected(
            lambda: fixture.execute("preflight"),
            "equal its retained immediate inventory leaf",
        )

    def test_symlink_hardlink_and_special_sources_are_rejected(self) -> None:
        for kind in ("symlink", "hardlink", "special"):
            with self.subTest(kind=kind):
                fixture = self.fixture()
                if kind == "symlink":
                    path = fixture.legacy / "unsafe-link"
                    path.symlink_to(fixture.events)
                    fixture.plan["mappings"].append(
                        {
                            "kind": "regular",
                            "source": str(path),
                            "target": "data/unsafe-link",
                            "validation": "none",
                        }
                    )
                elif kind == "hardlink":
                    path = fixture.legacy / "hardlinked.jsonl"
                    os.link(fixture.events, path)
                    fixture.plan["mappings"].append(
                        {
                            "kind": "regular",
                            "source": str(path),
                            "target": "data/hardlinked.jsonl",
                            "validation": "jsonl",
                        }
                    )
                else:
                    path = fixture.legacy / "unsafe-fifo"
                    os.mkfifo(path, 0o600)
                    fixture.plan["mappings"].append(
                        {
                            "kind": "regular",
                            "source": str(path),
                            "target": "data/unsafe-fifo",
                            "validation": "none",
                        }
                    )
                fixture.refresh_inventory()
                fixture.write_plan()
                self.assert_rejected(lambda: fixture.execute("preflight"))

    def test_raw_lock_and_wal_mappings_are_rejected(self) -> None:
        fixture = self.fixture()
        lock = fixture.legacy / "journal.lock"
        lock.write_text("lock", encoding="ascii")
        fixture.plan["mappings"].append(
            {
                "kind": "regular",
                "source": str(lock),
                "target": "data/journal-copy",
                "validation": "none",
            }
        )
        fixture.refresh_inventory()
        fixture.write_plan()
        self.assert_rejected(lambda: fixture.execute("preflight"), "lock or SQLite")

        fixture = self.fixture()
        journal = Path(str(fixture.database) + "-journal")
        journal.write_bytes(b"rollback-journal")
        journal.chmod(0o666)
        self.assert_rejected(
            lambda: fixture.execute("preflight"), "rollback journal must be absent"
        )

        fixture = self.fixture()
        super_journal = Path(str(fixture.database) + "-mj-test")
        super_journal.write_bytes(b"super-journal")
        super_journal.chmod(0o666)
        fixture.refresh_inventory()
        for leaf in fixture.plan["inventory_roots"][0]["leaves"]:  # type: ignore[index]
            if leaf["name"] == super_journal.name:
                leaf["decision"] = "reconstruct"
        fixture.write_plan()
        self.assert_rejected(lambda: fixture.execute("preflight"), "super-journal")

        fixture = self.fixture(wal=True)
        for leaf in fixture.plan["inventory_roots"][0]["leaves"]:  # type: ignore[index]
            if leaf["name"] == "state.db-wal":
                leaf["decision"] = "retain"
        fixture.plan["mappings"].append(
            {
                "kind": "regular",
                "source": str(fixture.database) + "-wal",
                "target": "data/raw-wal-copy",
                "validation": "none",
            }
        )
        fixture.write_plan()
        self.assert_rejected(lambda: fixture.execute("preflight"), "lock or SQLite")

    def test_active_service_timer_and_timer_unitfile_shapes(self) -> None:
        fixture = self.fixture()

        def active_service(unit: str) -> dict[str, str]:
            values = inactive_unit(unit)
            if unit == "agent-bridge-daemon.service":
                values.update(ActiveState="active", SubState="running", MainPID="123")
            return values

        self.assert_rejected(
            lambda: fixture.execute(
                "preflight", unit_state=active_service, platform="linux"
            ),
            "not fully quiesced",
        )

        positive_timer_shapes = (
            ("loaded", "disabled"),
            ("masked", "masked"),
            ("not-found", ""),
        )
        for load, unit_file in positive_timer_shapes:
            with self.subTest(load=load, unit_file=unit_file):
                def shape(unit: str, load=load, unit_file=unit_file):
                    values = inactive_unit(unit)
                    if unit.endswith(".timer"):
                        values["LoadState"] = load
                        values["UnitFileState"] = unit_file
                    return values

                self.assertEqual(
                    fixture.execute(
                        "preflight", unit_state=shape, platform="linux"
                    )["status"],
                    "ready_quiesced",
                )

        for load, unit_file in (("loaded", "enabled"), ("loaded", "masked"), ("masked", "disabled")):
            with self.subTest(rejected=(load, unit_file)):
                def bad_shape(unit: str, load=load, unit_file=unit_file):
                    values = inactive_unit(unit)
                    if unit.endswith(".timer"):
                        values["LoadState"] = load
                        values["UnitFileState"] = unit_file
                    return values

                self.assert_rejected(
                    lambda: fixture.execute(
                        "preflight", unit_state=bad_shape, platform="linux"
                    ),
                    "enabled or triggerable",
                )

    def test_external_open_database_fd_is_rejected(self) -> None:
        fixture = self.fixture()
        code = "import sys; f=open(sys.argv[1], 'rb'); print('ready', flush=True); sys.stdin.read()"
        child = subprocess.Popen(
            ("/usr/bin/python3", "-I", "-B", "-c", code, str(fixture.database)),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(child.kill)
        assert child.stdout is not None
        self.assertEqual(child.stdout.readline().strip(), "ready")
        if sys.platform == "darwin":
            fd_scan = REAL_SCAN_OPEN_FDS
        else:
            fd_scan = lambda paths: REAL_SCAN_OPEN_FDS(
                paths, pid_inventory=[child.pid]
            )
        self.assert_rejected(
            lambda: fixture.execute(
                "preflight",
                fd_scan=fd_scan,
            ),
            "external process",
        )
        assert child.stdin is not None
        child.stdin.close()
        child.wait(timeout=5)
        child.stdout.close()
        assert child.stderr is not None
        child.stderr.close()

        if sys.platform.startswith("linux"):
            with mock.patch.object(
                MIGRATION, "open_proc_pid_directory", side_effect=PermissionError
            ), mock.patch.object(MIGRATION.os, "stat", side_effect=PermissionError):
                self.assert_rejected(
                    lambda: REAL_SCAN_OPEN_FDS(
                        {str(fixture.database)}, pid_inventory=[999999]
                    ),
                    "cannot determine the owner",
                )

    def test_yama_exception_recognizes_only_exact_user_systemd_manager(self) -> None:
        fixture = self.fixture()
        proc = fixture.base / "fake-proc"
        pid = 4242
        private_dir(proc / str(pid))
        uid = os.geteuid()
        (proc / str(pid) / "status").write_text(
            f"Name:\tsystemd\nPid:\t{pid}\nTgid:\t{pid}\nPPid:\t1\n"
            f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\n",
            encoding="ascii",
        )
        (proc / str(pid) / "cmdline").write_bytes(b"/usr/lib/systemd/systemd\0--user\0")
        (proc / str(pid) / "cgroup").write_text(
            f"0::/user.slice/user-{uid}.slice/user@{uid}.service/init.scope\n",
            encoding="ascii",
        )
        self.assertTrue(MIGRATION.is_exact_user_systemd_manager(pid, str(proc)))
        (proc / str(pid) / "cmdline").write_bytes(b"/usr/lib/systemd/systemd\0--system\0")
        self.assertFalse(MIGRATION.is_exact_user_systemd_manager(pid, str(proc)))
        (proc / str(pid) / "cmdline").write_bytes(b"/usr/lib/systemd/systemd\0--user\0")
        (proc / str(pid) / "cgroup").write_text("0::/user.slice/attacker.scope\n", encoding="ascii")
        self.assertFalse(MIGRATION.is_exact_user_systemd_manager(pid, str(proc)))
        (proc / str(pid) / "cgroup").write_text(
            f"0::/user.slice/user-{uid}.slice/user@{uid}.service/init.scope\n",
            encoding="ascii",
        )
        pam_pid = 4243
        private_dir(proc / str(pam_pid))
        (proc / str(pam_pid) / "status").write_text(
            f"Name:\t(sd-pam)\nPid:\t{pam_pid}\nTgid:\t{pam_pid}\nPPid:\t{pid}\n"
            f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\n",
            encoding="ascii",
        )
        (proc / str(pam_pid) / "cmdline").write_bytes(b"(sd-pam)\0")
        (proc / str(pam_pid) / "cgroup").write_text(
            f"0::/user.slice/user-{uid}.slice/user@{uid}.service/init.scope\n",
            encoding="ascii",
        )
        self.assertTrue(MIGRATION.is_exact_user_manager_infrastructure(pam_pid, str(proc)))
        (proc / str(pam_pid) / "cgroup").write_text("0::/user.slice/attacker.scope\n", encoding="ascii")
        self.assertFalse(MIGRATION.is_exact_user_manager_infrastructure(pam_pid, str(proc)))

        if not sys.platform.startswith("linux"):
            return

        code = (
            "import ctypes,sys; "
            "assert ctypes.CDLL(None).prctl(4,0,0,0,0)==0; "
            "print('ready',flush=True); sys.stdin.read()"
        )
        child = subprocess.Popen(
            ("/usr/bin/python3", "-I", "-B", "-c", code),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(child.kill)
        assert child.stdout is not None
        self.assertEqual(child.stdout.readline().strip(), "ready")
        self.assert_rejected(
            lambda: REAL_SCAN_OPEN_FDS({str(fixture.database)}, pid_inventory=[child.pid]),
            "non-manager same-UID",
        )
        assert child.stdin is not None
        child.stdin.close()
        child.wait(timeout=5)
        child.stdout.close()
        assert child.stderr is not None
        child.stderr.close()

    def test_corrupt_and_busy_sqlite_are_rejected(self) -> None:
        fixture = self.fixture()
        fixture.database.write_bytes(b"not-a-sqlite-database")
        self.assert_rejected(lambda: fixture.execute("preflight"), "integrity")

        fixture = self.fixture()
        blocker = sqlite3.connect(fixture.database, timeout=0.0, isolation_level=None)
        blocker.execute("BEGIN EXCLUSIVE")
        self.addCleanup(blocker.close)
        self.assert_rejected(
            lambda: fixture.execute("migrate", confirmation=fixture.confirmation), "SQLite"
        )

    def test_collision_enospc_and_preexisting_target_are_rejected(self) -> None:
        fixture = self.fixture()
        other = fixture.legacy / "other.jsonl"
        other.write_text('{"different":true}\n', encoding="utf-8")
        fixture.plan["mappings"].append(
            {
                "kind": "regular",
                "source": str(other),
                "target": "data/agent-bridge/sidecars/events.jsonl",
                "validation": "jsonl",
            }
        )
        fixture.refresh_inventory()
        fixture.write_plan()
        self.assert_rejected(lambda: fixture.execute("preflight"), "overlap or duplicate")

        fixture = self.fixture()
        identical = fixture.legacy / "identical.jsonl"
        identical.write_bytes(fixture.events.read_bytes())
        fixture.plan["mappings"].append(
            {
                "kind": "regular",
                "source": str(identical),
                "target": "data/agent-bridge/sidecars/events.jsonl",
                "validation": "jsonl",
            }
        )
        fixture.refresh_inventory()
        fixture.write_plan()
        self.assert_rejected(
            lambda: fixture.execute("preflight"), "overlap or duplicate"
        )

        fixture = self.fixture()
        with mock.patch.object(MIGRATION, "free_bytes", return_value=0):
            self.assert_rejected(lambda: fixture.execute("preflight"), "lacks stage")

        fixture = self.fixture()
        target = fixture.root / "runtime-state/data/preexisting"
        target.write_text("occupied", encoding="ascii")
        target.chmod(0o600)
        self.assert_rejected(lambda: fixture.execute("preflight"), "skeleton must be empty")

    def test_pending_candidate_and_lock_drift_are_rejected(self) -> None:
        fixture = self.fixture()
        text = fixture.pending.read_text(encoding="ascii")
        fixture.pending.write_text(text.replace("challenge=" + "1" * 64, "challenge=" + "3" * 64), encoding="ascii")
        fixture.pending.chmod(0o600)
        self.assert_rejected(lambda: fixture.execute("preflight"), "pending digest")

        fixture = self.fixture()
        fixture.installed_script.write_text("tampered\n", encoding="ascii")
        fixture.installed_script.chmod(0o700)
        self.assert_rejected(lambda: fixture.execute("preflight"), "bytes do not match")

        fixture = self.fixture()
        fd = os.open(fixture.lock, os.O_RDWR)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        old = fixture.lock.with_suffix(".old")
        fixture.lock.rename(old)
        fixture.lock.write_bytes(b"")
        fixture.lock.chmod(0o600)
        self.assert_rejected(lambda: MIGRATION.validate_lock(str(fixture.lock), fd), "identity drifted")

    def test_fault_before_receipt_rolls_runtime_back(self) -> None:
        fixture = self.fixture(wal=True)
        platform = "darwin" if sys.platform == "darwin" else "linux"
        with mock.patch.object(
            MIGRATION, "publish_receipt", side_effect=MIGRATION.MigrationError("injected before receipt")
        ):
            self.assert_rejected(
                lambda: fixture.execute(
                    "migrate",
                    confirmation=fixture.confirmation,
                    platform=platform,
                ),
                "injected before receipt",
            )
        self.assertFalse((fixture.root / "publisher-state/migrations/current.json").exists())
        runtime = fixture.root / "runtime-state"
        self.assertEqual(set(path.name for path in runtime.iterdir()), set(MIGRATION.RUNTIME_LEAVES))
        self.assertTrue(all(not any(path.iterdir()) for path in runtime.iterdir()))
        self.assertFalse(any(fixture.root.glob("runtime-state.migration-stage.*")))

    @unittest.skipUnless(sys.platform == "darwin", "requires Darwin renameatx_np")
    def test_darwin_fault_before_receipt_rolls_runtime_back(self) -> None:
        fixture = self.fixture(wal=True)
        with mock.patch.object(
            MIGRATION,
            "publish_receipt",
            side_effect=MIGRATION.MigrationError("injected before Darwin receipt"),
        ):
            self.assert_rejected(
                lambda: fixture.execute(
                    "migrate",
                    confirmation=fixture.confirmation,
                    platform="darwin",
                ),
                "injected before Darwin receipt",
            )
        self.assertFalse(
            (fixture.root / "publisher-state/migrations/current.json").exists()
        )
        runtime = fixture.root / "runtime-state"
        self.assertEqual(
            {path.name for path in runtime.iterdir()}, set(MIGRATION.RUNTIME_LEAVES)
        )
        self.assertTrue(all(not any(path.iterdir()) for path in runtime.iterdir()))
        self.assertFalse(any(fixture.root.glob("runtime-state.migration-stage.*")))

    def test_final_gate_rehashes_sidecars_and_database_family_before_receipt(self) -> None:
        fixture = self.fixture()
        real_exchange = MIGRATION.rename_exchange

        def tamper_sidecar_then_exchange(left: str, right: str) -> None:
            fixture.events.write_text('{"event":"drifted","value":2}\n', encoding="utf-8")
            fixture.events.chmod(0o666)
            real_exchange(left, right)

        with mock.patch.object(
            MIGRATION, "rename_exchange", side_effect=tamper_sidecar_then_exchange
        ):
            self.assert_rejected(
                lambda: fixture.execute("migrate", confirmation=fixture.confirmation),
                "sidecar identity",
            )
        self.assertFalse((fixture.root / "publisher-state/migrations/current.json").exists())
        self.assertTrue(
            all(
                not any(path.iterdir())
                for path in (fixture.root / "runtime-state").iterdir()
            )
        )

        fixture = self.fixture()
        fixture.execute("migrate", confirmation=fixture.confirmation)
        migrated_state = snapshot(
            [
                fixture.root / "runtime-state",
                fixture.root / "publisher-state/migrations",
            ]
        )
        real_revalidate = MIGRATION.revalidate_bindings
        drifted = False

        def drift_after_locked_revalidate(context) -> None:
            nonlocal drifted
            real_revalidate(context)
            if context.command == "verify" and not drifted:
                drifted = True
                fixture.events.write_text('{"verify_race":"drift"}\n', encoding="utf-8")
                fixture.events.chmod(0o666)

        with mock.patch.object(
            MIGRATION, "revalidate_bindings", side_effect=drift_after_locked_revalidate
        ):
            self.assert_rejected(
                lambda: fixture.execute("verify"), "sidecar identity"
            )
        self.assertEqual(
            migrated_state,
            snapshot(
                [
                    fixture.root / "runtime-state",
                    fixture.root / "publisher-state/migrations",
                ]
            ),
        )
        self.assertTrue(
            (fixture.root / "publisher-state/migrations/current.json").is_file()
        )

        fixture = self.fixture()
        fixture.execute("migrate", confirmation=fixture.confirmation)
        original_events_inode = fixture.events.stat().st_ino
        real_revalidate = MIGRATION.revalidate_bindings
        replaced_directory = False

        def replace_source_directory_after_lock(context) -> None:
            nonlocal replaced_directory
            real_revalidate(context)
            if context.command == "verify" and not replaced_directory:
                replaced_directory = True
                retired = fixture.base / "retired-sidecars"
                os.rename(fixture.sidecars, retired)
                fixture.sidecars.mkdir(mode=0o755)
                fixture.sidecars.chmod(0o755)
                os.rename(retired / "events.jsonl", fixture.events)
                retired.rmdir()

        with mock.patch.object(
            MIGRATION,
            "revalidate_bindings",
            side_effect=replace_source_directory_after_lock,
        ):
            self.assert_rejected(
                lambda: fixture.execute("verify"), "sidecar identity"
            )
        self.assertEqual(fixture.events.stat().st_ino, original_events_inode)

        fixture = self.fixture()
        fixture.execute("migrate", confirmation=fixture.confirmation)
        target_events = (
            fixture.root
            / "runtime-state/data/agent-bridge/sidecars/events.jsonl"
        )
        real_revalidate = MIGRATION.revalidate_bindings
        revalidations = 0

        def drift_target_sidecar_after_final_revalidate(context) -> None:
            nonlocal revalidations
            real_revalidate(context)
            if context.command == "verify":
                revalidations += 1
                if revalidations == 2:
                    target_events.write_text(
                        '{"late_target":"drift"}\n', encoding="utf-8"
                    )
                    target_events.chmod(0o600)

        with mock.patch.object(
            MIGRATION,
            "revalidate_bindings",
            side_effect=drift_target_sidecar_after_final_revalidate,
        ):
            self.assert_rejected(
                lambda: fixture.execute("verify"), "target manifest drifted"
            )

        fixture = self.fixture()
        fixture.execute("migrate", confirmation=fixture.confirmation)
        target_database = fixture.root / "runtime-state" / MIGRATION.SQLITE_TARGET
        real_revalidate = MIGRATION.revalidate_bindings
        revalidations = 0

        def drift_target_database_after_final_revalidate(context) -> None:
            nonlocal revalidations
            real_revalidate(context)
            if context.command == "verify":
                revalidations += 1
                if revalidations == 2:
                    connection = sqlite3.connect(target_database)
                    try:
                        connection.execute(
                            "INSERT INTO memories(body) VALUES ('late-target-drift')"
                        )
                        connection.commit()
                    finally:
                        connection.close()

        with mock.patch.object(
            MIGRATION,
            "revalidate_bindings",
            side_effect=drift_target_database_after_final_revalidate,
        ):
            self.assert_rejected(
                lambda: fixture.execute("verify"),
                "target SQLite database fact drifted",
            )

        fixture = self.fixture()

        def create_journal_then_exchange(left: str, right: str) -> None:
            journal = Path(str(fixture.database) + "-journal")
            journal.write_bytes(b"late-writer")
            journal.chmod(0o666)
            real_exchange(left, right)

        with mock.patch.object(
            MIGRATION, "rename_exchange", side_effect=create_journal_then_exchange
        ):
            self.assert_rejected(
                lambda: fixture.execute("migrate", confirmation=fixture.confirmation),
                "must have no SQLite JOURNAL",
            )
        self.assertFalse((fixture.root / "publisher-state/migrations/current.json").exists())

    def test_tampered_receipt_target_source_and_source_wal_are_rejected(self) -> None:
        fixture = self.fixture()
        fixture.execute("migrate", confirmation=fixture.confirmation)
        receipt = fixture.root / "publisher-state/migrations/current.json"
        body = json.loads(receipt.read_text(encoding="ascii"))
        body["receipt_digest"] = "0" * 64
        receipt.write_text(json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii")
        receipt.chmod(0o600)
        self.assert_rejected(lambda: fixture.execute("verify"), "receipt digest")

        fixture = self.fixture()
        fixture.execute("migrate", confirmation=fixture.confirmation)
        target = fixture.root / "runtime-state/data/agent-bridge/sidecars/events.jsonl"
        target.write_text('{"tampered":true}\n', encoding="utf-8")
        target.chmod(0o600)
        self.assert_rejected(lambda: fixture.execute("verify"), "manifest drifted")

        fixture = self.fixture()
        fixture.execute("migrate", confirmation=fixture.confirmation)
        with fixture.database.open("ab") as handle:
            handle.write(b"tamper")
        self.assert_rejected(lambda: fixture.execute("verify"))

        fixture = self.fixture()
        fixture.execute("migrate", confirmation=fixture.confirmation)
        source_wal = Path(str(fixture.database) + "-wal")
        source_wal.write_bytes(b"writer-returned")
        source_wal.chmod(0o666)
        self.assert_rejected(lambda: fixture.execute("verify"), "must have no SQLite WAL")

        fixture = self.fixture()
        fixture.execute("migrate", confirmation=fixture.confirmation)
        source_journal = Path(str(fixture.database) + "-journal")
        source_journal.write_bytes(b"writer-returned")
        source_journal.chmod(0o666)
        self.assert_rejected(
            lambda: fixture.execute("verify"), "rollback journal must be absent"
        )

    def test_inherited_lock_fd_is_verified_without_opening_another_lock(self) -> None:
        fixture = self.fixture()
        fixture.execute("migrate", confirmation=fixture.confirmation)
        fd = os.open(fixture.lock, os.O_RDWR)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = fixture.execute("verify", inherited_lock_fd=fd)
        self.assertEqual(result["status"], "verified")
        self.assertGreaterEqual(os.fstat(fd).st_ino, 1)
        wrong_fd = os.open(fixture.plan_path, os.O_RDONLY)
        self.addCleanup(os.close, wrong_fd)
        self.assert_rejected(
            lambda: fixture.execute("verify", inherited_lock_fd=wrong_fd),
            "does not match the fixed lock path",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
