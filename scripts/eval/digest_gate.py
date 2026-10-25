#!/usr/bin/env python3
"""Offline promotion gate for digest-author drafts (S1 of the nightly
digest-author pipeline — docs/DESIGN-nightly-digest-author.md §7).

Everything runs against a SHADOW COPY of state.db (XDG_DATA_HOME override,
honored by ab_store::default_db_path). The live store is opened read-only
for backup and isolation verification. Before starting MCP, a read-only source
lifecycle and bound-revision check runs against the frozen copy. A candidate digest is materialized
only in the copy; the retrieval gates are:

  1. hit gate       — the candidate ranks ≤5 in ≥1 mode for ≥1 target query
  2. non-regression — synthesis set_recall any_mode@20, measured PRE vs POST
                      on the SAME frozen copy (paired design: living-corpus
                      drift cannot fake a regression), drops < 0.02

PASS means only that bound source revisions, lifecycle and retrieval checks
passed on the copy, not that the answer was verified. Promotion stays manual:
recheck current sources and review the claims before an agent
session runs the printed memory_save against the live store and tags the
draft resolved:promoted. This script never writes to the live store.

Usage:
  python3 scripts/eval/digest_gate.py --draft-key digest_draft_t1_s3
  python3 scripts/eval/digest_gate.py --draft-key ... --keep-scratch --report out.json
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EVAL_DIR)
from ab_eval import McpClient, eval_synthesis  # noqa: E402

DEFAULT_BINARY = os.path.expanduser("~/.local/bin/agent-bridge")
DEFAULT_DB = os.path.expanduser("~/.local/share/agent-bridge/state.db")
HIT_GATE_RANK = 5
NON_REGRESSION_EPS = 0.02
MODES = ["fts", "hybrid", "semantic"]
PIPELINE_TAG = "derived:digest_author"
# Match the author's primary-material boundary; do not silently certify a
# digest-of-digest whose ancestors this bounded check does not inspect.
NON_PRIMARY_KINDS = {"digest", "digest_draft", "distill_draft", "work_memory",
                     "session_handoff", "retrieval_feedback", "snapshot"}


def read_only_db(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def source_revision_hash(row):
    """v1 UTF-8 compact JSON array; field order shared with dream_digest.rs.

    Bind prompt material and lifecycle metadata, excluding read telemetry,
    ranking importance, and embeddings. No normalization of text or array order.
    """
    tags, related = json.loads(row["tags"]), json.loads(row["related_keys"])
    for values in (tags, related):
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ValueError("invalid source array")
    for name in ("key", "kind", "content", "status"):
        if not isinstance(row[name], str):
            raise ValueError("invalid source string")
    for name in ("scope", "superseded_by", "trigger_pattern"):
        if row[name] is not None and not isinstance(row[name], str):
            raise ValueError("invalid nullable source string")
    for name in ("created_at", "updated_at"):
        if type(row[name]) is not int or row[name] <= 0:
            raise ValueError("invalid source timestamp")
    payload = [row["key"], row["kind"], row["scope"], row["content"], tags, related,
               row["created_at"], row["updated_at"], row["status"],
               row["superseded_by"], row["trigger_pattern"]]
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def check_source_lifecycle(db_path, draft_key):
    """Check declared primary sources in one read transaction, with no telemetry.

    Require producer-generated revision bindings; legacy drafts fail closed.
    Matching bytes do not establish truth, scope eligibility, authenticated
    provenance, or freshness outside this snapshot.
    """
    result = {"pass": False, "checked_sources": 0, "issues": [],
              "source_revision_verified": False, "answer_validated": False,
              "basis": "frozen_snapshot_bound_source_revisions"}

    def issue(key, reason):
        result["issues"].append({"key": key, "reason": reason})

    def keys(value):
        if (not isinstance(value, list) or not value
                or any(not isinstance(k, str) or not k.strip() for k in value)
                or len(value) != len(set(value))):
            raise ValueError("source keys must be a nonempty unique string list")
        return value

    conn = read_only_db(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        draft = conn.execute("SELECT * FROM memories WHERE key=?", (draft_key,)).fetchone()
        if draft is None:
            issue(draft_key, "draft_missing")
            return result
        if (draft["kind"] != "digest_draft" or draft["status"] != "active"
                or draft["superseded_by"]):
            issue(draft_key, "draft_not_active_candidate")
            return result
        model = extract_model_json(draft["content"])
        if model.get("verdict") != "author":
            issue(draft_key, "draft_not_author")
            return result
        sources = keys(model["draft"]["source_keys"])
        declared = keys(json.loads(draft["related_keys"]))
        if set(sources) != set(declared):
            issue(draft_key, "source_keys_disagree_with_draft")
            return result
        binding = model.get("source_bindings")
        if not isinstance(binding, dict) or binding.get("schema") != "ab.digest.sources.v1":
            issue(draft_key, "source_binding_missing_or_unsupported")
            return result
        entries = binding.get("sources")
        if not isinstance(entries, list) or not entries or len(entries) > 12:
            issue(draft_key, "source_binding_invalid")
            return result
        hashes = {}
        for entry in entries:
            if (not isinstance(entry, dict) or set(entry) != {"key", "sha256"}
                    or not isinstance(entry["key"], str) or not entry["key"].strip()
                    or entry["key"] in hashes or not isinstance(entry["sha256"], str)
                    or re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is None):
                issue(draft_key, "source_binding_invalid")
                return result
            hashes[entry["key"]] = entry["sha256"]
        if not set(sources).issubset(hashes):
            issue(draft_key, "source_binding_incomplete")
            return result
        # The author supplies at most twelve primary rows. Bound work even for
        # hand-edited drafts rather than traversing arbitrary related_keys.
        if len(sources) > 12:
            issue(draft_key, "source_limit_exceeded")
            return result
        if type(draft["created_at"]) is not int or draft["created_at"] <= 0:
            issue(draft_key, "draft_creation_time_unknown")
            return result
        # Include uncited material: the author saw the entire manifest, so an
        # uncited correction can also change what the synthesis should say.
        for key, expected_hash in hashes.items():
            source = conn.execute("SELECT * FROM memories WHERE key=?", (key,)).fetchone()
            result["checked_sources"] += 1
            if source is None:
                issue(key, "source_missing")
                continue
            if source["status"] != "active" or source["superseded_by"]:
                issue(key, "source_not_active")
            if source["kind"] in NON_PRIMARY_KINDS:
                issue(key, "source_not_primary")
            updated = source["updated_at"]
            if type(updated) is not int or updated <= 0:
                issue(key, "source_update_time_unknown")
            elif updated > draft["created_at"]:
                issue(key, "source_updated_after_draft")
            if source_revision_hash(source) != expected_hash:
                issue(key, "source_revision_mismatch")
        result["pass"] = not result["issues"]
        result["source_revision_verified"] = result["pass"]
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, AttributeError, SystemExit):
        # Do not disclose source prose or SQL errors in a provenance report.
        issue(draft_key, "malformed_or_unverifiable_provenance")
    finally:
        conn.close()
    return result


def copy_db_to_shadow(src_db, scratch):
    """sqlite backup (WAL-safe) into the XDG layout the binary expects."""
    data_dir = os.path.join(scratch, "agent-bridge")
    os.makedirs(data_dir, exist_ok=True)
    dest = os.path.join(data_dir, "state.db")
    src = read_only_db(src_db)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return dest


def key_in_db(db_path, key):
    conn = read_only_db(db_path)
    try:
        row = conn.execute("SELECT 1 FROM memories WHERE key = ?", (key,)).fetchone()
        return row is not None
    finally:
        conn.close()


def extract_model_json(draft_content):
    """The draft row embeds the model's raw JSON as its last ```json block."""
    blocks = re.findall(r"```json\n(.*?)\n```", draft_content, re.DOTALL)
    if not blocks:
        raise SystemExit("draft row has no ```json block — not a digest_draft?")
    return json.loads(blocks[-1])


