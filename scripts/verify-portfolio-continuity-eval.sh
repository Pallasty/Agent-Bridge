#!/usr/bin/env bash
# Verify the no-write portfolio continuity evaluation contract.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCORER="$ROOT_DIR/scripts/eval/portfolio_continuity_eval.py"
FIXTURE="$ROOT_DIR/scripts/eval/fixtures/portfolio_continuity_contract.json"
PASS_CANDIDATE="$ROOT_DIR/scripts/eval/fixtures/portfolio_continuity_candidate_pass.json"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-10-portfolio-continuity-eval-contract.md"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-portfolio-continuity-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

PYTHONPYCACHEPREFIX="$tmpdir/pycache" python3 -m py_compile "$SCORER"

python3 "$SCORER" \
  --fixture "$FIXTURE" \
  --candidate "$PASS_CANDIDATE" \
  --strict \
  --output "$tmpdir/pass.json"

python3 - "$PASS_CANDIDATE" "$FIXTURE" "$tmpdir" <<'PY'
import copy
import json
import sys
from pathlib import Path

source = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
fixture = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
out = Path(sys.argv[3])

def write(name, mutate):
    candidate = copy.deepcopy(source)
    candidate["candidate_id"] = name
    mutate(candidate)
    (out / f"{name}.json").write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

def find_claim(candidate, case_index, claim_id):
    return next(
        claim
        for claim in candidate["cases"][case_index]["claims"]
        if claim["claim_id"] == claim_id
    )

write(
    "stale",
    lambda c: c["cases"][0]["claims"][0].update(
        {"evidence_keys": ["syn_goal_v1"]}
    ),
)
write(
    "missing",
    lambda c: c["cases"][0].update(
        {"claims": [x for x in c["cases"][0]["claims"] if x["claim_id"] != "next_action"]}
    ),
)
write(
    "unsupported",
    lambda c: c["cases"][0]["claims"].append(
        {"claim_id": "invented_detail", "confidence": "supported", "evidence_keys": []}
    ),
)
write(
    "forbidden",
    lambda c: c["cases"][0]["claims"].append(
        {"claim_id": "release_complete", "confidence": "supported", "evidence_keys": []}
    ),
)
write(
    "bad_abstention",
    lambda c: c["cases"][2].update(
        {
            "abstained": False,
            "claims": [
                {
                    "claim_id": "invented_status",
                    "confidence": "supported",
                    "evidence_keys": ["syn_partial_signal"],
                }
            ],
        }
    ),
)
write(
    "unknown_evidence",
    lambda c: c["cases"][0]["claims"][0].update(
        {"evidence_keys": ["syn_unknown_key"]}
    ),
)
write(
    "wrong_precision",
    lambda c: find_claim(c, 0, "current_risk").update(
        {"confidence": "uncertain", "evidence_keys": ["syn_next_action"]}
    ),
)
write(
    "missing_case",
    lambda c: c.update(
        {"cases": [case for case in c["cases"] if case["case_id"] != "insufficient_evidence"]}
    ),
)
write(
    "uncertain_required",
    lambda c: find_claim(c, 0, "current_goal").update(
        {"confidence": "uncertain"}
    ),
)
write(
    "raw_content",
    lambda c: c["cases"][0]["claims"][0].update(
        {"text": "raw answer content must be rejected"}
    ),
)
write(
    "abstention_smuggle",
    lambda c: c["cases"][2]["claims"][0].update(
        {"evidence_keys": ["syn_partial_signal"]}
    ),
)
write(
    "unknown_field",
    lambda c: c.update({"summary": "free-form candidate fields are forbidden"}),
)
write(
    "invalid_label",
    lambda c: c.update({"candidate_id": "free form candidate id"}),
)
write(
    "invalid_evidence_label",
    lambda c: c["cases"][0]["claims"][0].update(
        {"evidence_keys": ["free form evidence key"]}
    ),
)
write(
    "huge_latency",
    lambda c: c["cases"][0].update({"latency_ms": 10**1000}),
)

