#!/usr/bin/env python3
"""Slice 0 of the desktop embodiment dock — the *state aggregator*.

Reads Agent-Bridge's REAL state into one ``dock_snapshot.json`` that the dock
HTML renders. Strictly read-only; every source degrades gracefully (a missing
DB / file yields an empty section, never a crash) so the dock can run anywhere.

Sources (all already maintained by AB — the dock just makes them visible):
  - state.db  agent_presence / notifications / sessions   (SQLite, read-only)
  - pet_state/<pet>.json                                  ("the face": mood/mode)
  - sync_state.json                                       (memory-sync health)
  - daemon.log mtime                                      (daemon liveness)
"""
import glob
import json
import os
import pathlib
import sqlite3
import time

HOME = pathlib.Path.home()
STATE_DB = HOME / ".local/share/agent-bridge/state.db"
PET_GLOB = str(HOME / ".local/share/agent-bridge/pet_state/*.json")
SYNC_STATE = HOME / ".cache/agent-bridge/sync_state.json"
DAEMON_LOG = HOME / ".cache/agent-bridge/daemon.log"
OUT = pathlib.Path(__file__).resolve().parent / "dock_snapshot.json"

NOW = int(time.time())
FRESH_PRESENCE_S = 300   # a presence row is "live" if its heartbeat is < 5 min old
FRESH_DAEMON_S = 120     # the daemon is "beating" if its log moved in the last 2 min


def db_query(sql, params=()):
    """Read-only SQLite query; returns [] on any error (locked / missing / schema drift)."""
    try:
        con = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True, timeout=2)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, params).fetchall()]
        finally:
            con.close()
    except Exception:
        return []


def load_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except Exception:
        return None


# ── presence: who is alive, on which node, doing what ────────────────────────
presence = db_query(
    "SELECT name, node, project, role, description, last_heartbeat_at, session_id "
    "FROM agent_presence ORDER BY last_heartbeat_at DESC LIMIT 12"
)
for p in presence:
    hb = p.get("last_heartbeat_at") or 0
    p["age_s"] = NOW - hb
    p["fresh"] = p["age_s"] < FRESH_PRESENCE_S

# ── notifications: what just happened ────────────────────────────────────────
notifications = db_query(
    "SELECT ts, source, severity, title, body FROM notifications ORDER BY ts DESC LIMIT 6"
)
for n in notifications:
    n["age_s"] = NOW - (n.get("ts") or 0)

# ── sessions: what is running / just finished ────────────────────────────────
sessions = db_query(
    "SELECT id, runtime_id, cwd, started_at, ended_at, exit_code, cloud_run_state "
    "FROM sessions ORDER BY started_at DESC LIMIT 8"
)
for s in sessions:
    s["active"] = s.get("ended_at") is None
    s["age_s"] = NOW - (s.get("started_at") or 0)

# ── the face: pet/avatar mood drives the orb ─────────────────────────────────
pet = {}
pet_files = sorted(glob.glob(PET_GLOB))
# prefer a non-ritual sidecar; pick the most-recently-updated
candidates = [f for f in pet_files if not f.endswith(".ritual.json")]
if candidates:
    candidates.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    pet = load_json(candidates[0]) or {}

# ── sync + daemon liveness ───────────────────────────────────────────────────
sync = load_json(SYNC_STATE) or {}
daemon = {"fresh": False, "age_s": None}
try:
    daemon["age_s"] = NOW - int(DAEMON_LOG.stat().st_mtime)
    daemon["fresh"] = daemon["age_s"] < FRESH_DAEMON_S
except Exception:
    pass

# ── pending approvals (best-effort, read-only; clickable arrives in Slice 1) ──
approvals = []
for pat in (
    str(HOME / ".cache/agent-bridge/*pending*.json"),
    str(HOME / ".cache/agent-bridge/confirm*/*.json"),
    str(HOME / ".cache/agent-bridge/host-confirm/*.json"),
):
    for f in glob.glob(pat):
        data = load_json(f)
        if isinstance(data, dict) and data:
            approvals.append({"file": os.path.basename(f), "data": data})

snapshot = {
    "generated_at": NOW,
    "node_self": os.uname().nodename,
    "face": {
        "mode": pet.get("mode"),
        "mood": pet.get("mood"),
        "reason": pet.get("reason"),
        "last_event": pet.get("last_event"),
        "project": pet.get("project"),
        "updated_at": pet.get("updated_at"),
    },
    "presence": presence,
    "notifications": notifications,
    "sessions": sessions,
    "sync": {
        "consecutive_failures": sync.get("consecutive_failures"),
        "last_success_at": sync.get("last_success_at"),
        "last_attempt_at": sync.get("last_attempt_at"),
    },
    "daemon": daemon,
    "approvals": approvals,
}

OUT.write_text(json.dumps(snapshot, ensure_ascii=False))
if __name__ == "__main__":
    print(
        f"wrote {OUT.name}: "
        f"{len(presence)} presence ({sum(p['fresh'] for p in presence)} live), "
        f"{len(notifications)} notif, {len(sessions)} sessions "
        f"({sum(s['active'] for s in sessions)} active), "
        f"face.mood={snapshot['face']['mood']}, daemon.fresh={daemon['fresh']}"
    )
