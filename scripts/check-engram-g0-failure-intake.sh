#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

checker="scripts/eval/engram_g0_failure_intake.py"
contract="scripts/eval/fixtures/engram_g0_failure_intake_contract_v0.json"
synthetic="scripts/eval/fixtures/engram_g0_failure_intake_synthetic_v0.json"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT

python3 -m py_compile "$checker"
python3 "$checker" validate-contract --contract "$contract" >"$scratch/contract.1.json"
python3 "$checker" validate-contract --contract "$contract" >"$scratch/contract.2.json"
cmp "$scratch/contract.1.json" "$scratch/contract.2.json"

python3 - "$checker" "$contract" <<'PY'
import sys
import tempfile
from pathlib import Path

checker_path = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(checker_path.parent))
import engram_g0_failure_intake as gate

contract_value, _ = gate.read_json(Path(sys.argv[2]))
contract = gate.validate_contract(contract_value)
with tempfile.TemporaryDirectory() as temporary:
    frozen = Path(temporary) / "python.frozen"
    expected = gate.sha256_file(Path(sys.executable))
    observed = gate.freeze_baseline_binary(Path(sys.executable), frozen, expected)
    assert observed == expected
    assert frozen.is_file()

too_many_targets = [f"target_{index}" for index in range(33)]
private_spec = {
    "schema": gate.PRIVATE_SPEC_SCHEMA,
    "contract_id": contract["contract_id"],
    "packet_id": "synthetic_target_bound_test",
    "evidence_class": "synthetic_contract_test",
    "application": {
        "application_owner_id": "synthetic_owner",
        "affected_workflow_id": "synthetic_workflow",
        "failure_id": "synthetic_failure",
        "current_baseline_version": "synthetic_baseline",
    },
    "provenance": {
        "consumer_owned": False,
        "observed_before_candidate_selection": False,
        "candidate_authored_probes": True,
        "rights_cleared": False,
        "source_identity_sha256": "0" * 64,
        "consumer_review_receipt_sha256": "0" * 64,
    },
    "baseline": {
        "source_commit": "a" * 40,
        "binary_sha256": "b" * 64,
        "retrieval_modes": contract["modes"],
        "top_k": contract["top_k"],
        "environment_sha256": "c" * 64,
        "embedding_transport": "local",
    },
    "episode_groups": [{
        "episode_group_id": "synthetic_group",
        "episode_identity_sha256": "d" * 64,
        "partition": "fit_only",
        "probes": [
            {
                "probe_class": probe_class,
                "query": f"synthetic query {probe_class}",
                "expected_target_keys": too_many_targets,
            }
            for probe_class in gate.PROBE_CLASSES
        ],
    }],
}
try:
    gate.validate_private_spec(private_spec, contract)
except gate.InputError:
    pass
else:
    raise AssertionError("oversized private target set was not rejected")
PY

AGENT_BRIDGE_SEED_BOOST_DISABLE=1 \
AGENT_BRIDGE_EMBED_REMOTE_URL=http://127.0.0.1:7878/embed \
  python3 "$checker" fingerprint-environment --contract "$contract" \
  >"$scratch/environment.1.json"
AGENT_BRIDGE_SEED_BOOST_DISABLE=1 \
AGENT_BRIDGE_EMBED_REMOTE_URL=http://127.0.0.1:7878/embed \
  python3 "$checker" fingerprint-environment --contract "$contract" \
  >"$scratch/environment.2.json"
cmp "$scratch/environment.1.json" "$scratch/environment.2.json"
python3 - "$scratch/environment.1.json" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text())
assert result["embedding_transport"] == "loopback_delegated"
assert result["perception_filter_state_status"] == "disabled"
assert result["raw_environment_values_emitted"] is False
assert result["candidate_implementation_authority"] is False
PY

if AGENT_BRIDGE_SEED_BOOST_DISABLE=1 \
  AGENT_BRIDGE_EMBED_REMOTE_URL=https://example.com/embed \
  python3 "$checker" fingerprint-environment --contract "$contract" \
  >/dev/null 2>&1; then
  echo "external embedding delegation was not rejected" >&2
  exit 1
fi

python3 "$checker" evaluate --contract "$contract" --packet "$synthetic" >"$scratch/result.1.json"
python3 "$checker" evaluate --contract "$contract" --packet "$synthetic" >"$scratch/result.2.json"
cmp "$scratch/result.1.json" "$scratch/result.2.json"

python3 - "$scratch/result.1.json" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text())
assert result["g0_verdict"] == "SYNTHETIC_ONLY_NO_ADMISSION"
assert result["ready_for_g1_grouped_corpus_design"] is False
assert result["candidate_implementation_authority"] is False
assert result["g1_corpus_freeze_authority"] is False
assert result["retrieval_order_mutation_authority"] is False
assert result["runtime_promotion_authority"] is False
assert result["raw_content_in_receipt"] is False
assert result["signature_counts"] == {
    "generalization_gap": 1,
    "no_relevant_gap": 1,
    "ordinary_retrieval_gap": 1,
    "overgeneralization_gap": 1,
}
PY

