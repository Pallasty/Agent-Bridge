# Memory derivation improvements

## Authorization and goal

On 2026-10-25 the owner said, “很好！那我们就基于你的分析结论和建议，规划并落地目标。”
This changes the preceding research-only scope to planning and implementation.
The implementation choice below is the working agent's, not a separately
specified owner requirement. It does not reopen held collection campaigns.

The intended outcome is to prevent derived memories from carrying withdrawn
evidence forward as current knowledge. Implement this in finite increments at
existing entry points, retaining original records and reviewable failure reasons.

Research inputs: RuVector `c44d7337c0c5ad2ecd2294178475387facb96516`, Hindsight
`4822d66e093dadfd6b2b80186fd0395ef80926ca`, and AB baseline
`9e2f22c53a9495c7ba9c9d7e24cb436cde4bf4c1`. These were static source reviews,
not executed product comparisons. RuVector suggests diversity-aware selection;
Hindsight suggests source-dependent invalidation, evidence budgets, and structured
delta edits. Neither establishes natural-task benefit for AB.

## First increment: withdrawn sources block digest promotion evaluation

The demonstrated defect is in `scripts/eval/digest_gate.py`: retrieval hit and
non-regression scores could be evaluated without checking the lifecycle of the
draft's sources. A source marked superseded still reached process startup.
The initial regression test reproduced this on an isolated SQLite fixture.

- Recent real problem: an existing promotion entry accepts withdrawn sources
  for evaluation; source inspection and a regression fixture establish the defect.
- Natural occurrences in the last 30 days: unknown; fixtures are not incidents.
- Owner cost per occurrence: unknown.
- Smallest closure: reject ineligible sources before launching MCP or materializing
  a candidate, explain why, and leave the original database unchanged.
- Increment: add a read-only prerequisite to the existing gate and test it.
- Doing nothing: ranking PASS can continue to be mistaken for source validity.

### Acceptance

1. Read the draft and sources in one read transaction on the existing shadow copy.
2. Reject missing/inactive drafts, wrong draft types, non-author or malformed
   provenance, empty/duplicate/mismatched source lists, and more than 12 sources.
3. Reject missing, archived, superseded, tombstoned, conflict, or unknown-status
   sources, including an active row with a replacement pointer.
4. Reject sources with unknown update times or updates later than draft creation.
5. Reject the author's known non-primary source kinds. Do not walk arbitrary
   `related_keys` as if every relationship were a derivation dependency.
6. Rejection produces `BLOCKED_SOURCE_LIFECYCLE` in the JSON report, nonzero exit,
   no MCP startup, and cleanup of the temporary copy.
7. Active, eligible primary sources proceed to the existing retrieval checks;
   passing this prerequisite alone never produces overall PASS.
8. Reports explicitly retain `source_revision_verified=false` and
   `answer_validated=false`. No source contents appear in rejection reasons.

### Limits

Legacy draft records preserve source keys but not source content hashes, despite
the older design document describing a full manifest. Timestamps cannot establish
byte identity: same-second edits, imported/backdated edits, and edit-then-restore
are not detected. An older timestamp is not proof of unchanged content.

This check covers the frozen copy only. It does not establish current remote
source freshness, semantic entailment, access-scope suitability, independent
support, or task benefit. It does not update/delete existing live digests or block
their ordinary retrieval. The manual promoter must recheck current sources and
review claims before saving; this is not an atomic live promotion guard.

No new scheduler, LLM call, MCP tool, schema migration, runtime deployment, or
automatic promotion is introduced. Existing draft-author behavior is unchanged.

## Second increment: bind the material actually supplied to the author

Owner continuation: “很好！按照你的思路规划并落地下一目标。” The selected
increment extends the existing author/gate pair with source revision bindings.
It does not activate background refresh or invalidate already-promoted rows.
The first increment and its recorded results above remain historical.

The reproduced gap is a same-second source edit: lifecycle remains active and
`updated_at` remains unchanged, so the first increment accepts different content.
Natural incident count and owner cost remain unknown. The smallest closure is to
capture versions when authoring and require those versions at evaluation.

### Format and custody

`build_digest_draft_record` adds `source_bindings` to the persisted JSON packet,
overwriting any field of that name emitted by the model. It uses the same
in-memory manifest that produced the model prompt, not a later database read.
Every manifest row is bound, including material not cited in the final draft.
The envelope schema is `ab.digest.sources.v1`, with a `sources` array of
`{"key": ..., "sha256": ...}` entries. It remains inside the existing draft
record; no new table or daemon is introduced.

The hash is SHA-256 over UTF-8 compact JSON of this ordered array:

