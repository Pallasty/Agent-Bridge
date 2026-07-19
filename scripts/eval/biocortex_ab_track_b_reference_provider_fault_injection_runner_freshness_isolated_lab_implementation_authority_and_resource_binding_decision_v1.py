#!/usr/bin/env python3
"""Deterministic reviewer for the bounded T10 freshness authority decision."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, NoReturn

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
OWNER_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
MANIFEST_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json"
SEMANTIC_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
PREDECESSOR_MANIFEST_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1_pack_v0.json"
PACK_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.freshness_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.receipt.v0"
DECISION = "AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_T10_FRESHNESS_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED"
NEXT_UNIT = "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_FRESHNESS_SYNTHETIC_EXACT_T09_RECEIPT_TRACK_OBSERVED_AT_VALIDATION_CHECKED_AT_DECISION_RECHECK_AT_EXPIRES_AT_AND_MAX_AGE_SECONDS_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
STATE = "AUTHORIZED_T10_FRESHNESS_ISOLATED_LAB_EXACT_UNIT"
DOMAIN = "AB_TRACK_B_T10_FRESHNESS_AUTHORITY_DECISION_PACK_RECEIPT_V1"
BASELINE = "80d78735ebda85c62be0af82c0afb18b23bed975"
BASELINE_TREE = "3f40474c9fcb40eb596b6dbf8537e27d9ac0bd06"
PROFILE_FIELDS = ("t09_receipt_content_sha256", "track_id", "observed_at_unix_seconds", "validation_checked_at_unix_seconds", "decision_recheck_at_unix_seconds", "expires_at_unix_seconds", "max_age_seconds")
REQUEST_FIELDS = ("observed_at_unix_seconds", "validation_checked_at_unix_seconds", "decision_recheck_at_unix_seconds", "expires_at_unix_seconds", "max_age_seconds")
OWNER_KEYS = ("authorized_component_contract", "boundary", "date", "decision", "implementation_authority", "next_unit", "nonclaims", "owner_implementation_actor", "predecessor", "resource_binding", "rollback", "schema", "schema_version", "state_machine", "status")

class ReviewError(ValueError): pass
def fail(code: str, detail: str) -> NoReturn: raise ReviewError(f"{code}: {detail}")
def require(value: bool, code: str, detail: str) -> None:
    if not value: fail(code,detail)
def pairs(items: list[tuple[str,Any]]) -> dict[str,Any]:
    out={}
    for key,value in items:
        require(type(key) is str and key not in out,"E_JSON_DUPLICATE",repr(key)); out[key]=value
    return out
def no_float(value: str) -> NoReturn: fail("E_JSON_FLOAT",value)
def parse_int(value: str) -> int:
    result=int(value); require(-(2**63)<=result<=2**63-1,"E_JSON_INT_RANGE",value); return result
def checked_path(relative: str) -> Path:
    require(type(relative) is str and relative and not relative.startswith("/") and all(part not in ("", ".", "..") for part in relative.split("/")),"E_PATH",relative)
    candidate=ROOT.joinpath(*relative.split("/")); resolved=candidate.resolve(strict=True)
    require(ROOT in resolved.parents and candidate.is_file() and not candidate.is_symlink(),"E_PATH_ESCAPE",relative); return candidate
def load(relative: str) -> dict[str,Any]:
    raw=checked_path(relative).read_bytes(); require(0<len(raw)<=8*1024*1024,"E_SIZE",relative); text=raw.decode("utf-8","strict")
    decoder=json.JSONDecoder(object_pairs_hook=pairs,parse_int=parse_int,parse_float=no_float,parse_constant=no_float,strict=True); value,end=decoder.raw_decode(text)
    require(not text[end:].strip() and type(value) is dict,"E_JSON_ROOT",relative); return value
def canonical(value: Any) -> bytes: return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def domain_sha(value: Mapping[str,Any]) -> str: return sha(DOMAIN.encode("ascii")+b"\x00"+canonical(value))

def validate(owner: Mapping[str,Any], manifest: Mapping[str,Any], semantic: Mapping[str,Any], predecessor: Mapping[str,Any]) -> None:
    require(set(owner)==set(OWNER_KEYS),"E_OWNER_FIELDS","closed field set drift")
    require(owner["schema_version"]==1 and owner["date"]=="2026-07-19","E_OWNER_HEADER","drift")
    require(owner["decision"]==DECISION and owner["next_unit"]==NEXT_UNIT,"E_OWNER_DECISION","drift")
    require(owner["owner_implementation_actor"]["actor_id"]=="pallasting" and owner["owner_implementation_actor"]["actor_class"]=="PROJECT_OWNER","E_OWNER_ACTOR","drift")
    pred=owner["predecessor"]; require(pred["exact_release_commit"]==BASELINE and pred["exact_release_tree"]==BASELINE_TREE and pred["implementation_authority_consumed"] is True,"E_PREDECESSOR","drift")
    require(predecessor["source_baseline"]["commit"]=="35575397bfe4ec11278565e0221f46c17130efc4" and predecessor["boundary"]["t09_content_identity_and_quarantine_custody_implemented_after_integrated_full_gate"] is True,"E_PREDECESSOR_MANIFEST","drift")
    contract=owner["authorized_component_contract"]; binding=contract["binding_model"]
    require(binding["policy_match_fields"]==list(PROFILE_FIELDS) and binding["request_fields"]==list(REQUEST_FIELDS),"E_FIELDS","drift")
    require(binding["policy_match_dimension_count"]==7 and binding["request_field_count"]==5 and len(binding["profiles"])==2,"E_COUNTS","drift")
    require(binding["profile_order"]==["MANAGED_SPANNER_CLOUD_KMS","SELF_HOSTED_ETCD_OPENBAO"],"E_PROFILE_ORDER","drift")
    require([profile["track_id"] for profile in binding["profiles"]]==binding["profile_order"],"E_PROFILE_SEQUENCE","drift")
    for profile in binding["profiles"]:
        require(set(profile)==set(PROFILE_FIELDS),"E_PROFILE_KEYS",profile["track_id"])
        for field in REQUEST_FIELDS: require(type(profile[field]) is int and 0<=profile[field]<=2**63-1,"E_PROFILE_INTEGER",field)
        observed=profile["observed_at_unix_seconds"]; validation=profile["validation_checked_at_unix_seconds"]; decision=profile["decision_recheck_at_unix_seconds"]; expires=profile["expires_at_unix_seconds"]; age=profile["max_age_seconds"]
        require(observed<=validation<=decision<expires and validation-observed<=age and decision-observed<=age,"E_FRESHNESS_ARITHMETIC",profile["track_id"])
    topology=contract["input_topology"]; require(topology["public_input_count"]==14 and len(topology["public_input_tuple"])==14 and topology["public_input_tuple"][-1]=="mode","E_API","drift")
    require(topology["review_order"]==["MODE_PREOBSERVATION_GUARD","T09_FIVE_IDENTITY_REVIEW_EXACTLY_ONCE","SEPARATE_FRESHNESS_POLICY_REVIEW","DETACHED_FRESHNESS_REQUEST_REVIEW_LAST","EXACT_SINGLE_PROFILE_MATCH","BOUNDED_STALENESS_ARITHMETIC"],"E_ORDER","drift")
    arithmetic=contract["freshness_arithmetic"]; require(arithmetic["ambient_clock_allowed"] is False and arithmetic["production_trusted_time_claimed"] is False and arithmetic["future_date_or_clock_skew_claimed_as_t11_coverage"] is False,"E_TIME_BOUNDARY","drift")
    authority=owner["implementation_authority"]; require(authority["current_state"]==STATE and authority["exact_next_unit_authorized"] is True and authority["non_transitive"] is True,"E_AUTHORITY","drift")
    forbidden=set(authority["forbidden_operations"]); require({"ACCESS_AMBIENT_SYSTEM_OR_PROVIDER_CLOCK","CLAIM_T11_CLOCK_SKEW_COVERAGE","CLAIM_T12_OWNER_TOCTOU_COVERAGE","USE_WALL_MONOTONIC_NETWORK_PROVIDER_OR_TRUSTED_TIME"}<=forbidden,"E_FORBIDDEN","missing")
    resources=owner["resource_binding"]; limits=resources["component_limits"]
    require(resources["effective_external_paid_spend_cap"]==0 and resources["network"] is False and limits["max_parallel_workers"]==1 and limits["max_predecessor_review_calls"]==1 and limits["max_private_scratch_bytes"]==67108864 and limits["public_input_count"]==14,"E_RESOURCES","drift")
    boundary=owner["boundary"]; require(boundary["current_released_component_total"]==7 and boundary["future_successor_component_total_after_exact_integrated_full_gate"]==8 and boundary["production_ingestion_controls_implemented"]==0 and boundary["runtime_authority"] is False and boundary["provider_authority"] is False,"E_BOUNDARY","drift")
    require(owner["state_machine"]["current_state"]==STATE and owner["state_machine"]["decision_full_gate_consumes_new_authority"] is False,"E_STATE","drift")
    threats={item["case_id"]:item for item in semantic["threat_cases"]}; require(threats["T10"]["threat_class"]=="FRESHNESS" and threats["T10"]["expected_reason_code"]=="E_PRODUCTION_FRESHNESS_FAILED","E_T10_SEMANTIC","drift")
    require(threats["T11"]["threat_class"]=="CLOCK_SKEW","E_T11_SEMANTIC","drift")
    controls={item["control_id"]:item for item in semantic["production_ingestion_controls"]}; require(controls["TRUSTED_TIME_FRESHNESS"]["implemented"] is False,"E_CONTROL","drift")
    require(manifest["authorized_unit"]==NEXT_UNIT and manifest["source_baseline"]["commit"]==BASELINE and manifest["state"]["decision_full_gate_consumes_new_authority"] is False,"E_MANIFEST","drift")

def evaluate() -> str:
    owner,manifest,semantic,predecessor=map(load,(OWNER_REL,MANIFEST_REL,SEMANTIC_REL,PREDECESSOR_MANIFEST_REL)); validate(owner,manifest,semantic,predecessor)
    receipt={
        "schema":PACK_SCHEMA,"status":"T10_FRESHNESS_IMPLEMENTATION_AUTHORITY_CANDIDATE_PENDING_EXACT_INTEGRATED_FULL_GATE","decision":DECISION,"date":"2026-07-19","owner_actor_id":"pallasting","owner_actor_class":"PROJECT_OWNER","semantic_owner_signature_observed":False,
        "baseline_commit":BASELINE,"baseline_tree":BASELINE_TREE,"predecessor_t09_released":True,"predecessor_authority_consumed":True,"authorization_candidate_state":STATE,"freshness_implementation_authority_candidate":True,"decision_full_gate_consumes_new_authority":False,"implementation_authority_single_use_consumed":False,"implementation_authority_non_transitive":True,
        "authorized_unit":NEXT_UNIT,"authorized_candidate_surface_component_count":1,"authorized_local_threat_specification":"T10","t10_freshness_implemented":False,"t11_clock_skew_authorized":False,"t12_owner_toctou_authorized":False,"public_input_count":14,"predecessor_review_count_per_success":1,"binding_profile_count":2,"request_field_count":5,"policy_match_dimension_count":7,
        "mode_observed_first":True,"freshness_request_observed_last":True,"ambient_clock_allowed":False,"signed_trusted_time_bound":False,"production_currentness_proved":False,"integer_time_labels_are_trusted_time":False,"validation_and_decision_staleness_arithmetic_authorized":True,
        "effective_external_paid_spend_cap":0,"max_parallel_workers":1,"max_private_scratch_bytes":67108864,"network":False,"credentials_authorized":False,"real_evidence_input_authorized":False,"production_resource_authority_bound":False,
        "current_released_component_total":7,"future_component_total_after_exact_integrated_full_gate":8,"production_ingestion_control_count":14,"production_ingestion_controls_implemented":0,"production_threat_specification_count":20,"production_threat_specifications_runtime_exercised":0,"runtime_prerequisite_count":16,"runtime_prerequisites_satisfied":0,"real_evidence_items_present":0,"production_validated_evidence_items":0,"runtime_authority":False,"provider_authority":False,"side_effects_unlocked":"REVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY","content_sha256":"0"*64,
    }
    without=dict(receipt); without.pop("content_sha256"); receipt["content_sha256"]=domain_sha(without)
    return "".join(f"{key}\t{str(value).lower() if type(value) is bool else value}\n" for key,value in receipt.items())

def main() -> int:
    argparse.ArgumentParser().parse_args()
    try: sys.stdout.write(evaluate()); return 0
    except (ReviewError,OSError,UnicodeError,ValueError,TypeError,KeyError,AssertionError) as error: print(f"review_error\t{error}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
