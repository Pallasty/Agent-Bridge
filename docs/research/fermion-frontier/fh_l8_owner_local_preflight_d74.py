#!/usr/bin/env python3
"""Validate a recorded owner-local preflight observation without admitting it."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
RECORD = HERE / "fh_l8_owner_local_preflight_d74.json"

class D74Error(RuntimeError): pass

def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping): raise D74Error("object required")
    return value

def verify() -> dict[str, Any]:
    value = load(RECORD)
    if value.get("observation_id") != "FH-L8-OWNER-LOCAL-PREFLIGHT-D74-V1": raise D74Error("id drift")
    for name, expected in value["source_pins"].items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected: raise D74Error("source pin drift")
    observed = value["owner_local_observation"]
    if observed["reservation_logical_bytes"] != 3110572064 or observed["filesystem_available_bytes"] < observed["reservation_logical_bytes"] or observed["filesystem_type"] != "f2fs": raise D74Error("observation drift")
    if any(value["authority"].values()): raise D74Error("authority open")
    return {"status": "VERIFIED_D74_OWNER_LOCAL_PREFLIGHT_OBSERVATION", "reservation_logical_bytes": observed["reservation_logical_bytes"], "owner_confirmation_present": False, "decision": value["decision"]}

if __name__ == "__main__": print(json.dumps(verify(), sort_keys=True))
