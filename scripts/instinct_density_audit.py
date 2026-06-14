#!/usr/bin/env python3
"""delta① observer audit snapshot — analyze the observer sidecar log.

Reads the observer sidecar log written by ab-instinct-observer-hook and
estimates the per-session density of clean
behavioral signals, to decide whether an auto-miner is worth building.
Spec/falsifier: docs/design/ECC_INSTINCT_MINING_PROBE_2026_05_24.md (Phase 0b).

Two signal classes (heuristic — an upper-bound proxy; the real miner would use
an LLM pass for precision, this just answers "is there ENOUGH to bother?"):

  - correction  : a UserPromptSubmit whose text carries negation / redirection
                  cues right after assistant action ("不对/应该/instead/revert"…)
  - error-resln : a PostToolUse with a CLEAN error signal that is later followed
                  (same session) by a SUCCESS of the same tool — i.e. a fix
                  landed. stderr-only records are reported as sensor noise, not
                  counted as errors.

Gate (frozen): mean mineable signals/session >= ~1 over >=5 sessions -> proceed
to Phase 1 miner. Below that -> NO_SIGNAL (don't build it).

Usage:  python3 scripts/instinct_density_audit.py [--log PATH] [--json]
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

def default_log_path():
    explicit = os.environ.get("AB_INSTINCT_OBSERVER_LOG", "").strip()
    if explicit:
        return os.path.expanduser(explicit)
    if os.path.isdir("/Data") and os.access("/Data", os.W_OK):
        return "/Data/agent-bridge/instinct-probe/observations.jsonl"
    return os.path.expanduser("~/.cache/agent-bridge/instinct-probe/observations.jsonl")


DEFAULT_LOG = default_log_path()

# Bilingual negation / redirection cues. Deliberately broad (density is an
# upper-bound estimate; FPs are acceptable, FNs would hide real signal).
CORRECTION_CUES = [
    "不对", "不是", "错了", "错误", "应该", "而不是", "别这样", "不要", "其实",
    "重来", "撤销", "回退", "改成", "不行", "有问题", "搞错", "弄反",
    "no,", "not quite", "that's not", "that is not", "wrong", "actually",
    "instead", "should be", "should not", "shouldn't", "don't", "do not",
    "revert", "undo", "rollback", "mistake", "incorrect", "fix that", "no.",
]


def classify_prompt(text):
    low = text.lower()
    return any(cue in text or cue in low for cue in CORRECTION_CUES)


def is_clean_error(record):
    return bool(record.get("err") and record.get("err_source"))


def load(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def analyze(rows):
    by_sid = defaultdict(lambda: {
        "prompts": 0, "corrections": 0, "tools": 0,
        "clean_errors": 0, "clean_error_resolutions": 0,
        "stderr_success": 0, "legacy_untrusted_errors": 0,
        "legacy_error_resolutions": 0,
        "_clean_err_pending": defaultdict(int),
        "_legacy_err_pending": defaultdict(int),
    })
    # chronological per session for error->fix detection
    rows = sorted(rows, key=lambda r: r.get("ts", 0))
    for r in rows:
        sid = r.get("sid", "?")
        s = by_sid[sid]
        ev = r.get("ev")
        if ev == "UserPromptSubmit":
            s["prompts"] += 1
            if classify_prompt(r.get("prompt", "")):
                s["corrections"] += 1
        elif ev == "PostToolUse":
            s["tools"] += 1
            tool = r.get("tool", "?")
            clean_err = is_clean_error(r)
            legacy_err = bool(r.get("err"))
            stderr_success = bool(r.get("stderr_nonempty")) and not clean_err
            legacy_untrusted = legacy_err and not r.get("err_source")
            if stderr_success:
                s["stderr_success"] += 1
            if legacy_untrusted:
                s["legacy_untrusted_errors"] += 1

            if clean_err:
                s["clean_errors"] += 1
                s["_clean_err_pending"][tool] += 1
            elif s["_clean_err_pending"].get(tool, 0) > 0:
                # a success of a tool that previously errored = resolution
                s["clean_error_resolutions"] += 1
                s["_clean_err_pending"][tool] -= 1

            # Preserve the old upper-bound line so we can see how much of the
            # previous density came from untrusted stderr-derived errors.
            if legacy_err:
                s["_legacy_err_pending"][tool] += 1
            elif s["_legacy_err_pending"].get(tool, 0) > 0:
                s["legacy_error_resolutions"] += 1
                s["_legacy_err_pending"][tool] -= 1
    # finalize
    sessions = {}
    for sid, s in by_sid.items():
        s.pop("_clean_err_pending", None)
        s.pop("_legacy_err_pending", None)
        s["clean_mineable"] = s["corrections"] + s["clean_error_resolutions"]
        s["legacy_upper_bound_mineable"] = s["corrections"] + s["legacy_error_resolutions"]
        sessions[sid] = s
    return sessions


def verdict_for(mean, n):
    if n < 5:
        return "INSUFFICIENT_SESSIONS"
    if mean >= 1.0:
        return "DENSITY_OK_PROCEED_PHASE1"
    return "NO_SIGNAL"


def verdict(sessions):
    n = len(sessions)
    total_clean = sum(s["clean_mineable"] for s in sessions.values())
    total_legacy = sum(s["legacy_upper_bound_mineable"] for s in sessions.values())
    mean_clean = (total_clean / n) if n else 0.0
    mean_legacy = (total_legacy / n) if n else 0.0
    return {
        "sessions": n,
        "total_clean_mineable": total_clean,
        "mean_clean_mineable_per_session": round(mean_clean, 3),
        "total_legacy_upper_bound_mineable": total_legacy,
        "mean_legacy_upper_bound_per_session": round(mean_legacy, 3),
        "legacy_untrusted_errors": sum(s["legacy_untrusted_errors"] for s in sessions.values()),
        "stderr_success_records": sum(s["stderr_success"] for s in sessions.values()),
        "gate": "mean>=1.0 over >=5 sessions",
        "verdict": verdict_for(mean_clean, n),
        "legacy_upper_bound_verdict": verdict_for(mean_legacy, n),
    }


def event_summary(rows):
    events = defaultdict(int)
    tools = defaultdict(int)
    latest_ts = None
    for row in rows:
        ev = row.get("ev", "?")
        events[ev] += 1
        if ev == "PostToolUse":
            tools[row.get("tool", "?")] += 1
        ts = row.get("ts")
        if isinstance(ts, (int, float)):
            latest_ts = ts if latest_ts is None else max(latest_ts, ts)
    latest_iso = None
    if latest_ts is not None:
        latest_iso = datetime.fromtimestamp(latest_ts, timezone.utc).isoformat()
    return {
        "events": dict(sorted(events.items())),
        "top_tools": dict(sorted(tools.items(), key=lambda kv: (-kv[1], kv[0]))[:10]),
        "latest_event_at": latest_iso,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = load(args.log)
    sessions = analyze(rows)
    summary = verdict(sessions)
    summary["log"] = args.log
    summary["total_records"] = len(rows)
    summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    summary.update(event_summary(rows))

    if args.json:
        print(json.dumps({"summary": summary, "per_session": sessions}, ensure_ascii=False, indent=2))
        return

    print(f"=== instinct observer audit snapshot ({args.log}) ===")
    print(f"records: {len(rows)} | sessions: {summary['sessions']}")
    print(f"events: {summary['events']} | latest: {summary['latest_event_at']}")
    print(f"{'session':<40} {'prompt':>6} {'corr':>5} {'tool':>5} {'cerr':>5} {'cfix':>5} "
          f"{'clean':>6} {'legacy':>6} {'noise':>5}")
    for sid, s in sorted(sessions.items(), key=lambda kv: -kv[1]["clean_mineable"]):
        print(f"{sid:<40} {s['prompts']:>6} {s['corrections']:>5} {s['tools']:>5} "
              f"{s['clean_errors']:>5} {s['clean_error_resolutions']:>5} "
              f"{s['clean_mineable']:>6} {s['legacy_upper_bound_mineable']:>6} "
              f"{s['legacy_untrusted_errors'] + s['stderr_success']:>5}")
    print(f"--- clean mean/session: {summary['mean_clean_mineable_per_session']} "
          f"| verdict: {summary['verdict']} ({summary['gate']}) ---")
    print(f"--- legacy upper-bound mean/session: {summary['mean_legacy_upper_bound_per_session']} "
          f"| verdict: {summary['legacy_upper_bound_verdict']} | "
          f"untrusted legacy errors: {summary['legacy_untrusted_errors']} | "
          f"stderr-success records: {summary['stderr_success_records']} ---")


if __name__ == "__main__":
    main()
