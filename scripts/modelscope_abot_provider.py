#!/usr/bin/env python3
"""Default-off client for the public ModelScope ABot-World Studio."""

from __future__ import annotations

import argparse
import hashlib
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
ARTIFACT_RECEIPT_SCHEMA = "agent_bridge.modelscope_abot_artifact_capture.v0"
PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class GradioEvent:
    event: str
    data: Any


def jpeg_dimensions(content: bytes) -> tuple[int, int] | None:
    if not content.startswith(b"\xff\xd8"):
        return None
    offset = 2
    sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset + 8 < len(content):
        if content[offset] != 0xFF:
            offset += 1
            continue
        marker = content[offset + 1]
        if marker in sof_markers:
            height = int.from_bytes(content[offset + 5 : offset + 7], "big")
            width = int.from_bytes(content[offset + 7 : offset + 9], "big")
            return width, height
        if marker == 0xDA or offset + 4 > len(content):
            break
        if marker in {0x01, *range(0xD0, 0xDA)}:
            offset += 2
            continue
        segment_length = int.from_bytes(content[offset + 2 : offset + 4], "big")
        if segment_length < 2:
            break
        offset += 2 + segment_length
    return None


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
        advertised = self.endpoint_names()
        missing_advertised = sorted(REQUIRED_ENDPOINTS - advertised)
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
        blockers: list[str] = []
        if missing_advertised:
            blockers.append("required_endpoint_not_advertised")
        if not isinstance(start, dict) or not start:
            blockers.append("start_dependency_missing")
        if not isinstance(stop, dict) or not stop:
            blockers.append("stop_dependency_missing")
        if stateful:
            blockers.append("hidden_state_required")
        return {
            "schema": "agent_bridge.modelscope_abot_session_contract.v0",
            "provider_id": PROVIDER_ID,
            "start_input_count": len(start_inputs),
            "start_output_count": len(start_outputs),
            "stop_input_count": len(stop_inputs),
            "missing_advertised_endpoints": missing_advertised,
            "hidden_state_required": stateful,
            "rest_lifecycle_supported": not blockers,
            "browser_or_websocket_adapter_required": stateful,
            "admission_blockers": blockers,
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


def validate_artifact_receipt(receipt: Any, receipt_path: Path) -> dict[str, Any]:
    violations: list[str] = []
    if not isinstance(receipt, dict):
        violations.append("receipt_not_object")
        receipt = {}
    if receipt.get("schema") != ARTIFACT_RECEIPT_SCHEMA:
        violations.append("schema_mismatch")
    if receipt.get("provider_id") != PROVIDER_ID:
        violations.append("provider_id_mismatch")

    artifact = receipt.get("artifact")
    artifact_sha = None
    if not isinstance(artifact, dict):
        violations.append("artifact_not_object")
        artifact = {}
    artifact_ref = artifact.get("ref")
    if not isinstance(artifact_ref, str) or not artifact_ref:
        violations.append("artifact_ref_missing")
    else:
        evidence_root = receipt_path.resolve().parent
        artifact_path = (evidence_root / artifact_ref).resolve()
        if artifact_path.parent != evidence_root:
            violations.append("artifact_ref_outside_evidence_root")
        elif not artifact_path.is_file():
            violations.append("artifact_file_missing")
        else:
            content = artifact_path.read_bytes()
            artifact_sha = hashlib.sha256(content).hexdigest()
            if artifact_sha != artifact.get("sha256"):
                violations.append("artifact_sha256_mismatch")
            if len(content) != artifact.get("bytes"):
                violations.append("artifact_size_mismatch")
            if not (content.startswith(b"\xff\xd8\xff") and content.endswith(b"\xff\xd9")):
                violations.append("artifact_not_complete_jpeg")
            if jpeg_dimensions(content) != (artifact.get("width"), artifact.get("height")):
                violations.append("artifact_dimensions_mismatch")
    if artifact.get("content_type") != "image/jpeg":
        violations.append("artifact_content_type_mismatch")

    request = receipt.get("request")
    if not isinstance(request, dict):
        violations.append("request_not_object")
        request = {}
    if request.get("schema") != "agent_bridge.projection_request_envelope.v0":
        violations.append("request_schema_mismatch")
    if request.get("provider_id") != PROVIDER_ID:
        violations.append("request_provider_mismatch")
    if request.get("projection_class") != "simulated.generated":
        violations.append("request_projection_class_mismatch")
    if "provider_native_jpeg_frame" not in request.get("requested_outputs", []):
        violations.append("request_output_missing")

    rollout = receipt.get("rollout")
    if not isinstance(rollout, dict):
        violations.append("rollout_not_object")
        rollout = {}
    if rollout.get("schema") != "agent_bridge.simulated_world_rollout.v0":
        violations.append("rollout_schema_mismatch")
    if not request.get("request_id") or rollout.get("request_id") != request.get("request_id"):
        violations.append("rollout_request_mismatch")
    if rollout.get("evidence_class") != "simulated.generated":
        violations.append("rollout_evidence_class_mismatch")
    provider = rollout.get("provider")
    if not isinstance(provider, dict) or provider.get("id") != PROVIDER_ID:
        violations.append("rollout_provider_mismatch")
    expected_hashes = [f"sha256:{artifact_sha}"] if artifact_sha else []
    if rollout.get("generated_artifact_hashes") != expected_hashes:
        violations.append("rollout_artifact_hash_mismatch")
    if rollout.get("verdict") != "not_verified":
        violations.append("rollout_verdict_must_be_not_verified")
    constraints = request.get("constraints", {})
    if not isinstance(constraints, dict):
        violations.append("request_constraints_not_object")
        constraints = {}
    generation_parameters = rollout.get("generation_parameters", {})
    if not isinstance(generation_parameters, dict):
        violations.append("rollout_generation_parameters_not_object")
        generation_parameters = {}
    request_prompt_sha = constraints.get("prompt_sha256")
    rollout_prompt_sha = generation_parameters.get("prompt_sha256")
    if not request_prompt_sha or rollout_prompt_sha != request_prompt_sha:
        violations.append("rollout_prompt_binding_mismatch")
    boundary = rollout.get("truth_boundary")
    if not isinstance(boundary, dict):
        violations.append("rollout_truth_boundary_missing")
    elif (
        boundary.get("external_world_effect_claimed") is not False
        or boundary.get("generated_visual_claimed") is not True
        or boundary.get("verified_to") is not None
    ):
        violations.append("rollout_truth_boundary_exceeded")
    if receipt.get("runtime_admitted") is not False:
        violations.append("runtime_admitted_must_be_false")

    valid = not violations
    return {
        "schema": "agent_bridge.modelscope_abot_artifact_validation.v0",
        "valid": valid,
        "violations": violations,
        "artifact_bound": valid,
        "rollout_contract_satisfied": valid,
        "rollout_eligible": valid,
        "runtime_admitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output")
    parser.add_argument("--session-contract", action="store_true")
    parser.add_argument("--validate-browser-receipt", type=Path)
    parser.add_argument("--validate-artifact-receipt", type=Path)
    args = parser.parse_args()
    if args.validate_artifact_receipt:
        receipt = json.loads(args.validate_artifact_receipt.read_text(encoding="utf-8"))
        result = validate_artifact_receipt(receipt, args.validate_artifact_receipt)
    elif args.validate_browser_receipt:
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
