#!/usr/bin/env bash
# Offline fixtures for the temporal-truth and retrieval-causality audits.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPORAL="$ROOT_DIR/scripts/eval/temporal_truth_drift_audit.py"
TELEMETRY="$ROOT_DIR/scripts/eval/retrieval_telemetry_causality_audit.py"
AS_OF=2000000000

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-memory-evidence-audits-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

python3 - "$tmpdir" "$AS_OF" <<'PY'
import json
import shutil
import sqlite3
import sys
from pathlib import Path

root = Path(sys.argv[1])
as_of = int(sys.argv[2])
day = 86_400


def make_temporal(path):
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE memories (
          key TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          tags TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL,
          last_accessed_at INTEGER NOT NULL,
          access_count INTEGER NOT NULL,
          status TEXT NOT NULL,
          superseded_by TEXT,
          dedupe_key TEXT
        );
        CREATE TABLE memory_edges (
          from_key TEXT NOT NULL,
          to_key TEXT NOT NULL,
          edge_type TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        """
    )

    def memory(
        key,
        *,
        kind="decision",
        tags=None,
        age_days=1,
        last_access_delta=5_000,
        status="active",
        superseded_by=None,
        dedupe_key=None,
        raw_tags=None,
    ):
        ts = as_of - age_days * day
        con.execute(
            "INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                key,
                kind,
                raw_tags if raw_tags is not None else json.dumps(tags or []),
                ts,
                ts,
                as_of - last_access_delta,
                2,
                status,
                superseded_by,
                dedupe_key,
            ),
        )

    memory("status_mismatch", superseded_by="winner")
    memory("edge_target", last_access_delta=500)
    memory("edge_winner")
    memory("invalid_target", last_access_delta=500)
    memory("invalidator")
    memory("declared_old")
    memory("declared_source", tags=["continuity_supersedes:declared_old"])
    memory("corrected_target")
    memory("correction:corrected_target:fixture", kind="feedback")
    memory("corrected_valid")
    memory("correction:corrected_valid:fixture", kind="feedback")
    memory(
        "stale_state",
        tags=[
            "continuity_actionability:must_block",
            "continuity_freshness_policy:version_bound",
            "continuity_role:state",
        ],
        age_days=20,
    )
    memory(
        "old_constraint",
        tags=[
            "continuity_actionability:must_block",
            "continuity_freshness_policy:project_phase_bound",
            "continuity_role:constraint",
        ],
        age_days=50,
    )
    memory("dup_one", dedupe_key="fixture-duplicate")
    memory("dup_two", dedupe_key="fixture-duplicate")
    memory("bad_tags", raw_tags="{not-json")
    memory(
        "retired_old",
        status="superseded",
        superseded_by="retired_winner",
    )
    memory("retired_winner")

    edge_ts = as_of - 1_000
    con.executemany(
        "INSERT INTO memory_edges VALUES (?,?,?,?)",
        [
            ("edge_winner", "edge_target", "supersedes", edge_ts),
            ("invalidator", "invalid_target", "invalidates", edge_ts),
            (
                "correction:corrected_valid:fixture",
                "corrected_valid",
                "corrects",
                edge_ts,
            ),
            ("retired_winner", "retired_old", "supersedes", edge_ts),
        ],
    )
    con.commit()
    con.close()


def make_telemetry(path, labelled):
    con = sqlite3.connect(path)
    traffic = ", traffic_class TEXT" if labelled else ""
    con.executescript(
        f"""
        CREATE TABLE memories (key TEXT PRIMARY KEY, status TEXT NOT NULL);
        CREATE TABLE retrieval_surfacing (
          memory_key TEXT NOT NULL,
          mode TEXT NOT NULL,
          rank INTEGER NOT NULL,
          surfaced_at INTEGER NOT NULL,
          used_at INTEGER,
          consumed_at INTEGER
          {traffic}
        );
        """
    )

    def surfacing(key, mode, rank, age, used, traffic_class=None):
        con.execute("INSERT OR IGNORE INTO memories VALUES (?, 'active')", (key,))
        values = [key, mode, rank, as_of - age, as_of - age + 60 if used else None, None]
        if labelled:
            values.append(traffic_class)
        placeholders = ",".join("?" for _ in values)
        con.execute(f"INSERT INTO retrieval_surfacing VALUES ({placeholders})", values)

    if not labelled:
        surfacing("u_decay", "fts", 0, 30_000, False)
        surfacing("u_decay", "fts", 1, 29_000, False)
        surfacing("u_used", "semantic", 2, 28_000, True)
        surfacing("u_young", "hybrid", 3, 1_000, False)
        surfacing("u_boot", "bootstrap", 0, 30_000, True)
        surfacing("u_boot", "bootstrap", 10, day + 30_000, True)
        surfacing("u_boot", "bootstrap", 20, 2 * day + 30_000, True)
    else:
        surfacing("l_eval_decay", "fts", 0, 30_000, False, "eval")
        surfacing("l_eval_decay", "fts", 1, 29_000, False, "eval")
        surfacing("l_org_decay", "hybrid", 0, 30_000, False, "organic")
        surfacing("l_org_decay", "hybrid", 1, 29_000, False, "organic")
        surfacing("l_mixed_used", "semantic", 0, 30_000, True, "eval")
        surfacing("l_mixed_used", "semantic", 1, 29_000, False, "organic")
        surfacing("l_org_used", "fts", 2, 28_000, True, "organic")
        surfacing("l_boot", "bootstrap", 0, 30_000, True, "bootstrap")

    con.commit()
    con.close()


make_temporal(root / "temporal.db")
make_telemetry(root / "telemetry-unlabelled.db", labelled=False)
make_telemetry(root / "telemetry-labelled.db", labelled=True)
shutil.copy2(root / "telemetry-labelled.db", root / "telemetry-partial.db")
con = sqlite3.connect(root / "telemetry-partial.db")
con.execute(
    "UPDATE retrieval_surfacing SET traffic_class=NULL "
    "WHERE memory_key='l_org_decay' AND rank=0"
)
con.commit()
con.close()

con = sqlite3.connect(root / "bad-schema.db")
con.execute("CREATE TABLE memories (key TEXT PRIMARY KEY)")
con.commit()
con.close()
PY

python3 "$TEMPORAL" \
  --db "$tmpdir/temporal.db" \
  --as-of "$AS_OF" \
  --json > "$tmpdir/temporal.json"

python3 "$TELEMETRY" \
  --db "$tmpdir/telemetry-unlabelled.db" \
  --as-of "$AS_OF" \
  --json > "$tmpdir/telemetry-unlabelled.json"

python3 "$TELEMETRY" \
  --db "$tmpdir/telemetry-labelled.db" \
  --as-of "$AS_OF" \
  --json > "$tmpdir/telemetry-labelled.json"

python3 "$TELEMETRY" \
  --db "$tmpdir/telemetry-partial.db" \
  --as-of "$AS_OF" \
  --json > "$tmpdir/telemetry-partial.json"

python3 - "$tmpdir" <<'PY'
import json
import sqlite3
import sys
from pathlib import Path

root = Path(sys.argv[1])


def packet(name):
    return json.loads((root / name).read_text(encoding="utf-8"))


temporal = packet("temporal.json")
assert temporal["schema"] == "agent_bridge.temporal_truth_drift_audit.v0"
assert temporal["verdict"] == "REVIEW_REQUIRED"
assert temporal["semantic_truth_judgment"] is False
assert temporal["raw_memory_content_read"] is False
assert temporal["raw_identifiers_in_output"] is False
assert temporal["signals"] == {
    "active_corrected_target": 1,
    "active_correction_without_corrects_edge": 1,
    "active_declared_supersedes_target": 1,
    "active_duplicate_dedupe_key": 2,
    "active_target_of_invalidates_edge": 1,
    "active_target_of_supersedes_edge": 1,
    "active_with_superseded_by": 1,
    "aging_constraint_review": 1,
    "aging_freshness_bound_state": 1,
    "declared_supersedes_missing_edge": 1,
    "malformed_tags": 1,
}
assert temporal["signal_details"]["active_duplicate_dedupe_groups"] == 1
assert temporal["signal_details"]["post_supersede_or_invalidate_access_rows"] == 2
assert temporal["signal_details"]["freshness_bound_age_bands"] == {"d14-29": 1}
assert temporal["signal_details"]["unique_actionable_candidate_rows"] == 10
assert temporal["no_write_invariant"]["passed"] is True

unlabelled = packet("telemetry-unlabelled.json")
assert unlabelled["schema"] == "agent_bridge.retrieval_telemetry_causality_audit.v0"
assert unlabelled["verdict"] == "BLOCKED_NEEDS_TRAFFIC_CLASS"
assert unlabelled["query_text_read"] is False
assert unlabelled["query_text_heuristics_allowed"] is False
assert unlabelled["observability"]["traffic_class_column_present"] is False
assert unlabelled["mature_pending"]["rows"] == 3
assert unlabelled["mature_pending"]["existing_decay_candidate_memories"] == 1
assert unlabelled["mature_pending"]["existing_reinforce_candidate_memories"] == 1
assert unlabelled["eval_contamination_bounds"] == {
    "decay_candidate_memories_max": 1,
    "decay_candidate_memories_min": 0,
    "identified_exactly": False,
    "reinforce_candidate_memories_max": 1,
    "reinforce_candidate_memories_min": 0,
}
assert unlabelled["ambient_stage2_gate"]["verdict"] == "WAIT"
assert unlabelled["outcome_apply_authorized"] is False
assert unlabelled["no_write_invariant"]["passed"] is True

labelled = packet("telemetry-labelled.json")
assert labelled["verdict"] == "READY_FOR_CLEAN_SHADOW"
assert labelled["observability"]["causal_separation_ready"] is True
assert labelled["mature_pending"]["rows"] == 7
assert labelled["mature_pending"]["existing_decay_candidate_memories"] == 2
assert labelled["mature_pending"]["existing_reinforce_candidate_memories"] == 2
assert labelled["mature_pending"]["organic_decay_candidate_memories"] == 1
assert labelled["mature_pending"]["organic_reinforce_candidate_memories"] == 1
assert labelled["mature_pending"]["known_eval_decay_candidate_memories"] == 1
assert labelled["mature_pending"]["known_eval_reinforce_candidate_memories"] == 1
assert labelled["eval_contamination_bounds"]["identified_exactly"] is True
assert labelled["outcome_apply_authorized"] is False

partial = packet("telemetry-partial.json")
assert partial["verdict"] == "BLOCKED_PARTIAL_TRAFFIC_CLASS"
assert partial["observability"]["mature_pending_rows_without_valid_class"] == 1
assert partial["eval_contamination_bounds"]["identified_exactly"] is False

for name in (
    "temporal.json",
    "telemetry-unlabelled.json",
    "telemetry-labelled.json",
    "telemetry-partial.json",
):
    text = (root / name).read_text(encoding="utf-8")
    for raw_identifier in (
        "status_mismatch",
        "edge_target",
        "declared_old",
        "stale_state",
        "u_decay",
        "u_used",
        "l_eval_decay",
        "l_org_decay",
        "l_mixed_used",
    ):
        assert json.dumps(raw_identifier) not in text, (name, raw_identifier)

for db_name, expected in (
    ("temporal.db", (18, 4)),
    ("telemetry-unlabelled.db", (4, 7)),
    ("telemetry-labelled.db", (5, 8)),
):
    con = sqlite3.connect(root / db_name)
    if db_name == "temporal.db":
        actual = (
            con.execute("SELECT count(*) FROM memories").fetchone()[0],
            con.execute("SELECT count(*) FROM memory_edges").fetchone()[0],
        )
    else:
        actual = (
            con.execute("SELECT count(*) FROM memories").fetchone()[0],
            con.execute("SELECT count(*) FROM retrieval_surfacing").fetchone()[0],
        )
    con.close()
    assert actual == expected, (db_name, actual, expected)

print("Memory evidence audit fixture verification passed")
PY

if python3 "$TEMPORAL" --db "$tmpdir/bad-schema.db" --json \
  > "$tmpdir/bad-stdout" 2> "$tmpdir/bad-stderr"; then
  echo "expected temporal audit to reject the incomplete schema" >&2
  exit 1
fi

grep -q "missing required tables" "$tmpdir/bad-stderr"
