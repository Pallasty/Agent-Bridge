import fcntl
import hashlib
import importlib.util
import json
import os
import pathlib
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/app_control.py"


def load_module():
    spec = importlib.util.spec_from_file_location("app_control_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_media_run(tracks, calls, *, player="rhythmbox", discovery=True):
    state = {"metadata_reads": 0}

    def fake_run(argv, env, timeout=2.0):
        calls.append(argv)
        if argv == ["playerctl", "-l"] and discovery:
            return 0, player, ""
        if argv == ["playerctl", "-p", player, "status"]:
            return 0, "Playing", ""
        if argv == ["playerctl", "-p", player, "volume"]:
            return 0, "0.50", ""
        if argv == ["playerctl", "-p", player, "position"]:
            return 0, "12.5", ""
        if argv[-2:] == ["--format", "{{mpris:length}}"]:
            return 0, "187000000", ""
        if argv[-2:] == ["--format", "{{mpris:trackid}}\t{{xesam:artist}}\t{{xesam:title}}"]:
            index = min(state["metadata_reads"], len(tracks) - 1)
            track = tracks[index]
            state["metadata_reads"] += 1
            if isinstance(track, tuple):
                track_id, artist, title = track
            else:
                track_id, artist, title = track, "Artist", "Title"
            return 0, f"{track_id or ''}\t{artist or ''}\t{title or ''}", ""
        if argv == ["playerctl", "-p", player, "next"]:
            return 0, "", ""
        raise AssertionError(argv)

    return fake_run


class VirtualClock:
    def __init__(self, start=1000.0):
        self.now = float(start)

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class AppControlTests(unittest.TestCase):
    def assert_preflight_receipt(
        self,
        mod,
        payload,
        *,
        state,
        candidate,
        outcome=None,
        error_code=None,
    ):
        self.assertEqual(payload["schema"], mod.SCHEMA)
        self.assertTrue(payload["read_only"])
        self.assertTrue(payload["preflight_only"])
        preflight = payload["preflight"]
        self.assertEqual(preflight["schema"], mod.OPERATION_PREFLIGHT_SCHEMA)
        self.assertEqual(preflight["state"], state)
        self.assertIs(preflight["candidate"], candidate)
        self.assertIs(preflight["blocked"], not candidate)
        self.assertEqual(
            preflight["outcome"],
            outcome or ("eligible" if candidate else "blocked"),
        )
        self.assertGreater(preflight["observed_at_unix_seconds"], 0)
        self.assertTrue(preflight["advisory"])
        self.assertTrue(preflight["must_revalidate"])
        for key in (
            "dispatch_authorized",
            "reservation_created",
            "operation_record_mutated",
            "player_observed",
            "effect_verified",
            "automatic_new_id_allowed",
        ):
            self.assertIs(preflight[key], False, key)
        self.assertTrue(payload["claim_boundary"])
        self.assertTrue(
            all(value is False for value in payload["claim_boundary"].values())
        )
        if candidate:
            self.assertEqual(payload["verdict"], "verified")
            self.assertEqual(payload["recover"], "proceed")
            self.assertIsNone(payload["error"])
        else:
            self.assertEqual(payload["verdict"], "error")
            self.assertIn(payload["recover"], ("retry", "replan"))
            self.assertEqual(payload["error"]["code"], error_code or state)

    @staticmethod
    def create_operation_lock(mod, operation_id):
        path = mod.operation_lock_path(operation_id)
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        return path

    def write_operation_fixture(
        self,
        mod,
        operation_id,
        *,
        phase,
        dispatch_count,
        player_selector="rhythmbox",
        ttl=3600,
        created_at=None,
        player=None,
        baseline=None,
        payload=None,
        workspace_sha256=None,
    ):
        mod.ensure_operation_directory(mod.operation_directory())
        self.create_operation_lock(mod, operation_id)
        created_at = time.time() - 1 if created_at is None else created_at
        request = mod.operation_request("next", player_selector, ttl)
        digest = mod.operation_request_digest("next", player_selector, ttl)
        record = mod.operation_record(
            operation_id,
            digest,
            request,
            created_at=created_at,
            expires_at=created_at + ttl,
            phase=phase,
            dispatch_count=dispatch_count,
            player=player,
            baseline=baseline,
            payload=payload,
            workspace_sha256=workspace_sha256,
        )
        record_path = mod.operation_record_path(operation_id)
        mod.atomic_write_json(record_path, record)
        return record_path, record

    def test_session_bus_hydration_replaces_stale_unix_socket(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            runtime = pathlib.Path(tmp)
            bus = socket.socket(socket.AF_UNIX)
            try:
                bus.bind(str(runtime / "bus"))
                env = {
                    "XDG_RUNTIME_DIR": str(runtime),
                    "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/999999/stale-bus",
                }
                with mock.patch.object(mod.sys, "platform", "linux"):
                    restored = mod.hydrate_session_bus(env, runtime_dir=runtime)
            finally:
                bus.close()
        expected = f"unix:path={runtime / 'bus'}"
        self.assertEqual(env["DBUS_SESSION_BUS_ADDRESS"], expected)
        self.assertEqual(restored["DBUS_SESSION_BUS_ADDRESS"], expected)

    def test_session_bus_hydration_preserves_unverifiable_transport(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            runtime = pathlib.Path(tmp)
            bus = socket.socket(socket.AF_UNIX)
            try:
                bus.bind(str(runtime / "bus"))
                env = {
                    "XDG_RUNTIME_DIR": str(runtime),
                    "DBUS_SESSION_BUS_ADDRESS": "tcp:host=127.0.0.1,port=1234",
                }
                with mock.patch.object(mod.sys, "platform", "linux"):
                    restored = mod.hydrate_session_bus(env, runtime_dir=runtime)
            finally:
                bus.close()
        self.assertEqual(env["DBUS_SESSION_BUS_ADDRESS"], "tcp:host=127.0.0.1,port=1234")
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", restored)

    def test_player_selection_is_exact_then_unique_substring(self):
        mod = load_module()
        players = ["rhythmbox", "spotify.instance42"]
        self.assertEqual(mod.select_player(players, "RHYTHMBOX"), ("rhythmbox", None))
        self.assertEqual(mod.select_player(players, "spotify"), ("spotify.instance42", None))
        self.assertEqual(mod.select_player(players, "missing"), (None, "player_not_found"))
        self.assertEqual(mod.select_player(players, None), (None, "ambiguous_player"))

    def test_unspecified_multiplayer_selects_only_unique_playing_player(self):
        mod = load_module()
        statuses = {"chromium.instance": "Paused", "rhythmbox": "Playing"}
        def fake_run(argv, env, timeout=2.0):
            return 0, statuses[argv[2]], ""
        old_run = mod.run
        try:
            mod.run = fake_run
            player, error, selection = mod.select_player_for_action(
                list(statuses), None, {}
            )
        finally:
            mod.run = old_run
        self.assertEqual((player, error), ("rhythmbox", None))
        self.assertEqual(selection["policy"], "unique_playing_player")
        self.assertEqual(selection["playing_players"], ["rhythmbox"])

    def test_unspecified_multiplayer_fails_closed_without_unique_playing_player(self):
        mod = load_module()
        for statuses in (
            {"one": "Paused", "two": "Stopped"},
            {"one": "Playing", "two": "Playing"},
        ):
            with self.subTest(statuses=statuses):
                old_run = mod.run
                try:
                    mod.run = lambda argv, env, timeout=2.0: (0, statuses[argv[2]], "")
                    player, error, _ = mod.select_player_for_action(list(statuses), None, {})
                finally:
                    mod.run = old_run
                self.assertIsNone(player)
                self.assertEqual(error, "ambiguous_player")

    def test_unspecified_multiplayer_fails_closed_on_incomplete_status_observation(self):
        mod = load_module()
        def fake_run(argv, env, timeout=2.0):
            if argv[2] == "one":
                return 0, "Playing", ""
            return 1, "", "D-Bus unavailable"
        old_run = mod.run
        try:
            mod.run = fake_run
            player, error, selection = mod.select_player_for_action(["one", "two"], None, {})
        finally:
            mod.run = old_run
        self.assertIsNone(player)
        self.assertEqual(error, "player_selection_incomplete")
        self.assertEqual(selection["observations"][1]["status"], "observation_failed")

    def test_track_actions_require_identity_change(self):
        mod = load_module()
        before = {"track_id": "one", "artist": "a", "title": "t", "playback_status": "Playing"}
        same = dict(before)
        changed = dict(before, track_id="two")
        self.assertFalse(mod.effect_verified("next", before, same)[0])
        self.assertTrue(mod.effect_verified("next", before, changed)[0])

    def test_settled_track_observer_resets_every_invalid_or_changed_candidate(self):
        mod = load_module()
        clock = VirtualClock()
        def track(track_id):
            return {"track_id": track_id, "title": str(track_id)}, None

        observations = [
            track("B"),
            track("B"),
            track(None),
            track("B"),
            track("B"),
            (None, {"code": "observation_failed"}),
            track("B"),
            track("B"),
            track("A"),
            track("B"),
            track("B"),
            track("C"),
            track("C"),
            track("C"),
        ]
        with mock.patch.object(mod, "observe", side_effect=observations):
            outcome = mod.observe_settled_track_change(
                "rhythmbox",
                {"track_id": "A"},
                {},
                4.0,
                monotonic_fn=clock.monotonic,
                sleep_fn=clock.sleep,
            )

        self.assertTrue(outcome["verified"])
        self.assertEqual(outcome["after"]["track_id"], "C")
        self.assertEqual(outcome["polls"], 14)
        self.assertEqual(
            outcome["settlement"],
            {
                "schema": mod.TRACK_SETTLEMENT_SCHEMA,
                "candidate_track_id": "C",
                "required_consecutive_observations": 3,
                "observed_consecutive_observations": 3,
                "required_stable_ms": 500,
                "observed_stable_ms": 500,
                "settled": True,
            },
        )

    def test_status_actions_verify_the_requested_state(self):
        mod = load_module()
        before = {"playback_status": "Playing"}
        self.assertTrue(mod.effect_verified("pause", before, {"playback_status": "Paused"})[0])
        self.assertFalse(mod.effect_verified("pause", before, {"playback_status": "Playing"})[0])

    def test_state_get_returns_protocol_observation(self):
        mod = load_module()
        old_run, old_which = mod.run, mod.shutil.which
        def fake_run(argv, env, timeout=2.0):
            if argv == ["playerctl", "-l"]: return 0, "rhythmbox", ""
            if argv[-1] == "status": return 0, "Playing", ""
            if argv[-1] == "position": return 0, "12.5", ""
            if any("mpris:length" in item for item in argv): return 0, "187000000", ""
            if "metadata" in argv: return 0, "/track/1\tArtist\tTitle", ""
            if argv[-1] == "volume": return 0, "0.50", ""
            raise AssertionError(argv)
        try:
            mod.run = fake_run; mod.shutil.which = lambda _: "/usr/bin/playerctl"
            payload = mod.execute("state_get", "rhythmbox", False, 0.2)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(payload["verdict"], "verified")
        self.assertEqual(payload["verification"]["predicate"], "player_state_observed")
        self.assertEqual(payload["before"]["title"], "Title")

    def test_position_get_returns_seconds_and_duration(self):
        mod = load_module()
        old_run, old_which = mod.run, mod.shutil.which
        def fake_run(argv, env, timeout=2.0):
            if argv == ["playerctl", "-l"]: return 0, "rhythmbox", ""
            if argv[-1] == "status": return 0, "Playing", ""
            if argv[-1] == "position": return 0, "12.5", ""
            if any("mpris:length" in item for item in argv): return 0, "187000000", ""
            if "metadata" in argv: return 0, "/track/1\tArtist\tTitle", ""
            if argv[-1] == "volume": return 0, "0.50", ""
            raise AssertionError(argv)
        try:
            mod.run = fake_run; mod.shutil.which = lambda _: "/usr/bin/playerctl"
            payload = mod.execute("position_get", "rhythmbox", False, 0.2)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(payload["verdict"], "verified")
        self.assertEqual(payload["verification"]["predicate"], "media_position_observed")
        self.assertAlmostEqual(payload["before"]["position_seconds"], 12.5)
        self.assertAlmostEqual(payload["before"]["duration_seconds"], 187.0)

    def test_playlist_list_and_activate_use_unique_object_path(self):
        mod = load_module()
        old_run, old_which = mod.run, mod.shutil.which
        calls = []
        playlist = "/org/gnome/Rhythmbox3/Playlist/0x1"
        def fake_run(argv, env, timeout=2.0):
            calls.append(argv)
            if argv == ["playerctl", "-l"]: return 0, "rhythmbox", ""
            if argv[0] == "gdbus" and "org.mpris.MediaPlayer2.Playlists.GetPlaylists" in argv:
                return 0, "([(objectpath '/org/gnome/Rhythmbox3/Playlist/0x1', 'Allin1.m3u', ''), (objectpath '/org/gnome/Rhythmbox3/Playlist/0x2', 'Allin1.m3u', '')],)", ""
            if argv[0] == "gdbus" and "org.mpris.MediaPlayer2.Playlists.ActivatePlaylist" in argv: return 0, "()", ""
            if argv[0] == "gdbus" and "org.freedesktop.DBus.Properties.Get" in argv:
                return 0, "(<(true, (objectpath '/org/gnome/Rhythmbox3/Playlist/0x1', 'Allin1.m3u', ''))>,)", ""
            if argv[-1] == "status": return 0, "Playing", ""
            if argv[-1] == "position": return 0, "1.0", ""
            if any("mpris:length" in item for item in argv): return 0, "100000000", ""
            if "metadata" in argv: return 0, "/track/1\tArtist\tTitle", ""
            if argv[-1] == "volume": return 0, "0.50", ""
            raise AssertionError(argv)
        try:
            mod.run = fake_run; mod.shutil.which = lambda _: "/usr/bin/playerctl"
            listed = mod.execute("playlist_list", "rhythmbox", False, 0.2)
            activated = mod.execute("playlist_activate", "rhythmbox", False, 0.2, playlist_id=playlist)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(len(listed["playlists"]), 2)
        self.assertEqual(activated["verdict"], "verified")
        self.assertEqual(activated["active_playlist"]["id"], playlist)
        self.assertEqual(activated["verification"]["predicate"], "playlist_active_id_matches_target")
        self.assertEqual(
            activated["dispatch"]["argv"],
            mod.playlist_argv(
                "rhythmbox",
                "org.mpris.MediaPlayer2.Playlists.ActivatePlaylist",
                [playlist],
            ),
        )

    def test_playlist_activate_verifies_target_even_when_stopped_without_track(self):
        mod = load_module()
        old_run, old_which = mod.run, mod.shutil.which
        playlist = "/org/gnome/Rhythmbox3/Playlist/0x1"
        def fake_run(argv, env, timeout=2.0):
            if argv == ["playerctl", "-l"]: return 0, "rhythmbox", ""
            if argv[0] == "gdbus" and "org.mpris.MediaPlayer2.Playlists.GetPlaylists" in argv:
                return 0, "([(objectpath '/org/gnome/Rhythmbox3/Playlist/0x1', 'Recently Added', '')],)", ""
            if argv[0] == "gdbus" and "org.mpris.MediaPlayer2.Playlists.ActivatePlaylist" in argv: return 0, "()", ""
            if argv[0] == "gdbus" and "org.freedesktop.DBus.Properties.Get" in argv:
                return 0, "(<(true, (objectpath '/org/gnome/Rhythmbox3/Playlist/0x1', 'Recently Added', ''))>,)", ""
            if argv[-1] == "status": return 0, "Stopped", ""
            if argv[-1] == "position": return 1, "", "No player could handle this command"
            if any("mpris:length" in item for item in argv): return 1, "", "No player could handle this command"
            if "metadata" in argv: return 1, "", "No player could handle this command"
            if argv[-1] == "volume": return 0, "0.50", ""
            raise AssertionError(argv)
        try:
            mod.run = fake_run; mod.shutil.which = lambda _: "/usr/bin/playerctl"
            activated = mod.execute("playlist_activate", "rhythmbox", False, 0.2, playlist_id=playlist)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(activated["verdict"], "verified")
        self.assertEqual(activated["after"]["playback_status"], "Stopped")
        self.assertFalse(activated["after"]["metadata_available"])

    def test_playlist_activate_repauses_unexpected_resume(self):
        mod = load_module()
        old_run, old_which = mod.run, mod.shutil.which
        playlist = "/org/gnome/Rhythmbox3/Playlist/0x1"
        state = {"activated": False, "paused": False, "pause_calls": 0}
        def fake_run(argv, env, timeout=2.0):
            if argv == ["playerctl", "-l"]: return 0, "rhythmbox", ""
            if argv[0] == "gdbus" and "org.mpris.MediaPlayer2.Playlists.GetPlaylists" in argv:
                return 0, "([(objectpath '/org/gnome/Rhythmbox3/Playlist/0x1', 'Recently Added', '')],)", ""
            if argv[0] == "gdbus" and "org.mpris.MediaPlayer2.Playlists.ActivatePlaylist" in argv:
                state["activated"] = True; return 0, "()", ""
            if argv[0] == "gdbus" and "org.freedesktop.DBus.Properties.Get" in argv:
                return 0, "(<(true, (objectpath '/org/gnome/Rhythmbox3/Playlist/0x1', 'Recently Added', ''))>,)", ""
            if argv == ["playerctl", "-p", "rhythmbox", "pause"]:
                state["paused"] = True; state["pause_calls"] += 1; return 0, "", ""
            if argv[-1] == "status":
                return 0, "Paused" if not state["activated"] or state["paused"] else "Playing", ""
            if argv[-1] == "position": return 1, "", "No player could handle this command"
            if any("mpris:length" in item for item in argv): return 1, "", "No player could handle this command"
            if "metadata" in argv: return 1, "", "No player could handle this command"
            if argv[-1] == "volume": return 0, "0.50", ""
            raise AssertionError(argv)
        try:
            mod.run = fake_run; mod.shutil.which = lambda _: "/usr/bin/playerctl"
            activated = mod.execute("playlist_activate", "rhythmbox", False, 0.2, playlist_id=playlist)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(activated["verdict"], "verified")
        self.assertEqual(state["pause_calls"], 1)
        self.assertEqual(activated["after"]["playback_status"], "Paused")
        self.assertTrue(activated["playback_preservation"]["required"])
        self.assertEqual(activated["playback_preservation"]["status"], "verified")

    def test_playlist_activate_dry_run_never_calls_activate(self):
        mod = load_module()
        playlist = "/org/gnome/Rhythmbox3/Playlist/0x1"
        calls = []

        def fake_run(argv, env, timeout=2.0):
            calls.append(argv)
            if argv == ["playerctl", "-l"]:
                return 0, "rhythmbox", ""
            if argv[0] == "gdbus" and "org.mpris.MediaPlayer2.Playlists.GetPlaylists" in argv:
                return 0, "([(objectpath '/org/gnome/Rhythmbox3/Playlist/0x1', 'Recently Added', '')],)", ""
            raise AssertionError(f"dry run attempted unexpected call: {argv}")

        with mock.patch.object(mod, "run", side_effect=fake_run), \
             mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"):
            payload = mod.execute(
                "playlist_activate", "rhythmbox", True, 0.2, playlist_id=playlist
            )

        self.assertEqual(payload["verdict"], "verified")
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["dispatch"]["status"], "not_dispatched_dry_run")
        self.assertEqual(
            payload["dispatch"]["argv"],
            mod.playlist_argv(
                "rhythmbox",
                "org.mpris.MediaPlayer2.Playlists.ActivatePlaylist",
                [playlist],
            ),
        )
        self.assertFalse(
            any("org.mpris.MediaPlayer2.Playlists.ActivatePlaylist" in call for call in calls)
        )

    def test_playlist_current_returns_active_playlist_and_track_summary(self):
        mod = load_module()
        old_run, old_which = mod.run, mod.shutil.which
        def fake_run(argv, env, timeout=2.0):
            if argv == ["playerctl", "-l"]: return 0, "rhythmbox", ""
            if argv[0] == "gdbus" and "org.mpris.MediaPlayer2.Playlists.GetPlaylists" in argv:
                return 0, "([(objectpath '/org/gnome/Rhythmbox3/Playlist/0x1', 'Allin1.m3u', '')],)", ""
            if argv[0] == "gdbus" and "org.freedesktop.DBus.Properties.Get" in argv:
                return 0, "(<(true, (objectpath '/org/gnome/Rhythmbox3/Playlist/0x1', 'Allin1.m3u', ''))>,)", ""
            if argv[-1] == "status": return 0, "Playing", ""
            if argv[-1] == "position": return 0, "1.0", ""
            if any("mpris:length" in item for item in argv): return 0, "100000000", ""
            if "metadata" in argv: return 0, "/track/1\tArtist\tTitle", ""
            if argv[-1] == "volume": return 0, "0.50", ""
            raise AssertionError(argv)
        try:
            mod.run = fake_run; mod.shutil.which = lambda _: "/usr/bin/playerctl"
            payload = mod.execute("playlist_current", "rhythmbox", False, 0.2)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(payload["verdict"], "verified")
        self.assertEqual(payload["active_playlist"]["id"], "/org/gnome/Rhythmbox3/Playlist/0x1")
        self.assertEqual(payload["active_playlist"]["name"], "Allin1.m3u")
        self.assertEqual(payload["track_summary"]["title"], "Title")
        self.assertEqual(payload["verification"]["predicate"], "active_playlist_observed")

    def test_playlist_current_preserves_inactive_and_empty_metadata_state(self):
        mod = load_module()
        old_run, old_which = mod.run, mod.shutil.which
        def fake_run(argv, env, timeout=2.0):
            if argv == ["playerctl", "-l"]: return 0, "rhythmbox", ""
            if argv[0] == "gdbus":
                return 0, "(<(false, (objectpath '/', '', ''))>,)", ""
            if argv[-1] == "status": return 0, "Stopped", ""
            if argv[-1] == "position": return 1, "", "no position"
            if any("mpris:length" in item for item in argv): return 1, "", "no length"
            if "metadata" in argv: return 1, "", "no metadata"
            if argv[-1] == "volume": return 0, "0.50", ""
            raise AssertionError(argv)
        try:
            mod.run = fake_run; mod.shutil.which = lambda _: "/usr/bin/playerctl"
            payload = mod.execute("playlist_current", "rhythmbox", False, 0.2)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(payload["verdict"], "verified")
        self.assertFalse(payload["active_playlist"]["active"])
        self.assertIsNone(payload["active_playlist"]["id"])
        self.assertFalse(payload["track_summary"]["metadata_available"])
        self.assertIsNone(payload["track_summary"]["track_id"])

    def test_playlist_current_fails_closed_when_active_playlist_read_fails(self):
        mod = load_module()
        old_run, old_which = mod.run, mod.shutil.which
        def fake_run(argv, env, timeout=2.0):
            if argv == ["playerctl", "-l"]: return 0, "rhythmbox", ""
            if argv[0] == "gdbus": return 1, "", "org.freedesktop.DBus.Error.Failed"
            raise AssertionError(argv)
        try:
            mod.run = fake_run; mod.shutil.which = lambda _: "/usr/bin/playerctl"
            payload = mod.execute("playlist_current", "rhythmbox", False, 0.2)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(payload["status"], "observation_failed")
        self.assertEqual(payload["error"]["code"], "active_playlist_observation_failed")

    def test_playlist_current_uses_unique_playing_player(self):
        mod = load_module()
        old_run, old_which = mod.run, mod.shutil.which
        def fake_run(argv, env, timeout=2.0):
            if argv == ["playerctl", "-l"]: return 0, "chromium.instance\nrhythmbox", ""
            if argv == ["playerctl", "-p", "chromium.instance", "status"]: return 0, "Paused", ""
            if argv == ["playerctl", "-p", "rhythmbox", "status"]: return 0, "Playing", ""
            if argv[:4] == ["playerctl", "-p", "rhythmbox", "metadata"]: return 0, "/track\tArtist\tTitle", ""
            if argv == ["playerctl", "-p", "rhythmbox", "volume"]: return 0, "1.0", ""
            if argv == ["playerctl", "-p", "rhythmbox", "position"]: return 0, "2.0", ""
            if argv[:4] == ["playerctl", "-p", "rhythmbox", "metadata"]: return 0, "2000000", ""
            if argv[-2:] == ["--format", "{{mpris:length}}"]: return 0, "2000000", ""
            if argv[0] == "gdbus": return 0, "(true, (objectpath '/playlist', 'List'))", ""
            raise AssertionError(argv)
        try:
            mod.run = fake_run; mod.shutil.which = lambda _: "/usr/bin/playerctl"
            payload = mod.execute("playlist_current", None, False, 0.2)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(payload["verdict"], "verified")
        self.assertEqual(payload["player"], "rhythmbox")
        self.assertEqual(payload["selection"]["policy"], "unique_playing_player")

    def test_control_action_does_not_dispatch_when_multiple_players_are_paused(self):
        mod = load_module()
        old_run, old_which = mod.run, mod.shutil.which
        calls = []
        def fake_run(argv, env, timeout=2.0):
            calls.append(argv)
            if argv == ["playerctl", "-l"]: return 0, "chromium.instance\nrhythmbox", ""
            if argv[0] == "playerctl" and argv[-1] == "status": return 0, "Paused", ""
            if argv[0] == "playerctl" and "metadata" in argv: return 0, "/track\tArtist\tTitle", ""
            if argv[0] == "playerctl" and argv[-1] == "volume": return 0, "1.0", ""
            if argv[0] == "playerctl" and argv[-1] == "position": return 0, "2.0", ""
            if argv[0] == "gdbus": return 0, "(true, (objectpath '/', ''))", ""
            raise AssertionError(argv)
        try:
            mod.run = fake_run; mod.shutil.which = lambda _: "/usr/bin/playerctl"
            payload = mod.execute("pause", None, True, 0.2)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(payload["verdict"], "error")
        self.assertEqual(payload["error"]["code"], "ambiguous_player")
        self.assertFalse(any(call[0] == "playerctl" and call[-1] == "pause" for call in calls))

    def test_actions_fail_closed_when_no_mpris_player_exists(self):
        mod = load_module()
        old_run, old_which = mod.run, mod.shutil.which
        def fake_run(argv, env, timeout=2.0):
            if argv == ["playerctl", "-l"]: return 0, "", ""
            raise AssertionError(argv)
        try:
            mod.run = fake_run; mod.shutil.which = lambda _: "/usr/bin/playerctl"
            payload = mod.execute("playlist_current", None, False, 0.2)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(payload["status"], "target_unavailable")
        self.assertEqual(payload["verdict"], "error")
        self.assertEqual(payload["error"]["code"], "no_mpris_player")
        self.assertEqual(payload["route"]["selected"], None)
        self.assertFalse(any(item["status"] == "executed" for item in payload["route"]["fallbacks"]))

    def test_dry_run_discovers_and_never_dispatches(self):
        mod = load_module()
        calls = []

        def fake_run(argv, env, timeout=2.0):
            calls.append(argv)
            if argv == ["playerctl", "-l"]:
                return 0, "rhythmbox", ""
            if argv[-1] == "status":
                return 0, "Playing", ""
            if argv[-1] == "position":
                return 0, "12.5", ""
            if "mpris:length" in argv:
                return 0, "187000000", ""
            if "metadata" in argv:
                return 0, "/track/1\tArtist\tTitle", ""
            if argv[-1] == "volume":
                return 0, "0.50", ""
            raise AssertionError(f"unexpected mutation: {argv}")

        old_run, old_which = mod.run, mod.shutil.which
        try:
            mod.run = fake_run
            mod.shutil.which = lambda _: "/usr/bin/playerctl"
            payload = mod.execute("next", "rhythmbox", True, 0.2)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(payload["status"], "planned")
        self.assertEqual(payload["dispatch"]["status"], "not_dispatched_dry_run")
        self.assertNotIn(["playerctl", "-p", "rhythmbox", "next"], calls)

    def test_real_action_dispatches_allowlisted_argv_and_reobserves(self):
        mod = load_module()
        metadata_reads = 0
        calls = []

        def fake_run(argv, env, timeout=2.0):
            nonlocal metadata_reads
            calls.append(argv)
            if argv == ["playerctl", "-l"]:
                return 0, "rhythmbox", ""
            if argv[-1] == "status":
                return 0, "Playing", ""
            if argv[-1] == "position":
                return 0, "12.5", ""
            if "mpris:length" in argv:
                return 0, "187000000", ""
            if "metadata" in argv:
                metadata_reads += 1
                track = "1" if metadata_reads == 1 else "2"
                return 0, f"/track/{track}\tArtist\tTitle {track}", ""
            if argv[-1] == "volume":
                return 0, "0.50", ""
            if argv == ["playerctl", "-p", "rhythmbox", "next"]:
                return 0, "", ""
            raise AssertionError(argv)

        old_run, old_which = mod.run, mod.shutil.which
        try:
            mod.run = fake_run
            mod.shutil.which = lambda _: "/usr/bin/playerctl"
            payload = mod.execute("next", "rhythmbox", False, 0.2)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(payload["verdict"], "verified")
        self.assertEqual(calls.count(["playerctl", "-p", "rhythmbox", "next"]), 1)
        self.assertEqual(payload["route"]["selected"]["layer"], "application_protocol")
        self.assertFalse(payload["route"]["silent_fallback_allowed"])

    def test_volume_set_is_range_checked_and_verified(self):
        mod = load_module()
        calls = []
        volume_reads = 0

        def fake_run(argv, env, timeout=2.0):
            nonlocal volume_reads
            calls.append(argv)
            if argv == ["playerctl", "-l"]:
                return 0, "rhythmbox", ""
            if argv[-1] == "status":
                return 0, "Playing", ""
            if argv[-1] == "position":
                return 0, "12.5", ""
            if "mpris:length" in argv:
                return 0, "187000000", ""
            if "metadata" in argv:
                return 0, "/track/1\tArtist\tTitle", ""
            if argv[-1] == "volume":
                volume_reads += 1
                return 0, "0.50" if volume_reads == 1 else "0.70", ""
            if argv[:4] == ["playerctl", "-p", "rhythmbox", "volume"]:
                return 0, "", ""
            raise AssertionError(argv)

        old_run, old_which = mod.run, mod.shutil.which
        try:
            mod.run = fake_run
            mod.shutil.which = lambda _: "/usr/bin/playerctl"
            payload = mod.execute("volume_set", "rhythmbox", False, 0.2, 0.7)
        finally:
            mod.run, mod.shutil.which = old_run, old_which
        self.assertEqual(payload["verdict"], "verified")
        self.assertIn(["playerctl", "-p", "rhythmbox", "volume", "0.700"], calls)
        self.assertEqual(payload["verification"]["predicate"], "volume_is_requested")

    def test_volume_set_rejects_out_of_range(self):
        mod = load_module()
        old_which = mod.shutil.which
        try:
            mod.shutil.which = lambda _: "/usr/bin/playerctl"
            payload = mod.execute("volume_set", "rhythmbox", False, 0.2, 1.1)
        finally:
            mod.shutil.which = old_which
        self.assertEqual(payload["error"]["code"], "invalid_volume")

    def test_volume_set_invalid_range_precedes_backend_probe(self):
        mod = load_module()
        original = mod.list_players
        mod.list_players = lambda env: ([], {"code": "no_mpris_player"})
        try:
            payload = mod.execute("volume_set", "rhythmbox", False, 0.2, 1.1)
        finally:
            mod.list_players = original
        self.assertEqual(payload["error"]["code"], "invalid_volume")
        self.assertEqual(payload["recover"], "replan")

    def test_operation_preflight_absent_is_candidate_without_mkdir_or_player(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            journal_dir = pathlib.Path(tmp) / "missing" / "operations"
            with mock.patch.dict(
                os.environ, {"AB_APP_CONTROL_OPERATION_DIR": str(journal_dir)}
            ), mock.patch.object(
                mod, "run", side_effect=AssertionError("must not call playerctl")
            ), mock.patch.object(
                mod,
                "ensure_operation_directory",
                side_effect=AssertionError("preflight must not mkdir"),
            ), mock.patch.object(
                mod,
                "atomic_write_json",
                side_effect=AssertionError("preflight must not write a record"),
            ):
                payload = mod.execute(
                    "next",
                    "rhythmbox",
                    False,
                    0.2,
                    operation_id="preflight-absent",
                    operation_preflight=True,
                )
            self.assertFalse(journal_dir.exists())

        self.assert_preflight_receipt(
            mod, payload, state="fresh_candidate", candidate=True
        )
        self.assertFalse(payload["preflight"]["record_present"])
        self.assertEqual(payload["preflight"]["dispatch_count"], 0)
        self.assertIsNone(payload["preflight"]["remaining_secs"])
        self.assertEqual(
            payload["preflight"]["operation_id_disposition"],
            "reusable_same_request",
        )
        self.assertTrue(payload["preflight"]["same_id_retry_allowed"])

    def test_durable_operation_workspace_context_conflict_fails_before_player_access(self):
        mod = load_module()
        operation_id = "workspace-bound"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
        ):
            self.write_operation_fixture(
                mod, operation_id, phase="retryable", dispatch_count=0,
                workspace_sha256="1" * 64,
            )
            with mock.patch.object(mod, "run", side_effect=AssertionError("must not call playerctl")):
                payload = mod.execute(
                    "next", "rhythmbox", False, 0.2, operation_id=operation_id,
                    workspace_sha256="2" * 64,
                )
        self.assertEqual(payload["error"]["code"], "operation_context_conflict")
        self.assertEqual(payload["recover"], "replan")

    def test_operation_preflight_cli_flag_is_backend_only_and_non_creating(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal_dir = pathlib.Path(tmp) / "not-created"
            env = dict(os.environ)
            env["AB_APP_CONTROL_OPERATION_DIR"] = str(journal_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--action",
                    "next",
                    "--player",
                    "rhythmbox",
                    "--operation-id",
                    "preflight-cli",
                    "--operation-preflight",
                    "--wrapper-contract-version",
                    "agent_bridge.app_control.wrapper_contract.v1",
                ],
                capture_output=True,
                text=True,
                env=env,
                check=False,
                timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(journal_dir.exists())
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["preflight"]["schema"],
            "agent_bridge.app_control.operation_preflight.v0",
        )
        self.assertTrue(payload["preflight"]["candidate"])
        self.assertFalse(payload["preflight"]["blocked"])

    def test_mutating_cli_requires_exact_wrapper_contract_before_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            playerctl = bin_dir / "playerctl"
            marker = root / "playerctl-called"
            playerctl.write_text(
                "#!/bin/sh\ntouch \"$APP_CONTROL_TEST_MARKER\"\nexit 99\n",
                encoding="utf-8",
            )
            playerctl.chmod(0o755)
            for supplied in (None, "agent_bridge.app_control.wrapper_contract.v0"):
                journal_dir = root / ("journal-missing" if supplied is None else "journal-wrong")
                env = dict(os.environ)
                env.update({
                    "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
                    "APP_CONTROL_TEST_MARKER": str(marker),
                    "AB_APP_CONTROL_OPERATION_DIR": str(journal_dir),
                })
                argv = [
                    sys.executable,
                    str(SCRIPT),
                    "--action", "next",
                    "--player", "rhythmbox",
                    "--operation-id", "contract-gated",
                ]
                if supplied is not None:
                    argv.extend(["--wrapper-contract-version", supplied])
                result = subprocess.run(
                    argv, capture_output=True, text=True, env=env, check=False, timeout=5
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["error"]["code"], "wrapper_contract_mismatch")
                self.assertTrue(payload["read_only"])
                self.assertFalse(marker.exists())
                self.assertFalse(journal_dir.exists())

    def test_read_only_cli_remains_compatible_without_wrapper_contract(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--action", "discover", "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        payload = json.loads(result.stdout)
        self.assertNotEqual(payload.get("error", {}).get("code"), "wrapper_contract_mismatch")

    def test_operation_preflight_retryable_uses_read_only_snapshot(self):
        mod = load_module()
        operation_id = "preflight-retryable"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
        ):
            record_path, _ = self.write_operation_fixture(
                mod,
                operation_id,
                phase="retryable",
                dispatch_count=0,
            )
            lock_path = mod.operation_lock_path(operation_id)
            before_record = record_path.read_bytes()
            before_lock = lock_path.read_bytes()
            real_open = os.open
            opened_flags = []

            def read_only_open(path, flags, mode=0o777, *, dir_fd=None):
                opened_flags.append(flags)
                write_flags = (
                    os.O_WRONLY
                    | os.O_RDWR
                    | os.O_CREAT
                    | os.O_TRUNC
                    | os.O_APPEND
                )
                self.assertEqual(flags & write_flags, 0)
                if dir_fd is None:
                    return real_open(path, flags, mode)
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(
                mod, "run", side_effect=AssertionError("must not call playerctl")
            ), mock.patch.object(
                mod,
                "atomic_write_json",
                side_effect=AssertionError("preflight must not write a record"),
            ), mock.patch.object(mod.os, "open", side_effect=read_only_open):
                payload = mod.execute(
                    "next",
                    "rhythmbox",
                    False,
                    0.2,
                    operation_id=operation_id,
                    operation_preflight=True,
                )
            self.assertGreaterEqual(len(opened_flags), 2)
            self.assertEqual(record_path.read_bytes(), before_record)
            self.assertEqual(lock_path.read_bytes(), before_lock)

        self.assert_preflight_receipt(
            mod, payload, state="retryable_candidate", candidate=True
        )
        self.assertTrue(payload["preflight"]["record_present"])
        self.assertEqual(payload["preflight"]["observed_phase"], "retryable")
        self.assertEqual(payload["preflight"]["dispatch_count"], 0)
        self.assertGreater(payload["preflight"]["remaining_secs"], 0)
        self.assertEqual(len(payload["preflight"]["record_sha256"]), 64)

    def test_operation_preflight_verified_terminal_is_replay_candidate(self):
        mod = load_module()
        operation_id = "preflight-terminal"
        calls = []
        media_run = make_media_run(["/track/1", "/track/2"], calls)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
        ):
            with mock.patch.object(mod, "run", side_effect=media_run), mock.patch.object(
                mod.shutil, "which", return_value="/usr/bin/playerctl"
            ):
                first = mod.execute(
                    "next", "rhythmbox", False, 0.8, operation_id=operation_id
                )
            self.assertEqual(first["verdict"], "verified")
            record_path = mod.operation_record_path(operation_id)
            before = record_path.read_bytes()
            calls.clear()
            with mock.patch.object(
                mod, "run", side_effect=AssertionError("must not call playerctl")
            ), mock.patch.object(
                mod,
                "atomic_write_json",
                side_effect=AssertionError("preflight must not write a record"),
            ):
                payload = mod.execute(
                    "next",
                    "rhythmbox",
                    False,
                    0.2,
                    operation_id=operation_id,
                    operation_preflight=True,
                )
                replay = mod.execute(
                    "next", "rhythmbox", False, 0.2, operation_id=operation_id
                )
            self.assertEqual(record_path.read_bytes(), before)

        self.assert_preflight_receipt(
            mod, payload, state="terminal_replay_candidate", candidate=True
        )
        self.assertEqual(payload["preflight"]["observed_phase"], "terminal")
        self.assertEqual(payload["preflight"]["terminal_verdict"], "verified")
        self.assertEqual(payload["preflight"]["dispatch_count"], 1)
        self.assertGreater(payload["preflight"]["remaining_secs"], 0)
        self.assertTrue(replay["transaction"]["idempotent_replay"])
        self.assertEqual(calls, [])

    def test_operation_preflight_dispatch_started_is_recovery_candidate_without_observation(self):
        mod = load_module()
        operation_id = "preflight-recovery"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
        ):
            record_path, _ = self.write_operation_fixture(
                mod,
                operation_id,
                phase="dispatch_started",
                dispatch_count=1,
                player="rhythmbox",
                baseline={"track_id": "/track/1"},
            )
            before = record_path.read_bytes()
            with mock.patch.object(
                mod, "run", side_effect=AssertionError("must not observe player")
            ), mock.patch.object(
                mod,
                "atomic_write_json",
                side_effect=AssertionError("preflight must not terminalize recovery"),
            ):
                payload = mod.execute(
                    "next",
                    "rhythmbox",
                    False,
                    0.2,
                    operation_id=operation_id,
                    operation_preflight=True,
                )
            self.assertEqual(record_path.read_bytes(), before)

        self.assert_preflight_receipt(
            mod,
            payload,
            state="recovery_observation_candidate",
            candidate=True,
        )
        self.assertEqual(payload["preflight"]["observed_phase"], "dispatch_started")
        self.assertEqual(payload["preflight"]["dispatch_count"], 1)
        self.assertGreater(payload["preflight"]["remaining_secs"], 0)
        self.assertFalse(payload["preflight"]["player_observed"])

    def test_operation_preflight_expired_blocks_with_honest_id_disposition(self):
        mod = load_module()
        operation_id = "preflight-expired"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
        ):
            record_path, _ = self.write_operation_fixture(
                mod,
                operation_id,
                phase="dispatch_started",
                dispatch_count=1,
                created_at=time.time() - 3601,
                player="rhythmbox",
                baseline={"track_id": "/track/1"},
            )
            before = record_path.read_bytes()
            with mock.patch.object(
                mod, "run", side_effect=AssertionError("must not call playerctl")
            ), mock.patch.object(
                mod,
                "atomic_write_json",
                side_effect=AssertionError("preflight must not write a record"),
            ):
                payload = mod.execute(
                    "next",
                    "rhythmbox",
                    False,
                    0.2,
                    operation_id=operation_id,
                    operation_preflight=True,
                )
            self.assertEqual(record_path.read_bytes(), before)

        self.assert_preflight_receipt(
            mod,
            payload,
            state="operation_expired",
            candidate=False,
        )
        self.assertEqual(payload["preflight"]["remaining_secs"], 0)
        self.assertEqual(
            payload["preflight"]["operation_id_disposition"], "expired"
        )
        self.assertFalse(payload["preflight"]["same_id_retry_allowed"])
        self.assertFalse(payload["preflight"]["automatic_new_id_allowed"])
        self.assertIn(
            "without_automatic_actuation_or_id_replacement",
            payload["preflight"]["recommended_next"],
        )

    def test_operation_preflight_conflict_blocks_without_silent_new_identity(self):
        mod = load_module()
        operation_id = "preflight-conflict"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
        ):
            record_path, _ = self.write_operation_fixture(
                mod,
                operation_id,
                phase="retryable",
                dispatch_count=0,
                player_selector="spotify",
            )
            before = record_path.read_bytes()
            with mock.patch.object(
                mod, "run", side_effect=AssertionError("must not call playerctl")
            ), mock.patch.object(
                mod,
                "atomic_write_json",
                side_effect=AssertionError("preflight must not write a record"),
            ):
                payload = mod.execute(
                    "next",
                    "rhythmbox",
                    False,
                    0.2,
                    operation_id=operation_id,
                    operation_preflight=True,
                )
            self.assertEqual(record_path.read_bytes(), before)

        self.assert_preflight_receipt(
            mod,
            payload,
            state="idempotency_conflict",
            candidate=False,
        )
        self.assertEqual(
            payload["preflight"]["operation_id_disposition"],
            "conflicts_with_request",
        )
        self.assertFalse(payload["preflight"]["same_id_retry_allowed"])
        self.assertFalse(payload["preflight"]["automatic_new_id_allowed"])
        self.assertIn(
            "resolve_the_original_request_binding",
            payload["preflight"]["recommended_next"],
        )

    def test_operation_preflight_malformed_record_is_blocked_and_unchanged(self):
        mod = load_module()
        operation_id = "preflight-malformed"
        malformed = b'{"schema":"broken"'
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
        ):
            mod.ensure_operation_directory(mod.operation_directory())
            self.create_operation_lock(mod, operation_id)
            record_path = mod.operation_record_path(operation_id)
            record_path.write_bytes(malformed)
            record_path.chmod(0o600)
            with mock.patch.object(
                mod, "run", side_effect=AssertionError("must not call playerctl")
            ), mock.patch.object(
                mod,
                "atomic_write_json",
                side_effect=AssertionError("preflight must not repair a record"),
            ):
                payload = mod.execute(
                    "next",
                    "rhythmbox",
                    False,
                    0.2,
                    operation_id=operation_id,
                    operation_preflight=True,
                )
            self.assertEqual(record_path.read_bytes(), malformed)

        self.assert_preflight_receipt(
            mod,
            payload,
            state="operation_record_invalid",
            candidate=False,
        )
        self.assertEqual(
            payload["preflight"]["operation_id_disposition"],
            "invalid_or_unavailable",
        )
        self.assertFalse(payload["preflight"]["same_id_retry_allowed"])
        self.assertFalse(payload["preflight"]["automatic_new_id_allowed"])

    def test_operation_preflight_rejects_record_and_lock_symlinks(self):
        for target_kind in ("record", "lock"):
            with self.subTest(target_kind=target_kind):
                mod = load_module()
                operation_id = f"preflight-{target_kind}-symlink"
                with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
                    os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
                ):
                    mod.ensure_operation_directory(mod.operation_directory())
                    target = pathlib.Path(tmp) / f"outside-{target_kind}"
                    target.write_bytes(b"do not follow")
                    target.chmod(0o600)
                    record_path = mod.operation_record_path(operation_id)
                    lock_path = mod.operation_lock_path(operation_id)
                    if target_kind == "record":
                        self.create_operation_lock(mod, operation_id)
                        record_path.symlink_to(target)
                    else:
                        lock_path.symlink_to(target)
                    with mock.patch.object(
                        mod, "run", side_effect=AssertionError("must not call playerctl")
                    ), mock.patch.object(
                        mod,
                        "atomic_write_json",
                        side_effect=AssertionError("preflight must not write through symlink"),
                    ):
                        payload = mod.execute(
                            "next",
                            "rhythmbox",
                            False,
                            0.2,
                            operation_id=operation_id,
                            operation_preflight=True,
                        )
                    self.assertTrue(
                        (record_path if target_kind == "record" else lock_path).is_symlink()
                    )
                    self.assertEqual(target.read_bytes(), b"do not follow")

                self.assert_preflight_receipt(
                    mod,
                    payload,
                    state="operation_record_invalid",
                    candidate=False,
                )

    def test_operation_preflight_busy_lock_is_blocked_but_same_id_retryable(self):
        mod = load_module()
        operation_id = "preflight-busy"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
        ):
            mod.ensure_operation_directory(mod.operation_directory())
            lock_path = self.create_operation_lock(mod, operation_id)
            lock_fd = os.open(lock_path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                before = lock_path.read_bytes()
                with mock.patch.object(
                    mod, "run", side_effect=AssertionError("must not call playerctl")
                ), mock.patch.object(
                    mod,
                    "atomic_write_json",
                    side_effect=AssertionError("preflight must not write a record"),
                ):
                    payload = mod.execute(
                        "next",
                        "rhythmbox",
                        False,
                        0.2,
                        operation_id=operation_id,
                        operation_preflight=True,
                    )
                self.assertEqual(lock_path.read_bytes(), before)
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)

        self.assert_preflight_receipt(
            mod,
            payload,
            state="operation_lock_busy",
            candidate=False,
            outcome="indeterminate",
        )
        self.assertEqual(payload["recover"], "retry")
        self.assertEqual(
            payload["preflight"]["operation_id_disposition"],
            "indeterminate_do_not_replace_automatically",
        )
        self.assertTrue(payload["preflight"]["same_id_retry_allowed"])
        self.assertFalse(payload["preflight"]["automatic_new_id_allowed"])

    def test_operation_preflight_unavailable_journal_has_observation_and_blocks_identity_use(self):
        mod = load_module()
        with mock.patch.dict(
            os.environ, {"AB_APP_CONTROL_OPERATION_DIR": "relative-preflight-state"}
        ), mock.patch.object(
            mod, "run", side_effect=AssertionError("must not call playerctl")
        ), mock.patch.object(
            mod,
            "ensure_operation_directory",
            side_effect=AssertionError("preflight must not mkdir"),
        ):
            payload = mod.execute(
                "next",
                "rhythmbox",
                False,
                0.2,
                operation_id="preflight-unavailable",
                operation_preflight=True,
            )

        self.assert_preflight_receipt(
            mod,
            payload,
            state="operation_journal_unavailable",
            candidate=False,
        )
        self.assertEqual(
            payload["preflight"]["operation_id_disposition"],
            "invalid_or_unavailable",
        )
        self.assertFalse(payload["preflight"]["same_id_retry_allowed"])
        self.assertFalse(payload["preflight"]["automatic_new_id_allowed"])

    def test_operation_preflight_terminal_failure_blocks_without_replaying_or_redispatching(self):
        mod = load_module()
        operation_id = "preflight-terminal-failure"
        calls = []
        media_run = make_media_run(["/track/1"], calls)

        def failed_next(argv, env, timeout=2.0):
            if argv == ["playerctl", "-p", "rhythmbox", "next"]:
                calls.append(argv)
                return 1, "", "backend refused next"
            return media_run(argv, env, timeout)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
        ):
            with mock.patch.object(mod, "run", side_effect=failed_next), mock.patch.object(
                mod.shutil, "which", return_value="/usr/bin/playerctl"
            ):
                failed = mod.execute(
                    "next", "rhythmbox", False, 0.2, operation_id=operation_id
                )
            self.assertEqual(failed["verdict"], "error")
            self.assertEqual(failed["transaction"]["dispatch_count"], 1)
            record_path = mod.operation_record_path(operation_id)
            before = record_path.read_bytes()
            calls.clear()
            with mock.patch.object(
                mod, "run", side_effect=AssertionError("must not call playerctl")
            ), mock.patch.object(
                mod,
                "atomic_write_json",
                side_effect=AssertionError("preflight must not rewrite terminal receipt"),
            ):
                payload = mod.execute(
                    "next",
                    "rhythmbox",
                    False,
                    0.2,
                    operation_id=operation_id,
                    operation_preflight=True,
                )
            self.assertEqual(record_path.read_bytes(), before)

        self.assert_preflight_receipt(
            mod,
            payload,
            state="terminal_operation_not_verified",
            candidate=False,
        )
        self.assertEqual(payload["preflight"]["dispatch_count"], 1)
        self.assertEqual(payload["preflight"]["terminal_verdict"], "error")
        self.assertEqual(
            payload["preflight"]["operation_id_disposition"], "terminal_failure"
        )
        self.assertFalse(payload["preflight"]["same_id_retry_allowed"])
        self.assertIn(
            "reobserve_and_replan_without_automatic_new_id",
            payload["preflight"]["recommended_next"],
        )
        self.assertEqual(calls, [])

    def test_operation_preflight_is_advisory_and_execute_revalidates_toctou_conflict(self):
        mod = load_module()
        operation_id = "preflight-toctou"
        with tempfile.TemporaryDirectory() as tmp:
            journal_dir = pathlib.Path(tmp) / "operations"
            with mock.patch.dict(
                os.environ, {"AB_APP_CONTROL_OPERATION_DIR": str(journal_dir)}
            ):
                with mock.patch.object(
                    mod, "run", side_effect=AssertionError("must not call playerctl")
                ):
                    candidate = mod.execute(
                        "next",
                        "rhythmbox",
                        False,
                        0.2,
                        operation_id=operation_id,
                        operation_preflight=True,
                    )
                self.assertFalse(journal_dir.exists())
                record_path, _ = self.write_operation_fixture(
                    mod,
                    operation_id,
                    phase="retryable",
                    dispatch_count=0,
                    player_selector="spotify",
                )
                before = record_path.read_bytes()
                with mock.patch.object(
                    mod, "run", side_effect=AssertionError("must revalidate before playerctl")
                ):
                    action = mod.execute(
                        "next", "rhythmbox", False, 0.2, operation_id=operation_id
                    )
                self.assertEqual(record_path.read_bytes(), before)

        self.assert_preflight_receipt(
            mod, candidate, state="fresh_candidate", candidate=True
        )
        self.assertFalse(candidate["claim_boundary"]["state_unchanged_until_action"])
        self.assertFalse(candidate["preflight"]["dispatch_authorized"])
        self.assertTrue(candidate["preflight"]["must_revalidate"])
        self.assertEqual(action["error"]["code"], "idempotency_conflict")
        self.assertEqual(action["transaction"]["dispatch_count"], 0)

    def test_durable_next_dispatches_exactly_once_and_writes_secure_receipt(self):
        mod = load_module()
        calls = []
        fake_run = make_media_run(["/track/1", "/track/2"], calls)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=fake_run), \
             mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"):
            payload = mod.execute(
                "next", "rhythmbox", False, 0.8, operation_id="episode:next-001"
            )
            record_path = mod.operation_record_path("episode:next-001")
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(stat.S_IMODE(pathlib.Path(tmp).stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(record_path.stat().st_mode), 0o600)

        self.assertEqual(payload["verdict"], "verified")
        self.assertFalse(payload["read_only"])
        self.assertEqual(
            payload["verification"]["predicate"], "track_identity_changed_settled"
        )
        self.assertEqual(
            payload["verification"]["settlement"]["schema"],
            mod.TRACK_SETTLEMENT_SCHEMA,
        )
        self.assertEqual(payload["dispatch"]["status"], "dispatched")
        self.assertEqual(payload["dispatch"]["rc"], 0)
        self.assertEqual(payload["transaction"]["schema"], mod.OPERATION_SCHEMA)
        self.assertEqual(payload["transaction"]["phase"], "verified")
        self.assertEqual(payload["transaction"]["dispatch_count"], 1)
        self.assertFalse(payload["transaction"]["external_execution_repeated"])
        self.assertEqual(len(payload["transaction"]["request_digest"]), 64)
        self.assertEqual(calls.count(["playerctl", "-p", "rhythmbox", "next"]), 1)
        self.assertEqual(record["phase"], "terminal")
        self.assertEqual(record["dispatch_count"], 1)
        self.assertEqual(record["player"], "rhythmbox")
        self.assertEqual(record["baseline"]["track_id"], "/track/1")
        self.assertEqual(record["payload"]["verdict"], "verified")

    def test_durable_next_ignores_transient_changed_id_and_settles_final_track(self):
        mod = load_module()
        calls = []
        clock = VirtualClock()
        fake_run = make_media_run(
            [
                ("/track/A", "Artist", "A"),
                ("/track/B", "Artist", "transient B"),
                ("/track/C", "Artist", "settled C"),
                ("/track/C", "Artist", "settled C"),
                ("/track/C", "Artist", "settled C"),
            ],
            calls,
        )
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=fake_run), \
             mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"), \
             mock.patch.object(mod.time, "monotonic", side_effect=clock.monotonic), \
             mock.patch.object(mod.time, "sleep", side_effect=clock.sleep):
            payload = mod.execute(
                "next", "rhythmbox", False, 2.0, operation_id="settled-transient"
            )
            record = json.loads(
                mod.operation_record_path("settled-transient").read_text(encoding="utf-8")
            )

        self.assertEqual(payload["verdict"], "verified")
        self.assertEqual(payload["after"]["track_id"], "/track/C")
        self.assertEqual(payload["after"]["title"], "settled C")
        self.assertEqual(payload["verification"]["polls"], 4)
        self.assertEqual(
            payload["verification"]["settlement"]["candidate_track_id"],
            "/track/C",
        )
        self.assertEqual(record["phase"], "terminal")
        self.assertEqual(record["payload"]["after"]["track_id"], "/track/C")
        self.assertEqual(calls.count(["playerctl", "-p", "rhythmbox", "next"]), 1)

    def test_pending_same_id_restarts_candidate_window_without_redispatch(self):
        mod = load_module()
        operation_id = "settled-pending-retry"
        calls = []
        clock = VirtualClock()
        media_run = make_media_run(
            ["/track/A", "/track/B", "/track/B", "/track/B",
             "/track/C", "/track/C", "/track/C"],
            calls,
        )
        dispatched_record = {"bytes": None}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
        ):
            record_path = mod.operation_record_path(operation_id)

            def checked_run(argv, env, timeout=2.0):
                if argv == ["playerctl", "-p", "rhythmbox", "next"]:
                    dispatched_record["bytes"] = record_path.read_bytes()
                return media_run(argv, env, timeout)

            with mock.patch.object(mod, "run", side_effect=checked_run), \
                 mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"), \
                 mock.patch.object(mod.time, "monotonic", side_effect=clock.monotonic), \
                 mock.patch.object(mod.time, "sleep", side_effect=clock.sleep):
                first = mod.execute(
                    "next", "rhythmbox", False, 0.3, operation_id=operation_id
                )
                pending_bytes = record_path.read_bytes()
                calls.clear()
                preflight = mod.execute(
                    "next",
                    "rhythmbox",
                    False,
                    0.8,
                    operation_id=operation_id,
                    operation_preflight=True,
                )
                self.assertEqual(record_path.read_bytes(), pending_bytes)
                recovered = mod.execute(
                    "next", "rhythmbox", False, 0.8, operation_id=operation_id
                )

        self.assertEqual(first["error"]["code"], "operation_effect_not_settled")
        self.assertEqual(first["recover"], "retry")
        self.assertEqual(first["transaction"]["phase"], "dispatch_started")
        self.assertEqual(first["transaction"]["dispatch_count"], 1)
        self.assertEqual(
            first["verification"]["settlement"]["candidate_track_id"], "/track/B"
        )
        self.assertFalse(first["verification"]["settlement"]["settled"])
        self.assertEqual(
            first["verification"]["settlement"]["required_stable_ms"], 500
        )
        self.assertLess(
            first["verification"]["settlement"]["observed_stable_ms"], 500
        )
        self.assertEqual(pending_bytes, dispatched_record["bytes"])
        self.assertNotIn("payload", json.loads(pending_bytes))
        self.assertEqual(
            preflight["preflight"]["state"], "recovery_observation_candidate"
        )
        self.assertFalse(preflight["preflight"]["player_observed"])
        self.assertEqual(recovered["verdict"], "verified")
        self.assertEqual(recovered["after"]["track_id"], "/track/C")
        self.assertEqual(recovered["verification"]["polls"], 3)
        self.assertEqual(
            recovered["verification"]["settlement"]["observed_consecutive_observations"],
            3,
        )
        self.assertTrue(recovered["transaction"]["recovered_after_interruption"])
        self.assertFalse(any(call == ["playerctl", "-p", "rhythmbox", "next"] for call in calls))
        self.assertFalse(any(call == ["playerctl", "-l"] for call in calls))

    def test_durable_next_same_id_replays_without_playerctl(self):
        mod = load_module()
        calls = []
        fake_run = make_media_run(["/track/1", "/track/2"], calls)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=fake_run), \
             mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"):
            first = mod.execute("next", "rhythmbox", False, 0.8, operation_id="replay.1")
            calls.clear()
            replay = mod.execute("next", "rhythmbox", False, 0.2, operation_id="replay.1")

        self.assertEqual(first["verdict"], "verified")
        self.assertEqual(replay["verdict"], "verified")
        self.assertEqual(replay["transaction"]["phase"], "verified")
        self.assertTrue(replay["transaction"]["idempotent_replay"])
        self.assertFalse(replay["transaction"]["external_execution_repeated"])
        self.assertEqual(
            replay["verification"]["settlement"],
            first["verification"]["settlement"],
        )
        self.assertEqual(calls, [])

    def test_durable_next_same_id_different_request_conflicts_without_playerctl(self):
        mod = load_module()
        calls = []
        fake_run = make_media_run(["/track/1", "/track/2"], calls)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=fake_run), \
             mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"):
            first = mod.execute("next", "rhythmbox", False, 0.8, operation_id="conflict-1")
            calls.clear()
            conflict = mod.execute("next", "spotify", False, 0.2, operation_id="conflict-1")

        self.assertEqual(first["verdict"], "verified")
        self.assertEqual(conflict["error"]["code"], "idempotency_conflict")
        self.assertEqual(conflict["recover"], "replan")
        self.assertEqual(calls, [])

    def test_dispatch_started_changed_track_recovers_without_dispatch(self):
        mod = load_module()
        operation_id = "recover:changed"
        calls = []
        fake_run = make_media_run(["/track/2"], calls, discovery=False)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=fake_run):
            mod.ensure_operation_directory(mod.operation_directory())
            now = time.time()
            created_at = now - 1
            digest = mod.operation_request_digest("next", "rhythmbox", 3600)
            record = mod.operation_record(
                operation_id,
                digest,
                mod.operation_request("next", "rhythmbox", 3600),
                created_at=created_at,
                expires_at=created_at + 3600,
                phase="dispatch_started",
                dispatch_count=1,
                player="rhythmbox",
                baseline={"track_id": "/track/1", "artist": "Artist", "title": "Title 1"},
            )
            mod.atomic_write_json(mod.operation_record_path(operation_id), record)
            payload = mod.execute(
                "next", "rhythmbox", False, 0.8, operation_id=operation_id
            )

        self.assertEqual(payload["verdict"], "verified")
        self.assertEqual(payload["causal_attribution"], "unknown_after_restart")
        self.assertEqual(
            payload["verification"]["predicate"],
            "track_identity_changed_after_restart_settled",
        )
        self.assertEqual(payload["transaction"]["phase"], "verified")
        self.assertTrue(payload["transaction"]["recovered_after_interruption"])
        self.assertGreaterEqual(payload["verification"]["polls"], 3)
        self.assertEqual(
            payload["verification"]["settlement"]["candidate_track_id"],
            "/track/2",
        )
        self.assertEqual(payload["selection"]["selector"], "rhythmbox")
        self.assertFalse(payload["transaction"]["external_execution_repeated"])
        self.assertFalse(any(call == ["playerctl", "-p", "rhythmbox", "next"] for call in calls))
        self.assertFalse(any(call == ["playerctl", "-l"] for call in calls))

    def test_dispatch_started_same_or_unknown_track_remains_pending(self):
        for suffix, current_track, expected_reason in (
            ("same", "/track/1", "track_id_unchanged"),
            ("unknown", None, "current_track_id_missing"),
        ):
            with self.subTest(suffix=suffix):
                mod = load_module()
                operation_id = f"recover:{suffix}"
                calls = []
                fake_run = make_media_run([current_track], calls, discovery=False)
                with tempfile.TemporaryDirectory() as tmp, \
                     mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
                     mock.patch.object(mod, "run", side_effect=fake_run):
                    mod.ensure_operation_directory(mod.operation_directory())
                    now = time.time()
                    created_at = now - 1
                    digest = mod.operation_request_digest("next", "rhythmbox", 3600)
                    record = mod.operation_record(
                        operation_id,
                        digest,
                        mod.operation_request("next", "rhythmbox", 3600),
                        created_at=created_at,
                        expires_at=created_at + 3600,
                        phase="dispatch_started",
                        dispatch_count=1,
                        player="rhythmbox",
                        baseline={"track_id": "/track/1"},
                    )
                    record_path = mod.operation_record_path(operation_id)
                    mod.atomic_write_json(record_path, record)
                    before = record_path.read_bytes()
                    payload = mod.execute(
                        "next", "rhythmbox", False, 0.2, operation_id=operation_id
                    )
                    self.assertEqual(record_path.read_bytes(), before)
                    calls.clear()
                    pending_retry = mod.execute(
                        "next", "rhythmbox", False, 0.2, operation_id=operation_id
                    )
                    self.assertEqual(record_path.read_bytes(), before)

                self.assertEqual(payload["status"], "indeterminate")
                self.assertEqual(payload["verdict"], "error")
                self.assertEqual(payload["recover"], "retry")
                self.assertEqual(payload["error"]["reason"], expected_reason)
                self.assertEqual(
                    payload["error"]["code"], "operation_effect_not_settled"
                )
                self.assertEqual(payload["transaction"]["phase"], "dispatch_started")
                self.assertTrue(payload["transaction"]["recovered_after_interruption"])
                self.assertFalse(
                    pending_retry["transaction"]["idempotent_replay"]
                )
                self.assertFalse(
                    any(call == ["playerctl", "-p", "rhythmbox", "next"] for call in calls)
                )
                self.assertFalse(any(call == ["playerctl", "-l"] for call in calls))

    def test_corrupt_dispatch_started_anchor_fails_closed_without_rewrite(self):
        mutations = {
            "missing-player": lambda record: record.pop("player"),
            "missing-resolved-player": lambda record: record.pop("resolved_player"),
            "resolved-player-mismatch": lambda record: record.__setitem__(
                "resolved_player", "spotify"
            ),
            "missing-baseline-track": lambda record: record.__setitem__(
                "baseline", {"track_id": None}
            ),
            "baseline-player-mismatch": lambda record: record.__setitem__(
                "baseline", {"player": "spotify", "track_id": "/track/1"}
            ),
            "unexpected-payload": lambda record: record.__setitem__(
                "payload", {"verdict": "verified"}
            ),
        }
        for suffix, mutate in mutations.items():
            with self.subTest(suffix=suffix):
                mod = load_module()
                operation_id = f"corrupt-pending-{suffix}"
                with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
                    os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
                ), mock.patch.object(
                    mod, "run", side_effect=AssertionError("must not call playerctl")
                ):
                    mod.ensure_operation_directory(mod.operation_directory())
                    created_at = time.time() - 1
                    request = mod.operation_request("next", "rhythmbox", 3600)
                    digest = mod.operation_request_digest("next", "rhythmbox", 3600)
                    record = mod.operation_record(
                        operation_id,
                        digest,
                        request,
                        created_at=created_at,
                        expires_at=created_at + 3600,
                        phase="dispatch_started",
                        dispatch_count=1,
                        player="rhythmbox",
                        baseline={"player": "rhythmbox", "track_id": "/track/1"},
                    )
                    mutate(record)
                    record_path = mod.operation_record_path(operation_id)
                    mod.atomic_write_json(record_path, record)
                    before = record_path.read_bytes()
                    payload = mod.execute(
                        "next", "rhythmbox", False, 0.8, operation_id=operation_id
                    )

                    self.assertEqual(record_path.read_bytes(), before)

                self.assertEqual(payload["error"]["code"], "operation_record_invalid")
                self.assertEqual(payload["recover"], "replan")
                self.assertEqual(payload["transaction"]["phase"], "journal_error")
                self.assertEqual(payload["transaction"]["dispatch_count"], 1)

    def test_expired_operation_never_observes_or_dispatches(self):
        mod = load_module()
        operation_id = "expired-1"
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=AssertionError("must not call playerctl")):
            mod.ensure_operation_directory(mod.operation_directory())
            now = time.time()
            created_at = now - 3601
            digest = mod.operation_request_digest("next", "rhythmbox", 3600)
            record = mod.operation_record(
                operation_id,
                digest,
                mod.operation_request("next", "rhythmbox", 3600),
                created_at=created_at,
                expires_at=created_at + 3600,
                phase="dispatch_started",
                dispatch_count=1,
                player="rhythmbox",
                baseline={"track_id": "/track/1"},
            )
            mod.atomic_write_json(mod.operation_record_path(operation_id), record)
            payload = mod.execute(
                "next", "rhythmbox", False, 0.2, operation_id=operation_id
            )

        self.assertEqual(payload["error"]["code"], "operation_expired")
        self.assertEqual(payload["recover"], "replan")

    def test_dispatch_started_expiry_during_recovery_never_terminalizes(self):
        for suffix, wall_times in (
            ("after-observation", [1000.0, 1000.6]),
            ("before-terminal-write", [1000.0, 1000.4, 1000.6]),
        ):
            with self.subTest(suffix=suffix):
                mod = load_module()
                operation_id = f"recovery-expiry-{suffix}"
                calls = []
                clock = VirtualClock()
                fake_run = make_media_run(["/track/2"], calls, discovery=False)
                with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
                    os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
                ):
                    mod.ensure_operation_directory(mod.operation_directory())
                    request = mod.operation_request("next", "rhythmbox", 60)
                    digest = mod.operation_request_digest("next", "rhythmbox", 60)
                    record = mod.operation_record(
                        operation_id,
                        digest,
                        request,
                        created_at=940.5,
                        expires_at=1000.5,
                        phase="dispatch_started",
                        dispatch_count=1,
                        player="rhythmbox",
                        baseline={"player": "rhythmbox", "track_id": "/track/1"},
                    )
                    record_path = mod.operation_record_path(operation_id)
                    mod.atomic_write_json(record_path, record)
                    before = record_path.read_bytes()
                    with mock.patch.object(mod, "run", side_effect=fake_run), \
                         mock.patch.object(mod.time, "time", side_effect=wall_times), \
                         mock.patch.object(
                             mod.time, "monotonic", side_effect=clock.monotonic
                         ), mock.patch.object(
                             mod.time, "sleep", side_effect=clock.sleep
                         ):
                        payload = mod.execute(
                            "next",
                            "rhythmbox",
                            False,
                            0.8,
                            operation_id=operation_id,
                            operation_ttl_secs=60,
                        )

                    self.assertEqual(record_path.read_bytes(), before)

                self.assertEqual(payload["error"]["code"], "operation_expired")
                self.assertEqual(payload["recover"], "replan")
                self.assertEqual(payload["transaction"]["phase"], "dispatch_started")
                self.assertEqual(payload["transaction"]["dispatch_count"], 1)
                self.assertTrue(
                    payload["transaction"]["recovered_after_interruption"]
                )
                self.assertFalse(
                    any(call == ["playerctl", "-p", "rhythmbox", "next"] for call in calls)
                )
                self.assertFalse(any(call == ["playerctl", "-l"] for call in calls))

    def test_fresh_terminal_write_rechecks_expiry_and_leaves_dispatch_anchor(self):
        mod = load_module()
        operation_id = "fresh-terminal-expiry"
        calls = []
        clock = VirtualClock()
        fake_run = make_media_run(["/track/1", "/track/2"], calls)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}
        ), mock.patch.object(mod, "run", side_effect=fake_run), mock.patch.object(
            mod.shutil, "which", return_value="/usr/bin/playerctl"
        ), mock.patch.object(
            mod.time, "time", side_effect=[1000.0, 1000.1, 1059.9, 1060.1]
        ), mock.patch.object(
            mod.time, "monotonic", side_effect=clock.monotonic
        ), mock.patch.object(
            mod.time, "sleep", side_effect=clock.sleep
        ):
            payload = mod.execute(
                "next",
                "rhythmbox",
                False,
                0.8,
                operation_id=operation_id,
                operation_ttl_secs=60,
            )
            record = json.loads(
                mod.operation_record_path(operation_id).read_text(encoding="utf-8")
            )

        self.assertEqual(payload["error"]["code"], "operation_expired")
        self.assertEqual(payload["recover"], "replan")
        self.assertEqual(payload["transaction"]["phase"], "dispatch_started")
        self.assertEqual(record["phase"], "dispatch_started")
        self.assertEqual(record["dispatch_count"], 1)
        self.assertNotIn("payload", record)
        self.assertEqual(
            calls.count(["playerctl", "-p", "rhythmbox", "next"]), 1
        )

    def test_durable_next_requires_nonempty_baseline_track_id(self):
        mod = load_module()
        calls = []
        fake_run = make_media_run([None], calls)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=fake_run), \
             mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"):
            payload = mod.execute(
                "next", "rhythmbox", False, 0.2, operation_id="baseline-missing"
            )
            record = json.loads(
                mod.operation_record_path("baseline-missing").read_text(encoding="utf-8")
            )

        self.assertEqual(payload["error"]["code"], "missing_baseline_track_id")
        self.assertEqual(payload["recover"], "replan")
        self.assertEqual(record["phase"], "terminal")
        self.assertEqual(record["dispatch_count"], 0)
        self.assertNotIn(["playerctl", "-p", "rhythmbox", "next"], calls)

    def test_durable_next_requires_strict_changed_post_track_id(self):
        for suffix, after in (
            ("same-id-new-title", ("/track/1", "Artist", "Title 2")),
            ("missing-id-new-title", (None, "Artist", "Title 2")),
        ):
            with self.subTest(suffix=suffix):
                mod = load_module()
                calls = []
                fake_run = make_media_run(
                    [("/track/1", "Artist", "Title 1"), after], calls
                )
                with tempfile.TemporaryDirectory() as tmp, \
                     mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
                     mock.patch.object(mod, "run", side_effect=fake_run), \
                     mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"):
                    payload = mod.execute(
                        "next", "rhythmbox", False, 0.01,
                        operation_id=f"strict:{suffix}",
                    )
                    record = json.loads(
                        mod.operation_record_path(f"strict:{suffix}").read_text(
                            encoding="utf-8"
                        )
                    )

                self.assertEqual(payload["verdict"], "error")
                self.assertEqual(payload["recover"], "retry")
                self.assertEqual(
                    payload["error"]["code"], "operation_effect_not_settled"
                )
                self.assertEqual(
                    payload["verification"]["predicate"],
                    "track_identity_change_not_settled",
                )
                self.assertEqual(payload["transaction"]["dispatch_count"], 1)
                self.assertEqual(payload["transaction"]["phase"], "dispatch_started")
                self.assertEqual(record["phase"], "dispatch_started")
                self.assertEqual(
                    calls.count(["playerctl", "-p", "rhythmbox", "next"]), 1
                )

    def test_busy_operation_lock_fails_closed(self):
        mod = load_module()
        operation_id = "busy-1"
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=AssertionError("must not call playerctl")):
            mod.ensure_operation_directory(mod.operation_directory())
            lock_fd = os.open(mod.operation_lock_path(operation_id), os.O_RDWR | os.O_CREAT, 0o600)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                payload = mod.execute(
                    "next", "rhythmbox", False, 0.2, operation_id=operation_id
                )
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)

        self.assertEqual(payload["error"]["code"], "operation_lock_busy")
        self.assertFalse(payload["transaction"]["external_execution_repeated"])

    def test_journal_write_failure_before_dispatch_never_calls_next(self):
        mod = load_module()
        calls = []
        fake_run = make_media_run(["/track/1"], calls)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=fake_run), \
             mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"), \
             mock.patch.object(mod, "atomic_write_json", side_effect=OSError("disk full")):
            payload = mod.execute(
                "next", "rhythmbox", False, 0.2, operation_id="write-failure"
            )

        self.assertEqual(payload["error"]["code"], "journal_write_failed")
        self.assertEqual(payload["recover"], "replan")
        self.assertEqual(payload["transaction"]["dispatch_count"], 0)
        self.assertNotIn(["playerctl", "-p", "rhythmbox", "next"], calls)

    def test_retryable_predispatch_failure_reobserves_same_operation(self):
        mod = load_module()
        calls = []
        media_run = make_media_run(["/track/1", "/track/2"], calls)
        attempts = {"discovery": 0}

        def fake_run(argv, env, timeout=2.0):
            if argv == ["playerctl", "-l"] and attempts["discovery"] == 0:
                attempts["discovery"] += 1
                calls.append(argv)
                return 1, "", "temporary bus error"
            return media_run(argv, env, timeout)

        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=fake_run), \
             mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"):
            first = mod.execute(
                "next", "rhythmbox", False, 0.2, operation_id="retryable-1"
            )
            record = json.loads(
                mod.operation_record_path("retryable-1").read_text(encoding="utf-8")
            )
            second = mod.execute(
                "next", "rhythmbox", False, 0.8, operation_id="retryable-1"
            )

        self.assertEqual(first["recover"], "retry")
        self.assertEqual(first["transaction"]["phase"], "retryable")
        self.assertEqual(first["transaction"]["dispatch_count"], 0)
        self.assertEqual(record["phase"], "retryable")
        self.assertEqual(second["verdict"], "verified")
        self.assertEqual(calls.count(["playerctl", "-p", "rhythmbox", "next"]), 1)

    def test_terminal_receipt_requires_admissible_verified_evidence(self):
        mod = load_module()
        operation_id = "forged-terminal"
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=AssertionError("must not call playerctl")):
            mod.ensure_operation_directory(mod.operation_directory())
            now = time.time()
            digest = mod.operation_request_digest("next", "rhythmbox", 3600)
            request = mod.operation_request("next", "rhythmbox", 3600)
            forged_payload = {
                "schema": mod.SCHEMA,
                "verdict": "verified",
                "recover": "proceed",
                "domain": "media",
                "action": "next",
                "read_only": False,
                "verification": {"status": "verified", "predicate": "track_identity_changed"},
                "transaction": mod.operation_transaction(
                    operation_id,
                    digest,
                    phase="verified",
                    dispatch_count=1,
                    idempotent_replay=False,
                    recovered_after_interruption=False,
                    expires_at=now + 3600,
                ),
            }
            record = mod.operation_record(
                operation_id,
                digest,
                request,
                created_at=now,
                expires_at=now + 3600,
                phase="terminal",
                dispatch_count=1,
                payload=forged_payload,
            )
            mod.atomic_write_json(mod.operation_record_path(operation_id), record)
            payload = mod.execute(
                "next", "rhythmbox", False, 0.2, operation_id=operation_id
            )

        self.assertEqual(payload["verdict"], "error")
        self.assertEqual(payload["error"]["code"], "operation_record_invalid")

    def test_terminal_receipt_rejects_type_confusion_and_record_mismatch(self):
        mod = load_module()
        operation_id = "terminal-shape-check"
        calls = []
        media_run = make_media_run(["/track/1", "/track/2"], calls)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=media_run), \
             mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"):
            fresh = mod.execute(
                "next", "rhythmbox", False, 0.8, operation_id=operation_id
            )
            self.assertEqual(fresh["verdict"], "verified")
            record_path = mod.operation_record_path(operation_id)
            valid_record = json.loads(record_path.read_text(encoding="utf-8"))

            def dispatch_count_float(record):
                record["payload"]["transaction"]["dispatch_count"] = 1.0

            def rc_bool(record):
                record["payload"]["dispatch"]["rc"] = False

            def wrong_status(record):
                record["payload"]["status"] = "not-verified"

            def baseline_mismatch(record):
                record["baseline"] = {"track_id": "/different"}

            def wrong_expiry(record):
                record["payload"]["transaction"]["expires_at"] = -1

            def malformed_before(record):
                record["payload"]["before"] = []

            def legacy_unsettled(record):
                record["payload"]["verification"].pop("settlement")
                record["payload"]["verification"]["predicate"] = "track_identity_changed"

            def settlement_candidate_mismatch(record):
                record["payload"]["verification"]["settlement"][
                    "candidate_track_id"
                ] = "/track/other"

            def settlement_required_count_wrong(record):
                record["payload"]["verification"]["settlement"][
                    "required_consecutive_observations"
                ] = 2

            def settlement_observed_count_bool(record):
                record["payload"]["verification"]["settlement"][
                    "observed_consecutive_observations"
                ] = True

            def settlement_required_stable_bool(record):
                record["payload"]["verification"]["settlement"][
                    "required_stable_ms"
                ] = True

            def settlement_observed_stable_short(record):
                record["payload"]["verification"]["settlement"][
                    "observed_stable_ms"
                ] = 499

            def settlement_polls_too_small(record):
                record["payload"]["verification"]["polls"] = 2

            def settlement_false(record):
                record["payload"]["verification"]["settlement"]["settled"] = False

            def settlement_reason_nonnull(record):
                record["payload"]["verification"]["reason"] = "observation_failed"

            def settlement_reason_missing(record):
                record["payload"]["verification"].pop("reason")

            def settlement_observation_error_nonnull(record):
                record["payload"]["verification"]["observation_error"] = {
                    "code": "observation_failed"
                }

            def settlement_observation_error_missing(record):
                record["payload"]["verification"].pop("observation_error")

            for name, mutate in (
                ("dispatch-count-float", dispatch_count_float),
                ("rc-bool", rc_bool),
                ("wrong-status", wrong_status),
                ("baseline-mismatch", baseline_mismatch),
                ("wrong-expiry", wrong_expiry),
                ("malformed-before", malformed_before),
                ("legacy-unsettled", legacy_unsettled),
                ("settlement-candidate-mismatch", settlement_candidate_mismatch),
                ("settlement-required-count-wrong", settlement_required_count_wrong),
                ("settlement-observed-count-bool", settlement_observed_count_bool),
                ("settlement-required-stable-bool", settlement_required_stable_bool),
                ("settlement-observed-stable-short", settlement_observed_stable_short),
                ("settlement-polls-too-small", settlement_polls_too_small),
                ("settlement-false", settlement_false),
                ("settlement-reason-nonnull", settlement_reason_nonnull),
                ("settlement-reason-missing", settlement_reason_missing),
                (
                    "settlement-observation-error-nonnull",
                    settlement_observation_error_nonnull,
                ),
                (
                    "settlement-observation-error-missing",
                    settlement_observation_error_missing,
                ),
            ):
                with self.subTest(name=name):
                    record = json.loads(json.dumps(valid_record))
                    mutate(record)
                    mod.atomic_write_json(record_path, record)
                    with mock.patch.object(
                        mod, "run", side_effect=AssertionError("must not call playerctl")
                    ):
                        payload = mod.execute(
                            "next", "rhythmbox", False, 0.2,
                            operation_id=operation_id,
                        )
                    self.assertEqual(payload["verdict"], "error")
                    self.assertEqual(
                        payload["error"]["code"], "operation_record_invalid"
                    )

    def test_dispatch_started_is_durable_before_next_and_terminal_write_failure_recovers(self):
        mod = load_module()
        operation_id = "terminal-write-failure"
        calls = []
        media_run = make_media_run(["/track/1", "/track/2"], calls)
        write_count = {"value": 0}
        real_atomic_write = mod.atomic_write_json

        def checked_run(argv, env, timeout=2.0):
            if argv == ["playerctl", "-p", "rhythmbox", "next"]:
                record = json.loads(
                    mod.operation_record_path(operation_id).read_text(encoding="utf-8")
                )
                self.assertEqual(record["phase"], "dispatch_started")
                self.assertEqual(record["dispatch_count"], 1)
                self.assertEqual(record["baseline"]["track_id"], "/track/1")
            return media_run(argv, env, timeout)

        def fail_terminal_write(path, value):
            write_count["value"] += 1
            if write_count["value"] == 2:
                raise OSError("simulated terminal fsync failure")
            return real_atomic_write(path, value)

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
                 mock.patch.object(mod, "run", side_effect=checked_run), \
                 mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"), \
                 mock.patch.object(mod, "atomic_write_json", side_effect=fail_terminal_write):
                failed = mod.execute(
                    "next", "rhythmbox", False, 0.8, operation_id=operation_id
                )
                record_path = mod.operation_record_path(operation_id)
            interrupted_record = json.loads(
                record_path.read_text(encoding="utf-8")
            )
            calls_before_recovery = list(calls)
            with mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
                 mock.patch.object(mod, "run", side_effect=checked_run):
                recovered = mod.execute(
                    "next", "rhythmbox", False, 0.8, operation_id=operation_id
                )

        self.assertEqual(failed["error"]["code"], "journal_write_failed")
        self.assertEqual(failed["transaction"]["dispatch_count"], 1)
        self.assertEqual(interrupted_record["phase"], "dispatch_started")
        self.assertNotIn("payload", interrupted_record)
        self.assertEqual(recovered["verdict"], "verified")
        self.assertEqual(
            recovered["verification"]["settlement"]["schema"],
            mod.TRACK_SETTLEMENT_SCHEMA,
        )
        self.assertTrue(recovered["transaction"]["recovered_after_interruption"])
        self.assertEqual(
            calls.count(["playerctl", "-p", "rhythmbox", "next"]),
            calls_before_recovery.count(["playerctl", "-p", "rhythmbox", "next"]),
        )

    def test_failed_dispatch_receipt_replays_without_redispatch(self):
        mod = load_module()
        calls = []
        media_run = make_media_run(["/track/1"], calls)

        def failed_next(argv, env, timeout=2.0):
            if argv == ["playerctl", "-p", "rhythmbox", "next"]:
                calls.append(argv)
                return 1, "", "backend refused next"
            return media_run(argv, env, timeout)

        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=failed_next), \
             mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"):
            first = mod.execute(
                "next", "rhythmbox", False, 0.2, operation_id="failed-dispatch"
            )
            calls.clear()
            replay = mod.execute(
                "next", "rhythmbox", False, 0.2, operation_id="failed-dispatch"
            )

        self.assertEqual(first["verdict"], "error")
        self.assertEqual(first["recover"], "replan")
        self.assertEqual(first["transaction"]["dispatch_count"], 1)
        self.assertEqual(replay["verdict"], "error")
        self.assertEqual(replay["recover"], "replan")
        self.assertTrue(replay["transaction"]["idempotent_replay"])
        self.assertEqual(calls, [])

    def test_sigkill_after_real_child_dispatch_recovers_without_second_next(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            state_path = root / "media-state.json"
            state_path.write_text(
                json.dumps({"track_id": "/track/1", "next_count": 0}),
                encoding="utf-8",
            )
            fake_playerctl = bin_dir / "playerctl"
            fake_playerctl.write_text(
                """#!/usr/bin/env python3
import json
import os
import pathlib
import signal
import sys

state_path = pathlib.Path(os.environ["FAKE_MEDIA_STATE"])
args = sys.argv[1:]
if args == ["-l"]:
    print("rhythmbox")
    raise SystemExit(0)
if args == ["-p", "rhythmbox", "status"]:
    print("Playing")
    raise SystemExit(0)
if args == ["-p", "rhythmbox", "volume"]:
    print("0.50")
    raise SystemExit(0)
if args == ["-p", "rhythmbox", "position"]:
    print("12.5")
    raise SystemExit(0)
if args[-2:] == ["--format", "{{mpris:length}}"]:
    print("187000000")
    raise SystemExit(0)
if args[-2:] == ["--format", "{{mpris:trackid}}\\t{{xesam:artist}}\\t{{xesam:title}}"]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    print(f"{state['track_id']}\\tArtist\\tTitle")
    raise SystemExit(0)
if args == ["-p", "rhythmbox", "next"]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["track_id"] = "/track/2"
    state["next_count"] += 1
    state_path.write_text(json.dumps(state), encoding="utf-8")
    os.kill(os.getppid(), signal.SIGKILL)
    raise SystemExit(0)
raise SystemExit(64)
""",
                encoding="utf-8",
            )
            fake_playerctl.chmod(0o755)
            journal_dir = root / "operations"
            env = dict(os.environ)
            env.update(
                {
                    "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
                    "FAKE_MEDIA_STATE": str(state_path),
                    "AB_APP_CONTROL_OPERATION_DIR": str(journal_dir),
                }
            )
            operation_id = "ab-episode-0123456789abcdef0123456789abcdef"
            argv = [
                sys.executable,
                str(SCRIPT),
                "--action",
                "next",
                "--player",
                "rhythmbox",
                "--operation-id",
                operation_id,
                "--verify-timeout",
                "4.0",
                "--wrapper-contract-version",
                "agent_bridge.app_control.wrapper_contract.v1",
            ]
            crashed = subprocess.run(
                argv, capture_output=True, text=True, env=env, check=False, timeout=5
            )
            self.assertEqual(crashed.returncode, -signal.SIGKILL)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if state["next_count"] == 1:
                    break
                time.sleep(0.01)
            self.assertEqual(state["next_count"], 1)
            record_path = journal_dir / (
                hashlib.sha256(operation_id.encode("ascii")).hexdigest() + ".json"
            )
            interrupted_record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(interrupted_record["phase"], "dispatch_started")
            self.assertEqual(interrupted_record["dispatch_count"], 1)

            index_script = SCRIPT.with_name("app-control-recovery-candidates.py")
            discovered = subprocess.run(
                [sys.executable, str(index_script), "--journal", str(journal_dir)],
                capture_output=True, text=True, env=env, check=False, timeout=5,
            )
            self.assertEqual(discovered.returncode, 0, discovered.stderr)
            handoff = json.loads(discovered.stdout)
            self.assertEqual(handoff["candidate_count"], 1)
            candidate = handoff["candidates"][0]
            self.assertEqual(candidate["operation_id"], operation_id)
            self.assertEqual(candidate["request"]["action"], "next")
            self.assertEqual(candidate["request"]["player_selector"], "rhythmbox")
            self.assertEqual(candidate["request"]["operation_ttl_secs"], 3600)
            self.assertFalse(candidate["automatic_execution_allowed"])
            record_sha_before_recovery = hashlib.sha256(record_path.read_bytes()).hexdigest()
            self.assertEqual(candidate["record_sha256"], record_sha_before_recovery)

            recovery_argv = [
                sys.executable, str(SCRIPT), "--action", candidate["request"]["action"],
                "--player", candidate["request"]["player_selector"],
                "--operation-id", candidate["operation_id"],
                "--operation-ttl-secs", str(candidate["request"]["operation_ttl_secs"]),
                "--verify-timeout", "4.0",
                "--wrapper-contract-version", "agent_bridge.app_control.wrapper_contract.v1",
            ]

            recovered = subprocess.run(
                recovery_argv, capture_output=True, text=True, env=env, check=False, timeout=5
            )
            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            payload = json.loads(recovered.stdout)
            self.assertEqual(payload["verdict"], "verified")
            self.assertEqual(
                payload["verification"]["predicate"],
                "track_identity_changed_after_restart_settled",
            )
            self.assertEqual(
                payload["verification"]["settlement"]["schema"],
                "agent_bridge.app_control.track_settlement.v0",
            )
            self.assertGreaterEqual(
                payload["verification"]["settlement"]["observed_stable_ms"], 500
            )
            self.assertTrue(payload["transaction"]["recovered_after_interruption"])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["next_count"], 1)
            replayed = subprocess.run(
                recovery_argv, capture_output=True, text=True, env=env, check=False, timeout=5
            )
            self.assertEqual(replayed.returncode, 0, replayed.stderr)
            replay_payload = json.loads(replayed.stdout)
            self.assertTrue(replay_payload["transaction"]["idempotent_replay"])
            self.assertEqual(
                replay_payload["verification"]["settlement"],
                payload["verification"]["settlement"],
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["next_count"], 1)

    def test_relative_journal_path_and_pre_dispatch_expiry_fail_closed(self):
        mod = load_module()
        with mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": "relative-state"}), \
             mock.patch.object(mod, "run", side_effect=AssertionError("must not call playerctl")):
            relative = mod.execute(
                "next", "rhythmbox", False, 0.2, operation_id="relative-path"
            )
        self.assertEqual(relative["error"]["code"], "operation_journal_unavailable")

        calls = []
        media_run = make_media_run(["/track/1"], calls)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"AB_APP_CONTROL_OPERATION_DIR": tmp}), \
             mock.patch.object(mod, "run", side_effect=media_run), \
             mock.patch.object(mod.shutil, "which", return_value="/usr/bin/playerctl"), \
             mock.patch.object(
                 mod.time, "time", side_effect=[1000.0, 1061.0, 1061.0]
             ):
            expired = mod.execute(
                "next", "rhythmbox", False, 0.2,
                operation_id="expired-before-dispatch", operation_ttl_secs=60,
            )
        self.assertEqual(expired["error"]["code"], "operation_expired")
        self.assertEqual(expired["transaction"]["dispatch_count"], 0)
        self.assertNotIn(["playerctl", "-p", "rhythmbox", "next"], calls)

    def test_operation_id_scope_format_and_ttl_fail_before_backend(self):
        mod = load_module()
        with mock.patch.object(mod, "run", side_effect=AssertionError("must not call playerctl")):
            invalid_id = mod.execute(
                "next", "rhythmbox", False, 0.2, operation_id="not allowed"
            )
            invalid_ttl = mod.execute(
                "next", "rhythmbox", False, 0.2, operation_id="valid", operation_ttl_secs=59
            )
            wrong_action = mod.execute(
                "pause", "rhythmbox", False, 0.2, operation_id="valid"
            )
            dry_run = mod.execute(
                "next", "rhythmbox", True, 0.2, operation_id="valid"
            )

        self.assertEqual(invalid_id["error"]["code"], "invalid_operation_id")
        self.assertEqual(invalid_ttl["error"]["code"], "invalid_operation_ttl_secs")
        self.assertEqual(wrong_action["error"]["code"], "unsupported_idempotent_operation")
        self.assertEqual(dry_run["error"]["code"], "unsupported_idempotent_operation")


if __name__ == "__main__":
    unittest.main()
