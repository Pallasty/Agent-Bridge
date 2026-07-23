"""Pure compiler for one private T22-A1 domain workload plan.

The compiler consumes already-validated private values and emits exact argv,
environment, path, TLS, command, and workload bindings.  It performs no file,
credential, process, listener, socket, service, fault, or provider operation.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-workload-plan/v1\0"
DOMAIN_IDS = ("domain-1", "domain-2", "domain-3")
TOOL_NAMES = ("python3", "etcd", "etcdctl", "bao", "openssl", "ssh-keygen")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
OID40 = re.compile(r"^[0-9a-f]{40}$")


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(PLAN_DOMAIN + canonical(value)).hexdigest()


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value)) and value != "0" * 64


def private_absolute_path(value: object) -> str:
    require(isinstance(value, str) and Path(value).is_absolute(), "E_WORKLOAD_PLAN_ABSOLUTE_PATH")
    require("\n" not in value and "\r" not in value and "\x00" not in value, "E_WORKLOAD_PLAN_PATH_CONTROL")
    resolved = Path(value).resolve(strict=False)
    repository = ROOT.resolve()
    require(repository not in (resolved, *resolved.parents) and resolved not in repository.parents, "E_WORKLOAD_PLAN_PATH_SCOPE")
    return str(resolved)


def hcl_string(value: str) -> str:
    require("\n" not in value and "\r" not in value and "\x00" not in value, "E_WORKLOAD_PLAN_HCL_VALUE")
    return json.dumps(value)


def https(ip: str, port: int) -> str:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError as error:
        raise SafeFailure("E_WORKLOAD_PLAN_IP") from error
    host = f"[{address.compressed}]" if address.version == 6 else address.compressed
    return f"https://{host}:{port}"


def socket_address(ip: str, port: int) -> str:
    address = ipaddress.ip_address(ip)
    host = f"[{address.compressed}]" if address.version == 6 else address.compressed
    return f"{host}:{port}"


def command_allowlist(domain_id: str, fault_target_domain_id: str) -> list[str]:
    common_start = ["PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE"]
    common_end = ["CLEANUP_OWNED_PROCESSES", "TERMINAL_STATUS"]
    if domain_id == "domain-1":
        middle = [
            "EXECUTE_AUTHORIZE_CONSUME", "CREATE_PREFAULT_TRANSIT_SIGNATURE",
            "VERIFY_SURVIVING_QUORUM_AND_STATE", "VERIFY_POSTFAULT_TRANSIT_SIGNATURE",
        ]
    elif domain_id == fault_target_domain_id:
        middle = ["STOP_OWNED_SERVICE_SET", "RESTART_OWNED_SERVICE_SET", "VERIFY_TARGET_REJOIN"]
    else:
        middle = ["VERIFY_SURVIVING_QUORUM_AND_STATE"]
    return [*common_start, *middle, *common_end]


def openbao_config(
    domain_id: str,
    domain_root: str,
    endpoint: dict,
    leader: dict,
    credentials: dict,
) -> str:
    data_dir = private_absolute_path(str(Path(domain_root) / "openbao"))
    certificate = private_absolute_path(credentials["domain_identity"]["certificate_path"])
    private_key = private_absolute_path(credentials["domain_identity"]["private_key_path"])
    ca_certificate = private_absolute_path(credentials["ca_certificate_path"])
    require(
        is_sha256(credentials.get("ca_certificate_sha256"))
        and is_sha256(credentials["domain_identity"].get("certificate_sha256"))
        and is_sha256(credentials["domain_identity"].get("spki_sha256")),
        "E_WORKLOAD_PLAN_CREDENTIAL_DIGEST",
    )
    require(
        credentials["domain_identity"].get("private_key_spki_sha256")
        == credentials["domain_identity"]["spki_sha256"]
        and credentials["domain_identity"].get("certificate_private_key_match_verified") is True
        and credentials["domain_identity"].get("private_key_file_mode") == "0600",
        "E_WORKLOAD_PLAN_CREDENTIAL_KEY_BINDING",
    )
    api = https(endpoint["overlay_ip"], endpoint["openbao_api_port"])
    cluster = https(endpoint["overlay_ip"], endpoint["openbao_cluster_port"])
    lines = [
        "ui = false",
        "disable_mlock = true",
        'log_level = "warn"',
        f"api_addr = {hcl_string(api)}",
        f"cluster_addr = {hcl_string(cluster)}",
        'storage "raft" {',
        f"  path = {hcl_string(data_dir)}",
        f"  node_id = {hcl_string('bao-' + domain_id[-1])}",
    ]
    if domain_id != "domain-1":
        lines.extend([
            "  retry_join {",
            f"    leader_api_addr = {hcl_string(https(leader['overlay_ip'], leader['openbao_api_port']))}",
            f"    leader_ca_cert_file = {hcl_string(ca_certificate)}",
            f"    leader_client_cert_file = {hcl_string(certificate)}",
            f"    leader_client_key_file = {hcl_string(private_key)}",
            "  }",
        ])
    lines.extend([
        "}",
        'listener "tcp" {',
        f"  address = {hcl_string(socket_address(endpoint['overlay_ip'], endpoint['openbao_api_port']))}",
        f"  cluster_address = {hcl_string(socket_address(endpoint['overlay_ip'], endpoint['openbao_cluster_port']))}",
        f"  tls_cert_file = {hcl_string(certificate)}",
        f"  tls_key_file = {hcl_string(private_key)}",
        f"  tls_client_ca_file = {hcl_string(ca_certificate)}",
        "  tls_require_and_verify_client_cert = true",
        '  tls_min_version = "tls12"',
        "}",
    ])
    return "\n".join(lines) + "\n"


def _compile(execution: dict, endpoint_manifest: dict, readiness: dict) -> dict:
    require(isinstance(execution, dict) and isinstance(endpoint_manifest, dict) and isinstance(readiness, dict), "E_WORKLOAD_PLAN_INPUT")
    source_commit = execution.get("source_commit")
    run_id = execution.get("run_id")
    execution_sha256 = execution.get("content_sha256")
    require(isinstance(source_commit, str) and bool(OID40.fullmatch(source_commit)), "E_WORKLOAD_PLAN_SOURCE")
    require(isinstance(run_id, str) and run_id and is_sha256(execution_sha256), "E_WORKLOAD_PLAN_EXECUTION")
    domain_id = readiness.get("domain_id")
    require(domain_id in DOMAIN_IDS, "E_WORKLOAD_PLAN_DOMAIN")
    require(readiness.get("source_commit") == source_commit and readiness.get("run_id") == run_id, "E_WORKLOAD_PLAN_READINESS_RUN")
    require(is_sha256(readiness.get("content_sha256")), "E_WORKLOAD_PLAN_READINESS_DIGEST")
    require(endpoint_manifest.get("source_commit") == source_commit and endpoint_manifest.get("run_id") == run_id, "E_WORKLOAD_PLAN_ENDPOINT_RUN")
    private_runtime = execution.get("private_runtime")
    require(isinstance(private_runtime, dict), "E_WORKLOAD_PLAN_PRIVATE_RUNTIME")
    require(endpoint_manifest.get("content_sha256") == private_runtime.get("private_endpoint_manifest_content_sha256"), "E_WORKLOAD_PLAN_ENDPOINT_BINDING")
    require(readiness.get("bindings", {}).get("private_endpoint_manifest_content_sha256") == endpoint_manifest.get("content_sha256"), "E_WORKLOAD_PLAN_READINESS_ENDPOINT")
    require(readiness.get("bindings", {}).get("runtime_credential_manifest_content_sha256") == private_runtime.get("runtime_credential_manifest_content_sha256"), "E_WORKLOAD_PLAN_READINESS_CREDENTIAL")

    domains = endpoint_manifest.get("domains")
    require(isinstance(domains, list) and [row.get("domain_id") for row in domains] == list(DOMAIN_IDS), "E_WORKLOAD_PLAN_ENDPOINT_SET")
    endpoints = {row["domain_id"]: row for row in domains}
    endpoint = endpoints[domain_id]
    require(readiness.get("endpoint_binding", {}).get("overlay_ip") == endpoint.get("overlay_ip"), "E_WORKLOAD_PLAN_OVERLAY_BINDING")
    require(all(
        readiness["endpoint_binding"].get(field) == endpoint.get(field)
        for field in ("agent_control_port", "etcd_client_port", "etcd_peer_port", "openbao_api_port", "openbao_cluster_port")
    ), "E_WORKLOAD_PLAN_PORT_BINDING")
    require(endpoint.get("bind_exact_overlay_ip_only") is True and endpoint.get("public_listener_allowed") is False, "E_WORKLOAD_PLAN_LISTENER_SCOPE")

    topology = execution.get("topology", {}).get("domains")
    require(isinstance(topology, list) and [row.get("domain_id") for row in topology] == list(DOMAIN_IDS), "E_WORKLOAD_PLAN_TOPOLOGY")
    topology_row = topology[int(domain_id[-1]) - 1]
    require(topology_row.get("etcd_member") == f"etcd-{domain_id[-1]}" and topology_row.get("openbao_member") == f"bao-{domain_id[-1]}", "E_WORKLOAD_PLAN_MEMBER_BINDING")
    fault_target = execution.get("fault", {}).get("target_domain_id")
    require(fault_target in {"domain-2", "domain-3"}, "E_WORKLOAD_PLAN_FAULT_TARGET")
    authorization = execution.get("authorization", {})
    budget = execution.get("budget", {})
    maximum_runtime_seconds = authorization.get("maximum_runtime_seconds")
    maximum_spend_usd_cents = budget.get("maximum_spend_usd_cents")
    require(
        isinstance(maximum_runtime_seconds, int) and 0 < maximum_runtime_seconds <= 14400
        and authorization.get("automatic_retry_allowed") is False,
        "E_WORKLOAD_PLAN_RUNTIME_LIMIT",
    )
    require(
        isinstance(maximum_spend_usd_cents, int) and 0 <= maximum_spend_usd_cents <= 100000,
        "E_WORKLOAD_PLAN_SPEND_LIMIT",
    )
    expires_at = execution.get("expires_at")
    require(isinstance(expires_at, str) and expires_at.endswith("Z"), "E_WORKLOAD_PLAN_EXPIRY")

    tool_rows = readiness.get("toolchain", {}).get("executables")
    require(isinstance(tool_rows, list) and [row.get("name") for row in tool_rows] == list(TOOL_NAMES), "E_WORKLOAD_PLAN_TOOL_SET")
    tools = {
        row["name"]: {"path": private_absolute_path(row["path"]), "sha256": row["sha256"]}
        for row in tool_rows
    }
    require(all(is_sha256(row["sha256"]) for row in tools.values()), "E_WORKLOAD_PLAN_TOOL_DIGEST")
    local = readiness.get("local_paths", {})
    root = private_absolute_path(local.get("domain_private_root"))
    require(local.get("etcd_data_dir") == str(Path(root) / "etcd"), "E_WORKLOAD_PLAN_ETCD_ROOT")
    require(local.get("openbao_data_dir") == str(Path(root) / "openbao"), "E_WORKLOAD_PLAN_OPENBAO_ROOT")
    require(local.get("owned_logs_dir") == str(Path(root) / "logs"), "E_WORKLOAD_PLAN_LOG_ROOT")
    require(local.get("domain_evidence_dir") == str(Path(root) / "evidence"), "E_WORKLOAD_PLAN_EVIDENCE_ROOT")
    credentials = readiness.get("credential_placement", {})
    require(credentials.get("mode") == "OWNER_MEDIATED_OUT_OF_BAND_EXACT_HASH_PLACEMENT", "E_WORKLOAD_PLAN_CREDENTIAL_MODE")
    require(credentials.get("all_paths_local_to_attested_host") is True, "E_WORKLOAD_PLAN_CREDENTIAL_LOCALITY")

    client_url = https(endpoint["overlay_ip"], endpoint["etcd_client_port"])
    peer_url = https(endpoint["overlay_ip"], endpoint["etcd_peer_port"])
    initial_cluster = ",".join(
        f"etcd-{row['domain_id'][-1]}={https(row['overlay_ip'], row['etcd_peer_port'])}"
        for row in domains
    )
    certificate = private_absolute_path(credentials["domain_identity"]["certificate_path"])
    private_key = private_absolute_path(credentials["domain_identity"]["private_key_path"])
    ca_certificate = private_absolute_path(credentials["ca_certificate_path"])
    etcd_argv = [
        tools["etcd"]["path"], f"--name={topology_row['etcd_member']}",
        f"--data-dir={local['etcd_data_dir']}", f"--listen-client-urls={client_url}",
        f"--advertise-client-urls={client_url}", f"--listen-peer-urls={peer_url}",
        f"--initial-advertise-peer-urls={peer_url}", f"--initial-cluster={initial_cluster}",
        f"--initial-cluster-token=t22-a1-{execution_sha256[:16]}", "--initial-cluster-state=new",
        f"--cert-file={certificate}", f"--key-file={private_key}",
        f"--trusted-ca-file={ca_certificate}", "--client-cert-auth=true",
        f"--peer-cert-file={certificate}", f"--peer-key-file={private_key}",
        f"--peer-trusted-ca-file={ca_certificate}", "--peer-client-cert-auth=true",
        "--logger=zap", "--log-level=warn", "--log-outputs=stderr",
    ]
    config_path = str(Path(root) / "config" / "openbao.hcl")
    config_text = openbao_config(domain_id, root, endpoint, endpoints["domain-1"], credentials)
    coordinator_trust = credentials.get("coordinator_trust_material")
    require(isinstance(coordinator_trust, dict), "E_WORKLOAD_PLAN_COORDINATOR_TRUST")
    coordinator_trust_paths = {
        "certificate_path": private_absolute_path(coordinator_trust.get("certificate_path")),
        "certificate_sha256": coordinator_trust.get("certificate_sha256"),
        "spki_sha256": coordinator_trust.get("spki_sha256"),
        "runtime_public_key_path": private_absolute_path(coordinator_trust.get("runtime_public_key_path")),
        "runtime_public_key_sha256": coordinator_trust.get("runtime_public_key_sha256"),
    }
    require(
        all(is_sha256(coordinator_trust_paths[field]) for field in (
            "certificate_sha256", "spki_sha256", "runtime_public_key_sha256",
        )),
        "E_WORKLOAD_PLAN_COORDINATOR_TRUST_DIGEST",
    )
    coordinator = credentials.get("coordinator_material")
    if domain_id == "domain-1":
        require(isinstance(coordinator, dict), "E_WORKLOAD_PLAN_COORDINATOR_MATERIAL")
        coordinator_paths = {
            "certificate_path": private_absolute_path(coordinator["client_identity"]["certificate_path"]),
            "private_key_path": private_absolute_path(coordinator["client_identity"]["private_key_path"]),
            "certificate_sha256": coordinator["client_identity"]["certificate_sha256"],
            "spki_sha256": coordinator["client_identity"]["spki_sha256"],
            "private_key_spki_sha256": coordinator["client_identity"]["private_key_spki_sha256"],
            "runtime_public_key_path": private_absolute_path(coordinator["runtime_public_key_path"]),
            "runtime_private_key_path": private_absolute_path(coordinator["runtime_private_key_path"]),
        }
        require(
            is_sha256(coordinator_paths["certificate_sha256"])
            and is_sha256(coordinator_paths["spki_sha256"]),
            "E_WORKLOAD_PLAN_COORDINATOR_CREDENTIAL_DIGEST",
        )
        require(
            coordinator_paths["private_key_spki_sha256"] == coordinator_paths["spki_sha256"]
            and coordinator["client_identity"].get("certificate_private_key_match_verified") is True
            and coordinator["client_identity"].get("private_key_file_mode") == "0600",
            "E_WORKLOAD_PLAN_COORDINATOR_KEY_BINDING",
        )
        require(
            coordinator_paths["certificate_path"] == coordinator_trust_paths["certificate_path"]
            and coordinator_paths["certificate_sha256"] == coordinator_trust_paths["certificate_sha256"]
            and coordinator_paths["spki_sha256"] == coordinator_trust_paths["spki_sha256"]
            and coordinator_paths["runtime_public_key_path"] == coordinator_trust_paths["runtime_public_key_path"],
            "E_WORKLOAD_PLAN_COORDINATOR_TRUST_CROSS_BINDING",
        )
    else:
        require(coordinator is None, "E_WORKLOAD_PLAN_COORDINATOR_SCOPE")
        coordinator_paths = None

    process_environment = {
        "HOME": root,
        "LANG": "C",
        "LC_ALL": "C",
        "NO_PROXY": ",".join(row["overlay_ip"] for row in domains),
    }
    workload_key = f"/agent-bridge/t22-a1/authority/{execution_sha256}"
    authorized_value = "AUTHORIZED_UNCLAIMED:" + execution_sha256
    consumed_value = "CONSUMED_FOR_EXACT_RUN:" + execution_sha256
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_workload_plan.v1",
        "packet_kind": "T22_A1_PRIVATE_SOURCE_BOUND_DOMAIN_WORKLOAD_PLAN",
        "run_id": run_id,
        "source_commit": source_commit,
        "domain_id": domain_id,
        "bindings": {
            "execution_contract_sha256": execution_sha256,
            "private_endpoint_manifest_content_sha256": endpoint_manifest["content_sha256"],
            "runtime_credential_manifest_content_sha256": private_runtime["runtime_credential_manifest_content_sha256"],
            "runtime_readiness_packet_sha256": readiness["content_sha256"],
        },
        "role": {
            "topology_role": topology_row["role"],
            "fault_target_domain_id": fault_target,
            "this_domain_is_fault_target": domain_id == fault_target,
        },
        "limits": {
            "execution_expires_at": expires_at,
            "maximum_runtime_seconds": maximum_runtime_seconds,
            "maximum_spend_usd_cents": maximum_spend_usd_cents,
            "automatic_retry_allowed": False,
        },
        "network": {
            "overlay_ip": endpoint["overlay_ip"],
            "agent_control_endpoint": https(endpoint["overlay_ip"], endpoint["agent_control_port"]),
            "etcd_client_endpoint": client_url,
            "etcd_peer_endpoint": peer_url,
            "openbao_api_endpoint": https(endpoint["overlay_ip"], endpoint["openbao_api_port"]),
            "openbao_cluster_endpoint": https(endpoint["overlay_ip"], endpoint["openbao_cluster_port"]),
            "all_etcd_client_endpoints": [https(row["overlay_ip"], row["etcd_client_port"]) for row in domains],
            "bind_exact_overlay_ip_only": True,
            "public_listener_allowed": False,
        },
        "tools": tools,
        "paths": {
            "domain_private_root": root,
            "etcd_data_dir": local["etcd_data_dir"],
            "openbao_data_dir": local["openbao_data_dir"],
            "owned_logs_dir": local["owned_logs_dir"],
            "domain_evidence_dir": local["domain_evidence_dir"],
            "config_dir": str(Path(root) / "config"),
            "execution_reservation_dir": local["execution_reservation_dir"],
        },
        "credentials": {
            "ca_certificate_path": ca_certificate,
            "ca_certificate_sha256": credentials["ca_certificate_sha256"],
            "domain_certificate_path": certificate,
            "domain_private_key_path": private_key,
            "domain_certificate_sha256": credentials["domain_identity"]["certificate_sha256"],
            "domain_spki_sha256": credentials["domain_identity"]["spki_sha256"],
            "domain_private_key_spki_sha256": credentials["domain_identity"]["private_key_spki_sha256"],
            "domain_operator_public_key_path": private_absolute_path(credentials["domain_operator_public_key_path"]),
            "domain_operator_private_key_path": private_absolute_path(credentials["domain_operator_private_key_path"]),
            "coordinator_trust_material": coordinator_trust_paths,
            "coordinator_material": coordinator_paths,
        },
        "processes": {
            "environment": process_environment,
            "environment_inherits_parent": False,
            "etcd": {
                "argv": etcd_argv,
                "stdin": "DEVNULL",
                "stdout_log_path": str(Path(local["owned_logs_dir"]) / "etcd.stdout.log"),
                "stderr_log_path": str(Path(local["owned_logs_dir"]) / "etcd.stderr.log"),
            },
            "openbao": {
                "argv": [tools["bao"]["path"], "server", f"-config={config_path}"],
                "config_path": config_path,
                "config_content_sha256": hashlib.sha256(config_text.encode()).hexdigest(),
                "config_text": config_text,
                "stdin": "DEVNULL",
                "stdout_log_path": str(Path(local["owned_logs_dir"]) / "openbao.stdout.log"),
                "stderr_log_path": str(Path(local["owned_logs_dir"]) / "openbao.stderr.log"),
            },
        },
        "workload": {
            "authority_key": workload_key,
            "authorized_unclaimed_value": authorized_value,
            "authorized_unclaimed_value_sha256": hashlib.sha256(authorized_value.encode()).hexdigest(),
            "consumed_value": consumed_value,
            "consumed_value_sha256": hashlib.sha256(consumed_value.encode()).hexdigest(),
            "linearizable_read_required": True,
            "exact_compare_and_swap_required": True,
            "replay_must_be_rejected": True,
            "openbao_transit_mount": "t22-a1-transit",
            "openbao_transit_key": "t22-a1-ed25519",
            "openbao_transit_key_type": "ed25519",
            "bootstrap_secret_transport": "BOUNDED_MTLS_SECRET_FRAME_MEMORY_ONLY",
            "bootstrap_secret_persistence_allowed": False,
        },
        "command_policy": {
            "allowed_commands": command_allowlist(domain_id, fault_target),
            "arbitrary_command_or_shell_allowed": False,
            "automatic_retry_allowed": False,
            "owned_processes_only": True,
            "owned_run_root_only": True,
            "host_global_network_mutation_allowed": False,
            "host_reboot_or_power_action_allowed": False,
        },
        "claims": {
            "plan_is_execution_authority": False,
            "raw_endpoints_or_paths_publicly_emittable": False,
            "production_admissible": False,
        },
    }
    value["content_sha256"] = digest(value)
    return value


def validate_plan(value: object, execution: dict, endpoint_manifest: dict, readiness: dict) -> dict:
    require(isinstance(value, dict), "E_WORKLOAD_PLAN_SHAPE")
    expected = _compile(execution, endpoint_manifest, readiness)
    require(value == expected, "E_WORKLOAD_PLAN_EXACT_RECONSTRUCTION")
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256", None)
    require(claimed == digest(unsigned), "E_WORKLOAD_PLAN_DIGEST")
    return value


def build_plan(execution: dict, endpoint_manifest: dict, readiness: dict) -> dict:
    value = _compile(execution, endpoint_manifest, readiness)
    return validate_plan(value, execution, endpoint_manifest, readiness)


def status() -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_workload_plan_status.v0",
        "status": "OFFLINE_PRIVATE_WORKLOAD_PLAN_COMPILER_READY_EXECUTION_ACTIVATION_GATE_CLOSED",
        "real_private_inputs_read": 0,
        "credential_files_read": 0,
        "network_accessed": False,
        "listeners_started": 0,
        "processes_started": 0,
        "services_started": 0,
        "faults_injected": 0,
        "spend_usd_cents": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }


if __name__ == "__main__":
    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
