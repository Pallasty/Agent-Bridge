#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

validator="scripts/eval/engram_g1_role_review.py"
contract="scripts/eval/fixtures/engram_g1_role_review_contract_v1.json"
preflight_contract="scripts/eval/fixtures/engram_g1_freeze_preflight_contract_v1.json"
preflight_validator="scripts/eval/engram_g1_freeze_preflight.py"
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
  "$preflight_validator" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
contract = Path(sys.argv[2])
preflight_contract = Path(sys.argv[3])
preflight_validator = Path(sys.argv[4])

assert hashlib.sha256(contract.read_bytes()).hexdigest() == receipt["contract_sha256"]
assert hashlib.sha256(preflight_contract.read_bytes()).hexdigest() == receipt["predecessor_contract_sha256"]
assert hashlib.sha256(preflight_validator.read_bytes()).hexdigest() == receipt["predecessor_validator_sha256"]
assert receipt["contract_verdict"] == "READY_FOR_PRIVATE_ROLE_REVIEW_PACKET"
assert receipt["ready_for_private_role_review_packet"] is True
assert receipt["application_owner_may_equal_consumer_curator"] is True
assert receipt["independence_auditor_must_be_outside_all_role_holders"] is True
assert receipt["maximum_intake_episode_groups"] == 36
assert receipt["current_private_corpus_assembly_authority"] is False
assert receipt["g1_corpus_freeze_authority"] is False
assert receipt["candidate_implementation_authority"] is False
assert receipt["biocortex_experiment_execution_authority"] is False
assert receipt["retrieval_order_mutation_authority"] is False
assert receipt["live_store_write_authority"] is False
assert receipt["runtime_promotion_authority"] is False
PY

python3 - "$contract" "$preflight_contract" "$scratch" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

