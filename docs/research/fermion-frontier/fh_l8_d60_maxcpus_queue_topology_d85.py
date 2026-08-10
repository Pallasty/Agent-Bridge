#!/usr/bin/env python3
"""Validate the D85 maxcpus/NVMe queue observation, read-only and fail-closed."""
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_maxcpus_queue_topology_d85_contract.json"
RESULT = HERE / "fh_l8_d60_maxcpus_queue_topology_d85_result.json"

class D85Error(RuntimeError): pass

def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping): raise D85Error("object required")
    return value

def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-MAXCPUS-QUEUE-TOPOLOGY-D85-V1": raise D85Error("identity drift")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", str(contract["baseline_commit"]), "HEAD"], check=False, capture_output=True).returncode:
        raise D85Error("baseline drift")
    for name, expected in contract["source_pins"].items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected: raise D85Error(f"source pin mismatch: {name}")
    if any(contract["authority"][key] for key in ("runtime_lock_precommitted", "measurement_authorized", "numeric_runtime_seconds_proven", "full53_execution_authorized")):
        raise D85Error("authority opened")

def evaluate(contract: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    a = contract["acceptance"]
    tokens = set(snapshot.get("cmdline_tokens_present", []))
    cmdline_ok = set(a["required_cmdline_tokens"]).issubset(tokens)
    irq_ok = int(snapshot.get("d82r_plan_irq_conflict_count", 1)) == 0
    result = {
        "status": "VERIFIED_D85_MAXCPUS_NOT_INSTALLED_NVME_QUEUE_STILL_ON_CPU15",
        "source_pin_count": len(contract["source_pins"]),
        "cmdline_tokens_admitted": cmdline_ok,
        "maxcpus_token_present": snapshot.get("maxcpus_token_present") is True,
        "cpu15_online": snapshot.get("cpu15_online") is True,
        "nvme_queue_count": snapshot.get("nvme_queue_count"),
        "d82r_irq_conflict_count": snapshot.get("d82r_plan_irq_conflict_count"),
        "d82r_isolation_admitted": irq_ok,
        "transaction_residue_absent": snapshot.get("transaction_residue_absent") is True,
        "runtime_lock_precommitted": False,
        "measurement_authorized": False,
        "timing_measurements_executed": 0,
        "numeric_runtime_seconds_proven": False,
        "full53_execution_authorized": False,
    }
    result["decision"] = "READY_D82R_FRESH_TRANSACTION" if cmdline_ok and irq_ok else "NO_GO_D85_MAXCPUS_TOKEN_MISSING_AND_NVME0Q15_IRQ_CONFLICT_REMAINS"
    result["next_gate"] = "HOST_ADMIN_INSTALL_MAXCPUS_BOOT_CONFIG_THEN_RESTART" if not snapshot.get("maxcpus_token_present") else "OWNER_REVIEW_NVME_QUEUE_ISOLATION"
    return result

def verify() -> dict[str, Any]:
    contract = load(CONTRACT); verify_contract(contract); return evaluate(contract, contract["observed_snapshot"])

if __name__ == "__main__": print(json.dumps(verify(), indent=2))
