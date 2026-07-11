#!/usr/bin/env python3
"""Ambient stage-2 data-gate probe — is the bootstrap telemetry ripe yet?

Stage 1 (PR #72) writes session_bootstrap's semantic page to
retrieval_surfacing as mode=bootstrap, quarantined from every reinforce/decay
aggregate. Stage 2 (calibrate an ambient-specific rule + mode-sliced shadow)
was gated on data accumulation. This probe reads only explicitly organic
ambient traffic and prints an OPEN/WAIT/BLOCKED verdict. Evaluation and
historical unknown traffic never contribute to the gate. Read-only; never part
of ab_eval baselines (maturation gate, not a regression component).

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
import datetime
import json
import os
from pathlib import Path
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
VALID_TRAFFIC_CLASSES = {"unknown", "organic", "eval"}


def _open_read_only(db_path):
    uri = Path(db_path).expanduser().resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    db.execute("PRAGMA query_only=ON")
    if db.execute("PRAGMA query_only").fetchone()[0] != 1:
        db.close()
        raise RuntimeError("SQLite query_only could not be enabled")
    return db


def _day(timestamp):
    return datetime.datetime.fromtimestamp(
        timestamp, tz=datetime.timezone.utc
    ).date().isoformat()


def _traffic_class(value):
    if isinstance(value, str):
        value = value.strip().lower()
        if value in VALID_TRAFFIC_CLASSES:
            return value
    return "invalid_or_unlabeled"


def probe(db_path):
    db = _open_read_only(db_path)
    db.execute("BEGIN")
    db.execute("SELECT count(*) FROM sqlite_master").fetchone()
    start_changes = db.total_changes
    try:
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "retrieval_surfacing" not in tables:
            raise RuntimeError("missing required table: retrieval_surfacing")
        columns = {
            row[1] for row in db.execute("PRAGMA table_info(retrieval_surfacing)")
        }
        required = {"memory_key", "mode", "rank", "surfaced_at", "used_at"}
        missing = required - columns
        if missing:
            raise RuntimeError("missing required columns: " + ", ".join(sorted(missing)))
        traffic_class_present = "traffic_class" in columns
        fields = "memory_key, rank, surfaced_at, used_at"
        if traffic_class_present:
            fields += ", traffic_class"
        raw_rows = db.execute(
            f"SELECT {fields} FROM retrieval_surfacing WHERE mode='bootstrap'"
        ).fetchall()
        rows = []
        for raw in raw_rows:
            rows.append(
                {
                    "memory_key": raw[0],
                    "rank": int(raw[1]),
                    "surfaced_at": int(raw[2]),
                    "used_at": None if raw[3] is None else int(raw[3]),
                    "traffic_class": (
                        _traffic_class(raw[4])
                        if traffic_class_present
                        else "unobservable"
                    ),
                }
            )

        class_counts = {}
        for row in rows:
            label = row["traffic_class"]
            class_counts[label] = class_counts.get(label, 0) + 1
        organic_rows = [
            row for row in rows if row["traffic_class"] == "organic"
        ]
        first_organic = min(
            (row["surfaced_at"] for row in organic_rows), default=None
        )
        post_label_unknown_rows = (
            0
            if first_organic is None
            else sum(
                1
                for row in rows
                if row["surfaced_at"] >= first_organic
                and row["traffic_class"] not in {"organic", "eval"}
            )
        )

        exposure_days = {}
        stamp_days = {}
        bands = {
            "r00-05": [0, 0],
            "r06-15": [0, 0],
            "r16-30": [0, 0],
            "r31+": [0, 0],
        }
        for row in organic_rows:
            surfaced_day = _day(row["surfaced_at"])
            day_entry = exposure_days.setdefault(surfaced_day, [0, set()])
            day_entry[0] += 1
            day_entry[1].add(row["memory_key"])
            if row["rank"] <= 5:
                band = "r00-05"
            elif row["rank"] <= 15:
                band = "r06-15"
            elif row["rank"] <= 30:
                band = "r16-30"
            else:
                band = "r31+"
            bands[band][0] += 1
            if row["used_at"] is not None:
                bands[band][1] += 1
                used_day = _day(row["used_at"])
                stamp_days[used_day] = stamp_days.get(used_day, 0) + 1

        organic_used = [row for row in organic_rows if row["used_at"] is not None]
        total_stamps = len(organic_used)
        distinct_days = len(stamp_days)
        clean_stamps = sum(
            1
            for row in organic_used
            if row["rank"] <= CLEAN_RANK_MAX
            and not row["memory_key"].startswith("distill_draft_")
        )

        per_day = [
            (day, values[0], len(values[1]))
            for day, values in sorted(exposure_days.items())
        ]
        stamps_per_day = sorted(stamp_days.items())
        rank_curve = [
            (band, values[0], values[1]) for band, values in bands.items()
        ]
        end_changes = db.total_changes
    finally:
        db.close()

    conditions = {
        f"total_stamps>={GATE_TOTAL_STAMPS}": total_stamps >= GATE_TOTAL_STAMPS,
        f"distinct_days>={GATE_DISTINCT_DAYS}": distinct_days >= GATE_DISTINCT_DAYS,
        f"clean_stamps>={GATE_CLEAN_STAMPS}": clean_stamps >= GATE_CLEAN_STAMPS,
    }
    if not traffic_class_present:
        verdict = "BLOCKED_NEEDS_TRAFFIC_CLASS"
    elif first_organic is None:
        verdict = "WAIT_LABELLED_DATA"
    elif post_label_unknown_rows:
        verdict = "BLOCKED_PARTIAL_TRAFFIC_CLASS"
    else:
        verdict = "OPEN" if all(conditions.values()) else "WAIT"

    return {
        "traffic_class_column_present": traffic_class_present,
        "bootstrap_traffic_class_counts": dict(sorted(class_counts.items())),
        "first_organic_surfaced_at": first_organic,
        "post_label_unknown_rows": post_label_unknown_rows,
        "eval_rows_excluded": class_counts.get("eval", 0),
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
        "verdict": verdict,
        "no_write_invariant": {
            "sqlite_uri_mode": "ro",
            "query_only": True,
            "consistent_read_snapshot": True,
            "connection_total_changes_before": start_changes,
            "connection_total_changes_after": end_changes,
            "passed": start_changes == 0 and end_changes == 0,
        },
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
        print(
            "traffic_class: "
            + ("present" if r["traffic_class_column_present"] else "absent")
        )
        print(f"bootstrap classes: {r['bootstrap_traffic_class_counts']}")
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
