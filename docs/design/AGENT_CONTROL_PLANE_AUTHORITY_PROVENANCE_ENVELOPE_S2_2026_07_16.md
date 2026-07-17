# Agent Control-Plane Authority And Provenance Envelope S2

Date: 2026-07-16

Status: DESIGN_FROZEN / STATIC_CONTRACT / SYNTHETIC_TRUST_BOUNDARY / NO_RUNTIME_AUTHORITY

## Decision

S2 defines the smallest independent authority/provenance envelope that could
close the identity, scope, session, resume, adapter, and external-evidence gaps
identified by S1. It also defines a deterministic offline verifier for frozen
synthetic fixtures.

This stage does not build a production authenticator. It tests the shape,
ordering, and fail-closed semantics that a future authenticator must satisfy.

## Threat Model

Assume an Agent can forge every value originating in:

- prompt or model output;
- current or resumed session text;
- adapter-provided metadata;
- owner, reviewer, and decision-source strings;
- forum, memory, commit, and evidence references;
- self-reported completion or approval fields.

Consequently, an envelope cannot authenticate itself. S2 separates:

1. an evaluator-owned trusted-receipt record, standing in for an independently
   verified external receipt; and
2. an Agent-presented envelope, which must bind byte-for-byte to that trusted
   record before policy checks can succeed.

Both live in one offline fixture for reproducibility. That co-location is a
test harness convenience, not a deployable trust architecture.

## Claims Bound By The Envelope

The canonical claims contain:

- envelope version and receipt identity;
- issuer and principal identity;
- action class;
- target and scope digests;
- decision-source digest;
- session-epoch and resume-parent digests;
- adapter identity, build digest, and capability digest;
- issuance and expiry timestamps;
- nonce;
- evidence digest;
- verifier identity and policy version.

All digest fields use the form sha256 followed by a colon and 64 lowercase
hexadecimal characters. S2 checks their shape but does not dereference the
underlying object.

## Canonical Claims Digest

The checker serializes fields in a fixed order under a fixed domain separator.
Strings and unsigned integers have distinct type tags. Every field name and
string value is length-prefixed; integers are encoded as big-endian u64.
SHA-256 is then applied to the resulting bytes.

The checker computes this digest independently for:

- the trusted receipt claims; and
- the Agent-presented envelope claims.

The values must match. A digest supplied by the Agent is never accepted as the
source of truth.

## Synthetic Attestation Boundary

Each trusted fixture receipt also has a synthetic attestation token. The token
models successful lookup of an external verifier receipt. It is intentionally
not a signature, MAC, certificate, credential, or proof of key possession.

A future production stage must replace this token lookup with an actual
independent verifier and a durable replay store. S2 makes no claim that its
fixture token is cryptographically authentic.

## Verification Order

The verifier derives exactly one state, using this precedence:

1. unavailable: the independent verifier cannot be consulted;
2. invalid: receipt lookup, synthetic attestation, canonical binding,
   structural validity, trust chain, policy version, or time-window ordering
   fails;
3. stale: the receipt is expired or not yet valid outside allowed skew;
4. replayed: the nonce is already consumed;
5. out_of_scope: the authenticated claims do not match the current requested
   action, target, scope, decision source, session/resume lineage, adapter, or
   evidence;
6. verified: every preceding check passes.

Reasons are emitted in deterministic lexical order. Expected fixture labels
are comparison data only and are not classifier inputs.

## Runtime Consumption Rule

A verified S2 result may only be cited as evidence in a later human T6 review.
It does not directly authorize or execute anything.

Every report must explicitly keep these fields false:

- may_dispatch;
- may_run_shadow;
- may_enable_runtime;
- may_write_memory;
- may_write_graph;
- may_change_retrieval;
- may_change_session;
- cryptographic_authenticity_proven;
- production_authority_granted.

Raw Agent claims, including a correctly shaped but unbound envelope, never
count as authority.

## Source Lineage

- current T6 source commit:
  a1c9469e9a14cd73159d34974f0e99714ce5a1f0
- S1 result commit:
  232cadaced8ac1ab6e18907d451fba9208d03079
- S1 mapping fixture SHA-256:
  a08d3faf25b82fd84f5f0e27bba55485a6b3f9d3e00a9f22413eb9a971b37c8e

The S2 checker embeds the S1 design, mapping, and result as inert bytes and
verifies their frozen hashes. It invokes no T6 or MCP function.

## Acceptance

The frozen suite contains four verified controls and nineteen rejecting cases.
It independently exercises:

- unknown receipt, forged attestation, and claim tampering;
- untrusted issuer/principal/verifier and wrong policy;
- malformed claims and invalid time ordering;
- expiry, future issuance, and nonce replay;
- action, target, scope, decision source, session, resume, adapter, and
  evidence mismatches;
- verifier unavailability.

Acceptance requires:

- 23 unique cases with exact expected status and exact reasons;
- four verified controls and zero verified adversarial cases;
- zero false accepts and zero control false rejects;
- all six states represented;
- source hashes and parent lineage unchanged;
- all authority fields false;
- byte-identical output across repeated runs.

## Deferred Work

S2 does not include real keys, signing, certificate or identity-provider
integration, a network verifier, a nonce database, a T6 consumer, MCP surface,
feature flag, runtime admission, shadow execution, deployment, or master
merge. Each is a separate higher-side-effect gate.
