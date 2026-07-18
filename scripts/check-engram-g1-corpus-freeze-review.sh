#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

validator="scripts/eval/engram_g1_corpus_freeze_review.py"
contract="scripts/eval/fixtures/engram_g1_corpus_freeze_review_contract_v1.json"
preflight_contract="scripts/eval/fixtures/engram_g1_freeze_preflight_contract_v1.json"
preflight_validator="scripts/eval/engram_g1_freeze_preflight.py"
role_review_contract="scripts/eval/fixtures/engram_g1_role_review_contract_v1.json"
role_review_validator="scripts/eval/engram_g1_role_review.py"
scratch="$(mktemp -d)"
data_root="$repo_root/data"
created_data_root=0
if [[ ! -d "$data_root" ]]; then
  created_data_root=1
fi
mkdir -p "$data_root"
private_scratch="$(mktemp -d "$data_root/.engram-g1-corpus-freeze-review-check.XXXXXX")"
cleanup() {
  rm -rf "$scratch" "$private_scratch"
  if [[ "$created_data_root" -eq 1 ]]; then
    rmdir "$data_root" 2>/dev/null || true
  fi
}
trap cleanup EXIT

python3 -m py_compile "$validator"
bash -n "$0"

python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/contract.1.json"
python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/contract.2.json"
cmp "$scratch/contract.1.json" "$scratch/contract.2.json"

python3 - "$scratch/contract.1.json" "$contract" "$validator" \
  "$preflight_contract" "$preflight_validator" "$role_review_contract" \
  "$role_review_validator" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
contract = Path(sys.argv[2])
validator = Path(sys.argv[3])
preflight_contract = Path(sys.argv[4])
preflight_validator = Path(sys.argv[5])
role_review_contract = Path(sys.argv[6])
role_review_validator = Path(sys.argv[7])

assert hashlib.sha256(contract.read_bytes()).hexdigest() == receipt["contract_sha256"]
assert hashlib.sha256(validator.read_bytes()).hexdigest() == receipt["validator_sha256"]
assert hashlib.sha256(preflight_contract.read_bytes()).hexdigest() == receipt["preflight_contract_sha256"]
assert hashlib.sha256(preflight_validator.read_bytes()).hexdigest() == receipt["preflight_validator_sha256"]
assert hashlib.sha256(role_review_contract.read_bytes()).hexdigest() == receipt["role_review_contract_sha256"]
assert hashlib.sha256(role_review_validator.read_bytes()).hexdigest() == receipt["role_review_validator_sha256"]
assert receipt["contract_verdict"] == (
    "STRUCTURAL_CORPUS_FREEZE_REVIEW_PACKET_PREPARATION_ALLOWED_NO_AUTHORITY"
)
assert receipt["structural_corpus_freeze_review_packet_preparation_permitted"] is True
assert receipt["secure_custody_capture_required_before_authenticated_review"] is True
assert receipt["secure_custody_capture_verified"] is False
assert receipt["ready_for_authenticated_freeze_authority_review"] is False
assert receipt["authenticated_freeze_authority_required_before_preregistration"] is True
assert receipt["required_freeze_reviewer_count"] == 2
assert receipt["proposed_frozen_episode_groups"] == 30
assert receipt["requires_new_review_for_any_manifest_change"] is True
assert receipt["current_private_corpus_assembly_authority"] is False
assert receipt["current_g1_corpus_freeze_authority"] is False
assert receipt["authenticated_freeze_authority_verified"] is False
assert receipt["ready_for_candidate_protocol_preregistration"] is False
assert receipt["candidate_manifest_access_authority"] is False
assert receipt["candidate_fit_access_authority"] is False
assert receipt["candidate_implementation_authority"] is False
assert receipt["biocortex_experiment_execution_authority"] is False
assert receipt["retrieval_order_mutation_authority"] is False
assert receipt["live_store_write_authority"] is False
assert receipt["runtime_promotion_authority"] is False
for field, value in receipt.items():
    if (
        field.startswith("ready_for_")
        or field.endswith("_authority")
        or field.endswith("_verified")
    ):
        assert value is False, field
PY

python3 - "$contract" "$preflight_contract" "$role_review_contract" \
  "$scratch" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

contract_path = Path(sys.argv[1])
preflight_contract_path = Path(sys.argv[2])
role_review_contract_path = Path(sys.argv[3])
scratch = Path(sys.argv[4])
contract = json.loads(contract_path.read_text(encoding="utf-8"))
role_review_contract = json.loads(
    role_review_contract_path.read_text(encoding="utf-8")
)
contract_sha256 = hashlib.sha256(contract_path.read_bytes()).hexdigest()
preflight_sha256 = hashlib.sha256(preflight_contract_path.read_bytes()).hexdigest()
role_review_sha256 = hashlib.sha256(role_review_contract_path.read_bytes()).hexdigest()


def digest(label):
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def write(name, value):
    path = scratch / name
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


holders = []
for role_name, independence_class, suffix in [
    ("candidate_implementer", "candidate_team", "candidate"),
    ("consumer_curator", "consumer", "curator"),
    ("freeze_reviewer", "independent_reviewer", "freeze_reviewer_1"),
    ("freeze_reviewer", "independent_reviewer", "freeze_reviewer_2"),
    ("sealed_evaluator_custodian", "independent_custodian", "custodian"),
]:
    holders.append(
        {
            "role": role_name,
            "independence_class": independence_class,
            "holder_commitment_sha256": digest(f"holder:{suffix}"),
            "appointment_receipt_sha256": digest(f"appointment:{suffix}"),
        }
    )

role = {
    "schema": "agent_bridge.engram_g1_role_commitment_packet.v1",
    "contract_id": "engram_g1_freeze_preflight_20260718",
    "contract_sha256": preflight_sha256,
    "packet_id": "synthetic_role_commitment_for_freeze_v1",
    "evidence_class": "synthetic_contract_test",
    "created_at_unix": 1784370000,
    "created_before_private_corpus_assembly": True,
    "holders": holders,
    "attestations": {
        "all_holder_commitments_distinct": True,
        "holder_commitments_use_private_salts": True,
        "consumer_curator_outside_candidate_team": True,
        "freeze_reviewers_outside_candidate_team": True,
        "sealed_custodian_outside_candidate_team": True,
        "candidate_denied_private_manifest": True,
        "candidate_denied_sealed_material": True,
        "candidate_cannot_approve_freeze": True,
        "appointments_precede_corpus_assembly": True,
        "identity_truth_requires_independent_review": True,
    },
}
role_path = write("synthetic-role.json", role)
role_sha256 = hashlib.sha256(role_path.read_bytes()).hexdigest()