def search_rank(mcp, query, key, mode):
    text = mcp.call_tool("memory_search", {"query": query, "mode": mode, "limit": 10})
    keys = [h.get("record", h).get("key") for h in json.loads(text)]
    return keys.index(key) + 1 if key in keys else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft-key", required=True)
    ap.add_argument("--binary", default=DEFAULT_BINARY)
    ap.add_argument("--db", default=DEFAULT_DB, help="live state.db to shadow-copy")
    ap.add_argument("--scratch-dir", default=None,
                    help="parent dir for the shadow copy (default: system tmp)")
    ap.add_argument("--keep-scratch", action="store_true")
    ap.add_argument("--report", default=None, help="write the JSON report here")
    args = ap.parse_args()

    scratch = tempfile.mkdtemp(prefix="ab-digest-gate-", dir=args.scratch_dir)
    shadow_db = copy_db_to_shadow(args.db, scratch)
    # Everything the binary spawns from here on must see the shadow copy.
    os.environ["XDG_DATA_HOME"] = scratch
    print(f"shadow copy: {shadow_db}")

    report = {"draft_key": args.draft_key, "shadow_db": shadow_db}
    try:
        report["source_lifecycle"] = check_source_lifecycle(shadow_db, args.draft_key)
        if not report["source_lifecycle"]["pass"]:
            report["verdict"] = "BLOCKED_SOURCE_LIFECYCLE"
            print(json.dumps(report["source_lifecycle"], ensure_ascii=False))
            raise SystemExit("BLOCKED_SOURCE_LIFECYCLE: refresh/review source evidence before evaluation")
        # ── isolation proof: a write lands in the copy, never in live ──
        sentinel = f"digest_gate_sentinel_{os.getpid()}"
        mcp = McpClient(args.binary)
        mcp.call_tool("memory_save", {
            "key": sentinel, "kind": "observation",
            "content": "digest_gate isolation sentinel (shadow copy only)"})
        if not key_in_db(shadow_db, sentinel):
            raise SystemExit("ABORT: sentinel missing from shadow copy — "
                             "XDG_DATA_HOME override did not take effect")
        if key_in_db(args.db, sentinel):
            raise SystemExit("ABORT: sentinel FOUND IN LIVE DB — the spawned "
                             "binary ignored XDG_DATA_HOME; live store may be "
                             "polluted, investigate before rerunning")
        print("isolation: sentinel in shadow only — OK")

        # ── read the draft + PRE eval on the same client/frozen copy ──
        draft_text = mcp.call_tool("memory_get", {"key": args.draft_key})
        draft_row = json.loads(draft_text)
        if not draft_row:
            raise SystemExit(f"draft row {args.draft_key} not found")
        model = extract_model_json(draft_row["content"])
        if model.get("verdict") != "author":
            raise SystemExit(f"draft verdict is {model.get('verdict')!r} — "
                             "only author drafts go through the gate")
        d = model["draft"]
        digest_key = d["key"]
        target_queries = [q for q in d.get("target_queries", []) if q.strip()]
        if not digest_key.startswith("digest_") or not target_queries:
            raise SystemExit("malformed draft payload (key prefix / target_queries)")
        report["digest_key"] = digest_key
        report["target_queries"] = target_queries

        pre = eval_synthesis(mcp)
        pre_any = pre["metrics"]["any_mode"]["set_recall@20"]
        report["pre_any_mode_set_recall@20"] = pre_any
        mcp.close()

        # ── materialize the candidate in the copy (fresh client) ──
        mcp = McpClient(args.binary)
        binding_tag = "digest_sources_v1:" + json.dumps(
            model["source_bindings"], ensure_ascii=False, separators=(",", ":"))
        # Host-verified bindings travel with the live digest, not merely with
        # its draft. Never preserve model-supplied tags in this reserved namespace.
        tags = sorted({t for t in d.get("tags", []) if not t.startswith("digest_sources_v1:")} |
                      {binding_tag, "digest", PIPELINE_TAG,
                                                "digest:candidate",
                                                f"promoted_from:{args.draft_key}"})
        save_args = {
            "key": digest_key, "kind": "digest", "content": d["content"],
            "tags": tags, "related_keys": d.get("source_keys", []),
            "importance": 0.6,
            "continuity": {"retrieval_trigger": d.get("retrieval_trigger", "")[:160]},
        }
        mcp.call_tool("memory_save", save_args)
        mcp.close()

        # ── POST: hit gate + paired non-regression (fresh client: cold
        #    caches, so the candidate is visible to every mode) ──
        mcp = McpClient(args.binary)
        hit_rows = []
        best = 0
        for q in target_queries:
            ranks = {m: search_rank(mcp, q, digest_key, m) for m in MODES}
            q_best = min((r for r in ranks.values() if r > 0), default=0)
            if q_best and (best == 0 or q_best < best):
                best = q_best
            hit_rows.append({"query": q[:60], "ranks": ranks, "best": q_best})
        hit_pass = 0 < best <= HIT_GATE_RANK
        report["hit_gate"] = {"per_query": hit_rows, "best_rank": best,
                              "pass": hit_pass}

        post = eval_synthesis(mcp)
        post_any = post["metrics"]["any_mode"]["set_recall@20"]
        delta = round(post_any - pre_any, 3)
        nr_pass = delta >= -NON_REGRESSION_EPS
        report["post_any_mode_set_recall@20"] = post_any
        report["delta"] = delta
        report["non_regression_pass"] = nr_pass
        # Per-query diagnosis: a drop on the candidate's OWN target query is
        # self-crowding (the digest outranks the scattered golds it summarizes
        # — the answer_vehicle lens sees the win set_recall can't); a drop on
        # any OTHER query is true collateral damage. The verdict floor treats
        # both the same in v1; the breakdown makes the distinction reviewable.
        pre_q = {p["id"]: p["any_mode"]["set_recall@20"] for p in pre["per_query"]}
        diffs = []
        for p in post["per_query"]:
            d = round(p["any_mode"]["set_recall@20"] - pre_q.get(p["id"], 0), 3)
            if d != 0:
                diffs.append({"id": p["id"], "query": p["query"],
                              "pre": pre_q.get(p["id"]), "delta": d})
        report["per_query_diffs"] = diffs
        if diffs:
            print("per-query set_recall@20 diffs (any_mode):")
            for row in diffs:
                print(f"  {row['id']}: {row['pre']} {row['delta']:+.3f}  {row['query']}")
        mcp.close()

        verdict = "PASS" if (hit_pass and nr_pass) else "FAIL"
        report["verdict"] = verdict

        print(f"\nhit gate: best rank {best or 'miss'} "
              f"(need ≤{HIT_GATE_RANK}) → {'PASS' if hit_pass else 'FAIL'}")
        for row in hit_rows:
            print(f"  {row['ranks']}  {row['query']}")
        print(f"non-regression: any_mode set_recall@20 {pre_any} -> {post_any} "
              f"({delta:+.3f}, floor -{NON_REGRESSION_EPS}) → "
              f"{'PASS' if nr_pass else 'FAIL'}")
        print(f"\nverdict: {verdict}")
        if verdict == "PASS":
            report["manual_promotion"] = {
                "memory_save": save_args,
                "requires_current_source_and_claim_review": True,
            }
            print("Bound source revisions and lifecycle checked on a frozen copy only; "
                  "answer truth is NOT verified. Recheck current "
                  "sources and review claims before manual promotion.")
            print("\npromotion (manual, against the LIVE store — S1 keeps a "
                  "human/agent in the loop):")
            print(f"  memory_save {json.dumps(save_args, ensure_ascii=False)}")
            print(f"  then tag {args.draft_key} resolved:promoted, and declare "
                  f"the vehicle in fixtures/synthesis_queries.json if this "
                  f"topic came from the eval set")
    finally:
        if args.report:
            with open(args.report, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=1)
            print(f"report: {args.report}")
        if args.keep_scratch:
            print(f"scratch kept: {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)

    sys.exit(0 if report.get("verdict") == "PASS" else 1)


if __name__ == "__main__":
    main()
