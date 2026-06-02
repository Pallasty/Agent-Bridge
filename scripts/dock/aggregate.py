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
import re
import shutil
import sqlite3
import subprocess
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

# ── pending approvals (the canonical host-confirm `desktop_pending` store) ────
# Slice 1 makes these clickable: the dock RECORDS the human's decision to
# dock_decisions/; the gated Rust `desktop_confirm` still owns single-use
# consumption + execution, so surfacing here never bypasses the gate.
# honor XDG_CACHE_HOME like desktop_confirm_store does, so a sandboxed run
# (e.g. try_steer_demo.sh) reads the SAME isolated store the dock_server writes to.
_CACHE_ROOT = pathlib.Path(os.environ.get("XDG_CACHE_HOME") or (HOME / ".cache")) / "agent-bridge"
PENDING_DIR = _CACHE_ROOT / "desktop_pending"
DECISIONS_DIR = _CACHE_ROOT / "dock_decisions"


def _safe_token(t):
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(t))[:128]


# Risk classifier for cross-process steer payloads. A NUDGE, not a security boundary:
# it red-flags injection text that matches destructive/privilege/remote-exec/credential
# patterns so the human slows down before approving. Heuristics are evadable — a flag's
# ABSENCE must never read as "safe" (the real boundary stays human judgment + single-use).
_RISK_HIGH = [
    (r"\brm\s+-[rfRF]", "rm -rf"), (r"\bdd\b", "dd"), (r"\bmkfs", "mkfs"),
    (r">\s*/dev/\w", "写 /dev/"), (r":\s*\(\s*\)\s*\{.*\|.*&\s*\}", "fork bomb"),
    (r"\bsudo\b", "sudo"), (r"\bdoas\b", "doas"), (r"(^|\s)su\s", "su"),
    (r"curl\b[^|]*\|\s*(sh|bash|zsh)", "curl|sh"), (r"wget\b[^|]*\|\s*(sh|bash|zsh)", "wget|sh"),
    (r"\beval\b", "eval"), (r"(~/\.ssh|id_rsa|id_ed25519|\.env\b|secret)", "凭据/密钥"),
    (r"\bchmod\s+-R", "chmod -R"), (r"\bchown\s+-R", "chown -R"),
    (r"git\s+push\b[^\n]*(-f\b|--force)", "git push --force"),
    (r"\b(shutdown|reboot|halt|poweroff)\b", "关机/重启"),
]
_RISK_CAUTION = [
    (r"\|\s*(sh|bash|zsh|python\d?)\b", "管道入解释器"), (r">>?\s*\S", "重定向写文件"),
    (r"\brm\b", "rm"), (r"\b(docker|kubectl|systemctl|apt|apt-get|pip\d?|npm|cargo)\b", "有副作用工具"),
]


def classify_steer_risk(text):
    t = text or ""
    hits = [lbl for pat, lbl in _RISK_HIGH if re.search(pat, t, re.I)]
    if hits:
        return {"level": "high", "reasons": hits[:3]}
    hits = [lbl for pat, lbl in _RISK_CAUTION if re.search(pat, t, re.I)]
    if hits:
        return {"level": "caution", "reasons": hits[:3]}
    return {"level": "normal", "reasons": []}


approvals = []
for f in glob.glob(str(PENDING_DIR / "*.json")):
    rec = load_json(f)
    if not isinstance(rec, dict) or rec.get("status") != "pending":
        continue
    if NOW > int(rec.get("expires_at", 0)):
        continue  # expired tokens are dead; don't surface
    token = rec.get("token") or pathlib.Path(f).stem
    decided = load_json(DECISIONS_DIR / f"{_safe_token(token)}.json")
    entry = {
        "token": token,
        "kind": rec.get("kind"),
        "summary": rec.get("summary") or rec.get("kind"),
        "expires_in_s": int(rec.get("expires_at", 0)) - NOW,
        "decided": decided.get("decision") if isinstance(decided, dict) else None,
    }
    # cross-process control plane (probe): a steer pending injects into ANOTHER
    # session, so surface the payload legibly — the human must see EXACTLY what text
    # lands in which session before approving (the security crux of this direction).
    if rec.get("kind") == "steer":
        pl = rec.get("payload") or {}
        entry["steer"] = {
            "session": pl.get("session"),
            "text": pl.get("text"),
            "submit": bool(pl.get("submit")),
            "staged_by": pl.get("staged_by"),
        }
        entry["risk"] = classify_steer_risk(pl.get("text"))
    approvals.append(entry)


# ── the face, deepened: avatar cortex motion semantics ───────────────────────
def cortex_motion():
    """Best-effort parse of `agent-bridge avatar cortex-motion` key=value output
    into {gesture, mood, attention, animation, intensity, state}. Returns {} on
    any failure (binary missing / slow / output changed) so the orb cleanly
    falls back to mood-only expression."""
    ab = shutil.which("agent-bridge") or str(HOME / ".local/bin/agent-bridge.real")
    try:
        out = subprocess.run(
            [ab, "avatar", "cortex-motion"],
            capture_output=True, text=True, timeout=3,
        )
        kv = {}
        for tok in out.stdout.split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv[k] = v
        keys = ("gesture", "mood", "attention", "animation", "intensity", "state")
        return {k: kv[k] for k in keys if kv.get(k)}
    except Exception:
        return {}


CORTEX = cortex_motion()

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
        "cortex": CORTEX,
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
