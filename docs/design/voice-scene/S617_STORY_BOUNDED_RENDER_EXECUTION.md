# S617 Story bounded-render execution

S617 crosses the render-only runtime boundary once for the fixed chapter-two
three-segment fixture. It uses a newly generated 300-second owner envelope, the
installed `story-render-owner-v1` key, S613 preparation, and the S606 executor.

The first pre-nonce attempt exposed and fixed an integration defect: S606 passes
its pinned S604 execution contract to the model-verifier callback, while the
S609 verifier validates the distinct pinned S608 runtime contract. S610 now
adapts that interface while validating and digest-binding the supplied S604
contract before delegating model verification to captured S608. A regression
test covers both acceptance and S604 drift rejection.

The next attempt passed model admission and consumed its nonce, then exposed an
atomic-file naming mismatch: S606 supplied `00.wav.part`, while the real
`soundfile` writer selects its container from the final suffix. S606 now uses
`00.part.wav`, preserving both a recognizable WAV suffix and atomic rename.
Its failure cleanup removed the owned output directory and partial artifacts;
the consumed nonce remains in the audit database and cannot be replayed. The
successful retry therefore uses a third fresh envelope and a second consumed
nonce. S617 records all three key reads/envelopes, the pre-nonce rejection, and
the post-nonce failure rather than collapsing them into a single attempt.

The admitted effects are limited to creating the fixed render root and output
directory, creating and consuming one persistent nonce, loading the pinned CPU
INT4 ONNX model, and writing three segment WAV files, one assembled WAV file,
and the executor receipt. Playback, recording, cache writes, network access,
GPU access, and AB memory writes remain outside this stage.

The render evidence root is on the existing `/Data` `fuseblk` mount. That mount
reports fixed `0777` modes even when a directory is created with `0700`, so
S617 records the observed mode and makes no POSIX privacy claim for audio
evidence. Secret custody remains separate on the native POSIX filesystem, where
the runtime directory and key/nonce files enforce `0700` and `0600`.

The repository result intentionally records no MAC, nonce, authorization ID,
or key material. The installed key is read once into a mutable buffer for
signing and preparation, then that buffer is best-effort cleared. This is not a
claim of complete Python object or process-memory zeroization. The short-lived
envelope is not persisted, and references to the envelope and prepared grant
are discarded after execution.

Acceptance requires the result schema, the executor receipt schema, live WAV
metadata and hashes, the recorded `fuseblk` output semantics, the private
nonce-store mode, exactly one consumed nonce row, natural EOS for all three
segments, and explicit false playback and memory authorization.
