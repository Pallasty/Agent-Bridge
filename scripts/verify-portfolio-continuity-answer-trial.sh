#!/usr/bin/env bash
# Verify the isolated capture, fixed-model generation, blinding, and score gate.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ADAPTER="$ROOT_DIR/scripts/eval/portfolio_continuity_answer_trial.py"
CONTRACT="$ROOT_DIR/scripts/eval/fixtures/portfolio_continuity_answer_contract.json"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-10-portfolio-continuity-blinded-answer-trial-prereg.md"
EXPANDED_CONTRACT="$ROOT_DIR/scripts/eval/fixtures/portfolio_continuity_expanded_answer_contract.json"
EXPANDED_REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-10-portfolio-continuity-expanded-answer-trial-prereg.md"
SUCCESSOR_CONTRACT="$ROOT_DIR/scripts/eval/fixtures/portfolio_continuity_successor_answer_contract.json"
SUCCESSOR_REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-10-portfolio-continuity-successor-protocol-prereg.md"
expanded_contract_sha_before="$(sha256sum "$EXPANDED_CONTRACT" | cut -d' ' -f1)"
expanded_report_sha_before="$(sha256sum "$EXPANDED_REPORT" | cut -d' ' -f1)"
successor_contract_sha_before="$(sha256sum "$SUCCESSOR_CONTRACT" | cut -d' ' -f1)"
successor_report_sha_before="$(sha256sum "$SUCCESSOR_REPORT" | cut -d' ' -f1)"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-answer-trial-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT
export PYTHONPYCACHEPREFIX="$tmpdir/pycache"

python3 -m py_compile "$ADAPTER"
python3 "$ADAPTER" validate-contract --contract "$CONTRACT" >"$tmpdir/repo-contract.json"
python3 "$ADAPTER" validate-contract --contract "$SUCCESSOR_CONTRACT" \
  >"$tmpdir/repo-successor-contract.json"
python3 - "$SUCCESSOR_CONTRACT" "$SUCCESSOR_REPORT" \
  "$ROOT_DIR/scripts/eval/README.md" "$ROOT_DIR/CHANGELOG.md" "$ROOT_DIR" <<'PY'
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

contract_path = Path(sys.argv[1])
report_path = Path(sys.argv[2])
public_paths = [contract_path, report_path, Path(sys.argv[3]), Path(sys.argv[4])]
root = Path(sys.argv[5])
contract = json.loads(contract_path.read_text(encoding="utf-8"))
report = report_path.read_text(encoding="utf-8")


def reported_hash(field: str, length: int) -> str:
    match = re.search(rf"^{re.escape(field)}: ([0-9a-f]{{{length}}})$", report, re.M)
    if match is None:
        raise SystemExit(f"successor preregistration is missing {field}")
    return match.group(1)


assert contract["schema"].endswith(".v2")
assert len(contract["cases"]) == 12
assert all("prompt" not in case for case in contract["cases"])
assert all("retrieval_query" not in case for case in contract["cases"])
assert all("retrieval_query_sha256" in case for case in contract["cases"])
contract_sha = hashlib.sha256(contract_path.read_bytes()).hexdigest()
assert reported_hash("contract_sha256", 64) == contract_sha
frozen_commit = reported_hash("contract_commit", 40)
for field, relative in {
    "harness_source_sha256": "scripts/eval/portfolio_continuity_answer_trial.py",
    "surface_source_sha256": "scripts/eval/portfolio_continuity_ab_trial.py",
}.items():
    current = root / relative
    expected = hashlib.sha256(current.read_bytes()).hexdigest()
    assert contract[field] == expected
    assert reported_hash(field, 64) == expected
    frozen = subprocess.check_output(
        ["git", "show", f"{frozen_commit}:{relative}"], cwd=root
    )
    if frozen != current.read_bytes():
        raise SystemExit(f"successor {field} drifted from its frozen commit")
frozen_contract = subprocess.check_output(
    [
        "git",
        "show",
        f"{frozen_commit}:scripts/eval/fixtures/portfolio_continuity_successor_answer_contract.json",
    ],
    cwd=root,
)
if frozen_contract != contract_path.read_bytes():
    raise SystemExit("successor contract drifted from its frozen commit")
for anchor in (
    "PRE-REGISTERED / IMPLEMENTATION VERIFIED / INDEPENDENT REVIEW",
    "NOT EXECUTED",
    "INVALID_REFERENCE_COVERAGE",
    "explicit full restart",
    "no answer postprocessing",
    "Automatic retry",
):
    assert anchor in report

private_dir = (
    root
    / "data/eval/portfolio-continuity-successor-answer-blind-20260710"
)
corpus_path = private_dir / "corpus.private.json"
seed_path = private_dir / "blind_seed.txt"
if corpus_path.exists() and seed_path.exists():
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    private_values = [seed_path.read_text(encoding="utf-8").strip()]
    for case in corpus["cases"]:
        private_values.extend([case["prompt"], case["retrieval_query"]])
    public = "\n".join(path.read_text(encoding="utf-8") for path in public_paths)
    if any(value in public for value in private_values):
        raise SystemExit("successor public artifacts leaked private material")
PY
python3 - "$ROOT_DIR" "$EXPANDED_CONTRACT" >"$tmpdir/repo-expanded-contract.json" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
contract_path = Path(sys.argv[2])
frozen_commit = "f472244f2bd07c9edee6b8b34118a17c795d72a7"
contract_bytes = contract_path.read_bytes()
contract = json.loads(contract_bytes)
if hashlib.sha256(contract_bytes).hexdigest() != (
    "a02affde622ede83c52121e47dd5cb085127b1e4525427518909eb7ba43de57d"
):
    raise SystemExit("historical expanded contract bytes drifted")
historical_contract = subprocess.check_output(
    [
        "git",
        "show",
        f"{frozen_commit}:scripts/eval/fixtures/portfolio_continuity_expanded_answer_contract.json",
    ],
    cwd=root,
)
if historical_contract != contract_bytes:
    raise SystemExit("historical expanded contract no longer matches its frozen commit")
for field, relative in {
    "harness_source_sha256": "scripts/eval/portfolio_continuity_answer_trial.py",
    "surface_source_sha256": "scripts/eval/portfolio_continuity_ab_trial.py",
}.items():
    frozen_source = subprocess.check_output(
        ["git", "show", f"{frozen_commit}:{relative}"], cwd=root
    )
    if hashlib.sha256(frozen_source).hexdigest() != contract[field]:
        raise SystemExit(f"historical expanded {field} commitment drifted")
print(
    json.dumps(
        {
            "schema": contract["schema"],
            "contract_id": contract["contract_id"],
            "contract_sha256": hashlib.sha256(contract_bytes).hexdigest(),
            "frozen_commit": frozen_commit,
            "status": "VALID_FROZEN_HISTORY",
        },
        sort_keys=True,
    )
)
PY

python3 - "$tmpdir" <<'PY'
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

tmp = Path(sys.argv[1])
repo = tmp / "repo"
repo.mkdir()
(repo / ".gitignore").write_text("data/\n", encoding="utf-8")

