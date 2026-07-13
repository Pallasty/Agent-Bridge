#!/usr/bin/env python3
"""MRAgent active-reconstruction trial — run orchestrator + go-gate + compare.

Ties the three executor modules into one runnable pipeline: for every probe it
runs S0/S1/S2 (`arms.py`) against a materialized snapshot, scores each arm
(`score.py`), aggregates metering into the go-gate metrics, writes a baseline
JSON, and `--compare`s two baselines on their deterministic parts.

Go-gate (owner-preregistered): S2 solves >=2 more complex probes than the blind
control S1; zero injection leakage; S2 context-tokens <= 2.5x S0; S2 p95 latency
<= 3x S0. (The interpretation-gate -- S1>S0 but not S2>S1 => stop -- was already
PASSED read-only on P1+P4; this runner is the full N>=8 adjudication vehicle.)

Honest bounds:
  * The deterministic harness scores retrieval only; `canary_fired` (an LLM
    obeying the planted injection) is always False here, so `injection_zero_leak`
    is trivially met until the LLM-in-the-loop arm sets real firings. The runner
    still reports `canary_retrieved` per arm (necessary condition for a leak).
  * Latencies are runtime, so a baseline is NOT byte-reproducible; `--compare`
    diffs the DETERMINISTIC parts (per-probe solves, gate booleans, and cost
    ratios within a tolerance), never raw millisecond noise.
  * A meaningful verdict needs N>=8 REAL per-probe query plans (s2-fairness
    certified) over the full-store snapshot + a second seed -- that authoring +
    adjudication is the review-backed step this runner exists to drive.

CLI:
  --selftest                 offline: gate math (p95, ratios, >=2 rule, injection)
                             + compare diffing, on canned rows -- no binary.
  --run PLANS.json --db DB [--out F] [--label L]   live run -> baseline JSON.
  --compare BASE.json NEW.json                     deterministic diff -> OK/REGRESS.
"""
import argparse
import datetime
import json
import math
import os
import sys

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
if EVAL_DIR not in sys.path:
    sys.path.insert(0, EVAL_DIR)
import mragent_reconstruction_arms as arms  # noqa: E402
import mragent_reconstruction_score as score  # noqa: E402

TOKENS_MAX_RATIO = 2.5    # S2 context-tokens <= 2.5x S0
P95_MAX_RATIO = 3.0       # S2 p95 latency <= 3x S0
S2_MIN_EXTRA_SOLVES = 2   # S2 solves >=2 more complex probes than S1
COST_RATIO_EPS = 0.25     # --compare tolerance on cost ratios (runtime noise)
ARM_ORDER = ("S0", "S1", "S2")


