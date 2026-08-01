# S610 Story executor secure runtime composition review

S610 adds a preparation-only composition entrypoint. It validates the S604
execution contract, loads the fixed S608 runtime contract, imports the
SHA-256-pinned S609 verifier source, validates the signed envelope and request,
and returns the exact six keyword arguments required by S606.

During composition review an S609 path defect was found and fixed: tokenizer
support assets live in the official Qwen snapshot, not an absent `tts/`
directory under the ONNX snapshot. S610 fixes that path and hash-checks the four
small files actually consumed by config/tokenizer setup. It does not reread the
official multi-gigabyte PyTorch weights.

The preparation module has no executor import or invocation, CLI, environment
secret loading, SQLite creation, ONNX Runtime import, rendering, playback,
recording, or memory write. Secure key and nonce-parent installation, followed
by separately authorized invocation, remain later gates.