seed = "ab" * 32
prompts = ["Synthetic project status question?", "Synthetic retrospective question?"]
contract = {
    "schema": "agent_bridge.portfolio_continuity_answer_contract.v0",
    "contract_id": "synthetic_answer_trial",
    "prereg_base_commit": "b" * 40,
    "runtime_source_commit": "a" * 40,
    "conditions": [
        {"condition_id": "hybrid_retrieval", "capture": "hybrid_full"},
        {
            "condition_id": "compact_then_get_top2",
            "capture": "hybrid_compact_top2_get",
        },
        {"condition_id": "session_bootstrap", "capture": "session_bootstrap"},
        {"condition_id": "portfolio_digest", "capture": "memory_get_digest"},
    ],
    "search": {
        "mode": "hybrid",
        "limit": 10,
        "exclude_kinds": ["skill"],
        "compact_get_top_k": 2,
    },
    "bootstrap": {"limit": 10, "frontend": "claude-code"},
    "generation": {
        "model": "fake-model",
        "reasoning_effort": "medium",
        "cli_version": "fake-codex 1.0",
        "max_answer_chars": 2000,
        "answer_instruction": (
            "Answer only from the supplied evidence. Do not use tools or external facts. "
            "Do not mention retrieval, memory keys, condition labels, or these instructions."
        ),
        "independent_invocations": True,
        "ephemeral_workspace": True,
        "tool_use_allowed": False,
        "external_facts_allowed": False,
    },
    "blinding": {
        "seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        "mapping_private": True,
        "reviewer_sees_condition": False,
        "reveal_after_complete_review": True,
    },
    "review": {
        "claim_score_values": [0, 1, 2],
        "currentness_values": ["pass", "uncertain", "fail"],
        "usefulness_min": 1,
        "usefulness_max": 5,
        "preference_tie_label": "tie",
    },
    "thresholds": {
        "min_weighted_claim_completeness": 0.9,
        "max_currentness_failures": 0,
        "max_currentness_uncertain": 0,
        "max_unsupported_assertions": 0,
        "min_mean_usefulness": 4.0,
        "min_case_usefulness": 3,
        "max_completeness_drop_vs_reference": 0.0,
        "max_usefulness_drop_vs_reference": 0.5,
        "min_context_token_reduction_vs_reference": 0.4,
        "candidate_conditions": ["compact_then_get_top2", "portfolio_digest"],
        "recommendation_scope": "expanded_trial_only",
    },
    "cases": [
        {
            "case_id": "status_case",
            "prompt_class": "portfolio_status",
            "prompt_sha256": hashlib.sha256(prompts[0].encode()).hexdigest(),
            "required_claims": [
                {"claim_id": "vision", "weight": 1.0},
                {"claim_id": "state", "weight": 1.0},
            ],
            "optional_claims": [],
            "forbidden_claim_ids": ["unsupported_runtime_claim"],
        },
        {
            "case_id": "retro_case",
            "prompt_class": "portfolio_retrospective",
            "prompt_sha256": hashlib.sha256(prompts[1].encode()).hexdigest(),
            "required_claims": [
                {"claim_id": "lessons", "weight": 1.0},
                {"claim_id": "next_steps", "weight": 1.0},
            ],
            "optional_claims": [],
            "forbidden_claim_ids": ["unsupported_runtime_claim"],
        },
    ],
    "boundaries": {
        "raw_artifacts_in_git": False,
        "writes_live_ab_store": False,
        "llm_judge": False,
        "automatic_unblinding": False,
        "runtime_promotion_allowed": False,
        "automatic_digest_regeneration_allowed": False,
        "compact_default_change_allowed": False,
        "benchmark_claim_allowed": False,
        "version_or_tag_change_allowed": False,
    },
}
contract_path = repo / "answer-contract.json"
contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
subprocess.run(["git", "config", "user.email", "synthetic@example.invalid"], cwd=repo, check=True)
subprocess.run(["git", "config", "user.name", "Synthetic"], cwd=repo, check=True)
subprocess.run(["git", "add", ".gitignore", "answer-contract.json"], cwd=repo, check=True)
subprocess.run(["git", "commit", "-qm", "synthetic contract"], cwd=repo, check=True)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
contract_sha = hashlib.sha256(contract_path.read_bytes()).hexdigest()
spec = {
    "schema": "agent_bridge.portfolio_continuity_answer_spec.v0",
    "trial_id": "synthetic_answer_trial_run",
    "contract_sha256": contract_sha,
    "contract_commit": head,
    "repo": str(repo),
    "digest_key": "syn_00",
    "blind_seed": seed,
    "cases": [
        {"case_id": "status_case", "prompt": prompts[0]},
        {"case_id": "retro_case", "prompt": prompts[1]},
    ],
}
(repo / "data").mkdir()
(repo / "data/spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
bad_seed = json.loads(json.dumps(spec))
bad_seed["blind_seed"] = "cd" * 32
(repo / "data/spec.bad-seed.json").write_text(
    json.dumps(bad_seed, indent=2) + "\n", encoding="utf-8"
)

with sqlite3.connect(tmp / "source.db") as conn:
    conn.execute("CREATE TABLE marker (value TEXT NOT NULL)")
    conn.execute("INSERT INTO marker(value) VALUES ('live-source')")

fake_agent = r'''#!/usr/bin/env python3
import json
import os
import sqlite3
import sys

if sys.argv[1:] == ["--version"]:
    if os.environ.get("FAKE_WRONG_AGENT_VERSION"):
        print("agent-bridge 0.14.0 (fake; cccccccccccc)")
    else:
        print("agent-bridge 0.14.0 (fake; aaaaaaaaaaaa)")
    raise SystemExit(0)

db = os.environ["AGENT_BRIDGE_DB"]
if not os.environ.get("FAKE_HIDE_DB_PATH"):
    print(f"SQLite store path={db}", file=sys.stderr, flush=True)

records = []
for index in range(10):
    records.append({
        "key": f"syn_{index:02d}",
        "kind": "digest" if index == 0 else "context",
        "tags": ["synthetic", f"rank-{index + 1}"],
        "importance": 0.9 - index * 0.01,
        "status": "active",
        "created_at": 100 + index,
        "updated_at": 200 + index,
        "content": (f"Synthetic evidence row {index}. " + "grounded detail " * 140),
    })
if os.environ.get("FAKE_INTERNAL_IDENTIFIERS"):
    records[0]["content"] += (
        " portfolio_state_digest hybrid_retrieval portfolio_digest "
        "compact_then_get_top2 session_bootstrap"
    )

def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)

for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    request_id = request["id"]
    if request.get("method") == "initialize":
        emit({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-agent-bridge", "version": "test"},
            },
        })
        continue
    if request.get("method") != "tools/call":
        emit({"jsonrpc": "2.0", "id": request_id, "error": {"code": -1}})
        continue
    params = request["params"]
    name = params["name"]
    args = params.get("arguments", {})
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE marker SET value='snapshot-mutated'")
    if name == "memory_search":
        ordered = list(records)
        if os.environ.get("FAKE_REQUIRE_RETRIEVAL_QUERY") and not args.get(
            "query", ""
        ).startswith("Synthetic retrieval query"):
            ordered = []
        if args.get("compact") and os.environ.get("FAKE_RANK_MISMATCH"):
            ordered[0], ordered[1] = ordered[1], ordered[0]
        if not args.get("compact") and os.environ.get("FAKE_EMPTY_FULL_SEARCH"):
            ordered = []
        if not args.get("compact") and os.environ.get("FAKE_DUPLICATE_FULL_SEARCH"):
            ordered[1] = ordered[0]
        if args.get("compact"):
            rows = []
            for rank, record in enumerate(ordered, start=1):
                content = record["content"]
                row = {
                    "key": record["key"],
                    "kind": record["kind"],
                    "tags": record["tags"],
                    "importance": record["importance"],
                    "score": 1.0 / rank,
                    "content_preview": content[:200],
                    "content_chars": len(content),
                    "content_truncated": len(content) > 200,
                }
                if os.environ.get("FAKE_COMPACT_LEAK"):
                    row["content"] = content
                rows.append(row)
            text = json.dumps(rows, ensure_ascii=False)
        else:
            text = json.dumps(
                [
                    {"record": record, "score": 1.0 / rank}
                    for rank, record in enumerate(ordered, start=1)
                ],
                ensure_ascii=False,
            )
    elif name == "session_bootstrap":
        text = (
            "=== Project State ===\n"
            + records[0]["content"]
            + "\n=== Next Actions ===\n"
            + records[1]["content"]
        )
    elif name == "memory_get":
        key = args["key"]
        record = next((row for row in records if row["key"] == key), None)
        if record is None:
            emit({"jsonrpc": "2.0", "id": request_id, "error": {"code": -2}})
            continue
        text = json.dumps(record, ensure_ascii=False)
    else:
        emit({"jsonrpc": "2.0", "id": request_id, "error": {"code": -3}})
        continue
    emit({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"isError": False, "content": [{"type": "text", "text": text}]},
    })
'''
fake_agent_path = tmp / "fake-agent-bridge"
fake_agent_path.write_text(fake_agent, encoding="utf-8")
fake_agent_path.chmod(0o755)

fake_codex = r'''#!/usr/bin/env python3
import hashlib
import json
import os
import sys
from pathlib import Path

if sys.argv[1:] == ["--version"]:
    if os.environ.get("FAKE_WRONG_CODEX_VERSION"):
        print("fake-codex 2.0")
    else:
        print("fake-codex 1.0")
    raise SystemExit(0)

prompt = sys.stdin.read()
output_path = Path(sys.argv[sys.argv.index("--output-last-message") + 1])
count_path = os.environ.get("FAKE_CODEX_COUNT_FILE")
if count_path:
    path = Path(count_path)
    count = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    path.write_text(str(count + 1), encoding="utf-8")
if os.environ.get("FAKE_CODEX_MARKER_LEAK"):
    answer = "hybrid_retrieval"
elif os.environ.get("FAKE_CODEX_DIGEST_KEY_LEAK"):
    answer = "syn_00"
else:
    answer = "Synthetic grounded project answer " + hashlib.sha256(prompt.encode()).hexdigest()[:12]
if os.environ.get("FAKE_CODEX_PADDED_ANSWER"):
    answer = "  " + answer + "  \n"
output_path.write_text(json.dumps({"answer_markdown": answer}) + "\n", encoding="utf-8")
print(json.dumps({"type": "thread.started", "thread_id": "synthetic"}))
print(json.dumps({"type": "turn.started"}))
if os.environ.get("FAKE_CODEX_TOOL_EVENT"):
    print(json.dumps({
        "type": "item.completed",
        "item": {"type": "command_execution", "command": "forbidden"},
    }))
else:
    print(json.dumps({
        "type": "item.completed",
        "item": {"type": "agent_message", "text": answer},
    }))
print(json.dumps({"type": "turn.completed"}))
'''
fake_codex_path = tmp / "fake-codex"
fake_codex_path.write_text(fake_codex, encoding="utf-8")
fake_codex_path.chmod(0o755)
PY

repo="$tmpdir/repo"
data="$repo/data"
contract="$repo/answer-contract.json"
spec="$data/spec.json"
capture="$data/capture.raw.json"

python3 "$ADAPTER" validate-contract --contract "$contract" >"$tmpdir/contract.json"
python3 "$ADAPTER" capture \
  --contract "$contract" \
  --spec "$spec" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$capture" \
  --redacted-output "$data/capture.redacted.json" \
  >"$tmpdir/capture.stdout.json"

python3 "$ADAPTER" generate \
  --contract "$contract" \
  --spec "$spec" \
  --capture "$capture" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$data/generation.raw.json" \
  --blind-output "$data/blind.packet.json" \
  --map-output "$data/blind.map.json" \
  --review-template-output "$data/review.template.json" \
  --redacted-output "$data/generation.redacted.json" \
  >"$tmpdir/generate.stdout.json"

python3 - "$tmpdir" <<'PY'
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

tmp = Path(sys.argv[1])
data = tmp / "repo/data"
blind = json.loads((data / "blind.packet.json").read_text(encoding="utf-8"))
review = json.loads((data / "review.template.json").read_text(encoding="utf-8"))
review["reviewer"] = "synthetic-owner"
review["reviewed_at"] = 1_800_000_000
for case in review["cases"]:
    for answer in case["answers"]:
        for claim in answer["claim_scores"]:
            claim["score"] = 2
        answer["currentness"] = "pass"
        answer["unsupported_assertion_count"] = 0
        answer["usefulness"] = 4
    case["preferred_answer_id"] = "tie"
(data / "review.complete.json").write_text(
    json.dumps(review, indent=2) + "\n", encoding="utf-8"
)

incomplete = json.loads(json.dumps(review))
incomplete["cases"][0]["answers"][0]["claim_scores"][0]["score"] = None
(data / "review.incomplete.json").write_text(
    json.dumps(incomplete, indent=2) + "\n", encoding="utf-8"
)

bad_map = json.loads((data / "blind.map.json").read_text(encoding="utf-8"))
bad_map["cases"][0]["answers"][0]["answer_sha256"] = "0" * 64
(data / "blind.map.bad-hash.json").write_text(
    json.dumps(bad_map, indent=2) + "\n", encoding="utf-8"
)

generation = json.loads((data / "generation.raw.json").read_text(encoding="utf-8"))
bad_generation = json.loads(json.dumps(generation))
bad_generation["generated_at"] += 1
(data / "generation.bad-hash.json").write_text(
    json.dumps(bad_generation, indent=2) + "\n", encoding="utf-8"
)

bad_blind_case = json.loads(json.dumps(blind))
bad_blind_case["cases"].pop()
(data / "blind.bad-case.json").write_text(
    json.dumps(bad_blind_case, indent=2) + "\n", encoding="utf-8"
)
bad_blind_rubric = json.loads(json.dumps(blind))
bad_blind_rubric["cases"][0]["required_claims"][0]["weight"] = 0.01
(data / "blind.bad-rubric.json").write_text(
    json.dumps(bad_blind_rubric, indent=2) + "\n", encoding="utf-8"
)
bad_blind_leak = json.loads(json.dumps(blind))
bad_blind_leak["condition_mapping"] = {"ans_hidden": "hybrid_retrieval"}
(data / "blind.bad-leak.json").write_text(
    json.dumps(bad_blind_leak, indent=2) + "\n", encoding="utf-8"
)

capture = json.loads((data / "capture.raw.json").read_text(encoding="utf-8"))
bad_capture = json.loads(json.dumps(capture))
bad_capture["runs"][0]["snapshot_sha256_before"] = "0" * 64
(data / "capture.bad-run.json").write_text(
    json.dumps(bad_capture, indent=2) + "\n", encoding="utf-8"
)

with sqlite3.connect(tmp / "source.db") as conn:
    assert conn.execute("SELECT value FROM marker").fetchone()[0] == "live-source"

blind_text = (data / "blind.packet.json").read_text(encoding="utf-8")
review_text = (data / "review.template.json").read_text(encoding="utf-8")
for condition in [
    "hybrid_retrieval",
    "compact_then_get_top2",
    "session_bootstrap",
    "portfolio_digest",
]:
    assert condition not in blind_text
    assert condition not in review_text
assert blind["boundary"]["condition_mapping_present"] is False
assert blind["boundary"]["raw_context_present"] is False
PY

python3 "$ADAPTER" score \
  --contract "$contract" \
  --capture "$capture" \
  --generation "$data/generation.raw.json" \
  --blind-packet "$data/blind.packet.json" \
  --blind-map "$data/blind.map.json" \
  --review "$data/review.complete.json" \
  --output "$data/score.json" \
  >"$tmpdir/score.stdout.json"

if python3 "$ADAPTER" score \
  --contract "$contract" \
  --capture "$capture" \
  --generation "$data/does-not-exist-generation.json" \
  --blind-packet "$data/blind.packet.json" \
  --blind-map "$data/does-not-exist-map.json" \
  --review "$data/review.incomplete.json" \
  --output "$data/score.incomplete.json" \
  >"$tmpdir/incomplete.stdout" 2>"$tmpdir/incomplete.stderr"; then
  echo "incomplete blind review unexpectedly passed" >&2
  exit 1
fi

if python3 "$ADAPTER" score \
  --contract "$contract" \
  --capture "$capture" \
  --generation "$data/generation.raw.json" \
  --blind-packet "$data/blind.packet.json" \
  --blind-map "$data/blind.map.bad-hash.json" \
  --review "$data/review.complete.json" \
  --output "$data/score.bad-map.json" \
  >"$tmpdir/bad-map.stdout" 2>"$tmpdir/bad-map.stderr"; then
  echo "hash-drifted blind map unexpectedly passed" >&2
  exit 1
fi

if python3 "$ADAPTER" score \
  --contract "$contract" \
  --capture "$capture" \
  --generation "$data/generation.bad-hash.json" \
  --blind-packet "$data/blind.packet.json" \
  --blind-map "$data/blind.map.json" \
  --review "$data/review.complete.json" \
  --output "$data/score.bad-generation.json" \
  >"$tmpdir/bad-generation.stdout" 2>"$tmpdir/bad-generation.stderr"; then
  echo "hash-drifted generation packet unexpectedly passed" >&2
  exit 1
fi

if python3 "$ADAPTER" score \
  --contract "$contract" \
  --capture "$capture" \
  --generation "$data/generation.raw.json" \
  --blind-packet "$data/blind.bad-case.json" \
  --blind-map "$data/blind.map.json" \
  --review "$data/review.complete.json" \
  --output "$data/score.bad-case.json" \
  >"$tmpdir/bad-case.stdout" 2>"$tmpdir/bad-case.stderr"; then
  echo "blind packet with missing case unexpectedly passed" >&2
  exit 1
fi

if python3 "$ADAPTER" score \
  --contract "$contract" \
  --capture "$capture" \
  --generation "$data/generation.raw.json" \
  --blind-packet "$data/blind.bad-rubric.json" \
  --blind-map "$data/blind.map.json" \
  --review "$data/review.complete.json" \
  --output "$data/score.bad-rubric.json" \
  >"$tmpdir/bad-rubric.stdout" 2>"$tmpdir/bad-rubric.stderr"; then
  echo "blind packet with modified rubric unexpectedly passed" >&2
  exit 1
fi

if python3 "$ADAPTER" score \
  --contract "$contract" \
  --capture "$capture" \
  --generation "$data/generation.raw.json" \
  --blind-packet "$data/blind.bad-leak.json" \
  --blind-map "$data/blind.map.json" \
  --review "$data/review.complete.json" \
  --output "$data/score.bad-leak.json" \
  >"$tmpdir/bad-leak.stdout" 2>"$tmpdir/bad-leak.stderr"; then
  echo "blind packet with condition mapping unexpectedly passed" >&2
  exit 1
fi

if python3 "$ADAPTER" score \
  --contract "$contract" \
  --capture "$data/capture.bad-run.json" \
  --generation "$data/generation.raw.json" \
  --blind-packet "$data/blind.packet.json" \
  --blind-map "$data/blind.map.json" \
  --review "$data/review.complete.json" \
  --output "$data/score.bad-run.json" \
  >"$tmpdir/bad-run.stdout" 2>"$tmpdir/bad-run.stderr"; then
  echo "capture with forged isolation run unexpectedly passed" >&2
  exit 1
fi

if FAKE_COMPACT_LEAK=1 python3 "$ADAPTER" capture \
  --contract "$contract" \
  --spec "$spec" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$data/capture.leak.json" \
  --redacted-output "$data/capture.leak.redacted.json" \
  >"$tmpdir/leak.stdout" 2>"$tmpdir/leak.stderr"; then
  echo "compact full-content leak unexpectedly passed" >&2
  exit 1
fi

if FAKE_RANK_MISMATCH=1 python3 "$ADAPTER" capture \
  --contract "$contract" \
  --spec "$spec" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$data/capture.rank.json" \
  --redacted-output "$data/capture.rank.redacted.json" \
  >"$tmpdir/rank.stdout" 2>"$tmpdir/rank.stderr"; then
  echo "compact/full rank mismatch unexpectedly passed" >&2
  exit 1
fi

if FAKE_HIDE_DB_PATH=1 python3 "$ADAPTER" capture \
  --contract "$contract" \
  --spec "$spec" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$data/capture.hidden.json" \
  --redacted-output "$data/capture.hidden.redacted.json" \
  >"$tmpdir/hidden.stdout" 2>"$tmpdir/hidden.stderr"; then
  echo "unconfirmed snapshot path unexpectedly passed" >&2
  exit 1
fi

if FAKE_WRONG_AGENT_VERSION=1 python3 "$ADAPTER" capture \
  --contract "$contract" \
  --spec "$spec" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$data/capture.wrong-version.json" \
  --redacted-output "$data/capture.wrong-version.redacted.json" \
  >"$tmpdir/wrong-version.stdout" 2>"$tmpdir/wrong-version.stderr"; then
  echo "wrong Agent-Bridge identity unexpectedly passed" >&2
  exit 1
fi

if python3 "$ADAPTER" capture \
  --contract "$contract" \
  --spec "$data/spec.bad-seed.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$data/capture.bad-seed.json" \
  --redacted-output "$data/capture.bad-seed.redacted.json" \
  >"$tmpdir/bad-seed.stdout" 2>"$tmpdir/bad-seed.stderr"; then
  echo "blind-seed commitment mismatch unexpectedly passed" >&2
  exit 1
fi

if FAKE_CODEX_TOOL_EVENT=1 python3 "$ADAPTER" generate \
  --contract "$contract" \
  --spec "$spec" \
  --capture "$capture" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$data/generation.tool.json" \
  --blind-output "$data/blind.tool.json" \
  --map-output "$data/map.tool.json" \
  --review-template-output "$data/review.tool.json" \
  --redacted-output "$data/generation.tool.redacted.json" \
  >"$tmpdir/tool.stdout" 2>"$tmpdir/tool.stderr"; then
  echo "Codex tool event unexpectedly passed" >&2
  exit 1
fi

if FAKE_WRONG_CODEX_VERSION=1 python3 "$ADAPTER" generate \
  --contract "$contract" \
  --spec "$spec" \
  --capture "$capture" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$data/generation.wrong-version.json" \
  --blind-output "$data/blind.wrong-version.json" \
  --map-output "$data/map.wrong-version.json" \
  --review-template-output "$data/review.wrong-version.json" \
  --redacted-output "$data/generation.wrong-version.redacted.json" \
  >"$tmpdir/codex-version.stdout" 2>"$tmpdir/codex-version.stderr"; then
  echo "wrong Codex identity unexpectedly passed" >&2
  exit 1
fi

outside="$tmpdir/outside-capture.json"
if python3 "$ADAPTER" capture \
  --contract "$contract" \
  --spec "$spec" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$outside" \
  --redacted-output "$data/outside.redacted.json" \
  >"$tmpdir/outside.stdout" 2>"$tmpdir/outside.stderr"; then
  echo "raw output outside ignored data unexpectedly passed" >&2
  exit 1
fi

python3 - "$tmpdir" "$CONTRACT" "$REPORT" "$ROOT_DIR/scripts/eval/README.md" "$ROOT_DIR/CHANGELOG.md" <<'PY'
import json
import sys
from pathlib import Path

tmp = Path(sys.argv[1])
repo_contract = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
report = Path(sys.argv[3]).read_text(encoding="utf-8")
readme = Path(sys.argv[4]).read_text(encoding="utf-8")
changelog = Path(sys.argv[5]).read_text(encoding="utf-8")
data = tmp / "repo/data"
score = json.loads((data / "score.json").read_text(encoding="utf-8"))
capture = json.loads((data / "capture.redacted.json").read_text(encoding="utf-8"))
generation = json.loads((data / "generation.redacted.json").read_text(encoding="utf-8"))

assert score["status"] == "READY_FOR_EXPANDED_TRIAL"
assert score["candidate_recommendations"]["compact_then_get_top2"][
    "advance_to_expanded_trial"
] is True
assert score["candidate_recommendations"]["portfolio_digest"][
    "advance_to_expanded_trial"
] is True
assert score["boundary"]["runtime_promotion_allowed"] is False
assert capture["case_count"] == 2
assert capture["condition_run_count"] == 8
assert all(case["ranking_projection_invariant"] for case in capture["cases"])
assert generation["status"] == "WAIT_OWNER_BLIND_REVIEW"
assert generation["answer_count"] == 8
assert generation["boundary"]["condition_mapping_in_packet"] is False

for safe_path in [
    data / "capture.redacted.json",
    data / "generation.redacted.json",
    data / "score.json",
    tmp / "capture.stdout.json",
    tmp / "generate.stdout.json",
    tmp / "score.stdout.json",
]:
    text = safe_path.read_text(encoding="utf-8")
    for private in [
        "Synthetic project status question?",
        "Synthetic evidence row",
        "Synthetic grounded project answer",
        "ans_",
        "synthetic-owner",
    ]:
        assert private not in text, (safe_path, private)

assert "must be populated" in (tmp / "incomplete.stderr").read_text(encoding="utf-8")
assert "answer hash mismatch" in (tmp / "bad-map.stderr").read_text(encoding="utf-8")
assert "generation hash mismatch" in (
    tmp / "bad-generation.stderr"
).read_text(encoding="utf-8")
assert "case count mismatch" in (tmp / "bad-case.stderr").read_text(encoding="utf-8")
assert "claim rubric differs" in (tmp / "bad-rubric.stderr").read_text(encoding="utf-8")
assert "unsupported field" in (tmp / "bad-leak.stderr").read_text(encoding="utf-8")
assert "did not start from the shared snapshot" in (
    tmp / "bad-run.stderr"
).read_text(encoding="utf-8")
assert "unsupported field" in (tmp / "leak.stderr").read_text(encoding="utf-8")
assert "rankings differ" in (tmp / "rank.stderr").read_text(encoding="utf-8")
assert "did not confirm" in (tmp / "hidden.stderr").read_text(encoding="utf-8")
assert "identity does not match" in (tmp / "wrong-version.stderr").read_text(encoding="utf-8")
assert "preregistered commitment" in (tmp / "bad-seed.stderr").read_text(encoding="utf-8")
assert "attempted tool use" in (tmp / "tool.stderr").read_text(encoding="utf-8")
assert "identity does not match" in (tmp / "codex-version.stderr").read_text(encoding="utf-8")
assert "must stay under repository data/" in (tmp / "outside.stderr").read_text(encoding="utf-8")

assert repo_contract["blinding"]["seed_sha256"] == (
    "bc08a39664fb3151f046538560f0922fa592ca36975d3f9e6f23f313f6144428"
)
assert repo_contract["generation"]["model"] == "gpt-5.4"
assert repo_contract["search"]["compact_get_top_k"] == 2
assert repo_contract["thresholds"]["recommendation_scope"] == "expanded_trial_only"
assert "portfolio_continuity_answer_trial.py" in readme
assert "Blinded portfolio-continuity answer trial" in changelog

required_report = [
    "# Portfolio Continuity Blinded Answer Trial Preregistration",
    "PRE-REGISTERED",
    "compact_then_get_top2",
    "gpt-5.4",
    "codex-cli 0.144.1",
    "bc08a39664fb3151f046538560f0922fa592ca36975d3f9e6f23f313f6144428",
    "expanded_trial_only",
    "WAIT_OWNER_BLIND_REVIEW",
    "runtime_promotion_allowed: false",
    "Forum thread: `design#119`, start post `3037`",
]
missing = [needle for needle in required_report if needle not in report]
if missing:
    raise SystemExit("missing report anchors: " + ", ".join(missing))
for private in [
    "portfolio_state_digest",
    "我们来检查Agent-Bridge记忆中项目的当前状态",
]:
    assert private not in report

print("Portfolio continuity blinded answer trial verification passed")
PY

# Exercise the committed v1 12-case/two-condition matrix end to end.
v1repo="$tmpdir/v1repo"
mkdir -p "$v1repo/scripts/eval" "$v1repo/data"
cp "$ADAPTER" "$v1repo/scripts/eval/portfolio_continuity_answer_trial.py"
cp "$ROOT_DIR/scripts/eval/portfolio_continuity_ab_trial.py" \
  "$v1repo/scripts/eval/portfolio_continuity_ab_trial.py"
printf 'data/\n' >"$v1repo/.gitignore"

python3 - "$v1repo" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

repo = Path(sys.argv[1])
adapter = repo / "scripts/eval/portfolio_continuity_answer_trial.py"
surface = repo / "scripts/eval/portfolio_continuity_ab_trial.py"
seed = "ef" * 32
strata = [
    "portfolio_status",
    "portfolio_retrospective",
    "portfolio_planning",
    "dependency_risk",
    "stale_state",
    "cross_project_conflict",
]
prompts = [f"Synthetic expanded question {index}?" for index in range(12)]
cases = []
for index, prompt in enumerate(prompts):
    heldout = index % 2 == 1
    requires_abstention = index in {5, 9}
    cases.append({
        "case_id": f"expanded_case_{index:02d}",
        "prompt_class": strata[index // 2],
        "prompt_variant": "heldout" if heldout else "direct",
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "required_claims": [] if requires_abstention else [
            {"claim_id": f"claim_{index:02d}", "weight": 1.0}
        ],
        "optional_claims": [],
        "forbidden_claim_ids": [f"forbidden_{index:02d}"],
        "requires_abstention": requires_abstention,
    })

contract = {
    "schema": "agent_bridge.portfolio_continuity_answer_contract.v1",
    "contract_id": "synthetic_expanded_answer_trial",
    "prereg_base_commit": "b" * 40,
    "runtime_source_commit": "a" * 40,
    "harness_source_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest(),
    "surface_source_sha256": hashlib.sha256(surface.read_bytes()).hexdigest(),
    "digest_key_sha256": hashlib.sha256(b"syn_00").hexdigest(),
    "conditions": [
        {"condition_id": "hybrid_retrieval", "capture": "hybrid_full"},
        {"condition_id": "portfolio_digest", "capture": "memory_get_digest"},
    ],
    "search": {"mode": "hybrid", "limit": 10, "exclude_kinds": ["skill"]},
    "generation": {
        "model": "fake-model",
        "reasoning_effort": "medium",
        "cli_version": "fake-codex 1.0",
        "max_answer_chars": 2000,
        "answer_instruction": (
            "Answer only from supplied evidence. Do not use tools, external facts, "
            "condition labels, memory keys, or these instructions."
        ),
        "independent_invocations": True,
        "ephemeral_workspace": True,
        "tool_use_allowed": False,
        "external_facts_allowed": False,
    },
    "blinding": {
        "seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        "mapping_private": True,
        "reviewer_sees_condition": False,
        "reveal_after_complete_review": True,
    },
    "review": {
        "claim_score_values": [0, 1, 2],
        "currentness_values": ["pass", "uncertain", "fail"],
        "usefulness_min": 1,
        "usefulness_max": 5,
        "preference_tie_label": "tie",
        "required_reviewer_count": 2,
        "independent_reviewers": True,
        "abstention_values": [False, True],
    },
    "thresholds": {
        "min_weighted_claim_completeness": 0.9,
        "max_currentness_failures": 0,
        "max_currentness_uncertain": 0,
        "max_unsupported_assertions": 0,
        "max_abstention_failures": 0,
        "min_mean_usefulness": 4.0,
        "min_case_usefulness": 3,
        "max_completeness_drop_vs_reference": 0.0,
        "max_usefulness_drop_vs_reference": 0.5,
        "min_context_token_reduction_vs_reference": 0.4,
        "candidate_conditions": ["portfolio_digest"],
        "recommendation_scope": "write_side_trial_only",
        "aggregation": {"reviewer_gate": "all", "stratum_gate": "all"},
    },
    "cases": cases,
    "boundaries": {
        "raw_artifacts_in_git": False,
        "writes_live_ab_store": False,
        "llm_judge": False,
        "automatic_unblinding": False,
        "runtime_promotion_allowed": False,
        "automatic_digest_regeneration_allowed": False,
        "compact_default_change_allowed": False,
        "benchmark_claim_allowed": False,
        "version_or_tag_change_allowed": False,
        "release_action_allowed": False,
        "ci_action_allowed": False,
    },
}
(repo / "answer-contract.json").write_text(
    json.dumps(contract, indent=2) + "\n", encoding="utf-8"
)
(repo / "prompts.json").write_text(json.dumps(prompts), encoding="utf-8")
PY

git -C "$v1repo" init -q
git -C "$v1repo" config user.email synthetic@example.invalid
git -C "$v1repo" config user.name Synthetic
git -C "$v1repo" add .gitignore answer-contract.json prompts.json scripts/eval
git -C "$v1repo" commit -qm 'synthetic v1 contract and harness'

python3 - "$v1repo" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1])
contract_path = repo / "answer-contract.json"
contract = json.loads(contract_path.read_text(encoding="utf-8"))
prompts = json.loads((repo / "prompts.json").read_text(encoding="utf-8"))
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
spec = {
    "schema": "agent_bridge.portfolio_continuity_answer_spec.v1",
    "trial_id": "synthetic_expanded_run",
    "contract_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
    "contract_commit": head,
    "repo": str(repo),
    "digest_key": "syn_00",
    "blind_seed": "ef" * 32,
    "cases": [
        {"case_id": case["case_id"], "prompt": prompt}
        for case, prompt in zip(contract["cases"], prompts, strict=True)
    ],
}
(repo / "data/spec.json").write_text(
    json.dumps(spec, indent=2) + "\n", encoding="utf-8"
)
PY

