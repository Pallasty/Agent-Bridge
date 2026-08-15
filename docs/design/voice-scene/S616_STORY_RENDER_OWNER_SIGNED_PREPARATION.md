# S616 Story render owner-signed preparation

On 2026-08-01, the owner explicitly authorized one real installed-key read, one
300-second Story render authorization envelope, and S613 preparation-only
validation. The authorization did not include nonce consumption or executor,
model, audio, recording, playback, or memory effects.

The one-shot in-memory orchestration built the exact three-segment chapter-two
request from the S602 preflight and S603 accepted fixture. S615 validated its
contract, model, output, installed-custody metadata, and nonce absence before
creating the unsigned proposal.

The S612 fixed loader then read `story-render-owner-v1` exactly once. A real MAC
was generated in memory. To preserve the single-read constraint, that already
loaded and short-lived context was lent to the unmodified S613 public
`prepare_installed_secure_bounded_render` entrypoint; S613 was invoked once and
accepted the envelope. Its authority verifier accepted the prepared narrow
authorization, while its model verifier was constructed but never invoked.

The loader buffer was cleared, and references to the envelope, nonce, MAC,
prepared request, and verifier were discarded after validation. Python cannot
guarantee secure erasure of immutable strings, so the receipt deliberately does
not claim that. None of those grant values were written to disk or emitted by
the orchestration. The durable receipt contains only
content-addressing hashes, timestamps, fixed public paths, counts, and Boolean
effects; it cannot be replayed as an authorization envelope.

The nonce database family and proposed output directory remained absent. S606
was neither imported nor called. No model was loaded, no ONNX graph ran, no
audio was rendered or played, and no AB memory was written.

The next gate is a separately owner-authorized nonce/executor transaction. This
S616 receipt does not authorize that gate and cannot be used as its grant.
