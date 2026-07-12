# Portfolio Continuity Successor V3 Protocol Preregistration

Date: 2026-07-10

Status: **PRE-REGISTERED / IMPLEMENTATION VERIFIED / INDEPENDENT READ-ONLY
REVIEW PASSED / FROZEN / NOT EXECUTED**. This change defines contract v3 and
its fail-closed validator.
It does not perform capture, answer generation, model review, scoring,
unblinding, an Agent-Bridge write, remote CI, versioning, tagging, release, or
deployment.

## Identity

```yaml
schema: agent_bridge.portfolio_continuity_answer_contract.v3
contract_id: portfolio_continuity_successor_v3_answer_blind_20260710
preregistration_base: a9bb0c93fcfecc63761946f50c7275f78de8db23
contract_commit: 1d2da68181a276a71da36688f53c8f26f3770b50
contract_sha256: da9e190492d74824159bbff18eaeff02a4848921989f4077072f126e1d4e4bcc
harness_source_sha256: 0b92b1153a77257a49fc847eb37be3e20d687c41067559c22b2ebed72649e003
surface_source_sha256: b6f599e748088e36424bd03e70a5bc3112aeaf728f6679b19297889a98e5b7f3
runtime_source_commit: 1f75ede032b36db321c3e767d620eac5a6a44c6e
blind_seed_sha256: 0df722697912c7da5f6749b434102e362f7ae872e5bc440e5b667de2c5e0ad3b
digest_key_sha256: a9d9842db1fe7437ce4a276ddae9a1c91d776cd75606ec2269bb50fc7df21cf1
execution_repo_path_sha256: 116257ea10192e1be1c92ef77e005f06d597c006801ea9eefcb5a29d4fdcee74
case_count: 12
condition_count: 2
answer_count_if_generated: 24
reviewer_count: 2
execution_status: NOT_EXECUTED
```

V3 uses a separate harness and contract. The historical v2 harness remains
byte-identical to its frozen `af15d857...` source; v3 does not weaken v2 hash
checking or reopen its consumed generation and scoring allowances. The first
v3 candidate at `9b0dcbcc` was never executed and is superseded by this
post-review refreeze.

## Independent Review Gate

Claude Opus 4.8 performed an independent public-source-only review in a clean
detached worktree with no private `data/`, writes, commands, MCP, web, capture,
or answer generation. The first review receipt SHA-256 is
`d14a534840810d0656757eb48b5523dbad5a654b40783272959a745073be1fd1`.
It confirmed the overall fail-closed order but found an operator-selected
score-claim replay path and unparsed command provenance. Both were remediated
before refreeze.

A fresh no-persistence follow-up reviewed candidate `1d2da681` and returned
`PASS`; receipt SHA-256 is
`384d471018a5e49eaa79b38221eb2541c128be172c9612bd25ccfe77dbaa4266`.
It mechanically confirmed deterministic contract-scoped score identity,
different-output replay rejection, complete Claude/Codex argv validation,
request/workspace binding, pre-unblind ordering, alias guards, source hashes,
v2 isolation, and adversarial coverage. Remaining risks are disclosed in the
implementation-review report and do not authorize execution by themselves.

## Prior Result

V2 remains terminal as `NO_ADVANCE_REVIEW_PROTOCOL_FAILURE`. Both returned
review packets self-identified as Claude and shared one stable base identity,
while the frozen scorer checked only unequal free-form strings. Its single
score pass also unblinded before two admissible reviews existed. V2 generation,
reviews, exploratory score, and map remain private failure evidence and are not
inputs to v3.

V3 is a new trial identity with a fresh seed commitment, execution worktree,
generation claim namespace, review receipts, structured responses, command records,
and single-use score claim. It is not a v2 retry.

## Frozen Question Set

The twelve question, retrieval-query, claim-rubric, abstention, and six-stratum
commitments are unchanged from v2 to preserve comparison scope. Exact prompts
and retrieval queries remain private under ignored `data/`; checked-in files
contain only their SHA-256 commitments. A later execution must make a fresh
capture against runtime source `1f75ede0` and must not reuse v2 capture or
generation bytes.

Conditions remain:

| Condition | Role | Capture |
| --- | --- | --- |
| `hybrid_retrieval` | Reference | Full hybrid search, limit 10 |
| `portfolio_digest` | Candidate | Direct read of the committed digest key |

The v2 coverage, deterministic context projection, raw-result retention,
single generation attempt plus narrowly authorized pre-model restart, exact
private-spec binding, canonical worktree binding, no answer postprocessing,
and marker/tool failure rules all remain in force.

## Generator

The generator remains Codex CLI `0.144.1`, model `gpt-5.4`, reasoning effort
`medium`, one process per answer, in an empty ephemeral read-only workspace.
User config and project rules are ignored. Tools, MCP, repository access, web,
memory, and external facts are forbidden. This preserves the v2 generator
comparison while giving v3 a fresh capture and execution identity.

No generator process is invoked by this preregistration.

## Fixed Review Roster

| Slot | Provider | CLI | Model | Effort | Generator overlap |
| --- | --- | --- | --- | --- | --- |
| `reviewer_anthropic_opus` | Anthropic | Claude Code `2.1.207` | `claude-opus-4-8` | CLI default | none |
| `reviewer_openai_sol` | OpenAI | Codex CLI `0.144.1` | `gpt-5.6-sol` | `max` | same provider, different model |

