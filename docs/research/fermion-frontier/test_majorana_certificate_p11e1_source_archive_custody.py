#!/usr/bin/env python3
"""Synthetic, offline tests for the P11-E1 acquisition runner and receipts."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
PATH = BASE / "majorana_certificate_p11e1_source_archive_acquisition_runner.py"
VALIDATOR_PATH = BASE / "majorana_certificate_p11e1_source_archive_custody_validator.py"
SPEC = importlib.util.spec_from_file_location("p11e1_runner", PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


class P11E1RunnerTests(unittest.TestCase):
    def test_frozen_identity_snapshot_and_root(self) -> None:
        self.assertEqual(RUNNER.SNAPSHOT, "20260719T064131Z")
        self.assertEqual(len(RUNNER.IDENTITIES), 4)
        self.assertEqual(str(RUNNER.ROOT), "/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e1-source-custody")

    def test_control_parser_and_sha256_rows(self) -> None:
        payload = b"abc"
        sha = hashlib.sha256(payload).hexdigest()
        raw = f"Source: sample\nVersion: 1\nChecksums-Sha256:\n {sha} 3 sample.tar.xz\n".encode()
        fields = RUNNER.parse_control(raw)
        self.assertEqual(fields["Source"], "sample")
        self.assertEqual(RUNNER.checksum_rows(fields["Checksums-Sha256"]), {"sample.tar.xz": (3, sha)})

    def test_duplicate_and_unsafe_checksum_names_fail(self) -> None:
        sha = "0" * 64
        for value in (f"{sha} 1 ../x", f"{sha} 1 x\n{sha} 1 x"):
            with self.subTest(value=value), self.assertRaises(RUNNER.AcquisitionError):
                RUNNER.checksum_rows(value)

    def test_environment_is_explicit_and_has_no_proxy_or_credentials(self) -> None:
        env = RUNNER.safe_environment()
        self.assertEqual(set(env), {"PATH", "HOME", "LANG", "LC_ALL", "APT_CONFIG"})
        self.assertTrue(all("proxy" not in key.lower() for key in env))

    def test_apt_templates_are_download_only_and_authenticated(self) -> None:
        self.assertEqual(RUNNER.SOURCES.count("Types: deb-src\n"), 2)
        self.assertEqual(RUNNER.SOURCES.count(f"Snapshot: {RUNNER.SNAPSHOT}\n"), 2)
        self.assertNotIn("Trusted: yes", RUNNER.SOURCES)
        self.assertIn('Acquire::AllowInsecureRepositories "false";', RUNNER.APT_CONF_LINES)

    def test_subprocess_is_direct_argv_without_shell(self) -> None:
        tree = ast.parse(PATH.read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                 and node.func.value.id == "subprocess"]
        self.assertEqual(len(calls), 1)
        keywords = {kw.arg: kw.value for kw in calls[0].keywords}
        self.assertNotIn("shell", keywords)
        self.assertIn("env", keywords)

    def test_published_partial_result_is_canonical_and_does_not_claim_complete_custody(self) -> None:
        manifest_raw = (BASE / "majorana_certificate_p11e1_source_archive_custody_manifest.json").read_bytes()
        report_raw = (BASE / "majorana_certificate_p11e1_source_archive_custody_report.json").read_bytes()
        manifest = json.loads(manifest_raw)
        report = json.loads(report_raw)
        self.assertEqual(manifest_raw, RUNNER.canonical_bytes(manifest))
        self.assertEqual(report_raw, RUNNER.canonical_bytes(report))
        self.assertFalse(report["complete_set_custody_established"])
        self.assertFalse(report["source_archive_custody_established"])
        self.assertEqual(len(manifest["accepted_files"]), 6)

    def test_independent_validator_has_no_acquisition_subprocess(self) -> None:
        tree = ast.parse(VALIDATOR_PATH.read_text(encoding="utf-8"))
        self.assertFalse(any(isinstance(node, ast.Import) and any(alias.name == "subprocess" for alias in node.names)
                             for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
