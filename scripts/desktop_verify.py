#!/usr/bin/env python3
"""desktop_verify — read-only postflight verifier for Linux Computer Use (thread 79).

The "verify" + "recover" leg of the snapshot -> act -> verify -> recover loop. After a
desktop_invoke / desktop_action, you rarely want the raw new snapshot — you want one
answer: *did my intended effect happen, and if not, what should I do next?* This tool
re-observes the bus (AT-SPI registry + sway window tree, the same sources
desktop_snapshot reads) and checks ONE expectation, POLLING until it holds or a timeout
elapses (GUIs animate; a single check races the toolkit — see the GTK4 settle lesson).

Design is for the caller's ergonomics, not minimal surface:
  * the expectation reuses the SAME selector vocabulary you just acted on
    (--app/--role/--name for AT-SPI, --win-* for windows) so verify is a near-copy of
    the act call;
  * it returns a `recover` hint (proceed|retry|replan|escalate) that maps 1:1 to your
    next move, so you read ONE field instead of re-deriving intent from raw state;
  * an optional cheap before-fingerprint (--before-present / --before-focus) splits a
    miss into `unchanged` (nothing moved -> idempotent retry) vs `diverged` (state
    moved but not as expected -> re-plan), without forcing a full before-snapshot.

Strictly READ-ONLY: it never clicks, types, or moves anything — so observing the REAL
desktop is safe and ungated. Isolation mirrors the act tools only to SCOPE what counts
as "present": --cage-pid restricts AT-SPI matches to a process subtree, --swaysock
points window checks at a nested compositor.

verdict  : verified | unmet | error
recover  : proceed   | retry | replan | escalate
change   : unchanged | diverged | null   (only when a before-fingerprint is given)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from desktop_invoke import (  # noqa: E402  shared bounded selector + cage check
    DEFAULT_SEARCH_BUDGET,
    DEFAULT_SEARCH_MAX_DEPTH,
    DEFAULT_SEARCH_MAX_NODES,
    find_element,
)
from desktop_snapshot import hydrate_linux_session_env  # noqa: E402

SCHEMA = "desktop_verify/v0"

ELEMENT_EXPECTS = {"element_gone", "element_appeared", "state_is", "state_not"}
WINDOW_EXPECTS = {"window_gone", "window_appeared", "focus_is"}

# friendly state name -> pyatspi STATE_* attribute (resolved lazily so --help works
# without the binding installed).
_STATE_ALIASES = {
    "checked": "STATE_CHECKED",
    "expanded": "STATE_EXPANDED",
    "selected": "STATE_SELECTED",
    "showing": "STATE_SHOWING",
    "visible": "STATE_VISIBLE",
    "focused": "STATE_FOCUSED",
    "sensitive": "STATE_SENSITIVE",
    "enabled": "STATE_ENABLED",
    "pressed": "STATE_PRESSED",
    "active": "STATE_ACTIVE",
}


def _element_states(node, pyatspi) -> list[str]:
    """Friendly names of the states this accessible currently holds."""
    held: list[str] = []
    try:
        sset = node.getState()
    except Exception:  # noqa: BLE001
        return held
    for friendly, const_name in _STATE_ALIASES.items():
        const = getattr(pyatspi, const_name, None)
        if const is None:
            continue
        try:
            if sset.contains(const):
                held.append(friendly)
        except Exception:  # noqa: BLE001
            continue
    return held


def resolve_atspi_matches(app_match, role_match, name_match, nth, cage_pid,
                          search_budget=DEFAULT_SEARCH_BUDGET,
                          max_nodes=DEFAULT_SEARCH_MAX_NODES,
                          max_depth=DEFAULT_SEARCH_MAX_DEPTH):
    """Resolve the exact nth AT-SPI target through desktop_invoke's bounded DFS."""
    hydrate_linux_session_env()
    try:
        import pyatspi  # noqa: PLC0415  deferred binding
    except Exception as exc:  # noqa: BLE001  pragma: no cover
        return [], f"pyatspi unavailable: {exc}", None
    try:
        node, app_name, app_pid, coverage = find_element(
            app_match, role_match, name_match, nth, cage_pid=cage_pid,
            search_budget=search_budget, max_nodes=max_nodes, max_depth=max_depth,
        )
    except Exception as exc:  # noqa: BLE001
        return [], f"AT-SPI registry unreachable: {exc}", None
    if node is None:
        return [], None, coverage
    try:
        match = {
            "role": node.getRoleName(),
            "name": node.name or "",
            "app": app_name,
            "pid": app_pid,
            "in_scope": True,
            "states": _element_states(node, pyatspi),
        }
    except Exception as exc:  # noqa: BLE001
        return [], f"matched AT-SPI target became unreadable: {exc}", coverage
    return [match], None, coverage


