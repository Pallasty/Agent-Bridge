"""Render one local embedded GLB into a reviewed-later PNG with bounded tools.

Requires Linux/POSIX, a trusted Godot binary, and the AB asset_inspect example.
This owns subprocess groups, not a sandbox: escaped sessions and SIGKILL of the
runner are outside its cleanup guarantee. No model or remote service is used.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
import hashlib
import html
import json
import math
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time
from typing import Any, BinaryIO


MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_LOG_BYTES = 1024 * 1024
SIZE = 512
INSPECTION_SCHEMA = "agent_bridge.asset_inspection.v1"


class RecipeError(Exception):
    """A tool or asset failed the fixed recipe contract."""


class RecipeTimeout(RecipeError):
    """The total recipe deadline expired."""


class RecipeCancelled(RecipeError):
    """The owner cancelled this invocation."""


def bounded_file(path: Path, limit: int = MAX_FILE_BYTES) -> bytes:
    """Read one regular non-symlink leaf without blocking on a FIFO."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
            raise RecipeError(f"expected regular file of at most {limit} bytes: {path}")
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise RecipeError(f"file exceeds {limit} bytes: {path}")
    return content


def digest(content: bytes) -> str:
    """Identify exactly the bytes used by this invocation."""
    return hashlib.sha256(content).hexdigest()


def file_identity(path: Path, checkpoint: Callable[[], None]) -> dict[str, Any]:
    """Hash a trusted tool without loading its complete binary into memory."""
    checkpoint()
    hasher = hashlib.sha256()
    count = 0
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise RecipeError(f"tool must be a regular executable: {path}")
        while True:
            checkpoint()
            content = stream.read(1024 * 1024)
            if not content:
                break
            hasher.update(content)
            count += len(content)
    checkpoint()
    return {"path": str(path), "sha256": hasher.hexdigest(), "bytes": count}


class ProcessOwner:
    """Drain capped logs and reclaim only process groups spawned by this run."""

    def __init__(self, root: Path, timeout: float, started: float, report: dict[str, Any]) -> None:
        self.root = root
        self.deadline = started + timeout
        self.cancelled_signal: int | None = None
        self.report = report
        self.selector = selectors.DefaultSelector()
        self.processes: list[subprocess.Popen[bytes]] = []
        self.streams: list[BinaryIO] = []
        self.entries: dict[int, dict[str, Any]] = {}
        self.previous_handlers: dict[int, Any] = {}

    def install_handlers(self) -> None:
        """Defer cancellation until a checkpoint so spawned children stay owned."""
        for number in (signal.SIGINT, signal.SIGTERM):
            self.previous_handlers[number] = signal.signal(number, self.on_signal)

    def on_signal(self, number: int, _frame: Any) -> None:
        self.cancelled_signal = number

    def checkpoint(self) -> None:
        if self.cancelled_signal is not None:
            raise RecipeCancelled(f"cancelled by signal {self.cancelled_signal}")
        if time.monotonic() >= self.deadline:
            raise RecipeTimeout("total wall-clock timeout expired")

    def start(self, label: str, argv: list[str], env: dict[str, str], pass_fds: tuple[int, ...] = ()) -> subprocess.Popen[bytes]:
        """Create one new session and immediately retain its process ownership."""
        self.checkpoint()
        entry: dict[str, Any] = {"label": label, "argv": argv, "returncode": None, "logs": {}}
        self.report["commands"].append(entry)
        process = subprocess.Popen(argv, cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True, pass_fds=pass_fds)
        self.processes.append(process)
        self.entries[process.pid] = entry
        for kind, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            if stream is None:
                raise RecipeError("subprocess pipe unavailable")
            logpath = self.root / "logs" / f"{label}.{kind}.log"
            destination = logpath.open("xb")
            self.streams.append(destination)
            info = {"path": str(logpath), "bytes_seen": 0, "bytes_saved": 0, "truncated": False}
            entry["logs"][kind] = info
            os.set_blocking(stream.fileno(), False)
            self.selector.register(stream, selectors.EVENT_READ, (destination, info))
        return process

    def drain(self, wait: float = .025) -> None:
        """Consume both pipes even after their individual log caps are reached."""
        for key, _mask in self.selector.select(wait):
            stream = key.fileobj
            try:
                content = os.read(stream.fileno(), 65536)
            except BlockingIOError:
                continue
            if not content:
                self.selector.unregister(stream)
                stream.close()
                continue
            destination, info = key.data
            info["bytes_seen"] += len(content)
            saved = content[:max(0, MAX_LOG_BYTES - info["bytes_saved"])]
            destination.write(saved)
            destination.flush()
            info["bytes_saved"] += len(saved)
            info["truncated"] = info["bytes_seen"] > MAX_LOG_BYTES

    @staticmethod
    def exited(process: subprocess.Popen[bytes]) -> bool:
        """Observe exit without reaping the session leader before group cleanup."""
        return os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None

    @staticmethod
    def signal_group(process: subprocess.Popen[bytes], number: int) -> None:
        try:
            os.killpg(process.pid, number)
        except ProcessLookupError:
            pass

    def retire(self, process: subprocess.Popen[bytes]) -> None:
        """TERM, then KILL its group and wait for the direct child (under 1 s grace)."""
        if process not in self.processes:
            return
        self.signal_group(process, signal.SIGTERM)
        until = time.monotonic() + .15
        while time.monotonic() < until:
            self.drain(.01)
        self.signal_group(process, signal.SIGKILL)
        process.wait()
        self.entries[process.pid]["returncode"] = process.returncode
        self.processes.remove(process)
        self.drain(0)

    def run(self, label: str, argv: list[str], env: dict[str, str]) -> bytes:
        """Run one foreground command while applying the shared deadline."""
        process = self.start(label, argv, env)
        try:
            while not self.exited(process):
                self.checkpoint()
                self.drain()
            self.checkpoint()
        finally:
            self.retire(process)
        entry = self.entries[process.pid]
        if process.returncode != 0:
            raise RecipeError(f"{label} exited {process.returncode}; see {label}.stderr.log")
        info = entry["logs"]["stdout"]
        if label.startswith("inspect") and info["truncated"]:
            raise RecipeError(f"{label} JSON exceeds the output limit")
        return Path(info["path"]).read_bytes()

    def close(self) -> None:
        """Reclaim live sessions, close logs, then restore caller signal handlers."""
        for process in list(reversed(self.processes)):
            self.retire(process)
        for key in list(self.selector.get_map().values()):
            key.fileobj.close()
        self.selector.close()
        for stream in self.streams:
            stream.close()
        for number, handler in self.previous_handlers.items():
            signal.signal(number, handler)


