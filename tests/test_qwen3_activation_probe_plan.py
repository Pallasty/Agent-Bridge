import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "eval" / "qwen3_activation_probe_plan.py"
SPEC = importlib.util.spec_from_file_location("qwen3_activation_probe_plan", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def tensor(name, family, shape=(4, 4), elements=16, diagnostics=True):
    return {
        "name": name,
        "family": family,
        "dtype": "BF16",
        "shape": list(shape),
        "element_count": elements,
        "diagnostics": ({
            "groupwise_q8_nrmse": {"128": 0.01},
            "normalized_entropy": {"256": 0.8},
        } if diagnostics else None),
    }


class ActivationProbePlanTests(unittest.TestCase):
    def test_excludes_codec_embeddings_heads_and_non_matrix_tensors(self):
        report = {"files": [
            {"partition": "talker", "tensors": [
                tensor("talker.model.layers.0.self_attn.q_proj.weight", "attention", elements=64),
                tensor("talker.model.embed_tokens.weight", "text_embedding", elements=128),
                tensor("talker.code_predictor.lm_head.0.weight", "code_predictor_head"),
                tensor("talker.model.layers.0.norm.weight", "norm_scale_or_bias", shape=(4,)),
            ]},
            {"partition": "speech_tokenizer_codec", "tensors": [
                tensor("decoder.weight", "feed_forward_or_projection", elements=256),
            ]},
        ]}
        plan = MODULE.build_plan(report, "abc", 96)
        self.assertEqual(plan["selection"]["eligible_count"], 1)
        self.assertEqual(plan["modules"][0]["module"], "talker.model.layers.0.self_attn.q_proj")
        self.assertFalse(plan["capture_budget"]["retain_full_activations"])
        self.assertFalse(plan["execution_boundary"]["modifies_worker_v1"])

    def test_selection_is_bounded_and_deterministic(self):
        rows = [
            tensor(f"talker.model.layers.{index}.mlp.weight", "feed_forward_or_projection", elements=index + 1)
            for index in range(5)
        ]
        report = {"files": [{"partition": "talker", "tensors": rows}]}
        first = MODULE.build_plan(report, "abc", 2)
        second = MODULE.build_plan(report, "abc", 2)
        self.assertEqual(first, second)
        self.assertEqual([row["elements"] for row in first["modules"]], [5, 4])


if __name__ == "__main__":
    unittest.main()
