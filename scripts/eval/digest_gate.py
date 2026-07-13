#!/usr/bin/env python3
"""Offline promotion gate for digest-author drafts (S1 of the nightly
digest-author pipeline — docs/DESIGN-nightly-digest-author.md §7).

Everything runs against a SHADOW COPY of state.db (XDG_DATA_HOME override,
honored by ab_store::default_db_path). The live store is opened read-only
exactly once, to prove the sentinel write did NOT land there. A candidate
digest is materialized only in the copy; the two gates are:

  1. hit gate       — the candidate ranks ≤5 in ≥1 mode for ≥1 target query
  2. non-regression — synthesis set_recall any_mode@20, measured PRE vs POST
                      on the SAME frozen copy (paired design: living-corpus
                      drift cannot fake a regression), drops < 0.02

PASS means "safe to promote"; promotion itself stays manual in S1 — an agent
session runs the printed memory_save against the live store and tags the
draft resolved:promoted. This script never writes to the live store.

Usage:
  python3 scripts/eval/digest_gate.py --draft-key digest_draft_t1_s3
  python3 scripts/eval/digest_gate.py --draft-key ... --keep-scratch --report out.json
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EVAL_DIR)
from ab_eval import McpClient, eval_synthesis  # noqa: E402

DEFAULT_BINARY = os.path.expanduser("~/.local/bin/agent-bridge")
DEFAULT_DB = os.path.expanduser("~/.local/share/agent-bridge/state.db")
HIT_GATE_RANK = 5
NON_REGRESSION_EPS = 0.02
MODES = ["fts", "hybrid", "semantic"]
PIPELINE_TAG = "derived:digest_author"


def copy_db_to_shadow(src_db, scratch):
    """sqlite backup (WAL-safe) into the XDG layout the binary expects."""
    data_dir = os.path.join(scratch, "agent-bridge")
    os.makedirs(data_dir, exist_ok=True)
    dest = os.path.join(data_dir, "state.db")
    src = sqlite3.connect(f"file:{src_db}?mode=ro", uri=True)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return dest


def key_in_db(db_path, key):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
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
        tags = sorted(set(d.get("tags", [])) | {"digest", PIPELINE_TAG,
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
            print("\npromotion (manual, against the LIVE store — S1 keeps a "
                  "human/agent in the loop):")
            print(f"  memory_save {json.dumps(save_args, ensure_ascii=False)[:400]}…")
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
