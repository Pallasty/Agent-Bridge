import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "eval" / "qwen3_activation_gate.py"
SPEC = importlib.util.spec_from_file_location("qwen3_activation_gate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
CAPTURE_HASH = "c" * 64


class ActivationGateTests(unittest.TestCase):
    def fixture(self):
        corpus = {"schema": MODULE.CORPUS_SCHEMA, "cases": [{"id": "case-a"}]}
        plan = {
            "schema": MODULE.PLAN_SCHEMA,
            "static_report_sha256": "static",
            "selection": {"algorithm": "rotation", "selected_count": 1},
            "modules": [
                {
                    "module": "layer.proj",
                    "tensor": "layer.proj.weight",
                    "shape": [2, 2],
                    "source_dtype": "BF16",
                }
            ],
        }
        policy = {
            "schema": MODULE.POLICY_SCHEMA,
            "activation_plan": {
                "sha256": "plan",
                "static_report_sha256": "static",
                "selection_algorithm": "rotation",
                "selected_modules": 1,
            },
            "corpus": {"sha256": "corpus"},
            "source_model": {
                "device": "mps",
                "runtime_dtype": "float16",
                "runtime": {
                    "python": "3.12.13",
                    "torch": "2.13.0",
                    "qwen_tts": "0.1.1",
                    "generation_api": "generate_custom_voice",
                    "language": "Chinese",
                },
            },
            "resource_ladder": {
                "receipt_sha256": "ladder",
                "module_counts": [8, 24, 48, 96],
            },
            "capture_requirements": {"minimum_samples_per_module_case": 4},
            "source_assets": [{"partition": "talker", "bytes": 8, "sha256": "asset"}],
        }
        capture = {
            "schema": MODULE.CAPTURE_SCHEMA,
            "status": "CAPTURED_READ_ONLY_FULL",
            "plan_sha256": "plan",
            "corpus_sha256": "corpus",
            "device": "mps",
            "dtype": "float16",
            "runtime": {
                "python": "3.12.13",
                "torch": "2.13.0",
                "qwen_tts": "0.1.1",
                "generation_api": "generate_custom_voice",
                "language": "Chinese",
            },
            "planned_modules": 1,
            "resolved_modules": 1,
            "resolved_bindings": [
                {
                    "module": "layer.proj",
                    "tensor": "layer.proj.weight",
                    "shape": [2, 2],
                    "source_dtype": "BF16",
                    "weight_identity_verified": True,
                }
            ],
            "cases_requested": 1,
            "cases_completed": 1,
            "model_assets": [{"partition": "talker", "bytes": 8, "sha256": "asset"}],
            "empty_activations": [],
            "nonfinite_activations": [],
            "writes_audio": False,
            "mutates_weights": False,
            "allows_candidate_generation": False,
            "allows_runtime_wiring_or_promotion": False,
            "cases": [
                {
                    "case": {"id": "case-a"},
                    "rows": [
                        {
                            "module": "layer.proj",
                            "sample_count": 4,
                            "nonfinite_candidates": 0,
                            "total_elements_seen": 8,
                            "output_signature_sha256": "signature",
                        }
                    ],
                }
            ],
        }
        resource_ladder = {
            "schema": MODULE.LADDER_SCHEMA,
            "activation_plan_sha256": "plan",
            "corpus_sha256": "corpus",
            "runs": [
                {
                    "modules": modules,
                    "capture_status": (
                        "CAPTURED_READ_ONLY_FULL"
                        if modules == 96
                        else "CAPTURED_READ_ONLY_SMOKE"
                    ),
                    "report_sha256": CAPTURE_HASH if modules == 96 else "b" * 64,
                    "time_log_sha256": "a" * 64,
                    "swaps": 0,
                    "empty_activations": 0,
                    "nonfinite_activations": 0,
                }
                for modules in (8, 24, 48, 96)
            ],
            "allows_fake_quant_execution": False,
            "allows_quantized_weight_writing": False,
            "allows_runtime_candidate_generation": False,
            "allows_runtime_wiring_or_promotion": False,
        }
        return policy, plan, capture, corpus, resource_ladder

    def test_complete_receipt_reaches_design_only(self):
        policy, plan, capture, corpus, resource_ladder = self.fixture()
        report = MODULE.evaluate(
            policy,
            plan,
            capture,
            corpus,
            resource_ladder,
            "policy",
            "plan",
            CAPTURE_HASH,
            "corpus",
            "ladder",
        )
        self.assertEqual(report["status"], MODULE.READY)
        self.assertTrue(report["allows_functional_sensitivity_design"])
        self.assertFalse(report["allows_fake_quant_execution"])
        self.assertFalse(report["allows_quantized_weight_writing"])

    def test_nonfinite_candidate_fails_closed(self):
        policy, plan, capture, corpus, resource_ladder = self.fixture()
        capture["cases"][0]["rows"][0]["nonfinite_candidates"] = 1
        report = MODULE.evaluate(
            policy,
            plan,
            capture,
            corpus,
            resource_ladder,
            "policy",
            "plan",
            CAPTURE_HASH,
            "corpus",
            "ladder",
        )
        self.assertEqual(report["status"], MODULE.BLOCKED)
        self.assertIn("nonfinite_candidates:case-a:layer.proj", report["failures"])

    def test_runtime_and_resource_ladder_are_hard_bound(self):
        policy, plan, capture, corpus, resource_ladder = self.fixture()
        capture["device"] = "cpu"
        resource_ladder["runs"][-1]["report_sha256"] = "d" * 64
        report = MODULE.evaluate(
            policy,
            plan,
            capture,
            corpus,
            resource_ladder,
            "policy",
            "plan",
            CAPTURE_HASH,
            "corpus",
            "ladder",
        )
        self.assertEqual(report["status"], MODULE.BLOCKED)
        self.assertIn("capture_device_mismatch", report["failures"])
        self.assertIn("resource_ladder_full_capture_hash_mismatch", report["failures"])


if __name__ == "__main__":
    unittest.main()
