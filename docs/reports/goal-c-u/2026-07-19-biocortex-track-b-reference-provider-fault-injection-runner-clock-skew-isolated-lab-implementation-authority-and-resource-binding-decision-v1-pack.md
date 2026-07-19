# BioCortex Track B T11 clock-skew implementation authority decision v1

Date: 2026-07-19

Status: one exact reversible isolated-lab T11 implementation unit becomes
authorized only after ordinary integration and this decision's full gate.

## Decision

The owner directive authorizes exactly:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_CLOCK_SKEW_SYNTHETIC_EXACT_T10_RECEIPT_TRACK_VALIDATION_REFERENCE_TIME_DECISION_RECHECK_REFERENCE_TIME_AND_MAXIMUM_CLOCK_SKEW_SECONDS_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`.

The authority is single-successor in intent, non-transitive, default-off and
limited to reversible code, schema, public fixtures, tests and documentation.
This decision activates but does not consume it. Only the later exact
successor's ordinary integration and passing full gate may consume it. No
external ledger exists, so global single-use is not claimed.

The semantic actor is `pallasting / PROJECT_OWNER`, derived from the project
profile, the current owner directive and session continuity. No signature,
cryptographic identity proof, trusted decision timestamp, runtime owner
decision or production authority was observed.

## Exact T11 candidate contract

The future API has sixteen public inputs. It extends the released T10 API's
thirteen pre-mode inputs with a separately injected clock-skew policy, a
detached clock-skew request and `mode`. Mode is syntactically last but observed
first. Production, unknown and non-exact-string modes reject before every
other input. In `SYNTHETIC_KAT`, T10 is called exactly once; the clock-skew
policy is observed next and the detached request last.

The request is a closed three-integer object, in this order:

1. `validation_reference_time_unix_seconds`;
2. `decision_recheck_reference_time_unix_seconds`; and
3. `maximum_clock_skew_seconds`.

The policy contains exactly two ordered rows, managed then self-hosted. Each
row matches five dimensions: exact T10 receipt content SHA-256, its track and
the three request integers. Zero or multiple matches, extra fields, wildcard,
normalization, inheritance or substitution reject fail-closed.

The public KAT profiles are frozen as follows:

| Track | T10 receipt SHA-256 | Validation reference | Decision reference | Maximum skew |
|---|---|---:|---:|---:|
| managed | `620dc08e2f8b41cac5bf0944b50ecc9d2435e59fb5c01e68544270ca94d03714` | 1,999,999,995 | 2,000,000,115 | 90 |
| self-hosted | `16c7b9228bf36329723376aba4f273f9356759037b4f31ca5a4adbf810bee14d` | 2,100,000,065 | 2,100,000,125 | 90 |

The authorized pure-integer arithmetic is:

- validation reference time is not later than decision reference time;
- absolute T10 validation-label minus validation-reference difference is at
  most `maximum_clock_skew_seconds`;
- absolute T10 decision-label minus decision-reference difference is at most
  `maximum_clock_skew_seconds`;
- when the T10 observation label is later than either reference label, that
  positive future-date difference is at most `maximum_clock_skew_seconds`;
- maximum skew is a nonnegative signed-int64 value no greater than 300.

The managed positive row intentionally makes the observation label five
seconds later than its validation reference while remaining inside the bound.
The self-hosted row exercises the opposite direction. A future implementation
must therefore use signed-direction-safe subtraction rather than a single
unsigned ordering assumption.

These values are fixed public labels, not Unix-time truth, signed time,
provider time or production currentness. No wall, monotonic, network,
provider, signed or trusted clock may be accessed.

## Semantic boundary

T11 targets the frozen `CLOCK_SKEW` threat: evidence is future-dated or its
reference-time skew exceeds the bound. The historical production failure code
remains `E_PRODUCTION_FRESHNESS_FAILED`. This isolated-lab decision does not
bind a real signed-time source and does not prove production clock truth.

It does not authorize or claim T12 owner TOCTOU, owner windows, real
expiry/currentness, durable replay/custody, production admission, fault
injection, output or claim authority.

The released predecessor is T10 integration
`135904ab64d369e5953ff5948a8c4231bf1eccf1`, tree
`b0f63ed0bcc5faf2243cd181f3bcca658bc5abdf`, with ordered parents
`60e5c0f1bbfc15349b8e0c18d32fde594eeafac4` and
`6727ef20372557ce240ccb1f1a4e2a22bcd2bea8`.

The current released surface remains eight isolated-lab components covering
T01–T10. This decision implements zero. Only a future exact T11 successor may
reach nine components covering T01–T11 after its integrated full gate.

## Resource and review boundary

- paid spend: zero in all currencies;
- network, endpoints, credentials, private keys and seeds: none;
- dependencies: Python standard library only, no fetch;
- one worker and one T10 predecessor call per success;
- private scratch at most 64 MiB;
- policy at most 64 KiB and request at most 16 KiB;
- exactly two frozen profiles and maximum skew no greater than 300 seconds;
- two independent lanes: contract conformance and security/source-bound gate.

Neither lane is production security approval. Production controls remain 0/14,
runtime threat executions 0/20, prerequisites 0/16, real/validated evidence
zero, and runtime/provider authority false.
