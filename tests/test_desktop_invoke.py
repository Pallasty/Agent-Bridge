import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
SCRIPT = SCRIPT_DIR / "desktop_invoke.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        spec = importlib.util.spec_from_file_location("desktop_invoke_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class DesktopInvokeTests(unittest.TestCase):
    def test_main_hydrates_session_env_before_selector_resolution(self):
        mod = load_module()
        hydrated = []
        mod.hydrate_linux_session_env = lambda: hydrated.append(True)

        stdout = io.StringIO()
        with mock.patch.object(
            sys, "argv", [str(SCRIPT)]
        ), contextlib.redirect_stdout(stdout):
            rc = mod.main()

        self.assertEqual(rc, 2)
        self.assertEqual(hydrated, [True])
        self.assertEqual(
            json.loads(stdout.getvalue())["error"],
            "no selector: pass at least one of --app/--role/--name",
        )


if __name__ == "__main__":
    unittest.main()