role_review = {
    "schema": "agent_bridge.engram_g1_role_review_packet.v1",
    "contract_id": "engram_g1_role_review_20260718",
    "contract_sha256": role_review_sha256,
    "packet_id": digest("packet:synthetic-role-review-for-freeze"),
    "evidence_class": "synthetic_contract_test",
    "role_packet_sha256": role_sha256,
    "review_started_at_unix": 1784370100,
    "review_completed_at_unix": 1784370200,
    "application_owner_review": {
        "reviewer_role": "application_owner",
        "reviewer_commitment_sha256": digest("holder:curator"),
        "review_receipt_sha256": digest("role-review:application-owner"),
        "decision": "approve",
        "owner_is_consumer_curator": True,
        "appointment_evidence_complete": True,
        "consumer_ownership_confirmed": True,
        "workflow_authority_confirmed": True,
    },
    "independence_audit": {
        "reviewer_role": "independence_auditor",
        "auditor_commitment_sha256": digest("reviewer:independence-auditor"),
        "audit_receipt_sha256": digest("role-review:independence-auditor"),
        "decision": "approve",
        "all_role_holders_distinct": True,
        "owner_overlap_rule_reviewed": True,
        "candidate_exclusions_reviewed": True,
        "sealed_custody_reviewed": True,
        "salt_custody_reviewed": True,
        "appointment_chronology_reviewed": True,
    },
    "attestations": {
        "reviewer_commitments_use_private_salts": True,
        "candidate_did_not_author_review": True,
        "candidate_did_not_see_raw_review_evidence": True,
        "raw_identities_absent": True,
        "external_identity_truth_not_authenticated_by_validator": True,
    },
}
role_review_path = write("synthetic-role-review.json", role_review)
role_review_packet_sha256 = hashlib.sha256(role_review_path.read_bytes()).hexdigest()

owner_decision = {
    "schema": "agent_bridge.engram_g1_role_owner_decision_packet.v1",
    "contract_id": "engram_g1_role_review_20260718",
    "contract_sha256": role_review_sha256,
    "decision_id": digest("decision:synthetic-owner-endorsement-for-freeze"),
    "evidence_class": "synthetic_contract_test",
    "role_packet_sha256": role_sha256,
    "review_packet_sha256": role_review_packet_sha256,
    "owner_commitment_sha256": digest("holder:curator"),
    "decided_at_unix": 1784370300,
    "decision": "endorse_private_corpus_assembly_for_authentication",
    "owner_endorsement_receipt_sha256": digest("owner:assembly-endorsement"),
    "proposed_assembly_scope": role_review_contract["proposed_assembly_scope"],
    "attestations": {
        "application_owner_authored_endorsement": True,
        "candidate_did_not_author_decision": True,
        "candidate_did_not_see_raw_decision_evidence": True,
        "owner_commitment_uses_private_salt": True,
        "raw_identities_absent": True,
        "validator_does_not_authenticate_owner_identity": True,
    },
}
owner_decision_path = write("synthetic-owner-decision.json", owner_decision)
owner_decision_sha256 = hashlib.sha256(owner_decision_path.read_bytes()).hexdigest()


def ranks_for(signature, probe_class):
    zero = {"fts": 0, "hybrid": 0, "semantic": 0}
    if signature == "overgeneralization_gap":
        return {
            "exact": {"fts": 1, "hybrid": 7, "semantic": 1},
            "related": {"fts": 0, "hybrid": 0, "semantic": 1},
            "unrelated": {"fts": 0, "hybrid": 0, "semantic": 3},
        }[probe_class]
    if signature == "no_relevant_gap":
        return {
            "exact": {"fts": 2, "hybrid": 0, "semantic": 0},
            "related": {"fts": 0, "hybrid": 4, "semantic": 0},
            "unrelated": zero,
        }[probe_class]
    if signature == "ordinary_retrieval_gap":
        return zero
    if signature == "generalization_gap":
        return {
            "exact": {"fts": 3, "hybrid": 0, "semantic": 0},
            "related": zero,
            "unrelated": zero,
        }[probe_class]
    raise AssertionError(signature)


schedule = [
    ("fit", "overgeneralization_gap", 6),
    ("fit", "no_relevant_gap", 3),
    ("fit", "ordinary_retrieval_gap", 1),
    ("fit", "generalization_gap", 2),
    ("development", "overgeneralization_gap", 4),
    ("development", "no_relevant_gap", 3),
    ("development", "ordinary_retrieval_gap", 1),
    ("sealed", "overgeneralization_gap", 5),
    ("sealed", "no_relevant_gap", 3),
    ("sealed", "ordinary_retrieval_gap", 1),
    ("sealed", "generalization_gap", 1),
]

groups = []
group_index = 0
for partition, signature, count in schedule:
    for _ in range(count):
        is_g0 = group_index == 0
        group_commitment = (
            "5bb20800cea3bdb973ea0604fcd280e89666736b7cd9e595e24c89f4b744a1fc"
            if is_g0
            else digest(f"episode-group:{group_index}")
        )
        target_set = digest(f"target-set:{group_index}")
        probes = []
        for probe_class in ("exact", "related", "unrelated"):
            ranks = ranks_for(signature, probe_class)
            probes.append(
                {
                    "probe_class": probe_class,
                    "query_sha256": digest(f"query:{group_index}:{probe_class}"),
                    "expected_target_set_sha256": target_set,
                    "replay_ranks": [dict(ranks), dict(ranks)],
                }
            )
        groups.append(
            {
                "episode_group_id_sha256": group_commitment,
                "application_family_id_sha256": digest(
                    f"application-family:{group_index % 4}"
                ),
                "source_identity_sha256": digest(f"source:{group_index}"),
                "consumer_observation_receipt_sha256": digest(
                    f"consumer-observation:{group_index}"
                ),
                "rights_receipt_sha256": digest(f"rights:{group_index}"),
                "partition": partition,
                "declared_signature": signature,
                "is_admitted_g0_incident": is_g0,
                "provenance": {
                    "consumer_owned": True,
                    "observed_before_candidate_implementation_lock": True,
                    "candidate_authored_probes": False,
                    "rights_cleared": True,
                },
                "expected_target_set_sha256": target_set,
                "probes": probes,
            }
        )
        group_index += 1

