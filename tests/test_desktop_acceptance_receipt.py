"""Deterministic tests for the isolated desktop acceptance receipt."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "desktop_accept" / "desktop_acceptance_receipt.py"
SPEC = importlib.util.spec_from_file_location("desktop_acceptance_receipt", SCRIPT)
assert SPEC and SPEC.loader
RECEIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECEIPT)


def payloads() -> dict[str, dict]:
    return {
        "isolated_invoke": {
            "schema": "desktop_invoke/v0",
            "allowed": True,
            "rc": 0,
            "found": {"app": "toy_button", "app_pid": 222, "isolated": True},
        },
        "postcondition_verify": {
            "schema": "desktop_verify/v0",
            "verdict": "verified",
            "recover": "proceed",
            "observed": {"count": 1},
        },
        "dry_run_invoke": {
            "schema": "desktop_invoke/v0",
            "allowed": True,
            "dry_run": True,
        },
        "host_invoke": {
            "schema": "desktop_invoke/v0",
            "allowed": False,
            "reason": "host posture denied",
        },
        "semantic_task": {
            "schema": "agent_bridge.desktop_semantic_task.v0",
            "status": "verified",
            "verdict": "verified",
            "recover": "proceed",
            "safety": {
                "mode": "isolated",
                "host_mutation_exposed": False,
                "coordinate_input_exposed": False,
            },
            "verification": {"verdict": "verified", "recover": "proceed"},
        },
    }


class DesktopAcceptanceReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.binary = self.root / "agent-bridge"
        self.binary.write_bytes(b"test agent-bridge binary\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self, **overrides):
        values = payloads()
        values.update(overrides.pop("payload_overrides", {}))
        arguments = {
            "source_commit": "b" * 40,
            "binary_path": self.binary,
            "binary_version": f"agent-bridge 0.14.0 ({'b' * 12})",
            "backend": "headless",
            "output_names": ["HEADLESS-1"],
            "display": "wayland-accept",
            "sway_pid": 1234,
            "snapshot_target_present": True,
            **values,
            "activation_counts": {
                "isolated": 1,
                "dry_run": 1,
                "host_denied": 1,
                "transaction": 2,
            },
            "hostname": "aio2",
            "architecture": "x86_64",
        }
        arguments.update(overrides)
        return RECEIPT.build_receipt(**arguments)

    def test_valid_receipt_covers_provenance_channels_and_all_checks(self) -> None:
        receipt = self.build()

        self.assertEqual(receipt["schema"], RECEIPT.SCHEMA)
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["environment"]["outputs"], ["HEADLESS-1"])
        self.assertEqual(RECEIPT.validate_receipt(receipt), [])
        self.assertEqual(
            {item["id"] for item in receipt["checks"]}, RECEIPT.REQUIRED_CHECKS
        )
        self.assertTrue(all(item["reason"] for item in receipt["channels"]["skipped"]))

    def test_missing_provenance_is_rejected(self) -> None:
        receipt = self.build()
        receipt["source"]["commit"] = ""
        receipt["binary"]["sha256"] = "not-a-digest"

        errors = RECEIPT.validate_receipt(receipt)

        self.assertIn("source_commit_invalid", errors)
        self.assertIn("binary_sha256_invalid", errors)

    def test_binary_build_must_match_the_harness_source_commit(self) -> None:
        receipt = self.build(
            binary_version=f"agent-bridge 0.14.0 ({'c' * 12})"
        )

        self.assertIn(
            "binary_source_commit_mismatch", RECEIPT.validate_receipt(receipt)
        )

    def test_dirty_binary_build_is_rejected(self) -> None:
        receipt = self.build(
            binary_version=f"agent-bridge 0.14.0 ({'b' * 12}-dirty)"
        )

        self.assertEqual(receipt["status"], "failed")
        self.assertIn("binary_source_dirty", RECEIPT.validate_receipt(receipt))

    def test_physical_output_is_rejected_by_builder_and_validator(self) -> None:
        receipt = self.build(output_names=["HDMI-A-1"])

        self.assertEqual(receipt["status"], "failed")
        errors = RECEIPT.validate_receipt(receipt)
        self.assertIn("physical_output_present", errors)
        self.assertIn("physical_output_audit_failed", errors)

    def test_nonisolated_action_is_rejected_even_if_checks_are_forged(self) -> None:
        receipt = self.build()
        receipt["phases"]["isolated_invoke"]["payload"]["found"]["isolated"] = False
        for check in receipt["checks"]:
            check["passed"] = True

        self.assertIn("isolated_target_unproven", RECEIPT.validate_receipt(receipt))

    def test_unverified_postcondition_is_rejected(self) -> None:
        receipt = self.build()
        receipt["phases"]["postcondition_verify"]["payload"]["verdict"] = "unmet"

        self.assertIn("postcondition_not_verified", RECEIPT.validate_receipt(receipt))

    def test_incomplete_a_to_d_check_coverage_is_rejected(self) -> None:
        receipt = self.build()
        receipt["checks"] = receipt["checks"][:-1]

        errors = RECEIPT.validate_receipt(receipt)

        self.assertIn("check_coverage_incomplete", errors)
        self.assertIn("required_check_failed", errors)

    def test_semantic_task_payload_is_digest_bound(self) -> None:
        receipt = self.build()
        receipt["phases"]["semantic_task"]["payload"]["recover"] = "retry"

        errors = RECEIPT.validate_receipt(receipt)

        self.assertIn("semantic_task_recover_invalid", errors)
        self.assertIn("semantic_task_payload_digest_mismatch", errors)

    def test_cli_writes_then_validates_a_portable_receipt(self) -> None:
        values = payloads()
        paths = {}
        for name, payload in values.items():
            path = self.root / f"{name}.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            paths[name] = path
        output = self.root / "evidence" / "receipt.json"
        command = [
            sys.executable,
            str(SCRIPT),
            "write",
            "--output",
            str(output),
            "--source-commit",
            "a" * 40,
            "--binary",
            str(self.binary),
            "--binary-version",
            f"agent-bridge 0.14.0 ({'a' * 12})",
            "--backend",
            "headless",
            "--output-names",
            "HEADLESS-1",
            "--display",
            "wayland-accept",
            "--sway-pid",
            "1234",
            "--snapshot-target-present",
            "true",
            "--isolated-invoke",
            str(paths["isolated_invoke"]),
            "--postcondition-verify",
            str(paths["postcondition_verify"]),
            "--dry-run-invoke",
            str(paths["dry_run_invoke"]),
            "--host-invoke",
            str(paths["host_invoke"]),
            "--semantic-task",
            str(paths["semantic_task"]),
            "--isolated-activations",
            "1",
            "--dry-run-activations",
            "1",
            "--host-activations",
            "1",
            "--transaction-activations",
            "2",
        ]

        written = subprocess.run(command, check=False, capture_output=True, text=True)
        validated = subprocess.run(
            [sys.executable, str(SCRIPT), "validate", str(output)],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(written.returncode, 0, written.stderr or written.stdout)
        self.assertEqual(validated.returncode, 0, validated.stderr or validated.stdout)
        self.assertEqual(json.loads(validated.stdout)["status"], "passed")
        self.assertEqual(json.loads(output.read_text())["status"], "passed")


if __name__ == "__main__":
    unittest.main()
