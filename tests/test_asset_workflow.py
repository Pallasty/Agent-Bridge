"""Recipe contracts exercised through real local subprocesses, without Godot."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/asset_workflow/render_glb.py"

INSPECTOR = r'''#!/usr/bin/env python3
import hashlib, json, os, pathlib, struct, sys
p = pathlib.Path(sys.argv[1]); b = p.read_bytes(); digest = hashlib.sha256(b).hexdigest()
if os.environ.get("INSPECTOR_FAIL") or digest != sys.argv[2]:
    sys.exit("fixture inspector refused input")
if b.startswith(b"glTF"):
    fmt = "glb"; details = {"mesh_count": 1}
elif b.startswith(b"\x89PNG\r\n\x1a\n"):
    fmt = "png"; w, h = struct.unpack(">II", b[16:24])
    details = {"width": w, "height": h, "has_alpha": True,
       "fully_transparent_pixels": w*h-1, "partially_transparent_pixels": 0,
       "opaque_pixels": 1}
    if os.environ.get("RENDER_MODE") == "invisible":
        details["fully_transparent_pixels"] = w*h; details["opaque_pixels"] = 0
else:
    sys.exit("fixture invalid signature")
print(json.dumps({"schema": "agent_bridge.asset_inspection.v1", "path": str(p),
 "bytes": len(b), "sha256": digest, "expected_sha256_matches": True,
 "format": fmt, "details": details, "visual_quality_reviewed": False}))
'''

RENDERER = r'''#!/usr/bin/env python3
import hashlib, json, os, pathlib, signal, struct, subprocess, sys, time, zlib
model, output, receipt = [pathlib.Path(p) for p in sys.argv[sys.argv.index("--")+1:]]
root = output.parent
(root/"renderer.started").write_text("yes")
(root/"renderer.pid").write_text(str(os.getpid()))
mode = os.environ.get("RENDER_MODE", "success")
if mode in ("hang", "child_success"):
    child = subprocess.Popen([sys.executable, "-c", "import os,pathlib,signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); pathlib.Path(" + repr(str(root/"child.pid")) + ").write_text(str(os.getpid())); time.sleep(120)"])
    deadline = time.monotonic()+5
    while not (root/"child.pid").exists() and time.monotonic()<deadline:
        time.sleep(.01)
    (root/"ready").write_text("yes")
    if mode == "hang":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(120)
if mode == "nonzero": sys.exit(7)
if mode == "missing": sys.exit(0)
if mode == "flood":
    sys.stdout.write("x"*2500000); sys.stderr.write("y"*2500000)
size = 256 if mode == "wrong_size" else 512
def chunk(kind, data):
    return struct.pack(">I", len(data))+kind+data+struct.pack(">I", zlib.crc32(kind+data)&0xffffffff)
row = b"\x00" + b"\x80\x90\xa0\x00"*size
png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size,size,8,6,0,0,0)) + chunk(b"IDAT", zlib.compress(row*size)) + chunk(b"IEND", b"")
output.write_bytes(png)
if mode == "missing_receipt": sys.exit(0)
receipt.write_text(json.dumps({"schema": "agent_bridge.asset_render.v1",
 "renderer": "dummy" if mode == "dummy" else "fixture-opengl", "godot_version": "fixture-4.6",
 "width": size, "height": size, "mesh_count": 1,
 "material_policy": "original" if mode == "wrong_material" else "neutral_geometry",
 "input_sha256": "0"*64 if mode == "wrong_input_hash" else hashlib.sha256(model.read_bytes()).hexdigest(),
 "preview_sha256": "0"*64 if mode == "wrong_output_hash" else hashlib.sha256(png).hexdigest()}))
'''

XVFB = r'''#!/usr/bin/env python3
import os, pathlib, sys, time
pathlib.Path("xvfb.pid").write_text(str(os.getpid()))
descriptor = int(sys.argv[sys.argv.index("-displayfd")+1])
os.write(descriptor, b"12345\n"); os.close(descriptor)
time.sleep(120)
'''


class AssetWorkflowTests(unittest.TestCase):
    """The runner owns lifecycle and validation; fixture tools own fake formats."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="ab-asset-recipe-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.model = self.root / "source.glb"
        self.model.write_bytes(b"glTFfixture input")
        self.output = self.root / "run"
        self.inspector = self.root / "inspector"
        self.godot = self.root / "godot"
        self.inspector.write_text(INSPECTOR)
        self.godot.write_text(RENDERER)
        self.inspector.chmod(0o700)
        self.godot.chmod(0o700)
        self.env = dict(os.environ, DISPLAY=":fixture")

    def command(self, timeout: float = 8.0) -> list[str]:
        return [sys.executable, str(RUNNER), "--input", str(self.model),
                "--output-dir", str(self.output), "--godot", str(self.godot),
                "--inspector", str(self.inspector), "--timeout-seconds", str(timeout)]

    def run_recipe(self, mode: str = "success", timeout: float = 8.0) -> subprocess.CompletedProcess[str]:
        return subprocess.run(self.command(timeout), env=dict(self.env, RENDER_MODE=mode),
                              capture_output=True, text=True, timeout=timeout + 5)

    def report(self) -> dict[str, object]:
        self.assertTrue((self.output / "report.json").is_file(), "every created run needs a report")
        return json.loads((self.output / "report.json").read_text())

    def assert_stopped(self, pid: int) -> None:
        end = time.monotonic() + 2
        while time.monotonic() < end:
            try:
                state = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1][0]
            except FileNotFoundError:
                return
            if state == "Z":
                return
            time.sleep(.02)
        self.fail(f"owned process {pid} is still running")

    def test_success_keeps_input_and_binds_report(self) -> None:
        before = self.model.read_bytes()
        result = self.run_recipe()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.report()
        self.assertEqual(report["status"], "rendered_pending_review")
        self.assertIs(report["visual_quality_reviewed"], False)
        self.assertEqual(report["input"]["sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(report["output"]["sha256"], hashlib.sha256((self.output / "preview.png").read_bytes()).hexdigest())
        self.assertEqual(self.model.read_bytes(), before)
        self.assertTrue((self.output / "preview.html").is_file())
        self.assertIn("tools", report)
        self.assertIn("scripts", report)
        self.assertGreaterEqual(len(report["commands"]), 3)

    def test_invalid_input_never_starts_renderer(self) -> None:
        self.model.write_bytes(b"not a model")
        result = self.run_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.report()["status"], "failed")
        self.assertFalse((self.output / "renderer.started").exists())

    def test_existing_output_is_untouched(self) -> None:
        self.output.mkdir()
        marker = self.output / "owner-data"
        marker.write_text("keep")
        result = self.run_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.output.iterdir()), [marker])
        self.assertEqual(marker.read_text(), "keep")

    def test_output_symlink_is_untouched(self) -> None:
        target = self.root / "owner"; target.mkdir()
        self.output.symlink_to(target, target_is_directory=True)
        result = self.run_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.output.is_symlink())
        self.assertEqual(list(target.iterdir()), [])

    def test_renderer_errors_never_claim_success(self) -> None:
        for mode in ("nonzero", "missing", "missing_receipt", "wrong_size", "dummy", "invisible"):
            with self.subTest(mode=mode):
                self.output = self.root / mode
                result = self.run_recipe(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.report()["status"], "failed")
                self.assertFalse((self.output / "preview.html").exists())

    def test_inspector_failure_stops_before_renderer(self) -> None:
        self.env["INSPECTOR_FAIL"] = "1"
        result = self.run_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.report()["status"], "failed")
        self.assertFalse((self.output / "renderer.started").exists())

    def test_receipt_hashes_and_material_policy_are_bound(self) -> None:
        for mode in ("wrong_input_hash", "wrong_output_hash", "wrong_material"):
            with self.subTest(mode=mode):
                self.output = self.root / mode
                result = self.run_recipe(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.report()["status"], "failed")

    def test_private_xvfb_is_allocated_and_cleaned(self) -> None:
        xvfb = self.root / "Xvfb"
        xvfb.write_text(XVFB)
        xvfb.chmod(0o700)
        environment = self.env.copy()
        environment.pop("DISPLAY", None)
        result = subprocess.run(self.command() + ["--xvfb", str(xvfb)], env=environment,
                                capture_output=True, text=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.report()
        self.assertEqual(report["environment"]["DISPLAY"], ":12345")
        self.assert_stopped(int((self.output / "xvfb.pid").read_text()))

    def test_missing_display_stops_before_renderer(self) -> None:
        self.env.pop("DISPLAY", None)
        result = self.run_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.report()["status"], "failed")
        self.assertFalse((self.output / "renderer.started").exists())

    def test_timeout_cleans_parent_and_same_group_child(self) -> None:
        result = self.run_recipe("hang", timeout=1.5)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.report()["status"], "timed_out")
        for name in ("renderer.pid", "child.pid"):
            self.assert_stopped(int((self.output / name).read_text()))

    def test_success_also_cleans_same_group_child(self) -> None:
        result = self.run_recipe("child_success")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_stopped(int((self.output / "child.pid").read_text()))

    def test_cancellation_cleans_parent_and_child(self) -> None:
        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=signum):
                self.output = self.root / f"signal-{signum}"
                process = subprocess.Popen(self.command(), env=dict(self.env, RENDER_MODE="hang"),
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    deadline = time.monotonic() + 5
                    while not (self.output / "ready").exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(.02)
                    self.assertTrue((self.output / "ready").exists(), "child-ready barrier missing")
                    process.send_signal(signum)
                    process.communicate(timeout=3)
                    self.assertNotEqual(process.returncode, 0)
                    self.assertEqual(self.report()["status"], "cancelled")
                    for name in ("renderer.pid", "child.pid"):
                        self.assert_stopped(int((self.output / name).read_text()))
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.communicate()

    def test_logs_are_bounded_without_pipe_deadlock(self) -> None:
        result = self.run_recipe("flood")
        self.assertEqual(result.returncode, 0, result.stderr)
        for logfile in (self.output / "logs").iterdir():
            self.assertLessEqual(logfile.stat().st_size, 1024 * 1024)

    def test_input_symlink_and_fifo_fail_without_hanging(self) -> None:
        for kind in ("symlink", "fifo"):
            with self.subTest(kind=kind):
                self.output = self.root / kind
                source = self.root / (kind + ".glb")
                if kind == "symlink":
                    source.symlink_to(self.model)
                else:
                    os.mkfifo(source)
                original = self.model
                self.model = source
                result = self.run_recipe(timeout=2)
                self.model = original
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.output / "renderer.started").exists())

    def test_executable_fifo_tool_fails_without_waiting_for_a_writer(self) -> None:
        fifo = self.root / "godot-fifo"
        os.mkfifo(fifo, 0o700)
        self.godot = fifo
        process = subprocess.Popen(self.command(.1), env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            try:
                process.communicate(timeout=1.5)
            except subprocess.TimeoutExpired:
                self.fail("executable FIFO tool blocked beyond the deadline and cleanup grace")
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(self.report()["status"], "failed")
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate()

    def test_finalization_observes_cancellation_and_deadline_before_commit(self) -> None:
        # Unit injection pins an otherwise sub-millisecond boundary; tool processes
        # remain real. The broader lifecycle tests deliver actual OS signals.
        specification = importlib.util.spec_from_file_location("asset_recipe_boundary", RUNNER)
        self.assertIsNotNone(specification)
        self.assertIsNotNone(specification.loader)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        original_write = Path.write_text
        original_install = module.ProcessOwner.install_handlers
        original_clock = time.monotonic
        for boundary in ("preview", "report"):
            for event in ("sigint", "sigterm", "deadline"):
                with self.subTest(boundary=boundary, event=event):
                    self.output = self.root / f"final-{boundary}-{event}"
                    captured: list[Any] = []
                    injected = [False]

                    def capture_owner(owner: Any) -> None:
                        captured.append(owner)
                        original_install(owner)

                    def boundary_write(path: Path, text: str, *args: Any, **kwargs: Any) -> int:
                        result = original_write(path, text, *args, **kwargs)
                        is_preview = boundary == "preview" and path.name == "preview.html"
                        is_report = boundary == "report" and path.name in ("report.json", ".report.json.pending")
                        if not injected[0] and (is_preview or is_report):
                            injected[0] = True
                            if event != "deadline":
                                captured[0].on_signal(signal.SIGINT if event == "sigint" else signal.SIGTERM, None)
                        return result

                    def boundary_clock() -> float:
                        return original_clock() + (20 if injected[0] and event == "deadline" else 0)

                    with (patch.object(module.ProcessOwner, "install_handlers", capture_owner),
                          patch.object(Path, "write_text", boundary_write),
                          patch.object(module.time, "monotonic", boundary_clock),
                          patch.object(sys, "argv", self.command()[1:]),
                          patch.dict(os.environ, self.env, clear=True),
                          redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
                        code = module.main()
                    self.assertTrue(injected[0], "finalization boundary was not reached")
                    self.assertNotEqual(code, 0)
                    self.assertEqual(self.report()["status"], "timed_out" if event == "deadline" else "cancelled")
                    self.assertFalse((self.output / "preview.html").exists())


if __name__ == "__main__":
    unittest.main()
