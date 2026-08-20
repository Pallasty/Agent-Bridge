import importlib.util
import pathlib
import unittest
import json

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/macos-ax-composite-identity-eligibility.py"
SPEC = importlib.util.spec_from_file_location("composite_identity", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def receipt():
    return {
        "schema": "agent_bridge.macos_ax_composite_identity_probe.v0",
        "status": "eligible", "eligible_now": True, "read_only": True,
        "action_performed": False, "sample_count": 2, "sample_interval_ms": 250,
        "scope": {"bundle_id": "com.example.App", "pid": 123, "process_launch_time_ms": 1000},
        "candidates": [
            {"cg_window_id": 7, "focused_first": True, "focused_second": True,
             "unique_bijection_first": True, "unique_bijection_second": True, "stable_across_samples": True},
            {"cg_window_id": 8, "focused_first": False, "focused_second": False,
             "unique_bijection_first": True, "unique_bijection_second": True, "stable_across_samples": True},
        ],
    }


class CompositeIdentityEligibilityTests(unittest.TestCase):
    def test_valid_two_sample_bijection_is_readonly_eligible(self):
        result = MODULE.summarize(receipt())
        self.assertTrue(result["eligible_now"])
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["unfocused_candidate_count"], 1)
        self.assertFalse(result["live_focus_authorized"])
        self.assertFalse(result["titles_retained"])
        self.assertFalse(result["bounds_retained"])

    def test_any_contract_mutation_fails_closed(self):
        mutations = [
            ("status", "ineligible"), ("eligible_now", False), ("read_only", False),
            ("action_performed", True), ("sample_count", 1),
        ]
        for field, value in mutations:
            candidate = receipt(); candidate[field] = value
            with self.subTest(field=field): self.assertFalse(MODULE.summarize(candidate)["eligible_now"])
        for field, value in (("stable_across_samples", False), ("unique_bijection_second", False),
                             ("cg_window_id", 0), ("focused_first", None)):
            candidate = receipt(); candidate["candidates"][1][field] = value
            with self.subTest(field=field): self.assertFalse(MODULE.summarize(candidate)["eligible_now"])

    def test_title_and_bounds_never_escape_reducer(self):
        candidate = receipt()
        candidate["candidates"][0]["title"] = "Secret"
        candidate["candidates"][0]["rect"] = {"x": 1}
        output = str(MODULE.summarize(candidate))
        self.assertNotIn("Secret", output)
        self.assertNotIn("rect", output)

    def test_swift_source_is_read_only_and_uses_exact_components(self):
        source = (ROOT / "scripts/macos_ax_composite_identity_probe.swift").read_text()
        self.assertIn("CGWindowListCopyWindowInfo", source)
        self.assertIn("process_launch_time_ms", source)
        self.assertIn("cg_window_id", source)
        self.assertNotIn("AXUIElementSetAttributeValue", source)
        self.assertNotIn("System Events", source)

    def test_live_evidence_is_negative_and_does_not_expand_authority(self):
        path = ROOT / "docs/design/evidence/macos_ax_composite_identity_readonly_eligibility_2026_08_20.json"
        value = json.loads(path.read_text())
        self.assertEqual(value["decision"]["status"], "INELIGIBLE_COMPOSITE_IDENTITY")
        self.assertEqual(value["observation"]["final_reason"], "ax_title_incomplete")
        self.assertEqual(value["observation"]["candidate_count"], 0)
        self.assertFalse(value["source"]["raw_receipt_retained"])
        self.assertFalse(value["source"]["titles_retained"])
        self.assertFalse(value["source"]["bounds_retained"])
        self.assertTrue(all(item is False for item in value["claim_boundary"].values()))


if __name__ == "__main__": unittest.main()
