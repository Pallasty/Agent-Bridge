"""Read-only, secret-blind preflight for the T22-A0 real-process pilot."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import shutil
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a0-real-lab-owner-authorization-proposal-v1.json"
AUTHORIZATION_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a0_owner_authorization_v1.py"
DOMAIN = b"AB_TRACK_B_T22_A0_OWNER_AUTHORIZATION_PROPOSAL_V1\0"
REQUIRED_TOOLS = ("etcd", "etcdctl", "bao", "toxiproxy-server")


def load_authorization_module():
    spec = importlib.util.spec_from_file_location("t22_a0_owner_authorization", AUTHORIZATION_SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def proposal_sha256(value: dict) -> str:
    unsigned = dict(value)
    unsigned.pop("proposal_sha256", None)
    return hashlib.sha256(DOMAIN + canonical(unsigned)).hexdigest()


def validate_proposal(value: dict) -> None:
    assert value["schema"] == "agent_bridge.biocortex.track_b.t22_a0.owner_authorization_proposal.v1"
    assert value["state"] == "AWAITING_EXACT_OWNER_SIGNATURE"
    assert value["track_id"] == "SELF_HOSTED_ETCD_OPENBAO"
    assert value["scope"]["physical_host_count"] == 1
    assert value["scope"]["failure_domain_claim"] == "PROCESS_ONLY_SINGLE_PHYSICAL_HOST"
    assert value["scope"]["spend_limit_usd"] == 0
    assert value["scope"]["maximum_runtime_seconds"] == 14400
    assert value["scope"]["credential_access_before_signature"] is False
    assert value["scope"]["preexisting_or_ambient_credential_access"] is False
    assert value["scope"]["ephemeral_lab_bootstrap_material_after_signature"] is True
    assert value["scope"]["ephemeral_lab_bootstrap_material_persisted"] is False
    assert value["scope"]["provider_or_cloud_access"] is False
    assert value["scope"]["production_or_customer_data"] is False
    assert value["scope"]["host_global_network_mutation"] is False
    assert value["scope"]["public_hash_pinned_downloads_after_signature"] is True
    assert value["topology"] == {"etcd_processes": 3, "openbao_processes": 3, "toxiproxy_processes": 1}
    assert value["execution_contract"] == {
        "path": "docs/design/fixtures/biocortex-ab-track-b-t22-a0-real-process-execution-contract-v1.json",
        "schema": "agent_bridge.biocortex.track_b.t22_a0.real_process_execution_contract.v1",
        "contract_sha256": "f84fe9ea9d8948afa7eca516f486bb40d690acfd19437a7b3469af8c4dc37616",
    }
    assert value["allowed_faults_after_signature"] == [
        "OWNED_PROCESS_KILL", "LOOPBACK_PROXY_DISCONNECT", "OWNED_SERVICE_RESTART",
    ]
    assert value["acceptance"] == [
        "HASH_PINNED_PUBLIC_RELEASE_ARTIFACTS_VERIFIED",
        "THREE_ETCD_PROCESSES_FORM_ONE_LOCAL_CLUSTER",
        "THREE_OPENBAO_PROCESSES_FORM_ONE_LOCAL_RAFT_CLUSTER",
        "ONE_LINEARIZABLE_AUTHORIZE_AND_CONSUME_TRANSITION_OBSERVED",
        "ONE_PROCESS_OR_LOOPBACK_PROXY_FAULT_INJECTED_AND_RECOVERED",
        "RAW_CANONICAL_VALIDATION_AND_CLEANUP_RECEIPTS_WRITTEN",
        "NO_STDOUT_LOG_CALLBACK_OR_SUBPROCESS_MODEL_OUTPUT",
        "ALL_SERVICES_STOPPED_AND_ARTIFACT_ROOT_SCOPED_AT_END",
    ]
    assert value["signing"]["owner_id"] == "pallasting"
    assert value["signing"]["owner_role"] == "PROJECT_OWNER"
    assert value["signing"]["signature_scheme"] == "OPENSSH_SSHSIG_ED25519"
    assert value["signing"]["signature_namespace"] == "agent-bridge-t22-a0-owner-v1"
    assert value["signing"]["owner_public_key"] == "UNBOUND"
    assert value["signing"]["owner_signature"] == "UNBOUND"
    assert value["signing"]["exact_payload_generated"] is False
    assert value["claims"]["real_process_execution_authorized"] is False
    assert value["claims"]["three_failure_domain_evidence"] is False
    assert value["claims"]["external_anti_rollback_evidence"] is False
    assert value["claims"]["production_admissible"] is False
    assert proposal_sha256(value) == value["proposal_sha256"]


def inspect() -> dict:
    proposal = json.loads(PROPOSAL.read_text())
    validate_proposal(proposal)
    authorization_status = load_authorization_module().status()
    tools = {name: (shutil.which(name) or "MISSING") for name in REQUIRED_TOOLS}
    missing = [name for name, path in tools.items() if path == "MISSING"]
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a0.preflight_receipt.v0",
        "status": "BLOCKED_OWNER_SIGNATURE_AND_PINNED_TOOLS_REQUIRED",
        "host": socket.gethostname(),
        "platform": platform.system(),
        "physical_host_count": 1,
        "required_tool_count": len(REQUIRED_TOOLS),
        "missing_tool_count": len(missing),
        "missing_tools": missing,
        "owner_public_key_bound": authorization_status["owner_trust_anchor_valid"],
        "owner_signature_verified": False,
        "credentials_accessed": False,
        "network_accessed": False,
        "spend_authorized_usd": 0,
        "services_started": 0,
        "faults_injected": 0,
        "real_evidence_items_created": 0,
        "production_admissible": False,
        "proposal_sha256": proposal["proposal_sha256"],
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True, separators=(",", ":")))
