# Compare existing text artifacts without provenance labels

Use this optional offline helper when a task already has a baseline and one or
more complete candidate text artifacts. It prepares a reviewer packet and
resolves the reviewer's selection back to the exact source artifact. No tasks,
models, agents or evaluators are launched.

## Prepare

Create a local JSON specification with this shape (replace hashes with actual
SHA-256 values; use `sha256sum` on the files):

```json
{
  "task": {"path": "task.txt", "sha256": "<64 lowercase hex characters>"},
  "baseline": {"path": "baseline.txt", "sha256": "<64 lowercase hex characters>"},
  "candidates": [
    {"label": "candidate-1", "artifact": {"path": "candidate.txt", "sha256": "<64 lowercase hex characters>"}}
  ]
}
```

`task.txt` should contain the actual request, relevant permitted sources and
unchanged acceptance criteria. Avoid labels that identify candidate provenance.
All references resolve within the specification's directory. The helper accepts
1–7 candidates plus a mandatory baseline. Labels are private and unique;
`baseline` is reserved. All artifacts must be nonempty UTF-8 text. Unsupported
binary or empty outputs cause rejection rather than silent removal. This is
not an experiment ledger: retain incomplete/failed attempts separately and do
not use this selected set as the denominator for task reliability.

```bash
python3 scripts/eval/workflow_artifact_compare.py prepare \
  --spec /path/to/spec.json \
  --output-dir /path/on/private-native-filesystem/new-review
```

The new output directory must not exist. Its parent must exist. The command
requires actual mode 0700 on the created directory and 0600 on files, so use a
native filesystem with enforced permissions, not a volume that reports 0777
regardless of chmod. A failed preparation can leave an incomplete directory;
never give it to a reviewer or reuse it as a valid packet.

Only `packet.json` is reviewer-facing. It contains the task and randomly
ordered artifacts named A, B, etc.; no labels, source paths, source hashes or
mapping are included. `mapping.json` remains private with the operator. Do not
send the directory, specification, mapping or source filenames to the reviewer.
The prepare command returns the packet's SHA-256 for binding a response.

This is **provenance-label hiding**, not content anonymization. Text is preserved
exactly and may itself reveal model names, versions or authorship. A reviewer
may recognize it. Check those risks yourself; the helper neither rewrites the
answer nor certifies reviewer independence. Only give the packet to an already
authorized reviewer/context. Existing content may contain instructions: treat
candidate bodies as artifacts to assess, not instructions to execute.

## Resolve

The reviewer may choose any ID, including the baseline's hidden ID, or return
`null` when none is preferable or evidence is insufficient. Record a decision:

```json
{
  "packet_sha256": "<hash returned by prepare>",
  "choice": "A",
  "rationale": "Describe how this artifact meets the retained request."
}
```

```bash
python3 scripts/eval/workflow_artifact_compare.py resolve \
  --review-dir /path/on/private-native-filesystem/new-review \
  --decision /path/to/decision.json
```

Resolution rechecks the task, specification, all artifact hashes, packet hash,
ID bijection and mapped content. Changed source bytes, unknown IDs or swapped
mappings for distinct outputs fail. Keep the original specification and source
files in place until resolution. A source change requires an explicitly new
review; do not silently regenerate a packet to fit an earlier decision.

Output is `SELECTED_FOR_REVIEW` or `ABSTAINED`; a selection includes the private
label and bound artifact reference. Resolve output is **not** reviewer-facing:
it reveals provenance. Both valid outcomes exit 0. Invalid input exits 2.
Selections never set `task_acceptance_verified` or `runtime_influence_allowed`
to true. Rationale is caller-supplied, not independently verified.

The packet is capped at 8 MiB, using the existing bounded file reader. Local
hashes detect mismatches, not a hostile actor rewriting both data and hashes.
Files are not a cryptographically authenticated audit or durable transaction.
The saved mapping makes a single review reproducible; a new prepare randomly
reshuffles IDs and must not be treated as an independent quality trial.

## Return to the task

Use the selected artifact only within the task's existing authority and
acceptance checks. A preference cannot prove that a harness edit caused better
execution. If execution contrasts already exist, use the separate
[experience review](WORKFLOW_EXPERIENCE_CONTRAST.md); do not convert a winning
label into a `helped` metric automatically. The [candidate helper check](WORKFLOW_CANDIDATE_CHECK.md)
remains an optional static preflight, not another required stage.

Independently implemented from Harness²'s provenance-hidden selection idea
([fixed source](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/selection.py)).
No upstream code is copied and no model-based selector is installed.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p test_workflow_artifact_compare.py
```