contract_path = Path(sys.argv[1])
preflight_contract_path = Path(sys.argv[2])
scratch = Path(sys.argv[3])
contract = json.loads(contract_path.read_text(encoding="utf-8"))
contract_sha256 = hashlib.sha256(contract_path.read_bytes()).hexdigest()
preflight_sha256 = hashlib.sha256(preflight_contract_path.read_bytes()).hexdigest()


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
for role, independence_class, suffix in [
    ("candidate_implementer", "candidate_team", "candidate"),
    ("consumer_curator", "consumer", "curator"),
    ("freeze_reviewer", "independent_reviewer", "freeze_reviewer_1"),
    ("freeze_reviewer", "independent_reviewer", "freeze_reviewer_2"),
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

role = {
    "schema": "agent_bridge.engram_g1_role_commitment_packet.v1",
    "contract_id": "engram_g1_freeze_preflight_20260718",
    "contract_sha256": preflight_sha256,
    "packet_id": "synthetic_role_commitment_for_review_v1",
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

review = {
    "schema": "agent_bridge.engram_g1_role_review_packet.v1",
    "contract_id": "engram_g1_role_review_20260718",
    "contract_sha256": contract_sha256,
    "packet_id": "synthetic_role_review_v1",
    "evidence_class": "synthetic_contract_test",
    "role_packet_sha256": role_sha256,
    "review_started_at_unix": 1784370100,
    "review_completed_at_unix": 1784370200,
    "application_owner_review": {
        "reviewer_role": "application_owner",
        "reviewer_commitment_sha256": digest("holder:curator"),
        "review_receipt_sha256": digest("review:application-owner"),
        "decision": "approve",
        "owner_is_consumer_curator": True,
        "appointment_evidence_complete": True,
        "consumer_ownership_confirmed": True,
        "workflow_authority_confirmed": True,
    },
    "independence_audit": {
        "reviewer_role": "independence_auditor",
        "auditor_commitment_sha256": digest("reviewer:independence-auditor"),
        "audit_receipt_sha256": digest("review:independence-auditor"),
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
review_path = write("synthetic-review.json", review)
review_sha256 = hashlib.sha256(review_path.read_bytes()).hexdigest()

decision = {
    "schema": "agent_bridge.engram_g1_role_owner_decision_packet.v1",
    "contract_id": "engram_g1_role_review_20260718",
    "contract_sha256": contract_sha256,
    "decision_id": "synthetic_owner_decision_v1",
    "evidence_class": "synthetic_contract_test",
    "role_packet_sha256": role_sha256,
    "review_packet_sha256": review_sha256,
    "owner_commitment_sha256": digest("holder:curator"),
    "decided_at_unix": 1784370300,
    "decision": "approve_private_corpus_assembly",
    "owner_authorization_receipt_sha256": digest("owner:authorization"),
    "authorization_scope": contract["approved_assembly_scope"],
    "attestations": {
        "application_owner_authored_decision": True,
        "candidate_did_not_author_decision": True,
        "candidate_did_not_see_raw_decision_evidence": True,
        "owner_commitment_uses_private_salt": True,
        "raw_identities_absent": True,
        "validator_does_not_authenticate_owner_identity": True,
    },
}
write("synthetic-owner-decision.json", decision)
PY

role_packet="$scratch/synthetic-role.json"
review_packet="$scratch/synthetic-review.json"
owner_decision="$scratch/synthetic-owner-decision.json"

python3 "$validator" validate-review --contract "$contract" \
  --preflight-contract "$preflight_contract" --role-packet "$role_packet" \
  --review-packet "$review_packet" >"$scratch/review.1.json"
python3 "$validator" validate-review --contract "$contract" \
  --preflight-contract "$preflight_contract" --role-packet "$role_packet" \
  --review-packet "$review_packet" >"$scratch/review.2.json"
cmp "$scratch/review.1.json" "$scratch/review.2.json"

python3 "$validator" validate-owner-decision --contract "$contract" \
  --preflight-contract "$preflight_contract" --role-packet "$role_packet" \
  --review-packet "$review_packet" --owner-decision "$owner_decision" \
  >"$scratch/decision.1.json"
python3 "$validator" validate-owner-decision --contract "$contract" \
  --preflight-contract "$preflight_contract" --role-packet "$role_packet" \
  --review-packet "$review_packet" --owner-decision "$owner_decision" \
  >"$scratch/decision.2.json"
cmp "$scratch/decision.1.json" "$scratch/decision.2.json"
(
  cd "$scratch"
  python3 "$repo_root/$validator" validate-owner-decision \
    --contract "$repo_root/$contract" \
    --preflight-contract "$repo_root/$preflight_contract" \
    --role-packet "$role_packet" --review-packet "$review_packet" \
    --owner-decision "$owner_decision"
) >"$scratch/decision.outside-cwd.json"
cmp "$scratch/decision.1.json" "$scratch/decision.outside-cwd.json"

python3 - "$scratch/review.1.json" "$scratch/decision.1.json" \
  "$role_packet" "$review_packet" "$owner_decision" <<'PY'
import json
import sys
from pathlib import Path

review = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
decision = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
role_packet = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
review_packet = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
owner_decision = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))

assert review["role_review_verdict"] == "SYNTHETIC_REVIEW_APPROVAL_VALID"
assert review["both_reviews_approved"] is True
assert review["owner_is_consumer_curator"] is True
assert review["ready_for_application_owner_decision"] is False
assert review["real_world_identity_authenticated_by_validator"] is False
assert review["holder_commitments_in_receipt"] is False
assert review["reviewer_commitments_in_receipt"] is False
assert review["appointment_or_review_receipts_in_receipt"] is False
assert review["private_corpus_assembly_authority"] is False
assert review["candidate_implementation_authority"] is False
assert review["runtime_promotion_authority"] is False

assert decision["owner_decision_verdict"] == "SYNTHETIC_APPROVAL_VALID_NO_AUTHORITY"
assert decision["structurally_approvable"] is True
assert decision["ready_for_private_corpus_assembly"] is False
assert decision["private_corpus_assembly_authority"] is False
assert decision["candidate_lane_may_execute"] is False
assert decision["g1_corpus_freeze_authority"] is False
assert decision["candidate_implementation_authority"] is False
assert decision["biocortex_experiment_execution_authority"] is False
assert decision["retrieval_order_mutation_authority"] is False
assert decision["live_store_write_authority"] is False
assert decision["runtime_promotion_authority"] is False
assert decision["holder_commitments_in_receipt"] is False
assert decision["reviewer_commitments_in_receipt"] is False
assert decision["appointment_review_or_authorization_receipts_in_receipt"] is False

private_commitments = {
    field
    for holder in role_packet["holders"]
    for field in (
        holder["holder_commitment_sha256"],
        holder["appointment_receipt_sha256"],
    )
}
private_commitments.update(
    {
        review_packet["application_owner_review"]["reviewer_commitment_sha256"],
        review_packet["application_owner_review"]["review_receipt_sha256"],
        review_packet["independence_audit"]["auditor_commitment_sha256"],
        review_packet["independence_audit"]["audit_receipt_sha256"],
        owner_decision["owner_commitment_sha256"],
        owner_decision["owner_authorization_receipt_sha256"],
    }
)


def string_leaves(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from string_leaves(child)
    elif isinstance(value, list):
        for child in value:
            yield from string_leaves(child)
    elif isinstance(value, str):
        yield value


assert private_commitments.isdisjoint(set(string_leaves(review)))
assert private_commitments.isdisjoint(set(string_leaves(decision)))
PY

python3 - "$contract" "$role_packet" "$review_packet" "$owner_decision" \
  "$scratch" <<'PY'
import copy
import hashlib
import json
import sys
from pathlib import Path

contract = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
role = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
review = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
decision = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
scratch = Path(sys.argv[5])


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
relaxed["approved_assembly_scope"]["maximum_intake_episode_groups"] = 37
write("contract-relaxed", relaxed)

review_mutations = {}
owner_candidate = copy.deepcopy(review)
owner_candidate["application_owner_review"]["reviewer_commitment_sha256"] = digest(
    "holder:candidate"
)
owner_candidate["application_owner_review"]["owner_is_consumer_curator"] = False
review_mutations["review-owner-candidate"] = owner_candidate

owner_curator_mismatch = copy.deepcopy(review)
owner_curator_mismatch["application_owner_review"][
    "reviewer_commitment_sha256"
] = digest("reviewer:outside-owner")
review_mutations["review-owner-curator-mismatch"] = owner_curator_mismatch

auditor_holder = copy.deepcopy(review)
auditor_holder["independence_audit"]["auditor_commitment_sha256"] = digest(
    "holder:candidate"
)
review_mutations["review-auditor-holder"] = auditor_holder

chronology = copy.deepcopy(review)
chronology["review_started_at_unix"] = role["created_at_unix"]
review_mutations["review-chronology"] = chronology

candidate_authored = copy.deepcopy(review)
candidate_authored["attestations"]["candidate_did_not_author_review"] = False
review_mutations["review-candidate-authored"] = candidate_authored

unsalted = copy.deepcopy(review)
unsalted["attestations"]["reviewer_commitments_use_private_salts"] = False
review_mutations["review-unsalted"] = unsalted

raw_identity = copy.deepcopy(review)
raw_identity["application_owner_review"]["name"] = "forbidden"
review_mutations["review-raw-identity"] = raw_identity

zero_receipt = copy.deepcopy(review)
zero_receipt["application_owner_review"]["review_receipt_sha256"] = "0" * 64
review_mutations["review-zero-receipt"] = zero_receipt

role_drift = copy.deepcopy(review)
role_drift["role_packet_sha256"] = "f" * 64
review_mutations["review-role-hash-drift"] = role_drift

for name, value in review_mutations.items():
    write(name, value)

one_reject = copy.deepcopy(review)
one_reject["independence_audit"]["decision"] = "reject"
one_reject_path = write("review-one-reject", one_reject)
one_reject_sha256 = hashlib.sha256(one_reject_path.read_bytes()).hexdigest()

decision_after_reject = copy.deepcopy(decision)
decision_after_reject["review_packet_sha256"] = one_reject_sha256
write("decision-approval-after-review-reject", decision_after_reject)

record_rejection = copy.deepcopy(decision_after_reject)
record_rejection["decision"] = "reject_role_roster"
record_rejection["decision_id"] = "synthetic_owner_rejection_v1"
write("decision-record-review-rejection", record_rejection)

decision_mutations = {}
before_review = copy.deepcopy(decision)
before_review["decided_at_unix"] = review["review_completed_at_unix"]
decision_mutations["decision-before-review"] = before_review

owner_mismatch = copy.deepcopy(decision)
owner_mismatch["owner_commitment_sha256"] = digest("reviewer:outside-owner")
decision_mutations["decision-owner-mismatch"] = owner_mismatch

zero_authorization = copy.deepcopy(decision)
zero_authorization["owner_authorization_receipt_sha256"] = "0" * 64
decision_mutations["decision-zero-authorization"] = zero_authorization

scope_mutation = copy.deepcopy(decision)
scope_mutation["authorization_scope"]["maximum_intake_episode_groups"] = 37
decision_mutations["decision-scope-mutation"] = scope_mutation

review_drift = copy.deepcopy(decision)
review_drift["review_packet_sha256"] = "f" * 64
decision_mutations["decision-review-hash-drift"] = review_drift

candidate_decision = copy.deepcopy(decision)
candidate_decision["attestations"]["candidate_did_not_author_decision"] = False
decision_mutations["decision-candidate-authored"] = candidate_decision

for name, value in decision_mutations.items():
    write(name, value)

real_role = copy.deepcopy(role)
real_role["evidence_class"] = "consumer_owned_real"
real_role_path = write("real-role-outside-data", real_role)
real_review = copy.deepcopy(review)
real_review["evidence_class"] = "consumer_owned_real"
real_review["role_packet_sha256"] = hashlib.sha256(real_role_path.read_bytes()).hexdigest()
write("real-review-outside-data", real_review)
PY

if python3 "$validator" validate-contract \
  --contract "$scratch/contract-relaxed.json" >/dev/null 2>&1; then
  echo "relaxed G1.2 contract was not rejected" >&2
  exit 1
fi

for mutation in \
  review-owner-candidate review-owner-curator-mismatch review-auditor-holder \
  review-chronology review-candidate-authored review-unsalted \
  review-raw-identity review-zero-receipt review-role-hash-drift; do
  if python3 "$validator" validate-review --contract "$contract" \
    --preflight-contract "$preflight_contract" --role-packet "$role_packet" \
    --review-packet "$scratch/$mutation.json" >/dev/null 2>&1; then
    echo "G1.2 role-review mutation was not rejected: $mutation" >&2
    exit 1
  fi
done

python3 "$validator" validate-review --contract "$contract" \
  --preflight-contract "$preflight_contract" --role-packet "$role_packet" \
  --review-packet "$scratch/review-one-reject.json" \
  >"$scratch/review-one-reject.receipt.json"
python3 - "$scratch/review-one-reject.receipt.json" <<'PY'
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert receipt["both_reviews_approved"] is False
assert receipt["ready_for_application_owner_decision"] is False
assert receipt["private_corpus_assembly_authority"] is False
PY

if python3 "$validator" validate-owner-decision --contract "$contract" \
  --preflight-contract "$preflight_contract" --role-packet "$role_packet" \
  --review-packet "$scratch/review-one-reject.json" \
  --owner-decision "$scratch/decision-approval-after-review-reject.json" \
  >/dev/null 2>&1; then
  echo "owner approval survived a rejected independent review" >&2
  exit 1
fi

python3 "$validator" validate-owner-decision --contract "$contract" \
  --preflight-contract "$preflight_contract" --role-packet "$role_packet" \
  --review-packet "$scratch/review-one-reject.json" \
  --owner-decision "$scratch/decision-record-review-rejection.json" \
  >"$scratch/decision-record-review-rejection.receipt.json"
python3 - "$scratch/decision-record-review-rejection.receipt.json" <<'PY'
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert receipt["owner_decision_verdict"] == "SYNTHETIC_REJECTION_VALID_NO_AUTHORITY"
assert receipt["private_corpus_assembly_authority"] is False
PY

for mutation in \
  decision-before-review decision-owner-mismatch decision-zero-authorization \
  decision-scope-mutation decision-review-hash-drift \
  decision-candidate-authored; do
  if python3 "$validator" validate-owner-decision --contract "$contract" \
    --preflight-contract "$preflight_contract" --role-packet "$role_packet" \
    --review-packet "$review_packet" \
    --owner-decision "$scratch/$mutation.json" >/dev/null 2>&1; then
    echo "G1.2 owner-decision mutation was not rejected: $mutation" >&2
    exit 1
  fi
done

if python3 "$validator" validate-review --contract "$contract" \
  --preflight-contract "$preflight_contract" \
  --role-packet "$scratch/real-role-outside-data.json" \
  --review-packet "$scratch/real-review-outside-data.json" \
  >/dev/null 2>&1; then
  echo "real G1.2 packets outside ignored data/ were not rejected" >&2
  exit 1
fi

printf '{"schema":"%s","schema":"duplicate"}\n' \
  "agent_bridge.engram_g1_role_review_contract.v1" \
  >"$scratch/duplicate.json"
if python3 "$validator" validate-contract --contract "$scratch/duplicate.json" \
  >/dev/null 2>&1; then
  echo "duplicate JSON field was not rejected" >&2
  exit 1
fi

git diff --check
git diff --cached --check
echo "engram G1 role review: PASS"
