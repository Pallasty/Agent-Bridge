import copy
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "reference_qualification_validator",
    HERE / "reference_qualification_validator.py",
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VALIDATOR)


def load_json(name):
    with (HERE / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class ReferenceQualificationTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_json("reference_qualification_contract.json")
        self.template = load_json("reference_qualification_template.json")
        self.tempdir = tempfile.TemporaryDirectory()
        self.artifact_root = pathlib.Path(self.tempdir.name)
        self.ledger = copy.deepcopy(self.template)
        self.ledger["route_inputs"] = {
            "batch_fingerprints": ["route-batch-1"],
            "circuit_fingerprints": ["route-circuit-1"],
        }
        self.ledger["references"] = {
            observable: self._reference(observable, position)
            for position, observable in enumerate(
                self.contract["workload"]["observable_order"]
            )
        }

    def tearDown(self):
        self.tempdir.cleanup()

    def _reference(self, observable, position):
        artifact_name = f"{observable}-certificate.json"
        workload = self.contract["workload"]
        reference = {
            "observable": observable,
            "value": 0.5 if observable == "staggered_magnetization" else 0.125,
            "reference_target": self.contract["reference_target"],
            "hamiltonian_fingerprint": workload["hamiltonian_fingerprint"],
            "initial_state_fingerprint": workload["initial_state_fingerprint"],
            "evolution_fingerprint": workload["evolution_fingerprint"],
            "observable_definition_fingerprint": workload["observables"][observable][
                "definition_fingerprint"
            ],
            "boundary_condition_fingerprint": self.contract[
                "boundary_condition_fingerprint"
            ],
            "hamiltonian_convention_fingerprint": self.contract[
                "hamiltonian_convention_fingerprint"
            ],
            "reference_formula_fingerprint": "synthetic-independent-reference-formula-v1",
            "reference_term_sequence_fingerprint": (
                "synthetic-independent-reference-term-sequence-v1"
            ),
            "method_class": "exact_diagonalization",
            "method_description": "synthetic exhaustive diagonalization certificate",
            "solver_fingerprint": "synthetic-exact-solver-v1",
            "configuration_fingerprint": f"synthetic-config-{position}-v1",
            "certificate_checker_fingerprint": "synthetic-interval-checker-v1",
            "implementation_commit": "a" * 40,
            "environment_lock_sha256": "b" * 64,
            "theorem_and_assumptions_fingerprint": "synthetic-ed-theorem-v1",
            "rounding_mode": "directed_interval",
            "method_claims": {"full_target_sector_covered": True},
            "certificate_artifact": artifact_name,
            "certificate_sha256": "",
            "certificate_claim": "rigorous_absolute_error_bound",
            "total_abs_bound": 0.001,
            "error_decomposition": {
                "time_evolution": 0.0002,
                "representation_truncation": 0.0002,
                "floating_point": 0.0002,
                "observable_evaluation": 0.0002,
            },
            "independent_of_route_estimates": True,
            "independence_provenance": "computed without route batches or circuits",
            "input_fingerprints": [
                "independent-hamiltonian-input",
                f"independent-reference-config-{position}",
            ],
            "provenance": "synthetic validator fixture only",
        }
        self._write_certificate(reference)
        return reference

    def _write_certificate(self, reference):
        record_binding = {
            field: copy.deepcopy(reference[field])
            for field in VALIDATOR.CERTIFICATE_BOUND_FIELDS
        }
        certificate = {
            "schema_version": 1,
            "record_binding": record_binding,
            "method_specific_details": {
                "synthetic_fixture_only": True,
                "not_a_machine_checked_certificate": True,
            },
        }
        payload = json.dumps(
            certificate,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        (self.artifact_root / reference["certificate_artifact"]).write_bytes(payload)
        reference["certificate_sha256"] = hashlib.sha256(payload).hexdigest()

    def refresh_certificates(self, ledger):
        for reference in ledger["references"].values():
            self._write_certificate(reference)

    def assess(self, ledger=None, *, external_snapshot=True, **kwargs):
        selected_ledger = ledger if ledger is not None else self.ledger
        if external_snapshot and "route_input_fingerprints" not in kwargs:
            kwargs["route_input_fingerprints"] = copy.deepcopy(
                selected_ledger["route_inputs"]
            )
        return VALIDATOR.validate_ledger(
            self.contract,
            selected_ledger,
            artifact_root=self.artifact_root,
            **kwargs,
        )

    def test_empty_reference_template_is_unresolved(self):
        result = self.assess(self.template)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("every observable" in error for error in result["errors"]))

    def test_complete_synthetic_records_are_only_structurally_unverified(self):
        result = self.assess()
        self.assertEqual(result["status"], "STRUCTURALLY_COMPLETE_UNVERIFIED")
        self.assertEqual(
            result["structurally_complete_observables"],
            ["staggered_magnetization", "double_occupancy"],
        )
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(
            result["bound_budget_adequacy"],
            "NOT_ASSESSED_NO_CAMPAIGN_CONTRACT",
        )
        self.assertIs(result["ready_gate_eligible"], False)

    def test_binding_looking_record_without_external_snapshot_is_diagnostic(self):
        result = self.assess(external_snapshot=False)
        self.assertEqual(result["status"], "DIAGNOSTIC_ONLY")
        self.assertTrue(
            any("external route-input snapshot" in warning for warning in result["warnings"])
        )

    def test_partial_external_snapshot_is_not_enough_for_structural_state(self):
        result = self.assess(
            route_input_fingerprints={
                "batch_fingerprints": ["route-batch-1"],
                "circuit_fingerprints": [],
            }
        )
        self.assertEqual(result["status"], "DIAGNOSTIC_ONLY")
        self.assertTrue(
            any("complete external" in warning for warning in result["warnings"])
        )

    def test_qualified_bounded_state_is_not_reachable_or_allowed(self):
        result = self.assess()
        emitted_statuses = {result["status"]} | {
            reference["status"] for reference in result["references"].values()
        }
        self.assertTrue(emitted_statuses <= VALIDATOR.ALLOWED_STATUSES)
        self.assertNotIn("QUALIFIED_BOUNDED", VALIDATOR.ALLOWED_STATUSES)
        self.assertNotIn("QUALIFIED_BOUNDED", emitted_statuses)
        self.assertIs(result["ready_gate_eligible"], False)

    def test_arbitrary_blob_with_matching_sha_is_unresolved(self):
        bad = copy.deepcopy(self.ledger)
        reference = bad["references"]["double_occupancy"]
        payload = b"arbitrary bytes are not a certificate"
        (self.artifact_root / reference["certificate_artifact"]).write_bytes(payload)
        reference["certificate_sha256"] = hashlib.sha256(payload).hexdigest()
        result = self.assess(bad)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(
            any("strict UTF-8 JSON" in error for error in result["errors"])
        )

    def test_certificate_content_drift_with_matching_sha_is_unresolved(self):
        bad = copy.deepcopy(self.ledger)
        reference = bad["references"]["double_occupancy"]
        artifact = self.artifact_root / reference["certificate_artifact"]
        certificate = json.loads(artifact.read_text(encoding="utf-8"))
        certificate["record_binding"]["value"] = 0.375
        payload = json.dumps(
            certificate,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        artifact.write_bytes(payload)
        reference["certificate_sha256"] = hashlib.sha256(payload).hexdigest()
        result = self.assess(bad)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(
            any("does not match ledger" in error for error in result["errors"])
        )

    def test_certificate_boolean_cannot_equal_numeric_ledger_value(self):
        bad = copy.deepcopy(self.ledger)
        reference = bad["references"]["staggered_magnetization"]
        reference["value"] = 1.0
        self.refresh_certificates(bad)
        artifact = self.artifact_root / reference["certificate_artifact"]
        certificate = json.loads(artifact.read_text(encoding="utf-8"))
        certificate["record_binding"]["value"] = True
        payload = json.dumps(
            certificate,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        artifact.write_bytes(payload)
        reference["certificate_sha256"] = hashlib.sha256(payload).hexdigest()
        result = self.assess(bad)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(
            any("does not match ledger" in error for error in result["errors"])
        )

    def test_certificate_hash_drift_is_unresolved(self):
        bad = copy.deepcopy(self.ledger)
        bad["references"]["double_occupancy"]["certificate_sha256"] = "0" * 64
        result = self.assess(bad)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("does not match local artifact" in error for error in result["errors"]))

    def test_reference_identity_drift_is_invalid_schema(self):
        bad = copy.deepcopy(self.ledger)
        bad["references"]["staggered_magnetization"][
            "hamiltonian_fingerprint"
        ] = "different-workload"
        result = self.assess(bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("contract identity" in error for error in result["errors"]))

    def test_reference_value_must_stay_inside_physical_range(self):
        cases = {
            "staggered_magnetization": 1.01,
            "double_occupancy": -0.01,
        }
        for observable, value in cases.items():
            with self.subTest(observable=observable):
                bad = copy.deepcopy(self.ledger)
                bad["references"][observable]["value"] = value
                result = self.assess(bad)
                self.assertEqual(result["status"], "UNRESOLVED")
                self.assertTrue(
                    any("physical range" in error for error in result["errors"])
                )

    def test_missing_observable_is_unresolved(self):
        bad = copy.deepcopy(self.ledger)
        bad["references"].pop("double_occupancy")
        result = self.assess(bad)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("every observable" in error for error in result["errors"]))

    def test_error_decomposition_cannot_exceed_total_bound(self):
        bad = copy.deepcopy(self.ledger)
        bad["references"]["double_occupancy"]["error_decomposition"][
            "floating_point"
        ] = 0.01
        result = self.assess(bad)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("sum exceeds" in error for error in result["errors"]))

    def test_tiny_positive_component_cannot_fit_zero_total_bound(self):
        bad = copy.deepcopy(self.ledger)
        reference = bad["references"]["double_occupancy"]
        reference["total_abs_bound"] = 0.0
        reference["error_decomposition"] = {
            "time_evolution": 5e-13,
            "representation_truncation": 0.0,
            "floating_point": 0.0,
            "observable_evaluation": 0.0,
        }
        result = self.assess(bad)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("sum exceeds" in error for error in result["errors"]))

    def test_uncertified_tn_krylov_and_stochastic_methods_stay_diagnostic(self):
        for method_class in (
            "uncertified_tensor_network",
            "uncertified_krylov",
            "stochastic_estimator",
        ):
            with self.subTest(method_class=method_class):
                diagnostic = copy.deepcopy(self.ledger)
                for reference in diagnostic["references"].values():
                    reference["method_class"] = method_class
                self.refresh_certificates(diagnostic)
                result = self.assess(diagnostic)
                self.assertEqual(result["status"], "DIAGNOSTIC_ONLY")
                self.assertTrue(
                    all(
                        reference["status"] == "DIAGNOSTIC_ONLY"
                        for reference in result["references"].values()
                    )
                )

    def test_every_binding_method_accepts_only_its_required_true_claims(self):
        for method_class, required_claims in VALIDATOR.METHOD_CLAIM_REQUIREMENTS.items():
            with self.subTest(method_class=method_class):
                candidate = copy.deepcopy(self.ledger)
                for reference in candidate["references"].values():
                    reference["method_class"] = method_class
                    reference["method_claims"] = {
                        claim: True for claim in required_claims
                    }
                self.refresh_certificates(candidate)
                result = self.assess(candidate)
                self.assertEqual(
                    result["status"], "STRUCTURALLY_COMPLETE_UNVERIFIED"
                )

    def test_false_or_missing_method_claim_downgrades_each_binding_method(self):
        for method_class, required_claims in VALIDATOR.METHOD_CLAIM_REQUIREMENTS.items():
            for failed_claim in required_claims:
                with self.subTest(method_class=method_class, failed_claim=failed_claim):
                    candidate = copy.deepcopy(self.ledger)
                    claims = {claim: True for claim in required_claims}
                    claims[failed_claim] = False
                    for reference in candidate["references"].values():
                        reference["method_class"] = method_class
                        reference["method_claims"] = copy.deepcopy(claims)
                    self.refresh_certificates(candidate)
                    result = self.assess(candidate)
                    self.assertEqual(result["status"], "DIAGNOSTIC_ONLY")
                    self.assertTrue(
                        any(failed_claim in warning for warning in result["warnings"])
                    )

    def test_diagnostic_method_cannot_upgrade_with_forged_binding_claims(self):
        forged = copy.deepcopy(self.ledger)
        every_claim = {
            claim: True
            for claims in VALIDATOR.METHOD_CLAIM_REQUIREMENTS.values()
            for claim in claims
        }
        for reference in forged["references"].values():
            reference["method_class"] = "stochastic_estimator"
            reference["method_claims"] = copy.deepcopy(every_claim)
            reference["certificate_claim"] = "rigorous_absolute_error_bound"
            reference["rounding_mode"] = "directed_interval"
        self.refresh_certificates(forged)
        result = self.assess(forged)
        self.assertEqual(result["status"], "DIAGNOSTIC_ONLY")
        self.assertTrue(
            all(
                reference["status"] == "DIAGNOSTIC_ONLY"
                for reference in result["references"].values()
            )
        )

    def test_binding_method_requires_directed_interval_rounding(self):
        bad = copy.deepcopy(self.ledger)
        for reference in bad["references"].values():
            reference["rounding_mode"] = "round_to_nearest"
        self.refresh_certificates(bad)
        result = self.assess(bad)
        self.assertEqual(result["status"], "DIAGNOSTIC_ONLY")
        self.assertTrue(any("rounding_mode" in warning for warning in result["warnings"]))

    def test_binding_metadata_fields_are_structurally_required(self):
        cases = {
            "certificate_checker_fingerprint": None,
            "implementation_commit": "main",
            "environment_lock_sha256": "not-a-sha256",
            "theorem_and_assumptions_fingerprint": "",
            "reference_formula_fingerprint": "",
            "reference_term_sequence_fingerprint": "",
        }
        for field, replacement in cases.items():
            with self.subTest(field=field):
                bad = copy.deepcopy(self.ledger)
                reference = bad["references"]["double_occupancy"]
                if replacement is None:
                    reference.pop(field)
                else:
                    reference[field] = replacement
                result = self.assess(bad)
                self.assertEqual(result["status"], "UNRESOLVED")

    def test_claimed_independence_cannot_reuse_declared_route_input(self):
        bad = copy.deepcopy(self.ledger)
        bad["references"]["double_occupancy"]["input_fingerprints"].append(
            "route-circuit-1"
        )
        self.refresh_certificates(bad)
        result = self.assess(bad)
        self.assertEqual(result["status"], "DIAGNOSTIC_ONLY")
        self.assertTrue(any("reuses route" in warning for warning in result["warnings"]))

    def test_external_route_snapshot_catches_input_hidden_by_ledger(self):
        bad = copy.deepcopy(self.ledger)
        bad["route_inputs"] = {
            "batch_fingerprints": [],
            "circuit_fingerprints": [],
        }
        bad["references"]["staggered_magnetization"]["input_fingerprints"].append(
            "external-route-batch"
        )
        self.refresh_certificates(bad)
        result = self.assess(
            bad,
            route_input_fingerprints={
                "batch_fingerprints": ["external-route-batch"],
                "circuit_fingerprints": [],
            },
        )
        self.assertEqual(result["status"], "DIAGNOSTIC_ONLY")
        self.assertTrue(any("external-route-batch" in warning for warning in result["warnings"]))

    def test_certificate_path_cannot_escape_artifact_root(self):
        bad = copy.deepcopy(self.ledger)
        bad["references"]["double_occupancy"]["certificate_artifact"] = "../outside"
        result = self.assess(bad)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("safe relative path" in error for error in result["errors"]))

    def test_contract_workload_drift_is_invalid_schema(self):
        bad_contract = copy.deepcopy(self.contract)
        bad_contract["workload"]["target_R"] = 200
        result = VALIDATOR.validate_ledger(
            bad_contract, self.ledger, artifact_root=self.artifact_root
        )
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(
            any("convergence_workload_policy" in error for error in result["errors"])
        )

    def test_contract_workload_comparison_is_type_exact(self):
        bad_contract = copy.deepcopy(self.contract)
        bad_contract["workload"]["observables"]["double_occupancy"][
            "physical_range"
        ] = [False, True]
        result = VALIDATOR.validate_ledger(
            bad_contract, self.ledger, artifact_root=self.artifact_root
        )
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(
            any("convergence_workload_policy" in error for error in result["errors"])
        )

    def test_boolean_schema_versions_are_rejected(self):
        bad_contract = copy.deepcopy(self.contract)
        bad_contract["schema_version"] = True
        self.assertTrue(VALIDATOR.validate_contract(bad_contract))
        self.assertEqual(
            VALIDATOR.validate_ledger(bad_contract, self.ledger)["status"],
            "INVALID_SCHEMA",
        )

        bad_ledger = copy.deepcopy(self.ledger)
        bad_ledger["schema_version"] = True
        self.assertEqual(self.assess(bad_ledger)["status"], "INVALID_SCHEMA")

    def test_non_object_top_levels_fail_closed(self):
        for value in (None, [], "not-an-object"):
            with self.subTest(value=value):
                self.assertTrue(VALIDATOR.validate_contract(value))
                self.assertEqual(
                    VALIDATOR.validate_ledger(value, self.ledger)["status"],
                    "INVALID_SCHEMA",
                )
                self.assertEqual(
                    VALIDATOR.validate_ledger(self.contract, value)["status"],
                    "INVALID_SCHEMA",
                )

    def test_huge_numeric_value_fails_closed(self):
        bad = copy.deepcopy(self.ledger)
        bad["references"]["double_occupancy"]["total_abs_bound"] = 10**10000
        result = self.assess(bad)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("must be finite" in error for error in result["errors"]))

    def test_cli_structurally_complete_state_still_exits_nonzero(self):
        ledger_path = self.artifact_root / "ledger.json"
        route_inputs_path = self.artifact_root / "route-inputs.json"
        ledger_path.write_text(json.dumps(self.ledger), encoding="utf-8")
        route_inputs_path.write_text(
            json.dumps(self.ledger["route_inputs"]), encoding="utf-8"
        )
        process = subprocess.run(
            [
                sys.executable,
                str(HERE / "reference_qualification_validator.py"),
                "--contract",
                str(HERE / "reference_qualification_contract.json"),
                "--ledger",
                str(ledger_path),
                "--artifact-root",
                str(self.artifact_root),
                "--route-inputs",
                str(route_inputs_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 1)
        result = json.loads(process.stdout)
        self.assertEqual(result["status"], "STRUCTURALLY_COMPLETE_UNVERIFIED")
        self.assertIs(result["ready_gate_eligible"], False)


if __name__ == "__main__":
    unittest.main()
