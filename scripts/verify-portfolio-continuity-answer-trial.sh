#!/usr/bin/env bash
# Verify the isolated capture, fixed-model generation, blinding, and score gate.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ADAPTER="$ROOT_DIR/scripts/eval/portfolio_continuity_answer_trial.py"
CONTRACT="$ROOT_DIR/scripts/eval/fixtures/portfolio_continuity_answer_contract.json"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-10-portfolio-continuity-blinded-answer-trial-prereg.md"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-answer-trial-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT
export PYTHONPYCACHEPREFIX="$tmpdir/pycache"

python3 -m py_compile "$ADAPTER"
python3 "$ADAPTER" validate-contract --contract "$CONTRACT" >"$tmpdir/repo-contract.json"

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
        if args.get("compact") and os.environ.get("FAKE_RANK_MISMATCH"):
            ordered[0], ordered[1] = ordered[1], ordered[0]
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
answer = "Synthetic grounded project answer " + hashlib.sha256(prompt.encode()).hexdigest()[:12]
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
