# S5ZJ: Rust story contract core

## Result

The first native migration unit is implemented as a pure, unexported Rust
module. It parses the structured S5ZG request, validates the currently bounded
dry-run source contract, emits recursively key-sorted compact JSON, computes
SHA-256 over its UTF-8 bytes, and reproduces the S5ZF segment cache key.

Five Rust tests bind these operations to fixed Python-oracle vectors, including
Chinese text and a non-ASCII object key. Invalid source suffixes, live-mode
requests, and chapter zero fail closed.

## Boundary

`story_contract.rs` is deliberately not declared from `lib.rs` or `main.rs`.
It reads no source file, performs no chapter ingest, creates no voice plan, and
has no MCP/runtime authority. It cannot load a model, render or play audio,
write cache or memory, or spawn a child process. The integration test imports
the file directly so this parity unit remains removable without changing the
accepted Python oracle.

## Next gate

S5ZK may build source-byte hashing, TXT/Markdown decoding, chapter discovery,
and chapter selection on this core, with cross-language golden parity. It must
remain unregistered and non-actuating.
