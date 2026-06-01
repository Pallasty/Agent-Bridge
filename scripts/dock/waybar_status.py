#!/usr/bin/env python3
"""Emit one waybar custom-module JSON line for Claude's live state.

Reads dock_snapshot.json (kept fresh by the tray wrapper) and maps it to
``{"text","tooltip","class"}`` so the status-bar glyph *follows state*: its
colour is the mood, it grows a badge when sessions run, and it flips to a
warning when something needs the human. Hover shows a summary; click opens the
full dock panel.
"""
import html
import json
import pathlib

SNAP = pathlib.Path(__file__).resolve().parent / "dock_snapshot.json"
ROBOT = "\U000f06a9"   # 󰚩  nf-md-robot
WARN = ""        #   nf-fa-warning

# mood -> waybar CSS class (coloured in style.css)
MOOD_CLASS = {
    "happy": "happy", "calm": "calm", "content": "calm",
    "thinking": "thinking", "orienting": "thinking", "working": "thinking", "focused": "thinking",
    "alert": "alert", "concerned": "alert",
    "error": "error", "sad": "error",
    "tired": "idle", "idle": "idle",
}


def ago(s):
    if s is None or s < 0:
        return "—"
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


def emit(text, tooltip, cls):
    print(json.dumps({"text": text, "tooltip": tooltip, "class": cls}, ensure_ascii=False))


try:
    d = json.loads(SNAP.read_text())
except Exception:
    emit(ROBOT, "Claude · 聚合器未就绪", "idle")
    raise SystemExit(0)

face = d.get("face") or {}
mood = face.get("mood") or "idle"
mode = face.get("mode") or mood
reason = face.get("reason") or face.get("last_event") or "静默"
presence = d.get("presence") or []
sessions = d.get("sessions") or []
approvals = d.get("approvals") or []
notifs = d.get("notifications") or []
daemon = d.get("daemon") or {}
node = d.get("node_self") or "?"

live = sum(1 for p in presence if p.get("fresh"))
active = sum(1 for s in sessions if s.get("active"))
cls = MOOD_CLASS.get(mood, "idle")

# glyph follows state: warning+count when you're needed, badge when running
if approvals:
    text, cls = f"{WARN} {len(approvals)}", "approval"
elif active:
    text = f"{ROBOT} {active} ●"
else:
    text = ROBOT


def esc(x):
    return html.escape(str(x))


lines = [
    f"<b>Claude</b> · {esc(node)}  <i>{esc(mode)}</i>",
    f"<span foreground='#9399b2'>{esc(reason)[:72]}</span>",
    "",
    f"在场  <b>{live}</b> live / {len(presence)}",
    f"会话  <b>{active}</b> running",
]
if approvals:
    lines.append(f"<span foreground='#f9e2af'>⚠  {len(approvals)} 待你拍板</span>")
if notifs:
    n0 = notifs[0]
    lines.append(f"最近  {esc(n0.get('title', ''))[:40]} · {ago(n0.get('age_s'))}前")
lines += ["", f"<span foreground='#6c7086'>daemon ♥ {ago(daemon.get('age_s'))}  ·  点击展开 ▸</span>"]

emit(text, "\n".join(lines), cls)
