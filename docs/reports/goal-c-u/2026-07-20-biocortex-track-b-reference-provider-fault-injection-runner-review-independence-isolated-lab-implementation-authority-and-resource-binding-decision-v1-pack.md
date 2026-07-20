# BioCortex Track B T18 review-independence isolated-lab authority decision

The T18 threat is `REVIEW_INDEPENDENCE`: a reviewer is not independent, or the validator build/configuration binding drifts. The required modeled disposition is fail-closed through `E_PRODUCTION_INDEPENDENT_REVIEW_FAILED`.

This decision authorizes exactly one future, offline implementation. Its thirty public inputs preserve the T17 invocation unchanged, then add a separately injected two-profile policy and a detached three-digest request. Each profile binds the exact T17 receipt and track to a synthetic reviewer identity digest, validator build digest, and validator configuration digest. Profiles are fixed in managed then self-hosted order; an absent, malformed, substituted, reordered, cross-track, reviewer, build, or config value must reject.

The decision is non-transitive and remains unconsumed. It authorizes no real reviewer identity or independence determination, no real validator build/config binding, and no network, provider, runtime, or production operation. Integration of only the exact successor may consume it and move the isolated-lab candidate surface from 15 to 16; T19 remains unauthorized.
