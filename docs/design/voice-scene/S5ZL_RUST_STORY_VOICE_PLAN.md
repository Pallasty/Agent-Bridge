# S5ZL: Rust story voice-plan parity

## Result

The unexported native story module now validates accepted role mapping and
explicit pacing policy, splits source-grounded attributed dialogue, assigns the
narrator and character Qwen voices, preserves Unicode source spans, derives
structural transitions, and hashes the complete voice plan canonically.

The fixed cross-language vector reproduces Python's five segments, four
transitions (`paragraph_break`, two `speaker_turn`, and `scene_break`), source
normalization metadata, and plan SHA-256
`f6cbc5aa1eba5b4b5a722fe3be6224a17b8ffd14c95325b31d0ed060ad6a0113`.
The first segment plus fixed model evidence also reproduces the Python cache
key `5599579c3cc255c44ba645750dc1fafa0d12904ecc158e85905c7f506703a7b6`.

## Boundary

This unit consumes already structured, accepted evidence. It does not infer or
approve voices, call Qwen, render or play audio, verify WAV/ASR output, write a
cache or memory, export the module, or register an MCP tool. Ambiguous or
unaccepted inputs remain review-blocked or fail closed.

## Next gate

S5ZM may compose the Rust request, source ingest, voice plan, bounded request
projection, and negative controls into complete S5ZF preflight parity. Runtime
registration remains a separate owner-authorized action after that proof.