assert len(groups) == 30
manifest = {
    "schema": "agent_bridge.engram_g1_private_corpus_manifest.v1",
    "contract_id": "engram_g1_freeze_preflight_20260718",
    "contract_sha256": preflight_sha256,
    "manifest_id": "synthetic_grouped_corpus_for_freeze_v1",
    "evidence_class": "synthetic_contract_test",
    "assembled_at_unix": 1784370400,
    "role_packet_sha256": role_sha256,
    "baseline": {
        "source_commit": "3bf8ad3a67ff02a4e717db8e29e89079f66c01cf",
        "binary_sha256": "2fcd99a55acb0e433320ada9b058651d46c10500a2ec6459866c3dd504580f30",
        "environment_sha256": "13be7b202d061a1fd37bc2405427ecf1251f85d043b8b5341c8efbc835564f5e",
        "perception_filter_state_sha256": "9569e1553c59f54bc95dc9cca9aed6cb65f1fd1b4aae2c4522629aaf63ed9b31",
        "embedding_transport": "loopback_delegated",
        "retrieval_modes": ["fts", "hybrid", "semantic"],
        "aggregate_envelope": "any_mode",
        "top_k": 10,
        "deterministic_replays": 2,
    },
    "replay_integrity": {
        "source_db_query_only": True,
        "source_db_total_changes_before": 0,
        "source_db_total_changes_after": 0,
        "base_snapshot_sha256_before": digest("base-snapshot"),
        "base_snapshot_sha256_after": digest("base-snapshot"),
        "base_snapshot_unchanged": True,
        "durable_state_sha256_before": digest("durable-state"),
        "durable_state_sha256_after": digest("durable-state"),
        "durable_state_unchanged": True,
        "fresh_snapshot_per_probe_mode_replay": True,
        "baseline_observation_count": 540,
        "live_memory_writes": 0,
        "candidate_mechanism_enabled": False,
        "biocortex_retrieval_enabled": False,
    },
    "episode_groups": groups,
    "assembly_attestations": {
        "candidate_has_not_seen_private_manifest": True,
        "candidate_has_not_seen_sealed_material": True,
        "partitioned_by_episode_group": True,
        "no_probe_crosses_partitions": True,
        "curation_completed_before_candidate_implementation_lock": True,
        "alternates_excluded_from_frozen_manifest": True,
        "commitment_salts_held_by_sealed_custodian": True,
        "contains_raw_queries": False,
        "freeze_review_not_yet_granted": True,
    },
}
manifest_path = write("synthetic-manifest.json", manifest)
manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

reviewer_checks = {
    "exact_manifest_bytes_reviewed": True,
    "roster_and_partition_counts_reviewed": True,
    "provenance_receipts_reviewed": True,
    "replay_integrity_reviewed": True,
    "application_family_cap_reviewed": True,
    "admitted_g0_fit_only_reviewed": True,
    "candidate_exclusions_reviewed": True,
    "sealed_raw_material_not_received": True,
}
reviewer_reviews = []
for suffix in ("freeze_reviewer_1", "freeze_reviewer_2"):
    reviewer_reviews.append(
        {
            "reviewer_role": "freeze_reviewer",
            "reviewer_commitment_sha256": digest(f"holder:{suffix}"),
            "freeze_review_receipt_sha256": digest(f"freeze-review:{suffix}"),
            "decision": "approve",
            **reviewer_checks,
        }
    )

freeze_review = {
    "schema": "agent_bridge.engram_g1_corpus_freeze_review_packet.v1",
    "contract_id": "engram_g1_corpus_freeze_review_20260718",
    "contract_sha256": contract_sha256,
    "packet_id": digest("packet:synthetic-corpus-freeze-review"),
    "evidence_class": "synthetic_contract_test",
    "role_packet_sha256": role_sha256,
    "role_review_packet_sha256": role_review_packet_sha256,
    "owner_decision_packet_sha256": owner_decision_sha256,
    "manifest_sha256": manifest_sha256,
    "review_started_at_unix": 1784370500,
    "review_completed_at_unix": 1784370600,
    "reviewer_reviews": reviewer_reviews,
    "custodian_attestation": {
        "custodian_role": "sealed_evaluator_custodian",
        "custodian_commitment_sha256": digest("holder:custodian"),
        "custody_receipt_sha256": digest("freeze-review:custodian"),
        "exact_manifest_in_custody": True,
        "commitment_salts_in_custody": True,
        "manifest_bytes_unchanged_during_review": True,
        "freeze_reviewers_received_hash_only_material_only": True,
        "sealed_raw_material_not_disclosed_to_candidate": True,
        "partition_membership_not_disclosed_to_candidate": True,
        "labels_not_disclosed_to_candidate": True,
        "sealed_raw_material_not_disclosed_to_freeze_reviewers": True,
    },
    "attestations": {
        "reviewer_commitments_use_private_salts": True,
        "candidate_did_not_author_or_approve_freeze_review": True,
        "candidate_did_not_receive_private_manifest": True,
        "candidate_did_not_receive_sealed_material": True,
        "raw_identities_absent": True,
        "raw_queries_absent": True,
        "external_identity_and_evidence_truth_not_authenticated_by_validator": True,
    },
}
write("synthetic-freeze-review.json", freeze_review)
PY

role_packet="$scratch/synthetic-role.json"
role_review_packet="$scratch/synthetic-role-review.json"
owner_decision="$scratch/synthetic-owner-decision.json"
manifest="$scratch/synthetic-manifest.json"
freeze_review="$scratch/synthetic-freeze-review.json"

chain_args=(
  --contract "$contract"
  --preflight-contract "$preflight_contract"
  --role-review-contract "$role_review_contract"
  --role-packet "$role_packet"
  --role-review-packet "$role_review_packet"
  --owner-decision "$owner_decision"
  --manifest "$manifest"
)

python3 "$validator" validate-chain "${chain_args[@]}" \
  >"$scratch/chain.1.json"
python3 "$validator" validate-chain "${chain_args[@]}" \
  >"$scratch/chain.2.json"
cmp "$scratch/chain.1.json" "$scratch/chain.2.json"

python3 "$validator" validate-freeze-review "${chain_args[@]}" \
  --freeze-review "$freeze_review" >"$scratch/freeze.1.json"
python3 "$validator" validate-freeze-review "${chain_args[@]}" \
  --freeze-review "$freeze_review" >"$scratch/freeze.2.json"
cmp "$scratch/freeze.1.json" "$scratch/freeze.2.json"
(
  cd "$scratch"
  python3 "$repo_root/$validator" validate-freeze-review \
    --contract "$repo_root/$contract" \
    --preflight-contract "$repo_root/$preflight_contract" \
    --role-review-contract "$repo_root/$role_review_contract" \
    --role-packet "$role_packet" \
    --role-review-packet "$role_review_packet" \
    --owner-decision "$owner_decision" --manifest "$manifest" \
    --freeze-review "$freeze_review"
) >"$scratch/freeze.outside-cwd.json"
cmp "$scratch/freeze.1.json" "$scratch/freeze.outside-cwd.json"

python3 - "$scratch/chain.1.json" "$scratch/freeze.1.json" "$role_packet" \
  "$role_review_packet" "$owner_decision" "$freeze_review" "$manifest" <<'PY'
import json
import sys
from pathlib import Path

chain = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
freeze = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
role = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
role_review = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
owner = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
freeze_review = json.loads(Path(sys.argv[6]).read_text(encoding="utf-8"))
manifest = json.loads(Path(sys.argv[7]).read_text(encoding="utf-8"))

assert chain["input_chain_verdict"] == "SYNTHETIC_FREEZE_CHAIN_VALID_NO_AUTHORITY"
assert chain["structural_chain_complete"] is True
assert chain["secure_custody_capture_verified"] is False
assert chain["ready_for_authenticated_freeze_authority_review"] is False
assert chain["authenticated_assembly_authority_verified"] is False
assert chain["episode_group_count"] == 30
assert chain["partition_counts"] == {"development": 8, "fit": 12, "sealed": 10}
assert chain["signature_counts"] == {
    "generalization_gap": 3,
    "no_relevant_gap": 9,
    "ordinary_retrieval_gap": 3,
    "overgeneralization_gap": 15,
}
assert chain["private_corpus_assembly_authority"] is False
assert chain["g1_corpus_freeze_authority"] is False
assert chain["ready_for_candidate_protocol_preregistration"] is False
assert chain["candidate_manifest_access_authority"] is False
assert chain["candidate_fit_access_authority"] is False
assert chain["candidate_implementation_authority"] is False
assert chain["biocortex_experiment_execution_authority"] is False
assert chain["retrieval_order_mutation_authority"] is False
assert chain["live_store_write_authority"] is False
assert chain["runtime_promotion_authority"] is False

