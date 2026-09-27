"""Offline record recovery tests; fixture text files are not media-quality evidence."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve().parents[1] / "skills/film-production/scripts/project.py"
SPEC = importlib.util.spec_from_file_location("film_project", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
project = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project)


def save(root: Path, name: str, value: dict[str, Any]) -> None:
    (root / name).write_text(json.dumps(value), encoding="utf-8")


def read(root: Path, name: str) -> dict[str, Any]:
    return json.loads((root / name).read_text(encoding="utf-8"))


def artifact(root: Path, name: str, content: str) -> dict[str, str]:
    data = content.encode()
    (root / name).write_bytes(data)
    return {"path": name, "sha256": hashlib.sha256(data).hexdigest()}


class FilmRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "film"
        project.init_project(self.root, "film-demo")

    def fixture(self) -> None:
        brief = read(self.root, "brief.json")
        brief["script"] = {"revision": "v3", **artifact(self.root, "script.txt", "原创虚构结局")}
        save(self.root, "brief.json", brief)
        save(self.root, "bible.json", {
            "schema_version": 1, "project_id": "film-demo", "entities": [],
            "assets": [{"id": "hero", "version": "v2", "approved": True,
                        "rights": "original_fixture", **artifact(self.root, "hero.txt", "自有占位") }],
        })
        shots = [
            {"id": "s1", "script_revision": "v3", "asset_versions": {"hero": "v2"},
             "selected_generation_id": "g1", "source_refs": [], "intent": "未来的结局"},
            {"id": "s2", "script_revision": "v3", "asset_versions": {"hero": "v2"},
             "selected_generation_id": None, "source_refs": [], "intent": "铺垫"},
        ]
        save(self.root, "shots.json", {"schema_version": 1, "project_id": "film-demo", "shots": shots})
        takes = []
        for gid, sid, review in [("g1", "s1", "accepted"), ("g2", "s1", "rejected"),
                                  ("g3", "s2", "unreviewed")]:
            takes.append({"id": gid, "shot_id": sid, "status": "generated",
                          "script_revision": "v3", "asset_versions": {"hero": "v2"},
                          "review": {"decision": review, "reason": "fixture only"},
                          "output": artifact(self.root, f"{gid}.txt", gid)})
        save(self.root, "generations.json", {
            "schema_version": 1, "project_id": "film-demo", "generations": takes,
        })

    def test_init_is_empty_and_refuses_overwrite(self) -> None:
        self.assertEqual(project.recover(self.root)["status"], "planning")
        with self.assertRaises(FileExistsError):
            project.init_project(self.root, "other")
        self.assertEqual(read(self.root, "brief.json")["project_id"], "film-demo")

    def test_recovery_keeps_selected_old_take_and_identifies_pending_review(self) -> None:
        self.fixture()
        result = project.recover(self.root)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["selected"], {"s1": "g1"})
        self.assertIn({"shot_id": "s2", "action": "review_candidates"}, result["next_actions"])

    def test_asset_change_invalidates_selection_and_old_handoff(self) -> None:
        self.fixture()
        project.checkpoint(self.root)
        self.assertTrue(project.recover(self.root)["handoff_matches_files"])
        bible = read(self.root, "bible.json")
        bible["assets"][0]["version"] = "v3"
        save(self.root, "bible.json", bible)
        result = project.recover(self.root)
        self.assertFalse(result["handoff_matches_files"])
        self.assertNotIn("s1", result["selected"])
        self.assertTrue(any("asset version" in issue for issue in result["errors"]))

    def test_tampered_selected_output_fails(self) -> None:
        self.fixture()
        handoff = read(self.root, "handoff.json")
        handoff["summary"] = "Selected s1; s2 needs review"
        save(self.root, "handoff.json", handoff)
        project.checkpoint(self.root)
        (self.root / "g1.txt").write_text("replaced", encoding="utf-8")
        result = project.recover(self.root)
        self.assertNotIn("s1", result["selected"])
        self.assertTrue(any("hash" in issue for issue in result["errors"]))
        self.assertIsNone(result["handoff_summary"])

    def test_missing_candidate_is_a_blocker_before_review(self) -> None:
        self.fixture()
        (self.root / "g3.txt").unlink()
        result = project.recover(self.root)
        self.assertIn({"shot_id": "s2", "action": "reconcile_records"}, result["next_actions"])
        self.assertTrue(any("missing artifact" in issue for issue in result["errors"]))

    def test_script_change_invalidates_selected_take(self) -> None:
        self.fixture()
        brief = read(self.root, "brief.json")
        brief["script"]["revision"] = "v4"
        save(self.root, "brief.json", brief)
        result = project.recover(self.root)
        self.assertEqual(result["selected"], {})
        self.assertTrue(any("script revision" in issue for issue in result["errors"]))

    def test_generated_but_unreviewed_take_is_not_selected(self) -> None:
        self.fixture()
        shots = read(self.root, "shots.json")
        shots["shots"][1]["selected_generation_id"] = "g3"
        save(self.root, "shots.json", shots)
        self.assertTrue(any("accepted" in issue for issue in project.recover(self.root)["errors"]))

    def test_fiction_accepts_climax_but_documentary_requires_sources(self) -> None:
        self.fixture()
        self.assertEqual(project.recover(self.root)["errors"], [])
        brief = read(self.root, "brief.json")
        brief["source_mode"] = "documentary"
        save(self.root, "brief.json", brief)
        self.assertTrue(any("source evidence" in issue for issue in project.recover(self.root)["errors"]))

    def test_artifact_paths_cannot_escape_project(self) -> None:
        self.fixture()
        bible = read(self.root, "bible.json")
        bible["assets"][0]["path"] = "../outside.txt"
        save(self.root, "bible.json", bible)
        self.assertTrue(any("outside" in issue for issue in project.recover(self.root)["errors"]))

    def test_cross_project_handoff_is_rejected(self) -> None:
        handoff = read(self.root, "handoff.json")
        handoff["project_id"] = "other-film"
        save(self.root, "handoff.json", handoff)
        with self.assertRaisesRegex(ValueError, "project_id"):
            project.recover(self.root)


if __name__ == "__main__":
    unittest.main()
