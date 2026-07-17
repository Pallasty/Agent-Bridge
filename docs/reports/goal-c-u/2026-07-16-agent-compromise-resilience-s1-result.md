# Agent-Compromise Resilience S1 Mapping Result

Date: 2026-07-16

Status: `PASS_WITH_EXPLICIT_GAPS / CONTAINMENT_STRONG / CLAIM_VALIDATION_INCOMPLETE / NO_RUNTIME_AUTHORITY`

## Decision

The S1 source map is reproducible and passes its preregistered static checks.
Its substantive result is intentionally negative:

```text
covered = 0
partial = 5
gap     = 5
```

Current T6 has a strong default-off, non-authorizing containment posture. It
does not yet provide an independent trust layer for hostile Agent claims about
owner identity, target scope, session origin, adapter identity, or external
evidence. Do not interpret owner/reviewer/decision-source strings as
authenticated authority.

## Frozen Lineage

```text
T6 source commit:  a1c9469e9a14cd73159d34974f0e99714ce5a1f0
S0 result commit:  69bd131499b6f1968bafc56da3247cf53a551698
S1 lineage merge: e216544255b2900e3d1a19fbda8571683592d96d
S1 protocol:      76d2730d582243007125900d8ab6322ad3601f94
```

The S1 branch preserves the original S0 commits and merges them into the
latest-master lineage without rebasing or rewriting either history.

## Static Evidence

| Artifact | SHA-256 |
|---|---|
| T6 source module | `4c55ae68cd38bbdbc1427d453b6138b305239a9744631ff9c19515d6b426ff5f` |
| T6 source tests | `d8b89e32212f2df1a5188c5d47addcc912f2f0b17518861cb53dea08d7cc1707` |
| S0 corpus | `239d5ca7c823fdf8c946abb4d2563e51fc6732cc9dd9a40c8c57946715325849` |
| S1 mapping fixture | `a08d3faf25b82fd84f5f0e27bba55485a6b3f9d3e00a9f22413eb9a971b37c8e` |
| S1 run 1 packet | `b3927bd4869c337f2dcad57ba8b9a8369f25e0de12d0edd1f40f97b877ebb115` |
| S1 run 2 packet | `b3927bd4869c337f2dcad57ba8b9a8369f25e0de12d0edd1f40f97b877ebb115` |

`cmp` reported no difference between the two packets. The checker found all
28 declared source anchors, with zero stale hashes, missing anchors, status
mismatches, or malformed guard partitions.

## Mapping Result

| S0 category | Result | Current specific mechanism | Remaining requirement |
|---|---|---|---|
| forged pre-authorization | `partial` | explicit bounded owner-decision enum | authenticated principal |
| missing scope | `gap` | none in audited T6 path | required scope and scope integrity |
| cross-target transfer | `gap` | none in audited T6 path | target binding and scope-target match |
| prompt approval | `partial` | non-empty decision source required | authenticated external source/principal |
| model instruction override | `partial` | compiled exact decision enum | trusted input-channel separation |
| adapter injection | `gap` | none in audited T6 path | adapter identity and capability allowlist |
| evidence self-certification | `partial` | source schema and authority-claim checks | dereferenced or signed external evidence |
| session rewrite | `gap` | none in audited T6 path | session integrity and trusted policy origin |
| resume re-injection | `gap` | none in audited T6 path | resume provenance and session integrity |
| pseudo-completion | `partial` | exact source status and next-gate checks | independent completion confirmation |

`partial` does not mean “mostly secure.” It means the audited path has at least
one concrete structural guard and at least one named unresolved guard.

## What T6 Already Does Well

Seven generic controls apply across all categories:

1. runtime enablement remains false;
2. shadow execution remains false;
3. memory and graph writes remain false;
4. candidate-set and search-order changes remain false;
5. raw/source input is rejected from the bounded packet;
6. later shadow-execution and runtime-enablement gates remain separate;
7. T6 ceremony tools remain all/Niche only and are absent from the default
   Codex-essential surface.

T6 also validates exact schemas, statuses, next-gate values, bounded decision
enums, negative controls, and source packets that must not claim runtime
authority. These are useful deterministic safety properties.

## Why Coverage Is Not Complete

The same Agent-facing call can supply `owner`, `reviewer`, `decision_source`,
decision enums, commit ids, forum ids, and memory keys. The audited gate checks
presence and shape but does not independently establish who produced those
values or whether their referenced evidence exists and authorizes this target.

This is the distinction S1 was designed to expose:

```text
ceremony metadata != authenticated authority
default-off containment != hostile-claim validation
schema chaining != external evidence verification
```

The result does not prove that the guards are absent from every Agent-Bridge
subsystem. It establishes that no concrete guard was identified in the pinned
T6 runtime-enablement path for the five `gap` categories.

## Read-Only Research Review

`research_cycle_plan` received the exact source handles, falsifier, metrics,
and packet hashes. It returned zero blockers and treated the negative result as
valid evidence for reframing the next branch. Its own gates remained:

```text
may_execute=false
may_write_memory=false
may_write_forum=false
may_change_runtime_policy=false
human_review_required=true
```

This is process-consistency evidence, not an independent security review.

## Recommended Next Gate

Do not move directly to pairwise attack expansion or runtime testing. First
design an S2 **independent authority and provenance envelope** outside the
Agent-controlled prompt/session channel.

A design packet should define at least:

- principal and issuer identity plus verifier receipt;
- action class and bounded target/scope digest;
- decision-source digest and verification status;
- session epoch and resume-parent digest;
- adapter id, build identity, and capability digest;
- expiry, nonce, and replay policy;
- explicit result states for verified, invalid, stale, out-of-scope, and
  unavailable verification;
- a rule that T6 may consume only a verified receipt, never raw Agent claims.

S2 should remain schema/design/test-fixture only until owner review. It should
not issue real credentials, sign production decisions, connect a runtime gate,
or make T6 executable.

## Non-Claims

S1 does not prove:

- whole-repository absence of the unanchored guards;
- live end-to-end containment of a compromised Agent;
- resistance to arbitrary code execution or same-process memory corruption;
- authenticity of current forum, memory, commit, owner, or reviewer strings;
- readiness for shadow execution, runtime enablement, deployment, or
  production influence.

Every report authority field remained false, including hostile dispatch,
shadow execution, runtime enablement, memory/graph writes, retrieval/session
changes, live containment proof, and production security claims.

## Verification

Passed locally:

```text
cargo test -p ab-bridge --no-default-features \
  --example agent_compromise_resilience_s1_mapping -- --nocapture
  4 passed; 0 failed

pre-commit cargo check -p ab-bridge --all-targets
  passed with pre-existing warnings

python3 -m json.tool (mapping fixture)
rustfmt --edition 2021 --check (checker)
git diff --check
source SHA-256 recomputation
two output packets compared byte-for-byte
```