v1adapter="$v1repo/scripts/eval/portfolio_continuity_answer_trial.py"
v1surface="$v1repo/scripts/eval/portfolio_continuity_ab_trial.py"
v1data="$v1repo/data"
python3 "$v1adapter" capture \
  --contract "$v1repo/answer-contract.json" \
  --spec "$v1data/spec.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$v1data/capture.raw.json" \
  --redacted-output "$v1data/capture.redacted.json" \
  >"$tmpdir/v1-capture.stdout.json"

FAKE_EMPTY_FULL_SEARCH=1 python3 "$v1adapter" capture \
  --contract "$v1repo/answer-contract.json" \
  --spec "$v1data/spec.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$v1data/capture.empty-reference.raw.json" \
  --redacted-output "$v1data/capture.empty-reference.redacted.json" \
  >"$tmpdir/v1-capture-empty-reference.stdout.json"

python3 "$v1adapter" generate \
  --contract "$v1repo/answer-contract.json" \
  --spec "$v1data/spec.json" \
  --capture "$v1data/capture.empty-reference.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v1data/generation.empty-reference.raw.json" \
  --blind-output "$v1data/blind.empty-reference.packet.json" \
  --map-output "$v1data/blind.empty-reference.map.json" \
  --review-template-output "$v1data/review.empty-reference.template.json" \
  --redacted-output "$v1data/generation.empty-reference.redacted.json" \
  >"$tmpdir/v1-generate-empty-reference.stdout.json"

