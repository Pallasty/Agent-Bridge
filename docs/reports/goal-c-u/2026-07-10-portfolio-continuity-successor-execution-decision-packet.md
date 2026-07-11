# Portfolio Continuity Successor Execution Decision Packet

Date: 2026-07-10

Status: **TERMINAL / NO_ADVANCE_REVIEW_PROTOCOL_FAILURE**. The read-only
capture and fixed 24-cell generation matrix remain valid, but the later review
gate failed. Their public records are
`2026-07-10-portfolio-continuity-successor-capture-result.md` and
`2026-07-10-portfolio-continuity-successor-answer-trial-result.md`; the review
failure audit is
`2026-07-10-portfolio-continuity-successor-review-protocol-failure.md`. One
non-admissible custodian score pass and unblinding occurred. No runtime change,
CI action, release, tag, or version change occurred.

## Frozen Implementation

| Item | Binding |
| --- | --- |
| implementation commit | `e5c985d4916086bc3396ab28d2a4943b82f5df0a` |
| documentation binding commit | `dbf98d506463689a0db8a8a89bb4cc8329e59c52` |
| contract SHA-256 | `ef109025d1b7b7724295d075edbb7061a56f1e5a87faa643d8e6b55383f815dd` |
| harness SHA-256 | `af15d85758c4e5454a27a8f18a2e3101f60c5472c8fdc352a750ba5681e045ee` |
| surface SHA-256 | `0ff5ab27b79d36169fee22b5de5f2c4563cb1ba0f6edebf354a17cfcb60e6311` |
| canonical execution-worktree path SHA-256 | `70680947cae27b8b6d4650c3f905fa8379686bf7e465fa1baf3803a33bbc4935` |

The designated worktree remains detached at the implementation commit. Its
ignored private directories now contain the mode-restricted frozen input,
spec, runtime binary copy, capture artifacts, single-use attempt claim,
generation artifacts, blind packet, private map, review template, score
artifacts, and command receipts. The two reviews and custodian receipt
are retained in a separate mode-restricted private handoff root. None is
tracked by Git.

## Completed Checks

- `validate-contract` reports `VALID` for v2.
- The complete local synthetic verifier passes v0, v1, and v2.
- V2 adversarial coverage includes both whitespace-only private-spec changes
  and a same-commit alternate worktree; each is stopped before a model call.
- An external independent read-only review of `e5c985d4` returned `PASS` with
  no blocker and did not inspect `data/`, perform a real trial, or invoke CI.
- The execution commit's verifier fixture wiring is repaired in `dbf98d50`.
  The current public verifier passes from that binding and mechanically checks
  the frozen `e5c985d4` contract/harness bytes; the capture/generation harness
  itself is unchanged.
- The real capture validates against the frozen contract and has exact status
  `VALID` for all twelve reference-coverage cases.
- The capture performed 24 isolated condition runs, wrote no live memory, and
  called no LLM.
- A targeted post-capture read-only audit found no pre-generation blocker and
  retained the frozen capture. Its finding dispositions are recorded in
  `2026-07-10-portfolio-continuity-successor-post-capture-audit.md`.
- Immediate generation preflight confirmed the frozen worktree and hashes,
  exact `codex-cli 0.144.1` identity with empty stderr, valid coverage, fresh
  outputs, private permissions, and no prior attempt claim.
- The sole attempt-1 generation completed all 24 fixed cells using `gpt-5.4`
  with medium reasoning. It observed no tool events, applied no answer
  postprocessing, performed no retry, and produced no failure receipt or
  attempt-2 claim.
- Content-blind postflight validation passed the complete capture-generation-
  blind-map hash chain, deterministic blinding, review template, redacted
  completion marker, permissions, and public-summary leak guard.
- Two returned review packets bind the expected blind packet and pass the
  frozen validator mechanically. Both reviewer fields explicitly identify
  Claude and share one stable base identifier, so they do not satisfy
  the two-independent-human-reviewer gate.
