"""Offline KATs for the T22-A1 exact evidence finalizer."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_exact_evidence_finalizer_v1.py"
spec = importlib.util.spec_from_file_location("t22a1_exact_evidence_finalizer_kat", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
runner = module.load_runner_module()


def sha(label: str) -> str:
    return hashlib.sha256(f"T22_A1_EXACT_FINALIZER_SYNTHETIC:{label}".encode()).hexdigest()


def expect_failure(action, expected: str) -> None:  # noqa: ANN001
    try:
        action()
    except module.SafeFailure as error:
        assert str(error) == expected, (str(error), expected)
        return
    raise AssertionError(f"unsafe exact finalizer input admitted: {expected}")


schedule = runner.global_schedule("domain-3")
receipt_chains = {domain_id: [] for domain_id in module.DOMAIN_IDS}
transcript = []
for sequence, (domain_id, command) in enumerate(schedule):
    receipt = {
        "domain_id": domain_id, "command": command,
        "content_sha256": sha(f"receipt:{sequence}:{domain_id}:{command}"),
    }
    receipt_chains[domain_id].append(receipt)
    row = {
        "sequence": sequence, "domain_id": domain_id, "command": command,
        "command_receipt_sha256": receipt["content_sha256"],
    }
    row["transcript_sha256"] = runner.digest(row)
    transcript.append(row)

module.validate_transcript(transcript, receipt_chains, "domain-3")
negative_count = 0
bad_digest = copy.deepcopy(transcript)
bad_digest[0]["transcript_sha256"] = sha("wrong-transcript")
expect_failure(
    lambda: module.validate_transcript(bad_digest, receipt_chains, "domain-3"),
    "E_EXACT_FINALIZER_TRANSCRIPT_DIGEST",
)
negative_count += 1
bad_order = copy.deepcopy(transcript)
bad_order[0], bad_order[1] = bad_order[1], bad_order[0]
expect_failure(
    lambda: module.validate_transcript(bad_order, receipt_chains, "domain-3"),
    "E_EXACT_FINALIZER_TRANSCRIPT",
)
negative_count += 1
missing_receipt = copy.deepcopy(receipt_chains)
missing_receipt["domain-1"].pop()
expect_failure(
    lambda: module.validate_transcript(transcript, missing_receipt, "domain-3"),
    "E_EXACT_FINALIZER_TRANSCRIPT",
)
negative_count += 1

domain_public_keys = {domain_id: f"ssh-ed25519 SYNTHETIC-{domain_id}\n".encode() for domain_id in module.DOMAIN_IDS}
expect_failure(
    lambda: module.ExactEvidenceFinalizer(object(), object(), domain_public_keys, 2, False),
    "E_EXACT_FINALIZER_ACTIVATION_NOT_READY",
)
negative_count += 1


class Collector:
    event_plan = []
    signed_events = []
    log_sets = {domain_id: [] for domain_id in module.DOMAIN_IDS}

    def validate_complete(self) -> None:
        return None


class BootstrapStore:
    def __init__(self) -> None:
        self.secret = bytearray(b"SYNTHETIC-FINALIZER-SECRET")

    def take_secret_for_evidence(self) -> bytearray:
        value = self.secret
        self.secret = bytearray()
        return value


store = BootstrapStore()
finalizer = module.ExactEvidenceFinalizer(Collector(), store, domain_public_keys, 2, True)
owned_secret = store.secret
expect_failure(
    lambda: finalizer({"fault": {"target_domain_id": "domain-3"}}, {}, [], receipt_chains, transcript),
    "E_EVIDENCE_EXECUTION",
)
assert owned_secret == bytearray(len(owned_secret))
negative_count += 1
expect_failure(
    lambda: finalizer({"fault": {"target_domain_id": "domain-3"}}, {}, [], receipt_chains, transcript),
    "E_EXACT_FINALIZER_SINGLE_ATTEMPT",
)
negative_count += 1

status = module.status()
assert status["exact_evidence_finalizer_activation_ready"] is False
assert status["single_attempt_only"] is True
assert status["secret_ownership_transferred_and_zeroized"] is True
assert status["real_private_inputs_read"] == status["persistent_evidence_sets_created"] == 0
assert status["network_accessed"] is False and status["listeners_started"] == 0
assert status["processes_started"] == status["faults_injected"] == status["spend_usd_cents"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

print("t22_a1_exact_evidence_finalizer_check\tpass")
print("synthetic_exact_transcript_command_count\t23")
print("directed_negative_test_count\t6")
print("early_failure_secret_zeroization_count\t1")
print("single_attempt_rejection_count\t1")
print("real_private_inputs_read\t0")
print("persistent_evidence_sets_created\t0")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("processes_started\t0")
print("faults_injected\t0")
print("production_admissible\tfalse")
