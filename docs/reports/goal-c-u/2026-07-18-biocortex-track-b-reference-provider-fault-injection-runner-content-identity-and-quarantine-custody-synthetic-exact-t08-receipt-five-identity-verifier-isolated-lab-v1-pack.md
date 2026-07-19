# BioCortex Track B T09 exact five-identity verifier v1

Date: 2026-07-18

Status: frozen implementation candidate; release and authority consumption require
an ordinary two-parent integration and one passing integrated `full-replay` gate.

## Implemented unit

This packet implements only the authorized unit:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_SYNTHETIC_EXACT_T08_RECEIPT_RAW_FRAME_SHA256_CANONICAL_FRAME_SHA256_PACKET_ID_SHA256_SIGNATURE_SUBJECT_SHA256_AND_VALIDATION_SUBJECT_SHA256_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`.

It adds one pure, public-only synthetic KAT component. It binds five detached
SHA-256 labels to the unchanged frame accepted by the real frozen T08 chain and
to the exact receipt returned by that chain. It creates no custody store,
append-only record, retention/tombstone state, replay CAS or production
canonicalizer.

## Public contract and observation order

The function accepts exactly twelve public inputs: the nine pre-mode T08
inputs, a separately injected T09 policy, a detached T09 request, and `mode`.
Although syntactically last, `mode` is observed first. Production, unknown and
non-exact-string modes reject before every other input.

In `SYNTHETIC_KAT`, the verifier:

1. invokes the frozen T08 public reviewer exactly once;
2. derives the five identities from the unchanged frame and real T08 receipt;
3. validates the separately injected closed-world T09 policy;
4. observes and validates the detached five-field request last; and
5. selects exactly one seven-dimension profile or rejects fail-closed.

The request fields, in order, are `raw_frame_sha256`,
`canonical_frame_sha256`, `packet_id_sha256`, `signature_subject_sha256`, and
`validation_subject_sha256`. The two policy rows are managed then self-hosted.
Each row additionally binds the exact T08 receipt content hash and its track.
All values use exact ASCII equality. Wildcard, prefix, hierarchy, inheritance,
normalization, zero matches and multiple matches reject.

## Derivation and truth boundary

For the two frozen KAT frames, T01 already accepted exact canonical bytes, so
raw and canonical SHA-256 are intentionally equal. This is not generalized to
production canonicalization. Packet identity hashes the u64be-length-prefixed
domain `AB_TRACK_B_T09_SYNTHETIC_PACKET_ID_V1` and unchanged frame bytes.
Signature subject hashes the exact T05 per-track signature domain and frame
using the same u64be length prefixes. Validation subject is the exact T08
receipt content SHA-256. Track and validation subject never come from the T09
request.

Successful local review authenticates none of those real identities and
authorizes no output or claim. `QUARANTINE_CUSTODY` and
`E_PRODUCTION_CUSTODY_FAILED` remain the historical production control and
failure code; production controls implemented remain 0/14.

## Verification

The independent contract lane runs both real managed/self-hosted T08→T01
chains and 115 directed rejections: 4 mode guards, 11 policy JSON, 11 request
JSON, 43 closed-world policy, 31 exact request-field, 5 derived-identity, 8
predecessor-receipt and 2 default-deny cases. It also enforces 14 source-AST
and 18 fixture/schema guards. The receipt schema closes exactly 84 fields.

The separate source-bound gate freezes the eight-path delta, modes, hashes,
dependency archive, topology, checker stdout, checker self-test, and current
T09 authority replay. These are two distinct reviewer lanes, not production
security approval or two human identities.

## Authority consumption and next boundary

The exact source baseline is the released T09 authority integration
`35575397bfe4ec11278565e0221f46c17130efc4`, tree
`0cb2a7f5ca0e896e4219c4b75bb28ac8b5653faf`. Source `fast`, integrated
`fast`, and failed full gates do not consume authority. Only an ordinary
two-parent integration whose second parent is the exact one-parent source
commit, followed by a passing `full-replay`, consumes this unit and releases
the seventh isolated-lab component covering T01–T09.

T10 freshness is not authorized. Real evidence, runtime/provider authority,
network, credentials, paid resources, custody persistence, production
canonicalization and downstream action/output authority remain absent.