- A parallel custodian line ran the scorer once. Its mechanical status is
  `NO_ADVANCE`, but the score is non-admissible because review provenance
  failed before unblinding. Audit did not rerun the scorer.
- The completed score has empty stderr. Post-score validation passed the full
  hash chain, output privacy boundary, semantic stdout equality, and all 14
  packet-slice calculations without rerunning the scorer. Those mechanical
  checks do not cure the reviewer-provenance failure.

## Generation Identity

| Item | Binding |
| --- | --- |
| capture SHA-256 | `0041ed29ec778ffce824755cb0c73025252f668ca876d7d5dcc3598c416c82f9` |
| generation SHA-256 | `c83f62ce88f2509667f949c1dd2ebca1410537f73a4ed49d595b62b1c635d368` |
| redacted generation SHA-256 | `eb7b94e1e14f6226507b101b4bda4b5aceedf2a1647bbf163a8fb4f254941c3c` |
| blind packet SHA-256 | `12a1364f59ee970956e289823608641dd83747e605fb7308ebfa4e221c416c0b` |
| private blind map SHA-256 | `e80693737e4afb0204cf3dd7b108c6011504f92d18364594945d5b70539b8b80` |
| review template SHA-256 | `016dfdbd34a61f0a38c748f8256796caaab6f191961c089df4518401c89f45fd` |
| attempt-1 claim SHA-256 | `fc0967830ca7082a646a2679f91075a327ba43c75c2a3f31d06f0035a17469ec` |

## Score Identity

| Item | Binding |
| --- | --- |
| review 1 SHA-256 | `8d6874cb3084e7b0f7b98b6f6264bd310eaa2dfa032d14ff769304a7761b4a0b` |
| review 2 SHA-256 | `86188b8ee4f5435d886a46a35c0fa954861990f4306d04e582b1ccd4738d2e3a` |
| non-admissible score SHA-256 | `32bd54632fa342e481f57d17526a11358fd35ccc38209611efc0718e6e4cf065` |
| score stdout SHA-256 | `1edaa4f51179fc69c902c437996bc129253e4ad606e05d3242213070dbcc8328` |
| private reviewer declarations SHA-256 | `bed06056b4206fcc6ffc25bad6124468412ff6db6f513cb66bf453cf5b8a516f` |
| private custodian receipt SHA-256 | `e09992c837ed355c6b4dd26157d72ebd945e0f600e8386c4be8e5a08ff13254d` |

## Terminal Decision

1. The existing packets do not count as two independent human reviews.
2. The one scoring pass has been consumed and the private map opened before
   the valid review gate. This trial cannot be repaired by replacement reviews
   or a scorer rerun.
3. The formal outcome is `NO_ADVANCE_REVIEW_PROTOCOL_FAILURE`. The existing
   score is retained only as exploratory failure evidence.
4. Any future trial requires a separate preregistration and stronger
   custodian-verified reviewer provenance.

## Trust Boundary

The local claim latch prevents accidental or ad hoc retries within the bound,
managed worktree. It is not a tamper-proof multi-host ledger: an operator able
to delete/forge local private files or move execution to another managed host
falls outside this mechanism. A stronger guarantee would require a separately
authorized custodian-controlled append-only ledger or atomic service.

Within that boundary, two low-severity hardening limits remain: attempt 2 does
not reparse the existing attempt-1 claim packet, and score-time generation
validation does not repeat the generation-time forbidden-marker substring scan.
Both require private-artifact forgery and do not weaken the frozen
generation-time gate. A hard crash after a durable claim but before a receipt
can also consume the contract without a restart; this fails closed and must not
be repaired by deleting the claim. None occurred in this execution: the
redacted completion marker exists, the hash chain validates, and no failure
receipt or second attempt exists.

The score command has no technical replay latch. Governance authorized and
executed one scoring pass; post-score validation used only the completed score
packet and did not call the scorer again.

## Explicit Non-Authorities

The failed review protocol authorizes no automatic digest regeneration,
write-side preregistration, runtime promotion, retrieval-default changes,
benchmark claims, remote CI, release, version, tag, or deployment changes.
