# S615 Story render authorization proposal review

S615 adds the missing boundary between an exact bounded-render request and an
owner signature. The new proposal builder validates the S604 execution
contract, the S610 request/model bindings, and the S614 installed-custody
receipt before producing an unsigned, content-addressed proposal. Both the S610
composition source and S614 installation receipt are SHA-256 pinned so an
unreviewed dependency change fails closed.

The proposal fixes the authorization action, issuer, subject, and key ID. It
binds the contract digest, preflight digest, absent output target, request
digest, a five-minute TTL, and CSPRNG-generated public authorization/nonce
identifiers. Its proof field is named but explicitly absent, so the proposal is
not an authority envelope and cannot satisfy S613 by itself.

Custody inspection is metadata-only. The builder verifies the installed
directory/file identity, modes, owner, link count, and nonce-family absence. It
does not open the installed key bundle, load key material, calculate a key
digest, or generate a real MAC. Tests prove S609 canonical-field compatibility
only by adding a synthetic test MAC made from synthetic key material.

The accepted source has no executor, SQLite, ONNX, subprocess, environment, or
CLI surface. It creates no nonce store, output directory, model session, audio,
or memory record. S615 therefore does not authorize rendering or any other
actuation.

The next gate is
`owner_authorized_story_render_envelope_signing_preflight`. Crossing it requires
explicit owner authorization to read the installed key and generate one real
short-lived MAC. Even that gate must remain preparation-only: nonce consumption
and S606 executor invocation require a later, separate authorization.
