import copy
import importlib.util
import json
import math
import pathlib
import tempfile
import unittest


HERE = pathlib.Path(__file__).resolve().parent
MODULE_PATH = HERE / "fb_s1_same_u_tdhf_residual_benchmark.py"
INITIAL_CONTRACT_PATH = HERE / "fb_s1_same_u_tdhf_residual_contract.json"
AMENDED_CONTRACT_PATH = HERE / "fb_s1a_same_u_tdhf_residual_contract.json"
SPEC = importlib.util.spec_from_file_location("fb_s1_benchmark", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FbS1ProtocolTests(unittest.TestCase):
    def test_frozen_amendment_and_source_bindings_load(self):
        contract = MODULE.load_contract(AMENDED_CONTRACT_PATH)
        self.assertEqual(contract["analysis_class"], "POST_REVEAL_AMENDED_EXPLORATORY")
        self.assertFalse(contract["confirmation_authority"])
        self.assertEqual(contract["models"]["candidate_state_dimension"], 5)
        self.assertEqual(
            MODULE.sha256_path(AMENDED_CONTRACT_PATH),
            "363c18d668ce8ea7eb3896ccd7c72ab39fdbf3cbce6509604eb625d2ea139d0b",
        )

    def test_any_contract_byte_drift_is_rejected(self):
        original = json.loads(AMENDED_CONTRACT_PATH.read_text(encoding="utf-8"))
        mutations = []
        overlap = copy.deepcopy(original)
        overlap["physics"]["test_u"][0] = overlap["physics"]["train_u"][0]
        mutations.append(overlap)
        leakage = copy.deepcopy(original)
        leakage["split"]["future_values_visible_to_fit"] = True
        mutations.append(leakage)
        claim = copy.deepcopy(original)
        claim["nonclaims"]["runtime_authority"] = True
        mutations.append(claim)
        threshold = copy.deepcopy(original)
        threshold["success"]["minimum_nrmse_improvement_fraction"] = -1.0
        mutations.append(threshold)
        duplicate_seed = copy.deepcopy(original)
        duplicate_seed["models"]["candidate_seeds"] = [11, 11, 47]
        mutations.append(duplicate_seed)
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with tempfile.TemporaryDirectory() as directory:
                    path = pathlib.Path(directory) / "contract.json"
                    path.write_text(json.dumps(mutation), encoding="utf-8")
                    with self.assertRaisesRegex(MODULE.BenchmarkError, "frozen contract hash"):
                        MODULE.load_contract(path)

    def test_initial_dimension_eight_protocol_is_statically_rejected(self):
        self.assertEqual(
            MODULE.candidate_inventory(8),
            {"parameters": 54, "state": 8, "ops": 114},
        )
        with self.assertRaisesRegex(MODULE.BenchmarkError, "statically violates budget"):
            MODULE.run(INITIAL_CONTRACT_PATH)

    def test_budget_derived_dimension_five_inventory(self):
        self.assertEqual(
            MODULE.candidate_inventory(5),
            {"parameters": 36, "state": 5, "ops": 72},
        )
        self.assertLessEqual(MODULE.candidate_inventory(5)["parameters"], 40)
        self.assertGreater(MODULE.candidate_inventory(6)["parameters"], 40)

    def test_fixed_weights_are_precomputed_and_deterministic(self):
        first = MODULE.fixed_reservoir_weights(11, 5)
        second = MODULE.fixed_reservoir_weights(11, 5)
        self.assertEqual(first, second)
        self.assertEqual(len(first["input"]), 5)
        self.assertTrue(all(len(row) == 2 for row in first["input"]))

    def test_future_suffix_cannot_change_scaling_or_fitted_weights(self):
        prefix, warmup = 48, 8
        sequences = [
            [
                [
                    math.sin(0.13 * step + case),
                    math.cos(0.17 * step - 0.3 * case),
                ]
                for step in range(61)
            ]
            for case in range(3)
        ]
        mutated = copy.deepcopy(sequences)
        for sequence in mutated:
            for step in range(prefix + 1, len(sequence)):
                sequence[step] = [1e9 + step, -1e9 - step]
        self.assertEqual(
            MODULE.scales(sequences, prefix),
            MODULE.scales(mutated, prefix),
        )
        for name in ("AFFINE_DMD", "RIDGE_VAR4", "PRONY_AR8"):
            left = MODULE.fit_direct(name, sequences, prefix, warmup, 1e-6)
            right = MODULE.fit_direct(name, mutated, prefix, warmup, 1e-6)
            self.assertEqual(left["weights"], right["weights"])
            self.assertEqual(left["fit_rows"], 120)
        left = MODULE.fit_reservoir(sequences, prefix, warmup, 1e-6, 11, 5)
        right = MODULE.fit_reservoir(mutated, prefix, warmup, 1e-6, 11, 5)
        self.assertEqual(left["weights"], right["weights"])
        self.assertEqual(left["fit_rows"], 120)

    def test_decision_truth_table_is_fail_closed(self):
        cases = {
            (False, True, False, True): "INVALID_PHYSICS_CONSTRAINTS",
            (True, False, False, True): "INVALID_BUDGET_ACCOUNTING",
            (True, True, True, True): "NO_GO_DIRECT_REDUCTION",
            (True, True, False, False): "NO_GO_KPI",
            (True, True, False, True): "GO_BIOCORTEX_MOTIVATED_PROXY",
        }
        for inputs, expected in cases.items():
            with self.subTest(inputs=inputs):
                self.assertEqual(MODULE.classify_status(*inputs), expected)

    def test_non_finite_results_are_rejected(self):
        with self.assertRaisesRegex(MODULE.BenchmarkError, "non-finite"):
            MODULE.assert_finite_tree({"metric": float("nan")})


if __name__ == "__main__":
    unittest.main()
