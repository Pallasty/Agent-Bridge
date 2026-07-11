#!/usr/bin/env python3
"""AB internal regression benchmark (基尺) — see README.md in this directory.

Read-only: drives the deployed binary over MCP stdio; opens state.db mode=ro.
Components: retrieval (hit@k/MRR over curated real labels), continuity
(restore-drill checklist vs session_bootstrap), governance lint (stale
high-privilege rows). Distillation is gated (corpus < 10) and not implemented.
"""
import argparse
import datetime
import json
import os
import re
import sqlite3
import subprocess
import sys

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BINARY = os.path.expanduser("~/.local/bin/agent-bridge")
DEFAULT_DB = os.path.expanduser("~/.local/share/agent-bridge/state.db")
PROJECT_CWD = "/Data/CascadeProjects/agent-bridge"
LINT_STALE_DAYS = 14
# Conditional gates (continuity_role:constraint) are age-tolerant: they block
# an action until its gates are satisfied, and age alone does not expire them
# (two consecutive adjudications, 2026-07-05/06, both kept flagged constraint
# rows). They surface separately, on a longer leash, for periodic review.
LINT_CONSTRAINT_STALE_DAYS = 45
MRR_REGRESS_EPS = 0.05
# Only any_mode (the per-pair best-rank union) gates REGRESS. Single modes
# breathe on a living corpus — measured same-day 2026-07-06: hybrid drifted
# ±0.06 on an unchanged DB (coactivation graph moves under the searches
# themselves), and each ~10-row write day joggles some near-tie pair one
# fts rank (= 0.056 MRR on 9 pairs, a guaranteed false REGRESS). any_mode
# stayed exactly 0.679 through all of it; a real code regression drags the
# union down too. Per-mode deltas still print as informational notes.


class McpClient:
    """Serial JSON-RPC driver over stdio (same pattern as live_verify_*)."""

    def __init__(self, binary):
        env = os.environ.copy()
        env["AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS"] = "eval"
        self.proc = subprocess.Popen(
            [binary, "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
        )
        self._id = 0
        self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ab-eval", "version": "0"},
        })
        self.proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.proc.stdin.flush()

    def _rpc(self, method, params):
        self._id += 1
        self.proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}) + "\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("EOF from MCP server")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == self._id:
                return msg

    def call_tool(self, name, args):
        r = self._rpc("tools/call", {"name": name, "arguments": args})
        return r["result"]["content"][0]["text"]

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)


