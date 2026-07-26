import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fh_l8_bootstrap", HERE / "fh_l8_external_evidence_intake_bootstrap.py"
)
BOOTSTRAP = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(BOOTSTRAP)


def load(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


class FHExternalEvidenceIntakeBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.contract = load("fh_l8_external_evidence_intake_contract.json")

    @staticmethod
    def _route_export(
        route: str,
        *,
        linear_size: int = 8,
        trotter_steps: int = 100,
        workload_fingerprint: str = "FH_L8_UoverT8_tT1_half_filling",
        steps=None,
    ) -> dict:
        if steps is None:
            steps = [{"step": i, "events": []} for i in range(trotter_steps)]
        return {
            "schema_version": 1,
            "route": route,
            "linear_size": linear_size,
            "trotter_steps": trotter_steps,
            "workload_fingerprint": workload_fingerprint,
            "steps": steps,
        }

    def test_find_candidates_identifies_valid_route_exports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native_path = root / "native.json"
            dynamic_path = root / "nested" / "dynamic.json"
            other_route_path = root / "other_route.json"
            malformed_path = root / "malformed.json"
            mismatch_path = root / "mismatch.json"
            empty_steps_path = root / "empty_steps.json"

            dynamic_path.parent.mkdir(parents=True, exist_ok=True)
            native_path.write_text(json.dumps(self._route_export("native_fermions")), encoding="utf-8")
            dynamic_path.write_text(
                json.dumps(self._route_export("dynamic_jw_local_grid_source_leading")),
                encoding="utf-8",
            )
            other_route_path.write_text(json.dumps(self._route_export("other_route")), encoding="utf-8")
            malformed_path.write_text("{\"route\": \"native_fermions\",", encoding="utf-8")
            mismatch_path.write_text(
                json.dumps(self._route_export("native_fermions", linear_size=10)),
                encoding="utf-8",
            )
            empty_steps_path.write_text(
                json.dumps(self._route_export("native_fermions", steps=[])),
                encoding="utf-8",
            )

            candidates = BOOTSTRAP.find_candidates(root, self.contract)

            self.assertIn("native_fermions", candidates)
            self.assertIn("dynamic_jw_local_grid_source_leading", candidates)
            self.assertNotIn("fsn_standard_figure_candidate_fit", candidates)
            self.assertEqual(len(candidates["native_fermions"]), 1)
            self.assertEqual(len(candidates["dynamic_jw_local_grid_source_leading"]), 1)
            self.assertIn(native_path, candidates["native_fermions"])
            self.assertIn(dynamic_path, candidates["dynamic_jw_local_grid_source_leading"])
            self.assertEqual(candidates.get("fsn_standard_figure_candidate_fit"), None)

    def test_parse_select_route_file_specs_rejects_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "native.json").write_text("{}", encoding="utf-8")

            parsed = BOOTSTRAP.parse_select_route_file_specs(
                ["native_fermions:native.json"],
                root,
                self.contract["required_routes"],
            )
            self.assertEqual(parsed["native_fermions"], root / "native.json")

            with self.assertRaises(ValueError) as context:
                BOOTSTRAP.parse_select_route_file_specs(
                    ["unknown_route:native.json"],
                    root,
                    self.contract["required_routes"],
                )
            self.assertIn("unknown route", str(context.exception))

            with self.assertRaises(ValueError) as context:
                BOOTSTRAP.parse_select_route_file_specs(
                    [f"native_fermions:../outside.json"],
                    root,
                    self.contract["required_routes"],
                )
            self.assertIn("must be under intake root", str(context.exception))

            with self.assertRaises(ValueError) as context:
                BOOTSTRAP.parse_select_route_file_specs(
                    ["native_fermions:not-found.json"],
                    root,
                    self.contract["required_routes"],
                )
            self.assertIn("does not exist", str(context.exception))

    def test_build_registry_populates_sketch_metadata_and_digests(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "export.json"
            export = self._route_export("native_fermions")
            path.write_text(json.dumps(export), encoding="utf-8")
            selection = {"native_fermions": path}
            contract_path = root / "contract.json"
            contract_path.write_text(json.dumps(self.contract), encoding="utf-8")

            registry = BOOTSTRAP.build_registry(contract_path, root, selection)

            self.assertEqual(registry["schema_version"], self.contract["schema_version"])
            self.assertEqual(registry["contract_id"], self.contract["contract_id"])
            self.assertEqual(registry["workload_fingerprint"], self.contract["workload_fingerprint"])
            self.assertIn("native_fermions", registry["artifacts"])
            registration = registry["artifacts"]["native_fermions"]
            self.assertEqual(registration["artifact_path"], "export.json")
            expected_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(registration["sha256"], expected_sha256)
            self.assertEqual(registration["source_url"], "")
            self.assertEqual(registration["route"], "native_fermions")

    def test_summarize_reports_status_for_each_required_route(self):
        candidates = {
            "native_fermions": [Path("a.json"), Path("b.json")],
            "dynamic_jw_local_grid_source_leading": [Path("c.json")],
        }
        registry = {
            "artifacts": {
                "native_fermions": {"artifact_path": "a.json"},
            }
        }
        report = BOOTSTRAP.summarize(candidates, self.contract, registry)
        self.assertIn("native_fermions: MULTIPLE [a.json, b.json]", report)
        self.assertIn("dynamic_jw_local_grid_source_leading: UNSELECTED c.json", report)
        self.assertIn("fsn_standard_figure_candidate_fit: MISSING", report)
        self.assertIn("fsn_ladder_figure_candidate_fit: MISSING", report)


if __name__ == "__main__":
    unittest.main()