```text
[key, kind, scope, content, tags, related_keys, created_at, updated_at,
 status, superseded_by, trigger_pattern]
```

Strings and list order are preserved, with no Unicode normalization. Nullable
fields remain null. Rust and Python share fixed encoding vectors with Chinese,
emoji, escaping, a NUL, and U+2028. Access counters, last-access time, ranking
importance, and embeddings are intentionally excluded: this is a fingerprint of
author material and lifecycle metadata, not every stored byte.

### Acceptance and compatibility

- Reject missing/unsupported bindings, duplicates, malformed hashes, incomplete
  cited-source coverage, and more than twelve bound rows before MCP startup.
- Compare every bound row in the same read snapshot used by the lifecycle check.
  Content, scope, tags, relationship, or timestamp changes invalidate the binding.
- Retain missing/non-active/replacement-pointer checks even when a hash matches.
- Legacy drafts without bindings are retained but blocked. Never backfill their
  hashes from today's database: that would invent the version the author saw.
- Release the updated author and gate together. The previously installed binary
  still emits unbound drafts until an explicitly performed build/deployment;
  do not weaken the gate to accommodate that older producer. Regeneration uses
  the updated producer and the existing reviewed workflow, not an automatic job.
- Successful checks set `source_revision_verified=true` for these bound fields
  in the frozen copy only; `answer_validated` remains false.
- A deleted/recreated row with a different creation time or other bound field is
  rejected. An identical recreation with all bound fields restored is
  indistinguishable. This is snapshot equality, not an immutable generation log.
- Binding data is host-generated metadata, not a signed receipt. Deliberate
  rewriting of the whole draft/bindings in storage is outside the threat model.
- Manual promotion still needs current-source and claim review. A source can
  change after the snapshot; this change does not make live promotion atomic.

The previous first-increment statements that revision verification is always
false and author output is unchanged are superseded for new bound drafts only.
No claim is made about model honesty, semantic entailment, deployment, or task
benefit. This is version binding at the existing draft/promotion boundary;
invalidation propagation to existing live digests remains a separate decision.

Second-increment verification commands (real-disk Cargo target required):

```sh
CARGO_TARGET_DIR=/Data/CascadeProjects/agent-bridge/target CARGO_BUILD_JOBS=4 \
  cargo test -p ab-bridge --lib dream_digest::tests
PYTHONDONTWRITEBYTECODE=1 python3 -W error::ResourceWarning -m unittest discover \
  -s tests -p test_digest_gate_provenance.py -v
```

The producer's original shape test failed before implementation because
`source_bindings.schema` was null. The consumer's same-second content/scope/tag/
relationship/trigger tests also failed on the first-increment implementation.
The shared encoding fixture is `tests/fixtures/digest_source_revisions_v1.json`.

Second-increment result (2026-10-25): all 19 `dream_digest` Rust module tests
passed, including producer binding, host override of model metadata, uncited
material, and shared encoding vectors. All 20 Python tests passed with
ResourceWarning promoted to an error. The Rust build emitted existing warnings
elsewhere in the crate; this is not a warning-free build or a full-workspace test
claim. `git diff --check` passed. Implementation remains in the local worktree;
no installed binary, runtime memory, scheduled collection, or CI was changed.

## Third increment: current-use admission at memory_get

Owner continuation: “很好！按照你的思路规划并落地下一目标。” This accepts
the preceding proposal to stop already-promoted digests serving as current
evidence after source withdrawal, initially at one existing read entry point.
The selected entry is MCP `memory_get`; search, bootstrap, `fetch`, exports and
direct Store reads are not covered by this increment. No global action guard is
claimed. Natural incident count and owner cost remain unknown.

### Delivery and acceptance

- The promotion script carries the verified `source_bindings` into a reserved
  `digest_sources_v1:` tag and keeps the complete save parameters in a PASS
  report. Model-supplied tags in that namespace are replaced. FAIL reports do
  not provide manual promotion instructions.
- A bounded exact-key read API admits at most 13 unique keys, each at most 4096
  bytes, and reads them in one SQLite transaction without any telemetry writes.
  Unsupported backends cannot substitute sequential reads and call them a snapshot.
- `memory_get` checks kind=`digest` before its normal access/feedback path. It
  snapshots the digest plus its at-most-12 bound sources, verifies the digest
  has not changed since selecting that source set, and evaluates source hashes,
  lifecycle and compatible scope. It never follows replacement pointers to
  silently bless a stale conclusion.
- A valid digest returns its ordinary record and an explicit current-use
  assessment. A changed/missing/retired source or retired digest yields
  `needs_review`; missing/invalid bindings or unavailable verification yields
  `unknown`. Both withhold the body from this endpoint, with `content=null`,
  `eligible_for_current_use=false`, and no proactive hint. The retained row is
  not rewritten, archived, or deleted.
