#!/usr/bin/env python3
"""Corrected D54 runner entry point for nested authorization authority fields."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fh_l8_object_cost_measurement_d54_runner as base


AUTHORIZATION_ID = "FH-L8-D54R-OBJECT-COST-MEASUREMENT-AUTH-V1"
sample_plan = base.sample_plan


def validate_authorization(
    authorization: Mapping[str, Any],
    runner_path: Path,
    d53_path: Path = base.D53_CONTRACT,
) -> None:
    if authorization.get("authorization_id") != AUTHORIZATION_ID:
        raise base.D54RunnerError("authorization id drift")
    if authorization.get("measurement_execution_authorized") is not True:
        raise base.D54RunnerError("measurement execution is not authorized")
    if authorization.get("runner_sha256") != base.digest(runner_path):
        raise base.D54RunnerError("runner source pin mismatch")
    if authorization.get("d53_contract_sha256") != base.digest(d53_path):
        raise base.D54RunnerError("D53 contract pin mismatch")
    authority = authorization.get("authority")
    if not isinstance(authority, Mapping):
        raise base.D54RunnerError("authorization authority object missing")
    if authority.get("packed_q3_reads_authorized") != 0:
        raise base.D54RunnerError("packed-q3 authority must remain zero")
    if authority.get("full53_execution_authorized") is not False:
        raise base.D54RunnerError("full53 authority unexpectedly open")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--tier", required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--sample-kind", choices=("warmup", "measured"), required=True)
    parser.add_argument("--repetition", type=int, required=True)
    args = parser.parse_args()
    runner_path = Path(__file__).resolve()
    validate_authorization(base.load(args.authorization), runner_path)
    d53 = base.load(base.D53_CONTRACT)
    requested = {
        "tier": args.tier,
        "size": args.size,
        "sample_kind": args.sample_kind,
        "repetition": args.repetition,
    }
    if requested not in base.sample_plan(d53):
        raise base.D54RunnerError("requested sample is outside D53 plan")
    if args.tier == "synthetic_object_calibration":
        result = base.measure_synthetic(args.size)
    elif args.tier == "source_bound_fixed64_micro":
        result = base.measure_fixed64(args.size)
    else:
        raise base.D54RunnerError("unknown measurement tier")
    print(json.dumps({**requested, **result}, sort_keys=True))


if __name__ == "__main__":
    main()