def collect_sway_windows(swaysock):
    """Window skeleton via desktop_snapshot's sway helpers. Returns (windows, error)."""
    try:
        from desktop_snapshot import _sway_env, collect_windows  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001  pragma: no cover
        return [], f"sway helpers unavailable: {exc}"

    env = _sway_env()  # host SWAYSOCK from env / runtime-dir probe
    if swaysock:
        env["SWAYSOCK"] = swaysock  # override: point window checks at a nested compositor
    try:
        wins = collect_windows(env)
    except Exception as exc:  # noqa: BLE001
        return [], f"swaymsg get_tree failed: {exc}"
    if isinstance(wins, dict) and wins.get("error"):
        return [], str(wins["error"])
    return wins, None


def _win_title(win):
    """sway windows carry the title under 'name' (see desktop_snapshot._walk_tree);
    a couple of code paths historically read 'title' — accept either, prefer 'name'."""
    return win.get("name") or win.get("title") or ""


def window_matches(win, app_id, pid, title):
    ok = True
    if app_id:
        ok = ok and bool(win.get("app_id")) and app_id.lower() in (win.get("app_id") or "").lower()
    if pid is not None:
        ok = ok and win.get("pid") == pid
    if title:
        ok = ok and title.lower() in _win_title(win).lower()
    # require at least one selector to have been provided
    return ok if (app_id or pid is not None or title) else False


def evaluate(args) -> tuple[bool, dict[str, Any], Any | None]:
    """Evaluate the expectation once. Returns (holds, observed, error)."""
    expect = args.expect
    if expect in ELEMENT_EXPECTS:
        matches, err, coverage = resolve_atspi_matches(
            args.app, args.role, args.name, args.nth, args.cage_pid,
            search_budget=args.search_budget, max_nodes=args.search_max_nodes,
            max_depth=args.search_max_depth,
        )
        if err:
            return False, {"matches": [], "count": 0}, err
        observed = {"matches": matches, "count": len(matches), "search": coverage}
        present = len(matches) > 0
        if not present and coverage is not None and not coverage["complete"]:
            return False, observed, {
                "code": "search_incomplete",
                "message": "AT-SPI search budget exhausted before target absence was established",
            }
        if expect == "element_gone":
            return (not present), observed, None
        if expect == "element_appeared":
            return present, observed, None
        # state_is / state_not need the element present
        if not present:
            observed["note"] = "element_absent"
            return False, observed, None
        want = (args.state or "").lower()
        has = any(want in m["states"] for m in in_scope)
        if expect == "state_is":
            return has, observed, None
        return (not has), observed, None  # state_not

    if expect in WINDOW_EXPECTS:
        wins, err = collect_sway_windows(args.swaysock)
        if err:
            return False, {"windows": [], "focused": None}, err
        matched = [
            w for w in wins if window_matches(w, args.win_app_id, args.win_pid, args.win_title)
        ]
        focused = next((w for w in wins if w.get("focused")), None)
        focused_brief = (
            {"app_id": focused.get("app_id"), "title": _win_title(focused) or None, "pid": focused.get("pid")}
            if focused
            else None
        )
        observed = {
            "windows": [
                {"app_id": w.get("app_id"), "title": _win_title(w) or None, "pid": w.get("pid"),
                 "focused": w.get("focused")}
                for w in matched
            ],
            "count": len(matched),
            "focused": focused_brief,
        }
        if expect == "window_gone":
            return (len(matched) == 0), observed, None
        if expect == "window_appeared":
            return (len(matched) > 0), observed, None
        # focus_is: the focused window must match the selector
        holds = focused is not None and window_matches(
            focused, args.win_app_id, args.win_pid, args.win_title
        )
        return holds, observed, None

    return False, {}, f"unknown --expect {expect!r}"


def classify_change(args, observed) -> str | None:
    """unchanged vs diverged from a cheap before-fingerprint (only when one is given)."""
    if args.expect in ELEMENT_EXPECTS and args.before_present is not None:
        present_now = observed.get("count", 0) > 0
        # before_present True + still present  -> nothing moved (retry the same act)
        # before_present True + something else -> handled by holds; reaching here = miss
        if args.before_present == present_now:
            return "unchanged"
        return "diverged"
    if args.expect == "focus_is" and args.before_focus:
        foc = observed.get("focused") or {}
        cur = f"{foc.get('app_id') or ''}|{foc.get('title') or ''}".lower()
        before = args.before_focus.lower()
        # focus still where it was -> nothing moved; focus elsewhere (not target) -> diverged
        return "unchanged" if before in cur or cur in before else "diverged"
    return None


