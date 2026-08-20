#!/usr/bin/env python3
"""Bounded MCP runner for one preregistered embodied-media dogfood side.

The runner is orchestration only. Its sole success authority is the versioned
collector module. Raw receipts are written only to a caller-selected private
directory; stdout is always content-free.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import ipaddress
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

RUNNER_SCHEMA = "agent_bridge.embodied_media_episode_runner.v0"
OPERATION_ID_RE = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z", re.ASCII)
COMPANION_PACKAGE = "dev.agentbridge.companion"


def load_collector():
    path = Path(__file__).with_name("embodied-media-episode-dogfood-collector.py")
    spec = importlib.util.spec_from_file_location("embodied_media_episode_collector", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("collector module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collector = load_collector()


class RunnerError(RuntimeError):
    def __init__(self, phase: str, code: str):
        super().__init__(code)
        self.phase = phase
        self.code = code


class StdioMcpClient:
    def __init__(self, binary: Path, env: dict[str, str]):
        self.request_id = 0
        try:
            self.proc = subprocess.Popen(
                [str(binary), "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, env=env,
            )
            self._rpc("initialize", {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "ab-embodied-media-dogfood-runner", "version": "0"},
            })
            self.proc.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}) + "\n")
            self.proc.stdin.flush()
        except (OSError, RunnerError) as error:
            if hasattr(self, "proc") and self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
            if isinstance(error, RunnerError):
                raise
            raise RunnerError("mcp", "mcp_start_failed") from error

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.request_id += 1
        request_id = self.request_id
        self.proc.stdin.write(json.dumps({"jsonrpc":"2.0","id":request_id,"method":method,"params":params}) + "\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RunnerError("mcp", "mcp_eof")
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get("id") == request_id:
                if "error" in response:
                    raise RunnerError("mcp", "json_rpc_error")
                return response

    def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        response = self._rpc("tools/call", {"name": name, "arguments": args})
        result = response.get("result", {})
        blocks = result.get("content", [])
        text = next((item.get("text") for item in blocks if item.get("type") == "text"), None)
        if not isinstance(text, str):
            raise RunnerError(name, "tool_json_missing")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise RunnerError(name, "tool_json_invalid") from error
        if not isinstance(payload, dict):
            raise RunnerError(name, "tool_json_not_object")
        return payload

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=5)


class PrivateReceiptSink:
    def __init__(self, root: Path):
        if not root.is_absolute():
            raise RunnerError("inputs", "receipt_directory_not_absolute")
        try:
            root.mkdir(mode=0o700, parents=False, exist_ok=False)
            os.chmod(root, 0o700)
        except OSError as error:
            raise RunnerError("inputs", "receipt_directory_unavailable") from error
        self.root = root

    def write(self, index: int, tool: str, payload: dict[str, Any]) -> None:
        safe_tool = re.sub(r"[^a-z0-9_]", "_", tool)
        path = self.root / f"{index:02d}-{safe_tool}.json"
        data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                os.write(fd, data)
                os.fsync(fd)
            finally:
                os.close(fd)
            directory_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as error:
            raise RunnerError(tool, "receipt_write_failed") from error


def validate_secure_directory(path: Path) -> None:
    if not path.is_absolute():
        raise RunnerError("inputs", "journal_directory_not_absolute")
    try:
        info = path.lstat()
    except OSError as error:
        raise RunnerError("inputs", "journal_directory_unavailable") from error
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise RunnerError("inputs", "journal_directory_not_owner_only")


def exact_operation_hash(operation_id: str, expected: str) -> None:
    if OPERATION_ID_RE.fullmatch(operation_id) is None:
        raise RunnerError("inputs", "operation_id_invalid")
    actual = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()
    if actual != expected or collector.lowercase_sha256(expected) is False:
        raise RunnerError("inputs", "operation_id_hash_mismatch")


def validate_run_inputs(
    *, pair_id: str, side: str, operation_id: str,
    operation_id_sha256: str, player: str, serial: str, bind: str,
    owner_restatements: int, manual_interventions: int,
) -> None:
    exact_operation_hash(operation_id, operation_id_sha256)
    if not isinstance(pair_id, str) or re.fullmatch(r"embodied-media-pair-[0-9]{2}", pair_id) is None:
        raise RunnerError("inputs", "pair_id_invalid")
    if side not in {"baseline", "trial"}:
        raise RunnerError("inputs", "side_invalid")
    if not isinstance(player, str) or not player or player.strip() != player:
        raise RunnerError("inputs", "player_invalid")
    if not isinstance(serial, str) or not serial or serial.strip() != serial or len(serial) > 256:
        raise RunnerError("inputs", "serial_invalid")
    try:
        ipaddress.ip_address(bind)
    except ValueError as error:
        raise RunnerError("inputs", "bind_invalid") from error
    for value, name in ((owner_restatements, "owner_restatements"), (manual_interventions, "manual_interventions")):
        if not collector.strict_int(value):
            raise RunnerError("inputs", f"{name}_invalid")


def fallback_force_stop(adb: str, serial: str, timeout_secs: float = 10.0) -> bool:
    try:
        result = subprocess.run(
            [adb, "-s", serial, "shell", "am", "force-stop", COMPANION_PACKAGE],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout_secs, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def run_side(
    client: Any,
    *,
    pair_id: str,
    side: str,
    operation_id: str,
    operation_id_sha256: str,
    player: str,
    serial: str,
    bind: str,
    sink: Any,
    owner_restatements: int = 0,
    manual_interventions: int = 0,
    clock: Callable[[], float] = time.monotonic,
    adb_cleanup: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    validate_run_inputs(
        pair_id=pair_id, side=side, operation_id=operation_id,
        operation_id_sha256=operation_id_sha256, player=player,
        serial=serial, bind=bind, owner_restatements=owner_restatements,
        manual_interventions=manual_interventions,
    )
    receipts: list[dict[str, Any]] = []
    session_id: str | None = None
    start_attempted = False
    cleanup_completed = False
    started = clock()

    def call(tool: str, args: dict[str, Any]) -> dict[str, Any]:
        payload = client.call_tool(tool, args)
        receipts.append({"tool": tool, "payload": payload})
        sink.write(len(receipts), tool, payload)
        return payload

    try:
        pending_payload = call("app_control", {
            "domain":"media", "action":"next", "player":player,
            "operation_id":operation_id, "operation_ttl_secs":3600,
            "verify_timeout_secs":0.1, "timeout_ms":30000,
        })
        pending = collector.validate_pending(pending_payload)
        if side == "baseline":
            recovery_payload = call("app_control", {
                "domain":"media", "action":"next", "player":player,
                "operation_id":operation_id, "operation_ttl_secs":3600,
                "verify_timeout_secs":5.0, "timeout_ms":30000,
            })
            recovery = collector.validate_recovery(recovery_payload, pending)
            start_attempted = True
            start = call("mobile_projection_start", {
                "serial":serial, "bind":bind,
                "title":"Agent-Bridge bounded media episode",
                "body":"Verified settled media state", "status":"dogfood baseline",
                "ttl_seconds":120, "auto_connect":True, "timeout_ms":30000,
            })
            session_id = start.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                raise RunnerError("mobile_projection_start", "session_id_missing")
            call("mobile_projection_wait", {"session_id":session_id,"timeout_ms":30000})
            sync = call("mobile_projection_sync_media", {"session_id":session_id,"player":recovery["player"],"timeout_ms":30000})
            revision = sync.get("projection_update", {}).get("revision")
            digest = sync.get("projection_update", {}).get("frame_sha256")
            if not collector.strict_int(revision, 1) or not collector.lowercase_sha256(digest):
                raise RunnerError("mobile_projection_sync_media", "projection_binding_missing")
            call("mobile_projection_wait", {"session_id":session_id,"target_revision":revision,"target_frame_sha256":digest,"timeout_ms":30000})
            call("mobile_projection_stop", {"session_id":session_id,"timeout_ms":30000})
            cleanup_completed = True
            session_id = None
        else:
            episode = call("advance_track_then_project", {
                "operation_id":operation_id, "bind":bind, "serial":serial,
                "player":player, "operation_ttl_secs":3600,
                "verify_timeout_secs":5.0, "projection_ttl_seconds":120,
                "auto_connect":True, "timeout_ms":30000,
            })
            cleanup_completed = episode.get("cleanup", {}).get("verified") is True
        elapsed_ms = max(0, round((clock() - started) * 1000))
        bundle = {
            "schema":collector.INPUT_SCHEMA, "pair_id":pair_id, "side":side,
            "operation_id_sha256":operation_id_sha256, "receipts":receipts,
            "metrics":{
                "owner_restatements":owner_restatements,
                "manual_interventions":manual_interventions,
                "failed_or_replanned_calls":0,
                "elapsed_ms":elapsed_ms,
            },
        }
        return collector.collect(bundle)
    finally:
        if side == "baseline" and not cleanup_completed:
            stopped = False
            if session_id is not None:
                try:
                    stop = call("mobile_projection_stop", {"session_id":session_id,"timeout_ms":30000})
                    stopped = stop.get("adb_force_stop", {}).get("exit_code") == 0
                except Exception:
                    stopped = False
            if (start_attempted or session_id is not None) and not stopped and adb_cleanup is not None:
                adb_cleanup(serial)
        elif side == "trial" and not cleanup_completed and adb_cleanup is not None:
            adb_cleanup(serial)


def rejected(error: RunnerError) -> dict[str, Any]:
    return {
        "schema": RUNNER_SCHEMA, "status":"REJECTED",
        "phase":error.phase, "code":error.code,
        "enrollment_allowed":False, "runtime_influence_allowed":False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--side", choices=("baseline","trial"), required=True)
    parser.add_argument("--pair-id", required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--operation-id-sha256", required=True)
    parser.add_argument("--player", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--bind", required=True)
    parser.add_argument("--binary", type=Path, default=Path.home()/".local/bin/agent-bridge")
    parser.add_argument("--journal-directory", type=Path, required=True)
    parser.add_argument("--private-receipt-directory", type=Path, required=True)
    parser.add_argument("--adb", default=os.environ.get("AGENT_BRIDGE_ADB", "adb"))
    parser.add_argument("--owner-restatements", type=int, default=0)
    parser.add_argument("--manual-interventions", type=int, default=0)
    args = parser.parse_args()
    client = None
    try:
        validate_run_inputs(
            pair_id=args.pair_id, side=args.side, operation_id=args.operation_id,
            operation_id_sha256=args.operation_id_sha256, player=args.player,
            serial=args.serial, bind=args.bind,
            owner_restatements=args.owner_restatements,
            manual_interventions=args.manual_interventions,
        )
        validate_secure_directory(args.journal_directory)
        if not args.binary.is_absolute() or not args.binary.is_file():
            raise RunnerError("inputs", "binary_invalid")
        sink = PrivateReceiptSink(args.private_receipt_directory)
        env = os.environ.copy()
        env["AGENT_BRIDGE_TOOLSET"] = "codex-essential-mobile-projection"
        env["AB_APP_CONTROL_OPERATION_DIR"] = str(args.journal_directory)
        client = StdioMcpClient(args.binary, env)
        result = run_side(
            client, pair_id=args.pair_id, side=args.side,
            operation_id=args.operation_id,
            operation_id_sha256=args.operation_id_sha256,
            player=args.player, serial=args.serial, bind=args.bind, sink=sink,
            owner_restatements=args.owner_restatements,
            manual_interventions=args.manual_interventions,
            adb_cleanup=lambda serial: fallback_force_stop(args.adb, serial),
        )
    except (RunnerError, collector.ContractError) as error:
        if isinstance(error, collector.ContractError):
            error = RunnerError("collector", "collector_contract_rejected")
        result = rejected(error)
        print(json.dumps(result, separators=(",", ":")))
        return 2
    finally:
        if client is not None:
            client.close()
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
