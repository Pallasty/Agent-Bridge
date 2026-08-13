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
ACTIONS = (
    "discover", "next", "previous", "play", "pause", "play_pause", "stop",
    "volume_get", "volume_up", "volume_down", "volume_set", "state_get", "position_get",
    "playlist_list", "playlist_current", "playlist_activate",
)
PLAYERCTL_ACTION = {
    "next": "next",
    "previous": "previous",
    "play": "play",
    "pause": "pause",
    "play_pause": "play-pause",
    "stop": "stop",
}
METADATA_FORMAT = "{{mpris:trackid}}\t{{xesam:artist}}\t{{xesam:title}}"
MPRIS_PLAYLIST_PATH = "/org/mpris/MediaPlayer2"


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


def playlist_call(player: str, method: str, args: list[str], env: dict[str, str]) -> tuple[int, str, str]:
    bus = f"org.mpris.MediaPlayer2.{player}"
    return run(["gdbus", "call", "--session", "--dest", bus, "--object-path", MPRIS_PLAYLIST_PATH, "--method", method, *args], env)


def list_playlists(player: str, env: dict[str, str]) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    rc, out, err = playlist_call(player, "org.mpris.MediaPlayer2.Playlists.GetPlaylists", ["0", "100", "Alphabetical", "false"], env)
    if rc != 0:
        return [], {"code": "playlist_discovery_failed", "rc": rc, "message": err or out}
    import re
    entries = [{"id": path, "name": name} for path, name in re.findall(r"(?:objectpath )?'([^']+)', '([^']*)', '[^']*'", out)]
    return entries, None


