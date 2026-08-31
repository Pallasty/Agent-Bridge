#!/usr/bin/python3
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("publish-and-acquire-trusted-seed.py")
SPEC = importlib.util.spec_from_file_location("publication_seed", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def run(*args: str, cwd: Path) -> str:
    result = subprocess.run(["/usr/bin/git", *args], cwd=cwd, check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            env={"PATH": "/usr/bin:/bin", "HOME": str(cwd), "LANG": "C", "LC_ALL": "C"})
    return result.stdout.strip()


class Fixture:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.source = base / "source"
        self.remote = base / "gitlab.git"
        self.seed_parent = base / "seeds"
        self.seed = self.seed_parent / "agent-bridge"
        self.key = base / "gitlab-key"
        self.known = base / "known-hosts"
        self.manifest = base / "manifest.json"
        self.source.mkdir(mode=0o700)
        self.seed_parent.mkdir(mode=0o700)
        self.key.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nfixture\n-----END OPENSSH PRIVATE KEY-----\n")
        self.known.write_text("gitlab.com ssh-ed25519 AAAAfixture\n")
        os.chmod(self.key, 0o600)
        os.chmod(self.known, 0o600)
        run("init", "-q", "--bare", str(self.remote), cwd=base)
        run("-C", str(self.remote), "config", "receive.advertisePushOptions", "true", cwd=base)
        run("init", "-q", "-b", "master", cwd=self.source)
        run("config", "user.name", "fixture", cwd=self.source)
        run("config", "user.email", "fixture@invalid", cwd=self.source)
        (self.source / "README.md").write_text("base\n")
        run("add", "README.md", cwd=self.source)
        run("commit", "-q", "-m", "base", cwd=self.source)
        run("remote", "add", "gitlab", str(self.remote), cwd=self.source)
        run("push", "-q", "gitlab", "master", cwd=self.source)
        (self.source / "README.md").write_text("candidate\n")
        run("commit", "-qam", "candidate", cwd=self.source)
        self.candidate = run("rev-parse", "HEAD", cwd=self.source)
        self.write_manifest()

    def write_manifest(self, **changes: object) -> None:
        value = {"schema": MODULE.SCHEMA, "candidate_commit": self.candidate,
                 "source_repository": str(self.source), "seed_path": str(self.seed),
                 "gitlab_deploy_key": str(self.key), "known_hosts": str(self.known)}
        value.update(changes)
        if "authentication" in changes:
            value.pop("gitlab_deploy_key")
        self.manifest.write_text(json.dumps(value, sort_keys=True))
        os.chmod(self.manifest, 0o600)

    def invoke(self, command: str, confirm: str | None = None) -> tuple[int, dict[str, object] | None, str]:
        argv = [command, "--manifest", str(self.manifest)]
        if confirm is not None:
            argv += ["--confirm", confirm]
        output, error = io.BytesIO(), io.StringIO()
        class Buffer:
            def __init__(self, target: io.BytesIO) -> None: self.buffer = target
        with contextlib.redirect_stdout(Buffer(output)), contextlib.redirect_stderr(error):
            status = MODULE.main(argv)
        packet = json.loads(output.getvalue()) if output.getvalue() else None
        return status, packet, error.getvalue()


class PublicationSeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ab-publication-seed.")
        self.base = Path(self.temp.name).resolve()
        os.chmod(self.base, 0o700)
        self.fixture = Fixture(self.base)
        self.original_remote = MODULE.REMOTE
        MODULE.REMOTE = str(self.fixture.remote)

    def tearDown(self) -> None:
        MODULE.REMOTE = self.original_remote
        self.temp.cleanup()

    def test_plan_wrong_confirmation_publish_skip_and_seed_happy_path(self) -> None:
        before = sorted(str(path.relative_to(self.base)) for path in self.base.rglob("*"))
        status, plan, error = self.fixture.invoke("plan")
        self.assertEqual(status, 0, error)
        assert plan
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["ci_policy"], "skip")
        after = sorted(str(path.relative_to(self.base)) for path in self.base.rglob("*"))
        self.assertEqual(before, after)
        status, _, error = self.fixture.invoke("publish", "wrong")
        self.assertNotEqual(status, 0)
        self.assertIn("confirmation is not exact", error)
        self.assertNotEqual(run("--git-dir", str(self.fixture.remote), "rev-parse", "master", cwd=self.base), self.fixture.candidate)

        status, packet, error = self.fixture.invoke("publish", str(plan["confirmation"]))
        self.assertEqual(status, 0, error)
        assert packet
        self.assertEqual(packet["status"], "published_authoritative_candidate")
        self.assertEqual(packet["ci_policy"], "skip")
        status, packet, error = self.fixture.invoke("acquire-seed")
        self.assertEqual(status, 0, error)
        self.assertEqual(packet["status"], "acquired_independent_seed")
        self.assertEqual(stat.S_IMODE(self.fixture.seed.stat().st_mode), 0o700)
        status, packet, error = self.fixture.invoke("verify")
        self.assertEqual(status, 0, error)
        self.assertEqual(packet["status"], "verified_publication_and_seed")
        local_config = run(
            "-C", str(self.fixture.seed), "config", "--local", "--list", cwd=self.base
        )
        self.assertNotIn("core.ignorecase", local_config)
        self.assertNotIn("core.precomposeunicode", local_config)

    def test_non_fast_forward_dirty_input_and_existing_seed_fail_closed(self) -> None:
        (self.fixture.source / "dirty").write_text("dirty\n")
        status, _, error = self.fixture.invoke("plan")
        self.assertNotEqual(status, 0)
        self.assertIn("completely clean", error)
        (self.fixture.source / "dirty").unlink()

        self.fixture.seed.mkdir(mode=0o700)
        status, _, error = self.fixture.invoke("acquire-seed")
        self.assertNotEqual(status, 0)
        self.assertIn("not authoritative", error)

        self.fixture.write_manifest(candidate_commit="0" * 40)
        status, _, error = self.fixture.invoke("plan")
        self.assertNotEqual(status, 0)
        self.assertIn("HEAD does not equal", error)

    def test_manifest_and_private_input_custody_are_strict(self) -> None:
        raw = self.fixture.manifest.read_text()
        self.fixture.manifest.write_text(raw.replace('{', '{"schema":"duplicate",', 1))
        os.chmod(self.fixture.manifest, 0o600)
        status, _, error = self.fixture.invoke("plan")
        self.assertNotEqual(status, 0)
        self.assertIn("duplicate key schema", error)
        self.fixture.write_manifest()
        os.chmod(self.fixture.key, 0o644)
        status, _, error = self.fixture.invoke("plan")
        self.assertNotEqual(status, 0)
        self.assertIn("mode must be 0600", error)

    def test_seed_tamper_and_remote_drift_are_rejected(self) -> None:
        _, plan, _ = self.fixture.invoke("plan")
        assert plan
        self.assertEqual(self.fixture.invoke("publish", str(plan["confirmation"]))[0], 0)
        self.assertEqual(self.fixture.invoke("acquire-seed")[0], 0)
        (self.fixture.seed / "tamper").write_text("x\n")
        status, _, error = self.fixture.invoke("verify")
        self.assertNotEqual(status, 0)
        self.assertIn("not clean", error)
        (self.fixture.seed / "tamper").unlink()
        run(
            "-C", str(self.fixture.seed), "config", "filter.bad.clean", "/bin/false",
            cwd=self.base,
        )
        status, _, error = self.fixture.invoke("verify")
        self.assertNotEqual(status, 0)
        self.assertIn("Git authority configuration drifted", error)

    def test_agent_socket_mode_binds_exact_public_identity(self) -> None:
        agent_key = self.base / "agent-key"
        subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(agent_key)], check=True)
        public_key = Path(str(agent_key) + ".pub")
        os.chmod(public_key, 0o600)
        fingerprint = subprocess.run(
            ["/usr/bin/ssh-keygen", "-E", "sha256", "-lf", str(public_key)],
            check=True, stdout=subprocess.PIPE, text=True,
        ).stdout.split()[1]
        socket_path = self.base / "agent.sock"
        agent_socket = socket.socket(socket.AF_UNIX)
        agent_socket.bind(str(socket_path))
        os.chmod(socket_path, 0o600)
        try:
            self.fixture.write_manifest(authentication={
                "mode": "agent_socket", "socket_path": str(socket_path),
                "public_key_path": str(public_key), "public_key_fingerprint": fingerprint,
            })
            with mock.patch.object(MODULE, "agent_fingerprints", return_value={fingerprint}):
                status, plan, error = self.fixture.invoke("plan")
                self.assertEqual(status, 0, error)
                assert plan
                self.assertEqual(self.fixture.invoke("publish", str(plan["confirmation"]))[0], 0)
                self.assertEqual(self.fixture.invoke("acquire-seed")[0], 0)
                self.assertEqual(self.fixture.invoke("verify")[0], 0)
            self.fixture.seed.rename(self.base / "accepted-seed")
            self.fixture.write_manifest(authentication={
                "mode": "agent_socket", "socket_path": str(socket_path),
                "public_key_path": str(public_key), "public_key_fingerprint": "SHA256:wrong",
            })
            rejected = self.fixture.invoke("plan")
            self.assertNotEqual(rejected[0], 0)
            self.assertIn("does not match", rejected[2])
        finally:
            agent_socket.close()

    def test_github_requires_commit_skip_and_never_uses_gitlab_push_option(self) -> None:
        governed_remote = str(self.fixture.remote)
        original_authority = MODULE.AUTHORITIES.get(governed_remote)
        MODULE.AUTHORITIES[governed_remote] = {
            "name": "github", "host": "github.com", "ci_policy": "commit_message",
        }
        self.fixture.known.write_text("github.com ssh-ed25519 AAAAfixture\n")
        os.chmod(self.fixture.known, 0o600)

        def governed_manifest() -> None:
            value = {
                "schema": MODULE.SCHEMA,
                "candidate_commit": self.fixture.candidate,
                "source_repository": str(self.fixture.source),
                "seed_path": str(self.fixture.seed),
                "authoritative_remote": governed_remote,
                "deploy_key": str(self.fixture.key),
                "known_hosts": str(self.fixture.known),
            }
            self.fixture.manifest.write_text(json.dumps(value, sort_keys=True))
            os.chmod(self.fixture.manifest, 0o600)

        try:
            governed_manifest()
            status, _, error = self.fixture.invoke("plan")
            self.assertNotEqual(status, 0)
            self.assertIn("lacks an exact workflow skip instruction", error)

            run("commit", "--amend", "-q", "-m", "candidate [skip ci]", cwd=self.fixture.source)
            self.fixture.candidate = run("rev-parse", "HEAD", cwd=self.fixture.source)
            governed_manifest()
            status, plan, error = self.fixture.invoke("plan")
            self.assertEqual(status, 0, error)
            assert plan
            self.assertEqual(plan["ci_mechanism"], "commit_message")

            observed: list[tuple[str, ...]] = []
            original_git = MODULE.git

            def recording_git(args: tuple[str, ...], **kwargs: object) -> bytes:
                observed.append(tuple(args))
                return original_git(args, **kwargs)

            with mock.patch.object(MODULE, "git", side_effect=recording_git):
                status, packet, error = self.fixture.invoke(
                    "publish", str(plan["confirmation"])
                )
            self.assertEqual(status, 0, error)
            assert packet
            pushes = [args for args in observed if args and args[0] == "push"]
            self.assertEqual(len(pushes), 1)
            self.assertNotIn("--push-option=ci.skip", pushes[0])
        finally:
            if original_authority is None:
                MODULE.AUTHORITIES.pop(governed_remote, None)
            else:
                MODULE.AUTHORITIES[governed_remote] = original_authority

    def test_atomic_seed_activation_never_replaces_a_racing_target(self) -> None:
        source = self.base / "activation-source"
        destination = self.base / "activation-destination"
        source.mkdir()
        destination.mkdir()
        marker = destination / "owned"
        marker.write_text("preserve\n")
        with self.assertRaisesRegex(MODULE.Blocked, "appeared during atomic activation"):
            MODULE.rename_noreplace(str(source), str(destination))
        self.assertTrue(source.is_dir())
        self.assertEqual(marker.read_text(), "preserve\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
