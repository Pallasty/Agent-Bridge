"""Synthetic KAT for the pure T22-A1 domain workload-plan compiler."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_workload_plan_v1.py"
spec = importlib.util.spec_from_file_location("t22a1domainworkloadplan", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

SOURCE_COMMIT = "a" * 40
RUN_ID = "t22-a1-20260722T220000.000000z-123456789abc"


def sha(label: str) -> str:
    return hashlib.sha256(f"T22_A1_DOMAIN_WORKLOAD_PLAN_SYNTHETIC:{label}".encode()).hexdigest()


ENDPOINT = {
    "source_commit": SOURCE_COMMIT,
    "run_id": RUN_ID,
    "content_sha256": sha("endpoint-manifest"),
    "domains": [
        {
            "domain_id": f"domain-{number}",
            "overlay_ip": f"100.64.40.{number}",
            "agent_control_port": 29000,
            "etcd_client_port": 2379,
            "etcd_peer_port": 2380,
            "openbao_api_port": 8200,
            "openbao_cluster_port": 8201,
            "bind_exact_overlay_ip_only": True,
            "public_listener_allowed": False,
        }
        for number in (1, 2, 3)
    ],
}

EXECUTION = {
    "source_commit": SOURCE_COMMIT,
    "run_id": RUN_ID,
    "content_sha256": sha("execution"),
    "private_runtime": {
        "private_endpoint_manifest_content_sha256": ENDPOINT["content_sha256"],
        "runtime_credential_manifest_content_sha256": sha("credential-manifest"),
    },
    "topology": {
        "domains": [
            {
                "domain_id": f"domain-{number}",
                "role": "COORDINATOR_VOTER" if number == 1 else "PARTICIPANT_VOTER",
                "etcd_member": f"etcd-{number}",
                "openbao_member": f"bao-{number}",
            }
            for number in (1, 2, 3)
        ],
    },
    "fault": {"target_domain_id": "domain-3"},
    "authorization": {"maximum_runtime_seconds": 3600, "automatic_retry_allowed": False},
    "budget": {"maximum_spend_usd_cents": 0},
    "expires_at": "2026-07-22T23:00:00Z",
}


def placed_identity(root: Path, prefix: str) -> dict:
    return {
        "certificate_path": str(root / f"{prefix}.crt"),
        "private_key_path": str(root / f"{prefix}.key"),
        "certificate_sha256": sha(f"certificate:{root}:{prefix}"),
        "spki_sha256": sha(f"spki:{root}:{prefix}"),
        "private_key_spki_sha256": sha(f"spki:{root}:{prefix}"),
        "private_key_file_mode": "0600",
        "certificate_private_key_match_verified": True,
    }


def readiness(number: int) -> dict:
    domain_id = f"domain-{number}"
    root = Path(f"/private/t22-a1/{RUN_ID}/{domain_id}")
    credentials = root / "credentials"
    endpoint = ENDPOINT["domains"][number - 1]
    coordinator = None
    if number == 1:
        coordinator = {
            "client_identity": placed_identity(credentials, "coordinator"),
            "runtime_public_key_path": str(credentials / "coordinator-runtime.pub"),
            "runtime_private_key_path": str(credentials / "coordinator-runtime"),
        }
    coordinator_trust = {
        "certificate_path": str(credentials / "coordinator.crt"),
        "certificate_sha256": sha(f"certificate:{credentials}:coordinator"),
        "spki_sha256": sha(f"spki:{credentials}:coordinator"),
        "runtime_public_key_path": str(credentials / "coordinator-runtime.pub"),
        "runtime_public_key_sha256": sha("coordinator-runtime"),
    }
    return {
        "source_commit": SOURCE_COMMIT,
        "run_id": RUN_ID,
        "domain_id": domain_id,
        "content_sha256": sha(f"readiness:{number}"),
        "bindings": {
            "private_endpoint_manifest_content_sha256": ENDPOINT["content_sha256"],
            "runtime_credential_manifest_content_sha256": EXECUTION["private_runtime"]["runtime_credential_manifest_content_sha256"],
        },
        "endpoint_binding": {
            key: endpoint[key]
            for key in (
                "overlay_ip", "agent_control_port", "etcd_client_port", "etcd_peer_port",
                "openbao_api_port", "openbao_cluster_port",
            )
        },
        "toolchain": {
            "executables": [
                {"name": name, "path": f"/private/tools/{domain_id}/{name}", "sha256": sha(f"tool:{number}:{name}")}
                for name in module.TOOL_NAMES
            ],
        },
        "local_paths": {
            "domain_private_root": str(root),
            "etcd_data_dir": str(root / "etcd"),
            "openbao_data_dir": str(root / "openbao"),
            "owned_logs_dir": str(root / "logs"),
            "domain_evidence_dir": str(root / "evidence"),
            "execution_reservation_dir": str(root / "execution-reservations"),
        },
        "credential_placement": {
            "mode": "OWNER_MEDIATED_OUT_OF_BAND_EXACT_HASH_PLACEMENT",
            "all_paths_local_to_attested_host": True,
            "ca_certificate_path": str(credentials / "ca.crt"),
            "ca_certificate_sha256": sha(f"ca:{number}"),
            "domain_identity": placed_identity(credentials, "domain"),
            "domain_operator_public_key_path": str(credentials / "domain-operator.pub"),
            "domain_operator_private_key_path": str(credentials / "domain-operator"),
            "coordinator_trust_material": coordinator_trust,
            "coordinator_material": coordinator,
        },
    }


READINESS = [readiness(number) for number in (1, 2, 3)]
PLANS = [module.build_plan(EXECUTION, ENDPOINT, packet) for packet in READINESS]
assert [plan["domain_id"] for plan in PLANS] == list(module.DOMAIN_IDS)
assert all(module.validate_plan(plan, EXECUTION, ENDPOINT, packet) == plan for plan, packet in zip(PLANS, READINESS))
assert all(plan["network"]["public_listener_allowed"] is False for plan in PLANS)
assert all(plan["processes"]["environment_inherits_parent"] is False for plan in PLANS)
assert all("sh" not in [Path(argument).name for argument in plan["processes"]["etcd"]["argv"]] for plan in PLANS)
assert all("--peer-client-cert-auth=true" in plan["processes"]["etcd"]["argv"] for plan in PLANS)
assert all("--client-cert-auth=true" in plan["processes"]["etcd"]["argv"] for plan in PLANS)
assert 'tls_require_and_verify_client_cert = true' in PLANS[0]["processes"]["openbao"]["config_text"]
assert "retry_join" not in PLANS[0]["processes"]["openbao"]["config_text"]
assert all("retry_join" in plan["processes"]["openbao"]["config_text"] for plan in PLANS[1:])
assert PLANS[0]["credentials"]["coordinator_material"] is not None
assert PLANS[1]["credentials"]["coordinator_material"] is None
assert all(plan["credentials"]["coordinator_trust_material"] is not None for plan in PLANS)
assert PLANS[2]["role"]["this_domain_is_fault_target"] is True
assert "STOP_OWNED_SERVICE_SET" in PLANS[2]["command_policy"]["allowed_commands"]
assert "STOP_OWNED_SERVICE_SET" not in PLANS[0]["command_policy"]["allowed_commands"]


def rejected_inputs(execution: dict, endpoint: dict, packet: dict) -> None:
    try:
        module.build_plan(execution, endpoint, packet)
    except module.SafeFailure:
        return
    raise AssertionError("unsafe workload-plan inputs admitted")


def mutate_input(target: str, mutation) -> None:  # noqa: ANN001
    execution = copy.deepcopy(EXECUTION)
    endpoint = copy.deepcopy(ENDPOINT)
    packet = copy.deepcopy(READINESS[0])
    mutation({"execution": execution, "endpoint": endpoint, "readiness": packet}[target])
    rejected_inputs(execution, endpoint, packet)


input_mutations = (
    ("execution", lambda x: x.update(source_commit="b" * 40)),
    ("execution", lambda x: x.update(content_sha256="0" * 64)),
    ("endpoint", lambda x: x.update(run_id="t22-a1-other")),
    ("endpoint", lambda x: x.update(content_sha256=sha("other-endpoint"))),
    ("readiness", lambda x: x.update(source_commit="b" * 40)),
    ("readiness", lambda x: x.update(domain_id="domain-4")),
    ("readiness", lambda x: x["bindings"].update(private_endpoint_manifest_content_sha256=sha("other-endpoint"))),
    ("readiness", lambda x: x["bindings"].update(runtime_credential_manifest_content_sha256=sha("other-credential"))),
    ("endpoint", lambda x: x["domains"].reverse()),
    ("endpoint", lambda x: x["domains"][0].update(overlay_ip="100.64.40.9")),
    ("endpoint", lambda x: x["domains"][0].update(etcd_client_port=12379)),
    ("endpoint", lambda x: x["domains"][0].update(bind_exact_overlay_ip_only=False)),
    ("endpoint", lambda x: x["domains"][0].update(public_listener_allowed=True)),
    ("execution", lambda x: x["topology"]["domains"].reverse()),
    ("execution", lambda x: x["topology"]["domains"][0].update(etcd_member="etcd-other")),
    ("execution", lambda x: x["fault"].update(target_domain_id="domain-1")),
    ("execution", lambda x: x["authorization"].update(maximum_runtime_seconds=14401)),
    ("execution", lambda x: x["authorization"].update(automatic_retry_allowed=True)),
    ("execution", lambda x: x["budget"].update(maximum_spend_usd_cents=100001)),
    ("execution", lambda x: x.update(expires_at="not-a-time")),
    ("readiness", lambda x: x["toolchain"]["executables"].reverse()),
    ("readiness", lambda x: x["toolchain"]["executables"][0].update(path="relative/python3")),
    ("readiness", lambda x: x["toolchain"]["executables"][0].update(sha256="0" * 64)),
    ("readiness", lambda x: x["local_paths"].update(etcd_data_dir="/private/other/etcd")),
    ("readiness", lambda x: x["credential_placement"].update(mode="CENTRAL_ONLY")),
    ("readiness", lambda x: x["credential_placement"].update(all_paths_local_to_attested_host=False)),
    ("readiness", lambda x: x["credential_placement"]["domain_identity"].update(certificate_sha256="0" * 64)),
    ("readiness", lambda x: x["credential_placement"]["domain_identity"].update(private_key_spki_sha256=sha("other-private-key"))),
    ("readiness", lambda x: x["credential_placement"].update(coordinator_trust_material=None)),
    ("readiness", lambda x: x["credential_placement"]["coordinator_trust_material"].update(certificate_sha256="0" * 64)),
    ("readiness", lambda x: x["credential_placement"].update(coordinator_material=None)),
)
for target, mutation in input_mutations:
    mutate_input(target, mutation)


def rejected_plan(mutation, recalc: bool = True) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(PLANS[0])
    mutation(candidate)
    if recalc:
        candidate.pop("content_sha256", None)
        candidate["content_sha256"] = module.digest(candidate)
    try:
        module.validate_plan(candidate, EXECUTION, ENDPOINT, READINESS[0])
    except module.SafeFailure:
        return
    raise AssertionError("unsafe workload plan mutation admitted")


plan_mutations = (
    lambda x: x["network"].update(public_listener_allowed=True),
    lambda x: x["processes"].update(environment_inherits_parent=True),
    lambda x: x["processes"]["environment"].update(HTTPS_PROXY="https://proxy.invalid"),
    lambda x: x["processes"]["etcd"]["argv"].append("--listen-client-urls=https://0.0.0.0:2379"),
    lambda x: x["processes"]["openbao"].update(config_text=x["processes"]["openbao"]["config_text"].replace("tls_require_and_verify_client_cert = true", "tls_disable = true")),
    lambda x: x["command_policy"].update(arbitrary_command_or_shell_allowed=True),
    lambda x: x["command_policy"]["allowed_commands"].append("RUN_SHELL"),
    lambda x: x["workload"].update(bootstrap_secret_persistence_allowed=True),
    lambda x: x["credentials"].update(domain_private_key_path="/tmp/other.key"),
    lambda x: x["credentials"]["coordinator_trust_material"].update(runtime_public_key_sha256=sha("other-runtime-key")),
    lambda x: x["claims"].update(plan_is_execution_authority=True),
    lambda x: x["claims"].update(production_admissible=True),
)
for mutation in plan_mutations:
    rejected_plan(mutation)
rejected_plan(lambda x: x.update(content_sha256=sha("forged")), recalc=False)

domain_two = copy.deepcopy(READINESS[1])
domain_two["credential_placement"]["coordinator_material"] = copy.deepcopy(READINESS[0]["credential_placement"]["coordinator_material"])
rejected_inputs(EXECUTION, ENDPOINT, domain_two)

status = module.status()
assert status["status"] == "OFFLINE_PRIVATE_WORKLOAD_PLAN_COMPILER_READY_EXECUTION_ACTIVATION_GATE_CLOSED"
assert status["real_private_inputs_read"] == status["credential_files_read"] == 0
assert status["network_accessed"] is False
assert status["listeners_started"] == status["processes_started"] == status["services_started"] == 0
assert status["faults_injected"] == status["spend_usd_cents"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

negative_count = len(input_mutations) + len(plan_mutations) + 2
print("t22_a1_domain_workload_plan_check\tpass")
print("synthetic_valid_domain_plan_count\t3")
print(f"directed_negative_test_count\t{negative_count}")
print("real_private_inputs_read\t0")
print("credential_files_read\t0")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("processes_started\t0")
print("services_started\t0")
print("faults_injected\t0")
print("production_admissible\tfalse")
