#!/usr/bin/env python3
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-plan-s21b-a9-v0.json"
CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-plan-transcript-contract-s21b-a9-v0.json"
ROLES = ("controller", "observer", "runner", "validator")


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: checker OUTPUT_DIRECTORY")
    output_dir = pathlib.Path(sys.argv[1])
    contract = json.loads(CONTRACT.read_text(encoding="ascii"))
    plan_bytes = PLAN.read_bytes()
    plan = json.loads(plan_bytes)
    assert plan_bytes == canonical_bytes(plan)
    assert len(plan_bytes) == contract["canonical_plan_bytes"] == 371
    digest = hashlib.sha256(plan_bytes).hexdigest()
    assert digest == contract["canonical_plan_sha256"]
    assert plan["allow_device_access"] is False
    assert plan["allow_external_input"] is False
    assert plan["allow_live_execution"] is False
    assert plan["allow_network"] is False
    assert plan["allow_paid_resources"] is False
    assert plan["side_effects_unlocked"] == "NONE"
    assert plan["test_only"] is True

    chain = contract["role_chain"]
    assert [entry["role"] for entry in chain] == list(ROLES)
    for role, expected in zip(ROLES, chain, strict=True):
        raw = (output_dir / f"{role}.json").read_bytes()
        packet = json.loads(raw)
        assert raw == canonical_bytes(packet)
        assert packet["format_id"] == contract["transcript_format_id"]
        assert packet["role"] == role
        assert packet["next_role"] == expected["next_role"]
        assert packet["operation"] == expected["operation"]
        assert packet["state"] == expected["state"]
        assert packet["plan_sha256"] == digest
        assert packet["plan_metadata_read"] is True
        assert packet["real_experiment_input_read"] is False
        assert packet["execution_capability_present"] is False
        assert packet["live_execution_permitted"] is False
        assert packet["side_effects_unlocked"] == "NONE"
        assert packet["test_only"] is True
    print("S21B_A9_DRY_RUN_PLAN_TRANSCRIPT_GATE\tPASS")


if __name__ == "__main__":
    main()
