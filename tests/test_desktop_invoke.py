import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import types
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

    @staticmethod
    def fake_atspi(children):
        class Node:
            def __init__(self, role, name="", children=None, pid=None):
                self.role = role
                self.name = name
                self.children = list(children or [])
                self.pid = pid

            def getRoleName(self):
                return self.role

            def getRole(self):
                return 0 if self.role == "application" else 1

            @property
            def childCount(self):
                return len(self.children)

            def getChildAtIndex(self, index):
                return self.children[index]

            def get_process_id(self):
                return self.pid

        app = Node("application", "large-app", children, 4242)
        desktop = Node("desktop", children=[app])
        module = types.SimpleNamespace(
            ROLE_APPLICATION=0,
            Registry=types.SimpleNamespace(getDesktop=lambda _index: desktop),
        )
        return Node, module

    def test_bounded_finder_stops_at_exact_nth_without_visiting_tail(self):
        mod = load_module()
        Node, pyatspi = self.fake_atspi([])

        class Poison(Node):
            def getRoleName(self):
                raise AssertionError("tail must not be visited after nth target")

        first = Node("button", "first")
        _Node, pyatspi = self.fake_atspi([first, Poison("label")])
        with mock.patch.dict(sys.modules, {"pyatspi": pyatspi}):
            node, app, pid, coverage = mod.find_element(
                "large", "button", None, 0, search_budget=1.0
            )
        self.assertIs(node, first)
        self.assertEqual((app, pid), ("large-app", 4242))
        self.assertEqual(coverage["stop_reason"], "target_found")
        self.assertLessEqual(coverage["visited_nodes"], 2)

    def test_bounded_finder_honors_nth_and_never_falls_back(self):
        mod = load_module()
        Node, pyatspi = self.fake_atspi([])
        first = Node("button", "first")
        second = Node("button", "second")
        _Node, pyatspi = self.fake_atspi([first, second])
        with mock.patch.dict(sys.modules, {"pyatspi": pyatspi}):
            node, _app, _pid, coverage = mod.find_element("large", "button", None, 1)
            missing, _app, _pid, absent = mod.find_element("large", "button", None, 9)
        self.assertIs(node, second)
        self.assertEqual(coverage["matched_before_target"], 1)
        self.assertIsNone(missing)
        self.assertTrue(absent["complete"])
        self.assertEqual(absent["stop_reason"], "registry_exhausted")

    def test_bounded_finder_reports_incomplete_instead_of_absent(self):
        mod = load_module()
        Node, pyatspi = self.fake_atspi([])
        _Node, pyatspi = self.fake_atspi([Node("label", str(i)) for i in range(20)])
        with mock.patch.dict(sys.modules, {"pyatspi": pyatspi}):
            node, _app, _pid, coverage = mod.find_element(
                "large", "button", None, 0, max_nodes=3
            )
        self.assertIsNone(node)
        self.assertFalse(coverage["complete"])
        self.assertEqual(coverage["stop_reason"], "node_budget")

    def test_bounded_finder_reports_deep_tree_as_incomplete(self):
        mod = load_module()
        Node, _pyatspi = self.fake_atspi([])
        branch = Node("button", "too-deep")
        for depth in range(8):
            branch = Node("panel", f"level-{depth}", [branch])
        _Node, pyatspi = self.fake_atspi([branch])
        with mock.patch.dict(sys.modules, {"pyatspi": pyatspi}):
            node, _app, _pid, coverage = mod.find_element(
                "large", "button", None, 0, max_depth=3
            )
        self.assertIsNone(node)
        self.assertFalse(coverage["complete"])
        self.assertEqual(coverage["stop_reason"], "depth_budget")


if __name__ == "__main__":
    unittest.main()
