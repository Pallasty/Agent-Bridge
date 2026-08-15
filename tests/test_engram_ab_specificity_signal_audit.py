from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/eval/engram_ab_specificity_signal_audit.py"
SPEC = importlib.util.spec_from_file_location("engram_specificity_audit", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE memories (
                key TEXT PRIMARY KEY,
                scope TEXT,
                status TEXT NOT NULL
            );
            CREATE TABLE memory_edges (
                from_key TEXT NOT NULL,
                to_key TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                weight REAL NOT NULL
            );
            CREATE TABLE memory_coactivation (
                key_a TEXT NOT NULL,
                key_b TEXT NOT NULL,
                count INTEGER NOT NULL,
                consolidated INTEGER NOT NULL,
                last_at INTEGER NOT NULL
            );
            INSERT INTO memories VALUES
                ('target', 'project:/host/agent-bridge', 'active'),
                ('same_a', 'project:/other/agent-bridge', 'active'),
                ('same_b', 'project:/other/agent-bridge', 'active'),
                ('cross', 'project:/host/other', 'active');
            """
        )
        connection.commit()
    finally:
        connection.close()


class SpecificitySignalAuditTests(unittest.TestCase):
    def test_no_go_when_only_noisy_unconsolidated_signal_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.db"
            create_db(db)
            connection = sqlite3.connect(db)
            try:
                connection.executescript(
                    """
                    INSERT INTO memory_edges VALUES
                        ('target', 'same_a', 'evolved', 1.0),
                        ('target', 'cross', 'evolved', 1.0),
                        ('target', 'same_b', 'relates', 1.0);
                    INSERT INTO memory_coactivation VALUES
                        ('target', 'same_a', 1, 0, 100);
                    """
                )
                connection.commit()
            finally:
                connection.close()

            before = file_digest(db)
            result = MODULE.audit_snapshot(db, "target", "agent-bridge")
            self.assertEqual(
                result["status"], "NO_GO_INSUFFICIENT_TRUSTED_CLUSTER_SIGNAL"
            )
            self.assertEqual(result["metrics"]["trusted_cluster_degree"], 0)
            self.assertEqual(result["metrics"]["coactivation_max_count"], 1)
            self.assertEqual(
                result["metrics"]["consolidated_coactivation_degree"], 0
            )
            self.assertEqual(result["metrics"]["evolved_scope_purity"], 0.5)
            self.assertEqual(before, file_digest(db))

    def test_ready_when_crystallized_cluster_degree_reaches_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.db"
            create_db(db)
            connection = sqlite3.connect(db)
            try:
                connection.executescript(
                    """
                    INSERT INTO memory_edges VALUES
                        ('target', 'same_a', 'cofires', 1.0),
                        ('target', 'same_b', 'co_referenced', 1.0);
                    """
                )
                connection.commit()
            finally:
                connection.close()

            result = MODULE.audit_snapshot(db, "target", "agent-bridge")
            self.assertEqual(result["status"], "READY_FOR_OFFLINE_CLUSTER_SCOUT")
            self.assertEqual(result["metrics"]["trusted_cluster_degree"], 2)

    def test_ready_when_consolidated_coactivation_degree_reaches_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.db"
            create_db(db)
            connection = sqlite3.connect(db)
            try:
                connection.executescript(
                    """
                    INSERT INTO memory_coactivation VALUES
                        ('target', 'same_a', 5, 1, 100),
                        ('target', 'same_b', 6, 1, 101);
                    """
                )
                connection.commit()
            finally:
                connection.close()

            result = MODULE.audit_snapshot(db, "target", "agent-bridge")
            self.assertEqual(result["status"], "READY_FOR_OFFLINE_CLUSTER_SCOUT")
            self.assertEqual(
                result["metrics"]["consolidated_coactivation_degree"], 2
            )

    def test_missing_target_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.db"
            create_db(db)
            with self.assertRaisesRegex(MODULE.AuditError, "target key is absent"):
                MODULE.audit_snapshot(db, "missing", "agent-bridge")


if __name__ == "__main__":
    unittest.main()