def load_fixture(name):
    with open(os.path.join(EVAL_DIR, "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- retrieval
def eval_retrieval(mcp):
    fixture = load_fixture("retrieval_pairs.json")
    modes = ["fts", "hybrid", "semantic"]
    per_pair = []
    for pair in fixture["pairs"]:
        # `expected_any` lists every key that legitimately satisfies the
        # query (living corpus: near-tie relevant rows swap ranks as recency
        # drifts); the pair scores by the best-ranked accepted key.
        accepted = pair.get("expected_any") or [pair["expected_key"]]
        row = {"query": pair["query"][:50], "expected": accepted[0], "ranks": {}}
        if len(accepted) > 1:
            row["accepted"] = accepted
        for mode in modes:
            try:
                text = mcp.call_tool("memory_search", {
                    "query": pair["query"], "mode": mode, "limit": 10})
                hits = json.loads(text)
                keys = [h.get("record", h).get("key") for h in hits]
            except Exception as e:  # search failure = miss, keep the run going
                keys = []
                row.setdefault("errors", {})[mode] = str(e)[:120]
            found = [keys.index(k) + 1 for k in accepted if k in keys]
            row["ranks"][mode] = min(found) if found else 0  # 0 = miss
        per_pair.append(row)

    metrics = {}
    n = len(per_pair)
    for mode in modes:
        ranks = [p["ranks"][mode] for p in per_pair]
        metrics[mode] = {
            "hit@5": round(sum(1 for r in ranks if 0 < r <= 5) / n, 3),
            "hit@10": round(sum(1 for r in ranks if 0 < r <= 10) / n, 3),
            "mrr": round(sum(1 / r for r in ranks if r > 0) / n, 3),
        }
    any_ranks = [min((r for r in p["ranks"].values() if r > 0), default=0) for p in per_pair]
    metrics["any_mode"] = {
        "hit@5": round(sum(1 for r in any_ranks if 0 < r <= 5) / n, 3),
        "hit@10": round(sum(1 for r in any_ranks if 0 < r <= 10) / n, 3),
        "mrr": round(sum(1 / r for r in any_ranks if r > 0) / n, 3),
    }
    return {"pairs": n, "metrics": metrics, "per_pair": per_pair}


# --------------------------------------------------------------- continuity
def eval_continuity(mcp):
    fixture = load_fixture("continuity_checklist.json")
    text = mcp.call_tool("session_bootstrap", {
        "cwd": PROJECT_CWD, "frontend": "claude-code"})
    results, tiers = [], {}
    for probe in fixture["probes"]:
        if probe["type"] == "key":
            # full row, floor index line, or any other verbatim key trace
            found = probe["value"] in text
        elif probe["type"] == "section":
            found = f"=== {probe['value']}" in text or f"== {probe['value']}" in text \
                or f"-- {probe['value']}" in text or probe["value"] in text
        else:  # text
            found = probe["value"] in text
        results.append({**probe, "found": found})
        t = tiers.setdefault(probe["tier"], {"total": 0, "found": 0,
                                             "required": 0, "required_found": 0})
        t["total"] += 1
        t["found"] += int(found)
        if probe["required"]:
            t["required"] += 1
            t["required_found"] += int(found)
    missing_required = [r["value"] for r in results if r["required"] and not r["found"]]
    return {
        "bootstrap_chars": len(text),
        "tiers": tiers,
        "missing_required": missing_required,
        "probes": results,
    }


# ------------------------------------------------------------- distillation
def eval_distillation(db_path):
    """S1 distillation-candidate detector, measured against the hand-curated
    pub_* corpus (ground truth = the corpus rows' non-pub provenance links).

    The detector is the draft S1 heuristic (validated 2026-07-07, in-store
    recall 4/4): verified lessons/error_patterns by continuity tag, plus
    verified outcomes by facet tag — two different tag vocabularies, both
    required. Rows already public or dismissed (distill:no) are excluded.
    Gate: below 10 corpus rows there is nothing to evaluate honestly.
    """
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    pubs = db.execute(
        "SELECT key, related_keys FROM memories WHERE key LIKE 'pub_%' AND status='active'"
    ).fetchall()
    if len(pubs) < 10:
        db.close()
        return {"status": "gated", "reason": f"pub_* corpus < 10 rows ({len(pubs)})"}
    sources = set()
    for _, rk in pubs:
        for k in json.loads(rk or "[]"):
            if not k.startswith("pub_"):
                sources.add(k)
    in_store = {s for s in sources
                if db.execute("SELECT 1 FROM memories WHERE key=? AND status='active'",
                              (s,)).fetchone()}
    cands = db.execute(
        """SELECT key FROM memories WHERE status='active'
           AND key NOT LIKE 'pub_%'
           AND tags NOT LIKE '%\"zone:public\"%'
           AND tags NOT LIKE '%\"distill:no\"%'
           AND ((kind IN ('lesson','error_pattern')
                 AND tags LIKE '%\"continuity_confidence:verified\"%')
             OR (kind IN ('present_outcome','outcome')
                 AND tags LIKE '%\"verify:verified\"%'))"""
    ).fetchall()
    db.close()
    cand_keys = {c[0] for c in cands}
    hits = sorted(in_store & cand_keys)
    return {
        "status": "active",
        "corpus_rows": len(pubs),
        "provenance_sources": len(sources),
        # File-archive provenance (session memory files) is invisible to a
        # store-side detector by construction; recall is scored on the
        # in-store subset only.
        "provenance_in_store": len(in_store),
        "detector_population": len(cand_keys),
        "detector_recall_hits": hits,
        "detector_recall": f"{len(hits)}/{len(in_store)}",
    }


# ---------------------------------------------------------- governance lint
def eval_governance_lint(db_path):
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = db.execute(
        """SELECT key, kind, created_at, tags FROM memories WHERE status='active'
           AND tags LIKE '%\"continuity_actionability:must_block\"%'
           AND (tags LIKE '%\"continuity_freshness_policy:version_bound\"%'
             OR tags LIKE '%\"continuity_freshness_policy:project_phase_bound\"%')
           AND created_at < strftime('%s','now') - ? * 86400
           ORDER BY created_at""", (LINT_STALE_DAYS,)).fetchall()
    db.close()
    now = datetime.datetime.now().timestamp()
    suspects, aging_constraints = [], []
    for k, kind, c, tags in rows:
        age = round((now - c) / 86400)
        entry = {"key": k, "kind": kind, "age_days": age}
        if '"continuity_role:constraint"' in tags:
            # v1: conditional gates are age-tolerant — only long-idle ones
            # surface, and only for periodic review, never as stale suspects.
            if age >= LINT_CONSTRAINT_STALE_DAYS:
                aging_constraints.append(entry)
        else:
            suspects.append(entry)
    return {
        "stale_days_threshold": LINT_STALE_DAYS,
        "constraint_stale_days_threshold": LINT_CONSTRAINT_STALE_DAYS,
        "suspects": suspects,
        "aging_constraints": aging_constraints,
    }


# ------------------------------------------------------------------ compare
def compare(base, current):
    """`base` is the pre-loaded baseline dict — loaded BEFORE this run wrote
    its own baseline file, so a same-day compare (the standard discipline
    usage) diffs against the committed morning state instead of itself."""
    verdict, notes = "PASS", []
    b_m = base.get("retrieval", {}).get("metrics", {})
    c_m = current.get("retrieval", {}).get("metrics", {})
    for mode in c_m:
        if mode in b_m:
            delta = c_m[mode]["mrr"] - b_m[mode]["mrr"]
            gates = mode == "any_mode"
            tag = "" if gates or delta >= -MRR_REGRESS_EPS else " [drift, informational]"
            notes.append(f"retrieval {mode} MRR {b_m[mode]['mrr']} -> {c_m[mode]['mrr']} ({delta:+.3f}){tag}")
            if gates and delta < -MRR_REGRESS_EPS:
                verdict = "REGRESS"
    b_miss = set(base.get("continuity", {}).get("missing_required", []))
    c_miss = set(current.get("continuity", {}).get("missing_required", []))
    newly = c_miss - b_miss
    if newly:
        verdict = "REGRESS"
        notes.append(f"continuity newly missing required probes: {sorted(newly)}")
    fixed = b_miss - c_miss
    if fixed:
        notes.append(f"continuity probes recovered: {sorted(fixed)}")
    b_lint = {s["key"] for s in base.get("governance_lint", {}).get("suspects", [])}
    c_lint = {s["key"] for s in current.get("governance_lint", {}).get("suspects", [])}
    if c_lint - b_lint:
        notes.append(f"lint new suspects (informational): {sorted(c_lint - b_lint)}")
    return verdict, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default=DEFAULT_BINARY)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--component",
                    choices=["retrieval", "continuity", "lint", "distillation"],
                    default=None)
    ap.add_argument("--compare", default=None, metavar="BASELINE_JSON")
    ap.add_argument("--out", default=None, help="output path (default baselines/<date>.json)")
    args = ap.parse_args()

    # Load the compare baseline FIRST: the default output path is
    # baselines/<today>.json, so a same-day --compare would otherwise read
    # the file this run just overwrote and trivially PASS with +0.000.
    baseline_data = None
    if args.compare:
        with open(args.compare, encoding="utf-8") as f:
            baseline_data = json.load(f)

    result = {
        "date": datetime.date.today().isoformat(),
        "binary": args.binary,
    }
    need_mcp = args.component in (None, "retrieval", "continuity")
    mcp = McpClient(args.binary) if need_mcp else None
    try:
        if args.component in (None, "retrieval"):
            result["retrieval"] = eval_retrieval(mcp)
        if args.component in (None, "continuity"):
            result["continuity"] = eval_continuity(mcp)
        if args.component in (None, "lint"):
            result["governance_lint"] = eval_governance_lint(args.db)
        if args.component in (None, "distillation"):
            result["distillation"] = eval_distillation(args.db)
    finally:
        if mcp:
            mcp.close()

    # Baselines are full-run snapshots. A --component run writes only to an
    # explicit --out, never the default baselines/<date>.json — a partial
    # file there blinds the next day's --compare (bit us 2026-07-07 when a
    # --component lint run overwrote the day's full baseline).
    out = args.out or (
        None if args.component
        else os.path.join(EVAL_DIR, "baselines", f"{result['date']}.json")
    )
    if out:
        out_dir = os.path.dirname(out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f"wrote {out}")
    else:
        print(f"component run ({args.component}): baseline not written (pass --out to save)")

    if "retrieval" in result:
        for mode, m in result["retrieval"]["metrics"].items():
            print(f"retrieval[{mode}]: hit@5={m['hit@5']} hit@10={m['hit@10']} mrr={m['mrr']}")
    if "continuity" in result:
        c = result["continuity"]
        for tier, t in sorted(c["tiers"].items()):
            print(f"continuity[{tier}]: {t['found']}/{t['total']} found, "
                  f"required {t['required_found']}/{t['required']}")
        if c["missing_required"]:
            print(f"continuity MISSING required: {c['missing_required']}")
    if "governance_lint" in result:
        for s in result["governance_lint"]["suspects"]:
            print(f"lint suspect: {s['key']} ({s['kind']}, {s['age_days']}d)")
        for s in result["governance_lint"].get("aging_constraints", []):
            print(f"lint aging constraint (review, not stale): {s['key']} ({s['kind']}, {s['age_days']}d)")
        if not result["governance_lint"]["suspects"] \
                and not result["governance_lint"].get("aging_constraints"):
            print("lint: clean (no suspects, no aging constraints)")
    if "distillation" in result:
        d = result["distillation"]
        if d["status"] == "gated":
            print(f"distillation: gated ({d['reason']})")
        else:
            print(f"distillation: corpus={d['corpus_rows']} "
                  f"detector recall {d['detector_recall']} (in-store provenance), "
                  f"population={d['detector_population']}")

    if args.compare:
        verdict, notes = compare(baseline_data, result)
        print(f"\ncompare vs {args.compare}: {verdict}")
        for n in notes:
            print(f"  {n}")
        sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
