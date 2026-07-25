import importlib.util
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent

SPEC = importlib.util.spec_from_file_location(
    "bridge", HERE / "fh_l8_evidence_orchestrator_bridge.py"
)
BRIDGE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(BRIDGE)


class EvidenceOrchestratorBridgeTests(unittest.TestCase):
    def test_bridge_runs_with_empty_registry(self) -> None:
        result = BRIDGE.evaluate_bridge(
            HERE / "fh_l8_external_evidence_registry_template.json",
            HERE,
            HERE / "evidence_manifest_source_snapshot.json",
        )
        self.assertEqual(result["intake"]["status"], "INCOMPLETE")
        self.assertIn("all five routes must be admitted before comparison", result["intake"]["errors"][0])
        self.assertEqual(result["evidence"]["status"], "UNRESOLVED")
        self.assertEqual(result["cross_route_snapshot"]["status"], "UNRESOLVED")
        self.assertEqual(
            result["summary"],
            {
                "intake_status": "INCOMPLETE",
                "evidence_status": "UNRESOLVED",
                "cross_route_status": "UNRESOLVED",
            },
        )
        self.assertIn("next_actions", result)
        self.assertGreaterEqual(len(result["next_actions"]), 10)
        self.assertEqual(result["next_actions"][0]["priority"], "1")
        self.assertTrue(
            any(
                action["area"] == "intake" and action["route"] == "native_fermions"
                for action in result["next_actions"]
            )
        )


if __name__ == "__main__":
    unittest.main()