if FAKE_DUPLICATE_FULL_SEARCH=1 python3 "$v1adapter" capture \
  --contract "$v1repo/answer-contract.json" \
  --spec "$v1data/spec.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$v1data/capture.duplicate-ranking.raw.json" \
  --redacted-output "$v1data/capture.duplicate-ranking.redacted.json" \
  >"$tmpdir/v1-capture-duplicate-ranking.stdout" \
  2>"$tmpdir/v1-capture-duplicate-ranking.stderr"; then
  echo "v1 capture with duplicate full-search ranking unexpectedly passed" >&2
  exit 1
fi
test ! -e "$v1data/capture.duplicate-ranking.raw.json"
test ! -e "$v1data/capture.duplicate-ranking.redacted.json"

python3 "$v1adapter" generate \
  --contract "$v1repo/answer-contract.json" \
  --spec "$v1data/spec.json" \
  --capture "$v1data/capture.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v1data/generation.raw.json" \
  --blind-output "$v1data/blind.packet.json" \
  --map-output "$v1data/blind.map.json" \
  --review-template-output "$v1data/review.template.json" \
  --redacted-output "$v1data/generation.redacted.json" \
  >"$tmpdir/v1-generate.stdout.json"

if FAKE_CODEX_DIGEST_KEY_LEAK=1 python3 "$v1adapter" generate \
  --contract "$v1repo/answer-contract.json" \
  --spec "$v1data/spec.json" \
  --capture "$v1data/capture.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v1data/generation.key-leak.json" \
  --blind-output "$v1data/blind.key-leak.json" \
  --map-output "$v1data/map.key-leak.json" \
  --review-template-output "$v1data/review.key-leak.json" \
  --redacted-output "$v1data/generation.key-leak.redacted.json" \
  >"$tmpdir/v1-key-leak.stdout" 2>"$tmpdir/v1-key-leak.stderr"; then
  echo "v1 answer leaking the committed digest key unexpectedly passed" >&2
  exit 1
fi

python3 - "$v1data" <<'PY'
import copy
import json
import sys
from pathlib import Path

data = Path(sys.argv[1])
template = json.loads((data / "review.template.json").read_text(encoding="utf-8"))
reviews = []
for reviewer in ["synthetic-reviewer-alpha", "synthetic-reviewer-bravo"]:
    review = copy.deepcopy(template)
    review.update({
        "reviewer": reviewer,
        "reviewed_at": 1_800_000_000,
        "independent_review": True,
        "condition_blinded": True,
    })
    for case in review["cases"]:
        for answer in case["answers"]:
            for claim in answer["claim_scores"]:
                claim["score"] = 2
            answer["currentness"] = "pass"
            answer["unsupported_assertion_count"] = 0
            answer["usefulness"] = 4
            if "abstention_pass" in answer:
                answer["abstention_pass"] = True
        case["preferred_answer_id"] = "tie"
    reviews.append(review)

for index, review in enumerate(reviews, start=1):
    (data / f"review.{index}.json").write_text(
        json.dumps(review, indent=2) + "\n", encoding="utf-8"
    )

incomplete = copy.deepcopy(reviews[1])
incomplete["cases"][0]["answers"][0]["claim_scores"][0]["score"] = None
(data / "review.incomplete.json").write_text(
    json.dumps(incomplete, indent=2) + "\n", encoding="utf-8"
)
duplicate = copy.deepcopy(reviews[1])
duplicate["reviewer"] = reviews[0]["reviewer"]
(data / "review.duplicate.json").write_text(
    json.dumps(duplicate, indent=2) + "\n", encoding="utf-8"
)
abstention_fail = copy.deepcopy(reviews[1])
for case in abstention_fail["cases"]:
    for answer in case["answers"]:
        if "abstention_pass" in answer:
            answer["abstention_pass"] = False
            (data / "review.abstention-fail.json").write_text(
                json.dumps(abstention_fail, indent=2) + "\n", encoding="utf-8"
            )
            raise SystemExit
PY

python3 "$v1adapter" score \
  --contract "$v1repo/answer-contract.json" \
  --capture "$v1data/capture.raw.json" \
  --generation "$v1data/generation.raw.json" \
  --blind-packet "$v1data/blind.packet.json" \
  --blind-map "$v1data/blind.map.json" \
  --review "$v1data/review.1.json" \
  --review "$v1data/review.2.json" \
  --output "$v1data/score.json" \
  >"$tmpdir/v1-score.stdout.json"

python3 "$v1adapter" score \
  --contract "$v1repo/answer-contract.json" \
  --capture "$v1data/capture.raw.json" \
  --generation "$v1data/generation.raw.json" \
  --blind-packet "$v1data/blind.packet.json" \
  --blind-map "$v1data/blind.map.json" \
  --review "$v1data/review.2.json" \
  --review "$v1data/review.1.json" \
  --output "$v1data/score.swapped.json" \
  >"$tmpdir/v1-score-swapped.stdout.json"

cmp "$v1data/score.json" "$v1data/score.swapped.json"

python3 - "$v1data" <<'PY'
import copy
import hashlib
import json
import sys
from pathlib import Path

data = Path(sys.argv[1])
review = json.loads((data / "review.2.json").read_text(encoding="utf-8"))
mapping = json.loads((data / "blind.map.json").read_text(encoding="utf-8"))
digest_ids = {
    case["case_id"]: next(
        answer["answer_id"]
        for answer in case["answers"]
        if answer["condition"] == "portfolio_digest"
    )
    for case in mapping["cases"]
}
disagreement = copy.deepcopy(review)
first_case = disagreement["cases"][0]
for answer in first_case["answers"]:
    if answer["answer_id"] == digest_ids[first_case["case_id"]]:
        answer["claim_scores"][0]["score"] = 0
(data / "review.disagreement.json").write_text(
    json.dumps(disagreement, indent=2) + "\n", encoding="utf-8"
)

bad_field = copy.deepcopy(review)
bad_field["cases"][0]["answers"][0]["abstention_pass"] = True
(data / "review.bad-abstention-field.json").write_text(
    json.dumps(bad_field, indent=2) + "\n", encoding="utf-8"
)

contract = json.loads((data.parent / "answer-contract.json").read_text(encoding="utf-8"))
bad_stratum = copy.deepcopy(contract)
bad_stratum["cases"][0]["prompt_class"] = "stale_state"
(data / "contract.bad-stratum.json").write_text(
    json.dumps(bad_stratum, indent=2) + "\n", encoding="utf-8"
)
bad_abstention_count = copy.deepcopy(contract)
bad_abstention_count["cases"][1]["required_claims"] = []
bad_abstention_count["cases"][1]["requires_abstention"] = True
(data / "contract.bad-abstention-count.json").write_text(
    json.dumps(bad_abstention_count, indent=2) + "\n", encoding="utf-8"
)
bad_condition = copy.deepcopy(contract)
bad_condition["conditions"].append(
    {"condition_id": "session_bootstrap", "capture": "session_bootstrap"}
)
(data / "contract.extra-condition.json").write_text(
    json.dumps(bad_condition, indent=2) + "\n", encoding="utf-8"
)

spec = json.loads((data / "spec.json").read_text(encoding="utf-8"))
bad_digest_spec = copy.deepcopy(spec)
bad_digest_spec["digest_key"] = "syn_01"
(data / "spec.bad-digest.json").write_text(
    json.dumps(bad_digest_spec, indent=2) + "\n", encoding="utf-8"
)

sys.path.insert(0, str(data.parent / "scripts/eval"))
import portfolio_continuity_ab_trial as surface

capture = json.loads((data / "capture.raw.json").read_text(encoding="utf-8"))
for case in capture["cases"]:
    row = case["conditions"]["portfolio_digest"]
    record = copy.deepcopy(row["raw_result"])
    record["key"] = "syn_01"
    context = json.dumps(record, ensure_ascii=False)
    row["raw_result"] = record
    row["context"] = context
    row["context_sha256"] = hashlib.sha256(context.encode()).hexdigest()
    row["context_bytes"] = len(context.encode())
    row["context_tokens_estimate"] = surface.estimate_tokens(context)
(data / "capture.bad-digest.json").write_text(
    json.dumps(capture, indent=2) + "\n", encoding="utf-8"
)
PY

if python3 "$v1adapter" score \
  --contract "$v1repo/answer-contract.json" \
  --capture "$v1data/capture.raw.json" \
  --generation "$v1data/does-not-exist-generation.json" \
  --blind-packet "$v1data/blind.packet.json" \
  --blind-map "$v1data/does-not-exist-map.json" \
  --review "$v1data/review.1.json" \
  --output "$v1data/score.missing-review.json" \
  >"$tmpdir/v1-missing-review.stdout" 2>"$tmpdir/v1-missing-review.stderr"; then
  echo "v1 score with one review unexpectedly passed" >&2
  exit 1
fi

if python3 "$v1adapter" score \
  --contract "$v1repo/answer-contract.json" \
  --capture "$v1data/capture.raw.json" \
  --generation "$v1data/does-not-exist-generation.json" \
  --blind-packet "$v1data/blind.packet.json" \
  --blind-map "$v1data/does-not-exist-map.json" \
  --review "$v1data/review.1.json" \
  --review "$v1data/review.incomplete.json" \
  --output "$v1data/score.incomplete-review.json" \
  >"$tmpdir/v1-incomplete-review.stdout" 2>"$tmpdir/v1-incomplete-review.stderr"; then
  echo "v1 score with incomplete second review unexpectedly passed" >&2
  exit 1
fi