assert freeze["freeze_review_verdict"] == "SYNTHETIC_FREEZE_ENDORSEMENT_VALID_NO_AUTHORITY"
assert freeze["structural_freeze_endorsement_complete"] is True
assert freeze["secure_custody_capture_verified"] is False
assert freeze["freeze_reviewer_approve_count"] == 2
assert freeze["freeze_reviewer_reject_count"] == 0
assert freeze["ready_for_authenticated_freeze_authority_review"] is False
assert freeze["authenticated_freeze_authority_verified"] is False
assert freeze["ready_for_candidate_protocol_preregistration"] is False
assert freeze["private_corpus_assembly_authority"] is False
assert freeze["g1_corpus_freeze_authority"] is False
assert freeze["candidate_manifest_access_authority"] is False
assert freeze["candidate_fit_access_authority"] is False
assert freeze["candidate_implementation_authority"] is False
assert freeze["biocortex_experiment_execution_authority"] is False
assert freeze["retrieval_order_mutation_authority"] is False
assert freeze["live_store_write_authority"] is False
assert freeze["runtime_promotion_authority"] is False
assert freeze["group_identifiers_in_receipt"] is False
assert freeze["partition_membership_in_receipt"] is False
assert freeze["holder_or_reviewer_commitments_in_receipt"] is False
assert freeze["appointment_review_or_custody_receipts_in_receipt"] is False
assert freeze["freeze_review_packet_identifier_in_receipt"] is False
assert "packet_id" not in freeze

private_commitments = {
    field
    for holder in role["holders"]
    for field in (
        holder["holder_commitment_sha256"],
        holder["appointment_receipt_sha256"],
    )
}
private_commitments.update(
    {
        role_review["application_owner_review"]["reviewer_commitment_sha256"],
        role_review["application_owner_review"]["review_receipt_sha256"],
        role_review["independence_audit"]["auditor_commitment_sha256"],
        role_review["independence_audit"]["audit_receipt_sha256"],
        owner["owner_commitment_sha256"],
        owner["owner_endorsement_receipt_sha256"],
        freeze_review["custodian_attestation"]["custodian_commitment_sha256"],
        freeze_review["custodian_attestation"]["custody_receipt_sha256"],
    }
)
for review in freeze_review["reviewer_reviews"]:
    private_commitments.add(review["reviewer_commitment_sha256"])
    private_commitments.add(review["freeze_review_receipt_sha256"])
for group in manifest["episode_groups"]:
    private_commitments.update(
        {
            group["episode_group_id_sha256"],
            group["application_family_id_sha256"],
            group["source_identity_sha256"],
            group["consumer_observation_receipt_sha256"],
            group["rights_receipt_sha256"],
            group["expected_target_set_sha256"],
        }
    )
    for probe in group["probes"]:
        private_commitments.add(probe["query_sha256"])
        private_commitments.add(probe["expected_target_set_sha256"])

private_packet_identifiers = {
    role["packet_id"],
    role_review["packet_id"],
    owner["decision_id"],
    freeze_review["packet_id"],
}


