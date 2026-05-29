import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/desktop_snapshot.py"


def load_module():
    spec = importlib.util.spec_from_file_location("desktop_snapshot_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DesktopSnapshotTests(unittest.TestCase):
    def test_swaymsg_uses_resolved_swaysock_env(self):
        mod = load_module()
        seen = {}

        def fake_which(name):
            return "/usr/bin/swaymsg" if name == "swaymsg" else None

        def fake_run(cmd, timeout=8.0, env=None):
            seen["cmd"] = cmd
            seen["timeout"] = timeout
            seen["env"] = env
            return 0, "[]", ""

        old_which = mod.shutil.which
        old_run = mod._run
        try:
            mod.shutil.which = fake_which
            mod._run = fake_run

            self.assertEqual(mod._swaymsg("get_outputs", {"SWAYSOCK": "/tmp/sway.sock"}), [])
        finally:
            mod.shutil.which = old_which
            mod._run = old_run

        self.assertEqual(seen["cmd"], ["swaymsg", "-t", "get_outputs", "-r"])
        self.assertEqual(seen["timeout"], 6.0)
        self.assertIsNotNone(seen["env"])
        self.assertEqual(seen["env"]["SWAYSOCK"], "/tmp/sway.sock")


if __name__ == "__main__":
    unittest.main()
