# S5ZF `/story` integration preflight

S5ZF connects the accepted static story pipeline without registering or
executing a production command. It reparses `/story PATH from-start` or
`/story PATH chapter N`, rereads the exact UTF-8 source, verifies its SHA-256
and chapter selection, then binds the accepted mapping, S5ZC voice plan, S5Y
role audition, S5ZE continuity result, and model inference hash.

Each prospective render request receives a deterministic cache key over source,
voice-plan, event, text, Qwen speaker, style instruction, voice-profile version,
and inference implementation. A changed source, role style/version, voice,
model, or plan therefore cannot silently reuse old audio. Runtime flags such as
`--play` remain forbidden, unavailable chapters fail closed, and every runtime
effect in the output is false.

The real chapter-two preflight selects three segments, excludes the four prior
segments, preserves two 1.0-second internal gaps and the 2.2-second preceding
scene break, and validates against the dedicated Draft 2020-12 schema. This is
an execution packet design, not execution authority: no MCP tool is registered,
no model is loaded, no ONNX graph runs, and no audio, cache, or memory is
written. The next gate is the static production-registration contract.