def string_leaves(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from string_leaves(child)
    elif isinstance(value, list):
        for child in value:
            yield from string_leaves(child)
    elif isinstance(value, str):
        yield value


assert private_commitments.isdisjoint(set(string_leaves(chain)))
assert private_commitments.isdisjoint(set(string_leaves(freeze)))
assert private_packet_identifiers.isdisjoint(set(string_leaves(chain)))
assert private_packet_identifiers.isdisjoint(set(string_leaves(freeze)))
PY

python3 - "$contract" "$role_packet" "$role_review_packet" "$owner_decision" \
  "$manifest" "$freeze_review" "$scratch" "$private_scratch" <<'PY'
import copy
import hashlib
import json
import sys
from pathlib import Path

contract_path = Path(sys.argv[1])
contract = json.loads(contract_path.read_text(encoding="utf-8"))
contract_sha256 = hashlib.sha256(contract_path.read_bytes()).hexdigest()
role = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
role_review = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
owner = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
manifest = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
freeze = json.loads(Path(sys.argv[6]).read_text(encoding="utf-8"))
scratch = Path(sys.argv[7])
private_scratch = Path(sys.argv[8])


def digest(label):
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def write(name, value):
    path = scratch / f"{name}.json"
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def write_private(name, value):
    path = private_scratch / f"{name}.json"
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


public_alias_targets = {
    "contract": contract_sha256,
    "current_validator": hashlib.sha256(
        Path("scripts/eval/engram_g1_corpus_freeze_review.py").read_bytes()
    ).hexdigest(),
    "predecessor_validator": contract["predecessors"]["freeze_preflight"][
        "validator_sha256"
    ],
    "packet": freeze["role_packet_sha256"],
}
alias_cases = [
    ("chain-id-vs-contract", "chain_packet_id", "contract"),
    (
        "chain-commitment-vs-predecessor-validator",
        "chain_commitment",
        "predecessor_validator",
    ),
    ("chain-receipt-vs-packet", "chain_receipt", "packet"),
    ("group-id-vs-contract", "group_identifier", "contract"),
    ("query-vs-current-validator", "query", "current_validator"),
    ("target-vs-packet", "target", "packet"),
    ("review-receipt-vs-contract", "current_review_receipt", "contract"),
    (
        "custody-receipt-vs-predecessor-validator",
        "current_custody_receipt",
        "predecessor_validator",
    ),
    ("freeze-id-vs-current-validator", "current_packet_id", "current_validator"),
]
assert {case[1] for case in alias_cases} == {
    "chain_packet_id",
    "chain_commitment",
    "chain_receipt",
    "group_identifier",
    "query",
    "target",
    "current_review_receipt",
    "current_custody_receipt",
    "current_packet_id",
}
assert {case[2] for case in alias_cases} == {
    "contract",
    "current_validator",
    "predecessor_validator",
    "packet",
}


def write_alias_case(case_name, value_class, target_class):
    role_case = copy.deepcopy(role)
    review_case = copy.deepcopy(role_review)
    owner_case = copy.deepcopy(owner)
    manifest_case = copy.deepcopy(manifest)
    freeze_case = copy.deepcopy(freeze)
    target = public_alias_targets[target_class]

    if value_class == "chain_packet_id":
        review_case["packet_id"] = target
    elif value_class == "chain_commitment":
        holder = next(
            holder
            for holder in role_case["holders"]
            if holder["role"] == "freeze_reviewer"
        )
        old_commitment = holder["holder_commitment_sha256"]
        holder["holder_commitment_sha256"] = target
        freeze_review = next(
            review
            for review in freeze_case["reviewer_reviews"]
            if review["reviewer_commitment_sha256"] == old_commitment
        )
        freeze_review["reviewer_commitment_sha256"] = target
    elif value_class == "chain_receipt":
        owner_case["owner_endorsement_receipt_sha256"] = target
    elif value_class == "group_identifier":
        manifest_case["episode_groups"][1]["episode_group_id_sha256"] = target
    elif value_class == "query":
        manifest_case["episode_groups"][1]["probes"][0]["query_sha256"] = target
    elif value_class == "target":
        group = manifest_case["episode_groups"][1]
        group["expected_target_set_sha256"] = target
        for probe in group["probes"]:
            probe["expected_target_set_sha256"] = target
    elif value_class == "current_review_receipt":
        freeze_case["reviewer_reviews"][0]["freeze_review_receipt_sha256"] = target
    elif value_class == "current_custody_receipt":
        freeze_case["custodian_attestation"]["custody_receipt_sha256"] = target
    elif value_class == "current_packet_id":
        freeze_case["packet_id"] = target
    else:
        raise AssertionError(value_class)

    case_dir = scratch / f"redacted-alias-{case_name}"
    case_dir.mkdir()

    def write_case_packet(name, value):
        path = case_dir / f"{name}.json"
        path.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    role_case_path = write_case_packet("role", role_case)
    role_case_sha256 = hashlib.sha256(role_case_path.read_bytes()).hexdigest()
    review_case["role_packet_sha256"] = role_case_sha256
    review_case_path = write_case_packet("role-review", review_case)
    review_case_sha256 = hashlib.sha256(review_case_path.read_bytes()).hexdigest()
    owner_case["role_packet_sha256"] = role_case_sha256
    owner_case["review_packet_sha256"] = review_case_sha256
    owner_case_path = write_case_packet("owner", owner_case)
    owner_case_sha256 = hashlib.sha256(owner_case_path.read_bytes()).hexdigest()
    manifest_case["role_packet_sha256"] = role_case_sha256
    manifest_case_path = write_case_packet("manifest", manifest_case)
    manifest_case_sha256 = hashlib.sha256(manifest_case_path.read_bytes()).hexdigest()
    freeze_case["role_packet_sha256"] = role_case_sha256
    freeze_case["role_review_packet_sha256"] = review_case_sha256
    freeze_case["owner_decision_packet_sha256"] = owner_case_sha256
    freeze_case["manifest_sha256"] = manifest_case_sha256
    write_case_packet("freeze", freeze_case)


for alias_case in alias_cases:
    write_alias_case(*alias_case)


relaxed = copy.deepcopy(contract)
relaxed["proposed_freeze_scope"]["permits_group_substitution"] = True
write("contract-relaxed", relaxed)

owner_reject = copy.deepcopy(owner)
owner_reject["decision"] = "reject_role_roster"
write("owner-reject", owner_reject)

owner_receipt_alias_role = copy.deepcopy(owner)
owner_receipt_alias_role["owner_endorsement_receipt_sha256"] = owner[
    "role_packet_sha256"
]
write("owner-receipt-alias-role-packet", owner_receipt_alias_role)

owner_receipt_alias_contract = copy.deepcopy(owner)
owner_receipt_alias_contract["owner_endorsement_receipt_sha256"] = contract_sha256
write("owner-receipt-alias-g13-contract", owner_receipt_alias_contract)

owner_id_alias_contract = copy.deepcopy(owner)
owner_id_alias_contract["decision_id"] = contract_sha256
write("owner-id-alias-g13-contract", owner_id_alias_contract)

manifest_before_owner = copy.deepcopy(manifest)
manifest_before_owner["assembled_at_unix"] = owner["decided_at_unix"]
write("manifest-before-owner", manifest_before_owner)

manifest_group_alias_owner = copy.deepcopy(manifest)
manifest_group_alias_owner["episode_groups"][1]["episode_group_id_sha256"] = freeze[
    "owner_decision_packet_sha256"
]
write("manifest-group-alias-owner-packet", manifest_group_alias_owner)

manifest_group_alias_validator = copy.deepcopy(manifest)
manifest_group_alias_validator["episode_groups"][1][
    "episode_group_id_sha256"
] = contract["predecessors"]["freeze_preflight"]["validator_sha256"]
write("manifest-group-alias-preflight-validator", manifest_group_alias_validator)

manifest_source_alias_contract = copy.deepcopy(manifest)
manifest_source_alias_contract["episode_groups"][1][
    "source_identity_sha256"
] = contract["predecessors"]["role_review"]["contract_sha256"]
write("manifest-source-alias-role-review-contract", manifest_source_alias_contract)

manifest_query_alias_packet = copy.deepcopy(manifest)
manifest_query_alias_packet["episode_groups"][1]["probes"][0][
    "query_sha256"
] = freeze["role_packet_sha256"]
write("manifest-query-alias-role-packet", manifest_query_alias_packet)

manifest_target_alias_validator = copy.deepcopy(manifest)
aliased_target = contract["predecessors"]["role_review"]["validator_sha256"]
manifest_target_alias_validator["episode_groups"][1][
    "expected_target_set_sha256"
] = aliased_target
for probe in manifest_target_alias_validator["episode_groups"][1]["probes"]:
    probe["expected_target_set_sha256"] = aliased_target
write("manifest-target-alias-role-review-validator", manifest_target_alias_validator)

freeze_mutations = {}
for field in (
    "role_packet_sha256",
    "role_review_packet_sha256",
    "owner_decision_packet_sha256",
    "manifest_sha256",
):
    mutation = copy.deepcopy(freeze)
    mutation[field] = "f" * 64
    freeze_mutations[f"freeze-{field}-drift"] = mutation

early_review = copy.deepcopy(freeze)
early_review["review_started_at_unix"] = manifest["assembled_at_unix"]
freeze_mutations["freeze-review-chronology"] = early_review

candidate_reviewer = copy.deepcopy(freeze)
candidate_reviewer["reviewer_reviews"][0]["reviewer_commitment_sha256"] = digest(
    "holder:candidate"
)
freeze_mutations["freeze-candidate-reviewer"] = candidate_reviewer

duplicate_reviewer = copy.deepcopy(freeze)
duplicate_reviewer["reviewer_reviews"][1][
    "reviewer_commitment_sha256"
] = duplicate_reviewer["reviewer_reviews"][0]["reviewer_commitment_sha256"]
freeze_mutations["freeze-duplicate-reviewer"] = duplicate_reviewer

outsider_reviewer = copy.deepcopy(freeze)
outsider_reviewer["reviewer_reviews"][0][
    "reviewer_commitment_sha256"
] = digest("reviewer:outsider")
freeze_mutations["freeze-outsider-reviewer"] = outsider_reviewer

missing_check = copy.deepcopy(freeze)
missing_check["reviewer_reviews"][0]["provenance_receipts_reviewed"] = False
freeze_mutations["freeze-approval-missing-check"] = missing_check

zero_receipt = copy.deepcopy(freeze)
zero_receipt["reviewer_reviews"][0]["freeze_review_receipt_sha256"] = "0" * 64
freeze_mutations["freeze-zero-review-receipt"] = zero_receipt

duplicate_receipt = copy.deepcopy(freeze)
duplicate_receipt["reviewer_reviews"][1][
    "freeze_review_receipt_sha256"
] = duplicate_receipt["reviewer_reviews"][0]["freeze_review_receipt_sha256"]
freeze_mutations["freeze-duplicate-review-receipt"] = duplicate_receipt

review_receipt_alias_manifest = copy.deepcopy(freeze)
review_receipt_alias_manifest["reviewer_reviews"][0][
    "freeze_review_receipt_sha256"
] = freeze["manifest_sha256"]
freeze_mutations["freeze-review-receipt-alias-manifest"] = (
    review_receipt_alias_manifest
)

wrong_custodian = copy.deepcopy(freeze)
wrong_custodian["custodian_attestation"][
    "custodian_commitment_sha256"
] = digest("holder:freeze_reviewer_1")
freeze_mutations["freeze-wrong-custodian"] = wrong_custodian

custody_receipt_reuse = copy.deepcopy(freeze)
custody_receipt_reuse["custodian_attestation"][
    "custody_receipt_sha256"
] = custody_receipt_reuse["reviewer_reviews"][0]["freeze_review_receipt_sha256"]
freeze_mutations["freeze-custody-receipt-reuse"] = custody_receipt_reuse

custody_receipt_alias_owner = copy.deepcopy(freeze)
custody_receipt_alias_owner["custodian_attestation"][
    "custody_receipt_sha256"
] = freeze["owner_decision_packet_sha256"]
freeze_mutations["freeze-custody-receipt-alias-owner-decision"] = (
    custody_receipt_alias_owner
)

custody_broken = copy.deepcopy(freeze)
custody_broken["custodian_attestation"][
    "manifest_bytes_unchanged_during_review"
] = False
freeze_mutations["freeze-custody-broken"] = custody_broken

candidate_authored = copy.deepcopy(freeze)
candidate_authored["attestations"][
    "candidate_did_not_author_or_approve_freeze_review"
] = False
freeze_mutations["freeze-candidate-authored"] = candidate_authored

raw_identity = copy.deepcopy(freeze)
raw_identity["reviewer_reviews"][0]["name"] = "forbidden"
freeze_mutations["freeze-raw-identity"] = raw_identity

nonopaque_packet_id = copy.deepcopy(freeze)
nonopaque_packet_id["packet_id"] = "freeze_review_for_alice"
freeze_mutations["freeze-nonopaque-packet-id"] = nonopaque_packet_id

packet_id_alias_holder = copy.deepcopy(freeze)
packet_id_alias_holder["packet_id"] = role["holders"][0][
    "holder_commitment_sha256"
]
freeze_mutations["freeze-packet-id-alias-holder"] = packet_id_alias_holder

packet_id_alias_review_receipt = copy.deepcopy(freeze)
packet_id_alias_review_receipt["packet_id"] = role_review[
    "application_owner_review"
]["review_receipt_sha256"]
freeze_mutations["freeze-packet-id-alias-role-review-receipt"] = (
    packet_id_alias_review_receipt
)

packet_id_alias_custody = copy.deepcopy(freeze)
packet_id_alias_custody["packet_id"] = freeze["custodian_attestation"][
    "custody_receipt_sha256"
]
freeze_mutations["freeze-packet-id-alias-custody-receipt"] = (
    packet_id_alias_custody
)

packet_id_alias_manifest = copy.deepcopy(freeze)
packet_id_alias_manifest["packet_id"] = freeze["manifest_sha256"]
freeze_mutations["freeze-packet-id-alias-manifest"] = packet_id_alias_manifest

for name, value in freeze_mutations.items():
    write(name, value)

one_reject = copy.deepcopy(freeze)
one_reject["reviewer_reviews"][1]["decision"] = "reject"
write("freeze-one-reject", one_reject)

real_role = copy.deepcopy(role)
real_role["evidence_class"] = "consumer_owned_real"
real_role_path = write("real-role-outside-data", real_role)
real_role_sha256 = hashlib.sha256(real_role_path.read_bytes()).hexdigest()

real_role_review = copy.deepcopy(role_review)
real_role_review["evidence_class"] = "consumer_owned_real"
real_role_review["role_packet_sha256"] = real_role_sha256
real_role_review_path = write("real-role-review-outside-data", real_role_review)
real_role_review_sha256 = hashlib.sha256(real_role_review_path.read_bytes()).hexdigest()

real_owner = copy.deepcopy(owner)
real_owner["evidence_class"] = "consumer_owned_real"
real_owner["role_packet_sha256"] = real_role_sha256
real_owner["review_packet_sha256"] = real_role_review_sha256
real_owner_path = write("real-owner-outside-data", real_owner)
real_owner_sha256 = hashlib.sha256(real_owner_path.read_bytes()).hexdigest()

real_manifest = copy.deepcopy(manifest)
real_manifest["evidence_class"] = "consumer_owned_real"
real_manifest["role_packet_sha256"] = real_role_sha256
real_manifest_path = write("real-manifest-outside-data", real_manifest)
real_manifest_sha256 = hashlib.sha256(real_manifest_path.read_bytes()).hexdigest()

real_freeze = copy.deepcopy(freeze)
real_freeze["evidence_class"] = "consumer_owned_real"
real_freeze["role_packet_sha256"] = real_role_sha256
real_freeze["role_review_packet_sha256"] = real_role_review_sha256
real_freeze["owner_decision_packet_sha256"] = real_owner_sha256
real_freeze["manifest_sha256"] = real_manifest_sha256
write("real-freeze-outside-data", real_freeze)

forged_real_role = copy.deepcopy(role)
forged_real_role["evidence_class"] = "consumer_owned_real"
forged_real_role_path = write_private("forged-real-role", forged_real_role)
forged_real_role_sha256 = hashlib.sha256(
    forged_real_role_path.read_bytes()
).hexdigest()

forged_real_role_review = copy.deepcopy(role_review)
forged_real_role_review["evidence_class"] = "consumer_owned_real"
forged_real_role_review["role_packet_sha256"] = forged_real_role_sha256
forged_real_role_review_path = write_private(
    "forged-real-role-review", forged_real_role_review
)
forged_real_role_review_sha256 = hashlib.sha256(
    forged_real_role_review_path.read_bytes()
).hexdigest()

forged_real_owner = copy.deepcopy(owner)
forged_real_owner["evidence_class"] = "consumer_owned_real"
forged_real_owner["role_packet_sha256"] = forged_real_role_sha256
forged_real_owner["review_packet_sha256"] = forged_real_role_review_sha256
forged_real_owner_path = write_private("forged-real-owner", forged_real_owner)
forged_real_owner_sha256 = hashlib.sha256(
    forged_real_owner_path.read_bytes()
).hexdigest()

forged_real_manifest = copy.deepcopy(manifest)
forged_real_manifest["evidence_class"] = "consumer_owned_real"
forged_real_manifest["role_packet_sha256"] = forged_real_role_sha256
forged_real_manifest_path = write_private(
    "forged-real-manifest", forged_real_manifest
)
forged_real_manifest_sha256 = hashlib.sha256(
    forged_real_manifest_path.read_bytes()
).hexdigest()

forged_real_freeze = copy.deepcopy(freeze)
forged_real_freeze["evidence_class"] = "consumer_owned_real"
forged_real_freeze["role_packet_sha256"] = forged_real_role_sha256
forged_real_freeze["role_review_packet_sha256"] = (
    forged_real_role_review_sha256
)
forged_real_freeze["owner_decision_packet_sha256"] = forged_real_owner_sha256
forged_real_freeze["manifest_sha256"] = forged_real_manifest_sha256
write_private("forged-real-freeze", forged_real_freeze)
PY

if python3 "$validator" validate-contract \
  --contract "$scratch/contract-relaxed.json" >/dev/null 2>&1; then
  echo "relaxed G1.3 contract was not rejected" >&2
  exit 1
fi

if python3 "$validator" validate-chain \
  --contract "$contract" --preflight-contract "$preflight_contract" \
  --role-review-contract "$role_review_contract" --role-packet "$role_packet" \
  --role-review-packet "$role_review_packet" \
  --owner-decision "$scratch/owner-reject.json" --manifest "$manifest" \
  >/dev/null 2>&1; then
  echo "G1.3 accepted a rejecting owner decision" >&2
  exit 1
fi

if python3 "$validator" validate-chain \
  --contract "$contract" --preflight-contract "$preflight_contract" \
  --role-review-contract "$role_review_contract" --role-packet "$role_packet" \
  --role-review-packet "$role_review_packet" --owner-decision "$owner_decision" \
  --manifest "$scratch/manifest-before-owner.json" >/dev/null 2>&1; then
  echo "G1.3 accepted manifest assembly before owner endorsement" >&2
  exit 1
fi

if python3 "$validator" validate-chain \
  --contract "$contract" --preflight-contract "$preflight_contract" \
  --role-review-contract "$role_review_contract" --role-packet "$role_packet" \
  --role-review-packet "$role_review_packet" \
  --owner-decision "$scratch/owner-receipt-alias-role-packet.json" \
  --manifest "$manifest" >/dev/null 2>&1; then
  echo "G1.3 accepted a redacted owner receipt aliasing a public packet hash" >&2
  exit 1
fi

if python3 "$validator" validate-chain \
  --contract "$contract" --preflight-contract "$preflight_contract" \
  --role-review-contract "$role_review_contract" --role-packet "$role_packet" \
  --role-review-packet "$role_review_packet" \
  --owner-decision "$scratch/owner-receipt-alias-g13-contract.json" \
  --manifest "$manifest" >/dev/null \
  2>"$scratch/owner-receipt-alias-g13-contract.stderr"; then
  echo "G1.3 accepted a redacted owner receipt aliasing the public contract hash" >&2
  exit 1
fi
if ! grep -Fq \
  "input_chain contains a redacted SHA-256 value that aliases a public receipt digest" \
  "$scratch/owner-receipt-alias-g13-contract.stderr"; then
  echo "G1.3 contract-alias regression was rejected for the wrong reason" >&2
  exit 1
fi

if python3 "$validator" validate-chain \
  --contract "$contract" --preflight-contract "$preflight_contract" \
  --role-review-contract "$role_review_contract" --role-packet "$role_packet" \
  --role-review-packet "$role_review_packet" --owner-decision "$owner_decision" \
  --manifest "$scratch/manifest-group-alias-owner-packet.json" \
  >/dev/null 2>&1; then
  echo "G1.3 accepted a redacted group identifier aliasing a public packet hash" >&2
  exit 1
fi

if python3 "$validator" validate-chain \
  --contract "$contract" --preflight-contract "$preflight_contract" \
  --role-review-contract "$role_review_contract" --role-packet "$role_packet" \
  --role-review-packet "$role_review_packet" --owner-decision "$owner_decision" \
  --manifest "$scratch/manifest-group-alias-preflight-validator.json" \
  >/dev/null 2>"$scratch/manifest-group-alias-preflight-validator.stderr"; then
  echo "G1.3 accepted a redacted group identifier aliasing a public validator hash" >&2
  exit 1
fi
if ! grep -Fq \
  "input_chain contains a redacted SHA-256 value that aliases a public receipt digest" \
  "$scratch/manifest-group-alias-preflight-validator.stderr"; then
  echo "G1.3 validator-alias regression was rejected for the wrong reason" >&2
  exit 1
fi

for alias_case in \
  owner-id-alias-g13-contract \
  manifest-source-alias-role-review-contract \
  manifest-query-alias-role-packet \
  manifest-target-alias-role-review-validator; do
  alias_owner="$owner_decision"
  alias_manifest="$manifest"
  case "$alias_case" in
    owner-*)
      alias_owner="$scratch/$alias_case.json"
      ;;
    manifest-*)
      alias_manifest="$scratch/$alias_case.json"
      ;;
  esac
  if python3 "$validator" validate-chain \
    --contract "$contract" --preflight-contract "$preflight_contract" \
    --role-review-contract "$role_review_contract" --role-packet "$role_packet" \
    --role-review-packet "$role_review_packet" --owner-decision "$alias_owner" \
    --manifest "$alias_manifest" >/dev/null \
    2>"$scratch/$alias_case.stderr"; then
    echo "G1.3 accepted a redacted SHA-256 alias: $alias_case" >&2
    exit 1
  fi
  if ! grep -Fq \
    "input_chain contains a redacted SHA-256 value that aliases a public receipt digest" \
    "$scratch/$alias_case.stderr"; then
    echo "G1.3 alias regression was rejected for the wrong reason: $alias_case" >&2
    exit 1
  fi
