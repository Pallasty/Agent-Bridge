# Free Recall Strategy R5 — Source-Only Plan Result

Date: 2026-07-22

Status: **COMPLETE / PLAN GATE PASS / R6 SLICE A SOURCE ELIGIBLE**

Preregistration:
`docs/design/FREE_RECALL_STRATEGY_R5_SOURCE_ONLY_PLAN_PREREGISTRATION_2026_07_22.md`

Validator:
`scripts/eval/free_recall_strategy_r5_source_plan.py`

## 1. Verdict

R5 passed its item-reference, isolation, mutation, determinism, and zero-
authority gates. The observation-only design can be decomposed into three
separately gated source slices, beginning with pure contract types, a keyed
pseudonym derivation function, a synthetic key provider, and a no-op sink.

R5 implemented none of those Rust slices. It authorizes no dependency change,
source, migration, build, execution, real capture, retrieval change, merge,
deployment, or production key provisioning.

## 2. `item_ref` resolution

The selected design is full-length HMAC-SHA-256 over independently length-
framed domain, key epoch, and exact UTF-8 memory key bytes. The textual form is:

```text
epr_v1_<epoch>_<64 lowercase hex digits>
```

The epoch grammar is `[a-z0-9-]{1,32}` and excludes the `_` delimiter. Memory
keys are bounded to `1..4096` UTF-8 bytes and key material to at least 32 bytes.

This rejects the principal alternatives:

- raw or unkeyed identifiers permit direct or dictionary matching;
- random handles require a persistent reverse map or `MemoryRecord` field;
- reversible encryption adds plaintext-recovery authority that the sidecar
  does not need;
- truncated tags reduce collision and guessing margins without a useful
  storage benefit here.

The source plan requires a reviewed HMAC implementation; it does not authorize
handwritten cryptography.

## 3. Gate results

| Gate | Result |
| --- | --- |
| Canonical source plan | pass |
| HMAC known answer | pass |
| Domain separation | pass |
| Epoch authentication | pass |
| Memory-key binding | pass |
| Weak key rejection | pass |
| Invalid epoch rejection | pass |
| Empty/oversized key rejection | pass |
| Directed mutations | `47 / 47` rejected as intended |
| JSON key-order invariance | pass |
| Zero source/runtime authority | pass |

Canonical plan SHA-256:

`8dc52250bc257391b289c21c41aad94b720addceaf69786aa1af754f9820d33e`

Public-synthetic known-answer item reference:

`epr_v1_epoch-test-0001_a90c09a8eb687d7d9858979d1dbb9801ec68e73628053a7200609e8a341b9c04`

## 4. Independent determinism evidence

The standard-library-only validator passed `py_compile` and self-test locally
and in the isolated tb14 worktree. Both runs emitted the same aggregate report
SHA-256:

`5dd21e345763e3d7737f15dae56727c473c5035f473caa5fb93681c6da238ff4`

No database, MCP tool, private state, wall clock, environment secret, or
network input participates in the report.

## 5. Accepted source sequence

### R6 candidate — Slice A only

- private `ab-store` contract types;
- canonical length framing and HMAC-SHA-256 derivation;
- internal key-provider interface;
- synthetic provider in tests only;
- no-op sink;
- known-answer and fail-closed unit tests.

Slice A must contain no SQLite, runtime key loader, producer call site, MCP
surface, feature enablement, or observable behavior change.

### Later Slice B

An inert separate relation and store adapter, using the schema version current
when separately authorized. It must remain disconnected from `memories`, FTS,
vectors, graph/coactivation, sync/export, and retrieval. Rollback disables and
leaves the relation inert; dropping populated state is a separate destructive
gate.

### Later Slice C

One explicit `session_curate:curation_batch` producer. It opens before the save
loop, emits item events only after successful saves, and closes after the loop.
A crash leaves an incomplete episode that abstains. Slice C requires compile-
time and runtime gates plus a trusted key provider.

Neither Slice B nor Slice C is opened by R5.

## 6. Security and lifecycle boundaries

- Source accepts keys through an internal provider; no environment, CLI,
  logging, serialization, auto-generation, or unkeyed fallback is allowed.
- Missing provider or unknown epoch disables emission or causes abstention.
- Rotation uses a new authenticated epoch and never rewrites old events.
- Normal ingestion is append-only. The only proposed deletion exception is an
  explicit transactional whole-episode purge; partial purge is forbidden.
- Real erasure cannot be claimed until backups, exports, sync peers, retained
  epochs, and actual memory-deletion policy are independently bound and tested.
- Offline joins are bounded, in-process, do not persist reverse maps, and never
  feed retrieval.

Production custody remains unresolved by design. R6 Slice A must not smuggle in
a production provider.

## 7. Next authority boundary

R6 may begin only after explicit owner authorization for **Slice A source
only**. That authorization would permit the narrowly scoped Rust types,
deriver, synthetic tests, and no-op sink, but not dependency widening unless
named, build/execution, Slice B/C, private data, merge, or deployment.

## 8. Primary references

- RFC 2104: <https://www.rfc-editor.org/rfc/rfc2104>
- NIST MAC publications:
  <https://csrc.nist.gov/Projects/message-authentication-codes/publications>
- RustCrypto `hmac` 0.12.1:
  <https://docs.rs/hmac/0.12.1/hmac/>
