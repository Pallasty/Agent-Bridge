#!/usr/bin/python3
"""Adversarial isolated tests for trusted-root provisioning v1."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("provision-trusted-deployment-root.py").resolve()
SPEC = importlib.util.spec_from_file_location("trusted_root_provisioning", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
PUBLICATION_SCRIPT = Path(__file__).with_name("publish-and-acquire-trusted-seed.py").resolve()
CREDENTIAL_SCRIPT = Path(__file__).with_name("prepare-gitlab-deploy-credential.py").resolve()
PYTHON = "/usr/bin/python3"
REMOTE = "git@gitlab.com:pallasting/agent-bridge.git"
GITHUB_REMOTE = "git@github.com:pallasting/Agent-Bridge.git"
MIN_FREE = 2 * 1024 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(repo: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_EMAIL": "r9-fixture@invalid",
        "GIT_AUTHOR_NAME": "R9 fixture",
        "GIT_COMMITTER_EMAIL": "r9-fixture@invalid",
        "GIT_COMMITTER_NAME": "R9 fixture",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(repo),
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
    }
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(repo), *args],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.decode("ascii").strip()


def private_tree(path: Path) -> None:
    for current, directories, files in os.walk(path):
        os.chmod(current, 0o700)
        for name in directories:
            os.chmod(Path(current, name), 0o700)
        for name in files:
            target = Path(current, name)
            mode = stat.S_IMODE(target.lstat().st_mode)
            os.chmod(target, 0o700 if mode & 0o100 else 0o600)


def start_test_agent(base: Path) -> tuple[subprocess.Popen[bytes], Path, Path, str]:
    private_key = base / "agent-identity"
    subprocess.run(
        ["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)],
        check=True,
    )
    public_key = Path(str(private_key) + ".pub")
    os.chmod(public_key, 0o600)
    socket_path = base / "agent.sock"
    process = subprocess.Popen(
        ["/usr/bin/ssh-agent", "-D", "-a", str(socket_path)],
        env={"PATH": "/usr/bin:/bin", "HOME": str(base), "LANG": "C", "LC_ALL": "C"},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(200):
        if socket_path.exists():
            break
        if process.poll() is not None:
            raise AssertionError("test ssh-agent exited before creating its socket")
        time.sleep(0.01)
    else:
        process.terminate()
        raise AssertionError("test ssh-agent did not create its socket")
    os.chmod(socket_path, 0o600)
    env = {
        "PATH": "/usr/bin:/bin", "HOME": str(base), "LANG": "C", "LC_ALL": "C",
        "SSH_AUTH_SOCK": str(socket_path),
    }
    subprocess.run(
        ["/usr/bin/ssh-add", str(private_key)], env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        check=True,
    )
    fingerprint = subprocess.run(
        ["/usr/bin/ssh-keygen", "-E", "sha256", "-lf", str(public_key)],
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, check=True,
    ).stdout.split()[1]
    return process, socket_path, public_key, fingerprint


class Fixture:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.seed = base / "seed"
        self.toolchain = base / "toolchain-input"
        self.inputs = base / "inputs"
        self.root = base / "trusted-root"
        self.manifest = base / "provision.json"
        self._write_seed()
        self._write_toolchain()
        self._write_inputs()
        self.write_manifest()

    def _write_seed(self) -> None:
        paths = {
            "scripts/provision-trusted-deployment-root.py": SCRIPT.read_bytes(),
            "scripts/publish-and-acquire-trusted-seed.py": PUBLICATION_SCRIPT.read_bytes(),
            "scripts/prepare-gitlab-deploy-credential.py": CREDENTIAL_SCRIPT.read_bytes(),
            "scripts/deploy_from_master.sh": b"#!/bin/sh\nexit 0\n",
            "scripts/migrate-trusted-runtime-state.py": b"#!/usr/bin/python3\n",
            "scripts/systemd/install-trusted-daemon-root.sh": b"#!/bin/sh\nexit 0\n",
            "scripts/wrapper/install.sh": b"#!/bin/sh\nexit 0\n",
            "scripts/wrapper/agent-bridge-wrapper.sh": b"#!/bin/sh\nexit 0\n",
            "scripts/wrapper/creds.example": b"# Agent-Bridge Primary\n",
            "README.md": b"fixture\n",
        }
        for relative, content in paths.items():
            target = self.seed / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        for relative in (
            "scripts/provision-trusted-deployment-root.py",
            "scripts/publish-and-acquire-trusted-seed.py",
            "scripts/prepare-gitlab-deploy-credential.py",
            "scripts/deploy_from_master.sh",
            "scripts/migrate-trusted-runtime-state.py",
            "scripts/systemd/install-trusted-daemon-root.sh",
        ):
            os.chmod(self.seed / relative, 0o700)
        os.chmod(self.seed / "scripts/wrapper/install.sh", 0o600)
        os.chmod(self.seed / "scripts/wrapper/agent-bridge-wrapper.sh", 0o600)
        os.chmod(self.seed / "scripts/wrapper/creds.example", 0o600)
        subprocess.run(
            ["/usr/bin/git", "init", "-q", "-b", "master", str(self.seed)],
            check=True,
        )
        run_git(self.seed, "config", "user.name", "R9 fixture")
        run_git(self.seed, "config", "user.email", "r9-fixture@invalid")
        run_git(self.seed, "add", ".")
        run_git(self.seed, "commit", "-q", "-m", "fixture")
        self.candidate = run_git(self.seed, "rev-parse", "HEAD")
        run_git(self.seed, "config", "--unset-all", "user.name")
        run_git(self.seed, "config", "--unset-all", "user.email")
        run_git(self.seed, "remote", "add", "gitlab", REMOTE)
        run_git(self.seed, "config", "branch.master.remote", "gitlab")
        run_git(self.seed, "config", "branch.master.merge", "refs/heads/master")
        run_git(self.seed, "update-ref", "refs/remotes/gitlab/master", self.candidate)
        private_tree(self.seed)

    def _write_toolchain(self) -> None:
        (self.toolchain / "bin").mkdir(parents=True)
        (self.toolchain / "lib").mkdir()
        (self.toolchain / "bin/cargo").write_text("#!/bin/sh\nexit 0\n")
        (self.toolchain / "bin/rustc").write_text("#!/bin/sh\nexit 0\n")
        (self.toolchain / "lib/runtime.dat").write_bytes(b"toolchain fixture\n")
        private_tree(self.toolchain)
        os.chmod(self.toolchain / "bin/cargo", 0o700)
        os.chmod(self.toolchain / "bin/rustc", 0o700)

    def _write_inputs(self) -> None:
        self.inputs.mkdir()
        self.key = self.inputs / "gitlab_deploy_key"
        self.known = self.inputs / "known_hosts"
        self.machine = self.inputs / "machine.env"
        self.credentials = self.inputs / "credentials"
        self.key.write_text(
            "-----BEGIN OPENSSH PRIVATE KEY-----\nfixture-private-data\n"
            "-----END OPENSSH PRIVATE KEY-----\n"
        )
        self.known.write_text("gitlab.com ssh-ed25519 AAAAC3NzaFixture\n")
        self.machine.write_text("export AB_SUBSTRATE_PROJECTION=bucket_pool\n")
        self.credentials.write_text("# Agent-Bridge Primary\nANTHROPIC_API_KEY=fixture\n")
        private_tree(self.inputs)

    def payload(self) -> dict[str, object]:
        def file(path: Path) -> dict[str, str]:
            return {"path": str(path), "sha256": sha256(path)}

        return {
            "schema": "agent_bridge.trusted_deployment_root_provisioning_manifest.v1",
            "candidate_commit": self.candidate,
            "deploy_root": str(self.root),
            "source_repository": str(self.seed),
            "authoritative_remote": REMOTE,
            "inputs": {
                "gitlab_deploy_key": file(self.key),
                "known_hosts": file(self.known),
                "toolchain": {"path": str(self.toolchain)},
                "machine_env": file(self.machine),
                "credentials": file(self.credentials),
            },
            "limits": {
                "max_source_files": 1000,
                "max_source_bytes": 16 * 1024 * 1024,
                "max_toolchain_files": 100,
                "max_toolchain_bytes": 1024 * 1024,
                "min_free_bytes_after": MIN_FREE,
            },
        }

    def write_manifest(self, payload: dict[str, object] | None = None) -> None:
        self.manifest.write_text(
            json.dumps(payload or self.payload(), sort_keys=True, indent=2) + "\n"
        )
        os.chmod(self.manifest, 0o600)

    def run(
        self,
        command: str,
        *,
        confirm: str | None = None,
        copied: bool = False,
        deploy_root: Path | None = None,
        inherited_fd: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        script = (
            self.root / "source/agent-bridge/scripts/provision-trusted-deployment-root.py"
            if copied
            else SCRIPT
        )
        args = [PYTHON, "-I", "-B", "-W", "error", str(script), command]
        selected_root = deploy_root or self.root
        if command == "verify":
            args += ["--deploy-root", str(selected_root)]
            if inherited_fd is not None:
                args += ["--inherited-lock-fd", str(inherited_fd)]
        else:
            args += ["--manifest", str(self.manifest), "--deploy-root", str(selected_root)]
            if command == "provision" and confirm is not None:
                args += ["--confirm", confirm]
        return subprocess.run(
            args,
            env={"HOME": str(self.base), "LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            pass_fds=(() if inherited_fd is None else (inherited_fd,)),
        )

    def plan(self) -> dict[str, object]:
        result = self.run("plan")
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(result.stdout)

    def provision(self) -> dict[str, object]:
        plan = self.plan()
        result = self.run("provision", confirm=str(plan["confirmation"]))
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(result.stdout)


def snapshot(root: Path) -> dict[str, tuple[int, int, str | None]]:
    result: dict[str, tuple[int, int, str | None]] = {}
    for path in sorted([root, *root.rglob("*")]):
        relative = str(path.relative_to(root)) if path != root else "."
        st = path.lstat()
        digest = sha256(path) if path.is_file() and not path.is_symlink() else None
        result[relative] = (stat.S_IMODE(st.st_mode), st.st_size, digest)
    return result


class ProvisioningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="ab-root-provision-test.")
        self.base = Path(self.temporary.name).resolve()
        os.chmod(self.base, 0o700)
        self.fixture = Fixture(self.base)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_plan_is_zero_write_and_confirmation_is_required(self) -> None:
        before = snapshot(self.base)
        plan = self.fixture.plan()
        after = snapshot(self.base)
        self.assertEqual(before, after)
        self.assertEqual(plan["status"], "ready")
        self.assertRegex(
            str(plan["confirmation"]),
            rf"^PROVISION:{self.fixture.candidate}:[0-9a-f]{{64}}$",
        )
        rejected = self.fixture.run("provision", confirm="PROVISION:wrong")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse(self.fixture.root.exists())
        self.assertEqual(list(self.base.glob(".trusted-root.provision-stage.*")), [])

    def test_happy_provision_and_independent_verify(self) -> None:
        provisioned = self.fixture.provision()
        self.assertEqual(provisioned["status"], "provisioned_bootstrap")
        self.assertEqual(stat.S_IMODE(self.fixture.root.stat().st_mode), 0o700)
        verified = self.fixture.run("verify", copied=True)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        packet = json.loads(verified.stdout)
        self.assertEqual(packet["status"], "verified_provisioning_custody")
        self.assertEqual(
            run_git(self.fixture.root / "source/agent-bridge", "status", "--porcelain=v1"),
            "",
        )
        self.assertNotIn("fixture-private-data", provisioned.__repr__())
        self.assertNotIn("fixture-private-data", verified.stdout)
        self.assertEqual(
            stat.S_IMODE((self.fixture.root / "publisher-state/deploy/publisher.kernel.lock").stat().st_mode),
            0o600,
        )

    def test_custody_normalization_may_not_dirty_source_before_activation(self) -> None:
        migration = self.fixture.seed / "scripts/migrate-trusted-runtime-state.py"
        run_git(
            self.fixture.seed,
            "update-index",
            "--chmod=-x",
            "scripts/migrate-trusted-runtime-state.py",
        )
        os.chmod(migration, 0o600)
        run_git(self.fixture.seed, "commit", "-q", "-m", "non-executable orchestrator")
        self.fixture.candidate = run_git(self.fixture.seed, "rev-parse", "HEAD")
        run_git(
            self.fixture.seed,
            "update-ref",
            "refs/remotes/gitlab/master",
            self.fixture.candidate,
        )
        self.assertEqual(run_git(self.fixture.seed, "status", "--porcelain=v1"), "")
        self.fixture.write_manifest()

        plan = self.fixture.plan()
        rejected = self.fixture.run(
            "provision", confirm=str(plan["confirmation"])
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            "copied source repository is not clean after custody normalization",
            rejected.stderr,
        )
        self.assertFalse(self.fixture.root.exists())
        self.assertEqual(list(self.base.glob(".trusted-root.provision-stage.*")), [])

    def test_agent_authentication_provisions_no_private_key_and_verifies_offline(self) -> None:
        process, socket_path, public_key, fingerprint = start_test_agent(self.base)
        try:
            payload = self.fixture.payload()
            inputs = payload["inputs"]
            assert isinstance(inputs, dict)
            inputs.pop("gitlab_deploy_key")
            inputs["gitlab_authentication"] = {
                "mode": "agent_socket",
                "socket_path": str(socket_path),
                "public_key": {"path": str(public_key), "sha256": sha256(public_key)},
                "public_key_fingerprint": fingerprint,
            }
            self.fixture.write_manifest(payload)
            provisioned = self.fixture.provision()
            self.assertEqual(provisioned["status"], "provisioned_bootstrap")
            git_config = self.fixture.root / "config/git"
            self.assertFalse((git_config / "gitlab_deploy_key").exists())
            self.assertTrue((git_config / "gitlab_agent_key.pub").is_file())
            descriptor = json.loads((git_config / "authentication.json").read_text())
            self.assertEqual(descriptor["mode"], "agent_socket")
            self.assertEqual(descriptor["public_key_fingerprint"], fingerprint)
        finally:
            process.terminate()
            process.wait(timeout=5)
        verified = self.fixture.run("verify", copied=True)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        descriptor_path = self.fixture.root / "config/git/authentication.json"
        descriptor_path.write_bytes(
            descriptor_path.read_bytes().replace(b"agent_socket", b"tampered", 1)
        )
        os.chmod(descriptor_path, 0o600)
        rejected = self.fixture.run("verify", copied=True)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("installed gitlab_authentication drifted", rejected.stderr)

    def test_github_agent_authority_provisions_and_verifies_offline(self) -> None:
        run_git(self.fixture.seed, "remote", "rename", "gitlab", "github")
        run_git(self.fixture.seed, "remote", "set-url", "github", GITHUB_REMOTE)
        private_tree(self.fixture.seed)
        self.fixture.known.write_text("github.com ssh-ed25519 AAAAC3NzaFixture\n")
        os.chmod(self.fixture.known, 0o600)
        process, socket_path, public_key, fingerprint = start_test_agent(self.base)
        try:
            payload = self.fixture.payload()
            payload["authoritative_remote"] = GITHUB_REMOTE
            inputs = payload["inputs"]
            assert isinstance(inputs, dict)
            inputs.pop("gitlab_deploy_key")
            inputs["github_authentication"] = {
                "mode": "agent_socket",
                "socket_path": str(socket_path),
                "public_key": {"path": str(public_key), "sha256": sha256(public_key)},
                "public_key_fingerprint": fingerprint,
            }
            self.fixture.write_manifest(payload)
            provisioned = self.fixture.provision()
            self.assertEqual(provisioned["status"], "provisioned_bootstrap")
            git_config = self.fixture.root / "config/git"
            self.assertFalse((git_config / "gitlab_agent_key.pub").exists())
            self.assertTrue((git_config / "github_agent_key.pub").is_file())
            descriptor = json.loads((git_config / "authentication.json").read_text())
            self.assertEqual(
                descriptor["schema"],
                "agent_bridge.github_agent_authentication.v1",
            )
            self.assertEqual(descriptor["public_key_path"], "github_agent_key.pub")
            source = self.fixture.root / "source/agent-bridge"
            self.assertEqual(run_git(source, "remote", "get-url", "github"), GITHUB_REMOTE)
        finally:
            process.terminate()
            process.wait(timeout=5)
        verified = self.fixture.run("verify", copied=True)
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_agent_authentication_requires_the_exact_loaded_identity(self) -> None:
        process, socket_path, public_key, fingerprint = start_test_agent(self.base)
        try:
            subprocess.run(
                ["/usr/bin/ssh-add", "-D"],
                env={
                    "PATH": "/usr/bin:/bin", "HOME": str(self.base), "LANG": "C", "LC_ALL": "C",
                    "SSH_AUTH_SOCK": str(socket_path),
                },
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                check=True,
            )
            payload = self.fixture.payload()
            inputs = payload["inputs"]
            assert isinstance(inputs, dict)
            inputs.pop("gitlab_deploy_key")
            inputs["gitlab_authentication"] = {
                "mode": "agent_socket",
                "socket_path": str(socket_path),
                "public_key": {"path": str(public_key), "sha256": sha256(public_key)},
                "public_key_fingerprint": fingerprint,
            }
            self.fixture.write_manifest(payload)
            rejected = self.fixture.run("plan")
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("identity is absent", rejected.stderr)
        finally:
            process.terminate()
            process.wait(timeout=5)

    def test_clean_descendant_source_advance_remains_admissible(self) -> None:
        self.fixture.provision()
        source = self.fixture.root / "source/agent-bridge"
        run_git(source, "config", "user.name", "R9 fixture")
        run_git(source, "config", "user.email", "r9-fixture@invalid")
        readme = source / "README.md"
        readme.write_text("fixture descendant\n")
        os.chmod(readme, 0o600)
        run_git(source, "add", "README.md")
        run_git(source, "commit", "-q", "-m", "descendant")
        descendant = run_git(source, "rev-parse", "HEAD")
        run_git(source, "config", "--unset-all", "user.name")
        run_git(source, "config", "--unset-all", "user.email")
        run_git(source, "update-ref", "refs/remotes/gitlab/master", descendant)
        private_tree(source)
        verified = self.fixture.run("verify", copied=True)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertEqual(json.loads(verified.stdout)["candidate_commit"], descendant)

        run_git(source, "update-index", "--add", "--cacheinfo", "160000", self.fixture.candidate, "nested")
        run_git(source, "commit", "-q", "-m", "gitlink descendant")
        (source / "nested").mkdir(mode=0o700)
        gitlink_descendant = run_git(source, "rev-parse", "HEAD")
        run_git(source, "update-ref", "refs/remotes/gitlab/master", gitlink_descendant)
        private_tree(source)
        rejected = self.fixture.run("verify", copied=True)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("may not contain gitlinks", rejected.stderr)

    def test_inherited_publisher_lock_fd_is_bound_to_the_fixed_inode(self) -> None:
        self.fixture.provision()
        lock = self.fixture.root / "publisher-state/deploy/publisher.kernel.lock"
        lock_fd = os.open(lock, os.O_RDWR)
        wrong_fd = os.open(self.fixture.root / "provisioning/current.json", os.O_RDONLY)
        try:
            accepted = self.fixture.run("verify", copied=True, inherited_fd=lock_fd)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            rejected = self.fixture.run("verify", copied=True, inherited_fd=wrong_fd)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("does not identify the fixed lock", rejected.stderr)
        finally:
            os.close(wrong_fd)
            os.close(lock_fd)

    def test_manifest_duplicate_unknown_and_input_digest_drift_are_rejected(self) -> None:
        raw = self.fixture.manifest.read_text()
        self.fixture.manifest.write_text(raw.replace('"schema":', '"schema": "duplicate",\n  "schema":', 1))
        os.chmod(self.fixture.manifest, 0o600)
        duplicate = self.fixture.run("plan")
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("duplicate key schema", duplicate.stderr)

        payload = self.fixture.payload()
        payload["unexpected"] = True
        self.fixture.write_manifest(payload)
        unknown = self.fixture.run("plan")
        self.assertNotEqual(unknown.returncode, 0)
        self.assertIn("keys are not exact", unknown.stderr)

        payload = self.fixture.payload()
        payload["inputs"]["machine_env"]["sha256"] = "0" * 64  # type: ignore[index]
        self.fixture.write_manifest(payload)
        drift = self.fixture.run("plan")
        self.assertNotEqual(drift.returncode, 0)
        self.assertIn("machine_env input digest mismatch", drift.stderr)

    def test_seed_authority_dirty_tree_and_local_override_are_rejected(self) -> None:
        other = run_git(
            self.fixture.seed,
            "commit-tree",
            f"{self.fixture.candidate}^{{tree}}",
            "-m",
            "other",
        )
        run_git(self.fixture.seed, "update-ref", "refs/remotes/gitlab/master", other)
        remote = self.fixture.run("plan")
        self.assertNotEqual(remote.returncode, 0)
        self.assertIn("must equal candidate", remote.stderr)
        run_git(self.fixture.seed, "update-ref", "refs/remotes/gitlab/master", self.fixture.candidate)

        (self.fixture.seed / "dirty").write_text("dirty\n")
        dirty = self.fixture.run("plan")
        self.assertNotEqual(dirty.returncode, 0)
        self.assertIn("completely clean", dirty.stderr)
        (self.fixture.seed / "dirty").unlink()

        override = self.fixture.seed / ".git/info/attributes"
        override.write_text("* filter=bad\n")
        os.chmod(override, 0o600)
        rejected = self.fixture.run("plan")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("forbidden Git override", rejected.stderr)
        override.unlink()

        run_git(self.fixture.seed, "config", "filter.bad.clean", "/bin/false")
        injected = self.fixture.run("plan")
        self.assertNotEqual(injected.returncode, 0)
        self.assertIn("local Git config is not exact", injected.stderr)

    def test_unsafe_parent_existing_root_and_symlink_target_are_rejected(self) -> None:
        unsafe_parent = self.base / "unsafe-parent"
        unsafe_parent.mkdir(mode=0o700)
        os.chmod(unsafe_parent, 0o777)
        payload = self.fixture.payload()
        payload["deploy_root"] = str(unsafe_parent / "root")
        self.fixture.write_manifest(payload)
        unsafe = self.fixture.run("plan", deploy_root=unsafe_parent / "root")
        self.assertNotEqual(unsafe.returncode, 0)
        self.assertIn("must not be group/other writable", unsafe.stderr)

        self.fixture.write_manifest()
        self.fixture.root.mkdir(mode=0o700)
        existing = self.fixture.run("plan")
        self.assertNotEqual(existing.returncode, 0)
        self.assertIn("already exists", existing.stderr)
        self.fixture.root.rmdir()

        link = self.base / "root-link"
        link.symlink_to(self.base / "missing")
        payload = self.fixture.payload()
        payload["deploy_root"] = str(link)
        self.fixture.write_manifest(payload)
        linked = self.fixture.run("plan", deploy_root=link)
        self.assertNotEqual(linked.returncode, 0)
        self.assertIn("must not traverse a symlink", linked.stderr)

        overlapping_root = self.fixture.seed / "nested-root"
        payload = self.fixture.payload()
        payload["deploy_root"] = str(overlapping_root)
        self.fixture.write_manifest(payload)
        overlap = self.fixture.run("plan", deploy_root=overlapping_root)
        self.assertNotEqual(overlap.returncode, 0)
        self.assertIn("must not overlap", overlap.stderr)

        wide_ancestor = self.base / "wide-ancestor"
        safe_child = wide_ancestor / "safe-child"
        safe_child.mkdir(parents=True, mode=0o700)
        os.chmod(wide_ancestor, 0o777)
        os.chmod(safe_child, 0o700)
        nested_root = safe_child / "trusted-root"
        payload = self.fixture.payload()
        payload["deploy_root"] = str(nested_root)
        self.fixture.write_manifest(payload)
        ancestor = self.fixture.run("plan", deploy_root=nested_root)
        self.assertNotEqual(ancestor.returncode, 0)
        self.assertIn("ancestor is replaceable", ancestor.stderr)

    def test_toolchain_symlink_hardlink_and_capacity_are_rejected(self) -> None:
        link = self.fixture.toolchain / "lib/link"
        link.symlink_to("runtime.dat")
        linked = self.fixture.run("plan")
        self.assertNotEqual(linked.returncode, 0)
        self.assertIn("tree contains a symlink", linked.stderr)
        link.unlink()

        hard = self.fixture.toolchain / "lib/hard"
        os.link(self.fixture.toolchain / "lib/runtime.dat", hard)
        hardlinked = self.fixture.run("plan")
        self.assertNotEqual(hardlinked.returncode, 0)
        self.assertIn("special or multiply linked", hardlinked.stderr)
        hard.unlink()

        payload = self.fixture.payload()
        payload["limits"]["min_free_bytes_after"] = shutil.disk_usage(self.base).free + 1  # type: ignore[index]
        self.fixture.write_manifest(payload)
        capacity = self.fixture.run("plan")
        self.assertNotEqual(capacity.returncode, 0)
        self.assertIn("insufficient capacity", capacity.stderr)

    def test_tree_file_hashing_uses_the_explicit_tree_byte_bound(self) -> None:
        tree = self.base / "large-tree-contract"
        tree.mkdir(mode=0o700)
        item = tree / "model.onnx"
        item.write_bytes(b"fixture")
        os.chmod(item, 0o600)
        admitted = MODULE.MAX_FILE_BYTES + 512 * 1024 * 1024
        with mock.patch.object(
            MODULE, "sha256_file", return_value=("0" * 64, len(b"fixture"))
        ) as digest:
            MODULE.tree_manifest(tree, max_files=1, max_bytes=admitted)
        digest.assert_called_once_with(str(item), maximum=admitted)

    def test_existing_deterministic_stage_is_never_cleaned_or_reused(self) -> None:
        plan = self.fixture.plan()
        stage = self.base / f".trusted-root.provision-stage.{str(plan['plan_digest'])[:24]}"
        stage.mkdir(mode=0o700)
        marker = stage / "owner-marker"
        marker.write_text("retain\n")
        os.chmod(marker, 0o600)
        rejected = self.fixture.run("provision", confirm=str(plan["confirmation"]))
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("stage already exists", rejected.stderr)
        self.assertEqual(marker.read_text(), "retain\n")
        self.assertFalse(self.fixture.root.exists())

    def test_atomic_activation_never_replaces_an_appearing_root(self) -> None:
        source = self.base / "activation-stage"
        destination = self.base / "appearing-root"
        source.mkdir(mode=0o700)
        destination.mkdir(mode=0o700)
        marker = destination / "owner-marker"
        marker.write_text("retain\n")
        os.chmod(marker, 0o600)
        with self.assertRaisesRegex(
            MODULE.ProvisionError, "deployment root appeared during atomic activation"
        ):
            MODULE.rename_noreplace(str(source), str(destination))
        self.assertTrue(source.is_dir())
        self.assertEqual(marker.read_text(), "retain\n")

    def test_verify_rejects_receipt_input_source_toolchain_and_lock_tampering(self) -> None:
        cases = ("receipt", "input", "source", "toolchain", "lock")
        for case in cases:
            with self.subTest(case=case):
                case_base = self.base / f"case-{case}"
                case_base.mkdir(mode=0o700)
                fixture = Fixture(case_base)
                fixture.provision()
                if case == "receipt":
                    path = fixture.root / "provisioning/current.json"
                    path.write_bytes(path.read_bytes().replace(b"bootstrap_seed", b"bootstrap_seed_tampered", 1))
                elif case == "input":
                    path = fixture.root / "config/agent-bridge/machine.env"
                    path.write_text("export AB_SUBSTRATE_PROJECTION=tampered\n")
                elif case == "source":
                    path = fixture.root / "source/agent-bridge/README.md"
                    path.write_text("tampered\n")
                elif case == "toolchain":
                    path = fixture.root / "toolchain/lib/runtime.dat"
                    path.write_text("tampered\n")
                else:
                    path = fixture.root / "publisher-state/deploy/publisher.kernel.lock"
                    path.unlink()
                    path.write_bytes(b"")
                os.chmod(path, 0o600)
                rejected = fixture.run("verify", copied=True)
                self.assertNotEqual(rejected.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
