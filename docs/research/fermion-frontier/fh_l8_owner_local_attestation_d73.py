#!/usr/bin/env python3
"""Validate the single-owner local-attestation workflow without accepting it."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_owner_local_attestation_d73_contract.json"
RESULT = HERE / "fh_l8_owner_local_attestation_d73_result.json"


class D73Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D73Error("object required")
    return value


def validate(contract: Mapping[str, Any]) -> dict[str, Any]:
    if contract.get("contract_id") != "FH-L8-OWNER-LOCAL-ATTESTATION-D73-V1":
        raise D73Error("contract id drift")
    for name, expected in contract["source_pins"].items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected:
            raise D73Error(f"source pin drift: {name}")
    if contract["supersedes_semantics"] != {
        "D67_D72_multi_party_or_external_contact_required": True,
        "replacement": "one_authenticated_project_owner_may_attest_owner_controlled_host_and_resources",
    }:
        raise D73Error("supersession drift")
    if set(contract["owner_local_roles"].values()) != {"project_owner"}:
        raise D73Error("single-owner role drift")
    if len(contract["required_independent_checks"]) != 4:
        raise D73Error("independent-check coverage drift")
    template = contract["owner_attestation_template"]
    if set(template) != {"owner_identity", "attestation_time_utc", "controlled_host_identity", "controlled_scope", "assertion", "owner_confirmation"} or any(template.values()):
        raise D73Error("template must remain blank")
    if contract["state"] != "OWNER_LOCAL_TEMPLATE_UNATTESTED" or any(contract["authority"].values()):
        raise D73Error("authority drift")
    return {
        "status": "VERIFIED_D73_OWNER_LOCAL_ATTESTATION_TEMPLATE",
        "owner_role_count": 1,
        "independent_check_count": 4,
        "owner_attestation_accepted": False,
        "external_contact_required": False,
        "decision": contract["decision"],
    }


def verify() -> dict[str, Any]:
    expected = validate(load(CONTRACT))
    if load(RESULT) != expected:
        raise D73Error("result drift")
    return expected


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
