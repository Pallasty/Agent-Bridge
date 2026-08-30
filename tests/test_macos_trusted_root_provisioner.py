from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/provision-macos-trusted-deployment-root.py"
SOURCE = ROOT / "scripts/macos-rename-exclusive.c"
SPEC = importlib.util.spec_from_file_location("macos_trusted_root_provisioner", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(sys.platform == "darwin", "Darwin native admission test")
class DarwinTrustedRootProvisionerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.parent = Path(self.temporary.name).resolve()
        self.parent.chmod(0o700)
        self.helper = self.parent / "macos-rename-exclusive"
        subprocess.run(
            ["/usr/bin/clang", "-Wall", "-Wextra", "-Werror", "-O2", str(SOURCE), "-o", str(self.helper)],
            check=True, capture_output=True, text=True,
        )
        self.helper.chmod(0o700)
        self.root = self.parent / "TrustedRuntime"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_plan_provision_verify_round_trip(self) -> None:
        plan = MODULE.build_plan(self.root, self.helper)
        self.assertTrue(plan["read_only"])
        result = MODULE.provision(self.root, self.helper, plan["confirmation"])
        self.assertEqual(result["verdict"], "PASS")
        self.assertFalse(result["production_state_imported"])
        self.assertFalse(result["launchd_changed"])
        self.assertEqual(MODULE.verify(self.root, self.helper)["tree_sha256"], result["tree_sha256"])

    def test_existing_destination_is_preserved_and_stage_retained(self) -> None:
        plan = MODULE.build_plan(self.root, self.helper)
        self.root.mkdir(mode=0o700)
        marker = self.root / "owner-marker"
        marker.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(MODULE.ProvisionError, "existing destination"):
            MODULE.provision(self.root, self.helper, plan["confirmation"])
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
        self.assertEqual(len(list(self.parent.glob(".TrustedRuntime.stage-*"))), 1)

    def test_destination_appearing_after_plan_is_preserved(self) -> None:
        plan = MODULE.build_plan(self.root, self.helper)
        self.root.mkdir(mode=0o700)
        marker = self.root / "race-winner"
        marker.write_bytes(b"winner")
        with self.assertRaises(MODULE.ProvisionError):
            MODULE.provision(self.root, self.helper, plan["confirmation"])
        self.assertEqual(marker.read_bytes(), b"winner")

    def test_wrong_confirmation_fails_before_staging(self) -> None:
        with self.assertRaisesRegex(MODULE.ProvisionError, "confirmation"):
            MODULE.provision(self.root, self.helper, "0" * 64)
        self.assertFalse(self.root.exists())
        self.assertEqual(list(self.parent.glob(".*.stage-*")), [])

    def test_receipt_detects_tree_and_helper_drift(self) -> None:
        plan = MODULE.build_plan(self.root, self.helper)
        MODULE.provision(self.root, self.helper, plan["confirmation"])
        (self.root / "config/root-manifest.json").write_bytes(b"{}\n")
        with self.assertRaisesRegex(MODULE.ProvisionError, "manifest"):
            MODULE.verify(self.root, self.helper)

    def test_receipt_mode_drift_fails_closed(self) -> None:
        plan = MODULE.build_plan(self.root, self.helper)
        MODULE.provision(self.root, self.helper, plan["confirmation"])
        receipt = self.root / MODULE.RECEIPT_NAME
        receipt.chmod(0o644)
        with self.assertRaisesRegex(MODULE.ProvisionError, "receipt"):
            MODULE.verify(self.root, self.helper)

    def test_mutable_namespace_content_does_not_drift_custody_spine(self) -> None:
        plan = MODULE.build_plan(self.root, self.helper)
        MODULE.provision(self.root, self.helper, plan["confirmation"])
        (self.root / "build/candidate").write_bytes(b"mutable build cache")
        (self.root / "publisher/pending.json").write_bytes(b"{}\n")
        result = MODULE.verify(self.root, self.helper)
        self.assertEqual(result["verdict"], "PASS")

    def test_extra_top_level_namespace_fails_closed(self) -> None:
        plan = MODULE.build_plan(self.root, self.helper)
        MODULE.provision(self.root, self.helper, plan["confirmation"])
        (self.root / "unadmitted").mkdir(mode=0o700)
        with self.assertRaisesRegex(MODULE.ProvisionError, "top-level"):
            MODULE.verify(self.root, self.helper)

    def test_native_helper_rejects_non_darwin_or_bad_shape_at_source_level(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("renameatx_np", source)
        self.assertIn("RENAME_EXCL", source)
        self.assertNotIn("rename(", source)


if __name__ == "__main__":
    unittest.main()
