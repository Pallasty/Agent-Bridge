#!/usr/bin/env python3
"""Capture a fresh D82 receipt from inside the exact isolated service cgroup."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
D82_PATH = HERE / "fh_l8_d60_owner_policy_isolation_d82.py"
DEFAULT_OUTPUT = Path("/Data/CascadeProjects/.ab-evidence/fh-l8-d82-isolation-receipt.json")


class D82ReceiptError(RuntimeError):
    pass


def load_d82():
    spec = importlib.util.spec_from_file_location("fh_l8_d82_capture_target", D82_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def build_receipt(d82: Any) -> dict[str, Any]:
    contract = d82.load(d82.CONTRACT)
    d82.verify_contract(contract)
    snapshot = d82.current_isolation_snapshot(contract["load_isolation_requirement"])
    result = d82.build_result(contract, snapshot)
    if result["load_isolation_admitted"] is not True:
        raise D82ReceiptError(
            "isolation not admitted: " + ",".join(result["load_isolation_failed_predicates"])
        )
    source_commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "receipt_id": "FH-L8-D82-FRESH-ISOLATION-RECEIPT-V1",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit,
        "d82_contract_sha256": hashlib.sha256(d82.CONTRACT.read_bytes()).hexdigest(),
        "capture_process_pid": os.getpid(),
        "result": result,
    }


def write_exclusive(path: Path, receipt: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise D82ReceiptError(f"receipt already exists: {path}")
    fd, temp_name = tempfile.mkstemp(prefix=".fh-l8-d82-receipt-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temp_name, path)
    finally:
        try:
            Path(temp_name).unlink()
        except FileNotFoundError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    receipt = build_receipt(load_d82())
    write_exclusive(args.output, receipt)
    print(json.dumps({"status": "CAPTURED", "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
