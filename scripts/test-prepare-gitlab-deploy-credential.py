#!/usr/bin/python3
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("prepare-gitlab-deploy-credential.py").resolve()
PYTHON = "/usr/bin/python3"


class Fixture:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.parent = base / "private"
        self.parent.mkdir(mode=0o700)
        self.target = self.parent / "gitlab"
        self.manifest = base / "manifest.json"
        self.write_manifest()

    def write_manifest(self, **changes: object) -> None:
        value = {"schema": "agent_bridge.gitlab_deploy_credential_manifest.v1",
                 "target_directory": str(self.target), "project_path": "pallasting/agent-bridge",
                 "key_comment": "agent-bridge-r9-release"}
        value.update(changes)
        self.manifest.write_text(json.dumps(value, sort_keys=True) + "\n")
        os.chmod(self.manifest, 0o600)

    def run(self, command: str, confirm: str | None = None) -> subprocess.CompletedProcess[str]:
        args = [PYTHON, "-I", "-B", "-W", "error", str(SCRIPT), command, "--manifest", str(self.manifest)]
        if confirm is not None: args += ["--confirm", confirm]
        return subprocess.run(args, env={"PATH": "/usr/bin:/bin", "HOME": str(self.base), "LANG": "C", "LC_ALL": "C"},
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)

    def plan(self) -> dict[str, object]:
        result = self.run("plan")
        if result.returncode: raise AssertionError(result.stderr)
        return json.loads(result.stdout)

    def generate(self) -> dict[str, object]:
        plan = self.plan()
        result = self.run("generate", str(plan["confirmation"]))
        if result.returncode: raise AssertionError(result.stderr)
        return json.loads(result.stdout)


def snapshot(root: Path) -> list[tuple[str, int, int]]:
    return [(str(path.relative_to(root)), stat.S_IMODE(path.lstat().st_mode), path.lstat().st_size)
            for path in sorted([root, *root.rglob("*")])]


class CredentialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ab-gitlab-credential.")
        self.base = Path(self.temp.name).resolve()
        os.chmod(self.base, 0o700)
        self.fixture = Fixture(self.base)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_plan_is_zero_write_wrong_confirmation_and_happy_generate_verify(self) -> None:
        before = snapshot(self.base)
        plan = self.fixture.plan()
        self.assertEqual(before, snapshot(self.base))
        self.assertEqual(plan["authority_state"], "will_generate_local_key_not_enrolled")
        wrong = self.fixture.run("generate", "wrong")
        self.assertNotEqual(wrong.returncode, 0)
        self.assertFalse(self.fixture.target.exists())
        generated = self.fixture.generate()
        self.assertEqual(generated["status"], "generated_local_key_not_enrolled")
        self.assertNotIn("PRIVATE KEY", generated.__repr__())
        self.assertEqual(stat.S_IMODE(self.fixture.target.stat().st_mode), 0o700)
        for name in ("gitlab_deploy_key", "gitlab_deploy_key.pub", "known_hosts", "enrollment.json", "receipt.json"):
            self.assertEqual(stat.S_IMODE((self.fixture.target / name).stat().st_mode), 0o600)
        verified = self.fixture.run("verify")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertEqual(json.loads(verified.stdout)["status"], "verified_local_key_not_enrolled")
        enrollment = json.loads((self.fixture.target / "enrollment.json").read_text())
        self.assertEqual(enrollment["enrollment_status"], "not_enrolled")
        self.assertEqual(enrollment["required_access"], "write_repository")

    def test_manifest_duplicate_invalid_comment_existing_target_and_stage_fail_closed(self) -> None:
        raw = self.fixture.manifest.read_text()
        self.fixture.manifest.write_text(raw.replace('{', '{"schema":"duplicate",', 1))
        os.chmod(self.fixture.manifest, 0o600)
        duplicate = self.fixture.run("plan")
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("duplicate key schema", duplicate.stderr)
        self.fixture.write_manifest(key_comment="bad comment")
        invalid = self.fixture.run("plan")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("key comment is invalid", invalid.stderr)
        self.fixture.write_manifest()
        plan = self.fixture.plan()
        stage = Path(str(self.fixture.target) + ".credential-stage")
        stage.mkdir(mode=0o700)
        marker = stage / "owner-marker"
        marker.write_text("retain\n")
        os.chmod(marker, 0o600)
        collision = self.fixture.run("generate", str(plan["confirmation"]))
        self.assertNotEqual(collision.returncode, 0)
        self.assertIn("stage already exists", collision.stderr)
        self.assertEqual(marker.read_text(), "retain\n")
        marker.unlink()
        stage.rmdir()
        self.fixture.target.mkdir(mode=0o700)
        existing = self.fixture.run("plan")
        self.assertNotEqual(existing.returncode, 0)
        self.assertIn("target already exists", existing.stderr)

    def test_replaceable_ancestor_and_manifest_mode_are_rejected(self) -> None:
        os.chmod(self.fixture.manifest, 0o644)
        mode = self.fixture.run("plan")
        self.assertNotEqual(mode.returncode, 0)
        self.assertIn("custody is invalid", mode.stderr)
        os.chmod(self.fixture.manifest, 0o600)
        os.chmod(self.fixture.parent, 0o777)
        ancestor = self.fixture.run("plan")
        self.assertNotEqual(ancestor.returncode, 0)
        self.assertIn("mode-0700 directory", ancestor.stderr)

    def test_private_public_known_hosts_receipt_and_mode_tamper_are_rejected(self) -> None:
        cases = ("private", "public", "known", "receipt", "mode")
        for case in cases:
            with self.subTest(case=case):
                base = self.base / f"case-{case}"
                base.mkdir(mode=0o700)
                fixture = Fixture(base)
                fixture.generate()
                if case == "private":
                    path = fixture.target / "gitlab_deploy_key"
                    path.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\ntampered\n")
                elif case == "public":
                    path = fixture.target / "gitlab_deploy_key.pub"
                    path.write_text("ssh-ed25519 AAAAtampered fixture\n")
                elif case == "known":
                    path = fixture.target / "known_hosts"
                    path.write_text("gitlab.com ssh-ed25519 AAAAtampered\n")
                elif case == "receipt":
                    path = fixture.target / "receipt.json"
                    path.write_bytes(path.read_bytes().replace(b"local_key_not_enrolled", b"enrolled", 1))
                else:
                    path = fixture.target / "enrollment.json"
                    os.chmod(path, 0o644)
                rejected = fixture.run("verify")
                self.assertNotEqual(rejected.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
