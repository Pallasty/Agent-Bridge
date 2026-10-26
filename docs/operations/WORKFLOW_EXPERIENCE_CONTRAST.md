# Review an experience against execution contrasts

Use this offline command when an ordinary task already produced a candidate
change and comparable execution records. It helps review the supporting
observations before writing a lesson; it does not run tasks or require every
maintenance change to become an experiment.

```bash
python3 scripts/eval/workflow_experience_contrast.py \
  --experience path/to/experience.json
```

The input remains an `agent_bridge.experience.v0` object with `experience_id`
and `goal`. Add the optional `execution_contrast` object shown in the
[runnable synthetic example](../../scripts/eval/fixtures/workflow_experience_contrast/experience.json).
Existing experience objects without this extension return `insufficient_evidence`
and `NO_ENTRY`; their previous history and status are not rewritten.

```bash
# Synthetic mechanics demonstration, not a measured AB improvement:
python3 scripts/eval/workflow_experience_contrast.py \
  --experience scripts/eval/fixtures/workflow_experience_contrast/experience.json

# Existing historical experience, with no machine-readable contrast attached:
python3 scripts/eval/workflow_experience_contrast.py \
  --experience docs/design/fixtures/workflow-feedback-experience-report-cli-2026-06-30.json
```

## Evidence contract

- `changes`: component name, description, and before/after file references.
  Every reference has `path` and lowercase `sha256`. The bytes must differ.
- `metrics`: unique metric names and `direction` (`higher` or `lower`). Choose
  these from the task's retained acceptance criteria, before inspecting candidate
  results; the command cannot establish that you did so.
- `pairs`: baseline and candidate references to JSON run records. Keep failed
  and not-run slots, not just the runs with convenient scores.
- Each run has a unique `run_id`, `conditions`, `execution_status`, and numeric
  `metrics`. Conditions include nonempty `task`, `input_sha256`, `model`, and
  `environment`. Record the actual relevant configuration/version, not merely
  the label “same”. Entire conditions objects must match within each pair.
  Tasks may differ between pairs.
- `execution_status` is `completed`, `failed`, or `not_run`. A completed
  execution does **not** mean the task succeeded or was independently accepted.
  Record task correctness as a task-specific metric only when supported by the
  existing acceptance evidence; never infer it from process completion.
- Optional `cost` fields are `input_tokens`, `output_tokens`, `elapsed_ms`.
  Missing values remain unknown; an incomplete aggregate is null, not zero.
  Zero is valid only if it is a real measurement, as in the no-model fixture.

Relative paths resolve under the experience file's directory, or an explicit
`--evidence-root`. References resolving outside that root are rejected. Each
file is limited to 8 MiB; at most 32 changes, 32 metrics and 100 pairs are
reviewed. The command reads files and prints JSON; it does not overwrite an
experience or write to the memory store. Keep private evidence under an
appropriately protected directory. This is a local review helper, not a sandbox
for hostile concurrent filesystem mutations.

## Read the result

| Result | Meaning and next action |
| --- | --- |
| `helped` / `hurt` + `REVIEW_LESSON` | At least two declared pairs, one changed component, matching paired conditions, completed executions, all selected metrics present, and directional changes with no opposite sign. Review a possible positive or negative lesson; not permission to publish it |
| `no_observed_effect` + `NO_ENTRY` | No selected numeric metric changed; keep the observation without inventing a benefit |
| `confounded` + `NO_ENTRY` | One pair, multiple changed components, mismatched conditions, or mixed improvement/regression signs; do not attribute the result to one edit |
| `insufficient_evidence` + `NO_ENTRY` | Missing changes/metrics/pairs, incomplete execution, or missing selected metric; retain gaps and failed/not-run counts |
| `invalid_input` + `NO_ENTRY` | Broken hash, missing file, repeated run ID/artifact, invalid types, duplicate JSON keys or other malformed evidence; correct the input, never substitute a favorable result |

Valid reviews exit 0, including `NO_ENTRY`. Exit 0 means the review completed,
not that the experience or task passed. Invalid inputs exit 2. Insufficient
evidence takes verdict precedence over confounds, but both remain in `reasons`.
Raw candidate-minus-baseline deltas, file bindings and all declared pairs stay
in the report. Cost is reported separately; improved selected metrics do not
establish a net benefit, especially when cost is unknown or higher.

Two pairs are a conservative review minimum, **not** statistical significance.
Repeated run IDs and identical artifacts are rejected, but this cannot detect
fabricated IDs, missing attempts, dishonest conditions or hidden simultaneous
edits. Hash checks establish byte identity, not the truth of measurements.
`causal_effect_proven` and `runtime_influence_allowed` always remain false.

For a lesson worth retaining, use the existing manually reviewed experience
workflow: state the trigger, exact change, linked observations, counterexamples,
unknowns and cost; check independent task acceptance and another applicable case
before claiming transfer. This helper does not promote memory, modify policy,
change retrieval, or replace existing workflow-feedback promotion requirements.

## Export a proposed experience draft

Add `--lesson path/to/lesson.json` to opt into draft output. Supply the actual
proposed lesson explicitly; the command does not generate or verify its meaning:

```json
{
  "cue": "When a request explicitly names a project",
  "lesson": "Preserve that project name in the retrieval query.",
  "counterexample": "Do not invent a project name when none was supplied.",
  "unknowns": ["Transfer beyond the observed cases is untested."]
}
```

The command rereads and verifies the contrast artifacts. Only `helped` or `hurt`
can produce `DRAFT_PROPOSED`; other valid reviews return `NO_ENTRY` with
`draft: null`. The JSON envelope contains `review` and an optional `draft` in
`agent_bridge.experience.v0` format. It prints to stdout; saving this output is
an explicit caller action. Exit codes are unchanged.

The draft retains the contrast, observations, costs (including unknown costs),
counterexample and unknowns. Its status is `proposed`, its lesson is marked
`caller_proposed`, and all promotion/runtime influence flags remain false.
Previous success or promotion claims are not inherited. A caller's lesson may
still contradict the observations; semantic review and existing promotion
requirements remain necessary. Artifact selection is not lesson evidence.

To review a saved draft, extract the envelope's `draft` object into a JSON file,
then run the original command with `--experience saved-draft.json` and
`--evidence-root` pointing to the original artifact directory. Relative artifact
references are preserved; `source_anchors.evidence_root` records that location
but is not automatically trusted or loaded. The canonical review SHA-256 binds
the embedded review serialization, not the original experience file or a signed
acceptance receipt. Keep local paths and private observations private.

Draft validation and limitations are recorded in the
[draft implementation report](../reports/2026-10-26-harness2-experience-draft.md).

## Provenance and validation

Method adapted from Harness²'s separation of edits and execution observations,
including negative/no-effect/confounded outcomes and abstention:
[`experience()` at fixed commit 1cfe254e](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/prompts.py#L1105).
This is an independent AB implementation; no upstream code or dependencies are
copied. It adds file/metric checking instead of accepting an evidence string as
proof. It does not implement Harness²'s recursive runner or learned improver.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p test_workflow_experience_contrast.py
```

Implementation and its limits are recorded in the
[2026-10-26 implementation report](../reports/2026-10-26-harness2-experience-contrast.md).
