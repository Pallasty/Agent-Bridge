#!/usr/bin/env python3
"""Validate the new burn-in-bound one-shot fake-Q8 authorization pack."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "agent_bridge.qwen3_tts.fake_q8_burnin_bound_authorization.v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(pack: dict, receipt: dict, *, receipt_hash: str) -> None:
    if pack.get("schema") != SCHEMA or pack.get("status") != "READY_FOR_ONE_NEW_ONE_SHOT_FAKE_Q8_SMOKE":
        raise ValueError("authorization pack identity/status drift")
    control = pack.get("control", {})
    if control.get("receipt_sha256") != receipt_hash or receipt.get("status") != control.get("status"):
        raise ValueError("burn-in receipt binding drift")
    if receipt.get("control_invariants", {}).get("measured_count") != control.get("measured_count"):
        raise ValueError("measured count drift")
    if any(row.get("classification") != control.get("all_paths") for key, row in receipt.get("paths", {}).items() if key != "predictor_heads_1_through_14"):
        raise ValueError("control path is not bit exact")
    if receipt.get("paths", {}).get("predictor_heads_1_through_14", {}).get("classification") != "BIT_EXACT":
        raise ValueError("predictor heads are not bit exact")
    trial = pack.get("trial", {})
    if not trial.get("one_shot_claim_o_excl") or not trial.get("claim_is_never_automatically_deleted"):
        raise ValueError("one-shot claim boundary drift")
    if trial.get("processes") != 1 or trial.get("modules") != 1 or trial.get("cases") != 1 or trial.get("fake_trials") != 1:
        raise ValueError("trial cardinality drift")
    if trial.get("trial_id", "").endswith("-001") is False or "v1-burnin" not in trial.get("trial_id", ""):
        raise ValueError("new trial identity drift")
    authorization = pack.get("authorization", {})
    if authorization.get("allows_exactly_one_module_one_case_fake_q8_smoke") is not True:
        raise ValueError("fake-Q8 authority missing")
    forbidden = ("allows_weight_mutation", "allows_quantized_weight_writing", "allows_runtime_candidate_generation", "allows_worker_socket_use", "allows_audio_decode_write_or_playback", "allows_runtime_wiring_fallback_deployment_or_promotion")
    if any(authorization.get(key) is not False for key in forbidden):
        raise ValueError("authorization grants forbidden authority")
    if pack.get("not_authorized") != ["model_write", "candidate_pack", "runtime_wiring", "worker_replacement", "deployment", "additional_trials"]:
        raise ValueError("negative authority boundary drift")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    pack = load(args.pack)
    receipt = load(args.receipt)
    validate(pack, receipt, receipt_hash=sha256(args.receipt))
    print(json.dumps({"status": "AUTHORIZATION_PACK_VALID", "trial_id": pack["trial"]["trial_id"], "receipt_sha256": sha256(args.receipt)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