nan_latency = copy.deepcopy(source)
nan_latency["candidate_id"] = "nan_latency"
nan_latency["cases"][0]["latency_ms"] = float("nan")
(out / "nan_latency.json").write_text(
    json.dumps(nan_latency, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

source_text = json.dumps(source, ensure_ascii=False, indent=2) + "\n"
schema_line = '  "schema": "agent_bridge.portfolio_continuity_candidate.v0",'
(out / "duplicate_field.json").write_text(
    source_text.replace(schema_line, f"{schema_line}\n{schema_line}", 1),
    encoding="utf-8",
)

impossible = copy.deepcopy(fixture)
impossible["cases"][0]["evidence_catalog"][1]["status"] = "archived"
(out / "impossible_fixture.json").write_text(
    json.dumps(impossible, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

vacuous = copy.deepcopy(fixture)
vacuous["cases"][0]["required_claims"] = []
(out / "vacuous_fixture.json").write_text(
    json.dumps(vacuous, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

quality_failures=(
  stale missing unsupported forbidden bad_abstention unknown_evidence
  wrong_precision missing_case uncertain_required
)
for name in "${quality_failures[@]}"; do
  if python3 "$SCORER" \
    --fixture "$FIXTURE" \
    --candidate "$tmpdir/$name.json" \
    --strict \
    --output "$tmpdir/$name.out.json"; then
    echo "expected $name candidate to fail strict evaluation" >&2
    exit 1
  fi
done

input_failures=(
  raw_content abstention_smuggle unknown_field invalid_label
  invalid_evidence_label nan_latency duplicate_field huge_latency
)
for name in "${input_failures[@]}"; do
  if python3 "$SCORER" \
    --fixture "$FIXTURE" \
    --candidate "$tmpdir/$name.json" \
    --output "$tmpdir/$name.out.json" \
    2>"$tmpdir/$name.err"; then
    echo "expected $name candidate to fail input validation" >&2
    exit 1
  fi
done

if python3 "$SCORER" \
  --fixture "$tmpdir/impossible_fixture.json" \
  --candidate "$PASS_CANDIDATE" \
  --output "$tmpdir/impossible-fixture.out.json" \
  2>"$tmpdir/impossible-fixture.err"; then
  echo "expected impossible fixture to fail input validation" >&2
  exit 1
fi

if python3 "$SCORER" \
  --fixture "$tmpdir/vacuous_fixture.json" \
  --candidate "$PASS_CANDIDATE" \
  --output "$tmpdir/vacuous-fixture.out.json" \
  2>"$tmpdir/vacuous-fixture.err"; then
  echo "expected vacuous fixture to fail input validation" >&2
  exit 1
fi

python3 - "$tmpdir" "$ROOT_DIR/scripts/eval/README.md" "$ROOT_DIR/CHANGELOG.md" "$REPORT" <<'PY'
import json
import re
import sys
from pathlib import Path

tmp = Path(sys.argv[1])
readme = Path(sys.argv[2]).read_text(encoding="utf-8")
changelog = Path(sys.argv[3]).read_text(encoding="utf-8")
report = Path(sys.argv[4]).read_text(encoding="utf-8")

passed = json.loads((tmp / "pass.json").read_text(encoding="utf-8"))
assert passed["schema"] == "agent_bridge.portfolio_continuity_eval.v0"
assert passed["verdict"] == "PASS"
assert passed["aggregate"]["case_count"] == 3
assert passed["aggregate"]["candidate_case_count"] == 3
assert passed["aggregate"]["cost_diagnostics_complete"] is True
assert passed["aggregate"]["case_pass_count"] == 3
assert passed["aggregate"]["required_claim_count"] == 8
assert passed["aggregate"]["required_claim_weight"] == 10.0
assert passed["aggregate"]["supported_claim_weight"] == 10.0
assert passed["aggregate"]["supported_claim_coverage"] == 1.0
assert passed["aggregate"]["evidence_precision"] == 1.0
assert passed["aggregate"]["stale_evidence_ref_count"] == 0
assert passed["aggregate"]["unknown_evidence_ref_count"] == 0
assert passed["aggregate"]["unsupported_claim_count"] == 0
assert passed["aggregate"]["forbidden_claim_count"] == 0
assert passed["aggregate"]["abstention_case_count"] == 1
assert passed["aggregate"]["abstention_pass_count"] == 1
assert passed["aggregate"]["context_tokens_total"] == 1010
assert passed["aggregate"]["latency_ms_p95"] == 22.0
assert all(passed["gate_checks"].values())
assert passed["gate_checks"]["abstention"] is True
assert all(passed["contract"].values()) is False  # explicit false capabilities exist
assert passed["contract"]["claim_ids_are_review_labels"] is True
assert passed["contract"]["natural_language_semantics_scored"] is False
assert passed["contract"]["raw_content_in_output"] is False
assert passed["contract"]["raw_evidence_keys_in_output"] is False
assert passed["contract"]["calls_llm"] is False
assert passed["contract"]["calls_retrieval"] is False
assert passed["contract"]["reads_ab_store"] is False
assert passed["contract"]["writes_ab_store"] is False
assert "raw-content field is forbidden; use redacted claim ids" in (
    tmp / "raw_content.err"
).read_text(
    encoding="utf-8"
)
assert "has no current accepted evidence" in (tmp / "impossible-fixture.err").read_text(
    encoding="utf-8"
)
assert "must be empty when confidence=abstained" in (
    tmp / "abstention_smuggle.err"
).read_text(encoding="utf-8")
assert "unsupported field(s)" in (tmp / "unknown_field.err").read_text(
    encoding="utf-8"
)
assert "free-form text is forbidden" in (tmp / "invalid_label.err").read_text(
    encoding="utf-8"
)
assert "free-form text is forbidden" in (
    tmp / "invalid_evidence_label.err"
).read_text(encoding="utf-8")
assert "non-standard JSON numeric constant is forbidden: NaN" in (
    tmp / "nan_latency.err"
).read_text(encoding="utf-8")
assert "JSON object contains a duplicate field" in (
    tmp / "duplicate_field.err"
).read_text(encoding="utf-8")
assert "must be a finite number" in (tmp / "huge_latency.err").read_text(
    encoding="utf-8"
)
assert "non-abstention cases must define required claims" in (
    tmp / "vacuous-fixture.err"
).read_text(encoding="utf-8")
assert re.fullmatch(r"[0-9a-f]{64}", passed["fixture_sha256"])
assert re.fullmatch(r"[0-9a-f]{64}", passed["candidate_sha256"])

serialized = json.dumps(passed, ensure_ascii=False)
for raw_key in ["syn_goal_v2", "syn_problem", "syn_partial_signal"]:
    assert raw_key not in serialized

stale = json.loads((tmp / "stale.out.json").read_text(encoding="utf-8"))
missing = json.loads((tmp / "missing.out.json").read_text(encoding="utf-8"))
unsupported = json.loads((tmp / "unsupported.out.json").read_text(encoding="utf-8"))
forbidden = json.loads((tmp / "forbidden.out.json").read_text(encoding="utf-8"))
bad_abstention = json.loads((tmp / "bad_abstention.out.json").read_text(encoding="utf-8"))
unknown = json.loads((tmp / "unknown_evidence.out.json").read_text(encoding="utf-8"))
wrong_precision = json.loads((tmp / "wrong_precision.out.json").read_text(encoding="utf-8"))
missing_case = json.loads((tmp / "missing_case.out.json").read_text(encoding="utf-8"))
uncertain_required = json.loads(
    (tmp / "uncertain_required.out.json").read_text(encoding="utf-8")
)

assert stale["verdict"] == "FAIL" and stale["aggregate"]["stale_evidence_ref_count"] == 1
assert missing["verdict"] == "FAIL" and missing["aggregate"]["missing_required_claim_count"] == 1
assert unsupported["verdict"] == "FAIL" and unsupported["aggregate"]["unsupported_claim_count"] == 1
assert forbidden["verdict"] == "FAIL" and forbidden["aggregate"]["forbidden_claim_count"] == 1
assert bad_abstention["verdict"] == "FAIL"
assert bad_abstention["aggregate"]["abstention_pass_count"] == 0
assert unknown["verdict"] == "FAIL" and unknown["aggregate"]["unknown_evidence_ref_count"] == 1
assert wrong_precision["verdict"] == "FAIL"
assert wrong_precision["aggregate"]["supported_claim_coverage"] == 1.0
assert wrong_precision["aggregate"]["evidence_precision"] == 0.888889
assert wrong_precision["aggregate"]["stale_evidence_ref_count"] == 0
assert wrong_precision["aggregate"]["unknown_evidence_ref_count"] == 0
assert wrong_precision["aggregate"]["unsupported_evidence_claim_count"] == 0
assert wrong_precision["gate_checks"]["evidence_precision"] is False
assert missing_case["verdict"] == "FAIL"
assert missing_case["aggregate"]["candidate_case_count"] == 2
assert missing_case["aggregate"]["cost_diagnostics_complete"] is False
assert missing_case["aggregate"]["case_pass_count"] == 2
assert missing_case["aggregate"]["abstention_pass_count"] == 0
assert missing_case["aggregate"]["context_tokens_total"] == 930
assert missing_case["aggregate"]["latency_ms_p95"] == 22.0
assert uncertain_required["verdict"] == "FAIL"
assert uncertain_required["aggregate"]["supported_claim_coverage"] == 0.8
assert uncertain_required["aggregate"]["missing_required_claim_count"] == 0
assert uncertain_required["cases"][0]["claim_coverage"] == 1.0
assert uncertain_required["cases"][0]["supported_claim_coverage"] == 0.666667

assert "portfolio_continuity_eval.py" in readme
assert "natural-language judge" in readme
assert "Portfolio continuity evaluation contract" in changelog

required_report = [
    "# Portfolio Continuity Evaluation Contract",
    "agent_bridge.portfolio_continuity_eval.v0",
    "claim_ids_are_review_labels: true",
    "natural_language_semantics_scored: false",
    "raw_evidence_keys_in_output: false",
    "calls_llm: false",
    "calls_retrieval: false",
    "reads_ab_store: false",
    "writes_ab_store: false",
    "benchmark_performance_claim: false",
    "supported_claim_coverage",
    "evidence_precision",
    "stale_evidence_ref_count",
    "unknown_evidence_ref_count",
    "abstention_pass_count",
    "synthetic fixtures only",
    "does not claim live digest quality",
    "portfolio_continuity_eval_contract_scope_20260710",
    "Forum thread: `design#119`, post `3026`",
]
missing_report = [needle for needle in required_report if needle not in report]
if missing_report:
    raise SystemExit("missing report anchors: " + ", ".join(missing_report))

print("Portfolio continuity evaluation verification passed")
PY