done

alias_case_count=0
for alias_case_dir in "$scratch"/redacted-alias-*; do
  alias_case_count=$((alias_case_count + 1))
  alias_error="$alias_case_dir/rejection.err"
  if python3 "$validator" validate-freeze-review \
    --contract "$contract" --preflight-contract "$preflight_contract" \
    --role-review-contract "$role_review_contract" \
    --role-packet "$alias_case_dir/role.json" \
    --role-review-packet "$alias_case_dir/role-review.json" \
    --owner-decision "$alias_case_dir/owner.json" \
    --manifest "$alias_case_dir/manifest.json" \
    --freeze-review "$alias_case_dir/freeze.json" \
    >/dev/null 2>"$alias_error"; then
    echo "G1.3 accepted redacted/public alias matrix case: $alias_case_dir" >&2
    exit 1
  fi
  alias_error_text="$(<"$alias_error")"
  if [[ "$alias_error_text" != *"redacted SHA-256 value that aliases a public receipt digest"* ]]; then
    echo "G1.3 alias matrix case failed before the alias guard: $alias_case_dir" >&2
    exit 1
  fi
done
if [[ "$alias_case_count" -ne 9 ]]; then
  echo "G1.3 alias matrix did not execute all 9 registered cases" >&2
  exit 1
fi

