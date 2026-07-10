# Portfolio Continuity Successor Answer Protocol Preregistration

Date: 2026-07-10

Status: **PRE-REGISTERED / IMPLEMENTATION VERIFIED / INDEPENDENT READ-ONLY
REVIEW PASSED / NOT EXECUTED**. This change defines and tests contract v2. It does not
perform a real capture, answer generation, blind review, unblinding, score,
benchmark, runtime change, version change, tag, release, or CI action.

## Identity

```yaml
schema: agent_bridge.portfolio_continuity_answer_contract.v2
contract_id: portfolio_continuity_successor_answer_blind_20260710
preregistration_base: 768f24aca039d82cf7b6bf748216d5a45900b432
contract_commit: e5c985d4916086bc3396ab28d2a4943b82f5df0a
contract_sha256: ef109025d1b7b7724295d075edbb7061a56f1e5a87faa643d8e6b55383f815dd
harness_source_sha256: af15d85758c4e5454a27a8f18a2e3101f60c5472c8fdc352a750ba5681e045ee
surface_source_sha256: 0ff5ab27b79d36169fee22b5de5f2c4563cb1ba0f6edebf354a17cfcb60e6311
runtime_source_commit: a8c6302325e27c9b5cb20f8c958ab719666de372
blind_seed_sha256: fc4dfdc5ef8f230996583dd9a9f5c79379316e4c9a36d8c52926053863c42579
digest_key_sha256: a9d9842db1fe7437ce4a276ddae9a1c91d776cd75606ec2269bb50fc7df21cf1
execution_repo_path_sha256: 70680947cae27b8b6d4650c3f905fa8379686bf7e465fa1baf3803a33bbc4935
case_count: 12
condition_count: 2
reviewer_count: 2
execution_status: NOT_EXECUTED
attempt_claim_scope: frozen_contract_sha256
capture_spec_binding: exact_private_spec_bytes
execution_worktree_binding: canonical_private_path_hash
```

The contract is frozen at the commit above. A later execution must use an
isolated worktree at that exact commit and a private spec bound to it.

## Review Gate

Three read-only independent review routes were attempted. The Codex reviewer
hit its usage limit, the Kilo reviewer exited without a review, and the Gemini
reviewer remained unavailable with provider 503 responses. None produced
findings, so none is counted as a completed review.

Local adversarial review found and fixed two retry-state issues before the
first v2 freeze: a retry receipt alone did not prevent a fresh attempt-1 rerun,
and internal claim files were not yet protected from output-path aliasing. A
subsequent read-only audit found one further fail-closed gap: changing only
private-spec JSON whitespace and recapturing could previously produce a new
claim identity. This revision supersedes that freeze. Each capture now binds
the exact private-spec byte hash, while the single-use attempt allowance is
scoped to the frozen public contract rather than mutable spec or capture bytes.
It also commits the canonical execution-worktree path hash, so a capture from a
different worktree or clone is rejected before it can create a separate local
claim namespace. Attempt 2 remains bound to its authorized receipt; claims
retain explicit private permissions and fsync and remain protected from
output-path writes.

An external Claude Code review completed on 2026-07-10 against implementation
commit `e5c985d4`, documentation binding `dbf98d50`, and decision packet
`0ec8c33c`. It returned `PASS` with no execution-safety blocker and did not
read private `data/`, execute a capture/generation, or invoke CI. The reviewer
statically verified contract/source/path hashes, retry derivation, exact
private-spec binding, alternate-worktree rejection, replay/coverage/semantic
failure behavior, and v0/v1 guards. This session separately ran the complete
public v0/v1/v2 verifier from current HEAD to a passing result.

The review records three disclosed limits. First, the execution commit's
public verifier fixture wiring is repaired by the later `dbf98d50`
documentation/verification binding; run the verifier from that binding or
later, where it mechanically checks the frozen `e5c985d4` contract and harness
bytes. This does not change the frozen capture/generation harness. Second,
the local claim latch is a managed-host guard rather than a tamper-proof
cross-host ledger, as stated below. Third, an invalid coverage capture sent to
`generate` intentionally consumes the single attempt-1 claim with no retry;
the operator must inspect the private coverage status before invoking
generation.

