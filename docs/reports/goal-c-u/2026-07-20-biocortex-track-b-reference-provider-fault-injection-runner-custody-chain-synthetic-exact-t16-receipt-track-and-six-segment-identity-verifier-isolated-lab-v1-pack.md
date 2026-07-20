# BioCortex Track B T17 synthetic custody-chain verifier v1

This is the exact, single-use successor authorized by the published T17 CUSTODY decision. It accepts only canonical, detached synthetic JSON and first calls the frozen T16 owner-set verifier exactly once. The T17 request consists of six SHA-256 identities — raw, canonical, validation, retention, cleanup, and tombstone — and is matched against the sole profile corresponding to the T16 receipt track.

The two fixed profiles are `MANAGED_SPANNER_CLOUD_KMS` and `SELF_HOSTED_ETCD_OPENBAO`. A mismatch, reordered value, missing field, duplicate value, malformed JSON, non-canonical JSON, unknown mode, or predecessor failure is rejected fail-closed; chain-request failures use `E_PRODUCTION_CUSTODY_FAILED` as the modeled threat disposition.

The component is a pure offline KAT. It performs no custody, retention, cleanup, tombstone, network, provider, runtime, or production action; it asserts no real-evidence claim. Successful isolated-lab integration consumes T17 only and raises the synthetic candidate surface from 14 to 15. T18 remains unauthorized.
