# BioCortex Track B T12 owner-TOCTOU synthetic verifier v1

Date: 2026-07-19

Status: exact authorized isolated-lab implementation; release evidence exists only after ordinary integration and full-gate PASS.

## Implemented contract

The eighteen-input API observes mode first, calls the frozen T11 reviewer exactly once, validates a separately injected two-profile owner-epoch policy, then observes the detached two-field request last. Matching binds the exact T11 receipt hash, track, validation owner epoch and decision-recheck owner epoch. Both nonnegative signed-int64 epochs must be exactly equal.

Managed binds T11 receipt `63f0c26f...be2ed8` to `41/41`; self-hosted binds `ce5af4f0...e2ed8` to `73/73`. Zero, multiple, drifted, malformed, negative, Boolean, production, unknown and subclass inputs reject fail-closed. Epoch mismatch maps to `E_PRODUCTION_OWNER_IDENTITY_OR_WINDOW_FAILED`.

## Evidence and boundary

The implementation is standard-library Python, public-data-only, serial, and invokes one T11 predecessor review per case. The independent checker covers both tracks, directed mutations, source imports/capabilities, exact authority binding and T12 semantic binding.

This component consumes the single-use T12 isolated-lab authority and moves the synthetic surface to ten components/T01–T12. It does not implement or prove real owner identity, role, signature, authorization, set membership, revision, deadline, trusted time, production window, durable ledger state, provider state or runtime action. Production controls remain 0/14, runtime threats 0/20, prerequisites 0/16 and real evidence zero. T13+ is unauthorized.
