#!/usr/bin/env python3
"""Independent pack checker for the runner-v1 offline doubles implementation."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

MODULE_NAME = (
    "biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_offline_authority_and_adapter_doubles_v1"
)
FROZEN_MODULE_NAME = (
    "biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_authority_and_adapter_contract_v1"
)
frozen_contract = None

EXPECTED_ADAPTER_IDS = (
    "SPANNER_AUTHORITY_ADAPTER",
    "CLOUD_KMS_SIGNER_ADAPTER",
    "MANAGED_FAULT_PROXY_ADAPTER",
    "MANAGED_EVIDENCE_COLLECTOR_ADAPTER",
    "ETCD_AUTHORITY_ADAPTER",
    "OPENBAO_TRANSIT_ADAPTER",
    "EXTERNAL_RESTORE_WITNESS_ADAPTER",
    "LAB_FAULT_CONTROLLER_ADAPTER",
    "SELF_HOSTED_EVIDENCE_COLLECTOR_ADAPTER",
)

EXPECTED_STOP_CONTROL_IDS = (
    "CAPABILITY_FENCE_CONTROL",
    "FAULT_DISARM_AND_EGRESS_ISOLATION_CONTROL",
    "CREDENTIAL_BROKER_REVOCATION_CONTROL",
    "DURABLE_EVIDENCE_RETENTION_CONTROL",
    "SCOPED_RESOURCE_CLEANUP_CONTROL",
)

EXPECTED_STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_OFFLINE_AUTHORITY_VERIFIER_"
    "AND_ADAPTER_DOUBLES_IMPLEMENTED_NO_PROVIDER_NO_CREDENTIAL_NO_PERMIT"
)
EXPECTED_DECISION = (
    "OFFLINE_AUTHORITY_VERIFIER_AND_ADAPTER_DOUBLES_PASS_"
    "RUNTIME_EXECUTION_REMAINS_BLOCKED"
)


class PackError(ValueError):
    pass


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise PackError(f"{code}: {message}")


def load_module(path: Path, module_name: str) -> object:
    spec = importlib.util.spec_from_file_location(module_name, path)
    require(
        spec is not None and spec.loader is not None,
        "E_SOURCE_LOAD",
        f"cannot create module spec for {path}",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def load_json(path: Path) -> object:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PackError(f"E_JSON_LOAD: cannot read {path}: {exc}") from exc

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            require(key not in result, "E_JSON_DUPLICATE", f"duplicate key {key} in {path}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                PackError(f"E_JSON_NONFINITE: {token} in {path}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackError(f"E_JSON_PARSE: cannot parse {path}: {exc}") from exc
    require(
        raw == frozen_contract.canonical_bytes(value),
        "E_JSON_CANONICAL",
        f"noncanonical JSON bytes in {path}",
    )
    return value


def validate_synthetic_fixture(fixture: dict[str, object]) -> None:
    require(
        set(fixture)
        == {
            "adapter_ids",
            "authority_fixture_count",
            "boundary",
            "control_evidence_kinds_per_fixture",
            "date",
            "private_capability_fixture",
            "schema",
            "scope_authority_roles_per_fixture",
            "signature_algorithm",
            "stop_control_ids",
            "stop_failure_injection_ids",
            "timestamps",
        },
        "E_FIXTURE_KEYS",
        "synthetic fixture key closure drift",
    )
    require(tuple(fixture["adapter_ids"]) == EXPECTED_ADAPTER_IDS, "E_FIXTURE_ADAPTERS", "adapter ids drift")
    require(fixture["authority_fixture_count"] == 9, "E_FIXTURE_COUNT", "authority fixture count drift")
    require(tuple(fixture["stop_control_ids"]) == EXPECTED_STOP_CONTROL_IDS, "E_FIXTURE_STOP", "stop ids drift")
    require(tuple(fixture["stop_failure_injection_ids"]) == EXPECTED_STOP_CONTROL_IDS, "E_FIXTURE_STOP", "stop failures drift")
    require(
        fixture["control_evidence_kinds_per_fixture"]
        == ["TRUSTED_TIME", "ROW_CURRENTNESS"],
        "E_FIXTURE_EVIDENCE",
        "control evidence kinds drift",
    )
    require(
        fixture["scope_authority_roles_per_fixture"]
        == [
            "OWNER",
            "CUSTODIAN",
            "RESOURCE_CONTROLLER",
            "COST_CONTROLLER",
            "EMERGENCY_STOP_CONTROLLER",
        ],
        "E_FIXTURE_ROLES",
        "scope authority roles drift",
    )
    boundary = fixture["boundary"]
    require(
        boundary
        == {
            "condition_output_authorized": False,
            "credentials_accessed": False,
            "experiment_rows": 0,
            "live_endpoint_bound": False,
            "output_permits": 0,
            "paid_resources_provisioned": False,
            "provider_called": False,
            "receipt_is_execution_authority": False,
            "receipt_is_output_permit": False,
            "runtime_authority": False,
            "runtime_rows": 0,
            "side_effects_unlocked": "NONE",
            "wire_attempts": 0,
        },
        "E_FIXTURE_BOUNDARY",
        "synthetic boundary drift",
    )


def assert_catalogs_match_contract(module: object, contract: dict[str, object]) -> None:
    expected_adapters = []
    for track_key, track_id in (
        ("managed", "MANAGED_SPANNER_CLOUD_KMS"),
        ("self_hosted", "SELF_HOSTED_ETCD_OPENBAO"),
    ):
        section = contract["adapter_interfaces"][track_key]
        for raw in section["adapters"]:
            expected_adapters.append((track_id, raw))

    require(tuple(module.ADAPTER_CATALOG) == EXPECTED_ADAPTER_IDS, "E_ADAPTER_CATALOG", "adapter order drift")
    require(len(expected_adapters) == 9, "E_ADAPTER_CATALOG", "adapter count drift")
    for track_id, raw in expected_adapters:
        spec = module.ADAPTER_CATALOG[raw["adapter_id"]]
        require(spec.adapter_id == raw["adapter_id"], "E_ADAPTER_CATALOG", "adapter id drift")
        require(spec.track_id == track_id, "E_ADAPTER_CATALOG", "adapter track drift")
        require(spec.credential_class == raw["credential_class"], "E_ADAPTER_CATALOG", "adapter credential drift")
        require(spec.allowed_operations == tuple(raw["allowed_operations"]), "E_ADAPTER_CATALOG", "adapter allowed operations drift")
        require(spec.forbidden_operations == tuple(raw["forbidden_operations"]), "E_ADAPTER_CATALOG", "adapter forbidden operations drift")
        require(spec.evidence_returns == tuple(raw["evidence_returns"]), "E_ADAPTER_CATALOG", "adapter evidence drift")

    expected_controls = contract["stop_control_plane"]["interfaces"]
    require(tuple(module.STOP_CONTROL_CATALOG) == EXPECTED_STOP_CONTROL_IDS, "E_STOP_CATALOG", "stop order drift")
    require(len(expected_controls) == 5, "E_STOP_CATALOG", "stop count drift")
    for raw in expected_controls:
        spec = module.STOP_CONTROL_CATALOG[raw["interface_id"]]
        require(spec.interface_id == raw["interface_id"], "E_STOP_CATALOG", "stop id drift")
        require(spec.credential_class == raw["credential_class"], "E_STOP_CATALOG", "stop credential drift")
        require(spec.allowed_operations == tuple(raw["allowed_operations"]), "E_STOP_CATALOG", "stop allowed operations drift")
        require(spec.forbidden_operations == tuple(raw["forbidden_operations"]), "E_STOP_CATALOG", "stop forbidden operations drift")
        require(spec.receipt_fields == tuple(raw["receipt_fields"]), "E_STOP_CATALOG", "stop receipt fields drift")

    experiment_credentials = {
        spec.credential_class for spec in module.ADAPTER_CATALOG.values()
    }
    stop_credentials = {
        spec.credential_class for spec in module.STOP_CONTROL_CATALOG.values()
    }
    require(len(experiment_credentials) == 9, "E_CREDENTIAL_ISOLATION", "experiment credential reuse")
    require(len(stop_credentials) == 5, "E_CREDENTIAL_ISOLATION", "stop credential reuse")
    require(experiment_credentials.isdisjoint(stop_credentials), "E_CREDENTIAL_ISOLATION", "stop credential reused by experiment")


def assert_conformance_receipt(receipt: dict[str, object]) -> None:
    expected = {
        "adapter_calls": 9,
        "adapter_cross_scope_rejections": 9,
        "adapter_duplicate_rejections": 9,
        "adapter_forbidden_rejections": 9,
        "authority_bundles_verified": 9,
        "condition_outputs": 0,
        "control_evidence_receipts_verified": 18,
        "control_ledger_duplicate_start_rejections": 9,
        "control_ledger_start_cas": 9,
        "credentials_accessed": 0,
        "decision": EXPECTED_DECISION,
        "experiment_rows": 0,
        "output_permits": 0,
        "paid_resources_provisioned": 0,
        "private_capability_commitments_verified": 9,
        "provider_calls": 0,
        "receipt_is_execution_authority": False,
        "receipt_is_output_permit": False,
        "runtime_authority": False,
        "runtime_rows": 0,
        "scope_signature_receipts_verified": 45,
        "side_effects_unlocked": "NONE",
        "status": EXPECTED_STATUS,
        "stop_control_operation_receipts": 6,
        "stop_sequences_absorbing_complete": 1,
        "stop_sequences_failed_quarantined": 5,
        "wire_attempts": 0,
    }
    for key, value in expected.items():
        require(receipt[key] == value, "E_RECEIPT", f"{key} drift")
    require(tuple(receipt["adapter_ids"]) == EXPECTED_ADAPTER_IDS, "E_RECEIPT", "adapter ids drift")
    require(tuple(receipt["stop_control_ids"]) == EXPECTED_STOP_CONTROL_IDS, "E_RECEIPT", "stop ids drift")


def validate_source_purity(source_path: Path) -> None:
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    allowed_import_roots = {
        "__future__",
        "copy",
        "dataclasses",
        "datetime",
        "functools",
        "hashlib",
        "json",
        "typing",
        "biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1",
    }
    forbidden_calls = {"compile", "eval", "exec", "open", "__import__"}
    forbidden_attributes = {
        "connect",
        "getenv",
        "now",
        "popen",
        "read_bytes",
        "read_text",
        "run",
        "system",
        "time",
        "urandom",
        "utcnow",
        "write_bytes",
        "write_text",
    }
    class_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(
                    alias.name.split(".", 1)[0] in allowed_import_roots,
                    "E_SOURCE_IMPORT",
                    f"forbidden import {alias.name}",
                )
        elif isinstance(node, ast.ImportFrom):
            require(
                (node.module or "").split(".", 1)[0] in allowed_import_roots,
                "E_SOURCE_IMPORT",
                f"forbidden import-from {node.module}",
            )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(
                    node.func.id not in forbidden_calls,
                    "E_SOURCE_CALL",
                    f"forbidden call {node.func.id}",
                )
            elif isinstance(node.func, ast.Attribute):
                require(
                    node.func.attr not in forbidden_attributes,
                    "E_SOURCE_CALL",
                    f"forbidden attribute call {node.func.attr}",
                )
        elif isinstance(node, ast.ClassDef):
            class_names.add(node.name)
    require(
        {
            "OfflineAuthorityVerifier",
            "PrivateCapabilityControlLedgerDouble",
            "ExperimentAdapterDouble",
            "StopControlDouble",
            "StopCoordinatorDouble",
        }.issubset(class_names),
        "E_SOURCE_API",
        "required implementation classes are missing",
    )


def expect_rejection(action: object, label: str) -> None:
    try:
        action()
    except Exception as exc:
        require(
            isinstance(exc, ValueError)
            and type(exc).__name__ in {"ContractError", "OfflineDoubleError"},
            "E_NEGATIVE_EXCEPTION",
            f"{label} raised {type(exc).__name__}",
        )
        return
    raise PackError(f"E_NEGATIVE_ACCEPTED: {label}")


def mutate_scalar(value: object) -> object:
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is list:
        return [*value, "UNAUTHORIZED_MUTATION"]
    if type(value) is str and len(value) == 64:
        return ("0" if value[0] != "0" else "1") + value[1:]
    if type(value) is str:
        return value + "_MUTATED"
    raise AssertionError(f"unsupported mutation type: {type(value).__name__}")


def invalid_scope_signature_attack(
    module: object,
    bundle: dict[str, object],
    store: object,
    slot: str,
) -> tuple[dict[str, object], object]:
    attacked_bundle = copy.deepcopy(bundle)
    attacked_store = store.clone()
    scope_receipt = attacked_bundle[slot]
    signature_receipt = attacked_store.resolve_document(
        scope_receipt["signature_receipt_sha256"],
        "E_TEST",
        "signature receipt",
    )
    original = attacked_store.resolve_signature(
        signature_receipt["signature_sha256"],
        "E_TEST",
        "signature",
    )
    invalid = bytes([original[0] ^ 1, *original[1:]])
    signature_receipt["signature_sha256"] = attacked_store.add_signature(invalid)
    scope_receipt["signature_receipt_sha256"] = attacked_store.add_document(
        signature_receipt
    )
    scope_receipt["receipt_id"] = frozen_contract._scope_receipt_id(scope_receipt)
    attacked_bundle["bundle_id"] = frozen_contract._authority_bundle_id(
        attacked_bundle
    )
    return attacked_bundle, attacked_store


def invalid_control_signature_attack(
    bundle: dict[str, object],
    store: object,
    reference_field: str,
) -> tuple[dict[str, object], object]:
    attacked_bundle = copy.deepcopy(bundle)
    attacked_store = store.clone()
    evidence = attacked_store.resolve_document(
        attacked_bundle["currentness"][reference_field],
        "E_TEST",
        "control evidence",
    )
    original = attacked_store.resolve_signature(
        evidence["signature_sha256"],
        "E_TEST",
        "control signature",
    )
    invalid = bytes([original[0] ^ 1, *original[1:]])
    evidence["signature_sha256"] = attacked_store.add_signature(invalid)
    attacked_bundle["currentness"][reference_field] = attacked_store.add_document(
        evidence
    )
    attacked_bundle["bundle_id"] = frozen_contract._authority_bundle_id(
        attacked_bundle
    )
    return attacked_bundle, attacked_store


def run_directed_negative_tests(
    module: object,
    contract: dict[str, object],
    authority_schema: dict[str, object],
) -> int:
    adapter_id = EXPECTED_ADAPTER_IDS[0]
    bundle, store, private_capability, ledger = module.build_synthetic_authority_fixture(
        contract,
        adapter_id,
        1,
    )
    verifier = module.OfflineAuthorityVerifier(contract, authority_schema)
    verifier.verify(bundle, store, private_capability, ledger)
    count = 0

    root_mutations = (
        "adapter_build_sha256",
        "adapter_set_manifest_sha256",
        "assignment_sha256",
        "bundle_id",
        "case_id",
        "cleanup_policy_sha256",
        "condition_output_authorized",
        "configuration_sha256",
        "contract_sha256",
        "cost_scope_sha256",
        "credential_scope_sha256",
        "effective_allowed_operations",
        "field_level_intersection_sha256",
        "namespace_id",
        "offline_harness_manifest_sha256",
        "phase",
        "profile_sha256",
        "public_bundle_is_bearer_capability",
        "receipt_is_output_permit",
        "repetition_index",
        "resource_scope_sha256",
        "retention_policy_sha256",
        "revocation_epoch",
        "runner_build_sha256",
        "schedule_sha256",
        "simulation_run_id",
        "stop_control_plane_manifest_sha256",
        "suite_id",
        "track_id",
    )
    for field in root_mutations:
        candidate = copy.deepcopy(bundle)
        candidate[field] = mutate_scalar(candidate[field])
        expect_rejection(
            lambda candidate=candidate: verifier.verify(
                candidate,
                store,
                private_capability,
                ledger,
            ),
            f"root mutation {field}",
        )
        count += 1

    receipt_mutations = (
        "artifact_type",
        "authority_principal_id_sha256",
        "nonce_sha256",
        "receipt_is_output_permit",
        "trust_policy_sha256",
    )
    for slot, _artifact_type in frozen_contract._AUTHORITY_ROLE_SLOTS:
        for field in receipt_mutations:
            candidate = copy.deepcopy(bundle)
            candidate[slot][field] = mutate_scalar(candidate[slot][field])
            expect_rejection(
                lambda candidate=candidate: verifier.verify(
                    candidate,
                    store,
                    private_capability,
                    ledger,
                ),
                f"{slot} mutation {field}",
            )
            count += 1

    for slot, _artifact_type in frozen_contract._AUTHORITY_ROLE_SLOTS:
        candidate, attacked_store = invalid_scope_signature_attack(
            module,
            bundle,
            store,
            slot,
        )
        expect_rejection(
            lambda candidate=candidate, attacked_store=attacked_store: verifier.verify(
                candidate,
                attacked_store,
                private_capability,
                ledger,
            ),
            f"active signature verification {slot}",
        )
        count += 1

    for reference_field in (
        "trusted_time_receipt_sha256",
        "row_currentness_receipt_sha256",
    ):
        candidate, attacked_store = invalid_control_signature_attack(
            bundle,
            store,
            reference_field,
        )
        expect_rejection(
            lambda candidate=candidate, attacked_store=attacked_store: verifier.verify(
                candidate,
                attacked_store,
                private_capability,
                ledger,
            ),
            f"active control signature verification {reference_field}",
        )
        count += 1

    wrong_private_capability = bytes(
        [private_capability[0] ^ 1, *private_capability[1:]]
    )
    expect_rejection(
        lambda: verifier.verify(bundle, store, wrong_private_capability, ledger),
        "wrong private capability bytes",
    )
    count += 1

    for slot, _artifact_type in frozen_contract._AUTHORITY_ROLE_SLOTS:
        attacked_store = store.clone()
        attacked_store._documents.pop(bundle[slot]["signature_receipt_sha256"])
        expect_rejection(
            lambda attacked_store=attacked_store: verifier.verify(
                bundle,
                attacked_store,
                private_capability,
                ledger,
            ),
            f"missing signature evidence {slot}",
        )
        count += 1
    for reference_field in (
        "trusted_time_receipt_sha256",
        "row_currentness_receipt_sha256",
    ):
        attacked_store = store.clone()
        attacked_store._documents.pop(bundle["currentness"][reference_field])
        expect_rejection(
            lambda attacked_store=attacked_store: verifier.verify(
                bundle,
                attacked_store,
                private_capability,
                ledger,
            ),
            f"missing control evidence {reference_field}",
        )
        count += 1

    for adapter_id in EXPECTED_ADAPTER_IDS:
        adapter = module.ExperimentAdapterDouble(adapter_id)
        spec = module.ADAPTER_CATALOG[adapter_id]
        request = {
            "binding_sha256": "0" * 64,
            "request_id_sha256": "1" * 64,
        }
        expect_rejection(
            lambda adapter=adapter, spec=spec, request=request: adapter.invoke(
                None,
                spec.forbidden_operations[0],
                request,
            ),
            f"forbidden adapter operation {adapter_id}",
        )
        count += 1
        expect_rejection(
            lambda adapter=adapter, request=request: adapter.invoke(
                None,
                "UNREGISTERED_EXPERIMENT_OPERATION",
                request,
            ),
            f"unknown adapter operation {adapter_id}",
        )
        count += 1
        expect_rejection(
            lambda adapter=adapter, spec=spec: adapter.invoke(
                None,
                spec.allowed_operations[0],
                {},
            ),
            f"malformed adapter request {adapter_id}",
        )
        count += 1

    stop_capability = module.StopCapability(
        bundle["simulation_run_id"],
        bundle["namespace_id"],
        "directed-negatives",
    )
    experiment_operation = module.ADAPTER_CATALOG[adapter_id].allowed_operations[0]
    for interface_id in EXPECTED_STOP_CONTROL_IDS:
        control = module.StopControlDouble(interface_id)
        spec = module.STOP_CONTROL_CATALOG[interface_id]
        expect_rejection(
            lambda control=control, spec=spec: control.invoke(
                stop_capability,
                (spec.forbidden_operations[0],),
                1,
            ),
            f"forbidden stop operation {interface_id}",
        )
        count += 1
        expect_rejection(
            lambda control=control: control.invoke(
                stop_capability,
                (experiment_operation,),
                1,
            ),
            f"experiment operation on stop control {interface_id}",
        )
        count += 1
        expect_rejection(
            lambda control=control: control.invoke(
                stop_capability,
                (),
                1,
            ),
            f"empty stop operation {interface_id}",
        )
        count += 1

    controls = {
        interface_id: module.StopControlDouble(interface_id)
        for interface_id in EXPECTED_STOP_CONTROL_IDS
    }
    coordinator = module.StopCoordinatorDouble(controls, contract)
    valid_trigger = "OWNER_CUSTODIAN_OR_EMERGENCY_OPERATOR_STOP"
    valid_reason = "OPERATOR_STOP"
    valid_role = "OWNER"
    expect_rejection(
        lambda: coordinator.stop(
            ledger.clone_started_for_stop_test(),
            stop_capability,
            "UNKNOWN_TRIGGER",
            valid_reason,
            valid_role,
        ),
        "unknown stop trigger",
    )
    count += 1
    expect_rejection(
        lambda: coordinator.stop(
            ledger.clone_started_for_stop_test(),
            stop_capability,
            valid_trigger,
            "UNKNOWN_REASON",
            valid_role,
        ),
        "unknown stop reason",
    )
    count += 1
    expect_rejection(
        lambda: coordinator.stop(
            ledger.clone_started_for_stop_test(),
            stop_capability,
            valid_trigger,
            valid_reason,
            "UNKNOWN_ROLE",
        ),
        "unknown stop role",
    )
    count += 1
    wrong_scope = module.StopCapability(
        "0" * 64,
        bundle["namespace_id"],
        "wrong-scope",
    )
    expect_rejection(
        lambda: coordinator.stop(
            ledger.clone_started_for_stop_test(),
            wrong_scope,
            valid_trigger,
            valid_reason,
            valid_role,
        ),
        "cross-run stop capability",
    )
    count += 1
    return count


def validate_manifest(
    root: Path,
    manifest: dict[str, object],
    receipt: dict[str, object],
) -> None:
    require(
        set(manifest)
        == {
            "boundary",
            "date",
            "decision",
            "evidence_sha256",
            "logical_baseline_commit",
            "next_unit",
            "packet",
            "predecessor",
            "results",
            "schema",
            "status",
            "test_oracle",
            "tracks",
        },
        "E_MANIFEST_KEYS",
        "manifest key closure drift",
    )
    require(
        manifest["schema"]
        == "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
        "runner_offline_authority_and_adapter_doubles_v1_pack_manifest.v0",
        "E_MANIFEST_SCHEMA",
        "manifest schema drift",
    )
    require(manifest["date"] == "2026-07-16", "E_MANIFEST_DATE", "manifest date drift")
    require(manifest["status"] == EXPECTED_STATUS, "E_MANIFEST_STATUS", "manifest status drift")
    require(manifest["decision"] == EXPECTED_DECISION, "E_MANIFEST_DECISION", "manifest decision drift")
    require(manifest["next_unit"] == receipt["next_unit"], "E_MANIFEST_NEXT", "manifest next unit drift")
    require(
        manifest["logical_baseline_commit"]
        == "08594b04fe9e23b11c70b3a5640c43ada9911a7b",
        "E_MANIFEST_BASELINE",
        "manifest baseline drift",
    )

    packet_paths = [
        "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1.py",
        "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1_pack.py",
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1_pack_synthetic_v0.json",
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1_pack.expected.v0.tsv",
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1_pack_v0.json",
        "docs/reports/goal-c-u/2026-07-16-biocortex-track-b-reference-provider-fault-injection-runner-offline-authority-and-adapter-doubles-v1-pack.md",
        "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-offline-authority-and-adapter-doubles-v1-pack.sh",
    ]
    require(manifest["packet"]["paths"] == packet_paths, "E_MANIFEST_PACKET", "packet paths drift")
    require(
        manifest["packet"]["modes"]
        == {
            path: ("100755" if path == packet_paths[-1] else "100644")
            for path in packet_paths
        },
        "E_MANIFEST_PACKET",
        "packet modes drift",
    )
    predecessor = manifest["predecessor"]
    require(
        predecessor
        == {
            "integration_commit": "08594b04fe9e23b11c70b3a5640c43ada9911a7b",
            "manifest_path": "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack_v0.json",
            "manifest_sha256": "ff7cae32c8f19df080e40724ff353126c57caad1e23d957e467d490519738b12",
            "source_commit": "8002636128b530c3f9b1989f2894785be91b7c18",
        },
        "E_MANIFEST_PREDECESSOR",
        "predecessor binding drift",
    )
    evidence = manifest["evidence_sha256"]
    expected_evidence_paths = {
        packet_paths[0],
        packet_paths[1],
        packet_paths[2],
        packet_paths[3],
        packet_paths[5],
        "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-adapter-contract-v1.json",
        "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-authority-receipt-schema-v1.json",
        "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-stop-receipt-schema-v1.json",
        "docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-runner-authority-and-adapter-contract-v1-pack.md",
        "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-authority-and-adapter-contract-v1-pack.sh",
        "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1.py",
        "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.py",
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.expected.v0.tsv",
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack_synthetic_v0.json",
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack_v0.json",
    }
    require(set(evidence) == expected_evidence_paths, "E_MANIFEST_EVIDENCE", "evidence path closure drift")
    for path, expected_sha256 in evidence.items():
        require(
            hashlib.sha256((root / path).read_bytes()).hexdigest() == expected_sha256,
            "E_MANIFEST_EVIDENCE",
            f"evidence hash drift: {path}",
        )

    require(
        manifest["results"]
        == {
            "adapter_calls": 9,
            "authority_bundles_verified": 9,
            "conformance_content_sha256": receipt["content_sha256"],
            "control_evidence_receipts_verified": 18,
            "experiment_rows": 0,
            "private_capability_commitments_verified": 9,
            "provider_calls": 0,
            "runtime_rows": 0,
            "scope_signature_receipts_verified": 45,
            "stop_sequences_absorbing_complete": 1,
            "stop_sequences_failed_quarantined": 5,
            "wire_attempts": 0,
        },
        "E_MANIFEST_RESULTS",
        "manifest results drift",
    )
    require(
        manifest["test_oracle"]
        == {
            "adapter_doubles": 9,
            "authority_artifacts_per_bundle": 5,
            "control_evidence_receipts_per_bundle": 2,
            "directed_negative_tests": 115,
            "scope_signature_receipts": 45,
            "source_ast_purity": "PASS",
            "stop_control_doubles": 5,
            "stop_control_operation_receipts": 6,
        },
        "E_MANIFEST_ORACLE",
        "manifest test oracle drift",
    )
    require(
        manifest["boundary"]
        == {
            "condition_output_authorized": False,
            "credentials_accessed": False,
            "execution_capability_emitted": False,
            "experiment_executed": False,
            "live_endpoint_bound": False,
            "offline_adapter_doubles_implemented": 9,
            "offline_authority_verifier_implemented": True,
            "offline_stop_control_doubles_implemented": 5,
            "output_permit_defined": False,
            "paid_resources_provisioned": False,
            "production_adapter_implemented": False,
            "provider_called": False,
            "receipt_is_execution_authority": False,
            "receipt_is_output_permit": False,
            "runtime_authority": False,
            "side_effects_unlocked": "NONE",
            "synthetic_private_capability_consumed": True,
        },
        "E_MANIFEST_BOUNDARY",
        "manifest boundary drift",
    )
    require(
        manifest["tracks"]
        == {
            "MANAGED_SPANNER_CLOUD_KMS": "OFFLINE_DOUBLE_CONFORMANCE_ONLY_NO_RUNTIME",
            "SELF_HOSTED_ETCD_OPENBAO": "OFFLINE_DOUBLE_CONFORMANCE_ONLY_NO_RUNTIME",
        },
        "E_MANIFEST_TRACKS",
        "manifest track result drift",
    )


def evaluate(root: Path, self_test: bool) -> str:
    global frozen_contract
    frozen_contract = load_module(
        root
        / "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_"
        "runner_authority_and_adapter_contract_v1.py",
        FROZEN_MODULE_NAME,
    )
    module = load_module(
        root
        / "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_"
        "runner_offline_authority_and_adapter_doubles_v1.py",
        MODULE_NAME,
    )
    for api_name in (
        "OfflineAuthorityVerifier",
        "PrivateCapabilityControlLedgerDouble",
        "ExperimentAdapterDouble",
        "StopControlDouble",
        "StopCoordinatorDouble",
        "build_synthetic_authority_fixture",
        "run_conformance",
        "render_tsv",
    ):
        require(callable(getattr(module, api_name, None)), "E_SOURCE_API", f"missing API {api_name}")

    source_path = (
        root
        / "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_"
        "runner_offline_authority_and_adapter_doubles_v1.py"
    )
    validate_source_purity(source_path)
    contract = load_json(
        root
        / "docs/design/fixtures/biocortex-ab-track-b-reference-provider-"
        "fault-injection-runner-adapter-contract-v1.json"
    )
    authority_schema = load_json(
        root
        / "docs/design/fixtures/biocortex-ab-track-b-reference-provider-"
        "fault-injection-runner-authority-receipt-schema-v1.json"
    )
    stop_schema = load_json(
        root
        / "docs/design/fixtures/biocortex-ab-track-b-reference-provider-"
        "fault-injection-runner-stop-receipt-schema-v1.json"
    )
    synthetic_fixture = load_json(
        root
        / "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_offline_authority_and_adapter_doubles_v1_pack_synthetic_v0.json"
    )
    manifest = load_json(
        root
        / "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_offline_authority_and_adapter_doubles_v1_pack_v0.json"
    )

    validate_synthetic_fixture(synthetic_fixture)
    assert_catalogs_match_contract(module, contract)
    receipt = module.run_conformance(contract, authority_schema, stop_schema)
    assert_conformance_receipt(receipt)
    validate_manifest(root, manifest, receipt)
    expected_content_sha256 = frozen_contract.sha256_value(
        {
            key: copy.deepcopy(value)
            for key, value in receipt.items()
            if key != "content_sha256"
        }
    )
    require(
        receipt["content_sha256"] == expected_content_sha256,
        "E_CONTENT_HASH",
        "conformance content hash mismatch",
    )
    negative_count = run_directed_negative_tests(module, contract, authority_schema)
    require(
        negative_count == 115,
        "E_NEGATIVE_COUNT",
        f"directed negative count drift: {negative_count}",
    )
    rendered = (
        module.render_tsv(receipt)
        + f"directed_negative_tests\t{negative_count}\n"
        + "source_ast_purity\tPASS\n"
    )
    expected_path = (
        root
        / "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_offline_authority_and_adapter_doubles_v1_pack.expected.v0.tsv"
    )
    require(
        expected_path.read_bytes() == rendered.encode("utf-8"),
        "E_EXPECTED_TSV",
        "expected TSV drift",
    )
    if self_test:
        repeated = module.run_conformance(
            copy.deepcopy(contract),
            copy.deepcopy(authority_schema),
            copy.deepcopy(stop_schema),
        )
        require(repeated == receipt, "E_DETERMINISM", "conformance rerun drift")
        require(
            module.render_tsv(repeated) == module.render_tsv(receipt),
            "E_DETERMINISM",
            "TSV rerun drift",
        )
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        rendered = evaluate(args.root.resolve(), args.self_test)
    except (OSError, PackError, AssertionError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
