# S609 Story executor runtime verifiers review

S609 implements and statically accepts three fail-closed adapters: an
HMAC-SHA-256 authorization verifier, a streaming CPU INT4 model-bundle
verifier, and the fixed nonce-store path accessor.

The authorization adapter keeps the complete signed envelope outside S606 and
exposes a verifier closure that accepts only the exact eight-field executor
view. The model adapter rejects path, content, size, contract, and symlink
drift, and hashes every bound file before returning true.

This stage uses synthetic keys and tiny synthetic model files only. It does not
load a real secret, create the nonce parent/database, import or call the
executor, load ONNX Runtime, render, play, record, or write memory. Secure
configuration and an executor composition entrypoint remain separate gates.