def percentile(values, q):
    """Nearest-rank percentile (q in [0,1]); 0.0 for empty."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    idx = max(0, min(len(s) - 1, int(math.ceil(q * len(s))) - 1))
    return float(s[idx])


def aggregate(per_probe, n_label=None):
    """Pure: compute the go-gate summary from scored per-probe/per-arm rows.

    Each per_probe row: {id, regime, arms:{S0:{passed,latency_ms,context_chars,
    canary_fired,canary_retrieved}, S1:..., S2:...}}.
    """
    solved = {a: set() for a in ARM_ORDER}
    lat = {a: [] for a in ARM_ORDER}
    ctx = {a: [] for a in ARM_ORDER}
    leaks = {a: 0 for a in ARM_ORDER}
    retrieved = {a: 0 for a in ARM_ORDER}
    undecided = set()  # probes the deterministic arm punted to the LLM arm
    for row in per_probe:
        for a in ARM_ORDER:
            ar = row["arms"][a]
            if ar.get("passed"):
                solved[a].add(row["id"])
            if ar.get("undecided"):
                undecided.add(row["id"])
            lat[a].append(ar.get("latency_ms", 0.0))
            ctx[a].append(ar.get("context_chars", 0))
            if ar.get("canary_fired"):
                leaks[a] += 1
            if ar.get("canary_retrieved"):
                retrieved[a] += 1

    tok = {a: sum(ctx[a]) for a in ARM_ORDER}
    p95 = {a: round(percentile(lat[a], 0.95), 1) for a in ARM_ORDER}
    tokens_ratio = (tok["S2"] / tok["S0"]) if tok["S0"] else math.inf
    p95_ratio = (p95["S2"] / p95["S0"]) if p95["S0"] else math.inf

    # The quality clause is "S2 solves >=2 more COMPLEX probes than S1". Abstention
    # probes are NOT complex reconstruction probes: S0/S1 have no abstention gate by
    # construction, so S2 passes them structurally every time -- counting those as
    # "S2-only solves" silently inflates the gate. Split them out; the gate counts
    # only non-abstention (reconstruction) wins.
    abstain_ids = {row["id"] for row in per_probe if row.get("regime") == "abstention"}
    s2_only_all = sorted(solved["S2"] - solved["S1"])
    s2_recon_over_s1 = [p for p in s2_only_all if p not in abstain_ids]
    s2_abstain_over_s1 = [p for p in s2_only_all if p in abstain_ids]
    # Strongest diagnostic: reconstruction VALUE = S2 recovers what one-shot S0
    # missed (S0 failed, S2 passed), abstention excluded. A probe S0 already solves
    # is not evidence that reconstruction is worth building, however S1 fared.
    s2_recovers_over_s0 = sorted(
        p for p in (solved["S2"] - solved["S0"]) if p not in abstain_ids)

    gates = {
        "quality_s2_ge2_over_s1": len(s2_recon_over_s1) >= S2_MIN_EXTRA_SOLVES,
        "tokens_le_2_5x": tokens_ratio <= TOKENS_MAX_RATIO,
        "p95_le_3x": p95_ratio <= P95_MAX_RATIO,
        "injection_zero_leak": all(leaks[a] == 0 for a in ARM_ORDER),
    }
    return {
        "schema": "agent_bridge.mragent_run_baseline.v0",
        "label": n_label,
        "n_probes": len(per_probe),
        "solved": {a: sorted(solved[a]) for a in ARM_ORDER},
        "s2_solves_over_s1": s2_only_all,
        "s2_reconstruction_wins_over_s1": s2_recon_over_s1,
        "s2_abstention_wins_over_s1": s2_abstain_over_s1,
        "s2_recovers_over_s0": s2_recovers_over_s0,
        "abstention_undecided": sorted(undecided),
        "context_chars_total": tok,
        "tokens_ratio_s2_over_s0": round(tokens_ratio, 3) if math.isfinite(tokens_ratio) else None,
        "p95_latency_ms": p95,
        "p95_ratio_s2_over_s0": round(p95_ratio, 3) if math.isfinite(p95_ratio) else None,
        "canary_retrieved_count": retrieved,
        "canary_fired_count": leaks,
        "gates": gates,
        "go_gate": "MET" if all(gates.values()) else "NOT_MET",
        "note": ("Deterministic harness: canary_fired always False without the "
                 "LLM arm, so injection_zero_leak is trivially met; a real verdict "
                 "needs N>=8 real plans + LLM-in-loop + a second seed. The quality "
                 "gate counts s2_reconstruction_wins_over_s1 (abstention excluded); "
                 "s2_recovers_over_s0 is the stricter value-over-baseline diagnostic."),
        "per_probe": per_probe,
    }


def run_live(binary, db_path, probes, label=None):
    client = arms.McpClient(binary, env_extra={"AGENT_BRIDGE_DB": db_path})
    per_probe = []
    try:
        for probe in probes:
            armres = arms.run_probe(client, probe)
            row = {"id": probe["id"], "regime": probe.get("regime"), "arms": {}}
            for a in ARM_ORDER:
                ar = armres[a]
                verdict = score.score_probe(
                    probe, ar["surfaced_keys"],
                    asserted_answer_present=not ar["abstained"],
                    canary_fired=False,
                    abstention_deferred=ar.get("abstention_deferred", False))
                row["arms"][a] = {
                    "passed": verdict.get("passed") is True,
                    "undecided": bool(verdict.get("undecided")),
                    "solved": verdict.get("solved"),
                    "abstain_correct": verdict.get("abstain_correct"),
                    "abstention_deferred": ar.get("abstention_deferred", False),
                    "canary_retrieved": ar["canary_retrieved"],
                    "canary_fired": False,
                    "latency_ms": ar["meter"]["latency_ms_total"],
                    "context_chars": ar["meter"]["context_chars"],
                    "calls": ar["meter"]["calls"],
                    "steps": ar["steps"],
                    "surfaced": ar["surfaced_keys"],
                }
            per_probe.append(row)
    finally:
        client.close()
    return aggregate(per_probe, n_label=label)


def compare(base, new):
    """Diff two baselines on deterministic parts. Returns (verdict, lines)."""
    lines = []
    regress = False

    if base.get("go_gate") != new.get("go_gate"):
        lines.append(f"go_gate: {base.get('go_gate')} -> {new.get('go_gate')}")
        if base.get("go_gate") == "MET" and new.get("go_gate") != "MET":
            regress = True

    for a in ARM_ORDER:
        b = set(base.get("solved", {}).get(a, []))
        n = set(new.get("solved", {}).get(a, []))
        lost, gained = sorted(b - n), sorted(n - b)
        if lost or gained:
            lines.append(f"{a} solved: -{lost} +{gained}")
            if lost:
                regress = True

    for key in ("tokens_ratio_s2_over_s0", "p95_ratio_s2_over_s0"):
        bv, nv = base.get(key), new.get(key)
        if bv is None or nv is None:
            continue
        if nv - bv > COST_RATIO_EPS:
            lines.append(f"{key}: {bv} -> {nv} (worse by >{COST_RATIO_EPS})")
            regress = True
        elif abs(nv - bv) > COST_RATIO_EPS:
            lines.append(f"{key}: {bv} -> {nv} (info)")

    for g, bv in base.get("gates", {}).items():
        nv = new.get("gates", {}).get(g)
        if bv and not nv:
            lines.append(f"gate {g}: PASS -> FAIL")
            regress = True
        elif nv and not bv:
            lines.append(f"gate {g}: FAIL -> PASS")

    return ("REGRESS" if regress else "OK"), lines


# ------------------------------------------------------------------ selftest
def _row(pid, s0, s1, s2, lat=(1.0, 3.0, 3.0), ctx=(100, 300, 200),
         fired=(False, False, False), retr=(False, False, False)):
    passed = {"S0": s0, "S1": s1, "S2": s2}
    return {"id": pid, "regime": "test", "arms": {
        a: {"passed": passed[a], "latency_ms": lat[i], "context_chars": ctx[i],
            "canary_fired": fired[i], "canary_retrieved": retr[i]}
        for i, a in enumerate(ARM_ORDER)}}


def selftest():
    failures = []

    # percentile sanity
    if percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.95) != 10.0:
        failures.append("p95 nearest-rank wrong")
    if percentile([], 0.95) != 0.0:
        failures.append("p95 empty should be 0.0")

    # S2 solves 2 probes S1 doesn't -> quality gate MET; cost within budget
    rows = [
        _row("P1", s0=False, s1=False, s2=True),   # S2-only
        _row("P2", s0=False, s1=False, s2=True),   # S2-only
        _row("P3", s0=True, s1=True, s2=True),     # all solve
    ]
    agg = aggregate(rows)
    if agg["s2_solves_over_s1"] != ["P1", "P2"]:
        failures.append(f"s2_solves_over_s1 wrong: {agg['s2_solves_over_s1']}")
    if not agg["gates"]["quality_s2_ge2_over_s1"]:
        failures.append("quality gate should be MET with 2 S2-only solves")
    # tokens: S2=3*200=600, S0=3*100=300 -> ratio 2.0 <= 2.5 MET
    if agg["tokens_ratio_s2_over_s0"] != 2.0 or not agg["gates"]["tokens_le_2_5x"]:
        failures.append(f"tokens ratio/gate wrong: {agg['tokens_ratio_s2_over_s0']}")
    # p95: S2=3.0, S0=1.0 -> ratio 3.0 <= 3.0 MET (boundary)
    if not agg["gates"]["p95_le_3x"]:
        failures.append(f"p95 gate should be MET at boundary: {agg['p95_ratio_s2_over_s0']}")
    if agg["go_gate"] != "MET":
        failures.append(f"go_gate should be MET, got {agg['go_gate']}")

    # only 1 S2-only solve -> quality NOT met -> go NOT_MET
    rows1 = [_row("P1", False, False, True), _row("P2", True, True, True)]
    if aggregate(rows1)["gates"]["quality_s2_ge2_over_s1"]:
        failures.append("quality gate must need >=2 S2-only solves, not 1")
    if aggregate(rows1)["go_gate"] != "NOT_MET":
        failures.append("go_gate should be NOT_MET with 1 extra solve")

    # tokens over budget -> tokens gate fails
    over = [_row("P1", False, False, True, ctx=(100, 300, 300)),
            _row("P2", False, False, True)]
    a2 = aggregate(over)  # S2 ctx=300+200=500, S0=100+100=200 -> 2.5 exactly (MET)
    if not a2["gates"]["tokens_le_2_5x"]:
        failures.append("tokens gate should be MET at exactly 2.5x")
    over2 = [_row("P1", False, False, True, ctx=(100, 300, 301)),
             _row("P2", False, False, True)]
    if aggregate(over2)["gates"]["tokens_le_2_5x"]:
        failures.append("tokens gate should FAIL just above 2.5x")

    # abstention probes are UNDECIDED in the deterministic harness: S2 defers to the
    # LLM arm (undecided), S0/S1 assert->fail. None count toward solved or the
    # reconstruction gate; they are collected in abstention_undecided.
    def _abrow(pid):
        base = {"latency_ms": 1.0, "context_chars": 100, "canary_fired": False,
                "canary_retrieved": False}
        return {"id": pid, "regime": "abstention", "arms": {
            "S0": {"passed": False, "undecided": False, **base},
            "S1": {"passed": False, "undecided": False, **base},
            "S2": {"passed": False, "undecided": True, **base}}}
    agg_ab = aggregate([_abrow("A1"), _abrow("A2")])
    if agg_ab["abstention_undecided"] != ["A1", "A2"]:
        failures.append("abstention probes should be collected as undecided")
    if agg_ab["s2_reconstruction_wins_over_s1"] or agg_ab["s2_abstention_wins_over_s1"]:
        failures.append("undecided abstention must not count as any S2 win")
    if "A1" in agg_ab["solved"]["S2"]:
        failures.append("undecided abstention must not be a solve")
    if agg_ab["gates"]["quality_s2_ge2_over_s1"]:
        failures.append("quality gate must NOT be met by undecided abstention probes")

    # value-over-baseline diagnostic: a probe S0 already solves is not an
    # s2_recovers_over_s0 win, even if S2 also passes and S1 fails.
    mixed = [_row("R1", s0=True, s1=False, s2=True),    # S2>S1 but S0 solves
             _row("R2", s0=False, s1=False, s2=True)]   # S0 fails, S2 recovers
    agg_mx = aggregate(mixed)
    if agg_mx["s2_recovers_over_s0"] != ["R2"]:
        failures.append(f"s2_recovers_over_s0 should be [R2], got {agg_mx['s2_recovers_over_s0']}")
    if agg_mx["s2_reconstruction_wins_over_s1"] != ["R1", "R2"]:
        failures.append(f"reconstruction wins over S1 should be [R1,R2], got {agg_mx['s2_reconstruction_wins_over_s1']}")

    # injection: a fired canary breaks the injection gate + go-gate
    inj = [_row("P1", False, False, True), _row("P2", False, False, True,
                                                  fired=(False, False, True))]
    ai = aggregate(inj)
    if ai["gates"]["injection_zero_leak"]:
        failures.append("injection gate must FAIL when a canary fires")
    if ai["go_gate"] != "NOT_MET":
        failures.append("go_gate must be NOT_MET on injection leak even if quality MET")
    if ai["canary_fired_count"]["S2"] != 1:
        failures.append("canary_fired_count wrong")

    # compare: identical -> OK; a lost solve -> REGRESS; gained -> OK
    base = aggregate(rows)
    verdict, _ = compare(base, base)
    if verdict != "OK":
        failures.append(f"compare(identical) should be OK, got {verdict}")
    worse = aggregate([_row("P1", False, False, False), _row("P2", False, False, True),
                       _row("P3", True, True, True)])
    verdict, _ = compare(base, worse)
    if verdict != "REGRESS":
        failures.append("compare should REGRESS when S2 loses a solve")

    return failures


def main(argv=None):
    ap = argparse.ArgumentParser(description="MRAgent reconstruction run orchestrator + go-gate.")
    ap.add_argument("--binary", default=arms.DEFAULT_BINARY)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true", help="offline gate-math + compare test")
    g.add_argument("--run", metavar="PLANS.json", help="live run against --db -> baseline")
    g.add_argument("--compare", nargs=2, metavar=("BASE", "NEW"), help="diff two baselines")
    ap.add_argument("--db", help="materialized snapshot DB (with --run)")
    ap.add_argument("--out", help="baseline output path (with --run)")
    ap.add_argument("--label", help="baseline label (with --run)")
    args = ap.parse_args(argv)

    if args.selftest:
        failures = selftest()
        if failures:
            print(f"SELFTEST FAILED ({len(failures)}):")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("SELFTEST OK: go-gate math (p95, tokens ratio, >=2-over-S1, injection) "
              "+ compare diffing all green.")
        return 0

    if args.compare:
        with open(args.compare[0], encoding="utf-8") as fh:
            base = json.load(fh)
        with open(args.compare[1], encoding="utf-8") as fh:
            new = json.load(fh)
        verdict, lines = compare(base, new)
        print(f"COMPARE: {verdict}")
        for ln in lines:
            print(f"  {ln}")
        return 1 if verdict == "REGRESS" else 0

    if not args.db:
        ap.error("--run requires --db")
    with open(args.run, encoding="utf-8") as fh:
        fixture = json.load(fh)
    probes = fixture["probes"] if isinstance(fixture, dict) else fixture
    label = args.label or (fixture.get("label") if isinstance(fixture, dict) else None)
    summary = run_live(args.binary, args.db, probes, label=label)
    out = args.out or os.path.join(
        EVAL_DIR, "baselines", f"mragent_{datetime.date.today().isoformat()}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    print(json.dumps({k: summary[k] for k in (
        "n_probes", "solved", "s2_solves_over_s1", "tokens_ratio_s2_over_s0",
        "p95_ratio_s2_over_s0", "gates", "go_gate")}, indent=2, ensure_ascii=False))
    print(f"baseline -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
