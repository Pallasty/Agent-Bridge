import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "macos_accept"))

from macos_ax_acceptance_receipt import (
    _payload_sha256,
    _verify_evidence_admissible,
    build_receipt,
    validate_receipt,
)


def _probe():
    return {
        "schema": "macos_ax_probe/v0",
        "read_only": True,
        "status": "ready",
        "permission": {
            "ax_trusted": True,
            "method": "AXIsProcessTrusted",
            "prompted": False,
        },
        "frontmost_app": {
            "name": "Example",
            "pid": 42,
            "bundle_id": "com.example.app",
            "role": "AXApplication",
        },
        "windows": [
            {
                "index": 0,
                "ax_identifier": "main",
                "title": "Example",
                "role": "AXWindow",
                "focused": True,
                "identity": {
                    "kind": "ax_identifier",
                    "value": "main",
                    "stable_across_samples": True,
                },
            },
            {
                "index": 1,
                "ax_identifier": None,
                "title": "Secondary",
                "role": "AXWindow",
                "focused": False,
                "identity": {
                    "kind": "sample_index",
                    "value": "1",
                    "stable_across_samples": False,
                },
            },
        ],
        "window_count": 2,
        "source_window_count": 2,
        "windows_read_ok": True,
        "app_identity_valid": True,
        "counts_consistent": True,
        "coverage_complete": True,
        "incomplete_reasons": [],
        "limits": {"max_windows": 8, "truncated": False, "include_windows": True},
        "errors": [],
    }


def _verified(expect):
    app = {
        "name": "Example",
        "pid": 42,
        "bundle_id": "com.example.app",
        "role": "AXApplication",
    }
    required_evidence = {
        "ax_trusted_is": "ax_trust",
        "frontmost_app_is": "frontmost_app_identity",
        "window_appeared": "frontmost_app_window_observation",
    }[expect]
    matches = (
        [{"ax_trusted": True}]
        if expect == "ax_trusted_is"
        else [app]
        if expect == "frontmost_app_is"
        else [{"index": 0, "title": "Example", "role": "AXWindow", "focused": True}]
    )
    return {
        "schema": "macos_ax_verify/v0",
        "expect": expect,
        "selector": {
            "state": "true" if expect == "ax_trusted_is" else None,
            "pid": 42 if expect != "ax_trusted_is" else None,
            "role": "AXWindow" if expect == "window_appeared" else None,
        },
        "scope": {
            "source": "frontmost_app_windows",
            "platform": {"system": "Darwin"},
            "max_windows": 0 if expect == "ax_trusted_is" else 8,
        },
        "verdict": "verified",
        "recover": "proceed",
        "observed": {
            "probe_status": "ready",
            "permission": {
                "ax_trusted": True,
                "method": "AXIsProcessTrusted",
                "prompted": False,
            },
            "frontmost_app": app if expect != "ax_trusted_is" else None,
            "count": 1,
            "matches": matches,
            "unknown_count": 0,
            "unknowns": [],
            "window_count": 2 if expect != "ax_trusted_is" else None,
            "source_window_count": 2 if expect != "ax_trusted_is" else None,
            "windows_read_ok": True if expect != "ax_trusted_is" else None,
            "app_identity_valid": expect != "ax_trusted_is",
            "counts_consistent": True if expect != "ax_trusted_is" else False,
            "scope_match": True if expect == "window_appeared" else None,
            "limits": {
                "max_windows": 8,
                "truncated": False,
                "include_windows": expect != "ax_trusted_is",
            },
            "coverage_complete": expect != "ax_trusted_is",
            "incomplete_reasons": [] if expect != "ax_trusted_is" else ["windows_invalid"],
            "proof_complete": True,
            "coverage": {
                "complete": expect != "ax_trusted_is",
                "reasons": [] if expect != "ax_trusted_is" else ["windows_invalid"],
            },
            "proof": {
                "complete": True,
                "truth": "match",
                "required_evidence": required_evidence,
            },
            "errors": [],
        },
        "error": None,
    }


