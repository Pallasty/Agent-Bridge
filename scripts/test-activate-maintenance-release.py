#!/usr/bin/env python3
"""Real file tests; fake admission only exists inside an isolated fixture."""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("activation", Path(__file__).with_name("activate-maintenance-release.py"))
activation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activation)


class MaintenanceActivationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(prefix="ab-maintenance-adoption-")
        self.addCleanup(self.fixture.cleanup)
        self.base = Path(self.fixture.name)
        self.home = self.base / "home"
        self.root = self.base / "private"
        self.mkdir(self.root)
        self.mkdir(self.home)
        self.home_patch = mock.patch.object(activation.Path, "home", return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)
        self.wrapper = self.home / ".local/bin/agent-bridge"
        self.write(self.wrapper, b"#!/bin/sh\nexec original-wrapper\n", 0o755)
        self.binary = self.root / "maintenance/bin/agent-bridge.real"
        self.write(self.binary, b"\x7fELF fixture agent_bridge.runtime_profile.maintenance.v1", 0o755)
        for label, path, mode in activation.assets(self.root):
            self.write(path, (label + ":" + path.name).encode(), mode)
        self.receipts = self.root / "publisher-state/maintenance/receipts"
        self.mkdir(self.receipts)
        self.write(self.root / "publisher-state/deploy/publisher.kernel.lock", b"", 0o600)
        for alias, target in activation.fixed_aliases(self.root, self.wrapper):
            if target.name == "scripts":
                self.mkdir(alias)
                self.write(alias / "retained-script.py", b"old runtime", 0o755)
            else:
                self.write(alias, b"old " + alias.name.encode(), 0o755)
        self.model = self.home / ".local/share/ab-tts/kokoro/model.bin"
        self.write(self.model, b"keep model untouched", 0o644)
        self.receipt = self.receipts / "fixture.fresh-mcp-admitted.meta"
        self.make_receipt()
        self.args = argparse.Namespace(action="plan", deploy_root=str(self.root), legacy_wrapper=str(self.wrapper), expected_binary_sha256=activation.digest(self.wrapper.with_name("agent-bridge.real")), expected_wrapper_sha256=activation.digest(self.wrapper), admission_receipt=str(self.receipt), manifest=None)
        self.original = {str(a): activation.snapshot(a) for a, _ in activation.fixed_aliases(self.root, self.wrapper)}

    def mkdir(self, path):
        path.mkdir(parents=True, exist_ok=True)
        while path == self.root or self.base in path.parents:
            path.chmod(0o700)
            if path == self.base:
                break
            path = path.parent

    def write(self, path, content, mode):
        self.mkdir(path.parent)
        path.write_bytes(content)
        path.chmod(mode)

    def make_receipt(self):
        fields = dict.fromkeys(activation.RECEIPT_KEYS, "fixture")
        release = self.root / "maintenance"
        fields.update(schema="agent_bridge.publisher_fresh_mcp_admission.v1", candidate_commit="a" * 40,
                      real_path=str(self.binary), shared_targets="|".join(map(str, [self.binary, release / "share/ab-tts/audio_embody.py", release / "lib/agent-bridge/scripts", self.root / "bin/agent-bridge"])),
                      installed_binary_sha256=activation.digest(self.binary), installed_binary_inode=str(self.binary.stat().st_ino), installed_binary_mode="755", installed_assets_sha256=activation.assets_digest(self.root),
                      fresh_mcp="verified", probe_schema="agent_bridge.publisher_fresh_mcp_probe.v1", probe_server_name="agent-bridge", probe_protocol_version="2024-11-05", probe_build_git_sha="a" * 12,
                      probe_toolset="codex-essential", probe_tool_count="5", probe_capabilities_tool_present="true", probe_method="independent_stdio_private_exact_binary_copy", probe_copied_binary_sha256=activation.digest(self.binary))
        body = "".join(f"{key}={fields[key]}\n" for key in activation.RECEIPT_KEYS[:-1])
        bound = hashlib.sha256(b"domain=agent_bridge.publisher_fresh_mcp_admission_receipt.v1\n" + body.encode()).hexdigest()
        self.write(self.receipt, (body + f"receipt_binding_sha256={bound}\n").encode(), 0o600)

    def assert_original(self):
        for alias, before in self.original.items():
            self.assertEqual(activation.snapshot(Path(alias)), before)
        self.assertEqual(activation.digest(self.wrapper), self.args.expected_wrapper_sha256)
        self.assertEqual(self.model.read_bytes(), b"keep model untouched")

    def test_default_plan_is_read_only_and_activation_rolls_back_exactly(self):
        before = activation.snapshot(self.base)
        result = activation.run(self.args)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(activation.snapshot(self.base), before)
        self.args.action = "activate"
        result = activation.run(self.args)
        self.assertEqual(result["status"], "activated")
        self.assertFalse(result["existing_mcp_sessions_refreshed"])
        payload = Path(json.loads(Path(result["manifest"]).read_text())["release_root"])
        for alias, target in activation.fixed_aliases(self.root, self.wrapper, payload):
            self.assertTrue(alias.is_symlink())
            self.assertEqual(os.readlink(alias), str(target))
        self.assertEqual(self.model.read_bytes(), b"keep model untouched")
        self.args.action = "rollback"
        self.args.manifest = result["manifest"]
        self.assertEqual(activation.run(self.args)["status"], "rolled_back")
        self.assert_original()

    def test_later_publication_does_not_change_active_inputs_or_prevent_rollback(self):
        self.args.action = "activate"
        result = activation.run(self.args)
        manifest = json.loads(Path(result["manifest"]).read_text())
        payload = Path(manifest["release_root"])
        active_binary = self.wrapper.with_name("agent-bridge.real")
        active_hash = activation.digest(active_binary)
        self.binary.write_bytes(b"later publisher binary")
        next_asset = self.root / "maintenance/lib/agent-bridge/scripts/app_control.py"
        next_asset.write_bytes(b"later publisher asset")
        self.assertEqual(activation.digest(active_binary), active_hash)
        self.assertNotEqual(activation.digest(next_asset), activation.digest(payload / "lib/agent-bridge/scripts/app_control.py"))
        activation.validate_frozen(self.root, payload)
        self.args.action = "rollback"
        self.args.manifest = result["manifest"]
        activation.run(self.args)
        self.assert_original()

    def test_second_adoption_can_rollback_to_previous_frozen_aliases(self):
        self.args.action = "activate"
        first = activation.run(self.args)
        old_manifest = json.loads(Path(first["manifest"]).read_text())
        old_payload = Path(old_manifest["release_root"])
        previous_hash = activation.digest(self.wrapper.with_name("agent-bridge.real"))
        self.binary.write_bytes(b"\x7fELF second build agent_bridge.runtime_profile.maintenance.v1")
        next_asset = self.root / "maintenance/lib/agent-bridge/scripts/app_control.py"
        next_asset.write_bytes(b"second runtime asset")
        self.make_receipt()
        self.assertEqual(activation.digest(self.wrapper.with_name("agent-bridge.real")), previous_hash)
        self.args.expected_binary_sha256 = previous_hash
        second = activation.run(self.args)
        new_manifest = json.loads(Path(second["manifest"]).read_text())
        self.assertNotEqual(old_manifest["release_root"], new_manifest["release_root"])
        self.assertNotEqual(activation.digest(self.wrapper.with_name("agent-bridge.real")), previous_hash)
        # Mutable staging may now contain a third release; rollback uses both
        # frozen receipts and never revalidates the obsolete staging inode.
        self.binary.write_bytes(b"unrelated third publication")
        next_asset.write_bytes(b"third staging content")
        (Path(new_manifest["release_root"]) / "bin/agent-bridge.real").write_bytes(b"damaged outgoing second version")
        self.args.action = "rollback"
        self.args.manifest = second["manifest"]
        activation.run(self.args)
        for alias, target in activation.fixed_aliases(self.root, self.wrapper, old_payload):
            self.assertTrue(alias.is_symlink())
            self.assertEqual(os.readlink(alias), str(target))
        self.assertEqual(activation.digest(self.wrapper.with_name("agent-bridge.real")), previous_hash)

    def test_arbitrary_existing_alias_is_not_an_adoption_source(self):
        alias = self.wrapper.with_name("agent-bridge.real")
        alias.unlink()
        alias.symlink_to(self.wrapper)
        with self.assertRaisesRegex(activation.ActivationError, "fixed maintenance release"):
            activation.run(self.args)

    def test_new_declared_asset_uses_its_own_inventory_and_rollback_removes_new_alias(self):
        self.args.action = "activate"
        first = activation.run(self.args)
        old_manifest = json.loads(Path(first["manifest"]).read_text())
        old_payload = Path(old_manifest["release_root"])
        previous_hash = activation.digest(self.wrapper.with_name("agent-bridge.real"))
        declared = activation.publisher_assets()
        declared["AUDIO_ADAPTER_COMPANIONS"] = declared["AUDIO_ADAPTER_COMPANIONS"] + ["new-helper.py"]
        declared["RUNTIME_ASSETS"] = declared["RUNTIME_ASSETS"] + ["new-runtime.py"]
        self.write(self.root / "maintenance/share/ab-tts/new-helper.py", b"new companion", 0o755)
        self.write(self.root / "maintenance/lib/agent-bridge/scripts/new-runtime.py", b"new runtime", 0o755)
        new_alias = self.home / ".local/share/ab-tts/new-helper.py"
        with mock.patch.object(activation, "publisher_assets", return_value=declared):
            self.make_receipt()
            activation.validate_frozen(self.root, old_payload)
            self.assertFalse(new_alias.exists())
            self.args.expected_binary_sha256 = previous_hash
            second = activation.run(self.args)
            self.assertTrue(new_alias.is_symlink())
            self.assertEqual(new_alias.read_bytes(), b"new companion")
            # Same binary, new assets: the release identity must still differ.
            new_payload = Path(json.loads(Path(second["manifest"]).read_text())["release_root"])
            self.assertNotEqual(old_payload, new_payload)
            self.binary.write_bytes(b"third staging version")
            self.args.action = "rollback"
            self.args.manifest = second["manifest"]
            activation.run(self.args)
            self.assertFalse(os.path.lexists(new_alias))
            activation.validate_frozen(self.root, old_payload)
            self.assertEqual(os.readlink(self.wrapper.with_name("agent-bridge.real")), str(old_payload / "bin/agent-bridge.real"))
        self.assertEqual(self.model.read_bytes(), b"keep model untouched")

    def test_prepared_manifest_can_restore_an_interrupted_partial_adoption(self):
        self.args.action = "activate"
        result = activation.run(self.args)
        manifest = Path(result["manifest"])
        data = json.loads(manifest.read_text())
        # Model an interruption with only the first alias switched. The durable
        # prepared manifest already lists all exact preconditions and backups.
        activation.restore(data["entries"][1:])
        data["status"] = "prepared"
        activation.save_manifest(manifest, data)
        self.args.action = "rollback"
        self.args.manifest = str(manifest)
        activation.run(self.args)
        self.assert_original()

    def test_shared_publisher_lock_prevents_alias_changes(self):
        lock = self.root / "publisher-state/deploy/publisher.kernel.lock"
        with lock.open("r+b") as held:
            activation.fcntl.flock(held.fileno(), activation.fcntl.LOCK_EX | activation.fcntl.LOCK_NB)
            self.args.action = "activate"
            with self.assertRaises(BlockingIOError):
                activation.run(self.args)
        self.assert_original()
        self.assertEqual(list(self.receipts.glob("*.maintenance-activation.json")), [])

    def test_damaged_outgoing_payload_does_not_block_restore_of_healthy_backups(self):
        self.args.action = "activate"
        result = activation.run(self.args)
        data = json.loads(Path(result["manifest"]).read_text())
        payload = Path(data["release_root"])
        (payload / "bin/agent-bridge.real").write_bytes(b"damaged new binary")
        (payload / "lib/agent-bridge/scripts/app_control.py").write_bytes(b"damaged new script")
        (payload / "asset-list.json").unlink()
        self.args.action = "rollback"
        self.args.manifest = result["manifest"]
        self.assertEqual(activation.run(self.args)["status"], "rolled_back")
        self.assert_original()

    def test_hard_interruption_leaves_only_staging_and_same_admission_can_retry(self):
        self.args.action = "activate"
        code = r"""
import argparse, importlib.util, json, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("activation", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
Path.home = classmethod(lambda cls: Path(sys.argv[2]))
os.umask(0o077)
def interrupt_copy(src, dst, length):
    dst.write(src.read(8))
    dst.flush()
    os._exit(73)
m.shutil.copyfileobj = interrupt_copy
m.run(argparse.Namespace(**json.loads(sys.argv[3])))
"""
        result = subprocess.run([sys.executable, "-B", "-c", code, str(Path(activation.__file__).resolve()), str(self.home), json.dumps(vars(self.args))], timeout=10, capture_output=True, text=True)
        self.assertEqual(result.returncode, 73, result.stderr)
        releases = self.root / "maintenance/releases"
        self.assertEqual(len(list(releases.glob(".staging-*"))), 1)
        self.assertEqual([path for path in releases.iterdir() if not path.name.startswith(".")], [])
        self.assertEqual(list(self.receipts.glob("*.maintenance-activation.json")), [])
        self.assert_original()
        adopted = activation.run(self.args)
        self.assertEqual(adopted["status"], "activated")
        self.assertEqual(list(releases.glob(".staging-*")), [])
        self.args.action = "rollback"
        self.args.manifest = adopted["manifest"]
        activation.run(self.args)
        self.assert_original()

    def test_changed_baseline_or_wrapper_is_rejected_before_moving_files(self):
        for field in ["expected_binary_sha256", "expected_wrapper_sha256"]:
            with self.subTest(field=field):
                args = argparse.Namespace(**vars(self.args))
                setattr(args, field, "0" * 64)
                args.action = "activate"
                with self.assertRaisesRegex(activation.ActivationError, "changed"):
                    activation.run(args)
                self.assert_original()

    def test_symlink_escape_bad_mode_and_unadmitted_assets_are_rejected(self):
        self.binary.chmod(0o777)
        with self.assertRaisesRegex(activation.ActivationError, "owner/type/mode"):
            activation.run(self.args)
        self.binary.chmod(0o755)
        target = self.root / "maintenance/share/ab-tts/audio_embody.py"
        content = target.read_bytes()
        target.write_bytes(b"changed after admission")
        with self.assertRaisesRegex(activation.ActivationError, "installed_assets_sha256"):
            activation.run(self.args)
        target.write_bytes(content)
        target.unlink()
        target.symlink_to(self.wrapper)
        with self.assertRaisesRegex(activation.ActivationError, "symlink"):
            activation.run(self.args)
        self.assert_original()

    def test_receipt_corruption_and_foreign_legacy_path_are_rejected(self):
        self.receipt.write_bytes(self.receipt.read_bytes().replace(b"fresh_mcp=verified", b"fresh_mcp=forgedxx"))
        with self.assertRaisesRegex(activation.ActivationError, "digest mismatch"):
            activation.run(self.args)
        self.make_receipt()
        self.args.legacy_wrapper = str(self.base / "elsewhere/agent-bridge")
        with self.assertRaisesRegex(activation.ActivationError, "HOME"):
            activation.run(self.args)

    def test_partial_alias_failure_restores_every_completed_move(self):
        self.args.action = "activate"
        original_symlink = os.symlink
        count = 0
        def fail_second(target, alias):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("injected second alias failure")
            original_symlink(target, alias)
        with mock.patch.object(activation.os, "symlink", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "injected"):
                activation.run(self.args)
        self.assert_original()
        manifests = list(self.receipts.glob("*.maintenance-activation.json"))
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text())["status"], "automatically_restored")

    def test_rollback_refuses_user_alias_changes_and_modified_backups(self):
        self.args.action = "activate"
        result = activation.run(self.args)
        self.args.action = "rollback"
        self.args.manifest = result["manifest"]
        payload = Path(json.loads(Path(result["manifest"]).read_text())["release_root"])
        alias, target = activation.fixed_aliases(self.root, self.wrapper, payload)[0]
        alias.unlink()
        alias.write_bytes(b"user later binary")
        with self.assertRaisesRegex(activation.ActivationError, "alias was changed"):
            activation.run(self.args)
        self.assertEqual(alias.read_bytes(), b"user later binary")
        alias.unlink()
        alias.symlink_to(target)
        manifest = json.loads(Path(result["manifest"]).read_text())
        Path(manifest["entries"][0]["backup"]).write_bytes(b"altered old binary")
        with self.assertRaisesRegex(activation.ActivationError, "backup content changed"):
            activation.run(self.args)
        self.assertTrue(alias.is_symlink())


if __name__ == "__main__":
    unittest.main()
