# BioCortex Track B T09 content-identity and quarantine-custody authority decision v1

Date: 2026-07-18

Status: one exact reversible isolated-lab T09 implementation unit becomes
authorized only after ordinary integration and this decision's full gate.

## Decision

The owner directive authorizes exactly this successor:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_SYNTHETIC_EXACT_T08_RECEIPT_RAW_FRAME_SHA256_CANONICAL_FRAME_SHA256_PACKET_ID_SHA256_SIGNATURE_SUBJECT_SHA256_AND_VALIDATION_SUBJECT_SHA256_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`

The authority is single-use in intent, non-transitive, default-off, and limited
to reversible code, schema, nonsecret public synthetic fixtures, tests and
documentation. The decision full gate activates but does not consume it. Only
the later exact successor integration and its full gate may consume it. Global
single-use is not claimed because no external authority ledger exists.

The semantic actor is `pallasting / PROJECT_OWNER`, derived from the established
project profile and current-session continuity. No signature, cryptographic
identity proof, trusted decision timestamp, runtime owner decision or production
authority was observed.

## Exact T09 contract

T09 is the `CONTENT_IDENTITY` threat. Its detached request is closed-world and
contains exactly five lowercase SHA-256 values, in this order:

1. `raw_frame_sha256`
2. `canonical_frame_sha256`
3. `packet_id_sha256`
4. `signature_subject_sha256`
5. `validation_subject_sha256`

The separately injected policy has two ordered profiles: managed, then
self-hosted. A profile matches seven exact ASCII dimensions: T08 receipt content
SHA-256, its `track_id`, and the five request values. Zero or multiple matches,
omission, additional fields, wildcard, prefix, hierarchy, inheritance,
normalization or cross-track substitution reject fail-closed.

The future API has twelve public inputs. `mode` is syntactically last but is
observed first. Production and unknown modes reject before every other input.
In `SYNTHETIC_KAT`, the frozen T08 reviewer is called exactly once. Only after
success are the five identities derived; T09 policy is observed before the
detached T09 request, and the request is observed last.

For these exact KATs, T01 accepts only frozen canonical frame bytes. Therefore
raw and canonical SHA-256 are deliberately equal; this is not a general
production canonicalizer claim. Packet identity uses the length-prefixed domain
`AB_TRACK_B_T09_SYNTHETIC_PACKET_ID_V1`. Signature subject is SHA-256 of the
exact T05 length-prefixed track signature domain plus unchanged frame bytes.
Validation subject is the T08 receipt content SHA-256. Track and validation
subject may come only from the real T08 receipt, never the detached request.

No caller-supplied predecessor receipt is accepted. T09 does not reparse or
reserialize the frame, invoke T08 more than once, or derive policy from the
frame, authentication bundle or request.

## Semantic boundary

The historical control is `QUARANTINE_CUSTODY`; T09 failure is
`E_PRODUCTION_CUSTODY_FAILED`. The production design calls for distinct raw and
canonical hashes plus append-only custody. This local component binds identity
values only. It does not create a quarantine store, append-only log, retention
record, tombstone, replay CAS, or production canonicalization mechanism.

T08 (`SUBJECT_BINDING`) is the released predecessor. T09 alone is authorized by
this decision. T10 freshness and later replay/custody-chain units remain
unauthorized. A match authenticates none of the real content, packet, signature
or validation subjects and accepts no evidence or output claim.

## Frozen predecessor

The logical baseline and sole source parent is the released T08 integration
`34b2d815b7439b346883bdfdebcd34640533a334`, tree
`a844741d20b8697fdfc70d1ae98e89e509139173`, with ordered parents
`34b1c7e6ca9c2b75fd2ef3cf418a444353059511` and
`4317400912b703a771eb2ca908a594d27b6e02b8`.

The T08 source is `4317400912b703a771eb2ca908a594d27b6e02b8`, tree
`48674e5ff95dc9c3b31d813c42c4bc18290277b3`, with sole parent
`8521ff6a9784a6d74be2b8ee0e02f3aba6b9f8a5`. Its full receipt is 84
lines with SHA-256
`4975b65754527caf6c54c0cc2b2a9674e8fd8b8e5c783a9874148c50a43db6f8`
and records `CONSUMED_SCOPE_COMPLETE`. The fast receipt is 84 lines with
SHA-256
`53a05c12cc1103013cd753ea78a5bda3c3cab8751162494162e36387ffbc90a9`.

## Artifact binding

The five non-self-referential current artifacts are frozen as follows:

| Artifact | SHA-256 |
|---|---|
| decision reviewer | `1b3997d1435a304c4e9698e207b5788ce681ff7a3bcd0379ee7c603b0ff41aa7` |
| independent checker | `823d7d71ec91f5c9cd8862fcf37d680b63054cf61ae333a4d2918a0eb883ac65` |
| owner decision record | `0d1debb201c51a9bafdbd9a391776be70e95fe5745500172a26bb697d62a61b3` |
| expected receipt TSV | `474e032fa99f8e83dbe8fb30ce71367de2d6f7a18e90d9f4f817cd82ffea3388` |
| pack manifest | `795f9b7f9f43175174e65544dd9b91d5d530437771439df31088d0de457c3eb6` |

The eight predecessor artifacts are frozen by raw SHA-256:

- receipt schema: `40d23b17f45f0c4cec7fa83e76b6edbf3616d3cb70a5466a3a111d33bab0c841`
- implementation report: `0e74e74869826145ef0ccc100793bbb5bc39416398104d68587ba820afa189b9`
- source-bound gate: `c352cd166d0a89efe1568bb45f0c86915e319bb3c9b6d48bcce70e83480a21b1`
- reviewer source: `2752e8b4ca393f5db14d7c980e65a5a71cdbff38a4eb19c861fffe5cc3ffc7f8`
- checker source: `54a37862f166d524791914239299529a746809a3b5b3305f04273cba856b6e10`
- expected TSV: `f08708c42399e94064b1452cfbccaa287462fc18e236b9daed96217affd5f4a4`
- synthetic fixture: `ab966ecef10652730b752f3308326f8fdba9cf61a3b688cfe421efc3788567c6`
- pack manifest: `efec8f434b3e957d8a2229cecc0172b9da69a14039dede8b94f7e137ae9d24fe`

The T09 semantic fixture is frozen at
`3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6`.
It retains all 14 production controls and 20 threats; offline conformance cannot
satisfy the production custody control.

## Deterministic review contract

The normal checker emits 78 unique TSV keys. The self-test emits 16 lines and
exercises 764 directed negatives: 11 JSON guards, 40 closed-world mutations,
423 complete grounding mutations, 34 identity/profile boundary mutations, 156
overclaim mutations, nine section hashes, 78 receipt fields and 13 source-AST
mutations.

The successor requires two distinct lanes:

- `CONTRACT_CONFORMANCE_REVIEW`
- `SECURITY_AND_SOURCE_BOUND_GATE_REVIEW`

Neither lane is production security approval.

## Resource and operational boundary

- external paid spend cap: zero in all currencies;
- network, endpoints, credentials, private keys and seeds: none;
- dependency fetches: forbidden; reference KAT uses Python standard library;
- workers: one; predecessor calls: one; private scratch: at most 64 MiB;
- frame: at most 1 MiB; policies: at most 64 KiB; requests: at most 16 KiB;
- permitted side effects: reversible local repository artifacts for the exact
  successor only.

Deep gates run as one foreground managed process and the same session is polled
to completion. Duplicate recursive replay processes are forbidden.

The released predecessor remains six isolated-lab components covering T01–T08.
This decision implements zero. Only the later exact successor may reach seven
components covering T01–T09. Production controls remain 0/14, runtime threats
0/20, prerequisites 0/16, evidence zero, downstream gates 0/4, and runtime and
provider authority false.