The independent review gate is therefore satisfied for this frozen
implementation. A later real execution still requires the separately recorded
owner decisions for capture and generation. Any implementation change requires
a new harness hash, contract hash, local verification, and independent review.

## Prior Result

The expanded v1 trial remains terminal as
`NO_ADVANCE_GENERATION_PROTOCOL_FAILURE`. Its valid capture was not scored:
the fixed generator emitted a forbidden condition or evidence marker, so no
generation packet, blind packet, blind map, reviews, unblinding, or score were
created. The canonical result is documented in
`2026-07-10-portfolio-continuity-expanded-answer-trial-result.md`.

Private inspection of the already-valid capture also showed that six of twelve
full-hybrid cases had zero hits, and internal implementation identifiers could
enter model context through record keys or content. Those observations motivate
a new protocol. They do not authorize an ad hoc rerun of v1 and are not reused
as answer-quality outcomes.

## Frozen Corpus

V2 retains the exact twelve v1 prompts, six strata, direct/held-out pairing,
rubric claims, two insufficiency cases, metrics, thresholds, and two-reviewer
all-gates aggregation. It adds one separately frozen retrieval query per case.

Checked-in material contains only prompt and query SHA-256 commitments. Exact
UTF-8 prompts, retrieval queries, and the new random seed remain under ignored
`data/`. Capture must verify both hashes before any retrieval call. Generation
still receives the original question; the retrieval query is used only to
construct the reference context.

## Fixed Conditions

The condition matrix is unchanged from v1:

| Condition | Role | Source |
| --- | --- | --- |
| `hybrid_retrieval` | Reference | Full hybrid search using the frozen retrieval query |
| `portfolio_digest` | Candidate | Direct read of the committed digest key |

Search remains hybrid, limit 10, excluding `skill`. Compact top-2 and session
bootstrap are not candidate conditions.

## Coverage Gate

Coverage is evaluated immediately after capture and stored in both private and
redacted capture packets.

- Every non-abstention case requires at least two unique reference keys.
- An abstention case may validly have zero reference hits.
- Duplicate reference keys invalidate capture.
- Generation requires exact coverage status `VALID`.
- `INVALID_REFERENCE_COVERAGE` stops before Codex identity observation or model
  invocation and emits a non-retryable private failure receipt.

This is a protocol-validity gate, not an answer-quality metric. It prevents the
reference condition from silently becoming an empty-context baseline on cases
where the rubric requires supported claims.

## Context Projection

V2 constructs model input deterministically before generation:

1. Preserve the private raw MCP result for audit.
2. Drop each record's `key` field from model-visible context.
3. Replace the five fixed internal identifiers with readable, fixed aliases in
   all projected string values.
4. Render canonical sorted JSON and bind its SHA-256, byte count, and token
   estimate.
5. Reject capture if any source identifier remains after projection.

This fixed projection does not generically scrub arbitrary key-like literals
that happen to occur in a record's substantive `content`; it removes the
record `key` field and aliases the five declared identifiers. That low-severity
residual scope is disclosed rather than expanded ad hoc after freeze.

The raw result is never reconstructed from projected context. Validation
instead recomputes the projection from the private raw result and requires
byte-identical context. Generated answers are not sanitized or rewritten. Any
forbidden marker in an answer is a semantic protocol failure.

## Failure Receipts

Every v2 generation command reserves a new ignored `--failure-output` path.
On a classified failure the harness writes one mode-0600 JSON packet through
the existing fsync-plus-atomic-replace writer. The packet includes only:

- contract, spec, and capture hashes;
- attempt number and prior-receipt hash;
- failure phase and machine error code;
- case, condition, and invocation coordinates when applicable;
- model-started state;
- answer SHA-256 and matched-marker SHA-256 when available;
- retry authorization and scope;
- explicit no-raw-material boundary flags.

It contains no prompt, retrieval query, context, raw answer, matched marker,
memory key, event stream, stderr, or reviewer data. Successful generation leaves
the reserved failure path absent.

## Retry Taxonomy

Automatic retry is forbidden.

| Failure class | Retry |
| --- | --- |
| Pre-model workspace, spawn, or Codex identity infrastructure failure on attempt 1 | One explicit full restart |
| Coverage gate failure | None |
| Any failure after any model process starts | None |
| Tool event, output schema, marker leak, or other semantic failure | None |
| Attempt 2 failure | None |

