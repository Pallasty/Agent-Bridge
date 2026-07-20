# S21B-A16 request-instantiation preconditions

S21B-A16 compiles the A15 template set into a precondition matrix. For every
future evidence-request template it requires a fresh scope binding, freshness
attestation, revocation clearance, and independent review evidence. The matrix
records all of these as absent and therefore prohibits instantiation.

This is a rule definition, not a request lifecycle. It does not create an
instance, select a recipient, access a credential, read real input, contact an
external system, or accept evidence. A future system must supply new,
request-specific bindings and undergo a separate review; none can be inherited
from A9–A15 or from another template.

The builder verifies A15's self digest, contract binding, exact request IDs,
and nonreusability flags before emitting a self-digested prohibition matrix.
Tampering a binding status or changing the prohibition state fails closed.
