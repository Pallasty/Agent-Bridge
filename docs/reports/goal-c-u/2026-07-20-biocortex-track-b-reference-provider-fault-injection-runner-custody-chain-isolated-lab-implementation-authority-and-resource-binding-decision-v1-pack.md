# BioCortex Track B T17 custody-chain isolated-lab authority decision

Date: 2026-07-20

Status: exact bounded reversible authority for one future synthetic implementation; this decision implements zero components and does not consume authority.

The authorized successor is a twenty-eight-input synthetic verifier. It observes mode first, invokes frozen T16 exactly once, validates a separately injected two-profile policy, then accepts a detached six-segment identity chain: raw, canonical, validation, retention, cleanup and tombstone SHA-256 identities. Any absent, malformed, substituted, reordered or cross-track segment rejects through `E_PRODUCTION_CUSTODY_FAILED`.

The profiles bind exact T16 receipts, tracks, a synthetic chain domain and exactly six segments. This is deterministic KAT identity checking only. It does not access, retain, clean up or tombstone real evidence, and does not establish production custody, retention, provider, runtime or network authority.

Current surface remains fourteen components/T01–T16. Only the exact successor may consume this authority and reach fifteen components/T01–T17. T18+ remains unauthorized.