for mutation in \
  freeze-role_packet_sha256-drift freeze-role_review_packet_sha256-drift \
  freeze-owner_decision_packet_sha256-drift freeze-manifest_sha256-drift \
  freeze-review-chronology freeze-candidate-reviewer \
  freeze-duplicate-reviewer freeze-outsider-reviewer \
  freeze-approval-missing-check freeze-zero-review-receipt \
  freeze-duplicate-review-receipt freeze-review-receipt-alias-manifest \
  freeze-wrong-custodian freeze-custody-receipt-reuse \
  freeze-custody-receipt-alias-owner-decision freeze-custody-broken \
  freeze-candidate-authored freeze-raw-identity \
  freeze-nonopaque-packet-id freeze-packet-id-alias-holder \
  freeze-packet-id-alias-role-review-receipt \
  freeze-packet-id-alias-custody-receipt \
  freeze-packet-id-alias-manifest; do
  if python3 "$validator" validate-freeze-review "${chain_args[@]}" \
    --freeze-review "$scratch/$mutation.json" >/dev/null 2>&1; then
    echo "G1.3 freeze-review mutation was not rejected: $mutation" >&2
    exit 1
  fi
done

python3 "$validator" validate-freeze-review "${chain_args[@]}" \
  --freeze-review "$scratch/freeze-one-reject.json" \
  >"$scratch/freeze-one-reject.receipt.json"
