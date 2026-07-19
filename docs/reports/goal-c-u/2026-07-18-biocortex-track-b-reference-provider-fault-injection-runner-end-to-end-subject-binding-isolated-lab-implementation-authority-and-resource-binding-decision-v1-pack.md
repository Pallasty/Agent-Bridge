# BioCortex Track B T08 end-to-end subject-binding implementation authority and resource decision v1

Date: 2026-07-18

Status: exact reversible isolated-lab implementation unit authorized only after
an ordinary integration and successful full replay of this decision gate.

## Decision

The project owner directive to continue the next bounded unit authorizes one
exact successor:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_END_TO_END_SUBJECT_BINDING_SYNTHETIC_EXACT_T07_RECEIPT_TRACK_PREREQUISITE_SOURCE_BUILD_SESSION_CHANNEL_SCHEDULE_ROW_SET_AND_SUBJECT_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`

The authority is single-use in intent, non-transitive, default-off, and limited
to reversible code, schema, public synthetic fixtures, tests and documentation.
It becomes effective only after this decision's ordinary two-parent integration
passes the full gate. The decision full gate does not consume the new authority;
only the exact later successor integration plus its full gate may consume it.
No external single-use ledger exists, so global single-use is not claimed.

The semantic actor is `pallasting / PROJECT_OWNER`, bound from the established
project profile plus current-session continuity. No owner signature,
cryptographic identity proof, trusted decision timestamp, runtime owner identity
or runtime admission decision was observed.

## Exact T08 contract

T08 is the `SUBJECT_BINDING` threat case. Its detached request is closed-world
and has exactly eight ASCII fields, in this order:

1. `prerequisite_id`
2. `source_id`
3. `build_id`
4. `session_id`
5. `channel_id`
6. `schedule_id`
7. `row_set_id`
8. `subject`

The policy has two ordered entries: managed, then self-hosted. Each entry matches
ten exact dimensions: T07 receipt content SHA-256, the non-substitutable
`track_id` carried by that receipt, and the eight detached request fields.
Matching is exact ASCII byte equality. Zero matches, multiple matches, wildcard,
prefix, hierarchy, inheritance, cross-track substitution, omitted fields and
additional fields reject fail-closed.

The future public API has exactly ten inputs. `mode` is syntactically last but
must be observed first. Production and unknown modes reject before any other
input observation. In `SYNTHETIC_KAT`, the frozen T07 public reviewer is invoked
exactly once. The separately injected T08 policy is reviewed after T07 success;
the detached T08 request is observed last.

The T07 receipt hash provides the predecessor commitment. The T08 verifier must
not accept a caller-supplied T07 receipt, receipt hash or track. It must not
reparse the frame, duplicate T07/T06 review, or derive policy from the frame,
authentication bundle or request.

This is a synthetic binding verifier, not a truth oracle. A successful match
does not prove prerequisite, source, build, session, channel, schedule, row-set
or subject truth/currentness. It does not authenticate a provider, profile,
namespace or configuration. It accepts no real evidence and grants no output,
fault, runner, deployment, runtime or provider authority.

## T07 / T08 / T09 separation

- T07 (`TRACK_ISOLATION`) is already released: exact packet profile,
  provider-or-lab profile, namespace, configuration and non-substitutable track.
- T08 (`SUBJECT_BINDING`) is the sole authorized successor component: exact
  prerequisite, source, build, session, channel, schedule, row-set and subject
  labels bound to the T07 receipt chain.
- T09 (`CONTENT_IDENTITY`) remains unauthorized: raw/canonical content identity,
  quarantine custody, append-only history and replay CAS.

The historical production control is `TRACK_SUBJECT_BINDING` with failure code
`E_PRODUCTION_TRACK_SUBJECT_BINDING_FAILED`. That shared control name does not
turn this local T08 KAT into a production mitigation or satisfy the production
control.

## Frozen predecessor

The logical baseline and sole source parent is the released T07 ordinary
integration `4bcecaefad5f8a4173e9cc8e0ea8460897badbc3`, tree
`739de5525eb6b6d3d535f926f33f8fd9ac14e921`, with parents in order
`084eb71dd9c95fbc6285041b1503327705f9a6a1` and
`9a78dbc00705bacf42b629147753f48603d431bc`.

The T07 source has the sole parent `084eb71dd9c95fbc6285041b1503327705f9a6a1`.
Its integrated full receipt is 94 lines with SHA-256
`12a8a1f2f975bbdf83b66c925500e43abc5917c5ec65b237ede02e93fa220c31`;
it records `CONSUMED_SCOPE_COMPLETE`. Its integrated fast receipt is 93 lines
with SHA-256
`5be17dca5300e396d4d092fe15a9b7d5141ee97a25d150df87413bbabe9aa676`.

The T07 per-track receipt hashes are:

- managed: `5db2449ebf80e668ac7fc8ccaec6cc62a7461d8874809543a74ee9b7b5d725b6`
- self-hosted: `3f49518a74a6a7075335db5b139035613ff992d1deedc0c31216832dd4dcb014`
- ordered receipt set: `44c79026c2d98dc99e48dac4a1f047f634a521a5a224a0933a852ebe6c78776a`

## Artifact binding

The five non-self-referential current artifacts are frozen as follows:

| Artifact | SHA-256 |
|---|---|
| decision reviewer | `1d662858461645b69908791662b5503d016a91823087b6895b7a225c30f9f06b` |
| independent checker | `c8a7328cb9c50e8666e8b468a0d325fc0b0914b48a3b1e7cedee6266da7a2cb7` |
| owner decision record | `2fd96dd1bfc038c65ea067d69b928148763d7e8e0671ef3d378bc72118332277` |
| expected receipt TSV | `aa25a61c1da03c75042de8680037f8a895035310d48dccae0472d6eb8c8fafad` |
| pack manifest | `2804660412b1d8c20da95fe0eabd264f18208e8dee5d59733d6b0e29a47f2870` |

The eight T07 predecessor artifacts are frozen by raw SHA-256:

- receipt schema: `7cdbb084c193e5936cd66237504f40cd3d050a3b5f814c0e8e92992a68ac9634`
- reviewer source: `777bfaa0c18569e68af1cf7c6e5957f1712079bfcfe4e2085e607dba5c9fcb23`
- checker source: `27c25f6c75504925859d693d09c391a6f60ec2c34aab84dda26bd610d4b94e91`
- synthetic fixture: `97a45faa1a2e4d1198c5ea5222ada4d31e46093c8956ecb319a2912e46b5b4e4`
- expected TSV: `bb1bb0f215cf8e272335dbec1d6c7ac2958dd52985a090a9e9fbf2abaf72585a`
- pack manifest: `75bcb6f0a47395b0aa5969f8071701a5ef8d777e902c255299d069413278b7e5`
- implementation report: `31398214bd12861b8ae614e1a255dcd58325186d74602b6f8ef92e4f802be128`
- source-bound gate: `aad0e8e3a71cd1e5d94921613ccddf936cadf4a4a5099831c0aeecf243d7261d`

The historical semantic fixture is frozen at
`3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6`.
It contains the exact 14-control production table and the T08 mutation:
prerequisite, source, build, session, channel, schedule, row set or subject
mismatch. Offline conformance cannot satisfy that production control.

## Deterministic oracle and review contract

The normal checker emits 78 unique TSV keys. The self-test emits 16 lines and
exercises 779 directed negatives: JSON guards, closed-world mutations, full
grounding-matrix mutations, binding/profile boundary mutations, overclaim
mutations, section-hash mutations, receipt mutations and source-AST mutations.

The exact successor must receive at least two distinct reviewer lanes:

- `CONTRACT_CONFORMANCE_REVIEW`
- `SECURITY_AND_SOURCE_BOUND_GATE_REVIEW`

Neither lane is a production security approval. Production security reviewer
binding remains absent.

## Resource and operational boundary

- external paid spend cap: zero in all currencies;
- provider endpoints, credentials, private keys and seeds: none;
- network and provider calls: forbidden;
- dependencies: Python standard library only, no fetch;
- maximum workers: one;
- private scratch checkpoint cap: 64 MiB;
- permitted side effects: reversible local repository artifacts for the exact
  successor only.

Deep gates must run as one foreground managed process, serially, and the same
session must be polled until completion. Starting duplicate recursive replays is
forbidden because it previously caused OOM and swap exhaustion.

Current released isolated-lab state remains five components and T01–T07 / seven
local threats. This decision implements zero components and zero threats. Only a
later exact successor integration and full gate may raise the ceiling to six
components and T01–T08 / eight threats.

Production controls remain 0/14, runtime threats 0/20, runtime prerequisites
0/16, real/validated/accepted evidence 0, downstream gates 0/4, runtime and
provider authority false, and side effects `NONE`.