if python3 "$v1adapter" score \
  --contract "$v1repo/answer-contract.json" \
  --capture "$v1data/capture.raw.json" \
  --generation "$v1data/does-not-exist-generation.json" \
  --blind-packet "$v1data/blind.packet.json" \
  --blind-map "$v1data/does-not-exist-map.json" \
  --review "$v1data/review.1.json" \
  --review "$v1data/review.duplicate.json" \
  --output "$v1data/score.duplicate-reviewer.json" \
  >"$tmpdir/v1-duplicate.stdout" 2>"$tmpdir/v1-duplicate.stderr"; then
  echo "v1 score with duplicate reviewer unexpectedly passed" >&2
  exit 1
fi

if python3 "$v1adapter" score \
  --contract "$v1repo/answer-contract.json" \
  --capture "$v1data/capture.raw.json" \
  --generation "$v1data/does-not-exist-generation.json" \
  --blind-packet "$v1data/blind.packet.json" \
  --blind-map "$v1data/does-not-exist-map.json" \
  --review "$v1data/review.1.json" \
  --review "$v1data/review.bad-abstention-field.json" \
  --output "$v1data/score.bad-abstention-field.json" \
  >"$tmpdir/v1-bad-abstention-field.stdout" \
  2>"$tmpdir/v1-bad-abstention-field.stderr"; then
  echo "v1 non-abstention answer with abstention_pass unexpectedly passed" >&2
  exit 1
fi

python3 "$v1adapter" score \
  --contract "$v1repo/answer-contract.json" \
  --capture "$v1data/capture.raw.json" \
  --generation "$v1data/generation.raw.json" \
  --blind-packet "$v1data/blind.packet.json" \
  --blind-map "$v1data/blind.map.json" \
  --review "$v1data/review.1.json" \
  --review "$v1data/review.abstention-fail.json" \
  --output "$v1data/score.abstention-fail.json" \
  >"$tmpdir/v1-abstention-fail.stdout.json"

python3 "$v1adapter" score \
  --contract "$v1repo/answer-contract.json" \
  --capture "$v1data/capture.raw.json" \
  --generation "$v1data/generation.raw.json" \
  --blind-packet "$v1data/blind.packet.json" \
  --blind-map "$v1data/blind.map.json" \
  --review "$v1data/review.1.json" \
  --review "$v1data/review.disagreement.json" \
  --output "$v1data/score.disagreement.json" \
  >"$tmpdir/v1-disagreement.stdout.json"

for bad_contract in \
  contract.bad-stratum.json \
  contract.bad-abstention-count.json \
  contract.extra-condition.json; do
  if python3 "$v1adapter" validate-contract \
    --contract "$v1data/$bad_contract" \
    >"$tmpdir/$bad_contract.stdout" 2>"$tmpdir/$bad_contract.stderr"; then
    echo "invalid v1 matrix contract unexpectedly passed: $bad_contract" >&2
    exit 1
  fi
done

if python3 "$v1adapter" capture \
  --contract "$v1repo/answer-contract.json" \
  --spec "$v1data/spec.bad-digest.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$v1data/capture.bad-digest-spec.json" \
  --redacted-output "$v1data/capture.bad-digest-spec.redacted.json" \
  >"$tmpdir/v1-bad-digest-spec.stdout" 2>"$tmpdir/v1-bad-digest-spec.stderr"; then
  echo "v1 spec with wrong digest key unexpectedly passed" >&2
  exit 1
fi

if python3 "$v1adapter" generate \
  --contract "$v1repo/answer-contract.json" \
  --spec "$v1data/spec.json" \
  --capture "$v1data/capture.bad-digest.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v1data/generation.bad-digest.json" \
  --blind-output "$v1data/blind.bad-digest.json" \
  --map-output "$v1data/map.bad-digest.json" \
  --review-template-output "$v1data/review.bad-digest.json" \
  --redacted-output "$v1data/generation.bad-digest.redacted.json" \
  >"$tmpdir/v1-bad-digest-capture.stdout" \
  2>"$tmpdir/v1-bad-digest-capture.stderr"; then
  echo "v1 capture with wrong digest key unexpectedly passed" >&2
  exit 1
fi

python3 - "$v1data" "$EXPANDED_CONTRACT" "$EXPANDED_REPORT" "$ADAPTER" "$tmpdir" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

data = Path(sys.argv[1])
contract_path = Path(sys.argv[2])
report_path = Path(sys.argv[3])
adapter_path = Path(sys.argv[4])
tmp = Path(sys.argv[5])

contract = json.loads(contract_path.read_text(encoding="utf-8"))
report = report_path.read_text(encoding="utf-8")
source_sha = hashlib.sha256(adapter_path.read_bytes()).hexdigest()
contract_sha = hashlib.sha256(contract_path.read_bytes()).hexdigest()
assert contract["harness_source_sha256"] == (
    "60dd2130f6e4af976e594dec284ae38c46c63b437a7f3080d5eb5f41369973a5"
)
assert contract["harness_source_sha256"] != source_sha
assert len(contract["cases"]) == 12
assert sum(case["requires_abstention"] for case in contract["cases"]) == 2
assert contract_sha in report
assert contract["harness_source_sha256"] in report

capture = json.loads((data / "capture.redacted.json").read_text(encoding="utf-8"))
generation = json.loads(
    (data / "generation.redacted.json").read_text(encoding="utf-8")
)
blind = json.loads((data / "blind.packet.json").read_text(encoding="utf-8"))
review_template = json.loads(
    (data / "review.template.json").read_text(encoding="utf-8")
)
score = json.loads((data / "score.json").read_text(encoding="utf-8"))
empty_capture = json.loads(
    (data / "capture.empty-reference.redacted.json").read_text(encoding="utf-8")
)
empty_generation = json.loads(
    (data / "generation.empty-reference.redacted.json").read_text(encoding="utf-8")
)
abstention_fail = json.loads(
    (data / "score.abstention-fail.json").read_text(encoding="utf-8")
)
disagreement = json.loads(
    (data / "score.disagreement.json").read_text(encoding="utf-8")
)

assert capture["case_count"] == 12
assert capture["condition_run_count"] == 24
assert all(not case["ranking_projection_invariant"] for case in capture["cases"])
assert generation["case_count"] == 12
assert generation["condition_count"] == 2
assert generation["answer_count"] == 24
assert generation["status"] == "WAIT_TWO_BLIND_REVIEWS"
assert all(
    case["conditions"]["hybrid_retrieval"]["observed_items"] == 0
    for case in empty_capture["cases"]
)
assert empty_capture["condition_run_count"] == 24
assert empty_generation["answer_count"] == 24
assert empty_generation["status"] == "WAIT_TWO_BLIND_REVIEWS"
assert blind["boundary"]["required_reviewer_count"] == 2
assert review_template["independent_review"] is False
assert review_template["condition_blinded"] is False

assert score["status"] == "READY_TO_PREREGISTER_WRITE_SIDE_TRIAL"
assert score["global"]["reviewer_count"] == 2
assert score["global"]["stratum_count"] == 6
assert score["global"]["advance"] is True
assert score["global"]["recommend_write_side_preregistration"] is True
assert len(score["per_reviewer"]) == 2
assert all(row["all_strata_gate_pass"] for row in score["per_reviewer"].values())
assert all(row["all_reviewers_gate_pass"] for row in score["per_stratum"].values())
assert score["boundary"]["pooled_reviewer_mean_used_for_gate"] is False
assert score["boundary"]["runtime_promotion_allowed"] is False
assert score["boundary"]["automatic_digest_regeneration_allowed"] is False
assert score["boundary"]["compact_default_change_allowed"] is False
assert score["boundary"]["version_or_tag_change_allowed"] is False
assert score["boundary"]["release_action_allowed"] is False
assert score["boundary"]["ci_action_allowed"] is False

assert abstention_fail["status"] == "NO_ADVANCE"
assert abstention_fail["global"]["advance"] is False
assert abstention_fail["global"]["all_abstention_pass"] is False
assert disagreement["status"] == "NO_ADVANCE"
assert disagreement["global"]["advance"] is False
assert not all(
    row["all_reviewers_gate_pass"] for row in disagreement["per_stratum"].values()
)

blind_text = (data / "blind.packet.json").read_text(encoding="utf-8")
review_text = (data / "review.template.json").read_text(encoding="utf-8")
for condition in ["hybrid_retrieval", "portfolio_digest"]:
    assert condition not in blind_text
    assert condition not in review_text
for safe_path in [
    data / "capture.redacted.json",
    data / "generation.redacted.json",
    data / "score.json",
    tmp / "v1-capture.stdout.json",
    tmp / "v1-generate.stdout.json",
    tmp / "v1-score.stdout.json",
]:
    text = safe_path.read_text(encoding="utf-8")
    for private in [
        "Synthetic expanded question",
        "Synthetic evidence row",
        "Synthetic grounded project answer",
        "ans_",
        "synthetic-reviewer-alpha",
        "synthetic-reviewer-bravo",
    ]:
        assert private not in text, (safe_path, private)

assert "exactly 2 --review" in (tmp / "v1-missing-review.stderr").read_text(
    encoding="utf-8"
)
incomplete_error = (tmp / "v1-incomplete-review.stderr").read_text(encoding="utf-8")
assert "must be populated" in incomplete_error
assert "does-not-exist" not in incomplete_error
duplicate_error = (tmp / "v1-duplicate.stderr").read_text(encoding="utf-8")
assert "distinct reviewer identities" in duplicate_error
assert "does-not-exist" not in duplicate_error
assert "unsupported field" in (
    tmp / "v1-bad-abstention-field.stderr"
).read_text(encoding="utf-8")
assert "digest_key does not match" in (
    tmp / "v1-bad-digest-spec.stderr"
).read_text(encoding="utf-8")
assert "digest key does not match" in (
    tmp / "v1-bad-digest-capture.stderr"
).read_text(encoding="utf-8")

required_report = [
    "# Portfolio Continuity Expanded Answer Trial Preregistration",
    "PRE-REGISTERED AT CONTRACT COMMIT / NOT EXECUTED",
    "case_count: 12",
    "reviewer_count: 2",
    "max_abstention_failures: 0",
    "write_side_trial_only",
    "READY_TO_PREREGISTER_WRITE_SIDE_TRIAL",
    "WAIT_TWO_BLIND_REVIEWS",
    "runtime_promotion_allowed: false",
]
missing = [needle for needle in required_report if needle not in report]
if missing:
    raise SystemExit("missing expanded report anchors: " + ", ".join(missing))

print("Portfolio continuity expanded blinded answer trial verification passed")
PY

python3 - "$v1repo" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

repo = Path(sys.argv[1])
contract_path = repo / "answer-contract.json"
contract = json.loads(contract_path.read_text(encoding="utf-8"))
contract["contract_id"] = "synthetic_expanded_answer_trial_dirty"
contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
spec = json.loads((repo / "data/spec.json").read_text(encoding="utf-8"))
spec["contract_sha256"] = hashlib.sha256(contract_path.read_bytes()).hexdigest()
(repo / "data/spec.dirty-contract.json").write_text(
    json.dumps(spec, indent=2) + "\n", encoding="utf-8"
)
PY

if python3 "$v1adapter" capture \
  --contract "$v1repo/answer-contract.json" \
  --spec "$v1data/spec.dirty-contract.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$v1data/capture.dirty-contract.json" \
  --redacted-output "$v1data/capture.dirty-contract.redacted.json" \
  >"$tmpdir/v1-dirty-contract.stdout" 2>"$tmpdir/v1-dirty-contract.stderr"; then
  echo "dirty v1 contract unexpectedly passed capture" >&2
  exit 1
fi
git -C "$v1repo" show HEAD:answer-contract.json >"$v1repo/answer-contract.json"

cp "$v1repo/answer-contract.json" "$v1data/untracked-contract.json"
python3 - "$v1data" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

data = Path(sys.argv[1])
spec = json.loads((data / "spec.json").read_text(encoding="utf-8"))
spec["contract_sha256"] = hashlib.sha256(
    (data / "untracked-contract.json").read_bytes()
).hexdigest()
(data / "spec.untracked-contract.json").write_text(
    json.dumps(spec, indent=2) + "\n", encoding="utf-8"
)
PY
if python3 "$v1adapter" capture \
  --contract "$v1data/untracked-contract.json" \
  --spec "$v1data/spec.untracked-contract.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$v1data/capture.untracked-contract.json" \
  --redacted-output "$v1data/capture.untracked-contract.redacted.json" \
  >"$tmpdir/v1-untracked-contract.stdout" \
  2>"$tmpdir/v1-untracked-contract.stderr"; then
  echo "untracked v1 contract unexpectedly passed capture" >&2
  exit 1
fi

printf '\n# verifier dirty harness\n' >>"$v1adapter"
if python3 "$v1adapter" validate-contract \
  --contract "$v1repo/answer-contract.json" \
  >"$tmpdir/v1-dirty-harness.stdout" 2>"$tmpdir/v1-dirty-harness.stderr"; then
  echo "dirty v1 harness unexpectedly passed validation" >&2
  exit 1
