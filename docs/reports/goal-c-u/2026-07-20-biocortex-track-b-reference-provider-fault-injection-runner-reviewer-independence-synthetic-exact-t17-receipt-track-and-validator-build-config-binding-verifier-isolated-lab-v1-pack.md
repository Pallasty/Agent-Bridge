# BioCortex Track B T18 synthetic review-independence verifier

This pure offline KAT consumes only the exact T18 authorization. It calls T17 once, then matches a detached canonical three-digest request — synthetic reviewer identity, validator build, and validator configuration — against the exact T17 receipt track profile. Drift, substitution, malformed data, ambiguity, or a non-independent identity model fails closed as `E_PRODUCTION_INDEPENDENT_REVIEW_FAILED`.

It has no real reviewer, build, configuration, network, provider, runtime, or production access. A successful receipt consumes T18 only, makes the synthetic candidate surface 16, and leaves T19 unauthorized.
