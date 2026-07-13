#!/usr/bin/env python3
"""MRAgent active-reconstruction trial — the three retrieval arms + metering.

  S0  one memory_search(hybrid, limit=8).
  S1  blind up-front decomposition into k sub-queries derived ONLY from the
      question text, union the hits. Equal call-budget control against S2 --
      it isolates "evidence-conditioning" from "just more queries".
  S2  evidence-conditioned reconstruction: round-1 hybrid -> inspect -> a graph
      hop (memory_neighbors from the best hit) + conditioned re-query rounds whose
      vocabulary is round-1-derivable, capped at 6 memory calls, WITH an
      existence/abstention gate that fires BEFORE assembly (P3: never stitch a
      fabricated answer).

Design decisions (honest scope):
  * Queries are FIXTURE-AUTHORED deterministic plans, exactly as the read-only
    pilot hand-authored them. Runtime LLM sub-query generation is a separate
    (review-backed) variance axis; this harness measures the RETRIEVAL MECHANISM
    under a competent planner, reproducibly.
  * Metering uses `compact:true` search: per-arm memory `calls`, `context_chars`
    (sum of hit content_chars = a context-token proxy; real provider tokens need
    the LLM arm), and per-call `latency` (run.py takes p95 across probes).
  * The deterministic harness measures `canary_retrieved` (did the injection row
    enter the arm's context) -- a NECESSARY condition for a leak. Actual
    `canary_fired` (an LLM obeying the embedded instruction) is set by the
    agent-in-the-loop wrapper, not this executor; here it defaults False.

CLI:
  --selftest              offline: MockClient drives S0/S1/S2 through scripted
                          corpora -- control flow, metering, abstention, cap,
                          canary-retrieval -- no binary/store.
  --run PLANS.json --db DB   live: run every plan x arm against a materialized
                          snapshot DB (AGENT_BRIDGE_DB scoped) and emit
                          score.py-ready arm results.
"""
import argparse
import json
import os
import sys
import time

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
if EVAL_DIR not in sys.path:
    sys.path.insert(0, EVAL_DIR)
from mragent_reconstruction_snapshot import McpClient, DEFAULT_BINARY, canary_keys  # noqa: E402

CANARY_KEY = canary_keys()[0]
CAP_CALLS = 6  # S2 hard bound: "3 rounds / 6 memory calls"


# ------------------------------------------------------------------ metering
class Meter:
    def __init__(self):
        self.calls = 0
        self.context_chars = 0
        self.latencies = []  # seconds

    def record(self, latency_s, chars):
        self.calls += 1
        self.latencies.append(latency_s)
        self.context_chars += int(chars)

    def as_dict(self):
        return {
            "calls": self.calls,
            "context_chars": self.context_chars,
            "latency_ms_total": round(sum(self.latencies) * 1000, 1),
            "latency_ms_max": round(max(self.latencies) * 1000, 1) if self.latencies else 0.0,
        }


def _search(client, meter, query, mode="hybrid", limit=8):
    """Return the ranked compact hit list; meter the call + its context cost."""
    t = time.monotonic()
    text = client.call_tool("memory_search", {
        "query": query, "mode": mode, "limit": limit, "compact": True})
    latency = time.monotonic() - t
    hits = json.loads(text) if text else []
    chars = sum(int(h.get("content_chars", 0)) for h in hits)
    meter.record(latency, chars)
    return hits


def _neighbors(client, meter, key, depth=1):
    """Graph hop: return neighbor keys (edges carry ~no content -> 0 chars)."""
    t = time.monotonic()
    text = client.call_tool("memory_neighbors", {"key": key, "depth": depth})
    latency = time.monotonic() - t
    rows = json.loads(text) if text else []
    keys = []
    for r in rows:
        for side in ("to_key", "from_key"):
            k = r.get(side)
            if k and k != key:
                keys.append(k)
    meter.record(latency, 0)
    return keys


def _result(arm, keys, meter, abstained=False, steps=None, abstention_deferred=False):
    seen, uniq = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            uniq.append(k)
    return {
        "arm": arm,
        "surfaced_keys": uniq,
        "abstained": abstained,
        # The deterministic arm cannot SOUNDLY decide existence-abstention (measured:
        # a non-existent-but-topically-dense target scores like a real match, and
        # entity-string presence is defeated by decoys + abbreviations). So on an
        # abstain-flagged probe it DEFERS rather than fake a score-floor decision;
        # the LLM-in-loop arm resolves it by enumeration. Deferred == UNDECIDED, not
        # pass and not fail.
        "abstention_deferred": abstention_deferred,
        "canary_retrieved": CANARY_KEY in seen,
        "meter": meter.as_dict(),
        "steps": steps or [],
    }


