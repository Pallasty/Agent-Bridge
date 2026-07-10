#!/usr/bin/env bash
# Verify the snapshot-safe AB-native portfolio-continuity trial adapter.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ADAPTER="$ROOT_DIR/scripts/eval/portfolio_continuity_ab_trial.py"
SCORER="$ROOT_DIR/scripts/eval/portfolio_continuity_eval.py"
SPEC_FIXTURE="$ROOT_DIR/scripts/eval/fixtures/portfolio_continuity_ab_capture_spec.json"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-10-portfolio-continuity-ab-native-surface-trial.md"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-portfolio-native-trial-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

PYTHONPYCACHEPREFIX="$tmpdir/pycache" python3 -m py_compile "$ADAPTER" "$SCORER"

python3 - "$SPEC_FIXTURE" "$tmpdir" "$ROOT_DIR" <<'PY'
import json
import sqlite3
import sys
from pathlib import Path

fixture = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
tmp = Path(sys.argv[2])
repo = Path(sys.argv[3])
fixture["repo"] = str(repo)
(tmp / "capture_spec.json").write_text(
    json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
wrong_identity = json.loads(json.dumps(fixture))
wrong_identity["source_commit"] = "b" * 40
(tmp / "capture_spec.wrong-identity.json").write_text(
    json.dumps(wrong_identity, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
private_boundary = json.loads(json.dumps(fixture))
private_repo = tmp / "private-boundary-repo"
private_repo.mkdir()
private_boundary["repo"] = str(private_repo)
(tmp / "capture_spec.private-boundary.json").write_text(
    json.dumps(private_boundary, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
tracked_repo = tmp / "tracked-private-repo"
tracked_repo.mkdir()
(tracked_repo / ".gitignore").write_text("/data/\n", encoding="utf-8")
tracked_boundary = json.loads(json.dumps(fixture))
tracked_boundary["repo"] = str(tracked_repo)
(tmp / "capture_spec.tracked-private.json").write_text(
    json.dumps(tracked_boundary, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

with sqlite3.connect(tmp / "source.db") as conn:
    conn.execute("CREATE TABLE marker (value TEXT NOT NULL)")
    conn.execute("INSERT INTO marker(value) VALUES ('live-source')")

fake = r'''#!/usr/bin/env python3
import json
import os
import sqlite3
import sys

if sys.argv[1:] == ["--version"]:
    print("agent-bridge 0.14.0 (fake; aaaaaaaaaaaa)")
    raise SystemExit(0)

db = os.environ["AGENT_BRIDGE_DB"]
if not os.environ.get("FAKE_HIDE_DB_PATH"):
    print(f"SQLite store path={db}", file=sys.stderr, flush=True)

digest = {
    "key": "syn_digest",
    "kind": "digest",
    "status": "active",
    "created_at": 100,
    "updated_at": 200,
    "content": "Synthetic digest private content: current goal, current problem, next action.",
}
noise = {
    "key": "syn_noise",
    "kind": "context",
    "status": "active",
    "created_at": 110,
    "updated_at": 210,
    "content": "Synthetic irrelevant private context that must remain in the raw capture only.",
}

def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)

for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    request_id = request["id"]
    method = request.get("method")
    if method == "initialize":
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
    if method != "tools/call":
        emit({"jsonrpc": "2.0", "id": request_id, "error": {"code": -1}})
        continue
    name = request["params"]["name"]
    if name == "memory_search":
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE marker SET value='snapshot-mutated'")
        text = json.dumps(
            [
                {"record": digest, "score": 1.0},
                {"record": noise, "score": 0.2},
            ],
            ensure_ascii=False,
        )
    elif name == "session_bootstrap":
        text = (
            "=== Project State ===\n"
            "Synthetic bootstrap private state: current goal and current problem.\n"
            "=== Stale Handoff ===\n"
            "Synthetic stale private next action.\n"
        )
    elif name == "memory_get":
        text = json.dumps(digest, ensure_ascii=False)
    else:
        emit({"jsonrpc": "2.0", "id": request_id, "error": {"code": -3}})
        continue
    emit({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "isError": False,
            "content": [{"type": "text", "text": text}],
            "backend_id": {"memory": "fake-sqlite"},
        },
    })
'''
fake_path = tmp / "fake-agent-bridge"
fake_path.write_text(fake, encoding="utf-8")
fake_path.chmod(0o755)
PY

git -C "$tmpdir/tracked-private-repo" init -q
mkdir -p "$tmpdir/tracked-private-repo/data"
printf '{}\n' >"$tmpdir/tracked-private-repo/data/tracked.json"
git -C "$tmpdir/tracked-private-repo" add -f .gitignore data/tracked.json

PYTHONPYCACHEPREFIX="$tmpdir/pycache" python3 - "$tmpdir" "$ROOT_DIR" <<'PY'
import json
import os
import sqlite3
import sys
from pathlib import Path

tmp = Path(sys.argv[1])
root = Path(sys.argv[2])
sys.path.insert(0, str(root / "scripts/eval"))
import portfolio_continuity_ab_trial as trial

source = tmp / "race-source.db"
raw_output = tmp / "race-output.json"
redacted_output = tmp / "race-redacted.json"
with sqlite3.connect(source) as conn:
    conn.execute("CREATE TABLE marker (value TEXT NOT NULL)")
    conn.execute("INSERT INTO marker(value) VALUES ('live-source')")

with trial.AtomicJsonDestination(raw_output) as raw_destination:
    with trial.AtomicJsonDestination(redacted_output) as redacted_destination:
        trial.validate_capture_output_paths(
            source,
            root,
            raw_output,
            redacted_output,
            raw_destination,
            redacted_destination,
        )
        os.link(source, raw_output)
        raw_destination.write({"safe": True})
assert not os.path.samefile(source, raw_output)
with sqlite3.connect(source) as conn:
    assert conn.execute("SELECT value FROM marker").fetchone()[0] == "live-source"

source_parent = tmp / "parent-race-source"
safe_parent = tmp / "parent-race-safe"
source_parent.mkdir()
safe_parent.mkdir()
parent_source = source_parent / "protected.db"
with sqlite3.connect(parent_source) as conn:
    conn.execute("CREATE TABLE marker (value TEXT NOT NULL)")
    conn.execute("INSERT INTO marker(value) VALUES ('parent-live-source')")
route = tmp / "parent-race-route"
route.symlink_to(safe_parent, target_is_directory=True)
parent_raw = route / parent_source.name
parent_redacted = safe_parent / "redacted.json"
with trial.AtomicJsonDestination(parent_raw) as raw_destination:
    with trial.AtomicJsonDestination(parent_redacted) as redacted_destination:
        trial.validate_capture_output_paths(
            parent_source,
            root,
            parent_raw,
            parent_redacted,
            raw_destination,
            redacted_destination,
        )
        route.unlink()
        route.symlink_to(source_parent, target_is_directory=True)
        raw_destination.write({"safe": True})
with sqlite3.connect(parent_source) as conn:
    assert conn.execute("SELECT value FROM marker").fetchone()[0] == "parent-live-source"
assert json.loads((safe_parent / parent_source.name).read_text(encoding="utf-8")) == {
    "safe": True
}

policy_repo = tmp / "fixed-policy-repo"
policy_outside = tmp / "fixed-policy-outside"
policy_repo.mkdir()
policy_outside.mkdir()
policy_route = tmp / "fixed-policy-route"
policy_route.symlink_to(policy_repo, target_is_directory=True)
policy_raw = policy_route / "unignored.json"
policy_redacted = policy_outside / "redacted.json"
with trial.AtomicJsonDestination(policy_raw) as raw_destination:
    with trial.AtomicJsonDestination(policy_redacted) as redacted_destination:
        policy_route.unlink()
        policy_route.symlink_to(policy_outside, target_is_directory=True)
        try:
            trial.validate_capture_output_paths(
                source,
                policy_repo,
                policy_raw,
                policy_redacted,
                raw_destination,
                redacted_destination,
            )
        except trial.TrialError as exc:
            assert "must be stored under data/" in str(exc)
        else:
            raise AssertionError("fixed in-repo output path bypassed the private-data policy")
assert not (policy_repo / "unignored.json").exists()
PY

python3 "$ADAPTER" capture \
  --spec "$tmpdir/capture_spec.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$tmpdir/capture.raw.json" \
  --redacted-output "$tmpdir/capture.redacted.json" \
  >"$tmpdir/capture.stdout.json"

python3 "$ADAPTER" capture \
  --spec "$tmpdir/capture_spec.tracked-private.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$tmpdir/tracked-private-repo/data/untracked.raw.json" \
  --redacted-output "$tmpdir/untracked-private.redacted.json" \
  >"$tmpdir/untracked-private.stdout.json"
git -C "$tmpdir/tracked-private-repo" check-ignore -q -- data/untracked.raw.json
test -z "$(git -C "$tmpdir/tracked-private-repo" ls-files -- data/untracked.raw.json)"

cp "$tmpdir/capture_spec.json" "$tmpdir/capture-spec-output-alias.json"
if python3 "$ADAPTER" capture \
  --spec "$tmpdir/capture-spec-output-alias.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$tmpdir/capture-spec-output-alias.json" \
  --redacted-output "$tmpdir/spec-alias-redacted.json" \
  >"$tmpdir/capture-spec-output-alias.stdout" \
  2>"$tmpdir/capture-spec-output-alias.stderr"; then
  echo "expected capture raw/spec alias to fail closed" >&2
  exit 1
fi
cmp -s "$tmpdir/capture_spec.json" "$tmpdir/capture-spec-output-alias.json"

ln "$tmpdir/fake-agent-bridge" "$tmpdir/capture-binary-output-alias.json"
if python3 "$ADAPTER" capture \
  --spec "$tmpdir/capture_spec.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$tmpdir/capture-binary-output-alias.json" \
  --redacted-output "$tmpdir/binary-alias-redacted.json" \
  >"$tmpdir/capture-binary-output-alias.stdout" \
  2>"$tmpdir/capture-binary-output-alias.stderr"; then
  echo "expected capture raw/binary hardlink alias to fail closed" >&2
  exit 1
fi
rm "$tmpdir/capture-binary-output-alias.json"

ln "$tmpdir/source.db" "$tmpdir/source-raw-hardlink.json"
if python3 "$ADAPTER" capture \
  --spec "$tmpdir/capture_spec.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$tmpdir/source-raw-hardlink.json" \
  --redacted-output "$tmpdir/hardlink-redacted.json" \
  >"$tmpdir/source-raw-hardlink.stdout" 2>"$tmpdir/source-raw-hardlink.stderr"; then
  echo "expected source/raw hardlink alias to fail closed" >&2
  exit 1
fi
rm "$tmpdir/source-raw-hardlink.json"

ln "$tmpdir/source.db" "$tmpdir/source-redacted-hardlink.json"
if python3 "$ADAPTER" capture \
  --spec "$tmpdir/capture_spec.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$tmpdir/hardlink-raw.json" \
  --redacted-output "$tmpdir/source-redacted-hardlink.json" \
  >"$tmpdir/source-redacted-hardlink.stdout" 2>"$tmpdir/source-redacted-hardlink.stderr"; then
  echo "expected source/redacted hardlink alias to fail closed" >&2
  exit 1
fi
rm "$tmpdir/source-redacted-hardlink.json"

ln -s "$tmpdir/source.db" "$tmpdir/source-raw-symlink.json"
if python3 "$ADAPTER" capture \
  --spec "$tmpdir/capture_spec.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$tmpdir/source-raw-symlink.json" \
  --redacted-output "$tmpdir/symlink-redacted.json" \
  >"$tmpdir/source-raw-symlink.stdout" 2>"$tmpdir/source-raw-symlink.stderr"; then
  echo "expected source/raw symlink alias to fail closed" >&2
  exit 1
fi
rm "$tmpdir/source-raw-symlink.json"

touch "$tmpdir/output-alias-raw.json"
ln "$tmpdir/output-alias-raw.json" "$tmpdir/output-alias-redacted.json"
if python3 "$ADAPTER" capture \
  --spec "$tmpdir/capture_spec.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$tmpdir/output-alias-raw.json" \
  --redacted-output "$tmpdir/output-alias-redacted.json" \
  >"$tmpdir/output-hardlink.stdout" 2>"$tmpdir/output-hardlink.stderr"; then
  echo "expected raw/redacted hardlink alias to fail closed" >&2
  exit 1
fi

python3 "$ADAPTER" review-template \
  --capture "$tmpdir/capture.raw.json" \
  --output "$tmpdir/review.template.json" \
  >"$tmpdir/review-template.stdout.json"

cp "$tmpdir/capture.raw.json" "$tmpdir/review-input-output-alias.json"
if python3 "$ADAPTER" review-template \
  --capture "$tmpdir/review-input-output-alias.json" \
  --output "$tmpdir/review-input-output-alias.json" \
  >"$tmpdir/review-input-output-alias.stdout" \
  2>"$tmpdir/review-input-output-alias.stderr"; then
  echo "expected private review input/output alias to fail closed" >&2
  exit 1
fi
cmp -s "$tmpdir/capture.raw.json" "$tmpdir/review-input-output-alias.json"

PYTHONPYCACHEPREFIX="$tmpdir/pycache" python3 - "$tmpdir" "$ROOT_DIR" <<'PY'
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

tmp = Path(sys.argv[1])
root = Path(sys.argv[2])
sys.path.insert(0, str(root / "scripts/eval"))
import portfolio_continuity_ab_trial as trial

capture_path = tmp / "capture.raw.json"
capture = json.loads(capture_path.read_text(encoding="utf-8"))
decisions = {
    "schema": "agent_bridge.portfolio_continuity_review_decisions.v1",
    "capture_sha256": hashlib.sha256(capture_path.read_bytes()).hexdigest(),
    "review_template_sha256": hashlib.sha256(
        (tmp / "review.template.json").read_bytes()
    ).hexdigest(),
    "selector_manifest_sha256": trial.review_selector_manifest_sha256(capture),
    "reviewer": "synthetic_reviewer",
    "cases": {},
}
for case in capture["cases"]:
    required = {item["claim_id"] for item in case["required_claims"]}
    key_decisions = {}
    title_decisions = {}
    for condition in case["conditions"].values():
        for item in condition["evidence"]:
            if item["source_key"] == "syn_digest":
                key_decisions["syn_digest"] = {
                    "status": "active",
                    "supports": sorted(required),
                }
            elif item["source_key"] == "syn_noise":
                key_decisions["syn_noise"] = {"status": "active", "supports": []}
            elif item["source_title"] == "Project State":
                title_decisions["Project State"] = {
                    "status": "active",
                    "supports": ["current_goal", "current_problem"],
                }
            elif item["source_title"] == "Stale Handoff":
                title_decisions["Stale Handoff"] = {
                    "status": "superseded",
                    "supports": ["next_action"],
                }
            else:
                raise AssertionError(item)
    decisions["cases"][case["case_id"]] = {
        "source_keys": key_decisions,
        "source_titles": title_decisions,
    }

(tmp / "review.decisions.json").write_text(
    json.dumps(decisions, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

tampered_template = json.loads((tmp / "review.template.json").read_text(encoding="utf-8"))
validity = tampered_template["cases"][0]["evidence_reviews"][0]
validity["valid_from"] = 0 if validity["valid_from"] != 0 else 1
tampered_template_bytes = (
    json.dumps(tampered_template, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
).encode("utf-8")
(tmp / "review.template-validity-tamper.json").write_bytes(tampered_template_bytes)
tampered_template_decisions = json.loads(json.dumps(decisions))
tampered_template_decisions["review_template_sha256"] = hashlib.sha256(
    tampered_template_bytes
).hexdigest()
(tmp / "review.decisions-validity-tamper.json").write_text(
    json.dumps(tampered_template_decisions, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

with sqlite3.connect(tmp / "source.db") as conn:
    assert conn.execute("SELECT value FROM marker").fetchone()[0] == "live-source"

redacted = json.loads((tmp / "capture.redacted.json").read_text(encoding="utf-8"))
assert redacted["capture_sha256"] == hashlib.sha256(capture_path.read_bytes()).hexdigest()
assert redacted["snapshot_sha256_before"] != redacted["snapshot_sha256_after"]
assert "aaaaaaaaaaaa" in redacted["binary_observation"]
assert all(redacted["boundary"].values()) is False
assert redacted["boundary"]["source_db_opened_read_only"] is True
assert redacted["boundary"]["source_db_passed_to_child"] is False
assert redacted["boundary"]["child_db_is_temporary_snapshot"] is True
assert redacted["boundary"]["child_snapshot_path_confirmed"] is True
assert redacted["boundary"]["live_store_writes"] is False
assert redacted["boundary"]["calls_llm"] is False
template_receipt = json.loads(
    (tmp / "review-template.stdout.json").read_text(encoding="utf-8")
)
assert template_receipt == {
    "output_sha256": hashlib.sha256((tmp / "review.template.json").read_bytes()).hexdigest(),
    "packet_schema": "agent_bridge.portfolio_continuity_evidence_review.v0",
    "private_packet_written": True,
    "schema": "agent_bridge.private_output_receipt.v0",
}

for path in [
    tmp / "capture.redacted.json",
    tmp / "capture.stdout.json",
    tmp / "review.template.json",
]:
    text = path.read_text(encoding="utf-8")
    for private in [
        "Synthetic private status prompt",
        "Synthetic private retrospective prompt",
        "Synthetic digest private content",
        "syn_digest",
        "syn_noise",
    ]:
        assert private not in text
PY

python3 "$ADAPTER" apply-review \
  --capture "$tmpdir/capture.raw.json" \
  --template "$tmpdir/review.template.json" \
  --decisions "$tmpdir/review.decisions.json" \
  --output "$tmpdir/review.json" \
  >"$tmpdir/apply-review.stdout.json"

python3 - "$tmpdir" <<'PY'
import copy
import hashlib
import json
import sys
from pathlib import Path

tmp = Path(sys.argv[1])
review = json.loads((tmp / "review.json").read_text(encoding="utf-8"))
decisions = json.loads((tmp / "review.decisions.json").read_text(encoding="utf-8"))
assert review["schema"] == "agent_bridge.portfolio_continuity_evidence_review.v1"
assert review["decision_binding"] == {
    "decisions_schema": "agent_bridge.portfolio_continuity_review_decisions.v1",
    "decisions_sha256": hashlib.sha256(
        (tmp / "review.decisions.json").read_bytes()
    ).hexdigest(),
    "review_template_sha256": decisions["review_template_sha256"],
    "selector_manifest_sha256": decisions["selector_manifest_sha256"],
}
apply_receipt = json.loads(
    (tmp / "apply-review.stdout.json").read_text(encoding="utf-8")
)
assert apply_receipt == {
    "output_sha256": hashlib.sha256((tmp / "review.json").read_bytes()).hexdigest(),
    "packet_schema": "agent_bridge.portfolio_continuity_evidence_review.v1",
    "private_packet_written": True,
    "schema": "agent_bridge.private_output_receipt.v0",
}

missing = copy.deepcopy(review)
missing["cases"][0]["evidence_reviews"].pop()
(tmp / "review.missing.json").write_text(json.dumps(missing), encoding="utf-8")

wrong_hash = copy.deepcopy(review)
wrong_hash["capture_sha256"] = "0" * 64
(tmp / "review.wrong-hash.json").write_text(json.dumps(wrong_hash), encoding="utf-8")

unknown_claim = copy.deepcopy(review)
unknown_claim["cases"][0]["evidence_reviews"][0]["supports_claim_ids"] = [
    "unknown_claim"
]
(tmp / "review.unknown-claim.json").write_text(
    json.dumps(unknown_claim), encoding="utf-8"
)

semantic_tamper = copy.deepcopy(review)
semantic_row = semantic_tamper["cases"][0]["evidence_reviews"][0]
semantic_row["status"] = (
    "archived" if semantic_row["status"] != "archived" else "active"
)
(tmp / "review.semantic-tamper.json").write_text(
    json.dumps(semantic_tamper), encoding="utf-8"
)

missing_decision = copy.deepcopy(decisions)
missing_decision["cases"]["synthetic_status"]["source_keys"].pop("syn_noise")
(tmp / "review.decisions-missing.json").write_text(
    json.dumps(missing_decision), encoding="utf-8"
)

wrong_capture_decision = copy.deepcopy(decisions)
wrong_capture_decision["capture_sha256"] = "0" * 64
(tmp / "review.decisions-wrong-capture.json").write_text(
    json.dumps(wrong_capture_decision), encoding="utf-8"
)

wrong_template_decision = copy.deepcopy(decisions)
wrong_template_decision["review_template_sha256"] = "0" * 64
(tmp / "review.decisions-wrong-template.json").write_text(
    json.dumps(wrong_template_decision), encoding="utf-8"
)

wrong_selector_decision = copy.deepcopy(decisions)
wrong_selector_decision["selector_manifest_sha256"] = "0" * 64
(tmp / "review.decisions-wrong-selector.json").write_text(
    json.dumps(wrong_selector_decision), encoding="utf-8"
)

legacy_decision = copy.deepcopy(decisions)
legacy_decision["schema"] = "agent_bridge.portfolio_continuity_review_decisions.v0"
legacy_decision.pop("capture_sha256")
legacy_decision.pop("review_template_sha256")
legacy_decision.pop("selector_manifest_sha256")
(tmp / "review.decisions-legacy-v0.json").write_text(
    json.dumps(legacy_decision), encoding="utf-8"
)

malformed_capture = json.loads((tmp / "capture.raw.json").read_text(encoding="utf-8"))
malformed_capture["cases"][0].pop("conditions")
(tmp / "capture.malformed.json").write_text(
    json.dumps(malformed_capture), encoding="utf-8"
)

selector_drift = json.loads((tmp / "capture.raw.json").read_text(encoding="utf-8"))
drift_case = selector_drift["cases"][0]
first_condition = next(iter(drift_case["conditions"].values()))
target = first_condition["evidence"][0]
drifted = False
for condition in drift_case["conditions"].values():
    for item in condition["evidence"]:
        if item is target or item["evidence_id"] != target["evidence_id"]:
            continue
        if isinstance(item.get("source_key"), str):
            item["source_key"] += "_drift"
        else:
            item["source_title"] += " drift"
        drifted = True
        break
    if drifted:
        break
assert drifted
(tmp / "capture.selector-drift.json").write_text(
    json.dumps(selector_drift), encoding="utf-8"
)
PY

if python3 "$ADAPTER" apply-review \
  --capture "$tmpdir/capture.raw.json" \
  --template "$tmpdir/review.template.json" \
  --decisions "$tmpdir/review.decisions-missing.json" \
  --output "$tmpdir/review.should-not-exist.json" \
  >"$tmpdir/bad-decisions.stdout" 2>"$tmpdir/bad-decisions.stderr"; then
  echo "expected missing selector decision to fail closed" >&2
  exit 1
fi

if python3 "$ADAPTER" apply-review \
  --capture "$tmpdir/capture.raw.json" \
  --template "$tmpdir/review.template.json" \
  --decisions "$tmpdir/review.decisions-wrong-capture.json" \
  --output "$tmpdir/review.should-not-exist.json" \
  >"$tmpdir/bad-decision-capture.stdout" 2>"$tmpdir/bad-decision-capture.stderr"; then
  echo "expected capture-mismatched review decisions to fail closed" >&2
  exit 1
fi

if python3 "$ADAPTER" apply-review \
  --capture "$tmpdir/capture.raw.json" \
  --template "$tmpdir/review.template.json" \
  --decisions "$tmpdir/review.decisions-wrong-template.json" \
  --output "$tmpdir/review.should-not-exist.json" \
  >"$tmpdir/bad-decision-template.stdout" 2>"$tmpdir/bad-decision-template.stderr"; then
  echo "expected template-mismatched review decisions to fail closed" >&2
  exit 1
fi

if python3 "$ADAPTER" apply-review \
  --capture "$tmpdir/capture.raw.json" \
  --template "$tmpdir/review.template-validity-tamper.json" \
  --decisions "$tmpdir/review.decisions-validity-tamper.json" \
  --output "$tmpdir/review.should-not-exist.json" \
  >"$tmpdir/bad-template-validity.stdout" \
  2>"$tmpdir/bad-template-validity.stderr"; then
  echo "expected capture-derived template validity drift to fail closed" >&2
  exit 1
fi

if python3 "$ADAPTER" apply-review \
  --capture "$tmpdir/capture.raw.json" \
  --template "$tmpdir/review.template.json" \
  --decisions "$tmpdir/review.decisions-wrong-selector.json" \
  --output "$tmpdir/review.should-not-exist.json" \
  >"$tmpdir/bad-decision-selector.stdout" 2>"$tmpdir/bad-decision-selector.stderr"; then
  echo "expected selector-mismatched review decisions to fail closed" >&2
  exit 1
fi

if python3 "$ADAPTER" apply-review \
  --capture "$tmpdir/capture.raw.json" \
  --template "$tmpdir/review.template.json" \
  --decisions "$tmpdir/review.decisions-legacy-v0.json" \
  --output "$tmpdir/review.should-not-exist.json" \
  >"$tmpdir/bad-decision-legacy.stdout" 2>"$tmpdir/bad-decision-legacy.stderr"; then
  echo "expected legacy unbound review decisions to fail closed" >&2
  exit 1
fi
test ! -e "$tmpdir/review.should-not-exist.json"

if python3 "$ADAPTER" review-template \
  --capture "$tmpdir/capture.malformed.json" \
  --output "$tmpdir/review.malformed.json" \
  >"$tmpdir/malformed.stdout" 2>"$tmpdir/malformed.stderr"; then
  echo "expected malformed capture to fail closed" >&2
  exit 1
fi

if python3 "$ADAPTER" review-template \
  --capture "$tmpdir/capture.selector-drift.json" \
  --output "$tmpdir/review.selector-drift.json" \
  >"$tmpdir/selector-drift.stdout" 2>"$tmpdir/selector-drift.stderr"; then
  echo "expected duplicate evidence selector drift to fail closed" >&2
  exit 1
fi

python3 "$ADAPTER" assemble \
  --capture "$tmpdir/capture.raw.json" \
  --review "$tmpdir/review.json" \
  --template "$tmpdir/review.template.json" \
  --decisions "$tmpdir/review.decisions.json" \
  --output-dir "$tmpdir/assembled" \
  >"$tmpdir/assemble.stdout.json"

if python3 "$ADAPTER" assemble \
  --capture "$tmpdir/capture.raw.json" \
  --review "$tmpdir/review.template.json" \
  --template "$tmpdir/review.template.json" \
  --decisions "$tmpdir/review.decisions.json" \
  --output-dir "$tmpdir/legacy-assembled" \
  >"$tmpdir/legacy-assemble.stdout" 2>"$tmpdir/legacy-assemble.stderr"; then
  echo "expected unbound legacy review packet to fail closed" >&2
  exit 1
fi

python3 "$SCORER" \
  --fixture "$tmpdir/assembled/fixture.reviewed.json" \
  --candidate "$tmpdir/assembled/candidate.hybrid_retrieval.json" \
  --strict \
  --output "$tmpdir/score.retrieval.json"

python3 "$SCORER" \
  --fixture "$tmpdir/assembled/fixture.reviewed.json" \
  --candidate "$tmpdir/assembled/candidate.portfolio_digest.json" \
  --strict \
  --output "$tmpdir/score.digest.json"

if python3 "$SCORER" \
  --fixture "$tmpdir/assembled/fixture.reviewed.json" \
  --candidate "$tmpdir/assembled/candidate.session_bootstrap.json" \
  --strict \
  --output "$tmpdir/score.bootstrap.json"; then
  echo "expected synthetic bootstrap evidence to fail strict scoring" >&2
  exit 1
fi

for name in missing wrong-hash unknown-claim semantic-tamper; do
  if python3 "$ADAPTER" assemble \
    --capture "$tmpdir/capture.raw.json" \
    --review "$tmpdir/review.$name.json" \
    --template "$tmpdir/review.template.json" \
    --decisions "$tmpdir/review.decisions.json" \
    --output-dir "$tmpdir/bad-$name" \
    >"$tmpdir/bad-$name.stdout" 2>"$tmpdir/bad-$name.stderr"; then
    echo "expected $name review to fail assembly" >&2
    exit 1
  fi
done

if FAKE_HIDE_DB_PATH=1 python3 "$ADAPTER" capture \
  --spec "$tmpdir/capture_spec.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$tmpdir/unconfirmed.raw.json" \
  --redacted-output "$tmpdir/unconfirmed.redacted.json" \
  >"$tmpdir/unconfirmed.stdout" 2>"$tmpdir/unconfirmed.stderr"; then
  echo "expected unconfirmed snapshot path to fail capture" >&2
  exit 1
fi

if python3 "$ADAPTER" capture \
  --spec "$tmpdir/capture_spec.wrong-identity.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$tmpdir/wrong-identity.raw.json" \
  --redacted-output "$tmpdir/wrong-identity.redacted.json" \
  >"$tmpdir/wrong-identity.stdout" 2>"$tmpdir/wrong-identity.stderr"; then
  echo "expected mismatched binary identity to fail capture" >&2
  exit 1
fi

if python3 "$ADAPTER" capture \
  --spec "$tmpdir/capture_spec.private-boundary.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$tmpdir/private-boundary-repo/raw-capture.json" \
  --redacted-output "$tmpdir/private-boundary.redacted.json" \
  >"$tmpdir/private-boundary.stdout" 2>"$tmpdir/private-boundary.stderr"; then
  echo "expected in-repo raw capture outside data/ to fail" >&2
  exit 1
fi

if python3 "$ADAPTER" capture \
  --spec "$tmpdir/capture_spec.tracked-private.json" \
  --source-db "$tmpdir/source.db" \
  --agent-bridge-bin "$tmpdir/fake-agent-bridge" \
  --raw-output "$tmpdir/tracked-private-repo/data/tracked.json" \
  --redacted-output "$tmpdir/tracked-private.redacted.json" \
  >"$tmpdir/tracked-private.stdout" 2>"$tmpdir/tracked-private.stderr"; then
  echo "expected tracked in-repo raw capture to fail" >&2
  exit 1
fi

python3 - "$tmpdir" "$ROOT_DIR/scripts/eval/README.md" "$ROOT_DIR/CHANGELOG.md" "$REPORT" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path

tmp = Path(sys.argv[1])
readme = Path(sys.argv[2]).read_text(encoding="utf-8")
changelog = Path(sys.argv[3]).read_text(encoding="utf-8")
report = Path(sys.argv[4]).read_text(encoding="utf-8")
normalized_readme = " ".join(readme.split())
summary = json.loads((tmp / "assembled/assembly.summary.json").read_text(encoding="utf-8"))
retrieval = json.loads((tmp / "score.retrieval.json").read_text(encoding="utf-8"))
bootstrap = json.loads((tmp / "score.bootstrap.json").read_text(encoding="utf-8"))
digest = json.loads((tmp / "score.digest.json").read_text(encoding="utf-8"))

assert summary["schema"] == "agent_bridge.portfolio_continuity_ab_assembly.v0"
assert summary["review_sha256"] == hashlib.sha256(
    (tmp / "review.json").read_bytes()
).hexdigest()
assert summary["conditions"]["hybrid_retrieval"]["observed_evidence_count"] == 4
assert summary["conditions"]["hybrid_retrieval"]["relevant_evidence_count"] == 2
assert summary["conditions"]["hybrid_retrieval"]["relevant_evidence_ratio"] == 0.5
assert summary["conditions"]["session_bootstrap"]["observed_evidence_count"] == 4
assert summary["conditions"]["session_bootstrap"]["stale_or_unknown_evidence_count"] == 2
assert summary["conditions"]["portfolio_digest"]["observed_evidence_count"] == 2
assert summary["conditions"]["portfolio_digest"]["relevant_evidence_ratio"] == 1.0
assert summary["boundary"]["raw_content_in_summary"] is False
assert summary["boundary"]["raw_evidence_keys_in_summary"] is False
assert summary["boundary"]["calls_llm"] is False
assert summary["boundary"]["writes_live_ab_store"] is False

assert retrieval["verdict"] == "PASS"
assert retrieval["aggregate"]["supported_claim_coverage"] == 1.0
assert retrieval["aggregate"]["evidence_precision"] == 1.0
assert digest["verdict"] == "PASS"
assert digest["aggregate"]["supported_claim_coverage"] == 1.0
assert digest["aggregate"]["context_tokens_total"] < retrieval["aggregate"]["context_tokens_total"]
assert bootstrap["verdict"] == "FAIL"
assert bootstrap["aggregate"]["supported_claim_coverage"] == 0.714286
assert bootstrap["aggregate"]["evidence_precision"] == 0.666667
assert bootstrap["aggregate"]["stale_evidence_ref_count"] == 2
assert bootstrap["aggregate"]["unsupported_evidence_claim_count"] == 2

for path in [tmp / "assembled/assembly.summary.json", tmp / "assemble.stdout.json"]:
    text = path.read_text(encoding="utf-8")
    for private in ["Synthetic", "syn_digest", "syn_noise", "current goal"]:
        assert private not in text

assert "exactly once" in (tmp / "bad-missing.stderr").read_text(encoding="utf-8")
assert "does not match" in (tmp / "bad-wrong-hash.stderr").read_text(encoding="utf-8")
assert "unknown supported claim" in (
    tmp / "bad-unknown-claim.stderr"
).read_text(encoding="utf-8")
assert "does not match the bound template and decisions" in (
    tmp / "bad-semantic-tamper.stderr"
).read_text(encoding="utf-8")
assert "leave evidence unreviewed" in (
    tmp / "bad-decisions.stderr"
).read_text(encoding="utf-8")
assert "do not match the raw capture" in (
    tmp / "bad-decision-capture.stderr"
).read_text(encoding="utf-8")
assert "do not match the review template" in (
    tmp / "bad-decision-template.stderr"
).read_text(encoding="utf-8")
assert "does not match the capture-derived template" in (
    tmp / "bad-template-validity.stderr"
).read_text(encoding="utf-8")
assert "do not match the capture selector manifest" in (
    tmp / "bad-decision-selector.stderr"
).read_text(encoding="utf-8")
assert "review decisions schema must be" in (
    tmp / "bad-decision-legacy.stderr"
).read_text(encoding="utf-8")
assert "review schema must be" in (
    tmp / "legacy-assemble.stderr"
).read_text(encoding="utf-8")
assert (tmp / "malformed.stderr").read_text(encoding="utf-8").strip() == (
    "ERROR: malformed trial packet"
)
assert "different review metadata" in (
    tmp / "selector-drift.stderr"
).read_text(encoding="utf-8")
assert "did not confirm" in (tmp / "unconfirmed.stderr").read_text(encoding="utf-8")
assert "binary identity does not match" in (
    tmp / "wrong-identity.stderr"
).read_text(encoding="utf-8")
assert "must be stored under data/" in (
    tmp / "private-boundary.stderr"
).read_text(encoding="utf-8")
assert "must not be tracked by git" in (
    tmp / "tracked-private.stderr"
).read_text(encoding="utf-8")
assert "must not overwrite the source SQLite database" in (
    tmp / "source-raw-hardlink.stderr"
).read_text(encoding="utf-8")
assert "must not overwrite an input file" in (
    tmp / "capture-spec-output-alias.stderr"
).read_text(encoding="utf-8")
assert "must not overwrite an input file" in (
    tmp / "capture-binary-output-alias.stderr"
).read_text(encoding="utf-8")
assert "must not overwrite the source SQLite database" in (
    tmp / "source-redacted-hardlink.stderr"
).read_text(encoding="utf-8")
assert "must not overwrite the source SQLite database" in (
    tmp / "source-raw-symlink.stderr"
).read_text(encoding="utf-8")
assert "must be different files" in (
    tmp / "output-hardlink.stderr"
).read_text(encoding="utf-8")
assert "must not overwrite an input file" in (
    tmp / "review-input-output-alias.stderr"
).read_text(encoding="utf-8")

assert "portfolio_continuity_ab_trial.py" in readme
assert "source DB path is never passed to the child" in normalized_readme
assert "Snapshot-safe AB-native portfolio continuity trial" in changelog
required_report = [
    "# AB-Native Portfolio Continuity Surface Trial",
    "PROVISIONAL / REVIEW_BINDING_GAP",
    "## Results (Provisional)",
    "agent_bridge.portfolio_continuity_ab_assembly.v0",
    "runtime_source_commit: a8c6302325e27c9b5cb20f8c958ab719666de372",
    "capture_sha256: ab08bee97a29caa2ef51d73266208fc7fdaa041f230a4572cffbab4da1a2545f",
    "raw_capture_in_git: false",
    "review_provenance: legacy_unbound_v0",
    "admission_status: blocked_pending_capture_bound_review",
    "writes_live_ab_store: false",
    "answer_quality_claim: false",
    "| `hybrid_retrieval` | MET (unadmitted) | 2/2",
    "| `session_bootstrap` | NOT MET (unadmitted) | 1/2",
    "| `portfolio_digest` | MET (unadmitted) | 2/2",
    "79.429% fewer estimated context tokens",
    "data/eval/portfolio-continuity-ab-native-20260710/",
    "does not currently",
    "It is not a pre-digest baseline",
    "Forum thread: `design#119`, start post `3033`",
]
missing_report = [needle for needle in required_report if needle not in report]
if missing_report:
    raise SystemExit("missing report anchors: " + ", ".join(missing_report))
assert re.search(r"\b(?:PASS|FAIL)\b", report) is None

print("AB-native portfolio continuity trial verification passed")
PY
