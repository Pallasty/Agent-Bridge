# S612 Story executor POSIX runtime binding review

S612 completes the source-side migration required by S611. The active S608
contract, S609 verifier, and S610 preparation now bind nonce custody to
`/home/pallasting/.agent-bridge-secure/story-render/story-render-nonces.sqlite3`.
The old `/Data/Models/...` FUSE path remains only as rejected historical
evidence in S611.

S612 also implements the fixed authority-key loader. It walks every parent with
directory descriptors and `O_NOFOLLOW`, opens the key with
`O_RDONLY|O_NOFOLLOW|O_CLOEXEC`, and validates regular-file type, exact mode,
UID/GID, and `nlink=1` using `fstat` on the same descriptor. The closed bundle
schema requires one active key, unique IDs, 32-byte nonzero keys, and explicit
active/verify-only/revoked status. Unknown and revoked keys fail closed.

Loaded key bytes live in a short-lived mutable context and are overwritten on
exit. This is best-effort Python memory hygiene, not a claim of hardware-backed
or allocator-wide zeroization.

No configuration was installed or read from the fixed path. No directory,
key, nonce database, model session, audio, playback, recording, or memory write
was created. The next stage must compose this installed-key loader into the
preparation entrypoint before any installation or invocation gate is opened.