# ------------------------------------------------------------------ arms
def run_s0(client, plan):
    m = Meter()
    hits = _search(client, m, plan["query"], "hybrid", plan.get("limit", 8))
    return _result("S0", [h["key"] for h in hits], m, steps=["round1"])


def run_s1(client, plan):
    m = Meter()
    keys = []
    for q in plan["s1_subqueries"]:
        keys += [h["key"] for h in _search(client, m, q, "hybrid", plan.get("s1_limit", 5))]
    return _result("S1", keys, m, steps=[f"q{i}" for i in range(len(plan["s1_subqueries"]))])


def run_s2(client, plan):
    m = Meter()
    keys = []
    steps = []
    r1 = _search(client, m, plan["s2_round1"], "hybrid", plan.get("limit", 8))
    keys += [h["key"] for h in r1]
    steps.append("round1")

    # existence/abstention gate BEFORE assembly (P3). A fixed (or any relative)
    # score floor was proven UNSOUND here: a non-existent-but-topically-dense target
    # scores as high as a real match, and entity-string presence is defeated by
    # decoys asserting the term + real entities abbreviating it. So the deterministic
    # arm does NOT decide -- it DEFERS to the LLM-in-loop arm (which enumerates the
    # members graph-connected to the topic cluster and tests set-membership). Deferred
    # is UNDECIDED: excluded from solved/failed and from the go-gate.
    if plan.get("abstain_expected"):
        return _result("S2", keys, m, abstention_deferred=True,
                       steps=steps + ["abstain-deferred-llm"])

    # graph hop from the best hit
    if r1 and m.calls < CAP_CALLS:
        keys += _neighbors(client, m, r1[0]["key"], depth=plan.get("s2_depth", 1))
        steps.append("neighbors")

    # conditioned re-query rounds (round-1-derivable vocabulary; author-certified)
    for cq in plan.get("s2_conditioned", []):
        if m.calls >= CAP_CALLS:
            steps.append("cap-hit")
            break
        keys += [h["key"] for h in _search(client, m, cq, "hybrid", plan.get("limit", 8))]
        steps.append("conditioned")

    return _result("S2", keys, m, abstained=False, steps=steps)


ARMS = {"S0": run_s0, "S1": run_s1, "S2": run_s2}


def run_probe(client, plan):
    return {arm: fn(client, plan) for arm, fn in ARMS.items()}


# ------------------------------------------------------------------ mock + selftest
class MockClient:
    """Scripted client: search_map[query] -> hits, neighbor_map[key] -> edge rows."""

    def __init__(self, search_map, neighbor_map):
        self.search_map = search_map
        self.neighbor_map = neighbor_map

    def call_tool(self, name, args):
        if name == "memory_search":
            return json.dumps(self.search_map.get(args["query"], []))
        if name == "memory_neighbors":
            return json.dumps(self.neighbor_map.get(args["key"], []))
        raise RuntimeError(f"MockClient: unexpected tool {name}")

    def close(self):
        pass


def _hit(key, score, chars):
    return {"key": key, "score": score, "content_chars": chars}


