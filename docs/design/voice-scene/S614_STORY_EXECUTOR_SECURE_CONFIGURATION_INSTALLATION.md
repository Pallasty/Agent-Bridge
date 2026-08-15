# S614 Story executor secure configuration installation

On 2026-08-01, the owner explicitly authorized the S614 actual installation in
the active Agent-Bridge session. The fixed, parameterless installer from source
commit `28a621a7` was invoked once from an isolated clean worktree.

The operation created the fixed runtime directory at mode `0700` and generated
one nonzero 32-byte authority key from `secrets.token_bytes`. It published the
closed key bundle at mode `0600` under active key ID
`story-render-owner-v1`. No key bytes or content digest are recorded in source,
logs, receipts, or this document.

Post-installation checks established:

- secure storage remains on `/home` ext4;
- directory and key ownership are `1000:1000`;
- the final key is a regular file with `nlink=1`;
- the S612 fixed fd-loader accepts the closed bundle and key ID;
- the mutable loader buffer was cleared after validation;
- the temporary publication file and nonce DB/WAL/SHM/lock are absent;
- the runtime directory contains only `authority-keys.v1.json`.

The exact redacted result is recorded in
`s614_story_render_secure_configuration_installation_result.json` and validates
against `story_render_secure_configuration_installation_result.schema.json`.

This installation does not authorize executor invocation. It did not create or
consume a nonce, load a model, run ONNX, render or play audio, record input, or
write AB memory. Those effects remain behind later, separate gates.