An explicit restart must present the complete first failure receipt. The
receipt must validate against the same contract, exact private-spec bytes, and
capture and must carry `retry_authorized=true`. Each v2 capture stores the
private spec SHA-256; generation rejects a supplied spec whose byte hash does
not match the capture before it can create a claim or start a model.

The contract also commits the SHA-256 of the canonical resolved execution
worktree path. `capture` and `generate` reject a spec whose resolved `repo`
path does not match it before opening the source database or creating claims.
This keeps the contract-scoped claim in one local namespace and blocks an
alternate worktree or clone from creating a fresh attempt 1.

Before either attempt, the harness creates a private single-use claim with
exclusive creation. Its allowance is scoped to the frozen public contract, not
to mutable private-spec or capture bytes; the claim packet retains both hashes
for provenance. Thus one contract permits exactly one attempt 1 and, only when
the first receipt authorizes it, one attempt 2. The attempt-2 claim binds the
first receipt hash. An unchanged receipt copied or renamed can represent only
that same single authorized restart; it cannot create an additional claim.
Changing a receipt breaks its hash binding. Starting another attempt 1 or
replaying attempt 2 fails before model invocation. Claiming consumes the
allowance even if that attempt later fails.

All v2 generation outputs must be fresh paths. The harness executes the matrix
once and has no retry loop.

## Generator And Review

The fixed generator remains Codex CLI `0.144.1`, model `gpt-5.4`, medium
reasoning, one independent process per answer, empty ephemeral read-only
workspace, ignored user config and project rules, no tools, no external facts,
and maximum 6000 answer characters.

V2 deliberately applies no answer postprocessing. The exact
`answer_markdown` string returned by the output packet is hashed, stored, and
blinded, including leading or trailing whitespace. Tool events and forbidden
markers invalidate generation.

Review and scoring retain the v1 two-reviewer, six-stratum, abstention,
absolute, non-inferiority, efficiency, and all-gates rules. A fully passing
score could recommend only preregistration of a separate write-side trial. It
would not authorize digest writes, regeneration, scheduling, deployment, or a
retrieval default change.

## Synthetic Verification

`scripts/verify-portfolio-continuity-answer-trial.sh` now verifies:

- historical v1 contract bytes against frozen commit `f472244f`;
- unchanged v0 and synthetic v1 success and adversarial behavior;
- v2 query/prompt separation and query use;
- raw-result retention with key removal and identifier aliasing in context;
- valid and invalid reference coverage;
- zero model calls after coverage failure or identity failure;
- atomic hash-only receipts for coverage, identity, and marker failures;
- exactly one explicit full restart and receipt replay rejection;
- zero retry after a model-started semantic failure, including a whitespace-only
  private-spec edit with both the original capture and a fresh recapture;
- alternate-worktree capture rejection before any source-database or model use;
- report, contract, harness, and surface hashes mechanically bound to the
  frozen contract commit;
- byte-preserving answers with no postprocessing;
- successful v2 generation, blinding, two-review validation, and scoring.

The verifier uses local fake Agent-Bridge and Codex executables. It does not
read the real memory store, call an LLM, or invoke remote CI.

## Execution Boundary

This preregistration stops before real capture. No successor capture,
generation packet, blind packet, map, review, unblinding, or score exists.
There is no automatic handoff from this implementation to execution. A later
operator decision must first complete independent review, bind the private spec
to the reviewed contract commit, and re-check binary, Codex, MCP, disk, and
process preconditions.

The local claim latch assumes one managed host, the committed canonical
worktree, and an operator who does not delete or forge private claim/receipt
files. It blocks accidental or ad hoc alternate-checkout retries; it is not a
tamper-proof, cross-host execution ledger. A stronger adversarial-operator
guarantee would require a separately authorized custodian-controlled append-only
ledger or atomic service, which this preregistration neither implements nor
authorizes.

Regardless of a future outcome, this protocol cannot authorize remote CI,
version or tag changes, release actions, runtime promotion, automatic digest
regeneration, compact-default changes, benchmark claims, or unscheduled reruns.