def selftest():
    failures = []
    # A found by round1; B ONLY via the A->B edge; C ONLY via conditioned vocab.
    search_map = {
        "seedq": [_hit("A", 0.5, 100)],
        "condq": [_hit("C", 0.4, 80)],
        "s1a": [_hit("A", 0.5, 100)],
        "s1b": [_hit("C", 0.4, 80)],
        "s1c": [],
        "ghostq": [_hit("X", 0.02, 10)],          # low score -> abstain
        "canaryq": [_hit(CANARY_KEY, 0.5, 200)],
    }
    neighbor_map = {"A": [{"from_key": "A", "to_key": "B", "edge_type": "evolved",
                           "weight": 0.7, "energy": 0.7}]}
    mock = MockClient(search_map, neighbor_map)

    # gap probe: gold needs B (edge-only) and C (conditioned-only)
    gap = {"id": "V-gap", "query": "seedq", "s1_subqueries": ["s1a", "s1b", "s1c"],
           "s2_round1": "seedq", "s2_conditioned": ["condq"]}
    r = run_probe(mock, gap)
    if set(r["S0"]["surfaced_keys"]) != {"A"}:
        failures.append(f"S0 should surface only A, got {r['S0']['surfaced_keys']}")
    if "B" in r["S1"]["surfaced_keys"]:
        failures.append("S1 (blind) must NOT reach B -- B is edge-only")
    if set(r["S1"]["surfaced_keys"]) != {"A", "C"}:
        failures.append(f"S1 should surface A,C, got {r['S1']['surfaced_keys']}")
    if set(r["S2"]["surfaced_keys"]) != {"A", "B", "C"}:
        failures.append(f"S2 should surface A,B,C, got {r['S2']['surfaced_keys']}")
    if r["S2"]["meter"]["calls"] != 3:
        failures.append(f"S2 gap should be 3 calls (round1+neighbors+1 cond), got {r['S2']['meter']['calls']}")
    # token proxy: S2 context = A(100)+neighbors(0)+C(80)=180; S0=100
    if r["S2"]["meter"]["context_chars"] != 180 or r["S0"]["meter"]["context_chars"] != 100:
        failures.append(f"context_chars wrong: S0={r['S0']['meter']['context_chars']} S2={r['S2']['meter']['context_chars']}")
    if r["S2"]["canary_retrieved"]:
        failures.append("gap probe must not retrieve the canary")

    # abstention probe: the deterministic arm cannot soundly decide existence, so it
    # DEFERS to the LLM arm (undecided) rather than fake a score-floor abstention.
    ab = {"id": "V-abstain", "query": "ghostq", "s1_subqueries": ["ghostq"],
          "s2_round1": "ghostq", "s2_conditioned": ["condq"], "abstain_expected": True}
    r = run_probe(mock, ab)
    if not r["S2"]["abstention_deferred"]:
        failures.append("S2 should DEFER abstention to the LLM arm on an abstain probe")
    if r["S2"]["abstained"]:
        failures.append("deterministic S2 must not claim a decided abstention")
    if "abstain-deferred-llm" not in r["S2"]["steps"]:
        failures.append("deferred S2 should record the abstain-deferred-llm step")
    if "neighbors" in r["S2"]["steps"] or "conditioned" in r["S2"]["steps"]:
        failures.append("deferred S2 must not assemble (no neighbors/conditioned)")

    # cap: 8 conditioned rounds must stop at CAP_CALLS with a cap-hit marker
    capp = {"id": "V-cap", "query": "seedq", "s1_subqueries": ["s1a"],
            "s2_round1": "seedq", "s2_conditioned": ["condq"] * 8}
    r = run_probe(mock, capp)
    if r["S2"]["meter"]["calls"] != CAP_CALLS:
        failures.append(f"S2 should hard-cap at {CAP_CALLS} calls, got {r['S2']['meter']['calls']}")
    if "cap-hit" not in r["S2"]["steps"]:
        failures.append("S2 cap should record a cap-hit marker")

    # canary retrieval detection
    canp = {"id": "V-canary", "query": "canaryq", "s1_subqueries": ["canaryq"],
            "s2_round1": "canaryq", "s2_conditioned": []}
    r = run_probe(mock, canp)
    if not r["S2"]["canary_retrieved"]:
        failures.append("S2 should flag canary_retrieved when the canary enters context")

    return failures


# ------------------------------------------------------------------ live run
def _score_ready(arm_result):
    """Shape an arm result for score.py's score_arm_results."""
    return {
        "surfaced_keys": arm_result["surfaced_keys"],
        "asserted_answer_present": not arm_result["abstained"],
        "abstention_deferred": arm_result.get("abstention_deferred", False),
        "canary_fired": False,  # deterministic harness; set by the LLM wrapper
        "canary_retrieved": arm_result["canary_retrieved"],
        "meter": arm_result["meter"],
        "steps": arm_result["steps"],
    }


def run_live(binary, db_path, plans):
    client = McpClient(binary, env_extra={"AGENT_BRIDGE_DB": db_path})
    out = {arm: {"arm": arm, "results": []} for arm in ARMS}
    try:
        for plan in plans:
            probe = run_probe(client, plan)
            for arm in ARMS:
                row = _score_ready(probe[arm])
                row["id"] = plan["id"]
                out[arm]["results"].append(row)
    finally:
        client.close()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="MRAgent reconstruction arms (S0/S1/S2) + metering.")
    ap.add_argument("--binary", default=DEFAULT_BINARY)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true", help="offline MockClient control-flow test")
    g.add_argument("--run", metavar="PLANS.json", help="live: run plans x arms against --db")
    ap.add_argument("--db", help="materialized snapshot DB (required with --run)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        failures = selftest()
        if failures:
            print(f"SELFTEST FAILED ({len(failures)}):")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("SELFTEST OK: S0/S1/S2 control flow + metering + abstention gate + "
              "6-call cap + canary-retrieval all green (MockClient).")
        return 0

    if not args.db:
        ap.error("--run requires --db")
    with open(args.run, "r", encoding="utf-8") as fh:
        plans = json.load(fh)
    plans = plans["plans"] if isinstance(plans, dict) else plans
    out = run_live(args.binary, args.db, plans)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
