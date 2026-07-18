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
trap 'rm -rf "$scratch"' EXIT

python3 -m py_compile "$validator"
bash -n "$0"

python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/contract.1.json"
python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/contract.2.json"
cmp "$scratch/contract.1.json" "$scratch/contract.2.json"

python3 - "$scratch/contract.1.json" "$contract" "$preflight_contract" \
  "$preflight_validator" "$role_review_contract" "$role_review_validator" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
contract = Path(sys.argv[2])
preflight_contract = Path(sys.argv[3])
preflight_validator = Path(sys.argv[4])
role_review_contract = Path(sys.argv[5])
role_review_validator = Path(sys.argv[6])

assert hashlib.sha256(contract.read_bytes()).hexdigest() == receipt["contract_sha256"]
assert hashlib.sha256(preflight_contract.read_bytes()).hexdigest() == receipt["preflight_contract_sha256"]
assert hashlib.sha256(preflight_validator.read_bytes()).hexdigest() == receipt["preflight_validator_sha256"]
assert hashlib.sha256(role_review_contract.read_bytes()).hexdigest() == receipt["role_review_contract_sha256"]
assert hashlib.sha256(role_review_validator.read_bytes()).hexdigest() == receipt["role_review_validator_sha256"]
assert receipt["contract_verdict"] == "READY_FOR_PRIVATE_CORPUS_FREEZE_REVIEW_PACKET"
assert receipt["ready_for_private_corpus_freeze_review_packet"] is True
assert receipt["required_freeze_reviewer_count"] == 2
assert receipt["frozen_episode_groups"] == 30
assert receipt["requires_new_review_for_any_manifest_change"] is True
assert receipt["current_g1_corpus_freeze_authority"] is False
assert receipt["candidate_manifest_access_authority"] is False
assert receipt["candidate_fit_access_authority"] is False
assert receipt["candidate_implementation_authority"] is False
assert receipt["biocortex_experiment_execution_authority"] is False
assert receipt["retrieval_order_mutation_authority"] is False
assert receipt["live_store_write_authority"] is False
assert receipt["runtime_promotion_authority"] is False
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
    "packet_id": "synthetic_role_review_for_freeze_v1",
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
    "decision_id": "synthetic_owner_assembly_approval_for_freeze_v1",
    "evidence_class": "synthetic_contract_test",
    "role_packet_sha256": role_sha256,
    "review_packet_sha256": role_review_packet_sha256,
    "owner_commitment_sha256": digest("holder:curator"),
    "decided_at_unix": 1784370300,
    "decision": "approve_private_corpus_assembly",
    "owner_authorization_receipt_sha256": digest("owner:assembly-authorization"),
    "authorization_scope": role_review_contract["approved_assembly_scope"],
    "attestations": {
        "application_owner_authored_decision": True,
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
    "packet_id": "synthetic_corpus_freeze_review_v1",
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
  "$role_review_packet" "$owner_decision" "$freeze_review" <<'PY'
import json
import sys
from pathlib import Path

chain = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
freeze = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
role = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
role_review = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
owner = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
freeze_review = json.loads(Path(sys.argv[6]).read_text(encoding="utf-8"))

assert chain["input_chain_verdict"] == "SYNTHETIC_FREEZE_CHAIN_VALID"
assert chain["ready_for_private_corpus_freeze_review"] is False
assert chain["episode_group_count"] == 30
assert chain["partition_counts"] == {"development": 8, "fit": 12, "sealed": 10}
assert chain["signature_counts"] == {
    "generalization_gap": 3,
    "no_relevant_gap": 9,
    "ordinary_retrieval_gap": 3,
    "overgeneralization_gap": 15,
}
assert chain["g1_corpus_freeze_authority"] is False
assert chain["candidate_implementation_authority"] is False
assert chain["runtime_promotion_authority"] is False

assert freeze["freeze_review_verdict"] == "SYNTHETIC_FREEZE_APPROVAL_VALID_NO_AUTHORITY"
assert freeze["structurally_freezable"] is True
assert freeze["freeze_reviewer_approve_count"] == 2
assert freeze["freeze_reviewer_reject_count"] == 0
assert freeze["ready_for_candidate_protocol_preregistration"] is False
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
        owner["owner_authorization_receipt_sha256"],
        freeze_review["custodian_attestation"]["custodian_commitment_sha256"],
        freeze_review["custodian_attestation"]["custody_receipt_sha256"],
    }
)
for review in freeze_review["reviewer_reviews"]:
    private_commitments.add(review["reviewer_commitment_sha256"])
    private_commitments.add(review["freeze_review_receipt_sha256"])


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
PY

python3 - "$contract" "$role_packet" "$role_review_packet" "$owner_decision" \
  "$manifest" "$freeze_review" "$scratch" <<'PY'
import copy
import hashlib
import json
import sys
from pathlib import Path

contract = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
role = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
role_review = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
owner = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
manifest = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
freeze = json.loads(Path(sys.argv[6]).read_text(encoding="utf-8"))
scratch = Path(sys.argv[7])


def digest(label):
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def write(name, value):
    path = scratch / f"{name}.json"
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


relaxed = copy.deepcopy(contract)
relaxed["approved_freeze_scope"]["permits_group_substitution"] = True
write("contract-relaxed", relaxed)

owner_reject = copy.deepcopy(owner)
owner_reject["decision"] = "reject_role_roster"
write("owner-reject", owner_reject)

manifest_before_owner = copy.deepcopy(manifest)
manifest_before_owner["assembled_at_unix"] = owner["decided_at_unix"]
write("manifest-before-owner", manifest_before_owner)

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
  echo "G1.3 accepted manifest assembly before owner approval" >&2
  exit 1
fi

for mutation in \
  freeze-role_packet_sha256-drift freeze-role_review_packet_sha256-drift \
  freeze-owner_decision_packet_sha256-drift freeze-manifest_sha256-drift \
  freeze-review-chronology freeze-candidate-reviewer \
  freeze-duplicate-reviewer freeze-outsider-reviewer \
  freeze-approval-missing-check freeze-zero-review-receipt \
  freeze-duplicate-review-receipt freeze-wrong-custodian \
  freeze-custody-receipt-reuse freeze-custody-broken \
  freeze-candidate-authored freeze-raw-identity; do
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
assert receipt["structurally_freezable"] is False
assert receipt["freeze_reviewer_approve_count"] == 1
assert receipt["freeze_reviewer_reject_count"] == 1
assert receipt["g1_corpus_freeze_authority"] is False
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