fi
git -C "$v1repo" show HEAD:scripts/eval/portfolio_continuity_answer_trial.py \
  >"$v1adapter"
chmod +x "$v1adapter"

printf '\n# verifier dirty surface helper\n' >>"$v1surface"
if python3 "$v1adapter" validate-contract \
  --contract "$v1repo/answer-contract.json" \
  >"$tmpdir/v1-dirty-surface.stdout" 2>"$tmpdir/v1-dirty-surface.stderr"; then
  echo "dirty v1 surface helper unexpectedly passed validation" >&2
  exit 1
fi
git -C "$v1repo" show HEAD:scripts/eval/portfolio_continuity_ab_trial.py \
  >"$v1surface"

python3 - "$v1data" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

data = Path(sys.argv[1])

def render(value):
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

blind = json.loads((data / "blind.packet.json").read_text(encoding="utf-8"))
blind["cases"][0]["answers"].reverse()
blind_bytes = render(blind)
(data / "blind.synced-reorder.json").write_bytes(blind_bytes)
blind_sha = hashlib.sha256(blind_bytes).hexdigest()

mapping = json.loads((data / "blind.map.json").read_text(encoding="utf-8"))
mapping["blind_packet_sha256"] = blind_sha
mapping["cases"][0]["answers"].reverse()
(data / "map.synced-reorder.json").write_bytes(render(mapping))

for index in (1, 2):
    review = json.loads((data / f"review.{index}.json").read_text(encoding="utf-8"))
    review["blind_packet_sha256"] = blind_sha
    (data / f"review.synced-reorder.{index}.json").write_bytes(render(review))
PY

if python3 "$v1adapter" score \
  --contract "$v1repo/answer-contract.json" \
  --capture "$v1data/capture.raw.json" \
  --generation "$v1data/generation.raw.json" \
  --blind-packet "$v1data/blind.synced-reorder.json" \
  --blind-map "$v1data/map.synced-reorder.json" \
  --review "$v1data/review.synced-reorder.1.json" \
  --review "$v1data/review.synced-reorder.2.json" \
  --output "$v1data/score.synced-reorder.json" \
  >"$tmpdir/v1-synced-reorder.stdout" 2>"$tmpdir/v1-synced-reorder.stderr"; then
  echo "synchronously reordered blind packet/map unexpectedly passed" >&2
  exit 1
fi

spec_sha_before="$(sha256sum "$v1data/spec.json" | cut -d' ' -f1)"
ln "$v1data/spec.json" "$v1data/capture-spec-output-alias.json"
if python3 "$v1adapter" capture \
  --contract "$v1repo/answer-contract.json" \
  --spec "$v1data/spec.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$v1data/capture-spec-output-alias.json" \
  --redacted-output "$v1data/capture-spec-output-alias.redacted.json" \
  >"$tmpdir/v1-capture-spec-alias.stdout" \
  2>"$tmpdir/v1-capture-spec-alias.stderr"; then
  echo "capture output hardlinked to spec unexpectedly passed" >&2
  exit 1
fi
rm "$v1data/capture-spec-output-alias.json"
test "$(sha256sum "$v1data/spec.json" | cut -d' ' -f1)" = "$spec_sha_before"

contract_sha_before="$(sha256sum "$v1repo/answer-contract.json" | cut -d' ' -f1)"
ln "$v1repo/answer-contract.json" "$v1data/generation-contract-output-alias.json"
if python3 "$v1adapter" generate \
  --contract "$v1repo/answer-contract.json" \
  --spec "$v1data/spec.json" \
  --capture "$v1data/capture.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v1data/generation-contract-output-alias.json" \
  --blind-output "$v1data/blind.contract-alias.json" \
  --map-output "$v1data/map.contract-alias.json" \
  --review-template-output "$v1data/review.contract-alias.json" \
  --redacted-output "$v1data/generation.contract-alias.redacted.json" \
  >"$tmpdir/v1-generate-contract-alias.stdout" \
  2>"$tmpdir/v1-generate-contract-alias.stderr"; then
  echo "generation output hardlinked to contract unexpectedly passed" >&2
  exit 1
fi
rm "$v1data/generation-contract-output-alias.json"
test "$(sha256sum "$v1repo/answer-contract.json" | cut -d' ' -f1)" = "$contract_sha_before"

harness_sha_before="$(sha256sum "$v1adapter" | cut -d' ' -f1)"
ln "$v1adapter" "$v1data/score-harness-output-alias.json"
if python3 "$v1adapter" score \
  --contract "$v1repo/answer-contract.json" \
  --capture "$v1data/capture.raw.json" \
  --generation "$v1data/generation.raw.json" \
  --blind-packet "$v1data/blind.packet.json" \
  --blind-map "$v1data/blind.map.json" \
  --review "$v1data/review.1.json" \
  --review "$v1data/review.2.json" \
  --output "$v1data/score-harness-output-alias.json" \
  >"$tmpdir/v1-score-harness-alias.stdout" \
  2>"$tmpdir/v1-score-harness-alias.stderr"; then
  echo "score output hardlinked to harness unexpectedly passed" >&2
  exit 1
fi
rm "$v1data/score-harness-output-alias.json"
test "$(sha256sum "$v1adapter" | cut -d' ' -f1)" = "$harness_sha_before"

python3 - "$tmpdir" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

tmp = Path(sys.argv[1])
data = tmp / "v1repo/data"
score = json.loads((data / "score.json").read_text(encoding="utf-8"))
abstention_fail = json.loads(
    (data / "score.abstention-fail.json").read_text(encoding="utf-8")
)
disagreement = json.loads(
    (data / "score.disagreement.json").read_text(encoding="utf-8")
)

assert score["schema"] == "agent_bridge.portfolio_continuity_answer_score.v1"
assert score["status"] == "READY_TO_PREREGISTER_WRITE_SIDE_TRIAL"
assert score["global"]["recommend_write_side_preregistration"] is True
assert score["global"]["all_reviewer_global_gates_pass"] is True
assert score["global"]["all_reviewer_stratum_gates_pass"] is True
assert set(score["per_reviewer"]) == {"reviewer_1", "reviewer_2"}
assert set(score["per_stratum"]) == {
    "portfolio_status",
    "portfolio_retrospective",
    "portfolio_planning",
    "dependency_risk",
    "stale_state",
    "cross_project_conflict",
}
assert all(row["case_count"] == 2 for row in score["per_stratum"].values())
assert score["boundary"]["pooled_reviewer_mean_used_for_gate"] is False
assert score["boundary"]["reviewer_identity_in_output"] is False
assert score["boundary"]["release_action_allowed"] is False
assert score["boundary"]["ci_action_allowed"] is False

assert abstention_fail["status"] == "NO_ADVANCE"
assert abstention_fail["global"]["all_abstention_pass"] is False
assert any(
    reviewer["global"]["abstention_failures"] > 0
    for reviewer in abstention_fail["per_reviewer"].values()
)
assert disagreement["status"] == "NO_ADVANCE"
assert disagreement["global"]["all_abstention_pass"] is True
assert disagreement["global"]["all_reviewer_stratum_gates_pass"] is False

for path in [
    data / "score.json",
    data / "score.swapped.json",
    data / "score.abstention-fail.json",
    data / "score.disagreement.json",
    tmp / "v1-score.stdout.json",
]:
    text = path.read_text(encoding="utf-8")
    for private in [
        "Synthetic expanded question",
        "Synthetic grounded project answer",
        "ans_",
        "synthetic-reviewer-alpha",
        "synthetic-reviewer-bravo",
        hashlib.sha256(b"synthetic-reviewer-alpha").hexdigest(),
        hashlib.sha256(b"synthetic-reviewer-bravo").hexdigest(),
        "reviewer_sha256",
    ]:
        assert private not in text, (path, private)

assert "exactly 2 --review" in (
    tmp / "v1-missing-review.stderr"
).read_text(encoding="utf-8")
assert "claim score must be populated" in (
    tmp / "v1-incomplete-review.stderr"
).read_text(encoding="utf-8")
assert "distinct reviewer identities" in (
    tmp / "v1-duplicate.stderr"
).read_text(encoding="utf-8")
assert "unsupported field" in (
    tmp / "v1-bad-abstention-field.stderr"
).read_text(encoding="utf-8")
assert "leaked a condition/evidence marker" in (
    tmp / "v1-key-leak.stderr"
).read_text(encoding="utf-8")
assert "fixed prompt strata" in (
    tmp / "contract.bad-stratum.json.stderr"
).read_text(encoding="utf-8")
assert "exactly two abstention cases" in (
    tmp / "contract.bad-abstention-count.json.stderr"
).read_text(encoding="utf-8")
assert "fixed condition order" in (
    tmp / "contract.extra-condition.json.stderr"
).read_text(encoding="utf-8")
assert "digest_key" in (
    tmp / "v1-bad-digest-spec.stderr"
).read_text(encoding="utf-8")
assert "digest key" in (
    tmp / "v1-bad-digest-capture.stderr"
).read_text(encoding="utf-8")
assert "bytes differ" in (
    tmp / "v1-dirty-contract.stderr"
).read_text(encoding="utf-8")
assert "not tracked" in (
    tmp / "v1-untracked-contract.stderr"
).read_text(encoding="utf-8")
assert "harness source hash" in (
    tmp / "v1-dirty-harness.stderr"
).read_text(encoding="utf-8")
assert "surface helper source hash" in (
    tmp / "v1-dirty-surface.stderr"
).read_text(encoding="utf-8")
assert "too short or contains duplicates" in (
    tmp / "v1-capture-duplicate-ranking.stderr"
).read_text(encoding="utf-8")
assert "committed seed" in (
    tmp / "v1-synced-reorder.stderr"
).read_text(encoding="utf-8")
for name in [
    "v1-capture-spec-alias.stderr",
    "v1-generate-contract-alias.stderr",
    "v1-score-harness-alias.stderr",
]:
    assert "file identities must be distinct" in (tmp / name).read_text(
        encoding="utf-8"
    )

print("Portfolio continuity expanded answer trial v1 verification passed")
PY

# Exercise the successor v2 projection, coverage, receipt, and retry protocol.
v2repo="$tmpdir/v2repo"
mkdir -p "$v2repo/scripts/eval" "$v2repo/data"
cp "$ADAPTER" "$v2repo/scripts/eval/portfolio_continuity_answer_trial.py"
cp "$ROOT_DIR/scripts/eval/portfolio_continuity_ab_trial.py" \
  "$v2repo/scripts/eval/portfolio_continuity_ab_trial.py"
printf 'data/\n' >"$v2repo/.gitignore"

python3 - "$v2repo" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

