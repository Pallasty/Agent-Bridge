import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "eval" / "qwen3_q8_scope_plan.py"
SPEC = importlib.util.spec_from_file_location("qwen3_q8_scope_plan", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Q8ScopePlanTests(unittest.TestCase):
    def test_percentile_ranks_are_deterministic_on_ties(self):
        rows = [
            {"module": "b", "risk": 1.0},
            {"module": "a", "risk": 1.0},
            {"module": "c", "risk": 2.0},
        ]
        ranks = MODULE.percentile_ranks(rows, "risk")
        self.assertEqual(ranks, {"a": 0.0, "b": 0.5, "c": 1.0})

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(MODULE.RISK_WEIGHTS.values()), 1.0)

    def test_scope_is_perturbation_only(self):
        self.assertEqual(MODULE.TARGET_PERTURBATION_MODULES, 48)
        self.assertIn("perturbation", MODULE.SCHEMA)

    def test_complete_scope_never_claims_candidate_authority(self):
        modules = [
            {
                "module": f"talker.model.layers.{index}.mlp.down_proj",
                "tensor": f"talker.model.layers.{index}.mlp.down_proj.weight",
                "family": "feed_forward_or_projection",
                "elements": 128,
                "static_q8_nrmse": 0.01 + index / 10000,
                "static_entropy_256": 0.5 + index / 1000,
            }
            for index in range(48)
        ]
        plan = {
            "selection": {"eligible_count": 48},
            "modules": modules,
        }
        capture = {
            "planned_modules": 48,
            "cases_completed": 1,
            "cases": [
                {
                    "rows": [
                        {
                            "module": row["module"],
                            "sample_count": 4096,
                            "nonfinite_candidates": 0,
                            "rms": 1.0,
                            "outlier_ratio_6x_median_abs": 0.01,
                            "kurtosis": 3.0,
                            "normalized_entropy": {"256": 0.7},
                        }
                        for row in modules
                    ]
                }
            ],
        }
        report = MODULE.build_scope(plan, capture, "plan", "capture", "gate")
        self.assertEqual(report["status"], "Q8_PERTURBATION_SCOPE_PLANNED_DEFAULT_OFF")
        self.assertEqual(report["summary"]["first_perturbation_scope_modules"], 48)
        self.assertFalse(report["functional_sensitivity_executed"])
        self.assertFalse(report["writes_quantized_weights"])
        self.assertFalse(report["creates_runtime_candidate"])
        self.assertFalse(report["authorization"]["allows_fake_quant_execution"])
        self.assertFalse(report["authorization"]["allows_quantized_weight_writing"])


if __name__ == "__main__":
    unittest.main()
