# BioCortex Track B T10 freshness implementation authority decision v1

Date: 2026-07-19

Status: one exact reversible isolated-lab T10 implementation unit becomes
authorized only after ordinary integration and this decision's full gate.

## Decision

The owner directive authorizes exactly:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_FRESHNESS_SYNTHETIC_EXACT_T09_RECEIPT_TRACK_OBSERVED_AT_VALIDATION_CHECKED_AT_DECISION_RECHECK_AT_EXPIRES_AT_AND_MAX_AGE_SECONDS_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`.

The authority is single-successor in intent, non-transitive, default-off and
limited to reversible code, schema, public fixtures, tests and documentation.
This decision activates but does not consume it. Only the later exact
successor's ordinary integration and passing full gate may consume it. No
external ledger exists, so global single-use is not claimed.

The semantic actor is `pallasting / PROJECT_OWNER`, derived from the project
profile and current-session continuity. No signature, cryptographic identity
proof, trusted decision timestamp, runtime owner decision or production
authority was observed.

## Exact T10 candidate contract

The future API has fourteen public inputs. It extends the released T09 API's
eleven pre-mode inputs with a separately injected freshness policy, a detached
freshness request and `mode`. Mode is syntactically last but observed first.
Production, unknown and non-exact-string modes reject before every other input.
In `SYNTHETIC_KAT`, T09 is called exactly once; the freshness policy is observed
next and the detached request last.

The request is a closed five-integer object, in this order:

1. `observed_at_unix_seconds`;
2. `validation_checked_at_unix_seconds`;
3. `decision_recheck_at_unix_seconds`;
4. `expires_at_unix_seconds`; and
5. `max_age_seconds`.

The policy contains exactly two ordered rows, managed then self-hosted. Each
row matches seven dimensions: exact T09 receipt content SHA-256, its track and
the five request integers. Zero or multiple matches, extra fields, wildcard,
normalization, inheritance or substitution reject fail-closed.

The authorized arithmetic is:

`observed <= validation_checked <= decision_recheck < expires`

and both checked ages must be at most `max_age_seconds`. The two KAT profiles
use public nonnegative signed-int64 labels only. These values are not Unix-time
truth, trusted time or evidence currentness. No wall, monotonic, network,
provider or signed clock may be accessed.

## Semantic boundary

T10 covers stale-at-validation and stale-at-required-decision-recheck behavior,
with historical production failure `E_PRODUCTION_FRESHNESS_FAILED`. It does not
authorize or claim T11 clock-skew coverage, signed trusted time, maximum skew,
T12 owner TOCTOU, owner windows, real expiry/currentness, durable replay/custody
or production admission.

The released predecessor is T09 integration
`80d78735ebda85c62be0af82c0afb18b23bed975`, tree
`3f40474c9fcb40eb596b6dbf8537e27d9ac0bd06`, with ordered parents
`92fe2facf6f27c85ec0a34a8c46e045b1aaf67e1` and
`43a8d3bf88ac4e6b9271d5c9bda6766d867879a6`.

The current released surface remains seven isolated-lab components covering
T01–T09. This decision implements zero. Only a future exact T10 successor may
reach eight components covering T01–T10 after its integrated full gate.

## Resource and review boundary

- paid spend: zero in all currencies;
- network, endpoints, credentials, private keys and seeds: none;
- dependencies: Python standard library only, no fetch;
- one worker and one T09 predecessor call per success;
- private scratch at most 64 MiB;
- policy at most 64 KiB and request at most 16 KiB;
- two independent lanes: contract conformance and security/source-bound gate.

Neither lane is production security approval. Production controls remain 0/14,
runtime threat executions 0/20, prerequisites 0/16, real/validated evidence
zero, and runtime/provider authority false.
