# S21B-A15 nonreusable evidence-request templates

S21B-A15 turns the six A14 proof-boundary requirements into a canonical set
of evidence-request templates. A template specifies the future evidence class,
its exact requirement, and its nonreusability conditions. It does not issue a
request, open an external channel, read evidence, accept evidence, or grant a
capability.

Each template is `TEMPLATE_ONLY_NOT_REQUESTED`, requires a single-use response
binding, and explicitly forbids prior-response reuse. A future request must be
separately instantiated and reviewed against current scope, freshness,
authority, and revocation information; this template set cannot substitute for
any of those materials.

The builder independently checks the A14 register self digest, contract hash,
six requirements, and their unresolved status. It emits a self-digested set
with explicit negative authority/capability fields. Any altered register or
template reuse claim fails closed.
