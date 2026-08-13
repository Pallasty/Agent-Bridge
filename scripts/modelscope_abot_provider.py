#!/usr/bin/env python3
"""Default-off client for the public ModelScope ABot-World Studio."""

from __future__ import annotations

import argparse
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://amap-cvlab-abot-world-0.ms.show"
REQUIRED_ENDPOINTS = {
    "/check_model_ready_ui",
    "/on_click_start_ws",
    "/on_stop_ws",
}
BROWSER_RECEIPT_SCHEMA = "agent_bridge.modelscope_abot_browser_lifecycle.v0"
PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class GradioEvent:
    event: str
    data: Any


def parse_sse(body: str) -> list[GradioEvent]:
    events: list[GradioEvent] = []
    current = "message"
    for line in body.splitlines():
        if line.startswith("event:"):
            current = line[6:].strip()
        elif line.startswith("data:"):
            value = line[5:].strip()
            try:
                data = json.loads(value)
            except json.JSONDecodeError:
                data = value
            events.append(GradioEvent(current, data))
    return events


class ModelScopeAbotProvider:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 35.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _json_get(self, path: str) -> Any:
        request = urllib.request.Request(
            self.base_url + path,
            headers={"Accept": "application/json", "User-Agent": "agent-bridge-abot-provider/0"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def api_info(self) -> dict[str, Any]:
        value = self._json_get("/gradio_api/info")
        if not isinstance(value, dict):
            raise ProviderError("gradio_api_info_not_object")
        return value

    def app_config(self) -> dict[str, Any]:
        value = self._json_get("/config")
        if not isinstance(value, dict):
            raise ProviderError("gradio_config_not_object")
        return value

    def endpoint_names(self) -> set[str]:
        named = self.api_info().get("named_endpoints", {})
        return set(named) if isinstance(named, dict) else set()

    def _call(
        self, endpoint: str, data: list[Any], session_hash: str | None = None
    ) -> list[GradioEvent]:
        name = endpoint.lstrip("/")
        path = f"/gradio_api/call/{name}"
        body: dict[str, Any] = {"data": data}
        if session_hash:
            body["session_hash"] = session_hash
        payload = json.dumps(body, ensure_ascii=True).encode()
        request = urllib.request.Request(
            self.base_url + path,
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "agent-bridge-abot-provider/0",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = json.load(response)
        event_id = result.get("event_id") if isinstance(result, dict) else None
        if not isinstance(event_id, str) or not event_id:
            raise ProviderError("gradio_event_id_missing")
        event_request = urllib.request.Request(
            self.base_url + path + "/" + event_id,
            headers={"Accept": "text/event-stream", "User-Agent": "agent-bridge-abot-provider/0"},
        )
        with urllib.request.urlopen(event_request, timeout=self.timeout) as response:
            events = parse_sse(response.read().decode("utf-8", errors="replace"))
        if any(event.event == "error" for event in events):
            raise ProviderError("gradio_event_error")
        return events

    def readiness(self) -> dict[str, Any]:
        endpoints = self.endpoint_names()
        missing = sorted(REQUIRED_ENDPOINTS - endpoints)
        events = self._call("/check_model_ready_ui", [None]) if not missing else []
        outputs = next((event.data for event in events if event.event == "complete"), None)
        ready_text = outputs[0] if isinstance(outputs, list) and outputs else ""
        ready = not missing and isinstance(ready_text, str) and "就绪" in ready_text
        return {
            "schema": "agent_bridge.modelscope_abot_readiness.v0",
            "provider_id": PROVIDER_ID,
            "ready": ready,
            "missing_endpoints": missing,
            "status_text": ready_text,
            "runtime_admitted": False,
        }

    def session_contract(self) -> dict[str, Any]:
        config = self.app_config()
        dependencies = config.get("dependencies", [])
        by_name = {
            dependency.get("api_name"): dependency
            for dependency in dependencies
            if isinstance(dependency, dict)
        }
        start = by_name.get("on_click_start_ws", {})
        stop = by_name.get("on_stop_ws", {})
        start_inputs = start.get("inputs", [])
        start_outputs = start.get("outputs", [])
        stop_inputs = stop.get("inputs", [])
        stateful = len(start_inputs) > 1 or len(stop_inputs) > 1
        return {
            "schema": "agent_bridge.modelscope_abot_session_contract.v0",
            "provider_id": PROVIDER_ID,
            "start_input_count": len(start_inputs),
            "start_output_count": len(start_outputs),
            "stop_input_count": len(stop_inputs),
            "hidden_state_required": stateful,
            "rest_lifecycle_supported": not stateful,
            "browser_or_websocket_adapter_required": stateful,
            "runtime_admitted": False,
        }


def validate_browser_receipt(receipt: Any) -> dict[str, Any]:
    violations: list[str] = []
    if not isinstance(receipt, dict):
        violations.append("receipt_not_object")
        receipt = {}
    if receipt.get("schema") != BROWSER_RECEIPT_SCHEMA:
        violations.append("schema_mismatch")
    if receipt.get("provider_id") != PROVIDER_ID:
        violations.append("provider_id_mismatch")

    observations = receipt.get("observations")
    if not isinstance(observations, dict):
        violations.append("observations_not_object")
        observations = {}
    required_true = (
        "start_observed",
        "stream_observed",
        "stop_requested",
        "stop_observed",
        "post_stop_ready",
    )
    for field in required_true:
        if observations.get(field) is not True:
            violations.append(f"{field}_not_true")

    max_fps = observations.get("max_observed_fps")
    if not isinstance(max_fps, (int, float)) or isinstance(max_fps, bool) or max_fps <= 0:
        violations.append("positive_max_observed_fps_required")
    if observations.get("post_stop_iframe_count") != 0:
        violations.append("post_stop_iframe_count_not_zero")

    artifact = receipt.get("generated_artifact")
    if artifact is not None:
        if not isinstance(artifact, dict):
            violations.append("generated_artifact_not_object_or_null")
        elif not artifact.get("ref") or not artifact.get("sha256"):
            violations.append("generated_artifact_unbound")
    if receipt.get("rollout_emitted") is not False:
        violations.append("rollout_emitted_must_be_false")
    if receipt.get("runtime_admitted") is not False:
        violations.append("runtime_admitted_must_be_false")

    return {
        "schema": "agent_bridge.modelscope_abot_browser_receipt_validation.v0",
        "valid": not violations,
        "violations": violations,
        "lifecycle_closed": not violations,
        "generated_artifact_bound": isinstance(artifact, dict) and not any(
            violation.startswith("generated_artifact_") for violation in violations
        ),
        "rollout_eligible": False,
        "runtime_admitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output")
    parser.add_argument("--session-contract", action="store_true")
    parser.add_argument("--validate-browser-receipt", type=Path)
    args = parser.parse_args()
    if args.validate_browser_receipt:
        receipt = json.loads(args.validate_browser_receipt.read_text(encoding="utf-8"))
        result = validate_browser_receipt(receipt)
    else:
        provider = ModelScopeAbotProvider(args.base_url)
        result = provider.session_contract() if args.session_contract else provider.readiness()
    rendered = json.dumps(result, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as stream:
            stream.write(rendered)
    else:
        print(rendered, end="")
    return 0 if result.get("ready", result.get("valid", True)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
