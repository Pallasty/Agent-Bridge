# BioCortex Track B T13 replay implementation authority decision v1

Date: 2026-07-19

Status: one exact reversible isolated-lab T13 implementation becomes authorized only after ordinary integration and full-gate PASS.

## Exact successor

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_REPLAY_SYNTHETIC_EXACT_T12_RECEIPT_TRACK_RESERVED_ISSUER_NONCE_SEQUENCE_AND_PACKET_IDENTITY_SUBMITTED_ISSUER_NONCE_SEQUENCE_AND_PACKET_IDENTITY_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`

The future API has twenty public inputs: T12's seventeen pre-mode inputs, separately injected replay policy, detached submission request, then mode. Mode is syntactically last and observed first. T12 is called exactly once; replay policy is observed next and request last.

The request is a closed three-field object: `submitted_issuer_nonce`, `submitted_sequence`, and `submitted_packet_identity_sha256`. Each of two ordered profiles binds exact T12 receipt and track, a reserved nonce/sequence/packet identity, and the exact submitted triple. Any equality between submitted and reserved nonce, sequence, or packet identity rejects with `E_PRODUCTION_REPLAY_REJECTED`; all three must be distinct for a valid synthetic case.

## Boundary and resources

All identifiers are public synthetic labels. This does not implement durable reservation, atomic compare-and-set, nonce issuance, issuer authentication, packet custody, retention, tombstones, distributed consensus, production replay protection, runtime/provider effects, or T14+. Standard-library Python only; network/spend/credentials zero; one worker; exactly one T12 predecessor call; policy <=64 KiB; request <=16 KiB; private scratch <=64 MiB.

Current surface remains ten components/T01–T12. This decision implements zero components and does not consume authority. Only the exact successor's ordinary integrated full gate may consume it and reach eleven components/T01–T13. Production controls remain 0/14, runtime threats 0/20, prerequisites 0/16 and real evidence zero.
