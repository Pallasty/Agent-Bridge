# S21B-A11 independent static replay verifier

S21B-A11 independently verifies an A10 chain receipt against the four A9
transcripts. It has no dependency on the A10 builder at execution time. The
verifier replays canonical-byte, plan, contract, transcript, ordering, receipt
self-digest, and per-transcript digest checks using its own implementation.

Its validity boundary is intentionally exact rather than temporal: A11 freezes
the raw SHA-256 values of the A9 plan, A9 transcript contract, and A10 receipt
contract. A changed contract or plan is not silently accepted as equivalent;
it requires a new verifier version and a new review. There is no clock-based
freshness claim, owner authority, real experiment input, or execution permit.

On success, the verifier emits one canonical static-replay statement to
standard output. The statement is self-digested with an A11-specific domain
and commits the input receipt's raw SHA-256 and chain digest. Invalid input
emits no statement and exits 65. The A11 gate covers valid replay and receipt
body, transcript, and unexpected-field tampering.