python3 - "$scratch/freeze-one-reject.receipt.json" <<'PY'
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert receipt["freeze_review_verdict"] == "SYNTHETIC_FREEZE_REJECTION_VALID_NO_AUTHORITY"
assert receipt["structural_freeze_endorsement_complete"] is False
assert receipt["secure_custody_capture_verified"] is False
assert receipt["freeze_reviewer_approve_count"] == 1
assert receipt["freeze_reviewer_reject_count"] == 1
assert receipt["g1_corpus_freeze_authority"] is False
assert receipt["ready_for_authenticated_freeze_authority_review"] is False
assert receipt["ready_for_candidate_protocol_preregistration"] is False
PY

if python3 "$validator" validate-freeze-review \
  --contract "$contract" --preflight-contract "$preflight_contract" \
  --role-review-contract "$role_review_contract" \
  --role-packet "$scratch/real-role-outside-data.json" \
  --role-review-packet "$scratch/real-role-review-outside-data.json" \
  --owner-decision "$scratch/real-owner-outside-data.json" \
  --manifest "$scratch/real-manifest-outside-data.json" \
  --freeze-review "$scratch/real-freeze-outside-data.json" \
  >/dev/null 2>&1; then
  echo "real G1.3 packets outside ignored data/ were not rejected" >&2
  exit 1
fi

python3 "$validator" validate-chain \
  --contract "$contract" --preflight-contract "$preflight_contract" \
  --role-review-contract "$role_review_contract" \
  --role-packet "$private_scratch/forged-real-role.json" \
  --role-review-packet "$private_scratch/forged-real-role-review.json" \
  --owner-decision "$private_scratch/forged-real-owner.json" \
  --manifest "$private_scratch/forged-real-manifest.json" \
  >"$scratch/forged-real-chain.receipt.json"
python3 - "$scratch/forged-real-chain.receipt.json" <<'PY'
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert receipt["input_chain_verdict"] == (
    "CLAIMED_REAL_CHAIN_STRUCTURALLY_VALID_SECURE_CUSTODY_REQUIRED"
)
assert receipt["structural_chain_complete"] is True
assert receipt["secure_custody_capture_verified"] is False
assert receipt["ready_for_authenticated_freeze_authority_review"] is False
assert receipt["authenticated_assembly_authority_verified"] is False
assert receipt["private_corpus_assembly_authority"] is False
assert receipt["g1_corpus_freeze_authority"] is False
assert receipt["ready_for_candidate_protocol_preregistration"] is False
assert receipt["candidate_manifest_access_authority"] is False
assert receipt["candidate_fit_access_authority"] is False
assert receipt["candidate_implementation_authority"] is False
assert receipt["biocortex_experiment_execution_authority"] is False
assert receipt["retrieval_order_mutation_authority"] is False
assert receipt["live_store_write_authority"] is False
assert receipt["runtime_promotion_authority"] is False
for field, value in receipt.items():
    if (
        field.startswith("ready_for_")
        or field.endswith("_authority")
        or field.endswith("_verified")
    ):
        assert value is False, field
PY

python3 "$validator" validate-freeze-review \
  --contract "$contract" --preflight-contract "$preflight_contract" \
  --role-review-contract "$role_review_contract" \
  --role-packet "$private_scratch/forged-real-role.json" \
  --role-review-packet "$private_scratch/forged-real-role-review.json" \
  --owner-decision "$private_scratch/forged-real-owner.json" \
  --manifest "$private_scratch/forged-real-manifest.json" \
  --freeze-review "$private_scratch/forged-real-freeze.json" \
  >"$scratch/forged-real-freeze.receipt.json"
python3 - "$scratch/forged-real-freeze.receipt.json" <<'PY'
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert receipt["freeze_review_verdict"] == (
    "CLAIMED_REAL_FREEZE_ENDORSEMENT_REQUIRES_SECURE_CUSTODY_CAPTURE"
)
assert receipt["structural_freeze_endorsement_complete"] is True
assert receipt["secure_custody_capture_verified"] is False
assert receipt["ready_for_authenticated_freeze_authority_review"] is False
assert receipt["authenticated_freeze_authority_verified"] is False
assert receipt["real_world_identity_authenticated_by_validator"] is False
assert receipt["ready_for_candidate_protocol_preregistration"] is False
assert receipt["private_corpus_assembly_authority"] is False
assert receipt["g1_corpus_freeze_authority"] is False
assert receipt["candidate_manifest_access_authority"] is False
assert receipt["candidate_fit_access_authority"] is False
assert receipt["candidate_implementation_authority"] is False
assert receipt["biocortex_experiment_execution_authority"] is False
assert receipt["retrieval_order_mutation_authority"] is False
assert receipt["live_store_write_authority"] is False
assert receipt["runtime_promotion_authority"] is False
assert receipt["freeze_review_packet_identifier_in_receipt"] is False
assert "packet_id" not in receipt
for field, value in receipt.items():
    if (
        field.startswith("ready_for_")
        or field.endswith("_authority")
        or field.endswith("_verified")
    ):
        assert value is False, field
PY

printf '{"schema":"%s","schema":"duplicate"}\n' \
  "agent_bridge.engram_g1_corpus_freeze_review_contract.v1" \
  >"$scratch/duplicate.json"
if python3 "$validator" validate-contract --contract "$scratch/duplicate.json" \
  >/dev/null 2>&1; then
  echo "duplicate JSON field was not rejected" >&2
  exit 1
fi

git diff --check
git diff --cached --check
echo "engram G1 corpus freeze review: PASS"