def inspect(owner: ProcessOwner, tool: Path, path: Path, content: bytes, fmt: str, env: dict[str, str]) -> dict[str, Any]:
    """Require the AB inspector to confirm the actual snapshot digest and type."""
    raw = owner.run(f"inspect-{fmt}", [str(tool), str(path), digest(content)], env)
    value = json.loads(raw)
    if not isinstance(value, dict) or any((
        value.get("schema") != INSPECTION_SCHEMA,
        value.get("sha256") != digest(content),
        value.get("bytes") != len(content),
        value.get("expected_sha256_matches") is not True,
        value.get("format") != fmt,
    )):
        raise RecipeError(f"{fmt} inspector report does not match the snapshot")
    return value


def start_xvfb(owner: ProcessOwner, binary: Path, env: dict[str, str]) -> str:
    """Ask an owned Xvfb to allocate a private display without a fixed-number race."""
    reader, writer = os.pipe()
    try:
        os.set_blocking(reader, False)
        process = owner.start("xvfb", [str(binary), "-displayfd", str(writer), "-screen", "0", "512x512x24", "-nolisten", "tcp", "-noreset"], env, (writer,))
    finally:
        os.close(writer)
    response = b""
    try:
        while b"\n" not in response:
            owner.checkpoint()
            if owner.exited(process):
                raise RecipeError("Xvfb exited before allocating a display")
            try:
                response += os.read(reader, 32)
            except BlockingIOError:
                pass
            if len(response) > 32:
                raise RecipeError("invalid Xvfb display response")
            owner.drain()
        number = response.strip()
        if not number.isdigit():
            raise RecipeError("invalid Xvfb display number")
        return ":" + number.decode("ascii")
    finally:
        os.close(reader)


