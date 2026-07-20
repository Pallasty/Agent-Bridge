# BioCortex Track B T14 concurrent-replay synthetic verifier v1

Date: 2026-07-19

Status: exact authorized isolated-lab implementation; release evidence exists only after ordinary integration and full-gate PASS.

The twenty-two-input API observes mode first, calls frozen T13 exactly once, validates a separately injected ordered two-profile concurrent-replay policy, and observes the detached five-field request last. Matching binds the exact T13 receipt, track, reservation-key SHA-256, both observed generations and both CAS-result booleans. The generations must be equal nonnegative signed-int64 values and exactly one synthetic contender must win; generation divergence, zero winners or two winners reject through `E_PRODUCTION_REPLAY_REJECTED`.

Evidence covers managed and self-hosted positive tracks, every policy/request dimension, malformed and noncanonical data, mode pre-observation, policy-before-request ordering, single predecessor invocation, source capability guards and exact authority/semantic bindings.

The implementation consumes T14 isolated-lab authority and moves the synthetic surface to twelve components/T01–T14. It does not create threads, perform compare-and-swap, establish linearizability, persist replay state, exercise provider/runtime effects or implement production concurrency protection. Production controls remain 0/14, runtime threats 0/20, prerequisites 0/16 and real evidence zero. T15+ remains unauthorized.
