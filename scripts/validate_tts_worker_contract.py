#!/usr/bin/env python3
"""Read-only validator for the AB TTS Worker v1 Unix-socket contract."""
import argparse
import json
import socket
import sys
from pathlib import Path

PROTOCOL = "ab.tts.worker.v1"


def request(socket_path, payload, timeout_s):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout_s)
    try:
        client.connect(socket_path)
        client.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        raw = bytearray()
        while len(raw) < 65536:
            chunk = client.recv(4096)
            if not chunk:
                break
            raw.extend(chunk)
            if b"\n" in chunk:
                break
        if not raw:
            raise RuntimeError("worker returned no JSON receipt")
        return json.loads(raw.split(b"\n", 1)[0].decode("utf-8"))
    finally:
        client.close()


def validate_health(receipt, expected_engine=None, required_capabilities=()):
    """Return fail-closed contract violations for a health receipt."""
    errors = []
    if receipt.get("protocol") != PROTOCOL:
        errors.append(f"protocol must be {PROTOCOL!r}")
    if receipt.get("ok") is not True or receipt.get("state") != "ready":
        errors.append("worker is not ready")
    for field in ("engine", "model", "device", "dtype"):
        value = receipt.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"missing non-empty {field}")
    capabilities = receipt.get("capabilities")
    if not isinstance(capabilities, list) or any(not isinstance(x, str) for x in capabilities):
        errors.append("capabilities must be a string array")
        capabilities = []
    if expected_engine and receipt.get("engine") != expected_engine:
        errors.append(f"engine must be {expected_engine!r}, got {receipt.get('engine')!r}")
    missing = [x for x in required_capabilities if x not in capabilities]
    if missing:
        errors.append("missing capabilities: " + ", ".join(missing))
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description="validate AB TTS Worker v1")
    ap.add_argument("--socket", required=True)
    ap.add_argument("--expected-engine")
    ap.add_argument("--require-capability", action="append", default=[], dest="capabilities")
    ap.add_argument("--text")
    ap.add_argument("--output")
    ap.add_argument("--speaker", default="Serena")
    ap.add_argument("--instruct", default="")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args(argv)
    timeout_s = max(1.0, min(args.timeout, 600.0))
    try:
        health = request(args.socket, {"op": "health"}, timeout_s)
        errors = validate_health(health, args.expected_engine, args.capabilities)
        result = {"ok": not errors, "protocol": PROTOCOL, "health": health}
        if errors:
            result["errors"] = errors
        if args.text is not None:
            if not args.output:
                raise ValueError("--output is required with --text")
            output = Path(args.output)
            if not output.is_absolute():
                raise ValueError("--output must be an absolute path")
            if errors:
                result["synth_skipped"] = "health contract failed"
            else:
                receipt = request(args.socket, {"op": "synthesize", "text": args.text,
                    "output": str(output), "speaker": args.speaker, "instruct": args.instruct}, timeout_s)
                result["synth"] = receipt
                if receipt.get("ok") is not True or not output.is_file() or output.stat().st_size == 0:
                    result["ok"] = False
                    result.setdefault("errors", []).append("synth receipt/file check failed")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 2
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "protocol": PROTOCOL, "errors": [str(exc)]}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
