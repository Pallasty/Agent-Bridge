import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/app_control.py"


def load_module():
    spec = importlib.util.spec_from_file_location("app_control_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AppControlTests(unittest.TestCase):
    def test_player_selection_is_exact_then_unique_substring(self):
        mod = load_module()
        players = ["rhythmbox", "spotify.instance42"]
        self.assertEqual(mod.select_player(players, "RHYTHMBOX"), ("rhythmbox", None))
        self.assertEqual(mod.select_player(players, "spotify"), ("spotify.instance42", None))
        self.assertEqual(mod.select_player(players, "missing"), (None, "player_not_found"))

    def test_track_actions_require_identity_change(self):
        mod = load_module()
        before = {"track_id": "one", "artist": "a", "title": "t", "playback_status": "Playing"}
        same = dict(before)
        changed = dict(before, track_id="two")
        self.assertFalse(mod.effect_verified("next", before, same)[0])
        self.assertTrue(mod.effect_verified("next", before, changed)[0])

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
        self.assertEqual(activated["verification"]["predicate"], "playlist_active_with_track")

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

    def test_playlist_current_probes_next_player_after_read_only_getter_failure(self):
        mod = load_module()
        old_run, old_which = mod.run, mod.shutil.which
        def fake_run(argv, env, timeout=2.0):
            if argv == ["playerctl", "-l"]: return 0, "chromium.instance\nrhythmbox", ""
            if argv[0] == "gdbus" and "chromium.instance" in " ".join(argv): return 1, "", "Get failed"
            if argv == ["playerctl", "-p", "rhythmbox", "status"]: return 0, "Paused", ""
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
        self.assertEqual(payload["selection"]["attempts"][0]["status"], "observation_failed")

    def test_control_action_does_not_probe_multiple_players(self):
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
        self.assertEqual(payload["verdict"], "verified")
        self.assertEqual(payload["player"], "chromium.instance")
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


if __name__ == "__main__":
    unittest.main()
