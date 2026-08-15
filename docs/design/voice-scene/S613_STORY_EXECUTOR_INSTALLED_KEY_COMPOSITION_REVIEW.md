# S613 Story executor installed-key composition review

S613 removes caller-supplied authority-key material from the public story-render
preparation interface. The only public entrypoint accepts three keyword-only
objects: the S604 execution contract, the complete signed authorization
envelope, and the bounded render request. The envelope's `key_id` selects a key
only through S612's fixed POSIX custody loader; there is no key, path, CLI, or
environment override.

Before either pinned dependency or the fixed key bundle can be read, the facade
requires the exact closed envelope field set, non-empty string values, and a
64-character lowercase hexadecimal MAC. The installed key context is then used
only to construct the HMAC authority verifier. Its mutable buffer is cleared on
context exit before request, model-support, or nonce-path preparation begins.
Those later steps reuse the same already validated, keyless dependency context,
so the runtime contract and verifier source cannot drift between the two phases.

Both dynamic source boundaries now hash and execute the same in-memory source
bytes. This closes the earlier check-then-import path race, while the S613
receipt binds the historical S612 review and the current evolved S610 and S612
source hashes. Historical S610-S612 receipts are not rewritten.

## Security limits

- Clearing is best-effort Python memory hygiene. `LoadedAuthorityKey.expose()`,
  JSON decoding, and `bytes.fromhex()` create immutable copies that Python
  cannot reliably overwrite; complete zeroization is explicitly not claimed.
- Private underscore helpers are an API boundary, not process isolation. Code
  already executing in this process is inside the trust boundary.
- `key_id` must select the fixed bundle record before its MAC can be verified;
  local key availability or timing differences are therefore not hidden.
- Executing the same hashed bytes closes a local file-loading race. It is not a
  trusted-boot, host-integrity, or software-supply-chain attestation.
- Authorization time-window enforcement and nonce consumption remain in S606's
  executor path and have not been invoked or authorized here.

No secure configuration was installed or read. No runtime directory, key,
nonce database, executor, model session, ONNX inference, audio, playback,
recording, or memory write occurred. The next gate is an explicit owner
authorization for secure configuration installation; it is not execution
authorization.
