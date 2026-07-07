#!/usr/bin/env python3
"""Ambient stage-2 data-gate probe — is the bootstrap telemetry ripe yet?

Stage 1 (PR #72) writes session_bootstrap's semantic page to
retrieval_surfacing as mode=bootstrap, quarantined from every reinforce/decay
aggregate. Stage 2 (calibrate an ambient-specific rule + mode-sliced shadow)
was gated on data accumulation. This probe reads the ambient slice and prints
an OPEN/WAIT verdict for that gate, so any session can re-check it with one
command. Read-only; never part of ab_eval baselines (maturation gate, not a
regression component).

Label semantics: used_at on an ambient row comes from attribute_retrieval_get
(store), which stamps ALL recent unconsumed surfacings of a key on any
explicit memory_get — mode-blind, rank-blind. Two known pollution sources,
both filtered at read time (stamps carry rank, so no code change needed):
  - distill_draft_* keys: the distillation review workflow memory_gets every
    draft; those stamps measure the review loop, not ambient surfacing value.
    (Source rows fetched during the same review can NOT be cheaply excluded —
    accept as residual noise, tracked by the deep-tail band below.)
  - rank > CLEAN_RANK_MAX: measured 2026-07-07, the deep-tail band (r31+,
    kernel index lines) stamped at 0.47% vs search-mode top-5 at 0.69% —
    near-parity says those gets had independent causes and the stamp is
    key+window coincidence, not surfacing-driven consultation.
"""
import argparse
import json
import os
import sqlite3
import sys

DEFAULT_DB = os.path.expanduser("~/.local/share/agent-bridge/state.db")

# Gate thresholds = calibration-sample floors, not statistical guarantees.
# ~100 stamps is the smallest base on which a rank cutoff + step size can be
# fit without one day dominating; 7 distinct days guards against a single
# workflow burst (2026-07-07: one distill-review session produced 22 of the
# first 30 stamps); >=50 clean stamps keeps the fit from being mostly the
# review loop measuring itself.
GATE_TOTAL_STAMPS = 100
GATE_DISTINCT_DAYS = 7
GATE_CLEAN_STAMPS = 50
CLEAN_RANK_MAX = 30


def probe(db_path):
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c = db.cursor()

    per_day = c.execute(
        "SELECT date(surfaced_at,'unixepoch') d, count(*),"
        "       count(DISTINCT memory_key)"
        " FROM retrieval_surfacing WHERE mode='bootstrap'"
        " GROUP BY d ORDER BY d"
    ).fetchall()

    stamps_per_day = c.execute(
        "SELECT date(used_at,'unixepoch') d, count(*)"
        " FROM retrieval_surfacing"
        " WHERE mode='bootstrap' AND used_at IS NOT NULL"
        " GROUP BY d ORDER BY d"
    ).fetchall()

    rank_curve = c.execute(
        "SELECT CASE WHEN rank<=5 THEN 'r00-05' WHEN rank<=15 THEN 'r06-15'"
        "            WHEN rank<=30 THEN 'r16-30' ELSE 'r31+' END band,"
        "       count(*) exposures,"
        "       sum(CASE WHEN used_at IS NOT NULL THEN 1 ELSE 0 END) used"
        " FROM retrieval_surfacing WHERE mode='bootstrap'"
        " GROUP BY band ORDER BY min(rank)"
    ).fetchall()

    total_stamps = sum(n for _, n in stamps_per_day)
    distinct_days = len(stamps_per_day)
    clean_stamps = c.execute(
        "SELECT count(*) FROM retrieval_surfacing"
        " WHERE mode='bootstrap' AND used_at IS NOT NULL"
        "   AND rank <= ? AND memory_key NOT LIKE 'distill_draft_%'",
        (CLEAN_RANK_MAX,),
    ).fetchone()[0]
    db.close()

    conditions = {
        f"total_stamps>={GATE_TOTAL_STAMPS}": total_stamps >= GATE_TOTAL_STAMPS,
        f"distinct_days>={GATE_DISTINCT_DAYS}": distinct_days >= GATE_DISTINCT_DAYS,
        f"clean_stamps>={GATE_CLEAN_STAMPS}": clean_stamps >= GATE_CLEAN_STAMPS,
    }
    return {
        "ambient_per_day": [
            {"day": d, "exposures": n, "distinct_keys": k} for d, n, k in per_day
        ],
        "stamps_per_day": [{"day": d, "stamps": n} for d, n in stamps_per_day],
        "rank_curve": [
            {
                "band": b,
                "exposures": e,
                "used": u,
                "use_rate_pct": round(100.0 * u / e, 2) if e else 0.0,
            }
            for b, e, u in rank_curve
        ],
        "total_stamps": total_stamps,
        "distinct_stamp_days": distinct_days,
        "clean_stamps": clean_stamps,
        "conditions": conditions,
        "verdict": "OPEN" if all(conditions.values()) else "WAIT",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    r = probe(args.db)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print("# ambient stage-2 data gate")
        print(f"DB: {args.db}")
        for row in r["ambient_per_day"]:
            print(f"  {row['day']}  exposures={row['exposures']:>5}  keys={row['distinct_keys']}")
        print("stamps/day: " + (", ".join(
            f"{s['day']}:{s['stamps']}" for s in r["stamps_per_day"]) or "none"))
        print("use-rate by rank band:")
        for b in r["rank_curve"]:
            print(f"  {b['band']}  {b['used']}/{b['exposures']}  ({b['use_rate_pct']}%)")
        print(f"total_stamps={r['total_stamps']}  distinct_days={r['distinct_stamp_days']}"
              f"  clean_stamps={r['clean_stamps']} (rank<={CLEAN_RANK_MAX},"
              " non-distill_draft)")
        for cond, ok in r["conditions"].items():
            print(f"  [{'x' if ok else ' '}] {cond}")
        print(f"verdict: {r['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
