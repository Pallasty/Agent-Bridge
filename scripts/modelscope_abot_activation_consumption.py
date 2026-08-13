#!/usr/bin/env python3
"""Non-actuating single-use activation consumption for ModelScope ABot."""

from __future__ import annotations

import hashlib
import json
from typing import Any


CONSUMPTION_SCHEMA = "agent_bridge.modelscope_abot_activation_consumption.v0"


class ActivationConsumptionError(ValueError):
    pass


def consume_activation(
    *, store: Any, activation_id: str, capability_contract: dict[str, Any],
    capability_validator: Any, now_unix_ms: int, fault_after_mark: bool = False,
) -> dict[str, Any]:
    if not isinstance(capability_contract, dict):
        raise ActivationConsumptionError("capability contract not object")
    capability_sha256 = hashlib.sha256(
        json.dumps(
            capability_contract, ensure_ascii=True, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode()
    ).hexdigest()
    validation = capability_validator(capability_contract, now_unix_ms)
    if validation.get("valid") is not True:
        raise ActivationConsumptionError("capability contract invalid")
    try:
        reference = store.validate_activation_reference(
            activation_id=activation_id,
            capability_sha256=capability_sha256,
            now_unix_ms=now_unix_ms,
        )
        if reference["capability_id"] != capability_contract.get("capability_id"):
            raise ActivationConsumptionError("capability id mismatch")
        result = store.consume_activation(
            activation_id=activation_id,
            capability_sha256=capability_sha256,
            now_unix_ms=now_unix_ms,
            fault_after_mark=fault_after_mark,
        )
    except ActivationConsumptionError:
        raise
    except Exception as error:
        raise ActivationConsumptionError("activation consumption rejected") from error
    result["capability_validated"] = True
    result["activation_reference_validated"] = True
    return result