- No-bound legacy digests stay unknown; no source bindings are fabricated from
  today's rows. Source content is never included in assessment diagnostics.
- Reads classified as digest at the initial peek do not bump access counters
  or emit retrieval-use/coactivation events. Non-digest `memory_get` retains
  its existing behavior. If a concurrent writer converts an ordinary row into
  a digest after that peek, the second guard still withholds unverified content,
  but the ordinary get may already have incremented its access counter.
- Snapshot validity is not semantic correctness, authenticated provenance, or
  an execution authorization. `answer_validated` remains false. A source can
  change after the read transaction; no use-time lock is promised.

### Executed verification (2026-10-25)

The new legacy-digest MCP regression first failed on the old read path because
it returned unverified content. With the guard installed, all of the following
passed on this working tree:

- 5 `digest_read` Rust tests, using real temporary SQLite files, read-only store
  connections and the actual MCP reader; includes byte-identical database
  checks before/after reads, same-second source edits, lifecycle withdrawal,
  replacement refusal, malformed bindings, scope mismatch, concurrent digest
  change, batch bounds/order and tombstone redaction.
- 1 legacy-digest MCP regression; retained body and zero access count verified.
- 1 existing ordinary-memory save/get/search continuity regression.
- 19 existing digest-author Rust tests, including shared hash vectors.
- 20 Python promotion-gate tests with ResourceWarning treated as an error;
  promotion preserves exactly one verified binding tag and complete PASS save
  arguments, and FAIL omits manual-promotion instructions.

Rust was built with `CARGO_BUILD_JOBS=4 cargo test -p ab-bridge --lib digest_read`
and `CARGO_TARGET_DIR=/Data/CascadeProjects/agent-bridge/target`; the remaining
Rust filters ran against that freshly built `ab_bridge-6cd8bffe4f1d59ba` test
binary. Logs: `/tmp/ab-digest-read-{green,unbound,ordinary,author,python}.log`.
The build reported existing warnings; no full-workspace test result is claimed.
These are local source regressions, not deployment or natural-task value proof.

Deployment remains separate. The author, promotion script and guarded reader
must be released together; this local source change does not activate the
installed MCP binary. Other read surfaces and live-memory migration remain
explicit follow-up decisions, not implied coverage.

## Remaining follow-up decisions

2026-10-25 read-only use audit: **NO_ADMITTED_CASE / HOLD_EXTENSION**. The
connected store had no typed digests or bound-source tags and no retained
per-key exposure/task-outcome chain. Existing tool-call counts do not establish
harm or benefit. The finite diagnostic is closed; no active sample pursuit or
automatic next implementation is opened. See the
[audit, scope limits and reopening condition](../reports/2026-10-25-digest-natural-use-audit.md).

| Candidate | Question to settle before implementation | Acceptance direction |
| --- | --- | --- |
| Other derived-memory read surfaces (not started) | Which search/bootstrap surface actually needs the same admission semantics and how will it account for withheld results? | No bypass claim until each consumer is integrated and tested; preserve history and unknown states |
| Diversity selection with evidence budgets | Do real bootstrap results crowd out distinct necessary evidence under a fixed token budget? | Paired frozen-corpus comparison; protect commitments/constraints first; measure answer completion, harmful recall, tokens, and retained provenance |
| Structured incremental digest refresh | Is repeated whole-document rewriting causing observed drift or measurable owner cost? | Untouched blocks remain byte-identical; edits cite live source revisions; rejected edits preserve the previous document |

HNSW, SONA, wholesale memory-store replacement, and automatic knowledge-page
maintenance are deferred. Each follow-up requires its own concrete entry point
and evidence; this document is not an instruction to run all candidates in order.
Historical invalid or held evaluations remain closed.

## Verification

Run the focused regression suite without accessing the live memory database:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p test_digest_gate_provenance.py -v
```

The CLI regression uses an intentionally nonexistent binary: source rejection
must happen before any attempt to launch it. Tests use real temporary SQLite
databases and compare original bytes before/after. They cover the prerequisite
and its CLI rejection route; they do not execute installed MCP retrieval or prove
natural-task benefit.

2026-10-25 result: 12 focused tests passed with ResourceWarning promoted to an
error. The original CLI regression first failed because no source-lifecycle
verdict was produced and process startup was attempted; after the change it
returns the expected rejection before startup. The eligible-candidate test uses
a substitute external MCP boundary and checks both retrieval PASS and regression
FAIL, without bypassing the new prerequisite or writing to the source database.
This is source/test completion for the first increment only, not deployment or
completion of the ordered follow-ups above.