def current_playlist(player: str, env: dict[str, str]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Read the MPRIS ActivePlaylist property without guessing by playlist name."""
    rc, out, err = playlist_call(
        player,
        "org.freedesktop.DBus.Properties.Get",
        ["org.mpris.MediaPlayer2.Playlists", "ActivePlaylist"],
        env,
    )
    if rc != 0:
        return None, {"code": "active_playlist_observation_failed", "rc": rc, "message": err or out}
    import re
    match = re.search(r"\(\s*(true|false),\s*\(objectpath '([^']*)', '([^']*)'", out)
    if not match:
        return None, {"code": "active_playlist_parse_failed", "message": out}
    active = match.group(1) == "true"
    playlist_id = match.group(2) if active and match.group(2) != "/" else None
    name = match.group(3) if active else None
    return {"active": active, "id": playlist_id, "name": name}, None


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
    rc_volume, volume_text, volume_error = run(["playerctl", "-p", player, "volume"], env)
    try:
        volume = float(volume_text) if rc_volume == 0 else None
    except ValueError:
        volume = None
        volume_error = f"invalid volume: {volume_text}"
    rc_position, position_text, position_error = run(["playerctl", "-p", player, "position"], env)
    try:
        position = float(position_text) if rc_position == 0 else None
    except ValueError:
        position = None
        position_error = f"invalid position: {position_text}"
    rc_length, length_text, length_error = run(
        ["playerctl", "-p", player, "metadata", "--format", "{{mpris:length}}"], env
    )
    try:
        duration = float(length_text) / 1_000_000 if rc_length == 0 else None
    except ValueError:
        duration = None
        length_error = f"invalid duration: {length_text}"
    return {
        "player": player,
        "playback_status": status,
        "track_id": fields[0] or None,
        "artist": fields[1] or None,
        "title": fields[2] or None,
        "volume": volume,
        "volume_available": volume is not None,
        "volume_error": None if volume is not None else (volume_error or volume_text),
        "position_seconds": position,
        "duration_seconds": duration,
        "position_available": position is not None and duration is not None,
        "position_error": None if position is not None else (position_error or position_text),
        "duration_error": None if duration is not None else (length_error or length_text),
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
    if action == "volume_get":
        return after.get("volume") is not None, "volume_observed"
    if action in ("volume_up", "volume_down", "volume_set"):
        before_volume = before.get("volume")
        after_volume = after.get("volume")
        if before_volume is None or after_volume is None:
            return False, "volume_unavailable"
        if action == "volume_set":
            return abs(after_volume - before.get("requested_volume", after_volume)) <= 0.01, "volume_is_requested"
        direction = 1 if action == "volume_up" else -1
        return (after_volume - before_volume) * direction > 0.001, "volume_changed_in_requested_direction"
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


def execute(action: str, player_selector: str | None, dry_run: bool, verify_timeout: float, volume: float | None = None, playlist_id: str | None = None) -> dict[str, Any]:
    started = time.monotonic()
    # Validate caller-supplied parameters before probing the optional backend.
    # This keeps malformed requests deterministic on machines without MPRIS and
    # preserves the contract's distinction between caller error and availability.
    if action == "volume_set" and (volume is None or not 0.0 <= volume <= 1.0):
        return {
            "schema": SCHEMA, "status": "error", "verdict": "error", "recover": "replan",
            "domain": "media", "action": action, "route": route_summary(False),
            "error": {"code": "invalid_volume", "message": "volume_set requires 0.0 <= volume <= 1.0"},
        }
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
        "actions": list(ACTIONS[1:]), "volume": {"supported": True, "range": [0.0, 1.0], "default_step": 0.05},
        "playlists": {"supported": True, "activation_requires_unique_id": True, "active_observation": True}},
            "route": route_summary(bool(players)), "session_env_restored": sorted(restored),
            "duration_ms": round((time.monotonic() - started) * 1000),
        }
    # Read-only playlist observation may probe each discovered player when no
    # selector was supplied. Some MPRIS clients advertise the interface but
    # fail the ActivePlaylist getter; do not let that unrelated client shadow
    # a healthy player. Control actions remain strictly single-target.
    if action == "playlist_current" and not player_selector and len(players) > 1:
        attempts = []
        for candidate in players:
            active_playlist, active_error = current_playlist(candidate, env)
            if active_error:
                attempts.append({"player": candidate, "status": "observation_failed", "error": active_error})
                continue
            after, observe_error = observe(candidate, env)
            if after is None:
                attempts.append({"player": candidate, "status": "observation_failed", "error": observe_error or {"code": "observation_failed"}})
                continue
            return {"schema": SCHEMA, "status": "observed", "verdict": "verified", "recover": "proceed", "domain": "media", "action": action, "read_only": True, "player": candidate, "active_playlist": active_playlist, "track_summary": after, "selection": {"policy": "first_verified_playlist_current", "attempts": attempts}, "route": route_summary(True), "verification": {"status": "verified", "predicate": "active_playlist_observed", "observation_error": observe_error}}
        return {"schema": SCHEMA, "status": "observation_failed", "verdict": "error", "recover": "retry", "domain": "media", "action": action, "players": players, "selection": {"policy": "first_verified_playlist_current", "attempts": attempts}, "route": route_summary(bool(players)), "error": {"code": "all_players_observation_failed", "message": "no discovered MPRIS player completed playlist_current"}}

    player, select_error = select_player(players, player_selector)
    if select_error:
        return {
            "schema": SCHEMA, "status": "target_unavailable", "verdict": "error", "recover": "replan",
            "domain": "media", "action": action, "players": players, "route": route_summary(False),
            "error": {"code": select_error, "selector": player_selector},
        }
    assert player is not None
    if action == "playlist_current":
        active_playlist, active_error = current_playlist(player, env)
        if active_error:
            return {"schema": SCHEMA, "status": "observation_failed", "verdict": "error", "recover": "retry", "domain": "media", "action": action, "player": player, "route": route_summary(True), "error": active_error}
        after, observe_error = observe(player, env)
        return {"schema": SCHEMA, "status": "observed", "verdict": "verified", "recover": "proceed", "domain": "media", "action": action, "read_only": True, "player": player, "active_playlist": active_playlist, "track_summary": after, "route": route_summary(True), "verification": {"status": "verified", "predicate": "active_playlist_observed", "observation_error": observe_error}}
    if action in ("playlist_list", "playlist_activate"):
        playlists, playlist_error = list_playlists(player, env)
        if playlist_error:
            return {"schema": SCHEMA, "status": "observation_failed", "verdict": "error", "recover": "retry", "domain": "media", "action": action, "player": player, "route": route_summary(True), "error": playlist_error}
        if action == "playlist_list":
            return {"schema": SCHEMA, "status": "observed", "verdict": "verified", "recover": "proceed", "domain": "media", "action": action, "read_only": True, "player": player, "playlists": playlists, "route": route_summary(True), "verification": {"status": "verified", "predicate": "playlist_catalog_observed"}}
        if not playlist_id:
            return {"schema": SCHEMA, "status": "error", "verdict": "error", "recover": "replan", "domain": "media", "action": action, "player": player, "route": route_summary(True), "playlists": playlists, "error": {"code": "missing_playlist_id", "message": "playlist_activate requires exact playlist object path"}}
        if playlist_id not in {item["id"] for item in playlists}:
            return {"schema": SCHEMA, "status": "target_unavailable", "verdict": "error", "recover": "replan", "domain": "media", "action": action, "player": player, "route": route_summary(True), "playlists": playlists, "error": {"code": "playlist_not_found", "playlist_id": playlist_id}}
        rc, out, err = playlist_call(player, "org.mpris.MediaPlayer2.Playlists.ActivatePlaylist", [playlist_id], env)
        if rc != 0:
            return {"schema": SCHEMA, "status": "action_failed", "verdict": "error", "recover": "retry", "domain": "media", "action": action, "player": player, "route": route_summary(True), "error": {"code": "playlist_activation_failed", "rc": rc, "message": err or out}}
        after, observe_error = observe(player, env)
        verified = after is not None and after.get("metadata_available") and after.get("track_id") is not None
        return {"schema": SCHEMA, "status": "verified" if verified else "unmet", "verdict": "verified" if verified else "unmet", "recover": "proceed" if verified else "replan", "domain": "media", "action": action, "player": player, "playlist_id": playlist_id, "route": route_summary(True), "after": after, "verification": {"status": "verified" if verified else "unmet", "predicate": "playlist_active_with_track" if verified else "playlist_activation_effect_unmet", "observation_error": observe_error}}
    before, error = observe(player, env)
    if error or before is None:
        return {
            "schema": SCHEMA, "status": "observation_failed", "verdict": "error", "recover": "retry",
            "domain": "media", "action": action, "route": route_summary(True), "error": error,
        }
    if action == "volume_get":
        if before.get("volume") is None:
            return {
                "schema": SCHEMA, "status": "observation_failed", "verdict": "error", "recover": "retry",
                "domain": "media", "action": action, "player": player,
                "route": route_summary(True), "before": before,
                "error": {"code": "volume_unavailable", "message": before.get("volume_error")},
            }
        return {
            "schema": SCHEMA, "status": "observed", "verdict": "verified", "recover": "proceed",
            "domain": "media", "action": action, "read_only": True, "player": player,
            "route": route_summary(True), "before": before,
            "verification": {"status": "verified", "predicate": "volume_observed"},
        }
    if action == "state_get":
        return {
            "schema": SCHEMA, "status": "observed", "verdict": "verified", "recover": "proceed",
            "domain": "media", "action": action, "read_only": True, "player": player,
            "route": route_summary(True), "before": before,
            "verification": {"status": "verified", "predicate": "player_state_observed"},
        }
    if action == "position_get":
        if not before.get("position_available"):
            return {
                "schema": SCHEMA, "status": "observation_failed", "verdict": "error", "recover": "retry",
                "domain": "media", "action": action, "player": player,
                "route": route_summary(True), "before": before,
                "error": {"code": "position_unavailable", "message": before.get("position_error") or before.get("duration_error")},
            }
        return {
            "schema": SCHEMA, "status": "observed", "verdict": "verified", "recover": "proceed",
            "domain": "media", "action": action, "read_only": True, "player": player,
            "route": route_summary(True), "before": before,
            "verification": {"status": "verified", "predicate": "media_position_observed"},
        }
    if dry_run:
        if action == "volume_set":
            planned_level = volume
        elif action in ("volume_up", "volume_down") and before.get("volume") is not None:
            planned_level = before["volume"] + (0.05 if action == "volume_up" else -0.05)
            planned_level = max(0.0, min(1.0, planned_level))
        else:
            planned_level = None
        planned_argv = ["playerctl", "-p", player, "volume", f"{planned_level:.3f}"] if planned_level is not None else ["playerctl", "-p", player, action]
        return {
            "schema": SCHEMA, "status": "planned", "verdict": "verified", "recover": "proceed",
            "domain": "media", "action": action, "read_only": True, "player": player,
            "route": route_summary(True), "before": before,
            "dispatch": {"status": "not_dispatched_dry_run", "argv": planned_argv},
            "verification": {"status": "not_run", "reason": "dry_run"},
        }
    if action == "volume_set":
        target = volume
    elif action in ("volume_up", "volume_down"):
        if before.get("volume") is None:
            return {"schema": SCHEMA, "status": "observation_failed", "verdict": "error", "recover": "replan", "domain": "media", "action": action, "player": player, "route": route_summary(True), "error": {"code": "volume_unavailable"}}
        target = before["volume"] + (0.05 if action == "volume_up" else -0.05)
        target = max(0.0, min(1.0, target))
    else:
        target = None
    argv = ["playerctl", "-p", player, "volume", f"{target:.3f}"] if target is not None else ["playerctl", "-p", player, PLAYERCTL_ACTION[action]]
    if target is not None:
        before["requested_volume"] = target
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
    parser.add_argument("--volume", type=float)
    parser.add_argument("--playlist-id")
    args = parser.parse_args()
    payload = execute(args.action, args.player, args.dry_run, min(max(args.verify_timeout, 0.1), 10.0), args.volume, args.playlist_id)
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return 0 if payload.get("verdict") == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
