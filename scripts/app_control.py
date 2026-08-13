#!/usr/bin/env python3
"""Bounded application control router — protocol first, UI fallback explicit.

The first adapter is Linux media control over MPRIS via ``playerctl``.  The
script never executes a shell string and never silently falls back to AT-SPI,
vision, or coordinate input.  Every mutation is followed by an independent
MPRIS read that verifies the requested effect.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, MutableMapping

SCHEMA = "agent_bridge.app_control.v0"
ACTIONS = ("discover", "next", "previous", "play", "pause", "play_pause", "stop")
PLAYERCTL_ACTION = {
    "next": "next",
    "previous": "previous",
    "play": "play",
    "pause": "pause",
    "play_pause": "play-pause",
    "stop": "stop",
}
METADATA_FORMAT = "{{mpris:trackid}}\t{{xesam:artist}}\t{{xesam:title}}"


def hydrate_session_bus(env: MutableMapping[str, str] | None = None) -> dict[str, str]:
    target = os.environ if env is None else env
    if not sys.platform.startswith("linux"):
        return {}
    uid = os.getuid()
    runtime = Path(target.get("XDG_RUNTIME_DIR", f"/run/user/{uid}"))
    try:
        if not runtime.is_dir() or runtime.stat().st_uid != uid:
            return {}
    except OSError:
        return {}
    restored: dict[str, str] = {}
    if not target.get("XDG_RUNTIME_DIR"):
        target["XDG_RUNTIME_DIR"] = str(runtime)
        restored["XDG_RUNTIME_DIR"] = str(runtime)
    bus = runtime / "bus"
    try:
        valid_bus = bus.is_socket() and bus.stat().st_uid == uid
    except OSError:
        valid_bus = False
    if valid_bus and not target.get("DBUS_SESSION_BUS_ADDRESS"):
        address = f"unix:path={bus}"
        target["DBUS_SESSION_BUS_ADDRESS"] = address
        restored["DBUS_SESSION_BUS_ADDRESS"] = address
    return restored


def run(argv: list[str], env: dict[str, str], timeout: float = 2.0) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, env=env, check=False
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"not found: {argv[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout:.1f}s"


def list_players(env: dict[str, str]) -> tuple[list[str], dict[str, Any] | None]:
    rc, out, err = run(["playerctl", "-l"], env)
    if rc != 0:
        return [], {"code": "discovery_failed", "rc": rc, "message": err or out}
    return [line.strip() for line in out.splitlines() if line.strip()], None


def select_player(players: list[str], selector: str | None) -> tuple[str | None, str | None]:
    if not players:
        return None, "no_mpris_player"
    if not selector:
        return players[0], None
    folded = selector.casefold()
    exact = [player for player in players if player.casefold() == folded]
    matches = exact or [player for player in players if folded in player.casefold()]
    if len(matches) == 1:
        return matches[0], None
    return None, "player_not_found" if not matches else "ambiguous_player"


def observe(player: str, env: dict[str, str]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    rc_status, status, err_status = run(["playerctl", "-p", player, "status"], env)
    rc_meta, meta, err_meta = run(
        ["playerctl", "-p", player, "metadata", "--format", METADATA_FORMAT], env
    )
    if rc_status != 0:
        return None, {
            "code": "observation_failed",
            "rc": rc_status,
            "message": err_status or status,
        }
    fields = (meta.split("\t", 2) + ["", "", ""])[:3] if rc_meta == 0 else ["", "", ""]
    return {
        "player": player,
        "playback_status": status,
        "track_id": fields[0] or None,
        "artist": fields[1] or None,
        "title": fields[2] or None,
        "metadata_available": rc_meta == 0,
        "metadata_error": None if rc_meta == 0 else (err_meta or meta),
    }, None


def effect_verified(action: str, before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
    if action in ("next", "previous"):
        before_identity = (before.get("track_id"), before.get("artist"), before.get("title"))
        after_identity = (after.get("track_id"), after.get("artist"), after.get("title"))
        return before_identity != after_identity, "track_identity_changed"
    expected = {
        "play": "Playing",
        "pause": "Paused",
        "stop": "Stopped",
    }.get(action)
    if expected:
        return after.get("playback_status") == expected, f"playback_status_is_{expected.lower()}"
    if action == "play_pause":
        return (
            after.get("playback_status") != before.get("playback_status"),
            "playback_status_changed",
        )
    return False, "unsupported_effect"


def route_summary(selected: bool) -> dict[str, Any]:
    return {
        "policy": "protocol_api_then_semantic_ui_then_vision",
        "selected": {
            "backend": "mpris_playerctl",
            "layer": "application_protocol",
            "priority": 1,
        } if selected else None,
        "fallbacks": [
            {"backend": "atspi", "layer": "ui_semantics", "status": "not_executed"},
            {"backend": "vision", "layer": "screen_pixels", "status": "not_executed"},
            {"backend": "coordinate_input", "layer": "input_emulation", "status": "not_executed"},
        ],
        "silent_fallback_allowed": False,
    }


def execute(action: str, player_selector: str | None, dry_run: bool, verify_timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    env = dict(os.environ)
    restored = hydrate_session_bus(env)
    if not shutil.which("playerctl"):
        return {
            "schema": SCHEMA, "status": "unavailable", "verdict": "error", "recover": "replan",
            "domain": "media", "action": action, "route": route_summary(False),
            "error": {"code": "backend_missing", "message": "playerctl is not installed"},
        }
    players, error = list_players(env)
    if error:
        return {
            "schema": SCHEMA, "status": "unavailable", "verdict": "error", "recover": "retry",
            "domain": "media", "action": action, "route": route_summary(False), "error": error,
        }
    if action == "discover":
        return {
            "schema": SCHEMA, "status": "observed", "verdict": "verified", "recover": "proceed",
            "domain": "media", "action": action, "read_only": True,
            "capabilities": {"backend": "mpris_playerctl", "available": True, "players": players,
                             "actions": list(ACTIONS[1:])},
            "route": route_summary(bool(players)), "session_env_restored": sorted(restored),
            "duration_ms": round((time.monotonic() - started) * 1000),
        }
    player, select_error = select_player(players, player_selector)
    if select_error:
        return {
            "schema": SCHEMA, "status": "target_unavailable", "verdict": "error", "recover": "replan",
            "domain": "media", "action": action, "players": players, "route": route_summary(False),
            "error": {"code": select_error, "selector": player_selector},
        }
    assert player is not None
    before, error = observe(player, env)
    if error or before is None:
        return {
            "schema": SCHEMA, "status": "observation_failed", "verdict": "error", "recover": "retry",
            "domain": "media", "action": action, "route": route_summary(True), "error": error,
        }
    if dry_run:
        return {
            "schema": SCHEMA, "status": "planned", "verdict": "verified", "recover": "proceed",
            "domain": "media", "action": action, "read_only": True, "player": player,
            "route": route_summary(True), "before": before,
            "dispatch": {"status": "not_dispatched_dry_run", "argv": ["playerctl", "-p", player, PLAYERCTL_ACTION[action]]},
            "verification": {"status": "not_run", "reason": "dry_run"},
        }
    argv = ["playerctl", "-p", player, PLAYERCTL_ACTION[action]]
    rc, out, err = run(argv, env)
    dispatch = {"status": "dispatched" if rc == 0 else "failed", "rc": rc, "argv": argv,
                "stdout": out, "stderr": err}
    if rc != 0:
        return {
            "schema": SCHEMA, "status": "action_failed", "verdict": "error", "recover": "retry",
            "domain": "media", "action": action, "player": player, "route": route_summary(True),
            "before": before, "dispatch": dispatch,
        }
    deadline = time.monotonic() + verify_timeout
    after = before
    verified = False
    predicate = ""
    polls = 0
    observation_error = None
    while True:
        polls += 1
        candidate, observation_error = observe(player, env)
        if candidate is not None:
            after = candidate
            verified, predicate = effect_verified(action, before, after)
            if verified:
                break
        if time.monotonic() >= deadline:
            break
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
    return {
        "schema": SCHEMA, "status": "verified" if verified else "unmet",
        "verdict": "verified" if verified else "unmet", "recover": "proceed" if verified else "replan",
        "domain": "media", "action": action, "read_only": False, "player": player,
        "route": route_summary(True), "before": before, "dispatch": dispatch, "after": after,
        "verification": {"status": "verified" if verified else "unmet", "predicate": predicate,
                         "polls": polls, "observation_error": observation_error},
        "session_env_restored": sorted(restored),
        "duration_ms": round((time.monotonic() - started) * 1000),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=("media",), default="media")
    parser.add_argument("--action", choices=ACTIONS, required=True)
    parser.add_argument("--player")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-timeout", type=float, default=2.0)
    args = parser.parse_args()
    payload = execute(args.action, args.player, args.dry_run, min(max(args.verify_timeout, 0.1), 10.0))
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return 0 if payload.get("verdict") == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
