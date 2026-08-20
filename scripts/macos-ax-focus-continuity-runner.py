#!/usr/bin/env python3
"""Private at-most-once runner for the preregistered macOS focus episode."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import time
from pathlib import Path
from typing import Any, Callable


OPERATION_ID_RE = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z", re.ASCII)
FAULT = "registered_response_loss_after_focus_return"


def _load_collector():
    path = Path(__file__).with_name("macos-ax-focus-continuity-collector.py")
    spec = importlib.util.spec_from_file_location("macos_ax_focus_continuity_collector", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("collector unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collector = _load_collector()


class RunnerError(RuntimeError):
    def __init__(self, code: str, recover: str = "replan"):
        super().__init__(code)
        self.code = code
        self.recover = recover


def _strict_int(value: Any, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def canonical_request(operation_id: str, target: dict[str, Any], ttl_secs: int) -> dict[str, Any]:
    if OPERATION_ID_RE.fullmatch(operation_id) is None:
        raise RunnerError("operation_id_invalid")
    if not _strict_int(ttl_secs, 60) or ttl_secs > 86_400:
        raise RunnerError("operation_ttl_invalid")
    if (
        not _strict_int(target.get("pid"), 1)
        or not isinstance(target.get("bundle_id"), str)
        or not target["bundle_id"]
        or target["bundle_id"].strip() != target["bundle_id"]
        or not isinstance(target.get("ax_identifier"), str)
        or not target["ax_identifier"]
        or target["ax_identifier"].strip() != target["ax_identifier"]
        or not isinstance(target.get("expected_role"), str)
        or not target["expected_role"]
        or target["expected_role"].strip() != target["expected_role"]
        or (
            target.get("expected_title") is not None
            and not isinstance(target.get("expected_title"), str)
        )
    ):
        raise RunnerError("target_invalid")
    return {
        "schema": "agent_bridge.macos_ax_focus_continuity_request.v0",
        "operation": "focus_window",
        "operation_id": operation_id,
        "operation_ttl_secs": ttl_secs,
        "target": target,
    }


class OperationJournal:
    def __init__(self, root: Path, operation_id: str):
        if not root.is_absolute():
            raise RunnerError("journal_directory_not_absolute")
        try:
            info = root.lstat()
        except OSError as error:
            raise RunnerError("journal_directory_unavailable") from error
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise RunnerError("journal_directory_not_owner_only")
        key = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()
        self.root = root
        self.record_path = root / f"{key}.json"
        self.lock_path = root / f"{key}.lock"
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        self.lock_fd = os.open(self.lock_path, flags, 0o600)
        lock_info = os.fstat(self.lock_fd)
        if (
            not stat.S_ISREG(lock_info.st_mode)
            or lock_info.st_uid != os.getuid()
            or stat.S_IMODE(lock_info.st_mode) != 0o600
        ):
            os.close(self.lock_fd)
            raise RunnerError("operation_lock_unsafe")
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            os.close(self.lock_fd)
            raise RunnerError("operation_lock_busy", "retry") from error

    def close(self) -> None:
        if getattr(self, "lock_fd", -1) >= 0:
            fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            os.close(self.lock_fd)
            self.lock_fd = -1

    def read(self) -> dict[str, Any] | None:
        try:
            fd = os.open(self.record_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except FileNotFoundError:
            return None
        except OSError as error:
            raise RunnerError("operation_record_unavailable") from error
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > 262_144
            ):
                raise RunnerError("operation_record_unsafe")
            raw = os.read(fd, 262_145)
        finally:
            os.close(fd)
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RunnerError("operation_record_invalid") from error
        if not isinstance(value, dict):
            raise RunnerError("operation_record_invalid")
        return value

    def write(self, value: dict[str, Any]) -> None:
        data = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        temp = self.root / f".{self.record_path.name}.{os.getpid()}.tmp"
        fd = os.open(
            temp,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            written = 0
            while written < len(data):
                count = os.write(fd, data[written:])
                if count <= 0:
                    raise OSError("short operation journal write")
                written += count
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temp, self.record_path)
        directory_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)


def _record_valid(record: dict[str, Any], request: dict[str, Any]) -> bool:
    base = (
        record.get("schema") == collector.JOURNAL_SCHEMA
        and record.get("request") == request
        and record.get("request_sha256") == collector.canonical_sha256(request)
        and record.get("phase") in {"prepared", "dispatch_started", "terminal"}
        and _strict_int(record.get("dispatch_count"))
        and record["dispatch_count"] <= 1
        and isinstance(record.get("created_at"), (int, float))
        and not isinstance(record.get("created_at"), bool)
        and isinstance(record.get("expires_at"), (int, float))
        and not isinstance(record.get("expires_at"), bool)
        and record["expires_at"] > record["created_at"]
    )
    if not base:
        return False
    phase = record["phase"]
    if phase == "prepared":
        return record["dispatch_count"] == 0 and "receipt" not in record
    if phase == "dispatch_started":
        return (
            record["dispatch_count"] == 1
            and isinstance(record.get("dispatch_started_at"), (int, float))
            and not isinstance(record.get("dispatch_started_at"), bool)
            and record["dispatch_started_at"] >= record["created_at"]
            and "receipt" not in record
        )
    if phase == "terminal":
        return record["dispatch_count"] == 1 and isinstance(record.get("receipt"), dict)
    return False


def _result(status: str, request: dict[str, Any], **values: Any) -> dict[str, Any]:
    result = {
        "schema": collector.SCHEMA,
        "status": status,
        "operation_id": request["operation_id"],
        "request_sha256": collector.canonical_sha256(request),
        "new_runtime_authority_granted": False,
        "cross_app_activation_performed": False,
        "content_mutation_performed": False,
    }
    result.update(values)
    return result


def run_episode(
    client: Any,
    *,
    operation_id: str,
    target: dict[str, Any],
    journal_directory: Path,
    operation_ttl_secs: int = 3600,
    fault_injection: str | None = None,
    clock: Callable[[], float] = time.time,
) -> dict[str, Any]:
    request = canonical_request(operation_id, target, operation_ttl_secs)
    if fault_injection not in {None, FAULT}:
        raise RunnerError("fault_injection_invalid")
    journal = OperationJournal(journal_directory, operation_id)
    lease_id: str | None = None
    try:
        now = clock()
        record = journal.read()
        resume_prepared = False
        if record is not None:
            if not _record_valid(record, request):
                raise RunnerError("operation_record_invalid_or_conflicting")
            if now >= record["expires_at"]:
                raise RunnerError("operation_expired")
            if record["phase"] == "terminal":
                receipt = record.get("receipt")
                try:
                    collector.validate_terminal_receipt(receipt, request)
                except collector.ContractError as error:
                    raise RunnerError("terminal_receipt_invalid") from error
                replay = dict(receipt)
                replay["idempotent_replay"] = True
                replay["external_execution_repeated"] = False
                replay["focus_dispatch_invoked_in_originating_call"] = receipt[
                    "focus_dispatch_invoked_in_this_call"
                ]
                replay["focus_dispatch_invoked_in_this_call"] = False
                return replay
            if record["phase"] == "dispatch_started":
                if record["dispatch_count"] != 1:
                    raise RunnerError("operation_record_invalid")
                verify_args = {
                    "expect": "window_focused",
                    "bundle_id": target["bundle_id"],
                    "pid": target["pid"],
                    "ax_identifier": target["ax_identifier"],
                    "role": target["expected_role"],
                    "max_windows": 50,
                    "poll_timeout_secs": 2.0,
                    "poll_interval_secs": 0.05,
                    "semantic_bus": True,
                    "semantic_include_raw": False,
                    "timeout_ms": 7000,
                }
                if target.get("expected_title") is not None:
                    verify_args["title"] = target["expected_title"]
                verification = client.call_tool("macos_ax_verify", verify_args)
                try:
                    collector.validate_recovery(verification, target)
                except collector.ContractError:
                    return _result(
                        "reobserve",
                        request,
                        phase="dispatch_started",
                        dispatch_count=1,
                        recover="reobserve",
                        redispatched=False,
                        focus_dispatch_invoked_in_this_call=False,
                        contract_bound_dispatch_count=1,
                        causal_attribution="unknown_after_interruption",
                    )
                receipt = _result(
                    "verified",
                    request,
                    phase="terminal",
                    dispatch_count=1,
                    recover="proceed",
                    recovered_after_interruption=True,
                    causal_attribution="unknown_after_interruption",
                    redispatched=False,
                    focus_dispatch_invoked_in_this_call=False,
                    contract_bound_dispatch_count=1,
                    idempotent_replay=False,
                    external_execution_repeated=False,
                    verification_sha256=collector.canonical_sha256(verification),
                )
                record["phase"] = "terminal"
                record["receipt"] = receipt
                record["terminal_at"] = clock()
                journal.write(record)
                return receipt
            if record["phase"] == "prepared" and record["dispatch_count"] == 0:
                resume_prepared = True
            else:
                raise RunnerError("operation_record_invalid")

        probe = client.call_tool("macos_ax_probe", {"max_windows": 50, "jxa_timeout_secs": 2.0})
        probe_evidence = collector.validate_probe(probe, target)
        admission = client.call_tool(
            "macos_ax_action_admission",
            {
                "operation": "focus_window",
                "authority_scope": "owner_standing",
                "target": target,
                "surface_receipt": probe,
                "max_observation_age_ms": 5000,
                "task_intent_bound": False,
                "requested_effect": "local_navigation",
            },
        )
        collector.validate_admission(admission)
        created_at = clock()
        if not resume_prepared:
            record = {
                "schema": collector.JOURNAL_SCHEMA,
                "request": request,
                "request_sha256": collector.canonical_sha256(request),
                "created_at": created_at,
                "expires_at": created_at + operation_ttl_secs,
                "phase": "prepared",
                "dispatch_count": 0,
                "probe_sha256": probe_evidence["probe_sha256"],
            }
            journal.write(record)
        else:
            record["probe_sha256"] = probe_evidence["probe_sha256"]
        lease = client.call_tool("embodiment_lease", {"op": "acquire"})
        lease_id = lease.get("lease_id")
        if (
            lease.get("schema") != "agent_bridge.embodiment_lease.v0"
            or lease.get("op") != "acquire"
            or lease.get("acquired") is not True
            or not isinstance(lease_id, str)
            or not lease_id
        ):
            lease_id = None
            raise RunnerError("lease_acquire_failed")
        if clock() >= record["expires_at"]:
            released = client.call_tool("embodiment_lease", {"op": "release", "lease_id": lease_id})
            if released.get("released") is not True:
                raise RunnerError("lease_cleanup_not_verified", "reobserve")
            lease_id = None
            raise RunnerError("operation_expired")
        record["phase"] = "dispatch_started"
        record["dispatch_count"] = 1
        record["dispatch_started_at"] = clock()
        journal.write(record)
        focus_args = dict(target)
        focus_args["embodiment_lease_id"] = lease_id
        focus = client.call_tool("macos_ax_focus_transaction", focus_args)
        released = client.call_tool("embodiment_lease", {"op": "release", "lease_id": lease_id})
        if (
            released.get("schema") != "agent_bridge.embodiment_lease.v0"
            or released.get("op") != "release"
            or released.get("lease_id") != lease_id
            or released.get("released") is not True
        ):
            raise RunnerError("lease_cleanup_not_verified", "reobserve")
        lease_id = None
        if fault_injection == FAULT:
            return _result(
                "response_lost",
                request,
                phase="dispatch_started",
                dispatch_count=1,
                recover="retry",
                registered_fault=FAULT,
                redispatched=False,
                focus_dispatch_invoked_in_this_call=True,
                contract_bound_dispatch_count=1,
            )
        collector.validate_focus(focus, target)
        receipt = _result(
            "verified",
            request,
            phase="terminal",
            dispatch_count=1,
            recover="proceed",
            recovered_after_interruption=False,
            causal_attribution="fresh_verified_transaction",
            redispatched=False,
            focus_dispatch_invoked_in_this_call=True,
            contract_bound_dispatch_count=1,
            idempotent_replay=False,
            external_execution_repeated=False,
            focus_transaction_sha256=collector.canonical_sha256(focus),
        )
        record["phase"] = "terminal"
        record["receipt"] = receipt
        record["terminal_at"] = clock()
        journal.write(record)
        return receipt
    except collector.ContractError as error:
        raise RunnerError(str(error), "reobserve") from error
    finally:
        if lease_id is not None:
            try:
                client.call_tool("embodiment_lease", {"op": "release", "lease_id": lease_id})
            except Exception:
                pass
        journal.close()


class StdioMcpClient:
    def __init__(self, binary: Path):
        env = os.environ.copy()
        env["AGENT_BRIDGE_TOOLSET"] = "codex-essential"
        self.request_id = 0
        self.proc = subprocess.Popen(
            [str(binary), "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, env=env,
        )
        self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "ab-macos-focus-continuity", "version": "0"}})
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.proc.stdin.flush()

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.request_id += 1
        request_id = self.request_id
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RunnerError("mcp_eof")
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get("id") == request_id:
                if "error" in response:
                    raise RunnerError("mcp_error")
                return response

    def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        result = self._rpc("tools/call", {"name": name, "arguments": args}).get("result", {})
        text = next((block.get("text") for block in result.get("content", []) if block.get("type") == "text"), None)
        if not isinstance(text, str):
            raise RunnerError("tool_json_missing")
        value = json.loads(text)
        if not isinstance(value, dict):
            raise RunnerError("tool_json_invalid")
        return value

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--ax-identifier", required=True)
    parser.add_argument("--expected-role", default="AXWindow")
    parser.add_argument("--expected-title")
    parser.add_argument("--operation-ttl-secs", type=int, default=3600)
    parser.add_argument("--journal-directory", type=Path, required=True)
    parser.add_argument("--binary", type=Path, default=Path.home() / ".local/bin/agent-bridge")
    parser.add_argument("--fault-injection", choices=(FAULT,))
    args = parser.parse_args()
    target = {"pid": args.pid, "bundle_id": args.bundle_id, "ax_identifier": args.ax_identifier, "expected_role": args.expected_role}
    if args.expected_title is not None:
        target["expected_title"] = args.expected_title
    client = None
    try:
        if not args.binary.is_absolute() or not args.binary.is_file():
            raise RunnerError("binary_invalid")
        client = StdioMcpClient(args.binary)
        result = run_episode(client, operation_id=args.operation_id, target=target, journal_directory=args.journal_directory, operation_ttl_secs=args.operation_ttl_secs, fault_injection=args.fault_injection)
    except RunnerError as error:
        result = {"schema": collector.SCHEMA, "status": "error", "error": {"code": error.code}, "recover": error.recover, "new_runtime_authority_granted": False}
        print(json.dumps(result, separators=(",", ":")))
        return 2
    finally:
        if client is not None:
            client.close()
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
