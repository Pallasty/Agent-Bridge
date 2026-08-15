import ast
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "eval" / "qwen3_fake_q8_sensitivity.py"
POLICY = (
    ROOT
    / "scripts"
    / "eval"
    / "fixtures"
    / "qwen3_tts_functional_sensitivity_policy_v0.json"
)
SPEC = importlib.util.spec_from_file_location("qwen3_fake_q8_sensitivity", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


class FakeQ8QuantizerTests(unittest.TestCase):
    def test_half_away_from_zero_ties_and_int8_range(self):
        source = np.zeros((1, 128), dtype=np.float64)
        source[0, :4] = [127.0, 0.5, -0.5, 0.0]
        original = source.copy()

        result = MODULE.quantize_groupwise_q8_numpy(source, 128)

        np.testing.assert_array_equal(result["q"][0, :4], [127, 1, -1, 0])
        np.testing.assert_array_equal(result["q"][0, 4:], np.zeros(124, dtype=np.int8))
        np.testing.assert_array_equal(
            result["dequant"][0, :4],
            np.array([127.0, 1.0, -1.0, 0.0], dtype=np.float16),
        )
        np.testing.assert_array_equal(source, original)
        self.assertEqual(result["q"].dtype, np.int8)
        self.assertEqual(result["dequant"].dtype, np.float16)
        self.assertEqual(result["group_count"], 1)
        self.assertEqual(result["zero_group_count"], 0)
        self.assertEqual(result["q_min"], -1)
        self.assertEqual(result["q_max"], 127)

    def test_zero_group_is_exact_and_negative_128_is_impossible(self):
        source = np.zeros((2, 128), dtype=np.float64)
        source[1, 0] = -127.0
        source[1, 1] = 127.0
        source[1, 2] = -126.6

        result = MODULE.quantize_groupwise_q8_numpy(source, 128)

        self.assertEqual(result["group_count"], 2)
        self.assertEqual(result["zero_group_count"], 1)
        np.testing.assert_array_equal(result["q"][0], np.zeros(128, dtype=np.int8))
        np.testing.assert_array_equal(
            result["dequant"][0],
            np.zeros(128, dtype=np.float16),
        )
        self.assertFalse(np.any(result["q"] == -128))
        self.assertGreaterEqual(int(result["q"].min()), -127)
        self.assertLessEqual(int(result["q"].max()), 127)

    def test_grouping_is_row_local_and_deterministic(self):
        source = np.empty((2, 256), dtype=np.float64)
        source[0, :128] = 1.0
        source[0, 128:] = 2.0
        source[1, :128] = 3.0
        source[1, 128:] = 4.0

        first = MODULE.quantize_groupwise_q8_numpy(source, 128)
        second = MODULE.quantize_groupwise_q8_numpy(source.copy(), 128)

        self.assertEqual(first["group_count"], 4)
        np.testing.assert_array_equal(first["q"], np.full_like(first["q"], 127))
        np.testing.assert_array_equal(first["dequant"], source.astype(np.float16))
        np.testing.assert_array_equal(first["q"], second["q"])
        np.testing.assert_array_equal(first["dequant"], second["dequant"])
        self.assertEqual(first["dequant_sha256"], second["dequant_sha256"])

    def test_rank_or_row_width_that_would_cross_rows_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.quantize_groupwise_q8_numpy(
                np.zeros(128, dtype=np.float64),
                128,
            )
        # The total element count is divisible by 128, but each row is not.
        # Accepting this shape would silently permit cross-row groups.
        with self.assertRaises(ValueError):
            MODULE.quantize_groupwise_q8_numpy(
                np.zeros((2, 64), dtype=np.float64),
                128,
            )

    def test_non_finite_source_is_rejected(self):
        for value in (np.nan, np.inf, -np.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                source = np.zeros((1, 128), dtype=np.float64)
                source[0, 17] = value
                MODULE.quantize_groupwise_q8_numpy(source, 128)


class FakeQ8DivergenceTests(unittest.TestCase):
    def test_code_divergence_exact_equal_gold(self):
        codes = np.arange(48, dtype=np.int64).reshape(3, 16)

        metrics = MODULE.code_divergence_metrics(codes, codes.copy())

        self.assertTrue(metrics["exact_equal"])
        self.assertEqual(metrics["control_sha256"], metrics["fake_sha256"])
        self.assertEqual(metrics["control_time_steps"], 3)
        self.assertEqual(metrics["fake_time_steps"], 3)
        self.assertEqual(metrics["absolute_length_drift"], 0)
        self.assertEqual(metrics["relative_length_drift"], 0.0)
        self.assertEqual(metrics["per_codebook_agreement"], [1.0] * 16)
        self.assertEqual(metrics["first_codebook_agreement"], 1.0)
        self.assertEqual(metrics["full_frame_agreement"], 1.0)
        self.assertEqual(metrics["element_mismatch_fraction"], 0.0)
        self.assertEqual(metrics["common_prefix_frames"], 3)
        self.assertIsNone(metrics["first_divergent_frame"])
        self.assertEqual(metrics["first_codebook_normalized_edit_distance"], 0.0)

    def test_code_divergence_length_and_content_gold(self):
        control = np.arange(64, dtype=np.int64).reshape(4, 16)
        control[:, 0] = [1, 2, 3, 4]
        fake = control[:3].copy()
        fake[1, 1] += 100
        fake[2, 0] = 9

        metrics = MODULE.code_divergence_metrics(control, fake)

        self.assertFalse(metrics["exact_equal"])
        self.assertEqual(metrics["control_time_steps"], 4)
        self.assertEqual(metrics["fake_time_steps"], 3)
        self.assertEqual(metrics["absolute_length_drift"], 1)
        self.assertEqual(metrics["relative_length_drift"], 0.25)
        np.testing.assert_allclose(
            metrics["per_codebook_agreement"],
            [2.0 / 3.0, 2.0 / 3.0] + [1.0] * 14,
        )
        self.assertAlmostEqual(metrics["first_codebook_agreement"], 2.0 / 3.0)
        self.assertAlmostEqual(metrics["full_frame_agreement"], 1.0 / 3.0)
        self.assertAlmostEqual(metrics["element_mismatch_fraction"], 2.0 / 48.0)
        self.assertEqual(metrics["common_prefix_frames"], 1)
        self.assertEqual(metrics["first_divergent_frame"], 1)
        # [1,2,3,4] -> [1,2,9] has one substitution and one deletion.
        self.assertEqual(metrics["first_codebook_normalized_edit_distance"], 0.5)

    def test_codebook_count_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.code_divergence_metrics(
                np.zeros((2, 16), dtype=np.int64),
                np.zeros((2, 15), dtype=np.int64),
            )

    def test_logit_summary_identical_gold(self):
        logits = np.array(
            [
                [4.0, 2.0, 1.0, -1.0],
                [-2.0, 0.0, 3.0, 1.0],
            ],
            dtype=np.float64,
        )

        metrics = MODULE.summarize_logit_pair(logits, logits.copy(), top_k=2)

        self.assertEqual(metrics["aligned_steps"], 2)
        self.assertAlmostEqual(metrics["control_to_fake_kl_mean"], 0.0, places=12)
        self.assertAlmostEqual(metrics["jensen_shannon_mean"], 0.0, places=12)
        self.assertEqual(metrics["top1_agreement"], 1.0)
        self.assertEqual(metrics["top8_retention"], 1.0)
        self.assertAlmostEqual(metrics["centered_logit_nrmse"], 0.0, places=12)

    def test_logit_summary_detects_rank_reversal_and_aligns_steps(self):
        control = np.array(
            [
                [4.0, 3.0, 2.0, 1.0],
                [1.0, 2.0, 3.0, 4.0],
                [9.0, 1.0, 0.0, -1.0],
            ],
            dtype=np.float64,
        )
        fake = np.array(
            [
                [1.0, 2.0, 3.0, 4.0],
                [4.0, 3.0, 2.0, 1.0],
            ],
            dtype=np.float64,
        )

        metrics = MODULE.summarize_logit_pair(control, fake, top_k=1)

        self.assertEqual(metrics["aligned_steps"], 2)
        self.assertEqual(metrics["top1_agreement"], 0.0)
        self.assertEqual(metrics["top8_retention"], 0.0)
        self.assertGreater(metrics["control_to_fake_kl_mean"], 0.0)
        self.assertGreater(metrics["jensen_shannon_mean"], 0.0)
        self.assertGreater(metrics["centered_logit_nrmse"], 0.0)

    def test_logit_summary_rejects_vocab_drift_or_non_finite_values(self):
        with self.assertRaises(ValueError):
            MODULE.summarize_logit_pair(
                np.zeros((2, 4), dtype=np.float64),
                np.zeros((2, 3), dtype=np.float64),
            )
        with self.assertRaises(ValueError):
            MODULE.summarize_logit_pair(
                np.array([[0.0, np.nan]], dtype=np.float64),
                np.zeros((1, 2), dtype=np.float64),
            )

    def test_frozen_t_plus_one_and_t_logit_alignment(self):
        talker = np.zeros((4, 3072), dtype=np.float16)
        predictors = [
            np.zeros((3, 2048), dtype=np.float16) for _ in range(15)
        ]
        summary = MODULE.validate_logit_alignment(3, talker, predictors)
        self.assertTrue(summary["alignment_contract_exact"])
        self.assertEqual(summary["talker_observed_steps"], 4)
        self.assertEqual(summary["predictor_observed_steps"], [3] * 15)

        with self.assertRaises(ValueError):
            MODULE.validate_logit_alignment(3, talker[:3], predictors)
        with self.assertRaises(ValueError):
            MODULE.validate_logit_alignment(3, talker, predictors[:-1])
        drifted = predictors.copy()
        drifted[7] = np.zeros((2, 2048), dtype=np.float16)
        with self.assertRaises(ValueError):
            MODULE.validate_logit_alignment(3, talker, drifted)


class FakeQ8StaticSafetyTests(unittest.TestCase):
    def test_one_shot_claim_is_owner_only_and_cannot_be_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claim = root / "trial.claim.json"
            result = root / "trial.result.json"
            receipt = MODULE.consume_trial_claim(
                claim,
                result,
                {"trial_id": "trial-a"},
            )
            self.assertEqual(receipt["mode"], "0o600")
            self.assertTrue(claim.is_file())
            with self.assertRaises(ValueError):
                MODULE.consume_trial_claim(
                    claim,
                    result,
                    {"trial_id": "trial-a"},
                )

    def test_json_snapshot_hashes_the_same_bytes_that_are_parsed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text('{"value":1}', encoding="utf-8")
            document, digest = MODULE.load_json_snapshot(path)
            self.assertEqual(document, {"value": 1})
            self.assertEqual(
                digest,
                MODULE.bytes_sha256(path.read_bytes()),
            )
            link = Path(directory) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(OSError):
                MODULE.load_json_snapshot(link)

    def test_instance_override_restores_after_body_and_setup_faults(self):
        class Holder:
            def method(self):
                return "class"

        holder = Holder()
        restored = {}
        with self.assertRaises(KeyboardInterrupt):
            with MODULE.temporary_instance_override(
                holder,
                "method",
                lambda: "proxy",
                restored,
            ):
                raise KeyboardInterrupt
        self.assertNotIn("method", holder.__dict__)
        self.assertTrue(restored["method"])

        class FaultOnce:
            def __init__(self):
                object.__setattr__(self, "fault", True)

            def __setattr__(self, name, value):
                object.__setattr__(self, name, value)
                if name == "method" and self.fault:
                    object.__setattr__(self, "fault", False)
                    raise RuntimeError("injected setup fault")

        faulty = FaultOnce()
        setup_restored = {}
        with self.assertRaises(RuntimeError):
            with MODULE.temporary_instance_override(
                faulty,
                "method",
                lambda: "proxy",
                setup_restored,
            ):
                pass
        self.assertNotIn("method", faulty.__dict__)
        self.assertTrue(setup_restored["method"])

    def test_control_logit_replay_requires_bit_exact_all_heads(self):
        talker = np.zeros((4, 3072), dtype=np.float32)
        predictors = [
            np.zeros((3, 2048), dtype=np.float32) for _ in range(15)
        ]
        control = {"talker": talker, "predictors": predictors}
        replay = {
            "talker": talker.copy(),
            "predictors": [rows.copy() for rows in predictors],
        }
        self.assertTrue(
            MODULE.control_logit_replay_evidence(control, replay)["exact"]
        )
        replay["predictors"][4][1, 7] = 1.0
        evidence = MODULE.control_logit_replay_evidence(control, replay)
        self.assertFalse(evidence["exact"])
        self.assertFalse(evidence["predictor_heads_exact"][4])

        signed_zero_replay = {
            "talker": talker.copy(),
            "predictors": [rows.copy() for rows in predictors],
        }
        signed_zero_replay["talker"][0, 0] = -0.0
        signed_zero_evidence = MODULE.control_logit_replay_evidence(
            control,
            signed_zero_replay,
        )
        self.assertFalse(signed_zero_evidence["exact"])
        self.assertEqual(
            signed_zero_evidence["comparison"],
            "canonical_shape_dtype_and_bytes",
        )

    def test_expected_non_model_helpers_are_public(self):
        for name in (
            "quantize_groupwise_q8_numpy",
            "code_divergence_metrics",
            "summarize_logit_pair",
            "temporary_linear_forward_proxy",
        ):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(MODULE, name)))

    def test_source_has_no_weight_mutator_model_writer_audio_or_socket_call(self):
        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)

        forbidden_attributes = {
            "data",
            "copy_",
            "load_state_dict",
            "register_parameter",
            "register_buffer",
            "save_pretrained",
            "set_",
        }
        seen_forbidden_attributes = sorted(
            {
                node.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
                and node.attr in forbidden_attributes
            }
        )
        self.assertEqual(seen_forbidden_attributes, [])

        assigned_weight_attributes = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and node.attr == "weight"
        ]
        self.assertEqual(assigned_weight_attributes, [])

        forbidden_calls = {
            "torch.save",
            "safetensors.torch.save_file",
            "safetensors.torch.save_model",
            "safetensors.serialize_file",
            "socket.socket",
            "wave.open",
            "soundfile.write",
            "torchaudio.save",
        }
        seen_forbidden_calls = sorted(
            {
                name
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and (name := dotted_name(node.func)) in forbidden_calls
            }
        )
        self.assertEqual(seen_forbidden_calls, [])

        forbidden_import_roots = {"socket", "soundfile", "torchaudio", "wave"}
        imported_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        self.assertTrue(forbidden_import_roots.isdisjoint(imported_roots))

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "setattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
            ):
                self.assertNotEqual(node.args[1].value, "weight")

        self.assertNotIn("READY_FOR_CANDIDATE", source)
        self.assertNotIn("READY_FOR_RUNTIME", source)
        self.assertNotIn("afplay", source)

    def test_frozen_policy_denies_writes_worker_audio_and_promotion(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        authorization = policy["authorization"]

        self.assertTrue(
            authorization["allows_exactly_one_module_one_case_fake_q8_smoke"]
        )
        for key in (
            "allows_additional_module_or_case",
            "allows_weight_mutation",
            "allows_quantized_weight_writing",
            "allows_packing_or_scale_storage_claim",
            "allows_runtime_candidate_generation",
            "allows_worker_socket_use",
            "allows_audio_decode_write_or_playback",
            "allows_runtime_wiring_fallback_deployment_or_promotion",
        ):
            with self.subTest(key=key):
                self.assertFalse(authorization[key])

        self.assertFalse(policy["execution"]["audio_decode"])
        self.assertFalse(policy["execution"]["audio_write"])
        self.assertTrue(policy["restoration"]["weight_mutation_forbidden"])
        self.assertEqual(
            policy["execution"]["explicit_cli_flag"],
            "--execute-frozen-one-trial",
        )
        self.assertTrue(policy["execution"]["one_shot_claim_o_excl"])
        self.assertTrue(
            policy["execution"]["claim_is_never_automatically_deleted"]
        )
        self.assertEqual(
            Path(policy["execution"]["claim_path"]).parent,
            MODULE.TRIAL_ROOT,
        )
        self.assertEqual(
            Path(policy["execution"]["result_path"]).parent,
            MODULE.TRIAL_ROOT,
        )


if __name__ == "__main__":
    unittest.main()
