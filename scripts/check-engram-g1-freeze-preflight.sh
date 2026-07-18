#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

validator="scripts/eval/engram_g1_freeze_preflight.py"
contract="scripts/eval/fixtures/engram_g1_freeze_preflight_contract_v1.json"
predecessor_design="scripts/eval/fixtures/engram_g1_grouped_corpus_design_v0.json"
predecessor_validator="scripts/eval/engram_g1_corpus_design.py"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT

python3 -m py_compile "$validator"
bash -n "$0"

python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/contract.1.json"
python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/contract.2.json"
cmp "$scratch/contract.1.json" "$scratch/contract.2.json"

python3 - "$scratch/contract.1.json" "$contract" "$predecessor_design" \
  "$predecessor_validator" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
contract = Path(sys.argv[2])
predecessor_design = Path(sys.argv[3])
predecessor_validator = Path(sys.argv[4])

assert hashlib.sha256(contract.read_bytes()).hexdigest() == receipt["contract_sha256"]
assert hashlib.sha256(predecessor_design.read_bytes()).hexdigest() == receipt["predecessor_design_sha256"]
assert hashlib.sha256(predecessor_validator.read_bytes()).hexdigest() == "2a408d64b34605f434377b3c11f71807f6c81068aa7bcba069c8d3a6dc44cb91"
assert receipt["contract_verdict"] == "READY_FOR_INDEPENDENT_ROLE_ASSIGNMENT"
assert receipt["ready_for_independent_role_assignment"] is True
assert receipt["decision_class"] == "deterministic_engineering_screen"
assert receipt["candidate_arm"] == "clustered_reorganization"
assert receipt["comparator_arms"] == ["stable_control", "density_only"]
assert receipt["minimum_paired_primary_repairs_vs_each_comparator"] == 2
assert receipt["maximum_new_exact_misses"] == 0
assert receipt["maximum_new_related_misses"] == 0
assert receipt["maximum_frozen_groups_per_application_family"] == 10
assert receipt["population_effect_claim_authority"] is False
assert receipt["g1_corpus_freeze_authority"] is False
assert receipt["candidate_implementation_authority"] is False
assert receipt["biocortex_experiment_execution_authority"] is False
assert receipt["runtime_promotion_authority"] is False
PY

python3 - "$contract" "$scratch" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

contract_path = Path(sys.argv[1])
scratch = Path(sys.argv[2])
contract_sha256 = hashlib.sha256(contract_path.read_bytes()).hexdigest()


def digest(label):
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


holders = []
for role, independence_class, suffix in [
    ("candidate_implementer", "candidate_team", "candidate"),
    ("consumer_curator", "consumer", "curator"),
    ("freeze_reviewer", "independent_reviewer", "reviewer_1"),
    ("freeze_reviewer", "independent_reviewer", "reviewer_2"),
    ("sealed_evaluator_custodian", "independent_custodian", "custodian"),
]:
    holders.append(
        {
            "role": role,
            "independence_class": independence_class,
            "holder_commitment_sha256": digest(f"holder:{suffix}"),
            "appointment_receipt_sha256": digest(f"appointment:{suffix}"),
        }
    )