The two review slots are different provider families. They are fixed headless
model reviews, not human reviews. `reviewer_openai_sol` shares OpenAI provider
family with the generator, so the trial does not claim generator-reviewer
provider independence. Claude effort remains the version-pinned CLI default
because the owner-approved, smoke-tested command profile did not set an effort
flag; the receipt must record `reasoning_effort_pinned_in_command=false`.

The scheduler has authored some evaluated portfolio material. After freeze it
may only forward the deterministic request and record outputs; it may not edit
prompts, blind packets, model responses, judgments, or review order. These
conflicts are explicit contract and receipt fields.

Gemini is not in the roster and is not permitted as fallback, replacement, or
retry.

## Review Provenance

Each review slot gets one invocation and zero retries. It runs from an empty
workspace with no project context, MCP, or tools. The only substantive request
is the fixed review instruction followed by the exact blind packet and fixed
reviewer slot.

Before unblinding, score requires one private mode-0600 object for each item in
each slot:

- completed review packet;
- custodian review receipt;
- full command record;
- exact structured model response, byte-identical to the review packet.

The receipt binds contract, blind packet, slot, provider, model, reasoning
policy, CLI/version, parsed command profile, command bytes, deterministic request,
structured response/review bytes, session identity, usage record, timestamps,
single invocation, zero retries, empty workspace, no tools/MCP/project context,
and the slot-specific COI disclosure. The review packet contains a fixed
`reviewer_slot`; free-form reviewer strings and self-attested independence are
not accepted as provenance.

The command record is strict JSON. It binds slot, absolute empty-workspace cwd,
stdin request hash, zero context-environment keys, and the complete normalized
Claude or Codex argv. Model and effort are therefore checked against command
content rather than trusted receipt Booleans. Any missing, substituted,
duplicated, permission-broad, or hash-mismatched provenance input stops before
generation or blind-map bytes are read.

## Blinding Changes

Answer ids remain seed-derived and opaque. In v3, each semantic
`forbidden_claim_id` is also replaced in the blind packet by a deterministic
`forbid_<24hex>` id. The private map binds each opaque id back to the frozen
contract claim. Required claim anchors remain visible because they define the
fixed scoring rubric; only forbidden labels that previously leaked temporal
truth hints are hidden.

The scorer validates both complete reviews and their provenance before it
creates a private single-use score claim. The claim path is not supplied by an
operator: it is deterministically keyed by the frozen contract SHA-256 in a
fixed ignored directory. Only then may the scorer open the condition-labelled
generation and map. Creating the claim consumes the sole unblinding allowance
even if a later map or score check fails.

## Scoring And Decision

V3 retains the v2 deterministic claim, currentness, unsupported-assertion,
usefulness, abstention, preference, non-inferiority, efficiency, and six-
stratum thresholds. Every absolute and comparative gate must pass separately
for each reviewer and each stratum. Reviewer means are never pooled to rescue
a failed slot.

The public score may report each fixed model/provider slot and exact
cross-reviewer agreement counts. Agreement is diagnostic only and is not a
gate. The OpenAI generator-reviewer overlap remains visible alongside each
reviewer's result.

A complete pass may recommend only preregistration of a separate write-side
trial. It cannot authorize digest writes or regeneration, runtime/retrieval
changes, benchmark claims, deployment, CI, release, version, or tag actions.

## Stop Conditions

| Event | Disposition |
| --- | --- |
| Capture coverage invalid | Stop before generation; no retry |
| Generator pre-model infrastructure failure on attempt 1 | At most one receipt-authorized full restart |
| Generator starts a model and then fails | Terminal; no retry |
| Review command/model/CLI/request/response/review mismatch | Terminal before unblinding |
| Review uses project context, MCP, tools, or a retry | Terminal before unblinding |
| Review slot missing, duplicated, substituted, or out of order | Terminal before unblinding |
| Deterministic contract-scoped score claim already exists | Reject replay before unblinding, including a new output path |
| Failure after score claim creation | Terminal; no replacement review or rescore |

## Verification

The v3 verifier exercises the full synthetic 12-case/24-answer blind and map
chain, both review slots, per-reviewer scoring input, agreement diagnostics,
receipt success, and adversarial mutations. It confirms command, request,
response, review, model, retry, workspace, tool, MCP, project-context, COI, and
score-replay failures, including a rehashed wrong-model command and replay
with a different score output path.

```bash
python3 -m py_compile \
  scripts/eval/portfolio_continuity_successor_v3_trial.py \
  scripts/verify-portfolio-continuity-successor-v3-prereg.py
python3 scripts/eval/portfolio_continuity_successor_v3_trial.py \
  validate-contract \
  --contract scripts/eval/fixtures/portfolio_continuity_successor_v3_answer_contract.json
python3 scripts/verify-portfolio-continuity-successor-v3-prereg.py
bash -n scripts/verify-portfolio-continuity-answer-trial.sh
git diff --check
```

Historical v0-v2 verification is run from its frozen documentation binding
`dbf98d506463689a0db8a8a89bb4cc8329e59c52`, where all three protocol
verifiers pass. Current master has a later retrieval-surface helper hash and
therefore correctly cannot execute the source-bound v2 contract directly.

## Repository Files

```text
scripts/eval/portfolio_continuity_successor_v3_trial.py
scripts/eval/fixtures/portfolio_continuity_successor_v3_answer_contract.json
scripts/verify-portfolio-continuity-successor-v3-prereg.py
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-successor-v3-protocol-prereg.md
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-successor-v3-implementation-review.md
```
