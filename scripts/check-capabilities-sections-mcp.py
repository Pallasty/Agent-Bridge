#!/usr/bin/env python3
"""Exercise a real MCP server, including its returned follow-up requests.

Default: isolated state and explicit denied browser policy. --host-config uses
the caller's environment and optional installed wrapper, without changing it.
Only initialize, tools/list, and read-only capabilities calls are sent.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time


class Client:
    def __init__(self, command, env, output):
        self.output = output
        self.stderr = (output / "server.stderr.log").open("w")
        self.proc = subprocess.Popen(command, env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.stderr,
                                     text=True, bufsize=1)
        self.rows = queue.Queue()
        self.counter = 0
        self.transcript = []

        def read():
            for line in self.proc.stdout:
                try:
                    self.rows.put(json.loads(line))
                except ValueError:
                    self.rows.put({"invalid_stdout": line})
            self.rows.put(None)

        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def send(self, row):
        self.transcript.append({"direction": "request", "message": row})
        self.proc.stdin.write(json.dumps(row) + "\n")
        self.proc.stdin.flush()

    def request(self, method, params):
        self.counter += 1
        self.send({"jsonrpc": "2.0", "id": self.counter,
                   "method": method, "params": params})
        deadline = time.monotonic() + 45
        while True:
            row = self.rows.get(timeout=max(0.001, deadline - time.monotonic()))
            assert row is not None, "server exited before its response"
            self.transcript.append({"direction": "response", "message": row})
            assert "invalid_stdout" not in row, row
            if row.get("id") == self.counter:
                assert "error" not in row, row
                return row["result"]

    def capability(self, args, error=False):
        result = self.request("tools/call", {"name": "capabilities", "arguments": args})
        assert result.get("isError", False) == error, result
        return json.loads(result["content"][0]["text"])

    def follow(self, hint):
        assert hint["tool"] == "capabilities", hint
        return self.capability(hint["arguments"])

    def close(self):
        self.proc.stdin.close()
        try:
            code = self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
            raise AssertionError("MCP failed to stop after EOF")
        finally:
            self.reader.join(timeout=5)
            self.proc.stdout.close()
            self.stderr.close()
            (self.output / "transcript.json").write_text(
                json.dumps(self.transcript, ensure_ascii=False, indent=2) + "\n")
        assert code == 0, f"MCP exit status {code}"


def exercise(client, isolated):
    checks = []
    init = client.request("initialize", {
        "protocolVersion": "2024-11-05", "capabilities": {},
        "clientInfo": {"name": "capabilities-sections-integration", "version": "1"}})
    assert init["serverInfo"]["name"] == "agent-bridge"
    client.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
    manifest = client.request("tools/list", {})
    tool = next(t for t in manifest["tools"] if t["name"] == "capabilities")
    selector = tool["inputSchema"]["properties"]["sections"]
    names = selector["items"]["enum"]
    assert selector["type"] == "array" and selector["minItems"] == 1
    assert len(names) == len(set(names))
    assert "sections" not in tool["inputSchema"].get("required", [])
    checks.append("tools/list advertises optional sections and valid topic enum")

    full = client.capability({"compact": True, "include_instinct_sessions": False})
    assert set(full) == set(names), "legacy shape or selector enum drift"
    assert "_selection" not in full
    checks.append("legacy response retains all sections without projection metadata")
    selected = client.capability({"compact": True, "sections": ["browser"]})
    required = {"security", "version", "build"}
    assert set(selected) == required | {"browser", "_selection"}
    for name in required | {"browser"}:
        assert selected[name] == full[name], f"changed retained section: {name}"
    if isolated:
        assert selected["security"]["browser"] is False
    checks.append("browser-only response retains complete security and identity values")

    meta = selected["_selection"]
    omitted = set(full) - required - {"browser"}
    assert set(meta["available_sections"]) == set(names)
    assert set(meta["always_included"]) == required
    assert set(meta["omitted_sections"]) == omitted
    assert meta["omission_scope"] == "response_fields_only"
    assert "all existing probes still run" in meta["diagnostics"]
    assert "compact" in meta["nested_omissions"]
    checks.append("omissions are complete, response-only, with nested compact caveats")

    more = client.follow(meta["follow_up"]["omitted_sections"])
    assert set(more) == omitted | required | {"_selection"}
    assert set(more["_selection"]["requested_sections"]) == omitted
    assert (set(selected) | set(more)) - {"_selection"} == set(full)
    assert more["mobile"] == full["mobile"]
    assert more["mobile"]["devices"]["probed"] is False
    assert more["mobile"]["devices"]["status"] == "not_probed"
    if isolated:
        assert more["mobile"]["default_serial"] is None
    recovered = client.follow(meta["follow_up"]["full_response"])
    assert set(recovered) == set(full) and "_selection" not in recovered
    # These sections are stable within this process. Probe timestamps and other
    # live diagnostics elsewhere may legitimately change between MCP calls.
    for name in required | {"browser", "memory"}:
        assert recovered[name] == full[name], name
    checks.append("returned follow-ups restore coverage and retain nested not_probed/false/null")

    for name in names:
        result = client.capability({"compact": True, "sections": [name]})
        assert set(result) == required | {name, "_selection"}, name
        assert result["_selection"]["requested_sections"] == [name]
    checks.append("every advertised topic works through tools/call")
    every = client.capability({"compact": True, "sections": names})
    assert set(every) == set(full) | {"_selection"}
    assert every["_selection"]["omitted_sections"] == []
    assert every["_selection"]["follow_up"]["omitted_sections"] is None
    checks.append("all-topics query has no invalid empty follow-up")
    duplicate = client.capability({"compact": True, "sections": ["browser", "browser"]})
    assert duplicate["_selection"]["requested_sections"] == ["browser"]
    checks.append("duplicate topics deduplicate")

    for bad in [[], None, "browser", [4], ["browzer"], ["browser", "browzer"]]:
        err = client.capability({"sections": bad}, error=True)
        assert err["error"]["code"] in {
            "invalid_capability_sections", "unknown_capability_section"}
        assert set(err["available_sections"]) == set(names)
        assert err["next_call"] == {"tool": "capabilities", "arguments": {"compact": True}}
    repaired = client.follow(err["next_call"])
    assert set(repaired) == set(full)
    checks.append("invalid selectors return MCP tool errors and usable recovery calls")

    # Explicit expanded diagnostics must survive a returned follow-up unchanged.
    detailed = client.capability({"compact": False, "include_instinct_sessions": True,
                                  "sections": ["hooks"]})
    for hint in detailed["_selection"]["follow_up"].values():
        assert hint["arguments"]["compact"] is False
        assert hint["arguments"]["include_instinct_sessions"] is True
    details_full = client.follow(detailed["_selection"]["follow_up"]["full_response"])
    assert set(details_full) == set(full)
    checks.append("expanded diagnostic preferences survive executable follow-up")

    defaulted = client.capability({"sections": ["browser"]})
    default_args = defaulted["_selection"]["follow_up"]["full_response"]["arguments"]
    assert isinstance(default_args["compact"], bool)
    assert default_args["include_instinct_sessions"] == (not default_args["compact"])
    checks.append("omitted detail flags resolve to explicit follow-up preferences")
    before = len(json.dumps(full, ensure_ascii=False, indent=2))
    after = len(json.dumps(selected, ensure_ascii=False, indent=2))
    assert after < before
    return {"status": "PASS", "checks": checks, "check_count": len(checks),
            "build": full["build"], "topics": names,
            "effective_toolset": full["mcp"]["toolset"],
            "effective_tool_profile": full["mcp"]["tool_profile"],
            "embedding_backend": full["memory"]["embedding"]["backend"],
            "full_chars": before, "browser_chars": after,
            "reduction_percent": round(100 * (1 - after / before), 2),
            "limitations": "Each call probes afresh; full value equality across changing diagnostics is not claimed."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", default="codex-essential")
    parser.add_argument("--wrapper", type=Path)
    parser.add_argument("--host-config", action="store_true")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    args.output.mkdir(parents=True, exist_ok=True)
    # State needs real owner/mode semantics for SQLite's existing lock checks.
    # Evidence may live on a FUSE/NTFS mount that cannot provide those semantics.
    with tempfile.TemporaryDirectory(prefix="ab-capabilities-mcp-") as state:
        root = Path(state).resolve()
        if args.host_config:
            env = os.environ.copy()
        else:
            env = {"PATH": "/usr/bin:/bin", "HOME": str(root),
                   "AGENT_BRIDGE_DB": str(root / "state.db"),
                   "AGENT_BRIDGE_STATE_DIR": str(root / "state"),
                   "AGENT_BRIDGE_EMBED_BACKEND": "hash", "AGENT_BRIDGE_HEADLESS": "1",
                   "AGENT_BRIDGE_TERMINAL": "pty", "AB_ALLOW_BROWSER": "false"}
            for kind in ["CONFIG", "DATA", "CACHE", "STATE"]:
                env[f"XDG_{kind}_HOME"] = str(root / kind.lower())
            env["AGENT_BRIDGE_CREDS_FILE"] = str(root / "absent-creds")
        env["AGENT_BRIDGE_TOOLSET"] = args.profile
        env["AGENT_BRIDGE_MAX_BLOCKING_THREADS"] = "32"
        env["AGENT_BRIDGE_REAL_BIN"] = str(binary)
        command = [str(args.wrapper.resolve() if args.wrapper else binary), "mcp"]
        client = Client(command, env, args.output)
        try:
            summary = exercise(client, isolated=not args.host_config)
        finally:
            client.close()
        summary.update(binary=str(binary), binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                       profile=args.profile, host_config=args.host_config,
                       wrapper=str(args.wrapper) if args.wrapper else None,
                       clean_eof_exit=True)
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
