# BioCortex Track B T14 concurrent-replay implementation authority decision v1

Date: 2026-07-19

Status: one exact reversible isolated-lab T14 implementation becomes authorized only after ordinary integration and full-gate PASS.

Exact successor: `REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_CONCURRENT_REPLAY_SYNTHETIC_EXACT_T13_RECEIPT_TRACK_RESERVATION_KEY_CONTENDER_A_AND_B_OBSERVED_GENERATION_AND_CAS_RESULT_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`.

The future API has twenty-two inputs: T13's nineteen pre-mode inputs, separate concurrent-replay policy, detached request, then mode. Mode is observed first; T13 is called exactly once; policy precedes request. The closed request has reservation key SHA-256, A/B observed generation, and A/B CAS result. Both contenders observe the same nonnegative signed-int64 generation, and exactly one Boolean CAS result may be true. Zero or two winners reject with `E_PRODUCTION_REPLAY_REJECTED`.

These are public synthetic interleaving labels. This does not implement threads, linearizability, atomic storage, CAS, locking, durable replay state, issuer authentication, provider/runtime effects or production concurrency. Standard-library Python only, network/spend/credentials zero, one worker, one T13 call, policy <=64 KiB, request <=16 KiB, scratch <=64 MiB.

Current surface remains eleven components/T01–T13. This decision implements zero components and does not consume authority. Only the exact successor may consume it and reach twelve components/T01–T14. T15+ is unauthorized; production controls remain 0/14, runtime threats 0/20, prerequisites 0/16 and evidence zero.
