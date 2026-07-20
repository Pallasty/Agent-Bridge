#!/usr/bin/env python3
"""Fail-closed checker for the non-live S21B-A2 subject-rebinding review."""
from __future__ import annotations

import argparse, copy, hashlib, json, struct
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[2]
PFX = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-subject-rebinding"
CONTRACT = ROOT / f"{PFX}-contract-s21b-a2-v0.json"
SCHEMA = ROOT / f"{PFX}-schema-s21b-a2-v0.json"
FIXTURE = ROOT / f"{PFX}-synthetic-s21b-a2-v0.json"
STATUS = ROOT / f"{PFX}-status-s21b-a2-v0.json"
SUCCESSOR = ROOT / f"{PFX}-successor-gate-s21b-a2-v0.json"
LEGACY = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-final-refreeze-subject-synthetic-s21a-v0.json"
DOMAIN = b"agent-bridge/biocortex/owned-lab/s21b-a2/unsigned-subject-rebinding-review/v1"


def fail(message: str) -> None:
    raise AssertionError(message)


def nodup(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate key: {key}")
        result[key] = value
    return result


def load(path: Path):
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or not raw[:-1].isascii():
        fail(f"noncanonical file: {path}")
    value = json.loads(raw[:-1], object_pairs_hook=nodup, parse_float=lambda _: fail("float"))
    canonical = json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")
    if raw != canonical + b"\n":
        fail(f"noncanonical json: {path}")
    return value, raw


def digest(value: dict) -> str:
    payload = dict(value)
    claimed = payload.pop("review_sha256")
    raw = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")
    actual = hashlib.sha256(struct.pack(">I", len(DOMAIN)) + DOMAIN + struct.pack(">Q", len(raw)) + raw).hexdigest()
    if claimed != actual:
        fail("review self hash mismatch")
    return actual


def check(fixture_override: dict | None = None) -> list[tuple[str, str]]:
    contract, _ = load(CONTRACT)
    schema, _ = load(SCHEMA)
    fixture, fixture_raw = load(FIXTURE)
    if fixture_override is not None:
        fixture = fixture_override
        fixture_raw = json.dumps(fixture, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    status, _ = load(STATUS)
    successor, _ = load(SUCCESSOR)
    legacy, _ = load(LEGACY)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(fixture)
    review_digest = digest(fixture)
    p = contract["predecessor_a1_binding"]
    l = contract["legacy_s21a_contract"]
    r = contract["replacement_subject_contract"]
    if p["integration_commit"] != "3df8536c841390fdc593fa4a518885b3f2291fc6" or p["integration_tree"] != "bdccc42dc1d4e4c30f57f0d464fc5a58f832b0d6": fail("a1 binding drift")
    if p["integration_first_parent"] != "a5c70f235cf4e1bffa26253e2618e0a0903c9a16" or p["integration_second_parent"] != "8078eea048b23cccf1f4e4faae2115affcede6c9": fail("a1 parent order drift")
    if not p["external_receipt_must_remain_outside_repository"] or p["candidate_supplied_receipt_values_authoritative"]: fail("receipt boundary drift")
    if l["fixed_stale_cargo_lock_sha256"] == l["current_a1_cargo_lock_sha256"] or l["legacy_subject_may_be_reused_for_a1"] or l["legacy_rust_validator_may_validate_a1_subject"]: fail("legacy reuse drift")
    if legacy["build_bindings"]["cargo_lock_sha256"] != l["fixed_stale_cargo_lock_sha256"]: fail("legacy fixture drift")
    if r["a1_receipt_may_substitute_for_a2_receipt"] or not r["real_subject_generated_outside_repository_only"] or not r["real_subject_requires_a2_post_integration_double_rebuild_receipt"]: fail("replacement boundary drift")
    if fixture["predecessor_a1_binding"]["integration_commit"] != p["integration_commit"] or fixture["legacy_s21a_contract"]["current_a1_cargo_lock_sha256"] != l["current_a1_cargo_lock_sha256"]: fail("fixture binding drift")
    b = fixture["generation_boundary"]
    if any(b[k] for k in ("real_a2_receipt_present", "real_unsigned_subject_present", "owner_signature_may_be_requested", "external_input_admission_may_begin", "live_execution_may_begin")) or b["side_effects_unlocked"] != "NONE": fail("generation unlocked")
    if status["current_outputs"]["real_unsigned_subject_present"] or successor["current_admission"]["external_unsigned_subject_generation_may_begin"]: fail("status unlocked")
    return [("schema", fixture["schema"]), ("packet_kind", fixture["packet_kind"]), ("review_state", fixture["review_state"]), ("review_sha256", review_digest), ("fixture_sha256", hashlib.sha256(fixture_raw).hexdigest()), ("a1_integration_commit", p["integration_commit"]), ("a1_integration_tree", p["integration_tree"]), ("a1_cargo_lock_sha256", p["integration_cargo_lock_sha256"]), ("a1_external_receipt_file_sha256", p["external_role_build_receipt_file_sha256"]), ("legacy_s21a_reuse", "REJECTED"), ("a2_receipt_substitution", "REJECTED"), ("real_subject", "NOT_GENERATED"), ("owner_signature", "NOT_REQUESTED"), ("external_input_admission", "NOT_RUN"), ("live_execution", "NOT_RUN"), ("side_effects_unlocked", "NONE"), ("gate", "PASS")]


def self_test() -> None:
    value, _ = load(FIXTURE)
    cases = [("predecessor_a1_binding.integration_commit", "0" * 40), ("legacy_s21a_contract.legacy_subject_may_be_reused_for_a1", True), ("replacement_subject_contract.a1_receipt_may_substitute_for_a2_receipt", True), ("generation_boundary.live_execution_may_begin", True), ("nonclaims.review_is_owner_signature", True), ("review_sha256", "f" * 64)]
    for path, replacement in cases:
        mutated = copy.deepcopy(value); cursor = mutated
        keys = path.split(".")
        for key in keys[:-1]: cursor = cursor[key]
        cursor[keys[-1]] = replacement
        try:
            check(mutated)
        except (AssertionError, json.JSONDecodeError, ValidationError):
            pass
        else:
            fail(f"mutation accepted: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    rows = check()
    if args.self_test: self_test()
    print("\n".join(f"{key}\t{value}" for key, value in rows))


if __name__ == "__main__": main()
