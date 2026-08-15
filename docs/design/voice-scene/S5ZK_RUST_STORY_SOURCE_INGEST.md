# S5ZK: Rust story source ingest parity

## Result

The unexported Rust story contract module now reads bounded TXT/Markdown
sources, hashes the exact source bytes, rejects non-UTF-8 input, creates the
stable source identifier, discovers chapter headings, preserves Python-style
Unicode character offsets, and selects chapters from either the beginning or
an explicit ordinal.

The `story_s1.md` golden test reproduces the Python oracle's 232-byte and
88-character evidence, both stable chapter identifiers, line/character spans,
and chapter-two selection packet byte for byte after canonical serialization.
Missing chapters and invalid UTF-8 fail closed.

## Boundary

This is source indexing only. The module remains absent from `lib.rs`,
`main.rs`, and the MCP registry. It does not extract cast, relationships,
events, utterances, or voice plans; it does not load a model, render/play
audio, write a cache or memory, or spawn a process.

## Next gate

S5ZL may port voice-plan construction, render transitions, and their provenance
bound cache keys, using the accepted Python artifacts as non-authoritative
golden oracles. Registration and runtime actuation remain separate gates.
