#!/usr/bin/env python3
"""Traversal diagnostic: can 1-hop expansion over EXISTING edges buy back
synthesis-class recall, or must the answer keep being written (digests)?

Question (2026-07-14, owner-approved arc): associations can live in three
places — storage ranking (measured 3x, net-negative), the agent's own loop
(reads a hit, follows the keys it cites), or pre-written digest rows. This
script measures the middle one: after a normal top-20 search, follow one hop
of edges from the top-10 hits and see what that reaches.

Three edge channels, scored separately because they differ in WHO can see them:
  rk    — related_keys on the hit row (visible in the search result itself)
  cite  — keys cited inline in the hit's content (visible by reading the hit)
  edge  — memory_edges rows in either direction (visible only via
          memory_neighbors / graph tooling; includes reverse links)

Metrics per query:
  baseline   — any_mode set_recall@20 exactly as eval_synthesis computes it
  budgeted   — replace ranks 11-20 with 1-hop neighbors of the top-10 seeds
               (seed-rank order, channel order rk>cite>edge), same @20 budget;
               reports golds GAINED and golds LOST vs baseline
  unbounded  — gold ∈ top-20 ∪ 1hop(top-10 any-mode seeds): the agent-reads-
               neighbors model, no rank budget
  ceiling    — for golds missed by baseline: 1-hop and 2-hop reachability from
               the any-mode seed set over the combined channels — are the
               edges there at all?
Hub attribution: for every gold reached through expansion, which seed row
reached it and whether that seed is a digest/*-kind row (is the digest arc
re-densifying the graph as a side effect?).

Read-only: searches go through the deployed binary under the eval traffic
class (same as ab_eval); edge/content reads open state.db mode=ro directly,
so no access_count bumps and no telemetry rows.
"""
import argparse
import datetime
import json
import os
import re
import sqlite3
import sys

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EVAL_DIR)
from ab_eval import McpClient, load_fixture, DEFAULT_BINARY, DEFAULT_DB  # noqa: E402

SEED_TOP_N = 10       # hits whose neighborhoods we expand
BUDGET = 20           # candidate-list budget for the budgeted variant
SEARCH_LIMIT = 20     # same as eval_synthesis SYNTHESIS_LIMIT
# Tokens that look like keys: intersected against the active-key set, so this
# only needs to be permissive enough to not split real keys (which use
# [a-z0-9_], plus ':' in correction/derived keys and '-' in a few legacy ones).
KEY_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_:.\-]*[A-Za-z0-9_]")


def load_graph(db_path):
    """One read-only pass over the store: active keys, per-row forward links
    (related_keys / inline citations), typed edges both directions, kinds."""
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT key, kind, related_keys, content FROM memories WHERE status='active'"
    ).fetchall()
    active = {r[0] for r in rows}
    kind = {r[0]: r[1] for r in rows}
    rk, cite = {}, {}
    for key, _, related, content in rows:
        rk[key] = [k for k in json.loads(related or "[]") if k in active and k != key]
        toks = []
        seen = set()
        for t in KEY_TOKEN_RE.findall(content or ""):
            if t != key and t in active and t not in seen:
                seen.add(t)
                toks.append(t)  # first-appearance order, deterministic
        cite[key] = toks
    edge = {}
    for f, t in db.execute(
            "SELECT from_key, to_key FROM memory_edges "
            "WHERE edge_type != 'coactivation' ORDER BY from_key, to_key"):
        if f in active and t in active:
            edge.setdefault(f, []).append(t)
            edge.setdefault(t, []).append(f)  # reverse direction on purpose
    db.close()
    return {"active": active, "kind": kind, "rk": rk, "cite": cite, "edge": edge}


def neighbors(graph, key, channels):
    out, seen = [], set()
    for ch in channels:
        for n in graph[ch].get(key, []):
            if n not in seen:
                seen.add(n)
                out.append((n, ch))
    return out


def search_keys(mcp, query, mode):
    text = mcp.call_tool("memory_search", {
        "query": query, "mode": mode, "limit": SEARCH_LIMIT})
    hits = json.loads(text)
    return [h.get("record", h).get("key") for h in hits]