class MacosAxAcceptanceReceiptTests(unittest.TestCase):
    def _receipt(self):
        return build_receipt(
            source_commit="a" * 40,
            probe_script=ROOT / "scripts" / "macos_ax_probe.py",
            verify_script=ROOT / "scripts" / "macos_ax_verify.py",
            probe=_probe(),
            trust_verify=_verified("ax_trusted_is"),
            app_verify=_verified("frontmost_app_is"),
            window_verify=_verified("window_appeared"),
        )

    def test_valid_receipt_passes_with_mixed_identity_coverage(self):
        receipt = self._receipt()
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["identity_coverage"]["stable_ax_identifier_count"], 1)
        self.assertEqual(receipt["identity_coverage"]["sample_local_index_count"], 1)
        self.assertEqual(validate_receipt(receipt), [])
        native = receipt["source"]["scripts"]["native_probe"]
        self.assertTrue(native["path"].endswith("macos_ax_native_probe.swift"))
        self.assertRegex(native["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn(
            "native_ax_frontmost_application",
            receipt["channels"]["selected"],
        )

    def test_missing_native_probe_dependency_is_rejected(self):
        receipt = self._receipt()
        receipt["source"]["scripts"]["native_probe"]["sha256"] = None
        errors = validate_receipt(receipt)
        self.assertIn("evidence_contract_invalid", errors)
        self.assertIn("check_recomputation_mismatch", errors)

    def test_app_identity_accepts_irrelevant_native_window_attribute_error(self):
        app_verify = _verified("frontmost_app_is")
        app_verify["observed"]["probe_status"] = "degraded"
        app_verify["observed"]["errors"] = [
            {
                "stage": "native_ax_window_attributes",
                "message": "one window attribute was unreadable",
            }
        ]
        self.assertTrue(_verify_evidence_admissible(app_verify, "frontmost_app_is", 42))

    def test_failed_postcondition_is_rejected(self):
        receipt = self._receipt()
        receipt["checks"][-1]["passed"] = False
        receipt["status"] = "failed"
        errors = validate_receipt(receipt)
        self.assertIn("required_check_failed", errors)
        self.assertIn("status_not_passed", errors)

    def test_old_minimal_verified_payload_is_rejected(self):
        receipt = self._receipt()
        receipt = build_receipt(
            source_commit="a" * 40,
            probe_script=ROOT / "scripts" / "macos_ax_probe.py",
            verify_script=ROOT / "scripts" / "macos_ax_verify.py",
            probe=_probe(),
            trust_verify={
                "schema": "macos_ax_verify/v0",
                "expect": "ax_trusted_is",
                "verdict": "verified",
                "recover": "proceed",
            },
            app_verify=_verified("frontmost_app_is"),
            window_verify=_verified("window_appeared"),
        )
        self.assertEqual(receipt["status"], "failed")
        self.assertFalse(next(check for check in receipt["checks"] if check["id"] == "trust_verified")["passed"])

    def test_prompted_permission_evidence_is_rejected(self):
        trust_verify = _verified("ax_trusted_is")
        trust_verify["observed"]["permission"]["prompted"] = True
        receipt = build_receipt(
            source_commit="a" * 40,
            probe_script=ROOT / "scripts" / "macos_ax_probe.py",
            verify_script=ROOT / "scripts" / "macos_ax_verify.py",
            probe=_probe(),
            trust_verify=trust_verify,
            app_verify=_verified("frontmost_app_is"),
            window_verify=_verified("window_appeared"),
        )
        check = next(
            item for item in receipt["checks"] if item["id"] == "trust_verified"
        )
        self.assertFalse(check["passed"])
        self.assertEqual(receipt["status"], "failed")

    def test_window_match_must_satisfy_bound_acceptance_selector(self):
        window_verify = _verified("window_appeared")
        window_verify["observed"]["matches"][0]["role"] = "AXButton"
        receipt = build_receipt(
            source_commit="a" * 40,
            probe_script=ROOT / "scripts" / "macos_ax_probe.py",
            verify_script=ROOT / "scripts" / "macos_ax_verify.py",
            probe=_probe(),
            trust_verify=_verified("ax_trusted_is"),
            app_verify=_verified("frontmost_app_is"),
            window_verify=window_verify,
        )
        check = next(
            item
            for item in receipt["checks"]
            if item["id"] == "window_presence_verified"
        )
        self.assertFalse(check["passed"])
        self.assertEqual(receipt["status"], "failed")

    def test_malformed_trust_or_app_match_fails_closed(self):
        for phase, expect, check_id in (
            ("trust_verify", "ax_trusted_is", "trust_verified"),
            ("app_verify", "frontmost_app_is", "frontmost_app_verified"),
        ):
            with self.subTest(phase=phase):
                payloads = {
                    "trust_verify": _verified("ax_trusted_is"),
                    "app_verify": _verified("frontmost_app_is"),
                    "window_verify": _verified("window_appeared"),
                }
                payloads[phase] = _verified(expect)
                payloads[phase]["observed"]["matches"] = [1]
                receipt = build_receipt(
                    source_commit="a" * 40,
                    probe_script=ROOT / "scripts" / "macos_ax_probe.py",
                    verify_script=ROOT / "scripts" / "macos_ax_verify.py",
                    probe=_probe(),
                    **payloads,
                )
                check = next(
                    item for item in receipt["checks"] if item["id"] == check_id
                )
                self.assertFalse(check["passed"])
                self.assertEqual(receipt["status"], "failed")

    def test_window_witness_must_fit_observation_bounds(self):
        window_verify = _verified("window_appeared")
        observed = window_verify["observed"]
        observed["window_count"] = 0
        observed["source_window_count"] = 0
        observed["limits"] = {
            "max_windows": 999,
            "truncated": False,
            "include_windows": False,
        }
        receipt = build_receipt(
            source_commit="a" * 40,
            probe_script=ROOT / "scripts" / "macos_ax_probe.py",
            verify_script=ROOT / "scripts" / "macos_ax_verify.py",
            probe=_probe(),
            trust_verify=_verified("ax_trusted_is"),
            app_verify=_verified("frontmost_app_is"),
            window_verify=window_verify,
        )
        check = next(
            item
            for item in receipt["checks"]
            if item["id"] == "window_presence_verified"
        )
        self.assertFalse(check["passed"])
        self.assertEqual(receipt["status"], "failed")

    def test_malformed_probe_permission_fails_without_crashing(self):
        probe = _probe()
        probe["permission"] = ["unexpected"]
        receipt = build_receipt(
            source_commit="a" * 40,
            probe_script=ROOT / "scripts" / "macos_ax_probe.py",
            verify_script=ROOT / "scripts" / "macos_ax_verify.py",
            probe=probe,
            trust_verify=_verified("ax_trusted_is"),
            app_verify=_verified("frontmost_app_is"),
            window_verify=_verified("window_appeared"),
        )
        check = next(item for item in receipt["checks"] if item["id"] == "ax_trusted")
        self.assertFalse(check["passed"])
        self.assertEqual(receipt["status"], "failed")

    def test_app_verification_rejects_unsupported_probe_status(self):
        app_verify = _verified("frontmost_app_is")
        app_verify["observed"]["probe_status"] = "unsupported_platform"
        receipt = build_receipt(
            source_commit="a" * 40,
            probe_script=ROOT / "scripts" / "macos_ax_probe.py",
            verify_script=ROOT / "scripts" / "macos_ax_verify.py",
            probe=_probe(),
            trust_verify=_verified("ax_trusted_is"),
            app_verify=app_verify,
            window_verify=_verified("window_appeared"),
        )
        check = next(
            item
            for item in receipt["checks"]
            if item["id"] == "frontmost_app_verified"
        )
        self.assertFalse(check["passed"])
        self.assertEqual(receipt["status"], "failed")

    def test_unhashable_app_status_and_check_id_fail_without_crashing(self):
        app_verify = _verified("frontmost_app_is")
        app_verify["observed"]["probe_status"] = []
        receipt = build_receipt(
            source_commit="a" * 40,
            probe_script=ROOT / "scripts" / "macos_ax_probe.py",
            verify_script=ROOT / "scripts" / "macos_ax_verify.py",
            probe=_probe(),
            trust_verify=_verified("ax_trusted_is"),
            app_verify=app_verify,
            window_verify=_verified("window_appeared"),
        )
        self.assertEqual(receipt["status"], "failed")
        receipt["checks"][0]["id"] = []
        self.assertIn("check_coverage_invalid", validate_receipt(receipt))

    def test_payload_tampering_is_rejected(self):
        receipt = self._receipt()
        tampered = copy.deepcopy(receipt)
        tampered["phases"]["probe"]["payload"]["status"] = "degraded"
        self.assertIn("probe_payload_digest_invalid", validate_receipt(tampered))

    def test_rehashed_payload_tampering_is_rejected_by_evidence_recomputation(self):
        receipt = self._receipt()
        phase = receipt["phases"]["probe"]
        phase["payload"]["status"] = "degraded"
        phase["payload_sha256"] = _payload_sha256(phase["payload"])
        errors = validate_receipt(receipt)
        self.assertIn("evidence_contract_invalid", errors)
        self.assertIn("check_recomputation_mismatch", errors)

    def test_forged_check_ids_are_rejected(self):
        receipt = self._receipt()
        receipt["checks"] = [
            {"id": f"forged-{index}", "passed": True}
            for index in range(13)
        ]
        self.assertIn("check_coverage_invalid", validate_receipt(receipt))

    def test_runner_persists_failed_receipt_when_verify_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            probe_script = temp / "macos_ax_probe.py"
            verify_script = temp / "macos_ax_verify.py"
            receipt_path = temp / "failed-receipt.json"
            probe_script.write_text(
                "import json\n"
                "print(json.dumps({'schema':'macos_ax_probe/v0','read_only':True,"
                "'status':'degraded','permission':{'ax_trusted':False},"
                "'frontmost_app':None,'windows':[],'window_count':0,"
                "'source_window_count':None,'windows_read_ok':None,"
                "'app_identity_valid':False,'counts_consistent':False,"
                "'coverage_complete':False,'incomplete_reasons':['probe_not_ready'],"
                "'limits':{'max_windows':8,'truncated':False,'include_windows':True},"
                "'errors':[]}))\n",
                encoding="utf-8",
            )
            verify_script.write_text(
                "import json\n"
                "print(json.dumps({'schema':'macos_ax_verify/v0','expect':'unknown',"
                "'selector':{},'scope':{},'verdict':'error','recover':'replan',"
                "'observed':{},'error':'synthetic_failure'}))\n"
                "raise SystemExit(3)\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "AB_MACOS_AX_PROBE_SCRIPT": str(probe_script),
                    "AB_MACOS_AX_VERIFY_SCRIPT": str(verify_script),
                    "AB_MACOS_ACCEPT_RECEIPT_PATH": str(receipt_path),
                    "AB_MACOS_ACCEPT_SOURCE_COMMIT": "a" * 40,
                }
            )
            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "macos_accept" / "run_readonly_accept.sh")],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertTrue(receipt_path.is_file())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(
                receipt["phases"]["probe"]["payload"]["status"],
                "degraded",
            )
            self.assertEqual(
                receipt["phases"]["trust_verify"]["payload"]["error"],
                "synthetic_failure",
            )


if __name__ == "__main__":
    unittest.main()
