#!/usr/bin/env python3
"""delta① Phase-0b density audit — analyze the observer sidecar log.

Reads ~/.cache/agent-bridge/instinct-probe/observations.jsonl (written by
ab-instinct-observer-hook) and estimates the per-session density of MINEABLE
behavioral signals, to decide whether an auto-miner is worth building.
Spec/falsifier: docs/design/ECC_INSTINCT_MINING_PROBE_2026_05_24.md (Phase 0b).

Two signal classes (heuristic — an upper-bound proxy; the real miner would use
an LLM pass for precision, this just answers "is there ENOUGH to bother?"):

  - correction  : a UserPromptSubmit whose text carries negation / redirection
                  cues right after assistant action ("不对/应该/instead/revert"…)
  - error-resln : a PostToolUse with err=true that is later followed (same
                  session) by a SUCCESS of the same tool — i.e. a fix landed

Gate (frozen): mean mineable signals/session >= ~1 over >=5 sessions -> proceed
to Phase 1 miner. Below that -> NO_SIGNAL (don't build it).

Usage:  python3 scripts/instinct_density_audit.py [--log PATH] [--json]
"""
import argparse
import json
import os
import sys
from collections import defaultdict

DEFAULT_LOG = os.path.expanduser("~/.cache/agent-bridge/instinct-probe/observations.jsonl")

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
        "prompts": 0, "corrections": 0, "tools": 0, "errors": 0,
        "error_resolutions": 0, "_err_pending": defaultdict(int),
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
            if r.get("err"):
                s["errors"] += 1
                s["_err_pending"][tool] += 1
            else:
                # a success of a tool that previously errored = resolution
                if s["_err_pending"].get(tool, 0) > 0:
                    s["error_resolutions"] += 1
                    s["_err_pending"][tool] -= 1
    # finalize
    sessions = {}
    for sid, s in by_sid.items():
        s.pop("_err_pending", None)
        s["mineable"] = s["corrections"] + s["error_resolutions"]
        sessions[sid] = s
    return sessions


def verdict(sessions):
    n = len(sessions)
    total_mineable = sum(s["mineable"] for s in sessions.values())
    mean = (total_mineable / n) if n else 0.0
    if n < 5:
        v = "INSUFFICIENT_SESSIONS"
    elif mean >= 1.0:
        v = "DENSITY_OK_PROCEED_PHASE1"
    else:
        v = "NO_SIGNAL"
    return {
        "sessions": n,
        "total_mineable": total_mineable,
        "mean_mineable_per_session": round(mean, 3),
        "gate": "mean>=1.0 over >=5 sessions",
        "verdict": v,
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

    if args.json:
        print(json.dumps({"summary": summary, "per_session": sessions}, ensure_ascii=False, indent=2))
        return

    print(f"=== instinct density audit ({args.log}) ===")
    print(f"records: {len(rows)} | sessions: {summary['sessions']}")
    print(f"{'session':<40} {'prompt':>6} {'corr':>5} {'tool':>5} {'err':>4} {'fix':>4} {'mine':>5}")
    for sid, s in sorted(sessions.items(), key=lambda kv: -kv[1]["mineable"]):
        print(f"{sid:<40} {s['prompts']:>6} {s['corrections']:>5} {s['tools']:>5} "
              f"{s['errors']:>4} {s['error_resolutions']:>4} {s['mineable']:>5}")
    print(f"--- mean mineable/session: {summary['mean_mineable_per_session']} "
          f"| verdict: {summary['verdict']} ({summary['gate']}) ---")


if __name__ == "__main__":
    main()
