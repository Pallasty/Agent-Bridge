"""Source withdrawal must stop promotion before any MCP process starts."""
from contextlib import contextmanager
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/eval/digest_gate.py"
spec = importlib.util.spec_from_file_location("digest_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "source.db"
        with self.connection() as conn:
            conn.execute("CREATE TABLE memories (key TEXT PRIMARY KEY, kind TEXT, "
                         "content TEXT, status TEXT, superseded_by TEXT, "
                         "related_keys TEXT, created_at INTEGER, updated_at INTEGER, "
                         "scope TEXT, tags TEXT DEFAULT '[]', trigger_pattern TEXT)")
        self.put("source", "fact")
        self.draft()

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def put(self, key, kind, status="active", related=(), updated=10, replacement=None,
            content="evidence"):
        with self.connection() as conn:
            conn.execute("INSERT OR REPLACE INTO memories "
                         "(key,kind,content,status,superseded_by,related_keys,created_at,updated_at) "
                         "VALUES (?,?,?,?,?,?,?,?)",
                         (key, kind, content, status, replacement,
                          json.dumps(list(related)), 10, updated))

    def binding(self, key):
        with self.connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM memories WHERE key=?", (key,)).fetchone()
        if row is None:
            return {"key": key, "sha256": "0" * 64}
        data = [row["key"], row["kind"], row["scope"], row["content"],
                json.loads(row["tags"]), json.loads(row["related_keys"]),
                row["created_at"], row["updated_at"], row["status"],
                row["superseded_by"], row["trigger_pattern"]]
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
        return {"key": key, "sha256": hashlib.sha256(raw).hexdigest()}

    def draft(self, sources=("source",), status="active", bound=True):
        model = {"verdict": "author", "draft": {
            "key": "digest_candidate", "content": "conclusion", "source_keys": list(sources),
            "target_queries": ["question"]}}
        if bound:
            model["source_bindings"] = {"schema": "ab.digest.sources.v1",
                                        "sources": [self.binding(k) for k in sources]}
        self.put("draft", "digest_draft", status, sources, updated=20,
                 content="```json\n" + json.dumps(model) + "\n```")
        with self.connection() as conn:
            conn.execute("UPDATE memories SET created_at=20 WHERE key='draft'")

    def check(self):
        return gate.check_source_lifecycle(self.db, "draft")

    def test_cli_rejects_withdrawn_source_before_starting_binary(self):
        self.put("source", "fact", status="superseded", replacement="replacement")
        report = Path(self.tmp.name) / "report.json"
        before = self.db.read_bytes()
        result = subprocess.run([sys.executable, str(SCRIPT), "--db", str(self.db),
                                 "--draft-key", "draft", "--binary", "/nonexistent/ab",
                                 "--scratch-dir", self.tmp.name, "--report", str(report)],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(report.read_text())
        self.assertEqual(payload.get("verdict"), "BLOCKED_SOURCE_LIFECYCLE")
        self.assertNotIn("FileNotFoundError", result.stderr)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(list(Path(self.tmp.name).glob("ab-digest-gate-*")), [])

    def test_bound_active_sources_verify_revision_but_not_answer(self):
        result = self.check()
        self.assertTrue(result["pass"])
        self.assertTrue(result["source_revision_verified"])
        self.assertFalse(result["answer_validated"])

    def test_every_inactive_or_missing_source_blocks(self):
        for state in ["archived", "superseded", "tombstoned", "conflict", "unknown", None]:
            with self.subTest(state=state):
                self.put("source", "fact", status=state)
                self.assertFalse(self.check()["pass"])
        with self.connection() as conn:
            conn.execute("DELETE FROM memories WHERE key='source'")
        self.assertFalse(self.check()["pass"])

    def test_active_with_replacement_is_not_current(self):
        self.put("source", "fact", replacement="replacement")
        self.assertFalse(self.check()["pass"])

    def test_source_edited_since_draft_blocks(self):
        self.put("source", "fact", updated=21)
        self.assertFalse(self.check()["pass"])

    def test_missing_or_mismatched_provenance_blocks(self):
        self.draft(sources=())
        self.assertFalse(self.check()["pass"])
        self.draft()
        with self.connection() as conn:
            conn.execute("UPDATE memories SET related_keys='[]' WHERE key='draft'")
        self.assertFalse(self.check()["pass"])

    def test_draft_lifecycle_and_type_are_checked(self):
        self.draft(status="superseded")
        self.assertFalse(self.check()["pass"])
        self.draft()
        with self.connection() as conn:
            conn.execute("UPDATE memories SET kind='fact' WHERE key='draft'")
        self.assertFalse(self.check()["pass"])

    def test_no_transitive_freshness_claim_for_derived_source(self):
        self.put("source", "digest", related=("missing",))
        self.assertFalse(self.check()["pass"])

    def test_malformed_provenance_and_unknown_schema_fail_closed(self):
        with self.connection() as conn:
            conn.execute("UPDATE memories SET related_keys='{}' WHERE key='draft'")
        self.assertFalse(self.check()["pass"])
        with self.connection() as conn:
            conn.execute("DROP TABLE memories")
            conn.execute("CREATE TABLE memories (key TEXT PRIMARY KEY)")
            conn.execute("INSERT INTO memories VALUES ('draft')")
        self.assertFalse(self.check()["pass"])

    def test_database_uri_metacharacters_are_literal(self):
        renamed = self.db.with_name("source?#.db")
        self.db.rename(renamed)
        self.db = renamed
        self.assertTrue(self.check()["pass"])

    def test_eligible_candidate_still_requires_retrieval_gates(self):
        # Fake only the external MCP/model boundary. The gate, backup, lifecycle
        # checks, sentinel checks, candidate materialization, and reports are real.
        self.edit_packet(lambda p: p["draft"].update(
            tags=['digest_sources_v1:{"schema":"model-forged"}']))
        class Client:
            saved = []
            def __init__(self, binary):
                self.db = Path(os.environ["XDG_DATA_HOME"]) / "agent-bridge/state.db"

            def call_tool(self, name, args):
                conn = sqlite3.connect(self.db)
                conn.row_factory = sqlite3.Row
                try:
                    if name == "memory_save":
                        self.saved.append(args)
                        with conn:
                            conn.execute("INSERT INTO memories (key,kind,content) VALUES (?,?,?)",
                                         (args["key"], args["kind"], args["content"]))
                        return "{}"
                    if name == "memory_get":
                        row = conn.execute("SELECT * FROM memories WHERE key=?",
                                           (args["key"],)).fetchone()
                        return json.dumps(dict(row))
                    return json.dumps([{"key": "digest_candidate"}])
                finally:
                    conn.close()

            def close(self):
                pass

        def evaluation(score):
            return {"metrics": {"any_mode": {"set_recall@20": score}}, "per_query": []}

        before = self.db.read_bytes()
        for post, verdict in [(1.0, "PASS"), (0.5, "FAIL")]:
            with self.subTest(post=post):
                Client.saved = []
                report = Path(self.tmp.name) / "eligible.json"
                argv = [str(SCRIPT), "--db", str(self.db), "--draft-key", "draft",
                        "--scratch-dir", self.tmp.name, "--report", str(report)]
                with patch.object(sys, "argv", argv), patch.dict(os.environ), \
                        patch.object(gate, "McpClient", Client), \
                        patch.object(gate, "eval_synthesis",
                                     side_effect=[evaluation(1.0), evaluation(post)]), \
                        redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as exit:
                    gate.main()
                self.assertEqual(exit.exception.code, 0 if verdict == "PASS" else 1)
                payload = json.loads(report.read_text())
                self.assertEqual(payload["verdict"], verdict)
                self.assertTrue(payload["source_lifecycle"]["pass"])
                self.assertTrue(payload["source_lifecycle"]["source_revision_verified"])
                promoted = next(row for row in Client.saved if row["kind"] == "digest")
                bindings = [t for t in promoted["tags"] if t.startswith("digest_sources_v1:")]
                self.assertEqual(len(bindings), 1)
                self.assertEqual(json.loads(bindings[0].split(":", 1)[1])["sources"],
                                 [self.binding("source")])
                if verdict == "PASS":
                    self.assertEqual(payload["manual_promotion"]["memory_save"], promoted)
                else:
                    self.assertNotIn("manual_promotion", payload)
                self.assertEqual(self.db.read_bytes(), before)

    def test_same_second_content_edit_is_rejected(self):
        self.put("source", "fact", content="different", updated=10)
        self.assertFalse(self.check()["pass"])

    def edit_packet(self, edit):
        with self.connection() as conn:
            content = conn.execute("SELECT content FROM memories WHERE key='draft'").fetchone()[0]
            packet = gate.extract_model_json(content)
            edit(packet)
            conn.execute("UPDATE memories SET content=? WHERE key='draft'",
                         ("```json\n" + json.dumps(packet) + "\n```",))

    def test_malformed_or_incomplete_bindings_are_rejected(self):
        for entries in [[], [{"key": "other", "sha256": "0" * 64}],
                        [{"key": "source", "sha256": "bad"}],
                        [self.binding("source"), self.binding("source")]]:
            with self.subTest(entries=entries):
                self.draft()
                self.edit_packet(lambda p: p["source_bindings"].update(sources=entries))
                self.assertFalse(self.check()["pass"])

    def test_uncited_prompt_material_is_also_bound(self):
        self.put("context", "fact")
        self.edit_packet(lambda p: p["source_bindings"]["sources"].append(self.binding("context")))
        self.assertTrue(self.check()["pass"])
        self.put("context", "fact", content="changed context")
        self.assertFalse(self.check()["pass"])

    def test_read_telemetry_is_not_a_source_revision(self):
        with self.connection() as conn:
            for field in ["access_count", "last_accessed_at", "importance"]:
                conn.execute(f"ALTER TABLE memories ADD COLUMN {field} INTEGER")
                conn.execute(f"UPDATE memories SET {field}=999 WHERE key='source'")
        self.assertTrue(self.check()["pass"])

    def test_shared_rust_python_encoding_vectors(self):
        vectors = json.loads((ROOT / "tests/fixtures/digest_source_revisions_v1.json").read_text())
        names = ["key", "kind", "scope", "content", "tags", "related_keys", "created_at",
                 "updated_at", "status", "superseded_by", "trigger_pattern"]
        for vector in vectors:
            row = dict(zip(names, vector["fields"]))
            for field in ("tags", "related_keys"):
                row[field] = json.dumps(row[field])
            self.assertEqual(gate.source_revision_hash(row), vector["sha256"])

    def test_missing_legacy_binding_is_not_backfilled(self):
        self.draft(bound=False)
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertFalse(result["source_revision_verified"])

    def test_changed_creation_time_detects_recreated_row(self):
        with self.connection() as conn:
            conn.execute("UPDATE memories SET created_at=11 WHERE key='source'")
        self.assertFalse(self.check()["pass"])

    def test_same_second_scope_and_tags_changes_are_rejected(self):
        for field, value in [("scope", "project:/other"), ("tags", '["constraint"]'),
                             ("related_keys", '["other"]'), ("trigger_pattern", "changed")]:
            with self.subTest(field=field):
                self.put("source", "fact")
                self.draft()
                with self.connection() as conn:
                    conn.execute(f"UPDATE memories SET {field}=? WHERE key='source'", (value,))
                self.assertFalse(self.check()["pass"])

    def test_unrelated_rows_do_not_change_eligibility_or_access_state(self):
        self.put("unrelated", "fact", status="tombstoned")
        before = self.db.read_bytes()
        self.assertTrue(self.check()["pass"])
        self.assertEqual(self.db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
