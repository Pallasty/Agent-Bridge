import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "eval" / "qwen3_functional_sensitivity_gate.py"
SPEC = importlib.util.spec_from_file_location("qwen3_functional_sensitivity_gate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FunctionalSensitivityGateTests(unittest.TestCase):
    def fixture(self):
        target = {
            "module": "talker.model.layers.6.mlp.gate_proj",
            "tensor": "talker.model.layers.6.mlp.gate_proj.weight",
            "family": "feed_forward_or_projection",
            "shape": [6144, 2048],
            "elements": 12582912,
            "source_dtype": "BF16",
            "runtime_dtype": "float16",
            "joint_risk_score": 0.25,
        }
        case = {"id": "case-a", "speaker": "Serena", "text": "text"}
        hashes = {
            "policy": "policy",
            "plan": "plan",
            "activation_gate": "gate",
            "activation_capture": "capture",
            "scope": "scope",
            "probe": "probe",
            "manifest": "manifest",
            "corpus": "corpus",
            "thresholds": "thresholds",
        }
        policy = {
            "schema": MODULE.POLICY_SCHEMA,
            "status": "FROZEN_ONE_MODULE_ONE_CASE_SMOKE_ONLY",
            "inputs": {
                "activation_plan_sha256": "plan",
                "activation_gate_sha256": "gate",
                "activation_capture_sha256": "capture",
                "perturbation_scope_sha256": "scope",
                "token_boundary_probe_sha256": "probe",
                "runtime_manifest_sha256": "manifest",
                "corpus_sha256": "corpus",
                "thresholds_sha256": "thresholds",
            },
            "target": target,
            "case": {"id": "case-a", "speaker": "Serena", "language": "Chinese"},
            "source_assets": [
                {"partition": "talker", "bytes": 8, "sha256": "asset"}
            ],
            "functional_runtime_source_pins": [
                {
                    "package": package,
                    "relative_path": relative_path,
                    "bytes": 8,
                    "sha256": "a" * 64,
                }
                for package, relative_path in (
                    ("qwen_tts", "__init__.py"),
                    ("transformers", "__init__.py"),
                    ("transformers", "generation/utils.py"),
                    ("safetensors", "__init__.py"),
                    ("safetensors", "torch.py"),
                    ("safetensors", "_safetensors_rust.abi3.so"),
                )
            ],
            "quantizer": {
                "group_size": 128,
                "qmin": -127,
                "qmax": 127,
                "rounding": "half_away_from_zero",
            },
            "execution": {
                "trial_id":
                    "qwen3-tts-q2-fs-v0-l6-gate-proj-zh-short-neutral-serena-001",
                "claim_path":
                    str(Path.home()) + "/.local/state/agent-bridge/"
                    "qwen3-evaluation-ledger/"
                    "qwen3-tts-q2-fs-v0-l6-gate-proj-zh-short-neutral-serena-001"
                    ".claim.json",
                "result_path":
                    str(Path.home()) + "/.local/state/agent-bridge/"
                    "qwen3-evaluation-ledger/"
                    "qwen3-tts-q2-fs-v0-l6-gate-proj-zh-short-neutral-serena-001"
                    ".result.json",
                "one_shot_claim_o_excl": True,
                "claim_is_never_automatically_deleted": True,
                "claim_and_result_parent_directory_fsync": True,
                "gate_evaluator_sha256": "a" * 64,
                "processes": 1,
                "modules": 1,
                "cases": 1,
                "fake_trials": 1,
                "do_sample": False,
                "subtalker_dosample": False,
            },
            "authorization": {
                "allows_exactly_one_module_one_case_fake_q8_smoke": True,
                "allows_additional_module_or_case": False,
                "allows_weight_mutation": False,
                "allows_quantized_weight_writing": False,
                "allows_packing_or_scale_storage_claim": False,
                "allows_runtime_candidate_generation": False,
                "allows_worker_socket_use": False,
                "allows_audio_decode_write_or_playback": False,
                "allows_runtime_wiring_fallback_deployment_or_promotion": False,
            },
        }
        plan = {
            "schema": MODULE.PLAN_SCHEMA,
            "modules": [{key: target[key] for key in (
                "module", "tensor", "family", "shape", "elements", "source_dtype"
            )}],
        }
        activation_gate = {
            "schema": MODULE.ACTIVATION_GATE_SCHEMA,
            "status": "READY_FOR_FUNCTIONAL_SENSITIVITY_DESIGN",
            "activation_plan_sha256": "plan",
            "activation_capture_sha256": "capture",
            "corpus_sha256": "corpus",
            "allows_quantized_weight_writing": False,
            "allows_runtime_candidate_generation": False,
            "allows_runtime_wiring_or_promotion": False,
        }
        scope = {
            "schema": MODULE.SCOPE_SCHEMA,
            "status": "Q8_PERTURBATION_SCOPE_PLANNED_DEFAULT_OFF",
            "activation_plan_sha256": "plan",
            "activation_capture_sha256": "capture",
            "activation_gate_sha256": "gate",
            "modules": [{
                "module": target["module"],
                "joint_risk_score": target["joint_risk_score"],
                "eligible_for_future_perturbation_design": True,
                "proposed_mode_if_separately_authorized":
                    "ONE_MODULE_AT_A_TIME_FAKE_Q8_GROUPWISE_SYMMETRIC",
            }],
            "allows_fake_quant_execution": False,
            "writes_quantized_weights": False,
            "creates_runtime_candidate": False,
            "allows_quantized_weight_writing": False,
            "allows_runtime_candidate_generation": False,
            "allows_runtime_wiring_or_promotion": False,
        }
        probe = {
            "schema": MODULE.PROBE_SCHEMA,
            "status": "TOKEN_CODE_BOUNDARY_OBSERVED_READ_ONLY",
            "activation_plan_sha256": "plan",
            "activation_gate_sha256": "gate",
            "runtime_manifest_sha256": "manifest",
            "corpus_sha256": "corpus",
            "case": case,
            "model_assets": [
                {"partition": "talker", "bytes": 8, "sha256": "asset"}
            ],
            "boundary": {
                "exact_generate_to_decode_match": True,
                "decode_was_intercepted": True,
                "returned_wave_samples": [0],
                "generated_codes": [{"time_steps": 2, "codebooks": 16}],
            },
            "allows_fake_quant_execution": False,
            "allows_quantized_weight_writing": False,
            "allows_runtime_candidate_generation": False,
            "allows_runtime_wiring_or_promotion": False,
            "mutates_weights": False,
            "decodes_audio": False,
            "writes_audio": False,
        }
        manifest = {"schema": MODULE.MANIFEST_SCHEMA}
        corpus = {"schema": MODULE.CORPUS_SCHEMA, "cases": [case]}
        thresholds = {"schema": MODULE.THRESHOLDS_SCHEMA}
        return policy, plan, activation_gate, scope, probe, manifest, corpus, thresholds, hashes

    def test_complete_chain_authorizes_only_one_smoke(self):
        report = MODULE.evaluate(*self.fixture())
        self.assertEqual(report["status"], MODULE.READY)
        self.assertTrue(report["allows_exactly_one_module_one_case_fake_q8_smoke"])
        self.assertFalse(report["allows_weight_mutation"])
        self.assertFalse(report["allows_runtime_candidate_generation"])

    def test_scope_or_probe_authority_drift_blocks(self):
        values = list(self.fixture())
        values[3]["allows_fake_quant_execution"] = True
        values[4]["writes_audio"] = True
        report = MODULE.evaluate(*values)
        self.assertEqual(report["status"], MODULE.BLOCKED)
        self.assertIn("scope_fake_execution_true", report["failures"])
        self.assertIn("probe_writes_audio", report["failures"])


if __name__ == "__main__":
    unittest.main()
