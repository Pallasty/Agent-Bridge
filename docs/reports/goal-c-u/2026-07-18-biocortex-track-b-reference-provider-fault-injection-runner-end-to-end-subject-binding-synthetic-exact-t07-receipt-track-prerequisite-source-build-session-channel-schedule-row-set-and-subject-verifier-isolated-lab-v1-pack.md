# BioCortex Track B T08 exact end-to-end subject-binding verifier v1

Date: 2026-07-18
Status: frozen implementation candidate; release requires the ordinary two-parent
integration topology and one passing integrated `full-replay` gate.

## Decision

Implement only the authorized isolated-lab successor:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_END_TO_END_SUBJECT_BINDING_SYNTHETIC_EXACT_T07_RECEIPT_TRACK_PREREQUISITE_SOURCE_BUILD_SESSION_CHANNEL_SCHEDULE_ROW_SET_AND_SUBJECT_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`.

This packet adds a pure, public-only, synthetic KAT verifier. It binds eight
caller labels to the exact receipt returned by the frozen T07 public verifier.
It does not establish the real-world truth or currentness of those labels and
does not grant provider, runtime, production, runner, fault-injection,
evidence-admission, deployment, output, or credential authority.

## Public contract

The public function accepts exactly ten inputs, in this order:

1. frame;
2. detached authentication bundle;
3. separately injected synthetic trust policy;
4. separately injected synthetic signer-authorization policy;
5. detached authorization request;
6. separately injected synthetic T07 track-profile policy;
7. detached T07 track-profile request;
8. separately injected synthetic T08 subject-binding policy;
9. detached T08 subject-binding request; and
10. mode.

The mode is rejected before any other input is observed. Only
`SYNTHETIC_KAT` is accepted. After the mode check, the verifier calls the
frozen T07 public reviewer exactly once, validates the T08 policy, and observes
the T08 request last.

The T08 request is a closed object containing exactly:

- `prerequisite_id`
- `source_id`
- `build_id`
- `session_id`
- `channel_id`
- `schedule_id`
- `row_set_id`
- `subject`

Each selected policy row matches ten dimensions by exact ASCII byte equality:
the T07 receipt `content_sha256`, its `track_id`, and all eight request
fields. Zero matches and multiple matches reject. Wildcards, prefixes,
hierarchies, inheritance, normalization, case folding, and substitution are not
implemented.

The policy contains exactly two ordered profiles: managed first, self-hosted
second. Both positive KATs traverse the real frozen T07→T06→T05 chain.

## Security and truth boundary

The returned 93-field receipt records the selected labels and predecessor
identity, but keeps each corresponding truth claim false. T08 does not parse
the frame after T07 succeeds and never accepts a caller-supplied predecessor
receipt. The track comes only from the exact T07 receipt.

After release, the isolated-lab surface is six of six components and covers
T01–T08. T09 content identity and quarantine custody remains unauthorized.
All production controls and runtime prerequisites remain zero; side effects
remain `NONE`.

## Verification

The independent checker contains separate source-AST, closed-JSON,
policy/request, predecessor-receipt, fixture/schema, and receipt-oracle checks.
Its contract lane runs two real positive predecessor reviews plus 167 directed
negative tests:

- 4 mode-before-observation tests;
- 4 exactly-once/order tests;
- 19 policy JSON tests;
- 19 request JSON tests;
- 60 policy closed-world tests;
- 49 request exact-field tests;
- 8 predecessor-receipt binding tests; and
- 4 default-deny tests.

The source-bound shell gate is the distinct security lane. It verifies the
eight-path packet delta, modes, raw hashes, dependency archive, topology,
checker stdout, self-test stdout, and the current T08 authority gate. These are
implementation-independent lanes, not a claim of two independent human
reviewer identities.

Frozen checker receipts:

- normal stdout: 48 lines,
  `f08708c42399e94064b1452cfbccaa287462fc18e236b9daed96217affd5f4a4`;
- self-test stdout: 16 lines,
  `7adebf036b5f58f8591cc7585eacd3886f9e802277496d5303ee2c357c6a1c28`;
- authority fast stdout: 144 lines,
  `19f63fd5a896346d5451972344abc82de187d0d1265a49fa6aad004fe01df9e8`;
- authority full stdout: 145 lines,
  `779d124f5b71904221ede99a0199dcd53ef404ef4790aea5584f62ed93d40d99`.

Core raw identities:

- source: `2752e8b4ca393f5db14d7c980e65a5a71cdbff38a4eb19c861fffe5cc3ffc7f8`;
- checker: `54a37862f166d524791914239299529a746809a3b5b3305f04273cba856b6e10`;
- fixture: `ab966ecef10652730b752f3308326f8fdba9cf61a3b688cfe421efc3788567c6`;
- schema: `40d23b17f45f0c4cec7fa83e76b6edbf3616d3cb70a5466a3a111d33bab0c841`;
- expected TSV: `f08708c42399e94064b1452cfbccaa287462fc18e236b9daed96217affd5f4a4`;
- manifest: `efec8f434b3e957d8a2229cecc0172b9da69a14039dede8b94f7e137ae9d24fe`.

## Authority consumption and release

The implementation gate invokes only the current T08 authority gate. That
authority gate owns T07 and all deeper replay, so the implementation gate never
calls T07 separately.

Source `fast`, integrated `fast`, and failed `full-replay` do not consume
the implementation authority. Only a passing `full-replay` on an ordinary
two-parent integration commit consumes this exact non-transitive authority and
releases T08. The source commit must have the frozen baseline as its sole
parent; the integration commit must keep current main as first parent and the
source commit as second parent.

No historical control name or successful replay authorizes T09 or any other
successor.
