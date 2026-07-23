"""One-shot runner-to-evidence finalization binding for T22-A1.

The finalizer closes the last in-memory gap between the source-bound runner,
the authenticated domain lanes, the signed-event compiler, and the private
atomic evidence writer.  It owns exactly one attempt: a failed compilation or
publication is terminal and must not be retried against the same run root.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPILER_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_evidence_compiler_v1.py"
WRITER_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_evidence_writer_v1.py"
RUNNER_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_source_bound_runner_v1.py"
DOMAIN_IDS = ("domain-1", "domain-2", "domain-3")
EXACT_EVIDENCE_FINALIZER_ACTIVATION_READY = False
_COMPILER_MODULE = None
_WRITER_MODULE = None
_RUNNER_MODULE = None


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def foreign_call(function, *arguments, **keywords):  # noqa: ANN001, ANN002, ANN003
    try:
        return function(*arguments, **keywords)
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error


def load_module(name: str, source: Path):
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_compiler_module():
    global _COMPILER_MODULE  # noqa: PLW0603
    if _COMPILER_MODULE is None:
        _COMPILER_MODULE = load_module("t22a1_compiler_for_exact_finalizer", COMPILER_SOURCE)
    return _COMPILER_MODULE


def load_writer_module():
    global _WRITER_MODULE  # noqa: PLW0603
    if _WRITER_MODULE is None:
        _WRITER_MODULE = load_module("t22a1_writer_for_exact_finalizer", WRITER_SOURCE)
    return _WRITER_MODULE


def load_runner_module():
    global _RUNNER_MODULE  # noqa: PLW0603
    if _RUNNER_MODULE is None:
        _RUNNER_MODULE = load_module("t22a1_runner_for_exact_finalizer", RUNNER_SOURCE)
    return _RUNNER_MODULE


def is_sha256(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and value != "0" * 64
        and all(character in "0123456789abcdef" for character in value)
    )


def validate_transcript(
    transcript: object,
    receipt_chains: object,
    fault_target_domain_id: object,
) -> None:
    require(
        isinstance(receipt_chains, dict) and set(receipt_chains) == set(DOMAIN_IDS),
        "E_EXACT_FINALIZER_RECEIPT_SET",
    )
    receipt_map: dict[tuple[str, str], dict] = {}
    for domain_id in DOMAIN_IDS:
        chain = receipt_chains[domain_id]
        require(isinstance(chain, list), "E_EXACT_FINALIZER_RECEIPT_SET")
        for receipt in chain:
            require(
                isinstance(receipt, dict) and receipt.get("domain_id") == domain_id
                and isinstance(receipt.get("command"), str)
                and is_sha256(receipt.get("content_sha256")),
                "E_EXACT_FINALIZER_RECEIPT_SET",
            )
            key = (domain_id, receipt["command"])
            require(key not in receipt_map, "E_EXACT_FINALIZER_RECEIPT_REPLAY")
            receipt_map[key] = receipt
    runner = load_runner_module()
    expected_schedule = foreign_call(runner.global_schedule, fault_target_domain_id)
    require(
        isinstance(transcript, list)
        and len(transcript) == len(receipt_map) == len(expected_schedule) == 23,
        "E_EXACT_FINALIZER_TRANSCRIPT",
    )
    observed_keys: list[tuple[str, str]] = []
    for sequence, (row, expected_key) in enumerate(zip(transcript, expected_schedule, strict=True)):
        require(
            isinstance(row, dict) and set(row) == {
                "sequence", "domain_id", "command", "command_receipt_sha256", "transcript_sha256",
            }
            and row["sequence"] == sequence and row["domain_id"] in DOMAIN_IDS
            and isinstance(row["command"], str)
            and is_sha256(row["command_receipt_sha256"])
            and is_sha256(row["transcript_sha256"]),
            "E_EXACT_FINALIZER_TRANSCRIPT",
        )
        key = (row["domain_id"], row["command"])
        require(
            key == expected_key and key in receipt_map
            and receipt_map[key]["content_sha256"] == row["command_receipt_sha256"]
            and key not in observed_keys,
            "E_EXACT_FINALIZER_TRANSCRIPT_BINDING",
        )
        unsigned = dict(row)
        claimed_transcript_sha256 = unsigned.pop("transcript_sha256")
        require(
            claimed_transcript_sha256 == runner.digest(unsigned),
            "E_EXACT_FINALIZER_TRANSCRIPT_DIGEST",
        )
        observed_keys.append(key)
    require(set(observed_keys) == set(receipt_map), "E_EXACT_FINALIZER_TRANSCRIPT_BINDING")


class ExactEvidenceFinalizer:
    """Transfer volatile evidence into one atomically published evidence set."""

    def __init__(
        self,
        collector,  # noqa: ANN001
        bootstrap_store,  # noqa: ANN001
        domain_public_keys: dict[str, bytes],
        synthetic_only: bool,
    ) -> None:
        require(
            synthetic_only or EXACT_EVIDENCE_FINALIZER_ACTIVATION_READY,
            "E_EXACT_FINALIZER_ACTIVATION_NOT_READY",
        )
        require(
            set(domain_public_keys) == set(DOMAIN_IDS)
            and all(isinstance(raw, bytes) and raw for raw in domain_public_keys.values()),
            "E_EXACT_FINALIZER_DOMAIN_KEY_SET",
        )
        self.collector = collector
        self.bootstrap_store = bootstrap_store
        self.domain_public_keys = dict(domain_public_keys)
        self.synthetic_only = synthetic_only
        self.attempted = False

    def __call__(
        self,
        execution: dict,
        admission: dict,
        plans: list[dict],
        receipt_chains: dict[str, list[dict]],
        transcript: list[dict],
    ) -> dict:
        require(not self.attempted, "E_EXACT_FINALIZER_SINGLE_ATTEMPT")
        self.attempted = True
        compiler = load_compiler_module()
        writer = load_writer_module()
        require(
            self.synthetic_only
            or (
                EXACT_EVIDENCE_FINALIZER_ACTIVATION_READY
                and compiler.EVIDENCE_ACTIVATION_READY
                and writer.EVIDENCE_WRITER_ACTIVATION_READY
            ),
            "E_EXACT_FINALIZER_ACTIVATION_CHAIN",
        )
        foreign_call(self.collector.validate_complete)
        maximum_observed_clock_skew_seconds = getattr(
            self.collector, "maximum_observed_clock_skew_seconds", None,
        )
        require(
            isinstance(maximum_observed_clock_skew_seconds, int)
            and 0 <= maximum_observed_clock_skew_seconds <= 300,
            "E_EXACT_FINALIZER_CLOCK_SKEW",
        )
        validate_transcript(transcript, receipt_chains, execution.get("fault", {}).get("target_domain_id"))
        signed_events = list(self.collector.signed_events)
        log_sets = {domain_id: list(self.collector.log_sets[domain_id]) for domain_id in DOMAIN_IDS}
        secret = foreign_call(self.bootstrap_store.take_secret_for_evidence)
        require(isinstance(secret, bytearray) and len(secret) > 0, "E_EXACT_FINALIZER_SECRET_OWNERSHIP")
        try:
            compilation = foreign_call(
                compiler.compile_terminal_evidence,
                execution, admission, plans, receipt_chains, signed_events,
                self.domain_public_keys, log_sets, [secret],
                maximum_observed_clock_skew_seconds, self.synthetic_only,
            )
            require(not any(secret), "E_EXACT_FINALIZER_SECRET_ZEROIZATION")
            publication = foreign_call(
                writer.persist_evidence_set,
                execution, compilation, signed_events, self.domain_public_keys, self.synthetic_only,
            )
        finally:
            if any(secret):
                secret[:] = b"\0" * len(secret)
        terminal = compilation["terminal_evidence"]
        require(
            publication.get("status") == "PASS_T22_A1_PRIVATE_EVIDENCE_SET_ATOMICALLY_PUBLISHED"
            and publication.get("terminal_evidence_content_sha256") == terminal.get("content_sha256")
            and is_sha256(publication.get("evidence_manifest_content_sha256"))
            and terminal.get("cleanup", {}).get("all_owned_processes_stopped") is True
            and terminal.get("cleanup", {}).get("all_owned_ports_released") is True
            and terminal.get("cleanup", {}).get("secret_value_scan_passed") is True,
            "E_EXACT_FINALIZER_PUBLICATION_BINDING",
        )
        return {
            "evidence_manifest_content_sha256": publication["evidence_manifest_content_sha256"],
            "terminal_evidence_content_sha256": terminal["content_sha256"],
            "all_owned_processes_cleaned": True,
            "all_owned_ports_released": True,
            "secret_value_scan_passed": True,
        }


def status() -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.exact_evidence_finalizer_status.v0",
        "status": "EXACT_RUNNER_EVIDENCE_FINALIZATION_PRESENT_REAL_ACTIVATION_CLOSED",
        "exact_evidence_finalizer_activation_ready": EXACT_EVIDENCE_FINALIZER_ACTIVATION_READY,
        "single_attempt_only": True, "secret_ownership_transferred_and_zeroized": True,
        "real_private_inputs_read": 0, "persistent_evidence_sets_created": 0,
        "network_accessed": False, "listeners_started": 0, "processes_started": 0,
        "faults_injected": 0, "spend_usd_cents": 0,
        "execution_authorized": False, "production_admissible": False,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
