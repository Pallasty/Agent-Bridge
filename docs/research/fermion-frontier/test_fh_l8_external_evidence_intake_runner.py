import copy
import importlib.util
import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent

SPEC = importlib.util.spec_from_file_location(
    "fh_l8_runner", HERE / "fh_l8_external_evidence_intake_runner.py"
)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)

SPEC = importlib.util.spec_from_file_location(
    "term_order_validator", HERE / "term_order_validator.py"
)
TERM_ORDER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(TERM_ORDER)


def load(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _registration(route: str, artifact_path: str, digest: str) -> dict:
    return {
        "artifact_path": artifact_path,
        "sha256": digest,
        "source_url": "https://example.invalid/export",
        "release_or_commit": "v1",
        "evidence_class": "PRIMARY_EXTERNAL_RAW_EXPORT",
        "provenance_attestation": "custody statement",
        "compiler_identity": "compiler",
        "compiler_version": "1",
        "compiler_configuration_sha256": "1" * 64,
        "environment_lock_sha256": "2" * 64,
    }


def _fixture_export(route: str, linear_size: int = 8, trotter_steps: int = 100) -> dict:
    terms_by_group = TERM_ORDER.expected_terms(linear_size)
    steps = []
    for step in range(trotter_steps):
        events = [
            {"group": group, "terms": list(terms_by_group[group])}
            for group in TERM_ORDER.GROUP_ORDER
        ]
        steps.append({"step": step, "events": events})
    return {
        "schema_version": 1,
        "route": route,
        "linear_size": linear_size,
        "trotter_steps": trotter_steps,
        "workload_fingerprint": "FH_L8_UoverT8_tT1_half_filling",
        "steps": steps,
    }


class ExternalEvidenceIntakeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.contract = load("fh_l8_external_evidence_intake_contract.json")

    def test_runner_empty_registry_stays_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            result = RUNNER.run(
                HERE / "fh_l8_external_evidence_registry_template.json",
                HERE,
                output,
            )
            saved = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIn("all five routes must be admitted before comparison", result["errors"])
        self.assertEqual(saved["status"], "INCOMPLETE")

    def test_runner_ready_for_comparison_with_all_routes_admitted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = copy.deepcopy(self.contract)
            registry["artifacts"] = {}
            for route in self.contract["required_routes"]:
                artifact_path = root / f"{route}.json"
                artifact = _fixture_export(route)
                artifact_path.write_text(json.dumps(artifact, sort_keys=True), encoding="utf-8")
                registry["artifacts"][route] = _registration(
                    route=route,
                    artifact_path=artifact_path.name,
                    digest=sha(artifact_path),
                )
            registry_path = root / "registry.json"
            registry_path.write_text(json.dumps(registry, sort_keys=True), encoding="utf-8")
            result = RUNNER.run(registry_path, root)

        self.assertEqual(result["status"], "READY_FOR_CROSS_ROUTE_COMPARISON")
        self.assertEqual(result["routes"]["native_fermions"]["status"], "ADMITTED")
        self.assertEqual(result["routes"]["dynamic_jw_local_grid_source_leading"]["status"], "ADMITTED")
        self.assertEqual(result["routes"]["dynamic_jw_local_grid_figure_candidate_fit"]["status"], "ADMITTED")
        self.assertEqual(result["routes"]["fsn_standard_figure_candidate_fit"]["status"], "ADMITTED")
        self.assertEqual(result["routes"]["fsn_ladder_figure_candidate_fit"]["status"], "ADMITTED")


if __name__ == "__main__":
    unittest.main()