def validate_render(receipt: dict[str, Any], inspection: dict[str, Any], input_sha256: str) -> None:
    """Validate technical output only; visual acceptance remains a human step."""
    renderer = receipt.get("renderer")
    if (receipt.get("schema") != "agent_bridge.asset_render.v1"
            or not isinstance(renderer, str) or not renderer.strip() or "dummy" in renderer.lower()
            or not isinstance(receipt.get("godot_version"), str) or not receipt["godot_version"]
            or receipt.get("width") != SIZE or receipt.get("height") != SIZE
            or receipt.get("material_policy") != "neutral_geometry"
            or receipt.get("input_sha256") != input_sha256
            or receipt.get("preview_sha256") != inspection["sha256"]
            or type(receipt.get("mesh_count")) is not int or receipt["mesh_count"] <= 0):
        raise RecipeError("renderer receipt is missing or outside the fixed contract")
    facts = inspection.get("details", {})
    transparent = facts.get("fully_transparent_pixels")
    partial = facts.get("partially_transparent_pixels")
    opaque = facts.get("opaque_pixels")
    if (facts.get("width") != SIZE or facts.get("height") != SIZE or facts.get("has_alpha") is not True
            or any(type(count) is not int or count < 0 for count in (transparent, partial, opaque))
            or transparent + partial + opaque != SIZE * SIZE
            or transparent <= 0 or partial + opaque <= 0):
        raise RecipeError("PNG must be 512x512 with visible pixels and transparent background")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--inspector", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=90)
    parser.add_argument("--xvfb", type=Path)
    parser.add_argument("--xvfb-library-dir", type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.timeout_seconds) or not 0 < args.timeout_seconds <= 3600:
        parser.error("--timeout-seconds must be finite and between 0 and 3600")
    if args.xvfb_library_dir is not None and args.xvfb is None:
        parser.error("--xvfb-library-dir requires --xvfb")
    return args


def publish_report(owner: ProcessOwner, report: dict[str, Any], code: int, started: float) -> int:
    """Commit a complete report after its last cancellation/deadline checkpoint.

    The report is staged while cancellation remains active. Signals are masked
    only across the final pending-signal check and atomic rename. That final
    checkpoint is the completion commit point; later signals do not roll back
    an already completed invocation. This is process-level publication, not a
    filesystem durability or SIGKILL guarantee.
    """
    pending = owner.root / ".report.json.pending"
    preview = owner.root / "preview.html"
    if code:
        preview.unlink(missing_ok=True)
    report["elapsed_seconds"] = round(time.monotonic() - started, 6)
    try:
        pending.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        blocked = {signal.SIGINT, signal.SIGTERM}
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
        try:
            if code == 0:
                for number in sorted(signal.sigpending() & blocked):
                    owner.on_signal(number, None)
                try:
                    owner.checkpoint()
                except RecipeCancelled as error:
                    report.update(status="cancelled", error=str(error))
                    code = 128 + (owner.cancelled_signal or signal.SIGINT)
                except RecipeTimeout as error:
                    report.update(status="timed_out", error=str(error))
                    code = 124
                if code:
                    preview.unlink(missing_ok=True)
                    report["elapsed_seconds"] = round(time.monotonic() - started, 6)
                    pending.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            os.replace(pending, owner.root / "report.json")
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
    except OSError:
        preview.unlink(missing_ok=True)
        raise
    return code