repo = Path(sys.argv[1])
adapter = repo / "scripts/eval/portfolio_continuity_answer_trial.py"
surface = repo / "scripts/eval/portfolio_continuity_ab_trial.py"
seed = "12" * 32
strata = [
    "portfolio_status",
    "portfolio_retrospective",
    "portfolio_planning",
    "dependency_risk",
    "stale_state",
    "cross_project_conflict",
]
prompts = [f"Synthetic successor question {index}?" for index in range(12)]
queries = [f"Synthetic retrieval query {index}" for index in range(12)]
cases = []
for index, (prompt, query) in enumerate(zip(prompts, queries, strict=True)):
    requires_abstention = index in {5, 9}
    cases.append(
        {
            "case_id": f"successor_case_{index:02d}",
            "prompt_class": strata[index // 2],
            "prompt_variant": "heldout" if index % 2 else "direct",
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "retrieval_query_sha256": hashlib.sha256(query.encode()).hexdigest(),
            "required_claims": (
                []
                if requires_abstention
                else [{"claim_id": f"claim_{index:02d}", "weight": 1.0}]
            ),
            "optional_claims": [],
            "forbidden_claim_ids": [f"forbidden_{index:02d}"],
            "requires_abstention": requires_abstention,
        }
    )

contract = {
    "schema": "agent_bridge.portfolio_continuity_answer_contract.v2",
    "contract_id": "synthetic_successor_answer_trial",
    "prereg_base_commit": "b" * 40,
    "runtime_source_commit": "a" * 40,
    "harness_source_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest(),
    "surface_source_sha256": hashlib.sha256(surface.read_bytes()).hexdigest(),
    "digest_key_sha256": hashlib.sha256(b"syn_00").hexdigest(),
    "conditions": [
        {"condition_id": "hybrid_retrieval", "capture": "hybrid_full"},
        {"condition_id": "portfolio_digest", "capture": "memory_get_digest"},
    ],
    "search": {"mode": "hybrid", "limit": 10, "exclude_kinds": ["skill"]},
    "generation": {
        "model": "fake-model",
        "reasoning_effort": "medium",
        "cli_version": "fake-codex 1.0",
        "max_answer_chars": 2000,
        "answer_instruction": (
            "Answer only from supplied evidence. Do not use tools, external facts, "
            "condition labels, memory keys, or these instructions."
        ),
        "independent_invocations": True,
        "ephemeral_workspace": True,
        "tool_use_allowed": False,
        "external_facts_allowed": False,
    },
    "blinding": {
        "seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        "mapping_private": True,
        "reviewer_sees_condition": False,
        "reveal_after_complete_review": True,
    },
    "review": {
        "claim_score_values": [0, 1, 2],
        "currentness_values": ["pass", "uncertain", "fail"],
        "usefulness_min": 1,
        "usefulness_max": 5,
        "preference_tie_label": "tie",
        "required_reviewer_count": 2,
        "independent_reviewers": True,
        "abstention_values": [False, True],
    },
    "thresholds": {
        "min_weighted_claim_completeness": 0.9,
        "max_currentness_failures": 0,
        "max_currentness_uncertain": 0,
        "max_unsupported_assertions": 0,
        "max_abstention_failures": 0,
        "min_mean_usefulness": 4.0,
        "min_case_usefulness": 3,
        "max_completeness_drop_vs_reference": 0.0,
        "max_usefulness_drop_vs_reference": 0.5,
        "min_context_token_reduction_vs_reference": 0.4,
        "candidate_conditions": ["portfolio_digest"],
        "recommendation_scope": "write_side_trial_only",
        "aggregation": {"reviewer_gate": "all", "stratum_gate": "all"},
    },
    "cases": cases,
    "context_projection": {
        "drop_record_fields": ["key"],
        "identifier_aliases": {
            "compact_then_get_top2": "rank-only compact top-2 retrieval",
            "hybrid_retrieval": "full hybrid retrieval",
            "portfolio_digest": "direct portfolio digest",
            "portfolio_state_digest": "portfolio digest record",
            "session_bootstrap": "session bootstrap",
        },
        "answer_postprocessing_allowed": False,
    },
    "coverage": {
        "min_reference_hits_non_abstention": 2,
        "min_reference_hits_abstention": 0,
        "require_unique_reference_keys": True,
        "generation_requires_status": "VALID",
    },
    "retry_policy": {
        "pre_model_full_restart_limit": 1,
        "post_model_retry_limit": 0,
        "semantic_retry_limit": 0,
        "automatic_retry": False,
    },
    "failure_receipt": {
        "private": True,
        "atomic_write": True,
        "raw_material_allowed": False,
    },
    "boundaries": {
        "raw_artifacts_in_git": False,
        "writes_live_ab_store": False,
        "llm_judge": False,
        "automatic_unblinding": False,
        "runtime_promotion_allowed": False,
        "automatic_digest_regeneration_allowed": False,
        "compact_default_change_allowed": False,
        "benchmark_claim_allowed": False,
        "version_or_tag_change_allowed": False,
        "release_action_allowed": False,
        "ci_action_allowed": False,
        "answer_postprocessing_allowed": False,
        "ad_hoc_retry_allowed": False,
    },
}
for filename, contract_variant in {
    "answer-contract.json": contract,
    "answer-contract.coverage.json": {
        **contract,
        "contract_id": "synthetic_successor_answer_coverage",
    },
    "answer-contract.semantic.json": {
        **contract,
        "contract_id": "synthetic_successor_answer_semantic",
    },
}.items():
    (repo / filename).write_text(
        json.dumps(contract_variant, indent=2) + "\n", encoding="utf-8"
    )
PY

git -C "$v2repo" init -q
git -C "$v2repo" config user.email synthetic@example.invalid
git -C "$v2repo" config user.name Synthetic
git -C "$v2repo" add .gitignore answer-contract*.json scripts/eval
git -C "$v2repo" commit -qm 'synthetic v2 contract and harness'

python3 - "$v2repo" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1])
contract_path = repo / "answer-contract.json"
prompts = [f"Synthetic successor question {index}?" for index in range(12)]
queries = [f"Synthetic retrieval query {index}" for index in range(12)]
head = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=repo, text=True
).strip()


def make_spec(contract_file: str, trial_id: str) -> dict[str, object]:
    contract = json.loads((repo / contract_file).read_text(encoding="utf-8"))
    return {
        "schema": "agent_bridge.portfolio_continuity_answer_spec.v2",
        "trial_id": trial_id,
        "contract_sha256": hashlib.sha256((repo / contract_file).read_bytes()).hexdigest(),
        "contract_commit": head,
        "repo": str(repo),
        "digest_key": "syn_00",
        "blind_seed": "12" * 32,
        "cases": [
            {
                "case_id": case["case_id"],
                "prompt": prompt,
                "retrieval_query": query,
            }
            for case, prompt, query in zip(
                contract["cases"], prompts, queries, strict=True
            )
        ],
    }


spec = make_spec("answer-contract.json", "synthetic_successor_run")
(repo / "data/spec.json").write_text(
    json.dumps(spec, indent=2) + "\n", encoding="utf-8"
)
invalid_coverage_spec = make_spec(
    "answer-contract.coverage.json", "synthetic_successor_invalid_coverage"
)
(repo / "data/spec.invalid-coverage.json").write_text(
    json.dumps(invalid_coverage_spec, indent=2) + "\n", encoding="utf-8"
)
semantic_spec = make_spec(
    "answer-contract.semantic.json", "synthetic_successor_semantic_failure"
)
semantic_bytes = (json.dumps(semantic_spec, indent=2) + "\n").encode("utf-8")
(repo / "data/spec.semantic.json").write_bytes(semantic_bytes)
# This is semantically identical JSON with only trailing JSON whitespace changed.
(repo / "data/spec.semantic-whitespace.json").write_bytes(semantic_bytes + b" \n")
PY

v2adapter="$v2repo/scripts/eval/portfolio_continuity_answer_trial.py"
v2data="$v2repo/data"
python3 "$v2adapter" validate-contract \
  --contract "$v2repo/answer-contract.json" \
  >"$tmpdir/v2-contract.stdout.json"
python3 "$v2adapter" validate-contract \
  --contract "$v2repo/answer-contract.coverage.json" \
  >"$tmpdir/v2-coverage-contract.stdout.json"
python3 "$v2adapter" validate-contract \
  --contract "$v2repo/answer-contract.semantic.json" \
  >"$tmpdir/v2-semantic-contract.stdout.json"
FAKE_INTERNAL_IDENTIFIERS=1 FAKE_REQUIRE_RETRIEVAL_QUERY=1 \
  python3 "$v2adapter" capture \
  --contract "$v2repo/answer-contract.json" \
  --spec "$v2data/spec.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$v2data/capture.raw.json" \
  --redacted-output "$v2data/capture.redacted.json" \
  >"$tmpdir/v2-capture.stdout.json"

FAKE_INTERNAL_IDENTIFIERS=1 FAKE_REQUIRE_RETRIEVAL_QUERY=1 \
  FAKE_EMPTY_FULL_SEARCH=1 python3 "$v2adapter" capture \
  --contract "$v2repo/answer-contract.coverage.json" \
  --spec "$v2data/spec.invalid-coverage.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$v2data/capture.invalid-coverage.raw.json" \
  --redacted-output "$v2data/capture.invalid-coverage.redacted.json" \
  >"$tmpdir/v2-invalid-capture.stdout.json"

FAKE_INTERNAL_IDENTIFIERS=1 FAKE_REQUIRE_RETRIEVAL_QUERY=1 \
  python3 "$v2adapter" capture \
  --contract "$v2repo/answer-contract.semantic.json" \
  --spec "$v2data/spec.semantic.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$v2data/capture.semantic.raw.json" \
  --redacted-output "$v2data/capture.semantic.redacted.json" \
  >"$tmpdir/v2-semantic-capture.stdout.json"

if FAKE_CODEX_COUNT_FILE="$tmpdir/v2-coverage-count" python3 "$v2adapter" generate \
  --contract "$v2repo/answer-contract.coverage.json" \
  --spec "$v2data/spec.invalid-coverage.json" \
  --capture "$v2data/capture.invalid-coverage.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v2data/coverage.generation.json" \
  --blind-output "$v2data/coverage.blind.json" \
  --map-output "$v2data/coverage.map.json" \
  --review-template-output "$v2data/coverage.review.json" \
  --redacted-output "$v2data/coverage.redacted.json" \
  --failure-output "$v2data/coverage.failure.json" \
  >"$tmpdir/v2-coverage.stdout" 2>"$tmpdir/v2-coverage.stderr"; then
  echo "v2 invalid coverage unexpectedly reached generation" >&2
  exit 1
fi

if FAKE_WRONG_CODEX_VERSION=1 \
  FAKE_CODEX_COUNT_FILE="$tmpdir/v2-identity-count" \
  python3 "$v2adapter" generate \
  --contract "$v2repo/answer-contract.json" \
  --spec "$v2data/spec.json" \
  --capture "$v2data/capture.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v2data/identity.generation.json" \
  --blind-output "$v2data/identity.blind.json" \
  --map-output "$v2data/identity.map.json" \
  --review-template-output "$v2data/identity.review.json" \
  --redacted-output "$v2data/identity.redacted.json" \
  --failure-output "$v2data/identity.failure.json" \
  >"$tmpdir/v2-identity.stdout" 2>"$tmpdir/v2-identity.stderr"; then
  echo "v2 wrong Codex identity unexpectedly passed" >&2
  exit 1
fi

FAKE_CODEX_PADDED_ANSWER=1 \
  FAKE_CODEX_COUNT_FILE="$tmpdir/v2-retry-count" \
  python3 "$v2adapter" generate \
  --contract "$v2repo/answer-contract.json" \
  --spec "$v2data/spec.json" \
  --capture "$v2data/capture.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v2data/retry.generation.json" \
  --blind-output "$v2data/retry.blind.json" \
  --map-output "$v2data/retry.map.json" \
  --review-template-output "$v2data/retry.review-template.json" \
  --redacted-output "$v2data/retry.redacted.json" \
  --failure-output "$v2data/retry.failure.json" \
  --prior-failure-receipt "$v2data/identity.failure.json" \
  >"$tmpdir/v2-retry.stdout.json"

if FAKE_CODEX_COUNT_FILE="$tmpdir/v2-retry-count" \
  python3 "$v2adapter" generate \
  --contract "$v2repo/answer-contract.json" \
  --spec "$v2data/spec.json" \
  --capture "$v2data/capture.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v2data/replay.generation.json" \
  --blind-output "$v2data/replay.blind.json" \
  --map-output "$v2data/replay.map.json" \
  --review-template-output "$v2data/replay.review.json" \
  --redacted-output "$v2data/replay.redacted.json" \
  --failure-output "$v2data/replay.failure.json" \
  --prior-failure-receipt "$v2data/identity.failure.json" \
  >"$tmpdir/v2-replay.stdout" 2>"$tmpdir/v2-replay.stderr"; then
  echo "v2 retry authorization replay unexpectedly passed" >&2
  exit 1
fi

if FAKE_CODEX_MARKER_LEAK=1 \
  FAKE_CODEX_COUNT_FILE="$tmpdir/v2-semantic-count" \
  python3 "$v2adapter" generate \
  --contract "$v2repo/answer-contract.semantic.json" \
  --spec "$v2data/spec.semantic.json" \
  --capture "$v2data/capture.semantic.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v2data/semantic.generation.json" \
  --blind-output "$v2data/semantic.blind.json" \
  --map-output "$v2data/semantic.map.json" \
  --review-template-output "$v2data/semantic.review.json" \
  --redacted-output "$v2data/semantic.redacted.json" \
  --failure-output "$v2data/semantic.failure.json" \
  >"$tmpdir/v2-semantic.stdout" 2>"$tmpdir/v2-semantic.stderr"; then
  echo "v2 marker leak unexpectedly passed" >&2
  exit 1
fi

# A byte-only private-spec edit cannot reuse a capture from the original spec.
if FAKE_CODEX_COUNT_FILE="$tmpdir/v2-semantic-count" \
  python3 "$v2adapter" generate \
  --contract "$v2repo/answer-contract.semantic.json" \
  --spec "$v2data/spec.semantic-whitespace.json" \
  --capture "$v2data/capture.semantic.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v2data/semantic-byte-mismatch.generation.json" \
  --blind-output "$v2data/semantic-byte-mismatch.blind.json" \
  --map-output "$v2data/semantic-byte-mismatch.map.json" \
  --review-template-output "$v2data/semantic-byte-mismatch.review.json" \
  --redacted-output "$v2data/semantic-byte-mismatch.redacted.json" \
  --failure-output "$v2data/semantic-byte-mismatch.failure.json" \
  >"$tmpdir/v2-semantic-byte-mismatch.stdout" \
  2>"$tmpdir/v2-semantic-byte-mismatch.stderr"; then
  echo "v2 accepted a whitespace-mutated spec with the original capture" >&2
  exit 1
fi