def recover_hint(verdict: str, change: str | None) -> str:
    if verdict == "verified":
        return "proceed"
    if verdict == "error":
        return "escalate"
    # unmet
    if change == "diverged":
        return "replan"
    return "retry"  # unchanged or unknown -> idempotent retry is safe


def run(args) -> dict[str, Any]:
    selector = {
        "app": args.app, "role": args.role, "name": args.name, "nth": args.nth,
        "win_app_id": args.win_app_id, "win_pid": args.win_pid, "win_title": args.win_title,
        "state": args.state,
    }
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "ts": int(time.time()),
        "expect": args.expect,
        "selector": {k: v for k, v in selector.items() if v is not None},
        "scope": {"cage_pid": args.cage_pid, "swaysock": args.swaysock},
    }
    if args.settle > 0:
        time.sleep(min(args.settle, 5.0))

    deadline = time.time() + max(0.0, args.timeout)
    polls = 0
    held = False
    observed: dict[str, Any] = {}
    error: Any | None = None
    started = time.time()
    held_after_ms: int | None = None
    while True:
        polls += 1
        held, observed, error = evaluate(args)
        if error:
            break
        if held:
            held_after_ms = int((time.time() - started) * 1000)
            break
        if time.time() >= deadline:
            break
        time.sleep(max(0.05, args.poll_interval))

    if error:
        verdict = "error"
        change = None
    elif held:
        verdict = "verified"
        change = None
    else:
        verdict = "unmet"
        change = classify_change(args, observed)

    recover = recover_hint(verdict, change)
    if isinstance(error, dict) and error.get("code") == "search_incomplete":
        recover = "replan"
    record.update(
        verdict=verdict,
        recover=recover,
        change=change,
        held_after_ms=held_after_ms,
        polls=polls,
        observed=observed,
        error=error,
    )
    return record


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="read-only postflight verifier (Linux Computer Use)")
    ap.add_argument(
        "--expect",
        required=True,
        choices=sorted(ELEMENT_EXPECTS | WINDOW_EXPECTS),
        help="the postcondition to check (reuses the selector you just acted on)",
    )
    # AT-SPI selector (element_*/state_*)
    ap.add_argument("--app", help="application name substring")
    ap.add_argument("--role", help="accessible role substring (e.g. button)")
    ap.add_argument("--name", help="accessible name substring (e.g. OK)")
    ap.add_argument("--nth", type=int, default=0)
    ap.add_argument("--cage-pid", type=int, default=None,
                    help="scope AT-SPI matches to this process subtree (isolated verify)")
    ap.add_argument("--search-budget", type=float, default=DEFAULT_SEARCH_BUDGET)
    ap.add_argument("--search-max-nodes", type=int, default=DEFAULT_SEARCH_MAX_NODES)
    ap.add_argument("--search-max-depth", type=int, default=DEFAULT_SEARCH_MAX_DEPTH)
    ap.add_argument("--state", help="for state_is/state_not: "
                    + "|".join(sorted(_STATE_ALIASES)))
    # window selector (window_*/focus_is)
    ap.add_argument("--win-app-id", help="sway app_id substring")
    ap.add_argument("--win-pid", type=int, default=None)
    ap.add_argument("--win-title", help="window title substring")
    ap.add_argument("--swaysock", help="nested sway IPC socket (isolated verify)")
    # polling
    ap.add_argument("--timeout", type=float, default=4.0,
                    help="poll until the expectation holds or this many seconds elapse")
    ap.add_argument("--poll-interval", type=float, default=0.3)
    ap.add_argument("--settle", type=float, default=0.0,
                    help="initial delay before the first check (let the GUI start reacting)")
    # optional before-fingerprint for unchanged|diverged
    ap.add_argument("--before-present", choices=["true", "false"], default=None,
                    help="was the AT-SPI target present BEFORE the act? splits a miss into "
                    "unchanged vs diverged")
    ap.add_argument("--before-focus", default=None,
                    help="focused 'app_id|title' BEFORE the act (for focus_is)")
    ap.add_argument("--compact", action="store_true")
    return ap


def main() -> int:
    args = parser().parse_args()
    if args.nth < 0:
        parser().error("--nth must be >= 0")
    if args.search_budget <= 0 or args.search_max_nodes <= 0 or args.search_max_depth < 0:
        parser().error("search budget/nodes must be positive and depth must be >= 0")
    # normalize before_present to bool|None
    if args.before_present is not None:
        args.before_present = args.before_present == "true"
    record = run(args)
    json.dump(record, sys.stdout, ensure_ascii=False, indent=None if args.compact else 2)
    sys.stdout.write("\n")
    # exit code mirrors recover urgency: 0 verified, 2 unmet, 3 error
    return {"verified": 0, "unmet": 2, "error": 3}.get(record["verdict"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