def main() -> int:
    """Keep every run artifact, including failed runs, under a new output root."""
    args = parse_args()
    started = time.monotonic()
    # absolute() preserves a symlink leaf so atomic mkdir rejects it unchanged.
    output = args.output_dir.absolute()
    try:
        output.mkdir(mode=0o700)
    except OSError as error:
        print(f"cannot create a new output directory: {error}", file=sys.stderr)
        return 1
    report: dict[str, Any] = {
        "schema": "agent_bridge.asset_recipe.v1", "status": "failed",
        "visual_quality_reviewed": False, "commands": [], "tools": {}, "scripts": {},
        "limits": {"timeout_seconds": args.timeout_seconds, "file_bytes": MAX_FILE_BYTES,
                   "log_bytes_per_stream": MAX_LOG_BYTES, "width": SIZE, "height": SIZE,
                   "cleanup_scope": "owned process groups; escaped sessions and runner SIGKILL excluded"},
    }
    owner = ProcessOwner(output, args.timeout_seconds, started, report)
    owner.install_handlers()
    code = 1
    try:
        (output / "logs").mkdir()
        env = os.environ.copy()
        for variable, directory in (("HOME", "home"), ("XDG_DATA_HOME", "data"),
                                    ("XDG_CACHE_HOME", "cache"), ("XDG_CONFIG_HOME", "config"),
                                    ("TMPDIR", "tmp")):
            path = output / directory
            path.mkdir(mode=0o700)
            env[variable] = str(path)
        env["LIBGL_ALWAYS_SOFTWARE"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        tools = {"godot": args.godot.resolve(strict=True), "inspector": args.inspector.resolve(strict=True)}
        if args.xvfb:
            tools["xvfb"] = args.xvfb.resolve(strict=True)
        for label, path in tools.items():
            owner.checkpoint()
            if not os.access(path, os.X_OK):
                raise RecipeError(f"tool is not executable: {path}")
            report["tools"][label] = file_identity(path, owner.checkpoint)
        source = bounded_file(args.input)
        snapshot = output / "input.glb"
        snapshot.write_bytes(source)
        report["input"] = {"original_path": str(args.input.absolute()), "snapshot_path": str(snapshot),
                           "sha256": digest(source), "bytes": len(source)}
        report["input_inspection"] = inspect(owner, tools["inspector"], snapshot, source, "glb", env)
        project = output / "project"
        project.mkdir()
        script_root = Path(__file__).resolve().parent
        report["scripts"]["render_glb.py"] = file_identity(Path(__file__).resolve(), owner.checkpoint)
        for name in ("project.godot", "render.gd"):
            content = bounded_file(script_root / "godot" / name)
            (project / name).write_bytes(content)
            report["scripts"][name] = {"sha256": digest(content), "bytes": len(content)}
        if args.xvfb:
            xvfb_env = env.copy()
            if args.xvfb_library_dir:
                library = args.xvfb_library_dir.resolve(strict=True)
                if not library.is_dir():
                    raise RecipeError("Xvfb library directory must be a directory")
                xvfb_env["LD_LIBRARY_PATH"] = str(library)
                report["xvfb_library_dir"] = str(library)
            env["DISPLAY"] = start_xvfb(owner, tools["xvfb"], xvfb_env)
        elif not env.get("DISPLAY"):
            raise RecipeError("DISPLAY is required unless --xvfb provides a private display")
        report["environment"] = {"DISPLAY": env["DISPLAY"], "LIBGL_ALWAYS_SOFTWARE": "1"}
        preview = output / "preview.png"
        rendering = output / "rendering.json"
        owner.run("godot", [str(tools["godot"]), "--path", str(project), "--display-driver", "x11",
                           "--rendering-method", "gl_compatibility", "--rendering-driver", "opengl3",
                           "--audio-driver", "Dummy", "--script", "res://render.gd", "--",
                           str(snapshot), str(preview), str(rendering)], env)
        png = bounded_file(preview)
        inspection = inspect(owner, tools["inspector"], preview, png, "png", env)
        receipt = json.loads(bounded_file(rendering, MAX_LOG_BYTES))
        if not isinstance(receipt, dict):
            raise RecipeError("rendering receipt must be an object")
        validate_render(receipt, inspection, digest(source))
        # Recheck bytes after all tools; a mutation cannot inherit an earlier digest.
        if bounded_file(snapshot) != source or bounded_file(preview) != png:
            raise RecipeError("an inspected asset changed during the recipe")
        report["output"] = {"path": str(preview), "sha256": digest(png), "bytes": len(png)}
        report["output_inspection"] = inspection
        report["rendering"] = receipt
        report["rendering_receipt_sha256"] = digest(bounded_file(rendering, MAX_LOG_BYTES))
        owner.checkpoint()
        for process in list(reversed(owner.processes)):
            owner.retire(process)
        owner.checkpoint()
        # No external resources or scripts: this is a local review artifact.
        (output / "preview.html").write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8"><title>Asset preview</title>'
            '<style>body{font:16px sans-serif;margin:2rem}img{background:repeating-conic-gradient(#ddd 0% 25%,#fff 0% 50%) 0/24px 24px;max-width:100%}</style>'
            '<h1>Rendered; visual review pending</h1><p>Technical checks passed. Visual quality has not been accepted.</p>'
            '<img src="preview.png" width="512" height="512" alt="Rendered GLB preview">'
            f'<p>SHA-256: <code>{html.escape(digest(png))}</code></p><a href="report.json">Technical report</a></html>',
            encoding="utf-8")
        owner.checkpoint()
        report["status"] = "rendered_pending_review"
        code = 0
    except RecipeCancelled as error:
        report.update(status="cancelled", error=str(error))
        code = 128 + (owner.cancelled_signal or signal.SIGINT)
    except RecipeTimeout as error:
        report.update(status="timed_out", error=str(error))
        code = 124
    except (OSError, ValueError, RecipeError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    finally:
        try:
            for process in list(reversed(owner.processes)):
                owner.retire(process)
            code = publish_report(owner, report, code, started)
        finally:
            owner.close()
    if code:
        print(f"{report['status']}: {report.get('error', 'recipe failed')}", file=sys.stderr)
    else:
        print(str(output / "report.json"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
