from __future__ import annotations

import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/story_render_artifact_package.py"
WORKER_TEST = ROOT / "tests/test_story_render_one_shot_worker.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_bytes() -> bytes:
    worker_test = load(WORKER_TEST, "s638_worker_fixture")
    return worker_test.encoded(worker_test.request())


class StoryRenderArtifactPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load(MODULE, "s638_package")
        self.temp = tempfile.TemporaryDirectory(dir="/Data/CascadeProjects")
        self.parent = Path(self.temp.name)
        os.chmod(self.parent, 0o700)
        self.package = self.parent / "package"

    def tearDown(self) -> None:
        os.chmod(self.package, 0o700) if self.package.exists() else None
        for path in self.package.rglob("*") if self.package.exists() else ():
            try:
                os.chmod(path, 0o700 if path.is_dir() else 0o600)
            except FileNotFoundError:
                pass
        self.temp.cleanup()

    def test_build_is_manifest_bound_private_and_offline(self) -> None:
        manifest = self.module.build_package(self.package)
        self.assertEqual(manifest, self.module.verify_package(self.package))
        self.assertEqual(stat.S_IMODE(self.package.stat().st_mode), 0o500)
        self.assertEqual(manifest["python"]["inference_dependency_closure"], "blocked_missing_offline_wheelhouse")
        self.assertTrue(all(value is False for value in manifest["authority"].values()))
        self.assertFalse(any(manifest["python"]["inference_modules"].values()))

    def test_tamper_symlink_extra_and_writable_parent_fail_closed(self) -> None:
        self.module.build_package(self.package)
        target = self.package / "scripts/story_render_worker_protocol.py"
        os.chmod(self.package, 0o700); os.chmod(target.parent, 0o700); os.chmod(target, 0o600)
        target.write_bytes(b"tampered")
        with self.assertRaises(self.module.PackageRejected):
            self.module.verify_package(self.package)

        other = self.parent / "other"; other.write_text("x")
        target.unlink(); target.symlink_to(other)
        with self.assertRaises(self.module.PackageRejected):
            self.module.verify_package(self.package)

    def test_descriptor_launch_survives_path_replacement_and_stays_custody_rejected(self) -> None:
        self.module.build_package(self.package)
        result = self.module.run_fail_closed_worker(self.package, request_bytes())
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        response = json.loads(result.stdout)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["code"], "custody_rejected")
        self.assertNotIn("authorization_id", response)

    def test_destination_must_be_new_and_private_parent_is_required(self) -> None:
        self.package.mkdir()
        with self.assertRaises(self.module.PackageRejected):
            self.module.build_package(self.package)
        self.package.rmdir(); os.chmod(self.parent, 0o777)
        with self.assertRaises(self.module.PackageRejected):
            self.module.build_package(self.package)


if __name__ == "__main__":
    unittest.main()