role_packet = {
    "schema": "agent_bridge.engram_g1_role_commitment_packet.v1",
    "contract_id": "engram_g1_freeze_preflight_20260718",
    "contract_sha256": contract_sha256,
    "packet_id": "synthetic_role_commitment_v1",
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
role_path = scratch / "synthetic-role.json"
role_path.write_text(
    json.dumps(role_packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    encoding="utf-8",
)
role_sha256 = hashlib.sha256(role_path.read_bytes()).hexdigest()


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
    "contract_sha256": contract_sha256,
    "manifest_id": "synthetic_grouped_corpus_v1",
    "evidence_class": "synthetic_contract_test",
    "assembled_at_unix": 1784370100,
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
(scratch / "synthetic-manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    encoding="utf-8",
)
PY

role_packet="$scratch/synthetic-role.json"
manifest="$scratch/synthetic-manifest.json"

python3 "$validator" validate-role --contract "$contract" \
  --role-packet "$role_packet" >"$scratch/role.1.json"
python3 "$validator" validate-role --contract "$contract" \
  --role-packet "$role_packet" >"$scratch/role.2.json"
cmp "$scratch/role.1.json" "$scratch/role.2.json"
(
  cd "$scratch"
  python3 "$repo_root/$validator" validate-role \
    --contract "$repo_root/$contract" --role-packet "$role_packet"
) >"$scratch/role.outside-cwd.json"
cmp "$scratch/role.1.json" "$scratch/role.outside-cwd.json"

python3 "$validator" validate-manifest --contract "$contract" \
  --role-packet "$role_packet" --manifest "$manifest" \
  >"$scratch/manifest.1.json"
python3 "$validator" validate-manifest --contract "$contract" \
  --role-packet "$role_packet" --manifest "$manifest" \
  >"$scratch/manifest.2.json"
cmp "$scratch/manifest.1.json" "$scratch/manifest.2.json"
(
  cd "$scratch"
  python3 "$repo_root/$validator" validate-manifest \
    --contract "$repo_root/$contract" --role-packet "$role_packet" \
    --manifest "$manifest"
) >"$scratch/manifest.outside-cwd.json"
cmp "$scratch/manifest.1.json" "$scratch/manifest.outside-cwd.json"

python3 - "$scratch/role.1.json" "$scratch/manifest.1.json" <<'PY'
import json
import sys
from pathlib import Path

role = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
manifest = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

assert role["role_packet_verdict"] == "SYNTHETIC_ROLE_PACKET_VALID"
assert role["ready_for_independent_role_commitment_review"] is False
assert role["distinct_holder_commitment_count"] == 5
assert role["holder_commitments_in_receipt"] is False
assert role["real_world_identity_authenticated_by_validator"] is False
assert role["private_corpus_assembly_authority"] is False
assert role["g1_corpus_freeze_authority"] is False
assert role["candidate_implementation_authority"] is False
assert role["runtime_promotion_authority"] is False

assert manifest["manifest_verdict"] == "SYNTHETIC_MANIFEST_VALID"
assert manifest["ready_for_independent_corpus_freeze_review"] is False
assert manifest["episode_group_count"] == 30
assert manifest["partition_counts"] == {"development": 8, "fit": 12, "sealed": 10}
assert manifest["signature_counts"] == {
    "generalization_gap": 3,
    "no_relevant_gap": 9,
    "ordinary_retrieval_gap": 3,
    "overgeneralization_gap": 15,
}
assert manifest["application_family_count"] == 4
assert manifest["maximum_groups_in_one_application_family"] == 8
assert manifest["baseline_observation_count"] == 540
assert manifest["group_identifiers_in_receipt"] is False
assert manifest["partition_membership_in_receipt"] is False
assert manifest["holder_commitments_in_receipt"] is False
assert manifest["raw_content_in_receipt"] is False
assert manifest["g1_corpus_freeze_authority"] is False
assert manifest["candidate_implementation_authority"] is False
assert manifest["biocortex_experiment_execution_authority"] is False
assert manifest["retrieval_order_mutation_authority"] is False
assert manifest["live_store_write_authority"] is False
assert manifest["runtime_promotion_authority"] is False
PY

python3 - "$contract" "$role_packet" "$manifest" "$scratch" <<'PY'
import copy
import json
import sys
from pathlib import Path

contract = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
role = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
manifest = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
scratch = Path(sys.argv[4])

contract_mutation = copy.deepcopy(contract)
contract_mutation["experiment_decision"][
    "minimum_paired_primary_repairs_vs_each_comparator"
] = 1
(scratch / "contract-relaxed.json").write_text(
    json.dumps(contract_mutation, sort_keys=True), encoding="utf-8"
)

role_mutations = {}
duplicate_holder = copy.deepcopy(role)
duplicate_holder["holders"][1]["holder_commitment_sha256"] = duplicate_holder[
    "holders"
][0]["holder_commitment_sha256"]
role_mutations["role-duplicate-holder"] = duplicate_holder

wrong_class = copy.deepcopy(role)
wrong_class["holders"][1]["independence_class"] = "candidate_team"
role_mutations["role-wrong-class"] = wrong_class

candidate_access = copy.deepcopy(role)
candidate_access["attestations"]["candidate_denied_private_manifest"] = False
role_mutations["role-candidate-access"] = candidate_access

unsalted_holder = copy.deepcopy(role)
unsalted_holder["attestations"]["holder_commitments_use_private_salts"] = False
role_mutations["role-unsalted-holder"] = unsalted_holder

real_outside_data = copy.deepcopy(role)
real_outside_data["evidence_class"] = "consumer_owned_real"
role_mutations["role-real-outside-data"] = real_outside_data

for name, value in role_mutations.items():
    (scratch / f"{name}.json").write_text(
        json.dumps(value, sort_keys=True), encoding="utf-8"
    )

manifest_mutations = {}

missing_group = copy.deepcopy(manifest)
missing_group["episode_groups"].pop()
missing_group["replay_integrity"]["baseline_observation_count"] = 522
manifest_mutations["manifest-missing-group"] = missing_group

role_drift = copy.deepcopy(manifest)
role_drift["role_packet_sha256"] = "f" * 64
manifest_mutations["manifest-role-drift"] = role_drift

role_chronology = copy.deepcopy(manifest)
role_chronology["assembled_at_unix"] = role["created_at_unix"]
manifest_mutations["manifest-role-chronology"] = role_chronology

g0_sealed = copy.deepcopy(manifest)
g0_sealed["episode_groups"][0]["partition"] = "sealed"
manifest_mutations["manifest-g0-sealed"] = g0_sealed

replay_drift = copy.deepcopy(manifest)
replay_drift["episode_groups"][0]["probes"][0]["replay_ranks"][1]["fts"] = 2
manifest_mutations["manifest-replay-drift"] = replay_drift

family_cap = copy.deepcopy(manifest)
dominant_family = family_cap["episode_groups"][0]["application_family_id_sha256"]
for group in family_cap["episode_groups"][:11]:
    group["application_family_id_sha256"] = dominant_family
manifest_mutations["manifest-family-cap"] = family_cap

signature_drift = copy.deepcopy(manifest)
signature_drift["episode_groups"][0]["declared_signature"] = "no_relevant_gap"
manifest_mutations["manifest-signature-drift"] = signature_drift

candidate_authored = copy.deepcopy(manifest)
candidate_authored["episode_groups"][0]["provenance"]["candidate_authored_probes"] = True
manifest_mutations["manifest-candidate-authored"] = candidate_authored

raw_query = copy.deepcopy(manifest)
raw_query["episode_groups"][0]["probes"][0]["query"] = "forbidden raw material"
manifest_mutations["manifest-raw-query"] = raw_query

duplicate_query = copy.deepcopy(manifest)
duplicate_query["episode_groups"][1]["probes"][0]["query_sha256"] = duplicate_query[
    "episode_groups"
][0]["probes"][0]["query_sha256"]
manifest_mutations["manifest-duplicate-query"] = duplicate_query

sealed_primary = copy.deepcopy(manifest)
for group in sealed_primary["episode_groups"]:
    if group["partition"] == "sealed" and group["declared_signature"] == "overgeneralization_gap":
        group["declared_signature"] = "no_relevant_gap"
        for probe in group["probes"]:
            if probe["probe_class"] == "unrelated":
                probe["replay_ranks"] = [
                    {"fts": 0, "hybrid": 0, "semantic": 0},
                    {"fts": 0, "hybrid": 0, "semantic": 0},
                ]
        break
manifest_mutations["manifest-sealed-primary-minimum"] = sealed_primary

assembly_drift = copy.deepcopy(manifest)
assembly_drift["assembly_attestations"]["candidate_has_not_seen_sealed_material"] = False
manifest_mutations["manifest-assembly-drift"] = assembly_drift

unsalted_manifest = copy.deepcopy(manifest)
unsalted_manifest["assembly_attestations"][
    "commitment_salts_held_by_sealed_custodian"
] = False
manifest_mutations["manifest-unsalted-commitments"] = unsalted_manifest

for name, value in manifest_mutations.items():
    (scratch / f"{name}.json").write_text(
        json.dumps(value, sort_keys=True), encoding="utf-8"
    )
PY

if python3 "$validator" validate-contract \
  --contract "$scratch/contract-relaxed.json" >/dev/null 2>&1; then
  echo "relaxed G1.1 contract was not rejected" >&2
  exit 1
fi

for mutation in \
  role-duplicate-holder role-wrong-class role-candidate-access \
  role-unsalted-holder role-real-outside-data; do
  if python3 "$validator" validate-role --contract "$contract" \
    --role-packet "$scratch/$mutation.json" >/dev/null 2>&1; then
    echo "G1.1 role mutation was not rejected: $mutation" >&2
    exit 1
  fi
done

for mutation in \
  manifest-missing-group manifest-role-drift manifest-role-chronology \
  manifest-g0-sealed \
  manifest-replay-drift manifest-family-cap manifest-signature-drift \
  manifest-candidate-authored manifest-raw-query manifest-duplicate-query \
  manifest-sealed-primary-minimum manifest-assembly-drift \
  manifest-unsalted-commitments; do
  if python3 "$validator" validate-manifest --contract "$contract" \
    --role-packet "$role_packet" --manifest "$scratch/$mutation.json" \
    >/dev/null 2>&1; then
    echo "G1.1 manifest mutation was not rejected: $mutation" >&2
    exit 1
  fi
done

printf '{"schema":"%s","schema":"duplicate"}\n' \
  "agent_bridge.engram_g1_freeze_preflight_contract.v1" \
  >"$scratch/duplicate.json"
if python3 "$validator" validate-contract --contract "$scratch/duplicate.json" \
  >/dev/null 2>&1; then
  echo "duplicate JSON field was not rejected" >&2
  exit 1
fi

git diff --check
git diff --cached --check
echo "engram G1 freeze preflight: PASS"
