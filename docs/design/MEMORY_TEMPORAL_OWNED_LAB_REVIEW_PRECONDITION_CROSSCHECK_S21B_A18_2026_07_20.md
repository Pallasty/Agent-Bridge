# S21B-A18 review/precondition cross-check

S21B-A18 cross-checks an A17 minimum independent-review packet against the
A16 request-instantiation precondition matrix. It validates reviewer/subject
separation and the four required review digests, then independently verifies
that all four freshness bindings remain `REQUIRED_ABSENT`.

The resulting decision is necessarily non-instantiating: a structurally valid
review packet cannot satisfy absent scope, freshness, revocation, and review
bindings. The synthetic fixture is not accepted for capability change. The
cross-check emits no request and grants no authority, capability, input
admission, or side effects.