def reachable(graph, seeds, targets, hops):
    """BFS over combined channels; returns {target: hop_distance} for reached."""
    dist = {s: 0 for s in seeds}
    frontier = list(seeds)
    for h in range(1, hops + 1):
        nxt = []
        for k in frontier:
            for n, _ in neighbors(graph, k, ("rk", "cite", "edge")):
                if n not in dist:
                    dist[n] = h
                    nxt.append(n)
        frontier = nxt
    return {t: dist[t] for t in targets if t in dist}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default=DEFAULT_BINARY)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--fixture", default="synthesis_queries.json")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    graph = load_graph(args.db)
    fixture = load_fixture(args.fixture)
    modes = ["fts", "hybrid", "semantic"]
    mcp = McpClient(args.binary)
    per_query = []
    try:
        for q in fixture["queries"]:
            gold = q["gold_set"]
            rec = {"id": q.get("id"), "query": q["query"][:50], "gold_n": len(gold)}
            mode_keys = {}
            for mode in modes:
                try:
                    mode_keys[mode] = search_keys(mcp, q["query"], mode)
                except Exception as e:
                    mode_keys[mode] = []
                    rec.setdefault("errors", {})[mode] = str(e)[:120]

            base_hit = {k for k in gold
                        if any(k in mode_keys[m][:BUDGET] for m in modes)}

            # budgeted: per mode, top-10 kept, ranks 11-20 handed to neighbors
            budg_hit, gained_via = set(), {}
            for mode in modes:
                seeds = mode_keys[mode][:SEED_TOP_N]
                cand = list(seeds)
                have = set(seeds)
                for seed in seeds:
                    for n, ch in neighbors(graph, seed, ("rk", "cite", "edge")):
                        if len(cand) >= BUDGET:
                            break
                        if n not in have:
                            have.add(n)
                            cand.append(n)
                            if n in gold and n not in base_hit:
                                gained_via.setdefault(n, []).append(
                                    {"mode": mode, "seed": seed,
                                     "seed_kind": graph["kind"].get(seed), "ch": ch})
                    if len(cand) >= BUDGET:
                        break
                budg_hit |= {k for k in gold if k in cand}

            # unbounded 1-hop from the union of per-mode top-10 seeds
            seed_union, seen = [], set()
            for m in modes:
                for k in mode_keys[m][:SEED_TOP_N]:
                    if k not in seen:
                        seen.add(k)
                        seed_union.append(k)
            hood = set(seed_union)
            hood_via = {}
            for seed in seed_union:
                for n, ch in neighbors(graph, seed, ("rk", "cite", "edge")):
                    if n not in hood:
                        hood.add(n)
                        hood_via[n] = {"seed": seed,
                                       "seed_kind": graph["kind"].get(seed), "ch": ch}
            unb_hit = base_hit | {k for k in gold if k in hood}

            # per-channel unbounded (which visibility class does the work?)
            ch_hit = {}
            for ch in ("rk", "cite", "edge"):
                reach = set(seed_union)
                for seed in seed_union:
                    for n, _ in neighbors(graph, seed, (ch,)):
                        reach.add(n)
                ch_hit[ch] = sorted(k for k in gold
                                    if k in reach and k not in base_hit)

            missed = [k for k in gold if k not in base_hit]
            ceil = reachable(graph, seed_union, missed, hops=2)

            g = len(gold) or 1
            rec.update({
                "seed_union_n": len(seed_union),
                "hood_n": len(hood),  # honest cost of the agent-reads model
                "baseline_recall20": round(len(base_hit) / g, 3),
                "budgeted_recall20": round(len(budg_hit) / g, 3),
                "unbounded_1hop_recall": round(len(unb_hit) / g, 3),
                "budget_gained": sorted(budg_hit - base_hit),
                "budget_lost": sorted(base_hit - budg_hit),
                "gained_via": gained_via,
                "unbounded_gained_via": {k: hood_via[k] for k in unb_hit - base_hit
                                         if k in hood_via},
                "per_channel_gains": ch_hit,
                "missed_baseline": missed,
                "ceiling": {k: f"{h}hop" for k, h in sorted(ceil.items())},
                "unreachable_2hop": sorted(set(missed) - set(ceil)),
            })
            per_query.append(rec)
    finally:
        mcp.close()

    n = len(per_query)
    summary = {
        "date": datetime.date.today().isoformat(),
        "fixture": args.fixture,
        "queries": n,
        "baseline_recall20": round(sum(p["baseline_recall20"] for p in per_query) / n, 3),
        "budgeted_recall20": round(sum(p["budgeted_recall20"] for p in per_query) / n, 3),
        "unbounded_1hop_recall": round(
            sum(p["unbounded_1hop_recall"] for p in per_query) / n, 3),
        "mean_hood_n": round(sum(p["hood_n"] for p in per_query) / n, 1),
        "missed_total": sum(len(p["missed_baseline"]) for p in per_query),
        "reachable_1hop": sum(1 for p in per_query
                              for v in p["ceiling"].values() if v == "1hop"),
        "reachable_2hop": sum(1 for p in per_query
                              for v in p["ceiling"].values() if v == "2hop"),
        "unreachable_2hop": sum(len(p["unreachable_2hop"]) for p in per_query),
    }
    digest_seeded = sum(
        1 for p in per_query for v in p["unbounded_gained_via"].values()
        if (v["seed_kind"] or "").startswith("digest") or "digest" in v["seed"])
    summary["unbounded_gains"] = sum(len(p["unbounded_gained_via"]) for p in per_query)
    summary["unbounded_gains_via_digest_seed"] = digest_seeded

    report = {"summary": summary, "per_query": per_query}
    out = args.out or os.path.join(
        EVAL_DIR, "baselines", "components",
        f"traversal_{summary['date']}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print(f"wrote {out}")
    print(f"baseline  any_mode set_recall@20      = {summary['baseline_recall20']}")
    print(f"budgeted  +1hop swap (same @20)       = {summary['budgeted_recall20']}")
    print(f"unbounded +1hop (agent-reads-model)   = {summary['unbounded_1hop_recall']}")
    print(f"missed golds: {summary['missed_total']}  "
          f"(1hop-reachable {summary['reachable_1hop']}, "
          f"2hop {summary['reachable_2hop']}, "
          f"unreachable@2 {summary['unreachable_2hop']})")
    print(f"expansion gains: {summary['unbounded_gains']} "
          f"({summary['unbounded_gains_via_digest_seed']} via digest-kind seed)")
    for p in per_query:
        flag = ""
        if p["budget_lost"]:
            flag = f"  LOST {p['budget_lost']}"
        print(f"  {p['id']}: base {p['baseline_recall20']} -> "
              f"budg {p['budgeted_recall20']} / unb {p['unbounded_1hop_recall']}"
              f"{flag}")


if __name__ == "__main__":
    main()
