#!/usr/bin/env python3
"""Bounded application control router — protocol first, UI fallback explicit.

The first adapter is Linux media control over MPRIS via ``playerctl``.  The
script never executes a shell string and never silently falls back to AT-SPI,
vision, or coordinate input.  Every mutation is followed by an independent
MPRIS read that verifies the requested effect.
"""
from __future__ import annotations

import argparse
import copy
import errno
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, MutableMapping

SCHEMA = "agent_bridge.app_control.v0"
OPERATION_SCHEMA = "agent_bridge.app_control.operation.v0"
OPERATION_PREFLIGHT_SCHEMA = "agent_bridge.app_control.operation_preflight.v0"
DEFAULT_OPERATION_TTL_SECS = 3600
MIN_OPERATION_TTL_SECS = 60
MAX_OPERATION_TTL_SECS = 86400
MAX_OPERATION_RECORD_BYTES = 256 * 1024
OPERATION_ID_RE = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z", re.ASCII)
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


def hydrate_session_bus(
    env: MutableMapping[str, str] | None = None,
    *,
    runtime_dir: Path | None = None,
) -> dict[str, str]:
    """Restore a trusted, live session bus for protocol adapters.

    Long-lived MCP processes can retain a non-empty Unix bus address after the
    corresponding socket has disappeared.  Treat that address as stale instead
    of letting every MPRIS operation fail behind an apparently configured bus.
    Non-path transports remain untouched because they cannot be validated with
    local filesystem ownership checks.
    """
    target = os.environ if env is None else env
    if not sys.platform.startswith("linux"):
        return {}
    uid = os.getuid()
    runtime = runtime_dir or Path(target.get("XDG_RUNTIME_DIR", f"/run/user/{uid}"))
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
    existing_address = target.get("DBUS_SESSION_BUS_ADDRESS", "")
    existing_valid = bool(existing_address)
    if existing_address.startswith("unix:path="):
        existing_path = Path(existing_address.removeprefix("unix:path=").split(",", 1)[0])
        try:
            existing_valid = existing_path.is_socket() and existing_path.stat().st_uid == uid
        except OSError:
            existing_valid = False
    if valid_bus and not existing_valid:
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
        return (players[0], None) if len(players) == 1 else (None, "ambiguous_player")
    folded = selector.casefold()
    exact = [player for player in players if player.casefold() == folded]
    matches = exact or [player for player in players if folded in player.casefold()]
    if len(matches) == 1:
        return matches[0], None
    return None, "player_not_found" if not matches else "ambiguous_player"


def select_player_for_action(
    players: list[str], selector: str | None, env: dict[str, str]
) -> tuple[str | None, str | None, dict[str, Any]]:
    """Select one player without depending on MPRIS enumeration order.

    Explicit selectors retain the exact-then-unique-substring contract.  With no
    selector, a single discovered player is safe.  Multiple players require a
    complete status observation and exactly one Playing instance; otherwise the
    caller must disambiguate explicitly.
    """
    if selector or len(players) <= 1:
        player, error = select_player(players, selector)
        return player, error, {
            "policy": "explicit_selector" if selector else "single_discovered_player",
            "selector": selector,
        }

    observations: list[dict[str, Any]] = []
    playing: list[str] = []
    incomplete = False
    for candidate in players:
        rc, out, err = run(["playerctl", "-p", candidate, "status"], env)
        if rc != 0:
            incomplete = True
            observations.append({
                "player": candidate,
                "status": "observation_failed",
                "rc": rc,
                "message": err or out,
            })
            continue
        playback_status = out.strip()
        observations.append({"player": candidate, "status": "observed", "playback_status": playback_status})
        if playback_status.casefold() == "playing":
            playing.append(candidate)

    selection = {
        "policy": "unique_playing_player",
        "selector": None,
        "observations": observations,
        "playing_players": playing,
    }
    if incomplete:
        return None, "player_selection_incomplete", selection
    if len(playing) == 1:
        return playing[0], None, selection
    return None, "ambiguous_player", selection


def playlist_argv(player: str, method: str, args: list[str]) -> list[str]:
    bus = f"org.mpris.MediaPlayer2.{player}"
    return [
        "gdbus",
        "call",
        "--session",
        "--dest",
        bus,
        "--object-path",
        MPRIS_PLAYLIST_PATH,
        "--method",
        method,
        *args,
    ]


def playlist_call(player: str, method: str, args: list[str], env: dict[str, str]) -> tuple[int, str, str]:
    return run(playlist_argv(player, method, args), env)


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


def strict_track_id_changed(
    action: str, before: dict[str, Any], after: dict[str, Any]
) -> tuple[bool, str]:
    """Verify a durable relative-track action from strict MPRIS identities only.

    Artist/title fields may update before the player's track identifier.  They
    are useful presentation metadata, but cannot prove that a relative action
    advanced to a different track across a restart boundary.
    """
    if action != "next":
        return False, "unsupported_durable_effect"
    before_id = before.get("track_id")
    after_id = after.get("track_id")
    return (
        isinstance(before_id, str)
        and bool(before_id)
        and isinstance(after_id, str)
        and bool(after_id)
        and before_id != after_id,
        "track_identity_changed",
    )


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


