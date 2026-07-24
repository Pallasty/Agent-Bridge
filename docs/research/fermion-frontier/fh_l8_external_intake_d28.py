#!/usr/bin/env python3
"""D28 fail-closed intake preflight. Signature verification is external-key bound."""
from __future__ import annotations

import hashlib
from pathlib import Path

REQUIRED = ("approval.json", "approval.ed25519.sig", "approval-public-key.pem", "resource-receipt.json", "resource-receipt.ed25519.sig", "resource-public-key.pem")


class IntakeError(ValueError):
    pass


def preflight(bundle: Path) -> dict:
    bundle = Path(bundle)
    missing = [name for name in REQUIRED if not (bundle / name).is_file()]
    if missing:
        return {"status": "NO_GO_D28_EXTERNAL_SIGNED_BUNDLE_ABSENT", "missing": missing,
                "bundle_admissible": False, "scientific_action_calls": 0,
                "full_53_scientific_execution_authorized": False,
                "next_gate": "INDEPENDENT_ED25519_SIGNED_APPROVAL_AND_RESOURCE_RECEIPT"}
    # This gate only admits an immutable handoff to a dedicated verifier. It
    # deliberately does not attempt to interpret unsigned JSON as authority.
    digests = {name: hashlib.sha256((bundle / name).read_bytes()).hexdigest() for name in REQUIRED}
    return {"status": "D28_BUNDLE_PRESENT_REQUIRES_DEDICATED_SIGNATURE_VERIFIER", "missing": [],
            "bundle_admissible": False, "sha256": digests, "scientific_action_calls": 0,
            "full_53_scientific_execution_authorized": False,
            "next_gate": "INDEPENDENT_ED25519_SIGNED_APPROVAL_AND_RESOURCE_RECEIPT"}
