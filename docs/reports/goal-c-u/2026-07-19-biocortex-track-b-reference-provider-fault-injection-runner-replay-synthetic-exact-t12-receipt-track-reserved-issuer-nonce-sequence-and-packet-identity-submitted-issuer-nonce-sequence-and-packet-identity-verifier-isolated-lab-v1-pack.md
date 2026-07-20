# BioCortex Track B T13 replay synthetic verifier v1

Date: 2026-07-19

Status: exact authorized isolated-lab implementation; release evidence exists only after ordinary integration and full-gate PASS.

The twenty-input API observes mode first, calls frozen T12 exactly once, validates a separately injected ordered two-profile replay policy, and observes the detached three-field submission last. Matching binds exact T12 receipt, track, submitted issuer nonce, sequence and packet SHA-256. Any equality to the selected profile's reserved nonce, sequence or packet identity rejects through `E_PRODUCTION_REPLAY_REJECTED`.

Evidence covers managed and self-hosted positive tracks, individual replay dimensions, malformed and noncanonical data, mode pre-observation, policy-before-request ordering, single predecessor invocation, source capability guards and exact authority/semantic bindings.

The implementation consumes T13 isolated-lab authority and moves the synthetic surface to eleven components/T01–T13. It does not implement durable reservation, atomic CAS, issuer authentication, custody, retention, tombstones, distributed consensus, runtime/provider effects or production replay protection. Production controls remain 0/14, runtime threats 0/20, prerequisites 0/16 and real evidence zero. T14+ remains unauthorized.
