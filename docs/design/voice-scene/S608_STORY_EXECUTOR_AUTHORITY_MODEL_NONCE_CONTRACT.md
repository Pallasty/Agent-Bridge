# S608 Story executor authority, model, nonce contract

S608 turns the six external blockers found by S607 into four deterministic,
machine-readable contracts. It does not install configuration or execute the
renderer.

The render authorization is a ten-minute maximum, single-use HMAC-SHA-256
envelope over RFC 8785 canonical JSON with an explicit domain separator. Key
material remains outside the envelope and outside this repository. The future
verifier must use constant-time comparison.

The CPU INT4 model contract binds the seven ONNX files to the SHA-256 values
already recorded by S5G. S608 rechecks their live sizes and rehashes only the
small manifest and `inference.py`; it deliberately does not reread the roughly
2 GB model payload. A runtime verifier must stream-hash all seven files before
nonce consumption.

The nonce database has a fixed non-caller-controlled path outside the render
output root, with required `0700` parent and `0600` database modes, symlink
rejection, and a `BEGIN IMMEDIATE` uniqueness transaction. Neither the parent
nor database is created in this stage.

The bounded-render receipt now has a JSON Schema that preserves the separate
playback and memory authorization gates. The next stage may implement and
review the authority/model verifiers and fixed nonce wiring, but may not install
keys, execute ONNX, render, play, record, or write memory without a later gate.
