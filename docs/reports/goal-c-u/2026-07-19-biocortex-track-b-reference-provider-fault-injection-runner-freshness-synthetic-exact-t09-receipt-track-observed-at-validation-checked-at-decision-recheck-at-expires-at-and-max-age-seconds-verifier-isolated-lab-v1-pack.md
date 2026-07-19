# BioCortex Track B T10 synthetic freshness verifier v1

Date: 2026-07-19

Status: implementation candidate. It is released and consumes the exact T10
authority only after ordinary two-parent integration and the full gate pass.

## Implemented unit

This pack implements exactly the authority named by the T10 decision:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_FRESHNESS_SYNTHETIC_EXACT_T09_RECEIPT_TRACK_OBSERVED_AT_VALIDATION_CHECKED_AT_DECISION_RECHECK_AT_EXPIRES_AT_AND_MAX_AGE_SECONDS_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`.

The public API has fourteen inputs. Exact mode is syntactically last but is
observed first. Production, unknown and string-subclass modes reject before
any other input. In `SYNTHETIC_KAT`, the frozen T09 public verifier is called
exactly once, the separately injected freshness policy is reviewed next, and
the detached freshness request is observed last.

## Closed binding and arithmetic

The policy is canonical strict JSON with exactly two ordered profiles:
managed then self-hosted. Each profile matches seven dimensions:

1. exact T09 receipt content SHA-256;
2. exact T09 receipt track;
3. `observed_at_unix_seconds`;
4. `validation_checked_at_unix_seconds`;
5. `decision_recheck_at_unix_seconds`;
6. `expires_at_unix_seconds`; and
7. `max_age_seconds`.

The detached request is a closed five-field object. All five values must be
nonnegative signed-int64 integers, with booleans and floats rejected. Matching
is type-exact and value-exact; zero or multiple matches reject. Wildcards,
normalization, prefix, hierarchy, inheritance and substitution are absent.

After exact profile selection, the verifier requires:

`observed <= validation_checked <= decision_recheck < expires`

and both `validation_checked - observed` and `decision_recheck - observed`
must be at most `max_age_seconds`. Failures surface the frozen public code
`E_PRODUCTION_FRESHNESS_FAILED` plus a stable nested reason.

## Truth boundary

The integers are fixed public KAT labels. The implementation imports no clock,
OS, network, subprocess, filesystem, credential or provider capability. It
does not claim that the labels are real Unix time, signed trusted time or
production currentness. It does not cover future-dated/skew behavior (T11) or
owner decision-window TOCTOU (T12).

Successful receipts are closed at 90 fields and bind the five labels to the
exact T09 receipt chain. They report eight locally exercised isolated-lab
components and T01–T10 only. Production controls remain 0/14, production
runtime threats 0/20, prerequisites 0/16 and real/validated evidence zero.
Runtime/provider/output/fault authority remains false and side effects remain
`NONE`.

## Independent evidence lanes

The contract-conformance checker executes two real T09→T01 positive chains,
validates both 90-field receipts and freezes their content hashes. It also
executes 120 directed negatives:

- 4 mode/pre-observation cases;
- 11 policy JSON and 11 request JSON cases;
- 43 policy closed-world cases;
- 31 request field/type/value cases;
- 6 independently forced arithmetic failure cases;
- 12 predecessor receipt/track truth-binding cases; and
- 2 default-deny cases.

The security/source-bound lane adds 16 AST/capability guards and 20 fixture /
schema guards. The gate freezes all artifact hashes, the exact authority
baseline, the exact eight-path delta, source/integration blob identity, one
worker, one predecessor call and a 64 MiB private-scratch ceiling.

Source-fast validation does not release or consume authority. Only an ordinary
integration whose second parent is the exact source commit, followed by full
replay of the frozen T10 authority chain, may set
`CONSUMED_SCOPE_COMPLETE` and release 8 components / T01–T10.

No successor is authorized here. T11 requires a separate owner/resource
decision.