if python3 "$checker" evaluate --contract "$contract" --packet "$synthetic" \
  --require-g1-ready >"$scratch/should-not-pass.json"; then
  echo "synthetic packet incorrectly passed --require-g1-ready" >&2
  exit 1
fi

python3 - "$synthetic" "$scratch/blocked-real.json" "$scratch/raw-field.json" \
  "$scratch/missing-probe.json" "$scratch/oversized-real.json" \
  "$scratch/mismatched-target-set.json" "$scratch/oversized-synthetic.json" \
  "$scratch/ambiguous.json" <<'PY'
import copy
import json
import sys
from pathlib import Path

source = json.loads(Path(sys.argv[1]).read_text())

blocked = copy.deepcopy(source)
blocked["evidence_class"] = "consumer_owned_real"
blocked["episode_groups"] = blocked["episode_groups"][:3]
blocked["replay"]["baseline_observation_count"] = 27
Path(sys.argv[2]).write_text(json.dumps(blocked), encoding="utf-8")

raw = copy.deepcopy(source)
raw["episode_groups"][0]["probes"][0]["query"] = "forbidden raw query"
Path(sys.argv[3]).write_text(json.dumps(raw), encoding="utf-8")

missing = copy.deepcopy(source)
missing["episode_groups"][0]["probes"].pop()
Path(sys.argv[4]).write_text(json.dumps(missing), encoding="utf-8")

oversized = copy.deepcopy(source)
oversized["evidence_class"] = "consumer_owned_real"
Path(sys.argv[5]).write_text(json.dumps(oversized), encoding="utf-8")

mismatched = copy.deepcopy(source)
mismatched["episode_groups"][0]["probes"][2]["expected_target_set_sha256"] = "f" * 64
Path(sys.argv[6]).write_text(json.dumps(mismatched), encoding="utf-8")

oversized_synthetic = copy.deepcopy(source)
extra_group = copy.deepcopy(source["episode_groups"][0])
extra_group["episode_group_id"] = "synthetic_fifth_group"
extra_group["episode_identity_sha256"] = "c" * 64
oversized_synthetic["episode_groups"].append(extra_group)
oversized_synthetic["replay"]["baseline_observation_count"] = 45
Path(sys.argv[7]).write_text(json.dumps(oversized_synthetic), encoding="utf-8")

ambiguous = copy.deepcopy(source)
ambiguous["episode_groups"][0]["probes"][2]["ranks"]["hybrid"] = 1
Path(sys.argv[8]).write_text(json.dumps(ambiguous), encoding="utf-8")
PY

python3 "$checker" evaluate --contract "$contract" \
  --packet "$scratch/blocked-real.json" >"$scratch/blocked-result.json"
python3 - "$scratch/blocked-result.json" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text())
assert result["g0_verdict"] == "BLOCKED_PROVENANCE"
assert result["ready_for_g1_grouped_corpus_design"] is False
assert result["blockers"] == [
    "candidate_authored_probes",
    "consumer_owned_false",
    "consumer_review_receipt_placeholder",
    "not_observed_before_candidate_selection",
    "rights_not_cleared",
    "source_identity_placeholder",
]
PY

if python3 "$checker" evaluate --contract "$contract" \
  --packet "$scratch/raw-field.json" >/dev/null 2>&1; then
  echo "raw-content mutation was not rejected" >&2
  exit 1
fi

if python3 "$checker" evaluate --contract "$contract" \
  --packet "$scratch/missing-probe.json" >/dev/null 2>&1; then
  echo "missing-probe mutation was not rejected" >&2
  exit 1
fi

if python3 "$checker" evaluate --contract "$contract" \
  --packet "$scratch/oversized-real.json" >/dev/null 2>&1; then
  echo "oversized real G0 packet was not rejected" >&2
  exit 1
fi

if python3 "$checker" evaluate --contract "$contract" \
  --packet "$scratch/mismatched-target-set.json" >/dev/null 2>&1; then
  echo "mismatched expected target set was not rejected" >&2
  exit 1
fi

if python3 "$checker" evaluate --contract "$contract" \
  --packet "$scratch/oversized-synthetic.json" >/dev/null 2>&1; then
  echo "oversized synthetic G0 packet was not rejected" >&2
  exit 1
fi

python3 "$checker" evaluate --contract "$contract" \
  --packet "$scratch/ambiguous.json" >"$scratch/ambiguous-result.json"
python3 - "$scratch/ambiguous-result.json" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text())
assert result["group_results"][0]["signature"] == "ambiguous_dual_failure"
assert result["ready_for_g1_grouped_corpus_design"] is False
PY

printf '{"schema":"%s","schema":"duplicate"}\n' \
  "agent_bridge.engram_g0_failure_replay_packet.v0" >"$scratch/duplicate.json"
if python3 "$checker" evaluate --contract "$contract" \
  --packet "$scratch/duplicate.json" >/dev/null 2>&1; then
  echo "duplicate JSON field was not rejected" >&2
  exit 1
fi

echo "engram G0 failure intake: PASS"