def execute_once(
    action: str,
    player_selector: str | None,
    dry_run: bool,
    verify_timeout: float,
    volume: float | None = None,
    playlist_id: str | None = None,
    *,
    before_dispatch: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
    effect_check: Callable[
        [str, dict[str, Any], dict[str, Any]], tuple[bool, str]
    ] = effect_verified,
) -> dict[str, Any]:
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
    player, select_error, selection = select_player_for_action(players, player_selector, env)
    if select_error:
        return {
            "schema": SCHEMA, "status": "target_unavailable", "verdict": "error", "recover": "replan",
            "domain": "media", "action": action, "players": players, "selection": selection,
            "route": route_summary(False),
            "error": {"code": select_error, "selector": player_selector},
        }
    assert player is not None
    selection["selected_player"] = player
    if action == "playlist_current":
        active_playlist, active_error = current_playlist(player, env)
        if active_error:
            return {"schema": SCHEMA, "status": "observation_failed", "verdict": "error", "recover": "retry", "domain": "media", "action": action, "player": player, "route": route_summary(True), "error": active_error}
        after, observe_error = observe(player, env)
        return {"schema": SCHEMA, "status": "observed", "verdict": "verified", "recover": "proceed", "domain": "media", "action": action, "read_only": True, "player": player, "selection": selection, "active_playlist": active_playlist, "track_summary": after, "route": route_summary(True), "verification": {"status": "verified", "predicate": "active_playlist_observed", "observation_error": observe_error}}
    if action in ("playlist_list", "playlist_activate"):
        playlists, playlist_error = list_playlists(player, env)
        if playlist_error:
            return {"schema": SCHEMA, "status": "observation_failed", "verdict": "error", "recover": "retry", "domain": "media", "action": action, "player": player, "route": route_summary(True), "error": playlist_error}
        if action == "playlist_list":
            return {"schema": SCHEMA, "status": "observed", "verdict": "verified", "recover": "proceed", "domain": "media", "action": action, "read_only": True, "player": player, "selection": selection, "playlists": playlists, "route": route_summary(True), "verification": {"status": "verified", "predicate": "playlist_catalog_observed"}}
        if not playlist_id:
            return {"schema": SCHEMA, "status": "error", "verdict": "error", "recover": "replan", "domain": "media", "action": action, "player": player, "route": route_summary(True), "playlists": playlists, "error": {"code": "missing_playlist_id", "message": "playlist_activate requires exact playlist object path"}}
        if playlist_id not in {item["id"] for item in playlists}:
            return {"schema": SCHEMA, "status": "target_unavailable", "verdict": "error", "recover": "replan", "domain": "media", "action": action, "player": player, "route": route_summary(True), "playlists": playlists, "error": {"code": "playlist_not_found", "playlist_id": playlist_id}}
        if dry_run:
            planned_argv = playlist_argv(
                player,
                "org.mpris.MediaPlayer2.Playlists.ActivatePlaylist",
                [playlist_id],
            )
            return {
                "schema": SCHEMA,
                "status": "planned",
                "verdict": "verified",
                "recover": "proceed",
                "domain": "media",
                "action": action,
                "read_only": True,
                "player": player,
                "selection": selection,
                "playlist_id": playlist_id,
                "playlists": playlists,
                "route": route_summary(True),
                "dispatch": {
                    "status": "not_dispatched_dry_run",
                    "method": "org.mpris.MediaPlayer2.Playlists.ActivatePlaylist",
                    "argv": planned_argv,
                },
                "verification": {"status": "not_run", "reason": "dry_run"},
            }
        before, before_error = observe(player, env)
        if before is None:
            return {"schema": SCHEMA, "status": "observation_failed", "verdict": "error", "recover": "retry", "domain": "media", "action": action, "player": player, "route": route_summary(True), "error": before_error or {"code": "observation_failed"}}
        preserve_nonplaying = before.get("playback_status") in ("Paused", "Stopped")
        activation_argv = playlist_argv(
            player,
            "org.mpris.MediaPlayer2.Playlists.ActivatePlaylist",
            [playlist_id],
        )
        rc, out, err = run(activation_argv, env)
        activation_dispatch = {
            "status": "dispatched" if rc == 0 else "failed",
            "rc": rc,
            "argv": activation_argv,
            "stdout": out,
            "stderr": err,
        }
        if rc != 0:
            return {"schema": SCHEMA, "status": "action_failed", "verdict": "error", "recover": "retry", "domain": "media", "action": action, "player": player, "route": route_summary(True), "error": {"code": "playlist_activation_failed", "rc": rc, "message": err or out}}
        deadline = time.monotonic() + verify_timeout
        polls = 0
        active_playlist = None
        active_error = None
        after = None
        observe_error = None
        verified = False
        while True:
            polls += 1
            active_playlist, active_error = current_playlist(player, env)
            after, observe_error = observe(player, env)
            verified = (
                active_error is None
                and active_playlist is not None
                and active_playlist.get("active") is True
                and active_playlist.get("id") == playlist_id
            )
            if verified or time.monotonic() >= deadline:
                break
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
        activation_status = after.get("playback_status") if after else None
        pause_dispatch = None
        preservation_verified = not preserve_nonplaying
        if verified and preserve_nonplaying and activation_status == "Playing":
            pause_rc, pause_out, pause_err = run(["playerctl", "-p", player, "pause"], env)
            pause_dispatch = {"status": "dispatched" if pause_rc == 0 else "failed", "rc": pause_rc, "stdout": pause_out, "stderr": pause_err}
            after, observe_error = observe(player, env)
            preservation_verified = pause_rc == 0 and after is not None and after.get("playback_status") == "Paused"
        elif verified and preserve_nonplaying:
            preservation_verified = activation_status != "Playing"
        verified = verified and preservation_verified
        return {"schema": SCHEMA, "status": "verified" if verified else "unmet", "verdict": "verified" if verified else "unmet", "recover": "proceed" if verified else "replan", "domain": "media", "action": action, "read_only": False, "player": player, "selection": selection, "playlist_id": playlist_id, "route": route_summary(True), "before": before, "dispatch": activation_dispatch, "active_playlist": active_playlist, "after": after, "playback_preservation": {"required": preserve_nonplaying, "before_status": before.get("playback_status"), "after_activation_status": activation_status, "status": "verified" if preservation_verified else "unmet", "pause_dispatch": pause_dispatch}, "verification": {"status": "verified" if verified else "unmet", "predicate": "playlist_active_id_matches_target" if verified else "playlist_activation_effect_unmet", "polls": polls, "active_playlist_error": active_error, "observation_error": observe_error}}
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
            "domain": "media", "action": action, "read_only": True, "player": player, "selection": selection,
            "route": route_summary(True), "before": before,
            "verification": {"status": "verified", "predicate": "volume_observed"},
        }
    if action == "state_get":
        return {
            "schema": SCHEMA, "status": "observed", "verdict": "verified", "recover": "proceed",
            "domain": "media", "action": action, "read_only": True, "player": player, "selection": selection,
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
            "domain": "media", "action": action, "read_only": True, "player": player, "selection": selection,
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
            "domain": "media", "action": action, "read_only": True, "player": player, "selection": selection,
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
    if before_dispatch is not None:
        preparation_error = before_dispatch({
            "action": action,
            "argv": argv,
            "before": before,
            "env": env,
            "player": player,
            "selection": selection,
            "session_env_restored": sorted(restored),
        })
        if preparation_error is not None:
            return preparation_error
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
            verified, predicate = effect_check(action, before, after)
            if verified:
                break
        if time.monotonic() >= deadline:
            break
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
    return {
        "schema": SCHEMA, "status": "verified" if verified else "unmet",
        "verdict": "verified" if verified else "unmet", "recover": "proceed" if verified else "replan",
        "domain": "media", "action": action, "read_only": False, "player": player, "selection": selection,
        "route": route_summary(True), "before": before, "dispatch": dispatch, "after": after,
        "verification": {"status": "verified" if verified else "unmet", "predicate": predicate,
                         "polls": polls, "observation_error": observation_error},
        "session_env_restored": sorted(restored),
        "duration_ms": round((time.monotonic() - started) * 1000),
    }


def operation_directory(env: MutableMapping[str, str] | None = None) -> Path:
    source = os.environ if env is None else env
    configured = source.get("AB_APP_CONTROL_OPERATION_DIR")
    if configured:
        return Path(configured).expanduser()
    state_home = source.get("XDG_STATE_HOME")
    base = Path(state_home).expanduser() if state_home else Path.home() / ".local" / "state"
    return base / "agent-bridge" / "app_control_operations"


def operation_record_path(
    operation_id: str, env: MutableMapping[str, str] | None = None
) -> Path:
    key = hashlib.sha256(operation_id.encode("ascii")).hexdigest()
    return operation_directory(env) / f"{key}.json"


def operation_lock_path(
    operation_id: str, env: MutableMapping[str, str] | None = None
) -> Path:
    key = hashlib.sha256(operation_id.encode("ascii")).hexdigest()
    return operation_directory(env) / f"{key}.lock"


def operation_request(
    action: str, player_selector: str | None, operation_ttl_secs: int
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "action": action,
        "player_selector": player_selector,
        "operation_ttl_secs": operation_ttl_secs,
    }


def operation_request_digest(
    action: str, player_selector: str | None, operation_ttl_secs: int
) -> str:
    canonical = json.dumps(
        operation_request(action, player_selector, operation_ttl_secs),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def ensure_operation_directory(path: Path) -> None:
    if not path.is_absolute():
        raise OSError("operation journal path must be absolute")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise OSError(f"operation journal is not a directory: {path}")
    os.chmod(path, 0o700)


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    """Durably replace one journal record without exposing a partial JSON file."""
    encoded = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    fd = -1
    temporary = ""
    try:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = ""
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def read_operation_record(path: Path) -> dict[str, Any] | None:
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
    except FileNotFoundError:
        return None
    try:
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            fd = -1
            value = json.load(stream)
    finally:
        if fd >= 0:
            os.close(fd)
    if not isinstance(value, dict):
        raise ValueError("operation record must be a JSON object")
    return value


def read_operation_record_snapshot(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read one bounded, owner-only regular record without following symlinks."""
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
    except FileNotFoundError:
        return None, None
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("operation record must be a regular file")
        if metadata.st_uid != os.getuid():
            raise ValueError("operation record must be owned by the current user")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise ValueError("operation record mode must be 0600")
        if metadata.st_size <= 0 or metadata.st_size > MAX_OPERATION_RECORD_BYTES:
            raise ValueError("operation record size is outside the bounded range")
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            encoded = stream.read(MAX_OPERATION_RECORD_BYTES + 1)
    finally:
        if fd >= 0:
            os.close(fd)
    if len(encoded) > MAX_OPERATION_RECORD_BYTES:
        raise ValueError("operation record exceeds the bounded read limit")
    try:
        value = json.loads(encoded.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("operation record is not valid UTF-8") from exc
    if not isinstance(value, dict):
        raise ValueError("operation record must be a JSON object")
    return value, hashlib.sha256(encoded).hexdigest()


def operation_transaction(
    operation_id: str,
    request_digest: str | None,
    *,
    phase: str,
    dispatch_count: int,
    idempotent_replay: bool,
    recovered_after_interruption: bool,
    expires_at: float | None,
) -> dict[str, Any]:
    return {
        "schema": OPERATION_SCHEMA,
        "operation_id": operation_id,
        "request_digest": request_digest,
        "phase": phase,
        "dispatch_count": dispatch_count,
        "idempotent_replay": idempotent_replay,
        "recovered_after_interruption": recovered_after_interruption,
        "external_execution_repeated": False,
        "expires_at": expires_at,
    }


def with_operation_transaction(
    payload: dict[str, Any], transaction: dict[str, Any]
) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    result["transaction"] = transaction
    return result


def operation_error(
    action: str,
    operation_id: Any,
    request_digest: str | None,
    code: str,
    message: str,
    *,
    phase: str = "rejected",
    dispatch_count: int = 0,
    expires_at: float | None = None,
    recover: str = "replan",
    status: str = "error",
    recovered_after_interruption: bool = False,
) -> dict[str, Any]:
    printable_id = operation_id if isinstance(operation_id, str) else str(operation_id)
    return {
        "schema": SCHEMA,
        "status": status,
        "verdict": "error",
        "recover": recover,
        "domain": "media",
        "action": action,
        "route": route_summary(False),
        "error": {"code": code, "message": message},
        "transaction": operation_transaction(
            printable_id,
            request_digest,
            phase=phase,
            dispatch_count=dispatch_count,
            idempotent_replay=False,
            recovered_after_interruption=recovered_after_interruption,
            expires_at=expires_at,
        ),
    }


def operation_record(
    operation_id: str,
    request_digest: str,
    request: dict[str, Any],
    *,
    created_at: float,
    expires_at: float,
    phase: str,
    dispatch_count: int,
    player: str | None = None,
    baseline: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema": OPERATION_SCHEMA,
        "operation_id": operation_id,
        "request_digest": request_digest,
        "request": request,
        "phase": phase,
        "dispatch_count": dispatch_count,
        "created_at": created_at,
        "expires_at": expires_at,
        "player": player,
        "resolved_player": player,
        "baseline": baseline,
    }
    if payload is not None:
        record["payload"] = payload
    return record


def terminal_record_from(
    base_record: dict[str, Any], payload: dict[str, Any], dispatch_count: int
) -> dict[str, Any]:
    record = copy.deepcopy(base_record)
    record["phase"] = "terminal"
    record["dispatch_count"] = dispatch_count
    if record.get("player") is None and isinstance(payload.get("player"), str):
        record["player"] = payload["player"]
        record["resolved_player"] = payload["player"]
    if record.get("baseline") is None and isinstance(payload.get("before"), dict):
        record["baseline"] = payload["before"]
    record["payload"] = payload
    return record


def replay_terminal_operation(
    record: dict[str, Any], operation_id: str, request_digest: str
) -> dict[str, Any]:
    payload = record.get("payload")
    if not terminal_payload_valid(
        payload,
        record,
        operation_id,
        request_digest,
    ):
        stored_request = record.get("request")
        recorded_action = (
            str(stored_request.get("action", "next"))
            if isinstance(stored_request, dict)
            else "next"
        )
        return operation_error(
            recorded_action,
            operation_id,
            request_digest,
            "operation_record_invalid",
            "terminal operation record has no admissible payload",
            phase="terminal",
            dispatch_count=int(record.get("dispatch_count", 0)),
            expires_at=record.get("expires_at"),
        )
    previous_transaction = payload.get("transaction")
    recovered = bool(
        isinstance(previous_transaction, dict)
        and previous_transaction.get("recovered_after_interruption")
    )
    return with_operation_transaction(
        payload,
        operation_transaction(
            operation_id,
            request_digest,
            phase="verified" if payload.get("verdict") == "verified" else "terminal",
            dispatch_count=int(record.get("dispatch_count", 0)),
            idempotent_replay=True,
            recovered_after_interruption=recovered,
            expires_at=record.get("expires_at"),
        ),
    )


def terminal_payload_valid(
    payload: Any,
    record: Any,
    operation_id: str,
    request_digest: str,
) -> bool:
    """Validate a stored receipt before allowing it to become a replay result."""
    if not isinstance(payload, dict) or not isinstance(record, dict):
        return False
    request = record.get("request")
    dispatch_count = record.get("dispatch_count")
    expires_at = record.get("expires_at")
    baseline = record.get("baseline")
    recorded_player = record.get("resolved_player") or record.get("player")
    if (
        record.get("schema") != OPERATION_SCHEMA
        or record.get("operation_id") != operation_id
        or record.get("request_digest") != request_digest
        or record.get("phase") != "terminal"
        or not isinstance(request, dict)
        or request.get("schema") != SCHEMA
        or request.get("action") != "next"
        or type(dispatch_count) is not int
        or dispatch_count not in (0, 1)
        or type(expires_at) not in (int, float)
        or isinstance(expires_at, bool)
        or not math.isfinite(float(expires_at))
    ):
        return False
    verdict = payload.get("verdict")
    recover = payload.get("recover")
    transaction = payload.get("transaction")
    if (
        payload.get("schema") != SCHEMA
        or payload.get("domain") != "media"
        or payload.get("action") != request.get("action")
        or not isinstance(payload.get("status"), str)
        or verdict not in ("verified", "unmet", "error")
        or not isinstance(transaction, dict)
        or transaction.get("schema") != OPERATION_SCHEMA
        or transaction.get("operation_id") != operation_id
        or transaction.get("request_digest") != request_digest
        or type(transaction.get("dispatch_count")) is not int
        or transaction.get("dispatch_count") != dispatch_count
        or transaction.get("external_execution_repeated") is not False
        or transaction.get("idempotent_replay") is not False
        or type(transaction.get("recovered_after_interruption")) is not bool
        or type(transaction.get("expires_at")) not in (int, float)
        or isinstance(transaction.get("expires_at"), bool)
        or not math.isfinite(float(transaction["expires_at"]))
        or float(transaction["expires_at"]) != float(expires_at)
    ):
        return False
    if verdict != "verified":
        if (
            recover not in ("retry", "replan")
            or (dispatch_count == 1 and recover != "replan")
            or transaction.get("phase") not in (
                "retryable",
                "terminal",
                "indeterminate",
                "journal_write_failed",
                "dispatch_started",
            )
        ):
            return False
        if dispatch_count == 1:
            return (
                isinstance(recorded_player, str)
                and bool(recorded_player)
                and isinstance(baseline, dict)
                and payload.get("player") == recorded_player
                and payload.get("before") == baseline
            )
        return True
    if (
        payload.get("status") != "verified"
        or recover != "proceed"
        or dispatch_count != 1
        or transaction.get("phase") != "verified"
        or payload.get("read_only") is not False
        or not isinstance(payload.get("verification"), dict)
        or payload["verification"].get("status") != "verified"
    ):
        return False
    before = payload.get("before")
    after = payload.get("after")
    selection = payload.get("selection")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return False
    if (
        not isinstance(recorded_player, str)
        or not recorded_player
        or payload.get("player") != recorded_player
        or not isinstance(selection, dict)
        or selection.get("selected_player") != recorded_player
        or selection.get("selector") != request.get("player_selector")
        or not isinstance(baseline, dict)
        or before != baseline
    ):
        return False
    changed, _ = strict_track_id_changed("next", before, after)
    if not changed:
        return False
    recovered = transaction["recovered_after_interruption"]
    predicate = payload["verification"].get("predicate")
    if recovered:
        return (
            predicate == "track_identity_changed_after_restart"
            and payload.get("causal_attribution") == "unknown_after_restart"
            and payload.get("dispatch") is None
        )
    dispatch = payload.get("dispatch")
    return (
        predicate == "track_identity_changed"
        and isinstance(dispatch, dict)
        and dispatch.get("status") == "dispatched"
        and type(dispatch.get("rc")) is int
        and dispatch.get("rc") == 0
        and dispatch.get("argv")
        == ["playerctl", "-p", recorded_player, "next"]
    )


def recover_dispatch_started_operation(
    record: dict[str, Any], operation_id: str, request_digest: str
) -> dict[str, Any]:
    """Resolve an interrupted next operation by observation, never by re-dispatch."""
    player = record.get("resolved_player") or record.get("player")
    baseline = record.get("baseline")
    expires_at = record.get("expires_at")
    dispatch_count = int(record.get("dispatch_count", 1))
    env = dict(os.environ)
    restored = hydrate_session_bus(env)
    after: dict[str, Any] | None = None
    observation_error: dict[str, Any] | None = None
    reason: str | None = None
    if not isinstance(player, str) or not player:
        reason = "persisted_player_missing"
    elif not isinstance(baseline, dict) or not isinstance(baseline.get("track_id"), str) or not baseline.get("track_id"):
        reason = "baseline_track_id_missing"
    else:
        after, observation_error = observe(player, env)
        if after is None:
            reason = "observation_failed"
        elif not isinstance(after.get("track_id"), str) or not after.get("track_id"):
            reason = "current_track_id_missing"
        elif after["track_id"] == baseline["track_id"]:
            reason = "track_id_unchanged"

    verified = reason is None
    transaction = operation_transaction(
        operation_id,
        request_digest,
        phase="verified" if verified else "indeterminate",
        dispatch_count=dispatch_count,
        idempotent_replay=False,
        recovered_after_interruption=True,
        expires_at=expires_at,
    )
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "verified" if verified else "indeterminate",
        "verdict": "verified" if verified else "error",
        "recover": "proceed" if verified else "replan",
        "domain": "media",
        "action": "next",
        "read_only": False,
        "player": player,
        "selection": {
            "policy": "persisted_exact_player",
            "selector": (
                record.get("request", {}).get("player_selector")
                if isinstance(record.get("request"), dict)
                else None
            ),
            "selected_player": player,
        },
        "route": route_summary(isinstance(player, str) and bool(player)),
        "before": baseline,
        "after": after,
        "causal_attribution": "unknown_after_restart",
        "verification": {
            "status": "verified" if verified else "indeterminate",
            "predicate": "track_identity_changed_after_restart",
            "causal_attribution": "unknown_after_restart",
            "observation_error": observation_error,
            "reason": reason,
        },
        "session_env_restored": sorted(restored),
        "transaction": transaction,
    }
    if not verified:
        payload["error"] = {
            "code": "operation_outcome_indeterminate",
            "message": "interrupted operation cannot be safely attributed or repeated",
            "reason": reason,
        }
    return payload


def operation_preflight_payload(
    operation_id: str,
    request: dict[str, Any],
    request_digest: str,
    *,
    state: str,
    outcome: str,
    recover: str,
    record_present: bool | None,
    observed_phase: str | None = None,
    dispatch_count: int | None = None,
    expires_at: float | None = None,
    terminal_verdict: str | None = None,
    observed_at: float | None = None,
    remaining_secs: float | None = None,
    record_sha256: str | None = None,
    lock_present: bool | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Return a read-only advisory receipt; it never authorizes dispatch."""
    eligible = outcome == "eligible"
    blocked = not eligible
    if observed_at is None:
        observed_at = time.time()
    if eligible:
        disposition = "reusable_same_request"
        same_id_retry_allowed = True
        recommended_next = "proceed_to_connection_then_revalidate_under_exclusive_lock"
    elif state == "operation_lock_busy":
        disposition = "indeterminate_do_not_replace_automatically"
        same_id_retry_allowed = True
        recommended_next = "retry_the_same_exact_request_after_the_current_holder_finishes"
    elif state == "operation_expired":
        disposition = "expired"
        same_id_retry_allowed = False
        recommended_next = "replan_from_current_state_without_automatic_actuation_or_id_replacement"
    elif state == "idempotency_conflict":
        disposition = "conflicts_with_request"
        same_id_retry_allowed = False
        recommended_next = "resolve_the_original_request_binding_or_create_an_explicit_new_intent"
    elif state == "terminal_operation_not_verified":
        disposition = "terminal_failure"
        same_id_retry_allowed = False
        recommended_next = (
            "reobserve_and_replan_without_automatic_new_id"
            if dispatch_count == 1
            else "create_a_new_id_only_for_an_explicit_new_intent"
        )
    else:
        disposition = "invalid_or_unavailable"
        same_id_retry_allowed = False
        recommended_next = "audit_or_repair_the_journal_without_deleting_or_replacing_the_id_automatically"
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": state,
        "verdict": "verified" if eligible else "error",
        "recover": "proceed" if eligible else recover,
        "domain": "media",
        "action": "next",
        "read_only": True,
        "preflight_only": True,
        "route": route_summary(False),
        "preflight": {
            "schema": OPERATION_PREFLIGHT_SCHEMA,
            "outcome": outcome,
            "state": state,
            "operation_id": operation_id,
            "request": request,
            "request_digest": request_digest,
            "record_present": record_present,
            "observed_phase": observed_phase,
            "dispatch_count": dispatch_count,
            "expires_at": expires_at,
            "terminal_verdict": terminal_verdict,
            "observed_at_unix_seconds": observed_at,
            "remaining_secs": remaining_secs,
            "record_sha256": record_sha256,
            "lock_present": lock_present,
            "candidate": eligible,
            "blocked": blocked,
            "advisory": True,
            "must_revalidate": True,
            "dispatch_authorized": False,
            "reservation_created": False,
            "operation_record_mutated": False,
            "player_observed": False,
            "effect_verified": False,
            "operation_id_disposition": disposition,
            "same_id_retry_allowed": same_id_retry_allowed,
            "automatic_new_id_allowed": False,
            "recommended_next": recommended_next,
        },
        "claim_boundary": {
            "authorizes_dispatch": False,
            "reserves_operation_id": False,
            "lock_held_at_return": False,
            "state_unchanged_until_action": False,
            "player_observed": False,
            "effect_verified": False,
            "current_track_verified": False,
        },
        "error": None,
    }
    if not eligible:
        payload["error"] = {
            "code": error_code or state,
            "message": error_message or "durable operation preflight did not pass",
        }
    return payload


def preflight_operation(
    action: str,
    player_selector: str | None,
    dry_run: bool,
    operation_id: Any,
    operation_ttl_secs: int,
) -> dict[str, Any]:
    """Advisory journal inspection with no player access or durable record write.

    This can reject an already-known conflict, expiry, malformed record, or
    terminal failure before a caller creates a presentation session.  A pass is
    never an execution lease: the mutating path must acquire its exclusive lock
    and repeat every check after connection confirmation.
    """
    if not isinstance(operation_id, str) or OPERATION_ID_RE.fullmatch(operation_id) is None:
        printable = operation_id if isinstance(operation_id, str) else str(operation_id)
        return operation_preflight_payload(
            printable,
            operation_request(action, player_selector, operation_ttl_secs),
            "",
            state="invalid_operation_id",
            outcome="blocked",
            recover="replan",
            record_present=False,
            error_code="invalid_operation_id",
            error_message="operation_id must be 1..128 ASCII alphanumeric or . _ : - characters",
        )
    if type(operation_ttl_secs) is not int or not (
        MIN_OPERATION_TTL_SECS <= operation_ttl_secs <= MAX_OPERATION_TTL_SECS
    ):
        return operation_preflight_payload(
            operation_id,
            operation_request(action, player_selector, operation_ttl_secs),
            "",
            state="invalid_operation_ttl_secs",
            outcome="blocked",
            recover="replan",
            record_present=False,
            error_code="invalid_operation_ttl_secs",
            error_message="operation_ttl_secs must be an integer from 60 through 86400",
        )
    request = operation_request(action, player_selector, operation_ttl_secs)
    request_digest = operation_request_digest(action, player_selector, operation_ttl_secs)
    if action != "next" or dry_run:
        return operation_preflight_payload(
            operation_id,
            request,
            request_digest,
            state="unsupported_idempotent_operation",
            outcome="blocked",
            recover="replan",
            record_present=False,
            error_code="unsupported_idempotent_operation",
            error_message="operation preflight is supported only for action=next with dry_run=false",
        )

    journal_dir = operation_directory()
    if not journal_dir.is_absolute():
        return operation_preflight_payload(
            operation_id,
            request,
            request_digest,
            state="operation_journal_unavailable",
            outcome="blocked",
            recover="replan",
            record_present=False,
            error_code="operation_journal_unavailable",
            error_message="operation journal path must be absolute",
        )
    try:
        try:
            directory_metadata = os.lstat(journal_dir)
        except FileNotFoundError:
            directory_metadata = None
        if directory_metadata is not None and (
            not stat.S_ISDIR(directory_metadata.st_mode)
            or directory_metadata.st_uid != os.getuid()
            or stat.S_IMODE(directory_metadata.st_mode) != 0o700
        ):
            raise OSError(
                "operation journal must be an owner-only 0700 directory without symlinks"
            )
    except OSError as exc:
        return operation_preflight_payload(
            operation_id,
            request,
            request_digest,
            state="operation_journal_unavailable",
            outcome="blocked",
            recover="replan",
            record_present=False,
            error_code="operation_journal_unavailable",
            error_message=str(exc),
        )

    record_path = operation_record_path(operation_id)
    lock_path = operation_lock_path(operation_id)
    lock_fd = -1
    locked = False
    lock_present = False
    try:
        try:
            lock_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            lock_fd = os.open(lock_path, lock_flags)
            lock_present = True
        except FileNotFoundError:
            lock_fd = -1
        except OSError as exc:
            return operation_preflight_payload(
                operation_id,
                request,
                request_digest,
                state="operation_record_invalid",
                outcome="blocked",
                recover="replan",
                record_present=None,
                lock_present=True,
                observed_at=time.time(),
                error_code="operation_record_invalid",
                error_message=f"operation lock cannot be opened safely: {exc}",
            )
        if lock_fd >= 0:
            lock_metadata = os.fstat(lock_fd)
            if (
                not stat.S_ISREG(lock_metadata.st_mode)
                or lock_metadata.st_uid != os.getuid()
                or stat.S_IMODE(lock_metadata.st_mode) != 0o600
            ):
                return operation_preflight_payload(
                    operation_id,
                    request,
                    request_digest,
                    state="operation_record_invalid",
                    outcome="blocked",
                    recover="replan",
                    record_present=None,
                    lock_present=True,
                    observed_at=time.time(),
                    error_code="operation_record_invalid",
                    error_message="operation lock must be an owner-only 0600 regular file",
                )
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                locked = True
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                return operation_preflight_payload(
                    operation_id,
                    request,
                    request_digest,
                    state="operation_lock_busy",
                    outcome="indeterminate",
                    recover="retry",
                    record_present=None,
                    lock_present=True,
                    observed_at=time.time(),
                    error_code="operation_lock_busy",
                    error_message="another process is handling this operation_id",
                )
        try:
            existing, record_sha256 = read_operation_record_snapshot(record_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return operation_preflight_payload(
                operation_id,
                request,
                request_digest,
                state="operation_record_invalid",
                outcome="blocked",
                recover="replan",
                record_present=True,
                lock_present=lock_present,
                observed_at=time.time(),
                error_code="operation_record_invalid",
                error_message=str(exc),
            )
        if existing is None:
            return operation_preflight_payload(
                operation_id,
                request,
                request_digest,
                state="fresh_candidate",
                outcome="eligible",
                recover="proceed",
                record_present=False,
                observed_phase=None,
                dispatch_count=0,
                observed_at=time.time(),
                lock_present=lock_present,
            )
        if not lock_present:
            return operation_preflight_payload(
                operation_id,
                request,
                request_digest,
                state="operation_record_invalid",
                outcome="blocked",
                recover="replan",
                record_present=True,
                observed_at=time.time(),
                record_sha256=record_sha256,
                lock_present=False,
                error_code="operation_record_invalid",
                error_message="operation record exists without its stable lock file",
            )

        phase = existing.get("phase")
        raw_dispatch_count = existing.get("dispatch_count")
        reported_dispatch_count = (
            raw_dispatch_count if type(raw_dispatch_count) is int else None
        )
        raw_expires_at = existing.get("expires_at")
        reported_expires_at = (
            float(raw_expires_at)
            if type(raw_expires_at) in (int, float)
            and not isinstance(raw_expires_at, bool)
            and math.isfinite(float(raw_expires_at))
            else None
        )
        observed_at = time.time()
        remaining_secs = (
            max(0.0, reported_expires_at - observed_at)
            if reported_expires_at is not None
            else None
        )

        def blocked(code: str, message: str, *, recover: str = "replan") -> dict[str, Any]:
            return operation_preflight_payload(
                operation_id,
                request,
                request_digest,
                state=code,
                outcome="indeterminate" if recover == "retry" else "blocked",
                recover=recover,
                record_present=True,
                observed_phase=phase if isinstance(phase, str) else None,
                dispatch_count=reported_dispatch_count,
                expires_at=reported_expires_at,
                observed_at=observed_at,
                remaining_secs=remaining_secs,
                record_sha256=record_sha256,
                lock_present=True,
                terminal_verdict=(
                    existing.get("payload", {}).get("verdict")
                    if isinstance(existing.get("payload"), dict)
                    else None
                ),
                error_code=code,
                error_message=message,
            )

        if existing.get("operation_id") != operation_id:
            return blocked(
                "operation_record_invalid",
                "operation record identity does not match its filename",
            )
        if existing.get("request_digest") != request_digest:
            return blocked(
                "idempotency_conflict",
                "operation_id is already bound to a different canonical request",
            )
        if existing.get("schema") != OPERATION_SCHEMA or existing.get("request") != request:
            return blocked(
                "operation_record_invalid",
                "operation record canonical request binding is malformed",
            )
        if reported_dispatch_count not in (0, 1):
            return blocked(
                "operation_record_invalid",
                "operation record dispatch_count must be 0 or 1",
            )
        if reported_expires_at is None:
            return blocked(
                "operation_record_invalid",
                "operation record has no valid expires_at",
            )
        created_at = existing.get("created_at")
        now = observed_at
        if (
            type(created_at) not in (int, float)
            or isinstance(created_at, bool)
            or not math.isfinite(float(created_at))
            or float(created_at) > now
            or not math.isclose(
                reported_expires_at - float(created_at),
                float(operation_ttl_secs),
                rel_tol=0.0,
                abs_tol=0.001,
            )
        ):
            return blocked(
                "operation_record_invalid",
                "operation record has inconsistent TTL timestamps",
            )
        if now >= reported_expires_at:
            return blocked(
                "operation_expired",
                "operation_id receipt has expired and cannot be executed again",
            )
        if phase == "terminal":
            if not terminal_payload_valid(existing.get("payload"), existing, operation_id, request_digest):
                return blocked(
                    "operation_record_invalid",
                    "terminal operation record has no admissible payload",
                )
            terminal_verdict = existing["payload"].get("verdict")
            if terminal_verdict != "verified":
                return blocked(
                    "terminal_operation_not_verified",
                    "terminal operation cannot make this embodied episode succeed",
                )
            return operation_preflight_payload(
                operation_id,
                request,
                request_digest,
                state="terminal_replay_candidate",
                outcome="eligible",
                recover="proceed",
                record_present=True,
                observed_phase="terminal",
                dispatch_count=reported_dispatch_count,
                expires_at=reported_expires_at,
                terminal_verdict="verified",
                observed_at=observed_at,
                remaining_secs=remaining_secs,
                record_sha256=record_sha256,
                lock_present=True,
            )
        if phase == "retryable" and reported_dispatch_count == 0:
            return operation_preflight_payload(
                operation_id,
                request,
                request_digest,
                state="retryable_candidate",
                outcome="eligible",
                recover="proceed",
                record_present=True,
                observed_phase="retryable",
                dispatch_count=0,
                expires_at=reported_expires_at,
                observed_at=observed_at,
                remaining_secs=remaining_secs,
                record_sha256=record_sha256,
                lock_present=True,
            )
        if phase == "dispatch_started" and reported_dispatch_count == 1:
            player = existing.get("resolved_player") or existing.get("player")
            baseline = existing.get("baseline")
            if (
                not isinstance(player, str)
                or not player
                or not isinstance(baseline, dict)
                or not isinstance(baseline.get("track_id"), str)
                or not baseline.get("track_id")
            ):
                return blocked(
                    "operation_record_invalid",
                    "dispatch_started record lacks an exact player or baseline track_id",
                )
            return operation_preflight_payload(
                operation_id,
                request,
                request_digest,
                state="recovery_observation_candidate",
                outcome="eligible",
                recover="proceed",
                record_present=True,
                observed_phase="dispatch_started",
                dispatch_count=1,
                expires_at=reported_expires_at,
                observed_at=observed_at,
                remaining_secs=remaining_secs,
                record_sha256=record_sha256,
                lock_present=True,
            )
        return blocked(
            "operation_record_invalid",
            f"unsupported operation phase/count: {phase!r}/{reported_dispatch_count!r}",
        )
    except OSError as exc:
        return operation_preflight_payload(
            operation_id,
            request,
            request_digest,
            state="operation_journal_unavailable",
            outcome="blocked",
            recover="replan",
            record_present=None,
            lock_present=lock_present,
            observed_at=time.time(),
            error_code="operation_journal_unavailable",
            error_message=str(exc),
        )
    finally:
        if locked:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
        if lock_fd >= 0:
            os.close(lock_fd)


def execute(
    action: str,
    player_selector: str | None,
    dry_run: bool,
    verify_timeout: float,
    volume: float | None = None,
    playlist_id: str | None = None,
    operation_id: str | None = None,
    operation_ttl_secs: int = DEFAULT_OPERATION_TTL_SECS,
    operation_preflight: bool = False,
) -> dict[str, Any]:
    if operation_preflight:
        return preflight_operation(
            action,
            player_selector,
            dry_run,
            operation_id,
            operation_ttl_secs,
        )
    if operation_id is None:
        return execute_once(
            action, player_selector, dry_run, verify_timeout, volume, playlist_id
        )

    if not isinstance(operation_id, str) or OPERATION_ID_RE.fullmatch(operation_id) is None:
        return operation_error(
            action,
            operation_id,
            None,
            "invalid_operation_id",
            "operation_id must be 1..128 ASCII alphanumeric or . _ : - characters",
        )
    if type(operation_ttl_secs) is not int or not (
        MIN_OPERATION_TTL_SECS <= operation_ttl_secs <= MAX_OPERATION_TTL_SECS
    ):
        return operation_error(
            action,
            operation_id,
            None,
            "invalid_operation_ttl_secs",
            "operation_ttl_secs must be an integer from 60 through 86400",
        )
    request = operation_request(action, player_selector, operation_ttl_secs)
    request_digest = operation_request_digest(action, player_selector, operation_ttl_secs)
    if action != "next" or dry_run:
        return operation_error(
            action,
            operation_id,
            request_digest,
            "unsupported_idempotent_operation",
            "operation_id is supported only for action=next with dry_run=false",
        )

    journal_dir = operation_directory()
    record_path = operation_record_path(operation_id)
    lock_path = operation_lock_path(operation_id)
    try:
        ensure_operation_directory(journal_dir)
    except OSError as exc:
        return operation_error(
            action,
            operation_id,
            request_digest,
            "operation_journal_unavailable",
            str(exc),
        )

    lock_fd = -1
    locked = False
    try:
        lock_flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        lock_fd = os.open(lock_path, lock_flags, 0o600)
        os.fchmod(lock_fd, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            return operation_error(
                action,
                operation_id,
                request_digest,
                "operation_lock_busy",
                "another process is handling this operation_id",
                phase="lock_busy",
                recover="retry",
            )

        try:
            existing = read_operation_record(record_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return operation_error(
                action,
                operation_id,
                request_digest,
                "operation_record_invalid",
                str(exc),
                phase="journal_error",
            )

        now = time.time()
        created_at = now
        expires_at = created_at + operation_ttl_secs
        base_record = operation_record(
            operation_id,
            request_digest,
            request,
            created_at=created_at,
            expires_at=expires_at,
            phase="fresh",
            dispatch_count=0,
        )
        if existing is not None:
            if existing.get("operation_id") != operation_id:
                return operation_error(
                    action,
                    operation_id,
                    request_digest,
                    "operation_record_invalid",
                    "operation record identity does not match its filename",
                    phase="journal_error",
                )
            if existing.get("request_digest") != request_digest:
                reported_dispatch_count = existing.get("dispatch_count")
                if type(reported_dispatch_count) is not int:
                    reported_dispatch_count = 0
                return operation_error(
                    action,
                    operation_id,
                    request_digest,
                    "idempotency_conflict",
                    "operation_id is already bound to a different canonical request",
                    phase=str(existing.get("phase", "journal_error")),
                    dispatch_count=reported_dispatch_count,
                    expires_at=existing.get("expires_at"),
                )
            if existing.get("schema") != OPERATION_SCHEMA or existing.get("request") != request:
                return operation_error(
                    action,
                    operation_id,
                    request_digest,
                    "operation_record_invalid",
                    "operation record canonical request binding is malformed",
                    phase="journal_error",
                )
            dispatch_count = existing.get("dispatch_count")
            if type(dispatch_count) is not int or dispatch_count not in (0, 1):
                return operation_error(
                    action,
                    operation_id,
                    request_digest,
                    "operation_record_invalid",
                    "operation record dispatch_count must be 0 or 1",
                    phase="journal_error",
                )
            expires_at = existing.get("expires_at")
            if type(expires_at) not in (int, float) or not math.isfinite(float(expires_at)):
                return operation_error(
                    action,
                    operation_id,
                    request_digest,
                    "operation_record_invalid",
                    "operation record has no valid expires_at",
                    phase="journal_error",
                    dispatch_count=dispatch_count,
                )
            recorded_created_at = existing.get("created_at")
            if (
                type(recorded_created_at) not in (int, float)
                or not math.isfinite(float(recorded_created_at))
                or float(recorded_created_at) > now
                or not math.isclose(
                    float(expires_at) - float(recorded_created_at),
                    float(operation_ttl_secs),
                    rel_tol=0.0,
                    abs_tol=0.001,
                )
            ):
                return operation_error(
                    action,
                    operation_id,
                    request_digest,
                    "operation_record_invalid",
                    "operation record has inconsistent TTL timestamps",
                    phase="journal_error",
                    dispatch_count=dispatch_count,
                )
            if now >= float(expires_at):
                return operation_error(
                    action,
                    operation_id,
                    request_digest,
                    "operation_expired",
                    "operation_id receipt has expired and cannot be executed again",
                    phase=str(existing.get("phase", "expired")),
                    dispatch_count=dispatch_count,
                    expires_at=float(expires_at),
                )
            phase = existing.get("phase")
            if phase == "terminal":
                return replay_terminal_operation(existing, operation_id, request_digest)
            if phase == "retryable":
                if dispatch_count != 0:
                    return operation_error(
                        action,
                        operation_id,
                        request_digest,
                        "operation_record_invalid",
                        "retryable operation record must have dispatch_count=0",
                        phase="journal_error",
                        dispatch_count=dispatch_count,
                        expires_at=float(expires_at),
                    )
                created_at = float(recorded_created_at)
                expires_at = float(expires_at)
                base_record = operation_record(
                    operation_id,
                    request_digest,
                    request,
                    created_at=created_at,
                    expires_at=expires_at,
                    phase="fresh",
                    dispatch_count=0,
                )
            elif phase != "dispatch_started":
                return operation_error(
                    action,
                    operation_id,
                    request_digest,
                    "operation_record_invalid",
                    f"unsupported operation phase: {phase!r}",
                    phase="journal_error",
                    dispatch_count=dispatch_count,
                    expires_at=float(expires_at),
                )
            else:
                if dispatch_count != 1:
                    return operation_error(
                        action,
                        operation_id,
                        request_digest,
                        "operation_record_invalid",
                        "dispatch_started operation record must have dispatch_count=1",
                        phase="journal_error",
                        dispatch_count=dispatch_count,
                        expires_at=float(expires_at),
                    )

                recovered_payload = recover_dispatch_started_operation(
                    existing, operation_id, request_digest
                )
                terminal = terminal_record_from(
                    existing, recovered_payload, dispatch_count
                )
                try:
                    atomic_write_json(record_path, terminal)
                except OSError as exc:
                    failed = operation_error(
                        action,
                        operation_id,
                        request_digest,
                        "journal_write_failed",
                        f"could not persist recovered terminal receipt: {exc}",
                        phase="dispatch_started",
                        dispatch_count=dispatch_count,
                        expires_at=float(expires_at),
                        status="indeterminate",
                        recovered_after_interruption=True,
                    )
                    failed["recovered_result"] = recovered_payload
                    return failed
                return recovered_payload
        prepared = False
        preparation_write_failed = False

        def persist_dispatch_started(context: dict[str, Any]) -> dict[str, Any] | None:
            nonlocal base_record, prepared, preparation_write_failed
            before = context["before"]
            player = context["player"]
            if not isinstance(before.get("track_id"), str) or not before.get("track_id"):
                return {
                    "schema": SCHEMA,
                    "status": "observation_failed",
                    "verdict": "error",
                    "recover": "replan",
                    "domain": "media",
                    "action": action,
                    "player": player,
                    "selection": context["selection"],
                    "route": route_summary(True),
                    "before": before,
                    "dispatch": {
                        "status": "not_dispatched_missing_baseline",
                        "argv": context["argv"],
                    },
                    "error": {
                        "code": "missing_baseline_track_id",
                        "message": "durable next requires a non-empty baseline track_id",
                    },
                }
            if time.time() >= expires_at:
                return operation_error(
                    action,
                    operation_id,
                    request_digest,
                    "operation_expired",
                    "operation expired before its dispatch budget could be consumed",
                    phase="terminal",
                    dispatch_count=0,
                    expires_at=expires_at,
                )
            base_record = operation_record(
                operation_id,
                request_digest,
                request,
                created_at=created_at,
                expires_at=expires_at,
                phase="dispatch_started",
                dispatch_count=1,
                player=player,
                baseline=before,
            )
            try:
                atomic_write_json(record_path, base_record)
            except OSError as exc:
                preparation_write_failed = True
                return operation_error(
                    action,
                    operation_id,
                    request_digest,
                    "journal_write_failed",
                    f"could not persist dispatch_started before dispatch: {exc}",
                    phase="journal_write_failed",
                    dispatch_count=0,
                    expires_at=expires_at,
                )
            prepared = True
            return None

        result = execute_once(
            action,
            player_selector,
            dry_run,
            verify_timeout,
            volume,
            playlist_id,
            before_dispatch=persist_dispatch_started,
            effect_check=strict_track_id_changed,
        )
        if preparation_write_failed:
            return result

        if prepared and result.get("verdict") != "verified":
            result["recover"] = "replan"

        dispatch_count = 1 if prepared else 0
        retryable = (
            not prepared
            and result.get("verdict") != "verified"
            and result.get("recover") == "retry"
        )
        transaction = operation_transaction(
            operation_id,
            request_digest,
            phase=(
                "verified"
                if result.get("verdict") == "verified"
                else "retryable" if retryable else "terminal"
            ),
            dispatch_count=dispatch_count,
            idempotent_replay=False,
            recovered_after_interruption=False,
            expires_at=expires_at,
        )
        result = with_operation_transaction(result, transaction)
        terminal = (
            operation_record(
                operation_id,
                request_digest,
                request,
                created_at=created_at,
                expires_at=expires_at,
                phase="retryable",
                dispatch_count=0,
                payload=result,
            )
            if retryable
            else terminal_record_from(base_record, result, dispatch_count)
        )
        try:
            atomic_write_json(record_path, terminal)
        except OSError as exc:
            failed = operation_error(
                action,
                operation_id,
                request_digest,
                "journal_write_failed",
                f"could not persist terminal receipt: {exc}",
                phase="dispatch_started" if prepared else "journal_write_failed",
                dispatch_count=dispatch_count,
                expires_at=expires_at,
                status="indeterminate" if prepared else "error",
            )
            failed["execution_result"] = result
            return failed
        return result
    except OSError as exc:
        return operation_error(
            action,
            operation_id,
            request_digest,
            "operation_journal_unavailable",
            str(exc),
            phase="journal_error",
        )
    finally:
        if locked:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
        if lock_fd >= 0:
            os.close(lock_fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=("media",), default="media")
    parser.add_argument("--action", choices=ACTIONS, required=True)
    parser.add_argument("--player")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-timeout", type=float, default=2.0)
    parser.add_argument("--volume", type=float)
    parser.add_argument("--playlist-id")
    parser.add_argument("--operation-id")
    parser.add_argument("--operation-ttl-secs", type=int, default=DEFAULT_OPERATION_TTL_SECS)
    parser.add_argument("--operation-preflight", action="store_true")
    args = parser.parse_args()
    payload = execute(
        args.action,
        args.player,
        args.dry_run,
        min(max(args.verify_timeout, 0.1), 10.0),
        args.volume,
        args.playlist_id,
        args.operation_id,
        args.operation_ttl_secs,
        args.operation_preflight,
    )
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return 0 if payload.get("verdict") == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