# Recapturing that byte-only variant cannot create another attempt-one allowance.
FAKE_INTERNAL_IDENTIFIERS=1 FAKE_REQUIRE_RETRIEVAL_QUERY=1 \
  python3 "$v2adapter" capture \
  --contract "$v2repo/answer-contract.semantic.json" \
  --spec "$v2data/spec.semantic-whitespace.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$v2data/capture.semantic-whitespace.raw.json" \
  --redacted-output "$v2data/capture.semantic-whitespace.redacted.json" \
  >"$tmpdir/v2-semantic-whitespace-capture.stdout.json"

if FAKE_CODEX_COUNT_FILE="$tmpdir/v2-semantic-count" \
  python3 "$v2adapter" generate \
  --contract "$v2repo/answer-contract.semantic.json" \
  --spec "$v2data/spec.semantic-whitespace.json" \
  --capture "$v2data/capture.semantic-whitespace.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v2data/semantic-recapture.generation.json" \
  --blind-output "$v2data/semantic-recapture.blind.json" \
  --map-output "$v2data/semantic-recapture.map.json" \
  --review-template-output "$v2data/semantic-recapture.review.json" \
  --redacted-output "$v2data/semantic-recapture.redacted.json" \
  --failure-output "$v2data/semantic-recapture.failure.json" \
  >"$tmpdir/v2-semantic-recapture.stdout" \
  2>"$tmpdir/v2-semantic-recapture.stderr"; then
  echo "v2 semantic failure allowed recapture plus a fresh attempt one" >&2
  exit 1
fi

if FAKE_CODEX_COUNT_FILE="$tmpdir/v2-semantic-count" \
  python3 "$v2adapter" generate \
  --contract "$v2repo/answer-contract.semantic.json" \
  --spec "$v2data/spec.semantic.json" \
  --capture "$v2data/capture.semantic.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v2data/semantic-fresh.generation.json" \
  --blind-output "$v2data/semantic-fresh.blind.json" \
  --map-output "$v2data/semantic-fresh.map.json" \
  --review-template-output "$v2data/semantic-fresh.review.json" \
  --redacted-output "$v2data/semantic-fresh.redacted.json" \
  --failure-output "$v2data/semantic-fresh.failure.json" \
  >"$tmpdir/v2-semantic-fresh.stdout" \
  2>"$tmpdir/v2-semantic-fresh.stderr"; then
  echo "v2 semantic failure allowed a fresh attempt one" >&2
  exit 1
fi

if FAKE_CODEX_COUNT_FILE="$tmpdir/v2-semantic-count" \
  python3 "$v2adapter" generate \
  --contract "$v2repo/answer-contract.semantic.json" \
  --spec "$v2data/spec.semantic.json" \
  --capture "$v2data/capture.semantic.raw.json" \
  --codex-bin "$tmpdir/fake-codex" \
  --generation-output "$v2data/semantic-retry.generation.json" \
  --blind-output "$v2data/semantic-retry.blind.json" \
  --map-output "$v2data/semantic-retry.map.json" \
  --review-template-output "$v2data/semantic-retry.review.json" \
  --redacted-output "$v2data/semantic-retry.redacted.json" \
  --failure-output "$v2data/semantic-retry.failure.json" \
  --prior-failure-receipt "$v2data/semantic.failure.json" \
  >"$tmpdir/v2-semantic-retry.stdout" \
  2>"$tmpdir/v2-semantic-retry.stderr"; then
  echo "v2 semantic failure unexpectedly authorized retry" >&2
  exit 1
fi

python3 - "$v2data" <<'PY'
import json
import sys
from pathlib import Path

data = Path(sys.argv[1])
template = json.loads(
    (data / "retry.review-template.json").read_text(encoding="utf-8")
)
for index, reviewer in enumerate(("reviewer-alpha", "reviewer-bravo"), start=1):
    review = json.loads(json.dumps(template))
    review["reviewer"] = reviewer
    review["reviewed_at"] = 1_900_000_000 + index
    review["independent_review"] = True
    review["condition_blinded"] = True
    for case in review["cases"]:
        for answer in case["answers"]:
            for claim in answer["claim_scores"]:
                claim["score"] = 2
            answer["currentness"] = "pass"
            answer["unsupported_assertion_count"] = 0
            answer["usefulness"] = 4
            if "abstention_pass" in answer:
                answer["abstention_pass"] = True
        case["preferred_answer_id"] = "tie"
    (data / f"retry.review-{index}.json").write_text(
        json.dumps(review, indent=2) + "\n", encoding="utf-8"
    )
PY

python3 "$v2adapter" score \
  --contract "$v2repo/answer-contract.json" \
  --capture "$v2data/capture.raw.json" \
  --generation "$v2data/retry.generation.json" \
  --blind-packet "$v2data/retry.blind.json" \
  --blind-map "$v2data/retry.map.json" \
  --review "$v2data/retry.review-1.json" \
  --review "$v2data/retry.review-2.json" \
  --output "$v2data/retry.score.json" \
  >"$tmpdir/v2-score.stdout.json"

python3 - "$v2data" "$tmpdir" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

data = Path(sys.argv[1])
tmp = Path(sys.argv[2])
capture = json.loads((data / "capture.raw.json").read_text(encoding="utf-8"))
redacted = (data / "capture.redacted.json").read_text(encoding="utf-8")
redacted_capture = json.loads(redacted)
invalid_capture = json.loads(
    (data / "capture.invalid-coverage.raw.json").read_text(encoding="utf-8")
)
coverage_failure = json.loads(
    (data / "coverage.failure.json").read_text(encoding="utf-8")
)
identity_failure = json.loads(
    (data / "identity.failure.json").read_text(encoding="utf-8")
)
generation = json.loads(
    (data / "retry.generation.json").read_text(encoding="utf-8")
)
blind = json.loads((data / "retry.blind.json").read_text(encoding="utf-8"))
semantic_failure = json.loads(
    (data / "semantic.failure.json").read_text(encoding="utf-8")
)
semantic_capture = json.loads(
    (data / "capture.semantic.raw.json").read_text(encoding="utf-8")
)
semantic_whitespace_capture = json.loads(
    (data / "capture.semantic-whitespace.raw.json").read_text(encoding="utf-8")
)
score = json.loads((data / "retry.score.json").read_text(encoding="utf-8"))

assert capture["schema"].endswith(".v2")
assert capture["spec_sha256"] == hashlib.sha256((data / "spec.json").read_bytes()).hexdigest()
assert redacted_capture["spec_sha256"] == capture["spec_sha256"]
assert capture["coverage"]["status"] == "VALID"
assert all(row["pass"] for row in capture["coverage"]["cases"])
assert all(case["retrieval_query"] != case["prompt"] for case in capture["cases"])
sources = {
    "compact_then_get_top2",
    "hybrid_retrieval",
    "portfolio_digest",
    "portfolio_state_digest",
    "session_bootstrap",
}
for case in capture["cases"]:
    hybrid = case["conditions"]["hybrid_retrieval"]
    digest = case["conditions"]["portfolio_digest"]
    assert hybrid["raw_result"][0]["record"]["key"] == "syn_00"
    assert "portfolio_state_digest" in hybrid["raw_result"][0]["record"]["content"]
    for context in (hybrid["context"], digest["context"]):
        assert '"key"' not in context
        assert not any(source in context for source in sources)
    assert "portfolio digest record" in hybrid["context"]
assert "Synthetic successor question" not in redacted
assert "Synthetic retrieval query" not in redacted
assert "syn_00" not in redacted

assert invalid_capture["coverage"]["status"] == "INVALID_REFERENCE_COVERAGE"
assert invalid_capture["coverage"]["failed_case_count"] == 10
assert coverage_failure["error_code"] == "reference_coverage_invalid"
assert coverage_failure["retry_authorized"] is False
assert coverage_failure["any_model_started"] is False
assert not (tmp / "v2-coverage-count").exists()

assert identity_failure["phase"] == "pre_model_infrastructure"
assert identity_failure["error_code"] == "codex_identity_unavailable"
assert identity_failure["retry_authorized"] is True
assert identity_failure["retry_scope"] == "explicit_full_restart"
assert identity_failure["any_model_started"] is False
assert not (tmp / "v2-identity-count").exists()

assert generation["schema"].endswith(".v2")
assert generation["attempt"] == 2
assert generation["prior_failure_receipt_sha256"] == hashlib.sha256(
    (data / "identity.failure.json").read_bytes()
).hexdigest()
answers = [
    row["answer_markdown"]
    for case in generation["cases"]
    for row in case["answers"].values()
]
assert len(answers) == 24
assert all(answer.startswith("  ") and answer.endswith("  \n") for answer in answers)
assert int((tmp / "v2-retry-count").read_text(encoding="utf-8")) == 24
assert not (data / "retry.failure.json").exists()
assert not (data / "replay.failure.json").exists()
assert "already claimed" in (tmp / "v2-replay.stderr").read_text(encoding="utf-8")

assert blind["schema"].endswith(".v2")
assert all(
    answer["answer_markdown"].startswith("  ")
    for case in blind["cases"]
    for answer in case["answers"]
)
assert score["schema"].endswith(".v2")
assert score["global"]["reviewer_count"] == 2

assert semantic_failure["error_code"] == "answer_marker_leak"
assert semantic_failure["phase"] == "semantic_validation"
assert semantic_failure["model_started"] is True
assert semantic_failure["any_model_started"] is True
assert semantic_failure["retry_authorized"] is False
assert semantic_failure["answer_sha256"] == hashlib.sha256(
    b"hybrid_retrieval"
).hexdigest()
assert semantic_failure["matched_marker_sha256"] == hashlib.sha256(
    b"hybrid_retrieval"
).hexdigest()
assert semantic_capture["spec_sha256"] == hashlib.sha256(
    (data / "spec.semantic.json").read_bytes()
).hexdigest()
assert semantic_whitespace_capture["spec_sha256"] == hashlib.sha256(
    (data / "spec.semantic-whitespace.json").read_bytes()
).hexdigest()
assert semantic_capture["spec_sha256"] != semantic_whitespace_capture["spec_sha256"]
assert int((tmp / "v2-semantic-count").read_text(encoding="utf-8")) == 1
assert not (data / "semantic-byte-mismatch.failure.json").exists()
assert "private byte identity mismatch" in (
    tmp / "v2-semantic-byte-mismatch.stderr"
).read_text(encoding="utf-8")
assert not (data / "semantic-recapture.failure.json").exists()
assert "already claimed" in (
    tmp / "v2-semantic-recapture.stderr"
).read_text(encoding="utf-8")
assert not (data / "semantic-fresh.failure.json").exists()
assert "already claimed" in (
    tmp / "v2-semantic-fresh.stderr"
).read_text(encoding="utf-8")
assert not (data / "semantic-retry.failure.json").exists()
for path in (
    data / "coverage.failure.json",
    data / "identity.failure.json",
    data / "semantic.failure.json",
):
    assert path.stat().st_mode & 0o777 == 0o600
    text = path.read_text(encoding="utf-8")
    for private in (
        "Synthetic successor question",
        "Synthetic retrieval query",
        "Synthetic grounded project answer",
        "syn_00",
        "answer_markdown",
    ):
        assert private not in text, (path, private)
claim_dir = data / "portfolio-continuity-generation-claims"
assert claim_dir.stat().st_mode & 0o777 == 0o700
claims = sorted(claim_dir.glob("*.json"))
assert len(claims) == 4
claim_identities = set()
for path in claims:
    assert path.stat().st_mode & 0o777 == 0o600
    claim = json.loads(path.read_text(encoding="utf-8"))
    assert claim["schema"].endswith("attempt_claim.v2")
    assert claim["execution_identity_sha256"] == hashlib.sha256(
        (
            "agent_bridge.portfolio_continuity_answer_attempt_claim.v2\0"
            + claim["contract_sha256"]
        ).encode("utf-8")
    ).hexdigest()
    claim_identities.add(claim["execution_identity_sha256"])
    assert claim["boundary"] == {
        "private": True,
        "raw_material_present": False,
        "single_use": True,
    }
assert len(claim_identities) == 3
for prefix in (
    "coverage",
    "identity",
    "semantic",
    "semantic-byte-mismatch",
    "semantic-recapture",
    "semantic-fresh",
    "semantic-retry",
    "replay",
):
    for suffix in ("generation", "blind", "map", "review", "redacted"):
        assert not (data / f"{prefix}.{suffix}.json").exists()

print("Portfolio continuity successor answer trial v2 verification passed")
PY

test "$(sha256sum "$EXPANDED_CONTRACT" | cut -d' ' -f1)" = \
  "$expanded_contract_sha_before"
test "$(sha256sum "$EXPANDED_REPORT" | cut -d' ' -f1)" = \
  "$expanded_report_sha_before"
test "$(sha256sum "$SUCCESSOR_CONTRACT" | cut -d' ' -f1)" = \
  "$successor_contract_sha_before"
test "$(sha256sum "$SUCCESSOR_REPORT" | cut -d' ' -f1)" = \
  "$successor_report_sha_before"
