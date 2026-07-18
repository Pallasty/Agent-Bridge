#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

validator="scripts/eval/engram_g1_corpus_design.py"
design="scripts/eval/fixtures/engram_g1_grouped_corpus_design_v0.json"
g0_contract="scripts/eval/fixtures/engram_g0_failure_intake_contract_v0.json"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT

python3 -m py_compile "$validator"
bash -n "$0"

python3 "$validator" --design "$design" --require-assembly-review-ready \
  >"$scratch/receipt.1.json"
python3 "$validator" --design "$design" --require-assembly-review-ready \
  >"$scratch/receipt.2.json"
cmp "$scratch/receipt.1.json" "$scratch/receipt.2.json"

python3 - "$scratch/receipt.1.json" "$design" "$g0_contract" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
design = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
g0_contract_sha256 = hashlib.sha256(Path(sys.argv[3]).read_bytes()).hexdigest()
assert design["g0_receipt_binding"]["contract_sha256"] == g0_contract_sha256
assert receipt["design_verdict"] == "READY_FOR_CONSUMER_CORPUS_ASSEMBLY_REVIEW"
assert receipt["ready_for_consumer_corpus_assembly_review"] is True
assert receipt["g0_verdict"] == "PASS_OBSERVED_RELEVANT_FAILURE"
assert receipt["admitted_signature"] == "overgeneralization_gap"
assert receipt["primary_metric"] == "unrelated_target_intrusion_rate_at_10"
assert receipt["decision_partition"] == "sealed"
assert receipt["unit_of_analysis"] == "episode_group"
assert receipt["episode_group_target"] == 30
assert receipt["episode_group_hard_cap"] == 36
assert receipt["preregistered_signature_minimum_count"] == 27
assert receipt["unallocated_target_slots"] == 3
assert receipt["partition_counts"] == {"development": 8, "fit": 12, "sealed": 10}
assert receipt["maximum_observations_per_replay"] == 324
assert receipt["maximum_baseline_observations"] == 648
assert receipt["raw_content_in_receipt"] is False
assert receipt["g1_corpus_freeze_authority"] is False
assert receipt["candidate_implementation_authority"] is False
assert receipt["retrieval_order_mutation_authority"] is False
assert receipt["biocortex_experiment_execution_authority"] is False
assert receipt["runtime_promotion_authority"] is False
PY

python3 - "$design" "$scratch" <<'PY'
import copy
import json
import sys
from pathlib import Path

source = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
scratch = Path(sys.argv[2])

mutations = {}

candidate = copy.deepcopy(source)
candidate["boundaries"]["candidate_implementation_authority"] = True
mutations["candidate-authority"] = candidate

split_probes = copy.deepcopy(source)
split_probes["corpus"]["keep_group_probes_together"] = False
mutations["split-probes"] = split_probes

split_count = copy.deepcopy(source)
split_count["corpus"]["partitions"]["fit"]["episode_groups"] = 11
mutations["split-count"] = split_count

g0_verdict = copy.deepcopy(source)
g0_verdict["g0_receipt_binding"]["g0_verdict"] = "NO_RELEVANT_FAILURE"
mutations["g0-verdict"] = g0_verdict

raw_query = copy.deepcopy(source)
raw_query["query"] = "forbidden raw probe"
mutations["raw-query"] = raw_query

relaxed_primary = copy.deepcopy(source)
relaxed_primary["metrics"]["primary"]["minimum_absolute_reduction"] = 0.19
mutations["relaxed-primary"] = relaxed_primary

unsealed_decision = copy.deepcopy(source)
unsealed_decision["metrics"]["decision_partition"] = "development"
mutations["unsealed-decision"] = unsealed_decision

sealed_retry = copy.deepcopy(source)
sealed_retry["sealed_evaluation"]["maximum_attempts"] = 2
mutations["sealed-retry"] = sealed_retry

for name, value in mutations.items():
    (scratch / f"{name}.json").write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
PY

for mutation in \
  candidate-authority split-probes split-count g0-verdict raw-query \
  relaxed-primary unsealed-decision sealed-retry; do
  if python3 "$validator" --design "$scratch/$mutation.json" >/dev/null 2>&1; then
    echo "engram G1 mutation was not rejected: $mutation" >&2
    exit 1
  fi
done

printf '{"schema":"%s","schema":"duplicate"}\n' \
  "agent_bridge.engram_g1_grouped_corpus_design.v0" >"$scratch/duplicate.json"
if python3 "$validator" --design "$scratch/duplicate.json" >/dev/null 2>&1; then
  echo "duplicate JSON field was not rejected" >&2
  exit 1
fi

git diff --check
git diff --cached --check
echo "engram G1 grouped-corpus design: PASS"
